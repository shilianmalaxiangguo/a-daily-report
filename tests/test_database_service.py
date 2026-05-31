import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class DatabaseServiceTest(unittest.TestCase):
    def test_database_service_selects_postgres_from_environment(self):
        from storage.database_service import DatabaseService

        class StubPostgresRepository:
            def __init__(self, database_url):
                self.database_url = database_url

        with patch.dict("os.environ", {"A_DAILY_REPORT_DATABASE_URL": "postgresql://unit/report"}, clear=False):
            with patch("storage.database_service.PostgresDailyFactDb", StubPostgresRepository):
                service = DatabaseService.from_environment()

        self.assertIsInstance(service.repository, StubPostgresRepository)
        self.assertEqual(service.repository.database_url, "postgresql://unit/report")

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
            service.upsert_mainline_daily({"trade_date": "2026-05-12", "primary_mainline": "半导体"})
            service.upsert_mainline_turnover_daily(
                {
                    "trade_date": "2026-05-12",
                    "primary_mainline": "半导体",
                    "sector_turnover_yi": 3.0,
                    "total_turnover_yi": 10.0,
                    "turnover_share_pct": 30.0,
                }
            )
            service.upsert_new_high_feedback_daily(
                {
                    "trade_date": "2026-05-12",
                    "new_high_count": 88,
                    "all_a_share_pct": 1.76,
                    "leading_sectors": "半导体",
                }
            )
            service.upsert_price_band_style_daily(
                {
                    "trade_date": "2026-05-12",
                    "high_price_pct": 0.8,
                    "low_price_pct": 1.6,
                }
            )
            service.upsert_monthly_account_ledger(
                {
                    "trade_date": "2026-05-12",
                    "account_id": "main",
                    "month_return_pct": 4.2,
                    "source_policy": "manual_review",
                }
            )

            self.assertEqual(total["total_amount_yi"], 2.5)
            self.assertEqual(queried_total["total_amount_yi"], 2.5)
            self.assertEqual(queried_total["stock_count"], 1)
            self.assertEqual(service.query_market_breadth_counts("2026-05-12")["up_count"], 1)
            self.assertEqual(len(ranks), 1)
            self.assertEqual(series["rows"][0]["share_pct"], 100.0)
            self.assertEqual(service.query_mainline_daily_series("2026-05-12")[0]["primary_mainline"], "半导体")
            self.assertEqual(service.query_mainline_turnover_series("2026-05-12", "半导体")[0]["sector_turnover"], 3.0)
            self.assertEqual(service.query_new_high_feedback_series("2026-05-12")[0]["new_high_count"], 88)
            price_band_rows = service.query_price_band_style_series("2026-05-12", window_days=25)["rows"]
            self.assertEqual(price_band_rows[0]["style_label"], "震荡")
            self.assertEqual(service.query_monthly_account_ledger("2026-05-12")["month_return_pct"], 4.2)

    def test_database_service_tracks_extreme_conviction_mentions_by_recent_25_trade_dates(self):
        from storage.database_service import DatabaseService

        with tempfile.TemporaryDirectory() as tmp:
            service = DatabaseService.sqlite_d1_compatible(Path(tmp) / "daily.db")
            rows = []
            for index in range(26):
                trade_date = f"2026-05-{index + 1:02d}"
                rows.append(
                    {
                        "record_id": f"{trade_date}:000001",
                        "mention_trade_date": trade_date,
                        "stock_code": "000001",
                        "stock_name": "样本一号",
                        "rank_no": 1,
                        "sector_candidate": "半导体",
                        "buy_window": "09:30-09:35",
                        "review_status": "等待复盘",
                    }
                )
            rows.append(
                {
                    "record_id": "2026-05-26:000002",
                    "mention_trade_date": "2026-05-26",
                    "stock_code": "000002",
                    "stock_name": "样本二号",
                    "rank_no": 2,
                    "sector_candidate": "电力",
                    "buy_window": "09:50-10:10",
                    "review_status": "等待复盘",
                }
            )
            rows.append(
                {
                    "record_id": "2026-05-26:000003",
                    "mention_trade_date": "2026-05-26",
                    "stock_code": "000003",
                    "stock_name": "淘汰样本",
                    "rank_no": 3,
                    "sector_candidate": "军工",
                    "buy_window": "09:50-10:10",
                    "review_status": "等待复盘",
                    "is_a_kill_eliminated": True,
                }
            )

            self.assertEqual(service.replace_extreme_conviction_mentions_for_trade_date("2026-05-26", rows[-3:]), 3)
            self.assertEqual(service.upsert_extreme_conviction_mentions(rows[:-3]), 25)
            result = service.query_extreme_conviction_mentions("2026-05-26", window_days=25)

        self.assertEqual(result[0]["mention_trade_date"], "2026-05-02")
        self.assertEqual(result[-1]["mention_trade_date"], "2026-05-26")
        self.assertIn("000002", [row["stock_code"] for row in result])
        self.assertNotIn("000003", [row["stock_code"] for row in result])

    def test_database_service_queries_sector_fund_flow_series_by_recent_trade_dates(self):
        from storage.database_service import DatabaseService

        with tempfile.TemporaryDirectory() as tmp:
            service = DatabaseService.sqlite_d1_compatible(Path(tmp) / "daily.db")
            service.upsert_sector_fund_flow_daily(
                {
                    "trade_date": "2026-05-21",
                    "sector_name": "半导体",
                    "net_inflow_yi": 12.34,
                    "source_policy": "unit-test",
                }
            )
            service.upsert_sector_fund_flow_daily(
                {
                    "trade_date": "2026-05-22",
                    "sector_name": "半导体",
                    "net_inflow_yi": -5.67,
                    "source_policy": "unit-test",
                }
            )

            result = service.query_sector_fund_flow_series("2026-05-22", "半导体", window_days=2)

        self.assertEqual(
            result,
            [
                {"date": "2026-05-21", "sector_name": "半导体", "inflow": 12.34},
                {"date": "2026-05-22", "sector_name": "半导体", "inflow": -5.67},
            ],
        )

    def test_database_service_upserts_market_daily_total_from_snapshot_total_turnover(self):
        from storage.database_service import DatabaseService

        with tempfile.TemporaryDirectory() as tmp:
            service = DatabaseService.sqlite_d1_compatible(Path(tmp) / "daily.db")

            service.upsert_market_daily_total(
                {
                    "trade_date": "2026-05-22",
                    "total_amount_yi": 29246.59,
                    "market_scope": "all_a",
                    "stock_count": 5504,
                    "source": "snapshot.total_turnover",
                }
            )
            result = service.query_market_daily_total("2026-05-22")

        self.assertEqual(result["total_amount_yi"], 29246.59)
        self.assertEqual(result["stock_count"], 5504)

    def test_database_service_filters_a_kill_shape_mentions_from_recent_tracking_query(self):
        from storage.database_service import DatabaseService

        with tempfile.TemporaryDirectory() as tmp:
            service = DatabaseService.sqlite_d1_compatible(Path(tmp) / "daily.db")
            bars = []
            for idx in range(40):
                if idx < 20:
                    close = 28 + idx * 0.1
                    pct_chg = 0.5
                elif idx < 39:
                    close = 25 - idx * 0.1
                    pct_chg = -1.0
                else:
                    close = 18.0
                    pct_chg = -10.0
                bars.append(
                    {
                        "trade_date": f"2026-05-{idx + 1:02d}",
                        "ts_code": "000586.SZ",
                        "stock_code": "000586",
                        "market": "SZ",
                        "name": "汇源通信",
                        "open": close + 0.2,
                        "high": close + 0.4,
                        "low": close - 0.4,
                        "close": close,
                        "pct_chg": pct_chg,
                        "vol": 10000 + idx,
                        "amount_yi": 1.0,
                    }
                )
            service.repository.upsert_stock_daily_quotes_recent(bars)
            service.upsert_extreme_conviction_mentions(
                [
                    {
                        "record_id": "2026-05-19:000586",
                        "mention_trade_date": "2026-05-19",
                        "stock_code": "000586",
                        "stock_name": "汇源通信",
                        "rank_no": 1,
                        "sector_candidate": "通信设备",
                        "buy_window": "09:30-09:35",
                        "review_status": "预演作废",
                    }
                ]
            )

            result = service.query_extreme_conviction_mentions("2026-05-40", window_days=25)
            with_a_kill = service.query_extreme_conviction_mentions("2026-05-40", window_days=25, include_a_kill=True)

        self.assertEqual(result, [])
        self.assertEqual([row["stock_code"] for row in with_a_kill], ["000586"])

    def test_database_service_marks_a_kill_shape_mentions_in_raw_tracking_rows(self):
        from storage.database_service import DatabaseService

        with tempfile.TemporaryDirectory() as tmp:
            service = DatabaseService.sqlite_d1_compatible(Path(tmp) / "daily.db")
            bars = []
            for idx in range(40):
                if idx < 20:
                    close = 28 + idx * 0.1
                    pct_chg = 0.5
                elif idx < 39:
                    close = 25 - idx * 0.1
                    pct_chg = -1.0
                else:
                    close = 18.0
                    pct_chg = -10.0
                bars.append(
                    {
                        "trade_date": f"2026-05-{idx + 1:02d}",
                        "ts_code": "000586.SZ",
                        "stock_code": "000586",
                        "market": "SZ",
                        "name": "汇源通信",
                        "open": close + 0.2,
                        "high": close + 0.4,
                        "low": close - 0.4,
                        "close": close,
                        "pct_chg": pct_chg,
                        "vol": 10000 + idx,
                        "amount_yi": 1.0,
                    }
                )
            service.repository.upsert_stock_daily_quotes_recent(bars)
            service.upsert_extreme_conviction_mentions(
                [
                    {
                        "record_id": "2026-05-19:000586",
                        "mention_trade_date": "2026-05-19",
                        "stock_code": "000586",
                        "stock_name": "汇源通信",
                        "rank_no": 1,
                        "sector_candidate": "通信设备",
                        "buy_window": "09:30-09:35",
                        "review_status": "预演作废",
                    }
                ]
            )

            before = service.query_extreme_conviction_mentions("2026-06-10", window_days=25, include_a_kill=True)
            marked = service.mark_a_kill_shape_extreme_conviction_mentions("2026-06-10", window_days=25)
            after = service.query_extreme_conviction_mentions("2026-06-10", window_days=25, include_a_kill=True)
            filtered = service.query_extreme_conviction_mentions("2026-06-10", window_days=25)

        self.assertEqual(before[0]["is_a_kill_eliminated"], False)
        self.assertEqual(marked, 1)
        self.assertEqual(after[0]["is_a_kill_eliminated"], True)
        self.assertEqual(after[0]["payload"]["is_a_kill_eliminated"], True)
        self.assertEqual(filtered, [])

    def test_database_service_returns_a_kill_shape_mark_details_when_requested(self):
        from storage.database_service import DatabaseService

        with tempfile.TemporaryDirectory() as tmp:
            service = DatabaseService.sqlite_d1_compatible(Path(tmp) / "daily.db")
            bars = []
            for idx in range(40):
                if idx < 20:
                    close = 28 + idx * 0.1
                    pct_chg = 0.5
                elif idx < 39:
                    close = 25 - idx * 0.1
                    pct_chg = -1.0
                else:
                    close = 18.0
                    pct_chg = -10.0
                bars.append(
                    {
                        "trade_date": f"2026-05-{idx + 1:02d}",
                        "ts_code": "000586.SZ",
                        "stock_code": "000586",
                        "market": "SZ",
                        "name": "汇源通信",
                        "open": close + 0.2,
                        "high": close + 0.4,
                        "low": close - 0.4,
                        "close": close,
                        "pct_chg": pct_chg,
                        "vol": 10000 + idx,
                        "amount_yi": 1.0,
                    }
                )
            service.repository.upsert_stock_daily_quotes_recent(bars)
            service.upsert_extreme_conviction_mentions(
                [
                    {
                        "record_id": "2026-05-19:000586",
                        "mention_trade_date": "2026-05-19",
                        "stock_code": "000586",
                        "stock_name": "汇源通信",
                        "rank_no": 1,
                        "sector_candidate": "通信设备",
                        "buy_window": "09:30-09:35",
                        "review_status": "预演作废",
                    }
                ]
            )

            result = service.mark_a_kill_shape_extreme_conviction_mentions(
                "2026-06-10",
                window_days=25,
                return_details=True,
            )

        self.assertEqual(result["updated_count"], 1)
        self.assertEqual(
            result["updated_records"],
            [
                {
                    "record_id": "2026-05-19:000586",
                    "mention_trade_date": "2026-05-19",
                    "stock_code": "000586",
                    "stock_name": "汇源通信",
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
