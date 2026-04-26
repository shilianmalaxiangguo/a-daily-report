def build_pk_decision_front_texts_node(context, node_meta=None, node_lookup=None):
    target_date = context.get("target_date", "")
    position_level = str(context.get("position_level", "") or "").strip()
    position_reason = str(context.get("position_reason", "") or "").strip()
    display_mvp_mode = bool(context.get("display_mvp_mode", False))
    high_board_count = context.get("high_board_count", 0)
    final_gate = context.get("final_gate", {}) or {}
    mainline_name = str(context.get("mainline_name", "") or "").strip()
    watchlist = context.get("watchlist", []) or []
    core_stocks = context.get("core_stocks", []) or []
    abnormal_watch_pool = context.get("abnormal_watch_pool", []) or []
    market_research_bundle = context.get("market_research_bundle", {}) or {}
    market_research_snapshot = context.get("market_research_snapshot", {}) or {}
    focus_group = context.get("focus_group", []) or []
    keep_group = context.get("keep_group", []) or []
    delete_group = context.get("delete_group", []) or []
    step2_bundle = context.get("step2_bundle", {}) or {}

    build_front_structure_layer_text = context["build_front_structure_layer_text"]
    build_front_follow_action_text = context["build_front_follow_action_text"]
    build_special_probe_focus_text = context["build_special_probe_focus_text"]
    build_philosophy_constraint_text = context["build_philosophy_constraint_text"]
    render_core_mvp_digest = context["render_core_mvp_digest"]
    render_mvp_focus_summary = context["render_mvp_focus_summary"]

    best_stock = context.get("best_stock")
    watch_anchor = context.get("watch_anchor")
    watch_anchor_type = context.get("watch_anchor_type", "")
    special_probe_verdict = context.get("special_probe_verdict", {})
    abnormal_probe_group = context.get("abnormal_probe_group", {})

    front_structure_layer_text = build_front_structure_layer_text(
        final_gate=final_gate,
        focus_group=focus_group,
        keep_group=keep_group,
        delete_group=delete_group,
        best_stock=best_stock,
        watch_anchor=watch_anchor,
        watch_anchor_type=watch_anchor_type,
        position_level=position_level,
        state_machine_snapshot=market_research_snapshot.get("state_machine", {}),
        target_date=target_date,
        special_probe_verdict=special_probe_verdict,
    )
    front_follow_action_text = build_front_follow_action_text(
        final_gate=final_gate,
        best_stock=best_stock,
        watch_anchor=watch_anchor,
        watch_anchor_type=watch_anchor_type,
        fallback_text=final_gate.get("final_action", context.get("step0_action", "")),
        focus_group=focus_group,
        keep_group=keep_group,
        delete_group=delete_group,
        position_level=position_level,
        state_machine_snapshot=market_research_snapshot.get("state_machine", {}),
        target_date=target_date,
        special_probe_verdict=special_probe_verdict,
    )
    special_probe_text = build_special_probe_focus_text(
        abnormal_probe_group=abnormal_probe_group,
        watch_anchor=watch_anchor,
        watch_anchor_type=watch_anchor_type,
        mainline_name=mainline_name,
        target_date=target_date,
    )
    philosophy_constraint_text = build_philosophy_constraint_text(
        final_gate=final_gate,
        best_stock=best_stock,
        watch_anchor=watch_anchor,
        watch_anchor_type=watch_anchor_type,
        state_machine_snapshot=market_research_snapshot.get("state_machine", {}),
    )

    core_mvp_digest_lines = render_core_mvp_digest(
        market_research_snapshot,
        final_gate=final_gate,
        position_level=position_level,
        position_reason=position_reason,
        exit_analysis=context.get("exit_analysis", {}) or {},
        execution_framework_text=context["get_execution_framework_text"](),
        high_board_count=high_board_count,
        structure_layer_text=front_structure_layer_text,
        front_follow_action_text=front_follow_action_text,
        special_probe_text=special_probe_text,
        philosophy_constraint_text=philosophy_constraint_text,
        best_stock=best_stock,
        watch_anchor=watch_anchor,
        watch_anchor_type=watch_anchor_type,
        target_date=target_date,
        compact=display_mvp_mode,
    )
    mvp_focus_summary_lines = render_mvp_focus_summary(
        market_research_snapshot,
        watchlist=watchlist,
        abnormal_watch_pool=abnormal_watch_pool,
        leader_memory_bank=context.get("leader_memory_bank", []) or [],
        core_stocks=core_stocks,
        crossline_observation_stocks=step2_bundle.get("crossline_observation_stocks", []),
        gem_breathing_candidates=market_research_bundle.get("gem_breathing_candidates", []),
        filtered_out_gem_candidates=market_research_bundle.get("filtered_out_gem_breathing_candidates", []),
        structure_layer_text=front_structure_layer_text,
        focus_group=focus_group,
        keep_group=keep_group,
        delete_group=delete_group,
        best_stock=best_stock,
        watch_anchor=watch_anchor,
        watch_anchor_type=watch_anchor_type,
        abnormal_probe_group=abnormal_probe_group,
        final_gate=final_gate,
        position_level=position_level,
        compact=display_mvp_mode,
    )

    return {
        "lines": [],
        "exports": {
            "front_structure_layer_text": front_structure_layer_text,
            "front_follow_action_text": front_follow_action_text,
            "special_probe_text": special_probe_text,
            "philosophy_constraint_text": philosophy_constraint_text,
            "core_mvp_digest_lines": core_mvp_digest_lines,
            "mvp_focus_summary_lines": mvp_focus_summary_lines,
        },
        "module_logs": [],
    }
