import importlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class TencentSectorRuntimeTest(unittest.TestCase):
    def _load_module(self):
        try:
            return importlib.import_module("input.tencent_sector_runtime")
        except ModuleNotFoundError as error:
            self.fail(f"input.tencent_sector_runtime should exist: {error}")

    def test_builds_sector_turnover_snapshot_from_existing_cje(self):
        runtime = self._load_module()

        result = runtime.get_sector_turnover_snapshot_from_tencent_fund_flow(
            "半导体",
            {
                "inflow": [
                    {"name": "半导体", "code": "pt01801081", "cje": 26381045.0, "lzg_name": "富瀚微"}
                ],
                "outflow": [],
            },
            target_date="2026-04-24",
            total_turnover=26414.92,
        )

        self.assertEqual(result["sector_name"], "半导体")
        self.assertEqual(result["sector_code"], "pt01801081")
        self.assertEqual(result["sector_turnover"], 2638.1)
        self.assertEqual(result["turnover_share_pct"], 9.99)
        self.assertEqual(result["leader_stock"], "富瀚微")
        self.assertEqual(result["source"], "tencent.fundflow.getHyRank")

    def test_refetches_tencent_rows_when_snapshot_only_has_sector_code(self):
        runtime = self._load_module()

        result = runtime.get_sector_turnover_snapshot_from_tencent_fund_flow(
            "半导体",
            {"inflow": [{"name": "半导体", "code": "pt01801081"}], "outflow": []},
            target_date="2026-04-24",
            total_turnover=26414.92,
            fetch_sector_fund_flow_rows=lambda: [
                {"name": "电池", "code": "pt01801737", "cje": 12665334.0},
                {"name": "半导体", "code": "pt01801081", "cje": 26381045.0, "lzg": {"name": "富瀚微"}},
            ],
        )

        self.assertEqual(result["sector_code"], "pt01801081")
        self.assertEqual(result["sector_turnover"], 2638.1)
        self.assertEqual(result["turnover_share_pct"], 9.99)
        self.assertEqual(result["leader_stock"], "富瀚微")


if __name__ == "__main__":
    unittest.main()
