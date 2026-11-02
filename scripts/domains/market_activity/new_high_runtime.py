from __future__ import annotations

import datetime as _dt

from market_data.kline_dates import normalize_kline_date_str


DEFAULT_NEW_HIGH_TOPDAYS = 250
DEFAULT_ALL_A_DENOMINATOR = 5000
DEFAULT_RECENT_LISTING_DAYS = 365
_MISSING_TEXT_VALUES = {"", "nan", "nat", "none", "null", "<na>"}
_MISSING_SECTOR_VALUES = {"-", "未知", "未归类", "待补充板块", "待补事实", "暂无"}


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


def _clean_text(value):
    if value is None:
        return ""
    try:
        text = str(value).strip()
    except Exception:
        return ""
    return "" if text.lower() in _MISSING_TEXT_VALUES else text


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
    text = _clean_text(name).upper()
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


def _has_explicit_new_stock_name(name):
    text = _clean_text(name).upper()
    return bool(text) and text.startswith(("N", "C"))


def _required_previous_trade_days(topdays_threshold):
    return max(int(topdays_threshold or DEFAULT_NEW_HIGH_TOPDAYS) - 1, 1)


def _amount_yi(row):
    amount = _safe_float((row or {}).get("amount_yi"))
    if amount > 0:
        return amount
    turnover_yi = _safe_float((row or {}).get("turnover_yi"))
    if turnover_yi > 0:
        return turnover_yi
    turnover = _safe_float((row or {}).get("turnover"))
    if turnover > 0:
        return turnover
    chinese_amount = _safe_float((row or {}).get("成交额"))
    if chinese_amount > 0:
        return chinese_amount
    amount_raw = _safe_float((row or {}).get("amount"))
    return round(amount_raw / 100000.0, 6) if amount_raw > 0 else 0.0


def is_missing_new_high_sector(value):
    text = _clean_text(value)
    return not text or text in _MISSING_SECTOR_VALUES


def is_missing_new_high_name(value, code=""):
    text = _clean_text(value)
    if not text:
        return True
    normalized = text.upper().replace(" ", "").replace("-", "")
    for suffix in (".SZ", ".SS", ".SH", ".BJ"):
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)]
            break
    for prefix in ("SZ", "SH", "BJ"):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):]
            break
    return bool(code) and normalized == _clean_code(code)


def _valid_sector(value):
    text = _clean_text(value)
    if is_missing_new_high_sector(text):
        return ""
    return text


def _contains_serialized_missing_text(value):
    if value is None:
        return False
    try:
        text = str(value).strip()
    except Exception:
        return False
    for separator in ("，", ",", "/", "|"):
        text = text.replace(separator, "、")
    return any(part.strip().lower() in (_MISSING_TEXT_VALUES - {""}) for part in text.split("、"))


def new_high_feedback_has_invalid_content(feedback):
    if not isinstance(feedback, dict):
        return False
    if _contains_serialized_missing_text(feedback.get("leading_sectors")):
        return True
    for row in feedback.get("sector_distribution") or []:
        if isinstance(row, dict) and _contains_serialized_missing_text(row.get("sector")):
            return True
    for row in feedback.get("top_stocks") or []:
        if not isinstance(row, dict):
            continue
        code = _clean_code(row.get("code") or row.get("stock_code") or row.get("ts_code"))
        if is_missing_new_high_name(row.get("name") or row.get("名称"), code):
            return True
        if is_missing_new_high_sector(row.get("sector") or row.get("industry") or row.get("所属板块")):
            return True
        if _has_explicit_new_stock_name(row.get("name")):
            return True
        if "history_trade_days" in row:
            threshold = _safe_int(row.get("topdays"), DEFAULT_NEW_HIGH_TOPDAYS)
            if _safe_int(row.get("history_trade_days"), -1) < _required_previous_trade_days(threshold):
                return True
    return False


def _stock_info_map_by_code(stock_info_map):
    normalized = {}
    for raw_code, info in (stock_info_map or {}).items():
        code = _clean_code(raw_code)
        if code and isinstance(info, dict):
            normalized[code] = info
    return normalized


def _stock_info_matches_target_date(info, target_date):
    target = normalize_kline_date_str(target_date)
    if not target or not isinstance(info, dict):
        return False
    raw_dates = [
        info.get(key)
        for key in ("trade_date", "source_date", "query_date", "date")
        if info.get(key) not in (None, "")
    ]
    if not raw_dates:
        return False
    normalized_dates = [normalize_kline_date_str(value) for value in raw_dates]
    return all(value == target for value in normalized_dates)


def _stock_info_name(info):
    for key in ("name", "名称", "stock_name"):
        name = _clean_text((info or {}).get(key))
        if name:
            return name
    return ""


def _stock_info_sector(info):
    for key in ("sector", "industry", "所属行业", "所属板块", "sector_name", "板块", "行业"):
        sector = _valid_sector((info or {}).get(key))
        if sector:
            return sector
    return ""


def new_high_feedback_identity_check(feedback):
    feedback = feedback if isinstance(feedback, dict) else {}
    issues = []
    for row in feedback.get("top_stocks") or []:
        if not isinstance(row, dict):
            continue
        code = _clean_code(row.get("code") or row.get("stock_code") or row.get("ts_code"))
        missing_fields = []
        if is_missing_new_high_name(row.get("name") or row.get("名称"), code):
            missing_fields.append("名称")
        if is_missing_new_high_sector(
            row.get("sector") or row.get("industry") or row.get("所属行业") or row.get("所属板块")
        ):
            missing_fields.append("所属板块")
        if missing_fields:
            issues.append(
                {
                    "code": code or "代码缺失",
                    "missing_fields": missing_fields,
                }
            )
    return {
        "complete": not issues,
        "source": str(feedback.get("source") or "new_high_feedback.top_stocks"),
        "issues": issues,
    }


def _refresh_new_high_feedback_aggregates(feedback, stocks, target_date):
    if _safe_int(feedback.get("new_high_count"), 0) != len(stocks):
        return feedback
    sector_rows = _build_sector_distribution(stocks)
    leading_sectors = _leading_sector_text(sector_rows)
    feedback["sector_distribution"] = sector_rows
    feedback["leading_sectors"] = leading_sectors
    feedback["summary"] = (
        f"今日非ST非新股非次新阶段新高 {len(stocks)} 只，"
        f"占全A约 {_format_pct(feedback.get('all_a_share_pct'))}，主要集中在 {leading_sectors}。"
    )
    target = normalize_kline_date_str(target_date)
    trend_rows = []
    for row in feedback.get("trend_rows") or []:
        item = dict(row or {})
        row_date = normalize_kline_date_str(item.get("trade_date") or item.get("date"))
        if target and row_date == target:
            item["leading_sectors"] = leading_sectors
        trend_rows.append(item)
    feedback["trend_rows"] = trend_rows
    return feedback


def reconcile_new_high_feedback_identity(feedback, stock_info_map, *, target_date):
    if not isinstance(feedback, dict):
        return feedback, new_high_feedback_identity_check(feedback)
    patched = dict(feedback)
    info_by_code = _stock_info_map_by_code(stock_info_map)
    stocks = []
    for row in feedback.get("top_stocks") or []:
        if not isinstance(row, dict):
            continue
        stock = dict(row)
        code = _clean_code(stock.get("code") or stock.get("stock_code") or stock.get("ts_code"))
        info = info_by_code.get(code) or {}
        identity_patched = False
        if _stock_info_matches_target_date(info, target_date):
            if is_missing_new_high_name(stock.get("name") or stock.get("名称"), code):
                name = _stock_info_name(info)
                if not is_missing_new_high_name(name, code):
                    stock["name"] = name
                    identity_patched = True
            if is_missing_new_high_sector(
                stock.get("sector") or stock.get("industry") or stock.get("所属行业") or stock.get("所属板块")
            ):
                sector = _stock_info_sector(info)
                if sector:
                    stock["sector"] = sector
                    identity_patched = True
            if identity_patched:
                for key in ("identity_source_date", "identity_source"):
                    value = _clean_text(info.get(key))
                    if value:
                        stock[key] = value
        stocks.append(stock)
    patched["top_stocks"] = stocks
    identity = new_high_feedback_identity_check(patched)
    patched["identity_check"] = identity
    if identity["complete"]:
        _refresh_new_high_feedback_aggregates(patched, stocks, target_date)
    return patched, identity


def _quote_lookup_key_map(rows):
    mapped = {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        keys = []
        for key in ("stock_code", "code", "代码", "ts_code"):
            value = str(row.get(key) or "").strip()
            if not value:
                continue
            keys.append(value.upper())
            keys.append(_clean_code(value))
        for key in keys:
            if key:
                mapped[key] = row
    return mapped


def _pct(value, denominator):
    denominator = _safe_float(denominator)
    if denominator <= 0:
        return 0.0
    return _safe_float(value) / denominator * 100.0


def _format_pct(value):
    return f"{_safe_float(value):.2f}%"


def _leading_sector_text(sector_rows, limit=3):
    names = [
        _valid_sector(row.get("sector"))
        for row in (sector_rows or [])
        if isinstance(row, dict) and _valid_sector(row.get("sector"))
    ][:limit]
    return "、".join(names) if names else "无阶段新高"


def _trend_leading_sector_text(row):
    count = _safe_int((row or {}).get("new_high_count"), 0)
    leading = _clean_text((row or {}).get("leading_sectors"))
    if count <= 0:
        return "无阶段新高"
    if (
        leading == "无阶段新高"
        or is_missing_new_high_sector(leading)
        or _contains_serialized_missing_text(leading)
    ):
        return "缺少逐股板块映射"
    return leading


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
        if is_missing_new_high_sector(item.get("leading_sectors")) or _contains_serialized_missing_text(
            item.get("leading_sectors")
        ):
            item["leading_sectors"] = _leading_sector_text(item.get("sector_distribution") or [])
        item["leading_sectors"] = _trend_leading_sector_text(item)
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
    quote_rows=None,
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
        "insufficient_stock_history": 0,
        "missing_code": 0,
    }
    stocks = []
    quote_map = _quote_lookup_key_map(quote_rows)
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
        name = _clean_text(row.get("name")) or _clean_text(basic.get("name"))
        if _is_st_or_risk(name, code, stock_risk_map):
            excluded_counts["st_or_risk"] += 1
            continue
        if _has_explicit_new_stock_name(name) or _is_new_or_recent(
            basic.get("list_date"),
            target_date or row.get("trade_date"),
            recent_listing_days,
        ):
            excluded_counts["new_or_recent"] += 1
            continue
        if (
            "history_trade_days" in row
            and _safe_int(row.get("history_trade_days"), -1)
            < _required_previous_trade_days(topdays_threshold)
        ):
            excluded_counts["insufficient_stock_history"] += 1
            continue
        quote = quote_map.get(code) or quote_map.get(ts_code)
        sector = ""
        for source_row in (basic, row, quote or {}):
            for sector_key in ("industry", "sector", "所属行业", "所属板块", "板块", "行业"):
                sector = _valid_sector((source_row or {}).get(sector_key))
                if sector:
                    break
            if sector:
                break
        sector = sector or "待补充板块"
        amount_yi = _amount_yi(row)
        quote_amount = _amount_yi(quote or {})
        if amount_yi <= 0 and quote_amount > 0:
            amount_yi = quote_amount
        stock = {
            "code": code,
            "ts_code": ts_code,
            "name": name or _clean_text((quote or {}).get("name")) or _clean_text((quote or {}).get("stock_name")) or code,
            "sector": sector or "待补充板块",
            "close": _safe_float(row.get("close") or (quote or {}).get("close")),
            "high": _safe_float(row.get("high") or (quote or {}).get("high")),
            "pct_chg": round(_safe_float(row.get("pct_chg") or row.get("pct_change") or (quote or {}).get("pct_chg")), 2),
            "amount_yi": amount_yi,
            "topdays": _safe_int(row.get("topdays")),
        }
        if "history_trade_days" in row:
            stock["history_trade_days"] = _safe_int(row.get("history_trade_days"))
        stocks.append(stock)

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
