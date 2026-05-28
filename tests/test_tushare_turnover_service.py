import sys
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
    def test_fetch_stock_daily_turnover_records_normalizes_daily_rows(self):
        from market_data.tushare_turnover_service import fetch_stock_daily_turnover_records

        fake_pro = _FakePro()
        rows = fetch_stock_daily_turnover_records("2026-05-12", pro=fake_pro)

        self.assertEqual(
            fake_pro.daily_calls,
            [
                {
                    "trade_date": "20260512",
                    "fields": (
                        "ts_code,trade_date,open,high,low,close,pre_close,"
                        "change,pct_chg,vol,amount"
                    ),
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


if __name__ == "__main__":
    unittest.main()
