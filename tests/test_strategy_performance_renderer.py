import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.strategy_performance_renderer import render_strategy_performance_section


class StrategyPerformanceRendererTest(unittest.TestCase):
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
                "trigger_text": "60分钟确认后执行",
                "factor_snapshot": {
                    "environment": {"score": 8, "position_level": "三档", "gate_status": "execute_50"},
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
                    "attribution": {"label": "执行有效"},
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
            "attribution_week_review": {"start_date": "2026-04-20", "end_date": "2026-04-22", "items": []},
            "gem_20cm_week_review": {"start_date": "2026-04-20", "end_date": "2026-04-22", "sample_count": 0},
            "setup_week_review": {"start_date": "2026-04-20", "end_date": "2026-04-22", "items": []},
            "ev_week_review": {"start_date": "2026-04-20", "end_date": "2026-04-22", "items": []},
            "ev_calibration_snapshot": {"global": {"sample_size": 0}},
            "self_calibration": {"start_date": "2026-04-20", "end_date": "2026-04-22", "suggestions": []},
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


if __name__ == "__main__":
    unittest.main()
