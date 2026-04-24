import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.market_analysis_builder import build_market_and_sector_analysis_contract


class MarketAnalysisBuilderTest(unittest.TestCase):
    def test_build_market_and_sector_analysis_contract_can_render_only_enabled_nodes(self):
        result = build_market_and_sector_analysis_contract(
            data={"total_turnover": 15600},
            market_analysis={
                "market_status": "震荡修复",
                "risk_sectors": [{"name": "地产", "risk_level": "high", "net_outflow": 12.5, "change": -2.13}],
                "hot_sectors": [("军工", 5), ("航空", 3), ("机器人", 2)],
            },
            sh_change=0.56,
            indices={"深证成指": {"涨跌幅": -0.22}, "创业板指": {"涨跌幅": 0.88}},
            exit_analysis={"sector_name": "军工"},
            main_sectors_info=[],
            secondary_sectors_info=[{"name": "机器人", "zt_count": 6, "change": 2.1, "net_inflow": 4.2}],
            ai_group_concepts_into_chains=lambda concepts: {"军工链": ["军工", "航空"], "机器人链": ["机器人"]},
            enabled_node_keys=["header", "market_state", "risk_sectors"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("## 八、市场与板块分析", rendered)
        self.assertIn("### 1. 市场整体状态", rendered)
        self.assertIn("### 4. 风险板块分析", rendered)
        self.assertNotIn("### 2. 主线板块分析", rendered)
        self.assertNotIn("### 3. 次强板块分析", rendered)
        self.assertNotIn("### 5. 市场关注度分析", rendered)

    def test_build_market_and_sector_analysis_contract_renders_mainline_and_risk(self):
        result = build_market_and_sector_analysis_contract(
            data={"total_turnover": 15600},
            market_analysis={
                "market_status": "震荡修复",
                "risk_sectors": [{"name": "地产", "risk_level": "high", "net_outflow": 12.5, "change": -2.13}],
                "hot_sectors": [("军工", 5), ("航空", 3), ("机器人", 2)],
            },
            sh_change=0.56,
            indices={"深证成指": {"涨跌幅": -0.22}, "创业板指": {"涨跌幅": 0.88}},
            exit_analysis={"sector_name": "军工"},
            main_sectors_info=[],
            secondary_sectors_info=[{"name": "机器人", "zt_count": 6, "change": 2.1, "net_inflow": 4.2}],
            ai_group_concepts_into_chains=lambda concepts: {"军工链": ["军工", "航空"], "机器人链": ["机器人"]},
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("## 八、市场与板块分析", rendered)
        self.assertIn("- **现在是什么情况**: 震荡修复", rendered)
        self.assertIn("**当前主线**: 军工", rendered)
        self.assertIn("**次强板块**", rendered)
        self.assertIn("🔴高风险", rendered)
        self.assertIn("**热榜关注产业链**", rendered)
        self.assertTrue(any(log["step"] == "render.market_and_sector_analysis" for log in result["module_logs"]))


if __name__ == "__main__":
    unittest.main()
