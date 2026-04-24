import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from daily_report_render import (
    REPORT_VARIANT_FULL,
    REPORT_VARIANT_SUMMARY,
    build_report_outputs,
    generate_markdown_report,
    generate_markdown_report_from_sections,
)


class DailyReportRenderTest(unittest.TestCase):
    def test_build_report_outputs_suppresses_helper_diagnostics_for_summary_render(self):
        with patch("daily_report_render._render_report_with_display_mode", side_effect=["# full", "# summary"]) as render_mock:
            outputs = build_report_outputs({"foo": "bar"}, "2026-04-22")

        self.assertIn(REPORT_VARIANT_FULL, outputs)
        self.assertIn(REPORT_VARIANT_SUMMARY, outputs)
        self.assertEqual(outputs[REPORT_VARIANT_FULL], "# full")
        self.assertEqual(outputs[REPORT_VARIANT_SUMMARY], "# summary")
        self.assertNotIn("阅读模式", outputs[REPORT_VARIANT_FULL])
        self.assertNotIn("阅读模式", outputs[REPORT_VARIANT_SUMMARY])
        self.assertEqual(render_mock.call_count, 2)
        self.assertTrue(render_mock.call_args_list[0].kwargs["emit_helper_diagnostics"])
        self.assertFalse(render_mock.call_args_list[1].kwargs["emit_helper_diagnostics"])
        self.assertFalse(render_mock.call_args_list[0].kwargs["persist_strategy_tracking"])
        self.assertFalse(render_mock.call_args_list[1].kwargs["persist_strategy_tracking"])
        self.assertIs(render_mock.call_args_list[0].kwargs["shared_runtime_cache"], render_mock.call_args_list[1].kwargs["shared_runtime_cache"])

    def test_generate_markdown_report_from_sections_deduplicates_no_trade_and_filters_draft_explanations(self):
        rendered = generate_markdown_report_from_sections(
            {
                "preamble": "⛔ 当前先不开新仓: 一档（空仓档），本轮不做PK出手结论。",
                "execution": "⛔ 当前先不开新仓: 一档（空仓档），本轮不做PK出手结论。\n为什么要看这块：这是草稿解释。\n结论：空仓等待。",
            }
        )

        self.assertEqual(rendered.count("当前先不开新仓"), 1)
        self.assertIn("结论：空仓等待。", rendered)
        self.assertNotIn("为什么要看这块", rendered)
        self.assertNotIn("草稿解释", rendered)

    def test_generate_markdown_report_from_sections_keeps_expected_order(self):
        rendered = generate_markdown_report_from_sections(
            {
                "preamble": "# Preamble",
                "environment": "",
                "observation": "## Observation",
                "execution": "## Execution",
                "review": "## Review",
                "summary": "## Summary",
            }
        )

        self.assertEqual(rendered, "# Preamble\n\n## Observation\n\n## Execution\n\n## Review\n\n## Summary")

    def test_generate_markdown_report_from_sections_handles_none(self):
        self.assertEqual(generate_markdown_report_from_sections(None), "")

    def test_generate_markdown_report_uses_legacy_path_when_sections_are_absent(self):
        fake_demo = types.ModuleType("daily_report_entry_demo")
        fake_demo.generate_markdown_report = lambda *args, **kwargs: "legacy report"

        with patch.dict(sys.modules, {"daily_report_entry_demo": fake_demo}):
            rendered = generate_markdown_report({"foo": "bar"}, "2026-04-21")

        self.assertEqual(rendered, "legacy report")

    def test_generate_markdown_report_prefers_sections_path_when_sections_exist(self):
        fake_demo = types.ModuleType("daily_report_entry_demo")
        fake_demo.generate_markdown_report = lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("legacy path should not run")
        )

        with patch.dict(sys.modules, {"daily_report_entry_demo": fake_demo}):
            rendered = generate_markdown_report(
                {
                    "sections": {
                        "preamble": "# Preamble",
                        "summary": "## Summary",
                    }
                },
                "2026-04-21",
            )

        self.assertEqual(rendered, "# Preamble\n\n## Summary")
