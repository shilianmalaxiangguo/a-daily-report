"""Dated concept net amounts, kept separate from prices and sector transfers."""
from copy import deepcopy
from datetime import datetime
import json
import math
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from report.sector_fact_loader import (
    _date, _normalize_nonfinite, _number, _target_date, is_reading_concept,
)

SOURCE = 'tushare.moneyflow_cnt_ths'
SCHEMA = 'concept_daily_net.v1'


def _stamp(value, day):
    try:
        stamp = datetime.fromisoformat(value)
    except (TypeError, ValueError) as error:
        raise ValueError('概念净额缺少有效取得时间') from error
    now = datetime.now(ZoneInfo('Asia/Shanghai'))
    if stamp.tzinfo is None or not day <= stamp.astimezone(now.tzinfo).date().isoformat() or stamp > now:
        raise ValueError('概念净额查询时间不符')
    return stamp.astimezone(now.tzinfo).date().isoformat()


def build_concept_flow(target_date, trade_dates, metadata, pages, *, retrieved_at,
                       directory_provenance=None):
    from report.sector_reading_history import evidence_hash
    target = _target_date(target_date)
    query = _stamp(retrieved_at, target)
    if directory_provenance:
        directory_query = _stamp(directory_provenance.get('retrieved_at'), target)
        if directory_provenance.get('query_date') != directory_query:
            raise ValueError('概念目录查询日与取得时间不符')
    days = [_date(day) for day in trade_dates]
    if not days or days != sorted(set(days)) or not all(days) or days[-1] != target:
        raise ValueError('概念净额交易日历不符')
    days = days[-7:]
    metadata = _normalize_nonfinite(metadata or {})
    directory = {code: deepcopy(meta) for code, meta in sorted(metadata.items())
                 if is_reading_concept(meta)}
    if any(not re.fullmatch(r'\d{6}\.TI', code) or not meta.get('name') for code, meta in directory.items()):
        raise ValueError('概念目录名称或代码不符')
    observed, normalized, seen_pages = {}, [], set()
    coverage = {}
    for page in pages:
        day = _date(page.get('trade_date'))
        if day not in days:
            raise ValueError('概念净额来源日期不符')
        page_query = _stamp(page.get('retrieved_at'), day)
        if page.get('query_date', page_query) != page_query:
            raise ValueError('概念净额查询日与取得时间不符')
        if datetime.fromisoformat(page['retrieved_at']) > datetime.fromisoformat(retrieved_at):
            raise ValueError('概念净额原始取得时间晚于整理时间')
        if (_date(page.get('source_date', day)) != day
                or page.get('source', SOURCE) != SOURCE or page.get('unit', '亿元') != '亿元'
                or ('trade_date' in (page.get('params') or {})
                    and _date(page['params']['trade_date']) != day)):
            raise ValueError('概念净额来源日期、单位或请求不符')
        # Multiple pages for a date are valid, but a repeated page is not a new sample.
        key = evidence_hash(page)
        if key in seen_pages:
            continue
        seen_pages.add(key)
        normalized.append({**deepcopy(page), 'query_date': page_query, 'source_date': day,
                           'source': SOURCE, 'unit': '亿元'})
        counts = coverage.setdefault(day, {'raw_count': 0, 'unmatched_codes': set(), 'error': ''})
        counts['error'] = page.get('missing_reason') or counts['error']
        for raw in page.get('rows') or []:
            if (_date(raw.get('trade_date')) != day or _date(raw.get('source_date', day)) != day
                    or raw.get('query_date', page_query) != page_query):
                raise ValueError('概念净额原始行日期不符')
            if raw.get('retrieved_at'):
                _stamp(raw['retrieved_at'], day)
                if datetime.fromisoformat(raw['retrieved_at']) > datetime.fromisoformat(page['retrieved_at']):
                    raise ValueError('概念净额原始行取得时间不符')
            code = str(raw.get('ts_code') or '').strip().upper()
            if not re.fullmatch(r'\d{6}\.TI', code):
                raise ValueError('概念净额原始代码不符')
            counts['raw_count'] += 1
            signature = (_number(raw.get('net_amount')), _number(raw.get('net_buy_amount')),
                         _number(raw.get('net_sell_amount')), str(raw.get('name') or raw.get('industry') or ''))
            identity = (day, code)
            if identity in observed and observed[identity] != signature:
                raise ValueError('同日同概念净额存在冲突')
            observed[identity] = signature
            if code not in directory:
                counts['unmatched_codes'].add(code)
    rows = []
    for code, meta in directory.items():
        values = [observed.get((day, code), (None,))[0] for day in days]
        rows.append({'track_id': 'index:' + code, 'identity': f'tushare.ths_index:N:{code}',
                     'code': code, 'index_type': 'N', 'name': meta['name'], 'values': values,
                     'missing_reasons': ['' if v is not None else
                         (coverage.get(day, {}).get('error') or '该日该概念没有有效净额记录')
                         for day, v in zip(days, values)]})
    daily_coverage = []
    for i, day in enumerate(days):
        counts = coverage.get(day, {})
        daily_coverage.append({'date': day, 'directory_count': len(directory),
            'matched_count': sum(r['values'][i] is not None for r in rows),
            'raw_count': counts.get('raw_count', 0), 'unmatched_codes': sorted(counts.get('unmatched_codes', []))})
    value = {'schema_version': SCHEMA, 'target_date': target, 'source': SOURCE,
             'unit': '亿元', 'query_date': query, 'retrieved_at': retrieved_at,
             'dates': days, 'directory': directory, 'directory_basis': 'latest_at_query',
             'raw_pages': sorted(normalized, key=lambda p: (p['trade_date'], evidence_hash(p))),
             'rows': rows, 'coverage': daily_coverage,
             'raw_derived': 'raw_pages为来源原始记录；rows为按目录代码和交易日对齐的派生视图',
             'interpretation': '来源定义的概念净额；概念成分重叠，不能相加为市场独立资金，也不能识别板块间转移。'}
    if directory_provenance:
        value['directory_provenance'] = deepcopy(directory_provenance)
    value['artifact_hash'] = evidence_hash(value)
    return value


def validate_concept_flow(value, target_date):
    from report.sector_reading_history import evidence_hash
    if not isinstance(value, dict) or value.get('schema_version') != SCHEMA:
        raise ValueError('概念净额事实格式不符')
    if value.get('artifact_hash') != evidence_hash({k: v for k, v in value.items() if k != 'artifact_hash'}):
        raise ValueError('概念净额事实指纹不符')
    rebuilt = build_concept_flow(target_date, value['dates'], value['directory'], value['raw_pages'],
                                 retrieved_at=value['retrieved_at'],
                                 directory_provenance=value.get('directory_provenance'))
    if value != rebuilt:
        raise ValueError('概念净额图与原始行不符')
    return deepcopy(value)


def collect_concept_flow(pro, target_date, trade_dates, metadata, *, calendar_verified,
                         directory_provenance=None, provider_hosts=()):
    if not calendar_verified:
        raise ValueError('概念净额缺少已核对的交易日历')
    pages = []
    for day in trade_dates[-7:]:
        offset = 0
        while True:
            params = {'trade_date': day.replace('-', ''), 'limit': 5000, 'offset': offset}
            try:
                frame = pro.moneyflow_cnt_ths(**params)
                raw = frame.to_dict('records')
                def clean(v):
                    if isinstance(v, dict): return {k: clean(x) for k, x in v.items()}
                    if isinstance(v, list): return [clean(x) for x in v]
                    return None if isinstance(v, float) and not math.isfinite(v) else v
                rows = clean(raw)
            except Exception as error:
                stamp = datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
                pages.append({'trade_date': day, 'retrieved_at': stamp, 'params': params, 'rows': [],
                              'missing_reason': f'该日查询未取得完整记录（{type(error).__name__}）'})
                break
            stamp = datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
            pages.append({'trade_date': day, 'retrieved_at': stamp, 'params': params, 'rows': rows,
                          'configured_provider_hosts': list(provider_hosts)})
            if len(rows) < 5000:
                break
            offset += len(rows)
            if offset > 25000:
                raise ValueError('概念净额分页未结束')
    return build_concept_flow(target_date, trade_dates, metadata, pages,
                              retrieved_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
                              directory_provenance=directory_provenance)


def concept_flow_view(value, target_date, *, track_ids=None):
    value = validate_concept_flow(value, target_date)
    selected = set(track_ids) if track_ids is not None else {r['track_id'] for r in value['rows']}
    return {key: value[key] for key in ('target_date', 'source', 'unit', 'query_date', 'retrieved_at',
                                      'dates', 'interpretation')} | {
        'rows': [row for row in value['rows'] if row['track_id'] in selected]}


def render_concept_flow(soup, value, target_date, *, track_ids=None):
    from report.sector_reading_primitives import _text
    value = concept_flow_view(value, target_date, track_ids=track_ids)
    section = soup.new_tag('div', attrs={'class': 'concept-flow'})
    section.append(_text(soup, 'h3', '概念逐日净额'))
    section.append(_text(soup, 'p', '每格是该概念在当日的来源净额（亿元），红正绿负，零与缺失分开。'
                        '概念成分可能重叠，不相加为市场总资金，不推断从哪个板块流向哪个板块。'))
    section.append(_text(soup, 'small', '仅载入本页价格比较所需概念；完整目录、查询原始记录与未选样本留在冻结来源。'))
    controls = soup.new_tag('div', attrs={'class': 'trend-controls'})
    controls.append(_text(soup, 'span', '查看概念'))
    controls.append(soup.new_tag('div', attrs={'id': 'concept-flow-buttons', 'class': 'reading-tags',
                                             'role': 'group', 'aria-label': '概念净额比较对象'}))
    select = soup.new_tag('select', attrs={'id': 'concept-flow-selector', 'hidden': ''})
    select.append(_text(soup, 'option', '近期价格比较样本'))
    select.option['value'] = ''
    for row in value['rows']:
        option = _text(soup, 'option', row['name'] + ' · ' + row['code'])
        option['value'] = row['track_id']
        select.append(option)
    controls.append(select)
    section.append(controls)
    frame = soup.new_tag('div', attrs={'class': 'trend-heat-scroll'})
    frame.append(soup.new_tag('div', attrs={'id': 'concept-flow-matrix', 'role': 'img',
                                          'aria-label': '概念逐交易日净额矩阵'}))
    section.append(frame)
    section.append(_text(soup, 'p', '选中格子联动相同代码的价格路径与日期；未匹配概念保持缺失。'))
    detail = soup.new_tag('p', attrs={'id': 'concept-flow-detail', 'aria-live': 'polite'})
    detail.string = '点选格子，对照当日净额与同板块价格。'
    section.append(detail)
    node = soup.new_tag('script', attrs={'type': 'application/json', 'id': 'concept-flow-data'})
    node.string = json.dumps(value, ensure_ascii=False, allow_nan=False).replace('<', '\\u003c')
    section.append(node)
    script = soup.new_tag('script')
    script.string = (Path(__file__).resolve().parents[1] / 'templates/sector_concept_flow.js').read_text()
    section.append(script)
    return section
