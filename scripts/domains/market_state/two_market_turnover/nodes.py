from report.market_condition_wording import describe_market_turnover_condition


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _append_log(logs, step, status, message, **details):
    logs.append(
        {
            "module": "domains.market_state.two_market_turnover.nodes",
            "step": step,
            "status": status,
            "message": message,
            "details": details,
        }
    )


def _normalized_history_rows(data):
    data = data or {}
    source_rows = data.get("market_turnover_history") or data.get("recent_market_turnover_history") or []
    rows = []
    for item in source_rows:
        row = dict(item or {})
        trade_date = str(row.get("date") or row.get("trade_date") or "").strip()
        turnover = _safe_float(row.get("turnover", row.get("total_turnover_yi", row.get("total_amount_yi"))))
        if not trade_date or turnover <= 0:
            continue
        rows.append({"date": trade_date, "turnover": round(turnover, 2)})
    return rows


def _top50_series_source_rows(data):
    data = data or {}
    for key in ("top50_turnover_share_series", "top50_turnover_share_trend", "top50_turnover_share_trend_rows"):
        value = data.get(key)
        if isinstance(value, dict):
            rows = value.get("rows") or value.get("trend_rows") or []
            if rows:
                return list(rows)
        elif isinstance(value, (list, tuple)) and value:
            return list(value)
    return []


def _normalized_top50_market_amount_rows(data, target_date=""):
    rows = []
    target_date = str(target_date or "").strip()
    if not target_date:
        return rows
    for item in _top50_series_source_rows(data):
        row = dict(item or {})
        trade_date = str(row.get("trade_date") or row.get("date") or "").strip()
        turnover = _safe_float(row.get("market_amount_yi", row.get("total_amount_yi")))
        if not trade_date or turnover <= 0:
            continue
        if trade_date == target_date:
            continue
        rows.append({"date": trade_date, "turnover": round(turnover, 2)})
    rows.sort(key=lambda row: row["date"])
    rows = [row for row in rows if row["date"] < target_date]
    return rows


def _comparison_state(current_turnover, history_rows):
    previous = _safe_float((history_rows[-1] if history_rows else {}).get("turnover"))
    previous2 = _safe_float((history_rows[-2] if len(history_rows) >= 2 else {}).get("turnover"))
    if current_turnover <= 0 or previous <= 0:
        return "unknown", "量能历史不足"
    if previous2 > 0 and current_turnover < previous * 0.97 and previous < previous2 * 0.97:
        return "shrinking", "成交额连续回落"
    if previous2 > 0 and current_turnover > previous * 1.03 and previous >= previous2 * 0.98:
        return "rising", "成交额继续回升"
    if current_turnover < previous * 0.97:
        return "pullback", "成交额冲高后回落"
    if current_turnover > previous * 1.03:
        return "rebound", "成交额重新放大"
    return "flat", "成交额横向波动"


def build_turnover_comparison(data, target_date=""):
    data = data or {}
    current_turnover = _safe_float(data.get("total_turnover", data.get("turnover")))
    history_rows = _normalized_history_rows(data)
    source = "context.market_turnover_history" if history_rows else "missing"
    if not history_rows:
        history_rows = _normalized_top50_market_amount_rows(data, target_date)
        if history_rows:
            source = "context.top50_turnover_share_series.market_amount_yi"
    state, label = _comparison_state(current_turnover, history_rows)
    previous_turnover = _safe_float((history_rows[-1] if history_rows else {}).get("turnover"))
    previous_change_pct = None
    if current_turnover > 0 and previous_turnover > 0:
        previous_change_pct = round((current_turnover / previous_turnover - 1) * 100, 2)
    series = [*history_rows]
    if current_turnover > 0:
        series.append({"date": str(target_date or "").strip(), "turnover": round(current_turnover, 2)})
    return {
        "state": state,
        "label": label,
        "condition_text": describe_market_turnover_condition(data),
        "latest_turnover_yi": round(current_turnover, 2),
        "previous_turnover_yi": round(previous_turnover, 2) if previous_turnover > 0 else 0.0,
        "previous_change_pct": previous_change_pct,
        "history_rows": history_rows,
        "series": series,
        "source": source,
    }


def build_two_market_turnover_compare_node(context, node_meta=None, node_lookup=None):
    context = context or {}
    data = context.get("data") or {}
    target_date = str(context.get("target_date") or "").strip()
    summary = build_turnover_comparison(data, target_date)
    logs = []
    _append_log(
        logs,
        "compare.two_market_turnover",
        "success" if summary["latest_turnover_yi"] > 0 else "degraded",
        "已完成两市成交额历史对比",
        latest_turnover_yi=summary["latest_turnover_yi"],
        history_count=len(summary["history_rows"]),
        source=summary["source"],
    )
    return {
        "exports": {"two_market_turnover_comparison": summary},
        "report_sections": {"two_market_turnover": summary},
        "diagnostics": {
            "latest_turnover_yi": summary["latest_turnover_yi"],
            "history_count": len(summary["history_rows"]),
            "source": summary["source"],
            "state": summary["state"],
        },
        "module_logs": logs,
    }
