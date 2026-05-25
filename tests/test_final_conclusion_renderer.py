import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

ACTION_TEXT = "只买军工一号，参与窗口确认后执行"

from report.final_conclusion_renderer import build_legacy_final_conclusion_lines
from report.conclusion_support import (
    build_candidate_trade_directive,
    build_focus_recap_text,
    derive_risk_guard_text,
    derive_trade_style,
    selected_target_is_attack_ready,
)


class FinalConclusionRendererTest(unittest.TestCase):
    def test_candidate_trade_directive_uses_observation_language_when_no_target(self):
        empty_directive = build_candidate_trade_directive(
            {"core_count": 0, "secondary_count": 0, "crossline_count": 0}
        )
        core_directive = build_candidate_trade_directive(
            {"core_count": 1, "secondary_count": 0, "crossline_count": 1}
        )

        self.assertIn("当前还没缩出具备参与资格的对象", empty_directive)
        self.assertIn("不把跨线对象直接当观察位", core_directive)
        self.assertNotIn("可执行对象", empty_directive)
        self.assertNotIn("当买点", core_directive)

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
        self.assertIn("| 唯一动作 | 军工一号(000001)；按预演参与窗口触发 |", rendered)
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
                "front_follow_action_text": ACTION_TEXT,
                "abnormal_probe_parts": ["主线异动里先看谁：军工一号(000001)"],
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("| 项目 | 明日指引 |", rendered)
        self.assertIn("| 主看方向 | 军工 / 高端装备 |", rendered)
        self.assertIn("| 如果要买只买谁 | 军工一号(000001)，按竞价/开盘前几分钟/回封/60分钟分层参与窗口触发 |", rendered)
        self.assertIn(f"| 明日唯一动作 | {ACTION_TEXT} |", rendered)
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
                "front_follow_action_text": ACTION_TEXT,
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

    def test_final_conclusion_prefers_selected_target_over_core_candidate(self):
        lines = build_legacy_final_conclusion_lines(
            {
                "display_mvp_mode": False,
                "step0_prediction": "NEUTRAL",
                "step0_prediction_cn": "🟡 中性",
                "step0_action": "先观察后确认",
                "final_gate": {
                    "can_new_entry": False,
                    "allow_attack_50_ready": True,
                    "final_action": "明日目标标的保留条件50%预演：只看000586 汇源通信",
                },
                "trade_gate_open": False,
                "watchlist_count": 15,
                "core_stocks": [{"name": "景兴纸业", "code": "002067"}],
                "selected_position_candidate": {
                    "name": "汇源通信",
                    "code": "000586",
                    "sector": "通信设备",
                },
                "position_decision": {
                    "target_position_pct": 50,
                    "participation_mode": "attack_50_preview",
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("| 今日关注标的 | 汇源通信(000586)：明日目标标的，参与窗口确认才执行 |", rendered)
        self.assertNotIn("景兴纸业(002067)：主线核心候选", rendered)

    def test_selected_target_stays_observation_when_position_decision_is_zero(self):
        context = {
            "final_gate": {
                "can_new_entry": False,
                "allow_attack_50_ready": True,
            },
            "selected_position_candidate": {
                "name": "汇源通信",
                "code": "000586",
            },
            "position_decision": {
                "target_position_pct": 0,
                "participation_mode": "observe_0",
            },
        }

        self.assertFalse(selected_target_is_attack_ready(context))
        self.assertEqual(build_focus_recap_text(context), "汇源通信(000586)：明日目标标的，先观察强弱与承接")
        self.assertEqual(derive_trade_style(context), "空仓")
        self.assertIn("当前先守住回撤", derive_risk_guard_text(context))

    def test_candidate_trade_directive_keeps_zero_position_target_observational(self):
        directive = build_candidate_trade_directive(
            {
                "core_count": 3,
                "secondary_count": 1,
                "crossline_count": 0,
                "final_gate": {
                    "can_new_entry": False,
                    "allow_attack_50_ready": True,
                },
                "selected_position_candidate": {
                    "name": "汇源通信",
                    "code": "000586",
                },
                "position_decision": {
                    "target_position_pct": 0,
                    "participation_mode": "observe_0",
                },
            }
        )

        self.assertIn("已缩到明日目标标的汇源通信(000586)，先观察强弱与承接", directive)
        self.assertNotIn("只看参与窗口是否成立", directive)

    def test_final_conclusion_rebuilds_stale_stage_rows_when_selected_target_is_ready(self):
        lines = build_legacy_final_conclusion_lines(
            {
                "display_mvp_mode": False,
                "step0_prediction": "NEUTRAL",
                "step0_prediction_cn": "🟡 中性",
                "step0_action": "旧动作：空仓观察，禁止新开仓",
                "final_gate": {
                    "can_new_entry": False,
                    "allow_attack_50_ready": True,
                    "final_action": "明日目标标的保留条件50%预演：只看000586 汇源通信，参与窗口确认才执行，不满足回到0%",
                },
                "trade_gate_open": False,
                "watchlist_count": 15,
                "core_count": 3,
                "secondary_count": 3,
                "crossline_count": 0,
                "front_structure_layer_text": "0%，旧风险摘要：继续观察",
                "report_stages": [
                    {"stage_key": "environment_follow", "title": "明日环境与跟随裁决", "summary": "旧结论：空仓等待，禁止新开仓"},
                    {"stage_key": "risk_review", "title": "明日风险预判", "summary": "旧风险：0%，继续观察"},
                    {"stage_key": "entry_plan", "title": "明日买点预计算", "summary": "旧买点：不开新仓"},
                ],
                "selected_position_candidate": {
                    "name": "汇源通信",
                    "code": "000586",
                    "sector": "通信设备",
                },
                "position_decision": {
                    "target_position_pct": 50,
                    "participation_mode": "attack_50_preview",
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("明日目标标的保留条件50%预演：只看000586 汇源通信", rendered)
        self.assertIn("| 明日风险预判 | 参与窗口失败回到0%，只接受小亏试错，不接受大亏硬扛 |", rendered)
        self.assertIn("| 明日买点预计算 | 条件进攻；只等明日目标标的自己走出参与窗口 |", rendered)
        self.assertNotIn("旧结论：空仓等待", rendered)
        self.assertNotIn("旧风险：0%", rendered)
        self.assertNotIn("旧买点：不开新仓", rendered)
        self.assertNotIn("0%，旧风险摘要", rendered)

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
                "front_follow_action_text": ACTION_TEXT,
                "enabled_node_keys": ["header", "table_header", "mvp_target", "mvp_action"],
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("#### 最终结论", rendered)
        self.assertIn("| 项目 | 明日指引 |", rendered)
        self.assertIn("| 如果要买只买谁 | 军工一号(000001)，按竞价/开盘前几分钟/回封/60分钟分层参与窗口触发 |", rendered)
        self.assertIn(f"| 明日唯一动作 | {ACTION_TEXT} |", rendered)
        self.assertNotIn("| 主看方向 |", rendered)
        self.assertNotIn("| 执行纪律 |", rendered)

    def test_final_conclusion_discipline_uses_layered_participation_windows(self):
        lines = build_legacy_final_conclusion_lines(
            {
                "display_mvp_mode": False,
                "step0_prediction": "CLEAR",
                "final_gate": {"can_new_entry": True},
                "trade_gate_open": True,
                "best_stock": {"name": "大唐发电", "code": "601991"},
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("竞价表态/开盘前几分钟/回封/60分钟确认分层处理", rendered)
        self.assertIn("不满足预演情境就回到0%", rendered)
        self.assertNotIn("明日前30分钟先确认环境", rendered)
        self.assertNotIn("买点一律" + "等60" + "分钟确认", rendered)


if __name__ == "__main__":
    unittest.main()
