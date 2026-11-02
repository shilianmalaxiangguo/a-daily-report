import copy
import html as html_lib
import json
import re
import sys
import unittest
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import daily_report_entry_demo
from knowledge.llm_wiki_context import build_llm_wiki_context
from knowledge.llm_wiki_router import route_llm_wiki_knowledge_trace


def _embedded_json_payload(rendered_html, script_id):
    match = re.search(
        rf'<script type="application/json" id="{script_id}">(.*?)</script>',
        rendered_html,
        re.S,
    )
    if not match:
        return {}
    return json.loads(html_lib.unescape(match.group(1)))


def _complete_wiki_context(target_date):
    context = build_llm_wiki_context(
        target_date=target_date,
        query_date="2026-07-17",
    )
    trace = route_llm_wiki_knowledge_trace(
        {"market": {"breadth": "上涨家数偏弱"}},
        manifest=context["manifest"],
        target_date=target_date,
        query_date="2026-07-17",
    )
    context["knowledge_hits"] = list(trace["hits"])
    context["knowledge_trace"] = trace
    return context


class DailyReportEntryHtmlOutputTest(unittest.TestCase):
    def setUp(self):
        report_output_tempdir = TemporaryDirectory()
        self.addCleanup(report_output_tempdir.cleanup)

        def temporary_report_output_path(target_date, mode="frozen", variant="full"):
            replay_suffix = "_replay" if mode == daily_report_entry_demo.LEDGER_MODE_REPLAY else ""
            label = '完整版' if variant == daily_report_entry_demo.REPORT_VARIANT_FULL else variant
            return str(
                Path(report_output_tempdir.name)
                / f"{target_date}_A股日报_{label}{replay_suffix}.md"
            )

        report_output_path_patcher = patch.object(
            daily_report_entry_demo,
            "_get_report_output_path",
            side_effect=temporary_report_output_path,
        )
        report_output_path_patcher.start()
        self.addCleanup(report_output_path_patcher.stop)

        path_selection_patcher = patch.object(
            daily_report_entry_demo,
            "_select_daily_report_data_path",
            side_effect=lambda args, target_date: {
                "eligible": False,
                "selected_path": daily_report_entry_demo._daily_report_data_path_label(args),
                "target_date": target_date,
                "reason": "保留测试指定路径",
                "data": {},
                "preflight": {},
            },
        )
        path_selection_patcher.start()
        self.addCleanup(path_selection_patcher.stop)

        def accept_legacy_save_stub(report_path, expected_markdown):
            return str(expected_markdown or "")

        saved_report_patcher = patch.object(
            daily_report_entry_demo,
            "read_verified_saved_report_markdown",
            side_effect=accept_legacy_save_stub,
        )
        saved_report_patcher.start()
        self.addCleanup(saved_report_patcher.stop)

        strategy_save_patcher = patch.object(
            daily_report_entry_demo,
            "save_position_strategy_report",
            return_value="/tmp/position-strategy.md",
        )
        strategy_save_patcher.start()
        self.addCleanup(strategy_save_patcher.stop)

        strategy_calendar_build_patcher = patch.object(
            daily_report_entry_demo,
            "_build_tomorrow_action_calendar_for_bear",
            return_value={
                "schema": "tomorrow_action_calendar.v1",
                "mode": "frozen",
                "requested_count": 25,
                "record_count": 0,
                "status": "source_incomplete",
                "records": [],
                "summary": {},
            },
        )
        strategy_calendar_build_patcher.start()
        self.addCleanup(strategy_calendar_build_patcher.stop)

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

    def test_day_order_timeline_is_inserted_after_heading_and_reading_map(self):
        markdown = "# 2026-07-08 A股日报\n\n## 阅读地图\n| 顺序 | 模块 | 用途 |\n|---:|---|---|\n| 1 | 明日执行结论 | 先看动作 |\n\n## 明日执行结论\n正文\n"
        timeline = "\n".join(
            [
                "| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |",
                "|------|------|----------|----------|-------------|------|",
                "| Td | 2026-07-08（周三） | 报告日：空仓 | 无 | 只定Te预案，不下单；B2不存在直到Te确认 | 写清执行资格和取消条件 |",
                "| Te | 2026-07-09（周四） | 新目标单独看B1，不用旧仓亏损补仓 | 华天科技(002185) | B1参与权；B2确认权 | B1未变强则取消B2；只检查B1 |",
            ]
        )

        updated = daily_report_entry_demo._prepend_position_timeline_markdown(markdown, timeline)
        updated_again = daily_report_entry_demo._prepend_position_timeline_markdown(updated, timeline)

        self.assertEqual(updated.count("## 账户日序表"), 1)
        self.assertEqual(updated_again, updated)
        self.assertLess(updated.index("## 阅读地图"), updated.index("## 账户日序表"))
        self.assertIn("| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |", updated)
        self.assertIn("| Te | 2026-07-09（周四） | 新目标单独看B1，不用旧仓亏损补仓 | 华天科技(002185) | B1参与权；B2确认权 | B1未变强则取消B2；只检查B1 |", updated)

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

    def test_build_t0_market_breadth_keeps_latest_25_dates_and_historical_nulls(self):
        class FactService:
            def __init__(self):
                self.index_query = None
                self.breadth_dates = []
                self.new_high_query_count = 0

            def query_index_daily_bars(self, index_code, end_date, *, window_days):
                self.index_query = (index_code, end_date, window_days)
                rows = [
                    {
                        "trade_date": f"2026-06-{day:02d}",
                        "close": 99 + day,
                    }
                    for day in range(1, 27)
                ]
                rows.append({"trade_date": "2026-06-27", "close": 127})
                return list(reversed(rows))

            def query_market_breadth_counts(self, trade_date):
                self.breadth_dates.append(trade_date)
                if trade_date == "2026-06-10":
                    return {
                        "trade_date": trade_date,
                        "source_date": "2026-06-09",
                        "up_count": 3100,
                        "down_count": 1900,
                    }
                return {
                    "trade_date": trade_date,
                    "source_date": trade_date,
                    "up_count": 3000,
                    "down_count": 2000,
                }

            def query_new_high_feedback_series(self, end_date, *, window_days):
                self.new_high_query_count += 1
                rows = [
                    {
                        "trade_date": f"2026-06-{day:02d}",
                        "all_a_share_pct": day / 10,
                    }
                    for day in range(2, 27)
                ]
                rows[9]["source_date"] = "2026-06-10"
                rows.append({"trade_date": "2026-06-27", "all_a_share_pct": 9.9})
                return rows

        service = FactService()

        payload = daily_report_entry_demo._build_t0_market_breadth_for_bear(
            "2026-06-26",
            service=service,
        )

        self.assertEqual(service.index_query, ("sh000985", "2026-06-26", 26))
        self.assertEqual(service.new_high_query_count, 1)
        self.assertEqual(len(payload["items"]), 25)
        self.assertEqual(payload["items"][0]["date"], "2026-06-02")
        self.assertEqual(payload["items"][-1]["date"], "2026-06-26")
        self.assertEqual(payload["items"][0]["all_a_change_pct"], 1.0)
        self.assertEqual(service.breadth_dates, [item["date"] for item in payload["items"]])
        self.assertNotIn("2026-06-27", [item["date"] for item in payload["items"]])
        items_by_date = {item["date"]: item for item in payload["items"]}
        self.assertIsNone(items_by_date["2026-06-10"]["up_count"])
        self.assertIsNone(items_by_date["2026-06-10"]["down_count"])
        self.assertIsNone(items_by_date["2026-06-11"]["new_high_share_pct"])

    def test_build_t0_market_breadth_prefers_report_new_high_history(self):
        class FactService:
            def __init__(self):
                self.new_high_query_count = 0

            def query_index_daily_bars(self, index_code, end_date, *, window_days):
                return [
                    {"trade_date": "2026-07-21", "close": 100},
                    {"trade_date": "2026-07-22", "close": 99},
                ]

            def query_market_breadth_counts(self, trade_date):
                return {
                    "trade_date": trade_date,
                    "source_date": trade_date,
                    "up_count": 1530,
                    "down_count": 3876,
                }

            def query_new_high_feedback_series(self, end_date, *, window_days):
                self.new_high_query_count += 1
                return [
                    {
                        "trade_date": "2026-07-22",
                        "all_a_share_pct": 0.28,
                    }
                ]

        service = FactService()
        report_rows = [
            {
                "trade_date": "2026-07-22",
                "all_a_share_pct": 0.10,
            }
        ]

        payload = daily_report_entry_demo._build_t0_market_breadth_for_bear(
            "2026-07-22",
            service=service,
            new_high_rows=report_rows,
            limit=1,
        )

        self.assertEqual(service.new_high_query_count, 0)
        self.assertEqual(payload["items"][0]["new_high_share_pct"], 0.10)

    def test_build_chinext_index_trend_keeps_latest_25_valid_target_date_rows(self):
        class FactService:
            def __init__(self):
                self.index_query = None

            def query_index_daily_bars(
                self,
                index_code,
                end_date,
                *,
                window_days,
                finite_positive_close_only,
            ):
                self.index_query = (
                    index_code,
                    end_date,
                    window_days,
                    finite_positive_close_only,
                )
                rows = [
                    {
                        "date": f"2026-06-{day:02d}",
                        "close": 3000 + day,
                    }
                    for day in range(1, 31)
                ]
                rows.extend(
                    [
                        {"date": "2026-07-01", "close": 4000},
                        {"date": "2026-06-30", "close": 3030},
                        {"date": "2026-06-29", "close": "nan"},
                        {"date": "", "close": 3028},
                        {"date": "2026-06-28", "close": 0},
                    ]
                )
                return list(reversed(rows))

        service = FactService()

        payload = daily_report_entry_demo._build_chinext_index_trend_for_bear(
            "2026-06-30",
            service=service,
        )

        self.assertEqual(
            service.index_query,
            ("sz399006", "2026-06-30", 25, True),
        )
        self.assertEqual(payload["schema"], "chinext_index_trend.v1")
        self.assertEqual(len(payload["items"]), 25)
        self.assertEqual(payload["items"][0], {"date": "2026-06-06", "close": 3006.0})
        self.assertEqual(payload["items"][-1], {"date": "2026-06-30", "close": 3030.0})
        self.assertEqual(
            [item["date"] for item in payload["items"]],
            sorted({item["date"] for item in payload["items"]}),
        )
        self.assertNotIn("2026-07-01", [item["date"] for item in payload["items"]])

    def test_build_chinext_index_trend_returns_empty_when_history_is_unavailable(self):
        class FactService:
            def query_index_daily_bars(
                self,
                index_code,
                end_date,
                *,
                window_days,
                finite_positive_close_only,
            ):
                raise OSError("history unavailable")

        self.assertEqual(
            daily_report_entry_demo._build_chinext_index_trend_for_bear(
                "2026-06-30",
                service=FactService(),
            ),
            {},
        )

    def test_bear_html_input_hash_changes_with_chinext_history(self):
        base_kwargs = {
            "output_path": Path("/tmp/2026-08-12_A股日报_完整版.html"),
            "t0_market_breadth": {"items": []},
        }

        without_chinext = daily_report_entry_demo._daily_report_bear_html_input_hash(
            "2026-08-12",
            "# 日报",
            **base_kwargs,
        )
        with_chinext = daily_report_entry_demo._daily_report_bear_html_input_hash(
            "2026-08-12",
            "# 日报",
            chinext_index_trend={
                "schema": "chinext_index_trend.v1",
                "items": [{"date": "2026-08-12", "close": 3602.0835}],
            },
            **base_kwargs,
        )

        self.assertNotEqual(without_chinext, with_chinext)

    def test_bear_turnover_facts_reach_renderer_and_invalidate_cached_html(self):
        rows = [{"code": "300450", "name": "先导智能", "trade_date": "2026-10-13", "turnover": 43.462502, "change_pct": -9.58}]
        kwargs = {"output_path": Path("/tmp/turnover.html"), "turnover_rank": rows}
        original_hash = daily_report_entry_demo._daily_report_bear_html_input_hash("2026-10-13", "# 日报", **kwargs)
        html = daily_report_entry_demo._render_daily_report_html_for_acceptance("2026-10-13", "# 日报", **kwargs)
        payload = _embedded_json_payload(html, "bear-chart-payload")
        self.assertEqual(payload["turnover_top30"]["items"][0]["turnover"], 43.462502)
        rows[0]["turnover"] = 44.0
        updated_hash = daily_report_entry_demo._daily_report_bear_html_input_hash("2026-10-13", "# 日报", **kwargs)
        self.assertNotEqual(original_hash, updated_hash)

    def test_bear_html_input_hash_changes_with_cffex_evidence_hash(self):
        base_kwargs = {
            "output_path": Path("/tmp/2026-08-19_A股日报_完整版.html"),
        }

        without_cffex = daily_report_entry_demo._daily_report_bear_html_input_hash(
            "2026-08-19",
            "# 日报",
            **base_kwargs,
        )
        with_cffex = daily_report_entry_demo._daily_report_bear_html_input_hash(
            "2026-08-19",
            "# 日报",
            cffex_index_futures_position_evidence={
                "schema_version": "cffex_index_futures_position_evidence.v1",
                "artifact_hash": "cffex-frozen-hash",
            },
            **base_kwargs,
        )

        self.assertNotEqual(without_cffex, with_cffex)

    def test_bear_html_input_hash_and_extraction_include_sector_three_axis(self):
        artifact = {
            "schema_version": "sector_tournament_three_axis.v1",
            "target_date": "2026-08-14",
            "artifact_hash": "frozen-three-axis",
        }
        data = {
            "selection_workflow": {
                "sector_tournament_three_axis": artifact,
            },
            "final_target_resolution": {
                "position_pct": 50,
                "execution_nature": "50%条件执行",
            },
        }
        before = copy.deepcopy(data)
        base_kwargs = {
            "output_path": Path("/tmp/2026-08-14_A股日报_完整版.html"),
        }

        without_three_axis = daily_report_entry_demo._daily_report_bear_html_input_hash(
            "2026-08-14",
            "# 日报",
            **base_kwargs,
        )
        with_three_axis = daily_report_entry_demo._daily_report_bear_html_input_hash(
            "2026-08-14",
            "# 日报",
            sector_tournament_three_axis=artifact,
            **base_kwargs,
        )

        self.assertNotEqual(without_three_axis, with_three_axis)
        self.assertIs(
            daily_report_entry_demo._sector_tournament_three_axis_for_bear(data),
            artifact,
        )
        self.assertEqual(data, before)
        self.assertEqual(
            daily_report_entry_demo._sector_tournament_three_axis_for_bear({}),
            {},
        )

    def test_t0_market_breadth_rendering_keeps_formal_decisions_unchanged(self):
        class FactService:
            def query_index_daily_bars(self, index_code, end_date, *, window_days):
                return [
                    {"trade_date": "2026-07-21", "close": 100},
                    {"trade_date": "2026-07-22", "close": 99},
                ]

            def query_market_breadth_counts(self, trade_date):
                return {
                    "trade_date": trade_date,
                    "source_date": trade_date,
                    "up_count": 1530,
                    "down_count": 3876,
                }

        data = {
            "selection_workflow": {
                "schema_version": "selection_workflow.v1",
                "final": {"position_pct": 50},
            },
            "final_target_resolution": {
                "new_entry_target": {"code": "603986", "name": "兆易创新"},
                "position_pct": 50,
                "execution_nature": "50%条件执行",
            },
            "two_layer_decision_payload": {
                "next_day_action": {
                    "execution_object": {"code": "603986", "name": "兆易创新"},
                    "position_pct": 50,
                    "execution_nature": "50%条件执行",
                    "b1_action": "B1先买参与权",
                    "b2_action": "确认后才补B2",
                    "exit_action": "失效条件出现则退出",
                }
            },
            "new_high_feedback": {
                "trend_rows": [
                    {"trade_date": "2026-07-22", "all_a_share_pct": 0.10},
                ]
            },
        }
        before = copy.deepcopy(data)

        chart = daily_report_entry_demo._build_t0_market_breadth_for_bear(
            "2026-07-22",
            service=FactService(),
            new_high_rows=data["new_high_feedback"]["trend_rows"],
            limit=1,
        )
        html = daily_report_entry_demo._render_daily_report_html_for_acceptance(
            "2026-07-22",
            "# 日报\n\n### 1. 指数与市场底色\n\n| 项目 | 结论 |\n|---|---|\n| 市场 | 防守 |",
            output_path=Path("/tmp/2026-07-22_A股日报_完整版_replay.html"),
            t0_market_breadth=chart,
        )

        self.assertIn('data-bear-chart="t0_market_breadth"', html)
        self.assertEqual(data, before)
        self.assertEqual(data["selection_workflow"], before["selection_workflow"])
        self.assertEqual(data["final_target_resolution"], before["final_target_resolution"])
        self.assertEqual(
            data["two_layer_decision_payload"]["next_day_action"],
            before["two_layer_decision_payload"]["next_day_action"],
        )



    def test_saved_markdown_html_sync_overwrites_existing_reader_html(self):
        with TemporaryDirectory() as tempdir:
            full_path = Path(tempdir) / "2026-06-05_A股日报_完整版_replay.md"
            html_path = full_path.with_suffix(".html")
            full_path.write_text(
                "\n".join(
                    [
                        "# 2026-06-05 A股日报",
                        "",
                        "## 明日执行结论",
                        "",
                        "### 账户动作",
                        "",
                        "明日新仓 0%不参与。",
                        "",
                        "### 执行条件",
                        "",
                        "条件满足才可做。",
                        "",
                        "### 不执行条件",
                        "",
                        "条件未满足，明日不做。",
                        "",
                        "## 经验库命中",
                        "",
                        "| 命中经验 | 知识ID |",
                        "|----------|--------|",
                        "| 指数强但赚钱效应弱 | `market.low-frequency-focus` |",
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
        self.assertIn(
            '<h2 class="bear-section-action" id="明日执行结论">明日执行结论</h2>',
            html,
        )
        self.assertIn(
            '<h2 class="bear-section-evidence" id="经验库命中">经验库命中</h2>',
            html,
        )
        self.assertLess(html.index('id="明日执行结论"'), html.index('id="经验库命中"'))
        self.assertLess(html.index('id="账户动作"'), html.index('id="经验库命中"'))
        self.assertLess(html.index('id="执行条件"'), html.index('id="经验库命中"'))
        self.assertLess(html.index('id="不执行条件"'), html.index('id="经验库命中"'))
        self.assertIn("市场脊梁", html)
        self.assertIn("中证500", html)
        self.assertIn('<td class="has-signal"><span class="signal-marker signal-hot">+0.82%</span></td>', html)

    def test_saved_replay_markdown_html_includes_t0_market_breadth_chart(self):
        with TemporaryDirectory() as tempdir:
            full_path = Path(tempdir) / "2026-06-05_A股日报_完整版_replay.md"
            full_path.write_text(
                "\n".join(
                    [
                        "# 2026-06-05 A股日报",
                        "",
                        "## 二、市场基底",
                        "",
                        "### 1. 指数与市场底色",
                        "",
                        "| 项目 | 结论 |",
                        "|------|------|",
                        "| 原始事实 | 保留 |",
                    ]
                ),
                encoding="utf-8",
            )
            breadth = {
                "items": [
                    {
                        "date": "2026-06-05",
                        "up_count": 3200,
                        "down_count": 1800,
                        "all_a_change_pct": 0.82,
                        "new_high_share_pct": 1.64,
                    }
                ]
            }

            path = daily_report_entry_demo._try_save_daily_report_html_from_saved_markdown(
                "2026-06-05",
                run_mode=daily_report_entry_demo.LEDGER_MODE_REPLAY,
                saved_report_paths={daily_report_entry_demo.REPORT_VARIANT_FULL: str(full_path)},
                t0_market_breadth=breadth,
            )
            html = path.read_text(encoding="utf-8")
            payload = _embedded_json_payload(html, "bear-chart-payload")

        self.assertEqual(path, full_path.with_suffix(".html"))
        self.assertEqual(html.count('data-bear-chart="t0_market_breadth"'), 1)
        self.assertEqual(payload["t0_market_breadth"]["items"], breadth["items"])

    def test_saved_replay_markdown_html_includes_chinext_overlay(self):
        with TemporaryDirectory() as tempdir:
            full_path = Path(tempdir) / "2026-08-12_A股日报_完整版_replay.md"
            full_path.write_text(
                "\n".join(
                    [
                        "# 2026-08-12 A股日报",
                        "",
                        "| 日期 | Top50占比 | 状态 | 较前日 | Top50成交额 | 两市成交额 |",
                        "|---|---:|---|---:|---:|---:|",
                        "| 2026-08-12 | 21.86% | 集中 | +0.75pct | 5828.45亿 | 26667.33亿 |",
                    ]
                ),
                encoding="utf-8",
            )
            chinext = {
                "schema": "chinext_index_trend.v1",
                "items": [{"date": "2026-08-12", "close": 3602.0835}],
            }

            path = daily_report_entry_demo._try_save_daily_report_html_from_saved_markdown(
                "2026-08-12",
                run_mode=daily_report_entry_demo.LEDGER_MODE_REPLAY,
                saved_report_paths={daily_report_entry_demo.REPORT_VARIANT_FULL: str(full_path)},
                chinext_index_trend=chinext,
            )
            html = path.read_text(encoding="utf-8")
            payload = _embedded_json_payload(html, "bear-chart-payload")

        chart = payload["market_turnover_top50_trend"]
        self.assertEqual(chart["chinext_available_count"], 1)
        self.assertEqual(chart["items"][0]["chinext_close"], 3602.0835)
        self.assertIn('data-bear-chart="top50_share_trend"', html)

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

    def test_sync_position_timeline_replaces_existing_markdown_section(self):
        timeline = "\n".join(
            [
                "| 轨道 | 标的 | 2026-07-05（周日） | 2026-07-06（周一） | 2026-07-07（周二） | 2026-07-08（周三） |",
                "|------|------|------|------|------|------|",
                "| Ta旧仓 | 太极实业(600667) | 上一份日报目标，进入旧仓/旧路径复核 | Ta+1 继续处理旧仓或取消路径 | Ta+2 优先处理旧仓，空仓时间尽可能接近全天空仓 | 空仓 |",
                "| Tb明日目标 | 空仓 | 空仓 | 没有Tb+0，空仓 | 没有Tb+1，空仓 | 空仓 |",
                "| Tc复核位 | 无 | 空仓 | 空仓 | 没有Tc+0，不提前占用 | 下一份日报再复核 |",
            ]
        )
        old_text = "\n".join(
            [
                "# 2026-07-06 A股日报",
                "",
                "## 阅读地图",
                "| 顺序 | 模块 | 用途 |",
                "|---:|---|---|",
                "| 1 | 日报裁决总览 | 先看动作 |",
                "",
                "## 账户日序表",
                "| 轨道 | 标的 | 2026-07-05（周日） | 2026-07-06（周一） | 2026-07-07（周二） | 2026-07-08（周三） |",
                "|------|------|------|------|------|------|",
                "| Tb明日目标 | 太极实业(600667) | 空仓 | 报告日确认明日目标 | Tb+0 条件买入，不是无条件买入 | Tb+1 只按昨晚预案执行或取消 |",
                "",
                "## 日报裁决总览",
                "正文",
            ]
        )
        with TemporaryDirectory() as tempdir:
            full_path = Path(tempdir) / "2026-07-06_A股日报_完整版.md"
            full_path.write_text(old_text, encoding="utf-8")

            synced = daily_report_entry_demo._sync_position_timeline_into_saved_markdown(
                {daily_report_entry_demo.REPORT_VARIANT_FULL: str(full_path)},
                timeline,
            )
            text = full_path.read_text(encoding="utf-8")

        self.assertTrue(synced)
        self.assertEqual(text.count("## 账户日序表"), 1)
        self.assertIn("| Tb明日目标 | 空仓 | 空仓 | 没有Tb+0，空仓 | 没有Tb+1，空仓 | 空仓 |", text)
        self.assertLess(text.index("## 账户日序表"), text.index("## 日报裁决总览"))
        self.assertNotIn("| Tb明日目标 | 太极实业(600667)", text)

    def test_extract_previous_report_target_ignores_observation_only_changdian_report(self):
        text = """
## 日报裁决总览
| 项目 | 结论 |
|------|------|
| 仓位姿态 | 0%不参与 |
| 最终对象 | 观察对象：长电科技(600584) |
| 对象性质 | 观察对象，不新增参与 |
| 推导摘要 | 明日执行目标为无，只观察长电科技(600584)的承接是否重新成立。 |

## 明日执行结论
| 项目 | 结论 |
|------|------|
| 明日仓位 | 0%不参与 |
| 明日执行对象 | 无 |
| 执行目标 | 无 |
| 观察对象 | 长电科技(600584) |

`-- 最终对象=长电科技(600584) 身份=观察对象（执行目标为无）
"""

        self.assertEqual(daily_report_entry_demo._extract_report_target_from_markdown(text), {})

    def test_entry_timeline_sync_keeps_changdian_process_target_out_of_tb_path(self):
        from portfolio.position_strategy_report import render_position_strategy_report

        source_report = """
## 日报裁决总览
| 项目 | 结论 |
|------|------|
| 仓位姿态 | 0%不参与 |
| 最终对象 | 观察对象：长电科技(600584) |
| 对象性质 | 观察对象，不新增参与 |
| 推导摘要 | 明日执行目标为无，只观察长电科技(600584)的承接是否重新成立。 |

## 明日执行结论
| 项目 | 结论 |
|------|------|
| 明日仓位 | 0%不参与 |
| 明日执行对象 | 无 |
| 执行目标 | 无 |
| 观察对象 | 长电科技(600584) |

`-- 最终对象=长电科技(600584) 身份=观察对象（执行目标为无）
"""
        with TemporaryDirectory() as strategy_root:
            strategy = render_position_strategy_report(
                data={
                    "final_target_resolution": {
                        "new_entry_target": {},
                        "process_target": {"name": "长电科技", "code": "600584", "sector": "半导体"},
                        "display_target": {"name": "长电科技", "code": "600584", "sector": "半导体"},
                        "capital_priority_decision": {"capital_priority": "wait", "reason": "无明日执行对象，保持观察"},
                    },
                    "execution_stage_context": {
                        "extreme_conviction_list": [
                            {
                                "name": "长电科技",
                                "code": "600584",
                                "sector": "半导体",
                                "planned_participation": {"buy_window": "09:50-10:10", "attack_state": "50%"},
                            }
                        ],
                        "selection_workflow": {
                            "final": {
                                "execution_object": {},
                                "position_pct": 0,
                                "action_text": "0%不参与",
                            }
                        },
                    },
                },
                target_date="2026-07-06",
                positions=[],
                source_report_markdown=source_report,
                output_root=Path(strategy_root),
            )
        timeline = daily_report_entry_demo._extract_position_timeline_markdown(strategy)
        old_markdown = "\n".join(
            [
                "# 2026-07-06 A股日报",
                "",
                "## 账户日序表",
                "| 轨道 | 标的 | 2026-07-05（周日） | 2026-07-06（周一） | 2026-07-07（周二） | 2026-07-08（周三） |",
                "|------|------|------|------|------|------|",
                "| Tb明日目标 | 长电科技(600584) | 空仓 | 报告日确认明日目标 | Tb+0 条件买入，不是无条件买入 | Tb+1 只按昨晚预案执行或取消 |",
                "",
                "## 日报裁决总览",
                "| 项目 | 结论 |",
                "|------|------|",
                "| 仓位姿态 | 0%不参与 |",
                "| 最终对象 | 无 |",
                "",
                "## 明日执行结论",
                "| 项目 | 结论 |",
                "|------|------|",
                "| 明日仓位 | 0%不参与 |",
                "| 明日执行对象 | 无 |",
                "| 执行性质 | 无明日执行对象 |",
            ]
        )
        with TemporaryDirectory() as tempdir:
            full_path = Path(tempdir) / "2026-07-06_A股日报_完整版.md"
            full_path.write_text(old_markdown, encoding="utf-8")

            synced = daily_report_entry_demo._sync_position_timeline_into_saved_markdown(
                {daily_report_entry_demo.REPORT_VARIANT_FULL: str(full_path)},
                timeline,
            )
            text = full_path.read_text(encoding="utf-8")

        self.assertTrue(synced)
        self.assertIn("| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |", text)
        self.assertIn("| Te | 2026-07-07（周二） | 空仓等待B1资格 | 无 | 没有B1/B2；保持空仓 | 空仓等待下一份日报 |", text)
        self.assertNotIn("| Tb明日目标 | 长电科技(600584)", text)
        self.assertIn(
            "| 长电科技 | 600584 | 半导体 | 无新增参与窗口 | 0%不参与 | 只作过程回放，不新增参与 | 不参与 | - |",
            strategy,
        )

    def test_inject_previous_report_target_as_simulated_default_old_position(self):
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
        self.assertFalse(summary["has_pending_position"])
        self.assertEqual(summary["role"], "旧仓处理")
        self.assertTrue(summary["inferred_from_previous_report"])
        self.assertIn("太极实业(600667)", summary["summary"])
        self.assertIn("上一份日报明日标的默认1x旧仓", summary["summary"])
        self.assertEqual(summary["holding_note"], "上一份日报明日标的默认1x旧仓")
        self.assertEqual(summary["position"], 50.0)
        self.assertEqual(summary["position_pct"], 50.0)
        self.assertEqual(summary["default_position_pct"], 50.0)
        self.assertEqual(summary["position_source"], "previous_report_target_default_1x")
        self.assertEqual(summary["source_report_date"], "2026-06-26")
        self.assertTrue(data["position_context_provided"])
        self.assertEqual(data["personal_position_context"]["existing_position_summary"], summary)

    def test_inject_previous_report_target_replaces_unprovided_unknown_summary(self):
        unknown_summary = {
            "has_position": False,
            "has_pending_position": False,
            "summary": "持仓未输入",
        }
        data = {
            "position_context_provided": False,
            "personal_position_context": {
                "existing_position_summary": dict(unknown_summary),
            },
            "existing_position_summary": dict(unknown_summary),
        }

        with patch.object(
            daily_report_entry_demo,
            "_read_previous_report_target_for_entry",
            return_value={
                "name": "长电科技",
                "code": "600584",
                "source_report_date": "2026-07-09",
            },
        ):
            summary = daily_report_entry_demo._inject_previous_report_target_as_existing_position(
                data,
                "2026-07-15",
            )

        self.assertTrue(summary["has_position"])
        self.assertFalse(summary["has_pending_position"])
        self.assertEqual(summary["name"], "长电科技")
        self.assertEqual(summary["position_pct"], 50.0)
        self.assertEqual(summary["default_position_pct"], 50.0)
        self.assertEqual(summary["position_source"], "previous_report_target_default_1x")
        self.assertTrue(data["position_context_provided"])
        self.assertEqual(
            data["personal_position_context"]["existing_position_summary"],
            summary,
        )

    def test_inject_previous_report_explicit_empty_as_confirmed_empty_position(self):
        unknown_summary = {
            "has_position": False,
            "has_pending_position": False,
            "summary": "持仓未输入",
        }
        data = {
            "position_context_provided": False,
            "personal_position_context": {
                "existing_position_summary": dict(unknown_summary),
            },
            "existing_position_summary": dict(unknown_summary),
        }

        with patch.object(
            daily_report_entry_demo,
            "_read_previous_report_target_for_entry",
            return_value={
                "source_report_date": "2026-07-15",
                "previous_report_no_target": True,
                "previous_position_ended": True,
            },
        ):
            summary = daily_report_entry_demo._inject_previous_report_target_as_existing_position(
                data,
                "2026-07-16",
            )

        self.assertFalse(summary["has_position"])
        self.assertFalse(summary["has_pending_position"])
        self.assertEqual(summary["position_source"], "previous_report_explicit_empty")
        self.assertEqual(summary["source_report_date"], "2026-07-15")
        self.assertTrue(data["position_context_provided"])
        self.assertEqual(data["existing_position_summary"], summary)
        self.assertEqual(
            data["personal_position_context"]["existing_position_summary"],
            summary,
        )

    def test_inject_older_explicit_empty_does_not_confirm_current_position(self):
        unknown_summary = {
            "has_position": False,
            "has_pending_position": False,
            "summary": "持仓未输入",
        }
        data = {
            "position_context_provided": False,
            "personal_position_context": {
                "existing_position_summary": dict(unknown_summary),
            },
            "existing_position_summary": dict(unknown_summary),
        }

        with patch.object(
            daily_report_entry_demo,
            "_read_previous_report_target_for_entry",
            return_value={
                "source_report_date": "2026-07-29",
                "previous_report_no_target": True,
                "previous_position_ended": True,
            },
        ):
            summary = daily_report_entry_demo._inject_previous_report_target_as_existing_position(
                data,
                "2026-07-31",
            )

        self.assertEqual(summary, {})
        self.assertFalse(data["position_context_provided"])
        self.assertEqual(data["existing_position_summary"], unknown_summary)
        self.assertEqual(
            data["personal_position_context"]["existing_position_summary"],
            unknown_summary,
        )

    def test_inject_previous_report_unresolved_no_target_keeps_position_unknown(self):
        data = {"position_context_provided": False}

        with patch.object(
            daily_report_entry_demo,
            "_read_previous_report_target_for_entry",
            return_value={
                "source_report_date": "2026-07-15",
                "previous_report_no_target": True,
            },
        ):
            summary = daily_report_entry_demo._inject_previous_report_target_as_existing_position(
                data,
                "2026-07-16",
            )

        self.assertEqual(summary, {})
        self.assertFalse(data["position_context_provided"])
        self.assertNotIn("existing_position_summary", data)

    def test_inject_previous_report_preserves_external_trade_pending(self):
        pending_summary = {
            "has_position": False,
            "has_pending_position": True,
            "summary": "外部交易待核实",
            "position": 0.0,
            "position_pct": 0.0,
            "position_source": "external_trade_pending",
        }
        data = {
            "position_context_provided": False,
            "personal_position_context": {
                "existing_position_summary": dict(pending_summary),
            },
            "existing_position_summary": dict(pending_summary),
        }

        with patch.object(
            daily_report_entry_demo,
            "_read_previous_report_target_for_entry",
            return_value={
                "name": "长电科技",
                "code": "600584",
                "source_report_date": "2026-07-15",
            },
        ) as read_previous:
            summary = daily_report_entry_demo._inject_previous_report_target_as_existing_position(
                data,
                "2026-07-16",
            )

        self.assertEqual(summary, {})
        read_previous.assert_not_called()
        self.assertEqual(
            data["personal_position_context"]["existing_position_summary"],
            pending_summary,
        )
        self.assertEqual(data["existing_position_summary"], pending_summary)
        self.assertFalse(data["position_context_provided"])




    def test_normalize_inferred_previous_target_records_updates_all_snapshot_copies(self):
        stale = {
            "name": "长电科技",
            "code": "600584",
            "summary": "持有长电科技(600584)，100%仓位",
            "position": 100.0,
            "position_source": "previous_report_target_default_1x",
            "source_report_date": "2026-07-09",
            "inferred_from_previous_report": True,
            "role": "旧仓处理",
        }
        data = {
            "personal_position_context": {"existing_position_summary": dict(stale)},
            "market_research_snapshot": {
                "final_target_resolution": {"existing_position_target": dict(stale)}
            },
        }

        normalized = daily_report_entry_demo._normalize_inferred_previous_target_records(data)

        self.assertEqual(normalized, 2)
        for record in (
            data["personal_position_context"]["existing_position_summary"],
            data["market_research_snapshot"]["final_target_resolution"]["existing_position_target"],
        ):
            self.assertEqual(
                record["summary"],
                "持有长电科技(600584)，1x/50%半仓，上一份日报明日标的默认1x旧仓；上一份日报目标来源=2026-07-09",
            )
            self.assertTrue(record["has_position"])
            self.assertFalse(record["has_pending_position"])
            self.assertEqual(record["position"], 50.0)
            self.assertEqual(record["position_pct"], 50.0)
            self.assertEqual(record["default_position_pct"], 50.0)
            self.assertEqual(record["role"], "旧仓处理")
            self.assertEqual(record["holding_note"], "上一份日报明日标的默认1x旧仓")

    def test_normalize_inferred_previous_target_records_repairs_marker_only_legacy_record(self):
        record = {
            "name": "长电科技",
            "code": "600584",
            "summary": "持有长电科技(600584)，100%仓位",
            "has_position": True,
            "position": "100",
            "position_pct": 100.0,
            "position_source": "previous_report_target_default_1x",
            "source_report_date": "2026-07-09",
        }

        normalized = daily_report_entry_demo._normalize_inferred_previous_target_records(record)

        self.assertEqual(normalized, 1)
        self.assertTrue(record["inferred_from_previous_report"])
        self.assertFalse(record["has_pending_position"])
        self.assertTrue(record["has_position"])
        self.assertEqual(record["position"], 50.0)
        self.assertEqual(record["position_pct"], 50.0)
        self.assertEqual(record["default_position_pct"], 50.0)
        self.assertEqual(record["role"], "旧仓处理")
        self.assertEqual(record["holding_note"], "上一份日报明日标的默认1x旧仓")

    def test_normalize_inferred_previous_target_records_handles_shared_reference_cycle(self):
        pending = {
            "name": "长电科技",
            "code": "600584",
            "summary": "持有长电科技(600584)，100%仓位",
            "position": 100.0,
            "position_source": "previous_report_target_default_1x",
            "inferred_from_previous_report": True,
        }
        data = {"pending": pending}
        data["execution_stage_context"] = {"pending": pending, "root": data}

        normalized = daily_report_entry_demo._normalize_inferred_previous_target_records(data)

        self.assertEqual(normalized, 1)
        self.assertTrue(pending["has_position"])
        self.assertFalse(pending["has_pending_position"])
        self.assertEqual(pending["position"], 50.0)
        self.assertEqual(pending["position_pct"], 50.0)
        self.assertEqual(pending["default_position_pct"], 50.0)

    def test_normalize_inferred_previous_target_records_keeps_confirmed_position_unchanged(self):
        record = {
            "name": "长电科技",
            "code": "600584",
            "summary": "持有长电科技(600584)，100%仓位",
            "has_position": True,
            "position": 100.0,
            "position_pct": 100.0,
            "position_source": "explicit_position_input",
        }
        expected = dict(record)

        normalized = daily_report_entry_demo._normalize_inferred_previous_target_records(record)

        self.assertEqual(normalized, 0)
        self.assertEqual(record, expected)

    def test_postgres_write_boundaries_normalize_inherited_position_exposure(self):
        captured = []

        class FakeService:
            def load_daily_report_snapshot(self, target_date):
                return {
                    "source": f"postgresql://daily-report-facts/{target_date}",
                    "field_count": 10,
                    "target_field_count": 10,
                    "data": stale_data(),
                }

            def save_daily_report_snapshot(self, target_date, data):
                captured.append(("save", target_date, data))
                return {"source": "postgresql://save"}

            def import_daily_report_facts(self, target_date, data):
                captured.append(("import", target_date, data))
                return {"source": "postgresql://import"}

        def stale_data():
            return {
                "selection_workflow": {
                    "schema_version": "selection_workflow.v1",
                    "final": {
                        "execution_object": {},
                        "position_pct": 0,
                        "action_text": "弱收盘价格否定，0%不参与",
                    },
                    "candidate_pool": [],
                },
                "position_decision": {
                    "target_position_pct": 0,
                    "signal_grade": "0",
                    "participation_mode": "observe_0",
                    "final_action": "已决定50%条件执行",
                },
                "final_target_resolution": {
                    "new_entry_target": {"name": "长电科技", "code": "600584"},
                    "display_target": {"name": "长电科技", "code": "600584"},
                    "capital_priority_decision": {"capital_priority": "old_position_t"},
                    "account_exposure_plan": {
                        "old_position_1x": True,
                        "new_entry_1x": False,
                        "max_exposure_x": 1,
                    },
                },
                "personal_position_context": {
                    "existing_position_summary": {
                        "name": "长电科技",
                        "code": "600584",
                        "has_position": True,
                        "position": 100.0,
                        "position_pct": 100.0,
                        "position_source": "previous_report_target_default_1x",
                    }
                }
            }

        with patch.object(daily_report_entry_demo, "_postgres_daily_report_service", return_value=FakeService()):
            loaded = daily_report_entry_demo.load_daily_report_data_from_postgres("2026-07-10")
            daily_report_entry_demo.save_daily_report_data_to_postgres("2026-07-10", stale_data())
            daily_report_entry_demo.import_daily_report_data_to_postgres("2026-07-10", stale_data())

        self.assertEqual([item[0] for item in captured], ["save", "import"])
        for data in [loaded, *(item[2] for item in captured)]:
            summary = data["personal_position_context"]["existing_position_summary"]
            self.assertTrue(summary["has_position"])
            self.assertFalse(summary["has_pending_position"])
            self.assertEqual(summary["position"], 50.0)
            self.assertEqual(summary["position_pct"], 50.0)
            self.assertEqual(summary["default_position_pct"], 50.0)
            position_decision = data["position_decision"]
            self.assertEqual(position_decision["target_position_pct"], 0)
            self.assertEqual(position_decision["final_action"], "0%不参与")
            resolution = data["final_target_resolution"]
            self.assertEqual(resolution["new_entry_target"], {})
            self.assertEqual(resolution["existing_position_target"]["code"], "600584")
            self.assertTrue(resolution["account_exposure_plan"]["old_position_1x"])
            self.assertEqual(resolution["account_exposure_plan"]["max_runtime_exposure_x"], 1)
            for resolution_copy in (
                data["final_target_resolution"],
                data["execution_stage_context"]["final_target_resolution"],
                data["market_research_snapshot"]["final_target_resolution"],
            ):
                inherited = resolution_copy["existing_position_target"]
                self.assertTrue(inherited["has_position"])
                self.assertFalse(inherited["has_pending_position"])
                self.assertEqual(inherited["role"], "旧仓处理")
                self.assertEqual(inherited["position"], 50.0)
                self.assertEqual(inherited["position_pct"], 50.0)
                self.assertEqual(inherited["default_position_pct"], 50.0)

    def test_stale_cleanup_preserves_historical_tomorrow_empty_directive(self):
        directive = {
            "schema_version": "tomorrow_account_action.v1",
            "action": "empty",
            "source": "historical_snapshot",
        }
        data = {
            "position_decision": {
                "tomorrow_account_action": dict(directive),
                "capital_priority_decision": {"capital_priority": "tomorrow_empty"},
            },
            "final_target_resolution": {
                "tomorrow_account_action": dict(directive),
                "capital_priority_decision": {"capital_priority": "tomorrow_empty"},
            },
        }

        daily_report_entry_demo._clear_stale_tomorrow_empty_resolution_copies(data)

        for container in (data["position_decision"], data["final_target_resolution"]):
            self.assertEqual(container["tomorrow_account_action"], directive)
            self.assertEqual(
                container["capital_priority_decision"]["capital_priority"],
                "tomorrow_empty",
            )

    def test_cached_cli_cleanup_includes_position_decision(self):
        data = {
            "position_decision": {
                "tomorrow_account_action": {
                    "schema_version": "tomorrow_account_action.v1",
                    "action": "empty",
                    "source": "explicit_cli",
                },
                "capital_priority_decision": {"capital_priority": "tomorrow_empty"},
            }
        }

        daily_report_entry_demo._clear_cached_explicit_cli_tomorrow_account_action(data)

        self.assertNotIn("tomorrow_account_action", data["position_decision"])
        self.assertNotIn("capital_priority_decision", data["position_decision"])



    def test_fresh_snapshot_rejects_incomplete_wiki_trace(self):
        data = {
            "knowledge": {
                "llm_wiki": {
                    "knowledge_trace": {
                        "schema_version": "knowledge_trace.v1",
                        "trace_hash": "1" * 64,
                    }
                }
            }
        }

        with self.assertRaisesRegex(
            daily_report_entry_demo.ReportCriticalDataMissingError,
            "知识引用资料不完整",
        ):
            daily_report_entry_demo._assert_fresh_llm_wiki_trace_complete(
                data,
                "2026-06-05",
                run_mode=daily_report_entry_demo.LEDGER_MODE_FROZEN,
            )

        daily_report_entry_demo._assert_fresh_llm_wiki_trace_complete(
            data,
            "2026-06-05",
            run_mode=daily_report_entry_demo.LEDGER_MODE_REPLAY,
        )

        complete = _complete_wiki_context("2026-06-05")
        with patch.object(
            daily_report_entry_demo,
            "is_complete_fresh_llm_wiki_context",
            return_value=False,
        ) as complete_check:
            with self.assertRaisesRegex(
                daily_report_entry_demo.ReportCriticalDataMissingError,
                "知识引用资料不完整",
            ):
                daily_report_entry_demo._assert_fresh_llm_wiki_trace_complete(
                    {"knowledge": {"llm_wiki": complete}},
                    "2026-06-05",
                    run_mode=daily_report_entry_demo.LEDGER_MODE_FROZEN,
                )
        complete_check.assert_called_once_with(
            complete,
            target_date="2026-06-05",
        )





    def test_bear_html_acceptance_failure_does_not_write_html(self):
        with TemporaryDirectory() as tempdir:
            report_path = Path(tempdir) / "2026-07-10_A股日报_完整版_replay.md"
            report_path.write_text("# report\n", encoding="utf-8")
            html_path = report_path.with_suffix(".html")

            def reject_html(_html_text):
                raise daily_report_entry_demo.ReportCriticalDataMissingError(
                    "position_timeline_html_missing: Bear HTML缺少账户日序表，停止生成"
                )

            with patch.object(daily_report_entry_demo, "render_markdown_report_html", return_value="<html>invalid</html>"):
                with self.assertRaises(daily_report_entry_demo.ReportCriticalDataMissingError):
                    daily_report_entry_demo._try_save_daily_report_html_from_saved_markdown(
                        "2026-07-10",
                        run_mode=daily_report_entry_demo.LEDGER_MODE_REPLAY,
                        saved_report_paths={daily_report_entry_demo.REPORT_VARIANT_FULL: str(report_path)},
                        validate_html=reject_html,
                    )

            self.assertFalse(html_path.exists())
            self.assertFalse(html_path.with_suffix(".html.tmp").exists())







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

        self.assertEqual(path.name, "2026-06-08_过程候选淘汰赛.html")
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



if __name__ == "__main__":
    unittest.main()
