import sys
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
        with patch.dict("os.environ", {}, clear=True), patch.dict(sys.modules, {"akshare": fake_akshare}), patch.object(
            minute_price_runtime,
            "fetch_tushare_minute_bars",
            return_value=tushare_bars,
            create=True,
        ) as tushare_mock:
            result = minute_price_runtime.fetch_index_minute_bars("sh.000001", period="60", target_date="2026-04-27")

        tushare_mock.assert_called_once_with("sh.000001", period="60", is_index=True, target_date="2026-04-27")
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
        with patch.dict("os.environ", {}, clear=True), patch.dict(sys.modules, {"akshare": fake_akshare}), patch.object(
            minute_price_runtime,
            "fetch_tushare_minute_bars",
            return_value=[],
            create=True,
        ):
            result = minute_price_runtime.fetch_index_minute_bars("sh.000001", period="60", target_date="2026-04-27")

        self.assertEqual(calls, [("sh000001", "60", "")])
        self.assertEqual(result["source"], "akshare.stock_zh_a_minute")

    def test_fetch_index_minute_bars_does_not_write_local_json_cache(self):
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
        with patch.dict("os.environ", {}, clear=True), patch.dict(sys.modules, {"akshare": fake_akshare}):
            first = minute_price_runtime.fetch_index_minute_bars("sh.000001", period="60", target_date="2026-04-27")
            second = minute_price_runtime.fetch_index_minute_bars("sh.000001", period="60", target_date="2026-04-27")

        self.assertEqual(len(calls), 2)
        self.assertEqual(first["source"], "akshare.stock_zh_a_minute")
        self.assertEqual(second["source"], "akshare.stock_zh_a_minute")

    def test_fetch_index_minute_bars_uses_postgres_structured_table_when_configured(self):
        class StubService:
            def is_postgres_backed(self):
                return True

            def query_index_minute_bars(self, index_code, target_date, *, period="60"):
                self.last_get = (index_code, target_date, period)
                return [
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

        service = StubService()

        class StubDatabaseService:
            @classmethod
            def from_environment(cls):
                return service

        with patch.object(
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
            side_effect=AssertionError("live fetch should not run when PostgreSQL rows exist"),
        ):
            result = minute_price_runtime.fetch_index_minute_bars(
                "sh.000001",
                period="60",
                target_date="2026-04-27",
            )

        self.assertEqual(service.last_get, ("sh000001", "2026-04-27", "60"))
        self.assertEqual(result["source"], "postgresql.index_minute_bars")
        self.assertEqual(result["bars"][0]["datetime"], "2026-04-27 09:30:00")

    def test_fetch_index_minute_bars_writes_postgres_structured_rows_without_json_file(self):
        class StubService:
            def __init__(self):
                self.saved = []

            def is_postgres_backed(self):
                return True

            def query_index_minute_bars(self, index_code, target_date, *, period="60"):
                return []

            def upsert_index_minute_bars(self, index_code, trade_date, period, rows, *, source_policy="", source_run_id=0):
                self.saved.append((index_code, trade_date, period, rows, source_policy, source_run_id))
                return len(rows)

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
        with patch.object(
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
            result = minute_price_runtime.fetch_index_minute_bars(
                "sh.000001",
                period="60",
                target_date="2026-04-27",
            )

        self.assertEqual(result["source"], "tushare.stock_mins")
        self.assertEqual(len(service.saved), 1)
        self.assertEqual(service.saved[0][0:3], ("sh000001", "2026-04-27", "60"))
        self.assertEqual(service.saved[0][3], tushare_bars)

    def test_fetch_index_minute_bars_filters_live_rows_to_target_date_before_saving(self):
        class StubService:
            def __init__(self):
                self.saved = []

            def is_postgres_backed(self):
                return True

            def query_index_minute_bars(self, index_code, target_date, *, period="60"):
                return []

            def upsert_index_minute_bars(self, index_code, trade_date, period, rows, *, source_policy="", source_run_id=0):
                self.saved.append((index_code, trade_date, period, rows, source_policy, source_run_id))
                return len(rows)

        service = StubService()

        class StubDatabaseService:
            @classmethod
            def from_environment(cls):
                return service

        def fake_stock_zh_a_minute(symbol, period, adjust):
            return pd.DataFrame(
                [
                    {
                        "day": "2026-04-26 09:30:00",
                        "open": "3900",
                        "high": "3910",
                        "low": "3890",
                        "close": "3905",
                        "volume": "70",
                        "amount": "170",
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

        fake_akshare = SimpleNamespace(stock_zh_a_minute=fake_stock_zh_a_minute)
        with patch.dict(sys.modules, {"akshare": fake_akshare}), patch.object(
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
            return_value=[],
        ):
            result = minute_price_runtime.fetch_index_minute_bars(
                "sh.000001",
                period="60",
                target_date="2026-04-27",
            )

        self.assertEqual([row["date"] for row in result["bars"]], ["2026-04-27"])
        self.assertEqual([row["date"] for row in service.saved[0][3]], ["2026-04-27"])

    def test_postgres_only_fetch_index_minute_bars_returns_missing_without_database(self):
        with patch.dict(
            "os.environ",
            {"A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME": "1"},
            clear=True,
        ), patch.object(
            minute_price_runtime,
            "fetch_tushare_minute_bars",
            side_effect=AssertionError("live fetch must not run in postgres-only mode"),
        ):
            result = minute_price_runtime.fetch_index_minute_bars(
                "sh.000001",
                period="60",
                target_date="2026-04-27",
            )

        self.assertFalse(result["success"])
        self.assertEqual(result["source"], "postgresql.index_minute_bars")
        self.assertEqual(result["status"], "postgres_minute_missing")

    def test_fetch_index_minute_bars_returns_live_bars_and_marks_postgres_write_failure(self):
        class StubService:
            def is_postgres_backed(self):
                return True

            def query_index_minute_bars(self, index_code, target_date, *, period="60"):
                return []

            def upsert_index_minute_bars(self, index_code, trade_date, period, rows, *, source_policy="", source_run_id=0):
                raise OSError("postgres write failed")

        service = StubService()

        class StubDatabaseService:
            @classmethod
            def from_environment(cls):
                return service

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
            return_value=[],
        ):
            result = minute_price_runtime.fetch_index_minute_bars(
                "sh.000001",
                period="60",
                target_date="2026-04-27",
            )

        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["source"], "akshare.stock_zh_a_minute")
        self.assertEqual(result["postgres_write_status"], "failed")
        self.assertIn("postgres write failed", result["postgres_write_error"])
        self.assertEqual(result["bars"][0]["datetime"], "2026-04-27 09:30:00")

    def test_fetch_index_minute_bars_returns_degraded_status_on_error(self):
        def fake_stock_zh_a_minute(symbol, period, adjust):
            raise RuntimeError("network down")

        fake_akshare = SimpleNamespace(stock_zh_a_minute=fake_stock_zh_a_minute)
        with patch.dict("os.environ", {}, clear=True), patch.dict(sys.modules, {"akshare": fake_akshare}):
            result = minute_price_runtime.fetch_index_minute_bars(
                "sh.000001",
                period="60",
                target_date="2026-04-27",
            )

        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "minute_fetch_failed")
        self.assertIn("network down", result["error"])


if __name__ == "__main__":
    unittest.main()
