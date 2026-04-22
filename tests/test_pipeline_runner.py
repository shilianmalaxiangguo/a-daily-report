import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from hooks.report.use_markdown_document import run as run_markdown_document
from legacy.daily_report_entry_demo_legacy_bridge import build_legacy_sections
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
        self.assertEqual(len(ctx["runtime"]["module_logs"]), 2)
        self.assertEqual(ctx["runtime"]["module_logs"][0]["hook_name"], "input.hot_rank")
        self.assertEqual(ctx["runtime"]["module_logs"][0]["status"], "success")
        self.assertEqual(ctx["runtime"]["module_logs"][1]["hook_name"], "report.markdown_document")
        self.assertIn("rendered", ctx["runtime"]["module_logs"][1]["output_zones"])

    def test_run_pipeline_supports_legacy_new_mixed_hooks(self):
        def legacy_sections_hook(ctx):
            sections = build_legacy_sections({"source": "legacy"}, ctx["request"]["target_date"])
            return {
                "value": {},
                "patches": {"sections": sections},
                "diagnostics": {"hook_name": "legacy.bridge", "status": "success"},
                "artifacts": {},
            }

        legacy_markdown = (
            "# Legacy Preamble\n\n"
            "## Environment\n"
            "Legacy environment body\n\n"
            "## Observation\n"
            "Legacy observation body\n\n"
            "## Execution\n"
            "Legacy execution body\n\n"
            "## Review\n"
            "Legacy review body\n\n"
            "## Summary\n"
            "Legacy summary body"
        )

        with patch("daily_report_render.generate_markdown_report", return_value=legacy_markdown):
            ctx = run_pipeline(
                request={"target_date": "2026-04-21"},
                hooks=[
                    ("legacy.bridge", legacy_sections_hook),
                    ("report.markdown_document", run_markdown_document),
                ],
        )

        self.assertEqual(ctx["sections"]["preamble"], "# Legacy Preamble")
        self.assertEqual(ctx["sections"]["environment"], "## Environment\nLegacy environment body")
        self.assertEqual(ctx["sections"]["observation"], "## Observation\nLegacy observation body")
        self.assertEqual(ctx["sections"]["execution"], "## Execution\nLegacy execution body")
        self.assertEqual(ctx["sections"]["review"], "## Review\nLegacy review body")
        self.assertEqual(ctx["sections"]["summary"], "## Summary\nLegacy summary body")
        self.assertEqual(
            ctx["rendered"]["markdown_document"],
            (
                "# Legacy Preamble\n\n"
                "## Environment\nLegacy environment body\n\n"
                "## Observation\nLegacy observation body\n\n"
                "## Execution\nLegacy execution body\n\n"
                "## Review\nLegacy review body\n\n"
                "## Summary\nLegacy summary body"
            ),
        )

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

    def test_run_pipeline_records_module_error_log(self):
        ctx = {
            "request": {"target_date": "2026-04-21"},
            "raw": {},
            "normalized": {},
            "derived": {},
            "decision": {},
            "knowledge": {},
            "sections": {},
            "rendered": {},
            "diagnostics": {},
            "runtime": {"module_logs": []},
        }

        def boom(ctx):
            raise RuntimeError("hook failed")

        with patch("orchestrator.pipeline_runner.build_empty_context", return_value=ctx):
            try:
                run_pipeline(request={"target_date": "2026-04-21"}, hooks=[("input.hot_rank", boom)])
            except RuntimeError as exc:
                self.assertEqual(str(exc), "hook failed")
            else:
                self.fail("expected RuntimeError")

        self.assertEqual(len(ctx["runtime"]["module_logs"]), 1)
        self.assertEqual(ctx["runtime"]["module_logs"][0]["hook_name"], "input.hot_rank")
        self.assertEqual(ctx["runtime"]["module_logs"][0]["status"], "error")
        self.assertIn("hook failed", ctx["runtime"]["module_logs"][0]["error"])
