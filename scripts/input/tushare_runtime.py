from __future__ import annotations

import datetime

from market_data.kline_dates import normalize_kline_date_str
from market_data.tushare_service import fetch_daily_price_bars
from market_data.tushare_turnover_service import fetch_stock_daily_turnover_records

__all__ = [
    "get_total_turnover_from_tushare_first",
    "get_major_indices_from_tushare_first",
    "get_wind_a_from_tushare_first",
]


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _resolve_query_date(target_date=None):
    if target_date:
        if isinstance(target_date, str):
            return datetime.datetime.strptime(target_date, "%Y-%m-%d")
        return target_date
    return datetime.datetime.now()


def _fallback_call(fn, target_date):
    if not callable(fn):
        return None
    return fn(target_date=target_date)


def get_total_turnover_from_tushare_first(
    target_date=None,
    *,
    fetch_stock_daily_turnover_records_fn=None,
    legacy_get_total_turnover_fn=None,
):
    fetcher = fetch_stock_daily_turnover_records_fn or fetch_stock_daily_turnover_records
    try:
        rows = fetcher(target_date)
        total = sum(_safe_float((row or {}).get("amount_yi")) for row in (rows or []))
        if total > 0:
            return round(total, 2)
    except Exception:
        pass

    fallback = _fallback_call(legacy_get_total_turnover_fn, target_date)
    return _safe_float(fallback)


def _change_pct(latest_bar, prev_bar):
    close_price = _safe_float((latest_bar or {}).get("close"))
    prev_close = _safe_float((prev_bar or {}).get("close"))
    open_price = _safe_float((latest_bar or {}).get("open"))
    if prev_close > 0:
        return (close_price - prev_close) / prev_close * 100
    if open_price > 0:
        return (close_price - open_price) / open_price * 100
    return 0.0


def _latest_index_payload(name, code, bars):
    normalized_bars = [
        {**(bar or {}), "date": normalize_kline_date_str((bar or {}).get("date"))}
        for bar in (bars or [])
    ]
    normalized_bars = [bar for bar in normalized_bars if bar.get("date")]
    normalized_bars.sort(key=lambda item: item.get("date", ""))
    if not normalized_bars:
        return None

    latest_bar = normalized_bars[-1]
    prev_bar = normalized_bars[-2] if len(normalized_bars) >= 2 else {}
    close_price = _safe_float(latest_bar.get("close"))
    if close_price <= 0:
        return None

    change_pct = _change_pct(latest_bar, prev_bar)
    return {
        "name": name,
        "code": code,
        "price": close_price,
        "open": _safe_float(latest_bar.get("open")),
        "close": close_price,
        "high": _safe_float(latest_bar.get("high")),
        "low": _safe_float(latest_bar.get("low")),
        "change_pct": change_pct,
        "turnover": _safe_float(latest_bar.get("amount_yi")),
        "涨跌幅": change_pct,
        "data_source": "tushare.index_daily",
        "trade_date": latest_bar.get("date"),
    }


def _index_query_window(target_date):
    query_date = _resolve_query_date(target_date)
    end_date = query_date.strftime("%Y-%m-%d")
    start_date = (query_date - datetime.timedelta(days=15)).strftime("%Y-%m-%d")
    return start_date, end_date


def get_major_indices_from_tushare_first(
    target_date=None,
    *,
    fetch_daily_price_bars_fn=None,
    legacy_get_major_indices_fn=None,
):
    fetcher = fetch_daily_price_bars_fn or fetch_daily_price_bars
    start_date, end_date = _index_query_window(target_date)
    index_map = {
        "上证指数": "000001",
        "深证成指": "399001",
        "创业板指": "399006",
    }

    try:
        indices = {}
        for name, code in index_map.items():
            payload = _latest_index_payload(
                name,
                code,
                fetcher(code, start_date, end_date, is_index=True),
            )
            if payload:
                indices[name] = payload
        if len(indices) >= 3:
            return indices
    except Exception:
        pass

    fallback = _fallback_call(legacy_get_major_indices_fn, target_date)
    return fallback or {}


def get_wind_a_from_tushare_first(
    target_date=None,
    *,
    fetch_daily_price_bars_fn=None,
    legacy_get_wind_a_fn=None,
):
    fetcher = fetch_daily_price_bars_fn or fetch_daily_price_bars
    start_date, end_date = _index_query_window(target_date)

    try:
        payload = _latest_index_payload(
            "中证全指",
            "000985",
            fetcher("000985", start_date, end_date, is_index=True),
        )
        if payload and _safe_float(payload.get("price")) > 0:
            return payload
    except Exception:
        pass

    fallback = _fallback_call(legacy_get_wind_a_fn, target_date)
    return fallback or {"price": 0, "change_pct": 0}
