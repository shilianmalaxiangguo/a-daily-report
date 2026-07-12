def _safe_float(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value):
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _pool_count(data, pool_key, stats_key):
    pool = (data or {}).get(pool_key)
    if isinstance(pool, list):
        return len(pool)
    market_stats = (data or {}).get("market_stats") or {}
    return _safe_int(market_stats.get(stats_key, (data or {}).get(stats_key, 0)))


def _profit_effect_state(data):
    data = data or {}
    market_stats = data.get("market_stats") or {}
    up_count = _safe_int(market_stats.get("up_count", data.get("up_count", 0)))
    down_count = _safe_int(market_stats.get("down_count", data.get("down_count", 0)))
    dt_count = _pool_count(data, "dt_pool", "dt_count")
    if down_count > up_count and down_count > 0:
        return "weak_breadth"
    if dt_count >= 3:
        return "limit_down_pressure"
    return "balanced"


def describe_market_turnover_condition(data):
    data = data or {}
    turnover = _safe_float(data.get("total_turnover", data.get("turnover", 0)))
    if turnover > 18000:
        volume_label = "量能充沛"
    elif turnover >= 15000:
        volume_label = "量能不差"
    elif turnover > 12000:
        volume_label = "量能适中"
    else:
        return "量能偏弱，先看不做"

    profit_effect_state = _profit_effect_state(data)
    if profit_effect_state == "weak_breadth":
        return f"{volume_label}，但赚钱效应不足"
    if profit_effect_state == "limit_down_pressure":
        return f"{volume_label}，但跌停端压力仍高"
    return f"{volume_label}，赚钱效应尚可"


__all__ = ["describe_market_turnover_condition"]
