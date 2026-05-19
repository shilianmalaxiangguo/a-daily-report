from __future__ import annotations

__all__ = [
    "build_mainline_attack_evidence_summary",
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


def _format_signed_pct(value):
    value = _safe_float(value)
    return f"{value:+.1f}%"


def _median(values):
    values = sorted(_safe_float(value) for value in values if _safe_float(value) > 0)
    if not values:
        return 0.0
    middle = len(values) // 2
    if len(values) % 2:
        return values[middle]
    return (values[middle - 1] + values[middle]) / 2


def _recent_total_turnover_values(recent_sector_turnover_history, current_snapshot):
    rows = list(recent_sector_turnover_history or [])
    if current_snapshot:
        rows.append(current_snapshot)
    values = []
    for item in rows[-25:]:
        total = _safe_float((item or {}).get("total_turnover"))
        if total > 0:
            values.append(total)
    return values


def _previous_total_turnover(recent_sector_turnover_history):
    for item in reversed(list(recent_sector_turnover_history or [])):
        total = _safe_float((item or {}).get("total_turnover"))
        if total > 0:
            return total
    return 0.0


def _capacity_relative_label(current_total, median_total):
    if current_total <= 0 or median_total <= 0:
        return "待累计"
    ratio = current_total / median_total
    if ratio < 0.9:
        return "缩量"
    if ratio < 1.1:
        return "常量"
    if ratio < 1.4:
        return "放量"
    return "巨量"


def _capacity_conclusion(current_total, previous_total, median_total, market_regime=""):
    if current_total <= 0:
        return "容量待累计"
    relative_label = _capacity_relative_label(current_total, median_total)
    daily_expanding = previous_total > 0 and current_total >= previous_total * 1.05
    daily_shrinking = previous_total > 0 and current_total <= previous_total * 0.95
    bull_like = str(market_regime or "").strip() in ("牛市", "超级牛市", "极强结构性行情")
    if relative_label == "巨量" and bull_like:
        return "牛市多线容量"
    if relative_label == "巨量":
        return "双线容量"
    if relative_label == "放量" and daily_expanding:
        return "双线孕育"
    if relative_label == "放量":
        return "单线容量"
    if relative_label == "缩量" or daily_shrinking:
        return "低容量"
    return "单线容量"


def _other_lines_text(current_record):
    values = []
    for key in ("secondary_mainline", "competition_mainline", "background_mainline"):
        value = str((current_record or {}).get(key) or "").strip()
        if value and value not in values:
            values.append(value)
    return " / ".join(values) if values else "-"


def _count_other_lines(current_record):
    text = _other_lines_text(current_record)
    if text == "-":
        return 0
    return len([part for part in text.split(" / ") if part.strip()])


def _resolve_mainline_regime(current_mainline, current_record, capacity):
    if not current_mainline:
        return "无主线"
    explicit = str((current_record or {}).get("mainline_regime") or "").strip()
    if explicit:
        return explicit
    relationship = str((current_record or {}).get("sector_relationship_state") or "").strip()
    if relationship in ("混沌接力", "交替竞争", "主线+背景线"):
        return relationship
    other_count = _count_other_lines(current_record)
    market_regime = str((current_record or {}).get("market_regime") or "").strip()
    if other_count >= 2 and market_regime not in ("牛市", "超级牛市", "极强结构性行情"):
        return "混沌接力"
    if other_count >= 2:
        return "多主线牛市"
    if other_count == 1 and capacity in ("双线孕育", "双线容量", "牛市多线容量"):
        return "双主线竞争"
    if other_count == 1:
        return "主线+背景线"
    return "单主线聚焦"


def _capacity_evidence_text(current_total, previous_total, median_total, relative_label):
    parts = []
    if current_total > 0:
        parts.append(f"今日{current_total:.2f}亿")
    else:
        parts.append("今日成交额待累计")
    if previous_total > 0:
        change_pct = (current_total - previous_total) / previous_total * 100 if current_total > 0 else 0.0
        parts.append(f"昨日{previous_total:.2f}亿，日环比{_format_signed_pct(change_pct)}")
    else:
        parts.append("昨日成交额待累计")
    if median_total > 0:
        parts.append(f"近25日中位数{median_total:.2f}亿，{relative_label}")
    else:
        parts.append("近25日中位数待累计")
    return "；".join(parts)


def _default_regime_action(regime, current_mainline, action_text):
    if regime == "无主线":
        return "不强行找主线，只保留异常观察"
    if regime == "单主线聚焦":
        return f"只围绕{current_mainline}做减法" if current_mainline else action_text
    if regime == "双主线竞争":
        return "不同时押两边，先看谁继续被资金选择"
    if regime == "主线+背景线":
        return "主攻线给执行优先级，背景线只观察回流"
    if regime == "混沌接力":
        return "不把每次轮动都当新主线，候选只保留判断样本"
    if regime == "多主线牛市":
        return "多线可以同时给资格，但仍要缩到具体参与窗口"
    return action_text or "先看主线证据是否继续聚焦"


def _sector_evidence_labels(row):
    labels = []
    if row["net_inflow_amount"] > 0 and row["net_inflow_rank"] <= 3:
        labels.append("资金净流入靠前")
    if row["net_inflow_amount"] >= 30 and row["net_inflow_rank"] == 1:
        labels.append("资金净流入明显领先")
    if row["limit_up_count"] >= 5:
        labels.append("批量涨停")
    if row["high_anchor_height"] >= 3:
        labels.append("高标强度突出")
    if row["broad_rally_pct"] >= 65:
        labels.append("板块普涨")
    if row["strong_gain_count"] >= 10:
        labels.append("高涨幅集群")
    if row["turnover_share_change"] >= 1.0:
        labels.append("成交占比扩张")
    return labels


def _normalize_sector_evidence_row(row):
    row = row or {}
    sector = str(row.get("sector_name") or row.get("sector") or "").strip()
    normalized = {
        "sector_name": sector,
        "net_inflow_amount": _safe_float(row.get("net_inflow_amount")),
        "net_inflow_rank": int(_safe_float(row.get("net_inflow_rank"), 999)),
        "limit_up_count": int(_safe_float(row.get("limit_up_count"))),
        "high_anchor_height": int(_safe_float(row.get("high_anchor_height"))),
        "high_anchor_name": str(row.get("high_anchor_name") or "").strip(),
        "broad_rally_pct": _safe_float(row.get("broad_rally_pct"), -1.0),
        "strong_gain_count": int(_safe_float(row.get("strong_gain_count"))),
        "sector_turnover": _safe_float(row.get("sector_turnover")),
        "turnover_share_pct": _safe_float(row.get("turnover_share_pct")),
        "turnover_share_change": _safe_float(row.get("turnover_share_change")),
    }
    missing = []
    for key in (
        "net_inflow_amount",
        "net_inflow_rank",
        "limit_up_count",
        "high_anchor_height",
        "broad_rally_pct",
        "strong_gain_count",
        "sector_turnover",
        "turnover_share_pct",
        "turnover_share_change",
    ):
        if row.get(key) in (None, ""):
            missing.append(key)
    normalized["missing_fields"] = missing
    normalized["evidence_labels"] = _sector_evidence_labels(normalized)
    normalized["local_evidence_count"] = _sector_local_evidence_count(normalized)
    normalized["fund_evidence_count"] = len(
        [
            label
            for label in normalized["evidence_labels"]
            if label in ("资金净流入靠前", "资金净流入明显领先", "成交占比扩张")
        ]
    )
    normalized["strength_evidence_count"] = len(
        [
            label
            for label in normalized["evidence_labels"]
            if label in ("批量涨停", "高标强度突出", "板块普涨", "高涨幅集群")
        ]
    )
    normalized["evidence_count"] = normalized["fund_evidence_count"] + normalized["strength_evidence_count"]
    return normalized


def _rank_sector_evidence(rows):
    return sorted(
        rows,
        key=lambda row: (
            row["fund_evidence_count"] > 0 and row["strength_evidence_count"] > 0,
            row["evidence_count"],
            row["local_evidence_count"],
            row["net_inflow_amount"],
            -row["net_inflow_rank"],
            row["limit_up_count"],
        ),
        reverse=True,
    )


def _is_confirmed_attack(row):
    return (
        row["fund_evidence_count"] > 0
        and row["strength_evidence_count"] > 0
        and row["evidence_count"] >= 3
    )


def _is_candidate_attack(row):
    return row["evidence_count"] > 0 or row["local_evidence_count"] > 0


def _candidate_gap(row):
    if row["fund_evidence_count"] > 0 and row["strength_evidence_count"] > 0:
        return "资金确认不足"
    if row["strength_evidence_count"] > 0 and row["fund_evidence_count"] == 0:
        return "情绪强于资金确认"
    if row["fund_evidence_count"] > 0 and row["strength_evidence_count"] == 0:
        return "资金试探但强度不足"
    return ""


def _confirmation_text(primary, labels):
    pieces = []
    if "资金净流入靠前" in labels or "资金净流入明显领先" in labels:
        pieces.append("资金净流入靠前")
    strength_parts = []
    if "批量涨停" in labels:
        strength_parts.append("涨停")
    if "高标强度突出" in labels:
        strength_parts.append("高标")
    if strength_parts:
        pieces.append("和".join(strength_parts) + "更集中")
    if "成交占比扩张" in labels:
        pieces.append("成交占比扩张")
    return f"{primary}" + "，".join(pieces) if pieces else f"{primary}主线确认依据待补充"


def _sector_local_evidence_count(row):
    count = 0
    if row["net_inflow_amount"] > 0 and row["net_inflow_rank"] <= 5:
        count += 1
    if row["limit_up_count"] >= 2:
        count += 1
    if row["high_anchor_height"] >= 2:
        count += 1
    if row["strong_gain_count"] >= 8:
        count += 1
    return count


def build_mainline_attack_evidence_summary(*, sector_evidence_rows=None, market_regime=""):
    rows = [
        _normalize_sector_evidence_row(row)
        for row in (sector_evidence_rows or [])
        if str((row or {}).get("sector_name") or (row or {}).get("sector") or "").strip()
    ]
    ranked = _rank_sector_evidence(rows)
    confirmed = [row for row in ranked if _is_confirmed_attack(row)]
    candidates = [row for row in ranked if not _is_confirmed_attack(row) and _is_candidate_attack(row)]
    if confirmed:
        primary = confirmed[0]
        other_confirmed = [row["sector_name"] for row in confirmed[1:]]
        relationship_hint = "双主线竞争" if other_confirmed else "单主线聚焦"
        return {
            "attack_state": "confirmed_attack",
            "primary_line": primary["sector_name"],
            "candidate_lines": other_confirmed,
            "background_lines": [row["sector_name"] for row in candidates[:2]],
            "relationship_hint": relationship_hint,
            "evidence_labels": primary["evidence_labels"],
            "confirmation_evidence": _confirmation_text(primary["sector_name"], primary["evidence_labels"]),
            "evidence_gaps": [],
            "sector_evidence_rows": ranked,
        }
    if len(candidates) >= 3:
        gaps = [gap for row in candidates for gap in [_candidate_gap(row)] if gap]
        return {
            "attack_state": "chaotic_rotation",
            "primary_line": "",
            "candidate_lines": [row["sector_name"] for row in candidates[:3]],
            "background_lines": [],
            "relationship_hint": "混沌接力",
            "evidence_labels": [],
            "confirmation_evidence": "多方向局部活跃但资金未明显胜出",
            "evidence_gaps": gaps,
            "sector_evidence_rows": ranked,
        }
    if candidates:
        gaps = [gap for row in candidates for gap in [_candidate_gap(row)] if gap]
        return {
            "attack_state": "candidate_attack",
            "primary_line": "",
            "candidate_lines": [row["sector_name"] for row in candidates],
            "background_lines": [],
            "relationship_hint": "候选线",
            "evidence_labels": candidates[0]["evidence_labels"],
            "confirmation_evidence": f"{candidates[0]['sector_name']}有局部进攻证据，但主线确认不足",
            "evidence_gaps": gaps,
            "sector_evidence_rows": ranked,
        }
    return {
        "attack_state": "no_attack",
        "primary_line": "",
        "candidate_lines": [],
        "background_lines": [],
        "relationship_hint": "无主线",
        "evidence_labels": [],
        "confirmation_evidence": "资金未形成明确进攻方向",
        "evidence_gaps": [],
        "sector_evidence_rows": ranked,
    }


def _build_mainline_capacity_regime_summary(
    *,
    current_mainline,
    current_record,
    current_snapshot,
    recent_sector_turnover_history,
    action_text,
):
    current_total = _safe_float((current_snapshot or {}).get("total_turnover"))
    previous_total = _previous_total_turnover(recent_sector_turnover_history)
    median_total = _median(_recent_total_turnover_values(recent_sector_turnover_history, current_snapshot))
    relative_label = _capacity_relative_label(current_total, median_total)
    capacity = _capacity_conclusion(
        current_total,
        previous_total,
        median_total,
        market_regime=(current_record or {}).get("market_regime"),
    )
    regime = _resolve_mainline_regime(current_mainline, current_record, capacity)
    process = str((current_record or {}).get("mainline_process") or "").strip()
    if not process:
        process = "无" if not current_mainline else "启动" if regime in ("单主线聚焦", "主线+背景线", "混沌接力") else "待观察"
    confirmation = str((current_record or {}).get("mainline_confirmation_evidence") or "").strip()
    if not confirmation:
        share = _safe_float((current_snapshot or {}).get("turnover_share_pct"))
        if current_mainline and share > 0:
            confirmation = f"{current_mainline}成交占比{share:.1f}%"
        elif current_mainline:
            confirmation = "资金态度待补充"
        else:
            confirmation = "资金未形成明确进攻方向"
    relationship = str((current_record or {}).get("sector_relationship_state") or "").strip() or (
        "暂未分出" if not current_mainline else regime
    )
    tomorrow_action = str((current_record or {}).get("mainline_regime_action") or "").strip()
    return {
        "mainline_capacity": capacity,
        "mainline_regime": regime,
        "primary_line": current_mainline or "暂无",
        "other_lines": _other_lines_text(current_record),
        "confirmation_evidence": confirmation,
        "sector_relationship_state": relationship,
        "mainline_process": process,
        "tomorrow_action": tomorrow_action or _default_regime_action(regime, current_mainline, action_text),
        "capacity_evidence": _capacity_evidence_text(current_total, previous_total, median_total, relative_label),
    }


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


def _snapshot_from_attack_evidence(current_snapshot, attack_evidence_summary, target_date):
    current_snapshot = current_snapshot or {}
    primary = str((attack_evidence_summary or {}).get("primary_line") or "").strip()
    if not primary:
        return current_snapshot
    if _sector_names_equal(str(current_snapshot.get("sector_name") or ""), primary):
        return current_snapshot

    evidence_row = {}
    for row in (attack_evidence_summary or {}).get("sector_evidence_rows") or []:
        if _sector_names_equal((row or {}).get("sector_name"), primary):
            evidence_row = row or {}
            break
    if not evidence_row:
        return current_snapshot

    share = _safe_float(evidence_row.get("turnover_share_pct"))
    total_turnover = _safe_float(current_snapshot.get("total_turnover"))
    sector_turnover = _safe_float(evidence_row.get("sector_turnover"))
    if sector_turnover <= 0 and total_turnover > 0 and share > 0:
        sector_turnover = round(total_turnover * share / 100, 2)
    updated = dict(current_snapshot)
    updated["date"] = str(current_snapshot.get("date") or target_date or "").strip()
    updated["sector_name"] = primary
    if share > 0:
        updated["turnover_share_pct"] = share
    if sector_turnover > 0:
        updated["sector_turnover"] = sector_turnover
    updated["daily_attack_line"] = primary
    updated["source_status"] = str(current_snapshot.get("source_status") or "attack_evidence").strip()
    return updated


def _sector_names_equal(left, right):
    left = str(left or "").strip()
    right = str(right or "").strip()
    return bool(left and right and (left == right or left in right or right in left))


def build_mainline_turnover_summary(
    *,
    target_date="",
    current_mainline_history_record=None,
    recent_mainline_history=None,
    current_sector_turnover_snapshot=None,
    recent_sector_turnover_history=None,
    sector_attack_evidence_rows=None,
):
    current_record = current_mainline_history_record or {}
    current_snapshot = current_sector_turnover_snapshot or {}
    current_mainline = _pick_current_mainline(current_record)
    attack_evidence_summary = (
        build_mainline_attack_evidence_summary(
            sector_evidence_rows=sector_attack_evidence_rows,
            market_regime=current_record.get("market_regime"),
        )
        if sector_attack_evidence_rows is not None
        else {}
    )
    evidence_primary_line = str((attack_evidence_summary or {}).get("primary_line") or "").strip()
    evidence_relationship = str((attack_evidence_summary or {}).get("relationship_hint") or "").strip()
    if attack_evidence_summary:
        if attack_evidence_summary.get("attack_state") == "confirmed_attack" and evidence_primary_line:
            current_mainline = evidence_primary_line
        elif attack_evidence_summary.get("attack_state") in ("no_attack", "chaotic_rotation", "candidate_attack"):
            current_mainline = ""
    current_snapshot = _snapshot_from_attack_evidence(
        current_snapshot,
        attack_evidence_summary if current_mainline else {},
        target_date,
    )
    previous_mainline = _pick_previous_mainline(recent_mainline_history, current_mainline)
    share_series = _build_share_series(recent_sector_turnover_history, current_snapshot)
    share_trend_label = _resolve_share_trend_label(current_mainline, previous_mainline, share_series)
    conclusion = _build_conclusion(current_mainline, previous_mainline, share_trend_label)
    mainline_path = _build_mainline_path_text(recent_mainline_history, current_mainline)
    share_path = _format_share_series(share_series)
    data_text = f"最近{len(share_series)}日主线 {mainline_path}；成交额占比 {share_path}，节奏偏{share_trend_label}" if mainline_path and share_path else ""

    action_text = _build_action_text(current_mainline, previous_mainline, share_trend_label)
    current_mainline_for_regime = evidence_primary_line if attack_evidence_summary else current_mainline
    current_record_for_regime = dict(current_record)
    if attack_evidence_summary:
        current_record_for_regime["mainline_confirmation_evidence"] = (
            attack_evidence_summary.get("confirmation_evidence") or ""
        )
        if evidence_relationship in ("混沌接力", "双主线竞争"):
            current_record_for_regime["sector_relationship_state"] = evidence_relationship
        if attack_evidence_summary.get("attack_state") in ("no_attack", "chaotic_rotation"):
            current_mainline_for_regime = ""

    capacity_regime_summary = _build_mainline_capacity_regime_summary(
        current_mainline=current_mainline_for_regime,
        current_record=current_record_for_regime,
        current_snapshot=current_snapshot,
        recent_sector_turnover_history=recent_sector_turnover_history,
        action_text=action_text,
    )
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
        "mainline_attack_evidence_summary": attack_evidence_summary,
        "mainline_capacity_regime_summary": capacity_regime_summary,
        "turnover_share_trend_rows": _build_turnover_share_trend_rows(
            recent_sector_turnover_history,
            current_snapshot,
            current_mainline,
        ),
    }
