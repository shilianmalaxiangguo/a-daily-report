import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from orchestrator.context_store import build_empty_context, merge_hook_patches


class ContextStoreTest(unittest.TestCase):
    def test_merge_hook_patches_updates_only_allowed_zones(self):
        ctx = build_empty_context({"target_date": "2026-04-21"})
        patches = {
            "raw": {"hot_rank": [{"code": "000001", "name": "平安银行"}]},
            "decision": {"final_action": "watch_only"},
        }

        merged = merge_hook_patches(ctx, patches)

        self.assertEqual(merged["request"]["target_date"], "2026-04-21")
        self.assertEqual(merged["raw"]["hot_rank"][0]["code"], "000001")
        self.assertEqual(merged["decision"]["final_action"], "watch_only")
        self.assertEqual(merged["derived"], {})

    def test_merge_hook_patches_deep_merges_diagnostics_derivations(self):
        ctx = build_empty_context({"target_date": "2026-04-21"})
        ctx = merge_hook_patches(
            ctx,
            {
                "diagnostics": {
                    "derivations": {
                        "market_phase": {"hook_name": "infer.market_phase", "phase": "observe"}
                    }
                }
            },
        )

        merged = merge_hook_patches(
            ctx,
            {
                "diagnostics": {
                    "derivations": {
                        "mainline": {"hook_name": "infer.mainline", "primary_line": "军工"}
                    }
                }
            },
        )

        self.assertEqual(
            merged["diagnostics"]["derivations"]["market_phase"]["hook_name"],
            "infer.market_phase",
        )
        self.assertEqual(
            merged["diagnostics"]["derivations"]["mainline"]["hook_name"],
            "infer.mainline",
        )

    def test_merge_hook_patches_rejects_unknown_zones(self):
        ctx = build_empty_context({"target_date": "2026-04-21"})

        with self.assertRaises(ValueError):
            merge_hook_patches(ctx, {"unknown": {"x": 1}})
