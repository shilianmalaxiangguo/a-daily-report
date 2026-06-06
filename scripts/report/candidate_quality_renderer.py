from __future__ import annotations


PANEL_FIELDS = [
    "市场情绪状态",
    "账户后台任务负担",
    "持仓优先动作",
    "今日新增上限",
    "主买对象",
    "补位对象",
    "禁止动作",
    "忽略清单",
]

CANDIDATE_TABLE_FIELDS = [
    "候选",
    "当前持仓",
    "可卖数量",
    "不可卖数量",
    "仓位性质",
    "账户状态",
    "计划仓位档",
    "实际仓位",
    "仓位偏离",
    "周期身份",
    "选股质量",
    "买点质量",
    "风险项",
    "成本项",
    "动作上限",
    "持仓动作",
    "新开仓动作",
    "恢复条件",
    "取关条件",
    "最晚复核",
]

COMPACT_CANDIDATE_TABLE_FIELDS = [
    "候选",
    "账户状态",
    "计划仓位档",
    "实际仓位",
    "当前持仓",
    "可卖数量",
    "选股质量",
    "买点质量",
    "动作上限",
    "新开仓动作",
]

COMPACT_TRACE_FIELDS = ["层级", "候选", "主线/板块", "板块锚反推", "为什么进入这一层", "卡点", "明日动作"]

FULL_TRACE_FIELDS = ["层级", "候选", "来源池", "主线/板块", "板块锚反推", "关键输入", "满足条件", "未满足/缺失", "分支结果", "明日动作", "失效条件"]

SINGLE_STOCK_FIELDS = [
    "当前上涨发动机",
    "市场辨识度",
    "趋势审美",
    "价格行为与承接",
    "选股质量",
    "买点质量",
    "账户状态",
    "计划仓位档",
    "实际仓位",
    "仓位偏离",
    "风险项",
    "成本项",
    "动作上限",
    "持仓动作",
    "新开仓动作",
    "恢复条件",
    "取关条件",
    "最坏情境",
    "触发条件",
    "应对动作",
    "一句话纪律",
]


def _cell(value):
    text = "" if value is None else str(value)
    return text.replace("\n", " ").replace("|", "／")


def _heading(level, title):
    level = min(6, max(1, int(level or 1)))
    return f"{'#' * level} {title}"


def _single_stock_cell(field, value):
    text = _cell(value)
    prefix = f"{field}："
    if field in ("风险项", "成本项") and text.startswith(prefix):
        return text[len(prefix) :]
    return text


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [item for item in value if item not in (None, "")]
    return [value] if value != "" else []


def _join_values(values, separator="、"):
    return separator.join(_cell(value) for value in _as_list(values) if _cell(value))


def _render_panel(panel, heading_level=3):
    visible_fields = (panel or {}).get("visible_fields", {}) or {}
    lines = [_heading(heading_level, "今日总决策面板"), "", "| 字段 | 内容 |", "|------|------|"]
    for field in PANEL_FIELDS:
        lines.append(f"| {field} | {_cell(visible_fields.get(field, ''))} |")
    return lines


def _render_candidate_table(contracts, heading_level=3, table_fields=None):
    table_fields = list(table_fields or CANDIDATE_TABLE_FIELDS)
    lines = [_heading(heading_level, "候选主表"), ""]
    if not contracts:
        lines.append("暂无候选进入动作分层。")
        return lines

    lines.append("| " + " | ".join(table_fields) + " |")
    lines.append("|" + "|".join(["------"] * len(table_fields)) + "|")
    for contract in contracts:
        row = (contract or {}).get("visible_row", {}) or {}
        lines.append("| " + " | ".join(_cell(row.get(field, "")) for field in table_fields) + " |")
    return lines


def _contract_trace(contract):
    return (contract or {}).get("trace", {}) or {}


def _trace_candidate_label(contract, trace):
    name = (trace or {}).get("stock_name", "")
    code = (trace or {}).get("stock_code", "")
    if name and code:
        return f"{name}({code})"
    if name or code:
        return name or code
    row = (contract or {}).get("visible_row", {}) or {}
    return row.get("候选", "暂无")


def _trace_mainline_sector(trace):
    mainline = (trace or {}).get("mainline", "")
    sector = (trace or {}).get("sector", "")
    if mainline and sector and mainline != sector:
        return f"{mainline}/{sector}"
    return mainline or sector


def _trace_anchor_reversal(trace):
    anchor = (trace or {}).get("anchor_reversal") or {}
    if not anchor:
        return ""
    parts = []
    sector_anchor = anchor.get("sector_anchor", "")
    candidate_role = anchor.get("candidate_role", "")
    relationship = anchor.get("relationship_to_anchor", "")
    why_not_anchor = anchor.get("why_not_anchor", "")
    repair_priority = anchor.get("repair_priority", "")
    decision = anchor.get("anchor_reversal_decision", "")
    reason = anchor.get("anchor_reversal_reason", "")
    ma_strategy = anchor.get("ma_binding_strategy", "")
    certainty_path = anchor.get("leader_certainty_path", "")
    limit_up_role = anchor.get("limit_up_evidence_role", "")
    if sector_anchor:
        parts.append(f"锚：{sector_anchor}")
    if candidate_role:
        parts.append(f"身份：{candidate_role}")
    if relationship:
        parts.append(f"关系：{relationship}")
    if why_not_anchor:
        parts.append(f"为什么不做锚：{why_not_anchor}")
    if repair_priority:
        parts.append(f"修复优先级：{repair_priority}")
    if decision:
        parts.append(f"结论：{decision}")
    if ma_strategy:
        parts.append(f"均线绑定：{ma_strategy}")
    if certainty_path:
        parts.append(f"龙头路径：{certainty_path}")
    if limit_up_role:
        parts.append(f"涨停证据：{limit_up_role}")
    if reason:
        parts.append(reason)
    return "；".join(parts)


def _trace_check_texts(trace, results):
    texts = []
    for check in (trace or {}).get("checks", []) or []:
        result = check.get("result", "")
        if result not in results:
            continue
        label = check.get("label", "")
        evidence = check.get("evidence", "")
        text = f"{label}：{result}" if label else result
        if evidence:
            text = f"{text}({evidence})"
        texts.append(text)
    return texts


def _trace_key_inputs(trace):
    texts = []
    for item in (trace or {}).get("key_inputs", []) or []:
        field = item.get("field", "")
        value = item.get("value", "")
        if field and value:
            texts.append(f"{field}：{value}")
        elif field or value:
            texts.append(field or value)
    return texts


def _trace_blocking_points(trace):
    points = _trace_check_texts(trace, {"未满足", "数据缺失"})
    if points:
        return "；".join(points)
    partial = _trace_check_texts(trace, {"部分满足"})
    if partial:
        return "；".join(partial)
    missing_data = _join_values((trace or {}).get("missing_data", []), separator="、")
    return f"缺失：{missing_data}" if missing_data else ""


def _trace_is_observation_only(trace):
    trace = trace or {}
    text = "；".join(
        str(part or "")
        for part in [
            trace.get("final_action"),
            "；".join(_as_list(trace.get("branch_path", []))),
            "；".join(_as_list(trace.get("missing_data", []))),
        ]
    )
    return any(
        marker in text
        for marker in (
            "只观察",
            "不新增参与",
            "继续不参与",
            "停止生成动作",
            "条件未满足",
            "账户不适配",
            "不能新增参与",
            "数据缺失",
        )
    )


def _trace_display_tier(trace):
    trace = trace or {}
    if _trace_is_observation_only(trace):
        return "观察层"
    tier = str(trace.get("tier") or "").strip()
    return {
        "T0": "执行候选",
        "T1": "复核候选",
        "T2": "等待候选",
        "T3": "资料候选",
    }.get(tier, tier or "候选")


def _compact_trace_row(contract):
    trace = _contract_trace(contract)
    return {
        "层级": _trace_display_tier(trace),
        "候选": _trace_candidate_label(contract, trace),
        "主线/板块": _trace_mainline_sector(trace),
        "板块锚反推": _trace_anchor_reversal(trace),
        "为什么进入这一层": trace.get("visible_summary", ""),
        "卡点": _trace_blocking_points(trace),
        "明日动作": trace.get("final_action", ""),
    }


def _full_trace_row(contract):
    trace = _contract_trace(contract)
    return {
        "层级": _trace_display_tier(trace),
        "候选": _trace_candidate_label(contract, trace),
        "来源池": _join_values(trace.get("source_pools", []), separator="、"),
        "主线/板块": _trace_mainline_sector(trace),
        "板块锚反推": _trace_anchor_reversal(trace),
        "关键输入": "；".join(_trace_key_inputs(trace)),
        "满足条件": "；".join(_trace_check_texts(trace, {"满足", "部分满足"})),
        "未满足/缺失": _trace_blocking_points(trace),
        "分支结果": "；".join(_as_list(trace.get("branch_path", []))),
        "明日动作": trace.get("final_action", ""),
        "失效条件": trace.get("failure_condition", ""),
    }


def _render_table_rows(fields, rows):
    lines = ["| " + " | ".join(fields) + " |", "|" + "|".join(["------"] * len(fields)) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(_cell(row.get(field, "")) for field in fields) + " |")
    return lines


def _render_compact_trace_table(contracts, heading_level=3):
    rows = [_compact_trace_row(contract) for contract in contracts if _contract_trace(contract).get("tier") in ("T0", "T1")]
    if not rows:
        return []
    lines = [_heading(heading_level, "候选选股轨迹"), ""]
    lines.extend(_render_table_rows(COMPACT_TRACE_FIELDS, rows))
    return lines


def _render_full_trace_table(contracts, heading_level=3):
    rows = [_full_trace_row(contract) for contract in contracts if _contract_trace(contract)]
    if not rows:
        return []
    lines = [_heading(heading_level, "候选选股轨迹明细"), ""]
    lines.extend(_render_table_rows(FULL_TRACE_FIELDS, rows))
    return lines


def _render_eliminated_summary(eliminated_summary, heading_level=3):
    rows = list(eliminated_summary or [])
    if not rows:
        return []
    lines = [_heading(heading_level, "未进入分层原因统计"), ""]
    lines.append("| 原因 | 数量 | 代表候选 | 处理 |")
    lines.append("|------|------|------|------|")
    for item in rows:
        item = item or {}
        lines.append(
            "| "
            + " | ".join(
                [
                    _cell(item.get("reason", "")),
                    _cell(item.get("count", "")),
                    _join_values(item.get("representatives", []), separator="、"),
                    _cell(item.get("treatment", "")),
                ]
            )
            + " |"
        )
    return lines


def _trace_anchor_payload(trace):
    anchor = (trace or {}).get("anchor_reversal") or {}
    return anchor if isinstance(anchor, dict) else {}


def _graph_text(value):
    return _cell(" ".join(str(value or "").split()))


def _graph_action_label(contract, trace):
    row = (contract or {}).get("visible_row", {}) or {}
    action_ceiling = str(row.get("动作上限") or "").strip()
    decision = str(_trace_anchor_payload(trace).get("anchor_reversal_decision") or "").strip()
    final_action = str((trace or {}).get("final_action") or "").strip()
    if any(marker in final_action for marker in ("条件未满足", "继续不参与", "只观察", "不新增参与")):
        return "观察/不参与"
    if action_ceiling == "主买" or decision == "可作为主对象":
        return "明日主买对象"
    if action_ceiling == "补位" or decision == "可作为补位":
        return "明日补位对象"
    if action_ceiling in ("不参与", "核心观察", "修复观察") or decision in ("降级观察", "不参与"):
        return "观察/不参与"
    return action_ceiling or trace.get("tier") or "候选观察"


def _append_graph_detail(lines, indent, label, value):
    text = _graph_text(value)
    if text:
        lines.append(f"{indent}+-- {label}: {text}")


def _render_sniper_selection_graph(contracts, eliminated_summary=None, heading_level=3):
    trace_pairs = [
        (contract, _contract_trace(contract))
        for contract in contracts or []
        if _contract_trace(contract)
    ]
    if not any(_trace_anchor_payload(trace) for _, trace in trace_pairs):
        return []

    first_trace = next((trace for _, trace in trace_pairs if _trace_anchor_payload(trace)), trace_pairs[0][1])
    first_anchor = _trace_anchor_payload(first_trace)
    mainline_label = _trace_mainline_sector(first_trace) or "待识别"
    sector_anchor = first_anchor.get("sector_anchor") or "待识别"

    lines = [
        _heading(heading_level, "狙击手最终标的路径图"),
        "",
        "```text",
        "原始候选池",
        "|",
        f"+-- 主线/板块: {_graph_text(mainline_label)}",
        "    |",
        f"    +-- 板块锚: {_graph_text(sector_anchor)}",
        "        |",
    ]
    for contract, trace in trace_pairs:
        anchor = _trace_anchor_payload(trace)
        if not anchor:
            continue
        action_label = _graph_action_label(contract, trace)
        candidate_label = _trace_candidate_label(contract, trace)
        lines.append(f"        +-- {_graph_text(action_label)}: {_graph_text(candidate_label)}")
        _append_graph_detail(lines, "        |   ", "来源池", _join_values(trace.get("source_pools", []), separator="、"))
        _append_graph_detail(lines, "        |   ", "身份", anchor.get("candidate_role"))
        _append_graph_detail(lines, "        |   ", "关系", anchor.get("relationship_to_anchor"))
        if anchor.get("why_not_anchor"):
            _append_graph_detail(lines, "        |   ", "为什么不做锚", anchor.get("why_not_anchor"))
        if action_label == "观察/不参与":
            blocking_point = anchor.get("why_not_anchor") or anchor.get("anchor_reversal_reason") or _trace_blocking_points(trace)
            _append_graph_detail(lines, "        |   ", "偏差/卡点", blocking_point)
        _append_graph_detail(lines, "        |   ", "处理", anchor.get("anchor_reversal_decision"))
        _append_graph_detail(lines, "        |   ", "依据", anchor.get("anchor_reversal_reason"))
        _append_graph_detail(lines, "        |   ", "明日动作", trace.get("final_action"))
        lines.append("        |")

    eliminated_rows = list(eliminated_summary or [])
    if eliminated_rows:
        lines.append("        +-- 未进入动作分层")
        for item in eliminated_rows[:3]:
            item = item or {}
            reason = _graph_text(item.get("reason", ""))
            treatment = _graph_text(item.get("treatment", ""))
            representatives = _join_values(item.get("representatives", []), separator="、")
            count = _graph_text(item.get("count", ""))
            summary = reason
            if count:
                summary = f"{summary} x{count}" if summary else f"x{count}"
            if representatives:
                summary = f"{summary} ({representatives})" if summary else representatives
            if treatment:
                summary = f"{summary} -> {treatment}" if summary else treatment
            if summary:
                lines.append(f"        |   +-- {summary}")

    while lines and lines[-1] == "        |":
        lines.pop()
    lines.append("```")
    return lines


def _render_trace_tables(contracts, eliminated_summary=None, heading_level=3):
    sections = []
    for section in (
        _render_sniper_selection_graph(contracts, eliminated_summary, heading_level),
        _render_compact_trace_table(contracts, heading_level),
        _render_full_trace_table(contracts, heading_level),
        _render_eliminated_summary(eliminated_summary, heading_level),
    ):
        if section:
            if sections:
                sections.append("")
            sections.extend(section)
    return sections


def _render_single_stock_details(contracts, heading_level=3):
    if not contracts:
        return []
    lines = [_heading(heading_level, "单票展开"), ""]
    for contract in contracts:
        row = (contract or {}).get("visible_row", {}) or {}
        fields = (contract or {}).get("single_stock_fields", {}) or {}
        candidate_title = _cell(row.get("候选", "暂无"))
        if heading_level >= 6:
            lines.append(f"**{candidate_title}**")
        else:
            lines.append(_heading(heading_level + 1, candidate_title))
        lines.append("")
        for field in SINGLE_STOCK_FIELDS:
            lines.append(f"- {field}：{_single_stock_cell(field, fields.get(field, ''))}")
        lines.append("")
    while lines and lines[-1] == "":
        lines.pop()
    return lines


def render_candidate_quality_section(
    panel,
    candidate_contracts,
    heading_level=2,
    table_fields=None,
    *,
    render_trace_tables=False,
    eliminated_summary=None,
):
    contracts = list(candidate_contracts or [])
    lines = [_heading(heading_level, "候选质量与动作分层"), ""]
    lines.extend(_render_panel(panel, heading_level + 1))
    lines.append("")
    lines.extend(_render_candidate_table(contracts, heading_level + 1, table_fields))
    if render_trace_tables:
        trace_lines = _render_trace_tables(contracts, eliminated_summary, heading_level + 1)
        if trace_lines:
            lines.append("")
            lines.extend(trace_lines)
    details = _render_single_stock_details(contracts, heading_level + 1)
    if details:
        lines.append("")
        lines.extend(details)
    return "\n".join(lines)


__all__ = [
    "COMPACT_CANDIDATE_TABLE_FIELDS",
    "COMPACT_TRACE_FIELDS",
    "FULL_TRACE_FIELDS",
    "render_candidate_quality_section",
]
