import html as html_lib
import json
import re
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import daily_report_entry_demo


def _embedded_json_payload(rendered_html, script_id):
    match = re.search(
        rf'<script type="application/json" id="{script_id}">(.*?)</script>',
        rendered_html,
        re.S,
    )
    if not match:
        return {}
    return json.loads(html_lib.unescape(match.group(1)))


class DailyReportEntryHtmlOutputTest(unittest.TestCase):
    def test_position_timeline_is_inserted_after_heading_and_reading_map(self):
        markdown = "# 2026-07-02 a股市场分析\n\n## 阅读地图\n| 顺序 | 模块 | 用途 |\n|---:|---|---|\n| 1 | 日报裁决总览 | 先看动作 |\n\n## 日报裁决总览\n正文\n"
        timeline = "| 轨道 | 标的 | 2026-07-02 |\n|------|------|------|\n| Ta旧仓 | 太极实业(600667) | 旧路径复核 |"

        updated = daily_report_entry_demo._prepend_position_timeline_markdown(markdown, timeline)
        updated_again = daily_report_entry_demo._prepend_position_timeline_markdown(updated, timeline)

        self.assertTrue(updated.startswith("# 2026-07-02 a股市场分析\n"))
        self.assertEqual(updated.count("## 账户日序表"), 1)
        self.assertEqual(updated_again, updated)
        self.assertLess(updated.index("## 阅读地图"), updated.index("## 账户日序表"))
        self.assertLess(updated.index("## 账户日序表"), updated.index("## 日报裁决总览"))

    def _valid_data(self):
        return {
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "中证1000": True,
                "成交额排名": True,
                "大盘涨跌统计": True,
                "热度前50个股": True,
            },
            "total_turnover": 1000,
            "wind_a_alternative": {"price": 5000, "data_source": "tushare.index_daily"},
            "csi1000_index": {"price": 8408.73, "data_source": "tushare.index_daily"},
            "turnover_rank": [{"code": "000001", "data_source": "tushare.daily"}],
            "market_stats": {"up_count": 2600, "down_count": 2100},
            "hot_rank_top50": [{"code": f"{index:06d}"} for index in range(50)],
            "hot_rank_sample_size": 50,
            "hot_rank_sample_target": 50,
            "top50_turnover_share_pct": 19.0,
            "top50_turnover_share_series": {
                "rows": [
                    {
                        "trade_date": "2026-06-05",
                        "total_turnover": 1000,
                        "share_pct": 19.0,
                        "up_count": 2600,
                        "down_count": 2100,
                    }
                ]
            },
            "mainline_context": {
                "confirmed_line": "电力",
                "attack_evidence": ["净流入居前"],
                "mainline_turnover_summary": {
                    "turnover_share_trend_rows": [
                        {"trade_date": "2026-06-05", "mainline": "电力", "turnover_share_pct": 18.2}
                    ]
                },
            },
            "market_research_snapshot": {
                "front_page_final_gate": {
                    "final_action": "0%不参与",
                    "can_new_entry": False,
                }
            },
            "elimination_tournament_payload": {
                "schema_version": "elimination_tournament.v1",
                "trade_date": "2026-06-05",
                "variant": "frozen",
                "final_action": {
                    "label": "0%不参与",
                    "position_pct": 0,
                    "target": {},
                    "source": "selection_workflow.final",
                    "reason": "无明日执行对象，保持观察",
                },
                "layers": [],
            },
        }

    def _report_outputs(self):
        return {
            daily_report_entry_demo.REPORT_VARIANT_FULL: "# full\n| 明日执行风格 | 0%不参与 |",
            daily_report_entry_demo.REPORT_VARIANT_SUMMARY: "# summary",
        }

    def test_postgres_only_saves_bear_html_after_postgres_fact_sync(self):
        order = []

        def save_outputs(*args, **kwargs):
            order.append("markdown")
            return {daily_report_entry_demo.REPORT_VARIANT_FULL: "/tmp/full.md"}

        def save_chanlun(*args, **kwargs):
            order.append("chanlun")
            return Path("/tmp/chanlun.html")

        def sync_postgres(*args, **kwargs):
            order.append("sync")
            return {"source": "postgresql://daily-report-facts/2026-06-05", "field_count": 8}

        def persist_runtime_artifacts(*args, **kwargs):
            order.append("runtime_artifacts")
            return {"decision_ledger_artifacts": {}, "candidate_trace_artifact": None}

        def save_html(*args, **kwargs):
            order.append("html")
            return Path("/tmp/2026-06-05_A股日报_完整版.html")

        with patch.object(sys, "argv", ["daily_report_entry_demo.py", "2026-06-05", "--postgres-only"]), \
             patch.object(daily_report_entry_demo, "load_daily_report_data_from_postgres", return_value=self._valid_data()), \
             patch.object(daily_report_entry_demo, "build_report_preflight", return_value={"failures": []}), \
             patch.object(daily_report_entry_demo, "render_report_preflight_lines", return_value=[]), \
             patch.object(daily_report_entry_demo, "load_strategy_performance_ledger", return_value={"records": []}), \
             patch.object(daily_report_entry_demo.os.path, "exists", return_value=False), \
             patch.object(daily_report_entry_demo, "build_report_outputs", return_value=self._report_outputs()), \
             patch.object(daily_report_entry_demo, "persist_report_runtime_artifacts", side_effect=persist_runtime_artifacts) as persist_mock, \
             patch.object(daily_report_entry_demo, "_build_sh_index_chanlun_html_for_audit", return_value="<h2>明日抉择</h2>"), \
             patch.object(daily_report_entry_demo, "save_report_outputs", side_effect=save_outputs), \
             patch.object(daily_report_entry_demo, "save_sh_index_chanlun_html_report", side_effect=save_chanlun), \
             patch.object(daily_report_entry_demo, "audit_report_markdown", return_value={"passed": True, "findings": []}), \
             patch.object(daily_report_entry_demo, "import_daily_report_data_to_postgres", side_effect=sync_postgres), \
             patch.object(daily_report_entry_demo, "_try_save_daily_report_html_from_saved_markdown", side_effect=save_html) as html_mock:
            daily_report_entry_demo.main()

        self.assertEqual(order, ["sync", "runtime_artifacts", "markdown", "chanlun", "html"])
        self.assertEqual(html_mock.call_count, 1)
        self.assertEqual(html_mock.call_args.args[0], "2026-06-05")
        self.assertEqual(html_mock.call_args.kwargs["run_mode"], daily_report_entry_demo.LEDGER_MODE_FROZEN)
        self.assertEqual(
            html_mock.call_args.kwargs["saved_report_paths"],
            {daily_report_entry_demo.REPORT_VARIANT_FULL: "/tmp/full.md"},
        )

    def test_main_entry_uses_markdown_reader_html_not_structured_dashboard_html(self):
        data = self._valid_data()

        with patch.object(sys, "argv", ["daily_report_entry_demo.py", "2026-06-10", "--postgres-only"]), \
             patch.object(daily_report_entry_demo, "load_daily_report_data_from_postgres", return_value=data), \
             patch.object(daily_report_entry_demo, "build_report_preflight", return_value={"failures": []}), \
             patch.object(daily_report_entry_demo, "render_report_preflight_lines", return_value=[]), \
             patch.object(daily_report_entry_demo, "load_strategy_performance_ledger", return_value={"records": []}), \
             patch.object(daily_report_entry_demo.os.path, "exists", return_value=False), \
             patch.object(daily_report_entry_demo, "build_report_outputs", return_value=self._report_outputs()), \
             patch.object(daily_report_entry_demo, "persist_report_runtime_artifacts", return_value={}), \
             patch.object(daily_report_entry_demo, "_build_sh_index_chanlun_html_for_audit", return_value="<h2>明日抉择</h2>"), \
             patch.object(daily_report_entry_demo, "save_report_outputs", return_value={daily_report_entry_demo.REPORT_VARIANT_FULL: "/tmp/full.md"}), \
             patch.object(daily_report_entry_demo, "save_sh_index_chanlun_html_report", return_value=Path("/tmp/chanlun.html")), \
             patch.object(daily_report_entry_demo, "audit_report_markdown", return_value={"passed": True, "findings": []}), \
             patch.object(daily_report_entry_demo, "import_daily_report_data_to_postgres", return_value={"source": "postgresql://daily-report-facts/2026-06-10", "field_count": 8}), \
             patch.object(daily_report_entry_demo, "_try_save_daily_report_html_from_saved_markdown", return_value=Path("/tmp/full.html")) as bear_html_mock, \
             patch.object(daily_report_entry_demo, "save_daily_report_html") as structured_html_mock:
            daily_report_entry_demo.main()

        bear_html_mock.assert_called_once()
        self.assertEqual(bear_html_mock.call_args.args, ("2026-06-10",))
        self.assertEqual(bear_html_mock.call_args.kwargs["run_mode"], daily_report_entry_demo.LEDGER_MODE_FROZEN)
        self.assertEqual(
            bear_html_mock.call_args.kwargs["saved_report_paths"],
            {daily_report_entry_demo.REPORT_VARIANT_FULL: "/tmp/full.md"},
        )
        prepend_markdown = bear_html_mock.call_args.kwargs["prepend_markdown"]
        self.assertTrue(prepend_markdown.startswith("| 轨道 | 标的 |"))
        self.assertIn("顶部长时间轴按日报视角展示", prepend_markdown)
        structured_html_mock.assert_not_called()

    def test_saved_markdown_html_sync_overwrites_existing_reader_html(self):
        with TemporaryDirectory() as tempdir:
            full_path = Path(tempdir) / "2026-06-05_A股日报_完整版_replay.md"
            html_path = full_path.with_suffix(".html")
            full_path.write_text(
                "\n".join(
                    [
                        "# 2026-06-05 A股日报",
                        "",
                        "## 市场脊梁",
                        "",
                        "| 指数 | 收盘 | 涨跌幅 | 解读 |",
                        "|------|------|--------|------|",
                        "| 中证500 | 5830.25 | +0.82% | 中盘修复 |",
                        "",
                        "正文",
                    ]
                ),
                encoding="utf-8",
            )
            html_path.write_text("<html><body>OLD_POSTGRES_SHORT_HTML</body></html>", encoding="utf-8")

            path = daily_report_entry_demo._try_save_daily_report_html_from_saved_markdown(
                "2026-06-05",
                run_mode=daily_report_entry_demo.LEDGER_MODE_REPLAY,
                saved_report_paths={daily_report_entry_demo.REPORT_VARIANT_FULL: str(full_path)},
            )

            html = html_path.read_text(encoding="utf-8")

        self.assertEqual(path, html_path)
        self.assertNotIn("OLD_POSTGRES_SHORT_HTML", html)
        self.assertIn("bear-shell", html)
        self.assertIn("Markdown日报", html)
        self.assertIn("市场脊梁", html)
        self.assertIn("中证500", html)
        self.assertIn('<td class="has-signal"><span class="signal-marker signal-hot">+0.82%</span></td>', html)

    def test_sync_position_timeline_into_saved_markdown(self):
        timeline = "\n".join(
            [
                "| 轨道 | 标的 | 2026-06-28（周日） | 2026-06-29（周一） | 2026-06-30（周二） | 2026-07-01（周三） |",
                "|------|------|------|------|------|------|",
                "| Ta旧仓 | 太极实业(600667) | 上一份日报目标，进入旧仓/旧路径复核 | Ta+1 继续处理旧仓或取消路径 | Ta+2 默认按昨晚预案尾盘卖出；失去持有资格才提前处理 | 空仓 |",
                "| Tb明日目标 | 深科技(000021) | 空仓 | 报告日确认明日目标 | Tb+0 条件买入，不是无条件买入 | Tb+1 只按昨晚预案执行或取消 |",
                "| Tc复核位 | 无 | 空仓 | 空仓 | 没有Tc+0，不提前占用 | 下一份日报再复核 |",
            ]
        )
        with TemporaryDirectory() as tempdir:
            full_path = Path(tempdir) / "2026-06-29_A股日报_完整版.md"
            full_path.write_text("# 2026-06-29 A股日报\n\n正文", encoding="utf-8")

            synced = daily_report_entry_demo._sync_position_timeline_into_saved_markdown(
                {daily_report_entry_demo.REPORT_VARIANT_FULL: str(full_path)},
                timeline,
            )
            text = full_path.read_text(encoding="utf-8")
            synced_again = daily_report_entry_demo._sync_position_timeline_into_saved_markdown(
                {daily_report_entry_demo.REPORT_VARIANT_FULL: str(full_path)},
                timeline,
            )
            text_again = full_path.read_text(encoding="utf-8")

        self.assertTrue(synced)
        self.assertTrue(text.startswith("# 2026-06-29 A股日报\n"))
        self.assertIn("## 账户日序表", text)
        self.assertLess(text.index("## 账户日序表"), text.index("正文"))
        self.assertIn("| 轨道 | 标的 | 2026-06-28（周日） | 2026-06-29（周一） | 2026-06-30（周二） |", text)
        self.assertIn("太极实业(600667)", text)
        self.assertIn("深科技(000021)", text)
        self.assertEqual(text, text_again)
        self.assertTrue(synced_again)

    def test_inject_previous_report_target_as_existing_position_context(self):
        data = {}
        with TemporaryDirectory() as tempdir:
            reports_root = Path(tempdir)
            (reports_root / "2026-06-26_A股日报_执行摘要.md").write_text(
                "| 最终对象 | 明日执行对象：太极实业(600667) |\n",
                encoding="utf-8",
            )

            summary = daily_report_entry_demo._inject_previous_report_target_as_existing_position(
                data,
                "2026-06-29",
                reports_root=reports_root,
            )

        self.assertTrue(summary["has_position"])
        self.assertTrue(summary["inferred_from_previous_report"])
        self.assertIn("太极实业(600667)", summary["summary"])
        self.assertIn("100%仓位", summary["summary"])
        self.assertIn("新仓是否叠加单独看Tb/Tc资格", summary["summary"])
        self.assertNotIn("新开仓0手", summary["summary"])
        self.assertEqual(summary["default_position_pct"], 100.0)
        self.assertEqual(summary["position_source"], "previous_report_target_default_1x")
        self.assertEqual(summary["source_report_date"], "2026-06-26")
        self.assertTrue(data["position_context_provided"])
        self.assertEqual(data["personal_position_context"]["existing_position_summary"], summary)

    def test_inferred_previous_report_target_marks_default_old_position_without_manual_input(self):
        data = self._valid_data()
        report_output_calls = []

        def capture_report_outputs(*args, **kwargs):
            report_output_calls.append(kwargs)
            return self._report_outputs()

        with patch.object(sys, "argv", ["daily_report_entry_demo.py", "2026-06-29", "--replay"]), \
             patch.object(daily_report_entry_demo, "replay_from_snapshot", return_value=(data, "2026-06-29")), \
             patch.object(daily_report_entry_demo, "build_report_preflight", return_value={"failures": []}), \
             patch.object(daily_report_entry_demo, "render_report_preflight_lines", return_value=[]), \
             patch.object(daily_report_entry_demo, "_read_previous_report_target_for_entry", return_value={
                 "name": "太极实业",
                 "code": "600667",
                 "source_report_date": "2026-06-26",
             }), \
             patch.object(daily_report_entry_demo, "build_report_outputs", side_effect=capture_report_outputs), \
             patch.object(daily_report_entry_demo, "_resolve_chanlun_tomorrow_decision", return_value={"position_pct": 0}), \
             patch.object(daily_report_entry_demo, "_build_sh_index_chanlun_html_for_audit", return_value="<h2>明日抉择</h2>"), \
             patch.object(daily_report_entry_demo, "_audit_generated_report_with_chanlun_html", return_value={"passed": True, "findings": []}), \
             patch.object(daily_report_entry_demo, "import_daily_report_data_to_postgres", return_value={"source": "postgresql://daily-report-facts/2026-06-29", "field_count": 8}), \
             patch.object(daily_report_entry_demo, "_try_persist_report_runtime_artifacts", return_value={}), \
             patch.object(daily_report_entry_demo, "save_report_outputs", return_value={}), \
             patch.object(daily_report_entry_demo, "save_sh_index_chanlun_html_report", return_value=Path("/tmp/chanlun.html")), \
             patch.object(daily_report_entry_demo, "render_position_strategy_report", return_value="| 轨道 | 标的 | 2026-06-28（周日） |\n|------|------|------|\n| Ta旧仓 | 太极实业(600667) | 旧路径复核 |"), \
             patch.object(daily_report_entry_demo, "save_position_strategy_report", return_value="/tmp/strategy.md"), \
             patch.object(daily_report_entry_demo, "_try_save_daily_report_html_from_saved_markdown", return_value=Path("/tmp/full.html")):
            daily_report_entry_demo.main()

        self.assertEqual(len(report_output_calls), 1)
        self.assertTrue(report_output_calls[0]["has_personal_positions"])
        self.assertTrue(data["position_context_provided"])
        summary = data["personal_position_context"]["existing_position_summary"]
        self.assertTrue(summary["inferred_from_previous_report"])
        self.assertIn("太极实业(600667)", summary["summary"])
        self.assertEqual(summary["position_source"], "previous_report_target_default_1x")

    def test_normal_path_skips_snapshot_when_postgres_fact_sync_succeeds(self):
        order = []

        def save_outputs(*args, **kwargs):
            order.append("markdown")
            return {daily_report_entry_demo.REPORT_VARIANT_FULL: "/tmp/full.md"}

        def save_chanlun(*args, **kwargs):
            order.append("chanlun")
            return Path("/tmp/chanlun.html")

        def sync_postgres(*args, **kwargs):
            order.append("sync")
            return {"source": "postgresql://daily-report-facts/2026-06-05", "field_count": 8}

        def persist_runtime_artifacts(*args, **kwargs):
            order.append("runtime_artifacts")
            return {"decision_ledger_artifacts": {}, "candidate_trace_artifact": None}

        def save_html(*args, **kwargs):
            order.append("html")
            return Path("/tmp/2026-06-05_A股日报_完整版.html")

        with patch.object(sys, "argv", ["daily_report_entry_demo.py", "2026-06-05"]), \
             patch.object(daily_report_entry_demo, "get_daily_data", return_value=self._valid_data()), \
             patch.object(daily_report_entry_demo, "build_report_preflight", return_value={"failures": []}), \
             patch.object(daily_report_entry_demo, "render_report_preflight_lines", return_value=[]), \
             patch.object(daily_report_entry_demo, "load_strategy_performance_ledger", return_value={"records": []}), \
             patch.object(daily_report_entry_demo.os.path, "exists", return_value=False), \
             patch.object(daily_report_entry_demo, "build_report_outputs", return_value=self._report_outputs()), \
             patch.object(daily_report_entry_demo, "persist_report_runtime_artifacts", side_effect=persist_runtime_artifacts), \
             patch.object(daily_report_entry_demo, "_build_sh_index_chanlun_html_for_audit", return_value="<h2>明日抉择</h2>"), \
             patch.object(daily_report_entry_demo, "save_report_outputs", side_effect=save_outputs), \
             patch.object(daily_report_entry_demo, "save_sh_index_chanlun_html_report", side_effect=save_chanlun), \
             patch.object(daily_report_entry_demo, "audit_report_markdown", return_value={"passed": True, "findings": []}), \
             patch.object(daily_report_entry_demo, "_save_data_snapshot") as snapshot_mock, \
             patch.object(daily_report_entry_demo, "import_daily_report_data_to_postgres", side_effect=sync_postgres), \
             patch.object(daily_report_entry_demo, "_try_save_daily_report_html_from_saved_markdown", side_effect=save_html):
            daily_report_entry_demo.main()

        self.assertEqual(order, ["sync", "runtime_artifacts", "markdown", "chanlun", "html"])
        snapshot_mock.assert_not_called()

    def test_html_render_failure_after_save_does_not_prevent_markdown_save(self):
        with patch.object(sys, "argv", ["daily_report_entry_demo.py", "2026-06-05", "--postgres-only"]), \
             patch.object(daily_report_entry_demo, "load_daily_report_data_from_postgres", return_value=self._valid_data()), \
             patch.object(daily_report_entry_demo, "build_report_preflight", return_value={"failures": []}), \
             patch.object(daily_report_entry_demo, "render_report_preflight_lines", return_value=[]), \
             patch.object(daily_report_entry_demo, "load_strategy_performance_ledger", return_value={"records": []}), \
             patch.object(daily_report_entry_demo.os.path, "exists", return_value=False), \
             patch.object(daily_report_entry_demo, "build_report_outputs", return_value=self._report_outputs()), \
             patch.object(daily_report_entry_demo, "persist_report_runtime_artifacts", return_value={}), \
             patch.object(daily_report_entry_demo, "_build_sh_index_chanlun_html_for_audit", return_value="<h2>明日抉择</h2>"), \
             patch.object(daily_report_entry_demo, "save_report_outputs", return_value={daily_report_entry_demo.REPORT_VARIANT_FULL: "/tmp/full.md"}) as save_markdown_mock, \
             patch.object(daily_report_entry_demo, "save_sh_index_chanlun_html_report", return_value=Path("/tmp/chanlun.html")), \
             patch.object(daily_report_entry_demo, "audit_report_markdown", return_value={"passed": True, "findings": []}), \
             patch.object(daily_report_entry_demo, "import_daily_report_data_to_postgres", return_value={"source": "postgresql://daily-report-facts/2026-06-05", "field_count": 8}), \
             patch.object(daily_report_entry_demo, "_try_save_daily_report_html_from_saved_markdown", return_value=None):
            daily_report_entry_demo.main()

        save_markdown_mock.assert_called_once()

    def test_runtime_artifact_failure_does_not_prevent_markdown_save(self):
        order = []

        def save_outputs(*args, **kwargs):
            order.append("markdown")
            return {daily_report_entry_demo.REPORT_VARIANT_FULL: "/tmp/full.md"}

        def save_chanlun(*args, **kwargs):
            order.append("chanlun")
            return Path("/tmp/chanlun.html")

        def save_html(*args, **kwargs):
            order.append("html")
            return Path("/tmp/2026-06-05_A股日报_完整版.html")

        with patch.object(sys, "argv", ["daily_report_entry_demo.py", "2026-06-05", "--postgres-only"]), \
             patch.object(daily_report_entry_demo, "load_daily_report_data_from_postgres", return_value=self._valid_data()), \
             patch.object(daily_report_entry_demo, "build_report_preflight", return_value={"failures": []}), \
             patch.object(daily_report_entry_demo, "render_report_preflight_lines", return_value=[]), \
             patch.object(daily_report_entry_demo, "load_strategy_performance_ledger", return_value={"records": []}), \
             patch.object(daily_report_entry_demo.os.path, "exists", return_value=False), \
             patch.object(daily_report_entry_demo, "build_report_outputs", return_value=self._report_outputs()), \
             patch.object(daily_report_entry_demo, "persist_report_runtime_artifacts", side_effect=OSError("ledger write failed")) as persist_mock, \
             patch.object(daily_report_entry_demo, "_build_sh_index_chanlun_html_for_audit", return_value="<h2>明日抉择</h2>"), \
             patch.object(daily_report_entry_demo, "save_report_outputs", side_effect=save_outputs) as save_markdown_mock, \
             patch.object(daily_report_entry_demo, "save_sh_index_chanlun_html_report", side_effect=save_chanlun), \
             patch.object(daily_report_entry_demo, "audit_report_markdown", return_value={"passed": True, "findings": []}), \
             patch.object(daily_report_entry_demo, "import_daily_report_data_to_postgres", return_value={"source": "postgresql://daily-report-facts/2026-06-05", "field_count": 8}), \
             patch.object(daily_report_entry_demo, "_try_save_daily_report_html_from_saved_markdown", side_effect=save_html):
            daily_report_entry_demo.main()

        persist_mock.assert_called_once()
        save_markdown_mock.assert_called_once()
        self.assertEqual(order, ["markdown", "chanlun", "html"])

    def test_main_saves_sector_capital_preflight_after_markdown(self):
        order = []
        tempdir = TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        html_dir = Path(tempdir.name)

        def save_outputs(*args, **kwargs):
            order.append("markdown")
            return {daily_report_entry_demo.REPORT_VARIANT_FULL: "/tmp/full.md"}

        def sync_postgres(*args, **kwargs):
            order.append("sync")
            return {"source": "postgresql://daily-report-facts/2026-06-05", "field_count": 8}

        def persist_runtime_artifacts(*args, **kwargs):
            order.append("runtime_artifacts")
            return {"decision_ledger_artifacts": {}, "candidate_trace_artifact": None}

        def save_elimination(*args, **kwargs):
            order.append("elimination")
            path = html_dir / "elimination.html"
            path.write_text("<html>elimination</html>", encoding="utf-8")
            return path

        def save_preflight(*args, **kwargs):
            order.append("preflight")
            path = html_dir / "preflight.html"
            path.write_text("<html>preflight</html>", encoding="utf-8")
            return path

        def save_chanlun(*args, **kwargs):
            order.append("chanlun")
            return Path("/tmp/chanlun.html")

        def save_html(*args, **kwargs):
            order.append("html")
            return Path("/tmp/2026-06-05_A股日报_完整版.html")

        with patch.object(sys, "argv", ["daily_report_entry_demo.py", "2026-06-05", "--postgres-only"]), \
             patch.object(daily_report_entry_demo, "load_daily_report_data_from_postgres", return_value=self._valid_data()), \
             patch.object(daily_report_entry_demo, "build_report_preflight", return_value={"failures": []}), \
             patch.object(daily_report_entry_demo, "render_report_preflight_lines", return_value=[]), \
             patch.object(daily_report_entry_demo, "load_strategy_performance_ledger", return_value={"records": []}), \
             patch.object(daily_report_entry_demo.os.path, "exists", return_value=False), \
             patch.object(daily_report_entry_demo, "build_report_outputs", return_value=self._report_outputs()), \
             patch.object(daily_report_entry_demo, "persist_report_runtime_artifacts", side_effect=persist_runtime_artifacts), \
             patch.object(daily_report_entry_demo, "_build_sh_index_chanlun_html_for_audit", return_value="<h2>明日抉择</h2>"), \
             patch.object(daily_report_entry_demo, "save_report_outputs", side_effect=save_outputs), \
             patch.object(daily_report_entry_demo, "_try_save_elimination_tournament_html", side_effect=save_elimination), \
             patch.object(daily_report_entry_demo, "_try_save_sector_capital_preflight_html", side_effect=save_preflight), \
             patch.object(daily_report_entry_demo, "save_sh_index_chanlun_html_report", side_effect=save_chanlun), \
             patch.object(daily_report_entry_demo, "audit_report_markdown", return_value={"passed": True, "findings": []}), \
             patch.object(daily_report_entry_demo, "import_daily_report_data_to_postgres", side_effect=sync_postgres), \
             patch.object(daily_report_entry_demo, "_try_save_daily_report_html_from_saved_markdown", side_effect=save_html):
            daily_report_entry_demo.main()

        self.assertEqual(order, ["sync", "runtime_artifacts", "markdown", "elimination", "preflight", "chanlun", "html"])

    def test_chart_html_fact_missing_still_saves_bear_html(self):
        with patch.object(sys, "argv", ["daily_report_entry_demo.py", "2026-06-05", "--postgres-only"]), \
             patch.object(daily_report_entry_demo, "load_daily_report_data_from_postgres", return_value=self._valid_data()), \
             patch.object(daily_report_entry_demo, "build_report_preflight", return_value={"failures": []}), \
             patch.object(daily_report_entry_demo, "render_report_preflight_lines", return_value=[]), \
             patch.object(daily_report_entry_demo, "load_strategy_performance_ledger", return_value={"records": []}), \
             patch.object(daily_report_entry_demo.os.path, "exists", return_value=False), \
             patch.object(daily_report_entry_demo, "build_report_outputs") as build_mock, \
             patch.object(daily_report_entry_demo, "_build_sh_index_chanlun_html_for_audit", return_value="<h2>明日抉择</h2>"), \
             patch.object(daily_report_entry_demo, "audit_report_markdown", return_value={"passed": True, "findings": []}), \
             patch.object(daily_report_entry_demo, "_assert_html_required_facts_complete", side_effect=daily_report_entry_demo.ReportCriticalDataMissingError("HTML 日报关键数据不完整，停止生成：主线证据")), \
             patch.object(daily_report_entry_demo, "persist_report_runtime_artifacts", return_value={}) as persist_mock, \
             patch.object(daily_report_entry_demo, "save_report_outputs", return_value={daily_report_entry_demo.REPORT_VARIANT_FULL: "/tmp/full.md"}) as save_markdown_mock, \
             patch.object(daily_report_entry_demo, "save_sh_index_chanlun_html_report", return_value=Path("/tmp/chanlun.html")) as save_chanlun_mock, \
             patch.object(daily_report_entry_demo, "import_daily_report_data_to_postgres", return_value={"source": "postgresql://daily-report-facts/2026-06-05", "field_count": 8}) as sync_mock, \
             patch.object(daily_report_entry_demo, "_try_save_daily_report_html_from_saved_markdown") as html_mock:
            daily_report_entry_demo.main()

        build_mock.assert_called_once()
        self.assertFalse(build_mock.call_args.kwargs["persist_runtime_artifacts"])
        persist_mock.assert_called_once()
        save_markdown_mock.assert_called_once()
        save_chanlun_mock.assert_called_once()
        sync_mock.assert_called_once()
        html_mock.assert_called_once()
        self.assertEqual(html_mock.call_args.args, ("2026-06-05",))
        self.assertEqual(html_mock.call_args.kwargs["run_mode"], daily_report_entry_demo.LEDGER_MODE_FROZEN)
        self.assertEqual(
            html_mock.call_args.kwargs["saved_report_paths"],
            {daily_report_entry_demo.REPORT_VARIANT_FULL: "/tmp/full.md"},
        )
        prepend_markdown = html_mock.call_args.kwargs["prepend_markdown"]
        self.assertTrue(prepend_markdown.startswith("| 轨道 | 标的 |"))
        self.assertIn("第一列是报告日，下一交易日是执行日", prepend_markdown)

    def test_bear_html_runs_after_report_runtime_data_exports(self):
        data = self._valid_data()
        data.pop("mainline_context", None)
        data["market_research_snapshot"] = {}
        order = []

        def build_outputs(runtime_data, *args, **kwargs):
            order.append("build")
            runtime_data["market_research_snapshot"] = {
                "front_page_final_gate": {
                    "final_action": "0%不参与；只保留观察对象，不新增参与",
                    "allow_new_entry": False,
                },
                "current_mainline_history_record": {
                    "primary_mainline": "AI算力基础设施",
                    "phase": "发酵",
                },
                "mainline_turnover_summary": {
                    "current_mainline": "AI算力基础设施",
                    "turnover_share_trend_rows": [
                        {
                            "trade_date": "2026-06-08",
                            "mainline": "AI算力基础设施",
                            "turnover_share_pct": 32.1,
                        }
                    ],
                    "mainline_attack_evidence_summary": {
                        "labels": ["成交额集中"],
                    },
                },
            }
            return self._report_outputs()

        def sync_postgres(*args, **kwargs):
            order.append("sync")
            return {"source": "postgresql://daily-report-facts/2026-06-08", "field_count": 8}

        def save_outputs(*args, **kwargs):
            order.append("markdown")
            return {daily_report_entry_demo.REPORT_VARIANT_FULL: "/tmp/full.md"}

        def persist_runtime_artifacts(*args, **kwargs):
            order.append("runtime_artifacts")
            return {"decision_ledger_artifacts": {}, "candidate_trace_artifact": None}

        with patch.object(sys, "argv", ["daily_report_entry_demo.py", "2026-06-08", "--overwrite-official"]), \
             patch.object(daily_report_entry_demo, "get_daily_data", return_value=data), \
             patch.object(daily_report_entry_demo, "build_report_preflight", return_value={"failures": []}), \
             patch.object(daily_report_entry_demo, "render_report_preflight_lines", return_value=[]), \
             patch.object(daily_report_entry_demo, "load_strategy_performance_ledger", return_value={"records": []}), \
             patch.object(daily_report_entry_demo.os.path, "exists", return_value=False), \
             patch.object(daily_report_entry_demo, "build_report_outputs", side_effect=build_outputs), \
             patch.object(daily_report_entry_demo, "persist_report_runtime_artifacts", side_effect=persist_runtime_artifacts) as persist_mock, \
             patch.object(daily_report_entry_demo, "_build_sh_index_chanlun_html_for_audit", return_value="<h2>明日抉择</h2>"), \
             patch.object(daily_report_entry_demo, "save_report_outputs", side_effect=save_outputs), \
             patch.object(daily_report_entry_demo, "save_sh_index_chanlun_html_report", return_value=Path("/tmp/chanlun.html")), \
             patch.object(daily_report_entry_demo, "audit_report_markdown", return_value={"passed": True, "findings": []}), \
             patch.object(daily_report_entry_demo, "import_daily_report_data_to_postgres", side_effect=sync_postgres), \
             patch.object(daily_report_entry_demo, "_try_save_daily_report_html_from_saved_markdown", side_effect=lambda *args, **kwargs: order.append("html") or Path("/tmp/full.html")):
            daily_report_entry_demo.main()

        self.assertEqual(order, ["build", "sync", "runtime_artifacts", "markdown", "html"])
        persist_mock.assert_called_once_with(
            data,
            "2026-06-08",
            run_mode=daily_report_entry_demo.LEDGER_MODE_FROZEN,
        )

    def test_sector_capital_preflight_html_saved_after_markdown(self):
        with TemporaryDirectory() as tempdir:
            full_path = Path(tempdir) / "2026-06-05_A股日报_完整版_replay.md"
            full_path.write_text("# 2026-06-05 A股日报", encoding="utf-8")
            data = self._valid_data()
            data["selection_workflow"] = {
                "schema_version": "selection_workflow.v1",
                "target_date": "2026-06-05",
                "final": {"execution_object": {}, "position_pct": 0, "action_text": "0%不参与"},
            }
            data["final_target_resolution"] = {
                "capital_priority_decision": {"capital_priority": "wait", "reason": "无明日执行对象，保持观察"}
            }
            data["two_layer_decision_payload"] = {"schema_version": "two_layer_daily_decision.v1"}
            data["sniper_target_derivation"] = {"schema_version": "sniper_target_derivation.v1"}

            path = daily_report_entry_demo._try_save_sector_capital_preflight_html(
                data,
                "2026-06-05",
                saved_report_paths={daily_report_entry_demo.REPORT_VARIANT_FULL: str(full_path)},
            )

            html = path.read_text(encoding="utf-8")

        self.assertEqual(path.name, "2026-06-05_板块资金扩散生成前复核.html")
        self.assertIn('meta name="artifact" content="sector-capital-preflight"', html)
        embedded = _embedded_json_payload(html, "sector-capital-preflight-payload")
        self.assertEqual(embedded["schema_version"], "sector_capital_preflight.v1")
        self.assertEqual(embedded["source_payloads"]["selection_workflow"]["schema_version"], "selection_workflow.v1")
        self.assertEqual(
            embedded["source_payloads"]["final_target_resolution"]["capital_priority_decision"]["capital_priority"],
            "wait",
        )
        self.assertEqual(
            embedded["source_payloads"]["two_layer_decision_payload"]["schema_version"],
            "two_layer_daily_decision.v1",
        )
        self.assertEqual(
            embedded["source_payloads"]["sniper_target_derivation"]["schema_version"],
            "sniper_target_derivation.v1",
        )
        self.assertIn("0%不参与", html)

    def test_elimination_tournament_html_uses_same_sector_preflight_chain(self):
        with TemporaryDirectory() as tempdir:
            full_path = Path(tempdir) / "2026-06-08_A股日报_完整版_replay.md"
            full_path.write_text("# 2026-06-08 A股日报", encoding="utf-8")
            data = self._valid_data()
            data["elimination_tournament_payload"] = {
                "schema_version": "elimination_tournament.v1",
                "trade_date": "2026-06-08",
                "variant": "replay",
                "final_action": {
                    "label": "0%不参与",
                    "position_pct": 0,
                    "target": {},
                    "source": "selection_workflow.final",
                    "reason": "无明日执行对象，保持观察",
                },
                "layers": [
                    {
                        "id": "sector",
                        "title": "板块层",
                        "entries": [
                            {
                                "stock": {"name": "大唐发电", "code": "601991", "sector": "火力发电"},
                                "status": "eliminated",
                                "candidate_origin": "legacy_signal_only",
                                "reason": "涨停、连板、T字板、一字板、热榜或旧龙头记忆只能作为过程证据，不能作为新仓入口",
                            }
                        ],
                    }
                ],
            }
            data["hot_plates"] = [{"name": "电力", "order": 1}]
            data["current_mainline_history_record"] = {"leading_line": "电力"}
            data["execution_stage_context"] = {
                "crossline_observation_stocks": [
                    {
                        "code": "601991",
                        "name": "大唐发电",
                        "sector": "火力发电",
                        "source": "hot_capacity_anchor_source",
                        "source_tier": "anchor_reversal_source",
                        "pattern": "放量冲高",
                    }
                ]
            }

            path = daily_report_entry_demo._try_save_elimination_tournament_html(
                data,
                "2026-06-08",
                saved_report_paths={daily_report_entry_demo.REPORT_VARIANT_FULL: str(full_path)},
            )

            html = path.read_text(encoding="utf-8")

        self.assertEqual(path.name, "2026-06-08_明日标的选股淘汰赛.html")
        embedded = _embedded_json_payload(html, "elimination-payload")
        by_id = {layer["id"]: layer for layer in embedded["layers"]}
        self.assertEqual(by_id["market_capital_structure"]["survivor_count"], 1)
        self.assertEqual(by_id["market_capital_structure"]["survivors"][0]["stock_label"], "大唐发电(601991)")
        self.assertEqual(by_id["carrier_role"]["survivor_count"], 1)
        self.assertEqual(by_id["quant_trace"]["input_count"], 1)
        self.assertEqual(by_id["price_action"]["input_count"], 1)
        self.assertEqual(by_id["price_action"]["eliminated_count"], 1)
        self.assertEqual(by_id["final_action"]["survivor_count"], 0)
        self.assertIn("趋势龙头/二波预期", html)

    def test_markdown_audit_failure_stops_before_runtime_artifact_persistence(self):
        data = self._valid_data()

        with patch.object(sys, "argv", ["daily_report_entry_demo.py", "2026-06-08", "--overwrite-official"]), \
             patch.object(daily_report_entry_demo, "get_daily_data", return_value=data), \
             patch.object(daily_report_entry_demo, "build_report_preflight", return_value={"failures": []}), \
             patch.object(daily_report_entry_demo, "render_report_preflight_lines", return_value=[]), \
             patch.object(daily_report_entry_demo, "load_strategy_performance_ledger", return_value={"records": []}), \
             patch.object(daily_report_entry_demo.os.path, "exists", return_value=False), \
             patch.object(daily_report_entry_demo, "build_report_outputs", return_value=self._report_outputs()) as build_mock, \
             patch.object(daily_report_entry_demo, "_build_sh_index_chanlun_html_for_audit", return_value="<h2>明日抉择</h2>"), \
             patch.object(daily_report_entry_demo, "audit_report_markdown", return_value={"passed": False, "findings": [{"code": "X", "message": "broken"}]}), \
             patch.object(daily_report_entry_demo, "persist_report_runtime_artifacts") as persist_mock, \
             patch.object(daily_report_entry_demo, "save_report_outputs") as save_markdown_mock, \
             patch.object(daily_report_entry_demo, "save_sh_index_chanlun_html_report") as save_chanlun_mock, \
             patch.object(daily_report_entry_demo, "import_daily_report_data_to_postgres") as sync_mock, \
             patch.object(daily_report_entry_demo, "_try_save_daily_report_html_from_saved_markdown") as html_mock:
            with self.assertRaises(daily_report_entry_demo.ReportCriticalDataMissingError):
                daily_report_entry_demo.main()

        build_mock.assert_called_once()
        self.assertFalse(build_mock.call_args.kwargs["persist_runtime_artifacts"])
        self.assertTrue(build_mock.call_args.kwargs["persist_decision_ledger"])
        persist_mock.assert_not_called()
        save_markdown_mock.assert_not_called()
        save_chanlun_mock.assert_not_called()
        sync_mock.assert_not_called()
        html_mock.assert_not_called()

    def test_missing_chart_mainline_context_still_saves_bear_html_only(self):
        data = self._valid_data()
        data["mainline_context"] = {}

        with patch.object(sys, "argv", ["daily_report_entry_demo.py", "2026-06-05", "--postgres-only"]), \
             patch.object(daily_report_entry_demo, "load_daily_report_data_from_postgres", return_value=data), \
             patch.object(daily_report_entry_demo, "build_report_preflight", return_value={"failures": []}), \
             patch.object(daily_report_entry_demo, "render_report_preflight_lines", return_value=[]), \
             patch.object(daily_report_entry_demo, "load_strategy_performance_ledger", return_value={"records": []}), \
             patch.object(daily_report_entry_demo.os.path, "exists", return_value=False), \
             patch.object(daily_report_entry_demo, "build_report_outputs") as build_mock, \
             patch.object(daily_report_entry_demo, "_build_sh_index_chanlun_html_for_audit", return_value="<h2>明日抉择</h2>"), \
             patch.object(daily_report_entry_demo, "audit_report_markdown", return_value={"passed": True, "findings": []}), \
             patch.object(daily_report_entry_demo, "persist_report_runtime_artifacts", return_value={}) as persist_mock, \
             patch.object(daily_report_entry_demo, "save_report_outputs", return_value={daily_report_entry_demo.REPORT_VARIANT_FULL: "/tmp/full.md"}) as save_markdown_mock, \
             patch.object(daily_report_entry_demo, "save_sh_index_chanlun_html_report", return_value=Path("/tmp/chanlun.html")) as save_chanlun_mock, \
             patch.object(daily_report_entry_demo, "import_daily_report_data_to_postgres", return_value={"source": "postgresql://daily-report-facts/2026-06-05", "field_count": 8}) as sync_mock, \
             patch.object(daily_report_entry_demo, "_try_save_daily_report_html_from_saved_markdown") as bear_html_mock, \
             patch.object(daily_report_entry_demo, "save_daily_report_html") as chart_html_mock:
            daily_report_entry_demo.main()

        build_mock.assert_called_once()
        self.assertFalse(build_mock.call_args.kwargs["persist_runtime_artifacts"])
        self.assertTrue(build_mock.call_args.kwargs["persist_decision_ledger"])
        persist_mock.assert_called_once()
        save_markdown_mock.assert_called_once()
        save_chanlun_mock.assert_called_once()
        sync_mock.assert_called_once()
        bear_html_mock.assert_called_once()
        self.assertEqual(bear_html_mock.call_args.args, ("2026-06-05",))
        self.assertEqual(bear_html_mock.call_args.kwargs["run_mode"], daily_report_entry_demo.LEDGER_MODE_FROZEN)
        self.assertEqual(
            bear_html_mock.call_args.kwargs["saved_report_paths"],
            {daily_report_entry_demo.REPORT_VARIANT_FULL: "/tmp/full.md"},
        )
        prepend_markdown = bear_html_mock.call_args.kwargs["prepend_markdown"]
        self.assertTrue(prepend_markdown.startswith("| 轨道 | 标的 |"))
        self.assertIn("第一列是报告日，下一交易日是执行日", prepend_markdown)
        chart_html_mock.assert_not_called()

    def test_postgres_only_market_total_only_stops_before_any_artifact_save(self):
        with patch.object(sys, "argv", ["daily_report_entry_demo.py", "2026-06-08", "--postgres-only", "--overwrite-official"]), \
             patch.object(
                 daily_report_entry_demo,
                 "load_daily_report_data_from_postgres",
                 side_effect=daily_report_entry_demo.ReportCriticalDataMissingError(
                     "2026-06-08 PostgreSQL 日报事实缺失，停止生成"
                 ),
             ), \
             patch.object(daily_report_entry_demo, "build_report_outputs") as build_mock, \
             patch.object(daily_report_entry_demo, "import_daily_report_data_to_postgres") as sync_mock, \
             patch.object(daily_report_entry_demo, "save_report_outputs") as save_markdown_mock, \
             patch.object(daily_report_entry_demo, "save_sh_index_chanlun_html_report") as save_chanlun_mock, \
             patch.object(daily_report_entry_demo, "_try_save_daily_report_html_from_saved_markdown") as html_mock:
            with self.assertRaises(daily_report_entry_demo.ReportCriticalDataMissingError):
                daily_report_entry_demo.main()

        build_mock.assert_not_called()
        sync_mock.assert_not_called()
        save_markdown_mock.assert_not_called()
        save_chanlun_mock.assert_not_called()
        html_mock.assert_not_called()

    def test_replay_path_postgres_sync_failure_stops_without_snapshot_fallback(self):
        order = []

        def save_outputs(*args, **kwargs):
            order.append("markdown")
            return {daily_report_entry_demo.REPORT_VARIANT_FULL: "/tmp/full.md"}

        def sync_postgres(*args, **kwargs):
            order.append("sync")
            raise ValueError("connection closed")

        def persist_runtime_artifacts(*args, **kwargs):
            order.append("runtime_artifacts")
            return {"decision_ledger_artifacts": {}, "candidate_trace_artifact": None}

        with patch.object(sys, "argv", ["daily_report_entry_demo.py", "2026-06-05", "--replay"]), \
             patch.object(daily_report_entry_demo, "replay_from_snapshot", return_value=(self._valid_data(), "2026-06-05")), \
             patch.object(daily_report_entry_demo, "build_report_preflight", return_value={"failures": []}), \
             patch.object(daily_report_entry_demo, "render_report_preflight_lines", return_value=[]), \
             patch.object(daily_report_entry_demo, "load_strategy_performance_ledger", return_value={"records": []}), \
             patch.object(daily_report_entry_demo.os.path, "exists", return_value=False), \
             patch.object(daily_report_entry_demo, "build_report_outputs", return_value=self._report_outputs()), \
             patch.object(daily_report_entry_demo, "persist_report_runtime_artifacts", side_effect=persist_runtime_artifacts) as persist_mock, \
             patch.object(daily_report_entry_demo, "_build_sh_index_chanlun_html_for_audit", return_value="<h2>明日抉择</h2>"), \
             patch.object(daily_report_entry_demo, "save_report_outputs", side_effect=save_outputs) as save_markdown_mock, \
             patch.object(daily_report_entry_demo, "save_sh_index_chanlun_html_report", return_value=Path("/tmp/chanlun.html")), \
             patch.object(daily_report_entry_demo, "audit_report_markdown", return_value={"passed": True, "findings": []}), \
             patch.object(daily_report_entry_demo, "_save_data_snapshot") as snapshot_mock, \
             patch.object(daily_report_entry_demo, "import_daily_report_data_to_postgres", side_effect=sync_postgres), \
             patch.object(daily_report_entry_demo, "_try_save_daily_report_html_from_saved_markdown") as html_mock:
            with self.assertRaises(daily_report_entry_demo.ReportCriticalDataMissingError):
                daily_report_entry_demo.main()

        self.assertEqual(order, ["sync"])
        self.assertNotIn("runtime_artifacts", order)
        persist_mock.assert_not_called()
        save_markdown_mock.assert_not_called()
        snapshot_mock.assert_not_called()
        html_mock.assert_not_called()

    def test_live_path_postgres_sync_failure_stops_without_snapshot_fallback(self):
        order = []

        def save_outputs(*args, **kwargs):
            order.append("markdown")
            return {daily_report_entry_demo.REPORT_VARIANT_FULL: "/tmp/full.md"}

        def sync_postgres(*args, **kwargs):
            order.append("sync")
            raise ValueError("connection closed")

        def persist_runtime_artifacts(*args, **kwargs):
            order.append("runtime_artifacts")
            return {"decision_ledger_artifacts": {}, "candidate_trace_artifact": None}

        with patch.object(sys, "argv", ["daily_report_entry_demo.py", "2026-06-05"]), \
             patch.object(daily_report_entry_demo, "get_daily_data", return_value=self._valid_data()), \
             patch.object(daily_report_entry_demo, "build_report_preflight", return_value={"failures": []}), \
             patch.object(daily_report_entry_demo, "render_report_preflight_lines", return_value=[]), \
             patch.object(daily_report_entry_demo, "load_strategy_performance_ledger", return_value={"records": []}), \
             patch.object(daily_report_entry_demo.os.path, "exists", return_value=False), \
             patch.object(daily_report_entry_demo, "build_report_outputs", return_value=self._report_outputs()), \
             patch.object(daily_report_entry_demo, "persist_report_runtime_artifacts", side_effect=persist_runtime_artifacts) as persist_mock, \
             patch.object(daily_report_entry_demo, "_build_sh_index_chanlun_html_for_audit", return_value="<h2>明日抉择</h2>"), \
             patch.object(daily_report_entry_demo, "save_report_outputs", side_effect=save_outputs) as save_markdown_mock, \
             patch.object(daily_report_entry_demo, "save_sh_index_chanlun_html_report", return_value=Path("/tmp/chanlun.html")), \
             patch.object(daily_report_entry_demo, "audit_report_markdown", return_value={"passed": True, "findings": []}), \
             patch.object(daily_report_entry_demo, "_save_data_snapshot") as snapshot_mock, \
             patch.object(daily_report_entry_demo, "import_daily_report_data_to_postgres", side_effect=sync_postgres), \
             patch.object(daily_report_entry_demo, "_try_save_daily_report_html_from_saved_markdown") as html_mock:
            with self.assertRaises(daily_report_entry_demo.ReportCriticalDataMissingError):
                daily_report_entry_demo.main()

        self.assertEqual(order, ["sync"])
        self.assertNotIn("runtime_artifacts", order)
        persist_mock.assert_not_called()
        save_markdown_mock.assert_not_called()
        snapshot_mock.assert_not_called()
        html_mock.assert_not_called()

    def test_chart_html_helper_writes_echarts_dashboard_html(self):
        data = self._valid_data()
        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            with patch.object(daily_report_entry_demo, "__file__", str(root / "scripts" / "daily_report_entry_demo.py")):
                path = daily_report_entry_demo._try_save_daily_report_chart_html(
                    data,
                    "2026-06-05",
                    run_mode=daily_report_entry_demo.LEDGER_MODE_REPLAY,
                    overwrite_existing=True,
                )
            html = path.read_text(encoding="utf-8")

        self.assertEqual(path.name, "2026-06-05_A股日报_完整版_replay.html")
        self.assertIn('id="daily-chart-market-capacity"', html)
        self.assertIn('id="daily-chart-mainline-share"', html)
        self.assertIn('id="daily-chart-payload"', html)
        self.assertIn("图表驾驶舱", html)

    def test_chart_html_helper_can_enrich_market_capacity_from_fact_service(self):
        data = self._valid_data()
        data["top50_turnover_share_series"] = {
            "rows": [
                {"trade_date": "2026-06-04", "share_pct": 20.2},
                {"trade_date": "2026-06-05", "share_pct": 19.0},
            ]
        }

        class FakeFactService:
            def query_market_daily_total(self, trade_date, *, market_scope="all_a"):
                return {
                    "2026-06-04": {"total_amount_yi": 31006.9},
                    "2026-06-05": {"total_amount_yi": 28234.29},
                }.get(trade_date, {})

            def query_market_breadth_counts(self, trade_date):
                return {
                    "2026-06-04": {"up_count": 1520, "down_count": 3920},
                    "2026-06-05": {"up_count": 899, "down_count": 4591},
                }.get(trade_date, {})

        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            with patch.object(daily_report_entry_demo, "__file__", str(root / "scripts" / "daily_report_entry_demo.py")):
                path = daily_report_entry_demo._try_save_daily_report_chart_html(
                    data,
                    "2026-06-05",
                    run_mode=daily_report_entry_demo.LEDGER_MODE_REPLAY,
                    overwrite_existing=True,
                    db_service=FakeFactService(),
                )
            html = path.read_text(encoding="utf-8")

        self.assertIn('"total_turnover":31006.9', html)
        self.assertIn('"up_count":1520', html)
        self.assertIn('"down_count":3920', html)

    def test_no_report_does_not_save_html(self):
        with patch.object(sys, "argv", ["daily_report_entry_demo.py", "2026-06-05", "--no-report"]), \
             patch.object(daily_report_entry_demo, "get_daily_data", return_value=self._valid_data()), \
             patch.object(daily_report_entry_demo, "build_report_preflight", return_value={"failures": []}), \
             patch.object(daily_report_entry_demo, "render_report_preflight_lines", return_value=[]), \
             patch.object(daily_report_entry_demo, "load_strategy_performance_ledger", return_value={"records": []}), \
             patch.object(daily_report_entry_demo.os.path, "exists", return_value=False), \
             patch.object(daily_report_entry_demo, "_save_data_snapshot"), \
             patch.object(daily_report_entry_demo, "import_daily_report_data_to_postgres", return_value={"source": "postgresql://daily-report-facts/2026-06-05", "field_count": 8}), \
             patch.object(daily_report_entry_demo, "_try_save_daily_report_html_from_saved_markdown") as html_mock:
            daily_report_entry_demo.main()

        html_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
