def resolve_mainline_turnover_summary(context=None):
    context = context or {}
    summary = dict(context.get("mainline_turnover_summary") or {})

    label = str(summary.get("label") or "主线更替与成交额占比").strip() or "主线更替与成交额占比"
    conclusion = str(summary.get("conclusion") or context.get("mainline_turnover_conclusion") or "").strip()
    data_text = str(summary.get("data_text") or context.get("mainline_turnover_data_text") or "").strip()
    action_text = str(summary.get("action_text") or context.get("mainline_turnover_action_text") or "").strip()

    if not conclusion and not data_text and not action_text:
        return {}

    return {
        "label": label,
        "conclusion": conclusion or "-",
        "data_text": data_text or "-",
        "action_text": action_text or "-",
    }


def resolve_double_mainline_summary(context=None):
    context = context or {}
    summary = dict(context.get("double_mainline_summary") or {})
    source = dict(context.get("mainline_turnover_summary") or {})

    cycle_mainline = str(summary.get("cycle_mainline") or source.get("cycle_mainline") or "").strip()
    daily_attack_line = str(summary.get("daily_attack_line") or source.get("daily_attack_line") or "").strip()
    relationship = str(summary.get("relationship") or source.get("relationship") or "").strip()
    tomorrow_action = str(summary.get("tomorrow_action") or source.get("tomorrow_action") or source.get("action_text") or "").strip()

    if not cycle_mainline and not daily_attack_line and not relationship and not tomorrow_action:
        return {}

    return {
        "cycle_mainline": cycle_mainline or "-",
        "daily_attack_line": daily_attack_line or "-",
        "relationship": relationship or "-",
        "tomorrow_action": tomorrow_action or "-",
    }


def _safe_pct_float(value):
    if value in (None, ""):
        return None
    if isinstance(value, str):
        value = value.strip().replace("%", "").replace("pct", "")
        if not value or value == "待累计":
            return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_degraded_turnover_item(item):
    status = str((item or {}).get("source_status") or "").strip().lower()
    return bool(status and status not in ("success", "ok"))


def _turnover_item_mainline(item):
    item = item or {}
    return str(
        item.get("mainline")
        or item.get("sector_name")
        or item.get("cycle_mainline")
        or item.get("daily_attack_line")
        or ""
    ).strip()


def _row_mainline(row, fallback=""):
    return str(row.get("cycle_mainline") or row.get("daily_attack_line") or fallback or "").strip()


def _share_change_from_structured_history(row, context):
    history = list((context or {}).get("recent_sector_turnover_history") or [])
    if not history:
        return None
    row_mainline = _row_mainline(
        row,
        ((context or {}).get("mainline_turnover_summary") or {}).get("current_mainline"),
    )
    row_share_source = row.get("turnover_share_pct")
    if row_share_source in (None, ""):
        row_share_source = row.get("share")
    row_share = _safe_pct_float(row_share_source)
    current_snapshot = (context or {}).get("current_sector_turnover_snapshot") or {}
    used_current_snapshot = False
    if current_snapshot and _turnover_item_mainline(current_snapshot) == row_mainline:
        snapshot_date = str(current_snapshot.get("date") or "").strip()
        row_date = str(row.get("date") or "").strip()
        if not row_date or not snapshot_date or row_date == snapshot_date:
            row_share = _safe_pct_float(current_snapshot.get("turnover_share_pct"))
            used_current_snapshot = True
    if (
        not row_mainline
        or row_share is None
        or row_share <= 0
        or (used_current_snapshot and _is_degraded_turnover_item(current_snapshot))
    ):
        return "待累计"

    previous_item = None
    row_date = str(row.get("date") or "").strip()
    for item in history:
        item_date = str((item or {}).get("date") or "").strip()
        if row_date and item_date and item_date >= row_date:
            continue
        previous_item = item or {}
    if not previous_item:
        return "待累计"
    previous_share = _safe_pct_float(previous_item.get("turnover_share_pct"))
    if _is_degraded_turnover_item(previous_item) or previous_share is None or previous_share <= 0:
        return "待累计"
    if _turnover_item_mainline(previous_item) != row_mainline:
        return None
    return f"{row_share - previous_share:+.1f}pct"


def resolve_turnover_share_trend_rows(context=None):
    context = context or {}
    rows = context.get("turnover_share_trend_rows")
    if rows is None:
        rows = (context.get("mainline_turnover_summary") or {}).get("turnover_share_trend_rows")
    normalized = []
    for row in rows or []:
        row = row or {}
        normalized.append(
            {
                "date": str(row.get("date") or "-").strip() or "-",
                "cycle_mainline": str(row.get("cycle_mainline") or "-").strip() or "-",
                "daily_attack_line": str(row.get("daily_attack_line") or "-").strip() or "-",
                "mainline_turnover": str(row.get("mainline_turnover") or "-").strip() or "-",
                "market_turnover": str(row.get("market_turnover") or "-").strip() or "-",
                "share": str(row.get("share") or "-").strip() or "-",
                "share_change": str(
                    _share_change_from_structured_history(row, context) or row.get("share_change") or "-"
                ).strip() or "-",
                "interpretation": str(row.get("interpretation") or "-").strip() or "-",
            }
        )
    return normalized
