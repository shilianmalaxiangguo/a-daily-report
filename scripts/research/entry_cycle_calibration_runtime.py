from __future__ import annotations

from market_data.kline_dates import normalize_kline_date_str

__all__ = [
    "build_default_entry_cycle_calibrations",
    "build_entry_cycle_calibrations",
    "build_entry_cycle_case",
    "get_default_entry_cycle_cases",
    "render_entry_cycle_calibration_markdown",
]


DEFAULT_ENTRY_CYCLE_CASES = [
    {
        "name": "博杰股份",
        "code": "002975",
        "case_type": "success",
        "first_report_date": "2026-04-09",
        "first_report_date_source": "strategy_ledger",
        "breakout_date": "2026-04-17",
        "reference_price": 86.90,
        "case_note": "选出后多日震荡，04-17放量突破。",
    },
    {
        "name": "龙蟠科技",
        "code": "603906",
        "case_type": "success",
        "first_report_date": "2026-04-16",
        "first_report_date_source": "strategy_ledger",
        "breakout_date": "2026-04-22",
        "reference_price": 25.05,
        "case_note": "选出后先横住，04-22重新加速。",
    },
    {
        "name": "中嘉博创",
        "code": "000889",
        "case_type": "success",
        "first_report_date": "2026-04-10",
        "first_report_date_source": "strategy_ledger",
        "breakout_date": "2026-04-15",
        "reference_price": 4.35,
        "case_note": "选出后先急杀再修复，固定-5%会提前误杀。",
    },
    {
        "name": "石大胜华",
        "code": "603026",
        "case_type": "counterexample",
        "first_report_date": "2026-04-14",
        "first_report_date_source": "strategy_ledger",
        "reference_price": 98.52,
        "case_note": "先强后回，更多是震荡消耗与机会成本。",
    },
    {
        "name": "甘肃能源",
        "code": "000791",
        "case_type": "counterexample",
        "first_report_date": "2026-04-13",
        "first_report_date_source": "memory_manual",
        "reference_price": 8.00,
        "reclaim_zone_low": 8.34,
        "reclaim_zone_high": 8.42,
        "case_note": "外部记忆案例：次日摸到关键区但没有站稳。",
    },
    {
        "name": "津药药业",
        "code": "600488",
        "case_type": "counterexample",
        "first_report_date": "2026-04-03",
        "first_report_date_source": "strategy_ledger",
        "breakout_date": "2026-04-07",
        "reference_price": 6.97,
        "case_note": "快进快出型，爆发后很快回落，不能当趋势持有样本。",
    },
]


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _round_or_none(value, digits=2):
    if value is None:
        return None
    return round(_safe_float(value), digits)


def _pct(base, value):
    base = _safe_float(base)
    value = _safe_float(value)
    if base <= 0:
        return None
    return (value / base - 1.0) * 100.0


def _format_pct(value):
    if value is None:
        return "-"
    return f"{_safe_float(value):+.2f}%"


def _normalize_bar(bar):
    bar = dict(bar or {})
    return {
        "date": normalize_kline_date_str(bar.get("date")),
        "open": _safe_float(bar.get("open")),
        "high": _safe_float(bar.get("high")),
        "low": _safe_float(bar.get("low")),
        "close": _safe_float(bar.get("close")),
        "volume": _safe_float(bar.get("volume")),
    }


def _prepare_bars(bars):
    normalized = [_normalize_bar(item) for item in (bars or [])]
    return [item for item in sorted(normalized, key=lambda x: x.get("date", "")) if item.get("date")]


def _first_on_or_after(bars, target_date):
    target_date = normalize_kline_date_str(target_date)
    for bar in bars:
        if bar.get("date") >= target_date:
            return bar
    return None


def _latest_on_or_before(bars, target_date):
    target_date = normalize_kline_date_str(target_date)
    result = None
    for bar in bars:
        if bar.get("date") <= target_date:
            result = bar
        else:
            break
    return result


def _slice_after_selection(bars, first_report_date, end_date=""):
    first_report_date = normalize_kline_date_str(first_report_date)
    end_date = normalize_kline_date_str(end_date)
    return [
        bar
        for bar in bars
        if bar.get("date") > first_report_date and (not end_date or bar.get("date") <= end_date)
    ]


def _has_reclaim_failure(case, path_bars):
    zone_low = _safe_float(case.get("reclaim_zone_low"))
    if zone_low <= 0:
        return False
    for bar in path_bars or []:
        if _safe_float(bar.get("high")) >= zone_low and _safe_float(bar.get("close")) < zone_low:
            return True
    return False


def _build_day_rows(path_bars, reference_price):
    rows = []
    previous_close = None
    for idx, bar in enumerate(path_bars or [], start=1):
        close_price = _safe_float(bar.get("close"))
        daily_change = _pct(previous_close, close_price) if previous_close else None
        rows.append({
            "date": bar.get("date", ""),
            "open": _round_or_none(bar.get("open")),
            "high": _round_or_none(bar.get("high")),
            "low": _round_or_none(bar.get("low")),
            "close": _round_or_none(close_price),
            "daily_change_pct": _round_or_none(daily_change),
            "cum_change_pct": _round_or_none(_pct(reference_price, close_price)),
            "amplitude_pct": _round_or_none(_pct(reference_price, _safe_float(bar.get("high"))) - _pct(reference_price, _safe_float(bar.get("low")))),
            "trading_day_index": idx,
        })
        previous_close = close_price
    return rows


def _build_interpretation(case, fixed_stop_result, recommended_stop_mode, max_drawdown, breakout_return):
    name = case.get("name", "-")
    if recommended_stop_mode == "structure_repair_band":
        return f"{name}说明固定-5%会误杀：先看收盘修复和后续再突破，不能只看盘中刺穿。"
    if recommended_stop_mode == "reclaim_failure_exit":
        low = case.get("reclaim_zone_low")
        high = case.get("reclaim_zone_high")
        zone = f"{low:.2f}-{high:.2f}" if isinstance(low, (int, float)) and isinstance(high, (int, float)) else "关键区"
        return f"{name}没有站稳{zone}，即使没触发-5%，也应该按关键区失败降级。"
    if recommended_stop_mode == "a_kill_exit":
        return f"{name}已经出现结构失真，固定-5%只是滞后的风险提示，应该更早按A杀出清。"
    if case.get("case_type") == "counterexample":
        return f"{name}不是趋势持有样本，重点是时间止损和机会成本，不是等待固定-5%。"
    return f"{name}的回撤在可承受区间内，后续突破才是介入周期完成信号。"


def get_default_entry_cycle_cases():
    return [dict(item) for item in DEFAULT_ENTRY_CYCLE_CASES]


def build_entry_cycle_case(case, bars):
    case = dict(case or {})
    prepared_bars = _prepare_bars(bars)
    first_report_date = normalize_kline_date_str(case.get("first_report_date"))
    breakout_date = normalize_kline_date_str(case.get("breakout_date"))
    as_of_date = normalize_kline_date_str(case.get("as_of_date")) or (prepared_bars[-1].get("date") if prepared_bars else "")
    cycle_end_date = breakout_date or as_of_date
    selected_bar = _first_on_or_after(prepared_bars, first_report_date)
    latest_bar = _latest_on_or_before(prepared_bars, as_of_date) or (prepared_bars[-1] if prepared_bars else None)
    reference_price = _safe_float(case.get("reference_price")) or _safe_float((selected_bar or {}).get("close"))

    path_bars = _slice_after_selection(prepared_bars, first_report_date, end_date=cycle_end_date)
    full_path_bars = _slice_after_selection(prepared_bars, first_report_date, end_date=as_of_date)
    pre_breakout_bars = [
        bar
        for bar in path_bars
        if not breakout_date or bar.get("date") < breakout_date
    ]
    vibration_bars = pre_breakout_bars or path_bars
    min_low = min((_safe_float(bar.get("low")) for bar in vibration_bars), default=None)
    max_high = max((_safe_float(bar.get("high")) for bar in vibration_bars), default=None)
    breakout_bar = _first_on_or_after(prepared_bars, breakout_date) if breakout_date else None

    max_drawdown = _pct(reference_price, min_low) if min_low is not None else None
    max_runup = _pct(reference_price, max_high) if max_high is not None else None
    range_amplitude = (max_runup - max_drawdown) if max_runup is not None and max_drawdown is not None else None
    breakout_return = _pct(reference_price, (breakout_bar or {}).get("close")) if breakout_bar else None
    fixed_scope_bars = full_path_bars if case.get("case_type") == "counterexample" else vibration_bars
    min_low_for_fixed = min((_safe_float(bar.get("low")) for bar in fixed_scope_bars), default=min_low)
    fixed_stop_touched = bool(min_low_for_fixed is not None and reference_price > 0 and min_low_for_fixed <= reference_price * 0.95)
    reclaim_failed = _has_reclaim_failure(case, full_path_bars)

    if fixed_stop_touched and case.get("case_type") == "success" and breakout_return is not None and breakout_return > 0:
        fixed_stop_result = "would_false_kill"
    elif fixed_stop_touched:
        fixed_stop_result = "would_cut_loss"
    elif case.get("case_type") == "counterexample" and reclaim_failed:
        fixed_stop_result = "would_not_warn"
    else:
        fixed_stop_result = "would_survive"

    if fixed_stop_result == "would_false_kill":
        recommended_stop_mode = "structure_repair_band"
    elif reclaim_failed and case.get("case_type") == "counterexample":
        recommended_stop_mode = "reclaim_failure_exit"
    elif fixed_stop_result == "would_cut_loss":
        recommended_stop_mode = "a_kill_exit"
    elif case.get("case_type") == "counterexample":
        recommended_stop_mode = "time_stop_or_downgrade"
    else:
        recommended_stop_mode = "structure_band"

    return {
        "name": case.get("name", ""),
        "code": case.get("code", ""),
        "case_type": case.get("case_type", ""),
        "first_report_date": first_report_date,
        "first_report_date_source": case.get("first_report_date_source", ""),
        "breakout_date": breakout_date,
        "as_of_date": as_of_date,
        "reference_price": _round_or_none(reference_price),
        "latest_close": _round_or_none((latest_bar or {}).get("close")),
        "cycle_gap_trading_days": len(path_bars),
        "max_drawdown_before_breakout_pct": _round_or_none(max_drawdown),
        "max_runup_before_breakout_pct": _round_or_none(max_runup),
        "range_amplitude_pct": _round_or_none(range_amplitude),
        "breakout_return_pct": _round_or_none(breakout_return),
        "fixed_5pct_stop_result": fixed_stop_result,
        "recommended_stop_mode": recommended_stop_mode,
        "interpretation": _build_interpretation(case, fixed_stop_result, recommended_stop_mode, max_drawdown, breakout_return),
        "case_note": case.get("case_note", ""),
        "day_rows": _build_day_rows(full_path_bars, reference_price),
    }


def build_entry_cycle_calibrations(cases, bars_by_code, as_of_date=""):
    results = []
    for case in cases or []:
        prepared_case = dict(case or {})
        if as_of_date:
            prepared_case["as_of_date"] = as_of_date
        results.append(build_entry_cycle_case(prepared_case, (bars_by_code or {}).get(prepared_case.get("code"), [])))
    return {
        "as_of_date": normalize_kline_date_str(as_of_date),
        "cases": results,
    }


def build_default_entry_cycle_calibrations(as_of_date="2026-04-24", fetch_daily_price_bars_fn=None):
    if fetch_daily_price_bars_fn is None:
        from market_data.daily_price_runtime import fetch_daily_price_bars as fetch_daily_price_bars_fn

    bars_by_code = {}
    for case in DEFAULT_ENTRY_CYCLE_CASES:
        start_date = case.get("first_report_date")
        bars_by_code[case["code"]] = fetch_daily_price_bars_fn(
            case["code"],
            start_date,
            as_of_date,
            prefer_fast=True,
        )
    return build_entry_cycle_calibrations(get_default_entry_cycle_cases(), bars_by_code, as_of_date=as_of_date)


def render_entry_cycle_calibration_markdown(calibration):
    calibration = calibration or {}
    cases = calibration.get("cases", []) or []
    lines = [
        "# 介入周期校准",
        "",
        "结论：固定 -5% 不能作为统一止损；成功样本看结构修复与再突破，反例样本看关键区失败、时间消耗和A杀。",
        "",
        "| 标的 | 类型 | 入选日 | 爆发/验证日 | 介入周期 | 最大回撤 | 最大上冲 | 振幅 | 固定-5%结果 | 建议模式 | 结论 |",
        "|------|------|--------|-------------|----------|----------|----------|------|--------------|----------|------|",
    ]
    type_label = {"success": "成功", "counterexample": "反例"}
    stop_label = {
        "would_false_kill": "会误杀",
        "would_cut_loss": "会止损",
        "would_not_warn": "不预警",
        "would_survive": "可存活",
    }
    mode_label = {
        "structure_repair_band": "结构修复带",
        "reclaim_failure_exit": "关键区失败退出",
        "a_kill_exit": "A杀出清",
        "time_stop_or_downgrade": "时间止损/降级",
        "structure_band": "结构容忍带",
    }
    for item in cases:
        lines.append(
            "| {name}({code}) | {case_type} | {first_date} | {breakout_date} | {gap}日 | {drawdown} | {runup} | {amplitude} | {fixed} | {mode} | {interpretation} |".format(
                name=item.get("name", "-"),
                code=item.get("code", "-"),
                case_type=type_label.get(item.get("case_type"), item.get("case_type", "-")),
                first_date=item.get("first_report_date", "-"),
                breakout_date=item.get("breakout_date") or item.get("as_of_date") or "-",
                gap=item.get("cycle_gap_trading_days", "-"),
                drawdown=_format_pct(item.get("max_drawdown_before_breakout_pct")),
                runup=_format_pct(item.get("max_runup_before_breakout_pct")),
                amplitude=_format_pct(item.get("range_amplitude_pct")),
                fixed=stop_label.get(item.get("fixed_5pct_stop_result"), item.get("fixed_5pct_stop_result", "-")),
                mode=mode_label.get(item.get("recommended_stop_mode"), item.get("recommended_stop_mode", "-")),
                interpretation=item.get("interpretation", "-"),
            )
        )
    lines.append("")
    for item in cases:
        rows = item.get("day_rows", []) or []
        if not rows:
            continue
        lines.extend([
            f"## {item.get('name', '-') }({item.get('code', '-')}) 日K路径",
            "",
            "| 日期 | 开盘 | 最高 | 最低 | 收盘 | 日涨幅 | 累计涨幅 | 单日振幅 |",
            "|------|------|------|------|------|--------|----------|----------|",
        ])
        for row in rows:
            lines.append(
                f"| {row.get('date', '-')} | {row.get('open', '-')} | {row.get('high', '-')} | {row.get('low', '-')} | {row.get('close', '-')} | {_format_pct(row.get('daily_change_pct'))} | {_format_pct(row.get('cum_change_pct'))} | {_format_pct(row.get('amplitude_pct'))} |"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
