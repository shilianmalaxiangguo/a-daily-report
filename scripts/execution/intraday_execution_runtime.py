from __future__ import annotations

import daily_report_analysis_utils as analysis_utils
from execution.entry_cycle_stop_runtime import build_entry_cycle_stop_policy, resolve_entry_cycle_profile
from market_data.kline_dates import normalize_kline_date_str as _normalize_kline_date_str
from market_data.tushare_minute_service import fetch_tushare_minute_bars

__all__ = [
    "build_intraday_execution_plan",
    "build_waiting_stock_plan",
    "compute_avg_volume",
    "fetch_intraday_bars",
    "fetch_tushare_minute_bars",
    "find_latest_intraday_pivot",
]

INTRADAY_CONFIRM_LOOKBACK_60M = 8
INTRADAY_STOP_LOOKBACK_30M = 12
MAX_SINGLE_TRADE_LOSS_PCT = analysis_utils.MAX_SINGLE_TRADE_LOSS_PCT
_MISSING = object()
_intraday_bar_cache = {}


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


def fetch_intraday_bars(stock_code, target_date, period="30", lookback_bars=12, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _fetch_intraday_bars_legacy_body(
            stock_code,
            target_date,
            period=period,
            lookback_bars=lookback_bars,
        )
    finally:
        _restore_runtime_bindings(previous)


def build_stop_execution_plan(entry_price, structure_stop=None, structure_label="结构止损"):
    return analysis_utils.build_stop_execution_plan(
        entry_price,
        structure_stop=structure_stop,
        structure_label=structure_label,
    )


def enrich_stop_plan_with_reference_anchors(stop_plan, stock_code, target_date, recent_bars=None):
    _ = stock_code, target_date, recent_bars
    return stop_plan


def find_latest_intraday_pivot(bars, mode="low", *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _find_latest_intraday_pivot_legacy_body(bars, mode=mode)
    finally:
        _restore_runtime_bindings(previous)


def compute_avg_volume(bars, sample_size=5, exclude_last=False, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _compute_avg_volume_legacy_body(
            bars,
            sample_size=sample_size,
            exclude_last=exclude_last,
        )
    finally:
        _restore_runtime_bindings(previous)


def build_intraday_execution_plan(stock_code, target_date, entry_price, signal_type="", fallback_stop=None, entry_cycle_profile=None, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _build_intraday_execution_plan_legacy_body(
            stock_code,
            target_date,
            entry_price,
            signal_type=signal_type,
            fallback_stop=fallback_stop,
            entry_cycle_profile=entry_cycle_profile,
        )
    finally:
        _restore_runtime_bindings(previous)


def build_waiting_stock_plan(stock_item, target_date, reason="", signal_type="", recent_bars=None, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _build_waiting_stock_plan_legacy_body(
            stock_item,
            target_date,
            reason=reason,
            signal_type=signal_type,
            recent_bars=recent_bars,
        )
    finally:
        _restore_runtime_bindings(previous)


def _fetch_intraday_bars(stock_code, target_date, period="30", lookback_bars=12):
    return _fetch_intraday_bars_legacy_body(
        stock_code,
        target_date,
        period=period,
        lookback_bars=lookback_bars,
    )


def _find_latest_intraday_pivot(bars, mode="low"):
    return _find_latest_intraday_pivot_legacy_body(bars, mode=mode)


def _compute_avg_volume(bars, sample_size=5, exclude_last=False):
    return _compute_avg_volume_legacy_body(
        bars,
        sample_size=sample_size,
        exclude_last=exclude_last,
    )


def _build_intraday_execution_plan(stock_code, target_date, entry_price, signal_type="", fallback_stop=None, entry_cycle_profile=None):
    return _build_intraday_execution_plan_legacy_body(
        stock_code,
        target_date,
        entry_price,
        signal_type=signal_type,
        fallback_stop=fallback_stop,
        entry_cycle_profile=entry_cycle_profile,
    )


def _build_waiting_stock_plan(stock_item, target_date, reason="", signal_type="", recent_bars=None):
    return _build_waiting_stock_plan_legacy_body(
        stock_item,
        target_date,
        reason=reason,
        signal_type=signal_type,
        recent_bars=recent_bars,
    )


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _normalize_stock_code(stock_code):
    return analysis_utils.normalize_stock_code(stock_code)


def _fetch_intraday_bars_legacy_body(stock_code, target_date, period="30", lookback_bars=12):
    code = _normalize_stock_code(stock_code)
    normalized_target = _normalize_kline_date_str(target_date)
    period = str(period)
    cache_key = (code, normalized_target, period, lookback_bars)
    if cache_key in _intraday_bar_cache:
        return list(_intraday_bar_cache[cache_key])

    if not code or not normalized_target:
        return []

    cleaned = []
    try:
        cleaned = fetch_tushare_minute_bars(
            code,
            period=period,
            target_date=normalized_target,
            is_index=False,
        )
    except Exception:
        cleaned = []

    if cleaned:
        result = cleaned[-lookback_bars:] if lookback_bars and len(cleaned) > lookback_bars else cleaned
        _intraday_bar_cache[cache_key] = list(result)
        return result

    try:
        import akshare as ak

        df = ak.stock_zh_a_hist_min_em(symbol=code, period=period, adjust="")
        records = df.to_dict("records") if df is not None else []
        if records:
            for row in records:
                dt_text = str(row.get("时间", "") or "").strip()
                if not dt_text:
                    continue
                date_text = _normalize_kline_date_str(dt_text.split(" ")[0])
                if not date_text or date_text > normalized_target:
                    continue
                cleaned.append(
                    {
                        "datetime": dt_text,
                        "date": date_text,
                        "open": _safe_float(row.get("开盘", 0)),
                        "high": _safe_float(row.get("最高", 0)),
                        "low": _safe_float(row.get("最低", 0)),
                        "close": _safe_float(row.get("收盘", 0)),
                        "volume": _safe_float(row.get("成交量", 0)),
                        "amount": _safe_float(row.get("成交额", 0)),
                    }
                )
    except Exception:
        cleaned = []

    result = cleaned[-lookback_bars:] if lookback_bars and len(cleaned) > lookback_bars else cleaned
    _intraday_bar_cache[cache_key] = list(result)
    return result


def _find_latest_intraday_pivot_legacy_body(bars, mode="low"):
    if not bars:
        return None, None

    field = "low" if mode == "low" else "high"
    comparator = min if mode == "low" else max

    for idx in range(len(bars) - 2, 0, -1):
        prev_val = float(bars[idx - 1].get(field) or 0)
        curr_val = float(bars[idx].get(field) or 0)
        next_val = float(bars[idx + 1].get(field) or 0)
        if curr_val <= 0:
            continue

        if mode == "low":
            is_pivot = curr_val <= prev_val and curr_val <= next_val and (curr_val < prev_val or curr_val < next_val)
        else:
            is_pivot = curr_val >= prev_val and curr_val >= next_val and (curr_val > prev_val or curr_val > next_val)

        if is_pivot:
            return round(curr_val, 2), bars[idx].get("datetime") or bars[idx].get("date")

    recent = bars[-4:] if len(bars) >= 4 else bars
    values = [float(b.get(field) or 0) for b in recent if float(b.get(field) or 0) > 0]
    if not values:
        return None, None

    fallback_value = round(comparator(values), 2)
    for bar in reversed(recent):
        val = round(float(bar.get(field) or 0), 2)
        if abs(val - fallback_value) < 1e-9:
            return fallback_value, bar.get("datetime") or bar.get("date")
    return fallback_value, recent[-1].get("datetime") or recent[-1].get("date")


def _compute_avg_volume_legacy_body(bars, sample_size=5, exclude_last=False):
    sample = bars[:-1] if exclude_last and len(bars) > 1 else bars
    if not sample:
        return 0.0
    sample = sample[-sample_size:] if len(sample) > sample_size else sample
    vols = [float(bar.get("volume") or 0) for bar in sample if float(bar.get("volume") or 0) >= 0]
    return sum(vols) / len(vols) if vols else 0.0


def _build_intraday_execution_plan_legacy_body(stock_code, target_date, entry_price, signal_type="", fallback_stop=None, entry_cycle_profile=None):
    try:
        entry = float(entry_price or 0)
    except (TypeError, ValueError):
        entry = 0

    if entry <= 0:
        return {}

    bars_60m = fetch_intraday_bars(
        stock_code,
        target_date,
        period="60",
        lookback_bars=INTRADAY_CONFIRM_LOOKBACK_60M,
    )
    bars_30m = fetch_intraday_bars(
        stock_code,
        target_date,
        period="30",
        lookback_bars=INTRADAY_STOP_LOOKBACK_30M,
    )

    latest_60m = bars_60m[-1] if bars_60m else None
    latest_30m = bars_30m[-1] if bars_30m else None

    support_60m, support_60m_dt = _find_latest_intraday_pivot(bars_60m, mode="low")
    recent_high_60m, recent_high_60m_dt = _find_latest_intraday_pivot(bars_60m, mode="high")
    structure_stop_30m, structure_stop_30m_dt = _find_latest_intraday_pivot(bars_30m, mode="low")

    if structure_stop_30m is None and fallback_stop:
        try:
            structure_stop_30m = round(float(fallback_stop), 2)
        except (TypeError, ValueError):
            structure_stop_30m = None

    if support_60m is None and structure_stop_30m is not None:
        support_60m = structure_stop_30m
        support_60m_dt = structure_stop_30m_dt

    recent_high_60m = recent_high_60m or round(entry, 2)
    confirm_price_60m = round(max(entry, recent_high_60m), 2)
    confirm_inputs_60m = {
        "entry_price": round(entry, 2),
        "recent_high": round(recent_high_60m, 2),
    }

    latest_60m_close = round(float(latest_60m.get("close") or 0), 2) if latest_60m else None
    latest_60m_open = round(float(latest_60m.get("open") or 0), 2) if latest_60m else None
    latest_60m_high = round(float(latest_60m.get("high") or 0), 2) if latest_60m else None
    latest_60m_low = round(float(latest_60m.get("low") or 0), 2) if latest_60m else None

    avg_volume_60m = _compute_avg_volume(bars_60m, sample_size=5, exclude_last=True)
    volume_ratio_60m = None
    if latest_60m and avg_volume_60m > 0:
        volume_ratio_60m = round(float(latest_60m.get("volume") or 0) / avg_volume_60m, 2)

    if signal_type == "breakout":
        confirm_rule = f"首个60分钟放量站上{confirm_price_60m:.2f}"
        if support_60m:
            confirm_rule += f"，且不破{support_60m:.2f}"
        confirm_state = "60分钟突破雏形" if (
            latest_60m_close and latest_60m_close >= entry and (volume_ratio_60m or 0) >= 1.0
        ) else "等待60分钟放量确认"
    elif signal_type == "panic_buy":
        confirm_rule = f"首个60分钟不破{support_60m:.2f}并收回{confirm_price_60m:.2f}" if support_60m else f"首个60分钟收回{confirm_price_60m:.2f}"
        confirm_state = "60分钟尾盘已回稳" if (
            latest_60m_close and latest_60m_open and latest_60m_close >= latest_60m_open
        ) else "等待60分钟转强"
    elif signal_type == "sweet_zone":
        confirm_rule = f"首个60分钟回踩不破{support_60m:.2f}后再站上{confirm_price_60m:.2f}" if support_60m else f"首个60分钟站上{confirm_price_60m:.2f}"
        confirm_state = "60分钟尾盘偏强" if (
            latest_60m_close and latest_60m_open and latest_60m_close >= latest_60m_open
        ) else "60分钟仍待确认"
    else:
        confirm_rule = f"首个60分钟站上{confirm_price_60m:.2f}"
        if support_60m:
            confirm_rule += f"，且不破{support_60m:.2f}"
        confirm_state = "可按60分钟确认" if latest_60m_close else "分钟数据不足"

    stop_plan = build_stop_execution_plan(
        entry,
        structure_stop_30m,
        structure_label="30分钟结构止损",
    )
    entry_cycle_stop_policy = build_entry_cycle_stop_policy(entry, stop_plan, entry_cycle_profile)
    confirm_basis_60m = "entry_cycle_calibrated" if entry_cycle_stop_policy else "entry_or_recent_high"

    return {
        "bars_60m": bars_60m,
        "bars_30m": bars_30m,
        "latest_60m_datetime": latest_60m.get("datetime") if latest_60m else "",
        "latest_60m_close": latest_60m_close,
        "latest_60m_high": latest_60m_high,
        "latest_60m_low": latest_60m_low,
        "latest_30m_datetime": latest_30m.get("datetime") if latest_30m else "",
        "confirm_price_60m": confirm_price_60m,
        "confirm_basis_60m": confirm_basis_60m,
        "confirm_inputs_60m": confirm_inputs_60m,
        "confirm_support_60m": support_60m,
        "confirm_support_60m_datetime": support_60m_dt,
        "confirm_high_60m_datetime": recent_high_60m_dt,
        "confirm_rule_60m": confirm_rule,
        "confirm_state_60m": confirm_state,
        "volume_ratio_60m": volume_ratio_60m,
        "structure_stop_30m": structure_stop_30m,
        "structure_stop_30m_datetime": structure_stop_30m_dt,
        "stop_plan": stop_plan,
        "entry_cycle_stop_policy": entry_cycle_stop_policy,
    }


def _build_waiting_stock_plan_legacy_body(stock_item, target_date, reason="", signal_type="", recent_bars=None):
    stock_item = stock_item or {}
    code = stock_item.get("code", "")
    try:
        entry_price = float(stock_item.get("close", 0) or stock_item.get("entry_price", 0) or 0)
    except (TypeError, ValueError):
        entry_price = 0.0

    entry_cycle_profile = resolve_entry_cycle_profile(code, stock_item.get("entry_cycle_profile"))
    minute_plan_kwargs = {
        "signal_type": signal_type,
        "fallback_stop": entry_price * (1 - MAX_SINGLE_TRADE_LOSS_PCT) if entry_price > 0 else None,
    }
    if entry_cycle_profile:
        minute_plan_kwargs["entry_cycle_profile"] = entry_cycle_profile
    minute_plan = build_intraday_execution_plan(
        code,
        target_date,
        entry_price,
        **minute_plan_kwargs,
    )
    stop_plan = minute_plan.get("stop_plan") or build_stop_execution_plan(entry_price)
    stop_plan = enrich_stop_plan_with_reference_anchors(
        stop_plan,
        code,
        target_date,
        recent_bars=recent_bars,
    )
    return {
        **stock_item,
        "entry_price": entry_price,
        "reason": reason or stock_item.get("reason") or stock_item.get("condition", "等待信号"),
        "minute_plan": minute_plan,
        "stop_plan": stop_plan,
        "stop_loss": stop_plan["effective_stop"] if stop_plan else 0,
    }
