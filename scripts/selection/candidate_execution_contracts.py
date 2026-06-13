from __future__ import annotations

import daily_report_analysis_utils as analysis_utils
from selection.advantage_dedup_runtime import build_grouped_advantage_score

DEFENSIVE_EXIT_RULE_TEXT = "错了就跑：失效价失守立即卖，最晚不超过单笔-5%"
PROFIT_EXIT_RULE_TEXT = "赚了主动卖：3~5日窗口内出现放量大阳优先兑现，最晚第5日收盘评估"
STRATEGY_HOLDING_DAYS_MIN = 3
STRATEGY_HOLDING_DAYS_MAX = 5

ABNORMAL_SETUP_LIBRARY = {
    "burst_hold": {
        "label": "大阳后抗跌",
        "phase": "hold",
        "group": "burst",
    },
    "burst_digest": {
        "label": "大阳后缩量消化",
        "phase": "digest",
        "group": "burst",
    },
    "upper_shadow_reclaim": {
        "label": "长上影后收复",
        "phase": "hold",
        "group": "upper_shadow",
    },
    "upper_shadow_digest": {
        "label": "长上影后消化",
        "phase": "digest",
        "group": "upper_shadow",
    },
    "horror_wash_hold": {
        "label": "恐怖阴线后抗跌",
        "phase": "hold",
        "group": "horror_wash",
    },
    "horror_wash_digest": {
        "label": "恐怖阴线后消化",
        "phase": "digest",
        "group": "horror_wash",
    },
    "fresh_abnormal_probe": {
        "label": "新异动试盘",
        "phase": "probe",
        "group": "fresh",
    },
    "abnormal_failed": {
        "label": "异动失效",
        "phase": "failed",
        "group": "failed",
    },
}

SETUP_EXECUTION_CONTRACTS = {
    "burst_hold": {
        "holding_days_min": 2,
        "holding_days_max": 4,
        "profit_take_pct": 0.05,
        "profit_exit_rule": "赚了主动卖：2~4日内若再走放量大阳/加速，优先兑现；次日不继续强化就主动收紧。",
    },
    "burst_digest": {
        "holding_days_min": 2,
        "holding_days_max": 4,
        "profit_take_pct": 0.04,
        "profit_exit_rule": "赚了主动卖：2~4日内只接受缩量消化后再转强；拖成横盘就减，不把短线拿成长线。",
    },
    "upper_shadow_reclaim": {
        "holding_days_min": 1,
        "holding_days_max": 3,
        "profit_take_pct": 0.04,
        "profit_exit_rule": "赚了主动卖：1~3日内若重新站回实体并继续冲高，优先兑现；收不回实体就不恋战。",
    },
    "upper_shadow_digest": {
        "holding_days_min": 2,
        "holding_days_max": 3,
        "profit_take_pct": 0.035,
        "profit_exit_rule": "赚了主动卖：只接受短暂消化后再收复实体；超过3日还磨蹭，主动结束交易。",
    },
    "horror_wash_hold": {
        "holding_days_min": 1,
        "holding_days_max": 3,
        "profit_take_pct": 0.05,
        "profit_exit_rule": "赚了主动卖：恐怖阴线后的修复只看快修复，1~3日内不能连续拔高就先兑现，不等二次回落。",
    },
    "horror_wash_digest": {
        "holding_days_min": 2,
        "holding_days_max": 4,
        "profit_take_pct": 0.04,
        "profit_exit_rule": "赚了主动卖：先接受缩量稳住，再等转强兑现；若迟迟不能转强，按短线节奏离场。",
    },
    "fresh_abnormal_probe": {
        "holding_days_min": 1,
        "holding_days_max": 2,
        "profit_take_pct": 0.03,
        "profit_exit_rule": "赚了主动卖：新异动试盘只给1~2天验证，能放大就留，不能放大就撤。",
    },
    "abnormal_failed": {
        "holding_days_min": 1,
        "holding_days_max": 1,
        "profit_take_pct": 0.02,
        "profit_exit_rule": "异动失效不做利润预期，只保留失败记录。",
    },
}

SETUP_PRIORITY_SCORE_MAP = {
    "horror_wash_hold": 100,
    "upper_shadow_reclaim": 96,
    "burst_hold": 92,
    "horror_wash_digest": 82,
    "upper_shadow_digest": 78,
    "burst_digest": 74,
    "fresh_abnormal_probe": 58,
    "abnormal_failed": 0,
}

FOLLOW_STATE_PRIORITY_SCORE_MAP = {
    "跌不下去": 86,
    "缩量消化": 72,
    "新异动待观察": 50,
    "已经转弱": 0,
}

__all__ = [
    "ABNORMAL_SETUP_LIBRARY",
    "DEFENSIVE_EXIT_RULE_TEXT",
    "FOLLOW_STATE_PRIORITY_SCORE_MAP",
    "PROFIT_EXIT_RULE_TEXT",
    "SETUP_EXECUTION_CONTRACTS",
    "SETUP_PRIORITY_SCORE_MAP",
    "STRATEGY_HOLDING_DAYS_MAX",
    "STRATEGY_HOLDING_DAYS_MIN",
    "build_candidate_exit_rules",
    "build_entry_timing_policy",
    "build_gem_textbook_front_text",
    "build_gem_textbook_next_step_text",
    "build_gem_textbook_reference_text",
    "build_limit_up_inertia_profile",
    "build_opportunity_comparison",
    "build_participation_window_from_candidate",
    "build_participation_window_policy",
    "build_quant_anchor_plan",
    "build_philosophy_constraint_text",
    "build_risk_reward_plan",
    "build_weak_to_strong_context",
    "candidate_has_formal_abnormal_setup",
    "candidate_is_resilient_abnormal",
    "format_holding_window_text",
    "get_setup_execution_contract",
    "get_setup_priority_score",
    "infer_risk_level_from_abnormal_follow_state",
    "is_bridge_priority_setup",
    "map_setup_id_to_signal_type",
    "resolve_candidate_follow_state",
    "resolve_candidate_setup_id",
]


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _round_or_none(value, digits=2):
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def _first_number(candidate, *keys, default=None):
    candidate = candidate or {}
    for key in keys:
        value = candidate.get(key)
        if value not in (None, ""):
            return _safe_float(value, default if default is not None else 0.0)
    return default


def _strength_already_contains_lianban_bonus(candidate, *, tomorrow_strength=0, lianban=0):
    if int(lianban or 0) < 2:
        return False
    base_strength = _first_number(candidate, "base_strength_score", default=None)
    if base_strength is None:
        return False
    return _safe_float(tomorrow_strength, 0) - base_strength >= 8


def _append_suppressed_advantage_points(advantage_dedup, points):
    if not points:
        return advantage_dedup
    updated = dict(advantage_dedup or {})
    suppressed_points = list(updated.get("suppressed_points") or [])
    for point in points:
        point = dict(point or {})
        score = _safe_float(point.get("score", 0), 0)
        suppressed_points.append(
            {
                "group": str(point.get("group") or "misc"),
                "label": str(point.get("label") or point.get("group") or "misc"),
                "score": score,
                "raw_score": _safe_float(point.get("raw_score", score), score),
                "source": str(point.get("source") or ""),
            }
        )
    updated["suppressed_points"] = suppressed_points
    updated["repeated_advantage_count"] = len(suppressed_points)
    return updated


def build_limit_up_inertia_profile(candidate=None):
    candidate = candidate or {}
    pattern = str(candidate.get("pattern", "") or "")
    reason_text = " / ".join(
        str(candidate.get(key, "") or "")
        for key in (
            "conviction_reason",
            "reason",
            "conviction_rule",
            "core_level",
            "stock_setup",
        )
    )
    combined = f"{pattern} / {reason_text}"
    lianban = int(_safe_float(candidate.get("连板数", candidate.get("lianban", 0)), 0))
    change_pct = _first_number(candidate, "change_pct", "change", "pct_chg", "涨跌幅", default=0.0)
    tomorrow_strength = _first_number(candidate, "tomorrow_strength", "score", default=0.0)
    is_limit_shape = any(marker in combined for marker in ("涨停", "T字", "一字", "连板", "打板", "回封"))

    if lianban >= 1 or is_limit_shape or any(marker in combined for marker in ("锚定龙", "龙一", "主线核心", "主线内核")):
        score = 78 + min(lianban, 4) * 7
        if "主线" in combined or "锚定龙" in combined or "龙一" in combined:
            score += 8
        inertia_points = []
        suppressed_inertia_points = []
        if tomorrow_strength >= 90:
            strength_point = {"group": "front_recognition", "label": "强度已到前排", "score": 5}
            if _strength_already_contains_lianban_bonus(candidate, tomorrow_strength=tomorrow_strength, lianban=lianban):
                suppressed_inertia_points.append({"group": "front_recognition", "label": f"{lianban}连板已体现在强度", "score": 5})
            else:
                inertia_points.append(strength_point)
        inertia_dedup = _append_suppressed_advantage_points(
            build_grouped_advantage_score(inertia_points),
            suppressed_inertia_points,
        )
        score += inertia_dedup["total_score"]
        return {
            "limit_up_inertia_level": "高惯性",
            "limit_up_inertia_score": min(score, 100),
            "next_day_limit_probability_band": "高于普通上涨样本",
            "limit_up_inertia_reason": "昨日涨停/连板/T字板已经被资金选择，次日冲高或再涨停概率高于普通上涨样本；只在竞价、回封或09:50-10:10窗口承接成立时参与",
            "limit_up_inertia_dedup": inertia_dedup,
        }

    if change_pct >= 5 or tomorrow_strength >= 80 or "强实体" in combined:
        return {
            "limit_up_inertia_level": "中惯性",
            "limit_up_inertia_score": 58,
            "next_day_limit_probability_band": "高于弱上涨样本",
            "limit_up_inertia_reason": "有强趋势或强实体，但不是昨日涨停惯性，先看09:50-10:10承接再决定",
        }

    return {
        "limit_up_inertia_level": "低惯性",
        "limit_up_inertia_score": 32,
        "next_day_limit_probability_band": "接近普通上涨样本",
        "limit_up_inertia_reason": "普通上涨不等同于资金已经选择，不能和昨日涨停/连板样本同权处理",
    }


def build_risk_reward_plan(candidate=None, *, min_ratio=2.0):
    candidate = candidate or {}
    entry = _first_number(
        candidate,
        "probe_entry_price",
        "ma_reversion_entry",
        "ma5",
        "ma10",
        "close",
        default=None,
    )
    stop = _first_number(
        candidate,
        "stop_price",
        "ma20",
        "effective_stop",
        "stop_loss",
        default=None,
    )
    target = _first_number(
        candidate,
        "target_price",
        "limit_up_price",
        "previous_high",
        "recent_high",
        "high",
        default=None,
    )

    base = {
        "risk_reward_min_ratio": float(min_ratio),
        "risk_reward_ratio": None,
        "risk_reward_state": "待计算",
        "risk_reward_plan": f"默认要求盈亏比不低于{min_ratio:g}:1；缺少观察位、作废线或上方空间时，不能把均线回归当观察位，只观察等价格事实补齐",
    }
    if entry is None or stop is None or target is None or entry <= 0 or stop <= 0 or target <= 0:
        return base

    downside = entry - stop
    upside = target - entry
    if downside <= 0 or upside <= 0:
        base.update(
            {
                "risk_reward_state": "不合格",
                "risk_reward_ratio": 0.0,
                "risk_reward_plan": "观察位、作废线和上方空间不构成正向盈亏比；只观察，不做均线试错",
            }
        )
        return base

    ratio = round(upside / downside, 2)
    state = "合格" if ratio >= float(min_ratio) else "不合格"
    if state == "合格":
        plan = f"试错前要求盈亏比不低于{min_ratio:g}:1；当前约{ratio}:1，允许在09:50-10:10承接成立后小仓参与"
    else:
        plan = f"试错前要求盈亏比不低于{min_ratio:g}:1；当前约{ratio}:1，不满足就只观察，不为低价感补仓"
    base.update(
        {
            "risk_reward_ratio": ratio,
            "risk_reward_state": state,
            "risk_reward_plan": plan,
        }
    )
    return base


def _first_text(candidate, *keys, default=""):
    candidate = candidate or {}
    for key in keys:
        value = candidate.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return default


def _downside_pct(entry, risk_price):
    try:
        entry = float(entry)
        risk_price = float(risk_price)
    except (TypeError, ValueError):
        return None
    if entry <= 0 or risk_price <= 0 or risk_price >= entry:
        return 0.0
    return round((entry - risk_price) / entry * 100, 2)


def _risk_price_comfort(*, entry, ma5, ma10, vwap, invalid_price):
    if entry is None or invalid_price is None:
        return "incomplete"
    risk_distances = {
        "ma5": _downside_pct(entry, ma5),
        "ma10": _downside_pct(entry, ma10),
        "vwap": _downside_pct(entry, vwap),
    }
    usable_distances = [value for value in risk_distances.values() if value is not None]
    if not usable_distances:
        return "incomplete"
    if risk_distances.get("ma5") is not None and risk_distances["ma5"] >= 5:
        return "unacceptable"
    nearest = min(value for value in usable_distances if value >= 0)
    if nearest >= 5:
        return "unacceptable"
    if nearest >= 3:
        return "stretched"
    return "comfortable"


def _candidate_materially_stronger(candidate):
    role = _first_text(candidate, "target_role", "role", "quality_role")
    role_is_core = role in {"core", "sector_anchor", "主线核心", "板块锚", "趋势核心"}
    evidence = candidate.get("strength_evidence") or candidate.get("positive_shape_evidence") or []
    if isinstance(evidence, str):
        evidence = [evidence]
    evidence_count = len([item for item in evidence if str(item or "").strip()])
    strength_score = _first_number(candidate, "tomorrow_strength", "strength_score", "quality_score", default=0)
    return bool(role_is_core and (evidence_count >= 2 or strength_score >= 85))


def _old_position_weakening(old_position):
    old_position = old_position or {}
    state = _first_text(old_position, "old_logic_state", "logic_state")
    action = _first_text(old_position, "old_plan_action", "action")
    return state in {"weakening", "invalid", "转弱", "失效"} or action in {"reduce", "exit", "repair_once", "减仓", "卖出"}


def build_opportunity_comparison(
    *,
    old_position=None,
    new_target=None,
    account_capital=None,
    requested_participation_pct=100,
    min_ratio=2.0,
):
    old_position = dict(old_position or {})
    new_target = dict(new_target or {})
    risk_reward = build_risk_reward_plan(new_target, min_ratio=min_ratio)
    entry = _first_number(
        new_target,
        "observation_price",
        "probe_entry_price",
        "ma_reversion_entry",
        "close",
        "price",
        "latest_price",
        default=None,
    )
    ma5 = _first_number(new_target, "ma5", "MA5", default=None)
    ma10 = _first_number(new_target, "ma10", "MA10", default=None)
    vwap = _first_number(new_target, "vwap", "VWAP", "intraday_vwap", default=None)
    invalid_price = _first_number(new_target, "invalid_price", "stop_price", "ma20", "effective_stop", "stop_loss", default=None)
    target_price = _first_number(new_target, "target_price", "limit_up_price", "previous_high", "recent_high", "high", default=None)
    risk_price_comfort = _risk_price_comfort(
        entry=entry,
        ma5=ma5,
        ma10=ma10,
        vwap=vwap,
        invalid_price=invalid_price,
    )
    missing_fields = []
    if entry is None:
        missing_fields.append("observation_price")
    if invalid_price is None:
        missing_fields.append("invalid_price")
    if target_price is None:
        missing_fields.append("target_price")
    if risk_price_comfort == "incomplete":
        missing_fields.append("risk_price")

    stronger = _candidate_materially_stronger(new_target)
    old_weakening = _old_position_weakening(old_position)
    risk_controllable = risk_reward["risk_reward_state"] == "合格" and risk_price_comfort == "comfortable"
    old_must_release = bool(old_position and old_weakening and stronger and risk_controllable)
    requested_pct = int(_safe_float(requested_participation_pct, 0))
    max_pct = min(max(requested_pct, 0), 100) if risk_controllable and stronger else 0
    if risk_price_comfort == "incomplete":
        final_action = "只保留观察，等风险价格补齐"
        capital_result = "observe"
    elif not risk_controllable and risk_price_comfort in {"stretched", "unacceptable"}:
        final_action = "强度保留，等待回踩/收回窗口"
        capital_result = "wait"
    elif risk_reward["risk_reward_state"] != "合格":
        final_action = "只保留观察，等待盈亏比修复"
        capital_result = "observe"
    elif old_must_release:
        final_action = "先释放旧仓资金，只在固定交易窗口参与新核心"
        capital_result = "new_entry_after_old_exit"
    elif stronger and risk_controllable:
        final_action = "新目标具备参与条件，按固定交易窗口执行"
        capital_result = "new_entry_after_old_exit" if old_position else "wait"
    else:
        final_action = "旧仓按原计划处理，新目标观察"
        capital_result = "old_position_t" if old_position else "observe"

    return {
        "schema_version": "opportunity_comparison.v1",
        "account_capital": account_capital or old_position.get("account_capital") or new_target.get("account_capital"),
        "old_position": {
            "name": _first_text(old_position, "name", "stock_name"),
            "code": _first_text(old_position, "code", "stock_code"),
            "shares": old_position.get("shares"),
            "sellable_shares": old_position.get("sellable_shares"),
            "unsellable_shares": old_position.get("unsellable_shares"),
            "holding_role": _first_text(old_position, "holding_role", default="old_position" if old_position else "unknown"),
            "old_logic_state": _first_text(old_position, "old_logic_state", "logic_state", default="incomplete"),
            "old_plan_action": _first_text(old_position, "old_plan_action", "action", default="observe"),
            "old_plan_reason": _first_text(old_position, "old_plan_reason", "reason"),
            "lower_defense_price": _first_number(old_position, "lower_defense_price", "defense_price", "stop_price", default=None),
            "upper_take_profit_price": _first_number(old_position, "upper_take_profit_price", "take_profit_price", "target_price", default=None),
            "missing_fields": [],
        },
        "new_target": {
            "name": _first_text(new_target, "name", "stock_name"),
            "code": _first_text(new_target, "code", "stock_code"),
            "line": _first_text(new_target, "line", "sector", "mainline"),
            "target_role": _first_text(new_target, "target_role", "role", "quality_role", default="unknown"),
            "strength_evidence": new_target.get("strength_evidence") or [],
            "entry_window": _first_text(new_target, "entry_window", "buy_window", "participation_window", default="no_trade"),
            "observation_price": entry,
            "ma5": ma5,
            "ma10": ma10,
            "vwap": vwap,
            "invalid_price": invalid_price,
            "target_price": target_price,
            "downside_to_ma5_pct": _downside_pct(entry, ma5),
            "downside_to_ma10_pct": _downside_pct(entry, ma10),
            "downside_to_vwap_pct": _downside_pct(entry, vwap),
            "downside_to_invalid_pct": _downside_pct(entry, invalid_price),
            "risk_reward_ratio": risk_reward.get("risk_reward_ratio"),
            "risk_reward_state": risk_reward.get("risk_reward_state"),
            "risk_reward_plan": risk_reward.get("risk_reward_plan"),
            "risk_price_comfort": risk_price_comfort,
            "missing_fields": missing_fields,
        },
        "comparison": {
            "new_target_materially_stronger": stronger,
            "old_position_must_be_released": old_must_release,
            "risk_boundary_controllable": risk_controllable,
            "capital_efficiency_result": capital_result,
            "max_participation_pct": max_pct,
            "final_action": final_action,
            "reason": final_action,
        },
    }


def build_gem_textbook_reference_text(label=""):
    label = str(label or "").strip()
    if label != "A级教材":
        return ""
    return (
        "参考样本：东山精密（元件/CPO双主线、业绩预增、历史新高）、"
        "朗特智能（消费电子/液冷推进、量价转强）、"
        "均胜电子（汽零/智驾+机器人双曲线、机构调研支撑）；"
        "反例：常友科技（风电设备，板块热度和持续性都弱）"
    )


def build_gem_textbook_front_text(candidate=None, position_decision=None):
    candidate = candidate or {}
    position_decision = position_decision or {}
    if str(candidate.get("watch_source", "") or "").strip() != "gem_breathing_20cm" and not candidate.get("textbook_label"):
        return ""

    label = str(candidate.get("textbook_label", "") or "").strip()
    profile = candidate.get("textbook_profile", {}) or {}
    last_active_date = str(profile.get("last_active_date", "") or "").strip()
    total_active_count = int(_safe_float(profile.get("total_active_count", 0)))
    tight_count = int(_safe_float(profile.get("tight_count", 0)))
    loose_count = int(_safe_float(profile.get("loose_count", 0)))
    target_position_pct = int(_safe_float(position_decision.get("target_position_pct", 0)))
    trigger_text = str(position_decision.get("trigger_text", "") or "09:50-10:10窗口满足条件").strip()
    if trigger_text == "09:50-10:10窗口":
        trigger_text = "09:50-10:10窗口内满足条件"
    ready = bool(position_decision.get("candidate_feedback_ready"))

    prefix_parts = []
    if label:
        prefix_parts.append(label)
    if total_active_count:
        prefix_parts.append(f"近60日{total_active_count}次")
    if tight_count or loose_count:
        prefix_parts.append(f"tight {tight_count} / loose {loose_count}")
    if last_active_date:
        prefix_parts.append(f"最近一次{last_active_date}")
    prefix = "，".join(prefix_parts) if prefix_parts else "20cm教材样本"

    reference_text = build_gem_textbook_reference_text(label)
    if reference_text:
        prefix = f"{prefix}；{reference_text}"

    if 0 < target_position_pct < 50:
        next_step = f"当前已进入50%条件执行，{trigger_text}后才允许动手，不满足转为0%不参与"
    elif label == "A级教材":
        next_step = "当前还差右侧确认和09:50-10:10窗口，确认后才评估50%条件执行" if not ready else f"反馈已接近到位，{trigger_text}后可评估50%条件执行"
    elif label == "B级教材":
        next_step = "先保留观察合同，等它走成右侧确认后再考虑升级"
    elif label == "C级观察样本":
        next_step = "不提前升级，只跟踪它会不会再次复现并走成右侧确认"
    else:
        next_step = "先保留观察合同，不直接给买入资格"

    return f"{prefix}；{next_step}"


def build_gem_textbook_next_step_text(candidate=None, position_decision=None):
    front_text = build_gem_textbook_front_text(candidate=candidate, position_decision=position_decision)
    if not front_text:
        return ""
    parts = [part.strip() for part in str(front_text).split("；") if part.strip()]
    return parts[-1] if parts else ""


def resolve_candidate_setup_id(candidate):
    candidate = candidate or {}
    return str(
        candidate.get("abnormal_setup_signal_id")
        or candidate.get("setup_signal_id")
        or ""
    ).strip()


def resolve_candidate_follow_state(candidate):
    candidate = candidate or {}
    return str(
        candidate.get("abnormal_follow_state")
        or candidate.get("follow_state")
        or ""
    ).strip()


def candidate_has_formal_abnormal_setup(candidate):
    setup_id = resolve_candidate_setup_id(candidate)
    return bool(setup_id and setup_id not in ("abnormal_failed",))


def candidate_is_resilient_abnormal(candidate):
    return resolve_candidate_follow_state(candidate) in ("跌不下去", "缩量消化")


def is_bridge_priority_setup(candidate, mainline_name=""):
    candidate = candidate or {}
    if not (candidate.get("is_mainline") or analysis_utils._candidate_matches_mainline(candidate, mainline_name)):
        return False
    return (
        resolve_candidate_setup_id(candidate) == "burst_hold"
        and resolve_candidate_follow_state(candidate) == "跌不下去"
    )


def build_weak_to_strong_context(candidate=None, mainline_name="", state_machine_snapshot=None):
    candidate = candidate or {}
    state_machine_snapshot = state_machine_snapshot or {}
    mainline_name = str(mainline_name or state_machine_snapshot.get("leading_line", "") or "").strip()
    name = str(candidate.get("name", "-") or "-").strip()
    code = str(candidate.get("code", "-") or "-").strip()
    setup_id = str(resolve_candidate_setup_id(candidate) or "").strip()
    follow_state = str(resolve_candidate_follow_state(candidate) or "").strip()
    energy_state = str(state_machine_snapshot.get("energy_state", "") or "").strip()
    pulse_stage = str(state_machine_snapshot.get("pulse_stage", "") or "").strip()
    strong_base = setup_id in (
        "burst_hold",
        "burst_digest",
        "upper_shadow_reclaim",
        "upper_shadow_digest",
        "horror_wash_hold",
        "horror_wash_digest",
    ) or "核心" in str(candidate.get("core_level", "") or "")
    fake_weak = follow_state in ("跌不下去", "缩量消化")
    mainline_support = analysis_utils._candidate_matches_mainline(candidate, mainline_name) if mainline_name else False
    retreat_risk = energy_state == "收缩防守" or pulse_stage == "退潮"

    if strong_base and fake_weak and mainline_support and not retreat_risk:
        return {
            "active": True,
            "scenario": "active",
            "summary_text": f"{name}({code})，第一波强势基础还在，当前是假弱非真弱；只在{mainline_name or '主线'}板块共振未坏时看后续超预期转强",
            "note_text": "强基底+假弱非真弱，只在主线共振未坏时继续等超预期转强",
            "score_bonus": 160,
            "lone_hero": False,
        }
    if strong_base and follow_state == "已经转弱":
        return {
            "active": False,
            "scenario": "true_weak",
            "summary_text": f"{name}({code}) 前面虽有强基底，但现在已经转弱，更像真弱，不再按弱转强处理",
            "note_text": "已经转弱，更像真弱，先从顶级买点序列降级",
            "score_bonus": -120,
            "lone_hero": False,
        }
    if strong_base and fake_weak and retreat_risk:
        return {
            "active": False,
            "scenario": "retreat_downgrade",
            "summary_text": f"{name}({code}) 虽有强基底和假弱特征，但当前环境更像退潮/防守期，弱转强先降级为观察",
            "note_text": "当前处于退潮/防守期，弱转强先降级为观察，不按顶级买点处理",
            "score_bonus": 0,
            "lone_hero": False,
        }
    if strong_base and fake_weak and not mainline_support:
        return {
            "active": False,
            "scenario": "lone_hero",
            "summary_text": f"{name}({code}) 虽有假弱转强形态，但当前更像孤胆英雄，缺少板块共振，不按顶级买点处理",
            "note_text": "形态虽像假弱转强，但缺少板块共振，只保留观察权",
            "score_bonus": 0,
            "lone_hero": True,
        }
    return {
        "active": False,
        "scenario": "inactive",
        "summary_text": "",
        "note_text": "",
        "score_bonus": 0,
        "lone_hero": False,
    }


def build_philosophy_constraint_text(
    final_gate=None,
    best_stock=None,
    watch_anchor=None,
    watch_anchor_type="",
    state_machine_snapshot=None,
):
    final_gate = final_gate or {}
    state_machine_snapshot = state_machine_snapshot or {}
    watch_anchor_type = str(watch_anchor_type or "").strip()
    energy_state = str(state_machine_snapshot.get("energy_state", "") or "").strip()
    execution_bias = str(state_machine_snapshot.get("execution_bias", "") or "").strip()
    fragments = []

    if best_stock:
        fragments.append("不为新故事切掉旧事实，只围绕已被市场证明的主线强者行动")
        if final_gate.get("can_new_entry"):
            fragments.append("这更像切入的钱，不是到处换故事的钱")
        else:
            fragments.append("若你已有主线核心，更先想卖不卖，而不是买不买")
    elif watch_anchor and "跨线" in watch_anchor_type:
        fragments.append("不为新故事切掉旧事实")

    if final_gate.get("can_new_entry") and any(key in energy_state for key in ("扩张", "进攻")):
        fragments.append("外部风险若已被市场脱敏，只保留背景作用")

    if execution_bias in ("watch_only", "divergence_only", "avoid") or (watch_anchor and "跨线" in watch_anchor_type):
        fragments.append("主观理解只用于观察，不用于提前硬上")

    ordered = []
    for fragment in fragments:
        text = str(fragment or "").strip()
        if text and text not in ordered:
            ordered.append(text)
    return "；".join(ordered)


def get_setup_execution_contract(setup_id="", follow_state=""):
    setup_id = str(setup_id or "").strip()
    follow_state = str(follow_state or "").strip()

    contract = dict(SETUP_EXECUTION_CONTRACTS.get(setup_id, {}))
    if not contract:
        contract = {
            "holding_days_min": STRATEGY_HOLDING_DAYS_MIN,
            "holding_days_max": STRATEGY_HOLDING_DAYS_MAX,
            "profit_take_pct": 0.05,
            "profit_exit_rule": PROFIT_EXIT_RULE_TEXT,
        }

    if follow_state == "新异动待观察":
        contract["holding_days_min"] = min(contract.get("holding_days_min", 1), 1)
        contract["holding_days_max"] = min(contract.get("holding_days_max", 2), 2)
    elif follow_state == "已经转弱":
        contract["holding_days_min"] = 1
        contract["holding_days_max"] = 1

    contract.setdefault("holding_days_min", STRATEGY_HOLDING_DAYS_MIN)
    contract.setdefault("holding_days_max", STRATEGY_HOLDING_DAYS_MAX)
    contract.setdefault("profit_take_pct", 0.05)
    contract.setdefault("profit_exit_rule", PROFIT_EXIT_RULE_TEXT)
    return contract


def get_setup_priority_score(setup_id="", follow_state=""):
    setup_id = str(setup_id or "").strip()
    follow_state = str(follow_state or "").strip()
    if setup_id:
        return SETUP_PRIORITY_SCORE_MAP.get(
            setup_id,
            FOLLOW_STATE_PRIORITY_SCORE_MAP.get(follow_state, 24),
        )
    return FOLLOW_STATE_PRIORITY_SCORE_MAP.get(follow_state, 18)


def infer_risk_level_from_abnormal_follow_state(follow_state):
    follow_state = str(follow_state or "").strip()
    if follow_state == "跌不下去":
        return "🟢 低风险"
    if follow_state == "缩量消化":
        return "🟡 中风险"
    if follow_state == "新异动待观察":
        return "🟠 待确认"
    if follow_state == "已经转弱":
        return "🔴 高风险"
    return "🟡 中风险"


def map_setup_id_to_signal_type(setup_id=""):
    setup_id = str(setup_id or "").strip()
    if setup_id in ("horror_wash_hold", "horror_wash_digest"):
        return "panic_buy"
    if setup_id in ("upper_shadow_reclaim", "upper_shadow_digest"):
        return "sweet_zone"
    if setup_id in ("burst_hold", "burst_digest", "fresh_abnormal_probe"):
        return "breakout"
    return ""


def build_entry_timing_policy(*, source_tier="extreme_conviction", participation_window_type="", participation_window=""):
    source_tier = str(source_tier or "extreme_conviction").strip() or "extreme_conviction"
    window_type = str(participation_window_type or "").strip()
    window_text = str(participation_window or "").strip()
    combined = f"{window_type} / {window_text}"

    no_trade_markers = ("只观察", "不开", "不参与", "禁止", "no_trade", "none")
    if source_tier in ("crossline_watch", "ordinary_watch") or any(marker in combined for marker in no_trade_markers):
        return {
            "source_tier": source_tier,
            "entry_timing": "no_trade",
            "buy_window": "none",
            "entry_timing_reason": "非重点观察执行层，或计划明确只观察，不生成买入窗口",
        }

    if any(marker in combined for marker in ("尾盘", "14:30", "14:45", "收盘前")):
        return {
            "source_tier": source_tier,
            "entry_timing": "tail_exception",
            "buy_window": "14:30-14:55",
            "entry_timing_reason": "尾盘只作为买卖窗口期的例外处理，用于避开盘中分歧消耗",
        }

    if window_type in ("auction_reseal", "board_or_miss") or any(
        marker in combined for marker in ("竞价", "回封", "打板")
    ):
        return {
            "source_tier": source_tier,
            "entry_timing": "open_core",
            "buy_window": "09:30-09:35",
            "entry_timing_reason": "强核心必须用开盘表态和回封质量验证，不能拖到后段确认",
        }

    return {
        "source_tier": source_tier,
        "entry_timing": "ten_confirm",
        "buy_window": "09:50-10:10",
        "entry_timing_reason": "普通结构样本先等早盘承接稳定，再看09:50-10:10窗口条件是否满足",
    }


def build_quant_anchor_plan(candidate=None):
    candidate = candidate or {}

    def _text(*keys):
        for key in keys:
            value = candidate.get(key)
            if value not in (None, ""):
                return str(value).strip()
        return ""

    zone = _text("anchor_zone_role", "quant_anchor_zone", "price_anchor_zone")
    confluence = _text("anchor_line_confluence", "quant_anchor_confluence", "price_anchor_confluence")
    hidden = _text("hidden_liquidity_read", "hidden_liquidity", "quant_hidden_liquidity")
    action = _text("anchor_action_plan", "quant_anchor_action", "price_anchor_action")
    factors = _text("common_selection_factors", "quant_common_selection_factors")
    momentum = _text("momentum_feedback_plan", "quant_momentum_feedback")
    reversal = _text("reversal_exit_plan", "quant_reversal_exit")

    if not any((zone, confluence, hidden, action, factors, momentum, reversal)):
        return {}

    if not action:
        if "顶部" in zone:
            action = "区间顶部锚点冲不过先止盈；放量吃掉并回踩不破，才恢复候选资格"
        elif "底部" in zone:
            action = "区间底部锚点只作承接观察；未站回VWAP前不直接参与，缩量止跌、站回VWAP且09:50-10:10窗口条件满足后，才允许50%条件执行"
        elif "吃掉" in zone or "消化" in hidden:
            action = "锚点被放量吃掉并回踩不破，只恢复候选资格；不能自动升级主买"
        elif "高潮" in zone or "反包" in zone:
            action = "高潮后反包先按先手兑现点；放量吃掉压力并回踩不破，才恢复候选观察"
        else:
            action = "锚点只作价格反应观察；必须叠加VWAP、MA和承接确认"
    if not factors:
        factors = "共同选择按四方检查：昨日持筹者、明日新买盘、主线资金、量化动量是否一致"
    if not momentum:
        momentum = "量化动量助攻才提高参与质量；越跌越弱时不低吸，站回VWAP后再看"
    if not reversal:
        reversal = "高潮后反包先按先手兑现点；放量吃掉压力并回踩不破后，才恢复候选观察"

    return {
        "anchor_zone_role": zone or "待确认",
        "anchor_line_confluence": confluence or "等待确认VWAP、MA、前高前低或成交密集区共振",
        "hidden_liquidity_read": hidden or "隐藏买卖盘待确认",
        "anchor_action_plan": action,
        "common_selection_factors": factors,
        "momentum_feedback_plan": momentum,
        "reversal_exit_plan": reversal,
    }


def _no_trade_observation_script_fields(reason="只观察，不新增参与"):
    reason = str(reason or "").strip() or "只观察，不新增参与"
    observation_text = f"{reason}；不生成新增参与动作"
    intraday_text = f"{reason}；分时黄线、均线和0轴只作为风险观察，不作为新增参与依据"
    return {
        "auction": observation_text,
        "auction_script": observation_text,
        "first_minutes": observation_text,
        "first_minutes_script": observation_text,
        "board": observation_text,
        "board_script": observation_text,
        "reseal": observation_text,
        "reseal_script": observation_text,
        "missed_action": reason,
        "cancellation": "保持0%不参与",
        "invalid_condition": "保持0%不参与",
        "intraday_yellow_line_probe": intraday_text,
        "intraday_average_line_cross_probe": intraday_text,
        "zero_axis_reclaim_probe": intraday_text,
        "daily_ma_entry_probe": f"{reason}；MA3/MA5/MA10只作观察和风险线，不生成新增参与资格",
    }


def build_participation_window_policy(window="", missed_action="", source_tier="extreme_conviction", candidate=None):
    window = str(window or "").strip()
    missed_action = str(missed_action or "").strip()
    no_trade_markers = ("只观察", "不开", "不参与", "禁止", "no_trade", "none")
    if any(marker in f"{window} / {missed_action}" for marker in no_trade_markers):
        window_type = "no_trade"
        auction_required = False
        first_minutes_required = False
        board_or_reseal_required = False
        ordinary_structure_confirm_allowed = False
        required_steps = ["只观察，不新增参与"]
        fallback_state = "保持0%不参与"
        participation_basis = {
            "observation": "计划明确只观察，不生成买入窗口",
            "missed_entry": missed_action or "只观察，不新增参与",
        }
        no_trade_fields = _no_trade_observation_script_fields(missed_action)
    elif "打板/错过" in window:
        window_type = "board_or_miss"
        auction_required = True
        first_minutes_required = True
        board_or_reseal_required = True
        ordinary_structure_confirm_allowed = False
        required_steps = ["交易逻辑确认", "竞价表态", "开盘前几分钟承接", "MA执行锚点", "回封/打板"]
        fallback_state = "不满足回到0%"
        participation_basis = {
            "auction": "价格位置 / 匹配金额 / 委托稳定 / 板块同步",
            "first_minutes": "主动资金继续抬价 / 承接连续",
            "ma_reversion": "量能、情绪、板块、资金、辨识度和承接已经给出买入资格后，才看日K MA5/MA10与分时黄线优化买点",
            "board_or_reseal": "大单金额持续进入 / 快速回封 / 封单质量改善",
            "missed_entry": missed_action,
        }
    elif "竞价" in window or "回封" in window:
        window_type = "auction_reseal"
        auction_required = True
        first_minutes_required = True
        board_or_reseal_required = True
        ordinary_structure_confirm_allowed = False
        required_steps = ["交易逻辑确认", "竞价表态", "开盘前几分钟承接", "MA执行锚点", "回封/打板"]
        fallback_state = "不满足回到0%"
        participation_basis = {
            "auction": "价格位置 / 匹配金额 / 委托稳定 / 板块同步",
            "first_minutes": "主动资金继续抬价 / 承接连续",
            "ma_reversion": "量能、情绪、板块、资金、辨识度和承接已经给出买入资格后，才看日K MA5/MA10与分时黄线优化买点",
            "board_or_reseal": "大单金额持续进入 / 快速回封 / 封单质量改善",
            "missed_entry": missed_action,
        }
    elif "开盘前几分钟" in window and "09:50-10:10" in window:
        window_type = "opening_structure_confirm"
        auction_required = False
        first_minutes_required = True
        board_or_reseal_required = False
        ordinary_structure_confirm_allowed = True
        required_steps = ["交易逻辑确认", "开盘前几分钟承接", "主线确认", "09:50-10:10窗口", "MA执行锚点"]
        fallback_state = "不满足回到0%"
        participation_basis = {
            "first_minutes": "主动资金继续抬价 / 承接连续",
            "ma_reversion": "量能、情绪、板块、资金、辨识度和承接已经给出买入资格后，才看日K MA5/MA10与分时黄线优化买点",
            "structure": "09:50-10:10窗口只服务普通结构，不覆盖强核心快路径",
            "missed_entry": missed_action,
        }
    else:
        window_type = "structure_confirm"
        auction_required = False
        first_minutes_required = False
        board_or_reseal_required = False
        ordinary_structure_confirm_allowed = True
        required_steps = ["交易逻辑确认", "主线确认", "承接", "09:50-10:10窗口", "MA执行锚点"]
        fallback_state = "不满足回到0%"
        participation_basis = {
            "ma_reversion": "量能、情绪、板块、资金、辨识度和承接已经给出买入资格后，才看日K MA5/MA10与分时黄线优化买点",
            "structure": "09:50-10:10窗口只服务普通结构，不覆盖强核心快路径",
            "missed_entry": missed_action,
        }
    if window_type != "no_trade":
        no_trade_fields = {}

    policy = {
        "participation_window_type": window_type,
        "auction_required": auction_required,
        "first_minutes_required": first_minutes_required,
        "board_or_reseal_required": board_or_reseal_required,
        "ordinary_structure_confirm_allowed": ordinary_structure_confirm_allowed,
        "missed_entry_policy": missed_action,
        "required_steps": required_steps,
        "fallback_state": fallback_state,
        "participation_basis": participation_basis,
        "decision_reason_basis": "买卖资格只来自量能、市场情绪、板块效应、资金表态、辨识度和连续承接；技术指标不能单独生成交易理由",
        "ma_execution_anchor": "MA3/MA5/MA10只优化买卖点和失效线，不能替代交易逻辑",
        "ma_reversion_probe_allowed": source_tier == "extreme_conviction" and window_type != "no_trade",
        "ma_reversion_window": "09:50-10:10" if source_tier == "extreme_conviction" and window_type != "no_trade" else "none",
        "ma_reversion_probe": "只限已经由量能、情绪、板块、资金、辨识度和承接给出买入资格的样本；常规回踩日K MA5/MA10，极度龙头可提前看MA3；MA只是执行锚点，不能因为MA3/MA5/MA10单独买入；分时黄线不破，且9:50-10:10承接不再继续杀，才允许50%条件执行",
        "intraday_yellow_line_probe": "分时黄线只作为日内承接确认线；09:50-10:10价格上穿分时黄色均价线并形成金叉，或水下强势修复到0轴后承接连续，才算试错条件；不是所有股票的低吸理由",
        "intraday_average_line_cross_probe": "09:50-10:10价格上穿分时黄色均价线并形成金叉，且上穿后不再快速跌回黄线下方，才允许50%条件执行",
        "zero_axis_reclaim_probe": "水下强势修复到0轴，0轴附近不再放量回落，才允许把修复视为资金重新表态",
        "daily_ma_entry_probe": "逻辑确认后再看MA3/MA5/MA10：MA3/MA5/MA10分别对应极度龙头/强势/趋势；MA不是买入理由，只是执行锚点和失效参考，仍要叠加分时承接",
        "daily_ma_role_map": {
            "ma3": "极度龙头",
            "ma5": "强势",
            "ma10": "趋势",
        },
        "ma20_invalidation": "有效跌破日K MA20或跌破后9:50-10:10不能收回，取消幻想，按A杀风险处理",
        "tracking_window_trade_days": 25,
    }
    policy.update(build_quant_anchor_plan(candidate))
    policy.update(build_limit_up_inertia_profile(candidate))
    policy.update(build_risk_reward_plan(candidate))
    policy.update(
        build_entry_timing_policy(
            source_tier=source_tier,
            participation_window_type=window_type,
            participation_window=window,
        )
    )
    policy.update(no_trade_fields)
    return policy


def build_participation_window_from_candidate(candidate=None, *, is_anchor=False, is_mainline=False):
    candidate = candidate or {}

    explicit = str(
        candidate.get("participation_window")
        or candidate.get("entry_window")
        or candidate.get("execution_window")
        or candidate.get("window")
        or candidate.get("conviction_window")
        or ""
    ).strip()
    if explicit:
        return explicit

    pattern = str(candidate.get("pattern", "") or "")
    core_level = str(candidate.get("core_level", "") or "")
    reason_text = " / ".join(
        str(candidate.get(key, "") or "")
        for key in (
            "conviction_reason",
            "stock_setup",
            "setup",
            "reason",
            "conviction_rule",
            "role",
        )
    )
    combined = f"{pattern} / {core_level} / {reason_text}"

    if "一字" in combined:
        return "打板/错过"

    fast_markers = (
        "T字",
        "涨停",
        "连板",
        "主线核心",
        "主线内核",
        "板块锚定龙",
        "趋势比价链锚定龙",
        "首波先锋",
        "分歧转一致",
        "资金顶出辨识度",
    )
    if is_anchor or any(marker in combined for marker in fast_markers):
        return "竞价表态 + 回封参与"

    if is_mainline:
        return "开盘前几分钟 + 09:50-10:10窗口"
    return "09:50-10:10窗口"


def format_holding_window_text(min_days, max_days):
    min_days = int(_safe_float(min_days, STRATEGY_HOLDING_DAYS_MIN) or STRATEGY_HOLDING_DAYS_MIN)
    max_days = int(_safe_float(max_days, STRATEGY_HOLDING_DAYS_MAX) or STRATEGY_HOLDING_DAYS_MAX)
    if min_days >= max_days:
        return f"{max_days}天内"
    return f"{min_days}-{max_days}天"


def build_candidate_exit_rules(candidate=None, stop_plan=None):
    candidate = candidate or {}
    follow_state = resolve_candidate_follow_state(candidate)
    setup_id = resolve_candidate_setup_id(candidate)
    contract = get_setup_execution_contract(setup_id, follow_state)

    effective_stop = None
    if stop_plan:
        effective_stop = _round_or_none(stop_plan.get("effective_stop"))
    if effective_stop is None:
        effective_stop = _round_or_none(candidate.get("stop_loss"))

    defensive_rule = DEFENSIVE_EXIT_RULE_TEXT
    if effective_stop is not None:
        defensive_rule = (
            f"错了就跑：这笔交易如果还对，就不该失守{effective_stop:.2f}；"
            f"失效价失守立即卖，最晚不超过单笔-5%"
        )

    return {
        "holding_days_min": contract.get("holding_days_min", STRATEGY_HOLDING_DAYS_MIN),
        "holding_days_max": contract.get("holding_days_max", STRATEGY_HOLDING_DAYS_MAX),
        "profit_take_pct": contract.get("profit_take_pct", 0.05),
        "defensive_exit_rule": defensive_rule,
        "profit_exit_rule": contract.get("profit_exit_rule", PROFIT_EXIT_RULE_TEXT),
    }
