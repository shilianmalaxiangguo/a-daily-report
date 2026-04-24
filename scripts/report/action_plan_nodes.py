def build_action_plan_overview_node(context, node_meta=None, node_lookup=None):
    section_title = str(context.get("section_title", "") or "明日操作计划").strip() or "明日操作计划"
    return {
        "lines": [
            f"#### {section_title}",
            "> **先看结论**：明天只执行唯一动作，或者只观察。",
            "> **怎么执行**：按盘前、开盘、首个60分钟、盘中、尾盘顺序，不临场改单。",
            "",
        ],
        "exports": {},
        "module_logs": [],
    }


def build_action_plan_table_node(context, node_meta=None, node_lookup=None):
    lines = [
        "**最终动作表**（只展示真正可执行对象）:",
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
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_action_plan_observation_blocks_node(context, node_meta=None, node_lookup=None):
    lines = []
    for block_title, block_lines in (
        ("**先看顺序**（优先盯最能反映主线承接的对象）:", context.get("observation_priority_lines") or []),
        ("**备用观察**（买点未触发，明日不操作）:", context.get("backup_observation_lines") or []),
    ):
        if block_lines:
            lines.append(block_title)
            lines.extend(block_lines)
            lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_action_plan_positioning_node(context, node_meta=None, node_lookup=None):
    lines = ["**明天仓位怎么放**:"]
    lines.extend(context.get("position_section_lines") or [])
    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_action_plan_schedule_node(context, node_meta=None, node_lookup=None):
    lines = ["**明日执行时间表**:", ""]
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
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_action_plan_alerts_node(context, node_meta=None, node_lookup=None):
    alert_rows = context.get("alert_rows") or []
    if not alert_rows:
        return {"lines": [], "exports": {}, "module_logs": []}

    lines = ["**⚠️ 异动预警**:", "| 股票 | 偏离天数 | 触发条件 | 实际涨幅 | 状态 |", "|------|----------|----------|----------|------|"]
    for row in alert_rows:
        lines.append(
            f"| {row.get('name', '-')}({row.get('code', '-')}) | {row.get('deviation_days', 0)}天 | "
            f"{row.get('trigger_info', '-')} | {row.get('actual_change_str', '-')} | {row.get('trigger_status', '-')} |"
        )
    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}
