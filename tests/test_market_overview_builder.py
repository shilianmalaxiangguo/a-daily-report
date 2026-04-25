import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.market_overview_builder import build_market_trend_sections_contract


class MarketOverviewBuilderTest(unittest.TestCase):
    def test_build_market_trend_sections_contract_renders_market_base_tables(self):
        result = build_market_trend_sections_contract(
            data={
                "indices": {
                    "上证指数": {"点位": 3200.12, "涨跌幅": 0.52},
                    "深证成指": {"点位": 10123.45, "涨跌幅": -0.21},
                    "创业板指": {"点位": 2123.45, "涨跌幅": -1.35},
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
        self.assertIn("## 二、市场基底", rendered)
        self.assertIn("### 1. 指数与市场底色", rendered)
        self.assertIn("| 指标 | 数值 | 涨跌幅 | 解读 |", rendered)
        self.assertIn("| 上证指数 | 3200.12 | +0.52% |", rendered)
        self.assertIn("| 两市成交额 | 16888.00亿 | - |", rendered)
        self.assertIn("| 涨停 / 跌停 | 35 / 3 | - |", rendered)
        self.assertIn("### 2. 市场状态结论", rendered)
        self.assertIn("| 项目 | 结论 |", rendered)
        self.assertIn("| 市场状态 |", rendered)
        self.assertIn("| 当前盈亏比 |", rendered)

    def test_build_market_trend_sections_contract_can_render_only_enabled_nodes(self):
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
            enabled_node_keys=["header", "indices", "sentiment"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("## 二、市场基底", rendered)
        self.assertIn("### 1. 指数与市场底色", rendered)
        self.assertNotIn("### 2. 市场状态结论", rendered)

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
        self.assertIn("## 二、市场基底", rendered)
        self.assertIn("| 上证指数 | 3200.12 | +0.52% | 强势上涨 |", rendered)
        self.assertIn("| 中证全指 | 5432.10 | +0.31% | 强势上涨 |", rendered)
        self.assertIn("| 两市成交额 | 16888.00亿 | - | 量能不差，但赚钱效应不足 |", rendered)
        self.assertIn("| 涨停 / 跌停 | 35 / 3 | - | 活跃度还在，但亏钱端不轻 |", rendered)
        self.assertIn("| 涨跌比 | 3600 / 1600 | - | 多头仍占优 |", rendered)
        self.assertIn("### 2. 市场状态结论", rendered)
        self.assertTrue(any(log["step"] == "render.market_trend_sections" for log in result["module_logs"]))


if __name__ == "__main__":
    unittest.main()
