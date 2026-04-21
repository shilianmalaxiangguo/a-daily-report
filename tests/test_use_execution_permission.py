import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from hooks.infer.use_execution_permission import run
from orchestrator.context_store import build_empty_context, merge_hook_patches


class UseExecutionPermissionTest(unittest.TestCase):
    def test_execution_permission_returns_watch_only_for_defensive_phase(self):
        fixture_path = ROOT / "tests" / "fixtures" / "golden_days" / "execution_permission_watch_only.json"
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        ctx = build_empty_context({"target_date": "2026-04-21"})
        ctx = merge_hook_patches(ctx, payload)

        result = run(ctx)

        self.assertEqual(result["patches"]["decision"]["execution_permission"]["label"], "watch_only")
        self.assertIn("phase=defend", result["patches"]["decision"]["execution_permission"]["reason"])
        self.assertEqual(
            result["patches"]["diagnostics"]["derivations"]["execution_permission"]["hook_name"],
            "infer.execution_permission",
        )
