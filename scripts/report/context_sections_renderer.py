from report.context_sections_node_registry import build_context_tail_node_specs
from report.context_sections_node_runtime import run_context_tail_nodes
from report.mainline_turnover_summary_support import (
    normalize_display_text_by_tag_pool,
    resolve_display_mainline_name,
    resolve_mainline_attack_evidence_summary,
)
from report.surface_wording import sanitize_user_visible_text


def render_mainline_discipline_section(mainline_name):
    mainline_name = str(mainline_name or "").strip()
    if not mainline_name:
        return []
    return [
        "#### 💡 主线执行纪律",
        f"> **主线**: {mainline_name}",
        "",
        "**只做什么，不做什么？**",
        "1. **只做主线**: 资金聚焦哪里，就只在那条线里找机会。",
        "2. **不做边缘**: 主线没确认前，B/C方向一律不抢。",
        "3. **只要确定性**: 有板块效应支撑的方向才给执行资格。",
        "",
        f"**今日纪律**: 认准'{mainline_name}'，就在'{mainline_name}'里找机会，绝不被'相关概念'分散火力！",
        "",
    ]


def render_supplementary_perspective_section(perspective_text):
    perspective_text = str(perspective_text or "").strip()
    if not perspective_text:
        return []
    lines = [
        "## 十三点五、补充观察",
        "> *以下只做补充观察，不单独给执行资格。*",
        "",
    ]
    lines.extend(perspective_text.split("\n"))
    lines.append("")
    return lines


def render_ai_market_insight_section(context):
    context = context or {}
    attack_summary = resolve_mainline_attack_evidence_summary(context)
    mainline_text = context.get("mainline_text", "暂无明确主线")
    focus_text = context.get("focus_text", "市场整体持续性，量能变化，板块轮动")
    flow_direction = normalize_display_text_by_tag_pool(context.get("flow_direction", "-"), context)
    if attack_summary and attack_summary.get("attack_state") != "confirmed_attack":
        mainline_text = "暂无确认主攻线"
        focus_text = attack_summary.get("confirmation_evidence") or "先看是否有单一方向胜出"
    else:
        display_mainline = resolve_display_mainline_name(context, fallback=mainline_text)
        if display_mainline:
            if mainline_text and mainline_text in focus_text:
                focus_text = focus_text.replace(mainline_text, display_mainline)
            mainline_text = display_mainline
    dt_count = context.get("dt_count")
    if context.get("dt_count_available") is False or dt_count is None:
        dt_count_text = "待确认"
    else:
        try:
            dt_count_text = f"{int(float(dt_count))}只"
        except (TypeError, ValueError):
            dt_count_text = "待确认"
    return [
        "## 十四、市场快照",
        f"- **核心特征**: {context.get('market_trend', '未知')}，涨停{int(context.get('zt_count', 0) or 0)}只，跌停{dt_count_text}",
        f"- **能量状态**: {context.get('energy_state', '未知')} - {flow_direction}",
        f"- **资金主线**: {mainline_text}",
        f"- **风险点**: {context.get('risk_text', '暂无明确风险')}",
        f"- **关注重点**: {focus_text}",
        "",
    ]


def _build_mainline_discipline_node(context, node_meta=None, node_lookup=None):
    return {"lines": render_mainline_discipline_section(context.get("mainline_name", "")), "exports": {}, "module_logs": []}


def _build_supplementary_perspective_node(context, node_meta=None, node_lookup=None):
    return {"lines": render_supplementary_perspective_section(context.get("supplementary_perspective", "")), "exports": {}, "module_logs": []}


def _build_market_insight_node(context, node_meta=None, node_lookup=None):
    return {"lines": render_ai_market_insight_section(context.get("market_insight", {}) or {}), "exports": {}, "module_logs": []}


CONTEXT_TAIL_NODE_BUILDERS = {
    "mainline_discipline": _build_mainline_discipline_node,
    "supplementary_perspective": _build_supplementary_perspective_node,
    "market_insight": _build_market_insight_node,
}


def build_context_tail_sections_result(context):
    context = context or {}
    node_specs = build_context_tail_node_specs(
        CONTEXT_TAIL_NODE_BUILDERS,
        enabled_node_keys=context.get("enabled_node_keys"),
    )
    return run_context_tail_nodes(node_specs, context)


def render_context_tail_sections(context):
    return sanitize_user_visible_text(build_context_tail_sections_result(context).get("lines", []))
