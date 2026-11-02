"""Dated new-high facts for the reading page; no legacy report or database writes."""
from datetime import date, datetime, timedelta
import hashlib
import json
import math
from pathlib import Path
import re
import os
import tempfile
from zoneinfo import ZoneInfo

SCHEMA = 'sector_new_high.v1'
SOURCE = 'tushare.stk_factor_pro.topdays + daily + stock_st + stock_basic + trade_cal'
METHOD = ('TOPRANGE(HIGH)字段topdays >= 250；分子排除当日ST及上市不足365自然日。'
          '分母为当日有成交A股日线样本（含北交所、ST和新股），不是全部上市总数。'
          '沿用来源最高价因子，不冒称收盘价新高；来源文档未明确该字段的复权方式。')


def _hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     allow_nan=False).encode()).hexdigest()


def _date(value):
    text = str(value or '')
    if re.fullmatch(r'\d{8}', text):
        text = f'{text[:4]}-{text[4:6]}-{text[6:]}'
    return date.fromisoformat(text).isoformat()


def _number(value):
    if isinstance(value, bool) or value is None or value == '':
        return None
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (ValueError, TypeError):
        return None


def _stamp(value, day):
    stamp = datetime.fromisoformat(value)
    now = datetime.now(ZoneInfo('Asia/Shanghai'))
    if stamp.tzinfo is None or stamp > now or stamp.astimezone(now.tzinfo).date() < date.fromisoformat(day):
        raise ValueError('创新高查询时间与事实日期不符')
    return stamp.astimezone(now.tzinfo).date().isoformat()


def _indexed(rows, day):
    result = {}
    for row in rows:
        code = row.get('ts_code')
        if (not isinstance(code, str) or not re.fullmatch(r'\d{6}\.(SH|SZ|BJ)', code)
                or _date(row.get('trade_date')) != day):
            raise ValueError('创新高明细代码或来源日期不符')
        if code in result:
            raise ValueError('创新高明细代码重复，不能证明样本完整')
        result[code] = row
    return result


def build_new_high_day(raw):
    day = _date(raw['trade_date'])
    query = _stamp(raw['retrieved_at'], day)
    daily = _indexed(raw['daily_rows'], day)
    factors = _indexed(raw['factor_rows'], day)
    st = _indexed(raw['st_rows'], day)
    if not daily or not factors or not st:
        raise ValueError('创新高日线、因子或当日ST名单为空，无法核验统计范围')
    if factors.keys() - daily.keys():
        raise ValueError('创新高因子与日线覆盖不一致，无法核验分母')
    universe, excluded, eligible, winners = [], {'st': 0, 'recent_listing': 0}, [], []
    for code, row in daily.items():
        values = [_number(row.get(key)) for key in ('high', 'vol', 'amount')]
        if any(value is None or value < 0 for value in values):
            raise ValueError('创新高日线价格或成交字段不完整')
        if values[1] == 0 or values[2] == 0:
            continue
        if values[0] <= 0:
            raise ValueError('创新高日线价格无效')
        universe.append(code)
        if code in st:
            excluded['st'] += 1
            continue
        try:
            age = (date.fromisoformat(day) - date.fromisoformat(_date(raw['list_dates'].get(code)))).days
        except (ValueError, TypeError) as error:
            raise ValueError('创新高样本缺少上市日期') from error
        if age < 0:
            raise ValueError('创新高样本上市日期晚于行情日期')
        if age < 365:
            excluded['recent_listing'] += 1
            continue
        value = _number(factors.get(code, {}).get('topdays'))
        if value is None or value < 0 or not value.is_integer():
            raise ValueError('创新高统计范围内缺少有效topdays因子')
        eligible.append(code)
        if value >= 250:
            winners.append(code)
    if not universe:
        raise ValueError('创新高没有当日有效成交样本')
    return {'date': day, 'source_date': day, 'query_date': query, 'retrieved_at': raw['retrieved_at'],
            'data_source': SOURCE, 'source_sha256': _hash(raw), 'new_high_count': len(winners),
            'new_high_share_pct': len(winners) / len(universe) * 100,
            'all_a_denominator': len(universe), 'eligible_count': len(eligible),
            'excluded_counts': excluded, 'new_high_codes': sorted(winners), 'missing_reason': ''}


def _pages(pro, endpoint, *, limit=6000, **params):
    rows = []
    for _ in range(10):
        page = getattr(pro, endpoint)(**params, limit=limit, offset=len(rows)).to_dict('records')
        rows.extend(page)
        if len(page) < limit:
            return rows
    raise ValueError('创新高来源分页超出单日范围')


def _calendar(pro, target_date, window_days):
    start = date.fromisoformat(target_date) - timedelta(days=70)
    rows = _pages(pro, 'trade_cal', exchange='SSE', start_date=start.strftime('%Y%m%d'),
                  end_date=target_date.replace('-', ''), fields='cal_date,is_open')
    indexed = {}
    for row in rows:
        day, opened = _date(row.get('cal_date')), _number(row.get('is_open'))
        if day in indexed or opened not in (0, 1):
            raise ValueError('创新高交易日历日期重复或开市标记不符')
        indexed[day] = int(opened)
    expected = [(start + timedelta(days=i)).isoformat() for i in range(71)]
    if sorted(indexed) != expected:
        raise ValueError('创新高交易日历不完整，不能跳过缺失日期')
    days = [day for day in expected if indexed[day]]
    if len(days) < window_days or days[-1] != target_date:
        raise ValueError('创新高交易日历开放日不足或缺目标日期')
    return days[-window_days:], {'start_date': start.isoformat(), 'end_date': target_date,
                                'rows': [{'date': day, 'is_open': indexed[day]} for day in expected],
                                'retrieved_at': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()}


def collect_new_high_series(pro, target_date, *, cache_root=None, window_days=25):
    """Only live/explicit repair calls reach here. Replay consumes the frozen result."""
    target_date = _date(target_date)
    if target_date > datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat():
        raise ValueError('创新高目标日期晚于今天')
    if type(window_days) is not int or not 1 <= window_days <= 25:
        raise ValueError('创新高窗口必须为1至25个交易日')
    days, calendar = _calendar(pro, target_date, window_days)
    root = Path(cache_root) if cache_root is not None else Path(__file__).resolve().parents[2] / '.generated/new-high-facts-v1'
    root.mkdir(parents=True, exist_ok=True)
    basics, basic_error, items, cache_repairs = None, None, [], []
    for day in days:
        path = root / (day + '.json')
        try:
            row = None
            if path.is_file():
                original = path.read_bytes()
                try:
                    raw = json.loads(original)
                    if raw.get('trade_date') != day:
                        raise ValueError('创新高原始资料日期与文件名不符')
                    row = build_new_high_day(raw)
                except (ValueError, KeyError, TypeError, AttributeError):
                    digest = hashlib.sha256(original).hexdigest()
                    backup = root / (day + '.invalid-' + digest + '.json')
                    if not backup.exists():
                        backup.write_bytes(original)
                    cache_repairs.append({'date': day, 'invalid_sha256': digest})
            if row is None:
                if basic_error is not None:
                    raise basic_error
                if basics is None:
                    try:
                        basics = {}
                        for status in ('L', 'D', 'P'):
                            for item in _pages(pro, 'stock_basic', list_status=status, fields='ts_code,list_date'):
                                code, listed = item['ts_code'], _date(item['list_date'])
                                if code in basics and basics[code] != listed:
                                    raise ValueError('创新高上市日期来源冲突')
                                basics[code] = listed
                    except Exception as error:
                        basic_error = error
                        raise
                compact = day.replace('-', '')
                daily = _pages(pro, 'daily', trade_date=compact, fields='ts_code,trade_date,high,vol,amount')
                raw = {'trade_date': day, 'daily_rows': daily,
                       'factor_rows': _pages(pro, 'stk_factor_pro', trade_date=compact, fields='ts_code,trade_date,topdays'),
                       'st_rows': _pages(pro, 'stock_st', limit=1000, trade_date=compact, fields='ts_code,trade_date'),
                       'list_dates': {r['ts_code']: basics.get(r['ts_code']) for r in daily},
                       'retrieved_at': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()}
                row = build_new_high_day(raw)
                # Only complete, reproducible days are cached; failures retry next live run.
                with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=root, delete=False) as handle:
                    json.dump(raw, handle, ensure_ascii=False, allow_nan=False)
                    temporary = Path(handle.name)
                try:
                    os.replace(temporary, path)
                finally:
                    temporary.unlink(missing_ok=True)
            items.append(row)
        except Exception as error:
            detail = str(error) if isinstance(error, ValueError) else '来源请求失败'
            stamp = datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
            items.append({'date': day, 'source_date': day, 'query_date': stamp[:10], 'retrieved_at': stamp,
                          'data_source': SOURCE, 'new_high_count': None, 'new_high_share_pct': None,
                          'missing_reason': f'{detail}（{type(error).__name__}）'})
    stamp = datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
    result = {'schema': SCHEMA, 'target_date': target_date, 'source_date': target_date,
              'query_date': stamp[:10], 'retrieved_at': stamp, 'data_source': SOURCE,
              'method': METHOD, 'window_days': window_days, 'calendar': calendar,
              'cache_repairs': cache_repairs, 'trade_dates': days, 'items': items}
    result['artifact_hash'] = _hash(result)
    validate_new_high_series(result, target_date)
    return result


def validate_new_high_series(value, target_date):
    if (value.get('schema') != SCHEMA or value.get('target_date') != target_date
            or value.get('source_date') != target_date or value.get('method') != METHOD
            or value.get('data_source') != SOURCE or value.get('artifact_hash') !=
            _hash({k: v for k, v in value.items() if k != 'artifact_hash'})):
        raise ValueError('创新高冻结事实口径、日期或指纹不符')
    if _stamp(value['retrieved_at'], target_date) != value.get('query_date'):
        raise ValueError('创新高整理时间不符')
    days = value.get('trade_dates', [])
    window = value.get('window_days')
    if (type(window) is not int or not 1 <= window <= 25 or len(days) != window
            or days != sorted(set(days)) or days[-1] != target_date
            or days != [r.get('date') for r in value.get('items', [])]):
        raise ValueError('创新高交易日与序列不符')
    calendar = value.get('calendar', {})
    start = date.fromisoformat(target_date) - timedelta(days=70)
    expected = [(start + timedelta(days=i)).isoformat() for i in range(71)]
    rows = calendar.get('rows', [])
    if (calendar.get('start_date') != start.isoformat() or calendar.get('end_date') != target_date
            or [r.get('date') for r in rows] != expected
            or any(type(r.get('is_open')) is not int or r['is_open'] not in (0, 1) for r in rows)
            or [r['date'] for r in rows if r['is_open']][-window:] != days
            or _stamp(calendar['retrieved_at'], target_date) != value['query_date']):
        raise ValueError('创新高开放交易日历凭据不完整或与序列不同')
    for row in value['items']:
        day = _date(row['date'])
        if (day != row.get('source_date') or row.get('data_source') != SOURCE
                or _stamp(row['retrieved_at'], day) != row.get('query_date')
                or row['retrieved_at'] > value['retrieved_at']):
            raise ValueError('创新高逐日来源或查询日期不符')
        if row.get('missing_reason'):
            if row.get('new_high_count') is not None or row.get('new_high_share_pct') is not None:
                raise ValueError('创新高缺失不能同时提供数值')
            continue
        fields = ('new_high_count', 'all_a_denominator', 'eligible_count')
        if any(type(row.get(k)) is not int or row[k] < 0 for k in fields):
            raise ValueError('创新高样本数量无效')
        count, denominator, eligible = (row[k] for k in fields)
        excluded = row.get('excluded_counts', {})
        codes = row.get('new_high_codes', [])
        share = _number(row.get('new_high_share_pct'))
        if (denominator <= 0 or not count <= eligible <= denominator or share is None
                or abs(share - count / denominator * 100) > 1e-8
                or set(excluded) != {'st', 'recent_listing'}
                or any(type(n) is not int or n < 0 for n in excluded.values())
                or eligible + sum(excluded.values()) != denominator
                or len(codes) != count or len(set(codes)) != count
                or not re.fullmatch(r'[0-9a-f]{64}', row.get('source_sha256', ''))):
            raise ValueError('创新高数量、分母或占比矛盾')
    return value
