from __future__ import annotations

__all__ = [
    "build_abnormal_setup_distribution",
    "snapshot_candidate_brief",
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


def build_abnormal_setup_distribution(abnormal_watch_pool, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _build_abnormal_setup_distribution_legacy_body(abnormal_watch_pool)
    finally:
        _restore_runtime_bindings(previous)


def snapshot_candidate_brief(candidate, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _snapshot_candidate_brief_legacy_body(candidate)
    finally:
        _restore_runtime_bindings(previous)


def _round_or_none(value, digits=4):
    if value is None:
        return None
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def normalize_stock_code(code):
    return str(code or "").strip()


def _build_abnormal_setup_distribution_legacy_body(abnormal_watch_pool):
    abnormal_watch_pool, _ = _split_abnormal_watch_pool(abnormal_watch_pool)
    grouped = {}
    for item in abnormal_watch_pool or []:
        setup_id = item.get("setup_signal_id") or "unknown"
        entry = grouped.setdefault(
            setup_id,
            {
                "id": setup_id,
                "label": item.get("setup_signal_label", setup_id),
                "count": 0,
            },
        )
        entry["count"] += 1
    return sorted(grouped.values(), key=lambda x: (x.get("count", 0), x.get("label", "")), reverse=True)


def _snapshot_candidate_brief_legacy_body(candidate):
    if not candidate:
        return {}

    signal = candidate.get("signal")
    minute_plan = candidate.get("minute_plan") or {}
    stop_plan = candidate.get("stop_plan") or {}
    contract_prices = _resolve_candidate_contract_prices(candidate, signal=signal)
    price_focus = _build_trade_price_focus(minute_plan, stop_plan)

    return {
        "name": candidate.get("name", ""),
        "code": normalize_stock_code(candidate.get("code", "")),
        "sector": candidate.get("sector", ""),
        "permission_label": candidate.get("permission_label", ""),
        "watch_anchor_type": candidate.get("watch_anchor_type", ""),
        "watch_anchor_note": candidate.get("watch_anchor_note", ""),
        "signal_type": candidate.get("signal_type") or (getattr(signal, "signal_type", "") if signal else ""),
        "setup_signal_id": candidate.get("abnormal_setup_signal_id", candidate.get("setup_signal_id", "")),
        "setup_signal_label": candidate.get("abnormal_setup_signal_label", candidate.get("setup_signal_label", "")),
        "abnormal_follow_state": candidate.get("abnormal_follow_state", candidate.get("follow_state", "")),
        "entry_range_low": contract_prices.get("entry_range_low"),
        "entry_range_high": contract_prices.get("entry_range_high"),
        "observe_anchor_price": contract_prices.get("observe_anchor_price"),
        "upgrade_trigger_price": contract_prices.get("upgrade_trigger_price"),
        "invalidation_price": contract_prices.get("invalidation_price"),
        "reset_breakout_price": contract_prices.get("reset_breakout_price"),
        "confirm_price_60m": _round_or_none(minute_plan.get("confirm_price_60m")),
        "confirm_support_60m": _round_or_none(minute_plan.get("confirm_support_60m")),
        "key_zone_low": price_focus.get("key_zone_low"),
        "key_zone_high": price_focus.get("key_zone_high"),
        "key_zone_display": price_focus.get("key_zone_display"),
        "execution_stop": price_focus.get("execution_stop"),
        "price_note": price_focus.get("note_text", ""),
        "price_confluence_reasons": list(price_focus.get("confluence_reasons", []) or []),
        "effective_stop": _round_or_none((stop_plan or {}).get("effective_stop") or candidate.get("stop_loss")),
        "report_day_is_one_word": bool(candidate.get("report_day_is_one_word")),
        "tomorrow_strength": _round_or_none(candidate.get("tomorrow_strength"), 2),
        "composite_score": _round_or_none(candidate.get("composite_score"), 6),
        "ev_pct": _round_or_none(candidate.get("ev_pct"), 6),
        "decision_stack": dict(candidate.get("decision_stack", {}) or {}),
    }
