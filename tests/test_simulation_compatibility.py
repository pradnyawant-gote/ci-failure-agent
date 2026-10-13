import importlib.util
import math
import unittest
from dataclasses import replace
from pathlib import Path

from ci_diagnosis.model import default_model
from ci_diagnosis.records import PublicCase, plain, fingerprint
from ci_diagnosis.runner import diagnose
from ci_diagnosis.simulation import OutcomeBank, Scenario
from ci_diagnosis.probability import ValidationError
from ci_diagnosis.legacy import (read_notebook, NOTEBOOK_SHA256, literal_parameters, reconcile_saved_traces,
                                original_unit_checks)
from tests.helpers import two_state_model


HAS_WORKBOOK_DEPS = importlib.util.find_spec("pandas") is not None and importlib.util.find_spec("openpyxl") is not None


class SimulationTests(unittest.TestCase):
    def setUp(self):
        self.model=default_model()

    def test_bank_reproducible_and_order_independent(self):
        truths={"one":"Code","two":"Test"}
        a=OutcomeBank(self.model,truths,42)
        b=OutcomeBank(self.model,dict(reversed(list(truths.items()))),42)
        self.assertEqual(a.manifest(),b.manifest())
        for action in reversed(self.model.actions):
            self.assertEqual(a.observe("one",action.action_id),b.observe("one",action.action_id))

    def test_different_seeds_have_separate_bank_identity(self):
        truths={str(i):"Code" for i in range(30)}
        self.assertNotEqual(OutcomeBank(self.model,truths,42).manifest()["bank_hash"],
                            OutcomeBank(self.model,truths,43).manifest()["bank_hash"])

    def test_common_outcomes_reused_across_policies(self):
        bank=OutcomeBank(self.model,{"one":"Code"},42)
        a=diagnose(PublicCase("one","Build"),self.model,bank)
        b=diagnose(PublicCase("one","Build"),self.model,bank,"lowest_cost")
        aa={r.action_id:r.outcome for r in a.actions_taken}
        bb={r.action_id:r.outcome for r in b.actions_taken}
        self.assertTrue(set(aa)&set(bb))
        self.assertTrue(all(aa[k]==bb[k] for k in set(aa)&set(bb)))

    def test_policy_order_does_not_change_diagnoses(self):
        bank=OutcomeBank(self.model,{"one":"Code"},42)
        case=PublicCase("one","Build")
        a=plain(diagnose(case,self.model,bank))
        diagnose(case,self.model,bank,"lowest_cost")
        self.assertEqual(a,plain(diagnose(case,self.model,bank)))

    def test_static_retry_reuses_evidence(self):
        bank=OutcomeBank(self.model,{"one":"Code"},42)
        a,b=bank.observe("one","recent_changes",0),bank.observe("one","recent_changes",1)
        self.assertEqual(a.outcome,b.outcome)
        self.assertEqual(a.evidence_id,b.evidence_id)
        self.assertNotEqual(a.event_id,b.event_id)

    def test_declared_unreliable_scenarios_have_no_evidence_update(self):
        bank=OutcomeBank(self.model,{"one":"Code"},scenario=Scenario("all_missing",missing_rate=1))
        result=diagnose(PublicCase("one","Build"),self.model,bank)
        self.assertEqual(result.decision,"ESCALATE")
        self.assertEqual(result.final_belief,self.model.initial_belief("Build"))
        self.assertTrue(all(not r.applied for r in result.actions_taken))

    def test_synthetic_multifault_is_environment_only(self):
        bank=OutcomeBank(self.model,{"one":("Code","Dependency")},42)
        self.assertEqual(bank.observe("one","pipeline_logs").status,"signal")
        result=diagnose(PublicCase("one","Build",False),self.model,bank)
        self.assertEqual(result.reason,"unsupported_scope")

    def test_invalid_scenarios(self):
        for kwargs in ({"noise":-1},{"correlation":1.1},{"signal_bias":float("nan")},
                       {"missing_rate":.6,"error_rate":.6}):
            with self.subTest(kwargs=kwargs),self.assertRaises(ValidationError):
                Scenario(**kwargs)


class NotebookTests(unittest.TestCase):
    def test_original_artifact_and_parameter_provenance(self):
        self.assertEqual(read_notebook()[1],NOTEBOOK_SHA256)
        from ci_diagnosis.parameters import RAW_PRIORS,RAW_STAGE_LIKELIHOODS,RAW_ACTIONS,RAW_OUTCOMES
        self.assertEqual(literal_parameters(),{"priors":RAW_PRIORS,"likelihoods":RAW_STAGE_LIKELIHOODS,
                                               "actions":RAW_ACTIONS,"outcome_models":RAW_OUTCOMES})

    def test_historical_saved_counts_not_new_results(self):
        r=reconcile_saved_traces()
        self.assertEqual(r["policies"]["historical_eig"]["correct_reports"],22)
        self.assertEqual(r["policies"]["historical_lowest_cost"]["correct_reports"],21)
        self.assertEqual(r["policies"]["historical_eig"]["wrong_reports"],3)
        self.assertIn("not reproduced",r["status"])

    @unittest.skipUnless(HAS_WORKBOOK_DEPS,"pandas/openpyxl needed for notebook compatibility")
    def test_original_checks_still_pass(self):
        self.assertEqual(original_unit_checks()["passed"],8)

    @unittest.skipUnless(HAS_WORKBOOK_DEPS,"pandas/openpyxl needed for notebook compatibility")
    def test_all_cells_via_python_bridge_without_notebook_changes(self):
        from ci_diagnosis.compatibility import execute_notebook_compatibility
        result=execute_notebook_compatibility()
        self.assertEqual(result["code_cells_executed"],13)
        self.assertEqual(result["original_unit_checks_passed"],8)
        self.assertEqual(read_notebook()[1],NOTEBOOK_SHA256)
        self.assertIn("still fails",result["unassisted_run_all"])

    def test_trace_display_does_not_corrupt_corrected_stage_function(self):
        from ci_diagnosis.compatibility import install_definitions
        env={};install_definitions(env)
        before=env["calculate_posterior"]("Build")
        env["likelihoods"]={"Code":.1,"Test":.2,"Dependency":.3,"CI/Config":.4}
        self.assertEqual(before,env["calculate_posterior"]("Build"))

    def test_compatibility_manual_driver_checks_final_outcome(self):
        from ci_diagnosis.compatibility import install_definitions
        env={};install_definitions(env)
        result=env["run_diagnosis"]("Build",["No relevant change found","Dependency-related change found"])
        self.assertEqual(result["decision"],"REPORT")
        self.assertEqual(result["root_cause"],"Dependency")

    def test_compatibility_ranking_respects_supplied_costs(self):
        from ci_diagnosis.compatibility import install_definitions
        env={};install_definitions(env)
        candidate={**env["actions"][0],"cost":100}
        ranked,_=env["rank_actions"](env["calculate_posterior"]("Build"),[candidate],env["outcome_models"])
        self.assertEqual(ranked[0]["cost"],100)
        with self.assertRaises(ValidationError):
            env["rank_actions"](env["calculate_posterior"]("Build"),[{**candidate,"cost":0}],env["outcome_models"])


@unittest.skipUnless(HAS_WORKBOOK_DEPS,"pandas/openpyxl needed for workbook integration")
class WorkbookIntegrationTests(unittest.TestCase):
    def test_workbook_split_and_small_reproducible_cohort(self):
        from ci_diagnosis.data import load_workbook,grouped_split
        from ci_diagnosis.evaluation import DEFAULT_WORKBOOK,cohort_run
        from ci_diagnosis.model import fit_stage_model
        rows,manifest=load_workbook(DEFAULT_WORKBOOK)
        train,validation,test=grouped_split(rows)
        self.assertEqual((manifest["source_count"],manifest["mapped_count"],manifest["excluded_count"]),(375,309,66))
        model=fit_stage_model(train)
        self.assertFalse(set(model.provenance["training_ids"]) & {r.source_id for r in validation+test})
        a=cohort_run(test[:4],model,Scenario(),42)
        b=cohort_run(list(reversed(test[:4])),model,Scenario(),42)
        for policy in a["records"]:
            self.assertEqual({r["case_id"]:r for r in a["records"][policy]}, {r["case_id"]:r for r in b["records"][policy]})
        self.assertEqual(a["bank"],b["bank"])

