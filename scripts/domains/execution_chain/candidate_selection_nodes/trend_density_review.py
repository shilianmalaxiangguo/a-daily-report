def build_candidate_selection_trend_density_review_node(context, node_meta=None, node_lookup=None):
    sector_trend_snapshot = context.get("sector_trend_snapshot", []) or []
    if not sector_trend_snapshot:
        return {"lines": [], "exports": {}, "module_logs": []}

    lines = [
        "**主线趋势密度复核**（不只看单个龙头，还看一条线里有多少活口）:",
        "| 板块 | 活跃趋势股 | 核心候选 | 锚定龙头 | 密度分 | 交易含义 |",
        "|------|------------|----------|----------|--------|----------|",
    ]
    for item in sector_trend_snapshot:
        anchor_text = f"{item.get('anchor_name', '-')}"
        if item.get("anchor_code"):
            anchor_text += f"({item.get('anchor_code')})"
        lines.append(
            f"| {item.get('sector', '-')} | {item.get('trend_count', 0)}只 | "
            f"{item.get('core_count', 0)}只 | {anchor_text} | {item.get('density_score', 0)} | "
            f"{item.get('anchor_reason', '-')} |"
        )
    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}
