import unittest
from dataclasses import replace

from ci_diagnosis.model import default_model, STATES
from ci_diagnosis.records import PublicCase, Observation, plain
from ci_diagnosis.runner import diagnose, Limits
from ci_diagnosis.simulation import SequenceProvider, OutcomeBank
from ci_diagnosis.probability import ValidationError
from tests.helpers import two_state_model


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.model = two_state_model()
        self.case = PublicCase("case", "Build")

    def run_case(self, items, *, limits=None, model=None, policy="eig_per_cost"):
        model = model or self.model
        return diagnose(self.case, model, SequenceProvider(items, [a.action_id for a in model.actions]), policy, limits)

    def test_report_after_final_step(self):
        result = self.run_case([("a0", "signal"), ("a1", "signal")], limits=Limits(max_steps=2, budget=2))
        self.assertEqual(result.decision, "REPORT")
        self.assertEqual(result.prediction, "Code")
        self.assertAlmostEqual(result.final_belief["Code"], 16/17)
        self.assertEqual(len(result.actions_taken), 2)

    def test_mixed_signals_keep_uncertainty(self):
        result = self.run_case([("a0", "signal"), ("a1", "no_signal")])
        self.assertEqual(result.decision, "ESCALATE")
        self.assertAlmostEqual(result.final_belief["Code"], .5)

    def test_empty_evidence_returns_explicit_referral(self):
        result = self.run_case([])
        self.assertEqual(result.decision, "ESCALATE")
        self.assertEqual(result.final_belief, dict(self.model.priors))
        self.assertTrue(all(r.status == "missing" for r in result.actions_taken))

    def test_failure_types_leave_belief_unchanged(self):
        for status in ("missing", "inconclusive", "tool_error", "timeout", "unavailable"):
            with self.subTest(status=status):
                result = self.run_case([Observation("a0", "e", status)], limits=Limits(max_steps=1))
                self.assertEqual(result.decision, "ESCALATE")
                self.assertEqual(result.final_belief, dict(self.model.priors))
                self.assertFalse(result.actions_taken[0].applied)

    def test_step_budget_attempt_limits(self):
        for limits in (Limits(max_steps=0), Limits(budget=0), Limits(budget=.99), Limits(max_attempts=0)):
            with self.subTest(limits=limits):
                result = self.run_case([("a0", "signal")], limits=limits)
                self.assertEqual(result.decision, "ESCALATE")
                self.assertEqual(result.actions_taken, ())
                self.assertEqual(result.diagnostic_cost, 0)

    def test_no_overspend_with_retries(self):
        items = [Observation("a0", "first", "tool_error"), Observation("a0", "second", "tool_error")]
        result = self.run_case(items, limits=Limits(budget=2, max_retries=5, max_attempts=2))
        self.assertEqual(result.diagnostic_cost, 2)
        self.assertEqual(len(result.actions_taken), 2)
        self.assertEqual(result.reason, "attempt_limit")
        self.assertEqual([r.attempt for r in result.actions_taken], [0, 1])

    def test_duplicate_evidence_is_not_double_counted(self):
        items = [Observation("a0", "event1", "signal", "signal", "same-artifact"),
                 Observation("a1", "event2", "signal", "signal", "same-artifact")]
        result = self.run_case(items)
        self.assertAlmostEqual(result.final_belief["Code"], .8)
        self.assertEqual(result.actions_taken[1].reason, "duplicate_evidence")
        self.assertEqual(result.diagnostic_cost, 2)

    def test_duplicate_event_is_not_double_counted(self):
        result = self.run_case([Observation("a0", "same", "signal", "signal"),
                                Observation("a1", "same", "signal", "signal")])
        self.assertAlmostEqual(result.final_belief["Code"], .8)
        self.assertEqual(result.actions_taken[1].reason, "duplicate_event")

    def test_outcome_pairing_validation(self):
        for item in (Observation("wrong", "e", "signal", "signal"),
                     Observation("a0", "e", "signal", "unknown"),
                     Observation("a0", "e", "tool_error", "no_signal"),
                     Observation("a0", "e", "signal", "signal", cost=100)):
            with self.subTest(item=item):
                result = self.run_case([item])
                self.assertEqual(result.reason, "invalid_observation_or_provider_error")
                self.assertEqual(result.final_belief, dict(self.model.priors))

    def test_zero_support_observation_refers(self):
        model = two_state_model(1)
        action = replace(model.actions[0], outcomes={
            "signal": dict(zip(STATES, (.8,.2,.25,.25))),
            "no_signal": dict(zip(STATES, (.2,.8,.25,.25))),
            "impossible": dict(zip(STATES, (0.,0.,.5,.5)))},
            labels={"signal":"Positive","no_signal":"Negative","impossible":"Impossible"})
        model = replace(model, actions=(action,))
        result = self.run_case([("a0", "impossible")], model=model)
        self.assertEqual(result.reason, "model_mismatch_zero_support")
        self.assertEqual(result.final_belief, dict(model.priors))

    def test_no_information_refers(self):
        model = two_state_model(2, positive=(.5,.5,.5,.5))
        self.assertEqual(self.run_case([], model=model).reason, "no_informative_actions")

    def test_unavailable_tools_and_permissions(self):
        bank = OutcomeBank(self.model, {"case": "Code"}, unavailable=("a0", "a1"))
        result = diagnose(self.case, self.model, bank)
        self.assertEqual(result.reason, "no_feasible_actions")
        result = self.run_case([], limits=Limits(allowed_actions=frozenset()))
        self.assertEqual(result.reason, "no_feasible_actions")

    def test_availability_exception_is_safe(self):
        class Broken:
            def available(self, action_id):
                raise RuntimeError("tool registry offline")
        result = diagnose(self.case, self.model, Broken())
        self.assertEqual(result.decision, "ESCALATE")
        self.assertTrue(all(v == "provider_availability_error" for v in result.candidate_trace[-1]["rejected"].values()))

    def test_late_signal_is_timeout_and_not_evidence(self):
        result = self.run_case([Observation("a0", "e", "signal", "signal", elapsed_seconds=31)])
        self.assertEqual(result.reason, "deadline_exhausted")
        self.assertEqual(result.final_belief, dict(self.model.priors))
        self.assertEqual(result.actions_taken[0].status, "timeout")

    def test_scope_and_calibration_referrals(self):
        bank = OutcomeBank(self.model, {"case": "Code"})
        result = diagnose(replace(self.case, supported_scope=False), self.model, bank)
        self.assertEqual(result.reason, "unsupported_scope")
        result = self.run_case([("a0","signal"),("a1","signal")], limits=Limits(allow_uncalibrated=False))
        self.assertEqual(result.reason, "empirical_calibration_unavailable")

    def test_threshold_boundary(self):
        for threshold, expected in ((.8,"REPORT"),(.800001,"ESCALATE")):
            result = self.run_case([("a0","signal")], model=two_state_model(1), limits=Limits(confidence_threshold=threshold))
            self.assertEqual(result.decision, expected)

    def test_known_last_observation_regression(self):
        model = default_model()
        result = diagnose(PublicCase("regression","Build"), model,
            SequenceProvider([("recent_changes","no_signal"),("dependency_changes","signal")],
                             [a.action_id for a in model.actions]))
        self.assertEqual(result.decision, "REPORT")
        self.assertEqual(result.prediction, "Dependency")
        self.assertGreater(result.confidence,.99)

    def test_invalid_limits(self):
        for kwargs in ({"budget":-1},{"max_steps":-1},{"max_retries":True},{"confidence_threshold":1.1},
                       {"max_seconds":float("nan")},{"max_attempts":1.5}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValidationError):
                Limits(**kwargs)

    def test_impossible_initial_stage_refers_without_fabricated_belief(self):
        stages={z:dict.fromkeys(STATES,0.0 if z=="Build" else 1/6) for z in self.model.stage_likelihoods}
        model=replace(self.model,stage_likelihoods=stages)
        result=self.run_case([],model=model)
        self.assertEqual(result.reason,"stage_model_mismatch_zero_support")
        self.assertEqual(result.final_belief,dict(model.priors))

    def test_truth_fields_not_allowed_in_public_case(self):
        with self.assertRaises(TypeError):
            PublicCase("case","Build", true_state="Code")

