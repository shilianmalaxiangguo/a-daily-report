from __future__ import annotations

import datetime
import json
import os
import re
import traceback

from market_data.daily_price_runtime import fetch_daily_price_bars
from market_data.kline_dates import (
    normalize_kline_date_str,
    parse_kline_date,
    short_kline_date,
)

__all__ = [
    "analyze_market_zhongshu",
    "build_structure_segment",
    "build_zhongshu_ascii_diagram",
    "build_zhongshu_structure",
    "split_zhongshu_history_and_today",
]


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


def build_structure_segment(hist_df, start_idx, end_idx, segment_type, zg=None, zd=None, reason=""):
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
    return segment


def build_zhongshu_structure(hist_df, min_zhongshu_klines=5, min_overlap_bars=3):
    """沿用连续重叠分段识别中枢，并保留全部非中枢K线为连接段。"""
    del min_overlap_bars
    if hist_df is None or len(hist_df) == 0:
        return [], []

    total = len(hist_df)
    structure_segments = []
    zhongshu_list = []
    run_start = 0
    run_high = float(hist_df.iloc[0]["high"])
    run_low = float(hist_df.iloc[0]["low"])

    for idx in range(1, total):
        prev_row = hist_df.iloc[idx - 1]
        row = hist_df.iloc[idx]
        overlap_high = min(float(prev_row["high"]), float(row["high"]))
        overlap_low = max(float(prev_row["low"]), float(row["low"]))

        if overlap_high > overlap_low:
            run_high = max(run_high, float(row["high"]))
            run_low = min(run_low, float(row["low"]))
            continue

        run_end = idx - 1
        segment_type = "zhongshu" if (run_end - run_start + 1) >= min_zhongshu_klines else "connector"
        segment_reason = (
            "连续重叠区间达到确认长度，识别为中枢"
            if segment_type == "zhongshu"
            else "连续重叠长度不足确认中枢，保留为连接段"
        )
        segment = build_structure_segment(
            hist_df,
            run_start,
            run_end,
            segment_type,
            zg=run_high if segment_type == "zhongshu" else None,
            zd=run_low if segment_type == "zhongshu" else None,
            reason=segment_reason,
        )
        structure_segments.append(segment)
        if segment_type == "zhongshu":
            zhongshu_list.append(segment.copy())

        run_start = idx
        run_high = float(row["high"])
        run_low = float(row["low"])

    run_end = total - 1
    segment_type = "zhongshu" if (run_end - run_start + 1) >= min_zhongshu_klines else "connector"
    segment_reason = (
        "连续重叠区间达到确认长度，识别为中枢"
        if segment_type == "zhongshu"
        else "历史尾部尚未达到确认中枢长度，作为连接段保留"
    )
    segment = build_structure_segment(
        hist_df,
        run_start,
        run_end,
        segment_type,
        zg=run_high if segment_type == "zhongshu" else None,
        zd=run_low if segment_type == "zhongshu" else None,
        reason=segment_reason,
    )
    structure_segments.append(segment)
    if segment_type == "zhongshu":
        zhongshu_list.append(segment.copy())

    for idx, segment in enumerate(structure_segments):
        if segment["segment_type"] != "connector":
            continue
        has_prev_zhongshu = any(s["segment_type"] == "zhongshu" for s in structure_segments[:idx])
        has_next_zhongshu = any(s["segment_type"] == "zhongshu" for s in structure_segments[idx + 1 :])
        if has_prev_zhongshu and has_next_zhongshu:
            segment["connector_role"] = "between"
        elif has_prev_zhongshu:
            segment["connector_role"] = "trailing"
        else:
            segment["connector_role"] = "leading"

    return structure_segments, zhongshu_list


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
        labeled_rows.append(
            "          最新确认结构中枢: "
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


def _load_iwencai_index_dataframe(recent_days, urlopen_fn=None):
    import pandas as pd
    import urllib.request

    api_key = os.environ.get("IWENCAI_API_KEY", "")
    urlopen_fn = urlopen_fn or urllib.request.urlopen
    url = "https://openapi.iwencai.com/v1/query2data"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "query": f"上证指数近{recent_days}天K线数据，包括日期、开盘价、最高价、最低价、收盘价、成交量",
        "page": "1",
        "limit": str(recent_days),
        "is_cache": "1",
        "expand_index": "true",
    }

    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    response = urlopen_fn(request, timeout=30)
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
    min_zhongshu_klines=5,
    target_date=None,
    *,
    fetch_dataframe=None,
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
            print_fn(f"[大盘结构] 尝试使用同花顺问财API获取{index_code}指数数据...")
            df = None
            data_source = "unknown"
            try:
                df, data_source = _load_iwencai_index_dataframe(recent_days, urlopen_fn=urlopen_fn)
            except Exception as error:
                print_fn(f"[大盘结构] 同花顺问财API获取失败: {error}，切换到BaoStock备用...")
                df, data_source = _load_baostock_index_dataframe(index_code, recent_days, bs_module=bs_module)

        if df is None or len(df) == 0:
            return {"success": False, "error": "所有数据源均无法获取指数数据"}

        for price_col in ["open", "high", "low", "close", "volume", "amount"]:
            if price_col in df.columns:
                df[price_col] = pd.to_numeric(df[price_col], errors="coerce")
        df = df.dropna(subset=["high", "low", "close"])

        recent_df, hist_df, today_df = split_zhongshu_history_and_today(
            df,
            recent_days=recent_days,
            target_date=target_date,
        )
        del recent_df

        structure_segments, zhongshu_list = build_zhongshu_structure(
            hist_df,
            min_zhongshu_klines=min_zhongshu_klines,
            min_overlap_bars=3,
        )

        today_price = float(today_df["close"])
        today_date = today_df["date"]
        current = zhongshu_list[-1] if zhongshu_list else None
        latest_structure_segment = structure_segments[-1] if structure_segments else None

        signal = {}
        if current:
            zg = current["zg"]
            zd = current["zd"]
            dist_to_zg = (today_price - zg) / zg
            dist_to_zd = (today_price - zd) / zd

            signal["zg"] = zg
            signal["zd"] = zd
            signal["dist_to_zg"] = dist_to_zg
            signal["dist_to_zd"] = dist_to_zd
            signal["today_price"] = today_price
            signal["today_date"] = today_date

            if dist_to_zg > 0:
                signal["comparison_result"] = "突破"
                signal["comparison_state"] = "breakout"
                signal["status"] = "✅ 突破中枢"
                signal["signal_type"] = "大盘突破"
                signal["position_level"] = "三档进攻档（50%）"
                signal["action"] = "积极做多"
            elif dist_to_zd < 0:
                signal["comparison_result"] = "下跌"
                signal["comparison_state"] = "down"
                signal["status"] = "⚠️ 跌破中枢"
                signal["signal_type"] = "跌破支撑"
                signal["position_level"] = "一档空仓档（0%）"
                signal["action"] = "清仓观望"
                signal["fell_into_next_zone"] = False
                if len(zhongshu_list) >= 2:
                    for prev_zs in reversed(zhongshu_list[:-1]):
                        if prev_zs["zd"] <= today_price <= prev_zs["zg"]:
                            signal["status"] = "🚨 跌破并落入下中枢区间"
                            signal["signal_type"] = "暴跌至下一中枢"
                            signal["action"] = "严禁抄底，等待企稳"
                            signal["fell_into_next_zone"] = True
                            break
            else:
                signal["comparison_result"] = "震荡"
                signal["comparison_state"] = "range"
                signal["status"] = "➖ 中枢内震荡"
                signal["signal_type"] = "按个股信号操作"
                signal["position_level"] = "二档防守档（30%）"
                signal["action"] = "精选个股"

        print_fn(f"[大盘结构] 数据源: {data_source}，识别到{len(zhongshu_list)}个结构中枢，当前价格{today_price:.2f}")
        return {
            "zhongshu_list": zhongshu_list,
            "current_zhongshu": current,
            "structure_segments": structure_segments,
            "latest_structure_segment": latest_structure_segment,
            "today_price": today_price,
            "today_date": today_date,
            "signal": signal,
            "success": True,
            "data_source": data_source,
        }
    except Exception as error:
        print_fn(f"大盘结构分析失败: {error}")
        traceback.print_exc()
        return {"success": False, "error": str(error)}
