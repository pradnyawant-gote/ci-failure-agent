"""Validated probability arithmetic. Exact zeros retain their meaning."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from .domain import Belief, OutcomeModel


class ValidationError(ValueError):
    """Malformed input/configuration; must never lead to an automatic report."""


class ImpossibleEvidence(ValidationError):
    """The supplied observation has zero support under the current belief."""


def finite_number(
    value: object, name: str, *, minimum: float | None = None, maximum: float | None = None
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{name} must be a finite number")
    try:
        number = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValidationError(f"{name} is not representable as a finite number") from exc
    if not math.isfinite(number):
        raise ValidationError(f"{name} must be finite")
    if minimum is not None and value < minimum:
        raise ValidationError(f"{name} must be >= {minimum}")
    if maximum is not None and value > maximum:
        raise ValidationError(f"{name} must be <= {maximum}")
    return number


def validate_vector(values: object, states: Sequence[str], *, normalized: bool = False) -> dict[str, float]:
    if not isinstance(values, Mapping) or set(values) != set(states):
        raise ValidationError("probability keys must exactly match the model states")
    checked = {s: finite_number(values[s], s, minimum=0, maximum=1) for s in states}
    if normalized and not math.isclose(math.fsum(checked.values()), 1, abs_tol=1e-10, rel_tol=0):
        raise ValidationError("belief must sum to one")
    return checked


def normalize(weights: Mapping[str, float]) -> dict[str, float]:
    if not isinstance(weights, Mapping) or not weights:
        raise ValidationError("weights must be a nonempty mapping")
    clean = {s: finite_number(w, s, minimum=0) for s, w in weights.items()}
    high = max(clean.values())
    if high <= 0:
        raise ImpossibleEvidence("zero or invalid normalization mass")
    scaled = {s: w / high for s, w in clean.items()}
    total = math.fsum(scaled.values())
    return {s: w / total for s, w in scaled.items()}


def log_evidence(belief: Belief, likelihood: Belief) -> tuple[float, dict[str, float]]:
    if not isinstance(belief, Mapping):
        raise ValidationError("belief must be a mapping")
    states = tuple(belief)
    b = validate_vector(belief, states, normalized=True)
    likelihood = validate_vector(likelihood, states)
    return _log_validated(b, likelihood)


def _log_validated(b: Belief, likelihood: Belief) -> tuple[float, dict[str, float]]:
    """Internal kernel: caller has validated keys, ranges and belief mass."""
    logs = {s: math.log(b[s]) + math.log(likelihood[s]) for s in b if b[s] > 0 and likelihood[s] > 0}
    if not logs:
        raise ImpossibleEvidence("observed evidence has zero model support")
    high = max(logs.values())
    log_q = high + math.log(math.fsum(math.exp(x - high) for x in logs.values()))
    return log_q, logs


def _posterior_from_logs(states: Sequence[str], logs: Mapping[str, float]) -> dict[str, float]:
    high = max(logs.values())
    weights = {s: math.exp(logs[s] - high) if s in logs else 0.0 for s in states}
    total = math.fsum(weights.values())
    return {s: w / total for s, w in weights.items()}


def update_belief(belief: Belief, likelihood: Belief) -> tuple[dict[str, float], float]:
    log_q, logs = log_evidence(belief, likelihood)
    # Rescale before normalizing instead of multiplying tiny probabilities.
    posterior = _posterior_from_logs(tuple(belief), logs)
    validate_vector(posterior, tuple(belief), normalized=True)
    return posterior, log_q


def entropy(belief: Belief) -> float:
    if not isinstance(belief, Mapping):
        raise ValidationError("belief must be a mapping")
    b = validate_vector(belief, tuple(belief), normalized=True)
    return -math.fsum(p * math.log2(p) for p in b.values() if p > 0)


def validate_outcome_model(outcomes: object, states: Sequence[str]) -> dict[str, dict[str, float]]:
    if not isinstance(outcomes, Mapping) or not outcomes:
        raise ValidationError("an executable action needs an outcome model")
    clean = {o: validate_vector(v, states) for o, v in outcomes.items()}
    for s in states:
        if not math.isclose(math.fsum(v[s] for v in clean.values()), 1, rel_tol=0, abs_tol=1e-10):
            raise ValidationError(f"outcome probabilities for {s} must sum to one")
    return clean


def expected_information_gain(belief: Belief, outcomes: OutcomeModel) -> float:
    if not isinstance(belief, Mapping):
        raise ValidationError("belief must be a mapping")
    states = tuple(belief)
    b = validate_vector(belief, states, normalized=True)
    outcomes = validate_outcome_model(outcomes, states)
    return _eig_validated(b, outcomes)


def _eig_validated(belief: Belief, outcomes: OutcomeModel, current_entropy: float | None = None) -> float:
    """Validated belief and immutable Action models only; same log-space math.

    Public callers use expected_information_gain. The policy validates belief
    once per ranking and Action validates/freeze its model once at construction.
    """
    if current_entropy is None:
        current_entropy = -math.fsum(p * math.log2(p) for p in belief.values() if p > 0)
    expected_entropy = 0.0
    for likelihood in outcomes.values():
        try:
            log_q, logs = _log_validated(belief, likelihood)
        except ImpossibleEvidence:
            continue  # A hypothetical impossible branch contributes zero.
        posterior = _posterior_from_logs(tuple(belief), logs)
        branch_entropy = -math.fsum(p * math.log2(p) for p in posterior.values() if p > 0)
        expected_entropy += math.exp(log_q) * branch_entropy
    value = current_entropy - expected_entropy
    if value < -1e-10 or value > current_entropy + 1e-10:
        raise ValidationError("information gain outside mathematical bounds")
    return max(0.0, value)
