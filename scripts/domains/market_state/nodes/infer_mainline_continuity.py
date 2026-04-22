from domains.market_state.trace import make_market_state_log


def run(ctx):
    inputs = ctx.get("inputs") or {}
    state = ctx.get("state") or {}
    helpers = ctx.get("helpers") or {}
    action_map = helpers["action_map"]
    level_to_score = helpers["level_to_score"]
    clamp = helpers["clamp"]

    data = inputs.get("data") or {}
    tracked_sector = state.get("tracked_sector", "")
    sector_zt_count = int(state.get("sector_zt_count", 0) or 0)
    sector_dt_count = int(state.get("sector_dt_count", 0) or 0)
    hot_weight = float(state.get("hot_weight", 0) or 0)
    dragon_stocks = list(inputs.get("dragon_stocks") or [])
    dt_pool_by_sector = state.get("dt_pool_by_sector", {}) or {}

    leader = helpers["get_sector_leader"](tracked_sector, dragon_stocks, dt_pool_by_sector)
    lhb_net_sell_codes = {
        helpers["normalize_stock_code"](item.get("code", ""))
        for item in data.get("lhb_net_sell_top10", [])
    }
    if leader and leader.get("is_limit_down"):
        leader_level = "红灯"
        leader_status = f"{leader.get('name', '-')}({leader.get('zt_type', '-')})，龙头已跌停失守"
    elif leader and leader.get("code", "") in lhb_net_sell_codes:
        leader_level = "橙灯"
        leader_status = f"{leader.get('name', '-')}({leader.get('zt_type', '-')})，龙虎榜出现净卖出"
    elif leader and float(leader.get("lianban", 0) or 0) >= 3:
        leader_level = "绿灯"
        leader_status = f"{leader.get('name', '-')}({leader.get('zt_type', '-')})，连板高度{int(leader.get('lianban', 0))}板"
    else:
        leader_level = "黄灯"
        leader_status = f"{tracked_sector}暂无明确涨停龙头，板块承接偏弱"

    if sector_zt_count >= 15 and sector_dt_count == 0:
        structure_level = "绿灯"
        structure_status = f"涨停{sector_zt_count}只 / 跌停{sector_dt_count}只，主升结构完整"
    elif sector_zt_count >= 5 and sector_dt_count <= 1:
        structure_level = "黄灯"
        structure_status = f"涨停{sector_zt_count}只 / 跌停{sector_dt_count}只，正常分歧，仍有反复空间"
    elif sector_dt_count >= 3:
        structure_level = "红灯"
        structure_status = f"涨停{sector_zt_count}只 / 跌停{sector_dt_count}只，跌停扩散，退潮明显"
    else:
        structure_level = "橙灯"
        structure_status = f"涨停{sector_zt_count}只 / 跌停{sector_dt_count}只，涨停回落，结构开始松动"

    core_stock = helpers["get_sector_core_hot_stock"](tracked_sector, data.get("hot_rank_top30", []))
    if core_stock and float(core_stock.get("change_pct", 0) or 0) > 0 and int(core_stock.get("hot_rank", 99) or 99) <= 10:
        core_level = "绿灯"
        core_status = f"{core_stock.get('name', '-')}热榜第{int(core_stock.get('hot_rank', 0))}，涨幅{float(core_stock.get('change_pct', 0)):+.2f}%，仍是板块交易核心"
    elif core_stock:
        core_level = "黄灯"
        core_status = f"{core_stock.get('name', '-')}热榜第{int(core_stock.get('hot_rank', 0))}，涨幅{float(core_stock.get('change_pct', 0)):+.2f}%，承接尚可但需要盯紧"
    elif hot_weight >= 1:
        core_level = "橙灯"
        core_status = f"{tracked_sector}在热榜核心区缺少明确承接，热榜占比仅{hot_weight:.1f}%"
    else:
        core_level = "红灯"
        core_status = f"{tracked_sector}在热榜核心区缺少明确承接，主线关注度明显流失"

    leader_score = clamp(level_to_score(leader_level), 0.0, 100.0)
    structure_score = clamp(level_to_score(structure_level), 0.0, 100.0)
    core_score = clamp(level_to_score(core_level), 0.0, 100.0)

    exports = {
        "leader_signal": {"layer": "龙头健康度", "status": leader_status, "level": leader_level, "action": action_map[leader_level]},
        "structure_signal": {"layer": "板块内部结构", "status": structure_status, "level": structure_level, "action": action_map[structure_level]},
        "core_signal": {"layer": "持仓个股承接", "status": core_status, "level": core_level, "action": action_map[core_level]},
        "continuity_snapshot": {
            "leader_score": leader_score,
            "structure_score": structure_score,
            "core_score": core_score,
            "leader_name": leader.get("name", "-") if leader else "-",
        },
    }
    return {
        "value": exports,
        "exports": exports,
        "state_patch": exports,
        "module_logs": [
            make_market_state_log(
                "mainline_continuity",
                "infer.mainline_continuity",
                "success",
                "continuity signals derived",
                tracked_sector=tracked_sector,
            )
        ],
        "errors": [],
        "control": {"status": "success"},
    }
