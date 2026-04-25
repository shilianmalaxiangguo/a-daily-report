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
        self.assertIn("| 项目 | 明日指引 |", rendered)
        self.assertIn("| 环境与跟随裁决 |", rendered)
        self.assertIn("| 明天观察池 | 12只 |", rendered)
        self.assertIn("| 唯一动作 | 军工一号(000001)；60分钟确认后按条件触发 |", rendered)
        self.assertIn("| 明日策略 | 唯一标的条件触发：只操作军工一号", rendered)
        self.assertNotIn("stage_key", rendered)
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
                "best_stock": {"name": "军工一号", "code": "000001", "r_reward_ratio": 2.4},
                "watch_anchor": None,
                "watch_anchor_type": "",
                "front_follow_action_text": "只买军工一号，60分钟确认后执行",
                "abnormal_probe_parts": ["主线异动里先看谁：军工一号(000001)"],
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("| 项目 | 明日指引 |", rendered)
        self.assertIn("| 主看方向 | 军工 / 高端装备 |", rendered)
        self.assertIn("| 如果要买只买谁 | 军工一号(000001)，60分钟确认后按条件触发 |", rendered)
        self.assertIn("| 明日唯一动作 | 只买军工一号，60分钟确认后执行 |", rendered)
        self.assertIn("| 操作风格 | 短线 |", rendered)
        self.assertIn("| 盈亏比约束 | 预估赚赔比 1:2.4", rendered)

    def test_mvp_mode_renders_market_outlook_and_today_focus_recap(self):
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
                "tracking_memory_status": {
                    "today_validated_items": [
                        {"name": "老龙头", "code": "000002", "follow_state": "今日再次入池"},
                        {"name": "军工一号", "code": "000001", "follow_state": "跌不下去"},
                    ]
                },
                "best_stock": {"name": "军工一号", "code": "000001", "r_reward_ratio": 2.4},
                "front_follow_action_text": "只买军工一号，60分钟确认后执行",
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("| 明日大盘预期 | 🟢 明朗；允许强势跟随 |", rendered)
        self.assertIn("| 今日关注标的 | 军工一号(000001)：已缩成明天唯一执行候选 |", rendered)
        self.assertNotIn("老龙头(000002)：今日再次入池", rendered)

    def test_mvp_mode_prefers_core_candidate_over_tracking_memory_focus(self):
        lines = build_legacy_final_conclusion_lines(
            {
                "display_mvp_mode": True,
                "step0_prediction": "CLEAR",
                "step0_prediction_cn": "🟢 明朗",
                "step0_action": "允许强势跟随",
                "final_gate": {"can_new_entry": True},
                "tracking_memory_status": {
                    "today_validated_items": [
                        {"name": "中嘉博创", "code": "000889", "follow_state": "新异动待观察"},
                    ]
                },
                "core_stocks": [{"name": "富瀚微", "code": "300613"}],
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("| 今日关注标的 | 富瀚微(300613)：主线核心候选，优先观察 |", rendered)
        self.assertNotIn("中嘉博创(000889)：新异动待观察", rendered)

    def test_full_mode_prefers_provided_report_stage_order_and_titles(self):
        lines = build_legacy_final_conclusion_lines(
            {
                "display_mvp_mode": False,
                "report_stages": [
                    {"stage_key": "watch_pool", "title": "观察池先看什么", "summary": "先缩观察池"},
                    {"stage_key": "environment_follow", "title": "环境先怎么判", "summary": "先判环境"},
                    {"stage_key": "entry_plan", "title": "买点计划怎么排", "summary": "先做计划"},
                ],
                "watchlist_count": 9,
                "core_count": 2,
                "secondary_count": 1,
                "crossline_count": 1,
                "front_structure_layer_text": "只等唯一动作",
                "trade_gate_open": True,
                "best_stock": {"name": "军工一号", "code": "000001"},
            }
        )

        rendered = "\n".join(lines)
        selection_row = "| 观察池先看什么 | 9只 |"
        environment_row = "| 环境先怎么判 | 先判环境 |"
        execution_row = "| 买点计划怎么排 | 只等明天唯一能买的那只自己走出来 |"
        self.assertIn(selection_row, rendered)
        self.assertIn(environment_row, rendered)
        self.assertIn(execution_row, rendered)
        self.assertLess(rendered.index(selection_row), rendered.index(environment_row))

    def test_full_mode_stage_rows_use_data_driven_market_focus_and_style(self):
        lines = build_legacy_final_conclusion_lines(
            {
                "display_mvp_mode": False,
                "step0_prediction": "CLEAR",
                "step0_prediction_cn": "🟢 明朗",
                "step0_action": "允许强势跟随",
                "watchlist_count": 15,
                "core_count": 2,
                "secondary_count": 1,
                "crossline_count": 1,
                "tracking_memory_status": {
                    "today_validated_items": [{"name": "老龙头", "code": "000002", "follow_state": "今日再次入池"}]
                },
                "final_gate": {"can_new_entry": True},
                "trade_gate_open": True,
                "best_stock": {"name": "军工一号", "code": "000001", "r_reward_ratio": 2.4},
                "front_structure_layer_text": "高位分歧加大",
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("| 环境与跟随裁决 | 🟢 明朗；允许强势跟随 |", rendered)
        self.assertIn("| 明天观察池 | 15只；军工一号(000001)：已缩成明天唯一执行候选 |", rendered)
        self.assertNotIn("老龙头(000002)：今日再次入池", rendered)
        self.assertIn("| 主线核心与跨线观察 | 2只主线核心 / 1只备选 / 1只跨线观察；先只在主线核心里做减法，目标缩到军工一号(000001) |", rendered)
        self.assertIn("| 明日风险预判 | 高位分歧加大；只接受预估赚赔比 1:2.4 的试错，不接受大亏硬扛 |", rendered)
        self.assertIn("| 明日买点预计算 | 短线；只等明天唯一能买的那只自己走出来 |", rendered)

    def test_full_mode_marks_trend_style_as_swing_instead_of_short_term(self):
        lines = build_legacy_final_conclusion_lines(
            {
                "display_mvp_mode": False,
                "step0_prediction": "CLEAR",
                "step0_prediction_cn": "🟢 明朗",
                "step0_action": "允许强势跟随",
                "core_count": 1,
                "secondary_count": 0,
                "crossline_count": 0,
                "final_gate": {"can_new_entry": True},
                "trade_gate_open": True,
                "style_switch": {"style_label": "趋势分歧优先"},
                "best_stock": {"name": "军工一号", "code": "000001", "r_reward_ratio": 2.8},
                "front_structure_layer_text": "趋势分歧更适合等回踩确认",
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("| 操作风格 | 波段 |", rendered)
        self.assertIn("| 明日买点预计算 | 波段；只等明天唯一能买的那只自己走出来 |", rendered)

    def test_mvp_mode_can_render_only_enabled_nodes(self):
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
                "front_follow_action_text": "只买军工一号，60分钟确认后执行",
                "enabled_node_keys": ["header", "table_header", "mvp_target", "mvp_action"],
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("#### 最终结论", rendered)
        self.assertIn("| 项目 | 明日指引 |", rendered)
        self.assertIn("| 如果要买只买谁 | 军工一号(000001)，60分钟确认后按条件触发 |", rendered)
        self.assertIn("| 明日唯一动作 | 只买军工一号，60分钟确认后执行 |", rendered)
        self.assertNotIn("| 主看方向 |", rendered)
        self.assertNotIn("| 执行纪律 |", rendered)


if __name__ == "__main__":
    unittest.main()
