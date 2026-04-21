import time


HOOK_NAME = "infer.market_phase"


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

    turnover_change_pct = float(snapshot.get("turnover_change_pct", 0))
    rise_fall_ratio = float(snapshot.get("rise_fall_ratio", 1))
    dt_count = int(snapshot.get("dt_count", 0))
    zhongshu_signal = str(snapshot.get("zhongshu_signal", "unknown"))

    phase = "defend" if (
        not missing_inputs
        and
        turnover_change_pct <= -5
        and rise_fall_ratio < 0.8
        and dt_count >= 8
        and zhongshu_signal == "not_open"
    ) else "observe"

    degraded = bool(missing_inputs)
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
        "warnings": ["missing required market snapshot inputs"] if degraded else [],
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
            "warnings": derivation["warnings"],
        },
        "artifacts": {},
    }
