import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from orchestrator.module_log_runtime import make_module_log


class ModuleLogRuntimeTest(unittest.TestCase):
    def test_make_module_log_collects_standardized_fields(self):
        log = make_module_log(
            "infer.mainline",
            diagnostics={"status": "success", "duration_ms": 12, "warnings": ["x"], "fallback_used": True},
            patches={"derived": {}, "diagnostics": {}},
            artifacts={"snapshot_path": "/tmp/a.json"},
        )

        self.assertEqual(log["hook_name"], "infer.mainline")
        self.assertEqual(log["status"], "success")
        self.assertEqual(log["duration_ms"], 12)
        self.assertEqual(log["warnings"], ["x"])
        self.assertEqual(log["output_zones"], ["derived", "diagnostics"])
        self.assertEqual(log["artifacts"], ["snapshot_path"])
        self.assertTrue(log["fallback_used"])


if __name__ == "__main__":
    unittest.main()
