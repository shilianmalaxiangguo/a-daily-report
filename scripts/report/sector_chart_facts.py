"""Append-only chart facts: fill dated holes without rewriting frozen decisions."""
from __future__ import annotations

import json
import os
import re
import tempfile
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from daily_report_source_health import redact_sensitive_text

from report.hypothesis_revision import _canonical_date, _hash
from report.sector_trend_tracking import (
    _day, _indexed, build_trend_evidence, fetch_trend_rows, project_trend,
    validate_trend_evidence,
)
from report.tracked_sector_facts import _number, validate_tracked_facts

SCHEMA = 'sector_chart_facts.v1'


def _current_direction(data, target_date):
    row = data.get('current_mainline_history_record') or {}
    return deepcopy(row) if row.get('date') == target_date else {}


def _focus_identity(name):
    from market_data.tushare_client import create_tushare_pro_api
    rows = create_tushare_pro_api(timeout_seconds=15).ths_index(exchange='A').to_dict('records')
    matches = [row for row in rows if row.get('name') == name and row.get('exchange') == 'A']
    return matches[0] if len(matches) == 1 else None


def _focus_track(focus, trend, target_date):
    if focus is None:
        return None
    identity = focus['identity']
    if not identity.get('name') or not identity.get('ts_code') or identity.get('exchange') != 'A':
        raise ValueError('主攻板块指数身份不完整')
    dates = [row['date'] for row in trend['tracks'][0]['path']]
    code = identity['ts_code']
    indexed = _indexed(focus['rows'], set(dates), {code})
    changes = {day: _number(row['pct_change']) for (day, _), row in indexed.items()}
    if any(change <= -100 for change in changes.values()):
        raise ValueError('主攻板块收益无效')
    market = {_day(row['trade_date']): _number(row['pct_chg']) for row in trend['raw']['market']}
    return {'track_id': f'focus:tushare.ths_daily:{code}', 'name': identity['name'],
            'started_date': target_date, 'method': '同代码板块指数',
            'path': project_trend({'started_date': target_date}, dates, changes, market, {})}


def _raw_groups(evidence):
    raw = evidence['raw']
    return {'daily': raw['daily'], 'market': raw['market'], **raw['indices']}


def _assert_extension(base, newer):
    if base['raw']['calendar'] != newer['raw']['calendar']:
        raise ValueError('补查不能改写原交易日历')
    for ident, membership in base['memberships'].items():
        if newer['memberships'].get(ident) != membership:
            raise ValueError('补查不能改写已冻结成员')
    groups = _raw_groups(newer)
    for key, rows in _raw_groups(base).items():
        indexed = {(_day(r['trade_date']), r['ts_code']): r for r in groups.get(key, [])}
        if any(indexed.get((_day(row['trade_date']), row['ts_code'])) != row for row in rows):
            raise ValueError('补查不能替换原有价格事实')


def validate_sector_chart_facts(payload, record, base):
    try:
        stamp = datetime.fromisoformat(payload['retrieved_at'])
        if (payload['schema_version'] != SCHEMA or payload['target_date'] != record['target_date']
                or payload['record_hash'] != record['artifact_hash']
                or payload['base_trend_hash'] != base['artifact_hash']
                or stamp.tzinfo is None or stamp.date().isoformat() < record['target_date']
                or payload['artifact_hash'] != _hash({k: v for k, v in payload.items() if k != 'artifact_hash'})
                or not validate_trend_evidence(payload['trend'], record)):
            return False
        _assert_extension(base, payload['trend'])
        focus = payload['focus']
        return payload['focus_track'] == _focus_track(focus, payload['trend'], record['target_date'])
    except (ValueError, TypeError, KeyError, AttributeError, IndexError):
        return False


def _query_error(exc):
    # The shared sanitizer removes credentials; omit all URL parameters as well.
    message = redact_sensitive_text(str(exc))
    message = re.sub(r'(https?://[^\s?\#\"\']+)[?\#][^\s\"\']*', r'\1?***', message)
    return {'error_type': type(exc).__name__, 'error_message': message}


def _incomplete_error(received, needed):
    """A short response is a failed query too; a bare label is not a reason."""
    return {'error_type': 'IncompleteSourceRows',
            'error_message': f'同源接口只返回{received}行，需要{needed}行，当日事实仍不完整'}


def collect_sector_chart_facts(record, base, tracked_evidence, current, *,
                               fetcher=fetch_trend_rows, identity_fetcher=_focus_identity, now=None, previous=None):
    """Query only absent dates/members; original non-null rows remain authoritative."""
    if not validate_trend_evidence(base, record):
        raise ValueError('原趋势事实无效，停止补查')
    if previous is not None and not validate_sector_chart_facts(previous, record, base):
        raise ValueError('前次图表补查与原日期不符')
    source = previous['trend'] if previous else base
    stamp = now or datetime.now(ZoneInfo('Asia/Shanghai'))
    if stamp.tzinfo is None or stamp.date().isoformat() < record['target_date']:
        raise ValueError('图表补查取得日期无效')
    memberships = deepcopy(source['memberships'])
    for bundle in tracked_evidence:
        if not validate_tracked_facts(bundle, record):
            raise ValueError('成员补查凭据无效')
        for entry in bundle['entries']:
            member = entry.get('membership')
            if member:
                old = memberships.get(entry['track_id'])
                if old is not None and old != member:
                    # Repeated capture time is not an identity change.
                    if any(old[k] != member[k] for k in ('codes', 'reference', 'reference_rows', 'source_hash')):
                        raise ValueError('补查成员与冻结成员冲突')
                else:
                    memberships[entry['track_id']] = deepcopy(member)
    raw = deepcopy(source['raw'])
    dates = [row['date'] for row in source['tracks'][0]['path']]
    codes = {code for member in memberships.values() for code in member['codes']}
    known = {(_day(row['trade_date']), row['ts_code']) for row in raw['daily']}
    jobs = [('daily', day, None, {code for code in codes if (day, code) not in known}) for day in dates]
    jobs = [job for job in jobs if job[3]]
    for track in record['tracks']:
        if track['seed']['data_source'] != 'tushare.ths_daily':
            continue
        code = track['seed']['code']
        known_dates = {_day(row['trade_date']) for row in raw['indices'].get(code, [])}
        jobs.extend(('ths_daily', day, code, {code}) for day in dates if day not in known_dates)
    market_dates = {_day(row['trade_date']) for row in raw['market']}
    jobs.extend(('index_daily', day, base['rules']['benchmark_code'], {base['rules']['benchmark_code']})
                for day in dates if day not in market_dates)
    issues = []

    def acquire(job):
        api, day, code, needed = job
        try:
            rows = fetcher(api, day, day, code)
            # All returned dates must belong to the request, even discarded codes.
            if any(_day(row['trade_date']) != day for row in rows):
                raise ValueError('返回其他日期')
            rows = [row for row in rows if row.get('ts_code') in needed]
            _indexed(rows, {day}, needed)
            if len(rows) == len(needed):
                return job, rows, {}
            return job, rows, {'issue': '同源目标日事实仍不完整', **_incomplete_error(len(rows), len(needed))}
        except Exception as exc:
            return job, [], {'issue': '同源目标日查询未完成', **_query_error(exc)}

    with ThreadPoolExecutor(max_workers=4) as pool:
        for (api, day, code, needed), rows, issue in pool.map(acquire, jobs):
            destination = raw['daily'] if api == 'daily' else raw['market'] if api == 'index_daily' else raw['indices'].setdefault(code, [])
            destination.extend(rows)
            if issue:
                issues.append({'api': api, 'date': day, 'code': code,
                               'target_date': record['target_date'],
                               'severity': 'error' if day == record['target_date'] else 'warning', **issue})
    trend = build_trend_evidence(record, raw, memberships, retrieved_at=stamp.isoformat())
    focus = deepcopy(previous['focus']) if previous else None
    name = current.get('primary_mainline') if current.get('date') == record['target_date'] else None
    if focus and focus['identity']['name'] != name:
        raise ValueError('前次主攻指数与目标日报不同')
    if name and focus is None:
        try:
            identity = identity_fetcher(name)
            if identity and identity.get('name') == name:
                focus = {'identity': identity, 'source': 'tushare.ths_index / tushare.ths_daily',
                         'rows': fetcher('ths_daily', dates[0], record['target_date'], identity['ts_code'])}
                _focus_track(focus, trend, record['target_date'])
            else:
                issues.append({'name': name, 'issue': '未取得唯一同名板块指数身份',
                               'target_date': record['target_date'], 'severity': 'error'})
        except Exception as exc:
            focus = None
            issues.append({'name': name, 'issue': '主攻方向同源历史路径未取得',
                           'target_date': record['target_date'], 'severity': 'error', **_query_error(exc)})
    payload = {'schema_version': SCHEMA, 'target_date': record['target_date'],
               'record_hash': record['artifact_hash'], 'base_trend_hash': base['artifact_hash'],
               'retrieved_at': stamp.isoformat(), 'trend': trend, 'focus': focus,
               'focus_track': _focus_track(focus, trend, record['target_date']), 'issues': issues}
    payload['artifact_hash'] = _hash(payload)
    if not validate_sector_chart_facts(payload, record, base):
        raise ValueError('图表补查与原始事实不符')
    return payload


def _directory(ledger_root, target_date):
    if not _canonical_date(target_date):
        raise ValueError('图表补查日期无效')
    return Path(ledger_root) / 'hypothesis-revision' / 'chart-facts' / target_date


def save_sector_chart_facts(payload, record, base, *, ledger_root):
    if not validate_sector_chart_facts(payload, record, base):
        raise ValueError('图表补查校验未通过')
    directory = _directory(ledger_root, record['target_date'])
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (payload['artifact_hash'] + '.json')
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=directory, delete=False) as stream:
        temporary = Path(stream.name)
        json.dump(payload, stream, ensure_ascii=False, allow_nan=False)
    try:
        try:
            os.link(temporary, path)
        except FileExistsError:
            if json.loads(path.read_text()) != payload:
                raise ValueError('图表补查文件已有不同内容')
    finally:
        temporary.unlink(missing_ok=True)
    return path


def load_sector_chart_facts(record, base, *, ledger_root):
    if base is None:
        return None
    values = []
    for path in _directory(ledger_root, record['target_date']).glob('*.json'):
        payload = json.loads(path.read_text())
        if path.stem != payload.get('artifact_hash') or not validate_sector_chart_facts(payload, record, base):
            raise ValueError('图表补查文件日期或内容不符')
        values.append(payload)
    values.sort(key=lambda row: (datetime.fromisoformat(row['retrieved_at']), row['artifact_hash']))
    for previous, current in zip(values, values[1:]):
        _assert_extension(previous['trend'], current['trend'])
    return values[-1] if values else None


def build_sector_display_context(snapshot, target_date, trend=None, chart_facts=None):
    """Project existing report labels; never promote a watch direction to a trade."""
    if not isinstance(snapshot, dict) or snapshot.get('date') != target_date:
        return None
    data = snapshot.get('data') or {}
    current = _current_direction(data, target_date)
    history = [deepcopy(row) for row in data.get('recent_mainline_history') or []
               if isinstance(row, dict) and _canonical_date(row.get('date')) and row['date'] < target_date]
    if current:
        history.append(current)
    stage = ((data.get('selection_workflow') or {}).get('sector_tournament_three_axis') or {}).get('stage_mainline') or {}
    focus = chart_facts.get('focus_track') if chart_facts else None
    if focus and focus['name'] != current.get('primary_mainline'):
        raise ValueError('补查主攻方向与目标日报不同')
    context = {'target_date': target_date, 'history': history, 'current': current,
               'stage_mainline': deepcopy(stage), 'focus_track': deepcopy(focus),
               'trade_dates': [row['date'] for row in trend['tracks'][0]['path']] if trend and trend['tracks'] else []}
    context['source_hash'] = _hash(context)
    return context
