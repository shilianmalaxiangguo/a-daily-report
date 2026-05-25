from report.candidate_quality_renderer import COMPACT_CANDIDATE_TABLE_FIELDS, render_candidate_quality_section
from selection.candidate_quality_contracts import (
    build_daily_quality_decision_panel,
    evaluate_candidate_quality_sample_contract,
)


def build_action_plan_overview_node(context, node_meta=None, node_lookup=None):
    section_title = str(context.get("section_title", "") or "明日操作计划").strip() or "明日操作计划"
    return {
        "lines": [
            f"#### {section_title}",
            "> **先看结论**：明天只执行唯一动作，或者只观察。",
            "> **怎么执行**：按盘前、竞价表态、开盘前几分钟、结构确认、盘中、尾盘顺序，不临场改单。",
            "",
        ],
        "exports": {},
        "module_logs": [],
    }


def build_action_plan_candidate_quality_node(context, node_meta=None, node_lookup=None):
    panel = context.get("candidate_quality_panel")
    contracts = context.get("candidate_quality_contracts") or []
    enabled_node_keys = set(context.get("enabled_node_keys") or [])
    heading_level = 5 if not enabled_node_keys or "overview" in enabled_node_keys else 2
    if not panel and context.get("candidate_quality_panel_fields"):
        panel = build_daily_quality_decision_panel(**context.get("candidate_quality_panel_fields"))
    if not contracts and context.get("candidate_quality_samples"):
        contracts = [
            evaluate_candidate_quality_sample_contract(candidate)
            for candidate in context.get("candidate_quality_samples")
        ]
    if not panel:
        return {"lines": [], "exports": {}, "module_logs": []}
    return {
        "lines": render_candidate_quality_section(
            panel,
            contracts,
            heading_level=heading_level,
            table_fields=COMPACT_CANDIDATE_TABLE_FIELDS,
        ).splitlines(),
        "exports": {},
        "module_logs": [],
    }


def build_action_plan_table_node(context, node_meta=None, node_lookup=None):
    lines = [
        "**最终动作表**（只展示真正具备参与资格的对象）:",
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
        ("**竞价表态与开盘买卖窗口（09:20-09:35，买卖只在09:30-09:35）**:", context.get("opening_lines") or []),
        ("**结构确认窗口（09:35-10:30）**:", context.get("first_hour_lines") or []),
        ("**盘中执行（10:30-14:30）**:", context.get("intraday_lines") or []),
        ("**尾盘买卖窗口（14:30-14:55）**:", context.get("closing_lines") or []),
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
