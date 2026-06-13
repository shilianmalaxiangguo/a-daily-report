import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from decision.chanlun import contracts
from decision.chanlun import runtime


def _daily_rows():
    return [
        {"date": "2026-04-20", "high": 110, "low": 100, "close": 105},
        {"date": "2026-04-21", "high": 108, "low": 98, "close": 101},
        {"date": "2026-04-22", "high": 109, "low": 101, "close": 104},
        {"date": "2026-04-23", "high": 112, "low": 102, "close": 110},
    ]


class ChanlunRuntimeContractTest(unittest.TestCase):
    def test_v1_runtime_has_no_full_recursive_execution_path(self):
        result = runtime.full_recursive_mode_status()

        self.assertEqual(result["mode"], "full_recursive_mode")
        self.assertEqual(result["status"], "deferred")
        self.assertFalse(result["enabled"])

    def test_practical_daily_mode_does_not_request_minute_confirmation(self):
        calls = []

        def fetch_minute_bars(**kwargs):
            calls.append(kwargs)
            return {"bars": []}

        result = runtime.analyze_practical_daily_structure(
            daily_rows=_daily_rows(),
            fetch_minute_bars=fetch_minute_bars,
        )

        self.assertEqual(calls, [])
        self.assertTrue(result["success"])
        self.assertEqual(result["mode"], contracts.PRACTICAL_DAILY_MODE)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["child_trend_types"], [])
        self.assertEqual(result["minute_confirmation"]["confirmation_status"], "not_requested")
        self.assertFalse(result["minute_confirmation"]["confirmed"])
        self.assertIsNone(result["minute_confirmation"]["period"])

    def test_practical_daily_mode_uses_base_rows_not_only_focus_rows(self):
        base_only_platform = [
            {"date": "2026-01-01", "high": 110, "low": 100, "close": 105},
            {"date": "2026-01-02", "high": 108, "low": 98, "close": 101},
            {"date": "2026-01-03", "high": 109, "low": 101, "close": 104},
        ]
        non_overlapping_focus = []
        for offset in range(120):
            current = date(2026, 2, 1) + timedelta(days=offset)
            low = 200 + offset * 3
            non_overlapping_focus.append(
                {"date": current.isoformat(), "high": low + 1, "low": low, "close": low}
            )

        result = runtime.analyze_practical_daily_structure(
            daily_rows=base_only_platform + non_overlapping_focus,
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["daily_structure_candidates"][0]["zhongshu_id"], "daily_zhongshu_1")

    def test_hybrid_mode_requests_default_60m_and_degrades_empty_minute_payload(self):
        calls = []

        def fetch_minute_bars(**kwargs):
            calls.append(kwargs)
            return {"status": "empty_source", "bars": []}

        result = runtime.analyze_hybrid_structure(
            daily_rows=_daily_rows(),
            fetch_minute_bars=fetch_minute_bars,
        )

        self.assertEqual(calls, [{"index_code": "sh.000001", "period": "60"}])
        self.assertTrue(result["success"])
        self.assertEqual(result["mode"], contracts.HYBRID_CONFIRMATION_MODE)
        self.assertEqual(result["minute_source_status"], "empty_source")
        self.assertEqual(result["child_trend_types"], [])
        self.assertEqual(
            result["minute_confirmation"]["confirmation_status"],
            contracts.DATA_INSUFFICIENT,
        )

    def test_hybrid_mode_passes_target_date_when_provided(self):
        calls = []

        def fetch_minute_bars(**kwargs):
            calls.append(kwargs)
            return {"status": "empty_source", "bars": []}

        runtime.analyze_hybrid_structure(
            daily_rows=_daily_rows(),
            fetch_minute_bars=fetch_minute_bars,
            target_date="2026-04-23",
        )

        self.assertEqual(calls, [{"index_code": "sh.000001", "period": "60", "target_date": "2026-04-23"}])


if __name__ == "__main__":
    unittest.main()
