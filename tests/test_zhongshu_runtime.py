import sys
import unittest
import urllib.error
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import decision.zhongshu_runtime as zhongshu_runtime
from decision.zhongshu_runtime import analyze_market_zhongshu, build_zhongshu_structure


def _raise_skill_version_low(*args, **kwargs):
    raise urllib.error.HTTPError(
        url="https://openapi.iwencai.com/v1/query2data",
        code=401,
        msg="Unauthorized",
        hdrs={},
        fp=BytesIO("当前 Skill 版本过低，本次请求无法执行。".encode("utf-8")),
    )


class ZhongshuRuntimeTest(unittest.TestCase):
    def test_iwencai_index_dataframe_sends_current_skillhub_headers(self):
        captured = {}

        class Response:
            def read(self):
                return b'{"status_code": 0, "datas": [{"\\u5f00\\u76d8\\u4ef7[20260428]": 1, "\\u6700\\u9ad8\\u4ef7[20260428]": 2, "\\u6700\\u4f4e\\u4ef7[20260428]": 0.5, "\\u6536\\u76d8\\u4ef7[20260428]": 1.5, "\\u6210\\u4ea4\\u91cf[20260428]": 100}]}'

        def fake_urlopen(request, timeout=30):
            captured["request"] = request
            return Response()

        df, source = zhongshu_runtime._load_iwencai_index_dataframe(1, urlopen_fn=fake_urlopen)

        request = captured["request"]
        self.assertEqual(source, "同花顺问财API")
        self.assertEqual(len(df), 1)
        self.assertEqual(request.get_header("X-claw-skill-id"), "hithink-market-query")
        self.assertEqual(request.get_header("X-claw-skill-version"), "1.0.0")
        self.assertEqual(request.get_header("X-claw-call-type"), "normal")
        self.assertEqual(request.get_header("X-claw-plugin-id"), "none")
        self.assertEqual(request.get_header("X-claw-plugin-version"), "none")
        self.assertEqual(len(request.get_header("X-claw-trace-id")), 64)

    def test_build_zhongshu_structure_detects_platform_without_20_klines(self):
        rows = [
            {"date": "2026-04-14", "open": 100, "high": 102, "low": 98, "close": 100, "volume": 1},
            {"date": "2026-04-15", "open": 100, "high": 112, "low": 99, "close": 110, "volume": 1},
            {"date": "2026-04-16", "open": 110, "high": 111, "low": 100, "close": 101, "volume": 1},
            {"date": "2026-04-17", "open": 101, "high": 110, "low": 100, "close": 109, "volume": 1},
        ]
        df = pd.DataFrame(rows)

        structure_segments, zhongshu_list = build_zhongshu_structure(df, min_zhongshu_klines=20)

        self.assertEqual([item["segment_type"] for item in structure_segments], ["zhongshu"])
        self.assertEqual(len(zhongshu_list), 1)
        self.assertEqual(zhongshu_list[0]["kline_count"], 4)
        self.assertNotIn("required_kline_count", zhongshu_list[0])
        self.assertEqual(zhongshu_list[0]["confirmation_status"], "confirmed")

    def test_analyze_market_zhongshu_marks_short_platform_as_confirmed_current(self):
        df = pd.DataFrame(
            [
                {"date": "2026-04-15", "open": 99, "high": 105, "low": 95, "close": 100, "volume": 1},
                {"date": "2026-04-16", "open": 100, "high": 104, "low": 96, "close": 101, "volume": 1},
                {"date": "2026-04-17", "open": 101, "high": 103, "low": 97, "close": 100, "volume": 1},
                {"date": "2026-04-20", "open": 100, "high": 104, "low": 96, "close": 102, "volume": 1},
                {"date": "2026-04-21", "open": 101, "high": 105, "low": 95, "close": 103, "volume": 1},
                {"date": "2026-04-22", "open": 102, "high": 104, "low": 96, "close": 102, "volume": 1},
                {"date": "2026-04-23", "open": 103, "high": 108, "low": 102, "close": 107, "volume": 1},
            ]
        )

        result = analyze_market_zhongshu(
            target_date="2026-04-23",
            fetch_dataframe=lambda **kwargs: (df, "test_feed"),
            use_chanlun_confirmation=False,
            print_fn=lambda *args, **kwargs: None,
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["current_zhongshu"]["confirmation_status"], "confirmed")
        self.assertNotIn("required_kline_count", result["current_zhongshu"])
        self.assertNotIn("/20", result["signal"]["status"])
        self.assertNotIn("等20根", result["signal"]["action"])
        self.assertEqual(result["latest_structure_segment"]["segment_type"], "connector")
        self.assertEqual(result["latest_structure_segment"]["connector_role"], "trailing")
        self.assertEqual(result["latest_structure_segment"]["start_date"], "2026-04-23")
        self.assertEqual(result["latest_structure_segment"]["end_date"], "2026-04-23")

    def test_append_today_trailing_connector_merges_existing_trailing_connector(self):
        structure_segments = [
            {
                "segment_type": "zhongshu",
                "start_date": "2026-04-01",
                "end_date": "2026-04-20",
                "kline_count": 13,
                "zg": 23.49,
                "zd": 21.01,
                "high": 27.68,
                "low": 20.71,
                "segment_high": 27.68,
                "segment_low": 20.71,
                "start_close": 21.88,
                "end_close": 27.31,
            },
            {
                "segment_type": "connector",
                "structure_kind": "connecting_line",
                "connector_id": "daily_macro_connector_6",
                "start_date": "2026-04-21",
                "end_date": "2026-04-27",
                "kline_count": 5,
                "high": 33.25,
                "low": 25.22,
                "segment_high": 33.25,
                "segment_low": 25.22,
                "start_close": 26.02,
                "end_close": 32.56,
                "connector_role": "trailing",
            },
        ]
        today_row = {"date": "2026-04-28", "high": 31.48, "low": 29.61, "close": 29.99}

        result = zhongshu_runtime.append_today_trailing_connector(structure_segments, today_row)

        self.assertEqual(len(result), 2)
        trailing = result[-1]
        self.assertEqual(trailing["segment_type"], "connector")
        self.assertEqual(trailing["connector_role"], "trailing")
        self.assertEqual(trailing["start_date"], "2026-04-21")
        self.assertEqual(trailing["end_date"], "2026-04-28")
        self.assertEqual(trailing["kline_count"], 6)
        self.assertEqual(trailing["high"], 33.25)
        self.assertEqual(trailing["low"], 25.22)
        self.assertEqual(trailing["start_close"], 26.02)
        self.assertEqual(trailing["end_close"], 29.99)

    def test_ascii_diagram_labels_forming_structure_without_claiming_confirmed(self):
        diagram = zhongshu_runtime.build_zhongshu_ascii_diagram(
            [
                {
                    "segment_type": "connector",
                    "start_date": "2026-04-10",
                    "end_date": "2026-04-13",
                    "kline_count": 2,
                    "segment_high": 102,
                    "segment_low": 96,
                    "start_close": 98,
                    "end_close": 101,
                },
                {
                    "segment_type": "zhongshu",
                    "start_date": "2026-04-14",
                    "end_date": "2026-04-24",
                    "kline_count": 9,
                    "required_kline_count": 20,
                    "zg": 105,
                    "zd": 95,
                    "segment_high": 106,
                    "segment_low": 94,
                    "start_close": 100,
                    "end_close": 102,
                },
            ],
            today_date="2026-04-27",
            today_price=101,
            signal={"comparison_result": "震荡", "comparison_state": "range"},
        )

        self.assertIn("当前形成中结构: 04-14->04-24", diagram)
        self.assertNotIn("最新确认结构中枢", diagram)

    def test_analyze_market_zhongshu_supports_injected_dataframe_and_detects_breakout(self):
        df = pd.DataFrame(
            [
                {"date": "2026-04-15", "open": 99, "high": 105, "low": 95, "close": 100, "volume": 1},
                {"date": "2026-04-16", "open": 100, "high": 104, "low": 96, "close": 101, "volume": 1},
                {"date": "2026-04-17", "open": 101, "high": 103, "low": 97, "close": 100, "volume": 1},
                {"date": "2026-04-18", "open": 100, "high": 104, "low": 96, "close": 102, "volume": 1},
                {"date": "2026-04-21", "open": 101, "high": 105, "low": 95, "close": 103, "volume": 1},
                {"date": "2026-04-22", "open": 103, "high": 108, "low": 102, "close": 107, "volume": 1},
            ]
        )

        result = analyze_market_zhongshu(
            target_date="2026-04-22",
            fetch_dataframe=lambda **kwargs: (df, "test_feed"),
            use_chanlun_confirmation=False,
            print_fn=lambda *args, **kwargs: None,
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["data_source"], "test_feed")
        self.assertEqual(result["signal"]["signal_type"], "大盘突破")
        self.assertEqual(result["signal"]["comparison_result"], "突破")
        self.assertEqual(len(result["zhongshu_list"]), 1)
        self.assertEqual(result["today_date"], "2026-04-22")

    def test_analyze_market_zhongshu_uses_tushare_index_daily_primary_for_120_day_window(self):
        dates = pd.bdate_range(end="2026-04-27", periods=130)
        rows = [
            {
                "date": date.strftime("%Y-%m-%d"),
                "open": 3900 + index,
                "high": 3920 + index,
                "low": 3880 + index,
                "close": 3905 + index,
                "volume": 100000 + index,
                "amount": 1000000 + index,
            }
            for index, date in enumerate(dates)
        ]

        akshare_calls = []

        def fake_index_daily_em(symbol):
            akshare_calls.append(symbol)
            raise AssertionError("AkShare should only run after Tushare index_daily fails")

        fake_akshare = SimpleNamespace(stock_zh_index_daily_em=fake_index_daily_em)
        with patch.dict(sys.modules, {"akshare": fake_akshare}), \
             patch.object(zhongshu_runtime, "fetch_tushare_daily_price_bars", return_value=rows, create=True) as tushare_mock, \
             patch.object(zhongshu_runtime, "fetch_daily_price_bars") as fast_mock, \
             patch.object(zhongshu_runtime, "_load_iwencai_index_dataframe") as iwencai_mock:
            result = analyze_market_zhongshu(
                index_code="sh000001",
                recent_days=120,
                target_date="2026-04-27",
                use_chanlun_confirmation=False,
                print_fn=lambda *args, **kwargs: None,
            )

        self.assertTrue(result["success"])
        self.assertEqual(result["data_source"], "tushare.index_daily")
        self.assertEqual(result["today_date"], "2026-04-27")
        self.assertEqual(akshare_calls, [])
        self.assertTrue(tushare_mock.call_args.kwargs["is_index"])
        fast_mock.assert_not_called()
        iwencai_mock.assert_not_called()

    def test_analyze_market_zhongshu_falls_back_to_fast_index_runtime_without_calling_iwencai(self):
        bars = [
            {"date": "2026-04-15", "open": 99, "high": 105, "low": 95, "close": 100, "volume": 1, "amount": 0},
            {"date": "2026-04-16", "open": 100, "high": 104, "low": 96, "close": 101, "volume": 1, "amount": 0},
            {"date": "2026-04-17", "open": 101, "high": 103, "low": 97, "close": 100, "volume": 1, "amount": 0},
            {"date": "2026-04-18", "open": 100, "high": 104, "low": 96, "close": 102, "volume": 1, "amount": 0},
            {"date": "2026-04-21", "open": 101, "high": 105, "low": 95, "close": 103, "volume": 1, "amount": 0},
            {"date": "2026-04-22", "open": 103, "high": 108, "low": 102, "close": 107, "volume": 1, "amount": 0},
        ]

        with patch.dict(sys.modules, {"akshare": SimpleNamespace()}), \
             patch.object(zhongshu_runtime, "fetch_tushare_daily_price_bars", return_value=[], create=True), \
             patch.object(zhongshu_runtime, "_load_iwencai_index_dataframe") as iwencai_mock, \
             patch.object(zhongshu_runtime, "fetch_daily_price_bars", return_value=bars):
            result = analyze_market_zhongshu(
                index_code="sh000001",
                target_date="2026-04-22",
                use_chanlun_confirmation=False,
                print_fn=lambda *args, **kwargs: None,
            )

        iwencai_mock.assert_not_called()
        self.assertTrue(result["success"])
        self.assertEqual(result["data_source"], "fast_index_runtime")
        self.assertEqual(result["signal"]["comparison_result"], "突破")

    def test_analyze_market_zhongshu_reports_skill_version_low_when_fast_index_is_unavailable(self):
        logs = []

        with patch.dict(sys.modules, {"akshare": SimpleNamespace()}), \
             patch.object(zhongshu_runtime, "fetch_tushare_daily_price_bars", return_value=[], create=True), \
             patch.object(zhongshu_runtime, "fetch_daily_price_bars", return_value=[]):
            result = analyze_market_zhongshu(
                index_code="sh000001",
                target_date="2026-04-22",
                urlopen_fn=_raise_skill_version_low,
                use_chanlun_confirmation=False,
                print_fn=logs.append,
            )

        self.assertFalse(result["success"])
        self.assertTrue(any("Skill 版本过低" in line for line in logs))
        self.assertFalse(any("HTTP Error 401" in line for line in logs))

    def test_analyze_market_zhongshu_opt_out_skips_default_minute_fetch(self):
        df = pd.DataFrame(
            [
                {"date": "2026-04-15", "open": 99, "high": 105, "low": 95, "close": 100, "volume": 1},
                {"date": "2026-04-16", "open": 100, "high": 104, "low": 96, "close": 101, "volume": 1},
                {"date": "2026-04-17", "open": 101, "high": 103, "low": 97, "close": 100, "volume": 1},
                {"date": "2026-04-20", "open": 100, "high": 104, "low": 96, "close": 102, "volume": 1},
                {"date": "2026-04-21", "open": 101, "high": 105, "low": 95, "close": 103, "volume": 1},
                {"date": "2026-04-22", "open": 103, "high": 108, "low": 102, "close": 107, "volume": 1},
            ]
        )

        with patch.object(zhongshu_runtime, "fetch_index_minute_bars", side_effect=AssertionError("minute fetch called")) as minute_mock:
            result = analyze_market_zhongshu(
                target_date="2026-04-22",
                fetch_dataframe=lambda **kwargs: (df, "test_feed"),
                use_chanlun_confirmation=False,
                print_fn=lambda *args, **kwargs: None,
            )

        self.assertTrue(result["success"])
        self.assertEqual(result["daily_structure_candidates"], [])
        self.assertIsNone(result["daily_structure_current"])
        self.assertEqual(result["chanlun_60m_structures"], [])
        self.assertEqual(result["chanlun_confirmation"], {})
        minute_mock.assert_not_called()

    def test_analyze_market_zhongshu_default_chanlun_path_does_not_require_minutes(self):
        df = pd.DataFrame(
            [
                {"date": "2026-04-14", "open": 100, "high": 102, "low": 98, "close": 100, "volume": 1, "amount": 1},
                {"date": "2026-04-15", "open": 100, "high": 112, "low": 99, "close": 110, "volume": 1, "amount": 1},
                {"date": "2026-04-16", "open": 110, "high": 111, "low": 100, "close": 101, "volume": 1, "amount": 1},
                {"date": "2026-04-17", "open": 101, "high": 110, "low": 100, "close": 109, "volume": 1, "amount": 1},
                {"date": "2026-04-27", "open": 109, "high": 112, "low": 104, "close": 108, "volume": 1, "amount": 1},
            ]
        )

        result = analyze_market_zhongshu(
            target_date="2026-04-27",
            fetch_dataframe=lambda **kwargs: (df, "test_feed"),
            use_chanlun_confirmation=True,
            fetch_minute_bars=lambda **kwargs: (_ for _ in ()).throw(AssertionError("minute fetch called")),
            print_fn=lambda *args, **kwargs: None,
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["chanlun_confirmation"]["confirmation_status"], "not_requested")
        self.assertEqual(result["chanlun_60m_structures"], [])

    def test_analyze_market_zhongshu_insufficient_60m_history_keeps_action_conservative(self):
        dates = pd.bdate_range(end="2026-04-27", periods=21)
        rows = []
        for index, date in enumerate(dates):
            is_today = index == len(dates) - 1
            rows.append(
                {
                    "date": date.strftime("%Y-%m-%d"),
                    "open": 4050,
                    "high": 4125 if is_today else 4114.84,
                    "low": 4100 if is_today else 3992.41,
                    "close": 4120 if is_today else 4050,
                    "volume": 1,
                    "amount": 1,
                }
            )
        df = pd.DataFrame(rows)

        result = analyze_market_zhongshu(
            target_date="2026-04-27",
            fetch_dataframe=lambda **kwargs: (df, "test_feed"),
            fetch_minute_bars=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("minute unavailable")),
            use_hybrid_confirmation=True,
            print_fn=lambda *args, **kwargs: None,
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["chanlun_confirmation"]["confirmation_status"], "data_insufficient")
        self.assertIn("60分钟确认", result["signal"]["status"])
        self.assertEqual(result["signal"]["action"], "只观察，等结构确认补齐")
        self.assertNotEqual(result["signal"]["action"], "积极做多")

    def test_analyze_market_zhongshu_exposes_chanlun_confirmation_contract(self):
        daily_rows = [
            {"date": "2026-04-14", "open": 100, "high": 102, "low": 98, "close": 100, "volume": 1, "amount": 1},
            {"date": "2026-04-15", "open": 100, "high": 112, "low": 99, "close": 110, "volume": 1, "amount": 1},
            {"date": "2026-04-16", "open": 110, "high": 111, "low": 100, "close": 101, "volume": 1, "amount": 1},
            {"date": "2026-04-17", "open": 101, "high": 110, "low": 100, "close": 109, "volume": 1, "amount": 1},
            {"date": "2026-04-27", "open": 109, "high": 112, "low": 104, "close": 108, "volume": 1, "amount": 1},
        ]
        df = pd.DataFrame(daily_rows)

        result = analyze_market_zhongshu(
            target_date="2026-04-27",
            fetch_dataframe=lambda **kwargs: (df, "test_feed"),
            fetch_minute_bars=lambda **kwargs: {
                "success": True,
                "status": "success",
                "bars": [
                    {"datetime": "2026-04-14 10:30:00", "date": "2026-04-14", "high": 4100, "low": 4000, "close": 4050},
                    {"datetime": "2026-04-14 14:00:00", "date": "2026-04-14", "high": 4090, "low": 4010, "close": 4040},
                    {"datetime": "2026-04-15 10:30:00", "date": "2026-04-15", "high": 4080, "low": 4020, "close": 4050},
                    {"datetime": "2026-04-15 14:00:00", "date": "2026-04-15", "high": 4095, "low": 4015, "close": 4035},
                ],
            },
            use_hybrid_confirmation=True,
            print_fn=lambda *args, **kwargs: None,
        )

        self.assertEqual(result["daily_structure_current"]["candidate_status"], "confirmed_platform")
        self.assertEqual(result["daily_structure_current"]["kline_count"], 3)
        self.assertNotIn("required_kline_count", result["daily_structure_current"])
        self.assertEqual(result["chanlun_confirmation"]["confirmation_status"], "confirmed_daily_level_zhongshu")
        self.assertNotIn("/20", result["signal"]["status"])

    def test_analyze_market_zhongshu_aligns_daily_candidate_with_forming_current_zone(self):
        rows = [
            {"date": "2026-04-14", "open": 100, "high": 102, "low": 98, "close": 100, "volume": 1, "amount": 1},
            {"date": "2026-04-15", "open": 100, "high": 112, "low": 99, "close": 110, "volume": 1, "amount": 1},
            {"date": "2026-04-16", "open": 110, "high": 111, "low": 100, "close": 101, "volume": 1, "amount": 1},
            {"date": "2026-04-17", "open": 101, "high": 110, "low": 100, "close": 109, "volume": 1, "amount": 1},
            {"date": "2026-04-27", "open": 109, "high": 112, "low": 104, "close": 108, "volume": 1, "amount": 1},
        ]
        df = pd.DataFrame(rows)

        result = analyze_market_zhongshu(
            target_date="2026-04-27",
            fetch_dataframe=lambda **kwargs: (df, "test_feed"),
            fetch_minute_bars=lambda **kwargs: {
                "success": True,
                "status": "success",
                "bars": [
                    {"datetime": "2026-04-14 10:30:00", "date": "2026-04-14", "high": 4100, "low": 4000, "close": 4050},
                    {"datetime": "2026-04-14 14:00:00", "date": "2026-04-14", "high": 4090, "low": 4010, "close": 4040},
                    {"datetime": "2026-04-15 10:30:00", "date": "2026-04-15", "high": 4080, "low": 4020, "close": 4050},
                    {"datetime": "2026-04-15 14:00:00", "date": "2026-04-15", "high": 4095, "low": 4015, "close": 4035},
                ],
            },
            use_hybrid_confirmation=True,
            print_fn=lambda *args, **kwargs: None,
        )

        current = result["daily_structure_current"]
        self.assertEqual(current["start_date"], "2026-04-14")
        self.assertEqual(current["end_date"], "2026-04-16")
        self.assertEqual(current["kline_count"], 3)
        self.assertNotIn("required_kline_count", current)
        self.assertEqual(current["candidate_status"], "confirmed_platform")
        self.assertEqual(result["chanlun_confirmation"]["confirmation_status"], "confirmed_daily_level_zhongshu")

        not_confirmed = analyze_market_zhongshu(
            target_date="2026-04-27",
            fetch_dataframe=lambda **kwargs: (df, "test_feed"),
            fetch_minute_bars=lambda **kwargs: {
                "success": True,
                "status": "success",
                "bars": [
                    {"datetime": "2026-04-14 10:30:00", "date": "2026-04-14", "high": 4100, "low": 4000, "close": 4050},
                    {"datetime": "2026-04-14 14:00:00", "date": "2026-04-14", "high": 3990, "low": 3900, "close": 3940},
                    {"datetime": "2026-04-15 10:30:00", "date": "2026-04-15", "high": 4200, "low": 4150, "close": 4180},
                    {"datetime": "2026-04-15 14:00:00", "date": "2026-04-15", "high": 4160, "low": 4150, "close": 4160},
                ],
            },
            use_hybrid_confirmation=True,
            print_fn=lambda *args, **kwargs: None,
        )
        self.assertEqual(not_confirmed["chanlun_confirmation"]["confirmation_status"], "not_confirmed")
        self.assertIn("60分钟确认：not_confirmed", not_confirmed["signal"]["status"])
        self.assertNotIn("当前中枢形成中", not_confirmed["signal"]["status"])


if __name__ == "__main__":
    unittest.main()
