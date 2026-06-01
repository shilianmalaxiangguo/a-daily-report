import io
import json
import os
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
    save_report_output,
    save_report_outputs,
)
from daily_report_snapshot_io import LEDGER_MODE_FROZEN, LEDGER_MODE_REPLAY
from report.decision_ledger import build_decision_ledger_snapshot, write_decision_ledger_artifacts


class DailyReportRenderTest(unittest.TestCase):
    def test_save_report_output_can_explicitly_overwrite_official_report(self):
        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            target_path = root / "2026-05-26_A股日报_完整版.md"
            target_path.write_text("# old", encoding="utf-8")

            saved_path = save_report_output(
                "# new",
                "2026-05-26",
                mode=LEDGER_MODE_FROZEN,
                variant=REPORT_VARIANT_FULL,
                output_path=str(target_path),
                overwrite_existing=True,
            )

            self.assertEqual(saved_path, str(target_path))
            self.assertEqual(target_path.read_text(encoding="utf-8"), "# new")

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
        self.assertTrue(render_mock.call_args_list[0].kwargs["persist_candidate_traces"])
        self.assertFalse(render_mock.call_args_list[1].kwargs["persist_candidate_traces"])
        self.assertEqual(
            Path(render_mock.call_args_list[0].kwargs["decision_ledger_root_dir"]).resolve(),
            ROOT.resolve(),
        )
        self.assertEqual(
            Path(render_mock.call_args_list[0].kwargs["candidate_trace_root_dir"]).resolve(),
            ROOT.resolve(),
        )
        self.assertIs(render_mock.call_args_list[0].kwargs["shared_runtime_cache"], render_mock.call_args_list[1].kwargs["shared_runtime_cache"])

    def test_build_report_outputs_forwards_postgres_only_runtime_config(self):
        with patch("daily_report_render._render_report_with_display_mode", side_effect=["# full", "# summary"]) as render_mock:
            build_report_outputs({"postgres_only": True}, "2026-05-29", emit_preflight=False)

        self.assertTrue(render_mock.call_args_list[0].kwargs["postgres_only"])
        self.assertTrue(render_mock.call_args_list[1].kwargs["postgres_only"])

    def test_build_report_outputs_persists_decision_ledger_before_replay_full_render(self):
        with patch("daily_report_render._render_report_with_display_mode", side_effect=["# full", "# summary"]) as render_mock:
            build_report_outputs({"foo": "bar"}, "2026-04-22", run_mode="replay", emit_preflight=False)

        self.assertTrue(render_mock.call_args_list[0].kwargs["persist_decision_ledger"])
        self.assertFalse(render_mock.call_args_list[1].kwargs["persist_decision_ledger"])
        self.assertTrue(render_mock.call_args_list[0].kwargs["persist_candidate_traces"])
        self.assertFalse(render_mock.call_args_list[1].kwargs["persist_candidate_traces"])

    def test_build_report_outputs_keeps_private_position_report_out_of_daily_reports(self):
        private_position_text = "\n## 持仓策略\n| 上峰水泥 | 100.0% | 私密动作 |\n"

        with patch("daily_report_render._render_report_with_display_mode", side_effect=["# full", "# summary"]):
            outputs = build_report_outputs(
                {"foo": "bar"},
                "2026-05-19",
                position_report_text=private_position_text,
                emit_preflight=False,
            )

        self.assertNotIn("持仓策略", outputs[REPORT_VARIANT_FULL])
        self.assertNotIn("上峰水泥", outputs[REPORT_VARIANT_FULL])
        self.assertNotIn("100.0%", outputs[REPORT_VARIANT_FULL])
        self.assertNotIn("持仓策略", outputs[REPORT_VARIANT_SUMMARY])
        self.assertNotIn("上峰水泥", outputs[REPORT_VARIANT_SUMMARY])
        self.assertNotIn("100.0%", outputs[REPORT_VARIANT_SUMMARY])

    def test_build_report_outputs_passes_structured_position_context_without_private_report_text(self):
        data = {
            "personal_position_context": {
                "account_profile": {"capital_text": "1w本金；总资产10126.52；当日盈利126.52（+1.27%）"},
                "existing_position_summary": {
                    "has_position": True,
                    "summary": "持有晶方科技(603005)1手，成本43.835；先处理旧仓",
                },
            }
        }

        with patch("daily_report_render._render_report_with_display_mode", side_effect=["# full", "# summary"]) as render_mock:
            outputs = build_report_outputs(
                data,
                "2026-05-26",
                has_personal_positions=True,
                position_report_text="\n## 持仓策略\n| 晶方科技 | 100.0% | 私密动作 |\n",
                emit_preflight=False,
            )

        self.assertNotIn("持仓策略", outputs[REPORT_VARIANT_FULL])
        self.assertEqual(render_mock.call_count, 2)
        self.assertTrue(render_mock.call_args_list[0].kwargs["has_personal_positions"])
        self.assertIn("personal_position_context", data)

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

    def test_save_replay_outputs_keeps_existing_decision_ledger_when_final_markdown_has_no_list(self):
        from storage.database_service import DatabaseService

        existing_snapshot = build_decision_ledger_snapshot(
            trade_date="2026-05-22",
            extreme_conviction_list=[
                {
                    "code": "000636",
                    "name": "风华高科",
                    "sector": "元器件",
                    "source_tier": "extreme_conviction",
                    "execution_eligibility": "observation_only",
                    "attack_state": "0%观察",
                    "conviction_reason": "形态健康，但最终0%只观察承接",
                }
            ],
            market_branch="空仓等待",
            sector_relationship_state="只观察",
        )

        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            write_decision_ledger_artifacts(existing_snapshot, root_dir=root)

            save_report_outputs(
                {
                    REPORT_VARIANT_FULL: "# 2026-05-22 A股市场分析\n\n正文没有候选表。",
                    REPORT_VARIANT_SUMMARY: "# summary",
                },
                "2026-05-22",
                mode=LEDGER_MODE_REPLAY,
                output_dir=str(root),
            )

            snapshot = json.loads((root / "data" / "decision-ledger" / "2026-05-22.json").read_text(encoding="utf-8"))
            service = DatabaseService.sqlite_d1_compatible(root / "data" / "cloudflare_free_daily.db")
            rows = service.query_extreme_conviction_mentions("2026-05-22", window_days=25)

        self.assertEqual([case["stock_code"] for case in snapshot["cases"]], ["000636"])
        self.assertEqual([row["stock_code"] for row in rows], ["000636"])

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
                persist_candidate_traces=True,
                candidate_trace_root_dir="/tmp/candidate-trace-root",
                postgres_only=True,
            )

        self.assertEqual(rendered, "# report")
        self.assertTrue(captured["persist_decision_ledger"])
        self.assertEqual(captured["decision_ledger_root_dir"], "/tmp/decision-ledger-root")
        self.assertTrue(captured["persist_candidate_traces"])
        self.assertEqual(captured["candidate_trace_root_dir"], "/tmp/candidate-trace-root")
        self.assertTrue(captured["postgres_only"])
        self.assertFalse(fake_demo._POSTGRES_ONLY_RUNTIME)

    def test_render_report_with_display_mode_sets_postgres_only_runtime_on_demo_module(self):
        fake_demo = types.ModuleType("daily_report_entry_demo")
        fake_demo.DISPLAY_MVP_MODE = False
        fake_demo.EMIT_HELPER_DIAGNOSTICS = True
        fake_demo.REPORT_RUNTIME_CACHE = None
        fake_demo._POSTGRES_ONLY_RUNTIME = False

        def _fake_generate_markdown_report(*args, **kwargs):
            self.assertTrue(fake_demo._POSTGRES_ONLY_RUNTIME)
            return "# report"

        fake_demo.generate_markdown_report = _fake_generate_markdown_report

        with patch.dict(sys.modules, {"daily_report_entry_demo": fake_demo}):
            rendered = _render_report_with_display_mode(
                False,
                {"postgres_only": True},
                "2026-05-29",
                postgres_only=True,
            )

        self.assertEqual(rendered, "# report")
        self.assertFalse(fake_demo._POSTGRES_ONLY_RUNTIME)

    def test_render_report_with_display_mode_sets_postgres_only_env_guard(self):
        fake_demo = types.ModuleType("daily_report_entry_demo")
        fake_demo.DISPLAY_MVP_MODE = False
        fake_demo.EMIT_HELPER_DIAGNOSTICS = True
        fake_demo.REPORT_RUNTIME_CACHE = None
        fake_demo._POSTGRES_ONLY_RUNTIME = False

        def _fake_generate_markdown_report(*args, **kwargs):
            self.assertEqual(os.environ.get("A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME"), "1")
            return "# report"

        fake_demo.generate_markdown_report = _fake_generate_markdown_report

        with patch.dict(sys.modules, {"daily_report_entry_demo": fake_demo}), \
             patch.dict(os.environ, {}, clear=True):
            rendered = _render_report_with_display_mode(
                False,
                {"postgres_only": True},
                "2026-05-29",
                postgres_only=True,
            )

        self.assertEqual(rendered, "# report")
        self.assertIsNone(os.environ.get("A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME"))

    def test_build_report_outputs_can_suppress_preflight_output(self):
        data = {
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "中证1000": True,
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
                "中证1000": True,
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

    def test_report_preflight_aborts_when_market_breadth_has_only_limit_counts(self):
        data = {
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "中证1000": True,
                "成交额排名": True,
                "大盘涨跌统计": True,
            },
            "step_status": {"涨停跌停数据获取": True},
            "total_turnover": 12345.67,
            "wind_a_alternative": {"price": 6686.86, "data_source": "tushare.index_daily"},
            "turnover_rank": [{"code": "000001", "data_source": "tushare.daily"}],
            "market_stats": {"up_count": 0, "down_count": 0, "zt_count": 102, "dt_count": 8},
            "module_logs": [
                {"step": "request.total_turnover", "status": "success", "details": {"provider": "tushare.daily"}},
                {"step": "request.wind_a", "status": "success", "details": {"provider": "tushare.index_daily"}},
                {"step": "request.turnover_rank", "status": "success", "details": {"provider": "tushare.daily"}},
                {
                    "step": "request.market_stats",
                    "status": "degraded",
                    "details": {"provider": "akshare.stock_market_activity_legu"},
                },
            ],
        }

        preflight = build_report_preflight(data, "2026-05-28")

        self.assertEqual(preflight["status"], "failed")
        self.assertIn("大盘涨跌统计", preflight["failures"])

    def test_report_preflight_aborts_when_hot_rank_sample_is_short(self):
        data = {
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "中证1000": True,
                "成交额排名": True,
                "热度前50个股": False,
            },
            "step_status": {"热度前50个股获取": False},
            "total_turnover": 12345.67,
            "wind_a_alternative": {"price": 6686.86, "data_source": "tushare.index_daily"},
            "turnover_rank": [{"code": "000001", "data_source": "tushare.daily"}],
            "hot_rank_top30": [{"code": f"000{idx:03d}"} for idx in range(1, 31)],
            "hot_rank_sample_size": 30,
            "hot_rank_sample_target": 50,
            "module_logs": [
                {"step": "request.total_turnover", "status": "success", "details": {"provider": "tushare.daily"}},
                {"step": "request.wind_a", "status": "success", "details": {"provider": "tushare.index_daily"}},
                {"step": "request.turnover_rank", "status": "success", "details": {"provider": "tushare.daily"}},
                {
                    "step": "request.hot_rank.primary",
                    "status": "degraded",
                    "details": {"provider": "tushare.ths_hot", "hot_rank_count": 30, "required_count": 50},
                },
            ],
        }

        preflight = build_report_preflight(data, "2026-05-28")

        self.assertEqual(preflight["status"], "failed")
        self.assertIn("热度前50个股", preflight["failures"])
        hot_rank_check = next(check for check in preflight["checks"] if check["label"] == "热度前50个股")
        self.assertEqual(hot_rank_check["value"], "30/50")
        self.assertEqual(hot_rank_check["row_count"], 30)

    def test_report_preflight_aborts_when_legacy_hot_rank_payload_has_only_top30(self):
        data = {
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "中证1000": True,
                "成交额排名": True,
            },
            "total_turnover": 12345.67,
            "wind_a_alternative": {"price": 6686.86, "data_source": "tushare.index_daily"},
            "turnover_rank": [{"code": "000001", "data_source": "tushare.daily"}],
            "hot_rank_top30": [{"code": f"000{idx:03d}"} for idx in range(1, 31)],
        }

        preflight = build_report_preflight(data, "2026-05-28")

        self.assertEqual(preflight["status"], "failed")
        self.assertIn("热度前50个股", preflight["failures"])

    def test_report_preflight_allows_empty_lianban_when_extraction_succeeded(self):
        data = {
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "中证1000": True,
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

    def test_report_preflight_accepts_xuangubao_plates_and_limit_up_reasons_when_newsflash_is_empty(self):
        data = {
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "中证1000": True,
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

        self.assertNotIn("选股通盘中异动", preflight["failures"])

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
                "中证1000": True,
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
                "中证1000": True,
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

    def test_report_preflight_fails_when_new_high_feedback_factor_missing(self):
        data = {
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "中证1000": True,
                "成交额排名": True,
                "创新高趋势反馈": False,
            },
            "step_status": {"创新高趋势反馈获取": False},
            "total_turnover": 12345.67,
            "wind_a_alternative": {"price": 6686.86, "data_source": "tushare.index_daily"},
            "turnover_rank": [{"code": "000001", "data_source": "tushare.daily"}],
            "new_high_feedback": {
                "available": False,
                "status": "upstream_empty",
                "source": "tushare.stk_factor_pro.topdays",
            },
            "module_logs": [
                {"step": "request.total_turnover", "status": "success", "details": {"provider": "tushare.daily"}},
                {"step": "request.wind_a", "status": "success", "details": {"provider": "tushare.index_daily"}},
                {"step": "request.turnover_rank", "status": "success", "details": {"provider": "tushare.daily"}},
                {
                    "step": "request.new_high_feedback",
                    "status": "degraded",
                    "details": {"provider": "tushare.stk_factor_pro.topdays", "new_high_count": 0},
                },
            ],
        }

        preflight = build_report_preflight(data, "2026-05-19")

        self.assertEqual(preflight["status"], "failed")
        self.assertIn("创新高趋势反馈", preflight["failures"])

    def test_report_preflight_echoes_new_high_recent_trend_rows(self):
        data = {
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "中证1000": True,
                "成交额排名": True,
                "创新高趋势反馈": True,
            },
            "step_status": {"创新高趋势反馈获取": True},
            "total_turnover": 12345.67,
            "wind_a_alternative": {"price": 6686.86, "data_source": "tushare.index_daily"},
            "turnover_rank": [{"code": "000001", "data_source": "tushare.daily"}],
            "new_high_feedback": {
                "available": True,
                "source": "tushare.stk_factor_pro.topdays",
                "new_high_count": 169,
                "trend_rows": [
                    {
                        "trade_date": "2026-05-18",
                        "new_high_count": 132,
                        "all_a_share_pct": 2.64,
                        "change_text": "+19",
                        "leading_sectors": "元器件、半导体、化工原料",
                    },
                    {
                        "trade_date": "2026-05-19",
                        "new_high_count": 164,
                        "all_a_share_pct": 3.28,
                        "change_text": "+32",
                        "leading_sectors": "半导体、元器件、专用机械",
                    },
                    {
                        "trade_date": "2026-05-20",
                        "new_high_count": 169,
                        "all_a_share_pct": 3.38,
                        "change_text": "+5",
                        "leading_sectors": "半导体、元器件、专用机械",
                    },
                ],
            },
            "module_logs": [
                {"step": "request.total_turnover", "status": "success", "details": {"provider": "tushare.daily"}},
                {"step": "request.wind_a", "status": "success", "details": {"provider": "tushare.index_daily"}},
                {"step": "request.turnover_rank", "status": "success", "details": {"provider": "tushare.daily"}},
                {
                    "step": "request.new_high_feedback",
                    "status": "success",
                    "details": {
                        "provider": "tushare.stk_factor_pro.topdays",
                        "new_high_count": 169,
                        "trend_row_count": 3,
                    },
                },
            ],
        }

        preflight = build_report_preflight(data, "2026-05-20")
        lines = render_report_preflight_lines(preflight)
        rendered = "\n".join(lines)

        self.assertIn("创新高趋势反馈: success", rendered)
        self.assertIn("row_count=3", rendered)
        self.assertIn("创新高近25个交易日:", rendered)
        self.assertIn("2026-05-18 132 2.64% +19 元器件、半导体、化工原料", rendered)
        self.assertIn("2026-05-20 169 3.38% +5 半导体、元器件、专用机械", rendered)

    def test_report_preflight_fails_when_top50_turnover_share_trend_missing(self):
        data = {
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "中证1000": True,
                "成交额排名": True,
                "Top50成交额占比趋势": False,
            },
            "step_status": {"Top50成交额占比趋势获取": False},
            "total_turnover": 12345.67,
            "wind_a_alternative": {"price": 6686.86, "data_source": "tushare.index_daily"},
            "turnover_rank": [{"code": "000001", "data_source": "tushare.daily"}],
            "top50_turnover_share_series": {"rows": []},
            "module_logs": [
                {"step": "request.total_turnover", "status": "success", "details": {"provider": "tushare.daily"}},
                {"step": "request.wind_a", "status": "success", "details": {"provider": "tushare.index_daily"}},
                {"step": "request.turnover_rank", "status": "success", "details": {"provider": "tushare.daily"}},
                {
                    "step": "request.top50_turnover_share_series",
                    "status": "degraded",
                    "details": {"provider": "storage.turnover_rank_daily", "row_count": 0},
                },
            ],
        }

        preflight = build_report_preflight(data, "2026-05-19")

        self.assertEqual(preflight["status"], "failed")
        self.assertIn("Top50成交额占比趋势", preflight["failures"])

    def test_report_preflight_fails_when_margin_pressure_missing(self):
        data = {
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "中证1000": True,
                "成交额排名": True,
                "融资承接压力": False,
            },
            "step_status": {"融资承接压力获取": False},
            "total_turnover": 12345.67,
            "wind_a_alternative": {"price": 6686.86, "data_source": "tushare.index_daily"},
            "turnover_rank": [{"code": "000001", "data_source": "tushare.daily"}],
            "margin_pressure": {"available": False, "rows": []},
            "module_logs": [
                {"step": "request.total_turnover", "status": "success", "details": {"provider": "tushare.daily"}},
                {"step": "request.wind_a", "status": "success", "details": {"provider": "tushare.index_daily"}},
                {"step": "request.turnover_rank", "status": "success", "details": {"provider": "tushare.daily"}},
                {
                    "step": "request.margin_pressure",
                    "status": "degraded",
                    "details": {"provider": "tushare.margin+tushare.index_daily.market_amount", "row_count": 0},
                },
            ],
        }

        preflight = build_report_preflight(data, "2026-05-22")

        self.assertEqual(preflight["status"], "failed")
        self.assertIn("融资承接压力", preflight["failures"])

    def test_report_preflight_fails_when_etf_turnover_series_missing(self):
        data = {
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "中证1000": True,
                "成交额排名": True,
                "ETF两市成交额趋势": False,
            },
            "step_status": {"ETF两市成交额趋势获取": False},
            "total_turnover": 12345.67,
            "wind_a_alternative": {"price": 6686.86, "data_source": "tushare.index_daily"},
            "turnover_rank": [{"code": "000001", "data_source": "tushare.daily"}],
            "etf_turnover_series": {"available": False, "rows": []},
            "module_logs": [
                {"step": "request.total_turnover", "status": "success", "details": {"provider": "tushare.daily"}},
                {"step": "request.wind_a", "status": "success", "details": {"provider": "tushare.index_daily"}},
                {"step": "request.turnover_rank", "status": "success", "details": {"provider": "tushare.daily"}},
                {
                    "step": "request.etf_turnover_series",
                    "status": "degraded",
                    "details": {"provider": "sina.etf.daily_amount", "row_count": 0},
                },
            ],
        }

        preflight = build_report_preflight(data, "2026-05-22")

        self.assertEqual(preflight["status"], "failed")
        self.assertIn("ETF两市成交额趋势", preflight["failures"])

    def test_report_preflight_fails_when_lhb_factor_missing(self):
        data = {
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "中证1000": True,
                "成交额排名": True,
            },
            "step_status": {"龙虎榜数据获取": False},
            "total_turnover": 12345.67,
            "wind_a_alternative": {"price": 6686.86, "data_source": "tushare.index_daily"},
            "turnover_rank": [{"code": "000001", "data_source": "tushare.daily"}],
            "lhb_data_status": "upstream_empty",
            "lhb_analysis": [],
            "module_logs": [
                {"step": "request.total_turnover", "status": "success", "details": {"provider": "tushare.daily"}},
                {"step": "request.wind_a", "status": "success", "details": {"provider": "tushare.index_daily"}},
                {"step": "request.turnover_rank", "status": "success", "details": {"provider": "tushare.daily"}},
                {
                    "step": "request.lhb_snapshot",
                    "status": "degraded",
                    "details": {"provider": "legacy.lhb_snapshot", "lhb_count": 0},
                },
            ],
        }

        preflight = build_report_preflight(data, "2026-05-19")

        self.assertEqual(preflight["status"], "failed")
        self.assertIn("龙虎榜数据", preflight["failures"])

    def test_report_preflight_fails_when_concept_fund_flow_missing(self):
        data = {
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "中证1000": True,
                "成交额排名": True,
                "概念资金流向": False,
            },
            "step_status": {"概念资金流向获取": False},
            "total_turnover": 12345.67,
            "wind_a_alternative": {"price": 6686.86, "data_source": "tushare.index_daily"},
            "turnover_rank": [{"code": "000001", "data_source": "tushare.daily"}],
            "concept_fund_flow": {"rows": [], "inflow": [], "outflow": []},
            "module_logs": [
                {"step": "request.total_turnover", "status": "success", "details": {"provider": "tushare.daily"}},
                {"step": "request.wind_a", "status": "success", "details": {"provider": "tushare.index_daily"}},
                {"step": "request.turnover_rank", "status": "success", "details": {"provider": "tushare.daily"}},
                {
                    "step": "request.concept_fund_flow",
                    "status": "degraded",
                    "details": {"provider": "tushare.ths_member+tushare.moneyflow", "row_count": 0},
                },
            ],
        }

        preflight = build_report_preflight(data, "2026-05-21")

        self.assertEqual(preflight["status"], "failed")
        self.assertIn("概念资金流向", preflight["failures"])

    def test_report_preflight_fails_when_xueqiu_hot_rank_factor_missing(self):
        data = {
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "中证1000": True,
                "成交额排名": True,
                "雪球A股24小时热榜": False,
            },
            "step_status": {"雪球A股24小时热榜获取": False},
            "total_turnover": 12345.67,
            "wind_a_alternative": {"price": 6686.86, "data_source": "tushare.index_daily"},
            "turnover_rank": [{"code": "000001", "data_source": "tushare.daily"}],
            "xueqiu_hot_rank_top100": [],
            "module_logs": [
                {"step": "request.total_turnover", "status": "success", "details": {"provider": "tushare.daily"}},
                {"step": "request.wind_a", "status": "success", "details": {"provider": "tushare.index_daily"}},
                {"step": "request.turnover_rank", "status": "success", "details": {"provider": "tushare.daily"}},
                {
                    "step": "request.xueqiu_hot_rank",
                    "status": "error",
                    "details": {
                        "provider": "xueqiu.hot_stock.type22",
                        "row_count": 0,
                        "error": "雪球登录态失效或缺失，关键数据不完整，停止生成",
                    },
                },
            ],
        }

        preflight = build_report_preflight(data, "2026-05-22")

        self.assertEqual(preflight["status"], "failed")
        self.assertIn("雪球A股24小时热榜", preflight["failures"])

    def test_report_preflight_fails_when_xueqiu_ai_argument_factor_missing(self):
        data = {
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "中证1000": True,
                "成交额排名": True,
                "雪球热榜AI解释": False,
            },
            "step_status": {"雪球热榜AI解释获取": False},
            "total_turnover": 12345.67,
            "wind_a_alternative": {"price": 6686.86, "data_source": "tushare.index_daily"},
            "turnover_rank": [{"code": "000001", "data_source": "tushare.daily"}],
            "xueqiu_hot_stock_arguments": [],
            "module_logs": [
                {"step": "request.total_turnover", "status": "success", "details": {"provider": "tushare.daily"}},
                {"step": "request.wind_a", "status": "success", "details": {"provider": "tushare.index_daily"}},
                {"step": "request.turnover_rank", "status": "success", "details": {"provider": "tushare.daily"}},
                {
                    "step": "request.xueqiu_hot_stock_arguments",
                    "status": "error",
                    "details": {
                        "provider": "xueqiu.hot_stock.argument",
                        "row_count": 0,
                        "error": "雪球接口返回空，关键数据不完整，停止生成",
                    },
                },
            ],
        }

        preflight = build_report_preflight(data, "2026-05-22")

        self.assertEqual(preflight["status"], "failed")
        self.assertIn("雪球热榜AI解释", preflight["failures"])

    def test_report_preflight_fails_when_any_registered_factor_status_failed(self):
        data = {
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "中证1000": True,
                "成交额排名": True,
                "价格带风格趋势": False,
            },
            "step_status": {"价格带风格趋势获取": False},
            "total_turnover": 12345.67,
            "wind_a_alternative": {"price": 6686.86, "data_source": "tushare.index_daily"},
            "turnover_rank": [{"code": "000001", "data_source": "tushare.daily"}],
            "price_band_style_series": {"rows": []},
            "module_logs": [
                {"step": "request.total_turnover", "status": "success", "details": {"provider": "tushare.daily"}},
                {"step": "request.wind_a", "status": "success", "details": {"provider": "tushare.index_daily"}},
                {"step": "request.turnover_rank", "status": "success", "details": {"provider": "tushare.daily"}},
                {
                    "step": "request.price_band_style_series",
                    "status": "degraded",
                    "details": {"provider": "tushare.ths_daily.price_band_style", "row_count": 0},
                },
            ],
        }

        preflight = build_report_preflight(data, "2026-05-22")

        self.assertEqual(preflight["status"], "failed")
        self.assertIn("价格带风格趋势", preflight["failures"])

    def test_report_preflight_accepts_lhb_rank_rows_when_analysis_table_is_empty(self):
        data = {
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "中证1000": True,
                "成交额排名": True,
            },
            "step_status": {"龙虎榜数据获取": True},
            "total_turnover": 12345.67,
            "wind_a_alternative": {"price": 6686.86, "data_source": "tushare.index_daily"},
            "turnover_rank": [{"code": "000001", "data_source": "tushare.daily"}],
            "lhb_analysis": [],
            "lhb_net_buy_top10": [{"code": "000001", "name": "军工一号"}],
            "lhb_net_sell_top10": [],
            "module_logs": [
                {"step": "request.total_turnover", "status": "success", "details": {"provider": "tushare.daily"}},
                {"step": "request.wind_a", "status": "success", "details": {"provider": "tushare.index_daily"}},
                {"step": "request.turnover_rank", "status": "success", "details": {"provider": "tushare.daily"}},
                {
                    "step": "request.lhb_snapshot",
                    "status": "success",
                    "details": {"provider": "tushare.top_list", "lhb_count": 0, "buy_count": 1},
                },
            ],
        }

        preflight = build_report_preflight(data, "2026-05-19")

        self.assertNotIn("龙虎榜数据", preflight["failures"])

    def test_report_preflight_fails_when_resonance_factor_not_computed(self):
        data = {
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "中证1000": True,
                "成交额排名": True,
            },
            "total_turnover": 12345.67,
            "wind_a_alternative": {"price": 6686.86, "data_source": "tushare.index_daily"},
            "turnover_rank": [{"code": "000001", "data_source": "tushare.daily"}],
            "zt_pool": [{"code": "000001"}],
            "sector_fund_flow": {"inflow": [{"name": "机器人"}]},
            "stocks_with_history": [{"code": "000001", "turnover": 80.0}],
            "resonance_scores": {},
            "trade_signals": [],
            "module_logs": [
                {"step": "request.total_turnover", "status": "success", "details": {"provider": "tushare.daily"}},
                {"step": "request.wind_a", "status": "success", "details": {"provider": "tushare.index_daily"}},
                {"step": "request.turnover_rank", "status": "success", "details": {"provider": "tushare.daily"}},
                {
                    "step": "infer.quant_signals",
                    "status": "success",
                    "details": {"volume_anomaly_count": 2, "lhb_count": 0, "resonance_count": 0, "signal_count": 0},
                },
            ],
        }

        preflight = build_report_preflight(data, "2026-05-19")

        self.assertEqual(preflight["status"], "failed")
        self.assertIn("板块共振结果", preflight["failures"])

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
                "中证1000": True,
                "成交额排名": True,
            },
            "total_turnover": 12345.67,
            "wind_a_alternative": {"price": 6686.86, "change_pct": 1.2, "data_source": "tushare.index_daily"},
            "csi1000_index": {"price": 6123.45, "change_pct": 1.1, "data_source": "tushare.index_daily"},
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
                    "step": "request.csi1000",
                    "status": "success",
                    "details": {"provider": "tushare.index_daily", "price": 6123.45},
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
        self.assertTrue(any("中证1000" in line and "tushare.index_daily" in line and "6123.45" in line for line in lines))
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

    def test_decision_preflight_accepts_postgres_xuangubao_summary_counts(self):
        data = {
            "data_status": {"选股通盘中异动": True},
            "step_status": {"选股通盘中异动获取": True},
            "postgres_only": True,
            "xuangubao_data": {
                "news_count": 0,
                "plate_count": 1,
                "limit_up_reason_count": 0,
                "diagnostics_status": "success",
            },
        }

        preflight = build_report_preflight(data, "2026-05-29")

        xgb_check = next(check for check in preflight["decision_checks"] if check["label"] == "选股通盘中异动")
        self.assertEqual(xgb_check["status"], "success")
        self.assertEqual(xgb_check["row_count"], 1)
        self.assertNotIn("选股通盘中异动", preflight["failures"])

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

    def test_generate_markdown_report_forwards_candidate_trace_config(self):
        fake_demo = types.ModuleType("daily_report_entry_demo")
        captured = {}

        def _fake_generate_markdown_report(*args, **kwargs):
            captured.update(kwargs)
            return "legacy report"

        fake_demo.generate_markdown_report = _fake_generate_markdown_report

        with patch.dict(sys.modules, {"daily_report_entry_demo": fake_demo}):
            rendered = generate_markdown_report(
                {"foo": "bar"},
                "2026-04-21",
                persist_candidate_traces=True,
                candidate_trace_root_dir="/tmp/candidate-trace-root",
            )

        self.assertEqual(rendered, "legacy report")
        self.assertTrue(captured["persist_candidate_traces"])
        self.assertEqual(captured["candidate_trace_root_dir"], "/tmp/candidate-trace-root")

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
