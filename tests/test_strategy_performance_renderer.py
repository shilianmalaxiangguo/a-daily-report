import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

ACTION_TEXT = "参与窗口确认后执行"

from report.strategy_performance_renderer import render_strategy_performance_nodes, render_strategy_performance_section


class StrategyPerformanceRendererTest(unittest.TestCase):
    def test_render_strategy_performance_nodes_can_render_only_enabled_nodes(self):
        helpers = {
            "ledger_mode_frozen": "frozen",
            "ledger_mode_replay": "replay",
            "defensive_exit_rule_text": "30分钟结构止损",
            "format_strategy_record_brief": lambda record: f"{record.get('report_date', '-')}/{record.get('stock_name', '-')}",
            "format_frozen_plan_columns": lambda record: ("买点区间", "60分钟确认", "次日观察边界", "历史异动锚点", "执行止损"),
            "get_plan_action_label": lambda action_type: {"execute": "已执行", "watch_only": "仅观察"}.get(action_type, action_type or "-"),
            "get_recent_record_display_metrics": lambda record: {},
            "format_pct_range": lambda a, b: f"{a}/{b}",
            "format_pct": lambda value: f"{value}",
            "safe_float": lambda value, default=0.0: float(default if value in (None, "") else value),
        }
        summary = {
            "ledger_mode": "frozen",
            "current_plan": {
                "report_date": "2026-04-22",
                "stock_name": "军工一号",
                "stock_code": "000001",
                "action_type": "execute",
                "market_energy_state": "修复",
                "trigger_text": ACTION_TEXT,
            },
            "recent_records": [{"report_date": "2026-04-21", "stock_name": "军工二号"}],
            "windows": [],
        }

        result = render_strategy_performance_nodes(
            {"performance_summary": summary, "helpers": helpers, "enabled_node_keys": ["header"]}
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("## 十五、策略计划账本", rendered)
        self.assertNotIn("### 1. 今日冻结计划", rendered)
        self.assertTrue(result["module_logs"])

    def test_render_strategy_performance_section_outputs_core_blocks(self):
        helpers = {
            "ledger_mode_frozen": "frozen",
            "ledger_mode_replay": "replay",
            "defensive_exit_rule_text": "30分钟结构止损",
            "format_strategy_record_brief": lambda record: f"{record.get('report_date', '-')}/{record.get('stock_name', '-')}",
            "format_frozen_plan_columns": lambda record: ("买点区间", "60分钟确认", "次日观察边界", "历史异动锚点", "执行止损"),
            "get_plan_action_label": lambda action_type: {"execute": "已执行", "watch_only": "仅观察"}.get(action_type, action_type or "-"),
            "get_recent_record_display_metrics": lambda record: {
                "strategy_return_worst": 0.01,
                "strategy_return_best": 0.03,
                "benchmark_return": 0.02,
                "alpha_return_worst": -0.01,
                "alpha_return_best": 0.01,
            },
            "format_pct_range": lambda a, b: f"{a}/{b}",
            "format_pct": lambda value: f"{value}",
            "safe_float": lambda value, default=0.0: float(default if value in (None, "") else value),
        }

        summary = {
            "ledger_mode": "frozen",
            "current_plan": {
                "report_date": "2026-04-22",
                "stock_name": "军工一号",
                "stock_code": "000001",
                "action_type": "execute",
                "market_energy_state": "修复",
                "trigger_text": ACTION_TEXT,
                "factor_snapshot": {
                    "environment": {"score": 8, "position_level": "50%条件执行", "gate_status": "execute_50"},
                    "structure": {"score": 7, "signal_type": "突破", "signal_status": "有效"},
                    "mainline": {"score": 9, "name": "军工"},
                    "memory": {"score": 5, "trusted_tracking_count": 2, "leader_memory_count": 1},
                    "abnormal": {"score": 6, "selected_setup": {"label": "主线异动", "follow_state": "承接"}},
                    "state_machine": {"energy_state": "修复", "flow_direction": "回流军工", "reflection_focus": "先看强分歧后的唯一动作"},
                    "selection": {"selected_candidate": {"decision_stack": {"trigger_score": 7, "tradability_score": 8}}},
                },
            },
            "recent_records": [
                {
                    "report_date": "2026-04-21",
                    "stock_name": "军工二号",
                    "stock_code": "000002",
                    "action_type": "execute",
                    "market_energy_state": "修复",
                    "simulation": {"status_label": "已触发"},
                    "attribution": {
                        "label": "执行有效",
                        "neat_freak_bucket": {"category": "handoff_buying_misjudged", "label": "后手买盘错估"},
                    },
                }
            ],
            "windows": [
                {
                    "name": "本周",
                    "start_date": "2026-04-20",
                    "end_date": "2026-04-22",
                    "plan_count": 3,
                    "triggered_count": 2,
                    "strategy_return_worst": 0.01,
                    "strategy_return_best": 0.05,
                    "benchmark_return": 0.02,
                    "alpha_return_worst": -0.01,
                    "alpha_return_best": 0.03,
                }
            ],
            "attribution_week_review": {
                "start_date": "2026-04-20",
                "end_date": "2026-04-22",
                "items": [
                    {
                        "label": "后手买盘错估",
                        "category": "handoff_buying_misjudged",
                        "count": 1,
                        "sample": "2026-04-21 军工二号(000002)",
                        "legacy_label": "执行有效",
                        "reason": "后手买盘不足后仍执行",
                    }
                ],
            },
            "gem_20cm_week_review": {"start_date": "2026-04-20", "end_date": "2026-04-22", "sample_count": 0},
            "setup_week_review": {"start_date": "2026-04-20", "end_date": "2026-04-22", "items": []},
            "ev_week_review": {"start_date": "2026-04-20", "end_date": "2026-04-22", "items": []},
            "ev_calibration_snapshot": {"global": {"sample_size": 0}},
            "self_calibration": {
                "start_date": "2026-04-20",
                "end_date": "2026-04-22",
                "suggestions": [
                    {
                        "area": "EV",
                        "bias": "样本不足",
                        "why": "当前同类触发记录太少",
                        "action": "继续积累真实触发记录",
                    }
                ],
            },
            "graduation_dashboard": {"source_label": "当前账本", "stage": "验证期", "total_score": 52, "verdict": "继续积累样本", "dimension_scores": [], "checks": [], "next_actions": []},
            "structure_cycle_reviews": [],
        }

        lines = render_strategy_performance_section(summary, helpers)
        rendered = "\n".join(lines)
        self.assertIn("## 十五、策略计划账本", rendered)
        self.assertIn("### 1. 今日冻结计划", rendered)
        self.assertIn("#### 1.1 冻结因子快照", rendered)
        self.assertIn("### 2. 最近计划回放", rendered)
        self.assertIn("### 3. 周 / 月 / 结构周期跑赢上证对比", rendered)
        self.assertIn("### 4. 错因归属周报", rendered)
        self.assertIn("#### 4.1 创业板20cm观察链周报", rendered)
        self.assertIn("### 5. 固定Setup信号库回顾", rendered)
        self.assertIn("### 6. 本周EV命中率周报", rendered)
        self.assertIn("### 7. 系统自校准建议", rendered)
        self.assertIn("### 8. 跨结构周期毕业看板", rendered)
        self.assertIn("| 模块 | 当前判断 | 当前证据 | 下步动作 |", rendered)
        self.assertIn("| 报告日 | 标的 | 状态 | 状态层 | 策略收益区间 | 上证 | 超额区间 | 归因 | 盘后归因桶 |", rendered)
        self.assertIn("| 2026-04-21 | 军工二号(000002) | 已触发 | 修复 | 0.01/0.03 | 0.02 | -0.01/0.01 | 执行有效 | 后手买盘错估 |", rendered)
        self.assertIn("| 盘后归因桶 | 次数 | 代表案例 | 原归因 | 说明 |", rendered)
        self.assertIn("| 后手买盘错估 | 1 | 2026-04-21 军工二号(000002) | 执行有效 | 后手买盘不足后仍执行 |", rendered)
        self.assertNotIn("| 模块 | 当前判断 | 为什么 | 下步动作 |", rendered)

    def test_render_strategy_performance_section_derives_missing_neat_freak_bucket_for_old_records(self):
        helpers = {
            "ledger_mode_frozen": "frozen",
            "ledger_mode_replay": "replay",
            "defensive_exit_rule_text": "30分钟结构止损",
            "format_strategy_record_brief": lambda record: f"{record.get('report_date', '-')}/{record.get('stock_name', '-')}",
            "format_frozen_plan_columns": lambda record: ("-", "-", "-", "-", "-"),
            "get_plan_action_label": lambda action_type: action_type or "-",
            "get_recent_record_display_metrics": lambda record: {
                "strategy_return_worst": 0.0,
                "strategy_return_best": 0.0,
                "benchmark_return": 0.0,
                "alpha_return_worst": 0.0,
                "alpha_return_best": 0.0,
            },
            "format_pct_range": lambda a, b: f"{a}/{b}",
            "format_pct": lambda value: f"{value}",
            "safe_float": lambda value, default=0.0: float(default if value in (None, "") else value),
        }
        summary = {
            "ledger_mode": "frozen",
            "current_plan": {"report_date": "2026-04-22"},
            "recent_records": [
                {
                    "report_date": "2026-04-21",
                    "stock_name": "旧记录",
                    "stock_code": "000003",
                    "action_type": "watch_only",
                    "market_energy_state": "修复",
                    "simulation": {"status": "watch_only"},
                    "attribution": {"category": "env_too_strict", "label": "环境过滤过严"},
                }
            ],
            "windows": [],
            "attribution_week_review": {"start_date": "2026-04-20", "end_date": "2026-04-22", "items": []},
            "gem_20cm_week_review": {"start_date": "2026-04-20", "end_date": "2026-04-22", "sample_count": 0},
            "setup_week_review": {"start_date": "2026-04-20", "end_date": "2026-04-22", "items": []},
            "ev_week_review": {"start_date": "2026-04-20", "end_date": "2026-04-22", "items": []},
            "ev_calibration_snapshot": {"global": {"sample_size": 0}},
            "self_calibration": {"start_date": "2026-04-20", "end_date": "2026-04-22", "suggestions": []},
            "graduation_dashboard": {"source_label": "当前账本", "stage": "验证期", "total_score": 0, "verdict": "-"},
            "structure_cycle_reviews": [],
        }

        rendered = "\n".join(render_strategy_performance_section(summary, helpers))

        self.assertIn("| 2026-04-21 | 旧记录(000003) | watch_only | 修复 | 0.0/0.0 | 0.0 | 0.0/0.0 | 环境过滤过严 | 触发过严 |", rendered)
        self.assertNotIn("| 环境过滤过严 | - |", rendered)

    def test_render_strategy_performance_section_normalizes_unknown_legacy_bucket(self):
        helpers = {
            "ledger_mode_frozen": "frozen",
            "ledger_mode_replay": "replay",
            "defensive_exit_rule_text": "30分钟结构止损",
            "format_strategy_record_brief": lambda record: f"{record.get('report_date', '-')}/{record.get('stock_name', '-')}",
            "format_frozen_plan_columns": lambda record: ("-", "-", "-", "-", "-"),
            "get_plan_action_label": lambda action_type: action_type or "-",
            "get_recent_record_display_metrics": lambda record: {
                "strategy_return_worst": 0.0,
                "strategy_return_best": 0.0,
                "benchmark_return": 0.0,
                "alpha_return_worst": 0.0,
                "alpha_return_best": 0.0,
            },
            "format_pct_range": lambda a, b: f"{a}/{b}",
            "format_pct": lambda value: f"{value}",
            "safe_float": lambda value, default=0.0: float(default if value in (None, "") else value),
        }
        summary = {
            "ledger_mode": "frozen",
            "current_plan": {"report_date": "2026-04-22"},
            "recent_records": [
                {
                    "report_date": "2026-04-21",
                    "stock_name": "旧记录",
                    "stock_code": "000005",
                    "action_type": "watch_only",
                    "market_energy_state": "修复",
                    "simulation": {"status": "watch_only"},
                    "attribution": {
                        "category": "env_too_strict",
                        "label": "环境过滤过严",
                        "neat_freak_bucket": {"category": "free_form_noise", "label": "自由发挥"},
                    },
                }
            ],
            "windows": [],
            "attribution_week_review": {"start_date": "2026-04-20", "end_date": "2026-04-22", "items": []},
            "gem_20cm_week_review": {"start_date": "2026-04-20", "end_date": "2026-04-22", "sample_count": 0},
            "setup_week_review": {"start_date": "2026-04-20", "end_date": "2026-04-22", "items": []},
            "ev_week_review": {"start_date": "2026-04-20", "end_date": "2026-04-22", "items": []},
            "ev_calibration_snapshot": {"global": {"sample_size": 0}},
            "self_calibration": {"start_date": "2026-04-20", "end_date": "2026-04-22", "suggestions": []},
            "graduation_dashboard": {"source_label": "当前账本", "stage": "验证期", "total_score": 0, "verdict": "-"},
            "structure_cycle_reviews": [],
        }

        rendered = "\n".join(render_strategy_performance_section(summary, helpers))

        self.assertIn("| 2026-04-21 | 旧记录(000005) | watch_only | 修复 | 0.0/0.0 | 0.0 | 0.0/0.0 | 环境过滤过严 | 触发过严 |", rendered)
        self.assertNotIn("自由发挥", rendered)

    def test_render_strategy_performance_section_outputs_monitoring_pools(self):
        helpers = {
            "ledger_mode_frozen": "frozen",
            "ledger_mode_replay": "replay",
            "defensive_exit_rule_text": "30分钟结构止损",
            "format_strategy_record_brief": lambda record: "brief",
            "format_frozen_plan_columns": lambda record: ("买点区间", "60分钟确认", "次日观察边界", "历史异动锚点", "执行止损"),
            "get_plan_action_label": lambda action_type: action_type or "-",
            "get_recent_record_display_metrics": lambda record: {},
            "format_pct_range": lambda a, b: f"{a}/{b}",
            "format_pct": lambda value: f"{value}",
            "safe_float": lambda value, default=0.0: float(default if value in (None, "") else value),
        }
        summary = {
            "ledger_mode": "frozen",
            "current_plan": {"report_date": "2026-04-24"},
            "recent_records": [],
            "windows": [],
            "monitoring_pool": {
                "main_pool": [{"stock_name": "博杰股份", "stock_code": "002975", "days_since_selected": 11, "cum_change_pct": 33.18, "pattern_type": "trend_continuation", "current_assessment": "保留", "assessment_reason": "趋势延续，继续跟踪", "anchor_price": 88.63, "observation_band_low": 86.16, "observation_band_high": 91.66, "failure_line": 85.30, "monitoring_rows": [{"date": "2026-04-10", "open": 86.64, "high": 90.67, "low": 86.52, "close": 88.63, "daily_change_pct": 1.99, "cum_change_pct_from_next_day": 0.0, "volume_state": "放量", "candle_shape": "上影阳线", "day_label": "震荡"}] }],
                "secondary_pool": [{"stock_name": "石大胜华", "stock_code": "603026", "days_since_selected": 11, "cum_change_pct": 22.0, "pattern_type": "range_consumption", "current_assessment": "观察", "monitoring_rows": [{"date": "2026-04-23", "open": 104.0, "high": 108.8, "low": 100.0, "close": 102.76, "daily_change_pct": -1.98, "cum_change_pct_from_next_day": 20.0, "volume_state": "平量", "candle_shape": "下影阴线"}]}],
            },
        }

        rendered = "\n".join(render_strategy_performance_section(summary, helpers))
        self.assertIn("主监测池", rendered)
        self.assertIn("副监测池", rendered)
        self.assertIn("博杰股份(002975)", rendered)
        self.assertIn("石大胜华(603026)", rendered)
        self.assertIn("2026-04-10", rendered)
        self.assertIn("上影阳线", rendered)
        self.assertIn("主池明细 - 博杰股份(002975)", rendered)
        self.assertIn("副池明细 - 石大胜华(603026)", rendered)
        self.assertIn("观察价位", rendered)
        self.assertIn("容忍带", rendered)
        self.assertIn("失真线", rendered)
        self.assertIn("趋势延续，继续跟踪", rendered)


if __name__ == "__main__":
    unittest.main()
