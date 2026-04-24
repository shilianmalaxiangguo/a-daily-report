def build_watch_pool_a_kill_filter_node(context, node_meta=None, node_lookup=None):
    filtered_by_a_kill = context.get("filtered_by_a_kill", []) or []
    if not filtered_by_a_kill:
        return {"lines": [], "exports": {}, "module_logs": []}

    lines = [f"**A杀过滤**（剔除{len(filtered_by_a_kill)}只）:"]
    for candidate, record in filtered_by_a_kill[:5]:
        lines.append(f"- ❌ {candidate.get('name')}({candidate.get('code')}) - A杀日{record.get('a_kill_date')} - 剩余{record.get('remaining_days')}天禁买")
    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}
