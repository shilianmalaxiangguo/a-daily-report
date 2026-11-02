"""Acquire dated facts for retained observations, independently of rankings."""
from __future__ import annotations

import json
import math
import os
import re
import tempfile
from copy import deepcopy
from datetime import date, datetime
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from zoneinfo import ZoneInfo
from urllib.parse import urlsplit

from report.hypothesis_revision import (
    _canonical_date, _hash, _next_event, validate_hypothesis_record,
)

SCHEMA = 'tracked_sector_facts.v1'
MEMBER_HISTORY_SOURCE = 'quicktiny.merged_kline'


def _number(value):
    if isinstance(value, bool):
        raise ValueError('数值无效')
    number = float(value)
    if not math.isfinite(number):
        raise ValueError('数值无效')
    return number


def _dated_rows(rows, target_date):
    result = {}
    for raw in rows:
        value = str(raw.get('trade_date', '')).replace('-', '')
        if value != target_date.replace('-', ''):
            raise ValueError('查询返回了其他日期的事实')
        code = str(raw.get('ts_code', '')).strip().upper()
        if not code or code in result:
            raise ValueError('事实代码缺失或重复')
        result[code] = deepcopy(raw)
    return result


def _aggregate(seed, rows, target_date, members):
    indexed = _dated_rows(rows, target_date)
    missing = sorted(set(members) - indexed.keys())
    if missing:
        raise ValueError(f'缺{len(missing)}/{len(members)}只成员的目标日行情（含停牌须单独核实）')
    weighted = amount = 0.0
    up = 0
    for code in members:
        raw = indexed[code]
        change = _number(raw['pct_chg'])
        turnover = _number(raw['amount']) / 100000
        if turnover <= 0:
            raise ValueError('成员成交额无效，不能补零')
        # Match the original normalized daily aggregation's six-decimal amount.
        turnover = round(turnover, 6)
        amount += turnover
        weighted += change * turnover
        up += change > 0
    if not members:
        raise ValueError('缺完整成员清单')
    providers = {indexed[code].get('data_source', 'tushare.daily') for code in members}
    if len(providers) != 1 or not providers <= {'tushare.daily', MEMBER_HISTORY_SOURCE}:
        raise ValueError('成员行情来源混杂，不能混算')
    source = (MEMBER_HISTORY_SOURCE + '.fixed_industry_aggregate'
              if MEMBER_HISTORY_SOURCE in providers else seed['data_source'])
    return {'name': seed['name'], 'code': '', 'trade_date': target_date,
            'change_pct': round(weighted / amount, 6), 'up_count': up,
            'stock_count': len(members), 'turnover_yi': round(amount, 6),
            'data_source': source}


def _membership_matches(seed, reference):
    return (reference['stock_count'] == seed.get('stock_count')
            and reference['up_count'] == seed.get('up_count')
            and abs(reference['change_pct'] - seed['change_pct']) <= .00001
            and seed.get('turnover_yi') is not None
            and abs(reference['turnover_yi'] - seed['turnover_yi']) <= .0001)


def fetch_history(api, target_date):
    """Exact-date historical queries only; no undated quote fallback."""
    from market_data.tushare_client import create_tushare_pro_api
    pro = create_tushare_pro_api(timeout_seconds=15)
    fields = ('ts_code,trade_date,pct_chg,amount' if api == 'daily'
              else 'ts_code,trade_date,pct_change')
    rows, offset = [], 0
    while True:
        page = getattr(pro, api)(trade_date=target_date.replace('-', ''),
                                fields=fields, limit=6000, offset=offset).to_dict('records')
        rows.extend(page)
        if len(page) < 6000:
            return rows
        offset += 6000
        if offset > 24000:
            raise ValueError('历史查询分页未结束')


def _member_history_url(code):
    if not isinstance(code, str) or not re.fullmatch(r'[0-9]{6}\.(SH|SZ|BJ)', code):
        raise ValueError('成员股票代码无效')
    return f'https://stock.quicktiny.cn/api/tushare/merged-kline/{code[-2:].lower()}{code[:6]}'


def _check_member_metadata(code, metadata):
    identities = {code.lower(), code[:6], code[-2:].lower() + code[:6]}
    for key in ('symbol', 'code', 'ts_code'):
        if key in metadata and str(metadata[key]).lower() not in identities:
            raise ValueError('成员历史响应股票身份不符')
    for key in ('source', 'data_source'):
        if key in metadata and metadata[key] not in ('daily', 'stock_daily', 'tushare.daily', MEMBER_HISTORY_SOURCE):
            raise ValueError('成员历史响应不是股票日线来源')
    if 'amount_unit' in metadata and metadata['amount_unit'] not in ('yuan', 'CNY', 'RMB', '元'):
        raise ValueError('成员历史成交额单位不符')


def normalize_member_history(code, response, *, target_date, reference_date, retrieved_at,
                             request_url, response_url):
    """Keep dated source rows; QuickTiny amount is yuan, Tushare amount is k-yuan."""
    expected_url = _member_history_url(code)
    returned = urlsplit(response_url)
    if (request_url != expected_url
            or (returned.scheme, returned.netloc, returned.path) != (
                'https', 'stock.quicktiny.cn', urlsplit(expected_url).path)):
        raise ValueError('成员历史请求与返回地址不符')
    if response.get('success') is not True or not isinstance(response.get('data'), list):
        raise ValueError('成员历史行情查询失败')
    if not _canonical_date(target_date) or not _canonical_date(reference_date):
        raise ValueError('成员历史查询日期无效')
    _check_member_metadata(code, response)
    selected = {}
    for raw in response['data']:
        raw_day = raw.get('date', '')
        if not isinstance(raw_day, str) or not re.fullmatch(r'[0-9]{8}|[0-9]{4}-[0-9]{2}-[0-9]{2}', raw_day):
            raise ValueError('成员历史日期格式无效')
        day = date.fromisoformat(raw_day).strftime('%Y%m%d')
        if day not in (target_date.replace('-', ''), reference_date.replace('-', '')):
            continue
        if day in selected:
            raise ValueError('成员历史日期重复')
        _check_member_metadata(code, raw)
        if raw.get('adjust') != 'none':
            raise ValueError('历史复权口径不符')
        close, previous = _number(raw['close']), _number(raw['pre_close'])
        change, amount = _number(raw['pct_chg']), _number(raw['amount'])
        if min(close, previous, amount) <= 0 or abs((close / previous - 1) * 100 - change) > .00011:
            raise ValueError('历史涨跌幅或成交额校验失败')
        low, high, volume = _number(raw['low']), _number(raw['high']), _number(raw['vol'])
        # This endpoint reports volume in lots and amount in yuan. Check each
        # date's implied average price, not just the reference date's units.
        if (min(low, high, volume) <= 0 or low > high or not low <= close <= high
                or not low - .01 <= amount / (volume * 100) <= high + .01):
            raise ValueError('成员历史成交额与成交量价格不一致')
        selected[day] = deepcopy(raw)
    if len(selected) != len({target_date, reference_date}):
        raise ValueError('缺目标日或起点历史行情')
    raw = selected[target_date.replace('-', '')]
    return {'ts_code': code, 'trade_date': target_date, 'source_date': target_date,
            'query_date': datetime.fromisoformat(retrieved_at).date().isoformat(),
            'retrieved_at': retrieved_at, 'data_source': MEMBER_HISTORY_SOURCE,
            'pct_chg': _number(raw['pct_chg']), 'amount': _number(raw['amount']) / 1000,
            'source_row': raw, 'reference_row': selected[reference_date.replace('-', '')],
            'request_url': request_url, 'response_url': response_url,
            'response_metadata': deepcopy({key: value for key, value in response.items() if key != 'data'})}


def fetch_member_history(codes, target_date, reference_date):
    """Fallback to dated raw history for the fixed member universe only."""
    import requests
    now = datetime.now(ZoneInfo('Asia/Shanghai'))
    days = max(20, (now.date() - date.fromisoformat(reference_date)).days + 10)

    def fetch(code):
        request_url = _member_history_url(code)
        with requests.Session() as session:
            session.trust_env = False
            response = session.get(request_url,
                                   params={'days': days}, timeout=(5, 15))
            response.raise_for_status()
        return normalize_member_history(code, response.json(), target_date=target_date,
                                        reference_date=reference_date,
                                        retrieved_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
                                        request_url=request_url, response_url=response.url)
    with ThreadPoolExecutor(max_workers=4) as pool:
        return list(pool.map(fetch, codes))


def _validate_member_history(rows, membership, target_date):
    reference_date = membership['reference']['trade_date']
    originals = _dated_rows(membership['reference_rows'], reference_date)
    indexed = _dated_rows(rows, target_date)
    if set(indexed) != set(membership['codes']):
        raise ValueError('替代源成员覆盖不完整')
    for code, row in indexed.items():
        stamp = datetime.fromisoformat(row['retrieved_at'])
        if not stamp.tzinfo or stamp.date().isoformat() < target_date:
            raise ValueError('实际取数时间不符')
        normalized = normalize_member_history(code, {**row['response_metadata'], 'data': [row['reference_row'], row['source_row']]},
                                              target_date=target_date, reference_date=reference_date,
                                              retrieved_at=row['retrieved_at'],
                                              request_url=row['request_url'], response_url=row['response_url'])
        if row != normalized:
            raise ValueError('归一事实与原始行情不符')
        raw, original = row['reference_row'], originals[code]
        if (abs(_number(raw['pct_chg']) - _number(original['pct_chg'])) > .0001
                or abs(_number(raw['amount']) / 1000 - _number(original['amount'])) > .01
                or ('close' in original and abs(_number(raw['close']) - _number(original['close'])) > .00001)):
            raise ValueError('替代源起点行情与原始事实不一致')


def collect_tracked_facts(record, *, fetcher=fetch_history, membership=None,
                          prior_evidence=(), now=None, member_fetcher=None):
    """Keep acquisition time separate from market date and append to a sidecar.

    A membership reconstruction is usable only after matching the seed day's
    count, breadth, weighted return and turnover. It remains labelled as such.
    """
    if not validate_hypothesis_record(record):
        raise ValueError('原日期记录无效，停止补查')
    stamp = now or datetime.now(ZoneInfo('Asia/Shanghai'))
    if stamp.tzinfo is None or stamp.date().isoformat() < record['target_date']:
        raise ValueError('实际取数时间无效')
    cache, errors = {}, {}

    def get(api, day):
        key = (api, day)
        if key not in cache and key not in errors:
            try:
                rows = fetcher(api, day)
                _dated_rows(rows, day)
                _hash(rows)  # Reject non-finite or non-JSON source values.
                if not rows:
                    raise ValueError('目标日期没有返回行情')
                cache[key] = rows
            except Exception as error:
                # Provider exceptions can contain credentials and URLs.
                failure = type(error).__name__
                reason = ('历史行情连接超时' if 'Timeout' in failure else
                          '历史行情连接失败' if failure in ('SSLError', 'ConnectionError') else
                          '返回事实不完整或日期不符' if failure in ('ValueError', 'TypeError', 'KeyError') else
                          '历史行情查询失败')
                errors[key] = reason
        if key in errors:
            raise ValueError(errors[key])
        return cache[key]

    previous_members = {}
    for evidence in prior_evidence:
        for entry in evidence['entries']:
            if entry.get('membership'):
                previous_members[entry['track_id']] = entry['membership']
    entries = []
    for track in record['tracks']:
        seed = track['seed']
        # Freeze new industry memberships too, so retirement from a ranking
        # does not lose tomorrow's acquisition universe.
        if track['events'][-1]['kind'] != 'missing' and not (
                track['started_date'] == record['target_date']
                and seed['data_source'] == 'tushare.daily.industry_aggregate'):
            continue
        entry = {'track_id': track['track_id'], 'seed_hash': track['seed_hash'],
                 'name': seed['name'], 'fact': None, 'event': None,
                 'membership': None, 'raw_rows': [], 'issue': '', 'basis': ''}
        try:
            if seed['data_source'] == 'tushare.ths_daily':
                rows = get('ths_daily', record['target_date'])
                raw = _dated_rows(rows, record['target_date']).get(seed['code'])
                if raw is None:
                    raise ValueError('目标日缺同代码指数收盘事实')
                entry['raw_rows'] = [raw]
                entry['basis'] = '同代码指数历史查询'
                fact = {'name': seed['name'], 'code': seed['code'],
                        'trade_date': record['target_date'], 'data_source': seed['data_source'],
                        'change_pct': _number(raw['pct_change']), 'up_count': None,
                        'stock_count': None, 'turnover_yi': None}
            else:
                frozen = previous_members.get(track['track_id'])
                if frozen is None:
                    if not membership:
                        raise ValueError('原记录未冻结完整行业成员，须先核对起点成员清单')
                    codes = sorted(code for code, info in membership['mapping'].items()
                                   if '.' in code and info.get('industry') == seed['name'])
                    reference_rows = membership.get('daily_by_date', {}).get(seed['trade_date'])
                    if reference_rows is None:
                        reference_rows = get('daily', seed['trade_date'])
                    reference_by_code = _dated_rows(reference_rows, seed['trade_date'])
                    # The source industry ranking excludes zero-turnover rows.
                    # Apply that rule only when freezing the seed universe;
                    # later missing/suspended members must still be reported.
                    codes = [code for code in codes if code not in reference_by_code
                             or _number(reference_by_code[code]['amount']) > 0]
                    selected = [r for r in reference_rows if r.get('ts_code') in codes]
                    reference = _aggregate(seed, selected, seed['trade_date'], codes)
                    if not _membership_matches(seed, reference):
                        raise ValueError('成员清单复算与起点聚合不一致，不能沿用')
                    frozen = {'codes': codes, 'reference': reference, 'reference_rows': selected,
                              'source': membership['source'], 'source_hash': _hash(membership['mapping']),
                              'captured_at': stamp.isoformat(), 'reconstructed': seed['trade_date'] != stamp.date().isoformat()}
                entry['membership'] = deepcopy(frozen)
                entry['basis'] = ('成员经起点复算核对，历史重建' if frozen['reconstructed']
                                  else '沿用已冻结成员')
                if track['started_date'] == record['target_date']:
                    entry['membership_only'] = True
                    entry['issue'] = '起点成员已冻结，下一份收盘事实再核验'
                    entries.append(entry)
                    continue
                try:
                    rows = get('daily', record['target_date'])
                    entry['raw_rows'] = [r for r in rows if r.get('ts_code') in frozen['codes']]
                    fact = _aggregate(seed, entry['raw_rows'], record['target_date'], frozen['codes'])
                except ValueError:
                    if member_fetcher is None:
                        raise
                    try:
                        rows = member_fetcher(frozen['codes'], record['target_date'], seed['trade_date'])
                    except Exception as error:
                        raise ValueError('替代历史源查询失败，保留原缺口') from error
                    _validate_member_history(rows, frozen, record['target_date'])
                    entry['raw_rows'] = rows
                    entry['basis'] += '；QuickTiny逐股历史复算（元换算为千元，起点逐股交叉核对）'
                    fact = _aggregate(seed, rows, record['target_date'], frozen['codes'])
            entry['fact'] = fact
            entry['event'] = _next_event(track, fact, record['target_date'], record['market_change'])
        except (ValueError, KeyError, TypeError) as error:
            entry['issue'] = str(error)
        entries.append(entry)
    result = {'schema_version': SCHEMA, 'target_date': record['target_date'],
              'record_hash': record['artifact_hash'], 'retrieved_at': stamp.isoformat(),
              'entries': entries}
    # Carry only dated references, not rewritten old results. The loader has
    # already verified their original records and raw evidence independently.
    result['history'] = [
        {'target_date': old['target_date'], 'artifact_hash': old['artifact_hash'],
         'retrieved_at': old['retrieved_at'], 'entries': deepcopy(old['entries'])}
        for old in prior_evidence if old['target_date'] < record['target_date']
    ]
    result['artifact_hash'] = _hash(result)
    return result


def validate_tracked_facts(evidence, record):
    try:
        stamp = datetime.fromisoformat(evidence['retrieved_at'])
        if (evidence['schema_version'] != SCHEMA or not stamp.tzinfo
                or stamp.date().isoformat() < record['target_date']
                or evidence['target_date'] != record['target_date']
                or evidence['record_hash'] != record['artifact_hash']
                or evidence['artifact_hash'] != _hash({k: v for k, v in evidence.items() if k != 'artifact_hash'})):
            return False
        tracks = {t['track_id']: t for t in record['tracks']}
        for historic in evidence.get('history', []):
            if not _canonical_date(historic['target_date']) or historic['target_date'] >= record['target_date']:
                return False
            for entry in historic['entries']:
                track = tracks.get(entry['track_id'])
                if not track or entry['seed_hash'] != track['seed_hash']:
                    return False
                event = entry['event']
                if event and (event['date'] != historic['target_date'] or event != _next_event(
                        track, entry['fact'], historic['target_date'], event['market_change'])):
                    return False
        seen = set()
        for entry in evidence['entries']:
            track = tracks[entry['track_id']]
            if entry['track_id'] in seen or entry['seed_hash'] != track['seed_hash']:
                return False
            seen.add(entry['track_id'])
            seed, fact = track['seed'], entry['fact']
            membership = entry['membership']
            if membership:
                codes = membership['codes']
                if not codes or len(set(codes)) != len(codes):
                    return False
                reference = _aggregate(seed, membership['reference_rows'], seed['trade_date'], codes)
                if reference != membership['reference'] or not _membership_matches(seed, reference):
                    return False
            if fact is None:
                if entry['event'] is not None or not entry['issue']:
                    return False
                if entry.get('membership_only') and (membership is None or track['started_date'] != record['target_date']):
                    return False
                continue
            if entry['issue']:
                return False
            if seed['data_source'] == 'tushare.daily.industry_aggregate':
                if fact.get('data_source') == MEMBER_HISTORY_SOURCE + '.fixed_industry_aggregate':
                    _validate_member_history(entry['raw_rows'], membership, record['target_date'])
                expected = _aggregate(seed, entry['raw_rows'], record['target_date'], membership['codes'])
            else:
                raw = _dated_rows(entry['raw_rows'], record['target_date'])[seed['code']]
                expected = {'name': seed['name'], 'code': seed['code'], 'trade_date': record['target_date'],
                            'data_source': seed['data_source'], 'change_pct': _number(raw['pct_change']),
                            'up_count': None, 'stock_count': None, 'turnover_yi': None}
            if fact != expected or entry['event'] != _next_event(track, fact, record['target_date'], record['market_change']):
                return False
        return True
    except (KeyError, TypeError, ValueError, AttributeError):
        return False


def _directory(ledger_root, target_date):
    if not _canonical_date(target_date):
        raise ValueError('补查日期不符')
    return Path(ledger_root) / 'hypothesis-revision' / 'supplements' / target_date


def save_tracked_facts(evidence, record, *, ledger_root):
    if not validate_tracked_facts(evidence, record):
        raise ValueError('补查凭据校验失败，停止保存')
    directory = _directory(ledger_root, record['target_date'])
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (evidence['artifact_hash'] + '.json')
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=directory, delete=False) as stream:
        temporary = Path(stream.name)
        json.dump(evidence, stream, ensure_ascii=False, indent=2, allow_nan=False)
    try:
        try:
            os.link(temporary, path)
        except FileExistsError:
            if json.loads(path.read_text(encoding='utf-8')) != evidence:
                raise ValueError('补查凭据已存在不同内容，拒绝覆盖')
    finally:
        temporary.unlink(missing_ok=True)
    return path


def load_tracked_facts(record, *, ledger_root):
    results = []
    for path in _directory(ledger_root, record['target_date']).glob('*.json'):
        evidence = json.loads(path.read_text(encoding='utf-8'))
        if not validate_tracked_facts(evidence, record) or path.stem != evidence['artifact_hash']:
            raise ValueError('补查凭据日期或内容不符，停止生成')
        for historic in evidence.get('history', []):
            old_path = _directory(ledger_root, historic['target_date']) / (historic['artifact_hash'] + '.json')
            original = json.loads(old_path.read_text(encoding='utf-8'))
            if historic != {key: original[key] for key in ('target_date', 'artifact_hash', 'retrieved_at', 'entries')}:
                raise ValueError('前期补查结果不符，停止生成')
        results.append(evidence)
    results = sorted(results, key=lambda e: (datetime.fromisoformat(e['retrieved_at']), e['artifact_hash']))
    # A failed retry may coexist with a successful immutable bundle, but two
    # different successful facts for the same identity/date are contradictory.
    successful = {}
    for bundle in results:
        for entry in bundle['entries']:
            if entry.get('event') is None:
                continue
            previous = successful.get(entry['track_id'])
            if previous is not None and previous != entry['event']:
                raise ValueError('同一身份同一日期出现不同补查结果，停止生成')
            successful[entry['track_id']] = entry['event']
    return results


def latest_entries(evidence):
    result = {}
    for item in evidence:
        for entry in item['entries']:
            if entry.get('membership_only'):
                continue
            candidate = {**entry, 'retrieved_at': item['retrieved_at']}
            previous = result.get(entry['track_id'], {})
            if previous.get('event') and entry.get('event') and previous['event'] != entry['event']:
                raise ValueError('同一身份同一日期出现不同补查结果，停止生成')
            # Preserve a confirmed fact when a later retry only reports a
            # provider failure. This is append-only evidence, not a new null.
            if entry.get('event') is None and result.get(entry['track_id'], {}).get('event') is not None:
                continue
            result[entry['track_id']] = candidate
    return result


def observation_projection(track, evidence):
    """Read corrected observations without mutating the original first review."""
    projection = deepcopy(track)
    dated = {}
    for bundle in evidence:
        for old in [*bundle.get('history', []), bundle]:
            for entry in old['entries']:
                if entry['track_id'] == track['track_id'] and entry['event']:
                    if old['target_date'] in dated and dated[old['target_date']]['event'] != entry['event']:
                        raise ValueError('前期补查事实相互冲突，停止生成')
                    dated[old['target_date']] = entry
    corrected_dates = []
    for index, event in enumerate(projection['events']):
        entry = dated.get(event['date'])
        if index > 0 and event['kind'] == 'missing' and entry:
            projection['events'][index] = deepcopy(entry['event'])
            corrected_dates.append(event['date'])
    return projection, corrected_dates
