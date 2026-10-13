"""One bounded runner for reports and referrals, including final observations.

Providers must honor the passed deadline: built-in providers are bounded local
lookups. This module does not forcibly interrupt arbitrary blocking external
code and is not a live CI adapter. Time, cost and permissions are contractual.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from collections.abc import Callable
from typing import Any

from .model import STAGES,Model
from .domain import ObservationProvider
from .policy import POLICIES, BASELINES, rank_actions, top_state
from .probability import ValidationError, ImpossibleEvidence, finite_number, update_belief
from .records import RECORD_VERSION, PublicCase, Observation, ActionRecord, Diagnosis, fingerprint
from .observability import emit,safe_detail


@dataclass(frozen=True)
class Limits:
    confidence_threshold: float = 0.90
    max_steps: int = 8
    budget: float = 11.0
    max_attempts: int = 12
    max_retries: int = 0
    max_seconds: float = 30.0
    minimum_eig: float = 1e-12
    allowed_actions: frozenset[str] | None = None
    allow_uncalibrated: bool = True
    benchmark_mode: bool = False

    def __post_init__(self) -> None:
        finite_number(self.confidence_threshold, "threshold", minimum=0, maximum=1)
        finite_number(self.budget, "budget", minimum=0)
        finite_number(self.max_seconds, "max_seconds", minimum=0)
        finite_number(self.minimum_eig, "minimum_eig", minimum=0)
        for field in ("max_steps", "max_attempts", "max_retries"):
            value = getattr(self, field)
            if type(value) is not int or value < 0:
                raise ValidationError(f"{field} must be a nonnegative integer")
        if type(self.allow_uncalibrated) is not bool or type(self.benchmark_mode) is not bool:
            raise ValidationError("allow_uncalibrated must be boolean")
        if self.allowed_actions is not None:
            object.__setattr__(self, "allowed_actions", frozenset(self.allowed_actions))


def diagnose(case: PublicCase, model: Model, provider: ObservationProvider, policy: str="eig_per_cost",
             limits: Limits | None=None, *, clock: Callable[[],float]=time.monotonic) -> Diagnosis:
    if not isinstance(case, PublicCase) or case.stage not in STAGES:
        raise ValidationError("diagnose needs a validated PublicCase with normalized stage")
    if policy not in POLICIES:
        raise ValidationError("unknown policy")
    limits = limits or Limits()
    if policy in BASELINES and not limits.benchmark_mode:
        raise ValidationError("forced baseline requires explicit benchmark_mode")
    if limits.allowed_actions is not None and not limits.allowed_actions.issubset({a.action_id for a in model.actions}):
        raise ValidationError("unknown permitted action ID")
    initial_mismatch = False
    try:
        belief = model.initial_belief(case.stage)
    except ImpossibleEvidence:
        belief = dict(model.priors)
        initial_mismatch = True
    records: list[ActionRecord] = []
    candidates: list[dict[str,Any]] = []
    used: set[str] = set()
    events: dict[str,tuple[str,str | None]] = {}
    evidence: dict[str,str | None] = {}
    attempts: dict[str,int] = {}
    spent = 0.0
    started = clock()
    elapsed_observed = 0.0
    model_hash, config_hash = model.model_hash, fingerprint(limits)
    case_ref=fingerprint(case.case_id)

    def finish(decision: str, reason: str, prediction: str | None=None) -> Diagnosis:
        breached=spent>limits.budget+1e-10
        emit("diagnostic_finished",case_ref=case_ref,policy=policy,decision=decision,reason=reason,
             diagnostic_cost=spent,budget_breached=breached)
        return Diagnosis(RECORD_VERSION, case.case_id, case.stage, policy, decision, reason, prediction,
                         dict(belief), max(belief.values()), spent, tuple(records), model.version,
                         model_hash, config_hash, tuple(candidates),budget_breached=breached,
                         benchmark=policy in BASELINES)

    if not case.supported_scope:
        return finish("ESCALATE", "unsupported_scope")
    if initial_mismatch:
        return finish("ESCALATE", "stage_model_mismatch_zero_support")
    if policy in BASELINES:
        # Forced baselines deliberately bypass the confidence gate. They are
        # evaluation comparators, not recommendations for automatic deployment.
        prediction = "Test" if policy == "fixed_test" else top_state(model.priors if policy == "prior_map" else belief)
        if policy == "fixed_test":
            belief = {s: float(s == "Test") for s in belief}
        elif policy == "prior_map":
            belief = dict(model.priors)
        return finish("REPORT", "forced_baseline_bypasses_gate", prediction)

    while True:
        if clock() - started >= limits.max_seconds or elapsed_observed >= limits.max_seconds:
            return finish("ESCALATE", "deadline_exhausted")
        if max(belief.values()) >= limits.confidence_threshold:
            if not limits.allow_uncalibrated:
                return finish("ESCALATE", "empirical_calibration_unavailable")
            return finish("REPORT", "model_confidence_threshold", top_state(belief))
        if len(used) >= limits.max_steps:
            return finish("ESCALATE", "step_limit")
        if len(records) >= limits.max_attempts:
            return finish("ESCALATE", "attempt_limit")
        feasible, rejected = [], {}
        for action in model.actions:
            if action.action_id in used:
                reason = "completed_or_retired"
            elif "all" not in action.tags and case.stage not in action.tags:
                reason = "stage_ineligible"
            elif limits.allowed_actions is not None and action.action_id not in limits.allowed_actions:
                reason = "permission_unavailable"
            elif action.cost > limits.budget - spent + 1e-10:
                reason = "unaffordable"
            else:
                try:
                    available=provider.available(action.action_id)
                    if type(available) is not bool:
                        raise ValidationError("availability must be boolean")
                except Exception as exc:
                    emit("provider_availability_error",case_ref=case_ref,action_id=action.action_id,
                         exception_type=type(exc).__name__)
                    rejected[action.action_id]="provider_availability_error"
                    continue
                if not available:
                    rejected[action.action_id]="provider_unavailable"
                    continue
                feasible.append(action)
                continue
            rejected[action.action_id] = reason
        ranking = rank_actions(belief, feasible, policy)
        useful = [r for r in ranking if r["eig"] > limits.minimum_eig]
        if policy=="risk_per_cost" and useful and not any(r["score"]>0 for r in useful):
            # Explicit EIG exploration fallback protects useful multistep sequences
            # when one-step unconstrained report risk has no immediate reduction.
            useful=sorted(useful,key=lambda r:(-r["eig"]/r["cost"],r["catalogue_order"]))
        candidates.append({"step": len(used), "ranking": ranking, "rejected": rejected,
                           "remaining_budget": limits.budget - spent})
        if not useful:
            return finish("ESCALATE", "no_informative_actions" if feasible else "no_feasible_actions")
        choice = useful[0]
        action = next(a for a in feasible if a.action_id == choice["action_id"])
        attempt = attempts.get(action.action_id, 0)
        attempts[action.action_id] = attempt + 1
        before = dict(belief)
        log_q = None
        applied = False
        terminal_reason = None
        remaining_seconds = max(0.0, limits.max_seconds - max(clock() - started, elapsed_observed))
        if remaining_seconds<=0:
            return finish("ESCALATE","deadline_exhausted")
        cost_basis="reported"
        reported_cost: float | None=None
        try:
            obs = provider.observe(case.case_id, action.action_id, attempt, remaining_seconds)
            if not isinstance(obs, Observation):
                raise ValidationError("provider must return Observation")
            cost = obs.validate(action)
            reported_cost=obs.cost
            cost_basis="reserved_estimate" if obs.cost is None else "reported"
        except Exception as exc:
            # A malformed event or adapter exception is a failed measurement.
            emit("provider_exception",case_ref=case_ref,action_id=action.action_id,exception_type=type(exc).__name__)
            obs = Observation(action.action_id, fingerprint([case_ref,action.action_id,attempt,"invalid"]),
                              "tool_error", detail=f"provider failure ({type(exc).__name__}); message omitted")
            cost = action.cost
            cost_basis="reserved_estimate"
            terminal_reason = "invalid_observation_or_provider_error"
        if cost>action.cost+1e-10:
            terminal_reason="provider_cost_overrun"
        if clock() - started >= limits.max_seconds or elapsed_observed + obs.elapsed_seconds >= limits.max_seconds:
            obs = Observation(action.action_id, obs.event_id, "timeout", evidence_id=obs.evidence_id,
                              cost=cost, elapsed_seconds=obs.elapsed_seconds,
                              detail="provider result arrived after the episode deadline")
        spent += cost
        elapsed_observed += obs.elapsed_seconds
        if terminal_reason:
            reason=terminal_reason
        elif obs.event_id in events and events[obs.event_id]!=(obs.status,obs.outcome):
            reason=terminal_reason="contradictory_event_identity"
        elif obs.event_id in events:
            reason = "duplicate_event"
            # Cost is incurred on the request even if the provider replayed an
            # old result; only evidence application is idempotent.
        elif obs.status=="signal" and obs.evidence_id is not None and obs.evidence_id in evidence and evidence[obs.evidence_id]!=obs.outcome:
            reason=terminal_reason="contradictory_evidence_identity"
        elif obs.status=="signal" and obs.evidence_id is not None and obs.evidence_id in evidence:
            reason = "duplicate_evidence"
        elif obs.status == "signal":
            assert obs.outcome is not None  # Established by Observation.validate.
            try:
                belief, log_q = update_belief(belief, action.outcomes[obs.outcome])
                applied = True
                reason = "accepted_evidence"
                if obs.evidence_id is not None:
                    evidence[obs.evidence_id]=obs.outcome
            except ImpossibleEvidence:
                reason = terminal_reason = "model_mismatch_zero_support"
        else:
            reason = obs.status
        events[obs.event_id]=(obs.status,obs.outcome)
        records.append(ActionRecord(action.action_id, action.name, attempt, obs.event_id, obs.evidence_id,
                                    obs.status, obs.outcome, cost, spent, choice["score"], choice["eig"],
                                    before, dict(belief), log_q, applied, reason, safe_detail(obs.detail),
                                    cost_basis,reported_cost))
        emit("observation_recorded",case_ref=case_ref,action_id=action.action_id,status=obs.status,
             reason=reason,cost=cost,applied=applied)
        if terminal_reason:
            return finish("ESCALATE", terminal_reason)
        retry = obs.status in {"tool_error", "timeout"} and attempt < limits.max_retries
        if not retry:
            used.add(action.action_id)
        # Re-enter the gate before testing remaining steps/cost. The final
        # successful observation can therefore produce a terminal report.

