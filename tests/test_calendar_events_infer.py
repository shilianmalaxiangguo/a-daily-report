import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from domains.calendar_events.infer import ai_analyze_event_sectors, analyze_event_sector, minimal_fallback_analysis


class CalendarEventsInferTest(unittest.TestCase):
    def test_minimal_fallback_analysis_recognizes_robot_theme(self):
        result = minimal_fallback_analysis("具身智能机器人大会开幕")
        self.assertEqual(result["main_direction"], "人形机器人")
        self.assertIn("减速器", result["related_sectors"])

    def test_minimal_fallback_analysis_uses_concrete_bucket_instead_of_other(self):
        result = minimal_fallback_analysis("未知行业政策发布")

        self.assertEqual(result["main_direction"], "政策催化")
        self.assertNotIn("其他", result["related_sectors"])
        self.assertIn("政策催化", result["related_sectors"])

    def test_ai_analyze_event_sectors_normalizes_llm_other_to_concrete_bucket(self):
        class OtherClient:
            def analyze_event_sectors(self, event_title, event_summary=""):
                return {
                    "main_direction": "其他",
                    "related_sectors": ["其他"],
                    "trading_logic": "AI无法识别明确产业链",
                    "expectation": "中性",
                    "confidence": "低",
                }

        result = ai_analyze_event_sectors(
            "未知行业政策发布",
            helpers={"_default_get_llm_service": lambda: OtherClient()},
            print_fn=lambda *args, **kwargs: None,
        )

        self.assertEqual(result["main_direction"], "政策催化")
        self.assertNotIn("其他", result["related_sectors"])

    def test_ai_analyze_event_sectors_handles_missing_llm_service_without_other(self):
        result = ai_analyze_event_sectors(
            "某区域发展规划发布",
            helpers={"_default_get_llm_service": lambda: None},
            print_fn=lambda *args, **kwargs: None,
        )

        self.assertNotEqual(result["main_direction"], "其他")
        self.assertTrue(result["related_sectors"])

    def test_ai_analyze_event_sectors_handles_malformed_llm_result_without_other(self):
        class MalformedClient:
            def analyze_event_sectors(self, event_title, event_summary=""):
                return None

        result = ai_analyze_event_sectors(
            "未知行业政策发布",
            helpers={"_default_get_llm_service": lambda: MalformedClient()},
            print_fn=lambda *args, **kwargs: None,
        )

        self.assertEqual(result["main_direction"], "政策催化")
        self.assertTrue(result["related_sectors"])

    def test_analyze_event_sector_prefers_hot_rank_concepts_before_keyword_fallback(self):
        sector = analyze_event_sector(
            "华为折叠屏新品发布",
            hot_rank_data=[
                {"concepts": ["折叠屏", "消费电子"]},
                {"concepts": ["算力"]},
            ],
        )
        self.assertEqual(sector, "折叠屏")

    def test_analyze_event_sector_never_returns_other_for_unknown_event(self):
        sector = analyze_event_sector("完全未知事件")

        self.assertEqual(sector, "政策催化")


if __name__ == "__main__":
    unittest.main()
