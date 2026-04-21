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
        self.assertEqual(result["diagnostics"]["status"], "success")
        self.assertEqual(result["diagnostics"]["source_used"], "normalized.market_snapshot")
        self.assertFalse(result["diagnostics"]["fallback_used"])
        self.assertGreaterEqual(result["diagnostics"]["duration_ms"], 0)
        self.assertEqual(
            result["patches"]["diagnostics"]["derivations"]["market_phase"]["dt_count"],
            11,
        )
        self.assertEqual(
            result["patches"]["diagnostics"]["derivations"]["market_phase"]["zhongshu_signal"],
            "not_open",
        )
        self.assertGreaterEqual(
            result["patches"]["diagnostics"]["derivations"]["market_phase"]["confidence"],
            0.5,
        )

    def test_market_phase_hook_marks_missing_inputs_as_degraded_observe(self):
        ctx = build_empty_context({"target_date": "2026-04-21"})

        result = run(ctx)

        self.assertEqual(result["value"]["market_phase"], "observe")
        self.assertEqual(result["patches"]["derived"]["market_phase"]["phase"], "observe")
        self.assertEqual(result["diagnostics"]["status"], "degraded")
        self.assertEqual(
            result["diagnostics"]["missing_inputs"],
            [
                "normalized.market_snapshot.turnover_change_pct",
                "normalized.market_snapshot.rise_fall_ratio",
                "normalized.market_snapshot.dt_count",
                "normalized.market_snapshot.zhongshu_signal",
            ],
        )
        self.assertEqual(result["diagnostics"]["source_used"], "normalized.market_snapshot")
        self.assertFalse(result["diagnostics"]["fallback_used"])
        self.assertEqual(
            result["patches"]["diagnostics"]["derivations"]["market_phase"]["dt_count"],
            0,
        )
        self.assertEqual(
            result["patches"]["diagnostics"]["derivations"]["market_phase"]["zhongshu_signal"],
            "unknown",
        )
