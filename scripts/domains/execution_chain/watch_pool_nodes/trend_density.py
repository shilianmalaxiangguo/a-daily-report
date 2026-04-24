def build_watch_pool_trend_density_node(context, node_meta=None, node_lookup=None):
    sector_trend_snapshot = context.get("sector_trend_snapshot_step1", []) or []
    display_mvp_mode = bool(context.get("display_mvp_mode", False))
    if not sector_trend_snapshot:
        return {"lines": [], "exports": {}, "module_logs": []}

    lines = [
        "**主线趋势密度扫描**（先看哪条线里活跃趋势股最多）",
        "| 板块 | 活跃趋势股 | 强势候选 | 涨停家数 | 锚定龙头 | 结论 |",
        "|------|------------|----------|----------|----------|------|",
    ]
    sector_preview = sector_trend_snapshot[:3] if display_mvp_mode else sector_trend_snapshot
    for item in sector_preview:
        anchor_text = f"{item.get('anchor_name', '-')}"
        if item.get("anchor_code"):
            anchor_text += f"({item.get('anchor_code')})"
        lines.append(
            f"| {item.get('sector', '-')} | {item.get('trend_count', 0)}只 | "
            f"{item.get('strong_count', 0)}只 | {item.get('limit_up_count', 0)}只 | "
            f"{anchor_text} | {item.get('anchor_reason', '-')} |"
        )
    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}
