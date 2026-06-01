from datetime import datetime, timedelta

from report.mainline_turnover_summary_support import (
    normalize_display_text_by_tag_pool,
    render_hot_sector_turnover_watch_grouped_lines,
    resolve_hot_sector_turnover_watch_rows,
    resolve_hot_sector_turnover_watch_summary,
    resolve_mainline_attack_evidence_summary,
    resolve_mainline_capacity_regime_summary,
    resolve_overtake_window_rows,
    resolve_trading_arena_fit_rows,
    resolve_mainline_turnover_summary,
    resolve_turnover_share_trend_rows,
    resolve_turnover_share_trend_summary,
)


_TRADING_DAY_FIELDS = ["monday", "tuesday", "wednesday", "thursday", "friday"]
_STATE_CODE_LABELS = {
    "expand": "爆发",
    "migrate": "切换",
    "probe": "试探",
    "contract": "收缩分歧",
    "observe": "观察",
}


def _display_latest_first(rows):
    return list(reversed(list(rows or [])))


def _full_row(label, current_evidence, derived_judgement, action_effect):
    return f"| {label} | {current_evidence} | {derived_judgement} | {action_effect} |"


def _evidence_table_header_lines():
    return [
        "| 证据环节 | 当前证据 | 推导判断 | 对动作的作用 |",
        "|----------|----------|----------|--------------|",
    ]


def _ensure_evidence_table_header(lines):
    lines = list(lines or [])
    if not lines or not str(lines[0]).startswith("| "):
        return lines
    if len(lines) >= 2 and "---" in str(lines[1]):
        return lines
    return _evidence_table_header_lines() + lines


def _display_text(value, context):
    return normalize_display_text_by_tag_pool(value, context)


def _observation(context):
    observation = context.get("observation")
    return observation if isinstance(observation, dict) else {}


def _benchmark_change(context):
    return float(context.get("benchmark_change", 0) or 0)


def _turnover(context):
    return float(context.get("turnover", 0) or 0)


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return None if default is None else float(default)
        return float(value)
    except (TypeError, ValueError):
        return None if default is None else float(default)


def _risk_preference_action_effect(benchmark_change, turnover, observation):
    dt_count = int(_safe_float(observation.get("dt_count"), 0))
    rise_fall_ratio = _safe_float(observation.get("rise_fall_ratio"), None)
    if rise_fall_ratio is None:
        rise_fall_ratio = _safe_float(observation.get("rise_fall_ratio_text"), None)
    has_heavy_down_pressure = benchmark_change <= -1.5 and (dt_count >= 30 or (rise_fall_ratio is not None and rise_fall_ratio < 0.4))
    if turnover > 0 and has_heavy_down_pressure:
        return "有量配合的下跌更像指数图形走弱后，量化动量和风控卖出互相强化；越跌图形越丑，越丑承接越弱，容易形成踩踏。"
    return "先看风险偏好，再决定能否继续往下判断"


def _short_date(value):
    text = str(value or "").strip()
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        return text[5:10]
    return text or "-"


def _parse_iso_date(value):
    text = str(value or "").strip()
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _week_start(value):
    parsed = _parse_iso_date(value)
    if not parsed:
        return None
    return parsed - timedelta(days=parsed.weekday())


def _weekday_field(value):
    parsed = _parse_iso_date(value)
    if not parsed or parsed.weekday() > 4:
        return None
    return _TRADING_DAY_FIELDS[parsed.weekday()]


def _append_calendar_cell(row, field, cell):
    existing = row.get(field)
    if not existing or existing == {"mainline": "-", "state": "-"}:
        row[field] = cell
    elif isinstance(existing, list):
        existing.append(cell)
    else:
        row[field] = [existing, cell]


def _record_mainline(record):
    return str(
        (record or {}).get("primary_mainline")
        or (record or {}).get("leading_line")
        or (record or {}).get("mainline")
        or (record or {}).get("sector")
        or "-"
    ).strip() or "-"


def _record_state(record):
    record = record or {}
    explicit_state = str(
        record.get("market_state")
        or record.get("state")
        or record.get("status")
        or record.get("structure_state")
        or ""
    ).strip()
    if explicit_state:
        return explicit_state
    rotation_label = str(record.get("rotation_label") or "").strip()
    if rotation_label:
        return rotation_label
    state_code = str(record.get("state_code") or "").strip().lower()
    return _STATE_CODE_LABELS.get(state_code, "观察")


def _format_cycle_calendar_cell(cell):
    if isinstance(cell, (list, tuple)):
        formatted = [_format_cycle_calendar_cell(item) for item in cell]
        return " / ".join([item for item in formatted if item and item != "-"]) or "-"
    if isinstance(cell, dict):
        mainline = str(cell.get("mainline") or cell.get("primary_mainline") or cell.get("sector") or "-").strip()
        state = str(cell.get("state") or cell.get("market_state") or cell.get("status") or "-").strip()
        if not mainline or mainline == "-":
            return "-"
        return f"[{mainline}] {state or '-'}"
    text = str(cell or "-").strip()
    if len(text) >= 6 and text[2] == "-" and text[5] == " ":
        return text[6:].strip() or "-"
    return text or "-"


def _group_mainline_cycles(records):
    groups = []
    for record in records:
        mainline = _record_mainline(record)
        if groups and groups[-1]["mainline"] == mainline:
            groups[-1]["records"].append(record)
        else:
            groups.append({"mainline": mainline, "records": [record]})
    return groups


def _cycle_date_range(records):
    if not records:
        return "-"
    start = _short_date(records[0].get("date"))
    end = _short_date(records[-1].get("date"))
    return start if start == end else f"{start} ~ {end}"


def _cycle_market_state(records):
    states = [_record_state(record) for record in records]
    states = [state for state in states if state and state != "-"]
    if not states:
        return "观察"
    return states[-1] if states[0] == states[-1] else f"{states[0]}后{states[-1]}"


def _cycle_stage(label, group_records, attack_summary=None):
    if label != "当前周期":
        return "已结束周期"
    if _cycle_market_state(group_records) == "逆势攻击":
        return "逆势试攻"
    attack_state = str((attack_summary or {}).get("attack_state") or "").strip()
    if attack_state == "chaotic_rotation":
        return "混沌轮动"
    if attack_state == "no_attack":
        return "无主线"
    if len(group_records or []) <= 1:
        return "切换试攻"
    return "延续验证"


def _cycle_transfer_state(label, group_records, market_state, attack_summary=None):
    if label != "当前周期":
        return "背景观察"
    if str(market_state or "").strip() == "逆势攻击":
        return "逆势试攻"
    attack_state = str((attack_summary or {}).get("attack_state") or "").strip()
    if attack_state == "chaotic_rotation":
        return "混沌轮动"
    if attack_state == "no_attack":
        return "无主线"
    if len(group_records or []) <= 1:
        return "首次攻击"
    text = str(market_state or "")
    if any(marker in text for marker in ("退潮", "衰弱", "分化", "回落")):
        return "延续但衰弱"
    if attack_state == "confirmed_attack":
        return "延续加强"
    return "待二次验证"


def _cycle_tomorrow_validation(label, attack_line, transfer_state):
    if label != "当前周期":
        return "观察是否退成背景线"
    if transfer_state in ("首次攻击", "待二次验证"):
        return f"看{attack_line}是否二次攻击，不能由单日攻击自动升级周期主线"
    if transfer_state == "延续加强":
        return f"看{attack_line}资金排名、涨停扩散和高标反馈能否继续"
    if transfer_state == "延续但衰弱":
        return f"看{attack_line}是否修复资金和高标反馈，否则降为背景线"
    if transfer_state == "混沌轮动":
        return "看是否有单一方向胜出，否则不强定主线"
    if transfer_state == "无主线":
        return "只记录资金是否重新聚焦"
    if transfer_state == "逆势试攻":
        return f"先防踩踏，再看{attack_line}是否修复承接，不能按顺势爆发追"
    return "继续验证传递性"


def _cycle_attack_line(label, group_mainline, attack_summary=None):
    if label != "当前周期":
        return group_mainline
    attack_state = str((attack_summary or {}).get("attack_state") or "").strip()
    primary_line = str((attack_summary or {}).get("primary_line") or "").strip()
    if attack_state == "confirmed_attack" and primary_line:
        return primary_line
    if attack_state == "chaotic_rotation":
        return "混沌轮动"
    if attack_state == "no_attack":
        return "暂无"
    if attack_state == "candidate_attack":
        candidates = (attack_summary or {}).get("candidate_lines") or []
        if candidates:
            return " / ".join([str(item).strip() for item in candidates[:3] if str(item).strip()]) or "候选线"
        return "候选线"
    return group_mainline


def _cycle_interpretation(label, mainline, market_state, attack_line=None, transfer_state=None):
    attack_line = str(attack_line or mainline or "-").strip() or "-"
    if label == "当前周期":
        if transfer_state == "首次攻击":
            return f"{attack_line}今日攻击成立，但传递性仍待二次验证；不自动升级周期主线。"
        if transfer_state == "逆势试攻":
            return f"{attack_line}今日只是放量杀跌中的局部逆势攻击，先按观察主攻线处理，不自动升级周期主线。"
        if transfer_state == "延续加强":
            return f"{attack_line}攻击开始出现传递，市场状态是{market_state}，继续看资金、涨停和高标反馈是否同步。"
        if transfer_state == "延续但衰弱":
            return f"{attack_line}仍有周期痕迹，但市场状态是{market_state}，先按衰弱延续处理。"
        if transfer_state == "混沌轮动":
            return f"当前多线分散，{attack_line}未形成稳定胜出，先按混沌轮动处理。"
        if transfer_state == "无主线":
            return "当前没有清晰攻击线，不强行生成周期主线。"
        return f"{attack_line}处在传递验证阶段，市场状态是{market_state}，先看是否继续攻击。"
    return f"{mainline}主导了上个周期，市场状态从前段推进到{market_state}，当前要观察它是否退成背景线。"


def _pivot_level(row, data=None):
    row = row or {}
    data = data or {}
    return str(
        row.get("pivot_level")
        or row.get("structure_level")
        or row.get("cycle_level")
        or data.get("pivot_level")
        or data.get("structure_level")
        or "日线中枢"
    ).strip() or "日线中枢"


def _mainline_degree(row, pivot_level):
    row = row or {}
    explicit = str(row.get("mainline_degree") or row.get("degree") or row.get("mainline_strength") or "").strip()
    if explicit:
        return explicit
    evolution_text = str(row.get("evolution") or row.get("market_state") or row.get("structure_state") or "").strip()
    if evolution_text == "逆势攻击":
        return "观察主攻线"
    pivot_level = str(pivot_level or "")
    if "大" in pivot_level:
        return "大主线"
    if any(keyword in pivot_level for keyword in ("小", "60", "30", "日内")):
        return "小周期主线"
    return "周期主线"


def _group_evolution(records):
    states = [_record_state(record) for record in records or []]
    states = [state for state in states if state and state != "-"]
    if not states:
        return "待确认"
    return states[-1] if states[0] == states[-1] else f"{states[0]}后{states[-1]}"


def _explicit_or_structural_replacement(row, mainline, previous_mainline=""):
    row = row or {}
    explicit = str(row.get("replacement") or row.get("replacement_relation") or "").strip()
    if explicit:
        return explicit
    if previous_mainline and previous_mainline != mainline:
        return f"接替{previous_mainline}"
    text = " ".join(str(row.get(key) or "") for key in ("evolution", "structure_state", "interpretation", "note"))
    if "接替" in text:
        return "接替前主线"
    if "震荡" in text or "分化" in text:
        return "中枢震荡"
    return "待确认"


def _previous_mainline_for(mainline, groups):
    mainline = str(mainline or "").strip()
    if not mainline:
        return ""
    for index in range(len(groups) - 1, -1, -1):
        if groups[index].get("mainline") == mainline:
            if index > 0:
                return groups[index - 1].get("mainline", "")
            return ""
    return groups[-1].get("mainline", "") if groups else ""


def _structure_interpretation(row):
    if row.get("interpretation"):
        text = str(row.get("interpretation")).strip()
        return text if text.endswith("。") else f"{text}。"
    mainline = str(row.get("mainline") or "当前主线").strip()
    pivot_level = str(row.get("pivot_level") or "日线中枢").strip()
    mainline_degree = str(row.get("mainline_degree") or "周期主线").strip()
    evolution = str(row.get("evolution") or row.get("structure_state") or "待确认").strip()
    replacement = str(row.get("replacement") or "待确认").strip()
    if evolution == "逆势攻击":
        return f"[{mainline}] 只是放量杀跌中的观察主攻线，不按周期主线处理；动作上先防踩踏，再等承接修复。"
    return f"中枢是主线周期载体：[{mainline}] 承载在{pivot_level}，主线程度是{mainline_degree}，当前演化为{evolution}；{replacement}，动作上先看承接是否稳定。"


def _downgrade_pivot_row_for_unconfirmed_attack(pivot_row, attack_summary):
    if not attack_summary or attack_summary.get("attack_state") == "confirmed_attack":
        return pivot_row
    downgraded = dict(pivot_row)
    downgraded["mainline"] = "暂无确认主线"
    downgraded["mainline_degree"] = "待确认"
    downgraded["replacement"] = "待确认"
    evidence = attack_summary.get("confirmation_evidence") or "板块攻击证据不足"
    downgraded["interpretation"] = f"中枢只记录候选方向，不把单日热度升级为周期主线；{evidence}。"
    return downgraded


def derive_market_research_cycle_layer(data, state_machine=None):
    data = data or {}
    state_machine = state_machine or {}
    records = list(data.get("recent_mainline_history") or [])
    current_record = data.get("current_mainline_history_record") or {}
    if current_record:
        records.append(current_record)
    records = [record for record in records if isinstance(record, dict) and record.get("date")]
    records = sorted(records, key=lambda item: str(item.get("date") or ""))

    groups = _group_mainline_cycles(records)
    calendar_rows = []
    selected_groups = groups[-5:]
    selected_records = records[-25:]
    calendar_row_by_week = {}
    for record in selected_records:
        field = _weekday_field(record.get("date"))
        week_start = _week_start(record.get("date"))
        if not field or not week_start:
            continue
        week_key = week_start.isoformat()
        row = calendar_row_by_week.setdefault(week_key, {"week_label": f"{_short_date(week_key)}当周"})
        _append_calendar_cell(
            row,
            field,
            {"date": _short_date(record.get("date")), "mainline": _record_mainline(record), "state": _record_state(record)},
        )
    for week_key in sorted(calendar_row_by_week):
        row = calendar_row_by_week[week_key]
        for field in _TRADING_DAY_FIELDS:
            row.setdefault(field, {"mainline": "-", "state": "-"})
        calendar_rows.append(row)

    cycle_rows = []
    attack_summary = resolve_mainline_attack_evidence_summary(data)
    total_groups = len(selected_groups)
    for index, group in enumerate(selected_groups):
        if index == total_groups - 1:
            label = "当前周期"
        else:
            label = f"近5周期-{index + 1}"
        market_state = _cycle_market_state(group["records"])
        attack_line = _cycle_attack_line(label, group["mainline"], attack_summary)
        cycle_stage = _cycle_stage(label, group["records"], attack_summary)
        transfer_state = _cycle_transfer_state(label, group["records"], market_state, attack_summary)
        cycle_rows.append(
            {
                "cycle_label": label,
                "date_range": _cycle_date_range(group["records"]),
                "trading_days": f"{len(group['records'])}日",
                "mainline": group["mainline"],
                "attack_line": attack_line,
                "cycle_stage": cycle_stage,
                "transfer_state": transfer_state,
                "market_state": market_state,
                "tomorrow_validation": _cycle_tomorrow_validation(label, attack_line, transfer_state),
                "interpretation": _cycle_interpretation(label, group["mainline"], market_state, attack_line, transfer_state),
            }
        )

    pivot_rows = []
    source_pivot_rows = list(data.get("pivot_mainline_history") or data.get("pivot_mainline_rows") or [])[-3:]
    for row in source_pivot_rows:
        if not isinstance(row, dict):
            continue
        mainline = row.get("mainline") or row.get("primary_mainline") or state_machine.get("leading_line") or "-"
        level = _pivot_level(row, data)
        previous_mainline = _previous_mainline_for(mainline, groups)
        pivot_row = {
            "date_range": row.get("date_range") or "-",
            "pivot_level": level,
            "pivot_range": row.get("pivot_range") or row.get("central_range") or "-",
            "position": row.get("position") or "中枢内",
            "structure_state": row.get("structure_state") or "结构待确认",
            "mainline": mainline,
            "mainline_degree": _mainline_degree(row, level),
            "evolution": row.get("evolution") or row.get("market_state") or row.get("structure_state") or "待确认",
            "replacement": _explicit_or_structural_replacement(row, mainline, previous_mainline),
        }
        pivot_row["interpretation"] = _structure_interpretation({**row, **pivot_row})
        pivot_row = _downgrade_pivot_row_for_unconfirmed_attack(pivot_row, attack_summary)
        pivot_rows.append(pivot_row)
    if not pivot_rows and cycle_rows:
        current = cycle_rows[-1]
        current_group = selected_groups[-1] if selected_groups else {"records": []}
        previous_mainline = selected_groups[-2]["mainline"] if len(selected_groups) > 1 else ""
        level = _pivot_level({}, data)
        evolution = data.get("evolution") or _group_evolution(current_group.get("records", [])) or state_machine.get("energy_state") or "待确认"
        pivot_row = {
            "date_range": current.get("date_range", "-"),
            "pivot_level": level,
            "pivot_range": data.get("pivot_range") or "-",
            "position": data.get("pivot_position") or "中枢内",
            "structure_state": data.get("structure_state") or state_machine.get("energy_state") or "结构待确认",
            "mainline": current.get("mainline", "-"),
            "mainline_degree": _mainline_degree({**data, "evolution": evolution}, level),
            "evolution": evolution,
            "replacement": _explicit_or_structural_replacement(data, current.get("mainline", "-"), previous_mainline),
        }
        pivot_row["interpretation"] = _structure_interpretation(pivot_row)
        pivot_row = _downgrade_pivot_row_for_unconfirmed_attack(pivot_row, attack_summary)
        pivot_rows.append(pivot_row)

    return {
        "cycle_calendar_rows": calendar_rows,
        "cycle_interpretation_rows": cycle_rows,
        "pivot_mainline_rows": pivot_rows,
    }


def build_market_research_snapshot_header_node(context, node_meta=None, node_lookup=None):
    return {"lines": ["### 🔬 市场研究快照"], "exports": {}, "module_logs": []}


def build_market_research_snapshot_table_header_node(context, node_meta=None, node_lookup=None):
    if context.get("compact"):
        return {"lines": [], "exports": {}, "module_logs": []}
    return {
        "lines": _evidence_table_header_lines(),
        "exports": {},
        "module_logs": [],
    }


def build_market_research_snapshot_risk_preference_node(context, node_meta=None, node_lookup=None):
    observation = _observation(context)
    benchmark_change = _benchmark_change(context)
    turnover = _turnover(context)
    action_effect = _risk_preference_action_effect(benchmark_change, turnover, observation)
    if context.get("compact"):
        lines = [
            (
                f"- **盘面风险偏好**: 上证{benchmark_change:+.2f}% / 涨停{observation.get('zt_count', 0)} / "
                f"跌停{observation.get('dt_count', 0)} / 涨跌比{observation.get('rise_fall_ratio_text', '暂无')} / 成交额{turnover:.0f}亿；{action_effect}"
            )
        ]
    else:
        lines = [
            _full_row(
                "盘面风险偏好",
                "热点/趋势/异常",
                (
                    f"上证{benchmark_change:+.2f}% / 涨停{observation.get('zt_count', 0)} / "
                    f"跌停{observation.get('dt_count', 0)} / 涨跌比{observation.get('rise_fall_ratio_text', '暂无')} / 成交额{turnover:.0f}亿"
                ),
                action_effect,
            )
        ]
    return {"lines": lines, "exports": {}, "module_logs": []}


def _build_turnover_share_trend_table_lines(context):
    hot_rows = resolve_hot_sector_turnover_watch_rows(context)
    hot_summary = resolve_hot_sector_turnover_watch_summary(context)
    rows = resolve_turnover_share_trend_rows(context)
    if not hot_rows and not rows:
        return []
    summary = resolve_turnover_share_trend_summary(context)
    lines = []
    if hot_rows:
        lines.append("#### 近期热点板块成交额连续跟踪")
        if hot_summary:
            lines.append(f"> {hot_summary}")
            lines.append("")
        lines.extend(render_hot_sector_turnover_watch_grouped_lines(hot_rows))
    if not rows:
        return lines
    lines.append("#### 主线切换成交额记录")
    if summary:
        lines.append(f"> {summary}")
        lines.append("")
    lines.extend(
        [
            "| 日期 | 周期主线 | 当天主攻线 | 主线成交额 | 两市成交额 | 占比 | 占比变化 | 解读 |",
            "|------|----------|------------|------------|------------|------|----------|------|",
        ]
    )
    for row in _display_latest_first(rows):
        lines.append(
            "| {date} | {cycle_mainline} | {daily_attack_line} | {mainline_turnover} | {market_turnover} | {share} | {share_change} | {interpretation} |".format(
                **row
            )
        )
    lines.append("")
    return lines


def _build_mainline_attack_evidence_table_lines(context):
    from report.mainline_turnover_summary_support import resolve_mainline_attack_evidence_rows

    rows = resolve_mainline_attack_evidence_rows(context)
    if not rows:
        return []
    lines = [
        "#### 主线攻击证据",
        "| 板块 | 攻击状态 | 净流入排名 | 净流入 | 涨停数 | 高标高度 | 成交占比变化 | 结论 |",
        "|------|----------|------------|--------|--------|----------|--------------|------|",
    ]
    for row in rows[:3]:
        lines.append(
            "| {sector_name} | {attack_state} | {net_inflow_rank} | {net_inflow_amount} | {limit_up_count} | {high_anchor_height} | {turnover_share_change} | {conclusion} |".format(
                **row
            )
        )
    return lines


def _build_overtake_window_table_lines(context):
    rows = resolve_overtake_window_rows(context)
    if not rows:
        return []
    lines = [
        "#### 超车窗口判断",
        "| 观察成熟度 | 对手方向 | 对手弱化证据 | 我方方向 | 我方承接证据 | 超车逻辑 | 主战场边界 | 失速差 | 不成立条件 | 明日验证 |",
        "|------------|----------|--------------|----------|--------------|----------|------------|--------|------------|----------|",
    ]
    for row in rows[:1]:
        lines.append(
            "| {observation_maturity} | {rival_line} | {rival_slowdown} | {own_line} | {own_stability} | {overtake_logic} | {arena_boundary} | {speed_gap} | {failure_condition} | {action} |".format(
                **row
            )
        )
    return lines


def _build_trading_arena_fit_table_lines(context):
    rows = resolve_trading_arena_fit_rows(context)
    if not rows:
        return []
    lines = [
        "#### 能力圈匹配判断",
        "| 适配位置 | 行情类型 | 适配理由 | 明日动作 |",
        "|----------|----------|----------|----------|",
    ]
    for row in rows[:1]:
        lines.append(
            "| {arena_label} | {market_style} | {fit_reason} | {action} |".format(
                **row
            )
        )
    return lines


def build_market_research_snapshot_mainline_focus_node(context, node_meta=None, node_lookup=None):
    attack_summary = resolve_mainline_attack_evidence_summary(context)
    competition_result = context.get("competition_result", "主线待定")
    competition_evidence = context.get("competition_evidence", "先看趋势密度、异常承接和资金聚焦谁先胜出")
    action_effect = "优先聚焦主线对象"
    if attack_summary and attack_summary.get("attack_state") == "confirmed_attack":
        primary_line = str(attack_summary.get("primary_line") or "").strip()
        if primary_line:
            competition_result = f"主攻线 {primary_line}"
            competition_evidence = attack_summary.get("confirmation_evidence") or f"{primary_line}攻击证据成立"
    elif attack_summary and attack_summary.get("attack_state") != "confirmed_attack":
        competition_result = "无确认主攻线"
        competition_evidence = attack_summary.get("confirmation_evidence") or "主线攻击证据不足"
        action_effect = "候选只观察，不给买入资格"
    if context.get("compact"):
        lines = [f"- **主线焦点**: {competition_result}；{competition_evidence}"]
    else:
        lines = [_full_row("主线焦点", competition_result, competition_evidence, action_effect)]
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_market_research_snapshot_mainline_turnover_node(context, node_meta=None, node_lookup=None):
    summary = resolve_mainline_turnover_summary(context)
    if not summary:
        return {"lines": [], "exports": {}, "module_logs": []}

    if context.get("compact"):
        detail_bits = [summary.get("conclusion", "-")]
        if summary.get("data_text") and summary["data_text"] != "-":
            detail_bits.append(summary["data_text"])
        if summary.get("action_text") and summary["action_text"] != "-":
            detail_bits.append(summary["action_text"])
        lines = [f"- **{summary.get('label', '主线更替与成交额占比')}**: {'；'.join(detail_bits)}"]
    else:
        lines = [
            _full_row(
                summary.get("label", "主线更替与成交额占比"),
                summary.get("conclusion", "-"),
                summary.get("data_text", "-"),
                summary.get("action_text", "-"),
            )
        ]
    lines.extend(_build_turnover_share_trend_table_lines(context))
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_market_research_snapshot_mainline_capacity_regime_node(context, node_meta=None, node_lookup=None):
    summary = resolve_mainline_capacity_regime_summary(context)
    if not summary:
        return {"lines": [], "exports": {}, "module_logs": []}
    lines = [
        "### 4. 主线容量与格局判断",
        "| 主线容量 | 主线格局 | 主攻线 | 竞争线/背景线 | 主线确认依据 | 板块关系状态 | 主线进程 | 明日动作 |",
        "|----------|----------|--------|----------------|--------------|--------------|----------|----------|",
        (
            "| {mainline_capacity} | {mainline_regime} | {primary_line} | {other_lines} | "
            "{confirmation_evidence} | {sector_relationship_state} | {mainline_process} | {tomorrow_action} |"
        ).format(**summary),
    ]
    lines.extend(_build_mainline_attack_evidence_table_lines(context))
    lines.extend(_build_overtake_window_table_lines(context))
    lines.extend(_build_trading_arena_fit_table_lines(context))
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_market_research_snapshot_lhb_capital_intent_node(context, node_meta=None, node_lookup=None):
    breakdown = context.get("capital_intent_breakdown") or {}
    status = context.get("lhb_capital_status") or {}
    conclusion = context.get("capital_conclusion") or {}
    if not breakdown and not status and not conclusion:
        return {"lines": [], "exports": {}, "module_logs": []}

    lines = []
    if breakdown:
        lines.extend(
            [
                "#### 资金意图拆解",
                "| 板块攻击资金 | 强度反馈 | 龙虎榜验证 | 资金一致性 | 明日含义 |",
                "|--------------|----------|------------|------------|----------|",
                "| {sector_fund_attitude} | {strength_feedback} | {lhb_validation} | {capital_consistency} | {tomorrow_meaning} |".format(
                    sector_fund_attitude=breakdown.get("sector_fund_attitude", "-"),
                    strength_feedback=breakdown.get("strength_feedback", "-"),
                    lhb_validation=breakdown.get("lhb_validation", "-"),
                    capital_consistency=breakdown.get("capital_consistency", "-"),
                    tomorrow_meaning=breakdown.get("tomorrow_meaning", "-"),
                ),
            ]
        )
    if status:
        lines.extend(
            [
                "#### 龙虎榜资金状态",
                "| 资金强弱 | 资金力度 | 资金方向 | 资金意图 | 风格转向 | 事件属性 |",
                "|----------|----------|----------|----------|----------|----------|",
                "| {capital_strength} | {capital_intensity} | {capital_direction} | {capital_intent} | {style_shift} | {event_attribute} |".format(
                    capital_strength=status.get("capital_strength", "-"),
                    capital_intensity=status.get("capital_intensity", "-"),
                    capital_direction=status.get("capital_direction", "-"),
                    capital_intent=status.get("capital_intent", "-"),
                    style_shift=status.get("style_shift", "-"),
                    event_attribute=status.get("event_attribute", "-"),
                ),
            ]
        )
    if conclusion:
        lines.extend(
            [
                "#### 资金结论",
                "| 当前资金状态 | 对主线的态度 | 对明日动作的含义 |",
                "|--------------|--------------|------------------|",
                "| {current_capital_state} | {mainline_attitude} | {tomorrow_action_meaning} |".format(
                    current_capital_state=conclusion.get("current_capital_state", "-"),
                    mainline_attitude=conclusion.get("mainline_attitude", "-"),
                    tomorrow_action_meaning=conclusion.get("tomorrow_action_meaning", "-"),
                ),
            ]
        )
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_market_research_snapshot_cycle_calendar_node(context, node_meta=None, node_lookup=None):
    rows = context.get("cycle_calendar_rows") or []
    if not rows:
        return {"lines": [], "exports": {}, "module_logs": []}

    lines = [
        "### 1. 周期日历主视图",
        "| 周次 | 一 | 二 | 三 | 四 | 五 |",
        "|------|------|------|------|------|------|",
    ]
    for row in rows:
        lines.append(
            "| {week_label} | {monday} | {tuesday} | {wednesday} | {thursday} | {friday} |".format(
                week_label=row.get("week_label", "-"),
                monday=_format_cycle_calendar_cell(row.get("monday", "-")),
                tuesday=_format_cycle_calendar_cell(row.get("tuesday", "-")),
                wednesday=_format_cycle_calendar_cell(row.get("wednesday", "-")),
                thursday=_format_cycle_calendar_cell(row.get("thursday", "-")),
                friday=_format_cycle_calendar_cell(row.get("friday", "-")),
            )
        )
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_market_research_snapshot_cycle_interpretation_node(context, node_meta=None, node_lookup=None):
    rows = context.get("cycle_interpretation_rows") or []
    if not rows:
        return {"lines": [], "exports": {}, "module_logs": []}

    lines = [
        "### 2. 周期解读",
        "| 周期 | 时间段 | 交易日数 | 攻击线 | 周期阶段 | 传递性 | 市场状态 | 明日验证点 | 周期解读 |",
        "|------|------|------|------|------|------|------|------|------|",
    ]
    for row in rows:
        lines.append(
            "| {cycle_label} | {date_range} | {trading_days} | {attack_line} | {cycle_stage} | {transfer_state} | {market_state} | {tomorrow_validation} | {interpretation} |".format(
                cycle_label=row.get("cycle_label", "-"),
                date_range=row.get("date_range", "-"),
                trading_days=row.get("trading_days", "-"),
                attack_line=row.get("attack_line") or row.get("mainline", "-"),
                cycle_stage=row.get("cycle_stage") or ("已结束周期" if row.get("cycle_label") != "当前周期" else "待验证"),
                transfer_state=row.get("transfer_state") or ("背景观察" if row.get("cycle_label") != "当前周期" else "待二次验证"),
                market_state=row.get("market_state", "-"),
                tomorrow_validation=row.get("tomorrow_validation") or ("观察是否退成背景线" if row.get("cycle_label") != "当前周期" else "验证是否二次攻击"),
                interpretation=_structure_interpretation(row),
            )
        )
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_market_research_snapshot_pivot_mainline_interpretation_node(context, node_meta=None, node_lookup=None):
    rows = context.get("pivot_mainline_rows") or []
    if not rows:
        return {"lines": [], "exports": {}, "module_logs": []}

    lines = [
        "### 3. 中枢与主线解读",
        "| 时间段 | 中枢级别 | 中枢区间 | 所在位置 | 对应主线 | 主线程度 | 演化状态 | 接替关系 | 结构解读 |",
        "|------|------|------|------|------|------|------|------|------|",
    ]
    for row in rows:
        lines.append(
            "| {date_range} | {pivot_level} | {pivot_range} | {position} | {mainline} | {mainline_degree} | {evolution} | {replacement} | {interpretation} |".format(
                date_range=row.get("date_range", "-"),
                pivot_level=row.get("pivot_level", "-"),
                pivot_range=row.get("pivot_range", "-"),
                position=row.get("position", "-"),
                mainline=row.get("mainline", "-"),
                mainline_degree=row.get("mainline_degree", "-"),
                evolution=row.get("evolution", "-"),
                replacement=row.get("replacement", "-"),
                interpretation=row.get("interpretation", "-"),
            )
        )
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_market_research_snapshot_rotation_node(context, node_meta=None, node_lookup=None):
    if context.get("compact"):
        return {"lines": [], "exports": {}, "module_logs": []}
    attack_summary = resolve_mainline_attack_evidence_summary(context)
    turnover_summary = resolve_mainline_turnover_summary(context)
    if str((context.get("mainline_turnover_summary") or {}).get("share_trend_label") or "").strip() == "逆势试攻":
        return {
            "lines": _ensure_evidence_table_header([
                _full_row(
                    "主线内部轮动",
                    context.get("rotation_label", "-"),
                    turnover_summary.get("conclusion", "-") if turnover_summary else context.get("rotation_summary_text", "-"),
                    turnover_summary.get("action_text", "-") if turnover_summary else context.get("rotation_action", "-"),
                )
            ]),
            "exports": {},
            "module_logs": [],
        }
    if attack_summary and attack_summary.get("attack_state") != "confirmed_attack":
        attack_state = attack_summary.get("attack_state")
        rotation_label = "混沌轮动" if attack_state == "chaotic_rotation" else "候选轮动"
        if attack_state == "no_attack":
            rotation_label = "无主线"
        return {
            "lines": _ensure_evidence_table_header([
                _full_row(
                    "主线内部轮动",
                    rotation_label,
                    attack_summary.get("confirmation_evidence") or "板块攻击证据不足",
                    "不围着单一方向做减法，只保留候选观察",
                )
            ]),
            "exports": {},
            "module_logs": [],
        }
    return {
        "lines": _ensure_evidence_table_header([
            _full_row(
                "主线内部轮动",
                context.get("rotation_label", "-"),
                _display_text(context.get("rotation_summary_text", "-") or context.get("rotation_reason", "-"), context),
                _display_text(context.get("rotation_action", "-"), context),
            )
        ]),
        "exports": {},
        "module_logs": [],
    }


def build_market_research_snapshot_narrative_node(context, node_meta=None, node_lookup=None):
    if context.get("compact"):
        return {"lines": [], "exports": {}, "module_logs": []}
    attack_summary = resolve_mainline_attack_evidence_summary(context)
    turnover_summary = resolve_mainline_turnover_summary(context)
    if str((context.get("mainline_turnover_summary") or {}).get("share_trend_label") or "").strip() == "逆势试攻":
        return {
            "lines": [
                _full_row(
                    "叙事节点",
                    "逆势观察",
                    turnover_summary.get("conclusion", "-") if turnover_summary else "局部方向只按逆势观察处理",
                    turnover_summary.get("action_text", "-") if turnover_summary else "先防踩踏，再看次日是否修复承接",
                )
            ],
            "exports": {},
            "module_logs": [],
        }
    if attack_summary and attack_summary.get("attack_state") != "confirmed_attack":
        return {
            "lines": [
                _full_row(
                    "叙事节点",
                    "叙事待验证",
                    "题材只能做背景，先看板块攻击证据是否胜出",
                    "不把节点热度当主线确认",
                )
            ],
            "exports": {},
            "module_logs": [],
        }
    return {
        "lines": [
            _full_row(
                "叙事节点",
                context.get("narrative_label", "-"),
                _display_text(context.get("narrative_reason", "-"), context),
                _display_text(context.get("narrative_action", "-"), context),
            )
        ],
        "exports": {},
        "module_logs": [],
    }


def build_market_research_snapshot_style_background_node(context, node_meta=None, node_lookup=None):
    style_label = context.get("style_label", "-")
    style_reason = context.get("style_reason", "-")
    style_evidence_text = context.get("style_evidence_text", "-") or style_reason
    if context.get("compact"):
        lines = [f"- **风格背景**: {style_label}；{style_reason}"]
    else:
        lines = [_full_row("风格背景", style_label, style_evidence_text, "背景参考，不直接触发动作")]
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_market_research_snapshot_abnormal_projection_node(context, node_meta=None, node_lookup=None):
    abnormal_label = context.get("abnormal_projection_label", "-")
    abnormal_reason = context.get("abnormal_projection_reason", "-")
    if str(abnormal_label).strip() == "异常观察为空":
        abnormal_label = "未形成样本"
    if context.get("compact"):
        lines = [f"- **异常承接证据**: {abnormal_label}；{abnormal_reason}"]
    else:
        lines = [_full_row("异常承接证据", abnormal_label, abnormal_reason, "允许继续进入下一步判断")]
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_market_research_snapshot_follow_verdict_node(context, node_meta=None, node_lookup=None):
    follow_label = context.get("follow_verdict_label", "-")
    follow_reason = context.get("follow_verdict_reason", "-")
    if context.get("compact"):
        lines = [f"- **明天能不能开仓**: {follow_label}；{follow_reason}"]
    else:
        lines = [_full_row("明天能不能开仓", follow_label, follow_reason, "动作锚定到“明天能不能开仓”")]
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_market_research_snapshot_state_summary_node(context, node_meta=None, node_lookup=None):
    lines = []
    if not context.get("compact"):
        lines.append("")
    lines.append(
        f"- **统一状态判断**: {context.get('state_energy', '-')}；{context.get('state_reason', '-')}；{_display_text(context.get('state_flow_direction', '-'), context)}"
    )
    market_performance = context.get("market_performance_evidence") or {}
    if market_performance:
        boundary = market_performance.get("decision_boundary") or "单指标不直接给买入或加仓。"
        lines.append(f"- **市场表现证据**: {market_performance.get('summary', '-')}；{boundary}")
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_market_research_snapshot_leader_memory_node(context, node_meta=None, node_lookup=None):
    if context.get("compact"):
        return {"lines": [], "exports": {}, "module_logs": []}
    observation = _observation(context)
    return {
        "lines": [
            f"- **龙头记忆**: 已保留{observation.get('leader_memory_count', 0)}只龙头回看资产，另有二次确认观察{observation.get('trusted_tracking_count', 0)}只"
        ],
        "exports": {},
        "module_logs": [],
    }


def build_market_research_snapshot_trend_density_node(context, node_meta=None, node_lookup=None):
    if context.get("compact"):
        return {"lines": [], "exports": {}, "module_logs": []}
    observation = _observation(context)
    if not observation.get("densest_sector"):
        return {"lines": [], "exports": {}, "module_logs": []}
    return {
        "lines": [
            f"- **最强趋势密度**: {_display_text(observation.get('densest_sector'), context)} 当前有{observation.get('densest_sector_trend_count', 0)}只活跃趋势股"
        ],
        "exports": {},
        "module_logs": [],
    }


def build_market_research_snapshot_style_note_node(context, node_meta=None, node_lookup=None):
    if context.get("compact") or not context.get("style_reason"):
        return {"lines": [], "exports": {}, "module_logs": []}
    return {"lines": [f"- **风格说明**: {context.get('style_reason')}"], "exports": {}, "module_logs": []}


def build_market_research_snapshot_dialectical_decision_node(context, node_meta=None, node_lookup=None):
    dialectical_decision = context.get("dialectical_decision") or {}
    if context.get("compact") or not dialectical_decision:
        return {"lines": [], "exports": {}, "module_logs": []}
    lines = [
        "### 🧠 辩证决策补充",
        f"- **现在更像什么阶段**: {dialectical_decision.get('stage_label', '-')}；{dialectical_decision.get('stage_reason', '-')}",
        f"- **指数和赚钱效应是否背离**: {dialectical_decision.get('index_profit_relation', '-')}；{dialectical_decision.get('index_profit_reason', '-')}",
        f"- **背离后怎么处理**: {dialectical_decision.get('index_profit_action', '-')}",
        f"- **赚钱效应现在往哪聚**: {_display_text(dialectical_decision.get('focus_label', '-'), context)}；{_display_text(dialectical_decision.get('focus_action', '-'), context)}",
        f"- **明天优先看哪类对象**: {dialectical_decision.get('candidate_focus', '-')}；{dialectical_decision.get('candidate_action', '-')}",
        f"- **什么情况下先不认这轮修复**: {_display_text(' / '.join(dialectical_decision.get('falsification_conditions', []) or ['暂无']), context)}",
    ]
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_market_research_snapshot_footer_node(context, node_meta=None, node_lookup=None):
    return {"lines": [""], "exports": {}, "module_logs": []}
