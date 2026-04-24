import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from selection.trend_snapshot_runtime import (
    build_extreme_conviction_list,
    build_leader_memory_bank,
    build_sector_trend_snapshot,
)


class SelectionTrendRuntimeTest(unittest.TestCase):
    def test_build_sector_trend_snapshot_prefers_dense_sector_and_anchor(self):
        result = build_sector_trend_snapshot(
            candidates=[
                {"code": "000001", "sector": "军工", "score": 75},
                {"code": "000002", "sector": "军工", "score": 55},
                {"code": "000003", "sector": "消费", "score": 42},
            ],
            watchlist=[
                {"code": "000001", "sector": "军工"},
                {"code": "000004", "sector": "军工"},
            ],
            evaluated_stocks=[
                {"code": "000001", "name": "军工一号", "sector": "军工", "tomorrow_strength": 82, "连板数": 2, "reason": "龙一", "pattern": "T字板"},
                {"code": "000003", "name": "消费一号", "sector": "消费", "tomorrow_strength": 40, "连板数": 0, "reason": "", "pattern": ""},
            ],
            dragon_stocks=[
                {"code": "000001", "name": "军工一号", "sector": "军工", "lianban": 2},
            ],
            zt_pool_by_sector={"军工": [{"code": "000001"}, {"code": "000002"}]},
            helpers={
                "normalize_stock_code": lambda code: str(code or ""),
                "stock_matches_sector": lambda stock, sector_name: stock.get("sector") == sector_name,
                "_safe_float": lambda value, default=0.0: float(value or default),
            },
        )

        self.assertEqual(result[0]["sector"], "军工")
        self.assertEqual(result[0]["anchor_code"], "000001")
        self.assertGreater(result[0]["density_score"], result[1]["density_score"])

    def test_build_conviction_and_memory_outputs_keep_mainline_priority(self):
        sector_snapshot = [{"sector": "军工", "anchor_code": "000001", "anchor_reason": "板块高标", "anchor_lianban": 3, "density_score": 78}]

        conviction = build_extreme_conviction_list(
            evaluated_stocks=[
                {"code": "000001", "sector": "军工", "tomorrow_strength": 80, "连板数": 3, "reason": "龙一", "pattern": "T字板"},
                {"code": "000002", "sector": "消费", "tomorrow_strength": 75, "连板数": 0, "reason": "", "pattern": ""},
            ],
            mainline_name="军工",
            sector_snapshot=sector_snapshot,
            helpers={
                "normalize_stock_code": lambda code: str(code or ""),
                "sector_name_matches": lambda sector, mainline: sector == mainline,
                "_safe_float": lambda value, default=0.0: float(value or default),
            },
        )
        memory = build_leader_memory_bank(
            sector_snapshot=sector_snapshot,
            watchlist=[{"code": "000001", "name": "军工一号", "sector": "军工", "reason": "龙一"}],
            dragon_stocks=[{"code": "000001", "name": "军工一号", "sector": "军工", "lianban": 3}],
            hot_rank_top30=[{"code": "000001"}],
            helpers={
                "normalize_stock_code": lambda code: str(code or ""),
                "_safe_float": lambda value, default=0.0: float(value or default),
            },
        )

        self.assertEqual(conviction[0]["code"], "000001")
        self.assertIn("主线内核", conviction[0]["conviction_reason"])
        self.assertEqual(memory[0]["code"], "000001")
        self.assertIn("热榜第1", memory[0]["remember_reason"])


if __name__ == "__main__":
    unittest.main()
