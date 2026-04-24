import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class DataCollectorShimTest(unittest.TestCase):
    def test_local_data_collector_shim_imports_for_entry_runtime(self):
        try:
            module = __import__("data_collector", fromlist=["data_collector"])
        except ModuleNotFoundError as error:
            self.fail(f"data_collector shim should exist for entry runtime: {error}")

        self.assertTrue(hasattr(module, "AShareDataCollector"))
        collector = module.AShareDataCollector()
        self.assertTrue(hasattr(collector, "get_wanzhu_top10"))


if __name__ == "__main__":
    unittest.main()
