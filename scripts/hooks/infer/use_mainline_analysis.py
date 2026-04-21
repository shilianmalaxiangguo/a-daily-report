from collections import Counter


HOOK_NAME = "infer.mainline"


def run(ctx):
    hot_rank = ((ctx.get("raw") or {}).get("hot_rank") or [])
    sectors = [item.get("sector", "未知") for item in hot_rank if item.get("sector")]
    counts = Counter(sectors)
    primary_line, primary_count = counts.most_common(1)[0] if counts else ("未知", 0)

    derivation = {
        "hook_name": HOOK_NAME,
        "inputs": ["raw.hot_rank", "derived.market_phase"],
        "assumptions": ["sector frequency approximates line concentration"],
        "formula": "choose most frequent sector in hot_rank",
        "output_keys": ["derived.mainline_analysis"],
        "confidence": 0.75 if primary_count >= 2 else 0.55,
        "warnings": [],
    }

    return {
        "value": {"primary_line": primary_line},
        "patches": {
            "derived": {
                "mainline_analysis": {
                    "primary_line": primary_line,
                    "sector_counts": dict(counts),
                    "hot_rank_weight": primary_count,
                }
            },
            "diagnostics": {"derivations": {"mainline_analysis": derivation}},
        },
        "diagnostics": {
            "hook_name": HOOK_NAME,
            "status": "success",
            "confidence": derivation["confidence"],
            "warnings": [],
        },
        "artifacts": {},
    }
