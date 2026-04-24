def build_candidate_selection_crossline_watch_node(context, node_meta=None, node_lookup=None):
    crossline_observation_stocks = context.get("crossline_observation_stocks", []) or []
    display_mvp_mode = bool(context.get("display_mvp_mode", False))
    safe_float = context["safe_float"]

    if not crossline_observation_stocks:
        return {"lines": [], "exports": {}, "module_logs": []}

    lines = [
        "**跨线观察候选**（只看能量迁移，不作为主线执行对象）:",
        "> **观察纪律**：跨线对象只用于确认资金是否外溢/切换，不代表主攻线已经切换。",
        "| 序号 | 股票 | 代码 | 板块 | 异动跟踪 | 预判强度 | 观察意义 | 明日原则 |",
        "|------|------|------|------|----------|----------|----------|----------|",
    ]
    crossline_preview = crossline_observation_stocks[:2] if display_mvp_mode else crossline_observation_stocks[:4]
    for idx, stock in enumerate(crossline_preview, 1):
        crossline_sector = stock.get("sector", "其他")
        follow_state = stock.get("abnormal_follow_state", "")
        if follow_state in ["跌不下去", "缩量消化"]:
            observation_reason = f"{crossline_sector}承接偏强，观察是否形成竞争线"
        else:
            observation_reason = f"{crossline_sector}有异动，先看是否只是情绪脉冲"
        lines.append(
            f"| {idx} | {stock.get('name', '-')} | {stock.get('code', '-')} | {crossline_sector} | "
            f"{stock.get('abnormal_summary', '无明显异动')} | {safe_float(stock.get('tomorrow_strength', 0)):.0f}分 | "
            f"{observation_reason} | 只看强弱，不直接给买入指令 |"
        )
    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}
