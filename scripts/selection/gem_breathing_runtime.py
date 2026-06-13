from __future__ import annotations

import datetime

import daily_report_analysis_utils as analysis_utils

__all__ = [
    "build_gem_elasticity_context",
    "build_gem_breathing_contract",
    "build_gem_breathing_textbook_profile",
    "build_gem_breathing_watch_anchor",
    "build_gem_observation_pool",
    "build_gem_breathing_prep_context",
    "classify_20cm_branch",
    "discover_all_gem_breathing_candidates",
    "discover_filtered_out_gem_breathing_candidates",
    "discover_gem_breathing_candidates",
    "evaluate_gem_breathing_window",
    "is_20cm_stock",
    "resolve_candidate_contract_prices",
    "should_hide_gem_execution_entry_range",
]

_MISSING = object()
QUANT_SYSTEM_AVAILABLE = False
STOP_PRIOR_LOW_TRADING_DAYS = 5
STRATEGY_HOLDING_DAYS_MAX = 5


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


def normalize_stock_code(code):
    return analysis_utils.normalize_stock_code(code)


def sector_name_matches(sector_a, sector_b):
    return analysis_utils.sector_name_matches(sector_a, sector_b)


def _round_or_none(value, digits=2):
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def _normalize_kline_date_str(value):
    return str(value or "").strip()


def _parse_kline_date(value):
    value = _normalize_kline_date_str(value)
    if not value:
        return None
    try:
        return datetime.datetime.strptime(value[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def fetch_daily_price_bars(*args, **kwargs):
    return []


def fetch_recent_price_bars(*args, **kwargs):
    return []


def evaluate_live_tradability(*args, **kwargs):
    return {}


def build_waiting_stock_plan(stock_item, *args, **kwargs):
    return dict(stock_item or {})


def analyze_buy_signal(*args, **kwargs):
    return None


def _candidate_matches_mainline(candidate, mainline_name=""):
    return analysis_utils._candidate_matches_mainline(candidate, mainline_name)


def _get_gem_stock_universe():
    return []


def evaluate_gem_breathing_window(bars=None, lookback_days=10, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _evaluate_gem_breathing_window_legacy_body(bars=bars, lookback_days=lookback_days)
    finally:
        _restore_runtime_bindings(previous)


def is_20cm_stock(candidate=None, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _is_20cm_stock_legacy_body(candidate=candidate)
    finally:
        _restore_runtime_bindings(previous)


def build_gem_breathing_prep_context(candidate=None, target_date="", lookback_days=10, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _build_gem_breathing_prep_context_legacy_body(
            candidate=candidate,
            target_date=target_date,
            lookback_days=lookback_days,
        )
    finally:
        _restore_runtime_bindings(previous)


def discover_all_gem_breathing_candidates(stock_meta_map, target_date="", *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _discover_all_gem_breathing_candidates_legacy_body(
            stock_meta_map,
            target_date=target_date,
        )
    finally:
        _restore_runtime_bindings(previous)


def discover_gem_breathing_candidates(stock_meta_map, target_date="", mainline_name="", limit=3, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _discover_gem_breathing_candidates_legacy_body(
            stock_meta_map,
            target_date=target_date,
            mainline_name=mainline_name,
            limit=limit,
        )
    finally:
        _restore_runtime_bindings(previous)


def discover_filtered_out_gem_breathing_candidates(stock_meta_map, target_date="", mainline_name="", limit=3, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _discover_filtered_out_gem_breathing_candidates_legacy_body(
            stock_meta_map,
            target_date=target_date,
            mainline_name=mainline_name,
            limit=limit,
        )
    finally:
        _restore_runtime_bindings(previous)


def build_gem_breathing_textbook_profile(candidate=None, target_date="", lookback_days=10, review_days=60, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _build_gem_breathing_textbook_profile_legacy_body(
            candidate=candidate,
            target_date=target_date,
            lookback_days=lookback_days,
            review_days=review_days,
        )
    finally:
        _restore_runtime_bindings(previous)


def build_gem_observation_pool(gem_breathing_candidates=None, target_date="", *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _build_gem_observation_pool_legacy_body(
            gem_breathing_candidates=gem_breathing_candidates,
            target_date=target_date,
        )
    finally:
        _restore_runtime_bindings(previous)


def build_gem_breathing_contract(candidate=None, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _build_gem_breathing_contract_legacy_body(candidate=candidate)
    finally:
        _restore_runtime_bindings(previous)


def build_gem_breathing_watch_anchor(gem_candidate=None, target_date="", mainline_name="", *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _build_gem_breathing_watch_anchor_legacy_body(
            gem_candidate=gem_candidate,
            target_date=target_date,
            mainline_name=mainline_name,
        )
    finally:
        _restore_runtime_bindings(previous)


def build_gem_elasticity_context(candidate=None, mainline_name="", mainline_anchor=None, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _build_gem_elasticity_context_legacy_body(
            candidate=candidate,
            mainline_name=mainline_name,
            mainline_anchor=mainline_anchor,
        )
    finally:
        _restore_runtime_bindings(previous)


def should_hide_gem_execution_entry_range(candidate=None, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _should_hide_gem_execution_entry_range_legacy_body(candidate=candidate)
    finally:
        _restore_runtime_bindings(previous)


def resolve_candidate_contract_prices(candidate=None, signal=None, expose_execution_entry_range=None, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _resolve_candidate_contract_prices_legacy_body(
            candidate=candidate,
            signal=signal,
            expose_execution_entry_range=expose_execution_entry_range,
        )
    finally:
        _restore_runtime_bindings(previous)


def classify_20cm_branch(candidate=None, mainline_name="", confirm_price=None, support_price=None, feedback_ready=False, allow_attack_50_ready=False, target_date="", mainline_anchor=None, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _classify_20cm_branch_legacy_body(
            candidate=candidate,
            mainline_name=mainline_name,
            confirm_price=confirm_price,
            support_price=support_price,
            feedback_ready=feedback_ready,
            allow_attack_50_ready=allow_attack_50_ready,
            target_date=target_date,
            mainline_anchor=mainline_anchor,
        )
    finally:
        _restore_runtime_bindings(previous)


def _is_20cm_stock(candidate=None):
    return _is_20cm_stock_legacy_body(candidate=candidate)


def _evaluate_gem_breathing_window(bars=None, lookback_days=10):
    return _evaluate_gem_breathing_window_legacy_body(bars=bars, lookback_days=lookback_days)


def _build_gem_breathing_prep_context(candidate=None, target_date="", lookback_days=10):
    return _build_gem_breathing_prep_context_legacy_body(
        candidate=candidate,
        target_date=target_date,
        lookback_days=lookback_days,
    )


def _discover_all_gem_breathing_candidates(stock_meta_map, target_date=""):
    return _discover_all_gem_breathing_candidates_legacy_body(stock_meta_map, target_date=target_date)


def _discover_gem_breathing_candidates(stock_meta_map, target_date="", mainline_name="", limit=3):
    return _discover_gem_breathing_candidates_legacy_body(
        stock_meta_map,
        target_date=target_date,
        mainline_name=mainline_name,
        limit=limit,
    )


def _discover_filtered_out_gem_breathing_candidates(stock_meta_map, target_date="", mainline_name="", limit=3):
    return _discover_filtered_out_gem_breathing_candidates_legacy_body(
        stock_meta_map,
        target_date=target_date,
        mainline_name=mainline_name,
        limit=limit,
    )


def _build_gem_breathing_textbook_profile(candidate=None, target_date="", lookback_days=10, review_days=60):
    return _build_gem_breathing_textbook_profile_legacy_body(
        candidate=candidate,
        target_date=target_date,
        lookback_days=lookback_days,
        review_days=review_days,
    )


def _build_gem_observation_pool(gem_breathing_candidates=None, target_date=""):
    return _build_gem_observation_pool_legacy_body(gem_breathing_candidates=gem_breathing_candidates, target_date=target_date)


def _build_gem_breathing_contract(candidate=None):
    return _build_gem_breathing_contract_legacy_body(candidate=candidate)


def _build_gem_breathing_watch_anchor(gem_candidate=None, target_date="", mainline_name=""):
    return _build_gem_breathing_watch_anchor_legacy_body(
        gem_candidate=gem_candidate,
        target_date=target_date,
        mainline_name=mainline_name,
    )


def _build_gem_elasticity_context(candidate=None, mainline_name="", mainline_anchor=None):
    return _build_gem_elasticity_context_legacy_body(
        candidate=candidate,
        mainline_name=mainline_name,
        mainline_anchor=mainline_anchor,
    )


def _should_hide_gem_execution_entry_range(candidate=None):
    return _should_hide_gem_execution_entry_range_legacy_body(candidate=candidate)


def _resolve_candidate_contract_prices(candidate=None, signal=None, expose_execution_entry_range=None):
    return _resolve_candidate_contract_prices_legacy_body(
        candidate=candidate,
        signal=signal,
        expose_execution_entry_range=expose_execution_entry_range,
    )


def _classify_20cm_branch(candidate=None, mainline_name="", confirm_price=None, support_price=None, feedback_ready=False, allow_attack_50_ready=False, target_date="", mainline_anchor=None):
    return _classify_20cm_branch_legacy_body(
        candidate=candidate,
        mainline_name=mainline_name,
        confirm_price=confirm_price,
        support_price=support_price,
        feedback_ready=feedback_ready,
        allow_attack_50_ready=allow_attack_50_ready,
        target_date=target_date,
        mainline_anchor=mainline_anchor,
    )


def _is_20cm_stock_legacy_body(candidate=None):
    candidate = candidate or {}
    code = normalize_stock_code(candidate.get("code") or candidate.get("stock_code") or "")
    return code.startswith("30")


def _evaluate_gem_breathing_window_legacy_body(bars=None, lookback_days=10):
    bars = list(bars or [])
    min_required_bars = max(lookback_days, 8)
    if len(bars) < min_required_bars:
        return {"active": False}

    window = bars[-lookback_days:]
    closes = [_safe_float(bar.get("close")) for bar in window]
    highs = [_safe_float(bar.get("high")) for bar in window]
    lows = [_safe_float(bar.get("low")) for bar in window]
    if any(price <= 0 for price in closes):
        return {"active": False}

    def _ma(values, n, idx):
        if idx + 1 < n:
            return None
        arr = values[idx - n + 1 : idx + 1]
        return sum(arr) / len(arr)

    spread_values = []
    abs_pct_values = []
    amp_values = []
    sign_changes = 0
    prev_sign = 0
    sign_series = []
    for i in range(1, len(closes)):
        pct = closes[i] / closes[i - 1] - 1 if closes[i - 1] > 0 else 0.0
        abs_pct_values.append(abs(pct) * 100)
        amp_values.append((highs[i] - lows[i]) / closes[i - 1] * 100 if closes[i - 1] > 0 else 0.0)
        mas = []
        for n in (3, 5, 10):
            m = _ma(closes, n, i)
            if m is not None:
                mas.append(m)
        if len(mas) == 3:
            spread_values.append((max(mas) - min(mas)) / closes[i] * 100)
        sign = 1 if pct > 0 else (-1 if pct < 0 else 0)
        sign_series.append(sign)
        if prev_sign and sign and prev_sign != sign:
            sign_changes += 1
        if sign:
            prev_sign = sign

    if not spread_values:
        return {"active": False}

    avg_spread = sum(spread_values) / len(spread_values)
    avg_abs_pct = sum(abs_pct_values) / len(abs_pct_values) if abs_pct_values else 0.0
    avg_amp = sum(amp_values) / len(amp_values) if amp_values else 0.0

    recent_window = min(5, len(abs_pct_values))
    if recent_window < 4 or len(spread_values) < 1:
        return {"active": False}
    recent_abs_pct = sum(abs_pct_values[-recent_window:]) / recent_window
    recent_amp = sum(amp_values[-recent_window:]) / recent_window
    recent_spread_window = min(recent_window, len(spread_values))
    recent_spread = sum(spread_values[-recent_spread_window:]) / recent_spread_window

    prior_abs_slice = abs_pct_values[-recent_window * 2 : -recent_window] if len(abs_pct_values) >= recent_window * 2 else abs_pct_values[:-recent_window]
    prior_amp_slice = amp_values[-recent_window * 2 : -recent_window] if len(amp_values) >= recent_window * 2 else amp_values[:-recent_window]
    if not prior_abs_slice or not prior_amp_slice:
        return {"active": False}
    prior_abs_pct = sum(prior_abs_slice) / len(prior_abs_slice)
    prior_amp = sum(prior_amp_slice) / len(prior_amp_slice)

    recent_sign_changes = 0
    recent_sign_slice = sign_series[-recent_window:]
    prev_recent_sign = 0
    for sign in recent_sign_slice:
        if prev_recent_sign and sign and prev_recent_sign != sign:
            recent_sign_changes += 1
        if sign:
            prev_recent_sign = sign

    relative_compression_ready = (
        recent_spread <= 3.0
        and recent_abs_pct <= min(2.4, prior_abs_pct * 0.8)
        and recent_amp <= min(4.0, prior_amp * 0.95)
        and recent_sign_changes >= 2
    )
    absolute_compression_ready = (
        recent_spread <= 2.0
        and recent_abs_pct <= 1.5
        and recent_amp <= 2.8
        and recent_sign_changes >= 3
    )
    wide_reacceleration_ready = (
        recent_spread <= 3.0
        and recent_abs_pct <= 2.9
        and recent_amp <= 7.2
        and recent_sign_changes >= 3
        and avg_abs_pct <= 3.4
        and avg_amp <= 8.0
        and recent_amp <= prior_amp * 0.85
    )
    compression_ready = relative_compression_ready or absolute_compression_ready or wide_reacceleration_ready
    active = (
        compression_ready
        and avg_spread <= 5.0
        and sign_changes >= 3
        and avg_abs_pct <= 5.5
        and avg_amp <= 8.5
    )
    tier = "tight" if active and recent_spread <= 2.0 and recent_abs_pct <= 1.8 and recent_amp <= 3.2 and recent_sign_changes >= 3 else "loose" if active else ""
    note = ""
    if active:
        note = "创业板20cm预启动观察：波动收敛，等待量价温和放大后的右侧确认。" if tier == "tight" else "创业板20cm存在波动收敛与节奏切换，适合先纳入预启动观察。"

    return {
        "active": active,
        "tier": tier,
        "avg_spread_pct": round(avg_spread, 2),
        "avg_abs_pct": round(avg_abs_pct, 2),
        "avg_amp_pct": round(avg_amp, 2),
        "sign_changes": sign_changes,
        "recent_spread_pct": round(recent_spread, 2),
        "recent_abs_pct": round(recent_abs_pct, 2),
        "recent_amp_pct": round(recent_amp, 2),
        "recent_sign_changes": recent_sign_changes,
        "prior_abs_pct": round(prior_abs_pct, 2),
        "prior_amp_pct": round(prior_amp, 2),
        "compression_ready": compression_ready,
        "note": note,
    }


def _build_gem_breathing_prep_context_legacy_body(candidate=None, target_date="", lookback_days=10):
    candidate = candidate or {}
    if not _is_20cm_stock(candidate):
        return {"active": False}

    code = normalize_stock_code(candidate.get("code") or candidate.get("stock_code") or "")
    target_date = _normalize_kline_date_str(target_date)
    if not code or not target_date:
        return {"active": False}

    target_dt = _parse_kline_date(target_date)
    recent_scan_start = target_date
    if target_dt:
        recent_scan_start = (target_dt - datetime.timedelta(days=max(lookback_days * 5, 45))).strftime("%Y-%m-%d")
    bars = fetch_daily_price_bars(
        code,
        recent_scan_start,
        target_date,
        is_index=False,
        prefer_fast=True,
        allow_baostock_fallback=False,
    )
    bars = [bar for bar in (bars or []) if _normalize_kline_date_str(bar.get("date")) <= target_date]
    return _evaluate_gem_breathing_window(bars, lookback_days=lookback_days)


def _discover_all_gem_breathing_candidates_legacy_body(stock_meta_map, target_date=""):
    stock_meta_map = stock_meta_map or {}
    items = []
    base_candidates = {}
    for code, meta in (stock_meta_map or {}).items():
        norm_code = normalize_stock_code(code)
        if not norm_code.startswith("30"):
            continue
        candidate = dict(meta or {})
        candidate["code"] = normalize_stock_code(candidate.get("code") or norm_code)
        base_candidates[candidate["code"]] = candidate
    for item in _get_gem_stock_universe():
        code = normalize_stock_code(item.get("code", ""))
        if not code.startswith("30") or code not in base_candidates:
            continue
        merged = dict(base_candidates.get(code, {}))
        merged.update({k: v for k, v in (item or {}).items() if v not in (None, "")})
        merged["code"] = code
        base_candidates[code] = merged
    for code, candidate in base_candidates.items():
        if not _is_20cm_stock(candidate):
            continue
        ctx = _build_gem_breathing_prep_context(candidate, target_date=target_date)
        if not ctx.get("active"):
            continue
        items.append(
            {
                "name": candidate.get("name", ""),
                "code": candidate.get("code", ""),
                "sector": candidate.get("sector", ""),
                "tier": ctx.get("tier", ""),
                "note": ctx.get("note", ""),
                "score": _safe_float(candidate.get("score", 0)),
                "close": _safe_float(candidate.get("close", candidate.get("latest_price", candidate.get("最新价", 0)))),
                "volume": _safe_float(candidate.get("volume", candidate.get("成交额", 0))),
                "change_pct": _safe_float(candidate.get("change_pct", candidate.get("涨跌幅", 0))),
                "avg_spread_pct": _safe_float(ctx.get("avg_spread_pct", 0)),
                "sign_changes": int(_safe_float(ctx.get("sign_changes", 0))),
            }
        )
    items.sort(
        key=lambda x: (1 if x.get("tier") == "tight" else 0, x.get("score", 0), -x.get("avg_spread_pct", 99), x.get("sign_changes", 0)),
        reverse=True,
    )
    return items


def _discover_gem_breathing_candidates_legacy_body(stock_meta_map, target_date="", mainline_name="", limit=3):
    all_items = _discover_all_gem_breathing_candidates(stock_meta_map, target_date=target_date)
    if mainline_name:
        all_items = [item for item in all_items if _candidate_matches_mainline(item, mainline_name)]
    return all_items[:limit]


def _discover_filtered_out_gem_breathing_candidates_legacy_body(stock_meta_map, target_date="", mainline_name="", limit=3):
    if not mainline_name:
        return []
    all_items = _discover_all_gem_breathing_candidates(stock_meta_map, target_date=target_date)
    items = []
    for item in all_items:
        if _candidate_matches_mainline(item, mainline_name):
            continue
        filtered_item = dict(item)
        filtered_item["filtered_reason"] = f"当前主线是{mainline_name}，该样本不在主线内，因此不纳入正式观察池。"
        items.append(filtered_item)
    return items[:limit]


def _empty_textbook_profile():
    return {
        "label": "",
        "total_active_count": 0,
        "tight_count": 0,
        "loose_count": 0,
        "last_active_date": "",
        "score_bonus": 0,
        "summary_text": "",
    }


def _build_gem_breathing_textbook_profile_legacy_body(candidate=None, target_date="", lookback_days=10, review_days=60):
    candidate = candidate or {}
    if not _is_20cm_stock(candidate):
        return _empty_textbook_profile()

    code = normalize_stock_code(candidate.get("code") or candidate.get("stock_code") or "")
    target_date = _normalize_kline_date_str(target_date)
    if not code or not target_date:
        return _empty_textbook_profile()

    bars = fetch_daily_price_bars(
        code,
        "2025-01-01",
        target_date,
        is_index=False,
        prefer_fast=True,
        allow_baostock_fallback=False,
    ) or []
    bars = [bar for bar in bars if _normalize_kline_date_str(bar.get("date")) <= target_date]
    min_required_bars = max(lookback_days, 8)
    if len(bars) < min_required_bars:
        return _empty_textbook_profile()

    start_idx = max(min_required_bars - 1, len(bars) - max(review_days, min_required_bars))
    active_points = []
    for idx in range(start_idx, len(bars)):
        window_bars = bars[: idx + 1]
        ctx = _evaluate_gem_breathing_window(window_bars, lookback_days=lookback_days)
        if not ctx.get("active"):
            continue
        active_points.append(
            {
                "date": _normalize_kline_date_str(bars[idx].get("date")),
                "tier": ctx.get("tier", ""),
            }
        )

    total_active_count = len(active_points)
    tight_count = len([item for item in active_points if item.get("tier") == "tight"])
    loose_count = len([item for item in active_points if item.get("tier") == "loose"])
    last_active_date = active_points[-1]["date"] if active_points else ""

    if tight_count >= 2 or (tight_count >= 1 and total_active_count >= 4):
        label = "A级教材"
        score_bonus = 8
    elif total_active_count >= 3:
        label = "B级教材"
        score_bonus = 4
    elif total_active_count >= 1:
        label = "C级观察样本"
        score_bonus = 1
    else:
        label = ""
        score_bonus = 0

    summary_text = ""
    if label:
        summary_text = (
            f"{label}：近{review_days}日出现{total_active_count}次，"
            f"tight {tight_count}次 / loose {loose_count}次，最近一次{last_active_date}"
        )

    return {
        "label": label,
        "total_active_count": total_active_count,
        "tight_count": tight_count,
        "loose_count": loose_count,
        "last_active_date": last_active_date,
        "score_bonus": score_bonus,
        "summary_text": summary_text,
    }


def _build_gem_observation_pool_legacy_body(gem_breathing_candidates=None, target_date=""):
    pool = []
    textbook_rank_map = {"A级教材": 3, "B级教材": 2, "C级观察样本": 1}
    for raw in (gem_breathing_candidates or []):
        item = dict(raw or {})
        tier = str(item.get("tier", "") or "").strip()
        base_score = _safe_float(item.get("score", 0))
        strength_bonus = 12 if tier == "tight" else 6
        note = str(item.get("note", "") or "").strip() or "创业板20cm预启动观察。"
        textbook_profile = build_gem_breathing_textbook_profile(item, target_date=target_date) if target_date else _empty_textbook_profile()
        textbook_summary = str(textbook_profile.get("summary_text", "") or "").strip()
        watch_anchor_note = str(item.get("watch_anchor_note", "") or "先看右侧确认和09:50-10:10窗口，不直接给买入资格").strip()
        if textbook_summary:
            watch_anchor_note = f"{watch_anchor_note}；{textbook_summary}"
        item.update(
            {
                "pattern": "创业板20cm预启动",
                "core_level": f"🫁 20cm预启动观察{' / ' + textbook_profile.get('label', '') if textbook_profile.get('label') else ''}",
                "abnormal_summary": note,
                "abnormal_follow_state": "预启动呼吸感",
                "tmr_forecast": "先看右侧确认和09:50-10:10窗口内条件是否成立，确认前只观察不执行",
                "tomorrow_strength": round(base_score + strength_bonus + _safe_float(textbook_profile.get("score_bonus", 0)), 1),
                "watch_source": "gem_breathing_20cm",
                "close": _safe_float(item.get("close", 0)),
                "volume": _safe_float(item.get("volume", 0)),
                "change_pct": _safe_float(item.get("change_pct", 0)),
                "entry_price": _safe_float(item.get("close", 0)),
                "watch_anchor_note": watch_anchor_note,
                "textbook_label": str(textbook_profile.get("label", "") or "").strip(),
                "textbook_summary": textbook_summary,
                "textbook_profile": textbook_profile,
                "textbook_rank": textbook_rank_map.get(str(textbook_profile.get("label", "") or "").strip(), 0),
            }
        )
        pool.append(item)
    pool.sort(
        key=lambda x: (
            _safe_float(x.get("textbook_rank", 0)),
            _safe_float((x.get("textbook_profile") or {}).get("tight_count", 0)),
            _safe_float((x.get("textbook_profile") or {}).get("total_active_count", 0)),
            _safe_float(x.get("tomorrow_strength", 0)),
        ),
        reverse=True,
    )
    return pool


def _build_gem_breathing_contract_legacy_body(candidate=None):
    candidate = candidate or {}
    minute_plan = candidate.get("minute_plan") or {}
    stop_plan = candidate.get("stop_plan") or {}
    confirm_price = _round_or_none(
        minute_plan.get("confirm_price_60m")
        or candidate.get("confirm_price_60m")
    )
    support_price = _round_or_none(
        minute_plan.get("confirm_support_60m")
        or candidate.get("execution_stop")
        or candidate.get("display_anchor_price")
        or candidate.get("effective_stop")
    )
    entry_range = candidate.get("entry_range") or ()
    reset_breakout_price = None
    if isinstance(entry_range, (list, tuple)) and len(entry_range) >= 2:
        reset_breakout_price = _round_or_none(entry_range[1])
    if reset_breakout_price is None:
        reset_breakout_price = _round_or_none(candidate.get("entry_range_high") or confirm_price)
    holding_days_max = int(
        _safe_float(
            candidate.get("holding_days_max")
            or stop_plan.get("holding_days_max")
            or STRATEGY_HOLDING_DAYS_MAX
        )
        or STRATEGY_HOLDING_DAYS_MAX
    )
    active_window_days = min(max(holding_days_max, 3), 5)
    if confirm_price is not None and support_price is not None:
        upgrade_condition_text = f"09:50-10:10站上{confirm_price:.2f}且不破{support_price:.2f}，才评估50%条件执行"
    elif confirm_price is not None:
        upgrade_condition_text = f"09:50-10:10站上{confirm_price:.2f}，才评估50%条件执行"
    else:
        upgrade_condition_text = "先完成右侧确认，并且固定交易窗口内条件成立，才评估50%条件执行；普通结构只看09:50-10:10窗口"
    return {
        "active": bool(confirm_price or support_price or reset_breakout_price),
        "contract_kind": "gem_breathing_20cm",
        "active_window_days": active_window_days,
        "right_side_trigger_price": confirm_price,
        "upgrade_condition_text": upgrade_condition_text,
        "void_price": support_price,
        "reset_breakout_price": reset_breakout_price,
    }


def _build_gem_breathing_watch_anchor_legacy_body(gem_candidate=None, target_date="", mainline_name=""):
    del mainline_name
    gem_candidate = dict(gem_candidate or {})
    code = normalize_stock_code(gem_candidate.get("code", ""))
    close_price = _safe_float(gem_candidate.get("close", 0))
    if not code:
        return {}

    recent_bars = fetch_recent_price_bars(code, target_date, lookback_days=4)
    daily_anchor_bars = fetch_recent_price_bars(
        code,
        target_date,
        lookback_days=max(STOP_PRIOR_LOW_TRADING_DAYS + 5, 10),
    )
    tradability_guard = evaluate_live_tradability(
        gem_candidate,
        target_date,
        recent_bars=recent_bars,
    )
    signal = (
        analyze_buy_signal(
            code,
            gem_candidate.get("name", ""),
            close_price,
            _safe_float(gem_candidate.get("volume")),
        )
        if (QUANT_SYSTEM_AVAILABLE and close_price > 0 and code)
        else None
    )
    signal_type = getattr(signal, "signal_type", "") if signal and getattr(signal, "is_valid", False) else ""
    entry_seed_price = signal.entry_price if signal and getattr(signal, "is_valid", False) else close_price

    watch_anchor = build_waiting_stock_plan(
        {
            **gem_candidate,
            "entry_price": entry_seed_price,
            "condition": gem_candidate.get("tmr_forecast") or gem_candidate.get("note") or "先看创业板20cm呼吸感是否升级成右侧确认",
            "tradability_guard": tradability_guard,
            "report_day_is_one_word": tradability_guard.get("report_day_is_one_word", False),
        },
        target_date,
        reason=gem_candidate.get("tmr_forecast") or gem_candidate.get("note") or "先看创业板20cm呼吸感是否升级成右侧确认",
        signal_type=signal_type,
        recent_bars=daily_anchor_bars,
    )
    watch_anchor.update(
        {
            "watch_source": "gem_breathing_20cm",
            "permission_label": "创业板20cm预启动观察权",
            "permission_reason": "只先进观察池，先看右侧确认和09:50-10:10窗口，不直接给买入资格",
            "watch_anchor_type": "创业板20cm预启动先看谁",
            "watch_anchor_note": (
                f"{str(gem_candidate.get('note', '') or '创业板20cm预启动观察。').strip()}；"
                "只先进观察池，先看右侧确认和09:50-10:10窗口，不满足继续观察"
            ),
            "tradability_guard": tradability_guard,
            "report_day_is_one_word": tradability_guard.get("report_day_is_one_word", False),
            "abnormal_follow_state": gem_candidate.get("abnormal_follow_state", "预启动呼吸感"),
            "breathing_tier": gem_candidate.get("tier", ""),
        }
    )
    if signal and getattr(signal, "is_valid", False):
        watch_anchor["signal"] = signal
        watch_anchor["signal_type"] = getattr(signal, "signal_type", "")
        watch_anchor["position_pct"] = _safe_float(signal.position_pct, 0.0)
        watch_anchor["entry_price"] = signal.entry_price
        watch_anchor["entry_range"] = (signal.entry_price * 0.97, signal.entry_price * 1.03)
    watch_anchor["gem_breathing_contract"] = _build_gem_breathing_contract(watch_anchor)
    gem_contract = watch_anchor.get("gem_breathing_contract", {}) or {}
    upgrade_text = str(gem_contract.get("upgrade_condition_text", "") or "").strip()
    void_price = _round_or_none(gem_contract.get("void_price"))
    reset_breakout_price = _round_or_none(gem_contract.get("reset_breakout_price"))
    note_parts = [str(gem_candidate.get("note", "") or "创业板20cm预启动观察。").strip()]
    textbook_summary = str(gem_candidate.get("textbook_summary", "") or "").strip()
    if textbook_summary:
        note_parts.append(textbook_summary)
    if upgrade_text:
        note_parts.append(upgrade_text)
    if void_price is not None:
        note_parts.append(f"失守{void_price:.2f}作废")
    elif reset_breakout_price is not None:
        note_parts.append(f"失守后至少重新站回{reset_breakout_price:.2f}再评估")
    note_parts.append("确认前只先进观察池，先看右侧确认和09:50-10:10窗口，不直接给买入资格")
    watch_anchor["watch_anchor_note"] = "；".join(part for part in note_parts if part)
    return watch_anchor


def _build_gem_elasticity_context_legacy_body(candidate=None, mainline_name="", mainline_anchor=None):
    candidate = candidate or {}
    mainline_name = str(mainline_name or "").strip()
    sector = str(candidate.get("sector", "") or candidate.get("sector_name", "") or "").strip()
    if not mainline_name or not sector:
        return {"active": False}
    if not sector_name_matches(sector, mainline_name):
        return {"active": False}
    anchor_name = str((mainline_anchor or {}).get("name", "") or "").strip() or mainline_name
    return {
        "active": True,
        "label": "主板强锚对应的创业板弹性标的",
        "anchor_name": anchor_name,
        "reason": f"{anchor_name}仍是主板强锚时，创业板更像这条主线里的白银弹性层。",
    }


def _should_hide_gem_execution_entry_range_legacy_body(candidate=None):
    candidate = candidate or {}
    if str(candidate.get("watch_source", "") or "").strip() != "gem_breathing_20cm":
        return False
    position_pct = int(_safe_float(candidate.get("position_pct", 0)))
    participation_mode = str(candidate.get("participation_mode", "") or "").strip()
    action_type = str(candidate.get("action_type", "") or "").strip()
    return position_pct <= 0 and participation_mode not in ("attack_50_ready", "execute_50") and action_type != "execute"


def _resolve_candidate_contract_prices_legacy_body(candidate=None, signal=None, expose_execution_entry_range=None):
    candidate = candidate or {}
    minute_plan = candidate.get("minute_plan") or {}
    gem_contract = candidate.get("gem_breathing_contract") or {}
    entry_range = candidate.get("entry_range")
    if not entry_range and signal:
        entry_range = (signal.entry_price, signal.entry_price)

    observe_anchor_price = _round_or_none(
        candidate.get("entry_price")
        or (signal.entry_price if signal else None)
        or (entry_range[0] if isinstance(entry_range, (list, tuple)) and entry_range else None)
    )
    upgrade_trigger_price = _round_or_none(
        gem_contract.get("right_side_trigger_price")
        or minute_plan.get("confirm_price_60m")
    )
    invalidation_price = _round_or_none(
        gem_contract.get("void_price")
        or minute_plan.get("confirm_support_60m")
        or candidate.get("execution_stop")
        or candidate.get("display_anchor_price")
        or candidate.get("effective_stop")
        or candidate.get("stop_loss")
    )
    reset_breakout_price = _round_or_none(
        gem_contract.get("reset_breakout_price")
        or candidate.get("entry_range_high")
        or (entry_range[1] if isinstance(entry_range, (list, tuple)) and len(entry_range) >= 2 else None)
        or minute_plan.get("confirm_price_60m")
    )

    if expose_execution_entry_range is None:
        expose_execution_entry_range = not _should_hide_gem_execution_entry_range(candidate)

    entry_range_low = _round_or_none(entry_range[0]) if expose_execution_entry_range and isinstance(entry_range, (list, tuple)) and len(entry_range) >= 1 else None
    entry_range_high = _round_or_none(entry_range[1]) if expose_execution_entry_range and isinstance(entry_range, (list, tuple)) and len(entry_range) >= 2 else None

    return {
        "entry_range_low": entry_range_low,
        "entry_range_high": entry_range_high,
        "observe_anchor_price": observe_anchor_price,
        "upgrade_trigger_price": upgrade_trigger_price,
        "invalidation_price": invalidation_price,
        "reset_breakout_price": reset_breakout_price,
    }


def _classify_20cm_branch_legacy_body(candidate=None, mainline_name="", confirm_price=None, support_price=None, feedback_ready=False, allow_attack_50_ready=False, target_date="", mainline_anchor=None):
    candidate = candidate or {}
    if not _is_20cm_stock(candidate):
        return {
            "is_20cm": False,
            "allow_watch_pool": False,
            "allow_attack_50_ready": False,
            "observe_only": False,
            "direct_ban": False,
            "reason": "",
        }

    follow_state = str(candidate.get("abnormal_follow_state", candidate.get("follow_state", "")) or "").strip()
    sector = str(candidate.get("sector", "") or "").strip()
    textbook_label = str(candidate.get("textbook_label", "") or "").strip()
    textbook_summary = str(candidate.get("textbook_summary", "") or "").strip()
    lianban = int(_safe_float(candidate.get("lianban", candidate.get("连板数", 0)) or 0))
    change_pct = abs(_safe_float(candidate.get("change_pct", candidate.get("涨跌幅", 0.0))))
    clear_boundary = confirm_price is not None and support_price is not None and confirm_price > 0 and support_price > 0
    mainline_match = bool(mainline_name and sector and sector_name_matches(sector, mainline_name))
    right_side_ok = follow_state in ("跌不下去", "缩量消化", "长上影后收复")
    breathing_prep = _build_gem_breathing_prep_context(candidate, target_date=target_date)
    elasticity_context = _build_gem_elasticity_context(candidate, mainline_name=mainline_name, mainline_anchor=mainline_anchor)
    textbook_ready = textbook_label == "A级教材" and breathing_prep.get("active") and elasticity_context.get("active")
    risky_chase = lianban >= 2 or change_pct >= 15 or follow_state in ("一致加速", "高位加速") or not clear_boundary

    if risky_chase:
        return {
            "is_20cm": True,
            "allow_watch_pool": False,
            "allow_attack_50_ready": False,
            "observe_only": False,
            "direct_ban": True,
            "reason": "20cm 高波动接力/边界不清样本直接禁做，只保留远离情绪顶点后的后续观察。",
            "breathing_prep": breathing_prep,
            "elasticity_context": elasticity_context,
        }

    allow_watch_pool = mainline_match and clear_boundary and (right_side_ok or breathing_prep.get("active"))
    allow_conditional = allow_watch_pool and allow_attack_50_ready and ((right_side_ok and feedback_ready) or (textbook_ready and feedback_ready))
    if allow_conditional:
        if textbook_ready and not right_side_ok:
            reason = f"{textbook_summary or textbook_label}；属于反复验证过的20cm教材样本，当前边界清楚且反馈就绪，可先进入50%条件执行；固定交易窗口内条件不满足则0%不参与。"
        else:
            reason = "20cm 只作为右侧补充分支；主线、确认链、固定交易窗口条件和风险边界都清楚时，才评估50%条件执行；不满足则0%不参与。"
    elif breathing_prep.get("active") and elasticity_context.get("active"):
        reason = f"{breathing_prep.get('note') or '创业板20cm呼吸感预启动。'}；{elasticity_context.get('reason', '')}"
    elif breathing_prep.get("active"):
        reason = breathing_prep.get("note") or "创业板20cm呼吸感预启动，只先进观察池，不直接执行。"
    else:
        reason = "20cm 样本可进观察池，但当前只保留观察权，不直接给执行仓位。"

    return {
        "is_20cm": True,
        "allow_watch_pool": allow_watch_pool,
        "allow_attack_50_ready": allow_conditional,
        "observe_only": allow_watch_pool and not allow_conditional,
        "direct_ban": False,
        "reason": reason,
        "breathing_prep": breathing_prep,
        "elasticity_context": elasticity_context,
    }
