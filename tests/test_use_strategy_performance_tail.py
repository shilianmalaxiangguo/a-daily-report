import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from hooks.report.use_strategy_performance_tail import run


class UseStrategyPerformanceTailTest(unittest.TestCase):
    def test_strategy_performance_tail_prefers_unified_renderer(self):
        captured = {"unified": 0, "append": 0}
        data = {
            "strategy_tracking": {
                "performance_summary": {"score": "existing"},
            }
        }

        def fake_build_factor_snapshot(*args, **kwargs):
            return {"factor": "snapshot"}

        def fake_build_plan_context(*args, **kwargs):
            return {"plan": "context"}

        def fake_render_nodes(context):
            captured["unified"] += 1
            self.assertEqual((context.get("performance_summary") or {}).get("score"), "existing")
            return {"lines": ["strategy-unified"], "module_logs": []}

        def fake_append_section(report, performance_summary):
            captured["append"] += 1
            report.append("strategy-append")

        result = run(
            {
                "inputs": {
                    "target_date": "2026-04-22",
                    "data": data,
                    "market_zhongshu": {"phase": "attack"},
                    "final_gate": {"can_new_entry": True},
                    "exit_analysis": {"sector_name": "军工"},
                    "position_level": "三档（进攻档）",
                    "position_reason": "环境放行",
                    "best_stock": {"name": "军工一号", "code": "000001"},
                    "watch_anchor": {"name": "观察锚点", "code": "000002"},
                    "watch_anchor_type": "继续看谁",
                    "persist_strategy_tracking": False,
                    "run_mode": "replay",
                    "factor_context": {},
                },
                "helpers": {
                    "build_strategy_factor_snapshot": fake_build_factor_snapshot,
                    "build_strategy_plan_context": fake_build_plan_context,
                    "render_strategy_performance_nodes": fake_render_nodes,
                    "append_strategy_performance_section": fake_append_section,
                },
            }
        )

        text = "\n".join(result["value"]["lines"])
        self.assertIn("strategy-unified", text)
        self.assertEqual(captured["unified"], 1)
        self.assertEqual(captured["append"], 0)

    def test_strategy_performance_tail_updates_ledger_when_persist_enabled(self):
        captured = {"update_calls": 0}
        data = {}

        def fake_build_factor_snapshot(*args, **kwargs):
            return {"factor": "snapshot"}

        def fake_build_plan_context(*args, **kwargs):
            return {"plan": "context"}

        def fake_update_book(data_arg, target_date, plan_context, market_zhongshu, ledger_mode="frozen"):
            captured["update_calls"] += 1
            captured["update_args"] = {
                "target_date": target_date,
                "plan_context": plan_context,
                "ledger_mode": ledger_mode,
            }
            return {"score": "summary"}

        def fake_append_section(report, performance_summary):
            captured["appended_summary"] = performance_summary
            report.append(f"strategy:{performance_summary.get('score')}")

        result = run(
            {
                "inputs": {
                    "target_date": "2026-04-22",
                    "data": data,
                    "market_zhongshu": {"phase": "attack"},
                    "final_gate": {"can_new_entry": True},
                    "exit_analysis": {"sector_name": "军工"},
                    "position_level": "三档（进攻档）",
                    "position_reason": "环境放行",
                    "best_stock": {"name": "军工一号", "code": "000001"},
                    "watch_anchor": {"name": "观察锚点", "code": "000002"},
                    "watch_anchor_type": "继续看谁",
                    "persist_strategy_tracking": True,
                    "run_mode": "frozen",
                    "factor_context": {
                        "main_sectors_info": [{"name": "军工"}],
                        "secondary_sectors_info": [{"name": "机器人"}],
                    },
                },
                "helpers": {
                    "build_strategy_factor_snapshot": fake_build_factor_snapshot,
                    "build_strategy_plan_context": fake_build_plan_context,
                    "update_strategy_performance_book": fake_update_book,
                    "append_strategy_performance_section": fake_append_section,
                },
            }
        )

        payload = result["value"]
        self.assertEqual(payload["exports"]["strategy_factor_snapshot"], {"factor": "snapshot"})
        self.assertEqual(payload["exports"]["strategy_plan_context"], {"plan": "context"})
        self.assertEqual(payload["exports"]["strategy_performance_summary"], {"score": "summary"})
        self.assertEqual(captured["update_calls"], 1)
        self.assertEqual(captured["appended_summary"], {"score": "summary"})
        self.assertIn("strategy:summary", "\n".join(payload["lines"]))
        self.assertEqual(data["strategy_tracking"]["plan"], {"plan": "context"})
        self.assertEqual(result["diagnostics"]["hook_name"], "report.strategy_performance_tail")

    def test_strategy_performance_tail_reuses_existing_summary_when_replay_without_persist(self):
        captured = {"update_calls": 0}
        data = {
            "strategy_tracking": {
                "performance_summary": {"score": "existing"},
            }
        }

        def fake_build_factor_snapshot(*args, **kwargs):
            return {"factor": "snapshot"}

        def fake_build_plan_context(*args, **kwargs):
            return {"plan": "context"}

        def fake_update_book(*args, **kwargs):
            captured["update_calls"] += 1
            return {"score": "new"}

        def fake_append_section(report, performance_summary):
            captured["appended_summary"] = performance_summary
            report.append(f"strategy:{performance_summary.get('score')}")

        result = run(
            {
                "inputs": {
                    "target_date": "2026-04-22",
                    "data": data,
                    "market_zhongshu": {"phase": "attack"},
                    "final_gate": {"can_new_entry": True},
                    "exit_analysis": {"sector_name": "军工"},
                    "position_level": "三档（进攻档）",
                    "position_reason": "环境放行",
                    "best_stock": {"name": "军工一号", "code": "000001"},
                    "watch_anchor": {"name": "观察锚点", "code": "000002"},
                    "watch_anchor_type": "继续看谁",
                    "persist_strategy_tracking": False,
                    "run_mode": "replay",
                    "factor_context": {},
                },
                "helpers": {
                    "build_strategy_factor_snapshot": fake_build_factor_snapshot,
                    "build_strategy_plan_context": fake_build_plan_context,
                    "update_strategy_performance_book": fake_update_book,
                    "append_strategy_performance_section": fake_append_section,
                },
            }
        )

        payload = result["value"]
        self.assertEqual(captured["update_calls"], 0)
        self.assertEqual(captured["appended_summary"], {"score": "existing"})
        self.assertEqual(payload["exports"]["strategy_performance_summary"], {"score": "existing"})
        self.assertIn("strategy:existing", "\n".join(payload["lines"]))

    def test_strategy_performance_tail_backfills_monitoring_pool_from_factor_snapshot(self):
        captured = {}
        data = {
            "strategy_tracking": {
                "performance_summary": {
                    "score": "existing",
                    "current_plan": {
                        "factor_snapshot": {
                            "core_stocks": [{"name": "博杰股份", "code": "002975"}],
                            "secondary_stocks": [],
                            "crossline_observation_stocks": [],
                            "gem_observation_stocks": [],
                            "generic_watch_stocks": [],
                        }
                    },
                },
            }
        }

        def fake_build_factor_snapshot(*args, **kwargs):
            return {
                "core_stocks": [{"name": "博杰股份", "code": "002975"}],
                "secondary_stocks": [],
                "crossline_observation_stocks": [],
                "gem_observation_stocks": [],
                "generic_watch_stocks": [],
            }

        def fake_build_plan_context(*args, **kwargs):
            return {"plan": "context"}

        def fake_append_section(report, performance_summary):
            captured["summary"] = performance_summary
            report.append(str(bool((performance_summary.get("monitoring_pool", {}) or {}).get("main_pool"))))

        result = run(
            {
                "inputs": {
                    "target_date": "2026-04-22",
                    "data": data,
                    "market_zhongshu": {"phase": "attack"},
                    "final_gate": {"can_new_entry": True},
                    "exit_analysis": {"sector_name": "军工"},
                    "position_level": "三档（进攻档）",
                    "position_reason": "环境放行",
                    "best_stock": {"name": "军工一号", "code": "000001"},
                    "watch_anchor": {"name": "观察锚点", "code": "000002"},
                    "watch_anchor_type": "继续看谁",
                    "persist_strategy_tracking": False,
                    "run_mode": "replay",
                    "factor_context": {},
                },
                "helpers": {
                    "build_strategy_factor_snapshot": fake_build_factor_snapshot,
                    "build_strategy_plan_context": fake_build_plan_context,
                    "append_strategy_performance_section": fake_append_section,
                },
            }
        )

        payload = result["value"]
        self.assertTrue((captured["summary"].get("monitoring_pool", {}) or {}).get("main_pool"))
        self.assertIn("True", "\n".join(payload["lines"]))

    def test_strategy_performance_tail_skips_recompute_when_render_only_and_summary_missing(self):
        captured = {"update_calls": 0}
        data = {}

        def fake_build_factor_snapshot(*args, **kwargs):
            return {"factor": "snapshot"}

        def fake_build_plan_context(*args, **kwargs):
            return {"plan": "context"}

        def fake_update_book(*args, **kwargs):
            captured["update_calls"] += 1
            return {"score": "new"}

        def fake_append_section(report, performance_summary):
            captured["appended_summary"] = performance_summary
            if performance_summary:
                report.append(f"strategy:{performance_summary.get('score')}")

        result = run(
            {
                "inputs": {
                    "target_date": "2026-04-22",
                    "data": data,
                    "market_zhongshu": {"phase": "attack"},
                    "final_gate": {"can_new_entry": True},
                    "exit_analysis": {"sector_name": "军工"},
                    "position_level": "三档（进攻档）",
                    "position_reason": "环境放行",
                    "best_stock": {"name": "军工一号", "code": "000001"},
                    "watch_anchor": {"name": "观察锚点", "code": "000002"},
                    "watch_anchor_type": "继续看谁",
                    "persist_strategy_tracking": False,
                    "run_mode": "replay",
                    "factor_context": {},
                },
                "helpers": {
                    "build_strategy_factor_snapshot": fake_build_factor_snapshot,
                    "build_strategy_plan_context": fake_build_plan_context,
                    "update_strategy_performance_book": fake_update_book,
                    "append_strategy_performance_section": fake_append_section,
                },
            }
        )

        payload = result["value"]
        self.assertEqual(captured["update_calls"], 0)
        self.assertEqual(captured["appended_summary"], {})
        self.assertEqual(payload["exports"]["strategy_performance_summary"], {})
        self.assertEqual(payload["lines"], [])


    def test_strategy_performance_tail_appends_monitoring_pool_summary(self):
        captured = {}
        data = {
            "strategy_tracking": {
                "performance_summary": {
                    "score": "existing",
                    "monitoring_pool": {
                        "main_pool": [{"stock_name": "博杰股份", "stock_code": "002975", "days_since_selected": 11, "cum_change_pct": 33.18, "pattern_type": "trend_continuation", "current_assessment": "保留"}],
                        "secondary_pool": [],
                    },
                },
            }
        }

        def fake_build_factor_snapshot(*args, **kwargs):
            return {"factor": "snapshot"}

        def fake_build_plan_context(*args, **kwargs):
            return {"plan": "context"}

        def fake_append_section(report, performance_summary):
            from report.strategy_performance_renderer import render_strategy_performance_section
            report.extend(render_strategy_performance_section(performance_summary, {
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
            }))

        result = run(
            {
                "inputs": {
                    "target_date": "2026-04-22",
                    "data": data,
                    "market_zhongshu": {"phase": "attack"},
                    "final_gate": {"can_new_entry": True},
                    "exit_analysis": {"sector_name": "军工"},
                    "position_level": "三档（进攻档）",
                    "position_reason": "环境放行",
                    "best_stock": {"name": "军工一号", "code": "000001"},
                    "watch_anchor": {"name": "观察锚点", "code": "000002"},
                    "watch_anchor_type": "继续看谁",
                    "persist_strategy_tracking": False,
                    "run_mode": "replay",
                    "factor_context": {},
                },
                "helpers": {
                    "build_strategy_factor_snapshot": fake_build_factor_snapshot,
                    "build_strategy_plan_context": fake_build_plan_context,
                    "append_strategy_performance_section": fake_append_section,
                },
            }
        )

        text = "\n".join(result["value"]["lines"])
        self.assertIn("主监测池", text)
        self.assertIn("博杰股份(002975)", text)


if __name__ == "__main__":
    unittest.main()
