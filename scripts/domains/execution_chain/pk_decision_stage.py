from domains.execution_chain.pk_decision_node_registry import build_pk_decision_node_specs
from domains.execution_chain.pk_decision_node_runtime import run_pk_decision_nodes
from domains.execution_chain.pk_decision_nodes.action_plan_context import build_pk_decision_action_plan_context_node
from domains.execution_chain.pk_decision_nodes.export_stage_state import build_pk_decision_export_stage_state_node
from domains.execution_chain.pk_decision_nodes.front_texts import build_pk_decision_front_texts_node
from domains.execution_chain.pk_decision_nodes.observation_pool import build_pk_decision_observation_pool_node
from domains.execution_chain.pk_decision_nodes.pk_context import build_pk_decision_pk_context_node
from domains.execution_chain.pk_decision_nodes.probe_position import build_pk_decision_probe_position_node
from domains.execution_chain.pk_decision_nodes.render_sections import build_pk_decision_render_sections_node
from domains.execution_chain.pk_decision_nodes.score_candidates import build_pk_decision_score_candidates_node
from domains.execution_chain.pk_decision_nodes.watch_anchor import build_pk_decision_watch_anchor_node


def _append_log(logs, step, status, message, **details):
    logs.append(
        {
            "module": "domains.execution_chain.pk_decision_stage",
            "step": step,
            "status": status,
            "message": message,
            "details": details,
        }
    )


def format_closed_gate_buy_limit_text(position_level, final_gate):
    final_gate = final_gate or {}
    if final_gate.get("allow_conditional_30"):
        return "等10点确认，未确认不开"
    return f"⛔{position_level}禁止新开仓"


PK_DECISION_NODE_BUILDERS = {
    "score_candidates": build_pk_decision_score_candidates_node,
    "observation_pool": build_pk_decision_observation_pool_node,
    "watch_anchor": build_pk_decision_watch_anchor_node,
    "probe_position": build_pk_decision_probe_position_node,
    "front_texts": build_pk_decision_front_texts_node,
    "pk_context": build_pk_decision_pk_context_node,
    "action_plan_context": build_pk_decision_action_plan_context_node,
    "render_sections": build_pk_decision_render_sections_node,
    "export_stage_state": build_pk_decision_export_stage_state_node,
}


def build_pk_decision_runtime(stage_context, stage_meta, stage_lookup=None, enabled_node_keys=None):
    stage_context = stage_context or {}
    stage_meta = stage_meta or {}
    node_context = {
        **stage_context,
        "stage_label": str(stage_meta.get("label", "") or "Step 5").strip() or "Step 5",
        "stage_title": str(stage_meta.get("title", "") or "PK决胜局（期望值模型）").strip() or "PK决胜局（期望值模型）",
    }
    node_specs = build_pk_decision_node_specs(PK_DECISION_NODE_BUILDERS, enabled_node_keys=enabled_node_keys)
    runtime_result = run_pk_decision_nodes(node_specs, node_context)
    return {
        "lines": runtime_result["lines"],
        "exports": dict(runtime_result.get("context", {}).get("stage_exports", {}) or {}),
        "module_logs": list(runtime_result.get("module_logs") or []),
    }


def build_pk_decision_stage(stage_context, stage_meta, stage_lookup=None):
    stage_context = stage_context or {}
    logs = []

    target_date = stage_context.get("target_date", "")
    run_mode = stage_context.get("run_mode")
    position_level = str(stage_context.get("position_level", "") or "").strip()
    position_reason = str(stage_context.get("position_reason", "") or "").strip()
    step0_prediction = str(stage_context.get("step0_prediction", "") or "").strip()
    step0_prediction_cn = str(stage_context.get("step0_prediction_cn", "") or "").strip()
    step0_action = str(stage_context.get("step0_action", "") or "").strip()
    display_mvp_mode = bool(stage_context.get("display_mvp_mode", False))
    high_board_count = stage_context.get("high_board_count", 0)
    has_personal_positions = bool(stage_context.get("has_personal_positions", False))
    final_gate = stage_context.get("final_gate", {}) or {}
    mainline_name = str(stage_context.get("mainline_name", "") or "").strip()
    watchlist = stage_context.get("watchlist", []) or []
    core_stocks = stage_context.get("core_stocks", []) or []
    secondary_stocks = stage_context.get("secondary_stocks", []) or []
    abnormal_watch_pool = stage_context.get("abnormal_watch_pool", []) or []
    abnormal_watch_pool_all = stage_context.get("abnormal_watch_pool_all", []) or []
    market_research_bundle = stage_context.get("market_research_bundle", {}) or {}
    market_research_snapshot = stage_context.get("market_research_snapshot", {}) or {}
    focus_group = stage_context.get("focus_group", []) or []
    keep_group = stage_context.get("keep_group", []) or []
    delete_group = stage_context.get("delete_group", []) or []
    step2_bundle = stage_context.get("step2_bundle", {}) or {}
    conviction_codes = stage_context.get("conviction_codes", set()) or set()
    leader_memory_codes = stage_context.get("leader_memory_codes", set()) or set()
    executable_stocks = stage_context.get("executable_stocks", []) or []
    waiting_stocks = stage_context.get("waiting_stocks", []) or []
    safe_float = stage_context["safe_float"]
    build_strategy_ev_calibration = stage_context["build_strategy_ev_calibration"]
    score_execution_candidate = stage_context["score_execution_candidate"]
    score_candidate_decision_stack = stage_context["score_candidate_decision_stack"]
    sort_decision_stack_candidates = stage_context["sort_decision_stack_candidates"]
    sort_watch_anchor_candidates = stage_context["sort_watch_anchor_candidates"]
    get_trade_permission = stage_context["get_trade_permission"]
    fetch_recent_price_bars = stage_context["fetch_recent_price_bars"]
    evaluate_live_tradability = stage_context["evaluate_live_tradability"]
    analyze_buy_signal = stage_context.get("analyze_buy_signal")
    quant_system_available = bool(stage_context.get("quant_system_available", False))
    build_waiting_stock_plan = stage_context["build_waiting_stock_plan"]
    derive_watch_anchor_type = stage_context["derive_watch_anchor_type"]
    derive_watch_anchor_note = stage_context["derive_watch_anchor_note"]
    build_abnormal_watch_anchor_candidates = stage_context["build_abnormal_watch_anchor_candidates"]
    select_priority_watch_anchor = stage_context["select_priority_watch_anchor"]
    build_abnormal_probe_group = stage_context["build_abnormal_probe_group"]
    build_special_probe_verdict = stage_context["build_special_probe_verdict"]
    build_position_sizing_decision = stage_context["build_position_sizing_decision"]
    build_front_structure_layer_text = stage_context["build_front_structure_layer_text"]
    build_front_follow_action_text = stage_context["build_front_follow_action_text"]
    build_special_probe_focus_text = stage_context["build_special_probe_focus_text"]
    build_philosophy_constraint_text = stage_context["build_philosophy_constraint_text"]
    render_core_mvp_digest = stage_context["render_core_mvp_digest"]
    render_mvp_focus_summary = stage_context["render_mvp_focus_summary"]
    build_trade_price_focus = stage_context["build_trade_price_focus"]
    build_observation_price_focus_text = stage_context["build_observation_price_focus_text"]
    should_surface_price_note = stage_context["should_surface_price_note"]
    build_observation_price_note_text = stage_context["build_observation_price_note_text"]
    append_watch_anchor_note = stage_context["append_watch_anchor_note"]
    append_observation_price_focus_note = stage_context["append_observation_price_focus_note"]
    compose_observation_focus_text = stage_context["compose_observation_focus_text"]
    build_stop_execution_plan = stage_context["build_stop_execution_plan"]
    build_candidate_exit_rules = stage_context["build_candidate_exit_rules"]
    format_holding_window_text = stage_context["format_holding_window_text"]
    render_pk_decision_section = stage_context["render_pk_decision_section"]
    render_action_plan_section = stage_context["render_action_plan_section"]
    decision_stack_order_text = stage_context["decision_stack_order_text"]
    today_predictions = stage_context.get("today_predictions", []) or []
    nextday_predictions = stage_context.get("nextday_predictions", []) or []

    stage_label = str((stage_meta or {}).get("label", "") or "Step 5").strip() or "Step 5"

    lines = []

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

    pk_candidates = scored_executable_stocks if trade_gate_open else []
    best_stock = pk_candidates[0] if pk_candidates else None
    runner_up = pk_candidates[1] if len(pk_candidates) >= 2 else None
    watch_anchor = None
    watch_anchor_type = ""
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
    )
    selected_position_candidate = best_stock or watch_anchor
    if selected_position_candidate and position_decision.get("target_position_pct", 0) > 0:
        selected_position_candidate["position_pct"] = int(safe_float(position_decision.get("target_position_pct", 0)))
    if selected_position_candidate:
        selected_position_candidate["candidate_feedback_ready"] = bool(position_decision.get("candidate_feedback_ready"))

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
        fallback_text=final_gate.get("final_action", step0_action),
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
        exit_analysis=stage_context.get("exit_analysis", {}) or {},
        execution_framework_text=stage_context["get_execution_framework_text"](),
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
        leader_memory_bank=stage_context.get("leader_memory_bank", []) or [],
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

    pending_lines = []
    if trade_gate_open:
        if display_pending_candidates:
            if len(display_pending_candidates) >= 2:
                pending_lines.append(f"**重点盯盘股排序**（{len(display_pending_candidates)}只，先看谁最可能走成明天唯一能买的那只）:")
                pending_lines.append("| 股票 | 来源 | 60分钟确认点 | 候选顺位 | 说明 |")
                pending_lines.append("|------|------|--------------|----------|------|")
                for idx, candidate in enumerate(display_pending_candidates[:5], 1):
                    minute_plan = candidate.get("minute_plan") or {}
                    confirm_price = minute_plan.get("confirm_price_60m")
                    confirm_text = f"{confirm_price:.2f}" if confirm_price else "待盘中确认"
                    source_text = candidate.get("permission_label", "候选")
                    note = candidate.get("reason", candidate.get("permission_reason", "等待盘中确认"))
                    pending_lines.append(
                        f"| {candidate.get('name')} | {source_text} | {confirm_text} | 第{idx}顺位 | {note} |"
                    )
                pending_lines.append("")
            top_pending = display_pending_candidates[0]
            top_minute_plan = top_pending.get("minute_plan") or {}
            top_stop_plan = top_pending.get("stop_plan")
            top_price_focus = build_trade_price_focus(top_minute_plan, top_stop_plan)
            top_confirm_price = top_minute_plan.get("confirm_price_60m")
            top_price_focus_text = build_observation_price_focus_text(top_price_focus)
            pending_lines.append(f"**明天先盯哪只**: {top_pending.get('name')}({top_pending.get('code')})")
            pending_lines.append(
                f"- **原因**: {top_pending.get('permission_reason', top_pending.get('reason', '当前先看它能否继续证明自己'))}"
            )
            if top_confirm_price:
                pending_lines.append(f"- **60分钟确认点**: {top_confirm_price:.2f}")
            if top_price_focus_text and top_price_focus_text != "-":
                pending_lines.append(f"- **价格怎么盯**: {top_price_focus_text}")
            if should_surface_price_note(top_price_focus):
                pending_lines.append(f"- **价格怎么看**: {build_observation_price_note_text(top_price_focus)}")
            pending_lines.append("- **升级条件**: 明日先完成60分钟确认，再走成明天唯一能买的那只，不能直接追价")
            pending_lines.append("")
        else:
            pending_lines.extend(["**当前没有能下手的票**: 无需PK", ""])

    observation_lines = []
    if not trade_gate_open:
        if display_observation_candidates:
            if len(display_observation_candidates) >= 2:
                observation_lines.append(f"**先看谁排第几**（{len(display_observation_candidates)}只，优先盯强分歧但没坏的对象）:")
                observation_lines.append("| 股票 | 来源 | 买点 | 60分钟确认点 | 先看顺序 | 说明 |")
                observation_lines.append("|------|------|------|--------------|------------|------|")
                source_label_map = {
                    "execute_layer": "执行层",
                    "keep_group_watch": "观察组",
                    "waiting_layer": "等待层",
                    "abnormal_probe": "异常层",
                }
                for idx, candidate in enumerate(display_observation_candidates[:5], 1):
                    signal = candidate.get("signal")
                    minute_plan = candidate.get("minute_plan") or {}
                    confirm_price = minute_plan.get("confirm_price_60m")
                    confirm_text = f"{confirm_price:.2f}" if confirm_price else "待盘中确认"
                    buy_type_map = {"sweet_zone": "甜品区", "breakout": "突破", "panic_buy": "恐慌盘"}
                    buy_type = buy_type_map.get(signal.signal_type, signal.signal_type) if signal else "基础"
                    source_text = source_label_map.get(candidate.get("watch_source", ""), "观察")
                    note = candidate.get("watch_priority_label", "观察")
                    if idx == 1:
                        note = f"{note}，优先看它能否继续证明自己"
                    observation_lines.append(
                        f"| {candidate.get('name')} | {source_text} | {buy_type} | {confirm_text} | 第{idx}顺位 | {note} |"
                    )
                observation_lines.append("")
            top_watch = display_observation_candidates[0]
            top_signal = top_watch.get("signal")
            observation_lines.append(f"**观察优先锚点**: {top_watch.get('name')}({top_watch.get('code')})")
            observation_lines.append(
                f"- **原因**: {top_watch.get('watch_priority_label', '观察优先')}；"
                f"{top_watch.get('reason', top_watch.get('tomorrow_risk', '当前优先盯它的承接变化'))}"
            )
            if top_signal:
                entry_range = top_watch.get("entry_range", (top_signal.entry_price, top_signal.entry_price))
                minute_plan = top_watch.get("minute_plan") or {}
                stop_plan = top_watch.get("stop_plan")
                price_focus = build_trade_price_focus(minute_plan, stop_plan)
                confirm_price = minute_plan.get("confirm_price_60m")
                observation_price_focus_text = build_observation_price_focus_text(price_focus)
                observation_lines.append(f"- **跟踪区间**: {entry_range[0]:.2f}-{entry_range[1]:.2f}")
                if confirm_price:
                    observation_lines.append(f"- **60分钟确认点**: {confirm_price:.2f}")
                if observation_price_focus_text and observation_price_focus_text != "-":
                    observation_lines.append(f"- **价格怎么盯**: {observation_price_focus_text}")
                if should_surface_price_note(price_focus):
                    observation_lines.append(f"- **价格怎么看**: {build_observation_price_note_text(price_focus)}")
                observation_lines.append(f"- **参考依据**: {top_watch.get('ev_model_source', '类型先验')}")
                observation_lines.append("- **观察纪律**: 只记录是否继续走强，不构成明日买入指令")
            observation_lines.append("")
        else:
            observation_lines.extend(["**无执行权候选**: 当前没有进入执行层的标的，只保留观察池", ""])

    conclusion_lines = ["**结论**:"]
    if best_stock:
        signal = best_stock.get("signal")
        if signal:
            entry_range = best_stock.get("entry_range", (signal.entry_price, signal.entry_price))
            buy_type_map = {
                "sweet_zone": "甜品区买入",
                "breakout": "放量突破买入",
                "panic_buy": "恐慌盘买入",
            }
            buy_type = buy_type_map.get(signal.signal_type, signal.signal_type)
            conclusion_lines.append(f"- **如果要买只买谁**: {best_stock.get('name')}({best_stock.get('code')})")
            conclusion_lines.append(f"- **怎么买**: {buy_type}")
            conclusion_lines.append(f"- **到什么价位再动手**: {entry_range[0]:.2f}-{entry_range[1]:.2f}")
            display_position_pct = safe_float(best_stock.get("position_pct", signal.position_pct))
            conclusion_lines.append(f"- **仓位放多少**: {display_position_pct:.0f}%")
            stop_plan = best_stock.get("stop_plan") or build_stop_execution_plan(
                signal.entry_price,
                best_stock.get("stop_loss", signal.stop_loss),
                structure_label="日线预估结构止损",
            )
            minute_plan = best_stock.get("minute_plan") or {}
            price_focus = build_trade_price_focus(minute_plan, stop_plan)
            confirm_price = minute_plan.get("confirm_price_60m")
            if confirm_price:
                conclusion_lines.append(f"- **60分钟确认点**: {confirm_price:.2f}")
            conclusion_lines.append(f"- **价格怎么盯**: {price_focus.get('compact_text', '-')}")
            if should_surface_price_note(price_focus):
                conclusion_lines.append(f"- **价格怎么看**: {price_focus.get('note_text', '-')}")
            conclusion_lines.append(f"- **参考依据**: {best_stock.get('ev_model_source', '类型先验')}")
            conclusion_lines.append("- **出手时怎么做**: 明日仅在60分钟确认后买入，买后用30分钟结构止损，最晚不超过单笔-5%；其他标的无论多诱人都**禁止操作**")
        else:
            conclusion_lines.append(f"- **如果要买只买谁**: {best_stock.get('name')}({best_stock.get('code')})")
            conclusion_lines.append("- **出手时怎么做**: 明日仅在60分钟确认后按条件触发买入，买后用30分钟结构止损，其他标的禁止操作")
    else:
        if trade_gate_open and watch_anchor:
            conclusion_lines.append(f"- **明天先盯哪只**: {watch_anchor.get('name')}({watch_anchor.get('code')})")
            conclusion_lines.append("- **现在是什么情况**: 市场允许出手，但还没有缩到一只可买股，明日先等它自己证明")
        else:
            conclusion_lines.append("- **明天没有可买对象**: 明日不产生买入动作")
        conclusion_lines.append(f"- **明天能不能开仓**: {front_structure_layer_text}")
        if watch_anchor:
            minute_plan = watch_anchor.get("minute_plan") or {}
            stop_plan = watch_anchor.get("stop_plan")
            price_focus = build_trade_price_focus(minute_plan, stop_plan)
            confirm_price = minute_plan.get("confirm_price_60m")
            confirm_text = f"{confirm_price:.2f}" if confirm_price else "待盘中确认"
            observation_price_focus_text = build_observation_price_focus_text(price_focus)
            conclusion_lines.append(f"- **{watch_anchor_type}**: {watch_anchor.get('name')}({watch_anchor.get('code')})")
            conclusion_lines.append(
                f"- **{'现在重点盯什么' if trade_gate_open else '现在重点看什么'}**: "
                f"{compose_observation_focus_text(confirm_text, observation_price_focus_text)}"
            )
            append_watch_anchor_note(conclusion_lines, watch_anchor)
            if should_surface_price_note(price_focus):
                conclusion_lines.append(f"- **价格怎么看**: {build_observation_price_note_text(price_focus)}")
            if trade_gate_open:
                conclusion_lines.append("- **出手时怎么做**: 只能等它走成明天唯一能买的那只后再买，盘中强也不允许提前抢跑")
            elif final_gate.get("allow_conditional_30"):
                conclusion_lines.append("- **当前先不抢**: 二档防守观察，只在10点确认主线承接后评估30%条件试错")
            else:
                conclusion_lines.append(f"- **当前先不买**: {position_level}，当前只允许观察，不允许新买入")
        else:
            conclusion_lines.append("- **明天先怎么观察**: 空仓观望")
    conclusion_lines.append("")

    lines.extend(
        render_pk_decision_section(
            {
                "decision_stack_order_text": decision_stack_order_text,
                "scored_executable_stocks": scored_executable_stocks,
                "pk_candidates": pk_candidates,
                "stage_label": stage_label,
                "stage_title": "PK决胜局（期望值模型）",
                "trade_gate_open": trade_gate_open,
                "position_level": position_level,
                "pending_lines": pending_lines,
                "observation_lines": observation_lines,
                "conclusion_lines": conclusion_lines,
            }
        )
    )

    action_rows = []
    if best_stock:
        if "signal" in best_stock:
            signal = best_stock["signal"]
            minute_plan = best_stock.get("minute_plan") or {}
            confirm_price = minute_plan.get("confirm_price_60m")
            stop_plan = best_stock.get("stop_plan") or build_stop_execution_plan(
                signal.entry_price,
                best_stock.get("stop_loss", signal.stop_loss),
                structure_label="日线预估结构止损",
            )
            exit_rules = build_candidate_exit_rules(best_stock, stop_plan)
            stop_summary_text = (stop_plan or {}).get("summary")
            if not stop_summary_text:
                stop_summary_text = f"预估{best_stock.get('stop_loss', signal.stop_loss):.2f}"
            action_rows.append(
                {
                    "action": "🔥 唯一买入",
                    "name": best_stock.get("name"),
                    "code": best_stock.get("code"),
                    "trigger": f"明日首个60分钟站上{confirm_price:.2f}" if confirm_price else "明日60分钟确认后触发",
                    "risk_window": f"{stop_summary_text} / {format_holding_window_text(exit_rules.get('holding_days_min'), exit_rules.get('holding_days_max'))}",
                }
            )
        else:
            stop_plan = best_stock.get("stop_plan")
            minute_plan = best_stock.get("minute_plan") or {}
            confirm_price = minute_plan.get("confirm_price_60m")
            exit_rules = build_candidate_exit_rules(best_stock, stop_plan)
            action_rows.append(
                {
                    "action": "🔥 唯一买入",
                    "name": best_stock.get("name"),
                    "code": best_stock.get("code"),
                    "trigger": (
                        f"明日首个60分钟站上{confirm_price:.2f}后按{best_stock.get('trigger', '条件')}执行"
                        if confirm_price
                        else f"明日60分钟确认后按{best_stock.get('trigger', '条件')}执行"
                    ),
                    "risk_window": f"{(stop_plan or {}).get('summary', '先看30分钟结构 / 最晚-5%')} / "
                    f"{format_holding_window_text(exit_rules.get('holding_days_min'), exit_rules.get('holding_days_max'))}",
                }
            )
    elif trade_gate_open and watch_anchor:
        minute_plan = watch_anchor.get("minute_plan") or {}
        stop_plan = watch_anchor.get("stop_plan")
        price_focus = build_trade_price_focus(minute_plan, stop_plan)
        confirm_price = minute_plan.get("confirm_price_60m")
        exit_rules = build_candidate_exit_rules(watch_anchor, stop_plan)
        action_rows.append(
            {
                "action": "👀 明天先盯哪只",
                "name": watch_anchor.get("name"),
                "code": watch_anchor.get("code"),
                "trigger": (
                    f"首个60分钟站上{confirm_price:.2f}后，再看是否走成明天唯一能买的那只"
                    if confirm_price
                    else "先看60分钟确认，再看是否走成明天唯一能买的那只"
                ),
                "risk_window": f"{(price_focus or {}).get('key_zone_display', '-')} / "
                f"{format_holding_window_text(exit_rules.get('holding_days_min'), exit_rules.get('holding_days_max'))}",
            }
        )
    else:
        action_rows.append(
            {
                "action": "❌ 明天没有可买对象",
                "name": "-",
                "code": "-",
                "trigger": format_closed_gate_buy_limit_text(position_level, final_gate) if not trade_gate_open else "无符合条件标的",
                "risk_window": "-",
            }
        )

    observation_priority_lines = []
    if not trade_gate_open and display_observation_candidates:
        for candidate in display_observation_candidates[:3]:
            minute_plan = candidate.get("minute_plan") or {}
            stop_plan = candidate.get("stop_plan")
            price_focus = build_trade_price_focus(minute_plan, stop_plan)
            confirm_price = minute_plan.get("confirm_price_60m")
            confirm_text = f"{confirm_price:.2f}" if confirm_price else "待盘中确认"
            observation_price_focus_text = build_observation_price_focus_text(price_focus)
            observation_priority_lines.append(
                f"- 👀 {candidate.get('name')}({candidate.get('code')}) - "
                f"{candidate.get('watch_anchor_type', candidate.get('permission_label', '观察权'))}，"
                f"{compose_observation_focus_text(confirm_text, observation_price_focus_text)}"
            )
            append_watch_anchor_note(observation_priority_lines, candidate, prefix="  ")
            append_observation_price_focus_note(observation_priority_lines, price_focus, prefix="  ")

    backup_observation_lines = []
    for candidate in waiting_stocks[:3]:
        minute_plan = candidate.get("minute_plan") or {}
        stop_plan = candidate.get("stop_plan")
        price_focus = build_trade_price_focus(minute_plan, stop_plan)
        confirm_price = minute_plan.get("confirm_price_60m")
        confirm_text = f"{confirm_price:.2f}" if confirm_price else "待盘中确认"
        observation_price_focus_text = build_observation_price_focus_text(price_focus)
        backup_observation_lines.append(
            f"- ⏳ {candidate.get('name')}({candidate.get('code')}) - 等买点出现，"
            f"{compose_observation_focus_text(confirm_text, observation_price_focus_text)}"
        )
        append_observation_price_focus_note(backup_observation_lines, price_focus, prefix="  ")

    position_section_lines = [
        f"- **市场环境档位**: {position_level}",
        f"- **明日裁决**: {step0_prediction_cn}",
        f"- **怎么执行**: {stage_context['get_execution_framework_text']()}",
    ]
    if position_level == "一档（空仓档）":
        position_section_lines.extend(
            [
                "- **现在到底是什么状态**: 空仓",
                "- **明天仓位放多少**: 0%（必须空仓）",
                "- **明天具体怎么做**: 清仓或保持空仓，禁止任何买入",
            ]
        )
    elif position_level == "二档（防守档）":
        position_section_lines.append("- **现在到底是什么状态**: 防守观察")
        if final_gate.get("should_reduce"):
            position_section_lines.append("- **明天仓位放多少**: 最多30%（只留强者，不做新增）")
            position_section_lines.append(
                "- **明天具体怎么做**: 只处理你的旧仓，去弱留强，禁止新开仓"
                if has_personal_positions
                else "- **明天具体怎么做**: 市场级原则是若你有旧仓就去弱留强，禁止新开仓"
            )
        else:
            position_section_lines.append("- **明天仓位放多少**: 最多30%（只在10点确认后条件试错）")
            position_section_lines.append(
                "- **明天具体怎么做**: 旧强仓可持有；新仓只允许主线核心完成10点确认后小仓试错"
                if has_personal_positions
                else "- **明天具体怎么做**: 只观察主线核心是否完成10点确认，确认前不开，确认后最多30%条件试错"
            )
    else:
        if not best_stock:
            if watch_anchor:
                position_section_lines.extend(
                    [
                        "- **现在到底是什么状态**: 还没有缩到一只可买股",
                        "- **明天仓位放多少**: 0%（市场允许出手，但还没有可买股前不开仓）",
                        "- **明天具体怎么做**: 只观察明天先盯哪只，等它走成明天唯一能买的那只后再买",
                    ]
                )
            else:
                position_section_lines.extend(
                    [
                        "- **现在到底是什么状态**: 市场允许出手但还没有对象",
                        "- **明天仓位放多少**: 0%（没有标的可买）",
                        "- **明天具体怎么做**: 空仓等待，不做任何试错买入",
                    ]
                )
        elif step0_prediction == "DIFFICULT":
            position_section_lines.extend(
                [
                    "- **现在到底是什么状态**: 等开盘再确认",
                    "- **明天仓位放多少**: 开盘前重新评估后再定",
                    "- **明天具体怎么做**: 观望为主，不急于开仓",
                ]
            )
        elif step0_prediction == "NEUTRAL":
            position_section_lines.extend(
                [
                    "- **现在到底是什么状态**: 已经缩到一只可买股",
                    "- **明天仓位放多少**: 最多30%（轻仓试错）",
                    "- **明天具体怎么做**: 严格按买点触发，不追涨",
                ]
            )
        else:
            position_section_lines.extend(
                [
                    "- **现在到底是什么状态**: 已经缩到一只可买股",
                    "- **明天仓位放多少**: 最多50%（正常参与）",
                    "- **明天具体怎么做**: 积极执行买点计划",
                ]
            )

    pre_market_lines = []
    if best_stock:
        if "signal" in best_stock:
            signal = best_stock["signal"]
            minute_plan = best_stock.get("minute_plan") or {}
            confirm_price = minute_plan.get("confirm_price_60m")
            structure_stop_30m = minute_plan.get("structure_stop_30m")
            if confirm_price:
                pre_market_lines.append(f"- **设价格预警**: {best_stock.get('name')}({best_stock.get('code')}) - 首个60分钟站上{confirm_price:.2f}提醒")
            else:
                entry_range = best_stock.get("entry_range", (signal.entry_price, signal.entry_price))
                pre_market_lines.append(f"- **设价格预警**: {best_stock.get('name')}({best_stock.get('code')}) - 触及{entry_range[0]:.2f}-{entry_range[1]:.2f}提醒")
            if structure_stop_30m:
                pre_market_lines.append(f"- **止损预埋**: 若买入，30分钟结构止损先盯{structure_stop_30m:.2f}")
        else:
            minute_plan = best_stock.get("minute_plan") or {}
            confirm_price = minute_plan.get("confirm_price_60m")
            pre_market_lines.append(
                f"- **关注标的**: {best_stock.get('name')}({best_stock.get('code')}) - "
                f"{'首个60分钟站上' + format(confirm_price, '.2f') + '后按条件触发' if confirm_price else '按条件触发'}"
            )
    elif watch_anchor:
        minute_plan = watch_anchor.get("minute_plan") or {}
        stop_plan = watch_anchor.get("stop_plan")
        price_focus = build_trade_price_focus(minute_plan, stop_plan)
        confirm_price = minute_plan.get("confirm_price_60m")
        confirm_text = f"{confirm_price:.2f}" if confirm_price else "待盘中确认"
        observation_price_focus_text = build_observation_price_focus_text(price_focus)
        pre_market_lines.append(
            f"- **{watch_anchor_type}**: {watch_anchor.get('name')}({watch_anchor.get('code')}) - "
            f"{compose_observation_focus_text(confirm_text, observation_price_focus_text)}"
        )
        append_watch_anchor_note(pre_market_lines, watch_anchor)
        append_observation_price_focus_note(pre_market_lines, price_focus)
    else:
        pre_market_lines.append("- **空仓准备**: 无操作标的，准备观望")
    pre_market_lines.extend(["- 查看隔夜消息、外围市场、期货走势", "- 确认A杀冷却池无变化"])

    opening_lines = [
        "- 观察涨跌比、昨日涨停溢价率",
        "- 重新评估Step 0裁决是否仍然成立",
        "- 观察观察池个股的竞价情况",
        "- 这30分钟只确认环境，不抢买点",
    ]
    if trade_gate_open and best_stock:
        first_hour_lines = [
            "- 日线环境未被破坏 + 60分钟结构确认 → 才允许执行买点",
            "- 直接高开离买点>5% 或 60分钟走弱 → 放弃，等新的买点",
        ]
        intraday_lines = [
            "- 60分钟确认后，触及买点区间且大盘不崩 → 按预设仓位买入",
            "- 买入后用30分钟结构设置止损；若结构止损过深，则直接用单笔-5%硬止损",
            "- 跌破执行止损线 → 无条件止损",
        ]
    elif trade_gate_open and watch_anchor:
        first_hour_lines = [
            "- 市场允许出手，但当前还不是明天唯一能买的那只，本时段先看重点盯盘股能否完成60分钟确认",
            "- 只有它继续抗跌并走成明天唯一能买的那只，才允许进入买入流程",
        ]
        intraday_lines = [
            "- 继续只盯明天先盯哪只，不做多票分散",
            "- 它如果始终走不成明天唯一能买的那只 → 当天继续等待，不抢跑",
            "- 若候选盘中直接走坏或失守关键位/带 → 取消它的执行资格",
        ]
    else:
        if final_gate.get("allow_conditional_30"):
            first_hour_lines = [
                "- 当前仍是防守观察，本时段只确认主线核心是否完成10点确认",
                "- 重点观察优先锚点是否继续走强；确认后最多30%条件试错，未确认不开",
            ]
            intraday_lines = [
                "- 以观察和处理持仓为主；新仓只允许10点确认后的主线核心小仓试错",
                "- 若你有仓位，30分钟结构失守或日内明显转弱 → 执行减仓/止损",
                "- 若观察标的全天未形成更强确认 → 继续等待",
            ]
        else:
            first_hour_lines = [
                "- 当前门控不允许新开仓，本时段只确认环境是否继续支持持仓/观察",
                "- 重点观察优先锚点是否继续走强；若你有旧仓，只处理旧仓，不做新增",
            ]
            intraday_lines = [
                "- 以观察和处理持仓为主，不做新开仓",
                "- 若你有仓位，30分钟结构失守或日内明显转弱 → 执行减仓/止损",
                "- 若观察标的全天未形成更强确认 → 继续等待",
            ]

    closing_lines = ["- 未买入的保持观望"]
    if trade_gate_open and best_stock:
        closing_lines.append("- 已买入的确认30分钟止损线是否需要上移")
    else:
        closing_lines.append("- 若你有旧仓，确认30分钟结构止损线是否需要上移")

    alert_rows = []
    for pred in (today_predictions or [])[:3]:
        actual_change = pred.get("actual_change_pct")
        if actual_change is not None:
            actual_change_str = f"{actual_change:+.2f}%"
            if pred.get("is_triggered") is True:
                trigger_status = "✅已触发"
            elif pred.get("is_triggered") is False:
                trigger_status = "⏳未触发"
            else:
                trigger_status = "❓未知"
        else:
            actual_change_str = "-"
            trigger_status = "待观察"
        alert_rows.append(
            {
                "name": pred.get("name", "?"),
                "code": pred.get("code", "?"),
                "deviation_days": pred.get("deviation_days", 0),
                "trigger_info": f"{pred.get('trigger_pct', 0):+.2f}%",
                "actual_change_str": actual_change_str,
                "trigger_status": trigger_status,
            }
        )
    for pred in (nextday_predictions or [])[:2]:
        alert_rows.append(
            {
                "name": pred.get("name", "?"),
                "code": pred.get("code", "?"),
                "deviation_days": pred.get("deviation_days", 0),
                "trigger_info": f"次日{pred.get('trigger_pct', 0):+.2f}%",
                "actual_change_str": "-",
                "trigger_status": "次日观察",
            }
        )

    lines.extend(
        render_action_plan_section(
            {
                "section_title": "明日操作计划",
                "action_rows": action_rows,
                "observation_priority_lines": observation_priority_lines,
                "backup_observation_lines": backup_observation_lines,
                "position_section_lines": position_section_lines,
                "pre_market_lines": pre_market_lines,
                "opening_lines": opening_lines,
                "first_hour_lines": first_hour_lines,
                "intraday_lines": intraday_lines,
                "closing_lines": closing_lines,
                "alert_rows": alert_rows,
            }
        )
    )
    lines.append("")

    _append_log(
        logs,
        "render.stage",
        "success",
        "已生成PK决策阶段",
        stage_key=(stage_meta or {}).get("stage_key", "pk_decision"),
        trade_gate_open=trade_gate_open,
        has_best_stock=bool(best_stock),
        has_watch_anchor=bool(watch_anchor),
    )
    return {
        "lines": lines,
        "exports": {
            "trade_gate_open": trade_gate_open,
            "best_stock": best_stock,
            "runner_up": runner_up,
            "watch_anchor": watch_anchor,
            "watch_anchor_type": watch_anchor_type,
            "abnormal_probe_group": abnormal_probe_group,
            "special_probe_verdict": special_probe_verdict,
            "position_decision": position_decision,
            "front_structure_layer_text": front_structure_layer_text,
            "front_follow_action_text": front_follow_action_text,
            "special_probe_text": special_probe_text,
            "philosophy_constraint_text": philosophy_constraint_text,
            "scored_executable_stocks": scored_executable_stocks,
            "core_mvp_digest_lines": core_mvp_digest_lines,
            "mvp_focus_summary_lines": mvp_focus_summary_lines,
        },
        "module_logs": logs,
    }
