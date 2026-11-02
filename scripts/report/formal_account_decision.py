from __future__ import annotations

import datetime
from copy import deepcopy
from typing import Any

from knowledge.llm_wiki_manifest import stable_json_hash
from report.position_tier_contract import POSITION_TIER_B1_B2_PCT, POSITION_TIER_B1_PCT


FACT_SCHEMA_VERSION = "candidate_decision_evidence_facts.v1"
COMPARISON_FIELDS = (
    "sector_continuity",
    "stage_fit",
    "carrier_quality",
    "upside_space",
    "loss_boundary",
    "executability",
)
FORMAL_DECISION_INPUT_SCHEMA_VERSION = "formal_decision_input.v1"
FORMAL_ACCOUNT_DECISION_SCHEMA_VERSION = "formal_account_decision.v1"
DECISION_PROJECTION_SCHEMA_VERSION = "decision_projection.v1"
DECISION_PRODUCT_FREEZE_SCHEMA_VERSION = "decision_product_freeze.v1"
DECISION_PRODUCT_FREEZE_REVIEW_SCHEMA_VERSION = "decision_product_freeze_review.v1"
DECISION_PRODUCT_FREEZE_KEY = "decision_product_freeze"
FORMAL_ADD_REQUIRED_FIELDS = (
    "sector_continuity",
    "stock_continuity",
    "risk_adjusted_strongest",
    "loss_boundary",
    "account_capacity",
)
FORMAL_TREND_REQUIRED_FIELDS = (
    "sector_diffusion",
    "stock_carrier",
    "loss_boundary",
    "risk_adjusted_strongest",
)
QUALIFICATION_STATUSES = {
    "qualified",
    "not_qualified",
    "unresolved",
    "not_applicable",
}


def _text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _date(value: Any) -> str:
    text = _text(value)
    try:
        return datetime.date.fromisoformat(text).isoformat()
    except (TypeError, ValueError):
        return ""


def _list(value: Any) -> list:
    return list(value) if isinstance(value, (list, tuple)) else []


def _stock(value: Any) -> dict[str, str]:
    value = value if isinstance(value, dict) else {}
    nested = value.get("stock") if isinstance(value.get("stock"), dict) else {}
    source = {**value, **nested}
    name = _text(source.get("name") or source.get("stock_name") or source.get("名称"))
    raw_code = _text(
        source.get("code")
        or source.get("stock_code")
        or source.get("symbol")
        or source.get("代码")
    )
    digits = "".join(char for char in raw_code.split(".", 1)[0] if char.isdigit())
    code = digits[-6:] if len(digits) >= 6 else raw_code
    result = {key: item for key, item in {"name": name, "code": code}.items() if item}
    sector = _text(source.get("sector") or source.get("sector_name") or source.get("industry"))
    if sector:
        result["sector"] = sector
    return result


def _stock_key(value: Any) -> str:
    stock = _stock(value)
    return stock.get("code") or stock.get("name") or ""


def _status(value: Any) -> str:
    if isinstance(value, bool):
        return "qualified" if value else "not_qualified"
    if isinstance(value, dict):
        if isinstance(value.get("qualified"), bool):
            return "qualified" if value.get("qualified") else "not_qualified"
        value = value.get("status")
    normalized = _text(value).lower()
    return normalized if normalized in QUALIFICATION_STATUSES else "unresolved"


def _pct(value: Any) -> float | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        number = float(str(value).replace("%", "").strip())
    except (TypeError, ValueError):
        return None
    return number if 0 <= number <= 100 else None


def _normalized_trade_dates(*values: Any) -> list[str]:
    dates = {
        normalized
        for value in values
        for item in _list(value)
        if (normalized := _date(item))
    }
    return sorted(dates)


def _next_trade_date(after_date: Any, trade_dates: list[str]) -> str:
    normalized = _date(after_date)
    if not normalized:
        return ""
    return next((item for item in trade_dates if item > normalized), "")


def _source_date(value: Any, report_date: str, missing: list[str], field: str) -> str:
    normalized = _date(value)
    if not normalized or normalized > report_date:
        missing.append(field)
        return ""
    return normalized


def _normalize_sector_rows(facts: dict, report_date: str) -> list[dict]:
    rows = []
    for raw in _list(facts.get("sector_qualifications")):
        if not isinstance(raw, dict):
            continue
        missing = []
        sector = _text(raw.get("sector") or raw.get("sector_name"))
        source_date = _source_date(raw.get("source_date"), report_date, missing, "source_date")
        status = _status(raw)
        if not sector or not source_date:
            status = "unresolved"
        rows.append(
            {
                "sector": sector,
                "stage": _text(raw.get("stage") or raw.get("sector_stage")),
                "status": status,
                "source_date": source_date,
                "source": _text(raw.get("source")),
                "missing_fields": sorted(set(missing)),
            }
        )
    return sorted(rows, key=lambda item: (item.get("sector", ""), stable_json_hash(item)))


def _normalize_candidate_rows(facts: dict, sectors: list[dict]) -> tuple[list[dict], list[dict]]:
    sector_status = {}
    for row in sectors:
        sector = row.get("sector")
        status = row.get("status")
        if sector in sector_status and sector_status[sector] != status:
            sector_status[sector] = "unresolved"
        elif sector not in sector_status:
            sector_status[sector] = status
    eligible = []
    observations = []
    grouped = {}
    for raw in _list(facts.get("candidates")):
        if not isinstance(raw, dict):
            continue
        stock = _stock(raw)
        key = _stock_key(stock)
        if not key:
            continue
        sector = _text(raw.get("sector") or stock.get("sector"))
        comparison = raw.get("comparison_fields") if isinstance(raw.get("comparison_fields"), dict) else {}
        comparison_fields = {
            field: _status(comparison.get(field)) for field in COMPARISON_FIELDS
        }
        row = {
            "stock": stock,
            "sector": sector,
            "sector_qualification": sector_status.get(sector, "unresolved"),
            "stock_qualification": _status(raw.get("stock_qualification")),
            "executability": _status(raw.get("executability")),
            "comparison_fields": comparison_fields,
            "clear_advantage": raw.get("clear_advantage") is True,
            "evidence_sources": sorted(
                set(_text(item) for item in _list(raw.get("evidence_sources")) if _text(item))
            ),
        }
        grouped.setdefault(key, []).append(row)

    for key in sorted(grouped):
        rows = sorted(grouped[key], key=stable_json_hash)
        decision_hashes = {
            stable_json_hash(
                {
                    field: value
                    for field, value in candidate_row.items()
                    if field != "evidence_sources"
                }
            )
            for candidate_row in rows
        }
        if len(decision_hashes) > 1:
            stocks = sorted(
                (_stock(row.get("stock")) for row in rows),
                key=stable_json_hash,
            )
            sectors_for_key = {row.get("sector", "") for row in rows}
            row = {
                "stock": stocks[0] if stocks else {},
                "sector": sectors_for_key.pop() if len(sectors_for_key) == 1 else "",
                "sector_qualification": "unresolved",
                "stock_qualification": "unresolved",
                "executability": "unresolved",
                "comparison_fields": {
                    field: "unresolved" for field in COMPARISON_FIELDS
                },
                "clear_advantage": False,
                "evidence_sources": sorted(
                    {
                        source
                        for candidate_row in rows
                        for source in candidate_row.get("evidence_sources", [])
                    }
                ),
            }
        else:
            row = deepcopy(rows[0])
            row["evidence_sources"] = sorted(
                {
                    source
                    for candidate_row in rows
                    for source in candidate_row.get("evidence_sources", [])
                }
            )
        fully_qualified = bool(
            row["sector_qualification"] == "qualified"
            and row["stock_qualification"] == "qualified"
            and row["executability"] == "qualified"
            and all(
                value == "qualified"
                for value in row["comparison_fields"].values()
            )
        )
        (eligible if fully_qualified else observations).append(row)
    sorter = lambda item: (_stock_key(item.get("stock")), stable_json_hash(item))
    return sorted(eligible, key=sorter), sorted(observations, key=sorter)


def _candidate_selection(eligible: list[dict]) -> dict:
    explicit_winners = [row for row in eligible if row.get("clear_advantage")]
    winner = {}
    if len(explicit_winners) == 1:
        status = "clear_winner"
        winner = explicit_winners[0].get("stock") or {}
    elif len(eligible) == 1:
        status = "single_qualified"
        winner = eligible[0].get("stock") or {}
    elif len(eligible) >= 2 and len(
        {stable_json_hash(row.get("comparison_fields")) for row in eligible}
    ) == 1:
        status = "tie_unresolved"
    elif eligible:
        status = "unresolved"
    else:
        status = "no_qualified_candidate"
    return {
        "status": status,
        "winner": _stock(winner),
        "eligible_candidates": [deepcopy(row) for row in eligible],
        "tied_candidates": (
            [_stock(row.get("stock")) for row in eligible]
            if status == "tie_unresolved"
            else []
        ),
        "required_fields": list(COMPARISON_FIELDS),
    }


def _normalize_leg(
    raw: dict,
    prefix: str,
    trade_dates: list[str],
    missing: list[str],
    *,
    report_date: str,
) -> dict:
    nested = raw.get(prefix) if isinstance(raw.get(prefix), dict) else {}
    buy_date = _date(nested.get("buy_date") or raw.get(f"{prefix}_buy_date"))
    position_pct = _pct(nested.get("position_pct", raw.get(f"{prefix}_position_pct")))
    sellable_pct = _pct(nested.get("sellable_pct", raw.get(f"{prefix}_sellable_pct")))
    earliest_sell_date = _date(
        nested.get("earliest_sell_date") or raw.get(f"{prefix}_earliest_sell_date")
    )
    active = bool(buy_date or (position_pct or 0) > 0 or (sellable_pct or 0) > 0)
    if active and not buy_date:
        missing.append(f"{prefix}_buy_date")
    if active and position_pct is None:
        missing.append(f"{prefix}_position_pct")
    if active and sellable_pct is None:
        missing.append(f"{prefix}_sellable_pct")
    if active and not earliest_sell_date:
        earliest_sell_date = _next_trade_date(buy_date, trade_dates)
    if active and not earliest_sell_date:
        missing.append(f"{prefix}_earliest_sell_date")
    if earliest_sell_date and buy_date and earliest_sell_date <= buy_date:
        missing.append(f"{prefix}_earliest_sell_date")
        earliest_sell_date = ""
    if (
        position_pct is not None
        and sellable_pct is not None
        and sellable_pct > position_pct
    ):
        missing.append(f"{prefix}_sellable_pct")
        sellable_pct = position_pct
    if buy_date == report_date and (sellable_pct or 0) > 0:
        missing.append(f"{prefix}_sellable_pct")
        sellable_pct = 0.0
    return {
        "buy_date": buy_date,
        "position_pct": position_pct,
        "sellable_pct": sellable_pct,
        "earliest_sell_date": earliest_sell_date,
    }


def _normalize_lifecycle_record(
    raw: dict,
    *,
    report_date: str,
    trade_dates: list[str],
    default_decision_date: str,
) -> dict:
    missing = [item for item in _list(raw.get("missing_fields")) if _text(item)]
    stock = _stock(raw)
    if not stock:
        missing.append("stock")
    b1 = _normalize_leg(
        raw,
        "b1",
        trade_dates,
        missing,
        report_date=report_date,
    )
    b2 = _normalize_leg(
        raw,
        "b2",
        trade_dates,
        missing,
        report_date=report_date,
    )
    decision_date = _date(raw.get("decision_date") or default_decision_date)
    review_date = _date(raw.get("review_date")) or _next_trade_date(
        b1.get("buy_date"), trade_dates
    )
    if b1.get("buy_date") and not decision_date:
        missing.append("decision_date")
    if decision_date and b1.get("buy_date") and decision_date >= b1["buy_date"]:
        missing.append("decision_date")
        decision_date = ""
    if b1.get("buy_date") and not review_date:
        missing.append("review_date")
    if review_date and b1.get("buy_date") and review_date <= b1["buy_date"]:
        missing.append("review_date")
        review_date = ""
    if b2.get("buy_date") and b1.get("buy_date") and b2["buy_date"] <= b1["buy_date"]:
        missing.extend(("b2_buy_date", "b2_earliest_sell_date"))
        b2["buy_date"] = ""
        b2["earliest_sell_date"] = ""
    if b1.get("buy_date") and b1["buy_date"] > report_date:
        missing.append("b1_buy_date")
        b1["buy_date"] = ""
    if b2.get("buy_date") and b2["buy_date"] > report_date:
        missing.append("b2_buy_date")
        b2["buy_date"] = ""
        b2["earliest_sell_date"] = ""

    planned_exit_raw = raw.get("planned_exit") if isinstance(raw.get("planned_exit"), dict) else {}
    planned_exit = {
        "date": _date(planned_exit_raw.get("date") or raw.get("planned_exit_date")),
        "reason": _text(planned_exit_raw.get("reason") or raw.get("planned_exit_reason")),
    }
    exit_raw = raw.get("exit_confirmation") if isinstance(raw.get("exit_confirmation"), dict) else {}
    exit_status = _text(exit_raw.get("status") or raw.get("exit_status")).lower()
    if exit_status not in {"unconfirmed", "partial", "confirmed", "unknown"}:
        exit_status = "unknown"
        missing.append("exit_confirmation_status")
    exit_date = _date(exit_raw.get("date") or raw.get("exit_date"))
    exit_position_pct = _pct(
        exit_raw.get("position_pct", raw.get("exited_position_pct"))
    )
    if exit_date and exit_date > report_date:
        missing.append("exit_confirmation_date")
        exit_date = ""
        exit_status = "unconfirmed"
    if exit_status in {"partial", "confirmed"} and not exit_date:
        missing.append("exit_confirmation_date")
    if exit_status in {"partial", "confirmed"} and exit_position_pct is None:
        missing.append("exit_confirmation_position_pct")
    source_date = _source_date(raw.get("source_date"), report_date, missing, "source_date")
    funds_released = raw.get("funds_released") if isinstance(raw.get("funds_released"), bool) else None
    return {
        "stock": stock,
        "decision_date": decision_date,
        "b1_buy_date": b1.get("buy_date", ""),
        "review_date": review_date,
        "b2_buy_date": b2.get("buy_date", ""),
        "b1_earliest_sell_date": b1.get("earliest_sell_date", ""),
        "b2_earliest_sell_date": b2.get("earliest_sell_date", ""),
        "b1": b1,
        "b2": b2,
        "planned_exit": planned_exit,
        "exit_confirmation": {
            "status": exit_status or "unknown",
            "date": exit_date,
            "position_pct": exit_position_pct,
        },
        "funds_released": funds_released,
        "source_date": source_date,
        "source": _text(raw.get("source")),
        "missing_fields": sorted(set(missing)),
    }


def _normalize_lifecycle_records(
    raw_rows: Any,
    *,
    report_date: str,
    trade_dates: list[str],
    default_decision_date: str,
) -> list[dict]:
    records = [
        _normalize_lifecycle_record(
            raw,
            report_date=report_date,
            trade_dates=trade_dates,
            default_decision_date=default_decision_date,
        )
        for raw in _list(raw_rows)
        if isinstance(raw, dict)
    ]
    unfinished = []
    for record in records:
        confirmation = record.get("exit_confirmation") or {}
        active_legs = [
            leg
            for prefix in ("b1", "b2")
            if isinstance((leg := record.get(prefix)), dict)
            and bool(
                leg.get("buy_date")
                or leg.get("earliest_sell_date")
                or (leg.get("position_pct") or 0) > 0
                or (leg.get("sellable_pct") or 0) > 0
            )
        ]
        gross_position_complete = all(
            leg.get("position_pct") is not None for leg in active_legs
        )
        gross_position_pct = sum(
            _pct(leg.get("position_pct")) or 0 for leg in active_legs
        )
        confirmed_exit_pct = _pct(confirmation.get("position_pct"))
        ended = bool(
            confirmation.get("status") == "confirmed"
            and confirmation.get("date")
            and confirmation.get("date") <= report_date
            and record.get("funds_released") is True
            and gross_position_complete
            and confirmed_exit_pct is not None
            and confirmed_exit_pct >= gross_position_pct
        )
        if not ended:
            unfinished.append(record)
    return sorted(
        unfinished,
        key=lambda item: (_stock_key(item.get("stock")), item.get("b1_buy_date", "")),
    )


def _normalize_account_qualification(raw: Any, name: str) -> dict:
    raw = raw if isinstance(raw, dict) else {"status": raw}
    conditions = raw.get("required_conditions")
    conditions = conditions if isinstance(conditions, dict) else {}
    return {
        "name": name,
        "status": _status(raw),
        "stock": _stock(raw),
        "required_conditions": {
            _text(key): value for key, value in conditions.items() if _text(key)
        },
        "reason_codes": sorted(
            set(_text(item) for item in _list(raw.get("reason_codes")) if _text(item))
        ),
        "missing_fields": sorted(
            set(_text(item) for item in _list(raw.get("missing_fields")) if _text(item))
        ),
    }


def build_formal_decision_input(data: Any, *, report_date: Any) -> dict:
    data = data if isinstance(data, dict) else {}
    normalized_date = _date(report_date)
    existing = data.get("formal_decision_input")
    if (
        isinstance(existing, dict)
        and existing.get("schema_version") == FORMAL_DECISION_INPUT_SCHEMA_VERSION
        and existing.get("report_date") == normalized_date
    ):
        return deepcopy(existing)
    facts_present = "candidate_decision_evidence_facts" in data
    facts = data.get("candidate_decision_evidence_facts")
    if not facts_present:
        return {}
    facts = facts if isinstance(facts, dict) else {}
    warnings = []
    source_valid = True
    if facts.get("schema_version") != FACT_SCHEMA_VERSION:
        warnings.append("formal_decision_facts_schema_invalid")
        source_valid = False
    fact_report_date = _date(facts.get("report_date") or facts.get("target_date"))
    query_date = _date(facts.get("query_date"))
    if fact_report_date != normalized_date:
        warnings.append("formal_decision_facts_report_date_mismatch")
        source_valid = False
    if query_date != normalized_date:
        warnings.append("formal_decision_facts_query_date_mismatch")
        source_valid = False

    trade_dates = _normalized_trade_dates(
        facts.get("trade_dates"),
        facts.get("trading_dates"),
        data.get("trade_dates"),
        data.get("trading_dates"),
    )
    sectors = _normalize_sector_rows(facts, normalized_date) if source_valid else []
    eligible, observations = (
        _normalize_candidate_rows(facts, sectors) if source_valid else ([], [])
    )
    selection = _candidate_selection(eligible)
    if not source_valid:
        selection["status"] = "facts_invalid"
        selection["winner"] = {}
    lifecycle_source = (
        facts.get("holdings")
        if isinstance(facts.get("holdings"), (list, tuple))
        else data.get("position_lifecycle_records")
    )
    lifecycle_records = _normalize_lifecycle_records(
        lifecycle_source,
        report_date=normalized_date,
        trade_dates=trade_dates,
        default_decision_date=_date(facts.get("decision_date")),
    )
    supplied_options = facts.get("capital_qualifications")
    supplied_options = supplied_options if isinstance(supplied_options, dict) else {}
    qualifications = {
        name: _normalize_account_qualification(supplied_options.get(name), name)
        for name in ("hold", "add", "replace", "cash", "trend_continue")
    }
    approved_fields = data.get("approved_formal_fields")
    approved_fields = deepcopy(approved_fields) if isinstance(approved_fields, list) else []
    payload = {
        "schema_version": FORMAL_DECISION_INPUT_SCHEMA_VERSION,
        "report_date": normalized_date,
        "source_valid": source_valid,
        "candidate_selection": selection,
        "candidate_ledger": [deepcopy(row) for row in eligible],
        "candidate_observations": [deepcopy(row) for row in observations],
        "position_lifecycle_records": lifecycle_records,
        "account_qualifications": qualifications,
        "trade_dates": trade_dates,
        "approved_formal_fields": approved_fields,
        "ignored_evidence_fields": [
            "volume_price_evidence",
            "decision_robustness_version_health",
            "version_health",
        ],
        "warnings": sorted(set(warnings)),
    }
    payload["input_hash"] = stable_json_hash(
        {
            "facts": facts,
            "approved_formal_fields": approved_fields,
            "trade_dates": trade_dates,
        }
    )
    return payload


def prepare_formal_decision_input(data: Any, *, report_date: Any) -> dict:
    if not isinstance(data, dict):
        return {}
    payload = build_formal_decision_input(data, report_date=report_date)
    if not payload:
        return {}
    data["formal_decision_input"] = deepcopy(payload)
    data["position_lifecycle_records"] = deepcopy(
        payload.get("position_lifecycle_records") or []
    )
    return payload


def _condition_qualified(value: Any) -> bool:
    if value is True:
        return True
    return _text(value).lower() in {"qualified", "confirmed", "accepted", "supported"}


def _required_conditions_qualified(option: dict, fields: tuple[str, ...]) -> bool:
    conditions = option.get("required_conditions")
    conditions = conditions if isinstance(conditions, dict) else {}
    return all(_condition_qualified(conditions.get(field)) for field in fields)


def _record_position_pct(record: dict) -> float:
    total = sum(
        _pct((record.get(prefix) or {}).get("position_pct")) or 0
        for prefix in ("b1", "b2")
        if isinstance(record.get(prefix), dict)
    )
    confirmation = record.get("exit_confirmation")
    confirmation = confirmation if isinstance(confirmation, dict) else {}
    if record.get("funds_released") is True and confirmation.get("status") in {
        "partial",
        "confirmed",
    }:
        total -= _pct(confirmation.get("position_pct")) or 0
    return max(0.0, total)


def _relevant_holding(records: list[dict], *stocks: Any) -> dict:
    keys = [_stock_key(stock) for stock in stocks if _stock_key(stock)]
    for key in keys:
        for record in records:
            if _stock_key(record.get("stock")) == key:
                return record
    return records[0] if len(records) == 1 else {}


def _decision_stage(record: dict, report_date: str) -> str:
    if not record:
        return "decision_day"
    b1_buy_date = _date(record.get("b1_buy_date"))
    review_date = _date(record.get("review_date"))
    if b1_buy_date and report_date == b1_buy_date:
        return "b1_buy_day"
    if b1_buy_date and review_date and report_date >= review_date:
        return "b1_review_day"
    if b1_buy_date and report_date > b1_buy_date:
        return "between_b1_and_review"
    return "awaiting_b1"


def build_formal_account_decision(
    formal_input: Any,
    *,
    selection_workflow: Any,
    report_date: Any,
) -> dict:
    formal_input = formal_input if isinstance(formal_input, dict) else {}
    normalized_date = _date(report_date)
    if (
        formal_input.get("schema_version") != FORMAL_DECISION_INPUT_SCHEMA_VERSION
        or formal_input.get("report_date") != normalized_date
    ):
        return {}
    workflow = selection_workflow if isinstance(selection_workflow, dict) else {}
    final = workflow.get("final") if isinstance(workflow.get("final"), dict) else {}
    final_target = _stock(final.get("execution_object"))
    try:
        final_position_pct = int(float(final.get("position_pct") or 0))
    except (TypeError, ValueError):
        final_position_pct = 0
    if final_position_pct <= 0:
        final_target = {}

    records = [
        deepcopy(item)
        for item in _list(formal_input.get("position_lifecycle_records"))
        if isinstance(item, dict)
    ]
    options = formal_input.get("account_qualifications")
    options = options if isinstance(options, dict) else {}
    hold_option = options.get("hold") if isinstance(options.get("hold"), dict) else {}
    add_option = options.get("add") if isinstance(options.get("add"), dict) else {}
    replace_option = options.get("replace") if isinstance(options.get("replace"), dict) else {}
    trend_option = (
        options.get("trend_continue")
        if isinstance(options.get("trend_continue"), dict)
        else {}
    )
    relevant = _relevant_holding(
        records,
        add_option.get("stock"),
        hold_option.get("stock"),
        final_target,
    )
    relevant_stock = _stock(relevant.get("stock"))
    stage = _decision_stage(relevant, normalized_date)
    exposure_pct = sum(_record_position_pct(record) for record in records)
    available_pct = max(0.0, 100.0 - exposure_pct)
    trade_dates = _normalized_trade_dates(formal_input.get("trade_dates"))
    next_trade_date = _next_trade_date(normalized_date, trade_dates)
    selection = formal_input.get("candidate_selection")
    selection = selection if isinstance(selection, dict) else {}
    unique_target = bool(
        final_target
        and selection.get("status") in {"clear_winner", "single_qualified"}
        and _stock_key(selection.get("winner")) == _stock_key(final_target)
    )
    holding_keys = {_stock_key(record.get("stock")) for record in records}
    target_differs = bool(final_target and _stock_key(final_target) not in holding_keys)
    replace_ready = bool(
        unique_target
        and (
            (not records)
            or (
                replace_option.get("status") == "qualified"
                and _stock_key(replace_option.get("stock")) == _stock_key(final_target)
                and target_differs
            )
        )
    )
    account_exposure_complete = all(
        not {
            "b1_position_pct",
            "b2_position_pct",
            "exit_confirmation_position_pct",
        }.intersection(record.get("missing_fields") or [])
        for record in records
    )
    hold_ready = bool(
        relevant
        and hold_option.get("status") == "qualified"
        and _stock_key(hold_option.get("stock")) == _stock_key(relevant_stock)
    )
    trend_ready = bool(
        relevant
        and hold_ready
        and trend_option.get("status") == "qualified"
        and _stock_key(trend_option.get("stock")) == _stock_key(relevant_stock)
        and _required_conditions_qualified(trend_option, FORMAL_TREND_REQUIRED_FIELDS)
    )
    planned_exit = relevant.get("planned_exit") if isinstance(relevant.get("planned_exit"), dict) else {}
    exit_due = bool(
        planned_exit.get("date")
        and planned_exit.get("date") <= normalized_date
        and not trend_ready
    )
    add_ready = bool(
        relevant
        and unique_target
        and _stock_key(relevant_stock) == _stock_key(final_target)
        and stage == "b1_review_day"
        and hold_ready
        and not exit_due
        and account_exposure_complete
        and add_option.get("status") == "qualified"
        and _stock_key(add_option.get("stock")) == _stock_key(relevant_stock)
        and _required_conditions_qualified(add_option, FORMAL_ADD_REQUIRED_FIELDS)
        and available_pct >= POSITION_TIER_B1_PCT
        and next_trade_date
    )

    if stage == "b1_buy_day" and relevant:
        selected_action = "hold"
        reason_code = "b1_buy_day_only"
    elif replace_ready and records:
        selected_action = "replace"
        reason_code = "new_object_clear_winner"
    elif add_ready:
        selected_action = "add"
        reason_code = "same_stock_b2_all_base_conditions_met"
    elif relevant and stage == "b1_review_day" and (not hold_ready or exit_due):
        selected_action = "cash"
        reason_code = "review_exit_to_cash"
    elif relevant:
        selected_action = "hold"
        reason_code = "hold_b1_keep_cash" if hold_ready else "holding_fact_pending"
    elif replace_ready:
        selected_action = "replace"
        reason_code = "new_b1_plan"
    else:
        selected_action = "cash"
        reason_code = "no_unique_executable_object"

    exit_targets = []
    if selected_action in {"replace", "cash"} and records:
        for record in records:
            sellable = sum(
                _pct((record.get(prefix) or {}).get("sellable_pct")) or 0
                for prefix in ("b1", "b2")
                if isinstance(record.get(prefix), dict)
            )
            exit_targets.append(
                {
                    "stock": _stock(record.get("stock")),
                    "sellable_position_pct": min(100.0, sellable),
                    "exit_confirmation": deepcopy(record.get("exit_confirmation") or {}),
                    "funds_released": record.get("funds_released"),
                }
            )

    requires_exit_confirmation = bool(selected_action == "replace" and records)
    sellable_exit_pct = sum(
        _pct(target.get("sellable_position_pct")) or 0 for target in exit_targets
    )
    remaining_after_exit_pct = max(0.0, exposure_pct - sellable_exit_pct)
    if selected_action == "add":
        planned_total_pct = POSITION_TIER_B1_B2_PCT
        new_entry_pct = POSITION_TIER_B1_PCT
        closing_target_pct = planned_total_pct
    elif selected_action == "replace":
        planned_total_pct = POSITION_TIER_B1_PCT
        new_entry_pct = 0 if requires_exit_confirmation or not next_trade_date else POSITION_TIER_B1_PCT
        closing_target_pct = (
            remaining_after_exit_pct
            if requires_exit_confirmation
            else planned_total_pct
        )
    elif selected_action == "hold":
        planned_total_pct = exposure_pct
        new_entry_pct = 0
        closing_target_pct = exposure_pct
    else:
        planned_total_pct = 0
        new_entry_pct = 0
        closing_target_pct = remaining_after_exit_pct

    if selected_action == "replace":
        decision_date = normalized_date
        b1_buy_date = next_trade_date
        review_date = _next_trade_date(b1_buy_date, trade_dates)
        b1_earliest_sell_date = review_date
        b2_buy_date = ""
        b2_earliest_sell_date = ""
    else:
        decision_date = (
            _date(relevant.get("decision_date")) if relevant else normalized_date
        )
        b1_buy_date = _date(relevant.get("b1_buy_date")) if relevant else ""
        review_date = _date(relevant.get("review_date")) if relevant else ""
        b1_earliest_sell_date = (
            _date(relevant.get("b1_earliest_sell_date")) if relevant else ""
        )
        b2_buy_date = normalized_date if selected_action == "add" else _date(
            relevant.get("b2_buy_date") if relevant else ""
        )
        b2_earliest_sell_date = (
            next_trade_date
            if selected_action == "add"
            else _date(relevant.get("b2_earliest_sell_date") if relevant else "")
        )
    date_missing = ["account_exposure_above_100"] if exposure_pct > 100 else []
    if not account_exposure_complete:
        date_missing.append("account_exposure_incomplete")
    if selected_action == "replace" and not b1_buy_date:
        date_missing.append("b1_buy_date")
    if selected_action == "replace" and not review_date:
        date_missing.append("review_date")
    if selected_action == "replace" and b1_buy_date and not b1_earliest_sell_date:
        date_missing.append("b1_earliest_sell_date")
    if selected_action == "add" and not b2_earliest_sell_date:
        date_missing.append("b2_earliest_sell_date")

    outcomes = {
        name: {
            "selected": name == selected_action,
            "status": (
                "qualified"
                if name == selected_action
                else "not_qualified"
            ),
        }
        for name in ("hold", "add", "replace", "cash")
    }
    decision = {
        "schema_version": FORMAL_ACCOUNT_DECISION_SCHEMA_VERSION,
        "report_date": normalized_date,
        "selected_action": selected_action,
        "reason_codes": [reason_code],
        "formal_execution_object": final_target,
        "decision_stage": stage,
        "outcomes": outcomes,
        "position_lifecycle_records": records,
        "position_lifecycle_dates": {
            "decision_date": decision_date,
            "b1_buy_date": b1_buy_date,
            "review_date": review_date,
            "b2_buy_date": b2_buy_date,
            "b1_earliest_sell_date": b1_earliest_sell_date,
            "b2_earliest_sell_date": b2_earliest_sell_date,
        },
        "b1": {
            "action": (
                "plan_after_exit"
                if selected_action == "replace" and requires_exit_confirmation
                else "plan"
                if selected_action == "replace"
                else "exit"
                if selected_action == "cash" and relevant
                else "hold"
                if relevant
                else "none"
            ),
            "stock": final_target if selected_action == "replace" else relevant_stock,
            "position_pct": POSITION_TIER_B1_PCT if selected_action == "replace" else _pct(
                (relevant.get("b1") or {}).get("position_pct") if relevant else None
            )
            or 0,
            "buy_date": b1_buy_date,
            "earliest_sell_date": b1_earliest_sell_date,
        },
        "b2": {
            "action": "buy" if selected_action == "add" else "not_buy",
            "stock": relevant_stock if selected_action == "add" else {},
            "position_pct": POSITION_TIER_B1_PCT if selected_action == "add" else 0,
            "buy_date": b2_buy_date if selected_action == "add" else "",
            "earliest_sell_date": b2_earliest_sell_date if selected_action == "add" else "",
        },
        "exit_plan": {
            "targets": exit_targets,
            "requires_confirmation_before_reuse": requires_exit_confirmation,
        },
        "account_exposure": {
            "current_position_pct": exposure_pct,
            "available_position_pct": available_pct,
            "planned_total_position_pct": planned_total_pct,
            "executable_new_entry_pct": new_entry_pct,
            "max_runtime_exposure_pct": exposure_pct + new_entry_pct,
            "closing_target_position_pct": closing_target_pct,
        },
        "approved_formal_fields": deepcopy(formal_input.get("approved_formal_fields") or []),
        "ignored_evidence_fields": deepcopy(formal_input.get("ignored_evidence_fields") or []),
        "missing_fields": sorted(set(date_missing)),
    }
    decision["decision_hash"] = stable_json_hash(
        {key: value for key, value in decision.items() if key != "decision_hash"}
    )
    return decision


_DECISION_PROJECTION_ROOT_KEYS = (
    "selection_workflow",
    "final_target_resolution",
    "position_decision",
    "two_layer_decision_payload",
    "formal_decision_input",
    "formal_account_decision",
)
_DECISION_PRODUCT_EVIDENCE_KEYS = (
    "candidate_decision_evidence",
    "decision_robustness_version_health",
    "research_execution_evidence",
    "market_polarization_evidence",
)
_OPTIONAL_DECISION_PRODUCT_EVIDENCE_KEYS = frozenset(
    {"market_polarization_evidence"}
)
_DECISION_PRODUCT_ACCOUNT_ACTIONS = {"hold", "add", "replace", "cash", "unresolved"}


def _decision_product_sources(data: Any) -> list[dict]:
    if not isinstance(data, dict):
        return []
    sources = [data]
    market_snapshot = data.get("market_research_snapshot")
    execution_context = data.get("execution_stage_context")
    if isinstance(market_snapshot, dict):
        sources.append(market_snapshot)
    if isinstance(execution_context, dict):
        sources.append(execution_context)
        nested_snapshot = execution_context.get("market_research_snapshot")
        if isinstance(nested_snapshot, dict):
            sources.append(nested_snapshot)
    unique = []
    seen = set()
    for source in sources:
        marker = id(source)
        if marker in seen:
            continue
        seen.add(marker)
        unique.append(source)
    return unique


def _first_decision_product_mapping(data: Any, key: str) -> dict:
    for source in _decision_product_sources(data):
        value = source.get(key)
        if isinstance(value, dict):
            return deepcopy(value)
    return {}


def _decision_product_artifact_date(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    for key in ("target_date", "report_date", "trade_date", "source_date", "date"):
        normalized = _date(value.get(key))
        if normalized:
            return normalized
    return ""


def _decision_product_source_dates(
    target_date: str,
    *,
    formal_input: dict,
    formal_account: dict,
    evidence: dict | None = None,
    knowledge: dict | None = None,
) -> dict[str, str]:
    result = {"target_date": target_date}
    candidates = {
        "formal_input": _decision_product_artifact_date(formal_input),
        "formal_account": _decision_product_artifact_date(formal_account),
    }
    for key, value in (evidence or {}).items():
        if isinstance(value, dict):
            candidates[key] = _decision_product_artifact_date(value)
    if isinstance(knowledge, dict):
        candidates["knowledge_explanation"] = _date(knowledge.get("target_date"))
    for key, value in candidates.items():
        if value:
            result[key] = value
    return result


def _decision_product_candidate_row_id(selection_workflow: dict, formal_object: dict) -> str:
    target_key = _stock_key(formal_object)
    if not target_key:
        return ""
    for raw in _list(selection_workflow.get("candidate_pool")):
        if not isinstance(raw, dict):
            continue
        candidate = raw.get("stock") if isinstance(raw.get("stock"), dict) else raw
        if _stock_key(candidate) != target_key:
            continue
        explicit = _text(
            raw.get("candidate_row_id")
            or raw.get("row_id")
            or raw.get("case_id")
            or raw.get("candidate_id")
        )
        return explicit or f"candidate:{stable_json_hash(raw)}"
    return f"stock:{target_key}"


def canonical_decision_projection_hash(projection: Any) -> str:
    if not isinstance(projection, dict):
        return ""
    return stable_json_hash(
        {key: value for key, value in projection.items() if key != "projection_hash"}
    )


def canonical_decision_product_freeze_hash(artifact: Any) -> str:
    if not isinstance(artifact, dict):
        return ""
    return stable_json_hash(
        {key: value for key, value in artifact.items() if key != "freeze_hash"}
    )


def build_decision_projection(data: Any, *, target_date: Any) -> dict:
    normalized_date = _date(target_date)
    if not normalized_date or not isinstance(data, dict):
        return {}
    roots = {
        key: _first_decision_product_mapping(data, key)
        for key in _DECISION_PROJECTION_ROOT_KEYS
    }
    final_resolution = roots["final_target_resolution"]
    formal_account = roots["formal_account_decision"]
    if not formal_account and isinstance(final_resolution.get("formal_account_decision"), dict):
        formal_account = deepcopy(final_resolution.get("formal_account_decision") or {})
        roots["formal_account_decision"] = formal_account
    if not any(roots.values()):
        return {}

    selection_workflow = roots["selection_workflow"]
    final = (
        selection_workflow.get("final")
        if isinstance(selection_workflow.get("final"), dict)
        else {}
    )
    formal_object = _stock(formal_account.get("formal_execution_object"))
    if not formal_object:
        formal_object = _stock(final_resolution.get("new_entry_target"))
    if not formal_object:
        formal_object = _stock(final.get("execution_object"))
    position_decision = roots["position_decision"]
    exposure = (
        formal_account.get("account_exposure")
        if isinstance(formal_account.get("account_exposure"), dict)
        else {}
    )
    exposure_plan = (
        final_resolution.get("account_exposure_plan")
        if isinstance(final_resolution.get("account_exposure_plan"), dict)
        else {}
    )

    action = _text(formal_account.get("selected_action")).lower()
    if action not in _DECISION_PRODUCT_ACCOUNT_ACTIONS:
        action = "unresolved"
    outcomes = (
        formal_account.get("outcomes")
        if isinstance(formal_account.get("outcomes"), dict)
        else final_resolution.get("account_options")
        if isinstance(final_resolution.get("account_options"), dict)
        else {}
    )
    normalized_outcomes = {
        name: deepcopy(outcomes.get(name)) if isinstance(outcomes.get(name), dict) else {}
        for name in ("hold", "add", "replace", "cash")
    }
    funds_destination = {
        "hold": "unused_capacity_cash",
        "add": "same_stock_b2",
        "replace": "new_b1_after_exit_confirmation",
        "cash": "cash",
    }.get(action, "unresolved")
    missing = []
    for key, value in roots.items():
        if not value:
            missing.append(key)
    if action == "unresolved":
        missing.append("account_action")

    projection = {
        "schema_version": DECISION_PROJECTION_SCHEMA_VERSION,
        "target_date": normalized_date,
        "formal_object": formal_object,
        "decision_position_pct": _pct(final.get("position_pct")),
        "account_position": {
            "current_position_pct": _pct(
                exposure.get("current_position_pct", exposure_plan.get("old_position_actual_pct"))
            ),
            "planned_total_position_pct": _pct(
                exposure.get(
                    "planned_total_position_pct",
                    exposure_plan.get("planned_new_entry_pct"),
                )
            ),
            "executable_new_entry_pct": _pct(
                exposure.get("executable_new_entry_pct", exposure_plan.get("new_entry_pct"))
            ),
            "closing_target_position_pct": _pct(
                exposure.get(
                    "closing_target_position_pct",
                    exposure_plan.get("tomorrow_closing_target_position_pct"),
                )
            ),
        },
        "execution_nature": _text(
            position_decision.get("execution_nature")
            or position_decision.get("participation_mode")
            or position_decision.get("final_action")
        ),
        "account_action": action,
        "account_outcomes": normalized_outcomes,
        "b1": deepcopy(formal_account.get("b1") or {}),
        "b2": deepcopy(formal_account.get("b2") or {}),
        "old_position_action": deepcopy(final_resolution.get("old_position_plan") or {}),
        "exit_action": deepcopy(
            formal_account.get("exit_plan")
            or position_decision.get("exit_action")
            or {}
        ),
        "funds_destination": {
            "mode": funds_destination,
            "requires_exit_confirmation": bool(
                ((formal_account.get("exit_plan") or {}).get("requires_confirmation_before_reuse"))
                if isinstance(formal_account.get("exit_plan"), dict)
                else False
            ),
        },
        "candidate_row_id": _decision_product_candidate_row_id(
            selection_workflow,
            formal_object,
        ),
        "input_hashes": {
            "formal_input": _text(roots["formal_decision_input"].get("input_hash")),
            "formal_account": _text(formal_account.get("decision_hash")),
        },
        "source_dates": _decision_product_source_dates(
            normalized_date,
            formal_input=roots["formal_decision_input"],
            formal_account=formal_account,
        ),
        "availability": "complete" if not missing else "partial",
        "missing_fields": sorted(set(missing)),
        **roots,
    }
    projection["projection_hash"] = canonical_decision_projection_hash(projection)
    return projection


def _build_decision_product_read_only_evidence(data: dict, target_date: str) -> dict:
    artifacts = {
        key: _first_decision_product_mapping(data, key)
        for key in _DECISION_PRODUCT_EVIDENCE_KEYS
    }
    candidate = artifacts.get("candidate_decision_evidence") or {}
    missing = [
        key
        for key, value in artifacts.items()
        if not value and key not in _OPTIONAL_DECISION_PRODUCT_EVIDENCE_KEYS
    ]
    volume_price = (
        candidate.get("volume_price_evidence")
        if isinstance(candidate.get("volume_price_evidence"), (dict, list))
        else {}
    )
    if not volume_price:
        missing.append("volume_price_evidence")
    source_dates = _decision_product_source_dates(
        target_date,
        formal_input={},
        formal_account={},
        evidence=artifacts,
    )
    return {
        "decision_scope": "explanation_only",
        "formal_effect": "none",
        **artifacts,
        "volume_price_evidence": deepcopy(volume_price),
        "source_dates": source_dates,
        "missing_fields": sorted(set(missing)),
        "availability": "complete" if not missing else "partial",
    }


def build_decision_product_freeze(
    data: Any,
    *,
    target_date: Any,
    artifact_origin: str = "fresh",
) -> dict:
    normalized_date = _date(target_date)
    if not normalized_date or not isinstance(data, dict):
        return {}
    projection = build_decision_projection(data, target_date=normalized_date)
    if not projection:
        return {}
    read_only_evidence = _build_decision_product_read_only_evidence(
        data,
        normalized_date,
    )
    knowledge = data.get("knowledge") if isinstance(data.get("knowledge"), dict) else {}
    llm_wiki = (
        deepcopy(knowledge.get("llm_wiki"))
        if isinstance(knowledge.get("llm_wiki"), dict)
        else {}
    )
    missing = list(projection.get("missing_fields") or [])
    missing.extend(read_only_evidence.get("missing_fields") or [])
    if not llm_wiki:
        missing.append("knowledge_explanation")
    source_dates = _decision_product_source_dates(
        normalized_date,
        formal_input=projection.get("formal_decision_input") or {},
        formal_account=projection.get("formal_account_decision") or {},
        evidence={
            key: read_only_evidence.get(key) or {}
            for key in _DECISION_PRODUCT_EVIDENCE_KEYS
        },
        knowledge=llm_wiki,
    )
    artifact = {
        "schema_version": DECISION_PRODUCT_FREEZE_SCHEMA_VERSION,
        "target_date": normalized_date,
        "artifact_origin": _text(artifact_origin) or "fresh",
        "decision_projection": projection,
        "read_only_evidence": read_only_evidence,
        "knowledge_explanation": llm_wiki,
        "source_dates": source_dates,
        "availability": "complete" if not missing else "partial",
        "missing_fields": sorted(set(missing)),
        "decision_projection_hash": canonical_decision_projection_hash(projection),
        "read_only_evidence_hash": stable_json_hash(read_only_evidence),
        "knowledge_explanation_hash": stable_json_hash(llm_wiki),
    }
    artifact["freeze_hash"] = canonical_decision_product_freeze_hash(artifact)
    return artifact


def build_legacy_decision_product_freeze(data: Any, *, target_date: Any) -> dict:
    return build_decision_product_freeze(
        data,
        target_date=target_date,
        artifact_origin="legacy_snapshot_mapping",
    )


def validate_decision_product_freeze(
    artifact: Any,
    *,
    target_date: Any,
) -> tuple[bool, list[str]]:
    normalized_date = _date(target_date)
    if not isinstance(artifact, dict):
        return False, ["decision_product_freeze_type_invalid"]
    errors = []
    if artifact.get("schema_version") != DECISION_PRODUCT_FREEZE_SCHEMA_VERSION:
        errors.append("decision_product_freeze_schema_invalid")
    if not normalized_date or artifact.get("target_date") != normalized_date:
        errors.append("decision_product_freeze_target_date_mismatch")
    projection = artifact.get("decision_projection")
    if not isinstance(projection, dict):
        errors.append("decision_product_freeze_projection_type_invalid")
        projection = {}
    elif projection.get("schema_version") != DECISION_PROJECTION_SCHEMA_VERSION:
        errors.append("decision_product_freeze_projection_schema_invalid")
    if projection.get("target_date") != normalized_date:
        errors.append("decision_product_freeze_projection_date_mismatch")
    for key in _DECISION_PROJECTION_ROOT_KEYS:
        if key not in projection:
            errors.append(f"decision_product_freeze_projection_field_missing:{key}")
        elif not isinstance(projection.get(key), dict):
            errors.append(f"decision_product_freeze_projection_field_type_invalid:{key}")
    if projection.get("account_action") not in _DECISION_PRODUCT_ACCOUNT_ACTIONS:
        errors.append("decision_product_freeze_account_action_invalid")
    expected_projection_hash = canonical_decision_projection_hash(projection)
    if not expected_projection_hash or projection.get("projection_hash") != expected_projection_hash:
        errors.append("decision_product_freeze_projection_hash_mismatch")
    if artifact.get("decision_projection_hash") != expected_projection_hash:
        errors.append("decision_product_freeze_projection_reference_hash_mismatch")

    evidence = artifact.get("read_only_evidence")
    if not isinstance(evidence, dict):
        errors.append("decision_product_freeze_evidence_type_invalid")
        evidence = {}
    if artifact.get("read_only_evidence_hash") != stable_json_hash(evidence):
        errors.append("decision_product_freeze_evidence_hash_mismatch")
    knowledge = artifact.get("knowledge_explanation")
    if not isinstance(knowledge, dict):
        errors.append("decision_product_freeze_knowledge_type_invalid")
        knowledge = {}
    if artifact.get("knowledge_explanation_hash") != stable_json_hash(knowledge):
        errors.append("decision_product_freeze_knowledge_hash_mismatch")
    source_dates = artifact.get("source_dates")
    if not isinstance(source_dates, dict):
        errors.append("decision_product_freeze_source_dates_type_invalid")
    else:
        for key, value in source_dates.items():
            normalized_source_date = _date(value)
            if not normalized_source_date:
                errors.append(f"decision_product_freeze_source_date_invalid:{key}")
            elif normalized_source_date > normalized_date:
                errors.append(f"decision_product_freeze_source_date_after_target:{key}")
    formal_account = projection.get("formal_account_decision")
    if isinstance(formal_account, dict) and formal_account.get("decision_hash"):
        expected_decision_hash = stable_json_hash(
            {
                key: value
                for key, value in formal_account.items()
                if key != "decision_hash"
            }
        )
        if formal_account.get("decision_hash") != expected_decision_hash:
            errors.append("decision_product_freeze_formal_account_hash_mismatch")
    expected_freeze_hash = canonical_decision_product_freeze_hash(artifact)
    if not expected_freeze_hash or artifact.get("freeze_hash") != expected_freeze_hash:
        errors.append("decision_product_freeze_hash_mismatch")
    return not errors, sorted(set(errors))


def decision_projection_from_freeze(
    artifact: Any,
    *,
    target_date: Any,
) -> dict:
    valid, _ = validate_decision_product_freeze(
        artifact,
        target_date=target_date,
    )
    if not valid:
        return {}
    return deepcopy(artifact.get("decision_projection") or {})


def apply_decision_product_freeze(
    data: Any,
    artifact: Any,
    *,
    target_date: Any,
) -> tuple[bool, dict]:
    if not isinstance(data, dict):
        return False, {}
    valid, errors = validate_decision_product_freeze(
        artifact,
        target_date=target_date,
    )
    review = {
        "schema_version": DECISION_PRODUCT_FREEZE_REVIEW_SCHEMA_VERSION,
        "target_date": _date(target_date),
        "availability": (
            str((artifact or {}).get("availability") or "available")
            if valid
            else "historical_snapshot_invalid"
        ),
        "artifact_origin": (
            _text((artifact or {}).get("artifact_origin"))
            if isinstance(artifact, dict)
            else ""
        ),
        "freeze_hash": (
            _text((artifact or {}).get("freeze_hash"))
            if isinstance(artifact, dict)
            else ""
        ),
        "valid": valid,
        "errors": errors,
    }
    data["decision_product_freeze_review"] = review
    if not valid:
        return False, review
    frozen = deepcopy(artifact)
    projection = frozen.get("decision_projection") or {}
    data[DECISION_PRODUCT_FREEZE_KEY] = frozen
    for key in _DECISION_PROJECTION_ROOT_KEYS:
        value = projection.get(key)
        if isinstance(value, dict) and value:
            data[key] = deepcopy(value)
        else:
            data.pop(key, None)
    formal_account = projection.get("formal_account_decision") or {}
    if isinstance(formal_account.get("position_lifecycle_records"), list):
        data["position_lifecycle_records"] = deepcopy(
            formal_account.get("position_lifecycle_records") or []
        )
    evidence = frozen.get("read_only_evidence") or {}
    for key in _DECISION_PRODUCT_EVIDENCE_KEYS:
        if isinstance(evidence.get(key), dict) and evidence.get(key):
            data[key] = deepcopy(evidence.get(key))
        else:
            data.pop(key, None)
    knowledge = frozen.get("knowledge_explanation") or {}
    if knowledge:
        data.setdefault("knowledge", {})["llm_wiki"] = deepcopy(knowledge)
    elif isinstance(data.get("knowledge"), dict):
        data["knowledge"].pop("llm_wiki", None)
    return True, review
