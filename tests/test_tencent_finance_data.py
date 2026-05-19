import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class TencentFinanceDataTest(unittest.TestCase):
    def test_get_stock_batch_info_exists_even_when_legacy_class_lacks_it(self):
        module = __import__("tencent_finance_data", fromlist=["tencent_finance_data"])

        self.assertTrue(hasattr(module.TencentFinanceData(), "get_stock_batch_info"))

    def test_get_stock_batch_info_parses_tencent_quote_lines(self):
        module = __import__("tencent_finance_data", fromlist=["tencent_finance_data"])

        class _Response:
            text = (
                'v_sz000001="51~平安银行~000001~12.34~11.90~12.00~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~3.70~12.80~11.70~0~0~1850000";'
            )

        class _Session:
            def __init__(self):
                self.headers = {}

            def get(self, url, timeout=0):
                self.url = url
                return _Response()

        data = module.TencentFinanceData()
        data.session = _Session()

        result = data.get_stock_batch_info(["000001"])

        self.assertEqual(result["000001"]["name"], "平安银行")
        self.assertEqual(result["000001"]["change_pct"], 3.7)
        self.assertEqual(result["000001"]["close"], 12.34)
        self.assertEqual(result["000001"]["open"], 12.0)
        self.assertEqual(result["000001"]["high"], 12.8)
        self.assertEqual(result["000001"]["low"], 11.7)


if __name__ == "__main__":
    unittest.main()
