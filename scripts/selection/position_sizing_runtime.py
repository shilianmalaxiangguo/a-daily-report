from __future__ import annotations

from report.strategy_tracking_support import build_candidate_feedback_clock as _default_build_candidate_feedback_clock
from selection.candidate_execution_contracts import (
    build_weak_to_strong_context as _default_build_weak_to_strong_context,
    is_bridge_priority_setup as _default_is_bridge_priority_setup,
)
from selection.gem_breathing_runtime import classify_20cm_branch as _default_classify_20cm_branch
from selection.monthly_rhythm_runtime import build_monthly_rhythm_decision as _default_build_monthly_rhythm_decision

__all__ = [
    "build_position_sizing_decision",
    "with_single_focus_counts",
]

_MISSING = object()


def _install_runtime_bindings(bindings):
    previous = {}
    module_globals = globals()
    for key, value in (bindings or {}).items():
        if key.startswith("__") and key.endswith("__"):
            continue
        previous[key] = module_globals.get(key, _MISSING)
        module_globals[key] = value
    return previous


def _restore_runtime_bindings(previous):
    module_globals = globals()
    for key, value in (previous or {}).items():
        if value is _MISSING:
            module_globals.pop(key, None)
        else:
            module_globals[key] = value


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


def _candidate_identity(candidate):
    if not isinstance(candidate, dict):
        return None
    code = str(candidate.get("code") or candidate.get("股票代码") or candidate.get("证券代码") or "").strip()
    name = str(candidate.get("name") or candidate.get("名称") or candidate.get("stock_name") or "").strip()
    sector = str(
        candidate.get("sector")
        or candidate.get("sector_name")
        or candidate.get("所属板块")
        or candidate.get("板块")
        or ""
    ).strip()
    direction = str(
        candidate.get("direction")
        or candidate.get("theme")
        or candidate.get("line")
        or candidate.get("所属方向")
        or candidate.get("方向")
        or ""
    ).strip()
    if code:
        return ("code", code)
    if name:
        return ("name", name)
    if not any((sector, direction)):
        return None
    return (code, name, sector, direction)


def with_single_focus_counts(final_gate=None, focus_group=None, keep_group=None):
    enriched_gate = dict(final_gate or {})
    candidates = [item for item in list(focus_group or []) + list(keep_group or []) if item]
    if candidates and "candidate_count" not in enriched_gate:
        enriched_gate["candidate_count"] = len(candidates)
    if candidates and "unique_target_count" not in enriched_gate:
        identities = {_candidate_identity(candidate) for candidate in candidates}
        identities.discard(None)
        enriched_gate["unique_target_count"] = len(identities) if identities else len(candidates)
    return enriched_gate


def _coerce_optional_count(value):
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _read_single_focus_count(final_gate=None, state_machine_snapshot=None):
    final_gate = final_gate or {}
    state_machine_snapshot = state_machine_snapshot or {}
    for source, key in (
        (final_gate, "unique_target_count"),
        (final_gate, "candidate_count"),
        (state_machine_snapshot, "unique_target_count"),
        (state_machine_snapshot, "candidate_count"),
    ):
        count = _coerce_optional_count(source.get(key))
        if count is not None:
            return count
    return None


def _build_single_focus_constraint(final_gate=None, state_machine_snapshot=None, best_stock=None, candidate=None, watch_anchor_type=""):
    focus_count = _read_single_focus_count(
        final_gate=final_gate,
        state_machine_snapshot=state_machine_snapshot,
    )
    if focus_count is not None and focus_count > 1:
        return {
            "status": "multiple_candidates",
            "reason": "多候选未缩到唯一对象，只能在50%标准进攻和0%等待之间二选一。",
        }
    if not best_stock:
        if candidate and _is_explicit_extreme_conviction_target(candidate, watch_anchor_type=watch_anchor_type):
            return {
                "status": "clear",
                "reason": "已缩到明日极度看好目标，等待固定交易窗口内条件成立。",
            }
        return {
            "status": "missing_target",
            "reason": "缺少唯一执行对象，当前只能保持观察。",
        }
    return {
        "status": "clear",
        "reason": "已缩到唯一执行对象，可以按仓位门槛继续评估。",
    }


def _build_candidate_feedback_clock(candidate=None, watch_anchor_type="", state_machine_snapshot=None, mainline_name="", target_date=""):
    return _default_build_candidate_feedback_clock(
        candidate=candidate,
        watch_anchor_type=watch_anchor_type,
        state_machine_snapshot=state_machine_snapshot,
        mainline_name=mainline_name,
        target_date=target_date,
    )


def _classify_20cm_branch(candidate=None, mainline_name="", confirm_price=None, support_price=None, feedback_ready=False, allow_attack_50_ready=False, target_date="", mainline_anchor=None):
    return _default_classify_20cm_branch(
        candidate=candidate,
        mainline_name=mainline_name,
        confirm_price=confirm_price,
        support_price=support_price,
        feedback_ready=feedback_ready,
        allow_attack_50_ready=allow_attack_50_ready,
        target_date=target_date,
        mainline_anchor=mainline_anchor,
    )


def _build_weak_to_strong_context(candidate=None, mainline_name="", state_machine_snapshot=None):
    return _default_build_weak_to_strong_context(
        candidate,
        mainline_name=mainline_name,
        state_machine_snapshot=state_machine_snapshot,
    )


def _is_bridge_priority_setup(candidate, mainline_name=""):
    return _default_is_bridge_priority_setup(candidate, mainline_name=mainline_name)


def _build_monthly_rhythm_decision(target_date="", monthly_context=None, state_machine_snapshot=None, final_gate=None):
    return _default_build_monthly_rhythm_decision(
        target_date=target_date,
        monthly_context=monthly_context,
        state_machine_snapshot=state_machine_snapshot,
        final_gate=final_gate,
    )


def _candidate_allows_full_a_grade(candidate):
    candidate = candidate or {}
    decision_stack = candidate.get("decision_stack") or {}
    return bool(
        candidate.get("a_grade_candidate")
        or candidate.get("allow_full_attack")
        or str(candidate.get("signal_grade", "")).strip().upper() == "A"
        or decision_stack.get("a_grade_candidate")
        or decision_stack.get("allow_full_attack")
        or str(decision_stack.get("signal_grade", "")).strip().upper() == "A"
    )


def _has_clear_invalidation(candidate, support_price):
    candidate = candidate or {}
    if support_price is not None:
        return True
    stop_plan = candidate.get("stop_plan") or {}
    keys = (
        "failure_line",
        "stop_price",
        "stop_loss_price",
        "invalidation_price",
        "support_price",
    )
    return any(candidate.get(key) not in (None, "") or stop_plan.get(key) not in (None, "") for key in keys)


def _truthy_field(candidate, *keys):
    candidate = candidate or {}
    decision_stack = candidate.get("decision_stack") or {}
    for key in keys:
        value = candidate.get(key, _MISSING)
        if value is _MISSING:
            value = decision_stack.get(key, _MISSING)
        if value is _MISSING:
            continue
        if isinstance(value, bool):
            if value:
                return True
            continue
        text = str(value or "").strip()
        if text and text not in ("0", "False", "false", "否", "无", "-"):
            return True
    return False


def _has_explicit_participation_window(candidate):
    return _truthy_field(
        candidate,
        "participation_window",
        "entry_window",
        "execution_window",
        "conviction_window",
        "auction_script",
        "first_minutes_script",
        "board_script",
        "reseal_script",
        "missed_action",
    )


def _has_active_trend_chain(candidate, mainline_name=""):
    candidate = candidate or {}
    if _truthy_field(candidate, "trend_chain_active", "relative_price_chain_active", "mainline_chain_active"):
        return True
    chain = str(candidate.get("trend_chain") or candidate.get("relative_price_chain") or "").strip()
    if chain:
        return True
    sector = str(candidate.get("sector") or candidate.get("sector_name") or "").strip()
    return bool(mainline_name and sector and (sector in mainline_name or mainline_name in sector))


def _has_explicit_trend_chain(candidate):
    candidate = candidate or {}
    if _truthy_field(candidate, "trend_chain_active", "relative_price_chain_active", "mainline_chain_active"):
        return True
    return bool(str(candidate.get("trend_chain") or candidate.get("relative_price_chain") or "").strip())


def _has_acceptance_act_right(candidate, feedback_clock=None):
    if _truthy_field(candidate, "acceptance_act_right", "acceptance_ready", "stock_acceptance", "act_right"):
        return True
    candidate = candidate or {}
    for key in ("acceptance_state", "abnormal_follow_state", "abnormal_summary"):
        text = str(candidate.get(key) or "").strip()
        if any(marker in text for marker in ("跌不下去", "承接", "缩量消化", "回封", "强")):
            return True
    feedback_clock = feedback_clock or {}
    return bool(feedback_clock.get("ready") and _safe_float(feedback_clock.get("score", 0), 0) >= 90)


def _has_explicit_acceptance_act_right(candidate):
    return _truthy_field(candidate, "acceptance_act_right", "acceptance_ready", "stock_acceptance", "act_right")


def _build_full_attack_check(
    *,
    candidate=None,
    best_stock=None,
    monthly_rhythm=None,
    feedback_clock=None,
    support_price=None,
    branch_20cm=None,
    mainline_name="",
):
    candidate = candidate or {}
    monthly_rhythm = monthly_rhythm or {}
    feedback_clock = feedback_clock or {}
    branch_20cm = branch_20cm or {}
    missing = []
    if not best_stock:
        missing.append("唯一对象")
    if not monthly_rhythm.get("allow_full_attack") or int(_safe_float(monthly_rhythm.get("max_position_pct", 0), 0)) < 80:
        missing.append("非冰点进攻环境")
    if not _candidate_allows_full_a_grade(candidate):
        missing.append("核心强度")
    if not _has_explicit_trend_chain(candidate):
        missing.append("趋势比价链")
    if not _has_explicit_participation_window(candidate):
        missing.append("固定交易窗口条件")
    if not _has_explicit_acceptance_act_right(candidate):
        missing.append("承接继续正确")
    if not _has_clear_invalidation(candidate, support_price):
        missing.append("失效价")
    if branch_20cm.get("is_20cm"):
        missing.append("10cm核心适配")
    return {
        "status": "ready" if not missing else "incomplete",
        "missing": missing,
        "required": ["唯一对象", "趋势比价链", "固定交易窗口条件", "承接继续正确", "失效价", "非冰点进攻环境"],
    }


def _grade_for_position(position_pct):
    position_pct = int(_safe_float(position_pct, 0))
    if position_pct >= 100:
        return "100"
    if position_pct >= 50:
        return "50"
    return "0"


def _full_a_position_pct(candidate):
    _ = candidate or {}
    return 100


def _is_explicit_extreme_conviction_target(candidate=None, watch_anchor_type=""):
    candidate = candidate or {}
    text = " ".join(
        str(value or "")
        for value in [
            watch_anchor_type,
            candidate.get("source_tier"),
            candidate.get("source_section"),
            candidate.get("watch_anchor_type"),
            candidate.get("identity"),
        ]
    )
    return "极度看好" in text or "extreme_conviction" in text


def _explicit_market_ice_point(monthly_context=None, state_machine_snapshot=None, final_gate=None):
    monthly_context = monthly_context or {}
    state_machine_snapshot = state_machine_snapshot or {}
    final_gate = final_gate or {}
    return any(
        source.get("market_ice_point") is True
        for source in (monthly_context, state_machine_snapshot, final_gate)
        if isinstance(source, dict)
    )


def _apply_monthly_rhythm_to_decision(
    decision,
    *,
    monthly_rhythm,
    candidate=None,
    best_stock=None,
    watch_anchor_type="",
    mainline_name="",
    feedback_clock=None,
    support_price=None,
    branch_20cm=None,
):
    decision = dict(decision or {})
    monthly_rhythm = dict(monthly_rhythm or {})
    feedback_clock = dict(feedback_clock or {})
    branch_20cm = dict(branch_20cm or {})
    max_position_pct = int(_safe_float(monthly_rhythm.get("max_position_pct", 100), 100))
    target_position_pct = int(_safe_float(decision.get("target_position_pct", 0), 0))
    base_reason = str(decision.get("sizing_reason", "") or "").strip()
    full_attack_check = _build_full_attack_check(
        candidate=candidate,
        best_stock=best_stock,
        monthly_rhythm=monthly_rhythm,
        feedback_clock=feedback_clock,
        support_price=support_price,
        branch_20cm=branch_20cm,
        mainline_name=mainline_name,
    )

    full_attack_ready = bool(
        target_position_pct >= 50
        and full_attack_check.get("status") == "ready"
    )
    if full_attack_ready and max_position_pct >= 80:
        full_position_pct = min(_full_a_position_pct(candidate), max_position_pct)
        decision.update(
            {
                "participation_mode": f"full_{full_position_pct}",
                "target_position_pct": full_position_pct,
                "signal_grade": "100",
                "monthly_rhythm": monthly_rhythm,
                "full_attack_ready": True,
                "full_attack_check": full_attack_check,
                "sizing_reason": "100%核心进攻条件成立：月度允许进攻、唯一对象确认、失效价清楚；盈利不是降档理由。",
            }
        )
        return decision

    if target_position_pct > max_position_pct:
        if max_position_pct <= 0:
            capped_mode = "observe_0"
            capped_position = 0
        else:
            capped_mode = "execute_50"
            capped_position = 50
        cap_reason = monthly_rhythm.get("reason") or "月度节奏限制仓位。"
        decision.update(
            {
                "participation_mode": capped_mode,
                "target_position_pct": capped_position,
                "sizing_reason": f"{base_reason} 月度节奏降档：{cap_reason}".strip(),
            }
        )

    decision["monthly_rhythm"] = monthly_rhythm
    decision["signal_grade"] = _grade_for_position(decision.get("target_position_pct", 0))
    decision["full_attack_ready"] = False
    decision["full_attack_check"] = full_attack_check
    return decision


def build_position_sizing_decision(
    final_gate=None,
    state_machine_snapshot=None,
    best_stock=None,
    watch_anchor=None,
    watch_anchor_type="",
    mainline_name="",
    target_date="",
    special_probe_verdict=None,
    mainline_anchor=None,
    monthly_context=None,
    *,
    helpers=None,
):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _build_position_sizing_decision_legacy_body(
            final_gate=final_gate,
            state_machine_snapshot=state_machine_snapshot,
            best_stock=best_stock,
            watch_anchor=watch_anchor,
            watch_anchor_type=watch_anchor_type,
            mainline_name=mainline_name,
            target_date=target_date,
            special_probe_verdict=special_probe_verdict,
            mainline_anchor=mainline_anchor,
            monthly_context=monthly_context,
        )
    finally:
        _restore_runtime_bindings(previous)


def _build_position_sizing_decision_legacy_body(
    final_gate=None,
    state_machine_snapshot=None,
    best_stock=None,
    watch_anchor=None,
    watch_anchor_type="",
    mainline_name="",
    target_date="",
    special_probe_verdict=None,
    mainline_anchor=None,
    monthly_context=None,
):
    final_gate = final_gate or {}
    state_machine_snapshot = state_machine_snapshot or {}
    special_probe_verdict = special_probe_verdict or {}
    monthly_context = monthly_context or {}
    mainline_name = str(mainline_name or state_machine_snapshot.get("leading_line", "") or "").strip()
    execution_bias = str(state_machine_snapshot.get("execution_bias", "") or "").strip()
    candidate = best_stock or watch_anchor or {}
    feedback_clock = _build_candidate_feedback_clock(
        candidate=candidate,
        watch_anchor_type=watch_anchor_type,
        state_machine_snapshot=state_machine_snapshot,
        mainline_name=mainline_name,
        target_date=target_date,
    )
    confirm_price = feedback_clock.get("confirm_price")
    support_price = feedback_clock.get("support_price")
    if confirm_price is not None and support_price is not None:
        trigger_text = f"09:50-10:10站上{confirm_price:.2f}且不破{support_price:.2f}"
    elif confirm_price is not None:
        trigger_text = f"09:50-10:10站上{confirm_price:.2f}"
    else:
        trigger_text = "09:50-10:10窗口满足条件"

    probe_state = str(special_probe_verdict.get("probe_state", "") or "").strip()
    probe_code = str(special_probe_verdict.get("code", "") or "").strip()
    probe_allows_attack_50_ready = bool(special_probe_verdict.get("allows_attack_50_ready"))
    probe_allows_execute_50 = bool(special_probe_verdict.get("allows_execute_50"))
    pre_allow_attack_50_ready = bool(final_gate.get("allow_attack_50_ready")) or bool(final_gate.get("can_new_entry")) or probe_allows_attack_50_ready
    branch_20cm = _classify_20cm_branch(
        candidate=candidate,
        mainline_name=mainline_name,
        confirm_price=confirm_price,
        support_price=support_price,
        feedback_ready=bool(feedback_clock.get("ready")),
        allow_attack_50_ready=pre_allow_attack_50_ready,
        target_date=target_date,
        mainline_anchor=mainline_anchor,
    )
    weak_to_strong_context = _build_weak_to_strong_context(
        candidate=candidate,
        mainline_name=mainline_name,
        state_machine_snapshot=state_machine_snapshot,
    )
    weak_to_strong_upgrade_ready = bool(
        candidate
        and weak_to_strong_context.get("active")
        and feedback_clock.get("ready")
        and feedback_clock.get("has_confirmation_chain")
        and not branch_20cm.get("is_20cm")
    )
    single_focus_constraint = _build_single_focus_constraint(
        final_gate=final_gate,
        state_machine_snapshot=state_machine_snapshot,
        best_stock=best_stock,
        candidate=candidate,
        watch_anchor_type=watch_anchor_type,
    )
    monthly_rhythm = _build_monthly_rhythm_decision(
        target_date=target_date,
        monthly_context=monthly_context,
        state_machine_snapshot=state_machine_snapshot,
        final_gate=final_gate,
    )

    decision = {
        "participation_mode": "observe_0",
        "target_position_pct": 0,
        "candidate_feedback_ready": bool(feedback_clock.get("ready")),
        "candidate_feedback_score": feedback_clock.get("score", 0),
        "candidate_feedback_reasons": list(feedback_clock.get("reasons", []) or []),
        "history_feedback": dict(feedback_clock.get("history_feedback", {}) or {}),
        "active_watch": bool(feedback_clock.get("active_watch")),
        "second_shot_ready": bool(feedback_clock.get("second_shot_ready")),
        "second_shot_breakout_price": _round_or_none(feedback_clock.get("second_shot_breakout_price")),
        "trigger_text": trigger_text,
        "sizing_reason": "当前只保留观察权。",
        "special_probe_state": probe_state,
        "special_probe_allows_attack_50_ready": probe_allows_attack_50_ready,
        "support_price": support_price,
        "branch_20cm": branch_20cm,
        "weak_to_strong_context": dict(weak_to_strong_context or {}),
        "weak_to_strong_upgrade_ready": weak_to_strong_upgrade_ready,
        "single_focus_constraint": single_focus_constraint,
        "monthly_rhythm": monthly_rhythm,
        "signal_grade": "0",
        "full_attack_ready": False,
    }

    def _finalize(decision_payload):
        return _apply_monthly_rhythm_to_decision(
            decision_payload,
            monthly_rhythm=monthly_rhythm,
            candidate=candidate,
            best_stock=best_stock,
            watch_anchor_type=watch_anchor_type,
            mainline_name=mainline_name,
            feedback_clock=feedback_clock,
            support_price=support_price,
            branch_20cm=branch_20cm,
        )

    if branch_20cm.get("direct_ban"):
        decision["sizing_reason"] = branch_20cm.get("reason") or "20cm 高波动样本当前禁做。"
        return _finalize(decision)

    if probe_state == "probe_deep_fall":
        decision["sizing_reason"] = "特殊探针已经深跌失效，继续维持0%观察。"
        return _finalize(decision)
    if (
        probe_state == "probe_flow_unconfirmed"
        and special_probe_verdict
        and not _is_explicit_extreme_conviction_target(candidate, watch_anchor_type=watch_anchor_type)
    ):
        decision["sizing_reason"] = "特殊探针只到承接/观察阶段，外溢确认不足，继续维持0%。"
        return _finalize(decision)

    if execution_bias == "allow_execute" and final_gate.get("can_new_entry") and not best_stock:
        decision["sizing_reason"] = single_focus_constraint.get("reason") or "缺少唯一执行对象，当前只能保持观察。"
        return _finalize(decision)

    if execution_bias == "allow_execute" and best_stock and final_gate.get("can_new_entry") and (not special_probe_verdict or probe_allows_execute_50 or not probe_state):
        if branch_20cm.get("is_20cm"):
            if branch_20cm.get("allow_attack_50_ready"):
                decision.update(
                    {
                        "participation_mode": "execute_50",
                        "target_position_pct": 50,
                        "sizing_reason": branch_20cm.get("reason") or "20cm 若能满足主线、确认链和风险边界，按50%标准进攻；不满足就是0%。",
                    }
                )
            else:
                decision["sizing_reason"] = branch_20cm.get("reason") or "20cm 当前只保留观察权，不直接给50%。"
            return _finalize(decision)
        if single_focus_constraint.get("status") == "multiple_candidates":
            if pre_allow_attack_50_ready and feedback_clock.get("ready"):
                decision.update(
                    {
                        "participation_mode": "execute_50",
                        "target_position_pct": 50,
                        "sizing_reason": "多候选未缩到唯一对象，但反馈成熟时只能在最强对象上按50%标准进攻；不满足就是0%。",
                    }
                )
            else:
                decision["sizing_reason"] = "多候选未缩到唯一对象，反馈未成熟则维持0%。"
            return _finalize(decision)
        if single_focus_constraint.get("status") != "clear":
            decision["sizing_reason"] = single_focus_constraint.get("reason") or "当前只保留观察权。"
            return _finalize(decision)
        decision.update(
            {
                "participation_mode": "execute_50",
                "target_position_pct": 50,
                "sizing_reason": "环境、主线和唯一对象已经同时对齐，只做50%正常执行仓。",
            }
        )
        return _finalize(decision)

    allow_attack_50_ready = bool(final_gate.get("allow_attack_50_ready")) or bool(final_gate.get("can_new_entry")) or probe_allows_attack_50_ready
    history_continuity_ready = feedback_clock.get("history_feedback", {}).get("continuous_days", 0) >= 2
    second_shot_ready = bool(feedback_clock.get("second_shot_ready"))
    second_shot_breakout_price = _round_or_none(feedback_clock.get("second_shot_breakout_price"))
    bridge_priority_candidate = _is_bridge_priority_setup(candidate, mainline_name=mainline_name)
    bridge_prep_observe_only = execution_bias == "prep_only" and bridge_priority_candidate
    conditional_probe_ok = (
        (not special_probe_verdict)
        or probe_allows_attack_50_ready
        or not probe_state
        or probe_code in ("fallback_probe_watch", "mainline_probe_watch", "validation_probe_watch", "no_probe")
    )

    def _standard_attack_reason():
        if second_shot_ready and second_shot_breakout_price is not None:
            return f"执行候选观察锚点仍在活观察窗口内，且已完成{second_shot_breakout_price:.2f}二次突破，按50%标准进攻预演。"
        if weak_to_strong_upgrade_ready:
            return "主线弱转强样本已具备09:50-10:10验证链：强基底假弱非真弱，按50%标准进攻；后续继续 act right 再评估是否升级为核心进攻。"
        if probe_state == "probe_crossline_upgrade_ready":
            return "跨线对象已先 act right，按50%标准进攻，但不直接当成核心进攻。"
        if probe_allows_attack_50_ready:
            return "环境条件尚未完全满足，但候选已具备可升级探针反馈，按50%标准进攻预演。"
        if execution_bias in ("prep_only", "divergence_only"):
            return "环境未完全共振，但最强对象已经先证明自己，按50%标准进攻预演。"
        return "环境条件尚未完全满足，但候选已连续多日报告并保持承接，按50%标准进攻预演。"

    if (
        execution_bias in ("prep_only", "divergence_only")
        and candidate
        and allow_attack_50_ready
        and feedback_clock.get("ready")
        and conditional_probe_ok
        and not bridge_prep_observe_only
    ):
        decision.update(
            {
                "participation_mode": "execute_50",
                "target_position_pct": 50,
                "sizing_reason": _standard_attack_reason(),
            }
        )
        return _finalize(decision)
    reduce_only_candidate_preview_ready = bool(
        execution_bias == "reduce_only"
        and candidate
        and allow_attack_50_ready
        and _is_explicit_extreme_conviction_target(candidate, watch_anchor_type=watch_anchor_type)
        and _has_explicit_participation_window(candidate)
        and _has_clear_invalidation(candidate, support_price)
        and not _explicit_market_ice_point(monthly_context, state_machine_snapshot, final_gate)
        and not branch_20cm.get("observe_only")
    )
    if reduce_only_candidate_preview_ready:
        monthly_rhythm.update(
            {
                "month_mode": "attack_prepare",
                "target_role": "attack_prepare",
                "max_position_pct": max(int(_safe_float(monthly_rhythm.get("max_position_pct", 0), 0)), 50),
                "allow_full_attack": False,
                "trend_invalid": False,
                "reason": "已有明确对象、固定交易窗口和失效价；环境要求先收缩时也保留50%标准进攻，条件不成立回0%。",
            }
        )
        decision.update(
            {
                "participation_mode": "attack_50_preview",
                "target_position_pct": 50,
                "sizing_reason": "已有明确对象、固定交易窗口和失效价；环境要求先收缩时也保留50%标准进攻，条件不成立回0%。",
            }
        )
        return _finalize(decision)
    if execution_bias == "watch_only" and candidate and allow_attack_50_ready and feedback_clock.get("ready") and (history_continuity_ready or probe_allows_attack_50_ready or second_shot_ready or weak_to_strong_upgrade_ready) and conditional_probe_ok:
        decision.update(
            {
                "participation_mode": "execute_50",
                "target_position_pct": 50,
                "sizing_reason": _standard_attack_reason(),
            }
        )
        return _finalize(decision)

    if (
        candidate
        and _is_explicit_extreme_conviction_target(candidate, watch_anchor_type=watch_anchor_type)
        and not _explicit_market_ice_point(monthly_context, state_machine_snapshot, final_gate)
        and feedback_clock.get("ready")
        and not branch_20cm.get("observe_only")
    ):
        monthly_rhythm.update(
            {
                "month_mode": "attack_prepare",
                "target_role": "attack_prepare",
                "max_position_pct": max(int(_safe_float(monthly_rhythm.get("max_position_pct", 0), 0)), 50),
                "allow_full_attack": False,
                "trend_invalid": False,
                "reason": "市场不是极端冰点且已有明日极度看好目标，保留50%标准进攻预演；失败回到0%。",
            }
        )
        decision.update(
            {
                "participation_mode": "attack_50_preview",
                "target_position_pct": 50,
                "sizing_reason": "明日极度看好目标标的已存在，市场未到极端冰点；盘前不抢跑，但保留50%标准进攻预演，固定交易窗口内条件不成立就回到0%。",
            }
        )
        return _finalize(decision)

    attack_prepare_candidate_ready = bool(
        candidate
        and execution_bias in ("watch_only", "prep_only", "divergence_only", "")
        and int(_safe_float(monthly_rhythm.get("max_position_pct", 0), 0)) >= 50
        and not _explicit_market_ice_point(monthly_context, state_machine_snapshot, final_gate)
        and not branch_20cm.get("is_20cm")
        and not branch_20cm.get("observe_only")
        and _has_explicit_participation_window(candidate)
        and _has_clear_invalidation(candidate, support_price)
        and conditional_probe_ok
        and not bridge_prep_observe_only
    )
    if attack_prepare_candidate_ready:
        decision.update(
            {
                "participation_mode": "attack_50_preview",
                "target_position_pct": 50,
                "sizing_reason": "已有明确候选、固定交易窗口和失效价，市场未到弱市场/冰点/趋势失效；按50%标准进攻预演，不再默认0%观察。",
            }
        )
        return _finalize(decision)

    if execution_bias == "avoid":
        decision["sizing_reason"] = "主线脉冲已退潮，维持0%观察。"
    elif execution_bias == "reduce_only":
        decision["sizing_reason"] = "当前只处理旧仓，不给新增仓位。"
    elif execution_bias == "watch_only":
        if branch_20cm.get("observe_only"):
            decision["sizing_reason"] = branch_20cm.get("reason") or "创业板20cm 当前只保留观察权。"
        elif special_probe_verdict and not conditional_probe_ok:
            decision["sizing_reason"] = "特殊探针反馈还没走到可升级阶段，当前只有观察权，没有执行仓位。"
        else:
            decision["sizing_reason"] = "当前只有观察权，没有执行仓位。"
    elif execution_bias == "prep_only":
        if bridge_prep_observe_only:
            decision["sizing_reason"] = "当前只保留条件执行预备态，仍需次日继续观察与09:50-10:10窗口，不直接升级50%。"
        else:
            decision["sizing_reason"] = "虽有条件执行预备态，但反馈时钟未成熟，维持0%。"
    return _finalize(decision)
