import importlib
import sys
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class _THSResponse:
    def __init__(self, rows):
        self.data = list(rows or [])
        self.df = pd.DataFrame(list(rows or []))


class _FakeTHS:
    def __init__(self, *, industry_rows=None, concept_rows=None, block_rows_by_code=None, block_errors_by_code=None):
        self._industry_rows = list(industry_rows or [])
        self._concept_rows = list(concept_rows or [])
        self._block_rows_by_code = dict(block_rows_by_code or {})
        self._block_errors_by_code = dict(block_errors_by_code or {})
        self.block_calls = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def ths_industry(self):
        return _THSResponse(self._industry_rows)

    def ths_concept(self):
        return _THSResponse(self._concept_rows)

    def market_data_block(self, link_code, query_key):
        self.block_calls.append((link_code, query_key))
        if link_code in self._block_errors_by_code:
            raise self._block_errors_by_code[link_code]
        return _THSResponse(self._block_rows_by_code.get(link_code, []))


class _BrokenTHS:
    def __enter__(self):
        raise RuntimeError("游客账户限流")

    def __exit__(self, exc_type, exc, tb):
        return False


class THSSectorRuntimeTest(unittest.TestCase):
    def _load_module(self):
        try:
            return importlib.import_module("input.ths_sector_runtime")
        except ModuleNotFoundError as error:
            self.fail(f"input.ths_sector_runtime should exist: {error}")

    def test_get_sector_turnover_snapshot_from_ths_normalizes_exact_industry_match(self):
        runtime = self._load_module()
        fake_ths = _FakeTHS(
            industry_rows=[{"代码": "URFI881121", "名称": "半导体"}],
            concept_rows=[],
            block_rows_by_code={
                "URFI881121": [
                    {
                        "总金额": 270294100000,
                        "领涨股": "300613",
                        "上涨家数": 114,
                        "下跌家数": 64,
                        "板块总市值": 9001238800000,
                        "板块流通市值": 6436869100000,
                    }
                ]
            },
        )

        result = runtime.get_sector_turnover_snapshot_from_ths(
            "半导体",
            target_date="2026-04-24",
            total_turnover=12345.6,
            helpers={
                "ths_client_factory": lambda: fake_ths,
                "sector_name_matches": lambda left, right: str(left or "") == str(right or "") or str(left or "") in str(right or "") or str(right or "") in str(left or ""),
            },
        )

        self.assertEqual(result["date"], "2026-04-24")
        self.assertEqual(result["sector_name"], "半导体")
        self.assertEqual(result["sector_kind"], "industry")
        self.assertEqual(result["matched_sector_names"], ["半导体"])
        self.assertEqual(result["matched_sector_codes"], ["URFI881121"])
        self.assertEqual(result["matched_sector_count"], 1)
        self.assertEqual(result["sector_turnover"], 2702.94)
        self.assertEqual(result["total_turnover"], 12345.6)
        self.assertEqual(result["turnover_share_pct"], 21.89)
        self.assertEqual(result["leader_stock"], "300613")
        self.assertEqual(result["up_count"], 114)
        self.assertEqual(result["down_count"], 64)
        self.assertEqual(result["source"], "thsdk.market_data_block")
        self.assertEqual(fake_ths.block_calls, [("URFI881121", "基础数据")])

    def test_get_sector_turnover_snapshot_from_ths_aggregates_fuzzy_industry_matches_before_concepts(self):
        runtime = self._load_module()
        fake_ths = _FakeTHS(
            industry_rows=[
                {"代码": "URFI100001", "名称": "通信设备"},
                {"代码": "URFI100002", "名称": "通信服务"},
            ],
            concept_rows=[
                {"代码": "URFI900001", "名称": "卫星通信"},
            ],
            block_rows_by_code={
                "URFI100001": [{"总金额": 120000000000, "上涨家数": 20, "下跌家数": 5}],
                "URFI100002": [{"总金额": 80000000000, "上涨家数": 12, "下跌家数": 6}],
                "URFI900001": [{"总金额": 999999999999}],
            },
        )

        result = runtime.get_sector_turnover_snapshot_from_ths(
            "通信",
            target_date="2026-04-24",
            total_turnover=10000.0,
            helpers={
                "ths_client_factory": lambda: fake_ths,
                "sector_name_matches": lambda left, right: str(left or "") == str(right or "") or str(left or "") in str(right or "") or str(right or "") in str(left or ""),
            },
        )

        self.assertEqual(result["sector_name"], "通信")
        self.assertEqual(result["sector_kind"], "industry")
        self.assertEqual(result["matched_sector_names"], ["通信设备", "通信服务"])
        self.assertEqual(result["matched_sector_codes"], ["URFI100001", "URFI100002"])
        self.assertEqual(result["matched_sector_count"], 2)
        self.assertEqual(result["sector_turnover"], 2000.0)
        self.assertEqual(result["turnover_share_pct"], 20.0)
        self.assertEqual(result["up_count"], 32)
        self.assertEqual(result["down_count"], 11)
        self.assertEqual(
            fake_ths.block_calls,
            [
                ("URFI100001", "基础数据"),
                ("URFI100002", "基础数据"),
            ],
        )

    def test_get_sector_turnover_snapshot_from_ths_degrades_when_thsdk_missing(self):
        runtime = self._load_module()
        previous_thsdk = sys.modules.pop("thsdk", None)
        try:
            result = runtime.get_sector_turnover_snapshot_from_ths(
                "通信",
                target_date="2026-04-24",
                total_turnover=10000.0,
            )
        finally:
            if previous_thsdk is not None:
                sys.modules["thsdk"] = previous_thsdk

        self.assertEqual(result["date"], "2026-04-24")
        self.assertEqual(result["sector_name"], "通信")
        self.assertEqual(result["sector_turnover"], 0.0)
        self.assertEqual(result["turnover_share_pct"], 0.0)
        self.assertEqual(result["source_status"], "missing_dependency")
        self.assertIn("thsdk", result["source_error"])

    def test_get_sector_turnover_snapshot_from_ths_returns_error_snapshot_when_client_unavailable(self):
        runtime = self._load_module()

        result = runtime.get_sector_turnover_snapshot_from_ths(
            "通信",
            target_date="2026-04-24",
            total_turnover=10000.0,
            helpers={
                "ths_client_factory": lambda: _BrokenTHS(),
            },
        )

        self.assertEqual(result["date"], "2026-04-24")
        self.assertEqual(result["sector_name"], "通信")
        self.assertEqual(result["sector_turnover"], 0.0)
        self.assertEqual(result["turnover_share_pct"], 0.0)
        self.assertEqual(result["source_status"], "error")
        self.assertIn("游客账户限流", result["source_error"])

    def test_get_sector_turnover_snapshot_from_ths_keeps_partial_data_when_one_block_query_fails(self):
        runtime = self._load_module()
        fake_ths = _FakeTHS(
            industry_rows=[
                {"代码": "URFI100001", "名称": "通信设备"},
                {"代码": "URFI100002", "名称": "通信服务"},
            ],
            block_rows_by_code={
                "URFI100001": [{"总金额": 120000000000, "上涨家数": 20, "下跌家数": 5}],
            },
            block_errors_by_code={
                "URFI100002": RuntimeError("通信服务限流"),
            },
        )

        result = runtime.get_sector_turnover_snapshot_from_ths(
            "通信",
            target_date="2026-04-24",
            total_turnover=10000.0,
            helpers={
                "ths_client_factory": lambda: fake_ths,
                "sector_name_matches": lambda left, right: str(left or "") == str(right or "") or str(left or "") in str(right or "") or str(right or "") in str(left or ""),
            },
        )

        self.assertEqual(result["sector_turnover"], 1200.0)
        self.assertEqual(result["turnover_share_pct"], 12.0)
        self.assertEqual(result["source_status"], "degraded")
        self.assertEqual(result["failed_sector_codes"], ["URFI100002"])
        self.assertIn("URFI100002", result["source_error"])


if __name__ == "__main__":
    unittest.main()
