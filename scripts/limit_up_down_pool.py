from __future__ import annotations

import math
import time
from datetime import datetime

import akshare as ak
import pandas as pd

from legacy_runtime_shim import export_or_default
from market_data.kline_dates import normalize_kline_date_str
from market_data.tushare_client import create_tushare_pro_api
from market_data.tushare_turnover_service import (
    fetch_stock_basic_map,
    fetch_stock_daily_turnover_records,
)

get_limit_up_pool = export_or_default("limit_up_down_pool", "get_limit_up_pool", lambda *args, **kwargs: ([], set()))
mark_limit_status = export_or_default("limit_up_down_pool", "mark_limit_status", lambda *args, **kwargs: {})

_LIMIT_DOWN_COLUMNS = (
    "序号",
    "代码",
    "名称",
    "涨跌幅",
    "最新价",
    "成交额",
    "所属行业",
    "data_source",
    "trade_date",
    "source_date",
)

_LIMIT_LIST_D_FIELDS = (
    "trade_date,ts_code,industry,name,close,pct_chg,amount,"
    "limit_amount,float_mv,total_mv,turnover_ratio,fd_amount,"
    "first_time,last_time,open_times,up_stat,limit_times,limit"
)


def _price_cents(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number <= 0:
        return None
    return round(number * 100)


def _is_missing_or_zero_limit(value):
    """Accept only the documented missing/zero first-day down-limit values."""
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return math.isnan(number) or number == 0.0


def _empty_limit_down_frame(*, source_confirmed, provider, source_date="", source_error=""):
    frame = pd.DataFrame(columns=_LIMIT_DOWN_COLUMNS)
    frame.attrs.update(
        {
            "source_confirmed": bool(source_confirmed),
            "provider": str(provider or ""),
            "source_date": normalize_kline_date_str(source_date),
            "source_error": str(source_error or ""),
        }
    )
    return frame


def _is_confirmed_no_price_limit(limit_row, daily_row, basic):
    name = str((basic or {}).get("name") or daily_row.get("name") or "").strip()
    up_limit = _price_cents((limit_row or {}).get("up_limit"))
    return (
        name.startswith(("N", "C"))
        # Tushare uses these two exact first-day no-price-limit sentinels
        # depending on the listing market.
        and up_limit in {10_000_000, 9_999_999}
        and _is_missing_or_zero_limit((limit_row or {}).get("down_limit"))
    )


def _fetch_target_date_suspended_codes(pro, source_date):
    """Return listed codes explicitly marked suspended on the target date."""
    fetcher = getattr(pro, "suspend_d", None)
    if not callable(fetcher):
        return set()
    compact = str(source_date or "").replace("-", "")
    frame = None
    for attempt in range(3):
        try:
            frame = fetcher(
                start_date=compact,
                end_date=compact,
                fields="ts_code,trade_date,suspend_type",
            )
        except Exception:
            frame = None
        rows = frame.to_dict("records") if hasattr(frame, "to_dict") else list(frame or [])
        if rows:
            break
        if attempt < 2:
            time.sleep(1)
    rows = frame.to_dict("records") if hasattr(frame, "to_dict") else list(frame or [])
    suspended = set()
    for row in rows:
        if normalize_kline_date_str(row.get("trade_date")) != source_date:
            continue
        ts_code = str(row.get("ts_code") or "").strip().upper()
        if ts_code and str(row.get("suspend_type") or "S").strip().upper() in {"S", "1", "TRUE"}:
            suspended.add(ts_code)
    return suspended


def _get_limit_down_pool_from_tushare_prices(
    date,
    *,
    pro=None,
    daily_fetcher=fetch_stock_daily_turnover_records,
    basic_fetcher=fetch_stock_basic_map,
):
    source_date = normalize_kline_date_str(date)
    compact = source_date.replace("-", "") if source_date else ""
    if not compact:
        raise ValueError("跌停池目标日期缺失")

    pro = pro or create_tushare_pro_api()
    limit_frame = pro.stk_limit(
        trade_date=compact,
        fields="trade_date,ts_code,pre_close,up_limit,down_limit",
    )
    limit_rows = limit_frame.to_dict("records") if hasattr(limit_frame, "to_dict") else list(limit_frame or [])
    daily_rows = []
    for attempt in range(3):
        try:
            daily_rows = list(daily_fetcher(source_date, pro=pro) or [])
        except Exception:
            daily_rows = []
        if daily_rows:
            break
        if attempt < 2:
            time.sleep(1)
    if not limit_rows or not daily_rows:
        raise RuntimeError("Tushare目标日涨跌停价或日行情为空")

    target_limit_rows = [
        row
        for row in limit_rows
        if str(row.get("ts_code") or "").strip()
        and normalize_kline_date_str(row.get("trade_date")) == source_date
    ]
    if not target_limit_rows:
        raise RuntimeError("Tushare目标日涨跌停价为空")
    basic_map = {}
    for attempt in range(4):
        try:
            basic_map = basic_fetcher(pro=pro) or {}
        except Exception:
            basic_map = {}
        if basic_map:
            break
        if attempt < 3:
            time.sleep(1)
    # stk_limit also contains ETF/fund and other non-stock instruments. When
    # stock_basic is available, restrict the comparison to listed A-share stocks;
    # an empty injected map remains supported for the small unit-test fixtures.
    listed_ts_codes = {
        str(key).strip().upper()
        for key in basic_map
        if "." in str(key) and str(key).strip().upper().endswith((".SH", ".SZ", ".BJ"))
    }
    if listed_ts_codes:
        target_limit_rows = [
            row
            for row in target_limit_rows
            if str(row.get("ts_code") or "").strip().upper() in listed_ts_codes
        ]
    suspended_codes = _fetch_target_date_suspended_codes(pro, source_date)
    limit_by_code = {}
    for row in target_limit_rows:
        ts_code = str(row.get("ts_code") or "").strip().upper()
        if ts_code in limit_by_code:
            raise RuntimeError(f"Tushare目标日涨跌停价代码重复：{ts_code}")
        limit_by_code[ts_code] = row
    daily_by_code = {}
    for row in daily_rows:
        ts_code = str(row.get("ts_code") or "").strip().upper()
        if not ts_code or normalize_kline_date_str(row.get("trade_date")) != source_date:
            continue
        if ts_code in daily_by_code:
            raise RuntimeError(f"Tushare目标日日行情代码重复：{ts_code}")
        daily_by_code[ts_code] = row
    daily_codes = set(daily_by_code)
    limit_codes = set(limit_by_code)
    expected_daily_codes = limit_codes - suspended_codes
    if not daily_codes or daily_codes != expected_daily_codes:
        raise RuntimeError(
            "Tushare目标日日行情覆盖不足："
            f"{len(daily_codes & expected_daily_codes)}/{len(expected_daily_codes)}，"
            f"日行情额外{len(daily_codes - limit_codes)}"
        )
    no_price_limit_codes = set()
    invalid_price_codes = []
    for ts_code, daily_row in daily_by_code.items():
        stock_code = str(daily_row.get("stock_code") or ts_code.split(".", 1)[0]).strip()
        basic = basic_map.get(stock_code) or basic_map.get(ts_code) or {}
        limit_row = limit_by_code.get(ts_code) or {}
        if _price_cents(daily_row.get("close")) is None:
            invalid_price_codes.append(ts_code)
        elif _is_confirmed_no_price_limit(limit_row, daily_row, basic):
            no_price_limit_codes.add(ts_code)
        elif _price_cents(limit_row.get("down_limit")) is None:
            invalid_price_codes.append(ts_code)
    if invalid_price_codes:
        raise RuntimeError(
            f"Tushare目标日涨跌停价格无效：{len(invalid_price_codes)}/{len(daily_codes)}"
        )

    rows = []
    for ts_code, daily_row in daily_by_code.items():
        if ts_code in no_price_limit_codes:
            continue
        down_limit_cents = _price_cents((limit_by_code.get(ts_code) or {}).get("down_limit"))
        close_cents = _price_cents(daily_row.get("close"))
        if close_cents != down_limit_cents:
            continue
        stock_code = str(daily_row.get("stock_code") or ts_code.split(".", 1)[0]).strip()
        basic = basic_map.get(stock_code) or basic_map.get(ts_code) or {}
        rows.append(
            {
                "序号": len(rows) + 1,
                "代码": stock_code,
                "名称": str(basic.get("name") or daily_row.get("name") or stock_code).strip(),
                "涨跌幅": float(daily_row.get("pct_chg") or 0.0),
                "最新价": float(daily_row.get("close") or 0.0),
                "成交额": round(float(daily_row.get("amount_raw_qianyuan") or 0.0) * 1000, 2),
                "所属行业": str(basic.get("industry") or "未知").strip() or "未知",
                "data_source": "tushare.stk_limit+tushare.daily",
                "trade_date": source_date,
                "source_date": source_date,
            }
        )

    frame = pd.DataFrame(rows, columns=_LIMIT_DOWN_COLUMNS)
    frame.attrs.update(
        {
            "source_confirmed": True,
            "provider": "tushare.stk_limit+tushare.daily",
            "source_date": source_date,
            "source_row_count": len(daily_codes),
            "price_limited_row_count": len(daily_codes) - len(no_price_limit_codes),
            "no_price_limit_row_count": len(no_price_limit_codes),
        }
    )
    return frame, {row["代码"] for row in rows}


def _get_limit_down_pool_from_tushare_limit_list_d(
    date,
    *,
    pro=None,
):
    """Use the dated Tushare limit-list direction field as a narrow fallback."""
    source_date = normalize_kline_date_str(date)
    compact = source_date.replace("-", "") if source_date else ""
    if not compact:
        raise ValueError("跌停池目标日期缺失")
    pro = pro or create_tushare_pro_api()
    fetcher = getattr(pro, "limit_list_d", None)
    if not callable(fetcher):
        raise RuntimeError("Tushare limit_list_d 不可用")

    rows = []
    last_error = ""
    for attempt in range(4):
        try:
            frame = fetcher(trade_date=compact, fields=_LIMIT_LIST_D_FIELDS)
            rows = frame.to_dict("records") if hasattr(frame, "to_dict") else list(frame or [])
            if rows:
                break
        except Exception as error:
            last_error = str(error)
        if attempt < 3:
            time.sleep(1)
    if not rows:
        raise RuntimeError(last_error or "Tushare目标日涨跌停列表为空")

    target_rows = [
        row
        for row in rows
        if normalize_kline_date_str(row.get("trade_date")) == source_date
    ]
    if not target_rows:
        raise RuntimeError("Tushare涨跌停列表缺少目标日期")
    if any("limit" not in row for row in target_rows):
        raise RuntimeError("Tushare涨跌停列表缺少方向字段")

    known_directions = {"U", "D", "Z", "UP", "DOWN", "炸板", "涨停", "跌停", "涨停池", "跌停池"}
    for row in target_rows:
        direction = str(row.get("limit") or "").strip().upper()
        if direction not in known_directions:
            raise RuntimeError("Tushare涨跌停列表方向字段无效")

    basic_map = {}
    try:
        basic_map = fetch_stock_basic_map(pro=pro) or {}
    except Exception:
        basic_map = {}
    down_rows = []
    for row in target_rows:
        direction = str(row.get("limit") or "").strip().upper()
        if direction not in {"D", "DOWN", "跌停", "跌停池"}:
            continue
        ts_code = str(row.get("ts_code") or "").strip().upper()
        if not ts_code:
            raise RuntimeError("Tushare跌停列表缺少股票代码")
        stock_code = ts_code.split(".", 1)[0]
        basic = basic_map.get(stock_code) or basic_map.get(ts_code) or {}
        down_rows.append(
            {
                "序号": len(down_rows) + 1,
                "代码": stock_code,
                "名称": str(row.get("name") or basic.get("name") or stock_code).strip(),
                "涨跌幅": float(row.get("pct_chg") or 0.0),
                "最新价": float(row.get("close") or 0.0),
                "成交额": float(row.get("amount") or 0.0),
                "所属行业": str(row.get("industry") or basic.get("industry") or "未知").strip() or "未知",
                "data_source": "tushare.limit_list_d",
                "trade_date": source_date,
                "source_date": source_date,
            }
        )

    frame = pd.DataFrame(down_rows, columns=_LIMIT_DOWN_COLUMNS)
    frame.attrs.update(
        {
            "source_confirmed": True,
            "provider": "tushare.limit_list_d",
            "source_date": source_date,
            "source_row_count": len(target_rows),
            "direction_field": "limit",
            "direction_value": "D",
        }
    )
    return frame, {row["代码"] for row in down_rows}


def get_limit_down_pool(
    date=None,
    use_backup=False,
    *,
    ak_module=None,
    pro=None,
    daily_fetcher=fetch_stock_daily_turnover_records,
    basic_fetcher=fetch_stock_basic_map,
):
    date = date or datetime.now().strftime("%Y%m%d")
    source_date = normalize_kline_date_str(date)
    primary_error = ""
    if not use_backup:
        try:
            frame = (ak_module or ak).stock_zt_pool_dtgc_em(date=str(date).replace("-", ""))
            print(f"📉 跌停股票数(东方财富): {len(frame)}")
            if not frame.empty:
                if "代码" not in frame.columns:
                    raise RuntimeError("东方财富跌停池缺少代码列")
                frame.attrs.update(
                    {
                        "source_confirmed": True,
                        "provider": "akshare.stock_zt_pool_dtgc_em",
                        "source_date": source_date,
                    }
                )
                return frame, set(frame["代码"].astype(str).tolist())
        except Exception as error:
            primary_error = str(error)
            print(f"⚠️ 东方财富跌停数据获取失败: {error}")

    try:
        frame, codes = _get_limit_down_pool_from_tushare_prices(
            source_date,
            pro=pro,
            daily_fetcher=daily_fetcher,
            basic_fetcher=basic_fetcher,
        )
        print(f"📉 跌停股票数(Tushare目标日价格核对): {len(frame)}")
        return frame, codes
    except Exception as error:
        price_error = str(error)
        # A transient empty page can occur on the proxy. In that narrow case,
        # use the dated direction endpoint; coverage/price failures remain
        # unconfirmed and must not be bypassed by a generic success response.
        if "为空" in price_error or "empty" in price_error.lower():
            try:
                frame, codes = _get_limit_down_pool_from_tushare_limit_list_d(
                    source_date,
                    pro=pro,
                )
                print(f"📉 跌停股票数(Tushare limit_list_d): {len(frame)}")
                return frame, codes
            except Exception as fallback_error:
                price_error = "; ".join(item for item in (price_error, str(fallback_error)) if item)
        source_error = "; ".join(item for item in (primary_error, price_error) if item)
        print(f"❌ 跌停池目标日交叉核对失败: {source_error}")
        return (
            _empty_limit_down_frame(
                source_confirmed=False,
                provider="akshare.stock_zt_pool_dtgc_em+tushare.stk_limit+tushare.daily",
                source_date=source_date,
                source_error=source_error,
            ),
            set(),
        )

__all__ = ["get_limit_up_pool", "get_limit_down_pool", "mark_limit_status"]
