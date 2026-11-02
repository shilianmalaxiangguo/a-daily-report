"""Dated stock comparisons for the featured sectors, not buy recommendations."""
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import math
import re

from report.sector_fact_loader import _date, _number, _daily_change, _daily_amount, _target_date


def build_member_comparison(target_date, trade_dates, memberships, daily_rows, *, retrieved_at, notes=(),
                            listing_evidence=None):
    from report.sector_reading_history import evidence_hash
    target = _target_date(target_date)
    stamp = datetime.fromisoformat(retrieved_at)
    query = stamp.astimezone(timezone(timedelta(hours=8))).date().isoformat()
    if stamp.tzinfo is None or not target <= query <= datetime.now(timezone(timedelta(hours=8))).date().isoformat():
        raise ValueError('成分查询日期不符')
    days = [_date(d) for d in trade_dates]
    if not days or days != sorted(set(days)) or any(not d or d > target for d in days) or days[-1] != target:
        raise ValueError('成分榜交易日期不符')
    days = days[-6:]
    delisted = {}
    if listing_evidence is not None:
        listing_stamp = datetime.fromisoformat(listing_evidence['retrieved_at'])
        listing_query = listing_stamp.astimezone(timezone(timedelta(hours=8))).date().isoformat()
        if (listing_stamp.tzinfo is None or not target <= listing_query <= datetime.now(timezone(timedelta(hours=8))).date().isoformat()
                or listing_evidence.get('source') != 'tushare.stock_basic'):
            raise ValueError('成分上市资料来源或查询日期不符')
        for raw in listing_evidence.get('rows', []):
            code, removed = raw.get('ts_code'), _date(raw.get('delist_date'))
            listed = _date(raw.get('list_date'))
            if (not re.fullmatch(r'\d{6}\.(SH|SZ|BJ)', str(code or ''))
                    or raw.get('list_status') != 'D' or not listed or not removed
                    or not listed <= removed <= listing_query):
                raise ValueError('成分摘牌日期或代码不符')
            if code in delisted and delisted[code] != removed:
                raise ValueError('成分摘牌资料冲突')
            delisted[code] = removed
    bars = {}
    for row in daily_rows:
        code, day = str(row.get('code') or ''), _date(row.get('date'))
        if not re.fullmatch(r'\d{6}\.(SH|SZ|BJ)', code) or day not in days:
            raise ValueError('成分股行情日期或代码不符')
        change, amount = _number(row.get('change_pct')), _number(row.get('turnover_yi'))
        if change is not None and change <= -100 or amount is not None and amount < 0:
            raise ValueError('成分股行情数值不符')
        item = {'code': code, 'date': day, 'change_pct': change, 'turnover_yi': amount}
        # Old snapshots contain only derived returns; new rows keep available
        # prices without dropping valid turnover when either price is missing.
        if any(key in row for key in ('close', 'pre_close')):
            close, previous = _number(row.get('close')), _number(row.get('pre_close'))
            close = close if close is not None and close > 0 else None
            previous = previous if previous is not None and previous > 0 else None
            if change is not None:
                if close is None or previous is None:
                    raise ValueError('成分股原始价格不完整')
                recomputed = (close - previous) / previous * 100
                if abs(recomputed - change) > 1e-8:
                    raise ValueError('成分股原始价格与涨跌不一致')
            item.update(close=close, pre_close=previous)
        if (code, day) in bars and bars[code, day] != item:
            raise ValueError('成分股同日行情冲突')
        bars[code, day] = item
    sectors, normalized = {}, {}
    for identity, source in memberships.items():
        index_code = source['index_code']
        if not re.fullmatch(r'\d{6}\.TI', index_code) or identity != 'index:' + index_code:
            raise ValueError('成分板块身份不符')
        members = {}
        for raw in source.get('members') or []:
            if raw.get('ts_code') != index_code:
                raise ValueError('成分返回了其他板块')
            if raw.get('is_new') == 'N':
                continue
            code, name = str(raw.get('con_code') or ''), str(raw.get('con_name') or '').strip()
            if not re.fullmatch(r'\d{6}\.(SH|SZ|BJ)', code) or not name:
                raise ValueError('成分股名称或代码缺失')
            if code in members and members[code] != name:
                raise ValueError('成分股名称冲突')
            members[code] = name
        normalized[identity] = {'index_code': index_code, 'name': source['name'],
                                'members': [{'ts_code': index_code, 'con_code': code, 'con_name': name}
                                            for code, name in sorted(members.items())]}
        excluded = [{'code': code, 'name': name, 'delist_date': delisted[code],
                     'reason': '窗口开始前已摘牌，保留原目录记录，不作为缺失行情'}
                    for code, name in sorted(members.items()) if delisted.get(code, '9999') < days[0]]
        excluded_codes = {row['code'] for row in excluded}
        if any(code in excluded_codes for code, day in bars):
            raise ValueError('成分摘牌资料与窗口行情冲突')
        rows = []
        for code, name in sorted(members.items()):
            if code in excluded_codes:
                continue
            path = [bars.get((code, d), {}) for d in days]
            changes = [r.get('change_pct') for r in path[-5:]]
            amounts = [r.get('turnover_yi') for r in path[:-1]]
            five = ((math.prod(1 + v / 100 for v in changes) - 1) * 100
                    if len(days) >= 5 and all(v is not None for v in changes) else None)
            amount = path[-1].get('turnover_yi')
            average = (math.fsum(amounts) / 5 if len(amounts) == 5 and all(v is not None for v in amounts) else None)
            rows.append({'code': code, 'name': name, 'change_pct': path[-1].get('change_pct'),
                         'five_day_pct': five, 'turnover_yi': amount,
                         'activity_ratio': amount / average if amount is not None and average and average > 0 else None})
        def top(key):
            return [r['code'] for r in sorted((r for r in rows if r[key] is not None),
                                              key=lambda r: (-r[key], r['code']))[:5]]
        sectors[identity] = {'name': source['name'], 'index_code': index_code, 'member_count': len(members) - len(excluded),
                             'rows': rows, 'gain_codes': top('five_day_pct'), 'amount_codes': top('turnover_yi'),
                             'coverage': {'five_day': sum(r['five_day_pct'] is not None for r in rows),
                                          'amount': sum(r['turnover_yi'] is not None for r in rows)}}
        if excluded:
            sectors[identity].update(directory_member_count=len(members), excluded_members=excluded)
    value = {'schema_version': 'sector_member_comparison.v1', 'target_date': target, 'source_date': target,
             'query_date': query, 'retrieved_at': retrieved_at, 'membership_basis': 'latest_at_query',
             'source': 'tushare.ths_member+daily', 'trade_dates': days, 'memberships': normalized,
             'daily_rows': [bars[key] for key in sorted(bars)], 'sectors': sectors, 'notes': list(notes)}
    if listing_evidence is not None:
        value['listing_evidence'] = deepcopy(listing_evidence)
    value['artifact_hash'] = evidence_hash(value)
    return value


def validate_member_comparison(value, target_date):
    from report.sector_reading_history import evidence_hash
    if (not isinstance(value, dict) or value.get('target_date') != target_date
            or value.get('artifact_hash') != evidence_hash({k: v for k, v in value.items() if k != 'artifact_hash'})):
        raise ValueError('成分榜日期或指纹不符')
    rebuilt = build_member_comparison(target_date, value['trade_dates'], value['memberships'], value['daily_rows'],
                                     retrieved_at=value['retrieved_at'], notes=value.get('notes', []),
                                     listing_evidence=value.get('listing_evidence'))
    if rebuilt != value:
        raise ValueError('成分榜数值投影不符')
    return deepcopy(value)


def member_relative_returns(value, view):
    """Compare the same five daily returns, not two independently chosen windows."""
    dates = value['trade_dates'][-5:]
    history = view.get('ranking_returns') or view.get('heat') or {}
    sector_dates = history.get('dates') or []
    sectors = {r['track_id']: dict(zip(sector_dates, r['pct'])) for r in history.get('rows', [])}
    result = {}
    for identity, sector in value['sectors'].items():
        source = sectors.get(identity, {})
        changes = [source.get(day) for day in dates]
        complete = (len(dates) == 5 and sector_dates[-5:] == dates
                    and all(v is not None for v in changes))
        benchmark = (math.prod(1 + v / 100 for v in changes) - 1) * 100 if complete else None
        result[identity] = {'rows': {r['code']: {
            'stock_pct': r['five_day_pct'], 'sector_pct': benchmark,
            'excess_pp': r['five_day_pct'] - benchmark
                         if r['five_day_pct'] is not None and benchmark is not None else None,
        } for r in sector['rows']}}
    return {'dates': dates, 'sectors': result, 'method': '同五个交易日日收益复利差；非可成交净收益或已识别alpha',
            'price_basis_note': '个股按原始收盘与前收盘价、指数按来源日涨跌复利；未证明统一复权或含分红收益。'}


def collect_member_comparison(pro, view, *, retrieved_at=None, member_fetcher=None, daily_fetcher=None,
                              listing_fetcher=None):
    from market_data.tushare_market_activity_service import fetch_tushare_open_trade_dates
    from market_data.tushare_turnover_service import fetch_stock_daily_turnover_records
    from report.sector_reading_history import numeric_trend_view
    target = _target_date(view['target_date'])
    view = numeric_trend_view(view, target)
    selected = {r['track_id'] for r in view['chart_selection']['comparison']}
    stamp = retrieved_at or datetime.now(timezone(timedelta(hours=8))).isoformat()
    start = (date.fromisoformat(target) - timedelta(days=25)).isoformat()
    days = fetch_tushare_open_trade_dates(start, target, pro=pro)[-6:]
    if not days or days[-1] != target:
        raise ValueError('成分榜缺少目标交易日历')
    memberships, notes = {}, []
    for track in view['tracks']:
        identity = track['track_id']
        if identity not in selected or not identity.startswith('index:'):
            continue
        code = identity.removeprefix('index:')
        try:
            members = (member_fetcher(code) if member_fetcher else pro.ths_member(ts_code=code).to_dict('records'))
        except Exception as error:
            members = []
            notes.append(f'{track["name"]}成分未能取得（{type(error).__name__}）')
        memberships[identity] = {'name': track['name'], 'index_code': code, 'members': members}
    wanted = {r['con_code'] for source in memberships.values() for r in source['members']}
    rows = []
    if wanted:
        for day in days:
            try:
                raw = (daily_fetcher(day) if daily_fetcher else
                       fetch_stock_daily_turnover_records(day, pro=pro, page_retry_count=1))
                if any(_date(r.get('trade_date')) != day for r in raw):
                    raise ValueError('成分股行情日期不符')
                rows.extend(
                    {
                        'code': r['ts_code'],
                        'date': day,
                        'change_pct': _daily_change(r),
                        'turnover_yi': _daily_amount(r),
                        'close': r.get('close'),
                        'pre_close': r.get('pre_close'),
                    }
                    for r in raw if r.get('ts_code') in wanted
                )
            except Exception as error:
                notes.append(f'{day}成分股行情未能取得（{type(error).__name__}）；该日不补零')
    listing_rows = []
    absent = wanted - {row['code'] for row in rows}
    if rows and (listing_fetcher is not None or callable(getattr(pro, 'query', None))):
        for code in sorted(absent):
            try:
                listed = (listing_fetcher(code) if listing_fetcher else pro.stock_basic(
                    ts_code=code, list_status='D', fields='ts_code,name,list_date,delist_date,list_status').to_dict('records'))
                if any(row.get('ts_code') != code for row in listed):
                    raise ValueError('摘牌查询返回其他股票')
                query_day = datetime.now(timezone(timedelta(hours=8))).date().isoformat()
                if any(row.get('list_status') != 'D' or not _date(row.get('list_date'))
                       or not _date(row.get('delist_date'))
                       or not _date(row['list_date']) <= _date(row['delist_date']) <= query_day
                       for row in listed):
                    raise ValueError('摘牌资料日期或上市状态不符')
                listing_rows.extend(listed)
            except Exception:
                notes.append(f'{code}上市状态未能核对，保留行情缺口。')
    evidence = ({'source': 'tushare.stock_basic', 'retrieved_at': datetime.now(timezone(timedelta(hours=8))).isoformat(),
                 'rows': listing_rows} if listing_rows else None)
    return build_member_comparison(target, days, memberships, rows, retrieved_at=stamp, notes=notes,
                                   listing_evidence=evidence)
