from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from html import escape
from pathlib import Path
from string import Template
from typing import Iterable


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


def _html(value: object) -> str:
    return escape(str(value if value is not None else ""), quote=True)


_CLEAN_STOCK_REF_RE = re.compile(
    r"(^|[\s:：=,，、;；|([{（【《])"
    r"(\*?[A-Za-zＡ-Ｚａ-ｚ\u4e00-\u9fff][A-Za-zＡ-Ｚａ-ｚ0-9\u4e00-\u9fff·]{1,5}\([036]\d{5}\))"
)
_STOCK_NAME_RE = re.compile(r"\*?[A-Za-zＡ-Ｚａ-ｚ\u4e00-\u9fff][A-Za-zＡ-Ｚａ-ｚ0-9\u4e00-\u9fff·]{1,10}")


def _strip_inline_markdown(text: str) -> str:
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"__([^_]+)__", r"\1", text)
    return text.strip()


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
        status_indexes = [
            header_index
            for header_index, header_text in enumerate(header_texts)
            if header_text in {"涨停状态", "状态"}
        ]
        is_up_pool = (
            ("涨停池" in current_heading and "跌停" not in current_heading)
            or "连板结果" in current_heading
            or "首板结果" in current_heading
            or any("首次涨停" in header_text for header_text in header_texts)
        )
        is_down_pool = "跌停池" in current_heading
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


def _table_cell_inline(headers: list[str], row: list[str], cell_index: int, stock_refs: tuple[str, ...]) -> str:
    header = headers[cell_index] if cell_index < len(headers) else ""
    cell = row[cell_index] if cell_index < len(row) else ""
    if _is_stock_code_header(header):
        code_html = _stock_code_cell(cell)
        if code_html:
            return code_html
    if _is_stock_name_header(header):
        name_html = _stock_name_cell(cell, row, stock_refs)
        if name_html:
            return name_html
    return _inline(cell, stock_refs)


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
        re.match(r"^近\d+个已结算交易日正确率", heading_title) is not None
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
    return ""


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
            cell_html = _table_cell_inline(headers, padded, cell_index, stock_refs)
            if class_name:
                cells.append(f'<td class="has-signal"><span class="signal-marker {class_name}">{cell_html}</span></td>')
            else:
                cells.append(f"<td>{cell_html}</td>")
        body_rows.append("<tr>" + "".join(cells) + "</tr>")
    body = "\n".join(body_rows) or f'<tr><td colspan="{len(headers)}">暂无数据</td></tr>'
    return (
        '<div class="reader-table"><table><thead><tr>'
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
    lines = markdown_text.splitlines()
    stock_refs = _collect_stock_refs(markdown_text)
    limit_pools = _collect_limit_pools(markdown_text)
    used_anchors: dict[str, int] = {}
    headings: list[Heading] = []
    fragments: list[str] = []
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
            fragments.append(f'<h{level} id="{_html(anchor)}">{_inline(heading_match.group(2), stock_refs)}</h{level}>')
            if level == 2:
                current_h2_title = heading_title
            current_section_title = heading_title
            index += 1
            continue

        if _is_table_start(lines, index):
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
