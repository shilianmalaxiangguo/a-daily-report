from __future__ import annotations

from market_data.kline_dates import normalize_kline_date_str as _default_normalize_kline_date_str
from report.strategy_tracking_store import load_strategy_performance_ledger as _default_load_strategy_performance_ledger
from report.strategy_tracking_support import (
    backfill_strategy_record_market_context as _default_backfill_strategy_record_market_context,
    build_trade_return_stats as _default_build_trade_return_stats,
)

__all__ = [
    "build_strategy_ev_calibration",
    "estimate_signal_type_ev",
    "score_execution_candidate",
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


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _clamp(value, low, high):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return low
    return max(low, min(high, value))


def _normalize_kline_date_str(value):
    return _default_normalize_kline_date_str(value)


def load_strategy_performance_ledger(*, mode="frozen"):
    return _default_load_strategy_performance_ledger(mode=mode)


def _backfill_strategy_record_market_context(record):
    return _default_backfill_strategy_record_market_context(record)


def _build_trade_return_stats(records):
    return _default_build_trade_return_stats(records)


def build_strategy_ev_calibration(as_of_date, ledger_mode="frozen", *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _build_strategy_ev_calibration_legacy_body(as_of_date, ledger_mode=ledger_mode)
    finally:
        _restore_runtime_bindings(previous)


def estimate_signal_type_ev(signal_type, loss_space_pct, calibration, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _estimate_signal_type_ev_legacy_body(signal_type, loss_space_pct, calibration)
    finally:
        _restore_runtime_bindings(previous)


def score_execution_candidate(candidate, ev_calibration, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _score_execution_candidate_legacy_body(candidate, ev_calibration)
    finally:
        _restore_runtime_bindings(previous)


def _estimate_signal_type_ev(signal_type, loss_space_pct, calibration):
    return _estimate_signal_type_ev_legacy_body(signal_type, loss_space_pct, calibration)


def _build_strategy_ev_calibration_legacy_body(as_of_date, ledger_mode="frozen"):
    ledger = load_strategy_performance_ledger(mode=ledger_mode)
    cutoff_date = _normalize_kline_date_str(as_of_date)
    historical_records = [
        _backfill_strategy_record_market_context(dict(record))
        for record in ledger.get("records", [])
        if _normalize_kline_date_str(record.get("report_date")) < cutoff_date
    ]

    global_stats = _build_trade_return_stats(historical_records)
    by_signal = {}
    for signal_type in EV_SIGNAL_TYPE_PRIORS.keys():
        signal_records = [
            record for record in historical_records
            if (record.get("signal_type") or "base") == signal_type
        ]
        by_signal[signal_type] = _build_trade_return_stats(signal_records)

    return {
        "global": global_stats,
        "by_signal": by_signal,
    }


def _estimate_signal_type_ev_legacy_body(signal_type, loss_space_pct, calibration):
    signal_type = signal_type or "base"
    prior = EV_SIGNAL_TYPE_PRIORS.get(signal_type, EV_SIGNAL_TYPE_PRIORS["base"])
    global_stats = (calibration or {}).get("global", {}) or {}
    signal_stats = ((calibration or {}).get("by_signal", {}) or {}).get(signal_type, {}) or {}

    prior_weight = _safe_float(prior.get("prior_weight"), 8.0)
    global_weight = min(_safe_float(global_stats.get("sample_size")), 6.0)
    signal_weight = min(_safe_float(signal_stats.get("sample_size")), 12.0)
    total_weight = prior_weight + global_weight + signal_weight

    def _blend_metric(key):
        weighted_sum = _safe_float(prior.get(key)) * prior_weight
        if global_weight > 0 and global_stats.get(key) is not None:
            weighted_sum += _safe_float(global_stats.get(key)) * global_weight
        if signal_weight > 0 and signal_stats.get(key) is not None:
            weighted_sum += _safe_float(signal_stats.get(key)) * signal_weight
        return weighted_sum / total_weight if total_weight > 0 else _safe_float(prior.get(key))

    win_rate = _clamp(_blend_metric("win_rate"), 0.20, 0.80)
    avg_win_pct = _clamp(_blend_metric("avg_win_pct"), 0.02, 0.20)
    avg_loss_pct = _clamp(_blend_metric("avg_loss_pct"), 0.015, 0.10)
    reward_multiple = _clamp(avg_win_pct / max(avg_loss_pct, 0.01), 1.2, 4.0)

    projected_loss_pct = max(_safe_float(loss_space_pct), avg_loss_pct * 0.8)
    projected_win_pct = max(projected_loss_pct * reward_multiple, avg_win_pct * 0.6)
    confidence = _clamp((signal_weight + global_weight) / max(total_weight, 1.0), 0.0, 0.85)

    signal_samples = int(_safe_float(signal_stats.get("sample_size")))
    global_samples = int(_safe_float(global_stats.get("sample_size")))
    if signal_samples > 0:
        source_label = f"同类账本{signal_samples}笔 + 全局{global_samples}笔校准"
    elif global_samples > 0:
        source_label = f"全局账本{global_samples}笔 + 类型先验"
    else:
        source_label = "类型先验（暂无历史成交）"

    return {
        "signal_type": signal_type,
        "signal_label": prior.get("label", signal_type),
        "win_rate": win_rate,
        "avg_win_pct": avg_win_pct,
        "avg_loss_pct": avg_loss_pct,
        "projected_win_pct": projected_win_pct,
        "projected_loss_pct": projected_loss_pct,
        "reward_multiple": reward_multiple,
        "confidence": confidence,
        "signal_sample_size": signal_samples,
        "global_sample_size": global_samples,
        "source_label": source_label,
    }


def _score_execution_candidate_legacy_body(candidate, ev_calibration):
    scored = dict(candidate or {})
    signal = scored.get("signal")
    max_single_trade_loss_pct = globals().get("MAX_SINGLE_TRADE_LOSS_PCT", 0.05)

    if signal:
        entry_price = _safe_float(signal.entry_price)
        stop_loss = _safe_float(scored.get("stop_loss", signal.stop_loss))
        position_pct = _safe_float(signal.position_pct, 0.0)
        signal_type = getattr(signal, "signal_type", "") or "base"
    else:
        entry_price = _safe_float(scored.get("entry_price", scored.get("close", 0.0)))
        stop_loss = _safe_float(scored.get("stop_loss", entry_price * (1 - max_single_trade_loss_pct)))
        position_pct = _safe_float(scored.get("position_pct", 20.0))
        signal_type = scored.get("signal_type") or "base"

    if entry_price <= 0:
        scored["win_rate"] = 0.0
        scored["r_reward_ratio"] = 0.0
        scored["ev"] = 0.0
        scored["composite_score"] = 0.0
        scored["profit_space"] = 0.0
        scored["loss_space"] = 0.0
        scored["projected_win_pct"] = 0.0
        scored["projected_loss_pct"] = 0.0
        scored["ev_model_source"] = "无有效从什么价开始算"
        scored["ev_sample_size"] = 0
        scored["ev_global_sample_size"] = 0
        scored["ev_confidence"] = 0.0
        scored["signal_type"] = signal_type
        return scored

    loss_space_pct = max((entry_price - stop_loss) / entry_price, 0.0)
    if loss_space_pct <= 0:
        loss_space_pct = max_single_trade_loss_pct

    posterior = estimate_signal_type_ev(signal_type, loss_space_pct, ev_calibration)
    projected_loss_pct = max(loss_space_pct, posterior.get("projected_loss_pct", loss_space_pct))
    projected_win_pct = max(projected_loss_pct * posterior.get("reward_multiple", 2.0), posterior.get("projected_win_pct", 0.0))

    profit_space = entry_price * projected_win_pct
    loss_space = entry_price * projected_loss_pct
    ev_pct = posterior.get("win_rate", 0.0) * projected_win_pct - (1 - posterior.get("win_rate", 0.0)) * projected_loss_pct
    composite_score = ev_pct * (position_pct / 100.0) * (1.0 + posterior.get("confidence", 0.0) * 0.15)
    r_reward_ratio = projected_win_pct / projected_loss_pct if projected_loss_pct > 0 else 0.0

    scored["win_rate"] = posterior.get("win_rate", 0.0)
    scored["r_reward_ratio"] = r_reward_ratio
    scored["ev"] = entry_price * ev_pct
    scored["ev_pct"] = ev_pct
    scored["composite_score"] = composite_score
    scored["profit_space"] = profit_space
    scored["loss_space"] = loss_space
    scored["projected_win_pct"] = projected_win_pct
    scored["projected_loss_pct"] = projected_loss_pct
    scored["ev_model_source"] = posterior.get("source_label", "")
    scored["ev_sample_size"] = posterior.get("signal_sample_size", 0)
    scored["ev_global_sample_size"] = posterior.get("global_sample_size", 0)
    scored["ev_confidence"] = posterior.get("confidence", 0.0)
    scored["signal_type"] = signal_type
    return scored
