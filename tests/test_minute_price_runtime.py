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

    def test_fetch_index_minute_bars_uses_tushare_before_akshare(self):
        akshare_calls = []

        def fake_stock_zh_a_minute(symbol, period, adjust):
            akshare_calls.append((symbol, period, adjust))
            raise AssertionError("AkShare should only run after Tushare stock_mins fails")

        fake_akshare = SimpleNamespace(stock_zh_a_minute=fake_stock_zh_a_minute)
        tushare_bars = [
            {
                "datetime": "2026-04-27 09:30:00",
                "date": "2026-04-27",
                "time": "09:30:00",
                "open": 3990.0,
                "high": 4001.0,
                "low": 3988.0,
                "close": 4000.0,
                "volume": 80.0,
                "amount": 180.0,
            }
        ]
        with patch.dict(sys.modules, {"akshare": fake_akshare}), patch.object(
            minute_price_runtime,
            "fetch_tushare_minute_bars",
            return_value=tushare_bars,
            create=True,
        ) as tushare_mock:
            result = minute_price_runtime.fetch_index_minute_bars("sh.000001", period="60", cache_dir=None)

        tushare_mock.assert_called_once_with("sh.000001", period="60", is_index=True, target_date=None)
        self.assertEqual(akshare_calls, [])
        self.assertEqual(result["source"], "tushare.stock_mins")
        self.assertEqual(result["bars"][0]["datetime"], "2026-04-27 09:30:00")

    def test_fetch_index_minute_bars_falls_back_to_akshare_when_tushare_empty(self):
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
        with patch.dict(sys.modules, {"akshare": fake_akshare}), patch.object(
            minute_price_runtime,
            "fetch_tushare_minute_bars",
            return_value=[],
            create=True,
        ):
            result = minute_price_runtime.fetch_index_minute_bars("sh.000001", period="60", cache_dir=None)

        self.assertEqual(calls, [("sh000001", "60", "")])
        self.assertEqual(result["source"], "akshare.stock_zh_a_minute")

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

    def test_fetch_index_minute_bars_uses_postgres_runtime_cache_when_configured(self):
        cached_payload = {
            "success": True,
            "status": "success",
            "source": "tushare.stock_mins",
            "symbol": "sh000001",
            "period": "60",
            "bars": [
                {
                    "datetime": "2026-04-27 09:30:00",
                    "date": "2026-04-27",
                    "time": "09:30:00",
                    "open": 3990.0,
                    "high": 4001.0,
                    "low": 3988.0,
                    "close": 4000.0,
                    "volume": 80.0,
                    "amount": 180.0,
                }
            ],
        }

        class StubService:
            def is_postgres_backed(self):
                return True

            def get_runtime_cache_entry(self, namespace, cache_key, target_date):
                self.last_get = (namespace, cache_key, target_date)
                return {"payload": cached_payload, "source": "runtime_cache"}

        service = StubService()

        class StubDatabaseService:
            @classmethod
            def from_environment(cls):
                return service

        with tempfile.TemporaryDirectory() as tmpdir, patch.object(
            minute_price_runtime,
            "DatabaseService",
            StubDatabaseService,
            create=True,
        ), patch.dict(
            "os.environ",
            {"A_DAILY_REPORT_DATABASE_URL": "postgresql://unit/report"},
            clear=True,
        ), patch.object(
            minute_price_runtime,
            "fetch_tushare_minute_bars",
            side_effect=AssertionError("live fetch should not run when PostgreSQL cache has bars"),
        ):
            result = minute_price_runtime.fetch_index_minute_bars("sh.000001", period="60", cache_dir=tmpdir)

        self.assertEqual(service.last_get, ("minute_price", "sh000001:60", ""))
        self.assertEqual(result["source"], "cache")
        self.assertEqual(result["bars"], cached_payload["bars"])
        self.assertEqual(list(Path(tmpdir).glob("*.json")), [])

    def test_fetch_index_minute_bars_writes_postgres_runtime_cache_without_json_file(self):
        class StubService:
            def __init__(self):
                self.saved = []

            def is_postgres_backed(self):
                return True

            def get_runtime_cache_entry(self, namespace, cache_key, target_date):
                return None

            def set_runtime_cache_entry(self, namespace, cache_key, target_date, payload, *, source="", ttl_seconds=None):
                self.saved.append((namespace, cache_key, target_date, payload, source, ttl_seconds))
                return True

        service = StubService()

        class StubDatabaseService:
            @classmethod
            def from_environment(cls):
                return service

        tushare_bars = [
            {
                "datetime": "2026-04-27 09:30:00",
                "date": "2026-04-27",
                "time": "09:30:00",
                "open": 3990.0,
                "high": 4001.0,
                "low": 3988.0,
                "close": 4000.0,
                "volume": 80.0,
                "amount": 180.0,
            }
        ]
        with tempfile.TemporaryDirectory() as tmpdir, patch.object(
            minute_price_runtime,
            "DatabaseService",
            StubDatabaseService,
            create=True,
        ), patch.dict(
            "os.environ",
            {"A_DAILY_REPORT_DATABASE_URL": "postgresql://unit/report"},
            clear=True,
        ), patch.object(
            minute_price_runtime,
            "fetch_tushare_minute_bars",
            return_value=tushare_bars,
        ):
            result = minute_price_runtime.fetch_index_minute_bars("sh.000001", period="60", cache_dir=tmpdir)

        self.assertEqual(result["source"], "tushare.stock_mins")
        self.assertEqual(len(service.saved), 1)
        self.assertEqual(service.saved[0][0:3], ("minute_price", "sh000001:60", ""))
        self.assertEqual(service.saved[0][3]["bars"], tushare_bars)
        self.assertEqual(list(Path(tmpdir).glob("*.json")), [])

    def test_postgres_only_fetch_index_minute_bars_does_not_write_file_cache_without_database(self):
        tushare_bars = [
            {
                "datetime": "2026-04-27 09:30:00",
                "date": "2026-04-27",
                "time": "09:30:00",
                "open": 3990.0,
                "high": 4001.0,
                "low": 3988.0,
                "close": 4000.0,
                "volume": 80.0,
                "amount": 180.0,
            }
        ]
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(
            "os.environ",
            {"A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME": "1"},
            clear=True,
        ), patch.object(
            minute_price_runtime,
            "fetch_tushare_minute_bars",
            return_value=tushare_bars,
        ):
            result = minute_price_runtime.fetch_index_minute_bars("sh.000001", period="60", cache_dir=tmpdir)

        self.assertEqual(result["source"], "tushare.stock_mins")
        self.assertEqual(list(Path(tmpdir).glob("*.json")), [])

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
