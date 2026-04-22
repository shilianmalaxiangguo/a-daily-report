from domains.market_state.contracts import build_market_state_action_map
from domains.market_state.trace import make_market_state_log


def run(ctx):
    inputs = ctx.get("inputs") or {}
    state = ctx.get("state") or {}
    helpers = ctx.get("helpers") or {}
    action_map = helpers.get("action_map") or build_market_state_action_map()
    safe_float = helpers.get("safe_float") or _safe_float

    data = inputs.get("data") or {}
    tracked_sector = state.get("tracked_sector", "")
    sector_inflow = safe_float(state.get("sector_inflow", 0), 0.0)
    hot_weight = safe_float(state.get("hot_weight", 0), 0.0)
    zt_pool_by_sector = state.get("zt_pool_by_sector", {}) or {}
    get_sector_hotlist_weight = helpers.get("get_sector_hotlist_weight") or (lambda *args, **kwargs: 0.0)
    replacement_candidates = []
    for sector in (data.get("sector_fund_flow", {}) or {}).get("inflow", []):
        sector_name = sector.get("name", "")
        if not sector_name or sector_name == tracked_sector:
            continue
        inflow = safe_float(sector.get("zljlr", 0), 0.0)
        sector_hot_weight = safe_float(get_sector_hotlist_weight(sector_name, data.get("tag_distribution", {})), 0.0)
        replacement_candidates.append(
            {
                "name": sector_name,
                "inflow": inflow,
                "zt_count": len(zt_pool_by_sector.get(sector_name, []) or []),
                "hot_weight": sector_hot_weight,
            }
        )
    replacement_candidates.sort(
        key=lambda item: (item.get("inflow", 0), item.get("zt_count", 0), item.get("hot_weight", 0)),
        reverse=True,
    )

    replacement = replacement_candidates[0] if replacement_candidates else None
    if not replacement:
        level = "绿灯"
        status = "未见明显替代主线，资金仍未完成切换"
    elif replacement.get("inflow", 0) > sector_inflow or replacement.get("hot_weight", 0) > hot_weight + 1:
        level = "黄灯"
        status = f"{replacement.get('name', '')}开始试探承接旧主线资金"
    else:
        level = "绿灯"
        status = f"{replacement.get('name', '')}暂未形成有效替代"

    signal = {
        "layer": "替代主线流向",
        "status": status,
        "level": level,
        "action": action_map.get(level, ""),
    }
    return {
        "value": signal,
        "exports": {"competition_signal": signal, "competition_snapshot": {"replacement": replacement or {}, "level": level}},
        "state_patch": {
            "competition_signal": signal,
            "competition_snapshot": {"replacement": replacement or {}, "level": level},
        },
        "module_logs": [
            make_market_state_log(
                "sector_competition",
                "infer.sector_competition",
                "success",
                "competition signal derived",
                tracked_sector=tracked_sector,
                level=level,
            )
        ],
        "errors": [],
        "control": {"status": "success"},
    }


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
