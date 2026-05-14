from report.market_fit_calibration import build_market_fit_calibration


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _has_resolved_mainline_turnover_summary(summary):
    if not isinstance(summary, dict):
        return False
    if not str(summary.get("current_mainline") or "").strip():
        return False
    for row in summary.get("turnover_share_trend_rows") or []:
        if not isinstance(row, dict):
            continue
        has_mainline_turnover = str(row.get("mainline_turnover") or "").strip() not in {"", "-", "数据暂缺"}
        missing_market_turnover = str(row.get("market_turnover") or "").strip() in {"", "-", "数据暂缺"}
        if has_mainline_turnover and missing_market_turnover:
            return False
    return True


def _resolve_effective_total_turnover(
    data,
    observation_snapshot,
    target_date,
    *,
    get_market_total_turnover_from_fact_db=None,
):
    data = data or {}
    observation_snapshot = observation_snapshot or {}
    for value in (
        data.get("total_turnover"),
        observation_snapshot.get("turnover"),
        observation_snapshot.get("total_turnover"),
    ):
        total_turnover = _safe_float(value)
        if total_turnover > 0:
            return total_turnover

    if callable(get_market_total_turnover_from_fact_db):
        total_turnover = _safe_float(get_market_total_turnover_from_fact_db(target_date))
        if total_turnover > 0:
            return total_turnover

    return 0.0


def _fill_sector_snapshot_total_turnover(snapshot, total_turnover):
    if not isinstance(snapshot, dict):
        return snapshot or {}
    if not snapshot:
        return {}
    total_turnover = round(_safe_float(total_turnover), 2)
    if total_turnover <= 0 or _safe_float(snapshot.get("total_turnover")) > 0:
        return snapshot
    snapshot = dict(snapshot)
    sector_turnover = _safe_float(snapshot.get("sector_turnover"))
    snapshot["total_turnover"] = total_turnover
    if sector_turnover > 0:
        snapshot["turnover_share_pct"] = round(sector_turnover / total_turnover * 100, 2)
    return snapshot


def _derive_lhb_capital_intent(data, mainline_name=""):
    data = data or {}
    buy_rows = list(data.get("lhb_net_buy_top10") or [])
    sell_rows = list(data.get("lhb_net_sell_top10") or [])
    if not buy_rows and not sell_rows:
        return {}, {}

    sector_totals = {}
    for item in buy_rows:
        sector = str((item or {}).get("sector") or "未归类").strip() or "未归类"
        sector_totals[sector] = sector_totals.get(sector, 0.0) + _safe_float((item or {}).get("net_buy_amount_yi"))
    top_sector, top_amount = max(sector_totals.items(), key=lambda pair: pair[1]) if sector_totals else (mainline_name or "未归类", 0.0)
    sell_amount = abs(sum(_safe_float((item or {}).get("net_buy_amount_yi")) for item in sell_rows))
    strength = "强" if top_amount >= 5 else "中" if top_amount >= 2 else "弱"
    style_shift = "资金向主线集中" if mainline_name and top_sector == mainline_name else "资金偏轮动试探"
    status = {
        "capital_strength": strength,
        "capital_intensity": f"龙虎榜净买入集中在{top_sector}，约{top_amount:.2f}亿；净卖出端约{sell_amount:.2f}亿",
        "capital_direction": top_sector,
        "capital_intent": "承接主线核心" if mainline_name and top_sector == mainline_name else "尝试外溢或轮动",
        "style_shift": style_shift,
        "event_attribute": "龙虎榜资金行为",
    }
    conclusion = {
        "current_capital_state": f"龙虎榜资金{strength}，方向在{top_sector}",
        "mainline_attitude": "资金仍在主线内确认" if mainline_name and top_sector == mainline_name else "资金没有完全确认主线，先看是否轮动",
        "tomorrow_action_meaning": "只看主线核心承接，不追非主线热票" if mainline_name and top_sector == mainline_name else "先观察资金是否回到主线，再决定是否给资格",
    }
    return status, conclusion


def _append_log(logs, step, status, message, **details):
    logs.append(
        {
            "module": "research.market_research_runtime",
            "step": step,
            "status": status,
            "message": message,
            "details": details,
        }
    )


def _collect_market_fit_observation_pool(data, observation_snapshot):
    pool = []
    for source in (
        (observation_snapshot or {}).get("abnormal_watch_pool"),
        (observation_snapshot or {}).get("leader_memory_bank"),
        (data or {}).get("watchlist"),
        (data or {}).get("candidates"),
    ):
        if isinstance(source, list):
            pool.extend(item for item in source if isinstance(item, dict))
    return pool


def _collect_market_fit_strong_samples(data):
    data = data or {}
    if isinstance(data.get("strong_samples"), list):
        return data.get("strong_samples") or []
    return data.get("zt_pool") or []


def _load_recent_mainline_history_for_cycle_calendar(loader, target_date):
    try:
        return loader(target_date, lookback_days=25, max_scan_days=60)
    except TypeError as exc:
        if "max_scan_days" not in str(exc):
            raise
        return loader(target_date, lookback_days=25)


def build_market_research_snapshot_contract(
    data,
    final_gate,
    position_level,
    exit_analysis,
    observation_snapshot=None,
    target_date="",
    *,
    build_abnormal_projection_summary,
    build_market_style_switch_snapshot,
    build_market_state_machine_snapshot,
    build_mainline_rotation_snapshot,
    build_abnormal_probe_group,
    build_special_probe_verdict,
    build_follow_verdict,
    build_dialectical_decision_snapshot,
    build_mainline_turnover_summary=None,
    build_mainline_history_record=None,
    load_recent_mainline_history=None,
    get_market_total_turnover_from_fact_db=None,
    get_sector_turnover_snapshot_from_tencent_fund_flow=None,
    get_sector_turnover_snapshot_from_ths=None,
    load_recent_sector_turnover_history=None,
):
    observation_snapshot = observation_snapshot or {}
    sector_ai_analysis = data.get("sector_ai_analysis", {}) or {}
    mainline_turnover_summary = data.get("mainline_turnover_summary") or observation_snapshot.get("mainline_turnover_summary") or {}
    logs = []

    abnormal_projection = build_abnormal_projection_summary(observation_snapshot.get("abnormal_watch_pool", []))
    _append_log(logs, "abnormal_projection", "success", "已构建异常投影摘要")

    style_switch_snapshot = build_market_style_switch_snapshot(
        target_date,
        data,
        observation_snapshot=observation_snapshot,
        abnormal_projection=abnormal_projection,
    )
    _append_log(logs, "style_switch", "success", "已构建风格切换快照")

    state_machine_snapshot = build_market_state_machine_snapshot(
        data,
        final_gate,
        position_level,
        exit_analysis,
        main_sectors_info=observation_snapshot.get("main_sectors_info", []),
        secondary_sectors_info=observation_snapshot.get("secondary_sectors_info", []),
        sector_trend_snapshot=observation_snapshot.get("sector_trend_snapshot", []),
        abnormal_watch_pool=observation_snapshot.get("abnormal_watch_pool", []),
    )
    _append_log(logs, "state_machine", "success", "已构建状态机快照", state_code=state_machine_snapshot.get("state_code", ""))

    mainline_rotation_snapshot = build_mainline_rotation_snapshot(
        observation=observation_snapshot,
        state_machine=state_machine_snapshot,
        style_switch=style_switch_snapshot,
        sector_ai_analysis=sector_ai_analysis,
    )
    special_probe_group = build_abnormal_probe_group(
        style_switch_snapshot=style_switch_snapshot,
        abnormal_watch_pool=observation_snapshot.get("abnormal_watch_pool", []),
        mainline_name=state_machine_snapshot.get("leading_line", ""),
        watch_anchor={},
    )
    special_probe_verdict = build_special_probe_verdict(
        abnormal_probe_group=special_probe_group,
        watch_anchor={},
        watch_anchor_type="",
        mainline_name=state_machine_snapshot.get("leading_line", ""),
        target_date=target_date,
    )
    follow_verdict = build_follow_verdict(
        final_gate,
        position_level,
        state_machine_snapshot,
        special_probe_verdict=special_probe_verdict,
    )
    _append_log(logs, "follow_verdict", "success", "已构建跟随裁决", follow_label=follow_verdict.get("label", ""))

    dialectical_decision = build_dialectical_decision_snapshot(
        observation=observation_snapshot,
        style_switch=style_switch_snapshot,
        state_machine=state_machine_snapshot,
        follow_verdict=follow_verdict,
        final_gate=final_gate,
    )
    current_mainline_history_record = data.get("current_mainline_history_record") or {}
    recent_mainline_history = data.get("recent_mainline_history") or []
    current_sector_turnover_snapshot = data.get("current_sector_turnover_snapshot") or {}
    recent_sector_turnover_history = data.get("recent_sector_turnover_history") or []

    if not current_mainline_history_record and callable(build_mainline_history_record):
        current_mainline_history_record = build_mainline_history_record(
            target_date,
            {
                "observation": observation_snapshot,
                "state_machine": state_machine_snapshot,
                "mainline_rotation_snapshot": mainline_rotation_snapshot,
            },
        )

    current_mainline_name = str(
        (current_mainline_history_record or {}).get("primary_mainline")
        or (current_mainline_history_record or {}).get("leading_line")
        or state_machine_snapshot.get("leading_line", "")
        or ""
    ).strip()

    if not recent_mainline_history and callable(load_recent_mainline_history):
        recent_mainline_history = _load_recent_mainline_history_for_cycle_calendar(
            load_recent_mainline_history,
            target_date,
        )

    total_turnover = _resolve_effective_total_turnover(
        data,
        observation_snapshot,
        target_date,
        get_market_total_turnover_from_fact_db=get_market_total_turnover_from_fact_db,
    )
    current_sector_turnover_snapshot = _fill_sector_snapshot_total_turnover(
        current_sector_turnover_snapshot,
        total_turnover,
    )

    if not current_sector_turnover_snapshot and current_mainline_name and callable(get_sector_turnover_snapshot_from_tencent_fund_flow):
        current_sector_turnover_snapshot = get_sector_turnover_snapshot_from_tencent_fund_flow(
            current_mainline_name,
            data.get("sector_fund_flow", {}),
            target_date=target_date,
            total_turnover=total_turnover,
        )

    has_sector_turnover = _safe_float((current_sector_turnover_snapshot or {}).get("sector_turnover")) > 0
    if not has_sector_turnover and current_mainline_name and callable(get_sector_turnover_snapshot_from_ths):
        current_sector_turnover_snapshot = get_sector_turnover_snapshot_from_ths(
            current_mainline_name,
            target_date=target_date,
            total_turnover=total_turnover,
        )

    if not recent_sector_turnover_history and current_mainline_name and callable(load_recent_sector_turnover_history):
        recent_sector_turnover_history = load_recent_sector_turnover_history(
            target_date,
            current_mainline_name,
            lookback_days=5,
        )

    if not _has_resolved_mainline_turnover_summary(mainline_turnover_summary) and callable(build_mainline_turnover_summary):
        mainline_turnover_summary = build_mainline_turnover_summary(
            target_date=target_date,
            current_mainline_history_record=current_mainline_history_record,
            recent_mainline_history=recent_mainline_history,
            current_sector_turnover_snapshot=current_sector_turnover_snapshot,
            recent_sector_turnover_history=recent_sector_turnover_history,
        )

    market_fit_calibration = build_market_fit_calibration(
        strong_samples=_collect_market_fit_strong_samples(data),
        current_mainline=current_mainline_name,
        observation_pool=_collect_market_fit_observation_pool(data, observation_snapshot),
    )
    _append_log(
        logs,
        "market_fit_calibration",
        "success",
        "已构建市场贴合度校准",
        fit_label=market_fit_calibration.get("fit_label", ""),
    )

    lhb_capital_status, capital_conclusion = _derive_lhb_capital_intent(data, current_mainline_name)

    return {
        "observation": observation_snapshot,
        "style_switch": style_switch_snapshot,
        "state_machine": state_machine_snapshot,
        "abnormal_projection": abnormal_projection,
        "follow_verdict": follow_verdict,
        "special_probe_verdict": special_probe_verdict,
        "dialectical_decision": dialectical_decision,
        "mainline_rotation_snapshot": mainline_rotation_snapshot,
        "current_mainline_history_record": current_mainline_history_record,
        "recent_mainline_history": recent_mainline_history,
        "current_sector_turnover_snapshot": current_sector_turnover_snapshot,
        "recent_sector_turnover_history": recent_sector_turnover_history,
        "mainline_turnover_summary": mainline_turnover_summary,
        "market_fit_calibration": market_fit_calibration,
        "lhb_capital_status": lhb_capital_status,
        "capital_conclusion": capital_conclusion,
        "sector_ai_analysis": sector_ai_analysis,
        "final_gate": final_gate,
        "module_logs": logs,
    }


def derive_step0_follow_plan_contract(market_research_snapshot, final_gate, position_level):
    market_research_snapshot = market_research_snapshot or {}
    state_machine_snapshot = market_research_snapshot.get("state_machine", {}) or {}
    follow_verdict = market_research_snapshot.get("follow_verdict", {}) or {}
    style_switch = market_research_snapshot.get("style_switch", {}) or {}
    special_probe_verdict = market_research_snapshot.get("special_probe_verdict", {}) or {}
    logs = []

    step0_prediction = "NEUTRAL"
    if not final_gate.get("can_new_entry"):
        step0_prediction = "BLOCKED"
    elif state_machine_snapshot.get("state_code") == "expand":
        step0_prediction = "CLEAR"
    elif state_machine_snapshot.get("state_code") == "contract":
        step0_prediction = "DIFFICULT"

    prediction_map = {
        "BLOCKED": follow_verdict.get("label", "🚫 暂不跟随"),
        "DIFFICULT": "⚠️ 先看环境",
        "NEUTRAL": follow_verdict.get("label", "🟡 条件跟随"),
        "CLEAR": follow_verdict.get("label", "🟢 跟随主线"),
    }
    step0_reason = follow_verdict.get("reason") or state_machine_snapshot.get("state_reason", "")
    step0_action = follow_verdict.get("action") or state_machine_snapshot.get("reflection_focus", "")
    style_action = style_switch.get("primary_action", "")
    probe_action = str(special_probe_verdict.get("action", "") or "").strip()
    probe_summary = str(special_probe_verdict.get("summary_text", "") or "").strip()
    if probe_action and probe_action not in step0_action:
        step0_action = f"先看特殊标的：{probe_action}" if not step0_action else f"先看特殊标的：{probe_action}；{step0_action}"
    style_label = str(style_switch.get("style_label", "") or "").strip()
    if style_action and style_action not in step0_action:
        if step0_action:
            style_note_prefix = f"市场层面的{style_label}只作背景参考" if style_label else "市场层面的风格分歧只作背景参考"
            style_action_text = f"{style_note_prefix}：{style_action}"
        else:
            style_action_text = style_action
        step0_action = f"{step0_action}；{style_action_text}" if step0_action else style_action_text
    if probe_summary and probe_summary not in step0_reason:
        step0_reason = f"{step0_reason}；{probe_summary}" if step0_reason else probe_summary

    if step0_prediction == "DIFFICULT" and not step0_reason:
        step0_reason = f"当前处于{state_machine_snapshot.get('energy_state', '未知状态')}，先确认环境，再决定是否继续跟随。"

    _append_log(logs, "step0_plan", "success", "已生成 Step0 跟随计划", prediction=step0_prediction)

    return {
        "step0_prediction": step0_prediction,
        "step0_prediction_cn": prediction_map.get(step0_prediction, step0_prediction),
        "step0_reason": step0_reason,
        "step0_action": step0_action,
        "position_level": position_level,
        "module_logs": logs,
    }
