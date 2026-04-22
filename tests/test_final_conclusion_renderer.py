import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.final_conclusion_renderer import build_legacy_final_conclusion_lines


class FinalConclusionRendererTest(unittest.TestCase):
    def test_full_mode_uses_dynamic_stage_rows_and_strategy_summary(self):
        lines = build_legacy_final_conclusion_lines(
            {
                "display_mvp_mode": False,
                "step0_prediction": "NEUTRAL",
                "step0_prediction_cn": "🟡 中性",
                "step0_action": "先观察后确认",
                "final_gate": {
                    "can_new_entry": True,
                    "gate_status": "conditional_entry",
                },
                "mainline_name": "军工",
                "watchlist_count": 12,
                "core_count": 2,
                "secondary_count": 1,
                "crossline_count": 1,
                "abnormal_watch_count": 2,
                "front_structure_layer_text": "只等唯一动作",
                "trade_gate_open": True,
                "best_stock": {"name": "军工一号", "code": "000001"},
                "watch_anchor": None,
                "watch_anchor_type": "",
                "front_follow_action_text": "只买军工一号，60分钟确认后触发",
                "abnormal_probe_parts": ["主线异动里先看谁：军工一号(000001)"],
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("| stage_key | 模块 | 明日指引 |", rendered)
        self.assertIn("| market_environment | 环境与跟随裁决 |", rendered)
        self.assertIn("| selection_focus | 明天观察池 |", rendered)
        self.assertIn("| decisive_choice | 唯一动作 |", rendered)
        self.assertIn("| **明日策略** | **唯一标的条件触发** | 只操作军工一号", rendered)
        self.assertNotIn("Step 4.5", rendered)

    def test_mvp_mode_renders_buy_target_and_single_action(self):
        lines = build_legacy_final_conclusion_lines(
            {
                "display_mvp_mode": True,
                "step0_prediction": "CLEAR",
                "step0_prediction_cn": "🟢 明朗",
                "step0_action": "允许强势跟随",
                "final_gate": {
                    "can_new_entry": True,
                    "gate_status": "execute_50",
                },
                "mainline_label": "军工 / 高端装备",
                "watchlist_count": 10,
                "core_count": 2,
                "crossline_count": 1,
                "abnormal_watch_count": 1,
                "front_structure_layer_text": "可以开仓，但只剩唯一动作",
                "trade_gate_open": True,
                "best_stock": {"name": "军工一号", "code": "000001"},
                "watch_anchor": None,
                "watch_anchor_type": "",
                "front_follow_action_text": "只买军工一号，60分钟确认后执行",
                "abnormal_probe_parts": ["主线异动里先看谁：军工一号(000001)"],
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("| 维度 | 明日结论 |", rendered)
        self.assertIn("| 明日主看方向 | 军工 / 高端装备 |", rendered)
        self.assertIn("| 如果要买只买谁 | 军工一号(000001)，60分钟确认后按条件触发 |", rendered)
        self.assertIn("| 明日唯一动作 | 只买军工一号，60分钟确认后执行 |", rendered)


if __name__ == "__main__":
    unittest.main()
