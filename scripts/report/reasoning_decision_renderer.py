from __future__ import annotations

import re
from typing import Any, Mapping


FORBIDDEN_MARKERS = ("chain-of-thought", "思维链", "完整推理链", "隐藏推理")
MAX_CELL_LENGTH = 120


def _sanitize_cell(value: Any) -> str:
    text = " ".join(str(value or "").split()).replace("|", "｜")
    for marker in FORBIDDEN_MARKERS:
        text = re.sub(re.escape(marker), "", text, flags=re.IGNORECASE)
    text = " ".join(text.split()).strip()
    if not text:
        return "-"
    if len(text) > MAX_CELL_LENGTH:
        return f"{text[:MAX_CELL_LENGTH].rstrip()}..."
    return text


def _join(items: Any) -> str:
    if not isinstance(items, list):
        return "-"
    values = [_sanitize_cell(item) for item in items]
    values = [value for value in values if value != "-"]
    return _sanitize_cell("；".join(values)) if values else "-"


def _evidence_text(decision: Mapping[str, Any]) -> str:
    items = decision.get("evidence")
    if not isinstance(items, list):
        return "-"
    values = []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        summary = _sanitize_cell(item.get("summary"))
        if summary != "-":
            values.append(summary)
    return _sanitize_cell("；".join(values)) if values else "-"


def _excluded_text(decision: Mapping[str, Any]) -> str:
    items = decision.get("excluded_candidates")
    if not isinstance(items, list):
        return "-"
    values = []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        name = _sanitize_cell(item.get("name"))
        code = _sanitize_cell(item.get("id") or item.get("code"))
        reason = _sanitize_cell(item.get("reason"))
        name = "" if name == "-" else name
        code = "" if code == "-" else code
        label = f"{name}({code})" if name and code else name or code or "-"
        values.append(f"{label}：{reason}")
    return _sanitize_cell("；".join(values)) if values else "-"


def render_reasoning_decision_lines(decision: Mapping[str, Any] | None) -> list[str]:
    if not isinstance(decision, Mapping) or not decision:
        return []
    return [
        "### 0. 推理裁决",
        "| 项目 | 内容 |",
        "|------|------|",
        f"| 结论 | {_sanitize_cell(decision.get('conclusion'))} |",
        f"| 关键证据 | {_evidence_text(decision)} |",
        f"| 触发条件 | {_join(decision.get('trigger_conditions'))} |",
        f"| 失败条件 | {_join(decision.get('failure_conditions'))} |",
        f"| 排除对象 | {_excluded_text(decision)} |",
        f"| 推理深度 | {_sanitize_cell(decision.get('reasoning_effort'))} |",
        "",
    ]
