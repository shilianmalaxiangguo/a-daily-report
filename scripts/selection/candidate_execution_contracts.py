from __future__ import annotations

import daily_report_analysis_utils as analysis_utils

DEFENSIVE_EXIT_RULE_TEXT = "错了就跑：30分钟结构失守立即卖，最晚不超过单笔-5%"
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
    "build_gem_textbook_front_text",
    "build_gem_textbook_next_step_text",
    "build_gem_textbook_reference_text",
    "build_philosophy_constraint_text",
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
    trigger_text = str(position_decision.get("trigger_text", "") or "完成60分钟确认").strip()
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

    if target_position_pct == 30:
        next_step = f"当前已进入30%条件试错候选，{trigger_text}后才允许试错"
    elif label == "A级教材":
        next_step = f"当前还差右侧确认和60分钟确认，确认后才评估30%条件试错" if not ready else f"反馈已接近到位，{trigger_text}后可评估30%条件试错"
    elif label == "B级教材":
        next_step = "先保留观察合同，等它走成右侧确认后再考虑升级"
    elif label == "C级观察样本":
        next_step = "不提前升级，只跟踪它会不会再次复现并走成右侧确认"
    else:
        next_step = "先保留观察合同，不直接给执行权"

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
            f"30分钟结构失守立即卖，最晚不超过单笔-5%"
        )

    return {
        "holding_days_min": contract.get("holding_days_min", STRATEGY_HOLDING_DAYS_MIN),
        "holding_days_max": contract.get("holding_days_max", STRATEGY_HOLDING_DAYS_MAX),
        "profit_take_pct": contract.get("profit_take_pct", 0.05),
        "defensive_exit_rule": defensive_rule,
        "profit_exit_rule": contract.get("profit_exit_rule", PROFIT_EXIT_RULE_TEXT),
    }
