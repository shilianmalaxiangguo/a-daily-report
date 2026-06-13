from __future__ import annotations

import datetime
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

from domains.market_activity.new_high_runtime import build_new_high_feedback_snapshot
from domains.market_state.margin_pressure_runtime import build_margin_pressure_snapshot
from market_data.kline_dates import normalize_kline_date_str
from market_data.tushare_service import fetch_daily_price_bars
from market_data.tushare_market_activity_service import (
    fetch_cyberfininvest_news_rows,
    fetch_investor_qa_rows,
    fetch_tushare_announcement_rows,
    fetch_tushare_holdertrade_rows,
    fetch_tushare_limit_rows,
    fetch_tushare_new_share,
    fetch_tushare_open_trade_dates,
    fetch_tushare_sector_flow,
    fetch_tushare_shock_rows,
    fetch_tushare_st_rows,
    fetch_tushare_stock_st_rows,
    fetch_tushare_ths_daily,
    fetch_tushare_ths_hot,
    fetch_tushare_ths_index_map,
    fetch_tushare_ths_member,
    fetch_tushare_top_list,
)
from market_data.tushare_turnover_service import (
    fetch_market_daily_amount_rows,
    fetch_market_index_amount_rows,
    fetch_market_margin_balance_rows,
    fetch_margin_balance_rows,
    fetch_stock_basic_map,
    fetch_stock_daily_turnover_records,
    fetch_stock_factor_pro_rows,
    fetch_stock_industry_map,
    fetch_stock_moneyflow_map,
    fetch_stock_name_map,
)

__all__ = [
    "ProviderValue",
    "get_total_turnover_from_tushare_first",
    "get_major_indices_from_tushare_first",
    "get_wind_a_from_tushare_first",
    "get_csi1000_from_tushare_first",
    "get_turnover_rank_from_tushare_first",
    "get_stock_hot_rank_from_tushare_first",
    "get_limit_pool_snapshot_from_tushare_first",
    "get_sector_hot_plates_from_tushare_first",
    "get_hot_concept_fund_flow_from_tushare_first",
    "get_sector_change_rank_from_tushare_first",
    "get_sector_fund_flow_from_tushare_first",
    "get_lhb_snapshot_from_tushare_first",
    "get_new_stock_calendar_from_tushare_first",
    "get_stock_risk_map_from_tushare_first",
    "get_new_high_feedback_from_tushare_first",
    "get_top50_turnover_share_series_from_tushare_first",
    "get_etf_turnover_series_from_sina_first",
    "get_price_band_style_series_from_tushare_first",
    "get_margin_pressure_from_tushare_first",
]


class ProviderValue(float):
    def __new__(
        cls,
        value,
        *,
        data_source="",
        source_endpoint="",
        source_row_count=0,
        source_retry_count=0,
    ):
        obj = float.__new__(cls, value)
        obj.data_source = data_source
        obj.source_endpoint = source_endpoint
        obj.source_row_count = source_row_count
        obj.source_retry_count = source_retry_count
        return obj


def _create_fact_database_service(database_service_cls=None, db_path=None):
    if database_service_cls is None:
        try:
            from storage.database_service import DatabaseService
        except Exception:  # pragma: no cover - optional runtime dependency
            DatabaseService = None
        database_service_cls = DatabaseService
    if database_service_cls is None:
        return None
    factory = getattr(database_service_cls, "fact_store_from_environment", None)
    if callable(factory):
        service = factory(db_path)
        if getattr(service, "repository", object()) is None:
            return None
        return service
    factory = getattr(database_service_cls, "from_environment", None)
    if callable(factory):
        service = factory(db_path)
        if getattr(service, "repository", object()) is None:
            return None
        return service
    return None


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
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


def _market_from_code(code):
    code = str(code or "").strip()
    if code.startswith(("6", "5", "9")):
        return "sh"
    if code.startswith(("8", "4")) or code.startswith("92"):
        return "bj"
    return "sz" if code else ""


def _normalize_time_text(value):
    text = str(value or "").strip()
    if not text:
        return ""
    if ":" in text:
        parts = text.split(":")
        if len(parts) == 2:
            return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}:00"
        if len(parts) >= 3:
            return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}:{parts[2].zfill(2)}"
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) >= 6:
        return f"{digits[:2]}:{digits[2:4]}:{digits[4:6]}"
    if len(digits) == 4:
        return f"{digits[:2]}:{digits[2:4]}:00"
    return text


def _parse_date(value):
    text = normalize_kline_date_str(value)
    if not text:
        return None
    try:
        return datetime.datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


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


def _subscription_window(days_to_subscription, subscription_date, next_trade_date):
    if days_to_subscription is None:
        return "missing_subscription_date"
    if subscription_date and next_trade_date and subscription_date == next_trade_date:
        return "next_trade_day_subscription"
    if days_to_subscription == 0:
        return "today_subscription"
    if days_to_subscription == 1:
        return "tomorrow_subscription"
    if 2 <= days_to_subscription <= 31:
        return "upcoming_subscription"
    if -7 <= days_to_subscription <= -1:
        return "recently_subscribed"
    return "outside_subscription_window"


def _pick(row, *keys, default=""):
    for key in keys:
        value = (row or {}).get(key)
        if value not in (None, "") and _clean_text(value):
            return value
    return default


def _clean_text(value):
    try:
        if value != value:
            return ""
    except Exception:
        pass
    text = str(value or "").strip()
    return "" if text.lower() == "nan" else text


_NON_SECTOR_LABELS = {
    "HS",
    "GEM",
    "STAR",
    "BJ",
    "SH",
    "SZ",
    "沪深",
    "创业板",
    "科创板",
    "北交所",
    "未知",
    "未归类",
    "其他",
    "其它",
    "-",
}


def _is_valid_sector_label(value):
    label = str(value or "").strip()
    return bool(label and label not in _NON_SECTOR_LABELS)


def _normalize_concepts(value):
    try:
        if value != value:
            return []
    except Exception:
        pass
    if isinstance(value, (list, tuple, set)):
        return [_clean_text(item) for item in value if _clean_text(item)]
    text = _clean_text(value)
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError):
        parsed = None
    if isinstance(parsed, (list, tuple, set)):
        return [_clean_text(item) for item in parsed if _clean_text(item)]
    return [_clean_text(item.strip().strip('"').strip("'")) for item in text.replace(";", ",").split(",") if _clean_text(item.strip().strip('"').strip("'"))]


def _is_limit_up_row(row):
    text = str(
        _pick(
            row,
            "limit",
            "limit_type",
            "status",
            "tag",
            "data_type",
            default="",
        )
        or ""
    )
    return text.upper() in {"U", "UP"} or "涨停" in text


def _is_limit_down_row(row):
    text = str(
        _pick(
            row,
            "limit",
            "limit_type",
            "status",
            "tag",
            "data_type",
            default="",
        )
        or ""
    )
    return text.upper() in {"D", "DOWN"} or "跌停" in text


def _is_new_high_hot_row(row):
    is_new = str((row or {}).get("is_new") or "").strip().upper()
    if is_new and is_new != "Y":
        return False
    market = str((row or {}).get("market") or (row or {}).get("data_type") or "").strip()
    return not market or market == "热股" or "热股" in market


def _resolve_query_date(target_date=None):
    if target_date:
        if isinstance(target_date, str):
            return datetime.datetime.strptime(target_date, "%Y-%m-%d")
        return target_date
    return datetime.datetime.now()


def _fallback_call(fn, target_date):
    if not callable(fn):
        return None
    return fn(target_date=target_date)


def _fetch_turnover_rows_with_retry(fetcher, target_date, retry_count=1):
    attempts = max(int(retry_count or 0), 0) + 1
    last_rows = []
    for attempt in range(attempts):
        rows = fetcher(target_date) or []
        last_rows = rows
        if rows:
            return rows, attempt
    return last_rows, attempts - 1


def _build_new_high_snapshot_from_fact_rows(rows, target_date, *, source=""):
    target_date_text = normalize_kline_date_str(target_date) or str(target_date or "").strip()
    fact_rows = []
    for row in rows or []:
        item = dict(row or {})
        trade_date = normalize_kline_date_str(item.get("trade_date") or item.get("date"))
        if not trade_date:
            continue
        item["trade_date"] = trade_date
        item["new_high_count"] = _safe_int(item.get("new_high_count"), 0)
        item["all_a_share_pct"] = round(_safe_float(item.get("all_a_share_pct")), 2)
        item["leading_sectors"] = _clean_text(item.get("leading_sectors"))
        fact_rows.append(item)
    fact_rows = sorted(fact_rows, key=lambda item: item.get("trade_date") or "")
    target_row = next((row for row in fact_rows if row.get("trade_date") == target_date_text), None)
    if not target_row or _safe_int(target_row.get("new_high_count"), 0) <= 0:
        return {}
    previous_count = None
    trend_rows = []
    for row in fact_rows:
        current_count = _safe_int(row.get("new_high_count"), 0)
        item = dict(row)
        if previous_count is None:
            item["change_text"] = item.get("change_text") or "待累计"
        else:
            existing_change = str(item.get("change_text") or "").strip()
            item["change_text"] = existing_change if existing_change and existing_change != "待累计" else f"{current_count - previous_count:+d}"
        previous_count = current_count
        trend_rows.append(item)
    data_source = source or target_row.get("source") or target_row.get("source_policy") or "storage.new_high_feedback_daily"
    leading_sectors = target_row.get("leading_sectors") or "待补充板块"
    count = _safe_int(target_row.get("new_high_count"), 0)
    share_pct = round(_safe_float(target_row.get("all_a_share_pct")), 2)
    return {
        "available": True,
        "status": "success",
        "source": data_source,
        "new_high_count": count,
        "all_a_share_pct": share_pct,
        "leading_sectors": leading_sectors,
        "summary": f"本地事实库记录显示阶段新高 {count} 只，占全A约 {share_pct:.2f}%，主要集中在 {leading_sectors}。",
        "sector_distribution": target_row.get("sector_distribution") or [],
        "top_stocks": target_row.get("top_stocks") or [],
        "trend_rows": trend_rows[-25:],
        "excluded_counts": {},
    }


def get_total_turnover_from_tushare_first(
    target_date=None,
    *,
    fetch_stock_daily_turnover_records_fn=None,
    legacy_get_total_turnover_fn=None,
    db_path=None,
    database_service_cls=None,
):
    fetcher = fetch_stock_daily_turnover_records_fn or fetch_stock_daily_turnover_records
    retry_count = 0
    try:
        rows, retry_count = _fetch_turnover_rows_with_retry(fetcher, target_date)
        total = sum(_safe_float((row or {}).get("amount_yi")) for row in (rows or []))
        if total > 0:
            return ProviderValue(
                round(total, 2),
                data_source="tushare.daily",
                source_endpoint="daily",
                source_row_count=len(rows or []),
                source_retry_count=retry_count,
            )
    except Exception:
        pass

    fallback = _fallback_call(legacy_get_total_turnover_fn, target_date)
    fallback_value = _safe_float(fallback)
    if fallback_value > 0:
        return ProviderValue(
            fallback_value,
            data_source="legacy.total_turnover",
            source_endpoint="fallback",
            source_row_count=0,
            source_retry_count=retry_count,
        )

    try:
        service = _create_fact_database_service(database_service_cls, db_path)
        row = service.query_market_daily_total(normalize_kline_date_str(target_date) or target_date, market_scope="all_a")
        local_total = _safe_float((row or {}).get("total_amount_yi", (row or {}).get("total_turnover_yi")))
        if local_total > 0:
            return ProviderValue(
                round(local_total, 2),
                data_source="storage.market_daily_totals",
                source_endpoint="market_daily_totals",
                source_row_count=_safe_int((row or {}).get("stock_count"), 0),
                source_retry_count=retry_count,
            )
    except Exception:
        pass

    return ProviderValue(
        fallback_value,
        data_source="legacy.total_turnover",
        source_endpoint="fallback",
        source_row_count=0,
        source_retry_count=retry_count,
    )


def _lookup_by_code(mapping, row, default=""):
    stock_code = str((row or {}).get("stock_code") or "").strip()
    ts_code = str((row or {}).get("ts_code") or "").strip().upper()
    value = (mapping or {}).get(stock_code)
    if value in (None, ""):
        value = (mapping or {}).get(ts_code)
    return str(value or default).strip()


def _append_stock_risk_event(risk_map, code, *, flag, title, source, event=None, summary_parts=None):
    code = _clean_code(code)
    if not code:
        return
    bucket = risk_map.setdefault(
        code,
        {
            "code": code,
            "risk_flags": [],
            "risk_events": [],
            "source_endpoints": [],
            "risk_summary": "",
        },
    )
    if flag and flag not in bucket["risk_flags"]:
        bucket["risk_flags"].append(flag)
    if source and source not in bucket["source_endpoints"]:
        bucket["source_endpoints"].append(source)
    event_payload = {
        "risk_type": flag,
        "title": _clean_text(title),
        "source": source,
    }
    if isinstance(event, dict):
        for key in ("ann_date", "pub_date", "imp_date", "trade_date", "url", "holder_name", "change_ratio", "reason"):
            value = event.get(key)
            if value not in (None, ""):
                event_payload[key] = value
    if event_payload["title"] and event_payload not in bucket["risk_events"]:
        bucket["risk_events"].append(event_payload)
    parts = list(summary_parts or [])
    if event_payload["title"]:
        parts.append(event_payload["title"])
    existing = [part.strip() for part in str(bucket.get("risk_summary") or "").split("；") if part.strip()]
    for part in parts:
        text = _clean_text(part)
        if text and text not in existing:
            existing.append(text)
    bucket["risk_summary"] = "；".join(existing)


def _announcement_risk_type(title):
    text = str(title or "")
    if any(marker in text for marker in ("退市整理期", "终止上市", "强制退市")):
        return "delist_risk"
    if any(marker in text for marker in ("退市风险警示", "其他风险警示", "实施风险警示", "ST")):
        return "risk_warning"
    if "减持" in text:
        return "holder_reduce_announcement"
    if any(marker in text for marker in ("异常波动", "风险提示公告", "股票交易异常", "停牌核查")):
        return "abnormal_volatility"
    if any(marker in text for marker in ("立案", "监管函", "问询函", "处罚", "重大违法")):
        return "regulatory_investigation"
    return ""


def _date_distance_days(date_value, target_date):
    parsed_date = _parse_date(date_value)
    parsed_target = _parse_date(target_date)
    if not parsed_date or not parsed_target:
        return None
    return abs((parsed_target - parsed_date).days)


def _is_recent_st_row(row, target_date, *, max_days=30):
    for key in ("imp_date", "pub_date", "trade_date"):
        distance = _date_distance_days((row or {}).get(key), target_date)
        if distance is not None and distance <= max_days:
            return True
    return False


def _iter_cyberfininvest_stock_codes(row):
    for stock in (row or {}).get("stocks") or []:
        if isinstance(stock, dict):
            code = _clean_code(stock.get("code"))
            if code:
                yield code


def _is_recent_cyberfininvest_news_row(row, target_date, *, max_days_back=1):
    parsed_target = _parse_date(target_date)
    if not parsed_target:
        return True
    for key in ("createTime", "updateTime", "pub_date", "ann_date"):
        parsed_date = _parse_date((row or {}).get(key))
        if not parsed_date:
            continue
        delta = (parsed_target - parsed_date).days
        return 0 <= delta <= max_days_back
    return True


def _merge_cyberfininvest_news_risks(risk_map, rows, target_date=None):
    for row in rows or []:
        if not _is_recent_cyberfininvest_news_row(row, target_date):
            continue
        title = _clean_text(_pick(row, "title", default=""))
        summary = _clean_text(_pick(row, "summary", default=""))
        risk_type = _announcement_risk_type(f"{title} {summary}")
        if not risk_type:
            continue
        event = {
            "title": title,
            "reason": summary,
            "url": _pick(row, "appUrl", "url", "pdfUrl", default=""),
            "pub_date": _pick(row, "createTime", "updateTime", default=""),
        }
        for code in _iter_cyberfininvest_stock_codes(row):
            _append_stock_risk_event(
                risk_map,
                code,
                flag=risk_type,
                title=title,
                source="cyberfininvest.news",
                event=event,
                summary_parts=[summary],
            )


_HYPE_EXPECTATION_DOWNGRADE_MARKERS = (
    "尚未与",
    "尚未达成合作",
    "未达成合作",
    "没有合作",
    "暂无合作",
    "无合作",
    "未开展业务合作",
    "无相关规划",
    "暂无相关规划",
    "无重组计划",
    "无相关业务",
    "业务占比较小",
    "占比较小",
    "占比很小",
    "尚未形成营业收入",
    "未形成营业收入",
    "尚未产生营业收入",
    "未产生营业收入",
    "尚未形成利润",
    "未形成利润",
    "尚未产生利润",
    "未产生利润",
    "尚未量产",
    "未量产",
    "尚未完成交付",
    "未完成交付",
    "距离批量化生产还需要较长周期",
    "传闻不实",
    "不属实",
)


def _is_hype_expectation_downgrade_row(row):
    text = " ".join(
        _clean_text(_pick(row, key, default=""))
        for key in ("title", "question", "answer", "summary", "content", "reply")
    )
    return any(marker in text for marker in _HYPE_EXPECTATION_DOWNGRADE_MARKERS)


def _merge_investor_qa_risks(risk_map, rows):
    for row in rows or []:
        if not _is_hype_expectation_downgrade_row(row):
            continue
        title = _clean_text(_pick(row, "title", "question", default="投资者问答澄清"))
        answer = _clean_text(_pick(row, "answer", "summary", "content", "reply", default=""))
        source = _clean_text(_pick(row, "source", default="investor_qa")) or "investor_qa"
        event = {
            "title": title,
            "reason": answer,
            "url": _pick(row, "url", "link", default=""),
            "pub_date": _pick(row, "pub_date", "ann_date", "trade_date", "datetime", default=""),
        }
        _append_stock_risk_event(
            risk_map,
            _pick(row, "ts_code", "code", "stock_code", default=""),
            flag="hype_expectation_downgrade",
            title=title,
            source=source,
            event=event,
            summary_parts=[answer],
        )
        code = _clean_code(_pick(row, "ts_code", "code", "stock_code", default=""))
        if code and "investor_qa" not in risk_map[code]["source_endpoints"]:
            risk_map[code]["source_endpoints"].append("investor_qa")


def get_stock_risk_map_from_tushare_first(
    target_date=None,
    *,
    fetch_tushare_st_rows_fn=None,
    fetch_tushare_stock_st_rows_fn=None,
    fetch_tushare_holdertrade_rows_fn=None,
    fetch_tushare_announcement_rows_fn=None,
    fetch_tushare_shock_rows_fn=None,
    fetch_cyberfininvest_news_rows_fn=None,
    fetch_investor_qa_rows_fn=None,
):
    risk_map = {}

    st_fetcher = fetch_tushare_st_rows_fn or fetch_tushare_st_rows
    stock_st_fetcher = fetch_tushare_stock_st_rows_fn or fetch_tushare_stock_st_rows
    holder_fetcher = fetch_tushare_holdertrade_rows_fn or fetch_tushare_holdertrade_rows
    announcement_fetcher = fetch_tushare_announcement_rows_fn or fetch_tushare_announcement_rows
    shock_fetcher = fetch_tushare_shock_rows_fn or fetch_tushare_shock_rows
    injected_primary_fetcher = any(
        fn is not None
        for fn in (
            fetch_tushare_st_rows_fn,
            fetch_tushare_stock_st_rows_fn,
            fetch_tushare_holdertrade_rows_fn,
            fetch_tushare_announcement_rows_fn,
            fetch_tushare_shock_rows_fn,
        )
    )
    if fetch_cyberfininvest_news_rows_fn is not None:
        cyber_news_fetcher = fetch_cyberfininvest_news_rows_fn
    elif injected_primary_fetcher:
        cyber_news_fetcher = lambda trade_date: []
    else:
        cyber_news_fetcher = fetch_cyberfininvest_news_rows
    investor_qa_fetcher = fetch_investor_qa_rows_fn or fetch_investor_qa_rows

    try:
        for row in st_fetcher(target_date) or []:
            if not _is_recent_st_row(row, target_date):
                continue
            title = _clean_text(_pick(row, "st_reason", "st_explain", default="实施其他风险警示"))
            _append_stock_risk_event(
                risk_map,
                _pick(row, "ts_code", "code", default=""),
                flag="st_warning",
                title=title or "实施其他风险警示",
                source="tushare.st",
                event=row,
                summary_parts=[_pick(row, "st_reason", default=""), _pick(row, "st_explain", default="")],
            )
    except Exception:
        pass

    try:
        for row in stock_st_fetcher(target_date) or []:
            _append_stock_risk_event(
                risk_map,
                _pick(row, "ts_code", "code", default=""),
                flag="stock_st",
                title="交易日ST名单",
                source="tushare.stock_st",
                event=row,
                summary_parts=["交易日ST名单"],
            )
    except Exception:
        pass

    try:
        for row in holder_fetcher(target_date) or []:
            trade_type = str(_pick(row, "trade_type", "in_de", default="")).strip().upper()
            title = f"{_clean_text(_pick(row, 'holder_name', default='股东'))}减持"
            if trade_type and trade_type != "DE" and "减" not in trade_type:
                continue
            _append_stock_risk_event(
                risk_map,
                _pick(row, "ts_code", "code", default=""),
                flag="holder_reduce",
                title=title,
                source="tushare.stk_holdertrade",
                event=row,
                summary_parts=[title],
            )
    except Exception:
        pass

    try:
        for row in announcement_fetcher(target_date) or []:
            title = _clean_text(_pick(row, "title", default=""))
            risk_type = _announcement_risk_type(title)
            if not risk_type:
                continue
            _append_stock_risk_event(
                risk_map,
                _pick(row, "ts_code", "code", default=""),
                flag=risk_type,
                title=title,
                source="tushare.anns_d",
                event=row,
                summary_parts=[title],
            )
    except Exception:
        pass

    try:
        for row in shock_fetcher(target_date) or []:
            title = _clean_text(_pick(row, "type", "reason", default="股票交易异常波动"))
            _append_stock_risk_event(
                risk_map,
                _pick(row, "ts_code", "code", default=""),
                flag="abnormal_volatility",
                title=title or "股票交易异常波动",
                source="tushare.stk_shock",
                event=row,
                summary_parts=[title, _pick(row, "reason", default="")],
            )
    except Exception:
        pass

    try:
        _merge_cyberfininvest_news_risks(risk_map, cyber_news_fetcher(target_date) or [], target_date=target_date)
    except Exception:
        pass

    try:
        if callable(investor_qa_fetcher):
            try:
                qa_rows = investor_qa_fetcher(target_date, lookback_trade_days=10) or []
            except TypeError:
                qa_rows = investor_qa_fetcher(target_date) or []
            _merge_investor_qa_risks(risk_map, qa_rows)
    except Exception:
        pass

    return risk_map


def get_new_high_feedback_from_tushare_first(
    target_date=None,
    *,
    pro=None,
    fetch_stock_factor_pro_rows_fn=None,
    fetch_stock_basic_map_fn=None,
    fetch_stock_risk_map_fn=None,
    fetch_tushare_open_trade_dates_fn=None,
    stock_risk_map=None,
    history_rows=None,
    db_path=None,
    database_service_cls=None,
    ensure_daily_metric_history_index_fn=None,
):
    factor_fetcher = fetch_stock_factor_pro_rows_fn or fetch_stock_factor_pro_rows
    basic_fetcher = fetch_stock_basic_map_fn or fetch_stock_basic_map
    target_date_text = normalize_kline_date_str(target_date)

    def _fetch_factor_rows(trade_date):
        if pro is not None:
            return factor_fetcher(trade_date, pro=pro) or []
        return factor_fetcher(trade_date) or []

    factor_trade_date = target_date_text or target_date
    factor_error = None
    try:
        factor_rows = _fetch_factor_rows(factor_trade_date)
    except Exception as error:
        factor_rows = []
        factor_error = error
    try:
        stock_basic_map = basic_fetcher() if callable(basic_fetcher) else {}
    except TypeError:
        stock_basic_map = basic_fetcher(pro=pro) if callable(basic_fetcher) and pro is not None else {}
    if stock_risk_map is None:
        risk_fetcher = fetch_stock_risk_map_fn or get_stock_risk_map_from_tushare_first
        try:
            stock_risk_map = risk_fetcher(target_date_text or factor_trade_date) if callable(risk_fetcher) else {}
        except TypeError:
            stock_risk_map = risk_fetcher(target_date=target_date_text or factor_trade_date) if callable(risk_fetcher) else {}
        except Exception:
            stock_risk_map = {}
    local_service = None
    local_service = _create_fact_database_service(database_service_cls, db_path)
    if local_service is not None:
        try:
            getattr(local_service, "repository", object())
        except Exception:
            local_service = None
    if not factor_rows and local_service is not None:
        try:
            raw_history_rows = local_service.query_new_high_feedback_series(
                target_date_text or factor_trade_date,
                window_days=25,
            )
            fact_snapshot = _build_new_high_snapshot_from_fact_rows(
                raw_history_rows,
                target_date_text or factor_trade_date,
            )
            if fact_snapshot:
                if factor_error is not None:
                    fact_snapshot.setdefault("factor_error", str(factor_error))
                fact_snapshot.setdefault("requested_trade_date", target_date_text)
                fact_snapshot.setdefault("factor_trade_date", factor_trade_date)
                return fact_snapshot
            history_rows = [
                row for row in (raw_history_rows or [])
                if str((row or {}).get("trade_date") or (row or {}).get("date") or "").strip()
                < str(target_date_text or factor_trade_date)
            ]
            quote_builder = getattr(local_service, "build_new_high_feedback_from_recent_quotes", None)
            if callable(quote_builder):
                rebuilt_snapshot = quote_builder(
                    target_date_text or factor_trade_date,
                    stock_basic_map=stock_basic_map,
                    stock_risk_map=stock_risk_map or {},
                    history_rows=history_rows,
                )
                if isinstance(rebuilt_snapshot, dict) and rebuilt_snapshot.get("available"):
                    rebuilt_snapshot.setdefault("trade_date", target_date_text or factor_trade_date)
                    rebuilt_snapshot.setdefault("source_policy", rebuilt_snapshot.get("source"))
                    if factor_error is not None:
                        rebuilt_snapshot.setdefault("factor_error", str(factor_error))
                    upsert_new_high = getattr(local_service, "upsert_new_high_feedback_daily", None)
                    if callable(upsert_new_high):
                        try:
                            upsert_new_high(rebuilt_snapshot)
                        except Exception:
                            pass
                    rebuilt_snapshot.setdefault("requested_trade_date", target_date_text)
                    rebuilt_snapshot.setdefault("factor_trade_date", factor_trade_date)
                    return rebuilt_snapshot
        except Exception:
            pass
    if history_rows is None and factor_rows:
        try:
            history_candidate_dates = None
            date_fetcher = fetch_tushare_open_trade_dates_fn or fetch_tushare_open_trade_dates
            if callable(date_fetcher):
                try:
                    target_dt = datetime.datetime.strptime(
                        target_date_text or factor_trade_date,
                        "%Y-%m-%d",
                    ).date()
                    start_date = (target_dt - datetime.timedelta(days=120)).strftime("%Y-%m-%d")
                    history_candidate_dates = date_fetcher(
                        start_date,
                        target_date_text or factor_trade_date,
                    )
                except Exception:
                    history_candidate_dates = None
            candidate_date_set = {
                str(date or "").strip()
                for date in (history_candidate_dates or [])
                if str(date or "").strip()
            }
            expected_previous_dates = [
                date
                for date in sorted(candidate_date_set)
                if str(date) < str(target_date_text or factor_trade_date)
            ][-24:]
            query_window_days = max(25, len(history_candidate_dates or []), 75 if candidate_date_set else 25)
            service = local_service or _create_fact_database_service(database_service_cls, db_path)
            raw_history_rows = service.query_new_high_feedback_series(
                target_date_text or factor_trade_date,
                window_days=query_window_days,
            ) if service is not None else None
            has_non_trade_history_rows = bool(
                candidate_date_set
                and any(
                    str((row or {}).get("trade_date") or (row or {}).get("date") or "").strip()
                    and str((row or {}).get("trade_date") or (row or {}).get("date") or "").strip() not in candidate_date_set
                    for row in (raw_history_rows or [])
                )
            )
            if raw_history_rows is not None:
                history_rows = [
                    row for row in (raw_history_rows or [])
                    if str((row or {}).get("trade_date") or (row or {}).get("date") or "").strip()
                    < str(target_date_text or factor_trade_date)
                    and (
                        not candidate_date_set
                        or str((row or {}).get("trade_date") or (row or {}).get("date") or "").strip() in candidate_date_set
                    )
                ]
            latest_date = max([str((row or {}).get("trade_date") or "").strip() for row in history_rows or []] or [""])
            previous_target = ""
            try:
                target_dt = datetime.datetime.strptime(target_date_text or factor_trade_date, "%Y-%m-%d").date()
                previous_target = (target_dt - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
            except Exception:
                previous_target = ""
            has_candidate_date_fetcher = bool(candidate_date_set)
            history_date_set = {
                str((row or {}).get("trade_date") or (row or {}).get("date") or "").strip()
                for row in history_rows or []
            }
            missing_expected_trade_dates = bool(
                expected_previous_dates
                and not set(expected_previous_dates).issubset(history_date_set)
            )
            should_rebuild_history = bool(
                previous_target
                and (
                    not latest_date
                    or latest_date < previous_target
                    or (has_candidate_date_fetcher and len(history_rows or []) < 24)
                    or has_non_trade_history_rows
                    or missing_expected_trade_dates
                )
            )
            if should_rebuild_history:
                if ensure_daily_metric_history_index_fn is None:
                    try:
                        from domains.market_state.daily_metric_history_index import ensure_daily_metric_history_index
                    except Exception:  # pragma: no cover - optional runtime dependency
                        ensure_daily_metric_history_index = None
                    ensure_daily_metric_history_index_fn = ensure_daily_metric_history_index
                if callable(ensure_daily_metric_history_index_fn):
                    def _build_new_high_for_history(history_date):
                        rows = _fetch_factor_rows(history_date)
                        return build_new_high_feedback_snapshot(
                            rows,
                            stock_basic_map=stock_basic_map,
                            stock_risk_map=stock_risk_map or {},
                            target_date=history_date,
                        )

                    ensure_daily_metric_history_index_fn(
                        end_date=target_date_text or factor_trade_date,
                        window_days=25,
                        max_scan_days=60,
                        db_path=db_path,
                        database_service_cls=database_service_cls,
                        build_new_high_feedback_fn=_build_new_high_for_history,
                        candidate_dates=history_candidate_dates,
                    )
                    service = _create_fact_database_service(database_service_cls, db_path)
                    if candidate_date_set and service is not None:
                        delete_outside_dates = getattr(service, "delete_new_high_feedback_outside_dates", None)
                        if callable(delete_outside_dates):
                            delete_outside_dates(
                                sorted(candidate_date_set),
                                end_date=target_date_text or factor_trade_date,
                            )
                    raw_history_rows = service.query_new_high_feedback_series(
                        target_date_text or factor_trade_date,
                        window_days=query_window_days,
                    ) if service is not None else history_rows
                    history_rows = [
                        row for row in (raw_history_rows or [])
                        if str((row or {}).get("trade_date") or (row or {}).get("date") or "").strip()
                        < str(target_date_text or factor_trade_date)
                        and (
                            not candidate_date_set
                            or str((row or {}).get("trade_date") or (row or {}).get("date") or "").strip() in candidate_date_set
                        )
                    ]
                    if candidate_date_set:
                        expected_set = set(expected_previous_dates)
                        history_rows = [
                            row
                            for row in history_rows
                            if str((row or {}).get("trade_date") or (row or {}).get("date") or "").strip() in expected_set
                        ] or history_rows[-24:]
        except Exception:
            history_rows = None
    snapshot = build_new_high_feedback_snapshot(
        factor_rows,
        stock_basic_map=stock_basic_map,
        stock_risk_map=stock_risk_map or {},
        target_date=factor_trade_date,
        history_rows=history_rows,
    )
    snapshot.setdefault("requested_trade_date", target_date_text)
    snapshot.setdefault("factor_trade_date", factor_trade_date)
    return snapshot


def get_top50_turnover_share_series_from_tushare_first(
    target_date=None,
    *,
    window_days=25,
    limit=50,
    db_path=None,
    database_service_cls=None,
    fetch_stock_daily_turnover_records_fn=None,
):
    try:
        service = _create_fact_database_service(database_service_cls, db_path)
        query_date = normalize_kline_date_str(target_date) or target_date

        def _query_series():
            return service.query_top_turnover_share_series(
                query_date,
                window_days=window_days,
                limit=limit,
                rank_scope="all_a",
            )

        payload = _query_series()
        rows = (payload or {}).get("rows") if isinstance(payload, dict) else []
        latest_date = normalize_kline_date_str((rows or [{}])[-1].get("trade_date")) if rows else ""
        if query_date and (not latest_date or latest_date < query_date):
            daily_fetcher = fetch_stock_daily_turnover_records_fn or fetch_stock_daily_turnover_records
            daily_rows = daily_fetcher(query_date) or []
            if daily_rows:
                run_id = service.save_provider_source_run(
                    {
                        "trade_date": query_date,
                        "provider": "tushare",
                        "endpoint": "daily",
                        "status": "success",
                        "row_count": len(daily_rows),
                    }
                )
                service.upsert_stock_daily_quotes_recent(daily_rows, source_run_id=run_id)
                service.rebuild_market_daily_total(query_date, source_run_id=run_id)
                service.rebuild_turnover_rank_daily(
                    query_date,
                    rank_limit=max(int(limit or 50), 100),
                    source_run_id=run_id,
                    rank_scope="all_a",
                )
                payload = _query_series()
    except Exception:
        payload = {"rows": []}
    if not isinstance(payload, dict):
        payload = {"rows": []}
    payload.setdefault("source", "storage.turnover_rank_daily")
    return payload


def _sina_etf_symbol(code):
    clean = _clean_code(code)
    if not clean:
        return ""
    market = _market_from_code(clean)
    if market == "bj":
        return ""
    return f"{market}{clean}" if market else ""


def _sina_etf_amount_yi(value):
    amount = _safe_float(value)
    if amount <= 0:
        return 0.0
    return amount / 100_000_000


def _extract_sina_etf_universe_symbol(row):
    for key in ("symbol", "代码", "code", "基金代码", "fund_code"):
        value = (row or {}).get(key)
        symbol = _sina_etf_symbol(value)
        if symbol:
            return symbol
    return ""


def _fetch_sina_etf_hist_encoded(symbol, *, timeout=10):
    import requests

    url = f"https://finance.sina.com.cn/realstock/company/{symbol}/hisdata_klc2/klc_kl.js"
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    text = response.text or ""
    if "=" not in text:
        return ""
    return text.split("=", 1)[1].split(";", 1)[0].replace('"', "")


def _new_sina_etf_hist_decoder():
    from akshare.fund.fund_etf_sina import hk_js_decode
    from py_mini_racer import MiniRacer

    js_code = MiniRacer()
    js_code.eval(hk_js_decode)
    return js_code


def _decode_sina_etf_hist_rows(encoded_text, decoder):
    encoded_text = str(encoded_text or "").strip()
    if not encoded_text:
        return []
    rows = decoder.call("d", encoded_text)
    return list(rows or [])


def get_etf_turnover_series_from_sina_first(
    target_date=None,
    *,
    window_days=25,
    max_workers=None,
    fetch_etf_universe_fn=None,
    fetch_etf_hist_fn=None,
):
    try:
        injected_hist_fetcher = fetch_etf_hist_fn is not None
        if fetch_etf_universe_fn is None:
            import akshare as ak

            fetch_etf_universe_fn = fetch_etf_universe_fn or (lambda: ak.fund_etf_category_sina(symbol="ETF基金"))

        universe = fetch_etf_universe_fn()
        if hasattr(universe, "to_dict"):
            universe_rows = universe.to_dict("records")
        else:
            universe_rows = list(universe or [])

        target_date_text = normalize_kline_date_str(target_date) or str(target_date or "").strip()
        symbols = []
        seen = set()
        for row in universe_rows:
            symbol = _extract_sina_etf_universe_symbol(row)
            if not symbol or symbol in seen:
                continue
            seen.add(symbol)
            symbols.append(symbol)

        amount_by_date = {}
        count_by_date = {}
        usable_count = 0
        empty_count = 0

        def _recent_hist_rows_from_fetcher(symbol):
            hist = fetch_etf_hist_fn(symbol)
            if hasattr(hist, "to_dict"):
                if hasattr(hist, "__getitem__") and target_date_text:
                    try:
                        dates = hist["date"].astype(str)
                        hist = hist.loc[dates <= target_date_text]
                    except Exception:
                        pass
                if hasattr(hist, "tail"):
                    try:
                        hist = hist.tail(max(int(window_days or 25) + 5, 30))
                    except Exception:
                        pass
                hist_rows = hist.to_dict("records")
            else:
                hist_rows = list(hist or [])
            return symbol, hist_rows

        def _fetch_encoded(symbol):
            return symbol, _fetch_sina_etf_hist_encoded(symbol)

        def _merge_hist_rows(hist_rows):
            if not hist_rows:
                return False
            usable_for_symbol = False
            for row in hist_rows:
                trade_date = normalize_kline_date_str(_pick(row, "trade_date", "date", "日期", default=""))
                if not trade_date:
                    continue
                if target_date_text and trade_date > target_date_text:
                    continue
                amount_yi = _sina_etf_amount_yi(_pick(row, "amount", "成交额", "成交金额", default=0))
                if amount_yi <= 0:
                    continue
                amount_by_date[trade_date] = amount_by_date.get(trade_date, 0.0) + amount_yi
                count_by_date[trade_date] = count_by_date.get(trade_date, 0) + 1
                usable_for_symbol = True
            return usable_for_symbol

        worker_count = max_workers
        if worker_count is None:
            worker_count = 1 if injected_hist_fetcher else 8
        worker_count = max(1, int(worker_count or 1))

        if not injected_hist_fetcher:
            encoded_payloads = []
            if worker_count == 1:
                for symbol in symbols:
                    try:
                        encoded_payloads.append(_fetch_encoded(symbol))
                    except Exception:
                        empty_count += 1
            else:
                with ThreadPoolExecutor(max_workers=worker_count) as executor:
                    futures = [executor.submit(_fetch_encoded, symbol) for symbol in symbols]
                    for future in as_completed(futures):
                        try:
                            encoded_payloads.append(future.result())
                        except Exception:
                            empty_count += 1
            decoder = _new_sina_etf_hist_decoder()
            for _, encoded_text in encoded_payloads:
                try:
                    if _merge_hist_rows(_decode_sina_etf_hist_rows(encoded_text, decoder)):
                        usable_count += 1
                    else:
                        empty_count += 1
                except Exception:
                    empty_count += 1
        elif worker_count == 1:
            for symbol in symbols:
                try:
                    _, hist_rows = _recent_hist_rows_from_fetcher(symbol)
                    if _merge_hist_rows(hist_rows):
                        usable_count += 1
                    else:
                        empty_count += 1
                except Exception:
                    empty_count += 1
        else:
            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                futures = [executor.submit(_recent_hist_rows_from_fetcher, symbol) for symbol in symbols]
                for future in as_completed(futures):
                    try:
                        _, hist_rows = future.result()
                        if _merge_hist_rows(hist_rows):
                            usable_count += 1
                        else:
                            empty_count += 1
                    except Exception:
                        empty_count += 1

        previous_amount = None
        rows = []
        for trade_date in sorted(amount_by_date)[-int(window_days or 25):]:
            amount = round(amount_by_date.get(trade_date, 0.0), 2)
            change_pct = "待累计" if previous_amount in (None, 0) else round((amount / previous_amount - 1) * 100, 2)
            rows.append(
                {
                    "trade_date": trade_date,
                    "etf_turnover_yi": amount,
                    "change_pct": change_pct,
                    "covered_etf_count": count_by_date.get(trade_date, 0),
                }
            )
            previous_amount = amount

        return {
            "available": bool(rows),
            "source": "sina.etf.daily_amount",
            "requested_trade_date": target_date_text,
            "usable_etf_count": usable_count,
            "empty_etf_count": empty_count,
            "rows": rows,
        }
    except Exception as error:
        return {
            "available": False,
            "source": "sina.etf.daily_amount",
            "requested_trade_date": normalize_kline_date_str(target_date) or str(target_date or "").strip(),
            "error": str(error),
            "rows": [],
        }


PRICE_BAND_HIGH_PRICE_CODE = "883916.TI"
PRICE_BAND_LOW_PRICE_CODE = "883960.TI"


def _compact_price_band_code(value):
    text = str(value or "").strip().upper()
    if "." in text:
        text = text.split(".", 1)[0]
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits[:6]


def _price_band_spread_pct(high_pct, low_pct):
    return _safe_float(high_pct) - _safe_float(low_pct)


def _price_band_style_label(spread_pct):
    spread_pct = _safe_float(spread_pct)
    if spread_pct > 2.0:
        return "高潮"
    if spread_pct < -2.0:
        return "冰点"
    return "震荡"


def _extract_price_band_pct(rows, ts_code):
    target = str(ts_code or "").strip().upper()
    clean_target = target.split(".", 1)[0]
    for row in rows or []:
        row_code = str((row or {}).get("ts_code") or (row or {}).get("code") or "").strip().upper()
        if row_code != target and row_code.split(".", 1)[0] != clean_target:
            continue
        return _safe_float(_pick(row, "pct_change", "pct_chg", "change_pct", default=0.0))
    return None


def _ths_history_line_cookie_value():
    from akshare.datasets import get_ths_js
    from py_mini_racer import MiniRacer

    with open(get_ths_js("ths.js"), encoding="utf-8") as handle:
        js_content = handle.read()
    js_code = MiniRacer()
    js_code.eval(js_content)
    return js_code.call("v")


def _parse_ths_price_band_history_rows(text, ts_code):
    from akshare.utils import demjson

    payload_text = str(text or "")
    start = payload_text.find("{")
    if start < 0:
        return []
    payload = demjson.decode(payload_text[start:-1])
    data_text = str((payload or {}).get("data") or "")
    parsed = []
    previous_close = None
    for raw_row in data_text.split(";"):
        fields = raw_row.split(",")
        if len(fields) < 5:
            continue
        trade_date = normalize_kline_date_str(fields[0])
        close = _safe_float(fields[4])
        if not trade_date or close <= 0:
            continue
        pct_change = 0.0
        if previous_close and previous_close > 0:
            pct_change = (close - previous_close) / previous_close * 100
        parsed.append(
            {
                "ts_code": str(ts_code or "").strip().upper(),
                "trade_date": trade_date,
                "close": close,
                "pct_change": pct_change,
                "source": "ths.history_line",
            }
        )
        previous_close = close
    return parsed


def fetch_ths_price_band_history(ts_code, start_date, end_date, *, timeout=10):
    import requests

    code = _compact_price_band_code(ts_code)
    start = normalize_kline_date_str(start_date)
    end = normalize_kline_date_str(end_date)
    if not code or not start or not end:
        return []
    year_start = int(start[:4])
    year_end = int(end[:4])
    cookie_value = _ths_history_line_cookie_value()
    rows = []
    for year in range(year_start, year_end + 1):
        url = f"https://d.10jqka.com.cn/v4/line/bk_{code}/01/{year}.js"
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "http://q.10jqka.com.cn",
            "Host": "d.10jqka.com.cn",
            "Cookie": f"v={cookie_value}",
        }
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        rows.extend(_parse_ths_price_band_history_rows(response.text, ts_code))
    return [
        row for row in rows
        if start <= normalize_kline_date_str(row.get("trade_date")) <= end
    ]


def _price_band_history_pct_by_date(fetcher, ts_code, start_date, end_date):
    if not callable(fetcher):
        return {}
    rows = fetcher(ts_code, start_date, end_date) or []
    result = {}
    for row in rows or []:
        trade_date = normalize_kline_date_str((row or {}).get("trade_date") or (row or {}).get("date"))
        if not trade_date:
            continue
        result[trade_date] = _safe_float(_pick(row, "pct_change", "pct_chg", "change_pct", default=0.0))
    return result


def _build_price_band_rows_from_history(fetcher, trade_dates, start_date, end_date, *, high_price_code, low_price_code):
    high_by_date = _price_band_history_pct_by_date(fetcher, high_price_code, start_date, end_date)
    low_by_date = _price_band_history_pct_by_date(fetcher, low_price_code, start_date, end_date)
    rows = []
    for trade_date in trade_dates or []:
        if trade_date not in high_by_date or trade_date not in low_by_date:
            continue
        high_pct = high_by_date[trade_date]
        low_pct = low_by_date[trade_date]
        spread_pct = _price_band_spread_pct(high_pct, low_pct)
        rows.append(
            {
                "trade_date": trade_date,
                "high_price_pct": high_pct,
                "low_price_pct": low_pct,
                "spread_pct": spread_pct,
                "style_label": _price_band_style_label(spread_pct),
            }
        )
    return rows


def _save_price_band_style_rows(service, rows, *, source_policy, high_price_code, low_price_code):
    if service is None:
        return
    for row in rows or []:
        try:
            save_run = getattr(service, "save_provider_source_run", None)
            source_run_id = 0
            if callable(save_run):
                source_run_id = save_run(
                    {
                        "trade_date": row.get("trade_date"),
                        "provider": source_policy.split(".", 1)[0],
                        "endpoint": source_policy,
                        "status": "success",
                        "row_count": 2,
                    }
                )
            service.upsert_price_band_style_daily(
                {
                    **dict(row or {}),
                    "high_price_code": high_price_code,
                    "low_price_code": low_price_code,
                    "source_policy": source_policy,
                    "source_run_id": source_run_id,
                }
            )
        except Exception:
            continue


def _build_price_band_style_payload(rows, *, source="tushare.ths_daily.price_band_style"):
    rows = list(rows or [])[-25:]
    for row in rows:
        row["spread_pct"] = _price_band_spread_pct(
            (row or {}).get("high_price_pct"),
            (row or {}).get("low_price_pct"),
        )
        row["style_label"] = _price_band_style_label(row.get("spread_pct"))
        high_pct = _safe_float((row or {}).get("high_price_pct"))
        low_pct = _safe_float((row or {}).get("low_price_pct"))
        if high_pct < 0 and low_pct < 0:
            row["absolute_label"] = "同步回落"
        elif high_pct > 0 and low_pct > 0:
            row["absolute_label"] = "同步修复"
        elif high_pct > 0 and low_pct <= 0:
            row["absolute_label"] = "高价占优"
        elif high_pct <= 0 and low_pct > 0:
            row["absolute_label"] = "低价抗跌"
        else:
            row["absolute_label"] = "待判断"
    high_total = sum(_safe_float((row or {}).get("high_price_pct")) for row in rows)
    low_total = sum(_safe_float((row or {}).get("low_price_pct")) for row in rows)
    spread_total = sum(_safe_float((row or {}).get("spread_pct")) for row in rows)
    latest_row = rows[-1] if rows else {}
    latest_spread = _safe_float((latest_row or {}).get("spread_pct"))
    latest_label = (latest_row or {}).get("style_label") or _price_band_style_label(latest_spread)
    latest_absolute_label = (latest_row or {}).get("absolute_label") or "待判断"
    summary = ""
    if rows:
        summary = (
            f"近{len(rows)}个交易日价格带风格："
            f"最新差值 {latest_spread:+.2f}pct，当前为{latest_label}；"
            f"绝对状态{latest_absolute_label}；"
            f"百元股累计 {high_total:+.2f}%，低价股累计 {low_total:+.2f}%。"
            f"价格带只作风格背景，不单独说明明日走势，明日仍看成交额与核心承接。"
        )
    return {
        "available": bool(rows),
        "source": source,
        "high_price_code": PRICE_BAND_HIGH_PRICE_CODE,
        "low_price_code": PRICE_BAND_LOW_PRICE_CODE,
        "spread_total_pct": spread_total,
        "latest_spread_pct": latest_spread,
        "latest_style_label": latest_label,
        "latest_absolute_label": latest_absolute_label,
        "rows": rows,
        "summary": summary if rows else "价格带风格趋势待累计。",
    }


def _build_recent_price_band_style_payload(rows, *, target_date, source="storage.price_band_style_daily.recent_window", error=""):
    payload = _build_price_band_style_payload(rows, source=source)
    if not payload.get("available"):
        return payload
    latest_row = (payload.get("rows") or [])[-1]
    latest_trade_date = normalize_kline_date_str((latest_row or {}).get("trade_date"))
    payload["requested_trade_date"] = normalize_kline_date_str(target_date) or str(target_date or "").strip()
    payload["latest_trade_date"] = latest_trade_date
    if error:
        payload["refresh_error"] = str(error)
    payload["summary"] = "最近可用窗口（截至{}）：{}".format(
        latest_trade_date or "待确认",
        payload.get("summary") or "价格带风格趋势已生成。",
    )
    return payload


def _latest_price_band_trade_date(rows):
    dates = [
        normalize_kline_date_str((row or {}).get("trade_date"))
        for row in rows or []
        if normalize_kline_date_str((row or {}).get("trade_date"))
    ]
    return max(dates) if dates else ""


def _price_band_recent_window_is_usable(latest_trade_date, target_date, trade_dates=None, *, max_stale_trade_days=1):
    latest = normalize_kline_date_str(latest_trade_date)
    target = normalize_kline_date_str(target_date)
    if not latest or not target:
        return False
    if latest >= target:
        return True
    normalized_trade_dates = sorted(
        {
            normalize_kline_date_str(item)
            for item in trade_dates or []
            if normalize_kline_date_str(item) and normalize_kline_date_str(item) <= target
        }
    )
    latest_dt = _parse_date(latest)
    target_dt = _parse_date(target)
    calendar_gap = (target_dt - latest_dt).days if latest_dt and target_dt else None
    if normalized_trade_dates:
        newer_trade_days = [item for item in normalized_trade_dates if latest < item <= target]
        if len(newer_trade_days) > int(max_stale_trade_days or 1):
            return False
        if latest not in normalized_trade_dates and calendar_gap is not None and calendar_gap > 3:
            return False
        return True
    if calendar_gap is None:
        return False
    return calendar_gap <= 3


def _build_stale_price_band_style_payload(rows, *, target_date, source="storage.price_band_style_daily.recent_window", error=""):
    target = normalize_kline_date_str(target_date) or str(target_date or "").strip()
    latest_trade_date = _latest_price_band_trade_date(rows)
    payload = _build_price_band_style_payload([], source=source)
    payload.update(
        {
            "available": False,
            "status": "stale_recent_window",
            "requested_trade_date": target,
            "latest_trade_date": latest_trade_date,
            "rows": [],
            "summary": (
                f"价格带风格趋势只到 {latest_trade_date or '待确认'}，"
                f"未覆盖 {target or '目标日'} 附近交易日；"
                "关键数据不完整，停止生成。"
            ),
        }
    )
    if error:
        error_text = str(error).strip()
        display_error = error_text.rstrip("。.!！？")
        payload["refresh_error"] = error_text
        payload["summary"] = (
            f"价格带风格趋势只到 {latest_trade_date or '待确认'}，"
            f"未覆盖 {target or '目标日'} 附近交易日；刷新失败：{display_error}。"
            "关键数据不完整，停止生成。"
        )
    return payload


def get_price_band_style_series_from_tushare_first(
    target_date=None,
    *,
    window_days=25,
    fetch_tushare_open_trade_dates_fn=None,
    fetch_tushare_ths_daily_fn=None,
    fetch_ths_price_band_history_fn=None,
    high_price_code=PRICE_BAND_HIGH_PRICE_CODE,
    low_price_code=PRICE_BAND_LOW_PRICE_CODE,
    db_path=None,
    database_service_cls=None,
):
    target_date_text = normalize_kline_date_str(target_date)
    if not target_date_text:
        return _build_price_band_style_payload([])
    service = None
    fact_rows = []
    should_use_fact_db = bool(
        db_path is not None
        or database_service_cls is not None
        or (fetch_tushare_open_trade_dates_fn is None and fetch_tushare_ths_daily_fn is None)
    )
    if should_use_fact_db:
        try:
            service = _create_fact_database_service(database_service_cls, db_path)
            payload = service.query_price_band_style_series(target_date_text, window_days=window_days)
            rows = (payload or {}).get("rows") if isinstance(payload, dict) else []
            fact_rows = list(rows or [])
            latest_date = normalize_kline_date_str((rows or [{}])[-1].get("trade_date")) if rows else ""
            if latest_date >= target_date_text and len(rows) >= max(int(window_days or 25), 1):
                return _build_price_band_style_payload(rows, source=(payload or {}).get("source") or "storage.price_band_style_daily")
        except Exception:
            service = None
            fact_rows = []
    target_dt = _parse_date(target_date_text)
    if not target_dt:
        return _build_price_band_style_payload([])
    start_date = (target_dt - datetime.timedelta(days=90)).strftime("%Y-%m-%d")
    date_fetcher = fetch_tushare_open_trade_dates_fn or fetch_tushare_open_trade_dates
    daily_fetcher = fetch_tushare_ths_daily_fn or fetch_tushare_ths_daily
    history_fetcher = fetch_ths_price_band_history_fn
    if history_fetcher is None and fetch_tushare_ths_daily_fn is None:
        history_fetcher = fetch_ths_price_band_history
    trade_dates = []
    try:
        trade_dates = [
            normalize_kline_date_str(item)
            for item in (date_fetcher(start_date, target_date_text) or [])
        ]
        trade_dates = [item for item in trade_dates if item and item <= target_date_text]
        trade_dates = sorted(set(trade_dates))[-max(int(window_days or 25), 1):]
        rows = []
        existing_dates = set()
        if service is not None:
            try:
                existing_rows = fact_rows
                existing_dates = {
                    normalize_kline_date_str((row or {}).get("trade_date"))
                    for row in existing_rows or []
                    if normalize_kline_date_str((row or {}).get("trade_date"))
                }
            except Exception:
                existing_dates = set()
        refresh_error = ""
        for trade_date in trade_dates:
            if service is not None and trade_date in existing_dates:
                continue
            try:
                daily_rows = daily_fetcher(trade_date) or []
            except Exception as error:
                refresh_error = str(error)
                continue
            high_pct = _extract_price_band_pct(daily_rows, high_price_code)
            low_pct = _extract_price_band_pct(daily_rows, low_price_code)
            if high_pct is None or low_pct is None:
                continue
            spread_pct = _price_band_spread_pct(high_pct, low_pct)
            rows.append(
                {
                    "trade_date": trade_date,
                    "high_price_pct": high_pct,
                    "low_price_pct": low_pct,
                    "spread_pct": spread_pct,
                    "style_label": _price_band_style_label(spread_pct),
                }
            )
            if service is not None:
                source_run_id = service.save_provider_source_run(
                    {
                        "trade_date": trade_date,
                        "provider": "tushare",
                        "endpoint": "ths_daily",
                        "status": "success",
                        "row_count": len(daily_rows),
                    }
                )
                service.upsert_price_band_style_daily(
                    {
                        **rows[-1],
                        "high_price_code": high_price_code,
                        "low_price_code": low_price_code,
                        "source_policy": "tushare.ths_daily.price_band_style",
                        "source_run_id": source_run_id,
                    }
                )
        history_rows = []
        latest_collected_date = _latest_price_band_trade_date(fact_rows + rows)
        if latest_collected_date < target_date_text:
            try:
                missing_trade_dates = [
                    trade_date for trade_date in trade_dates
                    if trade_date not in {
                        *existing_dates,
                        *{
                            normalize_kline_date_str((row or {}).get("trade_date"))
                            for row in rows or []
                            if normalize_kline_date_str((row or {}).get("trade_date"))
                        },
                    }
                ]
                history_rows = _build_price_band_rows_from_history(
                    history_fetcher,
                    missing_trade_dates,
                    start_date,
                    target_date_text,
                    high_price_code=high_price_code,
                    low_price_code=low_price_code,
                )
            except Exception as error:
                if not refresh_error:
                    refresh_error = str(error)
            if history_rows:
                _save_price_band_style_rows(
                    service,
                    history_rows,
                    source_policy="ths.history_line.price_band_style",
                    high_price_code=high_price_code,
                    low_price_code=low_price_code,
                )
                rows.extend(history_rows)
        if service is not None:
            try:
                refreshed = service.query_price_band_style_series(target_date_text, window_days=window_days)
                refreshed_rows = (refreshed or {}).get("rows") if isinstance(refreshed, dict) else []
                if refreshed_rows:
                    refreshed_source = (refreshed or {}).get("source") or "storage.price_band_style_daily"
                    latest_trade_date = _latest_price_band_trade_date(refreshed_rows)
                    if latest_trade_date >= target_date_text:
                        return _build_price_band_style_payload(
                            refreshed_rows,
                            source=refreshed_source,
                        )
                    if _price_band_recent_window_is_usable(latest_trade_date, target_date_text, trade_dates):
                        return _build_recent_price_band_style_payload(
                            refreshed_rows,
                            target_date=target_date_text,
                            source=(
                                "storage.price_band_style_daily.recent_window"
                                if refresh_error
                                else refreshed_source
                            ),
                            error=refresh_error,
                        )
                    return _build_stale_price_band_style_payload(
                        refreshed_rows,
                        target_date=target_date_text,
                        source=refreshed_source,
                        error=refresh_error or "价格带接口未返回目标日附近数据",
                    )
            except Exception:
                pass
        if rows:
            latest_trade_date = _latest_price_band_trade_date(rows)
            source = "ths.history_line.price_band_style" if history_rows and latest_trade_date >= target_date_text else "tushare.ths_daily.price_band_style"
            if latest_trade_date < target_date_text and not _price_band_recent_window_is_usable(latest_trade_date, target_date_text, trade_dates):
                return _build_stale_price_band_style_payload(
                    rows,
                    target_date=target_date_text,
                    source=source,
                    error=refresh_error or "价格带接口未返回目标日附近数据",
                )
            if latest_trade_date < target_date_text:
                return _build_recent_price_band_style_payload(
                    rows,
                    target_date=target_date_text,
                    source=source,
                )
        payload = _build_price_band_style_payload(rows, source="ths.history_line.price_band_style" if history_rows else "tushare.ths_daily.price_band_style")
        if refresh_error and not payload.get("available"):
            payload["error"] = refresh_error
        return payload
    except Exception as error:
        if fact_rows:
            latest_trade_date = _latest_price_band_trade_date(fact_rows)
            if not _price_band_recent_window_is_usable(latest_trade_date, target_date_text, trade_dates):
                return _build_stale_price_band_style_payload(
                    fact_rows,
                    target_date=target_date_text,
                    error=str(error),
                )
            return _build_recent_price_band_style_payload(
                fact_rows,
                target_date=target_date_text,
                error=str(error),
            )
        payload = _build_price_band_style_payload([])
        payload["error"] = str(error)
        return payload


def _merge_margin_and_turnover_rows(margin_rows, amount_rows):
    amount_by_date = {
        normalize_kline_date_str((row or {}).get("trade_date")): row
        for row in amount_rows or []
        if normalize_kline_date_str((row or {}).get("trade_date"))
    }
    rows = []
    for row in margin_rows or []:
        trade_date = normalize_kline_date_str((row or {}).get("trade_date"))
        amount_row = amount_by_date.get(trade_date) or {}
        if not trade_date:
            continue
        item = {
            **dict(row or {}),
            "trade_date": trade_date,
            "market_turnover_yi": _safe_float(amount_row.get("market_turnover_yi")),
            "stock_count": _safe_int(amount_row.get("stock_count")),
            "source_policy": "{}+{}".format(
                (row or {}).get("source_policy") or (row or {}).get("source") or "tushare.margin",
                amount_row.get("source_policy") or "tushare.index_daily.market_amount"
            ),
        }
        rows.append(item)
    return sorted(rows, key=lambda item: item.get("trade_date", ""))


def get_margin_pressure_from_tushare_first(
    target_date=None,
    *,
    window_days=25,
    calibration_days=250,
    pro=None,
    fetch_tushare_open_trade_dates_fn=None,
    fetch_margin_balance_rows_fn=None,
    fetch_market_daily_amount_rows_fn=None,
    fetch_market_index_amount_rows_fn=None,
    fetch_market_margin_balance_rows_fn=None,
    db_path=None,
    database_service_cls=None,
):
    target_date_text = normalize_kline_date_str(target_date)
    if not target_date_text:
        return build_margin_pressure_snapshot([])
    service = None
    should_use_fact_db = bool(
        db_path is not None
        or database_service_cls is not None
        or (
            fetch_margin_balance_rows_fn is None
            and fetch_market_margin_balance_rows_fn is None
            and fetch_market_daily_amount_rows_fn is None
            and fetch_market_index_amount_rows_fn is None
            and fetch_tushare_open_trade_dates_fn is None
        )
    )
    if should_use_fact_db:
        try:
            service = _create_fact_database_service(database_service_cls, db_path)
            payload = service.query_margin_pressure_series(
                target_date_text,
                window_days=max(int(calibration_days or 250), int(window_days or 25)),
            )
            fact_rows = (payload or {}).get("rows") if isinstance(payload, dict) else []
            latest_date = normalize_kline_date_str((fact_rows or [{}])[-1].get("trade_date")) if fact_rows else ""
            if latest_date >= target_date_text and len(fact_rows or []) >= int(window_days or 25):
                fact_snapshot = build_margin_pressure_snapshot(
                    fact_rows,
                    window_days=window_days,
                    calibration_days=calibration_days,
                    target_date=target_date_text,
                )
                if fact_snapshot.get("available") and (
                    latest_date >= target_date_text or len(fact_rows or []) >= int(calibration_days or 250)
                ):
                    return fact_snapshot
        except Exception:
            service = None
    target_dt = _parse_date(target_date_text)
    if not target_dt:
        return build_margin_pressure_snapshot([])
    start_date = (target_dt - datetime.timedelta(days=max(int(calibration_days or 250) * 2, 365))).strftime("%Y-%m-%d")
    date_fetcher = fetch_tushare_open_trade_dates_fn or fetch_tushare_open_trade_dates
    margin_fetcher = fetch_margin_balance_rows_fn or fetch_margin_balance_rows
    amount_fetcher = fetch_market_daily_amount_rows_fn or fetch_market_index_amount_rows_fn or fetch_market_index_amount_rows
    market_margin_fetcher = fetch_market_margin_balance_rows_fn or fetch_market_margin_balance_rows
    try:
        trade_dates = [
            normalize_kline_date_str(item)
            for item in (date_fetcher(start_date, target_date_text) or [])
        ]
        trade_dates = sorted({item for item in trade_dates if item and item <= target_date_text})
        selected_dates = trade_dates[-max(int(calibration_days or 250), int(window_days or 25)) :]
        if not selected_dates:
            return build_margin_pressure_snapshot([])
        start = selected_dates[0]
        end = selected_dates[-1]
        margin_rows = margin_fetcher(start, end, pro=pro) if pro is not None else margin_fetcher(start, end)
        amount_rows = amount_fetcher(start, end, pro=pro) if pro is not None else amount_fetcher(start, end)
        rows = _merge_margin_and_turnover_rows(margin_rows, amount_rows)
        selected_set = set(selected_dates)
        rows = [row for row in rows if row.get("trade_date") in selected_set]
        primary_snapshot = build_margin_pressure_snapshot(
            rows,
            window_days=window_days,
            calibration_days=calibration_days,
            target_date=target_date_text,
        )
        if not primary_snapshot.get("available") and primary_snapshot.get("status") in {"incomplete_exchange_rows", "upstream_empty"}:
            market_margin_rows = market_margin_fetcher(start, end)
            fallback_rows = _merge_margin_and_turnover_rows(market_margin_rows, amount_rows)
            fallback_rows = [row for row in fallback_rows if row.get("trade_date") in selected_set]
            if fallback_rows:
                rows = fallback_rows
        if service is not None:
            try:
                source_run_id = service.save_provider_source_run(
                    {
                        "trade_date": target_date_text,
                        "provider": "tushare",
                        "endpoint": "margin+index_daily",
                        "status": "success",
                        "row_count": len(rows),
                    }
                )
                for row in rows:
                    service.upsert_margin_pressure_daily({**row, "source_run_id": source_run_id})
                refresh_end_date = normalize_kline_date_str((rows or [{}])[-1].get("trade_date")) or target_date_text
                refreshed = service.query_margin_pressure_series(
                    refresh_end_date,
                    window_days=max(int(calibration_days or 250), int(window_days or 25)),
                )
                refreshed_rows = (refreshed or {}).get("rows") if isinstance(refreshed, dict) else []
                refreshed_snapshot = build_margin_pressure_snapshot(
                    refreshed_rows,
                    window_days=window_days,
                    calibration_days=calibration_days,
                    target_date=target_date_text,
                )
                if refreshed_snapshot.get("available"):
                    rows = refreshed_rows
            except Exception:
                pass
        return build_margin_pressure_snapshot(
            rows,
            window_days=window_days,
            calibration_days=calibration_days,
            target_date=target_date_text,
        )
    except Exception as error:
        if service is not None:
            try:
                fallback_payload = service.query_margin_pressure_series(
                    target_date_text,
                    window_days=max(int(calibration_days or 250), int(window_days or 25)),
                )
                fallback_rows = (fallback_payload or {}).get("rows") if isinstance(fallback_payload, dict) else []
                fallback_snapshot = build_margin_pressure_snapshot(
                    fallback_rows,
                    window_days=window_days,
                    calibration_days=calibration_days,
                    target_date=target_date_text,
                )
                if fallback_snapshot.get("available"):
                    fallback_snapshot.setdefault("refresh_error", str(error))
                    return fallback_snapshot
            except Exception:
                pass
        payload = build_margin_pressure_snapshot([])
        payload["error"] = str(error)
        return payload


def get_turnover_rank_from_tushare_first(
    target_date=None,
    *,
    limit=50,
    fetch_stock_daily_turnover_records_fn=None,
    fetch_stock_name_map_fn=None,
    fetch_stock_industry_map_fn=None,
    legacy_get_turnover_rank_fn=None,
    db_path=None,
    database_service_cls=None,
):
    def _load_name_and_industry_maps():
        name_map_loader = fetch_stock_name_map_fn or fetch_stock_name_map
        industry_map_loader = fetch_stock_industry_map_fn or fetch_stock_industry_map
        try:
            name_map = name_map_loader() if callable(name_map_loader) else {}
        except Exception:
            name_map = {}
        try:
            industry_map = industry_map_loader() if callable(industry_map_loader) else {}
        except Exception:
            industry_map = {}
        return name_map, industry_map

    def _ranked_from_rows(rows, *, source):
        rows = [row for row in (rows or []) if _safe_float((row or {}).get("amount_yi")) > 0]
        rows.sort(
            key=lambda row: (
                _safe_int((row or {}).get("rank_no"), 0) if _safe_int((row or {}).get("rank_no"), 0) > 0 else 999999,
                -_safe_float((row or {}).get("amount_yi")),
                str((row or {}).get("stock_code") or (row or {}).get("ts_code") or ""),
            )
        )
        if not rows:
            return []
        name_map, industry_map = _load_name_and_industry_maps()
        ranked = []
        for rank, row in enumerate(rows[: max(int(limit or 50), 1)], start=1):
            stock_code = str(row.get("stock_code") or "").strip()
            ts_code = str(row.get("ts_code") or "").strip().upper()
            code = stock_code or (ts_code.split(".", 1)[0] if "." in ts_code else ts_code)
            name = _lookup_by_code(name_map, row, row.get("name") or code)
            sector = _lookup_by_code(industry_map, row, "未知")
            ranked.append(
                {
                    "rank": rank,
                    "code": code,
                    "name": name,
                    "turnover": _safe_float(row.get("amount_yi")),
                    "change_pct": _safe_float(row.get("pct_chg")),
                    "sector": sector or "未知",
                    "data_source": source,
                    "trade_date": row.get("trade_date"),
                }
            )
        return ranked

    fetcher = fetch_stock_daily_turnover_records_fn or fetch_stock_daily_turnover_records
    try:
        rows = [row for row in (fetcher(target_date) or []) if _safe_float((row or {}).get("amount_yi")) > 0]
        rows.sort(
            key=lambda row: (
                -_safe_float((row or {}).get("amount_yi")),
                str((row or {}).get("stock_code") or (row or {}).get("ts_code") or ""),
            )
        )
        if rows:
            return _ranked_from_rows(rows, source="tushare.daily")
    except Exception:
        pass

    if callable(legacy_get_turnover_rank_fn):
        legacy_rows = legacy_get_turnover_rank_fn(target_date=target_date, limit=limit) or []
        if legacy_rows:
            return legacy_rows
    try:
        service = _create_fact_database_service(database_service_cls, db_path)
        local_rows = service.query_turnover_rank_rows(
            normalize_kline_date_str(target_date) or target_date,
            limit=max(int(limit or 50), 1),
            rank_scope="all_a",
        )
        ranked = _ranked_from_rows(local_rows, source="storage.turnover_rank_daily")
        if ranked:
            return ranked
    except Exception:
        pass
    return []


def _normalize_tushare_hot_rank_row(row, rank, *, market="热股"):
    code = _clean_code(_pick(row, "ts_code", "code", default=""))
    if not code:
        return None
    concepts = _pick(row, "concept", "concepts", default="")
    concept_list = _normalize_concepts(concepts)
    return {
        "rank": _safe_int(_pick(row, "rank", "热度排名", default=rank), rank),
        "code": code,
        "name": _clean_text(_pick(row, "ts_name", "name", "股票名称", default=code)),
        "rate": _safe_float(_pick(row, "hot", "rate", "heat", default=0.0)),
        "change_pct": _safe_float(_pick(row, "pct_change", "pct_chg", "涨跌幅", default=0.0)),
        "price": _safe_float(_pick(row, "current_price", "price", "最新价", default=0.0)),
        "concepts": concept_list,
        "popularity_tag": _clean_text(_pick(row, "rank_reason", "tag", "reason", default="")),
        "rank_time": _clean_text(_pick(row, "rank_time", "update_time", default="")),
        "data_source": "tushare.ths_hot",
        "market": market,
        "trade_date": normalize_kline_date_str(_pick(row, "trade_date", default="")),
    }


def _normalize_tushare_sector_hot_row(row, rank, *, market):
    code = str(_pick(row, "ts_code", "code", default="")).strip().upper()
    name = _clean_text(_pick(row, "ts_name", "name", default=code))
    if not name:
        return None
    return {
        "rank": _safe_int(_pick(row, "rank", default=rank), rank),
        "code": code,
        "name": name,
        "rate": _safe_float(_pick(row, "hot", "rate", default=0.0)),
        "change_pct": _safe_float(_pick(row, "pct_change", "pct_chg", default=0.0)),
        "tag": market,
        "hot_tag": _clean_text(_pick(row, "rank_reason", "tag", default="")),
        "rank_time": _clean_text(_pick(row, "rank_time", default="")),
        "data_source": "tushare.ths_hot",
        "market": market,
        "trade_date": normalize_kline_date_str(_pick(row, "trade_date", default="")),
    }


def get_stock_hot_rank_from_tushare_first(
    target_date=None,
    *,
    limit=50,
    fetch_tushare_ths_hot_fn=None,
    legacy_fetch_hot_rank_fn=None,
):
    fetcher = fetch_tushare_ths_hot_fn or fetch_tushare_ths_hot
    market = "热股"
    try:
        rows = [row for row in (fetcher(target_date, market=market) or []) if _is_new_high_hot_row(row)]
        normalized = []
        for fallback_rank, row in enumerate(rows, start=1):
            item = _normalize_tushare_hot_rank_row(row or {}, fallback_rank, market=market)
            if item:
                normalized.append(item)
        normalized.sort(key=lambda item: (item.get("rank") or 999999, item.get("code") or ""))
        if normalized:
            return normalized[: max(int(limit or 30), 1)]
    except Exception:
        pass

    if callable(legacy_fetch_hot_rank_fn):
        return legacy_fetch_hot_rank_fn(num=limit) or []
    return []


def get_sector_hot_plates_from_tushare_first(
    target_date=None,
    *,
    limit=20,
    fetch_tushare_ths_hot_fn=None,
    legacy_fetch_hot_plates_fn=None,
):
    fetcher = fetch_tushare_ths_hot_fn or fetch_tushare_ths_hot
    try:
        rows = []
        seen = set()
        for market in ("概念板块", "行业板块"):
            for row in fetcher(target_date, market=market) or []:
                item = _normalize_tushare_sector_hot_row(row or {}, len(rows) + 1, market=market)
                if item:
                    key = item.get("code") or item.get("name")
                    if key in seen:
                        continue
                    seen.add(key)
                    rows.append(item)
        rows.sort(key=lambda item: (item.get("rank") or 999999, -_safe_float(item.get("rate")), item.get("name") or ""))
        if rows:
            return rows[: max(int(limit or 20), 1)]
    except Exception:
        pass

    if callable(legacy_fetch_hot_plates_fn):
        return legacy_fetch_hot_plates_fn() or []
    return []


def _is_concept_hot_plate(row):
    row = row or {}
    tag = str(row.get("tag") or row.get("market") or "").strip()
    code = str(row.get("code") or row.get("ts_code") or "").strip().upper()
    if "概念" in tag:
        return True
    return code.startswith(("884", "885", "886"))


def _normalize_tushare_ths_index_code(code):
    code = str(code or "").strip().upper()
    if not code:
        return ""
    if code.endswith(".TI"):
        return code
    if code[:3] in {"884", "885", "886"} and code[:6].isdigit():
        return f"{code[:6]}.TI"
    return code


def _normalize_member_stock_code(row):
    return _clean_code(_pick(row or {}, "con_code", "ts_code", "code", default=""))


def _empty_concept_fund_flow_payload(*, fallback_used=False):
    return {
        "rows": [],
        "inflow": [],
        "outflow": [],
        "provider": "tushare.ths_member+tushare.moneyflow",
        "fallback_used": bool(fallback_used),
    }


def _concept_fund_flow_snapshot_payload(snapshot_fallback_fn, target_date, *, limit=20):
    if not callable(snapshot_fallback_fn):
        return {}
    try:
        payload = snapshot_fallback_fn(target_date) or {}
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    rows = [dict(row) for row in (payload.get("rows") or []) if isinstance(row, dict)]
    if not rows:
        return {}
    limit_value = max(int(limit or 20), 1)
    return {
        "rows": rows,
        "inflow": list(payload.get("inflow") or rows)[:limit_value],
        "outflow": list(payload.get("outflow") or [])[:limit_value],
        "provider": payload.get("provider") or "snapshot.concept_fund_flow",
        "fallback_used": True,
    }


def _concept_fund_flow_pending_hot_plate_payload(concept_plates, target_date, *, limit=20):
    rows = []
    for plate in concept_plates[: max(int(limit or 20), 1)]:
        code = str(plate.get("code") or plate.get("ts_code") or "").strip().upper()
        name = _clean_text(plate.get("name"))
        if not code or not name:
            continue
        change_pct = _safe_float(_pick(plate, "change_pct", "zdf", "change", default=0.0))
        rows.append(
            {
                "name": name,
                "code": code,
                "zljlr": "",
                "net_amount": "",
                "net_inflow": "",
                "change_pct": change_pct,
                "zdf": change_pct,
                "matched_member_count": 0,
                "missing_member_count": 0,
                "member_count": 0,
                "hot_plate_rank": plate.get("rank") or plate.get("order"),
                "hot_plate_heat": _safe_float(plate.get("rate")),
                "fund_flow_status": "pending",
                "data_source": "tushare.ths_hot.pending_moneyflow",
                "trade_date": normalize_kline_date_str(target_date),
            }
        )
    if not rows:
        return {}
    return {
        "rows": rows,
        "inflow": rows[: max(int(limit or 20), 1)],
        "outflow": [],
        "provider": "tushare.ths_hot.pending_moneyflow",
        "fallback_used": True,
    }


def get_hot_concept_fund_flow_from_tushare_first(
    target_date=None,
    *,
    hot_plates=None,
    limit=20,
    fetch_tushare_ths_member_fn=None,
    fetch_stock_moneyflow_map_fn=None,
    snapshot_fallback_fn=None,
    retry_sleep_fn=None,
):
    hot_plates = list(hot_plates or [])
    concept_plates = []
    seen_codes = set()
    for plate in hot_plates:
        if not isinstance(plate, dict) or not _is_concept_hot_plate(plate):
            continue
        code = _normalize_tushare_ths_index_code(plate.get("code") or plate.get("ts_code"))
        name = _clean_text(plate.get("name"))
        if not code or not name or code in seen_codes:
            continue
        seen_codes.add(code)
        normalized_plate = dict(plate)
        normalized_plate["code"] = code
        concept_plates.append(normalized_plate)
        if len(concept_plates) >= max(int(limit or 20), 1):
            break

    if not concept_plates:
        return _empty_concept_fund_flow_payload(fallback_used=False)

    member_fetcher = fetch_tushare_ths_member_fn or fetch_tushare_ths_member
    moneyflow_fetcher = fetch_stock_moneyflow_map_fn or fetch_stock_moneyflow_map
    def _fetch_stock_moneyflow():
        try:
            return moneyflow_fetcher(target_date) or {}
        except Exception:
            return {}

    def _aggregate_rows(stock_moneyflow):
        aggregated = []
        member_fetch_error_count = 0
        for plate in concept_plates:
            code = str(plate.get("code") or plate.get("ts_code") or "").strip().upper()
            name = _clean_text(plate.get("name"))
            try:
                member_rows = list(member_fetcher(code) or [])
            except Exception:
                member_fetch_error_count += 1
                member_rows = []
            if not member_rows:
                continue

            net_inflow = 0.0
            matched_count = 0
            missing_count = 0
            for member in member_rows:
                member_code = _normalize_member_stock_code(member)
                if not member_code:
                    continue
                value = stock_moneyflow.get(member_code)
                if value is None:
                    value = stock_moneyflow.get(str(_pick(member or {}, "con_code", "ts_code", "code", default="")).strip().upper())
                if value is None:
                    missing_count += 1
                    continue
                net_inflow += _safe_float(value)
                matched_count += 1

            if matched_count <= 0:
                continue
            change_pct = _safe_float(_pick(plate, "change_pct", "zdf", "change", default=0.0))
            aggregated.append(
                {
                    "name": name,
                    "code": code,
                    "zljlr": round(net_inflow, 6),
                    "net_amount": round(net_inflow, 6),
                    "net_inflow": round(net_inflow, 6),
                    "change_pct": change_pct,
                    "zdf": change_pct,
                    "matched_member_count": matched_count,
                    "missing_member_count": missing_count,
                    "member_count": matched_count + missing_count,
                    "hot_plate_rank": plate.get("rank") or plate.get("order"),
                    "data_source": "tushare.ths_member+tushare.moneyflow",
                    "trade_date": normalize_kline_date_str(target_date),
                }
            )
        return aggregated, member_fetch_error_count

    stock_moneyflow = _fetch_stock_moneyflow()
    if not stock_moneyflow:
        fallback = _concept_fund_flow_snapshot_payload(snapshot_fallback_fn, target_date, limit=limit)
        return fallback or _concept_fund_flow_pending_hot_plate_payload(concept_plates, target_date, limit=limit) or _empty_concept_fund_flow_payload(fallback_used=True)

    rows, member_fetch_error_count = _aggregate_rows(stock_moneyflow)

    if not rows:
        if member_fetch_error_count >= len(concept_plates):
            fallback = _concept_fund_flow_snapshot_payload(snapshot_fallback_fn, target_date, limit=limit)
            if fallback:
                return fallback
        elif callable(retry_sleep_fn):
            try:
                retry_sleep_fn(1)
            except Exception:
                pass
            stock_moneyflow = _fetch_stock_moneyflow()
            if stock_moneyflow:
                rows, member_fetch_error_count = _aggregate_rows(stock_moneyflow)
        elif retry_sleep_fn is None:
            try:
                import time

                time.sleep(1)
            except Exception:
                pass
            stock_moneyflow = _fetch_stock_moneyflow()
            if stock_moneyflow:
                rows, member_fetch_error_count = _aggregate_rows(stock_moneyflow)

    if not rows:
        fallback = _concept_fund_flow_snapshot_payload(snapshot_fallback_fn, target_date, limit=limit)
        if fallback:
            return fallback
        pending = _concept_fund_flow_pending_hot_plate_payload(concept_plates, target_date, limit=limit)
        if pending:
            return pending

    rows.sort(key=lambda item: (_safe_float(item.get("net_inflow")), item.get("name") or ""), reverse=True)
    return {
        "rows": rows,
        "inflow": rows[: max(int(limit or 20), 1)],
        "outflow": sorted(rows, key=lambda item: (_safe_float(item.get("net_inflow")), item.get("name") or ""))[: max(int(limit or 20), 1)],
        "provider": "tushare.ths_member+tushare.moneyflow",
        "fallback_used": False,
    }


def _is_tushare_a_share_industry_index(meta):
    meta = meta or {}
    if str(meta.get("exchange") or "").strip().upper() != "A":
        return False
    return str(meta.get("type") or "").strip().upper() == "I"


_SECTOR_CHANGE_RANK_ROWS_CACHE = {}


def _normalize_sector_change_row(row, meta, rank):
    name = _clean_text((meta or {}).get("name"))
    ts_code = str((row or {}).get("ts_code") or "").strip().upper()
    if not name or not ts_code:
        return None
    pct_change = _safe_float(_pick(row, "pct_change", "pct_chg", default=0.0))
    return {
        "rank": rank,
        "code": ts_code,
        "name": name,
        "change_pct": pct_change,
        "close": _safe_float(_pick(row, "close", default=0.0)),
        "turnover_rate": _safe_float(_pick(row, "turnover_rate", default=0.0)),
        "data_source": "tushare.ths_daily",
        "trade_date": normalize_kline_date_str(_pick(row, "trade_date", default="")),
    }


def _rank_sector_change_rows(rows, *, rank_type="up", limit=10):
    ranked = [dict(item) for item in rows or []]
    reverse = rank_type != "down"
    ranked.sort(key=lambda item: (_safe_float(item.get("change_pct")), item.get("name") or ""), reverse=reverse)
    ranked = ranked[: max(int(limit or 10), 1)]
    for rank, item in enumerate(ranked, start=1):
        item["rank"] = rank
    return ranked


def _safe_load_noarg(fetcher):
    try:
        return fetcher() if callable(fetcher) else {}
    except Exception:
        return {}


def _stock_row_codes(row):
    row = row or {}
    codes = []
    ts_code = str(_pick(row, "ts_code", "fs_code", default="")).strip().upper()
    stock_code = _clean_code(_pick(row, "stock_code", "code", "ts_code", default=""))
    for code in (stock_code, ts_code):
        if code and code not in codes:
            codes.append(code)
    if ts_code and "." in ts_code:
        compact = _clean_code(ts_code)
        if compact and compact not in codes:
            codes.append(compact)
    return codes


def _industry_from_stock_row(row, *, industry_map=None, basic_map=None):
    row_industry = _clean_text(_pick(row, "industry", "所属行业", "sector", default=""))
    if _is_valid_sector_label(row_industry):
        return row_industry
    for code in _stock_row_codes(row):
        industry = _clean_text((industry_map or {}).get(code))
        if _is_valid_sector_label(industry):
            return industry
        basic_item = (basic_map or {}).get(code)
        if isinstance(basic_item, dict):
            industry = _clean_text(basic_item.get("industry"))
            if _is_valid_sector_label(industry):
                return industry
    return ""


def _stock_daily_amount_yi(row):
    row = row or {}
    for key in ("amount_yi", "turnover_yi", "turnover"):
        if row.get(key) not in (None, ""):
            return _safe_float(row.get(key))
    if row.get("amount_raw_qianyuan") not in (None, ""):
        return _safe_float(row.get("amount_raw_qianyuan")) / 100000.0
    if row.get("amount") not in (None, ""):
        return _safe_float(row.get("amount")) / 100000.0
    return 0.0


def _stock_daily_change_pct(row):
    return _safe_float(_pick(row, "pct_chg", "pct_change", "change_pct", "zdf", default=0.0))


def _aggregate_stock_daily_change_by_industry(target_date, daily_rows, *, industry_map=None, basic_map=None):
    trade_date = normalize_kline_date_str(target_date)
    buckets = {}
    for row in daily_rows or []:
        industry = _industry_from_stock_row(row, industry_map=industry_map, basic_map=basic_map)
        if not industry:
            continue
        amount_yi = _stock_daily_amount_yi(row)
        weight = amount_yi if amount_yi > 0 else 1.0
        change_pct = _stock_daily_change_pct(row)
        bucket = buckets.setdefault(
            industry,
            {
                "change_weighted_sum": 0.0,
                "change_weight": 0.0,
                "turnover_yi": 0.0,
                "stock_count": 0,
                "up_count": 0,
                "down_count": 0,
            },
        )
        bucket["change_weighted_sum"] += change_pct * weight
        bucket["change_weight"] += weight
        bucket["turnover_yi"] += max(amount_yi, 0.0)
        bucket["stock_count"] += 1
        if change_pct > 0:
            bucket["up_count"] += 1
        elif change_pct < 0:
            bucket["down_count"] += 1

    rows = []
    for industry, bucket in buckets.items():
        weight = bucket.get("change_weight") or 1.0
        change_pct = bucket.get("change_weighted_sum", 0.0) / weight
        rows.append(
            {
                "name": industry,
                "code": "",
                "change_pct": round(change_pct, 6),
                "zdf": round(change_pct, 6),
                "turnover_yi": round(bucket.get("turnover_yi", 0.0), 6),
                "stock_count": int(bucket.get("stock_count", 0)),
                "up_count": int(bucket.get("up_count", 0)),
                "down_count": int(bucket.get("down_count", 0)),
                "data_source": "tushare.daily.industry_aggregate",
                "trade_date": trade_date,
                "source_date": trade_date,
                "query_date": trade_date,
            }
        )
    return rows


def _moneyflow_value_for_stock_row(stock_moneyflow, row):
    missing = object()
    for code in _stock_row_codes(row):
        value = (stock_moneyflow or {}).get(code, missing)
        if value is not missing and value not in (None, ""):
            return _safe_float(value)
    return None


def _aggregate_stock_moneyflow_by_industry(target_date, stock_moneyflow, daily_rows, *, industry_map=None, basic_map=None):
    trade_date = normalize_kline_date_str(target_date)
    buckets = {}
    for row in daily_rows or []:
        industry = _industry_from_stock_row(row, industry_map=industry_map, basic_map=basic_map)
        if not industry:
            continue
        net_inflow = _moneyflow_value_for_stock_row(stock_moneyflow, row)
        if net_inflow is None:
            continue
        amount_yi = _stock_daily_amount_yi(row)
        weight = amount_yi if amount_yi > 0 else 1.0
        change_pct = _stock_daily_change_pct(row)
        bucket = buckets.setdefault(
            industry,
            {
                "net_amount": 0.0,
                "positive_amount": 0.0,
                "negative_amount": 0.0,
                "change_weighted_sum": 0.0,
                "change_weight": 0.0,
                "turnover_yi": 0.0,
                "stock_count": 0,
                "matched_stock_count": 0,
            },
        )
        bucket["net_amount"] += net_inflow
        if net_inflow >= 0:
            bucket["positive_amount"] += net_inflow
        else:
            bucket["negative_amount"] += abs(net_inflow)
        bucket["change_weighted_sum"] += change_pct * weight
        bucket["change_weight"] += weight
        bucket["turnover_yi"] += max(amount_yi, 0.0)
        bucket["stock_count"] += 1
        bucket["matched_stock_count"] += 1

    rows = []
    for industry, bucket in buckets.items():
        weight = bucket.get("change_weight") or 1.0
        change_pct = bucket.get("change_weighted_sum", 0.0) / weight
        net_amount = bucket.get("net_amount", 0.0)
        rows.append(
            {
                "name": industry,
                "code": "",
                "zljlr": round(net_amount, 6),
                "net_amount": round(net_amount, 6),
                "net_inflow": round(net_amount, 6),
                "change_pct": round(change_pct, 6),
                "zdf": round(change_pct, 6),
                "net_buy_amount": round(bucket.get("positive_amount", 0.0), 6),
                "net_sell_amount": round(bucket.get("negative_amount", 0.0), 6),
                "turnover_yi": round(bucket.get("turnover_yi", 0.0), 6),
                "stock_count": int(bucket.get("stock_count", 0)),
                "matched_stock_count": int(bucket.get("matched_stock_count", 0)),
                "data_source": "tushare.moneyflow+daily.industry_aggregate",
                "trade_date": trade_date,
                "source_date": trade_date,
                "query_date": trade_date,
            }
        )
    return rows


def get_sector_change_rank_from_tushare_first(
    target_date=None,
    *,
    rank_type="up",
    limit=10,
    fetch_tushare_ths_daily_fn=None,
    fetch_tushare_ths_index_map_fn=None,
    fetch_stock_daily_turnover_records_fn=None,
    fetch_stock_basic_map_fn=None,
    fetch_stock_industry_map_fn=None,
    legacy_get_sector_change_fn=None,
):
    daily_fetcher = fetch_tushare_ths_daily_fn or fetch_tushare_ths_daily
    index_map_fetcher = fetch_tushare_ths_index_map_fn or fetch_tushare_ths_index_map
    cache_key = normalize_kline_date_str(target_date) or str(target_date or "")
    try:
        index_map = index_map_fetcher() if callable(index_map_fetcher) else {}
        rows = []
        for row in daily_fetcher(target_date) or []:
            ts_code = str((row or {}).get("ts_code") or "").strip().upper()
            meta = index_map.get(ts_code, {})
            if not _is_tushare_a_share_industry_index(meta):
                continue
            item = _normalize_sector_change_row(row or {}, meta, len(rows) + 1)
            if item:
                rows.append(item)
        if rows:
            if cache_key:
                _SECTOR_CHANGE_RANK_ROWS_CACHE[cache_key] = [dict(item) for item in rows]
            return _rank_sector_change_rows(rows, rank_type=rank_type, limit=limit)
    except Exception:
        if cache_key and _SECTOR_CHANGE_RANK_ROWS_CACHE.get(cache_key):
            return _rank_sector_change_rows(
                _SECTOR_CHANGE_RANK_ROWS_CACHE.get(cache_key),
                rank_type=rank_type,
                limit=limit,
            )

    daily_stock_fetcher = fetch_stock_daily_turnover_records_fn or fetch_stock_daily_turnover_records
    try:
        daily_rows = daily_stock_fetcher(target_date) if callable(daily_stock_fetcher) else []
    except Exception:
        daily_rows = []
    if daily_rows:
        basic_map = _safe_load_noarg(fetch_stock_basic_map_fn or fetch_stock_basic_map)
        industry_map = _safe_load_noarg(fetch_stock_industry_map_fn) if fetch_stock_industry_map_fn else {}
        aggregate_rows = _aggregate_stock_daily_change_by_industry(
            target_date,
            daily_rows,
            industry_map=industry_map,
            basic_map=basic_map,
        )
        if aggregate_rows:
            return _rank_sector_change_rows(aggregate_rows, rank_type=rank_type, limit=limit)

    if callable(legacy_get_sector_change_fn):
        return legacy_get_sector_change_fn(rank_type=rank_type, limit=limit, target_date=target_date) or []
    return []


def _normalize_sector_flow_row(row):
    name = _clean_text(_pick(row, "industry", "name", default=""))
    if not name:
        return None
    net_amount = _safe_float(_pick(row, "net_amount", "zljlr", "net_inflow", default=0.0))
    return {
        "name": name,
        "code": str(_pick(row, "ts_code", "code", default="")).strip().upper(),
        "zljlr": net_amount,
        "net_amount": net_amount,
        "net_inflow": net_amount,
        "change_pct": _safe_float(_pick(row, "pct_change", "zdf", "change_pct", default=0.0)),
        "zdf": _safe_float(_pick(row, "pct_change", "zdf", "change_pct", default=0.0)),
        "net_buy_amount": _safe_float(_pick(row, "net_buy_amount", default=0.0)),
        "net_sell_amount": _safe_float(_pick(row, "net_sell_amount", default=0.0)),
        "turnover_yi": _safe_float(_pick(row, "net_buy_amount", default=0.0)) + _safe_float(_pick(row, "net_sell_amount", default=0.0)),
        "lead_stock": _clean_text(_pick(row, "lead_stock", default="")),
        "data_source": "tushare.moneyflow_ind_ths",
        "trade_date": normalize_kline_date_str(_pick(row, "trade_date", default="")),
    }


def get_sector_fund_flow_from_tushare_first(
    target_date=None,
    *,
    limit=50,
    fetch_tushare_sector_flow_fn=None,
    fetch_stock_moneyflow_map_fn=None,
    fetch_stock_daily_turnover_records_fn=None,
    fetch_stock_basic_map_fn=None,
    fetch_stock_industry_map_fn=None,
    legacy_get_sector_fund_flow_fn=None,
):
    fetcher = fetch_tushare_sector_flow_fn or fetch_tushare_sector_flow
    try:
        rows = []
        for row in fetcher(target_date) or []:
            item = _normalize_sector_flow_row(row or {})
            if item:
                rows.append(item)
        if rows:
            inflow = sorted(rows, key=lambda item: (_safe_float(item.get("net_amount")), item.get("name") or ""), reverse=True)
            outflow = sorted(rows, key=lambda item: (_safe_float(item.get("net_amount")), item.get("name") or ""))
            cap = max(int(limit or 50), 1)
            return {
                "inflow": inflow[:cap],
                "outflow": outflow[:cap],
                "provider": "tushare.moneyflow_ind_ths",
                "fallback_used": False,
            }
    except Exception:
        pass

    moneyflow_fetcher = fetch_stock_moneyflow_map_fn or fetch_stock_moneyflow_map
    daily_fetcher = fetch_stock_daily_turnover_records_fn or fetch_stock_daily_turnover_records
    try:
        stock_moneyflow = moneyflow_fetcher(target_date) if callable(moneyflow_fetcher) else {}
    except Exception:
        stock_moneyflow = {}
    try:
        daily_rows = daily_fetcher(target_date) if callable(daily_fetcher) else []
    except Exception:
        daily_rows = []
    if stock_moneyflow and daily_rows:
        basic_map = _safe_load_noarg(fetch_stock_basic_map_fn or fetch_stock_basic_map)
        industry_map = _safe_load_noarg(fetch_stock_industry_map_fn) if fetch_stock_industry_map_fn else {}
        rows = _aggregate_stock_moneyflow_by_industry(
            target_date,
            stock_moneyflow,
            daily_rows,
            industry_map=industry_map,
            basic_map=basic_map,
        )
        if rows:
            inflow = sorted(rows, key=lambda item: (_safe_float(item.get("net_amount")), item.get("name") or ""), reverse=True)
            outflow = sorted(rows, key=lambda item: (_safe_float(item.get("net_amount")), item.get("name") or ""))
            cap = max(int(limit or 50), 1)
            return {
                "inflow": inflow[:cap],
                "outflow": outflow[:cap],
                "provider": "tushare.moneyflow+daily.industry_aggregate",
                "fallback_used": True,
                "trade_date": normalize_kline_date_str(target_date),
                "source_date": normalize_kline_date_str(target_date),
                "query_date": normalize_kline_date_str(target_date),
            }

    if callable(legacy_get_sector_fund_flow_fn):
        fallback = legacy_get_sector_fund_flow_fn(target_date=target_date, limit=limit) or {}
        return {
            **fallback,
            "provider": "legacy.sector_fund_flow",
            "fallback_used": True,
        }
    return {"inflow": [], "outflow": [], "provider": "legacy.sector_fund_flow", "fallback_used": True}


def _normalize_tushare_lhb_group(rows):
    grouped = {}
    for row in rows or []:
        code = _clean_code(_pick(row, "ts_code", "code", default=""))
        if not code:
            continue
        bucket = grouped.setdefault(
            code,
            {
                "代码": code,
                "fs_code": str(_pick(row, "ts_code", default="")).strip().upper(),
                "name": _clean_text(_pick(row, "name", default="")),
                "net_buy_amount": 0.0,
                "close_price": 0.0,
                "change_rate": 0.0,
                "reasons": [],
                "data_source": "tushare.top_list",
            },
        )
        bucket["net_buy_amount"] += _safe_float(_pick(row, "net_amount", default=0.0))
        bucket["close_price"] = bucket.get("close_price") or _safe_float(_pick(row, "close", default=0.0))
        bucket["change_rate"] = bucket.get("change_rate") or _safe_float(_pick(row, "pct_change", "change_rate", default=0.0))
        reason = _clean_text(_pick(row, "reason", default=""))
        if reason and reason not in bucket["reasons"]:
            bucket["reasons"].append(reason)
    return list(grouped.values())


def get_lhb_snapshot_from_tushare_first(
    target_date=None,
    *,
    fetch_tushare_top_list_fn=None,
    fetch_stock_industry_map_fn=None,
    legacy_get_lhb_snapshot_fn=None,
):
    fetcher = fetch_tushare_top_list_fn or fetch_tushare_top_list
    try:
        grouped_rows = _normalize_tushare_lhb_group(fetcher(target_date) or [])
        if grouped_rows:
            industry_map_loader = fetch_stock_industry_map_fn or fetch_stock_industry_map
            try:
                industry_map = industry_map_loader() if callable(industry_map_loader) else {}
            except Exception:
                industry_map = {}
            buy_rows = sorted(grouped_rows, key=lambda item: item.get("net_buy_amount", 0), reverse=True)[:10]
            sell_rows = sorted(grouped_rows, key=lambda item: item.get("net_buy_amount", 0))[:10]
            net_buy_top10 = []
            for rank, row in enumerate(buy_rows, start=1):
                sector = _lookup_by_code(industry_map, {"stock_code": row["代码"], "ts_code": row.get("fs_code", "")}, "未知")
                net_buy_top10.append(
                    {
                        "rank": rank,
                        "code": row["代码"],
                        "name": row.get("name", ""),
                        "net_buy_amount_yi": round(_safe_float(row.get("net_buy_amount")) / 1e8, 6),
                        "change_pct": _safe_float(row.get("change_rate")),
                        "zt_status": "正常",
                        "sector": sector or "未知",
                        "data_source": "tushare.top_list",
                    }
                )
            net_sell_top10 = []
            for rank, row in enumerate(sell_rows, start=1):
                sector = _lookup_by_code(industry_map, {"stock_code": row["代码"], "ts_code": row.get("fs_code", "")}, "未知")
                net_sell_top10.append(
                    {
                        "rank": rank,
                        "code": row["代码"],
                        "name": row.get("name", ""),
                        "net_buy_amount_yi": round(_safe_float(row.get("net_buy_amount")) / 1e8, 6),
                        "change_pct": _safe_float(row.get("change_rate")),
                        "zt_status": "正常",
                        "sector": sector or "未知",
                        "data_source": "tushare.top_list",
                    }
                )
            return {
                "lhb_net_buy_top10": net_buy_top10,
                "lhb_net_sell_top10": net_sell_top10,
                "lhb_analysis": grouped_rows,
                "provider": "tushare.top_list",
                "fallback_used": False,
            }
    except Exception:
        pass

    if callable(legacy_get_lhb_snapshot_fn):
        fallback = legacy_get_lhb_snapshot_fn(target_date=target_date) or {}
        return {**fallback, "provider": fallback.get("provider") or "legacy.lhb_snapshot", "fallback_used": True}
    return {"lhb_net_buy_top10": [], "lhb_net_sell_top10": [], "lhb_analysis": [], "provider": "legacy.lhb_snapshot", "fallback_used": True}


def _new_share_query_window(target_date):
    target = _parse_date(target_date) or datetime.datetime.now().date()
    start = target
    end = target + datetime.timedelta(days=31)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def _next_trade_date_from_tushare(target_date, *, fetch_open_trade_dates_fn=None):
    target = _parse_date(target_date) or datetime.datetime.now().date()
    end = target + datetime.timedelta(days=14)
    fetcher = fetch_open_trade_dates_fn or fetch_tushare_open_trade_dates
    for trade_date in fetcher(target.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")) or []:
        parsed = _parse_date(trade_date)
        if parsed and parsed > target:
            return parsed.strftime("%Y-%m-%d")
    return ""


def _normalize_tushare_new_share_row(row, target_date, *, next_trade_date=""):
    code = _clean_code(_pick(row, "ts_code", "sub_code", "code", default=""))
    subscription_date = normalize_kline_date_str(_pick(row, "ipo_date", "subscription_date", default=""))
    listing_date = normalize_kline_date_str(_pick(row, "issue_date", "listing_date", default=""))
    if not code or not subscription_date:
        return None
    target = _parse_date(target_date)
    subscription = _parse_date(subscription_date)
    listing = _parse_date(listing_date)
    days_to_subscription = (subscription - target).days if target and subscription else None
    days_to_listing = (listing - target).days if target and listing else None
    days_since_listing = (target - listing).days if target and listing else None
    window = _listing_window(days_to_listing) if listing_date else "missing_listing_date"
    subscription_window = _subscription_window(days_to_subscription, subscription_date, next_trade_date)
    return {
        "code": code,
        "name": _clean_text(_pick(row, "name", default="")),
        "subscription_code": _clean_text(_pick(row, "sub_code", default="")),
        "subscription_date": subscription_date,
        "net_issue_date": subscription_date,
        "listing_date": listing_date,
        "issue_amount_10k": _safe_float(_pick(row, "amount", default=0.0)),
        "online_issue_amount_10k": _safe_float(_pick(row, "market_amount", default=0.0)),
        "issue_price": _safe_float(_pick(row, "price", default=0.0)),
        "pe_ratio": _safe_float(_pick(row, "pe", "pe_ratio", default=0.0)),
        "fundraising_yi": _safe_float(_pick(row, "funds", default=0.0)),
        "market": _market_from_code(code),
        "days_to_subscription": days_to_subscription,
        "days_to_listing": days_to_listing,
        "days_since_listing": days_since_listing,
        "listing_window": window,
        "pre_listing_action": _pre_listing_action(window),
        "subscription_window": subscription_window,
        "next_trade_date": next_trade_date,
        "official_listing_date_missing": not bool(listing_date),
        "source": "tushare.new_share",
        "source_url": "",
        "source_status": "success",
        "data_source": "tushare.new_share",
    }


def get_new_stock_calendar_from_tushare_first(
    target_date=None,
    *,
    fetch_tushare_new_share_fn=None,
    next_trade_date_fn=None,
    fetch_tushare_open_trade_dates_fn=None,
    legacy_get_new_stock_calendar_fn=None,
):
    fetcher = fetch_tushare_new_share_fn or fetch_tushare_new_share
    start_date, end_date = _new_share_query_window(target_date)
    if callable(next_trade_date_fn):
        next_trade_date = normalize_kline_date_str(next_trade_date_fn(target_date))
    else:
        try:
            next_trade_date = _next_trade_date_from_tushare(
                target_date,
                fetch_open_trade_dates_fn=fetch_tushare_open_trade_dates_fn,
            )
        except Exception:
            next_trade_date = ""

    try:
        rows = []
        for row in fetcher(start_date, end_date) or []:
            item = _normalize_tushare_new_share_row(row or {}, target_date, next_trade_date=next_trade_date)
            if item:
                rows.append(item)
        rows.sort(key=lambda item: (item.get("subscription_date") or "", item.get("listing_date") or "", item.get("code") or ""))
        if rows:
            return rows
    except Exception:
        pass

    if callable(legacy_get_new_stock_calendar_fn):
        return legacy_get_new_stock_calendar_fn(target_date=target_date) or []
    return []


def _infer_lianban_days(row):
    for key in ("连板数", "lianban_days", "limit_times"):
        value = _safe_int((row or {}).get(key), 0)
        if value > 0:
            return value
    up_stat = str(_pick(row, "up_stat", "涨停统计", default="")).strip()
    if up_stat:
        first_number = ""
        for char in up_stat:
            if char.isdigit():
                first_number += char
            elif first_number:
                break
        if first_number:
            return max(_safe_int(first_number, 1), 1)
    return 1


def _normalize_limit_row(row, *, direction, industry_map=None):
    code = _clean_code(_pick(row, "ts_code", "code", "代码", default=""))
    if not code:
        return None
    first_time = _pick(row, "first_time", "first_lu_time", "first_ld_time", "首次封板时间", default="")
    last_time = _pick(row, "last_time", "last_lu_time", "last_ld_time", "最后封板时间", default="")
    lianban_days = _infer_lianban_days(row)
    industry = str(_pick(row, "industry", "所属行业", "行业", default="未知")).strip() or "未知"
    if not _is_valid_sector_label(industry):
        industry = _lookup_by_code(industry_map or {}, {"stock_code": code, "ts_code": _pick(row, "ts_code", default="")}, "未知")
    if not _is_valid_sector_label(industry):
        industry = "未知"
    return {
        "代码": code,
        "名称": str(_pick(row, "name", "ts_name", "名称", default=code)).strip(),
        "所属行业": industry,
        "涨跌幅": _safe_float(_pick(row, "pct_chg", "pct_change", "涨跌幅", default=0.0)),
        "成交额": round(_safe_float(_pick(row, "amount", "turnover", "成交额", default=0.0)) / 100000.0, 6),
        "连板数": lianban_days,
        "涨停统计": str(_pick(row, "up_stat", "lu_desc", "涨停统计", default=f"{lianban_days}连板" if direction == "up" else "")).strip(),
        "开盘价": _safe_float(_pick(row, "open", "开盘价", default=0.0)),
        "最新价": _safe_float(_pick(row, "price", "close", "最新价", default=0.0)),
        "最高价": _safe_float(_pick(row, "high", "最高价", default=0.0)),
        "最低价": _safe_float(_pick(row, "low", "最低价", default=0.0)),
        "首次封板时间": _normalize_time_text(first_time),
        "最后封板时间": _normalize_time_text(last_time),
        "打开次数": _safe_int(_pick(row, "open_num", "open_times", "打开次数", default=0), 0),
        "data_source": "tushare.limit_list_ths",
        "trade_date": normalize_kline_date_str(_pick(row, "trade_date", default="")),
    }


def _market_stats_from_daily_rows(rows, zt_count, dt_count):
    up_count = 0
    down_count = 0
    for row in rows or []:
        pct_chg = _safe_float(_pick(row, "pct_chg", "pct_change", "涨跌幅", default=0.0))
        if pct_chg > 0:
            up_count += 1
        elif pct_chg < 0:
            down_count += 1
    return {
        "up_count": up_count,
        "down_count": down_count,
        "zt_count": int(zt_count or 0),
        "dt_count": int(dt_count or 0),
    }


def _build_limit_pool_snapshot(rows, daily_rows, industry_map=None):
    zt_pool = []
    dt_pool = []
    for row in rows or []:
        if _is_limit_up_row(row):
            normalized = _normalize_limit_row(row or {}, direction="up", industry_map=industry_map)
            if normalized:
                zt_pool.append(normalized)
        elif _is_limit_down_row(row):
            normalized = _normalize_limit_row(row or {}, direction="down", industry_map=industry_map)
            if normalized:
                dt_pool.append(normalized)
    zt_pool.sort(key=lambda item: (-_safe_int(item.get("连板数"), 1), item.get("首次封板时间") or "99:99:99", item.get("代码") or ""))
    dt_pool.sort(key=lambda item: (item.get("代码") or ""))
    return {
        "zt_pool": zt_pool,
        "dt_pool": dt_pool,
        "limit_up_codes": {item["代码"] for item in zt_pool if item.get("代码")},
        "limit_down_codes": {item["代码"] for item in dt_pool if item.get("代码")},
        "market_stats": _market_stats_from_daily_rows(daily_rows or [], len(zt_pool), len(dt_pool)),
        "provider": "tushare.limit_list_ths",
        "fallback_used": False,
        "source_status": "success",
        "source_error": "",
    }


def _merge_fallback_market_stats_with_daily_breadth(fallback, daily_rows):
    fallback = dict(fallback or {})
    fallback_stats = dict(fallback.get("market_stats") or {})
    daily_stats = _market_stats_from_daily_rows(
        daily_rows or [],
        fallback_stats.get("zt_count", len(fallback.get("zt_pool") or [])),
        fallback_stats.get("dt_count", len(fallback.get("dt_pool") or [])),
    )
    if daily_stats.get("up_count") > 0 and daily_stats.get("down_count") > 0:
        fallback_stats["up_count"] = daily_stats["up_count"]
        fallback_stats["down_count"] = daily_stats["down_count"]
        fallback_stats.setdefault("zt_count", daily_stats["zt_count"])
        fallback_stats.setdefault("dt_count", daily_stats["dt_count"])
    fallback["market_stats"] = fallback_stats
    return fallback


def get_limit_pool_snapshot_from_tushare_first(
    target_date=None,
    *,
    fetch_tushare_limit_rows_fn=None,
    fetch_stock_daily_turnover_records_fn=None,
    fetch_stock_industry_map_fn=None,
    legacy_get_limit_pool_snapshot_fn=None,
    retry_sleep_fn=None,
):
    limit_fetcher = fetch_tushare_limit_rows_fn or fetch_tushare_limit_rows
    daily_fetcher = fetch_stock_daily_turnover_records_fn or fetch_stock_daily_turnover_records
    daily_rows = []
    try:
        rows = limit_fetcher(target_date) or []
        if not rows:
            if callable(retry_sleep_fn):
                try:
                    retry_sleep_fn(1)
                except Exception:
                    pass
                rows = limit_fetcher(target_date) or []
            elif retry_sleep_fn is None:
                try:
                    import time

                    time.sleep(1)
                except Exception:
                    pass
                rows = limit_fetcher(target_date) or []
        if rows:
            try:
                daily_rows = daily_fetcher(target_date) if callable(daily_fetcher) else []
            except Exception:
                daily_rows = []
            industry_map_loader = fetch_stock_industry_map_fn or fetch_stock_industry_map
            try:
                industry_map = industry_map_loader() if callable(industry_map_loader) else {}
            except Exception:
                industry_map = {}
            snapshot = _build_limit_pool_snapshot(rows, daily_rows, industry_map=industry_map)
            if snapshot["zt_pool"] or snapshot["dt_pool"]:
                return snapshot
    except Exception:
        pass

    if callable(legacy_get_limit_pool_snapshot_fn):
        fallback = legacy_get_limit_pool_snapshot_fn(target_date=target_date) or {}
        if not daily_rows:
            try:
                daily_rows = daily_fetcher(target_date) if callable(daily_fetcher) else []
            except Exception:
                daily_rows = []
        fallback = _merge_fallback_market_stats_with_daily_breadth(fallback, daily_rows)
        return {
            **fallback,
            "provider": "legacy.limit_pool_snapshot",
            "fallback_used": True,
            "source_status": "fallback",
            "source_error": fallback.get("source_error", "") if isinstance(fallback, dict) else "",
        }
    if not daily_rows:
        try:
            daily_rows = daily_fetcher(target_date) if callable(daily_fetcher) else []
        except Exception:
            daily_rows = []
    daily_stats = _market_stats_from_daily_rows(daily_rows or [], 0, 0)
    if daily_stats.get("up_count") > 0 and daily_stats.get("down_count") > 0:
        return {
            "zt_pool": [],
            "dt_pool": [],
            "limit_up_codes": set(),
            "limit_down_codes": set(),
            "market_stats": daily_stats,
            "provider": "tushare.daily",
            "fallback_used": True,
            "source_status": "daily_breadth_only",
            "source_error": "limit_pool_empty",
        }
    return {
        "zt_pool": [],
        "dt_pool": [],
        "limit_up_codes": set(),
        "limit_down_codes": set(),
        "market_stats": {},
        "provider": "legacy.limit_pool_snapshot",
        "fallback_used": True,
        "source_status": "empty",
        "source_error": "empty_result",
    }


def _change_pct(latest_bar, prev_bar):
    close_price = _safe_float((latest_bar or {}).get("close"))
    prev_close = _safe_float((prev_bar or {}).get("close"))
    open_price = _safe_float((latest_bar or {}).get("open"))
    if prev_close > 0:
        return (close_price - prev_close) / prev_close * 100
    if open_price > 0:
        return (close_price - open_price) / open_price * 100
    return 0.0


def _latest_index_payload(name, code, bars):
    normalized_bars = [
        {**(bar or {}), "date": normalize_kline_date_str((bar or {}).get("date"))}
        for bar in (bars or [])
    ]
    normalized_bars = [bar for bar in normalized_bars if bar.get("date")]
    normalized_bars.sort(key=lambda item: item.get("date", ""))
    if not normalized_bars:
        return None

    latest_bar = normalized_bars[-1]
    prev_bar = normalized_bars[-2] if len(normalized_bars) >= 2 else {}
    close_price = _safe_float(latest_bar.get("close"))
    if close_price <= 0:
        return None

    change_pct = _change_pct(latest_bar, prev_bar)
    return {
        "name": name,
        "code": code,
        "price": close_price,
        "open": _safe_float(latest_bar.get("open")),
        "close": close_price,
        "high": _safe_float(latest_bar.get("high")),
        "low": _safe_float(latest_bar.get("low")),
        "change_pct": change_pct,
        "turnover": _safe_float(latest_bar.get("amount_yi")),
        "涨跌幅": change_pct,
        "data_source": "tushare.index_daily",
        "trade_date": latest_bar.get("date"),
    }


def _index_query_window(target_date):
    query_date = _resolve_query_date(target_date)
    end_date = query_date.strftime("%Y-%m-%d")
    start_date = (query_date - datetime.timedelta(days=15)).strftime("%Y-%m-%d")
    return start_date, end_date


def get_major_indices_from_tushare_first(
    target_date=None,
    *,
    fetch_daily_price_bars_fn=None,
    legacy_get_major_indices_fn=None,
):
    fetcher = fetch_daily_price_bars_fn or fetch_daily_price_bars
    start_date, end_date = _index_query_window(target_date)
    index_map = {
        "上证指数": "000001",
        "深证成指": "399001",
        "创业板指": "399006",
    }

    try:
        indices = {}
        for name, code in index_map.items():
            payload = _latest_index_payload(
                name,
                code,
                fetcher(code, start_date, end_date, is_index=True),
            )
            if payload:
                indices[name] = payload
        if len(indices) >= 3:
            return indices
    except Exception:
        pass

    fallback = _fallback_call(legacy_get_major_indices_fn, target_date)
    return fallback or {}


def _get_single_index_from_tushare_first(
    name,
    code,
    target_date=None,
    *,
    fetch_daily_price_bars_fn=None,
    legacy_get_index_fn=None,
):
    fetcher = fetch_daily_price_bars_fn or fetch_daily_price_bars
    start_date, end_date = _index_query_window(target_date)

    try:
        payload = _latest_index_payload(
            name,
            code,
            fetcher(code, start_date, end_date, is_index=True),
        )
        if payload and _safe_float(payload.get("price")) > 0:
            return payload
    except Exception:
        pass

    fallback = _fallback_call(legacy_get_index_fn, target_date)
    return fallback or {"price": 0, "change_pct": 0}


def get_wind_a_from_tushare_first(
    target_date=None,
    *,
    fetch_daily_price_bars_fn=None,
    legacy_get_wind_a_fn=None,
):
    return _get_single_index_from_tushare_first(
        "中证全指",
        "000985",
        target_date,
        fetch_daily_price_bars_fn=fetch_daily_price_bars_fn,
        legacy_get_index_fn=legacy_get_wind_a_fn,
    )


def get_csi1000_from_tushare_first(
    target_date=None,
    *,
    fetch_daily_price_bars_fn=None,
    legacy_get_csi1000_fn=None,
):
    return _get_single_index_from_tushare_first(
        "中证1000",
        "000852",
        target_date,
        fetch_daily_price_bars_fn=fetch_daily_price_bars_fn,
        legacy_get_index_fn=legacy_get_csi1000_fn,
    )
