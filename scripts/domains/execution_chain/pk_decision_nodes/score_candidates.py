def build_pk_decision_score_candidates_node(context, node_meta=None, node_lookup=None):
    target_date = context.get("target_date", "")
    run_mode = context.get("run_mode")
    final_gate = context.get("final_gate", {}) or {}
    mainline_name = str(context.get("mainline_name", "") or "").strip()
    market_research_snapshot = context.get("market_research_snapshot", {}) or {}
    conviction_codes = context.get("conviction_codes", set()) or set()
    leader_memory_codes = context.get("leader_memory_codes", set()) or set()
    executable_stocks = context.get("executable_stocks", []) or []
    waiting_stocks = context.get("waiting_stocks", []) or []

    build_strategy_ev_calibration = context["build_strategy_ev_calibration"]
    score_execution_candidate = context["score_execution_candidate"]
    score_candidate_decision_stack = context["score_candidate_decision_stack"]
    sort_decision_stack_candidates = context["sort_decision_stack_candidates"]
    sort_watch_anchor_candidates = context["sort_watch_anchor_candidates"]

    trade_gate_open = final_gate.get("can_new_entry", False)
    ev_calibration = build_strategy_ev_calibration(target_date, ledger_mode=run_mode)
    scored_executable_stocks = [
        score_candidate_decision_stack(
            score_execution_candidate(stock, ev_calibration),
            final_gate=final_gate,
            mainline_name=mainline_name,
            conviction_codes=conviction_codes,
            leader_memory_codes=leader_memory_codes,
            state_machine_snapshot=market_research_snapshot.get("state_machine", {}),
            target_date=target_date,
        )
        for stock in executable_stocks
    ]
    scored_executable_stocks = sort_decision_stack_candidates(scored_executable_stocks)

    scored_waiting_stocks = [
        score_candidate_decision_stack(
            score_execution_candidate(stock, ev_calibration),
            final_gate=final_gate,
            mainline_name=mainline_name,
            conviction_codes=conviction_codes,
            leader_memory_codes=leader_memory_codes,
            state_machine_snapshot=market_research_snapshot.get("state_machine", {}),
            target_date=target_date,
        )
        for stock in waiting_stocks
    ]
    pending_candidates = (
        sort_watch_anchor_candidates(
            list(scored_waiting_stocks),
            mainline_name=mainline_name,
            state_machine_snapshot=market_research_snapshot.get("state_machine", {}),
        )
        if scored_waiting_stocks
        else []
    )

    pk_candidates = scored_executable_stocks if trade_gate_open else []
    best_stock = pk_candidates[0] if pk_candidates else None
    runner_up = pk_candidates[1] if len(pk_candidates) >= 2 else None

    return {
        "lines": [],
        "exports": {
            "trade_gate_open": trade_gate_open,
            "ev_calibration": ev_calibration,
            "scored_executable_stocks": scored_executable_stocks,
            "scored_waiting_stocks": scored_waiting_stocks,
            "pending_candidates": pending_candidates,
            "pk_candidates": pk_candidates,
            "best_stock": best_stock,
            "runner_up": runner_up,
        },
        "module_logs": [],
    }
