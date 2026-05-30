from report.mainline_turnover_summary_support import (
    resolve_mainline_capacity_regime_summary,
    resolve_overtake_window_summary,
    resolve_turnover_share_trend_rows,
)
from report.surface_wording import sanitize_user_visible_text


_GLUE_REGIMES = {"无主线", "混沌轮动", "混沌接力"}
_GLUE_TURNOVER_QUALITIES = {"杀跌放量", "缩量", "待累计"}
_REPLACEMENT_REGIMES = {"双主线竞争", "主线+背景线", "交替竞争"}


def build_market_research_snapshot_market_capacity_evolution_node(context, node_meta=None, node_lookup=None):
    context = context or {}
    capacity_summary = resolve_mainline_capacity_regime_summary(context)
    if not _has_capacity_summary(capacity_summary):
        return _empty_node()

    overtake_summary = resolve_overtake_window_summary(context)
    window_state = _first_value(context.get("window_state"), overtake_summary.get("window_state"))
    mainline_regime = _first_value(context.get("mainline_regime"), capacity_summary.get("mainline_regime"))
    turnover_quality = _text(context.get("turnover_quality"), "待确认")
    phase = _evolution_phase(window_state, mainline_regime, turnover_quality)

    lines = [
        "### 市场容量演化",
        f"- **当前阶段**: {phase}",
        "#### 成交量状态",
        f"- **容量读数**: {_turnover_state_text(context, turnover_quality, capacity_summary)}",
        "#### 板块竞争关系",
        f"- 主攻线: {_text(_first_value(capacity_summary.get('primary_line'), overtake_summary.get('own_line'), overtake_summary.get('primary_line')))}",
        f"- 竞争线/背景线: {_text(_first_value(capacity_summary.get('other_lines'), overtake_summary.get('rival_line')))}",
        f"- 板块关系状态: {_text(capacity_summary.get('sector_relationship_state'))}",
        "#### 演化判断",
    ]
    lines.extend(_evolution_judgement_lines(context, capacity_summary, overtake_summary, window_state))
    lines.extend(["#### 明日观察", *_tomorrow_observation_lines(phase)])
    return {"lines": lines, "exports": {}, "module_logs": []}


def _empty_node():
    return {"lines": [], "exports": {}, "module_logs": []}


def _has_capacity_summary(summary):
    summary = summary or {}
    return any(
        _has_meaningful_text(summary.get(key))
        for key in (
            "mainline_capacity",
            "mainline_regime",
            "primary_line",
            "confirmation_evidence",
            "sector_relationship_state",
            "mainline_process",
        )
    )


def _has_meaningful_text(value):
    text = str(value or "").strip()
    return bool(text and text not in {"-", "暂无"})


def _evolution_phase(window_state, mainline_regime, turnover_quality):
    window_state = str(window_state or "").strip()
    mainline_regime = str(mainline_regime or "").strip()
    turnover_quality = str(turnover_quality or "").strip()
    if not turnover_quality or turnover_quality == "待确认":
        return "待确认"
    if window_state == "open" and mainline_regime == "单主线聚焦" and turnover_quality == "做多放量":
        return "分化期（趋势确立）"
    if window_state == "confirm_next" or mainline_regime in _REPLACEMENT_REGIMES:
        return "接替期（竞争关系）"
    if window_state == "observe" or mainline_regime in _GLUE_REGIMES or turnover_quality in _GLUE_TURNOVER_QUALITIES:
        return "粘合期"
    return "待确认"


def _turnover_state_text(context, turnover_quality, capacity_summary):
    parts = [f"两市成交额: {_format_amount(_first_value(context.get('turnover'), context.get('total_turnover')))}"]
    average_turnover = _first_value(context.get("turnover_ma5"), context.get("avg_turnover_5d"))
    if average_turnover not in (None, ""):
        parts.append(f"近5日平均: {_format_amount(average_turnover)}")
    parts.append(f"成交量质量: {_text(turnover_quality)}")
    rise_fall = _rise_fall_text(context)
    if rise_fall:
        parts.append(f"涨跌比: {rise_fall}")
    parts.append(f"主线容量: {_text(capacity_summary.get('mainline_capacity'))}")
    return "；".join(parts)


def _evolution_judgement_lines(context, capacity_summary, overtake_summary, window_state):
    lines = [
        f"- **主线进程**: {_text(capacity_summary.get('mainline_process'))}",
        f"- **窗口观察**: {_text(window_state)}",
        f"- **容量证据**: {_text(_first_value(context.get('capacity_evidence'), capacity_summary.get('confirmation_evidence')))}",
    ]
    trend_text = _latest_turnover_share_trend_text(context)
    if trend_text:
        lines.append(f"- **最近占比**: {trend_text}")
    extra_parts = []
    for key in ("rival_slowdown", "own_stability", "action"):
        value = _text(overtake_summary.get(key), "")
        if value and value != "-" and value not in extra_parts:
            extra_parts.append(value)
    if extra_parts:
        lines.append(f"- **接替线索**: {'；'.join(extra_parts)}")
    return lines


def _latest_turnover_share_trend_text(context):
    rows = resolve_turnover_share_trend_rows(_context_with_safe_trend_rows(context))
    if not rows:
        return ""
    latest_rows = list(reversed(rows[-2:]))
    labels = []
    for row in latest_rows:
        labels.append(
            "{date} {cycle_mainline}/{daily_attack_line} {share}（{share_change}）".format(
                date=_text(row.get("date")),
                cycle_mainline=_text(row.get("cycle_mainline")),
                daily_attack_line=_text(row.get("daily_attack_line")),
                share=_text(row.get("share")),
                share_change=_text(row.get("share_change")),
            )
        )
    return "；".join(labels)


def _context_with_safe_trend_rows(context):
    context = dict(context or {})
    if "turnover_share_trend_rows" in context:
        context["turnover_share_trend_rows"] = _list_of_dicts(context.get("turnover_share_trend_rows"))
    summary = context.get("mainline_turnover_summary")
    if isinstance(summary, dict) and "turnover_share_trend_rows" in summary:
        safe_summary = dict(summary)
        safe_summary["turnover_share_trend_rows"] = _list_of_dicts(summary.get("turnover_share_trend_rows"))
        context["mainline_turnover_summary"] = safe_summary
    return context


def _tomorrow_observation_lines(phase):
    if phase == "粘合期":
        return [
            "- 两市成交额重新放大且主攻线胜出，再看接替是否成立。",
            "- 候选线成交占比连续抬升，才提高主攻线确认度。",
            "- 若缩量或多方向轮动延续，继续按粘合期观察。",
        ]
    if phase == "接替期（竞争关系）":
        return [
            "- 主攻线持续放量且成交占比继续抬升，接替才算延续。",
            "- 竞争线/背景线反超或主攻线承接走弱，继续按接替期观察。",
            "- 若两市成交额明显低于近5日平均，先看是否回到粘合期。",
        ]
    if phase == "分化期（趋势确立）":
        return [
            "- 主攻线持续拉升且成交占比抬升，确认分化延续。",
            "- 后排承接不能塌，否则分化转弱。",
            "- 缩量回落到近5日平均下方，观察是否回到粘合期。",
        ]
    return [
        "- 等主攻线、竞争线和成交量质量给出一致信号。",
        "- 成交占比连续两日抬升，才提高确认度。",
    ]


def _rise_fall_text(context):
    market_stats = _dict_or_empty(context.get("market_stats"))
    up_count = _first_value(market_stats.get("up_count"), context.get("up_count"))
    down_count = _first_value(market_stats.get("down_count"), context.get("down_count"))
    if up_count not in (None, "") and down_count not in (None, ""):
        return f"{_text(up_count)}/{_text(down_count)}"
    observation = _dict_or_empty(context.get("observation"))
    return _text(_first_value(observation.get("rise_fall_ratio_text"), context.get("rise_fall_ratio_text")), "")


def _format_amount(value):
    if value in (None, ""):
        return "暂无"
    text = str(value).strip().replace(",", "")
    if any(unit in text for unit in ("亿", "万", "元")):
        return _text(value)
    try:
        return f"{float(text):.0f}亿"
    except (TypeError, ValueError):
        return _text(value)


def _first_value(*values):
    for value in values:
        if value not in (None, ""):
            return value
    return ""


def _dict_or_empty(value):
    return value if isinstance(value, dict) else {}


def _list_of_dicts(value):
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _text(value, default="-"):
    if value in (None, ""):
        return default
    return str(sanitize_user_visible_text(value)).strip() or default
