from __future__ import annotations

import pandas as pd

from market_data.kline_dates import normalize_kline_date_str, parse_kline_date

DAILY_STRUCTURE_LOOKBACK_DAYS = 250
DAILY_REPORT_FOCUS_DAYS = 120
DAILY_CANDIDATE_MIN_KLINES = 20

__all__ = [
    "DAILY_CANDIDATE_MIN_KLINES",
    "DAILY_REPORT_FOCUS_DAYS",
    "DAILY_STRUCTURE_LOOKBACK_DAYS",
    "build_daily_structure_candidates",
]


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _prepare_daily_rows(rows, target_date=None):
    frame = pd.DataFrame(list(rows or []))
    if frame.empty:
        return frame
    frame["date"] = frame["date"].map(normalize_kline_date_str)
    frame["_dt"] = frame["date"].map(parse_kline_date)
    frame = frame.dropna(subset=["_dt"]).sort_values("_dt").reset_index(drop=True)
    if target_date:
        target_dt = parse_kline_date(target_date)
        if target_dt is not None:
            frame = frame[frame["_dt"] < target_dt].reset_index(drop=True)
    return frame


def _candidate_from_slice(frame, *, min_daily_klines=DAILY_CANDIDATE_MIN_KLINES):
    count = len(frame)
    high = max(_safe_float(value) for value in frame["high"])
    low = min(_safe_float(value) for value in frame["low"])
    if count >= min_daily_klines:
        status = "daily_cycle_confirmed_by_duration"
    elif count > 0:
        status = "daily_candidate_forming"
    else:
        status = "insufficient_duration"
    return {
        "start_date": frame.iloc[0]["date"],
        "end_date": frame.iloc[-1]["date"],
        "kline_count": int(count),
        "required_kline_count": int(min_daily_klines),
        "high": float(high),
        "low": float(low),
        "zg_candidate": float(high),
        "zd_candidate": float(low),
        "candidate_status": status,
        "mainline": "-",
        "mainline_state": "待确认",
    }


def build_daily_structure_candidates(rows, *, target_date=None, min_daily_klines=DAILY_CANDIDATE_MIN_KLINES):
    frame = _prepare_daily_rows(rows, target_date=target_date)
    if frame.empty:
        return {
            "success": False,
            "status": "empty_daily_bars",
            "daily_structure_candidates": [],
            "current_candidate": None,
            "daily_lookback_count": 0,
            "report_focus_count": 0,
        }
    base = frame.tail(DAILY_STRUCTURE_LOOKBACK_DAYS).reset_index(drop=True)
    if len(base) < min_daily_klines:
        current_slice = base
    else:
        current_slice = base.tail(min_daily_klines)
    current = _candidate_from_slice(current_slice, min_daily_klines=min_daily_klines)
    return {
        "success": True,
        "status": "success",
        "daily_structure_candidates": [current],
        "current_candidate": current,
        "daily_lookback_count": int(len(base)),
        "report_focus_count": min(int(len(base)), DAILY_REPORT_FOCUS_DAYS),
    }
