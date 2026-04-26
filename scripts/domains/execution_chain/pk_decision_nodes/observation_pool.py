def build_pk_decision_observation_pool_node(context, node_meta=None, node_lookup=None):
    target_date = context.get("target_date", "")
    final_gate = context.get("final_gate", {}) or {}
    mainline_name = str(context.get("mainline_name", "") or "").strip()
    market_research_snapshot = context.get("market_research_snapshot", {}) or {}
    keep_group = context.get("keep_group", []) or []
    step2_bundle = context.get("step2_bundle", {}) or {}
    conviction_codes = context.get("conviction_codes", set()) or set()
    leader_memory_codes = context.get("leader_memory_codes", set()) or set()
    abnormal_watch_pool_all = context.get("abnormal_watch_pool_all", []) or []

    safe_float = context["safe_float"]
    score_execution_candidate = context["score_execution_candidate"]
    score_candidate_decision_stack = context["score_candidate_decision_stack"]
    sort_watch_anchor_candidates = context["sort_watch_anchor_candidates"]
    get_trade_permission = context["get_trade_permission"]
    fetch_recent_price_bars = context["fetch_recent_price_bars"]
    evaluate_live_tradability = context["evaluate_live_tradability"]
    analyze_buy_signal = context.get("analyze_buy_signal")
    quant_system_available = bool(context.get("quant_system_available", False))
    build_waiting_stock_plan = context["build_waiting_stock_plan"]
    build_abnormal_watch_anchor_candidates = context["build_abnormal_watch_anchor_candidates"]

    trade_gate_open = context.get("trade_gate_open", False)
    ev_calibration = context.get("ev_calibration", {})
    scored_executable_stocks = context.get("scored_executable_stocks", []) or []
    scored_waiting_stocks = context.get("scored_waiting_stocks", []) or []
    pending_candidates = context.get("pending_candidates", []) or []

    scored_keep_watch_stocks = []
    if not trade_gate_open:
        for stock in keep_group:
            code = stock.get("code", "")
            close_price = safe_float(stock.get("close"))
            permission = get_trade_permission(
                stock,
                mainline_name=mainline_name,
                conviction_codes=conviction_codes,
                leader_memory_codes=leader_memory_codes,
                final_gate=final_gate,
                state_machine_snapshot=market_research_snapshot.get("state_machine", {}),
            )
            recent_bars = fetch_recent_price_bars(code, target_date, lookback_days=4)
            tradability_guard = evaluate_live_tradability(stock, target_date, recent_bars=recent_bars)
            signal = (
                analyze_buy_signal(code, stock.get("name", ""), close_price, safe_float(stock.get("volume")))
                if (quant_system_available and close_price > 0 and code and analyze_buy_signal)
                else None
            )
            signal_type = getattr(signal, "signal_type", "") if signal and signal.is_valid else ""
            entry_seed_price = signal.entry_price if signal and signal.is_valid else close_price
            watch_candidate = build_waiting_stock_plan(
                {
                    **stock,
                    "entry_price": entry_seed_price,
                    "condition": stock.get("tomorrow_risk") or stock.get("reason") or "继续观察",
                    "tradability_guard": tradability_guard,
                    "report_day_is_one_word": tradability_guard.get("report_day_is_one_word", False),
                },
                target_date,
                reason=stock.get("tomorrow_risk") or stock.get("reason") or "继续观察",
                signal_type=signal_type,
                recent_bars=[],
            )
            watch_candidate.update(
                {
                    "permission_label": permission.get("permission_label", ""),
                    "permission_reason": permission.get("permission_reason", ""),
                    "tradability_guard": tradability_guard,
                    "report_day_is_one_word": tradability_guard.get("report_day_is_one_word", False),
                    "watch_source": "keep_group_watch",
                }
            )
            if signal and signal.is_valid:
                watch_candidate["signal"] = signal
                watch_candidate["signal_type"] = getattr(signal, "signal_type", "")
                watch_candidate["position_pct"] = safe_float(signal.position_pct, 0.0)
                watch_candidate["entry_price"] = signal.entry_price
                watch_candidate["entry_range"] = (signal.entry_price * 0.97, signal.entry_price * 1.03)
            scored_keep_watch_stocks.append(
                score_candidate_decision_stack(
                    score_execution_candidate(watch_candidate, ev_calibration),
                    final_gate=final_gate,
                    mainline_name=mainline_name,
                    conviction_codes=conviction_codes,
                    leader_memory_codes=leader_memory_codes,
                    state_machine_snapshot=market_research_snapshot.get("state_machine", {}),
                    target_date=target_date,
                )
            )

    abnormal_watch_anchor_candidates = build_abnormal_watch_anchor_candidates(
        abnormal_watch_pool=abnormal_watch_pool_all,
        existing_candidates=list(scored_executable_stocks) + list(scored_waiting_stocks) + list(scored_keep_watch_stocks),
        seed_candidates=step2_bundle.get("evaluated_stocks", []),
        target_date=target_date,
        mainline_name=mainline_name,
        final_gate=final_gate,
        conviction_codes=conviction_codes,
        leader_memory_codes=leader_memory_codes,
        ev_calibration=ev_calibration,
        state_machine_snapshot=market_research_snapshot.get("state_machine", {}),
    )

    observation_candidates = []
    if not trade_gate_open:
        observation_candidates = sort_watch_anchor_candidates(
            list(abnormal_watch_anchor_candidates)
            + list(scored_executable_stocks)
            + list(scored_waiting_stocks)
            + list(scored_keep_watch_stocks),
            mainline_name=mainline_name,
            state_machine_snapshot=market_research_snapshot.get("state_machine", {}),
        )

    display_pending_candidates = abnormal_watch_anchor_candidates if abnormal_watch_anchor_candidates else pending_candidates
    display_observation_candidates = abnormal_watch_anchor_candidates if abnormal_watch_anchor_candidates else observation_candidates

    return {
        "lines": [],
        "exports": {
            "scored_keep_watch_stocks": scored_keep_watch_stocks,
            "abnormal_watch_anchor_candidates": abnormal_watch_anchor_candidates,
            "observation_candidates": observation_candidates,
            "display_pending_candidates": display_pending_candidates,
            "display_observation_candidates": display_observation_candidates,
        },
        "module_logs": [],
    }
