"""Existing policy families with deterministic ranking and explicit eligibility."""

from __future__ import annotations

from collections.abc import Sequence

from .probability import ValidationError, expected_information_gain, validate_vector
from .model import STATES,Action
from .domain import Belief,RankedAction
from .decision_cost import DecisionCosts

SEQUENTIAL_POLICIES = ("eig_per_cost", "lowest_cost", "risk_per_cost")
BASELINES = ("fixed_test", "stage_map", "prior_map")
POLICIES = SEQUENTIAL_POLICIES + BASELINES


def rank_actions(belief: Belief, actions: Sequence[Action], policy: str="eig_per_cost",
                 costs: DecisionCosts | None=None) -> list[RankedAction]:
    validate_vector(belief, STATES, normalized=True)
    if policy not in SEQUENTIAL_POLICIES:
        raise ValidationError("unknown sequential policy")
    ranked: list[RankedAction] = []
    costs=costs or DecisionCosts()
    for order, action in enumerate(actions):
        eig = expected_information_gain(belief, action.outcomes)
        risk_delta=costs.expected_reduction(belief,action.outcomes) if policy=="risk_per_cost" else 0.0
        ranked.append({"action_id": action.action_id, "name": action.name, "cost": action.cost,
                       "eig": eig, "score": (risk_delta if policy=="risk_per_cost" else eig) / action.cost,
                       "catalogue_order": order,"expected_risk_reduction":risk_delta})
    key = (lambda a: (-a["score"], a["catalogue_order"])) if policy != "lowest_cost" else (lambda a: (a["cost"], a["catalogue_order"]))
    return sorted(ranked, key=key)


def top_state(belief: Belief) -> str:
    validate_vector(belief, STATES, normalized=True)
    return max(STATES, key=lambda s: belief[s])

