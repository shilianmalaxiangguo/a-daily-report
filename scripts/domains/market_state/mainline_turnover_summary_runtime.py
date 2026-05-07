from __future__ import annotations

__all__ = [
    "build_mainline_turnover_summary",
    "should_rebuild_mainline_turnover_summary",
]


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _pick_current_mainline(current_record):
    current_record = current_record or {}
    return str(current_record.get("primary_mainline") or current_record.get("leading_line") or "").strip()


def _pick_summary_mainline(summary):
    summary = summary or {}
    return str(summary.get("current_mainline") or "").strip()


def _pick_previous_mainline(recent_mainline_history, current_mainline):
    history = list(recent_mainline_history or [])
    for item in reversed(history):
        mainline = str((item or {}).get("primary_mainline") or (item or {}).get("leading_line") or "").strip()
        if mainline:
            return mainline
    return current_mainline


def should_rebuild_mainline_turnover_summary(
    summary,
    *,
    current_mainline_history_record=None,
    recent_mainline_history=None,
):
    if not isinstance(summary, dict):
        return True

    current_mainline = _pick_current_mainline(current_mainline_history_record)
    summary_mainline = _pick_summary_mainline(summary)
    if not summary_mainline:
        return True
    if current_mainline and summary_mainline != current_mainline:
        return True

    previous_mainline = _pick_previous_mainline(recent_mainline_history, current_mainline)
    expects_switch = bool(current_mainline and previous_mainline and current_mainline != previous_mainline)
    if not expects_switch:
        return False

    summary_previous_mainline = str(summary.get("previous_mainline") or "").strip()
    summary_trend_label = str(summary.get("share_trend_label") or "").strip()
    summary_conclusion = str(summary.get("conclusion") or "").strip()
    return not (
        summary_previous_mainline == previous_mainline
        and summary_trend_label == "切换"
        and "主线切换" in summary_conclusion
    )


def _build_mainline_path_text(recent_mainline_history, current_mainline):
    history = list(recent_mainline_history or [])
    path = [
        str((item or {}).get("primary_mainline") or (item or {}).get("leading_line") or "").strip()
        for item in history
        if str((item or {}).get("primary_mainline") or (item or {}).get("leading_line") or "").strip()
    ]
    if current_mainline:
        path.append(current_mainline)
    return " -> ".join(path[-3:])


def _build_share_series(recent_sector_turnover_history, current_snapshot):
    history = list(recent_sector_turnover_history or [])
    series = []
    for item in history:
        share = round(_safe_float((item or {}).get("turnover_share_pct")), 1)
        if share > 0:
            series.append(share)
    current_share = round(_safe_float((current_snapshot or {}).get("turnover_share_pct")), 1)
    if current_share > 0:
        series.append(current_share)
    return series[-3:]


def _format_share_series(series):
    return " -> ".join(f"{value:.1f}%" for value in series)


def _resolve_share_trend_label(current_mainline, previous_mainline, share_series):
    if current_mainline and previous_mainline and current_mainline != previous_mainline:
        return "切换"
    if len(share_series) >= 2 and share_series[-1] > share_series[0]:
        return "强化"
    if len(share_series) >= 2 and share_series[-1] < share_series[0]:
        return "分化"
    return "持平"


def _build_conclusion(current_mainline, previous_mainline, share_trend_label):
    if current_mainline and previous_mainline and current_mainline != previous_mainline:
        return f"主线切换为{current_mainline}，旧主线{previous_mainline}退出中心"
    if current_mainline:
        return f"主线未切换，{current_mainline}仍是中心"
    return "主线待确认，暂不输出成交额占比结论"


def _build_action_text(current_mainline, previous_mainline, share_trend_label):
    if current_mainline and previous_mainline and current_mainline != previous_mainline:
        return f"只围绕新主线{current_mainline}重新收缩，不对旧主线做回流预判"
    if current_mainline and share_trend_label == "强化":
        return f"继续围绕{current_mainline}做减法，不追支线分流"
    if current_mainline and share_trend_label == "分化":
        return f"{current_mainline}虽在中心，但占比回落，先防分化，不追高位加速"
    if current_mainline:
        return f"继续围绕{current_mainline}观察承接，不做多线扩散"
    return "先等待主线明确，再谈成交额占比趋势"


def _format_amount_yi(value):
    amount = _safe_float(value)
    if amount <= 0:
        return "数据暂缺"
    return f"{amount:.2f}亿"


def _format_share_pct(value):
    share = _safe_float(value)
    if share <= 0:
        return "待累计"
    return f"{share:.1f}%"


def _format_share_change(current_share, previous_share):
    current_share = _safe_float(current_share)
    previous_share = _safe_float(previous_share)
    if current_share <= 0 or previous_share <= 0:
        return "待累计"
    change = current_share - previous_share
    return f"{change:+.1f}pct"


def _build_turnover_share_row(item, *, fallback_mainline="", daily_attack_line="", previous_share=0.0):
    item = item or {}
    source_status = str(item.get("source_status") or "").strip()
    share = _safe_float(item.get("turnover_share_pct"))
    sector_turnover = _safe_float(item.get("sector_turnover"))
    sector_name = str(item.get("sector_name") or fallback_mainline or "-").strip() or "-"
    row_daily_attack_line = str(
        item.get("daily_attack_line") or item.get("attack_line") or daily_attack_line or sector_name or "-"
    ).strip() or "-"
    if source_status == "missing_dependency":
        interpretation = "缺少板块成交额接口，先记录主线归属，成交额占比待后续数据累计"
    elif share > 0:
        interpretation = "主线成交额占比可用，继续观察占比抬升或回落"
    else:
        interpretation = "主线成交额占比暂缺，先不据此放大买入资格"
    return {
        "date": str(item.get("date") or "-").strip() or "-",
        "cycle_mainline": sector_name,
        "daily_attack_line": row_daily_attack_line,
        "mainline_turnover": _format_amount_yi(sector_turnover),
        "market_turnover": _format_amount_yi(item.get("total_turnover")),
        "share": _format_share_pct(share),
        "share_change": _format_share_change(share, previous_share),
        "interpretation": interpretation,
    }


def _turnover_row_mainline(item, fallback_mainline=""):
    item = item or {}
    return str(item.get("sector_name") or item.get("cycle_mainline") or fallback_mainline or "").strip()


def _turnover_row_key(item):
    item = item or {}
    return (str(item.get("date") or "").strip(), _turnover_row_mainline(item))


def _limit_turnover_share_source_rows(source_rows, current_mainline, limit=5):
    source_rows = list(source_rows or [])
    if len(source_rows) <= limit:
        return source_rows
    limited = source_rows[-limit:]
    current_mainline = str(current_mainline or "").strip()
    previous_distinct_item = None
    for item in reversed(source_rows):
        row_mainline = _turnover_row_mainline(item)
        if row_mainline and current_mainline and row_mainline != current_mainline:
            previous_distinct_item = item
            break
    if previous_distinct_item and _turnover_row_key(previous_distinct_item) not in {
        _turnover_row_key(item) for item in limited
    }:
        limited = [previous_distinct_item] + limited[-(limit - 1) :]
    return limited


def _build_turnover_share_trend_rows(recent_sector_turnover_history, current_snapshot, current_mainline):
    source_rows = list(recent_sector_turnover_history or []) + ([current_snapshot] if current_snapshot else [])
    rows = []
    previous_share_by_mainline = {}
    previous_share_any_mainline = 0.0
    for item in _limit_turnover_share_source_rows(source_rows, current_mainline):
        row_mainline = _turnover_row_mainline(item, current_mainline)
        previous_same_mainline = previous_share_by_mainline.get(row_mainline, 0.0)
        row = _build_turnover_share_row(
            item,
            fallback_mainline=current_mainline,
            daily_attack_line="",
            previous_share=previous_same_mainline if previous_same_mainline > 0 else previous_share_any_mainline,
        )
        rows.append(row)
        share = _safe_float((item or {}).get("turnover_share_pct"))
        if share > 0:
            previous_share_by_mainline[row_mainline] = share
            previous_share_any_mainline = share
    return rows


def build_mainline_turnover_summary(
    *,
    target_date="",
    current_mainline_history_record=None,
    recent_mainline_history=None,
    current_sector_turnover_snapshot=None,
    recent_sector_turnover_history=None,
):
    current_record = current_mainline_history_record or {}
    current_snapshot = current_sector_turnover_snapshot or {}
    current_mainline = _pick_current_mainline(current_record)
    previous_mainline = _pick_previous_mainline(recent_mainline_history, current_mainline)
    share_series = _build_share_series(recent_sector_turnover_history, current_snapshot)
    share_trend_label = _resolve_share_trend_label(current_mainline, previous_mainline, share_series)
    conclusion = _build_conclusion(current_mainline, previous_mainline, share_trend_label)
    mainline_path = _build_mainline_path_text(recent_mainline_history, current_mainline)
    share_path = _format_share_series(share_series)
    data_text = f"最近{len(share_series)}日主线 {mainline_path}；成交额占比 {share_path}，节奏偏{share_trend_label}" if mainline_path and share_path else ""

    action_text = _build_action_text(current_mainline, previous_mainline, share_trend_label)
    return {
        "date": str(target_date or current_record.get("date") or current_snapshot.get("date") or "").strip(),
        "label": "主线更替与成交额占比",
        "current_mainline": current_mainline,
        "previous_mainline": previous_mainline if previous_mainline != current_mainline else previous_mainline,
        "share_trend_label": share_trend_label,
        "conclusion": conclusion,
        "data_text": data_text,
        "action_text": action_text,
        "double_mainline_summary": {
            "cycle_mainline": current_mainline or "-",
            "daily_attack_line": current_mainline or "-",
            "relationship": "周期主线与当天主攻线一致" if current_mainline else "主线待确认",
            "tomorrow_action": action_text,
        },
        "turnover_share_trend_rows": _build_turnover_share_trend_rows(
            recent_sector_turnover_history,
            current_snapshot,
            current_mainline,
        ),
    }
