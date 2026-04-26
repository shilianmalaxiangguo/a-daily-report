def build_pk_decision_render_sections_node(context, node_meta=None, node_lookup=None):
    lines = []
    pk_context = {
        "decision_stack_order_text": context.get("decision_stack_order_text"),
        "scored_executable_stocks": context.get("scored_executable_stocks", []),
        "pk_candidates": context.get("pk_candidates", []),
        "stage_label": context.get("stage_label", "Step 5"),
        "stage_title": context.get("stage_title", "PK决胜局（期望值模型）"),
        "trade_gate_open": context.get("trade_gate_open", False),
        "position_level": context.get("position_level", ""),
        "pending_lines": context.get("pending_lines", []),
        "observation_lines": context.get("observation_lines", []),
        "conclusion_lines": context.get("conclusion_lines", []),
    }
    action_context = {
        "section_title": "明日操作计划",
        "action_rows": context.get("action_rows", []),
        "observation_priority_lines": context.get("observation_priority_lines", []),
        "backup_observation_lines": context.get("backup_observation_lines", []),
        "position_section_lines": context.get("position_section_lines", []),
        "pre_market_lines": context.get("pre_market_lines", []),
        "opening_lines": context.get("opening_lines", []),
        "first_hour_lines": context.get("first_hour_lines", []),
        "intraday_lines": context.get("intraday_lines", []),
        "closing_lines": context.get("closing_lines", []),
        "alert_rows": context.get("alert_rows", []),
    }
    lines.extend(context["render_pk_decision_section"](pk_context))
    lines.extend(context["render_action_plan_section"](action_context))
    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}
