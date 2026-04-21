import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from hooks.decision.use_action_plan import run
from orchestrator.context_store import build_empty_context, merge_hook_patches


class UseActionPlanTest(unittest.TestCase):
    def test_action_plan_builds_conditional_entry_summary(self):
        ctx = build_empty_context({"target_date": "2026-04-22"})
        ctx = merge_hook_patches(
            ctx,
            {
                "derived": {
                    "market_phase": {"phase": "observe"},
                    "mainline": {"primary_line": "军工"},
                    "strategy_contract": {
                        "contract_label": "conditional_entry",
                        "permission_label": "conditional_30",
                        "action_plan": "沿军工保留30%条件试错，前提是次日完成60分钟确认",
                    },
                },
                "decision": {
                    "execution_permission": {
                        "label": "conditional_30",
                    }
                },
            },
        )

        result = run(ctx)

        action_plan = result["patches"]["decision"]["action_plan"]
        self.assertEqual(action_plan["action_label"], "conditional_entry")
        self.assertIn("30%条件试错", action_plan["headline"])
        self.assertIn("军工", action_plan["headline"])
        self.assertIn("60分钟确认", action_plan["trigger"])

    def test_action_plan_builds_watch_only_summary_when_defensive(self):
        ctx = build_empty_context({"target_date": "2026-04-22"})
        ctx = merge_hook_patches(
            ctx,
            {
                "derived": {
                    "market_phase": {"phase": "defend"},
                    "mainline": {"primary_line": "军工"},
                    "strategy_contract": {
                        "contract_label": "defense_observe",
                        "permission_label": "watch_only",
                        "action_plan": "环境未开，只观察主线与旧仓处理，不做新增参与",
                    },
                },
                "decision": {
                    "execution_permission": {
                        "label": "watch_only",
                    }
                },
            },
        )

        result = run(ctx)

        action_plan = result["patches"]["decision"]["action_plan"]
        self.assertEqual(action_plan["action_label"], "watch_only")
        self.assertIn("只观察", action_plan["headline"])
        self.assertIn("环境未开", action_plan["rationale"])


if __name__ == "__main__":
    unittest.main()
