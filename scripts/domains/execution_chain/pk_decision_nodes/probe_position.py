from selection.position_sizing_runtime import with_single_focus_counts


def _candidate_key(candidate):
    candidate = candidate or {}
    return str(candidate.get("code") or candidate.get("stock_code") or candidate.get("代码") or candidate.get("name") or candidate.get("名称") or "").strip()


def _preferred_observation_target(context):
    for key in ("front_page_selected_position_candidate", "selected_position_candidate"):
        candidate = context.get(key)
        if isinstance(candidate, dict) and _candidate_key(candidate):
            return candidate
    for candidate in context.get("extreme_conviction_list", []) or []:
        if isinstance(candidate, dict) and _candidate_key(candidate):
            return candidate
    step2_bundle = context.get("step2_bundle") if isinstance(context.get("step2_bundle"), dict) else {}
    for candidate in step2_bundle.get("extreme_conviction_list", []) or []:
        if isinstance(candidate, dict) and _candidate_key(candidate):
            return candidate
    return None


def _prioritized_observation_candidates(context):
    candidates = list(context.get("display_observation_candidates", []) or [])
    target = _preferred_observation_target(context)
    target_key = _candidate_key(target)
    if not target_key:
        return candidates
    matched = []
    remaining = []
    for candidate in candidates:
        if _candidate_key(candidate) == target_key:
            matched.append(candidate)
        else:
            remaining.append(candidate)
    if matched:
        return matched + remaining
    return [target] + remaining


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
    selected_position_candidate = best_stock or (watch_anchor if context.get("trade_gate_open") else None)
    if not selected_position_candidate:
        for candidate in _prioritized_observation_candidates(context):
            if isinstance(candidate, dict) and (candidate.get("name") or candidate.get("code")):
                selected_position_candidate = candidate
                break
    if not selected_position_candidate:
        selected_position_candidate = watch_anchor
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
