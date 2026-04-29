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
        "kline_count": 4,
        "candidate_status": "confirmed_platform",
    }
    candidate.update(overrides)
    return candidate


def _overlapping_60m_structures():
    return [
        {"start_time": "2026-01-05 10:30:00", "end_time": "2026-01-08 14:00:00", "zg": 10, "zd": 4},
        {"start_time": "2026-01-09 10:30:00", "end_time": "2026-01-15 14:00:00", "zg": 9, "zd": 3},
        {"start_time": "2026-01-16 10:30:00", "end_time": "2026-01-23 14:00:00", "zg": 8, "zd": 2},
    ]


def _pandas_bool(value):
    return pd.Series([value], dtype="bool").iloc[0]


def _confirmed_daily_rows():
    return _daily_rows(start="2026-01-05", periods=20, high=4190.87, low=3983.58, close=4080)


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

    def test_build_daily_structure_candidates_detects_platform_without_20_day_gate(self):
        rows = [
            {"date": "2026-04-14", "open": 100, "high": 102, "low": 98, "close": 100},
            {"date": "2026-04-15", "open": 100, "high": 112, "low": 99, "close": 110},
            {"date": "2026-04-16", "open": 110, "high": 111, "low": 100, "close": 101},
            {"date": "2026-04-17", "open": 101, "high": 110, "low": 100, "close": 109},
        ]

        result = runtime.build_daily_structure_candidates(rows, target_date="2026-04-27", min_daily_klines=20)

        self.assertTrue(result["success"])
        current = result["current_candidate"]
        self.assertEqual(current["start_date"], "2026-04-14")
        self.assertEqual(current["end_date"], "2026-04-17")
        self.assertEqual(current["kline_count"], 4)
        self.assertEqual(current["candidate_status"], "confirmed_platform")
        self.assertNotIn("required_kline_count", current)
        self.assertEqual(current["zd_candidate"], 100.0)
        self.assertEqual(current["zg_candidate"], 111.0)
        self.assertEqual(current["platform_core_unit_count"], 3)

    def test_build_platform_sequence_keeps_only_one_connector_between_platforms(self):
        units = [
            {"start_date": "2026-01-01", "end_date": "2026-01-02", "high": 110, "low": 100, "direction": "up"},
            {"start_date": "2026-01-02", "end_date": "2026-01-03", "high": 108, "low": 98, "direction": "down"},
            {"start_date": "2026-01-03", "end_date": "2026-01-04", "high": 109, "low": 101, "direction": "up"},
            {"start_date": "2026-01-04", "end_date": "2026-01-05", "high": 125, "low": 112, "direction": "up"},
            {"start_date": "2026-01-05", "end_date": "2026-01-06", "high": 145, "low": 140, "direction": "up"},
            {"start_date": "2026-01-06", "end_date": "2026-01-07", "high": 136, "low": 128, "direction": "down"},
            {"start_date": "2026-01-07", "end_date": "2026-01-08", "high": 138, "low": 130, "direction": "up"},
            {"start_date": "2026-01-08", "end_date": "2026-01-09", "high": 137, "low": 129, "direction": "down"},
        ]

        segments, platforms = runtime.build_platform_sequence_from_trend_types(units, level="daily")

        self.assertEqual([item["segment_type"] for item in segments], ["zhongshu", "connector", "zhongshu"])
        self.assertEqual(len(platforms), 2)
        connector = segments[1]
        self.assertEqual(connector["start_date"], "2026-01-04")
        self.assertEqual(connector["end_date"], "2026-01-06")
        self.assertEqual(connector["trend_type_count"], 2)

    def test_build_platform_sequence_inserts_bridge_when_platforms_touch(self):
        units = [
            {"start_date": "2026-01-01", "end_date": "2026-01-02", "high": 110, "low": 100, "direction": "up"},
            {"start_date": "2026-01-02", "end_date": "2026-01-03", "high": 108, "low": 98, "direction": "down"},
            {"start_date": "2026-01-03", "end_date": "2026-01-04", "high": 109, "low": 101, "direction": "up"},
            {"start_date": "2026-01-04", "end_date": "2026-01-05", "high": 125, "low": 112, "direction": "up"},
            {"start_date": "2026-01-05", "end_date": "2026-01-06", "high": 124, "low": 113, "direction": "down"},
            {"start_date": "2026-01-06", "end_date": "2026-01-07", "high": 123, "low": 114, "direction": "up"},
        ]

        segments, platforms = runtime.build_platform_sequence_from_trend_types(units, level="daily")

        self.assertEqual([item["segment_type"] for item in segments], ["zhongshu", "connector", "zhongshu"])
        self.assertEqual(len(platforms), 2)
        self.assertEqual(segments[1]["connector_role"], "between")
        self.assertEqual(segments[1]["trend_type_count"], 1)

    def test_build_daily_structure_candidates_returns_not_yet_platform_without_three_overlapping_moves(self):
        rows = [
            {"date": "2026-04-14", "open": 100, "high": 101, "low": 100, "close": 100},
            {"date": "2026-04-15", "open": 100, "high": 110, "low": 109, "close": 110},
            {"date": "2026-04-16", "open": 110, "high": 51, "low": 50, "close": 50},
            {"date": "2026-04-17", "open": 50, "high": 60, "low": 59, "close": 60},
        ]

        result = runtime.build_daily_structure_candidates(rows, target_date="2026-04-27", min_daily_klines=20)

        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "not_yet_platform")
        self.assertEqual(result["daily_structure_candidates"], [])
        self.assertIsNone(result["current_candidate"])

    def test_build_daily_structure_candidates_uses_completed_history_before_target_day(self):
        rows = [
            {"date": "2026-04-14", "open": 100, "high": 102, "low": 98, "close": 100},
            {"date": "2026-04-15", "open": 100, "high": 112, "low": 99, "close": 110},
            {"date": "2026-04-16", "open": 110, "high": 111, "low": 100, "close": 101},
            {"date": "2026-04-17", "open": 101, "high": 110, "low": 100, "close": 109},
            {"date": "2026-04-28", "open": 109, "high": 160, "low": 150, "close": 155},
        ]

        result = runtime.build_daily_structure_candidates(rows, target_date="2026-04-28", min_daily_klines=20)

        current = result["current_candidate"]
        self.assertEqual(current["end_date"], "2026-04-17")
        self.assertEqual(current["kline_count"], 4)

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

    def test_confirm_daily_level_zhongshu_does_not_require_daily_duration(self):
        candidate = {
            "start_date": "2026-04-14",
            "end_date": "2026-04-17",
            "kline_count": 4,
            "candidate_status": "confirmed_platform",
            "zd_candidate": 100,
            "zg_candidate": 110,
        }
        structures = [
            {"start_time": "2026-04-14 10:30:00", "end_time": "2026-04-16 14:00:00", "zg": 4100, "zd": 4000},
            {"start_time": "2026-04-17 10:30:00", "end_time": "2026-04-21 14:00:00", "zg": 4090, "zd": 4010},
            {"start_time": "2026-04-22 10:30:00", "end_time": "2026-04-24 14:00:00", "zg": 4080, "zd": 4020},
        ]

        result = runtime.confirm_daily_level_zhongshu(candidate, structures)

        self.assertEqual(result["confirmation_status"], "confirmed_daily_level_zhongshu")
        self.assertTrue(result["confirmed"])
        self.assertNotIn("/20", result["explanation"])

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

    def test_confirm_daily_level_zhongshu_rejects_pandas_boolean_60m_numeric_fields(self):
        structures = [
            {"zg": _pandas_bool(True), "zd": _pandas_bool(False)},
            {"zg": _pandas_bool(True), "zd": _pandas_bool(False)},
            {"zg": _pandas_bool(True), "zd": _pandas_bool(False)},
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

        self.assertEqual(result["confirmation_status"], "confirmed_daily_level_zhongshu")
        self.assertTrue(result["confirmed"])
        self.assertNotIn("/20", result["explanation"])

    def test_confirm_daily_level_zhongshu_ignores_legacy_non_numeric_candidate_count(self):
        candidate = _confirmed_daily_candidate(kline_count="abc", required_kline_count="abc")

        result = runtime.confirm_daily_level_zhongshu(candidate, _overlapping_60m_structures())

        self.assertEqual(result["confirmation_status"], "confirmed_daily_level_zhongshu")
        self.assertTrue(result["confirmed"])
        self.assertNotIn("/20", result["explanation"])

    def test_confirm_daily_level_zhongshu_ignores_legacy_boolean_candidate_counts(self):
        candidate = _confirmed_daily_candidate(kline_count=True, required_kline_count=False)

        result = runtime.confirm_daily_level_zhongshu(candidate, _overlapping_60m_structures())

        self.assertEqual(result["confirmation_status"], "confirmed_daily_level_zhongshu")
        self.assertTrue(result["confirmed"])
        self.assertNotIn("/20", result["explanation"])

    def test_confirm_daily_level_zhongshu_ignores_legacy_pandas_boolean_candidate_counts(self):
        candidate = _confirmed_daily_candidate(
            kline_count=_pandas_bool(True),
            required_kline_count=_pandas_bool(True),
        )

        result = runtime.confirm_daily_level_zhongshu(candidate, _overlapping_60m_structures())

        self.assertEqual(result["confirmation_status"], "confirmed_daily_level_zhongshu")
        self.assertTrue(result["confirmed"])
        self.assertNotIn("/20", result["explanation"])

    def test_confirm_daily_level_zhongshu_degrades_non_iterable_60m_payload(self):
        result = runtime.confirm_daily_level_zhongshu(_confirmed_daily_candidate(), 123)

        self.assertEqual(result["confirmation_status"], "insufficient_60m_history")
        self.assertFalse(result["confirmed"])
        self.assertEqual(result["trend_type_count"], 0)

    def test_public_facade_uses_practical_daily_mode_by_default(self):
        calls = []

        def fetch_minute_bars(**kwargs):
            calls.append(kwargs)
            raise AssertionError("default facade must not fetch minute bars")

        result = runtime.analyze_chanlun_zhongshu(
            daily_rows=_confirmed_daily_rows(),
            target_date="2026-02-03",
            fetch_minute_bars=fetch_minute_bars,
        )

        self.assertEqual(calls, [])
        self.assertTrue(result["success"])
        self.assertEqual(result["mode"], "practical_daily_mode")
        self.assertEqual(result["chanlun_confirmation"]["confirmation_status"], "not_requested")

    def test_analyze_chanlun_zhongshu_returns_daily_candidate_and_confirmation(self):
        daily_rows = [
            {"date": "2026-04-14", "open": 100, "high": 102, "low": 98, "close": 100},
            {"date": "2026-04-15", "open": 100, "high": 112, "low": 99, "close": 110},
            {"date": "2026-04-16", "open": 110, "high": 111, "low": 100, "close": 101},
            {"date": "2026-04-17", "open": 101, "high": 110, "low": 100, "close": 109},
        ]
        minute_payload = {
            "success": True,
            "bars": [
                {"datetime": "2026-04-14 10:30:00", "date": "2026-04-14", "high": 4100, "low": 4000, "close": 4050},
                {"datetime": "2026-04-14 14:00:00", "date": "2026-04-14", "high": 4090, "low": 4010, "close": 4040},
                {"datetime": "2026-04-15 10:30:00", "date": "2026-04-15", "high": 4080, "low": 4020, "close": 4050},
                {"datetime": "2026-04-15 14:00:00", "date": "2026-04-15", "high": 4095, "low": 4015, "close": 4035},
            ],
        }

        result = runtime.analyze_chanlun_zhongshu(
            daily_rows=daily_rows,
            target_date="2026-04-27",
            fetch_minute_bars=lambda **kwargs: minute_payload,
            use_hybrid_confirmation=True,
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["mode"], "hybrid_confirmation_mode")
        self.assertEqual(result["current_candidate"]["candidate_status"], "confirmed_platform")
        self.assertEqual(result["chanlun_confirmation"]["confirmation_status"], "confirmed_daily_level_zhongshu")
        self.assertEqual(result["current_candidate"]["kline_count"], 3)

    def test_analyze_chanlun_zhongshu_degrades_when_minute_fetch_raises(self):
        def fetch_minute_bars(**kwargs):
            raise RuntimeError("network down")

        result = runtime.analyze_chanlun_zhongshu(
            daily_rows=_confirmed_daily_rows(),
            target_date="2026-02-03",
            fetch_minute_bars=fetch_minute_bars,
            use_hybrid_confirmation=True,
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["chanlun_60m_structures"], [])
        self.assertFalse(result["chanlun_confirmation"]["confirmed"])
        self.assertEqual(result["chanlun_confirmation"]["confirmation_status"], "data_insufficient")
        self.assertEqual(result["minute_source_status"], "minute_fetch_failed")
        self.assertIn("network down", result["minute_source_error"])

    def test_analyze_chanlun_zhongshu_rejects_missing_minute_lows(self):
        minute_payload = {
            "success": True,
            "bars": [
                {"datetime": "2026-01-05 10:30:00", "high": 4100},
                {"datetime": "2026-01-09 14:00:00", "high": 4090},
                {"datetime": "2026-01-16 14:00:00", "high": 4080},
            ],
        }

        result = runtime.analyze_chanlun_zhongshu(
            daily_rows=_confirmed_daily_rows(),
            target_date="2026-02-03",
            fetch_minute_bars=lambda **kwargs: minute_payload,
            use_hybrid_confirmation=True,
        )

        self.assertEqual(result["chanlun_60m_structures"], [])
        self.assertFalse(result["chanlun_confirmation"]["confirmed"])
        self.assertEqual(result["chanlun_confirmation"]["confirmation_status"], "data_insufficient")

    def test_analyze_chanlun_zhongshu_rejects_boolean_minute_bounds(self):
        minute_payload = {
            "success": True,
            "bars": [
                {"datetime": "2026-01-05 10:30:00", "high": True, "low": False},
                {"datetime": "2026-01-09 14:00:00", "high": True, "low": False},
                {"datetime": "2026-01-16 14:00:00", "high": True, "low": False},
            ],
        }

        result = runtime.analyze_chanlun_zhongshu(
            daily_rows=_confirmed_daily_rows(),
            target_date="2026-02-03",
            fetch_minute_bars=lambda **kwargs: minute_payload,
            use_hybrid_confirmation=True,
        )

        self.assertEqual(result["chanlun_60m_structures"], [])
        self.assertFalse(result["chanlun_confirmation"]["confirmed"])
        self.assertEqual(result["chanlun_confirmation"]["confirmation_status"], "data_insufficient")

    def test_analyze_chanlun_zhongshu_degrades_non_mapping_minute_bars(self):
        minute_payload = {
            "success": True,
            "bars": [
                {"datetime": "2026-01-05 10:30:00", "high": 4100, "low": 4000},
                "bad bar",
                {"datetime": "2026-01-16 14:00:00", "high": 4080, "low": 4020},
            ],
        }

        result = runtime.analyze_chanlun_zhongshu(
            daily_rows=_confirmed_daily_rows(),
            target_date="2026-02-03",
            fetch_minute_bars=lambda **kwargs: minute_payload,
            use_hybrid_confirmation=True,
        )

        self.assertEqual(result["chanlun_60m_structures"], [])
        self.assertFalse(result["chanlun_confirmation"]["confirmed"])
        self.assertEqual(result["chanlun_confirmation"]["confirmation_status"], "data_insufficient")

    def test_analyze_chanlun_zhongshu_degrades_non_iterable_minute_bars(self):
        result = runtime.analyze_chanlun_zhongshu(
            daily_rows=_confirmed_daily_rows(),
            target_date="2026-02-03",
            fetch_minute_bars=lambda **kwargs: {"success": True, "bars": 123},
            use_hybrid_confirmation=True,
        )

        self.assertEqual(result["chanlun_60m_structures"], [])
        self.assertFalse(result["chanlun_confirmation"]["confirmed"])
        self.assertEqual(result["chanlun_confirmation"]["confirmation_status"], "data_insufficient")

    def test_analyze_chanlun_zhongshu_degrades_non_dict_minute_fetch_result(self):
        result = runtime.analyze_chanlun_zhongshu(
            daily_rows=_confirmed_daily_rows(),
            target_date="2026-02-03",
            fetch_minute_bars=lambda **kwargs: ["bad payload"],
            use_hybrid_confirmation=True,
        )

        self.assertEqual(result["chanlun_60m_structures"], [])
        self.assertFalse(result["chanlun_confirmation"]["confirmed"])
        self.assertEqual(result["chanlun_confirmation"]["confirmation_status"], "data_insufficient")
        self.assertEqual(result["minute_source_status"], "invalid_minute_payload")


if __name__ == "__main__":
    unittest.main()
