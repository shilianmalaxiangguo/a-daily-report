from __future__ import annotations

from legacy_runtime_shim import export_or_default


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
calculate_resonance = export_or_default("quantitative_analyzer", "calculate_resonance", lambda *args, **kwargs: {})
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
