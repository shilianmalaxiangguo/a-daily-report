from __future__ import annotations

import datetime as _dt

import requests

from market_data.kline_dates import normalize_kline_date_str
from market_data.tushare_client import create_tushare_pro_api

__all__ = [
    "fetch_stock_basic_map",
    "fetch_stock_industry_map",
    "fetch_stock_name_map",
    "fetch_stock_factor_pro_rows",
    "fetch_stock_batch_quote_info",
    "fetch_stock_daily_turnover_records",
    "fetch_stock_daily_turnover_records_range",
    "fetch_market_daily_amount_rows",
    "fetch_market_index_amount_rows",
    "fetch_quicktiny_index_amount_rows",
    "fetch_market_margin_balance_rows",
    "fetch_margin_balance_rows",
    "fetch_stock_moneyflow_map",
    "fetch_stock_turnover_history",
]


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


def _compact_date(date_value):
    normalized = normalize_kline_date_str(date_value)
    return normalized.replace("-", "") if normalized else ""


def _frame_to_records(frame):
    if frame is None:
        return []
    if isinstance(frame, list):
        return list(frame)
    if hasattr(frame, "to_dict"):
        return frame.to_dict("records")
    return []


def _eastmoney_rows(payload):
    if not isinstance(payload, dict):
        return []
    result = payload.get("result") or {}
    rows = result.get("data") or []
    return list(rows) if isinstance(rows, list) else []


def _split_ts_code(ts_code):
    text = str(ts_code or "").strip().upper()
    if "." not in text:
        return "", ""
    code, market = text.split(".", 1)
    code = "".join(ch for ch in code if ch.isdigit()).zfill(6)
    market = market.strip()
    if not code or market not in {"SH", "SZ", "BJ"}:
        return "", ""
    return code, market


def _normalize_ts_code(security_code):
    text = str(security_code or "").strip().upper()
    if not text:
        return ""
    if "." in text:
        left, right = text.split(".", 1)
        if right in {"SH", "SZ", "BJ"}:
            return text
        if left in {"SH", "SZ", "BJ"}:
            return f"{right}.{left}"
    lowered = text.lower()
    if lowered.startswith(("sh", "sz", "bj")) and len(text) > 2:
        return f"{text[2:]}.{text[:2].upper()}"
    code = "".join(ch for ch in text if ch.isdigit()).zfill(6)
    if not code:
        return ""
    if code.startswith(("8", "4", "9")):
        market = "BJ"
    elif code.startswith(("6", "5")):
        market = "SH"
    else:
        market = "SZ"
    return f"{code}.{market}"


def _clean_code(value):
    text = str(value or "").strip().upper()
    if "." in text:
        text = text.split(".", 1)[0]
    for prefix in ("SH", "SZ", "BJ"):
        if text.startswith(prefix):
            text = text[len(prefix):]
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits.zfill(6) if digits else ""


def _normalize_daily_row(row):
    row = row or {}
    trade_date = normalize_kline_date_str(row.get("trade_date"))
    stock_code, market = _split_ts_code(row.get("ts_code"))
    amount_raw = _safe_float(row.get("amount"))
    if not trade_date or not stock_code or amount_raw <= 0:
        return None
    return {
        "trade_date": trade_date,
        "ts_code": str(row.get("ts_code") or "").strip().upper(),
        "stock_code": stock_code,
        "market": market,
        "name": str(row.get("name") or "").strip(),
        "open": _safe_float(row.get("open")),
        "high": _safe_float(row.get("high")),
        "low": _safe_float(row.get("low")),
        "close": _safe_float(row.get("close")),
        "pre_close": _safe_float(row.get("pre_close")),
        "change": _safe_float(row.get("change")),
        "pct_chg": _safe_float(row.get("pct_chg")),
        "vol": _safe_float(row.get("vol")),
        "amount_raw_qianyuan": amount_raw,
        "amount_yi": round(amount_raw / 100000.0, 6),
        "data_source": "tushare.daily",
    }


def _uses_sdk_post_endpoint(pro):
    http_url = str(getattr(pro, "_DataApi__http_url", "") or "").strip().rstrip("/").lower()
    return bool(http_url) and not http_url.endswith("/tushare/pro")


def fetch_stock_daily_turnover_records(
    trade_date,
    *,
    pro=None,
    ts_module=None,
    page_limit=1000,
    page_retry_count=5,
):
    compact = _compact_date(trade_date)
    if not compact:
        return []
    pro = pro or create_tushare_pro_api(ts_module=ts_module, timeout_seconds=30)
    fields = "ts_code,trade_date,open,high,low,close,pre_close,change,pct_chg,vol,amount"
    if _uses_sdk_post_endpoint(pro):
        last_error = None
        for attempt in range(max(int(page_retry_count or 0), 0) + 1):
            try:
                frame = pro.daily(trade_date=compact, fields=fields)
                normalized_rows = [
                    normalized
                    for row in _frame_to_records(frame)
                    if (normalized := _normalize_daily_row(row))
                ]
                if not normalized_rows:
                    raise RuntimeError(f"empty tushare daily result for {compact}")
                return normalized_rows
            except Exception as error:
                last_error = error
                if attempt >= max(int(page_retry_count or 0), 0):
                    raise
                try:
                    import time

                    time.sleep(1)
                except Exception:
                    pass
        raise last_error  # pragma: no cover - retry loop returns or raises

    records = []
    offset = 0
    limit = int(page_limit or 1000)
    while True:
        last_error = None
        page_rows = []
        for attempt in range(max(int(page_retry_count or 0), 0) + 1):
            try:
                frame = pro.daily(
                    start_date=compact,
                    end_date=compact,
                    fields=fields,
                    limit=limit,
                    offset=offset,
                )
                page_rows = _frame_to_records(frame)
                if offset > 0 and not page_rows:
                    raise RuntimeError(f"empty tushare daily page at offset {offset}")
                break
            except Exception as error:
                last_error = error
                if attempt >= max(int(page_retry_count or 0), 0):
                    raise
                try:
                    import time

                    time.sleep(1)
                except Exception:
                    pass
        else:  # pragma: no cover - defensive; loop either breaks or raises
            raise last_error
        for row in page_rows:
            normalized = _normalize_daily_row(row)
            if normalized:
                records.append(normalized)
        if len(page_rows) < limit:
            break
        offset += limit
    return records


def fetch_stock_daily_turnover_records_range(start_date, end_date, *, pro=None, ts_module=None, page_limit=6000):
    start = _compact_date(start_date)
    end = _compact_date(end_date)
    if not start or not end:
        return []
    pro = pro or create_tushare_pro_api(ts_module=ts_module)
    fields = "ts_code,trade_date,open,high,low,close,pre_close,change,pct_chg,vol,amount"
    rows = []
    offset = 0
    limit = int(page_limit or 6000)
    while True:
        frame = pro.daily(
            start_date=start,
            end_date=end,
            fields=fields,
            limit=limit,
            offset=offset,
        )
        page_rows = _frame_to_records(frame)
        for row in page_rows:
            normalized = _normalize_daily_row(row)
            if normalized:
                rows.append(normalized)
        if len(page_rows) < limit:
            break
        offset += limit
    return rows


def _is_hs_a_share_ts_code(ts_code):
    text = str(ts_code or "").strip().upper()
    if not text.endswith((".SH", ".SZ")):
        return False
    code = text.split(".", 1)[0]
    if code.startswith(("900", "200")):
        return False
    return True


def fetch_market_daily_amount_rows(start_date, end_date, *, pro=None, ts_module=None, page_limit=6000):
    start = _compact_date(start_date)
    end = _compact_date(end_date)
    if not start or not end:
        return []
    pro = pro or create_tushare_pro_api(ts_module=ts_module)
    rows = []
    offset = 0
    while True:
        frame = pro.daily(
            start_date=start,
            end_date=end,
            fields="ts_code,trade_date,amount",
            limit=int(page_limit or 6000),
            offset=offset,
        )
        page_rows = _frame_to_records(frame)
        rows.extend(page_rows)
        if len(page_rows) < int(page_limit or 6000):
            break
        offset += int(page_limit or 6000)
    buckets = {}
    for row in rows:
        ts_code = str((row or {}).get("ts_code") or "").strip().upper()
        if not _is_hs_a_share_ts_code(ts_code):
            continue
        trade_date = normalize_kline_date_str((row or {}).get("trade_date"))
        amount_raw = _safe_float((row or {}).get("amount"))
        if not trade_date or amount_raw <= 0:
            continue
        bucket = buckets.setdefault(trade_date, {"trade_date": trade_date, "market_turnover_yi": 0.0, "stock_count": 0})
        bucket["market_turnover_yi"] += amount_raw / 100000.0
        bucket["stock_count"] += 1
    return sorted(
        [
            {
                **item,
                "market_turnover_yi": round(item.get("market_turnover_yi", 0.0), 6),
                "source_policy": "tushare.daily",
            }
            for item in buckets.values()
        ],
        key=lambda item: item.get("trade_date", ""),
    )


def fetch_market_index_amount_rows(
    start_date,
    end_date,
    *,
    pro=None,
    ts_module=None,
    index_codes=("000001.SH", "399001.SZ"),
    quicktiny_fetcher=None,
):
    start = _compact_date(start_date)
    end = _compact_date(end_date)
    if not start or not end:
        return []
    if pro is None:
        try:
            pro = create_tushare_pro_api(ts_module=ts_module)
        except Exception:
            pro = None
    buckets = {}
    if pro is not None:
        for ts_code in index_codes or ():
            try:
                frame = pro.index_daily(ts_code=ts_code, start_date=start, end_date=end)
            except Exception:
                continue
            for row in _frame_to_records(frame):
                trade_date = normalize_kline_date_str((row or {}).get("trade_date"))
                amount_raw = _safe_float((row or {}).get("amount"))
                if not trade_date or amount_raw <= 0:
                    continue
                bucket = buckets.setdefault(
                    trade_date,
                    {
                        "trade_date": trade_date,
                        "market_turnover_yi": 0.0,
                        "index_count": 0,
                    },
                )
                bucket["market_turnover_yi"] += amount_raw / 100000.0
                bucket["index_count"] += 1
    primary_rows = [
        {
            **item,
            "market_turnover_yi": round(item.get("market_turnover_yi", 0.0), 6),
            "stock_count": item.get("index_count", 0),
            "source_policy": "tushare.index_daily.market_amount",
            "source_date": item.get("trade_date", ""),
            "query_date": normalize_kline_date_str(end_date),
        }
        for item in buckets.values()
    ]
    expected_index_count = len(tuple(index_codes or ()))
    primary_by_date = {row.get("trade_date"): row for row in primary_rows}
    target_row = primary_by_date.get(normalize_kline_date_str(end_date)) or {}
    target_is_complete = (
        _safe_int(target_row.get("index_count")) >= expected_index_count
        and _safe_float(target_row.get("market_turnover_yi")) > 0
    )
    if target_is_complete:
        return sorted(primary_rows, key=lambda item: item.get("trade_date", ""))

    fallback_fetcher = quicktiny_fetcher or fetch_quicktiny_index_amount_rows
    try:
        fallback_rows = fallback_fetcher(start_date, end_date, index_codes=index_codes) or []
    except Exception:
        fallback_rows = []
    for row in fallback_rows:
        item = dict(row or {})
        trade_date = normalize_kline_date_str(item.get("trade_date") or item.get("date"))
        if not trade_date or not (_compact_date(start_date) <= trade_date.replace("-", "") <= _compact_date(end_date)):
            continue
        if _safe_float(item.get("market_turnover_yi")) <= 0:
            continue
        if _safe_int(item.get("index_count")) < expected_index_count:
            continue
        existing = primary_by_date.get(trade_date) or {}
        if (
            _safe_int(existing.get("index_count")) < expected_index_count
            or _safe_float(existing.get("market_turnover_yi")) <= 0
        ):
            primary_by_date[trade_date] = {
                **item,
                "trade_date": trade_date,
                "market_turnover_yi": round(_safe_float(item.get("market_turnover_yi")), 6),
                "stock_count": _safe_int(item.get("stock_count", item.get("index_count"))),
                "index_count": _safe_int(item.get("index_count")),
                "source_policy": item.get("source_policy") or "quicktiny.merged_kline.index_daily.market_amount",
                "source_date": normalize_kline_date_str(item.get("source_date") or trade_date),
                "query_date": normalize_kline_date_str(item.get("query_date") or end_date),
            }
    return sorted(primary_by_date.values(), key=lambda item: item.get("trade_date", ""))


def fetch_quicktiny_index_amount_rows(
    start_date,
    end_date,
    *,
    index_codes=("000001.SH", "399001.SZ"),
    session=None,
):
    """Use QuickTiny's index_daily mirror only when Tushare lacks the target date."""
    start = normalize_kline_date_str(start_date)
    end = normalize_kline_date_str(end_date)
    if not start or not end or start > end:
        return []
    try:
        start_day = _dt.date.fromisoformat(start)
        end_day = _dt.date.fromisoformat(end)
    except ValueError:
        return []
    days = max((end_day - start_day).days + 10, 20)
    client = session or requests.Session()
    owns_session = session is None
    if owns_session:
        client.trust_env = False
    buckets = {}
    try:
        for ts_code in index_codes or ():
            code, market = _split_ts_code(ts_code)
            if not code or market not in {"SH", "SZ"}:
                continue
            symbol = f"{market.lower()}{code}"
            response = client.get(
                f"https://stock.quicktiny.cn/api/tushare/merged-kline/{symbol}?days={days}",
                timeout=(2, 6),
            )
            response.raise_for_status()
            payload = response.json()
            rows = payload.get("data") if isinstance(payload, dict) else []
            for row in rows or []:
                source = str((row or {}).get("source") or "").strip()
                trade_date = normalize_kline_date_str((row or {}).get("date"))
                amount_raw = _safe_float((row or {}).get("amount"))
                if (
                    source not in {"", "index_daily"}
                    or not trade_date
                    or not (start <= trade_date <= end)
                    or amount_raw <= 0
                ):
                    continue
                bucket = buckets.setdefault(
                    trade_date,
                    {"trade_date": trade_date, "market_turnover_yi": 0.0, "index_count": 0},
                )
                bucket["market_turnover_yi"] += amount_raw / 1e8
                bucket["index_count"] += 1
    finally:
        if owns_session:
            client.close()
    return sorted(
        [
            {
                **item,
                "market_turnover_yi": round(item.get("market_turnover_yi", 0.0), 6),
                "stock_count": item.get("index_count", 0),
                "source_policy": "quicktiny.merged_kline.index_daily.market_amount",
                "source_date": item.get("trade_date", ""),
                "query_date": end,
            }
            for item in buckets.values()
        ],
        key=lambda item: item.get("trade_date", ""),
    )


def fetch_market_margin_balance_rows(start_date, end_date, *, session=None):
    start = normalize_kline_date_str(start_date)
    end = normalize_kline_date_str(end_date)
    if not start or not end:
        return []
    client = session or requests
    params = {
        "reportName": "RPTA_RZRQ_LSHJ",
        "columns": "ALL",
        "source": "WEB",
        "sortColumns": "DIM_DATE",
        "sortTypes": "-1",
        "pageNumber": "1",
        "pageSize": "500",
        "filter": "",
    }
    response = client.get(
        "https://datacenter-web.eastmoney.com/api/data/v1/get",
        params=params,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://data.eastmoney.com/rzrq/total.html",
        },
        timeout=20,
    )
    payload = response.json()
    rows = []
    for row in _eastmoney_rows(payload):
        trade_date = normalize_kline_date_str((row or {}).get("DIM_DATE"))
        margin_balance = _safe_float((row or {}).get("RZYE")) / 1e8
        short_balance = _safe_float((row or {}).get("RQYE")) / 1e8
        margin_trading_balance = _safe_float((row or {}).get("RZRQYE")) / 1e8
        if not trade_date or trade_date < start or trade_date > end or margin_balance <= 0:
            continue
        rows.append(
            {
                "trade_date": trade_date,
                "margin_balance_yi": round(margin_balance, 6),
                "short_selling_balance_yi": round(short_balance, 6),
                "margin_trading_balance_yi": round(margin_trading_balance, 6),
                "exchange_count": 1,
                "is_market_level_margin_balance": True,
                "source_policy": "eastmoney.rzrq.total.RZYE",
            }
        )
    return sorted(rows, key=lambda item: item.get("trade_date", ""))


def fetch_margin_balance_rows(start_date, end_date, *, pro=None, ts_module=None):
    start = _compact_date(start_date)
    end = _compact_date(end_date)
    if not start or not end:
        return []
    pro = pro or create_tushare_pro_api(ts_module=ts_module)
    frame = pro.margin(start_date=start, end_date=end)
    buckets = {}
    for row in _frame_to_records(frame):
        trade_date = normalize_kline_date_str((row or {}).get("trade_date"))
        if not trade_date:
            continue
        bucket = buckets.setdefault(
            trade_date,
            {
                "trade_date": trade_date,
                "margin_balance_yi": 0.0,
                "short_selling_balance_yi": 0.0,
                "margin_trading_balance_yi": 0.0,
                "exchange_ids": set(),
            },
        )
        exchange_id = str((row or {}).get("exchange_id") or "").strip()
        if exchange_id:
            bucket["exchange_ids"].add(exchange_id)
        bucket["margin_balance_yi"] += _safe_float((row or {}).get("rzye")) / 1e8
        bucket["short_selling_balance_yi"] += _safe_float((row or {}).get("rqye")) / 1e8
        bucket["margin_trading_balance_yi"] += _safe_float((row or {}).get("rzrqye")) / 1e8
    result = []
    for item in buckets.values():
        result.append(
            {
                "trade_date": item["trade_date"],
                "margin_balance_yi": round(item["margin_balance_yi"], 6),
                "short_selling_balance_yi": round(item["short_selling_balance_yi"], 6),
                "margin_trading_balance_yi": round(item["margin_trading_balance_yi"], 6),
                "exchange_count": len(item["exchange_ids"]),
                "source_policy": "tushare.margin",
            }
        )
    return sorted(result, key=lambda item: item.get("trade_date", ""))


def fetch_stock_basic_map(*, pro=None, ts_module=None):
    pro = pro or create_tushare_pro_api(ts_module=ts_module)
    frame = pro.stock_basic(
        exchange="",
        list_status="L",
        fields="ts_code,name,industry,list_date",
    )
    mapping = {}
    for row in _frame_to_records(frame):
        stock_code, _market = _split_ts_code(row.get("ts_code"))
        if not stock_code:
            continue
        item = {
            "name": str(row.get("name") or "").strip(),
            "industry": str(row.get("industry") or "").strip(),
            "list_date": str(row.get("list_date") or "").strip(),
        }
        if not item["name"] and not item["industry"] and not item["list_date"]:
            continue
        ts_code = str(row.get("ts_code") or "").strip().upper()
        mapping[stock_code] = item
        if ts_code:
            mapping[ts_code] = item
    return mapping


def fetch_stock_factor_pro_rows(trade_date, *, pro=None, ts_module=None):
    compact = _compact_date(trade_date)
    if not compact:
        return []
    pro = pro or create_tushare_pro_api(ts_module=ts_module)
    fields = "ts_code,trade_date,open,high,low,close,pct_chg,vol,amount,topdays"
    page_limit = 6000
    rows = []
    offset = 0
    while True:
        frame = pro.stk_factor_pro(trade_date=compact, fields=fields, limit=page_limit, offset=offset)
        page_rows = _frame_to_records(frame)
        rows.extend(page_rows)
        if len(page_rows) < page_limit:
            break
        offset += page_limit
    return rows


def fetch_stock_industry_map(*, pro=None, ts_module=None):
    mapping = {}
    for key, item in fetch_stock_basic_map(pro=pro, ts_module=ts_module).items():
        industry = str(item.get("industry") or "").strip()
        if not industry:
            continue
        mapping[key] = industry
    return mapping


def fetch_stock_name_map(*, pro=None, ts_module=None):
    mapping = {}
    for key, item in fetch_stock_basic_map(pro=pro, ts_module=ts_module).items():
        name = str(item.get("name") or "").strip()
        if name:
            mapping[key] = name
    return mapping


def _resolve_stock_basic_item(name_map, code):
    item = (name_map or {}).get(code) or {}
    if isinstance(item, dict):
        return item
    return {"name": str(item or "").strip()}


def _resolve_stock_industry(basic_item):
    industry = str((basic_item or {}).get("industry") or "").strip()
    if not industry or industry in {"HS", "GEM", "STAR", "BJ", "SH", "SZ"}:
        return ""
    return industry


def _quote_status_from_pct(change_pct):
    if change_pct >= 9.9:
        return "涨停"
    if change_pct <= -9.9:
        return "跌停"
    return "正常"


def fetch_stock_batch_quote_info(
    codes,
    trade_date,
    *,
    fetch_daily_records_fn=None,
    fetch_name_map_fn=None,
):
    wanted = {_clean_code(code) for code in codes or []}
    wanted.discard("")
    if not wanted:
        return {}

    fetch_daily_records_fn = fetch_daily_records_fn or fetch_stock_daily_turnover_records
    fetch_name_map_fn = fetch_name_map_fn or fetch_stock_basic_map
    name_map = fetch_name_map_fn() or {}
    daily_records = fetch_daily_records_fn(trade_date) or []
    result = {}

    for row in daily_records:
        code = _clean_code((row or {}).get("stock_code") or (row or {}).get("ts_code"))
        if code not in wanted:
            continue
        basic_item = _resolve_stock_basic_item(name_map, code)
        name = str((row or {}).get("name") or basic_item.get("name") or "").strip()
        industry = _resolve_stock_industry(basic_item)
        change_pct = _safe_float((row or {}).get("pct_chg"))
        result[code] = {
            "name": name,
            "industry": industry,
            "所属行业": industry,
            "change_pct": round(change_pct, 2),
            "high": _safe_float((row or {}).get("high")),
            "low": _safe_float((row or {}).get("low")),
            "open": _safe_float((row or {}).get("open")),
            "close": _safe_float((row or {}).get("close")),
            "turnover": _safe_float((row or {}).get("amount_yi")),
            "zt_status": _quote_status_from_pct(change_pct),
            "data_source": (row or {}).get("data_source") or "tushare.daily",
            "trade_date": str(trade_date or "").strip(),
        }
    return result


def fetch_stock_moneyflow_map(trade_date, *, pro=None, ts_module=None):
    compact = _compact_date(trade_date)
    if not compact:
        return {}
    pro = pro or create_tushare_pro_api(ts_module=ts_module)
    frame = pro.moneyflow(trade_date=compact)
    mapping = {}
    for row in _frame_to_records(frame):
        stock_code, _market = _split_ts_code(row.get("ts_code"))
        net_amount = _safe_float(row.get("net_mf_amount"))
        if not stock_code:
            continue
        net_inflow_yi = round(net_amount / 10000.0, 6)
        ts_code = str(row.get("ts_code") or "").strip().upper()
        mapping[stock_code] = net_inflow_yi
        if ts_code:
            mapping[ts_code] = net_inflow_yi
    return mapping


def fetch_stock_turnover_history(security_code, start_date, end_date, *, pro=None, ts_module=None):
    start = _compact_date(start_date)
    end = _compact_date(end_date)
    ts_code = _normalize_ts_code(security_code)
    if not ts_code or not start or not end:
        return []
    pro = pro or create_tushare_pro_api(ts_module=ts_module)
    frame = pro.daily(ts_code=ts_code, start_date=start, end_date=end)
    rows = []
    for row in _frame_to_records(frame):
        normalized = _normalize_daily_row(row)
        if normalized:
            rows.append(normalized)
    rows.sort(key=lambda item: item.get("trade_date", ""))
    return [item["amount_yi"] for item in rows if _safe_float(item.get("amount_yi")) > 0]
