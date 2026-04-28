import sys
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from decision import chanlun_zhongshu_runtime as runtime


def _daily_rows(start="2026-01-01", periods=30, high=105, low=95, close=100):
    rows = []
    for idx, date in enumerate(pd.bdate_range(start=start, periods=periods)):
        rows.append(
            {
                "date": date.strftime("%Y-%m-%d"),
                "open": close,
                "high": high,
                "low": low,
                "close": close + idx * 0.1,
                "volume": 100 + idx,
                "amount": 1000 + idx,
            }
        )
    return rows


class ChanlunZhongshuRuntimeTest(unittest.TestCase):
    def test_build_daily_structure_candidates_missing_date_degrades_to_invalid_payload(self):
        result = runtime.build_daily_structure_candidates([{"high": 1, "low": 0}])

        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "invalid_daily_bars")
        self.assertEqual(result["daily_structure_candidates"], [])
        self.assertIsNone(result["current_candidate"])
        self.assertEqual(result["daily_lookback_count"], 0)
        self.assertEqual(result["report_focus_count"], 0)
        self.assertIn("date", result["error"])

    def test_build_daily_structure_candidates_missing_high_or_low_degrades_to_invalid_payload(self):
        cases = [
            ({"date": "2026-01-05", "low": 0}, "high"),
            ({"date": "2026-01-05", "high": 1}, "low"),
        ]
        for row, missing_column in cases:
            with self.subTest(missing_column=missing_column):
                result = runtime.build_daily_structure_candidates([row])

                self.assertFalse(result["success"])
                self.assertEqual(result["status"], "invalid_daily_bars")
                self.assertEqual(result["daily_structure_candidates"], [])
                self.assertIsNone(result["current_candidate"])
                self.assertEqual(result["daily_lookback_count"], 0)
                self.assertEqual(result["report_focus_count"], 0)
                self.assertIn(missing_column, result["error"])

    def test_build_daily_structure_candidates_empty_payload_includes_count_contract(self):
        result = runtime.build_daily_structure_candidates([])

        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "empty_daily_bars")
        self.assertEqual(result["daily_structure_candidates"], [])
        self.assertIsNone(result["current_candidate"])
        self.assertEqual(result["daily_lookback_count"], 0)
        self.assertEqual(result["report_focus_count"], 0)

    def test_build_daily_structure_candidates_marks_9_day_tail_as_forming_candidate(self):
        rows = _daily_rows(start="2026-04-14", periods=10, high=4114.84, low=3992.41, close=4050)

        result = runtime.build_daily_structure_candidates(rows, target_date="2026-04-27", min_daily_klines=20)

        self.assertTrue(result["success"])
        current = result["current_candidate"]
        self.assertEqual(current["start_date"], "2026-04-14")
        self.assertEqual(current["end_date"], "2026-04-24")
        self.assertEqual(current["kline_count"], 9)
        self.assertEqual(current["candidate_status"], "daily_candidate_forming")
        self.assertEqual(current["required_kline_count"], 20)
        self.assertEqual(current["zd_candidate"], 3992.41)
        self.assertEqual(current["zg_candidate"], 4114.84)

    def test_build_daily_structure_candidates_confirms_duration_only_after_20_days(self):
        rows = _daily_rows(start="2026-01-05", periods=20, high=4190.87, low=3983.58, close=4080)

        result = runtime.build_daily_structure_candidates(rows, target_date="2026-02-03", min_daily_klines=20)

        current = result["current_candidate"]
        self.assertEqual(current["kline_count"], 20)
        self.assertEqual(current["candidate_status"], "daily_cycle_confirmed_by_duration")
        self.assertEqual(current["zd_candidate"], 3983.58)
        self.assertEqual(current["zg_candidate"], 4190.87)

    def test_build_daily_structure_candidates_uses_latest_20_completed_bars_when_history_is_longer(self):
        rows = _daily_rows(start="2026-01-05", periods=25, high=4190.87, low=3983.58, close=4080)

        result = runtime.build_daily_structure_candidates(rows, target_date="2026-02-10", min_daily_klines=20)

        current = result["current_candidate"]
        self.assertEqual(current["start_date"], "2026-01-12")
        self.assertEqual(current["end_date"], "2026-02-06")
        self.assertEqual(current["kline_count"], 20)
        self.assertEqual(current["candidate_status"], "daily_cycle_confirmed_by_duration")

    def test_build_daily_structure_candidates_uses_completed_history_before_target_day(self):
        rows = _daily_rows(start="2026-04-14", periods=11, high=4114.84, low=3992.41, close=4050)

        result = runtime.build_daily_structure_candidates(rows, target_date="2026-04-28", min_daily_klines=20)

        current = result["current_candidate"]
        self.assertEqual(current["end_date"], "2026-04-27")
        self.assertEqual(current["kline_count"], 10)


if __name__ == "__main__":
    unittest.main()
