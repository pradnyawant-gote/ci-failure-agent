"""Immutable, validated models. Empirical stage fitting is training-only.

Diagnostic likelihoods and effort costs remain declared notebook assumptions.
Normalization preserves ratios (including the two 1.001 binary columns) rather
than inventing intended complements. Sample-derived smoothing is separate.
"""

from dataclasses import dataclass
from types import MappingProxyType
from collections.abc import Mapping

from .parameters import RAW_PRIORS, RAW_STAGE_LIKELIHOODS, RAW_ACTIONS, RAW_OUTCOMES
from .probability import (ValidationError, finite_number, normalize, validate_vector,
                          validate_outcome_model, update_belief)
from .records import fingerprint, plain

STATES = ("Code", "Test", "Dependency", "CI/Config")
STAGES = ("Build", "Test", "Setup / Dependency", "Quality / Analysis", "Deploy / Publish", "Ambiguous", "Unknown")
ACTION_IDS = ("pipeline_logs", "failed_stage", "last_success", "recent_changes", "dependency_changes",
              "ci_configuration", "runbooks", "image_cache", "hosting", "server_session")


def freeze(value):
    if isinstance(value, Mapping):
        return MappingProxyType({k: freeze(v) for k, v in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(freeze(v) for v in value)
    return value


@dataclass(frozen=True)
class Action:
    action_id: str
    name: str
    cost: float
    tags: tuple[str, ...]
    outcomes: Mapping
    labels: Mapping
    aliases: Mapping
    permission: str = "read_only"

    def __post_init__(self):
        if not self.action_id or not self.name:
            raise ValidationError("action requires stable ID and display name")
        if finite_number(self.cost, "action cost", minimum=0) <= 0:
            raise ValidationError("action cost must be strictly positive")
        if not self.tags or any(t not in STAGES + ("all",) for t in self.tags):
            raise ValidationError("invalid action stage tags")
        if self.permission != "read_only":
            raise ValidationError("this simulation supports read-only actions only")
        validate_outcome_model(self.outcomes, STATES)
        if set(self.labels) != set(self.outcomes) or any(v not in self.outcomes for v in self.aliases.values()):
            raise ValidationError("outcome labels/aliases must match canonical IDs")
        for field in ("outcomes", "labels", "aliases"):
            object.__setattr__(self, field, freeze(getattr(self, field)))
        object.__setattr__(self, "tags", tuple(self.tags))

    def canonical_outcome(self, value):
        if value in self.outcomes:
            return value
        if value in self.aliases:
            return self.aliases[value]
        raise ValidationError(f"unknown outcome for {self.action_id}: {value!r}")


@dataclass(frozen=True)
class Model:
    version: str
    priors: Mapping
    stage_likelihoods: Mapping
    actions: tuple[Action, ...]
    provenance: Mapping

    def __post_init__(self):
        if not self.version:
            raise ValidationError("model version is required")
        validate_vector(self.priors, STATES, normalized=True)
        if set(self.stage_likelihoods) != set(STAGES):
            raise ValidationError("stage vocabulary must exactly match model")
        for vector in self.stage_likelihoods.values():
            validate_vector(vector, STATES)
        for s in STATES:
            total = sum(v[s] for v in self.stage_likelihoods.values())
            if abs(total - 1) > 1e-10:
                raise ValidationError("stage likelihoods must sum over stages for each state")
        if len({a.action_id for a in self.actions}) != len(self.actions):
            raise ValidationError("duplicate action IDs")
        for name in ("priors", "stage_likelihoods", "provenance"):
            object.__setattr__(self, name, freeze(getattr(self, name)))
        object.__setattr__(self, "actions", tuple(self.actions))

    @property
    def model_hash(self):
        return fingerprint(self)

    def initial_belief(self, stage):
        if stage not in STAGES:
            raise ValidationError("stage must be normalized before inference")
        if stage in ("Unknown", "Ambiguous"):
            return dict(self.priors)  # No invented affirmative stage evidence.
        return update_belief(self.priors, self.stage_likelihoods[stage])[0]


def default_model():
    actions = []
    corrections = []
    for action_id, raw in zip(ACTION_IDS, RAW_ACTIONS):
        name = raw["name"]
        entries = list(RAW_OUTCOMES[name].items())
        totals = {s: sum(v[s] for _, v in entries) for s in STATES}
        outcomes = {key: {s: vector[s] / totals[s] for s in STATES}
                    for key, (_, vector) in zip(("signal", "no_signal"), entries)}
        labels = {key: label for key, (label, _) in zip(outcomes, entries)}
        aliases = {label: key for key, label in labels.items()}
        aliases.update({label: key for key, label in zip(outcomes, raw["outcomes"])})
        actions.append(Action(action_id, name, raw["cost"], tuple(raw["tags"]), outcomes, labels, aliases))
        corrections.extend({"action": action_id, "state": s, "original_sum": t}
                           for s, t in totals.items() if abs(t - 1) > 1e-10)
    stage_totals = {s: sum(v[s] for v in RAW_STAGE_LIKELIHOODS.values()) for s in STATES}
    stages = {z: {s: v[s] / stage_totals[s] for s in STATES} for z, v in RAW_STAGE_LIKELIHOODS.items()}
    return Model("notebook-assumptions-normalized/1", normalize(RAW_PRIORS), stages, tuple(actions), {
        "origin": "unchanged original notebook literal parameters",
        "normalization": "divide each prior/stage/outcome distribution by its own original total",
        "original_prior_sum": sum(RAW_PRIORS.values()), "original_stage_sums": stage_totals,
        "outcome_corrections": corrections, "diagnostic_likelihoods": "assumptions; not observed in workbook",
        "costs": "assumed relative effort units", "calibration": "not empirically validated",
        "support": "single exclusive mapped failure category; no simultaneous faults",
    })


def fit_stage_model(training_rows, base=None, *, alpha=1.0, beta=1.0):
    alpha = finite_number(alpha, "alpha", minimum=0)
    beta = finite_number(beta, "beta", minimum=0)
    if alpha == 0 or beta == 0 or not training_rows:
        raise ValidationError("positive smoothing and nonempty training data required")
    base = base or default_model()
    counts = {s: 0 for s in STATES}
    stage_counts = {z: {s: 0 for s in STATES} for z in STAGES}
    ids = set()
    for row in training_rows:
        if row.state not in STATES or row.stage not in STAGES or row.source_id in ids:
            raise ValidationError("invalid or duplicate training case")
        ids.add(row.source_id)
        counts[row.state] += 1
        stage_counts[row.stage][row.state] += 1
    priors = {s: (counts[s] + alpha) / (len(training_rows) + alpha * len(STATES)) for s in STATES}
    likelihoods = {z: {s: (stage_counts[z][s] + beta) / (counts[s] + beta * len(STAGES)) for s in STATES} for z in STAGES}
    provenance = plain(base.provenance)
    provenance.update({"initialization": "training-only source counts; heuristic stage labels",
                       "training_ids": sorted(ids), "alpha": alpha, "beta": beta, "counts": counts})
    return Model("training-stage-laplace/1", priors, likelihoods, base.actions, provenance)

