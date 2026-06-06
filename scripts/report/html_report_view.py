from __future__ import annotations

from typing import Any


__all__ = [
    "build_daily_report_view",
    "daily_report_view_has_required_facts",
    "missing_required_fact_labels",
]


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _first_dict(*values: Any) -> dict[str, Any]:
    for value in values:
        if isinstance(value, dict) and value:
            return value
    return {}


def _merge_dicts(*values: Any) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for value in values:
        if isinstance(value, dict) and value:
            merged.update(value)
    return merged


def _list_text(values: Any) -> list[str]:
    if isinstance(values, list):
        return [_text(value) for value in values if _text(value)]
    text = _text(values)
    return [text] if text else []


def _bool_or_none(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return None
    text = _text(value).lower()
    if text in {"1", "true", "yes", "y", "allow", "allowed"}:
        return True
    if text in {"0", "false", "no", "n", "deny", "denied"}:
        return False
    return None


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _load_postgres_data(target_date: str, db_service: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    reader = getattr(db_service, "load_daily_report_snapshot", None)
    if not callable(reader):
        return {}, {"source": "", "field_count": 0, "target_field_count": 0}
    loaded = reader(target_date) or {}
    data = loaded.get("data") if isinstance(loaded.get("data"), dict) else {}
    return data, loaded


def _extract_decision(data: dict[str, Any]) -> dict[str, Any]:
    snapshot = data.get("market_research_snapshot") if isinstance(data.get("market_research_snapshot"), dict) else {}
    two_layer = snapshot.get("two_layer_decision_payload") if isinstance(snapshot.get("two_layer_decision_payload"), dict) else {}
    front_decision = two_layer.get("front_decision") if isinstance(two_layer.get("front_decision"), dict) else {}
    return _merge_dicts(
        data.get("final_decision"),
        data.get("tomorrow_decision"),
        data.get("final_gate"),
        data.get("front_page_final_gate"),
        snapshot.get("tomorrow_decision"),
        snapshot.get("front_page_decision"),
        snapshot.get("position_decision"),
        front_decision,
        snapshot.get("final_gate"),
        snapshot.get("front_page_final_gate"),
    )


def _position_text(decision: dict[str, Any]) -> str:
    for key in ("max_position", "position_state", "position_level", "target_position"):
        text = _text(decision.get(key))
        if text:
            return text
    for key in ("target_position_pct", "position_pct"):
        text = _text(decision.get(key)).replace("%", "")
        if text:
            return "{}%".format(text)
    position_plan = _text(decision.get("position_plan"))
    if "B档执行" in position_plan or "50%" in position_plan:
        return "50%"
    final_action = _text(decision.get("final_action"))
    if "100%" in final_action:
        return "100%"
    if "50%" in final_action or "B档" in final_action:
        return "50%"
    if "0%" in final_action or "不参与" in final_action:
        return "0%"
    return ""


def _participation_bool(decision: dict[str, Any]) -> bool | None:
    for key in ("allow_new_entry", "can_new_entry", "can_participate"):
        parsed = _bool_or_none(decision.get(key))
        if parsed is not None:
            return parsed
    text = "；".join(
        value
        for value in (
            _text(decision.get("final_action")),
            _text(decision.get("action")),
            _text(decision.get("action_summary")),
            _text(decision.get("position_plan")),
        )
        if value
    )
    negative_tokens = ("不参与", "禁止参与", "不新增参与", "只观察", "只做退出", "等待确认", "不执行", "未出现执行资格")
    if any(token in text for token in negative_tokens):
        return False
    if text.startswith("0%") or " 0%" in text or "，0%" in text or "；0%" in text or "/ 0%" in text:
        return False
    positive_tokens = ("可参与", "标准进攻", "B档执行", "100%核心", "条件满足才B档执行")
    if any(token in text for token in positive_tokens):
        return True
    return False


def _extract_tomorrow_action(data: dict[str, Any]) -> dict[str, Any]:
    decision = _extract_decision(data)
    if not decision:
        return {}
    snapshot = data.get("market_research_snapshot") if isinstance(data.get("market_research_snapshot"), dict) else {}
    resolution = snapshot.get("final_target_resolution") if isinstance(snapshot.get("final_target_resolution"), dict) else {}
    target = _first_dict(
        decision.get("primary_target"),
        decision.get("target"),
        decision.get("execution_object"),
        resolution.get("display_target"),
        resolution.get("new_entry_target"),
        resolution.get("watch_target"),
        snapshot.get("selected_position_candidate"),
        data.get("selected_position_candidate"),
    )
    return {
        "position_state": _position_text(decision),
        "can_participate": _participation_bool(decision),
        "primary_target": target,
        "participation_window": _text(
            decision.get("participation_window") or decision.get("buy_window") or decision.get("trigger_text")
        ),
        "action_summary": _text(decision.get("final_action") or decision.get("action") or decision.get("action_summary")),
        "cancel_conditions": _list_text(decision.get("cancel_conditions") or decision.get("failure_conditions")),
        "risk_boundary": _text(decision.get("risk_boundary") or decision.get("invalidation")),
    }


def _breadth_summary(market_stats: dict[str, Any]) -> str:
    up_count = _text(market_stats.get("up_count"))
    down_count = _text(market_stats.get("down_count"))
    if not up_count and not down_count:
        return ""
    return "上涨{} / 下跌{}".format(up_count or "-", down_count or "-")


def _extract_market_spine(data: dict[str, Any]) -> dict[str, Any]:
    market_stats = data.get("market_stats") if isinstance(data.get("market_stats"), dict) else {}
    return {
        "market_fit": _text(data.get("market_fit") or data.get("market_fit_label")),
        "turnover_summary": _text(data.get("total_turnover")),
        "breadth_summary": _breadth_summary(market_stats),
        "market_phase": _text(data.get("market_phase") or data.get("market_trend")),
        "index_structure": _text(data.get("index_structure")),
        "why_it_matters": _text(data.get("market_reason") or data.get("market_summary")),
    }


def _extract_mainline_evidence(data: dict[str, Any]) -> dict[str, Any]:
    context = data.get("mainline_context") if isinstance(data.get("mainline_context"), dict) else {}
    return {
        "confirmed_line": _text(context.get("confirmed_line") or context.get("mainline") or data.get("mainline_name")),
        "supporting_lines": _list_text(context.get("supporting_lines")),
        "attack_evidence": _list_text(context.get("attack_evidence")),
        "turnover_share": _text(context.get("turnover_share")),
        "fund_flow": _text(context.get("fund_flow")),
        "sector_breadth": _text(context.get("sector_breadth")),
        "continuation_conditions": _list_text(context.get("continuation_conditions")),
        "failure_conditions": _list_text(context.get("failure_conditions")),
    }


def _query_candidate_actions(target_date: str, db_service: Any) -> list[dict[str, Any]]:
    reader = getattr(db_service, "query_extreme_conviction_mentions", None)
    if not callable(reader):
        return []
    rows = reader(target_date, window_days=25, include_a_kill=False) or []
    result = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        result.append(
            {
                "stock_code": _text(row.get("stock_code")),
                "stock_name": _text(row.get("stock_name")),
                "role": _text(row.get("sector_candidate") or row.get("role")),
                "source_reason": _text(row.get("reason")),
                "participation_script": _text(row.get("planned_window") or row.get("buy_window")),
                "entry_timing": _text(row.get("entry_timing")),
                "buy_window": _text(row.get("buy_window") or row.get("planned_window")),
                "risk_reward": _text(row.get("risk_reward")),
                "invalidation": _text(row.get("invalidation")),
                "missed_action": _text(row.get("next_action")),
                "review_status": _text(row.get("review_status")),
            }
        )
    return result


def _data_source_rows(target_date: str, loaded: dict[str, Any], db_service: Any) -> list[dict[str, Any]]:
    rows = [
        {
            "source_label": "PSQL日报事实",
            "source_policy": _text(loaded.get("source")),
            "source_date": target_date,
            "query_date": target_date,
            "trade_date": target_date,
            "status": "success" if _safe_int(loaded.get("target_field_count") or loaded.get("field_count")) > 0 else "missing",
            "warning": "",
        }
    ]
    coverage_reader = getattr(db_service, "daily_report_fact_coverage", None)
    coverage = coverage_reader(target_date) if callable(coverage_reader) else {}
    tables = coverage.get("tables") if isinstance(coverage, dict) and isinstance(coverage.get("tables"), dict) else {}
    for table_name, item in tables.items():
        item = item if isinstance(item, dict) else {}
        rows.append(
            {
                "source_label": _text(table_name),
                "source_policy": "postgresql.{}".format(_text(table_name)),
                "source_date": _text(item.get("max_trade_date")),
                "query_date": target_date,
                "trade_date": target_date,
                "status": "success" if _safe_int(item.get("target_count")) > 0 else "missing",
                "warning": "",
            }
        )
    return rows


def _missing_required_facts(view: dict[str, Any]) -> list[str]:
    missing = []
    action = view.get("tomorrow_action") if isinstance(view.get("tomorrow_action"), dict) else {}
    market = view.get("market_spine") if isinstance(view.get("market_spine"), dict) else {}
    sources = view.get("data_sources") if isinstance(view.get("data_sources"), list) else []
    if not action or not _text(action.get("action_summary")):
        missing.append("明日动作")
    if not market or (not _text(market.get("turnover_summary")) and not _text(market.get("breadth_summary"))):
        missing.append("市场结构")
    if not sources or all(_text(item.get("status")) == "missing" for item in sources if isinstance(item, dict)):
        missing.append("数据来源")
    return missing


def build_daily_report_view(target_date: str, db_service: Any, *, run_mode: str = "frozen") -> dict[str, Any]:
    target_date = _text(target_date)
    data, loaded = _load_postgres_data(target_date, db_service)
    candidate_actions = _query_candidate_actions(target_date, db_service)
    view = {
        "meta": {
            "trade_date": target_date,
            "report_title": "{} A股日报".format(target_date),
            "generated_at": "",
            "run_mode": _text(run_mode) or "frozen",
            "source": _text(loaded.get("source")),
            "data_source_summary": "PSQL日报事实",
        },
        "tomorrow_action": _extract_tomorrow_action(data),
        "market_spine": _extract_market_spine(data),
        "mainline_evidence": _extract_mainline_evidence(data),
        "candidate_actions": candidate_actions,
        "participation_reviews": [item for item in candidate_actions if _text(item.get("review_status"))],
        "data_sources": _data_source_rows(target_date, loaded, db_service),
        "diagnostics": {
            "missing_required_facts": [],
            "degraded_facts": [],
            "render_warnings": [],
            "html_artifact_path": "",
            "large_json_artifact": False,
        },
    }
    view["diagnostics"]["missing_required_facts"] = _missing_required_facts(view)
    return view


def missing_required_fact_labels(view: dict[str, Any]) -> list[str]:
    diagnostics = view.get("diagnostics") if isinstance(view.get("diagnostics"), dict) else {}
    return list(diagnostics.get("missing_required_facts") or [])


def daily_report_view_has_required_facts(view: dict[str, Any]) -> bool:
    return not missing_required_fact_labels(view)
