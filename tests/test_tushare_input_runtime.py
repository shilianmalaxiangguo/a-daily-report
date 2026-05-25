import sys
import unittest
from unittest.mock import patch
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from input.request_registry import build_input_request_registry
import input.tushare_runtime as tushare_runtime
from input.tushare_runtime import (
    get_margin_pressure_from_tushare_first,
    get_hot_concept_fund_flow_from_tushare_first,
    get_lhb_snapshot_from_tushare_first,
    get_limit_pool_snapshot_from_tushare_first,
    get_major_indices_from_tushare_first,
    get_new_high_feedback_from_tushare_first,
    get_sector_change_rank_from_tushare_first,
    get_sector_fund_flow_from_tushare_first,
    get_sector_hot_plates_from_tushare_first,
    get_price_band_style_series_from_tushare_first,
    get_stock_hot_rank_from_tushare_first,
    get_new_stock_calendar_from_tushare_first,
    get_stock_risk_map_from_tushare_first,
    get_total_turnover_from_tushare_first,
    get_top50_turnover_share_series_from_tushare_first,
    get_turnover_rank_from_tushare_first,
    get_wind_a_from_tushare_first,
)
from market_data.tushare_service import fetch_daily_price_bars


class _FakeFrame:
    def __init__(self, rows):
        self._rows = list(rows or [])

    def to_dict(self, orient="records"):
        if orient != "records":
            raise AssertionError(f"unexpected orient: {orient}")
        return list(self._rows)


class TushareInputRuntimeTest(unittest.TestCase):
    def test_request_registry_defaults_to_tushare_first_helpers(self):
        calls = []

        helpers = {
            "get_total_turnover_from_tushare_first": lambda *, target_date: calls.append("tushare_total") or 100.0,
            "get_major_indices_from_tushare_first": lambda *, target_date: calls.append("tushare_indices") or {},
            "get_wind_a_from_tushare_first": lambda *, target_date: calls.append("tushare_wind_a") or {},
            "get_turnover_rank_from_tushare_first": lambda *, target_date, limit=50: calls.append("tushare_turnover_rank") or [],
            "get_stock_hot_rank_from_tushare_first": lambda *, target_date, limit=30: calls.append("tushare_hot_rank") or [],
            "get_limit_pool_snapshot_from_tushare_first": lambda *, target_date: calls.append("tushare_limit_pool") or {},
            "get_sector_hot_plates_from_tushare_first": lambda *, target_date, limit=20: calls.append("tushare_sector_hot") or [],
            "get_hot_concept_fund_flow_from_tushare_first": lambda *, target_date, hot_plates=None, limit=20: calls.append("tushare_concept_flow") or {},
            "get_sector_change_rank_from_tushare_first": lambda *, target_date, rank_type="up", limit=10: calls.append(f"tushare_sector_change_{rank_type}") or [],
            "get_sector_fund_flow_from_tushare_first": lambda *, target_date, limit=50: calls.append("tushare_sector_flow") or {},
            "get_lhb_snapshot_from_tushare_first": lambda *, target_date: calls.append("tushare_lhb") or {},
            "get_new_stock_calendar_from_tushare_first": lambda *, target_date: calls.append("tushare_new_share") or [],
            "get_stock_risk_map_from_tushare_first": lambda *, target_date: calls.append("tushare_stock_risk") or {},
            "get_new_high_feedback_from_tushare_first": lambda *, target_date: calls.append("tushare_new_high") or {},
            "get_top50_turnover_share_series_from_tushare_first": lambda *, target_date, window_days=25, limit=50: calls.append("tushare_top50_series") or {"rows": []},
            "get_price_band_style_series_from_tushare_first": lambda *, target_date, window_days=25: calls.append("tushare_price_band_series") or {"rows": []},
            "get_margin_pressure_from_tushare_first": lambda *, target_date, window_days=25, calibration_days=250: calls.append("tushare_margin_pressure") or {"rows": []},
            "get_total_turnover_from_iwencai": lambda *, target_date: calls.append("legacy_total") or 0.0,
            "get_major_indices_from_iwencai": lambda *, target_date: calls.append("legacy_indices") or {},
            "get_wind_a_from_iwencai": lambda *, target_date: calls.append("legacy_wind_a") or {},
            "get_turnover_rank_from_iwencai": lambda *, target_date, limit=50: calls.append("legacy_turnover_rank") or [],
            "fetch_ths_hot_stock": lambda num=30: calls.append("legacy_ths_hot") or [],
            "get_legacy_limit_pool_snapshot": lambda target_date=None: calls.append("legacy_limit_pool") or {},
            "fetch_hot_plate": lambda: calls.append("legacy_sector_hot") or [],
            "get_sector_change_from_iwencai": lambda rank_type="up", limit=10, target_date=None: calls.append("legacy_sector_change") or [],
            "get_legacy_sector_fund_flow": lambda target_date=None, limit=50: calls.append("legacy_sector_flow") or {},
            "get_legacy_lhb_snapshot": lambda target_date=None: calls.append("legacy_lhb") or {},
            "get_legacy_new_stock_calendar": lambda target_date=None: calls.append("legacy_new_stock") or [],
        }

        registry = build_input_request_registry(helpers)
        self.assertEqual(registry["total_turnover"](target_date="2026-05-13"), 100.0)
        registry["major_indices"](target_date="2026-05-13")
        registry["wind_a"](target_date="2026-05-13")
        registry["turnover_rank"](target_date="2026-05-13", limit=50)
        registry["stock_hot_rank"](target_date="2026-05-13", limit=30)
        registry["limit_pool_snapshot"](target_date="2026-05-13")
        registry["sector_hot_plates"](target_date="2026-05-13", limit=20)
        registry["concept_fund_flow"](target_date="2026-05-13", hot_plates=[], limit=20)
        registry["sector_change_rank"](target_date="2026-05-13", rank_type="up", limit=10)
        registry["sector_fund_flow"](target_date="2026-05-13", limit=50)
        registry["lhb_snapshot"](target_date="2026-05-13")
        registry["new_stock_calendar"](target_date="2026-05-13")
        registry["stock_risk_map"](target_date="2026-05-13")
        registry["new_high_feedback"](target_date="2026-05-13")
        registry["top50_turnover_share_series"](target_date="2026-05-13")
        registry["price_band_style_series"](target_date="2026-05-13")
        registry["margin_pressure"](target_date="2026-05-13")

        self.assertEqual(
            calls,
            [
                "tushare_total",
                "tushare_indices",
                "tushare_wind_a",
                "tushare_turnover_rank",
                "tushare_hot_rank",
                "tushare_limit_pool",
                "tushare_sector_hot",
                "tushare_concept_flow",
                "tushare_sector_change_up",
                "tushare_sector_flow",
                "tushare_lhb",
                "tushare_new_share",
                "tushare_stock_risk",
                "tushare_new_high",
                "tushare_top50_series",
                "tushare_price_band_series",
                "tushare_margin_pressure",
            ],
        )

    def test_margin_pressure_uses_index_amount_proxy_for_250_day_calibration(self):
        class FakePro:
            def __init__(self):
                self.daily_calls = []
                self.index_daily_calls = []

            def margin(self, start_date="", end_date="", trade_date=""):
                return _FakeFrame(
                    [
                        {"trade_date": "20260520", "exchange_id": "SSE", "rzye": 1_000_000_000_000, "rqye": 10_000_000_000, "rzrqye": 1_010_000_000_000},
                        {"trade_date": "20260520", "exchange_id": "SZSE", "rzye": 1_000_000_000_000, "rqye": 10_000_000_000, "rzrqye": 1_010_000_000_000},
                        {"trade_date": "20260520", "exchange_id": "BSE", "rzye": 10_000_000_000, "rqye": 100_000_000, "rzrqye": 10_100_000_000},
                        {"trade_date": "20260521", "exchange_id": "SSE", "rzye": 1_050_000_000_000, "rqye": 10_000_000_000, "rzrqye": 1_060_000_000_000},
                        {"trade_date": "20260521", "exchange_id": "SZSE", "rzye": 1_050_000_000_000, "rqye": 10_000_000_000, "rzrqye": 1_060_000_000_000},
                        {"trade_date": "20260521", "exchange_id": "BSE", "rzye": 10_000_000_000, "rqye": 100_000_000, "rzrqye": 10_100_000_000},
                    ]
                )

            def daily(self, start_date="", end_date="", trade_date="", fields="", limit=None, offset=None):
                self.daily_calls.append(
                    {
                        "start_date": start_date,
                        "end_date": end_date,
                        "trade_date": trade_date,
                        "fields": fields,
                        "limit": limit,
                        "offset": offset,
                    }
                )
                return _FakeFrame([])

            def index_daily(self, ts_code="", start_date="", end_date=""):
                self.index_daily_calls.append({"ts_code": ts_code, "start_date": start_date, "end_date": end_date})
                amount_by_date = {
                    "20260520": {"000001.SH": 10_000_000.0, "399001.SZ": 20_000_000.0},
                    "20260521": {"000001.SH": 10_000_000.0, "399001.SZ": 20_000_000.0},
                }
                return _FakeFrame(
                    [
                        {"ts_code": ts_code, "trade_date": trade_date_value, "amount": by_code[ts_code]}
                        for trade_date_value, by_code in amount_by_date.items()
                        if ts_code in by_code
                    ]
                )

        fake_pro = FakePro()
        result = get_margin_pressure_from_tushare_first(
            "2026-05-21",
            window_days=2,
            calibration_days=2,
            pro=fake_pro,
            fetch_tushare_open_trade_dates_fn=lambda start_date, end_date: ["2026-05-20", "2026-05-21"],
        )

        self.assertTrue(result["available"])
        self.assertEqual([row["trade_date"] for row in result["rows"]], ["2026-05-20", "2026-05-21"])
        self.assertAlmostEqual(result["rows"][-1]["margin_balance_yi"], 21100.0)
        self.assertAlmostEqual(result["rows"][-1]["market_turnover_yi"], 300.0)
        self.assertEqual(result["latest_pressure_label"], "高压")
        self.assertIn("250日分位", result["summary"])
        self.assertEqual(fake_pro.daily_calls, [])
        self.assertEqual(
            [call["ts_code"] for call in fake_pro.index_daily_calls],
            ["000001.SH", "399001.SZ"],
        )

    def test_margin_pressure_falls_back_to_market_margin_balance_when_exchange_rows_incomplete(self):
        class FakePro:
            def index_daily(self, ts_code="", start_date="", end_date=""):
                amount_by_date = {
                    "20260520": {"000001.SH": 10_000_000.0, "399001.SZ": 20_000_000.0},
                    "20260521": {"000001.SH": 10_000_000.0, "399001.SZ": 20_000_000.0},
                    "20260522": {"000001.SH": 10_000_000.0, "399001.SZ": 20_000_000.0},
                }
                return _FakeFrame(
                    [
                        {"ts_code": ts_code, "trade_date": trade_date_value, "amount": by_code[ts_code]}
                        for trade_date_value, by_code in amount_by_date.items()
                        if ts_code in by_code
                    ]
                )

        result = get_margin_pressure_from_tushare_first(
            "2026-05-22",
            window_days=2,
            calibration_days=3,
            pro=FakePro(),
            fetch_tushare_open_trade_dates_fn=lambda start_date, end_date: ["2026-05-20", "2026-05-21", "2026-05-22"],
            fetch_margin_balance_rows_fn=lambda start_date, end_date, pro=None: [
                {
                    "trade_date": "2026-05-22",
                    "margin_balance_yi": 15000.0,
                    "exchange_count": 1,
                    "source_policy": "tushare.margin",
                }
            ],
            fetch_market_margin_balance_rows_fn=lambda start_date, end_date: [
                {
                    "trade_date": "2026-05-20",
                    "margin_balance_yi": 28836.18,
                    "exchange_count": 1,
                    "source_policy": "eastmoney.rzrq.total.RZYE",
                },
                {
                    "trade_date": "2026-05-21",
                    "margin_balance_yi": 28752.80,
                    "exchange_count": 1,
                    "source_policy": "eastmoney.rzrq.total.RZYE",
                },
            ],
        )

        self.assertTrue(result["available"])
        self.assertEqual(result["latest_data_date"], "2026-05-21")
        self.assertEqual(result["target_date"], "2026-05-22")
        self.assertTrue(result["is_stale_for_target"])
        self.assertIn("截至2026-05-21", result["summary"])
        self.assertIn("较目标日2026-05-22滞后一交易日", result["usage_note"])
        self.assertEqual([row["trade_date"] for row in result["rows"]], ["2026-05-20", "2026-05-21"])
        self.assertAlmostEqual(result["rows"][-1]["margin_balance_yi"], 28752.80)
        self.assertEqual(result["source"], "eastmoney.rzrq.total.RZYE+tushare.index_daily.market_amount")

    def test_margin_pressure_ignores_cached_incomplete_target_row_after_market_balance_fallback(self):
        class FakeDatabaseService:
            @classmethod
            def sqlite_d1_compatible(cls, db_path=None):
                return cls()

            def query_margin_pressure_series(self, end_date, *, window_days=25):
                return {
                    "rows": [
                        {
                            "trade_date": "2026-05-20",
                            "margin_balance_yi": 28836.18,
                            "market_turnover_yi": 29537.14,
                            "exchange_count": 3,
                            "source_policy": "tushare.margin+tushare.index_daily.market_amount",
                        },
                        {
                            "trade_date": "2026-05-21",
                            "margin_balance_yi": 28752.80,
                            "market_turnover_yi": 34816.05,
                            "exchange_count": 3,
                            "source_policy": "tushare.margin+tushare.index_daily.market_amount",
                        },
                        {
                            "trade_date": "2026-05-22",
                            "margin_balance_yi": 14688.01,
                            "market_turnover_yi": 29033.20,
                            "exchange_count": 1,
                            "source_policy": "tushare.margin+tushare.index_daily.market_amount",
                        },
                    ]
                }

            def save_provider_source_run(self, row):
                return 1

            def upsert_margin_pressure_daily(self, row):
                return dict(row or {})

        result = get_margin_pressure_from_tushare_first(
            "2026-05-22",
            window_days=2,
            calibration_days=3,
            database_service_cls=FakeDatabaseService,
            fetch_tushare_open_trade_dates_fn=lambda start_date, end_date: ["2026-05-20", "2026-05-21", "2026-05-22"],
            fetch_market_daily_amount_rows_fn=lambda start_date, end_date: [
                {"trade_date": "2026-05-20", "market_turnover_yi": 29537.14, "source_policy": "tushare.index_daily.market_amount"},
                {"trade_date": "2026-05-21", "market_turnover_yi": 34816.05, "source_policy": "tushare.index_daily.market_amount"},
                {"trade_date": "2026-05-22", "market_turnover_yi": 29033.20, "source_policy": "tushare.index_daily.market_amount"},
            ],
            fetch_margin_balance_rows_fn=lambda start_date, end_date: [
                {
                    "trade_date": "2026-05-22",
                    "margin_balance_yi": 14688.01,
                    "exchange_count": 1,
                    "source_policy": "tushare.margin",
                }
            ],
            fetch_market_margin_balance_rows_fn=lambda start_date, end_date: [
                {
                    "trade_date": "2026-05-20",
                    "margin_balance_yi": 28836.18,
                    "exchange_count": 1,
                    "source_policy": "eastmoney.rzrq.total.RZYE",
                },
                {
                    "trade_date": "2026-05-21",
                    "margin_balance_yi": 28752.80,
                    "exchange_count": 1,
                    "source_policy": "eastmoney.rzrq.total.RZYE",
                },
            ],
        )

        self.assertTrue(result["available"])
        self.assertEqual(result["latest_data_date"], "2026-05-21")
        self.assertEqual([row["trade_date"] for row in result["rows"]], ["2026-05-20", "2026-05-21"])
        self.assertEqual(result["source"], "eastmoney.rzrq.total.RZYE+tushare.index_daily.market_amount")

    def test_margin_pressure_uses_fact_db_previous_trade_date_when_online_refresh_times_out(self):
        class FakeDatabaseService:
            @classmethod
            def sqlite_d1_compatible(cls, db_path=None):
                return cls()

            def query_margin_pressure_series(self, end_date, *, window_days=25):
                return {
                    "rows": [
                        {
                            "trade_date": "2026-05-21",
                            "margin_balance_yi": 28752.80,
                            "market_turnover_yi": 34816.05,
                            "exchange_count": 3,
                            "source_policy": "tushare.margin+tushare.index_daily.market_amount",
                        },
                        {
                            "trade_date": "2026-05-22",
                            "margin_balance_yi": 28782.21,
                            "market_turnover_yi": 29033.20,
                            "exchange_count": 3,
                            "source_policy": "tushare.margin+tushare.index_daily.market_amount",
                        },
                    ]
                }

        result = get_margin_pressure_from_tushare_first(
            "2026-05-25",
            window_days=2,
            calibration_days=2,
            database_service_cls=FakeDatabaseService,
            fetch_tushare_open_trade_dates_fn=lambda start_date, end_date: ["2026-05-21", "2026-05-22", "2026-05-25"],
            fetch_market_daily_amount_rows_fn=lambda start_date, end_date: (_ for _ in ()).throw(TimeoutError("amount timeout")),
        )

        self.assertTrue(result["available"])
        self.assertEqual(result["latest_data_date"], "2026-05-22")
        self.assertEqual(result["target_date"], "2026-05-25")
        self.assertTrue(result["is_stale_for_target"])
        self.assertIn("较目标日2026-05-25滞后一交易日", result["usage_note"])

    def test_price_band_style_series_fetches_883916_and_883960_for_25_trade_dates(self):
        calls = []
        trade_dates = [f"2026-04-{day:02d}" for day in range(20, 31)] + [f"2026-05-{day:02d}" for day in range(1, 15)]

        def fetch_trade_dates(start_date, end_date):
            calls.append(("dates", start_date, end_date))
            return list(trade_dates)

        def fetch_ths_daily(trade_date):
            calls.append(("daily", trade_date))
            index = trade_dates.index(trade_date)
            return [
                {
                    "ts_code": "883916.TI",
                    "trade_date": trade_date.replace("-", ""),
                    "pct_change": 1.0 if index == 0 else 0.8,
                },
                {
                    "ts_code": "883960.TI",
                    "trade_date": trade_date.replace("-", ""),
                    "pct_change": 0.2 if index == 0 else 1.5,
                },
            ]

        result = get_price_band_style_series_from_tushare_first(
            "2026-05-14",
            window_days=25,
            fetch_tushare_open_trade_dates_fn=fetch_trade_dates,
            fetch_tushare_ths_daily_fn=fetch_ths_daily,
        )

        self.assertTrue(result["available"])
        self.assertEqual(result["high_price_code"], "883916.TI")
        self.assertEqual(result["low_price_code"], "883960.TI")
        self.assertEqual(len(result["rows"]), 25)
        self.assertEqual(result["rows"][0]["style_label"], "震荡")
        self.assertEqual(result["rows"][-1]["style_label"], "震荡")
        self.assertEqual(result["rows"][-1]["trade_date"], "2026-05-14")
        self.assertIn("近25个交易日价格带风格", result["summary"])
        self.assertIn("最新差值 -0.70pct，当前为震荡", result["summary"])
        self.assertNotIn("对数相对强弱", result["summary"])
        self.assertIn("不单独说明明日走势", result["summary"])
        self.assertIn("明日仍看成交额与核心承接", result["summary"])
        self.assertEqual(calls[0][0], "dates")
        self.assertEqual(len([call for call in calls if call[0] == "daily"]), 25)

    def test_price_band_style_series_uses_single_day_spread_and_three_states(self):
        trade_dates = ["2026-05-17", "2026-05-18", "2026-05-19", "2026-05-20", "2026-05-21"]
        pct_by_date = {
            "2026-05-17": (3.0, 0.0),
            "2026-05-18": (-3.0, 0.0),
            "2026-05-19": (2.0, 0.0),
            "2026-05-20": (-2.0, 0.0),
            "2026-05-21": (-4.2563, -2.8785),
        }

        result = get_price_band_style_series_from_tushare_first(
            "2026-05-21",
            window_days=5,
            fetch_tushare_open_trade_dates_fn=lambda start_date, end_date: trade_dates,
            fetch_tushare_ths_daily_fn=lambda trade_date: [
                {"ts_code": "883916.TI", "trade_date": trade_date.replace("-", ""), "pct_change": pct_by_date[trade_date][0]},
                {"ts_code": "883960.TI", "trade_date": trade_date.replace("-", ""), "pct_change": pct_by_date[trade_date][1]},
            ],
        )

        rows = result["rows"]
        self.assertAlmostEqual(rows[0]["spread_pct"], 3.0, places=4)
        self.assertEqual(rows[0]["style_label"], "高潮")
        self.assertAlmostEqual(rows[1]["spread_pct"], -3.0, places=4)
        self.assertEqual(rows[1]["style_label"], "冰点")
        self.assertEqual(rows[2]["style_label"], "震荡")
        self.assertEqual(rows[3]["style_label"], "震荡")
        self.assertAlmostEqual(rows[4]["spread_pct"], -1.3778, places=4)
        self.assertEqual(rows[4]["style_label"], "震荡")
        self.assertEqual(result["latest_style_label"], "震荡")
        self.assertAlmostEqual(result["latest_spread_pct"], -1.3778, places=4)
        self.assertIn("最新差值 -1.38pct，当前为震荡", result["summary"])
        self.assertNotIn("相对收益", result["summary"])

    def test_price_band_style_series_reads_from_fact_db_and_refreshes_missing_target(self):
        calls = []

        class FakeService:
            refreshed = False

            def query_price_band_style_series(self, end_date, *, window_days=25):
                calls.append(("query", end_date, window_days, self.refreshed))
                if not self.refreshed:
                    return {"rows": [{"trade_date": "2026-05-19", "high_price_pct": 0.5, "low_price_pct": 0.1}]}
                return {
                    "rows": [
                        {"trade_date": "2026-05-19", "high_price_pct": 0.5, "low_price_pct": 0.1},
                        {"trade_date": "2026-05-20", "high_price_pct": 1.2, "low_price_pct": -0.4},
                    ]
                }

            def save_provider_source_run(self, payload):
                calls.append(("save_run", payload["trade_date"], payload["row_count"]))
                return 9

            def upsert_price_band_style_daily(self, row):
                calls.append(("upsert", row["trade_date"], row["high_price_pct"], row["low_price_pct"], row["source_run_id"]))
                self.refreshed = True
                return row

        service = FakeService()

        class FakeDatabaseService:
            @classmethod
            def sqlite_d1_compatible(cls, db_path=None):
                calls.append(("db", db_path))
                return service

        result = get_price_band_style_series_from_tushare_first(
            "2026-05-20",
            window_days=25,
            db_path="daily.db",
            database_service_cls=FakeDatabaseService,
            fetch_tushare_open_trade_dates_fn=lambda start_date, end_date: ["2026-05-19", "2026-05-20"],
            fetch_tushare_ths_daily_fn=lambda trade_date: [
                {"ts_code": "883916.TI", "trade_date": trade_date.replace("-", ""), "pct_change": 1.2},
                {"ts_code": "883960.TI", "trade_date": trade_date.replace("-", ""), "pct_change": -0.4},
            ],
        )

        self.assertEqual(result["rows"][-1]["trade_date"], "2026-05-20")
        self.assertEqual(result["rows"][-1]["style_label"], "震荡")
        self.assertEqual(
            calls,
            [
                ("db", "daily.db"),
                ("query", "2026-05-20", 25, False),
                ("save_run", "2026-05-20", 2),
                ("upsert", "2026-05-20", 1.2, -0.4, 9),
                ("query", "2026-05-20", 25, True),
            ],
        )

    def test_price_band_style_series_backfills_fact_db_when_latest_exists_but_window_is_short(self):
        calls = []
        trade_dates = ["2026-05-18", "2026-05-19", "2026-05-20"]

        class FakeService:
            rows = [{"trade_date": "2026-05-20", "high_price_pct": 1.2, "low_price_pct": -0.4}]

            def query_price_band_style_series(self, end_date, *, window_days=25):
                calls.append(("query", end_date, window_days, len(self.rows)))
                return {"rows": list(self.rows)}

            def save_provider_source_run(self, payload):
                calls.append(("save_run", payload["trade_date"], payload["row_count"]))
                return len(calls)

            def upsert_price_band_style_daily(self, row):
                calls.append(("upsert", row["trade_date"]))
                self.rows = [
                    existing for existing in self.rows
                    if existing["trade_date"] != row["trade_date"]
                ] + [dict(row)]
                self.rows.sort(key=lambda item: item["trade_date"])
                return row

        service = FakeService()

        class FakeDatabaseService:
            @classmethod
            def sqlite_d1_compatible(cls, db_path=None):
                calls.append(("db", db_path))
                return service

        result = get_price_band_style_series_from_tushare_first(
            "2026-05-20",
            window_days=3,
            db_path="daily.db",
            database_service_cls=FakeDatabaseService,
            fetch_tushare_open_trade_dates_fn=lambda start_date, end_date: trade_dates,
            fetch_tushare_ths_daily_fn=lambda trade_date: [
                {"ts_code": "883916.TI", "trade_date": trade_date.replace("-", ""), "pct_change": 1.0},
                {"ts_code": "883960.TI", "trade_date": trade_date.replace("-", ""), "pct_change": 0.2},
            ],
        )

        self.assertEqual([row["trade_date"] for row in result["rows"]], trade_dates)
        self.assertIn(("upsert", "2026-05-18"), calls)
        self.assertIn(("upsert", "2026-05-19"), calls)

    def test_top50_turnover_share_series_uses_existing_database_service(self):
        calls = []

        class FakeDatabaseService:
            @classmethod
            def sqlite_d1_compatible(cls, db_path=None):
                calls.append(("sqlite_d1_compatible", db_path))
                return cls()

            def query_top_turnover_share_series(self, end_date, *, window_days=30, limit=50, rank_scope="all_a"):
                calls.append(("query", end_date, window_days, limit, rank_scope))
                return {
                    "rows": [
                        {
                            "trade_date": "2026-05-18",
                            "top_amount_yi": 6150.0,
                            "market_amount_yi": 30000.0,
                            "share_pct": 20.5,
                        }
                    ]
                }

        result = get_top50_turnover_share_series_from_tushare_first(
            "2026-05-18",
            window_days=25,
            limit=50,
            db_path="daily.db",
            database_service_cls=FakeDatabaseService,
        )

        self.assertEqual(result["rows"][0]["share_pct"], 20.5)
        self.assertEqual(
            calls,
            [
                ("sqlite_d1_compatible", "daily.db"),
                ("query", "2026-05-18", 25, 50, "all_a"),
            ],
        )

    def test_top50_turnover_share_series_refreshes_target_date_when_database_is_stale(self):
        calls = []

        class FakeDatabaseService:
            refreshed = False

            @classmethod
            def sqlite_d1_compatible(cls, db_path=None):
                calls.append(("sqlite_d1_compatible", db_path))
                return cls()

            def query_top_turnover_share_series(self, end_date, *, window_days=30, limit=50, rank_scope="all_a"):
                calls.append(("query", end_date, window_days, limit, rank_scope, self.refreshed))
                latest_date = "2026-05-20" if self.refreshed else "2026-05-19"
                return {
                    "rows": [
                        {
                            "trade_date": latest_date,
                            "top_amount_yi": 6150.0,
                            "market_amount_yi": 30000.0,
                            "share_pct": 20.5,
                        }
                    ]
                }

            def save_provider_source_run(self, payload):
                calls.append(("save_run", payload["trade_date"], payload["row_count"]))
                return 7

            def upsert_stock_daily_quotes_recent(self, rows, *, source_run_id=0):
                calls.append(("upsert", len(rows), source_run_id))
                return len(rows)

            def rebuild_market_daily_total(self, trade_date, *, source_run_id=0):
                calls.append(("rebuild_total", trade_date, source_run_id))
                return {}

            def rebuild_turnover_rank_daily(self, trade_date, *, rank_limit=100, source_run_id=0, rank_scope="all_a"):
                calls.append(("rebuild_rank", trade_date, rank_limit, source_run_id, rank_scope))
                self.refreshed = True
                return []

        result = get_top50_turnover_share_series_from_tushare_first(
            "2026-05-20",
            window_days=25,
            limit=50,
            db_path="daily.db",
            database_service_cls=FakeDatabaseService,
            fetch_stock_daily_turnover_records_fn=lambda trade_date: [
                {"trade_date": trade_date, "ts_code": "000001.SZ", "stock_code": "000001", "amount_yi": 1.0}
            ],
        )

        self.assertEqual(result["rows"][-1]["trade_date"], "2026-05-20")
        self.assertEqual(
            calls,
            [
                ("sqlite_d1_compatible", "daily.db"),
                ("query", "2026-05-20", 25, 50, "all_a", False),
                ("save_run", "2026-05-20", 1),
                ("upsert", 1, 7),
                ("rebuild_total", "2026-05-20", 7),
                ("rebuild_rank", "2026-05-20", 100, 7, "all_a"),
                ("query", "2026-05-20", 25, 50, "all_a", True),
            ],
        )

    def test_new_high_feedback_uses_tushare_stk_factor_pro_topdays(self):
        class FactorPro:
            def __init__(self):
                self.calls = []

            def stk_factor_pro(self, **kwargs):
                self.calls.append(kwargs)
                return _FakeFrame(
                    [
                        {
                            "ts_code": "000001.SZ",
                            "trade_date": "20260518",
                            "close": 12.3,
                            "high": 12.8,
                            "pct_chg": 5.2,
                            "amount": 2500000,
                            "topdays": 260,
                        },
                        {
                            "ts_code": "000002.SZ",
                            "trade_date": "20260518",
                            "close": 10,
                            "high": 10.1,
                            "pct_chg": 1.0,
                            "amount": 900000,
                            "topdays": 249,
                        },
                    ]
                )

        pro = FactorPro()
        result = get_new_high_feedback_from_tushare_first(
            "2026-05-18",
            pro=pro,
            fetch_stock_basic_map_fn=lambda: {
                "000001": {"name": "趋势一号", "industry": "半导体", "list_date": "20200102"},
                "000002": {"name": "未新高", "industry": "机器人", "list_date": "20200102"},
            },
            stock_risk_map={},
        )

        self.assertEqual(pro.calls[0]["trade_date"], "20260518")
        self.assertIn("topdays", pro.calls[0]["fields"])
        self.assertTrue(result["available"])
        self.assertEqual(result["new_high_count"], 1)
        self.assertEqual(result["top_stocks"][0]["name"], "趋势一号")
        self.assertEqual(result["sector_distribution"][0]["sector"], "半导体")

    def test_new_high_feedback_keeps_target_date_empty_instead_of_previous_day_substitute(self):
        calls = []

        def fake_factor_rows(trade_date, *, pro=None):
            calls.append(("factor", trade_date))
            if trade_date == "2026-05-20":
                return []
            if trade_date == "2026-05-19":
                return [
                    {
                        "ts_code": "000001.SZ",
                        "trade_date": "20260519",
                        "close": 12.3,
                        "high": 12.8,
                        "pct_chg": 5.2,
                        "amount": 2500000,
                        "topdays": 260,
                    }
                ]
            return []

        class FakeNoDatabaseService:
            @classmethod
            def sqlite_d1_compatible(cls, db_path=None):
                return None

        result = get_new_high_feedback_from_tushare_first(
            "2026-05-20",
            fetch_stock_factor_pro_rows_fn=fake_factor_rows,
            fetch_tushare_open_trade_dates_fn=lambda start_date, end_date: [
                "2026-05-16",
                "2026-05-19",
                "2026-05-20",
            ],
            fetch_stock_basic_map_fn=lambda: {
                "000001": {"name": "趋势一号", "industry": "半导体", "list_date": "20200102"},
            },
            stock_risk_map={},
            database_service_cls=FakeNoDatabaseService,
        )

        self.assertFalse(result["available"])
        self.assertEqual(result["status"], "upstream_empty")
        self.assertEqual(result["requested_trade_date"], "2026-05-20")
        self.assertEqual(result["factor_trade_date"], "2026-05-20")
        self.assertIn("2026-05-20", result["message"])
        self.assertNotIn("2026-05-19", result["message"])
        self.assertEqual(result["new_high_count"], 0)
        self.assertEqual(calls, [("factor", "2026-05-20")])

    def test_new_high_feedback_uses_recent_quotes_when_factor_rows_empty(self):
        calls = []

        class FakeService:
            def query_new_high_feedback_series(self, end_date, *, window_days=25):
                calls.append(("query", end_date, window_days))
                return [{"trade_date": "2026-05-20", "new_high_count": 2, "all_a_share_pct": 0.04}]

            def build_new_high_feedback_from_recent_quotes(self, trade_date, **kwargs):
                calls.append(("quote_builder", trade_date, kwargs.get("history_rows")))
                return {
                    "available": True,
                    "source": "storage.stock_daily_quotes_recent.high_break",
                    "new_high_count": 1,
                    "all_a_share_pct": 0.02,
                    "leading_sectors": "半导体",
                    "sector_distribution": [{"sector": "半导体", "new_high_count": 1}],
                    "top_stocks": [],
                    "trend_rows": [
                        {"trade_date": "2026-05-20", "new_high_count": 2, "all_a_share_pct": 0.04},
                        {"trade_date": "2026-05-21", "new_high_count": 1, "all_a_share_pct": 0.02},
                    ],
                }

            def upsert_new_high_feedback_daily(self, row):
                calls.append(("upsert", row.get("trade_date"), row.get("source_policy") or row.get("source")))
                return row

        class FakeDatabaseService:
            @classmethod
            def sqlite_d1_compatible(cls, db_path=None):
                calls.append(("db", db_path))
                return FakeService()

        result = get_new_high_feedback_from_tushare_first(
            "2026-05-21",
            fetch_stock_factor_pro_rows_fn=lambda trade_date: calls.append(("factor", trade_date)) or [],
            fetch_stock_basic_map_fn=lambda: {},
            fetch_tushare_open_trade_dates_fn=lambda start_date, end_date: ["2026-05-20", "2026-05-21"],
            database_service_cls=FakeDatabaseService,
            db_path="daily.db",
        )

        self.assertTrue(result["available"])
        self.assertEqual(result["source"], "storage.stock_daily_quotes_recent.high_break")
        self.assertEqual(result["new_high_count"], 1)
        self.assertEqual(result["requested_trade_date"], "2026-05-21")
        self.assertIn(
            ("quote_builder", "2026-05-21", [{"trade_date": "2026-05-20", "new_high_count": 2, "all_a_share_pct": 0.04}]),
            calls,
        )
        self.assertIn(("upsert", "2026-05-21", "storage.stock_daily_quotes_recent.high_break"), calls)

    def test_new_high_feedback_uses_recent_quotes_when_factor_fetch_times_out(self):
        calls = []

        class FakeService:
            def query_new_high_feedback_series(self, end_date, *, window_days=25):
                calls.append(("query", end_date, window_days))
                return [{"trade_date": "2026-05-22", "new_high_count": 267, "all_a_share_pct": 4.85}]

            def build_new_high_feedback_from_recent_quotes(self, trade_date, **kwargs):
                calls.append(("quote_builder", trade_date, kwargs.get("history_rows")))
                return {
                    "available": True,
                    "source": "storage.stock_daily_quotes_recent.high_break",
                    "new_high_count": 276,
                    "all_a_share_pct": 5.01,
                    "leading_sectors": "半导体",
                    "sector_distribution": [{"sector": "半导体", "new_high_count": 35}],
                    "top_stocks": [],
                    "trend_rows": [
                        {"trade_date": "2026-05-22", "new_high_count": 267, "all_a_share_pct": 4.85},
                        {"trade_date": "2026-05-25", "new_high_count": 276, "all_a_share_pct": 5.01},
                    ],
                }

            def upsert_new_high_feedback_daily(self, row):
                calls.append(("upsert", row.get("trade_date"), row.get("source_policy") or row.get("source")))
                return row

        class FakeDatabaseService:
            @classmethod
            def sqlite_d1_compatible(cls, db_path=None):
                calls.append(("db", db_path))
                return FakeService()

        def factor_timeout(trade_date):
            calls.append(("factor", trade_date))
            raise TimeoutError("stk_factor_pro timeout")

        result = get_new_high_feedback_from_tushare_first(
            "2026-05-25",
            fetch_stock_factor_pro_rows_fn=factor_timeout,
            fetch_stock_basic_map_fn=lambda: {},
            stock_risk_map={},
            database_service_cls=FakeDatabaseService,
            db_path="daily.db",
        )

        self.assertTrue(result["available"])
        self.assertEqual(result["source"], "storage.stock_daily_quotes_recent.high_break")
        self.assertEqual(result["new_high_count"], 276)
        self.assertIn("stk_factor_pro timeout", result["factor_error"])
        self.assertIn(
            ("quote_builder", "2026-05-25", [{"trade_date": "2026-05-22", "new_high_count": 267, "all_a_share_pct": 4.85}]),
            calls,
        )
        self.assertIn(("upsert", "2026-05-25", "storage.stock_daily_quotes_recent.high_break"), calls)

    def test_new_high_feedback_builds_risk_map_before_recent_quotes_fallback(self):
        calls = []

        class FakeService:
            def query_new_high_feedback_series(self, end_date, *, window_days=25):
                return [{"trade_date": "2026-05-20", "new_high_count": 2, "all_a_share_pct": 0.04}]

            def build_new_high_feedback_from_recent_quotes(self, trade_date, **kwargs):
                calls.append(("quote_builder_risk", kwargs.get("stock_risk_map")))
                return {
                    "available": True,
                    "source": "storage.stock_daily_quotes_recent.high_break",
                    "new_high_count": 1,
                    "all_a_share_pct": 0.02,
                    "leading_sectors": "半导体",
                    "trend_rows": [
                        {"trade_date": "2026-05-20", "new_high_count": 2, "all_a_share_pct": 0.04},
                        {"trade_date": "2026-05-21", "new_high_count": 1, "all_a_share_pct": 0.02},
                    ],
                }

            def upsert_new_high_feedback_daily(self, row):
                return row

        class FakeDatabaseService:
            @classmethod
            def sqlite_d1_compatible(cls, db_path=None):
                return FakeService()

        result = get_new_high_feedback_from_tushare_first(
            "2026-05-21",
            fetch_stock_factor_pro_rows_fn=lambda trade_date: [],
            fetch_stock_basic_map_fn=lambda: {},
            database_service_cls=FakeDatabaseService,
            fetch_stock_risk_map_fn=lambda target_date: {"000001": {"risk_flags": ["st_warning"]}},
        )

        self.assertTrue(result["available"])
        self.assertIn(("quote_builder_risk", {"000001": {"risk_flags": ["st_warning"]}}), calls)

    def test_new_high_feedback_reads_history_rows_from_fact_db(self):
        calls = []

        class FakeDatabaseService:
            @classmethod
            def sqlite_d1_compatible(cls, db_path=None):
                calls.append(("db", db_path))
                return cls()

            def query_new_high_feedback_series(self, end_date, *, window_days=25):
                calls.append(("query", end_date, window_days))
                return [
                    {
                        "trade_date": "2026-05-19",
                        "new_high_count": 100,
                        "all_a_share_pct": 2.0,
                        "leading_sectors": "机器人",
                    }
                ]

        result = get_new_high_feedback_from_tushare_first(
            "2026-05-20",
            fetch_stock_factor_pro_rows_fn=lambda trade_date: [
                {
                    "ts_code": "000001.SZ",
                    "trade_date": "20260520",
                    "close": 12.3,
                    "high": 12.8,
                    "pct_chg": 5.2,
                    "amount": 2500000,
                    "topdays": 260,
                }
            ],
            fetch_stock_basic_map_fn=lambda: {
                "000001": {"name": "趋势一号", "industry": "半导体", "list_date": "20200102"},
            },
            stock_risk_map={},
            database_service_cls=FakeDatabaseService,
            db_path="daily.db",
            fetch_tushare_open_trade_dates_fn=lambda start_date, end_date: [],
        )

        self.assertEqual([row["trade_date"] for row in result["trend_rows"]], ["2026-05-19", "2026-05-20"])
        self.assertEqual(result["trend_rows"][-1]["change_text"], "-99")
        self.assertEqual(calls, [("db", "daily.db"), ("query", "2026-05-20", 25)])

    def test_new_high_feedback_rebuilds_fact_db_history_when_index_is_stale(self):
        calls = []

        class FakeService:
            rebuilt = False

            def query_new_high_feedback_series(self, end_date, *, window_days=25):
                calls.append(("query", end_date, window_days, self.rebuilt))
                if not self.rebuilt:
                    return [{"trade_date": "2026-05-11", "new_high_count": 80, "all_a_share_pct": 1.6}]
                return [{"trade_date": "2026-05-19", "new_high_count": 100, "all_a_share_pct": 2.0}]

        service = FakeService()

        class FakeDatabaseService:
            @classmethod
            def sqlite_d1_compatible(cls, db_path=None):
                calls.append(("db", db_path))
                return service

        def ensure_index(**kwargs):
            calls.append(("ensure", kwargs["end_date"], kwargs["window_days"], kwargs["max_scan_days"], kwargs.get("db_path")))
            service.rebuilt = True
            return {"indexed_count": 1}

        result = get_new_high_feedback_from_tushare_first(
            "2026-05-20",
            fetch_stock_factor_pro_rows_fn=lambda trade_date: [
                {
                    "ts_code": "000001.SZ",
                    "trade_date": "20260520",
                    "close": 12.3,
                    "high": 12.8,
                    "pct_chg": 5.2,
                    "amount": 2500000,
                    "topdays": 260,
                }
            ],
            fetch_stock_basic_map_fn=lambda: {
                "000001": {"name": "趋势一号", "industry": "半导体", "list_date": "20200102"},
            },
            stock_risk_map={},
            database_service_cls=FakeDatabaseService,
            ensure_daily_metric_history_index_fn=ensure_index,
            db_path="daily.db",
            fetch_tushare_open_trade_dates_fn=lambda start_date, end_date: [],
        )

        self.assertEqual([row["trade_date"] for row in result["trend_rows"]], ["2026-05-19", "2026-05-20"])
        self.assertEqual(
            calls,
            [
                ("db", "daily.db"),
                ("query", "2026-05-20", 25, False),
                ("ensure", "2026-05-20", 25, 60, "daily.db"),
                ("db", "daily.db"),
                ("query", "2026-05-20", 25, True),
            ],
        )

    def test_new_high_feedback_rebuilds_fact_db_history_when_index_is_empty(self):
        calls = []

        class FakeService:
            rebuilt = False

            def query_new_high_feedback_series(self, end_date, *, window_days=25):
                calls.append(("query", end_date, window_days, self.rebuilt))
                if not self.rebuilt:
                    return []
                return [{"trade_date": "2026-05-19", "new_high_count": 100, "all_a_share_pct": 2.0}]

        service = FakeService()

        class FakeDatabaseService:
            @classmethod
            def sqlite_d1_compatible(cls, db_path=None):
                calls.append(("db", db_path))
                return service

        def ensure_index(**kwargs):
            calls.append(("ensure", kwargs["end_date"], kwargs["window_days"], kwargs["max_scan_days"], kwargs.get("db_path")))
            service.rebuilt = True
            return {"indexed_count": 1}

        result = get_new_high_feedback_from_tushare_first(
            "2026-05-20",
            fetch_stock_factor_pro_rows_fn=lambda trade_date: [
                {
                    "ts_code": "000001.SZ",
                    "trade_date": "20260520",
                    "pct_chg": 5.2,
                    "amount": 2500000,
                    "topdays": 260,
                }
            ],
            fetch_stock_basic_map_fn=lambda: {
                "000001": {"name": "趋势一号", "industry": "半导体", "list_date": "20200102"},
            },
            stock_risk_map={},
            database_service_cls=FakeDatabaseService,
            ensure_daily_metric_history_index_fn=ensure_index,
            db_path="daily.db",
            fetch_tushare_open_trade_dates_fn=lambda start_date, end_date: [],
        )

        self.assertEqual([row["trade_date"] for row in result["trend_rows"]], ["2026-05-19", "2026-05-20"])
        self.assertEqual(
            calls,
            [
                ("db", "daily.db"),
                ("query", "2026-05-20", 25, False),
                ("ensure", "2026-05-20", 25, 60, "daily.db"),
                ("db", "daily.db"),
                ("query", "2026-05-20", 25, True),
            ],
        )

    def test_new_high_feedback_rebuilds_fact_db_history_when_rows_include_non_trade_dates(self):
        calls = []

        class FakeService:
            rebuilt = False
            pruned = False

            def query_new_high_feedback_series(self, end_date, *, window_days=25):
                calls.append(("query", end_date, window_days, self.rebuilt))
                if not self.rebuilt:
                    return [
                        {"trade_date": "2026-05-16", "new_high_count": 1, "all_a_share_pct": 0.02},
                        {"trade_date": "2026-05-17", "new_high_count": 1, "all_a_share_pct": 0.02},
                        {"trade_date": "2026-05-19", "new_high_count": 164, "all_a_share_pct": 3.28},
                    ]
                return [
                    {"trade_date": "2026-05-15", "new_high_count": 130, "all_a_share_pct": 2.6},
                    {"trade_date": "2026-05-18", "new_high_count": 132, "all_a_share_pct": 2.64},
                    {"trade_date": "2026-05-19", "new_high_count": 164, "all_a_share_pct": 3.28},
                ]

            def delete_new_high_feedback_outside_dates(self, valid_dates, *, end_date=None):
                calls.append(("delete_outside", tuple(valid_dates), end_date))
                self.pruned = True

        service = FakeService()

        class FakeDatabaseService:
            @classmethod
            def sqlite_d1_compatible(cls, db_path=None):
                calls.append(("db", db_path))
                return service

        def ensure_index(**kwargs):
            calls.append(("ensure", kwargs["end_date"], tuple(kwargs.get("candidate_dates") or [])))
            service.rebuilt = True
            return {"indexed_count": 3}

        result = get_new_high_feedback_from_tushare_first(
            "2026-05-20",
            fetch_stock_factor_pro_rows_fn=lambda trade_date: [
                {
                    "ts_code": "000001.SZ",
                    "trade_date": "20260520",
                    "pct_chg": 5.2,
                    "amount": 2500000,
                    "topdays": 260,
                }
            ],
            fetch_tushare_open_trade_dates_fn=lambda start_date, end_date: [
                "2026-05-15",
                "2026-05-18",
                "2026-05-19",
                "2026-05-20",
            ],
            fetch_stock_basic_map_fn=lambda: {
                "000001": {"name": "趋势一号", "industry": "半导体", "list_date": "20200102"},
            },
            stock_risk_map={},
            database_service_cls=FakeDatabaseService,
            ensure_daily_metric_history_index_fn=ensure_index,
            db_path="daily.db",
        )

        trend_dates = [row["trade_date"] for row in result["trend_rows"]]
        self.assertEqual(trend_dates, ["2026-05-15", "2026-05-18", "2026-05-19", "2026-05-20"])
        self.assertNotIn("2026-05-16", trend_dates)
        self.assertIn(
            ("ensure", "2026-05-20", ("2026-05-15", "2026-05-18", "2026-05-19", "2026-05-20")),
            calls,
        )
        self.assertIn(
            (
                "delete_outside",
                ("2026-05-15", "2026-05-18", "2026-05-19", "2026-05-20"),
                "2026-05-20",
            ),
            calls,
        )
        self.assertTrue(service.pruned)

    def test_new_high_feedback_uses_trade_calendar_by_default_for_fact_db_history(self):
        calls = []

        class FakeService:
            rebuilt = False

            def query_new_high_feedback_series(self, end_date, *, window_days=25):
                calls.append(("query", end_date, window_days, self.rebuilt))
                if not self.rebuilt:
                    return [
                        {"trade_date": "2026-05-16", "new_high_count": 1, "all_a_share_pct": 0.02},
                        {"trade_date": "2026-05-17", "new_high_count": 1, "all_a_share_pct": 0.02},
                        {"trade_date": "2026-05-19", "new_high_count": 164, "all_a_share_pct": 3.28},
                    ]
                return [
                    {"trade_date": "2026-05-15", "new_high_count": 130, "all_a_share_pct": 2.6},
                    {"trade_date": "2026-05-18", "new_high_count": 132, "all_a_share_pct": 2.64},
                    {"trade_date": "2026-05-19", "new_high_count": 164, "all_a_share_pct": 3.28},
                ]

            def delete_new_high_feedback_outside_dates(self, valid_dates, *, end_date=None):
                calls.append(("delete_outside", tuple(valid_dates), end_date))

        service = FakeService()

        class FakeDatabaseService:
            @classmethod
            def sqlite_d1_compatible(cls, db_path=None):
                calls.append(("db", db_path))
                return service

        def ensure_index(**kwargs):
            calls.append(("ensure", kwargs["end_date"], tuple(kwargs.get("candidate_dates") or [])))
            service.rebuilt = True
            return {"indexed_count": 3}

        with patch(
            "input.tushare_runtime.fetch_tushare_open_trade_dates",
            lambda start_date, end_date: [
                "2026-05-15",
                "2026-05-18",
                "2026-05-19",
                "2026-05-20",
            ],
        ):
            result = get_new_high_feedback_from_tushare_first(
                "2026-05-20",
                fetch_stock_factor_pro_rows_fn=lambda trade_date: [
                    {
                        "ts_code": "000001.SZ",
                        "trade_date": "20260520",
                        "pct_chg": 5.2,
                        "amount": 2500000,
                        "topdays": 260,
                    }
                ],
                fetch_stock_basic_map_fn=lambda: {
                    "000001": {"name": "趋势一号", "industry": "半导体", "list_date": "20200102"},
                },
                stock_risk_map={},
                database_service_cls=FakeDatabaseService,
                ensure_daily_metric_history_index_fn=ensure_index,
                db_path="daily.db",
            )

        trend_dates = [row["trade_date"] for row in result["trend_rows"]]
        self.assertEqual(trend_dates, ["2026-05-15", "2026-05-18", "2026-05-19", "2026-05-20"])
        self.assertNotIn("2026-05-16", trend_dates)
        self.assertIn(
            ("ensure", "2026-05-20", ("2026-05-15", "2026-05-18", "2026-05-19", "2026-05-20")),
            calls,
        )

    def test_stock_risk_map_normalizes_st_reduction_announcements_and_shock_rows(self):
        result = get_stock_risk_map_from_tushare_first(
            "2026-05-18",
            fetch_tushare_st_rows_fn=lambda trade_date: [
                {
                    "ts_code": "000001.SZ",
                    "name": "风险样本",
                    "pub_date": "20260517",
                    "imp_date": "20260518",
                    "st_reason": "实施其他风险警示",
                    "st_explain": "公司内部控制被出具否定意见",
                }
            ],
            fetch_tushare_stock_st_rows_fn=lambda trade_date: [
                {"ts_code": "000001.SZ", "name": "风险样本", "trade_date": "20260518"}
            ],
            fetch_tushare_holdertrade_rows_fn=lambda trade_date: [
                {
                    "ts_code": "000002.SZ",
                    "ann_date": "20260518",
                    "holder_name": "控股股东",
                    "trade_type": "DE",
                    "change_ratio": 2.5,
                }
            ],
            fetch_tushare_announcement_rows_fn=lambda trade_date: [
                {
                    "ts_code": "000003.SZ",
                    "ann_date": "20260518",
                    "title": "关于控股股东减持计划的预披露公告",
                    "url": "https://example.invalid/reduce.pdf",
                }
            ],
            fetch_tushare_shock_rows_fn=lambda trade_date: [
                {
                    "ts_code": "000004.SZ",
                    "trade_date": "20260518",
                    "type": "异常波动",
                    "reason": "连续三个交易日涨幅偏离值累计超过20%",
                }
            ],
        )

        self.assertIn("st_warning", result["000001"]["risk_flags"])
        self.assertIn("holder_reduce", result["000002"]["risk_flags"])
        self.assertIn("holder_reduce_announcement", result["000003"]["risk_flags"])
        self.assertIn("abnormal_volatility", result["000004"]["risk_flags"])
        self.assertIn("实施其他风险警示", result["000001"]["risk_summary"])
        self.assertIn("减持", result["000002"]["risk_summary"])
        self.assertEqual(result["000003"]["risk_events"][0]["url"], "https://example.invalid/reduce.pdf")

    def test_stock_risk_map_merges_cyberfininvest_news_risks(self):
        result = get_stock_risk_map_from_tushare_first(
            "2026-05-18",
            fetch_tushare_st_rows_fn=lambda trade_date: [],
            fetch_tushare_stock_st_rows_fn=lambda trade_date: [],
            fetch_tushare_holdertrade_rows_fn=lambda trade_date: [],
            fetch_tushare_announcement_rows_fn=lambda trade_date: [],
            fetch_tushare_shock_rows_fn=lambda trade_date: [],
            fetch_cyberfininvest_news_rows_fn=lambda trade_date: [
                {
                    "title": "博实股份：股东联创未来拟减持不超过3%股份",
                    "summary": "股东拟减持公司股份。",
                    "stocks": [{"code": "002698", "name": "博实股份"}],
                    "createTime": "2026-05-18T20:44:29",
                    "appUrl": "https://news.example.invalid/a",
                },
                {
                    "title": "大普微：公司股票将于5月19日停牌核查",
                    "summary": "股票交易异常波动，停牌核查。",
                    "stocks": [{"code": "301666", "name": "大普微"}],
                    "createTime": "2026-05-18T20:10:23",
                },
                {
                    "title": "*ST观典：公司股票5月19日进入退市整理期",
                    "stocks": [{"code": "688287", "name": "*ST观典"}],
                    "createTime": "2026-05-18T18:41:07",
                },
            ],
        )

        self.assertIn("holder_reduce_announcement", result["002698"]["risk_flags"])
        self.assertIn("abnormal_volatility", result["301666"]["risk_flags"])
        self.assertIn("delist_risk", result["688287"]["risk_flags"])
        self.assertIn("cyberfininvest.news", result["002698"]["source_endpoints"])
        self.assertEqual(result["002698"]["risk_events"][0]["url"], "https://news.example.invalid/a")
        self.assertIn("停牌核查", result["301666"]["risk_summary"])

    def test_stock_risk_map_merges_investor_qa_theme_clarification_before_daily_report(self):
        result = get_stock_risk_map_from_tushare_first(
            "2026-05-22",
            fetch_tushare_st_rows_fn=lambda trade_date: [],
            fetch_tushare_stock_st_rows_fn=lambda trade_date: [],
            fetch_tushare_holdertrade_rows_fn=lambda trade_date: [],
            fetch_tushare_announcement_rows_fn=lambda trade_date: [],
            fetch_tushare_shock_rows_fn=lambda trade_date: [],
            fetch_cyberfininvest_news_rows_fn=lambda trade_date: [],
            fetch_investor_qa_rows_fn=lambda trade_date: [
                {
                    "code": "002580",
                    "name": "圣阳股份",
                    "source": "同花顺金融研究中心问董秘",
                    "question": "公司在AIDC数据中心的专用电源和储能系统和美国客户有合作吗",
                    "answer": "截至目前，公司在AIDC数据中心领域尚未与美国客户达成合作。",
                    "pub_date": "2026-05-22",
                    "url": "https://example.invalid/qa",
                }
            ],
        )

        self.assertIn("hype_expectation_downgrade", result["002580"]["risk_flags"])
        self.assertIn("尚未与美国客户达成合作", result["002580"]["risk_summary"])
        self.assertIn("investor_qa", result["002580"]["source_endpoints"])
        self.assertEqual(result["002580"]["risk_events"][0]["source"], "同花顺金融研究中心问董秘")

    def test_stock_risk_map_uses_default_investor_qa_fetcher_for_daily_pre_risk_snapshot(self):
        with patch.object(
            tushare_runtime,
            "fetch_investor_qa_rows",
            lambda trade_date: [
                {
                    "code": "002580",
                    "name": "圣阳股份",
                    "source": "同花顺金融研究中心问董秘",
                    "question": "公司在AIDC数据中心的专用电源和储能系统和美国客户有合作吗",
                    "answer": "截至目前，公司在AIDC数据中心领域尚未与美国客户达成合作。",
                    "pub_date": "2026-05-22",
                }
            ],
        ):
            result = get_stock_risk_map_from_tushare_first(
                "2026-05-22",
                fetch_tushare_st_rows_fn=lambda trade_date: [],
                fetch_tushare_stock_st_rows_fn=lambda trade_date: [],
                fetch_tushare_holdertrade_rows_fn=lambda trade_date: [],
                fetch_tushare_announcement_rows_fn=lambda trade_date: [],
                fetch_tushare_shock_rows_fn=lambda trade_date: [],
                fetch_cyberfininvest_news_rows_fn=lambda trade_date: [],
            )

        self.assertIn("hype_expectation_downgrade", result["002580"]["risk_flags"])
        self.assertIn("尚未与美国客户达成合作", result["002580"]["risk_summary"])

    def test_stock_risk_map_default_investor_qa_fetcher_uses_recent_window(self):
        captured = {}

        def fake_fetcher(trade_date, **kwargs):
            captured["trade_date"] = trade_date
            captured.update(kwargs)
            return []

        with patch.object(tushare_runtime, "fetch_investor_qa_rows", fake_fetcher):
            get_stock_risk_map_from_tushare_first(
                "2026-05-22",
                fetch_tushare_st_rows_fn=lambda trade_date: [],
                fetch_tushare_stock_st_rows_fn=lambda trade_date: [],
                fetch_tushare_holdertrade_rows_fn=lambda trade_date: [],
                fetch_tushare_announcement_rows_fn=lambda trade_date: [],
                fetch_tushare_shock_rows_fn=lambda trade_date: [],
                fetch_cyberfininvest_news_rows_fn=lambda trade_date: [],
            )

        self.assertEqual(captured["trade_date"], "2026-05-22")
        self.assertEqual(captured["lookback_trade_days"], 10)

    def test_stock_risk_map_ignores_future_cyberfininvest_news_in_replay(self):
        result = get_stock_risk_map_from_tushare_first(
            "2026-05-18",
            fetch_tushare_st_rows_fn=lambda trade_date: [],
            fetch_tushare_stock_st_rows_fn=lambda trade_date: [],
            fetch_tushare_holdertrade_rows_fn=lambda trade_date: [],
            fetch_tushare_announcement_rows_fn=lambda trade_date: [],
            fetch_tushare_shock_rows_fn=lambda trade_date: [],
            fetch_cyberfininvest_news_rows_fn=lambda trade_date: [
                {
                    "title": "未来样本：股东拟减持不超过3%股份",
                    "stocks": [{"code": "002699", "name": "未来样本"}],
                    "createTime": "2026-05-19T20:44:29",
                }
            ],
        )

        self.assertEqual(result, {})

    def test_stock_risk_map_ignores_st_history_far_before_target_without_daily_st_membership(self):
        result = get_stock_risk_map_from_tushare_first(
            "2026-05-18",
            fetch_tushare_st_rows_fn=lambda trade_date: [
                {
                    "ts_code": "000005.SZ",
                    "name": "旧风险样本",
                    "pub_date": "20200101",
                    "imp_date": "20200102",
                    "st_reason": "历史其他风险警示",
                }
            ],
            fetch_tushare_stock_st_rows_fn=lambda trade_date: [],
            fetch_tushare_holdertrade_rows_fn=lambda trade_date: [],
            fetch_tushare_announcement_rows_fn=lambda trade_date: [],
            fetch_tushare_shock_rows_fn=lambda trade_date: [],
        )

        self.assertEqual(result, {})

    def test_total_turnover_uses_tushare_daily_before_legacy_fallback(self):
        fallback_calls = []

        result = get_total_turnover_from_tushare_first(
            "2026-05-13",
            fetch_stock_daily_turnover_records_fn=lambda trade_date: [
                {"amount_yi": 120.5},
                {"amount_yi": 80.25},
            ],
            legacy_get_total_turnover_fn=lambda target_date=None: fallback_calls.append(target_date) or 0.0,
        )

        self.assertEqual(result, 200.75)
        self.assertEqual(fallback_calls, [])
        self.assertEqual(result.data_source, "tushare.daily")
        self.assertEqual(result.source_endpoint, "daily")
        self.assertEqual(result.source_row_count, 2)
        self.assertEqual(result.source_retry_count, 0)

    def test_total_turnover_retries_tushare_empty_before_legacy_fallback(self):
        fallback_calls = []
        tushare_calls = []

        result = get_total_turnover_from_tushare_first(
            "2026-05-13",
            fetch_stock_daily_turnover_records_fn=lambda trade_date: tushare_calls.append(trade_date) or [],
            legacy_get_total_turnover_fn=lambda target_date=None: fallback_calls.append(target_date) or 88.0,
        )

        self.assertEqual(result, 88.0)
        self.assertEqual(fallback_calls, ["2026-05-13"])
        self.assertEqual(tushare_calls, ["2026-05-13", "2026-05-13"])
        self.assertEqual(result.data_source, "legacy.total_turnover")
        self.assertEqual(result.source_endpoint, "fallback")
        self.assertEqual(result.source_row_count, 0)
        self.assertEqual(result.source_retry_count, 1)

    def test_major_indices_use_tushare_index_daily_before_legacy_fallback(self):
        fallback_calls = []
        bars_by_code = {
            "000001": [
                {"date": "2026-05-12", "open": 3300, "high": 3330, "low": 3290, "close": 3310},
                {"date": "2026-05-13", "open": 3310, "high": 3360, "low": 3305, "close": 3350},
            ],
            "399001": [
                {"date": "2026-05-12", "open": 10000, "high": 10100, "low": 9980, "close": 10050},
                {"date": "2026-05-13", "open": 10050, "high": 10200, "low": 10020, "close": 10150},
            ],
            "399006": [
                {"date": "2026-05-12", "open": 2100, "high": 2130, "low": 2090, "close": 2120},
                {"date": "2026-05-13", "open": 2120, "high": 2180, "low": 2110, "close": 2170},
            ],
        }

        result = get_major_indices_from_tushare_first(
            "2026-05-13",
            fetch_daily_price_bars_fn=lambda code, start_date, end_date, is_index=False: list(bars_by_code[code]),
            legacy_get_major_indices_fn=lambda target_date=None: fallback_calls.append(target_date) or {},
        )

        self.assertEqual(set(result), {"上证指数", "深证成指", "创业板指"})
        self.assertEqual(result["上证指数"]["data_source"], "tushare.index_daily")
        self.assertAlmostEqual(result["上证指数"]["change_pct"], (3350 - 3310) / 3310 * 100)
        self.assertEqual(fallback_calls, [])

    def test_wind_a_uses_tushare_index_daily_before_legacy_fallback(self):
        fallback_calls = []

        result = get_wind_a_from_tushare_first(
            "2026-05-13",
            fetch_daily_price_bars_fn=lambda code, start_date, end_date, is_index=False: [
                {"date": "2026-05-12", "close": 6200},
                {"date": "2026-05-13", "close": 6262},
            ],
            legacy_get_wind_a_fn=lambda target_date=None: fallback_calls.append(target_date) or {},
        )

        self.assertEqual(result["data_source"], "tushare.index_daily")
        self.assertAlmostEqual(result["change_pct"], 1.0)
        self.assertEqual(fallback_calls, [])

    def test_tushare_index_daily_uses_csi_code_for_wind_a(self):
        calls = []

        class FakePro:
            def index_daily(self, ts_code="", start_date="", end_date=""):
                calls.append((ts_code, start_date, end_date))
                return [
                    {
                        "trade_date": "20260513",
                        "open": 6200,
                        "high": 6280,
                        "low": 6190,
                        "close": 6262,
                        "vol": 100,
                    }
                ]

        rows = fetch_daily_price_bars(
            "000985",
            "2026-05-13",
            "2026-05-13",
            is_index=True,
            ts_module=object(),
            pro=FakePro(),
        )

        self.assertEqual(calls[0][0], "000985.CSI")
        self.assertEqual(rows[0]["data_source"], "tushare.index_daily")

    def test_turnover_rank_uses_tushare_daily_before_legacy_fallback(self):
        fallback_calls = []

        result = get_turnover_rank_from_tushare_first(
            "2026-05-13",
            limit=2,
            fetch_stock_daily_turnover_records_fn=lambda trade_date: [
                {"ts_code": "000001.SZ", "stock_code": "000001", "amount_yi": 120.5, "pct_chg": 2.1},
                {"ts_code": "600000.SH", "stock_code": "600000", "amount_yi": 320.25, "pct_chg": -1.2},
                {"ts_code": "300001.SZ", "stock_code": "300001", "amount_yi": 80.0, "pct_chg": 0.4},
            ],
            fetch_stock_name_map_fn=lambda: {"600000": "浦发银行", "000001": "平安银行"},
            fetch_stock_industry_map_fn=lambda: {"600000": "银行", "000001": "银行"},
            legacy_get_turnover_rank_fn=lambda target_date=None, limit=50: fallback_calls.append((target_date, limit)) or [],
        )

        self.assertEqual([item["code"] for item in result], ["600000", "000001"])
        self.assertEqual(result[0]["name"], "浦发银行")
        self.assertEqual(result[0]["sector"], "银行")
        self.assertEqual(result[0]["turnover"], 320.25)
        self.assertEqual(result[0]["change_pct"], -1.2)
        self.assertEqual(result[0]["data_source"], "tushare.daily")
        self.assertEqual(fallback_calls, [])

    def test_turnover_rank_falls_back_only_when_tushare_has_no_rows(self):
        fallback_calls = []

        result = get_turnover_rank_from_tushare_first(
            "2026-05-13",
            limit=2,
            fetch_stock_daily_turnover_records_fn=lambda trade_date: [],
            legacy_get_turnover_rank_fn=lambda target_date=None, limit=50: fallback_calls.append((target_date, limit)) or [
                {"code": "300750", "name": "宁德时代", "turnover": 145.1, "data_source": "eastmoney.turnover_rank"}
            ],
        )

        self.assertEqual(result[0]["code"], "300750")
        self.assertEqual(fallback_calls, [("2026-05-13", 2)])

    def test_stock_hot_rank_uses_tushare_ths_hot_before_legacy_fallback(self):
        fallback_calls = []

        result = get_stock_hot_rank_from_tushare_first(
            "2026-05-13",
            limit=2,
            fetch_tushare_ths_hot_fn=lambda trade_date=None, market="热股": [
                {
                    "ts_code": "300750.SZ",
                    "trade_date": "20260513",
                    "name": "宁德时代",
                    "pct_change": 2.5,
                    "current_price": 220.5,
                    "rank": 2,
                    "rank_time": "15:00:00",
                    "concept": "锂电池",
                },
                {
                    "ts_code": "600519.SH",
                    "trade_date": "20260513",
                    "name": "贵州茅台",
                    "pct_change": -1.2,
                    "current_price": 1500.0,
                    "rank": 1,
                    "rank_time": "15:00:00",
                    "concept": "白酒",
                },
            ],
            legacy_fetch_hot_rank_fn=lambda num=30: fallback_calls.append(num) or [],
        )

        self.assertEqual([item["code"] for item in result], ["600519", "300750"])
        self.assertEqual(result[0]["rank"], 1)
        self.assertEqual(result[0]["name"], "贵州茅台")
        self.assertEqual(result[0]["data_source"], "tushare.ths_hot")
        self.assertEqual(result[0]["market"], "热股")
        self.assertEqual(fallback_calls, [])

    def test_stock_hot_rank_falls_back_only_when_tushare_has_no_rows(self):
        fallback_calls = []

        result = get_stock_hot_rank_from_tushare_first(
            "2026-05-13",
            limit=1,
            fetch_tushare_ths_hot_fn=lambda trade_date=None, market="热股": [],
            legacy_fetch_hot_rank_fn=lambda num=30: fallback_calls.append(num) or [{"code": "000001", "name": "旧热榜"}],
        )

        self.assertEqual(result[0]["name"], "旧热榜")
        self.assertEqual(fallback_calls, [1])

    def test_stock_hot_rank_cleans_tushare_json_concepts_and_nan_reason(self):
        result = get_stock_hot_rank_from_tushare_first(
            "2024-03-15",
            limit=1,
            fetch_tushare_ths_hot_fn=lambda trade_date=None, market="热股": [
                {
                    "ts_code": "300750.SZ",
                    "trade_date": "20240315",
                    "ts_name": "宁德时代",
                    "rank": 1,
                    "concept": '["钠离子电池", "同花顺漂亮100"]',
                    "rank_reason": float("nan"),
                }
            ],
        )

        self.assertEqual(result[0]["concepts"], ["钠离子电池", "同花顺漂亮100"])
        self.assertEqual(result[0]["popularity_tag"], "")

    def test_limit_pool_snapshot_uses_tushare_limit_list_before_legacy_fallback(self):
        fallback_calls = []

        result = get_limit_pool_snapshot_from_tushare_first(
            "2026-05-13",
            fetch_tushare_limit_rows_fn=lambda trade_date: [
                {
                    "ts_code": "000001.SZ",
                    "trade_date": "20260513",
                    "name": "平安银行",
                    "industry": "银行",
                    "limit": "U",
                    "pct_chg": 10.01,
                    "amount": 123456.0,
                    "open_times": 1,
                    "up_stat": "2/1",
                    "first_time": "09:35:00",
                    "last_time": "14:55:00",
                },
                {
                    "ts_code": "000002.SZ",
                    "trade_date": "20260513",
                    "name": "万科A",
                    "industry": "地产",
                    "limit": "D",
                    "pct_chg": -10.0,
                    "amount": 65432.0,
                },
            ],
            fetch_stock_daily_turnover_records_fn=lambda trade_date: [
                {"stock_code": "000001", "pct_chg": 10.01},
                {"stock_code": "000002", "pct_chg": -10.0},
                {"stock_code": "000003", "pct_chg": 2.0},
                {"stock_code": "000004", "pct_chg": -1.0},
            ],
            legacy_get_limit_pool_snapshot_fn=lambda target_date=None: fallback_calls.append(target_date) or {},
        )

        self.assertEqual(result["provider"], "tushare.limit_list_ths")
        self.assertEqual(result["fallback_used"], False)
        self.assertEqual(result["market_stats"], {"up_count": 2, "down_count": 2, "zt_count": 1, "dt_count": 1})
        self.assertEqual(result["zt_pool"][0]["代码"], "000001")
        self.assertEqual(result["zt_pool"][0]["所属行业"], "银行")
        self.assertEqual(result["dt_pool"][0]["代码"], "000002")
        self.assertEqual(result["limit_up_codes"], {"000001"})
        self.assertEqual(result["limit_down_codes"], {"000002"})
        self.assertEqual(fallback_calls, [])

    def test_limit_pool_snapshot_does_not_use_market_type_as_industry(self):
        result = get_limit_pool_snapshot_from_tushare_first(
            "2026-05-18",
            fetch_tushare_limit_rows_fn=lambda trade_date: [
                {
                    "ts_code": "002342.SZ",
                    "trade_date": "20260518",
                    "name": "巨力索具",
                    "market_type": "HS",
                    "limit": "U",
                    "pct_chg": 10.0,
                    "amount": 123456.0,
                    "up_stat": "1/1",
                }
            ],
            fetch_stock_daily_turnover_records_fn=lambda trade_date: [],
            fetch_stock_industry_map_fn=lambda: {},
            legacy_get_limit_pool_snapshot_fn=lambda target_date=None: {},
        )

        self.assertEqual(result["zt_pool"][0]["代码"], "002342")
        self.assertEqual(result["zt_pool"][0]["所属行业"], "未知")

    def test_limit_pool_snapshot_backfills_industry_from_stock_industry_map(self):
        result = get_limit_pool_snapshot_from_tushare_first(
            "2026-05-19",
            fetch_tushare_limit_rows_fn=lambda trade_date: [
                {
                    "ts_code": "688126.SH",
                    "trade_date": "20260519",
                    "name": "沪硅产业",
                    "market_type": "HS",
                    "limit": "U",
                    "pct_chg": 20.0,
                    "amount": 7017204.6,
                    "up_stat": "1/1",
                }
            ],
            fetch_stock_daily_turnover_records_fn=lambda trade_date: [],
            fetch_stock_industry_map_fn=lambda: {"688126": "半导体"},
            legacy_get_limit_pool_snapshot_fn=lambda target_date=None: {},
        )

        self.assertEqual(result["zt_pool"][0]["代码"], "688126")
        self.assertEqual(result["zt_pool"][0]["所属行业"], "半导体")

    def test_limit_pool_snapshot_falls_back_only_when_tushare_has_no_rows(self):
        fallback_calls = []

        result = get_limit_pool_snapshot_from_tushare_first(
            "2026-05-13",
            fetch_tushare_limit_rows_fn=lambda trade_date: [],
            legacy_get_limit_pool_snapshot_fn=lambda target_date=None: fallback_calls.append(target_date)
            or {
                "zt_pool": [{"代码": "000001", "名称": "旧涨停"}],
                "dt_pool": [],
                "market_stats": {"zt_count": 1, "dt_count": 0},
            },
        )

        self.assertEqual(result["provider"], "legacy.limit_pool_snapshot")
        self.assertEqual(result["fallback_used"], True)
        self.assertEqual(result["zt_pool"][0]["名称"], "旧涨停")
        self.assertEqual(fallback_calls, ["2026-05-13"])

    def test_sector_hot_plates_use_tushare_ths_hot_before_legacy_fallback(self):
        fallback_calls = []

        result = get_sector_hot_plates_from_tushare_first(
            "2026-05-13",
            limit=3,
            fetch_tushare_ths_hot_fn=lambda trade_date=None, market="概念板块": [
                {"ts_code": "886069.TI", "ts_name": "人形机器人", "rank": 1, "pct_change": 5.32, "hot": 35852.5},
                {"ts_code": "881157.TI", "ts_name": "证券", "rank": 2, "pct_change": 1.05, "hot": 31311.0},
            ],
            legacy_fetch_hot_plates_fn=lambda: fallback_calls.append("legacy") or [],
        )

        self.assertEqual([item["name"] for item in result], ["人形机器人", "证券"])
        self.assertEqual(result[0]["data_source"], "tushare.ths_hot")
        self.assertEqual(result[0]["market"], "概念板块")
        self.assertEqual(fallback_calls, [])

    def test_sector_change_rank_uses_tushare_ths_daily_before_iwencai_fallback(self):
        fallback_calls = []

        result = get_sector_change_rank_from_tushare_first(
            "2026-05-13",
            rank_type="up",
            limit=2,
            fetch_tushare_ths_daily_fn=lambda trade_date: [
                {"ts_code": "881157.TI", "trade_date": "20260513", "pct_change": 1.05, "close": 1200},
                {"ts_code": "881168.TI", "trade_date": "20260513", "pct_change": 4.16, "close": 980},
                {"ts_code": "700001.TI", "trade_date": "20260513", "pct_change": 9.0, "close": 1000},
            ],
            fetch_tushare_ths_index_map_fn=lambda: {
                "881157.TI": {"name": "证券", "type": "I", "exchange": "A"},
                "881168.TI": {"name": "工业金属", "type": "I", "exchange": "A"},
                "700001.TI": {"name": "同花顺全A", "type": "BB", "exchange": "A"},
            },
            legacy_get_sector_change_fn=lambda rank_type="up", limit=10, target_date=None: fallback_calls.append(rank_type) or [],
        )

        self.assertEqual([item["name"] for item in result], ["工业金属", "证券"])
        self.assertEqual(result[0]["data_source"], "tushare.ths_daily")
        self.assertEqual(fallback_calls, [])

    def test_sector_change_rank_reuses_cached_tushare_rows_when_followup_fetch_times_out(self):
        cache = getattr(tushare_runtime, "_SECTOR_CHANGE_RANK_ROWS_CACHE", None)
        if isinstance(cache, dict):
            cache.clear()
        fallback_calls = []
        fetch_calls = []
        index_map = {
            "881157.TI": {"name": "证券", "type": "I", "exchange": "A"},
            "881168.TI": {"name": "工业金属", "type": "I", "exchange": "A"},
            "884090.TI": {"name": "分立器件", "type": "I", "exchange": "A"},
        }

        def fetch_ths_daily(trade_date):
            fetch_calls.append(trade_date)
            if len(fetch_calls) == 1:
                return [
                    {"ts_code": "881157.TI", "trade_date": "20260525", "pct_change": 1.05, "close": 1200},
                    {"ts_code": "881168.TI", "trade_date": "20260525", "pct_change": -2.25, "close": 980},
                    {"ts_code": "884090.TI", "trade_date": "20260525", "pct_change": 5.66, "close": 1680},
                ]
            raise TimeoutError("ths_daily timeout")

        index_fetcher = lambda: index_map
        up = get_sector_change_rank_from_tushare_first(
            "2026-05-25",
            rank_type="up",
            limit=2,
            fetch_tushare_ths_daily_fn=fetch_ths_daily,
            fetch_tushare_ths_index_map_fn=index_fetcher,
            legacy_get_sector_change_fn=lambda rank_type="up", limit=10, target_date=None: fallback_calls.append(rank_type) or [],
        )
        down = get_sector_change_rank_from_tushare_first(
            "2026-05-25",
            rank_type="down",
            limit=2,
            fetch_tushare_ths_daily_fn=fetch_ths_daily,
            fetch_tushare_ths_index_map_fn=index_fetcher,
            legacy_get_sector_change_fn=lambda rank_type="up", limit=10, target_date=None: fallback_calls.append(rank_type) or [],
        )

        self.assertEqual([item["name"] for item in up], ["分立器件", "证券"])
        self.assertEqual([item["name"] for item in down], ["工业金属", "证券"])
        self.assertEqual(down[0]["data_source"], "tushare.ths_daily")
        self.assertEqual(fallback_calls, [])

    def test_sector_fund_flow_uses_tushare_moneyflow_ind_before_tencent_fallback(self):
        fallback_calls = []

        result = get_sector_fund_flow_from_tushare_first(
            "2026-05-13",
            limit=2,
            fetch_tushare_sector_flow_fn=lambda trade_date: [
                {"industry": "证券", "ts_code": "881157.TI", "pct_change": 1.05, "net_amount": 12.5, "net_buy_amount": 30, "net_sell_amount": 17.5},
                {"industry": "工业金属", "ts_code": "881168.TI", "pct_change": 4.16, "net_amount": -8.0, "net_buy_amount": 10, "net_sell_amount": 18},
                {"industry": "机器人", "ts_code": "881999.TI", "pct_change": 2.5, "net_amount": 20.0, "net_buy_amount": 40, "net_sell_amount": 20},
            ],
            legacy_get_sector_fund_flow_fn=lambda target_date=None, limit=50: fallback_calls.append(target_date) or {},
        )

        self.assertEqual([item["name"] for item in result["inflow"]], ["机器人", "证券"])
        self.assertEqual([item["name"] for item in result["outflow"]], ["工业金属", "证券"])
        self.assertEqual(result["inflow"][0]["data_source"], "tushare.moneyflow_ind_ths")
        self.assertEqual(result["provider"], "tushare.moneyflow_ind_ths")
        self.assertEqual(fallback_calls, [])

    def test_hot_concept_fund_flow_aggregates_members_from_stock_moneyflow(self):
        member_calls = []
        moneyflow_calls = []

        result = get_hot_concept_fund_flow_from_tushare_first(
            "2026-05-19",
            hot_plates=[
                {"name": "共封装光学(CPO)", "code": "886033.TI", "tag": "概念板块", "change_pct": 1.43, "rank": 4},
                {"name": "通信设备", "code": "881129.TI", "tag": "行业板块", "change_pct": 1.18, "rank": 5},
            ],
            fetch_tushare_ths_member_fn=lambda ts_code: member_calls.append(ts_code)
            or [
                {"con_code": "002281.SZ", "con_name": "光迅科技"},
                {"con_code": "000988.SZ", "con_name": "华工科技"},
                {"con_code": "920045.BJ", "con_name": "北交所样本"},
            ],
            fetch_stock_moneyflow_map_fn=lambda target_date: moneyflow_calls.append(target_date)
            or {
                "002281": 12.027182,
                "000988": 3.5,
            },
        )

        self.assertEqual(member_calls, ["886033.TI"])
        self.assertEqual(moneyflow_calls, ["2026-05-19"])
        self.assertEqual(result["provider"], "tushare.ths_member+tushare.moneyflow")
        self.assertEqual(result["rows"][0]["name"], "共封装光学(CPO)")
        self.assertEqual(result["rows"][0]["net_inflow"], 15.527182)
        self.assertEqual(result["rows"][0]["matched_member_count"], 2)
        self.assertEqual(result["rows"][0]["missing_member_count"], 1)
        self.assertEqual(result["rows"][0]["change_pct"], 1.43)
        self.assertEqual(result["rows"][0]["data_source"], "tushare.ths_member+tushare.moneyflow")

    def test_hot_concept_fund_flow_accepts_legacy_theme_codes_without_ti_suffix(self):
        member_calls = []

        def fetch_members(ts_code):
            member_calls.append(ts_code)
            if ts_code == "884229.TI":
                return [
                    {"con_code": "002371.SZ", "con_name": "北方华创"},
                    {"con_code": "003043.SZ", "con_name": "华亚智能"},
                ]
            return []

        result = get_hot_concept_fund_flow_from_tushare_first(
            "2026-05-21",
            hot_plates=[
                {"name": "半导体设备", "code": "884229", "tag": "", "rank": 1},
                {"name": "汽车零部件", "code": "881126", "tag": "4家涨停", "rank": 2},
            ],
            fetch_tushare_ths_member_fn=fetch_members,
            fetch_stock_moneyflow_map_fn=lambda target_date: {
                "002371": 8.0,
                "003043.SZ": 2.5,
            },
        )

        self.assertEqual(member_calls, ["884229.TI"])
        self.assertEqual(len(result["rows"]), 1)
        self.assertEqual(result["rows"][0]["name"], "半导体设备")
        self.assertEqual(result["rows"][0]["code"], "884229.TI")
        self.assertEqual(result["rows"][0]["net_inflow"], 10.5)

    def test_lhb_snapshot_uses_tushare_top_list_before_finshare_fallback(self):
        fallback_calls = []

        result = get_lhb_snapshot_from_tushare_first(
            "2026-05-13",
            fetch_tushare_top_list_fn=lambda trade_date: [
                {"ts_code": "000001.SZ", "name": "平安银行", "net_amount": 320000000, "close": 11.0, "pct_change": 10.0},
                {"ts_code": "000002.SZ", "name": "万科A", "net_amount": -150000000, "close": 8.0, "pct_change": -5.0},
                {"ts_code": "000001.SZ", "name": "平安银行", "net_amount": 180000000, "close": 11.0, "pct_change": 10.0},
            ],
            fetch_stock_industry_map_fn=lambda: {"000001": "银行", "000002": "房地产"},
            legacy_get_lhb_snapshot_fn=lambda target_date=None: fallback_calls.append(target_date) or {},
        )

        self.assertEqual(result["provider"], "tushare.top_list")
        self.assertEqual(result["lhb_net_buy_top10"][0]["code"], "000001")
        self.assertEqual(result["lhb_net_buy_top10"][0]["net_buy_amount_yi"], 5.0)
        self.assertEqual(result["lhb_net_buy_top10"][0]["sector"], "银行")
        self.assertEqual(result["lhb_net_sell_top10"][0]["code"], "000002")
        self.assertEqual(result["lhb_net_sell_top10"][0]["sector"], "房地产")
        self.assertEqual(result["lhb_analysis"][0]["data_source"], "tushare.top_list")
        self.assertEqual(fallback_calls, [])

    def test_lhb_snapshot_falls_back_to_legacy_when_tushare_same_day_empty(self):
        fallback_calls = []

        result = get_lhb_snapshot_from_tushare_first(
            "2026-05-19",
            fetch_tushare_top_list_fn=lambda trade_date: [],
            legacy_get_lhb_snapshot_fn=lambda target_date=None: fallback_calls.append(target_date)
            or {
                "lhb_net_buy_top10": [
                    {
                        "rank": 1,
                        "code": "000636",
                        "name": "风华高科",
                        "net_buy_amount_yi": 1.513513,
                        "change_pct": 9.9898,
                        "sector": "电子元件",
                    }
                ],
                "lhb_net_sell_top10": [],
                "lhb_analysis": [{"代码": "000636", "data_source": "finshare.get_lhb"}],
                "provider": "finshare.get_lhb",
            },
        )

        self.assertEqual(fallback_calls, ["2026-05-19"])
        self.assertEqual(result["provider"], "finshare.get_lhb")
        self.assertTrue(result["fallback_used"])
        self.assertEqual(result["lhb_net_buy_top10"][0]["code"], "000636")

    def test_new_stock_calendar_uses_tushare_new_share_before_sina_fallback(self):
        fallback_calls = []
        fetch_calls = []

        result = get_new_stock_calendar_from_tushare_first(
            "2026-05-13",
            fetch_tushare_new_share_fn=lambda start_date, end_date: fetch_calls.append((start_date, end_date))
            or [
                {
                    "ts_code": "001365.SZ",
                    "sub_code": "001365",
                    "name": "天海电子",
                    "ipo_date": "20260507",
                    "issue_date": "20260518",
                    "amount": 7900,
                    "market_amount": 4424,
                    "price": 27.19,
                    "pe": 23.4,
                    "funds": 21.48,
                },
                {
                    "ts_code": "001237.SZ",
                    "sub_code": "001237",
                    "name": "惠康科技",
                    "ipo_date": "20260513",
                    "issue_date": float("nan"),
                    "amount": 3709,
                    "market_amount": 2967,
                    "price": 53.26,
                    "pe": 21.04,
                    "funds": 19.753,
                },
                {"ts_code": "688635.SH", "name": "长进光子", "ipo_date": "20260518", "amount": 2342},
            ],
            legacy_get_new_stock_calendar_fn=lambda target_date=None: fallback_calls.append(target_date) or [],
        )

        self.assertEqual(fetch_calls, [("2026-05-13", "2026-06-13")])
        self.assertEqual([item["code"] for item in result], ["001365", "001237", "688635"])
        self.assertEqual(result[0]["subscription_date"], "2026-05-07")
        self.assertEqual(result[0]["listing_date"], "2026-05-18")
        self.assertEqual(result[0]["listing_window"], "upcoming_soon")
        self.assertEqual(result[0]["subscription_window"], "recently_subscribed")
        self.assertFalse(result[0]["official_listing_date_missing"])
        self.assertEqual(result[1]["subscription_date"], "2026-05-13")
        self.assertEqual(result[1]["listing_date"], "")
        self.assertEqual(result[1]["listing_window"], "missing_listing_date")
        self.assertEqual(result[1]["subscription_window"], "today_subscription")
        self.assertTrue(result[1]["official_listing_date_missing"])
        self.assertEqual(result[2]["subscription_window"], "upcoming_subscription")
        self.assertEqual(result[2]["source"], "tushare.new_share")
        self.assertEqual(fallback_calls, [])

    def test_new_stock_calendar_marks_next_trade_day_subscription(self):
        result = get_new_stock_calendar_from_tushare_first(
            "2026-05-15",
            fetch_tushare_new_share_fn=lambda start_date, end_date: [
                {"ts_code": "688635.SH", "name": "长进光子", "ipo_date": "20260518", "issue_date": None},
                {"ts_code": "920161.BJ", "name": "龙辰科技", "ipo_date": "20260518", "issue_date": None},
            ],
            next_trade_date_fn=lambda target_date: "2026-05-18",
        )

        self.assertEqual([item["code"] for item in result], ["688635", "920161"])
        self.assertTrue(all(item["subscription_window"] == "next_trade_day_subscription" for item in result))
        self.assertTrue(all(item["next_trade_date"] == "2026-05-18" for item in result))


if __name__ == "__main__":
    unittest.main()
