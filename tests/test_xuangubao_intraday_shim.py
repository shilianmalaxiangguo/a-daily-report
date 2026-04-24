import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class XuangubaoIntradayShimTest(unittest.TestCase):
    def test_local_xuangubao_intraday_shim_imports_for_entry_runtime(self):
        try:
            module = __import__("xuangubao_intraday", fromlist=["xuangubao_intraday"])
        except ModuleNotFoundError as error:
            self.fail(f"xuangubao_intraday shim should exist for entry runtime: {error}")

        self.assertTrue(hasattr(module, "XuangubaoIntradayAnalyzer"))
        analyzer = module.XuangubaoIntradayAnalyzer()
        self.assertTrue(hasattr(analyzer, "fetch_xuangubao_data"))


if __name__ == "__main__":
    unittest.main()
