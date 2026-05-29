from adapters.ths.hot_rank_client import fetch_hot_rank


HOOK_NAME = "input.hot_rank"


def run(ctx):
    items = fetch_hot_rank(limit=50)
    return {
        "value": {"hot_rank": items},
        "patches": {
            "raw": {"hot_rank": items},
            "normalized": {
                "market_snapshot": {
                    "hot_rank_count": len(items),
                    "top_hot_rank_codes": [item.get("code", "") for item in items[:10]],
                }
            },
        },
        "diagnostics": {
            "hook_name": HOOK_NAME,
            "status": "success",
            "source_used": "ths",
            "fallback_used": False,
            "warnings": [],
        },
        "artifacts": {},
    }
