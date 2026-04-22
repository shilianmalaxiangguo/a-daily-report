def _row(stage_key, title, guidance):
    return {
        "stage_key": stage_key,
        "title": title,
        "guidance": guidance,
    }


def _build_environment_row(context):
    report_stages = context.get("report_stages") or []
    environment_stage = next((item for item in report_stages if item.get("stage_key") == "market_environment"), None) or {}
    summary = str(environment_stage.get("summary", "") or "").strip() or "-"
    return _row("market_environment", "环境与跟随裁决", summary)


def _build_selection_row(context):
    watchlist_count = int(context.get("watchlist_count", 0) or 0)
    return _row("selection_focus", "明天观察池", f"{watchlist_count}只")


def _build_probe_row(context):
    probe_parts = context.get("abnormal_probe_parts") or []
    if not probe_parts:
        return None
    return _row("anomaly_probe", "异常探针", "；".join(probe_parts))


def _build_candidate_row(context):
    core_count = int(context.get("core_count", 0) or 0)
    secondary_count = int(context.get("secondary_count", 0) or 0)
    crossline_count = int(context.get("crossline_count", 0) or 0)
    return _row(
        "candidate_selection",
        "主线核心与跨线观察",
        f"{core_count}+{secondary_count} / {crossline_count}只",
    )


def _build_risk_row(context):
    return _row("risk_review", "明日风险预判", str(context.get("risk_summary", "") or "-").strip() or "-")


def _build_execution_row(context):
    trade_gate_open = bool(context.get("trade_gate_open"))
    best_stock = context.get("best_stock") or {}
    watch_anchor = context.get("watch_anchor") or {}
    if trade_gate_open:
        if best_stock:
            guidance = "只等明天唯一能买的那只自己走出来"
        elif watch_anchor:
            guidance = "先确认重点盯盘股，再看能否缩到一只可买股"
        else:
            guidance = "当前仍未形成候选对象，先继续等待"
    else:
        guidance = "不开新仓，只保留重点观察谁"
    return _row("execution_plan", "明日买点预计算", guidance)


def _build_decisive_row(context):
    best_stock = context.get("best_stock") or {}
    watch_anchor = context.get("watch_anchor") or {}
    watch_anchor_type = str(context.get("watch_anchor_type", "") or "").strip()
    trade_gate_open = bool(context.get("trade_gate_open"))
    watch_anchor_note = str((watch_anchor or {}).get("watch_anchor_note", "") or "").strip()

    if best_stock:
        stock_label = f"{best_stock.get('name')}({best_stock.get('code')})"
        return _row("decisive_choice", "唯一动作", f"{stock_label}；60分钟确认后按条件触发")
    if watch_anchor:
        stock_label = f"{watch_anchor.get('name')}({watch_anchor.get('code')})"
        if trade_gate_open:
            guidance = f"{stock_label}；先做60分钟确认，只有走成明天唯一能买的那只才允许买入"
        else:
            guidance = f"{stock_label}；仅作强弱观察，不构成买入指令"
        if watch_anchor_type:
            guidance = f"{watch_anchor_type}：{guidance}"
        if watch_anchor_note:
            guidance = f"{guidance}；{watch_anchor_note}"
        return _row("decisive_choice", "唯一动作", guidance)
    return _row("decisive_choice", "唯一动作", "当前没有能下手的票，明日空仓观察")


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
    rows = []
    for builder in list(row_builders or DEFAULT_ROW_BUILDERS):
        row = builder(context)
        if row:
            rows.append(row)
    return rows
