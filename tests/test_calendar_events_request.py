import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from domains.calendar_events.request import collect_calendar_events_request_bundle
from report.calendar_section_nodes import render_calendar_section
from report.markdown_report_html import render_markdown_report_html


class _TimerStub:
    def __init__(self):
        self.records = []

    def record(self, label, order):
        self.records.append((label, order))
        return 0.1, 0.2


class CalendarEventsRequestTest(unittest.TestCase):
    def test_collect_calendar_events_request_bundle_builds_calendar_payload(self):
        timer = _TimerStub()
        emitted = []
        calls = []

        def _fetch_calendar_events(target_date=None):
            calls.append(target_date)
            if target_date is None:
                return []
            return [{"title": "军工大会", "date": target_date}]

        result = collect_calendar_events_request_bundle(
            "2026-04-22",
            fetch_calendar_events=_fetch_calendar_events,
            timer=timer,
            emit=emitted.append,
        )

        self.assertEqual(calls, [None, "2026-04-22"])
        self.assertEqual(result["results"]["calendar_events"][0]["date"], "2026-04-22")
        self.assertEqual(result["results"]["calendar_events"][0]["query_date"], "2026-04-22")
        self.assertEqual(result["results"]["calendar_events"][0]["source_date"], "2026-04-22")
        self.assertEqual(result["results"]["calendar_events"][0]["calendar_scope"], "target_date")
        self.assertTrue(result["data_status"]["预期日历"])
        self.assertTrue(result["step_status"]["预期日历获取"])
        self.assertEqual(timer.records[0], ("预期日历获取", 10))
        self.assertTrue(any("预期日历" in line for line in emitted))

    def test_collect_calendar_events_request_bundle_prefers_unfiltered_provider_window(self):
        timer = _TimerStub()
        emitted = []
        calls = []

        def _fetch_calendar_events(**kwargs):
            calls.append(kwargs)
            return [{"title": "政策发布"}]

        result = collect_calendar_events_request_bundle(
            "2026-05-18",
            fetch_calendar_events=_fetch_calendar_events,
            timer=timer,
            emit=emitted.append,
        )

        self.assertEqual(calls, [{}])
        self.assertTrue(result["data_status"]["预期日历"])
        self.assertTrue(result["step_status"]["预期日历获取"])
        self.assertEqual(result["results"]["calendar_events"][0]["title"], "政策发布")
        self.assertEqual(result["results"]["calendar_events"][0]["query_date"], "2026-05-18")
        self.assertEqual(result["results"]["calendar_events"][0]["calendar_scope"], "upcoming_window")

    def test_collect_calendar_events_request_bundle_supports_target_date_only_provider(self):
        calls = []

        def _fetch_calendar_events(target_date):
            calls.append(target_date)
            return [{"title": "目标日事件", "date": target_date}]

        result = collect_calendar_events_request_bundle(
            "2026-05-19",
            fetch_calendar_events=_fetch_calendar_events,
            timer=_TimerStub(),
            emit=lambda message: None,
        )

        self.assertEqual(calls, ["2026-05-19"])
        event = result["results"]["calendar_events"][0]
        self.assertEqual(event["date"], "2026-05-19")
        self.assertEqual(event["calendar_scope"], "target_date")

    def test_collect_calendar_events_request_bundle_does_not_hide_provider_type_error(self):
        calls = []

        def _fetch_calendar_events(target_date=None):
            calls.append(target_date)
            if target_date is None:
                raise TypeError("target_date parser failed inside provider")
            return [{"title": "目标日事件", "date": target_date}]

        result = collect_calendar_events_request_bundle(
            "2026-05-20",
            fetch_calendar_events=_fetch_calendar_events,
            timer=_TimerStub(),
            emit=lambda message: None,
        )

        self.assertEqual(calls, [None])
        self.assertFalse(result["data_status"]["预期日历"])
        self.assertEqual(result["module_logs"][0]["status"], "error")
        self.assertIn("parser failed inside provider", result["module_logs"][0]["details"]["error"])

    def test_collect_calendar_events_request_bundle_keeps_every_day_from_provider_window(self):
        timer = _TimerStub()
        emitted = []
        calls = []

        def _fetch_calendar_events(target_date=None):
            calls.append(target_date)
            if target_date:
                return [{"title": "目标日事件", "date": target_date}]
            return [
                {"title": "机器人大会", "date": "2026-06-26"},
                {"title": "云数据库发布", "date": "2026-06-27"},
            ]

        result = collect_calendar_events_request_bundle(
            "2026-06-26",
            fetch_calendar_events=_fetch_calendar_events,
            timer=timer,
            emit=emitted.append,
        )

        self.assertEqual(calls, [None])
        self.assertTrue(result["data_status"]["预期日历"])
        self.assertTrue(result["step_status"]["预期日历获取"])
        events = result["results"]["calendar_events"]
        self.assertEqual([event["date"] for event in events], ["2026-06-26", "2026-06-27"])
        self.assertTrue(all(event["query_date"] == "2026-06-26" for event in events))
        self.assertEqual([event["source_date"] for event in events], ["2026-06-26", "2026-06-27"])
        self.assertTrue(all(event["calendar_scope"] == "upcoming_window" for event in events))
        self.assertEqual(
            result["module_logs"][0]["details"]["calendar_scope"],
            "upcoming_window",
        )
        self.assertEqual(
            result["module_logs"][0]["details"]["source_dates"],
            ["2026-06-26", "2026-06-27"],
        )
        calendar_analysis = [
            {
                "date": event["date"],
                "title": event["title"],
                "star": "⭐⭐⭐",
                "ai_analysis": {"main_direction": "待确认", "expectation": "中性"},
            }
            for event in events
        ]
        markdown = "\n".join(
            render_calendar_section(
                {
                    "enabled_node_keys": ["event_table"],
                    "calendar_events_present": True,
                    "calendar_analysis": calendar_analysis,
                }
            )
        )
        bear_html = render_markdown_report_html(markdown, trade_date="2026-06-26")

        self.assertIn("2026-06-27", markdown)
        self.assertIn("2026-06-27", bear_html)


if __name__ == "__main__":
    unittest.main()
