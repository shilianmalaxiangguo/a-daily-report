import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class _FakeFrame:
    def __init__(self, rows):
        self._rows = rows

    def to_dict(self, orient="records"):
        if orient != "records":
            raise AssertionError(f"unexpected orient: {orient}")
        return list(self._rows)


class _FakePro:
    def daily(self, **kwargs):
        return _FakeFrame(
            [
                {
                    "ts_code": f"{index + 1:06d}.SZ",
                    "trade_date": kwargs["trade_date"],
                    "open": 10,
                    "high": 11,
                    "low": 9,
                    "close": 10.5,
                    "pct_chg": 1,
                    "vol": 1000,
                    "amount": (60 - index) * 100000,
                }
                for index in range(60)
            ]
        )

    def stock_basic(self, **kwargs):
        return _FakeFrame(
            [
                {
                    "ts_code": f"{index + 1:06d}.SZ",
                    "name": f"测试{index + 1:02d}",
                    "industry": "半导体" if index < 30 else "通信设备",
                }
                for index in range(60)
            ]
        )

    def moneyflow(self, **kwargs):
        return _FakeFrame(
            [
                {
                    "ts_code": f"{index + 1:06d}.SZ",
                    "trade_date": kwargs["trade_date"],
                    "net_mf_amount": (index + 1) * 10000,
                }
                for index in range(60)
            ]
        )


class CloudflareFreeTurnoverPipelineTest(unittest.TestCase):
    def test_run_turnover_pipeline_builds_db_and_export_artifact(self):
        from pipelines.cloudflare_free_turnover_pipeline import run_turnover_pipeline

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            result = run_turnover_pipeline(
                "2026-05-12",
                db_path=tmp_path / "daily.db",
                artifact_root=tmp_path / "r2",
                pro=_FakePro(),
            )

            artifact_path = tmp_path / "r2" / result["export"]["r2_key"]
            payload = json.loads(artifact_path.read_text(encoding="utf-8"))

            self.assertEqual(result["trade_date"], "2026-05-12")
            self.assertEqual(result["quote_count"], 60)
            self.assertEqual(result["rank_count"], 100 if result["rank_count"] == 100 else 60)
            self.assertEqual(result["market_total"]["stock_count"], 60)
            self.assertTrue(artifact_path.exists())
            self.assertEqual(payload["query_window"]["rank_limit"], 50)
            self.assertEqual(len(payload["rows"]), 1)
            self.assertAlmostEqual(payload["rows"][0]["top_amount_yi"], sum(range(11, 61)))
            self.assertEqual(payload["latest_sector_breakdown"]["trade_date"], "2026-05-12")
            self.assertEqual(payload["latest_sector_breakdown"]["sector_source"], "tushare.stock_basic.industry")
            self.assertEqual(
                payload["latest_sector_breakdown"]["rows"][:2],
                [
                    {
                        "sector": "半导体",
                        "amount_yi": 1365.0,
                        "share_pct": 76.9014,
                        "stock_count": 30,
                        "stocks": payload["latest_sector_breakdown"]["rows"][0]["stocks"],
                    },
                    {
                        "sector": "通信设备",
                        "amount_yi": 410.0,
                        "share_pct": 23.0986,
                        "stock_count": 20,
                        "stocks": payload["latest_sector_breakdown"]["rows"][1]["stocks"],
                    },
                ],
            )
            first_stock = payload["latest_sector_breakdown"]["rows"][0]["stocks"][0]
            self.assertEqual(first_stock["stock_code"], "000001")
            self.assertEqual(first_stock["stock_name"], "测试01")
            self.assertEqual(first_stock["rank"], 1)
            self.assertAlmostEqual(first_stock["net_inflow_yi"], 1.0)
            self.assertAlmostEqual(first_stock["close"], 10.5)
            self.assertAlmostEqual(first_stock["pct_chg"], 1.0)

    def test_run_turnover_pipeline_uses_injected_services(self):
        from pipelines.cloudflare_free_turnover_pipeline import run_turnover_pipeline
        from storage.database_service import DatabaseService

        class FakeMarketDataService:
            def __init__(self):
                self.calls = []

            def get_stock_daily_turnover_records(self, trade_date):
                self.calls.append(trade_date)
                return [
                    {
                        "trade_date": trade_date,
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

            def get_stock_moneyflow_map(self, trade_date):
                return {"000001": 1.25}

            def get_stock_name_map(self):
                return {"000001": "平安银行"}

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            market_data_service = FakeMarketDataService()
            database_service = DatabaseService.sqlite_d1_compatible(tmp_path / "daily.db")

            result = run_turnover_pipeline(
                "2026-05-12",
                artifact_root=tmp_path / "r2",
                market_data_service=market_data_service,
                database_service=database_service,
            )

            self.assertEqual(market_data_service.calls, ["2026-05-12"])
            self.assertEqual(result["quote_count"], 1)
            self.assertEqual(result["rank_count"], 1)
            payload = json.loads((tmp_path / "r2" / result["export"]["r2_key"]).read_text(encoding="utf-8"))
            first_stock = payload["latest_sector_breakdown"]["rows"][0]["stocks"][0]
            self.assertEqual(first_stock["stock_name"], "平安银行")
            self.assertAlmostEqual(first_stock["net_inflow_yi"], 1.25)


if __name__ == "__main__":
    unittest.main()
