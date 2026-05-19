import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from input.request_registry import build_input_request_registry
from input.tushare_runtime import (
    get_lhb_snapshot_from_tushare_first,
    get_limit_pool_snapshot_from_tushare_first,
    get_major_indices_from_tushare_first,
    get_sector_change_rank_from_tushare_first,
    get_sector_fund_flow_from_tushare_first,
    get_sector_hot_plates_from_tushare_first,
    get_stock_hot_rank_from_tushare_first,
    get_new_stock_calendar_from_tushare_first,
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
            "get_stock_hot_rank_from_tushare_first": lambda *, target_date, limit=30: calls.append("tushare_hot_rank") or [],
            "get_limit_pool_snapshot_from_tushare_first": lambda *, target_date: calls.append("tushare_limit_pool") or {},
            "get_sector_hot_plates_from_tushare_first": lambda *, target_date, limit=20: calls.append("tushare_sector_hot") or [],
            "get_sector_change_rank_from_tushare_first": lambda *, target_date, rank_type="up", limit=10: calls.append(f"tushare_sector_change_{rank_type}") or [],
            "get_sector_fund_flow_from_tushare_first": lambda *, target_date, limit=50: calls.append("tushare_sector_flow") or {},
            "get_lhb_snapshot_from_tushare_first": lambda *, target_date: calls.append("tushare_lhb") or {},
            "get_new_stock_calendar_from_tushare_first": lambda *, target_date: calls.append("tushare_new_share") or [],
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
        registry["sector_change_rank"](target_date="2026-05-13", rank_type="up", limit=10)
        registry["sector_fund_flow"](target_date="2026-05-13", limit=50)
        registry["lhb_snapshot"](target_date="2026-05-13")
        registry["new_stock_calendar"](target_date="2026-05-13")

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
                "tushare_sector_change_up",
                "tushare_sector_flow",
                "tushare_lhb",
                "tushare_new_share",
            ],
        )

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
            legacy_get_limit_pool_snapshot_fn=lambda target_date=None: {},
        )

        self.assertEqual(result["zt_pool"][0]["代码"], "002342")
        self.assertEqual(result["zt_pool"][0]["所属行业"], "未知")

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
