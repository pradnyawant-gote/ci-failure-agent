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
    logs = {s: math.log(b[s]) + math.log(likelihood[s]) for s in states if b[s] > 0 and likelihood[s] > 0}
    if not logs:
        raise ImpossibleEvidence("observed evidence has zero model support")
    high = max(logs.values())
    log_q = high + math.log(math.fsum(math.exp(x - high) for x in logs.values()))
    return log_q, logs


def update_belief(belief: Belief, likelihood: Belief) -> tuple[dict[str, float], float]:
    log_q, logs = log_evidence(belief, likelihood)
    # Rescale before normalizing instead of multiplying tiny probabilities.
    high = max(logs.values())
    posterior = normalize({s: math.exp(logs[s] - high) if s in logs else 0.0 for s in belief})
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
    validate_vector(belief, states, normalized=True)
    outcomes = validate_outcome_model(outcomes, states)
    expected_entropy = 0.0
    for likelihood in outcomes.values():
        try:
            posterior, log_q = update_belief(belief, likelihood)
        except ImpossibleEvidence:
            continue  # A hypothetical impossible branch contributes zero.
        expected_entropy += math.exp(log_q) * entropy(posterior)
    value = entropy(belief) - expected_entropy
    if value < -1e-10 or value > entropy(belief) + 1e-10:
        raise ValidationError("information gain outside mathematical bounds")
    return max(0.0, value)
