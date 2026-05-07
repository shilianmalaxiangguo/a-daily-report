import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from hooks.knowledge.use_trading_philosophy import run
from orchestrator.context_store import build_empty_context


class UseTradingPhilosophyTest(unittest.TestCase):
    def test_hook_materializes_trading_philosophy_knowledge_pack(self):
        ctx = build_empty_context({"target_date": "2026-04-22"})

        result = run(ctx)

        knowledge = result["patches"]["knowledge"]["trading_philosophy"]
        self.assertEqual(knowledge["source"], "skillhub")
        self.assertEqual(knowledge["version"], "2026-04-22")
        self.assertIn("环境条件满足", knowledge["decision_gate_chain"])
        self.assertIn("结构中枢周期", knowledge["main_derivation_chain"])
        self.assertIn(
            "knowledge.trading_philosophy",
            result["patches"]["diagnostics"]["derivations"]["trading_philosophy"]["hook_name"],
        )


if __name__ == "__main__":
    unittest.main()
