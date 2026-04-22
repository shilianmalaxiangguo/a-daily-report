import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from hooks.report.use_strategy_performance_tail import run


class UseStrategyPerformanceTailTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
