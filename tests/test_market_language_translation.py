import copy
import datetime as dt
import json
import math
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from domains.market_state.market_language_translation import (
    MARKET_LANGUAGE_SCHEMA_VERSION,
    build_market_language_source_projection,
    build_market_language_translation,
    canonical_market_language_hash,
    normalize_market_language_translation,
    validate_market_language_translation,
)


def _bar_rows_from_changes(
    changes,
    *,
    trade_date="2026-07-10",
    interval_minutes=1,
):
    timestamp = dt.datetime.fromisoformat(f"{trade_date} 09:31:00")
    price = 100.0
    rows = []
    for change in changes:
        open_price = price
        price *= 1.0 + change
        high = max(open_price, price) * 1.0002
        low = min(open_price, price) * 0.9998
        volume = 100000.0
        rows.append(
            {
                "datetime": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "open": open_price,
                "high": high,
                "low": low,
                "close": price,
                "volume": volume,
                "amount": price * volume,
            }
        )
        timestamp += dt.timedelta(minutes=interval_minutes)
    return rows


def _synthetic_one_minute_rows(trade_date="2026-07-10"):
    phases = (
        [0.0] * 16
        + [-0.0015] * 10
        + [0.0020] * 20
        + [-0.0018] * 18
        + [0.0002] * 6
    )
    return _bar_rows_from_changes(phases, trade_date=trade_date)


def _minute_input(
    rows,
    trade_date="2026-07-10",
    *,
    instrument_type="stock",
    bar_period_minutes=1,
):
    return {
        "trade_date": trade_date,
        "bar_period_minutes": bar_period_minutes,
        "instrument": {
            "type": instrument_type,
            "code": "000001.SH" if instrument_type == "index" else "600000.SH",
            "name": "上证指数" if instrument_type == "index" else "测试样本",
        },
        "source": {
            "provider": "unit_test.one_minute",
            "source_date": trade_date,
            "query_date": "2026-07-12",
            "bar_time_semantics": "interval_end",
            "amount_unit": "CNY",
            "amount_semantics": "interval",
            "volume_unit": "shares",
            "volume_semantics": "interval",
        },
        "minute_bars": rows,
    }


def _posthoc_trade_calendar():
    return {
        "provider": "unit_test.trade_calendar",
        "query_date": "2026-07-15",
        "range_start": "2026-07-10",
        "range_end": "2026-07-14",
        "open_dates": ["2026-07-10", "2026-07-13", "2026-07-14"],
    }


class MarketLanguageTranslationTest(unittest.TestCase):
    def _fixture_artifact(self, stem):
        payload = json.loads(
            (
                ROOT
                / "tests"
                / "fixtures"
                / "quant_pressure_one_minute"
                / "raw"
                / f"{stem}.json"
            ).read_text(encoding="utf-8")
        )
        projection = build_market_language_source_projection(
            payload,
            target_date=payload["trade_date"],
            analysis_mode="replay",
        )
        return build_market_language_translation(
            projection,
            target_date=payload["trade_date"],
            analysis_mode="replay",
            artifact_origin="reconstructed",
            include_posthoc=True,
        )

    def test_three_anchor_cases_keep_distinct_prefix_event_paths(self):
        giga = self._fixture_artifact("sh603986_20260710")
        jcet = self._fixture_artifact("sh600584_20260710")
        shanghai = self._fixture_artifact("sh000001_20260521")

        giga_down = [
            row for row in giga["timeline"]["events"] if row["pressure_direction"] == "downward"
        ]
        self.assertEqual(
            (
                giga_down[0]["candidate_at"][11:16],
                giga_down[0]["confirmed_at"][11:16],
                giga_down[0]["invalidated_at"][11:16],
            ),
            ("09:47", "09:49", "09:54"),
        )
        self.assertEqual(giga_down[1]["confirmed_at"][11:16], "10:02")

        jcet_down = [
            row for row in jcet["timeline"]["events"] if row["pressure_direction"] == "downward"
        ]
        self.assertEqual(
            (jcet_down[0]["candidate_at"][11:16], jcet_down[0]["confirmed_at"][11:16]),
            ("10:02", "10:04"),
        )
        self.assertEqual(jcet_down[-1]["candidate_at"][11:16], "14:30")

        first_shanghai = shanghai["timeline"]["events"][0]
        self.assertNotIn(
            "09:46",
            {row["candidate_at"][11:16] for row in shanghai["timeline"]["events"]},
        )
        self.assertEqual(first_shanghai["candidate_at"][11:16], "09:47")
        self.assertEqual(first_shanghai["pressure_direction"], "upward")
        self.assertEqual(first_shanghai["confirmed_at"][11:16], "09:49")
        self.assertEqual(shanghai["timeline"]["events"][-1]["confirmed_at"][11:16], "13:52")
        self.assertNotEqual(
            [row["candidate_at"][11:16] for row in giga["timeline"]["events"][:4]],
            [row["candidate_at"][11:16] for row in jcet["timeline"]["events"][:4]],
        )

    def test_next_window_task_bounds_attention_without_promising_notification(self):
        artifact = self._fixture_artifact("sh603986_20260710")
        task = artifact["next_window_task"]

        for text in (
            "低注意力研究目标，不替代正式执行计划",
            "T+1 09:30-09:35",
            "固定主动查看只安排在",
            "开盘按前一晚计划处理B1",
            "09:50-10:10后台复核",
            "只核对前一晚已允许的B2",
            "目前不会自动提醒",
            "未收到明确提示时B2不执行",
            "T+2 14:30-14:55",
            "不生成新决定",
            "不要求持续盯盘",
        ):
            self.assertIn(text, task)
        self.assertNotIn("09:45-09:50只做前哨观察", task)

    def test_insufficient_facts_keep_b2_inactive_without_a_clear_prompt(self):
        projection = build_market_language_source_projection(
            {},
            target_date="2026-07-10",
            analysis_mode="replay",
        )
        artifact = build_market_language_translation(
            projection,
            target_date="2026-07-10",
            analysis_mode="replay",
            artifact_origin="reconstructed",
        )

        self.assertEqual(artifact["evidence_status"], "insufficient")
        self.assertIn("补齐指数、全市场宽度与板块同步事实", artifact["next_window_task"])
        self.assertIn("目前不会自动提醒", artifact["next_window_task"])
        self.assertIn("未收到明确提示时B2不执行", artifact["next_window_task"])

    def test_weighted_index_and_market_breadth_conflict_stays_index_weighted_and_unclear(self):
        projection = build_market_language_source_projection(
            {
                "indices": {
                    "000001.SH": {
                        "name": "上证指数",
                        "change_pct": -1.1,
                        "trade_date": "2026-07-10",
                    }
                },
                "market_stats": {
                    "up_count": 3600,
                    "down_count": 900,
                    "flat_count": 100,
                    "trade_date": "2026-07-10",
                },
            },
            target_date="2026-07-10",
            analysis_mode="replay",
        )
        artifact = build_market_language_translation(
            projection,
            target_date="2026-07-10",
            analysis_mode="replay",
            artifact_origin="reconstructed",
        )

        self.assertEqual(artifact["force_scope"], "index_weighted")
        self.assertEqual(artifact["pressure_direction"], "unclear")
        self.assertTrue(
            any(row["evidence_id"] == "c-aggregation-conflict" for row in artifact["counter_evidence"])
        )

    def test_gradual_decline_is_pressure_expansion_not_false_cascade(self):
        rows = _bar_rows_from_changes([-0.0001] * 60)
        projection = build_market_language_source_projection(
            _minute_input(rows),
            target_date="2026-07-10",
            analysis_mode="replay",
        )
        artifact = build_market_language_translation(
            projection,
            target_date="2026-07-10",
            analysis_mode="replay",
            artifact_origin="reconstructed",
        )

        confirmed = [
            row
            for row in artifact["timeline"]["events"]
            if row["pressure_direction"] == "downward" and row["confirmed_at"]
        ]
        self.assertTrue(confirmed)
        self.assertEqual(artifact["pressure_direction"], "downward")
        self.assertEqual(artifact["phase"], "expansion")
        self.assertNotIn("cascade", {row["phase"] for row in confirmed})

    def test_one_bar_message_repricing_is_kept_as_transient_failed_event(self):
        rows = _bar_rows_from_changes([0.0] * 16 + [-0.03] + [0.0] * 35)
        projection = build_market_language_source_projection(
            _minute_input(rows),
            target_date="2026-07-10",
            analysis_mode="replay",
        )
        artifact = build_market_language_translation(
            projection,
            target_date="2026-07-10",
            analysis_mode="replay",
            artifact_origin="reconstructed",
        )

        downward = [
            row for row in artifact["timeline"]["events"] if row["pressure_direction"] == "downward"
        ]
        self.assertTrue(downward)
        self.assertTrue(any(row["confirmed_at"] is not None for row in downward))
        self.assertTrue(all(row["invalidated_at"] is not None for row in downward))
        self.assertTrue(
            all(row["confirmation_quality"] == "slope_persistence_only" for row in downward)
        )
        self.assertTrue(all(row["directional_follow_through_at"] is None for row in downward))
        self.assertTrue(
            any(
                row["evidence_id"].startswith("c-slope-only-confirmation-")
                for row in artifact["counter_evidence"]
            )
        )
        self.assertEqual(artifact["pressure_direction"], "balanced")
        self.assertEqual(artifact["phase"], "unclear")

    def test_single_stock_selling_pressure_does_not_become_whole_market_force(self):
        data = _minute_input(_bar_rows_from_changes([-0.001] * 55))
        data["market_stats"] = {
            "up_count": 3500,
            "down_count": 1000,
            "flat_count": 100,
            "trade_date": "2026-07-10",
        }
        projection = build_market_language_source_projection(
            data,
            target_date="2026-07-10",
            analysis_mode="replay",
        )
        artifact = build_market_language_translation(
            projection,
            target_date="2026-07-10",
            analysis_mode="replay",
            artifact_origin="reconstructed",
        )

        self.assertEqual(artifact["force_scope"], "single_stock")
        self.assertEqual(artifact["pressure_direction"], "downward")
        self.assertTrue(
            any(row["evidence_id"] == "c-aggregation-conflict" for row in artifact["counter_evidence"])
        )

    def test_fast_decline_followed_by_sustained_recovery_is_repair(self):
        rows = _bar_rows_from_changes([0.0] * 16 + [-0.002] * 10 + [0.003] * 30)
        projection = build_market_language_source_projection(
            _minute_input(rows),
            target_date="2026-07-10",
            analysis_mode="replay",
        )
        artifact = build_market_language_translation(
            projection,
            target_date="2026-07-10",
            analysis_mode="replay",
            artifact_origin="reconstructed",
        )

        self.assertTrue(
            any(row["pressure_direction"] == "downward" for row in artifact["timeline"]["events"])
        )
        self.assertEqual(artifact["pressure_direction"], "upward")
        self.assertEqual(artifact["phase"], "repair")
        self.assertIsNotNone(artifact["timeline"]["latest_confirmed_at"])

    def test_active_minute_event_keeps_direction_when_end_of_day_votes_disagree(self):
        template = json.loads(
            (
                ROOT
                / "tests"
                / "fixtures"
                / "quant_pressure_one_minute"
                / "raw"
                / "sh000001_20260521.json"
            ).read_text(encoding="utf-8")
        )["minute_bars"]
        changes = [0.0] * 220 + [-0.0001] * 18 + [0.0015] * 2
        price = 100.0
        rows = []
        for source_row, change in zip(template, changes):
            open_price = price
            price *= 1.0 + change
            rows.append(
                {
                    "datetime": source_row["datetime"],
                    "open": open_price,
                    "high": max(open_price, price) * 1.00001,
                    "low": min(open_price, price) * 0.99999,
                    "close": price,
                    "volume": 100000.0,
                    "amount": price * 100000.0,
                }
            )
        target_date = "2026-05-21"
        data = _minute_input(
            rows,
            trade_date=target_date,
            instrument_type="index",
        )
        data["indices"] = {
            "000001.SH": {
                "name": "上证指数",
                "change_pct": 1.0,
                "trade_date": target_date,
            }
        }
        data["market_stats"] = {
            "up_count": 3600,
            "down_count": 900,
            "flat_count": 100,
            "trade_date": target_date,
        }

        projection = build_market_language_source_projection(
            data,
            target_date=target_date,
            analysis_mode="replay",
        )
        artifact = build_market_language_translation(
            projection,
            target_date=target_date,
            analysis_mode="replay",
            artifact_origin="reconstructed",
        )

        active_event = next(
            row
            for row in reversed(artifact["timeline"]["events"])
            if row["invalidated_at"] is None
        )
        self.assertEqual(active_event["pressure_direction"], "downward")
        self.assertEqual(artifact["pressure_direction"], "downward")
        self.assertEqual(artifact["phase"], active_event["phase"])
        self.assertNotIn("向上", artifact["phase_label"])
        self.assertTrue(
            any(
                row["evidence_id"] == "c-aggregation-conflict"
                for row in artifact["counter_evidence"]
            )
        )

    def test_weighted_index_decline_with_positive_breadth_stays_index_weighted(self):
        data = _minute_input(
            _bar_rows_from_changes([-0.0008] * 55),
            instrument_type="index",
        )
        data["indices"] = {
            "000001.SH": {
                "name": "上证指数",
                "change_pct": -1.2,
                "trade_date": "2026-07-10",
            }
        }
        data["market_stats"] = {
            "up_count": 3600,
            "down_count": 900,
            "flat_count": 100,
            "trade_date": "2026-07-10",
        }
        projection = build_market_language_source_projection(
            data,
            target_date="2026-07-10",
            analysis_mode="replay",
        )
        artifact = build_market_language_translation(
            projection,
            target_date="2026-07-10",
            analysis_mode="replay",
            artifact_origin="reconstructed",
        )

        self.assertEqual(artifact["force_scope"], "index_weighted")
        self.assertEqual(artifact["pressure_direction"], "downward")
        self.assertTrue(
            any(row["evidence_id"] == "c-aggregation-conflict" for row in artifact["counter_evidence"])
        )

    def test_healthy_upward_diffusion_is_expansion_not_crowding_or_decay(self):
        data = _minute_input(
            _bar_rows_from_changes([0.0008] * 55),
            instrument_type="index",
        )
        data["indices"] = {
            "000001.SH": {
                "name": "上证指数",
                "change_pct": 1.1,
                "trade_date": "2026-07-10",
            }
        }
        data["market_stats"] = {
            "up_count": 3500,
            "down_count": 1000,
            "flat_count": 100,
            "trade_date": "2026-07-10",
        }
        data["market_language_sector_synchrony"] = {
            "leading_sector": "半导体",
            "active_constituent_pct": 72.0,
            "cross_sector_sync_pct": 66.0,
            "pressure_direction": "upward",
            "trade_date": "2026-07-10",
        }
        projection = build_market_language_source_projection(
            data,
            target_date="2026-07-10",
            analysis_mode="replay",
        )
        artifact = build_market_language_translation(
            projection,
            target_date="2026-07-10",
            analysis_mode="replay",
            artifact_origin="reconstructed",
        )

        self.assertEqual(artifact["force_scope"], "whole_market")
        self.assertEqual(artifact["pressure_direction"], "upward")
        self.assertEqual(artifact["phase"], "expansion")
        self.assertNotIn(artifact["phase"], {"crowding", "decay", "repair"})

    def test_explicit_source_dated_crowding_fact_can_mark_upward_crowding(self):
        data = _minute_input(
            _bar_rows_from_changes([0.0008] * 55),
            instrument_type="index",
        )
        data["indices"] = {
            "000001.SH": {
                "name": "上证指数",
                "change_pct": 1.1,
                "trade_date": "2026-07-10",
            }
        }
        data["market_stats"] = {
            "up_count": 3500,
            "down_count": 1000,
            "flat_count": 100,
            "trade_date": "2026-07-10",
        }
        data["market_language_sector_synchrony"] = {
            "leading_sector": "半导体",
            "active_constituent_pct": 72.0,
            "cross_sector_sync_pct": 66.0,
            "pressure_direction": "upward",
            "trade_date": "2026-07-10",
        }
        data["mainline_turnover_summary"] = {
            "sector_turnover_share_pct": 24.0,
            "crowding_signal": True,
            "crowding_evidence": ["板块成交占比集中且后排承接转弱"],
            "trade_date": "2026-07-10",
        }
        projection = build_market_language_source_projection(
            data,
            target_date="2026-07-10",
            analysis_mode="replay",
        )
        artifact = build_market_language_translation(
            projection,
            target_date="2026-07-10",
            analysis_mode="replay",
            artifact_origin="reconstructed",
        )

        self.assertEqual(artifact["pressure_direction"], "upward")
        self.assertEqual(artifact["phase"], "crowding")
        self.assertTrue(artifact["participation"]["crowding_signal"])

    def test_participation_trend_excludes_future_and_other_sector_rows(self):
        data = {
            "mainline_turnover_summary": {
                "current_mainline": "半导体",
                "trade_date": "2026-07-10",
                "query_date": "2026-07-10",
                "hot_sector_turnover_watch_rows": [
                    {"date": "2026-07-09", "sector_name": "半导体", "share": "5.0%"},
                    {"date": "2026-07-10", "sector_name": "半导体", "share": "10.0%"},
                    {"date": "2026-07-10", "sector_name": "电力", "share": "80.0%"},
                    {"date": "2026-07-13", "sector_name": "半导体", "share": "90.0%"},
                ],
            }
        }

        projection = build_market_language_source_projection(
            data,
            target_date="2026-07-10",
            analysis_mode="fresh",
        )

        self.assertEqual(
            projection["daily"]["participation"]["sector_turnover_share_change_pp"],
            5.0,
        )
        self.assertEqual(
            projection["daily"]["participation"]["sector_turnover_share_pct"],
            10.0,
        )

    def test_explicit_zero_synchronized_down_pct_is_not_replaced(self):
        projection = build_market_language_source_projection(
            {
                "market_stats": {
                    "up_count": 900,
                    "down_count": 100,
                    "flat_count": 0,
                    "synchronized_down_pct": 0.0,
                    "trade_date": "2026-07-10",
                }
            },
            target_date="2026-07-10",
            analysis_mode="fresh",
        )

        self.assertEqual(
            projection["daily"]["market_breadth"]["synchronized_down_pct"],
            0.0,
        )

    def test_negative_or_fractional_market_counts_are_rejected(self):
        for up_count in (-100, 900.5):
            with self.subTest(up_count=up_count):
                projection = build_market_language_source_projection(
                    {
                        "market_stats": {
                            "up_count": up_count,
                            "down_count": 1100,
                            "flat_count": 0,
                            "trade_date": "2026-07-10",
                        }
                    },
                    target_date="2026-07-10",
                    analysis_mode="fresh",
                )

                self.assertEqual(projection["daily"]["market_breadth"], {})

    def test_whole_market_scope_requires_breadth_direction_alignment(self):
        data = _minute_input(
            _bar_rows_from_changes([-0.0008] * 55),
            instrument_type="index",
        )
        data["indices"] = {
            "000001.SH": {
                "name": "上证指数",
                "change_pct": -1.1,
                "trade_date": "2026-07-10",
            }
        }
        data["market_stats"] = {
            "up_count": 3600,
            "down_count": 900,
            "flat_count": 100,
            "trade_date": "2026-07-10",
        }
        data["market_language_sector_synchrony"] = {
            "leading_sector": "权重方向",
            "active_constituent_pct": 70.0,
            "cross_sector_sync_pct": 65.0,
            "pressure_direction": "downward",
            "trade_date": "2026-07-10",
        }
        projection = build_market_language_source_projection(
            data,
            target_date="2026-07-10",
            analysis_mode="replay",
        )
        artifact = build_market_language_translation(
            projection,
            target_date="2026-07-10",
            analysis_mode="replay",
            artifact_origin="reconstructed",
        )

        self.assertEqual(artifact["force_scope"], "multi_sector")
        self.assertNotEqual(artifact["force_scope"], "whole_market")
        self.assertTrue(
            any(row["evidence_id"] == "c-aggregation-conflict" for row in artifact["counter_evidence"])
        )

    def test_whole_market_scope_requires_numeric_cross_sector_synchrony(self):
        data = _minute_input(
            _bar_rows_from_changes([-0.0008] * 55),
            instrument_type="index",
        )
        data["indices"] = {
            "000001.SH": {
                "name": "上证指数",
                "change_pct": -1.1,
                "trade_date": "2026-07-10",
            }
        }
        data["market_stats"] = {
            "up_count": 900,
            "down_count": 3600,
            "flat_count": 100,
            "trade_date": "2026-07-10",
        }
        data["market_language_sector_synchrony"] = {
            "pressure_direction": "downward",
            "trade_date": "2026-07-10",
        }

        projection = build_market_language_source_projection(
            data,
            target_date="2026-07-10",
            analysis_mode="replay",
        )
        artifact = build_market_language_translation(
            projection,
            target_date="2026-07-10",
            analysis_mode="replay",
            artifact_origin="reconstructed",
        )

        self.assertEqual(projection["daily"]["sector_synchrony"], {})
        self.assertEqual(artifact["force_scope"], "index_weighted")

    def test_cross_sector_majority_without_index_is_multi_sector(self):
        projection = build_market_language_source_projection(
            {
                "market_language_sector_synchrony": {
                    "leading_sector": "半导体",
                    "cross_sector_sync_pct": 65.0,
                    "pressure_direction": "downward",
                    "trade_date": "2026-07-10",
                }
            },
            target_date="2026-07-10",
            analysis_mode="fresh",
        )
        artifact = build_market_language_translation(
            projection,
            target_date="2026-07-10",
            analysis_mode="fresh",
        )

        self.assertEqual(artifact["force_scope"], "multi_sector")
        self.assertEqual(artifact["pressure_direction"], "downward")

    def test_cross_sector_sync_opposite_to_current_direction_does_not_define_scope(self):
        data = _minute_input(
            _bar_rows_from_changes([-0.0008] * 55),
            instrument_type="index",
        )
        data["market_language_sector_synchrony"] = {
            "leading_sector": "修复方向",
            "cross_sector_sync_pct": 65.0,
            "pressure_direction": "upward",
            "trade_date": "2026-07-10",
        }
        projection = build_market_language_source_projection(
            data,
            target_date="2026-07-10",
            analysis_mode="fresh",
        )
        artifact = build_market_language_translation(
            projection,
            target_date="2026-07-10",
            analysis_mode="fresh",
        )

        self.assertEqual(artifact["pressure_direction"], "downward")
        self.assertEqual(artifact["force_scope"], "index_weighted")
        self.assertTrue(
            any(row["evidence_id"] == "c-aggregation-conflict" for row in artifact["counter_evidence"])
        )

    def test_near_zero_drift_stays_balanced_without_events(self):
        rows = _bar_rows_from_changes([-1e-12] * 60)
        projection = build_market_language_source_projection(
            _minute_input(rows),
            target_date="2026-07-10",
            analysis_mode="replay",
        )
        artifact = build_market_language_translation(
            projection,
            target_date="2026-07-10",
            analysis_mode="replay",
            artifact_origin="reconstructed",
        )

        self.assertEqual(artifact["pressure_direction"], "balanced")
        self.assertEqual(artifact["phase"], "unclear")
        self.assertEqual(artifact["timeline"]["events"], [])

    def test_liquidity_proxies_require_interval_cny_and_share_units(self):
        data = _minute_input(_synthetic_one_minute_rows())
        data["source"].update(
            {
                "amount_semantics": "cumulative",
                "volume_unit": "lots",
                "volume_semantics": "cumulative",
            }
        )
        projection = build_market_language_source_projection(
            data,
            target_date="2026-07-10",
            analysis_mode="fresh",
        )
        artifact = build_market_language_translation(
            projection,
            target_date="2026-07-10",
            analysis_mode="fresh",
        )

        self.assertIsNone(artifact["liquidity_proxies"]["impact_per_100m_turnover_bp"])
        self.assertIsNone(artifact["liquidity_proxies"]["below_vwap_dwell_minutes"])

    def test_tiny_acceleration_does_not_turn_gradual_decline_into_cascade(self):
        rows = _bar_rows_from_changes([-0.0001] * 45 + [-0.000100001] * 15)
        projection = build_market_language_source_projection(
            _minute_input(rows),
            target_date="2026-07-10",
            analysis_mode="replay",
        )
        artifact = build_market_language_translation(
            projection,
            target_date="2026-07-10",
            analysis_mode="replay",
            artifact_origin="reconstructed",
        )

        self.assertEqual(artifact["pressure_direction"], "downward")
        self.assertEqual(artifact["phase"], "expansion")

    def test_replay_rejects_undated_end_of_day_facts(self):
        projection = build_market_language_source_projection(
            {
                "indices": {"000001.SH": {"name": "上证指数", "change_pct": -1.2}},
                "market_stats": {"up_count": 900, "down_count": 3600, "flat_count": 100},
                "market_language_sector_synchrony": {
                    "leading_sector": "半导体",
                    "active_constituent_pct": 70.0,
                    "pressure_direction": "downward",
                },
                "mainline_turnover_summary": {"sector_turnover_share_pct": 20.0},
            },
            target_date="2026-07-10",
            analysis_mode="replay",
        )
        artifact = build_market_language_translation(
            projection,
            target_date="2026-07-10",
            analysis_mode="replay",
            artifact_origin="reconstructed",
        )

        self.assertEqual(projection["daily"]["cap_weighted"], {})
        self.assertEqual(projection["daily"]["market_breadth"], {})
        self.assertEqual(projection["daily"]["sector_synchrony"], {})
        self.assertEqual(projection["daily"]["participation"], {})
        self.assertEqual(projection["sources"], [])
        self.assertEqual(artifact["evidence_status"], "insufficient")

    def test_missing_query_date_remains_unknown(self):
        projection = build_market_language_source_projection(
            {
                "indices": {
                    "000001.SH": {
                        "name": "上证指数",
                        "change_pct": -1.2,
                        "trade_date": "2026-07-10",
                    }
                }
            },
            target_date="2026-07-10",
            analysis_mode="replay",
        )

        self.assertEqual(len(projection["sources"]), 1)
        self.assertIsNone(projection["sources"][0]["query_date"])

    def test_malformed_query_date_is_rejected_during_source_projection(self):
        end_of_day_data = {
            "indices": {
                "000001.SH": {
                    "name": "上证指数",
                    "change_pct": -1.2,
                    "trade_date": "2026-07-10",
                    "query_date": "not-a-date",
                }
            }
        }
        minute_data = _minute_input(_synthetic_one_minute_rows())
        minute_data["source"]["query_date"] = "2026-07-10T15:30:00"

        for data in (end_of_day_data, minute_data):
            with self.subTest(data=data):
                with self.assertRaisesRegex(ValueError, "query_date"):
                    build_market_language_source_projection(
                        data,
                        target_date="2026-07-10",
                        analysis_mode="fresh",
                    )

    def test_source_dates_require_exact_iso_date(self):
        end_of_day_data = {
            "indices": {
                "000001.SH": {
                    "name": "上证指数",
                    "change_pct": -1.2,
                    "trade_date": "2026-07-10junk",
                }
            }
        }
        minute_data = _minute_input(_synthetic_one_minute_rows())
        minute_data["source"]["source_date"] = "2026-07-10junk"

        for data in (end_of_day_data, minute_data):
            with self.subTest(data=data):
                with self.assertRaisesRegex(ValueError, "source_date"):
                    build_market_language_source_projection(
                        data,
                        target_date="2026-07-10",
                        analysis_mode="fresh",
                    )

    def test_fresh_end_of_day_rows_do_not_inherit_top_level_date(self):
        data = {
            "trade_date": "2026-07-10",
            "target_date": "2026-07-10",
            "indices": {
                "000001.SH": {
                    "name": "上证指数",
                    "change_pct": -1.0,
                }
            },
            "market_stats": {
                "up_count": 900,
                "down_count": 3600,
                "flat_count": 100,
            },
        }

        projection = build_market_language_source_projection(
            data,
            target_date="2026-07-10",
            analysis_mode="fresh",
        )
        artifact = build_market_language_translation(
            projection,
            target_date="2026-07-10",
            analysis_mode="fresh",
        )

        self.assertEqual(projection["sources"], [])
        self.assertEqual(projection["daily"]["cap_weighted"], {})
        self.assertEqual(projection["daily"]["market_breadth"], {})
        self.assertEqual(artifact["evidence_status"], "insufficient")
        self.assertEqual(artifact["pressure_direction"], "unclear")

    def test_five_minute_path_is_not_promoted_to_one_minute_event_timing(self):
        rows = _bar_rows_from_changes(
            [-0.001] * 20,
            interval_minutes=5,
        )
        projection = build_market_language_source_projection(
            _minute_input(rows, bar_period_minutes=5),
            target_date="2026-07-10",
            analysis_mode="replay",
        )
        artifact = build_market_language_translation(
            projection,
            target_date="2026-07-10",
            analysis_mode="replay",
            artifact_origin="reconstructed",
        )

        self.assertEqual(artifact["data_granularity"], "five_minute")
        self.assertEqual(artifact["timeline"]["events"], [])
        self.assertIn("one_minute_price_path", artifact["missing_evidence"])

    def test_interval_start_is_normalized_to_equivalent_interval_end_timing(self):
        interval_start_rows = _synthetic_one_minute_rows()
        interval_end_rows = copy.deepcopy(interval_start_rows)
        for row in interval_end_rows:
            timestamp = dt.datetime.fromisoformat(row["datetime"]) + dt.timedelta(minutes=1)
            row["datetime"] = timestamp.strftime("%Y-%m-%d %H:%M:%S")

        interval_start_data = _minute_input(interval_start_rows)
        interval_start_data["source"]["bar_time_semantics"] = "interval_start"
        interval_end_data = _minute_input(interval_end_rows)
        interval_start_projection = build_market_language_source_projection(
            interval_start_data,
            target_date="2026-07-10",
            analysis_mode="replay",
        )
        interval_end_projection = build_market_language_source_projection(
            interval_end_data,
            target_date="2026-07-10",
            analysis_mode="replay",
        )
        interval_start_artifact = build_market_language_translation(
            interval_start_projection,
            target_date="2026-07-10",
            analysis_mode="replay",
            artifact_origin="reconstructed",
        )
        interval_end_artifact = build_market_language_translation(
            interval_end_projection,
            target_date="2026-07-10",
            analysis_mode="replay",
            artifact_origin="reconstructed",
        )

        self.assertEqual(
            interval_start_projection["minute_series"][0]["bars"],
            interval_end_projection["minute_series"][0]["bars"],
        )
        self.assertEqual(
            interval_start_projection["sources"][0]["time_semantics"],
            "interval_end_normalized_from_interval_start",
        )
        self.assertEqual(
            interval_start_artifact["timeline"]["first_candidate_at"],
            interval_end_artifact["timeline"]["first_candidate_at"],
        )

    def test_five_minute_and_end_of_day_sources_are_mixed_granularity(self):
        data = _minute_input(
            _bar_rows_from_changes([-0.001] * 20, interval_minutes=5),
            bar_period_minutes=5,
        )
        data["indices"] = {
            "000001.SH": {
                "name": "上证指数",
                "change_pct": -1.0,
                "trade_date": "2026-07-10",
            }
        }
        projection = build_market_language_source_projection(
            data,
            target_date="2026-07-10",
            analysis_mode="replay",
        )
        artifact = build_market_language_translation(
            projection,
            target_date="2026-07-10",
            analysis_mode="replay",
            artifact_origin="reconstructed",
        )

        self.assertEqual(
            {row["granularity"] for row in projection["sources"]},
            {"five_minute", "end_of_day"},
        )
        self.assertEqual(artifact["data_granularity"], "mixed")

    def test_declared_one_minute_rejects_five_minute_intervals(self):
        rows = _bar_rows_from_changes([-0.001] * 20, interval_minutes=5)
        projection = build_market_language_source_projection(
            _minute_input(rows, bar_period_minutes=1),
            target_date="2026-07-10",
            analysis_mode="replay",
        )

        self.assertEqual(projection["minute_series"], [])
        self.assertIn("minute_interval_inconsistent", projection["missing_evidence"])

    def test_inconsistent_one_minute_time_axis_is_rejected(self):
        rows = _bar_rows_from_changes([-0.001] * 40)
        for row in rows[20:]:
            timestamp = dt.datetime.fromisoformat(row["datetime"]) + dt.timedelta(minutes=1)
            row["datetime"] = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        projection = build_market_language_source_projection(
            _minute_input(rows),
            target_date="2026-07-10",
            analysis_mode="replay",
        )

        self.assertEqual(projection["minute_series"], [])
        self.assertIn("minute_interval_inconsistent", projection["missing_evidence"])

    def test_full_anchor_minute_sessions_remain_sufficient(self):
        for stem in (
            "sh603986_20260710",
            "sh600584_20260710",
            "sh000001_20260521",
        ):
            artifact = self._fixture_artifact(stem)
            self.assertEqual(artifact["evidence_status"], "sufficient", stem)

    def test_missing_final_five_minutes_is_not_sufficient_one_minute_evidence(self):
        payload = json.loads(
            (
                ROOT
                / "tests"
                / "fixtures"
                / "quant_pressure_one_minute"
                / "raw"
                / "sh603986_20260710.json"
            ).read_text(encoding="utf-8")
        )
        payload["minute_bars"] = payload["minute_bars"][:-5]
        projection = build_market_language_source_projection(
            payload,
            target_date="2026-07-10",
            analysis_mode="replay",
        )
        artifact = build_market_language_translation(
            projection,
            target_date="2026-07-10",
            analysis_mode="replay",
            artifact_origin="reconstructed",
        )

        self.assertEqual(len(projection["minute_series"][0]["bars"]), 235)
        self.assertEqual(artifact["evidence_status"], "partial")

    def test_future_prices_exist_only_in_replay_posthoc_validation(self):
        data = _minute_input(_synthetic_one_minute_rows())
        data["market_language_posthoc_trade_calendar"] = _posthoc_trade_calendar()
        data["market_language_posthoc_daily_bars"] = [
            {
                "trade_date": "2026-07-13",
                "source_date": "2026-07-13",
                "query_date": "2026-07-15",
                "code": "600000.SH",
                "open": 101.0,
                "high": 104.0,
                "low": 99.0,
                "close": 103.0,
                "source": "unit_test.daily",
            },
            {
                "trade_date": "2026-07-14",
                "source_date": "2026-07-14",
                "query_date": "2026-07-15",
                "code": "600000.SH",
                "open": 103.0,
                "high": 105.0,
                "low": 100.0,
                "close": 101.0,
                "source": "unit_test.daily",
            },
        ]
        data["market_language_fund_overlap"] = {
            "overlap_pct": 32.5,
            "target_date": "2026-07-10",
            "source_date": "2026-07-14",
            "query_date": "2026-07-15",
            "instrument_code": "600000.SH",
            "instrument_name": "测试样本",
            "source": "unit_test",
        }
        fresh_projection = build_market_language_source_projection(
            data,
            target_date="2026-07-10",
            analysis_mode="fresh",
        )
        fresh = build_market_language_translation(
            fresh_projection,
            target_date="2026-07-10",
            analysis_mode="fresh",
        )
        replay_projection = build_market_language_source_projection(
            data,
            target_date="2026-07-10",
            analysis_mode="replay",
        )
        replay = build_market_language_translation(
            replay_projection,
            target_date="2026-07-10",
            analysis_mode="replay",
            artifact_origin="reconstructed",
            include_posthoc=True,
        )

        self.assertIsNone(fresh["posthoc_validation"])
        self.assertEqual(
            fresh_projection["posthoc_inputs"],
            {"daily_bars": [], "fund_overlap": None, "trade_calendar": {}},
        )
        self.assertEqual(replay["posthoc_validation"]["t1_price_range"]["trade_date"], "2026-07-13")
        self.assertEqual(replay["posthoc_validation"]["t2_price_range"]["trade_date"], "2026-07-14")
        self.assertEqual(replay["posthoc_validation"]["fund_overlap"]["overlap_pct"], 32.5)
        self.assertTrue(replay["posthoc_validation"]["event_reviews"])
        self.assertIn("future_return_pct", replay["posthoc_validation"]["event_reviews"][0])
        production_copy = copy.deepcopy(replay)
        production_copy.pop("posthoc_validation", None)
        self.assertNotIn("future_return_pct", json.dumps(production_copy, ensure_ascii=False))

    def test_posthoc_daily_ranges_deduplicate_dates_and_require_matching_instrument(self):
        data = _minute_input(_synthetic_one_minute_rows())
        data["market_language_posthoc_trade_calendar"] = _posthoc_trade_calendar()
        data["market_language_posthoc_daily_bars"] = [
            {
                "trade_date": "2026-07-13",
                "source_date": "2026-07-13",
                "query_date": "2026-07-15",
                "code": "300001.SZ",
                "open": 80.0,
                "high": 82.0,
                "low": 79.0,
                "close": 81.0,
                "source": "wrong.instrument",
            },
            {
                "trade_date": "2026-07-13",
                "source_date": "2026-07-13",
                "query_date": "2026-07-15",
                "code": "600000.SH",
                "open": 101.0,
                "high": 104.0,
                "low": 99.0,
                "close": 103.0,
                "source": "unit_test.daily.first",
            },
            {
                "trade_date": "2026-07-13",
                "source_date": "2026-07-13",
                "query_date": "2026-07-16",
                "code": "600000.SH",
                "open": 102.0,
                "high": 105.0,
                "low": 100.0,
                "close": 104.0,
                "source": "unit_test.daily.duplicate",
            },
            {
                "trade_date": "2026-07-14",
                "source_date": "2026-07-14",
                "query_date": "2026-07-15",
                "code": "600000.SH",
                "open": 103.0,
                "high": 105.0,
                "low": 100.0,
                "close": 101.0,
                "source": "unit_test.daily.second",
            },
            {
                "trade_date": "2026-07-15",
                "source_date": "2026-07-15",
                "code": "600000.SH",
                "open": 101.0,
                "high": 103.0,
                "low": 99.0,
                "close": 100.0,
                "source": "missing.query.date",
            },
        ]
        projection = build_market_language_source_projection(
            data,
            target_date="2026-07-10",
            analysis_mode="replay",
        )
        artifact = build_market_language_translation(
            projection,
            target_date="2026-07-10",
            analysis_mode="replay",
            artifact_origin="reconstructed",
            include_posthoc=True,
        )

        posthoc = artifact["posthoc_validation"]
        self.assertEqual(posthoc["t1_price_range"]["trade_date"], "2026-07-13")
        self.assertEqual(posthoc["t1_price_range"]["source"], "unit_test.daily.first")
        self.assertEqual(posthoc["t2_price_range"]["trade_date"], "2026-07-14")

    def test_posthoc_does_not_shift_t2_into_a_missing_t1_slot(self):
        data = _minute_input(_synthetic_one_minute_rows())
        data["market_language_posthoc_trade_calendar"] = _posthoc_trade_calendar()
        data["market_language_posthoc_daily_bars"] = [
            {
                "trade_date": "2026-07-14",
                "source_date": "2026-07-14",
                "query_date": "2026-07-15",
                "code": "600000.SH",
                "open": 103.0,
                "high": 105.0,
                "low": 100.0,
                "close": 101.0,
                "source": "unit_test.daily.second",
            }
        ]

        projection = build_market_language_source_projection(
            data,
            target_date="2026-07-10",
            analysis_mode="replay",
        )
        artifact = build_market_language_translation(
            projection,
            target_date="2026-07-10",
            analysis_mode="replay",
            artifact_origin="reconstructed",
            include_posthoc=True,
        )

        posthoc = artifact["posthoc_validation"]
        self.assertIsNone(posthoc["t1_price_range"])
        self.assertEqual(posthoc["t2_price_range"]["trade_date"], "2026-07-14")

    def test_posthoc_instrument_identity_keeps_exchange_suffix(self):
        data = _minute_input(
            _synthetic_one_minute_rows(),
            instrument_type="index",
        )
        data["market_language_posthoc_trade_calendar"] = _posthoc_trade_calendar()
        data["market_language_posthoc_daily_bars"] = [
            {
                "trade_date": "2026-07-13",
                "source_date": "2026-07-13",
                "query_date": "2026-07-15",
                "code": "000001.SZ",
                "open": 10.0,
                "high": 10.5,
                "low": 9.8,
                "close": 10.2,
                "source": "wrong.exchange",
            }
        ]

        projection = build_market_language_source_projection(
            data,
            target_date="2026-07-10",
            analysis_mode="replay",
        )
        artifact = build_market_language_translation(
            projection,
            target_date="2026-07-10",
            analysis_mode="replay",
            artifact_origin="reconstructed",
            include_posthoc=True,
        )

        self.assertIsNone(artifact["posthoc_validation"]["t1_price_range"])

    def test_posthoc_fund_overlap_requires_dates_and_matching_instrument(self):
        data = _minute_input(_synthetic_one_minute_rows())
        data["market_language_fund_overlap"] = {
            "overlap_pct": 88.0,
            "target_date": "2026-07-09",
            "source_date": "2026-07-14",
            "query_date": "2026-07-15",
            "instrument_code": "300001.SZ",
            "source": "wrong.fact",
        }
        projection = build_market_language_source_projection(
            data,
            target_date="2026-07-10",
            analysis_mode="replay",
        )
        artifact = build_market_language_translation(
            projection,
            target_date="2026-07-10",
            analysis_mode="replay",
            artifact_origin="reconstructed",
            include_posthoc=True,
        )

        self.assertIsNone(projection["posthoc_inputs"]["fund_overlap"])
        self.assertIsNone(artifact["posthoc_validation"]["fund_overlap"])
        self.assertIn("fund_overlap", artifact["posthoc_validation"]["missing_evidence"])

    def test_posthoc_dates_reject_non_iso_suffixes(self):
        daily_case = _minute_input(_synthetic_one_minute_rows())
        daily_case["market_language_posthoc_daily_bars"] = [
            {
                "trade_date": "2026-07-13",
                "source_date": "2026-07-13",
                "query_date": "2026-07-15junk",
                "code": "600000.SH",
                "open": 101.0,
                "high": 104.0,
                "low": 99.0,
                "close": 103.0,
            }
        ]
        calendar_case = _minute_input(_synthetic_one_minute_rows())
        calendar_case["market_language_posthoc_trade_calendar"] = _posthoc_trade_calendar()
        calendar_case["market_language_posthoc_trade_calendar"]["query_date"] = "2026-07-15junk"
        overlap_case = _minute_input(_synthetic_one_minute_rows())
        overlap_case["market_language_fund_overlap"] = {
            "overlap_pct": 32.5,
            "target_date": "2026-07-10junk",
            "source_date": "2026-07-14",
            "query_date": "2026-07-15",
            "instrument_code": "600000.SH",
        }

        for data in (daily_case, calendar_case, overlap_case):
            with self.subTest(data=data):
                with self.assertRaisesRegex(ValueError, "must be YYYY-MM-DD"):
                    build_market_language_source_projection(
                        data,
                        target_date="2026-07-10",
                        analysis_mode="replay",
                    )

    def test_empty_input_is_insufficient_and_does_not_invent_event_times(self):
        projection = build_market_language_source_projection(
            {},
            target_date="2026-07-10",
            analysis_mode="replay",
        )
        artifact = build_market_language_translation(
            projection,
            target_date="2026-07-10",
            analysis_mode="replay",
            artifact_origin="reconstructed",
        )

        self.assertEqual(artifact["schema_version"], MARKET_LANGUAGE_SCHEMA_VERSION)
        self.assertEqual(artifact["evidence_status"], "insufficient")
        self.assertEqual(artifact["timeline"]["events"], [])
        self.assertIsNone(artifact["timeline"]["first_candidate_at"])
        self.assertIn("one_minute_price_path", artifact["missing_evidence"])
        self.assertIn("market_breadth", artifact["missing_evidence"])
        self.assertIsNone(artifact["posthoc_validation"])

    def test_target_date_end_of_day_facts_degrade_without_minute_precision(self):
        data = {
            "indices": {
                "000001.SH": {
                    "name": "上证指数",
                    "change_pct": -1.2,
                    "trade_date": "2026-07-10",
                    "data_source": "tushare.index_daily",
                }
            },
            "market_stats": {
                "up_count": 900,
                "down_count": 3600,
                "flat_count": 100,
                "trade_date": "2026-07-10",
                "data_source": "tushare.daily",
            },
        }
        projection = build_market_language_source_projection(
            data,
            target_date="2026-07-10",
            analysis_mode="fresh",
        )
        artifact = build_market_language_translation(
            projection,
            target_date="2026-07-10",
            analysis_mode="fresh",
        )

        self.assertEqual(artifact["data_granularity"], "end_of_day")
        self.assertEqual(artifact["evidence_status"], "partial")
        self.assertEqual(artifact["pressure_direction"], "downward")
        self.assertEqual(artifact["timeline"]["events"], [])
        self.assertAlmostEqual(
            artifact["aggregation_comparison"]["market_breadth"]["advance_ratio_pct"],
            900 / 4600 * 100,
        )
        self.assertEqual(
            artifact["aggregation_comparison"]["cap_weighted"]["return_pct"],
            -1.2,
        )

    def test_non_target_date_minute_source_is_rejected(self):
        rows = _synthetic_one_minute_rows("2026-07-09")
        projection = build_market_language_source_projection(
            _minute_input(rows, trade_date="2026-07-09"),
            target_date="2026-07-10",
            analysis_mode="replay",
        )
        artifact = build_market_language_translation(
            projection,
            target_date="2026-07-10",
            analysis_mode="replay",
            artifact_origin="reconstructed",
        )

        self.assertEqual(projection["minute_series"], [])
        self.assertEqual(artifact["timeline"]["events"], [])
        self.assertIn("target_date_minute_source", artifact["missing_evidence"])

    def test_one_minute_path_preserves_invalidated_round_and_re_candidate(self):
        projection = build_market_language_source_projection(
            _minute_input(_synthetic_one_minute_rows()),
            target_date="2026-07-10",
            analysis_mode="replay",
        )
        artifact = build_market_language_translation(
            projection,
            target_date="2026-07-10",
            analysis_mode="replay",
            artifact_origin="reconstructed",
        )

        events = artifact["timeline"]["events"]
        downward_events = [row for row in events if row["pressure_direction"] == "downward"]
        self.assertGreaterEqual(len(downward_events), 2)
        self.assertIsNotNone(downward_events[0]["confirmed_at"])
        self.assertIsNotNone(downward_events[0]["invalidated_at"])
        self.assertGreater(downward_events[1]["candidate_at"], downward_events[0]["invalidated_at"])
        self.assertEqual(
            artifact["timeline"]["candidate_invalidations"],
            sum(row["invalidated_at"] is not None for row in events),
        )
        self.assertEqual(artifact["evidence_status"], "partial")
        self.assertEqual(artifact["force_scope"], "single_stock")
        self.assertTrue(all(row["evidence_refs"] for row in events))

    def test_future_rows_do_not_rewrite_an_already_closed_event(self):
        rows = _synthetic_one_minute_rows()
        projection = build_market_language_source_projection(
            _minute_input(rows[:48]),
            target_date="2026-07-10",
            analysis_mode="replay",
        )
        partial = build_market_language_translation(
            projection,
            target_date="2026-07-10",
            analysis_mode="replay",
            artifact_origin="reconstructed",
        )
        closed = next(row for row in partial["timeline"]["events"] if row["invalidated_at"])

        changed_future = copy.deepcopy(rows)
        for row in changed_future[48:]:
            row["close"] *= 1.08
            row["open"] = row["close"]
            row["high"] = row["close"]
            row["low"] = row["close"]
            row["amount"] = row["close"] * row["volume"]
        extended_projection = build_market_language_source_projection(
            _minute_input(changed_future),
            target_date="2026-07-10",
            analysis_mode="replay",
        )
        extended = build_market_language_translation(
            extended_projection,
            target_date="2026-07-10",
            analysis_mode="replay",
            artifact_origin="reconstructed",
        )
        same_event = next(row for row in extended["timeline"]["events"] if row["event_id"] == closed["event_id"])

        for field in (
            "candidate_at",
            "detected_at",
            "confirmed_at",
            "invalidated_at",
            "causal_cutoff",
            "pressure_direction",
            "phase",
        ):
            self.assertEqual(same_event[field], closed[field], field)

    def test_direction_phase_validation_rejects_illegal_combinations(self):
        projection = build_market_language_source_projection(
            {},
            target_date="2026-07-10",
            analysis_mode="fresh",
        )
        artifact = build_market_language_translation(
            projection,
            target_date="2026-07-10",
            analysis_mode="fresh",
        )
        artifact["pressure_direction"] = "downward"
        artifact["phase"] = "crowding"

        with self.assertRaisesRegex(ValueError, "pressure_direction/phase"):
            validate_market_language_translation(artifact)

    def test_normalization_rejects_non_finite_numbers_and_hashes_numeric_equivalents(self):
        projection = build_market_language_source_projection(
            {},
            target_date="2026-07-10",
            analysis_mode="fresh",
        )
        artifact = build_market_language_translation(
            projection,
            target_date="2026-07-10",
            analysis_mode="fresh",
        )
        left = copy.deepcopy(artifact)
        right = copy.deepcopy(artifact)
        left["timeline"]["candidate_invalidations"] = 1.0
        right["timeline"]["candidate_invalidations"] = 1
        self.assertEqual(canonical_market_language_hash(left), canonical_market_language_hash(right))

        artifact["price_pressure"]["slope_5m_bp_per_min"] = math.inf
        with self.assertRaisesRegex(ValueError, "finite"):
            normalize_market_language_translation(artifact)

    def test_saved_source_query_date_must_be_valid_and_not_precede_source_date(self):
        projection = build_market_language_source_projection(
            _minute_input(_synthetic_one_minute_rows()),
            target_date="2026-07-10",
            analysis_mode="fresh",
        )
        artifact = build_market_language_translation(
            projection,
            target_date="2026-07-10",
            analysis_mode="fresh",
        )
        invalid = copy.deepcopy(artifact)
        invalid["sources"][0]["query_date"] = "not-a-date"
        with self.assertRaisesRegex(ValueError, "query_date"):
            validate_market_language_translation(invalid)

        before_source = copy.deepcopy(artifact)
        before_source["sources"][0]["query_date"] = "2026-07-09"
        with self.assertRaisesRegex(ValueError, "must not precede"):
            validate_market_language_translation(before_source)

    def test_validator_rejects_event_timestamp_from_another_date(self):
        artifact = self._fixture_artifact("sh603986_20260710")
        artifact["timeline"]["events"][0]["candidate_at"] = "2026-07-09 09:47:00"

        with self.assertRaisesRegex(ValueError, "target_date"):
            validate_market_language_translation(artifact)

    def test_validator_rejects_event_invalidation_before_confirmation(self):
        artifact = self._fixture_artifact("sh603986_20260710")
        event = next(
            row
            for row in artifact["timeline"]["events"]
            if row.get("confirmed_at") and row.get("invalidated_at")
        )
        event["invalidated_at"] = event["candidate_at"]

        with self.assertRaisesRegex(ValueError, "precedes confirmed_at"):
            validate_market_language_translation(artifact)

    def test_validator_rejects_confirmation_without_three_minute_observations(self):
        artifact = self._fixture_artifact("sh603986_20260710")
        event = next(
            row for row in artifact["timeline"]["events"] if row.get("confirmed_at")
        )
        event["confirmed_at"] = event["detected_at"]

        with self.assertRaisesRegex(ValueError, "three overlapping"):
            validate_market_language_translation(artifact)

    def test_validator_rejects_fixed_window_time_from_another_date(self):
        artifact = self._fixture_artifact("sh603986_20260710")
        artifact["fixed_window_observations"][0]["as_of_time"] = "2026-07-09 09:35:00"

        with self.assertRaisesRegex(ValueError, "fixed window as_of_time"):
            validate_market_language_translation(artifact)

    def test_validator_rejects_fixed_window_time_after_its_cutoff(self):
        artifact = self._fixture_artifact("sh603986_20260710")
        artifact["fixed_window_observations"][0]["as_of_time"] = "2026-07-10 14:55:00"

        with self.assertRaisesRegex(ValueError, "match its cutoff"):
            validate_market_language_translation(artifact)

    def test_validator_rejects_fixed_window_illegal_direction_phase_combination(self):
        artifact = self._fixture_artifact("sh603986_20260710")
        observation = artifact["fixed_window_observations"][0]
        observation["pressure_direction"] = "downward"
        observation["phase"] = "crowding"

        with self.assertRaisesRegex(ValueError, "fixed window pressure_direction/phase"):
            validate_market_language_translation(artifact)

    def test_validator_rejects_unknown_fixed_window_counter_evidence_reference(self):
        artifact = self._fixture_artifact("sh603986_20260710")
        artifact["fixed_window_observations"][0]["counter_evidence_refs"] = [
            "missing-counter-id"
        ]

        with self.assertRaisesRegex(ValueError, "fixed window counter_evidence_refs"):
            validate_market_language_translation(artifact)


if __name__ == "__main__":
    unittest.main()
