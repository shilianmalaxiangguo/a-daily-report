"""Exact-code, explicitly dated concept index prices from configured iWenCai."""
from copy import deepcopy
from datetime import datetime
import hashlib
import json
import os
import re
import secrets
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


SOURCE = 'iwencai.concept_index'
ENDPOINT = 'https://openapi.iwencai.com/v1/query2data'


def _hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     allow_nan=False, separators=(',', ':')).encode()).hexdigest()


def build_concept_prices(pages, target_date, *, retrieved_at):
    from report.sector_fact_loader import _number, _target_date
    target = _target_date(target_date)
    stamp = datetime.fromisoformat(retrieved_at)
    if stamp.tzinfo is None or not target <= stamp.astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat():
        raise ValueError('问财概念价格查询时间不符')
    if stamp > datetime.now(ZoneInfo('Asia/Shanghai')):
        raise ValueError('问财概念价格查询时间晚于当前时间')
    query_date = stamp.astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat()
    compact = target.replace('-', '')
    close_key, pct_key = f'收盘价[{compact}]', f'涨跌幅[{compact}]'
    rows, retained, expected = {}, [], None
    for page in pages:
        if page.get('status_code') != 0 or not isinstance(page.get('datas'), list):
            raise ValueError('问财概念价格响应未成功')
        total = page.get('code_count')
        if isinstance(total, bool) or not isinstance(total, int) or total < 0:
            raise ValueError('问财概念价格样本总数缺失')
        if expected is not None and total != expected:
            raise ValueError('问财概念价格分页样本范围变化')
        expected = total
        if page.get('row_count') != len(page['datas']):
            raise ValueError('问财概念价格分页记录不完整')
        retained.append({key: deepcopy(page[key]) for key in ('status_code', 'code_count', 'row_count', 'datas')})
        for raw in page['datas']:
            code = raw.get('指数代码')
            if (not isinstance(code, str) or not re.fullmatch(r'\d{6}\.TI', code)
                    or raw.get('指数类型') != '同花顺概念指数' or raw.get('成分领域') != 'A股指数'):
                raise ValueError('问财返回对象不是同花顺A股概念指数')
            close, change = _number(raw.get(close_key)), _number(raw.get(pct_key))
            if close is None or close <= 0 or change is None or change <= -100:
                raise ValueError('问财概念价格缺少目标日期有效点位或涨跌幅')
            if code in rows:
                raise ValueError('问财概念价格存在重复代码')
            rows[code] = {'ts_code': code, 'name': raw.get('指数简称') or code,
                          'trade_date': target, 'source_date': target,
                          'close': close, 'pct_change': change, 'data_source': SOURCE,
                          'query_date': query_date,
                          'retrieved_at': retrieved_at}
    if expected is None or expected <= 0 or len(rows) != expected:
        raise ValueError('问财概念价格分页覆盖不完整')
    value = {'source': SOURCE, 'target_date': target, 'query_date': query_date,
             'retrieved_at': retrieved_at, 'endpoint': ENDPOINT,
             'date_fields': [close_key, pct_key], 'raw_pages': retained,
             'rows': [rows[code] for code in sorted(rows)], 'sample_count': len(rows)}
    value['artifact_hash'] = _hash(value)
    return value


def validate_concept_prices(value, target_date):
    rebuilt = build_concept_prices(value['raw_pages'], target_date, retrieved_at=value['retrieved_at'])
    if rebuilt != value:
        raise ValueError('问财概念价格与原始响应不符')
    return rebuilt


def fetch_concept_prices(target_date, *, request=None):
    from report.sector_fact_loader import _target_date
    target = _target_date(target_date)
    token = os.environ.get('IWENCAI_API_KEY', '').strip()
    if not token:
        raise ValueError('未配置同花顺问财凭证')
    year, month, day = target.split('-')
    query = (f'{year}年{month}月{day}日所有同花顺概念指数，显示同花顺概念指数代码、概念名称、'
             f'{year}年{month}月{day}日收盘点位和涨跌幅，不要成分股和领涨股')
    pages = []
    for number in range(1, 21):
        body = {'query': query, 'page': str(number), 'limit': '500', 'is_cache': '1', 'expand_index': 'true'}
        headers = {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json',
                   'X-Claw-Call-Type': 'normal', 'X-Claw-Skill-Id': 'hithink-industry-query',
                   'X-Claw-Skill-Version': '1.0.0', 'X-Claw-Plugin-Id': 'none',
                   'X-Claw-Plugin-Version': 'none', 'X-Claw-Trace-Id': secrets.token_hex(32)}
        if request:
            page = request(body, headers)
        else:
            req = Request(ENDPOINT, json.dumps(body).encode(), headers=headers, method='POST')
            with urlopen(req, timeout=20) as response:
                page = json.load(response)
        pages.append(page)
        count = sum(len(p.get('datas') or []) for p in pages)
        if page.get('status_code') != 0 or not page.get('datas') or count >= (page.get('code_count') or 0):
            break
    return build_concept_prices(pages, target, retrieved_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat())


def merge_price_rows(rows, supplement, target_date):
    """Append only missing exact-code days; never overwrite native prices."""
    from report.sector_fact_loader import _number, _row_date
    value = validate_concept_prices(supplement, target_date)
    result = deepcopy(rows)
    existing = {r['ts_code']: r for r in rows if _row_date(r) == target_date}
    for row in value['rows']:
        previous = existing.get(row['ts_code'])
        if previous is None:
            result.append(deepcopy(row))
        elif (_number(previous.get('close')), _number(previous.get('pct_change'))) != (row['close'], row['pct_change']):
            raise ValueError('同代码同日的原价格与问财价格不一致，保留原始事实等待核对')
    return result
