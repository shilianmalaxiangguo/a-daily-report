import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def _m(*parts):
    return "".join(parts)

from hooks.infer.use_strategy_contract import run
from orchestrator.context_store import build_empty_context, merge_hook_patches


class UseStrategyContractTest(unittest.TestCase):
    def test_strategy_contract_builds_conditional_entry_contract_for_clear_mainline(self):
        ctx = build_empty_context({"target_date": "2026-04-22"})
        ctx = merge_hook_patches(
            ctx,
            {
                "derived": {
                    "market_phase": {"phase": "observe"},
                    "mainline": {"primary_line": "军工"},
                }
            },
        )

        result = run(ctx)

        contract = result["patches"]["derived"]["strategy_contract"]
        self.assertEqual(contract["contract_label"], "standard_attack")
        self.assertEqual(contract["permission_label"], "execute_50")
        self.assertIn("固定交易窗口条件", contract["gate_chain"])
        self.assertIn("军工", contract["action_plan"])
        self.assertIn("50%条件执行", contract["action_plan"])
        self.assertIn("固定交易窗口条件", contract["action_plan"])
        self.assertIn("强核心", contract["action_plan"])
        self.assertIn("普通结构", contract["action_plan"])
        self.assertNotIn("参与窗口和60分钟确认", contract["action_plan"])
        self.assertNotIn("同时成立", contract["action_plan"])
        self.assertNotIn(_m("3", "0%", "条件", "试错"), contract["action_plan"])
        self.assertEqual(
            result["patches"]["diagnostics"]["derivations"]["strategy_contract"]["hook_name"],
            "infer.strategy_contract",
        )

    def test_strategy_contract_for_defensive_phase_drops_to_watch_only(self):
        ctx = build_empty_context({"target_date": "2026-04-22"})
        ctx = merge_hook_patches(
            ctx,
            {
                "derived": {
                    "market_phase": {"phase": "defend"},
                    "mainline": {"primary_line": "军工"},
                }
            },
        )

        result = run(ctx)

        contract = result["patches"]["derived"]["strategy_contract"]
        self.assertEqual(contract["contract_label"], "defense_observe")
        self.assertEqual(contract["permission_label"], "watch_only")
        self.assertIn("只观察", contract["action_plan"])


if __name__ == "__main__":
    unittest.main()
