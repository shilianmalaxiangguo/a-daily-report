import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import decision.zhongshu_runtime as zhongshu_runtime
from decision.zhongshu_runtime import analyze_market_zhongshu


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

    def test_analyze_market_zhongshu_uses_fast_index_runtime_when_iwencai_fails(self):
        bars = [
            {"date": "2026-04-15", "open": 99, "high": 105, "low": 95, "close": 100, "volume": 1, "amount": 0},
            {"date": "2026-04-16", "open": 100, "high": 104, "low": 96, "close": 101, "volume": 1, "amount": 0},
            {"date": "2026-04-17", "open": 101, "high": 103, "low": 97, "close": 100, "volume": 1, "amount": 0},
            {"date": "2026-04-18", "open": 100, "high": 104, "low": 96, "close": 102, "volume": 1, "amount": 0},
            {"date": "2026-04-21", "open": 101, "high": 105, "low": 95, "close": 103, "volume": 1, "amount": 0},
            {"date": "2026-04-22", "open": 103, "high": 108, "low": 102, "close": 107, "volume": 1, "amount": 0},
        ]

        with patch.object(zhongshu_runtime, "_load_iwencai_index_dataframe", side_effect=RuntimeError("iwencai boom")), \
             patch.object(zhongshu_runtime, "fetch_daily_price_bars", return_value=bars):
            result = analyze_market_zhongshu(
                index_code="sh000001",
                target_date="2026-04-22",
                print_fn=lambda *args, **kwargs: None,
            )

        self.assertTrue(result["success"])
        self.assertEqual(result["data_source"], "fast_index_runtime")
        self.assertEqual(result["signal"]["comparison_result"], "突破")


if __name__ == "__main__":
    unittest.main()
