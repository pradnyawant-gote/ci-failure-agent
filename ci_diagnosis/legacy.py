"""Read-only notebook inspection and historical trace reconciliation.

This code never writes or executes the original evaluation cells unassisted.
Replaying saved observations does not reconstruct the missing original simulator.
"""

from __future__ import annotations

import ast
import contextlib
import hashlib
import io
import json
import re
from pathlib import Path
from typing import Any

from .domain import ObservationProvider
from .model import STATES
from .parameters import RAW_ACTIONS, RAW_OUTCOMES, RAW_PRIORS, RAW_STAGE_LIKELIHOODS
from .probability import ValidationError, normalize, update_belief
from .records import RECORD_VERSION, ActionRecord, Diagnosis, fingerprint

NOTEBOOK_SHA256 = "3e8dc01a20397bbd1d7a9f52002bf6eef35c2703bc96e9b7085117303f77c00f"
DEFAULT_NOTEBOOK = Path(__file__).resolve().parents[1] / "experiments" / "agent_simulation.ipynb"


def read_notebook(path: str | Path = DEFAULT_NOTEBOOK) -> tuple[dict[str, Any], str]:
    path = Path(path)
    data = path.read_bytes()
    return json.loads(data.decode("utf-8")), hashlib.sha256(data).hexdigest()


def literal_parameters(path: str | Path = DEFAULT_NOTEBOOK) -> dict[str, Any]:
    nb, _ = read_notebook(path)
    wanted = {"priors", "likelihoods", "actions", "outcome_models"}
    found = {}
    for cell in nb["cells"]:
        if cell["cell_type"] != "code":
            continue
        for node in ast.parse("".join(cell["source"])).body:
            if (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
            ):
                name = node.targets[0].id
                if name in wanted:
                    found[name] = ast.literal_eval(node.value)
    if set(found) != wanted:
        raise ValidationError("notebook literal parameter schema changed")
    return found


def original_unit_checks(path: str | Path = DEFAULT_NOTEBOOK, *, timeout: float = 60.0) -> dict[str, Any]:
    from .notebook_worker import execute_worker

    return execute_worker(Path(path), "unit", timeout)


def _unit_checks_inprocess(path: str | Path = DEFAULT_NOTEBOOK) -> dict[str, Any]:
    nb, before = read_notebook(path)
    namespace: dict[str, Any] = {}
    capture = io.StringIO()
    with contextlib.redirect_stdout(capture):
        for number in (3, 5, 7, 9):
            exec(
                compile("".join(nb["cells"][number - 1]["source"]), f"original_cell_{number}", "exec"),
                namespace,
            )
    if read_notebook(path)[1] != before:
        raise ValidationError("notebook changed during read-only checks")
    return {"passed": 8, "stdout": capture.getvalue(), "notebook_sha256": before}


def reconcile_saved_traces(path: str | Path = DEFAULT_NOTEBOOK) -> dict[str, Any]:
    nb, checksum = read_notebook(path)

    def text(number: int) -> str:
        return "".join("".join(o.get("text", [])) for o in nb["cells"][number - 1].get("outputs", []))

    displays = [o["data"]["text/plain"] for o in nb["cells"][10].get("outputs", []) if "data" in o]
    display = "".join(displays[0]) if displays else ""
    stages = {
        int(m.group(1)): m.group(2)
        for m in re.finditer(
            r"^\d+\s+(\d+)\s+(Build|Test)\s+(?:CI/Config|Code|Dependency|Test)\s*$", display, re.M
        )
    }
    results = {}
    costs = {a["name"]: a["cost"] for a in RAW_ACTIONS}
    for number, policy in ((13, "historical_eig"), (17, "historical_lowest_cost")):
        cohort: list[dict[str, Any]] = []
        for block in re.split(r"=+\n(?=CASE:)", text(number))[1:]:

            def field(label: str, block: str = block) -> str:
                match = re.search(r"^" + label + r": (.+)$", block, re.M)
                if not match:
                    raise ValidationError("malformed saved trace")
                return match.group(1)

            case_id = int(field("CASE"))
            if case_id not in stages:
                raise ValidationError("missing saved stage")
            stage = stages[case_id]
            belief = normalize({s: RAW_PRIORS[s] * RAW_STAGE_LIKELIHOODS[stage][s] for s in STATES})
            if number == 13:
                actions = [
                    (m.group(1), m.group(2))
                    for m in re.finditer(r"^  Action: (.+)\n  Outcome: (.+)$", block, re.M)
                ]
            else:
                actions = [(m.group(1), m.group(2)) for m in re.finditer(r"^  (.+) → (.+)$", block, re.M)]
            for name, outcome in actions:
                belief = update_belief(belief, RAW_OUTCOMES[name][outcome])[0]
            total_cost = float(field("TOTAL COST"))
            if abs(sum(costs[a] for a, _ in actions) - total_cost) > 1e-9:
                raise ValidationError("saved cost differs from recorded actions")
            prediction: str | None = field("PREDICTION")
            prediction = None if prediction == "None" else prediction
            cohort.append(
                {
                    "case_id": case_id,
                    "stage": stage,
                    "true_state": field("TRUE"),
                    "decision": field("DECISION"),
                    "prediction": prediction,
                    "final_belief": belief,
                    "diagnostic_cost": total_cost,
                    "action_names_and_outcomes": actions,
                }
            )
        if len(cohort) != 40 or len({r["case_id"] for r in cohort}) != 40:
            raise ValidationError("expected 40 unique saved traces")
        reports = [r for r in cohort if r["decision"] == "REPORT"]
        correct = sum(r["prediction"] == r["true_state"] for r in reports)
        results[policy] = {
            "count": 40,
            "reports": len(reports),
            "correct_reports": correct,
            "wrong_reports": len(reports) - correct,
            "coverage": len(reports) / 40,
            "selective_accuracy": correct / len(reports) if reports else None,
            "correct_auto_rate": correct / 40,
            "average_diagnostic_cost": sum(r["diagnostic_cost"] for r in cohort) / 40,
            "average_actions": sum(len(r["action_names_and_outcomes"]) for r in cohort) / 40,
            "records": cohort,
        }
    return {
        "notebook_sha256": checksum,
        "source_execution": "incomplete: missing results and simulator",
        "status": "reconciled historical saved traces; observation generator not reproduced",
        "policies": results,
    }


def reference_policy_run(
    case: Any,
    bank: ObservationProvider,
    policy: str,
    path: str | Path = DEFAULT_NOTEBOOK,
    *,
    reference: LegacyReference | None = None,
) -> Diagnosis:
    reference = reference or LegacyReference(path)
    return reference.run(case, bank, policy)


class LegacyReference:
    """Original decision/update functions with a newly specified Python harness.

    This supplies the missing EIG evaluation loop, not the historical simulator.
    Use only a signal-only bank and the original Build/Test normalization. There
    is no modern resource cap, for a controlled legacy comparison only.
    """

    def __init__(self, path: str | Path = DEFAULT_NOTEBOOK) -> None:
        nb, checksum = read_notebook(path)
        if checksum != NOTEBOOK_SHA256:
            raise ValidationError("legacy reference requires pinned notebook content")
        self._checksum = checksum
        self._env: dict[str, Any] = {}
        for number in (3, 5, 7, 15):
            exec(
                compile("".join(nb["cells"][number - 1]["source"]), f"reference_cell_{number}", "exec"),
                self._env,
            )

    def run(self, case: Any, bank: ObservationProvider, policy: str) -> Diagnosis:
        if case.stage not in {"Build", "Test"}:
            raise ValidationError("legacy reference uses the original binary stage vocabulary")
        env = self._env
        checksum = self._checksum
        belief = env["calculate_posterior"](case.stage)
        remaining = env["get_candidate_actions"](case.stage, env["actions"])
        names = {a["name"]: a for a in RAW_ACTIONS}
        from .model import default_model

        actions = {a.name: a for a in default_model().actions}
        records: list[ActionRecord] = []
        spent = 0.0
        while True:
            if policy == "eig_per_cost":
                decision = env["decide_next_step"](belief, remaining, env["outcome_models"])
            elif policy == "lowest_cost":
                decision = env["decide_next_step_cost_only"](belief, remaining)
            else:
                raise ValidationError("unsupported reference policy")
            if decision["decision"] != "RECOMMEND":
                prediction = decision.get("root_cause")
                return Diagnosis(
                    RECORD_VERSION,
                    case.case_id,
                    case.stage,
                    "legacy_reference_" + policy,
                    decision["decision"],
                    "original_policy_new_harness",
                    prediction,
                    belief,
                    max(belief.values()),
                    spent,
                    tuple(records),
                    "raw-notebook/1",
                    checksum,
                    fingerprint({"limits": "catalogue exhaustion", "source": checksum}),
                    (),
                )
            action = actions[decision["action"]["name"]]
            event = bank.observe(case.case_id, action.action_id, 0, 30.0)
            if event.status != "signal":
                raise ValidationError("legacy reference needs a signal-only bank")
            assert event.outcome is not None
            label = action.labels[event.outcome]
            before = dict(belief)
            belief = env["update_posterior_with_outcome"](belief, RAW_OUTCOMES[action.name][label])
            spent += names[action.name]["cost"]
            records.append(
                ActionRecord(
                    action.action_id,
                    action.name,
                    0,
                    event.event_id,
                    event.evidence_id,
                    "signal",
                    event.outcome,
                    action.cost,
                    spent,
                    decision["action"].get("score", 0),
                    decision["action"].get("eig", 0),
                    before,
                    dict(belief),
                    None,
                    True,
                    "original_update",
                )
            )
            remaining = [a for a in remaining if a["name"] != action.name]
