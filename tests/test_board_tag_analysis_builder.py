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

    def test_build_board_tag_analysis_sections_contract_falls_back_when_ai_summary_is_empty(self):
        result = build_board_tag_analysis_sections_contract(
            data={
                "tag_distribution": {"存储芯片": 5, "国家大基金持股": 3, "半导体": 2},
                "status_distribution": {},
                "high_lianban_stocks": [],
                "market_stats": {"up_count": 2900, "down_count": 2100},
            },
            analyze_sector_distribution=lambda *args, **kwargs: {},
        )

        rendered = "\n".join(str(line or "") for line in result["lines"])
        self.assertIn("**主热标签**：存储芯片（5次）", rendered)
        self.assertIn("存储芯片5次、国家大基金持股3次、半导体2次", rendered)
        self.assertIn("上涨2900家、下跌2100家", rendered)
        self.assertNotIn("**暂无板块分布数据**", rendered)

    def test_build_board_tag_analysis_sections_contract_labels_actual_top50_sample(self):
        result = build_board_tag_analysis_sections_contract(
            data={
                "hot_rank_top30": [{"code": f"000{idx:03d}", "name": f"热股{idx}"} for idx in range(1, 51)],
                "hot_rank_sample_size": 50,
                "hot_rank_sample_target": 50,
                "tag_distribution": {"CPO": 8},
                "status_distribution": {},
                "high_lianban_stocks": [],
                "market_stats": {"up_count": 2900, "down_count": 2100},
            },
            analyze_sector_distribution=None,
            enabled_node_keys=["source_note"],
        )

        rendered = "\n".join(str(line or "") for line in result["lines"])
        self.assertIn("基于热度前50个股", rendered)
        self.assertIn("热度前50个股详情见第四章", rendered)
        self.assertNotIn("前30", rendered)

    def test_build_board_tag_analysis_sections_contract_marks_zero_breadth_as_incomplete(self):
        result = build_board_tag_analysis_sections_contract(
            data={
                "tag_distribution": {"CPO": 8},
                "status_distribution": {},
                "high_lianban_stocks": [],
                "market_stats": {"up_count": 0, "down_count": 0},
            },
            analyze_sector_distribution=lambda *args, **kwargs: {},
        )

        rendered = "\n".join(str(line or "") for line in result["lines"])
        self.assertNotIn("上涨0家、下跌0家", rendered)
        self.assertIn("涨跌家数未采集，关键数据不完整，停止生成", rendered)

    def test_build_board_tag_analysis_sections_contract_renders_no_data_when_tags_missing(self):
        result = build_board_tag_analysis_sections_contract(
            data={"tag_distribution": {}, "status_distribution": {}, "high_lianban_stocks": []},
            analyze_sector_distribution=None,
        )

        rendered = "\n".join(str(line or "") for line in result["lines"])
        self.assertIn("**暂无板块分布数据**", rendered)


if __name__ == "__main__":
    unittest.main()
