import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.market_overview_builder import build_market_trend_sections_contract


class MarketOverviewBuilderTest(unittest.TestCase):
    def test_build_market_trend_sections_contract_renders_indices_volume_and_sentiment(self):
        result = build_market_trend_sections_contract(
            data={
                "indices": {
                    "上证指数": {"点位": 3200.12, "涨跌幅": 0.52},
                    "深证成指": {"点位": 10123.45, "涨跌幅": -0.21},
                },
                "wind_a_alternative": {"点位": 5432.1, "涨跌幅": 0.31},
                "total_turnover": 16888.0,
                "zt_pool": [{"code": "000001"}] * 35,
                "dt_pool": [{"code": "000002"}] * 3,
                "market_stats": {"up_count": 3600, "down_count": 1600},
            },
            target_date="2026-04-22",
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("## 三、大盘趋势判断", rendered)
        self.assertIn("| 上证指数 | 3200.12点 | +0.52% | 强势上涨 |", rendered)
        self.assertIn("| 中证全指 | 5432.10点 | +0.31% | 强势上涨 |", rendered)
        self.assertIn("| 2026-04-22 | 16888.00亿元 | 正常轮动 | 量能适中，观望情绪 |", rendered)
        self.assertIn("| 涨停家数 | 35只 | 赚钱效应尚可 |", rendered)
        self.assertIn("| 涨跌比 | 3600:1600 | 多头占优 |", rendered)
        self.assertTrue(any(log["step"] == "render.market_trend_sections" for log in result["module_logs"]))


if __name__ == "__main__":
    unittest.main()
