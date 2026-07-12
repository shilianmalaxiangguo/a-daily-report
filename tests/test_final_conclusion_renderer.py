import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

ACTION_TEXT = "只买军工一号，固定交易窗口条件满足后执行"

from report.execution_wording import PREMARKET_50_TRIGGER_TEXT, TWO_B_CONFIRMATION_CLAUSE
from report.final_conclusion_renderer import build_legacy_final_conclusion_lines
from report.conclusion_support import (
    build_candidate_trade_directive,
    build_focus_recap_text,
    build_market_outlook_text,
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
        self.assertIn("| 明天观察池 | 军工一号(000001)：已缩成明天唯一执行候选 |", rendered)
        self.assertIn(f"| 唯一动作 | 军工一号(000001)；{PREMARKET_50_TRIGGER_TEXT} |", rendered)
        self.assertIn("| 明日策略 | 唯一标的条件触发：只操作军工一号", rendered)
        self.assertNotIn("stage_key", rendered)
        self.assertNotIn("Step 4.5", rendered)

    def test_full_mode_does_not_render_inferred_plan_as_confirmed_old_position(self):
        lines = build_legacy_final_conclusion_lines(
            {
                "display_mvp_mode": False,
                "step0_prediction": "DIFFICULT",
                "step0_prediction_cn": "🟠 只处理旧仓",
                "step0_action": "不新增参与",
                "final_gate": {"can_new_entry": False, "should_reduce": True},
                "existing_position_summary": {
                    "has_position": True,
                    "summary": "持有太极实业(600667)，100%仓位；先看28.89能否守住，09:50-10:10收不回先卖；新仓是否叠加单独看Te执行资格",
                    "inferred_from_previous_report": True,
                    "position_source": "previous_report_target_default_1x",
                },
                "watchlist_count": 0,
                "core_count": 0,
                "secondary_count": 0,
                "crossline_count": 0,
            }
        )

        rendered = "\n".join(lines)
        self.assertNotIn("旧仓处理：持有太极实业(600667)", rendered)
        self.assertNotIn("| 操作风格 | 旧仓处理 |", rendered)
        self.assertNotIn("先处理旧仓：持有太极实业(600667)", rendered)
        self.assertIn("| 操作风格 | 空仓 |", rendered)

    def test_full_mode_keeps_new_target_actionable_with_inferred_default_old_position(self):
        context = {
            "display_mvp_mode": False,
            "step0_prediction": "NEUTRAL",
            "step0_prediction_cn": "🟡 条件进攻",
            "step0_action": "固定交易窗口确认",
            "final_gate": {
                "can_new_entry": False,
                "allow_attack_50_ready": True,
                "final_action": "明日目标标的已决定50%条件执行：只看601138 工业富联",
            },
            "trade_gate_open": False,
            "selected_position_candidate": {
                "name": "工业富联",
                "code": "601138",
                "sector": "通信设备",
            },
            "position_decision": {
                "target_position_pct": 50,
                "participation_mode": "attack_50_preview",
            },
            "existing_position_summary": {
                "has_position": True,
                "summary": "持有太极实业(600667)，100%仓位；上一份日报明日标的默认1x旧仓；新仓是否叠加单独看Te执行资格",
                "inferred_from_previous_report": True,
                "position_source": "previous_report_target_default_1x",
                "default_position_pct": 100.0,
            },
            "final_target_resolution": {
                "new_entry_target": {"name": "工业富联", "code": "601138", "sector": "通信设备"},
                "existing_position_target": {
                    "name": "太极实业",
                    "code": "600667",
                    "inferred_from_previous_report": True,
                    "position_source": "previous_report_target_default_1x",
                    "default_position_pct": 100.0,
                },
                "display_target": {"name": "工业富联", "code": "601138", "sector": "通信设备"},
                "capital_priority_decision": {
                    "capital_priority": "new_entry",
                    "reason": "旧仓默认1x按旧路径处理；新开仓对象具备执行资格时，按固定交易窗口确认，可与旧仓分账判断",
                },
            },
        }

        rendered = "\n".join(build_legacy_final_conclusion_lines(context))

        self.assertIn(f"| 今日关注标的 | 工业富联(601138)：明日目标标的，{PREMARKET_50_TRIGGER_TEXT} |", rendered)
        self.assertIn("| 操作风格 | 条件进攻 |", rendered)
        self.assertIn(f"| 唯一动作 | 工业富联(601138)；{PREMARKET_50_TRIGGER_TEXT} |", rendered)
        self.assertIn(f"| 明日买点预计算 | 条件进攻；只等明日目标标的{PREMARKET_50_TRIGGER_TEXT} |", rendered)
        self.assertNotIn("| 操作风格 | 旧仓处理 |", rendered)
        self.assertNotIn("| 唯一动作 | 旧仓处理：持有太极实业", rendered)
        self.assertNotIn("先处理旧仓风险", rendered)

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
        self.assertIn(f"| 如果要买只买谁 | 军工一号(000001)，按09:30-09:35竞价/开盘前几分钟/回封，或09:50-10:10窗口触发；{TWO_B_CONFIRMATION_CLAUSE} |", rendered)
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
                    "final_action": "明日目标标的保留50%条件执行：只看000586 汇源通信",
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
        self.assertIn(f"| 今日关注标的 | 汇源通信(000586)：明日目标标的，{PREMARKET_50_TRIGGER_TEXT} |", rendered)
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
        self.assertEqual(build_focus_recap_text(context), "汇源通信(000586)：观察对象，先观察强弱与承接")
        self.assertEqual(derive_trade_style(context), "空仓")
        self.assertIn("当前先守住回撤", derive_risk_guard_text(context))

    def test_wait_resolution_without_watch_target_does_not_promote_downgraded_sample_in_final_conclusion(self):
        context = {
            "display_mvp_mode": False,
            "step0_prediction_cn": "🚫 暂不跟随",
            "step0_action": "空仓等待，禁止参与",
            "final_gate": {
                "can_new_entry": False,
                "final_action": "空仓等待，禁止参与",
            },
            "trade_gate_open": False,
            "watchlist_count": 4,
            "core_count": 0,
            "secondary_count": 0,
            "crossline_count": 4,
            "selected_position_candidate": {
                "name": "大有能源",
                "code": "600403",
                "sector": "煤炭开采",
                "anchor_reversal_decision": "降级观察",
                "candidate_role": "观察样本",
            },
            "watch_anchor": {
                "name": "大有能源",
                "code": "600403",
                "sector": "煤炭开采",
                "watch_anchor_type": "跨线重点观察谁",
            },
            "position_decision": {
                "target_position_pct": 0,
                "participation_mode": "observe_0",
            },
            "final_target_resolution": {
                "watch_target": {},
                "capital_priority_decision": {
                    "capital_priority": "wait",
                    "reason": "空仓等待，禁止参与",
                },
            },
        }

        rendered = "\n".join(build_legacy_final_conclusion_lines(context))

        self.assertIn("| 今日关注标的 | 今天没有新增可信关注对象，明天先空仓观察 |", rendered)
        self.assertIn("| 明天观察池 | 4只 |", rendered)
        self.assertIn("| 唯一动作 | 当前没有能下手的票，明日空仓观察 |", rendered)
        self.assertNotIn("大有能源(600403)：观察对象", rendered)
        self.assertNotIn("跨线重点观察谁", rendered)

    def test_old_position_priority_keeps_new_target_as_observation_anchor(self):
        context = {
            "display_mvp_mode": False,
            "step0_prediction_cn": "🚫 暂不跟随",
                "final_gate": {
                    "can_new_entry": False,
                    "should_reduce": True,
                    "final_action": "先处理旧仓，不新增参与；新强对象只保留观察对象",
                },
            "selected_position_candidate": {
                "name": "工业富联",
                "code": "601138",
                "sector": "通信设备",
            },
            "position_decision": {
                "target_position_pct": 100,
                "participation_mode": "full_100",
            },
            "final_target_resolution": {
                "new_entry_target": {"name": "工业富联", "code": "601138", "sector": "通信设备"},
                "watch_target": {"name": "工业富联", "code": "601138", "sector": "通信设备"},
                "existing_position_target": {"name": "华电辽能", "code": "600396", "role": "旧仓处理"},
                "display_target": {"name": "华电辽能", "code": "600396", "role": "旧仓处理"},
                "capital_priority_decision": {
                    "capital_priority": "old_position_t",
                    "reason": "约1w账户先处理已有仓，工业富联只保留观察对象",
                },
            },
        }

        self.assertFalse(selected_target_is_attack_ready(context))
        self.assertEqual(build_focus_recap_text(context), "工业富联(601138)：观察对象，旧仓先处理")
        self.assertIn("先处理旧仓，不新增参与", build_market_outlook_text(context))
        self.assertIn("账户先处理旧仓，不新增参与", build_candidate_trade_directive(context))
        self.assertNotIn("固定交易窗口内条件是否成立", build_candidate_trade_directive(context))

        rendered = "\n".join(build_legacy_final_conclusion_lines(context))
        self.assertIn("| 今日关注标的 | 工业富联(601138)：观察对象，旧仓先处理 |", rendered)
        self.assertIn("| 明天观察池 | 工业富联(601138)：观察对象，旧仓先处理 |", rendered)
        self.assertIn("| 明日买点预计算 | 空仓；不开新仓，只保留重点观察谁 |", rendered)
        self.assertIn("| 唯一动作 | 工业富联(601138)；先观察强弱，不抢跑 |", rendered)
        self.assertIn("| 明日策略 | 只处理旧仓：继续研究市场，但不新增参与", rendered)
        self.assertNotIn("工业富联(601138)：明日目标标的", rendered)
        self.assertNotIn("只等明日目标标的在固定交易窗口内满足条件", rendered)
        self.assertNotIn("明日目标标的条件触发", rendered)

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

        self.assertIn("板块锚反推已收敛到观察对象汇源通信(000586)，先观察强弱与承接", directive)
        self.assertNotIn("只看参与窗口是否成立", directive)

    def test_candidate_trade_directive_replaces_legacy_counts_when_selected_target_exists(self):
        directive = build_candidate_trade_directive(
            {
                "core_count": 3,
                "secondary_count": 1,
                "crossline_count": 4,
                "selected_position_candidate": {
                    "name": "华锋股份",
                    "code": "002806",
                },
                "position_decision": {
                    "target_position_pct": 50,
                    "participation_mode": "attack_50_preview",
                },
            }
        )

        self.assertIn("板块锚反推已收敛到明日目标标的华锋股份(002806)", directive)
        self.assertNotIn("3只主线核心", directive)
        self.assertNotIn("1只备选", directive)
        self.assertNotIn("4只跨线观察", directive)

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
                    "final_action": "明日目标标的保留50%条件执行：只看000586 汇源通信，固定交易窗口内条件成立才执行，不满足回到0%",
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
        self.assertIn("明日目标标的保留50%条件执行：只看000586 汇源通信", rendered)
        self.assertIn("| 明日风险预判 | 固定交易窗口内条件不成立就回到0%，只接受小亏试错，不接受大亏硬扛 |", rendered)
        self.assertIn(f"| 明日买点预计算 | 条件进攻；只等明日目标标的{PREMARKET_50_TRIGGER_TEXT} |", rendered)
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
        selection_row = "| 观察池先看什么 | 军工一号(000001)：已缩成明天唯一执行候选 |"
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
        self.assertIn("| 明天观察池 | 军工一号(000001)：已缩成明天唯一执行候选 |", rendered)
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
        self.assertIn(f"| 如果要买只买谁 | 军工一号(000001)，按09:30-09:35竞价/开盘前几分钟/回封，或09:50-10:10窗口触发；{TWO_B_CONFIRMATION_CLAUSE} |", rendered)
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
        self.assertIn("09:30-09:35竞价表态/开盘前几分钟/回封，或09:50-10:10窗口", rendered)
        self.assertIn("不满足执行资格就回到0%", rendered)
        self.assertNotIn("明日前30分钟先确认环境", rendered)
        self.assertNotIn("买点一律" + "等60" + "分钟确认", rendered)


if __name__ == "__main__":
    unittest.main()
