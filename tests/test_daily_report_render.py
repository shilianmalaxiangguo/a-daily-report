import io
import sys
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from daily_report_render import (
    REPORT_VARIANT_FULL,
    REPORT_VARIANT_SUMMARY,
    ReportCriticalDataMissingError,
    _render_report_with_display_mode,
    build_report_outputs,
    build_report_preflight,
    render_report_preflight_lines,
    generate_markdown_report,
    generate_markdown_report_from_sections,
)


class DailyReportRenderTest(unittest.TestCase):
    def test_build_report_outputs_suppresses_helper_diagnostics_for_summary_render(self):
        with patch("daily_report_render._render_report_with_display_mode", side_effect=["# full", "# summary"]) as render_mock:
            outputs = build_report_outputs({"foo": "bar"}, "2026-04-22", emit_preflight=False)

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
        self.assertTrue(render_mock.call_args_list[0].kwargs["persist_decision_ledger"])
        self.assertFalse(render_mock.call_args_list[1].kwargs["persist_decision_ledger"])
        self.assertTrue(render_mock.call_args_list[0].kwargs["decision_ledger_root_dir"].endswith("a-daily-report"))
        self.assertIs(render_mock.call_args_list[0].kwargs["shared_runtime_cache"], render_mock.call_args_list[1].kwargs["shared_runtime_cache"])

    def test_build_report_outputs_does_not_persist_decision_ledger_for_replay(self):
        with patch("daily_report_render._render_report_with_display_mode", side_effect=["# full", "# summary"]) as render_mock:
            build_report_outputs({"foo": "bar"}, "2026-04-22", run_mode="replay", emit_preflight=False)

        self.assertFalse(render_mock.call_args_list[0].kwargs["persist_decision_ledger"])
        self.assertFalse(render_mock.call_args_list[1].kwargs["persist_decision_ledger"])

    def test_render_report_with_display_mode_forwards_decision_ledger_config(self):
        fake_demo = types.ModuleType("daily_report_entry_demo")
        captured = {}

        def _fake_generate_markdown_report(*args, **kwargs):
            captured.update(kwargs)
            return "# report"

        fake_demo.DISPLAY_MVP_MODE = False
        fake_demo.EMIT_HELPER_DIAGNOSTICS = True
        fake_demo.REPORT_RUNTIME_CACHE = None
        fake_demo.generate_markdown_report = _fake_generate_markdown_report

        with patch.dict(sys.modules, {"daily_report_entry_demo": fake_demo}):
            rendered = _render_report_with_display_mode(
                False,
                {"foo": "bar"},
                "2026-05-14",
                persist_decision_ledger=True,
                decision_ledger_root_dir="/tmp/decision-ledger-root",
            )

        self.assertEqual(rendered, "# report")
        self.assertTrue(captured["persist_decision_ledger"])
        self.assertEqual(captured["decision_ledger_root_dir"], "/tmp/decision-ledger-root")

    def test_build_report_outputs_can_suppress_preflight_output(self):
        data = {
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "成交额排名": True,
            },
            "total_turnover": 12345.67,
            "wind_a_alternative": {"price": 6686.86, "data_source": "tushare.index_daily"},
            "turnover_rank": [{"code": "000001", "data_source": "tushare.daily"}],
            "module_logs": [
                {
                    "step": "request.total_turnover",
                    "status": "success",
                    "details": {"provider": "tushare.daily", "total_turnover": 12345.67},
                },
            ],
        }

        stdout = io.StringIO()
        with patch("daily_report_render._render_report_with_display_mode", side_effect=["# full", "# summary"]):
            with redirect_stdout(stdout):
                build_report_outputs(data, "2026-05-13", emit_preflight=False)

        self.assertEqual(stdout.getvalue(), "")

    def test_build_report_outputs_aborts_when_critical_data_failed(self):
        data = {
            "data_status": {
                "两市成交额": False,
                "中证全指": False,
                "成交额排名": False,
            },
            "step_status": {
                "两市成交额获取": False,
                "中证全指获取": False,
                "成交额排名获取": False,
            },
        }

        with patch("daily_report_render._render_report_with_display_mode") as render_mock:
            with self.assertRaises(ReportCriticalDataMissingError) as error:
                build_report_outputs(data, "2026-05-13", emit_preflight=False)

        render_mock.assert_not_called()
        message = str(error.exception)
        self.assertIn("日报生成已终止", message)
        self.assertIn("两市成交额", message)
        self.assertIn("中证全指", message)
        self.assertIn("成交额排名", message)

    def test_build_report_outputs_aborts_when_snapshot_envelope_contains_critical_failures(self):
        snapshot = {
            "date": "2026-05-13",
            "saved_at": "2026-05-13T18:12:15",
            "mode": "frozen",
            "data": {
                "total_turnover": 0.0,
                "wind_a_alternative": {"price": 0, "change_pct": 0},
                "turnover_rank": [],
                "data_status": {
                    "两市成交额": False,
                    "中证全指": False,
                    "成交额排名": False,
                },
            },
        }

        with patch("daily_report_render._render_report_with_display_mode") as render_mock:
            with self.assertRaises(ReportCriticalDataMissingError):
                build_report_outputs(snapshot, "2026-05-13", emit_preflight=False)

        render_mock.assert_not_called()

    def test_build_report_outputs_aborts_when_tracked_critical_payload_is_missing_without_status(self):
        data = {
            "data_status": {"主要指数": True},
            "total_turnover": 0.0,
            "wind_a_alternative": {"price": 6686.865},
            "turnover_rank": [{"code": "000001"}],
        }

        with patch("daily_report_render._render_report_with_display_mode") as render_mock:
            with self.assertRaises(ReportCriticalDataMissingError) as error:
                build_report_outputs(data, "2026-05-13", emit_preflight=False)

        render_mock.assert_not_called()
        self.assertIn("两市成交额", str(error.exception))

    def test_report_preflight_fails_when_critical_provider_is_not_tushare(self):
        data = {
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "成交额排名": True,
            },
            "total_turnover": 12345.67,
            "wind_a_alternative": {"price": 6686.86, "data_source": "akshare.stock_zh_index_daily_em"},
            "turnover_rank": [{"code": "000001", "data_source": "eastmoney.push2.clist"}],
            "module_logs": [
                {
                    "step": "request.total_turnover",
                    "status": "success",
                    "details": {"provider": "akshare.stock_zh_index_daily_em", "total_turnover": 12345.67},
                },
                {
                    "step": "request.wind_a",
                    "status": "success",
                    "details": {"provider": "akshare.stock_zh_index_daily_em", "price": 6686.86},
                },
                {
                    "step": "request.turnover_rank",
                    "status": "success",
                    "details": {"provider": "eastmoney.turnover_rank", "row_count": 50},
                },
            ],
        }

        preflight = build_report_preflight(data, "2026-05-13")

        self.assertEqual(preflight["status"], "failed")
        self.assertEqual(preflight["failures"], ["两市成交额", "中证全指", "成交额排名"])

    def test_build_report_outputs_emits_preflight_by_default_before_abort(self):
        data = {
            "data_status": {"两市成交额": False},
            "total_turnover": 0.0,
        }

        stdout = io.StringIO()
        with patch("daily_report_render._render_report_with_display_mode"):
            with redirect_stdout(stdout):
                with self.assertRaises(ReportCriticalDataMissingError):
                    build_report_outputs(data, "2026-05-13")

        output = stdout.getvalue()
        self.assertIn("日报关键数据 preflight: failed / 2026-05-13", output)
        self.assertIn("两市成交额: failed", output)

    def test_report_preflight_renders_critical_fields_with_provider_and_row_count(self):
        data = {
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "成交额排名": True,
            },
            "total_turnover": 12345.67,
            "wind_a_alternative": {"price": 6686.86, "change_pct": 1.2, "data_source": "tushare.index_daily"},
            "turnover_rank": [{"code": "000001", "data_source": "tushare.daily"} for _ in range(50)],
            "module_logs": [
                {
                    "step": "request.total_turnover",
                    "status": "success",
                    "details": {"provider": "tushare.daily", "total_turnover": 12345.67},
                },
                {
                    "step": "request.wind_a",
                    "status": "success",
                    "details": {"provider": "tushare.index_daily", "price": 6686.86},
                },
                {
                    "step": "request.turnover_rank",
                    "status": "success",
                    "details": {"provider": "tushare.daily", "row_count": 50},
                },
            ],
        }

        preflight = build_report_preflight(data, "2026-05-13")
        lines = render_report_preflight_lines(preflight)

        self.assertEqual(preflight["status"], "success")
        self.assertIn("日报关键数据 preflight: success", lines[0])
        self.assertTrue(any("两市成交额" in line and "tushare.daily" in line and "12345.67" in line for line in lines))
        self.assertTrue(any("中证全指" in line and "tushare.index_daily" in line and "6686.86" in line for line in lines))
        self.assertTrue(any("成交额排名" in line and "tushare.daily" in line and "50" in line for line in lines))

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
