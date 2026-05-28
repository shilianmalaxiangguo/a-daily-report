import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def _m(*parts):
    return "".join(parts)

from hooks.decision.use_action_plan import run
from orchestrator.context_store import build_empty_context, merge_hook_patches


class UseActionPlanTest(unittest.TestCase):
    def test_action_plan_maps_legacy_conditional_label_to_50_attack_summary(self):
        ctx = build_empty_context({"target_date": "2026-04-22"})
        ctx = merge_hook_patches(
            ctx,
            {
                "derived": {
                    "market_phase": {"phase": "observe"},
                    "mainline": {"primary_line": "军工"},
                    "strategy_contract": {
                        "contract_label": "conditional_entry",
                        "permission_label": "attack_50_ready",
                        "action_plan": "沿军工进入50%标准进攻，前提是次日完成60分钟确认和参与窗口",
                    },
                },
                "decision": {
                    "execution_permission": {
                        "label": "attack_50_ready",
                    }
                },
            },
        )

        result = run(ctx)

        action_plan = result["patches"]["decision"]["action_plan"]
        self.assertEqual(action_plan["action_label"], "execute_50")
        self.assertIn("50%标准进攻", action_plan["headline"])
        self.assertIn("军工", action_plan["headline"])
        self.assertIn("固定交易窗口条件", action_plan["trigger"])
        self.assertIn("竞价表态", action_plan["trigger"])
        self.assertIn("回封", action_plan["trigger"])
        self.assertIn("09:50-10:10窗口", action_plan["trigger"])
        self.assertNotIn("参与窗口和60分钟确认", action_plan["trigger"])
        self.assertNotIn("同时成立", action_plan["trigger"])
        rendered = "\n".join(str(value) for value in action_plan.values())
        self.assertNotIn(_m("30%", "条件试错"), rendered)
        self.assertNotIn("attack_50_ready", rendered)

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
