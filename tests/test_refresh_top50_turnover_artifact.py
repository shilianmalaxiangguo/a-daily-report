import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class RefreshTop50TurnoverArtifactTest(unittest.TestCase):
    def test_refresh_top50_turnover_artifact_writes_r2_and_public_copy(self):
        from pipelines.refresh_top50_turnover_artifact import refresh_top50_turnover_artifact

        class FakeMarketDataService:
            def get_stock_daily_turnover_records(self, trade_date):
                return [
                    {
                        "trade_date": trade_date,
                        "ts_code": f"{index + 1:06d}.SZ",
                        "stock_code": f"{index + 1:06d}",
                        "market": "SZ",
                        "name": f"样本{index + 1:02d}",
                        "open": 10,
                        "high": 11,
                        "low": 9,
                        "close": 10.5,
                        "pct_chg": 1.0,
                        "vol": 1000,
                        "amount_yi": float(60 - index),
                    }
                    for index in range(60)
                ]

            def get_stock_industry_map(self):
                return {"000001": "半导体", "000002": "半导体"}

            def get_stock_name_map(self):
                return {"000001": "样本01"}

            def get_stock_moneyflow_map(self, trade_date):
                return {"000001": 1.23}

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            result = refresh_top50_turnover_artifact(
                "2026-05-13",
                db_path=tmp_path / "daily.db",
                artifact_root=tmp_path / ".generated" / "r2",
                public_copy_path=tmp_path / "snap-ui" / "public" / "data" / "snap-ui" / "turnover" / "top50-share" / "latest.json",
                market_data_service=FakeMarketDataService(),
            )

            self.assertEqual(result["trade_date"], "2026-05-13")
            self.assertEqual(result["row_count"], 1)
            self.assertGreater(result["latest_share_pct"], 0)
            self.assertTrue(result["has_sector_breakdown"])
            self.assertTrue(Path(result["r2_artifact_path"]).exists())
            self.assertTrue(Path(result["public_copy_path"]).exists())
            public_payload = json.loads(Path(result["public_copy_path"]).read_text(encoding="utf-8"))
            self.assertEqual(public_payload["query_window"]["end_date"], "2026-05-13")
            self.assertEqual(public_payload["query_window"]["window_days"], 25)
            self.assertEqual(public_payload["latest_sector_breakdown"]["sector_source"], "tushare.stock_basic.industry")

    def test_refresh_top50_turnover_artifact_does_not_overwrite_public_copy_when_tushare_empty(self):
        from pipelines.cloudflare_free_turnover_pipeline import TurnoverPipelineDataUnavailableError
        from pipelines.refresh_top50_turnover_artifact import refresh_top50_turnover_artifact

        class EmptyMarketDataService:
            def get_stock_daily_turnover_records(self, trade_date):
                return []

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            public_copy_path = (
                tmp_path
                / "snap-ui"
                / "public"
                / "data"
                / "snap-ui"
                / "turnover"
                / "top50-share"
                / "latest.json"
            )
            public_copy_path.parent.mkdir(parents=True, exist_ok=True)
            public_copy_path.write_text('{"sentinel":"previous-good-artifact"}', encoding="utf-8")

            with self.assertRaises(TurnoverPipelineDataUnavailableError):
                refresh_top50_turnover_artifact(
                    "2026-05-13",
                    db_path=tmp_path / "daily.db",
                    artifact_root=tmp_path / ".generated" / "r2",
                    public_copy_path=public_copy_path,
                    market_data_service=EmptyMarketDataService(),
                )

            self.assertEqual(
                json.loads(public_copy_path.read_text(encoding="utf-8")),
                {"sentinel": "previous-good-artifact"},
            )

    def test_public_copy_is_written_via_atomic_replace(self):
        from pipelines import refresh_top50_turnover_artifact as module

        calls = []

        def fake_replace(source, target):
            calls.append((Path(source).name, Path(target).name))

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source_path = tmp_path / "source.json"
            public_copy_path = tmp_path / "public" / "latest.json"
            source_path.write_text('{"ok":true}', encoding="utf-8")

            original_replace = module.os.replace
            module.os.replace = fake_replace
            try:
                copied_path = module._copy_public_artifact(source_path, public_copy_path)
            finally:
                module.os.replace = original_replace

            temp_path = public_copy_path.with_suffix(".json.tmp")
            self.assertEqual(copied_path, public_copy_path)
            self.assertEqual(calls, [(temp_path.name, public_copy_path.name)])
            self.assertEqual(json.loads(temp_path.read_text(encoding="utf-8")), {"ok": True})


if __name__ == "__main__":
    unittest.main()
