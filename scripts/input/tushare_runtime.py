from __future__ import annotations

import datetime
import json

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


def get_total_turnover_from_tushare_first(
    target_date=None,
    *,
    fetch_stock_daily_turnover_records_fn=None,
    legacy_get_total_turnover_fn=None,
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
    return ProviderValue(
        _safe_float(fallback),
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
    if database_service_cls is None:
        try:
            from storage.database_service import DatabaseService
        except Exception:  # pragma: no cover - optional runtime dependency
            DatabaseService = None
        database_service_cls = DatabaseService
    if database_service_cls is not None:
        try:
            local_service = database_service_cls.sqlite_d1_compatible(db_path)
        except Exception:
            local_service = None
    if not factor_rows and local_service is not None:
        try:
            raw_history_rows = local_service.query_new_high_feedback_series(
                target_date_text or factor_trade_date,
                window_days=25,
            )
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
            service = local_service or (database_service_cls.sqlite_d1_compatible(db_path) if database_service_cls is not None else None)
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
                    service = database_service_cls.sqlite_d1_compatible(db_path) if database_service_cls is not None else None
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
    if database_service_cls is None:
        from storage.database_service import DatabaseService

        database_service_cls = DatabaseService
    try:
        service = database_service_cls.sqlite_d1_compatible(db_path)
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


PRICE_BAND_HIGH_PRICE_CODE = "883916.TI"
PRICE_BAND_LOW_PRICE_CODE = "883960.TI"


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


def _build_price_band_style_payload(rows, *, source="tushare.ths_daily.price_band_style"):
    rows = list(rows or [])[-25:]
    for row in rows:
        row["spread_pct"] = _price_band_spread_pct(
            (row or {}).get("high_price_pct"),
            (row or {}).get("low_price_pct"),
        )
        row["style_label"] = _price_band_style_label(row.get("spread_pct"))
    high_total = sum(_safe_float((row or {}).get("high_price_pct")) for row in rows)
    low_total = sum(_safe_float((row or {}).get("low_price_pct")) for row in rows)
    spread_total = sum(_safe_float((row or {}).get("spread_pct")) for row in rows)
    latest_row = rows[-1] if rows else {}
    latest_spread = _safe_float((latest_row or {}).get("spread_pct"))
    latest_label = (latest_row or {}).get("style_label") or _price_band_style_label(latest_spread)
    summary = ""
    if rows:
        summary = (
            f"近{len(rows)}个交易日价格带风格："
            f"最新差值 {latest_spread:+.2f}pct，当前为{latest_label}；"
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
        "rows": rows,
        "summary": summary if rows else "价格带风格趋势待累计。",
    }


def get_price_band_style_series_from_tushare_first(
    target_date=None,
    *,
    window_days=25,
    fetch_tushare_open_trade_dates_fn=None,
    fetch_tushare_ths_daily_fn=None,
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
    if should_use_fact_db and database_service_cls is None:
        try:
            from storage.database_service import DatabaseService
        except Exception:  # pragma: no cover - optional runtime dependency
            DatabaseService = None
        database_service_cls = DatabaseService
    if should_use_fact_db and database_service_cls is not None:
        try:
            service = database_service_cls.sqlite_d1_compatible(db_path)
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
        for trade_date in trade_dates:
            if service is not None and trade_date in existing_dates:
                continue
            daily_rows = daily_fetcher(trade_date) or []
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
        if service is not None:
            try:
                refreshed = service.query_price_band_style_series(target_date_text, window_days=window_days)
                refreshed_rows = (refreshed or {}).get("rows") if isinstance(refreshed, dict) else []
                if refreshed_rows:
                    return _build_price_band_style_payload(
                        refreshed_rows,
                        source=(refreshed or {}).get("source") or "storage.price_band_style_daily",
                    )
            except Exception:
                pass
        return _build_price_band_style_payload(rows)
    except Exception as error:
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
    if should_use_fact_db and database_service_cls is None:
        try:
            from storage.database_service import DatabaseService
        except Exception:  # pragma: no cover - optional runtime dependency
            DatabaseService = None
        database_service_cls = DatabaseService
    if should_use_fact_db and database_service_cls is not None:
        try:
            service = database_service_cls.sqlite_d1_compatible(db_path)
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
        if not primary_snapshot.get("available") and primary_snapshot.get("status") == "incomplete_exchange_rows":
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
):
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
                        "data_source": "tushare.daily",
                        "trade_date": row.get("trade_date"),
                    }
                )
            return ranked
    except Exception:
        pass

    if callable(legacy_get_turnover_rank_fn):
        return legacy_get_turnover_rank_fn(target_date=target_date, limit=limit) or []
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
    limit=30,
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


def get_hot_concept_fund_flow_from_tushare_first(
    target_date=None,
    *,
    hot_plates=None,
    limit=20,
    fetch_tushare_ths_member_fn=None,
    fetch_stock_moneyflow_map_fn=None,
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
        return {"rows": [], "inflow": [], "outflow": [], "provider": "tushare.ths_member+tushare.moneyflow", "fallback_used": False}

    member_fetcher = fetch_tushare_ths_member_fn or fetch_tushare_ths_member
    moneyflow_fetcher = fetch_stock_moneyflow_map_fn or fetch_stock_moneyflow_map
    try:
        stock_moneyflow = moneyflow_fetcher(target_date) or {}
    except Exception:
        stock_moneyflow = {}
    if not stock_moneyflow:
        return {"rows": [], "inflow": [], "outflow": [], "provider": "tushare.ths_member+tushare.moneyflow", "fallback_used": True}

    rows = []
    for plate in concept_plates:
        code = str(plate.get("code") or plate.get("ts_code") or "").strip().upper()
        name = _clean_text(plate.get("name"))
        try:
            member_rows = list(member_fetcher(code) or [])
        except Exception:
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
        item = {
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
        rows.append(item)

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


def get_sector_change_rank_from_tushare_first(
    target_date=None,
    *,
    rank_type="up",
    limit=10,
    fetch_tushare_ths_daily_fn=None,
    fetch_tushare_ths_index_map_fn=None,
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


def get_limit_pool_snapshot_from_tushare_first(
    target_date=None,
    *,
    fetch_tushare_limit_rows_fn=None,
    fetch_stock_daily_turnover_records_fn=None,
    fetch_stock_industry_map_fn=None,
    legacy_get_limit_pool_snapshot_fn=None,
):
    limit_fetcher = fetch_tushare_limit_rows_fn or fetch_tushare_limit_rows
    daily_fetcher = fetch_stock_daily_turnover_records_fn or fetch_stock_daily_turnover_records
    try:
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
        return {
            **fallback,
            "provider": "legacy.limit_pool_snapshot",
            "fallback_used": True,
            "source_status": "fallback",
            "source_error": fallback.get("source_error", "") if isinstance(fallback, dict) else "",
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


def get_wind_a_from_tushare_first(
    target_date=None,
    *,
    fetch_daily_price_bars_fn=None,
    legacy_get_wind_a_fn=None,
):
    fetcher = fetch_daily_price_bars_fn or fetch_daily_price_bars
    start_date, end_date = _index_query_window(target_date)

    try:
        payload = _latest_index_payload(
            "中证全指",
            "000985",
            fetcher("000985", start_date, end_date, is_index=True),
        )
        if payload and _safe_float(payload.get("price")) > 0:
            return payload
    except Exception:
        pass

    fallback = _fallback_call(legacy_get_wind_a_fn, target_date)
    return fallback or {"price": 0, "change_pct": 0}
