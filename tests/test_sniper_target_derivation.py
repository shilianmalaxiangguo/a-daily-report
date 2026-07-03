import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.sniper_target_derivation import build_sniper_target_derivation_packet, full_section


class SniperTargetDerivationBayesianDiagnosisTest(unittest.TestCase):
    def test_bayesian_diagnosis_does_not_override_final_target(self):
        diagnosis = {
            "schema_version": "bayesian_diagnosis.v1",
            "conclusion": {
                "execution_object": {"name": "豫能控股", "code": "001896", "sector": "电力"},
                "path_conclusion": "条件执行",
                "position_pct": 50,
                "action_text": "已决定50%条件执行；盘中不满足取消，回到0%不参与",
                "final_action_alignment": "不一致",
            },
            "path": [
                {
                    "source_date": "2026-06-04",
                    "layer": "market",
                    "input_summary": "市场修复但分歧仍在",
                    "judgement": "市场未否定继续诊断",
                    "passes_forward": "进入主线层",
                    "cannot_conclude": ["市场层不能直接推出个股"],
                }
            ],
        }

        packet = build_sniper_target_derivation_packet(
            final_target_resolution={
                "display_target": {"name": "上海石化", "code": "600688", "sector": "石化"},
                "new_entry_target": {"name": "上海石化", "code": "600688", "sector": "石化"},
                "capital_priority_decision": {"capital_priority": "new_entry", "reason": "当前主链路最终对象"},
            },
            position_decision={"target_position_pct": 100, "sizing_reason": "当前主链路100%"},
            bayesian_diagnosis=diagnosis,
            target_date="2026-06-04",
        )

        self.assertEqual(packet["canonical_target"]["name"], "上海石化")
        self.assertEqual(packet["canonical_source"], "final_target_resolution.display_target")
        self.assertEqual(packet["final_action"]["position_pct"], 100)
        rendered = "\n".join(full_section(packet))
        self.assertIn("路径诊断复盘", rendered)
        self.assertIn("路径结论=条件执行", rendered)
        self.assertIn("最终动作一致性=不一致", rendered)
        self.assertIn("最终对象=上海石化(600688) 身份=执行对象", rendered)

    def test_bayesian_path_renders_when_final_action_has_no_object(self):
        diagnosis = {
            "schema_version": "bayesian_diagnosis.v1",
            "conclusion": {
                "execution_object": {},
                "path_conclusion": "无执行对象",
                "position_pct": 0,
                "action_text": "0%不参与",
                "final_action_alignment": "一致",
            },
            "path": [
                {
                    "source_date": "-",
                    "layer": "market",
                    "input_summary": "市场信息待确认",
                    "judgement": "市场层信息待确认",
                    "passes_forward": "不能单独推出参与资格",
                }
            ],
        }

        packet = build_sniper_target_derivation_packet(
            data={
                "selection_workflow": {
                    "schema_version": "selection_workflow.v1",
                    "final": {
                        "position_pct": 0,
                        "execution_object": {},
                        "action_text": "0%不参与",
                    },
                    "candidate_pool": [],
                }
            },
            bayesian_diagnosis=diagnosis,
            target_date="2026-06-04",
        )

        rendered = "\n".join(full_section(packet))

        self.assertIn("路径诊断复盘", rendered)
        self.assertIn("## 路径诊断复盘（过程证据）", rendered)
        self.assertIn("路径结论=无执行对象", rendered)
        self.assertIn("日期=来源日期缺失", rendered)
        self.assertNotIn("## 狙击手最终标的完整路径图（过程证据）", rendered)
        self.assertNotIn("最终对象=暂无", rendered)


if __name__ == "__main__":
    unittest.main()
