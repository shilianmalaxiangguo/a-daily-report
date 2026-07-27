from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import math
from collections.abc import Mapping


MARKET_LANGUAGE_SCHEMA_VERSION = "market_language_translation.v1"
SOURCE_PROJECTION_SCHEMA_VERSION = "market_language_source_projection.v1"
MARKET_LANGUAGE_SOURCE_POLICY = "postgresql.market_language_translation.v1"

VALID_FORCE_SCOPES = {
    "index_weighted",
    "single_stock",
    "single_sector",
    "multi_sector",
    "whole_market",
    "unclear",
}
VALID_DIRECTIONS = {"upward", "downward", "balanced", "unclear"}
VALID_PHASES_BY_DIRECTION = {
    "upward": {"trigger", "expansion", "crowding", "decay", "repair"},
    "downward": {"trigger", "expansion", "decay", "cascade"},
    "balanced": {"unclear"},
    "unclear": {"unclear"},
}
VALID_GRANULARITIES = {"one_minute", "five_minute", "end_of_day", "mixed"}
VALID_EVIDENCE_STATUSES = {"sufficient", "partial", "insufficient"}
MARKET_LANGUAGE_DIRECTION_SLOPE_EPSILON_BP_PER_MIN = 0.05

FIXED_WINDOW_SPECS = (
    ("09:30-09:35", "opening", "09:35"),
    ("09:45-09:50", "sentinel_observation", "09:50"),
    ("09:50-10:10", "morning_confirmation", "10:10"),
    ("14:30-14:55", "late_risk_review", "14:55"),
)

_COUNT_FIELD_NAMES = {
    "candidate_invalidations",
    "failed_rebound_count",
    "up_count",
    "down_count",
    "flat_count",
    "sample_count",
}
_DIRECTION_SLOPE_EPSILON = MARKET_LANGUAGE_DIRECTION_SLOPE_EPSILON_BP_PER_MIN
_SLOPE_COMPARISON_EPSILON = 0.05
_FOLLOW_THROUGH_MIN_BP = 0.10
_CROSS_SECTOR_SYNC_MIN_PCT = 50.0


def _text(value):
    return str(value or "").strip()


def _date_text(value):
    text = _text(value)
    if not text:
        return ""
    try:
        return dt.datetime.fromisoformat(text[:10]).date().isoformat()
    except ValueError:
        return ""


def _strict_date_text(value, *, field):
    raw = _text(value)
    if not raw:
        return ""
    normalized = _date_text(raw)
    if not normalized or normalized != raw:
        raise ValueError(f"{field} must be YYYY-MM-DD")
    return normalized


def _finite_float(value, *, field, allow_none=True):
    if value in (None, "") and allow_none:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a finite number")
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field} must be a finite number") from error
    if not math.isfinite(number):
        raise ValueError(f"{field} must be a finite number")
    return number


def _first_number(mapping, *keys):
    if not isinstance(mapping, Mapping):
        return None
    for key in keys:
        if mapping.get(key) in (None, ""):
            continue
        try:
            return _finite_float(mapping.get(key), field=key)
        except ValueError:
            continue
    return None


def _first_percentage_number(mapping, *keys):
    if not isinstance(mapping, Mapping):
        return None
    for key in keys:
        value = mapping.get(key)
        if value in (None, ""):
            continue
        if isinstance(value, str) and value.strip().endswith("%"):
            value = value.strip()[:-1].replace(",", "")
        try:
            return _finite_float(value, field=key)
        except ValueError:
            continue
    return None


def _first_text(mapping, *keys):
    if not isinstance(mapping, Mapping):
        return ""
    for key in keys:
        value = _text(mapping.get(key))
        if value:
            return value
    return ""


def _canonicalize_numbers(value):
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("market language artifact numbers must be finite")
        return int(value) if value.is_integer() else value
    if isinstance(value, Mapping):
        return {
            str(key): _canonicalize_numbers(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_canonicalize_numbers(item) for item in value]
    raise ValueError(f"market language artifact contains unsupported value: {type(value).__name__}")


def _canonical_hash(value):
    payload = json.dumps(
        _canonicalize_numbers(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def canonical_market_language_hash(artifact):
    return _canonical_hash(normalize_market_language_translation(artifact, validate=False))


def _normalize_timestamp(value, *, target_date=""):
    text = _text(value)
    if not text:
        return ""
    candidates = (text, text.replace("T", " "))
    parsed = None
    for candidate in candidates:
        try:
            parsed = dt.datetime.fromisoformat(candidate)
            break
        except ValueError:
            continue
    if parsed is None and len(text) == 5 and target_date:
        try:
            parsed = dt.datetime.fromisoformat(f"{target_date} {text}:00")
        except ValueError:
            parsed = None
    if parsed is None:
        return ""
    return parsed.strftime("%Y-%m-%d %H:%M:%S")


def _trading_minute_ordinal(timestamp):
    try:
        value = dt.datetime.fromisoformat(timestamp)
    except (TypeError, ValueError):
        return None
    if value.second or value.microsecond:
        return None
    minute_of_day = value.hour * 60 + value.minute
    morning_start = 9 * 60 + 31
    morning_end = 11 * 60 + 30
    afternoon_start = 13 * 60 + 1
    afternoon_end = 15 * 60
    if morning_start <= minute_of_day <= morning_end:
        return minute_of_day - morning_start
    if afternoon_start <= minute_of_day <= afternoon_end:
        return 120 + minute_of_day - afternoon_start
    return None


def _minute_time_axis_is_consistent(bars, period):
    if not bars or period not in {1, 5}:
        return False
    ordinals = [_trading_minute_ordinal(row.get("datetime")) for row in bars]
    if any(value is None for value in ordinals):
        return False
    return all(right - left == period for left, right in zip(ordinals[:-1], ordinals[1:]))


def _minute_payload_candidates(data):
    candidates = []
    if not isinstance(data, Mapping):
        return candidates
    if isinstance(data.get("minute_bars"), list):
        candidates.append(data)
    for key, instrument_type in (
        ("market_language_minute_bars", "index"),
        ("index_minute_bars", "index"),
        ("minute_price_payload", "index"),
    ):
        value = data.get(key)
        if isinstance(value, list):
            candidates.append(
                {
                    "minute_bars": value,
                    "instrument": {
                        "type": instrument_type,
                        "code": "000001.SH",
                        "name": "上证指数",
                    },
                    "source": {"provider": key},
                }
            )
        elif isinstance(value, Mapping) and isinstance(value.get("bars"), list):
            payload = dict(value)
            payload["minute_bars"] = list(value.get("bars") or [])
            payload.setdefault(
                "instrument",
                {"type": instrument_type, "code": "000001.SH", "name": "上证指数"},
            )
            candidates.append(payload)
    nested = data.get("market_data")
    if isinstance(nested, Mapping):
        for payload in _minute_payload_candidates(nested):
            candidates.append(payload)
    return candidates


def _bar_period_minutes(payload, bars):
    source = payload.get("source") if isinstance(payload.get("source"), Mapping) else {}
    explicit = (
        payload.get("bar_period_minutes")
        or payload.get("period_minutes")
        or payload.get("period")
        or source.get("bar_period_minutes")
        or source.get("period")
    )
    if explicit not in (None, ""):
        text = _text(explicit).lower().replace("min", "")
        try:
            return int(float(text))
        except ValueError:
            return 0
    if len(bars) < 2:
        return 0
    left = _trading_minute_ordinal(bars[0].get("datetime"))
    right = _trading_minute_ordinal(bars[1].get("datetime"))
    if left is None or right is None:
        return 0
    minutes = right - left
    return minutes if minutes > 0 else 0


def _normalize_minute_bars(payload, *, target_date):
    rows = payload.get("minute_bars") if isinstance(payload, Mapping) else None
    if not isinstance(rows, list) or not rows:
        return [], "minute_bars_missing"
    normalized = []
    seen = set()
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            return [], f"minute_bars[{index}]_invalid"
        timestamp = _normalize_timestamp(
            row.get("datetime") or row.get("trade_time") or row.get("time"),
            target_date=target_date,
        )
        if not timestamp or timestamp[:10] != target_date:
            return [], "target_date_minute_source"
        if timestamp in seen:
            return [], "minute_timestamp_duplicate"
        seen.add(timestamp)
        try:
            open_price = _finite_float(row.get("open"), field=f"minute_bars[{index}].open", allow_none=False)
            high_price = _finite_float(row.get("high"), field=f"minute_bars[{index}].high", allow_none=False)
            low_price = _finite_float(row.get("low"), field=f"minute_bars[{index}].low", allow_none=False)
            close_price = _finite_float(row.get("close"), field=f"minute_bars[{index}].close", allow_none=False)
            amount = _finite_float(row.get("amount"), field=f"minute_bars[{index}].amount")
            volume = _finite_float(row.get("volume"), field=f"minute_bars[{index}].volume")
        except ValueError:
            return [], "minute_numeric_field_invalid"
        if min(open_price, high_price, low_price, close_price) <= 0:
            return [], "minute_price_non_positive"
        if high_price < max(open_price, close_price, low_price) or low_price > min(
            open_price, close_price, high_price
        ):
            return [], "minute_ohlc_invalid"
        if amount is not None and amount < 0:
            return [], "minute_amount_negative"
        if volume is not None and volume < 0:
            return [], "minute_volume_negative"
        normalized.append(
            {
                "datetime": timestamp,
                "open": open_price,
                "high": high_price,
                "low": low_price,
                "close": close_price,
                "amount": amount,
                "volume": volume,
            }
        )
    normalized.sort(key=lambda row: row["datetime"])
    period = _bar_period_minutes(payload, normalized)
    if period not in {1, 5}:
        return [], "minute_period_unverified"
    source = payload.get("source") if isinstance(payload.get("source"), Mapping) else {}
    raw_time_semantics = _first_text(
        source,
        "bar_time_semantics",
        "time_semantics",
    ) or _first_text(payload, "bar_time_semantics", "time_semantics") or "interval_end"
    if raw_time_semantics == "interval_start":
        shifted = []
        for row in normalized:
            value = dt.datetime.fromisoformat(row["datetime"]) + dt.timedelta(minutes=period)
            item = dict(row)
            item["datetime"] = value.strftime("%Y-%m-%d %H:%M:%S")
            shifted.append(item)
        normalized = shifted
    elif raw_time_semantics != "interval_end":
        return [], "minute_time_semantics_unverified"
    if not _minute_time_axis_is_consistent(normalized, period):
        return [], "minute_interval_inconsistent"
    return normalized, ""


def _append_source(
    sources,
    *,
    source_id,
    provider,
    target_date,
    source_date,
    query_date,
    granularity,
    time_semantics,
    fields,
    content=None,
):
    row = {
        "source_id": source_id,
        "provider": _text(provider) or "daily_report_input",
        "target_date": target_date,
        "source_date": source_date,
        "query_date": query_date or None,
        "granularity": granularity,
        "time_semantics": _text(time_semantics) or (
            "interval_end" if granularity in {"one_minute", "five_minute"} else "end_of_day"
        ),
        "fields": sorted({_text(field) for field in fields if _text(field)}),
        "content_hash": _canonical_hash(content) if content is not None else None,
    }
    sources.append(row)
    return row


def _index_rows(data):
    indices = data.get("indices") if isinstance(data, Mapping) else None
    rows = []
    if isinstance(indices, Mapping):
        for code, item in indices.items():
            if isinstance(item, Mapping):
                row = dict(item)
                row.setdefault("code", code)
                rows.append(row)
    elif isinstance(indices, list):
        rows.extend(dict(item) for item in indices if isinstance(item, Mapping))
    for key in ("wind_a_alternative", "csi1000_index", "csi500_index"):
        item = data.get(key) if isinstance(data, Mapping) else None
        if isinstance(item, Mapping):
            row = dict(item)
            row.setdefault("code", key)
            rows.append(row)
    return rows


def _source_date_for_row(row, data, target_date, analysis_mode):
    del data, target_date, analysis_mode
    explicit = _strict_date_text(
        row.get("source_date") or row.get("trade_date") or row.get("date"),
        field="source_date",
    )
    return explicit


def _validated_query_date(value):
    if value in (None, ""):
        return None
    return _strict_date_text(value, field="query_date")


def _query_date_for_row(row, data):
    value = row.get("query_date")
    if value in (None, ""):
        value = data.get("query_date")
    return _validated_query_date(value)


def _select_cap_weighted_index(data, target_date, analysis_mode):
    rows = _index_rows(data)
    preferred_tokens = ("000001.SH", "sh000001", "上证指数", "000001")
    ranked = []
    for row in rows:
        source_date = _source_date_for_row(row, data, target_date, analysis_mode)
        if source_date != target_date:
            continue
        return_pct = _first_number(row, "change_pct", "pct_chg", "涨跌幅")
        if return_pct is None:
            continue
        identity = "|".join((_first_text(row, "code", "index_code"), _first_text(row, "name")))
        preference = next(
            (index for index, token in enumerate(preferred_tokens) if token.lower() in identity.lower()),
            len(preferred_tokens),
        )
        ranked.append((preference, row, source_date, return_pct))
    if not ranked:
        return None
    _, row, source_date, return_pct = sorted(ranked, key=lambda item: item[0])[0]
    return {
        "name": _first_text(row, "name") or "市值加权指数",
        "code": _first_text(row, "code", "index_code"),
        "return_pct": return_pct,
        "source_date": source_date,
        "provider": _first_text(row, "data_source", "source", "provider") or "daily_report.indices",
        "query_date": _query_date_for_row(row, data),
    }


def _market_breadth(data, target_date, analysis_mode):
    row = data.get("market_stats") if isinstance(data, Mapping) else None
    if not isinstance(row, Mapping):
        return None
    source_date = _source_date_for_row(row, data, target_date, analysis_mode)
    if source_date != target_date:
        return None
    up_count = _first_number(row, "up_count", "advance_count")
    down_count = _first_number(row, "down_count", "decline_count")
    flat_count = _first_number(row, "flat_count")
    if flat_count is None:
        flat_count = 0.0
    if up_count is None or down_count is None:
        return None
    if any(value < 0 or not float(value).is_integer() for value in (up_count, down_count, flat_count)):
        return None
    total = up_count + down_count + flat_count
    if total <= 0:
        return None
    synchronized_down_pct = _first_number(row, "synchronized_down_pct")
    if synchronized_down_pct is not None and not 0 <= synchronized_down_pct <= 100:
        return None
    return {
        "up_count": int(up_count),
        "down_count": int(down_count),
        "flat_count": int(flat_count),
        "advance_ratio_pct": up_count / total * 100.0,
        "median_return_pct": _first_number(row, "median_return_pct", "median_pct_chg"),
        "synchronized_down_pct": (
            synchronized_down_pct
            if synchronized_down_pct is not None
            else down_count / total * 100.0
        ),
        "source_date": source_date,
        "provider": _first_text(row, "data_source", "source", "provider") or "daily_report.market_stats",
        "query_date": _query_date_for_row(row, data),
    }


def _sector_synchrony(data, target_date, analysis_mode):
    candidates = []
    if isinstance(data, Mapping):
        candidates.append(data.get("market_language_sector_synchrony"))
        candidates.append(data.get("sector_internal_analysis"))
        snapshot = data.get("market_research_snapshot")
        if isinstance(snapshot, Mapping):
            candidates.append(snapshot.get("sector_internal_analysis"))
    for row in candidates:
        if not isinstance(row, Mapping):
            continue
        source_date = _source_date_for_row(row, data, target_date, analysis_mode)
        if source_date != target_date:
            continue
        active_pct = _first_number(row, "active_constituent_pct", "constituent_sync_pct")
        cross_pct = _first_number(row, "cross_sector_sync_pct", "multi_sector_sync_pct")
        if active_pct is not None and not 0 <= active_pct <= 100:
            active_pct = None
        if cross_pct is not None and not 0 <= cross_pct <= 100:
            cross_pct = None
        direction = _first_text(row, "pressure_direction", "direction")
        if direction not in VALID_DIRECTIONS:
            direction = ""
        if active_pct is None and cross_pct is None:
            continue
        return {
            "leading_sector": _first_text(row, "leading_sector", "sector_name", "selected_direction"),
            "active_constituent_pct": active_pct,
            "cross_sector_sync_pct": cross_pct,
            "pressure_direction": direction or "unclear",
            "source_date": source_date,
            "provider": _first_text(row, "data_source", "source", "provider")
            or "daily_report.sector_internal_analysis",
            "query_date": _query_date_for_row(row, data),
        }
    return None


def _participation_snapshot(data, target_date, analysis_mode):
    summary = data.get("mainline_turnover_summary") if isinstance(data, Mapping) else None
    if not isinstance(summary, Mapping):
        return {}
    source_date = _source_date_for_row(summary, data, target_date, analysis_mode)
    if source_date != target_date:
        return {}
    current_share = _first_percentage_number(
        summary,
        "sector_turnover_share_pct",
        "current_turnover_share_pct",
        "turnover_share_pct",
    )
    rows = summary.get("hot_sector_turnover_watch_rows") or summary.get("turnover_share_trend_rows")
    current_sector = _first_text(
        summary,
        "current_mainline",
        "sector_name",
        "selected_direction",
        "leading_sector",
        "mainline",
    )
    rows_by_date = {}
    if current_sector:
        for row in rows or []:
            if not isinstance(row, Mapping):
                continue
            row_date = _strict_date_text(
                row.get("source_date") or row.get("trade_date") or row.get("date"),
                field="participation row date",
            )
            row_sector = _first_text(
                row,
                "sector_name",
                "sector",
                "current_mainline",
                "mainline",
                "cycle_mainline",
                "daily_attack_line",
            )
            if not row_date or row_date > target_date or row_sector != current_sector:
                continue
            if _first_percentage_number(row, "turnover_share_pct", "share") is None:
                continue
            rows_by_date[row_date] = row
    same_sector_rows = [rows_by_date[date] for date in sorted(rows_by_date)]
    share_change = None
    if len(same_sector_rows) >= 2 and max(rows_by_date) == target_date:
        latest = _first_percentage_number(
            same_sector_rows[-1], "turnover_share_pct", "share"
        )
        previous = _first_percentage_number(
            same_sector_rows[-2], "turnover_share_pct", "share"
        )
        if latest is not None and previous is not None:
            share_change = latest - previous
    if current_share is None and same_sector_rows and max(rows_by_date) == target_date:
        current_share = _first_percentage_number(
            same_sector_rows[-1], "turnover_share_pct", "share"
        )
    crowding_status = _first_text(summary, "crowding_status", "participation_state")
    crowding_signal = summary.get("crowding_signal") is True or crowding_status == "crowding"
    raw_crowding_evidence = summary.get("crowding_evidence")
    crowding_evidence = [
        _text(item)
        for item in (
            raw_crowding_evidence
            if isinstance(raw_crowding_evidence, (list, tuple))
            else [raw_crowding_evidence]
        )
        if _text(item)
    ]
    result = {
        "sector_turnover_share_pct": current_share,
        "sector_turnover_share_change_pp": share_change,
        "breadth_change_pp": _first_number(summary, "breadth_change_pp"),
        "core_follower_spread_pct": _first_number(summary, "core_follower_spread_pct"),
        "rival_relative_strength_pct": _first_number(summary, "rival_relative_strength_pct"),
        "crowding_signal": crowding_signal,
        "crowding_evidence": crowding_evidence,
        "provider": _first_text(summary, "source", "data_source", "provider")
        or "daily_report.mainline_turnover_summary",
        "source_date": source_date,
        "query_date": _query_date_for_row(summary, data),
    }
    if not crowding_signal and not any(
        result.get(key) is not None
        for key in (
            "sector_turnover_share_pct",
            "sector_turnover_share_change_pp",
            "breadth_change_pp",
            "core_follower_spread_pct",
            "rival_relative_strength_pct",
        )
    ):
        return {}
    return result


def _instrument_identity_token(value):
    text = "".join(character for character in _text(value).upper() if character.isalnum())
    digits = "".join(character for character in text if character.isdigit())
    if len(digits) < 6:
        return text
    code = digits[-6:]
    exchange = ""
    exchange_aliases = (
        ("SH", ("SH", "SSE", "XSHG")),
        ("SZ", ("SZ", "SZSE", "XSHE")),
        ("BJ", ("BJ", "BSE", "XBSE")),
    )
    for normalized, aliases in exchange_aliases:
        if any(text.startswith(alias) or text.endswith(alias) for alias in aliases):
            exchange = normalized
            break
    return f"{code}.{exchange}" if exchange else code


def _normalized_instrument_identity(value):
    value = value if isinstance(value, Mapping) else {}
    instrument_type = _first_text(value, "type")
    if instrument_type not in {"stock", "index", "sector"}:
        instrument_type = ""
    return {
        "type": instrument_type,
        "code": _first_text(value, "code", "symbol", "ts_code"),
        "name": _first_text(value, "name"),
    }


def _instrument_identity_matches(left, right):
    left = _normalized_instrument_identity(left)
    right = _normalized_instrument_identity(right)
    left_code = _instrument_identity_token(left.get("code"))
    right_code = _instrument_identity_token(right.get("code"))
    if left_code or right_code:
        return bool(left_code and right_code and left_code == right_code)
    left_name = _text(left.get("name"))
    right_name = _text(right.get("name"))
    return bool(left_name and right_name and left_name == right_name)


def _posthoc_daily_bars(data, target_date):
    if not isinstance(data, Mapping):
        return []
    candidates = []
    for key in (
        "market_language_posthoc_daily_bars",
        "posthoc_daily_bars",
        "future_daily_bars",
    ):
        value = data.get(key)
        if isinstance(value, list):
            candidates.extend(value)
    normalized = []
    for row in candidates:
        if not isinstance(row, Mapping):
            continue
        trade_date = _strict_date_text(
            row.get("trade_date") or row.get("date"),
            field="posthoc trade_date",
        )
        if not trade_date or trade_date <= target_date:
            continue
        source_date = _strict_date_text(
            row.get("source_date"), field="posthoc source_date"
        )
        query_date = _strict_date_text(
            row.get("query_date"), field="posthoc query_date"
        )
        if source_date != trade_date or not query_date or query_date < trade_date:
            continue
        instrument = row.get("instrument") if isinstance(row.get("instrument"), Mapping) else {}
        instrument_code = _first_text(instrument, "code", "symbol") or _first_text(
            row,
            "code",
            "symbol",
            "ts_code",
        )
        instrument_name = _first_text(instrument, "name") or _first_text(row, "name")
        if not instrument_code and not instrument_name:
            continue
        try:
            open_price = _first_number(row, "open")
            high_price = _first_number(row, "high")
            low_price = _first_number(row, "low")
            close_price = _first_number(row, "close")
        except ValueError:
            continue
        if None in {open_price, high_price, low_price, close_price}:
            continue
        if min(open_price, high_price, low_price, close_price) <= 0:
            continue
        if high_price < max(open_price, close_price, low_price) or low_price > min(
            open_price, close_price, high_price
        ):
            continue
        normalized.append(
            {
                "trade_date": trade_date,
                "source_date": source_date,
                "query_date": query_date,
                "instrument_code": instrument_code,
                "instrument_name": instrument_name,
                "open": open_price,
                "high": high_price,
                "low": low_price,
                "close": close_price,
                "source": _first_text(row, "source", "data_source", "provider"),
            }
        )
    return sorted(normalized, key=lambda row: row["trade_date"])


def _posthoc_trade_calendar(data, target_date):
    if not isinstance(data, Mapping):
        return {}
    raw = data.get("market_language_posthoc_trade_calendar")
    if not isinstance(raw, Mapping):
        return {}
    range_start = _strict_date_text(
        raw.get("range_start") or raw.get("start_date"),
        field="posthoc calendar range_start",
    )
    range_end = _strict_date_text(
        raw.get("range_end") or raw.get("end_date"),
        field="posthoc calendar range_end",
    )
    query_date = _strict_date_text(
        raw.get("query_date"), field="posthoc calendar query_date"
    )
    if (
        not range_start
        or not range_end
        or not query_date
        or range_start > target_date
        or range_end <= target_date
    ):
        return {}
    open_dates = sorted(
        {
            date
            for value in raw.get("open_dates") or []
            if (
                date := _strict_date_text(
                    value, field="posthoc calendar open_date"
                )
            )
            and range_start <= date <= range_end
        }
    )
    if target_date not in open_dates:
        return {}
    return {
        "provider": _first_text(raw, "provider", "source", "data_source")
        or "explicit.trade_calendar",
        "query_date": query_date,
        "range_start": range_start,
        "range_end": range_end,
        "open_dates": open_dates,
    }


def _posthoc_fund_overlap(data, target_date):
    if not isinstance(data, Mapping):
        return None
    raw = data.get("market_language_fund_overlap")
    if not isinstance(raw, Mapping):
        return None
    fact_target_date = _strict_date_text(
        raw.get("target_date"), field="posthoc fund target_date"
    )
    source_date = _strict_date_text(
        raw.get("source_date") or raw.get("trade_date"),
        field="posthoc fund source_date",
    )
    query_date = _strict_date_text(
        raw.get("query_date"), field="posthoc fund query_date"
    )
    overlap_pct = _first_number(raw, "overlap_pct")
    instrument = raw.get("instrument") if isinstance(raw.get("instrument"), Mapping) else {}
    instrument_code = _first_text(instrument, "code", "symbol", "ts_code") or _first_text(
        raw,
        "instrument_code",
        "code",
        "symbol",
        "ts_code",
    )
    instrument_name = _first_text(instrument, "name") or _first_text(
        raw,
        "instrument_name",
        "name",
    )
    if (
        fact_target_date != target_date
        or not source_date
        or source_date < target_date
        or not query_date
        or query_date < source_date
        or overlap_pct is None
        or not 0 <= overlap_pct <= 100
        or not (instrument_code or instrument_name)
    ):
        return None
    return {
        "overlap_pct": overlap_pct,
        "target_date": fact_target_date,
        "source_date": source_date,
        "query_date": query_date,
        "instrument_code": instrument_code,
        "instrument_name": instrument_name,
        "source": _first_text(raw, "source", "provider", "data_source"),
    }


def build_market_language_source_projection(data, *, target_date, analysis_mode="fresh"):
    target_date = _strict_date_text(target_date, field="target_date")
    if not target_date:
        raise ValueError("target_date must be YYYY-MM-DD")
    analysis_mode = "replay" if analysis_mode == "replay" else "fresh"
    data = data if isinstance(data, Mapping) else {}
    sources = []
    minute_series = []
    missing = []

    for payload_index, payload in enumerate(_minute_payload_candidates(data), start=1):
        bars, reason = _normalize_minute_bars(payload, target_date=target_date)
        if reason:
            if reason not in missing:
                missing.append(reason)
            continue
        period = _bar_period_minutes(payload, bars)
        source = payload.get("source") if isinstance(payload.get("source"), Mapping) else {}
        source_date = _strict_date_text(
            source.get("source_date")
            or payload.get("source_date")
            or payload.get("trade_date")
            or bars[0]["datetime"][:10],
            field="minute source_date",
        )
        if source_date != target_date:
            if "target_date_minute_source" not in missing:
                missing.append("target_date_minute_source")
            continue
        source_id = f"src-minute-{payload_index:02d}"
        granularity = "one_minute" if period == 1 else "five_minute"
        raw_time_semantics = _first_text(
            source,
            "bar_time_semantics",
            "time_semantics",
        ) or _first_text(payload, "bar_time_semantics", "time_semantics") or "interval_end"
        source_row = _append_source(
            sources,
            source_id=source_id,
            provider=_first_text(source, "provider", "data_source", "source")
            or _first_text(payload, "provider", "data_source"),
            target_date=target_date,
            source_date=source_date,
            query_date=_validated_query_date(
                source.get("query_date") or payload.get("query_date")
            ),
            granularity=granularity,
            time_semantics=(
                "interval_end_normalized_from_interval_start"
                if raw_time_semantics == "interval_start"
                else "interval_end"
            ),
            fields=("datetime", "open", "high", "low", "close", "amount", "volume"),
            content=bars,
        )
        instrument = payload.get("instrument") if isinstance(payload.get("instrument"), Mapping) else {}
        instrument_type = _first_text(instrument, "type")
        if instrument_type not in {"stock", "index", "sector"}:
            instrument_type = "index" if "index" in source_row["provider"].lower() else "stock"
        minute_series.append(
            {
                "source_id": source_id,
                "granularity": granularity,
                "instrument": {
                    "type": instrument_type,
                    "code": _first_text(instrument, "code", "symbol"),
                    "name": _first_text(instrument, "name"),
                },
                "bars": bars,
                "amount_unit": _first_text(source, "amount_unit") or "CNY",
                "amount_semantics": _first_text(source, "amount_semantics") or "interval",
                "volume_unit": _first_text(source, "volume_unit"),
                "volume_semantics": _first_text(source, "volume_semantics"),
            }
        )

    cap_weighted = _select_cap_weighted_index(data, target_date, analysis_mode)
    if cap_weighted:
        source_id = "src-cap-weighted-eod"
        _append_source(
            sources,
            source_id=source_id,
            provider=cap_weighted.pop("provider"),
            target_date=target_date,
            source_date=cap_weighted.pop("source_date"),
            query_date=cap_weighted.pop("query_date"),
            granularity="end_of_day",
            time_semantics="end_of_day",
            fields=("return_pct", "code", "name"),
            content=cap_weighted,
        )
        cap_weighted["source_id"] = source_id

    breadth = _market_breadth(data, target_date, analysis_mode)
    if breadth:
        source_id = "src-market-breadth-eod"
        _append_source(
            sources,
            source_id=source_id,
            provider=breadth.pop("provider"),
            target_date=target_date,
            source_date=breadth.pop("source_date"),
            query_date=breadth.pop("query_date"),
            granularity="end_of_day",
            time_semantics="end_of_day",
            fields=breadth.keys(),
            content=breadth,
        )
        breadth["source_id"] = source_id

    sector = _sector_synchrony(data, target_date, analysis_mode)
    if sector:
        source_id = "src-sector-synchrony-eod"
        _append_source(
            sources,
            source_id=source_id,
            provider=sector.pop("provider"),
            target_date=target_date,
            source_date=sector.pop("source_date"),
            query_date=sector.pop("query_date"),
            granularity="end_of_day",
            time_semantics="end_of_day",
            fields=sector.keys(),
            content=sector,
        )
        sector["source_id"] = source_id

    participation = _participation_snapshot(data, target_date, analysis_mode)
    if participation:
        source_id = "src-participation-eod"
        _append_source(
            sources,
            source_id=source_id,
            provider=participation.pop("provider"),
            target_date=target_date,
            source_date=participation.pop("source_date"),
            query_date=participation.pop("query_date"),
            granularity="end_of_day",
            time_semantics="end_of_day",
            fields=participation.keys(),
            content=participation,
        )
        participation["source_id"] = source_id

    posthoc_inputs = {
        "daily_bars": [],
        "fund_overlap": None,
        "trade_calendar": {},
    }
    if analysis_mode == "replay":
        posthoc_inputs = {
            "daily_bars": _posthoc_daily_bars(data, target_date),
            "fund_overlap": _posthoc_fund_overlap(data, target_date),
            "trade_calendar": _posthoc_trade_calendar(data, target_date),
        }

    return {
        "schema_version": SOURCE_PROJECTION_SCHEMA_VERSION,
        "target_date": target_date,
        "analysis_mode": analysis_mode,
        "sources": sources,
        "minute_series": minute_series,
        "daily": {
            "cap_weighted": cap_weighted or {},
            "market_breadth": breadth or {},
            "sector_synchrony": sector or {},
            "participation": participation or {},
        },
        "posthoc_inputs": posthoc_inputs,
        "missing_evidence": missing,
    }


def _linear_slope_bp_per_minute(rows, lookback_minutes):
    count = lookback_minutes + 1
    selected = rows[-count:]
    if len(selected) < count:
        return None
    base = selected[0]["close"]
    ys = [math.log(row["close"] / base) * 10000.0 for row in selected]
    xs = list(range(len(ys)))
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    denominator = sum((value - mean_x) ** 2 for value in xs)
    if denominator <= 0:
        return None
    return sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / denominator


def _rolling_slope_curvature(rows, lookback_minutes=20):
    count = lookback_minutes + 1
    selected = rows[-count:]
    if len(selected) < count:
        return None
    slopes = []
    for endpoint in range(6, len(selected) + 1):
        slope = _linear_slope_bp_per_minute(selected[:endpoint], 5)
        if slope is not None:
            slopes.append(slope)
    if len(slopes) < 2:
        return None
    return (slopes[-1] - slopes[0]) / max(len(slopes) - 1, 1)


def market_language_linear_slope_bp_per_minute(rows, lookback_minutes):
    return _linear_slope_bp_per_minute(rows, lookback_minutes)


def market_language_rolling_curvature_bp_per_minute2(rows, lookback_minutes=20):
    return _rolling_slope_curvature(rows, lookback_minutes)


def _direction_from_slope(slope_15):
    if slope_15 is None:
        return "unclear"
    if slope_15 < -_DIRECTION_SLOPE_EPSILON:
        return "downward"
    if slope_15 > _DIRECTION_SLOPE_EPSILON:
        return "upward"
    return "balanced"


def _phase_from_surface(direction, slope_5, slope_15, curvature, *, confirmed=False):
    slope_delta = (
        slope_5 - slope_15
        if slope_5 is not None and slope_15 is not None
        else None
    )
    if direction == "downward":
        if confirmed and slope_delta is not None and slope_delta < -_SLOPE_COMPARISON_EPSILON:
            if curvature is None or curvature < 0:
                return "cascade"
        if confirmed and slope_delta is not None and slope_delta > _SLOPE_COMPARISON_EPSILON:
            return "decay"
        return "expansion" if confirmed else "trigger"
    if direction == "upward":
        if confirmed and slope_delta is not None and slope_delta < -_SLOPE_COMPARISON_EPSILON:
            return "decay"
        return "expansion" if confirmed else "trigger"
    return "unclear"


def _surface_at_prefix(prefix):
    slope_5 = _linear_slope_bp_per_minute(prefix, 5)
    slope_10 = _linear_slope_bp_per_minute(prefix, 10)
    slope_15 = _linear_slope_bp_per_minute(prefix, 15)
    slope_20 = _linear_slope_bp_per_minute(prefix, 20)
    curvature = _rolling_slope_curvature(prefix, 20)
    direction = _direction_from_slope(slope_15)
    return {
        "slope_5m_bp_per_min": slope_5,
        "slope_10m_bp_per_min": slope_10,
        "slope_15m_bp_per_min": slope_15,
        "slope_20m_bp_per_min": slope_20,
        "slope_change_bp_per_min": (
            slope_5 - slope_15 if slope_5 is not None and slope_15 is not None else None
        ),
        "curvature_bp_per_min2": curvature,
        "pressure_direction": direction,
    }


def _has_directional_follow_through(direction, candidate_close, current_close, elapsed_minutes):
    if elapsed_minutes <= 0 or candidate_close <= 0 or current_close <= 0:
        return False
    move_bp = math.log(current_close / candidate_close) * 10000.0
    threshold = max(_FOLLOW_THROUGH_MIN_BP, _DIRECTION_SLOPE_EPSILON * elapsed_minutes)
    if direction == "downward":
        return move_bp <= -threshold
    if direction == "upward":
        return move_bp >= threshold
    return False


def _build_timeline_events(bars, evidence_id):
    events = []
    active = None
    active_run = 0
    active_neutral_run = 0
    active_candidate_close = None
    active_candidate_ordinal = None
    latest_surface = _surface_at_prefix(bars)
    for index in range(len(bars)):
        prefix = bars[: index + 1]
        surface = _surface_at_prefix(prefix)
        direction = surface["pressure_direction"]
        timestamp = bars[index]["datetime"]
        is_candidate = direction in {"upward", "downward"}

        if active is not None:
            opposite_direction = is_candidate and direction != active["pressure_direction"]
            neutral_after_confirmation = (
                not is_candidate and active.get("confirmed_at") is not None
            )
            if neutral_after_confirmation:
                active_neutral_run += 1
                active["causal_cutoff"] = timestamp
                if active_neutral_run < 3:
                    continue
            if opposite_direction or not is_candidate:
                active["invalidated_at"] = timestamp
                active["causal_cutoff"] = timestamp
                events.append(active)
                active = None
                active_run = 0
                active_neutral_run = 0
                active_candidate_close = None
                active_candidate_ordinal = None

        if not is_candidate:
            continue
        if active is None:
            event_index = len(events) + 1
            active = {
                "event_id": f"event-{event_index:03d}-{direction}-{timestamp[11:16].replace(':', '')}",
                "candidate_at": timestamp,
                "detected_at": timestamp,
                "confirmed_at": None,
                "invalidated_at": None,
                "causal_cutoff": timestamp,
                "pressure_direction": direction,
                "phase": "trigger",
                "confirmation_basis": "three_overlapping_15m_slope_directions",
                "directional_follow_through_at": None,
                "confirmation_quality": "unconfirmed",
                "evidence_refs": [evidence_id],
            }
            active_run = 1
            active_neutral_run = 0
            active_candidate_close = bars[index]["close"]
            active_candidate_ordinal = _trading_minute_ordinal(timestamp)
        else:
            active_run += 1
            active_neutral_run = 0
            active["causal_cutoff"] = timestamp
        current_ordinal = _trading_minute_ordinal(timestamp)
        if (
            active.get("directional_follow_through_at") is None
            and active_candidate_close is not None
            and active_candidate_ordinal is not None
            and current_ordinal is not None
            and _has_directional_follow_through(
                direction,
                active_candidate_close,
                bars[index]["close"],
                current_ordinal - active_candidate_ordinal,
            )
        ):
            active["directional_follow_through_at"] = timestamp
        if active_run == 3:
            active["confirmed_at"] = timestamp
        if active["confirmed_at"] is not None:
            active["confirmation_quality"] = (
                "directional_follow_through"
                if active["directional_follow_through_at"] is not None
                else "slope_persistence_only"
            )
        active["phase"] = _phase_from_surface(
            direction,
            surface["slope_5m_bp_per_min"],
            surface["slope_15m_bp_per_min"],
            surface["curvature_bp_per_min2"],
            confirmed=active["confirmed_at"] is not None,
        )

    if active is not None:
        events.append(active)
    return events, latest_surface


def _failed_rebound_count(bars):
    if len(bars) < 3:
        return 0
    changes = [right["close"] - left["close"] for left, right in zip(bars[:-1], bars[1:])]
    return sum(
        1
        for left, right in zip(changes[:-1], changes[1:])
        if left > 0 and right < 0
    )


def _liquidity_proxies(series, bars):
    amount_usable = (
        bool(bars)
        and _text(series.get("amount_unit")).upper() == "CNY"
        and _text(series.get("amount_semantics")).lower() == "interval"
        and all(row.get("amount") is not None for row in bars)
    )
    impact = None
    if amount_usable and len(bars) >= 6:
        selected = bars[-6:]
        amount_yi = sum(row["amount"] for row in selected[1:]) / 100000000.0
        decline_bp = max(0.0, -math.log(selected[-1]["close"] / selected[0]["close"]) * 10000.0)
        if amount_yi > 0:
            impact = decline_bp / amount_yi

    below_vwap = None
    if (
        series.get("instrument", {}).get("type") == "stock"
        and amount_usable
        and _text(series.get("volume_unit")).lower() == "shares"
        and _text(series.get("volume_semantics")).lower() == "interval"
        and all(row.get("volume") is not None for row in bars)
    ):
        running_amount = 0.0
        running_volume = 0.0
        dwell = 0
        for row in bars:
            running_amount += row["amount"]
            running_volume += row["volume"]
            vwap = running_amount / running_volume if running_volume > 0 else None
            dwell = dwell + 1 if vwap is not None and row["close"] < vwap else 0
        below_vwap = dwell
    return {
        "impact_per_100m_turnover_bp": impact,
        "impact_reversion_ratio": None,
        "below_vwap_dwell_minutes": below_vwap,
        "is_proxy": True,
        "source_refs": [series["source_id"]],
        "as_of_time": bars[-1]["datetime"] if bars else None,
    }


def _fixed_window_observations(bars, evidence_id):
    observations = []
    for window, prefix_label, cutoff in FIXED_WINDOW_SPECS:
        if not bars or bars[-1]["datetime"][11:16] < cutoff:
            continue
        prefix = [row for row in bars if row["datetime"][11:16] <= cutoff]
        if not prefix:
            continue
        surface = _surface_at_prefix(prefix)
        direction = surface["pressure_direction"]
        recent_directions = [
            _surface_at_prefix(prefix[:index])["pressure_direction"]
            for index in range(max(1, len(prefix) - 2), len(prefix) + 1)
        ]
        confirmed = (
            len(recent_directions) == 3
            and direction in {"upward", "downward"}
            and all(value == direction for value in recent_directions)
        )
        phase = _phase_from_surface(
            direction,
            surface["slope_5m_bp_per_min"],
            surface["slope_15m_bp_per_min"],
            surface["curvature_bp_per_min2"],
            confirmed=confirmed,
        )
        observations.append(
            {
                "window": window,
                "observation_prefix": prefix_label,
                "as_of_time": prefix[-1]["datetime"],
                "pressure_direction": direction,
                "phase": phase,
                "evidence_refs": [evidence_id],
                "counter_evidence_refs": [],
            }
        )
    return observations


def _cap_weighted_direction(cap):
    cap_return = (cap or {}).get("return_pct")
    if cap_return is None:
        return "unclear"
    if cap_return <= -0.5:
        return "downward"
    if cap_return >= 0.5:
        return "upward"
    if abs(cap_return) <= 0.3:
        return "balanced"
    return "unclear"


def _breadth_direction(breadth):
    advance_ratio = (breadth or {}).get("advance_ratio_pct")
    if advance_ratio is None:
        return "unclear"
    if advance_ratio <= 40:
        return "downward"
    if advance_ratio >= 60:
        return "upward"
    if 45 <= advance_ratio <= 55:
        return "balanced"
    return "unclear"


def _daily_vote_direction(daily):
    votes = []
    cap = daily.get("cap_weighted") or {}
    cap_direction = _cap_weighted_direction(cap)
    if cap_direction != "unclear":
        votes.append(cap_direction)
    breadth = daily.get("market_breadth") or {}
    breadth_direction = _breadth_direction(breadth)
    if breadth_direction != "unclear":
        votes.append(breadth_direction)
    sector_direction = (daily.get("sector_synchrony") or {}).get("pressure_direction")
    if sector_direction in VALID_DIRECTIONS - {"unclear"}:
        votes.append(sector_direction)
    directional = [value for value in votes if value in {"upward", "downward"}]
    if directional and len(set(directional)) == 1:
        return directional[0], votes
    if not directional and votes and set(votes) == {"balanced"}:
        return "balanced", votes
    return "unclear", votes


def _force_scope(primary_series, daily, direction):
    instrument_type = ((primary_series or {}).get("instrument") or {}).get("type")
    if instrument_type == "stock":
        return "single_stock"
    if instrument_type == "sector":
        return "single_sector"
    cap = bool(daily.get("cap_weighted")) or instrument_type == "index"
    cap_direction = _cap_weighted_direction(daily.get("cap_weighted") or {})
    if cap_direction == "unclear" and instrument_type == "index":
        cap_direction = direction
    breadth_row = daily.get("market_breadth") or {}
    breadth = bool(breadth_row)
    breadth_direction = _breadth_direction(breadth_row)
    sector = daily.get("sector_synchrony") or {}
    sector_direction = sector.get("pressure_direction")
    active_sector_sync = sector.get("active_constituent_pct") is not None
    cross_sector_sync_pct = sector.get("cross_sector_sync_pct")
    cross_sector_sync = (
        cross_sector_sync_pct is not None
        and cross_sector_sync_pct >= _CROSS_SECTOR_SYNC_MIN_PCT
    )
    all_layers_aligned = (
        direction in {"upward", "downward"}
        and cap_direction == direction
        and breadth_direction == direction
        and sector_direction == direction
    )
    if cap and breadth and cross_sector_sync and all_layers_aligned:
        return "whole_market"
    if cross_sector_sync and sector_direction == direction:
        return "multi_sector"
    if cap:
        return "index_weighted"
    if active_sector_sync and sector_direction == direction:
        return "single_sector"
    return "unclear"


def _phase_label(direction, phase):
    labels = {
        ("upward", "trigger"): "向上压力启动",
        ("upward", "expansion"): "向上合力扩散",
        ("upward", "crowding"): "向上合力拥挤",
        ("upward", "decay"): "向上合力衰减",
        ("upward", "repair"): "此前向下压力后的修复",
        ("downward", "trigger"): "向下压力启动",
        ("downward", "expansion"): "向下压力扩散",
        ("downward", "decay"): "向下压力边际衰减",
        ("downward", "cascade"): "向下反馈加速",
        ("balanced", "unclear"): "多空接近平衡",
        ("unclear", "unclear"): "事实不足，阶段不清楚",
    }
    return labels.get((direction, phase), "事实不足，阶段不清楚")


def _next_window_task(as_of_time, direction, status):
    if status == "insufficient":
        return (
            "低注意力研究目标，不替代正式执行计划。"
            "固定主动查看只安排在T+1 09:30-09:35与T+2 14:30-14:55；"
            "开盘按前一晚计划处理B1（若有）。"
            "预定后台复核还需补齐指数、全市场宽度与板块同步事实，"
            "并且只核对前一晚已允许的B2。目前不会自动提醒；"
            "未收到明确提示时B2不执行。"
            "T+2尾盘按退出计划处理可卖仓位。"
            "其余时间不生成新决定，不要求持续盯盘。"
        )
    direction_text = {"downward": "向下压力", "upward": "向上合力"}.get(direction, "方向")
    return (
        "低注意力研究目标，不替代正式执行计划。"
        "固定主动查看只安排在T+1 09:30-09:35与T+2 14:30-14:55；"
        "开盘按前一晚计划处理B1（若有）。"
        f"预定规则是在09:50-10:10后台复核{direction_text}，"
        "并且只核对前一晚已允许的B2。目前不会自动提醒；"
        "未收到明确提示时B2不执行。"
        "T+2尾盘按退出计划处理可卖仓位。"
        "其余时间不生成新决定，不要求持续盯盘。"
    )


def _posthoc_validation(artifact, primary_series, projection=None):
    projection = projection if isinstance(projection, Mapping) else {}
    bars = list((primary_series or {}).get("bars") or [])
    if not bars:
        return {
            "validation_status": "insufficient",
            "event_reviews": [],
            "missing_evidence": ["one_minute_price_path"],
        }
    index_by_time = {row["datetime"]: index for index, row in enumerate(bars)}
    event_reviews = []
    day_low = min(row["low"] for row in bars)
    day_high = max(row["high"] for row in bars)
    day_range = day_high - day_low
    for event in (artifact.get("timeline") or {}).get("events") or []:
        anchor_time = event.get("detected_at") or event.get("candidate_at")
        index = index_by_time.get(anchor_time)
        if index is None:
            continue
        anchor = bars[index]["close"]
        future = bars[index + 1 :]
        review = {
            "event_id": event.get("event_id"),
            "anchor_at": anchor_time,
            "future_return_pct": {},
            "mfe_pct": None,
            "mae_pct": None,
            "anchor_day_range_percentile": (
                (anchor - day_low) / day_range * 100.0 if day_range > 0 else None
            ),
            "anchor_zone": None,
            "main_move_completion_pct": None,
        }
        percentile = review["anchor_day_range_percentile"]
        if percentile is not None:
            review["anchor_zone"] = (
                "low_zone" if percentile <= 33.3333 else "high_zone" if percentile >= 66.6667 else "middle_zone"
            )
        for horizon in (5, 10, 20):
            future_index = index + horizon
            review["future_return_pct"][f"{horizon}m"] = (
                (bars[future_index]["close"] / anchor - 1.0) * 100.0
                if future_index < len(bars)
                else None
            )
        if future:
            review["mfe_pct"] = (max(row["high"] for row in future) / anchor - 1.0) * 100.0
            review["mae_pct"] = (min(row["low"] for row in future) / anchor - 1.0) * 100.0
            if event.get("pressure_direction") == "downward":
                known_high = max(row["high"] for row in bars[: index + 1])
                future_low = min(row["low"] for row in future)
                total_move = known_high - future_low
                if total_move > 0:
                    review["main_move_completion_pct"] = max(
                        0.0,
                        min(100.0, (known_high - anchor) / total_move * 100.0),
                    )
            elif event.get("pressure_direction") == "upward":
                known_low = min(row["low"] for row in bars[: index + 1])
                future_high = max(row["high"] for row in future)
                total_move = future_high - known_low
                if total_move > 0:
                    review["main_move_completion_pct"] = max(
                        0.0,
                        min(100.0, (anchor - known_low) / total_move * 100.0),
                    )
        event_reviews.append(review)
    future_daily_candidates = list(
        (projection.get("posthoc_inputs") or {}).get("daily_bars") or []
    )
    primary_instrument = _normalized_instrument_identity(
        (primary_series or {}).get("instrument") or {}
    )
    primary_code = _instrument_identity_token(primary_instrument.get("code"))
    primary_name = _text(primary_instrument.get("name"))
    future_daily_bars_by_date = {}
    seen_trade_dates = set()
    for row in future_daily_candidates:
        row_code = _instrument_identity_token(row.get("instrument_code"))
        row_name = _text(row.get("instrument_name"))
        if primary_code and row_code != primary_code:
            continue
        if not primary_code and primary_name and row_name != primary_name:
            continue
        trade_date = row.get("trade_date")
        if not trade_date or trade_date in seen_trade_dates:
            continue
        seen_trade_dates.add(trade_date)
        future_daily_bars_by_date[trade_date] = row
    t0_close = bars[-1]["close"] if bars else None

    def daily_range(row):
        if not isinstance(row, Mapping) or t0_close in (None, 0):
            return None
        return {
            "trade_date": row.get("trade_date"),
            "source_date": row.get("source_date"),
            "query_date": row.get("query_date"),
            "instrument_code": row.get("instrument_code") or "",
            "open": row.get("open"),
            "high": row.get("high"),
            "low": row.get("low"),
            "close": row.get("close"),
            "return_from_t0_close_pct": (float(row.get("close")) / t0_close - 1.0) * 100.0,
            "source": row.get("source") or "",
        }

    posthoc_inputs = projection.get("posthoc_inputs") or {}
    trade_calendar = posthoc_inputs.get("trade_calendar") or {}
    expected_trade_dates = [
        value
        for value in trade_calendar.get("open_dates") or []
        if value > projection.get("target_date", "")
    ][:2]
    t1_date = expected_trade_dates[0] if expected_trade_dates else ""
    t2_date = expected_trade_dates[1] if len(expected_trade_dates) >= 2 else ""
    t1_range = daily_range(future_daily_bars_by_date.get(t1_date)) if t1_date else None
    t2_range = daily_range(future_daily_bars_by_date.get(t2_date)) if t2_date else None
    fund_overlap = posthoc_inputs.get("fund_overlap")
    if fund_overlap and not _instrument_identity_matches(
        primary_instrument,
        {
            "code": fund_overlap.get("instrument_code"),
            "name": fund_overlap.get("instrument_name"),
        },
    ):
        fund_overlap = None
    missing = []
    if len(expected_trade_dates) < 2:
        missing.append("posthoc_trade_calendar")
    if t1_range is None:
        missing.append("t1_price_range")
    if t2_range is None:
        missing.append("t2_price_range")
    if fund_overlap in (None, {}, []):
        missing.append("fund_overlap")
    return {
        "validation_status": "available" if event_reviews else "partial",
        "event_reviews": event_reviews,
        "t1_price_range": t1_range,
        "t2_price_range": t2_range,
        "fund_overlap": copy.deepcopy(fund_overlap),
        "trade_calendar": copy.deepcopy(trade_calendar),
        "missing_evidence": missing,
    }


def _is_complete_one_minute_session(primary_series):
    if (primary_series or {}).get("granularity") != "one_minute":
        return False
    bars = list((primary_series or {}).get("bars") or [])
    if len(bars) != 240:
        return False
    ordinals = [_trading_minute_ordinal(row.get("datetime")) for row in bars]
    return ordinals == list(range(240))


def build_market_language_translation(
    projection,
    *,
    target_date,
    analysis_mode="fresh",
    artifact_origin="computed",
    include_posthoc=False,
):
    target_date = _date_text(target_date)
    if not target_date:
        raise ValueError("target_date must be YYYY-MM-DD")
    projection = projection if isinstance(projection, Mapping) else {}
    if projection.get("target_date") not in (None, "", target_date):
        raise ValueError("projection target_date does not match target_date")
    analysis_mode = "replay" if analysis_mode == "replay" else "fresh"
    sources = copy.deepcopy(list(projection.get("sources") or []))
    minute_series = list(projection.get("minute_series") or [])
    one_minute_series = [row for row in minute_series if row.get("granularity") == "one_minute"]
    primary_series = next(
        (row for row in one_minute_series if (row.get("instrument") or {}).get("type") == "index"),
        one_minute_series[0] if one_minute_series else None,
    )
    daily = copy.deepcopy(projection.get("daily") or {})
    evidence = []
    counter_evidence = []
    missing = list(projection.get("missing_evidence") or [])

    events = []
    latest_surface = {
        "slope_5m_bp_per_min": None,
        "slope_10m_bp_per_min": None,
        "slope_15m_bp_per_min": None,
        "slope_20m_bp_per_min": None,
        "slope_change_bp_per_min": None,
        "curvature_bp_per_min2": None,
        "pressure_direction": "unclear",
    }
    fixed_windows = []
    price_pressure = {
        "slope_5m_bp_per_min": None,
        "slope_10m_bp_per_min": None,
        "slope_20m_bp_per_min": None,
        "slope_change_bp_per_min": None,
        "drawdown_from_known_high_pct": None,
        "failed_rebound_count": 0,
        "source_refs": [],
        "as_of_time": None,
    }
    liquidity = {
        "impact_per_100m_turnover_bp": None,
        "impact_reversion_ratio": None,
        "below_vwap_dwell_minutes": None,
        "is_proxy": True,
        "source_refs": [],
        "as_of_time": None,
    }
    as_of_time = "15:00"
    if primary_series:
        bars = list(primary_series.get("bars") or [])
        evidence_id = "e-minute-price-path"
        events, latest_surface = _build_timeline_events(bars, evidence_id)
        fixed_windows = _fixed_window_observations(bars, evidence_id)
        known_high = max(row["high"] for row in bars) if bars else None
        price_pressure = {
            "slope_5m_bp_per_min": latest_surface["slope_5m_bp_per_min"],
            "slope_10m_bp_per_min": latest_surface["slope_10m_bp_per_min"],
            "slope_20m_bp_per_min": latest_surface["slope_20m_bp_per_min"],
            "slope_change_bp_per_min": latest_surface["slope_change_bp_per_min"],
            "drawdown_from_known_high_pct": (
                (bars[-1]["close"] / known_high - 1.0) * 100.0 if known_high else None
            ),
            "failed_rebound_count": _failed_rebound_count(bars),
            "source_refs": [primary_series["source_id"]],
            "as_of_time": bars[-1]["datetime"] if bars else None,
        }
        liquidity = _liquidity_proxies(primary_series, bars)
        as_of_time = bars[-1]["datetime"][11:16] if bars else "15:00"
        evidence.append(
            {
                "evidence_id": evidence_id,
                "fact": f"已读取{len(bars)}个可追溯的一分钟价格点，只描述价格压力，不确认交易账户身份。",
                "as_of_time": bars[-1]["datetime"] if bars else None,
                "source_refs": [primary_series["source_id"]],
            }
        )
    elif "one_minute_price_path" not in missing:
        missing.append("one_minute_price_path")

    cap = daily.get("cap_weighted") or {}
    breadth = daily.get("market_breadth") or {}
    sector = daily.get("sector_synchrony") or {}
    if cap:
        evidence.append(
            {
                "evidence_id": "e-cap-weighted",
                "fact": f"{cap.get('name') or '市值加权指数'}日终涨跌幅为{float(cap.get('return_pct')):.2f}%。",
                "as_of_time": "15:00",
                "source_refs": [cap.get("source_id")],
            }
        )
    else:
        missing.append("cap_weighted_index")
    if breadth:
        evidence.append(
            {
                "evidence_id": "e-market-breadth",
                "fact": f"上涨家数占可统计样本{float(breadth.get('advance_ratio_pct')):.2f}%。",
                "as_of_time": "15:00",
                "source_refs": [breadth.get("source_id")],
            }
        )
    else:
        missing.append("market_breadth")
    if sector:
        evidence.append(
            {
                "evidence_id": "e-sector-synchrony",
                "fact": "板块内部与跨板块同步事实已进入三层对照。",
                "as_of_time": "15:00",
                "source_refs": [sector.get("source_id")],
            }
        )
    else:
        missing.append("sector_synchrony")
    daily_participation = daily.get("participation") or {}
    if daily_participation.get("crowding_signal") is True:
        crowding_facts = daily_participation.get("crowding_evidence") or []
        evidence.append(
            {
                "evidence_id": "e-explicit-crowding-fact",
                "fact": (
                    "来源已明确标记向上参与拥挤：" + "；".join(crowding_facts)
                    if crowding_facts
                    else "来源已明确标记向上参与拥挤，但未提供可展开的细项。"
                ),
                "as_of_time": "15:00",
                "source_refs": [daily_participation.get("source_id")],
            }
        )

    daily_direction, votes = _daily_vote_direction(daily)
    direction = latest_surface.get("pressure_direction") if primary_series else daily_direction
    if direction not in VALID_DIRECTIONS:
        direction = "unclear"
    latest_active = next(
        (row for row in reversed(events) if row.get("invalidated_at") is None),
        None,
    )
    if direction in {"balanced", "unclear"}:
        active_direction = (latest_active or {}).get("pressure_direction")
        if active_direction in {"upward", "downward"}:
            direction = active_direction
        elif daily_direction in {"upward", "downward"}:
            direction = daily_direction
    if primary_series:
        same_direction_active = (
            latest_active
            if latest_active and latest_active.get("pressure_direction") == direction
            else None
        )
        phase = same_direction_active.get("phase") if same_direction_active else "unclear"
        if direction == "upward" and any(
            row.get("pressure_direction") == "downward" for row in events
        ):
            phase = "repair"
        elif phase == "unclear" and direction in {"upward", "downward"}:
            phase = "trigger"
        if phase not in VALID_PHASES_BY_DIRECTION.get(direction, {"unclear"}):
            phase = "unclear" if direction in {"balanced", "unclear"} else "trigger"
    elif direction in {"upward", "downward"}:
        aligned_count = sum(value == direction for value in votes)
        phase = "expansion" if aligned_count >= 2 else "trigger"
    else:
        phase = "unclear"
    if (
        direction == "upward"
        and phase != "repair"
        and daily_participation.get("crowding_signal") is True
    ):
        phase = "crowding"

    full_one_minute_session = _is_complete_one_minute_session(primary_series)
    if primary_series and full_one_minute_session:
        evidence_status = "sufficient"
    elif sources:
        evidence_status = "partial"
    else:
        evidence_status = "insufficient"
    if not primary_series and evidence_status != "insufficient":
        counter_evidence.append(
            {
                "evidence_id": "c-no-minute-timing",
                "fact": "缺少目标日一分钟价格路径，不能给出候选、确认或失效的精确时刻。",
                "as_of_time": "15:00",
                "source_refs": [row["source_id"] for row in sources],
            }
        )
    if cap and not breadth:
        counter_evidence.append(
            {
                "evidence_id": "c-index-not-whole-market",
                "fact": "只有市值加权指数事实，不能把指数外形直接提高为全市场合力。",
                "as_of_time": "15:00",
                "source_refs": [cap.get("source_id")],
            }
        )
    directional_signals = {
        value for value in votes if value in {"upward", "downward"}
    }
    if primary_series and direction in {"upward", "downward"}:
        directional_signals.add(direction)
    if latest_active and latest_active.get("pressure_direction") in {"upward", "downward"}:
        directional_signals.add(latest_active["pressure_direction"])
    if directional_signals == {"upward", "downward"}:
        counter_evidence.append(
            {
                "evidence_id": "c-aggregation-conflict",
                "fact": "分钟价格路径、指数、宽度或板块方向并不一致，合力范围需要降级。",
                "as_of_time": "15:00",
                "source_refs": [row["source_id"] for row in sources],
            }
        )
    for event in events:
        if event.get("confirmation_quality") != "slope_persistence_only":
            continue
        counter_evidence.append(
            {
                "evidence_id": f"c-slope-only-confirmation-{event['event_id']}",
                "fact": (
                    "连续三个重叠十五分钟斜率保持同向，但候选后没有出现达到噪声带的同向延续；"
                    "这里只能说明原冲击仍留在滚动窗口，不能单独确认持续资金压力或交易账户机制。"
                ),
                "as_of_time": event.get("causal_cutoff"),
                "source_refs": [primary_series["source_id"]] if primary_series else [],
            }
        )

    source_granularities = {
        row.get("granularity")
        for row in sources
        if row.get("granularity") in {"one_minute", "five_minute", "end_of_day"}
    }
    if len(source_granularities) > 1:
        data_granularity = "mixed"
    elif "one_minute" in source_granularities:
        data_granularity = "one_minute"
    elif "five_minute" in source_granularities:
        data_granularity = "five_minute"
    else:
        data_granularity = "end_of_day"

    confirmed_times = [row.get("confirmed_at") for row in events if row.get("confirmed_at")]
    transition_times = [
        value
        for row in events
        for value in (row.get("candidate_at"), row.get("confirmed_at"), row.get("invalidated_at"))
        if value
    ]
    aggregation = {
        "cap_weighted": {
            "return_pct": cap.get("return_pct"),
            "slope_bp_per_min": (
                latest_surface.get("slope_15m_bp_per_min")
                if ((primary_series or {}).get("instrument") or {}).get("type") == "index"
                else None
            ),
            "source_refs": [cap.get("source_id")] if cap else [],
            "as_of_time": "15:00" if cap else None,
        },
        "market_breadth": {
            "advance_ratio_pct": breadth.get("advance_ratio_pct"),
            "median_return_pct": breadth.get("median_return_pct"),
            "synchronized_down_pct": breadth.get("synchronized_down_pct"),
            "source_refs": [breadth.get("source_id")] if breadth else [],
            "as_of_time": "15:00" if breadth else None,
        },
        "sector_synchrony": {
            "leading_sector": sector.get("leading_sector"),
            "active_constituent_pct": sector.get("active_constituent_pct"),
            "cross_sector_sync_pct": sector.get("cross_sector_sync_pct"),
            "source_refs": [sector.get("source_id")] if sector else [],
            "as_of_time": "15:00" if sector else None,
        },
    }
    participation = dict(daily.get("participation") or {})
    participation.update(
        {
            "source_refs": [participation.get("source_id")] if participation.get("source_id") else [],
            "as_of_time": "15:00" if sources else None,
        }
    )
    participation.pop("source_id", None)
    artifact = {
        "schema_version": MARKET_LANGUAGE_SCHEMA_VERSION,
        "target_date": target_date,
        "primary_instrument": _normalized_instrument_identity(
            (primary_series or {}).get("instrument") or {}
        ),
        "as_of_time": as_of_time,
        "analysis_mode": analysis_mode,
        "artifact_origin": artifact_origin if artifact_origin in {"computed", "loaded", "reconstructed"} else "computed",
        "data_granularity": data_granularity,
        "evidence_status": evidence_status,
        "missing_evidence": sorted(set(missing)),
        "force_scope": _force_scope(primary_series, daily, direction),
        "pressure_direction": direction,
        "phase": phase,
        "phase_label": _phase_label(direction, phase),
        "timeline": {
            "first_candidate_at": events[0]["candidate_at"] if events else None,
            "latest_confirmed_at": max(confirmed_times) if confirmed_times else None,
            "candidate_invalidations": sum(row.get("invalidated_at") is not None for row in events),
            "latest_transition_at": max(transition_times) if transition_times else None,
            "events": events,
        },
        "aggregation_comparison": aggregation,
        "price_pressure": price_pressure,
        "participation": participation,
        "liquidity_proxies": liquidity,
        "fixed_window_observations": fixed_windows,
        "evidence": evidence,
        "counter_evidence": counter_evidence,
        "next_window_task": _next_window_task(as_of_time, direction, evidence_status),
        "posthoc_validation": None,
        "sources": sources,
    }
    if include_posthoc and analysis_mode == "replay":
        artifact["posthoc_validation"] = _posthoc_validation(artifact, primary_series, projection)
    return normalize_market_language_translation(artifact)


def attach_market_language_posthoc_validation(artifact, projection):
    normalized = normalize_market_language_translation(artifact)
    if normalized.get("analysis_mode") != "replay":
        raise ValueError("posthoc validation is replay-only")
    projection = projection if isinstance(projection, Mapping) else {}
    one_minute_series = [
        row
        for row in projection.get("minute_series") or []
        if isinstance(row, Mapping) and row.get("granularity") == "one_minute"
    ]
    primary_series = next(
        (row for row in one_minute_series if (row.get("instrument") or {}).get("type") == "index"),
        one_minute_series[0] if one_minute_series else None,
    )
    artifact_instrument = normalized.get("primary_instrument") or {}
    projection_instrument = (primary_series or {}).get("instrument") or {}
    if primary_series and not _instrument_identity_matches(
        artifact_instrument,
        projection_instrument,
    ):
        normalized["posthoc_validation"] = {
            "validation_status": "insufficient",
            "event_reviews": [],
            "t1_price_range": None,
            "t2_price_range": None,
            "fund_overlap": None,
            "trade_calendar": {},
            "missing_evidence": ["primary_instrument_identity_match"],
        }
        return normalize_market_language_translation(normalized)
    if primary_series:
        artifact_source_refs = set(
            (normalized.get("price_pressure") or {}).get("source_refs") or []
        )
        artifact_primary_source = next(
            (
                row
                for row in normalized.get("sources") or []
                if row.get("source_id") in artifact_source_refs
                and row.get("granularity") == "one_minute"
            ),
            None,
        )
        projection_primary_source = next(
            (
                row
                for row in projection.get("sources") or []
                if row.get("source_id") == primary_series.get("source_id")
                and row.get("granularity") == "one_minute"
            ),
            None,
        )
        artifact_content_hash = (artifact_primary_source or {}).get("content_hash")
        projection_content_hash = (projection_primary_source or {}).get("content_hash")
        if (
            not artifact_content_hash
            or not projection_content_hash
            or artifact_content_hash != projection_content_hash
        ):
            normalized["posthoc_validation"] = {
                "validation_status": "insufficient",
                "event_reviews": [],
                "t1_price_range": None,
                "t2_price_range": None,
                "fund_overlap": None,
                "trade_calendar": {},
                "missing_evidence": ["primary_minute_content_hash_match"],
            }
            return normalize_market_language_translation(normalized)
    normalized["posthoc_validation"] = _posthoc_validation(normalized, primary_series, projection)
    return normalize_market_language_translation(normalized)


def _normalize_recursive(value, *, field_name=""):
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{field_name or 'number'} must be finite")
        if field_name in _COUNT_FIELD_NAMES:
            return int(value)
        return float(value)
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        return {
            str(key): _normalize_recursive(item, field_name=str(key))
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_normalize_recursive(item, field_name=field_name) for item in value]
    raise ValueError(f"unsupported market language value: {type(value).__name__}")


def validate_market_language_translation(artifact):
    if not isinstance(artifact, Mapping):
        raise ValueError("market language artifact must be an object")
    if artifact.get("schema_version") != MARKET_LANGUAGE_SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {MARKET_LANGUAGE_SCHEMA_VERSION}")
    target_date = _date_text(artifact.get("target_date"))
    if not target_date or target_date != artifact.get("target_date"):
        raise ValueError("target_date must be YYYY-MM-DD")
    direction = artifact.get("pressure_direction")
    phase = artifact.get("phase")
    if direction not in VALID_DIRECTIONS or phase not in VALID_PHASES_BY_DIRECTION.get(direction, set()):
        raise ValueError("pressure_direction/phase combination is invalid")
    if artifact.get("force_scope") not in VALID_FORCE_SCOPES:
        raise ValueError("force_scope is invalid")
    if artifact.get("data_granularity") not in VALID_GRANULARITIES:
        raise ValueError("data_granularity is invalid")
    if artifact.get("evidence_status") not in VALID_EVIDENCE_STATUSES:
        raise ValueError("evidence_status is invalid")
    if artifact.get("analysis_mode") not in {"fresh", "replay"}:
        raise ValueError("analysis_mode is invalid")
    if artifact.get("analysis_mode") == "fresh" and artifact.get("posthoc_validation") is not None:
        raise ValueError("fresh artifact must not contain posthoc_validation")

    source_ids = set()
    for source in artifact.get("sources") or []:
        source_id = _text(source.get("source_id"))
        if not source_id or source_id in source_ids:
            raise ValueError("source_id must be unique and non-empty")
        source_ids.add(source_id)
        source_date = source.get("source_date")
        if source.get("target_date") != target_date or source_date != target_date:
            raise ValueError("source target_date/source_date must match artifact target_date")
        query_date = source.get("query_date")
        if query_date not in (None, ""):
            normalized_query_date = _date_text(query_date)
            if normalized_query_date != query_date:
                raise ValueError("source query_date must be YYYY-MM-DD or null")
            if normalized_query_date < source_date:
                raise ValueError("source query_date must not precede source_date")

    evidence_ids = {
        _text(row.get("evidence_id"))
        for row in [*(artifact.get("evidence") or []), *(artifact.get("counter_evidence") or [])]
        if _text(row.get("evidence_id"))
    }
    source_ref_rows = [
        *(artifact.get("evidence") or []),
        *(artifact.get("counter_evidence") or []),
        artifact.get("price_pressure") or {},
        artifact.get("participation") or {},
        artifact.get("liquidity_proxies") or {},
        *((artifact.get("aggregation_comparison") or {}).values()),
    ]
    for row in source_ref_rows:
        if not isinstance(row, Mapping):
            continue
        if any(reference not in source_ids for reference in row.get("source_refs") or []):
            raise ValueError("source_refs contain an unknown source id")
    events = ((artifact.get("timeline") or {}).get("events") or [])
    event_ids = set()
    for event in events:
        event_id = _text(event.get("event_id"))
        if not event_id or event_id in event_ids:
            raise ValueError("event_id must be unique and non-empty")
        event_ids.add(event_id)
        event_direction = event.get("pressure_direction")
        event_phase = event.get("phase")
        if event_phase not in VALID_PHASES_BY_DIRECTION.get(event_direction, set()):
            raise ValueError("event pressure_direction/phase combination is invalid")
        candidate_at = _normalize_timestamp(event.get("candidate_at"))
        detected_at = _normalize_timestamp(event.get("detected_at"))
        confirmed_at = _normalize_timestamp(event.get("confirmed_at")) if event.get("confirmed_at") else ""
        invalidated_at = _normalize_timestamp(event.get("invalidated_at")) if event.get("invalidated_at") else ""
        follow_through_at = (
            _normalize_timestamp(event.get("directional_follow_through_at"))
            if event.get("directional_follow_through_at")
            else ""
        )
        causal_cutoff = _normalize_timestamp(event.get("causal_cutoff"))
        if not candidate_at or not detected_at or not causal_cutoff:
            raise ValueError("event timestamps are incomplete")
        event_timestamps = (
            candidate_at,
            detected_at,
            confirmed_at,
            invalidated_at,
            follow_through_at,
            causal_cutoff,
        )
        if any(
            value and not value.startswith(f"{target_date} ")
            for value in event_timestamps
        ):
            raise ValueError("event timestamps must belong to artifact target_date")
        event_ordinals = {
            name: _trading_minute_ordinal(value)
            for name, value in (
                ("candidate_at", candidate_at),
                ("detected_at", detected_at),
                ("confirmed_at", confirmed_at),
                ("invalidated_at", invalidated_at),
                ("directional_follow_through_at", follow_through_at),
                ("causal_cutoff", causal_cutoff),
            )
            if value
        }
        if any(value is None for value in event_ordinals.values()):
            raise ValueError("event timestamps must be A-share minute interval ends")
        if candidate_at > detected_at or detected_at > causal_cutoff:
            raise ValueError("event timestamp order is invalid")
        if confirmed_at and (confirmed_at < detected_at or confirmed_at > causal_cutoff):
            raise ValueError("event confirmed_at is outside causal cutoff")
        if confirmed_at and (
            event_ordinals["confirmed_at"] - event_ordinals["detected_at"] < 2
        ):
            raise ValueError("event confirmed_at must follow three overlapping slope observations")
        if invalidated_at and (invalidated_at < candidate_at or invalidated_at > causal_cutoff):
            raise ValueError("event invalidated_at is outside causal cutoff")
        if follow_through_at and (
            follow_through_at < candidate_at or follow_through_at > causal_cutoff
        ):
            raise ValueError("event directional_follow_through_at is outside causal cutoff")
        if invalidated_at and confirmed_at and invalidated_at < confirmed_at:
            raise ValueError("event invalidated_at precedes confirmed_at")
        if invalidated_at and follow_through_at and invalidated_at < follow_through_at:
            raise ValueError("event invalidated_at precedes directional_follow_through_at")
        if event.get("confirmation_basis") != "three_overlapping_15m_slope_directions":
            raise ValueError("event confirmation_basis is invalid")
        confirmation_quality = event.get("confirmation_quality")
        if confirmation_quality not in {
            "unconfirmed",
            "slope_persistence_only",
            "directional_follow_through",
        }:
            raise ValueError("event confirmation_quality is invalid")
        if confirmed_at and confirmation_quality == "unconfirmed":
            raise ValueError("confirmed event must declare confirmation_quality")
        if not confirmed_at and confirmation_quality != "unconfirmed":
            raise ValueError("unconfirmed event has invalid confirmation_quality")
        if confirmation_quality == "slope_persistence_only" and follow_through_at:
            raise ValueError("slope-only confirmation must not contain follow-through")
        if confirmation_quality == "directional_follow_through" and not follow_through_at:
            raise ValueError("directional confirmation requires follow-through")
        if any(reference not in evidence_ids for reference in event.get("evidence_refs") or []):
            raise ValueError("event evidence_refs contain an unknown evidence id")

    for observation in artifact.get("fixed_window_observations") or []:
        window_cutoffs = {row[0]: row[2] for row in FIXED_WINDOW_SPECS}
        window = observation.get("window")
        if window not in window_cutoffs:
            raise ValueError("fixed window is invalid")
        observation_direction = observation.get("pressure_direction")
        observation_phase = observation.get("phase")
        if observation_phase not in VALID_PHASES_BY_DIRECTION.get(observation_direction, set()):
            raise ValueError("fixed window pressure_direction/phase combination is invalid")
        observation_as_of = _normalize_timestamp(observation.get("as_of_time"))
        expected_as_of = f"{target_date} {window_cutoffs[window]}:00"
        if observation_as_of != expected_as_of:
            raise ValueError("fixed window as_of_time must match its cutoff")
        if "action" in observation or "position_pct" in observation:
            raise ValueError("fixed window observation must not contain a trade action")
        if any(reference not in evidence_ids for reference in observation.get("evidence_refs") or []):
            raise ValueError("fixed window evidence_refs contain an unknown evidence id")
        if any(
            reference not in evidence_ids
            for reference in observation.get("counter_evidence_refs") or []
        ):
            raise ValueError("fixed window counter_evidence_refs contain an unknown evidence id")
    return True


def normalize_market_language_translation(artifact, *, validate=True):
    normalized = _normalize_recursive(copy.deepcopy(artifact))
    timeline = normalized.get("timeline") if isinstance(normalized, Mapping) else None
    if isinstance(timeline, Mapping):
        value = timeline.get("candidate_invalidations")
        if isinstance(value, float):
            timeline["candidate_invalidations"] = int(value)
    if validate:
        validate_market_language_translation(normalized)
    return normalized


__all__ = [
    "FIXED_WINDOW_SPECS",
    "MARKET_LANGUAGE_DIRECTION_SLOPE_EPSILON_BP_PER_MIN",
    "MARKET_LANGUAGE_SCHEMA_VERSION",
    "MARKET_LANGUAGE_SOURCE_POLICY",
    "SOURCE_PROJECTION_SCHEMA_VERSION",
    "attach_market_language_posthoc_validation",
    "build_market_language_source_projection",
    "build_market_language_translation",
    "canonical_market_language_hash",
    "market_language_linear_slope_bp_per_minute",
    "market_language_rolling_curvature_bp_per_minute2",
    "normalize_market_language_translation",
    "validate_market_language_translation",
]
