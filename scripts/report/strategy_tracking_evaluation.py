from __future__ import annotations

__all__ = [
    "apply_yizi_chain_rules",
    "collect_record_market_path",
    "compute_benchmark_return",
    "compute_watch_outcome_metrics",
    "evaluate_single_strategy_record",
    "get_nth_bar_after",
    "get_recent_record_display_metrics",
    "simulate_exit_for_entry",
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


def simulate_exit_for_entry(
    entry_price,
    bars,
    structure_stop=None,
    holding_days_min=None,
    holding_days_max=None,
    profit_take_pct=0.05,
    *,
    helpers=None,
):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _simulate_exit_for_entry_legacy_body(
            entry_price,
            bars,
            structure_stop=structure_stop,
            holding_days_min=holding_days_min,
            holding_days_max=holding_days_max,
            profit_take_pct=profit_take_pct,
        )
    finally:
        _restore_runtime_bindings(previous)


def compute_benchmark_return(report_date, end_date, benchmark_report_close, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _compute_benchmark_return_legacy_body(report_date, end_date, benchmark_report_close)
    finally:
        _restore_runtime_bindings(previous)


def get_nth_bar_after(bars, after_date, nth=1, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _get_nth_bar_after_legacy_body(bars, after_date, nth=nth)
    finally:
        _restore_runtime_bindings(previous)


def compute_watch_outcome_metrics(record, as_of_date, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _compute_watch_outcome_metrics_legacy_body(record, as_of_date)
    finally:
        _restore_runtime_bindings(previous)


def evaluate_single_strategy_record(record, as_of_date, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _evaluate_single_strategy_record_legacy_body(record, as_of_date)
    finally:
        _restore_runtime_bindings(previous)


def collect_record_market_path(record, as_of_date, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _collect_record_market_path_legacy_body(record, as_of_date)
    finally:
        _restore_runtime_bindings(previous)


def apply_yizi_chain_rules(records, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _apply_yizi_chain_rules_legacy_body(records)
    finally:
        _restore_runtime_bindings(previous)


def get_recent_record_display_metrics(record, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _get_recent_record_display_metrics_legacy_body(record)
    finally:
        _restore_runtime_bindings(previous)


def _simulate_exit_for_entry(
    entry_price,
    bars,
    structure_stop=None,
    holding_days_min=None,
    holding_days_max=None,
    profit_take_pct=0.05,
):
    return _simulate_exit_for_entry_legacy_body(
        entry_price,
        bars,
        structure_stop=structure_stop,
        holding_days_min=holding_days_min,
        holding_days_max=holding_days_max,
        profit_take_pct=profit_take_pct,
    )


def _compute_benchmark_return(report_date, end_date, benchmark_report_close):
    return _compute_benchmark_return_legacy_body(report_date, end_date, benchmark_report_close)


def _get_nth_bar_after(bars, after_date, nth=1):
    return _get_nth_bar_after_legacy_body(bars, after_date, nth=nth)


def _compute_watch_outcome_metrics(record, as_of_date):
    return _compute_watch_outcome_metrics_legacy_body(record, as_of_date)


def _evaluate_single_strategy_record(record, as_of_date):
    return _evaluate_single_strategy_record_legacy_body(record, as_of_date)


def _collect_record_market_path(record, as_of_date):
    return _collect_record_market_path_legacy_body(record, as_of_date)


def _apply_yizi_chain_rules(records):
    return _apply_yizi_chain_rules_legacy_body(records)


def _get_recent_record_display_metrics(record):
    return _get_recent_record_display_metrics_legacy_body(record)


def _simulate_exit_for_entry_legacy_body(
    entry_price,
    bars,
    structure_stop=None,
    holding_days_min=None,
    holding_days_max=None,
    profit_take_pct=0.05,
):
    entry_price = _safe_float(entry_price, 0.0)
    if entry_price <= 0 or not bars:
        return {
            "exit_price": None,
            "exit_date": "",
            "exit_reason": "invalid",
            "status": "pending",
            "return_pct": 0.0,
        }

    default_holding_days_min = globals().get("STRATEGY_HOLDING_DAYS_MIN", 3)
    default_holding_days_max = globals().get("STRATEGY_HOLDING_DAYS_MAX", 5)
    max_single_trade_loss_pct = _safe_float(globals().get("MAX_SINGLE_TRADE_LOSS_PCT", 0.05), 0.05)

    hard_stop = round(entry_price * (1 - max_single_trade_loss_pct), 2)
    structure_stop = _safe_float(structure_stop, 0.0)
    effective_stop = round(max(structure_stop, hard_stop), 2) if structure_stop > 0 else hard_stop
    holding_days_min = max(int(_safe_float(holding_days_min, default_holding_days_min) or default_holding_days_min), 1)
    holding_days_max = max(int(_safe_float(holding_days_max, default_holding_days_max) or default_holding_days_max), holding_days_min)
    profit_take_pct = max(_safe_float(profit_take_pct, 0.05), 0.02)

    window_bars = list(bars[:holding_days_max])
    for idx, bar in enumerate(window_bars):
        low_price = _safe_float(bar.get("low"))
        close_price = _safe_float(bar.get("close"))
        if low_price > 0 and low_price <= effective_stop:
            return {
                "exit_price": effective_stop,
                "exit_date": bar.get("date", ""),
                "exit_reason": "stop_loss",
                "status": "closed",
                "return_pct": effective_stop / entry_price - 1,
                "effective_stop": effective_stop,
            }

        if close_price >= entry_price * (1 + profit_take_pct):
            return {
                "exit_price": round(close_price, 2),
                "exit_date": bar.get("date", ""),
                "exit_reason": "active_sell_big_yang",
                "status": "closed",
                "return_pct": close_price / entry_price - 1,
                "effective_stop": effective_stop,
            }

        if idx + 1 >= holding_days_min and idx + 1 == len(window_bars) and len(window_bars) < holding_days_max:
            return {
                "exit_price": round(close_price, 2),
                "exit_date": bar.get("date", ""),
                "exit_reason": "mark_to_market",
                "status": "open_mark_to_market",
                "return_pct": close_price / entry_price - 1,
                "effective_stop": effective_stop,
            }

    if len(window_bars) >= holding_days_max:
        exit_bar = window_bars[holding_days_max - 1]
        exit_close = _safe_float(exit_bar.get("close"))
        exit_low = _safe_float(exit_bar.get("low"))
        extra_bars = list(bars[holding_days_max:])
        sideways_hold = bool(
            extra_bars
            and exit_low > effective_stop
            and exit_close >= entry_price * 0.995
        )
        if sideways_hold:
            rebreak_reference = max(_safe_float(bar.get("close")) for bar in window_bars)
            extension_budget = min(max(holding_days_min - 1, 1), 2)
            for extra_offset, extra_bar in enumerate(extra_bars[:extension_budget], start=holding_days_max):
                extra_low = _safe_float(extra_bar.get("low"))
                extra_close = _safe_float(extra_bar.get("close"))
                if extra_low > 0 and extra_low <= effective_stop:
                    return {
                        "exit_price": effective_stop,
                        "exit_date": extra_bar.get("date", ""),
                        "exit_reason": "stop_loss",
                        "status": "closed",
                        "return_pct": effective_stop / entry_price - 1,
                        "effective_stop": effective_stop,
                    }
                if extra_close >= entry_price * (1 + profit_take_pct):
                    return {
                        "exit_price": round(extra_close, 2),
                        "exit_date": extra_bar.get("date", ""),
                        "exit_reason": "active_sell_big_yang",
                        "status": "closed",
                        "return_pct": extra_close / entry_price - 1,
                        "effective_stop": effective_stop,
                    }
                if extra_close >= rebreak_reference:
                    reset_result = _simulate_exit_for_entry(
                        entry_price=entry_price,
                        bars=bars[extra_offset:],
                        structure_stop=effective_stop,
                        holding_days_min=max(holding_days_min, 2),
                        holding_days_max=max(holding_days_min, 2),
                        profit_take_pct=profit_take_pct,
                    )
                    if reset_result.get("exit_date"):
                        return reset_result
                    break
            extension_exit_bar = extra_bars[min(extension_budget, len(extra_bars)) - 1]
            extension_exit_price = round(_safe_float(extension_exit_bar.get("close")), 2)
            return {
                "exit_price": extension_exit_price,
                "exit_date": extension_exit_bar.get("date", ""),
                "exit_reason": f"day{holding_days_max + min(extension_budget, len(extra_bars))}_close",
                "status": "closed",
                "return_pct": extension_exit_price / entry_price - 1 if entry_price > 0 else 0.0,
                "effective_stop": effective_stop,
            }
        exit_price = round(exit_close, 2)
        return {
            "exit_price": exit_price,
            "exit_date": exit_bar.get("date", ""),
            "exit_reason": f"day{holding_days_max}_close",
            "status": "closed",
            "return_pct": exit_price / entry_price - 1 if entry_price > 0 else 0.0,
            "effective_stop": effective_stop,
        }

    last_bar = window_bars[-1]
    last_close = round(_safe_float(last_bar.get("close")), 2)
    return {
        "exit_price": last_close,
        "exit_date": last_bar.get("date", ""),
        "exit_reason": "mark_to_market",
        "status": "open_mark_to_market",
        "return_pct": last_close / entry_price - 1 if entry_price > 0 else 0.0,
        "effective_stop": effective_stop,
    }


def _compute_benchmark_return_legacy_body(report_date, end_date, benchmark_report_close):
    report_date = _normalize_kline_date_str(report_date)
    end_date = _normalize_kline_date_str(end_date)
    benchmark_report_close = _safe_float(benchmark_report_close)
    if not report_date or not end_date:
        return 0.0

    benchmark_bars = fetch_daily_price_bars("sh.000001", report_date, end_date, is_index=True)
    if report_date == end_date:
        same_day_bar = _get_first_bar_on_or_after(benchmark_bars, report_date)
        if same_day_bar:
            change_pct = same_day_bar.get("change_pct", same_day_bar.get("涨跌幅"))
            if change_pct is not None:
                return _safe_float(change_pct) / 100.0
            open_price = _safe_float(same_day_bar.get("open"))
            close_price = _safe_float(same_day_bar.get("close"))
            if open_price > 0 and close_price > 0:
                return close_price / open_price - 1
        return 0.0

    if benchmark_report_close <= 0:
        benchmark_start_bar = _get_first_bar_on_or_after(benchmark_bars, report_date)
        if benchmark_start_bar:
            benchmark_report_close = _safe_float(benchmark_start_bar.get("close"))
        else:
            return 0.0
    benchmark_end_bar = _get_last_bar_on_or_before(benchmark_bars, end_date)
    if not benchmark_end_bar:
        return 0.0

    benchmark_end_close = _safe_float(benchmark_end_bar.get("close"))
    if benchmark_end_close <= 0:
        return 0.0
    return benchmark_end_close / benchmark_report_close - 1


def _get_nth_bar_after_legacy_body(bars, after_date, nth=1):
    after_dt = _parse_kline_date(after_date)
    if after_dt is None or nth <= 0:
        return None

    seen = 0
    for bar in bars or []:
        bar_dt = _parse_kline_date(bar.get("date"))
        if bar_dt and bar_dt > after_dt:
            seen += 1
            if seen == nth:
                return bar
    return None


def _compute_watch_outcome_metrics_legacy_body(record, as_of_date):
    record = record or {}
    report_date = _normalize_kline_date_str(record.get("report_date"))
    as_of_date = _normalize_kline_date_str(as_of_date)
    stock_code = normalize_stock_code(record.get("stock_code", ""))
    metrics = {
        "observation_baseline_price": None,
        "next_day_date": None,
        "next_day_stock_return": None,
        "next_day_benchmark_return": None,
        "next_day_alpha_return": None,
        "window_3d_end_date": None,
        "window_3d_stock_return": None,
        "window_3d_benchmark_return": None,
        "window_3d_alpha_return": None,
    }
    if not report_date or not as_of_date or not stock_code or as_of_date <= report_date:
        return metrics

    stock_bars = fetch_daily_price_bars(stock_code, report_date, as_of_date, is_index=False)
    report_close = _safe_float(record.get("report_day_close"))
    if report_close <= 0:
        report_close = _safe_float(record.get("entry_price_anchor"))
    if report_close <= 0:
        report_bar = _get_first_bar_on_or_after(stock_bars, report_date)
        if report_bar:
            report_close = _safe_float(report_bar.get("close"))
    if report_close <= 0:
        return metrics

    metrics["observation_baseline_price"] = round(report_close, 4)

    benchmark_bars = fetch_daily_price_bars("sh.000001", report_date, as_of_date, is_index=True)
    benchmark_report_close = _safe_float(record.get("benchmark_report_close"))
    if benchmark_report_close <= 0:
        benchmark_report_bar = _get_first_bar_on_or_after(benchmark_bars, report_date)
        if benchmark_report_bar:
            benchmark_report_close = _safe_float(benchmark_report_bar.get("close"))

    next_day_bar = _get_nth_bar_after(stock_bars, report_date, nth=1)
    if next_day_bar:
        next_day_close = _safe_float(next_day_bar.get("close"))
        if next_day_close > 0:
            metrics["next_day_date"] = next_day_bar.get("date") or None
            metrics["next_day_stock_return"] = next_day_close / report_close - 1
            benchmark_next_bar = _get_nth_bar_after(benchmark_bars, report_date, nth=1)
            if benchmark_report_close > 0 and benchmark_next_bar:
                benchmark_next_close = _safe_float(benchmark_next_bar.get("close"))
                if benchmark_next_close > 0:
                    metrics["next_day_benchmark_return"] = benchmark_next_close / benchmark_report_close - 1
                    metrics["next_day_alpha_return"] = (
                        metrics["next_day_stock_return"] - metrics["next_day_benchmark_return"]
                    )

    day3_bar = _get_nth_bar_after(stock_bars, report_date, nth=3)
    if day3_bar:
        day3_close = _safe_float(day3_bar.get("close"))
        if day3_close > 0:
            metrics["window_3d_end_date"] = day3_bar.get("date") or None
            metrics["window_3d_stock_return"] = day3_close / report_close - 1
            benchmark_day3_bar = _get_nth_bar_after(benchmark_bars, report_date, nth=3)
            if benchmark_report_close > 0 and benchmark_day3_bar:
                benchmark_day3_close = _safe_float(benchmark_day3_bar.get("close"))
                if benchmark_day3_close > 0:
                    metrics["window_3d_benchmark_return"] = benchmark_day3_close / benchmark_report_close - 1
                    metrics["window_3d_alpha_return"] = (
                        metrics["window_3d_stock_return"] - metrics["window_3d_benchmark_return"]
                    )

    return metrics


def _evaluate_single_strategy_record_legacy_body(record, as_of_date):
    report_date = _normalize_kline_date_str(record.get("report_date"))
    action_type = record.get("action_type", "no_trade")
    benchmark_report_close = _safe_float(record.get("benchmark_report_close"))
    benchmark_report_change_pct = _safe_float(record.get("benchmark_report_change_pct"))
    as_of_date = _normalize_kline_date_str(as_of_date)
    result = {
        "status": "pending",
        "status_label": _get_strategy_status_label("pending"),
        "status_note": "",
        "triggered": False,
        "trade_date": "",
        "confirm_triggered": False,
        "confirm_datetime": "",
        "entry_price_best": None,
        "entry_price_worst": None,
        "exit_date": "",
        "exit_reason": "",
        "strategy_return_best": 0.0,
        "strategy_return_worst": 0.0,
        "benchmark_return": 0.0,
        "alpha_return_best": 0.0,
        "alpha_return_worst": 0.0,
        "used_intraday": False,
        "as_of_date": as_of_date,
        "observation_baseline_price": None,
        "next_day_date": None,
        "next_day_stock_return": None,
        "next_day_benchmark_return": None,
        "next_day_alpha_return": None,
        "window_3d_end_date": None,
        "window_3d_stock_return": None,
        "window_3d_benchmark_return": None,
        "window_3d_alpha_return": None,
    }

    if not report_date:
        result["status"] = "invalid"
        result["status_label"] = _get_strategy_status_label("invalid")
        return result

    if report_date == as_of_date and benchmark_report_change_pct:
        default_benchmark_return = benchmark_report_change_pct / 100.0
    else:
        default_benchmark_return = _compute_benchmark_return(report_date, as_of_date, benchmark_report_close)
    result["benchmark_return"] = default_benchmark_return
    result["alpha_return_best"] = result["strategy_return_best"] - default_benchmark_return
    result["alpha_return_worst"] = result["strategy_return_worst"] - default_benchmark_return

    if action_type != "execute":
        result.update(_compute_watch_outcome_metrics(record, as_of_date))
        result["status"] = action_type
        result["status_label"] = _get_strategy_status_label(action_type)
        return result

    stock_code = normalize_stock_code(record.get("stock_code", ""))
    if not stock_code:
        result["status"] = "invalid"
        result["status_label"] = _get_strategy_status_label("invalid")
        return result

    trade_bars = fetch_daily_price_bars(stock_code, report_date, as_of_date, is_index=False)
    trade_bar = _get_first_bar_after(trade_bars, report_date)
    if not trade_bar:
        result["status"] = "pending"
        result["status_label"] = _get_strategy_status_label("pending")
        return result

    trade_date = trade_bar.get("date", "")
    result["trade_date"] = trade_date

    entry_low = _safe_float(record.get("entry_range_low"))
    entry_high = _safe_float(record.get("entry_range_high"))
    if entry_low <= 0 or entry_high <= 0:
        entry_anchor = _safe_float(record.get("entry_price_anchor"))
        if entry_anchor > 0:
            entry_low = entry_high = entry_anchor

    if entry_low > entry_high > 0:
        entry_low, entry_high = entry_high, entry_low

    confirm_price = _safe_float(record.get("confirm_price_60m"))
    support_price = _safe_float(record.get("confirm_support_60m"))

    day_60m = [
        bar for bar in fetch_intraday_bars(stock_code, trade_date, period="60", lookback_bars=10)
        if _normalize_kline_date_str(bar.get("date")) == trade_date
    ]
    day_30m = [
        bar for bar in fetch_intraday_bars(stock_code, trade_date, period="30", lookback_bars=20)
        if _normalize_kline_date_str(bar.get("date")) == trade_date
    ]

    confirm_triggered = False
    confirm_datetime = ""
    if day_60m:
        result["used_intraday"] = True
        if confirm_price > 0:
            for bar in day_60m:
                high_price = _safe_float(bar.get("high"))
                low_price = _safe_float(bar.get("low"))
                close_price = _safe_float(bar.get("close"))
                if high_price >= confirm_price and (
                    support_price <= 0 or low_price >= support_price or close_price >= support_price
                ):
                    confirm_triggered = True
                    confirm_datetime = bar.get("datetime", "")
                    break
        else:
            confirm_triggered = True
            confirm_datetime = day_60m[0].get("datetime", "")

    if not confirm_triggered:
        day_high = _safe_float(trade_bar.get("high"))
        day_low = _safe_float(trade_bar.get("low"))
        day_close = _safe_float(trade_bar.get("close"))
        if (confirm_price <= 0 or day_high >= confirm_price) and (
            support_price <= 0 or day_low >= support_price or day_close >= support_price
        ):
            confirm_triggered = True
            confirm_datetime = trade_date

    result["confirm_triggered"] = confirm_triggered
    result["confirm_datetime"] = confirm_datetime
    if not confirm_triggered:
        result["status"] = "not_triggered"
        result["status_label"] = _get_strategy_status_label("not_triggered")
        return result

    entry_candidates = []
    if day_30m:
        result["used_intraday"] = True
        for bar in day_30m:
            bar_dt = str(bar.get("datetime", ""))
            if confirm_datetime and len(confirm_datetime) > 10 and bar_dt and bar_dt < confirm_datetime:
                continue
            high_price = _safe_float(bar.get("high"))
            low_price = _safe_float(bar.get("low"))
            if high_price >= entry_low and low_price <= entry_high:
                entry_candidates.append(bar)

    if entry_candidates:
        actual_entry_low = min(max(entry_low, _safe_float(bar.get("low"))) for bar in entry_candidates)
        actual_entry_high = max(min(entry_high, _safe_float(bar.get("high"))) for bar in entry_candidates)
    else:
        day_high = _safe_float(trade_bar.get("high"))
        day_low = _safe_float(trade_bar.get("low"))
        if day_high >= entry_low and day_low <= entry_high:
            actual_entry_low = max(entry_low, day_low)
            actual_entry_high = min(entry_high, day_high)
        else:
            result["status"] = "not_triggered"
            result["status_label"] = _get_strategy_status_label("not_triggered")
            return result

    if actual_entry_low <= 0 or actual_entry_high <= 0 or actual_entry_low > actual_entry_high:
        result["status"] = "not_triggered"
        result["status_label"] = _get_strategy_status_label("not_triggered")
        return result

    window_bars = [bar for bar in trade_bars if _normalize_kline_date_str(bar.get("date")) >= trade_date]
    if not window_bars:
        result["status"] = "pending"
        result["status_label"] = _get_strategy_status_label("pending")
        return result

    default_holding_days_min = globals().get("STRATEGY_HOLDING_DAYS_MIN", 3)
    default_holding_days_max = globals().get("STRATEGY_HOLDING_DAYS_MAX", 5)
    structure_stop = _safe_float(record.get("structure_stop_30m") or record.get("effective_stop"))
    best_exit = _simulate_exit_for_entry(
        actual_entry_low,
        window_bars,
        structure_stop=structure_stop,
        holding_days_min=record.get("holding_days_min", default_holding_days_min),
        holding_days_max=record.get("holding_days_max", default_holding_days_max),
        profit_take_pct=record.get("profit_take_pct", 0.05),
    )
    worst_exit = _simulate_exit_for_entry(
        actual_entry_high,
        window_bars,
        structure_stop=structure_stop,
        holding_days_min=record.get("holding_days_min", default_holding_days_min),
        holding_days_max=record.get("holding_days_max", default_holding_days_max),
        profit_take_pct=record.get("profit_take_pct", 0.05),
    )

    result["triggered"] = True
    result["status"] = worst_exit.get("status", "closed")
    if best_exit.get("status") == "open_mark_to_market" or worst_exit.get("status") == "open_mark_to_market":
        result["status"] = "open_mark_to_market"
    result["status_label"] = _get_strategy_status_label(result["status"])
    result["entry_price_best"] = round(actual_entry_low, 2)
    result["entry_price_worst"] = round(actual_entry_high, 2)
    result["exit_date"] = worst_exit.get("exit_date") or best_exit.get("exit_date") or ""
    result["exit_reason"] = worst_exit.get("exit_reason") or best_exit.get("exit_reason") or ""
    result["strategy_return_best"] = best_exit.get("return_pct", 0.0)
    result["strategy_return_worst"] = worst_exit.get("return_pct", 0.0)

    benchmark_end_date = result["exit_date"] or trade_date
    if report_date == benchmark_end_date and benchmark_report_change_pct:
        benchmark_return = benchmark_report_change_pct / 100.0
    else:
        benchmark_return = _compute_benchmark_return(report_date, benchmark_end_date, benchmark_report_close)
    result["benchmark_return"] = benchmark_return
    result["alpha_return_best"] = result["strategy_return_best"] - benchmark_return
    result["alpha_return_worst"] = result["strategy_return_worst"] - benchmark_return
    return result


def _collect_record_market_path_legacy_body(record, as_of_date):
    code = normalize_stock_code(record.get("stock_code", ""))
    report_date = _normalize_kline_date_str(record.get("report_date"))
    as_of_date = _normalize_kline_date_str(as_of_date)
    if not code or not report_date or not as_of_date:
        return {}

    sim = record.get("simulation", {}) or {}
    baseline_price = _safe_float(record.get("report_day_close") or record.get("entry_price_anchor"))
    start_date = report_date
    if sim.get("triggered"):
        entry_low = _safe_float(sim.get("entry_price_best"))
        entry_high = _safe_float(sim.get("entry_price_worst"))
        if entry_low > 0 and entry_high > 0:
            baseline_price = (entry_low + entry_high) / 2.0
        elif entry_low > 0 or entry_high > 0:
            baseline_price = max(entry_low, entry_high)
        start_date = _normalize_kline_date_str(sim.get("trade_date")) or report_date

    if baseline_price <= 0:
        return {}

    bars = fetch_daily_price_bars(code, start_date, as_of_date, is_index=False)
    bars = [
        bar for bar in bars or []
        if start_date <= _normalize_kline_date_str(bar.get("date")) <= as_of_date
    ]
    if not bars:
        return {}

    end_bar = _get_last_bar_on_or_before(bars, as_of_date) or bars[-1]
    end_close = _safe_float(end_bar.get("close"))
    observed_return = (end_close / baseline_price - 1) if end_close > 0 else None

    highs = [_safe_float(bar.get("high")) for bar in bars if _safe_float(bar.get("high")) > 0]
    lows = [_safe_float(bar.get("low")) for bar in bars if _safe_float(bar.get("low")) > 0]
    max_runup = (max(highs) / baseline_price - 1) if highs else None
    max_drawdown = (min(lows) / baseline_price - 1) if lows else None

    midpoint_return = None
    if sim.get("triggered"):
        midpoint_return = (
            _safe_float(sim.get("strategy_return_worst")) + _safe_float(sim.get("strategy_return_best"))
        ) / 2.0

    post_exit_extension = None
    exit_date = _normalize_kline_date_str(sim.get("exit_date"))
    if exit_date:
        post_exit_bars = [
            bar for bar in bars
            if _normalize_kline_date_str(bar.get("date")) > exit_date
        ]
        if post_exit_bars and midpoint_return is not None:
            post_exit_high = max(_safe_float(bar.get("high")) for bar in post_exit_bars if _safe_float(bar.get("high")) > 0)
            if post_exit_high > 0:
                post_exit_extension = post_exit_high / baseline_price - 1 - midpoint_return

    return {
        "baseline_price": round(baseline_price, 4),
        "observed_return": observed_return,
        "max_runup": max_runup,
        "max_drawdown": max_drawdown,
        "post_exit_extension": post_exit_extension,
    }


def _apply_yizi_chain_rules_legacy_body(records):
    prev_execute_record = None
    for record in sorted(records or [], key=lambda x: _normalize_kline_date_str(x.get("report_date"))):
        if record.get("action_type") != "execute":
            continue

        sim = record.get("simulation", {}) or {}
        report_day_is_one_word = bool(record.get("report_day_is_one_word"))
        same_stock_chain = (
            prev_execute_record
            and normalize_stock_code(prev_execute_record.get("stock_code")) == normalize_stock_code(record.get("stock_code"))
            and _is_next_trading_day(prev_execute_record.get("report_date"), record.get("report_date"))
        )
        prev_chain_valid = bool(prev_execute_record.get("chain_entry_valid")) if prev_execute_record else False
        prev_day_one_word = bool(prev_execute_record.get("report_day_is_one_word")) if prev_execute_record else False

        if report_day_is_one_word:
            if same_stock_chain and prev_chain_valid and not prev_day_one_word:
                sim["status"] = "continuation_only"
                sim["status_note"] = "昨日已是同一有效链，今天一字只计延续不计新开仓"
                sim["status_label"] = _get_strategy_status_label(sim["status"], sim["status_note"])
                sim["triggered"] = False
                sim["confirm_triggered"] = False
                sim["entry_price_best"] = None
                sim["entry_price_worst"] = None
                sim["strategy_return_best"] = 0.0
                sim["strategy_return_worst"] = 0.0
                sim["benchmark_return"] = 0.0
                sim["alpha_return_best"] = 0.0
                sim["alpha_return_worst"] = 0.0
                record["chain_entry_valid"] = True
            else:
                sim["status"] = "invalid_consecutive_one_word" if same_stock_chain and prev_day_one_word else "invalid_report_day_one_word"
                sim["status_note"] = "当日一字板，次日默认买不进去；连续一字链条不计收益"
                sim["status_label"] = _get_strategy_status_label(sim["status"], sim["status_note"])
                sim["triggered"] = False
                sim["confirm_triggered"] = False
                sim["entry_price_best"] = None
                sim["entry_price_worst"] = None
                sim["strategy_return_best"] = 0.0
                sim["strategy_return_worst"] = 0.0
                sim["benchmark_return"] = 0.0
                sim["alpha_return_best"] = 0.0
                sim["alpha_return_worst"] = 0.0
                record["chain_entry_valid"] = False
        else:
            record["chain_entry_valid"] = bool(sim.get("triggered"))
            sim["status_label"] = _get_strategy_status_label(sim.get("status"), sim.get("status_note", ""))

        record["simulation"] = sim
        prev_execute_record = record


def _get_recent_record_display_metrics_legacy_body(record):
    record = record or {}
    sim = record.get("simulation", {}) or {}
    strategy_return_worst = sim.get("strategy_return_worst")
    strategy_return_best = sim.get("strategy_return_best")
    benchmark_return = sim.get("benchmark_return")

    if record.get("action_type") != "execute":
        raw_benchmark_change_pct = record.get("benchmark_report_change_pct")
        if raw_benchmark_change_pct not in (None, ""):
            benchmark_return = _safe_float(raw_benchmark_change_pct) / 100.0

    alpha_return_worst = sim.get("alpha_return_worst")
    alpha_return_best = sim.get("alpha_return_best")
    if benchmark_return is not None:
        alpha_return_worst = _safe_float(strategy_return_worst) - _safe_float(benchmark_return)
        alpha_return_best = _safe_float(strategy_return_best) - _safe_float(benchmark_return)

    return {
        "strategy_return_worst": strategy_return_worst,
        "strategy_return_best": strategy_return_best,
        "benchmark_return": benchmark_return,
        "alpha_return_worst": alpha_return_worst,
        "alpha_return_best": alpha_return_best,
    }
