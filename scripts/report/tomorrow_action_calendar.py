from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Any, Callable, Iterable, Mapping


__all__ = [
    "build_tomorrow_action_calendar",
    "build_tomorrow_action_calendar_from_service",
    "empty_tomorrow_action_calendar",
]


CALENDAR_SCHEMA = "tomorrow_action_calendar.v1"
DEFAULT_RECORD_COUNT = 25
CUMULATIVE_RETURN_START_DATE = "2026-06-17"
MAX_NEXT_TRADE_DATE_GAP_DAYS = 14
LEG_POSITION_X = 1
LEG_WEIGHT_PCT = 50.0
WEEKDAY_LABELS = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")
# The local fact store has trading dates but no holiday-name table. Keep this
# small, source-labelled schedule for dates that appear in the rendered window.
MARKET_CLOSURE_LABELS = {
    "2026-06-19": "端午休假",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _date_text(value: Any) -> str:
    text = _text(value)[:10]
    try:
        return date.fromisoformat(text).isoformat()
    except (TypeError, ValueError):
        return ""


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _stock_code(value: Any) -> str:
    text = _text(value).split(".", 1)[0]
    digits = "".join(character for character in text if character.isdigit())
    return digits.zfill(6) if digits else ""


def _calendar_base(*, mode: str, requested_count: int) -> dict[str, Any]:
    return {
        "schema": CALENDAR_SCHEMA,
        "status": "ready",
        "mode": _text(mode) or "frozen",
        "requested_count": max(int(requested_count or DEFAULT_RECORD_COUNT), 1),
        "record_count": 0,
        "report_date_start": "",
        "report_date_end": "",
        "execution_date_start": "",
        "execution_date_end": "",
        "source": "postgresql.strategy_performance_ledger",
        "return_basis": "account_intraday_open_to_close_two_day_1x",
        "missing_fields": [],
        "calendar_notes": [],
        "records": [],
        "summary": {
            "valid_count": 0,
            "plan_target_count": 0,
            "holding_count": 0,
            "target_count": 0,
            "empty_count": 0,
            "no_new_entry_count": 0,
            "incomplete_count": 0,
            "future_count": 0,
            "outperform_count": 0,
            "average_daily_return_pct": None,
            "average_excess_shanghai_pct": None,
            "cumulative_daily_return_pct": None,
            "cumulative_shanghai_return_pct": None,
            "cumulative_excess_shanghai_pct": None,
        },
        "cumulative_returns": {
            "rolling_25": {
                "coverage_status": "source_incomplete",
                "valid_count": 0,
                "cumulative_daily_return_pct": None,
            },
            "current_month": {
                "coverage_status": "source_incomplete",
                "period_start": "",
                "valid_count": 0,
                "cumulative_daily_return_pct": None,
            },
            "since_start": {
                "coverage_status": "source_incomplete",
                "period_start": CUMULATIVE_RETURN_START_DATE,
                "valid_count": 0,
                "cumulative_daily_return_pct": None,
            },
        },
    }


def empty_tomorrow_action_calendar(
    *,
    mode: str = "frozen",
    requested_count: int = DEFAULT_RECORD_COUNT,
    missing_fields: Iterable[str] = (),
) -> dict[str, Any]:
    payload = _calendar_base(mode=mode, requested_count=requested_count)
    payload["status"] = "source_incomplete"
    payload["missing_fields"] = list(
        dict.fromkeys(_text(field) for field in missing_fields if _text(field))
    )
    return payload


def _normalized_index_bars(
    index_bars: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    by_date: dict[str, list[tuple[float | None, float | None]]] = {}
    for raw in index_bars or []:
        row = raw if isinstance(raw, Mapping) else {}
        trade_date = _date_text(row.get("date") or row.get("trade_date"))
        open_price = _optional_float(row.get("open"))
        close_price = _optional_float(row.get("close"))
        if not trade_date:
            continue
        normalized_open = open_price if open_price is not None and open_price > 0 else None
        normalized_close = close_price if close_price is not None and close_price > 0 else None
        by_date.setdefault(trade_date, []).append((normalized_open, normalized_close))
    normalized = []
    for trade_date in sorted(by_date):
        price_pairs = by_date[trade_date]
        conflict = any(pair != price_pairs[0] for pair in price_pairs[1:])
        open_price, close_price = price_pairs[0] if not conflict else (None, None)
        normalized.append(
            {
                "date": trade_date,
                "open": open_price,
                "close": close_price,
                "conflict": conflict,
            }
        )
    return normalized


def _next_trade_date(after_date: str, trade_dates: Iterable[str]) -> str:
    candidates = [trade_date for trade_date in trade_dates if trade_date > after_date]
    if not candidates:
        return ""
    candidate = min(candidates)
    try:
        gap_days = (date.fromisoformat(candidate) - date.fromisoformat(after_date)).days
    except ValueError:
        return ""
    return candidate if 0 < gap_days <= MAX_NEXT_TRADE_DATE_GAP_DAYS else ""


def _classify_plan(record: Mapping[str, Any]) -> tuple[str, str, str, str, list[str]]:
    stock_name = _text(record.get("stock_name"))
    stock_code = _stock_code(record.get("stock_code"))
    action_type = _text(record.get("action_type")).lower()
    if record.get("tomorrow_account_empty") is True:
        return "empty", "空仓", "", "", []
    if action_type in {"no_trade", "watch_only", "observe", "wait"} or record.get("can_new_entry") is False:
        return "no_new_entry", "不新增", "", "", []
    if action_type == "execute" and (stock_name or stock_code):
        label = f"{stock_name}({stock_code})" if stock_name and stock_code else stock_name or stock_code
        return "target", label, stock_code, stock_name, []
    return "incomplete", "事实不足", "", "", ["tomorrow_action"]


def _intraday_return(open_price: Any, close_price: Any) -> float | None:
    normalized_open = _optional_float(open_price)
    normalized_close = _optional_float(close_price)
    if (
        normalized_open is None
        or normalized_open <= 0
        or normalized_close is None
        or normalized_close <= 0
    ):
        return None
    return (normalized_close / normalized_open - 1.0) * 100.0


def _benchmark_return(index_bars: list[dict[str, Any]], execution_date: str) -> float | None:
    row = next((item for item in index_bars if item.get("date") == execution_date), None)
    if not row:
        return None
    return _intraday_return(row.get("open"), row.get("close"))


def _stock_intraday_returns(
    stock_quote_loader: Callable[[str, list[str]], Iterable[Mapping[str, Any]]],
    execution_date: str,
    stock_codes: Iterable[str],
) -> dict[str, float]:
    requested_codes = sorted({_stock_code(code) for code in stock_codes if _stock_code(code)})
    if not requested_codes:
        return {}
    try:
        rows = stock_quote_loader(execution_date, requested_codes) or []
    except Exception:
        return {}
    matches: dict[str, list[float]] = {code: [] for code in requested_codes}
    for raw in rows:
        row = raw if isinstance(raw, Mapping) else {}
        row_date = _date_text(row.get("trade_date") or row.get("date"))
        row_code = _stock_code(row.get("stock_code") or row.get("code") or row.get("ts_code"))
        if row_date != execution_date or row_code not in matches:
            continue
        stock_return = _intraday_return(row.get("open"), row.get("close"))
        if stock_return is None:
            matches[row_code].append(float("nan"))
        else:
            matches[row_code].append(stock_return)
    result = {}
    for code, values in matches.items():
        if not values or any(not math.isfinite(value) for value in values):
            continue
        if any(abs(value - values[0]) > 1e-9 for value in values[1:]):
            continue
        result[code] = values[0]
    return result


def _action_items(active_legs: list[dict[str, Any]]) -> list[dict[str, str]]:
    grouped: dict[str, dict[str, Any]] = {}
    for leg in active_legs:
        stock_code = _text(leg.get("stock_code"))
        stock_name = _text(leg.get("stock_name"))
        key = stock_code or f"name:{stock_name}"
        group = grouped.setdefault(
            key,
            {
                "stock_code": stock_code,
                "stock_name": stock_name,
                "holding_days": [],
                "plan_report_dates": [],
                "leg_count": 0,
            },
        )
        if stock_name:
            group["stock_name"] = stock_name
        group["leg_count"] += 1
        group["holding_days"].append(int(leg.get("holding_day") or 0))
        plan_report_date = _date_text(leg.get("plan_report_date"))
        if plan_report_date:
            group["plan_report_dates"].append(plan_report_date)
    items = []
    for group in grouped.values():
        stock_name = group["stock_name"]
        stock_code = group["stock_code"]
        label = f"{stock_name}({stock_code})" if stock_name and stock_code else stock_name or stock_code
        leg_count = int(group["leg_count"])
        holding_days = "+".join(str(day) for day in sorted(set(group["holding_days"])))
        items.append(
            {
                "label": label,
                "position_label": f"{leg_count}x/{int(leg_count * LEG_WEIGHT_PCT)}%",
                "holding_label": f"第{holding_days}日",
                "plan_date_label": "/".join(sorted(set(group["plan_report_dates"]))),
            }
        )
    return items


def _build_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    complete = [record for record in records if record.get("performance_status") == "complete"]
    daily_returns = [float(record["daily_return_pct"]) for record in complete]
    shanghai_returns = [float(record["shanghai_return_pct"]) for record in complete]
    excess_returns = [float(record["excess_shanghai_pct"]) for record in complete]
    cumulative_daily = None
    cumulative_shanghai = None
    cumulative_excess = None
    if complete:
        daily_nav = 1.0
        shanghai_nav = 1.0
        for daily_return, shanghai_return in zip(daily_returns, shanghai_returns):
            daily_nav *= 1.0 + daily_return / 100.0
            shanghai_nav *= 1.0 + shanghai_return / 100.0
        cumulative_daily = (daily_nav - 1.0) * 100.0
        cumulative_shanghai = (shanghai_nav - 1.0) * 100.0
        cumulative_excess = cumulative_daily - cumulative_shanghai
    return {
        "valid_count": len(complete),
        "plan_target_count": sum(record.get("plan_action_kind") == "target" for record in records),
        "holding_count": sum(record.get("action_kind") == "target" for record in records),
        # Compatibility alias for early calendar payload consumers.
        "target_count": sum(record.get("action_kind") == "target" for record in records),
        "empty_count": sum(record.get("action_kind") == "empty" for record in records),
        "no_new_entry_count": sum(record.get("plan_action_kind") == "no_new_entry" for record in records),
        "incomplete_count": sum(record.get("performance_status") == "incomplete" for record in records),
        "future_count": sum(record.get("performance_status") == "future" for record in records),
        "outperform_count": sum(value > 0 for value in excess_returns),
        "average_daily_return_pct": sum(daily_returns) / len(daily_returns) if daily_returns else None,
        "average_excess_shanghai_pct": sum(excess_returns) / len(excess_returns) if excess_returns else None,
        "cumulative_daily_return_pct": cumulative_daily,
        "cumulative_shanghai_return_pct": cumulative_shanghai,
        "cumulative_excess_shanghai_pct": cumulative_excess,
    }


def _build_cumulative_return_scope(
    records: Iterable[Mapping[str, Any]],
    *,
    period_start: str = "",
    period_end: str = "",
    expected_trade_dates: Iterable[str] = (),
) -> dict[str, Any]:
    normalized_records = [record for record in records if isinstance(record, Mapping)]
    complete = [
        record
        for record in normalized_records
        if record.get("performance_status") == "complete"
        and (daily_return := _optional_float(record.get("daily_return_pct"))) is not None
        and (not period_start or _date_text(record.get("execution_date")) >= period_start)
        and (not period_end or _date_text(record.get("execution_date")) <= period_end)
    ]
    daily_nav = 1.0
    for record in complete:
        daily_nav *= 1.0 + float(record["daily_return_pct"]) / 100.0
    available_dates = {
        execution_date
        for record in normalized_records
        if (execution_date := _date_text(record.get("execution_date")))
        and (not period_start or execution_date >= period_start)
        and (not period_end or execution_date <= period_end)
    }
    expected_dates = {
        trade_date
        for raw_date in expected_trade_dates
        if (trade_date := _date_text(raw_date))
        and (not period_start or trade_date >= period_start)
        and (not period_end or trade_date <= period_end)
    }
    missing_execution_dates = sorted(expected_dates - available_dates)
    coverage_status = "complete" if not missing_execution_dates else "source_incomplete"
    if period_start and period_end and period_start > period_end:
        coverage_status = "not_started"
    return {
        "period_start": period_start,
        "period_end": period_end,
        "coverage_status": coverage_status,
        "missing_execution_dates": missing_execution_dates,
        "valid_count": len(complete),
        "cumulative_daily_return_pct": (daily_nav - 1.0) * 100.0 if complete else None,
    }


def build_tomorrow_action_calendar(
    *,
    target_report_date: str,
    mode: str,
    ledger: Mapping[str, Any] | None,
    index_bars: Iterable[Mapping[str, Any]],
    stock_quote_loader: Callable[[str, list[str]], Iterable[Mapping[str, Any]]],
    future_open_dates: Iterable[str] = (),
    requested_count: int = DEFAULT_RECORD_COUNT,
) -> dict[str, Any]:
    target_report_date = _date_text(target_report_date)
    normalized_mode = _text(mode) or "frozen"
    payload = _calendar_base(mode=normalized_mode, requested_count=requested_count)
    if not target_report_date:
        return empty_tomorrow_action_calendar(
            mode=normalized_mode,
            requested_count=requested_count,
            missing_fields=("target_report_date",),
        )
    ledger = ledger if isinstance(ledger, Mapping) else {}
    ledger_mode = _text(ledger.get("mode"))
    if ledger_mode and ledger_mode != normalized_mode:
        return empty_tomorrow_action_calendar(
            mode=normalized_mode,
            requested_count=requested_count,
            missing_fields=("ledger_mode",),
        )

    eligible_by_date = {}
    for raw in ledger.get("records") or []:
        record = raw if isinstance(raw, Mapping) else {}
        report_date = _date_text(record.get("report_date"))
        if report_date and report_date <= target_report_date:
            eligible_by_date[report_date] = record
    all_eligible_records = sorted(eligible_by_date.items())
    context_records = all_eligible_records

    normalized_bars = _normalized_index_bars(index_bars)
    index_dates = [row["date"] for row in normalized_bars]
    normalized_future_dates = sorted(
        {
            normalized
            for raw_date in future_open_dates or []
            if (normalized := _date_text(raw_date))
        }
    )
    trade_dates = sorted(set(index_dates + normalized_future_dates))

    plans = []
    for report_date, source_record in context_records:
        plan_kind, plan_label, stock_code, stock_name, missing_fields = _classify_plan(source_record)
        execution_date = _next_trade_date(report_date, trade_dates)
        plans.append(
            {
                "report_date": report_date,
                "execution_date": execution_date,
                "second_execution_date": (
                    _next_trade_date(execution_date, trade_dates)
                    if execution_date and plan_kind == "target"
                    else ""
                ),
                "plan_action_kind": plan_kind,
                "plan_action_label": plan_label,
                "stock_code": stock_code,
                "stock_name": stock_name,
                "missing_fields": missing_fields,
            }
        )
    plans_by_report_date = {plan["report_date"]: plan for plan in plans}

    calculated_records = []
    for report_date, _source_record in all_eligible_records:
        current_plan = plans_by_report_date[report_date]
        execution_date = current_plan["execution_date"]
        plan_kind = current_plan["plan_action_kind"]
        missing_fields = list(current_plan["missing_fields"])
        active_legs = []
        if execution_date and plan_kind != "empty":
            for plan in plans:
                if plan.get("plan_action_kind") != "target":
                    continue
                holding_day = (
                    1
                    if plan.get("execution_date") == execution_date
                    else 2
                    if plan.get("second_execution_date") == execution_date
                    else 0
                )
                if not holding_day:
                    continue
                active_legs.append(
                    {
                        "plan_report_date": plan["report_date"],
                        "stock_code": plan["stock_code"],
                        "stock_name": plan["stock_name"],
                        "holding_day": holding_day,
                        "position_x": LEG_POSITION_X,
                        "weight_pct": LEG_WEIGHT_PCT,
                        "stock_return_pct": None,
                        "contribution_pct": None,
                    }
                )

        position_limit_exceeded = len(active_legs) > 2
        if plan_kind == "empty":
            action_kind = "empty"
            action_label = "空仓"
        elif plan_kind == "incomplete" or position_limit_exceeded or not execution_date:
            action_kind = "incomplete"
            action_label = "事实不足"
        elif active_legs:
            action_kind = "target"
            action_label = "；".join(item["label"] for item in _action_items(active_legs))
        else:
            action_kind = "empty"
            action_label = "空仓"

        performance_status = "incomplete"
        daily_return_pct = None
        shanghai_return_pct = None
        excess_shanghai_pct = None
        if not execution_date:
            missing_fields.append("execution_date")
        elif execution_date > target_report_date:
            performance_status = "future"
        elif plan_kind == "incomplete":
            pass
        elif position_limit_exceeded:
            missing_fields.append("account_position_limit")
        else:
            shanghai_return_pct = _benchmark_return(normalized_bars, execution_date)
            if shanghai_return_pct is None:
                missing_fields.append("shanghai_intraday_return")
            if active_legs:
                stock_returns = _stock_intraday_returns(
                    stock_quote_loader,
                    execution_date,
                    [leg["stock_code"] for leg in active_legs],
                )
                for leg in active_legs:
                    stock_return = stock_returns.get(leg["stock_code"])
                    if stock_return is None:
                        continue
                    contribution = stock_return * leg["weight_pct"] / 100.0
                    leg["stock_return_pct"] = stock_return
                    leg["contribution_pct"] = contribution
                if any(leg["stock_return_pct"] is None for leg in active_legs):
                    missing_fields.append("stock_intraday_return")
                else:
                    daily_return_pct = sum(float(leg["contribution_pct"]) for leg in active_legs)
            else:
                daily_return_pct = 0.0
            if daily_return_pct is not None and shanghai_return_pct is not None:
                excess_shanghai_pct = daily_return_pct - shanghai_return_pct
                performance_status = "complete"

        weekday_label = ""
        if execution_date:
            weekday_label = WEEKDAY_LABELS[date.fromisoformat(execution_date).weekday()]
        calculated_records.append(
            {
                "report_date": report_date,
                "execution_date": execution_date,
                "weekday_label": weekday_label,
                "action_kind": action_kind,
                "action_label": action_label,
                "action_items": [] if position_limit_exceeded else _action_items(active_legs),
                "plan_action_kind": plan_kind,
                "plan_action_label": current_plan["plan_action_label"],
                "stock_code": current_plan["stock_code"],
                "stock_name": current_plan["stock_name"],
                "active_legs": active_legs,
                "total_position_pct": None if position_limit_exceeded else len(active_legs) * LEG_WEIGHT_PCT,
                "daily_return_pct": daily_return_pct,
                "shanghai_return_pct": shanghai_return_pct,
                "excess_shanghai_pct": excess_shanghai_pct,
                "performance_status": performance_status,
                "missing_fields": list(dict.fromkeys(missing_fields)),
            }
        )

    records = calculated_records[-payload["requested_count"] :]
    payload["records"] = records
    payload["record_count"] = len(records)
    if records:
        payload["report_date_start"] = records[0]["report_date"]
        payload["report_date_end"] = records[-1]["report_date"]
    execution_dates = [record["execution_date"] for record in records if record.get("execution_date")]
    if execution_dates:
        payload["execution_date_start"] = min(execution_dates)
        payload["execution_date_end"] = max(execution_dates)
        first_weekday = date.fromisoformat(min(execution_dates))
        first_weekday -= timedelta(days=first_weekday.weekday())
        last_weekday = date.fromisoformat(max(execution_dates))
        last_weekday += timedelta(days=4 - last_weekday.weekday())
        payload["calendar_notes"] = [
            {
                "date": closure_date,
                "weekday_label": WEEKDAY_LABELS[date.fromisoformat(closure_date).weekday()],
                "kind": "holiday",
                "label": closure_label,
                "source": "market_holiday_schedule",
            }
            for closure_date, closure_label in MARKET_CLOSURE_LABELS.items()
            if first_weekday <= date.fromisoformat(closure_date) <= last_weekday
            and closure_date not in trade_dates
        ]
    payload["summary"] = _build_summary(records)
    current_month_start = f"{target_report_date[:7]}-01"
    payload["cumulative_returns"] = {
        "rolling_25": _build_cumulative_return_scope(
            records,
            period_end=target_report_date,
        ),
        "current_month": _build_cumulative_return_scope(
            calculated_records,
            period_start=current_month_start,
            period_end=target_report_date,
            expected_trade_dates=index_dates,
        ),
        "since_start": _build_cumulative_return_scope(
            calculated_records,
            period_start=CUMULATIVE_RETURN_START_DATE,
            period_end=target_report_date,
            expected_trade_dates=index_dates,
        ),
    }
    if not records:
        payload["status"] = "source_incomplete"
        payload["missing_fields"] = ["tomorrow_action_history"]
    return payload


def build_tomorrow_action_calendar_from_service(
    *,
    target_report_date: str,
    mode: str,
    service: Any,
    future_open_dates: Iterable[str] = (),
    requested_count: int = DEFAULT_RECORD_COUNT,
) -> dict[str, Any]:
    if service is None:
        return empty_tomorrow_action_calendar(
            mode=mode,
            requested_count=requested_count,
            missing_fields=("postgresql",),
        )
    try:
        normalized_target_date = _date_text(target_report_date)
        normalized_count = max(int(requested_count or DEFAULT_RECORD_COUNT), 1)
        target_date = date.fromisoformat(normalized_target_date)
        month_start = target_date.replace(day=1)
        fixed_start = date.fromisoformat(CUMULATIVE_RETURN_START_DATE)
        earliest_scope_start = min(month_start, fixed_start) if target_date >= fixed_start else month_start
        history_limit = max(
            normalized_count + 1,
            (target_date - earliest_scope_start).days + 3,
        )
        history_reader = getattr(service, "query_tomorrow_action_history", None)
        history_records = (
            history_reader(normalized_target_date, mode=mode, limit=history_limit)
            if callable(history_reader)
            else []
        )
        if history_records:
            ledger = {"mode": mode, "records": history_records}
            source = "postgresql.strategy_factor_snapshot_fields"
        else:
            ledger = service.load_strategy_performance_ledger(mode=mode)
            source = "postgresql.strategy_performance_ledger"
        eligible_dates = sorted(
            report_date
            for raw in (ledger.get("records") or [])
            if isinstance(raw, Mapping)
            and (report_date := _date_text(raw.get("report_date")))
            and report_date <= normalized_target_date
        )
        query_end_date = (
            date.fromisoformat(normalized_target_date) + timedelta(days=MAX_NEXT_TRADE_DATE_GAP_DAYS)
        ).isoformat()
        earliest_date = (
            date.fromisoformat(eligible_dates[0])
            if eligible_dates
            else date.fromisoformat(normalized_target_date)
        )
        query_window = max(
            (date.fromisoformat(query_end_date) - earliest_date).days + 2,
            normalized_count * 4,
            120,
        )
        index_bars = service.query_index_daily_bars(
            "sh.000001",
            query_end_date,
            window_days=query_window,
        )
    except Exception:
        return empty_tomorrow_action_calendar(
            mode=mode,
            requested_count=requested_count,
            missing_fields=("postgresql",),
        )
    payload = build_tomorrow_action_calendar(
        target_report_date=target_report_date,
        mode=mode,
        ledger=ledger,
        index_bars=index_bars,
        stock_quote_loader=service.query_stock_daily_quotes_recent,
        future_open_dates=future_open_dates,
        requested_count=requested_count,
    )
    payload["source"] = source
    return payload
