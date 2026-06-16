import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class TushareMinuteServiceTest(unittest.TestCase):
    def test_fetch_tushare_minute_bars_passes_short_timeout_to_client(self):
        from market_data.tushare_minute_service import fetch_tushare_minute_bars

        calls = []

        class FakePro:
            def stock_mins(self, **kwargs):
                calls.append(("stock_mins", kwargs))
                return [
                    {
                        "trade_time": "2026-06-09 09:30:00",
                        "open": 10,
                        "high": 10.2,
                        "low": 9.9,
                        "close": 10.1,
                    }
                ]

        class FakeTs:
            def pro_api(self, token="", timeout=30):
                calls.append(("pro_api", {"token": token, "timeout": timeout}))
                return FakePro()

        rows = fetch_tushare_minute_bars(
            "603986",
            period="5",
            target_date="2026-06-09",
            ts_module=FakeTs(),
            timeout_seconds=2,
        )

        self.assertEqual(calls[0][0], "pro_api")
        self.assertEqual(calls[0][1]["timeout"], 2)
        self.assertEqual(
            calls[1],
            (
                "stock_mins",
                {
                    "ts_code": "603986.SH",
                    "start_date": "2026-06-09 00:00:00",
                    "end_date": "2026-06-09 23:59:59",
                    "freq": "5min",
                },
            ),
        )
        self.assertEqual(rows[0]["datetime"], "2026-06-09 09:30:00")

    def test_fetch_tushare_minute_bars_falls_back_to_stk_mins(self):
        from market_data.tushare_minute_service import fetch_tushare_minute_bars

        calls = []

        class FakePro:
            def stock_mins(self, **kwargs):
                calls.append(("stock_mins", kwargs))
                raise Exception("接口名不正确")

            def stk_mins(self, **kwargs):
                calls.append(("stk_mins", kwargs))
                return [
                    {
                        "trade_time": "2026-06-09 09:35:00",
                        "open": 10.1,
                        "high": 10.3,
                        "low": 10.0,
                        "close": 10.2,
                    }
                ]

        rows = fetch_tushare_minute_bars(
            "603986",
            period="5",
            target_date="2026-06-09",
            pro=FakePro(),
        )

        self.assertEqual([item[0] for item in calls], ["stock_mins", "stk_mins"])
        self.assertEqual(rows[0]["data_source"], "tushare.stk_mins")

    def test_fetch_tushare_minute_bars_reports_both_interface_errors(self):
        from market_data.tushare_minute_service import fetch_tushare_minute_bars

        class FakePro:
            def stock_mins(self, **kwargs):
                raise Exception("接口名不正确")

            def stk_mins(self, **kwargs):
                raise Exception("没有权限")

        with self.assertRaisesRegex(Exception, "stock_mins: 接口名不正确; stk_mins: 没有权限"):
            fetch_tushare_minute_bars(
                "603986",
                period="5",
                target_date="2026-06-09",
                pro=FakePro(),
            )


if __name__ == "__main__":
    unittest.main()
