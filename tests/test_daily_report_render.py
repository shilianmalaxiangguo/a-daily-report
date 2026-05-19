import io
import json
import sys
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
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
    save_report_outputs,
)
from daily_report_snapshot_io import LEDGER_MODE_REPLAY
from report.decision_ledger import build_decision_ledger_snapshot, write_decision_ledger_artifacts


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

    def test_save_replay_outputs_rebuilds_decision_ledger_from_final_full_markdown(self):
        stale_snapshot = build_decision_ledger_snapshot(
            trade_date="2026-05-18",
            extreme_conviction_list=[
                {"code": "600850", "name": "电科数字", "sector": "数据中心", "conviction_reason": "旧名单"},
                {"code": "603082", "name": "北自科技", "sector": "机器人", "conviction_reason": "旧名单"},
            ],
            market_branch="旧结果",
            sector_relationship_state="旧结果",
        )
        fresh_report = """
**极度看好名单**（只保留最心动的少数，每只都绑定参与窗口）:
| 优先级 | 股票 | 代码 | 所属板块 | 核心身份 | 极看理由 | 明日原则 |
|--------|------|------|----------|----------|----------|----------|
| 1 | 合百集团 | 000417 | 股权转让 | 板块锚定龙 | 板块锚定龙 | 只盯分歧后的转强 |
| 2 | 弘信电子 | 300657 | 算力 | 弹性核心 | 主线共振 | 只盯主动转强 |
| 3 | 利仁科技 | 001259 | 家电 | 高辨识度首板 | 资金承接强 | 不追一致高潮 |
"""

        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            write_decision_ledger_artifacts(stale_snapshot, root_dir=root)

            save_report_outputs(
                {REPORT_VARIANT_FULL: fresh_report, REPORT_VARIANT_SUMMARY: "# summary"},
                "2026-05-18",
                mode=LEDGER_MODE_REPLAY,
                output_dir=str(root),
            )

            snapshot = json.loads((root / "data" / "decision-ledger" / "2026-05-18.json").read_text(encoding="utf-8"))
            index = json.loads((root / "data" / "decision-ledger" / "index.json").read_text(encoding="utf-8"))

        self.assertEqual([case["stock_code"] for case in snapshot["cases"]], ["000417", "300657", "001259"])
        same_day_rows = {
            row["stock_code"]
            for row in index["extreme_conviction_backtest_rows"]
            if row["mention_trade_date"] == "2026-05-18"
        }
        self.assertEqual(same_day_rows, {"000417", "300657", "001259"})
        self.assertNotIn("600850", index["by_stock_code"])
        self.assertNotIn("603082", index["by_stock_code"])

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

    def test_build_report_outputs_aborts_when_decision_source_failed(self):
        data = {
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "成交额排名": True,
                "整合热榜": False,
            },
            "step_status": {"整合热榜获取": False},
            "total_turnover": 12345.67,
            "wind_a_alternative": {"price": 6686.86, "data_source": "tushare.index_daily"},
            "turnover_rank": [{"code": "000001", "data_source": "tushare.daily"}],
            "integrated_hot_list": [],
            "module_logs": [
                {"step": "request.total_turnover", "status": "success", "details": {"provider": "tushare.daily"}},
                {"step": "request.wind_a", "status": "success", "details": {"provider": "tushare.index_daily"}},
                {"step": "request.turnover_rank", "status": "success", "details": {"provider": "tushare.daily"}},
                {
                    "step": "request.integrated_hot_rank",
                    "status": "error",
                    "details": {"provider": "hot_list_integrated.get_integrated_hot_list", "error": "boom"},
                },
            ],
        }

        with patch("daily_report_render._render_report_with_display_mode") as render_mock:
            with self.assertRaises(ReportCriticalDataMissingError) as error:
                build_report_outputs(data, "2026-05-13", emit_preflight=False)

        render_mock.assert_not_called()
        self.assertIn("整合热榜", str(error.exception))

    def test_report_preflight_allows_empty_lianban_when_extraction_succeeded(self):
        data = {
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "成交额排名": True,
            },
            "step_status": {"连板梯队提取": True},
            "total_turnover": 12345.67,
            "wind_a_alternative": {"price": 6686.86, "data_source": "tushare.index_daily"},
            "turnover_rank": [{"code": "000001", "data_source": "tushare.daily"}],
            "lianban_data": [],
            "module_logs": [
                {"step": "request.total_turnover", "status": "success", "details": {"provider": "tushare.daily"}},
                {"step": "request.wind_a", "status": "success", "details": {"provider": "tushare.index_daily"}},
                {"step": "request.turnover_rank", "status": "success", "details": {"provider": "tushare.daily"}},
                {"step": "request.lianban_snapshot", "status": "success", "details": {"provider": "tushare.limit_list_ths", "lianban_count": 0}},
            ],
        }

        preflight = build_report_preflight(data, "2026-05-13")

        self.assertNotIn("连板梯队", preflight["failures"])

    def test_report_preflight_fails_when_xuangubao_newsflash_is_empty_even_with_other_payloads(self):
        data = {
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "成交额排名": True,
                "整合热榜": True,
                "预期日历": True,
                "选股通盘中异动": True,
                "顽主杯热门前十": True,
            },
            "step_status": {
                "整合热榜获取": True,
                "预期日历获取": True,
                "选股通盘中异动获取": True,
                "顽主杯热门前十获取": True,
            },
            "total_turnover": 12345.67,
            "wind_a_alternative": {"price": 6686.86, "data_source": "tushare.index_daily"},
            "turnover_rank": [{"code": "000001", "data_source": "tushare.daily"}],
            "integrated_hot_list": [{"code": "000001"}],
            "calendar_events": [{"title": "产业大会"}],
            "wanzhu_top10": [{"code": "000001"}],
            "xuangubao_data": {
                "xuangubao_news": [],
                "xuangubao_plates": [{"name": "国产芯片"}],
                "xuangubao_limit_up_reasons": [{"symbol": "600676.SS"}],
                "diagnostics": {"newsflash": "missing XUANGUBAO_IVANKA_TOKEN"},
            },
            "module_logs": [
                {"step": "request.total_turnover", "status": "success", "details": {"provider": "tushare.daily"}},
                {"step": "request.wind_a", "status": "success", "details": {"provider": "tushare.index_daily"}},
                {"step": "request.turnover_rank", "status": "success", "details": {"provider": "tushare.daily"}},
                {"step": "request.integrated_hot_rank", "status": "success", "details": {"provider": "primary_hot_rank.fallback", "integrated_count": 1}},
                {"step": "request.calendar_events", "status": "success", "details": {"provider": "tencent.get_calendar_events", "calendar_count": 1}},
                {
                    "step": "request.xuangubao",
                    "status": "success",
                    "details": {
                        "provider": "xuangubao.fetch_xuangubao_data",
                        "news_count": 0,
                        "plate_count": 1,
                        "limit_up_reason_count": 1,
                        "diagnostic_note": "newsflash=missing XUANGUBAO_IVANKA_TOKEN",
                    },
                },
                {"step": "request.wanzhu_top10", "status": "success", "details": {"provider": "AShareDataCollector.get_wanzhu_top10", "stock_count": 1}},
            ],
        }

        preflight = build_report_preflight(data, "2026-05-18")

        self.assertIn("选股通盘中异动", preflight["failures"])

    def test_report_preflight_ignores_stale_xuangubao_failure_log_when_payload_has_news(self):
        data = {
            "data_status": {"选股通盘中异动": True},
            "step_status": {"选股通盘中异动获取": True},
            "xuangubao_data": {
                "xuangubao_news": [{"title": "机器人概念股午后拉升"}],
                "xuangubao_plates": [{"name": "机器人"}],
                "xuangubao_limit_up_reasons": [{"symbol": "603082.SS"}],
            },
            "module_logs": [
                {
                    "step": "request.xuangubao",
                    "status": "failed",
                    "details": {
                        "provider": "xuangubao.fetch_xuangubao_data",
                        "news_count": 0,
                        "plate_count": 23,
                        "limit_up_reason_count": 101,
                    },
                }
            ],
        }

        preflight = build_report_preflight(data, "2026-05-18")

        self.assertNotIn("选股通盘中异动", preflight["failures"])

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

    def test_report_preflight_fails_when_index_or_turnover_rank_provider_is_not_tushare(self):
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
        self.assertEqual(preflight["failures"], ["中证全指", "成交额排名"])

    def test_report_preflight_accepts_positive_total_turnover_from_legacy_provider(self):
        data = {
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "成交额排名": True,
            },
            "total_turnover": 29170.74,
            "wind_a_alternative": {"price": 6477.21, "data_source": "tushare.index_daily"},
            "turnover_rank": [{"code": "000001", "data_source": "tushare.daily"}],
            "module_logs": [
                {
                    "step": "request.total_turnover",
                    "status": "success",
                    "details": {"provider": "legacy.total_turnover", "total_turnover": 29170.74, "row_count": 0},
                },
                {
                    "step": "request.wind_a",
                    "status": "success",
                    "details": {"provider": "tushare.index_daily", "price": 6477.21},
                },
                {
                    "step": "request.turnover_rank",
                    "status": "success",
                    "details": {"provider": "tushare.daily", "row_count": 50},
                },
            ],
        }

        preflight = build_report_preflight(data, "2026-05-18")

        self.assertEqual(preflight["status"], "success")
        self.assertEqual(preflight["failures"], [])

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

    def test_decision_preflight_counts_xuangubao_plates_when_news_count_is_zero(self):
        data = {
            "data_status": {"选股通盘中异动": True},
            "step_status": {"选股通盘中异动获取": True},
            "xuangubao_data": {
                "xuangubao_news": [],
                "xuangubao_plates": [{"name": "国产芯片"}, {"name": "光通信"}],
            },
            "module_logs": [
                {
                    "step": "request.xuangubao",
                    "status": "success",
                    "details": {"provider": "xuangubao.fetch_xuangubao_data", "news_count": 0, "plate_count": 2},
                }
            ],
        }

        preflight = build_report_preflight(data, "2026-05-18")

        xgb_check = next(check for check in preflight["decision_checks"] if check["label"] == "选股通盘中异动")
        self.assertEqual(xgb_check["row_count"], 2)

    def test_decision_preflight_counts_xuangubao_limit_up_reasons(self):
        data = {
            "data_status": {"选股通盘中异动": True},
            "step_status": {"选股通盘中异动获取": True},
            "xuangubao_data": {
                "xuangubao_news": [],
                "xuangubao_plates": [],
                "xuangubao_limit_up_reasons": [{"name": "交运股份"}],
            },
            "module_logs": [
                {
                    "step": "request.xuangubao",
                    "status": "success",
                    "details": {
                        "provider": "xuangubao.fetch_xuangubao_data",
                        "news_count": 0,
                        "plate_count": 0,
                        "limit_up_reason_count": 1,
                    },
                }
            ],
        }

        preflight = build_report_preflight(data, "2026-05-18")

        xgb_check = next(check for check in preflight["decision_checks"] if check["label"] == "选股通盘中异动")
        self.assertEqual(xgb_check["row_count"], 1)

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
