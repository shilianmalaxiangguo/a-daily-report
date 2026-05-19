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


if __name__ == "__main__":
    unittest.main()
