import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from market_data import minute_price_runtime


class MinutePriceRuntimeTest(unittest.TestCase):
    def test_normalize_index_minute_symbol_handles_common_index_forms(self):
        cases = {
            "sh.000001": "sh000001",
            "sz.399001": "sz399001",
            "sh000001": "sh000001",
            "sz399001": "sz399001",
            "000001": "sh000001",
            "399001": "sz399001",
            "399006": "sz399006",
        }

        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(minute_price_runtime.normalize_index_minute_symbol(raw), expected)

    def test_normalize_minute_frame_outputs_sorted_float_bars(self):
        frame = pd.DataFrame(
            [
                {
                    "day": "2026-04-27 10:30:00",
                    "open": "4000.1",
                    "high": "4010.2",
                    "low": "3990.3",
                    "close": "4005.4",
                    "volume": "100",
                    "amount": "200",
                },
                {
                    "day": "2026-04-27 09:30:00",
                    "open": "3990",
                    "high": "4001",
                    "low": "3988",
                    "close": "4000",
                    "volume": "80",
                    "amount": "180",
                },
            ]
        )

        bars = minute_price_runtime.normalize_minute_bars(frame)

        self.assertEqual([item["datetime"] for item in bars], ["2026-04-27 09:30:00", "2026-04-27 10:30:00"])
        self.assertEqual(bars[0]["open"], 3990.0)
        self.assertEqual(bars[1]["amount"], 200.0)

    def test_fetch_index_minute_bars_uses_sina_for_shanghai_index(self):
        calls = []

        def fake_stock_zh_a_minute(symbol, period, adjust):
            calls.append((symbol, period, adjust))
            return pd.DataFrame(
                [
                    {
                        "day": "2026-04-27 09:30:00",
                        "open": "3990",
                        "high": "4001",
                        "low": "3988",
                        "close": "4000",
                        "volume": "80",
                        "amount": "180",
                    }
                ]
            )

        fake_akshare = SimpleNamespace(stock_zh_a_minute=fake_stock_zh_a_minute)
        with patch.dict(sys.modules, {"akshare": fake_akshare}):
            result = minute_price_runtime.fetch_index_minute_bars("sh.000001", period="60", cache_dir=None)

        self.assertEqual(calls, [("sh000001", "60", "")])
        self.assertEqual(result["source"], "akshare.stock_zh_a_minute")
        self.assertEqual(result["bars"][0]["datetime"], "2026-04-27 09:30:00")

    def test_fetch_index_minute_bars_writes_and_reuses_cache(self):
        calls = []

        def fake_stock_zh_a_minute(symbol, period, adjust):
            calls.append(symbol)
            return pd.DataFrame(
                [
                    {
                        "day": "2026-04-27 09:30:00",
                        "open": "3990",
                        "high": "4001",
                        "low": "3988",
                        "close": "4000",
                        "volume": "80",
                        "amount": "180",
                    }
                ]
            )

        fake_akshare = SimpleNamespace(stock_zh_a_minute=fake_stock_zh_a_minute)
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(sys.modules, {"akshare": fake_akshare}):
            first = minute_price_runtime.fetch_index_minute_bars("sh.000001", period="60", cache_dir=tmpdir)
            second = minute_price_runtime.fetch_index_minute_bars("sh.000001", period="60", cache_dir=tmpdir)

        self.assertEqual(len(calls), 1)
        self.assertEqual(first["bars"], second["bars"])
        self.assertEqual(second["source"], "cache")

    def test_fetch_index_minute_bars_returns_live_bars_when_cache_write_fails(self):
        def fake_stock_zh_a_minute(symbol, period, adjust):
            return pd.DataFrame(
                [
                    {
                        "day": "2026-04-27 09:30:00",
                        "open": "3990",
                        "high": "4001",
                        "low": "3988",
                        "close": "4000",
                        "volume": "80",
                        "amount": "180",
                    }
                ]
            )

        fake_akshare = SimpleNamespace(stock_zh_a_minute=fake_stock_zh_a_minute)
        with patch.dict(sys.modules, {"akshare": fake_akshare}), patch.object(
            minute_price_runtime,
            "_write_cache",
            side_effect=OSError("cache unwritable"),
        ):
            result = minute_price_runtime.fetch_index_minute_bars("sh.000001", period="60", cache_dir="/invalid/cache")

        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["source"], "akshare.stock_zh_a_minute")
        self.assertEqual(result["bars"][0]["datetime"], "2026-04-27 09:30:00")

    def test_fetch_index_minute_bars_returns_degraded_status_on_error(self):
        def fake_stock_zh_a_minute(symbol, period, adjust):
            raise RuntimeError("network down")

        fake_akshare = SimpleNamespace(stock_zh_a_minute=fake_stock_zh_a_minute)
        with patch.dict(sys.modules, {"akshare": fake_akshare}):
            result = minute_price_runtime.fetch_index_minute_bars("sh.000001", period="60", cache_dir=None)

        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "minute_fetch_failed")
        self.assertIn("network down", result["error"])


if __name__ == "__main__":
    unittest.main()
