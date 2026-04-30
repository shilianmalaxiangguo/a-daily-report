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
    "aggregate_daily_macro_platforms",
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


def _build_synthetic_bridge_segment(prev_segment, next_unit, *, level, sequence_id):
    start_date = prev_segment.get("end_date")
    end_date = next_unit.get("start_date", start_date)
    start_time = prev_segment.get("end_time", start_date)
    end_time = next_unit.get("start_time", end_date)
    start_close = _safe_float(prev_segment.get("end_close"), default=_safe_float(prev_segment.get("high")))
    end_close = _safe_float(next_unit.get("start_close"), default=_safe_float(next_unit.get("low")))
    high = max(start_close, end_close)
    low = min(start_close, end_close)
    return {
        "segment_type": "connector",
        "structure_kind": "connecting_line",
        "connector_id": f"{level}_connector_{sequence_id}",
        "level": level,
        "start_date": start_date,
        "end_date": end_date,
        "start_time": start_time,
        "end_time": end_time,
        "kline_count": 0,
        "trend_type_count": 0,
        "trend_type_ids": [],
        "high": float(high),
        "low": float(low),
        "segment_high": float(high),
        "segment_low": float(low),
        "start_close": float(start_close),
        "end_close": float(end_close),
        "synthetic_bridge": True,
        "reason": "相邻平台之间的边界连接线；不重复占用下一平台走势类型",
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
            bridge = _build_synthetic_bridge_segment(
                segments[-1],
                units[index],
                level=level,
                sequence_id=connector_count,
            )
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


def _segment_price_high(segment):
    return _safe_float(
        segment.get("high", segment.get("segment_high", segment.get("zg", segment.get("ZG", 0.0))))
    )


def _segment_price_low(segment):
    return _safe_float(
        segment.get("low", segment.get("segment_low", segment.get("zd", segment.get("ZD", 0.0))))
    )


def _bounded_visual_range(zg, zd, high, low):
    del zg, zd
    return float(_safe_float(high)), float(_safe_float(low))


def _segment_kline_count(segment):
    return max(_safe_int(segment.get("kline_count"), default=1), 1)


def _cluster_kline_count(cluster):
    if not cluster:
        return 0
    total = sum(_segment_kline_count(segment) for segment in cluster)
    return max(total - max(0, len(cluster) - 1), 1)


def _copy_segment_with_macro_aliases(segment):
    copied = dict(segment)
    high = _segment_price_high(copied)
    low = _segment_price_low(copied)
    copied.setdefault("high", high)
    copied.setdefault("low", low)
    copied.setdefault("segment_high", high)
    copied.setdefault("segment_low", low)
    visual_high, visual_low = _bounded_visual_range(
        copied.get("zg", copied.get("ZG")),
        copied.get("zd", copied.get("ZD")),
        high,
        low,
    )
    copied.setdefault("visual_high", visual_high)
    copied.setdefault("visual_low", visual_low)
    copied.setdefault("rule_tier", "original_rule")
    return copied


def _core_ranges_overlap(left, right):
    left_zg = _strict_float(left.get("zg", left.get("ZG")))
    left_zd = _strict_float(left.get("zd", left.get("ZD")))
    right_zg = _strict_float(right.get("zg", right.get("ZG")))
    right_zd = _strict_float(right.get("zd", right.get("ZD")))
    if left_zg is None or left_zd is None or right_zg is None or right_zd is None:
        return False
    return min(left_zg, right_zg) > max(left_zd, right_zd)


MIN_CONFIRMED_PLATFORM_KLINES = 3
CENTER_MIGRATION_PRICE_PCT_LIMIT = 0.075
CENTER_MIGRATION_ENVELOPE_RATIO_LIMIT = 0.22


def _platform_core_bounds(platform):
    zg = _strict_float(platform.get("zg", platform.get("ZG")))
    zd = _strict_float(platform.get("zd", platform.get("ZD")))
    if zg is None or zd is None:
        high = _strict_float(platform.get("high", platform.get("segment_high")))
        low = _strict_float(platform.get("low", platform.get("segment_low")))
        if high is None or low is None:
            return None
        zg = high
        zd = low
    return max(zg, zd), min(zg, zd)


def _platform_core_center(platform):
    bounds = _platform_core_bounds(platform)
    if bounds is None:
        return None
    zg, zd = bounds
    return (zg + zd) / 2


def _has_large_center_migration(reference_platform, candidate_platform):
    if _core_ranges_overlap(reference_platform, candidate_platform):
        return False
    reference_bounds = _platform_core_bounds(reference_platform)
    reference_center = _platform_core_center(reference_platform)
    candidate_center = _platform_core_center(candidate_platform)
    if reference_bounds is None or reference_center is None or candidate_center is None:
        return False
    reference_zg, reference_zd = reference_bounds
    candidate_outside_reference_core = candidate_center > reference_zg or candidate_center < reference_zd
    if not candidate_outside_reference_core:
        return False
    reference_span = max(_segment_price_high(reference_platform) - _segment_price_low(reference_platform), 0.01)
    price_base = max(abs(reference_center), 0.01)
    center_shift = abs(candidate_center - reference_center)
    price_pct = center_shift / price_base
    envelope_ratio = center_shift / reference_span
    return (
        price_pct >= CENTER_MIGRATION_PRICE_PCT_LIMIT
        and envelope_ratio >= CENTER_MIGRATION_ENVELOPE_RATIO_LIMIT
    )


def _merge_macro_platform_pair(left, right, *, level, sequence_id):
    high = max(_segment_price_high(left), _segment_price_high(right))
    low = min(_segment_price_low(left), _segment_price_low(right))
    core_zg = min(_safe_float(left.get("zg", left.get("ZG"))), _safe_float(right.get("zg", right.get("ZG"))))
    core_zd = max(_safe_float(left.get("zd", left.get("ZD"))), _safe_float(right.get("zd", right.get("ZD"))))
    visual_high, visual_low = _bounded_visual_range(core_zg, core_zd, high, low)
    trend_type_ids = list(left.get("trend_type_ids") or []) + list(right.get("trend_type_ids") or [])
    core_trend_type_ids = list(left.get("core_trend_type_ids") or []) + list(right.get("core_trend_type_ids") or [])
    source_segment_ids = list(left.get("source_segment_ids") or [left.get("zhongshu_id")]) + list(
        right.get("source_segment_ids") or [right.get("zhongshu_id")]
    )
    return {
        **left,
        "segment_type": "zhongshu",
        "structure_kind": "platform",
        "zhongshu_id": f"{level}_macro_platform_{sequence_id}",
        "level": level,
        "start_date": left.get("start_date"),
        "end_date": right.get("end_date"),
        "start_time": left.get("start_time", left.get("start_date")),
        "end_time": right.get("end_time", right.get("end_date")),
        "kline_count": _cluster_kline_count([left, right]),
        "trend_type_count": _safe_int(left.get("trend_type_count"), default=0)
        + _safe_int(right.get("trend_type_count"), default=0),
        "platform_core_unit_count": _safe_int(left.get("platform_core_unit_count"), default=0)
        + _safe_int(right.get("platform_core_unit_count"), default=0),
        "core_trend_type_ids": [item for item in core_trend_type_ids if item],
        "trend_type_ids": [item for item in trend_type_ids if item],
        "source_segment_ids": [item for item in source_segment_ids if item],
        "source_segment_count": _safe_int(left.get("source_segment_count"), default=1)
        + _safe_int(right.get("source_segment_count"), default=1),
        "raw_platform_count": _safe_int(left.get("raw_platform_count"), default=1)
        + _safe_int(right.get("raw_platform_count"), default=1),
        "zg": float(core_zg),
        "zd": float(core_zd),
        "zg_candidate": float(core_zg),
        "zd_candidate": float(core_zd),
        "high": float(high),
        "low": float(low),
        "segment_high": float(high),
        "segment_low": float(low),
        "visual_high": visual_high,
        "visual_low": visual_low,
        "start_close": _safe_float(left.get("start_close"), default=_segment_price_low(left)),
        "end_close": _safe_float(right.get("end_close"), default=_segment_price_high(right)),
        "candidate_status": "confirmed_platform",
        "confirmation_status": "confirmed",
        "rule_tier": "daily_macro_core_overlap_merged",
        "reason": "相邻平台核心区间重叠，按同一日线中枢延伸合并处理",
    }


def _merge_macro_platform_pair_with_connectors(left, right, connectors, *, level, sequence_id):
    merged = _merge_macro_platform_pair(left, right, level=level, sequence_id=sequence_id)
    if not connectors:
        return merged
    cluster = [left, *connectors, right]
    high = max(_segment_price_high(segment) for segment in cluster)
    low = min(_segment_price_low(segment) for segment in cluster)
    trend_type_ids = list(merged.get("trend_type_ids") or [])
    source_segment_ids = list(merged.get("source_segment_ids") or [])
    for connector in connectors:
        trend_type_ids.extend(list(connector.get("trend_type_ids") or []))
        source_segment_ids.append(connector.get("connector_id") or f"{level}_connector_{len(source_segment_ids) + 1}")
    merged.update(
        {
            "kline_count": _cluster_kline_count(cluster),
            "trend_type_count": sum(_safe_int(segment.get("trend_type_count"), default=0) for segment in cluster),
            "trend_type_ids": [item for item in trend_type_ids if item],
            "source_segment_ids": [item for item in source_segment_ids if item],
            "source_segment_count": len(cluster),
            "high": float(high),
            "low": float(low),
            "segment_high": float(high),
            "segment_low": float(low),
            "visual_high": float(high),
            "visual_low": float(low),
        }
    )
    return merged


def _merge_envelope_platform_pair(left, right, *, level, sequence_id):
    high = max(_segment_price_high(left), _segment_price_high(right))
    low = min(_segment_price_low(left), _segment_price_low(right))
    trend_type_ids = list(left.get("trend_type_ids") or []) + list(right.get("trend_type_ids") or [])
    core_trend_type_ids = list(left.get("core_trend_type_ids") or []) + list(right.get("core_trend_type_ids") or [])
    source_segment_ids = list(left.get("source_segment_ids") or [left.get("zhongshu_id")]) + list(
        right.get("source_segment_ids") or [right.get("zhongshu_id")]
    )
    return {
        **left,
        "segment_type": "zhongshu",
        "structure_kind": "platform",
        "zhongshu_id": f"{level}_macro_envelope_platform_{sequence_id}",
        "level": level,
        "end_date": right.get("end_date"),
        "end_time": right.get("end_time", right.get("end_date")),
        "kline_count": _cluster_kline_count([left, right]),
        "trend_type_count": _safe_int(left.get("trend_type_count"), default=0)
        + _safe_int(right.get("trend_type_count"), default=0),
        "platform_core_unit_count": _safe_int(left.get("platform_core_unit_count"), default=0)
        + _safe_int(right.get("platform_core_unit_count"), default=0),
        "core_trend_type_ids": [item for item in core_trend_type_ids if item],
        "trend_type_ids": [item for item in trend_type_ids if item],
        "source_segment_ids": [item for item in source_segment_ids if item],
        "source_segment_count": _safe_int(left.get("source_segment_count"), default=1)
        + _safe_int(right.get("source_segment_count"), default=1),
        "raw_platform_count": _safe_int(left.get("raw_platform_count"), default=1)
        + _safe_int(right.get("raw_platform_count"), default=1),
        "high": float(high),
        "low": float(low),
        "segment_high": float(high),
        "segment_low": float(low),
        "visual_high": float(high),
        "visual_low": float(low),
        "end_close": _safe_float(right.get("end_close"), default=_segment_price_high(right)),
        "candidate_status": "confirmed_platform",
        "confirmation_status": "confirmed",
        "rule_tier": "daily_macro_envelope_merged",
        "reason": "后续小平台未被整根K线确认脱离宏观平台包络，按同一稳定中枢延伸合并处理",
    }


def _collapse_connector_segments(
    connectors,
    *,
    level,
    sequence_id,
    connector_role,
    prev_platform=None,
    next_platform=None,
):
    connectors = [connector for connector in connectors if connector.get("segment_type") == "connector"]
    if not connectors and prev_platform and next_platform:
        return _build_macro_connector(prev_platform, next_platform, level=level, sequence_id=sequence_id)
    if not connectors:
        return None
    first = connectors[0]
    last = connectors[-1]
    high = max(_segment_price_high(connector) for connector in connectors)
    low = min(_segment_price_low(connector) for connector in connectors)
    trend_type_ids = []
    source_segment_ids = []
    for connector in connectors:
        trend_type_ids.extend(list(connector.get("trend_type_ids") or []))
        source_segment_ids.append(connector.get("connector_id") or f"{level}_connector_{len(source_segment_ids) + 1}")
    return {
        "segment_type": "connector",
        "structure_kind": "connecting_line",
        "connector_id": f"{level}_macro_connector_{sequence_id}",
        "level": level,
        "start_date": first.get("start_date") or (prev_platform or {}).get("end_date"),
        "end_date": last.get("end_date") or (next_platform or {}).get("start_date"),
        "start_time": first.get("start_time", first.get("start_date")),
        "end_time": last.get("end_time", last.get("end_date")),
        "kline_count": _cluster_kline_count(connectors),
        "trend_type_count": sum(_safe_int(connector.get("trend_type_count"), default=0) for connector in connectors),
        "trend_type_ids": [item for item in trend_type_ids if item],
        "source_segment_ids": [item for item in source_segment_ids if item],
        "high": float(high),
        "low": float(low),
        "segment_high": float(high),
        "segment_low": float(low),
        "start_close": _safe_float(
            first.get("start_close"),
            default=_safe_float((prev_platform or {}).get("end_close"), default=high),
        ),
        "end_close": _safe_float(
            last.get("end_close"),
            default=_safe_float((next_platform or {}).get("start_close"), default=low),
        ),
        "connector_role": connector_role,
        "rule_tier": "daily_macro_bridge",
        "reason": "平台之间的连接细节压缩为一条连接线",
    }


def _build_price_platform_sequence(raw_segments, *, level):
    macro_segments = []
    macro_platforms = []
    current_platform = None
    pending_connectors = []
    leading_connectors = []
    connector_count = 0

    def append_connector(connectors, role, prev_platform=None, next_platform=None):
        nonlocal connector_count
        if not connectors and not (prev_platform and next_platform):
            return
        connector_count += 1
        connector = _collapse_connector_segments(
            connectors,
            level=level,
            sequence_id=connector_count,
            connector_role=role,
            prev_platform=prev_platform,
            next_platform=next_platform,
        )
        if connector is not None:
            macro_segments.append(connector)

    def flush_current_platform():
        if current_platform is None:
            return
        macro_segments.append(current_platform)
        macro_platforms.append(current_platform.copy())

    for segment in raw_segments:
        if segment.get("segment_type") == "connector":
            if current_platform is None:
                leading_connectors.append(segment)
            else:
                pending_connectors.append(segment)
            continue
        if segment.get("segment_type") != "zhongshu":
            continue
        platform = _copy_segment_with_macro_aliases(segment)
        if current_platform is None:
            append_connector(leading_connectors, "leading", next_platform=platform)
            leading_connectors = []
            current_platform = platform
            continue
        if _core_ranges_overlap(current_platform, platform):
            current_platform = _merge_macro_platform_pair_with_connectors(
                current_platform,
                platform,
                pending_connectors,
                level=level,
                sequence_id=len(macro_platforms) + 1,
            )
            pending_connectors = []
            continue
        flush_current_platform()
        append_connector(pending_connectors, "between", prev_platform=current_platform, next_platform=platform)
        pending_connectors = []
        current_platform = platform

    if current_platform is None:
        return [], []
    flush_current_platform()
    append_connector(pending_connectors, "trailing", prev_platform=current_platform)
    return macro_segments, macro_platforms


def _coerce_ordered_date_items(ordered_dates):
    items = []
    for item in ordered_dates or []:
        if isinstance(item, Mapping):
            date = normalize_kline_date_str(item.get("date"))
            row = dict(item)
        else:
            date = normalize_kline_date_str(item)
            row = {"date": date}
        if date:
            row["date"] = date
            items.append(row)
    return items


def _first_complete_departure_index(reference_platform, candidate_platform, date_items, index_by_date):
    bounds = _date_index_bounds(candidate_platform, index_by_date)
    if bounds is None:
        return None
    reference_high = _segment_price_high(reference_platform)
    reference_low = _segment_price_low(reference_platform)
    for idx in range(bounds[0], bounds[1] + 1):
        row = date_items[idx]
        high = _strict_float(row.get("high"))
        low = _strict_float(row.get("low"))
        if high is None or low is None:
            continue
        if low > reference_high:
            return idx, "up"
        if high < reference_low:
            return idx, "down"
    return None


def _merge_platforms_by_envelope_departure(platforms, ordered_dates, *, level):
    date_items = _coerce_ordered_date_items(ordered_dates)
    if not platforms or not date_items:
        return platforms
    if any(_strict_float(item.get("high")) is None or _strict_float(item.get("low")) is None for item in date_items):
        return platforms
    index_by_date = {item["date"]: idx for idx, item in enumerate(date_items)}
    current = dict(platforms[0])
    merged_platforms = []
    merge_count = 0

    for platform in platforms[1:]:
        candidate = dict(platform)
        departure = _first_complete_departure_index(current, candidate, date_items, index_by_date)
        if departure is None:
            if _has_large_center_migration(current, candidate):
                merged_platforms.append(current)
                current = candidate
                continue
            merge_count += 1
            current = _merge_envelope_platform_pair(current, candidate, level=level, sequence_id=merge_count)
            continue

        departure_idx, direction = departure
        current_bounds = _date_index_bounds(current, index_by_date)
        candidate_bounds = _date_index_bounds(candidate, index_by_date)
        if (
            direction == "down"
            and current_bounds is not None
            and candidate_bounds is not None
            and candidate_bounds[0] < departure_idx <= candidate_bounds[1]
        ):
            extended_current = _apply_date_span(current, current_bounds[0], departure_idx - 1, date_items)
            if extended_current is not None:
                current = extended_current
            adjusted_candidate = _apply_date_span(candidate, departure_idx, candidate_bounds[1], date_items)
            if adjusted_candidate is not None:
                candidate = adjusted_candidate

        merged_platforms.append(current)
        current = candidate

    merged_platforms.append(current)
    return merged_platforms


def _date_index_bounds(segment, index_by_date):
    start_idx = index_by_date.get(normalize_kline_date_str(segment.get("start_date")))
    end_idx = index_by_date.get(normalize_kline_date_str(segment.get("end_date")))
    if start_idx is None or end_idx is None:
        return None
    return (min(start_idx, end_idx), max(start_idx, end_idx))


def _apply_date_span(segment, start_idx, end_idx, date_items):
    if start_idx < 0 or end_idx >= len(date_items) or end_idx < start_idx:
        return None
    copied = dict(segment)
    copied["start_date"] = date_items[start_idx]["date"]
    copied["end_date"] = date_items[end_idx]["date"]
    copied["start_time"] = copied.get("start_time", copied["start_date"])
    copied["end_time"] = copied.get("end_time", copied["end_date"])
    copied["kline_count"] = int(end_idx - start_idx + 1)
    rows = date_items[start_idx : end_idx + 1]
    highs = [_strict_float(row.get("high")) for row in rows]
    lows = [_strict_float(row.get("low")) for row in rows]
    highs = [value for value in highs if value is not None]
    lows = [value for value in lows if value is not None]
    if highs and lows:
        high = float(max(highs))
        low = float(min(lows))
        copied["high"] = high
        copied["low"] = low
        copied["segment_high"] = high
        copied["segment_low"] = low
        if copied.get("segment_type") == "zhongshu":
            copied["visual_high"] = high
            copied["visual_low"] = low
    start_close = _strict_float(date_items[start_idx].get("close"))
    end_close = _strict_float(date_items[end_idx].get("close"))
    if start_close is not None:
        copied["start_close"] = float(start_close)
    if end_close is not None:
        copied["end_close"] = float(end_close)
    return copied


def _build_partition_connector(
    start_idx,
    end_idx,
    date_items,
    *,
    level,
    sequence_id,
    prev_platform=None,
    next_platform=None,
    connector_role="between",
):
    left = prev_platform or next_platform or {}
    right = next_platform or prev_platform or {}
    template = {
        "segment_type": "connector",
        "structure_kind": "connecting_line",
        "connector_id": f"{level}_macro_connector_{sequence_id}",
        "level": level,
        "trend_type_count": 0,
        "trend_type_ids": [],
        "connector_role": connector_role,
        "rule_tier": "daily_macro_bridge",
        "reason": "平台之间的连接段；按交易日唯一归属切分",
        "start_close": _safe_float(left.get("end_close"), default=_segment_price_high(left)),
        "end_close": _safe_float(right.get("start_close"), default=_segment_price_low(right)),
    }
    connector = _apply_date_span(template, start_idx, end_idx, date_items)
    if connector is None:
        return None
    high = _segment_price_high(connector)
    low = _segment_price_low(connector)
    connector["segment_high"] = high
    connector["segment_low"] = low
    connector["high"] = high
    connector["low"] = low
    return connector


def _partition_macro_sequence_by_dates(platforms, ordered_dates, *, level):
    date_items = _coerce_ordered_date_items(ordered_dates)
    if not platforms or not date_items:
        return None
    index_by_date = {item["date"]: idx for idx, item in enumerate(date_items)}
    indexed = []
    for platform in platforms:
        bounds = _date_index_bounds(platform, index_by_date)
        if bounds is None:
            return None
        indexed.append({"segment": dict(platform), "start_idx": bounds[0], "end_idx": bounds[1]})

    connectors = {}
    for idx in range(len(indexed) - 1):
        left = indexed[idx]
        right = indexed[idx + 1]
        left_end = left["end_idx"]
        right_start = right["start_idx"]
        if right_start <= left_end:
            connector_start = right_start
            connector_end = left_end
            left["end_idx"] = min(left["end_idx"], connector_start - 1)
            right["start_idx"] = max(right["start_idx"], connector_end + 1)
        elif right_start == left_end + 1:
            connectors[idx] = None
            continue
        else:
            connector_start = left_end + 1
            connector_end = right_start - 1
        if connector_start <= connector_end and 0 <= connector_start < len(date_items) and connector_end < len(date_items):
            connectors[idx] = (connector_start, connector_end)

    macro_segments = []
    macro_platforms = []
    connector_count = 0
    if indexed[0]["start_idx"] > 0:
        connector_count += 1
        leading = _build_partition_connector(
            0,
            indexed[0]["start_idx"] - 1,
            date_items,
            level=level,
            sequence_id=connector_count,
            next_platform=indexed[0]["segment"],
            connector_role="leading",
        )
        if leading is not None:
            macro_segments.append(leading)
    for idx, item in enumerate(indexed):
        platform = _apply_date_span(item["segment"], item["start_idx"], item["end_idx"], date_items)
        if platform is not None:
            macro_segments.append(platform)
            macro_platforms.append(platform.copy())
        if idx in connectors and idx + 1 < len(indexed):
            connector_count += 1
            connector_bounds = connectors[idx]
            if connector_bounds is None:
                connector = _build_macro_connector(
                    platform,
                    indexed[idx + 1]["segment"],
                    level=level,
                    sequence_id=connector_count,
                )
            else:
                connector = _build_partition_connector(
                    connector_bounds[0],
                    connector_bounds[1],
                    date_items,
                    level=level,
                    sequence_id=connector_count,
                    prev_platform=item["segment"],
                    next_platform=indexed[idx + 1]["segment"],
                    connector_role="between",
                )
            if connector is not None:
                macro_segments.append(connector)
    if indexed[-1]["end_idx"] < len(date_items) - 1:
        connector_count += 1
        trailing = _build_partition_connector(
            indexed[-1]["end_idx"] + 1,
            len(date_items) - 1,
            date_items,
            level=level,
            sequence_id=connector_count,
            prev_platform=indexed[-1]["segment"],
            connector_role="trailing",
        )
        if trailing is not None:
            macro_segments.append(trailing)

    return macro_segments, macro_platforms


def _partition_macro_sequence_by_dates_with_confirmed_minimum(platforms, ordered_dates, *, level):
    active_platforms = [dict(platform) for platform in platforms or []]
    if not active_platforms:
        return None
    for _attempt in range(len(active_platforms) + 1):
        partitioned = _partition_macro_sequence_by_dates(active_platforms, ordered_dates, level=level)
        if partitioned is None:
            return None
        macro_segments, macro_platforms = partitioned
        kept_platforms = [
            platform
            for platform in macro_platforms
            if _safe_int(platform.get("kline_count"), default=0) >= MIN_CONFIRMED_PLATFORM_KLINES
        ]
        if len(kept_platforms) == len(macro_platforms):
            return macro_segments, macro_platforms
        if not kept_platforms:
            return [], []
        if len(kept_platforms) == len(active_platforms):
            return macro_segments, macro_platforms
        active_platforms = kept_platforms
    return _partition_macro_sequence_by_dates(active_platforms, ordered_dates, level=level)


def _build_macro_connector(prev_platform, next_platform, *, level, sequence_id):
    start_close = _safe_float(prev_platform.get("end_close"), default=_segment_price_high(prev_platform))
    end_close = _safe_float(next_platform.get("start_close"), default=_segment_price_low(next_platform))
    high = max(start_close, end_close)
    low = min(start_close, end_close)
    start_date = prev_platform.get("end_date")
    next_start_date = next_platform.get("start_date")
    start_dt = parse_kline_date(start_date)
    next_start_dt = parse_kline_date(next_start_date)
    end_date = next_start_date
    if start_dt is not None and next_start_dt is not None and next_start_dt < start_dt:
        end_date = start_date
    end_time = (
        next_platform.get("start_time", end_date)
        if end_date == next_start_date
        else prev_platform.get("end_time", end_date)
    )
    return {
        "segment_type": "connector",
        "structure_kind": "connecting_line",
        "connector_id": f"{level}_macro_connector_{sequence_id}",
        "level": level,
        "start_date": start_date,
        "end_date": end_date,
        "start_time": prev_platform.get("end_time", prev_platform.get("end_date")),
        "end_time": end_time,
        "kline_count": 1,
        "trend_type_count": 1,
        "trend_type_ids": [],
        "high": float(high),
        "low": float(low),
        "segment_high": float(high),
        "segment_low": float(low),
        "start_close": float(start_close),
        "end_close": float(end_close),
        "connector_role": "between",
        "rule_tier": "daily_macro_bridge",
        "reason": "宏观平台之间保留一条桥接连接线，避免平台直接贴平台",
    }


def aggregate_daily_macro_platforms(
    structure_segments,
    *,
    level="daily",
    target_min_klines=20,
    target_max_klines=25,
    soft_min_klines=15,
    ordered_dates=None,
):
    del target_min_klines, target_max_klines, soft_min_klines
    raw_segments = [
        _copy_segment_with_macro_aliases(segment)
        for segment in _coerce_structure_sequence(structure_segments)
        if isinstance(segment, Mapping)
    ]
    if not raw_segments:
        return [], []

    macro_segments, macro_platforms = _build_price_platform_sequence(raw_segments, level=level)
    if ordered_dates:
        initial_partition = _partition_macro_sequence_by_dates_with_confirmed_minimum(
            macro_platforms,
            ordered_dates,
            level=level,
        )
        if initial_partition is not None:
            _initial_segments, macro_platforms = initial_partition
        macro_platforms = _merge_platforms_by_envelope_departure(macro_platforms, ordered_dates, level=level)
    partitioned = _partition_macro_sequence_by_dates_with_confirmed_minimum(
        macro_platforms,
        ordered_dates,
        level=level,
    )
    if partitioned is not None:
        return partitioned

    return macro_segments, [platform.copy() for platform in macro_platforms]


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
        "visual_high": float(platform.get("visual_high", platform.get("high", platform.get("zg", 0.0)))),
        "visual_low": float(platform.get("visual_low", platform.get("low", platform.get("zd", 0.0)))),
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
    raw_structure_segments, raw_platforms = build_platform_sequence_from_trend_types(trend_types, level="daily")
    structure_segments, platforms = aggregate_daily_macro_platforms(
        raw_structure_segments,
        level="daily",
        ordered_dates=base.to_dict("records"),
    )
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
        "raw_daily_structure_segments": raw_structure_segments,
        "raw_daily_structure_candidates": [_candidate_from_platform(item) for item in raw_platforms],
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
