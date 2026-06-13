from __future__ import annotations

import datetime as _dt

from market_data.kline_dates import normalize_kline_date_str


DEFAULT_NEW_HIGH_TOPDAYS = 250
DEFAULT_ALL_A_DENOMINATOR = 5000
DEFAULT_RECENT_LISTING_DAYS = 365


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return float(default)
        numeric = float(value)
        if numeric != numeric:
            return float(default)
        return numeric
    except (TypeError, ValueError):
        return float(default)


def _safe_int(value, default=0):
    try:
        if value in (None, ""):
            return int(default)
        return int(float(value))
    except (TypeError, ValueError):
        return int(default)


def _clean_code(value):
    text = str(value or "").strip().upper()
    if "." in text:
        text = text.split(".", 1)[0]
    for prefix in ("SH", "SZ", "BJ"):
        if text.startswith(prefix):
            text = text[len(prefix):]
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits.zfill(6) if digits else ""


def _compact_date(value):
    normalized = normalize_kline_date_str(value)
    return normalized.replace("-", "") if normalized else ""


def _parse_compact_date(value):
    text = _compact_date(value)
    if not text or len(text) != 8:
        return None
    try:
        return _dt.datetime.strptime(text, "%Y%m%d").date()
    except ValueError:
        return None


def _lookup_basic(stock_basic_map, code, ts_code):
    mapping = stock_basic_map or {}
    item = mapping.get(code) or mapping.get(str(ts_code or "").strip().upper()) or {}
    if isinstance(item, dict):
        return item
    return {"name": str(item or "").strip()}


def _is_st_or_risk(name, code, stock_risk_map):
    text = str(name or "").strip().upper()
    if text.startswith("*ST") or text.startswith("ST") or "退" in text:
        return True
    risk = (stock_risk_map or {}).get(code) or {}
    flags = set(risk.get("risk_flags") or [])
    return bool(flags.intersection({"st_warning", "risk_warning", "delist_risk"}))


def _is_new_or_recent(list_date, target_date, max_listing_days):
    listed = _parse_compact_date(list_date)
    target = _parse_compact_date(target_date)
    if not listed or not target:
        return False
    return 0 <= (target - listed).days < int(max_listing_days or DEFAULT_RECENT_LISTING_DAYS)


def _amount_yi(row):
    amount = _safe_float((row or {}).get("amount_yi"))
    if amount > 0:
        return amount
    amount_raw = _safe_float((row or {}).get("amount"))
    return round(amount_raw / 100000.0, 6) if amount_raw > 0 else 0.0


def _pct(value, denominator):
    denominator = _safe_float(denominator)
    if denominator <= 0:
        return 0.0
    return _safe_float(value) / denominator * 100.0


def _format_pct(value):
    return f"{_safe_float(value):.2f}%"


def _leading_sector_text(sector_rows, limit=3):
    names = [row.get("sector") for row in (sector_rows or [])[:limit] if row.get("sector")]
    return "、".join(names) if names else "待补充板块"


def _build_sector_distribution(stocks):
    buckets = {}
    for stock in stocks or []:
        sector = str(stock.get("sector") or "待补充板块").strip() or "待补充板块"
        bucket = buckets.setdefault(
            sector,
            {
                "sector": sector,
                "new_high_count": 0,
                "amount_yi": 0.0,
                "representative_stocks": [],
            },
        )
        bucket["new_high_count"] += 1
        bucket["amount_yi"] += _safe_float(stock.get("amount_yi"))
        if len(bucket["representative_stocks"]) < 3 and stock.get("name"):
            bucket["representative_stocks"].append(stock.get("name"))
    total = len(stocks or [])
    rows = []
    for bucket in buckets.values():
        rows.append(
            {
                **bucket,
                "amount_yi": round(bucket["amount_yi"], 2),
                "share_pct": round(_pct(bucket["new_high_count"], total), 2),
            }
        )
    return sorted(rows, key=lambda item: (-item["new_high_count"], -item["amount_yi"], item["sector"]))


def _build_trend_rows(target_date, new_high_count, all_a_share_pct, sector_rows, history_rows):
    rows = []
    for row in history_rows or []:
        item = dict(row or {})
        item.setdefault("trade_date", item.get("date", ""))
        item.setdefault("leading_sectors", _leading_sector_text(item.get("sector_distribution") or []))
        rows.append(item)
    rows = sorted(rows, key=lambda item: str(item.get("trade_date") or ""))
    previous_count = None
    for item in rows:
        current_count = _safe_int(item.get("new_high_count"), 0)
        if previous_count is None:
            item["change_text"] = item.get("change_text") or "待累计"
        else:
            existing_change = str(item.get("change_text") or "").strip()
            item["change_text"] = existing_change if existing_change and existing_change != "待累计" else f"{current_count - previous_count:+d}"
        previous_count = current_count
    previous = rows[-1] if rows else {}
    previous_count = _safe_int(previous.get("new_high_count"), 0)
    change_text = f"{new_high_count - previous_count:+d}" if previous else "待累计"
    rows.append(
        {
            "trade_date": normalize_kline_date_str(target_date) or str(target_date or ""),
            "new_high_count": new_high_count,
            "all_a_share_pct": round(_safe_float(all_a_share_pct), 2),
            "change_text": change_text,
            "leading_sectors": _leading_sector_text(sector_rows),
        }
    )
    return rows[-25:]


def build_new_high_feedback_snapshot(
    factor_rows,
    *,
    stock_basic_map=None,
    stock_risk_map=None,
    target_date="",
    topdays_threshold=DEFAULT_NEW_HIGH_TOPDAYS,
    all_a_denominator=DEFAULT_ALL_A_DENOMINATOR,
    recent_listing_days=DEFAULT_RECENT_LISTING_DAYS,
    history_rows=None,
    top_stock_limit=30,
):
    factor_rows = list(factor_rows or [])
    if not factor_rows:
        source = "tushare.stk_factor_pro.topdays"
        date_text = str(target_date or "").strip() or "目标日"
        return {
            "available": False,
            "status": "upstream_empty",
            "source": source,
            "message": f"Tushare stk_factor_pro 当前未返回 {date_text} 技术因子，暂不判断阶段新高反馈。",
            "new_high_count": 0,
            "all_a_share_pct": 0.0,
            "sector_distribution": [],
            "top_stocks": [],
            "trend_rows": [],
            "excluded_counts": {},
        }

    excluded_counts = {
        "below_topdays_threshold": 0,
        "st_or_risk": 0,
        "new_or_recent": 0,
        "missing_code": 0,
    }
    stocks = []
    for row in factor_rows:
        row = row or {}
        code = _clean_code(row.get("stock_code") or row.get("ts_code") or row.get("code"))
        if not code:
            excluded_counts["missing_code"] += 1
            continue
        if _safe_int(row.get("topdays")) < int(topdays_threshold or DEFAULT_NEW_HIGH_TOPDAYS):
            excluded_counts["below_topdays_threshold"] += 1
            continue
        ts_code = str(row.get("ts_code") or "").strip().upper()
        basic = _lookup_basic(stock_basic_map, code, ts_code)
        name = str(row.get("name") or basic.get("name") or "").strip()
        if _is_st_or_risk(name, code, stock_risk_map):
            excluded_counts["st_or_risk"] += 1
            continue
        if _is_new_or_recent(basic.get("list_date"), target_date or row.get("trade_date"), recent_listing_days):
            excluded_counts["new_or_recent"] += 1
            continue
        sector = str(basic.get("industry") or row.get("industry") or row.get("sector") or "待补充板块").strip()
        stocks.append(
            {
                "code": code,
                "ts_code": ts_code,
                "name": name or code,
                "sector": sector or "待补充板块",
                "close": _safe_float(row.get("close")),
                "high": _safe_float(row.get("high")),
                "pct_chg": round(_safe_float(row.get("pct_chg") or row.get("pct_change")), 2),
                "amount_yi": _amount_yi(row),
                "topdays": _safe_int(row.get("topdays")),
            }
        )

    stocks.sort(key=lambda item: (-item["amount_yi"], -item["pct_chg"], item["code"]))
    new_high_count = len(stocks)
    all_a_share_pct = round(_pct(new_high_count, all_a_denominator), 2)
    sector_rows = _build_sector_distribution(stocks)
    leading_sectors = _leading_sector_text(sector_rows)
    summary = (
        f"今日非ST非新股非次新阶段新高 {new_high_count} 只，"
        f"占全A约 {_format_pct(all_a_share_pct)}，主要集中在 {leading_sectors}。"
    )
    trend_rows = _build_trend_rows(target_date, new_high_count, all_a_share_pct, sector_rows, history_rows)
    return {
        "available": True,
        "status": "success",
        "source": "tushare.stk_factor_pro.topdays",
        "topdays_threshold": int(topdays_threshold or DEFAULT_NEW_HIGH_TOPDAYS),
        "all_a_denominator": int(all_a_denominator or DEFAULT_ALL_A_DENOMINATOR),
        "new_high_count": new_high_count,
        "all_a_share_pct": all_a_share_pct,
        "leading_sectors": leading_sectors,
        "summary": summary,
        "sector_distribution": sector_rows,
        "top_stocks": stocks[: int(top_stock_limit or 30)],
        "trend_rows": trend_rows,
        "excluded_counts": excluded_counts,
    }
