import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from domains.market_activity.infer import (
    analyze_market_and_sectors,
    resolve_market_mainline_context,
)


class MarketActivityInferAnalysisTest(unittest.TestCase):
    def test_analyze_market_and_sectors_builds_status_mainlines_risk_and_hot_concepts(self):
        result = analyze_market_and_sectors(
            {
                "indices": {
                    "上证指数": {"涨跌幅": 0.8},
                    "深证成指": {"涨跌幅": 0.7},
                    "创业板指": {"涨跌幅": 0.2},
                },
                "sector_fund_flow": {
                    "outflow": [
                        {"name": "地产", "zljlr": -12.5, "zdf": -3.2},
                        {"name": "消费", "zljlr": -5.0, "zdf": -1.0},
                    ]
                },
                "hot_rank_top30": [
                    {"name": "军工一号", "concepts": ["军工", "低空"]},
                    {"name": "军工二号", "concepts": ["军工", "商业航天"]},
                ],
            },
            helpers={
                "_build_unified_sector_strength_rows": lambda data: [
                    {"name": "军工", "role": "main", "unified_score": 88},
                    {"name": "机器人", "role": "secondary", "unified_score": 55},
                    {"name": "低空", "role": "observe", "unified_score": 32},
                ]
            },
        )

        self.assertEqual(result["market_status"], "小幅上涨")
        self.assertEqual(result["main_sectors"][0]["name"], "军工")
        self.assertEqual(result["secondary_sectors"][0]["name"], "机器人")
        self.assertEqual(result["sector_analysis"]["军工"]["unified_score"], 88)
        self.assertEqual(result["risk_sectors"][0]["name"], "地产")
        self.assertEqual(result["risk_sectors"][0]["risk_level"], "medium")
        self.assertEqual(result["hot_sectors"][0], ("军工", 2))

    def test_resolve_market_mainline_context_forces_top_row_and_extracts_dragons(self):
        result = resolve_market_mainline_context(
            {
                "zt_pool": [
                    {"代码": "000001", "名称": "军工龙头", "所属板块": "军工", "连板数": 3},
                    {"代码": "000002", "名称": "机器人一号", "所属板块": "机器人", "连板数": 1},
                ]
            },
            {
                "main_sectors": [],
                "secondary_sectors": [],
                "unified_sector_rows": [
                    {"name": "军工", "unified_score": 40},
                    {"name": "机器人", "unified_score": 33},
                    {"name": "消费", "unified_score": 20},
                ],
            },
            helpers={"normalize_stock_code": lambda code: str(code or "")},
        )

        self.assertEqual(result["main_sectors_info"][0]["name"], "军工")
        self.assertEqual(result["main_sectors"], ["军工"])
        self.assertEqual(result["secondary_sectors"], ["机器人", "消费"])
        self.assertEqual(result["dragon_stocks"][0]["code"], "000001")
        self.assertEqual(result["dragon_stocks"][0]["lianban"], 3)


if __name__ == "__main__":
    unittest.main()
