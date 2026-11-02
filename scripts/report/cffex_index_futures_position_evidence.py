"""Build and render the target-date CFFEX index-futures evidence surface.

This module deliberately has no dependency on candidate selection or account
execution.  It consumes the two dedicated CFFEX fact tables and returns a
compact, source-hashed payload that can be attached after the formal action.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import math
from collections import defaultdict
from copy import deepcopy
from typing import Any, Callable, Iterable, Mapping

from market_data.cffex_index_futures import (
    CFFEX_PRODUCTS,
    CFFEX_SOURCE_POLICY,
    CFFEX_SPOT_INDEX_CODES,
    CffexDataError,
    assess_cffex_day_scope,
    build_contract_market_context,
    build_history_windows,
    build_member_position_summary,
    build_top20_structure,
    normalize_contract_daily_record,
    normalize_member_rank_record,
    normalize_trade_date,
)


SCHEMA_VERSION = "cffex_index_futures_position_evidence.v1"
SOURCE_POLICY = CFFEX_SOURCE_POLICY


def normalize_cffex_position_trend_payload(
    value: Mapping[str, object] | None,
    trade_date: str,
    *,
    limit: int = 60,
) -> dict[str, object]:
    """Project validated CFFEX facts for charts without loading the report renderer."""
    if not isinstance(value, Mapping):
        return {}
    target_date = str(trade_date or "").strip()[:10]
    try:
        target_date = _dt.date.fromisoformat(target_date).isoformat()
    except ValueError:
        return {}
    if (
        value.get("schema_version") != SCHEMA_VERSION
        or str(value.get("target_date") or "") != target_date
        or str(value.get("source_date") or "") != target_date
    ):
        return {}
    history = value.get("history")
    windows = history.get("windows") if isinstance(history, Mapping) else None
    if not isinstance(windows, Mapping):
        return {}

    metric_fields = {
        "member_net_short_change": "member_net_short_change",
        "member_net_short_notional": "member_net_short_notional_yi",
        "top20_cross_section_net_short": "top20_cross_section_net_short",
    }
    values_by_metric: dict[str, dict[str, float | None]] = {}
    observed_dates: set[str] = set()
    for metric, output_field in metric_fields.items():
        metric_windows = windows.get(metric)
        if not isinstance(metric_windows, Mapping):
            values_by_metric[output_field] = {}
            continue
        window = metric_windows.get("60") or metric_windows.get("20")
        raw_values = window.get("values") if isinstance(window, Mapping) else None
        if not isinstance(raw_values, list):
            values_by_metric[output_field] = {}
            continue
        metric_values: dict[str, float | None] = {}
        for raw_item in raw_values:
            if not isinstance(raw_item, Mapping):
                continue
            item_date = str(raw_item.get("trade_date") or "").strip()[:10]
            try:
                item_date = _dt.date.fromisoformat(item_date).isoformat()
            except ValueError:
                continue
            if item_date > target_date:
                continue
            try:
                number = float(raw_item.get("value"))
            except (TypeError, ValueError):
                number = None
            if number is not None and not math.isfinite(number):
                number = None
            if item_date in metric_values and metric_values[item_date] != number:
                return {}
            metric_values[item_date] = number
            observed_dates.add(item_date)
        values_by_metric[output_field] = metric_values

    try:
        history_limit = max(int(limit or 60), 1)
    except (TypeError, ValueError):
        history_limit = 60
    ordered_dates = sorted(observed_dates)[-history_limit:]
    items: list[dict[str, object]] = []
    previous_top20: float | None = None
    for item_date in ordered_dates:
        member_change = values_by_metric["member_net_short_change"].get(item_date)
        member_notional = values_by_metric["member_net_short_notional_yi"].get(item_date)
        top20_balance = values_by_metric["top20_cross_section_net_short"].get(item_date)
        top20_change = (
            top20_balance - previous_top20
            if top20_balance is not None and previous_top20 is not None
            else None
        )
        items.append(
            {
                "date": item_date,
                "member_net_short_notional_yi": (
                    member_notional / 100_000_000
                    if member_notional is not None
                    else None
                ),
                "member_net_short_change": member_change,
                "top20_cross_section_net_short": top20_balance,
                "top20_cross_section_change": top20_change,
            }
        )
        previous_top20 = top20_balance
    if not any(
        item.get(field) is not None
        for item in items
        for field in (
            "member_net_short_notional_yi",
            "member_net_short_change",
            "top20_cross_section_net_short",
        )
    ):
        return {}
    return {
        "schema": "cffex_position_trend.v1",
        "target_date": target_date,
        "default_window": min(60, len(items)),
        "max_window": min(history_limit, len(items)),
        "items": items,
        "title": "股指期货净空结构趋势",
        "subtitle": (
            "名义金额、会员日变和前20榜单差额分面展示；"
            "榜单跨日变化包含会员或披露范围变化，不等于新增空单。"
        ),
    }


def canonical_cffex_evidence_hash(payload: Any) -> str:
    """Return a stable hash for a payload, excluding its self-hash field."""

    value = deepcopy(payload) if isinstance(payload, dict) else {}
    value.pop("artifact_hash", None)
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_cffex_evidence(payload: Any, *, target_date: Any) -> tuple[bool, list[str]]:
    """Validate provenance and reproducible semantics before rendering."""

    errors: list[str] = []
    if not isinstance(payload, Mapping):
        return False, ["cffex_evidence_type_invalid"]
    target = _safe_date(target_date)
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("cffex_evidence_schema_invalid")
    if not target or payload.get("target_date") != target:
        errors.append("cffex_evidence_target_date_mismatch")
    if payload.get("source_date") != target:
        errors.append("cffex_evidence_source_date_mismatch")
    query_date = payload.get("query_date")
    normalized_query_date = _safe_date(query_date) if query_date else ""
    if not query_date:
        errors.append("cffex_evidence_query_date_missing")
    elif not normalized_query_date:
        errors.append("cffex_evidence_query_date_invalid")
    elif normalized_query_date and target and normalized_query_date < target:
        errors.append("cffex_evidence_query_date_before_target")
    source_policy = str(payload.get("source_policy") or "").strip()
    if source_policy != SOURCE_POLICY:
        errors.append("cffex_evidence_source_policy_invalid")
    stored_hash = str(payload.get("artifact_hash") or "").strip().lower()
    if len(stored_hash) != 64 or stored_hash != canonical_cffex_evidence_hash(payload):
        errors.append("cffex_evidence_hash_mismatch")
    products = payload.get("products")
    if not isinstance(products, Mapping):
        products = {}
        errors.append("cffex_evidence_products_invalid")
    for product in CFFEX_PRODUCTS:
        item = products.get(product)
        if not isinstance(item, Mapping):
            errors.append(f"cffex_evidence_product_missing:{product}")
            continue
        if item.get("trade_date") != target:
            errors.append(f"cffex_evidence_product_date_mismatch:{product}")
    raw_target = payload.get("raw_target_day") or {}
    raw_contracts, contract_errors = _normalize_rows(
        raw_target.get("contract_rows"), target, kind="contract", target_only=True
    )
    raw_ranks, rank_errors = _normalize_rows(
        raw_target.get("member_rank_rows"), target, kind="rank", target_only=True
    )
    if contract_errors:
        errors.append("cffex_evidence_contract_rows_invalid")
    if rank_errors:
        errors.append("cffex_evidence_rank_rows_invalid")
    availability = str(payload.get("availability") or "")
    scope = assess_cffex_day_scope(
        raw_contracts,
        raw_ranks,
        expected_trade_date=target or payload.get("target_date"),
        expected_products=CFFEX_PRODUCTS,
    ) if target else {"integrity_errors": ["target_date_invalid"], "complete": False}
    if scope.get("integrity_errors"):
        errors.append("cffex_evidence_raw_scope_invalid")
    if availability == "complete" and not scope.get("complete"):
        errors.append("cffex_evidence_complete_scope_invalid")
    raw_sources = {
        (str(row.get("source_url") or ""), str(row.get("content_hash") or ""))
        for row in [*raw_contracts, *raw_ranks]
    }
    declared_sources = set()
    for item in payload.get("source_files") or []:
        if not isinstance(item, Mapping):
            errors.append("cffex_evidence_source_file_invalid")
            continue
        if item.get("source_date") != target:
            errors.append("cffex_evidence_source_file_date_mismatch")
        key = (str(item.get("source_url") or ""), str(item.get("content_hash") or ""))
        declared_sources.add(key)
    if raw_sources != declared_sources:
        errors.append("cffex_evidence_source_files_mismatch")
    if target:
        expected_source_files = _source_files(raw_contracts, raw_ranks, target)
        if not _values_equal(payload.get("source_files") or [], expected_source_files):
            errors.append("cffex_evidence_source_files_projection_mismatch")
        errors.extend(
            _validate_product_projections(
                products,
                raw_contracts,
                raw_ranks,
                target,
                availability=availability,
            )
        )
        errors.extend(
            _validate_member_and_top20_projections(
                payload,
                raw_contracts,
                raw_ranks,
                availability=availability,
            )
        )
        errors.extend(
            _validate_history_projection(
                payload.get("history"),
                target,
                availability=availability,
            )
        )
        calendar = (payload.get('history') or {}).get('calendar') or {}
        if calendar.get('verified') is True:
            days = calendar.get('trade_dates') or []
            previous = days[-2] if len(days) > 1 else None
            scopes = {'overall': (payload.get('top20') or {}).get('overall') or {},
                      **{product: (products.get(product) or {}).get('top20') or {} for product in CFFEX_PRODUCTS}}
            for scope, item in scopes.items():
                comparison_date = item.get('previous_trade_date')
                if comparison_date != previous or previous is None:
                    if (comparison_date is not None or any(item.get(key) is not None for key in (
                            'previous_top20_cross_section_net_short', 'top20_cross_section_change',
                            'membership_scope_residual', 'membership_changes'))
                            or item.get('comparison_availability') == 'complete'):
                        errors.append(f'cffex_evidence_previous_session_mismatch:{scope}')
    return not errors, errors


_TOP20_CURRENT_KEYS = (
    "long_quantity",
    "short_quantity",
    "top20_cross_section_net_short",
    "long_daily_change",
    "short_daily_change",
    "listed_member_daily_change_net",
    "long_member_count",
    "short_member_count",
    "contract_count",
    "availability",
)


def _validate_product_projections(products, raw_contracts, raw_ranks, target, *, availability):
    errors = []
    expected_product_payloads = {}
    for product in CFFEX_PRODUCTS:
        item = products.get(product)
        if not isinstance(item, Mapping):
            continue
        nested_contracts, contract_errors = _normalize_rows(
            item.get("contract_rows"), target, kind="contract", target_only=True
        )
        nested_ranks, rank_errors = _normalize_rows(
            item.get("member_rank_rows"), target, kind="rank", target_only=True
        )
        if contract_errors or rank_errors:
            errors.append(f"cffex_evidence_product_rows_invalid:{product}")
        expected_contracts = [
            row for row in raw_contracts if str(row.get("product_code") or "") == product
        ]
        expected_ranks = [
            row for row in raw_ranks if str(row.get("product_code") or "") == product
        ]
        if not _rows_equal(nested_contracts, expected_contracts):
            errors.append(f"cffex_evidence_product_contract_rows_mismatch:{product}")
        if not _rows_equal(nested_ranks, expected_ranks):
            errors.append(f"cffex_evidence_product_rank_rows_mismatch:{product}")
        if item.get("contract_count") != len(expected_contracts):
            errors.append(f"cffex_evidence_product_contract_count_mismatch:{product}")
        if item.get("rank_row_count") != len(expected_ranks):
            errors.append(f"cffex_evidence_product_rank_count_mismatch:{product}")
        reasons = _product_missing_reasons(
            product,
            expected_contracts,
            expected_ranks,
            target,
        )
        expected_product_availability = _product_availability(
            reasons,
            expected_contracts,
            expected_ranks,
        )
        if item.get("availability") != expected_product_availability:
            errors.append(f"cffex_evidence_product_availability_mismatch:{product}")
        if expected_product_availability != "unavailable" and not _values_equal(
            item.get("missing_reasons") or [],
            reasons,
        ):
            errors.append(f"cffex_evidence_product_missing_reasons_mismatch:{product}")
        expected_product_payloads[product] = {
            "availability": expected_product_availability,
        }
        if expected_product_availability == "unavailable":
            continue
        member = build_member_position_summary(expected_ranks, expected_contracts)
        expected_member = member.get("products", {}).get(product) or _empty_summary()
        if not _values_equal(item.get("member_position") or {}, expected_member):
            errors.append(f"cffex_evidence_product_member_projection_mismatch:{product}")
        expected_top20 = (
            build_top20_structure(expected_ranks, None).get("products", {}).get(product)
            or {}
        )
        if not _top20_current_projection_equal(item.get("top20"), expected_top20):
            errors.append(f"cffex_evidence_product_top20_projection_mismatch:{product}")
        errors.extend(_validate_top20_equations(item.get("top20"), suffix=product))
    expected_overall = _overall_availability(
        expected_product_payloads,
        raw_contracts,
        raw_ranks,
    )
    if availability != expected_overall:
        errors.append("cffex_evidence_availability_projection_mismatch")
    return errors


def _validate_member_and_top20_projections(payload, raw_contracts, raw_ranks, *, availability):
    if availability == "unavailable":
        return []
    errors = []
    member = build_member_position_summary(raw_ranks, raw_contracts)
    expected_member = {
        "member_name": member.get("member_name", "中信期货"),
        "official_member_names": member.get("official_member_names", []),
        "overall": member.get("overall") or _empty_summary(include_share=False),
        "products": member.get("products") or {},
        "included_contracts": member.get("included_contracts", []),
        "excluded_contracts": member.get("excluded_contracts", []),
    }
    if not _values_equal(payload.get("member_position") or {}, expected_member):
        errors.append("cffex_evidence_member_projection_mismatch")
    expected_top20 = build_top20_structure(raw_ranks, None)
    top20 = payload.get("top20")
    if not isinstance(top20, Mapping):
        return [*errors, "cffex_evidence_top20_invalid"]
    if not _top20_current_projection_equal(
        top20.get("overall"), expected_top20.get("overall") or {}
    ):
        errors.append("cffex_evidence_top20_projection_mismatch")
    errors.extend(_validate_top20_equations(top20.get("overall"), suffix="overall"))
    declared_products = top20.get("products")
    for product in CFFEX_PRODUCTS:
        declared = declared_products.get(product) if isinstance(declared_products, Mapping) else None
        embedded = (payload.get("products") or {}).get(product, {}).get("top20")
        if not _values_equal(declared or {}, embedded or {}):
            errors.append(f"cffex_evidence_top20_product_copy_mismatch:{product}")
    return errors


def _top20_current_projection_equal(actual, expected):
    if not isinstance(actual, Mapping) or not isinstance(expected, Mapping):
        return False
    return all(_values_equal(actual.get(key), expected.get(key)) for key in _TOP20_CURRENT_KEYS)


def _validate_top20_equations(value, *, suffix):
    if not isinstance(value, Mapping):
        return [f"cffex_evidence_top20_invalid:{suffix}"]
    errors = []
    current = value.get("top20_cross_section_net_short")
    previous = value.get("previous_top20_cross_section_net_short")
    change = value.get("top20_cross_section_change")
    listed = value.get("listed_member_daily_change_net")
    residual = value.get("membership_scope_residual")
    expected_change = (
        _numeric_value(current) - _numeric_value(previous)
        if _numeric_value(current) is not None and _numeric_value(previous) is not None
        else None
    )
    if not _values_equal(change, expected_change):
        errors.append(f"cffex_evidence_top20_change_mismatch:{suffix}")
    expected_residual = (
        _numeric_value(change) - _numeric_value(listed)
        if _numeric_value(change) is not None and _numeric_value(listed) is not None
        else None
    )
    if not _values_equal(residual, expected_residual):
        errors.append(f"cffex_evidence_top20_residual_mismatch:{suffix}")
    membership_changes = value.get("membership_changes")
    contracts_changed = bool(
        isinstance(membership_changes, Mapping)
        and (
            membership_changes.get("contracts_entered")
            or membership_changes.get("contracts_exited")
        )
    )
    if contracts_changed and value.get("comparison_availability") == "complete":
        errors.append(f"cffex_evidence_top20_comparison_scope_mismatch:{suffix}")
    return errors


def _validate_history_projection(history, target, *, availability):
    if not isinstance(history, Mapping):
        return ["cffex_evidence_history_invalid"]
    errors = []
    raw_dates = history.get("trade_dates")
    if not isinstance(raw_dates, list):
        raw_dates = []
        errors.append("cffex_evidence_history_dates_invalid")
    dates = [_safe_date(value) for value in raw_dates]
    if any(not value or value > target for value in dates):
        errors.append("cffex_evidence_history_future_or_invalid_date")
    if dates != sorted(set(dates)):
        errors.append("cffex_evidence_history_date_order_invalid")
    if history.get("sample_count") != len(dates):
        errors.append("cffex_evidence_history_sample_count_mismatch")
    if history.get("start_date") != (dates[0] if dates else ""):
        errors.append("cffex_evidence_history_start_date_mismatch")
    if history.get("end_date") != (dates[-1] if dates else ""):
        errors.append("cffex_evidence_history_end_date_mismatch")
    calendar = history.get('calendar')
    calendar_dates = None
    if calendar is not None:
        calendar_dates = calendar.get('trade_dates') if isinstance(calendar, Mapping) else None
        if (not isinstance(calendar_dates, list) or not calendar_dates
                or calendar_dates != sorted(set(calendar_dates))
                or any(_safe_date(day) != day or day > target for day in calendar_dates)
                or calendar_dates[-1] != target or calendar.get('verified') is not True
                or not calendar.get('source')):
            return [*errors, 'cffex_evidence_history_calendar_invalid']
    expected_coverage = "missing" if availability == "unavailable" and not dates else (
        "complete" if len(dates) >= 60 else "partial"
    )
    if calendar_dates is not None:
        expected_coverage = ('complete' if len(calendar_dates) >= 60
                             and dates == calendar_dates[-60:] else 'partial')
    if history.get("coverage_status") != expected_coverage:
        errors.append("cffex_evidence_history_coverage_mismatch")
    windows = history.get("windows")
    if availability == "unavailable" and not dates and calendar_dates is None:
        if windows not in ({}, None):
            errors.append("cffex_evidence_history_windows_unexpected")
        return errors
    if not isinstance(windows, Mapping):
        return [*errors, "cffex_evidence_history_windows_invalid"]
    metric_dates: dict[str, set[str]] = {}
    for metric in (
        "member_net_short_change",
        "member_net_short_notional",
        "top20_cross_section_net_short",
    ):
        metric_windows = windows.get(metric)
        if not isinstance(metric_windows, Mapping):
            errors.append(f"cffex_evidence_history_metric_missing:{metric}")
            continue
        for window in (20, 60):
            item = metric_windows.get(str(window))
            item_errors, finite_dates = _validate_history_window(
                item,
                target,
                requested_window=window,
                metric=metric,
            )
            errors.extend(item_errors)
            if calendar_dates is not None and isinstance(item, Mapping):
                actual_dates = [row.get('trade_date') for row in item.get('values', [])]
                if actual_dates != calendar_dates[-window:]:
                    errors.append(f'cffex_evidence_history_calendar_projection_mismatch:{metric}:{window}')
            if window == 60:
                metric_dates[metric] = finite_dates
    if len(metric_dates) == 3:
        complete_dates = set.intersection(*metric_dates.values())
        if dates != sorted(complete_dates):
            errors.append("cffex_evidence_history_dates_projection_mismatch")
    return errors


def align_cffex_history_calendar(payload, trade_dates, *, calendar_source):
    """Use real sessions rather than substituting older recorded dates."""
    target = payload['target_date']
    valid, errors = validate_cffex_evidence(payload, target_date=target)
    if not valid:
        raise ValueError('期货原始事实未通过核对：' + ','.join(errors))
    metrics = ('member_net_short_change', 'member_net_short_notional',
               'top20_cross_section_net_short')
    summaries = {}
    for metric in metrics:
        for row in payload['history']['windows'].get(metric, {}).get('60', {}).get('values', []):
            summaries.setdefault(row['trade_date'], {'trade_date': row['trade_date']})[metric] = row['value']
    calendar = list(trade_dates)
    windows = {metric: build_history_windows(summaries.values(), target_date=target,
               value_key=metric, trade_dates=calendar) for metric in metrics}
    calendar = calendar[-60:]
    complete = [day for day in calendar if all(
        _numeric_value(summaries.get(day, {}).get(metric)) is not None for metric in metrics)]
    value = deepcopy(payload)
    value['history'] = {'trade_dates': complete, 'sample_count': len(complete),
        'start_date': complete[0] if complete else '', 'end_date': complete[-1] if complete else '',
        'windows': windows, 'coverage_status': 'complete' if len(complete) == 60 else 'partial',
        'calendar': {'trade_dates': calendar, 'verified': True, 'source': str(calendar_source)}}
    previous = calendar[-2] if len(calendar) > 1 else None
    without_comparison = build_top20_structure(value['raw_target_day']['member_rank_rows'])
    scopes = {'overall': value['top20']['overall'], **value['top20'].get('products', {})}
    for scope, item in scopes.items():
        if previous is None or item.get('previous_trade_date') != previous:
            # An older disclosed row is not evidence of the actual previous session.
            clean = without_comparison['overall'] if scope == 'overall' else without_comparison['products'][scope]
            for key in ('previous_top20_cross_section_net_short', 'top20_cross_section_change',
                        'membership_scope_residual', 'membership_changes', 'comparison_availability'):
                item[key] = clean[key]
            item['previous_trade_date'] = None
        if scope != 'overall':
            value['products'][scope]['top20'] = deepcopy(item)
    value['artifact_hash'] = canonical_cffex_evidence_hash(value)
    valid, errors = validate_cffex_evidence(value, target_date=target)
    if not valid:
        raise ValueError('期货交易日历对照未通过：' + ','.join(errors))
    return value


def _validate_history_window(item, target, *, requested_window, metric):
    suffix = f"{metric}:{requested_window}"
    if not isinstance(item, Mapping):
        return [f"cffex_evidence_history_window_missing:{suffix}"], set()
    errors = []
    if item.get("requested_window") != requested_window:
        errors.append(f"cffex_evidence_history_window_size_mismatch:{suffix}")
    values = item.get("values")
    if not isinstance(values, list):
        return [*errors, f"cffex_evidence_history_values_invalid:{suffix}"], set()
    value_dates = []
    finite_rows = []
    for row in values:
        if not isinstance(row, Mapping):
            errors.append(f"cffex_evidence_history_value_row_invalid:{suffix}")
            continue
        date = _safe_date(row.get("trade_date"))
        if not date or date > target:
            errors.append(f"cffex_evidence_history_value_date_invalid:{suffix}")
            continue
        value_dates.append(date)
        number = _numeric_value(row.get("value"))
        if row.get("value") is not None and number is None:
            errors.append(f"cffex_evidence_history_value_invalid:{suffix}")
        if number is not None:
            finite_rows.append((date, number))
    if len(values) > requested_window or value_dates != sorted(set(value_dates)):
        errors.append(f"cffex_evidence_history_value_order_invalid:{suffix}")
    if item.get("observed_trade_day_count") != len(values):
        errors.append(f"cffex_evidence_history_observed_count_mismatch:{suffix}")
    if item.get("sample_count") != len(finite_rows):
        errors.append(f"cffex_evidence_history_finite_count_mismatch:{suffix}")
    if item.get("start_date") != (value_dates[0] if value_dates else ""):
        errors.append(f"cffex_evidence_history_window_start_mismatch:{suffix}")
    if item.get("end_date") != (value_dates[-1] if value_dates else ""):
        errors.append(f"cffex_evidence_history_window_end_mismatch:{suffix}")
    target_values = [number for date, number in finite_rows if date == target]
    current = target_values[0] if len(target_values) == 1 else None
    if bool(item.get("target_date_present")) != (target in value_dates):
        errors.append(f"cffex_evidence_history_target_presence_mismatch:{suffix}")
    if not _values_equal(item.get("current_value"), current):
        errors.append(f"cffex_evidence_history_current_value_mismatch:{suffix}")
    percentile = None
    if current is not None and finite_rows:
        percentile = sum(number <= current for _, number in finite_rows) / len(finite_rows) * 100
    if not _values_equal(item.get("empirical_percentile_pct"), percentile):
        errors.append(f"cffex_evidence_history_percentile_mismatch:{suffix}")
    expected_coverage = (
        "complete"
        if len(values) == requested_window
        and len(finite_rows) == requested_window
        and target in value_dates
        and current is not None
        else "insufficient"
    )
    if item.get("coverage_status") != expected_coverage:
        errors.append(f"cffex_evidence_history_window_coverage_mismatch:{suffix}")
    return errors, {date for date, _ in finite_rows}


def _rows_equal(left, right):
    return sorted(_canonical_value(row) for row in left or []) == sorted(
        _canonical_value(row) for row in right or []
    )


def _values_equal(left, right):
    left_number = _numeric_value(left)
    right_number = _numeric_value(right)
    if left_number is not None or right_number is not None:
        return (
            left_number is not None
            and right_number is not None
            and math.isclose(left_number, right_number, rel_tol=1e-12, abs_tol=1e-9)
        )
    return _canonical_value(left) == _canonical_value(right)


def _numeric_value(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _canonical_value(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def build_cffex_index_futures_position_evidence(
    target_date: Any,
    day_data: Mapping[str, Any] | None,
    history_data: Mapping[str, Any] | None = None,
    *,
    spot_rows_by_product: Mapping[str, Mapping[str, Any]] | None = None,
    query_date: Any | None = None,
) -> dict:
    """Build a compact target-date payload from normalized fact-table rows."""

    target = normalize_trade_date(target_date)
    day_data = day_data if isinstance(day_data, Mapping) else {}
    history_data = history_data if isinstance(history_data, Mapping) else {}
    contract_rows, contract_errors = _normalize_rows(
        day_data.get("contract_rows"), target, kind="contract", target_only=True
    )
    rank_rows, rank_errors = _normalize_rows(
        day_data.get("member_rank_rows"), target, kind="rank", target_only=True
    )
    all_history_contracts, history_contract_errors = _normalize_rows(
        history_data.get("contract_rows"), target, kind="contract", target_only=False
    )
    all_history_ranks, history_rank_errors = _normalize_rows(
        history_data.get("member_rank_rows"), target, kind="rank", target_only=False
    )
    if not all_history_contracts:
        all_history_contracts = list(contract_rows)
    if not all_history_ranks:
        all_history_ranks = list(rank_rows)

    query = _resolve_query_date(query_date, contract_rows, rank_rows, target)
    missing_reasons: list[str] = [
        *contract_errors,
        *rank_errors,
        *history_contract_errors,
        *history_rank_errors,
    ]
    product_payloads: dict[str, dict] = {}
    source_files = _source_files(contract_rows, rank_rows, target)
    for product in CFFEX_PRODUCTS:
        product_contracts = [
            row for row in contract_rows if str(row.get("product_code") or "").upper() == product
        ]
        product_ranks = [
            row for row in rank_rows if str(row.get("product_code") or "").upper() == product
        ]
        product_history_contracts = [
            row
            for row in all_history_contracts
            if str(row.get("product_code") or "").upper() == product
        ]
        product_history_ranks = [
            row
            for row in all_history_ranks
            if str(row.get("product_code") or "").upper() == product
        ]
        product_missing = _product_missing_reasons(
            product,
            product_contracts,
            product_ranks,
            target,
        )
        missing_reasons.extend(product_missing)
        member = build_member_position_summary(product_ranks, product_contracts)
        previous_ranks = _previous_date_rows(product_history_ranks, target)
        top20 = build_top20_structure(product_ranks, previous_ranks)
        spot = spot_rows_by_product.get(product) if isinstance(spot_rows_by_product, Mapping) else None
        market = build_contract_market_context(
            product_contracts,
            spot_rows_by_product={product: dict(spot)} if isinstance(spot, Mapping) else {},
        )
        product_member = member.get("products", {}).get(product) or _empty_summary()
        product_top20 = top20.get("products", {}).get(product) or {}
        product_top20['previous_trade_date'] = previous_ranks[0]['trade_date'] if previous_ranks else None
        product_payloads[product] = {
            "trade_date": target,
            "contract_count": len(product_contracts),
            "rank_row_count": len(product_ranks),
            "contract_rows": deepcopy(product_contracts),
            "member_rank_rows": deepcopy(product_ranks),
            "member_position": product_member,
            "top20": product_top20,
            "market_context": market.get("products", {}).get(product) or {},
            "availability": _product_availability(product_missing, product_contracts, product_ranks),
            "missing_reasons": product_missing,
        }

    overall_member = build_member_position_summary(rank_rows, contract_rows)
    previous_ranks = _previous_date_rows(all_history_ranks, target)
    overall_top20 = build_top20_structure(rank_rows, previous_ranks).get("overall") or {}
    overall_top20['previous_trade_date'] = previous_ranks[0]['trade_date'] if previous_ranks else None
    overall_market = build_contract_market_context(
        contract_rows,
        spot_rows_by_product={
            product: dict(row)
            for product, row in (spot_rows_by_product or {}).items()
            if isinstance(row, Mapping)
        },
    )

    historical_summaries = _compact_history_summaries(
        history_data.get("summaries"),
        target,
    )
    if not historical_summaries:
        historical_summaries = _build_historical_summaries(
            all_history_contracts,
            all_history_ranks,
            target,
        )
    windows = {
        "member_net_short_change": build_history_windows(
            historical_summaries,
            target_date=target,
            value_key="member_net_short_change",
        ),
        "member_net_short_notional": build_history_windows(
            historical_summaries,
            target_date=target,
            value_key="member_net_short_notional",
        ),
        "top20_cross_section_net_short": build_history_windows(
            historical_summaries,
            target_date=target,
            value_key="top20_cross_section_net_short",
        ),
    }
    history_dates = [
        str(row.get("trade_date") or "")
        for row in historical_summaries
        if all(
            row.get(key) is not None
            for key in (
                "member_net_short_change",
                "member_net_short_notional",
                "top20_cross_section_net_short",
            )
        )
    ]
    availability = _overall_availability(product_payloads, contract_rows, rank_rows)
    missing_reasons = list(dict.fromkeys(missing_reasons))
    if not contract_rows:
        missing_reasons.append("目标日没有中金所合约行情")
    if not rank_rows:
        missing_reasons.append("目标日没有中金所会员排名")
    payload = {
        "schema_version": SCHEMA_VERSION,
        "source_policy": SOURCE_POLICY,
        "target_date": target,
        "source_date": target,
        "query_date": query,
        "availability": availability,
        "missing_reasons": list(dict.fromkeys(missing_reasons)),
        "comparability_notes": [
            "中信期货为结算会员代客汇总，不代表期货公司自营或具体客户方向。",
            "前20多头榜和前20空头榜是独立截面，榜单净空差不是固定会员集合的真实净持仓。",
            "净空扩大不等于新增空单，需同时查看空头日变和多头日变。",
        ],
        "source_files": source_files,
        "products": product_payloads,
        "member_position": {
            "member_name": overall_member.get("member_name", "中信期货"),
            "official_member_names": overall_member.get("official_member_names", []),
            "overall": overall_member.get("overall") or _empty_summary(include_share=False),
            "products": overall_member.get("products") or {},
            "included_contracts": overall_member.get("included_contracts", []),
            "excluded_contracts": overall_member.get("excluded_contracts", []),
        },
        "top20": {
            "overall": overall_top20,
            "products": {
                product: product_payloads[product].get("top20") or {}
                for product in CFFEX_PRODUCTS
            },
        },
        "market_context": {
            "rows": overall_market.get("rows", []),
            "products": overall_market.get("products", {}),
        },
        "history": {
            "trade_dates": history_dates,
            "sample_count": len(history_dates),
            "start_date": history_dates[0] if history_dates else "",
            "end_date": history_dates[-1] if history_dates else "",
            "windows": windows,
            "coverage_status": "complete" if len(history_dates) >= 60 else "partial",
        },
        "raw_target_day": {
            "contract_rows": deepcopy(contract_rows),
            "member_rank_rows": deepcopy(rank_rows),
        },
    }
    payload["artifact_hash"] = canonical_cffex_evidence_hash(payload)
    return payload


def build_unavailable_cffex_evidence(target_date: Any, *, reason: str, query_date: Any | None = None) -> dict:
    target = normalize_trade_date(target_date)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "source_policy": SOURCE_POLICY,
        "target_date": target,
        "source_date": target,
        "query_date": _resolve_query_date(query_date, [], [], target),
        "availability": "unavailable",
        "missing_reasons": [str(reason or "中金所持仓事实缺失")],
        "comparability_notes": [],
        "source_files": [],
        "products": {
            product: {
                "trade_date": target,
                "contract_count": 0,
                "rank_row_count": 0,
                "contract_rows": [],
                "member_rank_rows": [],
                "member_position": _empty_summary(),
                "top20": {},
                "market_context": {},
                "availability": "unavailable",
                "missing_reasons": [str(reason or "中金所持仓事实缺失")],
            }
            for product in CFFEX_PRODUCTS
        },
        "member_position": {"member_name": "中信期货", "overall": _empty_summary(include_share=False), "products": {}},
        "top20": {"overall": {}, "products": {}},
        "market_context": {"rows": [], "products": {}},
        "history": {"trade_dates": [], "sample_count": 0, "start_date": "", "end_date": "", "windows": {}, "coverage_status": "missing"},
        "raw_target_day": {"contract_rows": [], "member_rank_rows": []},
    }
    payload["artifact_hash"] = canonical_cffex_evidence_hash(payload)
    return payload


def load_cffex_index_futures_position_evidence(
    target_date: Any,
    *,
    service: Any | None = None,
    replay: bool = False,
    frozen_payload: Mapping[str, Any] | None = None,
    query_date: Any | None = None,
    collector: Callable[..., Mapping[str, Any]] | None = None,
    spot_fetcher: Callable[..., list[dict]] | None = None,
    allow_fresh_write: bool = True,
) -> dict:
    """Load exact-date facts, optionally collecting a fresh missing day.

    Replay never calls ``collector`` or a database writer.  Fresh collection is
    best-effort: a missing optional source becomes an unavailable evidence
    payload and does not cancel the formal report.
    """

    target = normalize_trade_date(target_date)
    if isinstance(frozen_payload, Mapping):
        valid, _ = validate_cffex_evidence(frozen_payload, target_date=target)
        if valid:
            return deepcopy(dict(frozen_payload))

    if replay and service is not None and not _service_is_postgres(service):
        service = None
    try:
        day = _query_day(service, target)
        spot_rows = _query_spot_rows(service, target)
    except Exception as error:
        return build_unavailable_cffex_evidence(
            target,
            reason=f"中金所目标日事实读取失败：{error}",
            query_date=query_date,
        )
    if _day_is_complete(day, target):
        try:
            history = _query_evidence_history(service, target)
        except Exception as error:
            return build_unavailable_cffex_evidence(
                target,
                reason=f"中金所历史窗口读取失败：{error}",
                query_date=query_date,
            )
        return build_cffex_index_futures_position_evidence(
            target,
            day,
            history,
            spot_rows_by_product=spot_rows,
            query_date=query_date,
        )
    if replay:
        reason = _day_missing_reason(day) or "目标日 PostgreSQL 中金所事实缺失"
        return build_unavailable_cffex_evidence(target, reason=reason, query_date=query_date)

    if collector is None:
        from market_data.cffex_index_futures import collect_cffex_index_futures_day

        collector = collect_cffex_index_futures_day
    try:
        fresh = collector(
            target,
            strict=False,
            include_raw_bytes=False,
            query_date=query_date,
        )
    except Exception as error:  # optional evidence must not stop the report
        return build_unavailable_cffex_evidence(target, reason=f"中金所来源请求失败：{error}", query_date=query_date)
    if not _day_is_complete(fresh, target):
        return build_unavailable_cffex_evidence(
            target,
            reason=_day_missing_reason(fresh) or "中金所四品种事实不完整",
            query_date=query_date,
        )
    history_read_failure = None
    if service is not None and allow_fresh_write and _service_is_postgres(service):
        try:
            writer = getattr(service, "replace_cffex_index_futures_day", None)
            if callable(writer):
                writer(
                    target,
                    fresh.get("contract_rows") or [],
                    fresh.get("member_rank_rows") or [],
                    replace_products=CFFEX_PRODUCTS,
                )
            _upsert_fresh_spots(service, target, spot_fetcher=spot_fetcher)
            day = _query_day(service, target) or fresh
            history = _query_evidence_history(service, target)
            spot_rows = _query_spot_rows(service, target)
        except Exception as error:
            return build_unavailable_cffex_evidence(
                target,
                reason=f"中金所目标日事实保存失败：{error}",
                query_date=query_date,
            )
    else:
        day = fresh
        try:
            history = dict(_query_history(service, target, 60) or {})
        except Exception as error:
            history = {}
            history_read_failure = f"中金所历史窗口读取失败：{error}；仅保留目标日，不用其他日期替代。"
        # Fresh reading pages do not write the fact store. Retain its history
        # and append the exact fresh day instead of collapsing the chart to one point.
        history.pop('summaries', None)
        for key in ('contract_rows', 'member_rank_rows'):
            history[key] = [r for r in history.get(key) or [] if str(r.get('trade_date') or '') < target]
            history[key].extend(fresh.get(key) or [])
    payload = build_cffex_index_futures_position_evidence(
        target,
        day,
        history,
        spot_rows_by_product=spot_rows,
        query_date=query_date,
    )
    if history_read_failure:
        payload['missing_reasons'].append(history_read_failure)
        payload['artifact_hash'] = canonical_cffex_evidence_hash(payload)
    return payload


def render_cffex_evidence_lines(payload: Mapping[str, Any] | None) -> list[str]:
    """Render a compact, user-facing research section."""

    if not isinstance(payload, Mapping):
        return []
    availability = str(payload.get("availability") or "unavailable")
    lines = ["## 股指期货持仓结构（研究证据）"]
    if availability == "unavailable":
        lines.append("中金所股指期货持仓结构：事实不足，不把当前来源或其他日期替代目标日。")
        for reason in payload.get("missing_reasons") or []:
            lines.append(f"- 事实不足：{_display(reason)}")
        return lines
    lines.append(
        f"口径：目标日 {payload.get('target_date') or '未确认'}；来源日期 {payload.get('source_date') or '未确认'}；"
        f"查询日期 {payload.get('query_date') or '未确认'}；覆盖状态：{_availability_label(availability)}。"
    )
    member = payload.get("member_position") or {}
    overall = member.get("overall") or {}
    lines.extend(
        _markdown_table(
            ["对象", "多头持仓(手)", "空头持仓(手)", "多头日变(手)", "空头日变(手)", "净空余额(手)", "净空变化(手)", "名义净空"],
            [
                (
                    f"{member.get('member_name') or '中信期货'}代客会员汇总",
                    _fmt_num(overall.get("long_quantity")),
                    _fmt_num(overall.get("short_quantity")),
                    _fmt_num(overall.get("long_daily_change")),
                    _fmt_num(overall.get("short_daily_change")),
                    _fmt_num(overall.get("net_short_balance")),
                    _fmt_num(overall.get("net_short_change")),
                    _fmt_amount(overall.get("net_short_notional")),
                )
            ],
        )
    )
    lines.append("公式：净空余额 = 空头持仓 - 多头持仓；净空变化 = 空头日变 - 多头日变。净空扩大不等于新增空单。")
    top20 = payload.get("top20") or {}
    top = top20.get("overall") or {}
    lines.extend(
        _markdown_table(
            ["范围", "前20榜单净空差(手)", "跨日变化(手)", "当前榜内日变净差(手)", "会员/披露范围影响(手)", "可比性"],
            [
                (
                    "前20多空独立榜",
                    _fmt_num(top.get("top20_cross_section_net_short")),
                    _fmt_num(top.get("top20_cross_section_change")),
                    _fmt_num(top.get("listed_member_daily_change_net")),
                    _fmt_num(top.get("membership_scope_residual")),
                    _availability_label(top.get("comparison_availability")),
                )
            ],
        )
    )
    lines.append("前20榜单净空差是两张展示榜的截面差额，不是固定20家会员的真实净持仓；残差只表示会员或披露范围变化。")
    lines.append("### 四品种与价格上下文")
    product_rows = []
    for product in CFFEX_PRODUCTS:
        item = (payload.get("products") or {}).get(product) or {}
        member_product = (member.get("products") or {}).get(product) or {}
        market_product = (payload.get("market_context") or {}).get("products", {}).get(product) or {}
        market_contracts = market_product.get("contracts") or []
        front_contract = str(market_product.get("front_contract") or "")
        front_row = next(
            (
                row
                for row in market_contracts
                if str(row.get("contract_code") or "") == front_contract
            ),
            {},
        )
        total_open_interest_change = (
            sum(float(row.get("open_interest_change") or 0) for row in market_contracts)
            if market_contracts
            else None
        )
        product_rows.append(
            (
                product,
                _fmt_num(member_product.get("net_short_balance")),
                _fmt_num(member_product.get("net_short_change")),
                _fmt_amount(member_product.get("net_short_notional")),
                front_contract or "事实不足",
                _fmt_pct(front_row.get("settlement_change_pct")),
                _fmt_num(total_open_interest_change),
                _fmt_decimal(front_row.get("basis")),
                str(market_product.get("rollover_status") or "事实不足"),
                _availability_label(item.get("availability")),
            )
        )
    lines.extend(
        _markdown_table(
            [
                "品种",
                "净空余额(手)",
                "净空变化(手)",
                "名义净空",
                "近月合约",
                "结算涨跌",
                "全市场持仓变化(手)",
                "近月基差",
                "移仓提示",
                "事实",
            ],
            product_rows,
        )
    )
    history = payload.get("history") or {}
    lines.append(
        f"历史覆盖：{history.get('sample_count', 0)} 个交易日（{history.get('start_date') or '未开始'} 至 {history.get('end_date') or '未结束'}）；"
        "20日和60日窗口只按同口径目标日前事实计算，覆盖不足时保留事实不足。"
    )
    window_rows = []
    metric_labels = {
        "member_net_short_change": "中信净空变化",
        "member_net_short_notional": "中信名义净空",
        "top20_cross_section_net_short": "前20榜单净空差",
    }
    for metric, label in metric_labels.items():
        metric_windows = (history.get("windows") or {}).get(metric) or {}
        for window in ("20", "60"):
            item = metric_windows.get(window) or {}
            window_rows.append(
                (
                    label,
                    f"{window}日",
                    _fmt_num(item.get("sample_count")),
                    item.get("start_date") or "事实不足",
                    item.get("end_date") or "事实不足",
                    _fmt_history_value(metric, item.get("current_value")),
                    _fmt_pct(item.get("empirical_percentile_pct")),
                    _availability_label(item.get("coverage_status")),
                )
            )
    lines.extend(
        _markdown_table(
            ["指标", "窗口", "有效样本", "开始", "结束", "目标日值", "历史分位", "覆盖"],
            window_rows,
        )
    )
    for reason in payload.get("missing_reasons") or []:
        lines.append(f"- 事实不足或可比性下降：{_display(reason)}")
    for note in payload.get("comparability_notes") or []:
        lines.append(f"- 说明：{_display(note)}")
    return lines


def _build_historical_summaries(contract_rows, rank_rows, target):
    dates = sorted(
        {
            str(row.get("trade_date") or "")
            for row in [*(contract_rows or []), *(rank_rows or [])]
            if str(row.get("trade_date") or "") <= target
        }
    )[-60:]
    summaries = []
    for date in dates:
        contracts = [row for row in contract_rows or [] if str(row.get("trade_date") or "") == date]
        ranks = [row for row in rank_rows or [] if str(row.get("trade_date") or "") == date]
        if not _date_has_complete_scope(contracts, ranks):
            summaries.append({"trade_date": date, "member_net_short_change": None, "member_net_short_notional": None, "top20_cross_section_net_short": None})
            continue
        member = build_member_position_summary(ranks, contracts)
        top20 = build_top20_structure(ranks, _previous_date_rows(rank_rows, date)).get("overall") or {}
        overall = member.get("overall") or {}
        member_complete = overall.get("availability") == "complete"
        top20_complete = top20.get("availability") == "complete"
        summaries.append(
            {
                "trade_date": date,
                "member_net_short_change": overall.get("net_short_change") if member_complete else None,
                "member_net_short_notional": overall.get("net_short_notional") if member_complete else None,
                "top20_cross_section_net_short": top20.get("top20_cross_section_net_short") if top20_complete else None,
            }
        )
    return summaries


def _compact_history_summaries(rows, target):
    result = []
    seen_dates = set()
    value_keys = (
        "member_net_short_change",
        "member_net_short_notional",
        "top20_cross_section_net_short",
    )
    for raw in rows or []:
        if not isinstance(raw, Mapping):
            continue
        trade_date = _safe_date(raw.get("trade_date"))
        if not trade_date or trade_date > target or trade_date in seen_dates:
            continue
        complete = bool(raw.get("complete_scope"))
        item = {"trade_date": trade_date}
        for key in value_keys:
            value = raw.get(key) if complete else None
            try:
                item[key] = float(value) if value is not None else None
            except (TypeError, ValueError):
                item[key] = None
        result.append(item)
        seen_dates.add(trade_date)
    return sorted(result, key=lambda item: item["trade_date"])[-60:]


def _date_has_complete_scope(contracts, ranks):
    """Only use days with complete four-product and selected-member coverage."""

    dates = {
        str(row.get("trade_date") or "")
        for row in [*(contracts or []), *(ranks or [])]
        if str(row.get("trade_date") or "")
    }
    if len(dates) != 1:
        return False
    assessment = assess_cffex_day_scope(
        contracts,
        ranks,
        expected_trade_date=next(iter(dates)),
        expected_products=CFFEX_PRODUCTS,
    )
    return bool(assessment.get("complete"))


def _previous_date_rows(rows: Iterable[Mapping[str, Any]] | None, target: str) -> list[dict]:
    dates = sorted({str(row.get("trade_date") or "") for row in rows or [] if str(row.get("trade_date") or "") < target})
    if not dates:
        return []
    date = dates[-1]
    return [dict(row) for row in rows or [] if str(row.get("trade_date") or "") == date]


def _rows_for_target(rows, target):
    return [dict(row) for row in rows or [] if isinstance(row, Mapping) and str(row.get("trade_date") or "") == target]


def _rows_not_after(rows, target):
    return [dict(row) for row in rows or [] if isinstance(row, Mapping) and str(row.get("trade_date") or "") <= target]


def _product_missing_reasons(product, contracts, ranks, target):
    assessment = assess_cffex_day_scope(
        contracts,
        ranks,
        expected_trade_date=target,
        expected_products=(product,),
    )
    return list(
        dict.fromkeys(
            [
                *assessment.get("integrity_errors", []),
                *assessment.get("structural_reasons", []),
                *assessment.get("member_reasons", []),
            ]
        )
    )


def _product_availability(reasons, contracts, ranks):
    if not contracts and not ranks:
        return "unavailable"
    if reasons:
        return "partial"
    return "complete"


def _overall_availability(products, contracts, ranks):
    if all((products.get(product) or {}).get("availability") == "complete" for product in CFFEX_PRODUCTS):
        return "complete"
    if contracts or ranks:
        return "partial"
    return "unavailable"


def _source_files(contract_rows, rank_rows, target):
    result = []
    grouped = {}
    for row in [*(contract_rows or []), *(rank_rows or [])]:
        key = (str(row.get("source_url") or ""), str(row.get("content_hash") or ""))
        if not key[0]:
            continue
        grouped.setdefault(key, {"source_url": key[0], "content_hash": key[1], "source_date": row.get("source_date") or "", "query_date": row.get("query_date") or "", "products": set()})
        product = str(row.get("product_code") or "")
        if product:
            grouped[key]["products"].add(product)
    for item in grouped.values():
        item = dict(item)
        item["products"] = sorted(item.get("products") or [])
        item["status"] = "available"
        result.append(item)
    return sorted(result, key=lambda row: (row.get("source_url", ""), row.get("content_hash", "")))


def _day_is_complete(day, target):
    if not isinstance(day, Mapping):
        return False
    contracts, contract_errors = _normalize_rows(
        day.get("contract_rows"), target, kind="contract", target_only=True
    )
    ranks, rank_errors = _normalize_rows(
        day.get("member_rank_rows"), target, kind="rank", target_only=True
    )
    if contract_errors or rank_errors:
        return False
    assessment = assess_cffex_day_scope(
        contracts,
        ranks,
        expected_trade_date=target,
        expected_products=CFFEX_PRODUCTS,
    )
    return bool(assessment.get("structural_complete"))


def _normalize_rows(rows, target, *, kind, target_only):
    normalized = []
    errors = []
    normalizer = normalize_contract_daily_record if kind == "contract" else normalize_member_rank_record
    label = "合约日行情" if kind == "contract" else "会员排名"
    for index, raw in enumerate(rows or []):
        if not isinstance(raw, Mapping):
            errors.append(f"{label}第{index + 1}行格式无效")
            continue
        raw_date = _safe_date(raw.get("trade_date"))
        if target_only and raw_date != target:
            errors.append(f"{label}含非目标日记录：{raw_date or '日期无效'}")
            continue
        if not target_only and (not raw_date or raw_date > target):
            if raw_date and raw_date > target:
                errors.append(f"{label}历史窗口含目标日之后记录：{raw_date}")
            continue
        try:
            item = normalizer(dict(raw), expected_trade_date=raw_date)
            if item.get("source_policy") != SOURCE_POLICY:
                raise CffexDataError(f"来源规则不匹配：{item.get('source_policy') or '缺失'}")
        except (CffexDataError, TypeError, ValueError) as error:
            errors.append(f"{label}第{index + 1}行无效：{error}")
            continue
        normalized.append(item)
    return normalized, list(dict.fromkeys(errors))


def _day_missing_reason(day):
    if not isinstance(day, Mapping):
        return "目标日 PostgreSQL 中金所事实缺失"
    errors = [str(item.get("reason") or "") for item in day.get("source_errors") or [] if isinstance(item, Mapping)]
    return "; ".join(item for item in errors if item) or "目标日中金所四品种事实不完整"


def _query_day(service, target):
    reader = getattr(service, "query_cffex_index_futures_day", None) if service is not None else None
    return reader(target) if callable(reader) else {}


def _query_history(service, target, window):
    reader = getattr(service, "query_cffex_index_futures_history", None) if service is not None else None
    return reader(target, window_days=window) if callable(reader) else {}


def _query_evidence_history(service, target):
    summary_reader = (
        getattr(service, "query_cffex_index_futures_history_summaries", None)
        if service is not None
        else None
    )
    if callable(summary_reader):
        summary_payload = summary_reader(target, window_days=60) or {}
        if summary_payload.get("summaries"):
            comparison = _query_history(service, target, 2)
            result = dict(comparison or {})
            result["summaries"] = list(summary_payload.get("summaries") or [])
            result["summary_source"] = str(summary_payload.get("source") or "")
            return result
    return _query_history(service, target, 60)


def _query_spot_rows(service, target):
    result = {}
    reader = getattr(service, "query_index_daily_bars", None) if service is not None else None
    if not callable(reader):
        return result
    for product, index_code in CFFEX_SPOT_INDEX_CODES.items():
        try:
            rows = reader(index_code, target, window_days=3, finite_positive_close_only=True) or []
        except TypeError:
            rows = reader(index_code, target, window_days=3) or []
        for row in reversed(rows):
            date = str(row.get("date") or row.get("trade_date") or "")
            if date == target:
                result[product] = {"trade_date": target, "source_date": target, "close": row.get("close"), "index_code": index_code}
                break
    return result


def _upsert_fresh_spots(service, target, *, spot_fetcher=None):
    if spot_fetcher is None:
        from market_data.cffex_index_futures import fetch_tencent_index_daily_bars

        spot_fetcher = fetch_tencent_index_daily_bars
    writer = getattr(service, "upsert_index_daily_bars", None)
    if not callable(writer):
        return
    for product, index_code in CFFEX_SPOT_INDEX_CODES.items():
        try:
            rows = spot_fetcher(index_code, target, target) or []
            if rows:
                writer(index_code, rows, source_policy="tencent.fqkline.day.cffex-spot.v1")
        except Exception:
            continue


def _service_is_postgres(service):
    checker = getattr(service, "is_postgres_backed", None)
    return bool(callable(checker) and checker())


def _resolve_query_date(query_date, contract_rows, rank_rows, target):
    if query_date:
        try:
            return normalize_trade_date(query_date)
        except CffexDataError:
            pass
    dates = [str(row.get("query_date") or "") for row in [*(contract_rows or []), *(rank_rows or [])] if row.get("query_date")]
    return sorted(dates)[-1] if dates else target


def _safe_date(value):
    try:
        return normalize_trade_date(value)
    except (CffexDataError, TypeError, ValueError):
        return ""


def _empty_summary(*, include_share=True):
    result = {
        "long_quantity": None,
        "short_quantity": None,
        "net_short_balance": None,
        "long_daily_change": None,
        "short_daily_change": None,
        "net_short_change": None,
        "long_notional": None,
        "short_notional": None,
        "net_short_notional": None,
        "included_contract_count": 0,
        "excluded_contract_count": 0,
        "availability": "unavailable",
    }
    if include_share:
        result["net_short_share_of_market_open_interest_pct"] = None
    return result


def _availability_label(value):
    return {"complete": "完整", "partial": "部分", "insufficient": "覆盖不足", "incomplete": "不可比", "unavailable": "事实不足"}.get(str(value or ""), "事实不足")


def _fmt_num(value):
    if value is None:
        return "事实不足"
    try:
        return f"{float(value):,.0f}"
    except (TypeError, ValueError):
        return "事实不足"


def _fmt_amount(value):
    if value is None:
        return "事实不足"
    try:
        return f"{float(value) / 100000000:,.2f}亿元"
    except (TypeError, ValueError):
        return "事实不足"


def _fmt_decimal(value):
    if value is None:
        return "事实不足"
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return "事实不足"


def _fmt_pct(value):
    if value is None:
        return "事实不足"
    try:
        return f"{float(value):,.2f}%"
    except (TypeError, ValueError):
        return "事实不足"


def _fmt_history_value(metric, value):
    if metric == "member_net_short_notional":
        return _fmt_amount(value)
    return _fmt_num(value)


def _display(value):
    return str(value or "").replace("\n", " ").strip()


def _markdown_table(headers, rows):
    lines = ["| " + " | ".join(str(item) for item in headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(_display(item) for item in row) + " |")
    return lines


__all__ = [
    "SCHEMA_VERSION",
    "SOURCE_POLICY",
    "build_cffex_index_futures_position_evidence",
    "build_unavailable_cffex_evidence",
    "canonical_cffex_evidence_hash",
    "load_cffex_index_futures_position_evidence",
    "render_cffex_evidence_lines",
    "validate_cffex_evidence",
]
