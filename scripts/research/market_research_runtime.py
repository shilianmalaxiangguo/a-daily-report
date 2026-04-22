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
):
    observation_snapshot = observation_snapshot or {}
    sector_ai_analysis = data.get("sector_ai_analysis", {}) or {}
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

    return {
        "observation": observation_snapshot,
        "style_switch": style_switch_snapshot,
        "state_machine": state_machine_snapshot,
        "abnormal_projection": abnormal_projection,
        "follow_verdict": follow_verdict,
        "special_probe_verdict": special_probe_verdict,
        "dialectical_decision": dialectical_decision,
        "mainline_rotation_snapshot": mainline_rotation_snapshot,
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
