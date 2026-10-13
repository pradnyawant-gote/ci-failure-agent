import math
import unittest

from ci_diagnosis.data import SourceRow, grouped_split, normalize_stage
from ci_diagnosis.metrics import calculate_metrics, paired_difference, scored_record, verify_record_hash
from ci_diagnosis.model import STAGES, STATES, fit_stage_model
from ci_diagnosis.probability import ValidationError
from tests.helpers import terminal, two_state_model


class DataTests(unittest.TestCase):
    def test_missing_stages(self):
        for value in (None, float("nan"), "", "  ", "None"):
            with self.subTest(value=value):
                self.assertEqual(normalize_stage(value), "Unknown")

    def test_stage_fixtures(self):
        expected = {
            "build with Maven skipTests": "Build",
            "contest build": "Build",
            "deploy to production": "Deploy / Publish",
            "install dependencies": "Setup / Dependency",
            "Run pytest": "Test",
            "lint": "Quality / Analysis",
            "build and test": "Ambiguous",
            "Build and sonar analyze": "Ambiguous",
            "nondescript operation": "Ambiguous",
        }
        for value, stage in expected.items():
            with self.subTest(value=value):
                self.assertEqual(normalize_stage(value), stage)
        for stage in STAGES:
            self.assertEqual(normalize_stage(stage), stage)

    def test_invalid_stage_type(self):
        with self.assertRaises(ValidationError):
            normalize_stage({"test": True})

    def test_grouped_split_disjoint_and_order_independent(self):
        rows = [
            SourceRow(str(i), "project" + str(i // 2), STATES[i % 4], "Build", "build") for i in range(20)
        ]
        parts = grouped_split(rows, seed=3)
        groups = [{r.project for r in p} for p in parts]
        self.assertFalse(groups[0] & groups[1] or groups[0] & groups[2] or groups[1] & groups[2])
        self.assertEqual(parts, grouped_split(list(reversed(rows)), seed=3))
        self.assertEqual(sum(map(len, parts)), len(rows))

    def test_training_only_smoothing(self):
        train = [
            SourceRow("one", "train", "Code", "Build", "build"),
            SourceRow("two", "train", "Code", "Test", "test"),
        ]
        fitted = fit_stage_model(train, two_state_model())
        self.assertAlmostEqual(fitted.priors["Code"], 3 / 6)
        self.assertAlmostEqual(fitted.priors["Test"], 1 / 6)
        self.assertAlmostEqual(fitted.stage_likelihoods["Build"]["Code"], 2 / 9)
        self.assertEqual(set(fitted.provenance["training_ids"]), {"one", "two"})
        for state in STATES:
            self.assertGreater(fitted.priors[state], 0)
            self.assertTrue(all(fitted.stage_likelihoods[z][state] > 0 for z in STAGES))

    def test_empty_duplicate_training_and_tiny_split_rejected(self):
        row = SourceRow("one", "project", "Code", "Build", "build")
        for rows in ([], [row, row]):
            with self.subTest(rows=rows), self.assertRaises(ValidationError):
                fit_stage_model(rows)
        with self.assertRaises(ValidationError):
            grouped_split([row])


class MetricTests(unittest.TestCase):
    def setUp(self):
        self.records = [
            scored_record(
                terminal("one", dict(zip(STATES, (0.8, 0.2, 0.0, 0.0), strict=False)), cost=1), "Code"
            ),
            scored_record(
                terminal("two", dict(zip(STATES, (0.7, 0.3, 0.0, 0.0), strict=False)), cost=2), "Test"
            ),
            scored_record(
                terminal("three", dict(zip(STATES, (0.1, 0.1, 0.7, 0.1), strict=False)), "ESCALATE", None, 3),
                "Dependency",
            ),
        ]

    def test_hand_counted_selective_and_class_metrics(self):
        m = calculate_metrics(self.records)
        self.assertEqual(m["reports"], 2)
        self.assertEqual(m["correct_reports"], 1)
        self.assertAlmostEqual(m["coverage"], 2 / 3)
        self.assertEqual(m["selective_accuracy"], 0.5)
        self.assertAlmostEqual(m["balanced_accuracy"], 1 / 3)
        self.assertIsNone(m["recall"]["CI/Config"])
        self.assertEqual(m["confusion"]["Dependency"]["ESCALATE"], 1)

    def test_brier_log_loss_and_cost_hand_calculation(self):
        m = calculate_metrics(self.records)
        self.assertAlmostEqual(m["brier"], (0.08 + 0.98 + 0.12) / 3)
        self.assertAlmostEqual(m["log_loss"], (-math.log(0.8) - math.log(0.3) - math.log(0.7)) / 3)
        self.assertAlmostEqual(m["average_total_decision_cost"], (1 + 27 + 15) / 3)
        self.assertEqual(m["average_diagnostic_cost"], 2)

    def test_empty_and_no_reports_are_undefined(self):
        empty = calculate_metrics([])
        self.assertIsNone(empty["coverage"])
        self.assertIsNone(empty["log_loss"])
        referrals = calculate_metrics([self.records[-1]])
        self.assertIsNone(referrals["selective_accuracy"])
        self.assertEqual(referrals["selective_accuracy_status"], "undefined_no_reports")

    def test_zero_true_probability_explicit_infinite_loss(self):
        r = scored_record(terminal("zero", dict(zip(STATES, (1.0, 0.0, 0.0, 0.0), strict=False))), "Test")
        m = calculate_metrics([r])
        self.assertTrue(math.isinf(m["log_loss"]))
        self.assertEqual(m["zero_true_probability_cases"], 1)

    def test_record_integrity(self):
        self.assertTrue(verify_record_hash(self.records[0]))
        altered = {**self.records[0], "diagnostic_cost": 100}
        self.assertFalse(verify_record_hash(altered))
        with self.assertRaises(ValidationError):
            calculate_metrics([altered])

    def test_join_by_case_id_not_position(self):
        a = paired_difference(self.records, list(reversed(self.records)), repetitions=50)
        self.assertEqual(a["mean_difference"], 0)
        self.assertEqual(a["interval95"], [0, 0])
        with self.assertRaises(ValidationError):
            paired_difference(self.records, self.records[:-1])
        with self.assertRaises(ValidationError):
            paired_difference(self.records, self.records + [self.records[0]])

    def test_clustered_interval_reproducible(self):
        clusters = {"one": "repo1", "two": "repo1", "three": "repo2"}
        a = paired_difference(self.records, self.records, repetitions=20, clusters=clusters)
        self.assertEqual(a, paired_difference(self.records, self.records, repetitions=20, clusters=clusters))
        self.assertEqual(a["resampling"], "repository clusters")
