from __future__ import annotations

import math
from collections.abc import Mapping

import pandas as pd

from decision.chanlun.contracts import DEFAULT_CONFIRMATION_PERIOD
from decision.chanlun.runtime import (
    analyze_hybrid_structure as analyze_node_hybrid_structure,
    analyze_practical_daily_structure as analyze_node_practical_daily_structure,
)
from market_data.kline_dates import normalize_kline_date_str, parse_kline_date

DAILY_STRUCTURE_LOOKBACK_DAYS = 250
DAILY_REPORT_FOCUS_DAYS = 120
DAILY_CANDIDATE_MIN_KLINES = 20
REQUIRED_DAILY_COLUMNS = ("date", "high", "low")

__all__ = [
    "DAILY_CANDIDATE_MIN_KLINES",
    "DAILY_REPORT_FOCUS_DAYS",
    "DAILY_STRUCTURE_LOOKBACK_DAYS",
    "analyze_chanlun_zhongshu",
    "build_daily_structure_candidates",
    "build_chanlun_60m_structures",
    "build_platform_sequence_from_trend_types",
    "build_trend_types_from_bars",
    "confirm_daily_level_zhongshu",
]


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _strict_float(value):
    try:
        if pd.api.types.is_bool(value) or value in (None, ""):
            return None
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _safe_int(value, default=0):
    number = _strict_float(value)
    if number is None:
        return int(default)
    return int(number)


def _failure_result(status, error=None):
    result = {
        "success": False,
        "status": status,
        "daily_structure_candidates": [],
        "current_candidate": None,
        "daily_lookback_count": 0,
        "report_focus_count": 0,
    }
    if error:
        result["error"] = error
    return result


def _coerce_daily_frame(rows):
    if isinstance(rows, pd.DataFrame):
        return rows.copy()
    return pd.DataFrame(list(rows or []))


def _prepare_daily_rows(rows, target_date=None):
    frame = _coerce_daily_frame(rows)
    if frame.empty:
        return frame
    frame["date"] = frame["date"].map(normalize_kline_date_str)
    if "datetime" in frame.columns:
        frame["_dt"] = pd.to_datetime(frame["datetime"], errors="coerce")
        frame["_target_dt"] = frame["date"].map(parse_kline_date)
    else:
        frame["_dt"] = frame["date"].map(parse_kline_date)
        frame["_target_dt"] = frame["_dt"]
    frame = frame.dropna(subset=["_dt"]).sort_values("_dt").reset_index(drop=True)
    if target_date:
        target_dt = parse_kline_date(target_date)
        if target_dt is not None:
            frame = frame[frame["_target_dt"] < target_dt].reset_index(drop=True)
    return frame


def _trend_type_from_frame_slice(frame, start_idx, end_idx, direction, *, level, trend_type_id):
    segment = frame.iloc[start_idx : end_idx + 1]
    start_row = frame.iloc[start_idx]
    end_row = frame.iloc[end_idx]
    return {
        "trend_type_id": f"{level}_trend_{trend_type_id}",
        "level": level,
        "start_idx": int(start_idx),
        "end_idx": int(end_idx),
        "start_date": start_row["date"],
        "end_date": end_row["date"],
        "start_time": start_row.get("datetime", start_row["date"]) if hasattr(start_row, "get") else start_row["date"],
        "end_time": end_row.get("datetime", end_row["date"]) if hasattr(end_row, "get") else end_row["date"],
        "kline_count": int(end_idx - start_idx + 1),
        "high": float(segment["high"].max()),
        "low": float(segment["low"].min()),
        "start_close": _safe_float(start_row.get("close"), default=_safe_float(start_row.get("high"))),
        "end_close": _safe_float(end_row.get("close"), default=_safe_float(end_row.get("low"))),
        "direction": direction or "flat",
        "status": "completed_trend_type",
    }


def _direction_between(prev_close, next_close, fallback=None):
    prev_close = _safe_float(prev_close)
    next_close = _safe_float(next_close)
    if next_close > prev_close:
        return "up"
    if next_close < prev_close:
        return "down"
    return fallback or "flat"


def _ensure_close_column(frame):
    if "close" in frame.columns:
        frame["close"] = frame["close"].map(_safe_float)
    else:
        frame["close"] = (frame["high"].map(_safe_float) + frame["low"].map(_safe_float)) / 2.0
    return frame


def build_trend_types_from_bars(rows, *, target_date=None, level="daily"):
    frame = _coerce_daily_frame(rows)
    if frame.empty:
        return []
    missing_columns = [column for column in REQUIRED_DAILY_COLUMNS if column not in frame.columns]
    if missing_columns:
        return []
    frame = _prepare_daily_rows(frame, target_date=target_date)
    if frame.empty or len(frame) < 2:
        return []
    frame["high"] = frame["high"].map(_safe_float)
    frame["low"] = frame["low"].map(_safe_float)
    frame = _ensure_close_column(frame)
    frame = frame.dropna(subset=["high", "low", "close"]).reset_index(drop=True)
    if len(frame) < 2:
        return []

    trend_types = []
    start_idx = 0
    direction = None
    for idx in range(1, len(frame)):
        next_direction = _direction_between(frame.iloc[idx - 1]["close"], frame.iloc[idx]["close"], fallback=direction)
        if direction is None:
            direction = next_direction
            continue
        if next_direction == "flat" or next_direction == direction:
            continue
        trend_types.append(
            _trend_type_from_frame_slice(
                frame,
                start_idx,
                idx - 1,
                direction,
                level=level,
                trend_type_id=len(trend_types) + 1,
            )
        )
        start_idx = idx - 1
        direction = next_direction

    trend_types.append(
        _trend_type_from_frame_slice(
            frame,
            start_idx,
            len(frame) - 1,
            direction or "flat",
            level=level,
            trend_type_id=len(trend_types) + 1,
        )
    )
    return trend_types


def _normalize_trend_type(item, *, index=0, level="daily"):
    if not isinstance(item, Mapping):
        return None
    high = _strict_float(item.get("high", item.get("zg")))
    low = _strict_float(item.get("low", item.get("zd")))
    if high is None or low is None or high <= low:
        return None
    start_date = item.get("start_date") or item.get("start_time") or item.get("datetime") or f"{level}-{index}-start"
    end_date = item.get("end_date") or item.get("end_time") or item.get("datetime") or f"{level}-{index}-end"
    return {
        **dict(item),
        "trend_type_id": item.get("trend_type_id") or f"{level}_trend_{index + 1}",
        "level": item.get("level") or level,
        "start_date": start_date,
        "end_date": end_date,
        "start_time": item.get("start_time") or start_date,
        "end_time": item.get("end_time") or end_date,
        "high": float(high),
        "low": float(low),
        "direction": item.get("direction") or "unknown",
        "status": item.get("status") or "completed_trend_type",
        "kline_count": _safe_int(item.get("kline_count"), default=1) or 1,
    }


def _trend_type_overlap(trend_types):
    normalized = []
    for index, item in enumerate(trend_types):
        unit = _normalize_trend_type(item, index=index)
        if unit is None:
            return None
        normalized.append(unit)
    if len(normalized) < 3:
        return None
    zg = min(item["high"] for item in normalized[:3])
    zd = max(item["low"] for item in normalized[:3])
    if zg <= zd:
        return None
    return {"zg": float(zg), "zd": float(zd)}


def _unit_range_intersects_zone(unit, zone):
    unit = _normalize_trend_type(unit)
    if unit is None or not zone:
        return False
    return min(unit["high"], zone["zg"]) > max(unit["low"], zone["zd"])


def _segment_bounds_from_units(units):
    high = max(item["high"] for item in units)
    low = min(item["low"] for item in units)
    return float(high), float(low)


def _kline_count_from_units(units):
    if not units:
        return 0
    total = sum(max(_safe_int(item.get("kline_count"), default=1), 1) for item in units)
    return max(total - max(0, len(units) - 1), 1)


def _build_platform_segment(units, core_units, zone, *, level, sequence_id):
    high, low = _segment_bounds_from_units(units)
    first = units[0]
    last = units[-1]
    segment = {
        "segment_type": "zhongshu",
        "structure_kind": "platform",
        "zhongshu_id": f"{level}_platform_{sequence_id}",
        "level": level,
        "start_date": first["start_date"],
        "end_date": last["end_date"],
        "start_time": first.get("start_time", first["start_date"]),
        "end_time": last.get("end_time", last["end_date"]),
        "kline_count": _kline_count_from_units(units),
        "trend_type_count": len(units),
        "platform_core_unit_count": len(core_units),
        "core_trend_type_ids": [item.get("trend_type_id") for item in core_units],
        "trend_type_ids": [item.get("trend_type_id") for item in units],
        "zg": float(zone["zg"]),
        "zd": float(zone["zd"]),
        "zg_candidate": float(zone["zg"]),
        "zd_candidate": float(zone["zd"]),
        "high": high,
        "low": low,
        "segment_high": high,
        "segment_low": low,
        "start_close": _safe_float(first.get("start_close"), default=first["low"]),
        "end_close": _safe_float(last.get("end_close"), default=last["high"]),
        "candidate_status": "confirmed_platform",
        "confirmation_status": "confirmed",
        "reason": "至少三个连续走势类型存在重叠，按平台/中枢处理",
    }
    return segment


def _build_connector_segment(units, *, level, sequence_id):
    high, low = _segment_bounds_from_units(units)
    first = units[0]
    last = units[-1]
    return {
        "segment_type": "connector",
        "structure_kind": "connecting_line",
        "connector_id": f"{level}_connector_{sequence_id}",
        "level": level,
        "start_date": first["start_date"],
        "end_date": last["end_date"],
        "start_time": first.get("start_time", first["start_date"]),
        "end_time": last.get("end_time", last["end_date"]),
        "kline_count": _kline_count_from_units(units),
        "trend_type_count": len(units),
        "trend_type_ids": [item.get("trend_type_id") for item in units],
        "high": high,
        "low": low,
        "segment_high": high,
        "segment_low": low,
        "start_close": _safe_float(first.get("start_close"), default=first["low"]),
        "end_close": _safe_float(last.get("end_close"), default=last["high"]),
        "reason": "平台之间的一个连接走势；多个细分走势在同级别分解中合并为一条连接线",
    }


def build_platform_sequence_from_trend_types(trend_types, *, level="daily"):
    units = []
    for index, item in enumerate(_coerce_structure_sequence(trend_types)):
        normalized = _normalize_trend_type(item, index=index, level=level)
        if normalized is not None:
            units.append(normalized)
    if not units:
        return [], []

    segments = []
    platforms = []
    connector_units = []
    index = 0
    platform_count = 0
    connector_count = 0

    while index <= len(units) - 3:
        core_units = units[index : index + 3]
        zone = _trend_type_overlap(core_units)
        if zone is None:
            connector_units.append(units[index])
            index += 1
            continue

        if connector_units:
            connector_count += 1
            segments.append(_build_connector_segment(connector_units, level=level, sequence_id=connector_count))
            connector_units = []
        elif segments and segments[-1].get("segment_type") == "zhongshu":
            connector_count += 1
            bridge = _build_connector_segment([units[index]], level=level, sequence_id=connector_count)
            bridge["shared_with_next_platform"] = True
            bridge["reason"] = "相邻平台之间显式保留一条桥接连接线，避免平台直接贴平台"
            segments.append(bridge)

        platform_units = list(core_units)
        next_index = index + 3
        while next_index < len(units) and _unit_range_intersects_zone(units[next_index], zone):
            platform_units.append(units[next_index])
            next_index += 1

        platform_count += 1
        platform = _build_platform_segment(platform_units, core_units, zone, level=level, sequence_id=platform_count)
        segments.append(platform)
        platforms.append(platform.copy())
        index = next_index

    if index < len(units):
        connector_units.extend(units[index:])
    if connector_units:
        connector_count += 1
        segments.append(_build_connector_segment(connector_units, level=level, sequence_id=connector_count))

    for idx, segment in enumerate(segments):
        if segment.get("segment_type") != "connector":
            continue
        has_prev_platform = any(item.get("segment_type") == "zhongshu" for item in segments[:idx])
        has_next_platform = any(item.get("segment_type") == "zhongshu" for item in segments[idx + 1 :])
        if has_prev_platform and has_next_platform:
            segment["connector_role"] = "between"
        elif has_prev_platform:
            segment["connector_role"] = "trailing"
        else:
            segment["connector_role"] = "leading"

    return segments, platforms


def _candidate_from_platform(platform):
    if not platform:
        return None
    return {
        "start_date": platform.get("start_date"),
        "end_date": platform.get("end_date"),
        "kline_count": int(platform.get("kline_count") or 0),
        "trend_type_count": int(platform.get("trend_type_count") or 0),
        "platform_core_unit_count": int(platform.get("platform_core_unit_count") or 0),
        "high": float(platform.get("high", platform.get("segment_high", platform.get("zg", 0.0)))),
        "low": float(platform.get("low", platform.get("segment_low", platform.get("zd", 0.0)))),
        "zg_candidate": float(platform.get("zg")),
        "zd_candidate": float(platform.get("zd")),
        "zg": float(platform.get("zg")),
        "zd": float(platform.get("zd")),
        "candidate_status": platform.get("candidate_status") or "confirmed_platform",
        "confirmation_status": platform.get("confirmation_status") or "confirmed",
        "structure_kind": "platform",
        "trend_type_ids": list(platform.get("trend_type_ids") or []),
        "core_trend_type_ids": list(platform.get("core_trend_type_ids") or []),
        "mainline": "-",
        "mainline_state": "结构平台",
    }


def build_daily_structure_candidates(rows, *, target_date=None, min_daily_klines=DAILY_CANDIDATE_MIN_KLINES):
    del min_daily_klines
    frame = _coerce_daily_frame(rows)
    if frame.empty:
        return _failure_result("empty_daily_bars")
    missing_columns = [column for column in REQUIRED_DAILY_COLUMNS if column not in frame.columns]
    if missing_columns:
        missing_text = ", ".join(missing_columns)
        return _failure_result("invalid_daily_bars", error=f"missing required columns: {missing_text}")
    frame = _prepare_daily_rows(frame, target_date=target_date)
    if frame.empty:
        return _failure_result("empty_daily_bars")
    base = frame.tail(DAILY_STRUCTURE_LOOKBACK_DAYS).reset_index(drop=True)
    trend_types = build_trend_types_from_bars(base, level="daily")
    structure_segments, platforms = build_platform_sequence_from_trend_types(trend_types, level="daily")
    current = _candidate_from_platform(platforms[-1]) if platforms else None
    return {
        "success": True,
        "status": "success" if current else "not_yet_platform",
        "daily_structure_candidates": [_candidate_from_platform(item) for item in platforms],
        "current_candidate": current,
        "daily_lookback_count": int(len(base)),
        "report_focus_count": min(int(len(base)), DAILY_REPORT_FOCUS_DAYS),
        "daily_trend_types": trend_types,
        "daily_structure_segments": structure_segments,
    }


def _coerce_structure_sequence(structures):
    if structures is None:
        return []
    if isinstance(structures, Mapping):
        return [structures]
    if isinstance(structures, (str, bytes)):
        return []
    try:
        return list(structures)
    except TypeError:
        return []


def _coerce_minute_bar_sequence(minute_bars):
    if minute_bars is None:
        return []
    if isinstance(minute_bars, Mapping):
        return [minute_bars]
    if isinstance(minute_bars, (str, bytes)):
        return []
    try:
        return list(minute_bars)
    except TypeError:
        return []


def _normalize_60m_structure(item):
    if not isinstance(item, Mapping):
        return None
    zg = _strict_float(item.get("zg", item.get("high")))
    zd = _strict_float(item.get("zd", item.get("low")))
    if zg is None or zd is None or zg <= zd:
        return None
    return {"zg": zg, "zd": zd}


def _overlap_range(raw_structures):
    if not raw_structures:
        return None
    structures = []
    for item in raw_structures:
        normalized = _normalize_60m_structure(item)
        if normalized is None:
            return None
        structures.append(normalized)
    zg = min(item["zg"] for item in structures)
    zd = max(item["zd"] for item in structures)
    if zg <= zd:
        return None
    return {"zg": float(zg), "zd": float(zd)}


def confirm_daily_level_zhongshu(candidate, chanlun_60m_structures):
    if not isinstance(candidate, Mapping):
        candidate = {}
    structures = _coerce_structure_sequence(chanlun_60m_structures)
    if len(structures) < 3:
        return {
            "confirmed": False,
            "confirmation_status": "insufficient_60m_history",
            "trend_type_count": len(structures),
            "zg": None,
            "zd": None,
            "explanation": "60分钟走势类型不足3段，不能确认日线级别缠论中枢。",
        }
    overlap = _overlap_range(structures[:3])
    if not overlap:
        return {
            "confirmed": False,
            "confirmation_status": "not_confirmed",
            "trend_type_count": len(structures[:3]),
            "zg": None,
            "zd": None,
            "explanation": "前三个60分钟走势类型没有重叠区间。",
        }
    return {
        "confirmed": True,
        "confirmation_status": "confirmed_daily_level_zhongshu",
        "trend_type_count": 3,
        "zg": overlap["zg"],
        "zd": overlap["zd"],
        "explanation": "至少三个连续60分钟走势类型存在重叠，日线级别平台/中枢成立。",
    }


def build_chanlun_60m_structures(minute_bars):
    bars = _coerce_minute_bar_sequence(minute_bars)
    if not bars:
        return []
    normalized_rows = []
    for item in bars:
        if not isinstance(item, Mapping):
            return []
        high = _strict_float(item.get("high"))
        low = _strict_float(item.get("low"))
        if high is None or low is None or high <= low:
            return []
        close = _strict_float(item.get("close"))
        if close is None:
            close = (high + low) / 2.0
        dt = item.get("datetime") or item.get("date")
        normalized_rows.append(
            {
                "date": item.get("date") or str(dt or ""),
                "datetime": dt,
                "open": _safe_float(item.get("open"), default=close),
                "high": high,
                "low": low,
                "close": close,
                "volume": _safe_float(item.get("volume"), default=0.0),
                "amount": _safe_float(item.get("amount"), default=0.0),
            }
        )
    return build_trend_types_from_bars(normalized_rows, level="60m")


def _legacy_platform_aliases(platform, trend_types):
    if not isinstance(platform, Mapping):
        return platform
    enriched = dict(platform)
    trend_by_id = {item.get("trend_type_id"): item for item in trend_types if isinstance(item, Mapping)}
    trend_type_ids = list(enriched.get("trend_type_ids") or [])
    core_type_ids = list(enriched.get("child_trend_type_ids") or enriched.get("core_trend_type_ids") or [])
    units = [trend_by_id[item_id] for item_id in trend_type_ids if item_id in trend_by_id]
    core_units = [trend_by_id[item_id] for item_id in core_type_ids if item_id in trend_by_id]

    if units:
        first = units[0]
        last = units[-1]
        enriched.setdefault("start_date", first.get("start_date") or first.get("date"))
        enriched.setdefault("end_date", last.get("end_date") or last.get("date"))
        enriched.setdefault("start_time", first.get("start_time") or first.get("datetime") or enriched.get("start_date"))
        enriched.setdefault("end_time", last.get("end_time") or last.get("datetime") or enriched.get("end_date"))
        enriched.setdefault("kline_count", len(units))
        enriched.setdefault("trend_type_count", len(units))
        enriched.setdefault("high", max(_safe_float(item.get("high")) for item in units))
        enriched.setdefault("low", min(_safe_float(item.get("low")) for item in units))
    else:
        enriched.setdefault("trend_type_count", len(trend_type_ids))

    enriched.setdefault("platform_core_unit_count", len(core_units) or len(core_type_ids))
    if "ZG" in enriched:
        enriched.setdefault("zg", enriched.get("ZG"))
        enriched.setdefault("zg_candidate", enriched.get("ZG"))
    if "ZD" in enriched:
        enriched.setdefault("zd", enriched.get("ZD"))
        enriched.setdefault("zd_candidate", enriched.get("ZD"))
    if enriched.get("segment_type") == "zhongshu":
        enriched.setdefault("structure_kind", "platform")
    if enriched.get("status") == "confirmed":
        enriched.setdefault("candidate_status", "confirmed_platform")
        enriched.setdefault("confirmation_status", "confirmed")
    enriched.setdefault("mainline", "-")
    enriched.setdefault("mainline_state", "结构平台")
    return enriched


def _legacy_confirmation_aliases(confirmation):
    if not isinstance(confirmation, Mapping):
        return confirmation or {}
    enriched = dict(confirmation)
    if "ZG" in enriched:
        enriched.setdefault("zg", enriched.get("ZG"))
    if "ZD" in enriched:
        enriched.setdefault("zd", enriched.get("ZD"))
    return enriched


def _with_legacy_aliases(node_result, *, minute_source_error=None):
    result = dict(node_result or {})
    trend_types = list(result.get("daily_trend_types") or [])
    candidates = [
        _legacy_platform_aliases(candidate, trend_types)
        for candidate in list(result.get("daily_structure_candidates") or [])
    ]
    current = result.get("current_candidate")
    if current is not None:
        current = _legacy_platform_aliases(current, trend_types)

    confirmation = _legacy_confirmation_aliases(result.get("minute_confirmation"))
    result["daily_structure_candidates"] = candidates
    result["current_candidate"] = current
    result["minute_confirmation"] = confirmation
    result["chanlun_60m_structures"] = list(result.get("child_trend_types") or [])
    result["chanlun_confirmation"] = confirmation
    if minute_source_error is not None:
        result["minute_source_error"] = minute_source_error
    elif "minute_source_status" in result:
        result.setdefault("minute_source_error", None)
    return result


def analyze_chanlun_zhongshu(
    *,
    daily_rows,
    target_date=None,
    fetch_minute_bars=None,
    index_code="sh.000001",
    minute_period=DEFAULT_CONFIRMATION_PERIOD,
    min_daily_klines=DAILY_CANDIDATE_MIN_KLINES,
    use_hybrid_confirmation=False,
):
    del min_daily_klines
    if use_hybrid_confirmation and fetch_minute_bars is not None:
        minute_source_error = None

        def fetch_legacy_minute_trend_types(**kwargs):
            nonlocal minute_source_error
            try:
                minute_result = fetch_minute_bars(**kwargs)
            except Exception as exc:
                minute_source_error = str(exc)
                return {"status": "minute_fetch_failed", "error": minute_source_error, "bars": []}
            if not isinstance(minute_result, Mapping):
                minute_source_error = "minute fetch returned non-dict payload"
                return {"status": "invalid_minute_payload", "error": minute_source_error, "bars": []}
            return {
                **dict(minute_result),
                "bars": build_chanlun_60m_structures(minute_result.get("bars")),
            }

        result = analyze_node_hybrid_structure(
            daily_rows=daily_rows,
            fetch_minute_bars=fetch_legacy_minute_trend_types,
            target_date=target_date,
            index_code=index_code,
            minute_period=minute_period,
        )
        return _with_legacy_aliases(result, minute_source_error=minute_source_error)

    result = analyze_node_practical_daily_structure(
        daily_rows=daily_rows,
        fetch_minute_bars=fetch_minute_bars,
        target_date=target_date,
    )
    return _with_legacy_aliases(result)
