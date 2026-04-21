from collections import Counter


HOOK_NAME = "infer.mainline"


def run(ctx):
    hot_rank = ((ctx.get("raw") or {}).get("hot_rank") or [])
    market_snapshot = ((ctx.get("normalized") or {}).get("market_snapshot") or {})
    market_phase = ((ctx.get("derived") or {}).get("market_phase") or {})
    sectors = [item.get("sector", "未知") for item in hot_rank if item.get("sector")]
    counts = Counter(sectors)
    primary_line, primary_count = counts.most_common(1)[0] if counts else ("未知", 0)
    missing_inputs = []
    hot_rank_count = market_snapshot.get("hot_rank_count")
    if hot_rank_count is None:
        missing_inputs.append("normalized.market_snapshot.hot_rank_count")
    if not market_phase:
        missing_inputs.append("derived.market_phase")
    if hot_rank_count is not None and hot_rank_count != len(hot_rank):
        missing_inputs.append("normalized.market_snapshot.hot_rank_count")

    derivation = {
        "hook_name": HOOK_NAME,
        "inputs": ["raw.hot_rank", "normalized.market_snapshot", "derived.market_phase"],
        "assumptions": ["sector frequency approximates line concentration"],
        "formula": "choose most frequent sector in hot_rank",
        "output_keys": ["derived.mainline"],
        "confidence": 0.75 if primary_count >= 2 else 0.55,
        "hot_rank_count": hot_rank_count if hot_rank_count is not None else len(hot_rank),
        "missing_inputs": missing_inputs,
        "warnings": [],
    }
    warnings = []
    if hot_rank_count is None:
        warnings.append("missing normalized.market_snapshot.hot_rank_count")
    elif hot_rank_count != len(hot_rank):
        warnings.append("normalized.market_snapshot.hot_rank_count does not match raw.hot_rank")
    if not market_phase:
        warnings.append("missing derived.market_phase")

    return {
        "value": {"mainline": primary_line},
        "patches": {
            "derived": {
                "mainline": {
                    "primary_line": primary_line,
                    "sector_counts": dict(counts),
                    "hot_rank_weight": primary_count,
                }
            },
            "diagnostics": {"derivations": {"mainline": derivation}},
        },
        "diagnostics": {
            "hook_name": HOOK_NAME,
            "status": "degraded" if missing_inputs else "success",
            "duration_ms": 0,
            "confidence": derivation["confidence"],
            "source_used": "raw.hot_rank + normalized.market_snapshot",
            "fallback_used": False,
            "missing_inputs": missing_inputs,
            "warnings": warnings,
        },
        "artifacts": {},
    }
