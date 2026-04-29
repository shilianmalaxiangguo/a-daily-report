from __future__ import annotations

from .confirmation_nodes import confirm_with_child_trend_types
from .contracts import (
    DEFAULT_CONFIRMATION_PERIOD,
    HYBRID_CONFIRMATION_MODE,
    PRACTICAL_DAILY_MODE,
)
from .source_nodes import select_practical_daily_window
from .structure_nodes import identify_platforms_from_trend_types


__all__ = [
    "analyze_hybrid_structure",
    "analyze_practical_daily_structure",
]


def _trend_type_from_row(row, index):
    item = dict(row or {})
    high = float(item["high"])
    low = float(item["low"])
    return {
        **item,
        "trend_type_id": item.get("trend_type_id") or f"daily_trend_{index + 1}",
        "status": "completed_trend_type",
        "high": high,
        "low": low,
    }


def _daily_trend_types(rows):
    trend_types = []
    for index, row in enumerate(list(rows or [])):
        if not isinstance(row, dict) or row.get("high") is None or row.get("low") is None:
            continue
        try:
            trend_types.append(_trend_type_from_row(row, index))
        except (TypeError, ValueError):
            continue
    return trend_types


def _not_requested_confirmation():
    return {
        "confirmed": False,
        "confirmation_status": "not_requested",
        "period": None,
        "ZG": None,
        "ZD": None,
        "explanation": "practical daily no minute confirmation",
    }


def analyze_practical_daily_structure(*, daily_rows, fetch_minute_bars=None, target_date=None):
    window = select_practical_daily_window(daily_rows)
    trend_types = _daily_trend_types(window["base_rows"])
    segments, platforms = identify_platforms_from_trend_types(trend_types, level_id="daily")
    current_candidate = platforms[-1] if platforms else None

    return {
        "success": True,
        "mode": PRACTICAL_DAILY_MODE,
        "status": "success" if current_candidate else "not_yet_platform",
        "data_capability": window["data_capability"],
        "daily_trend_types": trend_types,
        "daily_structure_segments": segments,
        "daily_structure_candidates": platforms,
        "current_candidate": current_candidate,
        "child_trend_types": [],
        "minute_confirmation": _not_requested_confirmation(),
    }


def analyze_hybrid_structure(
    *,
    daily_rows,
    fetch_minute_bars,
    target_date=None,
    index_code="sh.000001",
    minute_period=DEFAULT_CONFIRMATION_PERIOD,
):
    result = dict(
        analyze_practical_daily_structure(
            daily_rows=daily_rows,
            fetch_minute_bars=None,
            target_date=target_date,
        )
    )
    period = str(minute_period)
    payload = fetch_minute_bars(index_code=index_code, period=period)
    minute_source_status = "invalid_minute_payload"
    bars = []
    if isinstance(payload, dict):
        minute_source_status = payload.get("status")
        bars = payload.get("bars") or []

    child_trend_types = _daily_trend_types(bars)
    result.update(
        {
            "mode": HYBRID_CONFIRMATION_MODE,
            "child_trend_types": child_trend_types,
            "minute_confirmation": confirm_with_child_trend_types(child_trend_types, period=period),
            "minute_source_status": minute_source_status,
        }
    )
    return result
