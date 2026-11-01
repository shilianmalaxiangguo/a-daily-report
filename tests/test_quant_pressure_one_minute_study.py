from __future__ import annotations

import copy
import json
import math
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "quant_pressure_one_minute"
sys.path.insert(0, str(ROOT / "scripts"))


class QuantPressureOneMinuteStudyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from research import quant_pressure_one_minute_study as study

        cls.study = study
        cls.cases = {
            path.stem: json.loads(path.read_text(encoding="utf-8"))
            for path in sorted((FIXTURE_ROOT / "raw").glob("*.json"))
        }

    def test_fixtures_keep_three_exact_cases_and_complete_minute_grid(self):
        expected = self.study.expected_a_share_one_minute_bar_times()

        self.assertEqual(
            set(self.cases),
            {
                "sh000001_20260521",
                "sh600584_20260710",
                "sh603986_20260710",
            },
        )
        self.assertEqual(len(expected), 240)
        self.assertEqual(expected[0], "09:31")
        self.assertEqual(expected[-1], "15:00")
        for case in self.cases.values():
            quality = self.study.validate_one_minute_case(copy.deepcopy(case))
            self.assertEqual(quality["status"], "verified")
            self.assertEqual(quality["bar_count"], 240)
            self.assertEqual(
                [row["datetime"][11:16] for row in case["minute_bars"]],
                expected,
            )
            self.assertEqual(
                case["validation_summary"]["normalized_no_trade_sentinel_times"],
                ["14:59"],
            )
            sentinel = next(
                row for row in case["minute_bars"] if row["datetime"].endswith("14:59:00")
            )
            self.assertEqual(sentinel["amount"], 0.0)

    def test_index_volume_is_unavailable_while_stock_volume_is_shares(self):
        index_case = self.cases["sh000001_20260521"]
        self.assertEqual(index_case["source"]["volume_unit"], "unavailable")
        self.assertTrue(all(row["volume"] is None for row in index_case["minute_bars"]))
        self.assertIn(
            "amount_divided_by_100",
            index_case["validation_summary"]["volume_interpretation"],
        )
        for case_id in ("sh603986_20260710", "sh600584_20260710"):
            case = self.cases[case_id]
            self.assertEqual(case["source"]["volume_unit"], "shares")
            self.assertTrue(all((row["volume"] or 0.0) >= 0 for row in case["minute_bars"]))
            cross = case["validation_summary"]["cross_source"]
            self.assertEqual(cross["common_interval_end_close_match_count"], 240)
            self.assertAlmostEqual(cross["tdx_to_tencent_volume_ratio"], 1.0, places=8)
            self.assertAlmostEqual(cross["tdx_to_tencent_amount_ratio"], 1.0, places=5)

    def test_validator_rejects_identity_prior_close_and_provenance_mutations(self):
        source = self.cases["sh603986_20260710"]
        mutations = []

        def mutate(path, value):
            case = copy.deepcopy(source)
            target = case
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            mutations.append(case)

        mutate(("instrument", "name"), "错误名称")
        mutate(("case_id",), "sh603986_20260709_1m")
        mutate(("previous_close",), 1.0)
        mutate(("source", "provider"), "错误来源")
        mutate(("source", "host"), "127.0.0.1")
        mutate(("source", "port"), 1)
        mutate(("source", "query_date"), "2026-07-10")
        mutate(("source", "timezone"), "UTC")
        mutate(("source", "source_uri"), "tdx://127.0.0.1:1")
        mutate(("source", "source_protocol"), "错误协议")
        mutate(("source", "amount_semantics"), "cumulative")
        mutate(("source", "volume_semantics"), "cumulative")
        mutate(("validation_summary", "raw_source_rows_sha256"), "0" * 64)
        mutate(
            ("validation_summary", "daily_reference_amount"),
            source["validation_summary"]["daily_reference_amount"] * 2,
        )
        mutate(
            ("validation_summary", "daily_amount_coverage_ratio"),
            source["validation_summary"]["daily_amount_coverage_ratio"] * 2,
        )
        mutate(
            (
                "validation_summary",
                "cross_server_validation",
                "secondary_host",
            ),
            "127.0.0.1",
        )
        mutate(
            (
                "validation_summary",
                "cross_server_validation",
                "max_amount_absolute_difference",
            ),
            1_000_000.0,
        )
        mutate(
            (
                "validation_summary",
                "cross_server_validation",
                "primary_total_amount",
            ),
            source["validation_summary"]["total_amount"] * 2,
        )
        mutate(
            (
                "validation_summary",
                "cross_source",
                "tdx_to_tencent_amount_ratio",
            ),
            source["validation_summary"]["cross_source"][
                "tdx_to_tencent_amount_ratio"
            ]
            * 2,
        )

        synchronized_daily = copy.deepcopy(source)
        synchronized_daily_validation = synchronized_daily["validation_summary"]
        synchronized_daily_validation["daily_reference_amount"] *= 2
        synchronized_daily_validation["daily_amount_coverage_ratio"] = (
            synchronized_daily_validation["total_amount"]
            / synchronized_daily_validation["daily_reference_amount"]
        )
        mutations.append(synchronized_daily)

        synchronized_tencent = copy.deepcopy(source)
        synchronized_tencent_cross = synchronized_tencent["validation_summary"][
            "cross_source"
        ]
        synchronized_tencent_cross["final_cumulative_amount"] *= 2
        synchronized_tencent_cross["tdx_to_tencent_amount_ratio"] = (
            synchronized_tencent["validation_summary"]["total_amount"]
            / synchronized_tencent_cross["final_cumulative_amount"]
        )
        mutations.append(synchronized_tencent)

        synchronized_sina = copy.deepcopy(self.cases["sh000001_20260521"])
        synchronized_sina_cross = synchronized_sina["validation_summary"][
            "cross_source"
        ]
        synchronized_sina_cross["five_minute_total_amount"] *= 2
        synchronized_sina_cross["tdx_to_sina_amount_ratio"] = (
            synchronized_sina["validation_summary"]["total_amount"]
            / synchronized_sina_cross["five_minute_total_amount"]
        )
        synchronized_sina_cross["source_date"] = "2026-05-20"
        mutations.append(synchronized_sina)
        for case in mutations:
            with self.subTest(case=case):
                with self.assertRaises(ValueError):
                    self.study.validate_one_minute_case(case)

    def test_window_range_excludes_the_bar_ending_at_the_start_boundary(self):
        index_case = self.cases["sh000001_20260521"]
        index_reviews = {
            row["window_id"]: row
            for row in self.study.build_window_reviews(
                index_case["minute_bars"], previous_close=index_case["previous_close"]
            )
        }
        giga_case = self.cases["sh603986_20260710"]
        giga_reviews = {
            row["window_id"]: row
            for row in self.study.build_window_reviews(
                giga_case["minute_bars"], previous_close=giga_case["previous_close"]
            )
        }
        self.assertAlmostEqual(
            index_reviews["morning_diagnostic"]["window_range_pct"], 0.5091
        )
        self.assertAlmostEqual(
            giga_reviews["late_handling"]["window_range_pct"], 1.9360
        )

    def test_formula_features_keep_curvature_directions_distinct(self):
        xs = [index / 20 for index in range(21)]
        ordinary = self.study.curve_shape_values("ordinary_log", xs, rate=2.0)
        critical = self.study.curve_shape_values(
            "critical_log", xs, critical_scale=1.2
        )
        power_linear = self.study.curve_shape_values(
            "finite_time_power", xs, exponent_m=1.0, critical_scale=1.2
        )
        power_sqrt = self.study.curve_shape_values(
            "finite_time_power", xs, exponent_m=0.5, critical_scale=1.2
        )

        ordinary_second = [
            ordinary[index + 1] - 2 * ordinary[index] + ordinary[index - 1]
            for index in range(1, len(ordinary) - 1)
        ]
        critical_second = [
            critical[index + 1] - 2 * critical[index] + critical[index - 1]
            for index in range(1, len(critical) - 1)
        ]
        sqrt_second = [
            power_sqrt[index + 1] - 2 * power_sqrt[index] + power_sqrt[index - 1]
            for index in range(1, len(power_sqrt) - 1)
        ]
        self.assertTrue(all(value < 0 for value in ordinary_second))
        self.assertTrue(all(value > 0 for value in critical_second))
        self.assertTrue(all(value > 0 for value in sqrt_second))
        for observed, expected in zip(power_linear, [x / 1.2 for x in xs]):
            self.assertAlmostEqual(observed, expected, places=10)

    def test_intraday_surface_reuses_formal_slope_and_curvature_without_early_rounding(self):
        from domains.market_state.market_language_translation import (
            market_language_linear_slope_bp_per_minute,
            market_language_rolling_curvature_bp_per_minute2,
        )

        prefix = self.cases["sh603986_20260710"]["minute_bars"][:60]
        surface = self.study._surface_snapshot(prefix)
        self.assertEqual(
            surface["slope_5m_bp_per_min"],
            market_language_linear_slope_bp_per_minute(prefix, 5),
        )
        self.assertEqual(
            surface["slope_15m_bp_per_min"],
            market_language_linear_slope_bp_per_minute(prefix, 15),
        )
        self.assertEqual(
            surface["curvature_20m_bp_per_min2"],
            market_language_rolling_curvature_bp_per_minute2(prefix, 20),
        )

        edge_rows = [
            {"close": 100.0 * math.exp((-0.050001 * index) / 10000.0)}
            for index in range(16)
        ]
        edge_surface = self.study._surface_snapshot(edge_rows)
        self.assertLess(edge_surface["slope_15m_bp_per_min"], -0.05)
        self.assertEqual(edge_surface["pressure_direction"], "downward")

    def test_small_power_exponent_converges_to_critical_log(self):
        xs = [index / 25 for index in range(26)]
        power = self.study.curve_shape_values(
            "finite_time_power", xs, exponent_m=0.0001, critical_scale=1.25
        )
        critical = self.study.curve_shape_values(
            "critical_log", xs, critical_scale=1.25
        )
        for observed, expected in zip(power, critical):
            self.assertAlmostEqual(observed, expected, places=3)

    def test_model_diagnostics_are_hindsight_only_and_compare_all_families(self):
        result = self.study.build_case_study(
            copy.deepcopy(self.cases["sh603986_20260710"])
        )
        expected_models = {
            "linear",
            "segmented",
            "finite_time_power",
            "sqrt_ellipse_proxy",
            "shifted_ellipse_arc",
            "exponential",
            "gompertz",
            "critical_log",
            "ordinary_log",
        }
        expected_parameter_counts = {
            "linear": 3,
            "segmented": 5,
            "finite_time_power": 5,
            "sqrt_ellipse_proxy": 4,
            "shifted_ellipse_arc": 5,
            "exponential": 4,
            "gompertz": 5,
            "critical_log": 4,
            "ordinary_log": 4,
        }
        for scope in ("full_day", "decline_segment"):
            diagnostics = result["model_diagnostics"][scope]
            self.assertTrue(diagnostics["hindsight_only"])
            self.assertEqual(set(diagnostics["models"]), expected_models)
            self.assertEqual(len(diagnostics["ranking"]), len(expected_models))
            self.assertEqual(diagnostics["ranking"][0]["delta_aicc"], 0.0)
            self.assertIn("residual_lag1", diagnostics["models"]["linear"])
            self.assertEqual(
                {
                    model: payload["parameter_count"]
                    for model, payload in diagnostics["models"].items()
                },
                expected_parameter_counts,
            )
            expected_order = [
                model
                for model, _payload in sorted(
                    diagnostics["models"].items(),
                    key=lambda item: (item[1]["aicc"], item[0]),
                )
            ]
            self.assertEqual(
                [row["model"] for row in diagnostics["ranking"]],
                expected_order,
            )
            for payload in diagnostics["models"].values():
                count = payload["observation_count"]
                parameters = payload["parameter_count"]
                expected_aicc = (
                    count * math.log(payload["residual_variance"])
                    + 2 * parameters
                    + 2
                    * parameters
                    * (parameters + 1)
                    / (count - parameters - 1)
                )
                self.assertAlmostEqual(payload["aicc"], expected_aicc, places=5)

    def test_window_reviews_use_exact_user_window_and_keep_substages(self):
        result = self.study.build_case_study(
            copy.deepcopy(self.cases["sh600584_20260710"])
        )
        reviews = {row["window_id"]: row for row in result["window_reviews"]}
        self.assertEqual(set(reviews), {"opening", "morning_diagnostic", "late_handling"})
        middle = reviews["morning_diagnostic"]
        self.assertEqual(middle["start_time"], "09:45")
        self.assertEqual(middle["end_time"], "10:10")
        self.assertEqual(
            [(row["start_time"], row["end_time"]) for row in middle["subwindows"]],
            [("09:45", "09:50"), ("09:50", "10:10")],
        )
        self.assertEqual(middle["causal_cutoff"], "2026-07-10 10:10:00")

    def test_future_bars_cannot_change_any_window_cutoff_metrics(self):
        case = copy.deepcopy(self.cases["sh603986_20260710"])
        window_cutoffs = {
            "opening": "09:35",
            "morning_diagnostic": "10:10",
            "late_handling": "14:55",
        }
        original = {
            row["window_id"]: row
            for row in self.study.build_window_reviews(
                case["minute_bars"], previous_close=case["previous_close"]
            )
        }
        for window_id, cutoff in window_cutoffs.items():
            mutated_bars = copy.deepcopy(case["minute_bars"])
            for row in mutated_bars:
                if row["datetime"][11:16] > cutoff:
                    row["open"] *= 0.2
                    row["high"] *= 0.2
                    row["low"] *= 0.2
                    row["close"] *= 0.2
                    row["amount"] *= 10
                    if row["volume"] is not None:
                        row["volume"] *= 10
            mutated = {
                row["window_id"]: row
                for row in self.study.build_window_reviews(
                    mutated_bars, previous_close=case["previous_close"]
                )
            }
            with self.subTest(window_id=window_id, cutoff=cutoff):
                self.assertEqual(original[window_id], mutated[window_id])

    def test_morning_window_records_false_candidate_and_live_confirmation(self):
        study = self.study.build_study(FIXTURE_ROOT)
        by_case = {row["case_id"]: row for row in study["cases"]}

        def morning(case_id):
            review = next(
                row
                for row in by_case[case_id]["window_reviews"]
                if row["window_id"] == "morning_diagnostic"
            )
            return review["pressure_timeline"]

        giga = morning("sh603986_20260710_1m")
        self.assertEqual(giga["first_candidate_time"], "09:47")
        self.assertEqual(giga["first_candidate_inside_window_time"], "09:47")
        self.assertEqual(giga["candidate_invalidation_count_inside_window"], 1)
        self.assertEqual(giga["active_pressure_run_start_time"], "10:00")
        self.assertEqual(giga["active_three_minute_confirmation_time"], "10:02")
        self.assertEqual(giga["first_confirmation_quality"], "slope_persistence_only")
        self.assertIsNone(giga["first_directional_follow_through_time"])
        self.assertEqual(giga["active_confirmation_quality"], "directional_follow_through")
        self.assertEqual(giga["active_directional_follow_through_time"], "10:01")

        jcet = morning("sh600584_20260710_1m")
        self.assertEqual(jcet["first_candidate_time"], "10:02")
        self.assertEqual(jcet["active_three_minute_confirmation_time"], "10:04")
        self.assertEqual(jcet["active_directional_follow_through_time"], "10:05")

        index = morning("sh000001_20260521_1m")
        self.assertIsNone(index["first_candidate_time"])
        self.assertEqual(index["candidate_invalidation_count_inside_window"], 0)
        self.assertFalse(index["active_confirmation_at_cutoff"])

        index_late = next(
            row
            for row in by_case["sh000001_20260521_1m"]["window_reviews"]
            if row["window_id"] == "late_handling"
        )["pressure_timeline"]
        self.assertEqual(index_late["first_candidate_time"], "10:17")
        self.assertEqual(index_late["first_three_minute_confirmation_time"], "10:19")
        self.assertEqual(index_late["first_directional_follow_through_time"], "10:24")
        self.assertEqual(index_late["active_pressure_run_start_time"], "13:50")
        self.assertTrue(index_late["active_run_started_before_window"])
        self.assertFalse(index_late["window_covers_first_candidate"])

    def test_confirmed_pressure_tolerates_two_neutral_minutes_only(self):
        def state(direction, close):
            return {"pressure_direction": direction, "close": close}

        two_neutral_minutes = [
            state("downward", 100.00),
            state("downward", 99.99),
            state("downward", 99.98),
            state("balanced", 99.98),
            state("balanced", 99.98),
            state("downward", 99.97),
        ]
        events = self.study._pressure_events_from_states(two_neutral_minutes)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["confirmed_index"], 2)
        self.assertIsNone(events[0]["invalidated_index"])

        third_neutral_minute = two_neutral_minutes[:5] + [
            state("balanced", 99.98)
        ]
        events = self.study._pressure_events_from_states(third_neutral_minute)
        self.assertEqual(events[0]["invalidated_index"], 5)

        opposite_direction = two_neutral_minutes[:3] + [state("upward", 100.01)]
        events = self.study._pressure_events_from_states(opposite_direction)
        self.assertEqual(events[0]["invalidated_index"], 3)

    def test_followups_are_hindsight_only_and_measure_remaining_risk(self):
        study = self.study.build_study(FIXTURE_ROOT)
        by_case = {row["case_id"]: row for row in study["cases"]}
        index_followups = {
            row["window_id"]: row
            for row in by_case["sh000001_20260521_1m"]["window_followups"]
        }
        morning = index_followups["morning_diagnostic"]
        self.assertTrue(morning["hindsight_only"])
        self.assertEqual(morning["objective_decline_completed_pct"], 0.0)
        self.assertEqual(morning["later_trough_time"], "14:53")
        self.assertLess(morning["remaining_drawdown_to_later_trough_pct"], -2.8)

    def test_segmented_winner_reports_opposite_shift_directions(self):
        study = self.study.build_study(FIXTURE_ROOT)
        by_name = {row["instrument"]["name"]: row for row in study["cases"]}
        expected = {
            "兆易创新": ("more_negative", -4.775, -10.746),
            "长电科技": ("less_negative", -26.617, -3.269),
            "上证指数": ("more_negative", -0.832, -2.951),
        }
        for name, (direction, before, after) in expected.items():
            parameters = by_name[name]["model_diagnostics"]["decline_segment"][
                "models"
            ]["segmented"]["parameters"]
            with self.subTest(name=name):
                self.assertEqual(parameters["slope_change_direction"], direction)
                self.assertAlmostEqual(
                    parameters["slope_before_bp_per_min"], before, places=3
                )
                self.assertAlmostEqual(
                    parameters["slope_after_bp_per_min"], after, places=3
                )
        self.assertTrue(
            by_name["长电科技"]["model_diagnostics"]["full_day"]["models"][
                "segmented"
            ]["boundary_hit"]
        )

    def test_one_minute_index_corrects_five_minute_low_label(self):
        result = self.study.build_case_study(
            copy.deepcopy(self.cases["sh000001_20260521"])
        )
        self.assertEqual(result["path_summary"]["day_low"]["time"], "14:53")
        self.assertAlmostEqual(result["path_summary"]["day_low"]["price"], 4074.22)
        self.assertEqual(result["path_summary"]["legacy_five_minute_low_bar_end"], "14:55")

    def test_strategy_research_marks_unobserved_t1_and_t2_dates(self):
        result = self.study.build_study(FIXTURE_ROOT)
        future = result["strategy_research"]["future_observations"]
        by_case = {row["case_id"]: row for row in future}
        for case_id in ("sh603986_20260710_1m", "sh600584_20260710_1m"):
            self.assertEqual(by_case[case_id]["t1_date"], "2026-07-13")
            self.assertEqual(by_case[case_id]["t2_date"], "2026-07-14")
            self.assertEqual(by_case[case_id]["status"], "future_unobserved")

    def test_tushare_capability_separates_stock_index_and_wrapper_limits(self):
        result = self.study.build_study(FIXTURE_ROOT)
        official, current = result["source_availability"][:2]
        self.assertEqual(official["stock_endpoint"], "stk_mins")
        self.assertEqual(official["index_endpoint"], "idx_mins")
        self.assertIn("1min", official["supported_frequencies"])
        self.assertEqual(official["maximum_rows_per_request"], 8000)
        self.assertEqual(official["document_ids"], {"stock": 370, "index": 419})
        self.assertEqual(
            current["current_wrapper_result"], "zero_usable_bars_for_three_cases"
        )
        self.assertIn(
            "index_path_does_not_call_idx_mins", current["wrapper_limits"]
        )

    def test_actual_formula_answer_separates_full_day_egg_from_decline_process(self):
        result = self.study.build_study(FIXTURE_ROOT)
        by_case = {row["case_id"]: row for row in result["cases"]}
        self.assertEqual(
            by_case["sh000001_20260521_1m"]["model_diagnostics"]["full_day"][
                "best_model"
            ],
            "shifted_ellipse_arc",
        )
        self.assertEqual(
            {
                row["model_diagnostics"]["decline_segment"]["best_model"]
                for row in result["cases"]
            },
            {"segmented"},
        )
        self.assertFalse(
            result["formula_synthesis"]["single_universal_formula_supported"]
        )

    def test_window_answer_distinguishes_early_pressure_and_afternoon_onset(self):
        result = self.study.build_study(FIXTURE_ROOT)
        by_case = {row["case_id"]: row for row in result["cases"]}

        def middle(case_id):
            return next(
                row
                for row in by_case[case_id]["window_reviews"]
                if row["window_id"] == "morning_diagnostic"
            )

        giga = middle("sh603986_20260710_1m")
        jcet = middle("sh600584_20260710_1m")
        index = middle("sh000001_20260521_1m")
        self.assertLess(giga["slope_15m_bp_per_min"], 0)
        self.assertLess(jcet["slope_15m_bp_per_min"], 0)
        self.assertEqual(jcet["observed_surface"], "rebound_inside_downward_pressure")
        self.assertGreater(index["slope_15m_bp_per_min"], 0)
        self.assertEqual(index["observed_surface"], "rising_or_repairing_surface")

    def test_afternoon_risk_candidate_keeps_event_failures_and_cutoff_sensitivity(self):
        result = self.study.build_study(FIXTURE_ROOT)
        by_case = {row["case_id"]: row for row in result["cases"]}
        all_case_ids = set(by_case)

        expected_events = {
            "sh603986_20260710_1m": [
                ("13:21", "13:23", "13:25", "14:20"),
                ("14:24", "14:26", "14:25", None),
            ],
            "sh600584_20260710_1m": [
                ("13:19", "13:21", "13:25", "13:59"),
                ("14:03", None, None, "14:05"),
                ("14:06", "14:08", "14:07", "14:19"),
                ("14:30", "14:32", "14:31", None),
            ],
            "sh000001_20260521_1m": [
                ("13:31", "13:33", "13:34", "13:48"),
                ("13:50", "13:52", "13:53", None),
            ],
        }
        for case_id, expected in expected_events.items():
            actual = [
                (
                    row["candidate_time"],
                    row["slope_confirmation_time"],
                    row["directional_follow_through_time"],
                    row["invalidated_time"],
                )
                for row in by_case[case_id]["afternoon_risk_review"]["events"]
            ]
            self.assertEqual(actual, expected)

        synthesis = result["afternoon_risk_synthesis"]
        self.assertEqual(synthesis["candidate_range"], "13:45-14:10")
        self.assertTrue(synthesis["formal_windows_unchanged"])
        self.assertFalse(synthesis["human_attention_required"])
        self.assertFalse(synthesis["intraday_action_allowed"])
        self.assertEqual(synthesis["notification_policy"], "silent")
        self.assertEqual(
            set(synthesis["active_at_observation_start_case_ids"]), all_case_ids
        )
        snapshots = {
            row["cutoff"]: set(row["active_at_cutoff_case_ids"])
            for row in synthesis["cutoff_sensitivity"]
        }
        self.assertEqual(
            snapshots,
            {
                "14:00": {
                    "sh603986_20260710_1m",
                    "sh000001_20260521_1m",
                },
                "14:05": {
                    "sh603986_20260710_1m",
                    "sh000001_20260521_1m",
                },
                "14:10": {
                    "sh603986_20260710_1m",
                    "sh600584_20260710_1m",
                    "sh000001_20260521_1m",
                },
                "14:20": {"sh000001_20260521_1m"},
            },
        )
        for row in synthesis["cutoff_sensitivity"]:
            self.assertEqual(set(row["captured_since_observation_case_ids"]), all_case_ids)
        self.assertEqual(
            [row["branch_id"] for row in synthesis["decision_branches"]],
            ["downward_risk", "upward_trend", "conflicted_or_invalidated"],
        )
        downward_branch = synthesis["decision_branches"][0]
        self.assertEqual(
            downward_branch["required_conditions"],
            [
                "downward_event_has_slope_persistence",
                "directional_price_follow_through_present",
                "corroboration_matches_force_scope",
                "rebound_recovery_failed",
                "event_not_invalidated",
                "existing_exit_conditions_allow_action",
            ],
        )
        self.assertEqual(
            downward_branch["research_handling"],
            "observation_only_risk_reduction_or_exit_candidate",
        )
        self.assertEqual(downward_branch["attention_handling"], "no_intraday_action")

        window_synthesis = result["window_synthesis"]
        self.assertEqual(
            window_synthesis["opening"],
            "opening_observation_not_curve_identification",
        )
        self.assertEqual(
            window_synthesis["morning_diagnostic"],
            "early_pressure_diagnosis_not_afternoon_shock_prediction",
        )
        self.assertEqual(
            window_synthesis["late_handling"],
            "overnight_risk_and_tail_state_not_early_exit",
        )
        attention_policy = window_synthesis["attention_policy"]
        self.assertEqual(
            attention_policy["routine_human_viewing_windows"],
            ["T+1 09:30-09:35", "T+2 14:30-14:55"],
        )
        self.assertFalse(attention_policy["automatic_notification_available"])

    def test_afternoon_review_keeps_cross_lunch_event_and_cutoffs_are_causal(self):
        monotonic_bars = copy.deepcopy(
            self.cases["sh603986_20260710"]["minute_bars"]
        )
        for index, row in enumerate(monotonic_bars):
            row["close"] = 100.0 * math.exp(-0.0002 * index)
        cross_lunch = self.study._afternoon_risk_review(monotonic_bars)
        self.assertEqual(len(cross_lunch["events"]), 1)
        self.assertLess(cross_lunch["events"][0]["candidate_time"], "13:00")
        self.assertIsNone(cross_lunch["events"][0]["invalidated_time"])
        self.assertTrue(cross_lunch["events"][0]["started_before_observation"])
        for row in cross_lunch["cutoff_checks"]:
            self.assertTrue(row["active_complete_evidence_at_cutoff"])
            self.assertTrue(row["captured_complete_evidence_since_observation"])

        for case in self.cases.values():
            full = self.study._afternoon_risk_review(case["minute_bars"])
            for cutoff in ("14:00", "14:05", "14:10", "14:20"):
                prefix = [
                    row
                    for row in case["minute_bars"]
                    if row["datetime"][11:16] <= cutoff
                ]
                truncated = self.study._afternoon_risk_review(prefix)
                full_check = next(
                    row for row in full["cutoff_checks"] if row["cutoff"] == cutoff
                )
                truncated_check = next(
                    row
                    for row in truncated["cutoff_checks"]
                    if row["cutoff"] == cutoff
                )
                self.assertEqual(full_check, truncated_check)

    def test_html_names_three_cases_formulas_windows_and_research_boundary(self):
        result = self.study.build_study(FIXTURE_ROOT)
        html = self.study.render_study_html(result)
        for text in (
            "2026-07-10 兆易创新",
            "2026-07-10 长电科技",
            "2026-05-21 上证指数",
            "09:30-09:35",
            "09:45-10:10",
            "09:45-09:50 T0前哨样本 / 09:50-10:10 T0早盘样本",
            "T0前哨样本",
            "T0早盘样本",
            "14:30-14:55",
            "有限时刻幂律",
            "临界对数",
            "普通对数",
            "T+0",
            "T+1",
            "T+2",
            "2026-07-13",
            "尚未发生",
            "Tushare",
            "stock_mins",
            "stk_mins",
            "idx_mins",
            "单次最多 8000 行",
            "当前账号未开通历史分钟数据",
            "截至截止全日首次候选",
            "重叠斜率连续",
            "候选后价格同向延续",
            "事后验收，不回填当时判断",
            "下降段前后速度（bp/分钟）",
            "MARKET LANGUAGE RESEARCH · REVISION 5",
            "11:30 / 13:01",
            "日报落地：只读研究目标，尚未改写正式动作链",
            "保护样本：先证明它会克制，再讨论是否有用",
            "market_language_translation.v1",
            "09:45-09:50 T0前哨样本 + 09:50-10:10 T0早盘样本",
            "本节三张案例图都只使用压力发生日 T0 的一分钟事实",
            "不能当成 T+1 买入或 T+2 卖出的回测",
            "它不是 T+1 的 B2 执行记录",
            "13:45-14:10 只作日终/replay 研究区间",
            "固定主动查看只安排在 T+1 09:30-09:35 与 T+2 14:30-14:55",
            "目前不会自动提醒",
            "未收到明确提示时 B2 不执行",
            "不要求持续盯盘",
            "不产生临时动作",
            "尾盘突袭涨停",
            "消息驱动",
            "快速修复",
            "截止分钟截面",
            "从 13:45 到四个截止时刻都曾捕获三例",
            "三例不能选出 14:10",
            "三例只复算向下分钟事件",
            "本研究压力口径截至 10:10 未识别",
            "单股独立风险",
        ):
            self.assertIn(text, html)
        self.assertNotIn("量化成交占比已确认", html)
        self.assertNotIn("幂律与 Gompertz 描述候选机制", html)
        self.assertNotIn("5·21 上证在 09:46 短暂出现压力候选", html)
        self.assertNotIn("14:30 后几乎不可能涨停", html)
        self.assertNotIn("14:30 后突然拉涨停的概率非常小", html)
        self.assertNotIn("为什么暂看 14:10", html)
        self.assertNotIn("14:00/14:05 会漏掉长电", html)
        self.assertNotIn("早盘窗口不可能预知午后鸭蛋弧", html)
        self.assertNotIn("13:45-14:10 午后风险复核", html)
        self.assertNotIn(">主执行<", html)
        self.assertIn("不能确认卖方账户身份", html)
        self.assertIn('class="window-scout"', html)
        self.assertIn("黄色是 09:45-09:50 T0 前哨样本", html)
        self.assertNotIn("浅红是 T+1 09:30-09:35 人工处理", html)
        self.assertNotIn("浅绿是 T+2 14:30-14:55 人工处理", html)
        self.assertGreaterEqual(html.count("<svg"), 7)
        self.assertEqual(html.count("<svg"), html.count("</svg>"))
        self.assertGreaterEqual(html.count('class="chart-legend-label"'), 24)
        self.assertNotIn('name="viewport"', html)
        self.assertNotIn("@media (max-width:", html)
        self.assertNotIn("-webkit-overflow-scrolling", html)

    def test_checked_in_html_matches_the_generator(self):
        result = self.study.build_study(FIXTURE_ROOT)
        expected = self.study.render_study_html(result)
        report_path = (
            ROOT
            / "reports"
            / "research"
            / "quant-pressure-replay-study-20260711.html"
        )
        self.assertEqual(report_path.read_text(encoding="utf-8"), expected)


if __name__ == "__main__":
    unittest.main()
