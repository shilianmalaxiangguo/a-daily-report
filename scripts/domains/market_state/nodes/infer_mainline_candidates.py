from domains.market_state.trace import make_market_state_log


def run(ctx):
    inputs = ctx.get("inputs") or {}
    helpers = ctx.get("helpers") or {}
    data = inputs.get("data") or {}
    market_analysis = inputs.get("market_analysis") or {}
    enhanced_main_sectors = list(inputs.get("enhanced_main_sectors") or [])

    sector_fund_flow = data.get("sector_fund_flow", {}) or {}
    inflow_sectors = sector_fund_flow.get("inflow", []) or []
    outflow_sectors = sector_fund_flow.get("outflow", []) or []

    if enhanced_main_sectors:
        tracked_sector = str(enhanced_main_sectors[0] or "").strip()
    else:
        main_sectors = market_analysis.get("main_sectors", []) if market_analysis else []
        tracked_sector = str(((main_sectors[0] or {}).get("name", "")) if main_sectors else "").strip()
    if not tracked_sector and inflow_sectors:
        tracked_sector = str((inflow_sectors[0] or {}).get("name", "") or "").strip()

    inflow_map = {item.get("name", ""): item.get("zljlr", 0) for item in inflow_sectors}
    outflow_map = {item.get("name", ""): abs(item.get("zljlr", 0)) for item in outflow_sectors}
    zt_pool_by_sector = data.get("zt_pool_by_sector", {}) or {}
    dt_pool_by_sector = data.get("dt_pool_by_sector", {}) or {}

    get_sector_hotlist_weight = helpers["get_sector_hotlist_weight"]
    load_recent_sector_flow_history = helpers["load_recent_sector_flow_history"]
    get_mainline_star_level = helpers["get_mainline_star_level"]

    sector_inflow = inflow_map.get(tracked_sector, 0)
    sector_outflow = outflow_map.get(tracked_sector, 0)
    sector_zt_count = len(zt_pool_by_sector.get(tracked_sector, []) or [])
    sector_dt_count = len(dt_pool_by_sector.get(tracked_sector, []) or [])
    hot_weight = get_sector_hotlist_weight(tracked_sector, data.get("tag_distribution", {})) if tracked_sector else 0
    inflow_history = load_recent_sector_flow_history(data.get("target_date", ""), tracked_sector, lookback_days=2) if tracked_sector else []
    mainline_snapshot = get_mainline_star_level(
        sector_inflow,
        sector_zt_count,
        dt_count=sector_dt_count,
        hot_weight=hot_weight,
        inflow_history=inflow_history,
    ) if tracked_sector else {}

    exports = {
        "tracked_sector": tracked_sector,
        "sector_inflow": sector_inflow,
        "sector_outflow": sector_outflow,
        "sector_zt_count": sector_zt_count,
        "sector_dt_count": sector_dt_count,
        "hot_weight": hot_weight,
        "inflow_history": inflow_history,
        "mainline_snapshot": mainline_snapshot,
        "zt_pool_by_sector": zt_pool_by_sector,
        "dt_pool_by_sector": dt_pool_by_sector,
    }
    return {
        "value": exports,
        "exports": exports,
        "state_patch": exports,
        "module_logs": [
            make_market_state_log(
                "mainline_candidates",
                "infer.mainline_candidates",
                "success",
                "tracked sector derived",
                tracked_sector=tracked_sector,
            )
        ],
        "errors": [],
        "control": {"status": "success"},
    }
