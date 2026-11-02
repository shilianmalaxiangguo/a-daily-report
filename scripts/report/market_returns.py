"""Dated full-market daily prices for the market-relation (alpha/beta) reading.

Only facts that the provider returns for an explicit trade date are kept. A day
that cannot be verified stays missing; it is never filled from another day.
"""
from datetime import date, datetime, timedelta
import json
import math
import os
from pathlib import Path
import re
import tempfile
from zoneinfo import ZoneInfo

from report.fact_utils import _date, _number, _target_date, evidence_hash

SCHEMA = 'market_returns.v2'
BENCHMARK = {'code': '000985.CSI', 'name': '中证全指'}
SESSIONS = 61
A_SHARE = re.compile(r'(6\d{5}\.SH|[03]\d{5}\.SZ)')
# The provider rounds pct_chg; prices remain the canonical return source.
PCT_TOLERANCE = 0.011
SOURCE = 'tushare.daily + index_daily + stock_basic + stock_st + trade_cal'
SHANGHAI = ZoneInfo('Asia/Shanghai')
# One text line per session ("index,close,pre_close,open,amount;..."): snapshots are
# written with indentation, which would put every number of a nested array on its own
# line. Open and amount (thousand yuan, rounded) serve next-open entry and liquidity.
PRICE_FORMAT = 'index,close,pre_close,open,amount_k;'


def _text(number):
    return '' if number is None else repr(number)


def encode_prices(rows):
    return ';'.join(f'{index},{close!r},{previous!r},{_text(opened)},{_text(amount)}'
                    for index, close, previous, opened, amount in rows)


def price_rows(value, day):
    text = value['prices'].get(day)
    if not text:
        return []
    rows = []
    for item in text.split(';'):
        index, close, previous, opened, amount = item.split(',')
        rows.append((int(index), float(close), float(previous),
                     float(opened) if opened else None, float(amount) if amount else None))
    return rows


def _now():
    return datetime.now(SHANGHAI)


def _query_date(retrieved_at, day):
    stamp = datetime.fromisoformat(retrieved_at)
    if stamp.tzinfo is None or stamp > _now() or stamp.astimezone(SHANGHAI).date().isoformat() < day:
        raise ValueError('全市场行情取得时间与事实日不符')
    return stamp.astimezone(SHANGHAI).date().isoformat()


def _pages(pro, endpoint, *, limit=6000, **params):
    rows = []
    for _ in range(10):
        page = getattr(pro, endpoint)(**params, limit=limit, offset=len(rows)).to_dict('records')
        rows.extend(page)
        if len(page) < limit:
            return rows
    raise ValueError('全市场行情分页超出单日范围')


def sessions_from_calendar(rows, target_date, count=SESSIONS):
    indexed = {}
    for row in rows:
        day, opened = _date(row.get('cal_date') or row.get('date')), _number(row.get('is_open'))
        if not day or day > target_date or day in indexed or opened not in (0, 1):
            raise ValueError('全市场行情交易日历日期重复、越界或开市标记不符')
        indexed[day] = int(opened)
    if not indexed:
        raise ValueError('全市场行情交易日历为空')
    start = date.fromisoformat(min(indexed))
    span = (date.fromisoformat(target_date) - start).days + 1
    expected = [(start + timedelta(days=i)).isoformat() for i in range(span)]
    if sorted(indexed) != expected:
        raise ValueError('全市场行情交易日历缺日，不能跳过缺失日期')
    opened = [day for day in expected if indexed[day]]
    if len(opened) < count or opened[-1] != target_date:
        raise ValueError('全市场行情交易日历开放日不足或缺目标日期')
    return opened[-count:]


def _clean_rows(page, day):
    """Return {code: (close, pre_close, open, amount_k)} and the number of rejected rows."""
    if page.get('source') != 'tushare.daily' or _date(page.get('trade_date')) != day:
        raise ValueError('全市场行情原始来源或日期不符')
    kept, rejected, seen = {}, 0, set()
    for raw in page.get('rows') or []:
        code = str(raw.get('ts_code') or '')
        if code in seen or _date(raw.get('trade_date')) != day:
            raise ValueError('全市场行情原始明细重复或日期不符')
        seen.add(code)
        if not A_SHARE.fullmatch(code):
            continue
        close, previous, source_pct = (_number(raw.get(k)) for k in ('close', 'pre_close', 'pct_chg'))
        if close is None or previous is None or close <= 0 or previous <= 0:
            rejected += 1
            continue
        derived = (close - previous) / previous * 100
        if source_pct is not None and abs(derived - source_pct) > PCT_TOLERANCE:
            rejected += 1
            continue
        opened, amount = _number(raw.get('open')), _number(raw.get('amount'))
        kept[code] = (close, previous, opened if opened is not None and opened > 0 else None,
                      float(round(amount)) if amount is not None and amount >= 0 else None)
    return kept, rejected


def build_market_returns(target_date, trade_dates, daily_pages, benchmark_rows, basics_rows, st_rows, *,
                         retrieved_at, provider_hosts=(), issues=()):
    target = _target_date(target_date)
    query = _query_date(retrieved_at, target)
    days = list(trade_dates)
    if not days or days[-1] != target or days != sorted(set(days)) or len(days) > SESSIONS:
        raise ValueError('全市场行情交易日期不符')
    issues = [dict(issue) for issue in issues]
    cleaned, rejected = {}, {}
    for day in days:
        page = daily_pages.get(day)
        if page is None:
            continue
        kept, dropped = _clean_rows(page, day)
        cleaned[day], rejected[day] = kept, dropped
    counts = sorted(len(rows) for rows in cleaned.values())
    if counts:
        typical = counts[len(counts) // 2]
        for day in list(cleaned):
            # A partially updated day would distort same-day breadth; keep it missing.
            if len(cleaned[day]) < typical * 0.9:
                issues.append({'date': day, 'reason': '当日个股样本明显少于其他交易日，按缺失处理'})
                del cleaned[day]
    if target not in cleaned:
        raise ValueError('目标日全市场个股行情未取得，停止计算大盘关系')
    benchmark = {}
    for row in benchmark_rows:
        day = _date(row.get('trade_date') or row.get('date'))
        close, previous = _number(row.get('close')), _number(row.get('pre_close'))
        opened = _number(row.get('open'))
        if row.get('ts_code', BENCHMARK['code']) != BENCHMARK['code'] or not day or day > target:
            raise ValueError('大盘基准代码或日期不符')
        if day not in days:
            continue
        if close is None or previous is None or close <= 0 or previous <= 0:
            continue
        value = (close, previous, opened if opened is not None and opened > 0 else None)
        if day in benchmark and benchmark[day] != value:
            raise ValueError('大盘基准同日数值冲突')
        benchmark[day] = value
    if target not in benchmark:
        raise ValueError('目标日大盘基准未取得，停止计算大盘关系')
    profiles = {}
    for row in basics_rows:
        code = str(row.get('ts_code') or '')
        if A_SHARE.fullmatch(code):
            profiles[code] = (str(row.get('name') or '').strip(), str(row.get('industry') or '').strip(),
                              _date(row.get('list_date')) or '')
    codes = sorted({code for rows in cleaned.values() for code in rows})
    position = {code: i for i, code in enumerate(codes)}
    st = None
    if st_rows is not None:
        if any(_date(row.get('trade_date')) != target for row in st_rows):
            raise ValueError('ST名单日期与目标日不符')
        st = sorted({str(row.get('ts_code')) for row in st_rows if A_SHARE.fullmatch(str(row.get('ts_code') or ''))})
    value = {
        'schema': SCHEMA, 'target_date': target, 'source_date': target, 'query_date': query,
        'retrieved_at': retrieved_at, 'data_source': SOURCE, 'provider_hosts': list(provider_hosts),
        'benchmark': {**BENCHMARK, 'rows': [{'date': day, 'close': benchmark[day][0], 'pre_close': benchmark[day][1],
                                             'open': benchmark[day][2]} for day in days if day in benchmark]},
        'trade_dates': days, 'codes': codes,
        'profile': {'basis': 'latest_at_query', 'query_date': query,
                    'names': [profiles.get(code, ('', '', ''))[0] for code in codes],
                    'industries': [profiles.get(code, ('', '', ''))[1] for code in codes],
                    'list_dates': [profiles.get(code, ('', '', ''))[2] for code in codes]},
        'st_codes': st, 'st_date': target if st is not None else None,
        'price_format': PRICE_FORMAT,
        'prices': {day: encode_prices((position[code], *cleaned[day][code]) for code in sorted(cleaned[day]))
                   for day in days if day in cleaned},
        'rejected_rows': {day: count for day, count in rejected.items() if count},
        'issues': issues,
    }
    value['artifact_hash'] = evidence_hash(value)
    return value


def validate_market_returns(value, target_date):
    if (not isinstance(value, dict) or value.get('schema') != SCHEMA or value.get('target_date') != target_date
            or value.get('source_date') != target_date
            or value.get('artifact_hash') != evidence_hash({k: v for k, v in value.items() if k != 'artifact_hash'})):
        raise ValueError('全市场行情日期或指纹不符')
    days, codes = value['trade_dates'], value['codes']
    if (not days or days[-1] != target_date or days != sorted(set(days)) or len(days) > SESSIONS
            or codes != sorted(set(codes)) or any(not A_SHARE.fullmatch(code) for code in codes)
            or value['query_date'] < target_date):
        raise ValueError('全市场行情日期或股票代码不符')
    profile = value['profile']
    if any(len(profile[key]) != len(codes) for key in ('names', 'industries', 'list_dates')):
        raise ValueError('全市场行情股票资料长度不符')
    if (target_date not in value['prices'] or any(day not in days for day in value['prices'])
            or value.get('price_format') != PRICE_FORMAT):
        raise ValueError('全市场行情缺少目标日或含其他日期')
    for day in value['prices']:
        seen = set()
        try:
            rows = price_rows(value, day)
        except (ValueError, AttributeError) as error:
            raise ValueError('全市场行情价格明细不符') from error
        for index, close, previous, opened, amount in rows:
            if (not isinstance(index, int) or not 0 <= index < len(codes) or index in seen
                    or not close > 0 or not previous > 0 or not math.isfinite(close) or not math.isfinite(previous)
                    or opened is not None and not (opened > 0 and math.isfinite(opened))
                    or amount is not None and not (amount >= 0 and math.isfinite(amount))):
                raise ValueError('全市场行情价格明细不符')
            seen.add(index)
    bench = value['benchmark']
    if (bench.get('code') != BENCHMARK['code'] or not bench['rows'] or bench['rows'][-1]['date'] != target_date
            or any(row['date'] not in days for row in bench['rows'])):
        raise ValueError('大盘基准日期不符')
    return value


def _cache_page(root, day, page):
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=root, delete=False) as stream:
        json.dump(page, stream, ensure_ascii=False, allow_nan=False)
        temporary = Path(stream.name)
    try:
        os.replace(temporary, root / (day + '.json'))
    finally:
        temporary.unlink(missing_ok=True)


def collect_market_returns(pro, target_date, *, cache_root=None, provider_hosts=(), sessions=SESSIONS):
    """Fetch explicit-date daily prices; cached days are re-validated, never trusted blindly."""
    target = _target_date(target_date)
    start = (date.fromisoformat(target) - timedelta(days=150)).strftime('%Y%m%d')
    calendar = _pages(pro, 'trade_cal', exchange='SSE', start_date=start, end_date=target.replace('-', ''),
                      fields='cal_date,is_open')
    days = sessions_from_calendar(calendar, target, sessions)
    root = Path(cache_root) if cache_root is not None else Path(__file__).resolve().parents[2] / 'data/market-returns'
    pages, issues = {}, []
    for day in days:
        path = root / (day + '.json')
        page = None
        if path.is_file():
            try:
                page = json.loads(path.read_text(encoding='utf-8'))
                _clean_rows(page, day)
            except (ValueError, TypeError, KeyError, AttributeError):
                page = None
        if page is None:
            try:
                rows = _pages(pro, 'daily', trade_date=day.replace('-', ''),
                              fields='ts_code,trade_date,open,close,pre_close,pct_chg,amount')
                page = {'source': 'tushare.daily', 'trade_date': day, 'source_date': day, 'rows': rows,
                        'configured_provider_hosts': list(provider_hosts), 'retrieved_at': _now().isoformat()}
                _clean_rows(page, day)
                # The target day may still be updating; only settled days are cached.
                if day < target or _now().date().isoformat() > target or _now().hour >= 18:
                    _cache_page(root, day, page)
            except Exception as error:
                issues.append({'date': day, 'reason': '该日个股行情未取得，保留缺口', 'error_type': type(error).__name__})
                continue
        pages[day] = page
    benchmark = _pages(pro, 'index_daily', ts_code=BENCHMARK['code'], start_date=days[0].replace('-', ''),
                       end_date=target.replace('-', ''), fields='ts_code,trade_date,open,close,pre_close')
    basics = _pages(pro, 'stock_basic', exchange='', list_status='L', fields='ts_code,name,industry,list_date')
    try:
        st_rows = _pages(pro, 'stock_st', limit=1000, trade_date=target.replace('-', ''), fields='ts_code,trade_date')
    except Exception as error:
        st_rows = None
        issues.append({'date': target, 'reason': '目标日ST名单未取得，改按查询日简称识别', 'error_type': type(error).__name__})
    return build_market_returns(target, days, pages, benchmark, basics, st_rows, retrieved_at=_now().isoformat(),
                                provider_hosts=provider_hosts, issues=issues)


def eligible_artifact_rows(value):
    """Exclude target-day ST stocks and stocks first listed inside the data span."""
    first = value['trade_dates'][0]
    st = set(value['st_codes'] or [])
    profile = value['profile']
    result, excluded = [], {'st': 0, 'new_listing': 0}
    for index, code in enumerate(value['codes']):
        name = profile['names'][index]
        is_st = code in st if value['st_codes'] is not None else name.upper().startswith(('ST', '*ST'))
        listed = profile['list_dates'][index]
        if is_st:
            excluded['st'] += 1
        elif not listed or listed >= first:
            excluded['new_listing'] += 1
        else:
            result.append(index)
    return result, excluded
