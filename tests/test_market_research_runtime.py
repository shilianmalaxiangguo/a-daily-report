import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from research.market_research_runtime import (
    build_market_research_snapshot_contract,
    derive_step0_follow_plan_contract,
)


class MarketResearchRuntimeTest(unittest.TestCase):
    def test_build_market_research_snapshot_contract_composes_state_machine_bundle(self):
        result = build_market_research_snapshot_contract(
            data={"sector_ai_analysis": {"mapping": {"军工": "军工"}}},
            final_gate={"can_new_entry": True},
            position_level="三档（进攻档）",
            exit_analysis={"overall_level": "黄灯"},
            observation_snapshot={
                "abnormal_watch_pool": [{"code": "000001"}],
                "main_sectors_info": [{"name": "军工"}],
                "secondary_sectors_info": [{"name": "机器人"}],
                "sector_trend_snapshot": [{"sector": "军工"}],
            },
            target_date="2026-04-22",
            build_abnormal_projection_summary=lambda pool: {"projection_label": "承接强化"},
            build_market_style_switch_snapshot=lambda target_date, data, observation_snapshot, abnormal_projection: {"style_label": "主线抱团"},
            build_market_state_machine_snapshot=lambda *args, **kwargs: {"leading_line": "军工", "state_code": "expand"},
            build_mainline_rotation_snapshot=lambda **kwargs: {"summary_text": "军工继续聚焦"},
            build_abnormal_probe_group=lambda **kwargs: {"probe_group_label": "先看异常"},
            build_special_probe_verdict=lambda **kwargs: {"summary_text": "先看异常承接", "action": "看军工异常股"},
            build_follow_verdict=lambda *args, **kwargs: {"label": "🟢 跟随主线", "reason": "主线清晰", "action": "只跟军工"},
            build_dialectical_decision_snapshot=lambda **kwargs: {"stage_label": "主升", "stage_action": "继续跟随"},
        )

        self.assertEqual(result["state_machine"]["leading_line"], "军工")
        self.assertEqual(result["follow_verdict"]["label"], "🟢 跟随主线")
        self.assertEqual(result["mainline_rotation_snapshot"]["summary_text"], "军工继续聚焦")
        self.assertEqual(result["special_probe_verdict"]["action"], "看军工异常股")
        self.assertTrue(any(log["step"] == "follow_verdict" for log in result["module_logs"]))

    def test_derive_step0_follow_plan_contract_merges_probe_and_style_actions(self):
        result = derive_step0_follow_plan_contract(
            {
                "state_machine": {"state_code": "contract", "energy_state": "收缩防守"},
                "follow_verdict": {"label": "🟡 条件跟随", "reason": "先看环境", "action": "缩小范围"},
                "style_switch": {"style_label": "轮动", "primary_action": "不要追高"},
                "special_probe_verdict": {"summary_text": "先看异常承接", "action": "看异常龙头"},
            },
            {"can_new_entry": True},
            "二档（防守档）",
        )

        self.assertEqual(result["step0_prediction"], "DIFFICULT")
        self.assertIn("先看特殊标的", result["step0_action"])
        self.assertIn("不要追高", result["step0_action"])
        self.assertIn("先看异常承接", result["step0_reason"])
        self.assertTrue(any(log["step"] == "step0_plan" for log in result["module_logs"]))


if __name__ == "__main__":
    unittest.main()
