from report.calendar_section_node_registry import build_calendar_section_node_specs
from report.calendar_section_node_runtime import run_calendar_section_nodes


def _has_calendar_events(context):
    if "calendar_events_present" in context:
        return bool(context.get("calendar_events_present"))
    return bool(
        (context.get("calendar_analysis") or [])
        or (context.get("top_directions") or [])
        or (context.get("unique_sectors") or [])
        or (context.get("bullish_events") or [])
    )


def build_calendar_section_header_node(context, node_meta=None, node_lookup=None):
    return {"lines": ["## 二、预期日历（AI智能分析板块）", ""], "exports": {}, "module_logs": []}


def build_calendar_section_top_directions_node(context, node_meta=None, node_lookup=None):
    top_directions = context.get("top_directions") or []
    if not top_directions or not _has_calendar_events(context):
        return {"lines": [], "exports": {}, "module_logs": []}
    lines = ["### 近期产业链热点分布", "| 产业链方向 | 事件数量 | 热度 |", "|-----------|---------|------|"]
    for direction, count in top_directions:
        heat = "🔥" * min(count, 5)
        lines.append(f"| {direction} | {count}个事件 | {heat} |")
    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_calendar_section_event_table_node(context, node_meta=None, node_lookup=None):
    calendar_analysis = context.get("calendar_analysis") or []
    if not calendar_analysis or not _has_calendar_events(context):
        return {"lines": [], "exports": {}, "module_logs": []}
    lines = [
        "### 重点事件明细",
        "| 日期 | 事件 | 重要度 | 产业链方向 | 预期 | 博弈方向 |",
        "|------|------|--------|-----------|------|---------|",
    ]
    for item in calendar_analysis:
        date = item.get("date", "")
        title = item.get("title", "")
        star = item.get("star", "")
        ai = item.get("ai_analysis", {}) or {}
        expectation_icon = {"利好": "📈", "利空": "📉", "中性": "➖"}.get(ai.get("expectation"), "➖")
        if any(keyword in title for keyword in ["风险", "警告", "谨慎", "监管"]):
            direction = "回避"
        elif ai.get("expectation") == "利好":
            direction = "事件观察"
        elif ai.get("expectation") == "利空":
            direction = "回避/对冲"
        else:
            direction = "观望"
        lines.append(f"| {date} | {title} | {star} | {ai.get('main_direction', '')} | {expectation_icon}{ai.get('expectation', '')} | {direction} |")
    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_calendar_section_insight_summary_node(context, node_meta=None, node_lookup=None):
    if not _has_calendar_events(context):
        return {"lines": [], "exports": {}, "module_logs": []}
    lines = ["### AI板块关联分析"]
    unique_sectors = context.get("unique_sectors") or []
    bullish_events = context.get("bullish_events") or []
    chain_analysis_insights = context.get("chain_analysis_insights", "")
    if unique_sectors:
        lines.append(f"**涉及细分板块**：{'、'.join(unique_sectors)}")
        lines.append("")
    if bullish_events:
        lines.append(f"**利好预期方向**：{len(bullish_events)}个事件")
        for item in bullish_events[:3]:
            ai = item.get("ai_analysis", {}) or {}
            lines.append(f"- {ai.get('main_direction', '')}: {str(item.get('title', ''))[:30]}...")
        lines.append("")
    if chain_analysis_insights:
        lines.append("**产业链洞察**：")
        lines.append(f"> {chain_analysis_insights}")
        lines.append("")
    if lines == ["### AI板块关联分析"]:
        return {"lines": [], "exports": {}, "module_logs": []}
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_calendar_section_empty_state_node(context, node_meta=None, node_lookup=None):
    if _has_calendar_events(context):
        return {"lines": [], "exports": {}, "module_logs": []}
    return {"lines": ["| - | 暂无重要事件 | - | - | - | - |"], "exports": {}, "module_logs": []}


def build_calendar_section_footer_node(context, node_meta=None, node_lookup=None):
    return {"lines": [""], "exports": {}, "module_logs": []}


CALENDAR_SECTION_NODE_BUILDERS = {
    "header": build_calendar_section_header_node,
    "top_directions": build_calendar_section_top_directions_node,
    "event_table": build_calendar_section_event_table_node,
    "insight_summary": build_calendar_section_insight_summary_node,
    "empty_state": build_calendar_section_empty_state_node,
    "footer": build_calendar_section_footer_node,
}


def render_calendar_section(context):
    context = context or {}
    node_specs = build_calendar_section_node_specs(
        CALENDAR_SECTION_NODE_BUILDERS,
        enabled_node_keys=context.get("enabled_node_keys"),
    )
    result = run_calendar_section_nodes(node_specs, context)
    return result["lines"]
