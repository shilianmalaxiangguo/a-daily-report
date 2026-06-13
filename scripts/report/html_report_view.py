from __future__ import annotations

from typing import Any

from domains.execution_chain.pk_decision_nodes.candidate_surface_filter import (
    candidate_can_be_current_observation_target,
)
from report.cycle_sector_style import cycle_sector_color


__all__ = [
    "build_daily_report_view",
    "daily_report_view_has_required_facts",
    "missing_required_fact_labels",
]

# Structured fact view for the HTML dashboard. The Bear/readable HTML path
# renders final Markdown in markdown_report_html.py.
TREND_CHART_WINDOW_DAYS = 25


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _first_dict(*values: Any) -> dict[str, Any]:
    for value in values:
        if isinstance(value, dict) and value:
            return value
    return {}


def _first_current_observation_dict(*values: Any) -> dict[str, Any]:
    for value in values:
        if isinstance(value, dict) and value and candidate_can_be_current_observation_target(value):
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


def _safe_float(value: Any) -> float | None:
    try:
        text = (
            str(value)
            .replace("%", "")
            .replace("pct", "")
            .replace("亿", "")
            .replace(",", "")
            .strip()
        )
        if text in {"", "-", "待累计", "数据暂缺"}:
            return None
        return float(text)
    except (TypeError, ValueError):
        return None


def _allowed_position_text(value: Any) -> str:
    pct = _safe_float(value)
    if pct is None or pct <= 0:
        return "0%"
    if pct >= 100:
        return "100%"
    return "50%"


def _first_present(*values: Any) -> Any:
    for value in values:
        if value is not None and value != "":
            return value
    return None


def _meaningful_text(value: Any) -> str:
    text = _text(value)
    if text in {"-", "待确认", "暂无确认主线", "暂无确认主攻线"}:
        return ""
    return text


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
        text = _text(decision.get(key))
        if text:
            return _allowed_position_text(text)
    position_plan = _text(decision.get("position_plan"))
    if "50%条件执行" in position_plan or "50%" in position_plan:
        return "50%"
    final_action = _text(decision.get("final_action"))
    if "100%" in final_action:
        return "100%"
    if "50%" in final_action or "50%执行" in final_action:
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
    positive_tokens = ("可参与", "条件执行", "50%条件执行", "100%核心", "条件满足才50%条件执行")
    if any(token in text for token in positive_tokens):
        return True
    return False


def _selection_workflow_final_is_empty(*sources: dict[str, Any]) -> bool:
    workflow: dict[str, Any] = {}
    for source in sources:
        if not isinstance(source, dict):
            continue
        nested_sources = [
            source,
            source.get("market_research_snapshot"),
            source.get("execution_stage_context"),
        ]
        for nested in list(nested_sources):
            if isinstance(nested, dict):
                nested_sources.extend([nested.get("market_research_snapshot"), nested.get("execution_stage_context")])
        for nested in nested_sources:
            if not isinstance(nested, dict):
                continue
            candidate = nested.get("selection_workflow") if isinstance(nested.get("selection_workflow"), dict) else {}
            if candidate.get("schema_version") == "selection_workflow.v1":
                workflow = candidate
                break
        if workflow:
            break
    if workflow.get("schema_version") != "selection_workflow.v1" or "final" not in workflow:
        return False
    final = workflow.get("final") if isinstance(workflow.get("final"), dict) else {}
    target = final.get("execution_object") if isinstance(final.get("execution_object"), dict) else {}
    position_pct = _safe_float(final.get("position_pct"))
    return position_pct is None or position_pct <= 0 or not _first_dict(target)


def _extract_tomorrow_action(data: dict[str, Any]) -> dict[str, Any]:
    decision = _extract_decision(data)
    if not decision:
        return {}
    snapshot = data.get("market_research_snapshot") if isinstance(data.get("market_research_snapshot"), dict) else {}
    resolution = snapshot.get("final_target_resolution") if isinstance(snapshot.get("final_target_resolution"), dict) else {}
    can_participate = _participation_bool(decision)
    execution_target = _first_dict(
        decision.get("primary_target"),
        decision.get("target"),
        decision.get("execution_object"),
        resolution.get("display_target"),
        resolution.get("new_entry_target"),
    )
    observation_target_sources = [resolution.get("watch_target")]
    if not _selection_workflow_final_is_empty(snapshot, data):
        observation_target_sources.extend([snapshot.get("selected_position_candidate"), data.get("selected_position_candidate")])
    observation_target = _first_current_observation_dict(*observation_target_sources)
    target = execution_target if can_participate is not False else {}
    return {
        "position_state": _position_text(decision),
        "can_participate": can_participate,
        "primary_target": target,
        "observation_target": observation_target if can_participate is False else {},
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


def _count_or_none(value: Any) -> int | None:
    if not _text(value):
        return None
    number = _safe_float(value)
    if number is None:
        return None
    return int(number)


def _number_or_none(value: Any) -> float | None:
    number = _safe_float(value)
    return number


def _rows_from(value: Any, *keys: str) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        for key in keys:
            rows = value.get(key)
            if isinstance(rows, list):
                return [item for item in rows if isinstance(item, dict)]
    return []


def _latest_points_through_target_date(
    points: list[dict[str, Any]],
    target_date: str,
    *,
    limit: int = TREND_CHART_WINDOW_DAYS,
) -> list[dict[str, Any]]:
    sorted_points = sorted(points, key=lambda item: _text(item.get("date")))
    through_target = [point for point in sorted_points if _text(point.get("date")) <= target_date]
    return through_target[-limit:]


def _query_market_total_for_chart(db_service: Any, trade_date: str) -> dict[str, Any]:
    reader = getattr(db_service, "query_market_daily_total", None)
    if not callable(reader):
        return {}
    try:
        value = reader(trade_date, market_scope="all_a") or {}
    except TypeError as error:
        if "market_scope" not in str(error):
            raise
        value = reader(trade_date) or {}
    return value if isinstance(value, dict) else {}


def _query_market_breadth_for_chart(db_service: Any, trade_date: str) -> dict[str, Any]:
    reader = getattr(db_service, "query_market_breadth_counts", None)
    if not callable(reader):
        return {}
    value = reader(trade_date) or {}
    return value if isinstance(value, dict) else {}


def _enrich_market_capacity_points_from_structured_facts(points: list[dict[str, Any]], db_service: Any) -> None:
    if not points:
        return
    for point in points:
        trade_date = _text(point.get("date"))
        if not trade_date:
            continue
        if point.get("total_turnover") is None:
            total = _query_market_total_for_chart(db_service, trade_date)
            point["total_turnover"] = _number_or_none(
                _first_present(
                    total.get("total_amount_yi"),
                    total.get("total_turnover"),
                    total.get("market_amount_yi"),
                    total.get("market_turnover"),
                )
            )
        if point.get("up_count") is None or point.get("down_count") is None:
            breadth = _query_market_breadth_for_chart(db_service, trade_date)
            if point.get("up_count") is None:
                point["up_count"] = _count_or_none(breadth.get("up_count"))
            if point.get("down_count") is None:
                point["down_count"] = _count_or_none(breadth.get("down_count"))


def _chart_payload(status: str, *, title: str, missing_reasons: list[str] | None = None, **payload: Any) -> dict[str, Any]:
    return {"status": status, "title": title, "missing_reasons": missing_reasons or [], **payload}


def _resolve_market_research_snapshot(data: dict[str, Any]) -> dict[str, Any]:
    return data.get("market_research_snapshot") if isinstance(data.get("market_research_snapshot"), dict) else {}


def _resolve_mainline_turnover_summary(data: dict[str, Any]) -> dict[str, Any]:
    snapshot = _resolve_market_research_snapshot(data)
    context = data.get("mainline_context") if isinstance(data.get("mainline_context"), dict) else {}
    return _first_dict(
        context.get("mainline_turnover_summary"),
        data.get("mainline_turnover_summary"),
        snapshot.get("mainline_turnover_summary"),
    )


def _latest_mainline_turnover_row(summary: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    rows = _rows_from(
        _first_present(summary.get("turnover_share_trend_rows"), data.get("turnover_share_trend_rows")),
        "rows",
        "items",
    )
    return rows[-1] if rows else {}


def _build_market_capacity_chart(data: dict[str, Any], target_date: str, db_service: Any = None) -> dict[str, Any]:
    series = data.get("top50_turnover_share_series")
    rows = _rows_from(series, "rows", "items")
    market_stats = data.get("market_stats") if isinstance(data.get("market_stats"), dict) else {}
    points: list[dict[str, Any]] = []
    for row in rows:
        date = _text(row.get("trade_date") or row.get("date"))
        top50_share = _number_or_none(_first_present(row.get("share_pct"), row.get("top50_share_pct")))
        if not date or top50_share is None:
            continue
        points.append(
            {
                "date": date,
                "total_turnover": _number_or_none(
                    _first_present(
                        row.get("total_turnover"),
                        row.get("market_turnover"),
                        row.get("market_amount_yi"),
                        row.get("total_amount_yi"),
                    )
                ),
                "top50_share_pct": top50_share,
                "up_count": _count_or_none(row.get("up_count")),
                "down_count": _count_or_none(row.get("down_count")),
            }
        )
    if not points:
        return _chart_payload(
            "missing",
            title="市场容量趋势",
            missing_reasons=["缺少目标日期 Top50 成交额占比序列"],
            points=[],
        )
    points = _latest_points_through_target_date(points, target_date)
    _enrich_market_capacity_points_from_structured_facts(points, db_service)
    if all(_text(point.get("date")) != target_date for point in points):
        return _chart_payload(
            "missing",
            title="市场容量趋势",
            missing_reasons=["缺少目标日期 Top50 成交额占比"],
            points=points,
        )
    target_point = next((point for point in points if _text(point.get("date")) == target_date), points[-1])
    if target_point.get("total_turnover") is None:
        target_point["total_turnover"] = _number_or_none(data.get("total_turnover"))
    if target_point.get("up_count") is None:
        target_point["up_count"] = _count_or_none(market_stats.get("up_count"))
    if target_point.get("down_count") is None:
        target_point["down_count"] = _count_or_none(market_stats.get("down_count"))
    if target_point.get("total_turnover") is None:
        return _chart_payload(
            "missing",
            title="市场容量趋势",
            missing_reasons=["缺少目标日期成交额"],
            points=points,
        )
    return _chart_payload(
        "ready",
        title="市场容量趋势",
        points=points,
        calculation_note="最近25个交易日；缺失保持空值，历史行缺失的成交额和涨跌家数不按0绘制。",
    )


def _build_mainline_turnover_share_chart(data: dict[str, Any], target_date: str) -> dict[str, Any]:
    summary = _resolve_mainline_turnover_summary(data)
    double_summary = (
        summary.get("double_mainline_summary") if isinstance(summary.get("double_mainline_summary"), dict) else {}
    )
    rows = _rows_from(
        _first_present(summary.get("turnover_share_trend_rows"), data.get("turnover_share_trend_rows")),
        "rows",
        "items",
    )
    points: list[dict[str, Any]] = []
    for row in rows:
        date = _text(row.get("trade_date") or row.get("date"))
        share = _number_or_none(
            _first_present(row.get("turnover_share_pct"), row.get("share_pct"), row.get("mainline_share_pct"), row.get("share"))
        )
        if not date or share is None:
            continue
        cycle_mainline = _text(
            row.get("cycle_mainline")
            or row.get("primary_mainline")
            or row.get("mainline")
            or row.get("mainline_name")
            or double_summary.get("cycle_mainline")
            or summary.get("cycle_mainline")
            or summary.get("current_cycle_mainline")
            or summary.get("current_mainline")
            or summary.get("primary_mainline")
        )
        daily_attack_line = _text(
            row.get("daily_attack_line")
            or row.get("attack_line")
            or double_summary.get("daily_attack_line")
            or summary.get("daily_attack_line")
            or summary.get("current_daily_attack_line")
            or row.get("mainline")
            or row.get("mainline_name")
            or cycle_mainline
        )
        points.append(
            {
                "date": date,
                "mainline": cycle_mainline or daily_attack_line,
                "cycle_mainline": cycle_mainline,
                "daily_attack_line": daily_attack_line,
                "mainline_turnover": _number_or_none(row.get("mainline_turnover")),
                "market_turnover": _number_or_none(row.get("market_turnover")),
                "turnover_share_pct": share,
                "share_delta_pct": _number_or_none(
                    _first_present(row.get("share_delta_pct"), row.get("delta_pct"), row.get("share_change"))
                ),
            }
        )
    if not points:
        return _chart_payload(
            "missing",
            title="主线成交占比趋势",
            missing_reasons=["缺少主线成交占比趋势行"],
            points=[],
        )
    points = _latest_points_through_target_date(points, target_date)
    if all(_text(point.get("date")) != target_date for point in points):
        return _chart_payload(
            "missing",
            title="主线成交占比趋势",
            missing_reasons=["缺少目标日期主线成交占比"],
            points=points,
        )
    return _chart_payload("ready", title="主线成交占比趋势", points=points)


def _normalize_tag_distribution(value: Any) -> dict[str, float]:
    if isinstance(value, dict):
        result: dict[str, float] = {}
        for key, raw_count in value.items():
            count = _number_or_none(raw_count)
            if _text(key) and count is not None:
                result[_text(key)] = count
        return result
    if isinstance(value, list):
        result = {}
        for item in value:
            if not isinstance(item, dict):
                continue
            tag = _text(item.get("tag") or item.get("name") or item.get("sector"))
            count = _number_or_none(_first_present(item.get("count"), item.get("stock_count"), item.get("value")))
            if tag and count is not None:
                result[tag] = count
        return result
    return {}


def _build_sector_heatmap_rows_from_attack_evidence(
    data: dict[str, Any],
    tag_distribution: dict[str, float],
) -> list[dict[str, Any]]:
    rows = _rows_from(data.get("sector_attack_evidence_rows"))
    if not rows:
        return []
    heat_rows: list[dict[str, Any]] = []
    for row in rows[:12]:
        sector = _text(row.get("sector_name") or row.get("sector") or row.get("name"))
        if not sector:
            continue
        continuity = _number_or_none(_first_present(row.get("turnover_share_pct"), row.get("continuity")))
        if continuity is None:
            continue
        heat_rows.append(
            {
                "sector": sector,
                "fund": _number_or_none(_first_present(row.get("net_inflow_amount"), row.get("net_inflow_amount_yi"))),
                "breadth": _number_or_none(
                    _first_present(row.get("turnover_share_change"), row.get("turnover_share_delta_pct"))
                ),
                "limit_up": _number_or_none(row.get("limit_up_count")),
                "height": _number_or_none(_first_present(row.get("high_anchor_height"), row.get("height"))),
                "continuity": continuity,
                "attention": tag_distribution[sector] if sector in tag_distribution else None,
            }
        )
    return heat_rows


def _build_sector_heatmap_chart(data: dict[str, Any]) -> dict[str, Any]:
    sector_fund_flow = data.get("sector_fund_flow") if isinstance(data.get("sector_fund_flow"), dict) else {}
    inflow_rows = _rows_from(sector_fund_flow.get("inflow"))
    tag_distribution = _normalize_tag_distribution(data.get("tag_distribution"))
    attack_evidence_rows = _rows_from(data.get("sector_attack_evidence_rows"))
    rows = _build_sector_heatmap_rows_from_attack_evidence(data, tag_distribution)
    if rows:
        columns = [
            {"key": "fund", "label": "资金"},
            {"key": "breadth", "label": "占比变化"},
            {"key": "limit_up", "label": "涨停"},
            {"key": "height", "label": "高标"},
            {"key": "continuity", "label": "成交占比"},
            {"key": "attention", "label": "注意力"},
        ]
        return _chart_payload(
            "ready",
            title="板块容量热力图",
            columns=columns,
            rows=rows,
            calculation_note="基于板块攻击证据行；热榜 tag 只作为注意力入口，缺失不按0计算。",
        )
    if attack_evidence_rows:
        return _chart_payload(
            "missing",
            title="板块容量热力图",
            missing_reasons=["板块成交占比事实不足"],
            columns=[],
            rows=[],
            calculation_note="热榜 tag 只作为注意力入口，不作为独立确认。",
        )
    if not inflow_rows:
        return _chart_payload(
            "missing",
            title="板块容量热力图",
            missing_reasons=["板块资金事实不足"],
            columns=[],
            rows=[],
            calculation_note="热榜 tag 只作为注意力入口，不作为独立确认。",
        )
    rows: list[dict[str, Any]] = []
    for row in inflow_rows[:12]:
        sector = _text(row.get("name") or row.get("sector") or row.get("plate_name"))
        if not sector:
            continue
        fund = _number_or_none(_first_present(row.get("amount"), row.get("cje"), row.get("net_inflow"), row.get("inflow")))
        change = _number_or_none(row.get("change_pct"))
        limit_up = _number_or_none(row.get("limit_up_count"))
        attention = tag_distribution[sector] if sector in tag_distribution else None
        continuity = _number_or_none(
            _first_present(row.get("turnover_share_pct"), row.get("turnover_share"), row.get("share_pct"))
        )
        if continuity is None:
            continue
        rows.append(
            {
                "sector": sector,
                "fund": fund,
                "breadth": change,
                "limit_up": limit_up,
                "height": _number_or_none(_first_present(row.get("height"), row.get("high_board_count"))),
                "continuity": continuity,
                "attention": attention,
            }
        )
    if not rows:
        return _chart_payload(
            "missing",
            title="板块容量热力图",
            missing_reasons=["板块成交占比事实不足"],
            columns=[],
            rows=[],
            calculation_note="热榜 tag 只作为注意力入口，不作为独立确认。",
        )
    columns = [
        {"key": "fund", "label": "资金"},
        {"key": "breadth", "label": "扩散"},
        {"key": "limit_up", "label": "涨停"},
        {"key": "height", "label": "高标"},
        {"key": "continuity", "label": "成交占比"},
        {"key": "attention", "label": "注意力"},
    ]
    return _chart_payload(
        "ready",
        title="板块容量热力图",
        columns=columns,
        rows=rows,
        calculation_note="热榜 tag 只作为注意力入口，不作为独立确认；缺失不按0计算。",
    )


def _build_mainline_attack_scatter_chart(data: dict[str, Any]) -> dict[str, Any]:
    summary = _resolve_mainline_turnover_summary(data)
    attack_summary = (
        summary.get("mainline_attack_evidence_summary")
        if isinstance(summary.get("mainline_attack_evidence_summary"), dict)
        else {}
    )
    primary_rows = _rows_from(
        _first_present(
            attack_summary.get("evidence_rows"),
            attack_summary.get("sector_evidence_rows"),
            attack_summary.get("sector_rows"),
            attack_summary.get("rows"),
            data.get("mainline_attack_evidence_rows"),
        ),
        "rows",
        "items",
    )
    rows = primary_rows or _rows_from(data.get("sector_attack_evidence_rows"))
    rows = _rows_from(
        rows,
        "rows",
        "items",
    )
    points: list[dict[str, Any]] = []
    for row in rows:
        sector = _text(row.get("sector") or row.get("name") or row.get("line") or row.get("sector_name"))
        if not sector:
            continue
        point = {
            "sector": sector,
            "role": _text(row.get("role") or row.get("line_role")) or ("板块攻击证据" if not primary_rows else ""),
            "source_date": _text(
                row.get("source_date")
                or row.get("trade_date")
                or row.get("date")
                or row.get("query_date")
            ),
            "turnover_share_delta_pct": _number_or_none(
                _first_present(
                    row.get("turnover_share_delta_pct"),
                    row.get("share_delta_pct"),
                    row.get("turnover_share_change"),
                    row.get("x"),
                )
            ),
            "turnover_share_pct": _number_or_none(
                _first_present(row.get("turnover_share_pct"), row.get("share_pct"), row.get("share"), row.get("turnover_share"))
            ),
            "fund_strength": _number_or_none(
                _first_present(
                    row.get("fund_strength"),
                    row.get("strength"),
                    row.get("net_inflow_amount"),
                    row.get("net_inflow_amount_yi"),
                    row.get("y"),
                )
            ),
            "limit_up_count": _number_or_none(row.get("limit_up_count")),
            "height": _number_or_none(
                _first_present(row.get("height"), row.get("high_board_count"), row.get("high_anchor_height"))
            ),
        }
        point["missing_fields"] = [
            key
            for key in ("turnover_share_delta_pct", "fund_strength", "limit_up_count", "height")
            if point.get(key) is None
        ]
        points.append(point)
    if not points:
        return _chart_payload(
            "missing",
            title="主线攻击证据",
            missing_reasons=["主线攻击证据缺少结构化散点行"],
            points=[],
        )
    if not any((point.get("turnover_share_pct") or 0) > 0 for point in points):
        return _chart_payload(
            "missing",
            title="主线攻击证据",
            missing_reasons=["板块成交占比事实不足"],
            points=points,
        )
    return _chart_payload("ready", title="主线攻击证据", points=points)


def _sample_stocks_for_tag(tag: str, hot_list: list[dict[str, Any]]) -> list[str]:
    samples: list[str] = []
    for item in hot_list:
        tags = item.get("tags") if isinstance(item.get("tags"), list) else []
        text_tags = {_text(value) for value in tags}
        if tag not in text_tags and tag != _text(item.get("tag")):
            continue
        stock_name = _text(item.get("stock_name") or item.get("name"))
        stock_code = _text(item.get("stock_code") or item.get("code"))
        label = stock_name or stock_code
        if stock_name and stock_code:
            label = f"{stock_name}({stock_code})"
        if label:
            samples.append(label)
        if len(samples) >= 5:
            break
    return samples


def _build_hot_tag_composition_chart(data: dict[str, Any]) -> dict[str, Any]:
    tag_distribution = _normalize_tag_distribution(data.get("tag_distribution"))
    hot_list = _rows_from(data.get("integrated_hot_list"))
    sample_size = _safe_int(_first_present(data.get("integrated_hot_list_sample_size"), data.get("hot_rank_sample_size")))
    sample_target = _safe_int(_first_present(data.get("integrated_hot_list_sample_target"), data.get("hot_rank_sample_target")))
    top100_ready = len(hot_list) >= 100 or (sample_target >= 100 and sample_size >= 100)
    if not top100_ready and sample_size < 50 and len(hot_list) < 50:
        return _chart_payload(
            "missing",
            title="热榜 Tag 构成",
            missing_reasons=["同花顺热榜样本不足"],
            tags=[],
        )
    tag_snapshot = (
        data.get("realtime_tag_evidence_snapshot")
        if isinstance(data.get("realtime_tag_evidence_snapshot"), dict)
        else {}
    )
    snapshot_rows = _rows_from(
        _first_present(tag_snapshot.get("tag_rows"), tag_snapshot.get("rows"), tag_snapshot.get("tags")),
        "rows",
        "items",
    )
    role_by_tag = {_text(row.get("tag") or row.get("name")): _text(row.get("role")) for row in snapshot_rows}
    sample_by_tag = {
        _text(row.get("tag") or row.get("name")): _list_text(row.get("sample_stocks"))
        for row in snapshot_rows
    }
    tags = []
    for tag, count in sorted(tag_distribution.items(), key=lambda item: item[1], reverse=True)[:16]:
        tags.append(
            {
                "tag": tag,
                "count": count,
                "role": role_by_tag.get(tag, ""),
                "sample_stocks": sample_by_tag.get(tag) or _sample_stocks_for_tag(tag, hot_list),
            }
        )
    if not tags:
        return _chart_payload(
            "missing",
            title="热榜 Tag 构成",
            missing_reasons=["同花顺热榜 tag 构成不足"],
            tags=[],
        )
    sample_label = "前100" if top100_ready else f"前{max(sample_size, len(hot_list))}"
    return _chart_payload(
        "ready",
        title="热榜 Tag 构成",
        tags=tags,
        calculation_note=f"基于同花顺热榜{sample_label}，只回答市场在讲什么，不直接给参与资格。",
    )


def _build_cycle_week_view_chart(data: dict[str, Any]) -> dict[str, Any]:
    summary = _resolve_mainline_turnover_summary(data)
    rows = _rows_from(
        _first_present(summary.get("cycle_calendar_rows"), data.get("cycle_calendar_rows")),
        "rows",
        "items",
    )
    weekdays = ("monday", "tuesday", "wednesday", "thursday", "friday")
    normalized = []
    for row in rows[:12]:
        normalized_row = {
            "week_label": _text(row.get("week_label") or row.get("week") or row.get("date")),
            "mainline": _text(row.get("mainline") or row.get("primary_mainline")),
            "phase": _text(row.get("phase") or row.get("stage")),
            "action": _text(row.get("action") or row.get("summary")),
        }
        if normalized_row["week_label"] and not any(
            normalized_row.get(key) for key in ("mainline", "phase", "action")
        ):
            day_cells = [
                row.get(day_key)
                for day_key in weekdays
                if isinstance(row.get(day_key), dict)
            ]
            meaningful_cells = [
                cell
                for cell in day_cells
                if _meaningful_text(cell.get("mainline"))
                or _meaningful_text(cell.get("state"))
                or _meaningful_text(cell.get("daily_attack_line"))
            ]
            if meaningful_cells:
                cell = meaningful_cells[-1]
                normalized_row["mainline"] = _meaningful_text(cell.get("mainline"))
                normalized_row["phase"] = _meaningful_text(cell.get("state") or cell.get("phase"))
                normalized_row["action"] = _meaningful_text(
                    cell.get("daily_attack_line") or cell.get("action") or cell.get("summary")
                )
        if normalized_row["week_label"] and any(
            normalized_row.get(key) for key in ("mainline", "phase", "action")
        ):
            normalized_row["color"] = cycle_sector_color(normalized_row.get("mainline"))
            normalized.append(normalized_row)
    if not normalized:
        fallback_rows = _build_cycle_week_rows_from_turnover_trend(data, summary)
        if fallback_rows:
            return _chart_payload(
                "ready",
                title="板块周视图",
                rows=fallback_rows,
                calculation_note="周期日历不足时，基于主线成交占比趋势按周生成。",
            )
        return _chart_payload(
            "missing",
            title="板块周视图",
            missing_reasons=["周期日历数据不足"],
            rows=[],
        )
    return _chart_payload("ready", title="板块周视图", rows=normalized)


def _top50_turnover_share_points(data: dict[str, Any], target_date: str) -> list[dict[str, Any]]:
    series = data.get("top50_turnover_share_series")
    rows = series.get("rows") if isinstance(series, dict) else series
    points: list[dict[str, Any]] = []
    for row in rows if isinstance(rows, list) else []:
        date = _text(row.get("trade_date") or row.get("date"))
        share = _number_or_none(_first_present(row.get("share_pct"), row.get("top50_share_pct")))
        if not date or share is None:
            continue
        points.append(
            {
                "date": date,
                "share_pct": share,
                "market_amount_yi": _number_or_none(
                    _first_present(row.get("market_amount_yi"), row.get("market_turnover_yi"), row.get("total_turnover"))
                ),
                "top50_amount_yi": _number_or_none(_first_present(row.get("top50_amount_yi"), row.get("amount_yi"))),
            }
        )
    return _latest_points_through_target_date(points, target_date)


def _build_turnover_rank_chart(data: dict[str, Any], target_date: str) -> dict[str, Any]:
    rows = _rows_from(data.get("turnover_rank"), "rows", "items")
    normalized = []
    for index, row in enumerate(rows[:50], start=1):
        name = _text(row.get("name") or row.get("stock_name"))
        code = _text(row.get("code") or row.get("stock_code"))
        turnover = _number_or_none(
            _first_present(row.get("turnover_yi"), row.get("turnover"), row.get("amount_yi"), row.get("amount"))
        )
        if not name and not code:
            continue
        if turnover is None:
            continue
        normalized.append(
            {
                "rank": _safe_int(row.get("rank")) or index,
                "name": name,
                "code": code,
                "sector": _text(row.get("sector") or row.get("industry")),
                "turnover_yi": turnover,
                "change_pct": _number_or_none(_first_present(row.get("change_pct"), row.get("pct_chg"))),
                "close": _number_or_none(row.get("close")),
                "zt_status": _text(row.get("zt_status")),
            }
        )
    normalized.sort(key=lambda item: item.get("rank") or 999)
    share_points = _top50_turnover_share_points(data, target_date)
    latest_share = share_points[-1].get("share_pct") if share_points else None
    previous_share = share_points[-2].get("share_pct") if len(share_points) >= 2 else None
    share_delta = (
        round((_number_or_none(latest_share) or 0.0) - (_number_or_none(previous_share) or 0.0), 4)
        if latest_share is not None and previous_share is not None
        else None
    )
    if not normalized and not share_points:
        return _chart_payload(
            "missing",
            title="Top50成交额占比",
            missing_reasons=["缺少目标日期 Top50 成交额占比和成交额排行"],
            rows=[],
            share_points=[],
        )
    return _chart_payload(
        "ready",
        title="Top50成交额占比",
        rows=normalized,
        share_points=share_points,
        latest_share_pct=latest_share,
        share_delta_pct=share_delta,
        calculation_note="Top50占比回答资金集中度；下方排行只解释集中到哪些票，不替代热榜tag方向。",
    )


def _build_new_high_chart(data: dict[str, Any], target_date: str) -> dict[str, Any]:
    feedback = data.get("new_high_feedback") if isinstance(data.get("new_high_feedback"), dict) else {}
    source_dates = {
        _text(feedback.get("factor_trade_date")),
        _text(feedback.get("requested_trade_date")),
        _text(feedback.get("trade_date")),
    }
    source_dates.discard("")
    if source_dates and target_date not in source_dates:
        return _chart_payload(
            "missing",
            title="创新高扩散",
            missing_reasons=["创新高反馈日期不匹配目标日期"],
            trend_rows=[],
            sector_rows=[],
            top_stocks=[],
        )
    trend_rows = []
    for row in _rows_from(feedback.get("trend_rows"), "rows", "items"):
        date = _text(row.get("trade_date") or row.get("date"))
        count = _number_or_none(row.get("new_high_count"))
        if not date or count is None:
            continue
        trend_rows.append(
            {
                "date": date,
                "new_high_count": count,
                "all_a_share_pct": _number_or_none(row.get("all_a_share_pct")),
                "leading_sectors": _text(row.get("leading_sectors")),
                "change_text": _text(row.get("change_text")),
            }
        )
    trend_rows = _latest_points_through_target_date(trend_rows, target_date)
    has_target_trend = any(_text(row.get("date")) == target_date for row in trend_rows)
    sector_rows = []
    for row in _rows_from(feedback.get("sector_distribution"), "rows", "items")[:12]:
        sector = _text(row.get("sector") or row.get("name"))
        count = _number_or_none(row.get("new_high_count") or row.get("count"))
        if not sector or count is None:
            continue
        sector_rows.append(
            {
                "sector": sector,
                "new_high_count": count,
                "share_pct": _number_or_none(row.get("share_pct")),
                "representative_stocks": _list_text(row.get("representative_stocks")),
            }
        )
    top_stocks = []
    for row in _rows_from(feedback.get("top_stocks"), "rows", "items")[:12]:
        name = _text(row.get("name") or row.get("stock_name"))
        code = _text(row.get("code") or row.get("stock_code"))
        if not name and not code:
            continue
        top_stocks.append(
            {
                "name": name,
                "code": code,
                "sector": _text(row.get("sector") or row.get("industry")),
                "pct_chg": _number_or_none(_first_present(row.get("pct_chg"), row.get("change_pct"))),
                "close": _number_or_none(row.get("close")),
                "topdays": _number_or_none(row.get("topdays")),
            }
        )
    if not trend_rows and not sector_rows and not top_stocks:
        return _chart_payload(
            "missing",
            title="创新高扩散",
            missing_reasons=["缺少目标日期创新高反馈"],
            trend_rows=[],
            sector_rows=[],
            top_stocks=[],
        )
    if trend_rows and not has_target_trend:
        return _chart_payload(
            "missing",
            title="创新高扩散",
            missing_reasons=["缺少目标日期创新高趋势行"],
            trend_rows=trend_rows,
            sector_rows=sector_rows,
            top_stocks=top_stocks,
        )
    return _chart_payload(
        "ready",
        title="创新高扩散",
        new_high_count=_number_or_none(feedback.get("new_high_count")),
        all_a_share_pct=_number_or_none(feedback.get("all_a_share_pct")),
        leading_sectors=_text(feedback.get("leading_sectors")),
        summary=_text(feedback.get("summary")),
        source=_text(feedback.get("source")),
        trend_rows=trend_rows,
        sector_rows=sector_rows,
        top_stocks=top_stocks,
        calculation_note="创新高只说明扩散方向；是否参与仍看主线承接、时间窗口和认错线距离。",
    )


def _normalize_lhb_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    for index, row in enumerate(rows[:10], start=1):
        name = _text(row.get("name") or row.get("stock_name"))
        code = _text(row.get("code") or row.get("stock_code"))
        net_buy = _number_or_none(
            _first_present(row.get("net_buy_amount_yi"), row.get("net_buy_yi"), row.get("amount_yi"), row.get("net_buy"))
        )
        if not name and not code:
            continue
        if net_buy is None:
            continue
        normalized.append(
            {
                "rank": _safe_int(row.get("rank")) or index,
                "name": name,
                "code": code,
                "sector": _text(row.get("sector") or row.get("industry")),
                "net_buy_amount_yi": net_buy,
                "change_pct": _number_or_none(_first_present(row.get("change_pct"), row.get("pct_chg"))),
                "close": _number_or_none(row.get("close")),
                "zt_status": _text(row.get("zt_status")),
            }
        )
    return normalized


def _filter_rows_for_target_date(rows: list[dict[str, Any]], target_date: str) -> list[dict[str, Any]]:
    filtered = []
    for row in rows:
        row_date = _normalize_report_date_text(
            row.get("trade_date") or row.get("date") or row.get("source_date") or row.get("query_date")
        )
        if row_date and row_date != target_date:
            continue
        filtered.append(row)
    return filtered


def _normalize_report_date_text(value: Any) -> str:
    text = _text(value)
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) >= 8:
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
    return text


def _clean_lhb_code(value: Any) -> str:
    text = _text(value).upper()
    if "." in text:
        text = text.split(".", 1)[0]
    for prefix in ("SH", "SZ", "BJ"):
        if text.startswith(prefix):
            text = text[len(prefix):]
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits.zfill(6) if digits else ""


def _lhb_amount_yi(row: dict[str, Any], yi_key: str, raw_key: str) -> float:
    value = _number_or_none(row.get(yi_key))
    if value is not None:
        return value
    raw = _number_or_none(row.get(raw_key))
    if raw is None:
        return 0.0
    return raw / 1e8 if abs(raw) > 10000 else raw


def _normalize_lhb_inst_detail_rows(rows: list[dict[str, Any]], target_date: str) -> list[dict[str, Any]]:
    normalized = []
    seen = set()
    for row in rows:
        trade_date = _normalize_report_date_text(row.get("trade_date") or row.get("date") or row.get("source_date") or row.get("query_date"))
        if not trade_date or trade_date != target_date:
            continue
        code = _clean_lhb_code(row.get("code") or row.get("stock_code") or row.get("ts_code"))
        if not code:
            continue
        exalter = _text(row.get("exalter") or row.get("seat") or row.get("seat_name"))
        seat_type = "机构" if _text(row.get("seat_type")) == "机构" or "机构" in exalter else "非机构"
        buy_yi = round(_lhb_amount_yi(row, "buy_yi", "buy"), 6)
        sell_yi = round(_lhb_amount_yi(row, "sell_yi", "sell"), 6)
        net_buy_yi = round(_lhb_amount_yi(row, "net_buy_yi", "net_buy"), 6)
        reason = _text(row.get("reason"))
        dedupe_key = (code, exalter, buy_yi, sell_yi, net_buy_yi, reason)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        normalized.append(
            {
                "trade_date": trade_date,
                "code": code,
                "ts_code": _text(row.get("ts_code")),
                "exalter": exalter,
                "seat_type": seat_type,
                "side": _text(row.get("side")),
                "buy_yi": buy_yi,
                "sell_yi": sell_yi,
                "net_buy_yi": net_buy_yi,
                "reason": reason,
                "data_source": _text(row.get("data_source") or "tushare.top_inst"),
            }
        )
    return normalized


def _signed_yi_text(value: Any) -> str:
    number = _number_or_none(value) or 0.0
    return f"{number:+.2f}亿"


def _build_lhb_reason_map(rows: list[dict[str, Any]]) -> dict[str, str]:
    reason_map: dict[str, str] = {}
    for row in rows:
        code = _clean_lhb_code(row.get("code") or row.get("代码") or row.get("ts_code") or row.get("fs_code"))
        if not code:
            continue
        reasons = row.get("reasons")
        if isinstance(reasons, list):
            reason = "；".join(_text(item) for item in reasons if _text(item))
        else:
            reason = _text(row.get("reason") or row.get("上榜原因"))
        if reason:
            reason_map[code] = reason
    return reason_map


def _lhb_mainline_keywords(data: dict[str, Any]) -> list[str]:
    snapshot = data.get("market_research_snapshot") if isinstance(data.get("market_research_snapshot"), dict) else {}
    summary = snapshot.get("mainline_turnover_summary") if isinstance(snapshot.get("mainline_turnover_summary"), dict) else {}
    context = data.get("mainline_context") if isinstance(data.get("mainline_context"), dict) else {}
    values = [
        context.get("confirmed_line"),
        context.get("daily_attack_line"),
        context.get("cycle_mainline"),
        summary.get("confirmed_line"),
        summary.get("daily_attack_line"),
        summary.get("cycle_mainline"),
    ]
    keywords = []
    for value in values:
        text = _meaningful_text(value)
        if text and text not in keywords:
            keywords.append(text)
    return keywords


def _lhb_matches_mainline(row: dict[str, Any], keywords: list[str]) -> bool:
    sector = _text(row.get("sector") or row.get("industry"))
    name = _text(row.get("name"))
    return any(keyword and (keyword in sector or sector in keyword or keyword in name) for keyword in keywords)


def _classify_lhb_quality(row: dict[str, Any], summary: dict[str, Any], keywords: list[str]) -> str:
    net_buy = _number_or_none(row.get("net_buy_amount_yi")) or 0.0
    institution_net = _number_or_none(summary.get("institution_net_buy_yi")) or 0.0
    broker_net = _number_or_none(summary.get("broker_net_buy_yi")) or 0.0
    if net_buy < 0:
        return "风险榜" if institution_net < 0 or broker_net < 0 else "分歧榜"
    if institution_net < -0.2 or broker_net < -1.0:
        return "分歧榜"
    if _lhb_matches_mainline(row, keywords) and (institution_net > 0 or broker_net > 0):
        return "主线好榜"
    if institution_net > 0.5:
        return "机构好榜"
    if broker_net > 0.5:
        return "非机构好榜"
    return "观察榜"


def _build_lhb_capital_read(row: dict[str, Any], summary: dict[str, Any]) -> str:
    net_buy = _number_or_none(row.get("net_buy_amount_yi")) or 0.0
    if not summary:
        return f"榜单净额{_signed_yi_text(net_buy)}；席位明细缺失，只按净买卖和板块位置观察。"
    parts = [
        f"榜单净额{_signed_yi_text(net_buy)}",
        f"机构{_signed_yi_text(summary.get('institution_net_buy_yi'))}",
        f"非机构{_signed_yi_text(summary.get('broker_net_buy_yi'))}",
    ]
    top_buy = _text(summary.get("top_buy_seat"))
    top_sell = _text(summary.get("top_sell_seat"))
    if top_buy:
        parts.append(f"买方代表：{top_buy}")
    if top_sell:
        parts.append(f"卖方压力：{top_sell}")
    return "；".join(parts)


def _build_lhb_seat_summaries(seat_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in seat_rows:
        code = _clean_lhb_code(row.get("code"))
        if not code:
            continue
        bucket = grouped.setdefault(
            code,
            {
                "code": code,
                "seat_count": 0,
                "institution_count": 0,
                "broker_count": 0,
                "institution_net_buy_yi": 0.0,
                "broker_net_buy_yi": 0.0,
                "total_net_buy_yi": 0.0,
                "reasons": [],
                "_seats": [],
            },
        )
        net_buy = _number_or_none(row.get("net_buy_yi")) or 0.0
        bucket["seat_count"] += 1
        bucket["total_net_buy_yi"] += net_buy
        if _text(row.get("seat_type")) == "机构":
            bucket["institution_count"] += 1
            bucket["institution_net_buy_yi"] += net_buy
        else:
            bucket["broker_count"] += 1
            bucket["broker_net_buy_yi"] += net_buy
        reason = _text(row.get("reason"))
        if reason and reason not in bucket["reasons"]:
            bucket["reasons"].append(reason)
        bucket["_seats"].append(row)
    for bucket in grouped.values():
        seats = sorted(bucket.pop("_seats"), key=lambda item: _number_or_none(item.get("net_buy_yi")) or 0.0, reverse=True)
        top_buy = seats[0] if seats else {}
        top_sell = seats[-1] if seats else {}
        bucket["top_buy_seat"] = _text(top_buy.get("exalter"))
        bucket["top_buy_yi"] = _number_or_none(top_buy.get("net_buy_yi"))
        bucket["top_sell_seat"] = _text(top_sell.get("exalter"))
        bucket["top_sell_yi"] = _number_or_none(top_sell.get("net_buy_yi"))
        for key in ("institution_net_buy_yi", "broker_net_buy_yi", "total_net_buy_yi"):
            bucket[key] = round(_number_or_none(bucket.get(key)) or 0.0, 6)
    return grouped


def _build_lhb_chart(data: dict[str, Any], target_date: str) -> dict[str, Any]:
    buy_rows = _normalize_lhb_rows(
        _filter_rows_for_target_date(_rows_from(data.get("lhb_net_buy_top10"), "rows", "items"), target_date)
    )
    sell_rows = _normalize_lhb_rows(
        _filter_rows_for_target_date(_rows_from(data.get("lhb_net_sell_top10"), "rows", "items"), target_date)
    )
    seat_rows = _normalize_lhb_inst_detail_rows(_rows_from(data.get("lhb_inst_detail"), "rows", "items"), target_date)
    seat_summaries = _build_lhb_seat_summaries(seat_rows)
    reason_map = _build_lhb_reason_map(_rows_from(data.get("lhb_analysis"), "rows", "items"))
    keywords = _lhb_mainline_keywords(data)
    name_by_code = {row.get("code"): row.get("name") for row in buy_rows + sell_rows if row.get("code") and row.get("name")}
    for row in buy_rows + sell_rows:
        code = _clean_lhb_code(row.get("code"))
        summary = seat_summaries.get(code, {})
        row["reason"] = reason_map.get(code, "")
        row["seat_status"] = "available" if summary else "missing"
        row["list_quality"] = _classify_lhb_quality(row, summary, keywords)
        row["capital_read"] = _build_lhb_capital_read(row, summary)
        if summary:
            row.update({key: value for key, value in summary.items() if key not in {"code", "reasons"}})
    if not buy_rows and not sell_rows:
        return _chart_payload(
            "missing",
            title="龙虎榜资金",
            missing_reasons=["缺少目标日期龙虎榜净买卖排行"],
            buy_rows=[],
            sell_rows=[],
            seat_rows=[],
            seat_summaries=[],
        )
    summary_rows = []
    for code, summary in seat_summaries.items():
        item = dict(summary)
        item["name"] = name_by_code.get(code, "")
        item["reason"] = "；".join(summary.get("reasons") or [])
        summary_rows.append(item)
    summary_rows = sorted(summary_rows, key=lambda item: abs(_number_or_none(item.get("total_net_buy_yi")) or 0.0), reverse=True)
    enriched_rows = sorted(
        buy_rows + sell_rows,
        key=lambda item: abs(_number_or_none(item.get("net_buy_amount_yi")) or 0.0),
        reverse=True,
    )
    return _chart_payload(
        "ready",
        title="龙虎榜资金",
        buy_rows=buy_rows,
        sell_rows=sell_rows,
        seat_rows=sorted(seat_rows, key=lambda item: abs(_number_or_none(item.get("net_buy_yi")) or 0.0), reverse=True)[:80],
        seat_summaries=summary_rows[:40],
        interpretation_rows=[
            {
                "name": row.get("name"),
                "code": row.get("code"),
                "sector": row.get("sector"),
                "list_quality": row.get("list_quality"),
                "capital_read": row.get("capital_read"),
                "institution_net_buy_yi": row.get("institution_net_buy_yi"),
                "broker_net_buy_yi": row.get("broker_net_buy_yi"),
            }
            for row in enriched_rows[:4]
        ],
        seat_detail_status="available" if seat_rows else _text(data.get("lhb_inst_detail_status") or "missing"),
        calculation_note="龙虎榜是资金偏好样本；好榜只代表资金表态更清楚，不直接生成明日参与动作。",
    )


def _build_price_band_chart(data: dict[str, Any], target_date: str) -> dict[str, Any]:
    series = data.get("price_band_style_series") if isinstance(data.get("price_band_style_series"), dict) else {}
    points = []
    for row in _rows_from(series.get("rows"), "rows", "items"):
        date = _text(row.get("trade_date") or row.get("date"))
        high_price = _number_or_none(row.get("high_price_pct"))
        low_price = _number_or_none(row.get("low_price_pct"))
        spread = _number_or_none(row.get("spread_pct"))
        if not date or (high_price is None and low_price is None and spread is None):
            continue
        points.append(
            {
                "date": date,
                "high_price_pct": high_price,
                "low_price_pct": low_price,
                "spread_pct": spread,
                "style_label": _text(row.get("style_label")),
                "absolute_label": _text(row.get("absolute_label")),
            }
        )
    points = _latest_points_through_target_date(points, target_date)
    if not points:
        return _chart_payload(
            "missing",
            title="百元股与低价股风格",
            missing_reasons=["缺少价格带风格序列"],
            points=[],
        )
    if all(_text(point.get("date")) != target_date for point in points):
        return _chart_payload(
            "missing",
            title="百元股与低价股风格",
            missing_reasons=["缺少目标日期价格带风格行"],
            points=points,
        )
    latest = points[-1]
    return _chart_payload(
        "ready",
        title="百元股与低价股风格",
        points=points,
        latest_spread_pct=_number_or_none(_first_present(series.get("latest_spread_pct"), latest.get("spread_pct"))),
        latest_style_label=_text(series.get("latest_style_label") or latest.get("style_label")),
        latest_absolute_label=_text(series.get("latest_absolute_label") or latest.get("absolute_label")),
        summary=_text(series.get("summary")),
        calculation_note="百元股与低价股的相对强弱用于判断风险偏好，不替代个股买点。",
    )


def _build_tail_window_chart(data: dict[str, Any]) -> dict[str, Any]:
    return _chart_payload(
        "ready",
        title="尾盘窗口",
        window="14:30-14:55",
        rule_rows=[
            {"label": "默认节奏", "text": "没有日内强核心承接，不新增参与。"},
            {"label": "例外条件", "text": "强核心全天强，且偏离MA5不大，最多25%试仓。"},
            {"label": "不追对象", "text": "非主线风扇股、后排补涨、认错线太远的样本不做。"},
            {"label": "复盘口径", "text": "这是尾盘例外，不是常规买点；次日按认错线和承接处理。"},
        ],
        missing_stock_pool=True,
        stock_rows=[],
        calculation_note="当前快照没有独立尾盘股池，驾驶舱只展示已有尾盘纪律，不补造股票列表。",
    )


def _build_cycle_week_rows_from_turnover_trend(data: dict[str, Any], summary: dict[str, Any]) -> list[dict[str, Any]]:
    trend_chart = _build_mainline_turnover_share_chart(data, "9999-12-31")
    points = trend_chart.get("points") if isinstance(trend_chart, dict) else []
    if not isinstance(points, list):
        return []
    grouped: dict[str, dict[str, Any]] = {}
    for point in points:
        if not isinstance(point, dict):
            continue
        date = _text(point.get("date"))
        if len(date) < 10:
            continue
        week_label = _week_label_for_date(date)
        mainline = _meaningful_text(point.get("cycle_mainline") or point.get("mainline"))
        daily_attack_line = _meaningful_text(point.get("daily_attack_line") or point.get("mainline"))
        share = _number_or_none(point.get("turnover_share_pct"))
        if not week_label or not mainline:
            continue
        current = grouped.get(week_label)
        if current is None or date >= _text(current.get("date")):
            grouped[week_label] = {
                "date": date,
                "week_label": week_label,
                "mainline": mainline,
                "phase": _cycle_week_share_phase(share),
                "action": daily_attack_line or mainline,
                "color": cycle_sector_color(mainline),
            }
    return [
        {key: value for key, value in row.items() if key != "date"}
        for row in sorted(grouped.values(), key=lambda item: _text(item.get("date")))[-5:]
    ]


def _week_label_for_date(date_text: str) -> str:
    from datetime import datetime, timedelta

    try:
        date = datetime.strptime(date_text[:10], "%Y-%m-%d").date()
    except ValueError:
        return date_text
    monday = date - timedelta(days=date.weekday())
    return monday.strftime("%m-%d当周")


def _cycle_week_share_phase(share: float | None) -> str:
    if share is None:
        return "成交占比待确认"
    return f"成交占比{share:.2f}%"


def _extract_charts(data: dict[str, Any], target_date: str, db_service: Any = None) -> dict[str, Any]:
    return {
        "market_capacity": _build_market_capacity_chart(data, target_date, db_service),
        "mainline_turnover_share": _build_mainline_turnover_share_chart(data, target_date),
        "sector_heatmap": _build_sector_heatmap_chart(data),
        "mainline_attack_scatter": _build_mainline_attack_scatter_chart(data),
        "hot_tag_composition": _build_hot_tag_composition_chart(data),
        "cycle_week_view": _build_cycle_week_view_chart(data),
        "turnover_rank": _build_turnover_rank_chart(data, target_date),
        "new_high": _build_new_high_chart(data, target_date),
        "lhb": _build_lhb_chart(data, target_date),
        "price_band": _build_price_band_chart(data, target_date),
        "tail_window": _build_tail_window_chart(data),
    }


def _latest_top50_turnover_share_pct(data: dict[str, Any], target_date: str) -> float | None:
    direct = _safe_float(_first_present(data.get("top50_turnover_share_pct"), data.get("top50_share_pct")))
    if direct is not None:
        return direct

    series = data.get("top50_turnover_share_series")
    rows = series.get("rows") if isinstance(series, dict) else series
    rows = rows if isinstance(rows, list) else []
    if not rows:
        return None
    for row in reversed(rows):
        if not isinstance(row, dict):
            continue
        if _text(row.get("trade_date") or row.get("date")) == target_date:
            return _safe_float(_first_present(row.get("share_pct"), row.get("top50_share_pct")))
    return None


def _extract_market_spine(data: dict[str, Any], target_date: str) -> dict[str, Any]:
    market_stats = data.get("market_stats") if isinstance(data.get("market_stats"), dict) else {}
    return {
        "market_fit": _text(data.get("market_fit") or data.get("market_fit_label")),
        "turnover_summary": _text(data.get("total_turnover")),
        "top50_turnover_share_pct": _latest_top50_turnover_share_pct(data, target_date),
        "up_count": _count_or_none(market_stats.get("up_count")),
        "down_count": _count_or_none(market_stats.get("down_count")),
        "breadth_summary": _breadth_summary(market_stats),
        "market_phase": _text(data.get("market_phase") or data.get("market_trend")),
        "index_structure": _text(data.get("index_structure")),
        "why_it_matters": _text(data.get("market_reason") or data.get("market_summary")),
    }


def _extract_mainline_evidence(data: dict[str, Any]) -> dict[str, Any]:
    snapshot = data.get("market_research_snapshot") if isinstance(data.get("market_research_snapshot"), dict) else {}
    context = data.get("mainline_context") if isinstance(data.get("mainline_context"), dict) else {}
    current_record = _first_dict(
        context.get("current_mainline_history_record"),
        data.get("current_mainline_history_record"),
        snapshot.get("current_mainline_history_record"),
    )
    turnover_summary = _first_dict(
        context.get("mainline_turnover_summary"),
        data.get("mainline_turnover_summary"),
        snapshot.get("mainline_turnover_summary"),
    )
    attack_summary = (
        turnover_summary.get("mainline_attack_evidence_summary")
        if isinstance(turnover_summary.get("mainline_attack_evidence_summary"), dict)
        else {}
    )
    double_summary = (
        turnover_summary.get("double_mainline_summary")
        if isinstance(turnover_summary.get("double_mainline_summary"), dict)
        else {}
    )
    latest_turnover_row = _latest_mainline_turnover_row(turnover_summary, data)
    attack_evidence = []
    attack_evidence.extend(_list_text(context.get("attack_evidence")))
    attack_evidence.extend(_list_text(attack_summary.get("labels")))
    attack_evidence.extend(_list_text(attack_summary.get("conclusion")))
    attack_evidence.extend(_list_text(turnover_summary.get("conclusion")))
    confirmed_line = _text(
        context.get("confirmed_line")
        or context.get("mainline")
        or data.get("mainline_name")
        or current_record.get("primary_mainline")
        or current_record.get("leading_line")
        or current_record.get("mainline")
        or turnover_summary.get("current_mainline")
        or turnover_summary.get("primary_mainline")
        or turnover_summary.get("cycle_mainline")
    )
    return {
        "confirmed_line": confirmed_line,
        "cycle_mainline": _text(
            context.get("cycle_mainline")
            or data.get("cycle_mainline")
            or _meaningful_text(double_summary.get("cycle_mainline"))
            or latest_turnover_row.get("cycle_mainline")
            or turnover_summary.get("current_cycle_mainline")
            or turnover_summary.get("cycle_mainline")
            or current_record.get("cycle_mainline")
            or current_record.get("primary_mainline")
            or confirmed_line
        ),
        "daily_attack_line": _text(
            context.get("daily_attack_line")
            or data.get("daily_attack_line")
            or _meaningful_text(double_summary.get("daily_attack_line"))
            or latest_turnover_row.get("daily_attack_line")
            or turnover_summary.get("current_daily_attack_line")
            or turnover_summary.get("daily_attack_line")
            or current_record.get("daily_attack_line")
            or attack_summary.get("primary_line")
            or confirmed_line
        ),
        "cycle_daily_relationship": _text(
            context.get("cycle_daily_relationship")
            or double_summary.get("relationship")
            or turnover_summary.get("cycle_daily_relationship")
        ),
        "supporting_lines": _list_text(context.get("supporting_lines")),
        "attack_evidence": attack_evidence,
        "turnover_share": _text(context.get("turnover_share") or turnover_summary.get("turnover_share")),
        "fund_flow": _text(context.get("fund_flow") or turnover_summary.get("fund_flow")),
        "sector_breadth": _text(context.get("sector_breadth") or turnover_summary.get("sector_breadth")),
        "continuation_conditions": _list_text(
            context.get("continuation_conditions") or turnover_summary.get("continuation_conditions")
        ),
        "failure_conditions": _list_text(
            context.get("failure_conditions") or turnover_summary.get("failure_conditions")
        ),
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
    mainline = view.get("mainline_evidence") if isinstance(view.get("mainline_evidence"), dict) else {}
    charts = view.get("charts") if isinstance(view.get("charts"), dict) else {}
    sources = view.get("data_sources") if isinstance(view.get("data_sources"), list) else []
    if not action or not _text(action.get("action_summary")):
        missing.append("明日动作")
    if not market or (not _text(market.get("turnover_summary")) and not _text(market.get("breadth_summary"))):
        missing.append("市场结构")
    if market.get("top50_turnover_share_pct") is None:
        missing.append("Top50成交额占比")
    if (charts.get("market_capacity") or {}).get("status") != "ready":
        missing.append("市场容量趋势")
    if (charts.get("mainline_turnover_share") or {}).get("status") != "ready":
        missing.append("主线成交占比趋势")
    if not mainline or (
        not _text(mainline.get("confirmed_line"))
        and not _list_text(mainline.get("attack_evidence"))
        and not _text(mainline.get("fund_flow"))
    ):
        missing.append("主线证据")
    if not sources or all(_text(item.get("status")) == "missing" for item in sources if isinstance(item, dict)):
        missing.append("数据来源")
    return missing


def build_daily_report_view(target_date: str, db_service: Any, *, run_mode: str = "frozen") -> dict[str, Any]:
    target_date = _text(target_date)
    data, loaded = _load_postgres_data(target_date, db_service)
    candidate_actions = _query_candidate_actions(target_date, db_service)
    charts = _extract_charts(data, target_date, db_service)
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
        "market_spine": _extract_market_spine(data, target_date),
        "mainline_evidence": _extract_mainline_evidence(data),
        "charts": charts,
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
    degraded = []
    for key, label in (
        ("sector_heatmap", "板块容量热力图"),
        ("mainline_attack_scatter", "主线攻击证据散点"),
        ("hot_tag_composition", "热榜 Tag 构成"),
        ("cycle_week_view", "板块周视图"),
        ("turnover_rank", "Top50成交额占比"),
        ("new_high", "创新高扩散"),
        ("lhb", "龙虎榜资金"),
        ("price_band", "百元股与低价股风格"),
    ):
        item = charts.get(key) if isinstance(charts.get(key), dict) else {}
        if item.get("status") != "ready":
            degraded.append(label)
    view["diagnostics"]["degraded_facts"] = degraded
    view["diagnostics"]["missing_required_facts"] = _missing_required_facts(view)
    return view


def missing_required_fact_labels(view: dict[str, Any]) -> list[str]:
    diagnostics = view.get("diagnostics") if isinstance(view.get("diagnostics"), dict) else {}
    return list(diagnostics.get("missing_required_facts") or [])


def daily_report_view_has_required_facts(view: dict[str, Any]) -> bool:
    return not missing_required_fact_labels(view)
