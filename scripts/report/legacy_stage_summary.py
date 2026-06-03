from report.legacy_stage_summary_node_registry import build_legacy_stage_summary_node_specs
from report.legacy_stage_summary_node_runtime import run_legacy_stage_summary_nodes
from report.conclusion_support import (
    build_candidate_trade_directive,
    build_focus_recap_text,
    build_market_outlook_text,
    build_risk_trade_note,
    derive_trade_style,
    get_watch_anchor_note,
    resolve_selected_position_candidate,
    resolve_today_focus_items,
    selected_target_is_attack_ready,
)


def _row(stage_key, title, guidance):
    return {
        "stage_key": stage_key,
        "title": title,
        "guidance": guidance,
    }


def _resolve_stage_meta(context):
    stage_meta_map = {}
    for item in context.get("report_stages") or []:
        if not isinstance(item, dict):
            continue
        raw_key = str(item.get("stage_key", "") or "").strip()
        if not raw_key:
            continue
        mapped_key = {
            "environment_follow": "market_environment",
            "watch_pool": "selection_focus",
            "candidate_selection": "candidate_selection",
            "risk_review": "risk_review",
            "entry_plan": "execution_plan",
            "pk_decision": "decisive_choice",
        }.get(raw_key, raw_key)
        stage_meta_map[mapped_key] = {**item, "stage_key": mapped_key}
    return stage_meta_map


def _resolve_stage_title(stage_meta, default_title):
    if stage_meta is not None and stage_meta.get("use_dynamic_title") is False:
        return default_title
    title = str((stage_meta or {}).get("title", "") or "").strip()
    return title or default_title


def _build_environment_row(context, stage_meta=None):
    report_stages = context.get("report_stages") or []
    environment_stage = next((item for item in report_stages if item.get("stage_key") == "market_environment"), None) or {}
    if stage_meta:
        environment_stage = stage_meta
    summary = str(environment_stage.get("summary", "") or "").strip()
    if context.get("prefer_data_driven_stage_rows") or not summary:
        summary = build_market_outlook_text(context)
    summary = summary or "-"
    return _row("market_environment", _resolve_stage_title(stage_meta, "环境与跟随裁决"), summary)


def _build_selection_row(context, stage_meta=None):
    watchlist_count = int(context.get("watchlist_count", 0) or 0)
    guidance = f"{watchlist_count}只"
    focus_text = build_focus_recap_text(context)
    if (
        resolve_selected_position_candidate(context)
        or context.get("best_stock")
        or resolve_today_focus_items(context)
    ) and focus_text:
        guidance = focus_text
    return _row("selection_focus", _resolve_stage_title(stage_meta, "明天观察池"), guidance)


def _build_probe_row(context, stage_meta=None):
    probe_parts = context.get("abnormal_probe_parts") or []
    if not probe_parts:
        return None
    return _row("anomaly_probe", _resolve_stage_title(stage_meta, "异常探针"), "；".join(probe_parts))


def _build_candidate_row(context, stage_meta=None):
    core_count = int(context.get("core_count", 0) or 0)
    secondary_count = int(context.get("secondary_count", 0) or 0)
    crossline_count = int(context.get("crossline_count", 0) or 0)
    prefer_data_driven_rows = bool(context.get("prefer_data_driven_stage_rows")) or not bool(context.get("report_stages"))
    guidance = f"{core_count}+{secondary_count} / {crossline_count}只"
    if prefer_data_driven_rows:
        guidance = build_candidate_trade_directive(context)
    return _row(
        "candidate_selection",
        _resolve_stage_title(stage_meta, "主线核心与跨线观察"),
        guidance,
    )


def _build_risk_row(context, stage_meta=None):
    risk_summary = str(context.get("risk_summary", "") or "").strip()
    prefer_data_driven_rows = bool(context.get("prefer_data_driven_stage_rows")) or not bool(context.get("report_stages"))
    if prefer_data_driven_rows:
        risk_note = build_risk_trade_note(context)
        if resolve_selected_position_candidate(context) and selected_target_is_attack_ready(context):
            guidance = risk_note
        else:
            guidance = f"{risk_summary}；{risk_note}" if risk_summary else risk_note
    else:
        guidance = risk_summary or "-"
    return _row("risk_review", _resolve_stage_title(stage_meta, "明日风险预判"), guidance)


def _build_execution_row(context, stage_meta=None):
    trade_gate_open = bool(context.get("trade_gate_open"))
    selected = resolve_selected_position_candidate(context)
    best_stock = context.get("best_stock") or {}
    watch_anchor = context.get("watch_anchor") or {}
    if selected and selected_target_is_attack_ready(context):
        guidance = "只等明日目标标的在固定交易窗口内满足条件"
    elif trade_gate_open:
        if best_stock:
            guidance = "只等明天唯一能买的那只自己走出来"
        elif watch_anchor:
            guidance = "先确认重点盯盘股，再看能否缩到一只可买股"
        else:
            guidance = "当前仍未形成候选对象，先继续等待"
    else:
        guidance = "不开新仓，只保留重点观察谁"
    prefer_data_driven_rows = bool(context.get("prefer_data_driven_stage_rows")) or not bool(context.get("report_stages"))
    trade_style = derive_trade_style(context)
    if prefer_data_driven_rows and trade_style:
        guidance = f"{trade_style}；{guidance}"
    return _row("execution_plan", _resolve_stage_title(stage_meta, "明日买点预计算"), guidance)


def _build_decisive_row(context, stage_meta=None):
    selected = resolve_selected_position_candidate(context)
    best_stock = context.get("best_stock") or {}
    watch_anchor = context.get("watch_anchor") or {}
    watch_anchor_type = str(context.get("watch_anchor_type", "") or "").strip()
    trade_gate_open = bool(context.get("trade_gate_open"))
    watch_anchor_note = get_watch_anchor_note(watch_anchor)

    if selected:
        stock_label = f"{selected.get('name')}({selected.get('code') or selected.get('stock_code')})"
        if selected_target_is_attack_ready(context):
            return _row("decisive_choice", _resolve_stage_title(stage_meta, "唯一动作"), f"{stock_label}；按固定交易窗口条件确认，不满足回到0%")
        return _row("decisive_choice", _resolve_stage_title(stage_meta, "唯一动作"), f"{stock_label}；先观察强弱，不抢跑")
    if best_stock:
        stock_label = f"{best_stock.get('name')}({best_stock.get('code')})"
        return _row("decisive_choice", _resolve_stage_title(stage_meta, "唯一动作"), f"{stock_label}；按固定交易窗口条件触发")
    if watch_anchor:
        stock_label = f"{watch_anchor.get('name')}({watch_anchor.get('code')})"
        if trade_gate_open:
            guidance = f"{stock_label}；先看固定交易窗口内条件，只有走成明天唯一能买的那只才参与"
        else:
            guidance = f"{stock_label}；仅作强弱观察，不构成买入指令"
        if watch_anchor_type:
            guidance = f"{watch_anchor_type}：{guidance}"
        if watch_anchor_note:
            guidance = f"{guidance}；{watch_anchor_note}"
        return _row("decisive_choice", _resolve_stage_title(stage_meta, "唯一动作"), guidance)
    return _row("decisive_choice", _resolve_stage_title(stage_meta, "唯一动作"), "当前没有能下手的票，明日空仓观察")


DEFAULT_ROW_BUILDERS = [
    _build_environment_row,
    _build_selection_row,
    _build_probe_row,
    _build_candidate_row,
    _build_risk_row,
    _build_execution_row,
    _build_decisive_row,
]


def build_legacy_report_stage_rows(context, row_builders=None):
    if row_builders is not None:
        rows = []
        for builder in list(row_builders or DEFAULT_ROW_BUILDERS):
            row = builder(context)
            if row:
                rows.append(row)
        return rows

    stage_meta_map = _resolve_stage_meta(context)
    row_builder_map = {
        "market_environment": _build_environment_row,
        "selection_focus": _build_selection_row,
        "anomaly_probe": _build_probe_row,
        "candidate_selection": _build_candidate_row,
        "risk_review": _build_risk_row,
        "execution_plan": _build_execution_row,
        "decisive_choice": _build_decisive_row,
    }
    ordered_stage_keys = []
    for item in context.get("report_stages") or []:
        raw_key = str((item or {}).get("stage_key", "") or "").strip()
        mapped_key = {
            "environment_follow": "market_environment",
            "watch_pool": "selection_focus",
            "candidate_selection": "candidate_selection",
            "risk_review": "risk_review",
            "entry_plan": "execution_plan",
            "pk_decision": "decisive_choice",
        }.get(raw_key, raw_key)
        if mapped_key in row_builder_map and mapped_key not in ordered_stage_keys:
            ordered_stage_keys.append(mapped_key)

    for stage_key in (
        "market_environment",
        "selection_focus",
        "anomaly_probe",
        "candidate_selection",
        "risk_review",
        "execution_plan",
        "decisive_choice",
    ):
        if stage_key not in ordered_stage_keys:
            ordered_stage_keys.append(stage_key)

    def _wrap_row_builder(stage_key, row_builder):
        def _node_builder(node_context, node_meta, node_lookup=None):
            row = row_builder(node_context["report_context"], node_context["stage_meta_map"].get(stage_key))
            return {
                "rows": [row] if row else [],
                "exports": {},
                "module_logs": [],
            }

        return _node_builder

    builder_map = {
        stage_key: _wrap_row_builder(stage_key, row_builder_map[stage_key])
        for stage_key in ordered_stage_keys
        if stage_key in row_builder_map
    }
    enabled_node_keys = context.get("enabled_node_keys")
    node_specs = build_legacy_stage_summary_node_specs(builder_map, enabled_node_keys=enabled_node_keys)
    runtime_result = run_legacy_stage_summary_nodes(
        node_specs,
        {
            "report_context": context,
            "stage_meta_map": stage_meta_map,
        },
    )
    return runtime_result["rows"]
