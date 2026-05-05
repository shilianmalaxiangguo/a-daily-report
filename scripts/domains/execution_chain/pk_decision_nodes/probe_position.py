from selection.position_sizing_runtime import with_single_focus_counts


def build_pk_decision_probe_position_node(context, node_meta=None, node_lookup=None):
    target_date = context.get("target_date", "")
    final_gate = with_single_focus_counts(
        context.get("final_gate", {}) or {},
        focus_group=context.get("focus_group", []) or [],
        keep_group=context.get("keep_group", []) or [],
    )
    mainline_name = str(context.get("mainline_name", "") or "").strip()
    market_research_snapshot = context.get("market_research_snapshot", {}) or {}
    abnormal_watch_pool_all = context.get("abnormal_watch_pool_all", []) or []

    safe_float = context["safe_float"]
    build_abnormal_probe_group = context["build_abnormal_probe_group"]
    build_special_probe_verdict = context["build_special_probe_verdict"]
    build_position_sizing_decision = context["build_position_sizing_decision"]

    best_stock = context.get("best_stock")
    watch_anchor = context.get("watch_anchor")
    watch_anchor_type = context.get("watch_anchor_type", "")

    abnormal_probe_group = build_abnormal_probe_group(
        market_research_snapshot.get("style_switch", {}) or {},
        abnormal_watch_pool=abnormal_watch_pool_all,
        mainline_name=mainline_name,
        watch_anchor=watch_anchor,
    )
    special_probe_verdict = build_special_probe_verdict(
        abnormal_probe_group=abnormal_probe_group,
        watch_anchor=watch_anchor,
        watch_anchor_type=watch_anchor_type,
        mainline_name=mainline_name,
        target_date=target_date,
    )
    position_decision = build_position_sizing_decision(
        final_gate=final_gate,
        state_machine_snapshot=market_research_snapshot.get("state_machine", {}) or {},
        best_stock=best_stock,
        watch_anchor=watch_anchor,
        watch_anchor_type=watch_anchor_type,
        mainline_name=mainline_name,
        target_date=target_date,
        special_probe_verdict=special_probe_verdict,
        monthly_context=context.get("monthly_context", {}) or {},
    )
    selected_position_candidate = best_stock or watch_anchor
    if selected_position_candidate and position_decision.get("target_position_pct", 0) > 0:
        selected_position_candidate["position_pct"] = int(safe_float(position_decision.get("target_position_pct", 0)))
    if selected_position_candidate:
        selected_position_candidate["candidate_feedback_ready"] = bool(position_decision.get("candidate_feedback_ready"))

    return {
        "lines": [],
        "exports": {
            "abnormal_probe_group": abnormal_probe_group,
            "special_probe_verdict": special_probe_verdict,
            "position_decision": position_decision,
            "selected_position_candidate": selected_position_candidate,
        },
        "module_logs": [],
    }
