def build_pk_decision_export_stage_state_node(context, node_meta=None, node_lookup=None):
    export_keys = [
        "trade_gate_open",
        "best_stock",
        "runner_up",
        "watch_anchor",
        "watch_anchor_type",
        "abnormal_probe_group",
        "special_probe_verdict",
        "position_decision",
        "front_structure_layer_text",
        "front_follow_action_text",
        "special_probe_text",
        "philosophy_constraint_text",
        "scored_executable_stocks",
        "core_mvp_digest_lines",
        "mvp_focus_summary_lines",
        "candidate_traces",
        "candidate_trace_eliminated_summary",
    ]
    stage_exports = {key: context.get(key) for key in export_keys if key in context}
    return {"lines": [], "exports": {"stage_exports": stage_exports}, "module_logs": []}
