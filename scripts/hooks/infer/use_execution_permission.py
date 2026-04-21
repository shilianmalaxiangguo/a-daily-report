HOOK_NAME = "infer.execution_permission"


def run(ctx):
    import time

    started_at = time.perf_counter()
    derived = ctx.get("derived") or {}
    market_phase = derived.get("market_phase") or {}
    phase_missing = "market_phase" not in derived
    mainline_missing = "mainline" not in derived
    phase = (market_phase.get("phase") or "observe").strip()
    mainline = ((derived.get("mainline") or {}).get("primary_line") or "未知").strip()

    label = "watch_only" if phase == "defend" else "conditional_30"
    reason = f"phase={phase}; primary_line={mainline}"
    warnings = []
    if phase_missing:
        warnings.append("missing derived.market_phase")
    if mainline_missing:
        warnings.append("missing derived.mainline")
    derivation = {
        "hook_name": HOOK_NAME,
        "inputs": ["derived.market_phase", "derived.mainline"],
        "assumptions": ["defensive phase blocks new execution"],
        "formula": "watch_only if phase == defend else conditional_30",
        "output_keys": ["derived.execution_permission", "decision.execution_permission"],
        "confidence": 0.85 if phase == "defend" else (0.55 if warnings else 0.65),
        "warnings": warnings,
    }
    duration_ms = int((time.perf_counter() - started_at) * 1000)

    return {
        "value": {"execution_permission": label},
        "patches": {
            "derived": {
                "execution_permission": {
                    "label": label,
                    "reason": reason,
                }
            },
            "decision": {
                "execution_permission": {
                    "label": label,
                    "reason": reason,
                }
            },
            "diagnostics": {"derivations": {"execution_permission": derivation}},
        },
        "diagnostics": {
            "hook_name": HOOK_NAME,
            "status": "degraded" if warnings else "success",
            "duration_ms": duration_ms,
            "confidence": derivation["confidence"],
            "warnings": warnings,
        },
        "artifacts": {},
    }
