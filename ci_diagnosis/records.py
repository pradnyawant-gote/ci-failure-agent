"""Typed public inputs and versioned, deterministic diagnostic records.

There are deliberately no truth-bearing fields in PublicCase or Diagnosis.
Truth is introduced by the evaluator after termination.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, fields, is_dataclass
from collections.abc import Mapping
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from .domain import Belief, STATES, STAGES
from .probability import ValidationError, finite_number, validate_vector

if TYPE_CHECKING:
    from .model import Action

RECORD_VERSION = "ci-diagnosis-record/2"
STATUSES = frozenset({"signal", "missing", "inconclusive", "unavailable", "tool_error", "timeout"})


def identifier(value: object, name: str, *, maximum: int = 256) -> str:
    if not isinstance(value,str) or not value or len(value)>maximum or not re.fullmatch(r"[A-Za-z0-9_.:/-]+",value):
        raise ValidationError(f"{name} must be a bounded identifier")
    return value


def freeze(value: Any) -> Any:
    """Copy and recursively freeze JSON-compatible containers at boundaries."""
    if isinstance(value,Mapping):
        if any(not isinstance(k,str) for k in value):
            raise ValidationError("serialized mapping keys must be strings")
        return MappingProxyType({k:freeze(v) for k,v in value.items()})
    if isinstance(value,(list,tuple)):
        return tuple(freeze(v) for v in value)
    return value


def plain(value: object) -> Any:
    if is_dataclass(value) and not isinstance(value,type):
        return {f.name: plain(getattr(value, f.name)) for f in fields(value) if f.metadata.get("serialize",True)}
    if isinstance(value, Mapping):
        if any(not isinstance(k,str) for k in value):
            raise ValidationError("serialized mapping keys must be strings")
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return sorted(plain(v) for v in value)
    return value


def fingerprint(value: object) -> str:
    try:
        raw = json.dumps(plain(value), sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError,ValueError) as exc:
        raise ValidationError("unsupported fingerprint value") from exc
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PublicCase:
    case_id: str
    stage: str
    supported_scope: bool = True

    def __post_init__(self) -> None:
        identifier(self.case_id,"case_id",maximum=128)
        if not isinstance(self.stage, str) or self.stage not in STAGES:
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

    def validate(self, action: Action) -> float:
        if self.action_id != action.action_id:
            raise ValidationError("observation action does not match requested action")
        identifier(self.event_id,"event_id")
        if not isinstance(self.status,str) or self.status not in STATUSES:
            raise ValidationError("unknown observation status")
        if self.status == "signal" and (not isinstance(self.outcome,str) or self.outcome not in action.outcomes):
            raise ValidationError("unknown outcome for action")
        if self.status != "signal" and self.outcome is not None:
            raise ValidationError("a failed/missing check cannot carry a diagnostic outcome")
        if self.evidence_id is not None:
            identifier(self.evidence_id,"evidence_id")
        if not isinstance(self.detail,str) or len(self.detail)>4096:
            raise ValidationError("detail must be bounded text")
        cost = action.cost if self.cost is None else finite_number(self.cost, "incurred cost", minimum=0)
        # Overrun is a contractual cost fact, not a malformed numeric value.
        # The runner records it and terminates instead of substituting a lower cost.
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
    posterior_before: Belief
    posterior_after: Belief
    log_predictive_probability: float | None
    applied: bool
    reason: str
    detail: str = ""
    cost_basis: str = "reserved_estimate"
    reported_cost: float | None = None

    def __post_init__(self) -> None:
        identifier(self.action_id,"action_id")
        identifier(self.event_id,"event_id")
        if self.evidence_id is not None:
            identifier(self.evidence_id,"evidence_id")
        if type(self.attempt) is not int or self.attempt<0 or self.status not in STATUSES:
            raise ValidationError("invalid action record attempt/status")
        if not isinstance(self.action_name,str) or not self.action_name or len(self.action_name)>256:
            raise ValidationError("invalid action display label")
        if not isinstance(self.reason,str) or not isinstance(self.detail,str) or len(self.detail)>512:
            raise ValidationError("invalid record error context")
        for name in ("cost","cumulative_cost","eig"):
            finite_number(getattr(self,name),name,minimum=0)
        finite_number(self.score,"score")
        if self.reported_cost is not None:
            finite_number(self.reported_cost,"reported_cost",minimum=0)
        if self.log_predictive_probability is not None:
            finite_number(self.log_predictive_probability,"log predictive probability",maximum=1e-10)
        if type(self.applied) is not bool or self.cost_basis not in {"reported","reserved_estimate"}:
            raise ValidationError("invalid record application/cost basis")
        for name in ("posterior_before","posterior_after"):
            object.__setattr__(self,name,freeze(validate_vector(getattr(self,name),STATES,normalized=True)))


@dataclass(frozen=True)
class Diagnosis:
    record_version: str
    case_id: str
    stage: str
    policy: str
    decision: str
    reason: str
    prediction: str | None
    final_belief: Belief
    confidence: float
    diagnostic_cost: float
    actions_taken: tuple[ActionRecord, ...]
    model_version: str
    model_hash: str
    config_hash: str
    candidate_trace: tuple[Mapping[str, Any], ...]
    calibration: str = "uncalibrated model probability; simulation only"
    budget_breached: bool = False
    benchmark: bool = False

    def __post_init__(self) -> None:
        identifier(self.case_id,"case_id",maximum=128)
        if self.stage not in STAGES or self.decision not in {"REPORT","ESCALATE"}:
            raise ValidationError("invalid terminal stage/decision")
        if (self.decision=="REPORT" and self.prediction not in STATES) or (self.decision=="ESCALATE" and self.prediction is not None):
            raise ValidationError("prediction disagrees with terminal disposition")
        b=validate_vector(self.final_belief,STATES,normalized=True)
        finite_number(self.confidence,"confidence",minimum=0,maximum=1)
        if not math.isclose(self.confidence,max(b.values()),abs_tol=1e-10,rel_tol=0):
            raise ValidationError("confidence disagrees with final belief")
        finite_number(self.diagnostic_cost,"diagnostic_cost",minimum=0)
        if not math.isclose(math.fsum(a.cost for a in self.actions_taken),self.diagnostic_cost,abs_tol=1e-9,rel_tol=0):
            raise ValidationError("diagnostic cost disagrees with trace")
        if type(self.budget_breached) is not bool or type(self.benchmark) is not bool:
            raise ValidationError("invalid terminal flags")
        object.__setattr__(self,"final_belief",freeze(b))
        object.__setattr__(self,"actions_taken",tuple(self.actions_taken))
        object.__setattr__(self,"candidate_trace",freeze(self.candidate_trace))

