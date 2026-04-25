from __future__ import annotations

from typing import Any, Mapping


def _join(items: Any) -> str:
    if not isinstance(items, list):
        return "-"
    values = [str(item).strip() for item in items if str(item).strip()]
    return "；".join(values) if values else "-"


def _evidence_text(decision: Mapping[str, Any]) -> str:
    items = decision.get("evidence")
    if not isinstance(items, list):
        return "-"
    values = []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        summary = str(item.get("summary") or "").strip()
        if summary:
            values.append(summary)
    return "；".join(values) if values else "-"


def _excluded_text(decision: Mapping[str, Any]) -> str:
    items = decision.get("excluded_candidates")
    if not isinstance(items, list):
        return "-"
    values = []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        name = str(item.get("name") or "").strip()
        code = str(item.get("id") or item.get("code") or "").strip()
        reason = str(item.get("reason") or "").strip()
        label = f"{name}({code})" if name and code else name or code or "-"
        values.append(f"{label}：{reason or '-'}")
    return "；".join(values) if values else "-"


def render_reasoning_decision_lines(decision: Mapping[str, Any] | None) -> list[str]:
    if not isinstance(decision, Mapping) or not decision:
        return []
    return [
        "### 0. 推理裁决",
        "| 项目 | 内容 |",
        "|------|------|",
        f"| 裁决 | {decision.get('action') or '-'} |",
        f"| 主线状态 | {decision.get('mainline_state') or '-'} |",
        f"| 结论 | {decision.get('conclusion') or '-'} |",
        f"| 关键证据 | {_evidence_text(decision)} |",
        f"| 触发条件 | {_join(decision.get('trigger_conditions'))} |",
        f"| 失败条件 | {_join(decision.get('failure_conditions'))} |",
        f"| 排除对象 | {_excluded_text(decision)} |",
        f"| 置信度 | {decision.get('confidence') or '-'} |",
        "",
    ]
