def build_watch_pool_leader_memory_node(context, node_meta=None, node_lookup=None):
    leader_memory_bank = context.get("leader_memory_bank", []) or []
    if not leader_memory_bank:
        return {"lines": [], "exports": {}, "module_logs": []}

    lines = [
        "**龙头记忆库**（第一次异动先记住，后面优先回看这些）",
        "| 股票 | 代码 | 板块 | 记忆理由 | 回看窗口 | 明日原则 |",
        "|------|------|------|----------|----------|----------|",
    ]
    for item in leader_memory_bank:
        lines.append(
            f"| {item.get('name', '-')} | {item.get('code', '-')} | {item.get('sector', '-')} | "
            f"{item.get('remember_reason', '-')} | {item.get('remember_window', '-')} | {item.get('action_rule', '-')} |"
        )
    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}
