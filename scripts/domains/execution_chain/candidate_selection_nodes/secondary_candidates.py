def build_candidate_selection_secondary_candidates_node(context, node_meta=None, node_lookup=None):
    secondary_stocks = context.get("secondary_stocks", []) or []
    display_mvp_mode = bool(context.get("display_mvp_mode", False))

    lines = ["**明日次核心预判**（主线内备选观察）:"]
    if secondary_stocks:
        lines.append("| 序号 | 股票 | 代码 | 板块 | 异动跟踪 | 预判强度 | 明日预期 |")
        lines.append("|------|------|------|------|----------|----------|----------|")
        secondary_preview = secondary_stocks[:2] if display_mvp_mode else secondary_stocks
        for idx, stock in enumerate(secondary_preview, 1):
            lines.append(
                f"| {idx} | {stock.get('name', '-')} | {stock.get('code', '-')} | {stock.get('sector', '-')} | "
                f"{stock.get('abnormal_summary', '无明显异动')} | {stock.get('tomorrow_strength', 0)}分 | {stock.get('tmr_forecast', '-')} |"
            )
    else:
        lines.append("- 无次核心股")

    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}
