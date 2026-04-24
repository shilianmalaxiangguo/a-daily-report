import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.board_tag_analysis_builder import build_board_tag_analysis_sections_contract


class BoardTagAnalysisBuilderTest(unittest.TestCase):
    def test_build_board_tag_analysis_sections_contract_can_render_only_enabled_nodes(self):
        result = build_board_tag_analysis_sections_contract(
            data={
                "tag_distribution": {"军工": 6, "机器人": 4},
                "status_distribution": {"涨停": 3},
                "high_lianban_stocks": [{"name": "军工一号"}],
                "market_stats": {"up_count": 3000, "down_count": 1700},
            },
            analyze_sector_distribution=lambda tag_distribution, status_distribution, high_lianban_stocks, top_n=15, market_stats=None: (
                "**主热方向**：军工\n- 热度集中，主线抱团明显"
            ),
            enabled_node_keys=["header", "analysis"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("## 十一、板块标签分析", rendered)
        self.assertIn("### 板块分布AI分析", rendered)
        self.assertNotIn("数据来源", rendered)
        self.assertNotIn("---", rendered)

    def test_build_board_tag_analysis_sections_contract_renders_ai_summary(self):
        result = build_board_tag_analysis_sections_contract(
            data={
                "tag_distribution": {"军工": 6, "机器人": 4},
                "status_distribution": {"涨停": 3},
                "high_lianban_stocks": [{"name": "军工一号"}],
                "market_stats": {"up_count": 3000, "down_count": 1700},
            },
            analyze_sector_distribution=lambda tag_distribution, status_distribution, high_lianban_stocks, top_n=15, market_stats=None: (
                "**主热方向**：军工\n- 热度集中，主线抱团明显"
            ),
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("## 十一、板块标签分析", rendered)
        self.assertIn("**主热方向**：军工", rendered)
        self.assertTrue(any(log["step"] == "render.board_tag_analysis" for log in result["module_logs"]))


if __name__ == "__main__":
    unittest.main()
