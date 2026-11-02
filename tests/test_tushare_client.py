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
            with patch.dict("os.environ", {}, clear=True), patch.object(client, "PROJECT_ENV", env_path):
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
            ), patch.object(client, "PROJECT_ENV", env_path):
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

    def test_foreign_working_directory_cannot_supply_credentials(self):
        import tempfile
        from unittest.mock import patch
        import market_data.tushare_client as client
        with tempfile.TemporaryDirectory() as tmp:
            foreign = Path(tmp) / 'foreign'; foreign.mkdir()
            project = Path(tmp) / 'project'; project.mkdir()
            (foreign / '.env').write_text('TUSHARE_TOKEN=foreign-token\nTUSHARE_HTTP_URL=https://foreign.invalid/tushare/pro\n')
            own = project / '.env'
            own.write_text('TUSHARE_TOKEN=project-token\nTUSHARE_HTTP_URL=https://project.invalid/tushare/pro\n')
            with patch.dict(os.environ, {}, clear=True), patch.object(client, 'PROJECT_ENV', own), \
                 patch.object(Path, 'cwd', return_value=foreign):
                config = client.resolve_tushare_runtime_config()
                self.assertEqual(config['token'], 'project-token')
                self.assertEqual(config['http_url'], 'https://project.invalid/tushare/pro')
                own.unlink()
                self.assertEqual(client.resolve_tushare_runtime_config(), {'token': '', 'http_url': ''})

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











if __name__ == "__main__":
    unittest.main()
