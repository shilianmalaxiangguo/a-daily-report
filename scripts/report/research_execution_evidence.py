from __future__ import annotations

import datetime
import re
from copy import deepcopy
from typing import Any

from knowledge.llm_wiki_manifest import is_sha256, stable_json_hash
from report.position_tier_contract import (
    POSITION_TIER_B1_PCT,
    normalize_planned_position_tier_pct,
    normalize_position_tier_pct,
    position_x_to_tier_pct,
)


SCHEMA_VERSION = "research_execution_evidence.v1"
FACT_SCHEMA_VERSION = "research_execution_facts.v1"
DECISION_SCOPE = "explanation_only"

_FIELD_ORDER = (
    "enterprise_premise",
    "valuation_position",
    "current_price_evidence",
    "position_identity",
    "conflict_handling",
    "next_t0_review",
)

_VALUATION_BASIS_FIELDS = (
    "metric",
    "earnings_basis",
    "earnings_basis_type",
    "fact_period_end",
    "earnings_period_end",
    "peer_group",
    "history_window",
    "comparison_result",
)

_PRICE_COMPONENT_FIELDS = (
    "sector_synchrony",
    "price_acceptance",
    "invalidation_condition",
)


def canonical_research_execution_evidence_hash(payload: Any) -> str:
    return stable_json_hash(payload if isinstance(payload, dict) else {}, excluded_keys={"artifact_hash"})


def research_execution_evidence_cache_key(target_date: Any, *, analysis_mode: str) -> tuple[str, str, str]:
    mode = "replay" if analysis_mode == "replay" else "fresh"
    return ("research_execution_evidence", _text(target_date), mode)


def _text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _date(value: Any) -> str:
    text = _text(value)
    try:
        return datetime.date.fromisoformat(text).isoformat()
    except (TypeError, ValueError):
        return ""


def _stock_payload(value: Any) -> dict:
    value = value if isinstance(value, dict) else {}
    nested = value.get("stock") if isinstance(value.get("stock"), dict) else {}
    source = {**value, **nested}
    code = _text(
        source.get("code")
        or source.get("stock_code")
        or source.get("ts_code")
        or source.get("symbol")
        or source.get("代码")
    )
    if "." in code:
        code = code.split(".", 1)[0]
    digits = "".join(char for char in code if char.isdigit())
    if len(digits) >= 6:
        code = digits[-6:]
    name = _text(
        source.get("name")
        or source.get("stock_name")
        or source.get("证券简称")
        or source.get("股票简称")
        or source.get("名称")
    )
    if not code and not name:
        return {}
    return {"code": code, "name": name}


def _stock_key(value: Any) -> str:
    stock = _stock_payload(value)
    return stock.get("code") or stock.get("name") or ""


def _stock_label(value: Any) -> str:
    stock = _stock_payload(value)
    name = stock.get("name") or ""
    code = stock.get("code") or ""
    if name and code:
        return f"{name}({code})"
    return name or code or "无"


def _evidence_field(
    status: str,
    text: str,
    source_date: str = "",
    source: str = "",
    *,
    preserve_text: bool = False,
) -> dict:
    return {
        "status": _text(status) or "insufficient",
        "text": str(text or "") if preserve_text else _text(text),
        "source_date": _date(source_date),
        "source": _text(source),
    }


def _contains_trade_instruction(value: Any) -> bool:
    text = _text(value).lower()
    return any(
        term in text
        for term in (
            "b1",
            "b2",
            "买入",
            "卖出",
            "开仓",
            "建仓",
            "加仓",
            "减仓",
            "补仓",
            "补足",
            "清仓",
            "止盈",
            "止损",
            "抄底",
            "追涨",
            "不参与",
            "参与资格",
            "建议持有",
            "继续持有",
        )
    ) or bool(
        re.search(
            r"(?:立即|及时|尽快|建议|应当|需要|必须|跌破|破位|失效|触发).{0,12}退出"
            r"|退出.{0,8}(?:持仓|交易|仓位)",
            text,
        )
    )


def _contains_price_target(value: Any) -> bool:
    text = _text(value).lower()
    return any(
        term in text
        for term in (
            "目标价",
            "合理价格",
            "合理价位",
            "买入价",
            "卖出价",
            "止盈价",
            "止损价",
        )
    )


def _is_nonempty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(_text(value))


def _is_flat_text_payload(value: Any, fields: tuple[str, ...], *, require_all: bool) -> bool:
    if not isinstance(value, dict) or any(key not in fields for key in value):
        return False
    if require_all and any(key not in value for key in fields):
        return False
    return all(_is_nonempty_text(item) for item in value.values())


def _contains_future_valuation_basis(value: Any) -> bool:
    text = _text(value).lower()
    return bool(
        any(
            term in text
            for term in ("预测", "一致预期", "远期", "forward", "forecast", "consensus")
        )
        or re.search(r"(?<!\d)(?:20)?\d{2}e(?![a-z])", text, flags=re.IGNORECASE)
    )


def _position_tier_x(x_value: Any, pct_value: Any, *, planned: bool) -> int | None:
    try:
        if x_value not in (None, ""):
            return position_x_to_tier_pct(x_value) // POSITION_TIER_B1_PCT
        normalized_pct = (
            normalize_planned_position_tier_pct(pct_value)
            if planned
            else normalize_position_tier_pct(pct_value)
        )
        return normalized_pct // POSITION_TIER_B1_PCT
    except (TypeError, ValueError):
        return None


def _historical_earnings_basis(
    basis: dict,
    *,
    target_date: str,
    query_date: str,
) -> bool:
    earnings_basis = _text(basis.get("earnings_basis"))
    lowered = earnings_basis.lower()
    if not earnings_basis:
        return False
    if _contains_future_valuation_basis(lowered):
        return False

    basis_type = _text(basis.get("earnings_basis_type")).lower()
    if basis_type and basis_type not in {"reported", "ttm", "historical"}:
        return False
    historical_markers = ("ttm", "已披露", "历史", "报告期", "年报", "中报", "季报")
    if not basis_type and not any(marker in lowered for marker in historical_markers):
        return False

    period_raw = _text(basis.get("fact_period_end") or basis.get("earnings_period_end"))
    if period_raw:
        period_end = _date(period_raw)
        if not period_end or period_end > target_date or period_end > query_date:
            return False
    return True


def _valuation_basis_payload(value: Any) -> dict:
    basis = value if isinstance(value, dict) else {}
    return {
        key: _text(basis.get(key))
        for key in _VALUATION_BASIS_FIELDS
        if basis.get(key) not in (None, "")
    }


def _valuation_fact_text(basis: Any) -> str:
    basis = basis if isinstance(basis, dict) else {}
    metric = _text(basis.get("metric"))
    earnings_basis = _text(basis.get("earnings_basis"))
    comparison_scope = "、".join(
        value
        for value in (
            _text(basis.get("peer_group")),
            _text(basis.get("history_window")),
        )
        if value
    )
    comparison_result = _text(basis.get("comparison_result"))
    if not all((metric, earnings_basis, comparison_scope, comparison_result)):
        return ""
    return f"{metric}（{earnings_basis}）相对{comparison_scope}：{comparison_result}"


def _price_components_text(components: Any) -> str:
    if not _is_flat_text_payload(components, _PRICE_COMPONENT_FIELDS, require_all=True):
        return ""
    sector_synchrony = _text(components.get("sector_synchrony"))
    price_acceptance = _text(components.get("price_acceptance"))
    invalidation_condition = _text(components.get("invalidation_condition"))
    if not all((sector_synchrony, price_acceptance, invalidation_condition)):
        return ""
    return (
        f"板块同步：{sector_synchrony}；"
        f"个股承接：{price_acceptance}；"
        f"失效条件：{invalidation_condition}"
    )


def _same_stock(left: Any, right: Any) -> bool:
    left_stock = _stock_payload(left)
    right_stock = _stock_payload(right)
    if left_stock.get("code") and right_stock.get("code"):
        return left_stock["code"] == right_stock["code"]
    return bool(left_stock.get("name") and left_stock.get("name") == right_stock.get("name"))


def _append_object(rows: list[dict], value: Any, role: str) -> None:
    stock = _stock_payload(value)
    if not stock:
        return
    for row in rows:
        if _same_stock(row.get("stock"), stock):
            roles = list(row.get("roles") or [])
            if role and role not in roles:
                roles.append(role)
            row["roles"] = roles
            row["role"] = "、".join(roles)
            return
    rows.append({"stock": stock, "roles": [role] if role else [], "role": role})


def _display_roles(resolution: dict, display: dict, *, confirmed_old: bool) -> list[str]:
    roles = []
    if confirmed_old and _same_stock(display, resolution.get("existing_position_target")):
        roles.append("已确认旧仓")
    if _same_stock(display, resolution.get("tradable_proxy_target")):
        roles.append("可交易替代表达")
    if _same_stock(display, resolution.get("new_entry_target")):
        roles.append("明日执行对象")
    if _same_stock(display, resolution.get("watch_target")):
        roles.append("观察对象")
    return list(dict.fromkeys(roles or ["最终显示对象"]))


def resolve_research_execution_objects(final_target_resolution: Any) -> list[dict]:
    resolution = final_target_resolution if isinstance(final_target_resolution, dict) else {}
    exposure = (
        resolution.get("account_exposure_plan")
        if isinstance(resolution.get("account_exposure_plan"), dict)
        else {}
    )
    confirmed_old = _text(exposure.get("position_fact_status")) == "confirmed"
    display = _stock_payload(resolution.get("display_target"))
    watch = _stock_payload(resolution.get("watch_target"))
    existing = _stock_payload(resolution.get("existing_position_target")) if confirmed_old else {}

    rows: list[dict] = []
    if display:
        for role in _display_roles(resolution, display, confirmed_old=confirmed_old):
            _append_object(rows, display, role)
    elif watch:
        _append_object(rows, watch, "观察对象")

    if existing:
        _append_object(rows, existing, "已确认旧仓")
    if len(rows) < 2 and watch:
        _append_object(rows, watch, "观察对象")
    return rows[:2]


def _fact_rows(data: dict, target_date: str) -> tuple[dict[str, dict], list[str], str]:
    raw = data.get("research_execution_facts") if isinstance(data, dict) else None
    if not isinstance(raw, dict):
        return {}, ["research_execution_facts_missing"], ""
    warnings: list[str] = []
    if raw.get("schema_version") != FACT_SCHEMA_VERSION:
        warnings.append("research_execution_facts_schema_invalid")
        return {}, warnings, ""
    if _date(raw.get("target_date")) != target_date:
        warnings.append("research_execution_facts_target_date_mismatch")
        return {}, warnings, ""
    query_date = _date(raw.get("query_date"))
    if not query_date:
        warnings.append("research_execution_facts_query_date_invalid")
        return {}, warnings, query_date
    if query_date != target_date:
        warnings.append("research_execution_facts_query_date_mismatch")
        return {}, warnings, ""
    rows = raw.get("objects")
    if not isinstance(rows, list):
        warnings.append("research_execution_facts_objects_invalid")
        return {}, warnings, query_date
    result: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            warnings.append("research_execution_fact_object_invalid")
            continue
        key = _stock_key(row.get("stock"))
        if not key:
            warnings.append("research_execution_fact_stock_missing")
            continue
        if key in result:
            warnings.append("research_execution_fact_stock_duplicate")
            continue
        result[key] = deepcopy(row)
    return result, list(dict.fromkeys(warnings)), query_date


def _dated_explicit_fact(
    value: Any,
    *,
    target_date: str,
    query_date: str,
    missing_text: str,
    require_evidence: bool = False,
    require_valuation_basis: bool = False,
) -> tuple[dict, list[str]]:
    value = value if isinstance(value, dict) else {}
    source_date = _date(value.get("source_date"))
    source = _text(value.get("source")) if _is_nonempty_text(value.get("source")) else ""
    text = _text(value.get("text")) if _is_nonempty_text(value.get("text")) else ""
    status = _text(value.get("status")) if _is_nonempty_text(value.get("status")) else ""
    warnings: list[str] = []
    evidence_refs: list[dict] = []
    valuation_basis: dict = {}
    if (
        not source_date
        or source_date > target_date
        or not query_date
        or source_date > query_date
        or not source
        or not text
    ):
        if value:
            warnings.append("research_execution_fact_date_or_source_invalid")
        return _evidence_field("insufficient", missing_text), warnings

    if require_evidence:
        evidence = value.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            warnings.append("enterprise_evidence_incomplete")
            return _evidence_field("insufficient", missing_text), warnings
        for item in evidence:
            if not isinstance(item, dict):
                warnings.append("enterprise_evidence_incomplete")
                return _evidence_field("insufficient", missing_text), warnings
            item_date = _date(item.get("source_date"))
            item_source_value = item.get("source")
            item_fact_value = item.get("fact") or item.get("text")
            item_source = _text(item_source_value) if _is_nonempty_text(item_source_value) else ""
            item_fact = _text(item_fact_value) if _is_nonempty_text(item_fact_value) else ""
            if not (
                item_date
                and item_date <= source_date
                and item_date <= target_date
                and item_date <= query_date
                and item_source
                and item_fact
            ):
                warnings.append("enterprise_evidence_incomplete")
                return _evidence_field("insufficient", missing_text), warnings
            if _contains_trade_instruction(item_fact) or _contains_price_target(item_fact):
                warnings.append("enterprise_evidence_action_text_rejected")
                return _evidence_field("insufficient", missing_text), warnings
            evidence_refs.append(
                {
                    "source_date": item_date,
                    "source": item_source,
                    "fact": item_fact,
                }
            )
        text = "；".join(item["fact"] for item in evidence_refs)
        source_date = max(item["source_date"] for item in evidence_refs)
        source = "、".join(dict.fromkeys(item["source"] for item in evidence_refs))

    if require_valuation_basis:
        if _contains_price_target(text):
            warnings.append("valuation_target_price_not_supported")
            return _evidence_field("insufficient", missing_text), warnings
        basis = value.get("basis") if isinstance(value.get("basis"), dict) else {}
        if not _is_flat_text_payload(basis, _VALUATION_BASIS_FIELDS, require_all=False):
            warnings.append("valuation_basis_fields_invalid")
            return _evidence_field("insufficient", missing_text), warnings
        valuation_basis = _valuation_basis_payload(basis)
        valuation_text = _valuation_fact_text(valuation_basis)
        if not valuation_text:
            warnings.append("valuation_basis_incomplete")
            return _evidence_field("insufficient", missing_text), warnings
        if not _historical_earnings_basis(
            basis,
            target_date=target_date,
            query_date=query_date,
        ):
            warnings.append("valuation_earnings_basis_not_historical")
            return _evidence_field("insufficient", missing_text), warnings
        if _contains_future_valuation_basis(text):
            warnings.append("valuation_text_uses_future_basis")
            return _evidence_field("insufficient", missing_text), warnings
        if any(
            _contains_trade_instruction(item) or _contains_price_target(item)
            for item in valuation_basis.values()
        ):
            warnings.append("valuation_basis_action_text_rejected")
            return _evidence_field("insufficient", missing_text), warnings
        text = valuation_text

    result = _evidence_field(status or "available", text, source_date, source)
    if require_evidence:
        result["evidence_refs"] = evidence_refs
    if require_valuation_basis:
        result["basis"] = valuation_basis
    return result, warnings


def _fact_for_stock(facts: dict[str, dict], stock: dict) -> dict:
    code = stock.get("code") or ""
    name = stock.get("name") or ""
    return facts.get(code) or facts.get(name) or {}


def _matching_final_object(two_layer: dict, stock: dict) -> dict:
    final_object = two_layer.get("final_object") if isinstance(two_layer.get("final_object"), dict) else {}
    return final_object if _same_stock(final_object.get("stock"), stock) else {}


def _price_evidence(data: dict, stock: dict, target_date: str, explicit: dict, query_date: str) -> tuple[dict, list[str]]:
    explicit_price, warnings = _dated_explicit_fact(
        explicit.get("current_price_evidence"),
        target_date=target_date,
        query_date=query_date,
        missing_text="价格证据不足，只保留研究观察",
    )
    if explicit_price.get("status") != "insufficient":
        components = (
            explicit.get("current_price_evidence", {}).get("components")
            if isinstance(explicit.get("current_price_evidence"), dict)
            else {}
        )
        components = components if isinstance(components, dict) else {}
        component_text = _price_components_text(components)
        if component_text:
            raw_texts = [explicit.get("current_price_evidence", {}).get("text")]
            raw_texts.extend(components.get(key) for key in _PRICE_COMPONENT_FIELDS)
            if any(_contains_trade_instruction(item) for item in raw_texts):
                warnings.append("current_price_evidence_action_text_rejected")
            else:
                result = _evidence_field(
                    explicit_price.get("status") or "available",
                    component_text,
                    explicit_price.get("source_date"),
                    explicit_price.get("source"),
                )
                result["components"] = {
                    key: _text(components.get(key))
                    for key in _PRICE_COMPONENT_FIELDS
                }
                return result, warnings
        warnings.append("current_price_evidence_components_incomplete")

    two_layer = data.get("two_layer_decision_payload") if isinstance(data.get("two_layer_decision_payload"), dict) else {}
    resolution = data.get("final_target_resolution") if isinstance(data.get("final_target_resolution"), dict) else {}
    old_plan = resolution.get("old_position_plan") if isinstance(resolution.get("old_position_plan"), dict) else {}
    if _same_stock(resolution.get("existing_position_target"), stock) and old_plan:
        invalidations = [_text(item) for item in old_plan.get("invalidation_lines") or [] if _text(item)]
        decision_class = _text(old_plan.get("decision_class"))
        basis = _text(old_plan.get("relative_strength_basis"))
        parts = []
        if decision_class == "failed":
            parts.append("当前交易已失效")
        if basis:
            parts.append(basis)
        if invalidations:
            parts.append("失效线：" + "；".join(invalidations))
        if parts:
            return _evidence_field(
                "available",
                "；".join(parts),
                target_date,
                "final_target_resolution.old_position_plan",
            ), warnings

    final_object = _matching_final_object(two_layer, stock)
    if final_object:
        execution = [_text(item) for item in final_object.get("execution_conditions") or [] if _text(item)]
        observation = [_text(item) for item in final_object.get("observation_conditions") or [] if _text(item)]
        failures = [_text(item) for item in final_object.get("failure_conditions") or [] if _text(item)]
        conditions = [*execution, *observation, *failures]
        if conditions:
            return _evidence_field(
                "insufficient",
                "当前价格事实不足；次日只按正式条件确认：" + "；".join(conditions),
                target_date,
                "two_layer_decision_payload.final_object",
            ), warnings
    return _evidence_field("insufficient", "价格证据不足，只保留研究观察"), warnings


def _position_evidence(data: dict, stock: dict, target_date: str) -> dict:
    resolution = data.get("final_target_resolution") if isinstance(data.get("final_target_resolution"), dict) else {}
    two_layer = data.get("two_layer_decision_payload") if isinstance(data.get("two_layer_decision_payload"), dict) else {}
    exposure = resolution.get("account_exposure_plan") if isinstance(resolution.get("account_exposure_plan"), dict) else {}
    status = _text(exposure.get("position_fact_status")) or "unknown"
    old_plan = resolution.get("old_position_plan") if isinstance(resolution.get("old_position_plan"), dict) else {}
    if _same_stock(resolution.get("existing_position_target"), stock):
        if status == "confirmed":
            decision_class = _text(old_plan.get("decision_class"))
            trade_role = _text(old_plan.get("trade_role"))
            if decision_class == "failed":
                identity = "已失效旧仓"
            elif _matching_final_object(two_layer, stock):
                old_x = _position_tier_x(
                    exposure.get("old_position_x"),
                    exposure.get("old_position_pct"),
                    planned=False,
                )
                planned_x = _position_tier_x(
                    exposure.get("planned_new_entry_x"),
                    exposure.get("planned_new_entry_pct"),
                    planned=True,
                )
                if old_x is not None and old_x >= 2:
                    identity = "已有B1+B2；计划仓位已满足，不再增加"
                elif (
                    old_x is not None
                    and old_x >= 1
                    and planned_x is not None
                    and planned_x >= 2
                ):
                    identity = "已有B1参与资格；B2只在确认后补"
                elif old_x is not None and old_x >= 1:
                    identity = "已有B1参与资格；计划仓位已满足，不再补"
                else:
                    identity = "已确认旧仓，仓位身份待复核"
            elif decision_class == "review_at_10_10" or (
                decision_class == "normal" and trade_role == "tplus2_exit"
            ):
                identity = "趋势观察仓"
            else:
                identity = "已确认旧仓，仓位身份待复核"
            return _evidence_field("available", identity, target_date, "final_target_resolution.account_exposure_plan")
        if status == "pending_confirmation":
            return _evidence_field("available", "持仓未知，外部交易待核实", target_date, "final_target_resolution.account_exposure_plan")
        if status == "none":
            return _evidence_field("available", "无仓位", target_date, "final_target_resolution.account_exposure_plan")
        return _evidence_field("available", "持仓未知，不推导旧仓动作", target_date, "final_target_resolution.account_exposure_plan")

    final_object = _matching_final_object(two_layer, stock)
    if final_object and _text(final_object.get("identity")) in {"明日执行对象", "明日计划对象"}:
        front = two_layer.get("front_decision") if isinstance(two_layer.get("front_decision"), dict) else {}
        pct = front.get("planned_position_pct", front.get("position_pct"))
        try:
            pct_value = int(float(pct))
        except (TypeError, ValueError):
            pct_value = 0
        if pct_value >= 100:
            identity = "B1参与资格；B2只在确认后补"
        elif pct_value >= 50:
            identity = "B1参与资格"
        else:
            identity = "研究观察"
        if status == "none":
            identity = f"无仓位；{identity}"
        elif status in {"unknown", "pending_confirmation"}:
            identity = f"持仓未知；{identity}"
        return _evidence_field("available", identity, target_date, "two_layer_decision_payload.front_decision")
    if status == "none":
        identity = "无仓位；研究观察"
    elif status in {"unknown", "pending_confirmation"}:
        identity = "持仓未知；研究观察"
    else:
        identity = "研究观察"
    return _evidence_field("available", identity, target_date, "final_target_resolution.watch_target")


def _conflict_handling(data: dict, stock: dict, target_date: str) -> dict:
    resolution = data.get("final_target_resolution") if isinstance(data.get("final_target_resolution"), dict) else {}
    two_layer = data.get("two_layer_decision_payload") if isinstance(data.get("two_layer_decision_payload"), dict) else {}
    if _same_stock(resolution.get("existing_position_target"), stock):
        rows = two_layer.get("old_position_action_rows") if isinstance(two_layer.get("old_position_action_rows"), dict) else {}
        action = rows.get("旧仓动作")
        if _text(action):
            return _evidence_field(
                "available",
                action,
                target_date,
                "two_layer_decision_payload.old_position_action_rows",
                preserve_text=True,
            )
    final_object = _matching_final_object(two_layer, stock)
    if final_object:
        action = final_object.get("execution_type")
        if _text(action):
            return _evidence_field(
                "available",
                action,
                target_date,
                "two_layer_decision_payload.final_object",
                preserve_text=True,
            )
    return _evidence_field("insufficient", "只列事实缺口，不新增动作")


def _next_t0_review(
    enterprise: dict,
    valuation: dict,
    price: dict,
    *,
    target_date: str,
) -> dict:
    missing = []
    if enterprise.get("status") == "insufficient":
        missing.append("企业前提")
    if valuation.get("status") == "insufficient":
        missing.append("估值位置")
    if price.get("status") == "insufficient":
        missing.append("价格证据")
    if missing:
        text = (
            "下一份T0日报补齐"
            + "、".join(missing)
            + "；事实补齐前不新增参与，当前动作不变"
        )
    else:
        text = "下一份T0日报重新核对企业、估值、板块同步、个股承接和失效条件；当前动作不变"
    return _evidence_field("available", text, target_date, "research_execution_evidence.v1")


def build_research_execution_evidence(
    data: Any,
    *,
    target_date: str,
    analysis_mode: str,
    source_decision_hash: str,
) -> dict:
    data = data if isinstance(data, dict) else {}
    normalized_target = _date(target_date)
    mode = "replay" if analysis_mode == "replay" else "fresh"
    resolution = data.get("final_target_resolution") if isinstance(data.get("final_target_resolution"), dict) else {}
    objects = resolve_research_execution_objects(resolution)
    fact_rows, warnings, facts_query_date = _fact_rows(data, normalized_target)
    built_objects = []
    for row in objects:
        stock = row["stock"]
        explicit = _fact_for_stock(fact_rows, stock)
        enterprise, enterprise_warnings = _dated_explicit_fact(
            explicit.get("enterprise_premise"),
            target_date=normalized_target,
            query_date=facts_query_date,
            missing_text="事实不足，不能判断企业前提是否变化",
            require_evidence=True,
        )
        valuation, valuation_warnings = _dated_explicit_fact(
            explicit.get("valuation_position"),
            target_date=normalized_target,
            query_date=facts_query_date,
            missing_text="事实不足，不因跌幅直接判定便宜",
            require_valuation_basis=True,
        )
        price, price_warnings = _price_evidence(
            data,
            stock,
            normalized_target,
            explicit,
            facts_query_date,
        )
        position = _position_evidence(data, stock, normalized_target)
        conflict = _conflict_handling(data, stock, normalized_target)
        next_review = _next_t0_review(
            enterprise,
            valuation,
            price,
            target_date=normalized_target,
        )
        warnings.extend(enterprise_warnings)
        warnings.extend(valuation_warnings)
        warnings.extend(price_warnings)
        built_objects.append(
            {
                "stock": stock,
                "role": row.get("role") or "观察对象",
                "roles": list(row.get("roles") or []),
                "enterprise_premise": enterprise,
                "valuation_position": valuation,
                "current_price_evidence": price,
                "position_identity": position,
                "conflict_handling": conflict,
                "next_t0_review": next_review,
            }
        )

    artifact = {
        "schema_version": SCHEMA_VERSION,
        "target_date": normalized_target,
        "query_date": facts_query_date or normalized_target,
        "analysis_mode": mode,
        "artifact_origin": "computed",
        "availability": "available" if built_objects else "unavailable",
        "decision_scope": DECISION_SCOPE,
        "source_decision_hash": _text(source_decision_hash),
        "objects": built_objects,
        "warnings": list(dict.fromkeys(warnings)),
    }
    if not built_objects:
        artifact["warnings"] = list(dict.fromkeys([*artifact["warnings"], "research_execution_object_missing"]))
    artifact["artifact_hash"] = canonical_research_execution_evidence_hash(artifact)
    return artifact


def validate_research_execution_evidence(
    artifact: Any,
    *,
    target_date: str,
    source_decision_hash: str = "",
    final_target_resolution: Any = None,
    formal_data: Any = None,
) -> tuple[bool, list[str]]:
    if not isinstance(artifact, dict):
        return False, ["research_execution_evidence_type_invalid"]
    errors = []
    normalized_target = _date(target_date)
    if artifact.get("schema_version") != SCHEMA_VERSION:
        errors.append("research_execution_evidence_schema_invalid")
    if not normalized_target or _date(artifact.get("target_date")) != normalized_target:
        errors.append("research_execution_evidence_target_date_mismatch")
    query_date = _date(artifact.get("query_date"))
    if not query_date:
        errors.append("research_execution_evidence_query_date_invalid")
    elif normalized_target and query_date != normalized_target:
        errors.append("research_execution_evidence_query_date_mismatch")
    if artifact.get("analysis_mode") not in {"fresh", "replay"}:
        errors.append("research_execution_evidence_analysis_mode_invalid")
    if artifact.get("decision_scope") != DECISION_SCOPE:
        errors.append("research_execution_evidence_scope_invalid")
    if not is_sha256(artifact.get("source_decision_hash")):
        errors.append("research_execution_evidence_decision_hash_invalid")
    if source_decision_hash and _text(artifact.get("source_decision_hash")) != _text(source_decision_hash):
        errors.append("research_execution_evidence_decision_mismatch")
    objects = artifact.get("objects")
    if not isinstance(objects, list) or len(objects) > 2:
        errors.append("research_execution_evidence_objects_invalid")
    else:
        keys = []
        expected_objects = (
            resolve_research_execution_objects(final_target_resolution)
            if isinstance(final_target_resolution, dict)
            else []
        )
        if isinstance(final_target_resolution, dict):
            expected_keys = [_stock_key(row.get("stock")) for row in expected_objects]
            actual_keys = [
                _stock_key(row.get("stock"))
                for row in objects
                if isinstance(row, dict)
            ]
            if actual_keys != expected_keys:
                errors.append("research_execution_evidence_object_scope_mismatch")
            elif any(
                _stock_payload(actual.get("stock")) != _stock_payload(expected.get("stock"))
                for actual, expected in zip(objects, expected_objects)
                if isinstance(actual, dict)
            ):
                errors.append("research_execution_evidence_object_identity_mismatch")
            elif any(
                _text(actual.get("role")) != _text(expected.get("role"))
                or list(actual.get("roles") or []) != list(expected.get("roles") or [])
                for actual, expected in zip(objects, expected_objects)
                if isinstance(actual, dict)
            ):
                errors.append("research_execution_evidence_object_role_mismatch")
        for row in objects:
            if not isinstance(row, dict) or not _stock_key(row.get("stock")):
                errors.append("research_execution_evidence_object_invalid")
                continue
            key = _stock_key(row.get("stock"))
            if key in keys:
                errors.append("research_execution_evidence_object_duplicate")
            keys.append(key)
            for field in _FIELD_ORDER:
                evidence = row.get(field)
                if not isinstance(evidence, dict) or not _text(evidence.get("text")):
                    errors.append(f"research_execution_evidence_{field}_invalid")
                    continue
                status = _text(evidence.get("status"))
                source_date_raw = _text(evidence.get("source_date"))
                source_date = _date(source_date_raw)
                source = _text(evidence.get("source"))
                if source_date_raw and not source_date:
                    errors.append(f"research_execution_evidence_{field}_source_date_invalid")
                if source_date and normalized_target and source_date > normalized_target:
                    errors.append(f"research_execution_evidence_{field}_source_date_future")
                if source_date and query_date and source_date > query_date:
                    errors.append(f"research_execution_evidence_{field}_source_date_after_query")
                if status != "insufficient" and (not source_date or not source):
                    errors.append(f"research_execution_evidence_{field}_source_missing")
            enterprise = row.get("enterprise_premise") if isinstance(row.get("enterprise_premise"), dict) else {}
            if _text(enterprise.get("status")) == "insufficient":
                if _text(enterprise.get("text")) != "事实不足，不能判断企业前提是否变化":
                    errors.append("research_execution_evidence_enterprise_insufficient_text_invalid")
            else:
                refs = enterprise.get("evidence_refs")
                if not isinstance(refs, list) or not refs:
                    errors.append("research_execution_evidence_enterprise_refs_invalid")
                else:
                    facts = []
                    for ref in refs:
                        ref = ref if isinstance(ref, dict) else {}
                        ref_date = _date(ref.get("source_date"))
                        ref_source = (
                            _text(ref.get("source"))
                            if _is_nonempty_text(ref.get("source"))
                            else ""
                        )
                        ref_fact = (
                            _text(ref.get("fact"))
                            if _is_nonempty_text(ref.get("fact"))
                            else ""
                        )
                        if not (
                            ref_date
                            and ref_date <= _date(enterprise.get("source_date"))
                            and ref_date <= normalized_target
                            and ref_date <= query_date
                            and ref_source
                            and ref_fact
                        ):
                            errors.append("research_execution_evidence_enterprise_refs_invalid")
                            break
                        if _contains_trade_instruction(ref_fact) or _contains_price_target(ref_fact):
                            errors.append("research_execution_evidence_enterprise_action_text_invalid")
                            break
                        facts.append(ref_fact)
                    if facts and _text(enterprise.get("text")) != "；".join(facts):
                        errors.append("research_execution_evidence_enterprise_text_mismatch")
                    expected_source_date = max(
                        (_date(ref.get("source_date")) for ref in refs if isinstance(ref, dict)),
                        default="",
                    )
                    expected_source = "、".join(
                        dict.fromkeys(
                            _text(ref.get("source"))
                            for ref in refs
                            if isinstance(ref, dict) and _text(ref.get("source"))
                        )
                    )
                    if (
                        _date(enterprise.get("source_date")) != expected_source_date
                        or _text(enterprise.get("source")) != expected_source
                    ):
                        errors.append("research_execution_evidence_enterprise_source_mismatch")
            valuation = row.get("valuation_position") if isinstance(row.get("valuation_position"), dict) else {}
            if _text(valuation.get("status")) == "insufficient":
                if _text(valuation.get("text")) != "事实不足，不因跌幅直接判定便宜":
                    errors.append("research_execution_evidence_valuation_insufficient_text_invalid")
            else:
                basis = valuation.get("basis") if isinstance(valuation.get("basis"), dict) else {}
                if (
                    not _is_flat_text_payload(basis, _VALUATION_BASIS_FIELDS, require_all=False)
                    or _contains_price_target(valuation.get("text"))
                    or _contains_trade_instruction(valuation.get("text"))
                    or not _valuation_fact_text(basis)
                    or not _historical_earnings_basis(
                        basis,
                        target_date=normalized_target,
                        query_date=query_date,
                    )
                ):
                    errors.append("research_execution_evidence_valuation_basis_invalid")
                elif _text(valuation.get("text")) != _valuation_fact_text(basis):
                    errors.append("research_execution_evidence_valuation_text_mismatch")
                if any(
                    _contains_trade_instruction(item) or _contains_price_target(item)
                    for item in basis.values()
                ):
                    errors.append("research_execution_evidence_valuation_action_text_invalid")
            price = row.get("current_price_evidence") if isinstance(row.get("current_price_evidence"), dict) else {}
            if _text(price.get("status")) != "insufficient" and "components" in price:
                components = price.get("components") if isinstance(price.get("components"), dict) else {}
                if not _price_components_text(components):
                    errors.append("research_execution_evidence_price_components_invalid")
                elif _text(price.get("text")) != _price_components_text(components):
                    errors.append("research_execution_evidence_price_text_mismatch")
                if (
                    _contains_trade_instruction(price.get("text"))
                    or _contains_price_target(price.get("text"))
                    or any(
                        _contains_trade_instruction(value) or _contains_price_target(value)
                        for value in components.values()
                    )
                ):
                    errors.append("research_execution_evidence_price_action_text_invalid")
            if isinstance(formal_data, dict):
                expected_position = _position_evidence(formal_data, row.get("stock") or {}, normalized_target)
                expected_conflict = _conflict_handling(formal_data, row.get("stock") or {}, normalized_target)
                expected_next_review = _next_t0_review(
                    enterprise,
                    valuation,
                    price,
                    target_date=normalized_target,
                )
                if row.get("position_identity") != expected_position:
                    errors.append("research_execution_evidence_position_identity_mismatch")
                if row.get("conflict_handling") != expected_conflict:
                    errors.append("research_execution_evidence_conflict_handling_mismatch")
                if row.get("next_t0_review") != expected_next_review:
                    errors.append("research_execution_evidence_next_t0_review_mismatch")
                if "components" not in price:
                    expected_price, _ = _price_evidence(
                        formal_data,
                        row.get("stock") or {},
                        normalized_target,
                        {},
                        normalized_target,
                    )
                    if price != expected_price:
                        errors.append("research_execution_evidence_price_formal_mismatch")
    expected_hash = canonical_research_execution_evidence_hash(artifact)
    if _text(artifact.get("artifact_hash")) != expected_hash:
        errors.append("research_execution_evidence_hash_mismatch")
    return not errors, list(dict.fromkeys(errors))


def _cell(value: Any) -> str:
    return str(value or "").replace("|", "｜").replace("\r\n", "\n").replace("\r", "\n").replace("\n", "；")


def _render_field(field: Any) -> str:
    field = field if isinstance(field, dict) else {}
    text = _cell(field.get("text")) or "事实不足"
    source_date = _date(field.get("source_date"))
    source = _cell(field.get("source"))
    provenance = " / ".join(part for part in (source_date, source) if part)
    return f"{text}（{provenance}）" if provenance else text


def render_research_execution_evidence_lines(artifact: Any) -> list[str]:
    valid, _ = validate_research_execution_evidence(
        artifact,
        target_date=(artifact or {}).get("target_date") if isinstance(artifact, dict) else "",
        source_decision_hash=(artifact or {}).get("source_decision_hash") if isinstance(artifact, dict) else "",
    )
    objects = artifact.get("objects") if isinstance(artifact, dict) else []
    if not valid or not objects:
        return []
    lines = [
        "## 研究与执行分层（研究证据）",
        "| 对象 | 企业前提 | 估值位置 | 当前价格证据 | 仓位身份 | 冲突处理 | 下一次 T0 复核 |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in objects:
        object_text = _stock_label(row.get("stock"))
        role = _cell(row.get("role"))
        if role:
            object_text = f"{object_text}（{role}）"
        lines.append(
            "| "
            + " | ".join(
                [
                    object_text,
                    _render_field(row.get("enterprise_premise")),
                    _render_field(row.get("valuation_position")),
                    _render_field(row.get("current_price_evidence")),
                    _render_field(row.get("position_identity")),
                    _render_field(row.get("conflict_handling")),
                    _render_field(row.get("next_t0_review")),
                ]
            )
            + " |"
        )
    return lines


__all__ = [
    "DECISION_SCOPE",
    "FACT_SCHEMA_VERSION",
    "SCHEMA_VERSION",
    "build_research_execution_evidence",
    "canonical_research_execution_evidence_hash",
    "render_research_execution_evidence_lines",
    "research_execution_evidence_cache_key",
    "resolve_research_execution_objects",
    "validate_research_execution_evidence",
]
