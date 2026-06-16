from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from html import escape, unescape
from pathlib import Path
from string import Template
from typing import Iterable

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from report.surface_wording import sanitize_user_visible_text


# Bear/readable HTML renderer: consumes the final Markdown report and preserves
# the reader-facing narrative. Structured fact checks live in html_report_view.py.
@dataclass(frozen=True)
class Heading:
    level: int
    title: str
    anchor: str


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


def _echarts_loader_html() -> str:
    source_path = _echarts_source_path()
    if source_path.exists():
        return f'<script src="{_html(source_path.as_uri())}"></script>'
    return '<script src="https://cdn.jsdelivr.net/npm/echarts@5.6.0/dist/echarts.min.js"></script>'


def _html(value: object) -> str:
    return escape(str(value if value is not None else ""), quote=True)


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


def _inline_without_code(text: str, stock_refs: tuple[str, ...]) -> str:
    parts: list[str] = []
    index = 0
    for match in re.finditer(r"(\*\*|__)(.+?)\1", text):
        parts.append(_stock_refs(_html(text[index : match.start()]), stock_refs))
        parts.append(f"<strong>{_stock_refs(_html(match.group(2)), stock_refs)}</strong>")
        index = match.end()
    parts.append(_stock_refs(_html(text[index:]), stock_refs))
    return "".join(parts)


def _table_cell_inline(
    headers: list[str],
    row: list[str],
    cell_index: int,
    stock_refs: tuple[str, ...],
    *,
    in_cycle_sector_surface: bool = False,
) -> str:
    header = headers[cell_index] if cell_index < len(headers) else ""
    cell = row[cell_index] if cell_index < len(row) else ""
    if in_cycle_sector_surface and "cycle-sector-" in cell:
        return _cycle_calendar_cell_inline(cell, stock_refs)
    if _is_stock_code_header(header):
        code_html = _stock_code_cell(cell)
        if code_html:
            return code_html
    if _is_stock_name_header(header):
        name_html = _stock_name_cell(cell, row, stock_refs)
        if name_html:
            return name_html
    return _inline(cell, stock_refs)


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
    lang_attr = f' lang="{_html(language)}"' if language else ""
    return (
        '<pre class="fenced-code"><code class="fenced-code-content"'
        + lang_attr
        + ">"
        + _html("\n".join(code_lines))
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


def _limit_status_from_turnover_row(change_pct: float | None, candle_text: str) -> str:
    text = _plain_cell_text(candle_text)
    if change_pct is not None and change_pct >= 9.8:
        return "涨停"
    if change_pct is not None and change_pct <= -9.8:
        return "跌停"
    if "涨停" in text:
        return "涨停"
    if "跌停" in text:
        return "跌停"
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


def _collect_sector_turnover_chart_items(lines: list[str], trade_date: str) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    seen: set[str] = set()
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
            else:
                current_sector = ""
                current_color = ""
            index += 1
            continue
        if not current_sector or not _is_table_start(lines, index):
            index += 1
            continue

        headers, rows, index = _collect_table(lines, index)
        date_index = _header_index(headers, "日期")
        sector_turnover_index = _header_index(headers, "板块成交额")
        total_turnover_index = _header_index(headers, "两市成交额")
        share_index = _header_index(headers, "占比")
        change_index = _header_index(headers, "同板块变化", "占比变化")
        status_index = _header_index(headers, "样本状态")
        note_index = _header_index(headers, "解读")
        if min(date_index, sector_turnover_index, total_turnover_index, share_index) < 0:
            continue

        preferred_rows = [row for row in rows if _plain_cell_text(_cell_at(row, date_index)) == trade_date] if trade_date else []
        if trade_date and not preferred_rows:
            continue
        candidates = preferred_rows or rows[:1]
        for row in candidates:
            share_pct = _numeric_percent(_cell_at(row, share_index))
            sector_turnover = _numeric_amount_yi(_cell_at(row, sector_turnover_index))
            total_turnover = _numeric_amount_yi(_cell_at(row, total_turnover_index))
            if share_pct is None or sector_turnover is None:
                continue
            sector = current_sector or "未命名板块"
            if sector in seen:
                continue
            seen.add(sector)
            items.append(
                {
                    "sector": sector,
                    "date": _plain_cell_text(_cell_at(row, date_index)),
                    "turnover": sector_turnover,
                    "total_turnover": total_turnover,
                    "share_pct": share_pct,
                    "change_pct": _numeric_pct_point(_cell_at(row, change_index)),
                    "status": _plain_cell_text(_cell_at(row, status_index)),
                    "note": _plain_cell_text(_cell_at(row, note_index)),
                    "color": current_color,
                }
            )
            break
        continue
    return sorted(items, key=lambda item: float(item.get("share_pct") or 0), reverse=True)


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
                    "status": _limit_status_from_turnover_row(change_pct, _cell_at(row, candle_index)),
                }
            )
        return items
    return []


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
        if not any(marker in current_heading for marker in ("标签热度排行榜", "标签面积占比图")) or not _is_table_start(lines, index):
            index += 1
            continue

        headers, rows, _next_index = _collect_table(lines, index)
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


def _is_lhb_side_heading(heading: str, side: str) -> bool:
    text = _plain_cell_text(heading)
    if side == "buy":
        return "净买入结果" in text
    return "净流出结果" in text or "净卖出结果" in text


def _collect_lhb_flow_items(lines: list[str], limit_per_side: int = 10) -> list[dict[str, object]]:
    current_heading = ""
    items: list[dict[str, object]] = []
    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        heading_match = re.match(r"^(#{1,6})\s+(.+?)\s*$", stripped)
        if heading_match:
            current_heading = heading_match.group(2)
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
        status_index = _header_index(headers, "涨停状态", "状态")
        candle_index = _header_index(headers, "蜡烛图形态")
        if min(amount_index, name_index, sector_index) < 0:
            continue

        for row in rows[:limit_per_side]:
            amount = _numeric_amount_yi(_cell_at(row, amount_index))
            if amount is None:
                continue
            signed_amount = abs(amount) if side == "buy" else -abs(amount)
            change_pct = _numeric_percent(_cell_at(row, change_index))
            status = _plain_cell_text(_cell_at(row, status_index))
            if not status:
                status = _limit_status_from_turnover_row(change_pct, _cell_at(row, candle_index))
            rank_text = _plain_cell_text(_cell_at(row, rank_index))
            try:
                rank = int(rank_text)
            except ValueError:
                rank = len([item for item in items if item.get("side") == side]) + 1
            items.append(
                {
                    "rank": rank,
                    "name": _plain_cell_text(_cell_at(row, name_index)),
                    "code": _plain_cell_text(_cell_at(row, code_index)),
                    "sector": _plain_cell_text(_cell_at(row, sector_index)),
                    "amount": signed_amount,
                    "abs_amount": abs(amount),
                    "change_pct": change_pct,
                    "status": status,
                    "side": side,
                }
            )
        continue

    return sorted(items, key=lambda item: float(item.get("amount") or 0), reverse=True)


def _collect_bear_chart_payload(markdown_text: str, trade_date: str) -> dict[str, object]:
    lines = markdown_text.splitlines()
    sector_items = _collect_sector_turnover_chart_items(lines, trade_date)
    market_turnover_items = _collect_market_turnover_top50_items(lines)
    turnover_items = _collect_turnover_top_items(lines, limit=30)
    turnover_sector_items = _collect_turnover_sector_share_items(turnover_items)
    board_tag_items = _collect_board_tag_rank_items(lines)
    lhb_items = _collect_lhb_flow_items(lines)
    payload: dict[str, object] = {}
    if market_turnover_items:
        payload["market_turnover_top50_trend"] = {
            "items": market_turnover_items,
            "title": "两市成交额与Top50占比",
            "subtitle": "柱看两市成交额，线看头部成交集中度",
        }
    if sector_items:
        payload["sector_turnover_share"] = {
            "items": sector_items,
            "title": "板块成交额占比",
            "subtitle": "只取目标日行；变化按同板块历史比较",
        }
    if turnover_items:
        if turnover_sector_items:
            payload["turnover_sector_share"] = {
                "items": turnover_sector_items,
                "title": "成交额Top30板块占比",
                "subtitle": "按成交核心结果表汇总板块成交额",
            }
        payload["turnover_top30"] = {
            "items": turnover_items,
            "title": "成交额Top30",
            "subtitle": "来自成交核心结果表，红涨绿跌",
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
            "subtitle": "正轴为净买入，负轴为净流出",
        }
    return payload


def _bear_chart_card_html(
    chart_id: str,
    *,
    eyebrow: str,
    title: str,
    subtitle: str,
    footnote: str,
    item_count: int,
    tall: bool = False,
) -> str:
    if item_count <= 0:
        return ""
    tall_class = " is-tall" if tall else ""
    return (
        f'<section class="bear-chart-card" data-bear-chart-card="{_html(chart_id)}">'
        '<div class="bear-chart-copy">'
        f'<span class="bear-chart-eyebrow">{_html(eyebrow)}</span>'
        f"<h4>{_html(title)}</h4>"
        f"<p>{_html(subtitle)}</p>"
        "</div>"
        f'<div class="bear-chart-frame{tall_class}">'
        f'<div class="bear-chart" data-bear-chart="{_html(chart_id)}" role="img" aria-label="{_html(title)}"></div>'
        "</div>"
        f'<p class="bear-chart-footnote">{_html(footnote)} · 当前样本 {item_count} 条</p>'
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
    return "龙虎榜结果" in section_title or str(section_title or "") in {"净买入结果", "净流出结果"}


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


def _row_limit_status_signal(headers: list[str], row: list[str]) -> str:
    for header_index, header_value in enumerate(headers):
        if header_index >= len(row):
            continue
        header_text = _table_header_text(header_value)
        if header_text not in {"连板标签", "涨停标签", "涨停状态", "状态"}:
            continue
        signal = _heat_core_status_signal(row[header_index])
        if signal:
            return signal
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


def _lhb_limit_signal(headers: list[str], row: list[str], cell_index: int, section_title: str) -> str:
    if not _is_lhb_section(section_title):
        return ""
    header = headers[cell_index] if cell_index < len(headers) else ""
    if _table_header_text(header) not in {"涨跌幅", "涨幅"}:
        return ""
    return _row_limit_status_signal(headers, row)


def _lhb_signal_strength_signal(headers: list[str], row: list[str], cell_index: int, section_title: str) -> str:
    if not _is_lhb_section(section_title):
        return ""
    header = headers[cell_index] if cell_index < len(headers) else ""
    if _table_header_text(header) != "信号强度":
        return ""
    text = row[cell_index] if cell_index < len(row) else ""
    return _heat_core_status_signal(text)


def _signal_class(
    headers: list[str],
    row: list[str],
    cell_index: int,
    *,
    section_title: str = "",
    limit_pools: LimitPools | None = None,
) -> str:
    limit_pools = limit_pools or LimitPools(up=frozenset(), down=frozenset())
    limit_signal = _heat_core_limit_signal(headers, row, cell_index, section_title, limit_pools)
    if limit_signal:
        return limit_signal

    lhb_signal = _lhb_limit_signal(headers, row, cell_index, section_title)
    if lhb_signal:
        return lhb_signal

    lhb_strength_signal = _lhb_signal_strength_signal(headers, row, cell_index, section_title)
    if lhb_strength_signal:
        return lhb_strength_signal

    header = headers[cell_index] if cell_index < len(headers) else ""
    label = row[0] if row else ""
    text = row[cell_index] if cell_index < len(row) else ""
    context = f"{header} {label}"

    if "Top50" in context and "占比" in context:
        pct = _numeric_percent(text)
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
) -> tuple[str, int]:
    headers = _split_table_row(lines[index])
    index += 2
    rows: list[list[str]] = []
    while index < len(lines) and lines[index].lstrip().startswith("|"):
        if not _is_table_separator(lines[index]):
            rows.append(_split_table_row(lines[index]))
        index += 1

    header_html = "".join(f"<th>{_inline(header, stock_refs)}</th>" for header in headers)
    is_cycle_calendar = _is_cycle_calendar_section(section_title)
    is_cycle_sector_surface = _is_cycle_sector_surface(section_title)
    body_rows = []
    for row in rows:
        padded = row + [""] * max(0, len(headers) - len(row))
        cells = []
        for cell_index, cell in enumerate(padded[: len(headers)]):
            class_name = _signal_class(
                headers,
                padded,
                cell_index,
                section_title=section_title,
                limit_pools=limit_pools,
            )
            cell_html = _table_cell_inline(
                headers,
                padded,
                cell_index,
                stock_refs,
                in_cycle_sector_surface=is_cycle_sector_surface,
            )
            if class_name:
                cells.append(f'<td class="has-signal"><span class="signal-marker {class_name}">{cell_html}</span></td>')
            else:
                cells.append(f"<td>{cell_html}</td>")
        body_rows.append("<tr>" + "".join(cells) + "</tr>")
    body = "\n".join(body_rows) or f'<tr><td colspan="{len(headers)}">暂无数据</td></tr>'
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
            or stripped.startswith(">")
            or stripped.startswith("- ")
            or stripped == "---"
            or _is_fenced_code_start(stripped)
            or _is_table_start(lines, index)
        ):
            break
        paragraph.append(stripped)
        index += 1
    return " ".join(paragraph), index


def _collect_prefixed(lines: list[str], index: int, prefix: str) -> tuple[list[str], int]:
    items = []
    while index < len(lines) and lines[index].strip().startswith(prefix):
        items.append(lines[index].strip()[len(prefix) :].strip())
        index += 1
    return items, index


def _render_nav(headings: Iterable[Heading], *, mobile: bool = False) -> str:
    items = []
    for index, heading in enumerate(headings):
        if heading.level > 3:
            continue
        active_class = " is-active" if index == 0 and not mobile else ""
        class_name = f' class="level-{heading.level}{active_class}"'
        current_attr = ' aria-current="true"' if active_class else ""
        items.append(
            f'<a{class_name}{current_attr} href="#{_html(heading.anchor)}" data-outline-anchor="{_html(heading.anchor)}">'
            f"{_html(heading.title)}</a>"
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
) -> str:
    markdown_text = _sanitize_reader_markdown_text(markdown_text)
    lines = markdown_text.splitlines()
    stock_refs = _collect_stock_refs(markdown_text)
    limit_pools = _collect_limit_pools(markdown_text)
    bear_chart_payload = _collect_bear_chart_payload(markdown_text, trade_date)
    used_anchors: dict[str, int] = {}
    headings: list[Heading] = []
    fragments: list[str] = []
    inserted_charts: set[str] = set()
    index = 0
    current_h2_title = ""
    current_section_title = ""

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped:
            index += 1
            continue

        heading_match = re.match(r"^(#{1,6})\s+(.+?)\s*$", stripped)
        if heading_match:
            level = len(heading_match.group(1))
            heading_title = _strip_inline_markdown(heading_match.group(2))
            if _is_stale_price_band_heading(lines, index, heading_title, level, trade_date):
                index = _skip_section(lines, index, level)
                continue
            if _is_judgment_review_internal_heading(current_h2_title, heading_title, level):
                fragments.append(f"<p><strong>{_inline(heading_match.group(2), stock_refs)}</strong></p>")
                index += 1
                continue
            anchor = _heading_anchor(heading_title, used_anchors)
            headings.append(Heading(level=level, title=heading_title, anchor=anchor))
            fragments.append(
                f'<h{level} id="{_html(anchor)}">'
                f'{_heading_inline(heading_match.group(2), stock_refs, section_title=heading_title)}</h{level}>'
            )
            sector_chart = bear_chart_payload.get("sector_turnover_share")
            if (
                "主线成交额占比趋势" in heading_title
                and isinstance(sector_chart, dict)
                and "sector_turnover_share" not in inserted_charts
            ):
                items = sector_chart.get("items") if isinstance(sector_chart.get("items"), list) else []
                fragments.append(
                    _bear_chart_card_html(
                        "sector_turnover_share",
                        eyebrow="容量雷达",
                        title="板块成交额占比",
                        subtitle="横向比较目标日热点板块的成交额占比，看资金最集中流向。",
                        footnote="图表来自下方板块成交额连续跟踪表",
                        item_count=len(items),
                    )
                )
                inserted_charts.add("sector_turnover_share")
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
                        subtitle="右侧看净买入强度，左侧看净流出压力；先看方向，再看是否验证主线。",
                        footnote="图表来自龙虎榜净买入/净流出结果表",
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
            market_turnover_chart = bear_chart_payload.get("market_turnover_top50_trend")
            if (
                isinstance(market_turnover_chart, dict)
                and "market_turnover_top50_trend" not in inserted_charts
                and _table_has_headers(lines, index, "日期", "Top50占比", "Top50成交额", "两市成交额")
            ):
                items = market_turnover_chart.get("items") if isinstance(market_turnover_chart.get("items"), list) else []
                fragments.append(
                    _bear_chart_card_html(
                        "market_turnover_top50_trend",
                        eyebrow="容量温度",
                        title="两市成交额 + Top50占比",
                        subtitle="柱形看总水位，折线看头部成交集中度；同一时间序列，不换比较基准。",
                        footnote="图表来自Top50成交额占比趋势表",
                        item_count=len(items),
                    )
                )
                inserted_charts.add("market_turnover_top50_trend")
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
                            subtitle="把成交核心个股按板块汇总，先看资金容量集中在哪些方向。",
                            footnote="图表来自成交核心结果表，按表内样本成交额重新汇总",
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
                        subtitle="按成交额排序，颜色跟随涨跌，涨停/跌停会在 tooltip 里标出来。",
                        footnote="图表来自成交核心结果表；若正文只输出部分行，图表同步只展示表内样本",
                        item_count=len(items),
                        tall=True,
                    )
                )
                inserted_charts.add("turnover_top30")
            table_html, index = _render_table(
                lines,
                index,
                stock_refs,
                section_title=current_section_title,
                limit_pools=limit_pools,
            )
            fragments.append(table_html)
            continue

        if _is_fenced_code_start(stripped):
            code_html, index = _render_fenced_code(lines, index)
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
        echarts_loader=_echarts_loader_html(),
        chart_payload=_json_for_html_script(bear_chart_payload),
    )


def render_markdown_report_file(
    markdown_path: str | Path,
    html_path: str | Path | None = None,
    *,
    title: str = "",
    trade_date: str = "",
    source_label: str = "Markdown日报",
) -> Path:
    source = Path(markdown_path)
    output = Path(html_path) if html_path is not None else source.with_suffix(".html")
    html = render_markdown_report_html(
        source.read_text(encoding="utf-8"),
        title=title or source.stem,
        trade_date=trade_date,
        source_label=source_label,
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
    args = parser.parse_args(argv)

    path = render_markdown_report_file(
        args.markdown_path,
        args.html_path,
        title=args.title,
        trade_date=args.trade_date,
        source_label=args.source_label,
    )
    print(f"HTML 日报已生成: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
