from __future__ import annotations

import contextlib
import copy
import io
import json
import math
import sys
import time
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "quant_pressure_replay"
sys.path.insert(0, str(ROOT / "scripts"))


class QuantPressureReplayRuntimeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from research import quant_pressure_replay_runtime as runtime

        cls.runtime = runtime
        cls.cases = {
            path.stem: json.loads(path.read_text(encoding="utf-8"))
            for path in sorted((FIXTURE_ROOT / "raw").glob("*.json"))
        }
        cls.expectations = json.loads(
            (FIXTURE_ROOT / "expectations.json").read_text(encoding="utf-8")
        )

    def _build(self, case_id):
        return self.runtime.build_quant_pressure_replay(copy.deepcopy(self.cases[case_id]))

    @staticmethod
    def _timeline_by_time(result):
        return {row["as_of_bar"]: row for row in result["prefix_timeline"]}

    @staticmethod
    def _all_keys(value):
        keys = set()
        if isinstance(value, dict):
            for key, child in value.items():
                keys.add(key)
                keys.update(QuantPressureReplayRuntimeTest._all_keys(child))
        elif isinstance(value, list):
            for child in value:
                keys.update(QuantPressureReplayRuntimeTest._all_keys(child))
        return keys

    def _assert_declared_expectation(self, result, assertion):
        timeline = result["prefix_timeline"]
        rows = self._timeline_by_time(result)
        kind = assertion["assertion"]
        if kind == "current_dynamics_any_after":
            observed = {
                row["current_dynamics"]
                for row in timeline
                if row["as_of_bar"] >= assertion["after"]
            }
            self.assertTrue(observed.intersection(assertion["allowed"]))
        elif kind == "point_field_not_in":
            self.assertNotIn(
                rows[assertion["as_of_bar"]][assertion["field"]],
                assertion["forbidden"],
            )
        elif kind == "event_order":
            before = next(
                row["metrics"][assertion["before"]]
                for row in timeline
                if row["metrics"].get(assertion["before"])
            )
            after = next(
                row["metrics"][assertion["after"]]
                for row in timeline
                if row["metrics"].get(assertion["after"])
            )
            self.assertLess(before, after)
        elif kind == "final_field_in":
            self.assertIn(timeline[-1][assertion["field"]], assertion["allowed"])
        elif kind == "final_field_not_in":
            self.assertNotIn(timeline[-1][assertion["field"]], assertion["forbidden"])
        elif kind == "final_field_equals":
            self.assertEqual(timeline[-1][assertion["field"]], assertion["value"])
        elif kind == "final_field_not_equals":
            self.assertNotEqual(timeline[-1][assertion["field"]], assertion["value"])
        elif kind == "opening_gap_separate_from_intraday_slope":
            self.assertIsNotNone(timeline[0]["metrics"]["opening_gap_bp"])
            self.assertIsNone(timeline[0]["metrics"]["current_log_slope_bp_per_bar"])
        elif kind == "all_prefix_field_equals":
            self.assertTrue(
                all(row[assertion["field"]] == assertion["value"] for row in timeline)
            )
        elif kind == "full_path_not_applicable":
            self.assertFalse(result["full_path_diagnostics"]["applicable"])
            self.assertEqual(result["full_path_diagnostics"]["reason"], assertion["reason"])
        else:
            self.fail(f"unknown declared expectation assertion: {kind}")

    def _assert_declared_must_not(self, result, rule):
        forbidden_names = {item["name"] for item in result["forbidden_inferences"]}
        inference_mapping = {
            "confirm_quant_identity": "quant_account_identity",
            "infer_quant_turnover_share": "quant_turnover_share",
            "confirm_slow_fund_handoff": "slow_fund_identity",
            "confirm_programmatic_cascade": "quant_account_identity",
        }
        if rule in inference_mapping:
            self.assertIn(inference_mapping[rule], forbidden_names)
        elif rule == "use_full_path_model_in_prefix":
            prefix_keys = self._all_keys(result["prefix_timeline"])
            self.assertNotIn("models", prefix_keys)
            self.assertNotIn("best_model", prefix_keys)
        elif rule == "retain_accelerating_after_sustained_repair":
            self.assertNotEqual(result["prefix_timeline"][-1]["current_dynamics"], "accelerating")
        elif rule == "count_overnight_gap_as_intraday_acceleration":
            self.assertNotIn(
                "accelerating",
                [row["current_dynamics"] for row in result["prefix_timeline"][:3]],
            )
        elif rule == "join_new_episode_to_repaired_prior_episode":
            self.assertNotEqual(result["prefix_timeline"][-1]["episode_structure"], "second_wave")
        elif rule == "rank_curve_identity":
            self.assertIsNone(result["full_path_diagnostics"]["best_model"])
        else:
            self.fail(f"unknown declared must_not rule: {rule}")

    def test_frozen_fixtures_keep_sources_units_validation_and_expectations_separate(self):
        expected_times = self.runtime.expected_a_share_5m_bar_times()

        self.assertEqual(len(self.cases), 5)
        self.assertEqual(set(self.cases), set(self.expectations["cases"]))
        for case_id, case in self.cases.items():
            bars = case["minute_bars"]
            source = case["source"]
            validation = case["validation_summary"]
            self.assertEqual(case["schema_version"], "quant_pressure_replay.v1")
            self.assertEqual(case["case_id"], case_id)
            self.assertEqual(len(bars), 48)
            self.assertEqual([row["datetime"][11:16] for row in bars], expected_times)
            self.assertEqual(source["source_date"], case["trade_date"])
            self.assertEqual(source["timezone"], "Asia/Shanghai")
            self.assertEqual(source["bar_time_semantics"], "interval_end")
            self.assertEqual(source["volume_semantics"], "interval")
            self.assertEqual(source["amount_semantics"], "interval")
            self.assertEqual(validation["bar_count"], 48)
            self.assertEqual(validation["expected_session_grid_status"], "complete")
            self.assertEqual(len(validation["selected_source_rows_sha256"]), 64)
            self.assertEqual(len(validation["normalized_minute_bars_sha256"]), 64)
            self.assertAlmostEqual(
                validation["total_amount"],
                sum(row["amount"] for row in bars),
                places=4,
            )
            self.assertNotIn("current_dynamics", self._all_keys(case))
            self.assertNotIn("episode_structure", self._all_keys(case))
            self.assertNotIn("best_model", self._all_keys(case))
            for row in bars:
                self.assertGreaterEqual(row["high"], max(row["open"], row["close"]))
                self.assertLessEqual(row["low"], min(row["open"], row["close"]))
                if case["instrument"]["type"] == "stock" and row["volume"] > 0:
                    average_price = row["amount"] / row["volume"]
                    self.assertGreaterEqual(average_price, row["low"] - 1e-6)
                    self.assertLessEqual(average_price, row["high"] + 1e-6)
        self.assertEqual(
            self.cases["sz002297_20260527"]["validation_summary"][
                "daily_aggregation_coverage_status"
            ],
            "partial",
        )
        self.assertAlmostEqual(
            self.cases["sz002297_20260527"]["validation_summary"][
                "daily_volume_coverage_ratio"
            ],
            0.9978589509,
            places=10,
        )
        for case_id in set(self.cases).difference({"sz002297_20260527"}):
            self.assertEqual(
                self.cases[case_id]["validation_summary"][
                    "daily_aggregation_coverage_status"
                ],
                "high",
            )

    def test_invalid_ohlc_and_duplicate_time_raise_instead_of_becoming_zero(self):
        bad_ohlc = copy.deepcopy(self.cases["sh603986_20260710"])
        bad_ohlc["minute_bars"][0]["high"] = bad_ohlc["minute_bars"][0]["low"] - 1
        with self.assertRaisesRegex(ValueError, "OHLC"):
            self.runtime.build_quant_pressure_replay(bad_ohlc)

        duplicate = copy.deepcopy(self.cases["sh603986_20260710"])
        duplicate["minute_bars"][1]["datetime"] = duplicate["minute_bars"][0]["datetime"]
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.runtime.build_quant_pressure_replay(duplicate)

    def test_observed_case_requires_validation_summary_and_exposes_tampered_totals(self):
        missing_summary = copy.deepcopy(self.cases["sh603986_20260710"])
        missing_summary.pop("validation_summary")
        with self.assertRaisesRegex(ValueError, "validation_summary"):
            self.runtime.build_quant_pressure_replay(missing_summary)

        tampered = copy.deepcopy(self.cases["sh603986_20260710"])
        tampered["validation_summary"]["total_amount"] += 100000000.0
        result = self.runtime.build_quant_pressure_replay(tampered)
        self.assertEqual(result["data_quality"]["status"], "partial")
        self.assertIn(
            "validation_total_amount_mismatch",
            result["data_quality"]["findings"],
        )

    def test_validation_summary_recomputes_local_hash_and_cross_source_coverage(self):
        swapped = copy.deepcopy(self.cases["sh000001_20260521"])
        swapped["minute_bars"][0]["amount"], swapped["minute_bars"][-1]["amount"] = (
            swapped["minute_bars"][-1]["amount"],
            swapped["minute_bars"][0]["amount"],
        )
        swapped_result = self.runtime.build_quant_pressure_replay(swapped)
        self.assertEqual(swapped_result["data_quality"]["status"], "partial")
        self.assertIn(
            "validation_normalized_minute_bars_hash_mismatch",
            swapped_result["data_quality"]["findings"],
        )

        bad_reference = copy.deepcopy(self.cases["sh603986_20260710"])
        bad_reference["validation_summary"]["daily_reference_ohlc"] = [1, 2, 3, 4]
        bad_reference["validation_summary"]["daily_reference_provider"] = ""
        bad_reference["validation_summary"]["daily_reference_source_url"] = ""
        result = self.runtime.build_quant_pressure_replay(bad_reference)
        self.assertEqual(result["data_quality"]["status"], "partial")
        self.assertFalse(result["data_quality"]["source_metadata_complete"])
        self.assertIn("validation_daily_reference_ohlc_mismatch", result["data_quality"]["findings"])

        bad_coverage = copy.deepcopy(self.cases["sh603986_20260710"])
        bad_coverage["validation_summary"]["daily_amount_coverage_ratio"] = 0.5
        coverage_result = self.runtime.build_quant_pressure_replay(bad_coverage)
        self.assertIn(
            "validation_daily_amount_coverage_mismatch",
            coverage_result["data_quality"]["findings"],
        )

    def test_complete_source_integrity_failure_blocks_amount_derivations(self):
        tampered = copy.deepcopy(self.cases["sh000001_20260521"])
        tampered["minute_bars"][0]["amount"], tampered["minute_bars"][-1]["amount"] = (
            tampered["minute_bars"][-1]["amount"],
            tampered["minute_bars"][0]["amount"],
        )

        result = self.runtime.build_quant_pressure_replay(tampered)
        final = result["prefix_timeline"][-1]

        self.assertTrue(result["data_quality"]["source_integrity_compromised"])
        self.assertEqual(final["evidence_status"], "partial")
        for field in (
            "cumulative_amount_yi",
            "recent_amount_yi",
            "recent_amount_share_of_observed_pct",
            "down_impact_bp_per_yi",
        ):
            self.assertIsNone(final["metrics"][field])
            self.assertEqual(
                final["metric_reasons"][field],
                "source_integrity_unverified",
            )

    def test_incomplete_source_metadata_degrades_evidence_without_erasing_values(self):
        incomplete = copy.deepcopy(self.cases["sh603986_20260710"])
        incomplete["source"]["provider"] = ""

        final = self.runtime.build_quant_pressure_replay(incomplete)["prefix_timeline"][-1]

        self.assertEqual(final["evidence_status"], "partial")
        self.assertIsNotNone(final["metrics"]["cumulative_amount_yi"])
        self.assertIsNotNone(final["metrics"]["cumulative_vwap"])

    def test_legal_zero_amount_prefix_explains_undefined_share(self):
        case = copy.deepcopy(self.cases["sh603986_20260710"])
        case["origin"] = "synthetic"
        case.pop("validation_summary")
        case["minute_bars"][0]["volume"] = 0.0
        case["minute_bars"][0]["amount"] = 0.0

        first = self.runtime.build_quant_pressure_replay(case)["prefix_timeline"][0]

        self.assertEqual(first["metrics"]["cumulative_amount_yi"], 0.0)
        self.assertEqual(first["metrics"]["recent_amount_yi"], 0.0)
        self.assertIsNone(first["metrics"]["recent_amount_share_of_observed_pct"])
        self.assertEqual(
            first["metric_reasons"]["recent_amount_share_of_observed_pct"],
            "amount_zero",
        )

    def test_failed_interval_validation_blocks_amount_metrics_and_invalid_stock_amount_raises(self):
        failed = copy.deepcopy(self.cases["sh603986_20260710"])
        failed["validation_summary"]["interval_semantics_check"] = "failed"
        result = self.runtime.build_quant_pressure_replay(failed)
        final = result["prefix_timeline"][-1]
        self.assertEqual(final["evidence_status"], "partial")
        self.assertIsNone(final["metrics"]["cumulative_vwap"])
        self.assertEqual(
            final["metric_reasons"]["cumulative_vwap"],
            "amount_semantics_unverified",
        )
        self.assertIsNone(final["metrics"]["down_impact_bp_per_yi"])

        zero_amount = copy.deepcopy(self.cases["sh603986_20260710"])
        zero_amount["minute_bars"][0]["amount"] = 0.0
        with self.assertRaisesRegex(ValueError, "amount/volume"):
            self.runtime.build_quant_pressure_replay(zero_amount)

    def test_fixed_session_slots_compress_lunch_but_expose_missing_intraday_bar(self):
        complete = self._build("sh000001_20260521")
        rows = self._timeline_by_time(complete)
        self.assertEqual(rows["2026-05-21 11:30:00"]["trade_slot_index"], 23)
        self.assertEqual(rows["2026-05-21 13:05:00"]["trade_slot_index"], 24)
        self.assertEqual(
            rows["2026-05-21 13:05:00"]["elapsed_trading_minutes"]
            - rows["2026-05-21 11:30:00"]["elapsed_trading_minutes"],
            5,
        )

        missing = copy.deepcopy(self.cases["sh000001_20260521"])
        missing["minute_bars"] = [
            row for row in missing["minute_bars"] if row["datetime"] != "2026-05-21 10:00:00"
        ]
        result = self.runtime.build_quant_pressure_replay(missing)
        row_1005 = self._timeline_by_time(result)["2026-05-21 10:05:00"]
        self.assertIn("2026-05-21 10:00:00", result["data_quality"]["missing_session_bars"])
        self.assertEqual(row_1005["trade_slot_index"], 6)
        self.assertNotEqual(result["data_quality"]["status"], "complete")
        self.assertEqual(row_1005["episode_structure"], "unclear")
        self.assertEqual(
            row_1005["metric_reasons"]["burst_start_time"],
            "intraday_bar_gap",
        )
        self.assertEqual(
            result["full_path_diagnostics"]["time_axis"],
            "fixed_a_share_trade_slot",
        )
        self.assertEqual(result["full_path_diagnostics"]["missing_slot_count"], 1)

        missing_open = copy.deepcopy(self.cases["sh000001_20260521"])
        missing_open["minute_bars"] = missing_open["minute_bars"][1:]
        missing_open_result = self.runtime.build_quant_pressure_replay(missing_open)
        first_observed = missing_open_result["prefix_timeline"][0]
        self.assertIsNone(first_observed["metrics"]["opening_gap_bp"])
        self.assertEqual(first_observed["metric_reasons"]["opening_gap_bp"], "opening_bar_missing")

    def test_unknown_stock_units_return_null_with_reason(self):
        case = copy.deepcopy(self.cases["sh603986_20260710"])
        case["source"]["volume_unit"] = "unknown"
        case["source"]["amount_unit"] = "unknown"
        result = self.runtime.build_quant_pressure_replay(case)
        final = result["prefix_timeline"][-1]

        self.assertIsNone(final["metrics"]["cumulative_vwap"])
        self.assertIn(
            final["metric_reasons"]["cumulative_vwap"],
            {"amount_unit_unverified", "volume_unit_unverified"},
        )
        self.assertIsNone(final["metrics"]["down_impact_bp_per_yi"])
        self.assertEqual(
            final["metric_reasons"]["down_impact_bp_per_yi"],
            "amount_unit_unverified",
        )
        self.assertEqual(final["evidence_status"], "partial")

    def test_missing_amount_is_not_silently_treated_as_zero(self):
        case = copy.deepcopy(self.cases["sh603986_20260710"])
        case["minute_bars"][-2]["amount"] = None
        result = self.runtime.build_quant_pressure_replay(case)
        final = result["prefix_timeline"][-1]

        self.assertIsNone(final["metrics"]["cumulative_vwap"])
        self.assertEqual(final["metric_reasons"]["cumulative_vwap"], "amount_missing")
        self.assertIsNone(final["metrics"]["down_impact_bp_per_yi"])
        self.assertEqual(
            final["metric_reasons"]["down_impact_bp_per_yi"],
            "amount_missing",
        )
        self.assertEqual(final["evidence_status"], "partial")

    def test_cumulative_amount_semantics_are_not_used_as_interval_amount(self):
        case = copy.deepcopy(self.cases["sh603986_20260710"])
        case["source"]["amount_semantics"] = "cumulative"
        result = self.runtime.build_quant_pressure_replay(case)
        final = result["prefix_timeline"][-1]

        self.assertIsNone(final["metrics"]["cumulative_amount_yi"])
        self.assertEqual(
            final["metric_reasons"]["cumulative_amount_yi"],
            "amount_semantics_unverified",
        )
        self.assertIsNone(final["metrics"]["down_impact_bp_per_yi"])
        self.assertEqual(
            final["metric_reasons"]["down_impact_bp_per_yi"],
            "amount_semantics_unverified",
        )

    def test_index_vwap_is_not_applicable_without_downgrading_price_path(self):
        result = self._build("sh000001_20260521")
        final = result["prefix_timeline"][-1]

        self.assertIsNone(final["metrics"]["cumulative_vwap"])
        self.assertEqual(
            final["metric_reasons"]["cumulative_vwap"],
            "index_vwap_not_applicable",
        )
        self.assertIn(
            "index_vwap_not_applicable",
            {item["reason"] for item in final["not_applicable_evidence"]},
        )
        self.assertNotEqual(final["evidence_status"], "insufficient")

    def test_index_missing_amount_is_partial_even_though_vwap_is_not_applicable(self):
        case = copy.deepcopy(self.cases["sh000001_20260521"])
        case["source"]["amount_semantics"] = "unknown"
        result = self.runtime.build_quant_pressure_replay(case)
        final = result["prefix_timeline"][-1]

        self.assertEqual(final["evidence_status"], "partial")
        self.assertEqual(
            final["metric_reasons"]["cumulative_vwap"],
            "index_vwap_not_applicable",
        )
        self.assertEqual(
            final["metric_reasons"]["down_impact_bp_per_yi"],
            "amount_semantics_unverified",
        )

    def test_opening_gap_is_separate_from_intraday_slope(self):
        result = self._build("sh000001_20260604")
        first = result["prefix_timeline"][0]
        final = result["prefix_timeline"][-1]

        self.assertLess(first["metrics"]["opening_gap_bp"], 0)
        self.assertIsNone(first["metrics"]["current_log_slope_bp_per_bar"])
        self.assertEqual(
            first["metric_reasons"]["current_log_slope_bp_per_bar"],
            "insufficient_prefix",
        )
        self.assertNotIn(
            "accelerating",
            [row["current_dynamics"] for row in result["prefix_timeline"][:3]],
        )
        self.assertNotEqual(
            self._timeline_by_time(result)["2026-06-04 13:10:00"]["current_dynamics"],
            "repairing",
        )
        self.assertNotEqual(final["episode_structure"], "second_wave")
        self.assertIsNot(final["handoff_risk_candidate"], True)

    def test_positive_slope_without_prior_pressure_is_not_called_repair(self):
        result = self._timeline_by_time(self._build("sh000001_20260521"))

        self.assertIsNone(result["2026-05-21 10:00:00"]["metrics"]["burst_start_time"])
        self.assertNotEqual(
            result["2026-05-21 10:00:00"]["current_dynamics"],
            "repairing",
        )

    def test_price_limit_constant_path_stays_insufficient_and_has_no_curve_rank(self):
        result = self._build("sz002297_20260527")

        self.assertTrue(
            all(row["evidence_status"] == "insufficient" for row in result["prefix_timeline"])
        )
        self.assertTrue(
            all(row["episode_structure"] == "unclear" for row in result["prefix_timeline"])
        )
        self.assertFalse(result["full_path_diagnostics"]["applicable"])
        self.assertEqual(
            result["full_path_diagnostics"]["reason"],
            "price_limit_path_not_identifiable",
        )
        self.assertIsNone(result["full_path_diagnostics"]["best_model"])

    def test_future_bars_never_rewrite_existing_prefix_rows(self):
        source = self.cases["sh603986_20260710"]
        partial = copy.deepcopy(source)
        partial["minute_bars"] = copy.deepcopy(source["minute_bars"][:18])
        partial_result = self.runtime.build_quant_pressure_replay(partial)

        extended = copy.deepcopy(partial)
        extreme = copy.deepcopy(source["minute_bars"][18])
        extreme["open"] = partial["minute_bars"][-1]["close"]
        extreme["high"] = extreme["open"]
        extreme["low"] = extreme["open"] * 0.90
        extreme["close"] = extreme["low"]
        extreme["amount"] = extreme["close"] * extreme["volume"]
        extended["minute_bars"].append(extreme)
        extended_result = self.runtime.build_quant_pressure_replay(extended)

        self.assertEqual(
            partial_result["prefix_timeline"],
            extended_result["prefix_timeline"][: len(partial_result["prefix_timeline"])],
        )

    def test_each_independent_prefix_equals_the_same_prefix_from_full_case(self):
        source = self.cases["sh603986_20260710"]
        full = self.runtime.build_quant_pressure_replay(copy.deepcopy(source))

        for size in range(1, len(source["minute_bars"]) + 1):
            partial = copy.deepcopy(source)
            partial["minute_bars"] = partial["minute_bars"][:size]
            partial_result = self.runtime.build_quant_pressure_replay(partial)
            self.assertEqual(
                partial_result["prefix_timeline"],
                full["prefix_timeline"][:size],
                f"prefix drift at {size} bars",
            )

    def test_first_change_detection_time_freezes_and_candidate_never_uses_future(self):
        result = self._build("sh603986_20260710")
        detected = [
            row for row in result["prefix_timeline"] if row["metrics"]["first_detected_at"]
        ]

        self.assertTrue(detected)
        first_detected_at = detected[0]["metrics"]["first_detected_at"]
        candidate_change_time = detected[0]["metrics"]["candidate_change_time"]
        self.assertLessEqual(candidate_change_time, first_detected_at)
        self.assertTrue(
            all(row["metrics"]["first_detected_at"] == first_detected_at for row in detected)
        )
        self.assertTrue(
            all(row["metrics"]["candidate_change_time"] == candidate_change_time for row in detected)
        )

    def test_change_point_requires_three_consecutive_candidates_and_exposes_current_support(self):
        result = self._timeline_by_time(self._build("sh603986_20260710"))

        self.assertEqual(
            self.runtime.ResearchPressureConfig().change_confirmation_bars,
            3,
        )
        self.assertIsNone(result["2026-07-10 10:10:00"]["metrics"]["first_detected_at"])
        self.assertIsNone(result["2026-07-10 10:15:00"]["metrics"]["first_detected_at"])
        detected_rows = [
            row for row in result.values() if row["metrics"]["first_detected_at"]
        ]
        self.assertTrue(detected_rows)
        self.assertGreaterEqual(detected_rows[0]["metrics"]["change_confirmation_count"], 3)
        self.assertFalse(result["2026-07-10 15:00:00"]["metrics"]["change_currently_supported"])
        self.assertIsNone(
            result["2026-07-10 15:00:00"]["metrics"]["current_candidate_estimate_time"]
        )

    def test_price_and_amount_scale_leave_bp_vwap_deviation_and_recovery_unchanged(self):
        base_case = copy.deepcopy(self.cases["sh603986_20260710"])
        base_case["origin"] = "synthetic"
        base_case.pop("validation_summary")
        scaled_case = copy.deepcopy(base_case)
        scale = 7.0
        scaled_case["previous_close"] *= scale
        for row in scaled_case["minute_bars"]:
            for key in ("open", "high", "low", "close", "amount"):
                row[key] *= scale

        base = self.runtime.build_quant_pressure_replay(base_case)
        scaled = self.runtime.build_quant_pressure_replay(scaled_case)
        self.assertEqual(
            [row["current_dynamics"] for row in base["prefix_timeline"]],
            [row["current_dynamics"] for row in scaled["prefix_timeline"]],
        )
        for left, right in zip(base["prefix_timeline"], scaled["prefix_timeline"]):
            for key in (
                "current_log_slope_bp_per_bar",
                "vwap_deviation_bp",
                "recovery_ratio_current",
            ):
                if left["metrics"][key] is None:
                    self.assertIsNone(right["metrics"][key])
                else:
                    self.assertAlmostEqual(left["metrics"][key], right["metrics"][key], places=7)
            if left["metrics"]["cumulative_vwap"] is not None:
                self.assertAlmostEqual(
                    left["metrics"]["cumulative_vwap"] * scale,
                    right["metrics"]["cumulative_vwap"],
                    places=5,
                )

    def test_real_case_event_order_and_protection_expectations(self):
        stock = self._build("sh603986_20260710")
        stock_final = stock["prefix_timeline"][-1]
        cooling = next(
            row["metrics"]["first_burst_cooling_confirmed_at"]
            for row in stock["prefix_timeline"]
            if row["metrics"]["first_burst_cooling_confirmed_at"]
        )
        second_wave = next(
            row["metrics"]["second_wave_detected_at"]
            for row in stock["prefix_timeline"]
            if row["metrics"]["second_wave_detected_at"]
        )
        self.assertLess(cooling, second_wave)
        self.assertIn(stock_final["episode_structure"], {"second_wave", "nonrepair_tail"})
        self.assertNotEqual(stock_final["current_dynamics"], "repairing")

        may_21 = self._timeline_by_time(self._build("sh000001_20260521"))
        afternoon_dynamics = [
            row["current_dynamics"]
            for as_of, row in may_21.items()
            if as_of >= "2026-05-21 13:35:00"
        ]
        self.assertTrue({"accelerating", "steady_down"}.intersection(afternoon_dynamics))
        self.assertNotEqual(may_21["2026-05-21 14:40:00"]["current_dynamics"], "repairing")
        self.assertNotEqual(may_21["2026-05-21 14:55:00"]["current_dynamics"], "repairing")

        repair = self._build("sh000001_20260709")["prefix_timeline"][-1]
        self.assertEqual(repair["current_dynamics"], "repairing")
        self.assertFalse(repair["handoff_risk_candidate"])

    def test_new_low_uses_fixed_first_low_and_revokes_durable_repair(self):
        may_21 = self._timeline_by_time(self._build("sh000001_20260521"))
        self.assertLess(
            may_21["2026-05-21 14:55:00"]["metrics"]["recovery_ratio_current"],
            0,
        )

        june_4 = self._timeline_by_time(self._build("sh000001_20260604"))
        invalidated = june_4["2026-06-04 11:25:00"]
        self.assertLess(invalidated["metrics"]["recovery_ratio_current"], 0)
        self.assertFalse(invalidated["metrics"]["repair_confirmed"])
        self.assertEqual(
            invalidated["metrics"]["repair_invalidated_at"],
            "2026-06-04 11:25:00",
        )
        self.assertNotEqual(invalidated["episode_structure"], "first_burst_completed")

    def test_invalidated_repair_can_be_reconfirmed_after_sustained_recovery(self):
        case = copy.deepcopy(self.cases["sh000001_20260604"])
        start_index = next(
            index
            for index, row in enumerate(case["minute_bars"])
            if row["datetime"] == "2026-06-04 11:25:00"
        )
        price = case["minute_bars"][start_index]["close"]
        for row in case["minute_bars"][start_index + 1 :]:
            opening = price
            price *= 1.0015
            row.update(
                {
                    "open": opening,
                    "high": max(opening, price),
                    "low": min(opening, price),
                    "close": price,
                }
            )
        final = self.runtime.build_quant_pressure_replay(case)["prefix_timeline"][-1]

        self.assertEqual(final["current_dynamics"], "repairing")
        self.assertTrue(final["metrics"]["repair_confirmed"])
        self.assertEqual(final["episode_structure"], "first_burst_completed")
        self.assertFalse(final["handoff_risk_candidate"])

    def test_transient_rebound_does_not_clear_confirmed_second_wave_risk(self):
        result = self._build("sh603986_20260710")
        second_wave_rows = [
            row for row in result["prefix_timeline"] if row["episode_structure"] == "second_wave"
        ]
        self.assertTrue(second_wave_rows)
        self.assertTrue(all(row["handoff_risk_candidate"] is True for row in second_wave_rows))

    def test_speed_peak_is_candidate_until_cooling_confirms_it(self):
        result = self._timeline_by_time(self._build("sh603986_20260710"))
        open_burst = result["2026-07-10 10:10:00"]
        self.assertIsNotNone(open_burst["metrics"]["first_burst_speed_peak_candidate_time"])
        self.assertIsNone(open_burst["metrics"]["first_burst_speed_peak_time"])
        self.assertEqual(
            open_burst["metric_reasons"]["first_burst_speed_peak_time"],
            "future_horizon_censored",
        )
        cooled = result["2026-07-10 10:25:00"]
        self.assertIsNotNone(cooled["metrics"]["first_burst_speed_peak_time"])

    def test_displayed_dynamics_slope_is_the_slope_used_by_the_label(self):
        result = self._timeline_by_time(self._build("sh000001_20260521"))
        row = result["2026-05-21 13:35:00"]

        self.assertEqual(row["metrics"]["dynamics_window_bars"], 4)
        self.assertEqual(row["metrics"]["trend_window_bars"], 6)
        self.assertLessEqual(
            row["metrics"]["current_log_slope_bp_per_bar"],
            self.runtime.ResearchPressureConfig().accelerating_slope_bp_per_bar,
        )
        self.assertEqual(row["current_dynamics"], "accelerating")

    def test_full_path_models_share_response_and_never_enter_prefix_timeline(self):
        result = self._build("sh000001_20260521")
        diagnostics = result["full_path_diagnostics"]
        expected_models = {
            "linear",
            "segmented",
            "finite_time_power",
            "sqrt_ellipse_proxy",
            "exponential",
            "gompertz",
            "logarithmic",
        }
        expected_parameter_counts = {
            "linear": 3,
            "segmented": 5,
            "finite_time_power": 5,
            "sqrt_ellipse_proxy": 4,
            "exponential": 4,
            "gompertz": 5,
            "logarithmic": 4,
        }

        self.assertTrue(diagnostics["hindsight_only"])
        self.assertTrue(diagnostics["applicable"])
        self.assertEqual(diagnostics["response"], "log_close_relative_to_first_bar")
        self.assertEqual(diagnostics["time_axis"], "fixed_a_share_trade_slot")
        self.assertEqual(set(diagnostics["models"]), expected_models)
        self.assertIn(diagnostics["best_model"], expected_models)
        self.assertNotIn("models", self._all_keys(result["prefix_timeline"]))
        self.assertNotIn("best_model", self._all_keys(result["prefix_timeline"]))
        for name, payload in diagnostics["models"].items():
            self.assertTrue(payload["applicable"])
            self.assertTrue(math.isfinite(payload["rmse"]))
            self.assertTrue(math.isfinite(payload["aicc"]))
            self.assertIn("boundary_hit", payload)
            self.assertEqual(payload["parameter_count"], expected_parameter_counts[name])
        self.assertEqual(diagnostics["ranking"][0]["delta_aicc"], 0.0)
        self.assertIn(diagnostics["selection_strength"], {"indistinguishable", "weak", "moderate", "strong"})
        self.assertIsInstance(
            diagnostics["models"]["finite_time_power"]["parameters"]["m_near_sqrt"],
            bool,
        )
        self.assertIsInstance(
            diagnostics["models"]["segmented"]["parameters"]["knot_index"],
            int,
        )

    def test_exact_log_linear_path_stops_aicc_ranking_instead_of_selecting_worse_model(self):
        case = copy.deepcopy(self.cases["sh603986_20260710"])
        case["origin"] = "synthetic"
        case.pop("validation_summary")
        case["previous_close"] = 100.0
        for index, row in enumerate(case["minute_bars"]):
            price = 100.0 * math.exp(-0.001 * index)
            row.update(
                {
                    "open": price,
                    "high": price,
                    "low": price,
                    "close": price,
                    "volume": 1000.0,
                    "amount": price * 1000.0,
                }
            )
        diagnostics = self.runtime.build_quant_pressure_replay(case)["full_path_diagnostics"]

        self.assertIsNone(diagnostics["best_model"])
        self.assertEqual(diagnostics["ranking"], [])
        self.assertEqual(diagnostics["ranking_reason"], "zero_residual_model_present")
        self.assertEqual(diagnostics["models"]["linear"]["aicc_reason"], "zero_residual")

    def test_aicc_strength_uses_unrounded_delta_when_display_values_tie(self):
        raw_ranking = [
            {"model": "first", "aicc": 1.0},
            {"model": "second", "aicc": 3.000000004},
        ]

        self.assertEqual(round(raw_ranking[1]["aicc"] - raw_ranking[0]["aicc"], 8), 2.0)
        self.assertEqual(
            self.runtime._aicc_selection_strength(raw_ranking),
            "weak",
        )

    def test_full_path_ranking_uses_unrounded_aicc_when_display_values_tie(self):
        original_round = self.runtime._round_or_none

        def force_eight_decimal_display_tie(value, digits=6):
            if value is not None and digits == 8:
                return 0.0
            return original_round(value, digits)

        with mock.patch.object(
            self.runtime,
            "_round_or_none",
            side_effect=force_eight_decimal_display_tie,
        ):
            diagnostics = self._build("sh603986_20260710")["full_path_diagnostics"]

        self.assertEqual({row["aicc"] for row in diagnostics["ranking"]}, {0.0})
        self.assertEqual(diagnostics["ranking"][0]["model"], "segmented")
        self.assertEqual(diagnostics["best_model"], "segmented")

    def test_every_null_prefix_metric_and_axis_candidate_has_reason(self):
        result = self._build("sh603986_20260710")
        for row in result["prefix_timeline"]:
            for field, value in row["metrics"].items():
                if value is None:
                    self.assertIn(field, row["metric_reasons"], (row["as_of_bar"], field))
            if row["handoff_risk_candidate"] is None:
                self.assertIn("handoff_risk_candidate", row["axis_reasons"])

    def test_expectations_file_drives_acceptance_and_forbidden_inference_contract(self):
        for case_id, expectation in self.expectations["cases"].items():
            result = self._build(case_id)
            for assertion in expectation["must"]:
                self._assert_declared_expectation(result, assertion)
            for rule in expectation["must_not"]:
                self._assert_declared_must_not(result, rule)

        forbidden_names = {
            item["name"] for item in self._build("sh000001_20260521")["forbidden_inferences"]
        }
        self.assertTrue(
            set(self.expectations["global_forbidden_inferences"]).issubset(forbidden_names)
        )

    def test_result_is_deterministic_strict_json_and_does_not_mutate_input(self):
        case = copy.deepcopy(self.cases["sh000001_20260521"])
        before = copy.deepcopy(case)
        first = self.runtime.build_quant_pressure_replay(case)
        second = self.runtime.build_quant_pressure_replay(copy.deepcopy(case))

        self.assertEqual(case, before)
        self.assertEqual(first, second)
        json.dumps(first, ensure_ascii=False, allow_nan=False)
        forbidden_keys = {
            "position",
            "buy_action",
            "sell_action",
            "quant_turnover_share",
            "quant_account_identity",
        }
        self.assertFalse(forbidden_keys.intersection(self._all_keys(first)))
        self.assertEqual(first["config"]["version"], "research.v1.1")
        self.assertEqual(
            first["config"]["material_drawdown_normalization"],
            "raw_bp_not_volatility_adjusted",
        )
        self.assertIn("not_production", first["config"]["calibration_policy"])

    def test_markdown_and_local_fixture_cli_keep_prefix_and_hindsight_separate(self):
        result = self._build("sh000001_20260521")
        markdown = self.runtime.render_quant_pressure_replay_markdown(result)

        self.assertIn("## 前缀时间线", markdown)
        self.assertIn("## 事后曲线诊断", markdown)
        self.assertIn("样本内形状拟合第一", markdown)
        self.assertIn("ΔAICc", markdown)
        self.assertIn("## 缺失与不适用证据", markdown)
        self.assertIn("## 禁止推断", markdown)
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            return_code = self.runtime.main(["--fixtures", str(FIXTURE_ROOT), "--case-id", "sh000001_20260521"])
        self.assertEqual(return_code, 0)
        self.assertIn("sh000001_20260521", stdout.getvalue())

    def test_single_case_finishes_under_one_second(self):
        started = time.perf_counter()
        self._build("sh000001_20260521")
        self.assertLess(time.perf_counter() - started, 1.0)


if __name__ == "__main__":
    unittest.main()
