from report.final_conclusion_node_registry import build_final_conclusion_node_specs
from report.final_conclusion_node_runtime import run_final_conclusion_nodes
from report.final_conclusion_nodes import (
    build_final_conclusion_footer_node,
    build_final_conclusion_full_discipline_node,
    build_final_conclusion_full_stage_rows_node,
    build_final_conclusion_full_strategy_node,
    build_final_conclusion_focus_recap_node,
    build_final_conclusion_header_node,
    build_final_conclusion_market_outlook_node,
    build_final_conclusion_mvp_action_node,
    build_final_conclusion_mvp_discipline_node,
    build_final_conclusion_mvp_focus_node,
    build_final_conclusion_mvp_gate_node,
    build_final_conclusion_mvp_mainline_node,
    build_final_conclusion_mvp_market_node,
    build_final_conclusion_mvp_probe_node,
    build_final_conclusion_mvp_target_node,
    build_final_conclusion_risk_guard_node,
    build_final_conclusion_style_summary_node,
    build_final_conclusion_table_header_node,
)
from report.surface_wording import sanitize_user_visible_text
from report.trading_time_window_contract import normalize_trading_time_text


FINAL_CONCLUSION_NODE_BUILDERS = {
    "header": build_final_conclusion_header_node,
    "table_header": build_final_conclusion_table_header_node,
    "market_outlook": build_final_conclusion_market_outlook_node,
    "mvp_market": build_final_conclusion_mvp_market_node,
    "focus_recap": build_final_conclusion_focus_recap_node,
    "mvp_mainline": build_final_conclusion_mvp_mainline_node,
    "mvp_focus": build_final_conclusion_mvp_focus_node,
    "mvp_gate": build_final_conclusion_mvp_gate_node,
    "mvp_probe": build_final_conclusion_mvp_probe_node,
    "mvp_target": build_final_conclusion_mvp_target_node,
    "mvp_action": build_final_conclusion_mvp_action_node,
    "style_summary": build_final_conclusion_style_summary_node,
    "risk_guard": build_final_conclusion_risk_guard_node,
    "mvp_discipline": build_final_conclusion_mvp_discipline_node,
    "full_stage_rows": build_final_conclusion_full_stage_rows_node,
    "full_strategy": build_final_conclusion_full_strategy_node,
    "full_discipline": build_final_conclusion_full_discipline_node,
    "footer": build_final_conclusion_footer_node,
}


def build_legacy_final_conclusion_lines(context):
    context = context or {}
    node_specs = build_final_conclusion_node_specs(
        FINAL_CONCLUSION_NODE_BUILDERS,
        enabled_node_keys=context.get("enabled_node_keys"),
    )
    result = run_final_conclusion_nodes(node_specs, context)
    return normalize_trading_time_text(sanitize_user_visible_text(result["lines"]))
