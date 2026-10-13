"""Implementation documentation, diagrams, change log and actual-result summaries.

Run ``python -B experiments/implementation_report.py`` to print the report.
This file contains documentation only; all executable implementation is in
ci_diagnosis/*.py. The original notebook and other project artifacts are intact.

Reproduction (from the project root, Python >=3.10):
    python -B -m unittest discover -s tests -v
    python -B experiments/agent_simulation.py --output experiments/evaluation_results.py

Workbook dependencies: pandas and openpyxl. Core and unit tests use standard
unittest; workbook-dependent tests explicitly skip if dependencies are absent.
Every experiment records exact interpreter/package versions and source hashes.
The tested bundled runtime was Python 3.12.14 / pandas 3.0.1 / openpyxl 3.1.5.

Notebook compatibility is read-only and assisted by Python closures. It does not
make unassisted Run All work: preserving the notebook necessarily preserves its
undefined results/simulator cells. execute_notebook_compatibility executes all
13 code cells in memory with corrected definitions/new synthetic observations.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

ORIGINAL_ARCHITECTURE = r'''flowchart TD
    A["Original notebook: sequential cell execution"] --> B["Four states, priors,<br/>seven-stage likelihoods; threshold 0.90"]
    B --> C["Ten actions: tags, relative costs,<br/>binary display labels"]
    C --> D["Bayes/entropy/EIG and cost policies"]
    D --> E["Eight original unit checks"]
    E --> F["Read workbook relative to experiments"]
    F --> G["Strip and map selected subcategories;<br/>exclude unmapped rows"]
    G --> H["test substring -> Test;<br/>otherwise -> Build"]
    H --> I["10 per cause; sample seed 42"]
    I --> J["Read global results"]
    J --> X["Missing EIG evaluation/results;<br/>NameError stops clean execution"]
    J -. "external kernel state only" .-> K["Print trace; replace global likelihoods<br/>with one diagnostic vector"]
    K --> L["Cost-only initialization"]
    L --> Y["Stage lookup KeyError"]
    L -. "if stage table restored" .-> M["simulate_action_outcome(action, truth, case)"]
    M --> Z["Undefined simulator"]
    I -. "later cells if failures bypassed" .-> N["Fixed Test baseline"]
    N --> O["Correct reports/all cases; selective precision;<br/>macro precision/recall; referrals; cost/actions"]
    O --> P["Positional zip comparisons;<br/>console/DataFrame/saved notebook outputs"]
    Q["Manual run_diagnosis(stage, strings)"] --> R["Initial prior times stage likelihood;<br/>normalize; filter action tags"]
    R --> S{"Maximum belief >= 0.90?"}
    S -->|yes| T["REPORT argmax"]
    S -->|no| U{"Actions remain?"}
    U -->|no| V["ESCALATE marker"]
    U -->|yes| W["q(outcome) and hypothetical Bayes beliefs;<br/>entropy change expectation; EIG/cost;<br/>unknown-model fallback by cost"]
    W --> AA["Consume next plain string;<br/>remove action by name; outcome lookup"]
    AA --> AB["Multiply belief times likelihood;<br/>normalize"]
    AB --> AC{"More supplied outcomes?"}
    AC -->|yes| S
    AC -->|no| AD["Raw posterior returned;<br/>no final terminal check"]
    AA -. "unknown model / mismatched strings" .-> AE["Unhandled KeyError"]
    AB -. "zero evidence" .-> AF["Division error"]
    AG["Assumed priors/likelihoods/costs;<br/>single cause; independent binary checks"] -.-> B
    AG -.-> AB
    AH["Existing saved outputs;<br/>not a fresh-source execution"] -.-> P
    AI["Documented V2 only:<br/>risk policy, smoothing, richer stages,<br/>8/11 limits, paired bank, generated logs"] -.-> J
    classDef code fill:#e4f5e9,stroke:#278447;
    classDef assumed fill:#fff0cc,stroke:#b77b12;
    classDef broken fill:#ffe1e1,stroke:#bd3030;
    classDef docs fill:#eee5ff,stroke:#7951ad;
    class A,B,C,D,E,F,G,H,I,J,K,L,N,O,P,Q,R,S,T,U,V,W,AA,AB,AC,AD code;
    class AG,AH assumed;
    class X,Y,M,Z,AE,AF broken;
    class AI docs;
'''

IMPLEMENTED_ARCHITECTURE = r'''flowchart TD
    A["parameters.py: original literal assumptions"] --> B["model.py: explicit ratio-preserving normalization;<br/>immutable validated priors/stages/actions;<br/>canonical IDs, labels and aliases"]
    B --> C{"Valid distributions, costs and registry?"}
    C -->|no| D["ValidationError; no diagnosis"]
    C -->|yes| E["records.py PublicCase:<br/>stable ID and normalized stage;<br/>truth absent"]
    E --> F["probability.py initial belief;<br/>Unknown/Ambiguous neutral evidence;<br/>log-space Bayesian arithmetic"]
    F --> G{"Supported scope and stage evidence?"}
    G -->|no| H["ESCALATE with explicit reason"]
    G -->|yes| I{"Confidence threshold met?"}
    I -->|yes| J{"Uncalibrated simulation reports permitted?"}
    J -->|no| H
    J -->|yes| K["REPORT model-MAP category;<br/>probability explicitly uncalibrated"]
    I -->|no| L["runner.py resource guards:<br/>steps, attempts, budget and cooperative deadline"]
    L --> M["Action eligibility:<br/>unused, stage tags, permission,<br/>provider availability and affordability"]
    M --> N["policy.py: EIG/cost or lowest cost;<br/>stable catalogue ties;<br/>reject zero-information candidates"]
    N --> O{"Feasible informative candidate?"}
    O -->|no| H
    O -->|yes| P["Typed provider request:<br/>case/action/attempt and remaining deadline"]
    P --> Q{"Observation status and schema"}
    Q -->|"invalid/provider exception"| R["Charge reserved effort;<br/>record failure; refer safely"] --> H
    Q -->|"missing/inconclusive/error/timeout"| S["Belief unchanged;<br/>record incurred effort;<br/>bounded retry or retire action"]
    Q -->|signal| T["Validate action/outcome pairing;<br/>event/artifact provenance deduplication"]
    T --> U{"New evidence with model support?"}
    U -->|duplicate| S
    U -->|"zero observed support"| H
    U -->|yes| V["Log weights + stable normalization;<br/>record before/after belief and log q"]
    V --> W["Update cost and action state"]
    S --> W
    W --> I
    K --> X["Versioned records with configuration/model hashes;<br/>candidate rejections, terminal reason and checksum"]
    H --> X
    X --> Y["metrics.py: probability quality, coverage/referrals,<br/>class confusion, effort and declared terminal loss"]

    Z["data.py workbook schema, stable jobs and scope mapping"] --> AA["Repository-disjoint training/validation/test"]
    AA --> AB["Training-only Laplace prior/stage estimates;<br/>diagnostic probabilities still assumptions"] --> B
    AA --> AC["Harness-only labels"]
    AC --> AD["simulation.py: SHA-keyed paired outcome bank;<br/>matched/noisy/correlated/biased synthetic scenarios"] --> P
    AE["Unchanged original notebook"] --> AF["legacy.py historical replay;<br/>compatibility.py corrected in-memory closures"]
    AF --> AG["Controlled original-policy comparison;<br/>new generator clearly distinguished"]
    Y --> AH["evaluation.py repeated seeds, clustered intervals,<br/>sensitivity and fixed/stage/prior-MAP baselines"]
    AG --> AH
    AH --> AI["evaluation_results.py: complete compressed ledger;<br/>payload checksum and runtime/source manifests"]
    AJ["tests/*.py: independent arithmetic,<br/>failure/resource/provenance/reproducibility checks"] -.-> B
    AJ -.-> W
    AJ -.-> AI
'''

AUDIT_FINDINGS = (
    ("B01", "notebook cells 13/15", "Undefined results and simulator", "New Python evaluator/provider; original failures preserved as baseline"),
    ("B02", "cell 13; calculate_posterior", "Printing overwrites stage model", "Immutable model and closure-based compatibility definitions"),
    ("B03", "cells 5/7 action/outcome tables", "Nine catalogue/model outcome mismatches", "Canonical IDs plus validated legacy aliases"),
    ("B04", "run_diagnosis", "No stop check after final observation", "One bounded runner returns structured terminal decisions"),
    ("B05", "prior/stage/outcome tables", "Rounding yields non-unit distributions", "Versioned ratio-preserving normalization and provenance"),
    ("B06/B07", "calculate_eig/update_posterior/should_stop", "Zero division, invalid beliefs and NaNs", "Explicit zero-support handling, log updates and schema validation"),
    ("B08/B09", "rank_actions fallback/cost", "Unexecutable fallback and invalid costs", "Validated complete registry; availability/permissions; positive declared costs"),
    ("B10/B11", "calculate_metrics/final zip", "Undefined metrics and positional pairing", "Denominators/null statuses; stable-ID paired comparison"),
    ("L01", "normalize_stage", "Missing/skipped/ambiguous context coerced", "Conservative seven-stage grammar; neutral unknown evidence"),
    ("L02-L07", "model and stopping assumptions", "Uncalibrated threshold, independence, scope and greedy selection", "Disclosed assumptions, scope/calibration guards, evidence deduplication and sensitivity; empirical validation remains needed"),
    ("L08-L11", "runner/evaluation/tests", "Resource, reproducibility and trace gaps", "Limits, grouped splits, paired seeds, full ledgers and automated tests"),
    ("L12", "preprint versus checkout", "Published V2 artifacts unavailable", "New implementation/version labeled distinctly; no V2 reproduction claim"),
)

CHANGELOG = {
    "ci_diagnosis/__init__.py": "Package/version and dependency contract",
    "ci_diagnosis/parameters.py": "Exact original notebook parameter literals and provenance",
    "ci_diagnosis/probability.py": "Validation, stable normalization/Bayes, entropy and EIG",
    "ci_diagnosis/model.py": "Immutable registry, canonical IDs/aliases, normalized assumptions and training-only estimation",
    "ci_diagnosis/data.py": "Read-only workbook validation, stage grammar and repository splits",
    "ci_diagnosis/policy.py": "EIG/cost, lowest-cost ranking and baseline identifiers",
    "ci_diagnosis/records.py": "Public case, typed events and versioned terminal/action records",
    "ci_diagnosis/runner.py": "Shared bounded decisions, failure/referral and evidence deduplication",
    "ci_diagnosis/simulation.py": "Declared reproducible paired synthetic providers and manual replay",
    "ci_diagnosis/metrics.py": "Abstention/calibration/probability/effort/loss metrics, checksums and paired intervals",
    "ci_diagnosis/legacy.py": "Read-only baseline tests, saved-trace reconciliation and original-policy harness",
    "ci_diagnosis/compatibility.py": "In-memory notebook-style corrected definitions and assisted execution",
    "ci_diagnosis/evaluation.py": "Repeated held-out experiments, control comparisons, sensitivity and Python artifact export",
    "experiments/agent_simulation.py": "Python evaluation entry point next to the preserved notebook",
    "experiments/implementation_report.py": "This documentation, Mermaid diagrams and actual-result presentation",
    "experiments/evaluation_results.py": "Generated complete evaluation ledger; checksummed compressed payload",
    "tests/__init__.py": "Test package",
    "tests/helpers.py": "Independent small mathematical fixtures",
    "tests/test_probability.py": "Bayesian/EIG correctness, validation, numerical and model checks",
    "tests/test_runner.py": "Terminal decisions, failures, resource limits, provenance and scope",
    "tests/test_data_metrics.py": "Stage/split/estimator correctness and hand-counted metrics",
    "tests/test_simulation_compatibility.py": "Pairing/reproducibility, historical baseline and notebook compatibility",
    "tests/test_artifacts.py": "Python artifact serialization, special metric values and format validation",
}

REMAINING_LIMITATIONS = (
    "Diagnostic outcomes/costs are synthetic assumptions. Training rows estimate only prior/stage distributions.",
    "The stage grammar is heuristic and has no independently annotated stage-validation set.",
    "The 0.90 gate is not empirically calibrated. allow_uncalibrated=False refuses such sequential reports.",
    "Likelihood dependence is stressed and duplicate artifacts suppressed; a fitted dependence model is not supplied.",
    "Single categorical causes only; unknown/multiple simultaneous causes need new ground truth and representation.",
    "Original observation generator and published V2 records are absent, so historical performance cannot be regenerated.",
    "External provider deadlines are cooperative. Built-ins are local bounded lookups; no live CI tools are implemented.",
    "No human-review outcomes or real operational cost savings are established.",
    "Risk/cost and lookahead remain optional future experiments; no untested performance benefit is claimed.",
    "This is a tested advisory simulation, not a production-ready diagnosis system.",
)


def main():
    from ci_diagnosis.artifacts import read_python_artifact
    result=read_python_artifact(Path(__file__).with_name('evaluation_results.py'))
    print("# 1. Original architecture\n\n```mermaid\n"+ORIGINAL_ARCHITECTURE+"```\n")
    print("# 2. Audit findings\n")
    for code, location, issue, correction in AUDIT_FINDINGS:
        print(f"- {code}, {location}: {issue}. {correction}.")
    print("\n# 3. Implemented architecture\n\n```mermaid\n"+IMPLEMENTED_ARCHITECTURE+"```\n")
    print("# 4. Python implementation and tests\n")
    for path, purpose in CHANGELOG.items():
        print(f"- {path}: {purpose}")
    print("\n# 5. Preserved original notebook\n")
    print("SHA-256:",result["original_unit_checks"]["notebook_sha256"])
    print("Original checks:",result["original_unit_checks"]["passed"])
    print("Compatibility mode:",result["compatibility"]["mode"])
    print("Unassisted Run All:",result["compatibility"]["unassisted_run_all"])
    print("\n# 6. Actual baseline comparisons and evaluation\n")
    print("Historical saved outputs: reconciliation only; missing generator not reproduced.")
    print("Controlled comparison: identical NEW synthetic bank, same 40 balanced cases and original stage mapping.")
    print("| Policy | Correct auto rate | Coverage | Selective accuracy | Mean diagnostic cost |")
    print("|---|---:|---:|---:|---:|")
    for policy,m in result["controlled_legacy_comparison"]["metrics"].items():
        sel="undefined" if m["selective_accuracy"] is None else f'{m["selective_accuracy"]:.2%}'
        print(f'| {policy} | {m["correct_auto_rate"]:.2%} | {m["coverage"]:.2%} | {sel} | {m["average_diagnostic_cost"]:.4f} |')
    print("\nRepository-disjoint test cohort:",result["split"]["test"]["case_count"],"cases;",
          len({r["seed"] for r in result["test_synthetic"]}),"seeds;",
          len({r["scenario"]["name"] for r in result["test_synthetic"]}),"declared synthetic scenarios.")
    print("| Scenario | Policy | Pooled coverage | Pooled selective accuracy | Mean decision cost |")
    print("|---|---|---:|---:|---:|")
    scenarios=sorted({run["scenario"]["name"] for run in result["test_synthetic"]})
    for scenario in scenarios:
        runs=[run for run in result["test_synthetic"] if run["scenario"]["name"]==scenario]
        for policy in ("eig_per_cost","lowest_cost","fixed_test","stage_map","prior_map"):
            metrics=[r["metrics"][policy] for r in runs]
            total=sum(m["count"] for m in metrics);reports=sum(m["reports"] for m in metrics)
            correct=sum(m["correct_reports"] for m in metrics)
            selective=f"{correct/reports:.2%}" if reports else "undefined"
            cost=sum(m["average_total_decision_cost"]*m["count"] for m in metrics)/total
            print(f"| {scenario} | {policy} | {reports/total:.2%} | {selective} | {cost:.4f} |")
    print("\nPooled seeds reuse the same cases: they are not additional independent repositories.")
    print("Full per-class metrics, Brier/log loss, ECE, ledgers, conditional clustered intervals and sensitivity are in evaluation_results.py.")
    print("\n# 7. Remaining limitations\n")
    for line in REMAINING_LIMITATIONS:
        print("- "+line)
    print("\n# 8. Change log\n\nAll files listed in section 4 were created as .py files. No existing notebook, workbook or project artifact was modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

