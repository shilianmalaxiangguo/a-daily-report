from __future__ import annotations

import argparse
import copy
import dataclasses
import datetime as dt
import hashlib
import json
import math
import re
import sys
from pathlib import Path


__all__ = [
    "ResearchPressureConfig",
    "build_quant_pressure_replay",
    "expected_a_share_5m_bar_times",
    "main",
    "render_quant_pressure_replay_markdown",
]


INPUT_SCHEMA_VERSION = "quant_pressure_replay.v1"
RESULT_SCHEMA_VERSION = "quant_pressure_replay_result.v1"
_DYNAMICS = {"accelerating", "steady_down", "decelerating", "repairing", "unclear"}
_EPISODES = {
    "first_burst_open",
    "first_burst_completed",
    "nonrepair_tail",
    "second_wave",
    "flash_candidate",
    "unclear",
}
_EVIDENCE = {"sufficient", "partial", "insufficient"}


@dataclasses.dataclass(frozen=True)
class ResearchPressureConfig:
    version: str = "research.v1.1"
    parameter_origin: str = "rough_assumptions_plus_protection_sample_correction"
    calibration_policy: str = "in_sample_research_only_not_production_or_out_of_sample"
    material_drawdown_normalization: str = "raw_bp_not_volatility_adjusted"
    slope_window_bars: int = 6
    dynamics_window_bars: int = 4
    minimum_price_evidence_bars: int = 8
    accelerating_slope_bp_per_bar: float = -6.0
    steady_down_slope_bp_per_bar: float = -4.0
    repairing_slope_bp_per_bar: float = 3.0
    slope_change_bp_per_bar: float = 2.0
    speed_window_bars: int = 3
    burst_speed_bp_per_bar: float = 5.0
    burst_drawdown_bp: float = 18.0
    burst_anchor_lookback_bars: int = 6
    cooling_speed_ratio: float = 0.55
    cooling_confirmation_bars: int = 2
    second_wave_speed_ratio: float = 0.45
    second_wave_confirmation_bars: int = 2
    second_wave_price_tolerance_bp: float = 10.0
    repair_ratio: float = 0.30
    repair_hold_ratio: float = 0.15
    repair_confirmation_bars: int = 2
    episode_reset_repair_bars: int = 3
    episode_reset_recovery_ratio: float = 0.60
    nonrepair_tail_bars: int = 6
    material_episode_drawdown_bp: float = 80.0
    flash_peak_speed_bp_per_bar: float = 20.0
    flash_max_bars: int = 4
    change_min_segment_bars: int = 4
    change_min_improvement_ratio: float = 0.35
    change_min_bic_improvement: float = 2.0
    change_min_slope_delta_bp_per_bar: float = 3.0
    change_confirmation_bars: int = 3
    impact_window_bars: int = 6


def expected_a_share_5m_bar_times():
    morning = _time_range(dt.time(9, 35), dt.time(11, 30), 5)
    afternoon = _time_range(dt.time(13, 5), dt.time(15, 0), 5)
    return [value.strftime("%H:%M") for value in morning + afternoon]


def _time_range(start, end, step_minutes):
    current = dt.datetime.combine(dt.date(2000, 1, 1), start)
    terminal = dt.datetime.combine(dt.date(2000, 1, 1), end)
    values = []
    while current <= terminal:
        values.append(current.time())
        current += dt.timedelta(minutes=step_minutes)
    return values


def _parse_datetime(value, *, field):
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a datetime string")
    try:
        parsed = dt.datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except ValueError as error:
        raise ValueError(f"{field} must use YYYY-MM-DD HH:MM:SS") from error
    return parsed


def _parse_date(value, *, field):
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a date string")
    try:
        return dt.datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as error:
        raise ValueError(f"{field} must use YYYY-MM-DD") from error


def _finite_number(value, *, field, allow_none=False):
    if value is None and allow_none:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field} must be a finite number")
    return number


def _round_or_none(value, digits=6):
    if value is None:
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _prepare_case(case):
    if not isinstance(case, dict):
        raise ValueError("case must be an object")
    source_case = copy.deepcopy(case)
    if source_case.get("schema_version") != INPUT_SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {INPUT_SCHEMA_VERSION}")

    case_id = source_case.get("case_id")
    if not isinstance(case_id, str) or not case_id.strip():
        raise ValueError("case_id must be a non-empty string")
    origin = source_case.get("origin")
    if origin not in {"observed", "synthetic"}:
        raise ValueError("origin must be observed or synthetic")

    instrument = source_case.get("instrument")
    if not isinstance(instrument, dict) or instrument.get("type") not in {"stock", "index"}:
        raise ValueError("instrument.type must be stock or index")
    if not instrument.get("code") or not instrument.get("name"):
        raise ValueError("instrument code and name are required")

    trade_date = _parse_date(source_case.get("trade_date"), field="trade_date")
    if source_case.get("bar_period_minutes") != 5:
        raise ValueError("bar_period_minutes must be 5")
    previous_close = _finite_number(
        source_case.get("previous_close"), field="previous_close", allow_none=True
    )
    if previous_close is not None and previous_close <= 0:
        raise ValueError("previous_close must be positive")
    price_limit_state = source_case.get("price_limit_state")
    if price_limit_state not in {"none", "limit_up", "limit_down", "unknown"}:
        raise ValueError("price_limit_state is invalid")

    source = source_case.get("source")
    if not isinstance(source, dict):
        raise ValueError("source must be an object")
    required_source_fields = {
        "provider",
        "query_date",
        "source_date",
        "timezone",
        "bar_time_semantics",
        "volume_unit",
        "amount_unit",
        "volume_semantics",
        "amount_semantics",
        "source_url",
    }
    missing_source_fields = sorted(required_source_fields.difference(source))
    if missing_source_fields:
        raise ValueError(f"source is missing fields: {', '.join(missing_source_fields)}")
    query_date = _parse_date(source.get("query_date"), field="source.query_date")
    source_date = _parse_date(source.get("source_date"), field="source.source_date")
    if source_date != trade_date:
        raise ValueError("source.source_date must match trade_date")
    if source.get("timezone") != "Asia/Shanghai":
        raise ValueError("source.timezone must be Asia/Shanghai")
    if source.get("bar_time_semantics") != "interval_end":
        raise ValueError("source.bar_time_semantics must be interval_end")
    if source.get("volume_unit") not in {"shares", "lots", "unknown"}:
        raise ValueError("source.volume_unit is invalid")
    if source.get("amount_unit") not in {"CNY", "CNY_10K", "unknown"}:
        raise ValueError("source.amount_unit is invalid")
    if source.get("volume_semantics") not in {"interval", "cumulative", "unknown"}:
        raise ValueError("source.volume_semantics is invalid")
    if source.get("amount_semantics") not in {"interval", "cumulative", "unknown"}:
        raise ValueError("source.amount_semantics is invalid")
    source_metadata_findings = []
    if not isinstance(source.get("provider"), str) or not source.get("provider").strip():
        source_metadata_findings.append("source_provider_missing")
    if (
        not isinstance(source.get("source_url"), str)
        or not source.get("source_url").startswith(("https://", "http://"))
    ):
        source_metadata_findings.append("source_url_invalid")
    if query_date < source_date:
        source_metadata_findings.append("source_query_date_before_source_date")

    expected_times = expected_a_share_5m_bar_times()
    slot_by_time = {value: index for index, value in enumerate(expected_times)}
    raw_bars = source_case.get("minute_bars")
    if not isinstance(raw_bars, list) or not raw_bars:
        raise ValueError("minute_bars must be a non-empty list")
    prepared_bars = []
    seen_datetimes = set()
    previous_datetime = None
    for index, raw_bar in enumerate(raw_bars):
        if not isinstance(raw_bar, dict):
            raise ValueError(f"minute_bars[{index}] must be an object")
        parsed_datetime = _parse_datetime(
            raw_bar.get("datetime"), field=f"minute_bars[{index}].datetime"
        )
        datetime_text = parsed_datetime.strftime("%Y-%m-%d %H:%M:%S")
        if datetime_text in seen_datetimes:
            raise ValueError(f"duplicate minute bar datetime: {datetime_text}")
        seen_datetimes.add(datetime_text)
        if parsed_datetime.date() != trade_date:
            raise ValueError(f"minute bar date does not match trade_date: {datetime_text}")
        time_text = parsed_datetime.strftime("%H:%M")
        if time_text not in slot_by_time or parsed_datetime.second != 0:
            raise ValueError(f"minute bar is outside the expected A-share session: {datetime_text}")
        if previous_datetime is not None and parsed_datetime <= previous_datetime:
            raise ValueError("minute_bars must be strictly increasing")
        previous_datetime = parsed_datetime

        open_price = _finite_number(raw_bar.get("open"), field=f"minute_bars[{index}].open")
        high_price = _finite_number(raw_bar.get("high"), field=f"minute_bars[{index}].high")
        low_price = _finite_number(raw_bar.get("low"), field=f"minute_bars[{index}].low")
        close_price = _finite_number(raw_bar.get("close"), field=f"minute_bars[{index}].close")
        volume = _finite_number(
            raw_bar.get("volume"), field=f"minute_bars[{index}].volume", allow_none=True
        )
        amount = _finite_number(
            raw_bar.get("amount"), field=f"minute_bars[{index}].amount", allow_none=True
        )
        if min(open_price, high_price, low_price, close_price) <= 0:
            raise ValueError(f"minute_bars[{index}] prices must be positive")
        if high_price < max(open_price, close_price) or low_price > min(open_price, close_price):
            raise ValueError(f"minute_bars[{index}] has inconsistent OHLC")
        if high_price < low_price:
            raise ValueError(f"minute_bars[{index}] has inconsistent OHLC range")
        if volume is not None and volume < 0:
            raise ValueError(f"minute_bars[{index}].volume must be non-negative")
        if amount is not None and amount < 0:
            raise ValueError(f"minute_bars[{index}].amount must be non-negative")
        if (
            instrument.get("type") == "stock"
            and source.get("volume_unit") == "shares"
            and source.get("amount_unit") == "CNY"
            and source.get("volume_semantics") == "interval"
            and source.get("amount_semantics") == "interval"
            and volume is not None
            and amount is not None
        ):
            if (volume > 0 and amount <= 0) or (volume <= 0 and amount > 0):
                raise ValueError(f"minute_bars[{index}] amount/volume is inconsistent")
            if volume > 0:
                average_price = amount / volume
                if average_price < low_price - 1e-6 or average_price > high_price + 1e-6:
                    raise ValueError(f"minute_bars[{index}] amount/volume price is outside OHLC")
        prepared_bars.append(
            {
                "datetime": datetime_text,
                "slot": slot_by_time[time_text],
                "open": open_price,
                "high": high_price,
                "low": low_price,
                "close": close_price,
                "volume": volume,
                "amount": amount,
            }
        )

    observed_times = {bar["datetime"][11:16] for bar in prepared_bars}
    missing_times = [
        f"{trade_date.isoformat()} {time_text}:00"
        for time_text in expected_times
        if time_text not in observed_times
    ]
    constant_path = max(bar["close"] for bar in prepared_bars) == min(
        bar["close"] for bar in prepared_bars
    )
    price_path_identifiable = not (
        constant_path and price_limit_state in {"limit_up", "limit_down"}
    )
    validation_summary = source_case.get("validation_summary")
    if origin == "observed" and not isinstance(validation_summary, dict):
        raise ValueError("observed case requires validation_summary")
    validation_summary = validation_summary or {}
    required_validation_fields = {
        "bar_count",
        "first_bar",
        "last_bar",
        "day_open",
        "day_high",
        "day_low",
        "day_close",
        "total_volume",
        "total_amount",
        "selected_source_rows_sha256",
        "normalized_minute_bars_sha256",
        "interval_semantics_check",
        "stock_amount_volume_price_check",
        "expected_session_grid_status",
        "daily_reference_provider",
        "daily_reference_source_url",
        "daily_reference_ohlc",
        "daily_reference_ohlc_tolerance",
        "daily_reference_volume_shares",
        "daily_reference_amount",
        "daily_volume_coverage_ratio",
        "daily_amount_coverage_ratio",
        "daily_aggregation_coverage_status",
    }
    if origin == "observed":
        missing_validation_fields = sorted(required_validation_fields.difference(validation_summary))
        if missing_validation_fields:
            raise ValueError(
                "validation_summary is missing fields: " + ", ".join(missing_validation_fields)
            )

    def summary_number_matches(field, actual, *, absolute_tolerance=1e-6):
        expected = validation_summary.get(field)
        return (
            isinstance(expected, (int, float))
            and not isinstance(expected, bool)
            and math.isfinite(float(expected))
            and math.isclose(
                float(expected),
                float(actual),
                rel_tol=1e-10,
                abs_tol=absolute_tolerance,
            )
        )

    validation_findings = []
    if validation_summary:
        exact_checks = {
            "bar_count": len(prepared_bars),
            "first_bar": prepared_bars[0]["datetime"],
            "last_bar": prepared_bars[-1]["datetime"],
        }
        for field, actual in exact_checks.items():
            if validation_summary.get(field) != actual:
                validation_findings.append(f"validation_{field}_mismatch")
        numeric_checks = {
            "day_open": prepared_bars[0]["open"],
            "day_high": max(bar["high"] for bar in prepared_bars),
            "day_low": min(bar["low"] for bar in prepared_bars),
            "day_close": prepared_bars[-1]["close"],
            "total_volume": sum((bar["volume"] or 0.0) for bar in prepared_bars),
            "total_amount": sum((bar["amount"] or 0.0) for bar in prepared_bars),
        }
        for field, actual in numeric_checks.items():
            tolerance = 1e-3 if field in {"total_volume", "total_amount"} else 1e-6
            if not summary_number_matches(field, actual, absolute_tolerance=tolerance):
                validation_findings.append(f"validation_{field}_mismatch")
        source_hash = validation_summary.get("selected_source_rows_sha256")
        if not isinstance(source_hash, str) or re.fullmatch(r"[0-9a-f]{64}", source_hash) is None:
            validation_findings.append("validation_source_hash_invalid")
        normalized_hash = hashlib.sha256(
            json.dumps(
                source_case.get("minute_bars"),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        if validation_summary.get("normalized_minute_bars_sha256") != normalized_hash:
            validation_findings.append("validation_normalized_minute_bars_hash_mismatch")
        expected_grid_status = "complete" if not missing_times else "partial"
        if validation_summary.get("expected_session_grid_status") != expected_grid_status:
            validation_findings.append("validation_session_grid_status_mismatch")
        coverage_status = validation_summary.get("daily_aggregation_coverage_status")
        if coverage_status not in {"high", "partial", "unknown"}:
            validation_findings.append("validation_daily_coverage_status_invalid")
        for field in ("daily_volume_coverage_ratio", "daily_amount_coverage_ratio"):
            value = validation_summary.get(field)
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                or not 0.0 <= float(value) <= 1.000001
            ):
                validation_findings.append(f"validation_{field}_invalid")
        reference_provider = validation_summary.get("daily_reference_provider")
        reference_url = validation_summary.get("daily_reference_source_url")
        if not isinstance(reference_provider, str) or not reference_provider.strip():
            source_metadata_findings.append("daily_reference_provider_missing")
        if not isinstance(reference_url, str) or not reference_url.startswith(("https://", "http://")):
            source_metadata_findings.append("daily_reference_source_url_invalid")
        reference_ohlc = validation_summary.get("daily_reference_ohlc")
        tolerance = validation_summary.get("daily_reference_ohlc_tolerance")
        actual_ohlc = [
            prepared_bars[0]["open"],
            max(bar["high"] for bar in prepared_bars),
            min(bar["low"] for bar in prepared_bars),
            prepared_bars[-1]["close"],
        ]
        valid_reference_ohlc = (
            isinstance(reference_ohlc, list)
            and len(reference_ohlc) == 4
            and all(
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and math.isfinite(float(value))
                for value in reference_ohlc
            )
            and isinstance(tolerance, (int, float))
            and not isinstance(tolerance, bool)
            and math.isfinite(float(tolerance))
            and float(tolerance) >= 0
        )
        if not valid_reference_ohlc or any(
            abs(float(reference) - actual) > float(tolerance)
            for reference, actual in zip(reference_ohlc or [], actual_ohlc)
        ):
            validation_findings.append("validation_daily_reference_ohlc_mismatch")

        reference_volume = validation_summary.get("daily_reference_volume_shares")
        stored_volume_ratio = validation_summary.get("daily_volume_coverage_ratio")
        calculated_volume_ratio = None
        if (
            isinstance(reference_volume, (int, float))
            and not isinstance(reference_volume, bool)
            and math.isfinite(float(reference_volume))
            and float(reference_volume) > 0
        ):
            calculated_volume_ratio = numeric_checks["total_volume"] / float(reference_volume)
        if (
            calculated_volume_ratio is None
            or not isinstance(stored_volume_ratio, (int, float))
            or isinstance(stored_volume_ratio, bool)
            or not math.isclose(
                float(stored_volume_ratio), calculated_volume_ratio, rel_tol=1e-9, abs_tol=1e-9
            )
        ):
            validation_findings.append("validation_daily_volume_coverage_mismatch")

        reference_amount = validation_summary.get("daily_reference_amount")
        stored_amount_ratio = validation_summary.get("daily_amount_coverage_ratio")
        calculated_amount_ratio = None
        if reference_amount is not None:
            if (
                isinstance(reference_amount, (int, float))
                and not isinstance(reference_amount, bool)
                and math.isfinite(float(reference_amount))
                and float(reference_amount) > 0
            ):
                calculated_amount_ratio = numeric_checks["total_amount"] / float(reference_amount)
            if (
                calculated_amount_ratio is None
                or not isinstance(stored_amount_ratio, (int, float))
                or isinstance(stored_amount_ratio, bool)
                or not math.isclose(
                    float(stored_amount_ratio), calculated_amount_ratio, rel_tol=1e-9, abs_tol=1e-9
                )
            ):
                validation_findings.append("validation_daily_amount_coverage_mismatch")
        elif stored_amount_ratio is not None:
            validation_findings.append("validation_daily_amount_coverage_mismatch")

        comparable_ratios = [
            ratio for ratio in (calculated_volume_ratio, calculated_amount_ratio) if ratio is not None
        ]
        expected_coverage_status = (
            "high" if comparable_ratios and min(comparable_ratios) >= 0.9999 else "partial"
        )
        if validation_summary.get("daily_aggregation_coverage_status") != expected_coverage_status:
            validation_findings.append("validation_daily_coverage_status_mismatch")
        if validation_summary.get("interval_semantics_check") != "passed_non_cumulative_bars":
            validation_findings.append("validation_interval_semantics_failed")
        expected_stock_check = (
            "passed" if instrument.get("type") == "stock" else "not_applicable_to_index_level"
        )
        if validation_summary.get("stock_amount_volume_price_check") != expected_stock_check:
            validation_findings.append("validation_stock_amount_volume_price_failed")
    validation_matches = not validation_findings
    source_integrity_compromised = bool(
        origin == "observed"
        and not missing_times
        and len(prepared_bars) == len(expected_times)
        and validation_findings
    )
    quality_findings = list(source_metadata_findings)
    if missing_times:
        quality_findings.append("missing_session_bars")
    quality_findings.extend(validation_findings)
    daily_coverage_status = validation_summary.get("daily_aggregation_coverage_status", "unknown")
    if daily_coverage_status == "partial":
        quality_findings.append("daily_aggregation_partial")
    data_quality = {
        "status": "complete" if not quality_findings else "partial",
        "expected_bar_count": len(expected_times),
        "observed_bar_count": len(prepared_bars),
        "missing_session_bars": missing_times,
        "unexpected_session_bars": [],
        "source_metadata_complete": not source_metadata_findings,
        "validation_summary_matches_input": validation_matches,
        "source_integrity_compromised": source_integrity_compromised,
        "price_path_identifiable": price_path_identifiable,
        "daily_aggregation_coverage_status": daily_coverage_status,
        "findings": quality_findings,
    }
    analysis_source = copy.deepcopy(source)
    if (
        origin == "observed"
        and validation_summary.get("interval_semantics_check") != "passed_non_cumulative_bars"
    ):
        analysis_source["volume_semantics"] = "unknown"
        analysis_source["amount_semantics"] = "unknown"
    if (
        origin == "observed"
        and instrument.get("type") == "stock"
        and validation_summary.get("stock_amount_volume_price_check") != "passed"
    ):
        analysis_source["volume_unit"] = "unknown"
        analysis_source["amount_unit"] = "unknown"
    return {
        "case_id": case_id,
        "origin": origin,
        "instrument": copy.deepcopy(instrument),
        "trade_date": trade_date.isoformat(),
        "previous_close": previous_close,
        "price_limit_state": price_limit_state,
        "source": analysis_source,
        "source_integrity_compromised": source_integrity_compromised,
        "bars": prepared_bars,
        "data_quality": data_quality,
    }


def _linear_fit(xs, ys):
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    denominator = sum((value - mean_x) ** 2 for value in xs)
    if denominator <= 1e-18:
        return None
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / denominator
    intercept = mean_y - slope * mean_x
    predictions = [intercept + slope * x for x in xs]
    sse = sum((actual - predicted) ** 2 for actual, predicted in zip(ys, predictions))
    return {"intercept": intercept, "slope": slope, "predictions": predictions, "sse": sse}


def _log_slope_bp(bars):
    if len(bars) < 2:
        return None
    fit = _linear_fit(
        [float(bar["slot"]) for bar in bars],
        [math.log(bar["close"]) for bar in bars],
    )
    return None if fit is None else fit["slope"] * 10000.0


def _rolling_slope_pair(bars, window):
    current = _log_slope_bp(bars[-window:]) if len(bars) >= window else None
    previous = _log_slope_bp(bars[-2 * window : -window]) if len(bars) >= 2 * window else None
    return current, previous


def _piecewise_candidate(bars, config):
    minimum = config.change_min_segment_bars
    if len(bars) < minimum * 2:
        return None
    xs = [float(bar["slot"]) for bar in bars]
    ys = [math.log(bar["close"]) for bar in bars]
    baseline = _linear_fit(xs, ys)
    if baseline is None or baseline["sse"] <= 1e-18:
        return None
    best = None
    sample_size = len(bars)
    baseline_bic = sample_size * math.log(baseline["sse"] / sample_size) + 3 * math.log(
        sample_size
    )
    for split in range(minimum, len(bars) - minimum + 1):
        knot = xs[split]
        fit = _fit_features(
            [[1.0, value, max(0.0, value - knot)] for value in xs],
            ys,
        )
        if fit is None:
            continue
        before_slope = fit["coefficients"][1]
        after_slope = before_slope + fit["coefficients"][2]
        slope_delta_bp = (after_slope - before_slope) * 10000.0
        candidate = {
            "index": split,
            "time": bars[split]["datetime"],
            "sse": fit["sse"],
            "before_slope_bp_per_bar": before_slope * 10000.0,
            "after_slope_bp_per_bar": after_slope * 10000.0,
            "slope_delta_bp_per_bar": slope_delta_bp,
            "bic": sample_size * math.log(max(fit["sse"], 1e-30) / sample_size)
            + 5 * math.log(sample_size),
        }
        if best is None or (candidate["bic"], candidate["index"]) < (
            best["bic"],
            best["index"],
        ):
            best = candidate
    if best is None:
        return None
    improvement = (baseline["sse"] - best["sse"]) / baseline["sse"]
    bic_improvement = baseline_bic - best["bic"]
    if improvement < config.change_min_improvement_ratio:
        return None
    if abs(best["slope_delta_bp_per_bar"]) < config.change_min_slope_delta_bp_per_bar:
        return None
    if bic_improvement < config.change_min_bic_improvement:
        return None
    best["improvement_ratio"] = improvement
    best["bic_improvement"] = bic_improvement
    return best


def _bar_returns_bp(bars):
    values = [None]
    for previous, current in zip(bars, bars[1:]):
        slot_delta = current["slot"] - previous["slot"]
        if slot_delta <= 0:
            values.append(None)
        else:
            values.append(math.log(current["close"] / previous["close"]) * 10000.0 / slot_delta)
    return values


def _episode_state(bars, config):
    empty = {
        "event_unavailable_reason": None,
        "burst_start_time": None,
        "first_burst_speed_peak_candidate_time": None,
        "first_burst_speed_peak_candidate_bp_per_bar": None,
        "first_burst_speed_peak_time": None,
        "first_burst_speed_peak_bp_per_bar": None,
        "first_burst_cooling_confirmed_at": None,
        "second_wave_detected_at": None,
        "first_burst_anchor_price": None,
        "first_burst_low_price": None,
        "episode_low_price_current": None,
        "recovery_ratio_current": None,
        "recovery_bars_current": 0,
        "repair_confirmed": False,
        "repair_invalidated_at": None,
        "nonrepair_bars_after_cooling": 0,
        "burst_duration_bars": None,
        "episode_drawdown_bp_current": None,
    }
    if any(current["slot"] != previous["slot"] + 1 for previous, current in zip(bars, bars[1:])):
        return {**empty, "event_unavailable_reason": "intraday_bar_gap"}
    if len(bars) < config.speed_window_bars + 1:
        return {**empty, "event_unavailable_reason": "insufficient_prefix"}

    returns = _bar_returns_bp(bars)
    speeds = [None] * len(bars)
    for index in range(config.speed_window_bars, len(bars)):
        window = returns[index - config.speed_window_bars + 1 : index + 1]
        if any(value is None for value in window):
            continue
        speeds[index] = max(0.0, -sum(window) / len(window))

    burst_start = None
    anchor_price = None
    peak_speed = None
    peak_index = None
    cooling_run = 0
    cooling_index = None
    first_low = None
    episode_low = None
    repair_run = 0
    repair_confirmed = False
    repair_invalidated_at = None
    durable_repair_index = None
    durable_repair_snapshot = None
    second_wave_run = 0
    second_wave_index = None
    for index, speed in enumerate(speeds):
        if speed is None:
            continue
        if burst_start is None:
            anchor_slice_start = max(0, index - config.burst_anchor_lookback_bars)
            anchor = max(bar["close"] for bar in bars[anchor_slice_start : index + 1])
            drawdown_bp = math.log(bars[index]["close"] / anchor) * 10000.0
            if speed >= config.burst_speed_bp_per_bar and drawdown_bp <= -config.burst_drawdown_bp:
                burst_start = max(0, index - config.speed_window_bars + 1)
                anchor_slice_start = max(0, burst_start - config.burst_anchor_lookback_bars)
                anchor_price = max(
                    bar["close"] for bar in bars[anchor_slice_start : burst_start + 1]
                )
                peak_speed = speed
                peak_index = index
            continue

        if cooling_index is None:
            if speed > (peak_speed or 0.0) + 1e-12:
                peak_speed = speed
                peak_index = index
                cooling_run = 0
            elif index > peak_index and speed <= max(
                config.burst_speed_bp_per_bar * 0.8,
                (peak_speed or 0.0) * config.cooling_speed_ratio,
            ):
                cooling_run += 1
                if cooling_run >= config.cooling_confirmation_bars:
                    cooling_index = index
                    first_low = min(
                        bar["close"] for bar in bars[burst_start : cooling_index + 1]
                    )
                    episode_low = first_low
            else:
                cooling_run = 0
            continue

        current_close = bars[index]["close"]
        made_new_low = current_close < (episode_low or current_close) * (1.0 - 1e-10)
        if made_new_low:
            episode_low = current_close
            if repair_confirmed and repair_invalidated_at is None:
                repair_invalidated_at = bars[index]["datetime"]
            repair_run = 0
            repair_confirmed = False

        recovery_denominator = (anchor_price or current_close) - (first_low or current_close)
        recovery_ratio = (
            (current_close - (first_low or current_close)) / recovery_denominator
            if recovery_denominator > 1e-12
            else None
        )
        recent_start = max(0, index - config.dynamics_window_bars + 1)
        recent_slope = _log_slope_bp(bars[recent_start : index + 1])
        if (
            recovery_ratio is not None
            and recovery_ratio >= config.repair_ratio
            and recent_slope is not None
            and recent_slope >= config.repairing_slope_bp_per_bar
        ):
            repair_run += 1
            if repair_run >= config.repair_confirmation_bars:
                repair_confirmed = True
        elif not repair_confirmed and recovery_ratio is not None and recovery_ratio < config.repair_hold_ratio:
            repair_run = 0

        if (
            durable_repair_index is None
            and repair_confirmed
            and repair_run >= config.episode_reset_repair_bars
            and recovery_ratio is not None
            and recovery_ratio >= config.episode_reset_recovery_ratio
        ):
            durable_repair_index = index
            durable_repair_snapshot = {
                "event_unavailable_reason": None,
                "burst_start_time": bars[burst_start]["datetime"],
                "first_burst_speed_peak_candidate_time": bars[peak_index]["datetime"],
                "first_burst_speed_peak_candidate_bp_per_bar": peak_speed,
                "first_burst_speed_peak_time": bars[peak_index]["datetime"],
                "first_burst_speed_peak_bp_per_bar": peak_speed,
                "first_burst_cooling_confirmed_at": bars[cooling_index]["datetime"],
                "second_wave_detected_at": None,
                "first_burst_anchor_price": anchor_price,
                "first_burst_low_price": first_low,
                "episode_low_price_current": episode_low,
                "recovery_ratio_current": recovery_ratio,
                "recovery_bars_current": repair_run,
                "repair_confirmed": True,
                "repair_invalidated_at": None,
                "nonrepair_bars_after_cooling": 0,
                "burst_duration_bars": bars[cooling_index]["slot"] - bars[burst_start]["slot"] + 1,
                "episode_drawdown_bp_current": max(
                    0.0, -math.log((episode_low or anchor_price) / anchor_price) * 10000.0
                ),
            }

        second_wave_speed = max(
            config.burst_speed_bp_per_bar,
            (peak_speed or 0.0) * config.second_wave_speed_ratio,
        )
        price_ceiling = (first_low or current_close) * (
            1.0 + config.second_wave_price_tolerance_bp / 10000.0
        )
        episode_drawdown_bp = max(
            0.0,
            -math.log((episode_low or current_close) / (anchor_price or current_close))
            * 10000.0,
        )
        if (
            not repair_confirmed
            and episode_drawdown_bp >= config.material_episode_drawdown_bp
            and speed >= second_wave_speed
            and current_close <= price_ceiling
        ):
            second_wave_run += 1
            if second_wave_index is None and second_wave_run >= config.second_wave_confirmation_bars:
                second_wave_index = index
        else:
            second_wave_run = 0

    if burst_start is None:
        return {**empty, "event_unavailable_reason": "episode_not_completed"}

    if durable_repair_snapshot is not None:
        later_bars = bars[durable_repair_index + 1 :]
        if later_bars:
            later_event = _episode_state(later_bars, config)
            if later_event.get("burst_start_time") is not None:
                return later_event
        first_low = durable_repair_snapshot["first_burst_low_price"]
        anchor_price = durable_repair_snapshot["first_burst_anchor_price"]
        final_close = bars[-1]["close"]
        later_low = min([first_low] + [bar["close"] for bar in later_bars])
        invalidating_bar = next(
            (bar for bar in later_bars if bar["close"] < first_low * (1.0 - 1e-10)),
            None,
        )
        denominator = anchor_price - first_low
        durable_repair_snapshot["recovery_ratio_current"] = (
            (final_close - first_low) / denominator if denominator > 1e-12 else None
        )
        durable_repair_snapshot["episode_low_price_current"] = later_low
        durable_repair_snapshot["episode_drawdown_bp_current"] = max(
            0.0, -math.log(later_low / anchor_price) * 10000.0
        )
        if invalidating_bar is not None:
            invalidating_index = next(
                index
                for index, bar in enumerate(bars)
                if bar["datetime"] == invalidating_bar["datetime"]
            )
            reconfirmation_run = 0
            reconfirmed = False
            running_low = first_low
            for index in range(invalidating_index, len(bars)):
                current_close = bars[index]["close"]
                if current_close < running_low * (1.0 - 1e-10):
                    running_low = current_close
                    reconfirmation_run = 0
                    reconfirmed = False
                recovery_ratio = (
                    (current_close - first_low) / denominator if denominator > 1e-12 else None
                )
                recent_start = max(0, index - config.dynamics_window_bars + 1)
                recent_slope = _log_slope_bp(bars[recent_start : index + 1])
                if (
                    recovery_ratio is not None
                    and recovery_ratio >= config.repair_ratio
                    and recent_slope is not None
                    and recent_slope >= config.repairing_slope_bp_per_bar
                ):
                    reconfirmation_run += 1
                    if reconfirmation_run >= config.repair_confirmation_bars:
                        reconfirmed = True
                elif (
                    not reconfirmed
                    and recovery_ratio is not None
                    and recovery_ratio < config.repair_hold_ratio
                ):
                    reconfirmation_run = 0
            durable_repair_snapshot["repair_confirmed"] = reconfirmed
            durable_repair_snapshot["repair_invalidated_at"] = invalidating_bar["datetime"]
            durable_repair_snapshot["recovery_bars_current"] = reconfirmation_run
            durable_repair_snapshot["episode_low_price_current"] = running_low
            durable_repair_snapshot["nonrepair_bars_after_cooling"] = (
                0
                if reconfirmed
                else bars[-1]["slot"]
                - next(
                    bar["slot"]
                    for bar in bars
                    if bar["datetime"]
                    == durable_repair_snapshot["first_burst_cooling_confirmed_at"]
                )
            )
        return durable_repair_snapshot

    final_close = bars[-1]["close"]
    recovery_denominator = (anchor_price or final_close) - (first_low or final_close)
    recovery_ratio = (
        (final_close - (first_low or final_close)) / recovery_denominator
        if cooling_index is not None and recovery_denominator > 1e-12
        else None
    )
    return {
        "event_unavailable_reason": None,
        "burst_start_time": bars[burst_start]["datetime"],
        "first_burst_speed_peak_candidate_time": bars[peak_index]["datetime"],
        "first_burst_speed_peak_candidate_bp_per_bar": peak_speed,
        "first_burst_speed_peak_time": (
            bars[peak_index]["datetime"] if cooling_index is not None else None
        ),
        "first_burst_speed_peak_bp_per_bar": peak_speed if cooling_index is not None else None,
        "first_burst_cooling_confirmed_at": (
            bars[cooling_index]["datetime"] if cooling_index is not None else None
        ),
        "second_wave_detected_at": (
            bars[second_wave_index]["datetime"] if second_wave_index is not None else None
        ),
        "first_burst_anchor_price": anchor_price,
        "first_burst_low_price": first_low,
        "episode_low_price_current": episode_low,
        "recovery_ratio_current": recovery_ratio,
        "recovery_bars_current": repair_run,
        "repair_confirmed": repair_confirmed,
        "repair_invalidated_at": repair_invalidated_at,
        "nonrepair_bars_after_cooling": (
            bars[-1]["slot"] - bars[cooling_index]["slot"]
            if cooling_index is not None and not repair_confirmed
            else 0
        ),
        "burst_duration_bars": (
            bars[cooling_index]["slot"] - bars[burst_start]["slot"] + 1
            if cooling_index is not None
            else bars[-1]["slot"] - bars[burst_start]["slot"] + 1
        ),
        "episode_drawdown_bp_current": (
            max(0.0, -math.log((episode_low or anchor_price) / anchor_price) * 10000.0)
            if anchor_price
            else None
        ),
    }


def _evidence_status(prepared, prefix, config):
    closes = [bar["close"] for bar in prefix]
    constant_limit_path = (
        prepared["price_limit_state"] in {"limit_up", "limit_down"}
        and max(closes) == min(closes)
    )
    if constant_limit_path or len(prefix) < config.dynamics_window_bars:
        return "insufficient"
    if not prepared["data_quality"]["source_metadata_complete"]:
        return "partial"
    if prepared["source_integrity_compromised"]:
        return "partial"
    prefix_slots = {bar["slot"] for bar in prefix}
    if any(slot not in prefix_slots for slot in range(prefix[-1]["slot"] + 1)):
        return "partial"
    if _amount_unavailable_reason(prepared, prefix) is not None:
        return "partial"
    if prepared["instrument"]["type"] == "stock":
        if _volume_unavailable_reason(prepared, prefix) is not None:
            return "partial"
    if len(prefix) < config.minimum_price_evidence_bars:
        return "partial"
    return "sufficient"


def _amount_unavailable_reason(prepared, bars):
    source = prepared["source"]
    if source.get("amount_unit") != "CNY":
        return "amount_unit_unverified"
    if source.get("amount_semantics") != "interval":
        return "amount_semantics_unverified"
    if any(bar.get("amount") is None for bar in bars):
        return "amount_missing"
    if prepared["source_integrity_compromised"]:
        return "source_integrity_unverified"
    return None


def _volume_unavailable_reason(prepared, bars):
    source = prepared["source"]
    if source.get("volume_unit") != "shares":
        return "volume_unit_unverified"
    if source.get("volume_semantics") != "interval":
        return "volume_semantics_unverified"
    if any(bar.get("volume") is None for bar in bars):
        return "volume_missing"
    if prepared["source_integrity_compromised"]:
        return "source_integrity_unverified"
    return None


def _dynamics(prefix, event, config, evidence_status):
    if evidence_status == "insufficient":
        return "unclear"
    window = config.dynamics_window_bars
    recent = _log_slope_bp(prefix[-window:]) if len(prefix) >= window else None
    previous = _log_slope_bp(prefix[-2 * window : -window]) if len(prefix) >= 2 * window else None
    if recent is None:
        return "unclear"
    recent_returns = [
        value for value in _bar_returns_bp(prefix[-(window + 1) :])[1:] if value is not None
    ]
    positive_count = sum(1 for value in recent_returns[-3:] if value > 0)
    has_pressure_episode = event.get("burst_start_time") is not None
    if (
        has_pressure_episode
        and recent >= config.repairing_slope_bp_per_bar
        and positive_count >= 2
    ):
        return "repairing"
    if (
        has_pressure_episode
        and event.get("repair_confirmed")
        and recent > 0
        and positive_count >= 1
    ):
        return "repairing"
    if recent <= config.accelerating_slope_bp_per_bar and (
        previous is None or recent <= previous - config.slope_change_bp_per_bar
    ):
        return "accelerating"
    if previous is not None and previous <= config.accelerating_slope_bp_per_bar and (
        recent >= previous + config.slope_change_bp_per_bar
    ) and recent < config.repairing_slope_bp_per_bar:
        return "decelerating"
    if recent <= config.steady_down_slope_bp_per_bar:
        return "steady_down"
    return "unclear"


def _episode_label(event, evidence_status, config):
    if evidence_status == "insufficient" or event.get("burst_start_time") is None:
        return "unclear"
    if event.get("repair_confirmed"):
        if (
            (event.get("first_burst_speed_peak_bp_per_bar") or 0.0)
            >= config.flash_peak_speed_bp_per_bar
            and (event.get("burst_duration_bars") or 999) <= config.flash_max_bars
        ):
            return "flash_candidate"
        return "first_burst_completed"
    if event.get("second_wave_detected_at"):
        return "second_wave"
    if event.get("first_burst_cooling_confirmed_at"):
        if event.get("nonrepair_bars_after_cooling", 0) >= config.nonrepair_tail_bars:
            return "nonrepair_tail"
        return "first_burst_completed"
    return "first_burst_open"


def _handoff_candidate(event, episode, evidence_status, config):
    if evidence_status == "insufficient" or event.get("first_burst_cooling_confirmed_at") is None:
        return None
    if event.get("repair_confirmed"):
        return False
    if (event.get("episode_drawdown_bp_current") or 0.0) < config.material_episode_drawdown_bp:
        return False
    return episode in {"second_wave", "nonrepair_tail"}


def _prefix_metrics(prepared, prefix, event, change_memory, config):
    instrument_type = prepared["instrument"]["type"]
    current_slope, previous_slope = _rolling_slope_pair(prefix, config.dynamics_window_bars)
    trend_slope, previous_trend_slope = _rolling_slope_pair(prefix, config.slope_window_bars)
    reasons = {}
    missing = []
    not_applicable = []
    if current_slope is None:
        reasons["current_log_slope_bp_per_bar"] = "insufficient_prefix"
    if previous_slope is None:
        reasons["previous_log_slope_bp_per_bar"] = "insufficient_prefix"
    if current_slope is None or previous_slope is None:
        reasons["slope_change_bp_per_bar"] = "insufficient_prefix"
    if trend_slope is None:
        reasons["trend_log_slope_bp_per_bar"] = "insufficient_prefix"
    if previous_trend_slope is None:
        reasons["previous_trend_log_slope_bp_per_bar"] = "insufficient_prefix"

    opening_gap_bp = None
    if prefix[0]["slot"] != 0:
        reasons["opening_gap_bp"] = "opening_bar_missing"
        missing.append({"field": "opening_gap_bp", "reason": "opening_bar_missing"})
    elif prepared["previous_close"] is not None:
        opening_gap_bp = math.log(prefix[0]["open"] / prepared["previous_close"]) * 10000.0
    else:
        reasons["opening_gap_bp"] = "previous_close_missing"
        missing.append({"field": "opening_gap_bp", "reason": "previous_close_missing"})

    cumulative_amount = None
    recent_amount = None
    recent_amount_share = None
    cumulative_amount_reason = _amount_unavailable_reason(prepared, prefix)
    if cumulative_amount_reason is None:
        cumulative_amount = sum(bar["amount"] for bar in prefix) / 100000000.0
        recent_amount = sum(
            bar["amount"] for bar in prefix[-config.impact_window_bars :]
        ) / 100000000.0
        if cumulative_amount > 0:
            recent_amount_share = recent_amount / cumulative_amount * 100.0
        else:
            reasons["recent_amount_share_of_observed_pct"] = "amount_zero"
            missing.append(
                {
                    "field": "recent_amount_share_of_observed_pct",
                    "reason": "amount_zero",
                }
            )
    else:
        reason = cumulative_amount_reason
        reasons["cumulative_amount_yi"] = reason
        reasons["recent_amount_yi"] = reason
        reasons["recent_amount_share_of_observed_pct"] = reason
        missing.append({"field": "cumulative_amount_yi", "reason": reason})

    cumulative_vwap = None
    vwap_deviation = None
    below_vwap_bars = None
    if instrument_type == "index":
        reason = "index_vwap_not_applicable"
        reasons["cumulative_vwap"] = reason
        reasons["vwap_deviation_bp"] = reason
        reasons["below_vwap_bars_current"] = reason
        not_applicable.append({"field": "stock_vwap", "reason": reason})
    elif (
        _amount_unavailable_reason(prepared, prefix) is None
        and _volume_unavailable_reason(prepared, prefix) is None
    ):
        total_volume = sum(bar["volume"] for bar in prefix)
        total_amount = sum(bar["amount"] for bar in prefix)
        if total_volume > 0:
            cumulative_vwap = total_amount / total_volume
            vwap_deviation = math.log(prefix[-1]["close"] / cumulative_vwap) * 10000.0
            below_vwap_bars = 0
            running_amount = 0.0
            running_volume = 0.0
            for bar in prefix:
                running_amount += bar["amount"]
                running_volume += bar["volume"]
                running_vwap = running_amount / running_volume if running_volume > 0 else None
                if running_vwap is not None and bar["close"] < running_vwap:
                    below_vwap_bars += 1
                else:
                    below_vwap_bars = 0
        else:
            reasons["cumulative_vwap"] = "volume_zero"
            reasons["vwap_deviation_bp"] = "volume_zero"
            reasons["below_vwap_bars_current"] = "volume_zero"
            missing.append({"field": "cumulative_vwap", "reason": "volume_zero"})
    else:
        reason = _amount_unavailable_reason(prepared, prefix) or _volume_unavailable_reason(
            prepared, prefix
        )
        reasons["cumulative_vwap"] = reason
        reasons["vwap_deviation_bp"] = reason
        reasons["below_vwap_bars_current"] = reason
        missing.append({"field": "stock_vwap", "reason": reason})

    impact = None
    impact_bars = prefix[-config.impact_window_bars :]
    impact_reason = _amount_unavailable_reason(prepared, impact_bars)
    if impact_reason is not None:
        reasons["down_impact_bp_per_yi"] = impact_reason
        missing.append({"field": "down_impact_bp_per_yi", "reason": impact_reason})
    elif len(prefix) <= config.impact_window_bars:
        reasons["down_impact_bp_per_yi"] = "insufficient_prefix"
    else:
        amount_yi = sum(
            bar["amount"] or 0.0 for bar in prefix[-config.impact_window_bars :]
        ) / 100000000.0
        decline_bp = max(
            0.0,
            -math.log(
                prefix[-1]["close"] / prefix[-config.impact_window_bars - 1]["close"]
            )
            * 10000.0,
        )
        if amount_yi > 0:
            impact = decline_bp / amount_yi
        else:
            reasons["down_impact_bp_per_yi"] = "amount_zero"

    reasons["cross_section_sync"] = "requires_cross_section"
    missing.append({"field": "cross_section_sync", "reason": "requires_cross_section"})

    change_null_reasons = {
        "candidate_change_time": "change_not_confirmed",
        "first_detected_at": "change_not_confirmed",
        "change_detected_at": "change_not_confirmed",
        "current_candidate_estimate_time": (
            "change_not_currently_supported"
            if change_memory.get("first_detected_at")
            else "change_not_confirmed"
        ),
        "candidate_revised_at": "candidate_not_revised",
        "change_before_slope_bp_per_bar": "change_not_currently_supported",
        "change_after_slope_bp_per_bar": "change_not_currently_supported",
        "change_improvement_ratio": "change_not_currently_supported",
        "change_bic_improvement": "change_not_currently_supported",
    }
    change_memory_keys = {
        "candidate_change_time": "candidate_change_time",
        "first_detected_at": "first_detected_at",
        "change_detected_at": "first_detected_at",
        "current_candidate_estimate_time": "current_candidate_estimate_time",
        "candidate_revised_at": "candidate_revised_at",
        "change_before_slope_bp_per_bar": "before_slope",
        "change_after_slope_bp_per_bar": "after_slope",
        "change_improvement_ratio": "improvement_ratio",
        "change_bic_improvement": "bic_improvement",
    }
    for field, reason in change_null_reasons.items():
        value_key = change_memory_keys[field]
        if change_memory.get(value_key) is None:
            reasons[field] = reason

    event_reason = event.get("event_unavailable_reason")
    event_null_reasons = {
        "burst_start_time": event_reason or "episode_not_completed",
        "first_burst_speed_peak_candidate_time": event_reason or "episode_not_completed",
        "first_burst_speed_peak_candidate_bp_per_bar": event_reason or "episode_not_completed",
        "first_burst_speed_peak_time": event_reason or "future_horizon_censored",
        "first_burst_speed_peak_bp_per_bar": event_reason or "future_horizon_censored",
        "first_burst_cooling_confirmed_at": event_reason or "future_horizon_censored",
        "second_wave_detected_at": event_reason or "future_horizon_censored",
        "first_burst_anchor_price": event_reason or "episode_not_completed",
        "first_burst_low_price": event_reason or "future_horizon_censored",
        "episode_low_price_current": event_reason or "future_horizon_censored",
        "recovery_ratio_current": event_reason or "episode_not_completed",
        "repair_invalidated_at": "repair_not_invalidated",
        "burst_duration_bars": event_reason or "future_horizon_censored",
        "episode_drawdown_bp_current": event_reason or "episode_not_completed",
    }
    for field, reason in event_null_reasons.items():
        if event.get(field) is None:
            reasons[field] = reason
    metrics = {
        "opening_gap_bp": _round_or_none(opening_gap_bp),
        "dynamics_window_bars": config.dynamics_window_bars,
        "trend_window_bars": config.slope_window_bars,
        "current_log_slope_bp_per_bar": _round_or_none(current_slope),
        "previous_log_slope_bp_per_bar": _round_or_none(previous_slope),
        "trend_log_slope_bp_per_bar": _round_or_none(trend_slope),
        "previous_trend_log_slope_bp_per_bar": _round_or_none(previous_trend_slope),
        "slope_change_bp_per_bar": _round_or_none(
            current_slope - previous_slope
            if current_slope is not None and previous_slope is not None
            else None
        ),
        "candidate_change_time": change_memory["candidate_change_time"],
        "first_detected_at": change_memory["first_detected_at"],
        "change_detected_at": change_memory["first_detected_at"],
        "current_candidate_estimate_time": change_memory["current_candidate_estimate_time"],
        "candidate_revised_at": change_memory["candidate_revised_at"],
        "change_confirmation_count": change_memory.get("confirmation_count", 0),
        "change_currently_supported": change_memory.get("currently_supported", False),
        "change_before_slope_bp_per_bar": _round_or_none(change_memory["before_slope"]),
        "change_after_slope_bp_per_bar": _round_or_none(change_memory["after_slope"]),
        "change_improvement_ratio": _round_or_none(change_memory["improvement_ratio"]),
        "change_bic_improvement": _round_or_none(change_memory.get("bic_improvement")),
        "cumulative_amount_yi": _round_or_none(cumulative_amount),
        "recent_amount_yi": _round_or_none(recent_amount),
        "recent_amount_share_of_observed_pct": _round_or_none(recent_amount_share),
        "cumulative_vwap": _round_or_none(cumulative_vwap),
        "vwap_deviation_bp": _round_or_none(vwap_deviation),
        "below_vwap_bars_current": below_vwap_bars,
        "down_impact_bp_per_yi": _round_or_none(impact),
        "cross_section_sync": None,
        "burst_start_time": event.get("burst_start_time"),
        "first_burst_speed_peak_candidate_time": event.get(
            "first_burst_speed_peak_candidate_time"
        ),
        "first_burst_speed_peak_candidate_bp_per_bar": _round_or_none(
            event.get("first_burst_speed_peak_candidate_bp_per_bar")
        ),
        "first_burst_speed_peak_time": event.get("first_burst_speed_peak_time"),
        "first_burst_speed_peak_bp_per_bar": _round_or_none(
            event.get("first_burst_speed_peak_bp_per_bar")
        ),
        "first_burst_cooling_confirmed_at": event.get("first_burst_cooling_confirmed_at"),
        "second_wave_detected_at": event.get("second_wave_detected_at"),
        "first_burst_anchor_price": _round_or_none(event.get("first_burst_anchor_price")),
        "first_burst_low_price": _round_or_none(event.get("first_burst_low_price")),
        "episode_low_price_current": _round_or_none(event.get("episode_low_price_current")),
        "recovery_ratio_current": _round_or_none(event.get("recovery_ratio_current")),
        "recovery_bars_current": event.get("recovery_bars_current", 0),
        "repair_confirmed": bool(event.get("repair_confirmed")),
        "repair_invalidated_at": event.get("repair_invalidated_at"),
        "nonrepair_bars_after_cooling": event.get("nonrepair_bars_after_cooling", 0),
        "burst_duration_bars": event.get("burst_duration_bars"),
        "episode_drawdown_bp_current": _round_or_none(
            event.get("episode_drawdown_bp_current")
        ),
    }
    return metrics, reasons, missing, not_applicable


def _solve_linear_system(matrix, vector):
    size = len(vector)
    augmented = [list(matrix[row]) + [vector[row]] for row in range(size)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) <= 1e-14:
            return None
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        divisor = augmented[column][column]
        augmented[column] = [value / divisor for value in augmented[column]]
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            augmented[row] = [
                value - factor * pivot_value
                for value, pivot_value in zip(augmented[row], augmented[column])
            ]
    solution = [augmented[row][-1] for row in range(size)]
    return solution if all(math.isfinite(value) for value in solution) else None


def _fit_features(features, ys):
    if not features or len(features) != len(ys):
        return None
    width = len(features[0])
    if any(len(row) != width for row in features) or len(features) < width:
        return None
    matrix = [
        [sum(row[left] * row[right] for row in features) for right in range(width)]
        for left in range(width)
    ]
    vector = [sum(row[column] * value for row, value in zip(features, ys)) for column in range(width)]
    coefficients = _solve_linear_system(matrix, vector)
    if coefficients is None:
        return None
    predictions = [sum(coef * value for coef, value in zip(coefficients, row)) for row in features]
    if not all(math.isfinite(value) for value in predictions):
        return None
    sse = sum((actual - predicted) ** 2 for actual, predicted in zip(ys, predictions))
    return {"coefficients": coefficients, "predictions": predictions, "sse": sse}


def _model_payload(
    *,
    fit,
    parameters,
    parameter_count,
    observation_count,
    boundary_parameters=(),
):
    if fit is None:
        return {
            "applicable": False,
            "reason": "singular_or_nonfinite_fit",
            "parameters": None,
            "rmse": None,
            "aicc": None,
        }
    sse = fit["sse"]
    if not math.isfinite(sse) or sse < 0:
        return {
            "applicable": False,
            "reason": "nonfinite_fit",
            "parameters": None,
            "rmse": None,
            "aicc": None,
        }
    rmse = math.sqrt(sse / observation_count)
    aicc = None
    aicc_reason = None
    if observation_count <= parameter_count + 1:
        aicc_reason = "insufficient_degrees_of_freedom"
    elif sse <= 1e-24:
        aicc_reason = "zero_residual"
    else:
        aic = observation_count * math.log(sse / observation_count) + 2 * parameter_count
        aicc = aic + (
            2 * parameter_count * (parameter_count + 1)
            / (observation_count - parameter_count - 1)
        )
        if not math.isfinite(aicc):
            aicc = None
            aicc_reason = "nonfinite_aicc"
    payload = {
        "applicable": True,
        "reason": None,
        "parameters": {
            key: (
                value
                if isinstance(value, (bool, int))
                else _round_or_none(value, 8)
                if isinstance(value, float)
                else value
            )
            for key, value in parameters.items()
        },
        "parameter_count": parameter_count,
        "observation_count": observation_count,
        "rmse": _round_or_none(rmse, 10),
        "aicc": _round_or_none(aicc, 8),
        "residual_variance": _round_or_none(sse / observation_count, 12),
        "boundary_hit": bool(boundary_parameters),
        "boundary_parameters": list(boundary_parameters),
        "_aicc_unrounded": aicc,
    }
    if aicc_reason:
        payload["aicc_reason"] = aicc_reason
    return payload


def _best_grid_fit(candidates):
    valid = [candidate for candidate in candidates if candidate.get("fit") is not None]
    if not valid:
        return None
    return min(valid, key=lambda item: (item["fit"]["sse"], item["stable_key"]))


def _aicc_selection_strength(raw_ranking):
    if not raw_ranking:
        return None
    if len(raw_ranking) < 2:
        return "strong"
    second_delta = raw_ranking[1]["aicc"] - raw_ranking[0]["aicc"]
    if second_delta <= 2:
        return "indistinguishable"
    if second_delta <= 4:
        return "weak"
    if second_delta <= 10:
        return "moderate"
    return "strong"


def _full_path_diagnostics(prepared):
    bars = prepared["bars"]
    closes = [bar["close"] for bar in bars]
    base = {
        "hindsight_only": True,
        "response": "log_close_relative_to_first_bar",
        "time_axis": "fixed_a_share_trade_slot",
        "missing_slot_count": len(prepared["data_quality"].get("missing_session_bars") or []),
        "interpretation_limit": "in_sample_shape_fit_not_account_identity_or_cause",
        "statistical_limitations": [
            "grid_selection_optimism_not_adjusted",
            "intraday_residual_autocorrelation_not_adjusted",
            "boundary_hit_parameters_are_not_stable_economic_estimates",
        ],
    }
    if (
        prepared["price_limit_state"] in {"limit_up", "limit_down"}
        and max(closes) == min(closes)
    ):
        return {
            **base,
            "applicable": False,
            "reason": "price_limit_path_not_identifiable",
            "models": {},
            "ranking": [],
            "ranking_reason": "price_limit_path_not_identifiable",
            "best_model": None,
            "selection_strength": None,
        }
    if len(closes) < 8 or max(closes) == min(closes):
        return {
            **base,
            "applicable": False,
            "reason": "insufficient_or_constant_path",
            "models": {},
            "ranking": [],
            "ranking_reason": "insufficient_or_constant_path",
            "best_model": None,
            "selection_strength": None,
        }

    observation_count = len(closes)
    first_slot = bars[0]["slot"]
    slot_span = bars[-1]["slot"] - first_slot
    xs = [(bar["slot"] - first_slot) / slot_span for bar in bars]
    ys = [math.log(close / closes[0]) for close in closes]
    models = {}

    linear_fit = _fit_features([[1.0, value] for value in xs], ys)
    models["linear"] = _model_payload(
        fit=linear_fit,
        parameters={
            "intercept": linear_fit["coefficients"][0] if linear_fit else None,
            "slope": linear_fit["coefficients"][1] if linear_fit else None,
        },
        parameter_count=3,
        observation_count=observation_count,
    )

    segmented_candidates = []
    for knot_index in range(4, observation_count - 4 + 1):
        knot = xs[knot_index]
        fit = _fit_features(
            [[1.0, value, max(0.0, value - knot)] for value in xs],
            ys,
        )
        segmented_candidates.append(
            {"fit": fit, "stable_key": (knot_index,), "knot_index": knot_index, "knot": knot}
        )
    segmented = _best_grid_fit(segmented_candidates)
    models["segmented"] = _model_payload(
        fit=segmented["fit"] if segmented else None,
        parameters={
            "intercept": segmented["fit"]["coefficients"][0] if segmented else None,
            "slope_before": segmented["fit"]["coefficients"][1] if segmented else None,
            "slope_delta": segmented["fit"]["coefficients"][2] if segmented else None,
            "knot_index": segmented["knot_index"] if segmented else None,
        },
        parameter_count=5,
        observation_count=observation_count,
        boundary_parameters=(
            ["knot_index"]
            if segmented and segmented["knot_index"] in {4, observation_count - 4}
            else []
        ),
    )

    power_candidates = []
    for exponent in (0.25, 0.35, 0.5, 0.65, 0.8, 1.0, 1.25):
        for critical_scale in (1.02, 1.1, 1.25, 1.5):
            feature = [
                1.0 - max(1e-9, 1.0 - value / critical_scale) ** exponent
                for value in xs
            ]
            fit = _fit_features([[1.0, value] for value in feature], ys)
            power_candidates.append(
                {
                    "fit": fit,
                    "stable_key": (exponent, critical_scale),
                    "exponent": exponent,
                    "critical_scale": critical_scale,
                }
            )
    power = _best_grid_fit(power_candidates)
    models["finite_time_power"] = _model_payload(
        fit=power["fit"] if power else None,
        parameters={
            "intercept": power["fit"]["coefficients"][0] if power else None,
            "amplitude": power["fit"]["coefficients"][1] if power else None,
            "exponent_m": power["exponent"] if power else None,
            "critical_scale": power["critical_scale"] if power else None,
            "m_near_sqrt": abs(power["exponent"] - 0.5) <= 0.1 if power else None,
        },
        parameter_count=5,
        observation_count=observation_count,
        boundary_parameters=(
            [
                name
                for name, value, bounds in (
                    ("exponent_m", power["exponent"], (0.25, 1.25)),
                    ("critical_scale", power["critical_scale"], (1.02, 1.5)),
                )
                if power and value in bounds
            ]
            if power
            else []
        ),
    )

    sqrt_candidates = []
    for critical_scale in (1.02, 1.1, 1.25, 1.5):
        feature = [
            1.0
            - math.sqrt(max(0.0, 1.0 - (value / critical_scale) ** 2))
            for value in xs
        ]
        fit = _fit_features([[1.0, value] for value in feature], ys)
        sqrt_candidates.append(
            {
                "fit": fit,
                "stable_key": (critical_scale,),
                "critical_scale": critical_scale,
            }
        )
    sqrt_fit = _best_grid_fit(sqrt_candidates)
    models["sqrt_ellipse_proxy"] = _model_payload(
        fit=sqrt_fit["fit"] if sqrt_fit else None,
        parameters={
            "intercept": sqrt_fit["fit"]["coefficients"][0] if sqrt_fit else None,
            "amplitude": sqrt_fit["fit"]["coefficients"][1] if sqrt_fit else None,
            "critical_scale": sqrt_fit["critical_scale"] if sqrt_fit else None,
        },
        parameter_count=4,
        observation_count=observation_count,
        boundary_parameters=(
            ["critical_scale"]
            if sqrt_fit and sqrt_fit["critical_scale"] in {1.02, 1.5}
            else []
        ),
    )

    exponential_candidates = []
    for rate in (0.25, 0.5, 1.0, 2.0, 3.0, 4.0):
        feature = [math.expm1(rate * value) for value in xs]
        fit = _fit_features([[1.0, value] for value in feature], ys)
        exponential_candidates.append(
            {"fit": fit, "stable_key": (rate,), "rate": rate}
        )
    exponential = _best_grid_fit(exponential_candidates)
    models["exponential"] = _model_payload(
        fit=exponential["fit"] if exponential else None,
        parameters={
            "intercept": exponential["fit"]["coefficients"][0] if exponential else None,
            "amplitude": exponential["fit"]["coefficients"][1] if exponential else None,
            "rate": exponential["rate"] if exponential else None,
        },
        parameter_count=4,
        observation_count=observation_count,
        boundary_parameters=(
            ["rate"] if exponential and exponential["rate"] in {0.25, 4.0} else []
        ),
    )

    gompertz_candidates = []
    for rate in (1.0, 2.0, 4.0, 6.0, 8.0):
        for center in (0.25, 0.5, 0.75, 1.0):
            feature = [
                math.exp(-math.exp(-rate * (value - center)))
                for value in xs
            ]
            fit = _fit_features([[1.0, value] for value in feature], ys)
            gompertz_candidates.append(
                {"fit": fit, "stable_key": (rate, center), "rate": rate, "center": center}
            )
    gompertz = _best_grid_fit(gompertz_candidates)
    models["gompertz"] = _model_payload(
        fit=gompertz["fit"] if gompertz else None,
        parameters={
            "intercept": gompertz["fit"]["coefficients"][0] if gompertz else None,
            "amplitude": gompertz["fit"]["coefficients"][1] if gompertz else None,
            "rate": gompertz["rate"] if gompertz else None,
            "center": gompertz["center"] if gompertz else None,
        },
        parameter_count=5,
        observation_count=observation_count,
        boundary_parameters=(
            [
                name
                for name, value, bounds in (
                    ("rate", gompertz["rate"], (1.0, 8.0)),
                    ("center", gompertz["center"], (0.25, 1.0)),
                )
                if gompertz and value in bounds
            ]
            if gompertz
            else []
        ),
    )

    logarithmic_candidates = []
    for rate in (0.25, 0.5, 1.0, 2.0, 4.0, 8.0):
        feature = [math.log1p(rate * value) for value in xs]
        fit = _fit_features([[1.0, value] for value in feature], ys)
        logarithmic_candidates.append(
            {"fit": fit, "stable_key": (rate,), "rate": rate}
        )
    logarithmic = _best_grid_fit(logarithmic_candidates)
    models["logarithmic"] = _model_payload(
        fit=logarithmic["fit"] if logarithmic else None,
        parameters={
            "intercept": logarithmic["fit"]["coefficients"][0] if logarithmic else None,
            "amplitude": logarithmic["fit"]["coefficients"][1] if logarithmic else None,
            "rate": logarithmic["rate"] if logarithmic else None,
        },
        parameter_count=4,
        observation_count=observation_count,
        boundary_parameters=(
            ["rate"] if logarithmic and logarithmic["rate"] in {0.25, 8.0} else []
        ),
    )
    zero_residual_present = any(
        payload.get("aicc_reason") == "zero_residual" for payload in models.values()
    )
    raw_ranking = []
    if not zero_residual_present:
        raw_ranking = sorted(
            (
                {"model": name, "aicc": payload.get("_aicc_unrounded")}
                for name, payload in models.items()
                if payload.get("_aicc_unrounded") is not None
            ),
            key=lambda item: (item["aicc"], item["model"]),
        )
    ranking = []
    if raw_ranking:
        best_aicc = raw_ranking[0]["aicc"]
        ranking = [
            {
                "model": item["model"],
                "aicc": _round_or_none(item["aicc"], 8),
                "delta_aicc": _round_or_none(item["aicc"] - best_aicc, 8),
            }
            for item in raw_ranking
        ]
    for payload in models.values():
        payload.pop("_aicc_unrounded", None)
    if zero_residual_present:
        ranking_reason = "zero_residual_model_present"
    elif not ranking:
        ranking_reason = "no_comparable_aicc"
    else:
        ranking_reason = None
    selection_strength = _aicc_selection_strength(raw_ranking)
    return {
        **base,
        "applicable": True,
        "reason": None,
        "models": models,
        "ranking": ranking,
        "ranking_reason": ranking_reason,
        "best_model": ranking[0]["model"] if ranking else None,
        "best_model_scope": "in_sample_shape_only" if ranking else None,
        "selection_strength": selection_strength,
    }


def _forbidden_inferences():
    return [
        {
            "name": "quant_account_identity",
            "value": None,
            "reason": "requires_account_level_order_flow",
        },
        {
            "name": "quant_turnover_share",
            "value": None,
            "reason": "requires_account_level_trade_classification",
        },
        {"name": "true_q_over_l", "value": None, "reason": "requires_signed_flow_and_depth"},
        {
            "name": "order_flow_imbalance",
            "value": None,
            "reason": "requires_order_flow",
        },
        {"name": "order_book_depth", "value": None, "reason": "requires_order_book"},
        {"name": "order_cancellation", "value": None, "reason": "requires_order_book_events"},
        {
            "name": "remaining_inventory",
            "value": None,
            "reason": "requires_account_inventory_and_execution_records",
        },
        {
            "name": "hawkes_self_excitation",
            "value": None,
            "reason": "requires_event_level_order_arrivals",
        },
        {
            "name": "slow_fund_identity",
            "value": None,
            "reason": "price_volume_path_cannot_identify_fund_type",
        },
        {
            "name": "position_or_trade_action",
            "value": None,
            "reason": "research_output_has_no_position_or_trade_action_contract",
        },
    ]


def build_quant_pressure_replay(case):
    config = ResearchPressureConfig()
    prepared = _prepare_case(case)
    bars = prepared["bars"]
    timeline = []
    memory = {
        "candidate_change_time": None,
        "first_detected_at": None,
        "current_candidate_estimate_time": None,
        "candidate_revised_at": None,
        "before_slope": None,
        "after_slope": None,
        "improvement_ratio": None,
        "bic_improvement": None,
        "pending_candidate_time": None,
        "pending_count": 0,
        "confirmation_count": 0,
        "currently_supported": False,
        "last_supported_candidate_time": None,
    }
    for end_index in range(len(bars)):
        prefix = bars[: end_index + 1]
        candidate = _piecewise_candidate(prefix, config)
        next_memory = dict(memory)
        next_memory["currently_supported"] = False
        if next_memory["first_detected_at"] is None:
            if candidate is None:
                next_memory["pending_candidate_time"] = None
                next_memory["pending_count"] = 0
                next_memory["confirmation_count"] = 0
            else:
                if candidate["time"] == next_memory["pending_candidate_time"]:
                    next_memory["pending_count"] += 1
                else:
                    next_memory["pending_candidate_time"] = candidate["time"]
                    next_memory["pending_count"] = 1
                next_memory["confirmation_count"] = next_memory["pending_count"]
            if (
                candidate is not None
                and next_memory["pending_count"] >= config.change_confirmation_bars
            ):
                next_memory.update(
                    {
                        "candidate_change_time": candidate["time"],
                        "first_detected_at": prefix[-1]["datetime"],
                        "current_candidate_estimate_time": candidate["time"],
                        "currently_supported": True,
                        "last_supported_candidate_time": candidate["time"],
                        "before_slope": candidate["before_slope_bp_per_bar"],
                        "after_slope": candidate["after_slope_bp_per_bar"],
                        "improvement_ratio": candidate["improvement_ratio"],
                        "bic_improvement": candidate["bic_improvement"],
                    }
                )
        elif candidate is not None:
            previous_supported_time = next_memory.get("last_supported_candidate_time")
            if previous_supported_time is not None and candidate["time"] != previous_supported_time:
                next_memory["candidate_revised_at"] = prefix[-1]["datetime"]
            next_memory.update(
                {
                    "currently_supported": True,
                    "confirmation_count": max(
                        config.change_confirmation_bars,
                        next_memory.get("confirmation_count", 0) + 1,
                    ),
                    "current_candidate_estimate_time": candidate["time"],
                    "last_supported_candidate_time": candidate["time"],
                    "before_slope": candidate["before_slope_bp_per_bar"],
                    "after_slope": candidate["after_slope_bp_per_bar"],
                    "improvement_ratio": candidate["improvement_ratio"],
                    "bic_improvement": candidate["bic_improvement"],
                }
            )
        else:
            next_memory.update(
                {
                    "currently_supported": False,
                    "confirmation_count": 0,
                    "current_candidate_estimate_time": None,
                    "before_slope": None,
                    "after_slope": None,
                    "improvement_ratio": None,
                    "bic_improvement": None,
                }
            )
        memory = next_memory

        event = _episode_state(prefix, config)
        evidence_status = _evidence_status(prepared, prefix, config)
        current_dynamics = _dynamics(prefix, event, config, evidence_status)
        episode_structure = _episode_label(event, evidence_status, config)
        handoff = _handoff_candidate(event, episode_structure, evidence_status, config)
        metrics, reasons, missing, not_applicable = _prefix_metrics(
            prepared, prefix, event, memory, config
        )
        axis_reasons = {}
        if handoff is None:
            axis_reasons["handoff_risk_candidate"] = (
                event.get("event_unavailable_reason") or "episode_not_completed"
            )
        if current_dynamics not in _DYNAMICS:
            raise AssertionError("invalid current_dynamics")
        if episode_structure not in _EPISODES:
            raise AssertionError("invalid episode_structure")
        if evidence_status not in _EVIDENCE:
            raise AssertionError("invalid evidence_status")
        timeline.append(
            {
                "as_of_bar": prefix[-1]["datetime"],
                "trade_slot_index": prefix[-1]["slot"],
                "elapsed_trading_minutes": (prefix[-1]["slot"] + 1) * 5,
                "metrics": metrics,
                "metric_reasons": reasons,
                "current_dynamics": current_dynamics,
                "episode_structure": episode_structure,
                "evidence_status": evidence_status,
                "handoff_risk_candidate": handoff,
                "axis_reasons": axis_reasons,
                "missing_evidence": missing,
                "not_applicable_evidence": not_applicable,
            }
        )

    result = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "case_id": prepared["case_id"],
        "origin": prepared["origin"],
        "instrument": copy.deepcopy(prepared["instrument"]),
        "trade_date": prepared["trade_date"],
        "data_quality": copy.deepcopy(prepared["data_quality"]),
        "config": dataclasses.asdict(config),
        "prefix_timeline": timeline,
        "full_path_diagnostics": _full_path_diagnostics(prepared),
        "forbidden_inferences": _forbidden_inferences(),
    }
    json.dumps(result, ensure_ascii=False, allow_nan=False)
    return result


_DYNAMICS_ZH = {
    "accelerating": "压力加速",
    "steady_down": "稳定下压",
    "decelerating": "压力降温",
    "repairing": "持续修复",
    "unclear": "暂不明确",
}
_EPISODES_ZH = {
    "first_burst_open": "第一轮压力进行中",
    "first_burst_completed": "第一轮压力已降温",
    "nonrepair_tail": "峰后未修复长尾",
    "second_wave": "第二轮压力",
    "flash_candidate": "闪燃候选",
    "unclear": "结构暂不明确",
}
_EVIDENCE_ZH = {
    "sufficient": "路径证据充分",
    "partial": "路径证据部分完整",
    "insufficient": "路径证据不足",
}


def _display_number(value, digits=2):
    return "-" if value is None else f"{float(value):.{digits}f}"


def render_quant_pressure_replay_markdown(result):
    result = result or {}
    instrument = result.get("instrument") or {}
    lines = [
        f"# {result.get('case_id', '-')} 量化压力阶段离线回放",
        "",
        f"> {instrument.get('name', '-')}({instrument.get('code', '-')}) / {result.get('trade_date', '-')}。五分钟价格成交路径只能识别压力形态，不能确认账户身份或下跌原因。",
        f"> 研究配置：{(result.get('config') or {}).get('version', '-')}；当前材料强度仍是未按历史波动标准化的样本内启发式。",
        "",
        "## 前缀时间线",
        "",
        "| 截止bar | 当前动力 | 事件结构 | 证据 | 斜率(bp/5分钟) | 修复比例 | 交接风险候选 |",
        "|---------|----------|----------|------|----------------|----------|--------------|",
    ]
    for row in result.get("prefix_timeline") or []:
        metrics = row.get("metrics") or {}
        handoff = row.get("handoff_risk_candidate")
        handoff_text = "待形成" if handoff is None else ("是" if handoff else "否")
        lines.append(
            "| {time} | {dynamics} | {episode} | {evidence} | {slope} | {recovery} | {handoff} |".format(
                time=row.get("as_of_bar", "-")[11:16],
                dynamics=_DYNAMICS_ZH.get(row.get("current_dynamics"), "-"),
                episode=_EPISODES_ZH.get(row.get("episode_structure"), "-"),
                evidence=_EVIDENCE_ZH.get(row.get("evidence_status"), "-"),
                slope=_display_number(metrics.get("current_log_slope_bp_per_bar")),
                recovery=_display_number(metrics.get("recovery_ratio_current")),
                handoff=handoff_text,
            )
        )

    diagnostics = result.get("full_path_diagnostics") or {}
    lines.extend(["", "## 事后曲线诊断", ""])
    if not diagnostics.get("applicable"):
        lines.append(f"- 不适用：{diagnostics.get('reason', 'unknown')}。")
    else:
        lines.extend(
            [
                "> 本节使用全天路径，只能复盘曲线形状，不得倒灌前缀时间线。",
                "",
                "| 模型 | RMSE | AICc | ΔAICc | 参数撞边界 |",
                "|------|------|------|-------|------------|",
            ]
        )
        delta_by_model = {
            item.get("model"): item.get("delta_aicc")
            for item in diagnostics.get("ranking") or []
        }
        for name, payload in (diagnostics.get("models") or {}).items():
            lines.append(
                f"| {name} | {_display_number(payload.get('rmse'), 6)} | {_display_number(payload.get('aicc'), 2)} | {_display_number(delta_by_model.get(name), 2)} | {'是' if payload.get('boundary_hit') else '否'} |"
            )
        lines.append("")
        if diagnostics.get("best_model"):
            lines.append(
                f"- 样本内形状拟合第一：{diagnostics.get('best_model')}；区分强度：{diagnostics.get('selection_strength') or '无法判断'}。"
            )
        else:
            lines.append(
                f"- 本次不排名：{diagnostics.get('ranking_reason') or 'no_comparable_aicc'}。"
            )
        lines.append("- 这份排名不能识别量化身份，也未校正五分钟残差自相关和网格择优偏差。")

    final = (result.get("prefix_timeline") or [{}])[-1]
    lines.extend(["", "## 缺失与不适用证据", ""])
    combined = (final.get("missing_evidence") or []) + (
        final.get("not_applicable_evidence") or []
    )
    if combined:
        for item in combined:
            lines.append(f"- {item.get('field', '-')}: {item.get('reason', '-')}。")
    else:
        lines.append("- 当前路径字段无额外缺失。")

    lines.extend(["", "## 禁止推断", ""])
    for item in result.get("forbidden_inferences") or []:
        lines.append(f"- {item.get('name', '-')}: {item.get('reason', '-')}。")
    return "\n".join(lines).rstrip() + "\n"


def _load_fixture_cases(fixtures_path):
    root = Path(fixtures_path)
    raw_dir = root / "raw"
    if not raw_dir.is_dir():
        raise ValueError(f"fixture raw directory does not exist: {raw_dir}")
    paths = sorted(raw_dir.glob("*.json"))
    if not paths:
        raise ValueError(f"fixture raw directory has no JSON cases: {raw_dir}")
    cases = []
    seen_case_ids = set()
    for path in paths:
        try:
            case = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError(f"invalid fixture JSON: {path}") from error
        case_id = case.get("case_id") if isinstance(case, dict) else None
        if case_id in seen_case_ids:
            raise ValueError(f"duplicate fixture case_id: {case_id}")
        seen_case_ids.add(case_id)
        cases.append(case)
    return cases


def main(argv=None):
    parser = argparse.ArgumentParser(description="五分钟压力阶段离线回放")
    parser.add_argument("--fixtures", required=True, help="包含 raw/*.json 的 fixture 目录")
    parser.add_argument("--case-id", default="", help="只输出一个案例")
    args = parser.parse_args(argv)
    cases = _load_fixture_cases(args.fixtures)
    if args.case_id:
        cases = [case for case in cases if case.get("case_id") == args.case_id]
        if not cases:
            raise ValueError(f"fixture case_id does not exist: {args.case_id}")
    documents = [
        render_quant_pressure_replay_markdown(build_quant_pressure_replay(case))
        for case in cases
    ]
    print("\n---\n\n".join(document.rstrip() for document in documents))
    return 0


if __name__ == "__main__":
    sys.exit(main())
