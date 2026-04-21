import time


HOOK_NAME = "infer.market_phase"


def _coerce_float(value, default, field_name, malformed_inputs):
    try:
        return float(value), False
    except (TypeError, ValueError):
        malformed_inputs.append(field_name)
        return default, True


def _coerce_int(value, default, field_name, malformed_inputs):
    try:
        return int(value), False
    except (TypeError, ValueError):
        malformed_inputs.append(field_name)
        return default, True


def run(ctx):
    started_at = time.perf_counter()
    normalized = ctx.get("normalized") or {}
    snapshot = normalized.get("market_snapshot") or {}
    required_fields = (
        "turnover_change_pct",
        "rise_fall_ratio",
        "dt_count",
        "zhongshu_signal",
    )
    missing_inputs = [
        f"normalized.market_snapshot.{field}"
        for field in required_fields
        if field not in snapshot
    ]
    malformed_inputs = []

    turnover_change_pct, _ = _coerce_float(
        snapshot.get("turnover_change_pct", 0),
        0,
        "normalized.market_snapshot.turnover_change_pct",
        malformed_inputs,
    )
    rise_fall_ratio, _ = _coerce_float(
        snapshot.get("rise_fall_ratio", 1),
        1,
        "normalized.market_snapshot.rise_fall_ratio",
        malformed_inputs,
    )
    dt_count, _ = _coerce_int(
        snapshot.get("dt_count", 0),
        0,
        "normalized.market_snapshot.dt_count",
        malformed_inputs,
    )
    zhongshu_signal = str(snapshot.get("zhongshu_signal", "unknown"))

    phase = "defend" if (
        not missing_inputs
        and
        turnover_change_pct <= -5
        and rise_fall_ratio < 0.8
        and dt_count >= 8
        and zhongshu_signal == "not_open"
    ) else "observe"

    degraded = bool(missing_inputs or malformed_inputs)
    derivation = {
        "hook_name": HOOK_NAME,
        "inputs": [
            "normalized.market_snapshot.turnover_change_pct",
            "normalized.market_snapshot.rise_fall_ratio",
            "normalized.market_snapshot.dt_count",
            "normalized.market_snapshot.zhongshu_signal",
        ],
        "assumptions": ["turnover <= -5", "rise_fall_ratio < 0.8", "dt_count >= 8"],
        "formula": "defend if turnover weak and breadth weak and zhongshu not open",
        "output_keys": ["derived.market_phase"],
        "confidence": 0.8 if phase == "defend" else (0.4 if degraded else 0.6),
        "turnover_change_pct": turnover_change_pct,
        "rise_fall_ratio": rise_fall_ratio,
        "dt_count": dt_count,
        "zhongshu_signal": zhongshu_signal,
        "missing_inputs": missing_inputs,
        "malformed_inputs": malformed_inputs,
        "warnings": ["missing or malformed market snapshot inputs"] if degraded else [],
    }

    duration_ms = int((time.perf_counter() - started_at) * 1000)

    return {
        "value": {"market_phase": phase},
        "patches": {
            "derived": {
                "market_phase": {
                    "phase": phase,
                    "turnover_change_pct": turnover_change_pct,
                    "rise_fall_ratio": rise_fall_ratio,
                }
            },
            "diagnostics": {"derivations": {"market_phase": derivation}},
        },
        "diagnostics": {
            "hook_name": HOOK_NAME,
            "status": "degraded" if degraded else "success",
            "duration_ms": duration_ms,
            "confidence": derivation["confidence"],
            "source_used": "normalized.market_snapshot",
            "fallback_used": False,
            "missing_inputs": missing_inputs,
            "malformed_inputs": malformed_inputs,
            "warnings": derivation["warnings"],
        },
        "artifacts": {},
    }
