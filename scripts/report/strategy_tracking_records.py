from __future__ import annotations

__all__ = [
    "find_strategy_record",
    "format_strategy_record_brief",
    "strategy_record_core_signature",
    "upsert_strategy_record",
    "merge_strategy_record_sources",
    "summarize_strategy_window",
    "prepare_records_for_review",
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


def find_strategy_record(records, report_date, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _find_strategy_record_legacy_body(records, report_date)
    finally:
        _restore_runtime_bindings(previous)


def format_strategy_record_brief(record, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _format_strategy_record_brief_legacy_body(record)
    finally:
        _restore_runtime_bindings(previous)


def strategy_record_core_signature(record, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _strategy_record_core_signature_legacy_body(record)
    finally:
        _restore_runtime_bindings(previous)


def upsert_strategy_record(ledger, plan_context, allow_overwrite=True, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _upsert_strategy_record_legacy_body(
            ledger,
            plan_context,
            allow_overwrite=allow_overwrite,
        )
    finally:
        _restore_runtime_bindings(previous)


def merge_strategy_record_sources(base_records, override_records, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _merge_strategy_record_sources_legacy_body(base_records, override_records)
    finally:
        _restore_runtime_bindings(previous)


def summarize_strategy_window(records, start_date, end_date, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _summarize_strategy_window_legacy_body(records, start_date, end_date)
    finally:
        _restore_runtime_bindings(previous)


def prepare_records_for_review(records, as_of_date, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _prepare_records_for_review_legacy_body(records, as_of_date)
    finally:
        _restore_runtime_bindings(previous)


def _find_strategy_record_legacy_body(records, report_date):
    report_date = _normalize_kline_date_str(report_date)
    for record in records or []:
        if _normalize_kline_date_str(record.get("report_date")) == report_date:
            return record
    return None


def _format_strategy_record_brief_legacy_body(record):
    if not record:
        return "无"
    stock_name = record.get("stock_name") or record.get("anchor_type") or "无标的"
    stock_code = record.get("stock_code", "")
    action_label = _get_plan_action_label(record.get("action_type", ""), record.get("position_pct"))
    if stock_code:
        stock_name = f"{stock_name}({stock_code})"
    return f"{action_label} / {stock_name}"


def _strategy_record_core_signature_legacy_body(record):
    if not record:
        return ()
    return (
        _normalize_kline_date_str(record.get("report_date")),
        record.get("action_type", ""),
        record.get("anchor_type", ""),
        record.get("stock_name", ""),
        record.get("stock_code", ""),
        _round_or_none(record.get("entry_range_low"), 4),
        _round_or_none(record.get("entry_range_high"), 4),
        _round_or_none(record.get("confirm_price_60m"), 4),
        _round_or_none(record.get("effective_stop"), 4),
        record.get("trigger_text", ""),
    )


def _upsert_strategy_record_legacy_body(ledger, plan_context, allow_overwrite=True):
    records = ledger.setdefault("records", [])
    report_date = plan_context.get("report_date")
    for idx, record in enumerate(records):
        if record.get("report_date") == report_date:
            if not allow_overwrite:
                return record, "preserved_existing"
            previous_simulation = record.get("simulation", {})
            updated = dict(record)
            updated.update(plan_context)
            if previous_simulation:
                updated["simulation"] = previous_simulation
            records[idx] = updated
            return updated, "updated"
    records.append(dict(plan_context))
    return records[-1], "created"


def _merge_strategy_record_sources_legacy_body(base_records, override_records):
    merged_by_date = {}
    for record in base_records or []:
        report_date = _normalize_kline_date_str(record.get("report_date"))
        if report_date:
            merged_by_date[report_date] = dict(record)

    for record in override_records or []:
        report_date = _normalize_kline_date_str(record.get("report_date"))
        if report_date:
            merged_by_date[report_date] = dict(record)

    return [
        merged_by_date[report_date]
        for report_date in sorted(merged_by_date.keys())
    ]


def _summarize_strategy_window_legacy_body(records, start_date, end_date):
    scoped = [
        record
        for record in (records or [])
        if start_date <= _normalize_kline_date_str(record.get("report_date")) <= end_date
    ]
    actionable = [record for record in scoped if record.get("action_type") == "execute"]
    triggered = [
        record for record in actionable
        if record.get("simulation", {}).get("triggered")
    ]
    evaluated = [
        record for record in actionable
        if record.get("simulation", {}).get("status") in ("closed", "open_mark_to_market", "not_triggered")
    ]
    included = [
        record for record in evaluated
        if record.get("simulation", {}).get("triggered")
    ]
    strategy_worst = _compound_returns(
        [record.get("simulation", {}).get("strategy_return_worst", 0.0) for record in included]
    )
    strategy_best = _compound_returns(
        [record.get("simulation", {}).get("strategy_return_best", 0.0) for record in included]
    )

    benchmark_return = None
    if actionable:
        benchmark_bars = fetch_daily_price_bars("sh.000001", start_date, end_date, is_index=True)
        benchmark_start = _get_first_bar_on_or_after(benchmark_bars, start_date)
        benchmark_end = _get_last_bar_on_or_before(benchmark_bars, end_date)
        if benchmark_start and benchmark_end:
            start_close = _safe_float(benchmark_start.get("close"))
            end_close = _safe_float(benchmark_end.get("close"))
            if start_close > 0:
                benchmark_return = end_close / start_close - 1

    alpha_worst = strategy_worst - benchmark_return if benchmark_return is not None else None
    alpha_best = strategy_best - benchmark_return if benchmark_return is not None else None
    positive_alpha_count = 0
    for record in included:
        sim = record.get("simulation", {})
        midpoint = (
            _safe_float(sim.get("alpha_return_worst")) + _safe_float(sim.get("alpha_return_best"))
        ) / 2.0
        if midpoint > 0:
            positive_alpha_count += 1

    return {
        "start_date": start_date,
        "end_date": end_date,
        "plan_count": len(scoped),
        "actionable_count": len(actionable),
        "triggered_count": len(triggered),
        "evaluated_count": len(evaluated),
        "strategy_return_worst": strategy_worst,
        "strategy_return_best": strategy_best,
        "benchmark_return": benchmark_return,
        "alpha_return_worst": alpha_worst,
        "alpha_return_best": alpha_best,
        "positive_alpha_count": positive_alpha_count,
        "open_count": sum(
            1
            for record in included
            if record.get("simulation", {}).get("status") == "open_mark_to_market"
        ),
    }


def _prepare_records_for_review_legacy_body(records, as_of_date):
    prepared = []
    for record in records or []:
        prepared.append(_backfill_strategy_record_market_context(dict(record)))

    prepared.sort(key=lambda x: _normalize_kline_date_str(x.get("report_date")))
    for record in prepared:
        record["simulation"] = _evaluate_single_strategy_record(record, as_of_date)
    _apply_yizi_chain_rules(prepared)
    for record in prepared:
        record["attribution"] = _classify_strategy_record_attribution(record, as_of_date)
    return prepared
