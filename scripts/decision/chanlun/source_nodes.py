from __future__ import annotations

from market_data.kline_dates import normalize_kline_date_str, parse_kline_date

from .contracts import (
    DAILY_BASE_BARS,
    DAILY_FOCUS_BARS,
    DATA_INSUFFICIENT,
    DATA_SUFFICIENT,
    LOCAL_CONFIRMATION_ONLY,
    LOCAL_ONLY_PERIODS,
    PRACTICAL_DAILY_MODE,
)


def _normalize_row(row):
    item = dict(row or {})
    item["date"] = normalize_kline_date_str(item.get("date") or item.get("datetime") or "")
    return item


def _sort_key(item):
    parsed = parse_kline_date(item.get("date"))
    return (parsed is None, parsed or item.get("date") or "")


def normalize_kline_rows(rows):
    normalized = [_normalize_row(row) for row in list(rows or []) if isinstance(row, dict)]
    return sorted(normalized, key=_sort_key)


def build_daily_capability(rows, requested_bars=DAILY_BASE_BARS):
    returned_bars = len(rows or [])
    status = DATA_SUFFICIENT if returned_bars >= requested_bars else DATA_INSUFFICIENT
    return {
        "provider": "daily_rows",
        "period": "daily",
        "requested_bars": int(requested_bars),
        "returned_bars": int(returned_bars),
        "returned_trading_days": int(returned_bars),
        "first_datetime": rows[0].get("date") if rows else None,
        "last_datetime": rows[-1].get("date") if rows else None,
        "capability_status": status,
        "supports_250_day_base": status == DATA_SUFFICIENT,
    }


def build_minute_capability(
    *,
    provider,
    period,
    requested_bars,
    returned_bars,
    returned_trading_days,
    first_datetime=None,
    last_datetime=None,
):
    period_text = str(period)
    supports_base = int(returned_trading_days or 0) >= DAILY_BASE_BARS
    if period_text in LOCAL_ONLY_PERIODS:
        status = LOCAL_CONFIRMATION_ONLY
        supports_base = False
    else:
        status = DATA_SUFFICIENT if supports_base else DATA_INSUFFICIENT
    return {
        "provider": provider,
        "period": period_text,
        "requested_bars": int(requested_bars or 0),
        "returned_bars": int(returned_bars or 0),
        "returned_trading_days": int(returned_trading_days or 0),
        "first_datetime": first_datetime,
        "last_datetime": last_datetime,
        "capability_status": status,
        "supports_250_day_base": bool(supports_base),
    }


def select_practical_daily_window(rows, *, base_bars=DAILY_BASE_BARS, focus_bars=DAILY_FOCUS_BARS):
    normalized = normalize_kline_rows(rows)
    base_rows = normalized[-int(base_bars) :]
    focus_rows = base_rows[-int(focus_bars) :]
    return {
        "mode": PRACTICAL_DAILY_MODE,
        "base_rows": base_rows,
        "focus_rows": focus_rows,
        "minute_data_required": False,
        "data_capability": build_daily_capability(base_rows, requested_bars=base_bars),
    }
