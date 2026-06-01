from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
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


def _cache_path(cache_dir, symbol, period):
    if cache_dir in (None, ""):
        return None
    return Path(cache_dir) / f"{symbol}_{period}m.json"


def _read_cache(path):
    if not path or not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _write_cache(path, payload):
    if not path:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _postgres_database_url():
    return (
        os.environ.get("A_DAILY_REPORT_DATABASE_URL")
        or os.environ.get("DATABASE_URL")
        or ""
    ).strip()


def _postgres_only_runtime():
    return os.environ.get("A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME", "").strip() == "1"


def _runtime_cache_service():
    database_url = _postgres_database_url()
    if not database_url.startswith(("postgres://", "postgresql://")):
        return None
    service = DatabaseService.from_environment()
    return service if service.is_postgres_backed() else None


def _runtime_cache_key(symbol, period):
    return f"{symbol}:{period}"


def _read_runtime_cache(service, symbol, period):
    if service is None:
        return None
    entry = service.get_runtime_cache_entry("minute_price", _runtime_cache_key(symbol, period), "")
    if not isinstance(entry, dict):
        return None
    payload = entry.get("payload")
    if not isinstance(payload, dict) or not payload.get("bars"):
        return None
    cached = dict(payload)
    cached["source"] = "cache"
    return cached


def _write_runtime_cache(service, symbol, period, payload):
    if service is None:
        return False
    return service.set_runtime_cache_entry(
        "minute_price",
        _runtime_cache_key(symbol, period),
        "",
        dict(payload or {}),
        source=str((payload or {}).get("source") or ""),
        ttl_seconds=24 * 3600,
    )


def fetch_index_minute_bars(index_code="sh.000001", period="60", *, cache_dir=DEFAULT_MINUTE_CACHE_DIR):
    symbol = normalize_index_minute_symbol(index_code)
    runtime_cache_service = _runtime_cache_service()
    postgres_cache_only = runtime_cache_service is not None or _postgres_only_runtime()
    path = None if postgres_cache_only else _cache_path(cache_dir, symbol, period)
    runtime_cached = _read_runtime_cache(runtime_cache_service, symbol, str(period))
    if runtime_cached and runtime_cached.get("bars"):
        return runtime_cached
    cached = _read_cache(path)
    if cached and cached.get("bars"):
        cached["source"] = "cache"
        return cached
    try:
        bars = fetch_tushare_minute_bars(index_code, period=str(period), is_index=True, target_date=None)
        if bars:
            payload = {
                "success": True,
                "status": "success",
                "source": "tushare.stock_mins",
                "symbol": symbol,
                "period": str(period),
                "bars": bars,
            }
            try:
                if runtime_cache_service is not None:
                    _write_runtime_cache(runtime_cache_service, symbol, str(period), payload)
                else:
                    _write_cache(path, payload)
            except Exception:
                pass
            return payload
    except Exception:
        pass
    try:
        import akshare as ak

        frame = ak.stock_zh_a_minute(symbol=symbol, period=str(period), adjust="")
        bars = normalize_minute_bars(frame)
        payload = {
            "success": bool(bars),
            "status": "success" if bars else "empty",
            "source": "akshare.stock_zh_a_minute",
            "symbol": symbol,
            "period": str(period),
            "bars": bars,
        }
        if bars:
            try:
                if runtime_cache_service is not None:
                    _write_runtime_cache(runtime_cache_service, symbol, str(period), payload)
                else:
                    _write_cache(path, payload)
            except Exception:
                pass
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
