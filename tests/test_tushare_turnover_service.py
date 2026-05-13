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

        self.assertEqual(fake_pro.daily_calls, [{"trade_date": "20260512"}])
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


if __name__ == "__main__":
    unittest.main()
