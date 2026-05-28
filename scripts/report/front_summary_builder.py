from report.mainline_turnover_summary_support import (
    resolve_double_mainline_summary,
    resolve_mainline_capacity_regime_summary,
    resolve_turnover_share_trend_rows,
)
from selection.position_sizing_runtime import with_single_focus_counts


def build_double_mainline_summary_contract(context=None):
    context = context or {}
    if any(key in context for key in ("cycle_mainline", "daily_attack_line", "relationship", "tomorrow_action")):
        context = {"double_mainline_summary": context}
    return resolve_double_mainline_summary(context)


def build_turnover_share_trend_contract(rows=None):
    return resolve_turnover_share_trend_rows({"turnover_share_trend_rows": rows or []})


def build_front_mainline_label_contract(market_research_snapshot, fallback_mainline=""):
    market_research_snapshot = market_research_snapshot or {}
    observation = market_research_snapshot.get("observation", {}) or {}
    state_machine = market_research_snapshot.get("state_machine", {}) or {}

    leading_line = state_machine.get("leading_line") or fallback_mainline or ""
    densest_sector = observation.get("densest_sector", "")
    densest_count = observation.get("densest_sector_trend_count", 0)

    parts = []
    if leading_line:
        parts.append(f"主攻线{leading_line}")
    if densest_sector:
        densest_label = f"趋势密度最强{densest_sector}"
        if densest_count:
            densest_label += f"({densest_count}只)"
        if densest_sector != leading_line:
            parts.append(densest_label)
        elif not parts:
            parts.append(densest_label)

    return "；".join(parts) if parts else "主线待确认"


def build_front_mainline_turnover_text_contract(market_research_snapshot):
    market_research_snapshot = market_research_snapshot or {}
    summary = market_research_snapshot.get("mainline_turnover_summary", {}) or {}

    parts = []
    conclusion = str(summary.get("conclusion", "") or "").strip()
    data_text = str(summary.get("data_text", "") or "").strip()
    if conclusion:
        parts.append(conclusion)
    if data_text:
        parts.append(data_text)
    return "；".join(parts)


def build_front_style_action_text_contract(
    style_switch=None,
    final_gate=None,
    best_stock=None,
    watch_anchor=None,
    watch_anchor_type="",
):
    style_switch = style_switch or {}
    final_gate = final_gate or {}
    style_label = str(style_switch.get("style_label", "待确认") or "待确认").strip()
    primary_action = str(style_switch.get("primary_action", "先看量能再决定跟随哪一侧") or "先看量能再决定跟随哪一侧").strip()
    watch_anchor_type = str(watch_anchor_type or "").strip()

    if best_stock:
        name = str(best_stock.get("name", "-") or "-").strip()
        code = str(best_stock.get("code", "") or "").strip()
        stock_label = f"{name}({code})" if code else name
        return f"{style_label}；市场层仍可参考{primary_action}，但执行层已只剩{stock_label}这一只，其余风格讨论不再构成动作建议"
    if watch_anchor and "异常" in watch_anchor_type:
        if "跨线" in watch_anchor_type:
            return f"{style_label}；市场层先看{primary_action}，但跨线对象只保留观察，不把新故事直接当成买入理由"
        return f"{style_label}；市场层先看{primary_action}，但没有缩到唯一对象前，这些风格讨论都不构成出手指令"
    return f"{style_label}；{primary_action}"


def render_core_mvp_digest_contract(
    market_research_snapshot,
    final_gate,
    position_level,
    position_reason,
    exit_analysis=None,
    execution_framework_text="",
    high_board_count=0,
    structure_layer_text="",
    front_follow_action_text="",
    special_probe_text="",
    philosophy_constraint_text="",
    best_stock=None,
    watch_anchor=None,
    watch_anchor_type="",
    target_date="",
    compact=False,
    *,
    build_front_mainline_label,
    build_gem_textbook_next_step_text,
    build_front_style_action_text,
    build_alignment_pool_text,
    build_mainline_rotation_snapshot,
    resolve_primary_mainline_name,
    build_weak_to_strong_context,
    get_contract_logic_digest_text,
    render_front_digest,
    safe_float,
):
    market_research_snapshot = market_research_snapshot or {}
    final_gate = final_gate or {}
    exit_analysis = exit_analysis or {}
    observation = market_research_snapshot.get("observation", {}) or {}
    style_switch = market_research_snapshot.get("style_switch", {}) or {}
    state_machine = market_research_snapshot.get("state_machine", {}) or {}
    follow_verdict = market_research_snapshot.get("follow_verdict", {}) or {}
    dialectical_decision = market_research_snapshot.get("dialectical_decision", {}) or {}

    mainline_label = build_front_mainline_label(
        market_research_snapshot,
        fallback_mainline=exit_analysis.get("sector_name", ""),
    )
    overall_level = exit_analysis.get("overall_level", "未知")
    dt_count = observation.get("dt_count", 0)
    front_high_board_count = max(
        int(safe_float(high_board_count)),
        int(safe_float(style_switch.get("high_board_count", 0))),
    )
    risk_parts = [f"主线状态{overall_level}"]
    risk_parts.append(f"跌停{dt_count}只")
    risk_parts.append(f"高位连板{front_high_board_count}只")
    front_follow_action_text = str(front_follow_action_text or final_gate.get("final_action", position_reason) or "").strip()
    can_open_text = str(structure_layer_text or follow_verdict.get("label", position_level) or "").strip()
    textbook_next_step_text = build_gem_textbook_next_step_text(watch_anchor, position_decision={})
    if textbook_next_step_text and textbook_next_step_text not in front_follow_action_text:
        front_follow_action_text = (
            f"{front_follow_action_text}；{textbook_next_step_text}"
            if front_follow_action_text
            else textbook_next_step_text
        )
    style_action_text = build_front_style_action_text(
        style_switch=style_switch,
        final_gate=final_gate,
        best_stock=best_stock,
        watch_anchor=watch_anchor,
        watch_anchor_type=watch_anchor_type,
    )
    alignment_pool_text = build_alignment_pool_text(
        market_research_snapshot=market_research_snapshot,
        watch_anchor=watch_anchor,
    )
    rotation_snapshot = market_research_snapshot.get("mainline_rotation_snapshot", {}) or build_mainline_rotation_snapshot(
        observation=observation,
        state_machine=state_machine,
        style_switch=style_switch,
        sector_ai_analysis=market_research_snapshot.get("sector_ai_analysis", {}) or {},
    )
    mainline_name = resolve_primary_mainline_name(
        market_research_snapshot,
        fallback_mainline=exit_analysis.get("sector_name", ""),
    )
    weak_to_strong_context = build_weak_to_strong_context(
        candidate=best_stock or watch_anchor,
        mainline_name=mainline_name,
        state_machine_snapshot=state_machine,
    )
    mainline_turnover_text = build_front_mainline_turnover_text_contract(market_research_snapshot)
    return render_front_digest(
        {
            "headline": front_follow_action_text,
            "state_text": f"{state_machine.get('energy_state', position_level)}；{state_machine.get('state_reason', position_reason)}",
            "mainline_label": mainline_label,
            "mainline_turnover_text": mainline_turnover_text,
            "mainline_capacity_regime_summary": resolve_mainline_capacity_regime_summary(market_research_snapshot),
            "turnover_share_trend_summary": str(
                (market_research_snapshot.get("mainline_turnover_summary") or {}).get("turnover_share_trend_summary")
                or market_research_snapshot.get("turnover_share_trend_summary")
                or ""
            ).strip(),
            "turnover_share_trend_rows": resolve_turnover_share_trend_rows(market_research_snapshot),
            "special_probe_text": special_probe_text,
            "philosophy_constraint_text": philosophy_constraint_text,
            "contract_logic_text": get_contract_logic_digest_text(),
            "alignment_pool_text": alignment_pool_text,
            "rotation_summary_text": rotation_snapshot.get("summary_text", ""),
            "rotation_narrative_text": rotation_snapshot.get("narrative_text", ""),
            "weak_to_strong_active": bool(weak_to_strong_context.get("active")),
            "weak_to_strong_summary_text": weak_to_strong_context.get("summary_text", ""),
            "style_action_text": style_action_text,
            "risk_parts": risk_parts,
            "can_open_text": can_open_text,
            "stage_label": dialectical_decision.get("stage_label", "") if dialectical_decision else "",
            "stage_action": dialectical_decision.get("stage_action", "") if dialectical_decision else "",
            "index_profit_relation": dialectical_decision.get("index_profit_relation", "") if dialectical_decision else "",
            "execution_framework_text": execution_framework_text,
            "compact": compact,
        }
    )


def render_mvp_focus_summary_contract(
    market_research_snapshot,
    watchlist=None,
    abnormal_watch_pool=None,
    leader_memory_bank=None,
    core_stocks=None,
    crossline_observation_stocks=None,
    gem_breathing_candidates=None,
    filtered_out_gem_candidates=None,
    structure_layer_text="",
    focus_group=None,
    keep_group=None,
    delete_group=None,
    best_stock=None,
    watch_anchor=None,
    watch_anchor_type="重点观察谁",
    abnormal_probe_group=None,
    final_gate=None,
    position_level="",
    target_date="",
    compact=False,
    *,
    resolve_primary_mainline_name,
    split_abnormal_watch_pool,
    build_bridge_prep_context,
    build_front_structure_layer_text,
    build_special_probe_verdict,
    build_special_probe_focus_text,
    build_mainline_rotation_snapshot,
    split_candidates_by_mainline,
    format_candidate_preview,
    candidate_matches_mainline,
    build_position_sizing_decision,
    build_cycle_triplet_texts,
    build_execute_anchor_window_text,
    format_abnormal_probe_text,
    build_front_follow_action_text,
    render_mvp_focus_summary,
):
    market_research_snapshot = market_research_snapshot or {}
    state_machine = market_research_snapshot.get("state_machine", {}) or {}
    mainline_name = resolve_primary_mainline_name(market_research_snapshot)
    watchlist = watchlist or []
    abnormal_watch_pool, degraded_abnormal_watch_pool = split_abnormal_watch_pool(abnormal_watch_pool)
    leader_memory_bank = leader_memory_bank or []
    core_stocks = core_stocks or []
    crossline_observation_stocks = crossline_observation_stocks or []
    gem_breathing_candidates = gem_breathing_candidates or []
    filtered_out_gem_candidates = filtered_out_gem_candidates or []
    focus_group = focus_group or []
    keep_group = keep_group or []
    delete_group = delete_group or []
    abnormal_probe_group = abnormal_probe_group or {}
    final_gate = with_single_focus_counts(
        final_gate,
        focus_group=focus_group,
        keep_group=keep_group,
    )
    bridge_prep = build_bridge_prep_context(
        position_level=position_level,
        final_gate=final_gate,
        watch_anchor=watch_anchor,
        watch_anchor_type=watch_anchor_type,
        state_machine_snapshot=state_machine,
    )

    if not structure_layer_text:
        structure_layer_text = build_front_structure_layer_text(
            final_gate=final_gate,
            focus_group=focus_group,
            keep_group=keep_group,
            delete_group=delete_group,
            best_stock=best_stock,
            watch_anchor=watch_anchor,
            watch_anchor_type=watch_anchor_type,
            position_level=position_level,
            state_machine_snapshot=state_machine,
            target_date=target_date,
            special_probe_verdict=build_special_probe_verdict(
                abnormal_probe_group=abnormal_probe_group,
                watch_anchor=watch_anchor,
                watch_anchor_type=watch_anchor_type,
                mainline_name=mainline_name,
                target_date=target_date,
            ),
        )
    special_probe_text = build_special_probe_focus_text(
        abnormal_probe_group=abnormal_probe_group,
        watch_anchor=watch_anchor,
        watch_anchor_type=watch_anchor_type,
        mainline_name=mainline_name,
        target_date=target_date,
    )
    rotation_snapshot = market_research_snapshot.get("mainline_rotation_snapshot", {}) or build_mainline_rotation_snapshot(
        observation=market_research_snapshot.get("observation", {}) or {},
        state_machine=state_machine,
        style_switch=market_research_snapshot.get("style_switch", {}) or {},
        sector_ai_analysis=market_research_snapshot.get("sector_ai_analysis", {}) or {},
    )

    mainline_watch_preview = ""
    crossline_watch_preview = ""
    generic_watch_preview = ""
    if watchlist:
        mainline_watchlist, crossline_watchlist = split_candidates_by_mainline(watchlist, mainline_name)
        if mainline_watchlist:
            mainline_watch_preview = format_candidate_preview(
                mainline_watchlist,
                lambda item: f"{item.get('name', '-')}({item.get('sector', '-')})",
                limit=2,
            )
        if crossline_watchlist:
            crossline_watch_preview = format_candidate_preview(
                crossline_watchlist,
                lambda item: f"{item.get('name', '-')}({item.get('sector', '-')})",
                limit=2,
            )
        if not mainline_watchlist and not crossline_watchlist:
            generic_watch_preview = format_candidate_preview(
                watchlist,
                lambda item: f"{item.get('name', '-')}({item.get('sector', '-')})",
                limit=3,
            )

    gem_breathing_text = ""
    filtered_gem_text = ""
    if gem_breathing_candidates:
        breathing_preview = " / ".join(
            f"{item.get('name', '-')}({item.get('code', '-')})[{item.get('tier', '-')}]"
            for item in gem_breathing_candidates[:2]
        )
        breathing_note = str(gem_breathing_candidates[0].get("note", "") or "").strip()
        gem_breathing_text = f"{breathing_preview}；{breathing_note}；只先进观察池，不直接给买入资格"
    elif filtered_out_gem_candidates:
        filtered_preview = " / ".join(
            f"{item.get('name', '-')}({item.get('code', '-')})[{item.get('sector', '-')}]"
            for item in filtered_out_gem_candidates[:2]
        )
        filtered_note = str(filtered_out_gem_candidates[0].get("filtered_reason", "") or "").strip()
        filtered_gem_text = f"当前有20cm预启动样本，但因非主线被过滤：{filtered_preview}；{filtered_note}"

    abnormal_preview = ""
    degraded_abnormal_text = ""
    if abnormal_watch_pool:
        abnormal_preview = " / ".join(
            f"{item.get('name', '-')}({item.get('follow_state', '-')})"
            for item in abnormal_watch_pool[:3]
        )
    elif degraded_abnormal_watch_pool:
        degraded_abnormal_text = "当前只有降级快照，先不把它当正式承接证据"

    memory_preview = ""
    if leader_memory_bank:
        memory_preview = " / ".join(
            f"{item.get('name', '-')}({item.get('sector', '-')})"
            for item in leader_memory_bank[:3]
        )

    core_preview = ""
    if core_stocks:
        core_preview = format_candidate_preview(
            core_stocks,
            lambda item: f"{item.get('name', '-')}({item.get('core_level', '-')})",
            limit=2,
        )
    cross_core_preview = ""
    if crossline_observation_stocks:
        cross_core_preview = format_candidate_preview(
            crossline_observation_stocks,
            lambda item: f"{item.get('name', '-')}({item.get('core_level', '-')})",
            limit=2,
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
        state_machine_snapshot=state_machine,
        best_stock=best_stock,
        watch_anchor=watch_anchor,
        watch_anchor_type=watch_anchor_type,
        mainline_name=mainline_name,
        target_date=target_date,
        special_probe_verdict=special_probe_verdict,
        mainline_anchor={},
    )
    cycle_triplet = build_cycle_triplet_texts(
        position_decision=position_decision,
        candidate=best_stock or watch_anchor,
        watch_anchor_type=watch_anchor_type,
    )
    build_execute_anchor_window_text(
        position_decision=position_decision,
        watch_anchor=watch_anchor,
        watch_anchor_type=watch_anchor_type,
    )
    branch_20cm = position_decision.get("branch_20cm", {}) or {}
    breathing_prep = branch_20cm.get("breathing_prep", {}) or {}
    special_probe_summary_text = special_probe_verdict.get("summary_text", "")
    if breathing_prep.get("active"):
        note = branch_20cm.get("reason") or breathing_prep.get("note") or "创业板20cm预启动观察。"
        gem_breathing_text = f"{note}；只先进观察池，不直接给买入资格"
    delete_preview = ""
    if delete_group:
        delete_preview = " / ".join(f"{item.get('name', '-')}" for item in delete_group[:2])

    buy_target_text = ""
    watch_target_text = ""
    no_trade_text = ""
    if final_gate.get("can_new_entry") and best_stock:
        buy_target_text = f"{best_stock.get('name', '-')}({best_stock.get('code', '-')})，只按09:30-09:35竞价表态/开盘承接/回封或09:50-10:10窗口参与，不追盘中情绪顶点"
    elif watch_anchor:
        watch_anchor_note = str(watch_anchor.get("watch_anchor_note", "") or "").strip()
        if final_gate.get("can_new_entry"):
            watch_target_text = (
                f"{watch_anchor.get('name', '-')}({watch_anchor.get('code', '-')})，"
                "先看固定交易窗口内条件，只有走成明天唯一能买的那只才参与"
                f"{'；' + watch_anchor_note if watch_anchor_note else ''}"
            )
        else:
            watch_anchor_label = f"（{watch_anchor_type}）" if str(watch_anchor_type or "").strip() else ""
            watch_target_text = (
                f"{watch_anchor.get('name', '-')}({watch_anchor.get('code', '-')}){watch_anchor_label}，"
                "只看强弱，不构成买入指令"
                f"{'；' + watch_anchor_note if watch_anchor_note else ''}"
            )
    else:
        if final_gate.get("allow_attack_50_ready") and not final_gate.get("can_new_entry") and not final_gate.get("should_reduce"):
            no_trade_text = "没有唯一对象就按0%不参与；只保留固定交易窗口预案，强核心看09:30-09:35竞价表态、开盘前几分钟或回封，普通结构只看09:50-10:10窗口"
        else:
            no_trade_text = "当前无新增执行对象，只保留市场研究与观察权"

    bridge_prep_label = ""
    bridge_prep_text = ""
    if bridge_prep.get("active"):
        bridge_prep_label = "条件执行预备态（优先保留）" if bridge_prep.get("priority_keep") else "条件执行预备态"
        bridge_prep_text = f"{bridge_prep.get('candidate_label', '-')}，{bridge_prep.get('upgrade_text', '-')}"

    mainline_abnormal_probe = abnormal_probe_group.get("mainline_abnormal_probe")
    crossline_abnormal_probe = abnormal_probe_group.get("crossline_abnormal_probe")
    validation_probe = abnormal_probe_group.get("validation_probe")
    fallback_watch_anchor = abnormal_probe_group.get("fallback_watch_anchor") or watch_anchor or {}
    mainline_probe_text = ""
    if mainline_abnormal_probe:
        mainline_probe_text = format_abnormal_probe_text(
            mainline_abnormal_probe,
            role_label="主线异动里先看谁",
            mainline_name=mainline_name,
            fallback_watch_anchor=fallback_watch_anchor,
        )
    crossline_probe_text = ""
    if crossline_abnormal_probe:
        crossline_probe_text = format_abnormal_probe_text(
            crossline_abnormal_probe,
            role_label="跨线异动里先看谁",
            mainline_name=mainline_name,
        )
    validation_probe_text = ""
    if validation_probe:
        validation_probe_text = format_abnormal_probe_text(
            validation_probe,
            role_label="承接验证先看谁",
            mainline_name=mainline_name,
        )

    front_follow_action_text = build_front_follow_action_text(
        final_gate=final_gate,
        best_stock=best_stock,
        watch_anchor=watch_anchor,
        watch_anchor_type=watch_anchor_type,
        fallback_text=final_gate.get("final_action", state_machine.get("reflection_focus", "-")),
        focus_group=focus_group,
        keep_group=keep_group,
        delete_group=delete_group,
        position_level=position_level,
        state_machine_snapshot=state_machine,
        target_date=target_date,
        special_probe_verdict=special_probe_verdict,
    )
    return render_mvp_focus_summary(
        {
            "special_probe_text": special_probe_text,
            "rotation_summary_text": rotation_snapshot.get("summary_text", ""),
            "rotation_narrative_text": rotation_snapshot.get("narrative_text", ""),
            "gem_breathing_text": gem_breathing_text,
            "filtered_gem_text": filtered_gem_text,
            "mainline_watch_preview": mainline_watch_preview,
            "crossline_watch_preview": crossline_watch_preview,
            "generic_watch_preview": generic_watch_preview,
            "abnormal_preview": abnormal_preview,
            "degraded_abnormal_text": degraded_abnormal_text,
            "memory_preview": memory_preview,
            "core_preview": core_preview,
            "cross_core_preview": cross_core_preview,
            "special_probe_summary_text": special_probe_summary_text,
            "structure_layer_text": structure_layer_text,
            "observation_cycle": cycle_triplet.get("observation_cycle", ""),
            "intervention_cycle": cycle_triplet.get("intervention_cycle", ""),
            "exit_cycle": cycle_triplet.get("exit_cycle", ""),
            "delete_preview": delete_preview,
            "buy_target_text": buy_target_text,
            "watch_target_text": watch_target_text,
            "no_trade_text": no_trade_text,
            "bridge_prep_label": bridge_prep_label,
            "bridge_prep_text": bridge_prep_text,
            "mainline_probe_text": mainline_probe_text,
            "crossline_probe_text": crossline_probe_text,
            "validation_probe_text": validation_probe_text,
            "front_follow_action_text": front_follow_action_text,
            "compact": compact,
        }
    )
