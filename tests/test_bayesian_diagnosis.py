import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.bayesian_diagnosis import SOURCE_DATE_MISSING, build_bayesian_diagnosis_packet


class BayesianDiagnosisTest(unittest.TestCase):
    def _base_inputs(self):
        target = {"name": "豫能控股", "code": "001896", "sector": "电力", "source_date": "2026-06-04"}
        return {
            "target_date": "2026-06-04",
            "data": {
                "target_date": "2026-06-04",
                "market_branch": "修复但分歧仍在",
                "source_date": "2026-06-04",
            },
            "market_research_snapshot": {
                "target_date": "2026-06-04",
                "source_date": "2026-06-04",
                "cycle_layer": {"cycle_mainline": "电力", "daily_attack_line": "电力", "source_date": "2026-06-04"},
                "capital_intent": {"summary": "资金未否定电力方向", "source_date": "2026-06-04"},
            },
            "final_target_resolution": {
                "display_target": target,
                "new_entry_target": target,
                "capital_priority_decision": {"capital_priority": "new_entry", "reason": "新开仓对象具备执行资格"},
                "source_date": "2026-06-04",
            },
            "position_decision": {
                "target_position_pct": 100,
                "final_action": "已决定100%核心进攻；跌破失效价取消",
                "source_date": "2026-06-04",
            },
        }

    def test_path_consistent_for_core_attack(self):
        packet = build_bayesian_diagnosis_packet(**self._base_inputs())

        self.assertEqual(packet["schema_version"], "bayesian_diagnosis.v1")
        self.assertEqual(packet["conclusion"]["path_conclusion"], "路径一致")
        self.assertEqual(packet["conclusion"]["execution_object"]["code"], "001896")
        self.assertEqual(packet["conclusion"]["position_pct"], 100)
        self.assertEqual(packet["conclusion"]["final_action_alignment"], "一致")
        self.assertNotIn("diagnosis_label", packet["conclusion"])
        self.assertNotIn("confidence", packet["conclusion"])
        self.assertEqual([step["layer"] for step in packet["path"]], list(packet["path_layers"]))

    def test_conditional_execution_keeps_fallback_to_zero(self):
        inputs = self._base_inputs()
        inputs["position_decision"] = {
            "target_position_pct": 50,
            "source_date": "2026-06-04",
        }

        packet = build_bayesian_diagnosis_packet(**inputs)

        self.assertEqual(packet["conclusion"]["path_conclusion"], "条件执行")
        self.assertEqual(packet["conclusion"]["position_pct"], 50)
        self.assertIn("1x/50%半仓条件执行", packet["conclusion"]["action_text"])
        self.assertIn("回到0%不参与", packet["conclusion"]["action_text"])

    def test_source_date_missing_is_preserved(self):
        inputs = self._base_inputs()
        inputs["data"].pop("source_date")
        inputs["market_research_snapshot"].pop("source_date")
        inputs["market_research_snapshot"]["cycle_layer"].pop("source_date")
        inputs["market_research_snapshot"]["capital_intent"].pop("source_date")
        inputs["final_target_resolution"].pop("source_date")
        inputs["final_target_resolution"]["display_target"].pop("source_date", None)
        inputs["final_target_resolution"]["new_entry_target"].pop("source_date", None)
        inputs["position_decision"].pop("source_date", None)

        packet = build_bayesian_diagnosis_packet(**inputs)

        self.assertIn(SOURCE_DATE_MISSING, {step["source_date"] for step in packet["path"]})
        self.assertEqual(packet["conclusion"]["path_conclusion"], "路径不完整，条件待确认")

    def test_postgres_only_frozen_facts_use_target_date_when_source_date_missing(self):
        inputs = self._base_inputs()
        inputs["data"].pop("source_date")
        inputs["data"]["postgres_only"] = True
        inputs["market_research_snapshot"].pop("source_date")
        inputs["market_research_snapshot"]["cycle_layer"].pop("source_date")
        inputs["market_research_snapshot"]["capital_intent"].pop("source_date")
        inputs["final_target_resolution"].pop("source_date")
        inputs["final_target_resolution"]["display_target"].pop("source_date", None)
        inputs["final_target_resolution"]["new_entry_target"].pop("source_date", None)
        inputs["position_decision"].pop("source_date", None)

        packet = build_bayesian_diagnosis_packet(**inputs)

        self.assertEqual({step["source_date"] for step in packet["path"]}, {"2026-06-04"})
        self.assertNotIn(SOURCE_DATE_MISSING, {step["source_date"] for step in packet["path"]})

    def test_zero_final_does_not_promote_observation_target(self):
        inputs = self._base_inputs()
        inputs["data"]["selection_workflow"] = {
            "schema_version": "selection_workflow.v1",
            "final": {
                "position_pct": 0,
                "execution_object": {},
                "action_text": "0%不参与",
            },
        }

        packet = build_bayesian_diagnosis_packet(**inputs)

        self.assertEqual(packet["conclusion"]["path_conclusion"], "无执行对象")
        self.assertEqual(packet["conclusion"]["position_pct"], 0)
        self.assertEqual(packet["conclusion"]["execution_object"], {})
        self.assertEqual(packet["conclusion"]["final_action_source"], "selection_workflow.final")

    def test_counter_evidence_lowers_positive_path(self):
        inputs = self._base_inputs()
        inputs["position_decision"]["counter_evidence"] = ["固定交易窗口未确认"]

        packet = build_bayesian_diagnosis_packet(**inputs)

        self.assertEqual(packet["conclusion"]["path_conclusion"], "存在反证")
        self.assertIn("固定交易窗口未确认", packet["counter_evidence"])


if __name__ == "__main__":
    unittest.main()
