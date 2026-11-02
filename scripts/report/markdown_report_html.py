from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass
from datetime import date
from html import escape, unescape
from pathlib import Path
from string import Template
from typing import Iterable, Mapping

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from domains.market_activity.new_high_structure import build_new_high_breadth_thresholds
from market_data.daily_price_runtime import get_limit_up_pct
from report.candidate_decision_evidence import validate_sector_tournament_three_axis
from report.candidate_lifecycle_display import candidate_source_display_label
from report.dual_cluster_projection import build_account_day_order_dual_cluster
from report.surface_wording import sanitize_user_visible_text


_ECHARTS_CDN_URL = "https://cdn.bootcdn.net/ajax/libs/echarts/5.6.0/echarts.min.js"
_MERMAID_CDN_URL = "https://cdn.bootcdn.net/ajax/libs/mermaid/11.12.0/mermaid.min.js"


# Bear/readable HTML renderer: consumes the final Markdown report and preserves
# the reader-facing narrative. Structured fact checks live in html_report_view.py.
@dataclass(frozen=True)
class Heading:
    level: int
    title: str
    anchor: str
    is_detailed_appendix: bool = False


@dataclass(frozen=True)
class LimitPools:
    up: frozenset[str]
    down: frozenset[str]


def _template_path() -> Path:
    return Path(__file__).resolve().parents[1] / "templates" / "daily_report_markdown_reader.html"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _echarts_source_path() -> Path:
    return _repo_root() / ".generated" / "vendor" / "echarts" / "echarts.min.js"


def _async_echarts_loader_html() -> str:
    return (
        '<script data-bear-echarts-loader="bootcdn">'
        "(function(){"
        "if(window.echarts){window.dispatchEvent(new Event('bear:echarts-ready'));return;}"
        "const script=document.createElement('script');"
        f"script.src={json.dumps(_ECHARTS_CDN_URL)};"
        "script.async=true;"
        "script.onload=()=>window.dispatchEvent(new Event('bear:echarts-ready'));"
        "document.head.appendChild(script);"
        "})();"
        "</script>"
    )


def _echarts_loader_html(output_path: str | Path | None = None) -> str:
    source_path = _echarts_source_path()
    if not source_path.is_file():
        return _async_echarts_loader_html()
    source = source_path.read_text(encoding="utf-8").replace("</script", "<\\/script")
    return (
        '<script data-bear-echarts-loader="inline" '
        f'data-source="{_html(_ECHARTS_CDN_URL)}">'
        f"{source}\n"
        "window.dispatchEvent(new Event('bear:echarts-ready'));"
        "</script>"
    )


def _mermaid_loader_html(output_path: str | Path | None = None, *, enabled: bool = False) -> str:
    if not enabled:
        return ""
    return (
        '<script data-bear-mermaid-loader="bootcdn">'
        "(function(){"
        "const renderMermaid=()=>{"
        "if(!window.mermaid){return;}"
        "window.mermaid.initialize({startOnLoad:false,securityLevel:'strict',theme:'base'});"
        "window.mermaid.run({querySelector:'.markdown-body .mermaid'});"
        "};"
        "const scheduleRender=()=>{"
        "if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',renderMermaid,{once:true});}else{renderMermaid();}"
        "};"
        "if(window.mermaid){scheduleRender();return;}"
        "const script=document.createElement('script');"
        f"script.src={json.dumps(_MERMAID_CDN_URL)};"
        "script.async=true;"
        "script.onload=scheduleRender;"
        "document.head.appendChild(script);"
        "})();"
        "</script>"
    )


def _html(value: object) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _tomorrow_action_calendar_pct(value: object) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    if not math.isfinite(number):
        return ""
    if abs(number) < 0.005:
        number = 0.0
    return f"{number:+.2f}%" if number else "0.00%"


def _tomorrow_action_calendar_metric(value: object, status: str) -> tuple[str, str]:
    if status == "future":
        return "待发生", "is-pending"
    if status != "complete":
        return "—", "is-incomplete"
    text = _tomorrow_action_calendar_pct(value)
    if not text:
        return "数值未记录", "is-incomplete"
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0.0
    tone = "is-positive" if number > 0 else "is-negative" if number < 0 else "is-flat"
    return text, tone


def _tomorrow_action_calendar_rows(
    records: list[Mapping[str, object]],
    calendar_notes: Iterable[Mapping[str, object]] = (),
) -> list[list[Mapping[str, object] | None]]:
    rows: list[list[Mapping[str, object] | None]] = []
    row_week_keys: list[tuple[int, int] | None] = []
    week_row_indexes: dict[tuple[int, int], list[int]] = {}
    undated: list[Mapping[str, object]] = []
    dated_records: list[date] = []
    for record in records:
        execution_date = str(record.get("execution_date") or "").strip()[:10]
        try:
            parsed_date = date.fromisoformat(execution_date)
        except ValueError:
            undated.append(record)
            continue
        weekday = parsed_date.weekday()
        if weekday > 4:
            undated.append(record)
            continue
        dated_records.append(parsed_date)
        iso_calendar = parsed_date.isocalendar()
        week_key = (iso_calendar.year, iso_calendar.week)
        target_row = None
        for row_index in reversed(week_row_indexes.get(week_key, [])):
            if rows[row_index][weekday] is None:
                target_row = row_index
                break
        if target_row is None:
            target_row = len(rows)
            rows.append([None] * 5)
            row_week_keys.append(week_key)
            week_row_indexes.setdefault(week_key, []).append(target_row)
        rows[target_row][weekday] = record
    for offset in range(0, len(undated), 5):
        row = list(undated[offset : offset + 5])
        rows.append(row + [None] * (5 - len(row)))
        row_week_keys.append(None)
    if dated_records:
        range_start = min(dated_records)
        range_end = max(dated_records)
        notes_by_date: dict[str, Mapping[str, object]] = {}
        for raw_note in calendar_notes or []:
            if not isinstance(raw_note, Mapping):
                continue
            note_date = str(raw_note.get("date") or "").strip()[:10]
            if note_date:
                notes_by_date[note_date] = raw_note
        for row_index, week_key in enumerate(row_week_keys):
            if week_key is None:
                continue
            for weekday in range(5):
                if rows[row_index][weekday] is not None:
                    continue
                cell_date = date.fromisocalendar(week_key[0], week_key[1], weekday + 1)
                cell_date_text = cell_date.isoformat()
                note = notes_by_date.get(cell_date_text)
                if note is not None:
                    cell_kind = str(note.get("kind") or "holiday").strip()
                    label = str(note.get("label") or "休市").strip()
                elif cell_date < range_start or cell_date > range_end:
                    cell_kind = "sample_outside"
                    label = "样本外"
                else:
                    cell_kind = "missing"
                    label = "记录缺失"
                rows[row_index][weekday] = {
                    "calendar_cell_kind": cell_kind,
                    "execution_date": cell_date_text,
                    "weekday_label": ("周一", "周二", "周三", "周四", "周五")[weekday],
                    "action_label": label,
                }
    return rows


def _render_tomorrow_action_calendar_cell(record: Mapping[str, object] | None) -> str:
    if record is None:
        return '<td class="tomorrow-action-calendar-cell is-blank" aria-label="无明日操作记录"></td>'
    execution_date = str(record.get("execution_date") or "").strip()[:10]
    report_date = str(record.get("report_date") or "").strip()[:10]
    weekday_label = str(record.get("weekday_label") or "星期待确认").strip()
    calendar_cell_kind = str(record.get("calendar_cell_kind") or "").strip()
    action_kind = str(record.get("action_kind") or "incomplete").strip()
    status = str(record.get("performance_status") or "incomplete").strip()
    action_label = str(record.get("action_label") or "").strip()
    if not action_label or action_label == "事实不足":
        action_label = (
            "计划待执行"
            if status == "future"
            else "账户记录未结算"
            if status != "complete"
            else "账户动作未记录"
        )
    if calendar_cell_kind:
        note_detail = {
            "holiday": "非交易日",
            "sample_outside": "样本区间外",
            "missing": "PostgreSQL 记录缺失",
        }.get(calendar_cell_kind, "周历注释")
        return (
            f'<td class="tomorrow-action-calendar-cell is-calendar-note is-{_html(calendar_cell_kind)}" '
            f'aria-label="{_html(execution_date)} {_html(weekday_label)} {_html(action_label)}">'
            '<article class="tomorrow-action-calendar-entry tomorrow-action-calendar-note">'
            '<header class="tomorrow-action-calendar-date">'
            f'<time datetime="{_html(execution_date)}">{_html(execution_date)}</time>'
            f'<span>{_html(weekday_label)}</span></header>'
            f'<strong>{_html(action_label)}</strong><span>{_html(note_detail)}</span>'
            '</article></td>'
        )
    raw_action_items = record.get("action_items")
    action_items = [item for item in raw_action_items or [] if isinstance(item, Mapping)]
    plan_action_kind = str(record.get("plan_action_kind") or "").strip()
    plan_action_label = str(record.get("plan_action_label") or "").strip()
    daily_return, daily_tone = _tomorrow_action_calendar_metric(record.get("daily_return_pct"), status)
    excess_return, excess_tone = _tomorrow_action_calendar_metric(record.get("excess_shanghai_pct"), status)
    date_label = execution_date or "执行日待确认"
    time_html = (
        f'<time datetime="{_html(execution_date)}">{_html(execution_date)}</time>'
        if execution_date
        else '<span class="tomorrow-action-calendar-date-missing">执行日待确认</span>'
    )
    report_date_html = (
        f'<span class="tomorrow-action-calendar-report-date">本格计划日报 {_html(report_date)}</span>'
        if report_date
        else ""
    )
    if action_items:
        action_html = '<div class="tomorrow-action-calendar-actions">' + "".join(
            '<div class="tomorrow-action-calendar-action-item">'
            f'<strong>{_html(item.get("label") or "账户对象未记录")}</strong>'
            f'<span>{_html(item.get("position_label") or "")} · {_html(item.get("holding_label") or "")}'
            + (
                f' · 计划日报 {_html(item.get("plan_date_label"))}'
                if item.get("plan_date_label")
                else ""
            )
            + '</span>'
            '</div>'
            for item in action_items
        ) + '</div>'
    else:
        action_html = f'<strong class="tomorrow-action-calendar-action">{_html(action_label)}</strong>'
    plan_note_html = ""
    if action_items and plan_action_kind in {"no_new_entry", "empty"}:
        plan_note_html = (
            f'<span class="tomorrow-action-calendar-plan-note">本日计划：{_html(plan_action_label)}</span>'
        )
    return (
        f'<td class="tomorrow-action-calendar-cell is-{_html(action_kind)} is-{_html(status)}" '
        f'aria-label="{_html(date_label)} {_html(weekday_label)} {_html(action_label)}">'
        '<article class="tomorrow-action-calendar-entry">'
        '<header class="tomorrow-action-calendar-date">'
        f'{time_html}<span>{_html(weekday_label)}</span>'
        '</header>'
        f'{action_html}{plan_note_html}{report_date_html}'
        '<dl class="tomorrow-action-calendar-metrics">'
        '<div><dt>当日涨幅</dt>'
        f'<dd class="{daily_tone}">{_html(daily_return)}</dd></div>'
        '<div><dt>跑赢上证</dt>'
        f'<dd class="{excess_tone}">{_html(excess_return)}</dd></div>'
        '</dl>'
        '</article></td>'
    )


def _render_tomorrow_action_calendar(payload: Mapping[str, object] | None) -> str:
    if not isinstance(payload, Mapping):
        return ""
    raw_records = payload.get("records")
    records = [record for record in raw_records or [] if isinstance(record, Mapping)]
    raw_calendar_notes = payload.get("calendar_notes")
    calendar_notes = [note for note in raw_calendar_notes or [] if isinstance(note, Mapping)]
    requested_count = max(int(payload.get("requested_count") or 25), 1)
    record_count = int(payload.get("record_count") or len(records))
    start_date = str(payload.get("execution_date_start") or "").strip()
    end_date = str(payload.get("execution_date_end") or "").strip()
    range_text = f" · {start_date} 至 {end_date}" if start_date and end_date else ""
    heading = (
        '<section class="tomorrow-action-calendar" aria-labelledby="tomorrow-action-calendar-title">'
        '<header class="tomorrow-action-calendar-header">'
        '<div><span class="tomorrow-action-calendar-eyebrow">账户日序</span>'
        '<h2 id="tomorrow-action-calendar-title">最近25条明日操作日历</h2></div>'
        f'<p>样本 {record_count}/{requested_count}{_html(range_text)}</p>'
        '</header>'
    )
    if not records:
        return (
            heading
            + '<p class="tomorrow-action-calendar-empty">未读取到近25条明日操作记录</p>'
            + '</section>'
        )
    body_rows = "".join(
        '<tr>' + "".join(_render_tomorrow_action_calendar_cell(record) for record in row) + '</tr>'
        for row in _tomorrow_action_calendar_rows(records, calendar_notes)
    )
    summary = payload.get("summary") if isinstance(payload.get("summary"), Mapping) else {}
    valid_count = int(summary.get("valid_count") or 0)
    outperform_count = int(summary.get("outperform_count") or 0)
    average_daily = _tomorrow_action_calendar_pct(summary.get("average_daily_return_pct")) or "数值未记录"
    average_excess = _tomorrow_action_calendar_pct(summary.get("average_excess_shanghai_pct")) or "数值未记录"
    cumulative_daily = _tomorrow_action_calendar_pct(summary.get("cumulative_daily_return_pct")) or "数值未记录"
    cumulative_returns = (
        payload.get("cumulative_returns")
        if isinstance(payload.get("cumulative_returns"), Mapping)
        else {}
    )
    rolling_scope = (
        cumulative_returns.get("rolling_25")
        if isinstance(cumulative_returns.get("rolling_25"), Mapping)
        else {}
    )
    current_month_scope = (
        cumulative_returns.get("current_month")
        if isinstance(cumulative_returns.get("current_month"), Mapping)
        else {}
    )
    since_start_scope = (
        cumulative_returns.get("since_start")
        if isinstance(cumulative_returns.get("since_start"), Mapping)
        else {}
    )
    rolling_cumulative = "累计值未结算"
    if rolling_scope.get("coverage_status") in (None, "", "complete"):
        rolling_cumulative = (
            _tomorrow_action_calendar_pct(rolling_scope.get("cumulative_daily_return_pct"))
            or cumulative_daily
        )
    current_month_cumulative = "累计值未结算"
    if current_month_scope.get("coverage_status") in (None, "", "complete"):
        current_month_cumulative = (
            _tomorrow_action_calendar_pct(current_month_scope.get("cumulative_daily_return_pct"))
            or "数值未记录"
        )
    since_start_cumulative = "累计值未结算"
    if since_start_scope.get("coverage_status") in (None, "", "complete"):
        since_start_cumulative = (
            _tomorrow_action_calendar_pct(since_start_scope.get("cumulative_daily_return_pct"))
            or "数值未记录"
        )
    summary_items = (
        f'<span>有效 {valid_count} 日</span>'
        f'<span>明日标的计划 {int(summary.get("plan_target_count", summary.get("target_count")) or 0)} 日</span>'
        f'<span>账户持仓 {int(summary.get("holding_count", summary.get("target_count")) or 0)} 日</span>'
        f'<span>空仓 {int(summary.get("empty_count") or 0)} 日</span>'
        f'<span>不新增计划 {int(summary.get("no_new_entry_count") or 0)} 日</span>'
        f'<span>平均当日涨幅 {_html(average_daily)}</span>'
        f'<span>平均跑赢上证 {_html(average_excess)}</span>'
        f'<span>滚动25天累计收益 {_html(rolling_cumulative)}</span>'
        f'<span>当前月累计收益 {_html(current_month_cumulative)}</span>'
        f'<span>2026-06-17起累计收益 {_html(since_start_cumulative)}</span>'
        f'<span>跑赢 {outperform_count}/{valid_count} 日</span>'
        f'<span>未结算 {int(summary.get("incomplete_count") or 0)} 日</span>'
        f'<span>待发生 {int(summary.get("future_count") or 0)} 日</span>'
    )
    return (
        heading
        + '<div class="tomorrow-action-calendar-scroll" role="region" '
        'aria-label="最近25条明日操作周历" tabindex="0">'
        '<table class="tomorrow-action-calendar-table">'
        '<thead><tr>'
        '<th scope="col">周一</th><th scope="col">周二</th><th scope="col">周三</th>'
        '<th scope="col">周四</th><th scope="col">周五</th>'
        '</tr></thead>'
        f'<tbody>{body_rows}</tbody></table></div>'
        f'<footer class="tomorrow-action-calendar-summary" aria-label="明日操作汇总">{summary_items}</footer>'
        '</section>'
    )


def _json_for_html_script(value: object) -> str:
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return (
        text.replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


_CLEAN_STOCK_REF_RE = re.compile(
    r"(^|[\s:：=,，、;；|([{（【《])"
    r"(\*?[A-Za-zＡ-Ｚａ-ｚ\u4e00-\u9fff][A-Za-zＡ-Ｚａ-ｚ0-9\u4e00-\u9fff·]{1,5}\([036]\d{5}\))"
)
_STOCK_NAME_RE = re.compile(r"\*?[A-Za-zＡ-Ｚａ-ｚ\u4e00-\u9fff][A-Za-zＡ-Ｚａ-ｚ0-9\u4e00-\u9fff·]{1,10}")
_CYCLE_SECTOR_SPAN_RE = re.compile(
    r"<span\b"
    r"(?=[^>]*\bclass=(?P<class_quote>[\"'])(?P<class_name>cycle-sector-(?:dot|label))(?P=class_quote))"
    r"(?=[^>]*\bstyle=(?P<style_quote>[\"'])(?P<style>[^\"']*)(?P=style_quote))"
    r"[^>]*>(?P<content>.*?)</span>",
    re.IGNORECASE,
)
_CYCLE_CALENDAR_TOKEN_RE = re.compile(
    r"<span\b"
    r"(?=[^>]*\bclass=[\"']cycle-sector-(?:dot|label)[\"'])"
    r"(?=[^>]*\bstyle=[\"'][^\"']*[\"'])"
    r"[^>]*>.*?</span>|<br\s*/?>",
    re.IGNORECASE,
)
_CYCLE_SECTOR_LEGACY_COLOR_OVERRIDES = {
    "#D84E42": "#DD4C4F",
    "#168C61": "#07A35A",
    "#2E7DD1": "#2F7FB8",
    "#C57917": "#A88400",
    "#9A5FB4": "#A75E9B",
    "#008A8A": "#4F8A87",
}
_CYCLE_SECTOR_COLOR_BY_NAME = {
    "电力": "#DD4C4F",
    "半导体": "#2F7FB8",
    "通信设备": "#DD4C4F",
    "元器件": "#2F7FB8",
    "电气设备": "#B7677A",
    "专用机械": "#4F8A87",
    "电池": "#07A35A",
    "证券": "#A75E9B",
    "国产芯片替代": "#A88400",
    "光通信/CPO": "#4F8A87",
}


def _strip_inline_markdown(text: str) -> str:
    text = re.sub(r"\[([^\]\n]+)\]\(([^)\s]+)\)", r"\1", text)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"__([^_]+)__", r"\1", text)
    return text.strip()


def _sanitize_reader_markdown_text(markdown_text: str) -> str:
    """Normalize legacy replay wording before converting Markdown to reader HTML."""
    return sanitize_user_visible_text(str(markdown_text or ""))


def _cycle_sector_display_color(color: str) -> str:
    normalized = str(color or "").upper()
    return _CYCLE_SECTOR_LEGACY_COLOR_OVERRIDES.get(normalized, normalized)


def _cycle_sector_span_color(style: str) -> str:
    match = re.search(r"(?:^|;)\s*color\s*:\s*(#[0-9A-Fa-f]{6})\s*(?:;|$)", str(style or ""))
    return match.group(1).upper() if match else ""


def _looks_like_stock_name(value: str) -> bool:
    text = _strip_inline_markdown(value)
    if not text or text in {"股票", "标的", "名称", "候选", "对象"}:
        return False
    return bool(_STOCK_NAME_RE.fullmatch(text))


def _table_header_text(value: str) -> str:
    return _strip_inline_markdown(value).replace(" ", "")


def _is_stock_name_header(value: str) -> bool:
    header = _table_header_text(value)
    return header in {"股票", "标的", "候选", "对象", "锚定龙头", "主观察对象", "观察对象", "今日关注标的", "明天观察池"}


def _is_stock_code_header(value: str) -> bool:
    return _table_header_text(value) in {"代码", "股票代码", "证券代码"}


def _stock_code_from_row(headers: list[str], row: list[str]) -> str:
    for index, header in enumerate(headers):
        if not _is_stock_code_header(header) or index >= len(row):
            continue
        code = _strip_inline_markdown(row[index])
        if re.fullmatch(r"[036]\d{5}", code):
            return code
    for cell in row:
        code = _strip_inline_markdown(cell)
        if re.fullmatch(r"[036]\d{5}", code):
            return code
    return ""


def _collect_stock_refs(markdown_text: str) -> tuple[str, ...]:
    refs: set[str] = set()
    for line in markdown_text.splitlines():
        for match in _CLEAN_STOCK_REF_RE.finditer(line):
            refs.add(_strip_inline_markdown(match.group(2)))
        if "|" not in line or _is_table_separator(line):
            continue
        cells = _split_table_row(line)
        for index, cell in enumerate(cells[:-1]):
            name = _strip_inline_markdown(cell)
            code = _strip_inline_markdown(cells[index + 1])
            if re.fullmatch(r"[036]\d{5}", code) and _looks_like_stock_name(name):
                refs.add(f"{name}({code})")
    return tuple(sorted(refs, key=len, reverse=True))


def _collect_limit_pools(markdown_text: str) -> LimitPools:
    lines = markdown_text.splitlines()
    up: set[str] = set()
    down: set[str] = set()
    current_heading = ""
    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        heading_match = re.match(r"^(#{1,6})\s+(.+?)\s*$", stripped)
        if heading_match:
            current_heading = _strip_inline_markdown(heading_match.group(2))
            index += 1
            continue
        if not _is_table_start(lines, index):
            index += 1
            continue

        headers = _split_table_row(lines[index])
        header_texts = [_table_header_text(header) for header in headers]
        is_up_pool = (
            ("涨停池" in current_heading and "跌停" not in current_heading)
            or "连板结果" in current_heading
            or "首板结果" in current_heading
            or any("首次涨停" in header_text for header_text in header_texts)
        )
        is_down_pool = "跌停池" in current_heading
        status_indexes: list[int] = []
        if is_up_pool or is_down_pool:
            status_indexes = [
                header_index
                for header_index, header_text in enumerate(header_texts)
                if header_text in {"涨停状态", "状态"}
            ]
        index += 2
        while index < len(lines) and lines[index].lstrip().startswith("|"):
            if _is_table_separator(lines[index]):
                index += 1
                continue
            row = _split_table_row(lines[index])
            code = _stock_code_from_row(headers, row)
            if code:
                if is_up_pool:
                    up.add(code)
                if is_down_pool:
                    down.add(code)
                for status_index in status_indexes:
                    if status_index >= len(row):
                        continue
                    status = _strip_inline_markdown(row[status_index])
                    if status == "涨停":
                        up.add(code)
                    elif status == "跌停":
                        down.add(code)
            index += 1
    return LimitPools(up=frozenset(up), down=frozenset(down))


def _stock_code_cell(value: str) -> str:
    text = _strip_inline_markdown(value)
    if re.fullmatch(r"[036]\d{5}", text):
        return f'<code class="stock-ref">{_html(text)}</code>'
    return ""


def _stock_name_cell(value: str, row: list[str], stock_refs: tuple[str, ...]) -> str:
    text = _strip_inline_markdown(value)
    if not _looks_like_stock_name(text):
        return ""
    has_code_in_row = any(re.fullmatch(r"[036]\d{5}", _strip_inline_markdown(cell)) for cell in row)
    has_named_ref = any(ref.startswith(f"{text}(") for ref in stock_refs)
    if not has_code_in_row and not has_named_ref:
        return ""
    return f'<code class="stock-ref">{_html(text)}</code>'


def _stock_refs(escaped_text: str, stock_refs: tuple[str, ...]) -> str:
    if not stock_refs:
        return escaped_text
    pattern = re.compile("|".join(re.escape(_html(ref)) for ref in stock_refs))
    return pattern.sub(lambda match: f'<code class="stock-ref">{match.group(0)}</code>', escaped_text)


_INLINE_MARKUP_RE = re.compile(
    r"(?P<link>\[(?P<link_label>[^\]\n]+)\]\((?P<link_href>[^)\s]+)\))"
    r"|(?P<strong_marker>\*\*|__)(?P<strong_text>.+?)(?P=strong_marker)"
)


def _plain_inline_html(text: str, stock_refs: tuple[str, ...]) -> str:
    return _stock_refs(_html(text), stock_refs)


def _is_safe_markdown_href(href: str) -> bool:
    value = str(href or "").strip()
    if not value or value.startswith("//"):
        return False
    if any(ord(char) < 32 for char in value):
        return False
    scheme_match = re.match(r"^([A-Za-z][A-Za-z0-9+.-]*):", value)
    if scheme_match:
        return scheme_match.group(1).lower() in {"http", "https"}
    return True


def _markdown_link_html(label: str, href: str, stock_refs: tuple[str, ...]) -> str:
    href = str(href or "").strip()
    if not _is_safe_markdown_href(href):
        return _plain_inline_html(f"[{label}]({href})", stock_refs)
    external_attrs = ""
    if re.match(r"^https?://", href, flags=re.IGNORECASE):
        external_attrs = ' target="_blank" rel="noopener noreferrer"'
    return f'<a href="{_html(href)}"{external_attrs}>{_plain_inline_html(label, stock_refs)}</a>'


def _inline_without_code(text: str, stock_refs: tuple[str, ...]) -> str:
    parts: list[str] = []
    index = 0
    for match in _INLINE_MARKUP_RE.finditer(text):
        parts.append(_plain_inline_html(text[index : match.start()], stock_refs))
        if match.group("link"):
            parts.append(
                _markdown_link_html(
                    match.group("link_label"),
                    match.group("link_href"),
                    stock_refs,
                )
            )
        else:
            parts.append(f"<strong>{_plain_inline_html(match.group('strong_text'), stock_refs)}</strong>")
        index = match.end()
    parts.append(_plain_inline_html(text[index:], stock_refs))
    return "".join(parts)


def _table_cell_inline(
    headers: list[str],
    row: list[str],
    cell_index: int,
    stock_refs: tuple[str, ...],
    *,
    section_title: str = "",
    in_cycle_sector_surface: bool = False,
) -> str:
    header = headers[cell_index] if cell_index < len(headers) else ""
    cell = row[cell_index] if cell_index < len(row) else ""
    if in_cycle_sector_surface and "cycle-sector-" in cell:
        return _cycle_calendar_cell_inline(cell, stock_refs)
    if _is_front_position_conclusion_cell(headers, row, cell_index, section_title):
        return _front_position_conclusion_cell_inline(cell, stock_refs)
    if _is_stock_code_header(header):
        code_html = _stock_code_cell(cell)
        if code_html:
            return code_html
    if _is_stock_name_header(header):
        name_html = _stock_name_cell(cell, row, stock_refs)
        if name_html:
            return name_html
    return _inline(cell, stock_refs)


def _is_front_position_conclusion_cell(
    headers: list[str],
    row: list[str],
    cell_index: int,
    section_title: str,
) -> bool:
    if _plain_cell_text(section_title) not in {"日报裁决总览", "明日执行结论"}:
        return False
    if cell_index >= len(headers) or _table_header_text(headers[cell_index]) != "结论":
        return False
    label = _plain_cell_text(row[0]) if row else ""
    return label in {"仓位姿态", "明日仓位", "明日新仓"}


def _front_position_conclusion_cell_inline(text: str, stock_refs: tuple[str, ...]) -> str:
    parts = [part.strip() for part in str(text or "").split("；") if part.strip()]
    if len(parts) <= 1:
        return _inline(text, stock_refs)
    return "<br>".join(_inline(part, stock_refs) for part in parts)


def _cycle_calendar_cell_inline(text: str, stock_refs: tuple[str, ...]) -> str:
    parts: list[str] = []
    index = 0
    for match in _CYCLE_CALENDAR_TOKEN_RE.finditer(text):
        parts.append(_inline(text[index : match.start()], stock_refs))
        token = match.group(0)
        if re.fullmatch(r"<br\s*/?>", token, flags=re.IGNORECASE):
            parts.append(" ")
        else:
            span = _CYCLE_SECTOR_SPAN_RE.fullmatch(token)
            if not span:
                parts.append(_inline(token, stock_refs))
            else:
                class_name = span.group("class_name").lower()
                if class_name == "cycle-sector-dot":
                    index = match.end()
                    continue
                raw_color = _cycle_sector_span_color(span.group("style"))
                if not raw_color:
                    parts.append(_inline(token, stock_refs))
                    index = match.end()
                    continue
                raw_content = unescape(span.group("content"))
                name = _cycle_sector_name(raw_content)
                color = _cycle_sector_color_for_name(name, _cycle_sector_display_color(raw_color))
                content = _html(raw_content)
                parts.append(f'<span class="{class_name}" style="--cycle-sector-color:{color}">{content}</span>')
        index = match.end()
    parts.append(_inline(text[index:], stock_refs))
    return "".join(parts).strip()


def _is_cycle_calendar_section(section_title: str) -> bool:
    return "周期日历主视图" in str(section_title or "")


def _is_cycle_sector_surface(section_title: str) -> bool:
    title = str(section_title or "")
    return any(
        marker in title
        for marker in (
            "周期日历主视图",
            "周期解读",
            "主线成交额占比趋势",
            "近期热点板块成交额连续跟踪",
            "主线切换成交额记录",
            "小周期成交额与主线切换判断",
        )
    )


def _heading_inline(text: str, stock_refs: tuple[str, ...], *, section_title: str = "") -> str:
    if _is_cycle_sector_surface(section_title) and "cycle-sector-" in text:
        return _cycle_calendar_cell_inline(text, stock_refs)
    return _inline(text, stock_refs)


def _cycle_sector_name(content: str) -> str:
    text = unescape(content or "").strip()
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1].strip()
    return text


def _cycle_sector_color_for_name(name: str, fallback_color: str) -> str:
    return _CYCLE_SECTOR_COLOR_BY_NAME.get(str(name or "").strip(), fallback_color)


def _plain_cell_text(text: str) -> str:
    value = unescape(str(text or ""))
    value = _CYCLE_SECTOR_SPAN_RE.sub(lambda match: unescape(match.group("content") or ""), value)
    value = re.sub(r"<[^>]+>", "", value)
    value = _strip_inline_markdown(value)
    return re.sub(r"\s+", " ", value).strip()


def _sector_name_and_color_from_heading(heading_title: str) -> tuple[str, str]:
    for span in _CYCLE_SECTOR_SPAN_RE.finditer(heading_title):
        if span.group("class_name") != "cycle-sector-label":
            continue
        name = _cycle_sector_name(span.group("content"))
        raw_color = _cycle_sector_span_color(span.group("style"))
        color = _cycle_sector_color_for_name(name, _cycle_sector_display_color(raw_color))
        return name, color
    text = _plain_cell_text(heading_title)
    if "：" in text:
        text = text.rsplit("：", 1)[-1].strip()
    return text.strip("[] "), ""


def _cycle_calendar_legend_html(rows: list[list[str]]) -> str:
    items: list[tuple[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        for cell in row:
            for span in _CYCLE_SECTOR_SPAN_RE.finditer(cell):
                if span.group("class_name") != "cycle-sector-label":
                    continue
                name = _cycle_sector_name(span.group("content"))
                raw_color = _cycle_sector_span_color(span.group("style"))
                if not raw_color:
                    continue
                color = _cycle_sector_color_for_name(name, _cycle_sector_display_color(raw_color))
                if not name or name in seen:
                    continue
                seen.add(name)
                items.append((name, color))
    if not items:
        return ""
    item_html = "".join(
        (
            f'<span class="cycle-sector-legend-item" style="--cycle-sector-color:{_html(color)}">'
            '<span class="cycle-sector-legend-dot" aria-hidden="true"></span>'
            f"<span>{_html(name)}</span>"
            "</span>"
        )
        for name, color in items
    )
    return f'<div class="cycle-sector-legend" aria-label="板块颜色图例">{item_html}</div>'


def _inline(text: str, stock_refs: tuple[str, ...] = ()) -> str:
    parts: list[str] = []
    index = 0
    for match in re.finditer(r"`([^`]+)`", text):
        parts.append(_inline_without_code(text[index : match.start()], stock_refs))
        parts.append(f"<code>{_html(match.group(1))}</code>")
        index = match.end()
    parts.append(_inline_without_code(text[index:], stock_refs))
    return "".join(parts)


def _heading_anchor(title: str, used: dict[str, int]) -> str:
    normalized = re.sub(r"\s+", "-", _strip_inline_markdown(title).lower()).strip("-")
    normalized = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff-]+", "", normalized) or "section"
    count = used.get(normalized, 0)
    used[normalized] = count + 1
    if count:
        return f"{normalized}-{count + 1}"
    return normalized


_ACTION_H2_TITLES = {
    "日报裁决总览",
    "明日执行结论",
    "满仓条件执行条件",
    "50%条件执行条件",
    "50%执行条件",
    "满仓执行条件",
    "不执行条件",
}

_EVIDENCE_H2_TITLES = {
    "研究与执行分层（研究证据）",
    "股指期货持仓结构（研究证据）",
    "8月热门股双群聚与动态迁移（研究证据）",
    "市场语言翻译（研究证据）",
    "板块资金扩散淘汰赛",
    "板块资金载体预案",
    "板块资金载体差异复核",
    "T0推演T+1/T+2交易环境",
    "知识模块",
    "知识复利提示",
    "知识复利候选",
    "交易原则",
    "经验库命中",
}


def _heading_class(level: int, title: str) -> str:
    if level != 2:
        return ""
    plain_title = _plain_cell_text(title)
    if plain_title == "阅读地图":
        return "bear-section-map"
    if plain_title in _ACTION_H2_TITLES:
        return "bear-section-action"
    if plain_title in _EVIDENCE_H2_TITLES:
        return "bear-section-evidence"
    return ""


def _parse_iso_date(value: str):
    import datetime as _dt

    try:
        return _dt.datetime.strptime(str(value or "").strip(), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _date_gap_days(later: str, earlier: str) -> int | None:
    later_date = _parse_iso_date(later)
    earlier_date = _parse_iso_date(earlier)
    if later_date is None or earlier_date is None:
        return None
    return (later_date - earlier_date).days


def _skip_section(lines: list[str], index: int, level: int) -> int:
    index += 1
    while index < len(lines):
        heading_match = re.match(r"^(#{1,6})\s+.+?\s*$", lines[index].strip())
        if heading_match and len(heading_match.group(1)) <= level:
            break
        index += 1
    return index


def _is_stale_price_band_heading(lines: list[str], index: int, heading_title: str, heading_level: int, trade_date: str) -> bool:
    if "价格带风格" not in heading_title:
        return False
    target = _parse_iso_date(trade_date)
    if target is None:
        return False
    section_end = _skip_section(lines, index, heading_level)
    section_text = "\n".join(lines[index:section_end])
    match = re.search(r"最近可用窗口（截至(\d{4}-\d{2}-\d{2})）", section_text)
    if not match:
        return False
    gap_days = _date_gap_days(trade_date, match.group(1))
    return gap_days is None or gap_days > 3


def _is_judgment_review_internal_heading(parent_title: str, heading_title: str, heading_level: int) -> bool:
    if heading_level != 3 or parent_title != "判断纠偏与今日五项结论":
        return False
    return (
        re.match(r"^近\d+个已结算交易日(正确率|复盘表现)", heading_title) is not None
        or heading_title.startswith("结算上一交易日")
        or heading_title == "上一交易日未完成结算"
        or heading_title.startswith("今日判断")
    )


def _split_table_row(line: str) -> list[str]:
    value = line.strip()
    if value.startswith("|"):
        value = value[1:]
    if value.endswith("|"):
        value = value[:-1]
    return [cell.strip() for cell in value.split("|")]


def _is_table_separator(line: str) -> bool:
    cells = _split_table_row(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell.strip()) for cell in cells if cell.strip())


def _is_table_start(lines: list[str], index: int) -> bool:
    return (
        index + 1 < len(lines)
        and lines[index].lstrip().startswith("|")
        and lines[index + 1].lstrip().startswith("|")
        and _is_table_separator(lines[index + 1])
    )


def _is_position_timeline_table(headers: list[str], rows: list[list[str]]) -> bool:
    header_texts = [_table_header_text(header) for header in headers]
    if len(header_texts) < 5 or header_texts[:2] != ["轨道", "标的"]:
        return False
    lane_names = {_plain_cell_text(row[0]) for row in rows if row}
    return {"Ta旧仓", "Tb明日目标", "Tc复核位"}.issubset(lane_names)


def _is_position_day_order_table(headers: list[str], rows: list[list[str]]) -> bool:
    header_texts = [_table_header_text(header) for header in headers]
    required = ["日序", "日期", "账户位置", "执行目标", "B1/B2执行层", "动作"]
    if header_texts[: len(required)] != required:
        return False
    day_codes = {_plain_cell_text(row[0]) for row in rows if row}
    return {"Ta", "Tb", "Tc", "Td", "Te"}.issubset(day_codes)


_CANDIDATE_LIFECYCLE_HEADERS = (
    "股票",
    "板块角色",
    "反推结论",
    "对照结果",
    "最终动作",
)
_CANDIDATE_LIFECYCLE_FOCUS_SOURCES = {
    "板块推导候选",
    "板块资金载体",
    "市场情绪线候选",
    "板块核心候选",
    "高确信观察池",
    "跨线观察池",
}
_CANDIDATE_LIFECYCLE_SOURCE_ORDER = (
    "板块推导候选",
    "板块资金载体",
    "市场情绪线候选",
    "板块核心候选",
    "高确信观察池",
    "跨线观察池",
    "通用过程池",
    "观察池",
    "主线核心池",
    "次级候选池",
    "热榜",
    "综合热度",
    "成交额排行",
    "运行时观察对象",
    "其他过程来源",
)
_CANDIDATE_LIFECYCLE_FOCUS_IDENTITIES = {
    "板块锚",
    "最终执行对象",
    "风险复核样本",
}


def _is_candidate_lifecycle_table(section_title: str, headers: list[str]) -> bool:
    if "候选生命周期证据" not in _plain_cell_text(section_title):
        return False
    header_texts = {_table_header_text(header) for header in headers}
    has_source_header = bool({"首次来源", "发现路径"} & header_texts)
    has_entry_header = bool({"入口处理", "进入理由"} & header_texts)
    return has_source_header and has_entry_header and set(_CANDIDATE_LIFECYCLE_HEADERS).issubset(header_texts)


def _candidate_lifecycle_source_labels(value: str) -> list[str]:
    labels: list[str] = []
    for source in re.split(r"[、,，;；]+", _plain_cell_text(value)):
        label = candidate_source_display_label(source)
        if label and label not in labels:
            labels.append(label)
    return labels or ["其他过程来源"]


def _candidate_lifecycle_unique_values(*values: str) -> list[str]:
    result: list[str] = []
    for value in values:
        text = _plain_cell_text(value)
        if text and text != "-" and text not in result:
            result.append(text)
    return result


def _candidate_lifecycle_has_focus_identity(*values: str) -> bool:
    for value in values:
        tokens = re.split(r"[、,，;；/|·\s（）()：:]+", _plain_cell_text(value))
        if _CANDIDATE_LIFECYCLE_FOCUS_IDENTITIES.intersection(tokens):
            return True
    return False


def _candidate_lifecycle_reason(
    entry_basis: str,
    sector_role: str,
    reversal_decision: str,
    comparison_result: str,
    final_action: str,
) -> str:
    comparison = _plain_cell_text(comparison_result)
    generic_results = {
        "",
        "-",
        _plain_cell_text(sector_role),
        _plain_cell_text(reversal_decision),
        _plain_cell_text(final_action),
        "降级观察",
        "只作过程回放，不新增参与",
    }
    if comparison not in generic_results:
        return comparison
    entry = _plain_cell_text(entry_basis)
    return entry if entry and entry != "-" else comparison or "暂无关键理由"


def _candidate_lifecycle_table_html(items: list[dict[str, object]], stock_refs: tuple[str, ...]) -> str:
    body_rows = []
    for item in items:
        source_text = "、".join(str(label) for label in item["source_labels"])
        body_rows.append(
            "<tr>"
            f'<td>{_table_cell_inline(item["headers"], item["row"], item["stock_index"], stock_refs)}</td>'
            f"<td>{_inline(source_text, stock_refs)}</td>"
            f"<td>{_inline(str(item['conclusion']), stock_refs)}</td>"
            f"<td>{_inline(str(item['reason']), stock_refs)}</td>"
            "</tr>"
        )
    body = "\n".join(body_rows) or '<tr><td colspan="4">暂无候选生命周期证据</td></tr>'
    return (
        '<div class="reader-table candidate-lifecycle-table"><table>'
        '<thead><tr><th>股票</th><th>发现路径</th><th>当前结论</th><th>关键理由</th></tr></thead>'
        f"<tbody>{body}</tbody></table></div>"
    )


def _render_candidate_lifecycle_table(
    headers: list[str],
    rows: list[list[str]],
    stock_refs: tuple[str, ...],
) -> str:
    indexes = {
        "stock": _header_index(headers, "股票"),
        "source": _header_index(headers, "发现路径", "首次来源"),
        "entry": _header_index(headers, "入口处理", "进入理由"),
        "role": _header_index(headers, "板块角色"),
        "reversal": _header_index(headers, "反推结论"),
        "comparison": _header_index(headers, "对照结果"),
        "action": _header_index(headers, "最终动作"),
    }
    items: list[dict[str, object]] = []
    source_counts: dict[str, int] = {}
    for row in rows:
        padded = row + [""] * max(0, len(headers) - len(row))
        source_labels = _candidate_lifecycle_source_labels(_cell_at(padded, indexes["source"]))
        for label in source_labels:
            source_counts[label] = source_counts.get(label, 0) + 1
        conclusion_values = _candidate_lifecycle_unique_values(
            _cell_at(padded, indexes["role"]),
            _cell_at(padded, indexes["reversal"]),
            _cell_at(padded, indexes["action"]),
        )
        conclusion = " · ".join(conclusion_values) or "待确认"
        reason = _candidate_lifecycle_reason(
            _cell_at(padded, indexes["entry"]),
            _cell_at(padded, indexes["role"]),
            _cell_at(padded, indexes["reversal"]),
            _cell_at(padded, indexes["comparison"]),
            _cell_at(padded, indexes["action"]),
        )
        is_focus = bool(
            _CANDIDATE_LIFECYCLE_FOCUS_SOURCES.intersection(source_labels)
            or _candidate_lifecycle_has_focus_identity(
                _cell_at(padded, indexes["role"]),
                _cell_at(padded, indexes["reversal"]),
                _cell_at(padded, indexes["comparison"]),
                _cell_at(padded, indexes["action"]),
            )
        )
        items.append(
            {
                "headers": headers,
                "row": padded,
                "stock_index": indexes["stock"],
                "source_labels": source_labels,
                "conclusion": conclusion,
                "reason": reason,
                "is_focus": is_focus,
            }
        )

    focus_items = [item for item in items if item["is_focus"]]
    remaining_items = [item for item in items if not item["is_focus"]]
    count_order = {label: index for index, label in enumerate(_CANDIDATE_LIFECYCLE_SOURCE_ORDER)}
    source_summary = "".join(
        f"<li><span>{_html(label)}</span><strong>{count}只</strong></li>"
        for label, count in sorted(source_counts.items(), key=lambda item: (count_order.get(item[0], 999), item[0]))
    )
    overview = (
        '<div class="candidate-lifecycle-overview" role="list" aria-label="候选数量概览">'
        f'<div role="listitem"><span>候选总数</span><strong>{len(items)}只</strong></div>'
        f'<div role="listitem"><span>重点展开</span><strong>{len(focus_items)}只</strong></div>'
        f'<div role="listitem"><span>其余收起</span><strong>{len(remaining_items)}只</strong></div>'
        "</div>"
    )
    if not items:
        return (
            '<section class="candidate-lifecycle" data-candidate-count="0">'
            f"{overview}<p class=\"candidate-lifecycle-empty\">暂无候选生命周期证据</p></section>"
        )
    sources = (
        '<div class="candidate-lifecycle-sources"><strong>发现路径</strong>'
        f'<ul aria-label="发现路径分布">{source_summary}</ul></div>'
    )
    focus = ""
    if focus_items:
        focus = (
            '<div class="candidate-lifecycle-focus"><h4>重点候选</h4>'
            f"{_candidate_lifecycle_table_html(focus_items, stock_refs)}</div>"
        )
    remaining = ""
    if remaining_items:
        remaining = (
            '<details class="candidate-lifecycle-rest">'
            f'<summary><span>其余过程样本</span><strong>{len(remaining_items)}只</strong></summary>'
            f"{_candidate_lifecycle_table_html(remaining_items, stock_refs)}</details>"
        )
    return (
        f'<section class="candidate-lifecycle" data-candidate-count="{len(items)}" '
        f'data-focus-count="{len(focus_items)}" data-collapsed-count="{len(remaining_items)}">'
        f"{overview}{sources}{focus}{remaining}</section>"
    )


def _is_board_tag_rank_table_headers(headers: list[str]) -> bool:
    header_texts = {_table_header_text(header) for header in headers}
    return (
        {"排名", "标签", "出现次数"}.issubset(header_texts)
        and ("全标签占比" in header_texts or "面积占比" in header_texts)
    )


def _is_board_tag_rank_heading(heading: str) -> bool:
    return any(marker in heading for marker in ("标签热度排行榜", "标签面积占比图"))


def _is_t100_marker_before_table(lines: list[str], table_index: int) -> bool:
    previous_index = table_index - 1
    while previous_index >= 0:
        previous = lines[previous_index].strip()
        if previous:
            text = _plain_cell_text(previous)
            return re.match(r"^T-?100(?:$|[（(])", text) is not None
        previous_index -= 1
    return False


def _is_board_tag_rank_table_context(current_heading: str, lines: list[str], table_index: int) -> bool:
    return _is_board_tag_rank_heading(current_heading) or _is_t100_marker_before_table(lines, table_index)


def _markdown_starts_with_position_timeline(markdown_text: str) -> bool:
    for line in str(markdown_text or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if (
            stripped == "## 账户日序表"
            or line.lstrip().startswith("| 轨道 | 标的 |")
            or line.lstrip().startswith("| 日序 | 日期 |")
        ):
            return True
    return False


def _position_timeline_lane_html(value: str) -> str:
    text = _plain_cell_text(value)
    match = re.match(r"^([A-Z][a-z]?)(.*)$", text)
    if not match:
        return f'<span class="timeline-lane-code">{_html(text)}</span>'
    code = match.group(1)
    label = match.group(2).strip()
    return (
        f'<span class="timeline-lane-code">{_html(code)}</span>'
        f'<span class="timeline-lane-label">{_html(label)}</span>'
    )


def _position_timeline_lane_class(value: str) -> str:
    text = _plain_cell_text(value)
    if text.startswith("Ta"):
        return "timeline-row-ta"
    if text.startswith("Tb"):
        return "timeline-row-tb"
    if text.startswith("Tc"):
        return "timeline-row-tc"
    if text.startswith("Td"):
        return "timeline-row-td"
    if text.startswith("Te"):
        return "timeline-row-te"
    return "timeline-row-neutral"


def _position_timeline_asset_html(value: str) -> str:
    text = _plain_cell_text(value)
    if text in {"", "-", "无", "空仓"}:
        return f'<span class="timeline-asset-empty">{_html(text or "无")}</span>'
    match = re.match(r"^(.+?)\((\d{6})\)$", text)
    if not match:
        return f'<span class="timeline-asset-name">{_html(text)}</span>'
    return (
        f'<span class="timeline-asset-name">{_html(match.group(1))}</span>'
        f'<span class="timeline-asset-code">{_html(match.group(2))}</span>'
    )


def _position_timeline_axis_state_label(value: str) -> str:
    text = _plain_cell_text(value)
    if text in {"", "-", "无", "空仓"}:
        return "空仓"
    match = re.search(r"([\u4e00-\u9fa5A-Za-z0-9·*STst]+)\((\d{6})\)", text)
    if match:
        return match.group(1)
    return text


def _position_timeline_unknown_account_text(value: str) -> bool:
    text = _plain_cell_text(value)
    return any(
        marker in text
        for marker in (
            "持仓未输入",
            "先确认是否已有旧仓",
            "旧仓事实不清",
            "先核对实际持仓",
            "账户仓位待确认",
        )
    )


_POSITION_TIMELINE_PENDING_MARKERS = (
    "外部交易待核实",
    "外部交易记录待核实",
    "外部成交记录待核实",
    "待成交确认",
    "未确认成交，不视为B1",
    "确认已成交才视为B1",
    "核实已成交才视为B1",
    "B1事实待确认",
)


def _position_timeline_date_html(value: str) -> str:
    text = _plain_cell_text(value)
    match = re.match(r"^(.+?)（(.+?)）$", text)
    if not match:
        return f'<span class="timeline-date-main">{_html(text)}</span>'
    return (
        f'<span class="timeline-date-main">{_html(match.group(1))}</span>'
        f'<span class="timeline-date-weekday">（{_html(match.group(2))}）</span>'
    )


def _position_timeline_action_badges(value: str) -> list[tuple[str, str]]:
    text = _plain_cell_text(value)
    if _position_timeline_unknown_account_text(text):
        return [("待确认", "is-check")]
    if any(marker in text for marker in ("0%不参与", "只核实成交记录", "只核实外部交易记录")) and any(
        marker in text for marker in _POSITION_TIMELINE_PENDING_MARKERS
    ):
        return [("只核实", "is-check")]
    b2_cancelled = "取消B2" in text or "B2取消" in text
    old_position_action = any(marker in text for marker in ("只处理旧仓", "旧仓处理", "旧仓进入复核"))
    if old_position_action and b2_cancelled:
        return [("取消B2", "is-cancel")]
    if old_position_action:
        return [("持仓处理", "is-hold")]
    if any(marker in text for marker in ("没有B1/B2", "不生成B1/B2", "无B1占用", "没有B1", "没有B2")):
        return [("空仓", "is-empty")]
    if any(marker in text for marker in _POSITION_TIMELINE_PENDING_MARKERS):
        return [("待确认", "is-check")]
    if any(marker in text for marker in ("B1不成立", "不参与", "不新增参与")):
        if b2_cancelled:
            return [("取消B2", "is-cancel")]
        return [("空仓", "is-empty")]
    badges: list[tuple[str, str]] = []
    if "B1" in text or "参与权" in text:
        badges.append(("参与权", "is-participate"))
    if any(
        marker in text
        for marker in (
            "临时加B2",
            "B2确认权",
            "确认权",
            "B2确认后",
            "B2只在确认后",
        )
    ):
        badges.append(("确认权", "is-confirm"))
    if b2_cancelled:
        badges.append(("取消B2", "is-cancel"))
    if "检查B1" in text or "检查 B1" in text:
        badges.append(("检查B1", "is-check"))
    if badges:
        return badges
    if "Ta+2" in text or "尽早卖出" in text:
        return [("必执行", "is-sell")]
    if text.startswith("Tb+0"):
        return [("条件买入", "is-buy")]
    if text.startswith("Tb+1"):
        return [("持仓处理", "is-hold")]
    if text.startswith("没有Tb+0"):
        return [("空仓", "is-empty")]
    return []


def _position_timeline_segment_is_selected(value: str) -> bool:
    text = _plain_cell_text(value)
    return "Ta+2" in text or "尽早卖出" in text or text.startswith("Tb+1")


def _position_timeline_cell_text(rows: list[list[str]], index: int, date_count: int, lane_prefix: str = "") -> str:
    for row in rows:
        lane = _plain_cell_text(row[0] if row else "")
        if lane_prefix and not lane.startswith(lane_prefix):
            continue
        cells = row[2 : 2 + date_count]
        if index < len(cells):
            text = _plain_cell_text(cells[index])
            if text:
                return text
    return ""


def _position_timeline_report_index(rows: list[list[str]], date_count: int) -> int:
    for index in range(date_count):
        if "报告日确认明日目标" in _position_timeline_cell_text(rows, index, date_count, "Tb"):
            return index
    return 0


def _position_timeline_selected_indexes(rows: list[list[str]], date_count: int) -> set[int]:
    report_index = _position_timeline_report_index(rows, date_count)
    execution_index = report_index + 1
    if execution_index < date_count:
        return {execution_index}
    return set()


def _position_timeline_execution_tag(rows: list[list[str]], index: int, date_count: int) -> str:
    day_texts: list[str] = []
    ta_text = ""
    tb_text = ""
    te_text = ""
    for row in rows:
        cells = row[2 : 2 + date_count]
        if index < len(cells):
            text = _plain_cell_text(cells[index])
            day_texts.append(text)
            lane = _plain_cell_text(row[0] if row else "")
            if lane.startswith("Ta"):
                ta_text = text
            elif lane.startswith("Tb"):
                tb_text = text
            elif lane.startswith("Te"):
                te_text = text
    has_ta_exit = any("Ta+2" in text or "尽早卖出" in text for text in day_texts)
    has_tb_hold = any(text.startswith("Tb+1") for text in day_texts)
    has_tb_buy = any(text.startswith("Tb+0") for text in day_texts)
    has_no_tb = tb_text.startswith("没有Tb")
    has_empty_ta = ta_text in {"空仓", "Ta+0 空仓"}
    intent_texts = [te_text] if te_text else day_texts
    pending_confirmation = any(
        any(marker in text for marker in _POSITION_TIMELINE_PENDING_MARKERS)
        for text in intent_texts
    )
    pending_verification_only = any(
        any(marker in text for marker in ("0%不参与", "只核实成交记录", "只核实外部交易记录"))
        for text in intent_texts
    ) and pending_confirmation
    explicit_participation = any(
        "B1参与权" in text or "参与权" in text
        for text in intent_texts
    )
    if any(_position_timeline_unknown_account_text(text) for text in intent_texts):
        return "待确认"
    if pending_verification_only:
        return "空仓执行"
    if pending_confirmation and not explicit_participation:
        return "待确认"
    if any(
        marker in text
        for text in intent_texts
        for marker in ("没有B1/B2", "空仓等待B1资格", "明日空仓")
    ):
        return "空仓执行"
    if any("取消B2" in text or "B2取消" in text for text in intent_texts):
        return "取消B2"
    if any(
        any(marker in text for marker in ("B1不成立", "不参与", "不新增参与"))
        for text in intent_texts
    ):
        return "空仓执行"
    if has_ta_exit and has_no_tb and not has_tb_hold and not has_tb_buy:
        return "空仓执行"
    if has_tb_hold:
        return "持仓处理"
    if ta_text.startswith("Ta+1"):
        return "持仓处理"
    if has_ta_exit:
        return "卖出处理"
    if has_tb_buy:
        return "条件买入"
    if has_no_tb and has_empty_ta and not has_tb_hold and not has_tb_buy:
        return "空仓执行"
    if any(
        any(marker in text for marker in ("只处理旧仓", "旧仓处理", "旧仓进入复核"))
        for text in intent_texts
    ):
        return "持仓处理"
    if explicit_participation:
        return "参与权"
    if any(
        any(marker in text for marker in ("没有B1/B2", "不生成B1/B2", "无B1占用", "没有B1", "没有B2"))
        for text in intent_texts
    ):
        return "空仓执行"
    if any("确认权" in text for text in intent_texts):
        return "确认权"
    if any("参与权" in text or "B1" in text for text in intent_texts):
        return "参与权"
    if any("不新增参与" in text or "没有B2" in text for text in intent_texts):
        return "空仓执行"
    return ""


def _position_timeline_execution_tag_class(tag: str) -> str:
    if "待确认" in tag:
        return "is-check"
    if "空仓" in tag:
        return "is-empty"
    if "确认权" in tag:
        return "is-confirm"
    if "参与权" in tag:
        return "is-buy"
    if "取消B2" in tag:
        return "is-sell"
    if "买入" in tag:
        return "is-buy"
    if "卖出" in tag:
        return "is-sell"
    if "持仓" in tag:
        return "is-hold"
    return "is-neutral"


def _position_timeline_axis_state_class(
    label: str,
    index: int,
    report_index: int,
    selected_indexes: set[int],
) -> str:
    if not label:
        return ""
    if label == "空仓":
        return "is-empty"
    if label == "持仓未输入":
        return "is-unknown"
    if index in selected_indexes:
        return "is-buy"
    if index == report_index:
        return "is-report"
    if index < report_index:
        return "is-history"
    return "is-neutral"


def _position_timeline_axis_state_tags(rows: list[list[str]], date_count: int) -> dict[int, str]:
    tags: dict[int, str] = {}
    for index in range(date_count):
        empty_label = ""
        for row in rows:
            cells = row[2 : 2 + date_count]
            if index >= len(cells) or not _plain_cell_text(cells[index]):
                continue
            cell_text = _plain_cell_text(cells[index])
            label = (
                "持仓未输入"
                if _position_timeline_unknown_account_text(cell_text)
                else _position_timeline_axis_state_label(row[1] if len(row) > 1 else "")
            )
            if label and label != "空仓":
                tags[index] = label
                break
            if label:
                empty_label = label
        if index not in tags and empty_label:
            tags[index] = empty_label
    return tags


def _position_timeline_date_markers_html(
    index: int,
    report_index: int,
    selected_indexes: set[int],
    execution_tags: dict[int, str],
    state_tags: dict[int, str] | None = None,
) -> str:
    parts: list[str] = []
    state_label = (state_tags or {}).get(index, "")
    if state_label:
        state_class = _position_timeline_axis_state_class(state_label, index, report_index, selected_indexes)
        parts.append(
            f'<span class="timeline-date-state {state_class}">{_html(state_label)}</span>'
        )
    if index == report_index:
        parts.append('<span class="timeline-date-context">报告日</span>')
    elif index < report_index:
        parts.append('<span class="timeline-date-source">旧路径来源</span>')
    if index in selected_indexes:
        parts.append('<span class="timeline-date-action">执行日</span>')
    tag = execution_tags.get(index, "")
    if tag:
        tag_class = _position_timeline_execution_tag_class(tag)
        parts.append(
            f'<span class="timeline-date-intent {tag_class}">{_html(tag)}</span>'
        )
    return "".join(parts)


def _position_timeline_state_parts(value: str) -> tuple[str, str]:
    text = _plain_cell_text(value)
    missing_match = re.match(r"^(没有(?:Ta|Tb|Tc|Td|Te)\+\d+)[，,、\s]*(.*)$", text)
    if missing_match:
        return missing_match.group(1), missing_match.group(2).strip()
    state_match = re.match(r"^((?:Ta|Tb|Tc|Td|Te)(?:\+\d+)?)\s*(.*)$", text)
    if state_match:
        return state_match.group(1), state_match.group(2).strip()
    return text, ""


def _position_timeline_state_class(value: str) -> str:
    text = _plain_cell_text(value)
    if text.startswith("没有"):
        return "is-missing"
    if text == "空仓" or text == "Ta+0 空仓":
        return "is-empty"
    if "Ta+2" in text or "尽早卖出" in text:
        return "is-exit"
    if text.startswith("Ta+"):
        return "is-ta"
    if text.startswith("Tb+"):
        return "is-tb"
    if text.startswith("Tc+"):
        return "is-tc"
    if text.startswith("Td"):
        return "is-td"
    if text.startswith("Te"):
        return "is-te"
    return "is-neutral"


def _position_timeline_segment_html(value: str) -> str:
    code, description = _position_timeline_state_parts(value)
    class_name = _position_timeline_state_class(value)
    action_badges = _position_timeline_action_badges(value)
    selected_class = " is-selected" if _position_timeline_segment_is_selected(value) else ""
    description_html = (
        f'<span class="timeline-state-text">{_html(description)}</span>' if description else ""
    )
    badge_html = (
        (
            '<span class="timeline-action-badges">'
            + "".join(
                f'<span class="timeline-action-badge {badge_class}">{_html(action_badge)}</span>'
                for action_badge, badge_class in action_badges
            )
            + "</span>"
            if action_badges
            else ""
        )
    )
    title = _plain_cell_text(value)
    tooltip = _html(title)
    return (
        f'<span class="timeline-bar-segment {class_name}{selected_class}" tabindex="0" '
        f'data-el-tooltip="{tooltip}" aria-label="{tooltip}">'
        f'<span class="timeline-state-code">{_html(code)}</span>'
        f"{description_html}"
        f"{badge_html}"
        "</span>"
    )


def _position_timeline_track_groups(cells: list[str]) -> list[tuple[int, list[str]]]:
    groups: list[tuple[int, list[str]]] = []
    start: int | None = None
    active_cells: list[str] = []
    for index, cell in enumerate(cells):
        class_name = _position_timeline_state_class(cell)
        text = _plain_cell_text(cell)
        is_track_item = bool(text) and class_name != "is-empty"
        if is_track_item:
            if start is None:
                start = index
            active_cells.append(cell)
            continue
        if start is not None:
            groups.append((start, active_cells))
            start = None
            active_cells = []
    if start is not None:
        groups.append((start, active_cells))
    return groups


def _position_timeline_bar_class(cells: list[str]) -> str:
    classes = {_position_timeline_state_class(cell) for cell in cells}
    if classes == {"is-missing"}:
        return "is-missing"
    return "is-active"


def _position_timeline_track_html(cells: list[str]) -> str:
    groups = _position_timeline_track_groups(cells)
    bars: list[str] = []
    for start, group_cells in groups:
        segments = "".join(_position_timeline_segment_html(cell) for cell in group_cells)
        bars.append(
            f'<div class="timeline-bar {_position_timeline_bar_class(group_cells)}" '
            f'style="--bar-start: {start + 1}; --bar-span: {len(group_cells)}; '
            f'--bar-segments: {len(group_cells)}">{segments}</div>'
        )
    return (
        f'<div class="timeline-track" style="--timeline-days: {len(cells)}">'
        f"{''.join(bars)}"
        "</div>"
    )


def _render_position_timeline_table(
    headers: list[str],
    rows: list[list[str]],
    stock_refs: tuple[str, ...],
    *,
    report_index: int | None = None,
    selected_indexes: set[int] | None = None,
    aria_label: str = "Ta Tb Tc 持仓时间轴",
) -> str:
    date_headers = headers[2:]
    if report_index is None:
        report_index = _position_timeline_report_index(rows, len(date_headers))
    if selected_indexes is None:
        selected_indexes = _position_timeline_selected_indexes(rows, len(date_headers))
    execution_tags = {
        index: _position_timeline_execution_tag(rows, index, len(date_headers))
        for index in selected_indexes
    }
    state_tags = _position_timeline_axis_state_tags(rows, len(date_headers))
    colgroup = (
        '<colgroup><col class="timeline-col-lane"><col class="timeline-col-asset">'
        '<col class="timeline-col-track">'
        + "</colgroup>"
    )
    header_cells = [
        '<th class="timeline-axis-origin" scope="col"><span>轨道</span></th>',
        '<th class="timeline-axis-asset" scope="col"><span>标的</span></th>',
        (
            '<th class="timeline-axis-track" scope="col">'
            f'<div class="timeline-axis-grid" style="--timeline-days: {len(date_headers)}">'
            + "".join(
                (
                    f'<span class="timeline-axis-date{" is-report-day" if index == report_index else ""}'
                    f'{" is-selected" if index in selected_indexes else ""}">'
                    f'{_position_timeline_date_html(header)}'
                    f'{_position_timeline_date_markers_html(index, report_index, selected_indexes, execution_tags, state_tags)}'
                    "</span>"
                )
                for index, header in enumerate(date_headers)
            )
            + "</div></th>"
        ),
    ]
    body_rows: list[str] = []
    for row in rows:
        padded = row + [""] * max(0, len(headers) - len(row))
        lane = padded[0]
        asset = padded[1]
        row_class = _position_timeline_lane_class(lane)
        track = _position_timeline_track_html(padded[2 : len(headers)])
        body_rows.append(
            f'<tr class="timeline-row {row_class}">'
            f'<th class="timeline-lane" scope="row">{_position_timeline_lane_html(lane)}</th>'
            f'<td class="timeline-asset">{_position_timeline_asset_html(asset)}</td>'
            f'<td class="timeline-track-cell" style="--timeline-days: {len(date_headers)}">{track}</td>'
            "</tr>"
        )
    body = "\n".join(body_rows)
    return (
        f'<div class="position-timeline-shell{" is-day-order" if "账户日序" in aria_label else ""}" '
        f'role="region" aria-label="{_html(aria_label)}">'
        '<div class="position-timeline-scroll">'
        '<table class="position-timeline-table">'
        f"{colgroup}<thead><tr>{''.join(header_cells)}</tr></thead><tbody>{body}</tbody>"
        "</table></div></div>"
    )


def _position_day_order_lane_label(code: str, account: str) -> str:
    text = _plain_cell_text(code)
    if text == "Td":
        return "Td今日"
    if text == "Te":
        return "Te明日"
    if text == "Tc":
        return "Tc上一日"
    if text == "Tb":
        return "Tb历史"
    if text == "Ta":
        return "Ta最远"
    account_text = _plain_cell_text(account)
    return f"{text}{account_text}" if account_text else text


def _position_day_order_asset(code: str, account: str, target: str) -> str:
    target_text = _plain_cell_text(target)
    if target_text not in {"", "-", "无"}:
        return target_text
    if _plain_cell_text(code) == "Te":
        return "无"
    account_text = _plain_cell_text(account)
    if "持仓未输入" in account_text:
        return "持仓未输入"
    stock_match = re.search(r"([\u4e00-\u9fa5A-Za-z0-9·]+)\((\d{6})\)", account_text)
    if stock_match:
        return f"{stock_match.group(1)}({stock_match.group(2)})"
    path_match = re.search(r"路径[：:]\s*([^；，,|]+)", account_text)
    if path_match:
        path_text = path_match.group(1).strip()
        if path_text and path_text not in {"-", "无", "空仓"}:
            return path_text
    return "无"


def _position_day_order_cell_text(code: str, account: str, b12: str, action: str) -> str:
    code_text = _plain_cell_text(code)
    details = [
        _plain_cell_text(account),
        _plain_cell_text(b12),
        _plain_cell_text(action),
    ]
    detail_text = "；".join(part for part in details if part)
    return f"{code_text} {detail_text}".strip()


def _position_day_order_projection_rows(headers: list[str], rows: list[list[str]]) -> list[dict]:
    normalized = []
    for row in rows:
        padded = row + [""] * max(0, len(headers) - len(row))
        code, row_date, account, target, b12, action = padded[:6]
        normalized.append(
            {
                "day_code": _plain_cell_text(code),
                "date": _plain_cell_text(row_date),
                "account": _plain_cell_text(account),
                "target": _plain_cell_text(target),
                "b12": _plain_cell_text(b12),
                "action": _plain_cell_text(action),
            }
        )
    return normalized


def _position_dual_cluster_status_class(value: str) -> str:
    return {
        "confirmed": "is-confirmed",
        "candidate": "is-candidate",
        "empty": "is-empty",
        "weakened": "is-weakened",
        "invalidated": "is-weakened",
        "coexisting": "is-coexisting",
        "impact_to_core": "is-transition",
        "core_to_impact": "is-transition",
        "dynamic_decay": "is-weakened",
        "core_weakened": "is-weakened",
    }.get(_plain_cell_text(value), "is-unresolved")


def _position_dual_cluster_role_cell(value: object, stock_refs: tuple[str, ...]) -> str:
    role = value if isinstance(value, dict) else {}
    status = _plain_cell_text(role.get("status"))
    text = _plain_cell_text(role.get("text")) or "角色待确认"
    return (
        f'<span class="position-dual-cluster-role {_position_dual_cluster_status_class(status)}" '
        f'data-role-status="{_html(status or "unresolved")}">'
        f"{_inline(text, stock_refs)}</span>"
    )


def _position_day_order_raw_table_html(
    headers: list[str],
    rows: list[list[str]],
    stock_refs: tuple[str, ...],
) -> str:
    header_html = "".join(f"<th>{_inline(header, stock_refs)}</th>" for header in headers)
    body_rows = []
    for row in rows:
        padded = row + [""] * max(0, len(headers) - len(row))
        body_rows.append(
            "<tr>"
            + "".join(
                f"<td>{_inline(cell, stock_refs)}</td>"
                for cell in padded[: len(headers)]
            )
            + "</tr>"
        )
    body = "".join(body_rows) or f'<tr><td colspan="{len(headers)}">暂无账户日序事实</td></tr>'
    return (
        '<div class="reader-table position-day-order-raw-table" role="region" '
        'aria-label="账户日序原始六列事实" tabindex="0">'
        f"<table><thead><tr>{header_html}</tr></thead><tbody>{body}</tbody></table></div>"
    )


def _render_position_dual_cluster_table(
    projection: dict,
    stock_refs: tuple[str, ...],
) -> str:
    rows = [row for row in list(projection.get("rows") or []) if isinstance(row, dict)]
    body_rows = []
    for row in rows:
        code = _plain_cell_text(row.get("day_code"))
        row_date = _plain_cell_text(row.get("date")) or "日期未记录"
        temporal_role = _plain_cell_text(row.get("temporal_role")) or "时间角色待确认"
        transition = row.get("transition") if isinstance(row.get("transition"), dict) else {}
        transition_status = _plain_cell_text(transition.get("status"))
        transition_text = _plain_cell_text(transition.get("text")) or "迁移待确认"
        body_rows.append(
            f'<tr class="position-dual-cluster-row position-dual-cluster-row-{_html(code.lower())}" '
            f'data-day-code="{_html(code)}">'
            '<th scope="row"><span class="position-dual-cluster-code">'
            f"{_html(code)}</span><strong>{_html(temporal_role)}</strong><small>{_html(row_date)}</small></th>"
            f'<td data-label="持续核心端">{_position_dual_cluster_role_cell(row.get("persistent_core"), stock_refs)}</td>'
            f'<td data-label="动态冲击端">{_position_dual_cluster_role_cell(row.get("dynamic_impact"), stock_refs)}</td>'
            f'<td data-label="迁移与反证"><span class="position-dual-cluster-transition {_position_dual_cluster_status_class(transition_status)}">'
            f"{_inline(transition_text, stock_refs)}</span></td>"
            f'<td data-label="账户容量"><span class="position-dual-cluster-capacity">{_inline(row.get("capacity") or "容量待确认", stock_refs)}</span></td>'
            f'<td data-label="动作"><span class="position-dual-cluster-action">{_inline(row.get("action") or "事实不足", stock_refs)}</span></td>'
            "</tr>"
        )
    body = "".join(body_rows) or '<tr><td colspan="6">账户双轨事实不足</td></tr>'
    artifact_hash = _plain_cell_text(projection.get("artifact_hash"))
    return (
        '<section class="position-dual-cluster" aria-label="Ta Te 账户双轨日序" '
        f'data-artifact-hash="{_html(artifact_hash)}">'
        '<div class="position-dual-cluster-head"><div><span>账户日序双轨</span>'
        '<h4>持续核心端与动态冲击端分开看</h4></div>'
        '<p>B1先取得参与权，B2只在确认后补；计划容量不等于已经持有。</p></div>'
        '<div class="position-dual-cluster-scroll" role="region" aria-label="账户双轨主视图" tabindex="0">'
        '<table class="position-dual-cluster-table"><thead><tr>'
        '<th>日序</th><th>持续核心端</th><th>动态冲击端</th><th>迁移与反证</th><th>账户容量</th><th>动作</th>'
        f"</tr></thead><tbody>{body}</tbody></table></div>"
        '<p class="position-dual-cluster-scope">旧仓不自动等于市场核心，新目标不确认参与者身份；'
        f'只读投影哈希：<code>{_html(artifact_hash)}</code></p></section>'
    )


def _render_position_day_order_table(
    headers: list[str],
    rows: list[list[str]],
    stock_refs: tuple[str, ...],
) -> str:
    date_headers: list[str] = []
    timeline_rows: list[list[str]] = []
    report_index = 0
    selected_indexes: set[int] = set()
    padded_rows: list[list[str]] = []
    for row in rows:
        padded = row + [""] * max(0, len(headers) - len(row))
        padded_rows.append(padded)
        date_headers.append(padded[1])
    for index, padded in enumerate(padded_rows):
        code, _date, account, target, b12, action = padded[:6]
        code_text = _plain_cell_text(code)
        if code_text == "Td":
            report_index = index
        if code_text == "Te":
            selected_indexes.add(index)
        cells = [""] * len(date_headers)
        cells[index] = _position_day_order_cell_text(code, account, b12, action)
        timeline_rows.append(
            [
                _position_day_order_lane_label(code, account),
                _position_day_order_asset(code, account, target),
                *cells,
            ]
        )
    timeline_headers = ["轨道", "标的", *date_headers]
    timeline_html = _render_position_timeline_table(
        timeline_headers,
        timeline_rows,
        stock_refs,
        report_index=report_index,
        selected_indexes=selected_indexes,
        aria_label="Ta Te 账户日序",
    )
    projection_rows = _position_day_order_projection_rows(headers, rows)
    target_date = next(
        (
            item.get("date")
            for item in projection_rows
            if item.get("day_code") == "Td"
        ),
        "",
    )
    projection = build_account_day_order_dual_cluster(
        projection_rows,
        target_date=target_date,
    )
    dual_cluster_html = _render_position_dual_cluster_table(projection, stock_refs)
    raw_table_html = _position_day_order_raw_table_html(headers, rows, stock_refs)
    return (
        dual_cluster_html
        + '<details class="position-day-order-facts" data-position-day-order-facts>'
        '<summary><span>账户日序原始事实</span><small>六列表与原时间轴，默认收起</small></summary>'
        '<div class="position-day-order-facts-body">'
        f"{raw_table_html}{timeline_html}</div></details>"
    )


def _is_fenced_code_start(line: str) -> bool:
    return line.strip().startswith("```")


def _render_fenced_code(lines: list[str], index: int) -> tuple[str, int]:
    opening = lines[index].strip()
    language = opening[3:].strip()
    index += 1
    code_lines = []
    while index < len(lines):
        if lines[index].strip().startswith("```"):
            index += 1
            break
        code_lines.append(lines[index])
        index += 1
    code_text = "\n".join(code_lines)
    if language == "mermaid":
        axis_labels: list[str] = []
        filtered_code_lines = []
        for code_line in code_lines:
            axis_match = re.match(r"^\s*%%\s*bear-axis:\s*(.*?)\s*$", code_line)
            if axis_match:
                axis_labels = [item.strip() for item in axis_match.group(1).split("|") if item.strip()]
                continue
            filtered_code_lines.append(code_line)
        code_text = "\n".join(filtered_code_lines)
        kind_attr = ' data-mermaid-kind="gantt"' if re.search(r"(?m)^\s*gantt\s*$", code_text) else ""
        axis_html = ""
        if axis_labels:
            axis_items = "".join(
                f'<span class="bear-gantt-axis-item">{_html(label)}</span>' for label in axis_labels
            )
            axis_html = f'<div class="bear-gantt-axis" aria-label="交易日时间轴">{axis_items}</div>'
        diagram_html = (
            '<div class="fenced-code mermaid" data-mermaid-diagram="true"'
            + kind_attr
            + ">"
            + _html(code_text)
            + "</div>"
        )
        if axis_html:
            return f'<div class="bear-gantt-shell">{axis_html}{diagram_html}</div>', index
        return diagram_html, index
    lang_attr = f' lang="{_html(language)}"' if language else ""
    return (
        '<pre class="fenced-code"><code class="fenced-code-content"'
        + lang_attr
        + ">"
        + _html(code_text)
        + "</code></pre>",
        index,
    )


def _numeric_percent(value: str) -> float | None:
    match = re.search(r"(-?\d+(?:\.\d+)?)\s*%", value)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _numeric_int(value: str) -> int | None:
    match = re.search(r"(?<!\d)(\d{2,5})(?!\d)", value)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _numeric_amount_yi(value: str) -> float | None:
    match = re.search(r"(-?\d+(?:\.\d+)?)\s*亿", value)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _numeric_amount_yi_cell(value: str, header: str) -> float | None:
    amount_yi = _numeric_amount_yi(value)
    if amount_yi is not None:
        return amount_yi
    if "亿" not in _plain_cell_text(header):
        return None
    return _chart_number_or_none(_plain_cell_text(value))


def _numeric_pct_point(value: str) -> float | None:
    match = re.search(r"([+-]?\d+(?:\.\d+)?)\s*pct", value, flags=re.IGNORECASE)
    if not match:
        return _numeric_percent(value)
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _header_index(headers: list[str], *candidates: str) -> int:
    normalized = {_table_header_text(candidate) for candidate in candidates}
    for index, header in enumerate(headers):
        if _table_header_text(header) in normalized:
            return index
    return -1


def _cell_at(row: list[str], index: int) -> str:
    return row[index] if 0 <= index < len(row) else ""


def _limit_status_from_turnover_row(
    change_pct: float | None,
    candle_text: str,
    stock_code: str = "",
    stock_name: str = "",
) -> str:
    text = _plain_cell_text(candle_text)
    if "涨停" in text:
        return "涨停"
    if "跌停" in text:
        return "跌停"
    if change_pct is None:
        return ""

    limit_threshold_pct = get_limit_up_pct(stock_code, stock_name) * 100
    if change_pct >= limit_threshold_pct:
        return "涨停"
    if change_pct <= -limit_threshold_pct:
        return "跌停"
    if change_pct <= -10:
        return "大幅回撤"
    return ""


def _collect_table(lines: list[str], index: int) -> tuple[list[str], list[list[str]], int]:
    headers = _split_table_row(lines[index])
    index += 2
    rows: list[list[str]] = []
    while index < len(lines) and lines[index].lstrip().startswith("|"):
        if not _is_table_separator(lines[index]):
            rows.append(_split_table_row(lines[index]))
        index += 1
    return headers, rows, index


def _table_has_headers(lines: list[str], index: int, *required_headers: str) -> bool:
    if not _is_table_start(lines, index):
        return False
    headers = _split_table_row(lines[index])
    return all(_header_index(headers, header) >= 0 for header in required_headers)


_SECTOR_CYCLE_FALLBACK_COLORS = (
    "#945C6E",
    "#2F7FB8",
    "#947A5C",
    "#DD4C4F",
    "#5C7F94",
    "#4F8A87",
    "#8F945C",
    "#A75E9B",
)


def _valid_iso_date(value: str) -> str:
    text = _plain_cell_text(value)
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        return ""


def _sector_relative_path_interpretation(
    record: Mapping[str, object] | None,
    *,
    path_complete: bool,
) -> str:
    record = record if isinstance(record, Mapping) else {}
    status = str(record.get("status") or "").strip()
    metric = record.get("relative_strength_metric")
    metric = metric if isinstance(metric, Mapping) else {}
    metric_value = _chart_number_or_none(metric.get("value"))
    rank = record.get("relative_strength_rank")
    if status == "阶段主线失效":
        return "阶段主线失效"
    if status == "阶段主线弱化":
        return "阶段主线弱化"
    if (
        status == "阶段主线已确认"
        and path_complete
        and str(record.get("divergence_test_status") or "") == "分歧已修复"
    ):
        return "高质量修复"
    if (
        status == "阶段主线已确认"
        and path_complete
        and metric_value is not None
        and metric_value > 0
        and rank == 1
    ):
        return "真正转强"
    if path_complete and metric_value is not None and metric_value > 0:
        return "普通反弹"
    if not path_complete:
        return "相对价格路径未生成"
    return "相对强弱未确认"


def _sector_relative_price_absorption(
    *,
    is_evaluated: bool,
    space_stage: str,
    edge_type: str,
) -> str:
    if not is_evaluated:
        return "待比较"
    if edge_type == "剩余惯性" or space_stage in {"市场响应", "全面共识"}:
        return "价格吸收较充分"
    if space_stage in {"局部秩序形成", "板块扩散"}:
        return "仍有传导空间"
    return "价格吸收未确认"


def _sector_cycle_lane_on_dates(
    lane: Mapping[str, object] | None,
    dates: list[str],
    recorded_dates: list[str],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    lane = lane if isinstance(lane, Mapping) else {}
    date_indexes = {record_date: index for index, record_date in enumerate(dates)}
    recorded_date_set = {
        record_date
        for value in recorded_dates
        if (record_date := _valid_iso_date(str(value or ""))) in date_indexes
    }
    active_indexes: set[int] = set()
    for run in lane.get("runs") if isinstance(lane.get("runs"), list) else []:
        if not isinstance(run, Mapping):
            continue
        start_date = _valid_iso_date(str(run.get("start_date") or ""))
        end_date = _valid_iso_date(str(run.get("end_date") or ""))
        if not start_date or not end_date:
            continue
        active_indexes.update(
            date_indexes[record_date]
            for record_date in recorded_date_set
            if start_date <= record_date <= end_date
        )
    runs: list[dict[str, object]] = []
    run_start: int | None = None
    for index in range(len(dates)):
        is_active = index in active_indexes
        if is_active and run_start is None:
            run_start = index
        if run_start is not None and (not is_active or index == len(dates) - 1):
            run_end = index if is_active else index - 1
            runs.append(
                {
                    "start_index": run_start,
                    "end_index": run_end,
                    "start_date": dates[run_start],
                    "end_date": dates[run_end],
                }
            )
            run_start = None

    observations = []
    for observation in (
        lane.get("observations") if isinstance(lane.get("observations"), list) else []
    ):
        if not isinstance(observation, Mapping):
            continue
        observation_date = _valid_iso_date(str(observation.get("date") or ""))
        if observation_date not in date_indexes:
            continue
        normalized = dict(observation)
        normalized["date_index"] = date_indexes[observation_date]
        observations.append(normalized)
    observations.sort(key=lambda item: int(item.get("date_index") or 0))
    return runs, observations


_SECTOR_FEEDBACK_EVENT_LABELS = {
    "price_response": "价格响应",
    "cross_day_feedback": "跨日反馈",
    "rotation": "轮动",
    "reflow": "冷却后回流",
    "turnover_participation": "成交参与",
    "capital_return": "资金回流",
    "main_fund_inflow": "主力净流入",
    "institution_net_buy": "机构净买",
}


def _sector_feedback_timeline(
    record: Mapping[str, object] | None,
    *,
    dates: list[str],
    normalized_path: list[dict[str, object]],
    runs: list[dict[str, object]],
    observations: list[dict[str, object]],
    capital_events: list[Mapping[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[str]]:
    record = record if isinstance(record, Mapping) else {}
    date_indexes = {record_date: index for index, record_date in enumerate(dates)}
    events_by_date: dict[str, dict[str, object]] = {}

    def add_event(
        record_date: str,
        kind: str,
        *,
        detail: str = "",
        amount_yi: float | None = None,
        stock_names: list[str] | None = None,
    ) -> None:
        normalized_date = _valid_iso_date(record_date)
        label = _SECTOR_FEEDBACK_EVENT_LABELS.get(kind)
        if normalized_date not in date_indexes or not label:
            return
        event = events_by_date.setdefault(
            normalized_date,
            {
                "date": normalized_date,
                "date_index": date_indexes[normalized_date],
                "kinds": [],
                "labels": [],
                "details": [],
                "details_by_kind": {},
                "stock_names_by_kind": {},
            },
        )
        if kind not in event["kinds"]:
            event["kinds"].append(kind)
            event["labels"].append(label)
        if detail and detail not in event["details"]:
            event["details"].append(detail)
        if detail:
            details_by_kind = event.get("details_by_kind")
            if isinstance(details_by_kind, dict):
                kind_details = details_by_kind.setdefault(kind, [])
                if detail not in kind_details:
                    kind_details.append(detail)
        if amount_yi is not None:
            amounts = event.setdefault("amounts_yi", {})
            if isinstance(amounts, dict):
                amounts[kind] = round(amount_yi, 6)
        if stock_names:
            names = event.setdefault("stock_names", [])
            stock_names_by_kind = event.get("stock_names_by_kind")
            kind_stock_names = (
                stock_names_by_kind.setdefault(kind, [])
                if isinstance(stock_names_by_kind, dict)
                else []
            )
            if isinstance(names, list):
                for stock_name in stock_names:
                    if stock_name and stock_name not in names:
                        names.append(stock_name)
                    if stock_name and stock_name not in kind_stock_names:
                        kind_stock_names.append(stock_name)

    for point in normalized_path:
        if _chart_number_or_none(point.get("normalized_value")) is None:
            continue
        add_event(
            str(point.get("date") or ""),
            "price_response",
            detail=f"相对路径 {point['normalized_value']:.1f}",
        )
    for record_date in record.get("active_trade_dates") if isinstance(record.get("active_trade_dates"), list) else []:
        add_event(str(record_date or ""), "cross_day_feedback")
    for run in runs:
        if not isinstance(run, Mapping):
            continue
        start_index = int(run.get("start_index") or 0)
        end_index = int(run.get("end_index") or 0)
        for date_index in range(max(start_index, 0), min(end_index, len(dates) - 1) + 1):
            add_event(dates[date_index], "rotation")
    for observation in observations:
        if not isinstance(observation, Mapping):
            continue
        share_pct = _chart_number_or_none(observation.get("share_pct"))
        turnover = _chart_number_or_none(observation.get("turnover"))
        if share_pct is None and (turnover is None or turnover <= 0):
            continue
        detail_parts = []
        if share_pct is not None:
            detail_parts.append(f"成交占比 {share_pct:.1f}%")
        if turnover is not None and turnover > 0:
            detail_parts.append(f"板块成交额 {turnover:.2f}亿")
        add_event(
            str(observation.get("date") or ""),
            "turnover_participation",
            detail="；".join(detail_parts),
        )
    for record_date in record.get("reflow_dates") if isinstance(record.get("reflow_dates"), list) else []:
        add_event(str(record_date or ""), "reflow")
    for evidence in record.get("repair_evidence") if isinstance(record.get("repair_evidence"), list) else []:
        if not isinstance(evidence, Mapping):
            continue
        kind = str(evidence.get("kind") or "")
        if kind == "capital_return":
            add_event(
                str(evidence.get("trade_date") or evidence.get("source_date") or ""),
                "capital_return",
            )
    for evidence in capital_events:
        if not isinstance(evidence, Mapping):
            continue
        amount_yi = _chart_number_or_none(evidence.get("amount_yi"))
        add_event(
            str(evidence.get("date") or ""),
            str(evidence.get("kind") or ""),
            detail=str(evidence.get("detail") or ""),
            amount_yi=amount_yi,
            stock_names=[
                str(value or "").strip()
                for value in evidence.get("stock_names")
                if str(value or "").strip()
            ]
            if isinstance(evidence.get("stock_names"), list)
            else None,
        )

    priority = (
        "institution_net_buy",
        "main_fund_inflow",
        "capital_return",
        "reflow",
        "rotation",
        "cross_day_feedback",
        "price_response",
        "turnover_participation",
    )
    events = sorted(events_by_date.values(), key=lambda item: int(item["date_index"]))
    for event in events:
        kinds = event.get("kinds") if isinstance(event.get("kinds"), list) else []
        event["primary_kind"] = next((kind for kind in priority if kind in kinds), "")

    event_indexes = [int(event["date_index"]) for event in events]
    stage_start_date = _valid_iso_date(str(record.get("stage_start_date") or ""))
    last_confirmed_date = _valid_iso_date(str(record.get("last_confirmed_date") or ""))
    as_of_date = _valid_iso_date(str(record.get("as_of_date") or ""))
    status = str(record.get("status") or "").strip()
    start_index: int | None = None
    end_index: int | None = None
    range_kind = "observed_feedback"
    start_basis = "首次可核实反馈"
    end_basis = "最近可核实反馈"

    source_start_date = ""
    source_end_date = ""
    allow_observed_feedback_fallback = True
    if stage_start_date:
        if status in {"阶段主线弱化", "阶段主线失效"} and last_confirmed_date:
            candidate_end_date = last_confirmed_date
            end_basis = "最近完整续证"
        elif status == "阶段主线已确认" and last_confirmed_date:
            candidate_end_date = last_confirmed_date
            end_basis = "最近完整续证"
        elif event_indexes:
            candidate_end_date = dates[max(event_indexes)]
        else:
            candidate_end_date = as_of_date or stage_start_date
        source_start_date = stage_start_date
        source_end_date = candidate_end_date
        has_fixed_confirmation_end = bool(
            last_confirmed_date
            and status in {"阶段主线已确认", "阶段主线弱化", "阶段主线失效"}
        )
        if has_fixed_confirmation_end:
            allow_observed_feedback_fallback = False
        candidate_end_index = next(
            (
                index
                for index in range(len(dates) - 1, -1, -1)
                if dates[index] <= candidate_end_date
            ),
            None,
        )
        if stage_start_date < dates[0]:
            candidate_start_index = next(
                (
                    event_index
                    for event_index in event_indexes
                    if candidate_end_index is not None and event_index <= candidate_end_index
                ),
                None,
            )
            if candidate_start_index is not None:
                start_basis = "轴内首次可核实反馈"
        else:
            candidate_start_index = next(
                (
                    index
                    for index, record_date in enumerate(dates)
                    if record_date >= stage_start_date
                ),
                None,
            )
        if (
            candidate_start_index is not None
            and candidate_end_index is not None
            and candidate_start_index <= candidate_end_index
        ):
            start_index = candidate_start_index
            end_index = candidate_end_index
            range_kind = "stage_interval"
            if start_basis != "轴内首次可核实反馈":
                start_basis = "阶段启动"
    if (
        (start_index is None or end_index is None)
        and event_indexes
        and allow_observed_feedback_fallback
    ):
        start_index = min(event_indexes)
        end_index = max(event_indexes)
        source_start_date = dates[start_index]
        source_end_date = dates[end_index]

    if start_index is None or end_index is None:
        return [], events, []
    end_index = max(start_index, end_index)
    status_label = {
        "阶段主线已确认": "持续反馈",
        "阶段主线弱化": "反馈减弱",
        "阶段主线失效": "反馈结束",
        "阶段主线候选": "观察中",
    }.get(status, "有反馈记录")
    evidence_day_count = sum(
        start_index <= int(event["date_index"]) <= end_index for event in events
    )
    visible_span_trading_days = end_index - start_index + 1
    calendar_dates = [
        record_date
        for value in (
            record.get("trading_calendar")
            if isinstance(record.get("trading_calendar"), list)
            else []
        )
        if (record_date := _valid_iso_date(str(value or "")))
    ]
    source_span_trading_days = sum(
        source_start_date <= record_date <= source_end_date
        for record_date in calendar_dates
    )
    span_trading_days = source_span_trading_days or visible_span_trading_days
    interval_events = [
        event
        for event in events
        if start_index <= int(event["date_index"]) <= end_index
    ]
    basis_labels = [
        _SECTOR_FEEDBACK_EVENT_LABELS[kind]
        for kind in priority
        if any(kind in (event.get("kinds") or []) for event in interval_events)
    ]
    interval = {
        "start_index": start_index,
        "end_index": end_index,
        "start_date": dates[start_index],
        "end_date": dates[end_index],
        "source_start_date": source_start_date or dates[start_index],
        "source_end_date": source_end_date or dates[end_index],
        "start_basis": start_basis,
        "end_basis": end_basis,
        "range_kind": range_kind,
        "status": status_label,
        "is_ongoing": bool(
            end_index == len(dates) - 1
            and status not in {"阶段主线弱化", "阶段主线失效"}
        ),
        "span_trading_days": span_trading_days,
        "visible_span_trading_days": visible_span_trading_days,
        "evidence_day_count": evidence_day_count,
        "evidence_coverage": round(
            evidence_day_count / visible_span_trading_days,
            8,
        ),
        "basis_labels": basis_labels,
    }
    return [interval], events, basis_labels


def _sector_relative_path_swimlane(
    base_payload: Mapping[str, object],
    three_axis: Mapping[str, object] | None,
    *,
    trade_date: str,
    capital_events_by_sector: Mapping[str, object] | None = None,
) -> dict[str, object]:
    target_date = _valid_iso_date(str(trade_date or ""))
    if (
        not target_date
        or not isinstance(three_axis, Mapping)
        or not validate_sector_tournament_three_axis(three_axis, target_date=target_date)
    ):
        return dict(base_payload)

    stage = three_axis.get("stage_mainline")
    stage = stage if isinstance(stage, Mapping) else {}
    raw_records = stage.get("directions") if isinstance(stage.get("directions"), list) else []
    records = [item for item in raw_records if isinstance(item, Mapping)]
    records_by_sector = {
        str(item.get("direction") or "").strip(): item
        for item in records
        if str(item.get("direction") or "").strip()
    }
    evaluated_direction = str(
        stage.get("evaluated_direction") or three_axis.get("direction") or ""
    ).strip()
    evaluated_record = records_by_sector.get(evaluated_direction, {})
    window = (
        evaluated_record.get("relative_strength_window")
        if isinstance(evaluated_record.get("relative_strength_window"), Mapping)
        else {}
    )
    window_date_values = (
        window.get("trade_dates") if isinstance(window.get("trade_dates"), list) else []
    )
    comparison_dates = [
        record_date
        for value in window_date_values
        if (record_date := _valid_iso_date(str(value or ""))) and record_date <= target_date
    ]
    comparison_dates = list(dict.fromkeys(comparison_dates))
    base_date_values = (
        base_payload.get("dates") if isinstance(base_payload.get("dates"), list) else []
    )
    base_dates = [
        record_date
        for value in base_date_values
        if (record_date := _valid_iso_date(str(value or ""))) and record_date <= target_date
    ]
    stage_calendar_dates = sorted(
        {
            record_date
            for record in records
            for value in (
                record.get("trading_calendar")
                if isinstance(record.get("trading_calendar"), list)
                else []
            )
            if (record_date := _valid_iso_date(str(value or "")))
            and record_date <= target_date
        }
    )
    dates = (
        comparison_dates
        if len(comparison_dates) >= 2
        else sorted(set(stage_calendar_dates + base_dates))[-25:]
    )
    if not dates:
        return dict(base_payload)

    confirmed_values = (
        stage.get("confirmed_directions")
        if isinstance(stage.get("confirmed_directions"), list)
        else []
    )
    confirmed_directions = [
        str(value or "").strip()
        for value in confirmed_values
        if str(value or "").strip()
    ]
    candidate_values = (
        stage.get("candidate_directions")
        if isinstance(stage.get("candidate_directions"), list)
        else []
    )
    candidate_directions = [
        str(value or "").strip()
        for value in candidate_values
        if str(value or "").strip()
    ]
    daily_attack_line = str(stage.get("daily_attack_line") or "").strip()
    comparison_scope = (
        evaluated_record.get("comparison_universe_scope")
        if isinstance(evaluated_record.get("comparison_universe_scope"), Mapping)
        else {}
    )
    comparison_direction_values = (
        comparison_scope.get("directions")
        if isinstance(comparison_scope.get("directions"), list)
        else []
    )
    comparison_directions = [
        str(value or "").strip()
        for value in comparison_direction_values
        if str(value or "").strip()
    ]
    comparison_rows = (
        evaluated_record.get("comparison_universe")
        if isinstance(evaluated_record.get("comparison_universe"), list)
        else []
    )
    endpoint_metric_by_sector = {
        str(item.get("direction") or "").strip(): _chart_number_or_none(item.get("metric_value"))
        for item in comparison_rows
        if isinstance(item, Mapping) and str(item.get("direction") or "").strip()
    }

    base_lanes = base_payload.get("lanes") if isinstance(base_payload.get("lanes"), list) else []
    base_by_sector = {
        str(item.get("sector") or "").strip(): item
        for item in base_lanes
        if isinstance(item, Mapping) and str(item.get("sector") or "").strip()
    }
    sector_order = list(
        dict.fromkeys(
            [
                *confirmed_directions,
                evaluated_direction,
                daily_attack_line,
                *candidate_directions,
                *comparison_directions,
                *records_by_sector.keys(),
                *base_by_sector.keys(),
            ]
        )
    )
    sector_order = [sector for sector in sector_order if sector]
    space_axis = three_axis.get("space_axis")
    space_axis = space_axis if isinstance(space_axis, Mapping) else {}
    time_axis = three_axis.get("time_axis")
    time_axis = time_axis if isinstance(time_axis, Mapping) else {}
    cognition_axis = three_axis.get("cognition_axis")
    cognition_axis = cognition_axis if isinstance(cognition_axis, Mapping) else {}
    edge_source = three_axis.get("edge_source")
    edge_source = edge_source if isinstance(edge_source, Mapping) else {}
    space_stage = str(space_axis.get("stage") or "事实不足")
    edge_type = str(edge_source.get("type") or "暂无可确认优势")
    capital_events_by_sector = (
        capital_events_by_sector if isinstance(capital_events_by_sector, Mapping) else {}
    )

    lanes = []
    complete_path_count = 0
    any_path_point = False
    interval_lane_count = 0
    capital_event_count = 0
    capital_event_dates: set[str] = set()
    interval_start_dates: list[str] = []
    interval_end_dates: list[str] = []
    ascii_lines = [
        f"共同起点 | {dates[0]} = 100" if comparison_dates else "共同起点 | 相对价格路径未生成",
        "日期 | " + " ".join(record_date[5:] for record_date in dates),
    ]
    for lane_index, sector in enumerate(sector_order):
        record = records_by_sector.get(sector)
        base_lane = base_by_sector.get(sector)
        runs, observations = _sector_cycle_lane_on_dates(base_lane, dates, base_dates)
        record_window = (
            record.get("relative_strength_window")
            if isinstance(record, Mapping)
            and isinstance(record.get("relative_strength_window"), Mapping)
            else {}
        )
        record_date_values = (
            record_window.get("trade_dates")
            if isinstance(record_window.get("trade_dates"), list)
            else []
        )
        record_dates = [
            record_date
            for value in record_date_values
            if (record_date := _valid_iso_date(str(value or ""))) and record_date <= target_date
        ]
        same_window = bool(comparison_dates and record_dates == comparison_dates)
        raw_path = (
            record.get("sector_index_path")
            if isinstance(record, Mapping) and isinstance(record.get("sector_index_path"), list)
            else []
        )
        raw_by_date: dict[str, Mapping[str, object]] = {}
        if same_window:
            for point in raw_path:
                if not isinstance(point, Mapping):
                    continue
                point_date = _valid_iso_date(str(point.get("trade_date") or ""))
                source_date = _valid_iso_date(str(point.get("source_date") or ""))
                raw_value = _chart_number_or_none(point.get("index_value"))
                if (
                    point_date in dates
                    and source_date
                    and source_date <= target_date
                    and raw_value is not None
                    and raw_value > 0
                ):
                    raw_by_date[point_date] = point
        baseline_point = raw_by_date.get(dates[0]) if dates else None
        baseline = (
            _chart_number_or_none(baseline_point.get("index_value"))
            if isinstance(baseline_point, Mapping)
            else None
        )
        normalized_path = []
        for date_index, record_date in enumerate(dates):
            point = raw_by_date.get(record_date)
            raw_value = (
                _chart_number_or_none(point.get("index_value"))
                if isinstance(point, Mapping)
                else None
            )
            normalized_value = (
                round(raw_value / baseline * 100.0, 6)
                if raw_value is not None and baseline is not None and baseline > 0
                else None
            )
            if normalized_value is not None:
                any_path_point = True
            normalized_path.append(
                {
                    "date": record_date,
                    "date_index": date_index,
                    "raw_value": raw_value,
                    "normalized_value": normalized_value,
                    "relative_strength_rank": (
                        point.get("relative_strength_rank")
                        if isinstance(point, Mapping)
                        else None
                    ),
                    "source_date": (
                        str(point.get("source_date") or "")
                        if isinstance(point, Mapping)
                        else ""
                    ),
                }
            )
        path_complete = bool(
            same_window
            and len(dates) >= 2
            and all(item["normalized_value"] is not None for item in normalized_path)
        )
        if path_complete:
            complete_path_count += 1
        if not isinstance(record, Mapping):
            path_missing_reason = "没有同一比较窗口的板块指数路径"
        elif not same_window:
            path_missing_reason = "比较窗口不一致，不能强行归一"
        elif not path_complete:
            path_missing_reason = "逐日板块指数路径不完整，缺失日保留断点"
        else:
            path_missing_reason = ""

        roles = []
        if sector in confirmed_directions:
            roles.append("阶段主线")
        if sector == daily_attack_line:
            roles.append("当日主攻")
        if sector == evaluated_direction:
            roles.append("当前评估")
        role_text = "/".join(roles) or "观察方向"
        metric = (
            record.get("relative_strength_metric")
            if isinstance(record, Mapping)
            and isinstance(record.get("relative_strength_metric"), Mapping)
            else {}
        )
        metric_value = _chart_number_or_none(metric.get("value"))
        if metric_value is None:
            metric_value = endpoint_metric_by_sector.get(sector)
        color = (
            str(base_lane.get("color") or "")
            if isinstance(base_lane, Mapping)
            else ""
        ) or _CYCLE_SECTOR_COLOR_BY_NAME.get(sector) or (
            _SECTOR_CYCLE_FALLBACK_COLORS[lane_index % len(_SECTOR_CYCLE_FALLBACK_COLORS)]
        )
        interpretation = _sector_relative_path_interpretation(
            record,
            path_complete=path_complete,
        )
        price_absorption = _sector_relative_price_absorption(
            is_evaluated=sector == evaluated_direction,
            space_stage=space_stage,
            edge_type=edge_type,
        )
        raw_capital_events = capital_events_by_sector.get(sector)
        capital_events = (
            [item for item in raw_capital_events if isinstance(item, Mapping)]
            if isinstance(raw_capital_events, list)
            else []
        )
        activity_intervals, activity_events, activity_basis_labels = (
            _sector_feedback_timeline(
                record,
                dates=dates,
                normalized_path=normalized_path,
                runs=runs,
                observations=observations,
                capital_events=capital_events,
            )
        )
        if activity_intervals:
            interval_lane_count += 1
            interval_start_dates.extend(
                str(item.get("start_date") or "") for item in activity_intervals
            )
            interval_end_dates.extend(
                str(item.get("end_date") or "") for item in activity_intervals
            )
        for event in activity_events:
            if any(
                kind in {"capital_return", "main_fund_inflow", "institution_net_buy"}
                for kind in (event.get("kinds") or [])
            ):
                capital_event_count += 1
                event_date = _valid_iso_date(str(event.get("date") or ""))
                if event_date:
                    capital_event_dates.add(event_date)
        lanes.append(
            {
                "sector": sector,
                "color": color,
                "runs": runs,
                "observations": observations,
                "activity_intervals": activity_intervals,
                "activity_events": activity_events,
                "activity_basis_labels": activity_basis_labels,
                "normalized_path": normalized_path,
                "path_complete": path_complete,
                "path_missing_reason": path_missing_reason,
                "roles": roles,
                "stage_status": (
                    str(record.get("status") or "阶段结构未生成")
                    if isinstance(record, Mapping)
                    else "阶段结构未生成"
                ),
                "interpretation": interpretation,
                "price_absorption": price_absorption,
                "relative_strength_metric": metric_value,
                "relative_strength_rank": (
                    record.get("relative_strength_rank")
                    if isinstance(record, Mapping)
                    else None
                ),
                "comparison_coverage": (
                    record.get("comparison_coverage")
                    if isinstance(record, Mapping)
                    else None
                ),
                "divergence_test_status": (
                    str(record.get("divergence_test_status") or "分歧检验未生成")
                    if isinstance(record, Mapping)
                    else "分歧检验未生成"
                ),
                "trend_density": (
                    record.get("trend_density") if isinstance(record, Mapping) else None
                ),
                "missing_fields": (
                    list(record.get("missing_fields") or [])
                    if isinstance(record, Mapping)
                    else ["sector_index_path"]
                ),
            }
        )
        activity_cells = ["  " for _record_date in dates]
        for interval in activity_intervals:
            for cell_index in range(
                int(interval.get("start_index") or 0),
                int(interval.get("end_index") or 0) + 1,
            ):
                activity_cells[cell_index] = "=="
        event_symbols = {
            "institution_net_buy": "I ",
            "main_fund_inflow": "$ ",
            "capital_return": "$ ",
            "reflow": "R ",
            "rotation": "R ",
            "cross_day_feedback": "F ",
            "price_response": "P ",
            "turnover_participation": "T ",
        }
        for event in activity_events:
            event_index = int(event.get("date_index") or 0)
            kinds = event.get("kinds") if isinstance(event.get("kinds"), list) else []
            activity_cells[event_index] = (
                "* "
                if len(kinds) > 1
                else event_symbols.get(str(event.get("primary_kind") or ""), "? ")
            )
        interval_text = (
            f"{activity_intervals[0]['start_date']} -> {activity_intervals[0]['end_date']}"
            if activity_intervals
            else "暂无可核实区间"
        )
        ascii_lines.append(
            f"{sector} [{role_text}·{interpretation}] | "
            + " ".join(activity_cells)
            + f" | {interval_text}"
        )
        value_cells = [
            "--" if item["normalized_value"] is None else f'{item["normalized_value"]:.1f}'
            for item in normalized_path
        ]
        ascii_lines.append(
            f"{sector} 价格辅助 | " + " ".join(value_cells)
        )
    ascii_lines.append(
        "图例 | == 反馈区间  P 价格响应  F 跨日反馈  R 轮动/回流  "
        "$ 主力资金  I 机构净买  T 成交参与  * 同日多项证据"
    )
    ascii_lines.append("说明 | 价格辅助仍按同起点100展示；--为缺口，不补0")

    evaluated_lane = next(
        (lane for lane in lanes if lane.get("sector") == evaluated_direction),
        {},
    )
    if evaluated_lane.get("path_complete"):
        path_status = "完整"
        insufficient_reason = ""
    elif any_path_point:
        path_status = "部分"
        insufficient_reason = str(
            evaluated_lane.get("path_missing_reason") or "当前评估方向路径不完整"
        )
    else:
        path_status = "归一价格路径未生成"
        insufficient_reason = str(
            evaluated_lane.get("path_missing_reason") or "相对价格路径未生成"
        )
    return {
        "schema": "sector_relative_path_swimlane.v2",
        "dates": dates,
        "lanes": lanes,
        "ascii": "\n".join(ascii_lines),
        "title": "板块反馈区间泳道",
        "subtitle": "线段显示首次反馈至最近反馈或结束；段内区分价格响应、轮动、成交参与和可核实资金入场。",
        "comparison_start_date": comparison_dates[0] if comparison_dates else "",
        "comparison_end_date": comparison_dates[-1] if comparison_dates else "",
        "baseline_value": 100,
        "path_status": path_status,
        "insufficient_reason": insufficient_reason,
        "complete_path_count": complete_path_count,
        "interval_lane_count": interval_lane_count,
        "interval_start_date": min(interval_start_dates) if interval_start_dates else "",
        "interval_end_date": max(interval_end_dates) if interval_end_dates else "",
        "capital_event_count": capital_event_count,
        "capital_event_date_count": len(capital_event_dates),
        "activity_status": "有可核实区间" if interval_lane_count else "暂无可核实区间",
        "evaluated_direction": evaluated_direction,
        "stage_mainlines": confirmed_directions,
        "daily_attack_line": daily_attack_line,
        "space_stage": space_stage,
        "time_stage": str(time_axis.get("stage") or "事实不足"),
        "cognition_stage": str(cognition_axis.get("stage") or "事实不足"),
        "edge_type": edge_type,
        "story_price_relation": str(three_axis.get("story_price_relation") or "事实不足"),
        "source_artifact_hash": str(three_axis.get("artifact_hash") or ""),
    }


def _collect_sector_cycle_swimlane(
    lines: list[str],
    *,
    sector_tournament_three_axis: Mapping[str, object] | None = None,
    trade_date: str = "",
) -> dict[str, object]:
    observations_by_sector: dict[str, list[dict[str, object]]] = {}
    tracked_sector_order: list[str] = []
    colors_by_sector: dict[str, str] = {}
    direction_rows: list[dict[str, str]] = []
    capital_events_by_sector: dict[str, list[dict[str, object]]] = {}
    stock_sector_by_code: dict[str, str] = {}
    institution_rows_by_code: dict[str, dict[str, object]] = {}
    target_date = _valid_iso_date(trade_date)
    current_heading = ""
    current_sector = ""
    current_color = ""
    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        heading_match = re.match(r"^(#{1,6})\s+(.+?)\s*$", stripped)
        if heading_match:
            current_heading = heading_match.group(2).strip()
            if "近期热点板块成交额连续跟踪" in _plain_cell_text(current_heading):
                current_sector, current_color = _sector_name_and_color_from_heading(current_heading)
                if "连续跟踪" in current_sector:
                    current_sector = ""
                    current_color = ""
                if current_sector and current_sector not in tracked_sector_order:
                    tracked_sector_order.append(current_sector)
                if current_sector and current_color:
                    colors_by_sector[current_sector] = current_color
            else:
                current_sector = ""
                current_color = ""
            index += 1
            continue
        if not _is_table_start(lines, index):
            index += 1
            continue

        headers, rows, index = _collect_table(lines, index)
        heading_text = _plain_cell_text(current_heading)
        code_index = _header_index(headers, "代码")
        stock_index = _header_index(headers, "股票")
        stock_sector_index = _header_index(headers, "所属板块")
        if code_index >= 0 and stock_sector_index >= 0:
            for row in rows:
                stock_code = _plain_cell_text(_cell_at(row, code_index))
                stock_sector, _color = _sector_name_and_color_from_heading(
                    _cell_at(row, stock_sector_index)
                )
                if stock_code and stock_sector:
                    stock_sector_by_code[stock_code] = stock_sector

        institution_amount_index = _header_index(headers, "机构净买(亿)")
        if (
            "机构净买强榜" in heading_text
            and min(code_index, stock_index, institution_amount_index) >= 0
        ):
            for row in rows:
                stock_code = _plain_cell_text(_cell_at(row, code_index))
                stock_name = _plain_cell_text(_cell_at(row, stock_index))
                amount_yi = _numeric_amount_yi_cell(
                    _cell_at(row, institution_amount_index),
                    _cell_at(headers, institution_amount_index),
                )
                if not stock_code or not stock_name or amount_yi is None or amount_yi <= 0:
                    continue
                institution_rows_by_code[stock_code] = {
                    "amount_yi": amount_yi,
                    "stock_name": stock_name,
                }

        fund_sector_index = _header_index(headers, "板块")
        fund_amount_index = _header_index(headers, "净流入", "主力净流入")
        if (
            "资金流入" in heading_text
            and target_date
            and min(fund_sector_index, fund_amount_index) >= 0
        ):
            for row in rows:
                sector, _color = _sector_name_and_color_from_heading(
                    _cell_at(row, fund_sector_index)
                )
                amount_yi = _numeric_amount_yi_cell(
                    _cell_at(row, fund_amount_index),
                    _cell_at(headers, fund_amount_index),
                )
                if not sector or amount_yi is None or amount_yi <= 0:
                    continue
                event = {
                    "date": target_date,
                    "kind": "main_fund_inflow",
                    "amount_yi": amount_yi,
                    "detail": f"主力净流入 {amount_yi:+.2f}亿",
                }
                sector_events = capital_events_by_sector.setdefault(sector, [])
                if event not in sector_events:
                    sector_events.append(event)
            continue

        if "小周期成交额与主线切换判断" in heading_text:
            date_index = _header_index(headers, "日期")
            sector_index = _header_index(headers, "小周期方向")
            if min(date_index, sector_index) < 0:
                continue
            for row in rows:
                record_date = _valid_iso_date(_cell_at(row, date_index))
                raw_sector = _cell_at(row, sector_index)
                sector, color = _sector_name_and_color_from_heading(raw_sector)
                if not record_date:
                    continue
                direction_rows.append({"date": record_date, "sector": sector})
                if sector and color:
                    colors_by_sector[sector] = color
            continue
        if not current_sector:
            continue

        date_index = _header_index(headers, "日期")
        sector_turnover_index = _header_index(headers, "板块成交额")
        total_turnover_index = _header_index(headers, "两市成交额")
        share_index = _header_index(headers, "占比")
        change_index = _header_index(headers, "同板块变化", "占比变化")
        status_index = _header_index(headers, "样本状态")
        note_index = _header_index(headers, "解读")
        if min(date_index, sector_turnover_index, total_turnover_index, share_index) < 0:
            continue

        sector_observations = observations_by_sector.setdefault(current_sector, [])
        seen_dates = {str(item.get("date") or "") for item in sector_observations}
        for row in rows:
            record_date = _valid_iso_date(_cell_at(row, date_index))
            if not record_date or record_date in seen_dates:
                continue
            seen_dates.add(record_date)
            turnover_text = _plain_cell_text(_cell_at(row, sector_turnover_index))
            total_turnover_text = _plain_cell_text(_cell_at(row, total_turnover_index))
            share_text = _plain_cell_text(_cell_at(row, share_index))
            change_text = _plain_cell_text(_cell_at(row, change_index))
            sector_observations.append(
                {
                    "date": record_date,
                    "turnover": _numeric_amount_yi(turnover_text),
                    "turnover_text": turnover_text,
                    "total_turnover": _numeric_amount_yi(total_turnover_text),
                    "total_turnover_text": total_turnover_text,
                    "share_pct": _numeric_percent(share_text),
                    "share_text": share_text,
                    "change_pct": _numeric_pct_point(_cell_at(row, change_index)),
                    "change_text": change_text,
                    "status": _plain_cell_text(_cell_at(row, status_index)),
                    "note": _plain_cell_text(_cell_at(row, note_index)),
                }
            )

    institution_by_sector: dict[str, dict[str, object]] = {}
    for stock_code, institution_row in institution_rows_by_code.items():
        sector = stock_sector_by_code.get(stock_code, "")
        if not sector:
            continue
        grouped = institution_by_sector.setdefault(
            sector,
            {"amount_yi": 0.0, "stock_names": []},
        )
        grouped["amount_yi"] = round(
            float(grouped["amount_yi"]) + float(institution_row["amount_yi"]),
            6,
        )
        stock_name = str(institution_row.get("stock_name") or "").strip()
        stock_names = grouped["stock_names"]
        if stock_name and isinstance(stock_names, list) and stock_name not in stock_names:
            stock_names.append(stock_name)
    for sector, grouped in institution_by_sector.items() if target_date else []:
        amount_yi = float(grouped["amount_yi"])
        stock_names = grouped["stock_names"] if isinstance(grouped["stock_names"], list) else []
        detail = f"机构净买 {amount_yi:+.2f}亿"
        if stock_names:
            detail += "（" + "、".join(str(value) for value in stock_names) + "）"
        capital_events_by_sector.setdefault(sector, []).append(
            {
                "date": target_date,
                "kind": "institution_net_buy",
                "amount_yi": amount_yi,
                "stock_names": stock_names,
                "detail": detail,
            }
        )

    direction_by_date: dict[str, str] = {}
    for item in direction_rows:
        record_date = item.get("date") or ""
        sector = item.get("sector") or ""
        if record_date and (record_date not in direction_by_date or sector):
            direction_by_date[record_date] = sector
    dates = sorted(direction_by_date)[-25:]
    if not dates or not any(direction_by_date.get(record_date) for record_date in dates):
        return _sector_relative_path_swimlane(
            {},
            sector_tournament_three_axis,
            trade_date=trade_date,
            capital_events_by_sector=capital_events_by_sector,
        )

    recent_sectors: list[str] = []
    for record_date in reversed(dates):
        sector = direction_by_date[record_date]
        if sector and sector not in recent_sectors:
            recent_sectors.append(sector)
    lane_sectors = recent_sectors + [sector for sector in tracked_sector_order if sector not in recent_sectors]
    date_indexes = {record_date: item_index for item_index, record_date in enumerate(dates)}
    lanes: list[dict[str, object]] = []
    ascii_rows: list[tuple[str, list[str]]] = []
    for lane_index, sector in enumerate(lane_sectors):
        runs: list[dict[str, object]] = []
        run_start: int | None = None
        for date_index, record_date in enumerate(dates):
            is_active = direction_by_date.get(record_date) == sector
            if is_active and run_start is None:
                run_start = date_index
            if run_start is not None and (not is_active or date_index == len(dates) - 1):
                run_end = date_index if is_active else date_index - 1
                runs.append(
                    {
                        "start_index": run_start,
                        "end_index": run_end,
                        "start_date": dates[run_start],
                        "end_date": dates[run_end],
                    }
                )
                run_start = None

        lane_observations: list[dict[str, object]] = []
        for observation in observations_by_sector.get(sector, []):
            observation_date = str(observation.get("date") or "")
            if observation_date not in date_indexes:
                continue
            normalized = dict(observation)
            date_index = date_indexes[observation_date]
            is_direction = direction_by_date.get(observation_date) == sector
            share_available = observation.get("share_pct") is not None
            normalized["date_index"] = date_index
            normalized["kind"] = "combined" if is_direction and share_available else (
                "available" if share_available else "missing"
            )
            lane_observations.append(normalized)
        lane_observations.sort(key=lambda item: int(item.get("date_index") or 0))

        color = colors_by_sector.get(sector) or _CYCLE_SECTOR_COLOR_BY_NAME.get(sector) or (
            _SECTOR_CYCLE_FALLBACK_COLORS[lane_index % len(_SECTOR_CYCLE_FALLBACK_COLORS)]
        )
        cells = [" " for _date in dates]
        for run in runs:
            for cell_index in range(int(run["start_index"]), int(run["end_index"]) + 1):
                cells[cell_index] = "#"
        for observation in lane_observations:
            cell_index = int(observation["date_index"])
            if observation.get("share_pct") is not None:
                cells[cell_index] = "@" if cells[cell_index] == "#" else "o"
            else:
                cells[cell_index] = "?"
        ascii_rows.append((sector, cells))
        lanes.append(
            {
                "sector": sector,
                "color": color,
                "runs": runs,
                "observations": lane_observations,
            }
        )

    date_row = "日期 | " + " ".join(record_date[5:] for record_date in dates)
    ascii_lines = [date_row]
    for sector, cells in ascii_rows:
        ascii_lines.append(f"{sector} | " + "    ".join(cells))
    ascii_lines.append("图例 | # 当日小周期方向  o 占比可用  ? 占比暂缺  @ 方向与占比同时出现")
    base_payload = {
        "schema": "sector_cycle_swimlane.v1",
        "dates": dates,
        "lanes": lanes,
        "ascii": "\n".join(ascii_lines),
        "title": "25日板块周期泳道",
        "subtitle": "连续条记录小周期方向，节点记录逐板块成交占比。",
    }
    return _sector_relative_path_swimlane(
        base_payload,
        sector_tournament_three_axis,
        trade_date=trade_date,
        capital_events_by_sector=capital_events_by_sector,
    )


def _collect_turnover_top_items(lines: list[str], limit: int = 30) -> list[dict[str, object]]:
    current_heading = ""
    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        heading_match = re.match(r"^(#{1,6})\s+(.+?)\s*$", stripped)
        if heading_match:
            current_heading = _plain_cell_text(heading_match.group(2))
            index += 1
            continue
        if "成交核心结果" not in current_heading or not _is_table_start(lines, index):
            index += 1
            continue

        headers, rows, _next_index = _collect_table(lines, index)
        rank_index = _header_index(headers, "排名")
        name_index = _header_index(headers, "股票", "标的")
        code_index = _header_index(headers, "代码", "股票代码")
        turnover_index = _header_index(headers, "成交额")
        sector_index = _header_index(headers, "所属板块", "板块")
        change_index = _header_index(headers, "涨跌幅", "涨幅")
        candle_index = _header_index(headers, "蜡烛图形态")
        if min(rank_index, name_index, code_index, turnover_index, sector_index, change_index) < 0:
            return []

        items: list[dict[str, object]] = []
        for row in rows[:limit]:
            turnover = _numeric_amount_yi(_cell_at(row, turnover_index))
            if turnover is None:
                continue
            change_pct = _numeric_percent(_cell_at(row, change_index))
            rank_text = _plain_cell_text(_cell_at(row, rank_index))
            try:
                rank = int(rank_text)
            except ValueError:
                rank = len(items) + 1
            items.append(
                {
                    "rank": rank,
                    "name": _plain_cell_text(_cell_at(row, name_index)),
                    "code": _plain_cell_text(_cell_at(row, code_index)),
                    "turnover": turnover,
                    "sector": _plain_cell_text(_cell_at(row, sector_index)),
                    "change_pct": change_pct,
                    "status": _limit_status_from_turnover_row(
                        change_pct,
                        _cell_at(row, candle_index),
                        stock_code=_plain_cell_text(_cell_at(row, code_index)),
                        stock_name=_plain_cell_text(_cell_at(row, name_index)),
                    ),
                }
            )
        return items
    return []


def _normalize_turnover_rank_items(
    rows: Iterable[Mapping[str, object]], trade_date: str, *, limit: int = 30,
) -> list[dict[str, object]]:
    """Read dated turnover facts; `turnover` is already expressed in 亿元.

    Keep this independent of the Markdown core table, which only lists >100亿.
    Missing dates/amounts are not inferred and missing returns remain unknown.
    """
    try:
        target_date = date.fromisoformat(trade_date).isoformat()
    except ValueError:
        return []
    by_code: dict[str, dict[str, object]] = {}
    for row in rows:
        if not isinstance(row, Mapping) or row.get("trade_date") != target_date:
            continue
        code = str(row.get("code") or "").strip()
        name = str(row.get("name") or "").strip()
        turnover = _chart_number_or_none(row.get("turnover"))
        if not code or not name or turnover is None or turnover <= 0 or code in by_code:
            continue
        by_code[code] = {
            "code": code,
            "name": name,
            "turnover": turnover,
            "change_pct": _chart_number_or_none(row.get("change_pct")),
            "sector": str(row.get("sector") or "待确认板块"),
            "trade_date": target_date,
            "status": "",
        }
    items = sorted(by_code.values(), key=lambda item: (-float(item["turnover"]), str(item["code"])))[:limit]
    for rank, item in enumerate(items, 1):
        item["rank"] = rank
    return items


def _collect_turnover_sector_share_items(turnover_items: list[dict[str, object]]) -> list[dict[str, object]]:
    total_turnover = sum(float(item.get("turnover") or 0) for item in turnover_items)
    if total_turnover <= 0:
        return []

    grouped: dict[str, dict[str, object]] = {}
    for item in turnover_items:
        sector = str(item.get("sector") or "待确认板块").strip() or "待确认板块"
        turnover = float(item.get("turnover") or 0)
        bucket = grouped.setdefault(
            sector,
            {
                "sector": sector,
                "turnover": 0.0,
                "count": 0,
                "leaders": [],
                "positive_count": 0,
                "negative_count": 0,
            },
        )
        bucket["turnover"] = float(bucket["turnover"]) + turnover
        bucket["count"] = int(bucket["count"]) + 1
        leaders = bucket["leaders"] if isinstance(bucket["leaders"], list) else []
        if len(leaders) < 3:
            leaders.append(
                {
                    "name": item.get("name") or "",
                    "code": item.get("code") or "",
                    "turnover": turnover,
                    "change_pct": item.get("change_pct"),
                    "status": item.get("status") or "",
                }
            )
        change_pct = item.get("change_pct")
        if isinstance(change_pct, (int, float)):
            if change_pct >= 0:
                bucket["positive_count"] = int(bucket["positive_count"]) + 1
            else:
                bucket["negative_count"] = int(bucket["negative_count"]) + 1

    items: list[dict[str, object]] = []
    for sector, bucket in grouped.items():
        turnover = float(bucket["turnover"])
        items.append(
            {
                **bucket,
                "share_pct": round(turnover / total_turnover * 100, 1),
                "color": _cycle_sector_color_for_name(sector, ""),
            }
        )
    return sorted(items, key=lambda item: float(item.get("turnover") or 0), reverse=True)


def _numeric_count(value: str) -> float | None:
    text = _plain_cell_text(value)
    match = re.search(r"(-?\d+(?:\.\d+)?)", text)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _collect_board_tag_rank_items(lines: list[str]) -> list[dict[str, object]]:
    current_heading = ""
    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        heading_match = re.match(r"^(#{1,6})\s+(.+?)\s*$", stripped)
        if heading_match:
            current_heading = _plain_cell_text(heading_match.group(2))
            index += 1
            continue
        if not _is_table_start(lines, index):
            index += 1
            continue

        headers, rows, _next_index = _collect_table(lines, index)
        if not _is_board_tag_rank_table_headers(headers) or not _is_board_tag_rank_table_context(
            current_heading, lines, index
        ):
            index = _next_index
            continue

        rank_index = _header_index(headers, "排名")
        tag_index = _header_index(headers, "标签")
        count_index = _header_index(headers, "出现次数")
        share_index = _header_index(headers, "全标签占比", "面积占比")
        if min(tag_index, count_index, share_index) < 0:
            return []

        items: list[dict[str, object]] = []
        for row_index, row in enumerate(rows):
            tag = _plain_cell_text(_cell_at(row, tag_index))
            count = _numeric_count(_cell_at(row, count_index))
            share_pct = _numeric_percent(_cell_at(row, share_index))
            if not tag or count is None or count <= 0 or share_pct is None:
                continue
            rank_text = _plain_cell_text(_cell_at(row, rank_index))
            try:
                rank = int(rank_text)
            except ValueError:
                rank = row_index + 1
            items.append({"rank": rank, "tag": tag, "count": count, "share_pct": share_pct})
        return sorted(items, key=lambda item: float(item.get("share_pct") or 0), reverse=True)
    return []


def _collect_market_turnover_top50_items(lines: list[str], limit: int = 25) -> list[dict[str, object]]:
    index = 0
    while index < len(lines):
        if not _table_has_headers(lines, index, "日期", "Top50占比", "Top50成交额", "两市成交额"):
            index += 1
            continue

        headers, rows, _next_index = _collect_table(lines, index)
        date_index = _header_index(headers, "日期")
        share_index = _header_index(headers, "Top50占比")
        state_index = _header_index(headers, "状态")
        change_index = _header_index(headers, "较前日")
        top50_turnover_index = _header_index(headers, "Top50成交额")
        total_turnover_index = _header_index(headers, "两市成交额")
        items: list[dict[str, object]] = []
        for row in rows[:limit]:
            total_turnover = _numeric_amount_yi(_cell_at(row, total_turnover_index))
            share_pct = _numeric_percent(_cell_at(row, share_index))
            top50_turnover = _numeric_amount_yi(_cell_at(row, top50_turnover_index))
            if total_turnover is None or share_pct is None:
                continue
            items.append(
                {
                    "date": _plain_cell_text(_cell_at(row, date_index)),
                    "top50_share_pct": share_pct,
                    "state": _plain_cell_text(_cell_at(row, state_index)),
                    "change_pct_point": _numeric_pct_point(_cell_at(row, change_index)),
                    "top50_turnover": top50_turnover,
                    "total_turnover": total_turnover,
                }
            )
        return list(reversed(items))
    return []


def _collect_new_high_share_items(lines: list[str], limit: int = 25) -> list[dict[str, object]]:
    index = 0
    while index < len(lines):
        if not _table_has_headers(lines, index, "日期", "新高数", "全A占比"):
            index += 1
            continue

        headers, rows, _next_index = _collect_table(lines, index)
        date_index = _header_index(headers, "日期")
        count_index = _header_index(headers, "新高数")
        share_index = _header_index(headers, "全A占比")
        signal_index = _header_index(headers, "趋势信号")
        items: list[dict[str, object]] = []
        for row in rows[:limit]:
            date = _plain_cell_text(_cell_at(row, date_index))
            count = _numeric_count(_cell_at(row, count_index))
            share_pct = _numeric_percent(_cell_at(row, share_index))
            if date and share_pct is not None:
                items.append(
                    {
                        "date": date,
                        "new_high_count": int(count) if count is not None else None,
                        "new_high_share_pct": share_pct,
                        "breadth_level_label": _plain_cell_text(_cell_at(row, signal_index)),
                    }
                )
        return list(reversed(items))
    return []


_LHB_SIDE_HEADINGS = ("净买入结果", "净流出结果", "净卖出结果")


def _is_lhb_side_heading(heading: str, side: str) -> bool:
    text = _plain_cell_text(heading)
    if side == "buy":
        return "净买入结果" in text
    return "净流出结果" in text or "净卖出结果" in text


def _frozen_limit_codes(value: object) -> set[str] | None:
    """Normalize one frozen code list; ``None`` marks a structurally invalid payload."""
    if not isinstance(value, (list, tuple, set, frozenset)):
        return None
    codes: set[str] = set()
    for entry in value:
        if isinstance(entry, bool) or not isinstance(entry, (str, int)):
            return None
        code = str(entry).strip().split(".")[0].strip()
        if not code:
            return None
        codes.add(code)
    return codes


def _frozen_lhb_limit_status(
    trade_date: str,
    lhb_limit_status: Mapping[str, object] | None,
) -> dict[str, str]:
    """Resolve 涨停/跌停 identity from the frozen target-day identity sets only.

    A missing payload, an unexpected structure, or a payload for another trade
    date yields an empty mapping: callers then leave everything uncolored instead
    of falling back to report text, change percentages, or candle shapes.
    """
    if not isinstance(lhb_limit_status, Mapping):
        return {}
    target_date = _valid_iso_date(trade_date)
    if not target_date:
        return {}
    if _plain_cell_text(lhb_limit_status.get("trade_date")) != target_date:
        return {}
    up_codes = _frozen_limit_codes(lhb_limit_status.get("limit_up_codes"))
    down_codes = _frozen_limit_codes(lhb_limit_status.get("limit_down_codes"))
    if up_codes is None or down_codes is None:
        return {}
    frozen_status = {code: "涨停" for code in up_codes - down_codes}
    frozen_status.update({code: "跌停" for code in down_codes - up_codes})
    return frozen_status


def _collect_lhb_flow_items(
    lines: list[str],
    limit_per_side: int = 10,
    *,
    trade_date: str = "",
    lhb_frozen_limits: Mapping[str, str] | None = None,
) -> list[dict[str, object]]:
    target_date = _valid_iso_date(trade_date)
    frozen_status = dict(lhb_frozen_limits or {})
    current_heading = ""
    heading_dates: dict[int, str] = {}
    items: list[dict[str, object]] = []
    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        heading_match = re.match(r"^(#{1,6})\s+(.+?)\s*$", stripped)
        if heading_match:
            current_heading = heading_match.group(2)
            level = len(heading_match.group(1))
            heading_dates = {key: value for key, value in heading_dates.items() if key < level}
            heading_date = re.search(r"\b\d{4}-\d{2}-\d{2}\b", current_heading)
            if heading_date:
                heading_dates[level] = heading_date.group()
            index += 1
            continue
        if not _is_table_start(lines, index):
            index += 1
            continue

        side = ""
        if _is_lhb_side_heading(current_heading, "buy"):
            side = "buy"
        elif _is_lhb_side_heading(current_heading, "sell"):
            side = "sell"
        if not side:
            index += 1
            continue

        headers, rows, index = _collect_table(lines, index)
        amount_index = _header_index(headers, "净买入(亿)" if side == "buy" else "净流出(亿)", "净买入", "净流出", "净卖出")
        rank_index = _header_index(headers, "排名")
        name_index = _header_index(headers, "股票", "标的")
        code_index = _header_index(headers, "代码", "股票代码")
        sector_index = _header_index(headers, "所属板块", "板块")
        change_index = _header_index(headers, "涨跌幅", "涨幅")
        date_index = _header_index(headers, "交易日期", "交易日", "日期")
        if min(amount_index, name_index, sector_index) < 0:
            continue

        for row in rows[:limit_per_side]:
            amount = _numeric_amount_yi(_cell_at(row, amount_index))
            if amount is None:
                continue
            if amount == 0:
                continue
            signed_amount = abs(amount) if side == "buy" else -abs(amount)
            change_pct = _numeric_percent(_cell_at(row, change_index))
            code = _plain_cell_text(_cell_at(row, code_index))
            row_date = _plain_cell_text(_cell_at(row, date_index))
            dates = [*heading_dates.values(), *([row_date] if row_date else [])]
            matches_target = bool(target_date) and all(value == target_date for value in dates)
            limit_status = frozen_status.get(code.split(".")[0].strip(), "") if matches_target else ""
            status = limit_status
            rank_text = _plain_cell_text(_cell_at(row, rank_index))
            try:
                rank = int(rank_text)
            except ValueError:
                rank = len([item for item in items if item.get("side") == side]) + 1
            items.append(
                {
                    "rank": rank,
                    "name": _plain_cell_text(_cell_at(row, name_index)),
                    "code": code,
                    "sector": _plain_cell_text(_cell_at(row, sector_index)),
                    "amount": signed_amount,
                    "abs_amount": abs(amount),
                    "change_pct": change_pct,
                    "status": status,
                    "limit_status": limit_status,
                    "side": side,
                }
            )
        continue

    return sorted(items, key=lambda item: float(item.get("amount") or 0), reverse=True)


def _intraday_feedback_number(value: str) -> float | None:
    text = _plain_cell_text(value)
    if not text or text in {"-", "待确认", "数据暂缺"}:
        return None
    parsed = _numeric_pct_point(text) if "pct" in text.lower() else _numeric_percent(text)
    if parsed is not None:
        return parsed
    if re.fullmatch(r"[+-]?\d+(?:\.\d+)?", text):
        try:
            return float(text)
        except ValueError:
            return None
    return None


def _normalize_intraday_time(value: str) -> str:
    text = _plain_cell_text(value)
    match = re.search(r"(\d{1,2}):(\d{2})(?::\d{2})?", text)
    if not match:
        return text
    return f"{int(match.group(1)):02d}:{match.group(2)}"


def _is_intraday_index_identity(name: str, role: str) -> bool:
    text = f"{name} {role}"
    return "指数" in text or name in {"上证", "沪指", "上证综指"}


def _intraday_feedback_series_key(name: str, code: str, role: str) -> str:
    if _is_intraday_index_identity(name, role):
        return name or code
    return code or name


def _is_intraday_feedback_point_table(headers: list[str]) -> bool:
    return (
        _header_index(headers, "时间", "时刻") >= 0
        and _header_index(headers, "对象", "标的", "名称") >= 0
        and _header_index(headers, "代码", "股票代码", "证券代码") >= 0
        and _header_index(headers, "角色") >= 0
        and _header_index(headers, "涨跌幅", "涨幅", "分时涨跌幅") >= 0
        and _header_index(headers, "相对上证", "相对沪指", "相对指数") >= 0
    )


def _is_intraday_feedback_event_table(headers: list[str]) -> bool:
    return (
        _header_index(headers, "时间", "时刻") >= 0
        and _header_index(headers, "对象", "标的", "名称") >= 0
        and _header_index(headers, "事件", "触发", "标注") >= 0
    )


def _collect_intraday_feedback_point_items(headers: list[str], rows: list[list[str]]) -> list[dict[str, object]]:
    time_index = _header_index(headers, "时间", "时刻")
    name_index = _header_index(headers, "对象", "标的", "名称")
    code_index = _header_index(headers, "代码", "股票代码", "证券代码")
    role_index = _header_index(headers, "角色")
    change_index = _header_index(headers, "涨跌幅", "涨幅", "分时涨跌幅")
    relative_index = _header_index(headers, "相对上证", "相对沪指", "相对指数")
    items: list[dict[str, object]] = []
    for row in rows:
        time_text = _normalize_intraday_time(_cell_at(row, time_index))
        name = _plain_cell_text(_cell_at(row, name_index))
        code = _plain_cell_text(_cell_at(row, code_index))
        role = _plain_cell_text(_cell_at(row, role_index)) or "观察对象"
        change_pct = _intraday_feedback_number(_cell_at(row, change_index))
        if not time_text or not name or change_pct is None:
            continue
        relative_pct = _intraday_feedback_number(_cell_at(row, relative_index))
        if relative_pct is None and _is_intraday_index_identity(name, role):
            relative_pct = 0.0
        items.append(
            {
                "time": time_text,
                "name": name,
                "code": code,
                "role": role,
                "series_key": _intraday_feedback_series_key(name, code, role),
                "change_pct": change_pct,
                "relative_pct": relative_pct,
            }
        )
    return items


def _dedupe_intraday_feedback_items(items: list[dict[str, object]]) -> list[dict[str, object]]:
    roles_by_key: dict[str, list[str]] = {}
    for item in items:
        key = str(item.get("series_key") or item.get("code") or item.get("name") or "")
        role = str(item.get("role") or "").strip()
        if not key or not role:
            continue
        roles = roles_by_key.setdefault(key, [])
        if role not in roles:
            roles.append(role)

    deduped: list[dict[str, object]] = []
    seen_points: set[tuple[str, str]] = set()
    for item in items:
        key = str(item.get("series_key") or item.get("code") or item.get("name") or "")
        time_text = str(item.get("time") or "")
        point_key = (key, time_text)
        if not key or not time_text or point_key in seen_points:
            continue
        seen_points.add(point_key)
        normalized = dict(item)
        roles = roles_by_key.get(key) or []
        if roles:
            normalized["role"] = " / ".join(roles)
        deduped.append(normalized)
    return deduped


def _collect_intraday_feedback_event_items(headers: list[str], rows: list[list[str]]) -> list[dict[str, object]]:
    time_index = _header_index(headers, "时间", "时刻")
    name_index = _header_index(headers, "对象", "标的", "名称")
    code_index = _header_index(headers, "代码", "股票代码", "证券代码")
    event_index = _header_index(headers, "事件", "触发", "标注")
    price_index = _header_index(headers, "价格", "价位")
    note_index = _header_index(headers, "说明", "备注")
    events: list[dict[str, object]] = []
    for row in rows:
        time_text = _normalize_intraday_time(_cell_at(row, time_index))
        name = _plain_cell_text(_cell_at(row, name_index))
        code = _plain_cell_text(_cell_at(row, code_index))
        event = _plain_cell_text(_cell_at(row, event_index))
        if not time_text or not event:
            continue
        events.append(
            {
                "time": time_text,
                "name": name,
                "code": code,
                "series_key": _intraday_feedback_series_key(name, code, ""),
                "event": event,
                "price": _plain_cell_text(_cell_at(row, price_index)),
                "note": _plain_cell_text(_cell_at(row, note_index)),
            }
        )
    return events


def _collect_intraday_feedback_account_conclusion(lines: list[str]) -> str:
    for line in lines:
        text = _plain_cell_text(line).strip()
        text = re.sub(r"^[>\-\*\s]+", "", text)
        match = re.search(r"账户(?:复盘)?结论\s*[:：]\s*(.+)$", text)
        if match:
            return match.group(1).strip()
    return ""


def _collect_intraday_feedback_review(lines: list[str]) -> dict[str, object]:
    items: list[dict[str, object]] = []
    events: list[dict[str, object]] = []
    index = 0
    while index < len(lines):
        if not _is_table_start(lines, index):
            index += 1
            continue

        headers, rows, index = _collect_table(lines, index)
        if _is_intraday_feedback_point_table(headers):
            items.extend(_collect_intraday_feedback_point_items(headers, rows))
            continue
        if _is_intraday_feedback_event_table(headers):
            events.extend(_collect_intraday_feedback_event_items(headers, rows))
            continue

    items = _dedupe_intraday_feedback_items(items)
    if not items:
        return {}
    return {
        "items": items,
        "events": events,
        "account_conclusion": _collect_intraday_feedback_account_conclusion(lines),
    }


def _chinext_close_by_date(
    value: Mapping[str, object] | None,
    trade_date: str,
) -> dict[str, float]:
    if not isinstance(value, Mapping) or not isinstance(value.get("items"), list):
        return {}
    target_date = _valid_iso_date(str(trade_date or ""))
    close_by_date: dict[str, float] = {}
    for item in value["items"]:
        if not isinstance(item, Mapping):
            continue
        item_date = _valid_iso_date(str(item.get("date") or item.get("trade_date") or ""))
        close = _chart_number_or_none(item.get("close"))
        if not item_date or (target_date and item_date > target_date) or close is None or close <= 0:
            continue
        close_by_date[item_date] = close
    return close_by_date


def _collect_bear_chart_payload(
    markdown_text: str,
    trade_date: str,
    *,
    chinext_index_trend: Mapping[str, object] | None = None,
    sector_tournament_three_axis: Mapping[str, object] | None = None,
    turnover_rank: Iterable[Mapping[str, object]] | None = None,
    lhb_frozen_limits: Mapping[str, str] | None = None,
) -> dict[str, object]:
    lines = markdown_text.splitlines()
    sector_cycle_swimlane = _collect_sector_cycle_swimlane(
        lines,
        sector_tournament_three_axis=sector_tournament_three_axis,
        trade_date=trade_date,
    )
    market_turnover_items = _collect_market_turnover_top50_items(lines)
    new_high_share_items = _collect_new_high_share_items(lines)
    turnover_items = (
        _normalize_turnover_rank_items(turnover_rank, trade_date)
        if turnover_rank is not None
        else _collect_turnover_top_items(lines, limit=30)
    )
    turnover_source = (
        f"{trade_date} 成交额全量榜，按金额降序取前30；单位：亿元"
        if turnover_rank is not None
        else "仅正文成交核心样本；未提供目标日完整成交榜，不代表全市场前30"
    )
    if len(turnover_items) < 30:
        turnover_source += f"；可核实 {len(turnover_items)} 条，不补齐缺失记录"
    turnover_sector_items = _collect_turnover_sector_share_items(turnover_items)
    board_tag_items = _collect_board_tag_rank_items(lines)
    lhb_items = _collect_lhb_flow_items(lines, trade_date=trade_date, lhb_frozen_limits=lhb_frozen_limits)
    intraday_feedback_review = _collect_intraday_feedback_review(lines)
    payload: dict[str, object] = {}
    if intraday_feedback_review:
        payload["intraday_feedback_review"] = {
            **intraday_feedback_review,
            "title": "盘面反馈复盘",
            "subtitle": "同屏比较上证、旧仓和目标对象的分时强弱",
        }
    if market_turnover_items:
        chinext_by_date = _chinext_close_by_date(chinext_index_trend, trade_date)
        aligned_chinext_count = 0
        if chinext_by_date:
            for item in market_turnover_items:
                close = chinext_by_date.get(str(item.get("date") or ""))
                item["chinext_close"] = close
                if close is not None:
                    aligned_chinext_count += 1
        payload["market_turnover_top50_trend"] = {
            "items": market_turnover_items,
            "title": "两市成交额与Top50占比",
            "subtitle": "柱看两市成交额，线看头部成交集中度",
        }
        if aligned_chinext_count:
            payload["market_turnover_top50_trend"]["chinext_available_count"] = aligned_chinext_count
    if new_high_share_items:
        payload["new_high_share_trend"] = {
            "items": new_high_share_items,
            "title": "创新高全A占比",
            "subtitle": "5%及以上为极致扩散，2%到5%为有效扩散，1%到2%为扩散偏冷，0.2%到1%为极低扩散；低于0.2%或个位数为扩散断层。",
            "thresholds": build_new_high_breadth_thresholds(),
        }
    if sector_cycle_swimlane:
        payload["sector_cycle_swimlane"] = sector_cycle_swimlane
    if turnover_items:
        if turnover_sector_items:
            payload["turnover_sector_share"] = {
                "items": turnover_sector_items,
                "title": "成交额Top30板块占比",
                "subtitle": turnover_source,
            }
        payload["turnover_top30"] = {
            "items": turnover_items,
            "title": "成交额Top30",
            "subtitle": turnover_source,
            "trade_date": trade_date,
            "unit": "亿元",
            "source": "turnover_rank" if turnover_rank is not None else "markdown_core_table",
            "complete": turnover_rank is not None and len(turnover_items) == 30,
        }
    if board_tag_items:
        payload["board_tag_rank_bar"] = {
            "items": board_tag_items,
            "title": "标签热度排行榜",
            "subtitle": "按热榜标签出现次数排序",
        }
    if lhb_items:
        payload["lhb_net_flow"] = {
            "items": lhb_items,
            "title": "龙虎榜净额表态",
            "subtitle": "正轴为净买入，负轴为净流出；柱色只按净额方向（正红负绿），收盘涨停与跌停身份只在表格和提示里标出，不按涨跌幅推断",
            "trade_date": trade_date,
        }
    return payload


def _chart_number_or_none(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _normalize_t0_market_breadth_payload(
    value: Mapping[str, object] | None,
    trade_date: str,
    *,
    limit: int = 25,
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        return {}
    raw_items = value.get("items")
    if not isinstance(raw_items, list):
        return {}
    target_date = str(trade_date or "").strip()[:10]
    items_by_date: dict[str, dict[str, object]] = {}
    for raw_item in raw_items:
        if not isinstance(raw_item, Mapping):
            continue
        item_date = str(raw_item.get("date") or raw_item.get("trade_date") or "").strip()[:10]
        try:
            parsed_date = date.fromisoformat(item_date)
        except ValueError:
            continue
        if target_date and item_date > target_date:
            continue
        up_count = _chart_number_or_none(raw_item.get("up_count"))
        down_count = _chart_number_or_none(raw_item.get("down_count"))
        items_by_date[parsed_date.isoformat()] = {
            "date": parsed_date.isoformat(),
            "up_count": int(up_count) if up_count is not None and up_count >= 0 else None,
            "down_count": int(down_count) if down_count is not None and down_count >= 0 else None,
            "all_a_change_pct": _chart_number_or_none(raw_item.get("all_a_change_pct")),
            "new_high_share_pct": _chart_number_or_none(raw_item.get("new_high_share_pct")),
        }
    items = [items_by_date[item_date] for item_date in sorted(items_by_date)][-max(int(limit or 25), 1) :]
    if not items:
        return {}
    return {
        "schema": "t0_market_breadth.v1",
        "items": items,
        "title": str(value.get("title") or "T0市场底色"),
        "subtitle": str(
            value.get("subtitle")
            or "上涨和下跌家数看市场宽度，双线看全A涨跌幅与创新高扩散。"
        ),
    }


def _normalize_cffex_position_trend_payload(
    value: Mapping[str, object] | None,
    trade_date: str,
    *,
    limit: int = 60,
) -> dict[str, object]:
    # Historical callers still import this name; current chart projection lives
    # with the CFFEX facts so this compatibility facade does not pull the old
    # report renderer into the current reading path.
    from report.cffex_index_futures_position_evidence import normalize_cffex_position_trend_payload

    return normalize_cffex_position_trend_payload(value, trade_date, limit=limit)


def _bear_chart_card_html(
    chart_id: str,
    *,
    eyebrow: str,
    title: str,
    subtitle: str,
    footnote: str,
    item_count: int,
    tall: bool = False,
    window_sizes: Iterable[int] = (),
    default_window_size: int | None = None,
) -> str:
    if item_count <= 0:
        return ""
    tall_class = " is-tall" if tall else ""
    chart_style = f' style="height:{item_count * 36 + 42}px;min-height:0"' if chart_id == "turnover_top30" else ""
    normalized_window_sizes = list(
        dict.fromkeys(
            size
            for raw_size in window_sizes
            if (size := int(raw_size)) > 0
        )
    )
    window_control = ""
    if len(normalized_window_sizes) > 1:
        buttons = []
        for index, size in enumerate(normalized_window_sizes):
            pressed = str(size == default_window_size if default_window_size is not None else index == 0).lower()
            buttons.append(
                f'<button type="button" data-window-size="{size}" '
                f'aria-pressed="{pressed}">{size}日</button>'
            )
        window_control = (
            '<div class="bear-chart-toolbar">'
            f'<div class="bear-chart-window-control" data-bear-chart-window-control="{_html(chart_id)}" '
            f'role="group" aria-label="{_html(title)}时间范围">'
            + "".join(buttons)
            + "</div></div>"
        )
    return (
        f'<section class="bear-chart-card" data-bear-chart-card="{_html(chart_id)}">'
        '<div class="bear-chart-copy">'
        f'<span class="bear-chart-eyebrow">{_html(eyebrow)}</span>'
        f"<h4>{_html(title)}</h4>"
        f"<p>{_html(subtitle)}</p>"
        "</div>"
        f"{window_control}"
        f'<div class="bear-chart-frame{tall_class}">'
        f'<div class="bear-chart" data-bear-chart="{_html(chart_id)}"{chart_style} role="img" aria-label="{_html(title)}"></div>'
        "</div>"
        f'<p class="bear-chart-footnote">{_html(footnote)} · 当前样本 {item_count} 条</p>'
        "</section>"
    )


def _bear_sector_cycle_swimlane_html(payload: Mapping[str, object]) -> str:
    dates = payload.get("dates") if isinstance(payload.get("dates"), list) else []
    lanes = payload.get("lanes") if isinstance(payload.get("lanes"), list) else []
    if not dates or not lanes:
        return ""
    is_relative_path = payload.get("schema") == "sector_relative_path_swimlane.v2"
    lane_count = len(lanes)
    chart_height = max(340, lane_count * (74 if is_relative_path else 46) + 82)
    track_width = max(760, len(dates) * 58)
    lane_label_parts = []
    for lane in lanes:
        if not isinstance(lane, Mapping):
            continue
        sector = str(lane.get("sector") or "未命名板块")
        color = str(lane.get("color") or "#6B7280")
        if is_relative_path:
            roles = lane.get("roles") if isinstance(lane.get("roles"), list) else []
            role_text = " / ".join(str(item) for item in roles if str(item).strip()) or "观察方向"
            intervals = (
                lane.get("activity_intervals")
                if isinstance(lane.get("activity_intervals"), list)
                else []
            )
            interval = next(
                (item for item in intervals if isinstance(item, Mapping)),
                {},
            )
            start_date = str(
                interval.get("source_start_date") or interval.get("start_date") or ""
            )
            end_date = str(
                interval.get("source_end_date") or interval.get("end_date") or ""
            )
            interval_text = (
                f"{start_date} → {end_date}"
                if start_date and end_date
                else "暂无可核实区间"
            )
            span_days = int(_chart_number_or_none(interval.get("span_trading_days")) or 0)
            span_text = f"{span_days}个交易日" if span_days else "持续日待确认"
            interval_status = str(interval.get("status") or "暂无可核实反馈")
            basis_values = (
                interval.get("basis_labels")
                if isinstance(interval.get("basis_labels"), list)
                else []
            )
            basis_set = {str(item) for item in basis_values if str(item).strip()}
            basis_groups = []
            if basis_set & {"机构净买", "主力净流入", "资金回流"}:
                basis_groups.append("主力/机构资金")
            if basis_set & {"轮动", "冷却后回流"}:
                basis_groups.append("轮动/回流")
            if basis_set & {"价格响应", "跨日反馈"}:
                basis_groups.append("价格/跨日响应")
            if "成交参与" in basis_set:
                basis_groups.append("成交参与")
            basis_text = " / ".join(basis_groups) or "证据类型待确认"
            lane_label_parts.append(
                '<span class="sector-cycle-lane-label is-relative-path">'
                f'<i style="--sector-cycle-color:{_html(color)}"></i>'
                '<span class="sector-cycle-lane-copy">'
                f'<strong>{_html(sector)}</strong>'
                f'<small>{_html(interval_text)} · {_html(span_text)}</small>'
                f'<small>{_html(role_text)} · {_html(interval_status)}</small>'
                f'<small>证据：{_html(basis_text)}</small>'
                '</span></span>'
            )
        else:
            lane_label_parts.append(
                '<span class="sector-cycle-lane-label">'
                f'<i style="--sector-cycle-color:{_html(color)}"></i>'
                f'{_html(sector)}</span>'
            )
    lane_labels = "".join(lane_label_parts)
    ascii_text = str(payload.get("ascii") or "")
    title = str(payload.get("title") or "25日板块周期泳道")
    subtitle = str(payload.get("subtitle") or "连续条记录小周期方向，节点记录逐板块成交占比。")
    if is_relative_path:
        start_date = str(payload.get("interval_start_date") or "")
        end_date = str(payload.get("interval_end_date") or "")
        interval_text = (
            f"{start_date} → {end_date}"
            if start_date and end_date
            else "暂无可核实区间"
        )
        interval_count = int(
            _chart_number_or_none(payload.get("interval_lane_count")) or 0
        )
        capital_date_count = int(
            _chart_number_or_none(payload.get("capital_event_date_count")) or 0
        )
        stage_mainlines = payload.get("stage_mainlines") if isinstance(payload.get("stage_mainlines"), list) else []
        stage_text = "、".join(str(item) for item in stage_mainlines if str(item).strip()) or "阶段方向未形成"
        daily_attack = str(payload.get("daily_attack_line") or "当日主攻方向未形成")
        path_status = str(payload.get("path_status") or "归一价格路径未生成")
        if path_status == "事实不足":
            path_status = "归一价格路径未生成"
        context_html = (
            '<div class="sector-cycle-context" aria-label="板块反馈区间摘要">'
            f'<span><b>反馈总区间</b>{_html(interval_text)}</span>'
            f'<span><b>有反馈板块</b>{interval_count}/{lane_count}个</span>'
            f'<span><b>资金参与日期</b>{capital_date_count}个交易日</span>'
            f'<span><b>阶段 / 当日</b>{_html(stage_text)} / {_html(daily_attack)}</span>'
            '</div>'
            + (
                '<p class="sector-cycle-insufficient">暂无可核实的板块反馈起止区间。</p>'
                if not interval_count
                else ""
            )
        )
        legend_html = (
            '<span><i class="is-feedback-range"></i>反馈起止区间</span>'
            '<span><i class="is-response"></i>价格/跨日反馈</span>'
            '<span><i class="is-rotation"></i>轮动/回流</span>'
            '<span><i class="is-fund"></i>主力资金</span>'
            '<span><i class="is-institution"></i>机构净买</span>'
            '<span><i class="is-turnover"></i>成交参与</span>'
            '<span><i class="is-path"></i>归一价格辅助线</span>'
        )
        label_width = 244
        aria_title = "板块反馈区间泳道图"
        footnote = (
            f"横轴共 {len(dates)} 个交易日；线段表示开始至结束的交易日区间，节点表示逐日证据；"
            f"归一价格路径仅作辅助（{path_status}），缺失不补0"
        )
    else:
        context_html = ""
        legend_html = (
            '<span><i class="is-run"></i>小周期方向</span>'
            '<span><i class="is-combined"></i>方向与占比同时出现</span>'
            '<span><i class="is-available"></i>占比可用</span>'
            '<span><i class="is-missing"></i>占比暂缺</span>'
        )
        label_width = 148
        aria_title = "最近25个交易日板块周期泳道图"
        footnote = f"横轴共 {len(dates)} 个交易日，缺失占比不按 0 处理"
    card_class = " is-relative-path" if is_relative_path else ""
    return (
        f'<section class="bear-chart-card sector-cycle-card{card_class}" '
        'data-bear-chart-card="sector_cycle_swimlane" data-sector-cycle-card '
        f'style="--sector-cycle-label-width:{label_width}px">'
        '<div class="bear-chart-copy">'
        f'<span class="bear-chart-eyebrow">{"反馈区间" if is_relative_path else "周期轮动"}</span>'
        f'<h4>{_html(title)}</h4>'
        f'<p>{_html(subtitle)}</p>'
        '</div>'
        f'{context_html}'
        '<div class="sector-cycle-legend" aria-label="泳道图图例">'
        f'{legend_html}'
        '</div>'
        f'<div class="sector-cycle-shell" style="--sector-cycle-height:{chart_height}px">'
        f'<div class="sector-cycle-lane-labels" aria-hidden="true">{lane_labels}</div>'
        f'<div class="sector-cycle-track-scroll" role="region" aria-label="{_html(aria_title)}横向时间轴" tabindex="0">'
        f'<div class="bear-chart sector-cycle-chart" data-bear-chart="sector_cycle_swimlane" '
        f'style="width:{track_width}px;height:{chart_height}px" role="img" '
        f'aria-label="{_html(aria_title)}"></div>'
        '</div></div>'
        '<div class="sector-cycle-ascii" data-sector-cycle-ascii role="region" '
        f'aria-label="{_html(title)}文本泳道" tabindex="0">'
        '<strong>文本泳道</strong>'
        f'<pre>{_html(ascii_text)}</pre></div>'
        '<div class="sector-cycle-scroll-controls" data-sector-cycle-scroll-controls>'
        '<button type="button" data-sector-cycle-scroll-backward aria-label="时间轴向左滚动" disabled>'
        '<span aria-hidden="true">&#8592;</span></button>'
        '<input type="range" min="0" max="0" value="0" step="1" '
        f'data-sector-cycle-scroll-range aria-label="横向浏览{_html(title)}时间轴" disabled>'
        '<button type="button" data-sector-cycle-scroll-forward aria-label="时间轴向右滚动" disabled>'
        '<span aria-hidden="true">&#8594;</span></button>'
        '</div>'
        f'<p class="bear-chart-footnote">{_html(footnote)}</p>'
        '</section>'
    )


def _sector_cycle_raw_records_open_html() -> str:
    return (
        '<details class="sector-cycle-raw-records" data-sector-cycle-raw-records>'
        '<summary><span>原始记录</span><small>逐板块明细与25日记录</small></summary>'
        '<div class="sector-cycle-raw-records-body">'
    )


_SECTOR_CYCLE_RAW_RECORDS_CLOSE_HTML = "</div></details>"


def _bear_appendix_section_open_html(
    heading_markdown: str,
    heading_title: str,
    anchor: str,
    stock_refs: tuple[str, ...],
) -> str:
    return (
        '<details class="bear-appendix-section" data-bear-appendix-section>'
        f'<summary id="{_html(anchor)}" data-bear-appendix-summary>'
        '<span class="bear-appendix-section-title">'
        f'{_heading_inline(heading_markdown, stock_refs, section_title=heading_title)}'
        '</span></summary>'
        '<div class="bear-appendix-section-body">'
    )


_BEAR_APPENDIX_SECTION_CLOSE_HTML = "</div></details>"


def _is_primary_sector_cycle_heading(title: str) -> bool:
    return (
        re.fullmatch(
            r"(?:\d+[.、]\s*)?主线成交额占比趋势(?:（近期热点板块连续跟踪）)?",
            _plain_cell_text(title),
        )
        is not None
    )


def _markdown_has_primary_sector_cycle_heading(lines: list[str]) -> bool:
    in_fenced_code = False
    for line in lines:
        if _is_fenced_code_start(line):
            in_fenced_code = not in_fenced_code
            continue
        if in_fenced_code:
            continue
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line.strip())
        if match and _is_primary_sector_cycle_heading(_strip_inline_markdown(match.group(2))):
            return True
    return False


_MARKET_STRUCTURE_CHART_RE = re.compile(r'^::market-structure-chart\{(?P<attrs>.*)\}$')
_DIRECTIVE_ATTR_RE = re.compile(r'([A-Za-z_][A-Za-z0-9_-]*)="([^"]*)"')


def _parse_directive_attrs(attr_text: str) -> dict[str, str]:
    return {match.group(1): match.group(2) for match in _DIRECTIVE_ATTR_RE.finditer(str(attr_text or ""))}


def _resolve_local_report_asset(src: str, output_path: str | Path | None) -> Path | None:
    value = str(src or "").strip()
    if not value or value.startswith("//") or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", value):
        return None
    base_dir = Path(output_path).resolve().parent if output_path is not None else _repo_root() / "reports"
    candidate = (base_dir / value).resolve()
    try:
        candidate.relative_to(base_dir.resolve())
    except ValueError:
        return None
    return candidate


def _load_market_structure_chart_data(src: str, output_path: str | Path | None) -> dict[str, object]:
    path = _resolve_local_report_asset(src, output_path)
    if path is None or not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    match = re.search(
        r'<script[^>]*\bid=["\']chanlun-chart-data["\'][^>]*>(.*?)</script>',
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return {}
    try:
        payload = json.loads(unescape(match.group(1)))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _market_structure_summary_text(chart_data: dict[str, object]) -> str:
    current = chart_data.get("currentSegment") if isinstance(chart_data.get("currentSegment"), dict) else {}
    latest_date = str(chart_data.get("latestDate") or "").strip()
    latest_price = chart_data.get("latestPrice")
    parts = []
    if latest_date:
        parts.append(f"最新K线 {latest_date}")
    try:
        parts.append(f"收盘 {float(latest_price):.2f}")
    except (TypeError, ValueError):
        pass
    if current:
        start = str(current.get("startDate") or "").strip()
        end = str(current.get("endDate") or "").strip()
        if start or end:
            parts.append(f"当前中枢 {start}~{end}".strip("~"))
        try:
            parts.append(f"ZD {float(current.get('zd')):.2f} / ZG {float(current.get('zg')):.2f}")
        except (TypeError, ValueError):
            pass
    return "；".join(parts)


def _render_market_structure_chart(line: str, output_path: str | Path | None) -> str:
    match = _MARKET_STRUCTURE_CHART_RE.match(line.strip())
    if not match:
        return ""
    attrs = _parse_directive_attrs(match.group("attrs"))
    title = attrs.get("title") or "上证指数日线中枢"
    chart_data = _load_market_structure_chart_data(attrs.get("src", ""), output_path)
    if not chart_data:
        return (
            '<section class="market-structure-chart-card is-missing">'
            '<div class="market-structure-chart-copy">'
            '<span class="market-structure-chart-eyebrow">指数结构</span>'
            f"<h4>{_html(title)}</h4>"
            "<p>上证结构图数据未生成，停止展示图表。</p>"
            "</div>"
            "</section>"
        )
    summary = _market_structure_summary_text(chart_data)
    summary_html = f"<p>{_html(summary)}</p>" if summary else ""
    return (
        '<section class="market-structure-chart-card" data-market-structure-card="true">'
        '<div class="market-structure-chart-copy">'
        '<span class="market-structure-chart-eyebrow">指数结构</span>'
        f"<h4>{_html(title)}</h4>"
        f"{summary_html}"
        "</div>"
        '<div class="market-structure-chart-frame">'
        f'<div class="market-structure-chart" data-market-structure-chart role="img" aria-label="{_html(title)}"></div>'
        "</div>"
        '<script type="application/json" class="market-structure-chart-data">'
        f"{_json_for_html_script(chart_data)}"
        "</script>"
        "</section>"
    )


def _is_turnover_change_context(header: str, label: str) -> bool:
    header_text = _table_header_text(header)
    label_text = _table_header_text(label)
    return (
        "成交额" in label_text
        and header_text in {"涨跌幅", "变化", "环比", "较昨日", "较前日", "涨跌"}
    )


def _is_etf_turnover_amount_context(header: str, label: str) -> bool:
    header_text = _table_header_text(header)
    label_text = _table_header_text(label)
    return header_text == "ETF两市成交额" or (
        label_text == "ETF两市成交额" and header_text in {"数值", "金额", "成交额", "当前值"}
    )


def _is_index_change_context(headers: list[str], header: str, label: str) -> bool:
    header_text = _table_header_text(header)
    label_text = _table_header_text(label)
    header_set = {_table_header_text(item) for item in headers}
    known_index_labels = {
        "上证指数",
        "深证成指",
        "创业板指",
        "科创50",
        "北证50",
        "中证全指",
        "中证1000",
        "沪深300",
        "中证500",
        "上证50",
    }
    return (
        header_text in {"涨跌幅", "涨跌", "变化", "日涨跌幅"}
        and ("指数" in header_set or label_text in known_index_labels or label_text.endswith("指数"))
    )


def _is_heat_core_section(section_title: str) -> bool:
    return "热度核心结果" in section_title


def _is_lhb_section(section_title: str) -> bool:
    text = _plain_cell_text(section_title)
    return "龙虎榜结果" in text or any(side in text for side in _LHB_SIDE_HEADINGS)


def _heat_core_status_signal(value: str) -> str:
    text = _table_header_text(value)
    if not text or text in {"-", "无", "正常"}:
        return ""
    if re.search(r"(未|非|不|没有|并非).{0,3}涨停", text):
        return ""
    if re.search(r"(未|非|不|没有|并非).{0,3}跌停", text):
        return ""
    if text in {"跌停", "跌停封死"} or re.search(r"(^|[、,，/；;])跌停($|[、,，/；;])", text):
        return "signal-cold"
    if text in {"涨停", "首板涨停"} or re.search(r"(^|[、,，/；;])涨停($|[、,，/；;])", text):
        return "signal-hot"
    if re.fullmatch(r"\d+(天)?\d*板", text) or re.fullmatch(r"\d+连板", text):
        return "signal-hot"
    return ""


def _row_explicit_limit_status_signal(headers: list[str], row: list[str], change_pct: float | None = None) -> str:
    for header_index, header_value in enumerate(headers):
        if header_index >= len(row):
            continue
        header_text = _table_header_text(header_value)
        if header_text not in {"连板标签", "涨停标签", "涨停状态", "状态"}:
            continue
        text = _table_header_text(row[header_index])
        if "涨停" not in text and "跌停" not in text:
            continue
        signal = _heat_core_status_signal(text)
        if signal == "signal-hot" and change_pct is not None and change_pct < 9.8:
            continue
        if signal == "signal-cold" and change_pct is not None and change_pct > -9.8:
            continue
        if signal:
            return signal
    return ""


def _heat_core_limit_signal(
    headers: list[str],
    row: list[str],
    cell_index: int,
    section_title: str,
    limit_pools: LimitPools,
) -> str:
    if not _is_heat_core_section(section_title):
        return ""
    header = headers[cell_index] if cell_index < len(headers) else ""
    if _table_header_text(header) not in {"涨跌幅", "涨幅"}:
        return ""
    code = _stock_code_from_row(headers, row)
    if code in limit_pools.up:
        return "signal-hot"
    if code in limit_pools.down:
        return "signal-cold"
    change_pct = _numeric_percent(row[cell_index]) if cell_index < len(row) else None
    row_signal = _row_explicit_limit_status_signal(headers, row, change_pct)
    if row_signal:
        return row_signal
    return ""


def _lhb_row_code(headers: list[str], row: list[str]) -> str:
    code_index = _header_index(headers, "代码", "股票代码", "证券代码")
    candidates = [_cell_at(row, code_index)] if code_index >= 0 else []
    candidates.extend(row)
    for candidate in candidates:
        code = _plain_cell_text(candidate).split(".")[0].strip()
        if re.fullmatch(r"\d{6}", code):
            return code
    return ""


def _frozen_limit_row_signal(
    headers: list[str],
    row: list[str],
    frozen_limits: Mapping[str, str],
) -> str:
    status = frozen_limits.get(_lhb_row_code(headers, row), "")
    if status == "涨停":
        return "signal-hot"
    if status == "跌停":
        return "signal-cold"
    return ""


def _lhb_limit_signal(
    headers: list[str],
    row: list[str],
    cell_index: int,
    section_title: str,
    frozen_limits: Mapping[str, str],
) -> str:
    if not _is_lhb_section(section_title):
        return ""
    header = headers[cell_index] if cell_index < len(headers) else ""
    if _table_header_text(header) not in {"涨跌幅", "涨幅"}:
        return ""
    return _frozen_limit_row_signal(headers, row, frozen_limits)


def _signal_class(
    headers: list[str],
    row: list[str],
    cell_index: int,
    *,
    section_title: str = "",
    limit_pools: LimitPools | None = None,
    lhb_frozen_limits: Mapping[str, str] | None = None,
) -> str:
    limit_pools = limit_pools or LimitPools(up=frozenset(), down=frozenset())
    lhb_frozen_limits = lhb_frozen_limits or {}
    limit_signal = _heat_core_limit_signal(headers, row, cell_index, section_title, limit_pools)
    if limit_signal:
        return limit_signal

    lhb_signal = _lhb_limit_signal(headers, row, cell_index, section_title, lhb_frozen_limits)
    if lhb_signal:
        return lhb_signal

    header = headers[cell_index] if cell_index < len(headers) else ""
    label = row[0] if row else ""
    text = row[cell_index] if cell_index < len(row) else ""
    context = f"{header} {label}"

    if "Top50" in context and "占比" in context:
        pct = _numeric_percent(text)
        if pct is not None and pct > 25:
            return "signal-extreme"
        if pct is not None and pct > 20:
            return "signal-hot"
        if pct is not None and pct < 18:
            return "signal-cold"

    if "全A占比" in context:
        pct = _numeric_percent(text)
        if pct is not None and pct > 5:
            return "signal-hot"
        if pct is not None and pct < 2:
            return "signal-cold"

    if "当日差值" in context or "价格带" in context:
        pct_point = _numeric_pct_point(text)
        if pct_point is not None and pct_point > 2:
            return "signal-hot"
        if pct_point is not None and pct_point < -2:
            return "signal-cold"

    if _is_etf_turnover_amount_context(header, label):
        amount = _numeric_amount_yi(text)
        if amount is not None and amount > 5500:
            return "signal-hot"
        if amount is not None and amount < 4500:
            return "signal-cold"

    if _is_turnover_change_context(header, label) or _is_index_change_context(headers, header, label):
        pct = _numeric_percent(text)
        if pct is not None and pct > 0:
            return "signal-hot"
        if pct is not None and pct < 0:
            return "signal-cold"

    if "上涨家数" in context:
        count = _numeric_int(text)
        if count is not None and count > 4000:
            return "signal-hot"

    if "下跌家数" in context:
        count = _numeric_int(text)
        if count is not None and count > 4000:
            return "signal-cold"

    if ("涨跌比" in label or "涨跌家数" in label) and cell_index > 0:
        pair = re.search(r"(\d{2,5})\s*/\s*(\d{2,5})", text)
        if pair:
            up_count = int(pair.group(1))
            down_count = int(pair.group(2))
            if up_count > 4000:
                return "signal-hot"
            if down_count > 4000:
                return "signal-cold"

    return ""


def _render_table(
    lines: list[str],
    index: int,
    stock_refs: tuple[str, ...],
    *,
    section_title: str = "",
    limit_pools: LimitPools | None = None,
    lhb_frozen_limits: Mapping[str, str] | None = None,
    hide_board_tag_heatbar: bool = False,
) -> tuple[str, int]:
    headers = _split_table_row(lines[index])
    index += 2
    rows: list[list[str]] = []
    while index < len(lines) and lines[index].lstrip().startswith("|"):
        if not _is_table_separator(lines[index]):
            rows.append(_split_table_row(lines[index]))
        index += 1

    if _is_candidate_lifecycle_table(section_title, headers):
        return _render_candidate_lifecycle_table(headers, rows, stock_refs), index

    if _is_position_day_order_table(headers, rows):
        return _render_position_day_order_table(headers, rows, stock_refs), index

    if _is_position_timeline_table(headers, rows):
        return _render_position_timeline_table(headers, rows, stock_refs), index

    hidden_columns: set[int] = set()
    if hide_board_tag_heatbar and _is_board_tag_rank_table_headers(headers):
        hidden_columns = {
            index for index, header in enumerate(headers) if _table_header_text(header) == "热度条"
        }
    visible_headers = [(index, header) for index, header in enumerate(headers) if index not in hidden_columns]
    header_html = "".join(f"<th>{_inline(header, stock_refs)}</th>" for _index, header in visible_headers)
    is_cycle_calendar = _is_cycle_calendar_section(section_title)
    is_cycle_sector_surface = _is_cycle_sector_surface(section_title)
    body_rows = []
    for row in rows:
        padded = row + [""] * max(0, len(headers) - len(row))
        cells = []
        for cell_index, cell in ((index, padded[index]) for index, _header in visible_headers):
            class_name = _signal_class(
                headers,
                padded,
                cell_index,
                section_title=section_title,
                limit_pools=limit_pools,
                lhb_frozen_limits=lhb_frozen_limits,
            )
            cell_html = _table_cell_inline(
                headers,
                padded,
                cell_index,
                stock_refs,
                section_title=section_title,
                in_cycle_sector_surface=is_cycle_sector_surface,
            )
            if class_name:
                cells.append(f'<td class="has-signal"><span class="signal-marker {class_name}">{cell_html}</span></td>')
            else:
                cells.append(f"<td>{cell_html}</td>")
        body_rows.append("<tr>" + "".join(cells) + "</tr>")
    body = "\n".join(body_rows) or f'<tr><td colspan="{len(visible_headers)}">暂无数据</td></tr>'
    legend_html = _cycle_calendar_legend_html(rows) if is_cycle_calendar else ""
    return (
        legend_html
        + '<div class="reader-table"><table><thead><tr>'
        + header_html
        + "</tr></thead><tbody>"
        + body
        + "</tbody></table></div>",
        index,
    )


def _collect_paragraph(lines: list[str], index: int) -> tuple[str, int]:
    paragraph = []
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped:
            break
        if (
            stripped.startswith("#")
            or stripped.startswith("<!--")
            or stripped.startswith(">")
            or stripped.startswith("- ")
            or stripped == "---"
            or _MARKET_STRUCTURE_CHART_RE.match(stripped)
            or _is_fenced_code_start(stripped)
            or _is_table_start(lines, index)
        ):
            break
        paragraph.append(stripped)
        index += 1
    return " ".join(paragraph), index


def _skip_html_comment(lines: list[str], index: int) -> int:
    while index < len(lines):
        if "-->" in lines[index]:
            return index + 1
        index += 1
    return index


def _collect_prefixed(lines: list[str], index: int, prefix: str) -> tuple[list[str], int]:
    items = []
    while index < len(lines) and lines[index].strip().startswith(prefix):
        items.append(lines[index].strip()[len(prefix) :].strip())
        index += 1
    return items, index


def _render_nav(headings: Iterable[Heading], *, mobile: bool = False) -> str:
    items = []
    appendix_items = []
    for index, heading in enumerate(headings):
        if heading.level > 3:
            continue
        active_class = " is-active" if index == 0 and not mobile else ""
        class_name = f' class="level-{heading.level}{active_class}"'
        current_attr = ' aria-current="true"' if active_class else ""
        link = (
            f'<a{class_name}{current_attr} href="#{_html(heading.anchor)}" data-outline-anchor="{_html(heading.anchor)}">'
            f"{_html(heading.title)}</a>"
        )
        if mobile and heading.is_detailed_appendix:
            appendix_items.append(link)
        else:
            items.append(link)
    if mobile and appendix_items:
        items.append(
            '<details class="mobile-nav-appendix">'
            '<summary><span>详细附录</span>'
            f'<small>{len(appendix_items)}项</small></summary>'
            '<div class="mobile-nav-appendix-links">'
            + "\n".join(appendix_items)
            + "</div></details>"
        )
    if not items:
        return ""
    nav_class = "mobile-nav" if mobile else "outline-nav"
    return f'<nav class="{nav_class}" aria-label="当前日报标题导航">' + "\n".join(items) + "</nav>"


def render_markdown_report_html(
    markdown_text: str,
    *,
    title: str = "A股日报",
    trade_date: str = "",
    source_label: str = "Markdown日报",
    output_path: str | Path | None = None,
    tomorrow_action_calendar: Mapping[str, object] | None = None,
    t0_market_breadth: Mapping[str, object] | None = None,
    chinext_index_trend: Mapping[str, object] | None = None,
    sector_tournament_three_axis: Mapping[str, object] | None = None,
    cffex_index_futures_position_evidence: Mapping[str, object] | None = None,
    turnover_rank: Iterable[Mapping[str, object]] | None = None,
    lhb_limit_status: Mapping[str, object] | None = None,
) -> str:
    markdown_text = _sanitize_reader_markdown_text(markdown_text)
    lines = markdown_text.splitlines()
    has_primary_sector_cycle_heading = _markdown_has_primary_sector_cycle_heading(lines)
    stock_refs = _collect_stock_refs(markdown_text)
    limit_pools = _collect_limit_pools(markdown_text)
    lhb_frozen_limits = _frozen_lhb_limit_status(trade_date, lhb_limit_status)
    bear_chart_payload = _collect_bear_chart_payload(
        markdown_text,
        trade_date,
        chinext_index_trend=chinext_index_trend,
        sector_tournament_three_axis=sector_tournament_three_axis,
        turnover_rank=turnover_rank,
        lhb_frozen_limits=lhb_frozen_limits,
    )
    normalized_market_breadth = _normalize_t0_market_breadth_payload(t0_market_breadth, trade_date)
    if normalized_market_breadth:
        bear_chart_payload["t0_market_breadth"] = normalized_market_breadth
    normalized_cffex_position_trend = _normalize_cffex_position_trend_payload(
        cffex_index_futures_position_evidence,
        trade_date,
    )
    if normalized_cffex_position_trend:
        bear_chart_payload["cffex_position_trend"] = normalized_cffex_position_trend
    used_anchors: dict[str, int] = {}
    headings: list[Heading] = []
    calendar_html = _render_tomorrow_action_calendar(tomorrow_action_calendar)
    fragments: list[str] = [calendar_html] if calendar_html else []
    inserted_charts: set[str] = set()
    has_mermaid_diagram = False
    index = 0
    current_h2_title = ""
    current_section_title = ""
    sector_cycle_raw_records_open = False
    sector_cycle_raw_records_close_level = 0
    in_detailed_appendix = False
    appendix_section_open = False

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped:
            index += 1
            continue

        if stripped.startswith("<!--"):
            index = _skip_html_comment(lines, index)
            continue

        market_structure_chart = _render_market_structure_chart(stripped, output_path)
        if market_structure_chart:
            fragments.append(market_structure_chart)
            index += 1
            continue

        heading_match = re.match(r"^(#{1,6})\s+(.+?)\s*$", stripped)
        if heading_match:
            level = len(heading_match.group(1))
            heading_title = _strip_inline_markdown(heading_match.group(2))
            plain_heading_title = _plain_cell_text(heading_title)
            if sector_cycle_raw_records_open and level <= sector_cycle_raw_records_close_level:
                fragments.append(_SECTOR_CYCLE_RAW_RECORDS_CLOSE_HTML)
                sector_cycle_raw_records_open = False
                sector_cycle_raw_records_close_level = 0
            if appendix_section_open and level <= 3:
                fragments.append(_BEAR_APPENDIX_SECTION_CLOSE_HTML)
                appendix_section_open = False
            if _is_stale_price_band_heading(lines, index, heading_title, level, trade_date):
                index = _skip_section(lines, index, level)
                continue
            if _is_judgment_review_internal_heading(current_h2_title, heading_title, level):
                fragments.append(f"<p><strong>{_inline(heading_match.group(2), stock_refs)}</strong></p>")
                index += 1
                continue
            if level <= 2:
                in_detailed_appendix = level == 2 and plain_heading_title == "八、详细附录"
            anchor = _heading_anchor(heading_title, used_anchors)
            heading_class = _heading_class(level, heading_title)
            class_attr = f' class="{heading_class}"' if heading_class else ""
            headings.append(
                Heading(
                    level=level,
                    title=heading_title,
                    anchor=anchor,
                    is_detailed_appendix=in_detailed_appendix and level == 3,
                )
            )
            if in_detailed_appendix and level == 3:
                fragments.append(
                    _bear_appendix_section_open_html(
                        heading_match.group(2),
                        heading_title,
                        anchor,
                        stock_refs,
                    )
                )
                appendix_section_open = True
            else:
                fragments.append(
                    f'<h{level}{class_attr} id="{_html(anchor)}">'
                    f'{_heading_inline(heading_match.group(2), stock_refs, section_title=heading_title)}</h{level}>'
                )
            market_breadth_chart = bear_chart_payload.get("t0_market_breadth")
            if (
                re.fullmatch(r"(?:\d+[.、]\s*)?指数与市场底色", heading_title)
                and isinstance(market_breadth_chart, dict)
                and "t0_market_breadth" not in inserted_charts
            ):
                items = (
                    market_breadth_chart.get("items")
                    if isinstance(market_breadth_chart.get("items"), list)
                    else []
                )
                fragments.append(
                    _bear_chart_card_html(
                        "t0_market_breadth",
                        eyebrow="市场宽度",
                        title="T0市场底色",
                        subtitle=str(
                            market_breadth_chart.get("subtitle")
                            or "上涨和下跌家数看市场宽度，双线看全A涨跌幅与创新高扩散。"
                        ),
                        footnote="图表来自截至报告日的历史市场事实",
                        item_count=len(items),
                    )
                )
                inserted_charts.add("t0_market_breadth")
            cffex_position_chart = bear_chart_payload.get("cffex_position_trend")
            if (
                plain_heading_title == "股指期货持仓结构（研究证据）"
                and isinstance(cffex_position_chart, dict)
                and "cffex_position_trend" not in inserted_charts
            ):
                items = (
                    cffex_position_chart.get("items")
                    if isinstance(cffex_position_chart.get("items"), list)
                    else []
                )
                fragments.append(
                    _bear_chart_card_html(
                        "cffex_position_trend",
                        eyebrow="衍生品结构",
                        title=str(
                            cffex_position_chart.get("title")
                            or "股指期货净空结构趋势"
                        ),
                        subtitle=str(cffex_position_chart.get("subtitle") or ""),
                        footnote=(
                            "默认显示最近60个交易日，可切换20日；不足60日按已有样本展示；"
                            "缺失值不补0，目标日精确值与名义金额复核见下表"
                        ),
                        item_count=len(items),
                        tall=True,
                        window_sizes=(20, 60),
                        default_window_size=60,
                    )
                )
                inserted_charts.add("cffex_position_trend")
            sector_cycle_chart = bear_chart_payload.get("sector_cycle_swimlane")
            is_primary_sector_cycle_heading = _is_primary_sector_cycle_heading(heading_title)
            is_sector_cycle_appendix_heading = (
                plain_heading_title == "附录：近期热点板块成交额连续跟踪"
            )
            if (
                (is_primary_sector_cycle_heading or is_sector_cycle_appendix_heading)
                and isinstance(sector_cycle_chart, dict)
            ):
                should_insert_sector_cycle_chart = (
                    "sector_cycle_swimlane" not in inserted_charts
                    and (
                        is_primary_sector_cycle_heading
                        or (
                            is_sector_cycle_appendix_heading
                            and not has_primary_sector_cycle_heading
                        )
                    )
                )
                if should_insert_sector_cycle_chart:
                    fragments.append(_bear_sector_cycle_swimlane_html(sector_cycle_chart))
                    inserted_charts.add("sector_cycle_swimlane")
                fragments.append(_sector_cycle_raw_records_open_html())
                sector_cycle_raw_records_open = True
                sector_cycle_raw_records_close_level = 3 if is_primary_sector_cycle_heading else 4
            lhb_chart = bear_chart_payload.get("lhb_net_flow")
            if (
                "龙虎榜结果" in heading_title
                and isinstance(lhb_chart, dict)
                and "lhb_net_flow" not in inserted_charts
            ):
                items = lhb_chart.get("items") if isinstance(lhb_chart.get("items"), list) else []
                fragments.append(
                    _bear_chart_card_html(
                        "lhb_net_flow",
                        eyebrow="资金表态",
                        title="龙虎榜净额表态",
                        subtitle=str(lhb_chart["subtitle"]),
                        footnote="净额来自龙虎榜结果表；涨跌停以目标日收盘身份为准，未确认不作标色",
                        item_count=len(items),
                        tall=True,
                    )
                )
                inserted_charts.add("lhb_net_flow")
            if level == 2:
                current_h2_title = heading_title
            current_section_title = heading_title
            board_tag_chart = bear_chart_payload.get("board_tag_rank_bar")
            if (
                any(marker in heading_title for marker in ("标签热度排行榜", "标签面积占比图"))
                and isinstance(board_tag_chart, dict)
                and "board_tag_rank_bar" not in inserted_charts
            ):
                items = board_tag_chart.get("items") if isinstance(board_tag_chart.get("items"), list) else []
                fragments.append(
                    _bear_chart_card_html(
                        "board_tag_rank_bar",
                        eyebrow="标签排行",
                        title="板块标签热度排行榜",
                        subtitle="按出现次数横向比较，直接看热榜标签前排强弱。",
                        footnote="图表来自下方标签热度排行榜",
                        item_count=len(items),
                        tall=True,
                    )
                )
                inserted_charts.add("board_tag_rank_bar")
            index += 1
            continue

        if _is_table_start(lines, index):
            is_sector_cycle_direction_table = (
                sector_cycle_raw_records_open
                and _table_has_headers(lines, index, "日期", "小周期方向", "主线成交额")
            )
            intraday_feedback_chart = bear_chart_payload.get("intraday_feedback_review")
            if (
                isinstance(intraday_feedback_chart, dict)
                and "intraday_feedback_review" not in inserted_charts
                and _is_intraday_feedback_point_table(_split_table_row(lines[index]))
            ):
                items = (
                    intraday_feedback_chart.get("items")
                    if isinstance(intraday_feedback_chart.get("items"), list)
                    else []
                )
                account_conclusion = str(intraday_feedback_chart.get("account_conclusion") or "").strip()
                footnote = "图表来自下方盘面反馈分时点表"
                if account_conclusion:
                    footnote = f"{footnote}；账户结论：{account_conclusion}"
                fragments.append(
                    _bear_chart_card_html(
                        "intraday_feedback_review",
                        eyebrow="盘面记录",
                        title="盘面反馈复盘",
                        subtitle="把上证、当前持仓和昨日目标/今日买入对象放到同一张分时强弱图里。",
                        footnote=footnote,
                        item_count=len(items),
                        tall=True,
                    )
                )
                inserted_charts.add("intraday_feedback_review")
            market_turnover_chart = bear_chart_payload.get("market_turnover_top50_trend")
            if (
                isinstance(market_turnover_chart, dict)
                and "market_turnover_top50_trend" not in inserted_charts
                and _table_has_headers(lines, index, "日期", "Top50占比", "Top50成交额", "两市成交额")
            ):
                items = market_turnover_chart.get("items") if isinstance(market_turnover_chart.get("items"), list) else []
                has_chinext = int(market_turnover_chart.get("chinext_available_count") or 0) > 0
                fragments.extend(
                    [
                        _bear_chart_card_html(
                            "market_turnover_trend",
                            eyebrow="市场容量",
                            title="两市成交额趋势",
                            subtitle="柱形只看市场总成交水位。",
                            footnote="图表来自Top50成交额占比趋势表",
                            item_count=len(items),
                        ),
                        _bear_chart_card_html(
                            "top50_share_trend",
                            eyebrow="头部集中度",
                            title=(
                                "Top50成交占比与创业板指趋势"
                                if has_chinext
                                else "Top50成交占比趋势"
                            ),
                            subtitle=(
                                "双轴比较头部成交集中度与创业板指数走势。"
                                if has_chinext
                                else "折线只看头部成交集中度。"
                            ),
                            footnote="图表来自Top50成交额占比趋势表",
                            item_count=len(items),
                        ),
                    ]
                )
                inserted_charts.add("market_turnover_top50_trend")
            new_high_share_chart = bear_chart_payload.get("new_high_share_trend")
            if (
                isinstance(new_high_share_chart, dict)
                and "new_high_share_trend" not in inserted_charts
                and _table_has_headers(lines, index, "日期", "新高数", "全A占比")
            ):
                items = (
                    new_high_share_chart.get("items")
                    if isinstance(new_high_share_chart.get("items"), list)
                    else []
                )
                fragments.append(
                    _bear_chart_card_html(
                        "new_high_share_trend",
                        eyebrow="趋势扩散",
                        title="创新高全A占比",
                        subtitle=str(
                            new_high_share_chart.get("subtitle")
                            or "创新高绝对水位分层；同一低值还要看变化方向。"
                        ),
                        footnote="图表来自创新高趋势反馈表",
                        item_count=len(items),
                    )
                )
                inserted_charts.add("new_high_share_trend")
            turnover_chart = bear_chart_payload.get("turnover_top30")
            turnover_sector_chart = bear_chart_payload.get("turnover_sector_share")
            if (
                "成交核心结果" in current_section_title
                and isinstance(turnover_chart, dict)
                and "turnover_top30" not in inserted_charts
            ):
                sector_items = (
                    turnover_sector_chart.get("items")
                    if isinstance(turnover_sector_chart, dict) and isinstance(turnover_sector_chart.get("items"), list)
                    else []
                )
                if sector_items and "turnover_sector_share" not in inserted_charts:
                    fragments.append(
                        _bear_chart_card_html(
                            "turnover_sector_share",
                            eyebrow="结构占比",
                            title="成交额Top30板块占比",
                            subtitle="按同一成交榜汇总板块金额，观察资金容量集中方向。",
                            footnote=str(turnover_sector_chart.get("subtitle") or ""),
                            item_count=len(sector_items),
                        )
                    )
                    inserted_charts.add("turnover_sector_share")
                items = turnover_chart.get("items") if isinstance(turnover_chart.get("items"), list) else []
                fragments.append(
                    _bear_chart_card_html(
                        "turnover_top30",
                        eyebrow="成交核心",
                        title="成交额Top30",
                        subtitle="按成交额排序，柱长看金额，柱尾显示成交额与涨跌幅；红涨绿跌。在图内向下滚动查看全部记录。",
                        footnote=str(turnover_chart.get("subtitle") or ""),
                        item_count=len(items),
                    )
                )
                inserted_charts.add("turnover_top30")
            board_tag_chart = bear_chart_payload.get("board_tag_rank_bar")
            is_board_tag_rank_table = _is_board_tag_rank_table_headers(
                _split_table_row(lines[index])
            ) and _is_board_tag_rank_table_context(current_section_title, lines, index)
            if (
                isinstance(board_tag_chart, dict)
                and "board_tag_rank_bar" not in inserted_charts
                and is_board_tag_rank_table
            ):
                items = board_tag_chart.get("items") if isinstance(board_tag_chart.get("items"), list) else []
                fragments.append(
                    _bear_chart_card_html(
                        "board_tag_rank_bar",
                        eyebrow="标签排行",
                        title="板块标签热度排行榜",
                        subtitle="按出现次数横向比较，直接看热榜标签前排强弱。",
                        footnote="图表来自下方标签热度排行榜",
                        item_count=len(items),
                        tall=True,
                    )
                )
                inserted_charts.add("board_tag_rank_bar")
            table_html, index = _render_table(
                lines,
                index,
                stock_refs,
                section_title=current_section_title,
                limit_pools=limit_pools,
                lhb_frozen_limits=lhb_frozen_limits,
                hide_board_tag_heatbar=is_board_tag_rank_table,
            )
            fragments.append(table_html)
            if is_sector_cycle_direction_table:
                fragments.append(_SECTOR_CYCLE_RAW_RECORDS_CLOSE_HTML)
                sector_cycle_raw_records_open = False
                sector_cycle_raw_records_close_level = 0
            continue

        if _is_fenced_code_start(stripped):
            code_html, index = _render_fenced_code(lines, index)
            if 'data-mermaid-diagram="true"' in code_html:
                has_mermaid_diagram = True
            fragments.append(code_html)
            continue

        if stripped == "---":
            fragments.append("<hr>")
            index += 1
            continue

        if stripped.startswith(">"):
            quote_lines, index = _collect_prefixed(lines, index, ">")
            quote = "<br>".join(_inline(item, stock_refs) for item in quote_lines)
            fragments.append(f"<blockquote>{quote}</blockquote>")
            continue

        if stripped.startswith("- "):
            item_lines, index = _collect_prefixed(lines, index, "- ")
            items = "".join(f"<li>{_inline(item, stock_refs)}</li>" for item in item_lines)
            fragments.append(f"<ul>{items}</ul>")
            continue

        paragraph, next_index = _collect_paragraph(lines, index)
        if paragraph:
            fragments.append(f"<p>{_inline(paragraph, stock_refs)}</p>")
            index = next_index
            continue
        index += 1

    if sector_cycle_raw_records_open:
        fragments.append(_SECTOR_CYCLE_RAW_RECORDS_CLOSE_HTML)
    if appendix_section_open:
        fragments.append(_BEAR_APPENDIX_SECTION_CLOSE_HTML)

    first_h1 = next((heading for heading in headings if heading.level == 1), None)
    page_title = title or (first_h1.title if first_h1 else "A股日报")
    nav = _render_nav(headings)
    mobile_nav = _render_nav(headings, mobile=True)
    template = Template(_template_path().read_text(encoding="utf-8"))
    return template.safe_substitute(
        title=_html(page_title),
        trade_date=_html(trade_date),
        source=_html(source_label),
        outline_title=_html(page_title),
        outline_nav=nav,
        mobile_nav=mobile_nav,
        document_body="\n".join(fragments),
        echarts_loader=_echarts_loader_html(output_path),
        mermaid_loader=_mermaid_loader_html(output_path, enabled=has_mermaid_diagram),
        chart_payload=_json_for_html_script(bear_chart_payload),
    )


def render_markdown_report_file(
    markdown_path: str | Path,
    html_path: str | Path | None = None,
    *,
    title: str = "",
    trade_date: str = "",
    source_label: str = "Markdown日报",
    prepend_markdown: str = "",
    tomorrow_action_calendar: Mapping[str, object] | None = None,
    t0_market_breadth: Mapping[str, object] | None = None,
    chinext_index_trend: Mapping[str, object] | None = None,
    sector_tournament_three_axis: Mapping[str, object] | None = None,
    cffex_index_futures_position_evidence: Mapping[str, object] | None = None,
    turnover_rank: Iterable[Mapping[str, object]] | None = None,
    lhb_limit_status: Mapping[str, object] | None = None,
) -> Path:
    source = Path(markdown_path)
    output = Path(html_path) if html_path is not None else source.with_suffix(".html")
    markdown_text = source.read_text(encoding="utf-8")
    if str(prepend_markdown or "").strip() and not _markdown_starts_with_position_timeline(markdown_text):
        markdown_text = f"{str(prepend_markdown).strip()}\n\n{markdown_text.lstrip()}"
    html = render_markdown_report_html(
        markdown_text,
        title=title or source.stem,
        trade_date=trade_date,
        source_label=source_label,
        output_path=output,
        tomorrow_action_calendar=tomorrow_action_calendar,
        t0_market_breadth=t0_market_breadth,
        chinext_index_trend=chinext_index_trend,
        sector_tournament_three_axis=sector_tournament_three_axis,
        cffex_index_futures_position_evidence=cffex_index_futures_position_evidence,
        turnover_rank=turnover_rank,
        lhb_limit_status=lhb_limit_status,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="把已有 markdown 日报渲染为阅读器 HTML")
    parser.add_argument("markdown_path")
    parser.add_argument("html_path", nargs="?")
    parser.add_argument("--title", default="")
    parser.add_argument("--trade-date", default="")
    parser.add_argument("--source-label", default="Markdown日报")
    parser.add_argument("--snapshot-json", default="", help="目标日冻结快照；读取完整成交榜及已有图表事实，不改写快照")
    parser.add_argument(
        "--chinext-index-trend-json",
        default="",
        help="创业板指数历史载荷 JSON 文件",
    )
    parser.add_argument(
        "--sector-tournament-three-axis-json",
        default="",
        help="板块资金扩散淘汰赛三坐标载荷 JSON 文件",
    )
    parser.add_argument(
        "--cffex-position-evidence-json",
        default="",
        help="中金所股指期货持仓结构载荷 JSON 文件",
    )
    args = parser.parse_args(argv)
    snapshot_data = {}
    if args.snapshot_json:
        try:
            snapshot = json.loads(Path(args.snapshot_json).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            parser.error(f"冻结快照无法读取：{exc}")
        if not isinstance(snapshot, dict) or not isinstance(snapshot.get("data"), dict):
            parser.error("冻结快照必须包含日期与 data 对象")
        snapshot_date = str(snapshot.get("date") or "")
        try:
            date.fromisoformat(snapshot_date)
        except ValueError:
            parser.error("冻结快照日期无效")
        if args.trade_date and args.trade_date != snapshot_date:
            parser.error("冻结快照日期与目标交易日不一致")
        args.trade_date = snapshot_date
        snapshot_data = snapshot["data"]
        if snapshot_data.get("target_date", snapshot_date) != snapshot_date:
            parser.error("冻结快照内外日期不一致")
        if not isinstance(snapshot_data.get("turnover_rank"), list):
            parser.error("冻结快照缺少完整成交榜 turnover_rank")

    chinext_index_trend = None
    if args.chinext_index_trend_json:
        payload_path = Path(args.chinext_index_trend_json)
        try:
            chinext_index_trend = json.loads(payload_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            parser.error(f"创业板指数历史载荷无法读取：{exc}")
        if not isinstance(chinext_index_trend, dict):
            parser.error("创业板指数历史载荷必须是 JSON 对象")

    sector_tournament_three_axis = None
    if args.sector_tournament_three_axis_json:
        payload_path = Path(args.sector_tournament_three_axis_json)
        try:
            sector_tournament_three_axis = json.loads(payload_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            parser.error(f"板块资金扩散淘汰赛三坐标载荷无法读取：{exc}")
        if not isinstance(sector_tournament_three_axis, dict):
            parser.error("板块资金扩散淘汰赛三坐标载荷必须是 JSON 对象")

    cffex_index_futures_position_evidence = None
    if args.cffex_position_evidence_json:
        payload_path = Path(args.cffex_position_evidence_json)
        try:
            cffex_index_futures_position_evidence = json.loads(
                payload_path.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as exc:
            parser.error(f"中金所股指期货持仓结构载荷无法读取：{exc}")
        if not isinstance(cffex_index_futures_position_evidence, dict):
            parser.error("中金所股指期货持仓结构载荷必须是 JSON 对象")

    path = render_markdown_report_file(
        args.markdown_path,
        args.html_path,
        title=args.title,
        trade_date=args.trade_date,
        source_label=args.source_label,
        chinext_index_trend=chinext_index_trend or snapshot_data.get("chinext_index_trend"),
        sector_tournament_three_axis=sector_tournament_three_axis or (
            snapshot_data.get("selection_workflow") or {}
        ).get("sector_tournament_three_axis"),
        cffex_index_futures_position_evidence=cffex_index_futures_position_evidence or snapshot_data.get("cffex_index_futures_position_evidence"),
        turnover_rank=snapshot_data.get("turnover_rank"),
        lhb_limit_status={
            "trade_date": args.trade_date,
            "limit_up_codes": snapshot_data.get("limit_up_codes"),
            "limit_down_codes": snapshot_data.get("limit_down_codes"),
        } if args.snapshot_json else None,
    )
    print(f"HTML 日报已生成: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
