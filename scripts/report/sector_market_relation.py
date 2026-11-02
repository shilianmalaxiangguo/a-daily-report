"""Dated market relationships, separate from stock-versus-sector differences."""
from copy import deepcopy
from datetime import datetime
import math
from zoneinfo import ZoneInfo

from report.sector_fact_loader import _date, _number, _daily_change, _daily_amount, _row_date
from report.sector_reading_history import evidence_hash, numeric_trend_view

SCHEMA = 'sector_member_history.v1'
BENCHMARK = {'code': '000985.CSI', 'name': '中证全指'}


def build_member_history(view, daily_rows, *, trade_dates, retrieved_at, provider_hosts=(), issues=()):
    """Retain additional raw prices without replacing the frozen five-day facts."""
    target = view['target_date']
    view = numeric_trend_view(view, target)
    members = view.get('member_comparison')
    inputs = view.get('price_inputs')
    if not members or not inputs or view.get('calendar_verified') is not True:
        raise ValueError('大盘关系缺少已核对的成员或交易日历')
    stamp = datetime.fromisoformat(retrieved_at)
    now = datetime.now(ZoneInfo('Asia/Shanghai'))
    query = stamp.astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat()
    if stamp.tzinfo is None or stamp > now or query < target:
        raise ValueError('关系资料查询日期不符')
    calendar = (view.get('price_inputs') or {}).get('trade_dates') or []
    days = list(trade_dates)
    if (not days or days[-1] != target or days != calendar[-len(days):]
            or days != sorted(set(days)) or len(days) > 61):
        raise ValueError('关系资料交易日期与原日历不符')
    wanted = {r['code'] for s in members['sectors'].values() for r in s['rows']}
    old = {(r['code'], r['date']): r for r in members['daily_rows']}
    rows = {}
    for source in daily_rows:
        code, day = source.get('code'), _date(source.get('date'))
        if code not in wanted or day not in days:
            raise ValueError('关系资料包含其他股票或日期')
        close, previous = _number(source.get('close')), _number(source.get('pre_close'))
        change, amount = _number(source.get('change_pct')), _number(source.get('turnover_yi'))
        if close is not None and close <= 0 or previous is not None and previous <= 0:
            raise ValueError('关系资料原始价格无效')
        if change is not None:
            if close is None or previous is None or change <= -100:
                raise ValueError('关系资料原始价格不完整')
            if abs((close - previous) / previous * 100 - change) > 1e-8:
                raise ValueError('关系资料原始价格与涨跌不一致')
        if amount is not None and amount < 0:
            raise ValueError('关系资料成交额无效')
        row = {'code': code, 'date': day, 'close': close, 'pre_close': previous,
               'change_pct': change, 'turnover_yi': amount}
        key = (code, day)
        if key in rows and rows[key] != row:
            raise ValueError('关系资料同日价格冲突')
        original = old.get(key, {})
        for field in ('change_pct', 'close', 'pre_close', 'turnover_yi'):
            value = original.get(field)
            if value is not None and (row[field] is None or abs(value - row[field]) > 1e-8):
                raise ValueError('关系资料不能替换原有价格事实')
        rows[key] = row
    # An extension cannot silently lose existing valid observations in its window.
    if any(day in days and r.get('change_pct') is not None and (code, day) not in rows
           for (code, day), r in old.items()):
        raise ValueError('关系资料缺少原有价格事实')
    value = {'schema_version': SCHEMA, 'target_date': target, 'source_date': target,
             'query_date': query, 'retrieved_at': retrieved_at, 'source': 'tushare.daily',
             'benchmark': deepcopy(BENCHMARK), 'price_inputs_hash': evidence_hash(inputs),
             'provider_hosts': list(provider_hosts), 'membership_hash': members['artifact_hash'],
             'membership_query_date': members['query_date'], 'membership_basis': members['membership_basis'],
             'trade_dates': days, 'daily_rows': [rows[key] for key in sorted(rows)], 'issues': list(issues)}
    value['artifact_hash'] = evidence_hash(value)
    return value


def validate_member_history(value, view):
    if (value.get('schema_version') != SCHEMA
            or value.get('artifact_hash') != evidence_hash({k: v for k, v in value.items() if k != 'artifact_hash'})
            or value.get('membership_hash') != (view.get('member_comparison') or {}).get('artifact_hash')):
        raise ValueError('关系资料成员或指纹不符')
    rebuilt = build_member_history(view, value['daily_rows'], trade_dates=value['trade_dates'],
        retrieved_at=value['retrieved_at'], provider_hosts=value['provider_hosts'], issues=value['issues'])
    if rebuilt != value:
        raise ValueError('关系资料与原始价格投影不符')
    return value


def collect_member_history(pro, view, *, window=20, provider_hosts=(), daily_fetcher=None):
    """Fetch only dated daily prices for the already frozen member set."""
    from market_data.tushare_turnover_service import fetch_stock_daily_turnover_records
    raw_view = view
    view = numeric_trend_view(raw_view, raw_view['target_date'])
    if window not in (20, 60):
        raise ValueError('关系资料仅支持20日或60日窗口')
    calendar = (view.get('price_inputs') or {}).get('trade_dates') or []
    days = calendar[-window - 1:]
    wanted = {r['code'] for s in view['member_comparison']['sectors'].values() for r in s['rows']}
    rows, issues = [], []
    for day in days:
        try:
            raw = (daily_fetcher(day) if daily_fetcher else
                   fetch_stock_daily_turnover_records(day, pro=pro, page_retry_count=1))
            if not raw or any(_row_date(r) != day for r in raw):
                raise ValueError('关系资料返回其他日期')
            rows.extend({'code': r['ts_code'], 'date': day, 'close': _number(r.get('close')),
                         'pre_close': _number(r.get('pre_close')), 'change_pct': _daily_change(r),
                         'turnover_yi': _daily_amount(r)} for r in raw if r.get('ts_code') in wanted)
        except Exception as error:
            issues.append({'date': day, 'reason': '该日查询未取得，保留缺口', 'error_type': type(error).__name__})
    return build_member_history(raw_view, rows, trade_dates=days,
        retrieved_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(), provider_hosts=provider_hosts, issues=issues)


def relation_summary(stock, market):
    if len(stock) != len(market):
        raise ValueError('个股与大盘关系窗口不同')
    def path(values):
        level, out = 100., [100.]
        for value in values:
            level = level * (1 + value / 100) if value is not None and level is not None else None
            out.append(level)
        return out
    pairs = [(a, b) for a, b in zip(stock, market) if a is not None and b is not None]
    complete = len(pairs) == len(stock) and bool(stock)
    stock_path, market_path = path(stock), path(market)
    up = [a for a, b in pairs if b > 0]
    down = [a for a, b in pairs if b < 0]
    return {'requested_days': len(stock), 'valid_days': len(pairs), 'complete': complete,
            'same_direction_days': sum(a * b > 0 for a, b in pairs) if complete else None,
            'market_up_days': len(up), 'market_down_days': len(down),
            'market_flat_days': sum(b == 0 for _, b in pairs),
            'market_up_stock_mean_pct': math.fsum(up) / len(up) if complete and up else None,
            'market_down_stock_mean_pct': math.fsum(down) / len(down) if complete and down else None,
            'stock_pct': stock_path[-1] - 100 if complete else None,
            'market_pct': market_path[-1] - 100 if complete else None,
            'excess_pp': stock_path[-1] - market_path[-1] if complete else None,
            'stock_path': stock_path, 'market_path': market_path}


def build_market_relation(raw_view, history=None):
    view = numeric_trend_view(raw_view, raw_view['target_date'])
    members = view.get('member_comparison')
    if not members or not view.get('price_inputs') or view.get('calendar_verified') is not True:
        return None
    if history is not None:
        validate_member_history(history, raw_view)
    source = history or members
    days = source['trade_dates']
    market_bars = {r['date']: r.get('close') for r in (view.get('price_inputs') or {}).get('market_bars', [])}
    market = [None]
    for previous, day in zip(days, days[1:]):
        a, b = market_bars.get(previous), market_bars.get(day)
        market.append((b / a - 1) * 100 if a and b else None)
    bars = {(r['code'], r['date']): r['change_pct'] for r in source['daily_rows']}
    index = view.get('ranking_returns') or view['heat']
    sectors = {r['track_id']: dict(zip(index['dates'], r['pct'])) for r in index['rows']}
    windows = [n for n in (5, 20, 60) if len(days) > n]
    wanted = {r['code'] for s in members['sectors'].values() for r in s['rows']}
    return {'benchmark': deepcopy(BENCHMARK), 'target_date': view['target_date'], 'dates': list(days),
            'available_windows': windows, 'default_window': 20 if 20 in windows else 5,
            'short_history': 20 not in windows, 'query_date': source['query_date'],
            'membership_query_date': members['query_date'], 'membership_basis': members['membership_basis'],
            'history_hash': source['artifact_hash'], 'market': market,
            'sectors': {identity: [sectors.get(identity, {}).get(day) for day in days]
                        for identity in members['sectors']},
            'stocks': {code: [bars.get((code, day)) for day in days] for code in sorted(wanted)},
            'issues': deepcopy(source.get('issues', []))}
