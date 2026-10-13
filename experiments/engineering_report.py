"""Traceable engineering audit and plan, established before source fixes.

Audit baseline: Git 02e7d04, Python package 1.0.0, 69 passing unittest tests.
Notebook and workbook digest checks passed. Baseline instrumented benchmark:
335 terminal records, 6.4131279 seconds, 3,550,898 peak traced bytes. Model
hashing occupied 1.636 cumulative profiler seconds; profiling adds overhead.

Run this report after validation: python -B experiments/engineering_report.py.
Configuration is non-executable TOML; all implementation and tests are Python.
The historical notebook and version-1 result artifact remain unchanged.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BASELINE_COMMIT = "02e7d04"
BASELINE_TESTS = 69
BASELINE_NOTEBOOK_SHA256 = "3e8dc01a20397bbd1d7a9f52002bf6eef35c2703bc96e9b7085117303f77c00f"
BASELINE_RESULT_SHA256 = "af6403e77b50426be6bcb5c779bd43d337c4e3f668f27bdd0be3e664d1b795c6"

CURRENT_ARCHITECTURE = r"""flowchart TD
    CLI["Python CLI/evaluation"] --> DATA["Workbook validation and seven-stage parser"]
    DATA --> SPLIT["Repository split; training-only priors/stages"]
    SPLIT --> MODEL["Immutable Model/Action; normalized assumptions"]
    RAW["Original diagnostic likelihoods and costs: assumptions"] --> MODEL
    MODEL --> RUN["Runner: policy, resources, observations and stopping"]
    TRUTH["Harness-only labels"] --> BANK["Keyed synthetic OutcomeBank"] --> RUN
    RUN --> POLICY["EIG/cost or lowest-cost; forced baselines"]
    POLICY --> MATH["Log-space Bayes; entropy/EIG"] --> RUN
    RUN --> RECORD["Terminal and action traces"]
    RECORD --> MUT["Weakness: nested records mutable"]
    RUN --> PRIV["Weakness: raw error text and admission ordering"]
    BANK --> SIM["Weakness: mutable configuration/duplicate faults"]
    RECORD --> METRIC["Coverage, probability, calibration, effort/loss metrics"]
    METRIC --> SEM["Weakness: incomplete semantic checks"]
    METRIC --> WRITE["Compressed Python result artifact"]
    WRITE --> IO["Weakness: direct writes and executable loading"]
    NB["Unchanged notebook"] --> COMPAT["In-process exec/closures"]
    COMPAT --> GLOBAL["Weakness: cwd/stdout global; content unpinned"]
    NB --> HIST["Historical replay and original-policy reference"] --> METRIC
    TEST["69 unit tests; no configured lint/type tools"] -.-> RUN
    classDef weak fill:#ffe1e1,stroke:#bd3030;
    class MUT,PRIV,SIM,SEM,IO,GLOBAL weak;
"""

CURRENT_WORKFLOW = r"""flowchart TD
    IN["PublicCase, model, limits, provider"] --> INIT["Stage-conditioned initial belief"]
    INIT --> SCOPE{"Supported scope/evidence?"}
    SCOPE -->|no| REFER["Referral"]
    SCOPE -->|yes| BASE{"Forced baseline?"}
    BASE -->|yes| FORCE["Report, bypassing calibration gate"]
    BASE -->|no| TIME{"Deadline expired?"}
    TIME -->|yes| REFER
    TIME -->|no| CONF{"Confidence reaches threshold?"}
    CONF -->|yes| CAL{"Uncalibrated reporting allowed?"}
    CAL -->|no| REFER
    CAL -->|yes| REPORT["Report MAP cause"]
    CONF -->|no| LIMIT["Step/attempt limits"]
    LIMIT --> AVAIL["Provider availability BEFORE local permission checks"]
    AVAIL --> FILTER["Filter actions; rank EIG/cost or cost"]
    FILTER --> NEXT{"Informative feasible check?"}
    NEXT -->|no| REFER
    NEXT -->|yes| OBS["Observe, even if remaining time becomes zero"]
    OBS --> EVENT{"Valid event?"}
    EVENT -->|no| ERR["Raw exception text; overrun charged as reserved cost"] --> REFER
    EVENT -->|yes| KIND{"Signal/failure/duplicate?"}
    KIND -->|signal| BAYES["Bayes; zero support refers"]
    KIND -->|failure/duplicate| SAME["Belief unchanged; bounded retry/retire"]
    BAYES --> LEDGER["Append trace and cost"]
    SAME --> LEDGER
    LEDGER --> TIME
    REPORT --> OUT["Mutable nested terminal record"]
    FORCE --> OUT
    REFER --> OUT
    classDef weak fill:#ffe1e1,stroke:#bd3030;
    class FORCE,AVAIL,OBS,ERR,OUT weak;
"""

TARGET_ARCHITECTURE = r"""flowchart TD
    CFG["Typed/versioned configuration and immutable domain"] --> MODEL["Validated cached model identity"]
    MODEL --> RUN["Typed provider protocol; shared runner"]
    RUN --> LOCAL["Scope, permissions, stage and resource guards FIRST"]
    LOCAL --> DEAD["Recheck deadline before provider request"]
    DEAD --> EVENT["Validated events; reported costs/overruns retained"]
    EVENT --> BAYES["Stable Bayes; provenance/conflict checks"]
    BAYES --> STOP["Explicit reporting/referral; benchmark baseline opt-in"]
    LOSS["Declared loss model"] --> RISK["Hand-verified risk reduction; experimental comparator"] --> STOP
    STOP --> TRACE["Immutable trace; sanitized structured logging"]
    TRACE --> SEM["Semantic validation plus checksum"]
    SEM --> STORE["Atomic Python artifact; bounded data-only reader"]
    STORE --> EVAL["Paired evaluation and sensitivity with uncertainty"]
    NB["Pinned unchanged notebook"] --> CHILD["Isolated bounded subprocess"] --> EVAL
    TOOLS["Pinned tools; dependency constraints; test/lint/type gates"] -.-> RUN
    TOOLS -.-> STORE
    BENCH["Same-workload benchmark; measured time/memory"] -.-> EVAL
"""

IMPLEMENTATION_GATES = r"""flowchart TD
    AUDIT["Baseline, register, diagrams and plan"] --> DOMAIN["T01 contracts/immutability"]
    DOMAIN --> G1{"Mathematical/schema tests pass?"}
    G1 -->|no| DOMAIN
    G1 -->|yes| RUN["T02 admission/privacy/cost handling"]
    RUN --> G2{"Failure/state-transition regressions pass?"}
    G2 -->|no| RUN
    G2 -->|yes| IO["T03 persistence; T04 compatibility/simulator"]
    IO --> G3{"Corruption/security/compatibility tests pass?"}
    G3 -->|no| IO
    G3 -->|yes| SCIENCE["T05 loss/policies; T06 evaluation/logging"]
    SCIENCE --> QUALITY["T07 tests, lint, format, types and benchmark"]
    QUALITY --> REPEAT{"Complete regression and deterministic repeat?"}
    REPEAT -->|no| FIX["Resolve measured failures"] --> QUALITY
    REPEAT -->|yes| REPORT["T08 evidence-based release assessment"]
    REPORT --> LIMIT["Research release only until empirical calibration,<br/>real traces and operational adapters are demonstrated"]
"""

# Each tuple: ID, severity, classification, baseline location, observed/repro,
# impact, correction, verification. Locations refer to the baseline commit.
FLAWS = (
    (
        "P001",
        "High",
        "defect",
        "runner.py:98 diagnose",
        "An empty permission set still calls provider.available for a0/a1",
        "Provider work occurs outside admission",
        "Local guards before availability",
        "Forbidden actions produce zero provider calls",
    ),
    (
        "P002",
        "Medium",
        "defect",
        "runner.py:129 diagnose",
        "Availability consumes deadline; observe is still called with zero remaining time",
        "Unnecessary late work/cost",
        "Deadline gate before observe",
        "Fake-clock late admission makes no observe call",
    ),
    (
        "P003",
        "High",
        "defect",
        "runner.py:138 diagnose; records.py Observation.detail",
        "Synthetic token/password in exception survives in trace",
        "Sensitive text retention",
        "Sanitized structured error context",
        "Secret canaries absent from records and logs",
    ),
    (
        "P004",
        "High",
        "defect",
        "records.py:82/103 ActionRecord/Diagnosis",
        "r.final_belief['Code']=.123 succeeds on frozen dataclass",
        "Trace/model claims can be mutated before scoring",
        "Deep immutable snapshots",
        "Nested mutation fails; serialization/replay passes",
    ),
    (
        "P005",
        "High",
        "defect",
        "runner.py:138 diagnose; records.py Observation.validate",
        "Provider reports cost=100; terminal cost becomes 1",
        "Overrun/measurement facts disappear",
        "Preserve reported cost and explicit overrun basis",
        "Overrun visible; no further action; no false budget guarantee",
    ),
    (
        "P006",
        "High",
        "defect",
        "metrics.py:39 calculate_metrics",
        "Rehashing a record with total_decision_cost=0 bypasses cost consistency",
        "Scientifically misleading summaries",
        "Semantic and trace-cost validation",
        "Rehashed inconsistent cost/decision records rejected",
    ),
    (
        "P007",
        "High",
        "defect",
        "evaluation.py:205 write_python_artifact",
        "Direct target write; any existing .py target accepted",
        "Partial artifacts/source overwrite possible",
        "Atomic writer and collision protection",
        "Fault injection leaves original bytes; source overwrite refused",
    ),
    (
        "P008",
        "High",
        "integration weakness",
        "legacy.py:47; compatibility.py:141",
        "User-supplied notebook path executes without trusted digest check",
        "Execution boundary insufficient",
        "Pinned content before executing cells",
        "Altered notebook refused before code execution",
    ),
    (
        "P009",
        "Medium",
        "defect",
        "compatibility.py:149/160 execute_notebook_compatibility",
        "os.chdir and stdout capture affect entire process",
        "Concurrent I/O/logging race",
        "Bounded isolated compatibility worker",
        "Parent cwd/stdout unchanged; worker timeout tested",
    ),
    (
        "P010",
        "Medium",
        "defect",
        "simulation.py:48/69 OutcomeBank",
        "Duplicate ('Code','Code') and mutable seed accepted",
        "Scenario distribution/manifest can drift",
        "Immutable configuration and strict cause/attempt/seed contracts",
        "Malformed scenarios rejected; original keyed outcomes retained",
    ),
    (
        "P011",
        "Medium",
        "engineering gap",
        "package signatures and project metadata",
        "No typed provider interface or configured dependency/lint/type gate",
        "Maintenance and environment failures unmeasured",
        "Typed boundaries and pyproject quality configuration",
        "Actual pytest/Ruff/mypy checks recorded",
    ),
    (
        "P012",
        "Medium",
        "measured performance issue",
        "model.py:96 Model.model_hash; legacy.py:112",
        "337 model hashes use 1.636 profiler seconds; repeated source loading",
        "Avoidable CPU under intended workload",
        "Cache identity on immutable model; reuse trusted reference runner",
        "Same-workload measured benchmark; unchanged policy outputs",
    ),
    (
        "P013",
        "Medium",
        "defect",
        "records.py:18 plain",
        "Mapping keys 1 and '1' collapse after str conversion",
        "Ambiguous hashes/configuration",
        "Reject non-string serialization keys",
        "Collision/type cases fail explicitly",
    ),
    (
        "P014",
        "Medium",
        "defect",
        "records.py:51 Observation; model.py:32 Action",
        "Detail/label schema can admit arbitrary non-serializable objects",
        "Unexpected errors outside validated boundary",
        "Complete bounded string/value validation",
        "Invalid detail/status/label cases receive explicit validation errors",
    ),
    (
        "P015",
        "High",
        "integration weakness",
        "evaluation.py artifact module; implementation_report.py result import",
        "Result access executes Python and decompresses without bounds",
        "Unsafe for untrusted/corrupt result files",
        "AST data-only reader with size/checksum bounds",
        "No code execution; malformed/truncated/oversized payload rejected",
    ),
    (
        "P016",
        "High",
        "design limitation",
        "runner.py:74 forced baselines",
        "fixed_test reports with confidence 1 despite allow_uncalibrated=False",
        "Benchmark output can be confused with guarded diagnosis",
        "Explicit benchmark opt-in separate from ordinary requests",
        "Baseline refused unless benchmark purpose explicitly enabled",
    ),
    (
        "L001",
        "High",
        "assumption",
        "parameters.py; model.py provenance",
        "Action likelihoods and costs are not measured diagnostic traces",
        "Production validity not established",
        "Preserve assumptions and test misspecification; acquire real traces later",
        "Never label synthetic scores empirical",
    ),
    (
        "L002",
        "High",
        "limitation",
        "runner.py confidence gate",
        "0.90 is not empirically calibrated",
        "High-confidence wrong reports remain possible",
        "Retain calibration refusal; external validation required",
        "Calibration requirement marked incomplete for production",
    ),
    (
        "L003",
        "High",
        "limitation",
        "model.py STATES; data.py mapping",
        "Single categorical cause; 66 rows excluded",
        "Unknown/multiple-fault scope restricted",
        "Explicit scope and human referral",
        "Unsupported scope tests and disclosures",
    ),
    (
        "L004",
        "High",
        "limitation",
        "domain provider protocol",
        "Arbitrary external providers remain cooperative",
        "No proven hard cancellation/live adapter",
        "Bound built-ins; isolate notebook; deployment remains incomplete",
        "Do not claim live-CI readiness",
    ),
    (
        "L005",
        "Medium",
        "limitation",
        "evaluation.py grouped experiment",
        "One repository split and three seeds; no real action outcomes",
        "Limited statistical generalization",
        "Paired uncertainty and sensitivity, larger external study later",
        "Denominators and conditional uncertainty retained",
    ),
)

PLAN = (
    {
        "id": "T01",
        "priority": "P0",
        "issues": ["P004", "P010", "P011", "P013", "P014"],
        "objective": "Typed immutable domain and explicit validation",
        "files": ["domain.py", "records.py", "model.py", "probability.py", "simulation.py"],
        "interfaces": "Typed provider; immutable beliefs/traces; validated JSON boundary",
        "dependencies": [],
        "acceptance": "No nested mutation; invalid schemas fail clearly",
        "tests": "Math, schema, serialization, scenario contracts",
        "risks": "Stricter formerly permissive inputs; record schema version changes",
        "verification": "Independent fixtures and static checks",
        "status": "planned",
    },
    {
        "id": "T02",
        "priority": "P0",
        "issues": ["P001", "P002", "P003", "P005", "P016"],
        "objective": "Safe admission, error handling, cost facts and baseline purpose",
        "files": ["runner.py", "observability.py"],
        "interfaces": "Provider calls after guards; bounded sanitized events; explicit overrun reasons",
        "dependencies": ["T01"],
        "acceptance": "Zero forbidden/late calls; no secret canaries; overruns retained",
        "tests": "Fake-clock, provider failure, cost and baseline regressions",
        "risks": "Justified stricter benchmark/cost behavior",
        "verification": "State-transition tests and ledger reconciliation",
        "status": "planned",
    },
    {
        "id": "T03",
        "priority": "P0",
        "issues": ["P006", "P007", "P015"],
        "objective": "Semantic records and atomic safe persistence",
        "files": ["metrics.py", "artifacts.py", "evaluation.py"],
        "interfaces": "Data-only bounded artifact loader; atomic writer; validated scored records",
        "dependencies": ["T01", "T02"],
        "acceptance": "Corruption and semantic inconsistencies rejected; source files protected",
        "tests": "Fault injection, atomicity, payload/checksum/size and cost tests",
        "risks": "Previously accepted malformed records no longer load",
        "verification": "Roundtrip/replay and negative test corpus",
        "status": "planned",
    },
    {
        "id": "T04",
        "priority": "P1",
        "issues": ["P008", "P009", "P010", "P012"],
        "objective": "Isolated compatibility and immutable deterministic environment",
        "files": ["legacy.py", "compatibility.py", "notebook_worker.py", "simulation.py"],
        "interfaces": "Pinned source worker; parent-process isolation; reusable reference runner",
        "dependencies": ["T01"],
        "acceptance": "Original notebook unchanged; no parent cwd/stdout changes",
        "tests": "Trusted digest, process timeout and repeated outcome tests",
        "risks": "Alternate untrusted notebooks deliberately unsupported",
        "verification": "All 13 cells and original eight checks in isolated worker",
        "status": "planned",
    },
    {
        "id": "T05",
        "priority": "P1",
        "issues": ["P016", "L001", "L002"],
        "objective": "Explicit declared decision costs and optional experimental risk comparison",
        "files": ["decision_cost.py", "policy.py", "evaluation.py"],
        "interfaces": "Loss matrix/report risk/expected reduction with impossible-branch handling",
        "dependencies": ["T01", "T02"],
        "acceptance": "Hand calculations pass; no uncalibrated production claim",
        "tests": "Independent symmetric/asymmetric risk fixtures and continuation cases",
        "risks": "A greedy positive risk score is not net utility or optimal planning",
        "verification": "Common-bank comparisons; preserve EIG default",
        "status": "planned",
    },
    {
        "id": "T06",
        "priority": "P1",
        "issues": ["P003", "P006", "L001", "L005"],
        "objective": "Structured observability and reproducible scientific evaluation",
        "files": ["observability.py", "evaluation.py", "tests"],
        "interfaces": "Sanitized JSON events; complete ledger; paired comparisons",
        "dependencies": ["T02", "T03", "T04", "T05"],
        "acceptance": "Case IDs, hashes, costs and metrics reconcile",
        "tests": "Unit/integration/end-to-end/regression and full repeated evaluation",
        "risks": "New record/implementation version changes artifact identity",
        "verification": "Two deterministic runs and source manifest checks",
        "status": "planned",
    },
    {
        "id": "T07",
        "priority": "P1",
        "issues": ["P011", "P012"],
        "objective": "Configured dependencies and measured engineering gates",
        "files": ["pyproject.toml", "quality.py", "benchmark.py"],
        "interfaces": "Pinned tools; constrained workbook dependencies; explicit pass/fail gates",
        "dependencies": ["T01", "T02", "T03", "T04", "T05", "T06"],
        "acceptance": "Test/lint/format/type results actually obtained; benchmark bounded",
        "tests": "Quality command/configuration and intended-workload benchmark",
        "risks": "Tool/environment availability; timing is host-dependent",
        "verification": "Recorded tool versions, exit codes, workloads and memory",
        "status": "planned",
    },
    {
        "id": "T08",
        "priority": "P1",
        "issues": ["L001", "L002", "L003", "L004", "L005"],
        "objective": "Evidence-based release assessment and full change log",
        "files": ["engineering_report.py", "README.md"],
        "interfaces": "Issue/task status and artifact-backed results",
        "dependencies": ["T01", "T02", "T03", "T04", "T05", "T06", "T07"],
        "acceptance": "Unproven requirements marked incomplete",
        "tests": "Report generation and artifact/source consistency",
        "risks": "Engineering checks cannot establish empirical deployment validity",
        "verification": "Final reviewed readiness matrix",
        "status": "planned",
    },
)


CHANGELOG = {
    "ci_diagnosis/__init__.py": "modified: engineering version 1.1.0",
    "ci_diagnosis/domain.py": "created: vocabulary, typed provider protocol and ranking contracts",
    "ci_diagnosis/records.py": "modified: bounded schema, immutable snapshots and record schema 2",
    "ci_diagnosis/model.py": "modified: complete validation, cached immutable identity and stable smoothing",
    "ci_diagnosis/probability.py": "modified: typed numerical contracts and explicit oversized-integer failure",
    "ci_diagnosis/policy.py": "modified: existing policies retained; experimental risk/cost comparator",
    "ci_diagnosis/decision_cost.py": "created: immutable declared losses and verified expected risk calculations",
    "ci_diagnosis/runner.py": "modified: permission/deadline ordering, explicit baseline purpose, overruns and provenance conflicts",
    "ci_diagnosis/observability.py": "created: sanitized structured event logging",
    "ci_diagnosis/simulation.py": "modified: immutable scenario configuration, valid distinct causes and keyed-draw-preserving optimization",
    "ci_diagnosis/data.py": "modified: bounded immutable workbook-byte intake, typed rows and source identity",
    "ci_diagnosis/artifacts.py": "created: atomic publication and bounded data-only artifact reader",
    "ci_diagnosis/metrics.py": "modified: semantic ledger/cost checks, explicit error rate and numerically stable summaries",
    "ci_diagnosis/legacy.py": "modified: typed bounded inspection and reusable pinned original-policy reference",
    "ci_diagnosis/compatibility.py": "modified: typed legacy closures; parent-safe subprocess entry",
    "ci_diagnosis/notebook_worker.py": "created: pinned, bounded child-process notebook checks",
    "ci_diagnosis/parameters.py": "modified: typing/formatting only; literal probabilities and costs unchanged",
    "ci_diagnosis/evaluation.py": "modified: benchmark-only baseline opt-in, experimental comparator, new schema/manifests and safe publication",
    "ci_diagnosis/benchmark.py": "created: fixed 335-record instrumented workload and predeclared regression gates",
    "ci_diagnosis/quality.py": "created: environment, pytest, lint, format, strict type and benchmark gates",
    "tests/helpers.py": "modified: independent fixtures now have coherent cost traces",
    "tests/test_artifacts.py": "modified: schema-2 artifact roundtrip and invalid-value tests",
    "tests/test_runner.py": "modified: explicit overrun accounting regression",
    "tests/test_probability.py": "modified: consistent formatting; independent mathematical cases preserved",
    "tests/test_data_metrics.py": "modified: formatting and semantic-record-compatible fixtures",
    "tests/test_simulation_compatibility.py": "modified: formatting; original regression cases retained",
    "tests/test_engineering.py": "created: admission, privacy, immutability, numerical, risk and process regressions",
    "tests/test_persistence.py": "created: real atomicity, corruption, overwrite-protection and non-executing-read tests",
    "experiments/agent_simulation.py": "modified: formatting; Python CLI remains the entry point",
    "experiments/implementation_report.py": "modified: previous release results loaded as data instead of executed Python",
    "experiments/engineering_report.py": "created: four diagrams, flaw register, plan, results and readiness assessment",
    "experiments/engineering_quality_results.py": "created: actual engineering gate and benchmark evidence",
    "experiments/engineering_evaluation_results.py": "created: complete version-1.1 experimental ledger; previous result artifact preserved",
    "pyproject.toml": "created: non-executable package/dependency/test/lint/type configuration",
    ".gitignore": "created: generated caches/build metadata exclusions",
    "README.md": "modified: current commands, justified interface changes and explicit research scope",
}


def _load(name: str) -> dict[str, Any]:
    from ci_diagnosis.artifacts import read_python_artifact

    path = Path(__file__).with_name(name)
    return read_python_artifact(path) if path.exists() else {}


def _current(hashes: dict[str, str]) -> bool:
    return bool(hashes) and all(
        (ROOT / path).is_file() and hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == expected
        for path, expected in hashes.items()
    )


def main() -> int:
    quality = _load("engineering_quality_results.py")
    experiment = _load("engineering_evaluation_results.py")
    config_hash = hashlib.sha256((ROOT / "pyproject.toml").read_bytes()).hexdigest()
    quality_current = (
        quality.get("passed", False)
        and _current(quality.get("source_hashes", {}))
        and quality.get("configuration_hash") == config_hash
    )
    experiment_current = (
        _current(experiment.get("source_code_hashes", {}))
        and experiment.get("configuration_hash") == config_hash
    )
    for title, diagram in (
        ("1. Current architecture at audit baseline", CURRENT_ARCHITECTURE),
        ("2. Current decision cycle at audit baseline", CURRENT_WORKFLOW),
    ):
        print(f"# {title}\n\n```mermaid\n{diagram}```\n")
    print("# 3. Prioritized flaw register\n")
    print("Exact baseline locations refer to Git", BASELINE_COMMIT, ". No Critical defect was established.")
    names = (
        "id",
        "severity",
        "classification",
        "baseline_location",
        "observed_behavior_and_reproduction",
        "impact",
        "correction",
        "verification",
    )
    register = []
    for item in FLAWS:
        row = dict(zip(names, item, strict=False))
        row["status"] = (
            "verified correction"
            if item[0].startswith("P") and quality_current
            else "incomplete/unverified"
            if item[0].startswith("L")
            else "implemented; validation stale/incomplete"
        )
        register.append(row)
    print(json.dumps(register, indent=2))
    for title, diagram in (
        ("4. Proposed target architecture", TARGET_ARCHITECTURE),
        ("5. Implementation and validation gates", IMPLEMENTATION_GATES),
    ):
        print(f"\n# {title}\n\n```mermaid\n{diagram}```\n")
    print("# 6. Traceable implementation plan\n")
    plan = [
        {
            **task,
            "status": "complete for research-simulation engineering"
            if quality_current and experiment_current
            else "implemented; evidence incomplete/stale",
        }
        for task in PLAN
    ]
    print(json.dumps(plan, indent=2))
    print("\n# 7. Source, tests and actual engineering results\n")
    print("Quality evidence current:", quality_current, ". Experiment evidence current:", experiment_current)
    for gate in quality.get("gates", []):
        print(gate["gate"], "PASS" if gate["passed"] else "FAIL", gate.get("stdout", ""))
    print("Instrumented benchmark:", json.dumps(quality.get("benchmark", {}), indent=2))
    print("\n# 8. Preserved artifacts\n")
    for filename, expected in (
        ("experiments/agent_simulation.ipynb", BASELINE_NOTEBOOK_SHA256),
        ("experiments/evaluation_results.py", BASELINE_RESULT_SHA256),
        (
            "data/replication-labeling.xlsx",
            "39647c82583a2039b69fcf57fa30808d46f9bbf3cbcf6caf023921c2588de860",
        ),
    ):
        print(
            filename,
            "UNCHANGED"
            if hashlib.sha256((ROOT / filename).read_bytes()).hexdigest() == expected
            else "MISMATCH",
        )
    print("\n# 9. Actual evaluation and comparisons\n")
    if experiment:
        print("Source split:", {k: v["case_count"] for k, v in experiment["split"].items()})
        print(
            "Historical saved traces are reconciliation only. Controlled comparisons use a NEW shared synthetic bank."
        )
        print("| Control policy | Correct auto rate | Coverage | Selective accuracy | Mean diagnostic cost |")
        print("|---|---:|---:|---:|---:|")
        for policy, m in experiment["controlled_legacy_comparison"]["metrics"].items():
            print(
                f"| {policy} | {m['correct_auto_rate']:.2%} | {m['coverage']:.2%} | {m['selective_accuracy']:.2%} | {m['average_diagnostic_cost']:.4f} |"
            )
        print(
            "\n| Synthetic scenario | Policy | Coverage pooled over seeds | Selective accuracy | Mean decision cost |"
        )
        print("|---|---|---:|---:|---:|")
        for scenario in sorted({r["scenario"]["name"] for r in experiment["test_synthetic"]}):
            runs = [r for r in experiment["test_synthetic"] if r["scenario"]["name"] == scenario]
            for policy in runs[0]["metrics"]:
                ms = [r["metrics"][policy] for r in runs]
                n = sum(m["count"] for m in ms)
                reports = sum(m["reports"] for m in ms)
                correct = sum(m["correct_reports"] for m in ms)
                selected = "undefined" if not reports else f"{correct / reports:.2%}"
                cost = sum(m["average_total_decision_cost"] * m["count"] for m in ms) / n
                print(f"| {scenario} | {policy} | {reports / n:.2%} | {selected} | {cost:.4f} |")
        print(
            "Repeated seeds reuse the same cases, not additional independent repositories. Clustered intervals are conditional on the declared simulator."
        )
        print(
            "Per-class, Brier/log-loss, calibration, cost, reason-code and sensitivity records are complete in the data artifact."
        )
    print("\n# 10. File-by-file change log\n")
    for path, change in CHANGELOG.items():
        print(f"- [{path}](<{(ROOT / path).as_posix()}>): {change}")
    print("\n# 11. Remaining risks and outstanding work\n")
    for issue in FLAWS:
        if issue[0].startswith("L"):
            print("-", issue[0], issue[4], "Required:", issue[6])
    print(
        "- Credential-pattern redaction is verified; real log privacy, access, retention and authenticity policies remain unvalidated."
    )
    print("- Risk/cost is a greedy experimental comparator, not net utility or a proof of optimal planning.")
    print(
        "- No additional notebook was created. Unassisted original notebook execution retains its historical failures; compatibility is explicitly assisted."
    )
    print("\n# 12. Evidence-based readiness assessment\n")
    print(
        "Research-simulation engineering:",
        "gates passed with current evidence"
        if quality_current and experiment_current
        else "incomplete/stale evidence",
    )
    print(
        "Production/live-CI deployment: INCOMPLETE. Real diagnostic likelihoods/costs, empirical calibration, independent operational evaluation, human outcomes and validated adapters are required."
    )
    return 0 if quality_current and experiment_current else 1


if __name__ == "__main__":
    raise SystemExit(main())
