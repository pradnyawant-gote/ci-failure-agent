import math
import unittest
from dataclasses import replace

from ci_diagnosis.model import STATES, default_model
from ci_diagnosis.policy import rank_actions
from ci_diagnosis.probability import (
    ImpossibleEvidence,
    ValidationError,
    expected_information_gain,
    normalize,
    update_belief,
    validate_vector,
)
from tests.helpers import two_state_model


class ProbabilityTests(unittest.TestCase):
    def setUp(self):
        self.belief = dict(zip(STATES, (0.5, 0.5, 0.0, 0.0), strict=False))

    def test_hand_calculated_bayes_and_evidence(self):
        posterior, log_q = update_belief(self.belief, dict(zip(STATES, (0.8, 0.2, 0.5, 0.5), strict=False)))
        self.assertAlmostEqual(posterior["Code"], 0.8)
        self.assertAlmostEqual(posterior["Test"], 0.2)
        self.assertAlmostEqual(math.exp(log_q), 0.5)
        self.assertEqual(posterior["Dependency"], 0)

    def test_hand_calculated_eig(self):
        action = two_state_model().actions[0]
        expected = 1 + 0.8 * math.log2(0.8) + 0.2 * math.log2(0.2)
        self.assertAlmostEqual(expected_information_gain(self.belief, action.outcomes), expected)
        self.assertAlmostEqual(expected, 0.2780719051126377)

    def test_policy_prevalidated_kernel_matches_public_math(self):
        model = default_model()
        for vector in (
            (0.25, 0.25, 0.25, 0.25),
            (0.5, 0.5, 0.0, 0.0),
            (0.99, 0.001, 0.008, 0.001),
            (1.0, 0.0, 0.0, 0.0),
        ):
            belief = dict(zip(STATES, vector, strict=False))
            ranking = rank_actions(belief, model.actions)
            for ranked in ranking:
                action = next(a for a in model.actions if a.action_id == ranked["action_id"])
                self.assertAlmostEqual(
                    ranked["eig"], expected_information_gain(belief, action.outcomes), places=12
                )

    def test_likelihood_scale_invariance(self):
        a, _ = update_belief(self.belief, dict.fromkeys(STATES, 0.5))
        b, _ = update_belief(self.belief, dict.fromkeys(STATES, 0.25))
        self.assertEqual(a, b)

    def test_hypothetical_impossible_branch_is_skipped(self):
        self.assertEqual(
            expected_information_gain(
                self.belief, {"impossible": dict.fromkeys(STATES, 0.0), "certain": dict.fromkeys(STATES, 1.0)}
            ),
            0,
        )

    def test_observed_impossibility_is_explicit(self):
        with self.assertRaises(ImpossibleEvidence):
            update_belief(self.belief, dict.fromkeys(STATES, 0.0))

    def test_log_space_underflow_protection(self):
        likelihood = dict.fromkeys(STATES, 5e-324)
        self.assertEqual(sum(self.belief[s] * likelihood[s] for s in STATES), 0)
        posterior, log_q = update_belief(self.belief, likelihood)
        self.assertAlmostEqual(posterior["Code"], 0.5)
        self.assertLess(log_q, -740)

    def test_large_weight_normalization_does_not_overflow(self):
        self.assertEqual(normalize({"a": 1e308, "b": 1e308}), {"a": 0.5, "b": 0.5})

    def test_invalid_belief_type_rejected(self):
        for value in (None, [], 1, "belief"):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                update_belief(value, dict.fromkeys(STATES, 0.5))

    def test_bad_values_rejected(self):
        for value in (-0.1, 1.1, float("nan"), float("inf"), "0.5", True):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                update_belief(self.belief, {**dict.fromkeys(STATES, 0.5), "Code": value})

    def test_bad_belief_keys_and_totals_rejected(self):
        for belief in ({}, {"Code": 1}, dict.fromkeys(STATES, 0.95), {**self.belief, "Extra": 0}):
            with self.subTest(belief=belief), self.assertRaises(ValidationError):
                validate_vector(belief, STATES, normalized=True)

    def test_bad_conditional_sum_rejected(self):
        with self.assertRaises(ValidationError):
            expected_information_gain(
                self.belief, {"yes": dict.fromkeys(STATES, 0.6), "no": dict.fromkeys(STATES, 0.5)}
            )

    def test_perfect_and_uninformative_eig(self):
        perfect = two_state_model(positive=(1, 0, 0.5, 0.5)).actions[0]
        blank = two_state_model(positive=(0.5, 0.5, 0.5, 0.5)).actions[0]
        self.assertEqual(expected_information_gain(self.belief, perfect.outcomes), 1)
        self.assertEqual(expected_information_gain(self.belief, blank.outcomes), 0)

    def test_normalization_correct_axes(self):
        model = default_model()
        self.assertAlmostEqual(sum(model.priors.values()), 1)
        for s in STATES:
            self.assertAlmostEqual(sum(v[s] for v in model.stage_likelihoods.values()), 1)
            for a in model.actions:
                self.assertAlmostEqual(sum(v[s] for v in a.outcomes.values()), 1)
        self.assertEqual(len(model.provenance["outcome_corrections"]), 2)

    def test_model_is_deeply_immutable(self):
        model = default_model()
        with self.assertRaises(TypeError):
            model.stage_likelihoods["Build"]["Code"] = 0.9
        with self.assertRaises(TypeError):
            model.actions[0].outcomes["signal"]["Code"] = 0.9

    def test_invalid_cost_and_missing_model_rejected(self):
        action = two_state_model().actions[0]
        for cost in (0, -1, float("nan"), float("inf")):
            with self.subTest(cost=cost), self.assertRaises(ValidationError):
                replace(action, cost=cost)
        with self.assertRaises(ValidationError):
            replace(action, outcomes={})

    def test_aliases_accept_all_original_catalogue_names(self):
        from ci_diagnosis.parameters import RAW_ACTIONS

        for action, raw in zip(default_model().actions, RAW_ACTIONS, strict=False):
            for index, label in enumerate(raw["outcomes"]):
                self.assertEqual(action.canonical_outcome(label), ("signal", "no_signal")[index])

    def test_ties_follow_catalogue_order(self):
        model = two_state_model()
        for policy in ("eig_per_cost", "lowest_cost"):
            self.assertEqual(rank_actions(model.priors, model.actions, policy)[0]["action_id"], "a0")

    def test_missing_stage_is_neutral_and_invalid_stage_rejected(self):
        model = default_model()
        self.assertEqual(model.initial_belief("Unknown"), dict(model.priors))
        self.assertEqual(model.initial_belief("Ambiguous"), dict(model.priors))
        with self.assertRaises(ValidationError):
            model.initial_belief("bad stage")
