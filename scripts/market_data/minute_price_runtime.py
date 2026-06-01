from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

from market_data.kline_dates import normalize_kline_date_str
from market_data.tushare_minute_service import fetch_tushare_minute_bars
from storage.database_service import DatabaseService

DEFAULT_MINUTE_CACHE_DIR = Path(__file__).resolve().parents[1] / "cache" / "minute_price"

__all__ = [
    "DEFAULT_MINUTE_CACHE_DIR",
    "fetch_index_minute_bars",
    "fetch_tushare_minute_bars",
    "normalize_index_minute_symbol",
    "normalize_minute_bars",
]


def normalize_index_minute_symbol(index_code: str) -> str:
    text = str(index_code or "").strip().lower()
    if text.startswith("sh."):
        return "sh" + text.split(".", 1)[1]
    if text.startswith("sz."):
        return "sz" + text.split(".", 1)[1]
    if text.startswith(("sh", "sz")):
        return text
    if text.startswith("399"):
        return "sz" + text
    if text.startswith("0"):
        return "sh" + text
    return text


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def normalize_minute_bars(frame) -> list[dict]:
    if frame is None or len(frame) == 0:
        return []
    prepared = frame.copy()
    time_col = "day" if "day" in prepared.columns else "时间" if "时间" in prepared.columns else None
    if not time_col:
        raise ValueError("分钟K线缺少时间列")
    prepared["_dt"] = pd.to_datetime(prepared[time_col], errors="coerce")
    prepared = prepared.dropna(subset=["_dt"]).sort_values("_dt").reset_index(drop=True)
    bars = []
    for _, row in prepared.iterrows():
        bars.append(
            {
                "datetime": row["_dt"].strftime("%Y-%m-%d %H:%M:%S"),
                "date": row["_dt"].strftime("%Y-%m-%d"),
                "time": row["_dt"].strftime("%H:%M:%S"),
                "open": _safe_float(row.get("open") if "open" in prepared.columns else row.get("开盘")),
                "high": _safe_float(row.get("high") if "high" in prepared.columns else row.get("最高")),
                "low": _safe_float(row.get("low") if "low" in prepared.columns else row.get("最低")),
                "close": _safe_float(row.get("close") if "close" in prepared.columns else row.get("收盘")),
                "volume": _safe_float(row.get("volume") if "volume" in prepared.columns else row.get("成交量")),
                "amount": _safe_float(row.get("amount") if "amount" in prepared.columns else row.get("成交额")),
            }
        )
    return bars


def _postgres_database_url():
    return (
        os.environ.get("A_DAILY_REPORT_DATABASE_URL")
        or os.environ.get("DATABASE_URL")
        or ""
    ).strip()


def _postgres_only_runtime():
    return os.environ.get("A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME", "").strip() == "1"


def _runtime_service():
    database_url = _postgres_database_url()
    if not database_url.startswith(("postgres://", "postgresql://")):
        return None
    service = DatabaseService.from_environment()
    return service if service.is_postgres_backed() else None


def _structured_payload(index_code, period, bars, source, *, status="success"):
    return {
        "success": bool(bars),
        "status": status if bars else "minute_fetch_failed",
        "source": source,
        "symbol": normalize_index_minute_symbol(index_code),
        "period": str(period),
        "bars": bars or [],
    }


def _try_upsert_index_minute_bars(service, symbol, target_date, period, bars, source_policy):
    if service is None or not target_date or not bars:
        return {}
    try:
        saved_count = service.upsert_index_minute_bars(
            symbol,
            target_date,
            str(period),
            bars,
            source_policy=source_policy,
        )
        return {
            "postgres_write_status": "success",
            "postgres_write_rows": int(saved_count or 0),
        }
    except Exception as error:
        return {
            "postgres_write_status": "failed",
            "postgres_write_error": str(error),
        }


def _filter_bars_to_target_date(bars, target_date):
    normalized_target = normalize_kline_date_str(target_date)
    if not normalized_target:
        return list(bars or [])
    filtered = []
    for bar in bars or []:
        if not isinstance(bar, dict):
            continue
        bar_date = normalize_kline_date_str(bar.get("date") or str(bar.get("datetime") or "")[:10])
        if bar_date == normalized_target:
            filtered.append(bar)
    return filtered


def fetch_index_minute_bars(index_code="sh.000001", period="60", *, target_date=None, cache_dir=DEFAULT_MINUTE_CACHE_DIR):
    del cache_dir
    symbol = normalize_index_minute_symbol(index_code)
    service = _runtime_service()
    if service is not None and target_date:
        cached_rows = service.query_index_minute_bars(symbol, target_date, period=str(period))
        if cached_rows:
            return _structured_payload(index_code, period, cached_rows, "postgresql.index_minute_bars")
        if _postgres_only_runtime():
            return {
                "success": False,
                "status": "postgres_minute_missing",
                "source": "postgresql.index_minute_bars",
                "symbol": symbol,
                "period": str(period),
                "trade_date": str(target_date),
                "bars": [],
            }
    elif _postgres_only_runtime():
        return {
            "success": False,
            "status": "postgres_minute_missing",
            "source": "postgresql.index_minute_bars",
            "symbol": symbol,
            "period": str(period),
            "trade_date": str(target_date or ""),
            "bars": [],
        }

    try:
        bars = _filter_bars_to_target_date(
            fetch_tushare_minute_bars(index_code, period=str(period), is_index=True, target_date=target_date),
            target_date,
        )
        if bars:
            payload = _structured_payload(index_code, period, bars, "tushare.stock_mins")
            payload.update(
                _try_upsert_index_minute_bars(
                    service,
                    symbol,
                    target_date,
                    period,
                    bars,
                    "tushare.stock_mins",
                )
            )
            return payload
    except Exception:
        pass

    try:
        import akshare as ak

        frame = ak.stock_zh_a_minute(symbol=symbol, period=str(period), adjust="")
        bars = _filter_bars_to_target_date(normalize_minute_bars(frame), target_date)
        payload = _structured_payload(index_code, period, bars, "akshare.stock_zh_a_minute", status="success" if bars else "empty")
        payload.update(
            _try_upsert_index_minute_bars(
                service,
                symbol,
                target_date,
                period,
                bars,
                "akshare.stock_zh_a_minute",
            )
        )
        return payload
    except Exception as error:
        return {
            "success": False,
            "status": "minute_fetch_failed",
            "source": "akshare.stock_zh_a_minute",
            "symbol": symbol,
            "period": str(period),
            "bars": [],
            "error": str(error),
        }
