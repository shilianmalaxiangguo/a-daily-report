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

    def as_sector_item(item):
        return item if isinstance(item, dict) else {}

    if enhanced_main_sectors:
        tracked_sector = str(enhanced_main_sectors[0] or "").strip()
    else:
        main_sectors = market_analysis.get("main_sectors", []) if market_analysis else []
        tracked_sector = str(((main_sectors[0] or {}).get("name", "")) if main_sectors else "").strip()
    if not tracked_sector and inflow_sectors:
        for item in inflow_sectors:
            sector_name = str(as_sector_item(item).get("name", "") or "").strip()
            if sector_name:
                tracked_sector = sector_name
                break

    safe_float = helpers.get("safe_float", float)

    def _safe_float_with_default(value, default):
        try:
            return safe_float(value, default=default)
        except TypeError:
            return None
        except ValueError:
            return default

    def _safe_float_basic(value):
        try:
            return safe_float(value)
        except (TypeError, ValueError):
            return None

    def parse_float(value, default=0.0):
        # Compatible with both helper styles:
        # 1) safe_float(value, default=...)
        # 2) safe_float(value)
        with_default = _safe_float_with_default(value, default)
        if with_default is not None:
            return with_default
        basic_value = _safe_float_basic(value)
        if basic_value is not None:
            return basic_value
        return default

    inflow_map = {}
    for item in inflow_sectors:
        sector_item = as_sector_item(item)
        sector_name = sector_item.get("name", "")
        inflow_map[sector_name] = parse_float(sector_item.get("zljlr", 0), default=0.0)

    outflow_map = {}
    for item in outflow_sectors:
        sector_item = as_sector_item(item)
        sector_name = sector_item.get("name", "")
        outflow_map[sector_name] = abs(parse_float(sector_item.get("zljlr", 0), default=0.0))
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

    mainline_candidates = {
        "tracked_sector": tracked_sector,
        "sector_inflow": sector_inflow,
        "sector_outflow": sector_outflow,
        "sector_zt_count": sector_zt_count,
        "sector_dt_count": sector_dt_count,
        "hot_weight": hot_weight,
        "inflow_history": inflow_history,
        "mainline_snapshot": mainline_snapshot,
    }
    # Canonical workflow-level export key.
    # Flat fields are kept for current downstream/state compatibility in Task 4.
    exports = {
        "mainline_candidates": mainline_candidates,
        "tracked_sector": tracked_sector,
        "sector_inflow": sector_inflow,
        "sector_outflow": sector_outflow,
        "sector_zt_count": sector_zt_count,
        "sector_dt_count": sector_dt_count,
        "hot_weight": hot_weight,
        "inflow_history": inflow_history,
        "mainline_snapshot": mainline_snapshot,
    }
    state_patch = dict(mainline_candidates)
    state_patch["mainline_candidates"] = mainline_candidates
    return {
        "value": exports,
        "exports": exports,
        "state_patch": state_patch,
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
