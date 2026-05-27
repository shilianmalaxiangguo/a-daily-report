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

COMPACT_TRACE_FIELDS = ["层级", "候选", "主线/板块", "为什么进入这一层", "卡点", "明日动作"]

FULL_TRACE_FIELDS = ["层级", "候选", "来源池", "主线/板块", "关键输入", "满足条件", "未满足/缺失", "分支结果", "明日动作", "失效条件"]

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


def _compact_trace_row(contract):
    trace = _contract_trace(contract)
    return {
        "层级": trace.get("tier", ""),
        "候选": _trace_candidate_label(contract, trace),
        "主线/板块": _trace_mainline_sector(trace),
        "为什么进入这一层": trace.get("visible_summary", ""),
        "卡点": _trace_blocking_points(trace),
        "明日动作": trace.get("final_action", ""),
    }


def _full_trace_row(contract):
    trace = _contract_trace(contract)
    return {
        "层级": trace.get("tier", ""),
        "候选": _trace_candidate_label(contract, trace),
        "来源池": _join_values(trace.get("source_pools", []), separator="、"),
        "主线/板块": _trace_mainline_sector(trace),
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


def _render_trace_tables(contracts, eliminated_summary=None, heading_level=3):
    sections = []
    for section in (
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
