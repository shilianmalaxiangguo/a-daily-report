import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class TushareClientTest(unittest.TestCase):
    def test_create_tushare_pro_api_sets_proxy_and_default_timeout(self):
        from market_data.tushare_client import TUSHARE_TIMEOUT_SECONDS, create_tushare_pro_api

        calls = []

        class FakeTs:
            def pro_api(self, token="", timeout=30):
                calls.append({"token": token, "timeout": timeout})
                return type("FakePro", (), {})()

        pro = create_tushare_pro_api(ts_module=FakeTs(), token="token-x", http_url="http://proxy.invalid/")

        self.assertEqual(calls, [{"token": "token-x", "timeout": TUSHARE_TIMEOUT_SECONDS}])
        self.assertEqual(pro._DataApi__http_url, "http://proxy.invalid")

    def test_create_tushare_pro_api_allows_timeout_override(self):
        from market_data.tushare_client import create_tushare_pro_api

        calls = []

        class FakeTs:
            def pro_api(self, token="", timeout=30):
                calls.append({"token": token, "timeout": timeout})
                return type("FakePro", (), {})()

        create_tushare_pro_api(ts_module=FakeTs(), token="token-x", http_url="http://proxy.invalid/", timeout_seconds=2)

        self.assertEqual(calls, [{"token": "token-x", "timeout": 2}])

    def test_create_tushare_pro_api_reads_token_and_proxy_from_dotenv(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        import market_data.tushare_client as client

        calls = []

        class FakeTs:
            def pro_api(self, token="", timeout=30):
                calls.append({"token": token, "timeout": timeout})
                return type("FakePro", (), {})()

        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            env_path.write_text(
                "TUSHARE_TOKEN=dotenv-token\nTUSHARE_HTTP_URL=http://dotenv-proxy.invalid/\n",
                encoding="utf-8",
            )
            with patch.dict("os.environ", {}, clear=True), patch.object(Path, "cwd", return_value=Path(tmpdir)):
                pro = client.create_tushare_pro_api(ts_module=FakeTs())

        self.assertEqual(calls, [{"token": "dotenv-token", "timeout": client.TUSHARE_TIMEOUT_SECONDS}])
        self.assertEqual(pro._DataApi__http_url, "http://dotenv-proxy.invalid")

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

    def test_cyberfininvest_news_fetcher_uses_authorization_and_returns_data_rows(self):
        from market_data.tushare_market_activity_service import fetch_cyberfininvest_news_rows

        captured = []

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return b'{"code":200,"data":[{"title":"risk","stocks":[{"code":"000001"}]}]}'

        def fake_open(request, timeout=0):
            captured.append({"url": request.full_url, "headers": dict(request.header_items()), "timeout": timeout})
            return FakeResponse()

        rows = fetch_cyberfininvest_news_rows("2026-05-18", authorization="token-x", opener=fake_open)

        self.assertEqual(rows, [{"title": "risk", "stocks": [{"code": "000001"}]}])
        self.assertIn("category=3", captured[0]["url"])
        self.assertIn("size=100", captured[0]["url"])
        self.assertEqual(captured[0]["headers"]["Authorization"], "token-x")

    def test_cyberfininvest_news_fetcher_reads_authorization_from_dotenv(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        import market_data.tushare_market_activity_service as service

        captured = []

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return b'{"code":200,"data":[]}'

        def fake_open(request, timeout=0):
            captured.append(dict(request.header_items()))
            return FakeResponse()

        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            env_path.write_text("CYBERFININVEST_AUTHORIZATION=dotenv-token\n", encoding="utf-8")
            with patch.dict("os.environ", {}, clear=True), patch.object(service.Path, "cwd", return_value=Path(tmpdir)):
                service.fetch_cyberfininvest_news_rows("2026-05-18", opener=fake_open)

        self.assertEqual(captured[0]["Authorization"], "dotenv-token")

    def test_investor_qa_fetcher_uses_configured_endpoint_and_returns_rows(self):
        from market_data.tushare_market_activity_service import fetch_investor_qa_rows

        captured = []

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return (
                    b'{"data":[{"code":"002580","question":"Q",'
                    b'"answer":"A","source":"ths_iwencai_investor_qa"}]}'
                )

        def fake_open(request, timeout=0):
            captured.append({"url": request.full_url, "headers": dict(request.header_items()), "timeout": timeout})
            return FakeResponse()

        rows = fetch_investor_qa_rows(
            "2026-05-22",
            endpoint_url="https://example.invalid/investor_qa",
            opener=fake_open,
            use_tushare=False,
        )

        self.assertEqual(
            rows,
            [{"code": "002580", "question": "Q", "answer": "A", "source": "ths_iwencai_investor_qa"}],
        )
        self.assertEqual(captured[0]["url"], "https://example.invalid/investor_qa?trade_date=2026-05-22")
        self.assertEqual(captured[0]["headers"]["User-agent"], "Mozilla/5.0")
        self.assertEqual(captured[0]["timeout"], 8)

    def test_investor_qa_fetcher_uses_tushare_irm_qa_before_external_endpoint(self):
        from market_data.tushare_market_activity_service import fetch_investor_qa_rows

        calls = []

        class FakePro:
            def irm_qa_sh(self, **kwargs):
                calls.append(("irm_qa_sh", kwargs))
                return [
                    {
                        "ts_code": "600000.SH",
                        "name": "沪市样本",
                        "trade_date": "20260522",
                        "question": "是否涉及数据中心？",
                        "answer": "公司相关业务占比较小。",
                    }
                ]

            def irm_qa_sz(self, **kwargs):
                calls.append(("irm_qa_sz", kwargs))
                return [
                    {
                        "ts_code": "002580.SZ",
                        "name": "圣阳股份",
                        "trade_date": "20260522",
                        "question": "是否与美国客户合作？",
                        "answer": "截至目前尚未达成合作。",
                    }
                ]

        rows = fetch_investor_qa_rows(
            "2026-05-22",
            endpoint_url="https://example.invalid/investor_qa",
            pro=FakePro(),
            opener=lambda request, timeout=0: self.fail("external endpoint should not be used when Tushare returns rows"),
        )

        self.assertEqual([call[0] for call in calls], ["irm_qa_sh", "irm_qa_sz"])
        self.assertEqual(calls[0][1]["trade_date"], "20260522")
        self.assertEqual(calls[1][1]["trade_date"], "20260522")
        self.assertEqual(rows[0]["source"], "tushare.irm_qa_sh")
        self.assertEqual(rows[1]["source"], "tushare.irm_qa_sz")
        self.assertEqual(rows[1]["code"], "002580")

    def test_investor_qa_fetcher_queries_recent_trade_window_when_requested(self):
        from market_data.tushare_market_activity_service import fetch_investor_qa_rows

        calls = []

        class FakePro:
            def irm_qa_sh(self, **kwargs):
                calls.append(("irm_qa_sh", kwargs))
                return []

            def irm_qa_sz(self, **kwargs):
                calls.append(("irm_qa_sz", kwargs))
                return [
                    {
                        "ts_code": "002580.SZ",
                        "trade_date": "20260516",
                        "q": "AIDC是否与美国客户合作？",
                        "a": "截至目前尚未达成合作。",
                    }
                ]

        rows = fetch_investor_qa_rows(
            "2026-05-22",
            pro=FakePro(),
            lookback_trade_days=10,
            fetch_trade_dates_fn=lambda start_date, end_date: [
                "2026-05-11",
                "2026-05-12",
                "2026-05-13",
                "2026-05-14",
                "2026-05-15",
                "2026-05-16",
                "2026-05-18",
                "2026-05-19",
                "2026-05-20",
                "2026-05-21",
                "2026-05-22",
            ],
        )

        self.assertEqual(rows[0]["code"], "002580")
        self.assertEqual(calls[0][1]["start_date"], "20260513")
        self.assertEqual(calls[0][1]["end_date"], "20260522")
        self.assertNotIn("trade_date", calls[0][1])
        self.assertEqual(calls[1][1]["start_date"], "20260513")
        self.assertEqual(calls[1][1]["end_date"], "20260522")

    def test_investor_qa_fetcher_falls_back_to_external_endpoint_when_tushare_unavailable(self):
        from market_data.tushare_market_activity_service import fetch_investor_qa_rows

        captured = []

        class FakePro:
            def irm_qa_sh(self, **kwargs):
                raise RuntimeError("no permission")

            def irm_qa_sz(self, **kwargs):
                raise RuntimeError("no permission")

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return b'{"data":[{"code":"002580","answer":"fallback"}]}'

        def fake_open(request, timeout=0):
            captured.append(request.full_url)
            return FakeResponse()

        rows = fetch_investor_qa_rows(
            "2026-05-22",
            endpoint_url="https://example.invalid/investor_qa",
            pro=FakePro(),
            opener=fake_open,
        )

        self.assertEqual(rows, [{"code": "002580", "answer": "fallback"}])
        self.assertEqual(captured, ["https://example.invalid/investor_qa?trade_date=2026-05-22"])

    def test_investor_qa_fetcher_accepts_nested_list_payload_and_skips_when_unconfigured(self):
        from market_data.tushare_market_activity_service import fetch_investor_qa_rows

        captured = []

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return b'{"data":{"list":[{"stock_code":"000001","answer":"no"}]}}'

        def fake_open(request, timeout=0):
            captured.append(request.full_url)
            return FakeResponse()

        self.assertEqual(fetch_investor_qa_rows("2026-05-22", endpoint_url="", opener=fake_open, use_tushare=False), [])

        rows = fetch_investor_qa_rows(
            "2026-05-22",
            endpoint_url="https://example.invalid/investor_qa?source=ths",
            opener=fake_open,
            use_tushare=False,
        )

        self.assertEqual(rows, [{"stock_code": "000001", "answer": "no"}])
        self.assertEqual(captured, ["https://example.invalid/investor_qa?source=ths&trade_date=2026-05-22"])


if __name__ == "__main__":
    unittest.main()
