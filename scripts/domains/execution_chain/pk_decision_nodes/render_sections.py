from domains.execution_chain.pk_decision_nodes.candidate_surface_filter import candidate_can_be_current_observation_target


def _candidate_key(candidate):
    candidate = candidate or {}
    return str(candidate.get("code") or candidate.get("stock_code") or candidate.get("代码") or candidate.get("name") or candidate.get("名称") or "").strip()


def _position_pct(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _candidate_with_workflow_identity(candidate):
    candidate = candidate if isinstance(candidate, dict) else {}
    stock = candidate.get("stock") if isinstance(candidate.get("stock"), dict) else candidate
    payload = dict(stock or {})
    for key, value in candidate.items():
        if key == "stock":
            continue
        if payload.get(key) in (None, "") and value not in (None, ""):
            payload[key] = value
    return payload


def _selection_workflow_from_context(context):
    sources = [context]
    if isinstance(context, dict):
        sources.extend([context.get("market_research_snapshot"), context.get("execution_stage_context")])
    for source in sources:
        if not isinstance(source, dict):
            continue
        workflow = source.get("selection_workflow")
        if isinstance(workflow, dict) and workflow.get("schema_version") == "selection_workflow.v1":
            return workflow
    return {}


def _selection_workflow_front_observation_target(workflow):
    workflow = workflow if isinstance(workflow, dict) else {}
    for candidate in workflow.get("candidate_pool", []) or []:
        if not isinstance(candidate, dict):
            continue
        if candidate.get("front_observation_qualified") is not True:
            continue
        payload = _candidate_with_workflow_identity(candidate)
        if candidate_can_be_current_observation_target(payload):
            return payload
    return {}


def _selection_workflow_final_empty_without_watch_target(context):
    workflow = _selection_workflow_from_context(context)
    if not workflow:
        return False
    final = workflow.get("final") if isinstance(workflow.get("final"), dict) else {}
    if "final" not in workflow:
        return False
    execution_object = final.get("execution_object") if isinstance(final.get("execution_object"), dict) else {}
    if _position_pct(final.get("position_pct")) > 0 and _candidate_key(execution_object):
        return False
    return True


def _final_resolution_waits_without_watch_target(context):
    resolution = (context or {}).get("final_target_resolution")
    if not isinstance(resolution, dict):
        return False
    decision = resolution.get("capital_priority_decision") if isinstance(resolution.get("capital_priority_decision"), dict) else {}
    if str(decision.get("capital_priority") or "").strip() != "wait":
        return False
    return not candidate_can_be_current_observation_target(resolution.get("watch_target"))


def build_pk_decision_render_sections_node(context, node_meta=None, node_lookup=None):
    lines = []
    final_wait_without_target = (
        _final_resolution_waits_without_watch_target(context)
        or _selection_workflow_final_empty_without_watch_target(context)
    )
    pk_context = {
        "decision_stack_order_text": context.get("decision_stack_order_text"),
        "scored_executable_stocks": context.get("scored_executable_stocks", []),
        "pk_candidates": context.get("pk_candidates", []),
        "stage_label": context.get("stage_label", "Step 5"),
        "stage_title": context.get("stage_title", "PK决胜局（期望值模型）"),
        "trade_gate_open": context.get("trade_gate_open", False),
        "position_level": context.get("position_level", ""),
        "position_decision": context.get("position_decision"),
        "pending_lines": context.get("pending_lines", []),
        "observation_lines": [] if final_wait_without_target else context.get("observation_lines", []),
        "conclusion_lines": [
            "**结论**:",
            "- **明天没有可买对象**: 明日不产生买入动作",
            "- **明天先怎么观察**: 空仓观望",
            "",
        ] if final_wait_without_target else context.get("conclusion_lines", []),
    }
    action_context = {
        "section_title": "明日操作计划",
        "action_rows": [] if final_wait_without_target else context.get("action_rows", []),
        "observation_priority_lines": [] if final_wait_without_target else context.get("observation_priority_lines", []),
        "backup_observation_lines": [] if final_wait_without_target else context.get("backup_observation_lines", []),
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
        "final_target_resolution": context.get("final_target_resolution"),
        "selection_workflow": context.get("selection_workflow"),
        "position_decision": context.get("position_decision"),
        "sniper_target_derivation": context.get("sniper_target_derivation"),
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
