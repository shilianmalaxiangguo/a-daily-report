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


def _confirmed_daily_candidate(**overrides):
    candidate = {
        "start_date": "2026-01-05",
        "end_date": "2026-02-12",
        "kline_count": 29,
        "required_kline_count": 20,
        "candidate_status": "daily_cycle_confirmed_by_duration",
    }
    candidate.update(overrides)
    return candidate


def _overlapping_60m_structures():
    return [
        {"start_time": "2026-01-05 10:30:00", "end_time": "2026-01-08 14:00:00", "zg": 10, "zd": 4},
        {"start_time": "2026-01-09 10:30:00", "end_time": "2026-01-15 14:00:00", "zg": 9, "zd": 3},
        {"start_time": "2026-01-16 10:30:00", "end_time": "2026-01-23 14:00:00", "zg": 8, "zd": 2},
    ]


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

    def test_confirm_daily_level_zhongshu_requires_three_60m_trend_overlaps(self):
        candidate = {
            "start_date": "2026-01-05",
            "end_date": "2026-02-12",
            "kline_count": 29,
            "required_kline_count": 20,
            "candidate_status": "daily_cycle_confirmed_by_duration",
            "zd_candidate": 3983.58,
            "zg_candidate": 4190.87,
        }
        structures = [
            {"start_time": "2026-01-05 10:30:00", "end_time": "2026-01-08 14:00:00", "zg": 4160, "zd": 4020},
            {"start_time": "2026-01-09 10:30:00", "end_time": "2026-01-15 14:00:00", "zg": 4140, "zd": 4000},
            {"start_time": "2026-01-16 10:30:00", "end_time": "2026-01-23 14:00:00", "zg": 4120, "zd": 4010},
        ]

        result = runtime.confirm_daily_level_zhongshu(candidate, structures)

        self.assertEqual(result["confirmation_status"], "confirmed_daily_level_zhongshu")
        self.assertEqual(result["trend_type_count"], 3)
        self.assertEqual(result["zd"], 4020.0)
        self.assertEqual(result["zg"], 4120.0)

    def test_confirm_daily_level_zhongshu_keeps_9_day_candidate_forming_even_with_60m_overlap(self):
        candidate = {
            "start_date": "2026-04-14",
            "end_date": "2026-04-24",
            "kline_count": 9,
            "required_kline_count": 20,
            "candidate_status": "daily_candidate_forming",
            "zd_candidate": 3992.41,
            "zg_candidate": 4114.84,
        }
        structures = [
            {"start_time": "2026-04-14 10:30:00", "end_time": "2026-04-16 14:00:00", "zg": 4100, "zd": 4000},
            {"start_time": "2026-04-17 10:30:00", "end_time": "2026-04-21 14:00:00", "zg": 4090, "zd": 4010},
            {"start_time": "2026-04-22 10:30:00", "end_time": "2026-04-24 14:00:00", "zg": 4080, "zd": 4020},
        ]

        result = runtime.confirm_daily_level_zhongshu(candidate, structures)

        self.assertEqual(result["confirmation_status"], "forming_daily_level_zhongshu")
        self.assertFalse(result["confirmed"])
        self.assertIn("9/20", result["explanation"])

    def test_confirm_daily_level_zhongshu_reports_insufficient_60m_history(self):
        candidate = {
            "start_date": "2026-01-05",
            "end_date": "2026-02-12",
            "kline_count": 29,
            "required_kline_count": 20,
            "candidate_status": "daily_cycle_confirmed_by_duration",
        }

        result = runtime.confirm_daily_level_zhongshu(candidate, [])

        self.assertEqual(result["confirmation_status"], "insufficient_60m_history")
        self.assertFalse(result["confirmed"])

    def test_confirm_daily_level_zhongshu_rejects_missing_60m_bounds(self):
        structures = [{"zg": 10}, {"zg": 9}, {"zg": 8}]

        result = runtime.confirm_daily_level_zhongshu(_confirmed_daily_candidate(), structures)

        self.assertEqual(result["confirmation_status"], "not_confirmed")
        self.assertFalse(result["confirmed"])
        self.assertIsNone(result["zg"])
        self.assertIsNone(result["zd"])

    def test_confirm_daily_level_zhongshu_rejects_invalid_60m_numeric_fields(self):
        structures = [
            {"zg": 10, "zd": "bad"},
            {"zg": 9, "zd": 3},
            {"zg": 8, "zd": 2},
        ]

        result = runtime.confirm_daily_level_zhongshu(_confirmed_daily_candidate(), structures)

        self.assertEqual(result["confirmation_status"], "not_confirmed")
        self.assertFalse(result["confirmed"])
        self.assertIsNone(result["zg"])
        self.assertIsNone(result["zd"])

    def test_confirm_daily_level_zhongshu_rejects_boolean_60m_numeric_fields(self):
        structures = [
            {"zg": True, "zd": False},
            {"zg": True, "zd": False},
            {"zg": True, "zd": False},
        ]

        result = runtime.confirm_daily_level_zhongshu(_confirmed_daily_candidate(), structures)

        self.assertEqual(result["confirmation_status"], "not_confirmed")
        self.assertFalse(result["confirmed"])
        self.assertIsNone(result["zg"])
        self.assertIsNone(result["zd"])

    def test_confirm_daily_level_zhongshu_rejects_invalid_60m_ranges(self):
        structures = [
            {"zg": 10, "zd": 4},
            {"zg": 9, "zd": 9},
            {"zg": 8, "zd": 2},
        ]

        result = runtime.confirm_daily_level_zhongshu(_confirmed_daily_candidate(), structures)

        self.assertEqual(result["confirmation_status"], "not_confirmed")
        self.assertFalse(result["confirmed"])

    def test_confirm_daily_level_zhongshu_rejects_no_60m_overlap(self):
        structures = [
            {"zg": 10, "zd": 8},
            {"zg": 7, "zd": 5},
            {"zg": 4, "zd": 2},
        ]

        result = runtime.confirm_daily_level_zhongshu(_confirmed_daily_candidate(), structures)

        self.assertEqual(result["confirmation_status"], "not_confirmed")
        self.assertFalse(result["confirmed"])
        self.assertIsNone(result["zg"])
        self.assertIsNone(result["zd"])

    def test_confirm_daily_level_zhongshu_degrades_non_mapping_candidate(self):
        result = runtime.confirm_daily_level_zhongshu("bad", _overlapping_60m_structures())

        self.assertEqual(result["confirmation_status"], "forming_daily_level_zhongshu")
        self.assertFalse(result["confirmed"])
        self.assertIn("0/20", result["explanation"])

    def test_confirm_daily_level_zhongshu_degrades_non_numeric_candidate_count(self):
        candidate = _confirmed_daily_candidate(kline_count="abc", required_kline_count="abc")

        result = runtime.confirm_daily_level_zhongshu(candidate, _overlapping_60m_structures())

        self.assertEqual(result["confirmation_status"], "forming_daily_level_zhongshu")
        self.assertFalse(result["confirmed"])
        self.assertIn("0/20", result["explanation"])

    def test_confirm_daily_level_zhongshu_degrades_boolean_candidate_counts(self):
        candidate = _confirmed_daily_candidate(kline_count=True, required_kline_count=False)

        result = runtime.confirm_daily_level_zhongshu(candidate, _overlapping_60m_structures())

        self.assertEqual(result["confirmation_status"], "forming_daily_level_zhongshu")
        self.assertFalse(result["confirmed"])
        self.assertIn("0/20", result["explanation"])

    def test_confirm_daily_level_zhongshu_degrades_non_iterable_60m_payload(self):
        result = runtime.confirm_daily_level_zhongshu(_confirmed_daily_candidate(), 123)

        self.assertEqual(result["confirmation_status"], "insufficient_60m_history")
        self.assertFalse(result["confirmed"])
        self.assertEqual(result["trend_type_count"], 0)


if __name__ == "__main__":
    unittest.main()
