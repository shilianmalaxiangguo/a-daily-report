HOOK_NAME = "infer.market_phase"


def run(ctx):
    snapshot = ((ctx.get("normalized") or {}).get("market_snapshot") or {})
    turnover_change_pct = float(snapshot.get("turnover_change_pct", 0))
    rise_fall_ratio = float(snapshot.get("rise_fall_ratio", 1))
    dt_count = int(snapshot.get("dt_count", 0))
    zhongshu_signal = str(snapshot.get("zhongshu_signal", "unknown"))

    phase = "defend" if (
        turnover_change_pct <= -5
        and rise_fall_ratio < 0.8
        and dt_count >= 8
        and zhongshu_signal == "not_open"
    ) else "observe"

    derivation = {
        "hook_name": HOOK_NAME,
        "inputs": ["normalized.market_snapshot"],
        "assumptions": ["turnover <= -5", "rise_fall_ratio < 0.8", "dt_count >= 8"],
        "formula": "defend if turnover weak and breadth weak and zhongshu not open",
        "output_keys": ["derived.market_phase"],
        "confidence": 0.8 if phase == "defend" else 0.6,
        "warnings": [],
    }

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
            "status": "success",
            "confidence": derivation["confidence"],
            "warnings": [],
        },
        "artifacts": {},
    }
