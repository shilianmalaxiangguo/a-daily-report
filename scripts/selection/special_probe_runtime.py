from __future__ import annotations

import daily_report_analysis_utils as analysis_utils
from execution.intraday_execution_runtime import build_waiting_stock_plan as _default_build_waiting_stock_plan
from market_data.daily_price_runtime import (
    evaluate_live_tradability as _default_evaluate_live_tradability,
    fetch_recent_price_bars as _default_fetch_recent_price_bars,
)
from market_data.daily_price_runtime import is_one_word_limit_bar as _default_is_one_word_limit_bar
from report.strategy_tracking_ev import score_execution_candidate as _default_score_execution_candidate
from report.strategy_tracking_support import build_candidate_feedback_clock as _default_build_candidate_feedback_clock
from selection.candidate_context_support import (
    build_trend_continuation_context as _default_build_trend_continuation_context,
    build_washout_reclaim_context as _default_build_washout_reclaim_context,
)
from selection.candidate_execution_contracts import (
    candidate_has_formal_abnormal_setup as _default_candidate_has_formal_abnormal_setup,
    candidate_is_resilient_abnormal as _default_candidate_is_resilient_abnormal,
    get_setup_priority_score as _default_get_setup_priority_score,
    infer_risk_level_from_abnormal_follow_state as _default_infer_risk_level_from_abnormal_follow_state,
    map_setup_id_to_signal_type as _default_map_setup_id_to_signal_type,
)
from selection.watch_anchor_support import (
    derive_watch_anchor_note as _default_derive_watch_anchor_note,
    requires_crossline_second_confirmation as _default_requires_crossline_second_confirmation,
    sort_watch_anchor_candidates as _default_sort_watch_anchor_candidates,
)

__all__ = [
    "build_abnormal_watch_anchor_candidates",
    "build_abnormal_probe_group",
    "build_mainline_upgrade_probe_context",
    "build_special_probe_focus_text",
    "build_special_probe_verdict",
    "format_abnormal_probe_text",
    "get_abnormal_follow_risk_signal",
    "score_candidate_decision_stack",
    "sort_decision_stack_candidates",
]

_MISSING = object()
DECISION_STACK_ORDER_TEXT = "环境 -> 主线 -> 记忆 -> 触发 -> 可交易性 -> EV"


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


def _clamp(value, low, high):
    return max(low, min(high, value))


def _candidate_matches_mainline(candidate, mainline_name=""):
    return analysis_utils._candidate_matches_mainline(candidate, mainline_name)


def _is_degraded_abnormal_snapshot(item):
    return analysis_utils._is_degraded_abnormal_snapshot(item)


def _split_abnormal_watch_pool(abnormal_watch_pool):
    formal_items = []
    degraded_items = []
    for item in abnormal_watch_pool or []:
        if _is_degraded_abnormal_snapshot(item):
            degraded_items.append(item)
        else:
            formal_items.append(item)
    return formal_items, degraded_items


def normalize_stock_code(code):
    return analysis_utils.normalize_stock_code(code)


def _derive_watch_anchor_note(candidate, mainline_name=""):
    return _default_derive_watch_anchor_note(candidate, mainline_name=mainline_name)


def _build_candidate_feedback_clock(candidate=None, watch_anchor_type="", state_machine_snapshot=None, mainline_name="", target_date=""):
    return _default_build_candidate_feedback_clock(
        candidate=candidate,
        watch_anchor_type=watch_anchor_type,
        state_machine_snapshot=state_machine_snapshot,
        mainline_name=mainline_name,
        target_date=target_date,
    )


def _requires_crossline_second_confirmation(candidate, mainline_name=""):
    return _default_requires_crossline_second_confirmation(candidate, mainline_name=mainline_name)


def _candidate_is_resilient_abnormal(candidate):
    return _default_candidate_is_resilient_abnormal(candidate)


def _candidate_has_formal_abnormal_setup(candidate):
    return _default_candidate_has_formal_abnormal_setup(candidate)


def _infer_risk_level_from_abnormal_follow_state(follow_state):
    return _default_infer_risk_level_from_abnormal_follow_state(follow_state)


def _get_setup_priority_score(setup_id="", follow_state=""):
    return _default_get_setup_priority_score(setup_id, follow_state)


def _map_setup_id_to_signal_type(setup_id=""):
    return _default_map_setup_id_to_signal_type(setup_id)


def sector_name_matches(sector_a, sector_b):
    return analysis_utils.sector_name_matches(sector_a, sector_b)


def _resolve_candidate_setup_id(candidate):
    candidate = candidate or {}
    return str(candidate.get("abnormal_setup_signal_id") or candidate.get("setup_signal_id") or "").strip()


def _resolve_candidate_follow_state(candidate):
    candidate = candidate or {}
    return str(candidate.get("abnormal_follow_state") or candidate.get("follow_state") or "").strip()


def _build_washout_reclaim_context(candidate, mainline_name="", conviction_codes=None, leader_memory_codes=None, target_date=""):
    return _default_build_washout_reclaim_context(
        candidate,
        mainline_name=mainline_name,
        conviction_codes=conviction_codes,
        leader_memory_codes=leader_memory_codes,
        target_date=target_date,
    )


def _build_trend_continuation_context(candidate, mainline_name="", conviction_codes=None, leader_memory_codes=None, target_date=""):
    return _default_build_trend_continuation_context(
        candidate,
        mainline_name=mainline_name,
        conviction_codes=conviction_codes,
        leader_memory_codes=leader_memory_codes,
        target_date=target_date,
    )


def _is_one_word_limit_bar(**kwargs):
    return _default_is_one_word_limit_bar(**kwargs)


def fetch_recent_price_bars(*args, **kwargs):
    return _default_fetch_recent_price_bars(*args, **kwargs)


def evaluate_live_tradability(*args, **kwargs):
    return _default_evaluate_live_tradability(*args, **kwargs)


def build_waiting_stock_plan(*args, **kwargs):
    return _default_build_waiting_stock_plan(*args, **kwargs)


def get_abnormal_follow_risk_signal(stock, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _get_abnormal_follow_risk_signal_legacy_body(stock)
    finally:
        _restore_runtime_bindings(previous)


def score_execution_candidate(candidate, ev_calibration=None):
    return _default_score_execution_candidate(candidate, ev_calibration)


def score_candidate_decision_stack(
    candidate,
    final_gate=None,
    mainline_name="",
    conviction_codes=None,
    leader_memory_codes=None,
    state_machine_snapshot=None,
    target_date="",
    *,
    helpers=None,
):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _score_candidate_decision_stack_legacy_body(
            candidate,
            final_gate=final_gate,
            mainline_name=mainline_name,
            conviction_codes=conviction_codes,
            leader_memory_codes=leader_memory_codes,
            state_machine_snapshot=state_machine_snapshot,
            target_date=target_date,
        )
    finally:
        _restore_runtime_bindings(previous)


def sort_decision_stack_candidates(candidates, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _sort_decision_stack_candidates_legacy_body(candidates)
    finally:
        _restore_runtime_bindings(previous)


def sort_watch_anchor_candidates(candidates, mainline_name="", state_machine_snapshot=None):
    return _default_sort_watch_anchor_candidates(
        candidates,
        mainline_name=mainline_name,
        state_machine_snapshot=state_machine_snapshot,
    )


def _score_candidate_decision_stack_legacy_body(
    candidate,
    final_gate=None,
    mainline_name="",
    conviction_codes=None,
    leader_memory_codes=None,
    state_machine_snapshot=None,
    target_date="",
):
    conviction_codes = conviction_codes or set()
    leader_memory_codes = leader_memory_codes or set()
    state_machine_snapshot = state_machine_snapshot or {}

    scored = dict(candidate or {})
    code = normalize_stock_code(scored.get("code", ""))
    name = scored.get("name", "")
    sector = str(scored.get("sector", "") or "").strip()
    abnormal_state = _resolve_candidate_follow_state(scored)
    setup_id = _resolve_candidate_setup_id(scored)
    permission_label = str(scored.get("permission_label", "") or "").strip()
    signal = scored.get("signal")
    minute_plan = scored.get("minute_plan") or {}
    stop_plan = scored.get("stop_plan") or {}
    entry_range = scored.get("entry_range")
    tradability_guard = scored.get("tradability_guard") or {}

    if not entry_range and signal:
        entry_range = (signal.entry_price, signal.entry_price)

    is_mainline = bool(mainline_name and sector_name_matches(sector, mainline_name))
    is_conviction = code in conviction_codes
    is_memory = code in leader_memory_codes
    report_day_is_one_word = (
        _is_one_word_limit_bar(
            stock_code=code,
            stock_name=name,
            open_price=scored.get("open"),
            high_price=scored.get("high"),
            low_price=scored.get("low"),
            close_price=scored.get("close"),
            change_pct=scored.get("change"),
        )
        if code and name
        else False
    )

    execution_bias = str(state_machine_snapshot.get("execution_bias", "") or "").strip()
    if execution_bias == "allow_execute":
        environment_score = 100
    elif execution_bias == "divergence_only":
        environment_score = 76
    elif execution_bias == "prep_only":
        environment_score = 58
    elif execution_bias == "watch_only":
        environment_score = 28
    elif execution_bias == "reduce_only":
        environment_score = 16
    elif execution_bias == "avoid":
        environment_score = 0
    else:
        environment_score = 100 if final_gate and final_gate.get("can_new_entry") else 35 if final_gate else 50
    mainline_score = 100 if is_mainline else 55 if not mainline_name else 20
    memory_score = 100 if is_conviction else 82 if is_memory else 62 if is_mainline else 25
    trigger_score = _get_setup_priority_score(setup_id, abnormal_state)
    if not setup_id and not abnormal_state:
        trigger_score = 18

    washout_reclaim_chain = _build_washout_reclaim_context(
        scored,
        mainline_name=mainline_name,
        conviction_codes=conviction_codes,
        leader_memory_codes=leader_memory_codes,
        target_date=target_date,
    )
    if washout_reclaim_chain.get("active"):
        if washout_reclaim_chain.get("recognition_ok"):
            memory_score = max(memory_score, 82 if not is_conviction else 100)
        if washout_reclaim_chain.get("recognition_ok") and washout_reclaim_chain.get("within_3d_window"):
            trigger_score += 10
        elif washout_reclaim_chain.get("recognition_ok"):
            trigger_score += 2
        else:
            trigger_score = max(trigger_score - 10, 12)

    trend_continuation_chain = _build_trend_continuation_context(
        scored,
        mainline_name=mainline_name,
        conviction_codes=conviction_codes,
        leader_memory_codes=leader_memory_codes,
        target_date=target_date,
    )
    if trend_continuation_chain.get("active"):
        memory_score = max(memory_score, 88 if not is_conviction else 100)
        trigger_score += 8
    elif trend_continuation_chain.get("recognition_ok") and trend_continuation_chain.get("act_right"):
        trigger_score += 3

    tradability_score = 0
    if tradability_guard and not tradability_guard.get("can_trade", True):
        tradability_score = 0
    else:
        if entry_range and entry_range[0] is not None and entry_range[1] is not None:
            tradability_score += 35
        if minute_plan.get("confirm_price_60m"):
            tradability_score += 25
        if minute_plan.get("confirm_support_60m"):
            tradability_score += 5
        if (stop_plan.get("effective_stop") if stop_plan else None) or scored.get("stop_loss"):
            tradability_score += 20
        if permission_label and "执行权" in permission_label:
            tradability_score += 10
        if not report_day_is_one_word:
            tradability_score += 10
        tradability_score = min(tradability_score, 100)

    ev_score = _clamp(_safe_float(scored.get("ev_pct")) * 3000, 0, 100)
    scored["report_day_is_one_word"] = bool(report_day_is_one_word)
    scored["tradability_blocked"] = bool(tradability_guard and not tradability_guard.get("can_trade", True))
    scored["tradability_block_reason"] = tradability_guard.get("reason", "")
    scored["decision_stack"] = {
        "environment_score": environment_score,
        "mainline_score": mainline_score,
        "memory_score": memory_score,
        "trigger_score": trigger_score,
        "tradability_score": tradability_score,
        "ev_score": ev_score,
        "setup_priority_score": trigger_score,
        "setup_id": setup_id,
        "has_formal_abnormal_setup": _candidate_has_formal_abnormal_setup(scored),
        "is_resilient_abnormal": _candidate_is_resilient_abnormal(scored),
        "washout_reclaim_chain": washout_reclaim_chain,
        "trend_continuation_chain": trend_continuation_chain,
        "order_text": DECISION_STACK_ORDER_TEXT,
    }
    return scored


def _sort_decision_stack_candidates_legacy_body(candidates):
    return sorted(
        candidates or [],
        key=lambda item: (
            (item.get("decision_stack", {}) or {}).get("environment_score", 0),
            (item.get("decision_stack", {}) or {}).get("mainline_score", 0),
            (item.get("decision_stack", {}) or {}).get("memory_score", 0),
            (item.get("decision_stack", {}) or {}).get("trigger_score", 0),
            (item.get("decision_stack", {}) or {}).get("tradability_score", 0),
            _safe_float(item.get("composite_score")),
            _safe_float(item.get("ev")),
            _safe_float(item.get("tomorrow_strength")),
        ),
        reverse=True,
    )


def _get_abnormal_follow_risk_signal_legacy_body(stock):
    if _is_degraded_abnormal_snapshot(stock) or bool(stock.get("abnormal_is_degraded_snapshot")):
        return {
            "light": "🟠 橙灯",
            "delta": 8,
            "reason": "当前仅有降级异常快照，不能把它当正式承接证据",
            "forecast": "先补齐真实K线承接证据，再决定是否继续跟踪",
        }

    state = str(stock.get("abnormal_follow_state", "") or "").strip()
    abnormal_type = str(stock.get("abnormal_type", "") or "").strip()
    setup_label = str(stock.get("abnormal_setup_signal_label", "") or "").strip()
    signal_name = setup_label or abnormal_type or "异动"
    watch_source = str(stock.get("watch_source", "") or "").strip()

    if watch_source == "gem_breathing_20cm" or state == "预启动呼吸感":
        return {
            "light": "🟡 黄灯",
            "delta": -4,
            "reason": "创业板20cm预启动仍在收拢观察期，先确认它有没有走成右侧确认",
            "forecast": "先看右侧确认和60分钟确认，再决定是否升级到30%条件试错",
        }

    if not state:
        return {
            "light": "🟡 黄灯",
            "delta": 0,
            "reason": "无异动承接信息",
            "forecast": "",
        }

    if state == "跌不下去":
        return {
            "light": "🟢 绿灯",
            "delta": -12,
            "reason": f"{signal_name}承接强，暂未看到继续下杀",
            "forecast": "异动后承接强，明日重点等60分钟确认",
        }
    if state == "缩量消化":
        return {
            "light": "🟡 黄灯",
            "delta": -6,
            "reason": f"{signal_name}正在缩量消化，暂未失守锚点",
            "forecast": "正在缩量消化，明日先看能否再转强",
        }
    if state == "新异动待观察":
        return {
            "light": "🟠 橙灯",
            "delta": 6,
            "reason": f"{signal_name}刚出现，承接尚未被验证",
            "forecast": "异动刚出现，明日先看承接，不宜直接乐观",
        }
    return {
        "light": "🔴 红灯",
        "delta": 22,
        "reason": f"{signal_name}已经转弱，承接明显不够",
        "forecast": "异动后承接转弱，明日易低开或继续下杀",
    }


def build_abnormal_probe_group(style_switch_snapshot=None, abnormal_watch_pool=None, mainline_name="", watch_anchor=None, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _build_abnormal_probe_group_legacy_body(
            style_switch_snapshot=style_switch_snapshot,
            abnormal_watch_pool=abnormal_watch_pool,
            mainline_name=mainline_name,
            watch_anchor=watch_anchor,
        )
    finally:
        _restore_runtime_bindings(previous)


def build_abnormal_watch_anchor_candidates(
    abnormal_watch_pool=None,
    existing_candidates=None,
    seed_candidates=None,
    target_date="",
    mainline_name="",
    final_gate=None,
    conviction_codes=None,
    leader_memory_codes=None,
    ev_calibration=None,
    state_machine_snapshot=None,
    *,
    helpers=None,
):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _build_abnormal_watch_anchor_candidates_legacy_body(
            abnormal_watch_pool=abnormal_watch_pool,
            existing_candidates=existing_candidates,
            seed_candidates=seed_candidates,
            target_date=target_date,
            mainline_name=mainline_name,
            final_gate=final_gate,
            conviction_codes=conviction_codes,
            leader_memory_codes=leader_memory_codes,
            ev_calibration=ev_calibration,
            state_machine_snapshot=state_machine_snapshot,
        )
    finally:
        _restore_runtime_bindings(previous)


def format_abnormal_probe_text(probe, role_label="", mainline_name="", fallback_watch_anchor=None, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _format_abnormal_probe_text_legacy_body(
            probe,
            role_label=role_label,
            mainline_name=mainline_name,
            fallback_watch_anchor=fallback_watch_anchor,
        )
    finally:
        _restore_runtime_bindings(previous)


def build_mainline_upgrade_probe_context(candidate=None, mainline_name="", target_date="", *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _build_mainline_upgrade_probe_context_legacy_body(
            candidate=candidate,
            mainline_name=mainline_name,
            target_date=target_date,
        )
    finally:
        _restore_runtime_bindings(previous)


def build_special_probe_verdict(abnormal_probe_group=None, watch_anchor=None, watch_anchor_type="", mainline_name="", target_date="", *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _build_special_probe_verdict_legacy_body(
            abnormal_probe_group=abnormal_probe_group,
            watch_anchor=watch_anchor,
            watch_anchor_type=watch_anchor_type,
            mainline_name=mainline_name,
            target_date=target_date,
        )
    finally:
        _restore_runtime_bindings(previous)


def build_special_probe_focus_text(abnormal_probe_group=None, watch_anchor=None, watch_anchor_type="", mainline_name="", target_date="", *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _build_special_probe_focus_text_legacy_body(
            abnormal_probe_group=abnormal_probe_group,
            watch_anchor=watch_anchor,
            watch_anchor_type=watch_anchor_type,
            mainline_name=mainline_name,
            target_date=target_date,
        )
    finally:
        _restore_runtime_bindings(previous)


def _build_abnormal_probe_group_legacy_body(
    style_switch_snapshot=None,
    abnormal_watch_pool=None,
    mainline_name="",
    watch_anchor=None,
):
    style_switch_snapshot = style_switch_snapshot or {}
    abnormal_watch_pool, degraded_pool = _split_abnormal_watch_pool(abnormal_watch_pool)
    formal_pool = [item for item in (abnormal_watch_pool or []) if not _is_degraded_abnormal_snapshot(item)]
    if not formal_pool:
        return {}

    mainline_name = str(mainline_name or "").strip()
    follow_state_rank = {
        "跌不下去": 4,
        "缩量消化": 3,
        "新异动待观察": 2,
        "已经转弱": 1,
    }

    def abnormal_sort_key(item):
        follow_state = str(item.get("follow_state", "") or "").strip()
        sector_name = str(item.get("sector", "") or "").strip()
        return (
            follow_state_rank.get(follow_state, 0),
            1 if sector_name and sector_name != "未知" else 0,
            1 if item.get("is_mainline") or _candidate_matches_mainline(item, mainline_name) else 0,
            _safe_float(item.get("abnormal_score", 0)),
            item.get("abnormal_date", ""),
        )

    sorted_pool = sorted(formal_pool, key=abnormal_sort_key, reverse=True)
    resilient_pool = [
        item for item in sorted_pool
        if str(item.get("follow_state", "") or "").strip() in ("跌不下去", "缩量消化")
    ]
    mainline_pool = [
        item for item in sorted_pool
        if item.get("is_mainline") or _candidate_matches_mainline(item, mainline_name)
    ]
    crossline_pool = [item for item in sorted_pool if item not in mainline_pool]

    selected_codes = {
        normalize_stock_code((mainline_pool[0] if mainline_pool else {}).get("code", "")),
        normalize_stock_code((crossline_pool[0] if crossline_pool else {}).get("code", "")),
    }
    validation_probe = None
    for item in resilient_pool or sorted_pool:
        code = normalize_stock_code(item.get("code", ""))
        if code and code in selected_codes:
            continue
        validation_probe = item
        break
    if not validation_probe:
        validation_probe = resilient_pool[0] if resilient_pool else (sorted_pool[0] if sorted_pool else None)

    return {
        "style_code": style_switch_snapshot.get("style_code", ""),
        "style_label": style_switch_snapshot.get("style_label", ""),
        "mainline_abnormal_probe": mainline_pool[0] if mainline_pool else None,
        "crossline_abnormal_probe": crossline_pool[0] if crossline_pool else None,
        "validation_probe": validation_probe,
        "fallback_watch_anchor": watch_anchor or {},
        "mainline_missing_reason": f"{mainline_name}方向今天没有进入异常库的放量异常" if mainline_name and not mainline_pool else "",
        "pool_size": len(sorted_pool),
        "degraded_count": len(degraded_pool),
    }


def _build_abnormal_watch_anchor_candidates_legacy_body(
    abnormal_watch_pool=None,
    existing_candidates=None,
    seed_candidates=None,
    target_date="",
    mainline_name="",
    final_gate=None,
    conviction_codes=None,
    leader_memory_codes=None,
    ev_calibration=None,
    state_machine_snapshot=None,
):
    abnormal_watch_pool, _ = _split_abnormal_watch_pool(abnormal_watch_pool)
    state_machine_snapshot = state_machine_snapshot or {}
    if not abnormal_watch_pool:
        return []

    candidate_lookup = {}
    for item in existing_candidates or []:
        code = normalize_stock_code((item or {}).get("code", ""))
        if code and code not in candidate_lookup:
            candidate_lookup[code] = dict(item or {})

    seed_lookup = {}
    for item in seed_candidates or []:
        code = normalize_stock_code((item or {}).get("code", ""))
        if code and code not in seed_lookup:
            seed_lookup[code] = dict(item or {})

    prepared = []
    seen_codes = set()
    for abnormal_item in abnormal_watch_pool or []:
        code = normalize_stock_code(abnormal_item.get("code", ""))
        if not code or code in seen_codes:
            continue
        seen_codes.add(code)

        if candidate_lookup.get(code):
            candidate = dict(candidate_lookup[code] or {})
        else:
            seed = dict(seed_lookup.get(code, {}) or {})
            entry_price = _safe_float(
                seed.get("close")
                or seed.get("price")
                or abnormal_item.get("anchor_price")
            )
            if entry_price <= 0:
                continue

            recent_bars = fetch_recent_price_bars(code, target_date, lookback_days=4)
            daily_anchor_bars = fetch_recent_price_bars(
                code,
                target_date,
                lookback_days=10,
            )
            tradability_guard = evaluate_live_tradability(
                {
                    **seed,
                    "code": code,
                    "name": abnormal_item.get("name", seed.get("name", "")),
                    "close": entry_price,
                },
                target_date,
                recent_bars=recent_bars,
            )
            candidate = build_waiting_stock_plan(
                {
                    **seed,
                    "name": abnormal_item.get("name", seed.get("name", "未知")),
                    "code": code,
                    "sector": seed.get("sector") or abnormal_item.get("sector", ""),
                    "close": entry_price,
                    "entry_price": entry_price,
                    "condition": abnormal_item.get("action_rule") or "只跟踪异常承接，不直接下单",
                    "tradability_guard": tradability_guard,
                    "report_day_is_one_word": tradability_guard.get("report_day_is_one_word", False),
                },
                target_date,
                reason=abnormal_item.get("action_rule") or "只跟踪异常承接，不直接下单",
                signal_type=_map_setup_id_to_signal_type(abnormal_item.get("setup_signal_id", "")),
                recent_bars=daily_anchor_bars,
            )
            candidate.update(
                {
                    "permission_label": "异常观察权",
                    "permission_reason": "当前只跟踪异常承接，不自动授予执行权",
                    "tradability_guard": tradability_guard,
                    "report_day_is_one_word": tradability_guard.get("report_day_is_one_word", False),
                }
            )

        candidate.update(
            {
                "name": abnormal_item.get("name", candidate.get("name", "未知")),
                "code": code,
                "sector": candidate.get("sector") or abnormal_item.get("sector", ""),
                "abnormal_date": abnormal_item.get("abnormal_date", ""),
                "abnormal_type": abnormal_item.get("abnormal_type", ""),
                "abnormal_follow_state": abnormal_item.get("follow_state", candidate.get("abnormal_follow_state", "")),
                "abnormal_setup_signal_id": abnormal_item.get("setup_signal_id", candidate.get("abnormal_setup_signal_id", "")),
                "abnormal_setup_signal_label": abnormal_item.get("setup_signal_label", candidate.get("abnormal_setup_signal_label", "")),
                "abnormal_setup_signal_phase": abnormal_item.get("setup_signal_phase", candidate.get("abnormal_setup_signal_phase", "")),
                "abnormal_score": abnormal_item.get("abnormal_score", candidate.get("abnormal_score", 0)),
                "anchor_price": abnormal_item.get("anchor_price", candidate.get("anchor_price")),
                "display_anchor_price": abnormal_item.get("display_anchor_price", candidate.get("display_anchor_price")),
                "is_mainline": bool(abnormal_item.get("is_mainline")),
                "action_rule": abnormal_item.get("action_rule") or candidate.get("action_rule") or "",
                "reason": abnormal_item.get("action_rule") or candidate.get("reason") or "",
                "watch_source": "abnormal_probe",
            }
        )
        minute_plan = dict(candidate.get("minute_plan", {}) or {})
        if abnormal_item.get("confirm_price_60m") is not None:
            minute_plan["confirm_price_60m"] = abnormal_item.get("confirm_price_60m")
        if abnormal_item.get("confirm_support_60m") is not None:
            minute_plan["confirm_support_60m"] = abnormal_item.get("confirm_support_60m")
        if abnormal_item.get("structure_stop_30m") is not None:
            minute_plan["structure_stop_30m"] = abnormal_item.get("structure_stop_30m")
        if abnormal_item.get("confirm_rule_60m"):
            minute_plan["confirm_rule_60m"] = abnormal_item.get("confirm_rule_60m")
        if minute_plan:
            candidate["minute_plan"] = minute_plan

        risk_signal = get_abnormal_follow_risk_signal(candidate)
        candidate.setdefault("abnormal_light", risk_signal.get("light", ""))
        candidate.setdefault(
            "risk_level",
            _infer_risk_level_from_abnormal_follow_state(candidate.get("abnormal_follow_state", "")),
        )
        if not candidate.get("raw_risk_score"):
            candidate["raw_risk_score"] = 18 if _candidate_is_resilient_abnormal(candidate) else 8
        if _candidate_is_resilient_abnormal(candidate) and not candidate.get("repair_buffers"):
            candidate["repair_buffers"] = ["异常承接未坏"]

        if not candidate.get("decision_stack"):
            candidate = score_candidate_decision_stack(
                score_execution_candidate(candidate, ev_calibration or {}),
                final_gate=final_gate,
                mainline_name=mainline_name,
                conviction_codes=conviction_codes,
                leader_memory_codes=leader_memory_codes,
                state_machine_snapshot=state_machine_snapshot,
                target_date=target_date,
            )

        prepared.append(candidate)

    return sort_watch_anchor_candidates(
        prepared,
        mainline_name=mainline_name,
        state_machine_snapshot=state_machine_snapshot,
    )


def _format_abnormal_probe_text_legacy_body(
    probe,
    role_label="",
    mainline_name="",
    fallback_watch_anchor=None,
):
    fallback_watch_anchor = fallback_watch_anchor or {}
    if not probe:
        if role_label == "主线异动里先看谁":
            fallback_name = fallback_watch_anchor.get("name")
            fallback_code = fallback_watch_anchor.get("code")
            if fallback_name:
                fallback_text = f"{fallback_name}({fallback_code})" if fallback_code else fallback_name
                fallback_is_mainline = not mainline_name or _candidate_matches_mainline(fallback_watch_anchor, mainline_name)
                fallback_is_abnormal = bool(
                    fallback_watch_anchor.get("abnormal_setup_signal_id")
                    or fallback_watch_anchor.get("setup_signal_id")
                    or fallback_watch_anchor.get("abnormal_type")
                )
                if mainline_name:
                    if fallback_is_mainline and fallback_is_abnormal:
                        return f"暂无，{mainline_name}方向今天没有进入异常库的放量异常；主线暂只保留异常承接观察{fallback_text}"
                    if fallback_is_mainline:
                        return f"暂无，{mainline_name}方向今天没有进入异常库的放量异常；主线只保留普通盯盘股{fallback_text}"
                    if fallback_is_abnormal:
                        return f"暂无，{mainline_name}方向今天没有进入异常库的放量异常；当前只保留跨线异常观察{fallback_text}"
                    return f"暂无，{mainline_name}方向今天没有进入异常库的放量异常"
                return f"暂无，当前只保留普通盯盘股{fallback_text}"
            if mainline_name:
                return f"暂无，{mainline_name}方向今天没有进入异常库的放量异常"
            return "暂无，当前没有进入异常库的主线放量异常"
        return ""

    name = probe.get("name", "-")
    code = probe.get("code", "-")
    setup_label = probe.get("setup_signal_label", probe.get("abnormal_type", "异常")) or "异常"
    follow_state = probe.get("follow_state", "-") or "-"
    action_rule = str(probe.get("action_rule", "") or "").strip()
    watch_anchor_note = str(probe.get("watch_anchor_note", "") or "").strip()
    if not watch_anchor_note and role_label == "跨线异动里先看谁" and mainline_name and not (probe.get("is_mainline") or _candidate_matches_mainline(probe, mainline_name)):
        sector = str(probe.get("sector", "") or "").strip()
        if sector:
            watch_anchor_note = f"跨线对象（{sector}），只用于观察强弱，不代表主攻线从{mainline_name}切换"
        else:
            watch_anchor_note = f"跨线对象，只用于观察强弱，不代表主攻线从{mainline_name}切换"

    text = f"{name}({code})，{setup_label} / {follow_state}"
    if action_rule:
        text += f"，{action_rule}"
    if watch_anchor_note:
        text += f"；{watch_anchor_note}"
    return text


def _build_mainline_upgrade_probe_context_legacy_body(candidate=None, mainline_name="", target_date=""):
    candidate = candidate or {}
    mainline_name = str(mainline_name or "").strip()
    follow_state = str(candidate.get("follow_state", "") or candidate.get("abnormal_follow_state", "") or "").strip()
    watch_anchor_type = str(candidate.get("watch_anchor_type", "") or "").strip()
    decision_stack = candidate.get("decision_stack", {}) or {}
    washout_chain = decision_stack.get("washout_reclaim_chain", {}) or {}
    trend_chain = decision_stack.get("trend_continuation_chain", {}) or {}
    strong_setup = bool(candidate.get("abnormal_setup_signal_id")) or _safe_float(decision_stack.get("trigger_score", 0)) >= 80
    is_mainline = bool(candidate.get("is_mainline")) or _candidate_matches_mainline(candidate, mainline_name) or ("主线" in watch_anchor_type and "跨线" not in watch_anchor_type)
    feedback_clock = _build_candidate_feedback_clock(
        candidate=candidate,
        watch_anchor_type=watch_anchor_type,
        state_machine_snapshot={"leading_line": mainline_name},
        mainline_name=mainline_name,
        target_date=target_date,
    )
    active = bool(is_mainline and follow_state in ("跌不下去", "缩量消化") and strong_setup)
    history_continuity = int(_safe_float((feedback_clock.get("history_feedback", {}) or {}).get("continuous_days", 0)))
    upgrade_ready = bool(
        active
        and feedback_clock.get("ready")
        and (
            trend_chain.get("active")
            or (washout_chain.get("active") and washout_chain.get("recognition_ok") and washout_chain.get("within_3d_window"))
            or history_continuity >= 2
        )
    )
    if upgrade_ready:
        probe_state = "probe_mainline_upgrade_ready"
        note = "主线探针已具备升级条件：承接未坏、确认链完整，且已出现连续反馈/主线修复证据。"
        action = "保留主线可升级探针；若次日继续 act right，可进入30%条件试错观察。"
    elif active:
        probe_state = "probe_resilient_hold"
        note = "主线探针仍在观察阶段：承接未坏，但升级证据还不够。"
        action = "继续盯主线探针能否给出连续反馈，再决定是否升级。"
    else:
        probe_state = "probe_flow_unconfirmed"
        note = "主线探针尚未形成可升级条件。"
        action = "先观察主线探针是否抗跌，不提前升级。"

    return {
        "active": active,
        "is_mainline": is_mainline,
        "upgrade_ready": upgrade_ready,
        "probe_state": probe_state,
        "allows_conditional_30": upgrade_ready,
        "allows_execute_50": False,
        "note": note,
        "action": action,
        "feedback_clock": feedback_clock,
    }


def _build_special_probe_verdict_legacy_body(
    abnormal_probe_group=None,
    watch_anchor=None,
    watch_anchor_type="",
    mainline_name="",
    target_date="",
):
    abnormal_probe_group = abnormal_probe_group or {}
    watch_anchor = watch_anchor or {}
    watch_anchor_type = str(watch_anchor_type or "").strip()
    mainline_name = str(mainline_name or "").strip()
    if "执行候选观察锚点" in watch_anchor_type:
        return {
            "code": "no_probe",
            "label": "特殊探针",
            "summary_text": "",
            "action": "",
            "probe_candidate": {},
            "probe_state": "no_probe",
            "allows_conditional_30": False,
            "allows_execute_50": False,
        }

    mainline_probe = abnormal_probe_group.get("mainline_abnormal_probe") or {}
    crossline_probe = abnormal_probe_group.get("crossline_abnormal_probe") or {}
    validation_probe = abnormal_probe_group.get("validation_probe") or {}
    fallback_watch_anchor = abnormal_probe_group.get("fallback_watch_anchor") or watch_anchor or {}

    def _probe_contract(probe=None, default_state="probe_flow_unconfirmed"):
        probe = probe or {}
        follow_state = str(probe.get("follow_state", "") or probe.get("abnormal_follow_state", "") or "").strip()
        note_text = str(probe.get("watch_anchor_note", "") or "").strip()
        if follow_state == "已经转弱":
            probe_state = "probe_deep_fall"
        elif "外溢确认阶段" in note_text or "外溢继续扩大" in note_text or "跨线外溢确认" in watch_anchor_type:
            probe_state = "probe_flow_confirmed"
        elif follow_state in ("跌不下去", "缩量消化"):
            probe_state = "probe_resilient_hold" if "主线" in watch_anchor_type and "跨线" not in watch_anchor_type else default_state
        else:
            probe_state = default_state
        return probe_state, probe_state == "probe_flow_confirmed", probe_state == "probe_mainline_confirmed"

    if crossline_probe:
        note = str(crossline_probe.get("watch_anchor_note", "") or _derive_watch_anchor_note(crossline_probe, mainline_name)).strip()
        if "不代表主攻线从" in note and "切换" in note:
            prefix, suffix = note.split("不代表主攻线从", 1)
            suffix = suffix.split("切换", 1)[1] if "切换" in suffix else suffix
            note = f"{prefix}不代表主攻线切换{suffix}"
        name = crossline_probe.get("name", "-")
        code = crossline_probe.get("code", "-")
        probe_state, allows_conditional_30, allows_execute_50 = _probe_contract(crossline_probe, default_state="probe_flow_unconfirmed")
        crossline_feedback = _build_candidate_feedback_clock(
            candidate=crossline_probe,
            watch_anchor_type=watch_anchor_type,
            state_machine_snapshot={"leading_line": mainline_name},
            mainline_name=mainline_name,
            target_date=target_date,
        )
        history_days = int(_safe_float((crossline_feedback.get("history_feedback", {}) or {}).get("continuous_days", 0)))
        crossline_upgrade_ready = bool(
            _requires_crossline_second_confirmation(crossline_probe, mainline_name)
            and crossline_feedback.get("ready")
            and crossline_feedback.get("has_confirmation_chain")
            and history_days >= 2
            and probe_state != "probe_deep_fall"
        )
        if crossline_upgrade_ready:
            return {
                "code": "crossline_probe_upgrade_ready",
                "label": "跨线可升级探针",
                "summary_text": f"{name}({code}) 虽然仍属跨线对象，但已经先 act right：承接未坏、确认链完整，且连续反馈已出现，只允许升级到30%条件试错，不直接当成主攻线切换。",
                "action": "先按跨线可升级探针对待；若继续 act right，只允许30%条件试错，不直接放到50%执行。",
                "probe_candidate": crossline_probe,
                "probe_state": "probe_crossline_upgrade_ready",
                "allows_conditional_30": True,
                "allows_execute_50": False,
            }
        return {
            "code": "crossline_probe_only",
            "label": "跨线特殊探针",
            "summary_text": f"{name}({code}) 只是跨线市场探针，{note or '只观察跨线强弱，不代表主攻线切换'}",
            "action": "只观察跨线强弱和资金外溢，不升级执行权",
            "probe_candidate": crossline_probe,
            "probe_state": probe_state,
            "allows_conditional_30": allows_conditional_30,
            "allows_execute_50": allows_execute_50,
        }

    if mainline_probe:
        name = mainline_probe.get("name", "-")
        code = mainline_probe.get("code", "-")
        follow_state = str(mainline_probe.get("follow_state", "") or "").strip() or "待观察"
        upgrade_probe_context = build_mainline_upgrade_probe_context(
            mainline_probe,
            mainline_name=mainline_name,
            target_date=target_date,
        )
        if upgrade_probe_context.get("upgrade_ready"):
            return {
                "code": "mainline_probe_upgrade_ready",
                "label": "主线可升级探针",
                "summary_text": f"{name}({code}) 已被识别成主线可升级探针：承接未坏、确认链完整，且出现连续反馈/修复证据，若次日继续 act right，才允许升级到30%条件试错。",
                "action": "先盯主线可升级探针是否继续证明自己；若次日继续 act right，再考虑30%条件试错，不直接给50%执行。",
                "probe_candidate": mainline_probe,
                "probe_state": upgrade_probe_context.get("probe_state"),
                "allows_conditional_30": bool(upgrade_probe_context.get("allows_conditional_30")),
                "allows_execute_50": False,
            }
        probe_state, allows_conditional_30, allows_execute_50 = _probe_contract(mainline_probe, default_state="probe_resilient_hold")
        return {
            "code": "mainline_probe_watch",
            "label": "主线特殊探针",
            "summary_text": f"{name}({code}) 是主线特殊探针，当前处于{follow_state}；若它也跌下去，这轮修复继续收，若它抗跌才保留后续升级预期",
            "action": "先盯主线特殊标的能不能跌下去，再决定观察权是否保留",
            "probe_candidate": mainline_probe,
            "probe_state": probe_state,
            "allows_conditional_30": allows_conditional_30,
            "allows_execute_50": allows_execute_50,
        }

    if validation_probe:
        name = validation_probe.get("name", "-")
        code = validation_probe.get("code", "-")
        probe_state, allows_conditional_30, allows_execute_50 = _probe_contract(validation_probe, default_state="probe_resilient_hold")
        return {
            "code": "validation_probe_watch",
            "label": "承接验证探针",
            "summary_text": f"{name}({code}) 用来验证这轮调整是良性承接还是继续转弱",
            "action": "先看验证探针是否抗跌，再决定是否保留观察权",
            "probe_candidate": validation_probe,
            "probe_state": probe_state,
            "allows_conditional_30": allows_conditional_30,
            "allows_execute_50": allows_execute_50,
        }

    if fallback_watch_anchor:
        name = fallback_watch_anchor.get("name", "-")
        code = fallback_watch_anchor.get("code", "-")
        probe_state, allows_conditional_30, allows_execute_50 = _probe_contract(fallback_watch_anchor, default_state="probe_flow_unconfirmed")
        return {
            "code": "fallback_probe_watch",
            "label": "特殊探针",
            "summary_text": f"{name}({code}) 先看它是深跌还是抗跌，再决定这轮调整是继续收还是重新攻",
            "action": "先观察这个特殊对象对调整的反馈，不直接升级执行权",
            "probe_candidate": fallback_watch_anchor,
            "probe_state": probe_state,
            "allows_conditional_30": allows_conditional_30,
            "allows_execute_50": allows_execute_50,
        }

    return {
        "code": "no_probe",
        "label": "特殊探针",
        "summary_text": "当前没有明确特殊探针，只保留普通观察。",
        "action": "先观察市场整体，不提前放松执行权",
        "probe_candidate": {},
        "probe_state": "no_probe",
        "allows_conditional_30": False,
        "allows_execute_50": False,
    }


def _build_special_probe_focus_text_legacy_body(
    abnormal_probe_group=None,
    watch_anchor=None,
    watch_anchor_type="",
    mainline_name="",
    target_date="",
):
    abnormal_probe_group = abnormal_probe_group or {}
    watch_anchor = watch_anchor or {}
    fallback_watch_anchor = abnormal_probe_group.get("fallback_watch_anchor") or watch_anchor or {}
    special_probe_verdict = build_special_probe_verdict(
        abnormal_probe_group=abnormal_probe_group,
        watch_anchor=watch_anchor,
        watch_anchor_type=watch_anchor_type,
        mainline_name=mainline_name,
        target_date=target_date,
    )
    if "执行候选观察锚点" in str(watch_anchor_type or ""):
        return ""
    if special_probe_verdict.get("code") == "crossline_probe_upgrade_ready":
        probe_candidate = special_probe_verdict.get("probe_candidate") or {}
        name = probe_candidate.get("name", "-")
        code = probe_candidate.get("code", "-")
        return f"{name}({code})，跨线可升级探针：已经先 act right，只允许30%条件试错，不直接当成主攻线切换"

    probe_specs = [
        ("mainline_abnormal_probe", "主线异动里先看谁"),
        ("crossline_abnormal_probe", "跨线异动里先看谁"),
        ("validation_probe", "承接验证先看谁"),
    ]
    for probe_key, role_label in probe_specs:
        text = str(
            format_abnormal_probe_text(
                abnormal_probe_group.get(probe_key),
                role_label=role_label,
                mainline_name=mainline_name,
                fallback_watch_anchor=fallback_watch_anchor if role_label == "主线异动里先看谁" else None,
            )
            or ""
        ).strip()
        if text and not text.startswith("暂无"):
            return text

    if fallback_watch_anchor:
        name = fallback_watch_anchor.get("name", "-")
        code = fallback_watch_anchor.get("code", "-")
        note = str(fallback_watch_anchor.get("watch_anchor_note", "") or "").strip()
        action_rule = str(fallback_watch_anchor.get("action_rule", "") or "").strip()
        text = f"{name}({code})，先看它是深跌还是抗跌，再决定这轮调整是继续收还是重新攻"
        if action_rule:
            text += f"；{action_rule}"
        if note:
            text += f"；{note}"
        return text
    return ""
