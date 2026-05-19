from __future__ import annotations

__all__ = [
    "build_monthly_rhythm_decision",
]


EARNINGS_DEFENSE_MONTHS = {4, 8, 10}


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _target_month(target_date=""):
    text = str(target_date or "").strip()
    try:
        if len(text) >= 7 and text[4] == "-":
            return int(text[5:7])
        if len(text) >= 6 and text[:6].isdigit():
            return int(text[4:6])
    except (TypeError, ValueError):
        return None
    return None


def _normalize_mode(mode=""):
    raw = str(mode or "").strip()
    mapping = {
        "财报防守": "earnings_defense",
        "季报防守": "earnings_defense",
        "财报/季报防守月": "earnings_defense",
        "财报/季报高筛选月": "earnings_defense",
        "防守月": "earnings_defense",
        "弱市防守": "weak_market_defense",
        "弱市场防守月": "weak_market_defense",
        "普通进攻": "ordinary_attack",
        "普通进攻月": "ordinary_attack",
        "进攻确认": "ordinary_attack",
        "强主线进攻": "strong_attack",
        "强主线进攻月": "strong_attack",
        "收益保护": "profit_protection",
    }
    return mapping.get(raw, raw)


def build_monthly_rhythm_decision(
    target_date="",
    monthly_context=None,
    state_machine_snapshot=None,
    final_gate=None,
):
    monthly_context = dict(monthly_context or {})
    state_machine_snapshot = dict(state_machine_snapshot or {})
    final_gate = dict(final_gate or {})

    month_return_pct = _safe_float(
        monthly_context.get("month_return_pct", monthly_context.get("monthly_return_pct", 0.0))
    )
    profit_cushion_pct = _safe_float(monthly_context.get("profit_cushion_pct", 10.0), 10.0)
    loss_guard_pct = _safe_float(monthly_context.get("loss_guard_pct", -3.0), -3.0)
    month = _target_month(target_date)
    explicit_mode = _normalize_mode(monthly_context.get("month_mode", monthly_context.get("monthly_mode", "")))
    execution_bias = str(state_machine_snapshot.get("execution_bias", "") or "").strip()
    energy_state = str(state_machine_snapshot.get("energy_state", "") or "").strip()

    calendar_earnings_month = month in EARNINGS_DEFENSE_MONTHS if month is not None else False
    explicit_attack_override = explicit_mode in ("ordinary_attack", "strong_attack")
    earnings_risk = (
        bool(monthly_context.get("earnings_risk"))
        or explicit_mode == "earnings_defense"
        or (calendar_earnings_month and not explicit_attack_override)
    )
    weak_market = (
        bool(monthly_context.get("weak_market"))
        or bool(monthly_context.get("market_ice_point"))
        or bool(state_machine_snapshot.get("market_ice_point"))
        or bool(final_gate.get("market_ice_point"))
        or explicit_mode == "weak_market_defense"
        or execution_bias in ("avoid", "reduce_only")
    )
    trend_invalid = bool(
        monthly_context.get("trend_invalid")
        or monthly_context.get("mainline_fading")
        or monthly_context.get("structure_invalid")
        or final_gate.get("should_reduce")
    )
    profit_cushion = month_return_pct >= profit_cushion_pct

    if weak_market:
        month_mode = "weak_market_defense"
    elif earnings_risk:
        month_mode = "earnings_defense"
    elif profit_cushion and trend_invalid:
        month_mode = "profit_protection"
    elif month_return_pct <= loss_guard_pct:
        month_mode = "weak_market_defense"
    elif explicit_mode:
        month_mode = explicit_mode
    elif execution_bias == "allow_execute":
        month_mode = "ordinary_attack"
    else:
        month_mode = "attack_prepare"

    allow_execute = execution_bias == "allow_execute" or bool(final_gate.get("can_new_entry"))
    if weak_market or trend_invalid:
        max_position_pct = 0
        allow_full_attack = False
        target_role = "defense_0"
        reason = "大盘冰点、弱市场或趋势失效时，三态模型只允许0%保护本金。"
    elif allow_execute:
        max_position_pct = 100
        allow_full_attack = True
        target_role = "attack_confirmed"
        if month_mode == "earnings_defense":
            reason = "最新三态模型不再因财报月自动压仓；合格标的至少50%，核心标的允许100%。"
        else:
            reason = "进攻窗口打开；盈利不是降档理由，走势继续正确时优先争取100%核心进攻。"
    elif month_mode in ("ordinary_attack", "strong_attack", "attack_prepare", "earnings_defense", "profit_protection"):
        max_position_pct = 50
        allow_full_attack = False
        target_role = "attack_prepare"
        reason = "已有进攻准备但未形成核心对象；三态模型至少按50%标准进攻预演。"
    else:
        max_position_pct = 0
        allow_full_attack = False
        target_role = "defense_0"
        reason = "没有合格标的时，三态模型只允许0%。"

    return {
        "month_mode": month_mode,
        "target_role": target_role,
        "month_return_pct": month_return_pct,
        "profit_cushion_pct": profit_cushion_pct,
        "loss_guard_pct": loss_guard_pct,
        "max_position_pct": max_position_pct,
        "allow_full_attack": allow_full_attack,
        "profit_cushion": profit_cushion,
        "trend_invalid": trend_invalid,
        "energy_state": energy_state,
        "calendar_earnings_month": calendar_earnings_month,
        "reason": reason,
    }
