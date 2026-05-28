from __future__ import annotations

import datetime
import json
import os
import re
import secrets
import traceback

from decision.chanlun_zhongshu_runtime import (
    aggregate_daily_macro_platforms,
    analyze_chanlun_zhongshu,
    build_platform_sequence_from_trend_types,
    build_trend_types_from_bars,
    detect_effective_departure_from_envelope,
)
from market_data.daily_price_runtime import fetch_daily_price_bars
from market_data.kline_dates import (
    normalize_kline_date_str,
    parse_kline_date,
    short_kline_date,
)
from market_data.minute_price_runtime import fetch_index_minute_bars
from market_data.tushare_service import fetch_daily_price_bars as fetch_tushare_daily_price_bars


class IwencaiSkillVersionError(RuntimeError):
    """Raised when OpenAPI rejects the locally installed SkillHub/skill version."""


__all__ = [
    "analyze_market_zhongshu",
    "build_structure_segment",
    "build_zhongshu_ascii_diagram",
    "build_zhongshu_structure",
    "split_zhongshu_history_and_today",
]

CONFIRMED_ZHONGSHU_MIN_KLINES = 20
FORMING_ZHONGSHU_MIN_KLINES = 5
TAIL_CANDIDATE_MIN_KLINES = 4
TAIL_CANDIDATE_MIN_RETRACE_RATIO = 0.15


def _is_forming_zhongshu_segment(segment):
    segment = segment or {}
    if segment.get("structure_kind") == "platform" or segment.get("candidate_status") == "confirmed_platform":
        return False
    if "required_kline_count" not in segment and segment.get("confirmation_status") == "confirmed":
        return False
    if segment.get("confirmation_status") == "forming" or bool(segment.get("is_current_forming")):
        return True
    kline_count = segment.get("kline_count")
    required_count = segment.get("required_kline_count") or CONFIRMED_ZHONGSHU_MIN_KLINES
    try:
        return int(kline_count) < int(required_count)
    except (TypeError, ValueError):
        return False


def _daily_candidate_from_forming_zhongshu(segment, required_kline_count):
    del segment, required_kline_count
    return None


def split_zhongshu_history_and_today(df, recent_days=120, target_date=None):
    """将K线数据拆分为历史中枢窗口和比较日。"""
    if df is None or len(df) == 0:
        raise ValueError("K线数据为空")
    if "date" not in df.columns:
        raise ValueError("K线数据缺少date列")

    prepared_df = df.copy()
    prepared_df["date"] = prepared_df["date"].map(normalize_kline_date_str)
    prepared_df["_date_obj"] = prepared_df["date"].map(parse_kline_date)
    prepared_df = prepared_df.dropna(subset=["_date_obj"]).sort_values("_date_obj").reset_index(drop=True)

    if target_date:
        target_dt = parse_kline_date(target_date)
        if target_dt is None:
            raise ValueError(f"无法解析target_date: {target_date}")
        prepared_df = prepared_df[prepared_df["_date_obj"] <= target_dt].reset_index(drop=True)

    if len(prepared_df) < 2:
        raise ValueError("可用K线不足，无法拆分历史中枢和比较日")

    recent_df = prepared_df.tail(recent_days + 1).reset_index(drop=True)
    hist_df = recent_df.iloc[:-1].copy()
    today_df = recent_df.iloc[-1].copy()
    return recent_df, hist_df, today_df


def build_structure_segment(
    hist_df,
    start_idx,
    end_idx,
    segment_type,
    zg=None,
    zd=None,
    reason="",
    confirmation_status=None,
    required_kline_count=None,
):
    """构建结构分段，确保每根K线都能归属到中枢或连接段。"""
    start_row = hist_df.iloc[start_idx]
    end_row = hist_df.iloc[end_idx]
    segment_slice = hist_df.iloc[start_idx : end_idx + 1]
    segment_high = float(segment_slice["high"].max())
    segment_low = float(segment_slice["low"].min())
    start_close = float(start_row["close"])
    end_close = float(end_row["close"])
    segment = {
        "segment_type": segment_type,
        "start_idx": int(start_idx),
        "end_idx": int(end_idx),
        "start_date": start_row["date"],
        "end_date": end_row["date"],
        "kline_count": int(end_idx - start_idx + 1),
        "segment_high": segment_high,
        "segment_low": segment_low,
        "start_close": start_close,
        "end_close": end_close,
        "reason": reason,
    }
    if segment_type == "zhongshu":
        segment["zg"] = float(zg)
        segment["zd"] = float(zd)
        segment["confirmation_status"] = confirmation_status or "confirmed"
        if required_kline_count is not None:
            segment["required_kline_count"] = int(required_kline_count)
        if segment["confirmation_status"] == "forming":
            segment["is_current_forming"] = True
    return segment


def build_zhongshu_structure(
    hist_df,
    min_zhongshu_klines=CONFIRMED_ZHONGSHU_MIN_KLINES,
    min_overlap_bars=3,
    min_current_zhongshu_klines=FORMING_ZHONGSHU_MIN_KLINES,
):
    """按平台/连接线分解结构，不再用日K连续重叠或20根长度确认中枢。"""
    del min_zhongshu_klines, min_overlap_bars, min_current_zhongshu_klines
    if hist_df is None or len(hist_df) == 0:
        return [], []
    trend_types = build_trend_types_from_bars(hist_df, level="daily")
    raw_segments, _raw_platforms = build_platform_sequence_from_trend_types(trend_types, level="daily")
    return aggregate_daily_macro_platforms(raw_segments, level="daily", ordered_dates=hist_df.to_dict("records"))


def append_today_trailing_connector(structure_segments, today_row):
    if not structure_segments or today_row is None:
        return structure_segments
    today_date = normalize_kline_date_str(today_row.get("date") if hasattr(today_row, "get") else None)
    if not today_date:
        return structure_segments
    last = structure_segments[-1]
    last_end = normalize_kline_date_str(last.get("end_date"))
    if last_end and today_date <= last_end:
        return structure_segments
    high = float(today_row.get("high"))
    low = float(today_row.get("low"))
    close = float(today_row.get("close"))
    if last.get("segment_type") == "connector" and last.get("connector_role") == "trailing":
        merged = dict(last)
        merged["end_date"] = today_date
        merged["end_time"] = today_date
        merged["kline_count"] = int(merged.get("kline_count") or 0) + 1
        merged["high"] = max(float(merged.get("high", high)), high)
        merged["low"] = min(float(merged.get("low", low)), low)
        merged["segment_high"] = max(float(merged.get("segment_high", high)), high)
        merged["segment_low"] = min(float(merged.get("segment_low", low)), low)
        merged["end_close"] = close
        merged["rule_tier"] = merged.get("rule_tier") or "daily_today_bridge"
        merged["reason"] = "最新比较日并入尾部连接段，避免连续尾部折线"
        return [*structure_segments[:-1], merged]

    prev_close = float(last.get("end_close", close))
    connector = {
        "segment_type": "connector",
        "structure_kind": "connecting_line",
        "connector_id": "daily_today_trailing_connector",
        "level": "daily",
        "start_date": today_date,
        "end_date": today_date,
        "start_time": today_date,
        "end_time": today_date,
        "kline_count": 1,
        "trend_type_count": 0,
        "trend_type_ids": [],
        "high": high,
        "low": low,
        "segment_high": high,
        "segment_low": low,
        "start_close": prev_close,
        "end_close": close,
        "connector_role": "trailing",
        "rule_tier": "daily_today_bridge",
        "reason": "最新比较日尚未并入平台，作为尾部连接段归属，避免K线三不管",
    }
    return [*structure_segments, connector]


def _record_value(record, key, default=None):
    if hasattr(record, "get"):
        return record.get(key, default)
    try:
        return record[key]
    except Exception:
        return default


def _safe_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


def _segment_number(segment, *keys):
    for key in keys:
        value = _safe_number(segment.get(key))
        if value is not None:
            return value
    return None


def _ordered_row_records(ordered_rows):
    if ordered_rows is None:
        return []
    if hasattr(ordered_rows, "to_dict"):
        try:
            rows = ordered_rows.to_dict("records")
        except TypeError:
            rows = list(ordered_rows)
    else:
        rows = list(ordered_rows or [])
    prepared = []
    for row in rows:
        date = normalize_kline_date_str(_record_value(row, "date"))
        if not date:
            continue
        high = _safe_number(_record_value(row, "high"))
        low = _safe_number(_record_value(row, "low"))
        close = _safe_number(_record_value(row, "close"))
        if high is None or low is None or close is None:
            continue
        prepared.append({"date": date, "high": high, "low": low, "close": close})
    return prepared


def _rows_for_segment(ordered_rows, segment):
    start_date = normalize_kline_date_str(segment.get("start_date"))
    end_date = normalize_kline_date_str(segment.get("end_date"))
    if not start_date or not end_date:
        return []
    left, right = (start_date, end_date) if start_date <= end_date else (end_date, start_date)
    return [row for row in _ordered_row_records(ordered_rows) if left <= row["date"] <= right]


def _latest_two_row_overlap(rows):
    if len(rows) < 2:
        return None
    prev_row, latest_row = rows[-2], rows[-1]
    zg = min(prev_row["high"], latest_row["high"])
    zd = max(prev_row["low"], latest_row["low"])
    if zg <= zd:
        return None
    return {"zg": float(zg), "zd": float(zd)}


def _tail_retrace_direction(rows, candidate_high, candidate_low, previous_platform):
    prev_high = _segment_number(previous_platform, "high", "segment_high", "zg")
    prev_low = _segment_number(previous_platform, "low", "segment_low", "zd")
    if prev_high is None or prev_low is None or candidate_high <= candidate_low or len(rows) < 2:
        return None
    latest_close = rows[-1]["close"]
    previous_close = rows[-2]["close"]
    tail_span = max(candidate_high - candidate_low, 0.01)
    if candidate_high > prev_high and latest_close < previous_close:
        retrace_ratio = (candidate_high - latest_close) / tail_span
        if retrace_ratio >= TAIL_CANDIDATE_MIN_RETRACE_RATIO:
            return "up_then_retrace"
    if candidate_low < prev_low and latest_close > previous_close:
        retrace_ratio = (latest_close - candidate_low) / tail_span
        if retrace_ratio >= TAIL_CANDIDATE_MIN_RETRACE_RATIO:
            return "down_then_retrace"
    return None


def append_tail_candidate_platform(structure_segments, ordered_rows):
    """把右侧尾部连接段升级为“候选平台”，但不写入确认中枢列表。"""
    if not structure_segments or len(structure_segments) < 2:
        return structure_segments
    last = structure_segments[-1]
    if last.get("segment_type") != "connector" or last.get("connector_role") != "trailing":
        return structure_segments
    previous_platform = None
    for segment in reversed(structure_segments[:-1]):
        if segment.get("segment_type") == "zhongshu" and segment.get("confirmation_status", "confirmed") == "confirmed":
            previous_platform = segment
            break
    if previous_platform is None:
        return structure_segments
    try:
        kline_count = int(last.get("kline_count") or 0)
    except (TypeError, ValueError):
        kline_count = 0
    if kline_count < TAIL_CANDIDATE_MIN_KLINES:
        return structure_segments

    rows = _rows_for_segment(ordered_rows, last)
    if len(rows) < TAIL_CANDIDATE_MIN_KLINES:
        return structure_segments
    candidate_high = max(row["high"] for row in rows)
    candidate_low = min(row["low"] for row in rows)
    overlap = _latest_two_row_overlap(rows)
    if overlap is None:
        return structure_segments
    retrace_direction = _tail_retrace_direction(rows, candidate_high, candidate_low, previous_platform)
    if retrace_direction is None:
        return structure_segments

    first = rows[0]
    latest = rows[-1]
    candidate = {
        **last,
        "segment_type": "candidate_platform",
        "structure_kind": "platform_candidate",
        "candidate_id": f"{last.get('connector_id') or 'tail_connector'}_candidate",
        "candidate_source_connector_id": last.get("connector_id"),
        "connector_role": "",
        "zg": float(overlap["zg"]),
        "zd": float(overlap["zd"]),
        "zg_candidate": float(overlap["zg"]),
        "zd_candidate": float(overlap["zd"]),
        "high": float(candidate_high),
        "low": float(candidate_low),
        "segment_high": float(candidate_high),
        "segment_low": float(candidate_low),
        "visual_high": float(candidate_high),
        "visual_low": float(candidate_low),
        "start_close": float(first["close"]),
        "end_close": float(latest["close"]),
        "kline_count": int(len(rows)),
        "trend_type_count": max(int(last.get("trend_type_count") or 0), 2),
        "confirmation_status": "forming",
        "candidate_status": "tail_platform_candidate",
        "is_current_forming": True,
        "is_tail_candidate": True,
        "rule_tier": "tail_candidate_platform",
        "tail_candidate_direction": retrace_direction,
        "reason": "尾部连接段脱离前平台后出现回撤与近两日重叠，标记为右侧候选平台；不进入确认中枢列表",
    }
    departure_metadata = detect_effective_departure_from_envelope(previous_platform, rows)
    if departure_metadata and departure_metadata.get("departure_status") == "confirmed":
        candidate.update(
            {
                "departure_status": departure_metadata.get("departure_status"),
                "departure_direction": departure_metadata.get("departure_direction"),
                "departure_warning_date": departure_metadata.get("departure_warning_date"),
                "departure_confirmed_date": departure_metadata.get("departure_confirmed_date"),
                "departure_envelope_high": departure_metadata.get("departure_envelope_high"),
                "departure_envelope_low": departure_metadata.get("departure_envelope_low"),
                "departure_source_platform_start_date": previous_platform.get("start_date"),
                "departure_source_platform_end_date": previous_platform.get("end_date"),
            }
        )
    return [*structure_segments[:-1], candidate]


def build_zhongshu_ascii_diagram(structure_segments, today_date, today_price, signal, max_segments=5):
    """构建极简箱体ASCII图。"""
    if not structure_segments:
        return ""

    recent_segments = structure_segments[-max_segments:]
    latest_zhongshu_pos = None
    latest_zhongshu_segment = None
    for idx, seg in enumerate(recent_segments):
        if seg.get("segment_type") == "zhongshu":
            latest_zhongshu_pos = idx
            latest_zhongshu_segment = seg

    chart_rows = 9
    plot_width_target = 56
    gap_between_segments = 2
    gap_before_today = 4

    price_points = [today_price]
    for seg in recent_segments:
        price_points.extend(
            [
                float(seg.get("segment_high", 0.0)),
                float(seg.get("segment_low", 0.0)),
                float(seg.get("start_close", 0.0)),
                float(seg.get("end_close", 0.0)),
            ]
        )
        if seg.get("segment_type") == "zhongshu":
            price_points.extend([float(seg.get("zg", 0.0)), float(seg.get("zd", 0.0))])

    min_price = min(price_points)
    max_price = max(price_points)
    if max_price <= min_price:
        max_price = min_price + 1.0
    padding = (max_price - min_price) * 0.08
    max_price += padding
    min_price -= padding

    def _price_to_row(value):
        ratio = (max_price - float(value)) / (max_price - min_price)
        row = int(round(ratio * (chart_rows - 1)))
        return max(0, min(chart_rows - 1, row))

    def _put(grid, row, col, ch):
        if 0 <= row < chart_rows and 0 <= col < chart_width:
            grid[row][col] = ch

    def _draw_line(grid, col1, row1, col2, row2):
        if col1 == col2:
            _put(grid, row1, col1, "|")
            return

        step_count = max(abs(col2 - col1), abs(row2 - row1))
        if step_count == 0:
            _put(grid, row1, col1, ".")
            return

        for step in range(step_count + 1):
            t = step / step_count
            col = int(round(col1 + (col2 - col1) * t))
            row = int(round(row1 + (row2 - row1) * t))
            if row2 < row1:
                ch = "/"
            elif row2 > row1:
                ch = "\\"
            else:
                ch = "-"
            _put(grid, row, col, ch)

    weights = [max(1, int(seg.get("kline_count", 1))) for seg in recent_segments]
    min_widths = [10 if seg.get("segment_type") == "zhongshu" else 4 for seg in recent_segments]
    base_width = sum(min_widths) + gap_between_segments * max(0, len(recent_segments) - 1)
    extra = max(0, plot_width_target - base_width)
    total_weight = max(1, sum(weights))
    segment_widths = []
    for base, weight in zip(min_widths, weights):
        segment_widths.append(base + int(round(extra * weight / total_weight)))

    cursor = 0
    seg_layouts = []
    for seg, width in zip(recent_segments, segment_widths):
        start_col = cursor
        end_col = start_col + width - 1
        mid_col = (start_col + end_col) // 2
        seg_layouts.append(
            {
                "segment": seg,
                "start_col": start_col,
                "end_col": end_col,
                "mid_col": mid_col,
            }
        )
        cursor = end_col + 1 + gap_between_segments

    today_col = cursor + gap_before_today
    chart_width = today_col + 1

    grid = [[" " for _ in range(chart_width)] for _ in range(chart_rows)]
    axis_row = ["-" for _ in range(chart_width)]
    tag_row = [" " for _ in range(chart_width)]
    date_row = [" " for _ in range(chart_width)]
    legend_parts = []

    segment_points = []
    zhongshu_idx = 0
    connector_idx = 0

    for idx, layout in enumerate(seg_layouts):
        seg = layout["segment"]
        start_col = layout["start_col"]
        end_col = layout["end_col"]
        mid_col = layout["mid_col"]
        axis_row[start_col] = "|"
        axis_row[end_col] = "|"

        start_row = _price_to_row(float(seg.get("start_close", today_price)))
        end_row = _price_to_row(float(seg.get("end_close", today_price)))

        if seg.get("segment_type") == "zhongshu":
            zhongshu_idx += 1
            top_row = _price_to_row(float(seg.get("zg", seg.get("segment_high", 0.0))))
            bottom_row = _price_to_row(float(seg.get("zd", seg.get("segment_low", 0.0))))
            if top_row > bottom_row:
                top_row, bottom_row = bottom_row, top_row

            is_latest_confirmed = idx == latest_zhongshu_pos
            horizontal = "=" if is_latest_confirmed else "-"
            vertical = "!" if is_latest_confirmed else "|"

            for col in range(start_col, end_col + 1):
                _put(grid, top_row, col, horizontal)
                _put(grid, bottom_row, col, horizontal)
            for row in range(top_row + 1, bottom_row):
                _put(grid, row, start_col, vertical)
                _put(grid, row, end_col, vertical)

            _draw_line(grid, start_col, start_row, end_col, end_row)
            center_row = (top_row + bottom_row) // 2
            label = f"ZS{zhongshu_idx}" + ("*" if is_latest_confirmed else "")
            label_start = max(start_col + 1, mid_col - len(label) // 2)
            for offset, ch in enumerate(label):
                col = label_start + offset
                if col < end_col:
                    _put(grid, center_row, col, ch)
            tag = label
            legend_parts.append(
                f"{tag}={short_kline_date(seg['start_date'])}->{short_kline_date(seg['end_date'])} "
                f"[{seg.get('zd', 0):.2f},{seg.get('zg', 0):.2f}]"
            )
        else:
            connector_idx += 1
            _draw_line(grid, start_col, start_row, end_col, end_row)
            tag = f"TR{connector_idx}"
            delta = float(seg.get("end_close", 0.0)) - float(seg.get("start_close", 0.0))
            direction = "up" if delta > 0 else "down" if delta < 0 else "flat"
            legend_parts.append(
                f"{tag}={short_kline_date(seg['start_date'])}->{short_kline_date(seg['end_date'])} transition-{direction}"
            )

        tag_start = max(0, mid_col - len(tag) // 2)
        for offset, ch in enumerate(tag):
            if tag_start + offset < chart_width:
                tag_row[tag_start + offset] = ch

        date_label = short_kline_date(seg["start_date"])
        date_start = max(0, mid_col - len(date_label) // 2)
        for offset, ch in enumerate(date_label):
            if date_start + offset < chart_width:
                date_row[date_start + offset] = ch

        segment_points.append(
            {
                "start_col": start_col,
                "start_row": start_row,
                "end_col": end_col,
                "end_row": end_row,
            }
        )

    for idx in range(len(segment_points) - 1):
        left = segment_points[idx]
        right = segment_points[idx + 1]
        _draw_line(grid, left["end_col"] + 1, left["end_row"], right["start_col"] - 1, right["start_row"])

    axis_row[today_col] = "|"
    today_row = _price_to_row(today_price)
    if segment_points:
        last = segment_points[-1]
        _draw_line(grid, last["end_col"] + 1, last["end_row"], today_col - 1, today_row)

    _put(grid, today_row, today_col, "T")
    comparison_state = signal.get("comparison_state", "") if signal else ""
    if comparison_state == "breakout":
        _put(grid, max(today_row - 1, 0), today_col, "^")
    elif comparison_state == "down":
        _put(grid, min(today_row + 1, chart_rows - 1), today_col, "v")

    today_tag = "TODAY"
    today_tag_start = max(0, today_col - len(today_tag) // 2)
    for offset, ch in enumerate(today_tag):
        if today_tag_start + offset < chart_width:
            tag_row[today_tag_start + offset] = ch

    today_date_label = short_kline_date(today_date)
    today_date_start = max(0, today_col - len(today_date_label) // 2)
    for offset, ch in enumerate(today_date_label):
        if today_date_start + offset < chart_width:
            date_row[today_date_start + offset] = ch

    latest_zg = float(latest_zhongshu_segment.get("zg", 0.0)) if latest_zhongshu_segment else None
    latest_zd = float(latest_zhongshu_segment.get("zd", 0.0)) if latest_zhongshu_segment else None
    latest_zg_row = _price_to_row(latest_zg) if latest_zg is not None else None
    latest_zd_row = _price_to_row(latest_zd) if latest_zd is not None else None

    labeled_rows = []
    for row_idx, line in enumerate(grid):
        if latest_zg_row is not None and row_idx == latest_zg_row:
            label = f"ZG {latest_zg:7.0f} | "
        elif latest_zd_row is not None and row_idx == latest_zd_row:
            label = f"ZD {latest_zd:7.0f} | "
        elif row_idx == 0:
            label = f"MAX{max_price:7.0f} | "
        elif row_idx == chart_rows - 1:
            label = f"MIN{min_price:7.0f} | "
        else:
            label = "           | "
        labeled_rows.append(label + "".join(line).rstrip())

    labeled_rows.append("        +-" + "".join(axis_row))
    labeled_rows.append("          " + "".join(tag_row).rstrip())
    labeled_rows.append("          " + "".join(date_row).rstrip())
    if latest_zhongshu_segment:
        latest_is_forming = _is_forming_zhongshu_segment(latest_zhongshu_segment)
        latest_label = "当前形成中结构" if latest_is_forming else "最新确认结构中枢"
        labeled_rows.append(
            f"          {latest_label}: "
            f"{short_kline_date(latest_zhongshu_segment['start_date'])}->{short_kline_date(latest_zhongshu_segment['end_date'])} "
            f"ZG={latest_zg:.2f} / ZD={latest_zd:.2f}"
        )
    comparison = signal.get("comparison_result", "unknown") if signal else "unknown"
    labeled_rows.append(f"          TODAY={short_kline_date(today_date)} {today_price:.2f} => {comparison}")
    labeled_rows.append("          " + " | ".join(legend_parts))
    return "\n".join(labeled_rows)


def _normalize_baostock_index_code(index_code):
    if index_code.startswith(("sh.", "sz.")):
        return index_code
    if index_code.startswith("sh"):
        return f"sh.{index_code[2:]}"
    if index_code.startswith("sz"):
        return f"sz.{index_code[2:]}"
    return index_code


def _build_iwencai_headers(api_key, *, call_type="normal"):
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-Claw-Call-Type": call_type,
        "X-Claw-Skill-Id": "hithink-market-query",
        "X-Claw-Skill-Version": "1.0.0",
        "X-Claw-Plugin-Id": "none",
        "X-Claw-Plugin-Version": "none",
        "X-Claw-Trace-Id": secrets.token_hex(32),
    }


def _load_iwencai_index_dataframe(recent_days, urlopen_fn=None):
    import pandas as pd
    import urllib.error
    import urllib.request

    api_key = os.environ.get("IWENCAI_API_KEY", "")
    urlopen_fn = urlopen_fn or urllib.request.urlopen
    base_url = (os.environ.get("IWENCAI_BASE_URL") or "https://openapi.iwencai.com").rstrip("/")
    url = f"{base_url}/v1/query2data"
    headers = _build_iwencai_headers(api_key)
    payload = {
        "query": f"上证指数近{recent_days}天K线数据，包括日期、开盘价、最高价、最低价、收盘价、成交量",
        "page": "1",
        "limit": str(recent_days),
        "is_cache": "1",
        "expand_index": "true",
    }

    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        response = urlopen_fn(request, timeout=30)
    except urllib.error.HTTPError as error:
        body = ""
        try:
            body = error.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        if error.code == 401 and "Skill 版本过低" in body:
            raise IwencaiSkillVersionError(body or "问财 SkillHub 本地技能版本过低") from error
        raise
    result = json.loads(response.read().decode("utf-8"))
    if result.get("status_code", 0) != 0:
        raise RuntimeError(f"API错误: {result.get('status_msg', 'unknown error')}")

    raw_data = (result.get("datas") or [{}])[0]
    dates = set()
    for key in raw_data.keys():
        match = re.search(r"\[(\d{8})\]", key)
        if match:
            dates.add(match.group(1))

    klines = []
    for date in sorted(dates):
        kline = {
            "date": date,
            "open": raw_data.get(f"开盘价[{date}]"),
            "high": raw_data.get(f"最高价[{date}]"),
            "low": raw_data.get(f"最低价[{date}]"),
            "close": raw_data.get(f"收盘价[{date}]"),
            "volume": raw_data.get(f"成交量[{date}]"),
            "amount": raw_data.get(f"成交额[{date}]"),
        }
        if kline["high"] and kline["low"] and kline["close"]:
            klines.append(kline)

    return pd.DataFrame(klines), "同花顺问财API"


def _normalize_akshare_index_symbol(index_code):
    code = str(index_code or "").lower().replace(".", "")
    if code.startswith(("sh", "sz")):
        return code
    if code.startswith(("000", "880", "899")):
        return f"sh{code}"
    if code.startswith(("399", "159")):
        return f"sz{code}"
    return code


def _load_akshare_index_dataframe(index_code, recent_days, target_date=None):
    import pandas as pd

    try:
        import akshare as ak
    except Exception:
        return None, "akshare.stock_zh_index_daily_em"

    symbol = _normalize_akshare_index_symbol(index_code)
    try:
        df = ak.stock_zh_index_daily_em(symbol=symbol)
    except Exception:
        return None, "akshare.stock_zh_index_daily_em"

    if df is None or getattr(df, "empty", False):
        return None, "akshare.stock_zh_index_daily_em"

    df = df.copy()
    if "date" not in df.columns:
        return None, "akshare.stock_zh_index_daily_em"

    df["date"] = df["date"].map(normalize_kline_date_str)
    if target_date:
        end_date = normalize_kline_date_str(target_date)
        df = df[df["date"] <= end_date]

    for column in ("open", "high", "low", "close", "volume", "amount"):
        if column not in df.columns:
            df[column] = 0.0
    df = df[["date", "open", "high", "low", "close", "volume", "amount"]]
    df = df.sort_values("date").tail(int(recent_days or 120) + 1).reset_index(drop=True)
    if len(df) < 2:
        return None, "akshare.stock_zh_index_daily_em"
    return df, "akshare.stock_zh_index_daily_em"


def _load_tushare_index_dataframe(index_code, recent_days, target_date=None):
    import pandas as pd

    end_dt = parse_kline_date(target_date) if target_date else datetime.datetime.now().date()
    if end_dt is None:
        end_dt = datetime.datetime.now().date()
    start_dt = end_dt - datetime.timedelta(days=int(recent_days or 120) + 45)
    try:
        bars = fetch_tushare_daily_price_bars(
            index_code,
            start_dt.strftime("%Y-%m-%d"),
            end_dt.strftime("%Y-%m-%d"),
            is_index=True,
        )
    except Exception:
        return None, "tushare.index_daily"
    if not bars:
        return None, "tushare.index_daily"

    df = pd.DataFrame(bars)
    if len(df) == 0 or "date" not in df.columns:
        return None, "tushare.index_daily"
    df = df.copy()
    df["date"] = df["date"].map(normalize_kline_date_str)
    end_date = normalize_kline_date_str(target_date) if target_date else ""
    if end_date:
        df = df[df["date"] <= end_date]
    for column in ("open", "high", "low", "close", "volume", "amount"):
        if column not in df.columns:
            df[column] = 0.0
    df = df[["date", "open", "high", "low", "close", "volume", "amount"]]
    df = df.sort_values("date").tail(int(recent_days or 120) + 1).reset_index(drop=True)
    if len(df) < 2:
        return None, "tushare.index_daily"
    return df, "tushare.index_daily"


def _load_baostock_index_dataframe(index_code, recent_days, bs_module=None):
    import pandas as pd
    bs_code = _normalize_baostock_index_code(index_code)
    end_date = datetime.datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.datetime.now() - datetime.timedelta(days=recent_days + 30)).strftime("%Y-%m-%d")
    bars = fetch_daily_price_bars(
        bs_code,
        start_date,
        end_date,
        is_index=True,
        prefer_fast=True,
        allow_baostock_fallback=False,
    )
    if not bars:
        return None, "fast_index_runtime"

    df = pd.DataFrame(bars)
    if len(df) == 0:
        return None, "fast_index_runtime"
    if "amount" not in df.columns:
        df["amount"] = 0.0
    return df[["date", "open", "high", "low", "close", "volume", "amount"]], "fast_index_runtime"


def analyze_market_zhongshu(
    index_code="sh000001",
    recent_days=120,
    min_zhongshu_klines=CONFIRMED_ZHONGSHU_MIN_KLINES,
    target_date=None,
    *,
    fetch_dataframe=None,
    fetch_minute_bars=None,
    use_chanlun_confirmation=True,
    use_hybrid_confirmation=False,
    urlopen_fn=None,
    bs_module=None,
    print_fn=print,
):
    """
    分析大盘中枢结构（双中枢识别），支持注入DataFrame供测试/运行时复用。
    """
    try:
        import pandas as pd

        if fetch_dataframe is not None:
            fetched = fetch_dataframe(
                index_code=index_code,
                recent_days=recent_days,
                min_zhongshu_klines=min_zhongshu_klines,
                target_date=target_date,
            )
            if isinstance(fetched, tuple):
                df, data_source = fetched
            else:
                df, data_source = fetched, "injected_dataframe"
        else:
            print_fn(f"[大盘结构] 尝试使用 Tushare index_daily 获取{index_code}近{recent_days}日指数K线...")
            df, data_source = _load_tushare_index_dataframe(index_code, recent_days, target_date=target_date)
            if df is None or len(df) == 0:
                print_fn(f"[大盘结构] Tushare index_daily 获取失败，尝试使用 AkShare 兜底...")
                df, data_source = _load_akshare_index_dataframe(index_code, recent_days, target_date=target_date)
            if df is None or len(df) == 0:
                print_fn(f"[大盘结构] AkShare 获取失败，尝试使用 fast_index_runtime 兜底...")
                df, data_source = _load_baostock_index_dataframe(index_code, recent_days, bs_module=bs_module)
            if df is None or len(df) == 0:
                print_fn(f"[大盘结构] fast_index_runtime 获取失败，尝试使用同花顺问财API 兜底...")
                df = None
                data_source = "unknown"
            try:
                if df is None or len(df) == 0:
                    df, data_source = _load_iwencai_index_dataframe(recent_days, urlopen_fn=urlopen_fn)
            except Exception as error:
                print_fn(f"[大盘结构] 同花顺问财API获取失败: {error}，fast_index_runtime 已尝试")

        if df is None or len(df) == 0:
            return {"success": False, "error": "所有数据源均无法获取指数数据"}

        for price_col in ["open", "high", "low", "close", "volume", "amount"]:
            if price_col in df.columns:
                df[price_col] = pd.to_numeric(df[price_col], errors="coerce")
        df = df.dropna(subset=["high", "low", "close"])

        from decision.security_zhongshu_node import analyze_security_zhongshu_from_frame

        result = analyze_security_zhongshu_from_frame(
            df,
            security_code=index_code,
            security_name="上证指数",
            security_type="index",
            recent_days=recent_days,
            min_zhongshu_klines=min_zhongshu_klines,
            target_date=target_date,
            data_source=data_source,
            print_fn=print_fn,
        )
        if not result.get("success"):
            return result
        if not use_chanlun_confirmation:
            result.setdefault("daily_structure_candidates", [])
            result.setdefault("daily_structure_current", None)
            result.setdefault("chanlun_60m_structures", [])
            result.setdefault("chanlun_confirmation", {})
            return result

        _recent_df, hist_df, today_df = split_zhongshu_history_and_today(
            df,
            recent_days=recent_days,
            target_date=target_date,
        )
        del _recent_df
        signal = result.setdefault("signal", {})

        chanlun_result = {}
        if use_chanlun_confirmation:
            daily_rows = hist_df.to_dict("records") + [today_df.to_dict()]
            chanlun_result = analyze_chanlun_zhongshu(
                daily_rows=daily_rows,
                target_date=target_date,
                fetch_minute_bars=fetch_minute_bars or fetch_index_minute_bars,
                index_code=index_code,
                minute_period="60",
                min_daily_klines=min_zhongshu_klines,
                use_hybrid_confirmation=use_hybrid_confirmation,
            )
            confirmation = chanlun_result.get("chanlun_confirmation") or {}
            current_candidate = chanlun_result.get("current_candidate") or {}
            if confirmation.get("confirmation_status") in ("data_insufficient", "insufficient_60m_history", "not_confirmed"):
                confirmation_status = confirmation.get("confirmation_status")
                signal["structure_confirmation"] = confirmation_status
                candidate_label = "平台待确认" if confirmation_status == "not_confirmed" else "平台数据不足"
                signal["status"] = (
                    f"⏳ {candidate_label}（走势类型数：{current_candidate.get('trend_type_count', 0)}，"
                    f"结构确认：{confirmation_status}）"
                )
                signal["signal_type"] = "中枢确认待观察"
                signal["position_level"] = "观察档（不加仓）"
                if confirmation_status in ("data_insufficient", "insufficient_60m_history"):
                    signal["action"] = "只观察，等结构确认补齐"
                elif confirmation_status == "not_confirmed":
                    signal["action"] = "只观察，等结构重新形成平台重叠"

        result.update(
            {
                "signal": signal,
                "daily_structure_candidates": chanlun_result.get("daily_structure_candidates", []),
                "daily_structure_current": chanlun_result.get("current_candidate"),
                "chanlun_60m_structures": chanlun_result.get("chanlun_60m_structures", []),
                "chanlun_confirmation": chanlun_result.get("chanlun_confirmation", {}),
            }
        )
        return result
    except Exception as error:
        print_fn(f"大盘结构分析失败: {error}")
        traceback.print_exc()
        return {"success": False, "error": str(error)}
