from __future__ import annotations

import datetime
import json

from market_data.kline_dates import normalize_kline_date_str
from market_data.tushare_service import fetch_daily_price_bars
from market_data.tushare_market_activity_service import (
    fetch_tushare_limit_rows,
    fetch_tushare_new_share,
    fetch_tushare_open_trade_dates,
    fetch_tushare_sector_flow,
    fetch_tushare_ths_daily,
    fetch_tushare_ths_hot,
    fetch_tushare_ths_index_map,
    fetch_tushare_top_list,
)
from market_data.tushare_turnover_service import (
    fetch_stock_daily_turnover_records,
    fetch_stock_industry_map,
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
    "get_sector_change_rank_from_tushare_first",
    "get_sector_fund_flow_from_tushare_first",
    "get_lhb_snapshot_from_tushare_first",
    "get_new_stock_calendar_from_tushare_first",
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


def _is_tushare_a_share_industry_index(meta):
    meta = meta or {}
    if str(meta.get("exchange") or "").strip().upper() != "A":
        return False
    return str(meta.get("type") or "").strip().upper() == "I"


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
        reverse = rank_type != "down"
        rows.sort(key=lambda item: (_safe_float(item.get("change_pct")), item.get("name") or ""), reverse=reverse)
        if rows:
            ranked = rows[: max(int(limit or 10), 1)]
            for rank, item in enumerate(ranked, start=1):
                item["rank"] = rank
            return ranked
    except Exception:
        pass

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
        return {**fallback, "provider": "legacy.lhb_snapshot", "fallback_used": True}
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
    try:
        if callable(next_trade_date_fn):
            next_trade_date = normalize_kline_date_str(next_trade_date_fn(target_date))
        else:
            next_trade_date = _next_trade_date_from_tushare(
                target_date,
                fetch_open_trade_dates_fn=fetch_tushare_open_trade_dates_fn,
            )
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


def _normalize_limit_row(row, *, direction):
    code = _clean_code(_pick(row, "ts_code", "code", "代码", default=""))
    if not code:
        return None
    first_time = _pick(row, "first_time", "first_lu_time", "first_ld_time", "首次封板时间", default="")
    last_time = _pick(row, "last_time", "last_lu_time", "last_ld_time", "最后封板时间", default="")
    lianban_days = _infer_lianban_days(row)
    industry = str(_pick(row, "industry", "所属行业", "行业", default="未知")).strip() or "未知"
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


def _build_limit_pool_snapshot(rows, daily_rows):
    zt_pool = []
    dt_pool = []
    for row in rows or []:
        if _is_limit_up_row(row):
            normalized = _normalize_limit_row(row or {}, direction="up")
            if normalized:
                zt_pool.append(normalized)
        elif _is_limit_down_row(row):
            normalized = _normalize_limit_row(row or {}, direction="down")
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
            snapshot = _build_limit_pool_snapshot(rows, daily_rows)
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
