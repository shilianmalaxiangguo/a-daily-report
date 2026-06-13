import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from export.sh_index_chanlun_html import (
    build_sh_index_chanlun_html_path,
    render_sh_index_chanlun_html,
    save_sh_index_chanlun_html_report,
)
from export import zhongshu_visual_snapshot
from daily_report_render import ReportCriticalDataMissingError


def _sample_market_zhongshu():
    return {
        "success": True,
        "today_date": "2026-05-19",
        "today_price": 4186.42,
        "signal": {
            "status": "平台内震荡",
            "signal_type": "按个股信号操作",
            "comparison_state": "inside",
        },
        "current_zhongshu": {
            "segment_type": "zhongshu",
            "start_date": "2026-05-11",
            "end_date": "2026-05-18",
            "kline_count": 6,
            "zg": 4232.18,
            "zd": 4190.25,
            "confirmation_status": "confirmed",
            "reason": "日线三段走势重叠形成平台",
        },
        "latest_structure_segment": {
            "segment_type": "connector",
            "connector_role": "trailing",
            "start_date": "2026-05-19",
            "end_date": "2026-05-19",
            "kline_count": 1,
            "segment_high": 4201.0,
            "segment_low": 4178.0,
            "reason": "尾部连接段",
        },
        "structure_segments": [
            {
                "segment_type": "zhongshu",
                "start_date": "2026-05-11",
                "end_date": "2026-05-18",
                "kline_count": 6,
                "zg": 4232.18,
                "zd": 4190.25,
                "segment_high": 4250.0,
                "segment_low": 4175.0,
                "confirmation_status": "confirmed",
                "reason": "日线三段走势重叠形成平台",
            },
            {
                "segment_type": "connector",
                "connector_role": "trailing",
                "start_date": "2026-05-19",
                "end_date": "2026-05-19",
                "kline_count": 1,
                "segment_high": 4201.0,
                "segment_low": 4178.0,
                "reason": "尾部连接段",
            },
        ],
    }


def _sample_rows():
    return [
        {
            "date": "2026-05-18",
            "open": 4200.0,
            "high": 4250.0,
            "low": 4175.0,
            "close": 4198.0,
            "volume": 100,
            "amount": 1000,
        },
        {
            "date": "2026-05-19",
            "open": 4190.0,
            "high": 4201.0,
            "low": 4178.0,
            "close": 4186.42,
            "volume": 120,
            "amount": 1200,
        },
    ]


class ShIndexChanlunHtmlTest(unittest.TestCase):
    def test_render_html_keeps_structure_segments_and_escapes_raw_text(self):
        market_zhongshu = _sample_market_zhongshu()
        market_zhongshu["structure_segments"][0]["reason"] = "日线三段走势重叠形成平台 <script>alert(1)</script>"
        payload = {
            "date": "2026-05-19",
            "index_code": "sh000001",
            "market_zhongshu": market_zhongshu,
            "index_klines": {"sh000001": _sample_rows()},
            "calculation_windows": {
                "structural_base_daily_bars": 250,
                "report_display_daily_bars": 250,
                "display_row_count": 2,
            },
            "strict_chanlun_policy": {
                "source_algorithm": "practical_daily_node_runtime; full_recursive_mode_deferred",
                "minute_confirmation": "not_requested",
            },
            "source_status": "success",
        }

        with TemporaryDirectory() as tmp:
            echarts_path = Path(tmp) / "echarts.min.js"
            echarts_path.write_text(
                "/* Licensed to the Apache Software Foundation */\nwindow.echarts={init:function(){return {setOption:function(){}}}};",
                encoding="utf-8",
            )
            with patch("export.sh_index_chanlun_html._echarts_source_path", return_value=echarts_path):
                html = render_sh_index_chanlun_html(payload)

        self.assertIn("<h1>2026-05-19 上证指数缠论拆解</h1>", html)
        self.assertIn("sh000001", html)
        self.assertIn("2026-05-11", html)
        self.assertIn("2026-05-18", html)
        self.assertIn("日线三段走势重叠形成平台", html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
        self.assertNotIn("<script>alert(1)</script>", html)

    def test_render_html_uses_echarts_candlestick_boxes_and_bridge_lines_for_structure_review(self):
        payload = {
            "date": "2026-05-19",
            "index_code": "sh000001",
            "market_zhongshu": _sample_market_zhongshu(),
            "index_klines": {"sh000001": _sample_rows()},
            "calculation_windows": {
                "structural_base_daily_bars": 250,
                "report_display_daily_bars": 250,
                "display_row_count": 2,
            },
            "strict_chanlun_policy": {
                "source_algorithm": "practical_daily_node_runtime; full_recursive_mode_deferred",
                "minute_confirmation": "not_requested",
            },
            "source_status": "success",
            "ascii_diagram": "ZG 4232 | ====ZS1====",
        }

        with TemporaryDirectory() as tmp:
            echarts_path = Path(tmp) / "echarts.min.js"
            echarts_path.write_text(
                "/* Licensed to the Apache Software Foundation */\nwindow.echarts={init:function(){return {setOption:function(){}}}};",
                encoding="utf-8",
            )
            with patch("export.sh_index_chanlun_html._echarts_source_path", return_value=echarts_path):
                html = render_sh_index_chanlun_html(payload)

        self.assertIn("Licensed to the Apache Software Foundation", html)
        self.assertNotIn("cdn.jsdelivr", html)
        self.assertIn("echarts.init", html)
        self.assertIn("type: 'candlestick'", html)
        self.assertIn("name: '中枢框'", html)
        self.assertIn("name: '平台桥接线'", html)
        self.assertIn("type: 'custom'", html)
        self.assertIn("type: 'polyline'", html)
        self.assertIn("zoneTopLabel(segment)", html)
        self.assertIn("zoneRangeLabel(segment)", html)
        self.assertIn("当前中枢", html)
        self.assertIn("根K线", html)
        self.assertIn("中枢核心", html)
        self.assertIn("2026-05-11", html)
        self.assertIn("4232.18", html)
        self.assertIn("4190.25", html)
        self.assertNotIn("var markAreas", html)
        self.assertNotIn("markArea: { silent: true", html)
        self.assertNotIn("segment.label + '中枢核心'", html)
        self.assertNotIn("ASCII结构图", html)
        self.assertNotIn("ZG 4232 | ====ZS1====", html)

    def test_summary_distinguishes_core_zg_zd_from_envelope_position(self):
        market_zhongshu = _sample_market_zhongshu()
        market_zhongshu["today_price"] = 4186.42
        market_zhongshu["signal"]["comparison_state"] = "inside"
        payload = {
            "date": "2026-05-19",
            "index_code": "sh000001",
            "market_zhongshu": market_zhongshu,
            "index_klines": {"sh000001": _sample_rows()},
            "calculation_windows": {
                "structural_base_daily_bars": 250,
                "report_display_daily_bars": 250,
                "display_row_count": 2,
            },
            "strict_chanlun_policy": {
                "source_algorithm": "practical_daily_node_runtime; full_recursive_mode_deferred",
                "minute_confirmation": "not_requested",
            },
            "source_status": "success",
        }

        html = render_sh_index_chanlun_html(payload)

        self.assertIn("<td>包络位置</td><td>结构区间内</td>", html)
        self.assertIn("<td>中枢核心</td><td>ZD 4190.25 ~ ZG 4232.18</td>", html)
        self.assertIn("<td>相对核心</td><td>低于ZD", html)

    def test_render_html_includes_tomorrow_decision_when_daily_report_decision_is_available(self):
        market_zhongshu = _sample_market_zhongshu()
        market_zhongshu["signal"] = {
            "status": "跌破并落入下中枢区间",
            "signal_type": "暴跌至下一中枢",
            "comparison_state": "down",
        }
        payload = {
            "date": "2026-05-21",
            "index_code": "sh000001",
            "market_zhongshu": market_zhongshu,
            "index_klines": {"sh000001": _sample_rows()},
            "calculation_windows": {
                "structural_base_daily_bars": 250,
                "report_display_daily_bars": 250,
                "display_row_count": 2,
            },
            "strict_chanlun_policy": {
                "source_algorithm": "practical_daily_node_runtime; full_recursive_mode_deferred",
                "minute_confirmation": "not_requested",
            },
            "source_status": "success",
            "tomorrow_decision": {
                "final_action": "空仓等待，禁止参与；若你有仓位，只做退出不做幻想 <script>alert(1)</script>",
                "can_new_entry": False,
                "operation_state": "观察态",
            },
        }

        html = render_sh_index_chanlun_html(payload)

        self.assertIn("<h2>明日抉择</h2>", html)
        self.assertIn("<td>最终执行条件</td><td>空仓等待，禁止参与；若你有仓位，只做退出不做幻想", html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
        self.assertIn("<td>明日最大仓位</td><td>0%</td>", html)
        self.assertIn("<td>新增参与</td><td>不参与</td>", html)
        self.assertIn("<td>指数结构含义</td><td>跌破并落入下中枢区间；暴跌至下一中枢</td>", html)
        self.assertNotIn("<script>alert(1)</script>", html)

    def test_save_report_writes_one_standalone_html_under_reports(self):
        def fake_runner(target_date, index_code):
            self.assertEqual(target_date, "2026-05-19")
            self.assertEqual(index_code, "sh000001")
            return _sample_market_zhongshu(), _sample_rows()

        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            written_path = save_sh_index_chanlun_html_report(
                "2026-05-19",
                root=root,
                runner=fake_runner,
            )

            expected_path = build_sh_index_chanlun_html_path("2026-05-19", root=root)
            self.assertEqual(written_path, expected_path)
            self.assertTrue(written_path.exists())
            self.assertEqual([path.suffix for path in written_path.parent.iterdir()], [".html"])
            text = written_path.read_text(encoding="utf-8")
            self.assertIn("2026-05-19 上证指数缠论拆解", text)
            self.assertIn("结构分段明细", text)
            self.assertIn("近日日K", text)
            self.assertIn("尾部连接段", text)

    def test_save_report_can_carry_daily_report_tomorrow_decision(self):
        def fake_runner(target_date, index_code):
            self.assertEqual(target_date, "2026-05-21")
            self.assertEqual(index_code, "sh000001")
            return _sample_market_zhongshu(), _sample_rows()

        with TemporaryDirectory() as tempdir:
            written_path = save_sh_index_chanlun_html_report(
                "2026-05-21",
                root=Path(tempdir),
                runner=fake_runner,
                tomorrow_decision={
                    "final_action": "空仓等待，禁止参与；若你有仓位，只做退出不做幻想",
                    "can_new_entry": False,
                    "operation_state": "观察态",
                },
            )

            text = written_path.read_text(encoding="utf-8")
            self.assertIn("明日抉择", text)
            self.assertIn("空仓等待，禁止参与；若你有仓位，只做退出不做幻想", text)

    def test_zero_position_tomorrow_decision_final_action_mentions_no_participation(self):
        payload = {
            "date": "2026-05-21",
            "index_code": "sh000001",
            "market_zhongshu": _sample_market_zhongshu(),
            "index_klines": {"sh000001": _sample_rows()},
            "tomorrow_decision": {
                "final_action": "禁止新增；若你有旧仓，去弱留强，不强就卖",
                "can_new_entry": False,
                "operation_state": "防守态",
            },
        }

        html = render_sh_index_chanlun_html(payload)

        self.assertIn("<td>最终执行条件</td><td>不新增参与；若你有旧仓，去弱留强，不强就卖</td>", html)
        self.assertIn("<td>明日最大仓位</td><td>0%</td>", html)
        self.assertIn("<td>新增参与</td><td>不参与</td>", html)

    def test_daily_entry_invokes_independent_html_report(self):
        source = (ROOT / "scripts" / "daily_report_entry_demo.py").read_text(encoding="utf-8")

        self.assertIn("save_sh_index_chanlun_html_report,", source)
        self.assertIn("save_sh_index_chanlun_html_report(", source)
        self.assertIn("_resolve_chanlun_tomorrow_decision(data)", source)

    def test_run_analysis_with_postgres_only_loader_does_not_fallback_to_live_sources(self):
        def postgres_loader(index_code, target_date, recent_days):
            self.assertEqual(index_code, "sh000001")
            self.assertEqual(target_date, "2026-05-29")
            self.assertEqual(recent_days, 250)
            return [], "postgresql.index_daily_bars"

        with patch(
            "market_data.daily_price_runtime.fetch_daily_price_bars",
            side_effect=AssertionError("live fallback must not run in PostgreSQL-only chanlun HTML"),
        ):
            result, rows = zhongshu_visual_snapshot.run_analysis(
                "2026-05-29",
                "sh000001",
                sse_loader=postgres_loader,
                allow_live_fallback=False,
            )

        self.assertFalse(result["success"])
        self.assertEqual(result["data_source"], "postgresql.index_daily_bars")
        self.assertEqual(rows, [])

    def test_save_html_rejects_missing_postgres_daily_bars_without_writing_empty_page(self):
        def missing_postgres_runner(target_date, index_code, **kwargs):
            self.assertFalse(kwargs.get("allow_live_fallback", True))
            return {
                "success": False,
                "error": "PostgreSQL指数日K不足，停止缠论HTML生成",
                "data_source": "postgresql.index_daily_bars",
            }, []

        with TemporaryDirectory() as tempdir:
            with self.assertRaises(ReportCriticalDataMissingError):
                save_sh_index_chanlun_html_report(
                    "2026-05-29",
                    root=tempdir,
                    runner=missing_postgres_runner,
                    allow_live_fallback=False,
                )

            self.assertFalse(build_sh_index_chanlun_html_path("2026-05-29", root=tempdir).exists())

    def test_render_html_exposes_daily_bar_data_source(self):
        payload = zhongshu_visual_snapshot.normalize_visual_payload(
            {
                "success": True,
                "data_source": "postgresql.index_daily_bars",
                "today_date": "2026-05-29",
                "today_price": 4068.57,
                "signal": {"status": "日线中枢内震荡"},
            },
            [
                {
                    "date": "2026-05-29",
                    "open": 4060.0,
                    "high": 4075.0,
                    "low": 4050.0,
                    "close": 4068.57,
                }
            ],
            date="2026-05-29",
            index_code="sh000001",
        )

        html = render_sh_index_chanlun_html(payload)

        self.assertIn("日线数据源", html)
        self.assertIn("postgresql.index_daily_bars", html)


if __name__ == "__main__":
    unittest.main()
