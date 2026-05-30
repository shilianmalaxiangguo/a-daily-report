from report.market_research_snapshot_node_registry import build_market_research_snapshot_node_specs
from report.market_research_snapshot_node_runtime import run_market_research_snapshot_nodes
from report.market_capacity_evolution_nodes import build_market_research_snapshot_market_capacity_evolution_node
from report.sector_internal_analysis_nodes import build_market_research_snapshot_sector_internal_analysis_node
from report.market_research_snapshot_nodes import (
    build_market_research_snapshot_abnormal_projection_node,
    build_market_research_snapshot_dialectical_decision_node,
    build_market_research_snapshot_follow_verdict_node,
    build_market_research_snapshot_footer_node,
    build_market_research_snapshot_header_node,
    build_market_research_snapshot_leader_memory_node,
    build_market_research_snapshot_lhb_capital_intent_node,
    build_market_research_snapshot_mainline_capacity_regime_node,
    build_market_research_snapshot_mainline_focus_node,
    build_market_research_snapshot_cycle_calendar_node,
    build_market_research_snapshot_cycle_interpretation_node,
    build_market_research_snapshot_pivot_mainline_interpretation_node,
    build_market_research_snapshot_mainline_turnover_node,
    build_market_research_snapshot_narrative_node,
    build_market_research_snapshot_risk_preference_node,
    build_market_research_snapshot_rotation_node,
    build_market_research_snapshot_state_summary_node,
    build_market_research_snapshot_style_background_node,
    build_market_research_snapshot_style_note_node,
    build_market_research_snapshot_table_header_node,
    build_market_research_snapshot_trend_density_node,
    derive_market_research_cycle_layer,
)
from report.step0_follow_node_registry import build_step0_follow_node_specs
from report.step0_follow_node_runtime import run_step0_follow_nodes
from report.step0_follow_nodes import (
    build_step0_follow_abnormal_projection_node,
    build_step0_follow_conclusion_node,
    build_step0_follow_footer_node,
    build_step0_follow_mainline_focus_node,
    build_step0_follow_reminder_node,
    build_step0_follow_risk_preference_node,
    build_step0_follow_state_summary_node,
    build_step0_follow_style_background_node,
    build_step0_follow_table_header_node,
    build_step0_follow_verdict_node,
)


MARKET_RESEARCH_SNAPSHOT_NODE_BUILDERS = {
    "header": build_market_research_snapshot_header_node,
    "cycle_calendar": build_market_research_snapshot_cycle_calendar_node,
    "cycle_interpretation": build_market_research_snapshot_cycle_interpretation_node,
    "pivot_mainline_interpretation": build_market_research_snapshot_pivot_mainline_interpretation_node,
    "mainline_capacity_regime": build_market_research_snapshot_mainline_capacity_regime_node,
    "market_capacity_evolution": build_market_research_snapshot_market_capacity_evolution_node,
    "sector_internal_analysis": build_market_research_snapshot_sector_internal_analysis_node,
    "table_header": build_market_research_snapshot_table_header_node,
    "risk_preference": build_market_research_snapshot_risk_preference_node,
    "mainline_focus": build_market_research_snapshot_mainline_focus_node,
    "mainline_turnover": build_market_research_snapshot_mainline_turnover_node,
    "lhb_capital_intent": build_market_research_snapshot_lhb_capital_intent_node,
    "rotation": build_market_research_snapshot_rotation_node,
    "narrative": build_market_research_snapshot_narrative_node,
    "style_background": build_market_research_snapshot_style_background_node,
    "abnormal_projection": build_market_research_snapshot_abnormal_projection_node,
    "follow_verdict": build_market_research_snapshot_follow_verdict_node,
    "state_summary": build_market_research_snapshot_state_summary_node,
    "leader_memory": build_market_research_snapshot_leader_memory_node,
    "trend_density": build_market_research_snapshot_trend_density_node,
    "style_note": build_market_research_snapshot_style_note_node,
    "dialectical_decision": build_market_research_snapshot_dialectical_decision_node,
    "footer": build_market_research_snapshot_footer_node,
}

STEP0_FOLLOW_NODE_BUILDERS = {
    "verdict": build_step0_follow_verdict_node,
    "table_header": build_step0_follow_table_header_node,
    "risk_preference": build_step0_follow_risk_preference_node,
    "style_background": build_step0_follow_style_background_node,
    "mainline_focus": build_step0_follow_mainline_focus_node,
    "abnormal_projection": build_step0_follow_abnormal_projection_node,
    "state_summary": build_step0_follow_state_summary_node,
    "conclusion": build_step0_follow_conclusion_node,
    "reminder": build_step0_follow_reminder_node,
    "footer": build_step0_follow_footer_node,
}


from report.surface_wording import sanitize_user_visible_text


GEM_BREATHING_FOCUS_LINE = "> **只看什么**：波动收敛、量价温和放大、右侧确认。"


def render_gem_breathing_step2_section(context):
    context = context or {}
    gem_observation_stocks = context.get("gem_observation_stocks") or []
    filtered_out_gem_candidates = context.get("filtered_out_gem_candidates") or []
    if not gem_observation_stocks and not filtered_out_gem_candidates:
        return []
    display_mvp_mode = bool(context.get("display_mvp_mode"))
    preview = gem_observation_stocks[:2] if display_mvp_mode else gem_observation_stocks[:4]
    lines = [
        "> **主线侧翼弹性层**：若主板强锚仍在，创业板20cm只作为主线白银弹性观察，不单列成独立战场。",
        "> **观察纪律**：只先进观察池，先看波动收敛、量价温和放大和右侧确认；确认前只观察不执行。",
    ]
    if filtered_out_gem_candidates:
        filtered_preview = filtered_out_gem_candidates[:2] if display_mvp_mode else filtered_out_gem_candidates[:4]
        filtered_text = "；".join(
            f"{item.get('name', '-')}({item.get('code', '-')})/{item.get('sector', '-')}：{item.get('filtered_reason', '-') or '-'}"
            for item in filtered_preview
        )
        lines.append(f"> **主线过滤提示**：当前有20cm预启动样本，但因非主线被过滤：{filtered_text}")
    if not preview:
        lines.append("")
        return lines
    lines.extend(
        [
            "| 序号 | 股票 | 代码 | 板块 | 预启动层级 | 当前线索 | 预判强度 | 明日原则 |",
            "|------|------|------|------|------------|----------|----------|----------|",
        ]
    )
    for i, item in enumerate(preview, 1):
        lines.append(
            f"| {i} | {item.get('name', '-')} | {item.get('code', '-')} | {item.get('sector', '-')} | "
            f"{item.get('tier', '-') or '-'} | {sanitize_user_visible_text(item.get('abnormal_summary', item.get('note', '-')) or '-')} | "
            f"{item.get('tomorrow_strength', 0)}分 | 先看右侧确认和09:50-10:10窗口，不满足继续观察 |"
        )
    lines.append("")
    return lines


def render_gem_breathing_pool_section(context):
    context = context or {}
    gem_observation_stocks = context.get("gem_observation_stocks") or []
    filtered_out_gem_candidates = context.get("filtered_out_gem_candidates") or []
    if not gem_observation_stocks and not filtered_out_gem_candidates:
        return []
    lines = [
        "#### Step 3.5 - 创业板20cm预启动观察池",
        "> **先看结论**：创业板20cm样本只保留观察权，不单列成独立战场。",
        GEM_BREATHING_FOCUS_LINE,
    ]
    if filtered_out_gem_candidates:
        filtered_text = "；".join(
            f"{item.get('name', '-')}({item.get('code', '-')})/{item.get('sector', '-')}：{item.get('filtered_reason', '-') or '-'}"
            for item in filtered_out_gem_candidates[:4]
        )
        lines.append(f"> **主线过滤提示**：当前有20cm预启动样本，但因非主线被过滤：{filtered_text}")
    lines.append("")
    if not gem_observation_stocks:
        return lines
    lines.extend(["| 股票 | 层级 | 预启动说明 | 观察动作 |", "|------|------|------------|----------|"])
    for item in gem_observation_stocks:
        lines.append(
            f"| {item.get('name', '-')}({item.get('code', '-')}) | {item.get('tier', '-') or item.get('core_level', '-')} | "
            f"{sanitize_user_visible_text(item.get('note', item.get('abnormal_summary', '-')))} | {sanitize_user_visible_text(item.get('watch_anchor_note', item.get('tmr_forecast', '-')))} |"
        )
    lines.append("")
    return lines


def render_market_research_snapshot_section(context):
    context = _with_fresh_cycle_layer(context or {})
    compact = bool(context.get("compact"))
    if context.get("enabled_node_keys") and "lhb_capital_intent" in context.get("enabled_node_keys"):
        builders = dict(MARKET_RESEARCH_SNAPSHOT_NODE_BUILDERS)
        builder = builders.pop("lhb_capital_intent")
        lines = []
        if "header" in context.get("enabled_node_keys"):
            lines.extend(build_market_research_snapshot_header_node(context).get("lines", []))
        lines.extend(builder(context).get("lines", []))
        return lines
    node_specs = build_market_research_snapshot_node_specs(
        MARKET_RESEARCH_SNAPSHOT_NODE_BUILDERS,
        enabled_node_keys=context.get("enabled_node_keys"),
        compact=compact,
    )
    result = run_market_research_snapshot_nodes(node_specs, context)
    if not context.get("enabled_node_keys") and (context.get("lhb_capital_status") or context.get("capital_conclusion")):
        result["lines"].extend(build_market_research_snapshot_lhb_capital_intent_node(context).get("lines", []))
    return result["lines"]


def _with_fresh_cycle_layer(context):
    context = dict(context or {})
    has_refresh_source = bool(
        context.get("current_mainline_history_record")
        or context.get("recent_mainline_history")
        or context.get("pivot_mainline_history")
    )
    if not has_refresh_source:
        return context
    cycle_layer = derive_market_research_cycle_layer(context, context.get("state_machine") or {})
    for key, value in cycle_layer.items():
        if value:
            context[key] = value
    return context


def render_step0_follow_section(context):
    context = context or {}
    compact = bool(context.get("compact"))
    node_specs = build_step0_follow_node_specs(
        STEP0_FOLLOW_NODE_BUILDERS,
        enabled_node_keys=context.get("enabled_node_keys"),
        compact=compact,
    )
    result = run_step0_follow_nodes(node_specs, context)
    return result["lines"]
