"""Reproducible, same-universe concentration over actual open sessions."""
from copy import deepcopy
from datetime import date, datetime, timedelta
import json
import hashlib
import os
from pathlib import Path
import re
import tempfile
from zoneinfo import ZoneInfo

from report.sector_fact_loader import _date, _number, _target_date

SCHEMA = 'sector_top50.v1'
METHOD = ('沪深有成交A股按当日成交额取前50，除以同批沪深A股成交额；不含北交所、基金及B股。'
          '有成交代码须与同日daily_basic逐一相符；这是同一服务两个接口的交叉核对，不是独立数据商认证。')


def _stamp(value, day):
    now = datetime.now(ZoneInfo('Asia/Shanghai'))
    stamp = datetime.fromisoformat(value)
    if stamp.tzinfo is None or stamp > now or stamp.astimezone(now.tzinfo).date().isoformat() < day:
        raise ValueError('成交占比取得时间与事实日不符')
    return stamp.astimezone(now.tzinfo).date().isoformat()


def _sessions(calendar, target):
    rows = calendar['rows']
    days = [_date(r.get('date') or r.get('cal_date')) for r in rows]
    flags = [_number(r.get('is_open')) for r in rows]
    if (not days or any(not d or d > target for d in days) or len(set(days)) != len(days)
            or any(v not in (0, 1) for v in flags)):
        raise ValueError('成交占比交易日历日期或开市标记不符')
    indexed = dict(zip(days, flags))
    start, end = date.fromisoformat(min(days)), date.fromisoformat(target)
    complete = [(start + timedelta(days=i)).isoformat() for i in range((end-start).days+1)]
    if sorted(days) != complete:
        raise ValueError('成交占比交易日历缺日，不能用最近快照代替交易日')
    opened = [d for d in complete if indexed[d]]
    if len(opened) < 25 or opened[-1] != target:
        raise ValueError('成交占比不足25个开放交易日或缺少目标日')
    _stamp(calendar['retrieved_at'], target)
    return opened[-25:]


def build_top50_series(target_date, calendar, daily_pages, chinext_page, *, retrieved_at, failures=None):
    from math import fsum
    from report.sector_reading_history import evidence_hash
    target = _target_date(target_date)
    query = _stamp(retrieved_at, target)
    days = _sessions(calendar, target)
    index, items = {}, []
    if chinext_page:
        if chinext_page.get('source') != 'tushare.index_daily':
            raise ValueError('创业板来源不符')
        _stamp(chinext_page['retrieved_at'], target)
        for row in chinext_page['rows']:
            day, close = _date(row.get('trade_date') or row.get('date')), _number(row.get('close'))
            if (not day or day > target or row.get('ts_code') != '399006.SZ' or close is None or close <= 0
                    or any(_date(row[k]) != day for k in ('date', 'trade_date', 'source_date') if row.get(k))):
                raise ValueError('创业板指数代码、日期或收盘值不符')
            if day in index and index[day] != close:
                raise ValueError('创业板同日收盘值冲突')
            index[day] = close
    for day in days:
        row = {'date': day, 'source_date': day, 'top50_scope': 'hs_a',
               'total_turnover': None, 'top50_turnover': None, 'top50_market_amount_yi': None,
               'top50_share_pct': None, 'sample_count': None, 'chinext_close': index.get(day),
               'top50_sample_label': METHOD, 'missing_reason': ''}
        if day in index:
            row['chinext_provenance'] = {k: chinext_page[k] for k in
                ('source', 'retrieved_at', 'provider_host', 'configured_provider_hosts', 'raw_source_sha256') if k in chinext_page}
            row['chinext_provenance'].update(source_date=day,
                query_date=_stamp(chinext_page['retrieved_at'], day))
        page = daily_pages.get(day)
        if page is None:
            row['missing_reason'] = (failures or {}).get(day) or '该交易日完整个股成交额未取得'
            items.append(row)
            continue
        if (page.get('source') != 'tushare.daily' or page.get('amount_unit') != '千元'
                or _date(page.get('trade_date')) != day
                or page.get('source_date') and _date(page['source_date']) != day):
            raise ValueError('成交占比原始来源、单位或日期不符')
        amounts, seen = {}, set()
        for raw in page['rows']:
            code = raw.get('ts_code', '')
            amount = _number(raw.get('amount'))
            if (not re.fullmatch(r'\d{6}\.(SH|SZ|BJ)', code) or code in seen
                    or _date(raw.get('trade_date')) != day or amount is None or amount < 0
                    or any(_date(raw[k]) != day for k in ('date', 'source_date') if raw.get(k))):
                raise ValueError('成交占比原始明细日期、代码、金额或唯一性不符')
            seen.add(code)
            if re.fullmatch(r'(6\d{5}\.SH|[03]\d{5}\.SZ)', code) and amount > 0:
                amounts[code] = amount / 100000
        if len(amounts) < 50:
            raise ValueError('成交占比有效沪深A股不足50只，不能证明完整样本')
        coverage = page.get('coverage') or {}
        if (coverage.get('source') != 'tushare.daily_basic'
                or _date(coverage.get('trade_date')) != day or _date(coverage.get('source_date')) != day):
            raise ValueError('成交占比缺少同日股票范围交叉核对，不能使用部分样本作分母')
        coverage_query = _stamp(coverage['retrieved_at'], day)
        codes, coverage_seen = set(), set()
        for raw in coverage['rows']:
            code = raw.get('ts_code', '')
            if (not re.fullmatch(r'\d{6}\.(SH|SZ|BJ)', code) or code in coverage_seen
                    or _date(raw.get('trade_date')) != day
                    or any(_date(raw[k]) != day for k in ('date', 'source_date') if raw.get(k))):
                raise ValueError('成交占比范围核对的日期、代码或唯一性不符')
            coverage_seen.add(code)
            if re.fullmatch(r'(6\d{5}\.SH|[03]\d{5}\.SZ)', code):
                codes.add(code)
        if codes != set(amounts):
            raise ValueError('成交占比两个接口的同日有成交股票范围不同，保留缺失而不计算占比')
        ranked = sorted(amounts, key=lambda c: (-amounts[c], c))
        denominator, numerator = fsum(amounts.values()), fsum(amounts[c] for c in ranked[:50])
        row.update(total_turnover=denominator, top50_market_amount_yi=denominator,
                   top50_turnover=numerator, top50_share_pct=numerator/denominator*100,
                   sample_count=len(amounts), coverage_count=len(codes), top50_codes=ranked[:50])
        row['coverage_provenance'] = {k: coverage[k] for k in ('source', 'retrieved_at', 'provider_host',
            'configured_provider_hosts', 'raw_source_sha256', 'source_ref') if coverage.get(k)}
        row['coverage_provenance'].update(source_date=day, query_date=coverage_query)
        provenance = {k: page[k] for k in ('source', 'retrieved_at', 'provider_host', 'source_ref',
                                           'configured_provider_hosts', 'raw_source_sha256') if page.get(k)}
        if page.get('retrieved_at'):
            provenance['query_date'] = _stamp(page['retrieved_at'], day)
        else:
            provenance['provenance_note'] = '原始取得时间未记录，不由文件时间补造'
        provenance['source_date'] = day
        row['share_provenance'] = provenance
        items.append(row)
    inputs = {'calendar': deepcopy(calendar), 'daily_pages': {d: deepcopy(daily_pages[d]) for d in days if d in daily_pages},
              'chinext_page': deepcopy(chinext_page)}
    if failures:
        inputs['failures'] = deepcopy(failures)
    value = {'schema': SCHEMA, 'target_date': target, 'source_date': target, 'query_date': query,
             'retrieved_at': retrieved_at, 'data_source': 'tushare.daily + daily_basic + index_daily + trade_cal',
             'method': METHOD, 'trade_dates': days, 'items': items, 'inputs': inputs}
    value['artifact_hash'] = evidence_hash(value)
    return value


def validate_top50_series(value, target_date):
    from report.sector_reading_history import evidence_hash
    if (value.get('schema') != SCHEMA or value.get('target_date') != target_date
            or value.get('artifact_hash') != evidence_hash({k: v for k, v in value.items() if k != 'artifact_hash'})):
        raise ValueError('成交占比修订日期或指纹不符')
    rebuilt = build_top50_series(target_date, **value['inputs'], retrieved_at=value['retrieved_at'])
    if rebuilt != value:
        raise ValueError('成交占比修订数值与原始输入不同')
    return value


def collect_top50_series(pro, target_date, *, cache_root=None, provider_hosts=()):
    """Fresh/explicit repair only; replay uses validate_top50_series offline."""
    from report.sector_new_high import _calendar, _pages
    target = _target_date(target_date)
    days, calendar = _calendar(pro, target, 25)
    root = Path(cache_root) if cache_root is not None else Path(__file__).resolve().parents[2] / '.generated/top50-facts-v1'
    root.mkdir(parents=True, exist_ok=True)
    pages, failures = {}, {}
    for day in days:
        path = root / (day + '.json')
        page = None
        if path.is_file():
            original = path.read_bytes()
            try:
                page = json.loads(original)
                build_top50_series(target, calendar, {day: page}, None,
                    retrieved_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat())
            except (ValueError, TypeError, KeyError, AttributeError):
                backup = root / (day + '.invalid-' + hashlib.sha256(original).hexdigest() + '.json')
                if not backup.exists():
                    backup.write_bytes(original)
                page = None
        try:
            if page is None:
                rows = _pages(pro, 'daily', trade_date=day.replace('-', ''), fields='ts_code,trade_date,amount')
                page = {'source': 'tushare.daily', 'trade_date': day, 'source_date': day,
                        'amount_unit': '千元', 'rows': rows, 'configured_provider_hosts': list(provider_hosts),
                        'retrieved_at': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()}
                coverage_rows = _pages(pro, 'daily_basic', trade_date=day.replace('-', ''),
                                       fields='ts_code,trade_date,turnover_rate')
                page['coverage'] = {'source': 'tushare.daily_basic', 'trade_date': day, 'source_date': day,
                    'rows': coverage_rows, 'configured_provider_hosts': list(provider_hosts),
                    'retrieved_at': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()}
                # Validate the day before caching, without replacing a previous source.
                build_top50_series(target, calendar, {day: page}, None,
                                   retrieved_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat())
                with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=root, delete=False) as stream:
                    json.dump(page, stream, ensure_ascii=False, allow_nan=False)
                    temporary = Path(stream.name)
                try:
                    os.replace(temporary, path)
                finally:
                    temporary.unlink(missing_ok=True)
            pages[day] = page
        except Exception:
            failures[day] = '该日成交额或股票范围来源未通过核对；保留缺失'
    try:
        rows = _pages(pro, 'index_daily', ts_code='399006.SZ', start_date=days[0].replace('-', ''),
                      end_date=target.replace('-', ''), fields='ts_code,trade_date,close')
        chinext = {'source': 'tushare.index_daily', 'rows': rows,
                   'configured_provider_hosts': list(provider_hosts),
                   'retrieved_at': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()}
    except Exception:
        chinext = None
        failures['chinext'] = '创业板来源未取得；保留缺失'
    return build_top50_series(target, calendar, pages, chinext,
                              retrieved_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(), failures=failures)
