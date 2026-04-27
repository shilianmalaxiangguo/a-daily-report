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
from decision.zhongshu_runtime import analyze_market_zhongshu


def _raise_skill_version_low(*args, **kwargs):
    raise urllib.error.HTTPError(
        url="https://openapi.iwencai.com/v1/query2data",
        code=401,
        msg="Unauthorized",
        hdrs={},
        fp=BytesIO("当前 Skill 版本过低，本次请求无法执行。".encode("utf-8")),
    )


class ZhongshuRuntimeTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
