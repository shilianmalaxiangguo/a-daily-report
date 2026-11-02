from __future__ import annotations

from typing import Any


def _resolve_pool_count(data: Any, *, status_label: str, pool_key: str, stats_key: str) -> int | None:
    data = data if isinstance(data, dict) else {}
    data_status = data.get("data_status") if isinstance(data.get("data_status"), dict) else {}
    if status_label in data_status and data_status.get(status_label) is not True:
        return None

    pool = data.get(pool_key)
    if isinstance(pool, list):
        return len(pool)

    market_stats = data.get("market_stats") if isinstance(data.get("market_stats"), dict) else {}
    value = market_stats.get(stats_key, data.get(stats_key))
    if value in (None, ""):
        return None
    try:
        return max(int(float(value)), 0)
    except (TypeError, ValueError):
        return None


def resolve_limit_up_count(data: Any) -> int | None:
    return _resolve_pool_count(
        data,
        status_label="涨停池",
        pool_key="zt_pool",
        stats_key="zt_count",
    )


def resolve_limit_down_count(data: Any) -> int | None:
    return _resolve_pool_count(
        data,
        status_label="跌停池",
        pool_key="dt_pool",
        stats_key="dt_count",
    )


def format_limit_count(value: Any) -> str:
    if value is None:
        return "待确认"
    try:
        return str(max(int(float(value)), 0))
    except (TypeError, ValueError):
        return "待确认"


__all__ = ["format_limit_count", "resolve_limit_down_count", "resolve_limit_up_count"]
