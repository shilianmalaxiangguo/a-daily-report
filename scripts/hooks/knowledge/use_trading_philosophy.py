import time

from knowledge.trading_philosophy import build_trading_philosophy_snapshot


HOOK_NAME = "knowledge.trading_philosophy"


def run(ctx):
    started_at = time.perf_counter()
    request = ctx.get("request") or {}
    snapshot = build_trading_philosophy_snapshot(
        target_date=request.get("target_date", ""),
        run_mode=request.get("run_mode", "frozen"),
        has_personal_positions=bool(request.get("has_personal_positions", False)),
        compact=bool(request.get("compact_philosophy", False)),
    )
    derivation = {
        "hook_name": HOOK_NAME,
        "inputs": ["request.target_date", "request.run_mode", "request.has_personal_positions"],
        "assumptions": ["trading philosophy is a versioned knowledge module"],
        "formula": "materialize latest trading philosophy knowledge pack",
        "output_keys": ["knowledge.trading_philosophy"],
        "confidence": 1.0,
        "warnings": [],
    }

    return {
        "value": {"trading_philosophy": snapshot},
        "patches": {
            "knowledge": {"trading_philosophy": snapshot},
            "diagnostics": {"derivations": {"trading_philosophy": derivation}},
        },
        "diagnostics": {
            "hook_name": HOOK_NAME,
            "status": "success",
            "duration_ms": int((time.perf_counter() - started_at) * 1000),
            "warnings": [],
        },
        "artifacts": {},
    }
