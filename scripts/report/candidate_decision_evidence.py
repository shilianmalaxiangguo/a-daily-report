from __future__ import annotations

import datetime
import math
import re
from copy import deepcopy
from typing import Any, Iterable

from knowledge.llm_wiki_manifest import stable_json_hash


SCHEMA_VERSION = "candidate_decision_evidence.v1"
FACT_SCHEMA_VERSION = "candidate_decision_evidence_facts.v1"
REPLAY_SCHEMA_VERSION = "candidate_decision_evidence_replay.v1"
SECTOR_DIFFUSION_STAGE_SCHEMA_VERSION = "sector_diffusion_stage_evidence.v1"
SECTOR_TOURNAMENT_THREE_AXIS_SCHEMA_VERSION = "sector_tournament_three_axis.v1"
DECISION_SCOPE = "explanation_only"
STAGE_MAINLINE_MIN_TRADING_DAYS = 10

STAGE_MAINLINE_STATUS_INSUFFICIENT = "事实不足"
STAGE_MAINLINE_STATUS_UNCONFIRMED = "未形成阶段主线"
STAGE_MAINLINE_STATUS_CANDIDATE = "阶段主线候选"
STAGE_MAINLINE_STATUS_CONFIRMED = "阶段主线已确认"
STAGE_MAINLINE_STATUS_WEAKENED = "阶段主线弱化"
STAGE_MAINLINE_STATUS_INVALIDATED = "阶段主线失效"

PRICE_ACCEPTANCE_STATUSES = {
    "accepted",
    "rejected",
    "unresolved",
    "not_applicable",
}
QUALIFICATION_STATUSES = {
    "qualified",
    "not_qualified",
    "unresolved",
    "not_applicable",
}
COMPARISON_FIELDS = (
    "sector_continuity",
    "stage_fit",
    "carrier_quality",
    "upside_space",
    "loss_boundary",
    "executability",
)
REPLAY_PATHS = (
    "moderate_volume",
    "expanded_accepted",
    "expanded_declining",
)
REPLAY_HORIZONS = (3, 5, 10)

REQUIRED_ARTIFACT_FIELDS = {
    "sector_qualifications": list,
    "candidates": list,
    "observations": list,
    "holdings": list,
    "volume_price_evidence": dict,
    "capital_options": dict,
    "comparison": dict,
    "missing_fields": list,
    "source_dates": dict,
    "warnings": list,
    "input_hash": str,
    "availability": str,
    "artifact_hash": str,
}

_ISO_DATE_IN_TEXT_PATTERN = re.compile(r"(?<!\d)(\d{4}-\d{2}-\d{2})(?!\d)")


def _text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _date(value: Any) -> str:
    text = _text(value)
    try:
        return datetime.date.fromisoformat(text).isoformat()
    except (TypeError, ValueError):
        return ""


def _is_present(value: Any) -> bool:
    return value is not None and value != ""


def _first_present(*values: Any) -> Any:
    return next((value for value in values if _is_present(value)), None)


def _optional_date(value: Any, missing: list[str], field: str) -> str:
    if not _is_present(value):
        return ""
    normalized = _date(value)
    if not normalized:
        missing.append(field)
    return normalized


def _optional_mapping(raw: dict, field: str, missing: list[str]) -> dict:
    value = raw.get(field)
    if not _is_present(value):
        return {}
    if not isinstance(value, dict):
        missing.append(field)
        return {}
    return value


def _float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        number = float(value)
        return number if number == number else None
    except (TypeError, ValueError):
        return None


def _percentage(value: Any, missing: list[str], field: str) -> float | None:
    if not _is_present(value):
        return None
    if isinstance(value, bool):
        missing.append(field)
        return None
    number = _float(value)
    if number is None or not 0 <= number <= 100:
        missing.append(field)
        return None
    return number


def _valid_normalized_percentage(value: Any) -> bool:
    return (
        value is None
        or (
            not isinstance(value, bool)
            and isinstance(value, (int, float))
            and 0 <= value <= 100
        )
    )


def _list(value: Any) -> list:
    return list(value) if isinstance(value, (list, tuple)) else []


def _strings(value: Any) -> list[str]:
    return list(dict.fromkeys(_text(item) for item in _list(value) if _text(item)))


def _as_of_strings(value: Any, target_date: str) -> list[str]:
    normalized = []
    for item in _list(value):
        if isinstance(item, dict):
            item_date = next(
                (
                    _date(item.get(key))
                    for key in ("source_date", "trade_date", "date", "query_date")
                    if _date(item.get(key))
                ),
                "",
            )
            if item_date and item_date > target_date:
                continue
            text = _text(
                item.get("text")
                or item.get("evidence")
                or item.get("description")
                or item.get("source_ref")
                or item.get("ref")
            )
        else:
            text = _text(item)
        if not text:
            continue
        embedded_dates = [
            _date(match)
            for match in _ISO_DATE_IN_TEXT_PATTERN.findall(text)
        ]
        if any(date and date > target_date for date in embedded_dates):
            continue
        normalized.append(text)
    return list(dict.fromkeys(normalized))


def _dated_as_of_evidence_rows(value: Any, target_date: str) -> list[dict]:
    normalized = []
    for item in _list(value):
        item_date = ""
        if isinstance(item, dict):
            item_date = next(
                (
                    _date(item.get(key))
                    for key in ("source_date", "trade_date", "date", "query_date")
                    if _date(item.get(key))
                ),
                "",
            )
            text = _text(
                item.get("text")
                or item.get("evidence")
                or item.get("description")
            )
        else:
            text = _text(item)
        if not text:
            continue
        embedded_dates = [
            _date(match)
            for match in _ISO_DATE_IN_TEXT_PATTERN.findall(text)
            if _date(match)
        ]
        dated = bool(item_date or embedded_dates)
        if (
            not dated
            or (item_date and item_date > target_date)
            or any(date > target_date for date in embedded_dates)
        ):
            continue
        source_date = item_date or max(embedded_dates)
        row = {"text": text, "source_date": source_date}
        if row not in normalized:
            normalized.append(row)
    return normalized


def _stock(value: Any) -> dict:
    value = value if isinstance(value, dict) else {}
    nested = value.get("stock") if isinstance(value.get("stock"), dict) else {}
    source = {**value, **nested}
    code = _text(
        source.get("code")
        or source.get("stock_code")
        or source.get("ts_code")
        or source.get("symbol")
    )
    if "." in code:
        code = code.split(".", 1)[0]
    digits = "".join(char for char in code if char.isdigit())
    if len(digits) >= 6:
        code = digits[-6:]
    name = _text(source.get("name") or source.get("stock_name") or source.get("名称"))
    return {"code": code, "name": name} if code or name else {}


def _stock_key(value: Any) -> str:
    stock = _stock(value)
    return stock.get("code") or stock.get("name") or ""


def _sector(value: Any) -> str:
    value = value if isinstance(value, dict) else {}
    return _text(
        value.get("sector")
        or value.get("sector_name")
        or value.get("direction")
        or value.get("proven_direction")
    )


def _enum(value: Any, allowed: set[str], default: str = "unresolved") -> str:
    text = _text(value).lower()
    return text if text in allowed else default


def _qualification(value: Any) -> str:
    if isinstance(value, bool):
        return "qualified" if value else "not_qualified"
    if isinstance(value, dict):
        if isinstance(value.get("qualified"), bool):
            return "qualified" if value.get("qualified") else "not_qualified"
        value = value.get("status")
    return _enum(value, QUALIFICATION_STATUSES)


def _facts_bundle(data: dict, report_date: str) -> tuple[dict, list[str]]:
    facts = data.get("candidate_decision_evidence_facts")
    if not isinstance(facts, dict) or not facts:
        return {}, []
    warnings = []
    if _text(facts.get("schema_version")) != FACT_SCHEMA_VERSION:
        warnings.append("candidate_decision_evidence_facts_schema_invalid")
    fact_report_date = _date(facts.get("report_date") or facts.get("target_date"))
    query_date = _date(facts.get("query_date"))
    if fact_report_date != report_date:
        warnings.append("candidate_decision_evidence_facts_report_date_mismatch")
    if query_date != report_date:
        warnings.append("candidate_decision_evidence_facts_query_date_mismatch")
    return ({}, warnings) if warnings else (deepcopy(facts), [])


def _source_date(value: Any, report_date: str, missing: list[str], field: str) -> str:
    normalized = _date(value)
    if not normalized or normalized > report_date:
        missing.append(field)
        return ""
    return normalized


def _normalize_sector_row(raw: Any, report_date: str) -> dict:
    raw = raw if isinstance(raw, dict) else {}
    missing = _strings(raw.get("missing_fields"))
    sector = _sector(raw)
    if not sector:
        missing.append("sector")
    source_date = _source_date(raw.get("source_date"), report_date, missing, "source_date")
    status = _qualification(raw)
    if not sector or not source_date:
        status = "unresolved"
    return {
        "sector": sector,
        "stage": _text(raw.get("stage") or raw.get("sector_stage")),
        "status": status,
        "evidence": _strings(raw.get("evidence")),
        "missing_fields": sorted(set(missing)),
        "source_date": source_date,
        "source": _text(raw.get("source")),
    }


def _sector_qualifications(workflow: dict, facts: dict, report_date: str) -> list[dict]:
    explicit = _list(facts.get("sector_qualifications"))
    rows = [_normalize_sector_row(item, report_date) for item in explicit]
    if not rows:
        proof = workflow.get("local_trend_sector_proof")
        proof = proof if isinstance(proof, dict) else {}
        source_dates = workflow.get("source_dates") if isinstance(workflow.get("source_dates"), dict) else {}
        direction = _text(proof.get("direction"))
        if direction:
            evidence = [
                field
                for field in (
                    "cross_day_continuity",
                    "divergence_acceptance",
                    "internal_expansion",
                    "competition_comparison",
                )
                if proof.get(field) is True
            ]
            rows = [
                _normalize_sector_row(
                    {
                        "sector": direction,
                        "stage": (
                            workflow.get("sector_layer", {}).get("sector_emotion", "")
                            if isinstance(workflow.get("sector_layer"), dict)
                            else ""
                        ),
                        "status": "qualified" if proof.get("complete") else "not_qualified",
                        "evidence": evidence,
                        "missing_fields": proof.get("evidence_gaps"),
                        "source_date": proof.get("source_date") or source_dates.get("sector_source_date"),
                        "source": "selection_workflow.local_trend_sector_proof",
                    },
                    report_date,
                )
            ]
    deduped = {}
    for row in sorted(rows, key=stable_json_hash):
        key = row.get("sector") or stable_json_hash(row)
        deduped.setdefault(key, row)
    return sorted(deduped.values(), key=lambda item: item.get("sector", ""))


def _comparison_fields(raw: Any) -> dict:
    raw = raw if isinstance(raw, dict) else {}
    supplied = raw.get("comparison_fields") if isinstance(raw.get("comparison_fields"), dict) else {}
    return {field: _qualification(supplied.get(field)) for field in COMPARISON_FIELDS}


def _candidate_row(
    raw: dict,
    explicit: dict,
    sector_status: str,
    *,
    in_workflow: bool,
) -> dict:
    merged = {**raw, **explicit}
    stock = _stock(merged)
    sector = _sector(merged)
    workflow_qualified = raw.get("new_entry_qualified") is True if in_workflow else False
    explicit_status = _qualification(explicit.get("stock_qualification")) if explicit else "unresolved"
    stock_status = "qualified" if workflow_qualified and explicit_status != "not_qualified" else "not_qualified"
    if not in_workflow:
        stock_status = "unresolved"
    exclusions = _strings(
        [
            *_list(raw.get("blocking_reasons")),
            raw.get("price_action_block_reason"),
            raw.get("eliminated_reason"),
            *_list(explicit.get("exclusion_reasons")),
        ]
    )
    return {
        "stock": stock,
        "sector": sector,
        "sector_phase": _text(explicit.get("sector_phase") or explicit.get("stage")),
        "sector_qualification": sector_status,
        "carrier_role": _text(
            explicit.get("carrier_role")
            or raw.get("sector_role")
            or raw.get("candidate_role")
        ),
        "stock_qualification": stock_status,
        "sniper_structure": deepcopy(explicit.get("sniper_structure"))
        if isinstance(explicit.get("sniper_structure"), dict)
        else {},
        "acceptance_evidence": _strings(explicit.get("acceptance_evidence")),
        "invalidation_distance": explicit.get("invalidation_distance"),
        "upside_space": explicit.get("upside_space"),
        "executability": _qualification(explicit.get("executability")),
        "exclusion_reasons": exclusions,
        "comparison_fields": _comparison_fields(explicit),
        "clear_advantage": explicit.get("clear_advantage") is True,
        "evidence_sources": _strings(
            [*_list(raw.get("source_pools")), *_list(explicit.get("evidence_sources"))]
        ),
        "in_selection_workflow": in_workflow,
    }


def _candidate_rows(
    workflow: dict,
    facts: dict,
    sectors: list[dict],
) -> tuple[list[dict], list[dict]]:
    explicit_rows = {
        _stock_key(item): item
        for item in _list(facts.get("candidates"))
        if isinstance(item, dict) and _stock_key(item)
    }
    sector_statuses = {row.get("sector"): row.get("status") for row in sectors}
    candidates = []
    observations = []
    seen = set()
    for raw in _list(workflow.get("candidate_pool")):
        if not isinstance(raw, dict) or not _stock_key(raw):
            continue
        key = _stock_key(raw)
        seen.add(key)
        explicit = explicit_rows.get(key, {})
        sector = _sector({**raw, **explicit})
        row = _candidate_row(
            raw,
            explicit,
            sector_statuses.get(sector, "unresolved"),
            in_workflow=True,
        )
        if row["sector_qualification"] == "qualified" and row["stock_qualification"] == "qualified":
            candidates.append(row)
        else:
            observations.append(row)
    for key, explicit in explicit_rows.items():
        if key in seen:
            continue
        sector = _sector(explicit)
        observations.append(
            _candidate_row(
                {},
                explicit,
                sector_statuses.get(sector, "unresolved"),
                in_workflow=False,
            )
        )
    sorter = lambda item: (_stock_key(item.get("stock")), item.get("sector", ""))
    return sorted(candidates, key=sorter), sorted(observations, key=sorter)


def _normalize_volume_fact(raw: Any, scope: str, report_date: str) -> dict:
    raw = raw if isinstance(raw, dict) else {}
    missing = _strings(raw.get("missing_fields"))
    volume_change = _enum(
        raw.get("volume_change"),
        {"expanded", "moderate", "contracted", "unknown"},
        "unknown",
    )
    disagreement = _enum(
        raw.get("disagreement_intensity"),
        {"expanded", "normal", "unknown"},
        "unknown",
    )
    if disagreement == "unknown" and volume_change == "expanded":
        disagreement = "expanded"
    elif disagreement == "unknown" and volume_change in {"moderate", "contracted"}:
        disagreement = "normal"
    price_progress = _enum(
        raw.get("price_progress"),
        {"advancing", "declining", "flat", "unknown"},
        "unknown",
    )
    close_position = _enum(
        raw.get("close_position"),
        {"strong", "middle", "weak", "unknown"},
        "unknown",
    )
    breakout_status = _enum(
        raw.get("breakout_status"),
        {"held", "failed", "not_applicable", "unknown"},
        "unknown",
    )
    pullback_volume = _enum(
        raw.get("pullback_volume"),
        {"contracted", "expanded", "not_applicable", "unknown"},
        "unknown",
    )
    cross_day_acceptance = _enum(
        raw.get("cross_day_acceptance"),
        {"confirmed", "failed", "unknown"},
        "unknown",
    )
    source_date = _source_date(raw.get("source_date"), report_date, missing, "source_date")
    next_source_date = ""
    if raw.get("next_source_date") not in (None, ""):
        next_source_date = _source_date(
            raw.get("next_source_date"),
            report_date,
            missing,
            "next_source_date",
        )
    if source_date and next_source_date and next_source_date <= source_date:
        missing.append("next_source_date")
        next_source_date = ""
    source = _text(raw.get("source"))
    if not source:
        missing.append("source")
    if disagreement == "unknown":
        missing.append("disagreement_intensity")
        acceptance = "unresolved"
    elif disagreement != "expanded":
        acceptance = "not_applicable"
    else:
        for field, value in (
            ("price_progress", price_progress),
            ("close_position", close_position),
            ("breakout_status", breakout_status),
            ("pullback_volume", pullback_volume),
            ("cross_day_acceptance", cross_day_acceptance),
        ):
            if value == "unknown":
                missing.append(field)
        if cross_day_acceptance in {"confirmed", "failed"} and not next_source_date:
            missing.append("next_source_date")
        # An expanded disagreement needs both dated sides of the price
        # observation. Without them, even a weak-looking bar is unresolved.
        if not source_date or not next_source_date:
            acceptance = "unresolved"
        else:
            rejected = (
                price_progress == "declining"
                or close_position == "weak"
                or breakout_status == "failed"
                or pullback_volume == "expanded"
                or cross_day_acceptance == "failed"
            )
            accepted = (
                price_progress == "advancing"
                and close_position == "strong"
                and breakout_status in {"held", "not_applicable"}
                and pullback_volume in {"contracted", "not_applicable"}
                and cross_day_acceptance == "confirmed"
            )
            acceptance = "rejected" if rejected else "accepted" if accepted else "unresolved"
    identity = {}
    if scope == "sector":
        identity = {"sector": _sector(raw)}
    elif scope == "stock":
        identity = {"stock": _stock(raw)}
    return {
        "scope": scope,
        **identity,
        "volume_change": volume_change,
        "disagreement_intensity": disagreement,
        "price_progress": price_progress,
        "close_position": close_position,
        "breakout_status": breakout_status,
        "pullback_volume": pullback_volume,
        "cross_day_acceptance": cross_day_acceptance,
        "price_acceptance": acceptance,
        "source_date": source_date,
        "next_source_date": next_source_date,
        "source": source,
        "missing_fields": sorted(set(missing)),
        "formal_effect": "none",
    }


def _volume_price_evidence(facts: dict, report_date: str) -> dict:
    raw = facts.get("volume_price_evidence")
    raw = raw if isinstance(raw, dict) else {}
    market = raw.get("market")
    market_row = _normalize_volume_fact(market, "market", report_date) if isinstance(market, dict) else {}
    sectors = [
        _normalize_volume_fact(item, "sector", report_date)
        for item in _list(raw.get("sectors"))
        if isinstance(item, dict)
    ]
    stocks = [
        _normalize_volume_fact(item, "stock", report_date)
        for item in _list(raw.get("stocks"))
        if isinstance(item, dict)
    ]
    return {
        "market": market_row,
        "sectors": sorted(sectors, key=lambda item: item.get("sector", "")),
        "stocks": sorted(stocks, key=lambda item: _stock_key(item.get("stock"))),
    }


def _position_leg(raw: dict, prefix: str, report_date: str, missing: list[str]) -> dict:
    nested = _optional_mapping(raw, prefix, missing)
    buy_date_value = _first_present(nested.get("buy_date"), raw.get(f"{prefix}_buy_date"))
    earliest_sell_date_value = _first_present(
        nested.get("earliest_sell_date"),
        raw.get(f"{prefix}_earliest_sell_date"),
    )
    position_value = _first_present(
        nested.get("position_pct"),
        raw.get(f"{prefix}_position_pct"),
    )
    sellable_value = _first_present(
        nested.get("sellable_pct"),
        raw.get(f"{prefix}_sellable_pct"),
    )
    buy_date = _optional_date(
        buy_date_value,
        missing,
        f"{prefix}_buy_date",
    )
    earliest_sell_date = _optional_date(
        earliest_sell_date_value,
        missing,
        f"{prefix}_earliest_sell_date",
    )
    position_pct = _percentage(position_value, missing, f"{prefix}_position_pct")
    sellable_pct = _percentage(sellable_value, missing, f"{prefix}_sellable_pct")
    leg_active = bool(
        _is_present(buy_date_value)
        or _is_present(earliest_sell_date_value)
        or (position_pct is not None and position_pct > 0)
        or (sellable_pct is not None and sellable_pct > 0)
    )
    if leg_active:
        if not buy_date:
            missing.append(f"{prefix}_buy_date")
        if not earliest_sell_date:
            missing.append(f"{prefix}_earliest_sell_date")
        if position_pct is None:
            missing.append(f"{prefix}_position_pct")
        if sellable_pct is None:
            missing.append(f"{prefix}_sellable_pct")
    if buy_date and buy_date > report_date:
        missing.append(f"{prefix}_buy_date")
        buy_date = ""
    if earliest_sell_date and buy_date and earliest_sell_date <= buy_date:
        missing.append(f"{prefix}_earliest_sell_date")
        earliest_sell_date = ""
    return {
        "buy_date": buy_date,
        "position_pct": position_pct,
        "sellable_pct": sellable_pct,
        "earliest_sell_date": earliest_sell_date,
    }


def _normalize_holding(raw: Any, report_date: str) -> dict:
    raw = raw if isinstance(raw, dict) else {}
    missing = _strings(raw.get("missing_fields"))
    stock = _stock(raw)
    if not stock:
        missing.append("stock")
    exit_confirmation = _optional_mapping(raw, "exit_confirmation", missing)
    exit_status_value = _first_present(exit_confirmation.get("status"), raw.get("exit_status"))
    exit_status = _enum(
        exit_status_value,
        {"unconfirmed", "partial", "confirmed", "unknown"},
        "unknown",
    )
    if _is_present(exit_status_value) and _text(exit_status_value).lower() not in {
        "unconfirmed",
        "partial",
        "confirmed",
        "unknown",
    }:
        missing.append("exit_confirmation_status")
    exit_position_pct = _percentage(
        _first_present(
            exit_confirmation.get("position_pct"),
            raw.get("exited_position_pct"),
        ),
        missing,
        "exit_confirmation_position_pct",
    )
    exit_date = _optional_date(
        _first_present(exit_confirmation.get("date"), raw.get("exit_date")),
        missing,
        "exit_confirmation_date",
    )
    if exit_status in {"partial", "confirmed"} and not exit_date:
        missing.append("exit_confirmation_date")
    if exit_status in {"partial", "confirmed"} and exit_position_pct is None:
        missing.append("exit_confirmation_position_pct")
    if exit_date and exit_date > report_date:
        missing.append("exit_confirmation_date")
        exit_date = ""
    planned_exit = _optional_mapping(raw, "planned_exit", missing)
    planned_exit_present = bool(planned_exit) or any(
        _is_present(raw.get(field)) for field in ("planned_exit_date", "planned_exit_reason")
    )
    planned_exit_date = _optional_date(
        _first_present(planned_exit.get("date"), raw.get("planned_exit_date")),
        missing,
        "planned_exit_date",
    )
    planned_exit_reason = _text(planned_exit.get("reason") or raw.get("planned_exit_reason"))
    if planned_exit_present and not planned_exit_date:
        missing.append("planned_exit_date")
    if planned_exit_present and not planned_exit_reason:
        missing.append("planned_exit_reason")
    b1 = _position_leg(raw, "b1", report_date, missing)
    b2 = _position_leg(raw, "b2", report_date, missing)
    if b1.get("buy_date") and b2.get("buy_date") and b2["buy_date"] <= b1["buy_date"]:
        missing.append("b2_buy_date")
        b2["buy_date"] = ""
        b2["earliest_sell_date"] = ""
        missing.append("b2_earliest_sell_date")
    return {
        "stock": stock,
        "b1": b1,
        "b2": b2,
        "planned_exit": {
            "date": planned_exit_date,
            "reason": planned_exit_reason,
        },
        "exit_confirmation": {
            "status": exit_status,
            "date": exit_date,
            "position_pct": exit_position_pct,
        },
        "funds_released": raw.get("funds_released")
        if isinstance(raw.get("funds_released"), bool)
        else None,
        "source_date": _source_date(raw.get("source_date"), report_date, missing, "source_date"),
        "source": _text(raw.get("source")),
        "missing_fields": sorted(set(missing)),
    }


def _fallback_holding(data: dict, report_date: str) -> list[dict]:
    resolution = data.get("final_target_resolution")
    resolution = resolution if isinstance(resolution, dict) else {}
    existing = resolution.get("existing_position_target")
    existing = existing if isinstance(existing, dict) else {}
    if not _stock(existing):
        return []
    old_plan = resolution.get("old_position_plan")
    old_plan = old_plan if isinstance(old_plan, dict) else {}
    holding = old_plan.get("holding") if isinstance(old_plan.get("holding"), dict) else {}
    return [
        _normalize_holding(
            {
                **existing,
                "b1_position_pct": _first_present(
                    holding.get("position_pct"),
                    existing.get("position_pct"),
                ),
                "planned_exit": old_plan.get("planned_exit"),
                "source_date": existing.get("source_date") or old_plan.get("source_date"),
                "source": "final_target_resolution.existing_position_target",
            },
            report_date,
        )
    ]


def _holdings(data: dict, facts: dict, report_date: str) -> tuple[list[dict], list[str]]:
    missing = []
    facts_has_holdings = "holdings" in facts
    facts_holdings_valid = isinstance(facts.get("holdings"), (list, tuple))
    lifecycle_present = "position_lifecycle_records" in data
    lifecycle_rows_valid = isinstance(data.get("position_lifecycle_records"), (list, tuple))
    source_known = False
    if facts_has_holdings and facts_holdings_valid:
        raw_rows = _list(facts.get("holdings"))
        source_known = True
    elif lifecycle_present and lifecycle_rows_valid:
        raw_rows = _list(data.get("position_lifecycle_records"))
        source_known = True
    else:
        raw_rows = []
    if facts_has_holdings and not facts_holdings_valid:
        missing.append("holdings")
    if lifecycle_present and not lifecycle_rows_valid and not facts_holdings_valid:
        missing.append("holdings")
    if any(not isinstance(item, dict) for item in raw_rows):
        missing.append("holdings")
    rows = [_normalize_holding(item, report_date) for item in raw_rows if isinstance(item, dict)]
    if not rows and not source_known:
        fallback = _fallback_holding(data, report_date)
        rows = fallback
        if not rows and not facts_has_holdings and not lifecycle_present:
            missing.append("holdings")
    for row in rows:
        for field in row.get("missing_fields", []):
            missing.append(f"holding:{_stock_key(row.get('stock')) or 'unknown'}:{field}")
    unfinished = [
        row
        for row in rows
        if not (
            row.get("exit_confirmation", {}).get("status") == "confirmed"
            and row.get("funds_released") is True
            and bool(row.get("exit_confirmation", {}).get("date"))
            and row.get("exit_confirmation", {}).get("date") <= report_date
        )
    ]
    return (
        sorted(
            unfinished,
            key=lambda item: (
                _stock_key(item.get("stock")),
                item.get("b1", {}).get("buy_date", ""),
            ),
        ),
        sorted(set(missing)),
    )


def _capital_option(raw: Any, name: str) -> dict:
    raw = raw if isinstance(raw, dict) else {"status": raw}
    return {
        "name": name,
        "status": _qualification(raw),
        "stock": _stock(raw),
        "evidence": _strings(raw.get("evidence")),
        "missing_fields": _strings(raw.get("missing_fields")),
        "reason_codes": _strings(raw.get("reason_codes")),
    }


def _capital_options(
    facts: dict,
    holdings: list[dict],
    volume_price: dict,
    comparison: dict,
) -> dict:
    supplied = facts.get("capital_qualifications")
    supplied = supplied if isinstance(supplied, dict) else {}
    options = {
        name: _capital_option(supplied.get(name), name)
        for name in ("hold", "add", "replace", "cash")
    }
    add = options["add"]
    add_stock = add.get("stock")
    if not add_stock and add["status"] == "qualified":
        if len(holdings) == 1:
            add_stock = deepcopy(holdings[0].get("stock") or {})
            add["stock"] = add_stock
        elif len(holdings) > 1:
            add["status"] = "unresolved"
            add["missing_fields"] = sorted(set([*add["missing_fields"], "add_stock"]))
        else:
            add["status"] = "unresolved"
            add["missing_fields"] = sorted(set([*add["missing_fields"], "add_stock"]))
    stock_fact = next(
        (
            item
            for item in volume_price.get("stocks", [])
            if _stock_key(item.get("stock")) == _stock_key(add_stock)
        ),
        {},
    )
    if add["status"] == "qualified":
        if not stock_fact:
            add["status"] = "unresolved"
            add["missing_fields"] = sorted(set([*add["missing_fields"], "stock_volume_price_evidence"]))
        elif stock_fact.get("disagreement_intensity") == "expanded" and stock_fact.get(
            "price_acceptance"
        ) != "accepted":
            add["status"] = "not_qualified"
            add["reason_codes"] = sorted(
                set([*add["reason_codes"], "expanded_disagreement_not_accepted"])
            )
    replace = options["replace"]
    if replace["status"] == "qualified":
        winner = _stock(comparison.get("winner"))
        comparison_status = _text(comparison.get("status"))
        if comparison_status not in {"clear_winner", "single_qualified"}:
            replace["status"] = "not_qualified" if comparison_status == "tie_unresolved" else "unresolved"
            replace["reason_codes"] = sorted(
                set([*replace["reason_codes"], "comparison_winner_unresolved"])
            )
        elif not winner or not replace.get("stock") or _stock_key(winner) != _stock_key(replace.get("stock")):
            replace["status"] = "not_qualified"
            replace["reason_codes"] = sorted(
                set([*replace["reason_codes"], "replacement_not_comparison_winner"])
            )
    cash_was_supplied = "cash" in supplied
    if not cash_was_supplied:
        if (
            options["add"]["status"] == "qualified"
            and options["replace"]["status"] == "qualified"
        ):
            options["cash"]["status"] = "qualified"
        elif options["add"]["status"] == "qualified" or options["replace"]["status"] == "qualified":
            options["cash"]["status"] = "not_qualified"
        elif (
            options["add"]["status"] == "not_qualified"
            and options["replace"]["status"] == "not_qualified"
            and options["hold"]["status"] in {"qualified", "not_qualified"}
        ):
            options["cash"]["status"] = "qualified"
        else:
            options["cash"]["status"] = "unresolved"
    if (
        options["replace"]["status"] == "qualified"
        and options["add"]["status"] == "qualified"
    ):
        interpretation = "add_replace_conflict_unresolved"
    elif options["replace"]["status"] == "qualified":
        interpretation = "replace_with_new_b1"
    elif options["add"]["status"] == "qualified":
        interpretation = "old_object_add_evidence_present"
    elif (
        options["hold"]["status"] == "qualified"
        and options["add"]["status"] == "not_qualified"
        and options["replace"]["status"] == "not_qualified"
    ):
        interpretation = "hold_b1_keep_cash"
    elif (
        options["hold"]["status"] == "not_qualified"
        and options["replace"]["status"] == "not_qualified"
    ):
        interpretation = "cash_only_after_independent_hold_review"
    else:
        interpretation = "unresolved"
    return {**options, "read_only_interpretation": interpretation, "formal_effect": "none"}


def _comparison(candidates: list[dict], workflow: dict) -> dict:
    fully_comparable = [
        item
        for item in candidates
        if all(item.get("comparison_fields", {}).get(field) == "qualified" for field in COMPARISON_FIELDS)
    ]
    explicit_winners = [item for item in fully_comparable if item.get("clear_advantage")]
    winner = {}
    if len(explicit_winners) == 1:
        status = "clear_winner"
        winner = explicit_winners[0].get("stock") or {}
    elif len(candidates) == 1 and len(fully_comparable) == 1:
        status = "single_qualified"
        winner = fully_comparable[0].get("stock") or {}
    elif len(fully_comparable) >= 2 and len(
        {stable_json_hash(item.get("comparison_fields")) for item in fully_comparable}
    ) == 1:
        status = "tie_unresolved"
    elif candidates:
        status = "unresolved"
    else:
        status = "no_qualified_candidate"
    final = workflow.get("final") if isinstance(workflow.get("final"), dict) else {}
    return {
        "status": status,
        "winner": _stock(winner),
        "required_fields": list(COMPARISON_FIELDS),
        "fully_comparable": [_stock(item.get("stock")) for item in fully_comparable],
        "tied_candidates": (
            [_stock(item.get("stock")) for item in fully_comparable]
            if status == "tie_unresolved"
            else []
        ),
        "formal_execution_object": _stock(final.get("execution_object")),
        "formal_effect": "none",
    }


def canonical_candidate_decision_evidence_hash(payload: Any) -> str:
    return stable_json_hash(
        payload if isinstance(payload, dict) else {},
        excluded_keys={"artifact_hash"},
    )


def candidate_decision_evidence_cache_key(report_date: Any, *, analysis_mode: str) -> tuple[str, str, str]:
    mode = "replay" if analysis_mode == "replay" else "fresh"
    return ("candidate_decision_evidence", _date(report_date), mode)


def canonical_sector_diffusion_stage_evidence_hash(payload: Any) -> str:
    return stable_json_hash(
        payload if isinstance(payload, dict) else {},
        excluded_keys={"artifact_hash"},
    )


def canonical_sector_tournament_three_axis_hash(payload: Any) -> str:
    return stable_json_hash(
        payload if isinstance(payload, dict) else {},
        excluded_keys={"artifact_hash"},
    )


def _explicit_bool_value(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    text = _text(value).lower()
    if text in {"1", "true", "yes", "confirmed", "是", "已确认"}:
        return True
    if text in {"0", "false", "no", "failed", "否", "失败"}:
        return False
    return None


def _valid_sector_stage_input(value: Any, target_date: str) -> dict:
    stage = deepcopy(value) if isinstance(value, dict) else {}
    input_payload = stage.get("input_payload") or {}
    input_proof = (
        input_payload.get("local_trend_sector_proof")
        if isinstance(input_payload, dict)
        and isinstance(input_payload.get("local_trend_sector_proof"), dict)
        else {}
    )
    direction_source_date = _date(stage.get("direction_source_date"))
    if (
        stage.get("schema_version") != SECTOR_DIFFUSION_STAGE_SCHEMA_VERSION
        or stage.get("decision_scope") != DECISION_SCOPE
        or stage.get("formal_effect") != "none"
        or _date(stage.get("target_date")) != target_date
        or stable_json_hash(stage.get("input_payload") or {}) != stage.get("input_hash")
        or canonical_sector_diffusion_stage_evidence_hash(stage) != stage.get("artifact_hash")
        or _text(stage.get("direction")) != _text(input_proof.get("direction"))
        or direction_source_date != _date(input_proof.get("direction_source_date"))
        or (_text(stage.get("direction")) and not direction_source_date)
        or (direction_source_date and direction_source_date > target_date)
    ):
        return {}
    source_dates = [_date(item) for item in _list(stage.get("source_dates"))]
    if any(not item or item > target_date for item in source_dates):
        return {}
    return stage


def _bounded_dates(value: Any, target_date: str) -> list[str]:
    return sorted(
        {
            item
            for item in (_date(raw) for raw in _list(value))
            if item and item <= target_date
        }
    )


def _nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _exact_nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    number = _float(value)
    if number is None or number < 0 or not number.is_integer():
        return None
    return int(number)


def _stage_field_source_date(raw: dict, field: str, target_date: str) -> str:
    field_dates = raw.get("field_source_dates")
    field_dates = field_dates if isinstance(field_dates, dict) else {}
    source_date = _date(
        field_dates.get(field)
        or raw.get(f"{field}_source_date")
        or raw.get("source_date")
    )
    return source_date if source_date and source_date <= target_date else ""


def _source_dated_rows(value: Any, target_date: str, fallback_date: str) -> list[dict]:
    prepared = []
    for item in _list(value):
        if isinstance(item, dict):
            prepared.append(item)
        elif _text(item) and fallback_date:
            prepared.append({"text": _text(item), "source_date": fallback_date})
    return _dated_as_of_evidence_rows(prepared, target_date)


def _normalize_stage_index_path(
    value: Any,
    target_date: str,
) -> tuple[list[dict], list[str]]:
    by_date: dict[str, dict] = {}
    errors = []
    for item in _list(value):
        if not isinstance(item, dict):
            continue
        trade_date = _date(
            item.get("trade_date") or item.get("date") or item.get("source_date")
        )
        source_date = _date(item.get("source_date") or trade_date)
        if (
            not trade_date
            or trade_date > target_date
            or not source_date
            or source_date > target_date
        ):
            continue
        index_value = _float(
            _first_present(
                item.get("index_value"),
                item.get("close"),
                item.get("value"),
            )
        )
        if index_value is None or not math.isfinite(index_value) or index_value <= 0:
            errors.append(f"sector_index_path.{trade_date}")
            continue
        row = {
            "trade_date": trade_date,
            "index_value": index_value,
            "relative_strength_rank": _nonnegative_int(
                item.get("relative_strength_rank")
            ),
            "source_date": source_date,
        }
        if row["relative_strength_rank"] == 0:
            row["relative_strength_rank"] = None
        previous = by_date.get(trade_date)
        if previous and previous != row:
            errors.append(f"sector_index_path.duplicate.{trade_date}")
            continue
        by_date[trade_date] = row
    return [by_date[key] for key in sorted(by_date)], sorted(set(errors))


def _relative_path_profile(
    sector_index_path: list[dict],
    window_dates: list[str],
) -> dict:
    missing = {
        "evidence_status": "事实不足",
        "position_label": "事实不足",
        "start_value": None,
        "end_value": None,
        "low_value": None,
        "low_date": "",
        "interval_return_pct": None,
        "low_vs_start_pct": None,
        "recovery_from_low_pct": None,
        "recovered_start": None,
        "made_window_new_high": None,
        "source_dates": [],
        "formal_effect": "none",
    }
    if len(window_dates) < 2:
        return missing
    path_by_date = {row.get("trade_date"): row for row in sector_index_path}
    if any(date not in path_by_date for date in window_dates):
        return missing
    rows = [path_by_date[date] for date in window_dates]
    values = [row.get("index_value") for row in rows]
    if any(not isinstance(value, (int, float)) or value <= 0 for value in values):
        return missing

    start_value = float(values[0])
    end_value = float(values[-1])
    low_index = min(range(len(values)), key=values.__getitem__)
    low_value = float(values[low_index])
    interval_return_pct = round((end_value / start_value - 1.0) * 100.0, 8)
    low_vs_start_pct = round((low_value / start_value - 1.0) * 100.0, 8)
    recovery_from_low_pct = (
        round((end_value - low_value) / (start_value - low_value) * 100.0, 8)
        if low_value < start_value
        else None
    )
    recovered_start = end_value >= start_value
    made_window_new_high = end_value > max(float(value) for value in values[:-1])
    if made_window_new_high:
        position_label = "区间突破"
    elif recovered_start:
        position_label = "收复起点"
    elif end_value > low_value:
        position_label = "低点修复未收复"
    else:
        position_label = "仍在低位"
    return {
        "evidence_status": "完整",
        "position_label": position_label,
        "start_value": start_value,
        "end_value": end_value,
        "low_value": low_value,
        "low_date": rows[low_index]["trade_date"],
        "interval_return_pct": interval_return_pct,
        "low_vs_start_pct": low_vs_start_pct,
        "recovery_from_low_pct": recovery_from_low_pct,
        "recovered_start": recovered_start,
        "made_window_new_high": made_window_new_high,
        "source_dates": sorted({row.get("source_date") for row in rows if row.get("source_date")}),
        "formal_effect": "none",
    }


def _normalize_comparison_universe(
    value: Any,
    target_date: str,
) -> tuple[list[dict], list[str]]:
    by_direction: dict[str, dict] = {}
    errors = []
    for item in _list(value):
        if not isinstance(item, dict):
            continue
        direction = _text(
            item.get("direction") or item.get("sector") or item.get("name")
        )
        source_date = _date(
            item.get("source_date") or item.get("trade_date") or item.get("date")
        )
        if source_date and source_date > target_date:
            continue
        if not direction:
            continue
        row = {
            "direction": direction,
            "metric_value": _float(
                _first_present(item.get("metric_value"), item.get("value"))
            ),
            "source_date": source_date,
        }
        previous = by_direction.get(direction)
        if previous and previous != row:
            errors.append(f"comparison_universe.duplicate.{direction}")
            continue
        by_direction[direction] = row
    return [by_direction[key] for key in sorted(by_direction)], sorted(set(errors))


def _normalize_comparison_universe_scope(
    value: Any,
    target_date: str,
) -> tuple[dict, list[str]]:
    raw = value if isinstance(value, dict) else {}
    source_date = _date(raw.get("source_date"))
    if not source_date or source_date > target_date:
        return {"directions": [], "source_date": ""}, [
            "comparison_universe_scope.source_date"
        ]

    directions = []
    errors = []
    seen = set()
    for item in _list(raw.get("directions")):
        direction = _text(item)
        if not direction:
            continue
        if direction in seen:
            errors.append(f"comparison_universe_scope.duplicate.{direction}")
            continue
        seen.add(direction)
        directions.append(direction)
    if len(directions) < 2:
        errors.append("comparison_universe_scope.directions")
    return {
        "directions": sorted(directions),
        "source_date": source_date,
    }, sorted(set(errors))


def _normalize_stage_repair_evidence(
    value: Any,
    *,
    target_date: str,
    divergence_date: str,
    repair_date: str,
    sector_index_path: list[dict],
    active_trade_dates: list[str],
) -> tuple[list[dict], bool, list[str]]:
    if not divergence_date or not repair_date:
        return [], False, []

    path_by_date = {row.get("trade_date"): row for row in sector_index_path}
    divergence_path = path_by_date.get(divergence_date) or {}
    repair_path = path_by_date.get(repair_date) or {}
    normalized_by_kind = {}
    errors = []

    for item in _list(value):
        if not isinstance(item, dict):
            continue
        kind = _text(item.get("kind")).lower()
        source_date = _date(item.get("source_date"))
        if not kind or source_date != repair_date or source_date > target_date:
            if kind:
                errors.append(f"repair_evidence.{kind}.source_date")
            continue
        if kind in normalized_by_kind:
            errors.append(f"repair_evidence.duplicate.{kind}")
            continue

        if kind == "sector_index_repair":
            divergence_value = _float(item.get("divergence_index_value"))
            repair_value = _float(item.get("repair_index_value"))
            if not (
                divergence_value is not None
                and repair_value is not None
                and divergence_path.get("index_value") is not None
                and repair_path.get("index_value") is not None
                and abs(divergence_value - divergence_path["index_value"]) <= 1e-6
                and abs(repair_value - repair_path["index_value"]) <= 1e-6
                and repair_value >= divergence_value
                and repair_path.get("relative_strength_rank") == 1
            ):
                errors.append("repair_evidence.sector_index_repair")
                continue
            normalized_by_kind[kind] = {
                "kind": kind,
                "divergence_index_value": divergence_value,
                "repair_index_value": repair_value,
                "source_date": source_date,
            }
            continue

        if kind == "capital_return":
            trade_date = _date(item.get("trade_date"))
            if not (
                trade_date == repair_date
                and repair_date in active_trade_dates
                and any(date <= divergence_date for date in active_trade_dates)
            ):
                errors.append("repair_evidence.capital_return")
                continue
            normalized_by_kind[kind] = {
                "kind": kind,
                "trade_date": trade_date,
                "source_date": source_date,
            }
            continue

        if kind == "internal_trend_density":
            row_trend_count = _nonnegative_int(item.get("trend_stock_count"))
            row_comparable_count = _nonnegative_int(
                item.get("comparable_stock_count")
            )
            row_definition_version = _text(item.get("trend_definition_version"))
            if not (
                row_trend_count is not None
                and row_trend_count >= 2
                and row_comparable_count is not None
                and row_comparable_count >= row_trend_count
                and row_definition_version
            ):
                errors.append("repair_evidence.internal_trend_density")
                continue
            normalized_by_kind[kind] = {
                "kind": kind,
                "trend_stock_count": row_trend_count,
                "comparable_stock_count": row_comparable_count,
                "trend_density": round(
                    row_trend_count / row_comparable_count,
                    8,
                ),
                "trend_definition_version": row_definition_version,
                "source_date": source_date,
            }
            continue

        errors.append(f"repair_evidence.kind.{kind}")

    required_kinds = {
        "sector_index_repair",
        "capital_return",
        "internal_trend_density",
    }
    complete = set(normalized_by_kind) == required_kinds and not errors
    return (
        [normalized_by_kind[key] for key in sorted(normalized_by_kind)],
        complete,
        sorted(set(errors)),
    )


def _stage_mainline_prior_status(value: Any) -> str:
    text = _text(value).lower()
    mapping = {
        "confirmed": STAGE_MAINLINE_STATUS_CONFIRMED,
        "阶段主线已确认": STAGE_MAINLINE_STATUS_CONFIRMED,
        "weakened": STAGE_MAINLINE_STATUS_WEAKENED,
        "阶段主线弱化": STAGE_MAINLINE_STATUS_WEAKENED,
        "invalidated": STAGE_MAINLINE_STATUS_INVALIDATED,
        "阶段主线失效": STAGE_MAINLINE_STATUS_INVALIDATED,
        "candidate": STAGE_MAINLINE_STATUS_CANDIDATE,
        "阶段主线候选": STAGE_MAINLINE_STATUS_CANDIDATE,
    }
    return mapping.get(text, STAGE_MAINLINE_STATUS_INSUFFICIENT)


def _normalize_stage_mainline_record(
    value: Any,
    *,
    target_date: str,
    fallback_direction: str = "",
) -> dict:
    raw = deepcopy(value) if isinstance(value, dict) else {}
    raw_source_date = _date(raw.get("source_date"))
    if raw_source_date and raw_source_date > target_date:
        return {}

    direction = _text(raw.get("direction") or fallback_direction)
    stage_start_date = _date(raw.get("stage_start_date"))
    if stage_start_date > target_date:
        stage_start_date = ""
    trading_calendar = _bounded_dates(raw.get("trading_calendar"), target_date)
    stage_calendar = [
        item
        for item in trading_calendar
        if stage_start_date and stage_start_date <= item <= target_date
    ]
    stage_span_trading_days = len(stage_calendar)

    raw_active_dates = _bounded_dates(raw.get("active_trade_dates"), target_date)
    active_trade_dates = [
        item
        for item in raw_active_dates
        if not stage_calendar or item in stage_calendar
    ]
    active_trade_day_count = len(active_trade_dates)
    calendar_positions = {date: index for index, date in enumerate(stage_calendar)}
    reflow_dates = []
    reflow_cooling_evidence = []
    for previous_date, current_date in zip(active_trade_dates, active_trade_dates[1:]):
        previous_index = calendar_positions.get(previous_date)
        current_index = calendar_positions.get(current_date)
        if (
            previous_index is None
            or current_index is None
            or current_index - previous_index < 2
        ):
            continue
        cooling_dates = stage_calendar[previous_index + 1 : current_index]
        reflow_dates.append(current_date)
        reflow_cooling_evidence.append(
            {
                "previous_active_date": previous_date,
                "reflow_date": current_date,
                "cooling_trade_dates": cooling_dates,
                "source_date": _stage_field_source_date(
                    raw,
                    "active_trade_dates",
                    target_date,
                ),
            }
        )

    sector_index_path, path_errors = _normalize_stage_index_path(
        raw.get("sector_index_path"),
        target_date,
    )
    metric_raw = raw.get("relative_strength_metric")
    metric_name = _text(
        metric_raw.get("name") if isinstance(metric_raw, dict) else metric_raw
    ).lower()
    if metric_name not in {"window_return_pct"}:
        metric_name = ""
    window_raw = raw.get("relative_strength_window")
    window_raw = window_raw if isinstance(window_raw, dict) else {}
    window_dates = _bounded_dates(window_raw.get("trade_dates"), target_date)
    window_start_date = _date(window_raw.get("start_date"))
    window_end_date = _date(window_raw.get("end_date"))
    if window_start_date > target_date:
        window_start_date = ""
    if window_end_date > target_date:
        window_end_date = ""
    if window_dates:
        window_start_date = window_start_date or window_dates[0]
        window_end_date = window_end_date or window_dates[-1]
    relative_strength_window = {
        "start_date": window_start_date,
        "end_date": window_end_date,
        "trade_dates": window_dates,
    }
    relative_path_profile = _relative_path_profile(
        sector_index_path if not path_errors else [],
        window_dates,
    )
    path_by_date = {row["trade_date"]: row for row in sector_index_path}
    path_complete = bool(
        len(window_dates) >= STAGE_MAINLINE_MIN_TRADING_DAYS
        and window_dates == stage_calendar
        and all(date in path_by_date for date in window_dates)
        and all(
            isinstance(path_by_date[date].get("relative_strength_rank"), int)
            for date in window_dates
        )
    )
    path_relative_strength_leading = bool(
        path_complete
        and all(
            path_by_date[date].get("relative_strength_rank") == 1
            for date in window_dates
        )
    )
    metric_value = None
    if metric_name == "window_return_pct" and path_complete:
        first_value = path_by_date[window_dates[0]]["index_value"]
        last_value = path_by_date[window_dates[-1]]["index_value"]
        metric_value = round((last_value / first_value - 1.0) * 100.0, 8)
    relative_strength_metric = {
        "name": metric_name,
        "value": metric_value,
    }

    comparison_scope, comparison_scope_errors = (
        _normalize_comparison_universe_scope(
            raw.get("comparison_universe_scope"),
            target_date,
        )
    )
    normalized_comparisons, comparison_errors = _normalize_comparison_universe(
        raw.get("comparison_universe"),
        target_date,
    )
    comparison_by_direction = {
        row["direction"]: row for row in normalized_comparisons
    }
    scope_directions = comparison_scope["directions"]
    comparison_universe = [
        deepcopy(
            comparison_by_direction.get(direction)
            or {
                "direction": direction,
                "metric_value": None,
                "source_date": "",
            }
        )
        for direction in scope_directions
    ]
    if set(comparison_by_direction) - set(scope_directions):
        comparison_errors.append("comparison_universe.outside_scope")
    valid_comparisons = [
        row
        for row in comparison_universe
        if row.get("metric_value") is not None and row.get("source_date")
    ]
    comparison_coverage = (
        round(len(valid_comparisons) / len(scope_directions), 8)
        if scope_directions
        else None
    )
    own_comparison = next(
        (row for row in valid_comparisons if row.get("direction") == direction),
        None,
    )
    relative_strength_rank = None
    if own_comparison:
        own_value = own_comparison["metric_value"]
        relative_strength_rank = 1 + sum(
            1
            for row in valid_comparisons
            if row.get("metric_value") is not None
            and row["metric_value"] > own_value
        )
    comparison_source_dates = {
        row.get("source_date") for row in valid_comparisons if row.get("source_date")
    }
    comparison_complete = bool(
        len(scope_directions) >= 2
        and set(comparison_by_direction) == set(scope_directions)
        and comparison_scope.get("source_date") == target_date
        and comparison_coverage == 1.0
        and comparison_source_dates == {target_date}
        and relative_strength_rank == 1
        and path_relative_strength_leading
        and metric_value is not None
        and own_comparison
        and abs(own_comparison["metric_value"] - metric_value) <= 1e-6
    )

    trend_stock_count = _nonnegative_int(raw.get("trend_stock_count"))
    comparable_stock_count = _nonnegative_int(raw.get("comparable_stock_count"))
    trend_definition_version = _text(raw.get("trend_definition_version"))
    trend_density = (
        round(trend_stock_count / comparable_stock_count, 8)
        if trend_stock_count is not None
        and comparable_stock_count
        and trend_stock_count <= comparable_stock_count
        else None
    )
    internal_density_complete = bool(
        trend_stock_count is not None
        and trend_stock_count >= 2
        and comparable_stock_count is not None
        and comparable_stock_count >= trend_stock_count
        and trend_definition_version
    )

    divergence_source_date = _stage_field_source_date(
        raw,
        "divergence_date",
        target_date,
    )
    divergence_date = _date(raw.get("divergence_date"))
    if (
        not divergence_source_date
        or not divergence_date
        or divergence_date > target_date
    ):
        divergence_date = ""
    repair_source_date = _stage_field_source_date(raw, "repair_date", target_date)
    repair_date = _date(raw.get("repair_date"))
    if not repair_source_date or not repair_date or repair_date > target_date:
        repair_date = ""
    repair_failed = _explicit_bool_value(raw.get("repair_failed")) is True or _text(
        raw.get("repair_status")
    ).lower() == "failed"
    repair_evidence, repair_evidence_complete, repair_errors = (
        _normalize_stage_repair_evidence(
            raw.get("repair_evidence"),
            target_date=target_date,
            divergence_date=divergence_date,
            repair_date=repair_date,
            sector_index_path=sector_index_path,
            active_trade_dates=active_trade_dates,
        )
    )
    if not divergence_date:
        divergence_test_status = "未经分歧检验"
        repair_date = ""
        repair_evidence = []
        repair_errors = []
    elif repair_failed:
        divergence_test_status = "分歧修复失败"
    elif (
        repair_date
        and divergence_date <= repair_date <= target_date
        and repair_evidence_complete
    ):
        divergence_test_status = "分歧已修复"
    else:
        divergence_test_status = "分歧尚未修复"

    evidence_source_date = _date(raw.get("source_date"))
    if evidence_source_date > target_date:
        evidence_source_date = ""
    weakening_evidence = _source_dated_rows(
        raw.get("weakening_evidence"),
        target_date,
        evidence_source_date,
    )
    invalidation_evidence = _source_dated_rows(
        raw.get("invalidation_evidence"),
        target_date,
        evidence_source_date,
    )

    tracked_fields = (
        "stage_start_date",
        "trading_calendar",
        "active_trade_dates",
        "sector_index_path",
        "relative_strength_metric",
        "relative_strength_window",
        "comparison_universe_scope",
        "comparison_universe",
        "trend_stock_count",
        "comparable_stock_count",
        "trend_definition_version",
    )
    field_source_dates = {
        field: source_date
        for field in tracked_fields
        if (source_date := _stage_field_source_date(raw, field, target_date))
    }
    field_source_dates.pop("comparison_universe_scope", None)
    if comparison_scope.get("source_date"):
        field_source_dates["comparison_universe_scope"] = comparison_scope[
            "source_date"
        ]
    if divergence_date:
        field_source_dates["divergence_date"] = divergence_source_date
    if repair_date:
        field_source_dates["repair_date"] = repair_source_date

    missing_fields = []
    if not direction:
        missing_fields.append("direction")
    if not stage_start_date or stage_start_date not in trading_calendar:
        missing_fields.append("stage_start_date")
    if stage_span_trading_days < STAGE_MAINLINE_MIN_TRADING_DAYS:
        missing_fields.append("stage_span_trading_days")
    if active_trade_day_count < 2:
        missing_fields.append("active_trade_dates")
    if not reflow_dates:
        missing_fields.append("reflow_dates")
    if not path_complete or path_errors:
        missing_fields.append("sector_index_path")
    if not metric_name or metric_value is None:
        missing_fields.append("relative_strength_metric")
    if (
        not comparison_complete
        or comparison_errors
        or comparison_scope_errors
    ):
        missing_fields.append("relative_strength_comparison")
    if not internal_density_complete:
        missing_fields.append("internal_trend_density")
    if divergence_test_status in {"分歧尚未修复", "分歧修复失败"}:
        missing_fields.append("divergence_repair")
    if any(field_source_dates.get(field) != target_date for field in tracked_fields):
        missing_fields.append("field_source_dates")
    if any(item not in stage_calendar for item in raw_active_dates):
        missing_fields.append("active_trade_dates_outside_calendar")

    recognition_date = _date(raw.get("recognition_date"))
    last_confirmed_date = _date(raw.get("last_confirmed_date"))
    if recognition_date > target_date:
        recognition_date = ""
    if last_confirmed_date > target_date:
        last_confirmed_date = ""
    first_eligible_confirmation_date = (
        stage_calendar[STAGE_MAINLINE_MIN_TRADING_DAYS - 1]
        if len(stage_calendar) >= STAGE_MAINLINE_MIN_TRADING_DAYS
        else ""
    )
    date_history_valid = bool(
        (not recognition_date and not last_confirmed_date)
        or (
            stage_start_date
            and first_eligible_confirmation_date
            and recognition_date
            and last_confirmed_date
            and recognition_date in stage_calendar
            and last_confirmed_date in stage_calendar
            and stage_start_date
            <= recognition_date
            and first_eligible_confirmation_date <= recognition_date
            <= last_confirmed_date
            <= target_date
        )
    )
    if not date_history_valid:
        missing_fields.append("stage_date_invariant")
        recognition_date = ""
        last_confirmed_date = ""

    prior_status = _stage_mainline_prior_status(
        raw.get("prior_status") or raw.get("status")
    )
    prior_confirmed_history = bool(
        recognition_date and last_confirmed_date and date_history_valid
    )
    current_evidence_complete = bool(
        not missing_fields
        and divergence_test_status in {"未经分歧检验", "分歧已修复"}
        and not weakening_evidence
        and not invalidation_evidence
    )

    if prior_status in {
        STAGE_MAINLINE_STATUS_WEAKENED,
        STAGE_MAINLINE_STATUS_INVALIDATED,
    } and prior_confirmed_history:
        status = prior_status
    elif invalidation_evidence or divergence_test_status == "分歧修复失败":
        status = (
            STAGE_MAINLINE_STATUS_INVALIDATED
            if prior_confirmed_history
            else STAGE_MAINLINE_STATUS_CANDIDATE
        )
    elif current_evidence_complete:
        status = STAGE_MAINLINE_STATUS_CONFIRMED
        if not recognition_date:
            recognition_date = target_date
        last_confirmed_date = target_date
    elif prior_confirmed_history:
        status = STAGE_MAINLINE_STATUS_WEAKENED
    elif direction and stage_start_date:
        status = STAGE_MAINLINE_STATUS_CANDIDATE
        recognition_date = ""
        last_confirmed_date = ""
    else:
        status = STAGE_MAINLINE_STATUS_INSUFFICIENT
        recognition_date = ""
        last_confirmed_date = ""

    if status == STAGE_MAINLINE_STATUS_CONFIRMED and not (
        stage_start_date
        <= recognition_date
        <= last_confirmed_date
        <= target_date
    ):
        status = STAGE_MAINLINE_STATUS_INSUFFICIENT
        recognition_date = ""
        last_confirmed_date = ""
        missing_fields.append("stage_date_invariant")

    source_dates = sorted(
        {
            date
            for date in (
                *field_source_dates.values(),
                *(row.get("source_date") for row in sector_index_path),
                *(row.get("source_date") for row in comparison_universe),
                *(row.get("source_date") for row in repair_evidence),
                *(row.get("source_date") for row in weakening_evidence),
                *(row.get("source_date") for row in invalidation_evidence),
            )
            if date and date <= target_date
        }
    )
    return {
        "direction": direction,
        "status": status,
        "evidence_sufficiency": (
            "完整"
            if current_evidence_complete
            else "部分"
            if direction and stage_start_date
            else "事实不足"
        ),
        "stage_start_date": stage_start_date,
        "recognition_date": recognition_date,
        "last_confirmed_date": last_confirmed_date,
        "as_of_date": target_date,
        "stage_span_trading_days": stage_span_trading_days,
        "trading_calendar": trading_calendar,
        "active_trade_dates": active_trade_dates,
        "reflow_dates": reflow_dates,
        "reflow_cooling_evidence": reflow_cooling_evidence,
        "active_trade_day_count": active_trade_day_count,
        "sector_index_path": sector_index_path,
        "relative_path_profile": relative_path_profile,
        "relative_strength_metric": relative_strength_metric,
        "relative_strength_window": relative_strength_window,
        "comparison_universe_scope": comparison_scope,
        "comparison_universe": comparison_universe,
        "comparison_coverage": comparison_coverage,
        "relative_strength_rank": relative_strength_rank,
        "trend_stock_count": trend_stock_count,
        "comparable_stock_count": comparable_stock_count,
        "trend_density": trend_density,
        "trend_definition_version": trend_definition_version,
        "divergence_test_status": divergence_test_status,
        "divergence_date": divergence_date,
        "repair_date": repair_date,
        "repair_evidence": repair_evidence,
        "source_dates": source_dates,
        "field_source_dates": field_source_dates,
        "weakening_evidence": weakening_evidence,
        "invalidation_evidence": invalidation_evidence,
        "missing_fields": sorted(
            set(
                missing_fields
                + path_errors
                + comparison_errors
                + comparison_scope_errors
                + repair_errors
            )
        ),
    }


def _stage_mainline_record_evidence(record: dict) -> list[str]:
    if not record:
        return ["事实不足"]
    parts = [
        f"方向={record.get('direction') or '待确认'}",
        f"状态={record.get('status') or '事实不足'}",
        f"阶段跨度={record.get('stage_span_trading_days') or 0}个交易日",
        f"活跃交易日={record.get('active_trade_day_count') or 0}日",
        "冷却后回流=" + (" -> ".join(record.get("reflow_dates") or []) or "事实不足"),
        (
            f"相对强度名次={record.get('relative_strength_rank')}/"
            f"{len((record.get('comparison_universe_scope') or {}).get('directions') or [])}"
            if record.get("relative_strength_rank") is not None
            else "相对强度名次=事实不足"
        ),
        (
            f"趋势股密度={record.get('trend_stock_count')}/"
            f"{record.get('comparable_stock_count')}"
            if record.get("trend_stock_count") is not None
            and record.get("comparable_stock_count") is not None
            else "趋势股密度=事实不足"
        ),
        f"分歧检验={record.get('divergence_test_status') or '事实不足'}",
    ]
    if record.get("recognition_date"):
        parts.append(f"确认日={record['recognition_date']}")
    if record.get("last_confirmed_date"):
        parts.append(f"最近完整续证日={record['last_confirmed_date']}")
    relative_path_profile = record.get("relative_path_profile")
    relative_path_profile = (
        relative_path_profile if isinstance(relative_path_profile, dict) else {}
    )
    if relative_path_profile.get("evidence_status") == "完整":
        parts.append(
            "同起点位置="
            + _text(relative_path_profile.get("position_label"))
            + f"；区间收益={relative_path_profile.get('interval_return_pct')}%"
        )
    return parts


def _three_axis_stage_mainline_input(
    value: Any,
    target_date: str,
    *,
    direction: str = "",
) -> dict:
    raw = deepcopy(value) if isinstance(value, dict) else {}
    rotation_dates = _bounded_dates(raw.get("phase_rotation_dates"), target_date)
    slope_dates = _bounded_dates(raw.get("sector_index_slope_dates"), target_date)
    rotation_status = _text(raw.get("phase_rotation_status")).lower()
    if rotation_status not in {"confirmed", "failed", "unresolved"}:
        rotation_status = "unresolved"
    if len(rotation_dates) < 2:
        rotation_status = "unresolved"
    slope_status = _text(raw.get("sector_index_slope_status")).lower()
    if slope_status not in {"upward", "flat", "downward", "unresolved"}:
        slope_status = "unresolved"
    if len(slope_dates) < 2:
        slope_status = "unresolved"

    cycle_mainline_source_date = _date(raw.get("cycle_mainline_source_date"))
    if cycle_mainline_source_date > target_date:
        cycle_mainline_source_date = ""
    cycle_mainline = (
        _text(raw.get("cycle_mainline")) if cycle_mainline_source_date else ""
    )
    daily_attack_line_source_date = _date(raw.get("daily_attack_line_source_date"))
    daily_attack_line = (
        _text(raw.get("daily_attack_line"))
        if daily_attack_line_source_date == target_date
        else ""
    )
    if not daily_attack_line:
        daily_attack_line_source_date = ""
    candidate_direction_source_date = _date(
        raw.get("candidate_direction_source_date")
    )
    observed_candidate_directions = (
        _strings(raw.get("candidate_directions"))
        if candidate_direction_source_date == target_date
        else []
    )
    candidate_direction_evidence = (
        _strings(raw.get("candidate_direction_evidence"))
        if observed_candidate_directions
        else []
    )
    if not observed_candidate_directions:
        candidate_direction_source_date = ""
    intraday_rotation_source_date = _date(raw.get("intraday_rotation_source_date"))
    intraday_rotation_count = _nonnegative_int(raw.get("intraday_rotation_count"))
    if intraday_rotation_source_date != target_date:
        intraday_rotation_count = None
        intraday_rotation_source_date = ""

    raw_records = [
        item for item in _list(raw.get("directions")) if isinstance(item, dict)
    ]
    if not raw_records and (direction or cycle_mainline):
        raw_records = [
            {
                "direction": direction or cycle_mainline,
                "source_date": cycle_mainline_source_date,
                "stage_start_date": rotation_dates[0] if rotation_dates else "",
                "trading_calendar": rotation_dates,
                "active_trade_dates": rotation_dates,
            }
        ]
    records = [
        record
        for item in raw_records
        if (
            record := _normalize_stage_mainline_record(
                item,
                target_date=target_date,
                fallback_direction=direction,
            )
        )
    ]
    records.sort(key=lambda item: (_text(item.get("direction")), item.get("status", "")))
    evaluated = next(
        (item for item in records if _text(item.get("direction")) == direction),
        records[0] if records and not direction else {},
    )
    confirmed_directions = [
        item["direction"]
        for item in records
        if item.get("status") == STAGE_MAINLINE_STATUS_CONFIRMED
    ]
    candidate_directions = [
        item["direction"]
        for item in records
        if item.get("status") == STAGE_MAINLINE_STATUS_CANDIDATE
    ]
    candidate_directions = list(
        dict.fromkeys([*candidate_directions, *observed_candidate_directions])
    )
    status = _text(evaluated.get("status")) or (
        STAGE_MAINLINE_STATUS_UNCONFIRMED
        if candidate_directions or daily_attack_line
        else STAGE_MAINLINE_STATUS_INSUFFICIENT
    )
    metric_value = _float(
        (evaluated.get("relative_strength_metric") or {}).get("value")
        if isinstance(evaluated.get("relative_strength_metric"), dict)
        else None
    )
    if status == STAGE_MAINLINE_STATUS_CONFIRMED:
        operation_context = "阶段主线上行" if metric_value and metric_value > 0 else "阶段主线已确认"
    elif status == STAGE_MAINLINE_STATUS_CANDIDATE and metric_value and metric_value > 0:
        operation_context = "上行热点，阶段主线尚未确认"
    elif status == STAGE_MAINLINE_STATUS_WEAKENED:
        operation_context = "阶段主线弱化，保留最近完整续证日"
    elif status == STAGE_MAINLINE_STATUS_INVALIDATED:
        operation_context = "阶段主线失效，重新观察"
    elif status == STAGE_MAINLINE_STATUS_UNCONFIRMED:
        operation_context = "当日多方向活跃，未形成跨日胜出方向"
    else:
        operation_context = "事实不足"

    slope_evidence = (
        _dated_as_of_evidence_rows(raw.get("sector_index_slope_evidence"), target_date)
        if len(slope_dates) >= 2
        else []
    )
    evidence = _stage_mainline_record_evidence(evaluated) if evaluated else []
    if candidate_directions:
        evidence.append("候选方向=" + "、".join(candidate_directions))
    evidence.extend(
        item for item in candidate_direction_evidence if item not in evidence
    )
    if daily_attack_line:
        evidence.append(f"当日主攻线={daily_attack_line}")
    if intraday_rotation_count is not None:
        evidence.append(
            f"目标日日内轮动={intraday_rotation_count}次，只作当日活跃证据"
        )
    counter_evidence = []
    if evaluated:
        counter_evidence.extend(
            _text(row.get("text"))
            for key in ("weakening_evidence", "invalidation_evidence")
            for row in _list(evaluated.get(key))
            if isinstance(row, dict) and _text(row.get("text"))
        )
    missing_fields = [
        f"stage_mainline.{item}"
        for item in _list(evaluated.get("missing_fields"))
        if _text(item)
    ]
    if not evaluated:
        missing_fields.append("stage_mainline.direction_record")

    direct_fields = {
        key: deepcopy(evaluated.get(key))
        for key in (
            "stage_start_date",
            "recognition_date",
            "last_confirmed_date",
            "as_of_date",
            "stage_span_trading_days",
            "active_trade_dates",
            "reflow_dates",
            "active_trade_day_count",
            "sector_index_path",
            "relative_path_profile",
            "relative_strength_metric",
            "relative_strength_window",
            "comparison_universe_scope",
            "comparison_universe",
            "comparison_coverage",
            "relative_strength_rank",
            "trend_stock_count",
            "comparable_stock_count",
            "trend_density",
            "trend_definition_version",
            "divergence_test_status",
            "divergence_date",
            "repair_date",
            "repair_evidence",
        )
    }
    return {
        "status": status,
        "operation_context": operation_context,
        "evaluated_direction": _text(evaluated.get("direction")),
        "confirmed_directions": confirmed_directions,
        "candidate_directions": candidate_directions,
        "candidate_direction_source_date": candidate_direction_source_date,
        "candidate_direction_evidence": candidate_direction_evidence,
        "directions": records,
        "cycle_mainline": "、".join(confirmed_directions) or cycle_mainline,
        "cycle_mainline_source_date": (
            target_date if confirmed_directions else cycle_mainline_source_date
        ),
        "daily_attack_line": daily_attack_line,
        "daily_attack_line_source_date": daily_attack_line_source_date,
        "phase_rotation_status": rotation_status,
        "phase_rotation_dates": rotation_dates,
        "sector_index_slope_status": slope_status,
        "sector_index_slope_dates": slope_dates,
        "sector_index_slope_evidence": slope_evidence,
        "intraday_rotation_count": intraday_rotation_count,
        "intraday_rotation_source_date": intraday_rotation_source_date,
        "evidence": evidence,
        "counter_evidence": counter_evidence,
        "missing_fields": sorted(set(missing_fields)),
        "source_dates": sorted(
            {
                date
                for date in (
                    *(item for record in records for item in record.get("source_dates", [])),
                    cycle_mainline_source_date,
                    daily_attack_line_source_date,
                    candidate_direction_source_date,
                    intraday_rotation_source_date,
                    *(row.get("source_date") for row in slope_evidence),
                )
                if date and date <= target_date
            }
        ),
        "scope": "阶段主线可多于一个；当日主攻线仍需另行比较",
        **direct_fields,
    }


def _normalize_cross_day_competition(value: Any, target_date: str) -> dict:
    raw = deepcopy(value) if isinstance(value, dict) else {}
    source_date = _date(raw.get("source_date"))
    if source_date and source_date > target_date:
        raw = {}
        source_date = ""

    def direction_rows(items: Any) -> list[dict]:
        rows = []
        for item in _list(items):
            if isinstance(item, dict):
                direction = _text(
                    item.get("direction") or item.get("sector") or item.get("name")
                )
                row_source_date = _date(
                    item.get("source_date")
                    or item.get("trade_date")
                    or item.get("date")
                )
            else:
                direction = _text(item)
                row_source_date = source_date
            if direction and row_source_date and row_source_date <= target_date:
                row = {"direction": direction, "source_date": row_source_date}
                if row not in rows:
                    rows.append(row)
        return sorted(rows, key=lambda item: item["direction"])

    divergence_directions = direction_rows(
        raw.get("possible_divergence_directions")
    )
    beneficiary_directions = direction_rows(
        raw.get("possible_beneficiary_directions")
    )
    confirmation_facts = _source_dated_rows(
        raw.get("confirmation_facts"),
        target_date,
        source_date,
    )
    falsification_facts = _source_dated_rows(
        raw.get("falsification_facts"),
        target_date,
        source_date,
    )
    source_dates = sorted(
        {
            item
            for item in (
                source_date,
                *(row["source_date"] for row in divergence_directions),
                *(row["source_date"] for row in beneficiary_directions),
                *(row["source_date"] for row in confirmation_facts),
                *(row["source_date"] for row in falsification_facts),
            )
            if item and item <= target_date
        }
    )
    complete = bool(
        (divergence_directions or beneficiary_directions)
        and confirmation_facts
        and falsification_facts
    )
    return {
        "as_of_date": target_date,
        "horizon_trade_days": [1, 2],
        "possible_divergence_directions": divergence_directions,
        "possible_beneficiary_directions": beneficiary_directions,
        "confirmation_facts": confirmation_facts,
        "falsification_facts": falsification_facts,
        "evidence_status": "完整" if complete else "事实不足",
        "source_dates": source_dates,
        "formal_effect": "none",
    }


def _three_axis_proof_input(value: Any, target_date: str) -> dict:
    proof = deepcopy(value) if isinstance(value, dict) else {}
    source_date = _date(proof.get("source_date"))
    if not source_date or source_date > target_date:
        return {}
    continuity_dates = sorted(
        {
            date
            for date in (_date(item) for item in _list(proof.get("continuity_dates")))
            if date and date <= target_date
        }
    )
    direction_source_date = _date(
        proof.get("direction_source_date") or source_date
    )
    direction = (
        _text(proof.get("direction"))
        if direction_source_date and direction_source_date <= target_date
        else ""
    )
    return {
        "direction": direction,
        "direction_source_date": direction_source_date if direction else "",
        "source_date": source_date,
        "continuity_dates": continuity_dates,
        "cross_day_continuity_status": _text(proof.get("cross_day_continuity_status")),
        "divergence_acceptance_status": _text(proof.get("divergence_acceptance_status")),
        "internal_expansion_status": _text(proof.get("internal_expansion_status")),
        "competition_comparison_status": _text(proof.get("competition_comparison_status")),
        "competition_state": _text(proof.get("competition_state")),
        "first_active_divergence": _explicit_bool_value(proof.get("first_active_divergence")),
        "capital_return_status": _text(proof.get("capital_return_status")),
        "consensus_status": _text(proof.get("consensus_status")),
        "story_spread_status": _text(proof.get("story_spread_status")),
        "trend_continuation_status": _text(proof.get("trend_continuation_status")),
        "leader_structure_status": _text(proof.get("leader_structure_status")),
        "stage_mainline_evidence": _three_axis_stage_mainline_input(
            proof.get("stage_mainline_evidence"),
            target_date,
            direction=direction,
        ),
        "cross_day_competition": _normalize_cross_day_competition(
            proof.get("cross_day_competition"),
            target_date,
        ),
    }


def _three_axis_market_input(value: Any, target_date: str) -> dict:
    market = deepcopy(value) if isinstance(value, dict) else {}
    source_date = _date(market.get("source_date"))
    if not source_date or source_date > target_date:
        return {}
    return {
        "source_date": source_date,
        "market_state": _text(market.get("market_state")),
        "broad_market_confirmation": _explicit_bool_value(
            market.get("broad_market_confirmation")
        ),
        "systemic_risk": _explicit_bool_value(market.get("systemic_risk")),
        "weak_market": _explicit_bool_value(market.get("weak_market")),
    }


def _three_axis_liquidity_facts_input(value: Any, target_date: str) -> dict:
    raw = deepcopy(value) if isinstance(value, dict) else {}
    current_source_date = _date(raw.get("current_turnover_source_date"))
    current_total_turnover = _float(raw.get("current_total_turnover"))
    if (
        current_source_date != target_date
        or not current_total_turnover
        or not math.isfinite(current_total_turnover)
        or current_total_turnover <= 0
    ):
        current_source_date = ""
        current_total_turnover = None

    previous_source_date = _date(raw.get("previous_turnover_source_date"))
    previous_total_turnover = _float(raw.get("previous_total_turnover"))
    if (
        not previous_source_date
        or previous_source_date >= target_date
        or not previous_total_turnover
        or not math.isfinite(previous_total_turnover)
        or previous_total_turnover <= 0
    ):
        previous_source_date = ""
        previous_total_turnover = None

    breadth_source_date = _date(raw.get("market_breadth_source_date"))
    up_count = _exact_nonnegative_int(raw.get("up_count"))
    down_count = _exact_nonnegative_int(raw.get("down_count"))
    if (
        breadth_source_date != target_date
        or up_count is None
        or down_count is None
        or up_count + down_count <= 0
    ):
        breadth_source_date = ""
        up_count = None
        down_count = None

    missing_fields = []
    if current_total_turnover is None:
        missing_fields.append("current_total_turnover")
    if previous_total_turnover is None:
        missing_fields.append("previous_total_turnover")
    if up_count is None or down_count is None:
        missing_fields.append("market_breadth")
    return {
        "target_date": target_date,
        "current_total_turnover": current_total_turnover,
        "current_turnover_source_date": current_source_date,
        "previous_total_turnover": previous_total_turnover,
        "previous_turnover_source_date": previous_source_date,
        "up_count": up_count,
        "down_count": down_count,
        "market_breadth_source_date": breadth_source_date,
        "missing_fields": missing_fields,
        "source_dates": sorted(
            date
            for date in {
                current_source_date,
                previous_source_date,
                breadth_source_date,
            }
            if date
        ),
    }


def _build_liquidity_allocation_context(
    facts: dict,
    proof: dict,
    target_date: str,
) -> dict:
    current_total_turnover = _float(facts.get("current_total_turnover"))
    previous_total_turnover = _float(facts.get("previous_total_turnover"))
    up_count = _nonnegative_int(facts.get("up_count"))
    down_count = _nonnegative_int(facts.get("down_count"))
    turnover_change_pct = (
        round(
            (current_total_turnover / previous_total_turnover - 1.0) * 100.0,
            8,
        )
        if current_total_turnover is not None
        and previous_total_turnover is not None
        and previous_total_turnover > 0
        else None
    )
    turnover_status = (
        "缩量"
        if turnover_change_pct is not None and turnover_change_pct < 0
        else "放量"
        if turnover_change_pct is not None and turnover_change_pct > 0
        else "持平"
        if turnover_change_pct == 0
        else "事实不足"
    )
    breadth_status = (
        "下跌家数占优"
        if up_count is not None and down_count is not None and down_count > up_count
        else "上涨家数占优"
        if up_count is not None and down_count is not None and up_count > down_count
        else "涨跌家数相当"
        if up_count is not None and down_count is not None
        else "事实不足"
    )
    down_share_pct = (
        round(down_count / (up_count + down_count) * 100.0, 8)
        if up_count is not None and down_count is not None and up_count + down_count > 0
        else None
    )
    expansion_source_date = _date(proof.get("source_date"))
    expansion_status = (
        _text(proof.get("internal_expansion_status"))
        if expansion_source_date == target_date
        else ""
    )
    missing_fields = list(_strings(facts.get("missing_fields")))
    if expansion_status not in {"confirmed", "failed"}:
        missing_fields.append("sector_internal_expansion")
    facts_complete = not missing_fields
    concentrated = bool(
        facts_complete
        and turnover_status == "缩量"
        and breadth_status == "下跌家数占优"
        and expansion_status == "confirmed"
    )
    allocation_pattern = (
        "集中式上涨"
        if concentrated
        else "未确认集中式上涨"
        if facts_complete
        else "事实不足"
    )
    source_dates = sorted(
        {
            *(_date(value) for value in _list(facts.get("source_dates"))),
            expansion_source_date if expansion_status in {"confirmed", "failed"} else "",
        }
        - {""}
    )
    return {
        "target_date": target_date,
        "evidence_status": "完整" if facts_complete else "事实不足",
        "turnover": {
            "current_value": current_total_turnover,
            "current_source_date": _date(facts.get("current_turnover_source_date")),
            "previous_value": previous_total_turnover,
            "previous_source_date": _date(facts.get("previous_turnover_source_date")),
            "change_pct": turnover_change_pct,
            "status": turnover_status,
        },
        "market_breadth": {
            "up_count": up_count,
            "down_count": down_count,
            "down_share_pct": down_share_pct,
            "status": breadth_status,
            "source_date": _date(facts.get("market_breadth_source_date")),
        },
        "sector_internal_expansion_status": expansion_status or "事实不足",
        "sector_internal_expansion_source_date": (
            expansion_source_date
            if expansion_status in {"confirmed", "failed"}
            else ""
        ),
        "allocation_pattern": allocation_pattern,
        "interpretation": (
            "成交额收缩、板块内部扩散且全市场下跌家数占优，上涨集中在局部方向"
            if concentrated
            else "量能、板块内部扩散与市场宽度尚未共同证明上涨集中在局部方向"
            if facts_complete
            else "量能、市场宽度或板块内部扩散事实不足"
        ),
        "applies_to": "当日主攻线解释",
        "stage_mainline_effect": "none",
        "formal_effect": "none",
        "missing_fields": sorted(set(missing_fields)),
        "source_dates": source_dates,
    }


def _three_axis_question(
    question: str,
    conclusion: str,
    evidence: str,
    counter_evidence: str,
    next_check: str,
) -> dict:
    return {
        "question": question,
        "conclusion": conclusion or "事实不足",
        "evidence": evidence or "事实不足",
        "counter_evidence": counter_evidence or "暂无明确反方证据",
        "next_check": next_check or "下一交易日继续验证",
    }


def build_sector_tournament_three_axis(
    *,
    target_date: Any,
    sector_diffusion_stage_evidence: Any,
    local_trend_sector_proof: Any,
    market_participation_limit: Any,
    liquidity_allocation_facts: Any = None,
    source_refs: Any = None,
) -> dict:
    normalized_date = _date(target_date)
    if not normalized_date:
        return {}
    stage = _valid_sector_stage_input(
        sector_diffusion_stage_evidence,
        normalized_date,
    )
    proof = _three_axis_proof_input(local_trend_sector_proof, normalized_date)
    market = _three_axis_market_input(market_participation_limit, normalized_date)
    liquidity_facts = _three_axis_liquidity_facts_input(
        liquidity_allocation_facts,
        normalized_date,
    )
    liquidity_allocation_context = _build_liquidity_allocation_context(
        liquidity_facts,
        proof,
        normalized_date,
    )

    stage_name = _text(stage.get("stage"))
    direction = _text(stage.get("direction") or proof.get("direction"))
    broad_market = market.get("broad_market_confirmation") is True
    systemic_risk = market.get("systemic_risk") is True
    price_evidence = _strings(stage.get("stage_evidence"))
    counter_evidence = _strings(stage.get("counter_evidence"))
    price_confirmed = "目标日价格接受=已确认" in price_evidence
    price_rejected = "目标日价格接受=失败" in counter_evidence
    core_confirmed = proof.get("divergence_acceptance_status") == "confirmed"
    core_failed = proof.get("divergence_acceptance_status") == "failed"
    expansion_confirmed = proof.get("internal_expansion_status") == "confirmed"
    expansion_failed = proof.get("internal_expansion_status") == "failed"
    competition_confirmed = proof.get("competition_comparison_status") == "confirmed"
    competition_failed = proof.get("competition_comparison_status") == "failed"
    first_divergence = proof.get("first_active_divergence") is True
    competition_state = _text(proof.get("competition_state"))
    competition_state_label = {
        "observe": "多方向轮动，未形成聚焦",
        "confirm_next": "候选方向等待跨日确认",
        "open": "竞争方向对照已展开",
    }.get(competition_state, competition_state or "尚无可确认竞争结构")
    leader_state = _text(proof.get("leader_structure_status"))
    stage_mainline_input = proof.get("stage_mainline_evidence") or {}
    stage_mainline = deepcopy(stage_mainline_input)
    stage_mainline_status = _text(stage_mainline.get("status")) or "未形成阶段主线"
    stage_mainline_context = (
        _text(stage_mainline.get("operation_context"))
        or "尚未形成可复算的阶段窗口"
    )
    stage_mainline_evidence = _strings(stage_mainline.get("evidence"))
    stage_mainline_counter_evidence = _strings(
        stage_mainline.get("counter_evidence")
    )
    stage_mainline_missing = _strings(stage_mainline.get("missing_fields"))
    phase_rotation_status = _text(stage_mainline.get("phase_rotation_status"))
    phase_rotation_dates = _list(stage_mainline_input.get("phase_rotation_dates"))
    relative_metric = stage_mainline.get("relative_strength_metric")
    relative_metric = relative_metric if isinstance(relative_metric, dict) else {}
    relative_metric_value = _float(relative_metric.get("value"))
    sector_index_slope_status = (
        "upward"
        if relative_metric_value is not None and relative_metric_value > 0
        else "downward"
        if relative_metric_value is not None and relative_metric_value < 0
        else "flat"
        if relative_metric_value == 0
        else "unresolved"
    )
    sector_index_slope_dates = _list(
        stage_mainline.get("sector_index_slope_dates")
    )
    sector_index_slope_known = relative_metric_value is not None
    slope_label = {
        "upward": "向上",
        "flat": "无明显斜率",
        "downward": "向下",
    }.get(sector_index_slope_status, "未取得可比板块指数路径")
    intraday_rotation_count = stage_mainline.get("intraday_rotation_count")
    cycle_mainline_source_date = _date(
        stage_mainline.get("cycle_mainline_source_date")
    )
    daily_attack_line_source_date = _date(
        stage_mainline.get("daily_attack_line_source_date")
    )
    intraday_rotation_source_date = _date(
        stage_mainline.get("intraday_rotation_source_date")
    )
    cycle_mainline = _text(stage_mainline.get("cycle_mainline"))
    daily_attack_line = _text(stage_mainline.get("daily_attack_line"))
    confirmed_directions = _strings(stage_mainline.get("confirmed_directions"))
    observed_directions = confirmed_directions or _strings(
        stage_mainline.get("candidate_directions")
    )
    daily_attack_relation = (
        "当日主攻与阶段主线一致"
        if daily_attack_line and daily_attack_line in confirmed_directions
        else f"阶段观察方向={'、'.join(observed_directions)}；当日主攻线={daily_attack_line}，二者分开比较"
        if observed_directions and daily_attack_line
        else f"当日主攻线={daily_attack_line}；尚无跨日胜出方向"
        if daily_attack_line
        else "当日未形成可确认主攻线"
    )
    stage_mainline["daily_attack_relation"] = daily_attack_relation
    stage_mainline["sector_index_slope_status"] = sector_index_slope_status
    stage_mainline["sector_index_slope_label"] = slope_label
    cross_day_competition = proof.get("cross_day_competition") or {
        "as_of_date": normalized_date,
        "horizon_trade_days": [1, 2],
        "possible_divergence_directions": [],
        "possible_beneficiary_directions": [],
        "confirmation_facts": [],
        "falsification_facts": [],
        "evidence_status": "事实不足",
        "source_dates": [],
        "formal_effect": "none",
    }

    if stage_name == "健康扩散候选":
        space_stage = "市场响应" if broad_market else "板块扩散"
        next_link = "全面共识" if broad_market else "市场响应"
    elif stage_name == "早期确认候选":
        space_stage = "局部秩序形成"
        next_link = "板块扩散"
    else:
        space_stage = "局部秩序未确认"
        next_link = "局部秩序形成"
    if broad_market and proof.get("consensus_status") == "confirmed":
        space_stage = "全面共识"
        next_link = "检验趋势延续或末端扩散"

    if systemic_risk:
        time_stage = "趋势破坏候选"
    elif not direction and (observed_directions or daily_attack_line):
        time_stage = "多方向轮动，未形成跨日胜出"
    elif price_rejected or core_failed or expansion_failed or competition_failed:
        time_stage = "趋势破坏候选" if first_divergence else "传导受阻"
    elif first_divergence and core_confirmed and price_confirmed:
        time_stage = "首次主动分歧已承接"
    elif stage_name == "健康扩散候选" and broad_market:
        time_stage = "趋势延续"
    elif (
        stage_name == "健康扩散候选"
        and competition_state == "单主线聚焦"
    ):
        time_stage = "聚焦主升"
    elif (
        stage_name == "健康扩散候选"
        and competition_state in {"双主线竞争", "多方向竞争", "强势轮动"}
        and proof.get("capital_return_status") == "confirmed"
    ):
        time_stage = "强势轮动"
    elif stage_name == "早期确认候选":
        time_stage = "趋势形成"
    elif direction and proof:
        time_stage = "反复尝试"
    else:
        time_stage = "事实不足"

    if systemic_risk:
        cognition_stage = "假设未通过全局验证"
        price_validation = (
            "局部价格接受，但全局传导失败"
            if price_confirmed
            else "全局传导失败"
        )
    elif price_rejected:
        cognition_stage = "假设被价格否定"
        price_validation = "价格否定"
    elif price_confirmed and stage_name in {"早期确认候选", "健康扩散候选"}:
        cognition_stage = "假设获得验证"
        price_validation = "价格接受"
    elif direction:
        cognition_stage = "假设待验证"
        price_validation = "价格待确认"
    elif observed_directions or daily_attack_line:
        cognition_stage = "多方向假设均未通过跨日验证"
        price_validation = "尚无板块方向通过价格验证"
    else:
        cognition_stage = "事实不足"
        price_validation = "事实不足"

    if systemic_risk:
        counterfactual = "该强不强"
    elif first_divergence and core_confirmed and price_confirmed:
        counterfactual = "该跌未跌"
    elif price_rejected or core_failed or expansion_failed or competition_failed:
        counterfactual = "该强不强"
    else:
        counterfactual = "尚待验证"

    if (
        systemic_risk
        or price_rejected
        or time_stage in {"传导受阻", "趋势破坏候选", "事实不足"}
        or stage_mainline_status
        in {STAGE_MAINLINE_STATUS_WEAKENED, STAGE_MAINLINE_STATUS_INVALIDATED}
    ):
        edge_type = "暂无可确认优势"
    elif space_stage in {"市场响应", "全面共识"}:
        edge_type = "剩余惯性"
    elif space_stage == "板块扩散":
        edge_type = "趋势惯性"
    elif space_stage == "局部秩序形成":
        edge_type = "传导差"
    else:
        edge_type = "认知差观察"

    story_spread = proof.get("story_spread_status")
    if systemic_risk:
        story_price_relation = "局部价格仍有响应，但系统性风险正在破坏向全局传导"
    elif price_rejected:
        story_price_relation = "故事完整或仍在传播，但价格已经不再响应"
    elif space_stage == "局部秩序形成":
        story_price_relation = "故事尚未讲完，但局部秩序已经通过价格证明自己"
    elif story_spread == "widespread" or space_stage in {"市场响应", "全面共识"}:
        story_price_relation = "故事传播扩大，新增预期差收窄，但趋势仍需由价格继续验证"
    elif price_confirmed:
        story_price_relation = "价格已留下验证痕迹，故事完整度本身不决定参与资格"
    else:
        story_price_relation = "只有结构假设，尚无足够价格痕迹"

    quant_evidence = [
        item
        for item in (
            "跨日延续" if proof.get("cross_day_continuity_status") == "confirmed" else "",
            "核心承接" if core_confirmed else "",
            "内部扩散" if expansion_confirmed else "",
            "竞争方向对照" if competition_confirmed else "",
            "资金回流" if proof.get("capital_return_status") == "confirmed" else "",
            "阶段主线证据完整"
            if stage_mainline_status == STAGE_MAINLINE_STATUS_CONFIRMED
            else "",
            "板块指数斜率向上"
            if sector_index_slope_known and sector_index_slope_status == "upward"
            else "",
        )
        if item
    ]
    actual_parts = []
    if quant_evidence:
        actual_parts.append("、".join(quant_evidence))
    if price_validation != "事实不足":
        actual_parts.append(price_validation)
    if systemic_risk:
        actual_parts.append("系统性风险仍在释放")
    if liquidity_allocation_context.get("allocation_pattern") == "集中式上涨":
        actual_parts.append("缩量背景下上涨集中在局部方向")
    actual_response = "；".join(actual_parts) or "尚无方向完成量化与价格双重验证"
    expected_response = (
        "若只是单日脉冲，应较快被吞没；若趋势形成，分歧后应继续承接并扩散"
    )
    falsification = (
        "若核心承接消失、内部扩散收缩、竞争方向夺回资金或价格否定，则修正或否定传导假设"
    )
    cognition_axis = {
        "stage": cognition_stage,
        "hypothesis": (
            f"{direction or '待确认方向'}的局部秩序正在向更大范围传导"
            if direction
            else "尚未形成可证伪的板块传导假设"
        ),
        "quant_evidence": quant_evidence
        or ["尚无方向同时满足跨日延续、核心承接、内部扩散与竞争胜出"],
        "price_validation": price_validation,
        "expected_response": expected_response,
        "actual_response": actual_response,
        "counterfactual_conclusion": counterfactual,
        "falsification": falsification,
    }

    missing_fields = sorted(
        set(
            _strings(stage.get("missing_fields"))
            + (["sector_diffusion_stage_evidence"] if not stage else [])
            + (["local_trend_sector_proof"] if not proof else [])
            + (["market_participation_limit"] if not market else [])
            + stage_mainline_missing
            + (
                ["cross_day_competition"]
                if cross_day_competition.get("evidence_status") != "完整"
                else []
            )
        )
    )
    remaining = _strings(stage.get("remaining_diffusion_evidence"))
    if space_stage == "市场响应":
        remaining = ["全面共识仍需价格和参与者继续扩散"]
    elif space_stage == "全面共识":
        remaining = ["只剩趋势延续与末端扩散的反证复核"]

    stage_evidence_text = "、".join(price_evidence) or (
        "尚无正向确认；反方=" + "、".join(counter_evidence)
        if counter_evidence
        else "尚无方向完成目标日价格接受"
    )
    effective_counter_evidence = list(counter_evidence)
    if systemic_risk and "系统性风险仍在释放" not in effective_counter_evidence:
        effective_counter_evidence.append("系统性风险仍在释放")
    counter_text = "、".join(effective_counter_evidence) or "暂无明确反方证据"
    leader_conclusion = {
        "leader_driven": "龙头正在引领板块",
        "late_followers": "后排末端补涨",
    }.get(leader_state, "未形成可验证的龙头带动结构")
    market_conclusion = (
        "系统性风险仍在释放"
        if systemic_risk
        else "市场已经响应局部秩序"
        if broad_market
        else "市场尚未广泛确认"
    )
    divergence_conclusion = (
        "系统性风险使局部承接不足以确认趋势"
        if systemic_risk
        else "首次主动分歧已被承接"
        if first_divergence and core_confirmed and price_confirmed
        else "分歧破坏趋势候选"
        if first_divergence and (core_failed or price_rejected)
        else "分歧性质待确认"
    )
    remaining_consensus_space = (
        "较大：局部已经成立，全局尚未响应"
        if space_stage == "局部秩序形成"
        else "仍有：板块扩散尚待市场响应"
        if space_stage == "板块扩散"
        else "收窄：市场已经响应，主要检验趋势惯性"
        if space_stage == "市场响应"
        else "较小：全面共识后只剩延续与末端风险复核"
        if space_stage == "全面共识"
        else "尚未进入传播阶段：先确认跨日胜出方向"
    )
    ten_questions = [
        _three_axis_question("大势是否从震荡进入趋势", market_conclusion, "；".join(part for part in (market.get("market_state") or "事实不足", liquidity_allocation_context.get("interpretation") or "") if part), "系统性风险仍在释放" if systemic_risk else "暂无明确系统性反方证据", "观察市场宽度与赚钱效应是否继续响应"),
        _three_axis_question("当前处于什么时间阶段", time_stage, stage_evidence_text, counter_text, "按当前阶段复核承接、扩散或破坏"),
        _three_axis_question("盘面是强势轮动还是形成聚焦", competition_state_label, "；".join(part for part in ("竞争方向对照已确认" if competition_confirmed else "多个候选方向均有局部活跃但未胜出", liquidity_allocation_context.get("allocation_pattern") or "") if part), "竞争方向重新分流资金" if competition_failed else "暂无明确反方证据", "观察资金回流与竞争方向集中度"),
        _three_axis_question(
            "哪个板块积累了可复算的阶段主线证据",
            f"{direction or '未形成跨日胜出方向'}；{stage_mainline_status}",
            "；".join(
                [
                    (
                        "跨日日期=" + " -> ".join(proof.get("continuity_dates") or [])
                        if proof.get("continuity_dates")
                        else "尚无方向取得连续两个交易日确认"
                    ),
                    *(stage_mainline_evidence or ["候选方向未形成可复算阶段窗口"]),
                ]
            ),
            "、".join(stage_mainline_counter_evidence) or "暂无明确系统性反方证据",
            "逐日复核冷却后回流、相对强度、内部密度与适用的分歧修复",
        ),
        _three_axis_question("局部秩序传播到哪一环", space_stage, stage_evidence_text, counter_text, f"下一环={next_link}"),
        _three_axis_question("龙头在引领板块还是后排末端补涨", leader_conclusion, leader_state or "尚无载体同时证明核心承接与板块扩散", "载体不能带动板块内部响应" if leader_state == "late_followers" else "暂无明确反方证据", "复核核心、中军与后排的同步性"),
        _three_axis_question("主观假设获得哪些量化与价格验证", cognition_stage, actual_response, counter_text, falsification),
        _three_axis_question("当前分歧是有效承接还是趋势破坏", divergence_conclusion, "核心承接与价格接受" if core_confirmed and price_confirmed else "核心承接未确认；目标日已有价格否定", counter_text, "只在显式首次主动分歧事实下使用首次分歧名称"),
        _three_axis_question("当前优势来自哪里", edge_type, story_price_relation, counter_text, "观察优势是否从传导差转为趋势惯性"),
        _three_axis_question("剩余传播空间是否大于已形成共识", remaining_consensus_space, "、".join(remaining) or "当前尚未形成可传播的已确认局部秩序", story_price_relation, "继续比较新增事实与价格响应"),
    ]

    source_dates = sorted(
        {
            item
            for item in (
                *(_date(value) for value in _list(stage.get("source_dates"))),
                _date(proof.get("source_date")),
                _date(proof.get("direction_source_date")),
                _date(market.get("source_date")),
                *(_date(value) for value in _list(proof.get("continuity_dates"))),
                *(_date(value) for value in phase_rotation_dates),
                *(_date(value) for value in sector_index_slope_dates),
                cycle_mainline_source_date,
                daily_attack_line_source_date,
                intraday_rotation_source_date,
                *(
                    _date(value)
                    for value in _list(stage_mainline.get("source_dates"))
                ),
                *(
                    _date(value)
                    for value in _list(cross_day_competition.get("source_dates"))
                ),
                *(
                    _date(value)
                    for value in _list(liquidity_allocation_context.get("source_dates"))
                ),
                *(
                    _date(item.get("source_date"))
                    for item in _list(
                        stage_mainline_input.get("sector_index_slope_evidence")
                    )
                    if isinstance(item, dict)
                ),
            )
            if item and item <= normalized_date
        }
    )
    normalized_source_refs = sorted(
        set(
            _as_of_strings(source_refs, normalized_date)
            + _as_of_strings(stage.get("source_refs"), normalized_date)
        )
    )
    input_payload = {
        "target_date": normalized_date,
        "sector_diffusion_stage_evidence": stage,
        "local_trend_sector_proof": proof,
        "market_participation_limit": market,
        "liquidity_allocation_facts": liquidity_facts,
        "source_refs": normalized_source_refs,
    }
    artifact = {
        "schema_version": SECTOR_TOURNAMENT_THREE_AXIS_SCHEMA_VERSION,
        "decision_scope": DECISION_SCOPE,
        "formal_effect": "none",
        "target_date": normalized_date,
        "direction": direction,
        "direction_source_date": _date(proof.get("direction_source_date")),
        "space_axis": {
            "stage": space_stage,
            "reached_link": space_stage,
            "next_link": next_link,
            "remaining_evidence": remaining,
        },
        "time_axis": {"stage": time_stage},
        "cognition_axis": cognition_axis,
        "stage_mainline": stage_mainline,
        "liquidity_allocation_context": liquidity_allocation_context,
        "cross_day_competition": cross_day_competition,
        "sector_foundation": {
            "direction": direction,
            "direction_source_date": _date(proof.get("direction_source_date")),
            "continuity_dates": proof.get("continuity_dates") or [],
            "competition_state": competition_state,
            "leader_structure": leader_conclusion,
            "stage_mainline_status": stage_mainline_status,
            "sector_index_slope": slope_label,
        },
        "counterfactual_review": {
            "expected_response": expected_response,
            "actual_response": actual_response,
            "conclusion": counterfactual,
        },
        "edge_source": {"type": edge_type},
        "story_price_relation": story_price_relation,
        "remaining_consensus_space": remaining_consensus_space,
        "next_checks": [item["next_check"] for item in ten_questions],
        "ten_questions": ten_questions,
        "evidence": price_evidence,
        "counter_evidence": effective_counter_evidence,
        "missing_fields": missing_fields,
        "source_dates": source_dates,
        "source_refs": normalized_source_refs,
        "input_payload": input_payload,
        "input_hash": stable_json_hash(input_payload),
    }
    artifact["artifact_hash"] = canonical_sector_tournament_three_axis_hash(artifact)
    return artifact


def validate_sector_tournament_three_axis(
    value: Any,
    *,
    target_date: Any = "",
) -> bool:
    artifact = deepcopy(value) if isinstance(value, dict) else {}
    artifact_target_date = _date(artifact.get("target_date"))
    expected_target_date = _date(target_date) or artifact_target_date
    if (
        not artifact
        or not expected_target_date
        or artifact_target_date != expected_target_date
        or artifact.get("schema_version")
        != SECTOR_TOURNAMENT_THREE_AXIS_SCHEMA_VERSION
        or artifact.get("decision_scope") != DECISION_SCOPE
        or artifact.get("formal_effect") != "none"
    ):
        return False
    input_payload = artifact.get("input_payload")
    if not isinstance(input_payload, dict):
        return False
    rebuilt = build_sector_tournament_three_axis(
        target_date=expected_target_date,
        sector_diffusion_stage_evidence=input_payload.get(
            "sector_diffusion_stage_evidence"
        ),
        local_trend_sector_proof=input_payload.get("local_trend_sector_proof"),
        market_participation_limit=input_payload.get("market_participation_limit"),
        liquidity_allocation_facts=input_payload.get("liquidity_allocation_facts"),
        source_refs=input_payload.get("source_refs"),
    )
    return bool(rebuilt and rebuilt == artifact)


def build_sector_diffusion_stage_evidence(
    *,
    target_date: Any,
    local_trend_sector_proof: Any,
    price_acceptance_rows: Any = None,
    source_refs: Any = None,
) -> dict:
    normalized_date = _date(target_date)
    proof = deepcopy(local_trend_sector_proof) if isinstance(local_trend_sector_proof, dict) else {}
    raw_source_date = _date(proof.get("source_date"))
    proof_is_not_future = bool(
        normalized_date
        and raw_source_date
        and raw_source_date <= normalized_date
    )
    # A proof produced after the target day is one indivisible future fact. Do
    # not let fields copied alongside its date leak into the target-day hash.
    effective_proof = proof if proof_is_not_future else {}
    raw_direction_source_date = _date(
        effective_proof.get("direction_source_date") or raw_source_date
    )
    direction = (
        _text(effective_proof.get("direction"))
        if raw_direction_source_date
        and normalized_date
        and raw_direction_source_date <= normalized_date
        else ""
    )
    direction_source_date = raw_direction_source_date if direction else ""
    source_date = (
        raw_source_date
        if proof_is_not_future
        else ""
    )
    continuity_dates = sorted(
        {
            date
            for date in (_date(value) for value in _list(effective_proof.get("continuity_dates")))
            if date and normalized_date and date <= normalized_date
        }
    )
    cross_day_status = _text(effective_proof.get("cross_day_continuity_status"))
    core_status = _text(effective_proof.get("divergence_acceptance_status"))
    expansion_status = _text(effective_proof.get("internal_expansion_status"))
    competition_status = _text(effective_proof.get("competition_comparison_status"))
    price_rows = []
    accepted_price_rows = []
    rejected_price_rows = []
    for raw in _list(price_acceptance_rows):
        if not isinstance(raw, dict):
            continue
        row_date = _date(raw.get("source_date"))
        row = {
            "stock": _stock(raw.get("stock")),
            "sector": _text(raw.get("sector")),
            "status": _text(raw.get("status")) or "unresolved",
            "source_date": row_date,
            "source_refs": _strings(raw.get("source_refs")),
        }
        if row_date and normalized_date and row_date > normalized_date:
            continue
        price_rows.append(row)
        if row_date == normalized_date and row["status"] == "accepted":
            accepted_price_rows.append(row)
        if row_date == normalized_date and row["status"] in {"rejected", "risk_first", "price_rejected"}:
            rejected_price_rows.append(row)

    source_date_matches_target = bool(
        normalized_date
        and source_date
        and source_date == normalized_date
        and proof.get("source_date_matches_target") is not False
    )
    cross_day_confirmed = bool(
        cross_day_status == "confirmed"
        and len(continuity_dates) >= 2
    )
    core_confirmed = core_status == "confirmed"
    price_confirmed = bool(accepted_price_rows) and not rejected_price_rows

    missing_fields = []
    counter_evidence = []
    stage_evidence = []
    if direction:
        stage_evidence.append(f"资金方向={direction}")
    else:
        missing_fields.append("direction")
    if source_date_matches_target:
        stage_evidence.append(f"目标日板块事实={source_date}")
    else:
        missing_fields.append("sector_source_date")
        if raw_source_date and raw_source_date <= normalized_date:
            counter_evidence.append(
                f"板块事实日期={raw_source_date}，目标日={normalized_date or '未知'}"
            )
    if cross_day_confirmed:
        stage_evidence.append("跨日延续=" + " -> ".join(continuity_dates))
    elif cross_day_status == "failed":
        counter_evidence.append("跨日延续=失败")
    else:
        missing_fields.append("cross_day_continuity")
    if core_confirmed:
        stage_evidence.append("核心承接=已确认")
    elif core_status == "failed":
        counter_evidence.append("核心承接=失败")
    else:
        missing_fields.append("core_acceptance")
    if price_confirmed:
        stage_evidence.append("目标日价格接受=已确认")
    elif rejected_price_rows:
        counter_evidence.append("目标日价格接受=失败")
    else:
        missing_fields.append("target_day_price_acceptance")
    early_confirmed = bool(
        normalized_date
        and direction
        and source_date_matches_target
        and cross_day_confirmed
        and core_confirmed
        and price_confirmed
    )
    expansion_confirmed = expansion_status == "confirmed"
    competition_confirmed = competition_status == "confirmed"
    expansion_failed = expansion_status == "failed"
    competition_failed = competition_status == "failed"
    if expansion_failed:
        counter_evidence.append("内部扩散=失败")
    if competition_failed:
        counter_evidence.append("竞争方向对照=失败")
    if not early_confirmed:
        stage = "未确认"
        next_link = "补齐目标日板块、跨日延续、核心承接与价格接受事实"
    elif expansion_failed or competition_failed:
        stage = "未确认"
        next_link = "重新确认板块内部扩散与竞争方向对照"
    elif expansion_confirmed and competition_confirmed:
        stage = "健康扩散候选"
        next_link = "市场响应"
        stage_evidence.extend(("内部扩散=已确认", "竞争方向对照=已确认"))
    else:
        stage = "早期确认候选"
        next_link = "板块内部扩散"

    remaining_diffusion_evidence = []
    if early_confirmed:
        if not expansion_confirmed:
            remaining_diffusion_evidence.append("internal_expansion")
        if not competition_confirmed:
            remaining_diffusion_evidence.append("competition_comparison")

    source_dates = sorted(
        {
            value
            for value in [
                source_date,
                direction_source_date,
                *continuity_dates,
                *(row.get("source_date") for row in price_rows),
            ]
            if value and (not normalized_date or value <= normalized_date)
        }
    )
    normalized_source_refs = sorted(
        set(
            _strings(source_refs)
            + [
                ref
                for row in price_rows
                for ref in _strings(row.get("source_refs"))
            ]
        )
    )
    normalized_proof = {
        "direction": direction,
        "direction_source_date": direction_source_date,
        "source_date": source_date,
        "source_date_matches_target": source_date_matches_target,
        "continuity_dates": continuity_dates,
        "cross_day_continuity_status": cross_day_status,
        "divergence_acceptance_status": core_status,
        "internal_expansion_status": expansion_status,
        "competition_comparison_status": competition_status,
    }
    source_input = {
        "target_date": normalized_date,
        "local_trend_sector_proof": normalized_proof,
        "price_acceptance_rows": price_rows,
        "source_refs": normalized_source_refs,
    }
    artifact = {
        "schema_version": SECTOR_DIFFUSION_STAGE_SCHEMA_VERSION,
        "decision_scope": DECISION_SCOPE,
        "formal_effect": "none",
        "target_date": normalized_date,
        "direction": direction,
        "direction_source_date": direction_source_date,
        "stage": stage,
        "stage_evidence": stage_evidence,
        "counter_evidence": sorted(set(counter_evidence)),
        "next_link": next_link,
        "remaining_diffusion_evidence": remaining_diffusion_evidence,
        "missing_fields": sorted(set(missing_fields)),
        "source_dates": source_dates,
        "source_refs": normalized_source_refs,
        "input_payload": source_input,
        "input_hash": stable_json_hash(source_input),
    }
    artifact["artifact_hash"] = canonical_sector_diffusion_stage_evidence_hash(artifact)
    return artifact


def build_candidate_decision_evidence(
    data: Any,
    *,
    report_date: Any,
    source_decision_hash: str,
) -> dict:
    data = data if isinstance(data, dict) else {}
    normalized_date = _date(report_date)
    if not normalized_date:
        return {}
    workflow = data.get("selection_workflow")
    workflow = workflow if isinstance(workflow, dict) else {}
    facts, warnings = _facts_bundle(data, normalized_date)
    sectors = _sector_qualifications(workflow, facts, normalized_date)
    candidates, observations = _candidate_rows(workflow, facts, sectors)
    volume_price = _volume_price_evidence(facts, normalized_date)
    comparison = _comparison(candidates, workflow)
    holdings, holding_missing = _holdings(data, facts, normalized_date)
    capital_options = _capital_options(facts, holdings, volume_price, comparison)
    missing = list(holding_missing)
    if not sectors:
        missing.append("sector_qualifications")
    if not facts.get("volume_price_evidence"):
        missing.append("volume_price_evidence")
    if not facts.get("capital_qualifications"):
        missing.append("capital_qualifications")
    missing.extend(
        f"sector:{row.get('sector') or 'unknown'}:{field}"
        for row in sectors
        for field in row.get("missing_fields", [])
    )
    missing.extend(
        f"volume_price:{row.get('scope') or 'unknown'}:{field}"
        for row in [
            volume_price.get("market", {}),
            *volume_price.get("sectors", []),
            *volume_price.get("stocks", []),
        ]
        if isinstance(row, dict)
        for field in row.get("missing_fields", [])
    )
    missing.extend(
        f"capital:{name}:{field}"
        for name in ("hold", "add", "replace", "cash")
        for field in capital_options.get(name, {}).get("missing_fields", [])
    )
    source_dates = {
        "report_date": normalized_date,
        "sector_dates": sorted(
            set(row.get("source_date") for row in sectors if row.get("source_date"))
        ),
        "volume_price_dates": sorted(
            set(
                item.get("source_date")
                for item in [
                    volume_price.get("market", {}),
                    *volume_price.get("sectors", []),
                    *volume_price.get("stocks", []),
                ]
                if isinstance(item, dict) and item.get("source_date")
            )
        ),
        "holding_dates": sorted(
            set(row.get("source_date") for row in holdings if row.get("source_date"))
        ),
    }
    source_input = {
        "selection_workflow": workflow,
        "final_target_resolution": data.get("final_target_resolution"),
        "facts": facts,
        "position_lifecycle_records": data.get("position_lifecycle_records"),
    }
    artifact = {
        "schema_version": SCHEMA_VERSION,
        "report_date": normalized_date,
        "decision_scope": DECISION_SCOPE,
        "formal_effect": "none",
        "source_decision_hash": _text(source_decision_hash),
        "sector_qualifications": sectors,
        "candidates": candidates,
        "observations": observations,
        "holdings": holdings,
        "volume_price_evidence": volume_price,
        "capital_options": capital_options,
        "comparison": comparison,
        "missing_fields": sorted(set(missing)),
        "source_dates": source_dates,
        "warnings": sorted(set(warnings)),
        "input_hash": stable_json_hash(source_input),
    }
    artifact["availability"] = (
        "complete" if not artifact["missing_fields"] and not artifact["warnings"] else "partial"
    )
    artifact["artifact_hash"] = canonical_candidate_decision_evidence_hash(artifact)
    return artifact


def validate_candidate_decision_evidence(
    artifact: Any,
    *,
    report_date: Any,
    source_decision_hash: str = "",
) -> tuple[bool, list[str]]:
    if not isinstance(artifact, dict):
        return False, ["candidate_decision_evidence_type_invalid"]
    errors = []
    normalized_date = _date(report_date)
    if artifact.get("schema_version") != SCHEMA_VERSION:
        errors.append("candidate_decision_evidence_schema_invalid")
    if artifact.get("report_date") != normalized_date:
        errors.append("candidate_decision_evidence_report_date_mismatch")
    if artifact.get("decision_scope") != DECISION_SCOPE or artifact.get("formal_effect") != "none":
        errors.append("candidate_decision_evidence_scope_invalid")
    if source_decision_hash and artifact.get("source_decision_hash") != source_decision_hash:
        errors.append("candidate_decision_evidence_decision_hash_mismatch")
    for field, expected_type in REQUIRED_ARTIFACT_FIELDS.items():
        if field not in artifact:
            errors.append(f"candidate_decision_evidence_required_field_missing:{field}")
        elif not isinstance(artifact.get(field), expected_type):
            errors.append(f"candidate_decision_evidence_field_type_invalid:{field}")
    qualified_sectors = {
        row.get("sector")
        for row in _list(artifact.get("sector_qualifications"))
        if isinstance(row, dict) and row.get("status") == "qualified"
    }
    for row in _list(artifact.get("candidates")):
        if not isinstance(row, dict) or row.get("sector") not in qualified_sectors:
            errors.append("candidate_decision_evidence_candidate_sector_invalid")
            continue
        if row.get("stock_qualification") != "qualified" or not _stock(row.get("stock")):
            errors.append("candidate_decision_evidence_candidate_qualification_invalid")
    volume_price = artifact.get("volume_price_evidence")
    volume_price = volume_price if isinstance(volume_price, dict) else {}
    for row in [
        volume_price.get("market"),
        *_list(volume_price.get("sectors")),
        *_list(volume_price.get("stocks")),
    ]:
        if not isinstance(row, dict) or not row:
            continue
        if row.get("price_acceptance") not in PRICE_ACCEPTANCE_STATUSES:
            errors.append("candidate_decision_evidence_price_acceptance_invalid")
        if row.get("formal_effect") != "none":
            errors.append("candidate_decision_evidence_volume_effect_invalid")
        if row.get("source_date") and (
            not _date(row.get("source_date")) or row.get("source_date") > normalized_date
        ):
            errors.append("candidate_decision_evidence_volume_source_date_invalid")
        if row.get("next_source_date") and (
            not _date(row.get("next_source_date")) or row.get("next_source_date") > normalized_date
        ):
            errors.append("candidate_decision_evidence_volume_next_date_invalid")
        source_date = _date(row.get("source_date"))
        next_source_date = _date(row.get("next_source_date"))
        if next_source_date and source_date and next_source_date <= source_date:
            errors.append("candidate_decision_evidence_volume_next_date_invalid")
        if row.get("price_acceptance") in {"accepted", "rejected"} and (
            not source_date or not next_source_date or next_source_date <= source_date
        ):
            errors.append("candidate_decision_evidence_price_acceptance_dates_invalid")
    artifact_missing = set(_strings(artifact.get("missing_fields")))
    for row in _list(artifact.get("holdings")):
        if not isinstance(row, dict):
            errors.append("candidate_decision_evidence_holding_invalid")
            continue
        source_date = _date(row.get("source_date"))
        if row.get("source_date") and (not source_date or source_date > normalized_date):
            errors.append("candidate_decision_evidence_holding_source_date_invalid")
        row_missing = set(_strings(row.get("missing_fields")))
        holding_key = _stock_key(row.get("stock")) or "unknown"
        for field in row_missing:
            if f"holding:{holding_key}:{field}" not in artifact_missing:
                errors.append(
                    f"candidate_decision_evidence_holding_missing_unpropagated:{field}"
                )
        position_dates = {}
        for prefix in ("b1", "b2"):
            if not isinstance(row.get(prefix), dict):
                errors.append(f"candidate_decision_evidence_{prefix}_structure_invalid")
                leg = {}
            else:
                leg = row.get(prefix)
            for field in ("buy_date", "position_pct", "sellable_pct", "earliest_sell_date"):
                if field not in leg:
                    errors.append(
                        f"candidate_decision_evidence_{prefix}_required_field_missing:{field}"
                    )
            buy_date = _date(leg.get("buy_date"))
            position_dates[prefix] = buy_date
            earliest_sell_date = _date(leg.get("earliest_sell_date"))
            if _is_present(leg.get("buy_date")) and (
                not buy_date or buy_date > normalized_date
            ):
                errors.append(f"candidate_decision_evidence_{prefix}_buy_date_invalid")
            if _is_present(leg.get("earliest_sell_date")) and not earliest_sell_date:
                errors.append(f"candidate_decision_evidence_{prefix}_sell_date_invalid")
            elif earliest_sell_date and buy_date and earliest_sell_date <= buy_date:
                errors.append(f"candidate_decision_evidence_{prefix}_sell_date_invalid")
            for field in ("position_pct", "sellable_pct"):
                if not _valid_normalized_percentage(leg.get(field)):
                    errors.append(
                        f"candidate_decision_evidence_{prefix}_{field}_invalid"
                    )
            leg_active = bool(
                buy_date
                or earliest_sell_date
                or (_float(leg.get("position_pct")) or 0) > 0
                or (_float(leg.get("sellable_pct")) or 0) > 0
            )
            for field, value in (
                (f"{prefix}_buy_date", buy_date),
                (f"{prefix}_earliest_sell_date", earliest_sell_date),
                (f"{prefix}_position_pct", leg.get("position_pct")),
                (f"{prefix}_sellable_pct", leg.get("sellable_pct")),
            ):
                if leg_active and value in (None, "") and field not in row_missing:
                    errors.append(f"candidate_decision_evidence_holding_fact_missing:{field}")
        if (
            position_dates.get("b1")
            and position_dates.get("b2")
            and position_dates["b2"] <= position_dates["b1"]
        ):
            errors.append("candidate_decision_evidence_b2_buy_date_invalid")
        if not isinstance(row.get("exit_confirmation"), dict):
            errors.append("candidate_decision_evidence_exit_confirmation_structure_invalid")
            exit_confirmation = {}
        else:
            exit_confirmation = row.get("exit_confirmation")
        for field in ("status", "date", "position_pct"):
            if field not in exit_confirmation:
                errors.append(
                    f"candidate_decision_evidence_exit_confirmation_required_field_missing:{field}"
                )
        if exit_confirmation.get("status") not in {
            "unconfirmed",
            "partial",
            "confirmed",
            "unknown",
        }:
            errors.append("candidate_decision_evidence_exit_confirmation_status_invalid")
        exit_date = _date(exit_confirmation.get("date"))
        if _is_present(exit_confirmation.get("date")) and (
            not exit_date or exit_date > normalized_date
        ):
            errors.append("candidate_decision_evidence_exit_date_invalid")
        if (
            exit_confirmation.get("status") == "confirmed"
            and row.get("funds_released") is True
            and not exit_date
            and "exit_confirmation_date" not in _strings(row.get("missing_fields"))
        ):
            errors.append("candidate_decision_evidence_confirmed_exit_date_missing")
        if exit_confirmation.get("status") in {"partial", "confirmed"}:
            if not exit_date and "exit_confirmation_date" not in row_missing:
                errors.append("candidate_decision_evidence_exit_confirmation_date_missing")
            if (
                exit_confirmation.get("position_pct") is None
                and "exit_confirmation_position_pct" not in row_missing
            ):
                errors.append("candidate_decision_evidence_exit_confirmation_position_pct_missing")
        if not _valid_normalized_percentage(exit_confirmation.get("position_pct")):
            errors.append("candidate_decision_evidence_exit_position_pct_invalid")
        if not isinstance(row.get("planned_exit"), dict):
            errors.append("candidate_decision_evidence_planned_exit_structure_invalid")
            planned_exit = {}
        else:
            planned_exit = row.get("planned_exit")
        for field in ("date", "reason"):
            if field not in planned_exit:
                errors.append(
                    f"candidate_decision_evidence_planned_exit_required_field_missing:{field}"
                )
        if not isinstance(planned_exit.get("date"), str) or not isinstance(
            planned_exit.get("reason"), str
        ):
            errors.append("candidate_decision_evidence_planned_exit_field_type_invalid")
        if _is_present(planned_exit.get("date")) and not _date(planned_exit.get("date")):
            errors.append("candidate_decision_evidence_planned_exit_date_invalid")
        if planned_exit.get("reason") and not planned_exit.get("date") and "planned_exit_date" not in row_missing:
            errors.append("candidate_decision_evidence_planned_exit_date_missing")
    capital = artifact.get("capital_options")
    capital = capital if isinstance(capital, dict) else {}
    for name in ("hold", "add", "replace", "cash"):
        option = capital.get(name) if isinstance(capital.get(name), dict) else {}
        if option.get("status") not in QUALIFICATION_STATUSES:
            errors.append(f"candidate_decision_evidence_{name}_status_invalid")
    if capital.get("formal_effect") != "none":
        errors.append("candidate_decision_evidence_capital_effect_invalid")
    comparison = artifact.get("comparison")
    comparison = comparison if isinstance(comparison, dict) else {}
    replace = capital.get("replace") if isinstance(capital.get("replace"), dict) else {}
    if replace.get("status") == "qualified" and (
        comparison.get("status") not in {"clear_winner", "single_qualified"}
        or not _stock(comparison.get("winner"))
        or _stock_key(comparison.get("winner")) != _stock_key(replace.get("stock"))
    ):
        errors.append("candidate_decision_evidence_replace_winner_mismatch")
    add = capital.get("add") if isinstance(capital.get("add"), dict) else {}
    cash = capital.get("cash") if isinstance(capital.get("cash"), dict) else {}
    if (
        add.get("status") == "qualified"
        and replace.get("status") == "qualified"
        and cash.get("status") == "not_qualified"
    ):
        errors.append("candidate_decision_evidence_conflict_cash_invalid")
    expected_availability = (
        "complete"
        if not _strings(artifact.get("missing_fields")) and not _strings(artifact.get("warnings"))
        else "partial"
    )
    if artifact.get("availability") != expected_availability:
        errors.append("candidate_decision_evidence_availability_invalid")
    if artifact.get("artifact_hash") != canonical_candidate_decision_evidence_hash(artifact):
        errors.append("candidate_decision_evidence_hash_mismatch")
    return not errors, list(dict.fromkeys(errors))


def _replay_dated_rows(
    value: Any,
    *,
    entry_date: str,
    relation: str,
    label: str,
) -> tuple[list[dict], list[str]]:
    rows = [dict(row) for row in _list(value) if isinstance(row, dict)]
    missing = []
    dates = []
    for row in rows:
        normalized = _date(row.get("date"))
        if not normalized:
            missing.append(f"{label}_date")
            continue
        row["date"] = normalized
        dates.append(normalized)
    if len(dates) != len(rows):
        return [], sorted(set(missing))
    if len(set(dates)) != len(dates):
        missing.append(f"{label}_date_duplicate")
    if dates != sorted(dates):
        missing.append(f"{label}_date_order")
    if entry_date:
        if relation == "before" and any(date >= entry_date for date in dates):
            missing.append(f"{label}_date_not_before_entry")
        if relation == "after" and any(date <= entry_date for date in dates):
            missing.append(f"{label}_date_not_after_entry")
    if missing:
        return [], sorted(set(missing))
    return rows, []


def _replay_outcome(sample: dict, horizon: int) -> tuple[dict, list[str]]:
    missing = []
    entry = sample.get("entry") if isinstance(sample.get("entry"), dict) else {}
    entry_date = _date(entry.get("date"))
    entry_close = _float(entry.get("close"))
    future_rows, future_missing = _replay_dated_rows(
        sample.get("future_rows"),
        entry_date=entry_date,
        relation="after",
        label="future",
    )
    missing.extend(future_missing)
    if not entry_date or not entry_close or entry_close <= 0:
        missing.append("entry")
    if len(future_rows) < horizon:
        missing.append(f"future_day_{horizon}")
    if missing:
        return {}, missing
    window = future_rows[:horizon]
    outcome_row = window[horizon - 1]
    close = _float(outcome_row.get("close"))
    highs = [_float(row.get("high")) for row in window]
    lows = [_float(row.get("low")) for row in window]
    if close is None or any(value is None for value in highs + lows):
        return {}, [f"future_price_{horizon}"]
    return {
        "horizon": horizon,
        "outcome_date": _date(outcome_row.get("date")),
        "return_pct": round((close / entry_close - 1.0) * 100.0, 2),
        "mfe_pct": round((max(highs) / entry_close - 1.0) * 100.0, 2),
        "mae_pct": round((min(lows) / entry_close - 1.0) * 100.0, 2),
        "source": _text(outcome_row.get("data_source") or entry.get("data_source")),
    }, []


def _replay_path_fact(sample: dict, path: str, report_date: str) -> tuple[dict, float | None, list[str]]:
    missing = []
    raw_fact = sample.get("volume_price_fact")
    raw_fact = raw_fact if isinstance(raw_fact, dict) else {}
    fact = _normalize_volume_fact(raw_fact, "stock", report_date) if raw_fact else {}
    expected = {
        "moderate_volume": ("normal", "not_applicable"),
        "expanded_accepted": ("expanded", "accepted"),
        "expanded_declining": ("expanded", "rejected"),
    }.get(path)
    if not fact:
        missing.append("volume_price_fact")
    elif expected != (
        fact.get("disagreement_intensity"),
        fact.get("price_acceptance"),
    ):
        missing.append("volume_price_path_mismatch")
    entry = sample.get("entry") if isinstance(sample.get("entry"), dict) else {}
    entry_date = _date(entry.get("date"))
    if not entry_date:
        missing.append("entry_date")
    if fact and fact.get("source_date") != entry_date:
        missing.append("volume_price_entry_date_mismatch")
    if fact and fact.get("next_source_date") and fact.get("next_source_date") <= entry_date:
        missing.append("volume_price_next_date_invalid")
    entry_volume = _float(entry.get("volume"))
    previous_rows, previous_missing = _replay_dated_rows(
        sample.get("previous_five"),
        entry_date=entry_date,
        relation="before",
        label="previous_five",
    )
    missing.extend(previous_missing)
    previous_volumes = [_float(row.get("volume")) for row in previous_rows]
    relative_volume = None
    if (
        entry_volume is None
        or len(previous_volumes) != 5
        or any(value is None or value <= 0 for value in previous_volumes)
    ):
        missing.append("previous_five_volume")
    else:
        relative_volume = round(entry_volume / (sum(previous_volumes) / 5.0), 4)
    historical_rows = [entry, *_list(sample.get("previous_five")), *_list(sample.get("future_rows"))]
    row_sources = [
        _text(row.get("data_source"))
        for row in historical_rows
        if isinstance(row, dict)
    ]
    fact_source = _text(raw_fact.get("source"))
    if not row_sources or any(not source for source in row_sources) or not fact_source:
        missing.append("historical_source_missing")
    sources = {source for source in [*row_sources, fact_source] if source}
    if len(sources) != 1:
        missing.append("historical_source_consistency")
    if _text(sample.get("price_adjustment")) != "qfq":
        missing.append("price_adjustment")
    return fact, relative_volume, missing


def summarize_volume_price_replay(
    samples: Iterable[dict],
    *,
    horizons: Iterable[int] = REPLAY_HORIZONS,
) -> dict:
    normalized_horizons = tuple(sorted(set(int(item) for item in horizons if int(item) > 0)))
    rows = []
    missing = []
    counts = {path: 0 for path in REPLAY_PATHS}
    for sample in samples if isinstance(samples, Iterable) else []:
        if not isinstance(sample, dict):
            continue
        path = _text(sample.get("path"))
        report_date = _date(sample.get("report_date"))
        stock = _stock(sample.get("entry"))
        if path not in REPLAY_PATHS:
            missing.append("unknown_path")
            continue
        counts[path] += 1
        outcomes = []
        row_missing = []
        fact, relative_volume, fact_missing = _replay_path_fact(
            sample,
            path,
            report_date,
        )
        row_missing.extend(fact_missing)
        for horizon in normalized_horizons:
            outcome, outcome_missing = _replay_outcome(sample, horizon)
            if outcome:
                outcomes.append(outcome)
            row_missing.extend(outcome_missing)
        if not report_date:
            row_missing.append("report_date")
        entry_date = _date(
            sample.get("entry", {}).get("date")
            if isinstance(sample.get("entry"), dict)
            else ""
        )
        if report_date and entry_date and entry_date > report_date:
            row_missing.append("entry_after_report_date")
        rows.append(
            {
                "path": path,
                "report_date": report_date,
                "stock": stock,
                "price_adjustment": _text(sample.get("price_adjustment")),
                "volume_price_fact": fact,
                "relative_volume_vs_previous_five": relative_volume,
                "outcomes": outcomes,
                "missing_fields": sorted(set(row_missing)),
            }
        )
        missing.extend(f"{path}:{field}" for field in row_missing)
    absent_paths = [path for path, count in counts.items() if count == 0]
    missing.extend(f"{path}:sample" for path in absent_paths)
    payload = {
        "schema_version": REPLAY_SCHEMA_VERSION,
        "paths": [
            {
                "path": path,
                "sample_count": counts[path],
                "dated_outcomes": [row for row in rows if row.get("path") == path],
            }
            for path in REPLAY_PATHS
        ],
        "horizons": list(normalized_horizons),
        "sample_count": sum(counts.values()),
        "missing_fields": sorted(set(missing)),
        "field_readiness": {
            "same_historical_fact_shape": not bool(missing),
            "dated_3_5_10_outcomes": not bool(missing) and normalized_horizons == REPLAY_HORIZONS,
            "formal_b2_use_ready": False,
            "reason": (
                "historical_facts_incomplete"
                if missing
                else "one_calibration_sample_per_path_does_not_validate_a_formal_b2_rule"
            ),
        },
    }
    payload["artifact_hash"] = stable_json_hash(payload, excluded_keys={"artifact_hash"})
    return payload


__all__ = [
    "COMPARISON_FIELDS",
    "DECISION_SCOPE",
    "FACT_SCHEMA_VERSION",
    "PRICE_ACCEPTANCE_STATUSES",
    "REPLAY_HORIZONS",
    "REPLAY_PATHS",
    "REPLAY_SCHEMA_VERSION",
    "SCHEMA_VERSION",
    "SECTOR_DIFFUSION_STAGE_SCHEMA_VERSION",
    "SECTOR_TOURNAMENT_THREE_AXIS_SCHEMA_VERSION",
    "STAGE_MAINLINE_MIN_TRADING_DAYS",
    "build_candidate_decision_evidence",
    "build_sector_diffusion_stage_evidence",
    "build_sector_tournament_three_axis",
    "candidate_decision_evidence_cache_key",
    "canonical_candidate_decision_evidence_hash",
    "canonical_sector_diffusion_stage_evidence_hash",
    "canonical_sector_tournament_three_axis_hash",
    "summarize_volume_price_replay",
    "validate_candidate_decision_evidence",
    "validate_sector_tournament_three_axis",
]
