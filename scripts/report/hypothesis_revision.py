"""Dated sector hypotheses, frozen expectations, and read-only revisions."""
from __future__ import annotations

import hashlib
import html
import json
import math
import os
import re
import tempfile
from copy import deepcopy
from datetime import date
from pathlib import Path


HYPOTHESES = (
    ('A', '持续走强', '下一份同口径日报仍上涨，并保持相对优势；板块扩散待成员事实验证。'),
    ('B', '短期脉冲', '下一份同口径日报转弱或失去相对优势，当前强势没有延续。'),
    ('C', '随市场波动', '没有稳定的相对优势；同向波动只提供相容证据，不证明因果。'),
)
SCHEMA = 'sector_hypothesis_record.v1'
DATED_SCHEMA = 'sector_hypothesis_record.v2'
LEDGER_DIRNAME = 'hypothesis-revision'


def hypothesis_ledger_root(full_html_path, *, ledger_root=None):
    if ledger_root is not None:
        return Path(ledger_root)
    full = Path(full_html_path).resolve()
    repo = Path(__file__).resolve().parents[2]
    root = repo / 'data' if full.parent in (repo / 'reports', repo / 'reports' / 'replay') else full.parent / 'data'
    return root / 'replay' if '_replay' in full.stem or full.parent.name == 'replay' else root


def hypothesis_record_path(target_date, *, ledger_root=None):
    """Return the immutable, date-addressed research record path."""
    if not _canonical_date(target_date):
        raise ValueError('板块假设日期不符，停止生成')
    root = Path(ledger_root) if ledger_root is not None else Path(__file__).resolve().parents[2] / 'data'
    return root / LEDGER_DIRNAME / f'{target_date}.json'


def _record_from_path(path, target_date):
    try:
        record = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, TypeError, ValueError) as error:
        raise ValueError('按日板块记录无法读取，停止生成') from error
    if not validate_hypothesis_record(record) or record.get('target_date') != target_date:
        raise ValueError('按日板块记录日期或内容不符，停止生成')
    return record


def load_hypothesis_record(target_date, *, ledger_root=None):
    """Read one dated record without rebuilding it from later facts."""
    path = hypothesis_record_path(target_date, ledger_root=ledger_root)
    return _record_from_path(path, target_date) if path.exists() else None


def save_hypothesis_record(record, *, ledger_root=None):
    """Persist one dated record, refusing to rewrite an existing date."""
    if not validate_hypothesis_record(record):
        raise ValueError('板块假设记录无效，停止保存')
    path = hypothesis_record_path(record['target_date'], ledger_root=ledger_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Publish a complete file without overwriting another writer's record.
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, suffix='.tmp', delete=False) as stream:
        temporary = Path(stream.name)
        json.dump(record, stream, ensure_ascii=False, indent=2, allow_nan=False)
    try:
        try:
            os.link(temporary, path)
        except FileExistsError:
            existing = _record_from_path(path, record['target_date'])
            if existing != record:
                raise ValueError('同一日期已有不同板块假设记录，拒绝覆盖')
    finally:
        temporary.unlink(missing_ok=True)
    return path


def save_hypothesis_record_from_html(html_text, target_date, *, ledger_root=None):
    match = re.search(r'<script\b[^>]*id="sector-hypothesis-record"[^>]*>(.*?)</script>',
                      str(html_text or ''), re.S)
    if not match:
        raise ValueError('日报缺少按日板块记录，停止保存')
    try:
        record = json.loads(match.group(1))
    except (TypeError, ValueError) as error:
        raise ValueError('日报按日板块记录格式不符，停止保存') from error
    if record.get('target_date') != target_date:
        raise ValueError('日报按日板块记录日期不符，停止保存')
    return save_hypothesis_record(record, ledger_root=ledger_root)


def load_previous_context(full_html_path, target_date, *, snapshot_root=None, ledger_root=None):
    """Read an earlier record in the same output namespace, with snapshot fallback.

    We say 'previous record', not T+1: the file history is not an exchange
    calendar and may contain gaps or holidays.
    """
    full = Path(full_html_path)
    replay = '_replay' in full.stem or full.parent.name == 'replay'
    suffix = '_replay' if replay else ''
    dated_root = hypothesis_ledger_root(full, ledger_root=ledger_root)
    dated_records = []
    for path in (dated_root / LEDGER_DIRNAME).glob('????-??-??.json'):
        candidate_date = path.stem
        if _canonical_date(candidate_date) and candidate_date < target_date:
            record = _record_from_path(path, candidate_date)
            dated_records.append((candidate_date, record))
    if dated_records:
        dated_records.sort(key=lambda item: item[0])
        return {
            'previous_record': dated_records[-1][1],
        }
    candidates = []
    for path in full.parent.glob(f'*_A股日报_板块日报{suffix}.html'):
        candidate_date = path.name[:10]
        if _canonical_date(candidate_date) and candidate_date < target_date:
            candidates.append((candidate_date, path))
    if candidates:
        previous_date, path = max(candidates)
        match = re.search(r'<script\b[^>]*id="sector-hypothesis-record"[^>]*>(.*?)</script>',
                          path.read_text(encoding='utf-8'), re.S)
        if match:
            record = json.loads(match.group(1))
            if not validate_hypothesis_record(record, before_date=target_date) or record['target_date'] != previous_date:
                raise ValueError('前次假设记录日期或内容不符，停止生成')
            return {'previous_record': record}
    root = Path(snapshot_root) if snapshot_root else Path(__file__).resolve().parents[2] / 'snapshots'
    if replay:
        root = root / 'replay'
    candidates = []
    for path in root.glob(f'????-??-??{suffix}.json'):
        candidate_date = path.name[:10]
        if _canonical_date(candidate_date) and candidate_date < target_date:
            candidates.append((candidate_date, path))
    if candidates:
        previous_date, path = max(candidates)
        snapshot = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(snapshot, dict) or snapshot.get('date') != previous_date:
            raise ValueError('前次冻结快照日期不符，停止生成')
        return {'previous_snapshot': snapshot}
    return {}


def _hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     allow_nan=False, separators=(',', ':')).encode()).hexdigest()


def _canonical_date(value):
    try:
        return date.fromisoformat(value).isoformat() == value
    except (TypeError, ValueError):
        return False


def _identity(row):
    # An index without its code can be displayed, but cannot be tracked by name.
    if row['data_source'] == 'tushare.ths_daily':
        return f"{row['data_source']}:{row['code']}" if row.get('code') else None
    return f"{row['data_source']}:{row['name']}"


def _width(row):
    return row['up_count'] / row['stock_count'] if row.get('stock_count') else None


def _validated_rows(rows, target_date):
    result, seen = [], set()
    for row in rows:
        if (not isinstance(row, dict) or row.get('trade_date') != target_date
                or row.get('data_source') not in ('tushare.ths_daily', 'tushare.daily.industry_aggregate')):
            continue
        change = row.get('change_pct')
        if isinstance(change, bool) or not isinstance(change, (int, float)) or not math.isfinite(change):
            continue
        if not row.get('name'):
            continue
        identity = _identity(row)
        if identity and identity in seen:
            raise ValueError('板块来源存在重复记录，停止生成')
        if identity:
            seen.add(identity)
        clean = deepcopy(row)
        up, count = clean.get('up_count'), clean.get('stock_count')
        if (isinstance(up, bool) or isinstance(count, bool)
                or not isinstance(up, (int, float)) or not isinstance(count, (int, float))
                or not math.isfinite(up) or not math.isfinite(count)
                or up != int(up) or count != int(count) or count <= 0 or up < 0 or up > count):
            clean['up_count'] = clean['stock_count'] = None
        if clean['data_source'] == 'tushare.ths_daily':
            clean['up_count'] = clean['stock_count'] = clean['turnover_yi'] = None
        result.append(clean)
    return result


def _assessment(row, market_change):
    change = row['change_pct']
    is_index = row['data_source'] == 'tushare.ths_daily'
    relative = change - market_change if is_index and market_change is not None else None
    width = _width(row)
    if relative is not None:
        if change > 0 and relative > 0:
            statuses = ('当日支持', '待跨日验证', '当日削弱')
            judgement = '今天强于全A；A值得续验，B尚未排除，C的当日解释被削弱。'
        elif change <= 0 and relative <= 0:
            statuses = ('当日反证', '当日相容', '当日相容')
            judgement = '今天没有正向相对优势；持续走强解释受反证，仍不能确认跟随市场的因果。'
        else:
            statuses = ('待验证', '待验证', '当日相容' if relative <= 0 else '当日削弱')
            judgement = '价格与相对优势不同步；等待下一份可比事实。'
        evidence = f"指数{change:+.2f}%；全A{market_change:+.2f}%；当日差值{relative:+.2f}个百分点。"
    else:
        statuses = ('当日支持' if change > 0 and width is not None and width > .5 else '待验证',
                    '待跨日验证', '待同口径指数')
        judgement = ('多数成员上涨，支持扩散观察；跨日持续性与相对指数优势仍待验证。'
                     if width is not None and width > .5 else '当日涨幅已有事实；扩散与相对优势仍待验证。')
        evidence = f"行业加权涨幅{change:+.2f}%；" if not is_index else f"指数{change:+.2f}%；"
        evidence += (f"上涨{row['up_count']}/{row['stock_count']}只。" if width is not None else '成员宽度待确认。')
    return {'relative_change': relative, 'statuses': list(statuses),
            'judgement': judgement, 'evidence': evidence}


def _freeze_sector(row, market_change):
    assessment = _assessment(row, market_change)
    is_index = row['data_source'] == 'tushare.ths_daily'
    # These rules are frozen BEFORE the following report is assessed.
    conditions = {
        'scope': '下一份同来源、同身份的收盘事实；仅检验延续一天，不等于整个趋势失效',
        'positive_change': 0,
        'positive_relative_change': 0 if is_index else None,
        'majority_width': .5 if row.get('stock_count') else None,
    }
    next_test = ('下次同代码指数仍上涨且强于全A；再补成员宽度、核心回撤和成交基准。'
                 if is_index else '下次同口径加权涨幅仍为正；成员上涨比例保持过半，再补指数比较。')
    revoke = ('若下次指数不涨且不强于全A，撤销A的“一天延续”预期；缺任何一项则待验证。'
              if is_index else '若下次加权涨幅非正且上涨成员不过半，撤销A的“一天延续”预期；缺失则待验证。')
    counter = ('成员宽度、成交基准与核心承接缺失，单日指数走强还不能证明持续扩散。'
               if is_index else (f"上涨仅{row['up_count']}/{row['stock_count']}只，扩散基础较弱。"
                    if row.get('stock_count') and _width(row) <= .5 else
                    '只有当日宽度，尚无跨日承接与同起点板块指数证据。'))
    return {**deepcopy(row), 'identity': _identity(row), **assessment,
            'conditions': conditions, 'next_test': next_test,
            'revoke': revoke, 'counter': counter}


def validate_hypothesis_record(record, *, before_date=None):
    if not isinstance(record, dict) or record.get('schema_version') not in (SCHEMA, DATED_SCHEMA):
        return False
    target = record.get('target_date')
    if not _canonical_date(target) or (before_date is not None and target >= before_date):
        return False
    if record.get('origin') not in ('as_of_report', 'historical_rebuild'):
        return False
    if record.get('definitions') != [list(item) for item in HYPOTHESES]:
        return False
    sectors = record.get('sectors')
    if not isinstance(sectors, list) or len(sectors) > 3:
        return False
    if not all(isinstance(item, dict) and item.get('trade_date') == target
               and isinstance(item.get('conditions'), dict) for item in sectors):
        return False
    try:
        valid = (record.get('artifact_hash') == _hash({k: v for k, v in record.items() if k != 'artifact_hash'})
                and len(_validated_rows(sectors, target)) == len(sectors)
                and all(item == _freeze_sector({k: item.get(k) for k in (
                    'name', 'code', 'trade_date', 'change_pct', 'up_count', 'stock_count', 'turnover_yi', 'data_source')},
                    record.get('market_change')) for item in sectors))
        if not valid or record.get('schema_version') == SCHEMA:
            return valid
        facts = record.get('facts')
        return (isinstance(facts, list) and facts == _validated_rows(facts, target)
                and record.get('input_hash') == _hash({'rows': facts, 'market_change': record.get('market_change')})
                and record.get('source_hash') == _hash(record.get('source_provenance'))
                and record.get('progress') == _track_progress_rows(record)
                and _validate_tracks(record))
    except (AttributeError, IndexError, KeyError, TypeError, ValueError):
        return False


def _review(old, new, market_change):
    if new is None:
        return {'changes': ['待验证'] * 3,
                'evidence': '今天没有同来源、同身份的记录；未上榜不能当作下跌或失败。'}
    conditions = old['conditions']
    change = new['change_pct']
    assessment = _assessment(new, market_change)
    positive = change > conditions['positive_change']
    relative = assessment['relative_change']
    width = _width(new)
    expected_relative = conditions.get('positive_relative_change')
    expected_width = conditions.get('majority_width')
    relative_ok = relative > expected_relative if relative is not None and expected_relative is not None else None
    width_ok = width > expected_width if width is not None and expected_width is not None else None
    # Missing a required observation leaves the original expectation unresolved.
    if (expected_relative is not None and relative_ok is None) or (expected_width is not None and width_ok is None):
        changes = ['待验证'] * 3
    elif positive and relative_ok is not False and width_ok is not False:
        changes = ['加强', '削弱', '削弱' if relative_ok else '待验证']
    elif not positive and (relative_ok is False or width_ok is False):
        changes = ['撤销一天延续预期', '加强', '相容但未确认因果' if relative_ok is False else '待验证']
    else:
        changes = ['削弱', '加强', '相容但未确认因果' if relative_ok is False else '待验证']
    evidence = assessment['evidence']
    if expected_relative is not None and relative_ok is None:
        evidence += '缺全A当日基准，无法核验原相对强弱条件。'
    if expected_width is not None and width_ok is None:
        evidence += '缺上涨成员数/成员总数，无法核验原宽度条件。'
    return {'changes': changes, 'evidence': evidence}


def _fact_row(row):
    return {key: deepcopy(row.get(key)) for key in (
        'name', 'code', 'trade_date', 'change_pct', 'up_count', 'stock_count', 'turnover_yi', 'data_source')}


def _new_track(seed, origin, market_change):
    return {'track_id': f"{seed['trade_date']}:{seed['identity']}",
            'identity': seed['identity'], 'started_date': seed['trade_date'], 'origin': origin,
            'seed': deepcopy(seed), 'seed_market_change': market_change,
            'seed_hash': _hash(seed), 'resolution': None,
            'events': [{'date': seed['trade_date'], 'fact': _fact_row(seed),
                        'market_change': market_change, 'changes': seed['statuses'],
                        'evidence': seed['evidence'], 'kind': 'established'}]}


def _next_event(track, row, target_date, market_change):
    review = _review(track['seed'], row, market_change)
    return {'date': target_date, 'fact': _fact_row(row) if row else None,
            'market_change': market_change, **review,
            'kind': 'missing' if review['changes'] == ['待验证'] * 3 else 'comparable'}


def _validate_tracks(record):
    tracks = record.get('tracks')
    if not isinstance(tracks, list):
        return False
    seen = set()
    for track in tracks:
        seed, events = track['seed'], track['events']
        identity = track['identity']
        if (not identity or identity in seen or identity != _identity(seed)
                or track['started_date'] != seed['trade_date']
                or not _canonical_date(track['started_date'])
                or track['track_id'] != f"{seed['trade_date']}:{identity}"
                or track['origin'] not in ('as_of_report', 'historical_rebuild')
                or seed != _freeze_sector(_fact_row(seed), track['seed_market_change'])
                or track['seed_hash'] != _hash(seed) or not isinstance(events, list) or not events):
            return False
        seen.add(identity)
        if events[0] != _new_track(seed, track['origin'], track['seed_market_change'])['events'][0]:
            return False
        previous_date = track['started_date']
        resolution = None
        for event in events[1:]:
            if not _canonical_date(event['date']) or not previous_date < event['date'] <= record['target_date']:
                return False
            fact = event['fact']
            if fact is not None and (len(_validated_rows([fact], event['date'])) != 1 or _identity(fact) != identity):
                return False
            if event != _next_event(track, fact, event['date'], event['market_change']):
                return False
            if resolution is None:
                resolution = {'date': event['date'], 'changes': event['changes']}
            previous_date = event['date']
        if track['resolution'] != resolution or events[-1]['date'] != record['target_date']:
            return False
        current = next((row for row in record['facts'] if _identity(row) == identity), None)
        if events[-1]['fact'] != current:
            return False
    return all(not sector['identity'] or sector['identity'] in seen for sector in record['sectors'])


def _track_progress_rows(record):
    rows = []
    for track in sorted(record.get('tracks') or [], key=lambda item: item.get('identity', '')):
        name = (track.get('seed') or {}).get('name') or track.get('identity')
        for event in track.get('events') or []:
            fact = event.get('fact') or {}
            rows.append({
                'date': event.get('date'), 'identity': track.get('identity'), 'name': fact.get('name') or name,
                'fact': event.get('evidence') or ('未上榜；不判失败' if event.get('kind') == 'missing' else '事实不足'),
                'states': list(event.get('changes') or ['待验证'] * 3),
                'revision': ('首次记录' if event.get('kind') == 'established' else
                             '无同源事实，保留原假设' if event.get('kind') == 'missing' else
                             '；'.join(event.get('changes') or [])),
            })
    return rows


def _progress_summary(track):
    reviewed = [event for event in track['events'][1:] if event['kind'] == 'comparable']
    missing = sum(event['kind'] == 'missing' for event in track['events'][1:])
    supported = sum(event['changes'][0] == '加强' for event in reviewed)
    last = track['events'][-1]
    resolution = track['resolution']
    result = ('首验尚无可比事实' if resolution is None else
              f"首验 {resolution['date']}：缺事实，无法验收" if resolution['changes'] == ['待验证'] * 3 else
              f"首验 {resolution['date']}：A{resolution['changes'][0]}")
    return f'可比{len(reviewed)}期 / 支持{supported}期 / 缺口{missing}期', result, last


def _track_lifecycle(track):
    """Fold frozen events in order; later evidence never changes an earlier row."""
    seed = track['seed']
    steps, streak, interrupted, retired_date = [], 0, False, None
    stage, beliefs = '尚未建立', ['尚未建立'] * 3
    for index, event in enumerate(track['events']):
        before, beliefs_before = stage, list(beliefs)
        checks = _expectation_checks(seed, event)
        if index == 0:
            stage, tone = '建立观察', 'start'
            beliefs = list(seed['statuses'])
            outcome = '起点事实，不计续验'
            reason = '据当日事实提出A；B仍可能解释单日上涨。'
        elif event['kind'] == 'missing':
            stage, tone, streak, interrupted = '缺证暂停', 'missing', 0, True
            outcome = '无法验收'
            reason = '缺' + '、'.join(check['label'] for check in checks if check['met'] is None) + '；暂停本段判断，旧结论不升级。'
            # Missing observations do not strengthen or weaken any explanation.
        elif event['changes'][0] == '撤销一天延续预期':
            stage, tone, streak, interrupted = '撤销本段预期', 'rejected', 0, True
            retired_date = retired_date or event['date']
            beliefs = list(event['changes'])
            outcome = '未兑现；触发原撤销条件'
            reason = '原来的延续条件未兑现；B获得支持，不能补理由维持A。'
        elif event['changes'][0] == '加强':
            streak += 1
            stage = ('恢复观察' if interrupted else '首次续证') if streak == 1 else f'逐份续证{streak}期'
            tone, beliefs = 'supported', list(event['changes'])
            outcome = '满足本期条件'
            reason = ('新增恢复证据；此前缺口或反证不改写。' if interrupted else
                      '本期满足原条件，A获支持、B削弱；还需后续同源事实。')
            if retired_date:
                beliefs[0] = '仅支持恢复观察；旧预期已撤销'
        else:
            stage, tone, streak, interrupted = '降级观察', 'weakened', 0, True
            beliefs = list(event['changes'])
            outcome = '原预期未全部兑现'
            reason = '价格与相对强弱或宽度未同时满足；A降级，B获得支持。'
        if retired_date:
            reason += f' {retired_date}的撤销结果保留。'
        required = ('同代码指数涨跌幅与全A当日收益' if seed['data_source'] == 'tushare.ths_daily'
                    else '同口径行业加权涨幅、上涨家数与成员总数')
        expected = '且'.join(f"{check['label']}{check['expected']}" for check in checks)
        next_task = f'下一份日报取{required}；预期{expected}。'
        if tone == 'missing':
            next_task += '若仍缺，继续暂停；后来补到的事实不补算本期成功。'
        elif retired_date:
            next_task += '只检验恢复能否延续；旧预期不复活。'
        else:
            next_task += '满足原条件才续证；部分未满足则降级，触发原反证则撤销。'
        steps.append({'date': event['date'], 'before': before, 'after': stage,
                      'beliefs_before': beliefs_before, 'beliefs_after': list(beliefs),
                      'checks': checks, 'outcome': outcome, 'evidence': event['evidence'],
                      'reason': reason, 'next_task': next_task, 'tone': tone,
                      'support_run': streak, 'retired_date': retired_date})
    return {'steps': steps, 'latest': steps[-1],
            'first_result': _progress_summary(track)[1],
            'first_outcome': steps[1]['outcome'] if len(steps) > 1 else '尚未首验'}


def _expectation_checks(seed, event):
    """Show the actual values against frozen thresholds, including partial gaps."""
    fact = event['fact']
    conditions = seed['conditions']
    change = fact['change_pct'] if fact else None
    observations = [('涨跌幅', change, conditions['positive_change'], '%')]
    if conditions.get('positive_relative_change') is not None:
        market = event['market_change']
        relative = change - market if change is not None and market is not None else None
        observations.append(('强于全A', relative, conditions['positive_relative_change'], '个百分点'))
    if conditions.get('majority_width') is not None:
        width = _width(fact) if fact else None
        observations.append(('上涨成员比例', width * 100 if width is not None else None,
                             conditions['majority_width'] * 100, '%'))
    return [{'label': label, 'expected': f'>{threshold:g}{unit}',
             'actual': f'{value:+.2f}{unit}' if value is not None else '缺数据',
             'met': value > threshold if value is not None else None}
            for label, value, threshold, unit in observations]


def build_hypothesis_revision(current_rows, *, target_date, market_change=None,
                              previous_record=None, previous_rows=None,
                              previous_date='', previous_market_change=None,
                              origin='historical_rebuild', source_provenance=None):
    if not _canonical_date(target_date):
        raise ValueError('板块假设日期不符，停止生成')
    current_rows = _validated_rows(current_rows, target_date)
    if market_change is not None and (isinstance(market_change, bool)
            or not isinstance(market_change, (float, int)) or not math.isfinite(market_change)):
        market_change = None
    if previous_record is not None and not validate_hypothesis_record(previous_record, before_date=target_date):
        raise ValueError('前次假设记录日期或内容不符，停止生成')
    if previous_record is None and previous_date:
        if not _canonical_date(previous_date) or previous_date >= target_date:
            raise ValueError('前次板块事实必须早于报告日，停止生成')
        previous_record = build_hypothesis_revision(
            previous_rows or [], target_date=previous_date,
            market_change=previous_market_change, origin='historical_rebuild')
    focus = [row for row in current_rows if row['change_pct'] > 0][:3]
    current_by_identity = {_identity(row): row for row in current_rows if _identity(row)}
    tracks = []
    if previous_record:
        tracks = deepcopy(previous_record.get('tracks') or [
            _new_track(row, previous_record['origin'], previous_record['market_change'])
            for row in previous_record['sectors'] if row.get('identity')])
    updates = []
    if previous_record:
        for track in tracks:
            old = track['seed']
            new = current_by_identity.get(track['identity'])
            event = _next_event(track, new, target_date, market_change)
            track['events'].append(event)
            if track['resolution'] is None:
                track['resolution'] = {'date': target_date, 'changes': deepcopy(event['changes'])}
            updates.append({'name': old['name'], 'previous_date': old['trade_date'],
                            'identity': old['identity'],
                            'previous_judgement': old['judgement'], 'previous_conditions': deepcopy(old['conditions']),
                            'previous_expectation': old['next_test'], 'previous_revoke': old['revoke'],
                            'origin': track['origin'], 'changes': event['changes'], 'evidence': event['evidence']})
    sectors = [_freeze_sector(row, market_change) for row in focus]
    known = {track['identity'] for track in tracks}
    for sector in sectors:
        if sector['identity'] and sector['identity'] not in known:
            tracks.append(_new_track(sector, origin, market_change))
            known.add(sector['identity'])
    record = {'schema_version': DATED_SCHEMA, 'target_date': target_date, 'origin': origin,
              'market_change': market_change,
              'definitions': [list(item) for item in HYPOTHESES],
              'input_hash': _hash({'rows': current_rows, 'market_change': market_change}),
              'previous_hash': previous_record['artifact_hash'] if previous_record else None,
              'previous_date': previous_record['target_date'] if previous_record else None,
              'facts': current_rows, 'sectors': sectors, 'updates': updates, 'tracks': tracks,
              'source_provenance': deepcopy(source_provenance)}
    record['source_hash'] = _hash(record['source_provenance'])
    record['progress'] = _track_progress_rows(record)
    record['artifact_hash'] = _hash(record)
    return record


HYPOTHESIS_STYLE = '''
.hypothesis-revision-section{min-width:0}
.hypothesis-updates,.hypothesis-facts,.hypothesis-progress{max-width:100%;overflow:auto}
.hypothesis-facts table{min-width:480px}
.hypothesis-progress table{min-width:700px}
.hypothesis-updates table{min-width:900px}
.hypothesis-rules>summary{cursor:pointer;padding:10px 0;font-weight:600;overflow-wrap:anywhere}
.hypothesis-origin{color:var(--reader-muted);font-size:13px;overflow-wrap:anywhere}
.observation-cards{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px;margin:20px 0}
.observation-card{min-width:0;padding:24px;border:1px solid var(--reader-line,#e5e5eb);border-radius:16px;background:#fff;box-shadow:none}
.observation-card header{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}
.observation-card h4{margin:0;font-size:19px;line-height:1.5}
.observation-date,.observation-note{font-size:12px;color:var(--reader-muted,#60616b)}
.observation-date{display:block;margin-top:6px}
.observation-label{display:inline-block;flex-shrink:0;max-width:50%;padding:4px 10px;border:0;border-radius:8px;background:#f1f3f5;color:#4b5563;font-size:12px;line-height:1.6}
.observation-card[data-tone=supported] .observation-label{background:#edf6f0;color:#346549}
.observation-card[data-tone=rejected] .observation-label{background:#faf0ef;color:#96514c}
.observation-card[data-tone=missing] .observation-label,.observation-card[data-tone=weakened] .observation-label{background:#f8f4e9;color:#806c3b}
.observation-card dl{display:grid;gap:16px;margin:24px 0 0}
.observation-card dl>div{display:grid;grid-template-columns:6em minmax(0,1fr);gap:12px;align-items:baseline}
.observation-card dt{font-size:13px;font-weight:400;color:var(--reader-muted,#60616b)}
.observation-card dd{margin:0;font-size:14px;line-height:1.8;overflow-wrap:anywhere}
.observation-checks{list-style:none;padding:0;margin:0}
.observation-checks li{margin:0}
.observation-card .observation-note{margin:18px 0 0;line-height:1.7}
.observation-intro{max-width:64ch;color:var(--reader-muted,#60616b)}
.observation-summary{display:flex;flex-wrap:wrap;gap:12px;margin:20px 0}
.observation-summary span{display:flex;align-items:baseline;gap:8px;padding:10px 14px;background:#f5f7f8;border:0;border-radius:10px;color:var(--reader-muted);font-size:13px}
.observation-summary strong{font-size:21px;font-weight:600;color:var(--reader-text)}
.observation-flow{min-width:0;max-width:100%;margin:20px 0 28px}
.observation-controls{display:flex;align-items:center;flex-wrap:wrap;gap:10px;margin:12px 0;min-width:0}
.observation-controls select{max-width:100%;min-width:0;min-height:40px;padding:8px 12px;font:inherit;font-size:13px;color:var(--reader-text);background:#fff;border:1px solid var(--reader-line);border-radius:9px}
.observation-controls label{font-size:13px;color:var(--reader-muted)}
.observation-flow-scroll{width:100%;max-width:100%;min-width:0;overflow:auto;overscroll-behavior-x:contain;border:1px solid var(--reader-line);border-radius:14px;background:linear-gradient(120deg,#fff8f2,#f7f3ff)}
#observation-flow-chart{height:520px;min-width:0}
.observation-flow-facts{padding:20px 24px;margin-top:16px;background:#f6f0ff;border:0;border-radius:14px;overflow-wrap:anywhere}
.observation-flow-facts h4{margin:0 0 12px;font-size:18px}
.observation-flow-facts .observation-checks{padding:0;list-style:none;line-height:1.9}
.observation-flow-fallback{font-size:13px;color:var(--reader-muted)}
.observation-relay-fact+.observation-relay-fact{border-top:1px solid #e1d3f5;margin-top:18px;padding-top:18px}
.hypothesis-current{padding:14px 18px;border:0;border-radius:12px;background:#f4f5f7}
@media(max-width:800px){.observation-cards{grid-template-columns:minmax(0,1fr)}.observation-card{padding:20px}.observation-card dl>div{grid-template-columns:1fr;gap:4px}}
.hypothesis-progress td,.hypothesis-updates td{vertical-align:top;overflow-wrap:anywhere}
.hypothesis-progress td{padding:8px 10px}
.trend-detail>summary{cursor:pointer;padding:12px 0;font-weight:600;overflow-wrap:anywhere}
.trend-echart{display:block;width:100%;height:310px;min-width:0}
#sector-trend-revisions{min-width:0;height:410px}
.trend-heat-scroll{overflow:auto;max-width:100%;padding-bottom:4px}
.trend-temperature-scale{display:flex;flex-wrap:wrap;gap:8px 12px;font-size:11px;color:var(--reader-muted);margin:10px 0}
.trend-temperature-scale span{display:inline-flex;align-items:center;gap:4px}
.trend-temperature-scale i{display:inline-block;width:13px;height:13px;border:1px solid #ddd;border-radius:2px}
.trend-detail-cards{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin-top:14px}
.trend-detail-cards .trend-chart-card:first-child{grid-column:1/-1}
.trend-detail-cards .trend-chart-card{min-width:0;padding:12px;border:1px solid var(--reader-line,#e4ddd6);border-radius:12px;background:#fffdf9}
.trend-detail-cards .trend-echart{height:260px}
.trend-detail-cards h4{margin:0 0 6px}
.trend-roster-wrap{max-width:100%;overflow:auto}
.trend-roster{width:100%;font-size:13px}
.trend-roster small{display:block;font-size:11px;color:var(--reader-muted)}
@media(max-width:600px){.trend-detail-cards{grid-template-columns:minmax(0,1fr)}.trend-detail-cards .trend-chart-card{padding:10px}}
.trend-controls{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin:16px 0 8px}
.trend-controls select{font:inherit;font-size:13px;color:inherit;border:1px solid #cfc6bb;border-radius:7px;background:#fffdf9;padding:7px;max-width:100%;min-width:0}
.trend-chart-caption,.trend-lead,.trend-gap-summary,.trend-focus-note{font-size:13px;line-height:1.65;color:var(--reader-muted)}
.sector-trend h4{margin:20px 0 8px}
.hypothesis-single-day>summary{cursor:pointer;padding:12px 0}
'''


def _observation_label(step):
    """Explain the recorded conclusion without changing its conditions."""
    if step['tone'] == 'supported':
        if step['after'].startswith('恢复观察'):
            return '重新出现好转'
        return f"连续{step['support_run']}次符合预期" if step['support_run'] > 1 else '本次符合预期'
    return {'start': '刚开始观察', 'missing': '数据不齐，暂不判断',
            'weakened': '表现不及预期', 'rejected': '原预期未兑现'}[step['tone']]


MAINLINE_CHANNELS = (('primary_mainline', '主攻线'), ('secondary_mainline', '次强线'),
                     ('competition_mainline', '竞争线'))

MAINLINE_SOURCE_LABELS = {
    'market_research_snapshot': '市场研究快照',
    'market_research_snapshot.confirmed_attack': '市场研究快照·主攻核对记录',
}


def _observation_flow(display_context, target_date):
    """Project only recorded, same-channel report intervals, never money flows."""
    empty = {'dates': [], 'nodes': [], 'links': [], 'history': [], 'sectors': [],
             'channels': [{'id': key, 'label': label} for key, label in MAINLINE_CHANNELS],
             'default_window': 7, 'source_hash': ''}
    if display_context is None:
        return empty
    if (not isinstance(display_context, dict) or not _canonical_date(target_date)
            or display_context.get('target_date') != target_date):
        raise ValueError('板块接力资料日期不符，停止展示')
    history = display_context.get('history', [])
    current = display_context.get('current')
    if current == {}:
        current = None
    if not isinstance(history, list):
        raise ValueError('板块接力历史记录不完整，停止展示')
    if current is not None and (not isinstance(current, dict) or current.get('date') != target_date):
        raise ValueError('本日主攻记录日期不符，停止展示')
    dated = {}
    for row in [*history, *([current] if current is not None else [])]:
        if not isinstance(row, dict) or not _canonical_date(row.get('date')):
            raise ValueError('板块接力历史日期不符，停止展示')
        day = row['date']
        if day > target_date:
            continue
        if day in dated and dated[day] != row:
            raise ValueError('同一日期存在冲突主攻记录，停止展示')
        dated[day] = row
    report_dates = sorted(dated)
    calendar = display_context.get('trade_dates', [])
    if (not isinstance(calendar, list) or any(not _canonical_date(day) for day in calendar)
            or len(calendar) != len(set(calendar))):
        raise ValueError('板块接力交易日期不符，停止展示')
    calendar = sorted(day for day in calendar if day <= target_date)
    # Keep every known trading-day column, including days without a report;
    # links still compare only adjacent recorded reports and never invent a flow.
    dates = sorted(set(report_dates) | {day for day in calendar if report_dates and day >= report_dates[0]})
    nodes, links = {}, {}
    for depth, day in enumerate(dates):
        row = dated.get(day)
        if row is None:
            continue
        for channel, _ in MAINLINE_CHANNELS:
            sector = row.get(channel)
            if sector is not None and not isinstance(sector, str):
                raise ValueError('板块接力名称不符，停止展示')
            if not sector or sector in ('无', '暂无', '未确认', '待确认', '无明确主线'):
                continue
            identity = f'{day}|{sector}'
            hue = int(hashlib.sha256(sector.encode()).hexdigest()[:8], 16) % 360
            node = nodes.setdefault(identity, {'name': identity, 'date': day, 'sector': sector,
                                               'depth': depth, 'color': f'hsl({hue}, 82%, 49%)',
                                               'channels': [], 'record': deepcopy(row)})
            node['channels'].append(channel)
    for previous_day, day in zip(report_dates, report_dates[1:]):
        calendar_known = previous_day in calendar and day in calendar
        missing_dates = [value for value in calendar if previous_day < value < day] if calendar_known else []
        interval = ('缺少交易日报：' + '、'.join(missing_dates) + '；仅比较前后报告，不代表连续接力'
                    if missing_dates else '相邻交易日报' if calendar_known else
                    '前后报告区间；未核对交易日历，不声称逐交易日连续')
        for channel, _ in MAINLINE_CHANNELS:
            source = f'{previous_day}|{dated[previous_day].get(channel)}'
            target = f'{day}|{dated[day].get(channel)}'
            if source not in nodes or target not in nodes:
                continue
            edge = links.setdefault((source, target), {
                'source': source, 'target': target, 'source_sector': nodes[source]['sector'],
                'target_sector': nodes[target]['sector'], 'source_date': previous_day,
                'target_date': day, 'value': 0, 'channels': [],
                'interval': interval, 'missing_dates': missing_dates, 'calendar_known': calendar_known,
                'source_record': deepcopy(dated[previous_day]), 'target_record': deepcopy(dated[day])})
            edge['value'] += 1
            edge['channels'].append(channel)
    return {**empty, 'dates': dates, 'nodes': list(nodes.values()), 'links': list(links.values()),
            'history': [deepcopy(dated[day]) for day in report_dates],
            'sectors': sorted({node['sector'] for node in nodes.values()}),
            'source_hash': display_context.get('source_hash', '')}


def _render_observation_flow(display_context, target_date):
    flow = _observation_flow(display_context, target_date)
    escaped = lambda value: html.escape(str(value), quote=True)
    if not flow['dates']:
        return '<p class="observation-flow-unavailable">缺少可比的跨日报主攻记录，暂不绘制板块接力；单日预期与原始记录仍保留在下方。</p>'
    options = ''.join(f'<option value="{escaped(name)}">{escaped(name)}</option>' for name in flow['sectors'])
    channels = ''.join(f'<option value="{key}">{label}</option>' for key, label in MAINLINE_CHANNELS)
    source_label = lambda value: MAINLINE_SOURCE_LABELS.get(value, '已冻结的历史来源' if value else '未记录')
    flow['source_labels'] = {row.get('source') or '': source_label(row.get('source')) for row in flow['history']}
    rows = ''.join('<tr>' + ''.join(f'<td>{escaped(source_label(row.get(key)) if key == "source" else row.get(key) or "未记录")}</td>'
                                   for key in ('date', 'primary_mainline', 'secondary_mainline',
                                               'competition_mainline', 'source', 'rotation_summary')) + '</tr>'
                   for row in flow['history'])
    encoded = json.dumps(flow, ensure_ascii=False, allow_nan=False).replace('<', '\\u003c')
    script = (Path(__file__).resolve().parents[1] / 'templates' / 'sector_observation_flow.js').read_text(encoding='utf-8')
    return ('<div class="observation-flow">'
            '<div class="observation-controls"><label for="observation-track">高亮板块</label>'
            f'<select id="observation-track"><option value="">全部板块</option>{options}</select>'
            f'<label for="observation-channel">观察通道</label><select id="observation-channel"><option value="">全部通道</option>{channels}</select>'
            '<label for="observation-window">近期报告</label><select id="observation-window"><option value="7">最近7份</option><option value="14">最近14份</option><option value="28">最近28份</option></select></div>'
            '<p class="observation-intro">按日期分列；色带仅连接相同通道，宽度代表记录数而非资金量。浅灰表示日报缺失或交易日历未核对；点击节点或色带可查原始记录。</p>'
            '<div class="observation-flow-scroll"><div id="observation-flow-chart" role="img" aria-label="实际板块跨日报接力图"></div></div>'
            '<p class="observation-flow-fallback">图表加载后可查看接力；全部日期、来源与依据保留在原记录中。</p>'
            '<details id="observation-flow-disclosure"><summary>所选节点与接力的原始记录</summary>'
            '<div id="observation-flow-facts" class="observation-flow-facts" aria-live="polite"></div></details>'
            '<details class="hypothesis-rules"><summary>全部主攻、次强、竞争原记录</summary>'
            '<div class="hypothesis-updates"><table><thead><tr><th>报告日期</th><th>主攻线</th><th>次强线</th><th>竞争线</th><th>原始来源</th><th>原始依据</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div></details>'
            f'<script type="application/json" id="observation-flow-data">{encoded}</script><script>{script}</script></div>')


def render_hypothesis_revision_fragment(record, *, tracked_evidence=(), trend_evidence=None, display_context=None,
                                       leader_board=None):
    from report.tracked_sector_facts import latest_entries, validate_tracked_facts, observation_projection
    if any(not validate_tracked_facts(e, record) for e in tracked_evidence):
        raise ValueError('补查事实与原日期记录不符，停止生成')
    supplements = latest_entries(tracked_evidence)
    esc = lambda value: html.escape(str(value if value is not None else ''), quote=True)
    tracks = record.get('tracks') or [
        _new_track(row, record['origin'], record['market_change'])
        for row in record['sectors'] if row.get('identity')]
    lifecycles = []
    for track in tracks:
        projected, corrected_dates = observation_projection(track, tracked_evidence)
        view = _track_lifecycle(projected)
        for step in view['steps']:
            if step['date'] in corrected_dates:
                step['after'] += '（补查）'
                step['reason'] += ' 按后来取得的事实复核；原日期记录和首验保留。'
        lifecycles.append((track, view))
    counts = {tone: sum(view['latest']['tone'] == tone for _, view in lifecycles)
              for tone in ('start', 'missing', 'supported', 'weakened', 'rejected')}
    out = ['<section class="hypothesis-revision-section compact-evidence" data-compact-item="sector_hypotheses">',
           '<h2 class="bear-section-evidence">板块观察：主攻怎样接力</h2>',
           '<p>先看各日报记录的主攻板块接力，再看月内走势。当前主攻不等于已确认阶段主线；观察结论不直接产生买入资格。</p>']
    out.append('<div class="observation-summary" aria-label="报告日核对结果">' + ''.join(
        f'<span><strong>{counts[tone]}</strong>{label}</span>' for tone, label in (
            ('supported', '符合原条件'), ('weakened', '表现不及预期'), ('rejected', '原预期未兑现'),
            ('missing', '数据不齐'), ('start', '刚开始观察'))) + '</div>')
    followups = [event for track in tracks for event in track['events'][1:]]
    if supplements:
        checked = sum(e['event'] is not None for e in supplements.values())
        out.append(f'<p class="hypothesis-current"><strong>到期核验：</strong>{checked}项已取得事实 · {len(supplements)-checked}项取数未完成。'
                   '按旧名单主动查询；补查单独留痕，不改原首验。</p>')
    if not supplements and followups and all(event['kind'] == 'missing' for event in followups):
        out.append('<p>旧观察缺少可比续证；今日新热点只有起点，尚未形成可比跟踪链。</p>')
    if record['origin'] == 'historical_rebuild' or any(t['origin'] == 'historical_rebuild' for t in tracks):
        out.append('<p class="hypothesis-origin">包含历史重建：按冻结事实复核，不冒充当时预测，不计入命中率。</p>')
    out.append('<h3>板块跨日报接力</h3>')
    out.append(_render_observation_flow(display_context, record['target_date']))
    if lifecycles:
        out.append('<details class="hypothesis-single-day"><summary>逐板块解释与全部原始记录</summary>')
        out.append('<div class="observation-cards">')
        for track, view in lifecycles:
            last, seed = view['latest'], track['seed']
            supplement = supplements.get(track['track_id'])
            previous = view['steps'][-2] if len(view['steps']) > 1 else None
            before = (f"{previous['date']}：{_observation_label(previous)}。" if previous else
                      '首次记录，还没有上次判断。')
            expected = '；'.join(f"{c['label']}{c['expected']}" for c in last['checks'])
            next_step = f'下份日报仍用同一板块口径，检查{expected}。'
            if last['tone'] == 'missing':
                next_step = f'先补齐{last["date"]}缺失的事实，再核对原条件；缺数据期间不算预期兑现。'
            elif last['retired_date']:
                next_step += '即使好转，也只作为新的恢复观察，不改写此前未兑现的结果。'
            elif last['tone'] == 'start':
                next_step += '等到后续事实出现，才能判断是否延续。'
            else:
                next_step += '全部满足才算继续符合预期，否则重新评估。'
            interpretation = {
                'start': '今天只是观察起点，还不能说上涨已经延续。',
                'missing': '缺少可比数据，既不能算成功，也不能据此判失败。',
                'weakened': '原条件只满足了一部分，不能继续按原来的强度期待。',
                'rejected': '原先期待的继续走强没有兑现，不再沿用这段预期。',
                'supported': '本次满足原条件，但不能据此确认整段趋势或取得买入资格。',
            }[last['tone']]
            if last['retired_date']:
                interpretation += f" {last['retired_date']}未兑现的记录仍然保留。"
            note = ''
            if supplement:
                if supplement['event']:
                    note = '本日事实来自后续补查；只用于复核，不算当时已经预测正确。'
                else:
                    note = f"本日补查未完成：{supplement['issue']}。未取得的事实不补算成功。"
            out.append(f'<article class="observation-card" data-track-id="{esc(track["track_id"])}" data-tone="{esc(last["tone"])}">'
                       f'<header><div><h4>{esc(seed["name"])}</h4><small class="observation-date">{esc(track["started_date"])}开始观察 · 本次核对{esc(last["date"])}</small></div>'
                       f'<span class="observation-label">{esc(_observation_label(last))}</span></header><dl>')
            out.append(f'<div><dt>上次怎么看</dt><dd>{esc(before)}<br>原本等的是：{esc(expected)}。</dd></div>')
            out.append('<div><dt>本日发生了什么</dt><dd><ul class="observation-checks">')
            for check in last['checks']:
                result = '待补数据' if check['met'] is None else '符合原条件' if check['met'] else '不符合原条件'
                out.append(f'<li>{esc(check["label"])} {esc(check["actual"])} · {esc(result)}</li>')
            fact = supplement['fact'] if supplement and supplement['event'] else track['events'][-1]['fact']
            if fact and fact.get('stock_count'):
                out.append(f'<li>上涨成员 {esc(fact["up_count"])}/{esc(fact["stock_count"])}</li>')
            out.append(f'</ul></dd></div><div><dt>现在怎么看</dt><dd>{esc(interpretation)}</dd></div>'
                       f'<div><dt>接下来等什么</dt><dd>{esc(next_step)}</dd></div></dl>')
            if note:
                out.append(f'<p class="observation-note">{esc(note)}</p>')
            out.append('</article>')
        out.append('</div><p class="hypothesis-origin">这里只按已有报告核对，不代表每天都有数据。首次核对结果和逐期事实保留在下方明细；后来的好转不会抹去过去的缺口或失败。</p>')
        out.append('<details class="hypothesis-rules hypothesis-journal"><summary>逐板块核对：原预期 → 实际证据 → 修正前后 → 下一检验</summary>')
        for track, view in lifecycles:
            seed = track['seed']
            source = '同花顺板块指数 ' + (seed.get('code') or '缺代码') if seed['data_source'] == 'tushare.ths_daily' else '行业汇总（成交额加权）'
            out.append(f'<details class="hypothesis-rules" data-journal-track="{esc(track["track_id"])}"><summary>{esc(seed["name"])} · {esc(view["latest"]["after"])}</summary>')
            out.append(f'<p><strong>原判断 {esc(track["started_date"])}：</strong>{esc(seed["judgement"])}</p>')
            out.append(f'<p><strong>原预期：</strong>{esc(seed["next_test"])}</p><p><strong>原撤销条件：</strong>{esc(seed["revoke"])}</p>')
            out.append(f'<p class="hypothesis-origin">来源：{esc(source)}。观察单位：下一份日报复核一次；原条件只检验一次延续，不直接确认整段趋势。</p>')
            out.append(f'<p><strong>{esc(view["first_result"])}</strong></p>')
            out.append('<div class="hypothesis-updates"><table><thead><tr><th>日期 / 修正前</th><th>原条件与实际值</th><th>本次结论 / 修正后</th><th>A / B / C变化</th><th>下一检验</th></tr></thead><tbody>')
            # Keep the original date journal intact; supplement rows below
            # explain each difference visible in the progress projection.
            for step in _track_lifecycle(track)['steps']:
                checks = '<br>'.join(esc(f"{c['label']} {c['expected']}；实际{c['actual']}；" +
                    ('缺失' if c['met'] is None else '满足' if c['met'] else '未满足')) for c in step['checks'])
                beliefs = '<br>'.join(esc(f'{key}：{before} → {after}') for (key, _, _), before, after in
                                     zip(HYPOTHESES, step['beliefs_before'], step['beliefs_after']))
                out.append(f'<tr data-revision-date="{esc(step["date"])}"><td>{esc(step["date"])}<br>{esc(step["before"])}</td>'
                           f'<td>{checks}<p>{esc(step["evidence"])}</p></td><td>{esc(step["outcome"])} → {esc(step["after"])}<p>{esc(step["reason"])}</p></td>'
                           f'<td>{beliefs}</td><td>{esc(step["next_task"])}</td></tr>')
            dated_supplements = {}
            for evidence in tracked_evidence:
                for dated in [*evidence.get('history', []), evidence]:
                    for entry in dated['entries']:
                        if entry['track_id'] == track['track_id']:
                            previous = dated_supplements.get(dated['target_date'], {})
                            if entry['event'] or not previous.get('event'):
                                dated_supplements[dated['target_date']] = {**entry, 'retrieved_at': dated['retrieved_at']}
            for supplement_date, supplement in sorted(dated_supplements.items()):
                event = supplement['event']
                checks = '<br>'.join(esc(f"{c['label']} {c['expected']}；实际{c['actual']}；" +
                    ('缺失' if c['met'] is None else '满足' if c['met'] else '未满足'))
                    for c in _expectation_checks(seed, event)) if event else esc(supplement['issue'])
                changes = '；'.join(f'{key}：{value}' for (key, _, _), value in zip(HYPOTHESES, event['changes'])) if event else '不更新A/B/C'
                out.append(f'<tr data-supplement-date="{esc(supplement_date)}"><td>{esc(supplement_date)}补查<br>取得于{esc(supplement["retrieved_at"])}</td>'
                           f'<td>{checks}</td><td>{esc(supplement["basis"])}；原首验保留</td><td>{esc(changes)}</td><td>继续按固定身份取数，不因退榜停止</td></tr>')
            out.append('</tbody></table></div></details>')
        out.append('</details></details>')
    else:
        out.append('<p>尚无可复核的观察记录。</p>')
    if trend_evidence is not None:
        from report.sector_trend_tracking import render_trend_fragment
        out.append(render_trend_fragment(trend_evidence, record, display_context=display_context,
                                        leader_board=leader_board))
        out.append('<details class="hypothesis-rules"><summary>今日上涨榜：发现新观察</summary>')
    out.append('<h3>今日上涨榜：发现新观察</h3>')
    sectors = record['sectors']
    if sectors:
        show_width = any(row.get('stock_count') for row in sectors)
        show_amount = any(row.get('turnover_yi') is not None for row in sectors)
        show_relative = any(row.get('relative_change') is not None for row in sectors)
        headings = ['板块分支', '涨跌幅']
        if show_relative:
            headings.append('强于全A（百分点）')
        if show_width:
            headings.append('上涨/样本')
        if show_amount:
            headings.append('成交（亿）')
        out.append('<div class="hypothesis-facts compact-sector-facts sector-daily-facts"><table><thead><tr>' + ''.join(f'<th>{esc(v)}</th>' for v in headings) + '</tr></thead><tbody>')
        for row in sectors:
            values = [row['name'], f"{row['change_pct']:+.2f}%"]
            if show_relative:
                values.append(f"{row['relative_change']:+.2f}" if row.get('relative_change') is not None else '缺全A基准')
            if show_width:
                values.append(f"{row['up_count']}/{row['stock_count']}" if row.get('stock_count') else '缺成员数据')
            if show_amount:
                values.append(f"{row['turnover_yi']:.2f}" if row.get('turnover_yi') is not None else '缺成交数据')
            out.append('<tr>' + ''.join(f'<td>{esc(value)}</td>' for value in values) + '</tr>')
        out.append('</tbody></table></div>')
        if all(row['data_source'] == 'tushare.ths_daily' for row in sectors):
            out.append('<small>同花顺板块指数上涨榜前三；指数当日收益，分支可能重叠。</small>')
        else:
            out.append('<small>行业上涨榜前三；成交额加权涨幅非板块指数收益。</small>')
        gaps = []
        if not show_width:
            gaps.append('缺成员上涨/总数，无法判断扩散')
        if not show_amount:
            gaps.append('缺同口径成交额与历史基准，无法判断放量')
        if any(row['data_source'] == 'tushare.ths_daily' for row in sectors) and not show_relative:
            gaps.append('缺全A当日收益，无法比较相对强弱')
        if gaps:
            out.append(f'<p class="hypothesis-origin">{esc("；".join(gaps))}。</p>')
    else:
        out.append('<p>目标日板块事实不足，暂不排列观察顺序。</p>')
    if trend_evidence is not None:
        out.append('</details>')
    out.append('<details class="hypothesis-rules"><summary>三个假设、来源与研究边界</summary><table class="sector-daily-hypotheses"><tbody>')
    for key, title, definition in HYPOTHESES:
        out.append(f'<tr class="compact-hypothesis-card"><td>{esc(key+"｜"+title)}</td><td>{esc(definition)}</td></tr>')
    out.append('</tbody></table><p>B与C可以同时相容，不强行分配三项概率；价格相对强弱不证明市场带动的因果。</p>')
    out.append('<p>提前交易需事件原文、发布时点及之前价格路径；没有这些事实，保持待确认。放量需同股成交基准，龙头需持续领涨与带动成员，成交额不等于放量或资金净流入。</p>')
    out.append('<p>先固定预测事件、期限、证伪条件与最大计划损失。未校准不填写概率；后续事实只修正当前记录，不改写原预期。缺失不等于失败。</p>')
    out.append('<p>日期记录保留原始事实与来源，修正表按冻结条件逐行复核；旧记录的本次整理不冒充新增事前承诺。完整观察进度保留，不因今日退榜或窗口移动删除旧节点。</p></details>')
    out.append('<p>研究只调整观察结论；参与按首屏原计划和认错线，B1先参与、B2确认后补，未确认不补足。</p></section>')
    return ''.join(out)
