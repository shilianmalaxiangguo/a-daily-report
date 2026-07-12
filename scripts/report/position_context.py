from __future__ import annotations

import re
from typing import Any


PREVIOUS_REPORT_TARGET_POSITION_SOURCE = "previous_report_target_default_1x"
PENDING_PREVIOUS_REPORT_ROLE = "前日报计划待成交确认"


def is_inferred_previous_report_position(summary: Any) -> bool:
    return isinstance(summary, dict) and bool(
        summary.get("inferred_from_previous_report") is True
        or summary.get("position_source") == PREVIOUS_REPORT_TARGET_POSITION_SOURCE
    )


def existing_position_summary_from_context(context: Any) -> dict[str, Any]:
    context = context if isinstance(context, dict) else {}
    personal_context = context.get("personal_position_context")
    personal_context = personal_context if isinstance(personal_context, dict) else {}
    summary = personal_context.get("existing_position_summary")
    if not isinstance(summary, dict):
        summary = context.get("existing_position_summary")
    return summary if isinstance(summary, dict) else {}


def normalize_inferred_previous_target_records(value: Any, _visited: set[int] | None = None) -> int:
    if not isinstance(value, (dict, list)):
        return 0
    if _visited is None:
        _visited = set()
    marker = id(value)
    if marker in _visited:
        return 0
    _visited.add(marker)
    normalized = 0
    if isinstance(value, dict):
        if is_inferred_previous_report_position(value):
            record_changed = False
            name = str(value.get("name") or value.get("stock_name") or "").strip()
            code = str(value.get("code") or value.get("stock_code") or "").strip()
            if not (name or code):
                match = re.search(r"([^，；|：:\n]+?)\((\d{6})\)", str(value.get("summary") or ""))
                if match:
                    name = re.sub(r"^(?:持有|已有旧仓|当前持仓)", "", match.group(1)).strip()
                    code = match.group(2)
            label = f"{name}({code})" if name and code else (name or code or "前日报计划对象")
            source_report_date = str(value.get("source_report_date") or "").strip()
            source_note = f"；上一份日报目标来源={source_report_date}" if source_report_date else ""
            canonical_summary = (
                f"前日报计划推定，待成交确认：{label}{source_note}；"
                "未确认成交前不视为B1，不新增B2"
            )
            if value.get("summary") != canonical_summary:
                value["summary"] = canonical_summary
                record_changed = True
            if value.get("has_position") is not False:
                value["has_position"] = False
                record_changed = True
            if value.get("has_pending_position") is not True:
                value["has_pending_position"] = True
                record_changed = True
            scenario_candidates = (
                value.get("default_position_pct"),
                value.get("position_pct"),
                value.get("position"),
            )
            scenario_position = next(
                (candidate for candidate in scenario_candidates if candidate not in (None, "", 0, 0.0, "0", "0.0")),
                next((candidate for candidate in scenario_candidates if candidate not in (None, "")), None),
            )
            if scenario_position not in (None, "") and value.get("default_position_pct") != scenario_position:
                value["default_position_pct"] = scenario_position
                record_changed = True
            for actual_position_key in ("position", "position_pct"):
                if value.get(actual_position_key) != 0.0:
                    value[actual_position_key] = 0.0
                    record_changed = True
            if value.get("inferred_from_previous_report") is not True:
                value["inferred_from_previous_report"] = True
                record_changed = True
            if value.get("role") != PENDING_PREVIOUS_REPORT_ROLE:
                value["role"] = PENDING_PREVIOUS_REPORT_ROLE
                record_changed = True
            if "holding_note" in value and value.get("holding_note") != "上一份日报计划推定，待成交确认":
                value["holding_note"] = "上一份日报计划推定，待成交确认"
                record_changed = True
            if record_changed:
                normalized += 1
        for child in value.values():
            normalized += normalize_inferred_previous_target_records(child, _visited)
    elif isinstance(value, list):
        for child in value:
            normalized += normalize_inferred_previous_target_records(child, _visited)
    return normalized


def is_position_timeline_header(line: Any) -> bool:
    text = str(line or "").lstrip()
    return text.startswith("| 轨道 | 标的 |") or text.startswith("| 日序 | 日期 |")


def extract_position_timeline_markdown(position_strategy_report: Any) -> str:
    lines = str(position_strategy_report or "").splitlines()
    if not lines or not is_position_timeline_header(lines[0]):
        return ""
    collected = []
    for line in lines:
        if line.startswith("#"):
            break
        collected.append(line)
    return "\n".join(collected).strip()


def markdown_has_position_timeline(markdown_text: Any) -> bool:
    saw_content = False
    for line in str(markdown_text or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped == "## 账户日序表":
            return True
        if not saw_content and is_position_timeline_header(line):
            return True
        saw_content = True
    return False


def prepend_position_timeline_markdown(markdown_text: Any, position_timeline_markdown: Any) -> str:
    timeline = str(position_timeline_markdown or "").strip()
    if not timeline:
        return str(markdown_text or "")
    section = f"## 账户日序表\n{timeline}"
    text = str(markdown_text or "")
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.strip() != "## 账户日序表":
            continue
        end = index + 1
        seen_table = False
        while end < len(lines):
            stripped = lines[end].strip()
            if lines[end].startswith("## "):
                break
            if not stripped:
                end += 1
                continue
            if stripped.startswith("|"):
                seen_table = True
                end += 1
                continue
            if seen_table and stripped.startswith("-"):
                end += 1
                continue
            break
        updated_lines = lines[:index] + [section, ""] + lines[end:]
        return "\n".join(updated_lines).strip() + "\n"
    if markdown_has_position_timeline(markdown_text):
        return str(markdown_text or "")
    text = str(markdown_text or "").lstrip()
    lines = text.splitlines()
    if not lines:
        return f"{section}\n"
    insert_at = 0
    if lines[0].startswith("# "):
        insert_at = 1
        while insert_at < len(lines) and not lines[insert_at].strip():
            insert_at += 1
        if insert_at < len(lines) and lines[insert_at].strip() == "## 阅读地图":
            insert_at += 1
            while insert_at < len(lines):
                if lines[insert_at].startswith("## "):
                    break
                insert_at += 1
            while insert_at < len(lines) and not lines[insert_at].strip():
                insert_at += 1
    updated_lines = lines[:insert_at] + ["", section, ""] + lines[insert_at:]
    return "\n".join(updated_lines).strip() + "\n"
