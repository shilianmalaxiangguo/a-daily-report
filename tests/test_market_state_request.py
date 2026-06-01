import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from domains.market_state.request import collect_market_state_request_bundle


class _TimerStub:
    def __init__(self):
        self.records = []

    def record(self, label, order):
        self.records.append((label, order))
        return 0.1, 0.2


class MarketStateRequestTest(unittest.TestCase):
    def test_collect_market_state_request_bundle_collects_first_request_slice(self):
        timer = _TimerStub()
        emitted = []
        request_registry = {
            "total_turnover": lambda *, target_date: 12345.6,
            "major_indices": lambda *, target_date: [
                {"code": "000001", "change_pct": 1.2, "data_source": "tushare.index_daily"}
            ],
            "wind_a": lambda *, target_date: {
                "price": 5432.1,
                "change_pct": 0.8,
                "data_source": "tushare.index_daily",
            },
            "csi1000": lambda *, target_date: {
                "price": 6123.4,
                "change_pct": 1.1,
                "data_source": "tushare.index_daily",
            },
        }

        result = collect_market_state_request_bundle(
            "2026-04-22",
            request_registry=request_registry,
            timer=timer,
            emit=emitted.append,
        )

        self.assertEqual(result["results"]["total_turnover"], 12345.6)
        self.assertEqual(result["results"]["turnover_data"]["date"], "2026-04-22")
        self.assertEqual(result["results"]["indices"][0]["code"], "000001")
        self.assertEqual(result["results"]["wind_a_alternative"]["price"], 5432.1)
        self.assertEqual(result["results"]["csi1000_index"]["price"], 6123.4)
        self.assertTrue(result["data_status"]["两市成交额"])
        self.assertTrue(result["data_status"]["主要指数"])
        self.assertTrue(result["data_status"]["中证全指"])
        self.assertTrue(result["data_status"]["中证1000"])
        self.assertTrue(result["step_status"]["两市成交额获取"])
        self.assertTrue(result["step_status"]["主要指数获取"])
        self.assertTrue(result["step_status"]["中证全指获取"])
        self.assertTrue(result["step_status"]["中证1000获取"])
        self.assertEqual(len(result["module_logs"]), 4)
        self.assertEqual(timer.records[0], ("两市成交额获取", 1))
        self.assertTrue(any("两市成交额" in line for line in emitted))
        self.assertIn("  1️⃣ 获取两市成交额（Tushare 优先）...", emitted)
        self.assertIn("  2️⃣ 获取三大指数（Tushare 优先）...", emitted)
        self.assertIn("  3️⃣ 获取中证全指（Tushare 优先）...", emitted)
        self.assertIn("  3.5️⃣ 获取中证1000（Tushare 优先）...", emitted)
        provider_by_step = {log["step"]: log["details"].get("provider") for log in result["module_logs"]}
        self.assertEqual(provider_by_step["request.total_turnover"], "tushare-first")
        self.assertEqual(provider_by_step["request.major_indices"], "tushare.index_daily")
        self.assertEqual(provider_by_step["request.wind_a"], "tushare.index_daily")
        self.assertEqual(provider_by_step["request.csi1000"], "tushare.index_daily")


if __name__ == "__main__":
    unittest.main()
