import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def _m(*parts):
    return "".join(parts)


def _cycle_sector_label_pattern(sector):
    return (
        r'<span class="cycle-sector-label" '
        r'style="color:#[0-9A-Fa-f]{6};border-color:#[0-9A-Fa-f]{6}">\['
        + re.escape(sector)
        + r"\]</span>"
    )


from report.front_page_v2_renderer import render_front_page_v2


class FrontPageV2RendererTest(unittest.TestCase):
    def test_front_page_opens_with_overtake_tone_when_window_summary_exists(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-29",
                market_research_snapshot={
                    "mainline_turnover_summary": {
                        "overtake_window_summary": {
                            "window_state": "open",
                            "primary_line": "半导体",
                            "rival_slowdown": "旧主线承接转弱，竞争线冲高回落",
                            "own_stability": "半导体资金扩散，核心承接稳定",
                            "observation_maturity": "跑过一段后再判断",
                            "overtake_logic": "对手过弯打滑，我方仍能弯道加速",
                            "action": "只在半导体核心里找参与资格",
                        }
                    },
                    "unique_action_target": {
                        "name": "晶方科技",
                        "code": "603005",
                        "condition": "主线确认 + 承接",
                    },
                },
            )
        )

        self.assertIn("- **今日基调**: 旧主线承接转弱，竞争线冲高回落；半导体资金扩散，核心承接稳定；只在半导体核心里找参与资格", rendered)
        self.assertNotIn("跑过一段后再判断，对手过弯打滑", rendered.split("## 明日账户建议", 1)[0])
        self.assertLess(rendered.index("- **今日基调**"), rendered.index("## 一、交易纪律"))

    def test_front_page_t002_renders_sniper_trade_scenarios(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-31",
                market_research_snapshot={
                    "position_decision": {"signal_grade": "50", "target_position_pct": 50},
                    "unique_action_target": {
                        "name": "强核心",
                        "code": "000001",
                        "condition": "主线确认 + 承接",
                    },
                },
                final_gate={"can_new_entry": True},
                position_level="0%不参与",
            )
        )

        discipline_section = rendered[rendered.index("## 一、交易纪律") : rendered.index("### 月度攻防与进攻仓位")]
        self.assertIn("| 明日结论 | 默认节奏 | 尾盘例外 | 最大风险 | 核心纪律 |", discipline_section)
        self.assertIn("T日只给T+1观察资格", discipline_section)
        self.assertIn("| 普通候选 | T+1 MA5回踩是基础入口", discipline_section)
        self.assertIn("| 强核心 | T+1混合龙头只用于板块核心、高辨识度、承接强", discipline_section)
        self.assertIn("| 已有旧仓/做T | 强势周期用MA5入/MA7清/MA5T", discipline_section)
        self.assertIn("| 失败仓/退潮 | 当天MA5买入后收盘跌破MA5，次日先按买点失败仓处理", discipline_section)
        self.assertIn("退潮警戒切MA5清", discipline_section)

    def test_front_page_surfaces_monthly_rhythm_position_grade_and_month_return(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-12",
                market_research_snapshot={
                    "mainline_turnover_summary": {"current_mainline": "机器人"},
                    "unique_action_target": {
                        "name": "机器人一号",
                        "code": "000001",
                        "condition": "主线确认 + 承接 + 60分钟确认",
                    },
                    "position_decision": {
                        "signal_grade": "50",
                        "target_position_pct": 50,
                        "full_attack_ready": False,
                        "sizing_reason": "唯一对象未完成100%核心确认，先按50%条件执行。",
                        "monthly_rhythm": {
                            "month_mode": "ordinary_attack",
                            "target_role": "attack_prepare",
                            "month_return_pct": 6.8,
                            "simulated_cumulative_return_pct": 9.3632,
                            "profit_cushion_pct": 10.0,
                            "max_position_pct": 50,
                            "allow_full_attack": False,
                            "profit_cushion": False,
                            "trend_invalid": False,
                            "reason": "处于进攻准备期，先按50%条件执行，不开放100%核心进攻。",
                        },
                    },
                    "two_layer_decision_payload": {
                        "front_decision": {
                            "execution_identity": "明日执行对象",
                            "position_plan": "50%条件执行",
                            "execution_object": {
                                "name": "太极实业",
                                "code": "600667",
                                "sector": "AI算力基础设施",
                            },
                        },
                        "b_level_conditions": {
                            "active_attack": {
                                "window": "09:30-09:35",
                                "money_confirmation": "分时大单净流入达标",
                            }
                        },
                    },
                },
            )
        )

        self.assertIn("### 月度攻防与进攻仓位", rendered)
        self.assertIn("| 本月模式 | 普通进攻月 |", rendered)
        self.assertIn("| 当月收益 | +6.80% |", rendered)
        self.assertIn("| 模拟累计收益 | +9.36% |", rendered)
        self.assertIn("| 盈利垫 | 未触发（阈值+10.00%） |", rendered)
        self.assertIn("| 进攻仓位三态 | 50% |", rendered)
        self.assertIn("| 明日最大仓位 | 50% |", rendered)
        self.assertIn("| 收益处理 | 未到盈利垫，按进攻仓位三态执行 |", rendered)

    def test_front_page_does_not_render_missing_month_return_as_zero(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-20",
                market_research_snapshot={
                    "mainline_turnover_summary": {"current_mainline": "半导体"},
                    "unique_action_target": {
                        "name": "晶方科技",
                        "code": "603005",
                        "condition": "固定交易窗口条件",
                    },
                    "position_decision": {
                        "signal_grade": "50",
                        "target_position_pct": 50,
                        "monthly_rhythm": {
                            "month_mode": "attack_prepare",
                            "month_return_pct": None,
                            "month_return_source": "missing",
                            "profit_cushion_pct": 10.0,
                            "profit_cushion": False,
                            "max_position_pct": 50,
                        },
                    },
                },
            )
        )

        self.assertIn("| 当月收益 | 未记录 |", rendered)
        self.assertIn("| 盈利垫 | 未记录（阈值+10.00%） |", rendered)
        self.assertNotIn("| 当月收益 | +0.00% |", rendered)

    def test_front_page_execution_plan_uses_layered_participation_windows(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-12",
                market_research_snapshot={
                    "mainline_turnover_summary": {"current_mainline": "电力"},
                    "unique_action_target": {
                        "name": "大唐发电",
                        "code": "601991",
                        "condition": "竞价表态 + 回封参与 + 失效价清楚",
                    },
                    "position_decision": {
                        "signal_grade": "100",
                        "target_position_pct": 100,
                        "full_attack_ready": True,
                        "monthly_rhythm": {"max_position_pct": 100},
                    },
                },
            )
        )

        self.assertIn("竞价表态", rendered)
        self.assertIn("开盘前几分钟", rendered)
        self.assertIn("回封参与", rendered)
        self.assertIn("T日只给T+1观察资格", rendered)
        self.assertIn("普通候选只等09:50-10:10 MA5回踩收回", rendered)
        self.assertIn("T+1混合龙头只用于板块核心、高辨识度、承接强", rendered)
        self.assertIn("09:50-10:10", rendered)
        self.assertIn("14:30-14:55", rendered)
        self.assertNotIn("买点等60分钟", rendered)
        self.assertNotIn(_m("满足60分钟确认", "才允许"), rendered)
        self.assertNotIn("60分钟确认", rendered)
        self.assertNotIn("09:50-10:10确认", rendered)

    def test_front_page_execution_plan_keeps_participation_to_fixed_time_windows(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-26",
                market_research_snapshot={
                    "mainline_turnover_summary": {"current_mainline": "半导体"},
                    "unique_action_target": {
                        "name": "富瀚微",
                        "code": "300613",
                        "participation_window": "60分钟确认",
                        "condition": "主线确认 + 承接 + 60分钟确认",
                    },
                    "position_decision": {
                        "signal_grade": "50",
                        "target_position_pct": 50,
                        "monthly_rhythm": {"max_position_pct": 50},
                    },
                },
            )
        )

        self.assertIn(
            "| 只看唯一对象 | 300613 富瀚微 | 09:50-10:10 | 主线确认 + 承接 + 09:50-10:10窗口 | 不满足回到0%不参与 |",
            rendered,
        )
        self.assertIn("| 09:30-09:35 |", rendered)
        self.assertIn("| 09:50-10:10 |", rendered)
        self.assertIn("| 14:30-14:55 |", rendered)
        self.assertNotIn("60分钟确认", rendered)

    def test_front_page_zero_participation_uses_observation_anchor_not_unique_object(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-28",
                market_research_snapshot={
                    "selected_position_candidate": {"name": "京能电力", "code": "600578", "sector": "电力"},
                    "position_decision": {
                        "signal_grade": "0",
                        "target_position_pct": 0,
                        "monthly_rhythm": {
                            "target_role": "defense_0",
                            "max_position_pct": 0,
                            "reason": "弱市场或趋势失效时，只允许0%保护本金。",
                        },
                    },
                    "front_page": {"backup_text": "暂无"},
                },
                final_gate={"can_new_entry": False, "market_ice_point": True},
            )
        )

        self.assertIn("| 观察对象 | 600578 京能电力（电力） |", rendered)
        self.assertIn("| 明日仓位 | 0%不参与 |", rendered)
        self.assertIn("| 执行目标 | 无 |", rendered)
        self.assertIn("| 不参与依据 | 市场情绪冰点，可能未止跌，不继续参与；弱市场或趋势失效时，只允许0%保护本金。 |", rendered)
        self.assertIn("| 无执行目标原因 | 市场情绪冰点，可能未止跌，不继续参与；指数图形与主攻线承接未修复，所以不给执行目标。 |", rendered)
        self.assertIn("| 责任归因 | 市场问题 |", rendered)
        self.assertIn("| 观察对象性质 | 强弱参照，不是执行目标 |", rendered)
        self.assertIn("| 恢复评估条件 | 主线承接 + 个股强弱重新确认 |", rendered)
        self.assertIn("| 观察对象去留 | 明日收盘前未满足恢复评估条件，移出前台观察 |", rendered)
        self.assertIn("| 明日观察动作 | 标的 | 观察窗 | 条件 | 不满足怎么办 |", rendered)
        self.assertIn("| 只看观察对象 | 600578 京能电力（电力） |", rendered)
        self.assertIn("观察对象只进入复盘和下一份日报判断", rendered)
        self.assertNotIn("观察" + "锚", rendered)
        self.assertNotIn("| 唯一对象 | 条件观察", rendered)
        self.assertNotIn("唯一对象是否", rendered)
        self.assertNotIn("| 执行目标 | 600578 京能电力（电力） |", rendered)

    def test_front_page_zero_participation_should_reduce_names_market_drawdown_reason(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-29",
                market_research_snapshot={
                    "selected_position_candidate": {"name": "华锋股份", "code": "002806", "sector": "汽车零部"},
                    "position_decision": {
                        "signal_grade": "0",
                        "target_position_pct": 0,
                        "monthly_rhythm": {
                            "max_position_pct": 0,
                            "target_role": "observe",
                            "trend_invalid": True,
                            "reason": "当天是放量杀跌里的局部逆势活跃，先防踩踏，等指数图形与主攻线承接同时修复后再给参与资格。",
                        },
                    },
                    "state_machine": {
                        "operation_state": "撤退态",
                        "execution_bias": "avoid",
                        "pulse_stage": "退潮",
                        "energy_state": "收缩防守",
                        "rise_fall_ratio": 0.40,
                    },
                },
                final_gate={"can_new_entry": False, "should_reduce": True},
            )
        )

        self.assertIn("| 明日仓位 | 0%不参与 |", rendered)
        account_section = rendered[rendered.index("## 明日账户建议") : rendered.index("## 一、交易纪律")]
        self.assertIn("| 0%原因 | 市场情绪退潮未止跌，可能还在释放风险，不继续参与", account_section)
        self.assertIn("| 不参与依据 | 市场情绪退潮未止跌，可能还在释放风险，不继续参与", rendered)
        self.assertIn("| 无执行目标原因 | 市场情绪退潮未止跌，可能还在释放风险，不继续参与", rendered)
        self.assertIn("市场情绪退潮未止跌，可能还在释放风险，不继续参与", rendered)
        self.assertIn("放量杀跌里的局部逆势活跃，先防踩踏", rendered)
        self.assertIn("买点失败仓次日先处理", rendered)
        self.assertNotIn("同类历史行说明同上，只看本行数值变化", rendered)
        self.assertNotIn("市场要求先降风险，不新增参与", rendered)

    def test_cycle_calendar_does_not_compress_repeated_day_cells_as_same_as_above(self):
        repeated = "连续记录同一个板块和状态时，周期日历也要每天明示板块，不写同上"
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-06-05",
                market_research_snapshot={
                    "cycle_calendar_rows": [
                        {
                            "week_label": "06-01当周",
                            "monday": repeated,
                            "tuesday": repeated,
                            "wednesday": repeated,
                            "thursday": repeated,
                            "friday": repeated,
                        }
                    ],
                },
                final_gate={"can_new_entry": False},
            )
        )

        calendar_section = rendered[rendered.index("### 1. 周期日历主视图") : rendered.index("### 2. 周期解读")]
        self.assertEqual(calendar_section.count(repeated), 5)
        self.assertNotIn("同类历史行说明同上，只看本行数值变化", calendar_section)

    def test_front_page_zero_observation_anchor_without_execution_basis_names_data_gap(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-06-04",
                market_research_snapshot={
                    "selected_position_candidate": {"name": "上海石化", "code": "600688", "sector": "炼化及贸"},
                    "position_decision": {"signal_grade": "0", "target_position_pct": 0},
                },
                final_gate={"can_new_entry": False},
            )
        )

        self.assertIn("| 观察对象 | 600688 上海石化（炼化及贸） |", rendered)
        self.assertIn("| 不参与依据 | 关键数据不完整：观察对象缺少完整执行条件，只能观察，不能新增参与。 |", rendered)
        self.assertIn("| 无执行目标原因 | 关键数据不完整，观察对象不能定义为执行目标 |", rendered)
        self.assertIn("| 责任归因 | 数据问题 |", rendered)

    def test_zero_position_selection_workflow_suppresses_stale_front_page_targets(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-06-04",
                market_research_snapshot={
                    "selected_position_candidate": {"name": "上海石化", "code": "600688", "sector": "炼化及贸"},
                    "unique_action_target": {"name": "上海石化", "code": "600688", "sector": "炼化及贸"},
                    "position_decision": {"signal_grade": "0", "target_position_pct": 0},
                    "final_target_resolution": {
                        "display_target": {},
                        "watch_target": {},
                        "capital_priority_decision": {
                            "capital_priority": "wait",
                            "reason": "空仓等待，禁止参与",
                        },
                    },
                    "selection_workflow": {
                        "schema_version": "selection_workflow.v1",
                        "final": {
                            "execution_object": {},
                            "position_pct": 0,
                            "action_text": "0%不参与",
                            "source_node": "N8",
                        },
                    },
                },
                final_gate={"can_new_entry": False, "final_action": "空仓等待，禁止参与；若你有仓位，只做退出不做幻想"},
            )
        )

        execution_section = rendered[rendered.index("## 六、明日执行计划") : rendered.index("## 七、最终结论")]
        final_section = rendered[rendered.index("## 七、最终结论") :]

        self.assertIn("| 观察对象 | 暂无 |", rendered)
        self.assertIn("| 只看观察对象 | 暂无 |", execution_section)
        self.assertIn("| 重点对象 | 明日执行风格 |", final_section)
        self.assertNotIn("600688 上海石化", execution_section + final_section)
        self.assertNotIn("观察对象：600688 上海石化", final_section)

    def test_selection_workflow_final_object_wins_over_old_front_page_targets(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-06-04",
                market_research_snapshot={
                    "selected_position_candidate": {"name": "上海石化", "code": "600688", "sector": "炼化及贸"},
                    "unique_action_target": {"name": "上海石化", "code": "600688", "sector": "炼化及贸"},
                    "position_decision": {"signal_grade": "50", "target_position_pct": 50},
                    "selection_workflow": {
                        "schema_version": "selection_workflow.v1",
                        "final": {
                            "execution_object": {"name": "豫能控股", "code": "001896", "sector": "电力"},
                            "position_pct": 50,
                            "action_text": "50%条件执行",
                            "source_node": "N8",
                        },
                    },
                },
            )
        )

        self.assertIn("001896 豫能控股（电力）", rendered)
        self.assertNotIn("600688 上海石化", rendered)

    def test_front_page_renders_premarket_narrative_review_cancel_from_selection_workflow(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-07-01",
                market_research_snapshot={
                    "position_decision": {"signal_grade": "100", "target_position_pct": 100},
                    "selection_workflow": {
                        "schema_version": "selection_workflow.v1",
                        "premarket_narrative_review": {
                            "status": "不参与",
                            "action_effect": "no_participation",
                            "action_effect_label": "不参与",
                            "summary": "Meta拟对外出售算力，击中AI算力和存储紧缺叙事",
                            "reason_chain": [
                                "AI算力和存储紧缺",
                                "Meta拟对外出售算力",
                                "韩国海力士和三星确认",
                                "太极实业直接暴露",
                                "满仓条件执行取消为不参与",
                            ],
                            "restore_conditions": ["同链板块不继续负反馈"],
                            "cancel_conditions": ["标的无法修复承接"],
                        },
                        "final": {
                            "execution_object": {},
                            "position_pct": 0,
                            "action_text": "0%不参与",
                            "source_node": "N8_5",
                            "premarket_narrative_review": {
                                "status": "不参与",
                                "action_effect": "no_participation",
                                "action_effect_label": "不参与",
                                "summary": "Meta拟对外出售算力，击中AI算力和存储紧缺叙事",
                                "reason_chain": [
                                    "AI算力和存储紧缺",
                                    "Meta拟对外出售算力",
                                    "韩国海力士和三星确认",
                                    "太极实业直接暴露",
                                    "满仓条件执行取消为不参与",
                                ],
                                "restore_conditions": ["同链板块不继续负反馈"],
                                "cancel_conditions": ["标的无法修复承接"],
                            },
                        },
                    },
                },
            )
        )

        self.assertIn("| 盘前叙事反证复核 | 不参与", rendered)
        self.assertIn("Meta拟对外出售算力", rendered)
        self.assertIn("动作上限：不参与", rendered)
        self.assertIn("同链板块不继续负反馈", rendered)
        candidate_section = rendered[rendered.index("## 五、个股解读") : rendered.index("## 六、明日执行计划")]
        final_section = rendered[rendered.index("## 七、最终结论") :]
        self.assertIn("| 明日仓位 | 0%不参与 |", candidate_section)
        self.assertIn("| 0%不参与", final_section)
        self.assertIn("盘前叙事反证复核见个股解读", final_section)
        self.assertNotIn("Meta拟对外出售算力", final_section)
        self.assertNotIn("| 明日仓位 | 100%核心进攻 |", candidate_section)
        self.assertNotIn("50%条件执行", candidate_section + final_section)
        self.assertNotIn("| 执行目标 | 太极实业(600667) |", candidate_section)
        self.assertNotIn("| 明日执行对象 | 太极实业(600667) |", candidate_section)

    def test_front_page_promotes_selected_candidate_to_50_when_zero_has_no_strong_reason(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-28",
                market_research_snapshot={
                    "selected_position_candidate": {
                        "name": "京能电力",
                        "code": "600578",
                        "sector": "电力",
                        "target_position_pct": 50,
                        "participation_window": "09:50-10:10确认",
                        "condition": "主线承接 + 个股强弱重新确认",
                        "fallback_state": "不满足回到0%",
                    },
                    "position_decision": {
                        "signal_grade": "0",
                        "target_position_pct": 0,
                        "sizing_reason": "当前只有观察对象，没有执行仓位。",
                    },
                    "front_page": {"backup_text": "暂无"},
                },
                final_gate={"can_new_entry": False, "market_ice_point": False},
            )
        )

        self.assertIn("| 明日仓位 | 50%条件执行 |", rendered)
        self.assertIn("| 执行目标 | 600578 京能电力（电力） |", rendered)
        self.assertIn("| 观察对象 | 无 |", rendered)
        self.assertNotIn("| 明日仓位 | 0%不参与 |", rendered)
        self.assertNotIn("| 观察对象性质 |", rendered)

    def test_front_page_zero_participation_without_anchor_names_decision_gap(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-28",
                market_research_snapshot={
                    "position_decision": {"signal_grade": "0", "target_position_pct": 0},
                    "candidate_snapshot": {"front_page": {"unique_object": "暂无"}},
                },
                final_gate={"can_new_entry": False},
            )
        )

        self.assertIn("| 明日仓位 | 0%不参与 |", rendered)
        self.assertIn("| 执行目标 | 无 |", rendered)
        self.assertIn("| 观察对象 | 暂无 |", rendered)
        self.assertIn("| 不参与依据 | 候选全部未达参与资格，需要复盘候选筛选。 |", rendered)
        self.assertIn("| 无执行目标原因 | 候选池没有选出足够强的核心 |", rendered)
        self.assertIn("| 责任归因 | 决策问题 |", rendered)

    def test_front_page_zero_participation_final_action_basis_is_strengthened_when_observation_anchor_exists(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-06-04",
                market_research_snapshot={
                    "selected_position_candidate": {"name": "上海石化", "code": "600688", "sector": "炼化及贸"},
                    "position_decision": {"signal_grade": "0", "target_position_pct": 0},
                    "front_page": {"backup_text": "暂无"},
                },
                final_gate={"can_new_entry": False, "final_action": "空仓等待，禁止参与；若你有仓位，只做退出不做幻想"},
            )
        )

        self.assertIn("| 观察对象 | 600688 上海石化（炼化及贸） |", rendered)
        self.assertIn(
            "| 不参与依据 | 空仓等待，禁止参与；若你有仓位，只做退出不做幻想；只处理旧仓，不新增参与。 |",
            rendered,
        )

    def test_front_page_zero_participation_keeps_inferred_default_old_position(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-07-02",
                market_research_snapshot={
                    "position_decision": {"signal_grade": "0", "target_position_pct": 0},
                    "existing_position_summary": {
                        "has_position": True,
                        "summary": "持有太极实业(600667)，100%仓位；先看28.89能否守住，09:50-10:10收不回先卖；新仓是否叠加单独看Tb/Tc资格",
                        "inferred_from_previous_report": True,
                        "position_source": "previous_report_target_default_1x",
                    },
                },
                final_gate={"can_new_entry": False, "final_action": "空仓等待，禁止参与；若你有仓位，只做退出不做幻想"},
            )
        )

        self.assertIn("| 明日仓位 | 0%新仓；旧仓处理 |", rendered)
        self.assertIn("| 旧仓处理 | 持有太极实业(600667)，100%仓位", rendered)
        self.assertIn("| 不参与依据 | 已有旧仓先按持仓预案处理；不新增参与。 |", rendered)
        self.assertNotIn("| 明日仓位 | 0%不参与 |", rendered)

    def test_front_page_unique_action_prefers_structured_required_steps(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-12",
                market_research_snapshot={
                    "mainline_turnover_summary": {"current_mainline": "电力"},
                    "unique_action_target": {
                        "name": "大唐发电",
                        "code": "601991",
                        "participation_window": "竞价表态 + 回封参与",
                        "participation_window_type": "auction_reseal",
                        "condition": "主线确认 + 承接 + 60分钟确认",
                        "required_steps": ["竞价表态", "开盘前几分钟承接", "回封/打板"],
                        "fallback_state": "不满足回到0%",
                    },
                    "position_decision": {
                        "signal_grade": "100",
                        "target_position_pct": 100,
                        "monthly_rhythm": {"max_position_pct": 100},
                    },
                },
            )
        )

        self.assertIn("| 只看唯一对象 | 601991 大唐发电 | 09:30-09:35 | 竞价表态 / 开盘前几分钟承接 / 回封/打板 | 不满足回到0%不参与 |", rendered)
        self.assertNotIn("| 只看唯一对象 | 601991 大唐发电 | 竞价表态 + 回封参与 | 主线确认 + 承接 + 60分钟确认 | 不做 |", rendered)

    def test_front_page_unique_action_uses_window_type_over_legacy_condition(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-12",
                market_research_snapshot={
                    "mainline_turnover_summary": {"current_mainline": "电力"},
                    "unique_action_target": {
                        "name": "大唐发电",
                        "code": "601991",
                        "participation_window": "竞价表态 + 回封参与",
                        "participation_window_type": "auction_reseal",
                        "condition": "主线确认 + 承接 + 60分钟确认",
                    },
                    "position_decision": {
                        "signal_grade": "100",
                        "target_position_pct": 100,
                        "monthly_rhythm": {"max_position_pct": 100},
                    },
                },
            )
        )

        self.assertIn("| 只看唯一对象 | 601991 大唐发电 | 09:30-09:35 | 竞价表态 / 开盘前几分钟承接 / 回封/打板 | 不满足回到0%不参与 |", rendered)
        self.assertNotIn("| 只看唯一对象 | 601991 大唐发电 | 竞价表态 + 回封参与 | 主线确认 + 承接 + 60分钟确认 | 不做 |", rendered)

    def test_front_page_renders_dragon_pullback_second_confirmation(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-24",
                market_research_snapshot={
                    "dragon_pullback_review": {
                        "leader": "华电辽能",
                        "second_confirmation": True,
                        "laggard_feedback": ["京能电力", "大唐发电"],
                    }
                },
            )
        )

        self.assertIn("| 龙头回头复核 | 华电辽能二次确认；京能电力、大唐发电低位补涨反哺核心辨识度 |", rendered)
        self.assertIn("龙头第一波后的回撤只算观察，第二波顶住压力且低位补涨同步，才说明市场继续投票", rendered)

    def test_front_page_renders_market_sector_spine_before_stock_sections(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-06-05",
                market_research_snapshot={
                    "market_structure_judgement": {
                        "index_profit_relation": "指数震荡但赚钱效应修复",
                        "turnover_distribution": "成交额回升，主动资金开始聚焦",
                        "rotation_nature": "电力压过旧科技，形成新旧切换",
                        "old_mainline_fatigue": "旧科技高位失速",
                        "tomorrow_rhythm": "只看新主线承接",
                        "candidate_policy": "个股裁决后置",
                        "summary_text": "市场从退潮末端进入发酵",
                    },
                    "mainline_turnover_summary": {
                        "current_mainline": "电力",
                        "cycle_stage": "发酵",
                        "data_text": "两市成交额回升至1.25万亿",
                        "turnover_share_trend_summary": "电力成交占比连续抬升",
                        "mainline_capacity_regime_summary": {
                            "mainline_capacity": "中等容量",
                            "mainline_regime": "主线+背景线",
                            "primary_line": "电力",
                            "other_lines": "科技、消费",
                            "confirmation_evidence": "电力成交占比抬升且涨停扩散",
                            "sector_relationship_state": "电力超车科技",
                            "mainline_process": "发酵",
                            "tomorrow_action": "只验证电力承接",
                        },
                        "overtake_window_summary": {
                            "window_state": "open",
                            "primary_line": "电力",
                            "rival_line": "科技",
                            "rival_slowdown": "科技冲高回落",
                            "own_line": "电力",
                            "own_stability": "电力承接继续",
                            "observation_maturity": "题材窗口打开",
                            "overtake_logic": "新线强于旧线",
                            "arena_boundary": "只看电力与科技的强弱互换",
                            "speed_gap": "电力速度领先",
                            "failure_condition": "电力承接断裂",
                            "action": "先看题材窗口是否延续",
                        },
                    },
                    "sector_internal_analysis": {
                        "sectors": [
                            {
                                "sector_name": "电力",
                                "core_anchor": "大唐发电",
                                "elastic_vehicle": "豫能控股",
                                "turnover_share_change": 1.8,
                            }
                        ]
                    },
                    "dragon_pullback_review": {
                        "leader": "大唐发电",
                        "second_confirmation": True,
                        "laggard_feedback": ["豫能控股"],
                    },
                    "selected_position_candidate": {"name": "豫能控股", "code": "001896", "sector": "电力"},
                    "position_decision": {"signal_grade": "0", "target_position_pct": 0},
                },
            )
        )

        expected_order = [
            "### 市场阶段",
            "### 资金结构",
            "### 板块关系",
            "### 超车 / 失速 / 窗口",
            "### 龙头 / 核心验证",
            "## 五、个股解读",
        ]
        for previous, current in zip(expected_order, expected_order[1:]):
            self.assertLess(rendered.index(previous), rendered.index(current))
        self.assertIn("| 周期标签 | 发酵 |", rendered)
        self.assertIn("| 市场资金 | 两市成交额回升至1.25万亿 |", rendered)
        self.assertIn("| 板块迁移 | 电力成交占比连续抬升 |", rendered)
        self.assertIn("| 主攻线 | 电力 | 科技、消费 | 电力超车科技 | 发酵 |", rendered)
        self.assertIn("| 题材窗口 | 发酵 | 题材窗口满足条件后 |", rendered)
        self.assertIn("| 电力 | 大唐发电 | 豫能控股 | 大唐发电二次确认；豫能控股低位补涨反哺核心辨识度 |", rendered)
        window_section = rendered[rendered.index("### 超车 / 失速 / 窗口") : rendered.index("### 龙头 / 核心验证")]
        for trading_window in ("09:30-09:35", "09:50-10:10", "14:30-14:55"):
            self.assertNotIn(trading_window, window_section)

    def test_front_page_market_sector_spine_comes_before_candidate_account_and_discipline_detail(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-06-05",
                market_research_snapshot={
                    "mainline_turnover_summary": {
                        "current_mainline": "电力",
                        "cycle_stage": "发酵",
                        "data_text": "市场成交额小幅修复",
                        "turnover_share_trend_summary": "电力资金迁移增强",
                    },
                    "two_layer_decision_payload": {
                        "opening_verdict": {
                            "position_stance": "0%不参与",
                            "final_object_identity": "观察对象",
                            "stock": {"name": "豫能控股", "code": "001896", "sector": "电力"},
                            "summary": "只保留观察对象",
                        },
                        "candidate_pool_verdict": {
                            "important_losers": [
                                {
                                    "stock": {"name": "上海石化", "code": "600688", "sector": "炼化及贸"},
                                    "dimension_results": {"funds_confirmation": "资金缺失"},
                                    "loss_reason": "资金确认不足",
                                }
                            ]
                        },
                    },
                    "selected_position_candidate": {"name": "豫能控股", "code": "001896", "sector": "电力"},
                    "position_decision": {"signal_grade": "0", "target_position_pct": 0},
                },
            )
        )

        self.assertLess(rendered.index("### 龙头 / 核心验证"), rendered.index("## 明日账户建议"))
        self.assertLess(rendered.index("### 龙头 / 核心验证"), rendered.index("## 一、交易纪律"))
        self.assertLess(rendered.index("### 龙头 / 核心验证"), rendered.index("## 五、个股解读"))

    def test_front_page_topic_window_keeps_topic_semantics_when_source_mentions_clock_time(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-06-05",
                market_research_snapshot={
                    "mainline_turnover_summary": {
                        "current_mainline": "电力",
                        "cycle_stage": "启动",
                        "overtake_window_summary": {
                            "window_state": "pending",
                            "primary_line": "电力",
                            "rival_line": "科技",
                            "own_line": "电力",
                            "rival_slowdown": "科技10点确认后失速",
                            "own_stability": "电力09:50确认承接",
                            "observation_maturity": "等10点确认后再看",
                            "failure_condition": "10点确认失败",
                            "action": "09:50确认",
                        },
                    },
                },
            )
        )

        window_section = rendered[rendered.index("### 超车 / 失速 / 窗口") : rendered.index("### 龙头 / 核心验证")]

        self.assertIn("| 题材窗口 | 启动 | 题材窗口待验证 | 题材窗口满足条件后 |", window_section)
        self.assertIn("题材窗口满足条件后", window_section)
        self.assertNotIn("09:50", window_section)
        self.assertNotIn("10:10", window_section)
        self.assertNotIn("10点", window_section)

    def test_front_page_market_sector_spine_compares_top_three_directions(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-06-05",
                market_research_snapshot={
                    "mainline_turnover_summary": {
                        "current_mainline": "电力",
                        "cycle_stage": "发酵",
                        "mainline_capacity_regime_summary": {
                            "primary_line": "电力",
                            "other_lines": "科技、消费",
                            "sector_relationship_state": "电力强于旧科技，消费仍是潜在超车线",
                            "mainline_process": "发酵",
                            "tomorrow_action": "比较前三个方向的承接",
                        },
                    },
                    "sector_internal_analysis": {
                        "sectors": [
                            {"sector_name": "电力", "core_anchor": "大唐发电", "elastic_vehicle": "豫能控股", "validation": "核心继续承接"},
                            {"sector_name": "科技", "core_anchor": "工业富联", "elastic_vehicle": "胜宏科技", "validation": "旧线观察回流"},
                            {"sector_name": "消费", "core_anchor": "中百集团", "elastic_vehicle": "桂发祥", "validation": "弹性待验证"},
                        ]
                    },
                },
            )
        )

        sector_section = rendered[rendered.index("### 板块关系") : rendered.index("### 超车 / 失速 / 窗口")]
        core_section = rendered[rendered.index("### 龙头 / 核心验证") : rendered.index("### 1. 周期日历主视图")]

        self.assertIn("| 主攻线 | 电力 | 科技、消费 | 电力强于旧科技，消费仍是潜在超车线 | 发酵 | 比较前三个方向的承接 |", sector_section)
        self.assertIn("| 竞争线 | 科技 | 电力 | 电力强于旧科技，消费仍是潜在超车线 | 发酵 | 比较前三个方向的承接 |", sector_section)
        self.assertIn("| 潜在超车线 | 消费 | 电力 | 电力强于旧科技，消费仍是潜在超车线 | 发酵 | 比较前三个方向的承接 |", sector_section)
        self.assertIn("| 电力 | 大唐发电 | 豫能控股 | 核心继续承接 |", core_section)
        self.assertIn("| 科技 | 工业富联 | 胜宏科技 | 旧线观察回流 |", core_section)
        self.assertIn("| 消费 | 中百集团 | 桂发祥 | 弹性待验证 |", core_section)

    def test_front_page_core_validation_falls_back_to_selection_workflow_candidates(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-06-29",
                market_research_snapshot={
                    "mainline_turnover_summary": {
                        "current_mainline": "化学制药",
                        "cycle_stage": "启动",
                        "mainline_capacity_regime_summary": {
                            "primary_line": "化学制药",
                            "other_lines": "医疗服务、国产芯片替代",
                            "sector_relationship_state": "双主线竞争",
                            "mainline_process": "启动",
                            "tomorrow_action": "不把每次轮动都当新主线，候选只保留判断样本",
                        },
                    },
                    "selection_workflow": {
                        "schema_version": "selection_workflow.v1",
                        "final": {
                            "position_pct": 100,
                            "execution_object": {"name": "深科技", "code": "000021", "sector": "消费电子"},
                        },
                        "candidate_pool": [
                            {
                                "name": "深科技",
                                "code": "000021",
                                "sector": "消费电子",
                                "status": "最终执行对象",
                                "entered_reason": "半导体进入板块候选；角色：趋势容量核心、板块锚/资金表领涨、量化弹性",
                            },
                            {
                                "name": "柏诚股份",
                                "code": "601133",
                                "sector": "专业工程",
                                "status": "过程候选",
                                "entered_reason": "化学制药板块锚定龙 / 2连板 / 趋势审美",
                            },
                            {
                                "name": "太龙药业",
                                "code": "600222",
                                "sector": "化学制药",
                                "status": "过程候选",
                                "entered_reason": "化学制药大阳线封板，作为弹性载体继续验证",
                            },
                        ],
                    },
                    "selected_position_candidate": {"name": "深科技", "code": "000021", "sector": "消费电子"},
                },
            )
        )

        core_section = rendered[rendered.index("### 龙头 / 核心验证") : rendered.index("### 1. 周期日历主视图")]
        self.assertIn("| 化学制药 | 柏诚股份(601133) | 太龙药业(600222) | 化学制药板块锚定龙 / 2连板 / 趋势审美 |", core_section)
        self.assertIn("| 国产芯片替代 | 深科技(000021) |", core_section)
        self.assertNotIn("| 化学制药 | 待补事实 | 待补事实 | 待验证 |", core_section)

    def test_front_page_derivation_chain_waits_until_after_market_spine(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-06-05",
                market_research_snapshot={
                    "mainline_turnover_summary": {"current_mainline": "电力", "cycle_stage": "发酵"},
                    "sniper_target_derivation": {
                        "schema_version": "sniper_target_derivation.v1",
                        "canonical_target": {"name": "豫能控股", "code": "001896", "sector": "电力", "role": "观察对象"},
                        "final_action": {"position_pct": 0, "action": "只观察，不新增参与"},
                        "compact_ascii": [
                            "原始候选",
                            "|",
                            "+-- 上海石化(600688): 过程候选 / 被替换",
                            "|",
                            "`-- 最终观察对象: 豫能控股(001896), 0%只观察",
                        ],
                    },
                },
            )
        )

        self.assertLess(rendered.index("### 市场阶段"), rendered.index("### 最终标的传导链"))
        self.assertLess(rendered.index("### 龙头 / 核心验证"), rendered.index("### 最终标的传导链"))

    def test_front_page_market_sector_spine_renders_missing_facts_without_crashing(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-06-05",
                market_research_snapshot={},
            )
        )

        self.assertIn("### 市场阶段", rendered)
        self.assertIn("### 资金结构", rendered)
        self.assertIn("### 板块关系", rendered)
        self.assertIn("### 超车 / 失速 / 窗口", rendered)
        self.assertIn("### 龙头 / 核心验证", rendered)
        self.assertLess(rendered.index("### 龙头 / 核心验证"), rendered.index("## 五、个股解读"))
        self.assertIn("待补事实", rendered)
        self.assertIn("待验证", rendered)

    def test_front_page_current_mainline_fields_downgrade_when_attack_evidence_is_chaotic(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-14",
                market_research_snapshot={
                    "target_date": "2026-05-14",
                    "current_mainline_history_record": {"date": "2026-05-14", "primary_mainline": "半导体", "market_state": "观察"},
                    "recent_mainline_history": [{"date": "2026-05-13", "primary_mainline": "电力", "market_state": "观察"}],
                    "pivot_mainline_rows": [
                        {
                            "date_range": "05-14",
                            "pivot_level": "日线中枢",
                            "pivot_range": "-",
                            "position": "中枢内",
                            "mainline": "半导体",
                            "mainline_degree": "周期主线",
                            "evolution": "观察",
                            "replacement": "接替电力",
                            "interpretation": "中枢是主线周期载体：[半导体] 承载在日线中枢，主线程度是周期主线，当前演化为观察；接替电力，动作上先看承接是否稳定。",
                        }
                    ],
                    "mainline_turnover_summary": {
                        "current_mainline": "半导体",
                        "mainline_attack_evidence_summary": {
                            "attack_state": "chaotic_rotation",
                            "primary_line": "",
                            "candidate_lines": ["化学制品", "养殖业", "家居用品"],
                            "confirmation_evidence": "多方向局部活跃但资金未明显胜出",
                        },
                        "turnover_share_trend_rows": [
                            {
                                "date": "2026-05-14",
                                "cycle_mainline": "半导体",
                                "daily_attack_line": "半导体",
                                "mainline_turnover": "4206.70亿",
                                "market_turnover": "33880.86亿",
                                "share": "12.4%",
                                "share_change": "待累计",
                                "interpretation": "主线成交额占比可用，继续观察占比抬升或回落",
                            }
                        ],
                    },
                },
            )
        )

        self.assertIn("| 05-14 | 日线中枢 | - | 中枢内 | 暂无确认主线 | 待确认 | 观察 | 待确认 | 中枢只记录候选方向，不把单日热度升级为周期主线；多方向局部活跃但资金未明显胜出。 |", rendered)
        self.assertRegex(
            rendered,
            r"\| 2026-05-14 \| "
            + _cycle_sector_label_pattern("半导体")
            + r" \| 4206\.70亿 \| 33880\.86亿 \| 12\.4% \| 待累计 \| 大周期延续 \| 主线成交额占比可用，继续观察占比抬升或回落 \|",
        )
        self.assertIn("| 0%不参与 | 不确定时不值得主动参与 | 暂无确认主线 | 暂无确认主攻线 |", rendered)
        self.assertNotIn("| 05-14 | 日线中枢 | - | 中枢内 | 半导体 | 周期主线 |", rendered)
        self.assertNotIn("| 2026-05-14 | 暂无确认主线 | 暂无确认主攻线 | 4206.70亿", rendered)
        self.assertNotIn("| 0%不参与 | 不确定时不值得主动参与 | 半导体 | 半导体 |", rendered)

    def test_front_page_maps_position_attack_grade_to_fixed_position_slabs(self):
        cases = [
            ("0", 0, "0%"),
            ("50", 50, "50%"),
            ("100", 100, "100%"),
        ]

        for signal_grade, target_position_pct, expected_label in cases:
            with self.subTest(signal_grade=signal_grade):
                rendered = "\n".join(
                    render_front_page_v2(
                        [],
                        target_date="2026-05-12",
                        market_research_snapshot={
                            "unique_action_target": {"name": "机器人一号", "code": "000001"},
                            "position_decision": {
                                "signal_grade": signal_grade,
                                "target_position_pct": target_position_pct,
                                "monthly_rhythm": {"max_position_pct": target_position_pct},
                            },
                        },
                    )
                )

                self.assertIn(f"| 进攻仓位三态 | {expected_label} |", rendered)

    def test_front_page_renders_position_state_machine_across_front_sections(self):
        cases = [
            (
                "0",
                0,
                {},
                "0%不参与",
                "0%无合格标的",
                "0%不参与",
                "0%：条件不满足",
            ),
            (
                "50",
                50,
                {"allow_attack_50_ready": True, "can_new_entry": False, "should_reduce": False},
                "50%条件执行",
                "50%条件执行对象",
                "50%条件执行",
                "50%：只做合格对象",
            ),
            (
                "100",
                100,
                {"can_new_entry": True},
                "100%核心进攻",
                "100%唯一核心对象",
                "100%核心进攻",
                "100%：唯一核心对象确认后进攻",
            ),
        ]
        for grade, target_position_pct, final_gate, execution_style, stock_state, discipline, action_text in cases:
            with self.subTest(grade=grade):
                rendered = "\n".join(
                    render_front_page_v2(
                        [],
                        target_date="2026-05-12",
                        market_research_snapshot={
                            "mainline_turnover_summary": {"current_mainline": "机器人"},
                            "unique_action_target": {
                                "name": "机器人一号",
                                "code": "000001",
                                "condition": "主线确认 + 承接 + 60分钟确认",
                            },
                            "position_decision": {
                                "signal_grade": grade,
                                "target_position_pct": target_position_pct,
                                "full_attack_ready": grade == "100",
                                "monthly_rhythm": {
                                    "month_mode": "ordinary_attack",
                                    "max_position_pct": target_position_pct,
                                },
                            },
                        },
                        final_gate=final_gate,
                        position_level="50%条件执行" if grade in ("50", "100") else "",
                    )
                )

                self.assertIn(f"| 当前状态 | {stock_state} |", rendered)
                self.assertIn(f"| {discipline} |", rendered)
                self.assertIn(f"| {execution_style} |", rendered)
                self.assertIn(action_text, rendered)
                self.assertNotIn("| 空仓 / 短线确认 |", rendered)

    def test_candidate_section_uses_observation_title_when_unique_target_is_empty(self):
        rendered = "\n".join(
            render_front_page_v2(
                [
                    "| 股票 | 代码 | 所属方向 | 标志性大阳线 | 近5日状态 | 承接 | 资金痕迹 | 明日资格 |",
                    "|------|------|----------|--------------|-----------|------|----------|----------|",
                    "| 富瀚微 | 300613 | 半导体 | 放量涨停 | 未完全爆发 | 明日验证承接 | 主线资金主动进攻 | 观察，等10点确认 |",
                ],
                target_date="2026-04-24",
                market_research_snapshot={
                    "mainline_turnover_summary": {
                        "current_mainline": "半导体",
                    },
                },
            )
        )

        self.assertIn("### 1. 个股裁决", rendered)
        front_stock_section = rendered[rendered.index("## 五、个股解读") : rendered.index("## 六、明日执行计划")]
        self.assertIn("| 观察对象 | 暂无 |", front_stock_section)
        self.assertIn("| 今日不买原因 | 没有观察对象，完整候选仅保留在附录和快照 |", front_stock_section)
        self.assertNotIn("| 股票 | 代码 | 所属方向 | 标志性大阳线 | 近5日状态 | 承接 | 资金痕迹 | 明日资格 |", front_stock_section)
        self.assertIn("| 只看观察对象 | 暂无 | 09:50-10:10 | 主线确认 + 承接 + 09:50-10:10窗口未同时满足 | 不满足回到0% |", rendered)

    def test_50_state_without_unique_target_falls_back_to_zero_not_condition_waiting(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-04-24",
                market_research_snapshot={
                    "mainline_turnover_summary": {"current_mainline": "半导体"},
                    "candidate_snapshot": {
                        "front_page": {
                            "unique_object": "暂无",
                            "backup_text": "富瀚微(300613)",
                            "no_buy_reason": "等待10点确认",
                            "trigger_condition": "10点确认；主线承接",
                            "failure_condition": "主线回落",
                        }
                    },
                    "position_decision": {
                        "signal_grade": "50",
                        "target_position_pct": 50,
                        "monthly_rhythm": {"month_mode": "earnings_defense", "max_position_pct": 50},
                    },
                },
                final_gate={"allow_attack_50_ready": True, "can_new_entry": False, "should_reduce": False},
                position_level="0%不参与",
            )
        )

        self.assertIn("| 观察对象 | 暂无 |", rendered)
        self.assertIn("| 当前状态 | 0%无合格标的 |", rendered)
        self.assertNotIn("50%执行", rendered)
        self.assertIn("| 0%不参与 |", rendered)

    def test_front_page_uses_extreme_conviction_target_as_tomorrow_action_target(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-19",
                market_research_snapshot={
                    "mainline_turnover_summary": {"current_mainline": "通信设备"},
                    "selected_position_candidate": {
                        "name": "汇源通信",
                        "code": "000586",
                        "sector": "通信设备",
                        "source_tier": "extreme_conviction",
                        "participation_window": "竞价表态 + 回封参与",
                        "participation_window_type": "auction_reseal",
                        "required_steps": ["竞价表态", "开盘前几分钟承接", "回封/打板"],
                        "fallback_state": "条件不满足回到0%",
                    },
                    "position_decision": {
                        "signal_grade": "50",
                        "target_position_pct": 50,
                        "participation_mode": "attack_50_preview",
                        "monthly_rhythm": {"month_mode": "ordinary_attack", "max_position_pct": 50},
                    },
                },
                final_gate={"can_new_entry": False, "should_reduce": True},
                position_level="0%不参与",
            )
        )

        self.assertIn("| 唯一对象 | 000586 汇源通信（通信设备） |", rendered)
        self.assertIn("| 当前状态 | 50%条件执行对象 |", rendered)
        self.assertIn("| 只看唯一对象 | 000586 汇源通信（通信设备） | 09:30-09:35 | 竞价表态 / 开盘前几分钟承接 / 回封/打板 | 条件不满足回到0%不参与 |", rendered)
        self.assertIn("| 50%条件执行", rendered)
        self.assertNotIn("| 唯一对象 | 暂无 |", rendered)

    def test_countertrend_attack_market_keeps_unique_target_observation_only(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-21",
                market_research_snapshot={
                    "mainline_turnover_summary": {
                        "current_mainline": "人形机器人",
                        "share_trend_label": "逆势试攻",
                        "conclusion": "人形机器人只是放量杀跌中的观察主攻线，不按周期主线切换处理",
                    },
                    "state_machine": {
                        "style_label": "放量杀跌",
                        "primary_action": "先防踩踏，等指数图形和主攻线承接同时修复后再给买入资格。",
                    },
                    "selected_position_candidate": {
                        "name": "华微电子",
                        "code": "600360",
                        "sector": "半导体",
                        "source_tier": "extreme_conviction",
                        "participation_window": "09:50-10:10",
                    },
                    "position_decision": {
                        "signal_grade": "50",
                        "target_position_pct": 50,
                    },
                },
                final_gate={"can_new_entry": False, "allow_attack_50_ready": True, "should_reduce": True},
                position_level="0%不参与",
            )
        )

        self.assertIn("| 观察对象 | 暂无 |", rendered)
        self.assertIn("| 当前状态 | 0%无合格标的 |", rendered)
        self.assertIn("| 只看观察对象 | 暂无 | 09:50-10:10 | 主线确认 + 承接 + 09:50-10:10窗口未同时满足 | 不满足回到0% |", rendered)
        self.assertIn("| 0%不参与 | 不确定时不值得主动参与 | 人形机器人 | 人形机器人 | 先看市场基底 | 暂无 | 0%不参与 |", rendered)
        self.assertNotIn("50%条件执行对象", rendered)
        self.assertNotIn("50%条件执行，只做合格对象", rendered)

    def test_anchor_reversal_downgraded_sample_is_not_surface_observation_target(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-06-05",
                market_research_snapshot={
                    "mainline_turnover_summary": {"current_mainline": "半导体"},
                    "selected_position_candidate": {
                        "name": "大有能源",
                        "code": "600403",
                        "sector": "煤炭开采",
                        "target_position_pct": 0,
                        "anchor_reversal_decision": "降级观察",
                        "candidate_role": "观察样本",
                        "relationship_to_anchor": "未证明比兆易创新(603986)更值得参与",
                        "final_action": "板块锚反推未通过，只观察承接，不新增参与",
                    },
                    "position_decision": {
                        "signal_grade": "0",
                        "target_position_pct": 0,
                    },
                },
                final_gate={"can_new_entry": False, "should_reduce": True},
                position_level="0%不参与",
            )
        )

        self.assertIn("| 观察对象 | 暂无 |", rendered)
        self.assertIn("| 只看观察对象 | 暂无 | 09:50-10:10 | 主线确认 + 承接 + 09:50-10:10窗口未同时满足 | 不满足回到0% |", rendered)
        self.assertNotIn("| 观察对象 | 600403 大有能源", rendered)
        self.assertNotIn("| 只看观察对象 | 600403 大有能源", rendered)

    def test_downgraded_final_resolution_watch_target_is_not_surface_observation_target(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-06-05",
                market_research_snapshot={
                    "mainline_turnover_summary": {"current_mainline": "半导体"},
                    "final_target_resolution": {
                        "watch_target": {
                            "name": "大有能源",
                            "code": "600403",
                            "sector": "煤炭开采",
                            "anchor_reversal_decision": "降级观察",
                            "candidate_role": "观察样本",
                            "candidate_layer": "watch_sample",
                            "execution_eligibility": "observation_only",
                        },
                        "capital_priority_decision": {
                            "capital_priority": "old_position_t",
                            "reason": "旧仓优先，过程样本只留证据",
                        },
                    },
                    "position_decision": {
                        "signal_grade": "0",
                        "target_position_pct": 0,
                    },
                },
                final_gate={"can_new_entry": False, "should_reduce": True},
                position_level="0%不参与",
            )
        )

        self.assertIn("| 观察对象 | 暂无 |", rendered)
        self.assertIn("| 只看观察对象 | 暂无 | 09:50-10:10 | 主线确认 + 承接 + 09:50-10:10窗口未同时满足 | 不满足回到0% |", rendered)
        self.assertNotIn("| 观察对象 | 600403 大有能源", rendered)
        self.assertNotIn("| 只看观察对象 | 600403 大有能源", rendered)

    def test_conflicting_explicit_process_observation_is_not_surface_observation_target(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-06-11",
                market_research_snapshot={
                    "mainline_turnover_summary": {"current_mainline": "国产芯片替代"},
                    "selection_workflow": {
                        "schema_version": "selection_workflow.v1",
                        "final": {
                            "execution_object": {},
                            "position_pct": 0,
                            "action_text": "0%不参与",
                            "source_node": "N8",
                        },
                    },
                    "final_target_resolution": {
                        "watch_target": {
                            "name": "和远气体",
                            "code": "002971",
                            "sector": "化学制品",
                            "front_observation_qualified": True,
                            "observation_layer": "process_observation",
                            "candidate_role": "过程候选",
                        },
                        "capital_priority_decision": {
                            "capital_priority": "wait",
                            "reason": "空仓等待",
                        },
                    },
                    "position_decision": {
                        "signal_grade": "0",
                        "target_position_pct": 0,
                    },
                },
                final_gate={"can_new_entry": False},
                position_level="0%不参与",
            )
        )

        self.assertIn("| 观察对象 | 暂无 |", rendered)
        self.assertIn("| 只看观察对象 | 暂无 | 09:50-10:10 | 主线确认 + 承接 + 09:50-10:10窗口未同时满足 | 不满足回到0% |", rendered)
        self.assertNotIn("| 观察对象 | 002971 和远气体", rendered)
        self.assertNotIn("| 只看观察对象 | 002971 和远气体", rendered)
        self.assertNotIn("观察对象：002971 和远气体", rendered)

    def test_zero_participation_surfaces_selected_candidate_as_conditional_observation(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-22",
                market_research_snapshot={
                    "mainline_turnover_summary": {"current_mainline": "元器件"},
                    "selected_position_candidate": {
                        "name": "风华高科",
                        "code": "000636",
                        "sector": "元器件",
                        "source_tier": "extreme_conviction",
                        "participation_window": "09:50-10:10",
                        "condition": "09:50-10:10站上37.62，且元器件/PCB链承接不塌",
                        "fallback_state": "不满足继续0%",
                    },
                    "position_decision": {
                        "signal_grade": "0",
                        "target_position_pct": 0,
                    },
                },
                final_gate={"can_new_entry": False, "should_reduce": True},
                position_level="0%不参与",
            )
        )

        self.assertIn("| 观察对象 | 000636 风华高科（元器件） |", rendered)
        self.assertIn("| 当前状态 | 0%条件观察 |", rendered)
        self.assertIn(
            "| 只看观察对象 | 000636 风华高科（元器件） | 09:50-10:10 | 09:50-10:10站上37.62，且元器件/PCB链承接不塌 | 不满足继续0% |",
            rendered,
        )
        self.assertIn(
            "| 0%不参与 | 不确定时不值得主动参与 | 元器件 | 元器件 | 先看市场基底 | 观察对象：000636 风华高科（元器件） | 0%不参与 | 盘前0%；只观察000636 风华高科（元器件），09:50-10:10站上37.62，且元器件/PCB链承接不塌成立才保留观察；未出现执行资格前不新增参与；不满足继续0% |",
            rendered,
        )
        self.assertNotIn("| 补位对象 | 风华高科", rendered)
        self.assertNotIn("| 只看唯一对象 | 暂无 |", rendered)

    def test_front_page_t0_card_caps_20260526_style_candidates(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-26",
                market_research_snapshot={
                    "account_profile": {"capital_text": "约1w账户"},
                    "selected_position_candidate": {
                        "name": "华天科技",
                        "code": "002185",
                        "sector": "半导体",
                    },
                    "position_decision": {
                        "signal_grade": "0",
                        "target_position_pct": 0,
                    },
                    "candidate_snapshot": {
                        "front_page": {
                            "backup_watch": [
                                {"label": "步步高(002251)", "sector": "超市连锁"},
                                {"label": "大众公用(600635)", "sector": "供气供热"},
                                {"label": "红星发展(600367)", "sector": "化工原料"},
                            ]
                        },
                        "extreme_conviction_list": [
                            {
                                "name": "步步高",
                                "code": "002251",
                                "sector": "超市连锁",
                                "sniper_role": "旧主买说法",
                            },
                            {
                                "name": "大众公用",
                                "code": "600635",
                                "sector": "供气供热",
                                "sniper_role": "旧补位说法",
                            },
                        ],
                    },
                },
            )
        )

        self.assertLess(rendered.index("## 明日账户建议"), rendered.index("## 一、交易纪律"))
        account_section = rendered[rendered.index("## 明日账户建议") : rendered.index("## 一、交易纪律")]
        self.assertIn("| 账户约束 | 约1w账户；未输入持仓，先确认旧仓；观察对象只进入复盘和下一份日报判断 |", account_section)
        self.assertIn("| 明日仓位 | 0%不参与 |", account_section)
        self.assertIn("| 明日动作 | 0%不参与；只保留观察对象，不新开 |", account_section)
        self.assertIn("| 观察对象 | 华天科技(002185)：观察对象，不是执行目标 |", account_section)
        self.assertIn("| 明日执行目标 | 持仓未输入，不能定义明日执行对象 |", account_section)
        self.assertIn("| 价格条件 | 开盘-5%附近不新开；-3%低开也只观察能否站回0轴/VWAP/MA强弱线；未出现执行资格前不新增参与 |", account_section)
        self.assertIn("| 新开仓上限 | 0 |", account_section)
        self.assertNotIn("| T0主对象 |", account_section)
        self.assertNotIn("条件观察", account_section)
        self.assertIn("| 今日不看 | 其他观察层只放附录观察，不同时盯多只，不为多个名单分散资金 |", account_section)
        self.assertNotIn("步步高", account_section)
        self.assertNotIn("大众公用", account_section)
        self.assertNotIn("红星发展", account_section)

    def test_front_page_account_card_respects_two_layer_execution_object(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-06-04",
                market_research_snapshot={
                    "account_profile": {"capital_text": "约1w账户"},
                    "selected_position_candidate": {
                        "name": "豫能控股",
                        "code": "001896",
                        "sector": "电力",
                    },
                    "position_decision": {
                        "signal_grade": "0",
                        "target_position_pct": 0,
                    },
                    "two_layer_decision_payload": {
                        "front_decision": {
                            "execution_identity": "明日执行对象",
                            "execution_object": {"name": "豫能控股", "code": "001896"},
                            "position_plan": "50%条件执行",
                        }
                    },
                },
            )
        )

        account_section = rendered[rendered.index("## 明日账户建议") : rendered.index("## 一、交易纪律")]
        self.assertIn("| 明日执行目标 | 豫能控股(001896)：已决定50%条件执行；不满足回到0% |", account_section)
        self.assertNotIn("不是执行对象", account_section)
        self.assertNotIn("不能定义明日执行对象", account_section)

    def test_front_page_uses_two_layer_execution_object_across_old_front_page_sections(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-06-04",
                market_research_snapshot={
                    "account_profile": {"capital_text": "约1w账户"},
                    "selected_position_candidate": {
                        "name": "豫能控股",
                        "code": "001896",
                        "sector": "电力",
                    },
                    "position_decision": {
                        "signal_grade": "0",
                        "target_position_pct": 0,
                    },
                    "two_layer_decision_payload": {
                        "front_decision": {
                            "execution_identity": "明日执行对象",
                            "execution_object": {"name": "豫能控股", "code": "001896"},
                            "position_plan": "50%条件执行",
                        }
                    },
                },
            )
        )

        self.assertIn("| 明日仓位 | 已决定50%条件执行；盘中不满足取消，回到0%不参与 |", rendered)
        self.assertIn("| 执行目标 | 豫能控股(001896) |", rendered)
        self.assertIn("| 明日唯一动作 | 标的 | 参与窗 | 条件 | 不满足怎么办 |", rendered)
        self.assertIn("| 只看明日执行对象 | 豫能控股(001896) | 09:30-09:35或09:50-10:10 |", rendered)
        self.assertIn("| 已决定50%条件执行；盘中不满足取消，回到0%不参与 | 不确定时不值得主动参与 |", rendered)
        self.assertIn("| 豫能控股(001896) | 50%条件执行 |", rendered)
        self.assertNotIn("观察" + "锚性质", rendered)
        self.assertNotIn("不是执行对象", rendered)
        self.assertNotIn("最终观察" + "锚", rendered)
        self.assertNotIn("只看观察对象", rendered)

    def test_front_page_closes_with_next_day_action_checklist(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-06-04",
                market_research_snapshot={
                    "unique_action_target": {
                        "name": "大唐发电",
                        "code": "601991",
                        "sector": "电力",
                        "participation_window": "09:50-10:10",
                        "condition": "主线承接 + 个股站回MA5",
                        "fallback_state": "不满足回到0%",
                    },
                },
                final_gate={"can_new_entry": True},
            )
        )

        final_section = rendered[rendered.index("## 七、最终结论") :]
        self.assertIn("### 明日行动清单", final_section)
        self.assertIn("| 仓位 | 50%条件执行 |", final_section)
        self.assertIn("| 最终对象 | 601991 大唐发电（电力） |", final_section)
        self.assertIn("| 执行/观察条件 | 09:50-10:10；主线承接 + 个股站回MA5 |", final_section)
        self.assertIn("| 不参与条件 | 不满足回到0%不参与 |", final_section)
        self.assertIn("| 旧仓处理 | 持仓未输入，执行前先确认旧仓情况 |", final_section)
        self.assertIn("| 复盘点 | 记录09:30-09:35、09:50-10:10、14:30-14:55三段是否满足条件 |", final_section)

    def test_next_day_action_checklist_does_not_use_stale_process_candidate_price_for_observation_target(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-06-04",
                market_research_snapshot={
                    "mainline_turnover_summary": {"current_mainline": "电力"},
                    "selected_position_candidate": {
                        "name": "豫能控股",
                        "code": "001896",
                        "sector": "电力",
                    },
                    "position_decision": {
                        "signal_grade": "0",
                        "target_position_pct": 0,
                        "trigger_text": "09:50-10:10站上3.38且不破3.21",
                    },
                    "sniper_target_derivation": {
                        "schema_version": "sniper_target_derivation.v1",
                        "canonical_target": {"name": "豫能控股", "code": "001896", "sector": "电力", "role": "观察对象"},
                        "final_action": {"position_pct": 0, "action": "只观察，不新增参与"},
                    },
                    "final_target_resolution": {
                        "watch_target": {"name": "豫能控股", "code": "001896", "sector": "电力"},
                        "capital_priority_decision": {"capital_priority": "wait"},
                    },
                },
                final_gate={"can_new_entry": False},
            )
        )

        final_section = rendered[rendered.index("### 明日行动清单") :]

        self.assertIn("| 最终对象 | 001896 豫能控股（电力） |", final_section)
        self.assertIn("| 执行/观察条件 | 09:50-10:10；主线承接 + 个股强弱重新确认 |", final_section)
        self.assertNotIn("3.38", final_section)
        self.assertNotIn("3.21", final_section)

    def test_front_page_t0_card_uses_final_action_state_for_new_entry_target(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-26",
                market_research_snapshot={
                    "unique_action_target": {"name": "大唐发电", "code": "601991", "sector": "电力"},
                },
                final_gate={"can_new_entry": True},
            )
        )

        account_section = rendered[rendered.index("## 明日账户建议") : rendered.index("## 一、交易纪律")]
        self.assertIn("| 明日仓位 | 50%条件执行 |", account_section)
        self.assertIn("| 明日动作 | 先确认旧仓情况；已决定执行；按昨晚预案检查执行资格；不满足取消，回到0%不参与 |", account_section)
        self.assertIn("| 明日执行目标 | 大唐发电(601991)：固定交易窗口条件 |", account_section)
        self.assertIn("| 持仓确认 | 持仓未输入，执行前先确认旧仓情况 |", account_section)
        self.assertNotIn("无旧仓", account_section)
        self.assertNotIn("确认没有旧仓", account_section)
        self.assertIn("| 价格条件 | 执行条件：MA5附近；按昨晚预案检查执行资格：09:50-10:10看承接；不满足取消，回到0%不参与 |", account_section)
        self.assertNotIn("命中才新开", account_section)
        self.assertIn("| 新开仓上限 | 1 |", account_section)
        self.assertNotIn("| T0主对象 |", account_section)
        self.assertNotIn("预计", account_section)
        self.assertIn("| 50%条件执行 |", rendered)

    def test_front_page_t0_card_uses_t0_main_object_when_no_yesterday_holding(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-28",
                market_research_snapshot={
                    "position_context_provided": True,
                    "account_profile": {"capital_text": "约1w账户"},
                    "selected_position_candidate": {
                        "name": "华电能源",
                        "code": "600726",
                        "sector": "电力",
                        "buy_ma_line": "MA7",
                    },
                    "position_decision": {
                        "signal_grade": "50",
                        "target_position_pct": 50,
                    },
                },
                final_gate={"allow_attack_50_ready": True},
            )
        )

        account_section = rendered[rendered.index("## 明日账户建议") : rendered.index("## 一、交易纪律")]
        self.assertIn("| 账户约束 | 约1w账户；无昨日持仓先看明日执行目标 |", account_section)
        self.assertIn("| 明日仓位 | 50%条件执行 |", account_section)
        self.assertIn("| 明日执行目标 | 华电能源(600726)：固定交易窗口条件 |", account_section)
        self.assertIn("| 备用观察 | 暂无 |", account_section)
        self.assertIn("| 价格条件 | 执行条件：MA7附近；按昨晚预案检查执行资格：09:50-10:10看承接；不满足取消，回到0%不参与 |", account_section)
        self.assertIn("| 明日动作 | 已决定执行；按昨晚预案检查执行资格；不满足取消，回到0%不参与 |", account_section)
        self.assertNotIn("命中才新开", account_section)
        self.assertNotIn("| 明日执行目标 | 无昨日持仓，不涉及明日执行对象 |", account_section)
        self.assertNotIn("预计", account_section)

    def test_front_page_t0_card_keeps_100pct_core_evidence(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-28",
                market_research_snapshot={
                    "position_context_provided": True,
                    "account_profile": {"capital_text": "约1w账户"},
                    "selected_position_candidate": {
                        "name": "华电能源",
                        "code": "600726",
                        "sector": "电力",
                        "buy_ma_line": "MA7",
                    },
                    "position_decision": {
                        "signal_grade": "100",
                        "target_position_pct": 100,
                        "monthly_rhythm": {"max_position_pct": 100},
                    },
                },
                final_gate={"allow_attack_50_ready": True},
            )
        )

        account_section = rendered[rendered.index("## 明日账户建议") : rendered.index("## 一、交易纪律")]
        self.assertIn("| 明日仓位 | 100%核心进攻 |", account_section)
        self.assertIn("| 明日执行目标 | 华电能源(600726)：固定交易窗口条件 |", account_section)
        self.assertIn("| 价格条件 | 执行条件：MA7附近；按昨晚预案检查执行资格：09:50-10:10看承接；不满足取消，回到0%不参与 |", account_section)
        self.assertIn("| 明日动作 | 已决定执行；按昨晚预案检查执行资格；不满足取消，回到0%不参与 |", account_section)
        self.assertNotIn("命中才新开", account_section)
        self.assertNotIn("| 明日仓位 | 50%条件执行 |", account_section)
        self.assertNotIn("预计", account_section)

    def test_front_page_reduce_only_candidate_renders_expected_50_preview(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-28",
                market_research_snapshot={
                    "account_profile": {"capital_text": "约1w账户"},
                    "selected_position_candidate": {
                        "name": "华电能源",
                        "code": "600726",
                        "sector": "电力",
                        "target_position_pct": 50,
                        "participation_window": "09:50-10:10",
                        "required_steps": ["竞价表态", "开盘前几分钟承接", "回封观察"],
                        "fallback_state": "不满足回到0%",
                    },
                    "position_decision": {
                        "participation_mode": "observe_0",
                        "target_position_pct": 0,
                        "signal_grade": "0",
                        "trigger_text": "09:50-10:10站上9.21且不破8.75",
                        "monthly_rhythm": {
                            "max_position_pct": 0,
                            "target_role": "observe",
                            "trend_invalid": True,
                        },
                    },
                    "state_machine": {"execution_bias": "reduce_only"},
                },
                final_gate={
                    "can_new_entry": False,
                    "should_reduce": True,
                    "allow_attack_50_ready": True,
                    "market_ice_point": False,
                },
            )
        )

        account_section = rendered[rendered.index("## 明日账户建议") : rendered.index("## 一、交易纪律")]
        self.assertIn("| 明日仓位 | 50%条件执行 |", account_section)
        self.assertIn("| 明日动作 | 先确认旧仓情况；已决定执行；按昨晚预案检查执行资格；不满足取消，回到0%不参与 |", account_section)
        self.assertIn("| 明日执行目标 | 华电能源(600726)：固定交易窗口条件 |", account_section)
        self.assertIn("| 持仓确认 | 持仓未输入，执行前先确认旧仓情况 |", account_section)
        self.assertNotIn("无旧仓", account_section)
        self.assertNotIn("确认没有旧仓", account_section)
        self.assertIn("| 价格条件 | 执行条件：MA5附近；按昨晚预案检查执行资格：09:50-10:10站上9.21且不破8.75；不满足取消，回到0%不参与 |", account_section)
        self.assertNotIn("命中才新开", account_section)
        self.assertNotIn("| 明日仓位 | 0%不参与 |", account_section)
        self.assertNotIn("| 观察对象 | 华电能源(600726)：观察" + "锚，不是执行对象 |", account_section)
        self.assertNotIn("预计", account_section)

    def test_front_page_t0_card_prioritizes_existing_position(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-26",
                market_research_snapshot={
                    "account_profile": {"capital_text": "约1w账户"},
                    "existing_position_summary": {
                        "has_position": True,
                        "summary": "已有昨日持仓晶方科技(603005)，先按持仓预案处理",
                    },
                    "selected_position_candidate": {
                        "name": "华天科技",
                        "code": "002185",
                        "sector": "半导体",
                    },
                    "position_decision": {
                        "signal_grade": "0",
                        "target_position_pct": 0,
                    },
                },
            )
        )

        account_section = rendered[rendered.index("## 明日账户建议") : rendered.index("## 一、交易纪律")]
        self.assertIn("| 账户约束 | 约1w账户；已有昨日持仓优先处理 |", account_section)
        self.assertIn("| 明日动作 | 先处理旧仓，不新增参与 |", account_section)
        self.assertIn("| 旧仓处理 | 已有昨日持仓晶方科技(603005)，先按持仓预案处理 |", account_section)
        self.assertIn("| 观察对象 | 华天科技(002185)：仅作观察对象 |", account_section)
        self.assertIn("| 新开仓上限 | 0 |", account_section)

    def test_front_page_t0_card_keeps_independent_etf_holding_separate_from_new_target(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-06-18",
                market_research_snapshot={
                    "account_profile": {"capital_text": "约1w账户"},
                    "existing_position_summary": {
                        "has_position": True,
                        "summary": "持有芯片ETF(159995)，33%仓位；持仓继续独立评估，不因新机会自动处理",
                    },
                    "selected_position_candidate": {
                        "name": "太极实业",
                        "code": "600667",
                        "sector": "半导体",
                    },
                    "position_decision": {
                        "signal_grade": "50",
                        "target_position_pct": 50,
                    },
                },
            )
        )

        account_section = rendered[rendered.index("## 明日账户建议") : rendered.index("## 一、交易纪律")]
        self.assertIn("| 账户约束 | 约1w账户；已有持仓继续独立评估 |", account_section)
        self.assertIn(
            "| 明日动作 | 持仓独立评估；太极实业(600667)按昨晚预案检查执行资格；不满足回到0%不参与 |",
            account_section,
        )
        self.assertIn("| 当前持仓 | 持有芯片ETF(159995)，33%仓位；持仓继续独立评估，不因新机会自动处理 |", account_section)
        self.assertIn("| 明日执行目标 | 太极实业(600667)：固定交易窗口条件 |", account_section)
        self.assertIn("| 新开仓上限 | 条件满足后1 |", account_section)
        self.assertNotIn("先处理旧仓", account_section)

    def test_front_page_t0_card_keeps_inferred_default_old_position_separate_from_new_target(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-07-02",
                market_research_snapshot={
                    "account_profile": {"capital_text": "约1w账户"},
                    "existing_position_summary": {
                        "has_position": True,
                        "summary": "持有太极实业(600667)，100%仓位；先看28.89能否守住，09:50-10:10收不回先卖；新仓是否叠加单独看Tb/Tc资格",
                        "inferred_from_previous_report": True,
                        "position_source": "previous_report_target_default_1x",
                        "default_position_pct": 100.0,
                    },
                    "selected_position_candidate": {
                        "name": "工业富联",
                        "code": "601138",
                        "sector": "通信设备",
                    },
                    "position_decision": {
                        "signal_grade": "50",
                        "target_position_pct": 50,
                    },
                    "final_target_resolution": {
                        "new_entry_target": {
                            "name": "工业富联",
                            "code": "601138",
                            "sector": "通信设备",
                        },
                        "account_exposure_plan": {
                            "schema_version": "full_or_empty_exposure.v1",
                            "old_position_1x": True,
                            "new_entry_1x": True,
                            "possible_intraday_overlap_2x": True,
                            "max_runtime_exposure_x": 2,
                            "old_position_label": "太极实业(600667)",
                            "new_entry_label": "工业富联(601138)",
                            "policy": "旧仓1x + 新买1x；若旧仓未先卖且新买成交，盘中交叉最高2x",
                        },
                        "capital_priority_decision": {
                            "capital_priority": "new_entry",
                            "reason": "旧仓默认1x按旧路径处理；新开仓对象具备执行资格时，按固定交易窗口确认，可与旧仓分账判断",
                        },
                    },
                },
                final_gate={"can_new_entry": True},
            )
        )

        account_section = rendered[rendered.index("## 明日账户建议") : rendered.index("## 一、交易纪律")]
        self.assertIn("| 账户约束 | 约1w账户；已有持仓继续独立评估 |", account_section)
        self.assertIn(
            "| 明日动作 | 持仓独立评估；工业富联(601138)按昨晚预案检查执行资格；不满足回到0%不参与 |",
            account_section,
        )
        self.assertIn(
            "| 当前持仓 | 持有太极实业(600667)，100%仓位；先看28.89能否守住，09:50-10:10收不回先卖；新仓是否叠加单独看Tb/Tc资格 |",
            account_section,
        )
        self.assertIn("| 账户风险暴露 | 旧仓1x + 新买1x；若旧仓未先卖且新买成交，盘中交叉最高2x |", account_section)
        self.assertIn("| 明日执行目标 | 工业富联(601138)：固定交易窗口条件 |", account_section)
        self.assertIn("| 新开仓上限 | 条件满足后1 |", account_section)
        self.assertNotIn("先处理旧仓", account_section)

    def test_front_page_account_advice_uses_knowledge_hit_for_unbuyable_core(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-29",
                market_research_snapshot={
                    "account_profile": {
                        "capital_text": "约1w账户",
                        "cash_available": 9800,
                    },
                    "selected_position_candidate": {
                        "name": "强核心",
                        "code": "000001",
                        "sector": "半导体",
                        "identity": "市场核心",
                        "one_lot_amount": 18000,
                    },
                    "position_decision": {
                        "signal_grade": "50",
                        "target_position_pct": 50,
                    },
                    "knowledge_hits": [
                        {
                            "knowledge_id": "account.unbuyable-core-anchor",
                            "title": "实际不可买不降低市场身份",
                            "report_slot": "账户约束",
                            "impact": "实际不可买只影响当前账户参与，不降低市场核心、池内身份或板块锚价值。",
                        }
                    ],
                },
            )
        )

        account_section = rendered[rendered.index("## 明日账户建议") : rendered.index("## 一、交易纪律")]
        self.assertIn("| 明日仓位 | 0%不参与 |", account_section)
        self.assertIn("| 明日动作 | 当前账户不参与；强核心仍保留市场核心观察 |", account_section)
        self.assertIn("| 观察对象 | 强核心(000001)：当前账户买不了一手，只保留观察 |", account_section)
        self.assertIn("| 明日执行目标 | 持仓未输入，不能定义明日执行对象 |", account_section)
        self.assertIn("| 新开仓上限 | 0 |", account_section)
        self.assertNotIn("| T0主对象 |", account_section)
        self.assertIn("| 经验库依据 | 实际不可买不降低市场身份 |", account_section)
        self.assertIn("| 当前状态 | 0%条件观察 |", rendered)
        self.assertIn("| 明日观察动作 | 标的 | 观察窗 | 条件 | 不满足怎么办 |", rendered)
        self.assertIn("| 只看观察对象 | 000001 强核心（半导体） | 09:50-10:10 | 主线承接 + 个股强弱重新确认 | 不满足继续0% |", rendered)
        self.assertIn(
            "| 0%不参与 | 不确定时不值得主动参与 | - | - | 先看市场基底 | 观察对象：000001 强核心（半导体） | 0%不参与 |",
            rendered,
        )
        self.assertNotIn("50%条件执行，只做合格对象", rendered)

    def test_front_page_account_advice_uses_cash_and_one_lot_without_knowledge_hit(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-29",
                market_research_snapshot={
                    "account_profile": {
                        "capital_text": "约1w账户",
                        "cash_available": 9800,
                    },
                    "selected_position_candidate": {
                        "name": "强核心",
                        "code": "000001",
                        "sector": "半导体",
                        "identity": "市场核心",
                        "one_lot_amount": 18000,
                    },
                    "position_decision": {
                        "signal_grade": "50",
                        "target_position_pct": 50,
                    },
                },
            )
        )

        account_section = rendered[rendered.index("## 明日账户建议") : rendered.index("## 一、交易纪律")]
        self.assertIn("| 明日仓位 | 0%不参与 |", account_section)
        self.assertIn("| 明日动作 | 当前账户不参与；强核心仍保留市场核心观察 |", account_section)
        self.assertIn("| 观察对象 | 强核心(000001)：当前账户买不了一手，只保留观察 |", account_section)
        self.assertNotIn("| T0主对象 |", account_section)
        self.assertNotIn("| 经验库依据 |", account_section)

    def test_front_page_account_advice_uses_tradable_proxy_for_unbuyable_core(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-06-03",
                market_research_snapshot={
                    "account_profile": {
                        "capital_text": "约1w账户",
                        "cash_available": 9800,
                    },
                    "mainline_turnover_summary": {"current_mainline": "通信设备"},
                    "selected_position_candidate": {
                        "name": "中际旭创",
                        "code": "300308",
                        "sector": "通信设备",
                        "identity": "市场核心",
                        "one_lot_amount": 16800,
                    },
                    "position_decision": {
                        "signal_grade": "50",
                        "target_position_pct": 50,
                    },
                    "final_target_resolution": {
                        "new_entry_target": {
                            "name": "中际旭创",
                            "code": "300308",
                            "sector": "通信设备",
                            "identity": "市场核心",
                            "one_lot_amount": 16800,
                            "participation_window": "09:50-10:10",
                        },
                        "watch_target": {
                            "name": "中际旭创",
                            "code": "300308",
                            "sector": "通信设备",
                            "identity": "市场核心",
                            "one_lot_amount": 16800,
                        },
                        "process_target": {
                            "name": "中际旭创",
                            "code": "300308",
                            "sector": "通信设备",
                            "identity": "市场核心",
                            "one_lot_amount": 16800,
                        },
                        "tradable_proxy_target": {
                            "name": "通信ETF",
                            "code": "515880",
                            "sector": "通信设备",
                            "proxy_effect_type": "行业板块效应",
                            "proxy_reason": "跟踪通信设备方向，不退到弱跟风个股",
                            "condition": "通信设备承接继续",
                            "participation_window": "09:50-10:10",
                            "fallback_state": "不满足回到0%",
                        },
                        "display_target": {
                            "name": "通信ETF",
                            "code": "515880",
                            "sector": "通信设备",
                            "proxy_effect_type": "行业板块效应",
                            "condition": "通信设备承接继续",
                            "participation_window": "09:50-10:10",
                            "fallback_state": "不满足回到0%",
                        },
                        "capital_priority_decision": {
                            "capital_priority": "tradable_proxy",
                            "reason": "目标标的中际旭创(300308)，小资金账户可用通信ETF(515880)替代",
                        },
                    },
                },
            )
        )

        account_section = rendered[rendered.index("## 明日账户建议") : rendered.index("## 一、交易纪律")]
        stock_section = rendered[rendered.index("## 五、个股解读") : rendered.index("## 六、明日执行计划")]
        execution_section = rendered[rendered.index("## 六、明日执行计划") : rendered.index("## 七、最终结论")]
        final_section = rendered[rendered.index("## 七、最终结论") :]

        self.assertIn("| 明日仓位 | 50%条件执行 |", account_section)
        self.assertIn("| 明日动作 | 目标标的中际旭创(300308)，小资金账户可用通信ETF(515880)替代 |", account_section)
        self.assertIn("| 明日执行目标 | 通信ETF(515880)：行业板块效应替代表达 |", account_section)
        self.assertIn("| 观察对象 | 中际旭创(300308)：市场核心保留观察 |", account_section)
        self.assertIn("| 新开仓上限 | 1 |", account_section)
        self.assertIn("| 执行目标 | 515880 通信ETF（通信设备） |", stock_section)
        self.assertIn("| 明日唯一动作 | 标的 | 参与窗 | 条件 | 不满足怎么办 |", execution_section)
        self.assertIn("| 只看唯一对象 | 515880 通信ETF（通信设备） | 09:50-10:10 | 通信设备承接继续 | 不满足回到0%不参与 |", execution_section)
        self.assertIn("| 50%条件执行，只做合格对象 |", final_section)
        self.assertIn("515880 通信ETF（通信设备）", final_section)
        self.assertNotIn("| 观察对象 | 中际旭创(300308)：当前账户买不了一手，只保留观察 |", account_section)

    def test_front_page_final_zero_action_blocks_tradable_proxy_execution(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-06-03",
                market_research_snapshot={
                    "account_profile": {
                        "capital_text": "约1w账户",
                        "cash_available": 9800,
                    },
                    "mainline_turnover_summary": {"current_mainline": "通信设备"},
                    "selected_position_candidate": {
                        "name": "中际旭创",
                        "code": "300308",
                        "sector": "通信设备",
                        "identity": "市场核心",
                        "one_lot_amount": 16800,
                    },
                    "position_decision": {
                        "signal_grade": "50",
                        "target_position_pct": 50,
                    },
                    "final_target_resolution": {
                        "new_entry_target": {
                            "name": "中际旭创",
                            "code": "300308",
                            "sector": "通信设备",
                            "identity": "市场核心",
                            "one_lot_amount": 16800,
                            "participation_window": "09:50-10:10",
                        },
                        "watch_target": {
                            "name": "中际旭创",
                            "code": "300308",
                            "sector": "通信设备",
                            "identity": "市场核心",
                            "one_lot_amount": 16800,
                        },
                        "tradable_proxy_target": {
                            "name": "通信ETF",
                            "code": "515880",
                            "sector": "通信设备",
                            "proxy_effect_type": "行业板块效应",
                            "condition": "通信设备承接继续",
                            "participation_window": "09:50-10:10",
                            "fallback_state": "不满足回到0%",
                        },
                        "display_target": {
                            "name": "通信ETF",
                            "code": "515880",
                            "sector": "通信设备",
                            "proxy_effect_type": "行业板块效应",
                            "condition": "通信设备承接继续",
                            "participation_window": "09:50-10:10",
                            "fallback_state": "不满足回到0%",
                        },
                        "capital_priority_decision": {
                            "capital_priority": "tradable_proxy",
                            "reason": "目标标的中际旭创(300308)，小资金账户可用通信ETF(515880)替代",
                        },
                    },
                },
                final_gate={"final_action": "空仓等待，禁止参与；若你有仓位，只做退出不做幻想"},
            )
        )

        account_section = rendered[rendered.index("## 明日账户建议") : rendered.index("## 一、交易纪律")]
        stock_section = rendered[rendered.index("## 五、个股解读") : rendered.index("## 六、明日执行计划")]
        execution_section = rendered[rendered.index("## 六、明日执行计划") : rendered.index("## 七、最终结论")]
        final_section = rendered[rendered.index("## 七、最终结论") :]

        self.assertIn("| 明日仓位 | 0%不参与 |", account_section)
        self.assertIn("| 明日动作 | 当前账户不参与；中际旭创仍保留市场核心观察 |", account_section)
        self.assertIn("| 观察对象 | 中际旭创(300308)：当前账户买不了一手，只保留观察 |", account_section)
        self.assertIn("| 明日仓位 | 0%不参与 |", stock_section)
        self.assertIn("| 执行目标 | 无 |", stock_section)
        self.assertIn("| 只看观察对象 | 300308 中际旭创（通信设备） |", execution_section)
        self.assertIn("| 0%不参与 | 不确定时不值得主动参与 | 通信设备 | 通信设备 | 先看市场基底 | 观察对象：300308 中际旭创（通信设备） | 0%不参与 |", final_section)
        self.assertNotIn("50%条件执行", account_section + stock_section + execution_section + final_section)
        self.assertNotIn("执行目标 | 515880 通信ETF", stock_section)
        self.assertNotIn("| 只看唯一对象 | 515880 通信ETF", execution_section)

    def test_front_page_t0_card_does_not_assume_no_holding_without_account_context(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-28",
                market_research_snapshot={
                    "account_profile": {"capital_text": "约1w账户"},
                    "selected_position_candidate": {
                        "name": "江海股份",
                        "code": "002484",
                        "sector": "元件",
                    },
                    "position_decision": {
                        "signal_grade": "0",
                        "target_position_pct": 0,
                    },
                },
                final_gate={"can_new_entry": False},
                position_level="0%不参与",
            )
        )

        account_section = rendered[rendered.index("## 明日账户建议") : rendered.index("## 一、交易纪律")]
        self.assertIn("| 账户约束 | 约1w账户；未输入持仓，先确认旧仓；观察对象只进入复盘和下一份日报判断 |", account_section)
        self.assertNotIn("无昨日持仓", account_section)

    def test_front_page_zero_participation_keeps_candidate_as_observation_not_t0(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-28",
                market_research_snapshot={
                    "account_profile": {"capital_text": "约1w账户"},
                    "selected_position_candidate": {
                        "name": "江海股份",
                        "code": "002484",
                        "sector": "元件",
                        "target_position_pct": 50,
                        "participation_window": "09:50-10:10",
                        "fallback_state": "不满足回到0%",
                    },
                    "position_decision": {
                        "signal_grade": "0",
                        "target_position_pct": 0,
                        "monthly_rhythm": {
                            "max_position_pct": 0,
                            "market_ice_point": True,
                            "reason": "冰点防守",
                        },
                    },
                },
                final_gate={"can_new_entry": False, "market_ice_point": True},
                position_level="0%不参与",
            )
        )

        account_section = rendered[rendered.index("## 明日账户建议") : rendered.index("## 一、交易纪律")]
        self.assertIn("| 明日仓位 | 0%不参与 |", account_section)
        self.assertIn("| 明日动作 | 0%不参与；只保留观察对象，不新开 |", account_section)
        self.assertIn("| 观察对象 | 江海股份(002484)：观察对象，不是执行目标 |", account_section)
        self.assertNotIn("| T0主对象 |", account_section)

    def test_front_page_t0_card_shows_position_decision_for_real_small_account_holding(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-26",
                market_research_snapshot={
                    "account_profile": {
                        "capital_text": "1w本金；总资产10126.52；当日盈利126.52（+1.27%）",
                    },
                    "existing_position_summary": {
                        "has_position": True,
                        "summary": "持有晶方科技(603005)1手，成本43.835；先看45.10能否守住，09:50-10:10收不回先卖；新开仓0手",
                    },
                    "selected_position_candidate": {
                        "name": "华天科技",
                        "code": "002185",
                        "sector": "半导体",
                    },
                    "position_decision": {
                        "signal_grade": "0",
                        "target_position_pct": 0,
                    },
                },
            )
        )

        account_section = rendered[rendered.index("## 明日账户建议") : rendered.index("## 一、交易纪律")]
        self.assertIn("| 账户约束 | 1w本金；总资产10126.52；当日盈利126.52（+1.27%）；已有昨日持仓优先处理 |", account_section)
        self.assertIn("| 明日动作 | 先处理旧仓，不新增参与 |", account_section)
        self.assertIn(
            "| 旧仓处理 | 持有晶方科技(603005)1手，成本43.835；先看45.10能否守住，09:50-10:10收不回先卖；新开仓0手 |",
            account_section,
        )
        self.assertIn("| 观察对象 | 华天科技(002185)：仅作观察对象 |", account_section)
        self.assertIn("| 新开仓上限 | 0 |", account_section)

    def test_front_page_final_no_new_entry_overrides_positive_position_decision(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-06-03",
                market_research_snapshot={
                    "selected_position_candidate": {
                        "name": "长电科技",
                        "code": "600584",
                        "sector": "半导体",
                        "participation_window": "09:30-09:35",
                        "condition": "半导体承接继续",
                        "fallback_state": "不满足继续0%",
                    },
                    "position_decision": {
                        "signal_grade": "100",
                        "target_position_pct": 100,
                        "monthly_rhythm": {
                            "max_position_pct": 100,
                            "reason": "候选强，但最终条件要求不新增参与",
                        },
                    },
                },
                final_gate={
                    "can_new_entry": False,
                    "should_reduce": True,
                    "final_action": "空仓等待，不新增参与；若有仓位只处理旧仓",
                },
                position_level="0%不参与",
            )
        )

        account_section = rendered[rendered.index("## 明日账户建议") : rendered.index("## 一、交易纪律")]
        stock_section = rendered[rendered.index("## 五、个股解读") : rendered.index("## 六、明日执行计划")]
        execution_section = rendered[rendered.index("## 六、明日执行计划") : rendered.index("## 七、最终结论")]
        final_section = rendered[rendered.index("## 七、最终结论") :]

        self.assertIn("| 明日仓位 | 0%不参与 |", account_section)
        self.assertIn("| 明日动作 | 0%不参与；只保留观察对象，不新开 |", account_section)
        self.assertIn("| 进攻仓位三态 | 0% |", rendered)
        self.assertIn("| 明日最大仓位 | 0% |", rendered)
        self.assertIn("| 观察对象 | 600584 长电科技（半导体） |", stock_section)
        self.assertIn("| 明日观察动作 | 标的 | 观察窗 | 条件 | 不满足怎么办 |", execution_section)
        self.assertNotIn("| 明日唯一动作 |", execution_section)
        self.assertNotIn("回封/打板", execution_section)
        self.assertIn("| 0%不参与 |", final_section)
        self.assertIn("| 0%不参与 |", final_section)
        self.assertNotIn("100%核心进攻", final_section)

    def test_zero_participation_observation_anchor_ignores_positive_required_steps(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-06-04",
                market_research_snapshot={
                    "selected_position_candidate": {
                        "name": "豫能控股",
                        "code": "001896",
                        "sector": "电力",
                        "participation_window": "09:50-10:10",
                        "participation_window_type": "auction_reseal",
                        "required_steps": ["竞价表态", "开盘前几分钟承接", "回封/打板"],
                        "fallback_state": "不满足回到0%",
                    },
                    "position_decision": {
                        "signal_grade": "0",
                        "target_position_pct": 0,
                    },
                    "existing_position_summary": {
                        "has_position": True,
                        "summary": "持有华电辽能(600396)，200股，今日做T；新开仓0手",
                    },
                },
                final_gate={
                    "can_new_entry": False,
                    "should_reduce": True,
                    "old_position_priority": True,
                    "final_action": "先处理旧仓，不新增参与；新强对象只保留观察" + "锚",
                },
            )
        )

        execution_section = rendered[rendered.index("## 六、明日执行计划") : rendered.index("## 七、最终结论")]

        self.assertIn(
            "| 只看观察对象 | 001896 豫能控股（电力） | 09:50-10:10 | 主线承接 + 个股强弱重新确认 | 不满足回到0% |",
            execution_section,
        )
        self.assertNotIn("回封/打板", execution_section)
        self.assertNotIn("竞价表态 + 开盘前几分钟", execution_section)

    def test_zero_participation_final_summary_prefers_position_trigger_text(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-25",
                market_research_snapshot={
                    "mainline_turnover_summary": {"current_mainline": "半导体"},
                    "selected_position_candidate": {
                        "name": "新洁能",
                        "code": "605111",
                        "sector": "半导体",
                        "condition": "当前主线处于退潮，环境已转撤退，先退出，等下一轮新脉冲。",
                        "fallback_state": "不满足继续0%",
                    },
                    "position_decision": {
                        "signal_grade": "0",
                        "target_position_pct": 0,
                        "trigger_text": "09:50-10:10站上63.22且不破60.06",
                    },
                },
                final_gate={"can_new_entry": False, "should_reduce": True},
                position_level="0%不参与",
            )
        )

        self.assertIn(
            "| 0%不参与 | 不确定时不值得主动参与 | 半导体 | 半导体 | 先看市场基底 | 观察对象：605111 新洁能（半导体） | 0%不参与 | 盘前0%；只观察605111 新洁能（半导体），09:50-10:10站上63.22且不破60.06成立才保留观察；未出现执行资格前不新增参与；不满足继续0% |",
            rendered,
        )
        self.assertNotIn("环境已转撤退，先退出", rendered.split("## 七、最终结论", 1)[-1])

    def test_zero_participation_final_summary_ignores_trigger_text_for_different_named_stock(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-06-04",
                market_research_snapshot={
                    "mainline_turnover_summary": {"current_mainline": "电力"},
                    "selected_position_candidate": {
                        "name": "豫能控股",
                        "code": "001896",
                        "sector": "电力",
                    },
                    "position_decision": {
                        "signal_grade": "0",
                        "target_position_pct": 0,
                        "trigger_text": "上海石化09:50-10:10站上3.38且不破3.21",
                    },
                    "final_target_resolution": {
                        "watch_target": {"name": "豫能控股", "code": "001896", "sector": "电力"},
                        "capital_priority_decision": {"capital_priority": "wait"},
                    },
                },
                final_gate={"can_new_entry": False},
            )
        )

        final_section = rendered[rendered.index("## 七、最终结论") :]

        self.assertIn("观察对象：001896 豫能控股（电力）", final_section)
        self.assertIn("主线承接 + 个股强弱重新确认", final_section)
        self.assertNotIn("上海石化", final_section)
        self.assertNotIn("3.38", final_section)
        self.assertNotIn("3.21", final_section)

    def test_zero_participation_does_not_surface_sniper_rows_as_actionable(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-21",
                market_research_snapshot={
                    "mainline_turnover_summary": {
                        "current_mainline": "混沌轮动",
                        "share_trend_label": "放量杀跌",
                    },
                    "candidate_snapshot": {
                        "extreme_conviction_list": [
                            {
                                "name": "豫能控股",
                                "code": "001896",
                                "sector": "火力发电",
                                "sniper_role": "明日主买对象",
                                "leader_speed_tier": "极致加速龙头",
                                "final_risk_review": {"status": "通过"},
                            },
                            {
                                "name": "浙江世宝",
                                "code": "002703",
                                "sector": "汽车配件",
                                "sniper_role": "明日补位对象",
                                "leader_speed_tier": "极致加速龙头",
                                "final_risk_review": {"status": "通过"},
                            },
                        ],
                    },
                    "position_decision": {
                        "signal_grade": "0",
                        "target_position_pct": 0,
                    },
                },
                final_gate={"can_new_entry": False, "should_reduce": True},
                position_level="0%不参与",
            )
        )

        self.assertIn("| 观察对象 | 暂无 |", rendered)
        self.assertIn("| 当前状态 | 0%无合格标的 |", rendered)
        self.assertIn("### 2. 明日候选观察", rendered)
        self.assertIn("| 角色 | 标的 | 速度档 | 买点线 | 卖点线 | 承接修复条件 | 观察复核 | 观察窗 |", rendered)
        self.assertIn("| 暂无 | - | - | - | - | - | - | - |", rendered)
        self.assertIn("| 只保留观察对象和备用观察 | 完整候选单保留在结构化快照与附录 | 最终0%时只观察，不做新增参与；观察对象只进入复盘和下一份日报判断 |", rendered)
        self.assertIn("| 明日观察动作 | 标的 | 观察窗 | 条件 | 不满足怎么办 |", rendered)
        self.assertNotIn("### 2. 明日主买与补位", rendered)
        self.assertNotIn("| 明日唯一动作 | 标的 | 参与窗 | 条件 | 不满足怎么办 |", rendered)
        self.assertIn("| 暂无 | - | - | - | - | - | - | - |", rendered)
        self.assertNotIn("001896 豫能控股", rendered)
        self.assertNotIn("002703 浙江世宝", rendered)
        self.assertNotIn("| 明日主买对象 |", rendered)
        self.assertNotIn("| 明日补位对象 |", rendered)
        self.assertIn("| 09:30-09:35 | 只看跌停扩散、主攻线承接和观察对象是否出现 | 无 | 弱仓/错仓先降风险 | 观察，不抢开盘 |", rendered)
        self.assertNotIn("买后用30分钟结构止损", rendered)
        self.assertNotIn("合格则参与，不合格回到0%", rendered)
        self.assertNotIn("买后用30分钟结构止损", rendered)

    def test_front_page_renders_sniper_primary_backup_speed_and_risk_review(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-21",
                market_research_snapshot={
                    "mainline_turnover_summary": {"current_mainline": "电力"},
                    "selected_position_candidate": {
                        "name": "大唐发电",
                        "code": "601991",
                        "sector": "电力",
                        "source_tier": "extreme_conviction",
                        "participation_window": "竞价表态 + 回封参与",
                        "participation_window_type": "auction_reseal",
                        "required_steps": ["竞价表态", "开盘前几分钟承接", "回封/打板"],
                        "fallback_state": "条件不满足回到0%",
                    },
                    "candidate_snapshot": {
                        "extreme_conviction_list": [
                            {
                                "name": "大唐发电",
                                "code": "601991",
                                "sector": "电力",
                                "sniper_role": "明日主买对象",
                                "leader_speed_tier": "极致加速龙头",
                                "buy_ma_line": "MA3",
                                "sell_ma_line": "MA5",
                                "acceptance_repair_required": "缩量回撤到MA3附近，站回VWAP",
                                "final_risk_review": {"status": "通过"},
                                "participation_window": "竞价表态 + 回封参与",
                            },
                            {
                                "name": "华电辽能",
                                "code": "600396",
                                "sector": "电力",
                                "sniper_role": "明日补位对象",
                                "leader_speed_tier": "大容量趋势龙头",
                                "buy_ma_line": "MA10",
                                "sell_ma_line": "MA20",
                                "acceptance_repair_required": "缩量回撤到MA10附近，站回VWAP",
                                "final_risk_review": {"status": "通过"},
                                "participation_window": "09:50-10:10",
                            },
                        ],
                    },
                    "position_decision": {
                        "signal_grade": "50",
                        "target_position_pct": 50,
                        "participation_mode": "attack_50_preview",
                        "monthly_rhythm": {"month_mode": "ordinary_attack", "max_position_pct": 50},
                    },
                },
                final_gate={"can_new_entry": False, "should_reduce": True},
                position_level="0%不参与",
            )
        )

        self.assertIn("### 2. 明日主买与补位", rendered)
        self.assertIn("| 明日主买对象 | 601991 大唐发电（电力） | 极致加速龙头 | MA3 | MA5 | 缩量回撤到MA3附近，站回VWAP | 通过 | 竞价表态 + 回封参与 |", rendered)
        self.assertIn("| 明日补位对象 | 600396 华电辽能（电力） | 大容量趋势龙头 | MA10 | MA20 | 缩量回撤到MA10附近，站回VWAP | 通过 | 09:50-10:10 |", rendered)

    def test_front_page_reads_sniper_candidates_from_top_level_snapshot_fallback(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-21",
                market_research_snapshot={
                    "mainline_turnover_summary": {"current_mainline": "电力"},
                    "selected_position_candidate": {
                        "name": "大唐发电",
                        "code": "601991",
                        "sector": "电力",
                    },
                    "position_decision": {
                        "signal_grade": "50",
                        "target_position_pct": 50,
                    },
                    "extreme_conviction_list": [
                        {
                            "name": "大唐发电",
                            "code": "601991",
                            "sector": "电力",
                            "sniper_role": "明日主买对象",
                            "leader_speed_tier": "极致加速龙头",
                            "buy_ma_line": "MA3",
                            "sell_ma_line": "MA5",
                            "acceptance_repair_required": "缩量回撤到MA3附近，站回VWAP",
                            "final_risk_review": {"status": "通过"},
                            "participation_window": "竞价表态 + 回封参与",
                        }
                    ],
                },
                final_gate={"can_new_entry": False, "should_reduce": True},
                position_level="0%不参与",
            )
        )

        self.assertIn("| 明日主买对象 | 601991 大唐发电（电力） | 极致加速龙头 | MA3 | MA5 |", rendered)

    def test_sniper_rows_follow_unique_action_target_when_final_target_differs(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-21",
                market_research_snapshot={
                    "unique_action_target": {
                        "name": "华微电子",
                        "code": "600360",
                        "sector": "半导体",
                        "participation_window": "09:50-10:10",
                    },
                    "candidate_snapshot": {
                        "extreme_conviction_list": [
                            {
                                "name": "豫能控股",
                                "code": "001896",
                                "sector": "火力发电",
                                "sniper_role": "明日主买对象",
                            },
                            {
                                "name": "浙江世宝",
                                "code": "002703",
                                "sector": "汽车配件",
                                "sniper_role": "明日补位对象",
                            },
                        ]
                    },
                    "position_decision": {
                        "signal_grade": "50",
                        "target_position_pct": 50,
                    },
                },
                final_gate={"can_new_entry": False, "should_reduce": True},
                position_level="0%不参与",
            )
        )

        self.assertIn("| 只看唯一对象 | 600360 华微电子（半导体） | 09:50-10:10 |", rendered)
        self.assertIn("| 暂无 | - | - | - | - | - | - | - |", rendered)
        self.assertNotIn("001896 豫能控股", rendered)
        self.assertNotIn("002703 浙江世宝", rendered)

    def test_candidate_section_uses_structured_snapshot_summary_and_hides_full_candidate_table(self):
        rendered = "\n".join(
            render_front_page_v2(
                [
                    "| 股票 | 代码 | 所属方向 | 标志性大阳线 | 近5日状态 | 承接 | 资金痕迹 | 明日资格 |",
                    "|------|------|----------|--------------|-----------|------|----------|----------|",
                    "| 富瀚微 | 300613 | 半导体 | 放量涨停 | 未完全爆发 | 明日验证承接 | 主线资金主动进攻 | 观察，等10点确认 |",
                ],
                target_date="2026-04-24",
                market_research_snapshot={
                    "mainline_turnover_summary": {"current_mainline": "半导体"},
                    "candidate_snapshot": {
                        "front_page": {
                            "unique_object": "暂无",
                            "backup_text": "富瀚微(300613)；华特气体(688268)",
                            "no_buy_reason": "60分钟确认未完成",
                            "trigger_condition": "10点确认；主线承接",
                            "failure_condition": "主线回落；跌破关键位",
                            "backup_watch": [
                                {
                                    "label": "富瀚微(300613)",
                                    "sector": "半导体",
                                    "role": "主线备选",
                                    "trigger_condition": "10点确认承接",
                                    "failure_condition": "跌破关键位",
                                }
                            ],
                        }
                    },
                },
            )
        )

        stock_section = rendered[rendered.index("## 五、个股解读") : rendered.index("## 六、明日执行计划")]
        self.assertIn("### 1. 个股裁决", stock_section)
        self.assertIn("| 备用观察 | 富瀚微(300613)；华特气体(688268) |", stock_section)
        self.assertIn("| 今日不买原因 | 09:50-10:10窗口未完成 |", stock_section)
        self.assertIn("| 明日触发 | 09:50-10:10窗口；主线承接 |", stock_section)
        self.assertIn("| 明日失效 | 主线回落；跌破关键位 |", stock_section)
        self.assertIn("### 2. 明日候选观察", stock_section)
        self.assertIn("| 角色 | 标的 | 速度档 | 买点线 | 卖点线 | 承接修复条件 | 观察复核 | 观察窗 |", stock_section)
        self.assertIn("### 3. 备用观察", stock_section)
        self.assertIn("| 富瀚微(300613) | 半导体 | 主线备选 | 09:50-10:10窗口 | 跌破关键位 |", stock_section)
        self.assertNotIn("| 股票 | 代码 | 所属方向 | 标志性大阳线 | 近5日状态 | 承接 | 资金痕迹 | 明日资格 |", stock_section)

    def test_front_page_renders_reasoning_decision_without_chain_of_thought(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-04-24",
                market_research_snapshot={
                    "candidate_pool": [
                        {
                            "code": "300613",
                            "name": "富瀚微",
                            "sector": "半导体",
                            "direction": "AI端侧芯片",
                        }
                    ],
                    "mainline_turnover_summary": {"current_mainline": "半导体"},
                    "reasoning_decision": {
                        "action": "observe",
                        "mainline_state": "strengthening",
                        "reasoning_effort": "xhigh",
                        "unique_target": None,
                        "conclusion": "主线仍需确认，明天只观察承接。",
                        "evidence": [{"field": "mainline_snapshot.current_mainline", "summary": "主线为半导体"}],
                        "trigger_conditions": ["10点后主线继续放量", "候选股完成60分钟确认"],
                        "failure_conditions": ["主线回落", "候选股承接失败"],
                        "excluded_candidates": [{"id": "300613", "name": "富瀚微", "reason": "60分钟确认未完成"}],
                        "confidence": "medium",
                    },
                },
            )
        )

        self.assertIn("### 0. 推理裁决", rendered)
        self.assertNotIn("| 裁决 | observe |", rendered)
        self.assertNotIn("| 主线状态 | strengthening |", rendered)
        self.assertIn("| 结论 | 主线仍需确认，明天只观察承接。 |", rendered)
        self.assertIn("| 关键证据 | 主线为半导体 |", rendered)
        self.assertIn("| 触发条件 | 09:50-10:10主线继续放量；候选股09:50-10:10窗口满足条件 |", rendered)
        self.assertIn("| 失败条件 | 主线回落；候选股承接失败 |", rendered)
        self.assertIn("| 排除对象 | 富瀚微(300613)：09:50-10:10窗口未完成 |", rendered)
        self.assertIn("| 推理深度 | xhigh |", rendered)
        self.assertNotIn("| 置信度 | medium |", rendered)
        self.assertNotIn("chain-of-thought", rendered)
        self.assertNotIn("思维链", rendered)
        self.assertNotIn("60分钟确认", rendered)

    def test_reasoning_decision_surface_sanitizes_forbidden_markers_and_table_breaks(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-04-24",
                market_research_snapshot={
                    "mainline_turnover_summary": {"current_mainline": "半导体"},
                    "reasoning_decision": {
                        "action": "observe",
                        "mainline_state": "unclear",
                        "reasoning_effort": "xhigh",
                        "unique_target": None,
                        "conclusion": "思维链：先想A\n再想B | 这段不该破表",
                        "evidence": [{"field": "x", "summary": "chain-of-thought: hidden | draft"}],
                        "trigger_conditions": ["10点确认\n不要换行", "候选|确认"],
                        "failure_conditions": ["主线回落 | 失败"],
                        "excluded_candidates": [{"id": "300613", "name": "富瀚微", "reason": "思维链 泄漏 | 原因"}],
                        "confidence": "medium|bad",
                    },
                },
            )
        )

        self.assertIn("### 0. 推理裁决", rendered)
        self.assertNotIn("思维链", rendered)
        self.assertNotIn("chain-of-thought", rendered)
        reasoning_section = rendered[rendered.index("### 0. 推理裁决") : rendered.index("| 明日观察动作 |")]
        for line in reasoning_section.splitlines():
            if line.startswith("|") and not line.startswith("|------"):
                self.assertEqual(line.count("|"), 3, line)

    def test_reasoning_decision_unique_target_drives_unique_action_when_snapshot_target_is_missing(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-04-24",
                market_research_snapshot={
                    "candidate_pool": [
                        {
                            "code": "300613",
                            "name": "富瀚微",
                            "sector": "半导体",
                            "direction": "AI端侧芯片",
                        }
                    ],
                    "mainline_turnover_summary": {"current_mainline": "半导体"},
                    "reasoning_decision": {
                        "action": "conditional_entry",
                        "mainline_state": "strengthening",
                        "reasoning_effort": "xhigh",
                        "unique_target": "300613",
                        "conclusion": "只看富瀚微，满足确认才按50%条件执行。",
                        "handoff_buying_evidence": "clear",
                        "evidence": [{"field": "mainline_snapshot.current_mainline", "summary": "主线为半导体"}],
                        "trigger_conditions": ["10点后主线继续放量", "富瀚微完成60分钟确认"],
                        "failure_conditions": ["主线回落"],
                        "excluded_candidates": [],
                        "confidence": "medium",
                    },
                },
            )
        )

        expected_label = "300613 富瀚微（半导体、AI端侧芯片）"
        self.assertIn(f"| 只看唯一对象 | {expected_label} | 09:50-10:10 | 主线确认 / 承接 / 09:50-10:10窗口 | 不满足回到0%不参与 |", rendered)
        self.assertIn(
            f"| 50%条件执行，只做合格对象 | 不确定时不值得主动参与 | 半导体 | 半导体 | 先看市场基底 | {expected_label} | 50%条件执行 |",
            rendered,
        )
        self.assertIn("| 50%条件执行 |", rendered)
        self.assertIn("50%：只做合格对象", rendered)

    def test_unique_target_label_keeps_markdown_tables_stable_when_direction_has_table_chars(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-04-24",
                market_research_snapshot={
                    "candidate_pool": [
                        {
                            "code": "300613",
                            "name": "富瀚微",
                            "sector": "半导体",
                            "direction": "AI|端侧\n芯片",
                        }
                    ],
                    "mainline_turnover_summary": {"current_mainline": "半导体"},
                    "reasoning_decision": {
                        "action": "conditional_entry",
                        "mainline_state": "strengthening",
                        "reasoning_effort": "xhigh",
                        "unique_target": "300613",
                        "conclusion": "只看富瀚微。",
                        "handoff_buying_evidence": "clear",
                        "evidence": [],
                        "trigger_conditions": ["10点确认"],
                        "failure_conditions": ["主线回落"],
                        "excluded_candidates": [],
                        "confidence": "medium",
                    },
                },
            )
        )

        expected_label = "300613 富瀚微（半导体、AI｜端侧 芯片）"
        self.assertIn(f"| 只看唯一对象 | {expected_label} | 09:50-10:10 | 主线确认 / 承接 / 09:50-10:10窗口 | 不满足回到0%不参与 |", rendered)
        for line in rendered.splitlines():
            if line.startswith("| 只看唯一对象 |") or line.startswith("| 50%条件执行"):
                self.assertNotIn("AI|端侧", line)

    def test_reasoning_conditional_entry_without_clear_handoff_stays_zero_state(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-04-24",
                market_research_snapshot={
                    "candidate_pool": [{"code": "300613", "name": "富瀚微", "sector": "半导体"}],
                    "mainline_turnover_summary": {"current_mainline": "半导体"},
                    "reasoning_decision": {
                        "action": "conditional_entry",
                        "mainline_state": "strengthening",
                        "reasoning_effort": "xhigh",
                        "unique_target": "300613",
                        "conclusion": "证据不足，只能观察。",
                        "handoff_buying_evidence": "insufficient",
                        "evidence": [{"field": "mainline_snapshot.current_mainline", "summary": "主线为半导体"}],
                        "trigger_conditions": ["10点确认"],
                        "failure_conditions": ["主线回落"],
                        "excluded_candidates": [],
                        "confidence": "medium",
                    },
                },
            )
        )

        self.assertIn("| 只看观察对象 | 暂无 | 09:50-10:10 | 主线确认 + 承接 + 09:50-10:10窗口未同时满足 | 不满足回到0% |", rendered)
        self.assertIn("| 0%不参与 | 不确定时不值得主动参与 | 半导体 | 半导体 | 先看市场基底 | 暂无 | 0%不参与 |", rendered)
        self.assertNotIn(_m("50%执行", "30%"), rendered)

    def test_conditional_defense_without_unique_target_renders_zero_state(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-04-24",
                market_research_snapshot={
                    "mainline_turnover_summary": {"current_mainline": "半导体"},
                    "state_machine": {"leading_line": "半导体"},
                    "candidate_snapshot": {
                        "front_page": {
                            "unique_object": "暂无",
                            "backup_text": "富瀚微(300613)",
                            "no_buy_reason": "等待10点确认",
                            "trigger_condition": "10点确认；主线承接",
                            "failure_condition": "主线回落",
                        }
                    },
                },
                final_gate={
                    "can_new_entry": False,
                    "allow_attack_50_ready": True,
                    "should_reduce": False,
                    "final_action": "观察，只看主线核心；09:50-10:10完成10点确认后才评估是否50%条件执行，否则不参与",
                },
                position_level="0%不参与",
            )
        )

        self.assertIn("| 0%不参与 |", rendered)
        self.assertIn("| 09:50-10:10 | 观察市场底色、主线承接、观察对象强弱 | 无 | 窗口内处理弱仓/错仓 | 条件未同时满足继续0% |", rendered)
        self.assertIn("| 14:30-14:55 | 只判断是否量化电风扇行情 | 无 | 非电风扇不新增参与 | 例外，不是常规 |", rendered)
        self.assertNotIn("10:00左右买", rendered)
        self.assertNotIn("新仓止损", rendered)
        self.assertNotIn("尾盘开新仓", rendered)
        self.assertNotIn(_m("3", "0%", "条件", "试错"), rendered)
        self.assertNotIn("50%执行", rendered)
        self.assertNotIn("| 空仓 / 短线确认 |", rendered)

    def test_reasoning_decision_unique_target_only_drives_action_for_conditional_entry(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-04-24",
                market_research_snapshot={
                    "candidate_pool": [{"code": "300613", "name": "富瀚微", "sector": "半导体"}],
                    "mainline_turnover_summary": {"current_mainline": "半导体"},
                    "reasoning_decision": {
                        "action": "observe",
                        "mainline_state": "strengthening",
                        "reasoning_effort": "xhigh",
                        "unique_target": "300613",
                        "conclusion": "只观察，不给执行目标。",
                        "evidence": [],
                        "trigger_conditions": ["10点确认"],
                        "failure_conditions": ["主线回落"],
                        "excluded_candidates": [],
                        "confidence": "medium",
                    },
                },
            )
        )

        self.assertIn("### 1. 个股裁决", rendered)
        self.assertIn("| 只看观察对象 | 暂无 | 09:50-10:10 | 主线确认 + 承接 + 09:50-10:10窗口未同时满足 | 不满足回到0% |", rendered)
        self.assertIn("| 0%不参与 | 不确定时不值得主动参与 | 半导体 | 半导体 | 先看市场基底 | 暂无 | 0%不参与 |", rendered)

    def test_non_actionable_reasoning_decision_blocks_snapshot_unique_target(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-04-24",
                market_research_snapshot={
                    "candidate_pool": [{"code": "300613", "name": "富瀚微", "sector": "半导体"}],
                    "unique_action_target": {
                        "name": "富瀚微",
                        "code": "300613",
                        "condition": "主线确认 + 承接 + 60分钟确认",
                    },
                    "mainline_turnover_summary": {"current_mainline": "半导体"},
                    "reasoning_decision": {
                        "action": "observe",
                        "mainline_state": "strengthening",
                        "reasoning_effort": "xhigh",
                        "unique_target": "300613",
                        "conclusion": "只观察，不给执行目标。",
                        "evidence": [],
                        "trigger_conditions": ["10点确认"],
                        "failure_conditions": ["主线回落"],
                        "excluded_candidates": [],
                        "confidence": "medium",
                    },
                },
            )
        )

        self.assertIn("### 1. 个股裁决", rendered)
        self.assertNotIn("### 1. 主线内可执行候选", rendered)
        self.assertIn("| 只看观察对象 | 暂无 | 09:50-10:10 | 主线确认 + 承接 + 09:50-10:10窗口未同时满足 | 不满足回到0% |", rendered)
        self.assertIn("| 0%不参与 | 不确定时不值得主动参与 | 半导体 | 半导体 | 先看市场基底 | 暂无 | 0%不参与 |", rendered)

    def test_empty_or_malformed_reasoning_decision_blocks_snapshot_unique_target(self):
        for reasoning_decision in ({}, "invalid"):
            with self.subTest(reasoning_decision=reasoning_decision):
                rendered = "\n".join(
                    render_front_page_v2(
                        [],
                        target_date="2026-04-24",
                        market_research_snapshot={
                            "candidate_pool": [{"code": "300613", "name": "富瀚微", "sector": "半导体"}],
                            "unique_action_target": {
                                "name": "富瀚微",
                                "code": "300613",
                                "condition": "主线确认 + 承接 + 60分钟确认",
                            },
                            "mainline_turnover_summary": {"current_mainline": "半导体"},
                            "reasoning_decision": reasoning_decision,
                        },
                    )
                )

                self.assertIn("### 1. 个股裁决", rendered)
                self.assertNotIn("### 1. 主线内可执行候选", rendered)
                self.assertIn("| 只看观察对象 | 暂无 | 09:50-10:10 | 主线确认 + 承接 + 09:50-10:10窗口未同时满足 | 不满足回到0% |", rendered)
                self.assertIn("| 0%不参与 | 不确定时不值得主动参与 | 半导体 | 半导体 | 先看市场基底 | 暂无 | 0%不参与 |", rendered)

    def test_turnover_share_lines_derives_share_change_from_structured_same_mainline_history(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-04-24",
                market_research_snapshot={
                    "current_sector_turnover_snapshot": {
                        "date": "2026-04-24",
                        "sector_name": "半导体",
                        "turnover_share_pct": 18.1,
                    },
                    "recent_sector_turnover_history": [
                        {"date": "2026-04-23", "sector_name": "半导体", "turnover_share_pct": 15.8},
                    ],
                    "mainline_turnover_summary": {
                        "current_mainline": "半导体",
                        "turnover_share_trend_rows": [
                            {
                                "date": "2026-04-24",
                                "cycle_mainline": "半导体",
                                "daily_attack_line": "半导体",
                                "mainline_turnover": "2180.00亿",
                                "market_turnover": "12834.00亿",
                                "share": "18.1%",
                                "share_change": "待累计",
                                "interpretation": "主线占比继续抬升",
                            }
                        ],
                    },
                },
            )
        )

        self.assertIn(
            "| 2026-04-24 | "
            '<span class="cycle-sector-label" style="color:#2F7FB8;border-color:#2F7FB8">[半导体]</span> | '
            "2180.00亿 | 12834.00亿 | 18.1% | +2.3pct | 大周期延续 | 主线占比继续抬升 |",
            rendered,
        )

    def test_turnover_share_lines_does_not_compare_against_previous_day_when_mainline_switches(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-04-24",
                market_research_snapshot={
                    "current_sector_turnover_snapshot": {
                        "date": "2026-04-24",
                        "sector_name": "半导体",
                        "turnover_share_pct": 18.1,
                    },
                    "recent_sector_turnover_history": [
                        {"date": "2026-04-23", "sector_name": "电力", "turnover_share_pct": 15.8},
                    ],
                    "mainline_turnover_summary": {
                        "current_mainline": "半导体",
                        "turnover_share_trend_rows": [
                            {
                                "date": "2026-04-24",
                                "cycle_mainline": "半导体",
                                "daily_attack_line": "半导体",
                                "mainline_turnover": "2180.00亿",
                                "market_turnover": "12834.00亿",
                                "share": "18.1%",
                                "share_change": "+2.3pct",
                                "interpretation": "新主线刚切换，先累计半导体自身占比",
                            }
                        ],
                    },
                },
            )
        )

        self.assertRegex(
            rendered,
            r"\| 2026-04-24 \| "
            + _cycle_sector_label_pattern("半导体")
            + r" \| 2180\.00亿 \| 12834\.00亿 \| 18\.1% \| 待累计 \| 大周期延续 \| 新主线刚切换，先累计半导体自身占比 \|",
        )
        self.assertNotRegex(
            rendered,
            r"\| 2026-04-24 \| "
            + _cycle_sector_label_pattern("半导体")
            + r" \| 2180\.00亿 \| 12834\.00亿 \| 18\.1% \| \+2\.3pct \|",
        )

    def test_turnover_share_lines_split_hot_sector_watch_by_sector(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-29",
                market_research_snapshot={
                    "mainline_turnover_summary": {
                        "hot_sector_turnover_watch_summary": "近期热点板块成交额连续跟踪：变化只按同一板块自身历史计算。",
                        "hot_sector_turnover_watch_rows": [
                            {
                                "date": "2026-05-28",
                                "sector_name": "光通信/CPO",
                                "sector_turnover": "8841.18亿",
                                "market_turnover": "29873.26亿",
                                "share": "29.6%",
                                "share_change": "待累计",
                                "sample_status": "待累计",
                                "interpretation": "光通信/CPO只记录本板块当日点位",
                            },
                            {
                                "date": "2026-05-29",
                                "sector_name": "通信设备",
                                "sector_turnover": "3062.15亿",
                                "market_turnover": "33408.58亿",
                                "share": "9.2%",
                                "share_change": "待累计",
                                "sample_status": "待累计",
                                "interpretation": "通信设备只记录本板块当日点位",
                            },
                            {
                                "date": "2026-05-29",
                                "sector_name": "国产芯片替代",
                                "sector_turnover": "10183.06亿",
                                "market_turnover": "33408.58亿",
                                "share": "30.5%",
                                "share_change": "+7.9pct",
                                "sample_status": "同板块连续",
                                "interpretation": "国产芯片替代同板块成交占比抬升",
                            },
                        ],
                    },
                },
            )
        )

        turnover_section = rendered[rendered.index("### 5. 主线成交额占比趋势") :]
        self.assertRegex(
            turnover_section,
            r"#### 近期热点板块成交额连续跟踪：" + _cycle_sector_label_pattern("国产芯片替代"),
        )
        self.assertRegex(
            turnover_section,
            r"#### 近期热点板块成交额连续跟踪：" + _cycle_sector_label_pattern("通信设备"),
        )
        self.assertRegex(
            turnover_section,
            r"#### 近期热点板块成交额连续跟踪：" + _cycle_sector_label_pattern("光通信/CPO"),
        )
        self.assertIn("| 日期 | 板块成交额 | 两市成交额 | 占比 | 同板块变化 | 样本状态 | 解读 |", turnover_section)
        self.assertIn("| 2026-05-29 | 3062.15亿 | 33408.58亿 | 9.2% | 待累计 | 待累计 | 通信设备只记录本板块当日点位 |", turnover_section)
        self.assertNotIn("| 日期 | 板块 | 板块成交额 | 两市成交额 | 占比 | 同板块变化 | 样本状态 | 解读 |", turnover_section)

    def test_turnover_share_lines_preserve_trend_table_labels_when_current_attack_unconfirmed(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-21",
                market_research_snapshot={
                    "mainline_turnover_summary": {
                        "current_mainline": "混沌轮动",
                        "mainline_attack_evidence_summary": {
                            "attack_state": "chaotic_rotation",
                            "primary_line": "",
                            "confirmation_evidence": "多线分散，主攻线尚未胜出",
                        },
                        "turnover_share_trend_rows": [
                            {
                                "date": "2026-05-19",
                                "cycle_mainline": "电力",
                                "daily_attack_line": "电力",
                                "mainline_turnover": "665.00亿",
                                "market_turnover": "29089.77亿",
                                "share": "2.3%",
                                "share_change": "+0.6pct",
                                "interpretation": "电力支线轮动，先看回流强度",
                            },
                            {
                                "date": "2026-05-20",
                                "cycle_mainline": "半导体",
                                "daily_attack_line": "半导体",
                                "mainline_turnover": "4050.00亿",
                                "market_turnover": "29764.59亿",
                                "share": "13.6%",
                                "share_change": "+1.5pct",
                                "interpretation": "半导体支线轮动，成交额占比明显抬升",
                            },
                        ],
                    },
                },
            )
        )

        turnover_section = rendered[rendered.index("### 5. 主线成交额占比趋势") :]
        self.assertIn(
            "| 2026-05-19 | "
            '<span class="cycle-sector-label" style="color:#DD4C4F;border-color:#DD4C4F">[电力]</span> | '
            "665.00亿 | 29089.77亿 | 2.3% | +0.6pct | 大周期延续 | 电力支线轮动，先看回流强度 |",
            turnover_section,
        )
        self.assertIn(
            "| 2026-05-20 | "
            '<span class="cycle-sector-label" style="color:#2F7FB8;border-color:#2F7FB8">[半导体]</span> | '
            "4050.00亿 | 29764.59亿 | 13.6% | +1.5pct | 大周期延续 | 半导体支线轮动，成交额占比明显抬升 |",
            turnover_section,
        )
        self.assertNotIn("| 2026-05-20 | 暂无确认主线 | 暂无确认主攻线 | 4050.00亿", turnover_section)

    def test_front_page_replaces_double_mainline_with_capacity_regime_table(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-05-14",
                market_research_snapshot={
                    "mainline_turnover_summary": {
                        "current_mainline": "半导体",
                        "mainline_capacity_regime_summary": {
                            "mainline_capacity": "双线孕育",
                            "mainline_regime": "混沌接力",
                            "primary_line": "半导体",
                            "other_lines": "电力 / 化学制品",
                            "confirmation_evidence": "半导体高标和涨停更集中，成交占比靠前",
                            "sector_relationship_state": "半导体尝试替代，电力退成背景线待确认",
                            "mainline_process": "半导体启动，电力背景线",
                            "tomorrow_action": "先看资金是否继续选择半导体；背景线只观察回流",
                        },
                        "mainline_attack_evidence_summary": {
                            "attack_state": "confirmed_attack",
                            "primary_line": "半导体",
                            "candidate_lines": ["电力"],
                            "confirmation_evidence": "半导体资金净流入靠前，涨停和高标更集中，成交占比扩张",
                            "sector_evidence_rows": [
                                {
                                    "sector_name": "半导体",
                                    "net_inflow_rank": 1,
                                    "net_inflow_amount": 45.0,
                                    "limit_up_count": 5,
                                    "high_anchor_height": 4,
                                    "turnover_share_change": 1.6,
                                },
                                {
                                    "sector_name": "电力",
                                    "net_inflow_rank": 2,
                                    "net_inflow_amount": 8.0,
                                    "limit_up_count": 1,
                                    "high_anchor_height": 1,
                                    "turnover_share_change": -0.5,
                                },
                            ],
                        },
                    },
                    "unique_action_target": {
                        "name": "中船特气",
                        "code": "688146",
                        "condition": "主线确认 + 承接 + 60分钟确认",
                    },
                },
            )
        )

        self.assertIn("### 4. 主线容量与格局判断", rendered)
        self.assertIn("| 主线容量 | 主线格局 | 主攻线 | 竞争线/背景线 | 主线确认依据 | 板块关系状态 | 主线进程 | 明日动作 |", rendered)
        self.assertIn("| 双线孕育 | 混沌接力 | 半导体 | 电力 / 化学制品 | 半导体高标和涨停更集中，成交占比靠前 | 半导体尝试替代，电力退成背景线待确认 | 半导体启动，电力背景线 | 先看资金是否继续选择半导体；背景线只观察回流 |", rendered)
        self.assertIn("#### 主线攻击证据", rendered)
        self.assertIn("| 板块 | 攻击状态 | 净流入排名 | 净流入 | 涨停数 | 高标高度 | 成交占比变化 | 结论 |", rendered)
        self.assertIn("| 半导体 | 确认主攻线 | 第1 | +45.00亿 | 5 | 4 | +1.6pct | 半导体资金净流入靠前，涨停和高标更集中，成交占比扩张 |", rendered)
        self.assertIn("| 电力 | 候选线 | 第2 | +8.00亿 | 1 | 1 | -0.5pct | 电力仍是候选线，证据不足以确认主攻线 |", rendered)
        self.assertNotIn("### 4. 双层主线结论", rendered)
        self.assertNotIn("| 周期主线 | 当天主攻线 | 两者关系 | 明日动作 |", rendered)

    def test_market_fit_embeds_in_existing_sections_without_standalone_modules(self):
        rendered = "\n".join(
            render_front_page_v2(
                [
                    "## 二、市场基底",
                    "### 1. 指数与市场底色",
                    "| 指标 | 数值 | 涨跌幅 | 解读 |",
                    "| 上证指数 | 4079.90 | -0.33% | 震荡修复 |",
                    "| 中证500 | 5830.25 | +0.82% | 中盘修复 |",
                    "### 2. 市场状态结论",
                    "| 项目 | 结论 | 依据 |",
                    "|------|------|------|",
                    "| 市场状态 | 收缩防守 | 指数弱、跌多涨少 |",
                    "## 三、周期与主线",
                    "**主线内可执行候选**:",
                    "| 股票 | 代码 | 所属方向 | 标志性大阳线 | 近5日状态 | 承接 | 资金痕迹 | 明日资格 |",
                    "|------|------|----------|--------------|-----------|------|----------|----------|",
                    "| 富瀚微 | 300613 | 半导体 | 放量涨停 | 未完全爆发 | 明日验证承接 | 主线资金主动进攻 | 观察，等10点确认 |",
                    "| 华特气体 | 688268 | 电子化学 | 放量大阳线 | 未完全爆发 | 明日验证承接 | 链内跟随 | 观察 |",
                    "| 股票 | 代码 | 所属方向 | 观察意义 | 明日原则 |",
                    "| 恩捷股份 | 002812 | 电池 | 轮动试探 | 只看强弱，不给买入指令 |",
                ],
                target_date="2026-04-24",
                market_research_snapshot={
                    "market_fit_calibration": {
                        "fit_label": "主线有效，池子偏窄",
                        "evidence_text": "强势样本3只，主线命中2只，观察池命中0只",
                        "cycle_note": "强势样本集中半导体，主线成交额占比抬升时优先看承接",
                        "action_text": "只扩主线内强票池",
                    },
                    "cycle_interpretation_rows": [
                        {
                            "cycle_label": "当前周期",
                            "date_range": "04-21 ~ 04-24",
                            "trading_days": "4日",
                            "mainline": "半导体",
                            "market_state": "修复接力",
                            "interpretation": "半导体接替电力，等待承接确认",
                        }
                    ],
                    "mainline_turnover_summary": {
                        "turnover_share_trend_summary": "近25个交易日主线成交额占比趋势：当前10.0%，区间10.0%-17.5%，主线成交占比回落，先看重新聚焦能否持续。",
                        "double_mainline_summary": {
                            "cycle_mainline": "半导体",
                            "daily_attack_line": "半导体",
                            "relationship": "周期主线与当天主攻线一致",
                            "tomorrow_action": "继续围绕半导体观察承接",
                        },
                        "turnover_share_trend_rows": [
                            {
                                "date": "2026-04-23",
                                "cycle_mainline": "电力",
                                "daily_attack_line": "电力",
                                "mainline_turnover": "2100亿",
                                "market_turnover": "12000亿",
                                "share": "17.5%",
                                "share_change": "-",
                                "interpretation": "上个周期退潮",
                            },
                            {
                                "date": "2026-04-24",
                                "cycle_mainline": "半导体",
                                "daily_attack_line": "半导体",
                                "mainline_turnover": "2638.10亿",
                                "market_turnover": "26414.92亿",
                                "share": "10.0%",
                                "share_change": "抬升",
                                "interpretation": "主线成交额占比抬升，强势样本开始集中",
                            },
                        ],
                    },
                    "unique_action_target": {
                        "name": "富瀚微",
                        "code": "300613",
                        "condition": "主线确认 + 承接 + 60分钟确认",
                    },
                },
                final_gate={"can_new_entry": False, "allow_attack_50_ready": True, "final_action": "观察，等10点确认"},
                position_level="轻仓",
            )
        )

        self.assertIn("| 中证500 | 5830.25 | +0.82% | 中盘修复 |", rendered)
        self.assertIn("| 市场贴合度 | 主线有效，池子偏窄 | 强势样本3只，主线命中2只，观察池命中0只 |", rendered)
        market_base = rendered[rendered.index("### 2. 市场状态结论") : rendered.index("## 三、周期与主线")]
        self.assertLess(market_base.index("| 项目 | 结论 | 依据 |"), market_base.index("| 市场贴合度 |"))
        self.assertNotIn("### 2. 市场状态结论\n| 市场贴合度 |", market_base)
        self.assertIn("强势样本集中半导体", rendered)
        self.assertIn("| 日期 | 小周期方向 | 主线成交额 | 两市成交额 | 占比 | 占比变化 | 切换判断 | 解读 |", rendered)
        turnover_section = rendered[rendered.index("### 5. 主线成交额占比趋势") :]
        self.assertIn("> 近25个交易日主线成交额占比趋势：当前10.0%，区间10.0%-17.5%，主线成交占比回落，先看重新聚焦能否持续。", turnover_section)
        self.assertLess(turnover_section.index("2026-04-24"), turnover_section.index("2026-04-23"))
        front_stock_section = rendered[rendered.index("## 五、个股解读") : rendered.index("## 六、明日执行计划")]
        self.assertNotIn("| 股票 | 代码 | 所属方向 | 标志性大阳线 | 近5日状态 | 承接 | 资金痕迹 | 明日资格 |", front_stock_section)
        self.assertIn("| 唯一对象 | 300613 富瀚微 |", front_stock_section)
        self.assertIn("| 明日唯一动作 | 标的 | 参与窗 | 条件 | 不满足怎么办 |", rendered)
        self.assertIn("| 只看唯一对象 | 300613 富瀚微 | 09:50-10:10 | 主线确认 + 承接 + 09:50-10:10窗口 | 不满足回到0%不参与 |", rendered)
        for forbidden in (
            "## 市场贴合度校准",
            "## 大阳线与承接",
            "## 主力画图",
            _m("执行", "权"),
            _m("闸", "门"),
            _m("门", "控"),
            _m("开", "闸"),
            _m("放", "行"),
        ):
            self.assertNotIn(forbidden, rendered)

    def test_front_page_renders_market_structure_before_cycle_section(self):
        rendered = "\n".join(
            render_front_page_v2(
                [
                    "## 二、市场基底",
                    "### 1. 指数与市场底色",
                    "| 指标 | 数值 | 涨跌幅 | 解读 |",
                    "| 创业板指 | 3914.88 | +1.20% | 强势上涨 |",
                    "### 2. 市场状态结论",
                    "| 项目 | 结论 | 依据 |",
                    "|------|------|------|",
                    "| 市场情绪总状态 | 局部强 | 指数强但涨跌家数偏弱 |",
                ],
                target_date="2026-05-27",
                market_research_snapshot={
                    "market_structure_judgement": {
                        "index_profit_relation": "指数强但真实赚钱效应弱，指数不能代表多数股票体感",
                        "turnover_distribution": "成交额高位但结构集中，不能按普涨支撑处理",
                        "rotation_nature": "消费、白酒更像对立反弹，尚未证明主线切换",
                        "old_mainline_fatigue": "科技仍活跃但短线疲态上升，只保留核心观察",
                        "tomorrow_rhythm": "低频聚焦",
                        "candidate_policy": "只保留主线核心；题材荒时不从旧方向强行扩散候选",
                        "summary_text": "指数强但真实赚钱效应弱；成交额高位但结构集中；明日节奏：低频聚焦",
                        "action_reason_text": "低频聚焦。原因是指数强但真实赚钱效应弱，成交额高位但结构集中。",
                    },
                    "mainline_turnover_summary": {"current_mainline": "科技"},
                },
            )
        )

        self.assertIn("### 3. 市场结构判断", rendered)
        self.assertLess(rendered.index("### 3. 市场结构判断"), rendered.index("## 三、周期与主线"))
        self.assertIn("| 明日节奏 | 低频聚焦；只保留主线核心；题材荒时不从旧方向强行扩散候选 |", rendered)
        self.assertIn("| 0%不参与 | 不确定时不值得主动参与 | 科技 | 科技 | 低频聚焦 |", rendered)
        self.assertIn("低频聚焦。原因是指数强但真实赚钱效应弱，成交额高位但结构集中。", rendered)

    def test_final_target_resolution_new_entry_after_old_position_exit_keeps_target_actionable(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-06-03",
                market_research_snapshot={
                    "mainline_turnover_summary": {"current_mainline": "通信设备"},
                    "existing_position_summary": {
                        "has_position": True,
                        "summary": "华电辽能(600396)：已有仓先按MA5T处理",
                    },
                    "unique_action_target": {
                        "name": "工业富联",
                        "code": "601138",
                        "sector": "通信设备",
                        "participation_window": "09:50-10:10",
                        "condition": "板块锚承接继续",
                        "fallback_state": "不满足回到0%",
                    },
                    "position_decision": {"signal_grade": "50", "target_position_pct": 50},
                    "final_target_resolution": {
                        "new_entry_target": {
                            "name": "工业富联",
                            "code": "601138",
                            "sector": "通信设备",
                            "participation_window": "09:50-10:10",
                            "condition": "板块锚承接继续",
                            "fallback_state": "不满足回到0%",
                        },
                        "existing_position_target": {
                            "name": "华电辽能",
                            "code": "600396",
                            "sector": "电力",
                            "role": "旧仓处理",
                        },
                        "display_target": {
                            "name": "工业富联",
                            "code": "601138",
                            "sector": "通信设备",
                        },
                        "capital_priority_decision": {
                            "capital_priority": "new_entry_after_old_exit",
                            "reason": "先处理旧仓腾出资金，工业富联具备执行条件",
                        },
                    },
                },
                final_gate={"can_new_entry": True},
            )
        )

        account_section = rendered[rendered.index("## 明日账户建议") : rendered.index("## 一、交易纪律")]
        stock_section = rendered[rendered.index("## 五、个股解读") : rendered.index("## 六、明日执行计划")]
        execution_section = rendered[rendered.index("## 六、明日执行计划") : rendered.index("## 七、最终结论")]
        final_section = rendered[rendered.index("## 七、最终结论") :]

        self.assertIn("| 明日动作 | 先处理旧仓，买工业富联(601138) |", account_section)
        self.assertIn("| 旧仓处理 | 华电辽能(600396)：已有仓先按MA5T处理 |", account_section)
        self.assertIn("| 明日执行目标 | 工业富联(601138)：固定交易窗口条件 |", account_section)
        self.assertIn("| 新开仓上限 | 资金释放后1 |", account_section)
        self.assertIn("| 明日仓位 | 50%条件执行 |", stock_section)
        self.assertIn("| 执行目标 | 601138 工业富联（通信设备） |", stock_section)
        self.assertIn("| 只看唯一对象 | 601138 工业富联（通信设备） | 09:50-10:10 | 板块锚承接继续 | 不满足回到0%不参与 |", execution_section)
        self.assertIn("| 50%条件执行，只做合格对象 |", final_section)
        self.assertIn("601138 工业富联（通信设备）", final_section)
        self.assertNotIn("观察" + "锚：601138 工业富联", final_section)

    def test_old_position_exit_keeps_unbuyable_core_proxy_as_action_target(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-06-03",
                market_research_snapshot={
                    "account_profile": {
                        "capital_text": "约1w账户",
                        "cash_available": 9800,
                    },
                    "mainline_turnover_summary": {"current_mainline": "通信设备"},
                    "existing_position_summary": {
                        "has_position": True,
                        "summary": "华电辽能(600396)：已有仓先按MA5T处理",
                    },
                    "selected_position_candidate": {
                        "name": "中际旭创",
                        "code": "300308",
                        "sector": "通信设备",
                        "identity": "市场核心",
                        "one_lot_amount": 16800,
                    },
                    "position_decision": {"signal_grade": "50", "target_position_pct": 50},
                    "final_target_resolution": {
                        "new_entry_target": {
                            "name": "中际旭创",
                            "code": "300308",
                            "sector": "通信设备",
                            "identity": "市场核心",
                            "one_lot_amount": 16800,
                        },
                        "existing_position_target": {
                            "name": "华电辽能",
                            "code": "600396",
                            "sector": "电力",
                            "role": "旧仓处理",
                        },
                        "watch_target": {
                            "name": "中际旭创",
                            "code": "300308",
                            "sector": "通信设备",
                            "identity": "市场核心",
                            "one_lot_amount": 16800,
                        },
                        "tradable_proxy_target": {
                            "name": "通信ETF",
                            "code": "515880",
                            "sector": "通信设备",
                            "proxy_effect_type": "行业板块效应",
                            "condition": "通信设备承接继续",
                            "participation_window": "09:50-10:10",
                            "fallback_state": "不满足回到0%",
                            "target_position_pct": 50,
                        },
                        "display_target": {
                            "name": "通信ETF",
                            "code": "515880",
                            "sector": "通信设备",
                            "proxy_effect_type": "行业板块效应",
                            "condition": "通信设备承接继续",
                            "participation_window": "09:50-10:10",
                            "fallback_state": "不满足回到0%",
                            "target_position_pct": 50,
                        },
                        "capital_priority_decision": {
                            "capital_priority": "new_entry_after_old_exit",
                            "reason": "先处理旧仓，目标标的中际旭创(300308)，小资金账户可用通信ETF(515880)替代",
                        },
                    },
                },
                final_gate={"can_new_entry": True},
            )
        )

        account_section = rendered[rendered.index("## 明日账户建议") : rendered.index("## 一、交易纪律")]
        stock_section = rendered[rendered.index("## 五、个股解读") : rendered.index("## 六、明日执行计划")]
        execution_section = rendered[rendered.index("## 六、明日执行计划") : rendered.index("## 七、最终结论")]
        final_section = rendered[rendered.index("## 七、最终结论") :]

        self.assertIn("| 明日仓位 | 50%条件执行 |", account_section)
        self.assertIn("| 明日动作 | 先处理旧仓，买通信ETF(515880) |", account_section)
        self.assertIn("| 旧仓处理 | 华电辽能(600396)：已有仓先按MA5T处理 |", account_section)
        self.assertIn("| 明日执行目标 | 通信ETF(515880)：行业板块效应替代表达 |", account_section)
        self.assertIn("| 执行目标 | 515880 通信ETF（通信设备） |", stock_section)
        self.assertIn("| 只看唯一对象 | 515880 通信ETF（通信设备） | 09:50-10:10 | 通信设备承接继续 | 不满足回到0%不参与 |", execution_section)
        self.assertIn("| 50%条件执行，只做合格对象 |", final_section)
        self.assertIn("515880 通信ETF（通信设备）", final_section)
        self.assertNotIn("当前账户买不了一手，只保留观察", account_section)

    def test_final_target_resolution_old_position_priority_turns_new_entry_into_watch_anchor(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-06-03",
                market_research_snapshot={
                    "mainline_turnover_summary": {"current_mainline": "通信设备"},
                    "existing_position_summary": {
                        "has_position": True,
                        "summary": "华电辽能(600396)：已有仓先按MA5T处理",
                    },
                    "unique_action_target": {
                        "name": "工业富联",
                        "code": "601138",
                        "sector": "通信设备",
                        "participation_window": "09:50-10:10",
                    },
                    "position_decision": {"signal_grade": "50", "target_position_pct": 50},
                    "final_target_resolution": {
                        "new_entry_target": {
                            "name": "工业富联",
                            "code": "601138",
                            "sector": "通信设备",
                            "participation_window": "09:50-10:10",
                            "condition": "板块锚承接继续",
                            "fallback_state": "不满足继续观察",
                        },
                        "existing_position_target": {
                            "name": "华电辽能",
                            "code": "600396",
                            "sector": "电力",
                            "role": "旧仓处理",
                        },
                        "watch_target": {
                            "name": "工业富联",
                            "code": "601138",
                            "sector": "通信设备",
                            "participation_window": "09:50-10:10",
                            "condition": "板块锚承接继续",
                            "fallback_state": "不满足继续观察",
                        },
                        "display_target": {
                            "name": "华电辽能",
                            "code": "600396",
                            "sector": "电力",
                            "role": "旧仓处理",
                        },
                        "capital_priority_decision": {
                            "capital_priority": "old_position_t",
                            "reason": "约1w账户先处理已有仓，工业富联只保留观察" + "锚",
                        },
                    },
                },
                final_gate={"can_new_entry": True},
            )
        )

        account_section = rendered[rendered.index("## 明日账户建议") : rendered.index("## 一、交易纪律")]
        stock_section = rendered[rendered.index("## 五、个股解读") : rendered.index("## 六、明日执行计划")]
        execution_section = rendered[rendered.index("## 六、明日执行计划") : rendered.index("## 七、最终结论")]
        final_section = rendered[rendered.index("## 七、最终结论") :]

        self.assertIn("| 明日动作 | 先处理旧仓，不新增参与 |", account_section)
        self.assertIn("| 旧仓处理 | 华电辽能(600396)：已有仓先按MA5T处理 |", account_section)
        self.assertIn("| 观察对象 | 工业富联(601138)：观察对象，未出现执行资格前不新增参与 |", account_section)
        self.assertIn("| 明日仓位 | 0%新仓；旧仓处理 |", stock_section)
        self.assertIn("| 执行目标 | 无 |", stock_section)
        self.assertIn("| 不参与依据 | 已有旧仓先按持仓预案处理；不新增参与。 |", stock_section)
        self.assertIn("| 观察对象 | 601138 工业富联（通信设备） |", stock_section)
        self.assertIn("| 明日观察动作 | 标的 | 观察窗 | 条件 | 不满足怎么办 |", execution_section)
        self.assertIn("| 只看观察对象 | 601138 工业富联（通信设备） | 09:50-10:10 | 板块锚承接继续 | 不满足继续观察 |", execution_section)
        self.assertIn("观察对象：601138 工业富联（通信设备）", final_section)
        self.assertNotIn("观察" + "锚", account_section + stock_section + execution_section + final_section)
        self.assertNotIn("| 明日唯一动作 |", execution_section)
        self.assertNotIn("| 只看唯一对象 | 601138 工业富联", execution_section)

    def test_front_page_uses_sniper_derivation_packet_for_final_observation_target(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-06-04",
                market_research_snapshot={
                    "mainline_turnover_summary": {"current_mainline": "电力"},
                    "unique_action_target": {"name": "上海石化", "code": "600688", "sector": "炼化及贸"},
                    "position_decision": {"signal_grade": "0", "target_position_pct": 0},
                    "sniper_target_derivation": {
                        "schema_version": "sniper_target_derivation.v1",
                        "canonical_target": {"name": "豫能控股", "code": "001896", "sector": "电力", "role": "观察对象"},
                        "final_action": {"position_pct": 0, "action": "只观察，不新增参与"},
                        "compact_ascii": [
                            "原始候选",
                            "|",
                            "+-- 上海石化(600688): 过程候选 / 被替换",
                            "|",
                            "`-- 最终观察对象: 豫能控股(001896), 0%只观察",
                        ],
                    },
                    "final_target_resolution": {
                        "watch_target": {"name": "豫能控股", "code": "001896", "sector": "电力"},
                        "display_target": {"name": "豫能控股", "code": "001896", "sector": "电力"},
                        "capital_priority_decision": {"capital_priority": "old_position_t"},
                    },
                },
                final_gate={"can_new_entry": False},
            )
        )

        account_section = rendered[rendered.index("## 明日账户建议") : rendered.index("## 一、交易纪律")]
        stock_section = rendered[rendered.index("## 五、个股解读") : rendered.index("## 六、明日执行计划")]
        execution_section = rendered[rendered.index("## 六、明日执行计划") : rendered.index("## 七、最终结论")]

        self.assertIn("```text", rendered)
        self.assertIn("`-- 最终观察对象: 豫能控股(001896), 0%只观察", rendered)
        self.assertIn("上海石化(600688): 过程候选 / 被替换", rendered)
        self.assertIn("豫能控股(001896)", account_section)
        self.assertIn("豫能控股", stock_section)
        self.assertIn("豫能控股", execution_section)
        self.assertNotIn("| T0主对象 | 上海石化", account_section)
        self.assertNotIn("| 只看唯一对象 | 600688 上海石化", execution_section)
        self.assertNotIn("观察" + "锚", rendered)

    def test_front_page_renders_bayesian_path_after_final_summary(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-06-04",
                market_research_snapshot={
                    "mainline_turnover_summary": {"current_mainline": "电力"},
                    "position_decision": {"signal_grade": "50", "target_position_pct": 50},
                    "final_target_resolution": {
                        "display_target": {"name": "豫能控股", "code": "001896", "sector": "电力"},
                        "new_entry_target": {"name": "豫能控股", "code": "001896", "sector": "电力"},
                        "capital_priority_decision": {"capital_priority": "new_entry"},
                    },
                    "bayesian_diagnosis": {
                        "schema_version": "bayesian_diagnosis.v1",
                        "conclusion": {
                            "path_conclusion": "条件执行",
                            "execution_object": {"name": "豫能控股", "code": "001896"},
                            "position_pct": 50,
                            "action_text": "已决定50%条件执行；盘中不满足取消，回到0%不参与",
                            "final_action_alignment": "一致",
                        },
                        "path": [
                            {
                                "source_date": "2026-06-04",
                                "layer": "market",
                                "judgement": "市场未否定继续诊断",
                            }
                        ],
                        "counter_evidence": ["固定交易窗口未确认"],
                    },
                },
            )
        )

        self.assertLess(rendered.index("## 七、最终结论"), rendered.index("### 路径诊断复盘"))
        self.assertIn("| 路径结论 | 条件执行 |", rendered)
        self.assertIn("| 最终动作一致性 | 一致 |", rendered)
        self.assertIn("| 执行对象 | 豫能控股(001896) |", rendered)
        self.assertIn("#### 关键路径", rendered)
        self.assertIn("- 市场未否定继续诊断", rendered)
        self.assertIn("#### 关键反证", rendered)
        self.assertIn("- 固定交易窗口未确认", rendered)
        self.assertNotIn("diagnosis_label", rendered)
        self.assertNotIn("confidence", rendered)


if __name__ == "__main__":
    unittest.main()
