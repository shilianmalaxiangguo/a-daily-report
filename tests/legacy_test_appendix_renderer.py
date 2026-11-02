import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.appendix_renderer import _request_step_timer_alias, render_execution_appendix
from report.execution_wording import PREMARKET_50_TRIGGER_TEXT


class AppendixRendererTest(unittest.TestCase):
    def test_xuangubao_request_step_uses_current_alias_for_elapsed_time(self):
        self.assertEqual(_request_step_timer_alias("request.xuangubao"), "选股通盘中异动获取")

    def test_render_execution_appendix_can_render_only_enabled_nodes(self):
        lines = render_execution_appendix(
            {
                "data_status": {"hot_rank": True},
                "step_status": {"collect_hot_rank": True},
                "normalized_timer_steps": [("collect_hot_rank", 1.20, 1.20)],
                "total_time": 1.20,
                "target_date": "2026-04-22",
                "generated_at": "2026-04-22 08:30:00",
                "report_version": "v2.5.0",
                "enabled_node_keys": ["header", "timer_stats"],
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("## 附录：数据获取与执行步骤清单", rendered)
        self.assertIn("### 执行时间统计", rendered)
        self.assertNotIn("### 一、数据获取清单", rendered)
        self.assertNotIn("### 二、执行步骤清单", rendered)

    def test_render_execution_appendix_outputs_status_and_timer_tables(self):
        lines = render_execution_appendix(
            {
                "data_status": {
                    "hot_rank": True,
                    "sector_rank": False,
                },
                "step_status": {
                    "collect_hot_rank": True,
                    "build_report": False,
                },
                "normalized_timer_steps": [
                    ("collect_hot_rank", 1.20, 1.20),
                    ("build_report", 2.03, 3.23),
                ],
                "total_time": 3.23,
                "target_date": "2026-04-22",
                "generated_at": "2026-04-22 08:30:00",
                "report_version": "v2.5.0",
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("## 附录：数据获取与执行步骤清单", rendered)
        self.assertIn("| hot_rank | ✅ 成功 | 数据正常 |", rendered)
        self.assertIn("| sector_rank | ❌ 失败 | 数据缺失或获取失败 |", rendered)
        self.assertIn("| collect_hot_rank | ✅ 已执行 | 正常完成 |", rendered)
        self.assertIn("| build_report | ❌ 跳过/失败 | 未执行或失败 |", rendered)
        self.assertIn("| collect_hot_rank | 1.20s | 1.20s |", rendered)
        self.assertIn("**报告版本**: v2.5.0", rendered)
        self.assertIn("**数据日期**: 2026-04-22", rendered)

    def test_render_execution_appendix_splits_xuangubao_counts(self):
        lines = render_execution_appendix(
            {
                "enabled_node_keys": ["data_status"],
                "data_status": {"选股通盘中异动": True},
                "xuangubao_data": {
                    "news_count": 46,
                    "plate_count": 22,
                    "limit_up_reason_count": 156,
                },
            }
        )

        rendered = "\n".join(lines)

        self.assertIn("| 选股通盘中异动 | ✅ 成功 | 新闻46条 / 盘面22个 / 涨停解释156条 |", rendered)
        self.assertIn("| 选股通新闻 | ✅ 成功 | 46条 |", rendered)
        self.assertIn("| 选股通盘面 | ✅ 成功 | 22个 |", rendered)
        self.assertIn("| 选股通涨停解释 | ✅ 成功 | 156条 |", rendered)

    def test_render_execution_appendix_splits_xuangubao_counts_from_request_log(self):
        lines = render_execution_appendix(
            {
                "enabled_node_keys": ["data_status"],
                "data_status": {"选股通盘中异动": True},
                "request_diagnostics": {
                    "request_logs": [
                        {
                            "step": "request.xuangubao",
                            "status": "success",
                            "details": {
                                "news_count": 46,
                                "plate_count": 22,
                                "limit_up_reason_count": 156,
                            },
                        }
                    ]
                },
            }
        )

        rendered = "\n".join(lines)

        self.assertIn("| 选股通盘中异动 | ✅ 成功 | 新闻46条 / 盘面22个 / 涨停解释156条 |", rendered)
        self.assertIn("| 选股通新闻 | ✅ 成功 | 46条 |", rendered)

    def test_render_execution_appendix_counts_request_degraded_rows_in_summary(self):
        lines = render_execution_appendix(
            {
                "enabled_node_keys": ["summary_stats"],
                "data_status": {"market_stats": True},
                "step_status": {"collect_market_stats": True},
                "request_diagnostics": {
                    "request_logs": [
                        {"step": "request.market_stats", "status": "degraded", "provider": "akshare"},
                        {"step": "request.pool_snapshot", "status": "success", "provider": "legacy"},
                    ]
                },
            }
        )

        rendered = "\n".join(lines)

        self.assertIn("数据源获取成功率**: 2/3 (66.7%)", rendered)
        self.assertIn("步骤执行成功率**: 2/3 (66.7%)", rendered)
        self.assertNotIn("1/1 (100.0%)", rendered)

    def test_render_execution_appendix_outputs_data_source_audit_table(self):
        lines = render_execution_appendix(
            {
                "enabled_node_keys": ["data_source_audit"],
                "request_diagnostics": {
                    "request_logs": [
                        {
                            "step": "request.total_turnover",
                            "status": "success",
                            "provider": "tushare.daily",
                            "target_keys": ["total_turnover"],
                            "fallback_used": False,
                        },
                        {
                            "step": "request.hot_rank.primary",
                            "status": "degraded",
                            "provider": "ths_hot_stock",
                            "target_keys": ["hot_rank_top30"],
                            "fallback_used": True,
                            "upstream_error": "tushare empty",
                        },
                        {
                            "step": "request.candidate_history",
                            "status": "success",
                            "provider": "tushare.daily",
                            "target_keys": ["stocks_with_history", "history_fetch_stats"],
                            "fallback_used": False,
                            "diagnostic_note": "Tushare并发4；空数据重试1次；失败代码: 003018",
                        },
                    ]
                },
                "normalized_timer_steps": [
                    ("步骤1: 两市成交额获取", 1.20, 1.20),
                    ("步骤5: 热度前50个股获取", 3.40, 4.60),
                    ("步骤15: 候选股历史成交额获取", 5.52, 10.12),
                ],
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("### 数据源请求审计", rendered)
        self.assertIn("| request.total_turnover | ✅ success | tushare.daily | total_turnover | 1.20s | 否 | - | - |", rendered)
        self.assertIn("| request.hot_rank.primary | ⚠️ degraded | ths_hot_stock | hot_rank_top30 | 3.40s | 是 | tushare empty | - |", rendered)
        self.assertIn("| request.candidate_history | ✅ success | tushare.daily | stocks_with_history；history_fetch_stats | 5.52s | 否 | - | Tushare并发4；空数据重试1次；失败代码: 003018 |", rendered)

    def test_render_execution_appendix_outputs_margin_pressure_full_25_day_table(self):
        margin_rows = []
        for index in range(25):
            margin_rows.append(
                {
                    "trade_date": f"2026-05-{index + 1:02d}",
                    "margin_balance_yi": 28000 + index,
                    "market_turnover_yi": 30000 + index,
                    "margin_turnover_ratio_pct": 93 + index / 10,
                    "pressure_diff_pct": -7 + index / 10,
                    "pressure_label": "中性",
                    "change_text": "待累计" if index == 0 else "+0.10pct",
                }
            )

        lines = render_execution_appendix(
            {
                "enabled_node_keys": ["margin_pressure_detail"],
                "margin_pressure": {
                    "available": True,
                    "rows": margin_rows,
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("### 附录A：融资承接压力完整25日表", rendered)
        self.assertIn("| 日期 | 融资余额 | 两市成交额 | 融资承接比 | 压力差 | 状态 | 较前日 |", rendered)
        self.assertIn("| 2026-05-01 | 28000.00亿 | 30000.00亿 | 93.00% | -7.00% | 中性 | 待累计 |", rendered)
        self.assertIn("| 2026-05-25 | 28024.00亿 | 30024.00亿 | 95.40% | -4.60% | 中性 | +0.10pct |", rendered)
        self.assertLess(rendered.index("2026-05-25"), rendered.index("2026-05-01"))
        self.assertEqual(rendered.count("| 2026-05-"), 25)

    def test_render_execution_appendix_outputs_etf_turnover_full_25_day_table(self):
        etf_rows = []
        for index in range(25):
            etf_rows.append(
                {
                    "trade_date": f"2026-05-{index + 1:02d}",
                    "etf_turnover_yi": 4400 + index,
                    "change_pct": "待累计" if index == 0 else 1.25,
                    "covered_etf_count": 1500 + index,
                }
            )

        lines = render_execution_appendix(
            {
                "enabled_node_keys": ["etf_turnover_detail"],
                "etf_turnover_series": {
                    "available": True,
                    "rows": etf_rows,
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("### 附录A：ETF两市成交额完整25日表", rendered)
        self.assertIn("| 日期 | ETF两市成交额 | 较前日 | 有成交ETF数 |", rendered)
        self.assertIn("| 2026-05-01 | 4400.00亿 | 待累计 | 1500 |", rendered)
        self.assertIn("| 2026-05-25 | 4424.00亿 | +1.25% | 1524 |", rendered)
        self.assertLess(rendered.index("2026-05-25"), rendered.index("2026-05-01"))
        self.assertEqual(rendered.count("| 2026-05-"), 25)

    def test_render_execution_appendix_outputs_new_stock_cycle_table(self):
        lines = render_execution_appendix(
            {
                "enabled_node_keys": ["new_stock_cycle_review"],
                "new_stock_research_pool": [
                    {
                        "code": "920161",
                        "name": "龙辰科技",
                        "listing_window": "missing_listing_date",
                        "new_stock_cycle_state": "single_stock_watch",
                        "c_stage_acceptance": "pending",
                        "emotion_outlet_status": "none",
                        "new_stock_recognition_status": "ordinary_new_stock",
                        "upgrade_eligible": False,
                        "candidate_upgrade_reason": "暂不升级：新股周期证明不足。",
                    },
                    {
                        "code": "301608",
                        "name": "C理奇智能",
                        "listing_window": "recently_listed",
                        "new_stock_cycle_state": "spread",
                        "c_stage_acceptance": "confirmed",
                        "emotion_outlet_status": "market_flag",
                        "new_stock_recognition_status": "emotion_flag",
                        "upgrade_eligible": True,
                        "candidate_upgrade_reason": "新股周期已通过扩散、C阶段承接和情绪出口验证。",
                    },
                ],
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("### 附录A：新股周期判定", rendered)
        self.assertIn("| 标的 | 上市窗口 | 新股周期 | C阶段承接 | 情绪出口 | 辨识度 | 是否升级 | 结论 |", rendered)
        self.assertIn("| 龙辰科技(920161) | missing_listing_date | single_stock_watch | pending | none | ordinary_new_stock | 否 | 有新股研究池，但今日未形成买入资格。暂不升级：新股周期证明不足。 |", rendered)
        self.assertIn("| C理奇智能(301608) | recently_listed | spread | confirmed | market_flag | emotion_flag | 是 | 有新股研究升级，进入观察。 |", rendered)

    def test_render_execution_appendix_marks_same_stock_t_candidate_as_final_execution_object(self):
        lines = render_execution_appendix(
            {
                "enabled_node_keys": ["visible_candidate_lists"],
                "final_target_resolution": {
                    "new_entry_target": {"name": "太极实业", "code": "600667"},
                    "existing_position_target": {"name": "太极实业", "code": "600667"},
                    "display_target": {"name": "太极实业", "code": "600667"},
                    "capital_priority_decision": {
                        "capital_priority": "same_stock_t",
                        "reason": "已有旧仓，同一标的只按T+1确认处理",
                    },
                },
                "extreme_conviction_list": [
                    {
                        "name": "太极实业",
                        "code": "600667",
                        "sector": "半导体",
                        "sniper_role": "候选观察",
                        "conviction_reason": "板块锚定龙",
                        "principle": "只观察",
                    }
                ],
            }
        )

        rendered = "\n".join(lines)
        self.assertIn(
            f"| 1 | 太极实业 | 600667 | 半导体 | 明日执行对象 | 板块锚定龙 | 已进入明日执行计划；{PREMARKET_50_TRIGGER_TEXT} |",
            rendered,
        )

    def test_render_execution_appendix_outputs_empty_continuity_tables_as_recording_contract(self):
        lines = render_execution_appendix(
            {
                "data_status": {},
                "step_status": {},
                "target_date": "2026-04-24",
                "generated_at": "2026-04-25 08:30:00",
                "report_version": "v2.5.0",
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("### 附录B：历史主线池", rendered)
        self.assertIn("| 暂无 | - | 今天开始记录 | 后续日报自动累计 |", rendered)
        self.assertIn("### 附录B：主线成交额占比完整历史", rendered)
        self.assertIn("### 附录C：当前个股观察监控池", rendered)
        self.assertIn("### 附录C：观察对象生命周期表", rendered)
        self.assertIn("| 暂无 | - | - | 0 | - | - | - | 今天开始记录 | 继续累计 |", rendered)

    def test_render_execution_appendix_places_execution_log_after_data_continuity_appendices(self):
        lines = render_execution_appendix(
            {
                "data_status": {"hot_rank": True},
                "step_status": {"collect_hot_rank": True},
                "appendix_b": {"historical_mainline_pool": [{"date": "2026-04-24", "mainline": "半导体"}]},
                "appendix_c": {"current_stock_monitoring_pool": [{"name": "富瀚微", "code": "300613"}]},
            }
        )

        rendered = "\n".join(lines)
        self.assertLess(rendered.index("### 附录B：历史主线池"), rendered.index("## 附录：数据获取与执行步骤清单"))
        self.assertLess(rendered.index("### 附录C：当前个股观察监控池"), rendered.index("## 附录：数据获取与执行步骤清单"))

    def test_render_execution_appendix_outputs_structure_mainline_evolution_table(self):
        lines = render_execution_appendix(
            {
                "enabled_node_keys": ["mainline_continuity"],
                "appendix_b": {
                    "structure_mainline_records": [
                        {
                            "date_range": "2026-04-21 ~ 2026-04-24",
                            "pivot_level": "小中枢",
                            "pivot_range": "3992-4114",
                            "position": "中枢内",
                            "mainline": "半导体",
                            "mainline_degree": "小周期主线",
                            "evolution": "[半导体] 接替 [电力]",
                            "replacement": "接替前主线",
                            "interpretation": "[半导体] 在中枢内接替 [电力]，但还未进入攻击段",
                        }
                    ]
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("### 附录B：中枢对应主线记录", rendered)
        self.assertIn("| 时间段 | 中枢级别 | 中枢区间 | 所在位置 | 对应主线 | 主线程度 | 演化状态 | 接替关系 | 解读 |", rendered)
        self.assertIn("| 2026-04-21 ~ 2026-04-24 | 小中枢 | 3992-4114 | 中枢内 | 半导体 | 小周期主线 | [半导体] 接替 [电力] | 接替前主线 | [半导体] 在中枢内接替 [电力]，但还未进入攻击段 |", rendered)

    def test_render_execution_appendix_outputs_entry_cycle_stop_calibration_table(self):
        lines = render_execution_appendix(
            {
                "enabled_node_keys": ["entry_cycle_calibration"],
                "entry_cycle_calibration": {
                    "cases": [
                        {
                            "name": "中嘉博创",
                            "code": "000889",
                            "case_type": "success",
                            "first_report_date": "2026-04-10",
                            "breakout_date": "2026-04-15",
                            "cycle_gap_trading_days": 3,
                            "max_drawdown_before_breakout_pct": -8.05,
                            "range_amplitude_pct": 13.12,
                            "fixed_5pct_stop_result": "would_false_kill",
                            "recommended_stop_mode": "structure_repair_band",
                            "interpretation": "中嘉博创说明固定-5%会误杀：先看收盘修复和后续再突破。",
                        },
                        {
                            "name": "甘肃能源",
                            "code": "000791",
                            "case_type": "counterexample",
                            "first_report_date": "2026-04-13",
                            "breakout_date": "",
                            "cycle_gap_trading_days": 5,
                            "max_drawdown_before_breakout_pct": -2.10,
                            "range_amplitude_pct": 6.40,
                            "fixed_5pct_stop_result": "would_not_warn",
                            "recommended_stop_mode": "reclaim_failure_exit",
                            "interpretation": "甘肃能源没有站稳关键区，应该按关键区失败降级。",
                        },
                        {
                            "name": "津药药业",
                            "code": "600488",
                            "case_type": "counterexample",
                            "first_report_date": "2026-04-03",
                            "breakout_date": "2026-04-07",
                            "cycle_gap_trading_days": 2,
                            "max_drawdown_before_breakout_pct": -7.22,
                            "range_amplitude_pct": 18.30,
                            "fixed_5pct_stop_result": "would_cut_loss",
                            "recommended_stop_mode": "a_kill_exit",
                            "interpretation": "津药药业应该按A杀出清，不当趋势持有。",
                        },
                    ]
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("### 附录C：介入周期止损校准", rendered)
        self.assertIn("中嘉博创(000889)", rendered)
        self.assertIn("固定-5%会误杀", rendered)
        self.assertIn("结构修复带", rendered)
        self.assertIn("甘肃能源(000791)", rendered)
        self.assertIn("关键区失败降级", rendered)
        self.assertIn("津药药业(600488)", rendered)
        self.assertIn("A杀出清", rendered)


if __name__ == "__main__":
    unittest.main()
