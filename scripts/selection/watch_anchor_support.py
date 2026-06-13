from __future__ import annotations

import daily_report_analysis_utils as analysis_utils
from selection.candidate_execution_contracts import (
    DEFENSIVE_EXIT_RULE_TEXT,
    PROFIT_EXIT_RULE_TEXT,
    STRATEGY_HOLDING_DAYS_MAX,
    STRATEGY_HOLDING_DAYS_MIN,
    build_candidate_exit_rules as _default_build_candidate_exit_rules,
    build_weak_to_strong_context as _default_build_weak_to_strong_context,
    candidate_has_formal_abnormal_setup as _default_candidate_has_formal_abnormal_setup,
    candidate_is_resilient_abnormal as _default_candidate_is_resilient_abnormal,
    format_holding_window_text as _default_format_holding_window_text,
    is_bridge_priority_setup as _default_is_bridge_priority_setup,
)
from selection.advantage_dedup_runtime import build_grouped_advantage_score

__all__ = [
    "append_watch_anchor_note",
    "build_cycle_triplet_texts",
    "build_execute_anchor_window_text",
    "classify_watch_anchor_bucket",
    "derive_pending_candidate_type",
    "derive_watch_anchor_note",
    "derive_watch_anchor_type",
    "requires_crossline_second_confirmation",
    "select_priority_watch_anchor",
    "sort_watch_anchor_candidates",
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


def classify_watch_anchor_bucket(candidate, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _classify_watch_anchor_bucket_legacy_body(candidate)
    finally:
        _restore_runtime_bindings(previous)


def requires_crossline_second_confirmation(candidate, mainline_name="", *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _requires_crossline_second_confirmation_legacy_body(candidate, mainline_name)
    finally:
        _restore_runtime_bindings(previous)


def derive_watch_anchor_type(candidate, mainline_name="", *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _derive_watch_anchor_type_legacy_body(candidate, mainline_name)
    finally:
        _restore_runtime_bindings(previous)


def derive_pending_candidate_type(candidate, mainline_name="", *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _derive_pending_candidate_type_legacy_body(candidate, mainline_name)
    finally:
        _restore_runtime_bindings(previous)


def derive_watch_anchor_note(candidate, mainline_name="", *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _derive_watch_anchor_note_legacy_body(candidate, mainline_name)
    finally:
        _restore_runtime_bindings(previous)


def append_watch_anchor_note(report_lines, candidate, prefix="  ", *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _append_watch_anchor_note_legacy_body(report_lines, candidate, prefix=prefix)
    finally:
        _restore_runtime_bindings(previous)


def select_priority_watch_anchor(
    trade_gate_open=False,
    abnormal_watch_anchor_candidates=None,
    pending_candidates=None,
    observation_candidates=None,
    waiting_stocks=None,
    gem_observation_stocks=None,
    target_date="",
    mainline_name="",
    *,
    helpers=None,
):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _select_priority_watch_anchor_legacy_body(
            trade_gate_open=trade_gate_open,
            abnormal_watch_anchor_candidates=abnormal_watch_anchor_candidates,
            pending_candidates=pending_candidates,
            observation_candidates=observation_candidates,
            waiting_stocks=waiting_stocks,
            gem_observation_stocks=gem_observation_stocks,
            target_date=target_date,
            mainline_name=mainline_name,
        )
    finally:
        _restore_runtime_bindings(previous)


def sort_watch_anchor_candidates(candidates, mainline_name="", state_machine_snapshot=None, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _sort_watch_anchor_candidates_legacy_body(
            candidates,
            mainline_name=mainline_name,
            state_machine_snapshot=state_machine_snapshot,
        )
    finally:
        _restore_runtime_bindings(previous)


def build_execute_anchor_window_text(position_decision=None, watch_anchor=None, watch_anchor_type="", *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _build_execute_anchor_window_text_legacy_body(
            position_decision=position_decision,
            watch_anchor=watch_anchor,
            watch_anchor_type=watch_anchor_type,
        )
    finally:
        _restore_runtime_bindings(previous)


def build_cycle_triplet_texts(position_decision=None, candidate=None, watch_anchor_type="", *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _build_cycle_triplet_texts_legacy_body(
            position_decision=position_decision,
            candidate=candidate,
            watch_anchor_type=watch_anchor_type,
        )
    finally:
        _restore_runtime_bindings(previous)


def _classify_watch_anchor_bucket(candidate):
    return _classify_watch_anchor_bucket_legacy_body(candidate)


def _requires_crossline_second_confirmation(candidate, mainline_name=""):
    return _requires_crossline_second_confirmation_legacy_body(candidate, mainline_name)


def _derive_watch_anchor_type(candidate, mainline_name=""):
    return _derive_watch_anchor_type_legacy_body(candidate, mainline_name)


def _derive_pending_candidate_type(candidate, mainline_name=""):
    return _derive_pending_candidate_type_legacy_body(candidate, mainline_name)


def _derive_watch_anchor_note(candidate, mainline_name=""):
    return _derive_watch_anchor_note_legacy_body(candidate, mainline_name)


def _append_watch_anchor_note(report_lines, candidate, prefix="  "):
    return _append_watch_anchor_note_legacy_body(report_lines, candidate, prefix=prefix)


def _select_priority_watch_anchor(
    trade_gate_open=False,
    abnormal_watch_anchor_candidates=None,
    pending_candidates=None,
    observation_candidates=None,
    waiting_stocks=None,
    gem_observation_stocks=None,
    target_date="",
    mainline_name="",
):
    return _select_priority_watch_anchor_legacy_body(
        trade_gate_open=trade_gate_open,
        abnormal_watch_anchor_candidates=abnormal_watch_anchor_candidates,
        pending_candidates=pending_candidates,
        observation_candidates=observation_candidates,
        waiting_stocks=waiting_stocks,
        gem_observation_stocks=gem_observation_stocks,
        target_date=target_date,
        mainline_name=mainline_name,
    )


def _sort_watch_anchor_candidates(candidates, mainline_name="", state_machine_snapshot=None):
    return _sort_watch_anchor_candidates_legacy_body(
        candidates,
        mainline_name=mainline_name,
        state_machine_snapshot=state_machine_snapshot,
    )


def _build_execute_anchor_window_text(position_decision=None, watch_anchor=None, watch_anchor_type=""):
    return _build_execute_anchor_window_text_legacy_body(
        position_decision=position_decision,
        watch_anchor=watch_anchor,
        watch_anchor_type=watch_anchor_type,
    )


def _build_cycle_triplet_texts(position_decision=None, candidate=None, watch_anchor_type=""):
    return _build_cycle_triplet_texts_legacy_body(
        position_decision=position_decision,
        candidate=candidate,
        watch_anchor_type=watch_anchor_type,
    )


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _build_gem_breathing_watch_anchor(gem_candidate=None, target_date="", mainline_name=""):
    return dict(gem_candidate or {})


def _round_or_none(value, digits=2):
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def _candidate_matches_mainline(candidate, mainline_name=""):
    return analysis_utils._candidate_matches_mainline(candidate, mainline_name)


def _resolve_candidate_setup_id(candidate):
    candidate = candidate or {}
    return str(
        candidate.get("abnormal_setup_signal_id")
        or candidate.get("setup_signal_id")
        or ""
    ).strip()


def _resolve_candidate_follow_state(candidate):
    candidate = candidate or {}
    return str(
        candidate.get("abnormal_follow_state")
        or candidate.get("follow_state")
        or ""
    ).strip()


def _candidate_has_formal_abnormal_setup(candidate):
    return _default_candidate_has_formal_abnormal_setup(candidate)


def _candidate_is_resilient_abnormal(candidate):
    return _default_candidate_is_resilient_abnormal(candidate)


def _build_weak_to_strong_context(candidate=None, mainline_name="", state_machine_snapshot=None):
    return _default_build_weak_to_strong_context(
        candidate=candidate,
        mainline_name=mainline_name,
        state_machine_snapshot=state_machine_snapshot,
    )


def _is_bridge_priority_setup(candidate, mainline_name=""):
    return _default_is_bridge_priority_setup(candidate, mainline_name)


def _build_candidate_exit_rules(candidate=None, stop_plan=None):
    return _default_build_candidate_exit_rules(candidate, stop_plan)


def _format_holding_window_text(min_days, max_days):
    return _default_format_holding_window_text(min_days, max_days)


def _classify_watch_anchor_bucket_legacy_body(candidate):
    candidate = candidate or {}
    abnormal_light = str(candidate.get("abnormal_light", "") or "").strip()
    risk_level = str(candidate.get("risk_level", "") or "").strip()
    raw_risk_score = _safe_float(candidate.get("raw_risk_score", 0))
    repair_count = len(candidate.get("repair_buffers", []) or [])

    if abnormal_light == "🟢 绿灯" and repair_count > 0 and risk_level == "🟡 中风险":
        return 4, "强分歧未坏"
    if abnormal_light == "🟢 绿灯" and repair_count > 0 and raw_risk_score >= 12:
        return 3, "分歧后承接"
    if risk_level == "🟢 低风险":
        return 2, "顺势观察"
    if risk_level == "🟡 中风险":
        return 1, "一般观察"
    return 0, "低优先级"


def _requires_crossline_second_confirmation_legacy_body(candidate, mainline_name=""):
    candidate = candidate or {}
    if not mainline_name:
        return False
    if _candidate_matches_mainline(candidate, mainline_name) or candidate.get("is_mainline"):
        return False
    return (
        _resolve_candidate_setup_id(candidate) == "burst_hold"
        and _resolve_candidate_follow_state(candidate) == "跌不下去"
    )


def _derive_watch_anchor_type_legacy_body(candidate, mainline_name=""):
    watch_source = str((candidate or {}).get("watch_source", "") or "").strip()
    bucket, _ = _classify_watch_anchor_bucket(candidate)
    is_mainline = _candidate_matches_mainline(candidate, mainline_name)
    requires_second_confirmation = _requires_crossline_second_confirmation(candidate, mainline_name)

    if watch_source == "gem_breathing_20cm":
        return "创业板20cm预启动先看谁"
    if requires_second_confirmation:
        if watch_source == "keep_group_watch" and bucket >= 4:
            return "跨线外溢确认先看谁"
        return "跨线承接成立先看谁"
    if watch_source == "abnormal_probe":
        return "主线异常先看谁" if is_mainline else "跨线异常先看谁"
    if watch_source == "keep_group_watch" and bucket >= 4:
        return "主线强分歧先看谁" if is_mainline else "跨线强分歧先看谁"
    if watch_source == "execute_layer":
        return "主线执行预案先看谁" if is_mainline else "跨线执行预案先看谁"
    if watch_source == "waiting_layer":
        return "主线继续看谁" if is_mainline else "跨线继续看谁"
    if watch_source == "keep_group_watch":
        return "主线重点观察谁" if is_mainline else "跨线重点观察谁"
    if is_mainline:
        return "主线重点观察谁"
    return "重点观察谁"


def _derive_pending_candidate_type_legacy_body(candidate, mainline_name=""):
    bucket, _ = _classify_watch_anchor_bucket(candidate)
    is_mainline = _candidate_matches_mainline(candidate, mainline_name)

    if str((candidate or {}).get("watch_source", "") or "").strip() == "abnormal_probe":
        return "主线异常先盯哪只" if is_mainline else "跨线异常先盯哪只"
    if bucket >= 4:
        return "主线强分歧先盯哪只" if is_mainline else "跨线强分歧先盯哪只"
    if str((candidate or {}).get("watch_source", "") or "").strip() == "execute_layer":
        return "主线执行预案先盯哪只" if is_mainline else "跨线执行预案先盯哪只"
    return "主线明天先盯哪只" if is_mainline else "跨线明天先盯哪只"


def _derive_watch_anchor_note_legacy_body(candidate, mainline_name=""):
    candidate = candidate or {}
    mainline_name = str(mainline_name or "").strip()
    decision_stack = candidate.get("decision_stack", {}) or {}
    washout_context = decision_stack.get("washout_reclaim_chain", {}) or {}
    trend_context = decision_stack.get("trend_continuation_chain", {}) or {}
    washout_note = str(washout_context.get("note", "") or "").strip()
    trend_note = str(trend_context.get("note", "") or "").strip()
    watch_source = str(candidate.get("watch_source", "") or "").strip()
    if watch_source == "gem_breathing_20cm":
        base_note = str(
            candidate.get("watch_anchor_note", "")
            or candidate.get("note", "")
            or candidate.get("abnormal_summary", "")
            or "创业板20cm预启动观察。"
        ).strip()
        suffix = "只先进观察池，先看右侧确认和09:50-10:10窗口，不满足继续观察"
        return f"{base_note}；{suffix}" if base_note else suffix
    if (not mainline_name or _candidate_matches_mainline(candidate, mainline_name)) and trend_note:
        if washout_note:
            return f"{trend_note}；{washout_note}"
        return trend_note
    if (not mainline_name or _candidate_matches_mainline(candidate, mainline_name)) and washout_note:
        return washout_note
    if not mainline_name or _candidate_matches_mainline(candidate, mainline_name):
        return ""

    sector = str(candidate.get("sector", "") or candidate.get("sector_name", "") or "").strip()
    watch_source = str(candidate.get("watch_source", "") or "").strip()
    bucket, _ = _classify_watch_anchor_bucket(candidate)

    scope_text = f"跨线对象（{sector}）" if sector else "跨线对象"
    if _requires_crossline_second_confirmation(candidate, mainline_name):
        if watch_source == "keep_group_watch" and bucket >= 4:
            note = (
                f"{scope_text}，当前已进入外溢确认阶段，但仍不代表主攻线从{mainline_name}切换；"
                "只有资金外溢继续扩大且竞争线承接持续，被市场再确认后才评估是否升级"
            )
        else:
            note = (
                f"{scope_text}，当前只到承接成立阶段，不代表主攻线从{mainline_name}切换；"
                "至少再看一天资金外溢是否被市场承认，不满足只观察不升级"
            )
        extra_note = "；".join([part for part in (washout_note, trend_note) if part])
        return f"{note}；{extra_note}" if extra_note else note
    if watch_source == "keep_group_watch" and bucket >= 4:
        note = f"{scope_text}，只用于观察市场承接，不代表主攻线从{mainline_name}切换"
    else:
        note = f"{scope_text}，只用于观察强弱，不代表主攻线从{mainline_name}切换"
    extra_note = "；".join([part for part in (washout_note, trend_note) if part])
    return f"{note}；{extra_note}" if extra_note else note


def _append_watch_anchor_note_legacy_body(report_lines, candidate, prefix="  "):
    note = str((candidate or {}).get("watch_anchor_note", "") or "").strip()
    if note:
        report_lines.append(f"{prefix}{note}")


def _select_priority_watch_anchor_legacy_body(
    trade_gate_open=False,
    abnormal_watch_anchor_candidates=None,
    pending_candidates=None,
    observation_candidates=None,
    waiting_stocks=None,
    gem_observation_stocks=None,
    target_date="",
    mainline_name="",
):
    abnormal_watch_anchor_candidates = abnormal_watch_anchor_candidates or []
    pending_candidates = pending_candidates or []
    observation_candidates = observation_candidates or []
    waiting_stocks = waiting_stocks or []
    gem_observation_stocks = gem_observation_stocks or []

    def _build_gem_anchor():
        if not gem_observation_stocks:
            return None, ""
        gem_watch_seed = dict(gem_observation_stocks[0] or {})
        watch_anchor = _build_gem_breathing_watch_anchor(
            gem_watch_seed,
            target_date=target_date,
            mainline_name=mainline_name,
        )
        watch_anchor_type = watch_anchor.get("watch_anchor_type", "创业板20cm预启动先看谁")
        return watch_anchor, watch_anchor_type

    if trade_gate_open:
        if abnormal_watch_anchor_candidates:
            watch_anchor = dict(abnormal_watch_anchor_candidates[0] or {})
            watch_anchor_type = _derive_pending_candidate_type(watch_anchor, mainline_name=mainline_name)
            watch_anchor["watch_anchor_type"] = watch_anchor_type
            watch_anchor["watch_anchor_note"] = _derive_watch_anchor_note(watch_anchor, mainline_name=mainline_name)
            return watch_anchor, watch_anchor_type
        gem_anchor, gem_anchor_type = _build_gem_anchor()
        if gem_anchor:
            return gem_anchor, gem_anchor_type
        if pending_candidates:
            watch_anchor = dict(pending_candidates[0] or {})
            watch_anchor_type = _derive_pending_candidate_type(watch_anchor, mainline_name=mainline_name)
            watch_anchor["watch_anchor_type"] = watch_anchor_type
            watch_anchor["watch_anchor_note"] = _derive_watch_anchor_note(watch_anchor, mainline_name=mainline_name)
            return watch_anchor, watch_anchor_type
        return None, ""

    if abnormal_watch_anchor_candidates:
        watch_anchor = dict(abnormal_watch_anchor_candidates[0] or {})
        watch_anchor_type = watch_anchor.get("watch_anchor_type", _derive_watch_anchor_type(watch_anchor, mainline_name=mainline_name))
        watch_anchor["watch_anchor_type"] = watch_anchor_type
        watch_anchor["watch_anchor_note"] = _derive_watch_anchor_note(watch_anchor, mainline_name=mainline_name)
        return watch_anchor, watch_anchor_type

    gem_anchor, gem_anchor_type = _build_gem_anchor()
    if gem_anchor:
        return gem_anchor, gem_anchor_type

    if observation_candidates:
        watch_anchor = dict(observation_candidates[0] or {})
        watch_anchor_type = watch_anchor.get("watch_anchor_type", "重点观察谁")
        return watch_anchor, watch_anchor_type

    if waiting_stocks:
        watch_anchor = dict(waiting_stocks[0] or {})
        watch_anchor_type = _derive_watch_anchor_type(watch_anchor, mainline_name=mainline_name) or "继续看谁"
        watch_anchor["watch_anchor_note"] = _derive_watch_anchor_note(watch_anchor, mainline_name=mainline_name)
        return watch_anchor, watch_anchor_type

    return None, ""


def _build_execute_anchor_window_text_legacy_body(position_decision=None, watch_anchor=None, watch_anchor_type=""):
    position_decision = position_decision or {}
    watch_anchor = watch_anchor or {}
    watch_anchor_type = str(watch_anchor_type or "").strip()
    if "执行候选观察" + "锚点" not in watch_anchor_type and "执行候选观察对象" not in watch_anchor_type:
        return ""

    history_feedback = position_decision.get("history_feedback", {}) or {}
    active_watch = bool(position_decision.get("active_watch") or history_feedback.get("active_watch"))
    if not active_watch:
        return ""

    active_window_days = max(int(_safe_float(history_feedback.get("active_window_days", 0))), 0)
    trading_days_since_latest = max(int(_safe_float(history_feedback.get("trading_days_since_latest", 0))), 0)
    remaining_days = max(active_window_days - trading_days_since_latest, 0) if active_window_days else 0
    latest_match = history_feedback.get("latest_match", {}) or {}
    support_price = _round_or_none(
        position_decision.get("support_price")
        or latest_match.get("confirm_support_60m")
        or latest_match.get("effective_stop")
        or watch_anchor.get("execution_stop")
        or watch_anchor.get("display_anchor_price")
    )
    second_shot_breakout_price = _round_or_none(position_decision.get("second_shot_breakout_price"))
    second_shot_ready = bool(position_decision.get("second_shot_ready"))

    prefix = f"这只票按{active_window_days}日活观察管理" if active_window_days else "这只票仍按活观察管理"
    if second_shot_ready and second_shot_breakout_price is not None:
        text = f"{prefix}；已完成{second_shot_breakout_price:.2f}二次突破，只进入50%条件执行"
    else:
        wait_text = f"，当前还剩{remaining_days}日观察寿命" if remaining_days else ""
        trigger_text = f"只有重新站上{second_shot_breakout_price:.2f}且固定交易窗口内条件成立，才考虑50%条件执行" if second_shot_breakout_price is not None else "只有重新完成二次突破且固定交易窗口内条件成立，才考虑50%条件执行"
        text = f"{prefix}{wait_text}；{trigger_text}"
    if support_price is not None:
        text += f"；不破{support_price:.2f}继续观察"
    text += "；过期或失守就作废"
    return text


def _build_cycle_triplet_texts_legacy_body(position_decision=None, candidate=None, watch_anchor_type=""):
    position_decision = position_decision or {}
    candidate = candidate or {}
    watch_anchor_type = str(watch_anchor_type or "").strip()
    watch_source = str(candidate.get("watch_source", "") or "").strip()
    gem_contract = candidate.get("gem_breathing_contract") or {}
    target_position_pct = int(_safe_float(position_decision.get("target_position_pct", 0)))
    trigger_text = str(position_decision.get("trigger_text", "") or "09:50-10:10窗口满足条件").strip()
    trigger_after_text = f"{trigger_text}内满足条件后" if trigger_text.endswith("窗口") else f"{trigger_text}后"
    execute_anchor_window_text = _build_execute_anchor_window_text(
        position_decision=position_decision,
        watch_anchor=candidate,
        watch_anchor_type=watch_anchor_type,
    )
    stop_plan = candidate.get("stop_plan") or {}
    exit_rules = _build_candidate_exit_rules(candidate, stop_plan) if candidate else {
        "holding_days_min": STRATEGY_HOLDING_DAYS_MIN,
        "holding_days_max": STRATEGY_HOLDING_DAYS_MAX,
        "defensive_exit_rule": DEFENSIVE_EXIT_RULE_TEXT,
        "profit_exit_rule": PROFIT_EXIT_RULE_TEXT,
    }
    holding_window_text = _format_holding_window_text(
        exit_rules.get("holding_days_min", STRATEGY_HOLDING_DAYS_MIN),
        exit_rules.get("holding_days_max", STRATEGY_HOLDING_DAYS_MAX),
    )

    observation_cycle = ""
    if watch_source == "gem_breathing_20cm" and candidate:
        contract_window = max(int(_safe_float(gem_contract.get("active_window_days", 0))), 0)
        if contract_window:
            observation_cycle = f"先给{contract_window}日呼吸感观察合同，重点看波动是否继续收敛、量价是否温和放大、能否走成右侧确认"
        else:
            observation_cycle = f"先给{holding_window_text}呼吸感观察合同，重点看波动是否继续收敛、量价是否温和放大、能否走成右侧确认"
    elif execute_anchor_window_text:
        observation_cycle = execute_anchor_window_text
    elif candidate:
        if target_position_pct == 50:
            observation_cycle = f"先给{holding_window_text}主线观察合同，重点看它是否继续 act right"
        elif 0 < target_position_pct < 50:
            observation_cycle = f"先给{holding_window_text}主线观察合同，重点看它是否继续走势符合强势标准，再决定是否进入50%条件执行"
        else:
            observation_cycle = f"先给{holding_window_text}观察合同，只观察不追，等它自己继续证明"

    intervention_cycle = ""
    second_shot_ready = bool(position_decision.get("second_shot_ready"))
    second_shot_breakout_price = _round_or_none(position_decision.get("second_shot_breakout_price"))
    if target_position_pct == 50:
        intervention_cycle = f"{trigger_after_text}按50%执行，才算被市场正式指派接货，不做模糊试单"
    elif 0 < target_position_pct < 50:
        if second_shot_ready and second_shot_breakout_price is not None:
            intervention_cycle = f"已完成{second_shot_breakout_price:.2f}二次突破，{trigger_after_text}评估50%条件执行"
        else:
            intervention_cycle = f"{trigger_after_text}才评估50%条件执行，确认后才算被市场指派接货，不满足继续0%不参与"
    elif execute_anchor_window_text:
        if second_shot_breakout_price is not None:
            intervention_cycle = f"只有重新站上{second_shot_breakout_price:.2f}且固定交易窗口内条件成立，才评估50%条件执行；普通结构只看09:50-10:10窗口"
        else:
            intervention_cycle = f"{trigger_after_text}再评估是否进入50%条件执行"
    elif candidate:
        if watch_source == "gem_breathing_20cm":
            upgrade_text = str(gem_contract.get("upgrade_condition_text", "") or "").strip()
            reset_price = _round_or_none(gem_contract.get("reset_breakout_price"))
            if 0 < target_position_pct < 50:
                intervention_cycle = f"{trigger_after_text}才评估50%条件执行，确认后才算被市场指派接货，不满足继续0%不参与"
            elif second_shot_breakout_price is not None:
                intervention_cycle = f"只有重新站上{second_shot_breakout_price:.2f}且固定交易窗口内条件成立，才评估50%条件执行；普通结构只看09:50-10:10窗口"
            elif reset_price is not None:
                intervention_cycle = f"只有重新站上{reset_price:.2f}且固定交易窗口内条件成立，才评估50%条件执行；普通结构只看09:50-10:10窗口"
            elif upgrade_text:
                intervention_cycle = f"{upgrade_text}；确认后才评估50%条件执行"
            else:
                intervention_cycle = f"{trigger_after_text}才评估是否出手，确认前不提前接货"
        else:
            intervention_cycle = f"当前还没进入介入周期；{trigger_after_text}才评估是否出手，确认前不提前接货"

    exit_cycle_parts = []
    history_feedback = position_decision.get("history_feedback", {}) or {}
    if execute_anchor_window_text:
        support_price = _round_or_none(
            position_decision.get("support_price")
            or history_feedback.get("latest_match", {}).get("confirm_support_60m")
            or history_feedback.get("latest_match", {}).get("effective_stop")
            or candidate.get("execution_stop")
            or candidate.get("display_anchor_price")
        )
        active_window_days = max(int(_safe_float(history_feedback.get("active_window_days", 0))), 0)
        if support_price is not None:
            exit_cycle_parts.append(f"失守{support_price:.2f}就作废")
        if active_window_days:
            exit_cycle_parts.append(f"{active_window_days}日观察到期也作废")
        if target_position_pct > 0:
            exit_cycle_parts.append(exit_rules.get("defensive_exit_rule", DEFENSIVE_EXIT_RULE_TEXT))
            exit_cycle_parts.append(exit_rules.get("profit_exit_rule", PROFIT_EXIT_RULE_TEXT))
    elif candidate:
        if watch_source == "gem_breathing_20cm":
            support_price = _round_or_none(
                gem_contract.get("void_price")
                or candidate.get("execution_stop")
                or candidate.get("display_anchor_price")
            )
            contract_window = max(int(_safe_float(gem_contract.get("active_window_days", 0))), 0)
            if support_price is not None:
                exit_cycle_parts.append(f"失守{support_price:.2f}就作废")
            if contract_window:
                exit_cycle_parts.append(f"{contract_window}日观察到期也作废")
            elif holding_window_text:
                exit_cycle_parts.append(f"{holding_window_text}观察到期也作废")
        exit_cycle_parts.append(exit_rules.get("defensive_exit_rule", DEFENSIVE_EXIT_RULE_TEXT))
        exit_cycle_parts.append(exit_rules.get("profit_exit_rule", PROFIT_EXIT_RULE_TEXT))

    exit_cycle = "；".join([part for part in exit_cycle_parts if str(part or "").strip()])
    return {
        "observation_cycle": observation_cycle,
        "intervention_cycle": intervention_cycle,
        "exit_cycle": exit_cycle,
    }


def _sort_watch_anchor_candidates_legacy_body(candidates, mainline_name="", state_machine_snapshot=None):
    prepared = []
    state_machine_snapshot = state_machine_snapshot or {}
    for item in candidates or []:
        candidate = dict(item or {})
        stack = candidate.get("decision_stack", {}) or {}
        bucket, label = _classify_watch_anchor_bucket(candidate)
        raw_risk_score = _safe_float(candidate.get("raw_risk_score", 0))
        risk_score = _safe_float(candidate.get("risk_score", 0))
        repair_count = len(candidate.get("repair_buffers", []) or [])
        risk_penalty_count = len(candidate.get("risk_penalties", []) or [])
        watch_source = str(candidate.get("watch_source", "") or "").strip()
        abnormal_priority_score = _safe_float(stack.get("setup_priority_score", stack.get("trigger_score", 0)))
        has_formal_setup = bool(stack.get("has_formal_abnormal_setup", _candidate_has_formal_abnormal_setup(candidate)))
        is_resilient_abnormal = bool(stack.get("is_resilient_abnormal", _candidate_is_resilient_abnormal(candidate)))

        weak_to_strong_context = _build_weak_to_strong_context(
            candidate=candidate,
            mainline_name=mainline_name,
            state_machine_snapshot={
                **state_machine_snapshot,
                "leading_line": mainline_name or state_machine_snapshot.get("leading_line", ""),
            },
        )
        weak_to_strong_score = _safe_float(weak_to_strong_context.get("score_bonus", 0))
        advantage_points = [
            {"group": "watch_bucket", "label": label, "score": bucket * 1000},
            {"group": "shape_confirmation", "label": "异动承接形态", "score": abnormal_priority_score},
            {"group": "market_selection", "label": "主攻线同向", "score": _safe_float(stack.get("mainline_score", 0)) * 8},
            {"group": "market_selection", "label": "历史记忆", "score": _safe_float(stack.get("memory_score", 0)) * 6},
            {"group": "shape_confirmation", "label": "触发强度", "score": _safe_float(stack.get("trigger_score", 0))},
            {"group": "tradability", "label": "执行完整度", "score": _safe_float(stack.get("tradability_score", 0)) * 3},
            {"group": "repair_quality", "label": "原始修复分", "score": min(raw_risk_score, 40) * 1.2},
            {"group": "repair_quality", "label": "修复项数量", "score": repair_count * 25},
            {"group": "ev", "label": "策略期望", "score": _safe_float(candidate.get("composite_score", 0)) * 100},
        ]
        if weak_to_strong_score >= 0:
            advantage_points.append({"group": "shape_confirmation", "label": "弱转强提示", "score": weak_to_strong_score})
        else:
            advantage_points.append({"group": "shape_penalty", "label": "弱转强失败", "score": weak_to_strong_score})
        if has_formal_setup:
            advantage_points.append({"group": "shape_confirmation", "label": "正式异动形态", "score": 180})
        if is_resilient_abnormal:
            advantage_points.append({"group": "shape_confirmation", "label": "抗跌样本", "score": 90})
        if watch_source == "keep_group_watch":
            advantage_points.append({"group": "watch_source", "label": "保留观察", "score": 40})
        if watch_source == "waiting_layer":
            advantage_points.append({"group": "watch_source", "label": "等待层", "score": -20})
        if watch_source == "abnormal_probe":
            advantage_points.append({"group": "watch_source", "label": "异动试探", "score": 120})
        if _is_bridge_priority_setup(candidate, mainline_name=mainline_name):
            advantage_points.append({"group": "shape_confirmation", "label": "主线桥接", "score": 180})
        if candidate.get("is_high_anchor") or _safe_float(candidate.get("limit_up_days"), 0) >= 3:
            advantage_points.append({"group": "shape_confirmation", "label": "当前高标", "score": 180})
            advantage_points.append({"group": "market_selection", "label": "板块高度", "score": 100})

        advantage_dedup = build_grouped_advantage_score(
            advantage_points,
            group_caps={
                "market_selection": 100,
                "shape_confirmation": 180,
                "tradability": 100,
                "repair_quality": 80,
                "ev": 100,
                "watch_source": 120,
            },
        )
        observation_priority_score = (
            advantage_dedup["total_score"]
            - risk_score * 4
            - risk_penalty_count * 4
        )

        candidate["watch_priority_bucket"] = bucket
        candidate["watch_priority_label"] = label
        candidate["watch_priority_score"] = round(observation_priority_score, 2)
        candidate["watch_advantage_dedup"] = advantage_dedup
        candidate["watch_anchor_type"] = _derive_watch_anchor_type(candidate, mainline_name=mainline_name)
        base_watch_anchor_note = _derive_watch_anchor_note(candidate, mainline_name=mainline_name)
        weak_note = str(weak_to_strong_context.get("note_text", "") or "").strip()
        if weak_note and weak_note not in base_watch_anchor_note:
            candidate["watch_anchor_note"] = "；".join(part for part in (base_watch_anchor_note, weak_note) if part)
        else:
            candidate["watch_anchor_note"] = base_watch_anchor_note
        candidate["weak_to_strong_context"] = weak_to_strong_context
        prepared.append(candidate)

    return sorted(
        prepared,
        key=lambda item: (
            _safe_float(item.get("watch_priority_score", 0)),
            -(_safe_float(item.get("risk_score", 0))),
            _safe_float(item.get("composite_score", 0)),
        ),
        reverse=True,
    )
