from __future__ import annotations

from selection.candidate_execution_contracts import build_philosophy_constraint_text as _default_build_philosophy_constraint_text
from selection.position_sizing_runtime import (
    build_position_sizing_decision as _default_build_position_sizing_decision,
    with_single_focus_counts,
)
from selection.watch_anchor_support import build_execute_anchor_window_text as _default_build_execute_anchor_window_text
from report.front_summary_builder import (
    build_front_mainline_label_contract,
    build_front_style_action_text_contract,
    render_core_mvp_digest_contract,
    render_mvp_focus_summary_contract,
)

__all__ = [
    "build_bridge_prep_context",
    "build_front_follow_action_text",
    "build_front_structure_layer_text",
    "build_front_mainline_label",
    "build_front_style_action_text",
    "format_candidate_preview",
    "front_position_guard_label",
    "render_core_mvp_digest",
    "render_mvp_focus_summary",
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


def _resolve_candidate_setup_id(candidate=None):
    candidate = candidate or {}
    return str(
        candidate.get("abnormal_setup_signal_id")
        or candidate.get("setup_signal_id")
        or ""
    ).strip()


def _build_position_sizing_decision(**kwargs):
    return _default_build_position_sizing_decision(**kwargs)


def _build_execute_anchor_window_text(position_decision=None, watch_anchor=None, watch_anchor_type=""):
    return _default_build_execute_anchor_window_text(
        position_decision=position_decision,
        watch_anchor=watch_anchor,
        watch_anchor_type=watch_anchor_type,
    )


def _build_philosophy_constraint_text(
    final_gate=None,
    best_stock=None,
    watch_anchor=None,
    watch_anchor_type="",
    state_machine_snapshot=None,
):
    return _default_build_philosophy_constraint_text(
        final_gate=final_gate,
        best_stock=best_stock,
        watch_anchor=watch_anchor,
        watch_anchor_type=watch_anchor_type,
        state_machine_snapshot=state_machine_snapshot,
    )


def _build_bridge_prep_context(
    position_level="",
    final_gate=None,
    watch_anchor=None,
    watch_anchor_type="",
    state_machine_snapshot=None,
):
    return build_bridge_prep_context(
        position_level=position_level,
        final_gate=final_gate,
        watch_anchor=watch_anchor,
        watch_anchor_type=watch_anchor_type,
        state_machine_snapshot=state_machine_snapshot,
    )


def build_front_mainline_label(market_research_snapshot, fallback_mainline=""):
    return build_front_mainline_label_contract(
        market_research_snapshot,
        fallback_mainline=fallback_mainline,
    )


def build_front_style_action_text(
    style_switch=None,
    final_gate=None,
    best_stock=None,
    watch_anchor=None,
    watch_anchor_type="",
):
    return build_front_style_action_text_contract(
        style_switch=style_switch,
        final_gate=final_gate,
        best_stock=best_stock,
        watch_anchor=watch_anchor,
        watch_anchor_type=watch_anchor_type,
    )


def front_position_guard_label(position_level="", *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _front_position_guard_label_legacy_body(position_level)
    finally:
        _restore_runtime_bindings(previous)


def _front_position_guard_label(position_level=""):
    return front_position_guard_label(position_level)


def format_candidate_preview(candidates, formatter, limit=3, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _format_candidate_preview_legacy_body(candidates, formatter, limit=limit)
    finally:
        _restore_runtime_bindings(previous)


def build_bridge_prep_context(
    position_level="",
    final_gate=None,
    watch_anchor=None,
    watch_anchor_type="",
    state_machine_snapshot=None,
    *,
    helpers=None,
):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _build_bridge_prep_context_legacy_body(
            position_level=position_level,
            final_gate=final_gate,
            watch_anchor=watch_anchor,
            watch_anchor_type=watch_anchor_type,
            state_machine_snapshot=state_machine_snapshot,
        )
    finally:
        _restore_runtime_bindings(previous)


def build_front_follow_action_text(
    final_gate=None,
    best_stock=None,
    watch_anchor=None,
    watch_anchor_type="",
    fallback_text="",
    focus_group=None,
    keep_group=None,
    delete_group=None,
    position_level="",
    state_machine_snapshot=None,
    target_date="",
    special_probe_verdict=None,
    *,
    helpers=None,
):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _build_front_follow_action_text_legacy_body(
            final_gate=final_gate,
            best_stock=best_stock,
            watch_anchor=watch_anchor,
            watch_anchor_type=watch_anchor_type,
            fallback_text=fallback_text,
            focus_group=focus_group,
            keep_group=keep_group,
            delete_group=delete_group,
            position_level=position_level,
            state_machine_snapshot=state_machine_snapshot,
            target_date=target_date,
            special_probe_verdict=special_probe_verdict,
        )
    finally:
        _restore_runtime_bindings(previous)


def build_front_structure_layer_text(
    final_gate=None,
    focus_group=None,
    keep_group=None,
    delete_group=None,
    best_stock=None,
    watch_anchor=None,
    watch_anchor_type="",
    position_level="",
    state_machine_snapshot=None,
    target_date="",
    special_probe_verdict=None,
    *,
    helpers=None,
):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _build_front_structure_layer_text_legacy_body(
            final_gate=final_gate,
            focus_group=focus_group,
            keep_group=keep_group,
            delete_group=delete_group,
            best_stock=best_stock,
            watch_anchor=watch_anchor,
            watch_anchor_type=watch_anchor_type,
            position_level=position_level,
            state_machine_snapshot=state_machine_snapshot,
            target_date=target_date,
            special_probe_verdict=special_probe_verdict,
        )
    finally:
        _restore_runtime_bindings(previous)


def render_core_mvp_digest(
    market_research_snapshot,
    final_gate,
    position_level,
    position_reason,
    exit_analysis=None,
    execution_framework_text="",
    high_board_count=0,
    structure_layer_text="",
    front_follow_action_text="",
    special_probe_text="",
    philosophy_constraint_text="",
    best_stock=None,
    watch_anchor=None,
    watch_anchor_type="",
    target_date="",
    compact=False,
    *,
    build_gem_textbook_next_step_text,
    build_alignment_pool_text,
    build_mainline_rotation_snapshot,
    resolve_primary_mainline_name,
    build_weak_to_strong_context,
    get_contract_logic_digest_text,
    render_front_digest,
    safe_float,
):
    return render_core_mvp_digest_contract(
        market_research_snapshot,
        final_gate,
        position_level,
        position_reason,
        exit_analysis=exit_analysis,
        execution_framework_text=execution_framework_text,
        high_board_count=high_board_count,
        structure_layer_text=structure_layer_text,
        front_follow_action_text=front_follow_action_text,
        special_probe_text=special_probe_text,
        philosophy_constraint_text=philosophy_constraint_text,
        best_stock=best_stock,
        watch_anchor=watch_anchor,
        watch_anchor_type=watch_anchor_type,
        target_date=target_date,
        compact=compact,
        build_front_mainline_label=build_front_mainline_label,
        build_gem_textbook_next_step_text=build_gem_textbook_next_step_text,
        build_front_style_action_text=build_front_style_action_text,
        build_alignment_pool_text=build_alignment_pool_text,
        build_mainline_rotation_snapshot=build_mainline_rotation_snapshot,
        resolve_primary_mainline_name=resolve_primary_mainline_name,
        build_weak_to_strong_context=build_weak_to_strong_context,
        get_contract_logic_digest_text=get_contract_logic_digest_text,
        render_front_digest=render_front_digest,
        safe_float=safe_float,
    )


def render_mvp_focus_summary(
    market_research_snapshot,
    watchlist=None,
    abnormal_watch_pool=None,
    leader_memory_bank=None,
    core_stocks=None,
    crossline_observation_stocks=None,
    gem_breathing_candidates=None,
    filtered_out_gem_candidates=None,
    structure_layer_text="",
    focus_group=None,
    keep_group=None,
    delete_group=None,
    best_stock=None,
    watch_anchor=None,
    watch_anchor_type="重点观察谁",
    abnormal_probe_group=None,
    final_gate=None,
    position_level="",
    target_date="",
    compact=False,
    *,
    resolve_primary_mainline_name,
    split_abnormal_watch_pool,
    build_bridge_prep_context,
    build_front_structure_layer_text,
    build_special_probe_verdict,
    build_special_probe_focus_text,
    build_mainline_rotation_snapshot,
    split_candidates_by_mainline,
    format_candidate_preview,
    candidate_matches_mainline,
    build_position_sizing_decision,
    build_cycle_triplet_texts,
    build_execute_anchor_window_text,
    format_abnormal_probe_text,
    build_front_follow_action_text,
    render_mvp_focus_summary,
):
    return render_mvp_focus_summary_contract(
        market_research_snapshot,
        watchlist=watchlist,
        abnormal_watch_pool=abnormal_watch_pool,
        leader_memory_bank=leader_memory_bank,
        core_stocks=core_stocks,
        crossline_observation_stocks=crossline_observation_stocks,
        gem_breathing_candidates=gem_breathing_candidates,
        filtered_out_gem_candidates=filtered_out_gem_candidates,
        structure_layer_text=structure_layer_text,
        focus_group=focus_group,
        keep_group=keep_group,
        delete_group=delete_group,
        best_stock=best_stock,
        watch_anchor=watch_anchor,
        watch_anchor_type=watch_anchor_type,
        abnormal_probe_group=abnormal_probe_group,
        final_gate=final_gate,
        position_level=position_level,
        target_date=target_date,
        compact=compact,
        resolve_primary_mainline_name=resolve_primary_mainline_name,
        split_abnormal_watch_pool=split_abnormal_watch_pool,
        build_bridge_prep_context=build_bridge_prep_context,
        build_front_structure_layer_text=build_front_structure_layer_text,
        build_special_probe_verdict=build_special_probe_verdict,
        build_special_probe_focus_text=build_special_probe_focus_text,
        build_mainline_rotation_snapshot=build_mainline_rotation_snapshot,
        split_candidates_by_mainline=split_candidates_by_mainline,
        format_candidate_preview=format_candidate_preview,
        candidate_matches_mainline=candidate_matches_mainline,
        build_position_sizing_decision=build_position_sizing_decision,
        build_cycle_triplet_texts=build_cycle_triplet_texts,
        build_execute_anchor_window_text=build_execute_anchor_window_text,
        format_abnormal_probe_text=format_abnormal_probe_text,
        build_front_follow_action_text=build_front_follow_action_text,
        render_mvp_focus_summary=render_mvp_focus_summary,
    )


def _build_front_follow_action_text_legacy_body(
    final_gate=None,
    best_stock=None,
    watch_anchor=None,
    watch_anchor_type="",
    fallback_text="",
    focus_group=None,
    keep_group=None,
    delete_group=None,
    position_level="",
    state_machine_snapshot=None,
    target_date="",
    special_probe_verdict=None,
):
    final_gate = final_gate or {}
    state_machine_snapshot = state_machine_snapshot or {}
    fallback_text = str(fallback_text or final_gate.get("final_action", "") or "").strip()
    watch_anchor_type = str(watch_anchor_type or "").strip()
    focus_group = focus_group or []
    keep_group = keep_group or []
    delete_group = delete_group or []
    final_gate = with_single_focus_counts(
        final_gate,
        focus_group=focus_group,
        keep_group=keep_group,
    )
    guard_label = _front_position_guard_label(position_level)
    execution_bias = str(state_machine_snapshot.get("execution_bias", "") or "").strip()
    pulse_stage = str(state_machine_snapshot.get("pulse_stage", "") or "").strip()
    bridge_prep = _build_bridge_prep_context(
        position_level=position_level,
        final_gate=final_gate,
        watch_anchor=watch_anchor,
        watch_anchor_type=watch_anchor_type,
        state_machine_snapshot=state_machine_snapshot,
    )
    position_decision = _build_position_sizing_decision(
        final_gate=final_gate,
        state_machine_snapshot=state_machine_snapshot,
        best_stock=best_stock,
        watch_anchor=watch_anchor,
        watch_anchor_type=watch_anchor_type,
        mainline_name=str(state_machine_snapshot.get("leading_line", "") or ""),
        target_date=target_date,
        special_probe_verdict=special_probe_verdict,
    )
    target_position_pct = int(_safe_float(position_decision.get("target_position_pct", 0)))
    trigger_text = position_decision.get("trigger_text", "09:50-10:10窗口满足条件")
    execute_anchor_window_text = _build_execute_anchor_window_text(
        position_decision=position_decision,
        watch_anchor=watch_anchor,
        watch_anchor_type=watch_anchor_type,
    )
    watch_source = str((watch_anchor or {}).get("watch_source", "") or "").strip()
    philosophy_constraint_text = _build_philosophy_constraint_text(
        final_gate=final_gate,
        best_stock=best_stock,
        watch_anchor=watch_anchor,
        watch_anchor_type=watch_anchor_type,
        state_machine_snapshot=state_machine_snapshot,
    )

    if watch_anchor and watch_source == "gem_breathing_20cm":
        note_text = str((watch_anchor or {}).get("watch_anchor_note", "") or "").strip()
        text = "不开新仓，只观察创业板20cm预启动是否走成右侧确认；命中09:50-10:10窗口内满足条件后才评估50%条件执行"
        if note_text:
            text = f"{text}；{note_text}"
        return f"{text}；{philosophy_constraint_text}" if philosophy_constraint_text else text

    if target_position_pct == 50 and best_stock:
        text = f"只做唯一对象，{trigger_text}后按50%执行"
        return f"{text}；{philosophy_constraint_text}" if philosophy_constraint_text else text
    probe_state = str((special_probe_verdict or {}).get("probe_state", "") or "").strip()

    if 0 < target_position_pct < 50:
        if execute_anchor_window_text:
            return execute_anchor_window_text
        if probe_state == "probe_crossline_upgrade_ready":
            return f"跨线对象已先走势符合强势标准；只在固定交易窗口内条件成立后评估50%条件执行，{trigger_text}后才动手，不满足转为0%不参与"
        return f"只允许一只进入50%条件执行；{trigger_text}后才动手，不满足转为0%不参与"
    if execution_bias == "avoid":
        text = "0%，先不跟随，继续观察，等下一轮真正的新启动"
        return f"{text}；{philosophy_constraint_text}" if philosophy_constraint_text else text
    if bridge_prep.get("active"):
        return f"默认不开新仓；{bridge_prep.get('upgrade_text', '')}；否则继续仅观察"
    if watch_anchor and "跨线承接成立" in watch_anchor_type:
        text = "不开新仓，只观察跨线承接有没有继续成立；没有外溢确认前不升级"
        return f"{text}；{philosophy_constraint_text}" if philosophy_constraint_text else text
    if watch_anchor and "跨线外溢确认" in watch_anchor_type:
        text = "不开新仓，只观察跨线资金外溢能否继续扩大；没有主攻线切换证据前仍不升级买入资格"
        return f"{text}；{philosophy_constraint_text}" if philosophy_constraint_text else text
    if watch_anchor and "跨线异常" in watch_anchor_type:
        if final_gate.get("can_new_entry"):
            text = "不开仓，先看特殊标的有没有深跌/抗跌，再决定这轮调整是继续收还是重新攻；只有它走成明天唯一能买的那只才考虑买入"
            return f"{text}；{philosophy_constraint_text}" if philosophy_constraint_text else text
        text = "不开新仓，只观察特殊标的有没有深跌/抗跌，再决定这轮调整何时结束"
        return f"{text}；{philosophy_constraint_text}" if philosophy_constraint_text else text
    if watch_anchor and "异常" in watch_anchor_type:
        if final_gate.get("can_new_entry"):
            return "不开仓，先看特殊标的有没有深跌/抗跌，再决定这轮调整是继续收还是重新攻；只有它走成明天唯一能买的那只才考虑买入"
        return "不开新仓，只观察特殊标的有没有深跌/抗跌，再决定这轮调整何时结束"
    if execution_bias == "watch_only" and final_gate.get("can_new_entry"):
        text = f"0%，主线脉冲已进入{pulse_stage or '钝化'}段，只观察不加仓"
        return f"{text}；{philosophy_constraint_text}" if philosophy_constraint_text else text
    if execution_bias == "divergence_only" and final_gate.get("can_new_entry") and not best_stock:
        return "0%，先等主线分歧承接成立，不做一致加速追价"
    if best_stock:
        if execution_bias == "divergence_only":
            return "0%，只做主线分歧承接后的唯一对象，不做一致加速追价"
        return fallback_text

    if final_gate.get("can_new_entry"):
        if focus_group or keep_group:
            return "不开仓，先缩小范围，等市场自己选出明天唯一能买的那只"
        if delete_group:
            return "不开仓，先回避走弱对象，等新的强票走出来"
        return "不开仓，继续观察，等市场自己选出明天唯一能买的那只"

    if focus_group:
        return f"{guard_label}不开新仓，只盯最强那几只，先不抢跑"
    if keep_group:
        return f"{guard_label}不开新仓，只保留观察名单，不给买入资格"
    if delete_group:
        return f"{guard_label}不开新仓，先回避走弱对象"
    return fallback_text


def _front_position_guard_label_legacy_body(position_level=""):
    text = str(position_level or "").strip()
    if not text:
        return "当前仓位"
    if "100%" in text or "核心进攻" in text:
        return "100%核心进攻"
    if "50%" in text or "条件执行" in text:
        return "50%条件执行"
    if "0%" in text or "防守" in text:
        return "0%不参与"
    return text


def _format_candidate_preview_legacy_body(candidates, formatter, limit=3):
    parts = []
    for item in (candidates or [])[:limit]:
        parts.append(formatter(item))
    return " / ".join(parts)


def _build_bridge_prep_context_legacy_body(
    position_level="",
    final_gate=None,
    watch_anchor=None,
    watch_anchor_type="",
    state_machine_snapshot=None,
):
    final_gate = final_gate or {}
    watch_anchor = watch_anchor or {}
    state_machine_snapshot = state_machine_snapshot or {}
    position_text = str(position_level or "").strip()
    watch_anchor_type = str(watch_anchor_type or "").strip()
    execution_bias = str(state_machine_snapshot.get("execution_bias", "") or "").strip()

    if execution_bias != "prep_only":
        return {"active": False}
    if not position_text:
        return {"active": False}
    if final_gate.get("can_new_entry"):
        return {"active": False}
    if not watch_anchor:
        return {"active": False}
    if "跨线" in watch_anchor_type:
        return {"active": False}
    if "主线" not in watch_anchor_type:
        return {"active": False}

    follow_state = str(
        watch_anchor.get("abnormal_follow_state")
        or watch_anchor.get("follow_state")
        or ""
    ).strip()
    if follow_state not in ("跌不下去", "缩量消化"):
        return {"active": False}

    minute_plan = watch_anchor.get("minute_plan") or {}
    confirm_price = _round_or_none(minute_plan.get("confirm_price_60m"))
    guard_price = _round_or_none(
        watch_anchor.get("display_anchor_price")
        or watch_anchor.get("execution_stop")
        or watch_anchor.get("effective_stop")
    )
    if confirm_price is None or guard_price is None:
        return {"active": False}

    name = watch_anchor.get("name", "-")
    code = watch_anchor.get("code", "-")
    priority_keep = (
        _resolve_candidate_setup_id(watch_anchor) == "burst_hold"
        and follow_state == "跌不下去"
        and "主线" in watch_anchor_type
    )
    upgrade_text = f"若次日09:50-10:10站上{confirm_price:.2f}且不破{guard_price:.2f}，才升级为唯一执行候选"
    summary_prefix = "0%不参与中优先保留一只固定交易窗口执行候选：" if priority_keep else "0%不参与中保留一只固定交易窗口执行候选："
    return {
        "active": True,
        "label": "条件执行预备态",
        "candidate_label": f"{name}({code})",
        "upgrade_text": upgrade_text,
        "summary_text": f"{summary_prefix}{upgrade_text}",
        "priority_keep": priority_keep,
    }


def _build_front_structure_layer_text_legacy_body(
    final_gate=None,
    focus_group=None,
    keep_group=None,
    delete_group=None,
    best_stock=None,
    watch_anchor=None,
    watch_anchor_type="",
    position_level="",
    state_machine_snapshot=None,
    target_date="",
    special_probe_verdict=None,
):
    final_gate = final_gate or {}
    focus_group = focus_group or []
    keep_group = keep_group or []
    delete_group = delete_group or []
    final_gate = with_single_focus_counts(
        final_gate,
        focus_group=focus_group,
        keep_group=keep_group,
    )
    state_machine_snapshot = state_machine_snapshot or {}
    bridge_prep = _build_bridge_prep_context(
        position_level=position_level,
        final_gate=final_gate,
        watch_anchor=watch_anchor,
        watch_anchor_type=watch_anchor_type,
        state_machine_snapshot=state_machine_snapshot,
    )
    position_decision = _build_position_sizing_decision(
        final_gate=final_gate,
        state_machine_snapshot=state_machine_snapshot,
        best_stock=best_stock,
        watch_anchor=watch_anchor,
        watch_anchor_type=watch_anchor_type,
        mainline_name=str(state_machine_snapshot.get("leading_line", "") or ""),
        target_date=target_date,
        special_probe_verdict=special_probe_verdict,
    )
    target_position_pct = int(_safe_float(position_decision.get("target_position_pct", 0)))
    trigger_text = position_decision.get("trigger_text", "09:50-10:10窗口满足条件")
    execute_anchor_window_text = _build_execute_anchor_window_text(
        position_decision=position_decision,
        watch_anchor=watch_anchor,
        watch_anchor_type=watch_anchor_type,
    )
    execution_bias = str(state_machine_snapshot.get("execution_bias", "") or "").strip()
    probe_state = str((special_probe_verdict or {}).get("probe_state", "") or "").strip()
    philosophy_constraint_text = _build_philosophy_constraint_text(
        final_gate=final_gate,
        best_stock=best_stock,
        watch_anchor=watch_anchor,
        watch_anchor_type=watch_anchor_type,
        state_machine_snapshot=state_machine_snapshot,
    )
    watch_source = str((watch_anchor or {}).get("watch_source", "") or "").strip()

    if watch_anchor and watch_source == "gem_breathing_20cm":
        note_text = str((watch_anchor or {}).get("watch_anchor_note", "") or "").strip()
        if 0 < target_position_pct < 50:
            text = f"创业板20cm预启动进入50%条件执行；{trigger_text}后才动手，不满足继续0%不参与"
        else:
            text = "创业板20cm预启动只先进观察池；先看右侧确认和09:50-10:10窗口，再决定是否进入50%条件执行"
        if note_text:
            text = f"{text}；{note_text}"
        return f"{text}；{philosophy_constraint_text}" if philosophy_constraint_text else text

    if target_position_pct == 50 and best_stock:
        text = f"市场已允许出手，而且已经缩到一只可买股；只做50%条件执行，{trigger_text}后才动手"
        return f"{text}；{philosophy_constraint_text}" if philosophy_constraint_text else text
    if 0 < target_position_pct < 50:
        if execute_anchor_window_text:
            return "50%条件执行；执行候选观察对象已进入二次突破升级阶段，仍需固定交易窗口内条件确认"
        if probe_state == "probe_crossline_upgrade_ready":
            return f"50%条件执行；跨线对象已先走势符合强势标准，{trigger_text}后才动手，不直接当成主攻线切换"
        return f"50%条件执行；{trigger_text}后才动手，不满足继续0%不参与"
    if execution_bias == "avoid":
        text = "0%，先不跟随，继续观察，等下一轮真正的新启动"
        return f"{text}；{philosophy_constraint_text}" if philosophy_constraint_text else text

    if final_gate.get("can_new_entry"):
        if best_stock:
            text = "市场已允许出手，而且已经缩到一只可买股"
            return f"{text}；{philosophy_constraint_text}" if philosophy_constraint_text else text
        if watch_anchor:
            if "异常" in str(watch_anchor_type or ""):
                text = "市场已允许出手，但现在只剩特殊标的观察层，还没有唯一执行对象"
                return f"{text}；{philosophy_constraint_text}" if philosophy_constraint_text else text
            text = "市场已允许出手，但现在还只有重点盯盘股，还没有缩到一只可买股"
            return f"{text}；{philosophy_constraint_text}" if philosophy_constraint_text else text
        if focus_group:
            return "市场已允许出手，但还没有缩到一只可买股"
        if keep_group:
            return "市场已允许出手，但当前只有观察层，还没有清晰执行对象"
        if delete_group:
            return "市场已允许出手，但当前这批票偏弱，先回避，不抢反弹"
        return "市场已允许出手，但当前还没有可买股"

    guard_label = _front_position_guard_label(position_level)
    if bridge_prep.get("active"):
        summary_text = str(bridge_prep.get("summary_text", "") or "").strip()
        if summary_text:
            return summary_text
        return f"{guard_label}默认不开新仓，但保留一只条件执行预备态对象：{bridge_prep.get('upgrade_text', '')}"
    if watch_anchor:
        if "跨线" in str(watch_anchor_type or ""):
            return f"{guard_label}不开新仓，只保留高优先级观察权，先看资金会不会向竞争线外溢"
        return f"{guard_label}不开新仓，只保留高优先级观察权，先看主线对象能否继续证明自己"
    if focus_group:
        return f"{guard_label}不开新仓，个股结构未坏，但环境未开"
    if keep_group:
        return f"{guard_label}不开新仓，当前只保留观察层，不给买入资格"
    if delete_group:
        return f"{guard_label}不开新仓，主线对象偏弱，先不出手"
    return f"{guard_label}不开新仓，只保留市场研究与观察权"
