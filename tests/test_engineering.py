"""New regressions for the engineering audit, using independent failure probes."""

import importlib.util
import io
import logging
import subprocess
import sys
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from ci_diagnosis.decision_cost import DecisionCosts
from ci_diagnosis.metrics import calculate_metrics, scored_record
from ci_diagnosis.model import STATES, default_model, fit_stage_model
from ci_diagnosis.observability import LOGGER, JsonFormatter
from ci_diagnosis.probability import ValidationError, finite_number
from ci_diagnosis.records import Observation, PublicCase, fingerprint, plain
from ci_diagnosis.runner import Limits, diagnose
from ci_diagnosis.simulation import OutcomeBank
from tests.helpers import terminal, two_state_model


class AdmissionAndPrivacyTests(unittest.TestCase):
    def setUp(self):
        self.model = two_state_model()
        self.case = PublicCase("audit", "Build")

    def test_no_provider_discovery_without_permissions(self):
        class Probe:
            def __init__(self):
                self.calls = []

            def available(self, action_id):
                self.calls.append(action_id)
                return True

            def observe(self, *args):
                raise AssertionError("forbidden observation")

        p = Probe()
        result = diagnose(self.case, self.model, p, limits=Limits(allowed_actions=frozenset()))
        self.assertEqual(p.calls, [])
        self.assertEqual(result.decision, "ESCALATE")

    def test_no_observe_after_availability_exhausts_deadline(self):
        class Probe:
            now = 0
            calls = 0

            def available(self, action_id):
                self.now += 1
                return True

            def observe(self, *args):
                self.calls += 1
                raise AssertionError("late observation")

        p = Probe()
        result = diagnose(self.case, self.model, p, limits=Limits(max_seconds=1), clock=lambda: p.now)
        self.assertEqual(result.reason, "deadline_exhausted")
        self.assertEqual(p.calls, 0)

    def test_secret_canaries_absent_from_trace_and_structured_log(self):
        class Probe:
            def available(self, action_id):
                return True

            def observe(self, *args):
                raise RuntimeError("token=SYNTHETIC_SECRET password=SYNTHETIC_PASSWORD")

        output = io.StringIO()
        handler = logging.StreamHandler(output)
        handler.setFormatter(JsonFormatter())
        old = LOGGER.level
        LOGGER.setLevel(logging.INFO)
        LOGGER.addHandler(handler)
        try:
            result = diagnose(self.case, self.model, Probe())
        finally:
            LOGGER.removeHandler(handler)
            LOGGER.setLevel(old)
        text = repr(plain(result)) + output.getvalue()
        self.assertNotIn("SYNTHETIC_SECRET", text)
        self.assertNotIn("SYNTHETIC_PASSWORD", text)
        self.assertIn("provider_exception", output.getvalue())
        self.assertIn("RuntimeError", output.getvalue())

    def test_provider_detail_is_redacted(self):
        class Probe:
            def available(self, action_id):
                return True

            def observe(self, case, action, attempt, timeout):
                return Observation(action, "evt", "missing", cost=0, detail="token=SYNTHETIC_SECRET")

        result = diagnose(self.case, self.model, Probe(), limits=Limits(max_steps=1))
        self.assertNotIn("SYNTHETIC_SECRET", repr(plain(result)))

    def test_forced_baseline_requires_explicit_benchmark_purpose(self):
        bank = OutcomeBank(self.model, {"audit": "Code"})
        with self.assertRaises(ValidationError):
            diagnose(self.case, self.model, bank, "fixed_test", Limits(allow_uncalibrated=False))
        result = diagnose(self.case, self.model, bank, "fixed_test", Limits(benchmark_mode=True))
        self.assertTrue(result.benchmark)


class IntegrityAndCostTests(unittest.TestCase):
    def test_terminal_and_nested_trace_are_immutable(self):
        from ci_diagnosis.simulation import SequenceProvider

        model = two_state_model()
        r = diagnose(
            PublicCase("immutable", "Build"),
            model,
            SequenceProvider([("a0", "signal"), ("a1", "signal")], ("a0", "a1")),
        )
        with self.assertRaises(TypeError):
            r.final_belief["Code"] = 0
        with self.assertRaises(TypeError):
            r.actions_taken[0].posterior_before["Code"] = 0
        with self.assertRaises(TypeError):
            r.candidate_trace[0]["ranking"][0]["score"] = 100

    def test_rehashed_semantic_cost_corruption_rejected(self):
        r = scored_record(
            terminal("cost", dict(zip(STATES, (0.8, 0.2, 0.0, 0.0), strict=False)), cost=1), "Code"
        )
        r["total_decision_cost"] = 0
        r["record_hash"] = fingerprint({k: v for k, v in r.items() if k != "record_hash"})
        with self.assertRaises(ValidationError):
            calculate_metrics([r])

    def test_mapping_key_collision_rejected(self):
        with self.assertRaises(ValidationError):
            fingerprint({1: "one", "1": "another"})

    def test_invalid_label_detail_and_status_are_explicit_validation_errors(self):
        model = two_state_model()
        with self.assertRaises(ValidationError):
            replace(model.actions[0], labels={"signal": {"bad": "object"}, "no_signal": "Negative"})
        for event in (
            Observation("a0", "event", "signal", "signal", detail=[]),
            Observation("a0", "event", [], None),
        ):
            with self.assertRaises(ValidationError):
                event.validate(model.actions[0])

    def test_duplicate_faults_and_mutable_seed_refused(self):
        model = two_state_model()
        with self.assertRaises(ValidationError):
            OutcomeBank(model, {"case": ("Code", "Code")})
        bank = OutcomeBank(model, {"case": "Code"})
        with self.assertRaises(AttributeError):
            bank.seed = 99
        with self.assertRaises(ValidationError):
            bank.observe("case", "a0", -1)
        with self.assertRaises(ValidationError):
            bank.materialize(0)

    def test_large_finite_means_and_medians_do_not_overflow(self):
        records = [
            scored_record(
                terminal(str(i), dict(zip(STATES, (1.0, 0.0, 0.0, 0.0), strict=False)), cost=1e308), "Code"
            )
            for i in range(2)
        ]
        m = calculate_metrics(records)
        self.assertEqual(m["average_diagnostic_cost"], 1e308)
        self.assertEqual(m["median_diagnostic_cost"], 1e308)

    def test_integer_beyond_float_range_is_validation_error(self):
        with self.assertRaises(ValidationError):
            finite_number(10**1000, "value")

    def test_large_smoothing_is_valid_uniform_limit(self):
        from ci_diagnosis.data import SourceRow

        model = fit_stage_model([SourceRow("one", "repo", "Code", "Build", "build")], alpha=1e308, beta=1e308)
        for s in STATES:
            self.assertAlmostEqual(model.priors[s], 0.25)
            self.assertAlmostEqual(model.stage_likelihoods["Build"][s], 1 / 7)


class RiskMathTests(unittest.TestCase):
    def test_independent_symmetric_risk_reduction(self):
        model = two_state_model()
        costs = DecisionCosts(dict.fromkeys(STATES, 1.0), 0.4)
        self.assertEqual(costs.minimum_report_risk(model.priors), 0.5)
        self.assertAlmostEqual(costs.expected_reduction(model.priors, model.actions[0].outcomes), 0.3)

    def test_asymmetric_minimum_risk_report_and_impossible_branch(self):
        belief = dict(zip(STATES, (0.6, 0.4, 0.0, 0.0), strict=False))
        costs = DecisionCosts({"Code": 1.0, "Test": 10.0, "Dependency": 1.0, "CI/Config": 1.0})
        self.assertAlmostEqual(costs.report_risk(belief, "Code"), 4.0)
        self.assertAlmostEqual(costs.report_risk(belief, "Test"), 0.6)
        outcomes = {"never": dict.fromkeys(STATES, 0.0), "always": dict.fromkeys(STATES, 1.0)}
        self.assertAlmostEqual(costs.expected_reduction(belief, outcomes), 0)

    def test_experimental_risk_policy_still_learns_useful_sequence(self):
        from ci_diagnosis.simulation import SequenceProvider

        model = two_state_model()
        r = diagnose(
            PublicCase("risk", "Build"),
            model,
            SequenceProvider([("a0", "signal"), ("a1", "signal")], ("a0", "a1")),
            "risk_per_cost",
        )
        self.assertEqual(r.prediction, "Code")
        self.assertAlmostEqual(r.confidence, 16 / 17)


class IsolatedNotebookTests(unittest.TestCase):
    @unittest.skipUnless(
        importlib.util.find_spec("pandas") and importlib.util.find_spec("openpyxl"),
        "workbook dependencies required",
    )
    def test_full_controlled_reference_preserves_raw_negative_scores(self):
        from ci_diagnosis.data import load_workbook
        from ci_diagnosis.evaluation import DEFAULT_WORKBOOK, controlled_legacy_comparison

        rows, _ = load_workbook(DEFAULT_WORKBOOK)
        result = controlled_legacy_comparison(rows, default_model())
        reference = result["records"]["legacy_reference_eig_per_cost"]
        self.assertEqual(len(reference), 40)
        actions = [a for r in reference for a in r["actions_taken"]]
        self.assertTrue(any(a["source_eig"] is not None and a["source_eig"] < 0 for a in actions))
        self.assertTrue(all(a["eig"] >= 0 for a in actions))

    def test_untrusted_digest_refused_before_subprocess(self):
        from ci_diagnosis.notebook_worker import execute_worker

        with (
            patch("ci_diagnosis.legacy.read_notebook", return_value=({}, "0" * 64)),
            patch("subprocess.run") as run,
        ):
            with self.assertRaises(ValidationError):
                execute_worker(Path("untrusted.py"), "unit")
            run.assert_not_called()

    def test_timeout_is_explicit(self):
        from ci_diagnosis.legacy import DEFAULT_NOTEBOOK
        from ci_diagnosis.notebook_worker import execute_worker

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("worker", 1)):
            with self.assertRaisesRegex(ValidationError, "terminated"):
                execute_worker(DEFAULT_NOTEBOOK, "unit")

    @unittest.skipUnless(
        importlib.util.find_spec("pandas") and importlib.util.find_spec("openpyxl"),
        "workbook dependencies required",
    )
    def test_parent_cwd_and_stdout_unchanged(self):
        from ci_diagnosis.compatibility import execute_notebook_compatibility

        before = Path.cwd()
        output = sys.stdout
        result = execute_notebook_compatibility()
        self.assertEqual(Path.cwd(), before)
        self.assertIs(sys.stdout, output)
        self.assertEqual(result["code_cells_executed"], 13)
