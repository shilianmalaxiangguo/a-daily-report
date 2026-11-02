from __future__ import annotations

from math import isfinite

from knowledge.sector_narrative_alias import merge_sector_evidence_rows_by_narrative

__all__ = [
    "build_mainline_attack_evidence_summary",
    "build_mainline_turnover_summary",
    "build_overtake_window_summary",
    "build_trading_arena_fit_summary",
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


def _build_share_point_text(recent_sector_turnover_history, current_snapshot):
    rows = list(recent_sector_turnover_history or [])
    if current_snapshot:
        rows.append(current_snapshot)
    points = []
    for item in rows:
        item = item or {}
        share = round(_safe_float(item.get("turnover_share_pct")), 1)
        if share <= 0:
            continue
        sector = str(
            item.get("cycle_mainline")
            or item.get("primary_mainline")
            or item.get("daily_attack_line")
            or item.get("sector_name")
            or "未命名方向"
        ).strip()
        date = str(item.get("date") or item.get("trade_date") or "").strip()
        point = f"{sector} {share:.1f}%"
        if date:
            point = f"{date} {point}"
        points.append(point)
    return "；".join(points[-3:])


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
    if share_trend_label == "逆势试攻":
        return f"{current_mainline}只按观察主攻线处理，先防踩踏，再看次日是否修复承接"
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


def _source_scope_text(item):
    source = str((item or {}).get("source") or (item or {}).get("data_source") or "").strip()
    if source == "tushare.moneyflow_ind_ths":
        return "Tushare行业资金流入+流出"
    if source == "thsdk.market_data_block":
        return "同花顺板块总金额"
    if source == "tencent.fundflow.getHyRank":
        return "腾讯行业资金成交额"
    return ""


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
        return "多线可以同时给资格，但仍要缩到具体固定交易窗口"
    return action_text or "先看主线证据是否继续聚焦"


def _is_countertrend_attack_record(current_record):
    text = " ".join(
        str((current_record or {}).get(key) or "")
        for key in ("rotation_label", "market_state", "state", "rotation_summary")
    )
    return "逆势攻击" in text or "放量杀跌" in text


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
    surface_names = [
        str(item or "").strip()
        for item in (row.get("surface_sector_names") or [])
        if str(item or "").strip()
    ]
    if surface_names:
        normalized["surface_sector_names"] = surface_names
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


def _snapshot_terms(group):
    terms = []
    for key in ("采用名称", "当日主攻分支", "大方向"):
        value = str((group or {}).get(key) or "").strip()
        if value:
            terms.append(value)
    for key in ("表层行业名", "辅助名称"):
        terms.extend([str(item or "").strip() for item in ((group or {}).get(key) or []) if str(item or "").strip()])
    return terms


def _apply_tag_snapshot_to_evidence_rows(rows, snapshot):
    groups = list((snapshot or {}).get("groups") or [])
    if not groups:
        return rows
    patched_rows = []
    for row in rows or []:
        row = dict(row or {})
        row_name = str(row.get("sector_name") or row.get("sector") or "").strip()
        row_terms = [row_name]
        row_terms.extend([str(item or "").strip() for item in (row.get("surface_sector_names") or []) if str(item or "").strip()])
        row_terms.extend([str(item or "").strip() for item in (row.get("concepts") or []) if str(item or "").strip()])
        matched_group = None
        for group in groups:
            if str(group.get("关系判断") or "") == "证据不足":
                continue
            group_terms = _snapshot_terms(group)
            if any(left and right and (left == right or left in right or right in left) for left in row_terms for right in group_terms):
                matched_group = group
                break
        if matched_group:
            adopted = str(matched_group.get("采用名称") or "").strip()
            if adopted:
                surface_names = list(row.get("surface_sector_names") or [])
                if row_name and row_name not in surface_names and row_name != adopted:
                    surface_names.append(row_name)
                for surface in matched_group.get("表层行业名") or []:
                    if surface and surface not in surface_names and surface != adopted:
                        surface_names.append(surface)
                row["sector_name"] = adopted
                row["surface_sector_names"] = surface_names
        patched_rows.append(row)
    return patched_rows


def _tag_snapshot_daily_attack_line(snapshot, *, max_labels=2):
    labels = []
    for group in (snapshot or {}).get("groups") or []:
        if str((group or {}).get("关系判断") or "") == "证据不足":
            continue
        label = str((group or {}).get("当日主攻分支") or (group or {}).get("采用名称") or "").strip()
        if label and label not in labels:
            labels.append(label)
    for label in (snapshot or {}).get("adopted_labels") or []:
        label = str(label or "").strip()
        if label and label not in labels:
            labels.append(label)
    return " / ".join(labels[: max(int(max_labels or 0), 1)])


def build_mainline_attack_evidence_summary(*, sector_evidence_rows=None, market_regime="", realtime_tag_evidence_snapshot=None):
    sector_evidence_rows = _apply_tag_snapshot_to_evidence_rows(sector_evidence_rows or [], realtime_tag_evidence_snapshot)
    rows = [
        _normalize_sector_evidence_row(row)
        for row in merge_sector_evidence_rows_by_narrative(sector_evidence_rows or [])
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


def _overtake_primary_row(attack_summary):
    primary = str((attack_summary or {}).get("primary_line") or "").strip()
    for row in (attack_summary or {}).get("sector_evidence_rows") or []:
        if str((row or {}).get("sector_name") or "").strip() == primary:
            return row
    return {}


def _overtake_rival_rows(attack_summary):
    primary = str((attack_summary or {}).get("primary_line") or "").strip()
    return [
        row
        for row in (attack_summary or {}).get("sector_evidence_rows") or []
        if str((row or {}).get("sector_name") or "").strip() and str((row or {}).get("sector_name") or "").strip() != primary
    ]


def _overtake_row_is_slowing(row):
    row = row or {}
    return (
        _safe_float(row.get("net_inflow_amount")) <= 0
        or _safe_float(row.get("turnover_share_change")) <= -0.5
        or int(_safe_float(row.get("limit_up_count"))) <= 1
        or int(_safe_float(row.get("local_evidence_count"))) <= 1
    )


def _overtake_row_still_competes(row):
    row = row or {}
    return (
        int(_safe_float(row.get("fund_evidence_count"))) > 0
        and int(_safe_float(row.get("strength_evidence_count"))) > 0
    ) or int(_safe_float(row.get("evidence_count"))) >= 3


def _line_list_text(rows):
    names = [str((row or {}).get("sector_name") or "").strip() for row in rows if str((row or {}).get("sector_name") or "").strip()]
    return "、".join(names[:2])


def build_overtake_window_summary(
    *,
    mainline_attack_evidence_summary=None,
    mainline_capacity_regime_summary=None,
    current_mainline_history_record=None,
):
    attack_summary = mainline_attack_evidence_summary or {}
    capacity_summary = mainline_capacity_regime_summary or {}
    current_record = current_mainline_history_record or {}
    attack_state = str(attack_summary.get("attack_state") or "").strip()
    primary_line = str(attack_summary.get("primary_line") or capacity_summary.get("primary_line") or "").strip()
    primary_row = _overtake_primary_row(attack_summary)
    primary_labels = list((primary_row or {}).get("evidence_labels") or attack_summary.get("evidence_labels") or [])
    has_fund = any(label in ("资金净流入靠前", "资金净流入明显领先", "成交占比扩张") for label in primary_labels)
    has_strength = any(label in ("批量涨停", "高标强度突出", "板块普涨", "高涨幅集群") for label in primary_labels)
    own_holds = attack_state == "confirmed_attack" and bool(primary_line) and has_fund and has_strength
    rival_rows = _overtake_rival_rows(attack_summary)
    slowing_rows = [row for row in rival_rows if _overtake_row_is_slowing(row)]
    competing_rows = [row for row in rival_rows if _overtake_row_still_competes(row)]
    has_named_rival = bool(
        str(current_record.get("secondary_mainline") or current_record.get("competition_mainline") or current_record.get("background_mainline") or "").strip()
    )
    rivals_slow = bool(slowing_rows) or (has_named_rival and attack_state == "confirmed_attack" and not competing_rows)

    if attack_state == "confirmed_attack" and own_holds and rivals_slow and not competing_rows:
        return {
            "window_state": "open",
            "primary_line": primary_line,
            "own_line": primary_line,
            "rival_line": _line_list_text(slowing_rows) or str(current_record.get("secondary_mainline") or current_record.get("competition_mainline") or current_record.get("background_mainline") or "旧主线").strip() or "旧主线",
            "rival_slowdown": (
                f"{_line_list_text(slowing_rows) or '旧主线'}承接转弱，竞争线冲高回落"
            ),
            "own_stability": f"{primary_line}资金扩散，核心承接稳定",
            "observation_maturity": "跑过一段后再判断",
            "overtake_logic": "对手过弯打滑，我方仍能弯道加速",
            "arena_boundary": "短线/超短主战场内主动出手",
            "speed_gap": "失速差拉开",
            "failure_condition": f"对手重新放量回流或{primary_line}开盘不承接",
            "action": f"只在{primary_line}核心里找参与资格",
            "evidence_labels": ["对手失速", "我方稳住", "失速差拉开"],
            "evidence_gaps": [],
        }

    if attack_state == "confirmed_attack" and own_holds:
        return {
            "window_state": "confirm_next",
            "primary_line": primary_line,
            "own_line": primary_line,
            "rival_line": _line_list_text(competing_rows) or "旧主线",
            "rival_slowdown": "旧主线或竞争线尚未完全退开" if competing_rows else "对手失速仍待确认",
            "own_stability": f"{primary_line}资金扩散，核心承接稳定",
            "observation_maturity": "还在跑圈确认",
            "overtake_logic": "我方有节奏，但对手打滑仍待确认",
            "arena_boundary": "短线/超短主战场内等待确认",
            "speed_gap": "未拉开",
            "failure_condition": f"对手继续回流或{primary_line}资金扩散降温",
            "action": "等竞价、开盘承接、回封或09:50-10:10窗口",
            "evidence_labels": ["我方稳住"],
            "evidence_gaps": ["对手失速待确认"],
        }

    if attack_state in ("chaotic_rotation", "candidate_attack"):
        candidate_lines = [
            str(item or "").strip()
            for item in attack_summary.get("candidate_lines") or []
            if str(item or "").strip()
        ]
        candidate_text = "、".join(candidate_lines)
        return {
            "window_state": "observe",
            "primary_line": primary_line,
            "own_line": primary_line or candidate_text or "候选方向",
            "rival_line": "多方向",
            "rival_slowdown": "多方向均有局部热度，但资金未明显胜出",
            "own_stability": "当前方向强度不足",
            "observation_maturity": (
                f"{candidate_text}已有局部热度，尚未形成跨日胜出方向"
                if candidate_text
                else "候选方向已有局部热度，尚未形成跨日胜出方向"
            ),
            "overtake_logic": "未形成对手打滑、我方加速的差值",
            "arena_boundary": "不为制造动作扩大战法",
            "speed_gap": "未拉开",
            "failure_condition": "没有单一方向连续胜出",
            "action": "仅观察，不给新增参与资格",
            "evidence_labels": [],
            "evidence_gaps": ["失速差未形成"],
        }

    return {
        "window_state": "no_trade",
        "primary_line": primary_line,
        "own_line": primary_line or "当前方向",
        "rival_line": "旧方向或全市场",
        "rival_slowdown": "旧方向失速或全市场同步走弱",
        "own_stability": "当前方向没有资金和强度扩散",
        "observation_maturity": "不能把全场打滑当超车",
        "overtake_logic": "对手弱但我方也弱，不构成弯道加速",
        "arena_boundary": "先防风险，不扩动作",
        "speed_gap": "未拉开",
        "failure_condition": "资金和强度扩散继续不足",
        "action": "不参与，先防风险",
        "evidence_labels": [],
        "evidence_gaps": ["我方未稳住"],
    }


def build_trading_arena_fit_summary(*, mainline_capacity_regime_summary=None, overtake_window_summary=None):
    capacity_summary = mainline_capacity_regime_summary or {}
    overtake_summary = overtake_window_summary or {}
    regime = str(capacity_summary.get("mainline_regime") or "").strip()
    capacity = str(capacity_summary.get("mainline_capacity") or "").strip()
    primary_line = str(overtake_summary.get("primary_line") or capacity_summary.get("primary_line") or "").strip()
    window_state = str(overtake_summary.get("window_state") or "").strip()
    home_regimes = {"单主线聚焦", "混沌接力", "双主线竞争", "主线+背景线"}
    non_home_markers = ("趋势", "机构", "抱团", "慢推")
    is_non_home = any(marker in regime for marker in non_home_markers) or capacity == "牛市多线容量"
    if window_state == "open" and regime in home_regimes and not is_non_home:
        return {
            "fit_state": "home_arena",
            "arena_label": "短线/超短线主战场",
            "market_style": regime or "主线扩散",
            "fit_reason": "量能、资金扩散、板块效应和核心承接进入短线/超短线可发挥区",
            "action": f"按短线/超短线主战场处理，围绕{primary_line or '主攻线'}核心继续寻找参与资格",
        }
    if is_non_home:
        return {
            "fit_state": "low_fit",
            "arena_label": "非主战场",
            "market_style": regime or capacity or "容量行情",
            "fit_reason": "更接近趋势容量、机构抱团或慢推行情，不是当前短线/超短线主战场",
            "action": "不扩战法，不为证明全能而新增参与，只保持不拖后腿",
        }
    return {
        "fit_state": "neutral_fit",
        "arena_label": "等待主战场",
        "market_style": regime or "未分出",
        "fit_reason": "短线/超短线主战场条件尚未充分展开",
        "action": "继续等量能异常、资金扩散、板块效应和核心承接同时出现",
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
    cycle_mainline = str(
        item.get("cycle_mainline")
        or item.get("primary_mainline")
        or item.get("sector_name")
        or fallback_mainline
        or "-"
    ).strip() or "-"
    row_daily_attack_line = str(
        item.get("daily_attack_line") or item.get("attack_line") or daily_attack_line or cycle_mainline or "-"
    ).strip() or "-"
    source_scope = _source_scope_text(item)
    if source_status == "missing_dependency":
        interpretation = "缺少板块成交额接口，先记录主线归属，成交额占比待后续数据累计"
    elif share > 0:
        prefix = f"{source_scope}口径，" if source_scope else ""
        interpretation = f"{prefix}主线成交额占比可用，继续观察占比抬升或回落"
    else:
        interpretation = "主线成交额占比暂缺，先不据此放大买入资格"
    return {
        "date": str(item.get("date") or "-").strip() or "-",
        "cycle_mainline": cycle_mainline,
        "daily_attack_line": row_daily_attack_line,
        "mainline_turnover": _format_amount_yi(sector_turnover),
        "market_turnover": _format_amount_yi(item.get("total_turnover")),
        "share": _format_share_pct(share),
        "share_change": _format_share_change(share, previous_share),
        "interpretation": interpretation,
    }


def _turnover_row_mainline(item, fallback_mainline=""):
    item = item or {}
    return str(item.get("cycle_mainline") or item.get("primary_mainline") or item.get("sector_name") or fallback_mainline or "").strip()


def _turnover_row_key(item):
    item = item or {}
    return (str(item.get("date") or "").strip(), _turnover_row_mainline(item))


def _limit_turnover_share_source_rows(source_rows, current_mainline, limit=25):
    source_rows = list(source_rows or [])
    if len(source_rows) <= limit:
        return source_rows
    return source_rows[-limit:]


def _build_turnover_share_trend_rows(
    recent_sector_turnover_history,
    current_snapshot,
    current_mainline,
    *,
    current_cycle_mainline="",
    current_daily_attack_line="",
):
    source_rows = list(recent_sector_turnover_history or [])
    if current_snapshot:
        current_item = dict(current_snapshot)
        if current_cycle_mainline and not current_item.get("cycle_mainline"):
            current_item["cycle_mainline"] = current_cycle_mainline
        if current_daily_attack_line and not current_item.get("daily_attack_line"):
            current_item["daily_attack_line"] = current_daily_attack_line
        source_rows.append(current_item)
    rows = []
    previous_share_by_mainline = {}
    for item in _limit_turnover_share_source_rows(source_rows, current_mainline):
        row_mainline = _turnover_row_mainline(item, current_mainline)
        previous_same_mainline = previous_share_by_mainline.get(row_mainline, 0.0)
        row = _build_turnover_share_row(
            item,
            fallback_mainline=current_mainline,
            daily_attack_line="",
            previous_share=previous_same_mainline,
        )
        rows.append(row)
        share = _safe_float((item or {}).get("turnover_share_pct"))
        if share > 0:
            previous_share_by_mainline[row_mainline] = share
    return rows


def _share_points_from_source_rows(source_rows):
    points = []
    for item in source_rows or []:
        share = round(_safe_float((item or {}).get("turnover_share_pct")), 1)
        if share <= 0:
            continue
        points.append(
            {
                "date": str((item or {}).get("date") or "").strip(),
                "sector_name": _turnover_row_mainline(item),
                "share": share,
            }
        )
    return points


def _share_direction_text(delta):
    delta = _safe_float(delta)
    if delta >= 0.5:
        return "主线成交占比抬升，资金聚焦度走强。"
    if delta <= -0.5:
        return "主线成交占比回落，先看重新聚焦能否持续。"
    return "主线成交占比横向震荡，暂按边走边确认处理。"


def _build_turnover_share_trend_summary(recent_sector_turnover_history, current_snapshot, current_mainline):
    source_rows = list(recent_sector_turnover_history or []) + ([current_snapshot] if current_snapshot else [])
    limited_rows = _limit_turnover_share_source_rows(source_rows, current_mainline, limit=25)
    points = _share_points_from_source_rows(limited_rows)
    if not points:
        return "近25个交易日主线成交额占比趋势：关键数据不完整，停止生成趋势判断。"
    shares = [point["share"] for point in points]
    current_share = shares[-1]
    low_share = min(shares)
    high_share = max(shares)
    current_sector = str(points[-1].get("sector_name") or current_mainline or "当日主线").strip() or "当日主线"
    unique_sectors = {
        str(point.get("sector_name") or "").strip()
        for point in points
        if str(point.get("sector_name") or "").strip()
    }
    window_label = f"近{len(limited_rows)}个交易日" if len(limited_rows) == 25 else f"近{len(points)}个有效交易日"
    if len(unique_sectors) > 1:
        return (
            f"{window_label}小周期成交额记录："
            f"当前{current_sector}{current_share:.1f}%，"
            f"样本包含{len(unique_sectors)}个不同方向；"
            "这是小周期方向的成交额记录，不作为大周期主线切换确认。"
        )
    recent_change_text = ""
    if len(shares) >= 5:
        direction_delta = current_share - shares[-5]
        recent_change_text = f"近5日{direction_delta:+.1f}pct，"
    elif len(shares) >= 2:
        direction_delta = current_share - shares[0]
        recent_change_text = f"区间首尾{direction_delta:+.1f}pct，"
    else:
        direction_delta = 0.0
    return (
        f"{window_label}主线成交额占比趋势："
        f"当前{current_share:.1f}%，"
        f"{recent_change_text}"
        f"区间{low_share:.1f}%-{high_share:.1f}%，"
        f"{_share_direction_text(direction_delta)}"
    )


def _is_directional_sector_label(value):
    label = str(value or "").strip()
    return bool(label and label not in {"-", "暂无", "无主线", "混沌轮动", "未知", "未归类"})


def _hot_sector_alias_key(value):
    return str(value or "").strip()


def _hot_sector_display_name(value):
    key = _hot_sector_alias_key(value)
    return key or str(value or "").strip()


def _watch_row_sector_name(item, fallback=""):
    item = item or {}
    return str(
        item.get("cycle_mainline")
        or item.get("primary_mainline")
        or item.get("daily_attack_line")
        or item.get("sector_name")
        or fallback
        or ""
    ).strip()


def _append_unique_sector_name(items, value):
    value = str(value or "").strip()
    alias_key = _hot_sector_alias_key(value)
    if _is_directional_sector_label(value) and alias_key not in {_hot_sector_alias_key(item) for item in items}:
        items.append(_hot_sector_display_name(value))


def _positive_finite_float(value):
    number = _safe_float(value)
    return number if isfinite(number) and number > 0 else 0.0


def _hot_sector_row_matches_target_date(row, target_date=""):
    row = row or {}
    row_date = str(row.get("date") or row.get("trade_date") or "").strip()
    target_date = str(target_date or "").strip()
    return not target_date or not row_date or row_date == target_date


def _has_hot_sector_turnover_evidence(row, *, target_date=""):
    row = row or {}
    if not _hot_sector_row_matches_target_date(row, target_date):
        return False
    share = _positive_finite_float(row.get("turnover_share_pct"))
    sector_turnover = _positive_finite_float(row.get("sector_turnover") or row.get("sector_turnover_yi"))
    if sector_turnover <= 0:
        total_turnover = _positive_finite_float(row.get("total_turnover") or row.get("total_turnover_yi"))
        if total_turnover > 0 and share > 0:
            sector_turnover = round(total_turnover * share / 100, 2)
    return bool(sector_turnover > 0 and share > 0)


def _has_strong_hot_sector_watch_evidence(row, *, target_date=""):
    row = row or {}
    return bool(
        _has_hot_sector_turnover_evidence(row, target_date=target_date)
        and _positive_finite_float(row.get("high_anchor_height")) >= 3
        and _positive_finite_float(row.get("limit_up_count")) >= 2
    )


def _hot_sector_candidate_names(
    *,
    target_date="",
    current_mainline="",
    current_snapshot=None,
    recent_sector_turnover_history=None,
    sector_attack_evidence_rows=None,
    recent_hot_sector_turnover_history=None,
    max_sectors=8,
):
    limit = max(int(max_sectors or 0), 1)
    candidates = []
    _append_unique_sector_name(candidates, _watch_row_sector_name(current_snapshot, current_mainline))
    _append_unique_sector_name(candidates, current_mainline)
    ranked_attack_rows = sorted(
        [row for row in sector_attack_evidence_rows or [] if isinstance(row, dict)],
        key=lambda row: (
            _safe_float(row.get("turnover_share_pct")),
            _safe_float(row.get("sector_turnover") or row.get("sector_turnover_yi")),
            abs(_safe_float(row.get("net_inflow_amount"))),
            _safe_float(row.get("limit_up_count")),
        ),
        reverse=True,
    )
    for row in reversed(list(recent_sector_turnover_history or [])[-8:]):
        _append_unique_sector_name(candidates, _watch_row_sector_name(row))
    for row in ranked_attack_rows:
        _append_unique_sector_name(candidates, _watch_row_sector_name(row))
    for row in reversed(list(recent_hot_sector_turnover_history or [])):
        _append_unique_sector_name(candidates, _watch_row_sector_name(row))

    selected = candidates[:limit]
    protected_keys = {
        _hot_sector_alias_key(_watch_row_sector_name(current_snapshot, current_mainline)),
        _hot_sector_alias_key(current_mainline),
    }
    current_attack_keys = {
        _hot_sector_alias_key(_watch_row_sector_name(row))
        for row in ranked_attack_rows
        if _has_hot_sector_turnover_evidence(row, target_date=target_date)
    }
    strong_attack_names = []
    for row in ranked_attack_rows:
        if _has_strong_hot_sector_watch_evidence(row, target_date=target_date):
            _append_unique_sector_name(strong_attack_names, _watch_row_sector_name(row))
    for strong_name in strong_attack_names:
        strong_key = _hot_sector_alias_key(strong_name)
        if strong_key in {_hot_sector_alias_key(name) for name in selected}:
            continue
        replacement_index = next(
            (
                index
                for index in range(len(selected) - 1, -1, -1)
                if _hot_sector_alias_key(selected[index]) not in protected_keys
                and _hot_sector_alias_key(selected[index]) not in current_attack_keys
            ),
            None,
        )
        if replacement_index is not None:
            selected[replacement_index] = strong_name
    return selected


def _hot_sector_row_key(item):
    return (
        str((item or {}).get("date") or (item or {}).get("trade_date") or "").strip(),
        _hot_sector_alias_key(_watch_row_sector_name(item)),
    )


def _row_has_better_turnover(candidate, existing):
    candidate_turnover = _safe_float((candidate or {}).get("sector_turnover") or (candidate or {}).get("sector_turnover_yi"))
    existing_turnover = _safe_float((existing or {}).get("sector_turnover") or (existing or {}).get("sector_turnover_yi"))
    if candidate_turnover > 0 and existing_turnover <= 0:
        return True
    candidate_total = _safe_float((candidate or {}).get("total_turnover") or (candidate or {}).get("total_turnover_yi"))
    existing_total = _safe_float((existing or {}).get("total_turnover") or (existing or {}).get("total_turnover_yi"))
    return candidate_total > 0 and existing_total <= 0


def _merge_hot_sector_source_row(existing, candidate):
    if not existing:
        return dict(candidate or {})
    if _row_has_better_turnover(candidate, existing):
        merged = dict(candidate or {})
        for key, value in (existing or {}).items():
            if key not in merged or merged.get(key) in (None, "", [], {}):
                merged[key] = value
        return merged
    merged = dict(existing or {})
    for key, value in (candidate or {}).items():
        if key not in merged or merged.get(key) in (None, "", [], {}):
            merged[key] = value
    return merged


def _attack_evidence_row_to_hot_sector_row(row, *, target_date="", total_turnover=0.0):
    row = dict(row or {})
    sector_name = _watch_row_sector_name(row)
    if not _is_directional_sector_label(sector_name):
        return {}
    share = _safe_float(row.get("turnover_share_pct"))
    sector_turnover = _safe_float(row.get("sector_turnover") or row.get("sector_turnover_yi"))
    total_turnover = _safe_float(row.get("total_turnover") or row.get("total_turnover_yi") or total_turnover)
    if sector_turnover <= 0 and total_turnover > 0 and share > 0:
        sector_turnover = round(total_turnover * share / 100, 2)
    return {
        "date": str(row.get("date") or row.get("trade_date") or target_date or "").strip(),
        "sector_name": _hot_sector_display_name(sector_name),
        "sector_turnover": sector_turnover,
        "total_turnover": total_turnover,
        "turnover_share_pct": share,
        "source": str(row.get("source") or row.get("source_policy") or "sector_attack_evidence").strip(),
    }


def _normalize_hot_sector_source_row(row, *, fallback_date="", fallback_total_turnover=0.0):
    row = dict(row or {})
    sector_name = _watch_row_sector_name(row)
    if not _is_directional_sector_label(sector_name):
        return {}
    share = _safe_float(row.get("turnover_share_pct"))
    sector_turnover = _safe_float(row.get("sector_turnover") or row.get("sector_turnover_yi"))
    total_turnover = _safe_float(row.get("total_turnover") or row.get("total_turnover_yi") or fallback_total_turnover)
    if share <= 0 and sector_turnover > 0 and total_turnover > 0:
        share = round(sector_turnover / total_turnover * 100, 2)
    if sector_turnover <= 0 and total_turnover > 0 and share > 0:
        sector_turnover = round(total_turnover * share / 100, 2)
    return {
        "date": str(row.get("date") or row.get("trade_date") or fallback_date or "").strip(),
        "sector_name": _hot_sector_display_name(sector_name),
        "sector_turnover": sector_turnover,
        "total_turnover": total_turnover,
        "turnover_share_pct": share,
        "source": str(row.get("source") or row.get("source_policy") or "").strip(),
    }


def _build_hot_sector_source_rows(
    *,
    target_date="",
    current_snapshot=None,
    recent_sector_turnover_history=None,
    sector_attack_evidence_rows=None,
    recent_hot_sector_turnover_history=None,
):
    current_total_turnover = _safe_float((current_snapshot or {}).get("total_turnover"))
    source_rows = []
    for row in recent_hot_sector_turnover_history or []:
        source_rows.append(_normalize_hot_sector_source_row(row))
    for row in recent_sector_turnover_history or []:
        source_rows.append(_normalize_hot_sector_source_row(row))
    if current_snapshot:
        source_rows.append(_normalize_hot_sector_source_row(current_snapshot, fallback_date=target_date))
    for row in sector_attack_evidence_rows or []:
        source_rows.append(
            _attack_evidence_row_to_hot_sector_row(
                row,
                target_date=target_date,
                total_turnover=current_total_turnover,
            )
        )

    deduped = {}
    for row in source_rows:
        if not row:
            continue
        key = _hot_sector_row_key(row)
        if not key[0] or not key[1]:
            continue
        deduped[key] = _merge_hot_sector_source_row(deduped.get(key), row)
    return list(deduped.values())


def _hot_sector_watch_interpretation(sector_name, share, previous_share):
    if share <= 0:
        return f"{sector_name}成交占比待累计，先不据此放大买入资格"
    if previous_share <= 0:
        return f"{sector_name}只记录本板块当日点位，等待同板块历史继续累计"
    change = share - previous_share
    if change >= 0.5:
        return f"{sector_name}同板块成交占比抬升，资金容量扩张"
    if change <= -0.5:
        return f"{sector_name}同板块成交占比回落，先看承接能否修复"
    return f"{sector_name}同板块成交占比横向震荡，继续观察方向选择"


def _build_hot_sector_watch_row(item, previous_share=0.0):
    item = item or {}
    sector_name = _watch_row_sector_name(item) or "-"
    share = _safe_float(item.get("turnover_share_pct"))
    previous_share = _safe_float(previous_share)
    total_turnover = _format_amount_yi(item.get("total_turnover"))
    return {
        "date": str(item.get("date") or "-").strip() or "-",
        "sector_name": sector_name,
        "sector_turnover": _format_amount_yi(item.get("sector_turnover")),
        "market_turnover": total_turnover,
        "total_turnover": total_turnover,
        "share": _format_share_pct(share),
        "share_change": _format_share_change(share, previous_share),
        "sample_status": "同板块连续" if share > 0 and previous_share > 0 else "待累计",
        "interpretation": _hot_sector_watch_interpretation(sector_name, share, previous_share),
    }


def _limit_hot_sector_watch_rows(rows, candidate_names, *, per_sector_limit=5, total_limit=30):
    by_sector = {}
    for row in rows or []:
        sector = _watch_row_sector_name(row)
        if not sector:
            continue
        by_sector.setdefault(sector, []).append(row)

    limited = []
    for sector in candidate_names or []:
        sector_rows = sorted(
            by_sector.get(sector, []),
            key=lambda item: str((item or {}).get("date") or ""),
        )
        limited.extend(sector_rows[-max(int(per_sector_limit or 0), 1):])
    limited.sort(key=lambda item: (str((item or {}).get("date") or ""), _watch_row_sector_name(item)))
    return limited[-max(int(total_limit or 0), 1):]


def _build_hot_sector_turnover_watch_rows(
    *,
    target_date="",
    current_mainline="",
    current_snapshot=None,
    recent_sector_turnover_history=None,
    sector_attack_evidence_rows=None,
    recent_hot_sector_turnover_history=None,
):
    candidate_names = _hot_sector_candidate_names(
        target_date=target_date,
        current_mainline=current_mainline,
        current_snapshot=current_snapshot,
        recent_sector_turnover_history=recent_sector_turnover_history,
        sector_attack_evidence_rows=sector_attack_evidence_rows,
        recent_hot_sector_turnover_history=recent_hot_sector_turnover_history,
    )
    if not candidate_names:
        return []
    source_rows = _build_hot_sector_source_rows(
        target_date=target_date,
        current_snapshot=current_snapshot,
        recent_sector_turnover_history=recent_sector_turnover_history,
        sector_attack_evidence_rows=sector_attack_evidence_rows,
        recent_hot_sector_turnover_history=recent_hot_sector_turnover_history,
    )
    filtered_rows = [
        row
        for row in source_rows
        if any(_sector_names_equal(_watch_row_sector_name(row), candidate) for candidate in candidate_names)
    ]
    limited_rows = _limit_hot_sector_watch_rows(filtered_rows, candidate_names)
    previous_share_by_sector = {}
    result = []
    for item in limited_rows:
        sector = _watch_row_sector_name(item)
        previous_share = previous_share_by_sector.get(sector, 0.0)
        result.append(_build_hot_sector_watch_row(item, previous_share=previous_share))
        share = _safe_float(item.get("turnover_share_pct"))
        if share > 0:
            previous_share_by_sector[sector] = share
    return result


def _hot_sector_watch_share_float(row):
    text = str((row or {}).get("share") or "").strip().replace("%", "")
    return _safe_float(text)


def _build_hot_sector_turnover_watch_summary(rows):
    rows = [row for row in rows or [] if isinstance(row, dict)]
    if not rows:
        return "近期热点板块成交额连续跟踪：关键数据不完整，停止生成趋势判断。"
    latest_date = max(str((row or {}).get("date") or "") for row in rows)
    latest_rows = [row for row in rows if str(row.get("date") or "") == latest_date]
    latest_rows = sorted(latest_rows, key=_hot_sector_watch_share_float, reverse=True)
    continuous = [row for row in rows if str(row.get("sample_status") or "") == "同板块连续"]
    leader = latest_rows[0] if latest_rows else rows[-1]
    leader_text = f"{leader.get('sector_name', '-')} {leader.get('share', '待累计')}"
    if continuous:
        return (
            f"近期热点板块成交额连续跟踪：当前{latest_date}记录{len(latest_rows)}个热点板块，"
            f"{leader_text}居前；变化只按同一板块自身历史计算。"
        )
    return (
        f"近期热点板块成交额连续跟踪：当前{latest_date}记录{len(latest_rows)}个热点板块，"
        f"{leader_text}居前；同板块历史仍待累计，不跨板块解释涨跌。"
    )


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
    return bool(left and right and _hot_sector_alias_key(left) == _hot_sector_alias_key(right))


def build_mainline_turnover_summary(
    *,
    target_date="",
    current_mainline_history_record=None,
    recent_mainline_history=None,
    current_sector_turnover_snapshot=None,
    recent_sector_turnover_history=None,
    recent_hot_sector_turnover_history=None,
    sector_attack_evidence_rows=None,
    realtime_tag_evidence_snapshot=None,
):
    current_record = current_mainline_history_record or {}
    current_snapshot = current_sector_turnover_snapshot or {}
    current_mainline = _pick_current_mainline(current_record)
    attack_evidence_summary = (
        build_mainline_attack_evidence_summary(
            sector_evidence_rows=sector_attack_evidence_rows,
            market_regime=current_record.get("market_regime"),
            realtime_tag_evidence_snapshot=realtime_tag_evidence_snapshot,
        )
        if sector_attack_evidence_rows is not None
        else {}
    )
    evidence_primary_line = str((attack_evidence_summary or {}).get("primary_line") or "").strip()
    evidence_relationship = str((attack_evidence_summary or {}).get("relationship_hint") or "").strip()
    tag_daily_attack_line = _tag_snapshot_daily_attack_line(realtime_tag_evidence_snapshot)
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
    is_countertrend_attack = bool(current_mainline and _is_countertrend_attack_record(current_record))
    share_series = _build_share_series(recent_sector_turnover_history, current_snapshot)
    share_trend_label = _resolve_share_trend_label(current_mainline, previous_mainline, share_series)
    if is_countertrend_attack:
        share_trend_label = "逆势试攻"
        conclusion = f"{current_mainline}只是放量杀跌中的观察主攻线，不按周期主线切换处理"
    else:
        conclusion = _build_conclusion(current_mainline, previous_mainline, share_trend_label)
    mainline_path = _build_mainline_path_text(recent_mainline_history, current_mainline)
    share_path = _format_share_series(share_series)
    mainline_path_parts = [part.strip() for part in mainline_path.split("->") if part.strip()]
    has_mixed_mainline_path = len(set(mainline_path_parts)) > 1
    if mainline_path and share_path and (share_trend_label == "切换" or has_mixed_mainline_path):
        share_point_text = _build_share_point_text(recent_sector_turnover_history, current_snapshot)
        data_text = (
            f"近期被记录方向分列：{share_point_text}；这些是各自板块点位，不做连续涨跌判断"
            if share_point_text
            else f"最近{len(share_series)}日主线 {mainline_path}；成交额占比为各自板块点位，节奏偏切换"
        )
    else:
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
    if is_countertrend_attack:
        current_record_for_regime["mainline_regime"] = "观察主攻线"
        current_record_for_regime["sector_relationship_state"] = "逆势试攻"
        current_record_for_regime["mainline_process"] = "逆势试攻"
        current_record_for_regime["mainline_regime_action"] = action_text

    capacity_regime_summary = _build_mainline_capacity_regime_summary(
        current_mainline=current_mainline_for_regime,
        current_record=current_record_for_regime,
        current_snapshot=current_snapshot,
        recent_sector_turnover_history=recent_sector_turnover_history,
        action_text=action_text,
    )
    overtake_window_summary = build_overtake_window_summary(
        mainline_attack_evidence_summary=attack_evidence_summary,
        mainline_capacity_regime_summary=capacity_regime_summary,
        current_mainline_history_record=current_record_for_regime,
    )
    trading_arena_fit_summary = build_trading_arena_fit_summary(
        mainline_capacity_regime_summary=capacity_regime_summary,
        overtake_window_summary=overtake_window_summary,
    )
    hot_sector_watch_rows = _build_hot_sector_turnover_watch_rows(
        target_date=target_date,
        current_mainline=current_mainline,
        current_snapshot=current_snapshot,
        recent_sector_turnover_history=recent_sector_turnover_history,
        sector_attack_evidence_rows=sector_attack_evidence_rows,
        recent_hot_sector_turnover_history=recent_hot_sector_turnover_history,
    )
    cycle_mainline = previous_mainline if is_countertrend_attack and previous_mainline else (current_mainline or "-")
    daily_attack_line = tag_daily_attack_line or current_mainline or "-"
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
            "cycle_mainline": cycle_mainline,
            "daily_attack_line": daily_attack_line,
            "relationship": (
                f"{current_mainline}只是放量杀跌中的观察主攻线，不按周期主线处理"
                if is_countertrend_attack and current_mainline
                else f"{tag_daily_attack_line}只是当日观察分支，不按周期主线处理"
                if tag_daily_attack_line and not current_mainline
                else f"{tag_daily_attack_line}是当天主攻线，{current_mainline}仍按周期主线观察"
                if tag_daily_attack_line and current_mainline and tag_daily_attack_line != current_mainline
                else "周期主线与当天主攻线一致" if current_mainline else "主线待确认"
            ),
            "tomorrow_action": action_text,
        },
        "mainline_attack_evidence_summary": attack_evidence_summary,
        "mainline_capacity_regime_summary": capacity_regime_summary,
        "overtake_window_summary": overtake_window_summary,
        "trading_arena_fit_summary": trading_arena_fit_summary,
        "turnover_share_trend_summary": _build_turnover_share_trend_summary(
            recent_sector_turnover_history,
            current_snapshot,
            current_mainline,
        ),
        "turnover_share_trend_rows": _build_turnover_share_trend_rows(
            recent_sector_turnover_history,
            current_snapshot,
            current_mainline,
            current_cycle_mainline=previous_mainline if is_countertrend_attack and previous_mainline else current_mainline,
            current_daily_attack_line=tag_daily_attack_line or current_mainline,
        ),
        "hot_sector_turnover_watch_summary": _build_hot_sector_turnover_watch_summary(hot_sector_watch_rows),
        "hot_sector_turnover_watch_rows": hot_sector_watch_rows,
    }
