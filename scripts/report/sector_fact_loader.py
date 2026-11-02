"""Small, dated fact loader for the current market-reading page.

This module deliberately does not import the report runtime, account context,
candidate selection, or any execution renderer.  It collects only the facts
that ``sector_daily_report`` can display and leaves unavailable facts empty.
"""
from __future__ import annotations

import datetime as _dt
import math
import os
from numbers import Real
from collections import defaultdict
from urllib.parse import urlsplit

from market_data.kline_dates import normalize_kline_date_str
from market_data.tushare_client import create_tushare_pro_api
from market_data.tushare_market_activity_service import (
    fetch_tushare_ths_daily,
    fetch_tushare_ths_index_map,
)
from market_data.tushare_service import fetch_daily_price_bars
from market_data.tushare_turnover_service import (
    fetch_stock_basic_map,
    fetch_stock_daily_turnover_records,
)


def _number(value):
    if isinstance(value, bool):
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _normalize_nonfinite(value):
    """Keep valid source values and turn NaN/Infinity into honest gaps."""
    if isinstance(value, dict):
        return {key: _normalize_nonfinite(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_nonfinite(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_normalize_nonfinite(item) for item in value)
    if isinstance(value, Real) and not isinstance(value, bool):
        return value if math.isfinite(value) else None
    return value


def _date(value):
    return normalize_kline_date_str(value) or ""


def _target_date(value):
    normalized = _date(value)
    if not normalized:
        raise ValueError("目标日期格式不符")
    parsed = _dt.date.fromisoformat(normalized)
    shanghai_today = _dt.datetime.now(
        _dt.timezone(_dt.timedelta(hours=8))
    ).date()
    if parsed > shanghai_today:
        raise ValueError("目标日期不能晚于当前上海日期")
    return normalized


def _code(value):
    text = str(value or "").strip().upper()
    if "." in text:
        text = text.split(".", 1)[0]
    digits = "".join(char for char in text if char.isdigit())
    return digits.zfill(6) if digits else ""


def _row_date(row):
    row = row if isinstance(row, dict) else {}
    if not row.get('trade_date') and not row.get('date'):
        return ""
    dates = {_date(row.get(key)) for key in ("trade_date", "date", "source_date") if row.get(key)}
    if len(dates) > 1:
        return ""
    return next(iter(dates), "")


def _exact_daily_rows(rows, target_date):
    exact = []
    invalid = 0
    seen = {}
    for row in rows or []:
        if not isinstance(row, dict):
            invalid += 1
            continue
        row_date = _row_date(row)
        if row_date == target_date:
            code = str(row.get("ts_code") or row.get("stock_code") or "").strip().upper()
            if not code:
                invalid += 1
            elif code not in seen:
                seen[code] = row
                exact.append(dict(row))
            elif seen[code] != row:
                invalid += 1
        else:
            invalid += 1
    # A partial/mixed-date response cannot be advertised as complete breadth.
    return ([] if invalid else exact), invalid


def _daily_amount(row):
    amount = _number(row.get("amount_yi"))
    if amount is not None:
        return amount if amount > 0 else None
    raw = _number(row.get("amount_raw_qianyuan"))
    if raw is not None:
        return raw / 100000.0 if raw > 0 else None
    raw = _number(row.get("amount"))
    return raw / 100000.0 if raw is not None and raw > 0 else None


def _daily_change(row):
    # The shared daily adapter defaults missing pct_chg to zero. Recompute from
    # its raw close/pre_close pair rather than counting unknown as unchanged.
    close, previous = _number(row.get("close")), _number(row.get("pre_close"))
    if close is None or previous is None or close <= 0 or previous <= 0:
        return None
    return (close - previous) / previous * 100.0


def _industry(row, basic_map):
    for key in ("industry", "所属行业", "sector"):
        value = str(row.get(key) or "").strip()
        if value:
            return value
    candidates = [_code(row.get("stock_code")), _code(row.get("ts_code")), str(row.get("ts_code") or "").strip().upper()]
    for key in candidates:
        item = (basic_map or {}).get(key)
        if isinstance(item, dict) and str(item.get("industry") or "").strip():
            return str(item["industry"]).strip()
        if isinstance(item, str) and item.strip():
            return item.strip()
    return ""


def _aggregate_by_industry(rows, target_date, basic_map, query_date):
    buckets = defaultdict(lambda: {"weighted": 0.0, "weight": 0.0, "turnover": 0.0, "count": 0, "up": 0, "down": 0})
    for row in rows:
        name = _industry(row, basic_map)
        if not name:
            continue
        change = _daily_change(row)
        amount = _daily_amount(row)
        if change is None or amount is None:
            continue
        weight = amount
        bucket = buckets[name]
        bucket["weighted"] += change * weight
        bucket["weight"] += weight
        bucket["turnover"] += amount
        bucket["count"] += 1
        if change > 0:
            bucket["up"] += 1
        elif change < 0:
            bucket["down"] += 1
    result = []
    for name, bucket in buckets.items():
        change = bucket["weighted"] / (bucket["weight"] or 1.0)
        result.append({
            "name": name,
            "code": "",
            "change_pct": round(change, 6),
            "zdf": round(change, 6),
            "turnover_yi": round(bucket["turnover"], 6),
            "stock_count": bucket["count"],
            "up_count": bucket["up"],
            "down_count": bucket["down"],
            "data_source": "tushare.daily.industry_aggregate",
            "trade_date": target_date,
            "source_date": target_date,
            "query_date": query_date,
        })
    return result


def is_reading_concept(meta):
    # The provider also labels benchmark constituent baskets as N. Their
    # explicit directory names identify them; code prefixes do not.
    return (meta.get('exchange') == 'A' and meta.get('type') == 'N'
            and not str(meta.get('name') or '').endswith(('样本股', '成份股')))


def _ths_index_rows(rows, index_map, target_date, *, index_type):
    result = []
    exact, invalid = _exact_daily_rows(rows, target_date)
    if invalid:
        raise ValueError("板块指数日期不符或记录冲突")
    for row in exact:
        code = str(row.get("ts_code") or "").strip().upper()
        meta = (index_map or {}).get(code) or {}
        if str(meta.get("exchange") or "").strip().upper() != "A":
            continue
        if str(meta.get("type") or "").strip().upper() != index_type:
            continue
        if index_type == 'N' and not is_reading_concept(meta):
            continue
        name = str(meta.get("name") or "").strip()
        change = _number(row.get("pct_change", row.get("pct_chg")))
        if not name or change is None:
            continue
        item = {
            "code": code,
            "name": name,
            "change_pct": round(change, 6),
            "data_source": row.get('data_source', 'tushare.ths_daily'),
            "trade_date": target_date,
            "source_date": target_date,
            "index_type": index_type,
            "identity": f"tushare.ths_index:{index_type}:{code}",
        }
        for key in ("close", "turnover_rate"):
            value = _number(row.get(key))
            if value is not None:
                item[key] = value
        for key in ('query_date', 'retrieved_at'):
            if row.get(key):
                item[key] = row[key]
        result.append(item)
    return result


def _ths_industry_rows(rows, index_map, target_date):
    return _ths_index_rows(rows, index_map, target_date, index_type="I")


def _rank(rows, *, descending):
    return [
        {**row, "rank": rank}
        for rank, row in enumerate(
            sorted(rows, key=lambda item: (item.get("change_pct", 0.0), item.get("name", "")), reverse=descending)[:10],
            start=1,
        )
    ]


def _index_fact(target_date, *, pro, ts_module):
    start = (_dt.date.fromisoformat(target_date) - _dt.timedelta(days=15)).isoformat()
    bars = fetch_daily_price_bars(
        "000985", start, target_date, is_index=True, pro=pro, ts_module=ts_module,
    )
    by_date = {}
    for bar in bars:
        if not isinstance(bar, dict):
            continue
        day = _date(bar.get("date") or bar.get("trade_date"))
        if not day or day > target_date:
            continue
        declared = {_date(bar.get(key)) for key in ("date", "trade_date") if bar.get(key)}
        if len(declared) > 1:
            return {}
        signature = tuple(_number(bar.get(key)) for key in ("close", "pre_close", "open", "high", "low"))
        previous = by_date.get(day)
        if previous is not None:
            previous_signature = tuple(_number(previous.get(key)) for key in ("close", "pre_close", "open", "high", "low"))
            if signature != previous_signature:
                return {}
            continue
        by_date[day] = dict(bar, date=day)
    bars = sorted(by_date.values(), key=lambda item: _date(item.get("date") or item.get("trade_date")))
    if not bars or _date(bars[-1].get("date")) != target_date:
        return {}
    latest = bars[-1]
    previous = bars[-2] if len(bars) > 1 else {}
    close = _number(latest.get("close"))
    previous_close = _number(latest.get("pre_close")) or _number(previous.get("close"))
    if close is None or close <= 0:
        return {}
    change = (close - previous_close) / previous_close * 100.0 if previous_close and previous_close > 0 else None
    return {
        "name": "中证全指",
        "code": "000985",
        "price": close,
        "close": close,
        "pre_close": previous_close,
        "open": _number(latest.get("open")),
        "high": _number(latest.get("high")),
        "low": _number(latest.get("low")),
        "change_pct": change,
        "涨跌幅": change,
        "data_source": "tushare.index_daily",
        "trade_date": target_date,
        "source_date": target_date,
    }


def collect_market_reading_data(
    target_date,
    *,
    pro=None,
    ts_module=None,
    daily_fetcher=None,
    basic_map_fetcher=None,
    ths_daily_fetcher=None,
    ths_index_map_fetcher=None,
    index_fact_fetcher=None,
    supplemental_collector=None,
    concept_price_fetcher=None,
):
    """Collect only dated facts needed by the current sector reading page."""
    target_date = _target_date(target_date)
    daily_fetcher = daily_fetcher or fetch_stock_daily_turnover_records
    basic_map_fetcher = basic_map_fetcher or fetch_stock_basic_map
    ths_daily_fetcher = ths_daily_fetcher or fetch_tushare_ths_daily
    ths_index_map_fetcher = ths_index_map_fetcher or fetch_tushare_ths_index_map
    errors = []
    collected_at = _dt.datetime.now(_dt.timezone(_dt.timedelta(hours=8))).isoformat()
    data = {
        "target_date": target_date,
        "source_date": target_date,
        "query_date": collected_at[:10],
        "collection_mode": "market_reading_facts",
        "reading_collected_at": collected_at,
        "reading_source_notes": [],
        "reading_collection": {"target_date": target_date, "providers": [], "errors": errors},
    }
    managed_client = pro is None
    try:
        pro = pro or create_tushare_pro_api(ts_module=ts_module, timeout_seconds=30)
    except Exception as exc:
        errors.append(f"Tushare: {exc.__class__.__name__}")
        data["reading_source_notes"].append("未能连接事实来源；市场与板块事实待确认。")
        return data
    if managed_client:
        from market_data.tushare_client import resolve_tushare_runtime_config
        configured = resolve_tushare_runtime_config().get('http_url') or 'https://api.tushare.pro'
        data['reading_collection']['configured_provider_hosts'] = [
            urlsplit(url.strip()).hostname for url in configured.split(',') if urlsplit(url.strip()).hostname]

    daily_rows = []
    basic_map = None

    def stock_basics():
        nonlocal basic_map
        if basic_map is None:
            try:
                basic_map = basic_map_fetcher(pro=pro, ts_module=ts_module)
            except Exception as exc:
                basic_map = {}
                errors.append(f"tushare.stock_basic: {exc.__class__.__name__}")
        return basic_map
    try:
        fetched = daily_fetcher(target_date, pro=pro, ts_module=ts_module)
        daily_rows, invalid = _exact_daily_rows(fetched, target_date)
        data["reading_collection"]["providers"].append({"name": "tushare.daily", "rows": len(daily_rows), "invalid_rows": invalid})
        if not daily_rows:
            errors.append("tushare.daily 未返回目标日有效记录")
            data["reading_source_notes"].append("个股日线缺失、日期不符或记录冲突；不据此计算涨跌家数与成交额。")
    except Exception as exc:
        errors.append(f"tushare.daily: {exc.__class__.__name__}")
        data["reading_source_notes"].append("目标日个股日线未能取得；涨跌家数与成交额待确认。")

    if daily_rows:
        ranked = sorted((row for row in daily_rows if _daily_amount(row) is not None),
                        key=lambda row: _daily_amount(row), reverse=True)
        rank_basics = stock_basics() if any(not row.get('name') or row.get('name') == _code(row.get('ts_code'))
                                           for row in ranked[:50]) else {}
        data['turnover_rank'] = [{
            'rank': i, 'code': _code(row.get('ts_code')),
            'name': (row.get('name') if row.get('name') and row.get('name') != _code(row.get('ts_code'))
                     else (rank_basics.get(_code(row.get('ts_code'))) or {}).get('name') or '名称待确认'),
            **({'name_source': 'tushare.stock_basic' if (rank_basics.get(_code(row.get('ts_code'))) or {}).get('name') else '未取得',
                'name_query_date': collected_at[:10],
                'name_retrieved_at': collected_at}
               if (not row.get('name') or row.get('name') == _code(row.get('ts_code'))) else {}),
            'turnover': _daily_amount(row), 'change_pct': _daily_change(row),
            'trade_date': target_date, 'source_date': target_date, 'query_date': collected_at[:10],
            'retrieved_at': collected_at, 'data_source': 'tushare.daily',
        } for i, row in enumerate(ranked[:50], 1)]
        if rank_basics and collected_at[:10] != target_date:
            data['reading_source_notes'].append('股票名称为本次查询的代码对应简称，仅用于榜单标签；不证明历史简称或行业归属未变。')
        if any(row['name'] == '名称待确认' for row in data['turnover_rank']):
            data['reading_source_notes'].append('部分股票简称未取得，左轴标名称待确认；股票代码仍保留在悬浮详情。')
        hs = [row for row in ranked if str(row.get('ts_code') or '').endswith(('.SH', '.SZ'))]
        if len(hs) >= 50:
            total, top = math.fsum(_daily_amount(row) for row in hs), math.fsum(_daily_amount(row) for row in hs[:50])
            data['top50_turnover_share_series'] = {'source': 'tushare.daily', 'query_date': collected_at[:10],
                'query_window': {'rank_scope': 'hs_a', 'end_date': target_date},
                'rows': [{'trade_date': target_date, 'source_date': target_date, 'query_date': collected_at[:10],
                          'market_amount_yi': total, 'top_amount_yi': top, 'share_pct': top / total * 100,
                          'sample_label': '沪深有成交股票；分子与分母同范围'}]}
        changes = [value for row in daily_rows if (value := _daily_change(row)) is not None]
        if changes:
            data["market_stats"] = {
                "up_count": sum(value > 0 for value in changes),
                "down_count": sum(value < 0 for value in changes),
                "flat_count": sum(value == 0 for value in changes),
                "stock_count": len(changes),
                "trade_date": target_date,
                "source_date": target_date,
                "query_date": collected_at[:10],
                "retrieved_at": collected_at,
                "data_source": "tushare.daily",
                "sample_label": "有有效成交日线及前收盘价的股票，不含停牌与零成交样本",
            }
        amounts = [_daily_amount(row) for row in daily_rows if str(row.get("ts_code") or "").endswith((".SH", ".SZ"))]
        if amounts and all(value is not None for value in amounts):
            data["turnover_data"] = {
                "total_turnover_yi": math.fsum(amounts),
                "date": target_date,
                "source_date": target_date,
                "query_date": collected_at[:10],
                "retrieved_at": collected_at,
                "data_source": "tushare.daily",
                "sample_label": "沪深有成交的股票日线金额合计，不含北交所、ETF与其他基金",
            }

    meta, ths, industry_rows = {}, [], []
    ths_at, directory_at = None, None
    data['sector_universe'] = 'concept'
    try:
        ths = ths_daily_fetcher(target_date, pro=pro, ts_module=ts_module)
        ths_at = _dt.datetime.now(_dt.timezone(_dt.timedelta(hours=8))).isoformat()
    except Exception as exc:
        errors.append(f"tushare.ths_daily: {exc.__class__.__name__}")
        data["reading_source_notes"].append("目标日概念指数原价格未能取得；继续核对概念目录与可用补查来源。")

    try:
        meta = _normalize_nonfinite(
            ths_index_map_fetcher(pro=pro, ts_module=ts_module, index_type='N')
        )
        directory_at = _dt.datetime.now(_dt.timezone(_dt.timedelta(hours=8))).isoformat()
    except Exception as exc:
        errors.append(f"tushare.ths_index.N: {exc.__class__.__name__}")
        data["reading_source_notes"].append("概念目录未能取得；不使用行业或当前热榜冒充概念。")

    try:
        ths_rows = _ths_index_rows(ths, meta, target_date, index_type='N')
    except Exception as exc:
        ths_rows = []
        errors.append(f"tushare.ths_daily: {exc.__class__.__name__}")
        data["reading_source_notes"].append("目标日概念指数未能取得；不使用行业或当前热榜冒充概念。")

    registered = {code for code, m in meta.items() if is_reading_concept(m)}
    if (registered - {r['code'] for r in ths_rows}
            and (concept_price_fetcher is not None or managed_client and os.environ.get('IWENCAI_API_KEY'))):
        from market_data.iwencai_concept_prices import fetch_concept_prices, merge_price_rows
        try:
            supplement = (concept_price_fetcher or fetch_concept_prices)(target_date)
            merged = merge_price_rows(ths, supplement, target_date)
            ths_rows = _ths_index_rows(merged, meta, target_date, index_type='N')
            data['reading_concept_prices'] = supplement
            data['reading_source_notes'].append('缺少的概念价格按同日同代码补查，数据来源于同花顺问财；未匹配的目录代码仍保留缺口。')
        except Exception as exc:
            errors.append(f'iwencai.concept_index: {exc.__class__.__name__}')
            data['reading_source_notes'].append('同花顺问财概念价格补查未通过核对，保留原来源与缺口。')

    try:
        industry_meta = _normalize_nonfinite(
            ths_index_map_fetcher(pro=pro, ts_module=ts_module, index_type='I')
        )
        industry_rows = _ths_industry_rows(ths, industry_meta, target_date)
    except Exception as exc:
        errors.append(f"tushare.ths_index.I: {exc.__class__.__name__}")

    if ths_rows:
        rows = ths_rows
        for row in rows:
            row.setdefault('query_date', (ths_at or collected_at)[:10])
            row.setdefault('retrieved_at', ths_at or collected_at)
        for source in sorted({r['data_source'] for r in rows}):
            data['reading_collection']['providers'].append({'name': source,
                'rows': sum(r['data_source'] == source for r in rows)})
    else:
        rows = []
        data["reading_source_notes"].append("没有可用概念样本；行业背景不替代概念，历史日期不借用当前上市行业映射重建归属。")
    if not industry_rows and daily_rows and collected_at[:10] == target_date:
        industry_rows = _aggregate_by_industry(daily_rows, target_date, stock_basics(), collected_at[:10])
    for row in industry_rows:
        row.update(query_date=collected_at[:10], retrieved_at=collected_at, index_type='I')
    data['industry_background'] = {'rows': industry_rows, 'label': '行业背景，不与概念混排'}
    registered = {code for code, m in meta.items() if is_reading_concept(m)}
    data['concept_directory'] = {'source': 'tushare.ths_index', 'index_type': 'N',
        'query_date': directory_at[:10] if directory_at else None, 'retrieved_at': directory_at,
        'basis': 'latest_at_query',
        'rows': [meta[code] for code in sorted(registered)], 'sample_count': len(registered),
        'price_count': len(ths_rows), 'missing_price_codes': sorted(registered - {r['code'] for r in ths_rows}),
        'excluded': [{'code': code, 'name': m.get('name'), 'reason': '目录原名明确为样本股或成份股篮子，不是主题概念'}
                     for code, m in sorted(meta.items()) if m.get('exchange') == 'A' and m.get('type') == 'N'
                     and not is_reading_concept(m)]}
    if ths_rows:
        data["reading_source_notes"].append("概念价格属于目标日；名称与类型按本次同花顺目录对应，未证明历史成分和分类未变。行业另作背景，不混排。")
    data["sector_change_up"] = _rank(rows, descending=True)
    data["sector_change_down"] = _rank(rows, descending=False)

    try:
        data["wind_a_alternative"] = (index_fact_fetcher(target_date) if index_fact_fetcher else _index_fact(target_date, pro=pro, ts_module=ts_module)) or {}
        if data["wind_a_alternative"]:
            data["wind_a_alternative"]["retrieved_at"] = collected_at
            data["wind_a_alternative"]["query_date"] = collected_at[:10]
        if data["wind_a_alternative"]:
            data["reading_collection"]["providers"].append({"name": "tushare.index_daily", "rows": 1})
        else:
            errors.append("tushare.index_daily 未返回目标日有效记录")
    except Exception as exc:
        data["wind_a_alternative"] = {}
        errors.append(f"tushare.index_daily: {exc.__class__.__name__}")
    if supplemental_collector is None:
        from report.sector_reading_sources import collect_reading_supplements
        supplemental_collector = collect_reading_supplements
    supplemental_collector(data, target_date, pro=pro, metadata=meta)
    return data


__all__ = ["collect_market_reading_data"]
