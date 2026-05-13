import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class CloudflareFreeJsonExportTest(unittest.TestCase):
    def _seed_db(self, db):
        rows = []
        for index in range(60):
            rows.append(
                {
                    "trade_date": "2026-05-12",
                    "ts_code": f"{index + 1:06d}.SZ",
                    "stock_code": f"{index + 1:06d}",
                    "market": "SZ",
                    "name": f"样本{index:02d}",
                    "open": 10,
                    "high": 11,
                    "low": 9,
                    "close": 10.5,
                    "pct_chg": 1.0,
                    "vol": 1000,
                    "amount_yi": float(60 - index),
                }
            )
        run_id = db.save_provider_source_run(
            {
                "trade_date": "2026-05-12",
                "provider": "tushare",
                "endpoint": "daily",
                "status": "success",
                "row_count": len(rows),
            }
        )
        db.upsert_stock_daily_quotes_recent(rows, source_run_id=run_id)
        db.rebuild_market_daily_total("2026-05-12", source_run_id=run_id)
        db.rebuild_turnover_rank_daily("2026-05-12", rank_limit=100, source_run_id=run_id)
        return run_id

    def test_export_turnover_share_series_writes_r2_shaped_json_and_indexes_artifact(self):
        from export.cloudflare_free_json_export import CloudflareFreeJsonExportService
        from storage.cloudflare_free_daily_db import CloudflareFreeDailyDb

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db = CloudflareFreeDailyDb(tmp_path / "daily.db")
            run_id = self._seed_db(db)
            service = CloudflareFreeJsonExportService(db, artifact_root=tmp_path / "r2")

            result = service.export_turnover_share_series("2026-05-12", window_days=30, limit=50)
            artifact_path = tmp_path / "r2" / result["r2_key"]
            payload = json.loads(artifact_path.read_text(encoding="utf-8"))

            self.assertEqual(result["r2_key"], "exports/turnover/top50-share/latest.json")
            self.assertTrue(artifact_path.exists())
            self.assertEqual(payload["schema_version"], "cf-free-turnover-series/v1")
            self.assertEqual(payload["query_window"]["end_date"], "2026-05-12")
            self.assertEqual(payload["source_run_ids"], [run_id])
            self.assertEqual(len(payload["rows"]), 1)
            self.assertEqual(payload["latest_sector_breakdown"]["rows"][0]["stocks"][0]["rank"], 1)
            self.assertEqual(payload["latest_sector_breakdown"]["rows"][0]["stocks"][0]["stock_code"], "000001")
            self.assertEqual(payload["latest_sector_breakdown"]["rows"][0]["stocks"][0]["stock_name"], "样本00")
            self.assertEqual(payload["latest_sector_breakdown"]["rows"][0]["stocks"][0]["amount_yi"], 60.0)
            self.assertEqual(payload["latest_sector_breakdown"]["rows"][0]["stocks"][0]["close"], 10.5)
            self.assertEqual(payload["latest_sector_breakdown"]["rows"][0]["stocks"][0]["pct_chg"], 1.0)
            artifacts = db.get_report_artifacts()
            self.assertEqual(len(artifacts), 1)
            self.assertEqual(artifacts[0]["variant"], "turnover-top50-share")
            self.assertEqual(artifacts[0]["visibility"], "public")
            self.assertEqual(artifacts[0]["r2_key"], "exports/turnover/top50-share/latest.json")
            self.assertEqual(artifacts[0]["schema_version"], "cf-free-turnover-series/v1")


if __name__ == "__main__":
    unittest.main()
