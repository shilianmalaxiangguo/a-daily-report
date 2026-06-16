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

    def test_reads_market_structure_inputs_from_data(self):
        judgement = build_market_structure_judgement(
            data={
                "market_structure_inputs": {
                    "index_change_pct": 1.2,
                    "up_count": 947,
                    "down_count": 4300,
                    "total_turnover": 32600.0,
                    "opposition_rotation": ["消费", "白酒"],
                    "old_mainline": "科技",
                    "old_mainline_fatigue": True,
                }
            },
            market_research_snapshot={},
        )

        self.assertEqual(judgement["tomorrow_rhythm"], "低频聚焦")
        self.assertIn("指数强但真实赚钱效应弱", judgement["index_profit_relation"])
        self.assertIn("成交额高位但结构集中", judgement["turnover_distribution"])
        self.assertIn("对立反弹", judgement["rotation_nature"])
        self.assertIn("科技仍活跃但短线疲态上升", judgement["old_mainline_fatigue"])
        self.assertTrue(any("1.20%" in item for item in judgement["fact_basis"]))
        self.assertTrue(any("上涨家数偏弱" in item for item in judgement["fact_basis"]))
        self.assertTrue(any("32600.00亿" in item for item in judgement["fact_basis"]))

    def test_uses_csi1000_as_fallback_index_when_all_share_is_missing(self):
        judgement = build_market_structure_judgement(
            data={
                "csi1000_index": {"change_pct": -2.1},
                "market_stats": {"up_count": 947, "down_count": 4300},
                "total_turnover": 32600.0,
            },
            market_research_snapshot={},
        )

        self.assertIn("同时偏弱", judgement["index_profit_relation"])
        self.assertTrue(any("-2.10%" in item for item in judgement["fact_basis"]))

    def test_uses_weaker_csi1000_when_all_share_is_milder(self):
        judgement = build_market_structure_judgement(
            data={
                "wind_a_alternative": {"change_pct": -0.3},
                "csi1000_index": {"change_pct": -2.1},
                "market_stats": {"up_count": 947, "down_count": 4300},
                "total_turnover": 32600.0,
            },
            market_research_snapshot={},
        )

        self.assertIn("同时偏弱", judgement["index_profit_relation"])
        self.assertTrue(any("-2.10%" in item for item in judgement["fact_basis"]))

    def test_ignores_empty_csi500_payload_when_choosing_weaker_index(self):
        judgement = build_market_structure_judgement(
            data={
                "csi500_index": {"price": 0, "change_pct": 0},
                "csi1000_index": {"price": 8521.23, "change_pct": -2.1},
                "market_stats": {"up_count": 947, "down_count": 4300},
                "total_turnover": 32600.0,
            },
            market_research_snapshot={},
        )

        self.assertIn("同时偏弱", judgement["index_profit_relation"])
        self.assertTrue(any("-2.10%" in item for item in judgement["fact_basis"]))
        self.assertFalse(any("+0.00%" in item for item in judgement["fact_basis"]))

    def test_no_section_when_inputs_are_empty(self):
        judgement = build_market_structure_judgement(data={}, market_research_snapshot={})

        self.assertEqual(judgement["summary_text"], "")
        self.assertEqual(render_market_structure_section(judgement), [])
        self.assertEqual(build_market_structure_knowledge_update(judgement), {})


if __name__ == "__main__":
    unittest.main()
