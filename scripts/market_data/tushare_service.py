from __future__ import annotations

from market_data.kline_dates import normalize_kline_date_str
from market_data.tushare_client import create_tushare_pro_api

__all__ = [
    "fetch_daily_price_bars",
    "fetch_daily_price_bars_by_trade_date",
    "normalize_ts_code",
]


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _load_tushare_module(ts_module=None):
    if ts_module is not None:
        return ts_module

    import tushare as ts  # type: ignore

    return ts


def _compact_date(date_value):
    normalized = normalize_kline_date_str(date_value)
    return normalized.replace("-", "") if normalized else ""


def normalize_ts_code(security_code, *, is_index=False):
    text = str(security_code or "").strip().upper()
    if not text:
        return ""
    if "." in text:
        left, right = text.split(".", 1)
        if left in ("SH", "SZ", "BJ"):
            return f"{right}.{left}"
        if right in ("SH", "SZ", "BJ"):
            return text
    lowered = text.lower()
    if lowered.startswith(("sh.", "sz.", "bj.")):
        market, code = lowered.split(".", 1)
        return f"{code}.{market.upper()}"
    if lowered.startswith(("sh", "sz", "bj")) and len(text) > 2:
        return f"{text[2:]}.{text[:2].upper()}"

    code = "".join(ch for ch in text if ch.isdigit())
    if not code:
        return ""
    code = code.zfill(6)
    if is_index:
        if code == "000985":
            market = "CSI"
        else:
            market = "SZ" if code.startswith("399") else "SH"
    elif code.startswith(("8", "4", "9")):
        market = "BJ"
    elif code.startswith(("6", "5")):
        market = "SH"
    else:
        market = "SZ"
    return f"{code}.{market}"


def _frame_to_records(frame):
    if frame is None:
        return []
    if isinstance(frame, list):
        return list(frame)
    if hasattr(frame, "to_dict"):
        return frame.to_dict("records")
    return []


def _stock_code_from_ts_code(value):
    text = str(value or "").strip().upper()
    if "." in text:
        text = text.split(".", 1)[0]
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits.zfill(6) if digits else ""


def _normalize_bar_row(row, *, data_source="tushare.pro_bar"):
    date_text = normalize_kline_date_str(row.get("trade_date") or row.get("date"))
    if not date_text:
        return None
    return {
        "date": date_text,
        "ts_code": str(row.get("ts_code") or "").strip().upper(),
        "stock_code": _stock_code_from_ts_code(row.get("ts_code")),
        "open": _safe_float(row.get("open")),
        "high": _safe_float(row.get("high")),
        "low": _safe_float(row.get("low")),
        "close": _safe_float(row.get("close")),
        "volume": _safe_float(row.get("vol") if row.get("vol") is not None else row.get("volume")),
        "data_source": data_source,
    }


def _normalize_index_bar_row(row):
    bar = _normalize_bar_row(row)
    if not bar:
        return None
    bar["data_source"] = "tushare.index_daily"
    bar["pre_close"] = _safe_float(row.get("pre_close"))
    bar["change"] = _safe_float(row.get("change"))
    bar["pct_chg"] = _safe_float(row.get("pct_chg"))
    bar["amount"] = _safe_float(row.get("amount"))
    return bar


def fetch_daily_price_bars(security_code, start_date, end_date, *, is_index=False, ts_module=None, pro=None):
    start = _compact_date(start_date)
    end = _compact_date(end_date)
    ts_code = normalize_ts_code(security_code, is_index=is_index)
    if not ts_code or not start or not end:
        return []

    ts = _load_tushare_module(ts_module)
    pro = pro or create_tushare_pro_api(ts_module=ts)
    if is_index:
        frame = pro.index_daily(ts_code=ts_code, start_date=start, end_date=end)
        normalize_row = _normalize_index_bar_row
    else:
        frame = ts.pro_bar(
            api=pro,
            ts_code=ts_code,
            start_date=start,
            end_date=end,
            adj="qfq",
        )
        normalize_row = _normalize_bar_row
    bars = []
    for row in _frame_to_records(frame):
        bar = normalize_row(row or {})
        if bar and normalize_kline_date_str(start_date) <= bar["date"] <= normalize_kline_date_str(end_date):
            bars.append(bar)
    return sorted(bars, key=lambda item: item.get("date", ""))


def fetch_daily_price_bars_by_trade_date(trade_date, *, ts_module=None, pro=None):
    compact = _compact_date(trade_date)
    if not compact:
        return []
    pro = pro or create_tushare_pro_api(ts_module=ts_module)
    frame = pro.daily(
        trade_date=compact,
        fields="ts_code,trade_date,open,high,low,close,pre_close,change,pct_chg,vol,amount",
    )
    bars = []
    for row in _frame_to_records(frame):
        bar = _normalize_bar_row(row or {}, data_source="tushare.daily")
        if bar and bar.get("stock_code"):
            bars.append(bar)
    return sorted(bars, key=lambda item: item.get("stock_code", ""))
