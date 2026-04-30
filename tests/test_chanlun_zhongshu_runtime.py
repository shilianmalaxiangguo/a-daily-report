import sys
import unittest
import json
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
        self.assertEqual(segments[1]["trend_type_count"], 0)
        self.assertTrue(segments[1]["synthetic_bridge"])
        bridge_trend_ids = set(segments[1]["trend_type_ids"])
        left_trend_ids = set(segments[0]["trend_type_ids"])
        right_trend_ids = set(segments[2]["trend_type_ids"])
        self.assertFalse(bridge_trend_ids & left_trend_ids)
        self.assertFalse(bridge_trend_ids & right_trend_ids)

    def test_aggregate_daily_macro_platforms_keeps_displaced_current_platform(self):
        raw_segments = [
            {
                "segment_type": "zhongshu",
                "start_date": "2026-03-18",
                "end_date": "2026-04-09",
                "kline_count": 16,
                "trend_type_count": 9,
                "zg": 3933.061,
                "zd": 3880.572,
                "high": 4065.373,
                "low": 3794.684,
                "segment_high": 4065.373,
                "segment_low": 3794.684,
                "start_close": 3860,
                "end_close": 4048,
            },
            {
                "segment_type": "connector",
                "start_date": "2026-04-09",
                "end_date": "2026-04-16",
                "kline_count": 6,
                "trend_type_count": 1,
                "high": 4057.831,
                "low": 3955.245,
                "segment_high": 4057.831,
                "segment_low": 3955.245,
                "start_close": 4048,
                "end_close": 4020,
                "connector_role": "between",
            },
            {
                "segment_type": "zhongshu",
                "start_date": "2026-04-09",
                "end_date": "2026-04-22",
                "kline_count": 10,
                "trend_type_count": 3,
                "zg": 4057.831,
                "zd": 4038.428,
                "high": 4106.844,
                "low": 3955.245,
                "segment_high": 4106.844,
                "segment_low": 3955.245,
                "start_close": 4048,
                "end_close": 4088,
            },
            {
                "segment_type": "connector",
                "start_date": "2026-04-22",
                "end_date": "2026-04-24",
                "kline_count": 3,
                "trend_type_count": 1,
                "high": 4114.844,
                "low": 4061.145,
                "segment_high": 4114.844,
                "segment_low": 4061.145,
                "start_close": 4088,
                "end_close": 4090,
                "connector_role": "between",
            },
            {
                "segment_type": "zhongshu",
                "start_date": "2026-04-22",
                "end_date": "2026-04-28",
                "kline_count": 5,
                "trend_type_count": 3,
                "zg": 4092.83,
                "zd": 4062.872,
                "high": 4114.844,
                "low": 4061.145,
                "segment_high": 4114.844,
                "segment_low": 4061.145,
                "start_close": 4088,
                "end_close": 4102,
            },
        ]

        segments, platforms = runtime.aggregate_daily_macro_platforms(raw_segments, level="daily")

        self.assertEqual(
            [item["segment_type"] for item in segments],
            ["zhongshu", "connector", "zhongshu", "connector", "zhongshu"],
        )
        self.assertFalse(
            any(
                left["segment_type"] == right["segment_type"] == "connector"
                for left, right in zip(segments, segments[1:])
            )
        )
        self.assertEqual(len(platforms), 3)
        current = platforms[-1]
        self.assertEqual(current["start_date"], "2026-04-22")
        self.assertEqual(current["end_date"], "2026-04-28")
        self.assertEqual(current["kline_count"], 5)
        self.assertEqual(current["high"], 4114.844)
        self.assertEqual(current["low"], 4061.145)
        self.assertEqual(current["visual_high"], current["high"])
        self.assertEqual(current["visual_low"], current["low"])
        self.assertEqual(current["rule_tier"], "original_rule")

    def test_aggregate_daily_macro_platforms_keeps_displaced_platforms_separate(self):
        dates = [f"2026-01-{day:02d}" for day in range(1, 11)]
        raw_segments = [
            {
                "segment_type": "zhongshu",
                "start_date": "2026-01-01",
                "end_date": "2026-01-05",
                "kline_count": 5,
                "trend_type_count": 3,
                "zg": 110,
                "zd": 100,
                "high": 115,
                "low": 96,
                "trend_type_ids": ["a", "b", "c"],
            },
            {
                "segment_type": "connector",
                "start_date": "2026-01-06",
                "end_date": "2026-01-06",
                "kline_count": 1,
                "trend_type_count": 0,
                "high": 118,
                "low": 92,
                "trend_type_ids": [],
            },
            {
                "segment_type": "zhongshu",
                "start_date": "2026-01-07",
                "end_date": "2026-01-10",
                "kline_count": 4,
                "trend_type_count": 3,
                "zg": 90,
                "zd": 80,
                "high": 94,
                "low": 78,
                "trend_type_ids": ["d", "e", "f"],
            },
        ]

        segments, platforms = runtime.aggregate_daily_macro_platforms(
            raw_segments,
            level="daily",
            target_min_klines=8,
            ordered_dates=dates,
        )

        self.assertEqual([item["segment_type"] for item in segments], ["zhongshu", "connector", "zhongshu"])
        self.assertEqual(len(platforms), 2)
        self.assertEqual((platforms[0]["zg"], platforms[0]["zd"]), (110, 100))
        self.assertEqual((platforms[1]["zg"], platforms[1]["zd"]), (90, 80))
        self.assertEqual((platforms[0]["visual_high"], platforms[0]["visual_low"]), (115, 96))
        self.assertEqual((platforms[1]["visual_high"], platforms[1]["visual_low"]), (94, 78))
        self.assertEqual((segments[1]["start_date"], segments[1]["end_date"]), ("2026-01-06", "2026-01-06"))
        self.assertEqual(segments[1]["connector_role"], "between")

    def test_aggregate_daily_macro_platforms_merges_adjacent_core_overlap(self):
        raw_segments = [
            {
                "segment_type": "zhongshu",
                "start_date": "2026-01-01",
                "end_date": "2026-01-20",
                "kline_count": 14,
                "trend_type_count": 5,
                "zg": 110,
                "zd": 100,
                "high": 116,
                "low": 94,
                "trend_type_ids": ["a", "b", "c"],
            },
            {
                "segment_type": "connector",
                "start_date": "2026-01-20",
                "end_date": "2026-01-21",
                "kline_count": 2,
                "trend_type_count": 1,
                "high": 112,
                "low": 106,
                "trend_type_ids": ["bridge"],
            },
            {
                "segment_type": "zhongshu",
                "start_date": "2026-01-21",
                "end_date": "2026-02-05",
                "kline_count": 12,
                "trend_type_count": 4,
                "zg": 112,
                "zd": 105,
                "high": 118,
                "low": 101,
                "trend_type_ids": ["d", "e"],
            },
        ]

        segments, platforms = runtime.aggregate_daily_macro_platforms(
            raw_segments,
            level="daily",
            target_min_klines=10,
        )

        self.assertEqual([item["segment_type"] for item in segments], ["zhongshu"])
        self.assertEqual(len(platforms), 1)
        merged = platforms[0]
        self.assertEqual(merged["start_date"], "2026-01-01")
        self.assertEqual(merged["end_date"], "2026-02-05")
        self.assertEqual(merged["zg"], 110)
        self.assertEqual(merged["zd"], 105)
        self.assertEqual(merged["high"], 118)
        self.assertEqual(merged["low"], 94)
        self.assertEqual(merged["rule_tier"], "daily_macro_core_overlap_merged")

    def test_aggregate_daily_macro_platforms_assigns_each_date_once(self):
        dates = [f"2026-01-{day:02d}" for day in range(1, 12)]
        raw_segments = [
            {
                "segment_type": "zhongshu",
                "start_date": "2026-01-01",
                "end_date": "2026-01-05",
                "kline_count": 5,
                "trend_type_count": 3,
                "zg": 110,
                "zd": 100,
                "high": 112,
                "low": 98,
                "trend_type_ids": ["a", "b", "c"],
            },
            {
                "segment_type": "connector",
                "start_date": "2026-01-05",
                "end_date": "2026-01-05",
                "kline_count": 1,
                "trend_type_count": 0,
                "high": 109,
                "low": 107,
                "trend_type_ids": [],
            },
            {
                "segment_type": "zhongshu",
                "start_date": "2026-01-05",
                "end_date": "2026-01-10",
                "kline_count": 6,
                "trend_type_count": 3,
                "zg": 125,
                "zd": 118,
                "high": 130,
                "low": 116,
                "trend_type_ids": ["d", "e", "f"],
            },
        ]

        segments, platforms = runtime.aggregate_daily_macro_platforms(
            raw_segments,
            level="daily",
            target_min_klines=3,
            ordered_dates=dates,
        )

        self.assertEqual([item["segment_type"] for item in segments], ["zhongshu", "connector", "zhongshu", "connector"])
        self.assertEqual((segments[0]["start_date"], segments[0]["end_date"]), ("2026-01-01", "2026-01-04"))
        self.assertEqual((segments[1]["start_date"], segments[1]["end_date"]), ("2026-01-05", "2026-01-05"))
        self.assertEqual((segments[2]["start_date"], segments[2]["end_date"]), ("2026-01-06", "2026-01-10"))
        self.assertEqual((segments[3]["start_date"], segments[3]["end_date"]), ("2026-01-11", "2026-01-11"))
        self.assertEqual(segments[3]["connector_role"], "trailing")

        ownership = {date: 0 for date in dates}
        for segment in segments:
            start = dates.index(segment["start_date"])
            end = dates.index(segment["end_date"])
            for date in dates[start : end + 1]:
                ownership[date] += 1
        self.assertTrue(all(count == 1 for count in ownership.values()), ownership)
        self.assertEqual([(item["start_date"], item["end_date"]) for item in platforms], [
            ("2026-01-01", "2026-01-04"),
            ("2026-01-06", "2026-01-10"),
        ])

    def test_aggregate_daily_macro_platforms_merges_real_index_fragments_until_complete_departure(self):
        payload = json.loads((ROOT / "data/snap-ui/zhongshu-visual/2026-04-29-sh000001.json").read_text())
        rows = payload["index_klines"]["sh000001"]
        hist_rows = rows[:-1]
        trend_types = runtime.build_trend_types_from_bars(hist_rows, level="daily")
        raw_segments, _raw_platforms = runtime.build_platform_sequence_from_trend_types(trend_types, level="daily")

        segments, platforms = runtime.aggregate_daily_macro_platforms(
            raw_segments,
            level="daily",
            ordered_dates=hist_rows,
        )

        target = next(
            item
            for item in platforms
            if item["start_date"] == "2025-12-30"
        )
        self.assertEqual(target["end_date"], "2026-03-20")
        self.assertEqual(target["kline_count"], 51)
        self.assertAlmostEqual(target["visual_low"], 3947.418)
        self.assertAlmostEqual(target["visual_high"], 4197.228)
        self.assertTrue(
            any(
                item["segment_type"] == "connector"
                and item.get("connector_role") == "departure"
                and item["start_date"] == "2025-12-25"
                and item["end_date"] == "2025-12-29"
                and item.get("departure_status") == "confirmed"
                for item in segments
            )
        )
        self.assertFalse(
            any(
                item["segment_type"] == "zhongshu"
                and item["start_date"] <= "2026-03-23" <= item["end_date"]
                and item["start_date"] == "2025-12-30"
                for item in segments
            )
        )

    def test_aggregate_daily_macro_platforms_cuts_real_index_departure_before_warning(self):
        payload = json.loads((ROOT / "data/snap-ui/zhongshu-visual/2026-04-29-sh000001.json").read_text())
        rows = payload["index_klines"]["sh000001"]
        hist_rows = rows[:-1]
        trend_types = runtime.build_trend_types_from_bars(hist_rows, level="daily")
        raw_segments, _raw_platforms = runtime.build_platform_sequence_from_trend_types(trend_types, level="daily")

        segments, platforms = runtime.aggregate_daily_macro_platforms(
            raw_segments,
            level="daily",
            ordered_dates=hist_rows,
        )

        platform = next(item for item in platforms if item["start_date"] == "2026-03-23")
        self.assertEqual(platform["end_date"], "2026-04-07")
        self.assertEqual(platform["boundary_policy"], "effective_departure")
        self.assertEqual(platform["retrospective_end_date"], "2026-04-08")
        self.assertEqual(platform["departure_warning_date"], "2026-04-08")
        self.assertEqual(platform["departure_confirmed_date"], "2026-04-10")
        self.assertEqual(platform["departure_direction"], "up")

        departure_connector = next(
            item
            for item in segments
            if item.get("segment_type") == "connector"
            and item.get("connector_role") == "departure"
            and item["start_date"] == "2026-04-08"
        )
        self.assertEqual(departure_connector["end_date"], "2026-04-09")
        self.assertEqual(departure_connector["departure_status"], "confirmed")
        self.assertEqual(departure_connector["departure_direction"], "up")
        self.assertFalse(
            any(
                item.get("segment_type") == "connector" and right.get("segment_type") == "connector"
                for item, right in zip(segments, segments[1:])
            ),
            segments,
        )

    def test_effective_departure_boundary_cuts_when_confirmation_is_inside_retrospective_span(self):
        platforms = [
            {
                "segment_type": "zhongshu",
                "start_date": "2026-01-01",
                "end_date": "2026-01-06",
                "zg": 98,
                "zd": 92,
                "high": 108,
                "low": 90,
                "segment_high": 108,
                "segment_low": 90,
                "visual_high": 108,
                "visual_low": 90,
            },
            {
                "segment_type": "zhongshu",
                "start_date": "2026-01-07",
                "end_date": "2026-01-08",
                "zg": 106,
                "zd": 102,
                "high": 110,
                "low": 101,
                "segment_high": 110,
                "segment_low": 101,
                "visual_high": 110,
                "visual_low": 101,
            },
        ]
        rows = [
            {"date": "2026-01-01", "high": 100, "low": 90, "close": 95},
            {"date": "2026-01-02", "high": 100, "low": 90, "close": 95},
            {"date": "2026-01-03", "high": 100, "low": 90, "close": 95},
            {"date": "2026-01-04", "high": 100, "low": 90, "close": 95},
            {"date": "2026-01-05", "high": 105, "low": 99, "close": 104},
            {"date": "2026-01-06", "high": 108, "low": 101, "close": 107},
            {"date": "2026-01-07", "high": 110, "low": 102, "close": 108},
            {"date": "2026-01-08", "high": 109, "low": 101, "close": 106},
        ]

        adjusted = runtime.apply_effective_departure_boundaries(platforms, rows)

        self.assertEqual(adjusted[0]["end_date"], "2026-01-04")
        self.assertEqual(adjusted[0]["departure_warning_date"], "2026-01-05")
        self.assertEqual(adjusted[0]["departure_confirmed_date"], "2026-01-06")

    def test_effective_departure_boundary_ignores_stale_confirmation_beyond_lookahead(self):
        platforms = [
            {
                "segment_type": "zhongshu",
                "start_date": "2026-01-01",
                "end_date": "2026-01-06",
                "zg": 98,
                "zd": 92,
                "high": 105,
                "low": 90,
                "segment_high": 105,
                "segment_low": 90,
                "visual_high": 105,
                "visual_low": 90,
            },
            {
                "segment_type": "zhongshu",
                "start_date": "2026-01-20",
                "end_date": "2026-01-20",
                "zg": 108,
                "zd": 104,
                "high": 112,
                "low": 103,
                "segment_high": 112,
                "segment_low": 103,
                "visual_high": 112,
                "visual_low": 103,
            },
        ]
        rows = [
            {"date": "2026-01-01", "high": 100, "low": 90, "close": 95},
            {"date": "2026-01-02", "high": 100, "low": 90, "close": 95},
            {"date": "2026-01-03", "high": 100, "low": 90, "close": 95},
            {"date": "2026-01-04", "high": 100, "low": 90, "close": 95},
            {"date": "2026-01-05", "high": 100, "low": 90, "close": 95},
            {"date": "2026-01-06", "high": 105, "low": 99, "close": 104},
            {"date": "2026-01-07", "high": 104, "low": 98, "close": 103},
            {"date": "2026-01-08", "high": 104, "low": 98, "close": 103},
            {"date": "2026-01-09", "high": 104, "low": 98, "close": 103},
            {"date": "2026-01-10", "high": 104, "low": 98, "close": 103},
            {"date": "2026-01-11", "high": 104, "low": 98, "close": 103},
            {"date": "2026-01-12", "high": 104, "low": 98, "close": 103},
            {"date": "2026-01-13", "high": 110, "low": 101, "close": 109},
            {"date": "2026-01-14", "high": 108, "low": 100, "close": 107},
            {"date": "2026-01-15", "high": 108, "low": 100, "close": 107},
            {"date": "2026-01-16", "high": 108, "low": 100, "close": 107},
            {"date": "2026-01-17", "high": 108, "low": 100, "close": 107},
            {"date": "2026-01-18", "high": 108, "low": 100, "close": 107},
            {"date": "2026-01-19", "high": 108, "low": 100, "close": 107},
            {"date": "2026-01-20", "high": 112, "low": 103, "close": 111},
        ]

        adjusted = runtime.apply_effective_departure_boundaries(platforms, rows)

        self.assertEqual(adjusted[0]["end_date"], "2026-01-06")
        self.assertNotIn("effective_departure", adjusted[0])

    def test_effective_departure_detector_uses_envelope_not_core_for_longpan_tail(self):
        reference = {
            "segment_type": "zhongshu",
            "start_date": "2026-04-01",
            "end_date": "2026-04-20",
            "zg": 23.3,
            "zd": 21.2,
            "high": 27.68,
            "low": 20.71,
            "segment_high": 27.68,
            "segment_low": 20.71,
            "visual_high": 27.68,
            "visual_low": 20.71,
        }
        rows = [
            {"date": "2026-04-14", "high": 24.2, "low": 22.11, "close": 23.68},
            {"date": "2026-04-16", "high": 25.05, "low": 24.1, "close": 25.05},
            {"date": "2026-04-20", "high": 27.68, "low": 25.92, "close": 27.31},
            {"date": "2026-04-21", "high": 26.66, "low": 25.22, "close": 26.02},
            {"date": "2026-04-22", "high": 28.62, "low": 26.2, "close": 28.62},
            {"date": "2026-04-23", "high": 31.4, "low": 27.95, "close": 30.45},
            {"date": "2026-04-28", "high": 31.48, "low": 29.61, "close": 29.99},
        ]

        metadata = runtime.detect_effective_departure_from_envelope(reference, rows)

        self.assertEqual(metadata["departure_warning_date"], "2026-04-22")
        self.assertEqual(metadata["departure_confirmed_date"], "2026-04-23")
        self.assertEqual(metadata["departure_direction"], "up")
        self.assertEqual(metadata["departure_status"], "confirmed")

    def test_effective_departure_detector_requires_envelope_bounds_not_core_only(self):
        reference = {
            "segment_type": "zhongshu",
            "start_date": "2026-04-01",
            "end_date": "2026-04-20",
            "zg": 100,
            "zd": 90,
        }
        rows = [
            {"date": "2026-04-21", "high": 102, "low": 99, "close": 101},
            {"date": "2026-04-22", "high": 105, "low": 101, "close": 104},
        ]

        metadata = runtime.detect_effective_departure_from_envelope(reference, rows)

        self.assertIsNone(metadata)

    def test_aggregate_daily_macro_platforms_splits_real_stock_after_large_center_migration(self):
        snapshot = json.loads((ROOT / "snapshots/2026-04-29.json").read_text())
        rows = snapshot["data"]["stock_klines"]["002805"]
        hist_rows = rows[:-1]
        trend_types = runtime.build_trend_types_from_bars(hist_rows, level="daily")
        raw_segments, _raw_platforms = runtime.build_platform_sequence_from_trend_types(trend_types, level="daily")

        _segments, platforms = runtime.aggregate_daily_macro_platforms(
            raw_segments,
            level="daily",
            ordered_dates=hist_rows,
        )

        self.assertFalse(
            any(
                item["start_date"] <= "2025-11-07" and item["end_date"] >= "2026-04-14"
                for item in platforms
            ),
            platforms,
        )

    def test_aggregate_daily_macro_platforms_does_not_confirm_two_day_real_stock_platform(self):
        snapshot = json.loads((ROOT / "snapshots/2026-04-29.json").read_text())
        rows = snapshot["data"]["stock_klines"]["002354"]
        hist_rows = rows[:-1]
        trend_types = runtime.build_trend_types_from_bars(hist_rows, level="daily")
        raw_segments, _raw_platforms = runtime.build_platform_sequence_from_trend_types(trend_types, level="daily")

        segments, platforms = runtime.aggregate_daily_macro_platforms(
            raw_segments,
            level="daily",
            ordered_dates=hist_rows,
        )

        self.assertTrue(platforms)
        self.assertFalse(
            any(item.get("segment_type") == "zhongshu" and item.get("kline_count") < 3 for item in segments),
            segments,
        )

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
