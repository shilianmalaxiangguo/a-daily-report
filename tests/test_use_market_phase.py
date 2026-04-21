import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from hooks.infer.use_market_phase import run
from orchestrator.context_store import build_empty_context, merge_hook_patches


class UseMarketPhaseTest(unittest.TestCase):
    def test_market_phase_hook_builds_phase_and_derivation_record(self):
        fixture_path = ROOT / "tests" / "fixtures" / "golden_days" / "market_phase_defend.json"
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        ctx = build_empty_context({"target_date": "2026-04-21"})
        ctx = merge_hook_patches(ctx, {"normalized": {"market_snapshot": payload}})

        result = run(ctx)

        self.assertEqual(result["patches"]["derived"]["market_phase"]["phase"], "defend")
        self.assertEqual(
            result["patches"]["diagnostics"]["derivations"]["market_phase"]["hook_name"],
            "infer.market_phase",
        )
        self.assertGreaterEqual(
            result["patches"]["diagnostics"]["derivations"]["market_phase"]["confidence"],
            0.5,
        )
