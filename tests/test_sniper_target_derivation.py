import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.execution_wording import PREMARKET_50_EXECUTION_TEXT, PREMARKET_FULL_EXECUTION_TEXT
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

    def test_same_stock_t_keeps_final_action_zero_when_position_decision_is_zero(self):
        packet = build_sniper_target_derivation_packet(
            final_target_resolution={
                "display_target": {"name": "太极实业", "code": "600667", "sector": "半导体"},
                "new_entry_target": {"name": "太极实业", "code": "600667", "sector": "半导体"},
                "existing_position_target": {"name": "太极实业", "code": "600667", "sector": "半导体"},
                "capital_priority_decision": {
                    "capital_priority": "same_stock_t",
                    "reason": "已有同股旧仓，目标仍是太极实业",
                },
            },
            position_decision={"target_position_pct": 0},
            target_date="2026-07-06",
        )

        self.assertEqual(packet["canonical_target"]["code"], "600667")
        self.assertEqual(packet["final_action"]["position_pct"], 0)
        self.assertEqual(packet["final_action"]["action"], "只观察，不新增参与")

    def test_two_layer_object_requires_valid_structured_position_tier(self):
        target = {"name": "太极实业", "code": "600667", "sector": "半导体"}
        invalid_front_decisions = (
            {
                "execution_identity": "明日执行对象",
                "position_plan": "33%条件执行",
                "position_pct": 33,
            },
            {
                "execution_identity": "明日执行对象",
                "position_plan": "75%条件执行",
                "position_pct": 75,
            },
            {
                "execution_identity": "明日执行对象",
                "position_plan": "50%条件执行",
            },
        )
        for front_decision in invalid_front_decisions:
            with self.subTest(front_decision=front_decision):
                packet = build_sniper_target_derivation_packet(
                    final_target_resolution={
                        "capital_priority_decision": {
                            "capital_priority": "wait",
                        },
                    },
                    position_decision={"target_position_pct": 0},
                    two_layer_decision_payload={
                        "front_decision": {
                            **front_decision,
                            "execution_object": target,
                        },
                    },
                    target_date="2026-07-19",
                )

                self.assertEqual(packet["canonical_target"], {})
                self.assertEqual(packet["canonical_role"], "观察对象")
                self.assertEqual(packet["final_action"]["position_pct"], 0)
                self.assertNotEqual(
                    packet["canonical_source"],
                    "two_layer_decision_payload.front_decision.execution_object",
                )

    def test_two_layer_object_propagates_valid_structured_position_tier(self):
        target = {"name": "太极实业", "code": "600667", "sector": "半导体"}
        for position_pct, expected_action in (
            (50, PREMARKET_50_EXECUTION_TEXT),
            (100, PREMARKET_FULL_EXECUTION_TEXT),
        ):
            with self.subTest(position_pct=position_pct):
                packet = build_sniper_target_derivation_packet(
                    final_target_resolution={
                        "capital_priority_decision": {
                            "capital_priority": "wait",
                        },
                    },
                    position_decision={"target_position_pct": 0},
                    two_layer_decision_payload={
                        "front_decision": {
                            "execution_identity": "明日执行对象",
                            "execution_object": target,
                            "position_pct": position_pct,
                        },
                    },
                    target_date="2026-07-19",
                )

                self.assertEqual(packet["canonical_target"]["code"], "600667")
                self.assertEqual(packet["canonical_role"], "执行对象")
                self.assertEqual(packet["final_action"]["position_pct"], position_pct)
                self.assertEqual(packet["final_action"]["action"], expected_action)

    def test_selection_workflow_rejects_non_tier_final_position(self):
        target = {"name": "太极实业", "code": "600667", "sector": "半导体"}
        for position_pct in (33, 75, None):
            with self.subTest(position_pct=position_pct):
                packet = build_sniper_target_derivation_packet(
                    data={
                        "selection_workflow": {
                            "schema_version": "selection_workflow.v1",
                            "final": {
                                "execution_object": target,
                                "position_pct": position_pct,
                                "action_text": "旧文案不能替代结构化仓位",
                            },
                            "candidate_pool": [],
                        },
                    },
                    position_decision={"target_position_pct": 50},
                    target_date="2026-07-19",
                )

                self.assertEqual(packet["canonical_target"], {})
                self.assertEqual(packet["canonical_role"], "无")
                self.assertEqual(packet["final_action"]["position_pct"], 0)

    def test_full_section_keeps_structured_50_percent_when_legacy_action_says_full_position(self):
        packet = build_sniper_target_derivation_packet(
            data={
                "selection_workflow": {
                    "schema_version": "selection_workflow.v1",
                    "target_date": "2026-07-07",
                    "final": {
                        "position_pct": 50,
                        "execution_object": {"name": "华天科技", "code": "002185", "sector": "半导体"},
                        "action_text": "满仓条件执行",
                    },
                    "candidate_pool": [
                        {
                            "stock": {"name": "华天科技", "code": "002185", "sector": "半导体"},
                            "status": "最终执行对象",
                        }
                    ],
                }
            },
            bayesian_diagnosis={
                "schema_version": "bayesian_diagnosis.v1",
                "conclusion": {
                    "path_conclusion": "条件执行",
                    "position_pct": 50,
                    "action_text": "满仓条件执行",
                    "final_action_alignment": "一致",
                },
                "path": [],
            },
            target_date="2026-07-07",
        )

        rendered = "\n".join(full_section(packet))

        self.assertIn("仓位=50% 动作=满仓条件执行", rendered)
        self.assertNotIn("仓位=满仓 动作=满仓条件执行", rendered)

    def test_full_section_keeps_cached_structured_50_percent_visible(self):
        packet = {
            "canonical_target": {"name": "华天科技", "code": "002185", "sector": "半导体"},
            "full_ascii": [
                "路径诊断复盘",
                "|-- 路径结论=条件执行 最终动作一致性=一致 仓位=50% 动作=满仓条件执行",
                "|",
                "T2 最终动作",
                "|-- 仓位=50% 动作=满仓条件执行 原因=来自 selection_workflow.v1 的 N8 仓位与执行条件",
            ],
        }

        rendered = "\n".join(full_section(packet))

        self.assertIn("仓位=50% 动作=满仓条件执行", rendered)
        self.assertNotIn("仓位=满仓 动作=满仓条件执行", rendered)


if __name__ == "__main__":
    unittest.main()
