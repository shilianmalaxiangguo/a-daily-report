import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from hooks.infer.use_mainline_analysis import run
from orchestrator.context_store import build_empty_context, merge_hook_patches


class UseMainlineAnalysisTest(unittest.TestCase):
    def test_mainline_hook_selects_strongest_line_and_records_derivation(self):
        fixture_path = ROOT / "tests" / "fixtures" / "golden_days" / "mainline_competition.json"
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        ctx = build_empty_context({"target_date": "2026-04-21"})
        ctx = merge_hook_patches(
            ctx,
            {
                "raw": {"hot_rank": payload["hot_rank"]},
                "normalized": {"market_snapshot": payload["market_snapshot"]},
                "derived": {"market_phase": {"phase": "observe"}},
            },
        )

        result = run(ctx)

        self.assertEqual(result["patches"]["derived"]["mainline"]["primary_line"], "机器人")
        self.assertIn("hot_rank_weight", result["patches"]["derived"]["mainline"])
        self.assertEqual(
            result["patches"]["diagnostics"]["derivations"]["mainline"]["hook_name"],
            "infer.mainline",
        )
        self.assertEqual(result["patches"]["diagnostics"]["derivations"]["mainline"]["hot_rank_count"], 3)
        self.assertIsInstance(result["diagnostics"]["duration_ms"], int)
        self.assertGreaterEqual(result["diagnostics"]["duration_ms"], 0)
        self.assertEqual(result["diagnostics"]["source_used"], "raw.hot_rank + normalized.market_snapshot")
        self.assertFalse(result["diagnostics"]["fallback_used"])

    def test_mainline_hook_degrades_when_market_phase_dependency_is_missing(self):
        fixture_path = ROOT / "tests" / "fixtures" / "golden_days" / "mainline_competition.json"
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        ctx = build_empty_context({"target_date": "2026-04-21"})
        ctx = merge_hook_patches(
            ctx,
            {
                "raw": {"hot_rank": payload["hot_rank"]},
            },
        )

        result = run(ctx)

        self.assertEqual(result["patches"]["derived"]["mainline"]["primary_line"], "机器人")
        self.assertEqual(result["diagnostics"]["status"], "degraded")
        self.assertIn("derived.market_phase", result["diagnostics"]["missing_inputs"])
        self.assertEqual(result["diagnostics"]["source_used"], "raw.hot_rank + normalized.market_snapshot")
        self.assertFalse(result["diagnostics"]["fallback_used"])
        self.assertEqual(
            result["patches"]["diagnostics"]["derivations"]["mainline"]["hook_name"],
            "infer.mainline",
        )

    def test_mainline_hook_uses_deterministic_tie_break_for_equal_sector_counts(self):
        ctx = build_empty_context({"target_date": "2026-04-21"})
        ctx = merge_hook_patches(
            ctx,
            {
                "raw": {
                    "hot_rank": [
                        {"code": "300001", "name": "Alpha", "sector": "机器人"},
                        {"code": "300002", "name": "Beta", "sector": "消费"},
                    ]
                },
                "normalized": {"market_snapshot": {"hot_rank_count": 2}},
                "derived": {"market_phase": {"phase": "observe"}},
            },
        )

        result = run(ctx)

        self.assertEqual(result["patches"]["derived"]["mainline"]["primary_line"], "机器人")
        self.assertEqual(result["patches"]["diagnostics"]["derivations"]["mainline"]["hot_rank_count"], 2)
