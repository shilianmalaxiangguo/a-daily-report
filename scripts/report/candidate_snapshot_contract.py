"""Compatibility contract for front-page candidate snapshots."""

from __future__ import annotations

from report.reasoning_decision_support import derive_unique_action_target_from_reasoning_decision


def _label(item):
    code = str(item.get("code") or item.get("股票代码") or "").strip()
    name = str(item.get("name") or item.get("股票") or item.get("股票名称") or "").strip()
    if code and name:
        return f"{name}({code})"
    return name or code or "观察对象"


def build_candidate_snapshot(data=None, *, market_research_snapshot=None):
    snapshot = market_research_snapshot or {}
    target = snapshot.get("unique_action_target")
    if "reasoning_decision" in snapshot:
        target = derive_unique_action_target_from_reasoning_decision(snapshot)
    has_target = isinstance(target, dict) and (target.get("name") or target.get("code"))
    front_page = {
        "unique_object": _label(target) if has_target else "暂无",
        "backup_text": "暂无",
        "no_buy_reason": "没有唯一对象，完整候选仅保留在附录和快照",
        "trigger_condition": "10点确认 + 主线承接 + 个股突破或回踩确认",
        "failure_condition": "主线回落 / 放量不承接",
        "backup_watch": [],
    }
    return {"front_page": front_page}


__all__ = ["build_candidate_snapshot"]
