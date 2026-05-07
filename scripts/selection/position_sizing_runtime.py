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


def _build_single_focus_constraint(final_gate=None, state_machine_snapshot=None, best_stock=None):
    focus_count = _read_single_focus_count(
        final_gate=final_gate,
        state_machine_snapshot=state_machine_snapshot,
    )
    if focus_count is not None and focus_count > 1:
        return {
            "status": "multiple_candidates",
            "reason": "多候选未缩到唯一对象，只允许30%条件试错/观察。",
        }
    if not best_stock:
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


def _classify_20cm_branch(candidate=None, mainline_name="", confirm_price=None, support_price=None, feedback_ready=False, allow_conditional_30=False, target_date="", mainline_anchor=None):
    return _default_classify_20cm_branch(
        candidate=candidate,
        mainline_name=mainline_name,
        confirm_price=confirm_price,
        support_price=support_price,
        feedback_ready=feedback_ready,
        allow_conditional_30=allow_conditional_30,
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


def _grade_for_position(position_pct):
    position_pct = int(_safe_float(position_pct, 0))
    if position_pct >= 80:
        return "A"
    if position_pct >= 50:
        return "A-"
    if position_pct >= 30:
        return "B"
    return "C"


def _full_a_position_pct(candidate):
    candidate = candidate or {}
    raw_value = (
        candidate.get("a_grade_position_pct")
        or candidate.get("full_attack_position_pct")
        or (candidate.get("decision_stack") or {}).get("a_grade_position_pct")
        or 100
    )
    position_pct = int(_safe_float(raw_value, 100))
    return max(80, min(100, position_pct))


def _apply_monthly_rhythm_to_decision(
    decision,
    *,
    monthly_rhythm,
    candidate=None,
    best_stock=None,
    watch_anchor_type="",
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

    full_attack_ready = bool(
        target_position_pct >= 50
        and monthly_rhythm.get("allow_full_attack")
        and best_stock
        and _candidate_allows_full_a_grade(candidate)
        and feedback_clock.get("ready")
        and _has_clear_invalidation(candidate, support_price)
        and not branch_20cm.get("is_20cm")
    )
    if full_attack_ready and max_position_pct >= 80:
        full_position_pct = min(_full_a_position_pct(candidate), max_position_pct)
        decision.update(
            {
                "participation_mode": f"a_grade_{full_position_pct}",
                "target_position_pct": full_position_pct,
                "signal_grade": "A",
                "monthly_rhythm": monthly_rhythm,
                "full_attack_ready": True,
                "sizing_reason": "A级满仓/重仓资格成立：月度允许进攻、唯一对象确认、失效价清楚；盈利不是降档理由。",
            }
        )
        return decision

    if target_position_pct > max_position_pct:
        if max_position_pct <= 0:
            capped_mode = "observe_0"
            capped_position = 0
        elif max_position_pct <= 30:
            capped_mode = "conditional_30"
            capped_position = 30
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
        trigger_text = f"首个60分钟站上{confirm_price:.2f}且不破{support_price:.2f}"
    elif confirm_price is not None:
        trigger_text = f"首个60分钟站上{confirm_price:.2f}"
    else:
        trigger_text = "完成60分钟确认"

    probe_state = str(special_probe_verdict.get("probe_state", "") or "").strip()
    probe_code = str(special_probe_verdict.get("code", "") or "").strip()
    probe_allows_conditional_30 = bool(special_probe_verdict.get("allows_conditional_30"))
    probe_allows_execute_50 = bool(special_probe_verdict.get("allows_execute_50"))
    pre_allow_conditional_30 = bool(final_gate.get("allow_conditional_30")) or bool(final_gate.get("can_new_entry")) or probe_allows_conditional_30
    branch_20cm = _classify_20cm_branch(
        candidate=candidate,
        mainline_name=mainline_name,
        confirm_price=confirm_price,
        support_price=support_price,
        feedback_ready=bool(feedback_clock.get("ready")),
        allow_conditional_30=pre_allow_conditional_30,
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
        "special_probe_allows_conditional_30": probe_allows_conditional_30,
        "support_price": support_price,
        "branch_20cm": branch_20cm,
        "weak_to_strong_context": dict(weak_to_strong_context or {}),
        "weak_to_strong_upgrade_ready": weak_to_strong_upgrade_ready,
        "single_focus_constraint": single_focus_constraint,
        "monthly_rhythm": monthly_rhythm,
        "signal_grade": "C",
        "full_attack_ready": False,
    }

    def _finalize(decision_payload):
        return _apply_monthly_rhythm_to_decision(
            decision_payload,
            monthly_rhythm=monthly_rhythm,
            candidate=candidate,
            best_stock=best_stock,
            watch_anchor_type=watch_anchor_type,
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
    if probe_state == "probe_flow_unconfirmed" and special_probe_verdict:
        decision["sizing_reason"] = "特殊探针只到承接/观察阶段，外溢确认不足，继续维持0%。"
        return _finalize(decision)

    if execution_bias == "allow_execute" and final_gate.get("can_new_entry") and not best_stock:
        decision["sizing_reason"] = single_focus_constraint.get("reason") or "缺少唯一执行对象，当前只能保持观察。"
        return _finalize(decision)

    if execution_bias == "allow_execute" and best_stock and final_gate.get("can_new_entry") and (not special_probe_verdict or probe_allows_execute_50 or not probe_state):
        if branch_20cm.get("is_20cm"):
            if branch_20cm.get("allow_conditional_30"):
                decision.update(
                    {
                        "participation_mode": "conditional_30",
                        "target_position_pct": 30,
                        "sizing_reason": branch_20cm.get("reason") or "20cm 只允许30%条件试错，不直接给50%。",
                    }
                )
            else:
                decision["sizing_reason"] = branch_20cm.get("reason") or "20cm 当前只保留观察权，不直接给50%。"
            return _finalize(decision)
        if single_focus_constraint.get("status") == "multiple_candidates":
            if pre_allow_conditional_30 and feedback_clock.get("ready"):
                decision.update(
                    {
                        "participation_mode": "conditional_30",
                        "target_position_pct": 30,
                        "sizing_reason": "多候选未缩到唯一对象，只允许30%条件试错/观察。",
                    }
                )
            else:
                decision["sizing_reason"] = "多候选未缩到唯一对象，只允许30%条件试错/观察，当前反馈未成熟，维持0%。"
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

    allow_conditional_30 = bool(final_gate.get("allow_conditional_30")) or bool(final_gate.get("can_new_entry")) or probe_allows_conditional_30
    history_continuity_ready = feedback_clock.get("history_feedback", {}).get("continuous_days", 0) >= 2
    second_shot_ready = bool(feedback_clock.get("second_shot_ready"))
    second_shot_breakout_price = _round_or_none(feedback_clock.get("second_shot_breakout_price"))
    bridge_priority_candidate = _is_bridge_priority_setup(candidate, mainline_name=mainline_name)
    bridge_prep_observe_only = execution_bias == "prep_only" and bridge_priority_candidate
    conditional_probe_ok = (
        (not special_probe_verdict)
        or probe_allows_conditional_30
        or not probe_state
        or probe_code in ("fallback_probe_watch", "mainline_probe_watch", "validation_probe_watch", "no_probe")
    )

    def _conditional_30_reason():
        if second_shot_ready and second_shot_breakout_price is not None:
            return f"执行候选观察锚点仍在活观察窗口内，且已完成{second_shot_breakout_price:.2f}二次突破，只允许30%条件试错仓。"
        if weak_to_strong_upgrade_ready:
            return "主线弱转强样本已具备60分钟确认链：强基底假弱非真弱，只允许30%条件试错仓；后续继续 act right 再评估是否升级到唯一动作。"
        if probe_state == "probe_crossline_upgrade_ready":
            return "跨线对象已先 act right，只允许30%条件试错，不直接当成主攻线切换。"
        if probe_allows_conditional_30:
            return "环境条件尚未完全满足，但候选已具备可升级探针反馈，只允许30%条件试错仓。"
        if execution_bias in ("prep_only", "divergence_only"):
            return "环境未完全共振，但最强对象已经先证明自己，只允许30%条件试错仓。"
        return "环境条件尚未完全满足，但候选已连续多日报告并保持承接，只允许30%条件试错仓。"

    if (
        execution_bias in ("prep_only", "divergence_only")
        and candidate
        and allow_conditional_30
        and feedback_clock.get("ready")
        and conditional_probe_ok
        and not bridge_prep_observe_only
    ):
        decision.update(
            {
                "participation_mode": "conditional_30",
                "target_position_pct": 30,
                "sizing_reason": _conditional_30_reason(),
            }
        )
        return _finalize(decision)
    if execution_bias == "watch_only" and candidate and allow_conditional_30 and feedback_clock.get("ready") and (history_continuity_ready or probe_allows_conditional_30 or second_shot_ready or weak_to_strong_upgrade_ready) and conditional_probe_ok:
        decision.update(
            {
                "participation_mode": "conditional_30",
                "target_position_pct": 30,
                "sizing_reason": _conditional_30_reason(),
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
            decision["sizing_reason"] = "当前只保留条件执行预备态，仍需次日继续观察与60分钟确认，不直接升级30%。"
        else:
            decision["sizing_reason"] = "虽有条件执行预备态，但反馈时钟未成熟，维持0%。"
    return _finalize(decision)
