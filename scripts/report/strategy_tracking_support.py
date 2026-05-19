from __future__ import annotations

import datetime

import daily_report_analysis_utils as analysis_utils
from daily_report_snapshot_io import LEDGER_MODE_FROZEN
from market_data.daily_price_runtime import (
    count_trading_days_between as _default_count_trading_days_between,
    fetch_daily_price_bars as _default_fetch_daily_price_bars,
    get_first_bar_on_or_after as _default_get_first_bar_on_or_after,
    is_next_trading_day as _default_is_next_trading_day,
)
from market_data.kline_dates import normalize_kline_date_str as _default_normalize_kline_date_str
from market_data.kline_dates import parse_kline_date as _default_parse_kline_date
from report.strategy_tracking_store import load_strategy_performance_ledger as _default_load_strategy_performance_ledger
from selection.candidate_execution_contracts import (
    DEFENSIVE_EXIT_RULE_TEXT,
    PROFIT_EXIT_RULE_TEXT,
    STRATEGY_HOLDING_DAYS_MAX,
    STRATEGY_HOLDING_DAYS_MIN,
    resolve_candidate_follow_state as _default_resolve_candidate_follow_state,
)

__all__ = [
    "backfill_strategy_record_market_context",
    "build_trade_return_stats",
    "build_candidate_feedback_clock",
    "build_candidate_history_feedback",
    "candidate_confirmation_chain",
    "compound_returns",
    "extract_candidate_report_prices",
    "format_pct",
    "format_pct_range",
    "get_plan_action_label",
    "get_run_mode_label",
    "get_signal_type_label",
    "get_strategy_status_label",
    "iter_record_probe_candidates",
    "resolve_probe_role_family",
    "summarize_ev_signal_review",
]

_MISSING = object()

EV_SIGNAL_TYPE_PRIORS = {
    "sweet_zone": {
        "win_rate": 0.53,
        "avg_win_pct": 0.085,
        "avg_loss_pct": 0.034,
        "prior_weight": 8.0,
        "label": "甜品区",
    },
    "breakout": {
        "win_rate": 0.49,
        "avg_win_pct": 0.078,
        "avg_loss_pct": 0.039,
        "prior_weight": 8.0,
        "label": "突破",
    },
    "panic_buy": {
        "win_rate": 0.44,
        "avg_win_pct": 0.118,
        "avg_loss_pct": 0.046,
        "prior_weight": 8.0,
        "label": "恐慌盘",
    },
    "base": {
        "win_rate": 0.50,
        "avg_win_pct": 0.080,
        "avg_loss_pct": 0.040,
        "prior_weight": 10.0,
        "label": "基础",
    },
}


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


def normalize_stock_code(code):
    return analysis_utils.normalize_stock_code(code)


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


def _candidate_matches_mainline(candidate, mainline_name=""):
    return analysis_utils._candidate_matches_mainline(candidate, mainline_name)


def _resolve_candidate_follow_state(candidate=None):
    return _default_resolve_candidate_follow_state(candidate or {})


def _normalize_kline_date_str(value):
    return _default_normalize_kline_date_str(value)


def _parse_kline_date(value):
    return _default_parse_kline_date(value)


def fetch_daily_price_bars(security_code, start_date, end_date, is_index=False):
    return _default_fetch_daily_price_bars(
        security_code,
        start_date,
        end_date,
        is_index=is_index,
    )


def _get_first_bar_on_or_after(bars, target_date):
    return _default_get_first_bar_on_or_after(bars, target_date)


def load_strategy_performance_ledger(*, mode=LEDGER_MODE_FROZEN):
    return _default_load_strategy_performance_ledger(mode=mode)


def _is_next_trading_day(prev_date, curr_date):
    return _default_is_next_trading_day(prev_date, curr_date)


def _count_trading_days_between(start_date, end_date):
    return _default_count_trading_days_between(start_date, end_date)


def compound_returns(values, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _compound_returns_legacy_body(values)
    finally:
        _restore_runtime_bindings(previous)


def get_strategy_status_label(status, note="", *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _get_strategy_status_label_legacy_body(status, note=note)
    finally:
        _restore_runtime_bindings(previous)


def get_plan_action_label(action_type, position_pct=None, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _get_plan_action_label_legacy_body(action_type, position_pct=position_pct)
    finally:
        _restore_runtime_bindings(previous)


def get_signal_type_label(signal_type, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _get_signal_type_label_legacy_body(signal_type)
    finally:
        _restore_runtime_bindings(previous)


def backfill_strategy_record_market_context(record, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _backfill_strategy_record_market_context_legacy_body(record)
    finally:
        _restore_runtime_bindings(previous)


def build_trade_return_stats(records, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _build_trade_return_stats_legacy_body(records)
    finally:
        _restore_runtime_bindings(previous)


def summarize_ev_signal_review(records, start_date, end_date, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _summarize_ev_signal_review_legacy_body(records, start_date, end_date)
    finally:
        _restore_runtime_bindings(previous)


def candidate_confirmation_chain(candidate=None, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _candidate_confirmation_chain_legacy_body(candidate)
    finally:
        _restore_runtime_bindings(previous)


def resolve_probe_role_family(probe_role="", watch_anchor_type="", anchor_type="", *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _resolve_probe_role_family_legacy_body(
            probe_role=probe_role,
            watch_anchor_type=watch_anchor_type,
            anchor_type=anchor_type,
        )
    finally:
        _restore_runtime_bindings(previous)


def iter_record_probe_candidates(record, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _iter_record_probe_candidates_legacy_body(record)
    finally:
        _restore_runtime_bindings(previous)


def build_candidate_history_feedback(candidate=None, target_date="", probe_role="", watch_anchor_type="", *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _build_candidate_history_feedback_legacy_body(
            candidate=candidate,
            target_date=target_date,
            probe_role=probe_role,
            watch_anchor_type=watch_anchor_type,
        )
    finally:
        _restore_runtime_bindings(previous)


def extract_candidate_report_prices(candidate=None, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _extract_candidate_report_prices_legacy_body(candidate)
    finally:
        _restore_runtime_bindings(previous)


def build_candidate_feedback_clock(
    candidate=None,
    watch_anchor_type="",
    state_machine_snapshot=None,
    mainline_name="",
    target_date="",
    *,
    helpers=None,
):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _build_candidate_feedback_clock_legacy_body(
            candidate=candidate,
            watch_anchor_type=watch_anchor_type,
            state_machine_snapshot=state_machine_snapshot,
            mainline_name=mainline_name,
            target_date=target_date,
        )
    finally:
        _restore_runtime_bindings(previous)


def format_pct(value, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _format_pct_legacy_body(value)
    finally:
        _restore_runtime_bindings(previous)


def format_pct_range(low_value, high_value, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _format_pct_range_legacy_body(low_value, high_value)
    finally:
        _restore_runtime_bindings(previous)


def get_run_mode_label(mode, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _get_run_mode_label_legacy_body(mode)
    finally:
        _restore_runtime_bindings(previous)


def _compound_returns(values):
    return _compound_returns_legacy_body(values)


def _get_strategy_status_label(status, note=""):
    return _get_strategy_status_label_legacy_body(status, note=note)


def _get_plan_action_label(action_type, position_pct=None):
    return _get_plan_action_label_legacy_body(action_type, position_pct=position_pct)


def _get_signal_type_label(signal_type):
    return _get_signal_type_label_legacy_body(signal_type)


def _backfill_strategy_record_market_context(record):
    return _backfill_strategy_record_market_context_legacy_body(record)


def _build_trade_return_stats(records):
    return _build_trade_return_stats_legacy_body(records)


def _summarize_ev_signal_review(records, start_date, end_date):
    return _summarize_ev_signal_review_legacy_body(records, start_date, end_date)


def _candidate_confirmation_chain(candidate=None):
    return _candidate_confirmation_chain_legacy_body(candidate)


def _resolve_probe_role_family(probe_role="", watch_anchor_type="", anchor_type=""):
    return _resolve_probe_role_family_legacy_body(
        probe_role=probe_role,
        watch_anchor_type=watch_anchor_type,
        anchor_type=anchor_type,
    )


def _iter_record_probe_candidates(record):
    return _iter_record_probe_candidates_legacy_body(record)


def _build_candidate_history_feedback(candidate=None, target_date="", probe_role="", watch_anchor_type=""):
    return _build_candidate_history_feedback_legacy_body(
        candidate=candidate,
        target_date=target_date,
        probe_role=probe_role,
        watch_anchor_type=watch_anchor_type,
    )


def _extract_candidate_report_prices(candidate=None):
    return _extract_candidate_report_prices_legacy_body(candidate)


def _build_candidate_feedback_clock(
    candidate=None,
    watch_anchor_type="",
    state_machine_snapshot=None,
    mainline_name="",
    target_date="",
):
    return _build_candidate_feedback_clock_legacy_body(
        candidate=candidate,
        watch_anchor_type=watch_anchor_type,
        state_machine_snapshot=state_machine_snapshot,
        mainline_name=mainline_name,
        target_date=target_date,
    )


def _format_pct(value):
    return _format_pct_legacy_body(value)


def _format_pct_range(low_value, high_value):
    return _format_pct_range_legacy_body(low_value, high_value)


def _get_run_mode_label(mode):
    return _get_run_mode_label_legacy_body(mode)


def _compound_returns_legacy_body(values):
    nav = 1.0
    for value in values or []:
        nav *= (1.0 + _safe_float(value, 0.0))
    return nav - 1.0


def _get_strategy_status_label_legacy_body(status, note=""):
    label_map = {
        "pending": "待评估",
        "invalid": "无效计划",
        "watch_only": "仅观察",
        "no_trade": "无交易",
        "not_triggered": "未触发",
        "closed": "已平仓",
        "open_mark_to_market": "持仓中",
        "continuation_only": "延续持有",
        "invalid_report_day_one_word": "无效：当日一字",
        "invalid_consecutive_one_word": "无效：连续一字",
    }
    base = label_map.get(status, status or "-")
    if note:
        return f"{base}（{note}）"
    return base


def _get_plan_action_label_legacy_body(action_type, position_pct=None):
    action_type = action_type or ""
    position_pct = int(_safe_float(position_pct, 0)) if position_pct is not None else None
    if action_type == "execute" and position_pct == 30:
        return "50%标准进攻预演"
    if action_type == "execute" and position_pct == 50:
        return "50%执行计划"
    label_map = {
        "execute": "执行计划",
        "watch_only": "仅观察",
        "no_trade": "无交易",
    }
    return label_map.get(action_type, action_type or "-")


def _get_signal_type_label_legacy_body(signal_type):
    signal_type = signal_type or "base"
    prior = EV_SIGNAL_TYPE_PRIORS.get(signal_type, EV_SIGNAL_TYPE_PRIORS["base"])
    return prior.get("label", signal_type)


def _backfill_strategy_record_market_context_legacy_body(record):
    record = record or {}
    report_date = _normalize_kline_date_str(record.get("report_date"))
    if not report_date:
        return record

    if _safe_float(record.get("benchmark_report_close")) <= 0:
        report_dt = _parse_kline_date(report_date)
        end_probe_date = report_date
        if report_dt is not None:
            end_probe_date = (report_dt + datetime.timedelta(days=7)).strftime("%Y-%m-%d")
        benchmark_bars = fetch_daily_price_bars("sh.000001", report_date, end_probe_date, is_index=True)
        benchmark_bar = _get_first_bar_on_or_after(benchmark_bars, report_date)
        if benchmark_bar:
            record["benchmark_report_close"] = round(_safe_float(benchmark_bar.get("close")), 4)

    record.setdefault("signal_type", "")
    record.setdefault("permission_label", "")
    record.setdefault("ev_model_source", "")
    record.setdefault("ev_sample_size", 0)
    record.setdefault("ev_global_sample_size", 0)
    record.setdefault("ev_confidence", 0.0)
    record.setdefault("abnormal_setup_signal_id", "")
    record.setdefault("abnormal_setup_signal_label", "")
    record.setdefault("abnormal_follow_state", "")
    record.setdefault("stock_sector", "")
    record.setdefault("defensive_exit_rule", DEFENSIVE_EXIT_RULE_TEXT)
    record.setdefault("profit_exit_rule", PROFIT_EXIT_RULE_TEXT)
    record.setdefault("holding_days_min", STRATEGY_HOLDING_DAYS_MIN)
    record.setdefault("holding_days_max", STRATEGY_HOLDING_DAYS_MAX)
    record.setdefault("profit_take_pct", 0.05)
    record.setdefault("contract_kind", "")
    record.setdefault("contract_active_window_days", 0)
    record.setdefault("contract_right_side_trigger_price", None)
    record.setdefault("contract_void_price", None)
    record.setdefault("contract_reset_breakout_price", None)
    record.setdefault("contract_upgrade_condition_text", "")
    record.setdefault("decision_stack", {})
    record.setdefault("factor_snapshot", {})
    record.setdefault("factor_snapshot_path", "")
    record.setdefault("factor_snapshot_mode", "")
    record.setdefault("factor_snapshot_version", "")
    record.setdefault("factor_snapshot_saved_at", "")
    record.setdefault("mainline_driver_type", "")
    record.setdefault("mainline_pulse_stage", "")
    record.setdefault("mainline_acceptance_quality", "")
    record.setdefault("mainline_passivation_risk", "")
    record.setdefault("mainline_execution_bias", "")
    record.setdefault("mainline_pulse_action_bias", "")
    record.setdefault("mainline_pulse_action_reason", "")
    return record


def _candidate_confirmation_chain_legacy_body(candidate=None):
    candidate = candidate or {}
    minute_plan = candidate.get("minute_plan") or {}
    confirm_price = _round_or_none(minute_plan.get("confirm_price_60m"))
    support_price = _round_or_none(
        minute_plan.get("confirm_support_60m")
        or candidate.get("display_anchor_price")
        or candidate.get("execution_stop")
        or candidate.get("effective_stop")
    )
    return {
        "has_confirmation_chain": confirm_price is not None and support_price is not None,
        "confirm_price": confirm_price,
        "support_price": support_price,
    }


def _resolve_probe_role_family_legacy_body(probe_role="", watch_anchor_type="", anchor_type=""):
    role_text = " / ".join(
        str(part or "").strip()
        for part in (probe_role, watch_anchor_type, anchor_type)
        if str(part or "").strip()
    )
    if probe_role in ("mainline_abnormal_probe", "crossline_abnormal_probe", "validation_probe"):
        return probe_role
    if "承接验证" in role_text:
        return "validation_probe"
    if "跨线" in role_text:
        return "crossline_abnormal_probe"
    if "主线" in role_text:
        return "mainline_abnormal_probe"
    return "watch_anchor"


def _iter_record_probe_candidates_legacy_body(record):
    record = record or {}
    factor_snapshot = record.get("factor_snapshot", {}) or {}
    selection = factor_snapshot.get("selection", {}) or {}
    candidates = []

    def append_candidate(candidate, role_family="watch_anchor"):
        candidate = candidate or {}
        code = normalize_stock_code(candidate.get("code") or candidate.get("stock_code", ""))
        setup_id = str(candidate.get("setup_signal_id", "") or candidate.get("abnormal_setup_signal_id", "") or "").strip()
        if not code and not setup_id:
            return
        candidates.append({
            "code": code,
            "setup_id": setup_id,
            "role_family": role_family,
        })

    append_candidate(
        {
            "code": record.get("stock_code", ""),
            "setup_signal_id": record.get("abnormal_setup_signal_id", ""),
        },
        _resolve_probe_role_family(anchor_type=record.get("anchor_type", "")),
    )
    append_candidate(
        selection.get("selected_candidate") or {},
        _resolve_probe_role_family(anchor_type=selection.get("anchor_type", "")),
    )
    abnormal_probes = selection.get("abnormal_probes", {}) or {}
    append_candidate(abnormal_probes.get("mainline_abnormal_probe") or {}, "mainline_abnormal_probe")
    append_candidate(abnormal_probes.get("crossline_abnormal_probe") or {}, "crossline_abnormal_probe")
    append_candidate(abnormal_probes.get("validation_probe") or {}, "validation_probe")
    return candidates


def _build_candidate_history_feedback_legacy_body(candidate=None, target_date="", probe_role="", watch_anchor_type=""):
    candidate = candidate or {}
    code = normalize_stock_code(candidate.get("code", ""))
    setup_id = str(candidate.get("abnormal_setup_signal_id", "") or candidate.get("setup_signal_id", "") or "").strip()
    target_date = _normalize_kline_date_str(target_date)
    role_family = _resolve_probe_role_family(
        probe_role=probe_role,
        watch_anchor_type=watch_anchor_type,
        anchor_type=candidate.get("watch_anchor_type", ""),
    )
    feedback = {
        "continuous_days": 0,
        "matched_records": 0,
        "role_family": role_family,
        "reasons": [],
        "latest_match": {},
        "active_watch": False,
        "active_window_days": 0,
        "trading_days_since_latest": 0,
        "contract_kind": "",
    }
    if not target_date or (not code and not setup_id):
        return feedback

    try:
        ledger = load_strategy_performance_ledger(mode=LEDGER_MODE_FROZEN)
    except Exception:
        return feedback

    matched_records = []
    for record in ledger.get("records", []) or []:
        report_date = _normalize_kline_date_str(record.get("report_date"))
        if not report_date or report_date >= target_date:
            continue
        if record.get("action_type") not in ("watch_only", "execute"):
            continue
        match_type = ""
        for item in _iter_record_probe_candidates(record):
            item_code = normalize_stock_code(item.get("code", ""))
            item_setup = str(item.get("setup_id", "") or "").strip()
            item_role = str(item.get("role_family", "") or "").strip()
            if code and item_code and item_code == code:
                match_type = "same_stock"
                break
            if setup_id and item_setup == setup_id and role_family and item_role == role_family:
                match_type = "same_setup_role"
                break
        if match_type:
            matched_records.append({
                "report_date": report_date,
                "match_type": match_type,
                "anchor_type": str(record.get("anchor_type", "") or "").strip(),
                "holding_days_max": max(
                    int(_safe_float(record.get("holding_days_max", STRATEGY_HOLDING_DAYS_MAX) or STRATEGY_HOLDING_DAYS_MAX)),
                    1,
                ),
                "confirm_price_60m": _round_or_none(record.get("confirm_price_60m")),
                "confirm_support_60m": _round_or_none(record.get("confirm_support_60m")),
                "entry_range_high": _round_or_none(record.get("entry_range_high")),
                "entry_range_low": _round_or_none(record.get("entry_range_low")),
                "effective_stop": _round_or_none(record.get("effective_stop")),
            })

    matched_records.sort(key=lambda item: item.get("report_date", ""), reverse=True)
    feedback["matched_records"] = len(matched_records)
    if matched_records:
        latest_same_stock = next((dict(item) for item in matched_records if item.get("match_type") == "same_stock"), None)
        feedback["latest_match"] = latest_same_stock or dict(matched_records[0])
    previous_anchor = target_date
    continuous_days = 0
    continuity_match_types = []
    for record in matched_records:
        record_date = record.get("report_date", "")
        if not _is_next_trading_day(record_date, previous_anchor):
            break
        continuous_days += 1
        continuity_match_types.append(record.get("match_type", ""))
        previous_anchor = record_date
    feedback["continuous_days"] = continuous_days
    if continuous_days >= 2:
        if "same_setup_role" in continuity_match_types:
            feedback["reasons"].append("历史连续探针/Setup反馈确认成立")
        else:
            feedback["reasons"].append("历史连续候选反馈确认成立")
    elif continuous_days == 1:
        feedback["reasons"].append("仅有1个前序候选日，连续性仍偏弱")

    latest_match = feedback.get("latest_match", {}) or {}
    latest_anchor_type = str(latest_match.get("anchor_type", "") or "").strip()
    if latest_match and ("执行候选观察锚点" in latest_anchor_type or "创业板20cm预启动" in latest_anchor_type):
        active_window_days = min(
            max(int(_safe_float(latest_match.get("holding_days_max", STRATEGY_HOLDING_DAYS_MAX) or STRATEGY_HOLDING_DAYS_MAX)), 3),
            5,
        )
        trading_span = _count_trading_days_between(latest_match.get("report_date", ""), target_date)
        trading_days_since_latest = max(trading_span - 1, 0) if trading_span else 0
        feedback["active_window_days"] = active_window_days
        feedback["trading_days_since_latest"] = trading_days_since_latest
        contract_kind = "gem_breathing_20cm" if "创业板20cm预启动" in latest_anchor_type else "execute_anchor"
        feedback["contract_kind"] = contract_kind
        if 0 < trading_days_since_latest <= active_window_days:
            feedback["active_watch"] = True
            if contract_kind == "gem_breathing_20cm":
                feedback["reasons"].append(f"创业板20cm预启动仍在{active_window_days}日观察窗口内")
            else:
                feedback["reasons"].append(f"执行候选观察锚点仍在{active_window_days}日活观察窗口内")
        elif trading_days_since_latest > active_window_days:
            if contract_kind == "gem_breathing_20cm":
                feedback["reasons"].append(f"创业板20cm预启动已超过{active_window_days}日观察窗口")
            else:
                feedback["reasons"].append(f"执行候选观察锚点已超过{active_window_days}日活观察窗口")
    return feedback


def _extract_candidate_report_prices_legacy_body(candidate=None):
    candidate = candidate or {}
    close_price = _round_or_none(
        candidate.get("close")
        or candidate.get("report_day_close")
        or candidate.get("price")
        or candidate.get("latest_price")
    )
    high_price = _round_or_none(candidate.get("high") or candidate.get("report_day_high") or close_price)
    low_price = _round_or_none(candidate.get("low") or candidate.get("report_day_low"))
    return {
        "close": close_price,
        "high": high_price,
        "low": low_price,
    }


def _build_candidate_feedback_clock_legacy_body(
    candidate=None,
    watch_anchor_type="",
    state_machine_snapshot=None,
    mainline_name="",
    target_date="",
):
    candidate = candidate or {}
    state_machine_snapshot = state_machine_snapshot or {}
    mainline_name = str(mainline_name or state_machine_snapshot.get("leading_line", "") or "").strip()
    watch_anchor_type = str(watch_anchor_type or candidate.get("watch_anchor_type", "") or "").strip()
    permission_label = str(candidate.get("permission_label", "") or "").strip()
    follow_state = _resolve_candidate_follow_state(candidate)
    confirmation = _candidate_confirmation_chain(candidate)
    tradability_guard = candidate.get("tradability_guard") or {}
    can_trade = tradability_guard.get("can_trade", True)
    decision_stack = candidate.get("decision_stack", {}) or {}
    strong_trigger = (
        bool(candidate.get("abnormal_setup_signal_id"))
        or _safe_float(decision_stack.get("trigger_score", decision_stack.get("setup_priority_score", 0))) >= 80
    )
    history_feedback = _build_candidate_history_feedback(
        candidate=candidate,
        target_date=target_date,
        probe_role=_resolve_probe_role_family(
            watch_anchor_type=watch_anchor_type,
            anchor_type=candidate.get("watch_anchor_type", ""),
        ),
        watch_anchor_type=watch_anchor_type,
    )
    is_priority_candidate = (
        _candidate_matches_mainline(candidate, mainline_name)
        or candidate.get("is_mainline")
        or "主线" in permission_label
        or "龙头" in permission_label
        or "重点观察" in permission_label
        or ("主线" in watch_anchor_type and "跨线" not in watch_anchor_type)
    )

    score = 0
    reasons = []
    if is_priority_candidate:
        score += 1
        reasons.append("属于主线/龙头/重点观察优先对象")
    if follow_state in ("跌不下去", "缩量消化"):
        score += 1
        reasons.append(f"承接状态为{follow_state}")
    if confirmation.get("has_confirmation_chain"):
        score += 1
        reasons.append("具备60分钟确认链")
    if can_trade and not candidate.get("report_day_is_one_word", False):
        score += 1
        reasons.append("可交易性正常")
    if strong_trigger:
        score += 1
        reasons.append("具备正式setup/高触发优先级")
    if history_feedback.get("continuous_days", 0) >= 2:
        score += 1
        reasons.append(f"已连续{history_feedback.get('continuous_days', 0)}个报告日进入候选")

    active_watch = bool(history_feedback.get("active_watch"))
    contract_kind = str(history_feedback.get("contract_kind", "") or "").strip()
    second_shot_ready = False
    second_shot_breakout_price = None
    if active_watch:
        latest_match = history_feedback.get("latest_match", {}) or {}
        prior_confirm = _round_or_none(latest_match.get("confirm_price_60m"))
        prior_range_high = _round_or_none(latest_match.get("entry_range_high"))
        prior_support = _round_or_none(latest_match.get("confirm_support_60m") or latest_match.get("effective_stop"))
        report_prices = _extract_candidate_report_prices(candidate)
        report_close = report_prices.get("close")
        report_low = report_prices.get("low")
        breakout_candidates = [price for price in (prior_range_high, prior_confirm) if price is not None]
        second_shot_breakout_price = max(breakout_candidates) if breakout_candidates else None
        guard_still_holds = prior_support is None or report_low is None or report_low >= prior_support
        if guard_still_holds:
            score += 1
            if contract_kind == "gem_breathing_20cm":
                reasons.append("创业板20cm预启动在观察窗口内仍未失守guard")
            else:
                reasons.append("执行候选观察锚点在活观察窗口内仍未失守初始guard")
        if (
            guard_still_holds
            and second_shot_breakout_price is not None
            and report_close is not None
            and report_close >= second_shot_breakout_price
        ):
            second_shot_ready = True
            score += 1
            if contract_kind == "gem_breathing_20cm":
                reasons.append(f"已重新站上{second_shot_breakout_price:.2f}，触发右侧确认/再突破条件")
            else:
                reasons.append(f"已重新站上{second_shot_breakout_price:.2f}，触发二次突破条件")
        elif (
            guard_still_holds
            and prior_confirm is not None
            and report_close is not None
            and report_close >= prior_confirm * 0.985
        ):
            if contract_kind == "gem_breathing_20cm":
                reasons.append("创业板20cm预启动仍贴着右侧确认位运行，继续保留观察合同")
            else:
                reasons.append("执行候选观察锚点仍贴着初始确认位运行，继续保留活观察")

    reasons.extend(history_feedback.get("reasons", []) or [])

    explicit_ready = candidate.get("candidate_feedback_ready")
    if explicit_ready is None:
        base_ready = bool(
            is_priority_candidate
            and follow_state in ("跌不下去", "缩量消化")
            and confirmation.get("has_confirmation_chain")
            and can_trade
            and not candidate.get("report_day_is_one_word", False)
            and strong_trigger
        )
        ready = bool(
            base_ready
            or second_shot_ready
            or (
                history_feedback.get("continuous_days", 0) >= 2
                and confirmation.get("has_confirmation_chain")
                and can_trade
                and strong_trigger
            )
        )
    else:
        ready = bool(explicit_ready)
        reasons.append("显式标记为反馈已就绪" if ready else "显式标记为反馈未就绪")

    return {
        "ready": ready,
        "score": score,
        "reasons": reasons,
        "confirm_price": confirmation.get("confirm_price"),
        "support_price": confirmation.get("support_price"),
        "has_confirmation_chain": confirmation.get("has_confirmation_chain"),
        "history_feedback": history_feedback,
        "contract_kind": contract_kind,
        "active_watch": active_watch,
        "second_shot_ready": second_shot_ready,
        "second_shot_breakout_price": second_shot_breakout_price,
    }


def _format_pct_legacy_body(value):
    if value is None:
        return "-"
    return f"{value * 100:+.2f}%"


def _format_pct_range_legacy_body(low_value, high_value):
    if low_value is None or high_value is None:
        return "-"
    return f"{low_value * 100:+.2f}% ~ {high_value * 100:+.2f}%"


def _get_run_mode_label_legacy_body(mode):
    return "官方冻结" if mode == LEDGER_MODE_FROZEN else "实验重放"


def _build_trade_return_stats_legacy_body(records):
    stats = {
        "sample_size": 0,
        "wins": 0,
        "losses": 0,
        "neutral": 0,
        "win_rate": None,
        "avg_win_pct": None,
        "avg_loss_pct": None,
    }
    if not records:
        return stats

    win_returns = []
    loss_returns = []
    sample_size = 0
    for record in records:
        if record.get("action_type") != "execute":
            continue
        sim = record.get("simulation", {}) or {}
        if not sim.get("triggered"):
            continue
        if sim.get("status") not in ("closed", "open_mark_to_market"):
            continue

        low = sim.get("strategy_return_worst")
        high = sim.get("strategy_return_best")
        if low is None or high is None:
            continue
        midpoint_return = (_safe_float(low) + _safe_float(high)) / 2.0
        sample_size += 1
        if midpoint_return > 0:
            win_returns.append(midpoint_return)
        elif midpoint_return < 0:
            loss_returns.append(abs(midpoint_return))
        else:
            stats["neutral"] += 1

    stats["sample_size"] = sample_size
    stats["wins"] = len(win_returns)
    stats["losses"] = len(loss_returns)
    if sample_size > 0:
        stats["win_rate"] = len(win_returns) / sample_size
    if win_returns:
        stats["avg_win_pct"] = sum(win_returns) / len(win_returns)
    if loss_returns:
        stats["avg_loss_pct"] = sum(loss_returns) / len(loss_returns)
    return stats


def _summarize_ev_signal_review_legacy_body(records, start_date, end_date):
    scoped = [
        record for record in (records or [])
        if start_date <= _normalize_kline_date_str(record.get("report_date")) <= end_date
        and record.get("action_type") == "execute"
    ]

    grouped = {}
    for record in scoped:
        signal_type = record.get("signal_type") or "base"
        group = grouped.setdefault(signal_type, {
            "signal_type": signal_type,
            "signal_label": _get_signal_type_label(signal_type),
            "plan_count": 0,
            "triggered_count": 0,
            "sample_count": 0,
            "hit_count": 0,
            "flat_count": 0,
            "miss_count": 0,
            "return_sum": 0.0,
            "alpha_sum": 0.0,
        })
        group["plan_count"] += 1

        sim = record.get("simulation", {}) or {}
        if sim.get("triggered"):
            group["triggered_count"] += 1

        if not sim.get("triggered") or sim.get("status") not in ("closed", "open_mark_to_market"):
            continue

        midpoint_return = (
            _safe_float(sim.get("strategy_return_worst")) + _safe_float(sim.get("strategy_return_best"))
        ) / 2.0
        midpoint_alpha = (
            _safe_float(sim.get("alpha_return_worst")) + _safe_float(sim.get("alpha_return_best"))
        ) / 2.0
        group["sample_count"] += 1
        group["return_sum"] += midpoint_return
        group["alpha_sum"] += midpoint_alpha

        if midpoint_return > 0:
            group["hit_count"] += 1
        elif midpoint_return < 0:
            group["miss_count"] += 1
        else:
            group["flat_count"] += 1

    items = []
    for item in grouped.values():
        sample_count = item.get("sample_count", 0)
        hit_rate = item.get("hit_count", 0) / sample_count if sample_count > 0 else None
        avg_return = item.get("return_sum", 0.0) / sample_count if sample_count > 0 else None
        avg_alpha = item.get("alpha_sum", 0.0) / sample_count if sample_count > 0 else None
        items.append({
            **item,
            "hit_rate": hit_rate,
            "avg_return": avg_return,
            "avg_alpha": avg_alpha,
        })

    items.sort(
        key=lambda x: (
            x.get("sample_count", 0),
            x.get("hit_rate") if x.get("hit_rate") is not None else -1,
            x.get("plan_count", 0),
        ),
        reverse=True,
    )
    return {
        "start_date": start_date,
        "end_date": end_date,
        "total_plan_count": len(scoped),
        "items": items,
    }
