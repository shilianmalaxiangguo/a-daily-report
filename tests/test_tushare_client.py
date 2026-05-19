import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class TushareClientTest(unittest.TestCase):
    def test_create_tushare_pro_api_sets_gateway_and_default_timeout(self):
        from market_data.tushare_client import TUSHARE_HTTP_URL, TUSHARE_TIMEOUT_SECONDS, create_tushare_pro_api

        calls = []

        class FakeTs:
            def pro_api(self, token="", timeout=30):
                calls.append({"token": token, "timeout": timeout})
                return type("FakePro", (), {})()

        pro = create_tushare_pro_api(ts_module=FakeTs(), token="token-x")

        self.assertEqual(calls, [{"token": "token-x", "timeout": TUSHARE_TIMEOUT_SECONDS}])
        self.assertEqual(pro._DataApi__http_url, TUSHARE_HTTP_URL)

    def test_create_tushare_pro_api_allows_timeout_override(self):
        from market_data.tushare_client import create_tushare_pro_api

        calls = []

        class FakeTs:
            def pro_api(self, token="", timeout=30):
                calls.append({"token": token, "timeout": timeout})
                return type("FakePro", (), {})()

        create_tushare_pro_api(ts_module=FakeTs(), token="token-x", timeout_seconds=2)

        self.assertEqual(calls, [{"token": "token-x", "timeout": 2}])

    def test_tushare_risk_fetchers_call_expected_pro_endpoints(self):
        from market_data.tushare_market_activity_service import (
            fetch_tushare_announcement_rows,
            fetch_tushare_holdertrade_rows,
            fetch_tushare_shock_rows,
            fetch_tushare_st_rows,
            fetch_tushare_stock_st_rows,
        )

        calls = []

        class FakePro:
            def st(self, **kwargs):
                calls.append(("st", kwargs))
                return [{"ts_code": "000001.SZ"}]

            def stock_st(self, **kwargs):
                calls.append(("stock_st", kwargs))
                return [{"ts_code": "000001.SZ"}]

            def stk_holdertrade(self, **kwargs):
                calls.append(("stk_holdertrade", kwargs))
                return [{"ts_code": "000002.SZ"}]

            def anns_d(self, **kwargs):
                calls.append(("anns_d", kwargs))
                return [{"ts_code": "000003.SZ"}]

            def stk_shock(self, **kwargs):
                calls.append(("stk_shock", kwargs))
                return [{"ts_code": "000004.SZ"}]

        pro = FakePro()

        self.assertEqual(fetch_tushare_st_rows("2026-05-18", pro=pro), [{"ts_code": "000001.SZ"}])
        self.assertEqual(fetch_tushare_stock_st_rows("2026-05-18", pro=pro), [{"ts_code": "000001.SZ"}])
        self.assertEqual(fetch_tushare_holdertrade_rows("2026-05-18", pro=pro), [{"ts_code": "000002.SZ"}])
        self.assertEqual(fetch_tushare_announcement_rows("2026-05-18", pro=pro), [{"ts_code": "000003.SZ"}])
        self.assertEqual(fetch_tushare_shock_rows("2026-05-18", pro=pro), [{"ts_code": "000004.SZ"}])

        call_by_name = {name: kwargs for name, kwargs in calls}
        self.assertIn("fields", call_by_name["st"])
        self.assertEqual(call_by_name["stock_st"]["trade_date"], "20260518")
        self.assertEqual(call_by_name["stk_holdertrade"]["ann_date"], "20260518")
        self.assertEqual(call_by_name["anns_d"]["ann_date"], "20260518")
        self.assertEqual(call_by_name["stk_shock"]["trade_date"], "20260518")


if __name__ == "__main__":
    unittest.main()
