import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from domains.calendar_events.request import collect_calendar_events_request_bundle


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

        result = collect_calendar_events_request_bundle(
            "2026-04-22",
            fetch_calendar_events=lambda target_date=None: [{"title": "军工大会", "date": target_date}],
            timer=timer,
            emit=emitted.append,
        )

        self.assertEqual(result["results"]["calendar_events"][0]["date"], "2026-04-22")
        self.assertTrue(result["data_status"]["预期日历"])
        self.assertTrue(result["step_status"]["预期日历获取"])
        self.assertEqual(timer.records[0], ("预期日历获取", 10))
        self.assertTrue(any("预期日历" in line for line in emitted))


if __name__ == "__main__":
    unittest.main()
