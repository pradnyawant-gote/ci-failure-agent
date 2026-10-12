"""Typed public inputs and versioned, deterministic diagnostic records.

There are deliberately no truth-bearing fields in PublicCase or Diagnosis.
Truth is introduced by the evaluator after termination.
"""

import hashlib
import json
from dataclasses import dataclass, fields, is_dataclass
from collections.abc import Mapping

from .probability import ValidationError, finite_number

RECORD_VERSION = "ci-diagnosis-record/1"
STATUSES = frozenset({"signal", "missing", "inconclusive", "unavailable", "tool_error", "timeout"})


def plain(value):
    if is_dataclass(value):
        return {f.name: plain(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, Mapping):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return sorted(plain(v) for v in value)
    return value


def fingerprint(value):
    raw = json.dumps(plain(value), sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PublicCase:
    case_id: str
    stage: str
    supported_scope: bool = True

    def __post_init__(self):
        if not isinstance(self.case_id, str) or not self.case_id.strip():
            raise ValidationError("case_id must be a nonempty string")
        if not isinstance(self.stage, str):
            raise ValidationError("stage must be a normalized string")
        if type(self.supported_scope) is not bool:
            raise ValidationError("supported_scope must be boolean")


@dataclass(frozen=True)
class Observation:
    action_id: str
    event_id: str
    status: str
    outcome: str | None = None
    evidence_id: str | None = None
    cost: float | None = None
    elapsed_seconds: float = 0.0
    detail: str = ""

    def validate(self, action):
        if self.action_id != action.action_id:
            raise ValidationError("observation action does not match requested action")
        if not isinstance(self.event_id, str) or not self.event_id:
            raise ValidationError("event_id is required")
        if self.status not in STATUSES:
            raise ValidationError("unknown observation status")
        if self.status == "signal" and self.outcome not in action.outcomes:
            raise ValidationError("unknown outcome for action")
        if self.status != "signal" and self.outcome is not None:
            raise ValidationError("a failed/missing check cannot carry a diagnostic outcome")
        if self.evidence_id is not None and (not isinstance(self.evidence_id, str) or not self.evidence_id):
            raise ValidationError("evidence_id must be a nonempty string when supplied")
        cost = action.cost if self.cost is None else finite_number(self.cost, "incurred cost", minimum=0)
        if cost > action.cost + 1e-10:
            raise ValidationError("provider cost exceeds reserved upper bound")
        finite_number(self.elapsed_seconds, "elapsed_seconds", minimum=0)
        return cost


@dataclass(frozen=True)
class ActionRecord:
    action_id: str
    action_name: str
    attempt: int
    event_id: str
    evidence_id: str | None
    status: str
    outcome: str | None
    cost: float
    cumulative_cost: float
    score: float
    eig: float
    posterior_before: dict
    posterior_after: dict
    log_predictive_probability: float | None
    applied: bool
    reason: str
    detail: str = ""


@dataclass(frozen=True)
class Diagnosis:
    record_version: str
    case_id: str
    stage: str
    policy: str
    decision: str
    reason: str
    prediction: str | None
    final_belief: dict
    confidence: float
    diagnostic_cost: float
    actions_taken: tuple[ActionRecord, ...]
    model_version: str
    model_hash: str
    config_hash: str
    candidate_trace: tuple[dict, ...]
    calibration: str = "uncalibrated model probability; simulation only"

