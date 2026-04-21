import sys
import unittest
from pathlib import Path

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
