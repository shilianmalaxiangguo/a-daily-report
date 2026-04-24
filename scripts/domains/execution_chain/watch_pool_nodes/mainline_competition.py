def build_watch_pool_mainline_competition_node(context, node_meta=None, node_lookup=None):
    snapshot = context.get("mainline_competition_snapshot", []) or []
    if not snapshot:
        return {"lines": [], "exports": {}, "module_logs": []}

    lines = [
        "**主线竞争格局**（不是板块名单，而是能量争夺排序）",
        "| 角色 | 方向 | 当前证据 | 判断 | 操作原则 |",
        "|------|------|----------|------|----------|",
    ]
    for item in snapshot:
        lines.append(
            f"| {item.get('role', '-')} | {item.get('sector', '-')} | {item.get('evidence', '-')} | "
            f"{item.get('judgement', '-')} | {item.get('action', '-')} |"
        )
    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}
