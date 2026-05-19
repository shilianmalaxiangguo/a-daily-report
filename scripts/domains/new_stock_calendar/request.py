from __future__ import annotations

import datetime as _dt
import html
import re
import urllib.request

SINA_NEW_STOCK_URL = "https://vip.stock.finance.sina.com.cn/corp/go.php/vRPD_NewStockIssue/page/{page}.phtml"

__all__ = [
    "collect_new_stock_calendar_request_bundle",
    "fetch_sina_new_stock_calendar_pages",
    "parse_sina_new_stock_calendar_html",
]


def _append_log(logs, step, status, message, **details):
    logs.append(
        {
            "module": "domains.new_stock_calendar.request",
            "step": step,
            "status": status,
            "message": message,
            "details": details,
        }
    )


def _strip_tags(value):
    text = re.sub(r"(?is)<[^>]+>", "", str(value or ""))
    text = html.unescape(text).replace("\xa0", " ").replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", text).strip()


def _safe_float(value, default=0.0):
    text = str(value or "").replace(",", "").replace("*", "").strip()
    if not text:
        return float(default)
    try:
        return float(text)
    except (TypeError, ValueError):
        return float(default)


def _normalize_code(value):
    text = _strip_tags(value).lower()
    text = text.replace(".sz", "").replace(".sh", "").replace(".ss", "").replace(".bj", "")
    for prefix in ("sz", "sh", "bj"):
        if text.startswith(prefix):
            text = text[2:]
            break
    match = re.search(r"\d{6}", text)
    return match.group(0) if match else ""


def _normalize_date(value):
    text = _strip_tags(value)
    if not text or text in {"-", "--"}:
        return ""
    match = re.search(r"\d{4}-\d{2}-\d{2}", text)
    return match.group(0) if match else ""


def _parse_date(value):
    text = _normalize_date(value)
    if not text:
        return None
    try:
        return _dt.datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def _market_from_code(code):
    code = str(code or "").strip()
    if code.startswith(("6", "5", "9")):
        return "sh"
    if code.startswith(("8", "4")) or code.startswith("92"):
        return "bj"
    return "sz" if code else ""


def _listing_window(days_to_listing):
    if days_to_listing is None:
        return "outside_window"
    if days_to_listing == 2:
        return "pre_alert_t2"
    if days_to_listing == 1:
        return "tomorrow_listing"
    if days_to_listing == 0:
        return "today_listing"
    if -5 <= days_to_listing <= -1:
        return "recently_listed"
    if 3 <= days_to_listing <= 7:
        return "upcoming_soon"
    return "outside_window"


def _pre_listing_action(listing_window):
    return {
        "pre_alert_t2": "prepare_clear_cash",
        "tomorrow_listing": "focus_tomorrow_battle",
        "today_listing": "live_open_confirm",
        "recently_listed": "post_listing_track",
    }.get(listing_window, "none")


def _extract_table_cells(row_html):
    return [_strip_tags(cell) for cell in re.findall(r"(?is)<td\b[^>]*>(.*?)</td>", row_html or "")]


def parse_sina_new_stock_calendar_html(html_text, target_date="", source_url=""):
    """Parse Sina's table-based new-stock calendar into normalized records."""
    target = _parse_date(target_date)
    records = []

    for row_html in re.findall(r"(?is)<tr\b[^>]*>(.*?)</tr>", html_text or ""):
        cells = _extract_table_cells(row_html)
        if len(cells) < 5:
            continue

        code = _normalize_code(cells[1]) or _normalize_code(cells[0])
        listing_date = _normalize_date(cells[4])
        if not code or not listing_date:
            continue

        listing = _parse_date(listing_date)
        days_to_listing = None
        days_since_listing = None
        if target and listing:
            days_to_listing = (listing - target).days
            days_since_listing = (target - listing).days
        window = _listing_window(days_to_listing)

        records.append(
            {
                "code": code,
                "name": cells[2] if len(cells) > 2 else "",
                "net_issue_date": _normalize_date(cells[3]) if len(cells) > 3 else "",
                "listing_date": listing_date,
                "issue_amount_10k": _safe_float(cells[5] if len(cells) > 5 else ""),
                "online_issue_amount_10k": _safe_float(cells[6] if len(cells) > 6 else ""),
                "issue_price": _safe_float(cells[7] if len(cells) > 7 else ""),
                "pe_ratio": _safe_float(cells[8] if len(cells) > 8 else ""),
                "fundraising_yi": _safe_float(cells[10] if len(cells) > 10 else ""),
                "market": _market_from_code(code),
                "days_to_listing": days_to_listing,
                "days_since_listing": days_since_listing,
                "listing_window": window,
                "pre_listing_action": _pre_listing_action(window),
                "source": "sina_new_stock_calendar",
                "source_url": source_url,
                "source_status": "success",
            }
        )

    return records


def fetch_sina_new_stock_calendar_pages(page_count=2, opener=None):
    """Fetch Sina calendar pages and decode their GB18030 response body."""
    opener = opener or urllib.request.build_opener()
    pages = []
    for page in range(1, int(page_count or 0) + 1):
        source_url = SINA_NEW_STOCK_URL.format(page=page)
        response = opener.open(source_url, timeout=10)
        try:
            with response as opened:
                body = opened.read()
        except AttributeError:
            body = response.read()
        if isinstance(body, bytes):
            html_text = body.decode("gb18030", errors="replace")
        else:
            html_text = str(body or "")
        pages.append({"page": page, "source_url": source_url, "html": html_text})
    return pages


def collect_new_stock_calendar_request_bundle(target_date, *, fetch_pages, timer, emit, page_count=2, request_registry=None):
    results = {"new_stock_calendar": []}
    data_status = {"新股上市日历": False}
    step_status = {"新股上市日历获取": False}
    module_logs = []

    emit("  1️⃣1️⃣ 获取新股上市日历（Tushare 优先）...")
    try:
        calendar_fetcher = (request_registry or {}).get("new_stock_calendar")
        pages = []
        if callable(calendar_fetcher):
            records = calendar_fetcher(target_date=target_date) or []
        else:
            pages = fetch_pages(page_count=page_count)
            records = []
            for page in pages or []:
                if isinstance(page, dict):
                    html_text = page.get("html", "")
                    source_url = page.get("source_url", "")
                else:
                    html_text = str(page or "")
                    source_url = ""
                records.extend(
                    parse_sina_new_stock_calendar_html(
                        html_text,
                        target_date=target_date,
                        source_url=source_url,
                    )
                )

        results["new_stock_calendar"] = records
        data_status["新股上市日历"] = bool(records)
        step_status["新股上市日历获取"] = bool(records)
        label = "新股上市日历获取" if records else "新股上市日历获取(空)"
        elapsed, _ = timer.record(label, 11)
        if records:
            emit(f"   ✅ 新股上市日历成功: {len(records)} 条 [⏱ {elapsed:.2f}s]")
        else:
            emit(f"   ⚠️ 新股上市日历返回空 [⏱ {elapsed:.2f}s]")
        _append_log(
            module_logs,
            "request.new_stock_calendar",
            "success" if records else "degraded",
            "已处理新股上市日历请求",
            provider="tushare.new_share" if callable(calendar_fetcher) else "sina_new_stock_calendar",
            target_keys=["new_stock_calendar"],
            page_count=len(pages or []),
            calendar_count=len(records),
        )
    except Exception as error:
        elapsed, _ = timer.record("新股上市日历获取(失败)", 11)
        emit(f"   ❌ 新股上市日历失败: {error} [⏱ {elapsed:.2f}s]")
        _append_log(
            module_logs,
            "request.new_stock_calendar",
            "error",
            "新股上市日历请求失败",
            provider="sina_new_stock_calendar",
            target_keys=["new_stock_calendar"],
            error=str(error),
        )

    return {
        "results": results,
        "data_status": data_status,
        "step_status": step_status,
        "module_logs": module_logs,
    }
