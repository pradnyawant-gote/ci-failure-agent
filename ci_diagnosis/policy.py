"""Existing policy families with deterministic ranking and explicit eligibility."""

from __future__ import annotations

from collections.abc import Sequence

from .decision_cost import DecisionCosts
from .domain import Belief, RankedAction
from .model import STATES, Action
from .probability import ValidationError, _eig_validated, entropy, validate_vector

SEQUENTIAL_POLICIES = ("eig_per_cost", "lowest_cost", "risk_per_cost")
BASELINES = ("fixed_test", "stage_map", "prior_map")
POLICIES = SEQUENTIAL_POLICIES + BASELINES


def rank_actions(
    belief: Belief,
    actions: Sequence[Action],
    policy: str = "eig_per_cost",
    costs: DecisionCosts | None = None,
) -> list[RankedAction]:
    b = validate_vector(belief, STATES, normalized=True)
    if policy not in SEQUENTIAL_POLICIES:
        raise ValidationError("unknown sequential policy")
    ranked: list[RankedAction] = []
    costs = costs or DecisionCosts()
    current_entropy = entropy(b)
    for order, action in enumerate(actions):
        eig = _eig_validated(b, action.outcomes, current_entropy)
        risk_delta = costs.expected_reduction(belief, action.outcomes) if policy == "risk_per_cost" else 0.0
        ranked.append(
            {
                "action_id": action.action_id,
                "name": action.name,
                "cost": action.cost,
                "eig": eig,
                "score": (risk_delta if policy == "risk_per_cost" else eig) / action.cost,
                "catalogue_order": order,
                "expected_risk_reduction": risk_delta,
            }
        )
    key = (
        (lambda a: (-a["score"], a["catalogue_order"]))
        if policy != "lowest_cost"
        else (lambda a: (a["cost"], a["catalogue_order"]))
    )
    return sorted(ranked, key=key)


def top_state(belief: Belief) -> str:
    validate_vector(belief, STATES, normalized=True)
    return max(STATES, key=lambda s: belief[s])
