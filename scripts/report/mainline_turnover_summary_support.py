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
                "share_change": str(row.get("share_change") or "-").strip() or "-",
                "interpretation": str(row.get("interpretation") or "-").strip() or "-",
            }
        )
    return normalized
