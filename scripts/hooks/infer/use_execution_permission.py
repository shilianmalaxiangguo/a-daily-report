HOOK_NAME = "infer.execution_permission"


def run(ctx):
    derived = ctx.get("derived") or {}
    phase = ((derived.get("market_phase") or {}).get("phase") or "observe").strip()
    mainline = ((derived.get("mainline") or {}).get("primary_line") or "未知").strip()

    label = "watch_only" if phase == "defend" else "conditional_30"
    reason = f"phase={phase}; primary_line={mainline}"
    derivation = {
        "hook_name": HOOK_NAME,
        "inputs": ["derived.market_phase", "derived.mainline"],
        "assumptions": ["defensive phase blocks new execution"],
        "formula": "watch_only if phase == defend else conditional_30",
        "output_keys": ["decision.execution_permission"],
        "confidence": 0.85 if phase == "defend" else 0.65,
        "warnings": [],
    }

    return {
        "value": {"execution_permission": label},
        "patches": {
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
            "status": "success",
            "confidence": derivation["confidence"],
            "warnings": [],
        },
        "artifacts": {},
    }
