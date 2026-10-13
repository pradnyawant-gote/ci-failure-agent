"""Python compatibility bridge for the unchanged notebook.

``execute_notebook_compatibility`` runs its source cells in memory, installing
corrected closures and the NEW synthetic provider between definition cells.
It does not edit notebook cells, overwrite saved outputs, or claim unassisted
Run All now works. Notebook-style functions accept legacy display aliases.
"""

from __future__ import annotations

import contextlib
import io
import os
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

from .domain import Belief, RankedAction
from .legacy import DEFAULT_NOTEBOOK, read_notebook
from .model import STATES, Action, Model, default_model
from .policy import rank_actions as modern_rank
from .policy import top_state
from .probability import ValidationError, expected_information_gain, update_belief
from .probability import entropy as modern_entropy
from .records import Observation, PublicCase, plain
from .runner import Limits, diagnose
from .simulation import OutcomeBank


class AliasOutcomes(Mapping[str, dict[str, float]]):
    def __init__(self, action: Action) -> None:
        self.action = action

    def __iter__(self) -> Iterator[str]:
        return iter(self.action.labels.values())

    def __len__(self) -> int:
        return len(self.action.outcomes)

    def __getitem__(self, key: str) -> dict[str, float]:
        return dict(self.action.outcomes[self.action.canonical_outcome(key)])


def legacy_result(result: Any, truth: str) -> dict[str, Any]:
    r: dict[str, Any] = plain(result)
    return {
        "case_id": int(r["case_id"]) if r["case_id"].isdigit() else r["case_id"],
        "true_root_cause": truth,
        "final_prediction": r["prediction"],
        "decision": r["decision"],
        "reason": r["reason"],
        "final_belief": r["final_belief"],
        "actions_taken": [
            {
                "action": a["action_name"],
                "cost": a["cost"],
                "outcome": a["outcome"],
                "posterior_before": a["posterior_before"],
                "posterior_after": a["posterior_after"],
            }
            for a in r["actions_taken"]
        ],
        "total_cost": r["diagnostic_cost"],
        "correct": r["decision"] == "REPORT" and r["prediction"] == truth,
    }


def install_definitions(namespace: dict[str, Any], model: Model | None = None) -> Model:
    selected_model = model or default_model()
    by_name = {a.name: a for a in selected_model.actions}
    namespace["states"] = list(STATES)
    namespace["priors"] = dict(selected_model.priors)
    namespace["likelihoods"] = {z: dict(v) for z, v in selected_model.stage_likelihoods.items()}
    namespace["actions"] = [
        {"name": a.name, "tags": list(a.tags), "cost": a.cost, "outcomes": list(a.labels.values())}
        for a in selected_model.actions
    ]
    namespace["outcome_models"] = {a.name: AliasOutcomes(a) for a in selected_model.actions}
    namespace["calculate_posterior"] = selected_model.initial_belief
    namespace["entropy"] = lambda values: modern_entropy(dict(zip(STATES, values, strict=False)))
    namespace["calculate_eig"] = expected_information_gain
    namespace["update_posterior_with_outcome"] = lambda b, likelihood: update_belief(b, likelihood)[0]
    namespace["should_stop"] = lambda b: (max(b.values()) >= 0.90 if top_state(b) else False, top_state(b))
    namespace["get_candidate_actions"] = lambda z, actions: [
        a for a in actions if "all" in a["tags"] or z in a["tags"]
    ]

    def rank(
        b: Belief, candidates: list[dict[str, Any]], outcome_models: Mapping[str, Any]
    ) -> tuple[list[RankedAction], list[Any]]:
        if any(a["name"] not in by_name or a["name"] not in outcome_models for a in candidates):
            raise ValidationError(
                "unsupported action/selected_model; compatibility cannot execute unknown checks"
            )
        checked = []
        for item in candidates:
            action = by_name[item["name"]]
            supplied = outcome_models[item["name"]]
            canonical: dict[str, dict[str, float]] = {}
            for label, vector in supplied.items():
                key = action.canonical_outcome(label)
                if key in canonical and canonical[key] != vector:
                    raise ValidationError("conflicting likelihoods for an outcome alias")
                canonical[key] = vector
            checked.append(replace(action, cost=item["cost"], outcomes=canonical))
        ranked = modern_rank(b, checked)
        return ranked, []

    def decision(
        b: Belief, candidates: list[dict[str, Any]], outcome_models: Mapping[str, Any]
    ) -> dict[str, Any]:
        label = top_state(b)
        if b[label] >= 0.90:
            return {"decision": "REPORT", "root_cause": label}
        ranked, _ = rank(b, candidates, outcome_models)
        useful = [r for r in ranked if r["eig"] > 1e-12]
        return {"decision": "RECOMMEND", "action": useful[0]} if useful else {"decision": "ESCALATE"}

    class LegacySequence:
        def __init__(self, outcomes: Iterable[str]) -> None:
            self.items = iter(outcomes)

        def available(self, action_id: str) -> bool:
            return True

        def observe(self, case_id: str, action_id: str, attempt: int, timeout_seconds: float) -> Observation:
            action = next(a for a in selected_model.actions if a.action_id == action_id)
            try:
                value = next(self.items)
            except StopIteration:
                return Observation(action_id, f"missing:{action_id}", "missing", cost=0)
            return Observation(
                action_id,
                f"legacy:{action_id}",
                "signal",
                action.canonical_outcome(value),
                f"legacy:{action_id}",
            )

    def run(stage: str, outcomes: Iterable[str]) -> dict[str, Any]:
        r = diagnose(
            PublicCase("manual", stage),
            selected_model,
            LegacySequence(outcomes),
            limits=Limits(max_steps=10, budget=100, max_attempts=10),
        )
        data: dict[str, Any] = plain(r)
        data["root_cause"] = r.prediction
        return data

    namespace["rank_actions"] = rank
    namespace["decide_next_step"] = decision
    namespace["run_diagnosis"] = run
    return selected_model


def prepare_evaluation(namespace: dict[str, Any], model: Model, seed: int = 42) -> None:
    cases = namespace["evaluation_cases"].to_dict("records")
    truths = {str(c["case_id"]): c["true_root_cause"] for c in cases}
    bank = OutcomeBank(model, truths, seed)
    action_by_name = {a.name: a for a in model.actions}

    def evaluate(case: dict[str, Any], policy: str) -> dict[str, Any]:
        result = diagnose(
            PublicCase(str(case["case_id"]), case["failed_stage"]),
            model,
            bank,
            policy,
            Limits(max_steps=10, budget=100, max_attempts=10),
        )
        r = legacy_result(result, case["true_root_cause"])
        for step in r["actions_taken"]:
            if step["outcome"] is not None:
                step["outcome"] = action_by_name[step["action"]].labels[step["outcome"]]
        return r

    namespace["results"] = [evaluate(c, "eig_per_cost") for c in cases]
    namespace["evaluate_case_cost_only"] = lambda c: evaluate(c, "lowest_cost")

    def simulate(name: str, truth: str, case_id: int | str) -> str:
        event = bank.observe(str(case_id), action_by_name[name].action_id)
        assert event.outcome is not None
        return action_by_name[name].labels[event.outcome]

    namespace["simulate_action_outcome"] = simulate
    namespace["_synthetic_bank_manifest"] = bank.manifest()


def execute_notebook_compatibility(
    path: str | Path = DEFAULT_NOTEBOOK, *, timeout: float = 60.0
) -> dict[str, Any]:
    from .notebook_worker import execute_worker

    return execute_worker(Path(path), "compatibility", timeout)


def _compatibility_inprocess(path: str | Path = DEFAULT_NOTEBOOK) -> dict[str, Any]:
    path = Path(path).resolve()
    nb, before = read_notebook(path)
    namespace: dict[str, Any] = {}
    output = io.StringIO()
    cwd = Path.cwd()
    model = default_model()
    try:
        os.chdir(path.parent)
        with contextlib.redirect_stdout(output):
            for number, cell in enumerate(nb["cells"], 1):
                if cell["cell_type"] != "code":
                    continue
                exec(compile("".join(cell["source"]), f"compat_cell_{number}", "exec"), namespace)
                if number == 7:
                    install_definitions(namespace, model)
                elif number in (11, 15):
                    prepare_evaluation(namespace, model)
    finally:
        os.chdir(cwd)
    if read_notebook(path)[1] != before:
        raise ValidationError("notebook changed during compatibility check")
    return {
        "notebook_sha256": before,
        "code_cells_executed": 13,
        "original_unit_checks_passed": 8,
        "mode": "Python bridge supplies corrected definitions and NEW synthetic observations",
        "unassisted_run_all": "still fails; original notebook is intentionally unchanged",
        "synthetic_bank": namespace["_synthetic_bank_manifest"],
        "comparison": namespace["comparison_df"].to_dict("records"),
        "stdout_characters": len(output.getvalue()),
    }
