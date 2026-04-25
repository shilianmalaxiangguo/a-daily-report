import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from hooks.report.use_execution_appendix_tail import run
from report.appendix_renderer import render_execution_appendix


class UseExecutionAppendixTailTest(unittest.TestCase):
    def test_execution_appendix_tail_hook_normalizes_timer_steps_and_renders_appendix(self):
        captured = {}

        def fake_normalize(timer_summary, step_status=None):
            captured["timer_summary"] = timer_summary
            captured["step_status"] = step_status
            return [["market_environment", 1.2, 1.2]]

        def fake_render(context):
            captured["render_context"] = context
            return [f"appendix:{context.get('report_version')}:{context.get('total_time')}"]

        result = run(
            {
                "inputs": {
                    "data_status": {"hot_rank": "success"},
                    "step_status": {"market_environment": True},
                    "timer_summary": {
                        "steps": [("market_environment", 1.2, 1.2)],
                        "total_time": 3.8,
                    },
                    "target_date": "2026-04-22",
                    "generated_at": "2026-04-22 21:00:00",
                    "report_version": "v2.5.0",
                },
                "helpers": {
                    "normalize_report_timer_steps": fake_normalize,
                    "render_execution_appendix": fake_render,
                },
            }
        )

        payload = result["value"]
        self.assertEqual(payload["exports"]["normalized_timer_steps"], [["market_environment", 1.2, 1.2]])
        self.assertEqual(payload["exports"]["total_time"], 3.8)
        self.assertIn("appendix:v2.5.0:3.8", "\n".join(payload["lines"]))
        self.assertEqual(captured["step_status"], {"market_environment": True})
        self.assertEqual(captured["render_context"]["target_date"], "2026-04-22")
        self.assertEqual(result["diagnostics"]["hook_name"], "report.execution_appendix_tail")
        self.assertTrue(payload["module_logs"])

    def test_execution_appendix_tail_hook_passes_appendix_b_and_c_continuity_inputs(self):
        captured = {}

        def fake_render(context):
            captured["render_context"] = context
            return ["appendix-continuity"]

        result = run(
            {
                "inputs": {
                    "target_date": "2026-04-25",
                    "appendix_b": {
                        "historical_mainline_pool": [{"mainline": "机器人"}],
                        "mainline_switch_log": [{"from_mainline": "低空经济", "to_mainline": "机器人"}],
                        "turnover_share_history": [{"date": "2026-04-24", "mainline": "机器人", "turnover_share_pct": 18.01}],
                        "structure_mainline_records": [{"structure": "日线中枢", "mainline": "机器人"}],
                    },
                    "appendix_c": {
                        "current_stock_monitoring_pool": [{"stock_name": "博杰股份", "stock_code": "002975"}],
                        "stock_lifecycle_records": [
                            {
                                "stock_name": "博杰股份",
                                "stock_code": "002975",
                                "first_report_date": "2026-04-22",
                                "source_report_date": "2026-04-22",
                                "tracked_trading_days": 3,
                                "daily_change_series": ["2026-04-23:+3.20%", "2026-04-24:+1.10%"],
                                "volume_change_summary": "放量",
                                "cumulative_change_pct": 4.33,
                                "current_interpretation": "趋势延续",
                                "current_action": "继续跟踪",
                            }
                        ],
                        "a_kill_elimination_records": [{"stock_name": "冷却股", "stock_code": "000003", "a_kill_date": "2026-04-24"}],
                    },
                },
                "helpers": {"render_execution_appendix": fake_render},
            }
        )

        self.assertEqual(result["value"]["lines"], ["appendix-continuity"])
        render_context = captured["render_context"]
        self.assertEqual(render_context["appendix_b"]["historical_mainline_pool"][0]["mainline"], "机器人")
        lifecycle = render_context["appendix_c"]["stock_lifecycle_records"][0]
        self.assertEqual(lifecycle["first_report_date"], "2026-04-22")
        self.assertEqual(lifecycle["source_report_date"], "2026-04-22")
        self.assertEqual(lifecycle["tracked_trading_days"], 3)
        self.assertEqual(lifecycle["daily_change_series"], ["2026-04-23:+3.20%", "2026-04-24:+1.10%"])
        self.assertEqual(lifecycle["volume_change_summary"], "放量")
        self.assertEqual(lifecycle["cumulative_change_pct"], 4.33)
        self.assertEqual(lifecycle["current_interpretation"], "趋势延续")
        self.assertEqual(lifecycle["current_action"], "继续跟踪")
        self.assertEqual(result["value"]["exports"]["appendix_c"]["a_kill_elimination_records"][0]["stock_code"], "000003")

    def test_execution_appendix_tail_hook_passes_entry_cycle_calibration_inputs(self):
        captured = {}

        def fake_render(context):
            captured["render_context"] = context
            return ["entry-cycle-calibration"]

        calibration = {
            "cases": [
                {
                    "name": "中嘉博创",
                    "code": "000889",
                    "recommended_stop_mode": "structure_repair_band",
                }
            ]
        }

        result = run(
            {
                "inputs": {
                    "entry_cycle_calibration": calibration,
                },
                "helpers": {"render_execution_appendix": fake_render},
            }
        )

        render_context = captured["render_context"]
        self.assertEqual(render_context["entry_cycle_calibration"]["cases"][0]["name"], "中嘉博创")
        self.assertEqual(result["value"]["exports"]["entry_cycle_calibration"]["cases"][0]["code"], "000889")

    def test_execution_appendix_renderer_outputs_appendix_b_and_c_continuity_tables(self):
        lines = render_execution_appendix(
            {
                "enabled_node_keys": ["mainline_continuity", "stock_continuity"],
                "appendix_b": {
                    "historical_mainline_pool": [{"date": "2026-04-24", "mainline": "机器人", "status": "主攻"}],
                    "mainline_switch_log": [{"date": "2026-04-24", "from_mainline": "低空经济", "to_mainline": "机器人", "reason": "成交额切换"}],
                    "turnover_share_history": [{"date": "2026-04-24", "mainline": "机器人", "turnover_share_pct": 18.01}],
                    "structure_mainline_records": [{"date": "2026-04-24", "structure": "日线中枢", "mainline": "机器人", "note": "中枢上沿确认"}],
                },
                "appendix_c": {
                    "current_stock_monitoring_pool": [{"stock_name": "博杰股份", "stock_code": "002975", "source_pool": "main", "current_action": "继续跟踪"}],
                    "stock_lifecycle_records": [
                        {
                            "stock_name": "博杰股份",
                            "stock_code": "002975",
                            "first_report_date": "2026-04-22",
                            "source_report_date": "2026-04-22",
                            "tracked_trading_days": 3,
                            "daily_change_series": ["2026-04-23:+3.20%", "2026-04-24:+1.10%"],
                            "volume_change_summary": "放量",
                            "cumulative_change_pct": 4.33,
                            "current_interpretation": "趋势延续",
                            "current_action": "继续跟踪",
                        }
                    ],
                    "a_kill_elimination_records": [{"stock_name": "冷却股", "stock_code": "000003", "a_kill_date": "2026-04-24", "reason": "A杀冷却"}],
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("### 附录B：历史主线池", rendered)
        self.assertIn("### 附录B：主线切换记录", rendered)
        self.assertIn("### 附录B：主线成交额占比完整历史", rendered)
        self.assertIn("### 附录B：中枢对应主线记录", rendered)
        self.assertIn("### 附录C：当前个股观察监控池", rendered)
        self.assertIn("### 附录C：观察对象生命周期表", rendered)
        self.assertIn("### 附录C：A杀淘汰记录", rendered)
        self.assertIn("首次进入日报日期", rendered)
        self.assertIn("来自哪天日报", rendered)
        self.assertIn("已跟踪交易日数", rendered)
        self.assertIn("次日至今每日涨幅", rendered)
        self.assertIn("量能变化", rendered)
        self.assertIn("累计涨幅", rendered)
        self.assertIn("当前解读", rendered)
        self.assertIn("当前处理", rendered)
        self.assertIn("| 博杰股份(002975) | 2026-04-22 | 2026-04-22 | 3 | 2026-04-23:+3.20%；2026-04-24:+1.10% | 放量 | 4.33 | 趋势延续 | 继续跟踪 |", rendered)


if __name__ == "__main__":
    unittest.main()
