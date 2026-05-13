from __future__ import annotations

from market_data.kline_dates import normalize_kline_date_str
from market_data.tushare_client import create_tushare_pro_api

__all__ = [
    "fetch_stock_industry_map",
    "fetch_stock_daily_turnover_records",
    "fetch_stock_turnover_history",
]


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _compact_date(date_value):
    normalized = normalize_kline_date_str(date_value)
    return normalized.replace("-", "") if normalized else ""


def _frame_to_records(frame):
    if frame is None:
        return []
    if isinstance(frame, list):
        return list(frame)
    if hasattr(frame, "to_dict"):
        return frame.to_dict("records")
    return []


def _split_ts_code(ts_code):
    text = str(ts_code or "").strip().upper()
    if "." not in text:
        return "", ""
    code, market = text.split(".", 1)
    code = "".join(ch for ch in code if ch.isdigit()).zfill(6)
    market = market.strip()
    if not code or market not in {"SH", "SZ", "BJ"}:
        return "", ""
    return code, market


def _normalize_ts_code(security_code):
    text = str(security_code or "").strip().upper()
    if not text:
        return ""
    if "." in text:
        left, right = text.split(".", 1)
        if right in {"SH", "SZ", "BJ"}:
            return text
        if left in {"SH", "SZ", "BJ"}:
            return f"{right}.{left}"
    lowered = text.lower()
    if lowered.startswith(("sh", "sz", "bj")) and len(text) > 2:
        return f"{text[2:]}.{text[:2].upper()}"
    code = "".join(ch for ch in text if ch.isdigit()).zfill(6)
    if not code:
        return ""
    if code.startswith(("8", "4", "9")):
        market = "BJ"
    elif code.startswith(("6", "5")):
        market = "SH"
    else:
        market = "SZ"
    return f"{code}.{market}"


def _normalize_daily_row(row):
    row = row or {}
    trade_date = normalize_kline_date_str(row.get("trade_date"))
    stock_code, market = _split_ts_code(row.get("ts_code"))
    amount_raw = _safe_float(row.get("amount"))
    if not trade_date or not stock_code or amount_raw <= 0:
        return None
    return {
        "trade_date": trade_date,
        "ts_code": str(row.get("ts_code") or "").strip().upper(),
        "stock_code": stock_code,
        "market": market,
        "name": str(row.get("name") or "").strip(),
        "open": _safe_float(row.get("open")),
        "high": _safe_float(row.get("high")),
        "low": _safe_float(row.get("low")),
        "close": _safe_float(row.get("close")),
        "pre_close": _safe_float(row.get("pre_close")),
        "change": _safe_float(row.get("change")),
        "pct_chg": _safe_float(row.get("pct_chg")),
        "vol": _safe_float(row.get("vol")),
        "amount_raw_qianyuan": amount_raw,
        "amount_yi": round(amount_raw / 100000.0, 6),
        "data_source": "tushare.daily",
    }


def fetch_stock_daily_turnover_records(trade_date, *, pro=None, ts_module=None):
    compact = _compact_date(trade_date)
    if not compact:
        return []
    pro = pro or create_tushare_pro_api(ts_module=ts_module)
    frame = pro.daily(trade_date=compact)
    records = []
    for row in _frame_to_records(frame):
        normalized = _normalize_daily_row(row)
        if normalized:
            records.append(normalized)
    return records


def fetch_stock_industry_map(*, pro=None, ts_module=None):
    pro = pro or create_tushare_pro_api(ts_module=ts_module)
    frame = pro.stock_basic(
        exchange="",
        list_status="L",
        fields="ts_code,name,industry",
    )
    mapping = {}
    for row in _frame_to_records(frame):
        stock_code, _market = _split_ts_code(row.get("ts_code"))
        industry = str(row.get("industry") or "").strip()
        if not stock_code or not industry:
            continue
        ts_code = str(row.get("ts_code") or "").strip().upper()
        mapping[stock_code] = industry
        if ts_code:
            mapping[ts_code] = industry
    return mapping


def fetch_stock_turnover_history(security_code, start_date, end_date, *, pro=None, ts_module=None):
    start = _compact_date(start_date)
    end = _compact_date(end_date)
    ts_code = _normalize_ts_code(security_code)
    if not ts_code or not start or not end:
        return []
    pro = pro or create_tushare_pro_api(ts_module=ts_module)
    frame = pro.daily(ts_code=ts_code, start_date=start, end_date=end)
    rows = []
    for row in _frame_to_records(frame):
        normalized = _normalize_daily_row(row)
        if normalized:
            rows.append(normalized)
    rows.sort(key=lambda item: item.get("trade_date", ""))
    return [item["amount_yi"] for item in rows if _safe_float(item.get("amount_yi")) > 0]
