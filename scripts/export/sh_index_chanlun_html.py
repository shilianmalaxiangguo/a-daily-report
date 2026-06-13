from __future__ import annotations

import datetime as dt
import json
import math
from html import escape
from pathlib import Path
from string import Template
from typing import Any, Callable

from export.zhongshu_visual_snapshot import normalize_visual_payload, run_analysis
from daily_report_render import ReportCriticalDataMissingError

DEFAULT_INDEX_CODE = "sh000001"
INDEX_NAME_BY_CODE = {
    "sh000001": "上证指数",
    "sz399001": "深证成指",
    "sz399006": "创业板指",
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _template_path() -> Path:
    return Path(__file__).resolve().parents[1] / "templates" / "sh_index_chanlun_report.html"


def _echarts_source_path() -> Path:
    return _repo_root() / ".generated" / "vendor" / "echarts" / "echarts.min.js"


def _echarts_loader_html() -> str:
    source_path = _echarts_source_path()
    if source_path.exists():
        source = source_path.read_text(encoding="utf-8").replace("</script", "<\\/script")
        return f"<script>\n{source}\n</script>"
    return '<script src="https://cdn.jsdelivr.net/npm/echarts@5.6.0/dist/echarts.min.js"></script>'


def _html(value: Any) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _first_text(record: dict[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return str(value)
    return default


def _number_text(value: Any) -> str:
    if value in (None, ""):
        return "-"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{number:.2f}"


def _number_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _date_span(record: dict[str, Any]) -> str:
    start = _first_text(record, "start_date", "startDate", "start_time", "startTime", default="-")
    end = _first_text(record, "end_date", "endDate", "end_time", "endTime", default="-")
    return start if start == end else f"{start} ~ {end}"


def _segment_type_label(value: Any) -> str:
    text = str(value or "")
    if text == "zhongshu":
        return "日线平台"
    if text == "candidate_platform":
        return "候选平台"
    if text == "connector":
        return "连接段"
    return text or "-"


def _segment_role_label(value: Any) -> str:
    text = str(value or "")
    labels = {
        "leading": "前置",
        "between": "平台之间",
        "trailing": "尾部",
        "departure": "离开",
    }
    return labels.get(text, text or "-")


def _status_label(value: Any) -> str:
    text = str(value or "")
    labels = {
        "confirmed": "已确认",
        "forming": "形成中",
        "success": "可用",
        "missing": "缺失",
        "degraded": "需核对",
        "not_requested": "未请求",
        "range": "结构区间内",
        "inside": "结构区间内",
        "breakout": "向上离开",
        "down": "向下离开",
        "tail_platform_candidate": "尾部候选平台",
    }
    return labels.get(text, text or "-")


def _core_range_text(zd: float | None, zg: float | None) -> str:
    if zd is None or zg is None:
        return "-"
    return f"ZD {_number_text(zd)} ~ ZG {_number_text(zg)}"


def _core_position_text(price: float | None, zd: float | None, zg: float | None) -> str:
    if price is None or zd is None or zg is None:
        return "-"
    if price < zd:
        distance = price - zd
        percent = distance / zd * 100 if zd else 0
        return f"低于ZD（{distance:.2f} / {percent:.2f}%）"
    if price > zg:
        distance = price - zg
        percent = distance / zg * 100 if zg else 0
        return f"高于ZG（+{distance:.2f} / +{percent:.2f}%）"
    return "ZD~ZG内"


def _table(headers: list[str], rows: list[list[Any]]) -> str:
    header_html = "".join(f"<th>{_html(header)}</th>" for header in headers)
    body_rows = []
    for row in rows:
        cells = "".join(f"<td>{_html(cell)}</td>" for cell in row)
        body_rows.append(f"<tr>{cells}</tr>")
    body_html = "\n".join(body_rows) if body_rows else f"<tr><td colspan=\"{len(headers)}\">暂无数据</td></tr>"
    return f"<table border=\"1\" cellpadding=\"4\" cellspacing=\"0\">\n<thead><tr>{header_html}</tr></thead>\n<tbody>\n{body_html}\n</tbody>\n</table>"


def _summary_rows(payload: dict[str, Any]) -> list[list[Any]]:
    market = payload.get("market_zhongshu") or {}
    signal = market.get("signal") or {}
    windows = payload.get("calculation_windows") or {}
    policy = payload.get("strict_chanlun_policy") or {}
    index_code = payload.get("index_code") or DEFAULT_INDEX_CODE
    current = market.get("current_zhongshu") or {}
    latest = market.get("latest_structure_segment") or {}
    today_price = _number_or_none(market.get("today_price"))
    current_zg = _number_or_none(current.get("zg"))
    current_zd = _number_or_none(current.get("zd"))
    return [
        ["日期", payload.get("date", "")],
        ["指数", f"{INDEX_NAME_BY_CODE.get(index_code, index_code)}（{index_code}）"],
        ["最新K线日期", market.get("today_date", payload.get("date", ""))],
        ["今日收盘", _number_text(market.get("today_price"))],
        ["日线数据源", market.get("data_source", "-")],
        ["结构结论", _first_text(signal, "status", default="-")],
        ["信号类型", _first_text(signal, "signal_type", "signalType", default="-")],
        ["包络位置", _status_label(_first_text(signal, "comparison_state", "comparisonState", default="-"))],
        ["中枢核心", _core_range_text(current_zd, current_zg)],
        ["相对核心", _core_position_text(today_price, current_zd, current_zg)],
        ["当前结构", _date_span(current) if current else "-"],
        ["最新分段", f"{_segment_type_label(latest.get('segment_type') or latest.get('segmentType'))} {_date_span(latest)}" if latest else "-"],
        ["基础K线数", windows.get("structural_base_daily_bars", "-")],
        ["展示K线数", windows.get("display_row_count", "-")],
        ["下级别结构证据", _status_label(policy.get("minute_confirmation", "-"))],
        ["数据状态", _status_label(payload.get("source_status", "-"))],
    ]


def _segment_row(segment: dict[str, Any]) -> list[Any]:
    segment_type = segment.get("segment_type") or segment.get("segmentType")
    high = segment.get("segment_high", segment.get("segmentHigh", segment.get("high")))
    low = segment.get("segment_low", segment.get("segmentLow", segment.get("low")))
    return [
        _segment_type_label(segment_type),
        _segment_role_label(segment.get("connector_role") or segment.get("connectorRole")),
        _date_span(segment),
        segment.get("kline_count", segment.get("klineCount", "-")),
        _number_text(segment.get("zg")),
        _number_text(segment.get("zd")),
        _number_text(high),
        _number_text(low),
        _status_label(_first_text(segment, "confirmation_status", "confirmationStatus", "candidate_status", "candidateStatus", default="-")),
        _status_label(_first_text(segment, "departure_status", "departureStatus", default="-")),
        _first_text(segment, "reason", default="-"),
    ]


def _segments_table(market: dict[str, Any]) -> str:
    segments = market.get("structure_segments") or market.get("zhongshu_list") or []
    rows = [_segment_row(segment) for segment in segments if isinstance(segment, dict)]
    return _table(
        ["类型", "角色", "时间", "K线数", "ZG", "ZD", "高点", "低点", "确认", "离开", "依据"],
        rows,
    )


def _current_table(market: dict[str, Any]) -> str:
    current = market.get("current_zhongshu") or {}
    latest = market.get("latest_structure_segment") or {}
    rows = []
    if isinstance(current, dict) and current:
        rows.append(["当前平台", *_segment_row(current)])
    if isinstance(latest, dict) and latest:
        rows.append(["最新分段", *_segment_row(latest)])
    return _table(
        ["项目", "类型", "角色", "时间", "K线数", "ZG", "ZD", "高点", "低点", "确认", "离开", "依据"],
        rows,
    )


def _kline_table(payload: dict[str, Any]) -> str:
    index_code = payload.get("index_code") or DEFAULT_INDEX_CODE
    rows = ((payload.get("index_klines") or {}).get(index_code) or [])[-80:]
    table_rows = [
        [
            row.get("date", ""),
            _number_text(row.get("open")),
            _number_text(row.get("high")),
            _number_text(row.get("low")),
            _number_text(row.get("close")),
            _number_text(row.get("volume")),
            _number_text(row.get("amount")),
        ]
        for row in rows
        if isinstance(row, dict)
    ]
    return _table(["日期", "开盘", "最高", "最低", "收盘", "成交量", "成交额"], table_rows)


def _index_kline_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    index_code = payload.get("index_code") or DEFAULT_INDEX_CODE
    rows = ((payload.get("index_klines") or {}).get(index_code) or [])
    return [row for row in rows if isinstance(row, dict)]


def _row_bounds(rows: list[dict[str, Any]], start_date: str, end_date: str) -> tuple[float | None, float | None]:
    highs = []
    lows = []
    for row in rows:
        row_date = str(row.get("date") or "")
        if not row_date or row_date < start_date or row_date > end_date:
            continue
        high = _number_or_none(row.get("high"))
        low = _number_or_none(row.get("low"))
        if high is not None:
            highs.append(high)
        if low is not None:
            lows.append(low)
    return (max(highs) if highs else None, min(lows) if lows else None)


def _row_close(rows: list[dict[str, Any]], target_date: str) -> float | None:
    for row in rows:
        if str(row.get("date") or "") == target_date:
            return _number_or_none(row.get("close"))
    return None


def _chart_segment(
    segment: dict[str, Any],
    index: int,
    *,
    rows: list[dict[str, Any]],
    current: dict[str, Any],
    latest: dict[str, Any],
) -> dict[str, Any] | None:
    start_date = _first_text(segment, "start_date", "startDate", "start_time", "startTime")
    end_date = _first_text(segment, "end_date", "endDate", "end_time", "endTime")
    if not start_date or not end_date:
        return None

    segment_type = segment.get("segment_type") or segment.get("segmentType")
    row_high, row_low = _row_bounds(rows, start_date, end_date)
    zg = _number_or_none(segment.get("zg"))
    zd = _number_or_none(segment.get("zd"))
    high = (
        _number_or_none(segment.get("segment_high"))
        or _number_or_none(segment.get("segmentHigh"))
        or _number_or_none(segment.get("high"))
        or row_high
        or zg
    )
    low = (
        _number_or_none(segment.get("segment_low"))
        or _number_or_none(segment.get("segmentLow"))
        or _number_or_none(segment.get("low"))
        or row_low
        or zd
    )
    current_start = _first_text(current, "start_date", "startDate", "start_time", "startTime")
    current_end = _first_text(current, "end_date", "endDate", "end_time", "endTime")
    latest_start = _first_text(latest, "start_date", "startDate", "start_time", "startTime")
    latest_end = _first_text(latest, "end_date", "endDate", "end_time", "endTime")

    return {
        "id": f"segment-{index + 1}",
        "kind": str(segment_type or ""),
        "label": _segment_type_label(segment_type),
        "role": _segment_role_label(segment.get("connector_role") or segment.get("connectorRole")),
        "startDate": start_date,
        "endDate": end_date,
        "startClose": _number_or_none(segment.get("start_close") or segment.get("startClose")) or _row_close(rows, start_date),
        "endClose": _number_or_none(segment.get("end_close") or segment.get("endClose")) or _row_close(rows, end_date),
        "zg": zg,
        "zd": zd,
        "high": high,
        "low": low,
        "klineCount": _number_or_none(segment.get("kline_count") or segment.get("klineCount")),
        "isCurrent": bool(start_date == current_start and end_date == current_end and str(segment_type or "") == "zhongshu"),
        "isLatest": bool(start_date == latest_start and end_date == latest_end),
    }


def _chart_data(payload: dict[str, Any]) -> dict[str, Any]:
    rows = _index_kline_rows(payload)
    dates = []
    candles = []
    volumes = []
    for row in rows:
        date = str(row.get("date") or "")
        open_price = _number_or_none(row.get("open"))
        close = _number_or_none(row.get("close"))
        low = _number_or_none(row.get("low"))
        high = _number_or_none(row.get("high"))
        if not date or open_price is None or close is None or low is None or high is None:
            continue
        dates.append(date)
        candles.append([open_price, close, low, high])
        volumes.append(_number_or_none(row.get("volume")) or 0)

    market = payload.get("market_zhongshu") or {}
    current = market.get("current_zhongshu") or {}
    latest = market.get("latest_structure_segment") or {}
    source_segments = market.get("structure_segments") or market.get("zhongshu_list") or []
    segments = [
        chart_segment
        for index, segment in enumerate(source_segments)
        if isinstance(segment, dict)
        for chart_segment in [_chart_segment(segment, index, rows=rows, current=current, latest=latest)]
        if chart_segment is not None
    ]
    current_segment = next(
        (segment for segment in segments if segment["isCurrent"]),
        next((segment for segment in segments if segment["kind"] == "zhongshu"), None),
    )
    latest_price = _number_or_none(market.get("today_price"))
    if latest_price is None and candles:
        latest_price = candles[-1][1]

    return {
        "dates": dates,
        "candles": candles,
        "volumes": volumes,
        "segments": segments,
        "currentSegment": current_segment,
        "latestDate": market.get("today_date") or payload.get("date") or (dates[-1] if dates else ""),
        "latestPrice": latest_price,
    }


def _json_for_html_script(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return (
        text.replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def render_sh_index_chanlun_html(payload: dict[str, Any], *, generated_at: str | None = None) -> str:
    index_code = payload.get("index_code") or DEFAULT_INDEX_CODE
    index_name = INDEX_NAME_BY_CODE.get(index_code, index_code)
    report_date = str(payload.get("date") or "")
    title = f"{report_date} {index_name}缠论拆解".strip()
    template = Template(_template_path().read_text(encoding="utf-8"))
    market = payload.get("market_zhongshu") or {}
    substitutions = {
        "title": _html(title),
        "heading": _html(title),
        "echarts_loader": _echarts_loader_html(),
        "generated_at": _html(generated_at or dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        "summary_table": _summary_rows_table(payload),
        "tomorrow_decision_section": _tomorrow_decision_section(payload),
        "chart_data": _json_for_html_script(_chart_data(payload)),
        "current_table": _current_table(market),
        "segments_table": _segments_table(market),
        "kline_table": _kline_table(payload),
    }
    return template.safe_substitute(substitutions)


def _summary_rows_table(payload: dict[str, Any]) -> str:
    return _table(["项目", "值"], _summary_rows(payload))


def _tomorrow_position_text(decision: dict[str, Any]) -> str:
    for key in ("max_position_pct", "target_position_pct", "position_pct"):
        value = _number_or_none(decision.get(key))
        if value is not None:
            return f"{value:.0f}%"
    if decision.get("can_new_entry") is False:
        return "0%"
    return "-"


def _tomorrow_participation_text(decision: dict[str, Any]) -> str:
    if decision.get("can_new_entry") is False:
        return "不参与"
    if decision.get("can_new_entry") is True:
        return "只按日报条件参与"
    return "-"


def _tomorrow_final_action_text(decision: dict[str, Any]) -> str:
    text = _first_text(decision, "final_action", "action", "summary", default="-")
    if decision.get("can_new_entry") is False and text not in ("", "-"):
        return text.replace("禁止新增", "不新增参与")
    return text


def _tomorrow_structure_text(payload: dict[str, Any]) -> str:
    signal = ((payload.get("market_zhongshu") or {}).get("signal") or {})
    parts = [
        _first_text(signal, "status", default=""),
        _first_text(signal, "signal_type", "signalType", default=""),
    ]
    return "；".join(part for part in parts if part) or "-"


def _tomorrow_decision_section(payload: dict[str, Any]) -> str:
    decision = payload.get("tomorrow_decision")
    if not isinstance(decision, dict) or not decision:
        return ""
    rows = [
        ["最终执行条件", _tomorrow_final_action_text(decision)],
        ["操作状态", _first_text(decision, "operation_state", "state", default="-")],
        ["明日最大仓位", _tomorrow_position_text(decision)],
        ["新增参与", _tomorrow_participation_text(decision)],
        ["指数结构含义", _tomorrow_structure_text(payload)],
    ]
    return "\n  <h2>明日抉择</h2>\n  " + _table(["项目", "值"], rows)


def build_sh_index_chanlun_html_path(target_date: str, *, root: str | Path | None = None) -> Path:
    base_root = Path(root) if root is not None else _repo_root()
    return base_root / "reports" / "chanlun-html" / f"{target_date}_上证指数缠论.html"


def save_sh_index_chanlun_html_report(
    target_date: str,
    *,
    root: str | Path | None = None,
    index_code: str = DEFAULT_INDEX_CODE,
    runner: Callable[[str, str], tuple[dict[str, Any], list[dict[str, Any]]]] = run_analysis,
    tomorrow_decision: dict[str, Any] | None = None,
    fetch_minute_bars: Callable[..., dict[str, Any]] | None = None,
    sse_loader: Callable[..., Any] | None = None,
    allow_live_fallback: bool = True,
) -> Path:
    runner_kwargs = {}
    if fetch_minute_bars is not None:
        runner_kwargs["fetch_minute_bars"] = fetch_minute_bars
    if sse_loader is not None:
        runner_kwargs["sse_loader"] = sse_loader
    if not allow_live_fallback:
        runner_kwargs["allow_live_fallback"] = False
    if runner_kwargs:
        market_zhongshu, rows = runner(target_date, index_code, **runner_kwargs)
    else:
        market_zhongshu, rows = runner(target_date, index_code)
    if not allow_live_fallback and not (market_zhongshu or {}).get("success"):
        raise ReportCriticalDataMissingError(
            (market_zhongshu or {}).get("error") or f"{target_date} PostgreSQL指数结构缺失，停止生成缠论HTML"
        )
    payload = normalize_visual_payload(market_zhongshu, rows, date=target_date, index_code=index_code)
    if tomorrow_decision:
        payload["tomorrow_decision"] = dict(tomorrow_decision)
    output_path = build_sh_index_chanlun_html_path(target_date, root=root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_sh_index_chanlun_html(payload), encoding="utf-8")
    return output_path


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="生成上证指数缠论拆解 HTML")
    parser.add_argument("date")
    parser.add_argument("--index-code", default=DEFAULT_INDEX_CODE)
    parser.add_argument("--root", default=str(_repo_root()))
    args = parser.parse_args(argv)
    path = save_sh_index_chanlun_html_report(args.date, root=args.root, index_code=args.index_code)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
