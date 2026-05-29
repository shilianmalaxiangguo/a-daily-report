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
        "candidate_quality_panel_fields": context.get("candidate_quality_panel_fields"),
        "candidate_quality_contracts": context.get("candidate_quality_contracts"),
        "candidate_quality_samples": context.get("candidate_quality_samples", []),
        "render_candidate_trace_tables": context.get("render_candidate_trace_tables", True),
        "candidate_trace_eliminated_items": context.get("candidate_trace_eliminated_items", []),
        "candidate_trace_eliminated_summary": context.get("candidate_trace_eliminated_summary"),
        "enabled_node_keys": context.get("action_plan_enabled_node_keys"),
    }
    existing_traces = context.get("candidate_traces")
    if existing_traces:
        action_context["candidate_traces"] = existing_traces
    lines.extend(context["render_pk_decision_section"](pk_context))
    action_exports = {}
    action_logs = []
    render_action_plan_result = context.get("render_action_plan_result")
    if render_action_plan_result:
        action_result = render_action_plan_result(action_context) or {}
        lines.extend(action_result.get("lines") or [])
        action_result_context = dict(action_result.get("context") or {})
        for export_key in ("candidate_traces", "candidate_trace_eliminated_summary"):
            if export_key in action_result_context:
                action_exports[export_key] = action_result_context.get(export_key)
        action_logs.extend(action_result.get("module_logs") or [])
    else:
        lines.extend(context["render_action_plan_section"](action_context))
    lines.append("")
    return {"lines": lines, "exports": action_exports, "module_logs": action_logs}
