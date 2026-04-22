def render_action_plan_section(context):
    context = context or {}
    lines = [
        "#### Step 5 - 明日操作计划",
        "> **核心问题**：明天具体怎么执行？盘前准备什么？开盘看什么？盘中怎么买？",
        "",
        "**Step 5.1 最终动作表**（只展示真正可执行对象）:",
        "",
        "| 明天具体怎么做 | 股票 | 代码 | 触发条件 | 止损/时间 |",
        "|----------|------|------|----------|-----------|",
    ]

    action_rows = context.get("action_rows") or []
    if action_rows:
        for row in action_rows:
            lines.append(
                f"| {row.get('action', '-')} | {row.get('name', '-')} | {row.get('code', '-')} | "
                f"{row.get('trigger', '-')} | {row.get('risk_window', '-')} |"
            )
    else:
        lines.append("| ❌ 明天没有可买对象 | - | - | 无符合条件标的 | - |")
    lines.append("")

    for block_title, block_lines in (
        ("**先看顺序**（优先盯最能反映主线承接的对象）:", context.get("observation_priority_lines") or []),
        ("**备用观察**（买点未触发，明日不操作）:", context.get("backup_observation_lines") or []),
    ):
        if block_lines:
            lines.append(block_title)
            lines.extend(block_lines)
            lines.append("")

    lines.append("**Step 5.2 明天仓位怎么放**:")
    lines.extend(context.get("position_section_lines") or [])
    lines.append("")

    lines.append("**Step 5.3 明日执行时间表**:")
    lines.append("")

    schedule_sections = [
        ("**盘前准备（08:30-09:15）**:", context.get("pre_market_lines") or []),
        ("**开盘前30分钟（09:30-10:00）**:", context.get("opening_lines") or []),
        ("**首个60分钟确认（09:30-10:30）**:", context.get("first_hour_lines") or []),
        ("**盘中执行（10:30-14:30）**:", context.get("intraday_lines") or []),
        ("**尾盘（14:30-15:00）**:", context.get("closing_lines") or []),
    ]
    for title, section_lines in schedule_sections:
        lines.append(title)
        lines.extend(section_lines)
        lines.append("")

    alert_rows = context.get("alert_rows") or []
    if alert_rows:
        lines.append("**⚠️ 异动预警**:")
        lines.append("| 股票 | 偏离天数 | 触发条件 | 实际涨幅 | 状态 |")
        lines.append("|------|----------|----------|----------|------|")
        for row in alert_rows:
            lines.append(
                f"| {row.get('name', '-')}({row.get('code', '-')}) | {row.get('deviation_days', 0)}天 | "
                f"{row.get('trigger_info', '-')} | {row.get('actual_change_str', '-')} | {row.get('trigger_status', '-')} |"
            )
        lines.append("")

    return lines
