import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.calendar_section_nodes import render_calendar_section
from report import runtime as report_runtime


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

    def test_event_table_does_not_treat_low_evidence_meeting_as_run_ahead(self):
        lines = render_calendar_section(
            {
                "enabled_node_keys": ["event_table"],
                "calendar_analysis": [
                    {
                        "date": "2026-06-05",
                        "title": "某行业交流会议将于6月5日举办",
                        "star": "⭐⭐⭐",
                        "ai_analysis": {"main_direction": "待确认", "expectation": "中性"},
                    }
                ],
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("| 2026-06-05 | 某行业交流会议将于6月5日举办 | ⭐⭐⭐ | 待确认 | ➖中性 | 观望 |", rendered)
        self.assertNotIn("抢跑/兑现", rendered)

    def test_user_supplied_low_evidence_events_render_without_policy_catalyst(self):
        original_remote_flag = getattr(report_runtime, "ENABLE_REMOTE_CALENDAR_LLM", None)
        try:
            report_runtime.ENABLE_REMOTE_CALENDAR_LLM = False
            calendar_context = report_runtime._build_calendar_ai_context(
                {
                    "calendar_events": [
                        {"date": "2026-06-05", "title": "华为云创想者大会将于6月5日至6日举办", "star": 3},
                        {"date": "2026-06-05", "title": "2026第十届中关村数字金融与金融安全大会将于6月5日举办", "star": 3},
                        {"date": "2026-06-05", "title": "2026全球数字合作交流会暨全球数据周将于6月5日至7日举办", "star": 2},
                        {"date": "2026-06-06", "title": "东风汽车：OpenVAN无人物流车品牌将于6月6日全球首发", "star": 2},
                        {"date": "2026-06-09", "title": "第二十七届国际气体产业链展览交易会（IG  China 2026） 将于6月9日至11日举办", "star": 3},
                        {"date": "2026-06-25", "title": "第21届开源中国·开源世界高峰论坛", "star": 3},
                    ]
                },
                print_fn=lambda *args, **kwargs: None,
            )
            lines = render_calendar_section(
                {
                    "enabled_node_keys": ["event_table"],
                    "calendar_events_present": True,
                    "calendar_analysis": calendar_context["calendar_analysis"],
                }
            )

            rendered = "\n".join(lines)
            self.assertNotIn("政策催化", rendered)
            self.assertNotIn("抢跑/兑现", rendered)
            self.assertIn("华为云创想者大会将于6月5日至6日举办", rendered)
            self.assertIn("云计算", rendered)
            self.assertIn("汽车产业链", rendered)
            self.assertIn("软件服务", rendered)
        finally:
            if original_remote_flag is None:
                if hasattr(report_runtime, "ENABLE_REMOTE_CALENDAR_LLM"):
                    delattr(report_runtime, "ENABLE_REMOTE_CALENDAR_LLM")
            else:
                report_runtime.ENABLE_REMOTE_CALENDAR_LLM = original_remote_flag


if __name__ == "__main__":
    unittest.main()
