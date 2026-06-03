import sys
import sqlite3
import tempfile
import unittest
import warnings
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

    def test_utc_now_text_does_not_emit_deprecation_warning(self):
        from storage import cloudflare_free_daily_db

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", DeprecationWarning)
            value = cloudflare_free_daily_db._utc_now_text()

        deprecations = [item for item in caught if issubclass(item.category, DeprecationWarning)]
        self.assertEqual(deprecations, [])
        self.assertRegex(value, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

    def test_connect_context_closes_connection_after_exit(self):
        from storage.cloudflare_free_daily_db import CloudflareFreeDailyDb

        with tempfile.TemporaryDirectory() as tmp:
            db = CloudflareFreeDailyDb(Path(tmp) / "daily.db")
            with db._connect() as conn:
                self.assertEqual(conn.execute("SELECT 1").fetchone()[0], 1)

            with self.assertRaises(sqlite3.ProgrammingError):
                conn.execute("SELECT 1").fetchone()

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

    def test_query_market_breadth_counts_from_recent_quotes(self):
        from storage.cloudflare_free_daily_db import CloudflareFreeDailyDb

        rows = self._rows_for_date("2026-05-12", count=4)
        rows[0]["pct_chg"] = 2.1
        rows[1]["pct_chg"] = -0.8
        rows[2]["pct_chg"] = 0.0
        rows[3]["pct_chg"] = 3.4
        with tempfile.TemporaryDirectory() as tmp:
            db = CloudflareFreeDailyDb(Path(tmp) / "daily.db")
            db.upsert_stock_daily_quotes_recent(rows, source_run_id=1)

            breadth = db.query_market_breadth_counts("2026-05-12")

        self.assertEqual(breadth["stock_count"], 4)
        self.assertEqual(breadth["up_count"], 2)
        self.assertEqual(breadth["down_count"], 1)
        self.assertEqual(breadth["flat_count"], 1)

    def test_monthly_account_ledger_round_trip_uses_latest_record_before_date(self):
        from storage.cloudflare_free_daily_db import CloudflareFreeDailyDb

        with tempfile.TemporaryDirectory() as tmp:
            db = CloudflareFreeDailyDb(Path(tmp) / "daily.db")
            db.upsert_monthly_account_ledger(
                {
                    "trade_date": "2026-04-30",
                    "account_id": "main",
                    "month_key": "2026-04",
                    "month_return_pct": 2.4,
                    "equity": 102400.0,
                    "cash": 52000.0,
                    "position_market_value": 50400.0,
                    "source_policy": "manual_review",
                }
            )
            db.upsert_monthly_account_ledger(
                {
                    "trade_date": "2026-05-20",
                    "account_id": "main",
                    "month_key": "2026-05",
                    "month_return_pct": 6.8,
                    "equity": 106800.0,
                    "cash": 50000.0,
                    "position_market_value": 56800.0,
                    "source_policy": "manual_review",
                }
            )

            latest = db.query_monthly_account_ledger("2026-05-20")
            earlier = db.query_monthly_account_ledger("2026-04-30")

        self.assertEqual(latest["trade_date"], "2026-05-20")
        self.assertEqual(latest["month_key"], "2026-05")
        self.assertAlmostEqual(latest["month_return_pct"], 6.8)
        self.assertAlmostEqual(latest["simulated_cumulative_return_pct"], 9.3632, places=4)
        self.assertEqual(latest["source_policy"], "manual_review")
        self.assertEqual(earlier["trade_date"], "2026-04-30")
        self.assertAlmostEqual(earlier["month_return_pct"], 2.4)
        self.assertAlmostEqual(earlier["simulated_cumulative_return_pct"], 2.4, places=4)

    def test_monthly_account_ledger_query_recomputes_after_out_of_order_backfill(self):
        from storage.cloudflare_free_daily_db import CloudflareFreeDailyDb

        with tempfile.TemporaryDirectory() as tmp:
            db = CloudflareFreeDailyDb(Path(tmp) / "daily.db")
            db.upsert_monthly_account_ledger(
                {
                    "trade_date": "2026-05-20",
                    "account_id": "main",
                    "month_key": "2026-05",
                    "month_return_pct": 6.8,
                    "source_policy": "manual_review",
                }
            )
            db.upsert_monthly_account_ledger(
                {
                    "trade_date": "2026-04-30",
                    "account_id": "main",
                    "month_key": "2026-04",
                    "month_return_pct": 2.4,
                    "source_policy": "manual_review",
                }
            )

            latest = db.query_monthly_account_ledger("2026-05-20")

        self.assertAlmostEqual(latest["simulated_cumulative_return_pct"], 9.3632, places=4)

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

    def test_t25_daily_metric_tables_round_trip(self):
        from storage.cloudflare_free_daily_db import CloudflareFreeDailyDb

        with tempfile.TemporaryDirectory() as tmp:
            db = CloudflareFreeDailyDb(Path(tmp) / "daily.db")
            db.upsert_mainline_daily(
                {
                    "trade_date": "2026-05-19",
                    "primary_mainline": "半导体",
                    "daily_attack_line": "半导体",
                    "secondary_mainline": "电力",
                    "competition_mainline": "机器人",
                    "leading_line": "半导体",
                    "state_code": "observe",
                    "source_policy": "snapshot_index",
                }
            )
            db.upsert_mainline_turnover_daily(
                {
                    "trade_date": "2026-05-19",
                    "primary_mainline": "半导体",
                    "sector_turnover_yi": 4050.0,
                    "total_turnover_yi": 29764.59,
                    "turnover_share_pct": 13.61,
                    "matched_sector_names": ["半导体"],
                    "source_policy": "tushare.moneyflow_ind_ths",
                }
            )
            db.upsert_new_high_feedback_daily(
                {
                    "trade_date": "2026-05-19",
                    "new_high_count": 126,
                    "all_a_share_pct": 2.52,
                    "leading_sectors": "半导体、机器人",
                    "sector_distribution": [{"sector": "半导体", "new_high_count": 35}],
                    "source_policy": "tushare.stk_factor_pro.topdays",
                }
            )
            db.upsert_price_band_style_daily(
                {
                    "trade_date": "2026-05-19",
                    "high_price_code": "883916.TI",
                    "low_price_code": "883960.TI",
                    "high_price_pct": 1.2,
                    "low_price_pct": -0.3,
                    "source_policy": "tushare.ths_daily.price_band_style",
                }
            )
            db.upsert_margin_pressure_daily(
                {
                    "trade_date": "2026-05-19",
                    "margin_balance_yi": 28770.87,
                    "short_selling_balance_yi": 208.52,
                    "margin_trading_balance_yi": 28979.38,
                    "market_turnover_yi": 28863.10,
                    "exchange_count": 3,
                    "source_policy": "tushare.margin+tushare.daily",
                }
            )

            mainline_rows = db.query_mainline_daily_series("2026-05-20", window_days=25)
            turnover_rows = db.query_mainline_turnover_series("2026-05-20", "半导体", window_days=25)
            new_high_rows = db.query_new_high_feedback_series("2026-05-20", window_days=25)
            price_band_rows = db.query_price_band_style_series("2026-05-20", window_days=25)["rows"]
            margin_rows = db.query_margin_pressure_series("2026-05-20", window_days=25)["rows"]

        self.assertEqual(mainline_rows[0]["date"], "2026-05-19")
        self.assertEqual(mainline_rows[0]["primary_mainline"], "半导体")
        self.assertEqual(turnover_rows[0]["sector_name"], "半导体")
        self.assertEqual(turnover_rows[0]["sector_turnover"], 4050.0)
        self.assertEqual(turnover_rows[0]["turnover_share_pct"], 13.61)
        self.assertEqual(new_high_rows[0]["trade_date"], "2026-05-19")
        self.assertEqual(new_high_rows[0]["new_high_count"], 126)
        self.assertEqual(price_band_rows[0]["trade_date"], "2026-05-19")
        self.assertEqual(price_band_rows[0]["style_label"], "震荡")
        self.assertAlmostEqual(price_band_rows[0]["spread_pct"], 1.5)
        self.assertEqual(margin_rows[0]["trade_date"], "2026-05-19")
        self.assertAlmostEqual(margin_rows[0]["margin_turnover_ratio_pct"], 99.68, places=2)

    def test_price_band_style_query_recomputes_legacy_spread_from_price_moves(self):
        from storage.cloudflare_free_daily_db import CloudflareFreeDailyDb

        with tempfile.TemporaryDirectory() as tmp:
            db = CloudflareFreeDailyDb(Path(tmp) / "daily.db")
            with db._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO price_band_style_daily(
                        trade_date, high_price_code, low_price_code, high_price_pct,
                        low_price_pct, spread_pct, style_label, source_policy, source_run_id
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    ("2026-05-20", "883916.TI", "883960.TI", 10.0, -10.0, 20.0, "", "legacy", 0),
                )
                conn.commit()

            rows = db.query_price_band_style_series("2026-05-20", window_days=25)["rows"]

        self.assertAlmostEqual(rows[0]["spread_pct"], 20.0)
        self.assertEqual(rows[0]["style_label"], "高潮")

    def test_build_new_high_feedback_from_recent_quotes_when_factor_rows_empty(self):
        from storage.cloudflare_free_daily_db import CloudflareFreeDailyDb

        with tempfile.TemporaryDirectory() as tmp:
            db = CloudflareFreeDailyDb(Path(tmp) / "daily.db")
            db.upsert_stock_daily_quotes_recent(
                [
                    {
                        "trade_date": "2026-05-20",
                        "ts_code": "000001.SZ",
                        "stock_code": "000001",
                        "market": "SZ",
                        "name": "趋势一号",
                        "high": 10.0,
                        "pct_chg": 1.0,
                        "amount_yi": 12.0,
                    },
                    {
                        "trade_date": "2026-05-20",
                        "ts_code": "000002.SZ",
                        "stock_code": "000002",
                        "market": "SZ",
                        "name": "趋势二号",
                        "high": 20.0,
                        "pct_chg": 1.0,
                        "amount_yi": 10.0,
                    },
                    {
                        "trade_date": "2026-05-21",
                        "ts_code": "000001.SZ",
                        "stock_code": "000001",
                        "market": "SZ",
                        "name": "趋势一号",
                        "high": 10.5,
                        "pct_chg": 3.0,
                        "amount_yi": 15.0,
                    },
                    {
                        "trade_date": "2026-05-21",
                        "ts_code": "000002.SZ",
                        "stock_code": "000002",
                        "market": "SZ",
                        "name": "趋势二号",
                        "high": 19.5,
                        "pct_chg": -2.0,
                        "amount_yi": 9.0,
                    },
                ]
            )

            snapshot = db.build_new_high_feedback_from_recent_quotes(
                "2026-05-21",
                stock_basic_map={
                    "000001": {"name": "趋势一号", "industry": "半导体", "list_date": "20200102"},
                    "000002": {"name": "趋势二号", "industry": "机器人", "list_date": "20200102"},
                },
                history_rows=[{"trade_date": "2026-05-20", "new_high_count": 2, "all_a_share_pct": 0.04}],
                lookback_days=1,
            )

        self.assertTrue(snapshot["available"])
        self.assertEqual(snapshot["source"], "storage.stock_daily_quotes_recent.high_break")
        self.assertEqual(snapshot["new_high_count"], 1)
        self.assertEqual(snapshot["leading_sectors"], "半导体")
        self.assertEqual(snapshot["trend_rows"][-1]["trade_date"], "2026-05-21")
        self.assertEqual(snapshot["trend_rows"][-1]["change_text"], "-1")

    def test_recent_quotes_new_high_feedback_requires_enough_history(self):
        from storage.cloudflare_free_daily_db import CloudflareFreeDailyDb

        with tempfile.TemporaryDirectory() as tmp:
            db = CloudflareFreeDailyDb(Path(tmp) / "daily.db")
            db.upsert_stock_daily_quotes_recent(
                [
                    {
                        "trade_date": "2026-05-20",
                        "ts_code": "000001.SZ",
                        "stock_code": "000001",
                        "market": "SZ",
                        "name": "趋势一号",
                        "high": 10.0,
                        "pct_chg": 1.0,
                        "amount_yi": 12.0,
                    },
                    {
                        "trade_date": "2026-05-21",
                        "ts_code": "000001.SZ",
                        "stock_code": "000001",
                        "market": "SZ",
                        "name": "趋势一号",
                        "high": 10.5,
                        "pct_chg": 3.0,
                        "amount_yi": 15.0,
                    },
                ]
            )

            snapshot = db.build_new_high_feedback_from_recent_quotes("2026-05-21", lookback_days=250)

        self.assertFalse(snapshot["available"])
        self.assertEqual(snapshot["status"], "insufficient_history")
        self.assertIn("本地日线历史不足", snapshot["message"])


if __name__ == "__main__":
    unittest.main()
