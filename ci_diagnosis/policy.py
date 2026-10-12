"""Existing policy families with deterministic ranking and explicit eligibility."""

from .probability import ValidationError, expected_information_gain, validate_vector
from .model import STATES

SEQUENTIAL_POLICIES = ("eig_per_cost", "lowest_cost")
BASELINES = ("fixed_test", "stage_map", "prior_map")
POLICIES = SEQUENTIAL_POLICIES + BASELINES


def rank_actions(belief, actions, policy="eig_per_cost"):
    validate_vector(belief, STATES, normalized=True)
    if policy not in SEQUENTIAL_POLICIES:
        raise ValidationError("unknown sequential policy")
    ranked = []
    for order, action in enumerate(actions):
        eig = expected_information_gain(belief, action.outcomes)
        ranked.append({"action_id": action.action_id, "name": action.name, "cost": action.cost,
                       "eig": eig, "score": eig / action.cost, "catalogue_order": order})
    key = (lambda a: (-a["score"], a["catalogue_order"])) if policy == "eig_per_cost" else (lambda a: (a["cost"], a["catalogue_order"]))
    return sorted(ranked, key=key)


def top_state(belief):
    validate_vector(belief, STATES, normalized=True)
    return max(STATES, key=lambda s: belief[s])

