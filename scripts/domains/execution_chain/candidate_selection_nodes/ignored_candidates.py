def build_candidate_selection_ignored_candidates_node(context, node_meta=None, node_lookup=None):
    ignored_stocks = context.get("ignored_stocks", []) or []
    if not ignored_stocks:
        return {"lines": [], "exports": {}, "module_logs": []}

    lines = [f"**暂不关注**: {len(ignored_stocks)}只（预判明日强度不足）"]
    for stock in ignored_stocks[:3]:
        lines.append(
            f"- {stock.get('name')}({stock.get('code')}) - 强度{stock.get('tomorrow_strength', 0)}分 - "
            f"{stock.get('abnormal_summary', '无明显异动')} - {stock.get('tmr_forecast', '')}"
        )
    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}
