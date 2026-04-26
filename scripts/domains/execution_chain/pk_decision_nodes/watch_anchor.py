def build_pk_decision_watch_anchor_node(context, node_meta=None, node_lookup=None):
    target_date = context.get("target_date", "")
    final_gate = context.get("final_gate", {}) or {}
    mainline_name = str(context.get("mainline_name", "") or "").strip()
    market_research_snapshot = context.get("market_research_snapshot", {}) or {}
    step2_bundle = context.get("step2_bundle", {}) or {}
    conviction_codes = context.get("conviction_codes", set()) or set()
    leader_memory_codes = context.get("leader_memory_codes", set()) or set()

    safe_float = context["safe_float"]
    get_trade_permission = context["get_trade_permission"]
    fetch_recent_price_bars = context["fetch_recent_price_bars"]
    evaluate_live_tradability = context["evaluate_live_tradability"]
    analyze_buy_signal = context.get("analyze_buy_signal")
    quant_system_available = bool(context.get("quant_system_available", False))
    build_waiting_stock_plan = context["build_waiting_stock_plan"]
    derive_watch_anchor_type = context["derive_watch_anchor_type"]
    derive_watch_anchor_note = context["derive_watch_anchor_note"]
    select_priority_watch_anchor = context["select_priority_watch_anchor"]

    trade_gate_open = context.get("trade_gate_open", False)
    pending_candidates = context.get("pending_candidates", []) or []
    observation_candidates = context.get("observation_candidates", []) or []
    waiting_stocks = context.get("waiting_stocks", []) or []
    abnormal_watch_anchor_candidates = context.get("abnormal_watch_anchor_candidates", []) or []

    watch_anchor, watch_anchor_type = select_priority_watch_anchor(
        trade_gate_open=trade_gate_open,
        abnormal_watch_anchor_candidates=abnormal_watch_anchor_candidates,
        pending_candidates=pending_candidates,
        observation_candidates=observation_candidates,
        waiting_stocks=waiting_stocks,
        gem_observation_stocks=step2_bundle.get("gem_observation_stocks", []),
        target_date=target_date,
        mainline_name=mainline_name,
    )
    if watch_anchor and not watch_anchor_type:
        watch_anchor_type = str(watch_anchor.get("watch_anchor_type", "") or "").strip()

    if not trade_gate_open and not watch_anchor and step2_bundle.get("crossline_observation_stocks"):
        crossline_watch_seed = dict(step2_bundle.get("crossline_observation_stocks", [])[0] or {})
        code = crossline_watch_seed.get("code", "")
        close_price = safe_float(crossline_watch_seed.get("close"))
        permission = get_trade_permission(
            crossline_watch_seed,
            mainline_name=mainline_name,
            conviction_codes=conviction_codes,
            leader_memory_codes=leader_memory_codes,
            final_gate=final_gate,
            state_machine_snapshot=market_research_snapshot.get("state_machine", {}),
        )
        recent_bars = fetch_recent_price_bars(code, target_date, lookback_days=4)
        tradability_guard = evaluate_live_tradability(
            crossline_watch_seed,
            target_date,
            recent_bars=recent_bars,
        )
        signal = (
            analyze_buy_signal(
                code,
                crossline_watch_seed.get("name", ""),
                close_price,
                safe_float(crossline_watch_seed.get("volume")),
            )
            if (quant_system_available and close_price > 0 and code and analyze_buy_signal)
            else None
        )
        signal_type = getattr(signal, "signal_type", "") if signal and signal.is_valid else ""
        entry_seed_price = signal.entry_price if signal and signal.is_valid else close_price
        watch_anchor = build_waiting_stock_plan(
            {
                **crossline_watch_seed,
                "entry_price": entry_seed_price,
                "condition": crossline_watch_seed.get("tmr_forecast")
                or crossline_watch_seed.get("abnormal_summary")
                or "观察跨线承接是否继续增强",
                "tradability_guard": tradability_guard,
                "report_day_is_one_word": tradability_guard.get("report_day_is_one_word", False),
            },
            target_date,
            reason=crossline_watch_seed.get("tmr_forecast")
            or crossline_watch_seed.get("abnormal_summary")
            or "观察跨线承接是否继续增强",
            signal_type=signal_type,
            recent_bars=[],
        )
        watch_anchor.update(
            {
                "permission_label": permission.get("permission_label", "") or "跨线观察权",
                "permission_reason": permission.get("permission_reason", "") or "只作承接观察，不授予主线执行权",
                "tradability_guard": tradability_guard,
                "report_day_is_one_word": tradability_guard.get("report_day_is_one_word", False),
                "watch_source": "keep_group_watch",
            }
        )
        if signal and signal.is_valid:
            watch_anchor["signal"] = signal
            watch_anchor["signal_type"] = getattr(signal, "signal_type", "")
            watch_anchor["position_pct"] = safe_float(signal.position_pct, 0.0)
            watch_anchor["entry_price"] = signal.entry_price
            watch_anchor["entry_range"] = (signal.entry_price * 0.97, signal.entry_price * 1.03)
        watch_anchor_type = derive_watch_anchor_type(watch_anchor, mainline_name=mainline_name) or "跨线重点观察谁"
        watch_anchor["watch_anchor_note"] = derive_watch_anchor_note(watch_anchor, mainline_name=mainline_name)

    return {
        "lines": [],
        "exports": {
            "watch_anchor": watch_anchor,
            "watch_anchor_type": watch_anchor_type,
        },
        "module_logs": [],
    }
