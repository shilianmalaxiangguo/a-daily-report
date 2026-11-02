import sys
import unittest
from pathlib import Path
from unittest.mock import patch

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
    def __init__(self):
        self.daily_calls = []

    def daily(self, **kwargs):
        self.daily_calls.append(kwargs)
        return _FakeFrame(
            [
                {
                    "ts_code": "000001.SZ",
                    "trade_date": "20260512",
                    "open": 10,
                    "high": 11,
                    "low": 9.8,
                    "close": 10.5,
                    "pre_close": 10,
                    "change": 0.5,
                    "pct_chg": 5,
                    "vol": 12345,
                    "amount": 250000,
                },
                {
                    "ts_code": "600000.SH",
                    "trade_date": "20260512",
                    "open": 8,
                    "high": 8.5,
                    "low": 7.9,
                    "close": 8.1,
                    "pre_close": 8.2,
                    "change": -0.1,
                    "pct_chg": -1.22,
                    "vol": 8000,
                    "amount": 100000,
                },
            ]
        )


class TushareTurnoverServiceTest(unittest.TestCase):
    def test_open_trade_dates_filters_closed_rows_when_provider_ignores_request_filter(self):
        from market_data.tushare_market_activity_service import fetch_tushare_open_trade_dates

        class CalendarPro:
            def __init__(self):
                self.calls = []

            def trade_cal(self, **kwargs):
                self.calls.append(kwargs)
                return _FakeFrame(
                    [
                        {"cal_date": "20260807", "is_open": 1},
                        {"cal_date": "20260808", "is_open": 0},
                        {"cal_date": "20260809", "is_open": "0"},
                        {"cal_date": "20260810", "is_open": "1"},
                    ]
                )

        pro = CalendarPro()
        result = fetch_tushare_open_trade_dates("2026-08-07", "2026-08-10", pro=pro)

        self.assertEqual(result, ["2026-08-07", "2026-08-10"])
        self.assertEqual(
            pro.calls,
            [
                {
                    "exchange": "SSE",
                    "start_date": "20260807",
                    "end_date": "20260810",
                    "is_open": "1",
                }
            ],
        )

    def test_market_index_amount_uses_quicktiny_only_for_missing_target_date(self):
        from market_data.tushare_turnover_service import fetch_market_index_amount_rows

        class IndexPro:
            def index_daily(self, **_kwargs):
                return _FakeFrame(
                    [
                        {"trade_date": "20260723", "amount": 1000000},
                    ]
                )

        fallback_calls = []

        result = fetch_market_index_amount_rows(
            "2026-07-23",
            "2026-07-24",
            pro=IndexPro(),
            quicktiny_fetcher=lambda start, end, *, index_codes: fallback_calls.append((start, end, index_codes)) or [
                {
                    "trade_date": "2026-07-24",
                    "market_turnover_yi": 15379.4784439685,
                    "index_count": 2,
                    "source_policy": "quicktiny.merged_kline.index_daily.market_amount",
                    "source_date": "2026-07-24",
                    "query_date": "2026-07-24",
                }
            ],
        )

        self.assertEqual(fallback_calls, [("2026-07-23", "2026-07-24", ("000001.SH", "399001.SZ"))])
        self.assertEqual(result[-1]["trade_date"], "2026-07-24")
        self.assertAlmostEqual(result[-1]["market_turnover_yi"], 15379.478444, places=6)
        self.assertEqual(result[-1]["source_policy"], "quicktiny.merged_kline.index_daily.market_amount")

    def test_market_index_amount_keeps_complete_tushare_target_without_quicktiny(self):
        from market_data.tushare_turnover_service import fetch_market_index_amount_rows

        class IndexPro:
            def index_daily(self, **kwargs):
                code = kwargs["ts_code"]
                amount = 1000000 if code == "000001.SH" else 2000000
                return _FakeFrame([{"trade_date": "20260724", "amount": amount}])

        result = fetch_market_index_amount_rows(
            "2026-07-24",
            "2026-07-24",
            pro=IndexPro(),
            quicktiny_fetcher=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("QuickTiny should not run")),
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["source_policy"], "tushare.index_daily.market_amount")
        self.assertAlmostEqual(result[0]["market_turnover_yi"], 30.0)

    def test_market_index_amount_uses_quicktiny_when_tushare_request_fails(self):
        from market_data.tushare_turnover_service import fetch_market_index_amount_rows

        class IndexPro:
            def index_daily(self, **_kwargs):
                raise RuntimeError("Tushare unavailable")

        result = fetch_market_index_amount_rows(
            "2026-07-27",
            "2026-07-27",
            pro=IndexPro(),
            quicktiny_fetcher=lambda start, end, *, index_codes: [
                {
                    "trade_date": "2026-07-27",
                    "market_turnover_yi": 16649.19416,
                    "index_count": 2,
                    "source_policy": "quicktiny.merged_kline.index_daily.market_amount",
                    "source_date": "2026-07-27",
                    "query_date": "2026-07-27",
                }
            ],
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["trade_date"], "2026-07-27")
        self.assertEqual(result[0]["source_policy"], "quicktiny.merged_kline.index_daily.market_amount")
        self.assertAlmostEqual(result[0]["market_turnover_yi"], 16649.19416)

    def test_market_index_amount_uses_quicktiny_when_tushare_client_init_fails(self):
        from market_data.tushare_turnover_service import fetch_market_index_amount_rows

        with patch(
            "market_data.tushare_turnover_service.create_tushare_pro_api",
            side_effect=RuntimeError("client init failed"),
        ):
            result = fetch_market_index_amount_rows(
                "2026-07-27",
                "2026-07-27",
                quicktiny_fetcher=lambda start, end, *, index_codes: [
                    {
                        "trade_date": "2026-07-27",
                        "market_turnover_yi": 16649.19416,
                        "index_count": 2,
                        "source_policy": "quicktiny.merged_kline.index_daily.market_amount",
                        "source_date": "2026-07-27",
                        "query_date": "2026-07-27",
                    }
                ],
            )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["trade_date"], "2026-07-27")
        self.assertEqual(result[0]["source_policy"], "quicktiny.merged_kline.index_daily.market_amount")

    def test_quicktiny_index_amount_adapter_filters_source_and_converts_yuan_to_yi(self):
        from market_data.tushare_turnover_service import fetch_quicktiny_index_amount_rows

        class FakeResponse:
            def __init__(self, rows):
                self._rows = rows

            def raise_for_status(self):
                return None

            def json(self):
                return {"data": list(self._rows)}

        class FakeSession:
            def __init__(self):
                self.calls = []

            def get(self, url, timeout=None):
                self.calls.append((url, timeout))
                if "/sh000001" in url:
                    return FakeResponse(
                        [
                            {"date": "2026-07-27", "amount": 100_000_000, "source": "index_daily"},
                            {"date": "2026-07-27", "amount": 900_000_000, "source": "stock_daily"},
                        ]
                    )
                return FakeResponse(
                    [
                        {"date": "2026-07-27", "amount": 200_000_000, "source": ""},
                        {"date": "2026-07-26", "amount": 300_000_000, "source": "index_daily"},
                    ]
                )

        session = FakeSession()
        result = fetch_quicktiny_index_amount_rows(
            "2026-07-27",
            "2026-07-27",
            session=session,
        )

        self.assertEqual(len(session.calls), 2)
        self.assertTrue(session.calls[0][0].endswith("/sh000001?days=20"))
        self.assertTrue(session.calls[1][0].endswith("/sz399001?days=20"))
        self.assertEqual([call[1] for call in session.calls], [(2, 6), (2, 6)])
        self.assertEqual(result[0]["trade_date"], "2026-07-27")
        self.assertEqual(result[0]["index_count"], 2)
        self.assertEqual(result[0]["stock_count"], 2)
        self.assertAlmostEqual(result[0]["market_turnover_yi"], 3.0)
        self.assertEqual(result[0]["source_date"], "2026-07-27")
        self.assertEqual(result[0]["query_date"], "2026-07-27")

    def test_fetch_stock_daily_turnover_records_normalizes_daily_rows(self):
        from market_data.tushare_turnover_service import fetch_stock_daily_turnover_records

        fake_pro = _FakePro()
        rows = fetch_stock_daily_turnover_records("2026-05-12", pro=fake_pro)

        self.assertEqual(
            fake_pro.daily_calls,
            [
                {
                    "start_date": "20260512",
                    "end_date": "20260512",
                    "fields": (
                        "ts_code,trade_date,open,high,low,close,pre_close,"
                        "change,pct_chg,vol,amount"
                    ),
                    "limit": 1000,
                    "offset": 0,
                }
            ],
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["trade_date"], "2026-05-12")
        self.assertEqual(rows[0]["ts_code"], "000001.SZ")
        self.assertEqual(rows[0]["stock_code"], "000001")
        self.assertEqual(rows[0]["market"], "SZ")
        self.assertEqual(rows[0]["amount_yi"], 2.5)
        self.assertEqual(rows[0]["amount_raw_qianyuan"], 250000.0)
        self.assertEqual(rows[0]["data_source"], "tushare.daily")
        self.assertEqual(rows[1]["market"], "SH")
        self.assertEqual(rows[1]["amount_yi"], 1.0)

    def test_fetch_stock_daily_turnover_records_uses_trade_date_for_a_channel(self):
        from market_data.tushare_turnover_service import fetch_stock_daily_turnover_records

        class AChannelPro:
            _DataApi__http_url = "http://a.sszhixia.cn/"

            def __init__(self):
                self.calls = []

            def daily(self, **kwargs):
                self.calls.append(kwargs)
                return _FakeFrame(
                    [
                        {"ts_code": "000001.SZ", "trade_date": "20260710", "pct_chg": -0.38, "amount": 999718.25},
                        {"ts_code": "600000.SH", "trade_date": "20260710", "pct_chg": 0.89, "amount": 691188.28},
                    ]
                )

        pro = AChannelPro()
        rows = fetch_stock_daily_turnover_records("2026-07-10", pro=pro)

        self.assertEqual(
            pro.calls,
            [
                {
                    "trade_date": "20260710",
                    "fields": (
                        "ts_code,trade_date,open,high,low,close,pre_close,"
                        "change,pct_chg,vol,amount"
                    ),
                }
            ],
        )
        self.assertEqual(len(rows), 2)
        self.assertAlmostEqual(sum(row["amount_yi"] for row in rows), 16.909065, places=6)

    def test_fetch_stock_daily_turnover_records_retries_empty_a_channel_result(self):
        from market_data.tushare_turnover_service import fetch_stock_daily_turnover_records

        class AChannelPro:
            _DataApi__http_url = "http://a.sszhixia.cn/"

            def __init__(self):
                self.calls = []

            def daily(self, **kwargs):
                self.calls.append(kwargs)
                if len(self.calls) == 1:
                    return _FakeFrame([])
                return _FakeFrame(
                    [{"ts_code": "000001.SZ", "trade_date": "20260710", "pct_chg": -0.38, "amount": 999718.25}]
                )

        pro = AChannelPro()
        with patch("time.sleep") as sleep:
            rows = fetch_stock_daily_turnover_records("2026-07-10", pro=pro, page_retry_count=1)

        self.assertEqual(len(pro.calls), 2)
        self.assertEqual(pro.calls[0], pro.calls[1])
        self.assertNotIn("limit", pro.calls[0])
        self.assertNotIn("offset", pro.calls[0])
        sleep.assert_called_once_with(1)
        self.assertEqual(len(rows), 1)

    def test_fetch_stock_daily_turnover_records_filters_invalid_dates_and_amounts(self):
        from market_data.tushare_turnover_service import fetch_stock_daily_turnover_records

        class BadPro:
            def daily(self, **kwargs):
                return _FakeFrame(
                    [
                        {"ts_code": "000001.SZ", "trade_date": "20260512", "amount": ""},
                        {"ts_code": "", "trade_date": "20260512", "amount": 10},
                        {"ts_code": "600000.SH", "trade_date": "", "amount": 10},
                    ]
                )

        self.assertEqual(fetch_stock_daily_turnover_records("2026-05-12", pro=BadPro()), [])

    def test_fetch_stock_daily_turnover_records_paginates_single_day_rows(self):
        from market_data.tushare_turnover_service import fetch_stock_daily_turnover_records

        class PagedPro:
            def __init__(self):
                self.calls = []

            def daily(self, **kwargs):
                self.calls.append(kwargs)
                offset = kwargs.get("offset", 0)
                if offset == 0:
                    return _FakeFrame(
                        [
                            {
                                "ts_code": "000001.SZ",
                                "trade_date": "20260512",
                                "amount": 250000,
                            },
                            {
                                "ts_code": "000002.SZ",
                                "trade_date": "20260512",
                                "amount": 150000,
                            },
                        ]
                    )
                return _FakeFrame(
                    [
                        {
                            "ts_code": "600000.SH",
                            "trade_date": "20260512",
                            "amount": 100000,
                        }
                    ]
                )

        fake_pro = PagedPro()
        rows = fetch_stock_daily_turnover_records("2026-05-12", pro=fake_pro, page_limit=2)

        self.assertEqual([call["offset"] for call in fake_pro.calls], [0, 2])
        self.assertEqual(len(rows), 3)
        self.assertEqual(sum(row["amount_yi"] for row in rows), 5.0)

    def test_fetch_stock_daily_turnover_records_range_paginates_full_daily_rows(self):
        from market_data.tushare_turnover_service import fetch_stock_daily_turnover_records_range

        class RangePro:
            def __init__(self):
                self.calls = []

            def daily(self, **kwargs):
                self.calls.append(kwargs)
                offset = kwargs.get("offset", 0)
                if offset == 0:
                    return _FakeFrame(
                        [
                            {
                                "ts_code": "000001.SZ",
                                "trade_date": "20260511",
                                "open": 10,
                                "high": 11,
                                "low": 9.8,
                                "close": 10.5,
                                "pre_close": 10,
                                "change": 0.5,
                                "pct_chg": 5,
                                "vol": 12345,
                                "amount": 250000,
                            },
                            {
                                "ts_code": "600000.SH",
                                "trade_date": "20260512",
                                "open": 8,
                                "high": 8.5,
                                "low": 7.9,
                                "close": 8.1,
                                "pre_close": 8.2,
                                "change": -0.1,
                                "pct_chg": -1.22,
                                "vol": 8000,
                                "amount": 100000,
                            },
                        ]
                    )
                return _FakeFrame([])

        pro = RangePro()
        rows = fetch_stock_daily_turnover_records_range("2026-05-01", "2026-05-12", pro=pro, page_limit=2)

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["trade_date"], "2026-05-11")
        self.assertEqual(rows[0]["stock_code"], "000001")
        self.assertEqual(rows[0]["high"], 11.0)
        self.assertEqual(rows[1]["market"], "SH")
        self.assertEqual(
            pro.calls,
            [
                {
                    "start_date": "20260501",
                    "end_date": "20260512",
                    "fields": (
                        "ts_code,trade_date,open,high,low,close,pre_close,"
                        "change,pct_chg,vol,amount"
                    ),
                    "limit": 2,
                    "offset": 0,
                },
                {
                    "start_date": "20260501",
                    "end_date": "20260512",
                    "fields": (
                        "ts_code,trade_date,open,high,low,close,pre_close,"
                        "change,pct_chg,vol,amount"
                    ),
                    "limit": 2,
                    "offset": 2,
                },
            ],
        )

    def test_fetch_stock_turnover_history_fetches_daily_amounts_for_one_stock(self):
        from market_data.tushare_turnover_service import fetch_stock_turnover_history

        class HistoryPro:
            def __init__(self):
                self.daily_calls = []

            def daily(self, **kwargs):
                self.daily_calls.append(kwargs)
                return _FakeFrame(
                    [
                        {"ts_code": "000001.SZ", "trade_date": "20260512", "amount": 250000},
                        {"ts_code": "000001.SZ", "trade_date": "20260511", "amount": 100000},
                    ]
                )

        pro = HistoryPro()
        rows = fetch_stock_turnover_history("000001", "2026-05-01", "2026-05-12", pro=pro)

        self.assertEqual(
            pro.daily_calls,
            [{"ts_code": "000001.SZ", "start_date": "20260501", "end_date": "20260512"}],
        )
        self.assertEqual(rows, [1.0, 2.5])

    def test_fetch_stock_batch_quote_info_builds_stock_full_info_from_daily_rows(self):
        from market_data.tushare_turnover_service import fetch_stock_batch_quote_info

        rows = fetch_stock_batch_quote_info(
            ["000001", "600000"],
            "2026-05-12",
            fetch_daily_records_fn=lambda trade_date: [
                {
                    "stock_code": "000001",
                    "name": "",
                    "open": 10,
                    "high": 11,
                    "low": 9.8,
                    "close": 10.5,
                    "pct_chg": 5,
                    "amount_yi": 2.5,
                    "data_source": "tushare.daily",
                },
                {
                    "stock_code": "600000",
                    "name": "浦发银行",
                    "open": 8,
                    "high": 8.5,
                    "low": 7.9,
                    "close": 8.1,
                    "pct_chg": -1.22,
                    "amount_yi": 1.0,
                    "data_source": "tushare.daily",
                },
            ],
            fetch_name_map_fn=lambda: {"000001": {"name": "平安银行", "industry": "银行"}},
        )

        self.assertEqual(set(rows), {"000001", "600000"})
        self.assertEqual(rows["000001"]["name"], "平安银行")
        self.assertEqual(rows["000001"]["industry"], "银行")
        self.assertEqual(rows["000001"]["所属行业"], "银行")
        self.assertEqual(rows["000001"]["change_pct"], 5.0)
        self.assertEqual(rows["000001"]["zt_status"], "正常")
        self.assertEqual(rows["000001"]["trade_date"], "2026-05-12")
        self.assertEqual(rows["600000"]["name"], "浦发银行")
        self.assertEqual(rows["600000"]["data_source"], "tushare.daily")

    def test_fetch_stock_basic_map_includes_list_date_for_recent_stock_filtering(self):
        from market_data.tushare_turnover_service import fetch_stock_basic_map

        class BasicPro:
            def __init__(self):
                self.calls = []

            def stock_basic(self, **kwargs):
                self.calls.append(kwargs)
                return _FakeFrame(
                    [
                        {
                            "ts_code": "000001.SZ",
                            "name": "平安银行",
                            "industry": "银行",
                            "list_date": "19910403",
                        }
                    ]
                )

        pro = BasicPro()
        result = fetch_stock_basic_map(pro=pro)

        self.assertIn("list_date", pro.calls[0]["fields"])
        self.assertEqual(result["000001"]["list_date"], "19910403")
        self.assertEqual(result["000001.SZ"]["list_date"], "19910403")

    def test_fetch_stock_basic_map_normalizes_missing_text_and_placeholder_list_date(self):
        from market_data.tushare_turnover_service import fetch_stock_basic_map

        class BasicPro:
            def stock_basic(self, **_kwargs):
                return _FakeFrame(
                    [
                        {
                            "ts_code": "301677.SZ",
                            "name": "C欣兴",
                            "industry": float("nan"),
                            "list_date": "19700101",
                        },
                        {
                            "ts_code": "000001.SZ",
                            "name": "<NA>",
                            "industry": "NaT",
                            "list_date": "nan",
                        },
                    ]
                )

        result = fetch_stock_basic_map(pro=BasicPro())

        self.assertEqual(result["301677"]["industry"], "")
        self.assertEqual(result["301677"]["list_date"], "")
        self.assertNotIn("000001", result)

    def test_fetch_stock_factor_pro_rows_uses_supported_page_size(self):
        from market_data.tushare_turnover_service import fetch_stock_factor_pro_rows

        class FactorPro:
            def __init__(self):
                self.calls = []

            def stk_factor_pro(self, **kwargs):
                self.calls.append(kwargs)
                if kwargs.get("limit") and kwargs["limit"] > 6000:
                    return _FakeFrame([])
                return _FakeFrame(
                    [
                        {
                            "ts_code": "000001.SZ",
                            "trade_date": "20260520",
                            "close": 12.3,
                            "high": 12.8,
                            "pct_chg": 5.2,
                            "amount": 2500000,
                            "topdays": 260,
                        }
                    ]
                )

        pro = FactorPro()
        rows = fetch_stock_factor_pro_rows("2026-05-20", pro=pro)

        self.assertEqual(len(rows), 1)
        self.assertEqual(pro.calls[0]["trade_date"], "20260520")
        self.assertEqual(pro.calls[0]["limit"], 6000)
        self.assertEqual(pro.calls[0].get("offset", 0), 0)

    def test_fetch_daily_price_bars_by_trade_date_normalizes_full_market_daily_rows(self):
        from market_data.tushare_service import fetch_daily_price_bars_by_trade_date

        fake_pro = _FakePro()
        rows = fetch_daily_price_bars_by_trade_date("2026-05-12", pro=fake_pro)

        self.assertEqual(
            fake_pro.daily_calls[-1],
            {
                "trade_date": "20260512",
                "fields": (
                    "ts_code,trade_date,open,high,low,close,pre_close,"
                    "change,pct_chg,vol,amount"
                ),
            },
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["date"], "2026-05-12")
        self.assertEqual(rows[0]["stock_code"], "000001")
        self.assertEqual(rows[0]["open"], 10.0)
        self.assertEqual(rows[0]["high"], 11.0)
        self.assertEqual(rows[0]["low"], 9.8)
        self.assertEqual(rows[0]["close"], 10.5)
        self.assertEqual(rows[0]["data_source"], "tushare.daily")


if __name__ == "__main__":
    unittest.main()
