from domains.market_state.mainline_turnover_summary_runtime import build_mainline_turnover_summary


def _append_log(logs, step, status, message, **details):
    logs.append(
        {
            "module": "domains.market_state.mainline_capacity.nodes",
            "step": step,
            "status": status,
            "message": message,
            "details": details,
        }
    )


def _source_status(snapshot):
    status = str((snapshot or {}).get("source_status") or "").strip()
    return status or "unknown"


def build_mainline_capacity_summary_node(context, node_meta=None, node_lookup=None):
    context = context or {}
    summary = build_mainline_turnover_summary(
        target_date=context.get("target_date") or "",
        current_mainline_history_record=context.get("current_mainline_history_record"),
        recent_mainline_history=context.get("recent_mainline_history"),
        current_sector_turnover_snapshot=context.get("current_sector_turnover_snapshot"),
        recent_sector_turnover_history=context.get("recent_sector_turnover_history"),
        recent_hot_sector_turnover_history=context.get("recent_hot_sector_turnover_history"),
        sector_attack_evidence_rows=context.get("sector_attack_evidence_rows"),
        realtime_tag_evidence_snapshot=context.get("realtime_tag_evidence_snapshot"),
    )
    capacity_summary = dict(summary.get("mainline_capacity_regime_summary") or {})
    attack_summary = dict(summary.get("mainline_attack_evidence_summary") or {})
    overtake_summary = dict(summary.get("overtake_window_summary") or {})
    arena_fit_summary = dict(summary.get("trading_arena_fit_summary") or {})
    turnover_rows = list(summary.get("turnover_share_trend_rows") or [])
    turnover_trend_summary = str(summary.get("turnover_share_trend_summary") or "").strip()
    hot_sector_watch_rows = list(summary.get("hot_sector_turnover_watch_rows") or [])
    hot_sector_watch_summary = str(summary.get("hot_sector_turnover_watch_summary") or "").strip()
    snapshot = context.get("current_sector_turnover_snapshot") or {}

    exports = {
        "mainline_turnover_summary": summary,
        "mainline_capacity_regime_summary": capacity_summary,
        "mainline_attack_evidence_summary": attack_summary,
        "overtake_window_summary": overtake_summary,
        "trading_arena_fit_summary": arena_fit_summary,
        "turnover_share_trend_rows": turnover_rows,
        "turnover_share_trend_summary": turnover_trend_summary,
        "hot_sector_turnover_watch_rows": hot_sector_watch_rows,
        "hot_sector_turnover_watch_summary": hot_sector_watch_summary,
    }
    diagnostics = {
        "target_date": summary.get("date") or context.get("target_date") or "",
        "current_mainline": summary.get("current_mainline") or "",
        "previous_mainline": summary.get("previous_mainline") or "",
        "share_trend_label": summary.get("share_trend_label") or "",
        "turnover_share_row_count": len(turnover_rows),
        "mainline_capacity": capacity_summary.get("mainline_capacity") or "",
        "mainline_regime": capacity_summary.get("mainline_regime") or "",
        "turnover_share_source_status": _source_status(snapshot),
        "attack_state": attack_summary.get("attack_state") or "",
    }
    logs = []
    _append_log(
        logs,
        "summary.mainline_capacity",
        "success" if summary.get("current_mainline") else "degraded",
        "已完成主线成交额与容量判断",
        current_mainline=diagnostics["current_mainline"],
        mainline_capacity=diagnostics["mainline_capacity"],
        turnover_share_row_count=diagnostics["turnover_share_row_count"],
    )
    return {
        "exports": exports,
        "report_sections": {
            "mainline_turnover_summary": summary,
            "mainline_capacity_regime": capacity_summary,
            "mainline_turnover_share_trend": {
                "summary": turnover_trend_summary,
                "rows": turnover_rows,
            },
            "hot_sector_turnover_watch": {
                "summary": hot_sector_watch_summary,
                "rows": hot_sector_watch_rows,
            },
        },
        "diagnostics": diagnostics,
        "module_logs": logs,
    }
