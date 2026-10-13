import math
import unittest
from dataclasses import replace

from ci_diagnosis.model import default_model, Action, STATES, STAGES
from ci_diagnosis.probability import (ValidationError, ImpossibleEvidence, validate_vector,
    update_belief, entropy, expected_information_gain, normalize)
from ci_diagnosis.policy import rank_actions
from tests.helpers import two_state_model


class ProbabilityTests(unittest.TestCase):
    def setUp(self):
        self.belief = dict(zip(STATES, (.5, .5, 0., 0.)))

    def test_hand_calculated_bayes_and_evidence(self):
        posterior, log_q = update_belief(self.belief, dict(zip(STATES, (.8, .2, .5, .5))))
        self.assertAlmostEqual(posterior["Code"], .8)
        self.assertAlmostEqual(posterior["Test"], .2)
        self.assertAlmostEqual(math.exp(log_q), .5)
        self.assertEqual(posterior["Dependency"], 0)

    def test_hand_calculated_eig(self):
        action = two_state_model().actions[0]
        expected = 1 + .8*math.log2(.8) + .2*math.log2(.2)
        self.assertAlmostEqual(expected_information_gain(self.belief, action.outcomes), expected)
        self.assertAlmostEqual(expected, .2780719051126377)

    def test_likelihood_scale_invariance(self):
        a, _ = update_belief(self.belief, dict.fromkeys(STATES, .5))
        b, _ = update_belief(self.belief, dict.fromkeys(STATES, .25))
        self.assertEqual(a, b)

    def test_hypothetical_impossible_branch_is_skipped(self):
        self.assertEqual(expected_information_gain(self.belief, {
            "impossible": dict.fromkeys(STATES, 0.), "certain": dict.fromkeys(STATES, 1.)}), 0)

    def test_observed_impossibility_is_explicit(self):
        with self.assertRaises(ImpossibleEvidence):
            update_belief(self.belief, dict.fromkeys(STATES, 0.))

    def test_log_space_underflow_protection(self):
        likelihood = dict.fromkeys(STATES, 5e-324)
        self.assertEqual(sum(self.belief[s]*likelihood[s] for s in STATES), 0)
        posterior, log_q = update_belief(self.belief, likelihood)
        self.assertAlmostEqual(posterior["Code"], .5)
        self.assertLess(log_q, -740)

    def test_large_weight_normalization_does_not_overflow(self):
        self.assertEqual(normalize({"a":1e308,"b":1e308}),{"a":.5,"b":.5})

    def test_invalid_belief_type_rejected(self):
        for value in (None,[],1,"belief"):
            with self.subTest(value=value),self.assertRaises(ValidationError):
                update_belief(value,dict.fromkeys(STATES,.5))

    def test_bad_values_rejected(self):
        for value in (-.1, 1.1, float("nan"), float("inf"), "0.5", True):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                update_belief(self.belief, {**dict.fromkeys(STATES, .5), "Code": value})

    def test_bad_belief_keys_and_totals_rejected(self):
        for belief in ({}, {"Code": 1}, dict.fromkeys(STATES, .95), {**self.belief, "Extra": 0}):
            with self.subTest(belief=belief), self.assertRaises(ValidationError):
                validate_vector(belief, STATES, normalized=True)

    def test_bad_conditional_sum_rejected(self):
        with self.assertRaises(ValidationError):
            expected_information_gain(self.belief, {"yes": dict.fromkeys(STATES, .6), "no": dict.fromkeys(STATES, .5)})

    def test_perfect_and_uninformative_eig(self):
        perfect = two_state_model(positive=(1, 0, .5, .5)).actions[0]
        blank = two_state_model(positive=(.5, .5, .5, .5)).actions[0]
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
            model.stage_likelihoods["Build"]["Code"] = .9
        with self.assertRaises(TypeError):
            model.actions[0].outcomes["signal"]["Code"] = .9

    def test_invalid_cost_and_missing_model_rejected(self):
        action = two_state_model().actions[0]
        for cost in (0, -1, float("nan"), float("inf")):
            with self.subTest(cost=cost), self.assertRaises(ValidationError):
                replace(action, cost=cost)
        with self.assertRaises(ValidationError):
            replace(action, outcomes={})

    def test_aliases_accept_all_original_catalogue_names(self):
        from ci_diagnosis.parameters import RAW_ACTIONS
        for action, raw in zip(default_model().actions, RAW_ACTIONS):
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

