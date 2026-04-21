import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from orchestrator.pipeline_runner import run_pipeline


def stub_input(ctx):
    return {
        "value": {},
        "patches": {"normalized": {"market_snapshot": {"hot_rank_count": 1}}},
        "diagnostics": {"hook_name": "input.hot_rank", "status": "success"},
        "artifacts": {},
    }


def stub_report(ctx):
    return {
        "value": {},
        "patches": {"rendered": {"markdown_document": "# report"}},
        "diagnostics": {"hook_name": "report.markdown_document", "status": "success"},
        "artifacts": {},
    }


class PipelineRunnerTest(unittest.TestCase):
    def test_run_pipeline_merges_patches_and_collects_trace(self):
        ctx = run_pipeline(
            request={"target_date": "2026-04-21"},
            hooks=[("input.hot_rank", stub_input), ("report.markdown_document", stub_report)],
        )

        self.assertEqual(ctx["normalized"]["market_snapshot"]["hot_rank_count"], 1)
        self.assertEqual(ctx["rendered"]["markdown_document"], "# report")
        self.assertEqual(ctx["runtime"]["trace_events"][0]["status"], "started")
        self.assertEqual(ctx["runtime"]["trace_events"][-1]["status"], "finished")

    def test_run_pipeline_records_error_and_finishes_when_hook_raises(self):
        class StubTraceRuntime:
            instances = []

            def __init__(self, run_id):
                self.run_id = run_id
                self.events = [{"status": "started"}]
                self.instances.append(self)

            def before_hook(self, hook, inputs):
                self.events.append({"status": "before", "hook": hook, "inputs": list(inputs or [])})

            def after_hook(self, hook, outputs, warnings=None, fallback_used=False, duration_ms=0):
                self.events.append({"status": "success", "hook": hook, "outputs": list(outputs or [])})

            def on_error(self, hook, inputs, error):
                self.events.append({"status": "error", "hook": hook, "error": str(error)})

            def finish(self):
                self.events.append({"status": "finished"})

        def boom(ctx):
            raise RuntimeError("hook failed")

        with patch("orchestrator.pipeline_runner.TraceRuntime", StubTraceRuntime):
            with self.assertRaises(RuntimeError):
                run_pipeline(request={"target_date": "2026-04-21"}, hooks=[("input.hot_rank", boom)])

        events = StubTraceRuntime.instances[0].events
        self.assertEqual(events[-2]["status"], "error")
        self.assertEqual(events[-1]["status"], "finished")
