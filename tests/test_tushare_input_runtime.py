import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from input.request_registry import build_input_request_registry
from input.tushare_runtime import (
    get_major_indices_from_tushare_first,
    get_total_turnover_from_tushare_first,
    get_turnover_rank_from_tushare_first,
    get_wind_a_from_tushare_first,
)
from market_data.tushare_service import fetch_daily_price_bars


class TushareInputRuntimeTest(unittest.TestCase):
    def test_request_registry_defaults_to_tushare_first_helpers(self):
        calls = []

        helpers = {
            "get_total_turnover_from_tushare_first": lambda *, target_date: calls.append("tushare_total") or 100.0,
            "get_major_indices_from_tushare_first": lambda *, target_date: calls.append("tushare_indices") or {},
            "get_wind_a_from_tushare_first": lambda *, target_date: calls.append("tushare_wind_a") or {},
            "get_turnover_rank_from_tushare_first": lambda *, target_date, limit=50: calls.append("tushare_turnover_rank") or [],
            "get_total_turnover_from_iwencai": lambda *, target_date: calls.append("legacy_total") or 0.0,
            "get_major_indices_from_iwencai": lambda *, target_date: calls.append("legacy_indices") or {},
            "get_wind_a_from_iwencai": lambda *, target_date: calls.append("legacy_wind_a") or {},
            "get_turnover_rank_from_iwencai": lambda *, target_date, limit=50: calls.append("legacy_turnover_rank") or [],
        }

        registry = build_input_request_registry(helpers)
        self.assertEqual(registry["total_turnover"](target_date="2026-05-13"), 100.0)
        registry["major_indices"](target_date="2026-05-13")
        registry["wind_a"](target_date="2026-05-13")
        registry["turnover_rank"](target_date="2026-05-13", limit=50)

        self.assertEqual(calls, ["tushare_total", "tushare_indices", "tushare_wind_a", "tushare_turnover_rank"])

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


if __name__ == "__main__":
    unittest.main()
