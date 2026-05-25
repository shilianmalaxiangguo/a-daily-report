import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.calendar_section_nodes import render_calendar_section


class CalendarSectionNodeRuntimeTest(unittest.TestCase):
    def test_render_calendar_section_can_render_only_enabled_nodes(self):
        lines = render_calendar_section(
            {
                "enabled_node_keys": ["header", "top_directions", "footer"],
                "top_directions": [("军工", 3), ("机器人", 2)],
                "calendar_analysis": [
                    {
                        "date": "2026-04-24",
                        "title": "军工大会",
                        "star": "⭐⭐⭐",
                        "ai_analysis": {"main_direction": "军工", "expectation": "利好"},
                    }
                ],
                "unique_sectors": ["军工", "机器人"],
                "bullish_events": [],
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("## 二、预期日历（AI智能分析板块）", rendered)
        self.assertIn("### 近期产业链热点分布", rendered)
        self.assertIn("| 军工 | 3个事件 |", rendered)
        self.assertNotIn("### 重点事件明细", rendered)
        self.assertNotIn("### AI板块关联分析", rendered)

    def test_event_table_uses_observation_wording_for_bullish_events(self):
        lines = render_calendar_section(
            {
                "enabled_node_keys": ["event_table"],
                "calendar_analysis": [
                    {
                        "date": "2026-05-22",
                        "title": "产业链供需改善",
                        "star": "⭐⭐",
                        "ai_analysis": {"main_direction": "半导体", "expectation": "利好"},
                    }
                ],
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("| 2026-05-22 | 产业链供需改善 | ⭐⭐ | 半导体 | 📈利好 | 事件观察 |", rendered)
        self.assertNotIn("关注埋伏", rendered)


if __name__ == "__main__":
    unittest.main()
