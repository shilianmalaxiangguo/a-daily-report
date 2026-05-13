import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class CloudflareFreeDailyDbTest(unittest.TestCase):
    def _rows_for_date(self, trade_date, count=60):
        rows = []
        for index in range(count):
            market = "SH" if index % 2 == 0 else "SZ"
            code = f"{600000 + index:06d}" if market == "SH" else f"{index + 1:06d}"
            rows.append(
                {
                    "trade_date": trade_date,
                    "ts_code": f"{code}.{market}",
                    "stock_code": code,
                    "market": market,
                    "name": f"样本{index:02d}",
                    "open": 10.0,
                    "high": 10.5,
                    "low": 9.8,
                    "close": 10.2,
                    "pct_chg": 1.0,
                    "vol": 1000 + index,
                    "amount_yi": float(count - index),
                    "data_source": "tushare.daily",
                }
            )
        return rows

    def test_upsert_quotes_builds_market_totals_and_turnover_rank(self):
        from storage.cloudflare_free_daily_db import CloudflareFreeDailyDb

        with tempfile.TemporaryDirectory() as tmp:
            db = CloudflareFreeDailyDb(Path(tmp) / "daily.db")
            run_id = db.save_provider_source_run(
                {
                    "trade_date": "2026-05-12",
                    "provider": "tushare",
                    "endpoint": "daily",
                    "status": "success",
                    "row_count": 60,
                }
            )
            db.upsert_stock_daily_quotes_recent(self._rows_for_date("2026-05-12"), source_run_id=run_id)
            total = db.rebuild_market_daily_total("2026-05-12", source_run_id=run_id)
            ranks = db.rebuild_turnover_rank_daily("2026-05-12", rank_limit=50, source_run_id=run_id)

            self.assertEqual(total["market_scope"], "all_a")
            self.assertEqual(total["stock_count"], 60)
            self.assertAlmostEqual(total["total_amount_yi"], sum(range(1, 61)))
            self.assertEqual(len(ranks), 50)
            self.assertEqual(ranks[0]["rank_no"], 1)
            self.assertEqual(ranks[0]["amount_yi"], 60.0)
            self.assertAlmostEqual(ranks[0]["amount_share_pct"], 60.0 / sum(range(1, 61)) * 100)

    def test_query_top_turnover_share_series_uses_precomputed_ranks(self):
        from storage.cloudflare_free_daily_db import CloudflareFreeDailyDb

        with tempfile.TemporaryDirectory() as tmp:
            db = CloudflareFreeDailyDb(Path(tmp) / "daily.db")
            for day in range(1, 32):
                trade_date = f"2026-05-{day:02d}"
                run_id = db.save_provider_source_run(
                    {
                        "trade_date": trade_date,
                        "provider": "tushare",
                        "endpoint": "daily",
                        "status": "success",
                        "row_count": 60,
                    }
                )
                db.upsert_stock_daily_quotes_recent(self._rows_for_date(trade_date), source_run_id=run_id)
                db.rebuild_market_daily_total(trade_date, source_run_id=run_id)
                db.rebuild_turnover_rank_daily(trade_date, rank_limit=100, source_run_id=run_id)

            series = db.query_top_turnover_share_series("2026-05-31", window_days=30, limit=50)

            self.assertEqual(series["schema_version"], "cf-free-turnover-series/v1")
            self.assertEqual(series["query_window"]["end_date"], "2026-05-31")
            self.assertEqual(series["query_window"]["window_days"], 30)
            self.assertEqual(series["query_window"]["rank_limit"], 50)
            self.assertEqual(len(series["rows"]), 30)
            self.assertEqual(series["rows"][0]["trade_date"], "2026-05-02")
            self.assertEqual(series["rows"][-1]["trade_date"], "2026-05-31")
            self.assertAlmostEqual(series["rows"][-1]["top_amount_yi"], sum(range(11, 61)))
            self.assertAlmostEqual(series["rows"][-1]["market_amount_yi"], sum(range(1, 61)))
            self.assertAlmostEqual(
                series["rows"][-1]["share_pct"],
                sum(range(11, 61)) / sum(range(1, 61)) * 100,
            )
            self.assertTrue(series["source_run_ids"])


if __name__ == "__main__":
    unittest.main()
