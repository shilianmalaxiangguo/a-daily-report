import os
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

        pro = create_tushare_pro_api(ts_module=FakeTs(), token="token-x", http_url="http://a.sszhixia.cn/")

        self.assertEqual(calls, [{"token": "token-x", "timeout": TUSHARE_TIMEOUT_SECONDS}])
        self.assertEqual(pro._DataApi__http_url, "http://a.sszhixia.cn")

    def test_create_tushare_pro_api_allows_timeout_override(self):
        from market_data.tushare_client import create_tushare_pro_api

        calls = []

        class FakeTs:
            def pro_api(self, token="", timeout=30):
                calls.append({"token": token, "timeout": timeout})
                return type("FakePro", (), {})()

        create_tushare_pro_api(ts_module=FakeTs(), token="token-x", http_url="http://proxy.invalid/", timeout_seconds=2)

        self.assertEqual(calls, [{"token": "token-x", "timeout": 2}])

    def test_create_tushare_pro_api_uses_replay_adapter_for_replay_url(self):
        from market_data.tushare_client import TushareReplayProApi, create_tushare_pro_api

        class FakeTs:
            def pro_api(self, token="", timeout=30):
                self.fail("Replay URL should not use the legacy Tushare SDK")

        pro = create_tushare_pro_api(
            ts_module=FakeTs(),
            token="token-x",
            http_url="https://tushare.indevs.in/tushare/pro/",
            timeout_seconds=7,
        )

        self.assertIsInstance(pro, TushareReplayProApi)
        self.assertEqual(pro.base_url, "https://tushare.indevs.in/tushare/pro")
        self.assertEqual(pro.timeout_seconds, 7)

    def test_tushare_replay_adapter_returns_dataframe_from_items(self):
        from market_data.tushare_client import TushareReplayProApi

        calls = []

        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "code": 0,
                    "msg": "ok",
                    "data": {
                        "fields": ["ts_code", "trade_date", "close"],
                        "items": [["000001.SZ", "20260701", 10.16]],
                    },
                    "count": 1,
                }

        class FakeRequests:
            def get(self, url, headers=None, params=None, timeout=None):
                calls.append({"url": url, "headers": headers, "params": params, "timeout": timeout})
                return FakeResponse()

        pro = TushareReplayProApi(
            token="token-x",
            base_url="https://tushare.indevs.in/tushare/pro/",
            timeout_seconds=9,
            requests_module=FakeRequests(),
        )
        frame = pro.daily(ts_code="000001.SZ", start_date="20260701", end_date="20260701")

        self.assertEqual(list(frame.columns), ["ts_code", "trade_date", "close"])
        self.assertEqual(frame.to_dict("records"), [{"ts_code": "000001.SZ", "trade_date": "20260701", "close": 10.16}])
        self.assertEqual(calls[0]["url"], "https://tushare.indevs.in/tushare/pro/daily")
        self.assertEqual(calls[0]["headers"], {"X-API-Key": "token-x"})
        self.assertEqual(calls[0]["params"]["ts_code"], "000001.SZ")
        self.assertEqual(calls[0]["timeout"], 9)

    def test_tushare_replay_adapter_tries_backup_base_url(self):
        from market_data.tushare_client import TushareReplayProApi

        calls = []

        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {"code": 0, "data": {"fields": ["ts_code"], "items": [["000001.SZ"]]}}

        class FakeRequests:
            def get(self, url, headers=None, params=None, timeout=None):
                calls.append(url)
                if "ai-tool.indevs.in" in url:
                    raise TimeoutError("primary timeout")
                return FakeResponse()

        pro = TushareReplayProApi(
            token="token-x",
            base_url="https://ai-tool.indevs.in/tushare/pro,https://tushare.indevs.in/tushare/pro",
            requests_module=FakeRequests(),
        )
        frame = pro.daily(ts_code="000001.SZ")

        self.assertEqual(frame.to_dict("records"), [{"ts_code": "000001.SZ"}])
        self.assertEqual(
            calls,
            [
                "https://ai-tool.indevs.in/tushare/pro/daily",
                "https://tushare.indevs.in/tushare/pro/daily",
            ],
        )

    def test_tushare_replay_adapter_splits_timeout_across_base_urls(self):
        from market_data.tushare_client import TushareReplayProApi

        calls = []

        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {"code": 0, "data": {"fields": ["ts_code"], "items": [["000001.SZ"]]}}

        class FakeRequests:
            def get(self, url, headers=None, params=None, timeout=None):
                calls.append({"url": url, "timeout": timeout})
                if "ai-tool.indevs.in" in url:
                    raise TimeoutError("primary timeout")
                return FakeResponse()

        pro = TushareReplayProApi(
            token="token-x",
            base_url="https://ai-tool.indevs.in/tushare/pro,https://tushare.indevs.in/tushare/pro",
            timeout_seconds=8,
            requests_module=FakeRequests(),
        )
        frame = pro.daily(ts_code="000001.SZ")

        self.assertEqual(frame.to_dict("records"), [{"ts_code": "000001.SZ"}])
        self.assertEqual([item["timeout"] for item in calls], [4.0, 4.0])

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
                "TUSHARE_TOKEN=dotenv-token\nTUSHARE_HTTP_URL=http://a.sszhixia.cn/\n",
                encoding="utf-8",
            )
            with patch.dict("os.environ", {}, clear=True), patch.object(Path, "cwd", return_value=Path(tmpdir)):
                pro = client.create_tushare_pro_api(ts_module=FakeTs())

        self.assertEqual(calls, [{"token": "dotenv-token", "timeout": client.TUSHARE_TIMEOUT_SECONDS}])
        self.assertEqual(pro._DataApi__http_url, "http://a.sszhixia.cn")

    def test_create_tushare_pro_api_prefers_dotenv_b_channel_over_legacy_environment(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        import market_data.tushare_client as client

        class FakeTs:
            def pro_api(self, token="", timeout=30):
                raise AssertionError("default runtime should prefer the Tushare B channel")

        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            env_path.write_text(
                "TUSHARE_TOKEN=dotenv-b-token\n"
                "TUSHARE_HTTP_URL=https://ai-tool.indevs.in/tushare/pro,https://tushare.indevs.in/tushare/pro\n",
                encoding="utf-8",
            )
            with patch.dict(
                "os.environ",
                {
                    "TUSHARE_TOKEN": "legacy-token",
                    "TUSHARE_HTTP_URL": "http://legacy-proxy.invalid/",
                },
                clear=True,
            ), patch.object(Path, "cwd", return_value=Path(tmpdir)):
                pro = client.create_tushare_pro_api(ts_module=FakeTs())

        self.assertIsInstance(pro, client.TushareReplayProApi)
        self.assertEqual(pro.token, "dotenv-b-token")
        self.assertEqual(
            pro.base_urls,
            [
                "https://ai-tool.indevs.in/tushare/pro",
                "https://tushare.indevs.in/tushare/pro",
            ],
        )

    def test_check_tushare_runtime_ready_reports_b_channel_provider(self):
        from unittest.mock import patch

        from market_data.tushare_client import check_tushare_runtime_ready

        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {"code": 0, "data": {"fields": ["ts_code"], "items": [["000001.SH"]]}}

        class FakeTs:
            def pro_api(self, token="", timeout=30):
                raise AssertionError("B channel should not use the legacy Tushare SDK")

        with patch("requests.get", return_value=FakeResponse()):
            result = check_tushare_runtime_ready(
                ts_module=FakeTs(),
                token="token-x",
                http_url="https://tushare.indevs.in/tushare/pro",
                timeout_seconds=2,
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["provider"], "tushare.b.daily")
        self.assertEqual(result["checks"][0]["row_count"], 1)

    def test_check_tushare_runtime_ready_uses_daily_probe_for_b_channel(self):
        from unittest.mock import patch

        from market_data.tushare_client import check_tushare_runtime_ready

        calls = []

        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {"code": 0, "data": {"fields": ["ts_code"], "items": [["000001.SZ"]]}}

        def fake_get(url, headers=None, params=None, timeout=None):
            calls.append({"url": url, "params": params, "timeout": timeout})
            return FakeResponse()

        with patch("requests.get", side_effect=fake_get):
            result = check_tushare_runtime_ready(
                token="token-x",
                http_url="https://tushare.indevs.in/tushare/pro",
                timeout_seconds=2,
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["provider"], "tushare.b.daily")
        self.assertEqual(result["checks"], [{"name": "daily", "row_count": 1}])
        self.assertEqual(calls[0]["url"], "https://tushare.indevs.in/tushare/pro/daily")
        self.assertEqual(calls[0]["params"], {"ts_code": "000001.SZ", "limit": 1})

    def test_check_tushare_runtime_ready_returns_success_for_index_basic(self):
        from market_data.tushare_client import check_tushare_runtime_ready

        calls = []

        class FakePro:
            def index_basic(self, **kwargs):
                calls.append(("index_basic", kwargs))
                return [{"ts_code": "000001.SH"}]

        class FakeTs:
            def pro_api(self, token="", timeout=30):
                calls.append(("pro_api", {"token": token, "timeout": timeout}))
                return FakePro()

        result = check_tushare_runtime_ready(
            ts_module=FakeTs(),
            token="token-x",
            http_url="http://proxy.invalid/",
            timeout_seconds=2,
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["provider"], "tushare.pro.index_basic")
        self.assertEqual(result["checks"][0]["row_count"], 1)
        self.assertEqual(calls[0], ("pro_api", {"token": "token-x", "timeout": 2}))
        self.assertEqual(calls[1], ("index_basic", {"limit": 1}))

    def test_check_tushare_runtime_ready_redacts_token_on_failure(self):
        from market_data.tushare_client import check_tushare_runtime_ready

        class FakePro:
            def index_basic(self, **kwargs):
                raise RuntimeError("bad token dotenv-token")

        class FakeTs:
            def pro_api(self, token="", timeout=30):
                return FakePro()

        result = check_tushare_runtime_ready(ts_module=FakeTs(), token="dotenv-token", http_url="http://proxy.invalid/")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_type"], "RuntimeError")
        self.assertIn("***", result["error_message"])
        self.assertNotIn("dotenv-token", result["error_message"])

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

    def test_investor_qa_fetcher_empty_endpoint_disables_env_fallback(self):
        from market_data.tushare_market_activity_service import fetch_investor_qa_rows

        captured = []
        previous = os.environ.get("INVESTOR_QA_ENDPOINT_URL")
        os.environ["INVESTOR_QA_ENDPOINT_URL"] = "https://example.invalid/env-investor-qa"

        class FakePro:
            def irm_qa_sh(self, **kwargs):
                return []

            def irm_qa_sz(self, **kwargs):
                return []

        def fake_open(request, timeout=0):
            captured.append(request.full_url)
            self.fail("explicit empty endpoint_url should disable external fallback")

        try:
            rows = fetch_investor_qa_rows(
                "2026-05-22",
                endpoint_url="",
                pro=FakePro(),
                opener=fake_open,
            )
        finally:
            if previous is None:
                os.environ.pop("INVESTOR_QA_ENDPOINT_URL", None)
            else:
                os.environ["INVESTOR_QA_ENDPOINT_URL"] = previous

        self.assertEqual(rows, [])
        self.assertEqual(captured, [])


if __name__ == "__main__":
    unittest.main()
