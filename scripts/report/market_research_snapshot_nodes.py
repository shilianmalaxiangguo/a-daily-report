from datetime import datetime, timedelta

from report.mainline_turnover_summary_support import resolve_mainline_turnover_summary, resolve_turnover_share_trend_rows


_TRADING_DAY_FIELDS = ["monday", "tuesday", "wednesday", "thursday", "friday"]


def _full_row(label, current_evidence, derived_judgement, action_effect):
    return f"| {label} | {current_evidence} | {derived_judgement} | {action_effect} |"


def _observation(context):
    return context.get("observation") or {}


def _benchmark_change(context):
    return float(context.get("benchmark_change", 0) or 0)


def _turnover(context):
    return float(context.get("turnover", 0) or 0)


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
    return str(
        (record or {}).get("market_state")
        or (record or {}).get("state")
        or (record or {}).get("status")
        or (record or {}).get("structure_state")
        or "观察"
    ).strip() or "观察"


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


def _cycle_interpretation(label, mainline, market_state):
    if label == "当前周期":
        return f"{mainline}正在承担当前周期的主线观察任务，市场状态是{market_state}，先看承接能否继续稳定。"
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
    return f"中枢是主线周期载体：[{mainline}] 承载在{pivot_level}，主线程度是{mainline_degree}，当前演化为{evolution}；{replacement}，动作上先看承接是否稳定。"


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
    selected_groups = groups[-2:]
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
    labels = ["上个周期", "当前周期"] if len(selected_groups) > 1 else ["当前周期"]
    for label, group in zip(labels, selected_groups):
        market_state = _cycle_market_state(group["records"])
        cycle_rows.append(
            {
                "cycle_label": label,
                "date_range": _cycle_date_range(group["records"]),
                "trading_days": f"{len(group['records'])}日",
                "mainline": group["mainline"],
                "market_state": market_state,
                "interpretation": _cycle_interpretation(label, group["mainline"], market_state),
            }
        )

    pivot_rows = []
    for row in data.get("pivot_mainline_history") or data.get("pivot_mainline_rows") or []:
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
            "mainline_degree": _mainline_degree(data, level),
            "evolution": evolution,
            "replacement": _explicit_or_structural_replacement(data, current.get("mainline", "-"), previous_mainline),
        }
        pivot_row["interpretation"] = _structure_interpretation(pivot_row)
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
        "lines": [
            "| 证据环节 | 当前证据 | 推导判断 | 对动作的作用 |",
            "|----------|----------|----------|--------------|",
        ],
        "exports": {},
        "module_logs": [],
    }


def build_market_research_snapshot_risk_preference_node(context, node_meta=None, node_lookup=None):
    observation = _observation(context)
    benchmark_change = _benchmark_change(context)
    turnover = _turnover(context)
    if context.get("compact"):
        lines = [
            (
                f"- **盘面风险偏好**: 上证{benchmark_change:+.2f}% / 涨停{observation.get('zt_count', 0)} / "
                f"跌停{observation.get('dt_count', 0)} / 涨跌比{observation.get('rise_fall_ratio_text', '暂无')} / 成交额{turnover:.0f}亿"
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
                "先看风险偏好，再决定能否继续往下判断",
            )
        ]
    return {"lines": lines, "exports": {}, "module_logs": []}


def _build_turnover_share_trend_table_lines(context):
    rows = resolve_turnover_share_trend_rows(context)
    if not rows:
        return []
    lines = [
        "#### 主线成交额占比趋势",
        "| 日期 | 周期主线 | 当天主攻线 | 主线成交额 | 两市成交额 | 占比 | 占比变化 | 解读 |",
        "|------|----------|------------|------------|------------|------|----------|------|",
    ]
    for row in rows:
        lines.append(
            "| {date} | {cycle_mainline} | {daily_attack_line} | {mainline_turnover} | {market_turnover} | {share} | {share_change} | {interpretation} |".format(
                **row
            )
        )
    return lines


def build_market_research_snapshot_mainline_focus_node(context, node_meta=None, node_lookup=None):
    competition_result = context.get("competition_result", "主线待定")
    competition_evidence = context.get("competition_evidence", "先看趋势密度、异常承接和资金聚焦谁先胜出")
    if context.get("compact"):
        lines = [f"- **主线焦点**: {competition_result}；{competition_evidence}"]
    else:
        lines = [_full_row("主线焦点", competition_result, competition_evidence, "优先聚焦主线对象")]
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


def build_market_research_snapshot_lhb_capital_intent_node(context, node_meta=None, node_lookup=None):
    status = context.get("lhb_capital_status") or {}
    conclusion = context.get("capital_conclusion") or {}
    if not status and not conclusion:
        return {"lines": [], "exports": {}, "module_logs": []}

    lines = []
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
        "| 周期 | 时间段 | 交易日数 | 主导主线 | 市场状态 | 周期解读 |",
        "|------|------|------|------|------|------|",
    ]
    for row in rows:
        lines.append(
            "| {cycle_label} | {date_range} | {trading_days} | {mainline} | {market_state} | {interpretation} |".format(
                cycle_label=row.get("cycle_label", "-"),
                date_range=row.get("date_range", "-"),
                trading_days=row.get("trading_days", "-"),
                mainline=row.get("mainline", "-"),
                market_state=row.get("market_state", "-"),
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
    return {
        "lines": [
            _full_row(
                "主线内部轮动",
                context.get("rotation_label", "-"),
                context.get("rotation_summary_text", "-") or context.get("rotation_reason", "-"),
                context.get("rotation_action", "-"),
            )
        ],
        "exports": {},
        "module_logs": [],
    }


def build_market_research_snapshot_narrative_node(context, node_meta=None, node_lookup=None):
    if context.get("compact"):
        return {"lines": [], "exports": {}, "module_logs": []}
    return {
        "lines": [
            _full_row(
                "叙事节点",
                context.get("narrative_label", "-"),
                context.get("narrative_reason", "-"),
                context.get("narrative_action", "-"),
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
        f"- **统一状态判断**: {context.get('state_energy', '-')}；{context.get('state_reason', '-')}；{context.get('state_flow_direction', '-')}"
    )
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
            f"- **最强趋势密度**: {observation.get('densest_sector')} 当前有{observation.get('densest_sector_trend_count', 0)}只活跃趋势股"
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
        f"- **赚钱效应现在往哪聚**: {dialectical_decision.get('focus_label', '-')}；{dialectical_decision.get('focus_action', '-')}",
        f"- **明天优先看哪类对象**: {dialectical_decision.get('candidate_focus', '-')}；{dialectical_decision.get('candidate_action', '-')}",
        f"- **什么情况下先不认这轮修复**: {' / '.join(dialectical_decision.get('falsification_conditions', []) or ['暂无'])}",
    ]
    return {"lines": lines, "exports": {}, "module_logs": []}


def build_market_research_snapshot_footer_node(context, node_meta=None, node_lookup=None):
    return {"lines": [""], "exports": {}, "module_logs": []}
