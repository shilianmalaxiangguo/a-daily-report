from __future__ import annotations

import datetime

from market_data.kline_dates import normalize_kline_date_str
from market_data.tushare_service import fetch_daily_price_bars
from market_data.tushare_turnover_service import (
    fetch_stock_daily_turnover_records,
    fetch_stock_industry_map,
    fetch_stock_name_map,
)

__all__ = [
    "ProviderValue",
    "get_total_turnover_from_tushare_first",
    "get_major_indices_from_tushare_first",
    "get_wind_a_from_tushare_first",
    "get_turnover_rank_from_tushare_first",
]


class ProviderValue(float):
    def __new__(
        cls,
        value,
        *,
        data_source="",
        source_endpoint="",
        source_row_count=0,
        source_retry_count=0,
    ):
        obj = float.__new__(cls, value)
        obj.data_source = data_source
        obj.source_endpoint = source_endpoint
        obj.source_row_count = source_row_count
        obj.source_retry_count = source_retry_count
        return obj


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


def _fetch_turnover_rows_with_retry(fetcher, target_date, retry_count=1):
    attempts = max(int(retry_count or 0), 0) + 1
    last_rows = []
    for attempt in range(attempts):
        rows = fetcher(target_date) or []
        last_rows = rows
        if rows:
            return rows, attempt
    return last_rows, attempts - 1


def get_total_turnover_from_tushare_first(
    target_date=None,
    *,
    fetch_stock_daily_turnover_records_fn=None,
    legacy_get_total_turnover_fn=None,
):
    fetcher = fetch_stock_daily_turnover_records_fn or fetch_stock_daily_turnover_records
    retry_count = 0
    try:
        rows, retry_count = _fetch_turnover_rows_with_retry(fetcher, target_date)
        total = sum(_safe_float((row or {}).get("amount_yi")) for row in (rows or []))
        if total > 0:
            return ProviderValue(
                round(total, 2),
                data_source="tushare.daily",
                source_endpoint="daily",
                source_row_count=len(rows or []),
                source_retry_count=retry_count,
            )
    except Exception:
        pass

    fallback = _fallback_call(legacy_get_total_turnover_fn, target_date)
    return ProviderValue(
        _safe_float(fallback),
        data_source="legacy.total_turnover",
        source_endpoint="fallback",
        source_row_count=0,
        source_retry_count=retry_count,
    )


def _lookup_by_code(mapping, row, default=""):
    stock_code = str((row or {}).get("stock_code") or "").strip()
    ts_code = str((row or {}).get("ts_code") or "").strip().upper()
    value = (mapping or {}).get(stock_code)
    if value in (None, ""):
        value = (mapping or {}).get(ts_code)
    return str(value or default).strip()


def get_turnover_rank_from_tushare_first(
    target_date=None,
    *,
    limit=50,
    fetch_stock_daily_turnover_records_fn=None,
    fetch_stock_name_map_fn=None,
    fetch_stock_industry_map_fn=None,
    legacy_get_turnover_rank_fn=None,
):
    fetcher = fetch_stock_daily_turnover_records_fn or fetch_stock_daily_turnover_records
    try:
        rows = [row for row in (fetcher(target_date) or []) if _safe_float((row or {}).get("amount_yi")) > 0]
        rows.sort(
            key=lambda row: (
                -_safe_float((row or {}).get("amount_yi")),
                str((row or {}).get("stock_code") or (row or {}).get("ts_code") or ""),
            )
        )
        if rows:
            name_map_loader = fetch_stock_name_map_fn or fetch_stock_name_map
            industry_map_loader = fetch_stock_industry_map_fn or fetch_stock_industry_map
            try:
                name_map = name_map_loader() if callable(name_map_loader) else {}
            except Exception:
                name_map = {}
            try:
                industry_map = industry_map_loader() if callable(industry_map_loader) else {}
            except Exception:
                industry_map = {}

            ranked = []
            for rank, row in enumerate(rows[: max(int(limit or 50), 1)], start=1):
                stock_code = str(row.get("stock_code") or "").strip()
                ts_code = str(row.get("ts_code") or "").strip().upper()
                code = stock_code or (ts_code.split(".", 1)[0] if "." in ts_code else ts_code)
                name = _lookup_by_code(name_map, row, row.get("name") or code)
                sector = _lookup_by_code(industry_map, row, "未知")
                ranked.append(
                    {
                        "rank": rank,
                        "code": code,
                        "name": name,
                        "turnover": _safe_float(row.get("amount_yi")),
                        "change_pct": _safe_float(row.get("pct_chg")),
                        "sector": sector or "未知",
                        "data_source": "tushare.daily",
                        "trade_date": row.get("trade_date"),
                    }
                )
            return ranked
    except Exception:
        pass

    if callable(legacy_get_turnover_rank_fn):
        return legacy_get_turnover_rank_fn(target_date=target_date, limit=limit) or []
    return []


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
