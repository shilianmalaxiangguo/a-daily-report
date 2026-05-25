from __future__ import annotations

from legacy_runtime_shim import export_or_default


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _score_fund_flow(fund_flow):
    if not fund_flow:
        return 0.0
    net_inflow = abs(_safe_float(fund_flow.get("zljlr", fund_flow.get("net_inflow", 0))))
    price_change = abs(_safe_float(fund_flow.get("zdf", fund_flow.get("change_pct", 0))))
    score = 1.0
    if net_inflow >= 50:
        score += 3.0
    elif net_inflow >= 20:
        score += 2.0
    elif net_inflow >= 5:
        score += 1.0
    if price_change >= 3:
        score += 1.0
    elif price_change >= 1:
        score += 0.5
    return min(score, 5.0)


def _score_limit_up(zt_stocks):
    count = len(zt_stocks or [])
    if count >= 8:
        return 5.0
    if count >= 5:
        return 4.0
    if count >= 3:
        return 3.0
    if count >= 1:
        return 2.0
    return 0.0


def _score_lhb(lhb_data):
    count = len(lhb_data or [])
    if count >= 3:
        return 3.0
    if count >= 1:
        return 2.0
    return 0.0


def _score_volume(volume_change):
    change = _safe_float(volume_change)
    if change >= 80:
        return 3.0
    if change >= 30:
        return 2.0
    if change >= 10:
        return 1.0
    return 0.0


def _score_sentiment(hot_rank_count):
    count = int(_safe_float(hot_rank_count))
    if count >= 5:
        return 2.0
    if count >= 2:
        return 1.0
    return 0.0


def _fallback_calculate_resonance(sectors_data):
    scores = {}
    for sector_name, data in (sectors_data or {}).items():
        if not isinstance(data, dict):
            continue

        dimension_scores = {
            "fund_flow": _score_fund_flow(data.get("fund_flow") or {}),
            "limit_up": _score_limit_up(data.get("zt_stocks") or []),
            "lhb": _score_lhb(data.get("lhb_data") or []),
            "volume": _score_volume(data.get("volume_change")),
            "sentiment": _score_sentiment(data.get("hot_rank_count")),
        }
        total_score = min(sum(dimension_scores.values()), 10.0)
        strength_dimensions = [key for key, value in dimension_scores.items() if value >= 2.0]

        if total_score >= 7.5 and len(strength_dimensions) >= 2:
            level = "强共振"
        elif total_score >= 5.0 and len(strength_dimensions) >= 2:
            level = "弱共振"
        else:
            level = "无共振"

        if level == "无共振":
            continue

        scores[sector_name] = {
            "total_score": round(total_score, 2),
            "strength_dimensions": strength_dimensions,
            "dimension_scores": {key: round(value, 2) for key, value in dimension_scores.items()},
            "resonance_level": level,
            "volume_change": round(_safe_float(data.get("volume_change")), 2),
        }
    return scores


class _VolumeAnomalyDetectorFallback:
    pass


class _LHBAnalyzerFallback:
    pass


class _ResonanceAnalyzerFallback:
    pass


class _SignalGeneratorFallback:
    pass


VolumeAnomalyDetector = export_or_default("quantitative_analyzer", "VolumeAnomalyDetector", _VolumeAnomalyDetectorFallback)
LHBAnalyzer = export_or_default("quantitative_analyzer", "LHBAnalyzer", _LHBAnalyzerFallback)
ResonanceAnalyzer = export_or_default("quantitative_analyzer", "ResonanceAnalyzer", _ResonanceAnalyzerFallback)
SignalGenerator = export_or_default("quantitative_analyzer", "SignalGenerator", _SignalGeneratorFallback)
analyze_volume_anomaly = export_or_default("quantitative_analyzer", "analyze_volume_anomaly", lambda *args, **kwargs: {})
analyze_lhb = export_or_default("quantitative_analyzer", "analyze_lhb", lambda *args, **kwargs: {})
calculate_resonance = export_or_default("quantitative_analyzer", "calculate_resonance", _fallback_calculate_resonance)
generate_trade_signals = export_or_default("quantitative_analyzer", "generate_trade_signals", lambda *args, **kwargs: {})

__all__ = [
    "VolumeAnomalyDetector",
    "LHBAnalyzer",
    "ResonanceAnalyzer",
    "SignalGenerator",
    "analyze_volume_anomaly",
    "analyze_lhb",
    "calculate_resonance",
    "generate_trade_signals",
]
