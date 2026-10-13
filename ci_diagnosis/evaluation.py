"""Reproducible experiments and Python-only output artifacts.

Run from the project root:
    python -B -m ci_diagnosis.evaluation --output experiments/evaluation_results.py
    python -B -m unittest discover -s tests -v

The workbook supplies labels/context, not real diagnostic observations.
Historical reconciliation, controlled legacy-policy comparisons, validation
repositories and test repositories are reported as separate experiments.
No empirical calibration or production-readiness claim is made.
"""

import argparse
import base64
import hashlib
import itertools
import json
import math
import platform
import sys
import zlib
from dataclasses import replace
from pathlib import Path

from . import __version__
from .compatibility import execute_notebook_compatibility
from .data import load_workbook, grouped_split
from .legacy import reconcile_saved_traces, original_unit_checks, reference_policy_run, DEFAULT_NOTEBOOK
from .metrics import (calculate_metrics, scored_record, paired_difference, risk_coverage,
                      DEFAULT_WRONG_LOSS, DEFAULT_REVIEW_COST)
from .model import default_model, fit_stage_model, STATES
from .policy import POLICIES
from .probability import ValidationError
from .records import plain, fingerprint, PublicCase
from .runner import diagnose, Limits
from .simulation import OutcomeBank, Scenario

DEFAULT_WORKBOOK = Path(__file__).resolve().parents[1] / "data" / "replication-labeling.xlsx"


def cohort_run(rows, model, scenario, seed, limits=None, policies=POLICIES):
    truths = {r.source_id: r.state for r in rows}
    bank = OutcomeBank(model, truths, seed, scenario)
    limits = limits or Limits()
    records = {policy: [scored_record(diagnose(r.public(), model, bank, policy, limits), r.state) for r in rows]
               for policy in policies}
    clusters = {r.source_id: r.project for r in rows}
    comparison = paired_difference(records["eig_per_cost"], records["lowest_cost"], seed=seed,
                                   repetitions=200, clusters=clusters) if {"eig_per_cost", "lowest_cost"}.issubset(records) else None
    return {"seed": seed, "scenario": plain(scenario), "model_version": model.version,
            "model_hash": model.model_hash, "limits": plain(limits), "bank": bank.manifest(limits.max_retries+1),
            "metrics": {p: calculate_metrics(rs) for p, rs in records.items()}, "records": records,
            "paired_cost_eig_minus_lowest": comparison,
            "descriptive_risk_coverage": {p: risk_coverage(rs) for p, rs in records.items()}}


def controlled_legacy_comparison(rows, model, seed=42):
    import pandas as pd
    frame = pd.DataFrame({"index": range(len(rows)), "state": [r.state for r in rows]})
    if any(sum(r.state == s for r in rows) < 10 for s in STATES):
        raise ValidationError("historical comparison requires at least ten cases per state")
    selected = [rows[i] for i in frame.groupby("state", group_keys=False).sample(n=10, random_state=42)["index"]]
    cases = [PublicCase(r.source_id, "Test" if any(w in r.step.lower() for w in
            ("test", "tests", "junit", "pytest", "cucumber")) else "Build") for r in selected]
    bank = OutcomeBank(model, {r.source_id: r.state for r in selected}, seed)
    records = {}
    for policy in ("eig_per_cost", "lowest_cost"):
        records["legacy_reference_"+policy] = [scored_record(reference_policy_run(c, bank, policy), r.state)
                                                 for c, r in zip(cases, selected)]
        records["corrected_unbounded_"+policy] = [scored_record(diagnose(c, model, bank, policy,
                    Limits(max_steps=10, budget=100, max_attempts=10)), r.state) for c, r in zip(cases, selected)]
        records["corrected_bounded_"+policy] = [scored_record(diagnose(c, model, bank, policy), r.state)
                                                  for c, r in zip(cases, selected)]
    for policy in ("fixed_test", "stage_map", "prior_map"):
        records[policy] = [scored_record(diagnose(c, model, bank, policy), r.state) for c, r in zip(cases, selected)]
    return {"status": "in-sample control; original policy functions, NEW shared synthetic bank",
            "stage_preprocessing": "original binary keyword rule for every policy in this control",
            "case_ids": [r.source_id for r in selected], "bank": bank.manifest(),
            "metrics": {p: calculate_metrics(rs) for p, rs in records.items()}, "records": records,
            "paired_correctness_effects": {p: paired_difference(
                records["corrected_unbounded_"+p], records["legacy_reference_"+p],
                field="correct", seed=seed, repetitions=200) for p in ("eig_per_cost", "lowest_cost")}}


def sensitivity(rows, model, seed=42):
    """One-at-a-time stress tests; no data-driven choice of favorable settings."""
    truths = {r.source_id: r.state for r in rows}
    fixed_bank = OutcomeBank(model, truths, seed)
    variants = [("reference", model, Limits()),
                ("uniform_prior", replace(model, version="sensitivity-uniform-prior/1", priors=dict.fromkeys(STATES, .25)), Limits()),
                ("threshold_0.80", model, Limits(confidence_threshold=.8)),
                ("threshold_0.95", model, Limits(confidence_threshold=.95)),
                ("budget_5", model, Limits(budget=5)),
                ("budget_15", model, Limits(budget=15, max_steps=10)),
                ("require_empirical_calibration", model, Limits(allow_uncalibrated=False))]
    weakened = []
    for a in model.actions:
        positive = {s: .7*a.outcomes["signal"][s] + .3*.5 for s in STATES}
        weakened.append(replace(a, outcomes={"signal": positive, "no_signal": {s: 1-positive[s] for s in STATES}}))
    variants.append(("weaker_agent_likelihoods", replace(model, version="sensitivity-weaker-likelihoods/1", actions=tuple(weakened)), Limits()))
    summary = {}
    for name, variant, limits in variants:
        records = [scored_record(diagnose(r.public(), variant, fixed_bank, limits=limits), r.state) for r in rows]
        summary[name] = calculate_metrics(records)
    for scale in (.5, 2.0):
        cost_model = replace(model, version=f"sensitivity-cost-{scale}/1",
                             actions=tuple(replace(a, cost=a.cost*scale) for a in model.actions))
        bank = OutcomeBank(cost_model, truths, seed)
        summary[f"action_cost_scale_{scale}"] = calculate_metrics([
            scored_record(diagnose(r.public(), cost_model, bank), r.state) for r in rows])
    baseline = [diagnose(r.public(), model, fixed_bank) for r in rows]
    for review_cost in (6.0, 24.0):
        summary[f"review_cost_{review_cost}"] = calculate_metrics([
            scored_record(r, row.state, review_cost=review_cost) for r, row in zip(baseline, rows)])
    for scale in (.5, 2.0):
        summary[f"wrong_loss_scale_{scale}"] = calculate_metrics([
            scored_record(r, row.state, wrong_loss={s:v*scale for s,v in DEFAULT_WRONG_LOSS.items()})
            for r, row in zip(baseline, rows)])
    unavailable_bank = OutcomeBank(model, truths, seed, unavailable=[a.action_id for a in model.actions])
    summary["all_tools_unavailable"] = calculate_metrics([
        scored_record(diagnose(r.public(), model, unavailable_bank), r.state) for r in rows])
    return {"status": "synthetic one-at-a-time sensitivity; no settings selected from these results", "seed": seed, "metrics": summary}


def run_experiment(workbook=DEFAULT_WORKBOOK, *, seeds=(42, 43, 44), split_seed=42, compatibility=True):
    if not seeds or len(set(seeds)) != len(seeds) or any(type(s) is not int for s in seeds):
        raise ValidationError("outcome seeds must be nonempty, unique integers")
    rows, source = load_workbook(workbook)
    train, validation, test = grouped_split(rows, split_seed)
    base = default_model()
    fitted = fit_stage_model(train, base)
    split = {name: {"case_count": len(cohort), "projects": sorted({r.project for r in cohort}),
                    "case_ids": [r.source_id for r in cohort], "class_counts": {s: sum(r.state == s for r in cohort) for s in STATES}}
             for name, cohort in (("train", train), ("validation", validation), ("test", test))}
    if any(set(split[a]["projects"]) & set(split[b]["projects"]) for a, b in itertools.combinations(split, 2)):
        raise ValidationError("repository split leakage")
    scenarios = (Scenario(), Scenario("noisy_unreliable", noise=.25, missing_rate=.1, error_rate=.05,
                                     timeout_rate=.05, inconclusive_rate=.05),
                 Scenario("correlated_signals", correlation=.8),
                 Scenario("biased_environment", noise=.25, signal_bias=.15))
    runs = [cohort_run(test, fitted, scenario, seed) for scenario in scenarios for seed in seeds]
    validation_run = cohort_run(validation, fitted, Scenario(), seeds[0])
    root=Path(__file__).resolve().parents[1]
    code_paths = sorted(list(Path(__file__).parent.glob("*.py"))+list((root/"tests").glob("*.py"))+
                        [root/"experiments/agent_simulation.py",root/"experiments/implementation_report.py"])
    code_hashes = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in code_paths}
    import pandas, openpyxl
    return {"implementation_version": __version__, "source": source, "runtime": {
                "python": platform.python_version(), "pandas": pandas.__version__, "openpyxl": openpyxl.__version__},
            "source_code_hashes": code_hashes, "split_seed": split_seed, "split": split,
            "loss_assumptions": {"wrong_report_by_true_state": DEFAULT_WRONG_LOSS, "review_cost": DEFAULT_REVIEW_COST,
                                 "origin": "declared newer-preprint costs; not empirically measured"},
            "model": plain(fitted), "model_hash": fitted.model_hash,
            "threshold_selection": "0.90 retained as declared assumption; no empirical calibration or test tuning",
            "original_unit_checks": original_unit_checks(), "historical_saved_output": reconcile_saved_traces(),
            "compatibility": execute_notebook_compatibility() if compatibility else None,
            "controlled_legacy_comparison": controlled_legacy_comparison(rows, base, seeds[0]),
            "validation_synthetic": validation_run, "test_synthetic": runs,
            "sensitivity_synthetic": sensitivity(test, fitted, seeds[0]),
            "limitations": ["diagnostic outcomes and effort are assumed, not observed in workbook",
                            "historical simulator and published V2 artifacts remain unavailable",
                            "heuristic stage labels, not independently validated stage annotations",
                            "single categorical cause; mixed faults remain unsupported",
                            "0.90 probabilities are uncalibrated; real human outcomes not evaluated",
                            "provider deadlines are cooperative; built-in providers are bounded local lookups",
                            "forced baselines deliberately bypass the automatic-report gate",
                            "repository-disjoint source counts do not establish live-CI generalization"]}


def write_python_artifact(path, result):
    path = Path(path)
    if path.suffix != ".py":
        raise ValidationError("evaluation artifacts in this project must use .py")
    # Full ledgers contain repeated schemas. Keep the Python-only artifact small
    # without truncating any observations, candidate scores or terminal records.
    def encode_special(value):
        if isinstance(value,float) and not math.isfinite(value):
            if math.isnan(value):
                raise ValidationError("NaN cannot be exported")
            return {"__infinite_metric__": 1 if value > 0 else -1}
        if isinstance(value,dict):
            return {k:encode_special(v) for k,v in value.items()}
        if isinstance(value,(list,tuple)):
            return [encode_special(v) for v in value]
        return value
    payload=json.dumps(encode_special(result),ensure_ascii=True,sort_keys=True,separators=(",",":"),allow_nan=False).encode()
    encoded=base64.b85encode(zlib.compress(payload,9)).decode("ascii")
    chunks="\n".join("    "+repr(encoded[i:i+120]) for i in range(0,len(encoded),120))
    text=('"""Complete versioned evaluation ledger, compressed to avoid duplicated schema text.\n'
          'Synthetic observations and costs; no production evidence.\n'
          'Regenerate: python -B -m ci_diagnosis.evaluation --output '+path.as_posix()+'\n"""\n'
          'import base64\nimport hashlib\nimport json\nimport zlib\n\n'
          'PAYLOAD_SHA256 = '+repr(hashlib.sha256(payload).hexdigest())+'\n'
          '_ENCODED = (\n'+chunks+'\n)\n\n'
          'def _metric_hook(value):\n'
          '    if set(value) == {"__infinite_metric__"}:\n'
          '        return float("inf") * value["__infinite_metric__"]\n'
          '    return value\n\n'
          '_payload = zlib.decompress(base64.b85decode(_ENCODED))\n'
          'if hashlib.sha256(_payload).hexdigest() != PAYLOAD_SHA256:\n'
          '    raise ValueError("Evaluation payload checksum mismatch")\n'
          'EVALUATION = json.loads(_payload, object_hook=_metric_hook)\n'
          'del _payload, _ENCODED\n')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", type=Path, default=DEFAULT_WORKBOOK)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44])
    parser.add_argument("--split-seed", type=int, default=42)
    args = parser.parse_args(argv)
    try:
        result = run_experiment(args.workbook, seeds=tuple(args.seeds), split_seed=args.split_seed)
        if args.output:
            write_python_artifact(args.output, result)
    except ValidationError as exc:
        print(f"Evaluation rejected: {exc}", file=sys.stderr)
        return 2
    print("Python implementation", __version__, "| notebook preserved", result["original_unit_checks"]["notebook_sha256"])
    print("Split:", {k: v["case_count"] for k, v in result["split"].items()})
    print("Synthetic held-out tests; assumed diagnostic outcomes and costs")
    print(f"{'Scenario':<26} {'Seed':<5} {'Policy':<15} {'Coverage':>9} {'Selective':>10} {'Brier':>8} {'Cost':>8}")
    for run in result["test_synthetic"]:
        for policy, m in run["metrics"].items():
            selective = 'n/a' if m["selective_accuracy"] is None else f'{m["selective_accuracy"]:.3f}'
            print(f'{run["scenario"]["name"]:<26} {run["seed"]:<5} {policy:<15} {m["coverage"]:>9.3f} '
                  f'{selective:>10} {m["brier"]:>8.3f} {m["average_total_decision_cost"]:>8.3f}')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

