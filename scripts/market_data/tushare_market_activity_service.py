from __future__ import annotations

from market_data.kline_dates import normalize_kline_date_str
from market_data.tushare_client import create_tushare_pro_api

__all__ = [
    "fetch_tushare_limit_rows",
    "fetch_tushare_new_share",
    "fetch_tushare_open_trade_dates",
    "fetch_tushare_sector_flow",
    "fetch_tushare_ths_daily",
    "fetch_tushare_ths_hot",
    "fetch_tushare_ths_index_map",
    "fetch_tushare_top_list",
]


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
