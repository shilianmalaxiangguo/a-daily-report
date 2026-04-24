def build_candidate_selection_conviction_list_node(context, node_meta=None, node_lookup=None):
    extreme_conviction_list = context.get("extreme_conviction_list", []) or []

    lines = ["**极度看好名单**（只保留最心动的少数，其他只观察）:"]
    if extreme_conviction_list:
        lines.append("| 优先级 | 股票 | 代码 | 所属板块 | 极看理由 | 明日原则 |")
        lines.append("|--------|------|------|----------|----------|----------|")
        for idx, stock in enumerate(extreme_conviction_list, 1):
            lines.append(
                f"| {idx} | {stock.get('name', '-')} | {stock.get('code', '-')} | "
                f"{stock.get('sector', '-')} | {stock.get('conviction_reason', '-')} | "
                f"{stock.get('conviction_rule', '-')} |"
            )
    else:
        lines.append("- 暂无极度看好标的，说明当下更适合广泛观察而不是集中出手。")
    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}
