def build_candidate_selection_crossline_watch_node(context, node_meta=None, node_lookup=None):
    crossline_observation_stocks = context.get("crossline_observation_stocks", []) or []
    display_mvp_mode = bool(context.get("display_mvp_mode", False))
    safe_float = context["safe_float"]

    if not crossline_observation_stocks:
        return {"lines": [], "exports": {}, "module_logs": []}

    lines = [
        "**跨线观察候选**（只看能量迁移，不作为主线执行对象）:",
        "| 股票 | 代码 | 所属方向 | 观察意义 | 明日原则 |",
        "|------|------|----------|----------|----------|",
    ]
    crossline_preview = crossline_observation_stocks[:2] if display_mvp_mode else crossline_observation_stocks[:4]
    for stock in crossline_preview:
        crossline_sector = stock.get("sector", "其他")
        follow_state = stock.get("abnormal_follow_state", "")
        if follow_state in ["跌不下去", "缩量消化"]:
            observation_reason = f"{crossline_sector}承接偏强，观察是否形成竞争线"
        else:
            observation_reason = f"{crossline_sector}有异动，先看是否只是情绪脉冲"
        lines.append(
            f"| {stock.get('name', '-')} | {stock.get('code', '-')} | {crossline_sector} | "
            f"{observation_reason} | 只看，不买 |"
        )
    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}
