from collections import Counter


HOOK_NAME = "infer.mainline"


def run(ctx):
    hot_rank = ((ctx.get("raw") or {}).get("hot_rank") or [])
    market_phase = ((ctx.get("derived") or {}).get("market_phase") or {})
    sectors = [item.get("sector", "未知") for item in hot_rank if item.get("sector")]
    counts = Counter(sectors)
    primary_line, primary_count = counts.most_common(1)[0] if counts else ("未知", 0)
    missing_inputs = []
    if not market_phase:
        missing_inputs.append("derived.market_phase")

    derivation = {
        "hook_name": HOOK_NAME,
        "inputs": ["raw.hot_rank", "derived.market_phase"],
        "assumptions": ["sector frequency approximates line concentration"],
        "formula": "choose most frequent sector in hot_rank",
        "output_keys": ["derived.mainline"],
        "confidence": 0.75 if primary_count >= 2 else 0.55,
        "missing_inputs": missing_inputs,
        "warnings": [],
    }

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
            "missing_inputs": missing_inputs,
            "warnings": ["missing derived.market_phase"] if missing_inputs else [],
        },
        "artifacts": {},
    }
