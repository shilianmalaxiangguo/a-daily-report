import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from domains.calendar_events.infer import analyze_event_sector, minimal_fallback_analysis


class CalendarEventsInferTest(unittest.TestCase):
    def test_minimal_fallback_analysis_recognizes_robot_theme(self):
        result = minimal_fallback_analysis("具身智能机器人大会开幕")
        self.assertEqual(result["main_direction"], "人形机器人")
        self.assertIn("减速器", result["related_sectors"])

    def test_analyze_event_sector_prefers_hot_rank_concepts_before_keyword_fallback(self):
        sector = analyze_event_sector(
            "华为折叠屏新品发布",
            hot_rank_data=[
                {"concepts": ["折叠屏", "消费电子"]},
                {"concepts": ["算力"]},
            ],
        )
        self.assertEqual(sector, "折叠屏")


if __name__ == "__main__":
    unittest.main()
