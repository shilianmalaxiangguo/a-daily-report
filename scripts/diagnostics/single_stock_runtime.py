def _append_log(logs, step, status, message, **details):
    logs.append(
        {
            "module": "diagnostics.single_stock_runtime",
            "step": step,
            "status": status,
            "message": message,
            "details": details,
        }
    )


def _absorb_single_stock_snapshot(base, item, source_tag=""):
    if not item:
        return

    mappings = {
        "name": ["name", "名称"],
        "sector": ["sector", "所属行业", "所属板块"],
        "change": ["change", "涨跌幅", "change_pct"],
        "close": ["close", "最新价", "price"],
        "open": ["open", "开盘价"],
        "high": ["high", "最高价"],
        "low": ["low", "最低价"],
        "volume": ["volume", "成交额", "amount"],
        "score": ["score"],
        "pattern": ["pattern"],
        "source": ["source"],
        "tomorrow_expectation": ["tomorrow_expectation"],
        "tomorrow_strength": ["tomorrow_strength"],
        "core_level": ["core_level"],
        "tmr_forecast": ["tmr_forecast"],
        "reason": ["reason"],
        "abnormal_follow_state": ["abnormal_follow_state", "follow_state"],
        "abnormal_type": ["abnormal_type"],
        "abnormal_summary": ["abnormal_summary"],
        "abnormal_setup_signal_id": ["abnormal_setup_signal_id", "setup_signal_id"],
        "abnormal_setup_signal_label": ["abnormal_setup_signal_label", "setup_signal_label"],
        "abnormal_is_degraded_snapshot": ["abnormal_is_degraded_snapshot", "is_degraded_snapshot"],
    }

    for target_key, source_keys in mappings.items():
        current_value = base.get(target_key)
        if current_value not in (None, "", 0, 0.0, False):
            continue
        for source_key in source_keys:
            value = item.get(source_key)
            if value not in (None, "", 0, 0.0, False):
                base[target_key] = value
                break

    if source_tag:
        base.setdefault("source_tags", [])
        if source_tag not in base["source_tags"]:
            base["source_tags"].append(source_tag)


def resolve_single_stock_snapshot_contract(
    data,
    stock_code,
    stock_name="",
    market_research_bundle=None,
    step2_bundle=None,
    *,
    normalize_stock_code,
    get_stock_sector,
    fetch_recent_price_bars,
    safe_float,
    compute_bar_change_pct,
):
    logs = []
    code = normalize_stock_code(stock_code)
    stock = {
        "code": code,
        "name": stock_name or "",
        "source_tags": [],
    }
    market_research_bundle = market_research_bundle or {}
    step2_bundle = step2_bundle or {}

    def maybe_absorb(item, source_tag):
        item_code = normalize_stock_code(item.get("code", item.get("代码", "")))
        item_name = item.get("name", item.get("名称", ""))
        if item_code and item_code == code:
            _absorb_single_stock_snapshot(stock, item, source_tag)
            return True
        if not code and stock_name and item_name == stock_name:
            _absorb_single_stock_snapshot(stock, item, source_tag)
            return True
        return False

    for source_tag, items in (
        ("step2_evaluated", step2_bundle.get("evaluated_stocks", [])),
        ("step1_watchlist", market_research_bundle.get("watchlist", [])),
        ("abnormal_watch", market_research_bundle.get("abnormal_watch_pool_all", [])),
        ("leader_memory", market_research_bundle.get("leader_memory_bank", [])),
        ("hot_rank", market_research_bundle.get("hot_stocks", [])),
        ("zt_pool", data.get("zt_pool", [])),
        ("turnover_rank", data.get("turnover_rank", [])),
        ("stocks_with_history", data.get("stocks_with_history", [])),
    ):
        for item in items or []:
            maybe_absorb(item, source_tag)

    if not stock.get("sector"):
        stock["sector"] = get_stock_sector(
            stock.get("name", ""),
            code,
            hot_rank_data=data.get("hot_rank_top30", []),
            zt_pool_data=data.get("zt_pool_by_sector", {}),
            lianban_data=(data.get("lianban_data", {}) or {}).get("stocks", []),
            lhb_data=data.get("lhb_details", []),
            sector_fund_flow=data.get("sector_fund_flow"),
            zt_pool_raw=data.get("zt_pool", []),
            dt_pool_raw=data.get("dt_pool", []),
            skip_api_call=True,
        )
        _append_log(logs, "resolve.sector", "success", "已补齐单票板块", sector=stock.get("sector", ""))

    if (safe_float(stock.get("close")) <= 0 or stock.get("change") in (None, "")) and code:
        recent_bars = fetch_recent_price_bars(code, data.get("target_date", ""), lookback_days=3)
        if recent_bars:
            latest_bar = recent_bars[-1]
            prev_bar = recent_bars[-2] if len(recent_bars) >= 2 else {}
            stock.setdefault("open", latest_bar.get("open"))
            stock.setdefault("high", latest_bar.get("high"))
            stock.setdefault("low", latest_bar.get("low"))
            stock["close"] = safe_float(stock.get("close") or latest_bar.get("close"))
            if stock.get("change") in (None, ""):
                stock["change"] = round(compute_bar_change_pct(latest_bar, prev_bar), 2)
            if safe_float(stock.get("volume")) <= 0:
                stock["volume"] = safe_float(latest_bar.get("amount") or latest_bar.get("volume"))
            _append_log(logs, "resolve.price_bars", "success", "已补齐单票价格快照", bar_count=len(recent_bars))
        else:
            _append_log(logs, "resolve.price_bars", "warning", "未取到补充K线，沿用现有快照")

    _append_log(logs, "resolve.snapshot", "success", "已解析单票快照", code=code, source_tags=stock.get("source_tags", []))
    return {"stock": stock, "module_logs": logs}


def compose_single_stock_final_verdict_contract(
    phase_context,
    stock,
    permission,
    tradability_guard,
    risk_signal,
    risk_row,
    quant_signal,
):
    final_gate = (phase_context or {}).get("final_gate", {}) or {}
    risk_group = risk_row.get("dest", "系统外")
    risk_level = risk_row.get("risk_level", "-")
    risk_reason_text = risk_row.get("reason", "-")
    risk_tomorrow_text = risk_row.get("tomorrow_risk", "-")

    if not tradability_guard.get("can_trade", True):
        return "观察，不买", f"卡在可交易性：{tradability_guard.get('reason', '')}"

    if risk_group == "明天先回避谁":
        return "回避", f"卡在个股风险层：{risk_tomorrow_text or risk_reason_text}"

    if risk_signal.get("light") == "🔴 红灯" or stock.get("abnormal_follow_state") == "已经转弱":
        return "回避", f"卡在触发层：{risk_signal.get('forecast') or permission.get('permission_reason', '')}"

    if not final_gate.get("can_new_entry", False):
        passed_parts = []
        if risk_level and risk_group and risk_group != "系统外":
            passed_parts.append(f"{risk_level}/{risk_group}")
        if permission.get("can_execute") and permission.get("permission_label"):
            passed_parts.append(permission.get("permission_label"))
        if tradability_guard.get("can_trade", True) and tradability_guard.get("status_label"):
            passed_parts.append(tradability_guard.get("status_label"))
        passed_text = " / ".join([part for part in passed_parts if part])
        if passed_text:
            prefix = "个股层已通过" if risk_group == "可按计划" else "个股层仍保留跟踪价值"
            return "环境未开，不买", f"{prefix}（{passed_text}），但环境层未开：{final_gate.get('final_action', '')}"
        return "环境未开，不买", f"环境层未开：{final_gate.get('final_action', '')}"

    if not permission.get("can_execute"):
        return "观察，等确认", f"卡在执行权限层：{permission.get('permission_reason', '') or '条件未齐，不抢跑'}"

    if quant_signal and quant_signal.is_valid:
        return "进入执行等待区", f"环境已开，且执行层通过：{permission.get('permission_reason', '')}；{quant_signal.reason}"

    if quant_signal and not quant_signal.is_valid and "跌破" in str(quant_signal.reason or ""):
        return "回避", f"结构层转弱：{quant_signal.reason}"

    if quant_signal and getattr(quant_signal, "reason", ""):
        return "观察，等确认", f"环境已开，但结构触发未完成：{quant_signal.reason}"

    return "观察，等确认", f"环境已开，但当前还没走出明确结构预案；{permission.get('permission_reason', '') or '继续等确认'}"


def build_single_stock_diagnostic_contract(
    data,
    target_date,
    stock_code,
    stock_name="",
    run_mode="frozen",
    *,
    build_market_phase_context,
    build_market_research_context_bundle,
    build_step2_candidate_bundle,
    build_step3_risk_bundle,
    resolve_single_stock_snapshot=None,
    normalize_stock_code,
    get_trade_permission,
    fetch_recent_price_bars,
    evaluate_live_tradability,
    get_abnormal_follow_risk_signal,
    safe_float,
    analyze_buy_signal,
    quant_system_available,
    build_intraday_execution_plan,
    build_stop_execution_plan,
    enrich_stop_plan_with_reference_anchors,
    stop_prior_low_trading_days,
    score_candidate_decision_stack,
    score_execution_candidate,
    build_strategy_ev_calibration,
    build_trade_price_focus,
    compose_single_stock_final_verdict=None,
    render_single_stock_diagnostic_markdown=None,
    get_stock_sector=None,
    compute_bar_change_pct=None,
):
    logs = []
    compose_single_stock_final_verdict = compose_single_stock_final_verdict or compose_single_stock_final_verdict_contract

    if resolve_single_stock_snapshot is None:
        resolve_single_stock_snapshot = lambda current_data, current_stock_code, stock_name="", market_research_bundle=None, step2_bundle=None: resolve_single_stock_snapshot_contract(
            current_data,
            current_stock_code,
            stock_name=stock_name,
            market_research_bundle=market_research_bundle,
            step2_bundle=step2_bundle,
            normalize_stock_code=normalize_stock_code,
            get_stock_sector=get_stock_sector,
            fetch_recent_price_bars=fetch_recent_price_bars,
            safe_float=safe_float,
            compute_bar_change_pct=compute_bar_change_pct,
        )

    phase_context = build_market_phase_context(data, target_date, emit_logs=False)
    _append_log(logs, "build.phase_context", "success", "已构建市场环境上下文")

    market_research_bundle = build_market_research_context_bundle(
        data,
        target_date,
        exit_analysis=phase_context.get("exit_analysis", {}),
        final_gate=phase_context.get("final_gate", {}),
        position_level=phase_context.get("position_level", ""),
        main_sectors_info=phase_context.get("main_sectors_info", []),
        secondary_sectors_info=phase_context.get("secondary_sectors_info", []),
        main_sectors=phase_context.get("main_sectors", []),
        secondary_sectors=phase_context.get("secondary_sectors", []),
        dragon_stocks=phase_context.get("dragon_stocks", []),
    )
    _append_log(logs, "build.research_bundle", "success", "已构建市场研究上下文")

    step2_bundle = build_step2_candidate_bundle(
        data,
        exit_analysis=phase_context.get("exit_analysis", {}),
        candidates=market_research_bundle.get("candidates", []),
        watchlist=market_research_bundle.get("watchlist", []),
        abnormal_watch_map=market_research_bundle.get("abnormal_watch_map", {}),
        dragon_stocks=phase_context.get("dragon_stocks", []),
        zt_pool_by_sector=market_research_bundle.get("zt_pool_by_sector", {}),
        gem_breathing_candidates=market_research_bundle.get("gem_breathing_candidates", []),
        target_date=target_date,
    )
    _append_log(logs, "build.step2_bundle", "success", "已构建候选池分层结果")

    step3_bundle = build_step3_risk_bundle(
        data,
        target_date,
        mainline_name=market_research_bundle.get("mainline_name", ""),
        core_stocks=step2_bundle.get("core_stocks", []),
        secondary_stocks=step2_bundle.get("secondary_stocks", []),
        gem_observation_stocks=step2_bundle.get("gem_observation_stocks", []),
        zt_pool_by_sector=market_research_bundle.get("zt_pool_by_sector", {}),
        dt_pool_by_sector=market_research_bundle.get("dt_pool_by_sector", {}),
        persist_a_kill=False,
    )
    _append_log(logs, "build.step3_bundle", "success", "已构建个股风险分层结果")

    resolved_snapshot = resolve_single_stock_snapshot(
        data,
        stock_code,
        stock_name=stock_name,
        market_research_bundle=market_research_bundle,
        step2_bundle=step2_bundle,
    )
    if isinstance(resolved_snapshot, dict) and "stock" in resolved_snapshot:
        stock = resolved_snapshot.get("stock", {}) or {}
        logs.extend(resolved_snapshot.get("module_logs", []) or [])
    else:
        stock = resolved_snapshot or {}

    code = normalize_stock_code(stock.get("code", stock_code))
    name = stock.get("name") or stock_name or code

    core_codes = {normalize_stock_code(item.get("code", "")) for item in step2_bundle.get("core_stocks", []) if item.get("code")}
    secondary_codes = {normalize_stock_code(item.get("code", "")) for item in step2_bundle.get("secondary_stocks", []) if item.get("code")}
    crossline_observation_codes = {
        normalize_stock_code(item.get("code", ""))
        for item in step2_bundle.get("crossline_observation_stocks", [])
        if item.get("code")
    }
    gem_observation_codes = {
        normalize_stock_code(item.get("code", ""))
        for item in step2_bundle.get("gem_observation_stocks", [])
        if item.get("code")
    }
    watch_codes = {normalize_stock_code(item.get("code", "")) for item in market_research_bundle.get("watchlist", []) if item.get("code")}
    conviction_codes = {
        normalize_stock_code(item.get("code", ""))
        for item in step2_bundle.get("extreme_conviction_list", [])
        if item.get("code")
    }
    leader_memory_codes = {
        normalize_stock_code(item.get("code", ""))
        for item in market_research_bundle.get("leader_memory_bank", [])
        if item.get("code")
    }

    abnormal_item = market_research_bundle.get("abnormal_watch_map", {}).get(code, {})
    if abnormal_item:
        _absorb_single_stock_snapshot(stock, abnormal_item, "abnormal_watch")
        _append_log(logs, "resolve.abnormal_watch", "success", "已补齐异动观察信息")

    if code in conviction_codes:
        system_role = "极度看好名单"
    elif code in core_codes:
        system_role = "明日核心"
    elif code in secondary_codes:
        system_role = "明日次核心"
    elif code in crossline_observation_codes:
        system_role = "跨线观察对象"
    elif code in gem_observation_codes:
        system_role = "创业板20cm预启动观察"
    elif code in leader_memory_codes:
        system_role = "龙头记忆"
    elif code in watch_codes:
        system_role = "观察池"
    else:
        system_role = "系统外对象"

    permission = get_trade_permission(
        stock,
        mainline_name=market_research_bundle.get("mainline_name", ""),
        conviction_codes=conviction_codes,
        leader_memory_codes=leader_memory_codes,
        final_gate=phase_context.get("final_gate", {}),
        state_machine_snapshot=market_research_bundle.get("market_state_snapshot", {}),
    )

    recent_bars = fetch_recent_price_bars(code, target_date, lookback_days=4) if code else []
    daily_anchor_bars = (
        fetch_recent_price_bars(code, target_date, lookback_days=max(stop_prior_low_trading_days + 5, 10))
        if code
        else []
    )
    tradability_guard = evaluate_live_tradability(stock, target_date, recent_bars=recent_bars)
    risk_signal = get_abnormal_follow_risk_signal(stock)

    close_price = safe_float(stock.get("close"))
    volume_value = safe_float(stock.get("volume"))
    quant_signal = analyze_buy_signal(code, name, close_price, volume_value) if (quant_system_available and close_price > 0 and code) else None
    minute_plan = (
        build_intraday_execution_plan(
            code,
            target_date,
            close_price,
            signal_type=(getattr(quant_signal, "signal_type", "") if quant_signal and quant_signal.is_valid else ""),
            fallback_stop=None,
        )
        if close_price > 0 and code
        else {}
    )
    stop_plan = (minute_plan.get("stop_plan") if minute_plan else None) or (
        build_stop_execution_plan(close_price) if close_price > 0 else None
    )
    stop_plan = enrich_stop_plan_with_reference_anchors(
        stop_plan,
        code,
        target_date,
        recent_bars=daily_anchor_bars,
    )

    scored_candidate = score_candidate_decision_stack(
        score_execution_candidate(
            {
                **stock,
                "entry_price": close_price,
                "stop_loss": stop_plan.get("effective_stop") if stop_plan else 0,
                "permission_label": permission.get("permission_label", ""),
                "minute_plan": minute_plan,
                "stop_plan": stop_plan,
                "tradability_guard": tradability_guard,
                "signal": quant_signal if quant_signal and quant_signal.is_valid else None,
            },
            build_strategy_ev_calibration(target_date, ledger_mode=run_mode),
        ),
        final_gate=phase_context.get("final_gate", {}),
        mainline_name=market_research_bundle.get("mainline_name", ""),
        conviction_codes=conviction_codes,
        leader_memory_codes=leader_memory_codes,
        state_machine_snapshot=market_research_bundle.get("market_state_snapshot", {}),
        target_date=target_date,
    )
    decision_stack = scored_candidate.get("decision_stack", {}) or {}
    risk_row = (step3_bundle.get("by_code", {}) or {}).get(code, {})
    risk_group = risk_row.get("dest", "系统外")
    risk_level = risk_row.get("risk_level", "-")
    risk_tomorrow_text = risk_row.get("tomorrow_risk", "-")
    risk_reason_text = risk_row.get("reason", "-")
    final_verdict, final_reason = compose_single_stock_final_verdict(
        phase_context,
        stock,
        permission,
        tradability_guard,
        risk_signal,
        risk_row,
        quant_signal,
    )

    price_focus = build_trade_price_focus(minute_plan, stop_plan)
    confirm_price = minute_plan.get("confirm_price_60m")
    confirm_text = f"{confirm_price:.2f}" if confirm_price else "-"
    ev_stack_text = f"{safe_float(decision_stack.get('ev_score')):.1f}" if decision_stack.get("ev_score") not in (None, "") else "-"

    payload = {
        "target_date": target_date,
        "name": name,
        "code": code,
        "position_level": phase_context.get("position_level", "-"),
        "final_action": phase_context.get("final_gate", {}).get("final_action", "-"),
        "mainline_name": market_research_bundle.get("mainline_name", "-"),
        "driver_type": (market_research_bundle.get("market_state_snapshot", {}) or {}).get("driver_type", "-"),
        "pulse_stage": (market_research_bundle.get("market_state_snapshot", {}) or {}).get("pulse_stage", "-"),
        "acceptance_quality": (market_research_bundle.get("market_state_snapshot", {}) or {}).get("acceptance_quality", "-"),
        "pulse_action_bias": (market_research_bundle.get("market_state_snapshot", {}) or {}).get("pulse_action_bias", "-"),
        "energy_state": (market_research_bundle.get("market_state_snapshot", {}) or {}).get("energy_state", "-"),
        "step0_prediction_cn": (market_research_bundle.get("step0_plan", {}) or {}).get("step0_prediction_cn", "-"),
        "system_role": system_role,
        "sector": stock.get("sector", "未知"),
        "change_pct": safe_float(stock.get("change")),
        "pattern": stock.get("pattern", "-"),
        "abnormal_follow_state": stock.get("abnormal_follow_state", "无明确异动跟踪"),
        "risk_light": risk_signal.get("light", "-"),
        "risk_reason": risk_signal.get("reason", "-"),
        "permission_label": permission.get("permission_label", "-"),
        "permission_reason": permission.get("permission_reason", "-"),
        "risk_level": risk_level,
        "risk_group": risk_group,
        "risk_reason_text": risk_reason_text,
        "risk_penalty_count": len(risk_row.get("risk_penalties", []) or []),
        "repair_buffer_count": len(risk_row.get("repair_buffers", []) or []),
        "raw_risk_score": risk_row.get("raw_risk_score", "-"),
        "risk_score": risk_row.get("risk_score", "-"),
        "tradability_status": tradability_guard.get("status_label", "-"),
        "tradability_reason": tradability_guard.get("reason", "-"),
        "quant_signal_type": getattr(quant_signal, "signal_type", "-") if quant_signal else "-",
        "quant_reason": quant_signal.reason if quant_signal else "暂无量化信号",
        "confirm_text": confirm_text,
        "key_zone_display": price_focus.get("key_zone_display", "-"),
        "execution_stop_display": price_focus.get("execution_stop_display", "-"),
        "hard_stop_display": price_focus.get("hard_stop_display", "-"),
        "price_note_text": price_focus.get("note_text", "-"),
        "decision_stack": decision_stack,
        "ev_stack_text": ev_stack_text,
        "final_verdict": final_verdict,
        "final_reason": final_reason or "-",
        "risk_tomorrow_text": risk_tomorrow_text,
        "tmr_forecast": stock.get("tmr_forecast"),
        "source_tags": stock.get("source_tags", []),
    }
    markdown = render_single_stock_diagnostic_markdown(payload)
    _append_log(logs, "render.markdown", "success", "已生成单票诊断 Markdown", system_role=system_role, final_verdict=final_verdict)

    return {
        "markdown": markdown,
        "payload": payload,
        "stock": stock,
        "phase_context": phase_context,
        "market_research_bundle": market_research_bundle,
        "step2_bundle": step2_bundle,
        "step3_bundle": step3_bundle,
        "module_logs": logs,
    }
