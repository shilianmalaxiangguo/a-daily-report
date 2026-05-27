import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.market_structure_judgement import (
    build_market_structure_judgement,
    build_market_structure_knowledge_update,
    render_market_structure_section,
)


class MarketStructureJudgementTest(unittest.TestCase):
    def test_builds_low_frequency_focus_from_strong_index_weak_breadth_sample(self):
        judgement = build_market_structure_judgement(
            data={
                "indices": {"创业板指": {"涨跌幅": 1.2}},
                "total_turnover": 32600.0,
                "market_stats": {"up_count": 947, "down_count": 4300},
            },
            market_research_snapshot={
                "market_structure_inputs": {
                    "opposition_rotation": ["消费", "白酒"],
                    "old_mainline": "科技",
                    "old_mainline_fatigue": True,
                    "neutral_topic": "",
                },
                "mainline_turnover_summary": {
                    "turnover_share_trend_summary": "科技老方向仍活跃，但短线疲态上升。",
                },
            },
        )

        self.assertEqual(judgement["tomorrow_rhythm"], "低频聚焦")
        self.assertEqual(judgement["candidate_policy"], "只保留主线核心；题材荒时不从旧方向强行扩散候选")
        self.assertIn("指数强但真实赚钱效应弱", judgement["index_profit_relation"])
        self.assertIn("成交额高位但结构集中", judgement["turnover_distribution"])
        self.assertIn("对立反弹", judgement["rotation_nature"])
        self.assertIn("短线疲态", judgement["old_mainline_fatigue"])
        self.assertIn("低频聚焦", judgement["action_reason_text"])

    def test_renders_front_page_section_with_compact_lines(self):
        judgement = build_market_structure_judgement(
            data={
                "indices": {"创业板指": {"涨跌幅": 1.2}},
                "total_turnover": 32600.0,
                "market_stats": {"up_count": 947, "down_count": 4300},
            },
            market_research_snapshot={
                "market_structure_inputs": {
                    "opposition_rotation": ["消费", "白酒"],
                    "old_mainline": "科技",
                    "old_mainline_fatigue": True,
                }
            },
        )

        rendered = "\n".join(render_market_structure_section(judgement))

        self.assertIn("### 3. 市场结构判断", rendered)
        self.assertIn("指数与体感", rendered)
        self.assertIn("成交结构", rendered)
        self.assertIn("轮动性质", rendered)
        self.assertIn("明日节奏", rendered)

    def test_builds_knowledge_update_only_when_reusable_rule_exists(self):
        judgement = build_market_structure_judgement(
            data={
                "indices": {"创业板指": {"涨跌幅": 1.2}},
                "total_turnover": 32600.0,
                "market_stats": {"up_count": 947, "down_count": 4300},
            },
            market_research_snapshot={
                "market_structure_inputs": {
                    "opposition_rotation": ["消费", "白酒"],
                    "old_mainline": "科技",
                    "old_mainline_fatigue": True,
                }
            },
        )

        update = build_market_structure_knowledge_update(judgement)

        self.assertEqual(update["topic"], "市场结构判断")
        self.assertIn("指数新高不等于真实赚钱效应改善", update["new_insight"])
        self.assertIn("上涨家数偏弱", update["fact_basis"])
        self.assertIn("wiki/板块补充/板块中枢与主线延续.md", update["suggested_nodes"])
        self.assertIn("明日节奏", update["next_effect"])

    def test_no_section_when_inputs_are_empty(self):
        judgement = build_market_structure_judgement(data={}, market_research_snapshot={})

        self.assertEqual(judgement["summary_text"], "")
        self.assertEqual(render_market_structure_section(judgement), [])
        self.assertEqual(build_market_structure_knowledge_update(judgement), {})


if __name__ == "__main__":
    unittest.main()
