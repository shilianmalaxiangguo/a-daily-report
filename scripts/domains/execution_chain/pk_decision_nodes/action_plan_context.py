from report.surface_wording import sanitize_user_visible_text
from domains.execution_chain.pk_decision_nodes.candidate_quality_scorecard import build_candidate_quality_scorecard_payload
from domains.execution_chain.pk_decision_nodes.candidate_surface_filter import candidate_can_be_current_observation_target
from domains.execution_chain.pk_decision_nodes.candidate_surface_filter import blocked_current_observation_keys
from report.trading_time_window_contract import normalize_trading_time_text


def _format_closed_gate_buy_limit_text(position_level, final_gate):
    final_gate = final_gate or {}
    if final_gate.get("allow_attack_50_ready"):
        return "等固定交易窗口内条件成立；未确认按0%不参与"
    return "保持空仓，不新增参与"


def _format_position_display(position_level):
    text = str(position_level or "").strip()
    if text == "0%不参与" or "空仓" in text:
        return "0%不参与"
    if "防守" in text:
        return "0%不参与"
    if text == "50%条件执行" or "50%" in text or "进攻" in text:
        return "50%条件执行"
    return text or "0%不参与"


def _is_ten_confirm_upgrade_candidate(candidate):
    candidate = candidate or {}
    if _candidate_has_incomplete_action_trace(candidate):
        return False
    text = " ".join(
        str(candidate.get(key, "") or "")
        for key in (
            "permission_label",
            "watch_anchor_type",
            "conviction_reason",
            "reason",
            "core_level",
            "watch_anchor_note",
        )
    )
    minute_plan = candidate.get("minute_plan") or {}
    return bool(
        minute_plan.get("confirm_price_60m")
        and (
            any(marker in text for marker in ("重点观察名单", "重点观察权", "重点观察确认"))
            or "极看" in text
            or "极度看好" in text
            or "板块锚定龙" in text
            or "首波先锋" in text
            or "主线核心" in text
        )
    )


def _candidate_has_incomplete_action_trace(candidate):
    candidate = candidate or {}
    if candidate.get("missing_data"):
        return True
    trace_values = []
    for key in ("trace", "candidate_trace", "quality_trace"):
        trace_values.extend(_flatten_trace_texts(candidate.get(key)))
    for key in ("checks", "final_action", "branch_result", "branch_path", "missing_reason", "reason", "action"):
        trace_values.extend(_flatten_trace_texts(candidate.get(key)))
    text = "；".join(trace_values)
    return "关键数据不完整" in text or "数据缺失" in text


def _flatten_trace_texts(value):
    if isinstance(value, dict):
        texts = []
        for item in value.values():
            texts.extend(_flatten_trace_texts(item))
        return texts
    if isinstance(value, (list, tuple, set)):
        texts = []
        for item in value:
            texts.extend(_flatten_trace_texts(item))
        return texts
    return [str(value or "")]


def _candidate_key(candidate):
    candidate = candidate or {}
    return str(candidate.get("code") or candidate.get("stock_code") or candidate.get("代码") or candidate.get("name") or candidate.get("名称") or "").strip()


def _trace_code(trace):
    trace = trace or {}
    return _candidate_key(trace)


def _incomplete_trace_codes_from_artifact(artifact):
    payload = artifact.get("payload") if isinstance(artifact, dict) else {}
    if not isinstance(payload, dict):
        payload = {}
    traces = artifact.get("traces") if isinstance(artifact, dict) else []
    if not traces:
        traces = payload.get("traces") or []
    codes = set()
    for trace in traces or []:
        if not isinstance(trace, dict):
            continue
        if _candidate_has_incomplete_action_trace(trace) or trace.get("missing_data"):
            code = _trace_code(trace)
            if code:
                codes.add(code)
    return codes


def _actionable_observation_candidates(candidates, incomplete_trace_codes=None):
    incomplete_trace_codes = set(incomplete_trace_codes or set())
    return [
        candidate
        for candidate in list(candidates or [])
        if not _candidate_has_incomplete_action_trace(candidate)
        and _candidate_key(candidate) not in incomplete_trace_codes
    ]


def _surface_observation_candidates(candidates):
    return [
        candidate
        for candidate in list(candidates or [])
        if candidate_can_be_current_observation_target(candidate)
    ]


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


def _final_target_empty_without_current_observation(context):
    if _selection_workflow_final_is_empty(context):
        return True
    if _final_resolution_waits_without_watch_target(context):
        return True
    workflow = _selection_workflow_from_context(context)
    if not workflow:
        return False
    final = workflow.get("final") if isinstance(workflow.get("final"), dict) else {}
    if "final" not in workflow:
        return False
    execution_object = final.get("execution_object") if isinstance(final.get("execution_object"), dict) else {}
    position_pct = _position_pct(final.get("position_pct"))
    if position_pct > 0 and _candidate_key(execution_object):
        return False
    return not bool(_selection_workflow_front_observation_target(workflow))


def _selection_workflow_final_is_empty(context):
    workflow = _selection_workflow_from_context(context)
    if not workflow:
        return False
    final = workflow.get("final") if isinstance(workflow.get("final"), dict) else {}
    if "final" not in workflow:
        return False
    execution_object = final.get("execution_object") if isinstance(final.get("execution_object"), dict) else {}
    position_pct = _position_pct(final.get("position_pct"))
    return position_pct <= 0 or not bool(_candidate_key(execution_object))


def _final_resolution_waits_without_watch_target(context):
    resolution = (context or {}).get("final_target_resolution")
    if not isinstance(resolution, dict):
        return False
    decision = resolution.get("capital_priority_decision") if isinstance(resolution.get("capital_priority_decision"), dict) else {}
    if str(decision.get("capital_priority") or "").strip() != "wait":
        return False
    return not candidate_can_be_current_observation_target(resolution.get("watch_target"))


def _selection_workflow_from_context(context):
    sources = [context]
    if isinstance(context, dict):
        sources.extend([context.get("market_research_snapshot"), context.get("execution_stage_context")])
    for source in sources:
        if not isinstance(source, dict):
            continue
        workflow = source.get("selection_workflow")
        if isinstance(workflow, dict) and workflow.get("schema_version") == "selection_workflow.v1":
            return workflow
    return {}


def _position_pct(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _selection_workflow_front_observation_target(workflow):
    workflow = workflow if isinstance(workflow, dict) else {}
    for candidate in workflow.get("candidate_pool", []) or []:
        if not isinstance(candidate, dict):
            continue
        if candidate.get("front_observation_qualified") is not True:
            continue
        if not candidate_can_be_current_observation_target(candidate):
            continue
        stock = candidate.get("stock") if isinstance(candidate.get("stock"), dict) else candidate
        if _candidate_key(stock):
            return stock
    return {}


def _prioritize_final_observation_anchor(context, candidates):
    target = _preferred_observation_target(context)
    target_key = _candidate_key(target)
    if not target_key:
        return list(candidates or [])
    matched = []
    remaining = []
    for candidate in list(candidates or []):
        if _candidate_key(candidate) == target_key:
            matched.append(candidate)
        else:
            remaining.append(candidate)
    if matched:
        return matched + remaining
    return [target] + remaining


ACTION_PLAN_CONTEXT_EXPORT_KEYS = (
    "action_rows",
    "observation_priority_lines",
    "backup_observation_lines",
    "position_section_lines",
    "pre_market_lines",
    "opening_lines",
    "first_hour_lines",
    "intraday_lines",
    "closing_lines",
    "alert_rows",
    "action_plan_context_diagnostics",
)


def _build_action_plan_context_diagnostics(
    *,
    action_rows,
    observation_priority_lines,
    backup_observation_lines,
    alert_rows,
    daily_new_entry_limit,
    best_stock,
    watch_anchor,
):
    return {
        "source": "pk_decision",
        "action_row_count": len(action_rows),
        "observation_priority_count": len(observation_priority_lines),
        "backup_observation_count": len(backup_observation_lines),
        "alert_count": len(alert_rows),
        "daily_new_entry_limit": daily_new_entry_limit,
        "has_best_stock": bool(best_stock),
        "has_watch_anchor": bool(watch_anchor),
        "degraded": not bool(action_rows),
    }


def _empty_final_action_row():
    return {
        "action": "暂无执行预案",
        "name": "-",
        "code": "-",
        "trigger": "当前最终对象为空，只回放过程候选，不新增参与",
        "risk_window": "-",
    }


def _clear_current_object_payload_for_empty_final(payload):
    updated = dict(payload or {})
    updated["action_rows"] = [_empty_final_action_row()]
    updated["observation_priority_lines"] = []
    updated["backup_observation_lines"] = []
    diagnostics = dict(updated.get("action_plan_context_diagnostics") or {})
    diagnostics["action_row_count"] = 1
    diagnostics["observation_priority_count"] = 0
    diagnostics["backup_observation_count"] = 0
    diagnostics["degraded"] = True
    diagnostics["final_target_empty"] = True
    updated["action_plan_context_diagnostics"] = diagnostics
    return updated


def _sanitize_action_plan_context_payload(payload, context=None):
    payload = dict(payload or {})
    if _final_target_empty_without_current_observation(context or {}):
        payload = _clear_current_object_payload_for_empty_final(payload)
    sanitized = {}
    for key in ACTION_PLAN_CONTEXT_EXPORT_KEYS:
        if key not in payload:
            continue
        value = payload.get(key)
        if key == "action_plan_context_diagnostics":
            sanitized[key] = dict(value or {})
        elif key == "alert_rows":
            sanitized[key] = list(value or [])
        else:
            sanitized[key] = sanitize_user_visible_text(value)
    return sanitized


def build_action_plan_context_payload(context):
    context = context or {}
    existing_payload = context.get("action_plan_context_payload")
    if existing_payload is not None:
        return _sanitize_action_plan_context_payload(existing_payload, context=context)

    trade_gate_open = context.get("trade_gate_open", False)
    best_stock = context.get("best_stock")
    watch_anchor = context.get("watch_anchor")
    watch_anchor_type = context.get("watch_anchor_type", "")
    position_level = str(context.get("position_level", "") or "").strip()
    step0_prediction = str(context.get("step0_prediction", "") or "").strip()
    step0_prediction_cn = str(context.get("step0_prediction_cn", "") or "").strip()
    final_gate = context.get("final_gate", {}) or {}
    has_personal_positions = bool(context.get("has_personal_positions", False))
    final_empty_without_current_observation = _final_target_empty_without_current_observation(context)
    if final_empty_without_current_observation:
        best_stock = None
        watch_anchor = None
    display_observation_candidates = context.get("display_observation_candidates", context.get("observation_candidates", [])) or []
    display_observation_candidates = _prioritize_final_observation_anchor(context, display_observation_candidates)
    blocked_observation_keys = blocked_current_observation_keys(display_observation_candidates)
    display_observation_candidates = _surface_observation_candidates(display_observation_candidates)
    if final_empty_without_current_observation:
        display_observation_candidates = []
    if not candidate_can_be_current_observation_target(watch_anchor) or _candidate_key(watch_anchor) in blocked_observation_keys:
        watch_anchor = None
    incomplete_trace_codes = _incomplete_trace_codes_from_artifact(context.get("candidate_trace_artifact") or {})
    actionable_observation_candidates = _actionable_observation_candidates(
        display_observation_candidates,
        incomplete_trace_codes,
    )
    waiting_stocks = context.get("waiting_stocks", []) or []
    if final_empty_without_current_observation:
        waiting_stocks = []
    today_predictions = context.get("today_predictions", []) or []
    nextday_predictions = context.get("nextday_predictions", []) or []

    build_trade_price_focus = context.get("build_trade_price_focus", lambda minute_plan, stop_plan: {})
    build_observation_price_focus_text = context.get("build_observation_price_focus_text", lambda price_focus: "-")
    append_watch_anchor_note = context.get("append_watch_anchor_note", lambda report_lines, candidate, prefix="  ": None)
    append_observation_price_focus_note = context.get(
        "append_observation_price_focus_note",
        lambda report_lines, price_focus, prefix="  ": None,
    )
    compose_observation_focus_text = context.get(
        "compose_observation_focus_text",
        lambda confirm_text, observation_price_focus_text: f"{confirm_text} / {observation_price_focus_text}",
    )
    build_stop_execution_plan = context.get("build_stop_execution_plan", lambda *args, **kwargs: {})
    build_candidate_exit_rules = context.get("build_candidate_exit_rules", lambda candidate, stop_plan=None: {})
    format_holding_window_text = context.get("format_holding_window_text", lambda min_days, max_days: "")
    get_execution_framework_text = context.get("get_execution_framework_text", lambda: "")
    ten_confirm_upgrade_candidate = next(
        (candidate for candidate in actionable_observation_candidates if _is_ten_confirm_upgrade_candidate(candidate)),
        None,
    )
    old_position_first = bool(final_gate.get("should_reduce") and has_personal_positions)
    can_ten_confirm_upgrade = (not old_position_first) and bool(final_gate.get("allow_attack_50_ready") or ten_confirm_upgrade_candidate)
    observation_anchor = display_observation_candidates[0] if display_observation_candidates else watch_anchor
    quality_backup_anchor = watch_anchor if best_stock else observation_anchor
    scorecard_context = dict(
        context,
        display_observation_candidates=display_observation_candidates,
        observation_candidates=display_observation_candidates,
        watch_anchor=quality_backup_anchor,
    )
    if (
        not candidate_can_be_current_observation_target(quality_backup_anchor)
        or _candidate_key(quality_backup_anchor) in blocked_observation_keys
    ):
        scorecard_context["watch_anchor"] = None
    scorecard_payload = build_candidate_quality_scorecard_payload(scorecard_context)
    if old_position_first:
        panel_fields = dict(scorecard_payload.get("candidate_quality_panel_fields") or {})
        panel_fields["daily_new_entry_limit"] = 0
        scorecard_payload["candidate_quality_panel_fields"] = sanitize_user_visible_text(panel_fields)
    daily_new_entry_limit = (
        scorecard_payload.get("candidate_quality_panel_fields", {}).get("daily_new_entry_limit", 0)
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
                    "trigger": f"明日09:50-10:10站上{confirm_price:.2f}" if confirm_price else "明日09:50-10:10窗口内满足条件后触发",
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
                        f"明日09:50-10:10站上{confirm_price:.2f}后按{best_stock.get('trigger', '条件')}执行"
                        if confirm_price
                        else f"明日09:50-10:10窗口内满足条件后按{best_stock.get('trigger', '条件')}执行"
                    ),
                    "risk_window": f"{(stop_plan or {}).get('summary', '先看失效价 / 最晚-5%')} / "
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
	                "action": "👀 明天只复盘哪只",
                "name": watch_anchor.get("name"),
                "code": watch_anchor.get("code"),
                "trigger": (
	                    f"09:50-10:10站上{confirm_price:.2f}后只记录承接，结果进入复盘和下一份日报判断"
	                    if confirm_price
	                    else "先看09:50-10:10窗口承接，结果进入复盘和下一份日报判断"
                ),
                "risk_window": f"{(price_focus or {}).get('key_zone_display', '-')} / "
                f"{format_holding_window_text(exit_rules.get('holding_days_min'), exit_rules.get('holding_days_max'))}",
            }
        )
    elif can_ten_confirm_upgrade and actionable_observation_candidates:
        candidate = ten_confirm_upgrade_candidate or actionable_observation_candidates[0] or {}
        minute_plan = candidate.get("minute_plan") or {}
        stop_plan = candidate.get("stop_plan")
        price_focus = build_trade_price_focus(minute_plan, stop_plan)
        confirm_price = minute_plan.get("confirm_price_60m")
        confirm_text = f"09:50-10:10站上{confirm_price:.2f}" if confirm_price else "09:50-10:10窗口内条件成立"
        action_rows.append(
            {
                "action": "⏳ 确认后执行预案",
                "name": candidate.get("name"),
                "code": candidate.get("code"),
                "trigger": f"{confirm_text}，且板块承接不塌，只按昨晚预案检查执行资格；不满足取消",
                "risk_window": (price_focus or {}).get("key_zone_display", "-"),
            }
        )
    else:
        action_rows.append(
            {
                "action": "❌ 明天没有可买对象",
                "name": "-",
                "code": "-",
                "trigger": _format_closed_gate_buy_limit_text(position_level, final_gate) if not trade_gate_open else "无符合条件标的",
                "risk_window": "-",
            }
        )

    observation_priority_lines = []
    if not trade_gate_open and display_observation_candidates:
        normalized_observation_candidates = []
        seen_observation_codes = set()
        for candidate in list(display_observation_candidates or []) + [context.get("watch_anchor")]:
            if not isinstance(candidate, dict):
                continue
            key = _candidate_key(candidate)
            if not key or key in seen_observation_codes:
                continue
            seen_observation_codes.add(key)
            normalized_observation_candidates.append(candidate)
        for candidate in normalized_observation_candidates[:3]:
            minute_plan = candidate.get("minute_plan") or {}
            stop_plan = candidate.get("stop_plan")
            price_focus = build_trade_price_focus(minute_plan, stop_plan)
            confirm_price = minute_plan.get("confirm_price_60m")
            confirm_text = f"{confirm_price:.2f}" if confirm_price else "待盘中确认"
            observation_price_focus_text = build_observation_price_focus_text(price_focus)
            observation_priority_lines.append(
                f"- 👀 {candidate.get('name')}({candidate.get('code')}) - "
                f"{candidate.get('watch_anchor_type', candidate.get('permission_label', '观察权'))}，"
                f"{normalize_trading_time_text(compose_observation_focus_text(confirm_text, observation_price_focus_text))}"
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
            f"{normalize_trading_time_text(compose_observation_focus_text(confirm_text, observation_price_focus_text))}"
        )
        append_observation_price_focus_note(backup_observation_lines, price_focus, prefix="  ")

    position_section_lines = [
        f"- **进攻仓位三态**: {_format_position_display(position_level)}",
        f"- **明日裁决**: {step0_prediction_cn}",
        f"- **怎么执行**: {normalize_trading_time_text(get_execution_framework_text())}",
    ]
    position_display = _format_position_display(position_level)
    if position_display == "0%不参与":
        if final_empty_without_current_observation:
            position_section_lines.extend(
                [
                    "- **现在到底是什么状态**: 0%不参与，不抢跑，候选只保留过程回看",
                    "- **明天仓位放多少**: 盘前0%；暂无新增参与资格，只观察风险是否钝化",
                    "- **明天具体怎么做**: 不新增参与；只看市场底色、主攻线承接和过程样本反馈",
                ]
            )
        elif can_ten_confirm_upgrade and display_observation_candidates:
            position_section_lines.extend(
                [
                    "- **现在到底是什么状态**: 0%不参与，禁止抢跑，但保留重点观察名单的盘中确认路径",
                    "- **明天仓位放多少**: 明日买入决定：不买新仓；观察对象只复盘，不参与",
                    "- **明天具体怎么做**: 09:50-10:10只看重点观察/主线核心是否主动证明自己，结果进入复盘和下一份日报判断，未命中继续0%",
                ]
            )
        else:
            position_section_lines.extend(
                [
                    "- **现在到底是什么状态**: 空仓",
                    "- **明天仓位放多少**: 0%（保持空仓）",
                    "- **明天具体怎么做**: 不新增参与；若有旧仓只处理旧仓，否则保持空仓",
                ]
            )
    else:
        if not best_stock:
            if watch_anchor:
                position_section_lines.extend(
                    [
                        "- **现在到底是什么状态**: 还没有缩到一只可买股",
	                        "- **明天仓位放多少**: 0%（明日买入决定：不买新仓）",
	                        "- **明天具体怎么做**: 只观察重点盯盘股承接，结果进入复盘和下一份日报判断",
                    ]
                )
            else:
                position_section_lines.extend(
                    [
                        "- **现在到底是什么状态**: 市场允许出手但还没有对象",
                        "- **明天仓位放多少**: 0%（没有标的可买）",
                        "- **明天具体怎么做**: 保持空仓，不做试错参与",
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
	                    "- **明天仓位放多少**: 已决定50%条件执行；盘中不满足取消，回到0%不参与",
	                    "- **明天具体怎么做**: 严格按昨晚预案检查执行资格，不追涨；不满足就转为0%",
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
                pre_market_lines.append(f"- **设价格预警**: {best_stock.get('name')}({best_stock.get('code')}) - 09:50-10:10站上{confirm_price:.2f}提醒")
            else:
                entry_range = best_stock.get("entry_range", (signal.entry_price, signal.entry_price))
                pre_market_lines.append(f"- **设价格预警**: {best_stock.get('name')}({best_stock.get('code')}) - 触及{entry_range[0]:.2f}-{entry_range[1]:.2f}提醒")
            if structure_stop_30m:
                pre_market_lines.append(f"- **风险预埋**: 若买入，先盯失效价{structure_stop_30m:.2f}")
        else:
            minute_plan = best_stock.get("minute_plan") or {}
            confirm_price = minute_plan.get("confirm_price_60m")
            pre_market_lines.append(
                f"- **关注标的**: {best_stock.get('name')}({best_stock.get('code')}) - "
                f"{'09:50-10:10站上' + format(confirm_price, '.2f') + '后按条件触发' if confirm_price else '按条件触发'}"
            )
    elif observation_anchor:
        minute_plan = observation_anchor.get("minute_plan") or {}
        stop_plan = observation_anchor.get("stop_plan")
        price_focus = build_trade_price_focus(minute_plan, stop_plan)
        confirm_price = minute_plan.get("confirm_price_60m")
        confirm_text = f"{confirm_price:.2f}" if confirm_price else "待盘中确认"
        observation_price_focus_text = build_observation_price_focus_text(price_focus)
        anchor_type = observation_anchor.get("watch_anchor_type") or watch_anchor_type or "观察对象"
        pre_market_lines.append(
            f"- **{anchor_type}**: {observation_anchor.get('name')}({observation_anchor.get('code')}) - "
            f"{normalize_trading_time_text(compose_observation_focus_text(confirm_text, observation_price_focus_text))}"
        )
        append_watch_anchor_note(pre_market_lines, observation_anchor)
        append_observation_price_focus_note(pre_market_lines, price_focus)
    else:
        pre_market_lines.append("- **空仓准备**: 无操作标的，准备观望")
    pre_market_lines.extend(["- 查看隔夜消息、外围市场、期货走势", "- 确认A杀冷却池无变化"])

    opening_lines = [
        "- 观察涨跌比、昨日涨停溢价率",
        "- 重新评估Step 0裁决是否仍然成立",
    ]
    if final_empty_without_current_observation:
        opening_lines.extend(
            [
                "- 只观察主攻线承接和过程样本反馈，不把竞价强弱转成新增参与",
                "- 若竞价表态和开盘承接同时成立，也只记为过程证据；不新增参与",
            ]
        )
    else:
        opening_lines.extend(
            [
                "- 观察唯一对象的竞价表态、匹配金额、委托稳定和板块同步",
                "- 若竞价表态和开盘前几分钟承接同时成立，按09:30-09:35窗口处理；不成立回到0%",
            ]
        )
    if trade_gate_open and best_stock:
        first_hour_lines = [
            "- 竞价/开盘前几分钟未触发时，只等09:50-10:10窗口内条件成立",
            "- 直接高开离计划过远且没有回封/承接方案 → 放弃，等新的买点",
        ]
        intraday_lines = [
            "- 竞价表态、开盘承接、打板/回封或09:50-10:10窗口任一路径命中，且大盘不崩 → 按预设仓位执行",
            "- 买入后按失效价和单笔-5%底线处理风险；若失效价过深，则直接用单笔-5%底线",
            "- 跌破执行止损线 → 无条件止损",
        ]
    elif trade_gate_open and watch_anchor:
	        first_hour_lines = [
	            "- 市场允许出手，但当前没有当晚已决定的执行对象，本时段只观察重点盯盘股承接",
	            "- 重点盯盘股即使继续抗跌，也只进入复盘和下一份日报判断",
	        ]
	        intraday_lines = [
	            "- 继续只盯观察对象，不做多票分散",
	            "- 它如果始终不能证明强于市场 → 当天继续等待，不抢跑",
            "- 若候选盘中直接走坏或失守关键位/带 → 取消它的执行资格",
        ]
    else:
        if can_ten_confirm_upgrade:
            if final_empty_without_current_observation:
                first_hour_lines = [
                    "- 当前是0%不参与，本时段只观察主线核心是否继续证明承接",
                    "- 重点观察优先对象是否继续走强；确认后也只保留观察，未确认保持0%",
                ]
                intraday_lines = [
                    "- 以观察和处理持仓为主；不新增参与",
                    "- 若你有仓位，失效价失守或日内明显转弱 → 执行减仓/止损",
                    "- 若观察标的全天未形成更强确认 → 继续等待",
                ]
            else:
                first_hour_lines = [
                    "- 当前是0%不参与，本时段只观察主线核心是否在固定交易窗口内满足条件",
                    "- 重点观察优先对象是否继续走强；确认后也只进入复盘和下一份日报判断，未确认保持0%",
                ]
                intraday_lines = [
                    "- 以观察和处理持仓为主；新仓只按昨晚日报已决定的对象执行或取消",
                    "- 若你有仓位，失效价失守或日内明显转弱 → 执行减仓/止损",
                    "- 若观察标的全天未形成更强确认 → 继续等待",
                ]
        else:
            first_hour_lines = [
                "- 当前条件不允许新开仓，本时段只确认环境是否继续支持持仓/观察",
                "- 重点观察优先对象是否继续走强；若你有旧仓，只处理旧仓，不做新增",
            ]
            intraday_lines = [
                "- 以观察和处理持仓为主，不做新开仓",
                "- 若你有仓位，失效价失守或日内明显转弱 → 执行减仓/止损",
                "- 若观察标的全天未形成更强确认 → 继续等待",
            ]

    closing_lines = ["- 未买入的保持观望"]
    if trade_gate_open and best_stock:
        closing_lines.append("- 已买入的确认风险线是否需要上移")
    else:
        closing_lines.append("- 若你有旧仓，确认风险线是否需要上移")

    alert_rows = []
    for pred in today_predictions[:3]:
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
    for pred in nextday_predictions[:2]:
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

    payload = {
        "action_rows": sanitize_user_visible_text(action_rows),
        "observation_priority_lines": sanitize_user_visible_text(observation_priority_lines),
        "backup_observation_lines": sanitize_user_visible_text(backup_observation_lines),
        "position_section_lines": sanitize_user_visible_text(position_section_lines),
        "pre_market_lines": sanitize_user_visible_text(pre_market_lines),
        "opening_lines": sanitize_user_visible_text(opening_lines),
        "first_hour_lines": sanitize_user_visible_text(first_hour_lines),
        "intraday_lines": sanitize_user_visible_text(intraday_lines),
        "closing_lines": sanitize_user_visible_text(closing_lines),
        "alert_rows": alert_rows,
        "action_plan_context_diagnostics": _build_action_plan_context_diagnostics(
            action_rows=action_rows,
            observation_priority_lines=observation_priority_lines,
            backup_observation_lines=backup_observation_lines,
            alert_rows=alert_rows,
            daily_new_entry_limit=daily_new_entry_limit,
            best_stock=best_stock,
            watch_anchor=watch_anchor,
        ),
        **scorecard_payload,
    }
    return payload


def build_pk_decision_action_plan_context_node(context, node_meta=None, node_lookup=None):
    payload = build_action_plan_context_payload(context)
    return {
        "lines": [],
        "exports": payload,
        "module_logs": [
            {
                "module": "domains.execution_chain.pk_decision_nodes.action_plan_context",
                "step": "build.action_plan_context",
                "status": "success",
                "message": "已生成明日操作计划上下文",
                "details": payload.get("action_plan_context_diagnostics", {}),
            }
        ],
    }
