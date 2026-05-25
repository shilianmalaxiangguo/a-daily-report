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


def render_candidate_quality_section(panel, candidate_contracts, heading_level=2, table_fields=None):
    contracts = list(candidate_contracts or [])
    lines = [_heading(heading_level, "候选质量与动作分层"), ""]
    lines.extend(_render_panel(panel, heading_level + 1))
    lines.append("")
    lines.extend(_render_candidate_table(contracts, heading_level + 1, table_fields))
    details = _render_single_stock_details(contracts, heading_level + 1)
    if details:
        lines.append("")
        lines.extend(details)
    return "\n".join(lines)


__all__ = ["COMPACT_CANDIDATE_TABLE_FIELDS", "render_candidate_quality_section"]
