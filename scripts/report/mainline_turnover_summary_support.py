from knowledge.sector_narrative_alias import (
    merge_sector_evidence_rows_by_narrative,
    normalize_sector_list_by_narrative,
)


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


_NON_DIRECTIONAL_SECTOR_LABELS = {
    "HS",
    "GEM",
    "STAR",
    "BJ",
    "SH",
    "SZ",
    "沪深",
    "创业板",
    "科创板",
    "北交所",
    "未知",
    "未归类",
    "-",
}


def _is_directional_sector_label(value):
    label = str(value or "").strip()
    return bool(label and label not in _NON_DIRECTIONAL_SECTOR_LABELS)


def resolve_double_mainline_summary(context=None):
    context = context or {}
    summary = dict(context.get("double_mainline_summary") or {})
    source = dict(context.get("mainline_turnover_summary") or {})
    if not summary:
        summary = dict(source.get("double_mainline_summary") or {})

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


def _string_list(value):
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or "").strip()
    if not text:
        return []
    return [part.strip() for part in text.replace("，", ",").split(",") if part.strip()]


def _directional_string_list(value):
    return [item for item in _string_list(value) if _is_directional_sector_label(item)]


def resolve_mainline_attack_evidence_summary(context=None):
    source = _normalized_attack_source(context)
    if not source:
        return {}
    primary_line = str(source.get("primary_line") or "").strip()
    return {
        "attack_state": str(source.get("attack_state") or "-").strip() or "-",
        "primary_line": primary_line if _is_directional_sector_label(primary_line) else "",
        "candidate_lines": _directional_string_list(source.get("candidate_lines")),
        "background_lines": _directional_string_list(source.get("background_lines")),
        "relationship_hint": str(source.get("relationship_hint") or "-").strip() or "-",
        "evidence_labels": _string_list(source.get("evidence_labels")),
        "confirmation_evidence": str(source.get("confirmation_evidence") or "-").strip() or "-",
        "evidence_gaps": _string_list(source.get("evidence_gaps")),
    }


def _format_rank(value):
    try:
        rank = int(float(value))
    except (TypeError, ValueError):
        return "-"
    return f"第{rank}" if rank > 0 and rank < 999 else "-"


def _format_signed_amount_yi(value):
    if value in (None, ""):
        return "-"
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return "-"
    return f"{amount:+.2f}亿"


def _format_plain_count(value):
    if value in (None, ""):
        return "-"
    try:
        return str(int(float(value)))
    except (TypeError, ValueError):
        return "-"


def _format_signed_pct_change(value):
    if value in (None, ""):
        return "-"
    try:
        change = float(value)
    except (TypeError, ValueError):
        return "-"
    return f"{change:+.1f}pct"


def _attack_state_label(summary, row):
    sector = str((row or {}).get("sector_name") or "").strip()
    attack_state = str((summary or {}).get("attack_state") or "").strip()
    primary = str((summary or {}).get("primary_line") or "").strip()
    if sector and primary and sector == primary and attack_state == "confirmed_attack":
        return "确认主攻线"
    if sector in _directional_string_list((summary or {}).get("candidate_lines")):
        return "候选线"
    if sector in _directional_string_list((summary or {}).get("background_lines")):
        return "背景线"
    if attack_state == "chaotic_rotation":
        return "混沌轮动"
    if attack_state == "no_attack":
        return "无主线"
    if attack_state == "candidate_attack":
        return "候选线"
    return "观察线"


def _attack_row_conclusion(summary, row, state_label):
    sector = str((row or {}).get("sector_name") or "").strip() or "暂无"
    if state_label == "确认主攻线":
        return str((summary or {}).get("confirmation_evidence") or f"{sector}攻击证据成立").strip()
    if state_label == "候选线":
        return f"{sector}仍是候选线，证据不足以确认主攻线"
    if state_label == "背景线":
        return f"{sector}只做背景观察"
    if state_label == "混沌轮动":
        return f"{sector}局部活跃，但资金未明显胜出"
    if state_label == "无主线":
        return str((summary or {}).get("confirmation_evidence") or "资金未形成明确进攻方向").strip()
    return f"{sector}保留观察"


def _attack_source_summary(context):
    context = context or {}
    source = dict(context.get("mainline_attack_evidence_summary") or {})
    if not source:
        source = dict((context.get("mainline_turnover_summary") or {}).get("mainline_attack_evidence_summary") or {})
    return source


def _normalized_attack_source(context):
    source = _attack_source_summary(context)
    if not source:
        return {}
    normalized = dict(source)
    source_rows = [row for row in source.get("sector_evidence_rows") or [] if isinstance(row, dict)]
    context_terms = []
    for row in source_rows:
        context_terms.append((row or {}).get("sector_name"))
        context_terms.extend((row or {}).get("surface_sector_names") or [])
    normalized_rows = merge_sector_evidence_rows_by_narrative(source_rows)
    normalized["sector_evidence_rows"] = normalized_rows
    primary_lines = normalize_sector_list_by_narrative([source.get("primary_line")], context_terms or source_rows)
    normalized["primary_line"] = primary_lines[0] if primary_lines else ""
    normalized["candidate_lines"] = normalize_sector_list_by_narrative(
        source.get("candidate_lines"),
        context_terms or source_rows,
    )
    normalized["background_lines"] = normalize_sector_list_by_narrative(
        source.get("background_lines"),
        context_terms or source_rows,
    )
    return normalized


def _snapshot_terms(group):
    terms = []
    for key in ("采用名称", "当日主攻分支", "大方向"):
        value = str((group or {}).get(key) or "").strip()
        if value:
            terms.append(value)
    for key in ("表层行业名", "辅助名称"):
        terms.extend([str(item or "").strip() for item in ((group or {}).get(key) or []) if str(item or "").strip()])
    return terms


def _snapshot_groups(context):
    if not isinstance(context, dict):
        return []
    snapshot = context.get("realtime_tag_evidence_snapshot") or {}
    if not snapshot:
        snapshot = ((context.get("sector_ai_analysis") or {}).get("realtime_tag_evidence_snapshot") or {})
    if not snapshot:
        snapshot = ((context.get("market_research_snapshot") or {}).get("realtime_tag_evidence_snapshot") or {})
    if not snapshot:
        snapshot = (((context.get("data") or {}).get("sector_ai_analysis") or {}).get("realtime_tag_evidence_snapshot") or {})
    if not snapshot:
        snapshot = ((context.get("data") or {}).get("realtime_tag_evidence_snapshot") or {})
    return [group for group in (snapshot.get("groups") or []) if isinstance(group, dict)]


def _map_label_by_tag_snapshot(label, context=None):
    label = str(label or "").strip()
    if not label:
        return ""
    for group in _snapshot_groups(context or {}):
        if str(group.get("关系判断") or "") == "证据不足":
            continue
        adopted = str(group.get("采用名称") or "").strip()
        if not adopted:
            continue
        terms = _snapshot_terms(group)
        if any(term and (label == term or label in term or term in label) for term in terms):
            return adopted
    return label


def _has_unwanted_term_prefix(text, start):
    prefix2 = text[max(0, start - 2) : start]
    return prefix2 in {"被动", "主动", "电子"}


def _replace_display_term(text, term, adopted):
    if not text or not term or not adopted or term == adopted:
        return text
    result = []
    cursor = 0
    term_len = len(term)
    while True:
        index = text.find(term, cursor)
        if index < 0:
            result.append(text[cursor:])
            break
        result.append(text[cursor:index])
        before = text[index - 1] if index > 0 else ""
        after_index = index + term_len
        after = text[after_index] if after_index < len(text) else ""
        if term_len <= 2 and _has_unwanted_term_prefix(text, index):
            result.append(term)
        else:
            result.append(adopted)
        cursor = after_index
    return "".join(result)


def normalize_display_text_by_tag_pool(text, context=None):
    normalized = str(text or "")
    groups = _snapshot_groups(context or {})
    replacements = []
    for group in groups:
        if str(group.get("关系判断") or "") == "证据不足":
            continue
        adopted = str(group.get("采用名称") or "").strip()
        if not adopted:
            continue
        for term in _snapshot_terms(group):
            if term and term != adopted:
                replacements.append((term, adopted))
    replacements.sort(key=lambda item: len(item[0]), reverse=True)
    for term, adopted in replacements:
        normalized = _replace_display_term(normalized, term, adopted)
    return normalized


def resolve_display_mainline_name(context=None, fallback=""):
    context = context or {}
    attack_summary = resolve_mainline_attack_evidence_summary(context)
    if attack_summary.get("attack_state") == "confirmed_attack" and attack_summary.get("primary_line"):
        return _map_label_by_tag_snapshot(attack_summary.get("primary_line"), context)

    summary = context.get("mainline_turnover_summary") or {}
    if not summary and isinstance(context.get("data"), dict):
        summary = (context.get("data") or {}).get("mainline_turnover_summary") or {}
    for value in (
        summary.get("current_mainline"),
        (summary.get("mainline_capacity_regime_summary") or {}).get("primary_line"),
        (context.get("current_mainline_history_record") or {}).get("primary_mainline"),
        fallback,
    ):
        mapped = _map_label_by_tag_snapshot(value, context)
        if _is_directional_sector_label(mapped):
            return mapped
    return ""


def _row_value(row, key):
    if key in set((row or {}).get("missing_fields") or []):
        return None
    return (row or {}).get(key)


def resolve_mainline_attack_evidence_rows(context=None, limit=3):
    source = _normalized_attack_source(context)
    if not source:
        return []
    source_rows = [row for row in source.get("sector_evidence_rows") or [] if isinstance(row, dict)]
    source_rows = [
        row
        for row in source_rows
        if _is_directional_sector_label((row or {}).get("sector_name"))
    ]
    if not source_rows:
        primary_line = source.get("primary_line") or ""
        source_rows = [{"sector_name": primary_line}] if _is_directional_sector_label(primary_line) else []

    rows = []
    for row in source_rows[: max(1, int(limit or 3))]:
        state_label = _attack_state_label(source, row)
        rows.append(
            {
                "sector_name": str(row.get("sector_name") or "暂无").strip() or "暂无",
                "attack_state": state_label,
                "net_inflow_rank": _format_rank(_row_value(row, "net_inflow_rank")),
                "net_inflow_amount": _format_signed_amount_yi(_row_value(row, "net_inflow_amount")),
                "limit_up_count": _format_plain_count(_row_value(row, "limit_up_count")),
                "high_anchor_height": _format_plain_count(_row_value(row, "high_anchor_height")),
                "turnover_share_change": _format_signed_pct_change(_row_value(row, "turnover_share_change")),
                "conclusion": _attack_row_conclusion(source, row, state_label),
            }
        )
    return rows


def resolve_mainline_capacity_regime_summary(context=None):
    context = context or {}
    attack_summary = resolve_mainline_attack_evidence_summary(context)
    source = dict(context.get("mainline_capacity_regime_summary") or {})
    if not source:
        source = dict((context.get("mainline_turnover_summary") or {}).get("mainline_capacity_regime_summary") or {})
    if attack_summary and attack_summary.get("attack_state") != "confirmed_attack":
        source = {
            "mainline_capacity": source.get("mainline_capacity") or "容量待确认",
            "mainline_regime": "无主线",
            "primary_line": "暂无",
            "other_lines": source.get("other_lines") or "候选观察",
            "confirmation_evidence": attack_summary.get("confirmation_evidence") or "板块攻击证据不足",
            "sector_relationship_state": "混沌轮动",
            "mainline_process": "无",
            "tomorrow_action": "不强行找主线，只保留候选观察",
        }
    if not source and any(
        key in context
        for key in (
            "mainline_capacity",
            "mainline_regime",
            "primary_line",
            "confirmation_evidence",
            "sector_relationship_state",
            "mainline_process",
            "tomorrow_action",
        )
    ):
        source = dict(context)
    if not source:
        double_summary = resolve_double_mainline_summary(context)
        primary_line = str(double_summary.get("daily_attack_line") or double_summary.get("cycle_mainline") or "").strip()
        if primary_line and primary_line != "-":
            other_line = str(double_summary.get("cycle_mainline") or "").strip()
            if other_line == primary_line:
                other_line = "-"
            source = {
                "mainline_capacity": "容量待累计",
                "mainline_regime": "单主线聚焦" if other_line == "-" else "主线+背景线",
                "primary_line": primary_line,
                "other_lines": other_line or "-",
                "confirmation_evidence": "主线确认依据待补充",
                "sector_relationship_state": double_summary.get("relationship") or "暂未分出",
                "mainline_process": "待观察",
                "tomorrow_action": double_summary.get("tomorrow_action") or "-",
            }
    if not source:
        summary_source = context.get("mainline_turnover_summary") or context
        current_mainline = str((summary_source or {}).get("current_mainline") or "").strip()
        if current_mainline:
            source = {
                "mainline_capacity": "容量待累计",
                "mainline_regime": "单主线聚焦",
                "primary_line": current_mainline,
                "other_lines": "-",
                "confirmation_evidence": "主线确认依据待补充",
                "sector_relationship_state": "暂未分出",
                "mainline_process": "待观察",
                "tomorrow_action": str((summary_source or {}).get("action_text") or "先看主线证据是否继续聚焦").strip(),
            }

    if not source:
        return {}

    return {
        "mainline_capacity": str(source.get("mainline_capacity") or "-").strip() or "-",
        "mainline_regime": str(source.get("mainline_regime") or "-").strip() or "-",
        "primary_line": str(source.get("primary_line") or "-").strip() or "-",
        "other_lines": str(source.get("other_lines") or "-").strip() or "-",
        "confirmation_evidence": str(source.get("confirmation_evidence") or "-").strip() or "-",
        "sector_relationship_state": str(source.get("sector_relationship_state") or "-").strip() or "-",
        "mainline_process": str(source.get("mainline_process") or "-").strip() or "-",
        "tomorrow_action": str(source.get("tomorrow_action") or "-").strip() or "-",
    }


def resolve_overtake_window_summary(context=None):
    context = context or {}
    source = dict(context.get("overtake_window_summary") or {})
    if not source:
        source = dict((context.get("mainline_turnover_summary") or {}).get("overtake_window_summary") or {})
    if not source:
        return {}
    def _extract_line_from_stability(text):
        text = str(text or "").strip()
        for marker in ("资金", "承接", "核心"):
            if marker in text:
                return text.split(marker, 1)[0].strip("，；、 ")
        return ""
    own_line = str(source.get("own_line") or source.get("primary_line") or _extract_line_from_stability(source.get("own_stability")) or "-").strip() or "-"
    failure_condition = str(
        source.get("failure_condition")
        or source.get("invalid_condition")
        or "对手重新放量回流或我方开盘不承接"
    ).strip() or "对手重新放量回流或我方开盘不承接"
    if own_line != "-":
        failure_condition = failure_condition.replace("我方", own_line)
    return {
        "window_state": str(source.get("window_state") or "-").strip() or "-",
        "primary_line": str(source.get("primary_line") or "-").strip() or "-",
        "rival_line": str(source.get("rival_line") or source.get("rival_direction") or "旧主线").strip() or "旧主线",
        "own_line": own_line,
        "rival_slowdown": str(source.get("rival_slowdown") or "-").strip() or "-",
        "own_stability": str(source.get("own_stability") or "-").strip() or "-",
        "observation_maturity": str(source.get("observation_maturity") or "-").strip() or "-",
        "overtake_logic": str(source.get("overtake_logic") or "-").strip() or "-",
        "arena_boundary": str(source.get("arena_boundary") or "-").strip() or "-",
        "speed_gap": str(source.get("speed_gap") or "-").strip() or "-",
        "failure_condition": failure_condition,
        "action": str(source.get("action") or "-").strip() or "-",
        "evidence_labels": _string_list(source.get("evidence_labels")),
        "evidence_gaps": _string_list(source.get("evidence_gaps")),
    }


def resolve_overtake_opening_tone_text(context=None):
    summary = resolve_overtake_window_summary(context)
    if not summary:
        return ""
    parts = []
    for key in ("rival_slowdown", "own_stability", "action"):
        value = str(summary.get(key) or "").strip()
        if value and value != "-" and value not in parts:
            parts.append(value)
    return "；".join(parts)


def resolve_overtake_window_rows(context=None):
    summary = resolve_overtake_window_summary(context)
    if not summary:
        return []
    return [
        {
            "rival_line": summary["rival_line"],
            "rival_slowdown": summary["rival_slowdown"],
            "own_line": summary["own_line"],
            "own_stability": summary["own_stability"],
            "observation_maturity": summary["observation_maturity"],
            "overtake_logic": summary["overtake_logic"],
            "arena_boundary": summary["arena_boundary"],
            "speed_gap": summary["speed_gap"],
            "failure_condition": summary["failure_condition"],
            "action": summary["action"],
        }
    ]


def resolve_trading_arena_fit_summary(context=None):
    context = context or {}
    source = dict(context.get("trading_arena_fit_summary") or {})
    if not source:
        source = dict((context.get("mainline_turnover_summary") or {}).get("trading_arena_fit_summary") or {})
    if not source:
        return {}
    return {
        "fit_state": str(source.get("fit_state") or "-").strip() or "-",
        "arena_label": str(source.get("arena_label") or "-").strip() or "-",
        "market_style": str(source.get("market_style") or "-").strip() or "-",
        "fit_reason": str(source.get("fit_reason") or "-").strip() or "-",
        "action": str(source.get("action") or "-").strip() or "-",
    }


def resolve_trading_arena_fit_rows(context=None):
    summary = resolve_trading_arena_fit_summary(context)
    if not summary:
        return []
    return [
        {
            "arena_label": summary["arena_label"],
            "market_style": summary["market_style"],
            "fit_reason": summary["fit_reason"],
            "action": summary["action"],
        }
    ]


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
        return "待累计"
    return f"{row_share - previous_share:+.1f}pct"


def resolve_turnover_share_trend_rows(context=None):
    context = context or {}
    rows = context.get("turnover_share_trend_rows")
    if rows is None:
        rows = (context.get("mainline_turnover_summary") or {}).get("turnover_share_trend_rows")
    normalized = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        row = row or {}
        normalized_row = {
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
        normalized.append(normalized_row)
    return normalized


def resolve_turnover_share_trend_summary(context=None):
    context = context or {}
    summary = str(context.get("turnover_share_trend_summary") or "").strip()
    if summary:
        return summary
    summary_source = context.get("mainline_turnover_summary") or {}
    if isinstance(summary_source, dict):
        return str(summary_source.get("turnover_share_trend_summary") or "").strip()
    return ""


def resolve_hot_sector_turnover_watch_rows(context=None):
    context = context or {}
    rows = context.get("hot_sector_turnover_watch_rows")
    if rows is None:
        rows = (context.get("mainline_turnover_summary") or {}).get("hot_sector_turnover_watch_rows")
    normalized = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        market_turnover = str(row.get("market_turnover") or row.get("total_turnover") or "-").strip() or "-"
        total_turnover = str(row.get("total_turnover") or row.get("market_turnover") or "-").strip() or "-"
        normalized.append(
            {
                "date": str(row.get("date") or "-").strip() or "-",
                "sector_name": str(row.get("sector_name") or "-").strip() or "-",
                "sector_turnover": str(row.get("sector_turnover") or "-").strip() or "-",
                "market_turnover": market_turnover,
                "total_turnover": total_turnover,
                "share": str(row.get("share") or "-").strip() or "-",
                "share_change": str(row.get("share_change") or "-").strip() or "-",
                "sample_status": str(row.get("sample_status") or "-").strip() or "-",
                "interpretation": str(row.get("interpretation") or "-").strip() or "-",
            }
        )
    return normalized


def resolve_hot_sector_turnover_watch_summary(context=None):
    context = context or {}
    summary = str(context.get("hot_sector_turnover_watch_summary") or "").strip()
    if summary:
        return summary
    summary_source = context.get("mainline_turnover_summary") or {}
    if isinstance(summary_source, dict):
        return str(summary_source.get("hot_sector_turnover_watch_summary") or "").strip()
    return ""
