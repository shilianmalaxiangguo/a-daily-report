from domains.market_state.trace import make_market_state_log


def run(ctx):
    state = ctx.get("state") or {}
    helpers = ctx.get("helpers") or {}
    action_map = helpers["action_map"]
    score_to_level = helpers["score_to_level"]

    tracked_sector = state.get("tracked_sector", "")
    mainline_snapshot = state.get("mainline_snapshot", {}) or {}
    mainline_score_pct = float(mainline_snapshot.get("score_pct", 0) or 0)
    sector_inflow = float(state.get("sector_inflow", 0) or 0)
    sector_outflow = float(state.get("sector_outflow", 0) or 0)
    sector_zt_count = int(state.get("sector_zt_count", 0) or 0)
    sector_dt_count = int(state.get("sector_dt_count", 0) or 0)
    hot_weight = float(state.get("hot_weight", 0) or 0)

    status = (
        f"{tracked_sector} {mainline_snapshot.get('star_level', '⭐')}（综合{mainline_score_pct:.0f}分），"
        f"净流入{sector_inflow:+.1f}亿，涨停{sector_zt_count}只，跌停{sector_dt_count}只，热榜占比{hot_weight:.1f}%"
    )
    level = "红灯" if sector_outflow > 12 and sector_dt_count >= 2 else score_to_level(mainline_score_pct)
    if mainline_snapshot.get("flow_trend") == "shrinking" and level == "绿灯":
        level = "黄灯"
    if mainline_snapshot.get("trend_label"):
        status += f"，{mainline_snapshot.get('trend_label')}"

    signal = {
        "layer": "主线地位复核",
        "status": status,
        "level": level,
        "action": action_map[level],
    }
    return {
        "value": signal,
        "exports": {"environment_signal": signal, "mainline_level": level, "mainline_score_pct": mainline_score_pct},
        "state_patch": {"environment_signal": signal, "mainline_level": level, "mainline_score_pct": mainline_score_pct},
        "module_logs": [
            make_market_state_log(
                "environment_signal",
                "infer.environment_signal",
                "success",
                "environment signal derived",
                tracked_sector=tracked_sector,
                level=level,
            )
        ],
        "errors": [],
        "control": {"status": "success"},
    }
