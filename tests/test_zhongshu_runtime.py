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
    def test_build_zhongshu_structure_requires_20_klines_except_current_tail(self):
        dates = pd.bdate_range(start="2026-03-02", periods=27)
        rows = []
        for index, date in enumerate(dates):
            if index < 6:
                high, low, close = 105, 95, 100
            else:
                high, low, close = 132, 124, 128
            rows.append(
                {
                    "date": date.strftime("%Y-%m-%d"),
                    "open": close,
                    "high": high,
                    "low": low,
                    "close": close,
                    "volume": 1,
                }
            )
        df = pd.DataFrame(rows)

        structure_segments, zhongshu_list = build_zhongshu_structure(df, min_zhongshu_klines=20)

        self.assertEqual(structure_segments[0]["segment_type"], "connector")
        self.assertEqual(structure_segments[0]["kline_count"], 6)
        self.assertEqual(len(zhongshu_list), 1)
        self.assertEqual(zhongshu_list[0]["kline_count"], 21)
        self.assertEqual(zhongshu_list[0]["confirmation_status"], "confirmed")

    def test_analyze_market_zhongshu_marks_short_latest_zone_as_forming_current(self):
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
            print_fn=lambda *args, **kwargs: None,
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["current_zhongshu"]["confirmation_status"], "forming")
        self.assertEqual(result["current_zhongshu"]["kline_count"], 6)
        self.assertEqual(result["current_zhongshu"]["required_kline_count"], 20)
        self.assertIn("6/20", result["signal"]["status"])
        self.assertIn("观察", result["signal"]["action"])

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
            print_fn=lambda *args, **kwargs: None,
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["data_source"], "test_feed")
        self.assertEqual(result["signal"]["signal_type"], "大盘突破")
        self.assertEqual(result["signal"]["comparison_result"], "突破")
        self.assertEqual(len(result["zhongshu_list"]), 1)
        self.assertEqual(result["today_date"], "2026-04-22")

    def test_analyze_market_zhongshu_uses_akshare_primary_for_120_day_window(self):
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

        def fake_index_daily_em(symbol):
            self.assertEqual(symbol, "sh000001")
            return pd.DataFrame(rows)

        fake_akshare = SimpleNamespace(stock_zh_index_daily_em=fake_index_daily_em)
        with patch.dict(sys.modules, {"akshare": fake_akshare}), \
             patch.object(zhongshu_runtime, "fetch_daily_price_bars") as fast_mock, \
             patch.object(zhongshu_runtime, "_load_iwencai_index_dataframe") as iwencai_mock:
            df, source = zhongshu_runtime._load_akshare_index_dataframe(
                "sh000001",
                recent_days=120,
                target_date="2026-04-27",
            )
            result = analyze_market_zhongshu(
                index_code="sh000001",
                recent_days=120,
                target_date="2026-04-27",
                print_fn=lambda *args, **kwargs: None,
            )

        self.assertEqual(source, "akshare.stock_zh_index_daily_em")
        self.assertEqual(len(df), 121)
        self.assertEqual(df.iloc[-1]["date"], "2026-04-27")
        self.assertTrue(result["success"])
        self.assertEqual(result["data_source"], "akshare.stock_zh_index_daily_em")
        self.assertEqual(result["today_date"], "2026-04-27")
        fast_mock.assert_not_called()
        iwencai_mock.assert_not_called()

    def test_analyze_market_zhongshu_uses_fast_index_runtime_primary_without_calling_iwencai(self):
        bars = [
            {"date": "2026-04-15", "open": 99, "high": 105, "low": 95, "close": 100, "volume": 1, "amount": 0},
            {"date": "2026-04-16", "open": 100, "high": 104, "low": 96, "close": 101, "volume": 1, "amount": 0},
            {"date": "2026-04-17", "open": 101, "high": 103, "low": 97, "close": 100, "volume": 1, "amount": 0},
            {"date": "2026-04-18", "open": 100, "high": 104, "low": 96, "close": 102, "volume": 1, "amount": 0},
            {"date": "2026-04-21", "open": 101, "high": 105, "low": 95, "close": 103, "volume": 1, "amount": 0},
            {"date": "2026-04-22", "open": 103, "high": 108, "low": 102, "close": 107, "volume": 1, "amount": 0},
        ]

        with patch.dict(sys.modules, {"akshare": SimpleNamespace()}), \
             patch.object(zhongshu_runtime, "_load_iwencai_index_dataframe") as iwencai_mock, \
             patch.object(zhongshu_runtime, "fetch_daily_price_bars", return_value=bars):
            result = analyze_market_zhongshu(
                index_code="sh000001",
                target_date="2026-04-22",
                print_fn=lambda *args, **kwargs: None,
            )

        iwencai_mock.assert_not_called()
        self.assertTrue(result["success"])
        self.assertEqual(result["data_source"], "fast_index_runtime")
        self.assertEqual(result["signal"]["comparison_result"], "突破")

    def test_analyze_market_zhongshu_reports_skill_version_low_when_fast_index_is_unavailable(self):
        logs = []

        with patch.dict(sys.modules, {"akshare": SimpleNamespace()}), \
             patch.object(zhongshu_runtime, "fetch_daily_price_bars", return_value=[]):
            result = analyze_market_zhongshu(
                index_code="sh000001",
                target_date="2026-04-22",
                urlopen_fn=_raise_skill_version_low,
                print_fn=logs.append,
            )

        self.assertFalse(result["success"])
        self.assertTrue(any("Skill 版本过低" in line for line in logs))
        self.assertFalse(any("HTTP Error 401" in line for line in logs))

    def test_analyze_market_zhongshu_exposes_chanlun_confirmation_contract(self):
        daily_rows = [
            {"date": "2026-04-14", "open": 4050, "high": 4114.84, "low": 3992.41, "close": 4050, "volume": 1, "amount": 1},
            {"date": "2026-04-15", "open": 4050, "high": 4114.84, "low": 3992.41, "close": 4051, "volume": 1, "amount": 1},
            {"date": "2026-04-16", "open": 4050, "high": 4114.84, "low": 3992.41, "close": 4052, "volume": 1, "amount": 1},
            {"date": "2026-04-17", "open": 4050, "high": 4114.84, "low": 3992.41, "close": 4053, "volume": 1, "amount": 1},
            {"date": "2026-04-20", "open": 4050, "high": 4114.84, "low": 3992.41, "close": 4054, "volume": 1, "amount": 1},
            {"date": "2026-04-21", "open": 4050, "high": 4114.84, "low": 3992.41, "close": 4055, "volume": 1, "amount": 1},
            {"date": "2026-04-22", "open": 4050, "high": 4114.84, "low": 3992.41, "close": 4056, "volume": 1, "amount": 1},
            {"date": "2026-04-23", "open": 4050, "high": 4114.84, "low": 3992.41, "close": 4057, "volume": 1, "amount": 1},
            {"date": "2026-04-24", "open": 4050, "high": 4114.84, "low": 3992.41, "close": 4058, "volume": 1, "amount": 1},
            {"date": "2026-04-27", "open": 4050, "high": 4114.84, "low": 3992.41, "close": 4086.34, "volume": 1, "amount": 1},
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
                    {"datetime": "2026-04-17 14:00:00", "date": "2026-04-17", "high": 4090, "low": 4010, "close": 4040},
                    {"datetime": "2026-04-24 14:00:00", "date": "2026-04-24", "high": 4080, "low": 4020, "close": 4050},
                ],
            },
            print_fn=lambda *args, **kwargs: None,
        )

        self.assertEqual(result["daily_structure_current"]["candidate_status"], "daily_candidate_forming")
        self.assertEqual(result["daily_structure_current"]["kline_count"], 9)
        self.assertEqual(result["chanlun_confirmation"]["confirmation_status"], "forming_daily_level_zhongshu")
        self.assertIn("日K候选", result["signal"]["status"])


if __name__ == "__main__":
    unittest.main()
