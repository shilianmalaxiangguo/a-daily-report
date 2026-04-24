from __future__ import annotations

import daily_report_analysis_utils as analysis_utils
from market_data.daily_price_runtime import fetch_recent_price_bars as _default_fetch_recent_price_bars
from market_data.kline_dates import normalize_kline_date_str as _default_normalize_kline_date_str
from market_data.kline_dates import parse_kline_date as _default_parse_kline_date
from selection.candidate_execution_contracts import (
    resolve_candidate_follow_state as _default_resolve_candidate_follow_state,
    resolve_candidate_setup_id as _default_resolve_candidate_setup_id,
)

__all__ = [
    "build_trend_continuation_context",
    "build_washout_reclaim_context",
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


def normalize_stock_code(code):
    return analysis_utils.normalize_stock_code(code)


def _candidate_matches_mainline(candidate, mainline_name=""):
    return analysis_utils._candidate_matches_mainline(candidate, mainline_name)


def _resolve_candidate_setup_id(candidate):
    return _default_resolve_candidate_setup_id(candidate)


def _resolve_candidate_follow_state(candidate):
    return _default_resolve_candidate_follow_state(candidate)


def _normalize_kline_date_str(value):
    return _default_normalize_kline_date_str(value)


def _parse_kline_date(value):
    return _default_parse_kline_date(value)


def fetch_recent_price_bars(code, target_date, lookback_days=4, fast_fail=True):
    return _default_fetch_recent_price_bars(code, target_date, lookback_days=lookback_days, fast_fail=fast_fail)


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


def build_washout_reclaim_context(candidate, mainline_name="", conviction_codes=None, leader_memory_codes=None, target_date="", *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _build_washout_reclaim_context_legacy_body(
            candidate,
            mainline_name=mainline_name,
            conviction_codes=conviction_codes,
            leader_memory_codes=leader_memory_codes,
            target_date=target_date,
        )
    finally:
        _restore_runtime_bindings(previous)


def build_trend_continuation_context(candidate, mainline_name="", conviction_codes=None, leader_memory_codes=None, target_date="", *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _build_trend_continuation_context_legacy_body(
            candidate,
            mainline_name=mainline_name,
            conviction_codes=conviction_codes,
            leader_memory_codes=leader_memory_codes,
            target_date=target_date,
        )
    finally:
        _restore_runtime_bindings(previous)


def _is_washout_reclaim_setup_id(setup_id=""):
    return str(setup_id or "").strip() in ("burst_hold", "upper_shadow_reclaim", "horror_wash_hold")


def _build_washout_reclaim_context_legacy_body(candidate, mainline_name="", conviction_codes=None, leader_memory_codes=None, target_date=""):
    candidate = candidate or {}
    conviction_codes = conviction_codes or set()
    leader_memory_codes = leader_memory_codes or set()
    setup_id = _resolve_candidate_setup_id(candidate)
    follow_state = _resolve_candidate_follow_state(candidate)
    code = normalize_stock_code(candidate.get("code", ""))
    is_mainline = bool(candidate.get("is_mainline")) or _candidate_matches_mainline(candidate, mainline_name)
    is_conviction = code in conviction_codes
    is_memory = code in leader_memory_codes
    abnormal_date = _normalize_kline_date_str(candidate.get("abnormal_date"))
    target_date = _normalize_kline_date_str(target_date)
    subtype = str(candidate.get("washout_reclaim_subtype") or candidate.get("abnormal_subtype") or "").strip()
    subtype_label_map = {
        "entity_bear_reclaim": "实体阴线后反包",
        "upper_shadow_eat": "上影线后吃上影",
        "gap_reclaim": "向下跳空+向上跳空",
        "flush_open_reclaim": "一步到位低开高走",
    }
    subtype_label = subtype_label_map.get(subtype, "")

    active = _is_washout_reclaim_setup_id(setup_id) and follow_state == "跌不下去"
    recognition_ok = bool(is_mainline or is_conviction or is_memory)
    days_since_abnormal = None
    within_3d_window = False
    if abnormal_date and target_date:
        abnormal_dt = _parse_kline_date(abnormal_date)
        target_dt = _parse_kline_date(target_date)
        if abnormal_dt and target_dt and target_dt >= abnormal_dt:
            days_since_abnormal = (target_dt - abnormal_dt).days
            within_3d_window = days_since_abnormal <= 3

    note = ""
    action_bias = ""
    if active:
        subtype_prefix = f"{subtype_label}，" if subtype_label else ""
        if recognition_ok and within_3d_window:
            note = f"{subtype_prefix}洗盘完成型修复，重点看三日内快速收复，不拖节奏。"
            action_bias = f"{subtype_prefix}洗盘完成型异动已进入三日内快速修复窗口，优先观察是否继续强化。"
        elif recognition_ok:
            note = f"{subtype_prefix}洗盘完成型修复，但已经超出三日快速修复窗口，后续若再动更像新周期，不按原节奏硬等。"
            action_bias = f"{subtype_prefix}洗盘完成型异动已过快速修复窗口，不能再把旧异动当作当前主驱动。"
        else:
            note = f"{subtype_prefix}洗盘完成型异动，但缺少辨识度/记忆资产前提，只能做背景观察，不提级。"
            action_bias = f"{subtype_prefix}缺少辨识度前提，洗盘修复只能看，不能按狙击手主目标处理。"

    return {
        "active": active,
        "recognition_ok": recognition_ok,
        "is_mainline": is_mainline,
        "is_conviction": is_conviction,
        "is_memory": is_memory,
        "days_since_abnormal": days_since_abnormal,
        "within_3d_window": within_3d_window,
        "stage_label": "洗盘完成型修复" if active else "",
        "subtype": subtype,
        "subtype_label": subtype_label,
        "note": note,
        "action_bias": action_bias,
    }


def _build_trend_continuation_context_legacy_body(candidate, mainline_name="", conviction_codes=None, leader_memory_codes=None, target_date=""):
    candidate = candidate or {}
    conviction_codes = conviction_codes or set()
    leader_memory_codes = leader_memory_codes or set()
    code = normalize_stock_code(candidate.get("code", ""))
    is_mainline = bool(candidate.get("is_mainline")) or _candidate_matches_mainline(candidate, mainline_name)
    is_conviction = code in conviction_codes
    is_memory = code in leader_memory_codes
    recognition_ok = bool(is_mainline or is_conviction or is_memory)

    recent_bars = list(candidate.get("recent_bars") or [])
    target_date = _normalize_kline_date_str(target_date)
    if not recent_bars and code and target_date:
        recent_bars = fetch_recent_price_bars(code, target_date, lookback_days=4, fast_fail=True)
    recent_bars = [bar for bar in recent_bars if _normalize_kline_date_str(bar.get("date"))]
    recent_bars = sorted(recent_bars, key=lambda x: _normalize_kline_date_str(x.get("date")))[-4:]

    act_right = False
    near_new_high = False
    active = False
    latest_close = 0.0
    if len(recent_bars) >= 3:
        closes = [_safe_float(bar.get("close")) for bar in recent_bars if _safe_float(bar.get("close")) > 0]
        highs = [_safe_float(bar.get("high")) for bar in recent_bars if _safe_float(bar.get("high")) > 0]
        lows = [_safe_float(bar.get("low")) for bar in recent_bars if _safe_float(bar.get("low")) > 0]
        latest_bar = recent_bars[-1]
        prev_bar = recent_bars[-2]
        latest_close = _safe_float(latest_bar.get("close"))
        latest_high = _safe_float(latest_bar.get("high"))
        prev_close = _safe_float(prev_bar.get("close"))
        prev_lows = lows[:-1] if len(lows) >= 2 else []
        rise_count = 0
        for idx in range(1, len(closes)):
            if closes[idx] >= closes[idx - 1] * 0.995:
                rise_count += 1
        act_right = rise_count >= max(2, len(closes) - 2) and latest_close >= prev_close * 0.995
        if prev_lows:
            act_right = act_right and _safe_float(latest_bar.get("low")) >= min(prev_lows) * 0.98
        prior_highs = highs[:-1] if len(highs) >= 2 else []
        if prior_highs and latest_high > 0:
            near_new_high = latest_high >= max(prior_highs) * 0.995 or latest_close >= max(prior_highs) * 0.985
        active = recognition_ok and act_right and near_new_high

    note = ""
    action_bias = ""
    if recognition_ok and act_right and near_new_high:
        note = "趋势续强，连续 act right，重点看是否继续创高。"
        action_bias = "高辨识度强趋势对象持续 act right，优先看顺势确认，不按普通观察票处理。"
    elif recognition_ok and act_right:
        note = "趋势未坏，但还没重新逼近新高，先等再次证明自己。"
        action_bias = "先等靠近关键高点再确认，不提前把趋势续强写成执行。"
    elif recognition_ok:
        note = "有辨识度，但最近没有连续 act right，先别按趋势续强处理。"
        action_bias = "趋势续强链暂未成立，避免把记忆资产错当成继续领涨。"

    return {
        "active": active,
        "recognition_ok": recognition_ok,
        "is_mainline": is_mainline,
        "is_conviction": is_conviction,
        "is_memory": is_memory,
        "act_right": act_right,
        "near_new_high": near_new_high,
        "latest_close": _round_or_none(latest_close) if latest_close > 0 else None,
        "stage_label": "趋势续强" if active else "",
        "note": note,
        "action_bias": action_bias,
    }
