import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from hooks.trace.trace_runtime import TraceRuntime


class TraceRuntimeTest(unittest.TestCase):
    def test_trace_runtime_records_before_after_and_error_events(self):
        runtime = TraceRuntime(run_id="run-1")

        runtime.before_hook("infer.market_phase", ["normalized.market_snapshot"])
        runtime.after_hook(
            "infer.market_phase",
            ["derived.market_phase"],
            warnings=["turnover fallback"],
            fallback_used=True,
            duration_ms=82,
        )
        runtime.on_error(
            "infer.mainline",
            ["derived.market_phase"],
            "missing hot rank payload",
        )

        events = runtime.events

        self.assertEqual(events[0]["status"], "started")
        self.assertEqual(events[1]["hook"], "infer.market_phase")
        self.assertEqual(events[2]["fallback_used"], True)
        self.assertEqual(events[3]["status"], "error")
        self.assertIn("missing hot rank payload", events[3]["error"])
