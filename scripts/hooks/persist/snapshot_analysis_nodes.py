def _pick_first_mapping(*values):
    for value in values:
        if isinstance(value, dict) and value:
            return dict(value)
    return {}


def _normalize_date(value):
    return str(value or "").strip()


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _normalize_mainline_history_record(record, target_date):
    record = dict(record or {})
    target_date = _normalize_date(target_date)
    primary_mainline = str(record.get("primary_mainline") or record.get("leading_line") or "").strip()
    if not primary_mainline:
        return {}
    return {
        "date": _normalize_date(record.get("date") or target_date),
        "primary_mainline": primary_mainline,
        "secondary_mainline": str(record.get("secondary_mainline", "") or "").strip(),
        "competition_mainline": str(record.get("competition_mainline", "") or "").strip(),
        "rotation_label": str(record.get("rotation_label", "") or "").strip(),
        "leading_line": str(record.get("leading_line") or primary_mainline).strip(),
        "state_code": str(record.get("state_code", "") or "").strip(),
        "rotation_summary": str(record.get("rotation_summary", "") or "").strip(),
        "source": str(record.get("source", "") or "persist.snapshot").strip(),
        "hot_rank_weight": int(record.get("hot_rank_weight", 0) or 0),
        "sector_counts": dict(record.get("sector_counts") or {}),
    }


def _build_mainline_history_from_ctx(context, target_date):
    derived = context.get("derived") or {}
    mainline = derived.get("mainline") or {}
    primary_line = str(mainline.get("primary_line") or mainline.get("mainline") or "").strip()
    if not primary_line:
        return {}
    return {
        "date": target_date,
        "primary_mainline": primary_line,
        "secondary_mainline": "",
        "competition_mainline": "",
        "rotation_label": "",
        "leading_line": primary_line,
        "state_code": "",
        "rotation_summary": "",
        "source": "persist.snapshot.derived.mainline",
        "hot_rank_weight": int(mainline.get("hot_rank_weight", 0) or 0),
        "sector_counts": dict(mainline.get("sector_counts") or {}),
    }


def _normalize_sector_turnover_snapshot(snapshot, target_date, fallback_sector_name=""):
    snapshot = dict(snapshot or {})
    sector_name = str(snapshot.get("sector_name") or fallback_sector_name or "").strip()
    sector_turnover = round(_safe_float(snapshot.get("sector_turnover")), 2)
    total_turnover = round(_safe_float(snapshot.get("total_turnover")), 2)
    turnover_share_pct = snapshot.get("turnover_share_pct")
    if turnover_share_pct in (None, "") and sector_turnover > 0 and total_turnover > 0:
        turnover_share_pct = sector_turnover / total_turnover * 100
    turnover_share_pct = round(_safe_float(turnover_share_pct), 2)
    if not sector_name or (sector_turnover <= 0 and turnover_share_pct <= 0):
        return {}
    return {
        "date": _normalize_date(snapshot.get("date") or target_date),
        "sector_name": sector_name,
        "sector_turnover": sector_turnover,
        "total_turnover": total_turnover,
        "turnover_share_pct": turnover_share_pct,
        "matched_sector_names": list(snapshot.get("matched_sector_names", []) or []),
        "matched_sector_codes": list(snapshot.get("matched_sector_codes", []) or []),
        "source": str(snapshot.get("source", "") or "persist.snapshot").strip(),
    }


def _resolve_market_snapshot_sector_turnover(context):
    normalized = context.get("normalized") or {}
    market_snapshot = normalized.get("market_snapshot") or {}
    return _pick_first_mapping(
        market_snapshot.get("sector_turnover_snapshot"),
        normalized.get("sector_turnover_snapshot"),
        (context.get("derived") or {}).get("sector_turnover_snapshot"),
        (context.get("raw") or {}).get("sector_turnover_snapshot"),
    )


def build_snapshot_mainline_history_node(context, node_meta=None, node_lookup=None):
    request = context.get("request") or {}
    target_date = _normalize_date(request.get("target_date"))
    explicit_record = _pick_first_mapping(
        (context.get("derived") or {}).get("mainline_history_record"),
        (context.get("normalized") or {}).get("mainline_history_record"),
        (context.get("raw") or {}).get("mainline_history_record"),
    )
    record = _normalize_mainline_history_record(explicit_record, target_date) or _build_mainline_history_from_ctx(context, target_date)
    if not record:
        return {"lines": [], "exports": {}, "module_logs": []}
    return {
        "lines": [],
        "exports": {"mainline_history_record": record},
        "module_logs": [
            {
                "module": "hooks.persist.snapshot_analysis_nodes",
                "step": "build.mainline_history_record",
                "status": "success",
                "message": "已构建主线历史记录快照节点",
                "details": {"primary_mainline": record.get("primary_mainline", "")},
            }
        ],
    }


def build_snapshot_sector_turnover_node(context, node_meta=None, node_lookup=None):
    request = context.get("request") or {}
    target_date = _normalize_date(request.get("target_date"))
    mainline_record = context.get("mainline_history_record") or {}
    sector_name = str(mainline_record.get("primary_mainline", "") or "").strip()
    snapshot = _normalize_sector_turnover_snapshot(_resolve_market_snapshot_sector_turnover(context), target_date, fallback_sector_name=sector_name)
    if not snapshot:
        return {"lines": [], "exports": {}, "module_logs": []}
    return {
        "lines": [],
        "exports": {"sector_turnover_snapshot": snapshot},
        "module_logs": [
            {
                "module": "hooks.persist.snapshot_analysis_nodes",
                "step": "build.sector_turnover_snapshot",
                "status": "success",
                "message": "已构建板块成交额快照节点",
                "details": {
                    "sector_name": snapshot.get("sector_name", ""),
                    "turnover_share_pct": snapshot.get("turnover_share_pct", 0.0),
                },
            }
        ],
    }
