from __future__ import annotations

import json
import os
import datetime
import urllib.parse
import urllib.request
from pathlib import Path

from market_data.kline_dates import normalize_kline_date_str
from market_data.tushare_client import create_tushare_pro_api

__all__ = [
    "fetch_cyberfininvest_news_rows",
    "fetch_investor_qa_rows",
    "fetch_tushare_announcement_rows",
    "fetch_tushare_holdertrade_rows",
    "fetch_tushare_limit_rows",
    "fetch_tushare_new_share",
    "fetch_tushare_open_trade_dates",
    "fetch_tushare_sector_flow",
    "fetch_tushare_shock_rows",
    "fetch_tushare_st_rows",
    "fetch_tushare_stock_st_rows",
    "fetch_tushare_ths_daily",
    "fetch_tushare_ths_hot",
    "fetch_tushare_ths_index_map",
    "fetch_tushare_ths_member",
    "fetch_tushare_top_inst",
    "fetch_tushare_top_list",
]

CYBERFININVEST_NEWS_URL = "https://cyberfininvest.com/api/news/list"
CYBERFININVEST_AUTH_ENV = "CYBERFININVEST_AUTHORIZATION"
INVESTOR_QA_ENDPOINT_ENV = "INVESTOR_QA_ENDPOINT_URL"


def _load_local_env_file():
    candidates = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parent.parent.parent / ".env",
    ]
    for env_path in candidates:
        if not env_path.exists():
            continue
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and value:
                os.environ.setdefault(key, value)
        return


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


def fetch_cyberfininvest_news_rows(
    trade_date=None,
    *,
    authorization=None,
    page=1,
    size=100,
    timeout_seconds=8,
    opener=None,
):
    _load_local_env_file()
    token = authorization or os.environ.get(CYBERFININVEST_AUTH_ENV, "")
    if not token:
        return []
    query = urllib.parse.urlencode({"category": 3, "type": 0, "page": int(page or 1), "size": int(size or 100)})
    request = urllib.request.Request(
        f"{CYBERFININVEST_NEWS_URL}?{query}",
        headers={
            "Accept": "application/json, text/plain, */*",
            "Authorization": token,
            "Referer": "https://cyberfininvest.com/workstation/news-analysis",
            "User-Agent": "Mozilla/5.0",
        },
    )
    open_fn = opener or urllib.request.urlopen
    with open_fn(request, timeout=timeout_seconds) as response:
        payload = json.loads(response.read().decode("utf-8"))
    data = payload.get("data") if isinstance(payload, dict) else []
    return list(data or [])


def _append_query_param(url, **params):
    parsed = urllib.parse.urlsplit(str(url or ""))
    query = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
    for key, value in params.items():
        if value not in (None, ""):
            query[key] = str(value)
    return urllib.parse.urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            urllib.parse.urlencode(query),
            parsed.fragment,
        )
    )


def _extract_json_rows(payload):
    if isinstance(payload, list):
        return list(payload)
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if isinstance(data, list):
        return list(data)
    if isinstance(data, dict):
        for key in ("list", "rows", "items", "records"):
            rows = data.get(key)
            if isinstance(rows, list):
                return list(rows)
    for key in ("list", "rows", "items", "records"):
        rows = payload.get(key)
        if isinstance(rows, list):
            return list(rows)
    return []


def _with_investor_qa_source(rows, source):
    normalized = []
    for row in rows or []:
        item = dict(row or {})
        code = str(item.get("code") or item.get("stock_code") or item.get("ts_code") or "").strip()
        if "." in code:
            item.setdefault("code", code.split(".", 1)[0])
        item.setdefault("source", source)
        normalized.append(item)
    return normalized


def _recent_trade_window(target_date, *, lookback_trade_days=1, fetch_trade_dates_fn=None):
    compact = _compact_date(target_date)
    if not compact:
        return "", ""
    window = max(int(lookback_trade_days or 1), 1)
    if window <= 1:
        return "", compact
    normalized = normalize_kline_date_str(target_date)
    try:
        target_dt = datetime.datetime.strptime(normalized, "%Y-%m-%d").date()
        calendar_start = (target_dt - datetime.timedelta(days=window - 1)).strftime("%Y-%m-%d")
        start_scan = (target_dt - datetime.timedelta(days=max(window * 3, 21))).strftime("%Y-%m-%d")
    except Exception:
        calendar_start = normalized
        start_scan = normalized
    fetcher = fetch_trade_dates_fn or fetch_tushare_open_trade_dates
    try:
        trade_dates = fetcher(start_scan, normalized) if callable(fetcher) else []
    except Exception:
        trade_dates = []
    normalized_dates = [
        normalize_kline_date_str(date)
        for date in (trade_dates or [])
        if normalize_kline_date_str(date)
    ]
    normalized_dates = sorted(set(normalized_dates))
    selected = [date for date in normalized_dates if calendar_start <= date <= normalized]
    if not selected:
        selected = [calendar_start, normalized]
    return selected[0].replace("-", ""), compact


def _fetch_tushare_investor_qa_rows(
    trade_date=None,
    *,
    pro=None,
    ts_module=None,
    lookback_trade_days=1,
    fetch_trade_dates_fn=None,
):
    compact = _compact_date(trade_date)
    if not compact:
        return []
    start_compact, end_compact = _recent_trade_window(
        trade_date,
        lookback_trade_days=lookback_trade_days,
        fetch_trade_dates_fn=fetch_trade_dates_fn,
    )
    pro = pro or create_tushare_pro_api(ts_module=ts_module)
    rows = []
    for endpoint in ("irm_qa_sh", "irm_qa_sz"):
        try:
            fetcher = getattr(pro, endpoint)
            kwargs = {"start_date": start_compact, "end_date": end_compact} if start_compact else {"trade_date": compact}
            rows.extend(_with_investor_qa_source(_frame_to_records(fetcher(**kwargs)), f"tushare.{endpoint}"))
        except Exception:
            continue
    return rows


def fetch_investor_qa_rows(
    trade_date=None,
    *,
    endpoint_url=None,
    timeout_seconds=8,
    opener=None,
    pro=None,
    ts_module=None,
    use_tushare=True,
    lookback_trade_days=1,
    fetch_trade_dates_fn=None,
):
    if use_tushare:
        tushare_rows = _fetch_tushare_investor_qa_rows(
            trade_date,
            pro=pro,
            ts_module=ts_module,
            lookback_trade_days=lookback_trade_days,
            fetch_trade_dates_fn=fetch_trade_dates_fn,
        )
        if tushare_rows:
            return tushare_rows

    _load_local_env_file()
    if endpoint_url is None:
        url = str(os.environ.get(INVESTOR_QA_ENDPOINT_ENV, "")).strip()
    else:
        url = str(endpoint_url or "").strip()
    if not url:
        return []
    normalized_date = normalize_kline_date_str(trade_date)
    start_compact, end_compact = _recent_trade_window(
        trade_date,
        lookback_trade_days=lookback_trade_days,
        fetch_trade_dates_fn=fetch_trade_dates_fn,
    )
    query_params = {"trade_date": normalized_date}
    if start_compact:
        query_params.update({"start_date": f"{start_compact[:4]}-{start_compact[4:6]}-{start_compact[6:8]}", "end_date": f"{end_compact[:4]}-{end_compact[4:6]}-{end_compact[6:8]}"})
    request = urllib.request.Request(
        _append_query_param(url, **query_params),
        headers={
            "Accept": "application/json, text/plain, */*",
            "User-Agent": "Mozilla/5.0",
        },
    )
    open_fn = opener or urllib.request.urlopen
    with open_fn(request, timeout=timeout_seconds) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return _extract_json_rows(payload)


def fetch_tushare_ths_hot(trade_date=None, *, market="热股", pro=None, ts_module=None):
    compact = _compact_date(trade_date)
    pro = pro or create_tushare_pro_api(ts_module=ts_module)
    fields = (
        "trade_date,data_type,ts_code,ts_name,rank,pct_change,current_price,"
        "concept,rank_reason,hot,rank_time"
    )
    kwargs = {"market": market, "is_new": "Y", "fields": fields}
    if compact:
        kwargs["trade_date"] = compact
    return _frame_to_records(pro.ths_hot(**kwargs))


def fetch_tushare_limit_rows(trade_date, *, pro=None, ts_module=None):
    compact = _compact_date(trade_date)
    if not compact:
        return []
    pro = pro or create_tushare_pro_api(ts_module=ts_module)
    fields = (
        "trade_date,ts_code,name,price,pct_chg,open_num,lu_desc,limit_type,tag,status,"
        "first_lu_time,last_lu_time,first_ld_time,last_ld_time,limit_order,limit_amount,"
        "turnover_rate,turnover,market_type"
    )
    rows = []
    for limit_type in ("涨停池", "跌停池"):
        frame = pro.limit_list_ths(trade_date=compact, limit_type=limit_type, fields=fields)
        for row in _frame_to_records(frame):
            item = dict(row or {})
            item.setdefault("limit_type", limit_type)
            rows.append(item)
    return rows


def fetch_tushare_ths_daily(trade_date, *, pro=None, ts_module=None):
    compact = _compact_date(trade_date)
    if not compact:
        return []
    pro = pro or create_tushare_pro_api(ts_module=ts_module)
    fields = "ts_code,trade_date,close,open,high,low,pre_close,avg_price,change,pct_change,vol,turnover_rate"
    return _frame_to_records(pro.ths_daily(trade_date=compact, fields=fields))


def fetch_tushare_ths_index_map(*, pro=None, ts_module=None):
    pro = pro or create_tushare_pro_api(ts_module=ts_module)
    frame = pro.ths_index(type="I")
    mapping = {}
    for row in _frame_to_records(frame):
        ts_code = str((row or {}).get("ts_code") or "").strip().upper()
        if ts_code:
            mapping[ts_code] = dict(row or {})
    return mapping


def fetch_tushare_ths_member(ts_code, *, pro=None, ts_module=None):
    ts_code = str(ts_code or "").strip().upper()
    if not ts_code:
        return []
    pro = pro or create_tushare_pro_api(ts_module=ts_module)
    return _frame_to_records(pro.ths_member(ts_code=ts_code))


def fetch_tushare_sector_flow(trade_date, *, pro=None, ts_module=None):
    compact = _compact_date(trade_date)
    if not compact:
        return []
    pro = pro or create_tushare_pro_api(ts_module=ts_module)
    fields = (
        "trade_date,ts_code,industry,lead_stock,close,pct_change,company_num,"
        "pct_change_stock,close_price,net_buy_amount,net_sell_amount,net_amount"
    )
    return _frame_to_records(pro.moneyflow_ind_ths(trade_date=compact, fields=fields))


def fetch_tushare_top_list(trade_date, *, pro=None, ts_module=None):
    compact = _compact_date(trade_date)
    if not compact:
        return []
    pro = pro or create_tushare_pro_api(ts_module=ts_module)
    fields = (
        "trade_date,ts_code,name,close,pct_change,turnover_rate,amount,"
        "l_sell,l_buy,l_amount,net_amount,net_rate,amount_rate,float_values,reason"
    )
    return _frame_to_records(pro.top_list(trade_date=compact, fields=fields))


def fetch_tushare_top_inst(trade_date, *, pro=None, ts_module=None):
    compact = _compact_date(trade_date)
    if not compact:
        return []
    pro = pro or create_tushare_pro_api(ts_module=ts_module)
    fields = "trade_date,ts_code,exalter,side,buy,buy_rate,sell,sell_rate,net_buy,reason"
    return _frame_to_records(pro.top_inst(trade_date=compact, fields=fields))


def fetch_tushare_st_rows(trade_date, *, pro=None, ts_module=None):
    compact = _compact_date(trade_date)
    if not compact:
        return []
    pro = pro or create_tushare_pro_api(ts_module=ts_module)
    fields = "ts_code,name,pub_date,imp_date,st_reason,st_explain"
    return _frame_to_records(pro.st(fields=fields))


def fetch_tushare_stock_st_rows(trade_date, *, pro=None, ts_module=None):
    compact = _compact_date(trade_date)
    if not compact:
        return []
    pro = pro or create_tushare_pro_api(ts_module=ts_module)
    fields = "ts_code,name,trade_date"
    return _frame_to_records(pro.stock_st(trade_date=compact, fields=fields))


def fetch_tushare_holdertrade_rows(trade_date, *, pro=None, ts_module=None):
    compact = _compact_date(trade_date)
    if not compact:
        return []
    pro = pro or create_tushare_pro_api(ts_module=ts_module)
    fields = "ts_code,ann_date,holder_name,holder_type,in_de,change_vol,change_ratio,after_share,after_ratio,avg_price,total_share,begin_date,close_date"
    return _frame_to_records(pro.stk_holdertrade(ann_date=compact, fields=fields))


def fetch_tushare_announcement_rows(trade_date, *, pro=None, ts_module=None):
    compact = _compact_date(trade_date)
    if not compact:
        return []
    pro = pro or create_tushare_pro_api(ts_module=ts_module)
    fields = "ts_code,ann_date,title,url"
    return _frame_to_records(pro.anns_d(ann_date=compact, fields=fields))


def fetch_tushare_shock_rows(trade_date, *, pro=None, ts_module=None):
    compact = _compact_date(trade_date)
    if not compact:
        return []
    pro = pro or create_tushare_pro_api(ts_module=ts_module)
    fields = "ts_code,trade_date,type,reason"
    return _frame_to_records(pro.stk_shock(trade_date=compact, fields=fields))


def fetch_tushare_new_share(start_date, end_date, *, pro=None, ts_module=None):
    start = _compact_date(start_date)
    end = _compact_date(end_date)
    if not start or not end:
        return []
    pro = pro or create_tushare_pro_api(ts_module=ts_module)
    fields = "ts_code,sub_code,name,ipo_date,issue_date,amount,market_amount,price,pe,limit_amount,funds,ballot"
    return _frame_to_records(pro.new_share(start_date=start, end_date=end, fields=fields))


def fetch_tushare_open_trade_dates(start_date, end_date, *, exchange="SSE", pro=None, ts_module=None):
    start = _compact_date(start_date)
    end = _compact_date(end_date)
    if not start or not end:
        return []
    pro = pro or create_tushare_pro_api(ts_module=ts_module)
    rows = _frame_to_records(pro.trade_cal(exchange=exchange, start_date=start, end_date=end, is_open="1"))
    dates = []
    for row in rows:
        cal_date = _compact_date((row or {}).get("cal_date"))
        if cal_date:
            dates.append(f"{cal_date[:4]}-{cal_date[4:6]}-{cal_date[6:8]}")
    return sorted(set(dates))
