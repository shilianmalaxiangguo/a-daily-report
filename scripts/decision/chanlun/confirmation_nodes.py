from __future__ import annotations

from .contracts import DEFAULT_CONFIRMATION_PERIOD, LOCAL_ONLY_PERIODS


def _overlap(units):
    if len(units) < 3:
        return None
    zg = min(float(item["high"]) for item in units[:3])
    zd = max(float(item["low"]) for item in units[:3])
    if zg <= zd:
        return None
    return {"ZG": zg, "ZD": zd}


def confirm_with_child_trend_types(child_trend_types, *, period=DEFAULT_CONFIRMATION_PERIOD):
    period_text = str(period)
    if period_text in LOCAL_ONLY_PERIODS:
        return {
            "confirmed": False,
            "confirmation_status": "local_confirmation_only",
            "period": period_text,
            "ZG": None,
            "ZD": None,
            "explanation": f"{period_text}m only supports local confirmation in v1 and cannot confirm the 250-day daily base.",
        }
    units = list(child_trend_types or [])
    zone = _overlap(units)
    if zone is None:
        return {
            "confirmed": False,
            "confirmation_status": "data_insufficient" if len(units) < 3 else "not_confirmed",
            "period": period_text,
            "ZG": None,
            "ZD": None,
            "explanation": "Need three completed child trend types with overlap.",
        }
    return {
        "confirmed": True,
        "confirmation_status": "confirmed_daily_level_zhongshu",
        "period": period_text,
        "ZG": zone["ZG"],
        "ZD": zone["ZD"],
        "explanation": f"Three completed {period_text}m trend types overlap.",
    }


def reject_full_recursive_mode():
    return {
        "mode": "full_recursive_mode",
        "enabled": False,
        "status": "deferred",
        "explanation": "Full recursive mode needs an external long-history minute data store and is outside v1.",
    }
