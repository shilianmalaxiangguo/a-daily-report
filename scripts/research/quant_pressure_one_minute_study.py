from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import math
import sys
from collections import Counter
from pathlib import Path

try:
    from research.quant_pressure_replay_runtime import (
        _aicc_selection_strength,
        _best_grid_fit,
        _fit_features,
        _model_payload,
    )
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from research.quant_pressure_replay_runtime import (
        _aicc_selection_strength,
        _best_grid_fit,
        _fit_features,
        _model_payload,
    )

from domains.market_state.market_language_translation import (
    MARKET_LANGUAGE_DIRECTION_SLOPE_EPSILON_BP_PER_MIN,
    market_language_linear_slope_bp_per_minute,
    market_language_rolling_curvature_bp_per_minute2,
)


__all__ = [
    "WINDOW_SPECS",
    "build_case_study",
    "build_study",
    "build_window_reviews",
    "curve_shape_values",
    "expected_a_share_one_minute_bar_times",
    "main",
    "render_study_html",
    "validate_one_minute_case",
]


INPUT_SCHEMA_VERSION = "quant_pressure_one_minute_case.v1"
RESULT_SCHEMA_VERSION = "quant_pressure_one_minute_study.v1"
RESEARCH_AS_OF_DATE = "2026-07-11"
IMPLEMENTATION_REVIEW_DATE = "2026-07-12"
SOURCE_COVERAGE_TOLERANCE = 0.0001
PRESSURE_SLOPE_EPSILON_BP_PER_MIN = (
    MARKET_LANGUAGE_DIRECTION_SLOPE_EPSILON_BP_PER_MIN
)
PRESSURE_SURFACES = {
    "downward_acceleration_surface",
    "downward_pressure_with_short_term_cooling",
    "coherent_downward_surface",
    "rebound_inside_downward_pressure",
}
DEFAULT_FIXTURE_ROOT = (
    Path(__file__).resolve().parents[2]
    / "tests"
    / "fixtures"
    / "quant_pressure_one_minute"
)
DEFAULT_REPORT_PATH = (
    Path(__file__).resolve().parents[2]
    / "reports"
    / "research"
    / "quant-pressure-replay-study-20260711.html"
)

WINDOW_SPECS = (
    {
        "window_id": "opening",
        "label": "09:30-09:35",
        "start_time": "09:30",
        "end_time": "09:35",
        "role": "opening_observation",
        "subwindows": (),
    },
    {
        "window_id": "morning_diagnostic",
        "label": "09:45-10:10",
        "start_time": "09:45",
        "end_time": "10:10",
        "role": "morning_diagnosis_and_execution_context",
        "subwindows": (
            {
                "label": "前哨观察",
                "start_time": "09:45",
                "end_time": "09:50",
            },
            {
                "label": "主执行",
                "start_time": "09:50",
                "end_time": "10:10",
            },
        ),
    },
    {
        "window_id": "late_handling",
        "label": "14:30-14:55",
        "start_time": "14:30",
        "end_time": "14:55",
        "role": "late_risk_and_overnight_handling",
        "subwindows": (),
    },
)

AFTERNOON_RISK_OBSERVATION_START = "13:45"
AFTERNOON_RISK_CANDIDATE_END = "14:10"
AFTERNOON_RISK_SENSITIVITY_CUTOFFS = ("14:00", "14:05", "14:10", "14:20")

MODEL_LABELS = {
    "linear": "线性",
    "segmented": "单变化点分段",
    "finite_time_power": "有限时刻幂律",
    "sqrt_ellipse_proxy": "四分之一椭圆代理",
    "shifted_ellipse_arc": "平移椭圆弧",
    "exponential": "指数",
    "gompertz": "Gompertz",
    "critical_log": "临界对数",
    "ordinary_log": "普通对数",
}

DECLARED_CASES = {
    "sh603986_20260710_1m": {
        "fixture_stem": "sh603986_20260710",
        "code": "603986.SH",
        "name": "兆易创新",
        "trade_date": "2026-07-10",
        "previous_close": 663.49,
        "raw_source_rows_sha256": "afb669d63f315718d4b4cdf0ea6875c8c89714c474b52742abbfce1bbf92dafb",
        "normalized_minute_bars_sha256": "e57389067c894649b26fb6a83e89133d4fd514d32873eddedf983323499344b7",
        "source_metadata_sha256": "f04206e13646f71a137174c72f7f269ed5490bc5d3fc424a1e26ba861116274f",
        "validation_summary_sha256": "6c72746eb45238475ea85b2c9c873d16b5b63adf3c20d72567d0af47d6d47578",
        "t1_date": "2026-07-13",
        "t2_date": "2026-07-14",
    },
    "sh600584_20260710_1m": {
        "fixture_stem": "sh600584_20260710",
        "code": "600584.SH",
        "name": "长电科技",
        "trade_date": "2026-07-10",
        "previous_close": 103.52,
        "raw_source_rows_sha256": "fd2cc5e9a7a4bccfccf415284b45b6c517916f3941dfa00fb06638797cad9d0f",
        "normalized_minute_bars_sha256": "982a96ed7d8e9b43ad84dcabb5a3163950856e38cfc4d13b6c84c5b87782d31c",
        "source_metadata_sha256": "7f333e6c1b6e46c951d4aafdaf72260e9b6959fd74de345c835ec5039784356f",
        "validation_summary_sha256": "db398ee1bd4cf06717be2228d3e79849e4df11aa92449839a3f8b5b331f89f8c",
        "t1_date": "2026-07-13",
        "t2_date": "2026-07-14",
    },
    "sh000001_20260521_1m": {
        "fixture_stem": "sh000001_20260521",
        "code": "000001.SH",
        "name": "上证指数",
        "trade_date": "2026-05-21",
        "previous_close": 4162.185,
        "raw_source_rows_sha256": "79ed50eb5e4c2fae34ea6cdeea72e5554247a2513c8269281bf4859b76864979",
        "normalized_minute_bars_sha256": "ccecd6792a6cbb9061087cc2cba1a7a8280454c4c0488ea894dfe83041c75d86",
        "source_metadata_sha256": "8d9d3acdaada9fb3828042197efb2a7608260cdbc0bb9ce729a7ff28d01eea58",
        "validation_summary_sha256": "c66fd3937aeea75162a68491d4768d979ff7972d0c55b1cbe765bb710af45643",
    },
}


def _time_range(start, end):
    current = dt.datetime.combine(dt.date(2000, 1, 1), start)
    terminal = dt.datetime.combine(dt.date(2000, 1, 1), end)
    values = []
    while current <= terminal:
        values.append(current.strftime("%H:%M"))
        current += dt.timedelta(minutes=1)
    return values


def expected_a_share_one_minute_bar_times():
    return _time_range(dt.time(9, 31), dt.time(11, 30)) + _time_range(
        dt.time(13, 1), dt.time(15, 0)
    )


def _canonical_hash(value):
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _finite_number(value, *, field, allow_none=False):
    if value is None and allow_none:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field} must be a finite number")
    return number


def _close_enough(left, right, *, tolerance):
    return abs(float(left) - float(right)) <= tolerance


def validate_one_minute_case(case):
    if not isinstance(case, dict):
        raise ValueError("case must be an object")
    if case.get("schema_version") != INPUT_SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {INPUT_SCHEMA_VERSION}")
    if case.get("bar_period_minutes") != 1:
        raise ValueError("bar_period_minutes must be 1")
    declared = DECLARED_CASES.get(case.get("case_id"))
    if declared is None:
        raise ValueError("case_id is not one of the three declared research cases")
    instrument = case.get("instrument") or {}
    if instrument.get("type") not in {"stock", "index"}:
        raise ValueError("instrument.type must be stock or index")
    trade_date = str(case.get("trade_date") or "")
    if (
        instrument.get("code") != declared["code"]
        or instrument.get("name") != declared["name"]
        or trade_date != declared["trade_date"]
    ):
        raise ValueError("case identity does not match the declared research case")
    previous_close = _finite_number(case.get("previous_close"), field="previous_close")
    if previous_close <= 0 or not _close_enough(
        previous_close, declared["previous_close"], tolerance=1e-9
    ):
        raise ValueError("previous_close does not match the frozen prior-day fact")
    source = case.get("source") or {}
    expected_source_identity = {
        "provider": "pytdx.TdxHq_API",
        "server_name": "杭州电信主站J2",
        "host": "115.238.56.198",
        "port": 7709,
        "query_date": RESEARCH_AS_OF_DATE,
        "timezone": "Asia/Shanghai",
        "source_uri": "tdx://115.238.56.198:7709",
        "returned_batch_count": 800,
    }
    for field, expected in expected_source_identity.items():
        if source.get(field) != expected:
            raise ValueError(f"source.{field} does not match the frozen collection")
    if source.get("source_date") != trade_date:
        raise ValueError("source_date must equal trade_date")
    if source.get("bar_time_semantics") != "interval_end":
        raise ValueError("bar_time_semantics must be interval_end")
    if source.get("amount_unit") != "CNY":
        raise ValueError("amount_unit must be CNY")
    expected_volume_unit = "shares" if instrument.get("type") == "stock" else "unavailable"
    if source.get("volume_unit") != expected_volume_unit:
        raise ValueError("volume_unit does not match instrument type")
    expected_volume_semantics = (
        "interval" if instrument.get("type") == "stock" else "unavailable"
    )
    if source.get("volume_semantics") != expected_volume_semantics:
        raise ValueError("volume_semantics does not match instrument type")
    if source.get("amount_semantics") != "interval":
        raise ValueError("amount_semantics must be interval")
    expected_protocol = (
        f"get_security_bars(KLINE_TYPE_1MIN, market=1, code={instrument['code'][:6]}, start=0, count=800)"
        if instrument.get("type") == "stock"
        else "get_index_bars(KLINE_TYPE_1MIN, market=1, code=000001, start=8000, count=800)"
    )
    if source.get("source_protocol") != expected_protocol:
        raise ValueError("source_protocol does not match the declared case")
    if _canonical_hash(source) != declared["source_metadata_sha256"]:
        raise ValueError("source metadata does not match the frozen collection")

    bars = case.get("minute_bars")
    if not isinstance(bars, list) or len(bars) != 240:
        raise ValueError("minute_bars must contain 240 interval-end slots")
    expected_times = expected_a_share_one_minute_bar_times()
    observed_times = []
    for index, bar in enumerate(bars):
        if not isinstance(bar, dict):
            raise ValueError(f"minute_bars[{index}] must be an object")
        timestamp = str(bar.get("datetime") or "")
        try:
            parsed = dt.datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
        except ValueError as error:
            raise ValueError(f"minute_bars[{index}].datetime is invalid") from error
        if parsed.strftime("%Y-%m-%d") != trade_date:
            raise ValueError("minute bar date must equal trade_date")
        observed_times.append(parsed.strftime("%H:%M"))
        open_price = _finite_number(bar.get("open"), field=f"minute_bars[{index}].open")
        high_price = _finite_number(bar.get("high"), field=f"minute_bars[{index}].high")
        low_price = _finite_number(bar.get("low"), field=f"minute_bars[{index}].low")
        close_price = _finite_number(bar.get("close"), field=f"minute_bars[{index}].close")
        amount = _finite_number(bar.get("amount"), field=f"minute_bars[{index}].amount")
        volume = _finite_number(
            bar.get("volume"),
            field=f"minute_bars[{index}].volume",
            allow_none=instrument.get("type") == "index",
        )
        if min(open_price, high_price, low_price, close_price) <= 0:
            raise ValueError("prices must be positive")
        if high_price < max(open_price, close_price, low_price):
            raise ValueError("high must cover open, close and low")
        if low_price > min(open_price, close_price, high_price):
            raise ValueError("low must cover open, close and high")
        if amount < 0 or (volume is not None and volume < 0):
            raise ValueError("volume and amount must be non-negative")
        if instrument.get("type") == "index" and volume is not None:
            raise ValueError("index minute volume must remain unavailable")
    if observed_times != expected_times:
        raise ValueError("minute bar grid is incomplete or misordered")

    validation = case.get("validation_summary") or {}
    if validation.get("raw_source_rows_sha256") != declared["raw_source_rows_sha256"]:
        raise ValueError("raw source row hash does not match the frozen collection")
    normalized_hash = _canonical_hash(bars)
    if (
        validation.get("normalized_minute_bars_sha256") != normalized_hash
        or normalized_hash != declared["normalized_minute_bars_sha256"]
    ):
        raise ValueError("normalized minute bar hash mismatch")
    if validation.get("normalized_no_trade_sentinel_times") != ["14:59"]:
        raise ValueError("14:59 no-trade sentinel must be declared")
    sentinel = bars[expected_times.index("14:59")]
    if sentinel.get("amount") != 0.0:
        raise ValueError("14:59 sentinel amount must normalize to zero")
    if instrument.get("type") == "stock" and sentinel.get("volume") != 0.0:
        raise ValueError("14:59 sentinel volume must normalize to zero")

    aggregates = {
        "day_open": bars[0]["open"],
        "day_high": max(row["high"] for row in bars),
        "day_low": min(row["low"] for row in bars),
        "day_close": bars[-1]["close"],
        "total_amount": sum(row["amount"] for row in bars),
        "total_volume": (
            sum(row["volume"] for row in bars)
            if instrument.get("type") == "stock"
            else None
        ),
    }
    for field in ("day_open", "day_high", "day_low", "day_close"):
        if not _close_enough(aggregates[field], validation.get(field), tolerance=1e-9):
            raise ValueError(f"{field} validation mismatch")
    if not _close_enough(
        aggregates["total_amount"], validation.get("total_amount"), tolerance=1e-3
    ):
        raise ValueError("total_amount validation mismatch")
    if instrument.get("type") == "stock" and not _close_enough(
        aggregates["total_volume"], validation.get("total_volume"), tolerance=1e-3
    ):
        raise ValueError("total_volume validation mismatch")

    daily_reference = validation.get("daily_reference_ohlc") or []
    if len(daily_reference) != 4:
        raise ValueError("daily_reference_ohlc must contain four values")
    tolerance = float(validation.get("daily_reference_ohlc_tolerance") or 0.0)
    for observed, expected in zip(
        (
            aggregates["day_open"],
            aggregates["day_high"],
            aggregates["day_low"],
            aggregates["day_close"],
        ),
        daily_reference,
    ):
        if not _close_enough(observed, expected, tolerance=tolerance):
            raise ValueError("daily reference OHLC mismatch")
    daily_amount_ratio = float(validation.get("daily_amount_coverage_ratio") or 0.0)
    if abs(daily_amount_ratio - 1.0) > SOURCE_COVERAGE_TOLERANCE:
        raise ValueError("daily amount coverage is outside tolerance")
    daily_reference_amount = _finite_number(
        validation.get("daily_reference_amount"),
        field="validation_summary.daily_reference_amount",
    )
    if daily_reference_amount <= 0:
        raise ValueError("daily_reference_amount must be positive")
    expected_amount_ratio = aggregates["total_amount"] / daily_reference_amount
    if not _close_enough(
        daily_amount_ratio,
        expected_amount_ratio,
        tolerance=1e-12,
    ):
        raise ValueError("daily amount coverage ratio is inconsistent")
    if instrument.get("type") == "stock":
        daily_reference_volume = _finite_number(
            validation.get("daily_reference_volume_shares"),
            field="validation_summary.daily_reference_volume_shares",
        )
        if daily_reference_volume <= 0:
            raise ValueError("daily_reference_volume_shares must be positive")
        expected_volume_ratio = aggregates["total_volume"] / daily_reference_volume
        daily_volume_ratio = float(validation.get("daily_volume_coverage_ratio") or 0.0)
        if abs(daily_volume_ratio - 1.0) > SOURCE_COVERAGE_TOLERANCE:
            raise ValueError("daily volume coverage is outside tolerance")
        if not _close_enough(
            daily_volume_ratio,
            expected_volume_ratio,
            tolerance=1e-12,
        ):
            raise ValueError("daily volume coverage ratio is inconsistent")
    cross_server = validation.get("cross_server_validation") or {}
    expected_secondary_server = {
        "secondary_server_name": "杭州电信主站J3",
        "secondary_host": "218.75.126.9",
        "secondary_port": 7709,
    }
    for field, expected in expected_secondary_server.items():
        if cross_server.get(field) != expected:
            raise ValueError(f"cross-server {field} mismatch")
    if cross_server.get("row_count") != 240:
        raise ValueError("cross-server minute row count mismatch")
    if float(cross_server.get("max_ohlc_absolute_difference") or 0.0) > 0.01:
        raise ValueError("cross-server OHLC mismatch")
    if float(cross_server.get("max_volume_absolute_difference") or 0.0) > 1.0:
        raise ValueError("cross-server volume mismatch")
    if float(cross_server.get("max_amount_absolute_difference") or 0.0) > 1000.0:
        raise ValueError("cross-server amount mismatch")
    if not _close_enough(
        cross_server.get("primary_total_amount"),
        aggregates["total_amount"],
        tolerance=1e-3,
    ):
        raise ValueError("cross-server primary amount is inconsistent")
    secondary_total_amount = _finite_number(
        cross_server.get("secondary_total_amount"),
        field="validation_summary.cross_server_validation.secondary_total_amount",
    )
    if secondary_total_amount <= 0 or abs(
        secondary_total_amount - aggregates["total_amount"]
    ) > 1000.0:
        raise ValueError("cross-server secondary amount is inconsistent")
    if instrument.get("type") == "stock":
        cross_source = validation.get("cross_source") or {}
        if cross_source.get("source_date") != trade_date.replace("-", ""):
            raise ValueError("stock cross-source date mismatch")
        if cross_source.get("common_interval_end_close_match_count") != 240:
            raise ValueError("stock cross-source close path mismatch")
        cross_volume = _finite_number(
            cross_source.get("final_cumulative_volume_shares"),
            field="validation_summary.cross_source.final_cumulative_volume_shares",
        )
        cross_amount = _finite_number(
            cross_source.get("final_cumulative_amount"),
            field="validation_summary.cross_source.final_cumulative_amount",
        )
        if cross_volume <= 0 or cross_amount <= 0:
            raise ValueError("stock cross-source totals must be positive")
        if not _close_enough(
            cross_volume, daily_reference_volume, tolerance=1.0
        ) or not _close_enough(
            cross_amount, daily_reference_amount, tolerance=0.01
        ):
            raise ValueError("stock cross-source totals do not match daily reference")
        stock_volume_ratio = float(
            cross_source.get("tdx_to_tencent_volume_ratio") or 0.0
        )
        stock_amount_ratio = float(
            cross_source.get("tdx_to_tencent_amount_ratio") or 0.0
        )
        if (
            abs(stock_volume_ratio - 1.0) > SOURCE_COVERAGE_TOLERANCE
            or abs(stock_amount_ratio - 1.0) > SOURCE_COVERAGE_TOLERANCE
        ):
            raise ValueError("stock cross-source coverage is outside tolerance")
        if not _close_enough(
            stock_volume_ratio,
            aggregates["total_volume"] / cross_volume,
            tolerance=1e-12,
        ):
            raise ValueError("stock cross-source volume ratio is inconsistent")
        if not _close_enough(
            stock_amount_ratio,
            aggregates["total_amount"] / cross_amount,
            tolerance=1e-12,
        ):
            raise ValueError("stock cross-source amount ratio is inconsistent")
    else:
        cross_source = validation.get("cross_source") or {}
        if cross_source.get("source_date") != trade_date:
            raise ValueError("index cross-source date mismatch")
        five_minute_amount = _finite_number(
            cross_source.get("five_minute_total_amount"),
            field="validation_summary.cross_source.five_minute_total_amount",
        )
        index_amount_ratio = float(cross_source.get("tdx_to_sina_amount_ratio") or 0.0)
        if (
            five_minute_amount <= 0
            or not _close_enough(
                five_minute_amount, daily_reference_amount, tolerance=0.01
            )
            or abs(index_amount_ratio - 1.0) > SOURCE_COVERAGE_TOLERANCE
            or not _close_enough(
                index_amount_ratio,
                aggregates["total_amount"] / five_minute_amount,
                tolerance=1e-12,
            )
        ):
            raise ValueError("index cross-source amount ratio is inconsistent")

    if _canonical_hash(validation) != declared["validation_summary_sha256"]:
        raise ValueError("validation summary does not match the frozen collection")

    return {
        "status": "verified",
        "case_id": case.get("case_id"),
        "bar_count": len(bars),
        "source": source.get("provider"),
        "source_date": source.get("source_date"),
        "volume_usable": instrument.get("type") == "stock",
        "amount_usable": True,
        **aggregates,
    }


def curve_shape_values(model, xs, **parameters):
    values = [float(value) for value in xs]
    if model == "linear":
        return values
    if model == "finite_time_power":
        exponent = float(parameters["exponent_m"])
        critical_scale = float(parameters["critical_scale"])
        if exponent <= 0 or critical_scale <= max(values, default=0.0):
            raise ValueError("finite_time_power parameters are outside the domain")
        output = []
        for value in values:
            remaining = 1.0 - value / critical_scale
            if exponent < 1e-7:
                output.append(-math.log(remaining))
            else:
                output.append((1.0 - remaining**exponent) / exponent)
        return output
    if model == "sqrt_ellipse_proxy":
        critical_scale = float(parameters["critical_scale"])
        if critical_scale <= max(values, default=0.0):
            raise ValueError("sqrt_ellipse_proxy is outside the domain")
        return [
            1.0 - math.sqrt(max(0.0, 1.0 - (value / critical_scale) ** 2))
            for value in values
        ]
    if model == "shifted_ellipse_arc":
        center = float(parameters["center"])
        radius = float(parameters["radius"])
        if radius <= max((abs(value - center) for value in values), default=0.0):
            raise ValueError("shifted_ellipse_arc is outside the domain")
        return [
            math.sqrt(max(0.0, 1.0 - ((value - center) / radius) ** 2))
            for value in values
        ]
    if model == "exponential":
        rate = float(parameters["rate"])
        return [math.expm1(rate * value) for value in values]
    if model == "gompertz":
        rate = float(parameters["rate"])
        center = float(parameters["center"])
        return [math.exp(-math.exp(-rate * (value - center))) for value in values]
    if model == "critical_log":
        critical_scale = float(parameters["critical_scale"])
        if critical_scale <= max(values, default=0.0):
            raise ValueError("critical_log is outside the domain")
        return [-math.log(1.0 - value / critical_scale) for value in values]
    if model == "ordinary_log":
        rate = float(parameters["rate"])
        return [math.log1p(rate * value) for value in values]
    raise ValueError(f"unknown curve model: {model}")


def _residual_lag1(actual, predicted):
    residuals = [left - right for left, right in zip(actual, predicted)]
    if len(residuals) < 3:
        return None
    mean = sum(residuals) / len(residuals)
    centered = [value - mean for value in residuals]
    denominator = sum(value * value for value in centered)
    if denominator <= 1e-24:
        return None
    return sum(left * right for left, right in zip(centered[1:], centered[:-1])) / denominator


def _round(value, digits=6):
    if value is None:
        return None
    return round(float(value), digits)


def _fit_one_feature_model(
    *,
    model,
    xs,
    ys,
    candidates,
    parameter_count,
    bounds,
):
    prepared = []
    for stable_key, parameters in candidates:
        try:
            feature = curve_shape_values(model, xs, **parameters)
        except (ValueError, OverflowError):
            continue
        fit = _fit_features([[1.0, value] for value in feature], ys)
        prepared.append(
            {
                "fit": fit,
                "stable_key": stable_key,
                "parameters": parameters,
            }
        )
    best = _best_grid_fit(prepared)
    if not best:
        return _model_payload(
            fit=None,
            parameters={},
            parameter_count=parameter_count,
            observation_count=len(xs),
        )
    fit = best["fit"]
    parameters = {
        "intercept_bp": fit["coefficients"][0],
        "amplitude_bp": fit["coefficients"][1],
        **best["parameters"],
    }
    boundary_parameters = [
        name
        for name, (lower, upper) in bounds.items()
        if best["parameters"].get(name) in {lower, upper}
    ]
    payload = _model_payload(
        fit=fit,
        parameters=parameters,
        parameter_count=parameter_count,
        observation_count=len(xs),
        boundary_parameters=boundary_parameters,
    )
    payload["fitted_log_bp"] = [_round(value, 5) for value in fit["predictions"]]
    payload["residual_lag1"] = _round(
        _residual_lag1(ys, fit["predictions"]), 6
    )
    return payload


def _fit_curve_models(bars, *, scope, start_label=None, end_label=None):
    if len(bars) < 24:
        raise ValueError("curve diagnostics require at least 24 observations")
    closes = [float(row["close"]) for row in bars]
    observation_count = len(closes)
    xs = [index / (observation_count - 1) for index in range(observation_count)]
    ys = [math.log(value / closes[0]) * 10000.0 for value in closes]
    models = {}

    linear_fit = _fit_features([[1.0, value] for value in xs], ys)
    models["linear"] = _model_payload(
        fit=linear_fit,
        parameters={
            "intercept_bp": linear_fit["coefficients"][0],
            "slope_bp_per_normalized_path": linear_fit["coefficients"][1],
        },
        parameter_count=3,
        observation_count=observation_count,
    )
    models["linear"]["fitted_log_bp"] = [
        _round(value, 5) for value in linear_fit["predictions"]
    ]
    models["linear"]["residual_lag1"] = _round(
        _residual_lag1(ys, linear_fit["predictions"]), 6
    )

    segmented_candidates = []
    minimum_segment = max(8, observation_count // 20)
    for knot_index in range(minimum_segment, observation_count - minimum_segment):
        knot = xs[knot_index]
        fit = _fit_features(
            [[1.0, value, max(0.0, value - knot)] for value in xs],
            ys,
        )
        segmented_candidates.append(
            {
                "fit": fit,
                "stable_key": (knot_index,),
                "knot_index": knot_index,
                "knot": knot,
            }
        )
    segmented = _best_grid_fit(segmented_candidates)
    segmented_fit = segmented["fit"] if segmented else None
    segmented_parameters = {}
    if segmented:
        slope_before_normalized = segmented_fit["coefficients"][1]
        slope_after_normalized = (
            slope_before_normalized + segmented_fit["coefficients"][2]
        )
        minute_span = observation_count - 1
        slope_before_per_minute = slope_before_normalized / minute_span
        slope_after_per_minute = slope_after_normalized / minute_span
        if slope_after_per_minute < slope_before_per_minute - 1e-9:
            slope_change_direction = "more_negative"
        elif slope_after_per_minute > slope_before_per_minute + 1e-9:
            slope_change_direction = "less_negative"
        else:
            slope_change_direction = "unchanged"
        segmented_parameters = {
            "intercept_bp": segmented_fit["coefficients"][0],
            "slope_before": slope_before_normalized,
            "slope_delta": segmented_fit["coefficients"][2],
            "slope_before_bp_per_min": _round(slope_before_per_minute, 6),
            "slope_after_bp_per_min": _round(slope_after_per_minute, 6),
            "slope_change_direction": slope_change_direction,
            "knot_index": segmented["knot_index"],
            "knot_time": bars[segmented["knot_index"]]["datetime"][11:16],
        }
    models["segmented"] = _model_payload(
        fit=segmented_fit,
        parameters=segmented_parameters,
        parameter_count=5,
        observation_count=observation_count,
        boundary_parameters=(
            ["knot_index"]
            if segmented
            and segmented["knot_index"]
            in {minimum_segment, observation_count - minimum_segment - 1}
            else []
        ),
    )
    if segmented_fit:
        models["segmented"]["fitted_log_bp"] = [
            _round(value, 5) for value in segmented_fit["predictions"]
        ]
        models["segmented"]["residual_lag1"] = _round(
            _residual_lag1(ys, segmented_fit["predictions"]), 6
        )

    critical_scales = (1.02, 1.05, 1.1, 1.2, 1.35, 1.5, 2.0)
    exponents = (0.08, 0.15, 0.25, 0.35, 0.5, 0.65, 0.8, 1.0, 1.25, 1.5)
    models["finite_time_power"] = _fit_one_feature_model(
        model="finite_time_power",
        xs=xs,
        ys=ys,
        candidates=[
            (
                (exponent, critical_scale),
                {"exponent_m": exponent, "critical_scale": critical_scale},
            )
            for exponent in exponents
            for critical_scale in critical_scales
        ],
        parameter_count=5,
        bounds={
            "exponent_m": (exponents[0], exponents[-1]),
            "critical_scale": (critical_scales[0], critical_scales[-1]),
        },
    )
    models["sqrt_ellipse_proxy"] = _fit_one_feature_model(
        model="sqrt_ellipse_proxy",
        xs=xs,
        ys=ys,
        candidates=[
            ((critical_scale,), {"critical_scale": critical_scale})
            for critical_scale in critical_scales
        ],
        parameter_count=4,
        bounds={"critical_scale": (critical_scales[0], critical_scales[-1])},
    )
    ellipse_centers = (-0.25, -0.1, 0.0, 0.1, 0.2, 0.3, 0.4, 0.5)
    ellipse_candidates = []
    for center in ellipse_centers:
        minimum_radius = max(abs(center), abs(1.0 - center))
        for multiplier in (1.001, 1.02, 1.05, 1.1, 1.25, 1.5, 2.0):
            radius = minimum_radius * multiplier
            ellipse_candidates.append(
                (
                    (center, radius),
                    {"center": center, "radius": radius},
                )
            )
    models["shifted_ellipse_arc"] = _fit_one_feature_model(
        model="shifted_ellipse_arc",
        xs=xs,
        ys=ys,
        candidates=ellipse_candidates,
        parameter_count=5,
        bounds={
            "center": (ellipse_centers[0], ellipse_centers[-1]),
        },
    )
    exponential_rates = (0.25, 0.5, 1.0, 2.0, 3.0, 4.0, 6.0, 8.0)
    models["exponential"] = _fit_one_feature_model(
        model="exponential",
        xs=xs,
        ys=ys,
        candidates=[((rate,), {"rate": rate}) for rate in exponential_rates],
        parameter_count=4,
        bounds={"rate": (exponential_rates[0], exponential_rates[-1])},
    )
    gompertz_rates = (1.0, 2.0, 4.0, 6.0, 8.0, 12.0)
    gompertz_centers = (0.2, 0.35, 0.5, 0.65, 0.8, 1.0)
    models["gompertz"] = _fit_one_feature_model(
        model="gompertz",
        xs=xs,
        ys=ys,
        candidates=[
            ((rate, center), {"rate": rate, "center": center})
            for rate in gompertz_rates
            for center in gompertz_centers
        ],
        parameter_count=5,
        bounds={
            "rate": (gompertz_rates[0], gompertz_rates[-1]),
            "center": (gompertz_centers[0], gompertz_centers[-1]),
        },
    )
    models["critical_log"] = _fit_one_feature_model(
        model="critical_log",
        xs=xs,
        ys=ys,
        candidates=[
            ((critical_scale,), {"critical_scale": critical_scale})
            for critical_scale in critical_scales
        ],
        parameter_count=4,
        bounds={"critical_scale": (critical_scales[0], critical_scales[-1])},
    )
    ordinary_rates = (0.25, 0.5, 1.0, 2.0, 4.0, 8.0)
    models["ordinary_log"] = _fit_one_feature_model(
        model="ordinary_log",
        xs=xs,
        ys=ys,
        candidates=[((rate,), {"rate": rate}) for rate in ordinary_rates],
        parameter_count=4,
        bounds={"rate": (ordinary_rates[0], ordinary_rates[-1])},
    )

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
                "aicc": _round(item["aicc"], 6),
                "delta_aicc": _round(item["aicc"] - best_aicc, 6),
            }
            for item in raw_ranking
        ]
    for payload in models.values():
        payload.pop("_aicc_unrounded", None)
    return {
        "hindsight_only": True,
        "scope": scope,
        "fit_start": start_label or bars[0]["datetime"][11:16],
        "fit_end": end_label or bars[-1]["datetime"][11:16],
        "observation_count": observation_count,
        "response": "log_close_relative_to_segment_start_bp",
        "time_axis": "continuous_a_share_trading_minute_index",
        "models": models,
        "ranking": ranking,
        "best_model": ranking[0]["model"] if ranking else None,
        "selection_strength": _aicc_selection_strength(raw_ranking),
        "aicc_limit": "minute_price_level_residuals_are_serially_correlated_and_grid_selection_is_optimistic",
    }


def _linear_slope_bp_per_minute(rows, lookback_minutes):
    return market_language_linear_slope_bp_per_minute(rows, lookback_minutes)


def _rolling_slope_curvature_bp_per_minute2(rows, lookback_minutes=20):
    return market_language_rolling_curvature_bp_per_minute2(
        rows,
        lookback_minutes,
    )


def _negative_share(rows, lookback_minutes=10):
    selected = rows[-(lookback_minutes + 1) :]
    if len(selected) < lookback_minutes + 1:
        return None
    changes = [
        right["close"] - left["close"]
        for left, right in zip(selected[:-1], selected[1:])
    ]
    return _round(sum(value < 0 for value in changes) / len(changes), 4)


def _surface_label(slope_5, slope_15, curvature):
    if slope_15 is None:
        return "opening_sample_too_short"
    if slope_15 < -PRESSURE_SLOPE_EPSILON_BP_PER_MIN:
        if slope_5 is not None and slope_5 < -PRESSURE_SLOPE_EPSILON_BP_PER_MIN:
            if (
                curvature is not None
                and curvature < 0
                and slope_5 < slope_15 - PRESSURE_SLOPE_EPSILON_BP_PER_MIN
            ):
                return "downward_acceleration_surface"
            if curvature is not None and curvature < 0:
                return "downward_pressure_with_short_term_cooling"
            return "coherent_downward_surface"
        if slope_5 is not None and slope_5 > PRESSURE_SLOPE_EPSILON_BP_PER_MIN:
            return "rebound_inside_downward_pressure"
        return "downward_pressure_with_short_term_cooling"
    if (
        slope_5 is not None
        and slope_5 > PRESSURE_SLOPE_EPSILON_BP_PER_MIN
        and slope_15 > PRESSURE_SLOPE_EPSILON_BP_PER_MIN
    ):
        return "rising_or_repairing_surface"
    return "mixed_surface"


def _surface_snapshot(prefix):
    slope_5 = _linear_slope_bp_per_minute(prefix, 5)
    slope_15 = _linear_slope_bp_per_minute(prefix, 15)
    curvature = _rolling_slope_curvature_bp_per_minute2(prefix, 20)
    return {
        "slope_5m_bp_per_min": slope_5,
        "slope_15m_bp_per_min": slope_15,
        "curvature_20m_bp_per_min2": curvature,
        "observed_surface": _surface_label(slope_5, slope_15, curvature),
        "pressure_direction": (
            "downward"
            if slope_15 is not None
            and slope_15 < -PRESSURE_SLOPE_EPSILON_BP_PER_MIN
            else "upward"
            if slope_15 is not None
            and slope_15 > PRESSURE_SLOPE_EPSILON_BP_PER_MIN
            else "balanced"
            if slope_15 is not None
            else "unclear"
        ),
    }


def _pressure_events_from_states(states):
    events = []
    active = None
    consecutive_run = 0
    neutral_run = 0
    for index, state in enumerate(states):
        direction = state["pressure_direction"]
        is_candidate = direction == "downward"
        if active is not None:
            if direction == "balanced" and active["confirmed_index"] is not None:
                neutral_run += 1
                if neutral_run < 3:
                    continue
            if not is_candidate:
                active["invalidated_index"] = index
                events.append(active)
                active = None
                consecutive_run = 0
                neutral_run = 0
        if not is_candidate:
            continue
        if active is None:
            active = {
                "candidate_index": index,
                "confirmed_index": None,
                "follow_through_index": None,
                "invalidated_index": None,
            }
            consecutive_run = 1
            neutral_run = 0
        else:
            consecutive_run += 1
            neutral_run = 0
        candidate_close = float(states[active["candidate_index"]]["close"])
        elapsed_minutes = index - active["candidate_index"]
        if elapsed_minutes > 0 and active["follow_through_index"] is None:
            move_bp = math.log(float(state["close"]) / candidate_close) * 10000.0
            threshold = max(
                0.10,
                PRESSURE_SLOPE_EPSILON_BP_PER_MIN * elapsed_minutes,
            )
            if move_bp <= -threshold:
                active["follow_through_index"] = index
        if consecutive_run == 3:
            active["confirmed_index"] = index
    if active is not None:
        events.append(active)
    return events


def _pressure_states(bars, *, end_time):
    states = []
    prefix = []
    for row in bars:
        time_text = row["datetime"][11:16]
        if time_text > end_time:
            continue
        prefix.append(row)
        snapshot = _surface_snapshot(prefix)
        states.append(
            {
                "time": time_text,
                "close": float(row["close"]),
                "surface": snapshot["observed_surface"],
                "pressure_direction": snapshot["pressure_direction"],
                "is_pressure_candidate": snapshot["pressure_direction"]
                == "downward",
            }
        )
    return states


def _pressure_timeline(bars, *, start_time, end_time):
    states = _pressure_states(bars, end_time=end_time)
    events = _pressure_events_from_states(states)
    first_event = events[0] if events else None
    first_candidate = (
        states[first_event["candidate_index"]] if first_event is not None else None
    )
    first_inside_event = next(
        (
            event
            for event in events
            if start_time <= states[event["candidate_index"]]["time"] <= end_time
        ),
        None,
    )
    first_candidate_inside_window = (
        states[first_inside_event["candidate_index"]]
        if first_inside_event is not None
        else None
    )
    first_confirmation_time = (
        states[first_event["confirmed_index"]]["time"]
        if first_event is not None and first_event["confirmed_index"] is not None
        else None
    )
    first_follow_through_time = (
        states[first_event["follow_through_index"]]["time"]
        if first_event is not None and first_event["follow_through_index"] is not None
        else None
    )
    invalidation_count_inside_window = sum(
        event["invalidated_index"] is not None
        and start_time <= states[event["invalidated_index"]]["time"] <= end_time
        for event in events
    )
    active_event = next(
        (event for event in reversed(events) if event["invalidated_index"] is None),
        None,
    )
    active_run_start_time = (
        states[active_event["candidate_index"]]["time"] if active_event else None
    )
    active_confirmation_time = (
        states[active_event["confirmed_index"]]["time"]
        if active_event and active_event["confirmed_index"] is not None
        else None
    )
    active_follow_through_time = (
        states[active_event["follow_through_index"]]["time"]
        if active_event and active_event["follow_through_index"] is not None
        else None
    )
    active_run_length = (
        len(states) - active_event["candidate_index"] if active_event else 0
    )

    return {
        "candidate_definition": "fifteen_minute_slope_below_minus_0_05_bp_per_min",
        "confirmation_definition": "three_overlapping_fifteen_minute_slope_directions",
        "first_candidate_time": first_candidate["time"] if first_candidate else None,
        "first_candidate_surface": (
            first_candidate["surface"] if first_candidate else None
        ),
        "first_candidate_inside_window_time": (
            first_candidate_inside_window["time"]
            if first_candidate_inside_window
            else None
        ),
        "window_covers_first_candidate": bool(
            first_candidate and start_time <= first_candidate["time"] <= end_time
        ),
        "first_three_minute_confirmation_time": first_confirmation_time,
        "first_directional_follow_through_time": first_follow_through_time,
        "first_confirmation_quality": (
            "directional_follow_through"
            if first_confirmation_time and first_follow_through_time
            else "slope_persistence_only"
            if first_confirmation_time
            else "unconfirmed"
        ),
        "candidate_invalidation_count_inside_window": (
            invalidation_count_inside_window
        ),
        "active_pressure_run_start_time": active_run_start_time,
        "active_pressure_point_count": active_run_length,
        "active_pressure_elapsed_trading_minutes": max(0, active_run_length - 1),
        "active_run_started_before_window": bool(
            active_run_start_time and active_run_start_time < start_time
        ),
        "active_three_minute_confirmation_time": active_confirmation_time,
        "active_directional_follow_through_time": active_follow_through_time,
        "active_confirmation_quality": (
            "directional_follow_through"
            if active_confirmation_time and active_follow_through_time
            else "slope_persistence_only"
            if active_confirmation_time
            else "unconfirmed"
        ),
        "active_confirmation_at_cutoff": active_confirmation_time is not None,
    }


def _afternoon_risk_review(bars):
    states = _pressure_states(bars, end_time="15:00")
    events = _pressure_events_from_states(states)

    def event_time(event, key):
        index = event[key]
        return states[index]["time"] if index is not None else None

    afternoon_events = []
    for event in events:
        candidate_time = event_time(event, "candidate_index")
        confirmed_time = event_time(event, "confirmed_index")
        follow_through_time = event_time(event, "follow_through_index")
        invalidated_time = event_time(event, "invalidated_index")
        if candidate_time < "13:00" and (
            invalidated_time is not None
            and invalidated_time <= AFTERNOON_RISK_OBSERVATION_START
        ):
            continue
        complete_evidence_time = (
            max(confirmed_time, follow_through_time)
            if confirmed_time and follow_through_time
            else None
        )
        afternoon_events.append(
            {
                "candidate_time": candidate_time,
                "slope_confirmation_time": confirmed_time,
                "directional_follow_through_time": follow_through_time,
                "complete_evidence_time": complete_evidence_time,
                "invalidated_time": invalidated_time,
                "started_before_observation": (
                    candidate_time < AFTERNOON_RISK_OBSERVATION_START
                ),
                "confirmation_quality": (
                    "directional_follow_through"
                    if confirmed_time and follow_through_time
                    else "slope_persistence_only"
                    if confirmed_time
                    else "unconfirmed"
                ),
            }
        )

    def is_active_at(event, cutoff):
        return event["candidate_time"] <= cutoff and (
            event["invalidated_time"] is None
            or event["invalidated_time"] > cutoff
        )

    def has_complete_evidence_by(event, cutoff):
        complete_time = event["complete_evidence_time"]
        return complete_time is not None and complete_time <= cutoff

    def captured_between(event, start_time, cutoff):
        complete_time = event["complete_evidence_time"]
        if complete_time is None or complete_time > cutoff:
            return False
        if event["invalidated_time"] is not None and event["invalidated_time"] <= start_time:
            return False
        return max(complete_time, start_time) <= cutoff

    cutoff_checks = []
    for cutoff in AFTERNOON_RISK_SENSITIVITY_CUTOFFS:
        active_event = next(
            (
                event
                for event in reversed(afternoon_events)
                if is_active_at(event, cutoff)
                and has_complete_evidence_by(event, cutoff)
            ),
            None,
        )
        captured = any(
            captured_between(
                event,
                AFTERNOON_RISK_OBSERVATION_START,
                cutoff,
            )
            for event in afternoon_events
        )
        cutoff_checks.append(
            {
                "cutoff": cutoff,
                "active_complete_evidence_at_cutoff": active_event is not None,
                "captured_complete_evidence_since_observation": captured,
                "active_candidate_time": (
                    active_event["candidate_time"] if active_event else None
                ),
            }
        )

    return {
        "observation_start": AFTERNOON_RISK_OBSERVATION_START,
        "candidate_end": AFTERNOON_RISK_CANDIDATE_END,
        "status": "three_case_research_candidate_only",
        "active_complete_evidence_at_observation_start": any(
            is_active_at(event, AFTERNOON_RISK_OBSERVATION_START)
            and has_complete_evidence_by(event, AFTERNOON_RISK_OBSERVATION_START)
            for event in afternoon_events
        ),
        "events": afternoon_events,
        "cutoff_checks": cutoff_checks,
    }


def _review_one_window(bars, *, previous_close, start_time, end_time):
    prefix = [row for row in bars if row["datetime"][11:16] <= end_time]
    if not prefix:
        raise ValueError(f"no bars at or before {end_time}")
    if start_time == "09:30":
        anchor_price = float(bars[0]["open"])
        path = [row for row in bars if row["datetime"][11:16] <= end_time]
        amount_rows = path
    else:
        anchor = next(
            (row for row in bars if row["datetime"][11:16] == start_time), None
        )
        if anchor is None:
            raise ValueError(f"missing window anchor {start_time}")
        anchor_price = float(anchor["close"])
        path = [
            row
            for row in bars
            if start_time <= row["datetime"][11:16] <= end_time
        ]
        amount_rows = [
            row
            for row in bars
            if start_time < row["datetime"][11:16] <= end_time
        ]
    end_row = path[-1]
    prefix_peak = max(prefix, key=lambda row: row["high"])
    if start_time == "09:30":
        range_high = max(row["high"] for row in path)
        range_low = min(row["low"] for row in path)
    else:
        range_high = max(
            [anchor_price, *(float(row["high"]) for row in amount_rows)]
        )
        range_low = min(
            [anchor_price, *(float(row["low"]) for row in amount_rows)]
        )
    surface = _surface_snapshot(prefix)
    return {
        "start_time": start_time,
        "end_time": end_time,
        "causal_cutoff": end_row["datetime"],
        "known_at_end_only": True,
        "path_point_count": len(path),
        "anchor_price": _round(anchor_price, 4),
        "end_price": _round(end_row["close"], 4),
        "window_return_pct": _round(
            (float(end_row["close"]) / anchor_price - 1.0) * 100.0, 4
        ),
        "window_range_pct": _round(
            (range_high - range_low) / anchor_price * 100.0,
            4,
        ),
        "window_amount_cny": _round(sum(row["amount"] for row in amount_rows), 2),
        "cumulative_amount_cny": _round(sum(row["amount"] for row in prefix), 2),
        "drawdown_from_known_peak_pct": _round(
            (float(end_row["close"]) / float(prefix_peak["high"]) - 1.0) * 100.0,
            4,
        ),
        "known_peak_time": prefix_peak["datetime"][11:16],
        "known_peak_price": _round(prefix_peak["high"], 4),
        "slope_5m_bp_per_min": surface["slope_5m_bp_per_min"],
        "slope_15m_bp_per_min": surface["slope_15m_bp_per_min"],
        "slope_30m_bp_per_min": _linear_slope_bp_per_minute(prefix, 30),
        "curvature_20m_bp_per_min2": surface[
            "curvature_20m_bp_per_min2"
        ],
        "negative_minute_share_last_10": _negative_share(prefix, 10),
        "observed_surface": surface["observed_surface"],
        "pressure_timeline": _pressure_timeline(
            bars,
            start_time=start_time,
            end_time=end_time,
        ),
        "quant_identity_confirmed": False,
    }


def build_window_reviews(bars, *, previous_close=None):
    del previous_close
    reviews = []
    for spec in WINDOW_SPECS:
        review = {
            "window_id": spec["window_id"],
            "label": spec["label"],
            "role": spec["role"],
            **_review_one_window(
                bars,
                previous_close=None,
                start_time=spec["start_time"],
                end_time=spec["end_time"],
            ),
        }
        review["subwindows"] = [
            {
                "label": child["label"],
                **_review_one_window(
                    bars,
                    previous_close=None,
                    start_time=child["start_time"],
                    end_time=child["end_time"],
                ),
            }
            for child in spec["subwindows"]
        ]
        reviews.append(review)
    return reviews


def _future_window_followups(bars, *, peak_index, trough_index):
    time_to_index = {row["datetime"][11:16]: index for index, row in enumerate(bars)}
    followups = []
    peak_price = float(bars[peak_index]["close"])
    trough_price = float(bars[trough_index]["close"])
    full_decline_bp = abs(math.log(trough_price / peak_price) * 10000.0)
    for spec in WINDOW_SPECS:
        end_index = time_to_index[spec["end_time"]]
        end_price = float(bars[end_index]["close"])
        outcomes = {}
        for horizon in (5, 10, 20):
            target = end_index + horizon
            outcomes[f"next_{horizon}m_return_pct"] = (
                _round((float(bars[target]["close"]) / end_price - 1.0) * 100.0, 4)
                if target < len(bars)
                else None
            )
        if end_index <= peak_index:
            risk_completion_pct = 0.0
            cutoff_relation = "before_objective_peak"
        elif end_index >= trough_index:
            risk_completion_pct = 100.0
            cutoff_relation = "at_or_after_objective_trough"
        else:
            completed_bp = abs(math.log(end_price / peak_price) * 10000.0)
            risk_completion_pct = min(
                100.0,
                max(0.0, completed_bp / full_decline_bp * 100.0),
            )
            cutoff_relation = "inside_objective_decline"
        later_trough_index = min(
            range(end_index, len(bars)), key=lambda index: bars[index]["close"]
        )
        later_trough_price = float(bars[later_trough_index]["close"])
        followups.append(
            {
                "window_id": spec["window_id"],
                "label": spec["label"],
                "hindsight_only": True,
                "objective_peak_time": bars[peak_index]["datetime"][11:16],
                "objective_trough_time": bars[trough_index]["datetime"][11:16],
                "cutoff_relation": cutoff_relation,
                "objective_decline_completed_pct": _round(
                    risk_completion_pct, 2
                ),
                "later_trough_time": bars[later_trough_index]["datetime"][11:16],
                "remaining_drawdown_to_later_trough_pct": _round(
                    (later_trough_price / end_price - 1.0) * 100.0,
                    4,
                ),
                **outcomes,
            }
        )
    return followups


def _point_extreme(bars, field, *, choose_max):
    chooser = max if choose_max else min
    row = chooser(bars, key=lambda item: item[field])
    return {"time": row["datetime"][11:16], "price": _round(row[field], 4)}


def _start_sensitivity(bars, peak_index, trough_index):
    starts = []
    for offset in (-5, 0, 5, 10, 20, 30):
        index = max(0, peak_index + offset)
        if trough_index - index + 1 >= 30:
            starts.append(index)
    rows = []
    for index in sorted(set(starts)):
        diagnostics = _fit_curve_models(
            bars[index : trough_index + 1],
            scope="decline_start_sensitivity",
            start_label=bars[index]["datetime"][11:16],
            end_label=bars[trough_index]["datetime"][11:16],
        )
        rows.append(
            {
                "start_time": bars[index]["datetime"][11:16],
                "observation_count": diagnostics["observation_count"],
                "best_model": diagnostics["best_model"],
                "selection_strength": diagnostics["selection_strength"],
                "top_two": diagnostics["ranking"][:2],
            }
        )
    winner_counts = Counter(row["best_model"] for row in rows if row["best_model"])
    return {
        "hindsight_only": True,
        "rows": rows,
        "winner_counts": dict(sorted(winner_counts.items())),
        "stable_single_winner": len(winner_counts) == 1,
    }


def build_case_study(case):
    quality = validate_one_minute_case(case)
    bars = case["minute_bars"]
    peak_index = max(range(len(bars)), key=lambda index: bars[index]["close"])
    trough_index = min(
        range(peak_index, len(bars)), key=lambda index: bars[index]["close"]
    )
    if trough_index - peak_index + 1 < 24:
        trough_index = len(bars) - 1
    decline_bars = bars[peak_index : trough_index + 1]
    previous_close = float(case["previous_close"])
    path_summary = {
        "day_open": {"time": "09:30", "price": _round(bars[0]["open"], 4)},
        "day_high": _point_extreme(bars, "high", choose_max=True),
        "day_low": _point_extreme(bars, "low", choose_max=False),
        "day_close": {"time": bars[-1]["datetime"][11:16], "price": bars[-1]["close"]},
        "peak_close": {
            "time": bars[peak_index]["datetime"][11:16],
            "price": bars[peak_index]["close"],
        },
        "trough_close_after_peak": {
            "time": bars[trough_index]["datetime"][11:16],
            "price": bars[trough_index]["close"],
        },
        "daily_return_pct": _round((bars[-1]["close"] / previous_close - 1.0) * 100.0, 4),
        "peak_to_trough_pct": _round(
            (bars[trough_index]["close"] / bars[peak_index]["close"] - 1.0) * 100.0,
            4,
        ),
        "legacy_five_minute_low_bar_end": (
            "14:55" if case["case_id"] == "sh000001_20260521_1m" else None
        ),
    }
    points = [
        {
            "time": row["datetime"][11:16],
            "close": row["close"],
            "low": row["low"],
            "amount_cny": row["amount"],
            "log_bp_from_previous_close": _round(
                math.log(row["close"] / previous_close) * 10000.0, 4
            ),
        }
        for row in bars
    ]
    return {
        "case_id": case["case_id"],
        "instrument": case["instrument"],
        "trade_date": case["trade_date"],
        "previous_close": previous_close,
        "data_quality": quality,
        "source": case["source"],
        "validation_summary": case["validation_summary"],
        "points": points,
        "path_summary": path_summary,
        "model_diagnostics": {
            "full_day": _fit_curve_models(bars, scope="full_day"),
            "decline_segment": _fit_curve_models(
                decline_bars,
                scope="objective_peak_close_to_later_trough_close",
                start_label=bars[peak_index]["datetime"][11:16],
                end_label=bars[trough_index]["datetime"][11:16],
            ),
            "start_sensitivity": _start_sensitivity(bars, peak_index, trough_index),
        },
        "window_reviews": build_window_reviews(bars, previous_close=previous_close),
        "afternoon_risk_review": _afternoon_risk_review(bars),
        "window_followups": _future_window_followups(
            bars,
            peak_index=peak_index,
            trough_index=trough_index,
        ),
        "forbidden_inferences": [
            "quant_account_identity",
            "quant_turnover_share",
            "order_trigger_chain",
            "stable_strategy_win_rate",
        ],
    }


def build_study(fixture_root=DEFAULT_FIXTURE_ROOT):
    fixture_root = Path(fixture_root)
    loaded = {
        path.stem: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((fixture_root / "raw").glob("*.json"))
    }
    order = [
        "sh603986_20260710",
        "sh600584_20260710",
        "sh000001_20260521",
    ]
    if set(loaded) != set(order):
        raise ValueError("fixture directory must contain the three declared cases")
    cases = [build_case_study(loaded[key]) for key in order]
    decline_winners = [
        case["model_diagnostics"]["decline_segment"]["best_model"] for case in cases
    ]
    stable_flags = [
        case["model_diagnostics"]["start_sensitivity"]["stable_single_winner"]
        for case in cases
    ]
    future_observations = []
    for case in cases[:2]:
        declared = DECLARED_CASES[case["case_id"]]
        t1_date = declared["t1_date"]
        t2_date = declared["t2_date"]
        future_observations.append(
            {
                "case_id": case["case_id"],
                "signal_date": case["trade_date"],
                "t1_date": t1_date,
                "t2_date": t2_date,
                "status": "future_unobserved",
                "as_of_date": RESEARCH_AS_OF_DATE,
            }
        )
    cutoff_sensitivity = []
    for cutoff in AFTERNOON_RISK_SENSITIVITY_CUTOFFS:
        checks = {
            case["case_id"]: next(
                row
                for row in case["afternoon_risk_review"]["cutoff_checks"]
                if row["cutoff"] == cutoff
            )
            for case in cases
        }
        active_case_ids = [
            case_id
            for case_id, check in checks.items()
            if check["active_complete_evidence_at_cutoff"]
        ]
        captured_case_ids = [
            case_id
            for case_id, check in checks.items()
            if check["captured_complete_evidence_since_observation"]
        ]
        cutoff_sensitivity.append(
            {
                "cutoff": cutoff,
                "active_at_cutoff_case_ids": active_case_ids,
                "active_at_cutoff_case_count": len(active_case_ids),
                "captured_since_observation_case_ids": captured_case_ids,
                "captured_since_observation_case_count": len(captured_case_ids),
            }
        )
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "as_of_date": RESEARCH_AS_OF_DATE,
        "cases": cases,
        "formula_synthesis": {
            "decline_segment_winners": decline_winners,
            "all_start_sensitivity_stable": all(stable_flags),
            "single_universal_formula_supported": False,
            "single_universal_formula_rejection_reason": (
                "three_pressure_cases_and_a_flexible_segmented_winner_do_not_establish_a_universal_law"
            ),
            "intraday_primary_method": "rolling_one_sided_slope_curvature_and_segment_change",
            "shape_research_parent_family": "normalized_finite_time_power",
            "identity_limit": "shape_fit_cannot_confirm_quant_accounts_or_cause",
        },
        "window_synthesis": {
            "opening": "opening_observation_not_curve_identification",
            "morning_diagnostic": "early_pressure_diagnosis_not_afternoon_shock_prediction",
            "late_handling": "overnight_risk_and_tail_state_not_early_exit",
            "timing_evidence_status": "three_cases_do_not_conflict_but_do_not_validate_tradable_lead_time",
        },
        "afternoon_risk_synthesis": {
            "candidate_range": (
                f"{AFTERNOON_RISK_OBSERVATION_START}-{AFTERNOON_RISK_CANDIDATE_END}"
            ),
            "status": "research_candidate_not_validated_trading_window",
            "formal_windows_unchanged": True,
            "slope_threshold_status": "uncalibrated_research_threshold",
            "active_at_observation_start_case_ids": [
                case["case_id"]
                for case in cases
                if case["afternoon_risk_review"][
                    "active_complete_evidence_at_observation_start"
                ]
            ],
            "cutoff_sensitivity": cutoff_sensitivity,
            "decision_branches": [
                {
                    "branch_id": "downward_risk",
                    "required_conditions": [
                        "downward_event_has_slope_persistence",
                        "directional_price_follow_through_present",
                        "corroboration_matches_force_scope",
                        "rebound_recovery_failed",
                        "event_not_invalidated",
                        "existing_exit_conditions_allow_action",
                    ],
                    "scope_rule": "single_stock_evidence_does_not_upgrade_to_market_force",
                    "research_handling": "observation_only_risk_reduction_or_exit_candidate",
                },
                {
                    "branch_id": "upward_trend",
                    "required_conditions": [
                        "upward_short_and_medium_slope",
                        "vwap_residency_present",
                        "breadth_and_participation_match_force_scope",
                    ],
                    "research_handling": "continue_holding",
                },
                {
                    "branch_id": "conflicted_or_invalidated",
                    "evidence_patterns": [
                        "false_candidate",
                        "fast_repair",
                        "scope_conflict",
                    ],
                    "research_handling": "defer_to_late_handling_window",
                },
            ],
        },
        "source_availability": [
            {
                "provider": "Tushare official historical minute APIs",
                "one_minute_capability": True,
                "stock_endpoint": "stk_mins",
                "index_endpoint": "idx_mins",
                "supported_frequencies": ["1min", "5min", "15min", "30min", "60min"],
                "maximum_rows_per_request": 8000,
                "document_ids": {"stock": 370, "index": 419},
            },
            {
                "provider": "current project Tushare channel and wrapper",
                "stock_mins_compat_result": "empty_frame_for_two_stock_cases",
                "stk_mins_result": "historical_minute_data_not_enabled_for_current_account",
                "idx_mins_result": "empty_frame_for_index_case",
                "current_wrapper_result": "zero_usable_bars_for_three_cases",
                "wrapper_limits": [
                    "empty_stock_mins_frame_stops_before_stk_mins_fallback",
                    "index_path_does_not_call_idx_mins",
                ],
            },
            {
                "provider": "pytdx TdxHq_API",
                "one_minute_capability": True,
                "current_account_status": "public_quote_server_verified",
                "observed_result": "240_interval_end_slots_for_three_cases",
            },
        ],
        "strategy_research": {
            "status": "research_protocol_not_validated_arbitrage",
            "future_observations": future_observations,
            "protocol": [
                {
                    "stage": "T+0",
                    "rule": "只识别压力表象、降温与修复质量；加速本身用于回避，不直接生成次日抄底资格。",
                },
                {
                    "stage": "T+1",
                    "rule": "只有板块、相对强度和承接继续确认才给 B1；B2 只在进一步确认后补。",
                },
                {
                    "stage": "T+2",
                    "rule": "固定卖出仍是待检验假说，必须与压力半衰期、可成交性和单账户资金占用一起回测。",
                },
            ],
            "account_overlap_options": [
                "单仓持有期间跳过重叠新信号",
                "两个 50% 资金槽交替",
                "T+2 开盘先处理旧仓再判断新信号，但这会改变原退出规则",
            ],
        },
    }


def _escape(value):
    return html.escape(str(value), quote=True)


def _fmt(value, digits=2, suffix=""):
    if value is None:
        return "—"
    return f"{float(value):.{digits}f}{suffix}"


def _surface_cn(value):
    return {
        "opening_sample_too_short": "样本过短",
        "downward_acceleration_surface": "下跌加速表象",
        "downward_pressure_with_short_term_cooling": "下压仍在、短线降温",
        "coherent_downward_surface": "连续下压表象",
        "rebound_inside_downward_pressure": "下压中的短线回抽",
        "rising_or_repairing_surface": "上行或修复表象",
        "mixed_surface": "方向混合",
    }.get(value, value)


def _confirmation_quality_cn(value):
    return {
        "directional_follow_through": "斜率连续 + 价格同向延续",
        "slope_persistence_only": "仅重叠斜率连续",
        "unconfirmed": "未形成",
    }.get(value, value)


def _window_display_label(review):
    if review["window_id"] == "morning_diagnostic":
        return "09:45-09:50 前哨 + 09:50-10:10 正式"
    return review["label"]


def _svg_polyline(points):
    return " ".join(f"{x:.2f},{y:.2f}" for x, y in points)


def _path_svg(case, *, width=860, height=280):
    points = case["points"]
    closes = [float(row["close"]) for row in points]
    lows = [float(row["low"]) for row in points]
    margin = {"left": 60, "right": 18, "top": 22, "bottom": 38}
    plot_w = width - margin["left"] - margin["right"]
    plot_h = height - margin["top"] - margin["bottom"]
    low = min(lows)
    high = max(closes)
    padding = max((high - low) * 0.08, high * 0.001)
    low -= padding
    high += padding

    def x_at(index):
        return margin["left"] + index / (len(points) - 1) * plot_w

    def y_at(value):
        return margin["top"] + (high - value) / (high - low) * plot_h

    path_points = [(x_at(index), y_at(value)) for index, value in enumerate(closes)]
    time_to_index = {row["time"]: index for index, row in enumerate(points)}
    shades = []
    shade_specs = (
        ("09:30", "09:35", "window-a"),
        ("09:45", "09:50", "window-scout"),
        ("09:50", "10:10", "window-b"),
        ("14:30", "14:55", "window-c"),
    )
    for start_time, end_time, css_class in shade_specs:
        start = 0 if start_time == "09:30" else time_to_index[start_time]
        end = time_to_index[end_time]
        x = x_at(start)
        span = max(2.0, x_at(end) - x)
        shades.append(
            f'<rect class="{css_class}" x="{x:.2f}" y="{margin["top"]}" width="{span:.2f}" height="{plot_h}" />'
        )
    grid = []
    for ratio in (0.0, 0.5, 1.0):
        value = high - ratio * (high - low)
        y = y_at(value)
        grid.append(
            f'<line class="chart-grid" x1="{margin["left"]}" y1="{y:.2f}" x2="{width-margin["right"]}" y2="{y:.2f}" />'
        )
        grid.append(
            f'<text class="axis-label" x="{margin["left"]-8}" y="{y+4:.2f}" text-anchor="end">{value:.2f}</text>'
        )
    ticks = []
    for label in ("09:31", "10:10", "14:30", "15:00"):
        x = x_at(time_to_index[label])
        ticks.append(
            f'<text class="axis-label" x="{x:.2f}" y="{height-12}" text-anchor="middle">{label}</text>'
        )
    lunch_x = (
        x_at(time_to_index["11:30"]) + x_at(time_to_index["13:01"])
    ) / 2.0
    ticks.append(
        f'<text class="axis-label" x="{lunch_x:.2f}" y="{height-12}" text-anchor="middle">11:30 / 13:01</text>'
    )
    peak = case["path_summary"]["peak_close"]
    low_point = case["path_summary"]["day_low"]
    peak_x = x_at(time_to_index[peak["time"]])
    peak_y = y_at(peak["price"])
    low_x = x_at(time_to_index[low_point["time"]])
    low_y = y_at(low_point["price"])
    title = f'{case["trade_date"]} {case["instrument"]["name"]} 一分钟收盘路径'
    return f"""
<svg class="price-chart" viewBox="0 0 {width} {height}" role="img" aria-labelledby="path-{_escape(case['case_id'])}-title path-{_escape(case['case_id'])}-desc">
  <title id="path-{_escape(case['case_id'])}-title">{_escape(title)}</title>
  <desc id="path-{_escape(case['case_id'])}-desc">连续交易分钟横轴。四段阴影依次表示开盘正式窗口、早盘前哨观察、早盘正式窗口和尾盘正式窗口；标记客观收盘峰值和日内最低。</desc>
  {''.join(shades)}
  {''.join(grid)}
  <polyline class="price-line" points="{_svg_polyline(path_points)}" />
  <circle class="peak-mark" cx="{peak_x:.2f}" cy="{peak_y:.2f}" r="4" />
  <text class="point-label" x="{peak_x:.2f}" y="{max(14, peak_y-9):.2f}" text-anchor="middle">峰 {peak['time']}</text>
  <circle class="low-mark" cx="{low_x:.2f}" cy="{low_y:.2f}" r="4" />
  <text class="point-label" x="{low_x:.2f}" y="{min(height-42, low_y+18):.2f}" text-anchor="middle">低 {low_point['time']}</text>
  {''.join(ticks)}
</svg>
"""


def _model_svg(case, *, scope="decline_segment", width=860, height=282):
    diagnostics = case["model_diagnostics"][scope]
    ranking = diagnostics["ranking"][:3]
    models = diagnostics["models"]
    actual_count = diagnostics["observation_count"]
    case_points = case["points"]
    start_time = diagnostics["fit_start"]
    end_time = diagnostics["fit_end"]
    start_index = next(index for index, row in enumerate(case_points) if row["time"] == start_time)
    end_index = next(index for index, row in enumerate(case_points) if row["time"] == end_time)
    selected = case_points[start_index : end_index + 1]
    base = float(selected[0]["close"])
    actual = [math.log(float(row["close"]) / base) * 10000.0 for row in selected]
    all_values = list(actual)
    for item in ranking:
        all_values.extend(models[item["model"]].get("fitted_log_bp") or [])
    margin = {"left": 62, "right": 18, "top": 62, "bottom": 38}
    plot_w = width - margin["left"] - margin["right"]
    plot_h = height - margin["top"] - margin["bottom"]
    low = min(all_values)
    high = max(all_values)
    pad = max((high - low) * 0.08, 5.0)
    low -= pad
    high += pad

    def x_at(index):
        return margin["left"] + index / max(1, actual_count - 1) * plot_w

    def y_at(value):
        return margin["top"] + (high - value) / (high - low) * plot_h

    lines = [
        f'<polyline class="fit-actual" points="{_svg_polyline([(x_at(i), y_at(v)) for i, v in enumerate(actual)])}" />'
    ]
    classes = ("fit-one", "fit-two", "fit-three")
    legend = ["实线：实际"]
    visible_legend = [("实际", "fit-actual")]
    for css_class, item in zip(classes, ranking):
        fitted = models[item["model"]].get("fitted_log_bp") or []
        lines.append(
            f'<polyline class="{css_class}" points="{_svg_polyline([(x_at(i), y_at(v)) for i, v in enumerate(fitted)])}" />'
        )
        legend.append(
            f"{MODEL_LABELS[item['model']]} Δ{item['delta_aicc']:.1f}"
        )
        visible_legend.append(
            (f"{MODEL_LABELS[item['model']]} Δ{item['delta_aicc']:.1f}", css_class)
        )
    legend_width = plot_w / max(1, len(visible_legend))
    legend_markup = []
    for index, (label, css_class) in enumerate(visible_legend):
        x = margin["left"] + index * legend_width
        legend_markup.append(
            f'<line class="{css_class}" x1="{x:.2f}" y1="25" x2="{x+24:.2f}" y2="25" />'
        )
        legend_markup.append(
            f'<text class="chart-legend-label" x="{x+31:.2f}" y="29">{_escape(label)}</text>'
        )
    scope_label = "全日" if scope == "full_day" else "客观下降段"
    title = f'{case["trade_date"]} {case["instrument"]["name"]} {scope_label}公式拟合'
    return f"""
<svg class="model-chart" viewBox="0 0 {width} {height}" role="img" aria-labelledby="model-{_escape(case['case_id'])}-{_escape(scope)}-title model-{_escape(case['case_id'])}-{_escape(scope)}-desc">
  <title id="model-{_escape(case['case_id'])}-{_escape(scope)}-title">{_escape(title)}</title>
  <desc id="model-{_escape(case['case_id'])}-{_escape(scope)}-desc">{_escape(scope_label)}实际对数基点路径与样本内前三种公式拟合。{_escape('；'.join(legend))}</desc>
  {''.join(legend_markup)}
  <line class="chart-grid" x1="{margin['left']}" y1="{y_at(0):.2f}" x2="{width-margin['right']}" y2="{y_at(0):.2f}" />
  {''.join(lines)}
  <text class="axis-label" x="{margin['left']}" y="{height-12}" text-anchor="start">{start_time}</text>
  <text class="axis-label" x="{width-margin['right']}" y="{height-12}" text-anchor="end">{end_time}</text>
  <text class="axis-label" x="{margin['left']-8}" y="{margin['top']+4}" text-anchor="end">{high:.0f} bp</text>
  <text class="axis-label" x="{margin['left']-8}" y="{height-margin['bottom']}" text-anchor="end">{low:.0f} bp</text>
</svg>
"""


def _family_svg(*, width=860, height=270):
    xs = [index / 100 for index in range(101)]
    series = [
        ("m=1 线性", curve_shape_values("finite_time_power", xs, exponent_m=1.0, critical_scale=1.1), "family-linear"),
        ("m=0.5 根号临界", curve_shape_values("finite_time_power", xs, exponent_m=0.5, critical_scale=1.1), "family-sqrt"),
        ("m=0.1 接近临界对数", curve_shape_values("finite_time_power", xs, exponent_m=0.1, critical_scale=1.1), "family-critical"),
        ("普通对数（前快后慢）", curve_shape_values("ordinary_log", xs, rate=3.0), "family-ordinary"),
    ]
    margin = {"left": 52, "right": 18, "top": 24, "bottom": 42}
    plot_w = width - margin["left"] - margin["right"]
    plot_h = height - margin["top"] - margin["bottom"]

    def x_at(value):
        return margin["left"] + value * plot_w

    def y_at(value):
        return margin["top"] + value * plot_h

    paths = []
    labels = []
    for index, (label, values, css_class) in enumerate(series):
        terminal = values[-1] or 1.0
        normalized = [value / terminal for value in values]
        paths.append(
            f'<polyline class="{css_class}" points="{_svg_polyline([(x_at(x), y_at(y)) for x, y in zip(xs, normalized)])}" />'
        )
        labels.append(
            f'<text class="family-label" x="{margin["left"]+10}" y="{margin["top"]+18+index*20}">{_escape(label)}</text>'
        )
    return f"""
<svg class="family-chart" viewBox="0 0 {width} {height}" role="img" aria-labelledby="family-title family-desc">
  <title id="family-title">有限时刻幂律母公式的曲率变化</title>
  <desc id="family-desc">横轴是归一化交易时间，纵轴是归一化向下位移。m 从 1 降到 0 时后段越来越陡，普通对数则前快后慢。</desc>
  <line class="chart-grid" x1="{margin['left']}" y1="{margin['top']}" x2="{margin['left']}" y2="{height-margin['bottom']}" />
  <line class="chart-grid" x1="{margin['left']}" y1="{height-margin['bottom']}" x2="{width-margin['right']}" y2="{height-margin['bottom']}" />
  {''.join(paths)}
  {''.join(labels)}
  <text class="axis-label" x="{margin['left']}" y="{height-12}" text-anchor="start">开始</text>
  <text class="axis-label" x="{width-margin['right']}" y="{height-12}" text-anchor="end">临界端</text>
</svg>
"""


def _model_ranking_rows(case):
    diagnostics = case["model_diagnostics"]["decline_segment"]
    rows = []
    for item in diagnostics["ranking"]:
        payload = diagnostics["models"][item["model"]]
        rows.append(
            "<tr>"
            f"<td>{_escape(MODEL_LABELS[item['model']])}</td>"
            f"<td>{_fmt(item['delta_aicc'], 2)}</td>"
            f"<td>{_fmt(payload.get('rmse'), 2, ' bp')}</td>"
            f"<td>{_fmt(payload.get('residual_lag1'), 3)}</td>"
            f"<td>{'是' if payload.get('boundary_hit') else '否'}</td>"
            "</tr>"
        )
    return "".join(rows)


def _scope_comparison_rows(cases):
    rows = []
    for case in cases:
        full = case["model_diagnostics"]["full_day"]
        decline = case["model_diagnostics"]["decline_segment"]
        full_second = full["ranking"][1] if len(full["ranking"]) > 1 else None
        decline_second = decline["ranking"][1] if len(decline["ranking"]) > 1 else None
        full_knot = full["models"]["segmented"].get("parameters") or {}
        decline_knot = decline["models"]["segmented"].get("parameters") or {}
        direction = {
            "more_negative": "加速",
            "less_negative": "降温",
            "unchanged": "近似不变",
        }.get(decline_knot.get("slope_change_direction"), "—")
        boundary_text = " / ".join(
            (
                "全日触边" if full["models"]["segmented"].get("boundary_hit") else "全日未触边",
                "下降段触边" if decline["models"]["segmented"].get("boundary_hit") else "下降段未触边",
            )
        )
        rows.append(
            "<tr>"
            f"<td>{_escape(case['trade_date'])} {_escape(case['instrument']['name'])}</td>"
            f"<td>{_escape(MODEL_LABELS[full['best_model']])}</td>"
            f"<td>{_escape(MODEL_LABELS[full_second['model']]) if full_second else '—'}"
            f"{'（Δ' + _fmt(full_second['delta_aicc'], 2) + '）' if full_second else ''}</td>"
            f"<td>{_escape(MODEL_LABELS[decline['best_model']])}</td>"
            f"<td>{_escape(MODEL_LABELS[decline_second['model']]) if decline_second else '—'}"
            f"{'（Δ' + _fmt(decline_second['delta_aicc'], 2) + '）' if decline_second else ''}</td>"
            f"<td>{_escape(str(full_knot.get('knot_time') or '—'))} / {_escape(str(decline_knot.get('knot_time') or '—'))}</td>"
            f"<td>{_fmt(decline_knot.get('slope_before_bp_per_min'), 3)} → {_fmt(decline_knot.get('slope_after_bp_per_min'), 3)}（{_escape(direction)}）</td>"
            f"<td>{_escape(boundary_text)}</td>"
            "</tr>"
        )
    return "".join(rows)


def _window_rows(cases):
    rows = []
    for case in cases:
        name = f"{case['trade_date']} {case['instrument']['name']}"
        for review in case["window_reviews"]:
            rows.append(
                "<tr>"
                f"<td>{_escape(name)}</td>"
                f"<td>{_escape(_window_display_label(review))}</td>"
                f"<td>{_fmt(review['window_return_pct'], 2, '%')}</td>"
                f"<td>{_fmt(review['drawdown_from_known_peak_pct'], 2, '%')}</td>"
                f"<td>{_fmt(review['window_amount_cny']/100_000_000, 2)}</td>"
                f"<td>{_fmt((review['negative_minute_share_last_10'] or 0.0)*100, 0, '%') if review['negative_minute_share_last_10'] is not None else '—'}</td>"
                f"<td>{_fmt(review['slope_5m_bp_per_min'], 2)}</td>"
                f"<td>{_fmt(review['slope_15m_bp_per_min'], 2)}</td>"
                f"<td>{_fmt(review['curvature_20m_bp_per_min2'], 3)}</td>"
                f"<td>{_escape(_surface_cn(review['observed_surface']))}</td>"
                "</tr>"
            )
    return "".join(rows)


def _window_timeline_rows(cases):
    rows = []
    for case in cases:
        name = f"{case['trade_date']} {case['instrument']['name']}"
        for review in case["window_reviews"]:
            timeline = review["pressure_timeline"]
            if timeline["active_confirmation_at_cutoff"]:
                follow_through = (
                    f"{timeline['active_directional_follow_through_time']}"
                    if timeline["active_directional_follow_through_time"]
                    else "未出现"
                )
                active_text = (
                    f"{timeline['active_pressure_run_start_time']} 起；"
                    f"{timeline['active_three_minute_confirmation_time']} 重叠斜率连续；"
                    f"价格同向延续 {follow_through}；"
                    f"连续 {timeline['active_pressure_point_count']} 个分钟结束点"
                    f"（跨度 {timeline['active_pressure_elapsed_trading_minutes']} 个交易分钟）"
                )
            elif timeline["first_candidate_time"]:
                active_text = "未持续到截止"
            else:
                active_text = "未出现"
            rows.append(
                "<tr>"
                f"<td>{_escape(name)}</td>"
                f"<td>{_escape(_window_display_label(review))}</td>"
                f"<td>{_escape(timeline['first_candidate_time'] or '未出现')}</td>"
                f"<td>{_escape(timeline['first_candidate_inside_window_time'] or '未出现')}</td>"
                f"<td>{'是' if timeline['window_covers_first_candidate'] else '否'}</td>"
                f"<td>{_escape(timeline['first_three_minute_confirmation_time'] or '未形成')}</td>"
                f"<td>{_escape(timeline['first_directional_follow_through_time'] or '未出现')}</td>"
                f"<td>{_escape(_confirmation_quality_cn(timeline['first_confirmation_quality']))}</td>"
                f"<td>{_escape(active_text)}</td>"
                f"<td>{timeline['candidate_invalidation_count_inside_window']}</td>"
                "</tr>"
            )
    return "".join(rows)


def _morning_subwindow_rows(cases):
    rows = []
    for case in cases:
        review = next(
            row
            for row in case["window_reviews"]
            if row["window_id"] == "morning_diagnostic"
        )
        for child in review["subwindows"]:
            rows.append(
                "<tr>"
                f"<td>{_escape(case['trade_date'])} {_escape(case['instrument']['name'])}</td>"
                f"<td>{_escape(child['label'])}</td>"
                f"<td>{_escape(child['start_time'])}-{_escape(child['end_time'])}</td>"
                f"<td>{_fmt(child['window_return_pct'], 2, '%')}</td>"
                f"<td>{_fmt(child['window_amount_cny']/100_000_000, 2)}</td>"
                f"<td>{_fmt((child['negative_minute_share_last_10'] or 0.0)*100, 0, '%') if child['negative_minute_share_last_10'] is not None else '—'}</td>"
                f"<td>{_fmt(child['slope_5m_bp_per_min'], 2)}</td>"
                f"<td>{_fmt(child['slope_15m_bp_per_min'], 2)}</td>"
                f"<td>{_escape(_surface_cn(child['observed_surface']))}</td>"
                "</tr>"
            )
    return "".join(rows)


def _afternoon_event_rows(cases):
    rows = []
    for case in cases:
        name = f"{case['trade_date']} {case['instrument']['name']}"
        for event in case["afternoon_risk_review"]["events"]:
            rows.append(
                "<tr>"
                f"<td>{_escape(name)}</td>"
                f"<td>{_escape(event['candidate_time'])}</td>"
                f"<td>{_escape(event['slope_confirmation_time'] or '未形成')}</td>"
                f"<td>{_escape(event['directional_follow_through_time'] or '未出现')}</td>"
                f"<td>{_escape(event['invalidated_time'] or '持续到收盘')}</td>"
                f"<td>{_escape(_confirmation_quality_cn(event['confirmation_quality']))}</td>"
                "</tr>"
            )
    return "".join(rows)


def _afternoon_cutoff_rows(study):
    names = {
        case["case_id"]: case["instrument"]["name"] for case in study["cases"]
    }
    rows = []
    for item in study["afternoon_risk_synthesis"]["cutoff_sensitivity"]:
        captured_names = [
            names[case_id] for case_id in item["captured_since_observation_case_ids"]
        ]
        active_names = [names[case_id] for case_id in item["active_at_cutoff_case_ids"]]
        rows.append(
            "<tr>"
            f"<td>{_escape(item['cutoff'])}</td>"
            f"<td>{item['captured_since_observation_case_count']} / {len(study['cases'])}"
            f"（{_escape('、'.join(captured_names) or '无')}）</td>"
            f"<td>{item['active_at_cutoff_case_count']} / {len(study['cases'])}"
            f"（{_escape('、'.join(active_names) or '无')}）</td>"
            "</tr>"
        )
    return "".join(rows)


def _afternoon_decision_branch_rows(study):
    branch_copy = {
        "downward_risk": (
            "向下事件已形成斜率连续和价格同向延续，反抽不能收回 VWAP 或关键参考线，"
            "事件尚未失效；全市场或板块合力必须有对应层级同步证据。单股独立风险不升级为市场合力",
            "可卖仓位进入减风险或退出候选；当前研究版仍等 14:30-14:55 正式窗口复核后处理",
        ),
        "upward_trend": (
            "中短斜率保持向上，价格持续驻留 VWAP 上方，板块宽度和成交参与仍在扩散",
            "继续持有，不因为到了 13:45-14:10 就卖；先观察上行是否衰减",
        ),
        "conflicted_or_invalidated": (
            "只有短暂候选、价格快速收回、出现快速修复，或指数、板块和个股证据冲突",
            "不抢结论，等 14:30-14:55 再处理",
        ),
    }
    rows = []
    for branch in study["afternoon_risk_synthesis"]["decision_branches"]:
        condition, handling = branch_copy[branch["branch_id"]]
        rows.append(
            "<tr>"
            f"<td>{_escape(condition)}</td>"
            f"<td>{_escape(handling)}</td>"
            "</tr>"
        )
    return "".join(rows)


def _window_followup_rows(cases):
    rows = []
    for case in cases:
        name = f"{case['trade_date']} {case['instrument']['name']}"
        for followup in case["window_followups"]:
            rows.append(
                "<tr>"
                f"<td>{_escape(name)}</td>"
                f"<td>{_escape(followup['label'])}</td>"
                f"<td>{_fmt(followup['objective_decline_completed_pct'], 1, '%')}</td>"
                f"<td>{_escape(followup['objective_peak_time'])} → {_escape(followup['objective_trough_time'])}</td>"
                f"<td>{_escape(followup['later_trough_time'])}</td>"
                f"<td>{_fmt(followup['remaining_drawdown_to_later_trough_pct'], 2, '%')}</td>"
                f"<td>{_fmt(followup['next_5m_return_pct'], 2, '%')}</td>"
                f"<td>{_fmt(followup['next_10m_return_pct'], 2, '%')}</td>"
                f"<td>{_fmt(followup['next_20m_return_pct'], 2, '%')}</td>"
                "</tr>"
            )
    return "".join(rows)


def render_study_html(study):
    cases = study["cases"]
    decline_winner_text = "；".join(
        f"{case['instrument']['name']}={MODEL_LABELS[case['model_diagnostics']['decline_segment']['best_model']]}"
        for case in cases
    )
    full_winner_text = "；".join(
        f"{case['instrument']['name']}={MODEL_LABELS[case['model_diagnostics']['full_day']['best_model']]}"
        for case in cases
    )
    source_rows = "".join(
        "<tr>"
        f"<td>{_escape(case['trade_date'])} {_escape(case['instrument']['name'])}</td>"
        f"<td>{case['data_quality']['bar_count']}</td>"
        f"<td>{_escape(case['source']['provider'])}</td>"
        f"<td>{_escape(case['source']['source_date'])}</td>"
        f"<td>{_fmt(case['validation_summary']['daily_amount_coverage_ratio']*100, 5, '%')}</td>"
        f"<td>{'可用' if case['data_quality']['volume_usable'] else '不可用；仅用成交额'}</td>"
        "</tr>"
        for case in cases
    )
    case_figures = "".join(
        f"""
<section class="case-study" aria-labelledby="case-{_escape(case['case_id'])}">
  <div class="case-heading">
    <div>
      <p class="eyebrow">{_escape(case['trade_date'])} · 1 MIN</p>
      <h3 id="case-{_escape(case['case_id'])}">{_escape(case['instrument']['name'])}</h3>
    </div>
    <p class="case-result">全天 {_fmt(case['path_summary']['daily_return_pct'], 2, '%')} · 峰到谷 {_fmt(case['path_summary']['peak_to_trough_pct'], 2, '%')} · 全日最优 {MODEL_LABELS[case['model_diagnostics']['full_day']['best_model']]} · 下降段最优 {MODEL_LABELS[case['model_diagnostics']['decline_segment']['best_model']]}</p>
  </div>
  <figure>
    <div class="chart-wrap">{_path_svg(case)}</div>
    <figcaption>真实一分钟结束时点。浅红、浅蓝、浅绿是三段正式窗口；黄色是 09:45-09:50 前哨观察，不是新增买卖窗口。</figcaption>
  </figure>
  <figure>
    <div class="chart-wrap">{_model_svg(case, scope='full_day')}</div>
    <figcaption>全日拟合回答“整张图看起来像什么”，会把早盘抬头和午后下落一起纳入。</figcaption>
  </figure>
  <figure>
    <div class="chart-wrap">{_model_svg(case, scope='decline_segment')}</div>
    <figcaption>下降段拟合固定为客观收盘峰值到其后收盘低点，回答“下跌过程如何换速”；两种排名都只描述收盘后形状。</figcaption>
  </figure>
  <div class="table-wrap">
    <table>
      <thead><tr><th>下降段公式</th><th>ΔAICc</th><th>RMSE</th><th>残差一阶相关</th><th>参数触边</th></tr></thead>
      <tbody>{_model_ranking_rows(case)}</tbody>
    </table>
  </div>
</section>
"""
        for case in cases
    )
    sensitivity_rows = "".join(
        "<tr>"
        f"<td>{_escape(case['trade_date'])} {_escape(case['instrument']['name'])}</td>"
        f"<td>{_escape(', '.join(f'{row['start_time']}→{MODEL_LABELS[row['best_model']]}' for row in case['model_diagnostics']['start_sensitivity']['rows']))}</td>"
        f"<td>{'稳定' if case['model_diagnostics']['start_sensitivity']['stable_single_winner'] else '不稳定'}</td>"
        "</tr>"
        for case in cases
    )
    future_rows = "".join(
        "<tr>"
        f"<td>{_escape(row['case_id'])}</td>"
        f"<td>{_escape(row['signal_date'])}</td>"
        f"<td>{_escape(row['t1_date'])}</td>"
        f"<td>{_escape(row['t2_date'])}</td>"
        f"<td>截至 {IMPLEMENTATION_REVIEW_DATE} 尚未发生</td>"
        "</tr>"
        for row in study["strategy_research"]["future_observations"]
    )
    protocol = "".join(
        f"<li><strong>{_escape(row['stage'])}</strong><span>{_escape(row['rule'])}</span></li>"
        for row in study["strategy_research"]["protocol"]
    )
    account_options = "".join(
        f"<li>{_escape(value)}</li>"
        for value in study["strategy_research"]["account_overlap_options"]
    )
    index_case = next(case for case in cases if case["instrument"]["type"] == "index")
    low_time = index_case["path_summary"]["day_low"]["time"]
    rendered = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="referrer" content="no-referrer">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'">
  <title>一分钟量化压力表象、公式与交易窗口复核</title>
  <style>
    :root {{ color-scheme: light dark; --bg:#eef1ef; --paper:#fff; --ink:#1d2421; --muted:#5f6a65; --line:#cbd2ce; --soft:#f5f7f5; --red:#a9362e; --red-soft:#f6e6e3; --blue:#28657a; --blue-soft:#e4f0f4; --green:#236a56; --green-soft:#e4f0eb; --amber:#956510; --purple:#6d557d; }}
    * {{ box-sizing:border-box; }}
    html {{ background:var(--bg); scroll-behavior:smooth; }}
    body {{ margin:0; color:var(--ink); background:var(--bg); font-family:"Avenir Next","PingFang SC","Microsoft YaHei",sans-serif; font-size:16px; line-height:1.72; letter-spacing:0; }}
    .sheet {{ width:min(1240px,calc(100% - 28px)); margin:22px auto 44px; background:var(--paper); border-top:6px solid var(--ink); }}
    header {{ padding:38px 52px 34px; border-bottom:1px solid var(--line); }}
    .kicker,.eyebrow {{ margin:0 0 12px; color:var(--red); font:500 12px/1.4 "SFMono-Regular",Consolas,monospace; text-transform:uppercase; }}
    h1,h2,h3 {{ margin:0; font-family:"Songti SC","STSong",Georgia,serif; font-weight:500; letter-spacing:0; }}
    h1 {{ max-width:960px; font-size:46px; line-height:1.18; }}
    .subtitle {{ max-width:900px; margin:18px 0 0; color:var(--muted); font-family:"Songti SC","STSong",Georgia,serif; font-size:21px; }}
    .meta {{ display:flex; flex-wrap:wrap; gap:8px 20px; margin:24px 0 0; padding:0; color:var(--muted); font:400 12px/1.5 "SFMono-Regular",Consolas,monospace; list-style:none; }}
    .findings {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); border-bottom:1px solid var(--line); }}
    .finding {{ min-height:154px; padding:25px; border-right:1px solid var(--line); }}
    .finding:last-child {{ border-right:0; }}
    .finding strong {{ display:block; margin-bottom:8px; font-family:"Songti SC","STSong",Georgia,serif; font-size:18px; font-weight:500; }}
    .finding p {{ margin:0; color:var(--muted); font-size:14px; }}
    main {{ padding:46px 52px 64px; }}
    section {{ margin-bottom:56px; padding-bottom:52px; border-bottom:1px solid var(--line); }}
    section:last-child {{ margin-bottom:0; border-bottom:0; }}
    h2 {{ margin-bottom:18px; font-size:30px; line-height:1.3; }}
    h3 {{ font-size:23px; line-height:1.35; }}
    p {{ margin:0 0 16px; }}
    .lead {{ max-width:920px; font-family:"Songti SC","STSong",Georgia,serif; font-size:20px; }}
    .truth {{ padding:18px 22px; border-left:4px solid var(--red); background:var(--red-soft); }}
    .case-study {{ padding:34px 0 40px; border-bottom:1px solid var(--line); }}
    .case-heading {{ display:flex; align-items:end; justify-content:space-between; gap:24px; margin-bottom:18px; }}
    .case-result {{ margin:0; color:var(--muted); font-size:14px; text-align:right; }}
    figure {{ margin:26px 0 32px; }}
    figcaption {{ margin-top:10px; color:var(--muted); font-size:13px; }}
    .chart-wrap {{ width:100%; overflow-x:auto; -webkit-overflow-scrolling:touch; }}
    svg {{ display:block; width:100%; height:auto; overflow:visible; }}
    .price-line,.fit-actual,.fit-one,.fit-two,.fit-three,.family-linear,.family-sqrt,.family-critical,.family-ordinary {{ fill:none; vector-effect:non-scaling-stroke; stroke-linecap:round; stroke-linejoin:round; }}
    .price-line,.fit-actual {{ stroke:var(--ink); stroke-width:2; }}
    .fit-one,.family-critical {{ stroke:var(--red); stroke-width:2; }}
    .fit-two,.family-sqrt {{ stroke:var(--blue); stroke-width:1.8; stroke-dasharray:7 4; }}
    .fit-three,.family-linear {{ stroke:var(--green); stroke-width:1.8; stroke-dasharray:2 4; }}
    .family-ordinary {{ stroke:var(--purple); stroke-width:1.8; stroke-dasharray:10 4 2 4; }}
    .chart-grid {{ stroke:var(--line); stroke-width:1; vector-effect:non-scaling-stroke; }}
    .axis-label,.point-label,.family-label,.chart-legend-label {{ fill:var(--muted); font-family:"SFMono-Regular",Consolas,monospace; font-size:12px; }}
    .chart-legend-label {{ fill:var(--ink); }}
    .point-label {{ fill:var(--ink); }}
    .peak-mark {{ fill:var(--blue); }} .low-mark {{ fill:var(--red); }}
    .window-a {{ fill:var(--red-soft); opacity:.7; }} .window-scout {{ fill:var(--amber); opacity:.18; }} .window-b {{ fill:var(--blue-soft); opacity:.7; }} .window-c {{ fill:var(--green-soft); opacity:.7; }}
    .table-wrap {{ width:100%; overflow-x:auto; }}
    table {{ width:100%; border-collapse:collapse; font-size:14px; }}
    th,td {{ padding:11px 12px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }}
    th {{ color:var(--muted); font-weight:500; white-space:nowrap; }}
    code {{ font-family:"SFMono-Regular",Consolas,monospace; font-size:.92em; overflow-wrap:anywhere; word-break:break-word; }}
    .formula {{ margin:22px 0; padding:20px 22px; background:var(--soft); font-family:"SFMono-Regular",Consolas,monospace; overflow-wrap:anywhere; }}
    .formula-grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:1px; background:var(--line); margin:26px 0; }}
    .formula-item {{ padding:20px; background:var(--paper); }}
    .formula-item strong {{ display:block; margin-bottom:8px; font-weight:500; }}
    .formula-item p {{ margin:0; color:var(--muted); font-size:14px; }}
    .steps {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); margin:28px 0; padding:0; list-style:none; }}
    .steps li {{ padding:22px; border-top:3px solid var(--ink); border-right:1px solid var(--line); }}
    .steps li:last-child {{ border-right:0; }}
    .steps strong {{ display:block; margin-bottom:10px; font-size:18px; }}
    .steps span {{ color:var(--muted); font-size:14px; }}
    .plain-list {{ margin:12px 0 0; padding-left:22px; }}
    .plain-list li {{ margin:8px 0; }}
    footer {{ padding:24px 52px 34px; border-top:1px solid var(--line); color:var(--muted); font-size:12px; }}
    @media (prefers-color-scheme: dark) {{ :root {{ --bg:#171b19; --paper:#202522; --ink:#edf2ef; --muted:#abb6b0; --line:#45504a; --soft:#292f2c; --red:#ee8177; --red-soft:#3b2927; --blue:#76bad0; --blue-soft:#25363c; --green:#72bea5; --green-soft:#25372f; --amber:#d7a94e; --purple:#bfa0d0; }} }}
    @media (max-width:800px) {{ .sheet {{ width:100%; margin:0; border-top-width:4px; }} header,main,footer {{ padding-left:20px; padding-right:20px; }} h1 {{ font-size:34px; }} .subtitle {{ font-size:18px; }} .findings,.formula-grid,.steps {{ grid-template-columns:1fr; }} .finding {{ min-height:0; border-right:0; border-bottom:1px solid var(--line); }} .finding:last-child {{ border-bottom:0; }} .case-heading {{ align-items:start; flex-direction:column; }} .case-result {{ text-align:left; }} .chart-wrap svg {{ width:780px; max-width:none; }} table {{ min-width:760px; }} .case-study table {{ min-width:620px; }} }}
    @media print {{ :root {{ --bg:#fff; --paper:#fff; --ink:#111; --muted:#555; --line:#bbb; }} .sheet {{ width:100%; margin:0; border:0; }} section,.case-study,figure {{ break-inside:avoid; }} }}
  </style>
</head>
<body>
<article class="sheet">
  <header>
    <p class="kicker">MARKET LANGUAGE RESEARCH · REVISION 4</p>
    <h1>一分钟市场语言：公式、事件时钟与日报只读落地</h1>
    <p class="subtitle">把“鸭蛋弧”拆成可复算的一分钟事实，再把形状、压力阶段、机制假说和交易动作分层。市场确实在说话，但曲线本身不提供账户身份证明。</p>
    <ul class="meta"><li>案例冻结：{RESEARCH_AS_OF_DATE}</li><li>落地复核：{IMPLEMENTATION_REVIEW_DATE}</li><li>主源：通达信历史一分钟</li><li>范围：三例锚定 + 七类保护路径，不外推普遍命中率</li></ul>
  </header>
  <div class="findings">
    <div class="finding"><strong>公式不再强行单选</strong><p>全日：{_escape(full_winner_text)}；下降段：{_escape(decline_winner_text)}。上证全日包络最像平移椭圆弧，三例客观下降段都由单变化点分段领先；日报盘中只用斜率、连续性和事件时钟。</p></div>
    <div class="finding"><strong>研究证据已经只读接入</strong><p><code>market_language_translation.v1</code> 只在原有明日动作之后展示；完整版和摘要版的正式对象、仓位、B1/B2 与退出动作逐字段保持不变。</p></div>
    <div class="finding"><strong>保护样本限制了过度解释</strong><p>普通缓跌、一次性重估、单股卖压、快速修复、权重与宽度背离、健康扩散和五分钟降级都已固定；形状只能描述压力，不能确认量化身份或 40% 成交占比。</p></div>
  </div>
  <main>
    <section id="verdict">
      <h2>先给结论</h2>
      <p class="lead">你的“像椭圆鸭蛋、像根号或 log”不是错觉，而是对负曲率和跌速变化的生活化识别。数学真正提供的不是一个万能答案，而是一套分工：椭圆描述包络，分段描述换挡，幂律与 Gompertz 描述候选经验过程，事件时钟负责盘中识别。</p>
      <p class="truth"><strong>最终答案：</strong>三例从收盘峰值到其后低点，都是灵活的单变化点分段模型最好，但单断点平均换挡方向并不相同：兆易创新和上证指数后段更负，长电科技在 10:04 后的全段平均明显降温；这不否认长电尾盘再次加速，一个断点也不能描述全部多轮换挡。共同冠军只说明一条直线不够，不说明同一种量化机制。上证全日由平移椭圆弧第一，说明“鸭蛋”适合描述全天包络。正式日报不拿某条最佳拟合公式直接发出动作，只翻译合力范围、方向、阶段、候选、确认、失效与反证。不能确认卖方账户身份，也不能据此推出量化成交占比。</p>
    </section>

    <section id="data">
      <h2>数据先过关：三例都是一分钟，不再用五分钟代替</h2>
      <p>每例固定为 240 个交易分钟结束时点，横轴压缩午休。通达信的 14:59 无成交占位值已归零；上证指数的通达信 volume 不是实际股数，因此彻底停用，只保留价格与成交额。</p>
      <p><strong>Tushare 官方能力与项目实测：</strong>官方股票历史分钟接口是 <code>stk_mins</code>，指数历史分钟接口是 <code>idx_mins</code>；两者都支持 <code>1min/5min/15min/30min/60min</code>，单次最多 8000 行。当前项目通道实测中，两只股票的兼容端点 <code>stock_mins</code> 返回空表，正式 <code>stk_mins</code> 显示当前账号未开通历史分钟数据；上证的 <code>idx_mins</code> 返回空表。现有封装既会接受股票空表并提前结束，也没有为指数调用 <code>idx_mins</code>，最终三例均为 0 个可用 bar。结论是 Tushare 本身能提供一分钟历史数据，但当前项目配置与封装尚不能把它作为有效来源，也不能把空表解释为目标日期无行情。</p>
      <div class="table-wrap"><table><thead><tr><th>案例</th><th>分钟数</th><th>主源</th><th>源日期</th><th>成交额覆盖</th><th>成交量</th></tr></thead><tbody>{source_rows}</tbody></table></div>
    </section>

    <section id="cases">
      <h2>三例路径与公式比较</h2>
      <p>上图是完整一分钟路径；下图只取“客观收盘峰值 → 其后收盘低点”。这样既展示你看到的全天鸭蛋外观，也避免手挑一小段来证明预设公式。</p>
      {case_figures}
    </section>

    <section id="formula">
      <h2>哪个公式最贴切：下降过程是分段，鸭蛋外观是椭圆类包络</h2>
      <p class="lead">严格按数据回答，三例下降段最接近单变化点分段模型；上证全日才最接近可平移的椭圆弧。它们不是二选一：分段回答“哪里换挡”，椭圆回答“全天包络像什么”。幂律、指数、Gompertz 和两种对数继续留在 replay 做竞争与反证，不进入普通日报的盘中动作计算。</p>
      <div class="table-wrap"><table><thead><tr><th>案例</th><th>全日第一</th><th>全日第二</th><th>下降段第一</th><th>下降段第二</th><th>分段点（全日 / 下降段）</th><th>下降段前后速度（bp/分钟）</th><th>分段搜索边界</th></tr></thead><tbody>{_scope_comparison_rows(cases)}</tbody></table></div>
      <p>表中的前后速度是“只允许一个断点”后的区间平均，不是全天每一分钟的固定机制。长电科技下降段在 10:04 后平均降温，但 14:30-14:55 又出现尾部加速；这正是多轮压力不能被一个断点概括的例子。</p>
      <div class="formula">D(t) = A · [1 - (1 - t/T)<sup>m</sup>] / m</div>
      <p><code>D(t)</code> 是累计向下位移，<code>T</code> 是只用于形状的临界尺度，<code>m</code> 控制后段是否变陡。<code>m=1</code> 退化为线性；<code>0&lt;m&lt;1</code> 表示越到后段跌速越快；<code>m≈0.5</code> 是根号临界，接近椭圆端点的外观；<code>m→0</code> 逼近临界对数。这个 <code>T</code> 不是预测真实崩溃时刻。</p>
      <figure><div class="chart-wrap">{_family_svg()}</div><figcaption>图形向下绘制的是归一化位移。普通 <code>log(1+kt)</code> 前快后慢，不能再与临界对数混称。</figcaption></figure>
      <h3>公式职责与变量，换成生活语言</h3>
      <p>下表统一令 <code>t</code> 为压缩午休后的交易时间进度（0 到 1），<code>y(t)</code> 为相对区间起点的对数价格基点；<code>a</code> 是起点位置，<code>b</code> 是方向和幅度。</p>
      <div class="table-wrap"><table><thead><tr><th>公式类</th><th>表达式</th><th>变量含义</th><th>看到什么</th></tr></thead><tbody>
        <tr><td>单变化点分段</td><td><code>y(t)=a+bt+c(t-τ)<sub>+</sub></code></td><td><code>τ</code> 是换挡位置；前段速度是 <code>b</code>，后段速度是 <code>b+c</code></td><td>卖压或承接在某处发生速度变化</td></tr>
        <tr><td>平移椭圆弧</td><td><code>y(t)=a+b√[1-((t-h)/r)²]</code></td><td><code>h</code> 是鸭蛋最高点的横向位置，<code>r</code> 是横向半径，<code>b</code> 是纵向高度</td><td>先抬头、再沿椭圆右侧越来越陡；上证全日最接近这一类</td></tr>
        <tr><td>有限时刻幂律</td><td><code>y(t)=a+b[1-(1-t/T)<sup>m</sup>]/m</code></td><td><code>m</code> 控制弯曲；<code>T</code> 是形状尺度，不是真实崩溃时刻</td><td>比较后段越来越陡的经验过程，不指认生成机制</td></tr>
        <tr><td>指数</td><td><code>y(t)=a+b(e<sup>kt</sup>-1)</code></td><td><code>k</code> 越大，速度按比例放大越快</td><td>比较没有明显换挡的持续加速包络</td></tr>
        <tr><td>Gompertz</td><td><code>y(t)=a+b·exp[-exp(-k(t-h))]</code></td><td><code>h</code> 靠近最大速度位置，<code>k</code> 控制曲线先增后减的快慢</td><td>比较单轮压力先增强、后边际衰减的经验外形</td></tr>
        <tr><td>临界对数</td><td><code>y(t)=a+b[-ln(1-t/T)]</code></td><td><code>b&lt;0</code> 时后段向下越来越陡</td><td>极强的临界端加速，仅作压力上界对照</td></tr>
        <tr><td>普通对数</td><td><code>y(t)=a+b·ln(1+kt)</code></td><td><code>b&lt;0</code> 时前段快、后段慢</td><td>一开始猛烈、随后逐渐耗尽，方向与临界对数相反</td></tr>
      </tbody></table></div>
      <div class="formula-grid">
        <div class="formula-item"><strong>分段模型</strong><p>最适合描述速度换挡和多轮压力；最佳断点是事后几何断点，不等于真实触发时刻。</p></div>
        <div class="formula-item"><strong>椭圆类</strong><p>四分之一代理受限；平移椭圆弧允许峰值左右移动，更接近上证全天“先抬头再沿鸭蛋右侧下落”的外观，但仍不是任意旋转椭圆。</p></div>
        <div class="formula-item"><strong>Gompertz</strong><p>适合单轮“招募增强 → 最大跌速 → 边际耗尽”；两轮压力仍需分段或事件结构。</p></div>
        <div class="formula-item"><strong>两种对数</strong><p>普通对数前快后慢；临界对数后段加速。上一版只放普通对数，数学口径不完整。</p></div>
      </div>
      <h3>下降段小范围起点敏感性</h3>
      <p>AICc 使用一分钟价格水平残差，残差高度相关，ΔAICc 会显得比真实证据更强。下降段起点前后移动时，三例的分段冠军稳定；但上证从“下降段”换成“全日”后冠军改为椭圆类，说明研究范围仍会改变答案。</p>
      <div class="table-wrap"><table><thead><tr><th>案例</th><th>下降段不同起点 → 最优公式</th><th>局部结论</th></tr></thead><tbody>{sensitivity_rows}</tbody></table></div>
    </section>

    <section id="windows">
      <h2>三段正式窗口反推：角色暂时合理，时点有效性仍待样本外验收</h2>
      <p><strong>09:30-09:35</strong> 只有五个完整分钟，适合看开盘冲击和相对强弱，不够识别椭圆或多轮级联。<strong>09:45-09:50</strong> 只作前哨观察，为 <strong>09:50-10:10</strong> 正式窗口准备证据，不新增买卖动作。<strong>14:30-14:55</strong> 适合判断尾部是否继续创新低、是否修复以及隔夜风险，但不能包装成“提前退出”。候选要求十五分钟斜率低于 -0.05 bp/分钟；三根相邻结束时点的十五分钟斜率同向只记为“重叠斜率连续”，还要检查候选后价格是否继续同向移动。这是透明研究口径，不是买入资格。</p>
      <div class="formula">κ<sub>20</sub>(t) = [s<sub>5</sub>(t) - s<sub>5</sub>(t-15)] / 15</div>
      <p>表中的二十分钟曲率代理不是另一套二次回归：<code>s5</code> 是六个收盘点拟合出的五交易分钟对数价格斜率，<code>κ20</code> 是最近十五个交易分钟里这条短斜率的平均变化，单位为 bp/交易分钟²。判断使用未舍入值，表格只在显示时保留小数。</p>
      <div class="table-wrap"><table><thead><tr><th>案例</th><th>窗口</th><th>窗口收益</th><th>距当时峰值</th><th>窗口成交额（亿元）</th><th>近10分钟下跌占比</th><th>5分斜率（bp/分钟）</th><th>15分斜率（bp/分钟）</th><th>20分曲率代理（bp/分钟²）</th><th>截止时表象</th></tr></thead><tbody>{_window_rows(cases)}</tbody></table></div>
      <h3>首次候选、重叠斜率连续与价格同向延续</h3>
      <div class="table-wrap"><table><thead><tr><th>案例</th><th>观察范围</th><th>截至截止全日首次候选</th><th>范围内首次候选</th><th>范围覆盖全日首次</th><th>首次重叠斜率连续</th><th>候选后价格同向延续</th><th>首次证据质量</th><th>截至截止当前轮</th><th>范围内候选失效次数</th></tr></thead><tbody>{_window_timeline_rows(cases)}</tbody></table></div>
      <h3>09:45-09:50 前哨 / 09:50-10:10 正式窗口拆解</h3>
      <p>前哨段只负责发现异动，不直接给新增动作；正式窗口再看中短斜率是否同向、短线回抽能否改变十五分钟压力。</p>
      <div class="table-wrap"><table><thead><tr><th>案例</th><th>子阶段</th><th>区间</th><th>区间收益</th><th>区间成交额（亿元）</th><th>近10分钟下跌占比</th><th>5分斜率（bp/分钟）</th><th>15分斜率（bp/分钟）</th><th>截止时表象</th></tr></thead><tbody>{_morning_subwindow_rows(cases)}</tbody></table></div>
      <h3>13:45-14:10 午后风险复核：只是待验证候选</h3>
      <p class="lead"><strong>13:45-14:10 只是待验证候选</strong>，不是第四段正式买卖时间。这三个案例只能说明：三例的向下分钟事件在 13:45 已经可见，不能反推出 14:10 是更好的结束点。它的研究价值是让事件时间钟在 14:30 前持续回答方向、连续性、对应市场范围和失效；正式三段窗口目前保持不变。</p>
      <p>你的生活经验可以改写成一个可检验假说：如果一只股票到 14:30 已经处于强势大涨，通常在 13:45-14:10 会更早留下向上斜率、VWAP 上方驻留、板块同步和成交参与的足迹。因此不能只凭“时间到了”卖出；有持续向上证据时，过早卖反而会放弃趋势。但这不是“14:30 后几乎不会再大涨”的统计结论。尾盘突袭涨停、消息驱动的快速重估和先弱后强的快速修复都是必须保留的反例。<strong>三例只复算向下分钟事件</strong>，没有历史强势尾盘样本验证这条向上假说。</p>
      <h3>三例午后事件原始时钟</h3>
      <div class="table-wrap"><table><thead><tr><th>案例</th><th>候选</th><th>斜率连续</th><th>价格同向延续</th><th>失效</th><th>证据质量</th></tr></thead><tbody>{_afternoon_event_rows(cases)}</tbody></table></div>
      <h3>截止分钟截面会变化，但三例不能选出 14:10</h3>
      <div class="table-wrap"><table><thead><tr><th>截止</th><th>13:45 至截止曾捕获</th><th>截止分钟截面仍有效</th></tr></thead><tbody>{_afternoon_cutoff_rows(study)}</tbody></table></div>
      <p><strong>正确读法：</strong>13:45 当下三例都已经具备斜率连续和价格同向延续；从 13:45 到四个截止时刻都曾捕获三例，所以 14:00 和 14:05 并没有漏掉长电。右栏只显示截止分钟截面：长电第一轮在 13:59 失效，14:06 再候选后到 14:10 又有效；到 14:20，长电与兆易此前那一轮均已失效。这张表说明事件会失效和重来，不能证明必须观察到 14:10。</p>
      <p>所有精确分钟都依赖当前尚未校准的 <code>0.05 bp/分钟</code> 研究阈值。阈值变化会移动候选与失效边界；后续必须加入普通日和多阈值敏感性，三例不能选出 14:10，也不能确定 13:45 是全市场最优起点。</p>
      <h3>怎样判断卖出：不是一根曲线，而是三种处理分支</h3>
      <div class="table-wrap"><table><thead><tr><th>当时证据</th><th>当前处理</th></tr></thead><tbody>{_afternoon_decision_branch_rows(study)}</tbody></table></div>
      <p>真正进入减风险候选至少要同时满足：方向向下；斜率连续并有价格同向延续；反抽未能修复；事件没有失效；证据与合力范围相配。全市场范围要有指数、宽度和多板块同步，板块范围要有板块内部扩散，单股独立风险只进入原有个股退出条件，不能升级成市场合力。只有向下斜率、只有跌破 VWAP、只有一根急跌，均不足以单独决定卖出；还要服从可卖仓位、前一晚计划、认错线和亏损边界。</p>
      <p><strong>防守式卖出和高位止盈要分开：</strong>前者看向下事件是否成立；后者看原本向上的合力是否衰减。价格仍高，但板块宽度先收缩、成交推动效率下降、后排掉队、核心跌回 VWAP 后反弹失败，才进入高位止盈候选。若向上斜率、VWAP 驻留、板块扩散和成交参与仍互相支持，持续上涨本身不是卖出条件。</p>
      <h3>事后验收，不回填当时判断</h3>
      <p>下表故意与上面的当时证据分开。主要下降完成比例、后续最低和未来 5/10/20 分钟收益都只有收盘后才知道，只用于检验窗口是否真的领先。</p>
      <div class="table-wrap"><table><thead><tr><th>案例</th><th>窗口</th><th>主要下降已完成</th><th>客观峰值 → 谷值</th><th>截止后最低时刻</th><th>截止后剩余跌幅</th><th>后5分钟</th><th>后10分钟</th><th>后20分钟</th></tr></thead><tbody>{_window_followup_rows(cases)}</tbody></table></div>
      <p class="truth">5·21 上证到 10:10 没有越过噪声带的下压候选；第一轮可记录候选是 10:17，10:19 只说明重叠斜率连续，10:24 才出现候选后价格同向延续，13:50 开始的这一轮才持续到尾盘。因此，本研究压力口径截至 10:10 未识别后来形成的午后鸭蛋弧，早盘窗口不能保证提前识别所有午后风险。兆易创新 09:47 的首次候选虽在 09:49 出现重叠斜率连续，却没有价格同向延续并于 09:54 失效；10:00 的第二轮才补齐延续证据。三段正式窗口的角色暂不冲突，但仍不能证明已经具备可交易领先量。</p>
    </section>

    <section id="implementation">
      <h2>日报落地：一个只读研究产物，两种时间钟</h2>
      <p class="lead">正式日报新增的不是“量化买卖按钮”，而是一份 <code>market_language_translation.v1</code> 研究证据。它在入口从目标日事实构建一次，完整版和摘要版各拿独立副本，只在原有明日执行结论之后展示。</p>
      <div class="formula">目标日事实 → 来源投影 → 合力范围 / 方向 / 阶段 / 多轮事件 → 研究证据区<br>正式候选 / 最终对象 / 仓位 / B1-B2 / 退出动作 ─────────────────→ 保持原链路</div>
      <div class="table-wrap"><table><thead><tr><th>层次</th><th>进入内容</th><th>时间边界</th><th>对正式动作的影响</th></tr></thead><tbody>
        <tr><td>当时事实</td><td>目标日指数、宽度、板块同步、参与度与可追溯分钟路径</td><td>只能读到 <code>causal_cutoff</code></td><td>仅生成研究解释</td></tr>
        <tr><td>市场语言产物</td><td>范围、方向、阶段、候选、确认、失效、反证、下一窗口任务</td><td>候选、确认与失效各自保留因果截止点</td><td>不进入正式决定输入</td></tr>
        <tr><td>正式日报</td><td><code>selection_workflow</code>、<code>final_target_resolution</code>、仓位与执行计划</td><td>继续按原有 T0 决定</td><td>研究产物只能在后方展示</td></tr>
        <tr><td>replay 验收</td><td>未来 5/10/20 分钟、MFE/MAE、低高区、T+1/T+2 与行情完成比例</td><td>仅在未来事实已发生后填写</td><td>只批改，不回写当时判断</td></tr>
      </tbody></table></div>
      <h3>固定时间钟没有扩张</h3>
      <p><code>09:30-09:35</code>、<code>09:50-10:10</code>、<code>14:30-14:55</code> 仍是唯一三段买卖处理时间。<code>09:45-09:50</code> 只作前哨观察；全天事件时钟可以记录午间或午后新候选，但窗口外只形成观察记录，等下一正式窗口或下一份日报处理。</p>
      <h3>正式决定逐字段不变</h3>
      <div class="table-wrap"><table><thead><tr><th>比较项</th><th>完整版</th><th>摘要版</th><th>结果</th></tr></thead><tbody>
        <tr><td><code>selection_workflow</code></td><td>接入前后逐字段比较</td><td>接入前后逐字段比较</td><td>相同</td></tr>
        <tr><td><code>final_target_resolution</code></td><td>接入前后逐字段比较</td><td>接入前后逐字段比较</td><td>相同</td></tr>
        <tr><td>明日执行对象 / 仓位 / 执行性质</td><td>显式投影比较</td><td>显式投影比较</td><td>相同</td></tr>
        <tr><td>B1 / B2 / 退出动作</td><td>显式投影比较</td><td>显式投影比较</td><td>相同</td></tr>
        <tr><td>原研究产物哈希</td><td>渲染前后核对</td><td>渲染前后核对</td><td>未改写</td></tr>
      </tbody></table></div>
      <p>fresh 产物的 <code>posthoc_validation</code> 固定为 <code>null</code>。PostgreSQL 只按目标日和专属 <code>source_policy=postgresql.market_language_translation.v1</code> 精确读写；本地 fresh 写入 <code>data/market-language/fresh/</code>，replay 只写入 <code>snapshots/replay/market-language/</code>，两者不互相覆盖。</p>
    </section>

    <section id="protection-samples">
      <h2>保护样本：先证明它会克制，再讨论是否有用</h2>
      <p>以下是受控路径回归，不是历史命中率。它们的任务是阻止三个极端案例反推普通行情，确保“同样像弧线”时仍允许得出不同范围、阶段或失败记录。</p>
      <div class="table-wrap"><table><thead><tr><th>保护路径</th><th>研究产物应怎样翻译</th><th>防止的误判</th></tr></thead><tbody>
        <tr><td>普通匀速缓跌</td><td>可以记录向下压力，但不能因浮点误差写成向下反馈加速</td><td>把所有缓跌都叫踩踏</td></tr>
        <tr><td>单根消息重估后横盘</td><td>重叠斜率可以短暂连续；没有候选后价格延续时降为“仅重叠斜率连续”，随后完整记录失效</td><td>把一次性价值重估解释为持续级联</td></tr>
        <tr><td>单股持续卖压、市场宽度向上</td><td>范围保持 <code>single_stock</code>，并记录聚合方向冲突</td><td>把单一大资金执行提高为全市场合力</td></tr>
        <tr><td>快速下跌后持续回升</td><td>先保留下压事件，再把当前阶段写成修复</td><td>只看日内曾经下跌而忽略恢复力</td></tr>
        <tr><td>权重指数下跌、上涨家数占优</td><td>范围保持 <code>index_weighted</code>，不能写 <code>whole_market</code></td><td>把上证的平滑鸭蛋等同于全部个股</td></tr>
        <tr><td>指数、宽度、板块健康同向上行</td><td>可提高为全市场向上扩散，不写拥挤、衰减或修复</td><td>系统只能识别下跌，无法描述健康合力</td></tr>
        <tr><td>只有五分钟路径</td><td>保留五分钟粒度并停止输出一分钟候选时刻</td><td>把桶结束时刻冒充真实一分钟事件</td></tr>
      </tbody></table></div>
      <p class="truth"><strong>保护样本带来的关键修正：</strong>三根重叠十五分钟斜率同向，只能确认下压表象仍在滚动窗口中可见，不等于确认持续卖压，更不等于确认量化账户。还要继续看价格是否同向延续、事件是否失效、范围是否扩散、宽度是否同向以及恢复力是否回来。</p>
    </section>

    <section id="strategy">
      <h2>T+0 识别 → T+1 条件参与 → T+2 处理：仍是待验收研究协议</h2>
      <p>市场语言产物不会自行把任何股票送入这条链。压力日的顺滑下跌最多提示次日研究对象，“压力大”本身更像回避信号；只有原日报已经在 T0 决定条件参与，且次日持续修复、相对强度和承接同时成立，才执行 B1，B2 仍只在进一步确认后补。</p>
      <ol class="steps">{protocol}</ol>
      <h3>7 月 10 日两例只能前瞻登记</h3>
      <div class="table-wrap"><table><thead><tr><th>案例</th><th>T+0</th><th>T+1</th><th>T+2</th><th>当前状态</th></tr></thead><tbody>{future_rows}</tbody></table></div>
      <p>截至本版复核日，2026-07-13 和 2026-07-14 尚未发生。报告不能提前填写收益，也不能用后来发生的数据倒推今天“已经成功”。</p>
      <h3>单账户资金会重叠</h3>
      <ul class="plain-list">{account_options}</ul>
      <p>满仓逐日执行在资金上不可行。未来回测必须使用单账户逐日净值，计入一手金额、最低佣金、卖出税费、滑点、涨跌停和空闲现金；不能把每笔事件收益直接相加。</p>
    </section>

    <section id="limits">
      <h2>这一步真正帮助日报什么，以及下一轮怎样验收</h2>
      <p>它已经把“乌云密布”的生活经验拆成可追溯字段：压力发生在指数、单股、单板块还是全市场；方向向上还是向下；处于启动、扩散、衰减、向下反馈加速或修复；候选何时出现、确认、失效和再来；指数、宽度和板块是否互相支持。</p>
      <div class="formula-grid">
        <div class="formula-item"><strong>现在能做</strong><p>在原有动作之后解释市场正在表达的范围、方向和阶段；让下一正式窗口知道应该核对延续、扩散、失效还是修复。</p></div>
        <div class="formula-item"><strong>现在不能做</strong><p>仅凭曲线确认量化账户、龙虎榜席位触发链、真实撤单率、A 股量化成交占比或次日必然反弹。</p></div>
        <div class="formula-item"><strong>下一轮验收</strong><p>连续积累样本外 replay，比较候选后的 5/10/20 分钟、MFE/MAE、失效率和不同市场范围，不只挑成功样本。</p></div>
        <div class="formula-item"><strong>升级前提</strong><p>只有研究证据在足够样本中稳定提高窗口复核质量，且没有改写正式决定，才单独讨论是否影响候选或仓位。</p></div>
      </div>
      <p class="truth">三例和保护路径足以支持“先记录并翻译一分钟表象”，仍不能证明“看到鸭蛋弧就买次日反弹”，也不能证明 A 股量化成交占比约 40%。真正的进步不是把直觉包装成确定性，而是让每次候选、失效和反证都能留下来接受未来事实批改。</p>
    </section>
  </main>
  <footer>案例数据冻结于 {RESEARCH_AS_OF_DATE} · 日报只读落地复核于 {IMPLEMENTATION_REVIEW_DATE} · 通达信一分钟主源 · 腾讯 / 新浪交叉核对 · AICc 与未来表现仅作 replay 验收 · 研究证据不改写正式日报交易决定</footer>
</article>
</body>
</html>
"""
    return "\n".join(line.rstrip() for line in rendered.splitlines()) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Build the one-minute quant pressure case study"
    )
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURE_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--stdout-json", action="store_true")
    args = parser.parse_args(argv)
    result = build_study(args.fixtures)
    rendered = render_study_html(result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    if args.stdout_json:
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2, allow_nan=False)
        sys.stdout.write("\n")
    else:
        print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
