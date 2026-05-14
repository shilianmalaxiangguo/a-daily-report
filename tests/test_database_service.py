import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class DatabaseServiceTest(unittest.TestCase):
    def test_database_service_wraps_cloudflare_free_repository(self):
        from storage.database_service import DatabaseService

        rows = [
            {
                "trade_date": "2026-05-12",
                "ts_code": "000001.SZ",
                "stock_code": "000001",
                "market": "SZ",
                "name": "平安银行",
                "open": 10,
                "high": 11,
                "low": 9,
                "close": 10.5,
                "pct_chg": 5,
                "vol": 1000,
                "amount_yi": 2.5,
            }
        ]

        with tempfile.TemporaryDirectory() as tmp:
            service = DatabaseService.sqlite_d1_compatible(Path(tmp) / "daily.db")
            run_id = service.save_provider_source_run(
                {
                    "trade_date": "2026-05-12",
                    "provider": "tushare",
                    "endpoint": "daily",
                    "status": "success",
                    "row_count": 1,
                }
            )

            self.assertEqual(service.upsert_stock_daily_quotes_recent(rows, source_run_id=run_id), 1)
            total = service.rebuild_market_daily_total("2026-05-12", source_run_id=run_id)
            queried_total = service.query_market_daily_total("2026-05-12")
            ranks = service.rebuild_turnover_rank_daily("2026-05-12", rank_limit=50, source_run_id=run_id)
            series = service.query_top_turnover_share_series("2026-05-12", window_days=30, limit=50)

            self.assertEqual(total["total_amount_yi"], 2.5)
            self.assertEqual(queried_total["total_amount_yi"], 2.5)
            self.assertEqual(queried_total["stock_count"], 1)
            self.assertEqual(len(ranks), 1)
            self.assertEqual(series["rows"][0]["share_pct"], 100.0)


if __name__ == "__main__":
    unittest.main()
