from report.candidate_quality_renderer import COMPACT_CANDIDATE_TABLE_FIELDS, render_candidate_quality_section
from report.sniper_target_derivation import (
    build_sniper_target_derivation_packet,
    compact_section as _sniper_target_derivation_compact_section,
)
from domains.execution_chain.pk_decision_nodes.candidate_quality_scorecard import build_candidate_quality_scorecard_payload
from domains.execution_chain.pk_decision_nodes.candidate_surface_filter import (
    candidate_blocks_current_observation_target,
    candidate_can_be_current_observation_target,
    candidate_identity_keys,
    candidate_matches_any_key,
)
from selection.candidate_quality_contracts import (
    build_daily_quality_decision_panel,
    evaluate_candidate_quality_sample_contract,
)
from selection.candidate_trace_contracts import build_eliminated_summary


_PROCESS_EVIDENCE_TITLES = {
    "候选质量与动作分层",
    "今日总决策面板",
    "候选主表",
    "最终标的传导链",
    "狙击手最终标的路径图",
    "候选选股轨迹",
    "候选选股轨迹明细",
    "未进入分层原因统计",
    "单票展开",
}


def _mark_process_evidence_headings(lines):
    marked = []
    for line in lines or []:
        text = str(line or "")
        stripped = text.strip()
        heading_match = stripped.split(" ", 1)
        if len(heading_match) == 2 and heading_match[0].startswith("#") and set(heading_match[0]) == {"#"}:
            title = heading_match[1]
            if title in _PROCESS_EVIDENCE_TITLES:
                hashes = heading_match[0]
                text = f"{hashes} {title}（过程证据）"
        marked.append(text)
    return marked


def _trace_code(trace):
    trace = trace or {}
    return str(trace.get("stock_code") or trace.get("code") or trace.get("代码") or "").strip()


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


def _incomplete_trace_codes(traces):
    codes = set()
    for trace in traces or []:
        if not isinstance(trace, dict):
            continue
        text = "；".join(_flatten_trace_texts(trace))
        if trace.get("missing_data") or "关键数据不完整" in text or "数据缺失" in text:
            code = _trace_code(trace)
            if code:
                codes.add(code)
    return codes


def _trace_structured_score(trace):
    trace = trace or {}
    score = 0
    for key in ("tier", "mainline", "sector", "sector_name", "trigger_condition", "failure_condition"):
        if str(trace.get(key) or "").strip():
            score += 1
    anchor_reversal = trace.get("anchor_reversal") or {}
    if isinstance(anchor_reversal, dict):
        score += sum(1 for value in anchor_reversal.values() if str(value or "").strip())
    checks = trace.get("checks") or []
    if isinstance(checks, list):
        score += sum(
            1
            for check in checks
            if isinstance(check, dict) and str(check.get("result") or "").strip() not in {"", "数据缺失"}
        )
    return score


def _trace_collection_score(traces):
    return sum(_trace_structured_score(trace) for trace in traces or [] if isinstance(trace, dict))


def _select_candidate_traces(existing_traces, contract_traces):
    existing_traces = list(existing_traces or [])
    contract_traces = list(contract_traces or [])
    if not existing_traces:
        return contract_traces
    if not contract_traces:
        return existing_traces
    if _trace_collection_score(contract_traces) > _trace_collection_score(existing_traces):
        return contract_traces
    return existing_traces


def _contracts_with_selected_traces(contracts, traces):
    traces_by_code = {
        _trace_code(trace): trace
        for trace in traces or []
        if isinstance(trace, dict) and _trace_code(trace)
    }
    rendered_contracts = []
    for contract in contracts or []:
        if not isinstance(contract, dict):
            rendered_contracts.append(contract)
            continue
        trace = traces_by_code.get(_trace_code(contract.get("trace") or {}))
        if not trace:
            rendered_contracts.append(contract)
            continue
        updated = dict(contract)
        updated["trace"] = trace
        rendered_contracts.append(updated)
    return rendered_contracts


def _candidate_quality_derivation_packet(context):
    packet = context.get("sniper_target_derivation")
    if isinstance(packet, dict) and packet.get("canonical_target"):
        return packet
    if not isinstance(context.get("final_target_resolution"), dict):
        return {}
    return build_sniper_target_derivation_packet(
        data=context,
        execution_stage_context=context.get("execution_stage_context") if isinstance(context.get("execution_stage_context"), dict) else {},
        market_research_snapshot=context,
        final_target_resolution=context.get("final_target_resolution"),
        selected_position_candidate=context.get("selected_position_candidate"),
        position_decision=context.get("position_decision"),
        final_gate=context.get("final_gate"),
        two_layer_decision_payload=context.get("two_layer_decision_payload"),
    )


def _candidate_key(candidate):
    candidate = candidate or {}
    return str(candidate.get("code") or candidate.get("stock_code") or candidate.get("代码") or candidate.get("name") or candidate.get("名称") or "").strip()


def _filtered_candidate_quality_panel_fields(panel_fields, candidate_samples=None):
    updated = dict(panel_fields or {})
    blocked_keys = {
        key
        for candidate in list(candidate_samples or [])
        if candidate_blocks_current_observation_target(candidate)
        for key in candidate_identity_keys(candidate)
    }
    for key in ("primary_buy_candidate", "backup_candidate"):
        candidate = updated.get(key)
        if candidate_blocks_current_observation_target(candidate) or candidate_matches_any_key(candidate, blocked_keys):
            updated[key] = None
    return updated


def _final_resolution_waits_without_watch_target(context):
    if _selection_workflow_final_is_empty(context):
        return True
    resolution = (context or {}).get("final_target_resolution")
    if not isinstance(resolution, dict):
        return _selection_workflow_final_empty_without_watch_target(context)
    decision = resolution.get("capital_priority_decision") if isinstance(resolution.get("capital_priority_decision"), dict) else {}
    if str(decision.get("capital_priority") or "").strip() != "wait":
        return _selection_workflow_final_empty_without_watch_target(context)
    if _position_pct(((context or {}).get("position_decision") or {}).get("target_position_pct")) <= 0:
        return True
    watch_target = resolution.get("watch_target")
    return not candidate_can_be_current_observation_target(watch_target)


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


def _selection_workflow_final_empty_without_watch_target(context):
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
        if candidate_blocks_current_observation_target(candidate):
            continue
        stock = candidate.get("stock") if isinstance(candidate.get("stock"), dict) else candidate
        if _candidate_key(stock):
            return stock
    return {}


def _clear_candidate_quality_panel_target_fields(panel_fields):
    updated = dict(panel_fields or {})
    updated["primary_buy_candidate"] = None
    updated["backup_candidate"] = None
    return updated


def _candidate_label(candidate):
    candidate = candidate or {}
    name = str(candidate.get("name") or candidate.get("stock_name") or candidate.get("名称") or "").strip()
    code = str(candidate.get("code") or candidate.get("stock_code") or candidate.get("代码") or "").strip()
    if name and code:
        return f"{name}({code})"
    return name or code


def _candidate_quality_panel_filter_candidates(context, contracts):
    candidates = list((context or {}).get("candidate_quality_samples") or [])
    for contract in list(contracts or []):
        if not isinstance(contract, dict):
            continue
        data = contract.get("data") if isinstance(contract.get("data"), dict) else {}
        candidate = data.get("candidate")
        if isinstance(candidate, dict):
            candidates.append(candidate)
    return candidates


def _filtered_candidate_quality_panel(panel, candidate_samples=None):
    if not isinstance(panel, dict):
        return panel
    data = panel.get("data") if isinstance(panel.get("data"), dict) else {}
    if data:
        filtered = _filtered_candidate_quality_panel_fields(data, candidate_samples)
        return build_daily_quality_decision_panel(
            market_emotion_label=filtered.get("market_emotion_label", ""),
            account_attention_load=filtered.get("account_attention_load", ""),
            holding_priority_action=filtered.get("holding_priority_action", ""),
            daily_new_entry_limit=filtered.get("daily_new_entry_limit", 0),
            primary_buy_candidate=filtered.get("primary_buy_candidate"),
            backup_candidate=filtered.get("backup_candidate"),
            forbidden_actions=filtered.get("forbidden_actions"),
            ignored_noise_items=filtered.get("ignored_noise_items"),
        )

    blocked_labels = {
        _candidate_label(candidate)
        for candidate in list(candidate_samples or [])
        if candidate_blocks_current_observation_target(candidate)
    }
    if not blocked_labels:
        return panel
    visible_fields = dict(panel.get("visible_fields") or {})
    for field in ("主买对象", "补位对象"):
        if str(visible_fields.get(field) or "").strip() in blocked_labels:
            visible_fields[field] = "暂无"
    return {**panel, "visible_fields": visible_fields}


def build_action_plan_overview_node(context, node_meta=None, node_lookup=None):
    section_title = str(context.get("section_title", "") or "明日操作计划").strip() or "明日操作计划"
    return {
        "lines": [
            f"#### {section_title}",
            "> **先看结论**：明天只执行唯一动作，或者只观察。",
            "> **怎么执行**：按盘前、09:30-09:35、09:50-10:10、盘中观察、14:30-14:55顺序，不临场改单。",
            "",
        ],
        "exports": {},
        "module_logs": [],
    }


def build_action_plan_candidate_quality_node(context, node_meta=None, node_lookup=None):
    context = context or {}
    if not context.get("candidate_quality_panel") and not context.get("candidate_quality_contracts"):
        if isinstance(context.get("sniper_target_derivation"), dict) or isinstance(context.get("final_target_resolution"), dict):
            context = {**context, **build_candidate_quality_scorecard_payload(context)}
    panel = context.get("candidate_quality_panel")
    contracts = context.get("candidate_quality_contracts") or []
    enabled_node_keys = set(context.get("enabled_node_keys") or [])
    heading_level = 5 if not enabled_node_keys or "overview" in enabled_node_keys else 2
    if not contracts and context.get("candidate_quality_samples"):
        contracts = [
            evaluate_candidate_quality_sample_contract(candidate)
            for candidate in context.get("candidate_quality_samples")
        ]
    filter_candidates = _candidate_quality_panel_filter_candidates(context, contracts)
    if panel:
        if _final_resolution_waits_without_watch_target(context):
            data = panel.get("data") if isinstance(panel, dict) and isinstance(panel.get("data"), dict) else {}
            if data:
                panel = build_daily_quality_decision_panel(
                    **_clear_candidate_quality_panel_target_fields(data)
                )
        panel = _filtered_candidate_quality_panel(panel, filter_candidates)
    if not panel and context.get("candidate_quality_panel_fields"):
        panel_fields = context.get("candidate_quality_panel_fields")
        if _final_resolution_waits_without_watch_target(context):
            panel_fields = _clear_candidate_quality_panel_target_fields(panel_fields)
        panel = build_daily_quality_decision_panel(
            **_filtered_candidate_quality_panel_fields(
                panel_fields,
                filter_candidates,
            )
        )
    if not panel:
        return {"lines": [], "exports": {}, "module_logs": []}
    eliminated_summary = context.get("candidate_trace_eliminated_summary")
    if eliminated_summary is None:
        eliminated_summary = build_eliminated_summary(context.get("candidate_trace_eliminated_items") or [])
    render_trace_tables_value = context.get("render_candidate_trace_tables", True)
    render_trace_tables = True if render_trace_tables_value is None else bool(render_trace_tables_value)
    contract_traces = [
        contract.get("trace")
        for contract in contracts
        if isinstance(contract, dict) and contract.get("trace")
    ]
    traces = _select_candidate_traces(context.get("candidate_traces") or [], contract_traces)
    rendered_contracts = _contracts_with_selected_traces(contracts, traces)
    rendered_lines = render_candidate_quality_section(
        panel,
        rendered_contracts,
        heading_level=heading_level,
        table_fields=COMPACT_CANDIDATE_TABLE_FIELDS,
        render_trace_tables=render_trace_tables,
        eliminated_summary=eliminated_summary,
        final_target_empty=_final_resolution_waits_without_watch_target(context),
    ).splitlines()
    derivation_packet = _candidate_quality_derivation_packet(context)
    derivation_lines = []
    if isinstance(derivation_packet, dict) and derivation_packet.get("canonical_target"):
        derivation_lines = _sniper_target_derivation_compact_section(
            derivation_packet,
            heading=f"{'#' * min(6, heading_level + 1)} 最终标的传导链",
        )
    if derivation_lines:
        insert_at = 0
        for index, line in enumerate(rendered_lines):
            if "候选主表" in str(line):
                insert_at = index
                while insert_at > 0 and str(rendered_lines[insert_at - 1]).strip() == "":
                    insert_at -= 1
                break
        rendered_lines = rendered_lines[:insert_at] + derivation_lines + [""] + rendered_lines[insert_at:]
    return {
        "lines": _mark_process_evidence_headings(rendered_lines),
        "exports": {
            "candidate_traces": traces,
            "candidate_trace_eliminated_summary": eliminated_summary,
        },
        "module_logs": [],
    }


def build_action_plan_table_node(context, node_meta=None, node_lookup=None):
    lines = [
        "**最终动作表**（只展示真正具备参与资格的对象）:",
        "",
        "| 明天具体怎么做 | 股票 | 代码 | 触发条件 | 止损/时间 |",
        "|----------|------|------|----------|-----------|",
    ]
    if _final_resolution_waits_without_watch_target(context):
        lines.append("| 暂无执行预案 | - | - | 当前最终对象为空，只回放过程候选，不新增参与 | - |")
        lines.append("")
        return {"lines": lines, "exports": {}, "module_logs": []}
    blocked_codes = _incomplete_trace_codes(context.get("candidate_traces") or [])
    action_rows = [
        row
        for row in (context.get("action_rows") or [])
        if str(row.get("code") or "").strip() not in blocked_codes
    ]
    if action_rows:
        for row in action_rows:
            lines.append(
                f"| {row.get('action', '-')} | {row.get('name', '-')} | {row.get('code', '-')} | "
                f"{row.get('trigger', '-')} | {row.get('risk_window', '-')} |"
            )
    else:
        lines.append("| ❌ 明天没有可买对象 | - | - | 无符合条件标的 | - |")
    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_action_plan_observation_blocks_node(context, node_meta=None, node_lookup=None):
    if _final_resolution_waits_without_watch_target(context):
        return {"lines": [], "exports": {}, "module_logs": []}
    lines = []
    for block_title, block_lines in (
        ("**先看顺序**（优先盯最能反映主线承接的对象）:", context.get("observation_priority_lines") or []),
        ("**备用观察**（买点未触发，明日不操作）:", context.get("backup_observation_lines") or []),
    ):
        if block_lines:
            lines.append(block_title)
            lines.extend(block_lines)
            lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_action_plan_positioning_node(context, node_meta=None, node_lookup=None):
    lines = ["**明天仓位怎么放**:"]
    lines.extend(context.get("position_section_lines") or [])
    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_action_plan_schedule_node(context, node_meta=None, node_lookup=None):
    lines = ["**明日执行时间表**:", ""]
    schedule_sections = [
        ("**盘前准备（08:30-09:15）**:", context.get("pre_market_lines") or []),
        ("**竞价表态与开盘买卖窗口（09:20-09:35，买卖只在09:30-09:35）**:", context.get("opening_lines") or []),
        ("**09:50-10:10买卖窗口（09:50-10:10）**:", context.get("first_hour_lines") or []),
        ("**盘中观察（非买卖窗口）**:", context.get("intraday_lines") or []),
        ("**尾盘买卖窗口（14:30-14:55）**:", context.get("closing_lines") or []),
    ]
    for title, section_lines in schedule_sections:
        lines.append(title)
        lines.extend(section_lines)
        lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_action_plan_alerts_node(context, node_meta=None, node_lookup=None):
    alert_rows = context.get("alert_rows") or []
    if not alert_rows:
        return {"lines": [], "exports": {}, "module_logs": []}

    lines = ["**⚠️ 异动预警**:", "| 股票 | 偏离天数 | 触发条件 | 实际涨幅 | 状态 |", "|------|----------|----------|----------|------|"]
    for row in alert_rows:
        lines.append(
            f"| {row.get('name', '-')}({row.get('code', '-')}) | {row.get('deviation_days', 0)}天 | "
            f"{row.get('trigger_info', '-')} | {row.get('actual_change_str', '-')} | {row.get('trigger_status', '-')} |"
        )
    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}
