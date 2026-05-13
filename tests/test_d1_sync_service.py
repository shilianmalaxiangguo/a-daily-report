import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class D1SyncServiceTest(unittest.TestCase):
    def _seed_db(self, db_path):
        from storage.database_service import DatabaseService

        service = DatabaseService.sqlite_d1_compatible(db_path)
        run_id = service.save_provider_source_run(
            {
                "trade_date": "2026-05-12",
                "provider": "tushare",
                "endpoint": "daily",
                "status": "success",
                "row_count": 2,
            }
        )
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
            },
            {
                "trade_date": "2026-05-12",
                "ts_code": "600000.SH",
                "stock_code": "600000",
                "market": "SH",
                "name": "浦发银行",
                "open": 8,
                "high": 8.5,
                "low": 7.9,
                "close": 8.1,
                "pct_chg": -1,
                "vol": 800,
                "amount_yi": 1.0,
            },
        ]
        service.upsert_stock_daily_quotes_recent(rows, source_run_id=run_id)
        service.rebuild_market_daily_total("2026-05-12", source_run_id=run_id)
        service.rebuild_turnover_rank_daily("2026-05-12", rank_limit=100, source_run_id=run_id)
        payload = service.query_top_turnover_share_series("2026-05-12", window_days=30, limit=50)
        service.save_turnover_share_series(payload)
        service.save_report_artifact(
            {
                "trade_date": "2026-05-12",
                "variant": "turnover-top50-share",
                "visibility": "public",
                "r2_key": "exports/turnover/top50-share/latest.json",
                "content_hash": "abc",
                "schema_version": "cf-free-turnover-series/v1",
                "source_run_id": run_id,
                "created_at": payload["generated_at"],
            }
        )

    def test_export_sql_includes_d1_tables_and_upserts(self):
        from storage.d1_sync_service import D1SyncService

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / "daily.db"
            self._seed_db(db_path)
            service = D1SyncService(db_path)
            sql_path = service.export_sql(tmp_path / "sync.sql")
            sql = sql_path.read_text(encoding="utf-8")

        self.assertNotIn("BEGIN TRANSACTION", sql)
        self.assertNotIn("COMMIT;", sql)
        self.assertIn("INSERT OR REPLACE INTO provider_source_runs", sql)
        self.assertIn("INSERT OR REPLACE INTO stock_daily_quotes_recent", sql)
        self.assertIn("INSERT OR REPLACE INTO market_daily_totals", sql)
        self.assertIn("INSERT OR REPLACE INTO turnover_rank_daily", sql)
        self.assertIn("INSERT OR REPLACE INTO turnover_share_series", sql)
        self.assertIn("INSERT OR REPLACE INTO report_artifacts", sql)
        self.assertIn("DELETE FROM turnover_rank_daily;", sql)
        self.assertIn("'平安银行'", sql)
        self.assertIn("'exports/turnover/top50-share/latest.json'", sql)

    def test_build_remote_execute_command_points_to_exported_sql(self):
        from storage.d1_sync_service import D1SyncService

        service = D1SyncService("/tmp/local.db")
        command = service.build_execute_command(
            "a-daily-report-free",
            "/tmp/sync.sql",
            remote=True,
        )

        self.assertEqual(
            command,
            [
                "wrangler",
                "d1",
                "execute",
                "a-daily-report-free",
                "--remote",
                "--file",
                "/tmp/sync.sql",
            ],
        )


if __name__ == "__main__":
    unittest.main()
