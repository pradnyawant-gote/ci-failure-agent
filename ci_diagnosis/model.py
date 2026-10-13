"""Immutable, validated models. Empirical stage fitting is training-only.

Diagnostic likelihoods and effort costs remain declared notebook assumptions.
Normalization preserves ratios (including the two 1.001 binary columns) rather
than inventing intended complements. Sample-derived smoothing is separate.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .domain import STAGES as STAGES
from .domain import STATES as STATES
from .domain import Belief, OutcomeModel
from .parameters import RAW_ACTIONS, RAW_OUTCOMES, RAW_PRIORS, RAW_STAGE_LIKELIHOODS
from .probability import (
    ValidationError,
    finite_number,
    normalize,
    update_belief,
    validate_outcome_model,
    validate_vector,
)
from .records import fingerprint, freeze, identifier, plain

if TYPE_CHECKING:
    from .data import SourceRow

ACTION_IDS = (
    "pipeline_logs",
    "failed_stage",
    "last_success",
    "recent_changes",
    "dependency_changes",
    "ci_configuration",
    "runbooks",
    "image_cache",
    "hosting",
    "server_session",
)


@dataclass(frozen=True)
class Action:
    action_id: str
    name: str
    cost: float
    tags: tuple[str, ...]
    outcomes: OutcomeModel
    labels: Mapping[str, str]
    aliases: Mapping[str, str]
    permission: str = "read_only"

    def __post_init__(self) -> None:
        if (
            not isinstance(self.action_id, str)
            or not self.action_id
            or not isinstance(self.name, str)
            or not self.name
        ):
            raise ValidationError("action requires stable ID and display name")
        identifier(self.action_id, "action_id", maximum=128)
        if len(self.name) > 256:
            raise ValidationError("action name too long")
        if finite_number(self.cost, "action cost", minimum=0) <= 0:
            raise ValidationError("action cost must be strictly positive")
        if not self.tags or any(t not in STAGES + ("all",) for t in self.tags):
            raise ValidationError("invalid action stage tags")
        if self.permission != "read_only":
            raise ValidationError("this simulation supports read-only actions only")
        validate_outcome_model(self.outcomes, STATES)
        if not isinstance(self.labels, Mapping) or not isinstance(self.aliases, Mapping):
            raise ValidationError("outcome labels and aliases must be mappings")
        if any(
            not isinstance(k, str) or not isinstance(v, str) or not k or not v or len(k) > 256 or len(v) > 256
            for mapping in (self.labels, self.aliases)
            for k, v in mapping.items()
        ):
            raise ValidationError("outcome labels/aliases must be bounded nonempty strings")
        if set(self.labels) != set(self.outcomes) or any(
            v not in self.outcomes for v in self.aliases.values()
        ):
            raise ValidationError("outcome labels/aliases must match canonical IDs")
        for component in ("outcomes", "labels", "aliases"):
            object.__setattr__(self, component, freeze(getattr(self, component)))
        object.__setattr__(self, "tags", tuple(self.tags))

    def canonical_outcome(self, value: str) -> str:
        if not isinstance(value, str):
            raise ValidationError("outcome identifier must be text")
        if value in self.outcomes:
            return value
        if value in self.aliases:
            return self.aliases[value]
        raise ValidationError(f"unknown outcome for {self.action_id}")


@dataclass(frozen=True)
class Model:
    version: str
    priors: Belief
    stage_likelihoods: Mapping[str, Belief]
    actions: tuple[Action, ...]
    provenance: Mapping[str, Any]
    _identity: str = field(init=False, repr=False, compare=False, metadata={"serialize": False})

    def __post_init__(self) -> None:
        if not isinstance(self.version, str) or not self.version:
            raise ValidationError("model version is required")
        if not isinstance(self.provenance, Mapping) or any(not isinstance(a, Action) for a in self.actions):
            raise ValidationError("model requires action instances and provenance mapping")
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
        object.__setattr__(self, "_identity", fingerprint(self))

    @property
    def model_hash(self) -> str:
        return self._identity

    def initial_belief(self, stage: str) -> dict[str, float]:
        if stage not in STAGES:
            raise ValidationError("stage must be normalized before inference")
        if stage in ("Unknown", "Ambiguous"):
            return dict(self.priors)  # No invented affirmative stage evidence.
        return update_belief(self.priors, self.stage_likelihoods[stage])[0]


def default_model() -> Model:
    actions = []
    corrections: list[dict[str, Any]] = []
    for action_id, raw in zip(ACTION_IDS, RAW_ACTIONS, strict=False):
        name = raw["name"]
        entries = list(RAW_OUTCOMES[name].items())
        totals = {s: sum(v[s] for _, v in entries) for s in STATES}
        outcomes = {
            key: {s: vector[s] / totals[s] for s in STATES}
            for key, (_, vector) in zip(("signal", "no_signal"), entries, strict=False)
        }
        labels = {key: label for key, (label, _) in zip(outcomes, entries, strict=False)}
        aliases = {label: key for key, label in labels.items()}
        aliases.update({label: key for key, label in zip(outcomes, raw["outcomes"], strict=False)})
        actions.append(Action(action_id, name, raw["cost"], tuple(raw["tags"]), outcomes, labels, aliases))
        corrections.extend(
            {"action": action_id, "state": s, "original_sum": t}
            for s, t in totals.items()
            if abs(t - 1) > 1e-10
        )
    stage_totals = {s: sum(v[s] for v in RAW_STAGE_LIKELIHOODS.values()) for s in STATES}
    stages = {z: {s: v[s] / stage_totals[s] for s in STATES} for z, v in RAW_STAGE_LIKELIHOODS.items()}
    return Model(
        "notebook-assumptions-normalized/1",
        normalize(RAW_PRIORS),
        stages,
        tuple(actions),
        {
            "origin": "unchanged original notebook literal parameters",
            "normalization": "divide each prior/stage/outcome distribution by its own original total",
            "original_prior_sum": sum(RAW_PRIORS.values()),
            "original_stage_sums": stage_totals,
            "outcome_corrections": corrections,
            "diagnostic_likelihoods": "assumptions; not observed in workbook",
            "costs": "assumed relative effort units",
            "calibration": "not empirically validated",
            "support": "single exclusive mapped failure category; no simultaneous faults",
        },
    )


def fit_stage_model(
    training_rows: list[SourceRow], base: Model | None = None, *, alpha: float = 1.0, beta: float = 1.0
) -> Model:
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
    # Equivalent Laplace formulas, normalized along their conditional axis to
    # avoid overflow of alpha*states or beta*stages at valid large smoothing.
    priors = normalize({s: counts[s] + alpha for s in STATES})
    columns = {s: normalize({z: stage_counts[z][s] + beta for z in STAGES}) for s in STATES}
    likelihoods = {z: {s: columns[s][z] for s in STATES} for z in STAGES}
    provenance = plain(base.provenance)
    provenance.update(
        {
            "initialization": "training-only source counts; heuristic stage labels",
            "training_ids": sorted(ids),
            "alpha": alpha,
            "beta": beta,
            "counts": counts,
        }
    )
    return Model("training-stage-laplace/1", priors, likelihoods, base.actions, provenance)
