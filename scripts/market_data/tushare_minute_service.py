from __future__ import annotations

import datetime

from market_data.kline_dates import normalize_kline_date_str
from market_data.tushare_client import create_tushare_pro_api
from market_data.tushare_service import normalize_ts_code

__all__ = [
    "fetch_tushare_minute_bars",
]


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _frame_to_records(frame):
    if frame is None:
        return []
    if isinstance(frame, list):
        return list(frame)
    if hasattr(frame, "to_dict"):
        return frame.to_dict("records")
    return []


def _resolve_target_date(target_date):
    normalized = normalize_kline_date_str(target_date)
    if normalized:
        return normalized
    return datetime.datetime.now().strftime("%Y-%m-%d")


def _minute_window(target_date):
    date_text = _resolve_target_date(target_date)
    return f"{date_text} 00:00:00", f"{date_text} 23:59:59", date_text


def _normalize_minute_row(row, *, data_source="tushare.stock_mins"):
    row = row or {}
    dt_text = str(row.get("trade_time") or row.get("datetime") or row.get("day") or row.get("时间") or "").strip()
    if not dt_text:
        return None
    try:
        dt = datetime.datetime.fromisoformat(dt_text.replace("/", "-"))
    except ValueError:
        return None
    return {
        "datetime": dt.strftime("%Y-%m-%d %H:%M:%S"),
        "date": dt.strftime("%Y-%m-%d"),
        "time": dt.strftime("%H:%M:%S"),
        "open": _safe_float(row.get("open") if row.get("open") is not None else row.get("开盘")),
        "high": _safe_float(row.get("high") if row.get("high") is not None else row.get("最高")),
        "low": _safe_float(row.get("low") if row.get("low") is not None else row.get("最低")),
        "close": _safe_float(row.get("close") if row.get("close") is not None else row.get("收盘")),
        "volume": _safe_float(row.get("vol") if row.get("vol") is not None else row.get("volume")),
        "amount": _safe_float(row.get("amount") if row.get("amount") is not None else row.get("成交额")),
        "data_source": data_source,
    }


def fetch_tushare_minute_bars(
    security_code,
    *,
    period="60",
    target_date=None,
    is_index=False,
    pro=None,
    ts_module=None,
    timeout_seconds=3,
):
    ts_code = normalize_ts_code(security_code, is_index=is_index)
    if not ts_code:
        return []
    start_time, end_time, date_text = _minute_window(target_date)
    pro = pro or create_tushare_pro_api(ts_module=ts_module, timeout_seconds=timeout_seconds)
    errors = []
    frame = None
    data_source = ""
    for api_name in ("stock_mins", "stk_mins"):
        api = getattr(pro, api_name, None)
        if not callable(api):
            continue
        try:
            frame = api(
                ts_code=ts_code,
                start_date=start_time,
                end_date=end_time,
                freq=f"{period}min",
            )
            data_source = f"tushare.{api_name}"
            break
        except Exception as exc:
            errors.append(f"{api_name}: {exc}")
    if frame is None and errors:
        raise Exception("; ".join(errors))
    bars = []
    for row in _frame_to_records(frame):
        bar = _normalize_minute_row(row, data_source=data_source or "tushare.stock_mins")
        if bar and bar.get("date") == date_text:
            bars.append(bar)
    return sorted(bars, key=lambda item: item.get("datetime", ""))
