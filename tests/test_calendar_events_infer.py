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

    def test_minimal_fallback_analysis_splits_calendar_events_by_theme_not_generic_policy(self):
        samples = {
            "2026年谷歌开发者大会（Google I/O 2026）将于5月19日至20日举办": "AI应用",
            "联想：天禧AI将于5月19日发布4.0大版本，核心升级为天禧Claw": "AI终端",
            "AMD AI开发者日2026将于5月19日在上海举办": "AI算力",
            "2026世界无人机大会5月21日至23日在深圳举行": "低空经济",
            "第十届集微半导体大会定于5月27日至29日在张江举行": "半导体",
            "今日有5亿元7天期逆回购到期": "金融流动性",
            "2026年美国临床肿瘤学会年会是美国临床肿瘤学会（ASCO）将于5月29日至6月2日举办": "医药医疗",
        }

        for title, expected_direction in samples.items():
            with self.subTest(title=title):
                result = minimal_fallback_analysis(title)
                self.assertEqual(result["main_direction"], expected_direction)

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

    def test_ai_analyze_event_sectors_uses_local_rules_by_default_without_llm(self):
        class ExplodingClient:
            def analyze_event_sectors(self, event_title, event_summary=""):
                raise AssertionError("DeepSeek should not be called by default")

        result = ai_analyze_event_sectors(
            "人形机器人产业大会召开",
            helpers={
                "_default_get_llm_service": lambda: ExplodingClient(),
                "ENABLE_REMOTE_CALENDAR_LLM": False,
            },
            print_fn=lambda *args, **kwargs: None,
        )

        self.assertEqual(result["main_direction"], "人形机器人")
        self.assertIn("减速器", result["related_sectors"])

    def test_ai_analyze_event_sectors_falls_back_to_local_rules_when_remote_llm_fails(self):
        class FailingClient:
            def analyze_event_sectors(self, event_title, event_summary=""):
                raise RuntimeError("deepseek timeout")

        emitted = []
        result = ai_analyze_event_sectors(
            "人形机器人产业大会召开",
            helpers={
                "_default_get_llm_service": lambda: FailingClient(),
                "ENABLE_REMOTE_CALENDAR_LLM": True,
            },
            print_fn=emitted.append,
        )

        self.assertEqual(result["main_direction"], "人形机器人")
        self.assertIn("减速器", result["related_sectors"])
        self.assertTrue(any("远程LLM失败" in line for line in emitted))

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
