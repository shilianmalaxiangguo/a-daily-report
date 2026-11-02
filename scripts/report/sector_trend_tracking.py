"""Dated, fixed-universe trend paths; historical context is not a forecast."""
from __future__ import annotations

import html
import json
import math
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from report.hypothesis_revision import _canonical_date, _hash, validate_hypothesis_record
from report.tracked_sector_facts import _aggregate, _membership_matches, _number, validate_tracked_facts

SCHEMA = 'sector_trend_path.v1'
RULES = {'version': 'trend_review.v1', 'background_intervals': 20, 'comparison_intervals': 5,
         'weak_windows': 2, 'benchmark_code': '000985.CSI', 'basket': 'fixed_members_daily_equal_weight'}
LEADER_LIMIT = 3
LEADER_WINDOW = 30
# 冷暖方格只在报告自身板块口径内排名：概念口径与行业口径不混排。
LEADER_UNIVERSES = {'concept': ('N', ('885', '886')), 'industry': ('I', ('881', '884', '700'))}


def leader_board_universe(rows):
    """按报告自身板块事实识别口径：885/886 为概念，881/884/700 为行业。

    行业聚合口径（tushare.daily.industry_aggregate）不带指数代码，按来源判定为行业。
    """
    codes = [str((row or {}).get('code') or '').strip().upper() for row in rows or []]
    if any(code[:3] in ('885', '886') for code in codes):
        return 'concept'
    if any(code[:3] in ('881', '884', '700') for code in codes):
        return 'industry'
    sources = [str((row or {}).get('data_source') or '') for row in rows or []]
    if any('industry_aggregate' in source for source in sources):
        return 'industry'
    return 'concept'


def _day(value):
    raw = str(value)
    if len(raw) == 8 and raw.isdigit():
        normalized = f'{raw[:4]}-{raw[4:6]}-{raw[6:]}'
    else:
        normalized = raw
    parsed = date.fromisoformat(normalized)
    if raw not in (parsed.isoformat(), parsed.strftime('%Y%m%d')):
        raise ValueError('趋势事实日期格式不符')
    return parsed.isoformat()


def fetch_trend_rows(api, start, end, code=None):
    from market_data.tushare_client import create_tushare_pro_api
    pro = create_tushare_pro_api(timeout_seconds=15)
    args = {'start_date': start.replace('-', ''), 'end_date': end.replace('-', '')}
    fields = {'daily': 'ts_code,trade_date,pct_chg,amount',
              'index_daily': 'ts_code,trade_date,pct_chg',
              'ths_daily': 'ts_code,trade_date,pct_change',
              'trade_cal': 'exchange,cal_date,is_open'}
    if code:
        args['ts_code'] = code
    if api == 'trade_cal':
        args['exchange'] = 'SSE'
    rows, offset = [], 0
    while True:
        part = getattr(pro, api)(**args, fields=fields[api], limit=6000, offset=offset).to_dict('records')
        rows.extend(part)
        if len(part) < 6000:
            return rows
        offset += 6000
        if offset > 24000:
            raise ValueError('趋势事实分页未结束')


def _indexed(rows, allowed_dates, codes):
    result = {}
    for raw in rows:
        day = _day(raw['trade_date'])
        code = raw['ts_code']
        if code not in codes or day not in allowed_dates:
            raise ValueError('趋势事实日期或股票身份不符')
        key = (day, code)
        if key in result:
            raise ValueError('趋势事实重复')
        result[key] = raw
    return result


def project_trend(track, dates, changes, market, breadth):
    """Prefix-only calculations: appending tomorrow never changes yesterday."""
    path, value, benchmark, peak = [], 100., 100., 100.
    weak = 0
    origin_value = None
    for i, day in enumerate(dates):
        change, broad = changes.get(day), breadth.get(day)
        market_change = market.get(day)
        if i:
            value = value * (1 + change / 100) if value is not None and change is not None else None
            benchmark = (benchmark * (1 + market_change / 100)
                         if benchmark is not None and market_change is not None else None)
        else:
            value = 100. if change is not None else None
            benchmark = 100. if market_change is not None else None
        if value is not None:
            peak = max(peak, value)
        if day == track['started_date']:
            origin_value = value
        r5 = m5 = None
        # Compute the recent window from returns, independently of any older
        # missing day; the full-path cumulative value remains unknown after a gap.
        recent_days = dates[max(0, i-4):i+1]
        if i >= 5 and all(changes.get(d) is not None for d in recent_days):
            r5 = (math.prod(1 + changes[d] / 100 for d in recent_days) - 1) * 100
        if i >= 5 and all(market.get(d) is not None for d in recent_days):
            m5 = (math.prod(1 + market[d] / 100 for d in recent_days) - 1) * 100
        relative5 = r5 - m5 if r5 is not None and m5 is not None else None
        recent_width = [breadth.get(d) for d in recent_days]
        mean_width = (sum(recent_width) / 5 if len(recent_width) == 5
                      and all(v is not None for v in recent_width) else None)
        previous_width = breadth.get(dates[i-1]) if i else None
        narrowing = broad is not None and previous_width is not None and broad < previous_width
        weak = weak + 1 if r5 is not None and relative5 is not None and r5 <= 0 and relative5 <= 0 else 0
        if change is None or market_change is None or r5 is None or relative5 is None:
            stage, explanation = '路径待补齐', '缺本日或完整5日比较；不以单日涨跌更新整段判断。'
        elif weak >= RULES['weak_windows']:
            stage, explanation = '连续走弱', '连续两次5日累计与相对表现均非正；下调A，B获支持。'
        elif weak:
            stage, explanation = '走势承压', '5日累计与相对表现均非正；下调A，继续核验能否修复。'
        elif r5 > 0 and relative5 > 0:
            if change < 0 or narrowing or (mean_width is not None and mean_width <= .5):
                stage, explanation = '上行中分歧', '5日价格与相对优势仍在；当日回落或内部参与减弱，A保留但扩散不加强。'
            else:
                stage, explanation = '上行证据延续', '5日价格与相对优势同向；A获阶段支持，仍需后续检验。'
        else:
            stage, explanation = '方向分化', '5日价格与相对优势不同步；A未获共同支持，保留B/C。'
        followups = sum(track['started_date'] < d <= day for d in dates)
        background = day < track['started_date']
        if background:
            judgement = '历史背景：' + stage
        elif followups < 5:
            judgement = f'观察后{followups}日：' + stage
            explanation += ' 建立观察后不足5个交易日，不确认新趋势。'
        else:
            judgement = stage
        if broad is None:
            explanation += ' 成员宽度缺失，不能确认板块扩散。'
        path.append({'date': day, 'background': background, 'change_pct': change,
                     'level': value, 'market_level': benchmark,
                     'cumulative_pct': value - 100 if value is not None else None,
                     'excess_pp': value - benchmark if value is not None and benchmark is not None else None,
                     'drawdown_pct': (value / peak - 1) * 100 if value is not None else None,
                     'since_observation_pct': (value / origin_value - 1) * 100
                         if not background and value is not None and origin_value is not None else None,
                     'five_day_pct': r5, 'five_day_excess_pp': relative5,
                     'breadth': broad, 'five_day_breadth': mean_width, 'narrowing': narrowing,
                     'before': path[-1]['judgement'] if path else '背景起点',
                     'judgement': judgement, 'reason': explanation,
                     'next_test': '下次仍检查5日累计及相对表现；连续两次均非正则下调A。上涨面与5日均值一并复核。'})
    return path


def build_trend_evidence(record, raw, memberships, *, retrieved_at):
    if not validate_hypothesis_record(record):
        raise ValueError('原观察记录无效')
    target = record['target_date']
    stamp = datetime.fromisoformat(retrieved_at)
    if not stamp.tzinfo or stamp.date().isoformat() < target:
        raise ValueError('趋势事实取得时间无效')
    calendar = raw['calendar']
    calendar_days = [_day(row['cal_date']) for row in calendar]
    if (not calendar_days or len(set(calendar_days)) != len(calendar_days)
            or max(calendar_days) != target or any(d > target for d in calendar_days)
            or any(row['exchange'] != 'SSE' or row['is_open'] not in (0, 1) for row in calendar)):
        raise ValueError('趋势交易日历不完整或日期不符')
    ordered_calendar = sorted(calendar_days)
    if (date.fromisoformat(ordered_calendar[-1]) - date.fromisoformat(ordered_calendar[0])).days + 1 != len(calendar_days):
        raise ValueError('趋势交易日历存在缺日')
    dates = sorted(_day(row['cal_date']) for row in calendar if row['is_open'] == 1)
    if not dates or dates[-1] != target:
        raise ValueError('目标日不在交易日历内')
    allowed = set(dates)
    market_rows = _indexed(raw['market'], allowed, {RULES['benchmark_code']})
    market = {d: _number(r['pct_chg']) for (d, _), r in market_rows.items()}
    if any(v <= -100 for v in market.values()):
        raise ValueError('基准收益无效')
    for track in record['tracks']:
        for event in track['events']:
            if (event['date'] in market and event['market_change'] is not None
                    and abs(market[event['date']] - event['market_change']) > .0001):
                raise ValueError('趋势基准与原日期记录不符')
    all_codes = {c for m in memberships.values() for c in m['codes']}
    stocks = _indexed(raw['daily'], allowed, all_codes)
    tracks = []
    for track in record['tracks']:
        seed, ident = track['seed'], track['track_id']
        membership = memberships.get(ident)
        changes, breadth = {}, {}
        if seed['data_source'] == 'tushare.daily.industry_aggregate':
            if membership:
                codes = membership['codes']
                if not codes or len(set(codes)) != len(codes):
                    raise ValueError('趋势成员清单不完整')
                reference = _aggregate(seed, membership['reference_rows'], seed['trade_date'], codes)
                if not _membership_matches(seed, reference):
                    raise ValueError('趋势成员与起点事实不一致')
                for d in dates:
                    rows = [stocks.get((d, c)) for c in codes]
                    if any(row is None for row in rows):
                        continue
                    returns = [_number(r['pct_chg']) for r in rows]
                    if any(v <= -100 for v in returns):
                        raise ValueError('成员收益无效')
                    changes[d] = sum(returns) / len(codes)
                    breadth[d] = sum(v > 0 for v in returns) / len(codes)
                # Rechecking the original day prevents silently changing the
                # acquisition universe or provider beneath a fixed observation.
                if seed['trade_date'] in changes:
                    reference_rows = [stocks[(seed['trade_date'], c)] for c in codes]
                    if not _membership_matches(seed, _aggregate(seed, reference_rows, seed['trade_date'], codes)):
                        raise ValueError('趋势起点行情与原记录不符')
            method = '固定成员每日等权研究组合'
        else:
            rows = _indexed(raw['indices'].get(seed['code'], []), allowed, {seed['code']})
            changes = {d: _number(r['pct_change']) for (d, _), r in rows.items()}
            if any(v <= -100 for v in changes.values()):
                raise ValueError('板块指数收益无效')
            if seed['trade_date'] in changes and abs(changes[seed['trade_date']] - seed['change_pct']) > .0001:
                raise ValueError('趋势指数起点与原记录不符')
            method = '同代码板块指数'
        tracks.append({'track_id': ident, 'seed_hash': track['seed_hash'], 'name': seed['name'],
                       'started_date': track['started_date'], 'method': method,
                       'member_count': len(membership['codes']) if membership else None,
                       'path': project_trend(track, dates, changes, market, breadth)})
    result = {'schema_version': SCHEMA, 'rules': deepcopy(RULES), 'target_date': target,
              'record_hash': record['artifact_hash'], 'retrieved_at': retrieved_at,
              'source': 'tushare.daily / ths_daily / index_daily / trade_cal',
              'calendar_start': ordered_calendar[0], 'memberships': deepcopy(memberships),
              'raw': deepcopy(raw), 'tracks': tracks}
    result['artifact_hash'] = _hash(result)
    return result


def validate_trend_evidence(evidence, record):
    try:
        return evidence == build_trend_evidence(record, evidence['raw'], evidence['memberships'],
                                                retrieved_at=evidence['retrieved_at'])
    except (ValueError, KeyError, TypeError, AttributeError, OverflowError):
        return False


def collect_trend_evidence(record, tracked_evidence, *, previous=None, fetcher=fetch_trend_rows):
    if any(not validate_tracked_facts(e, record) for e in tracked_evidence):
        raise ValueError('趋势所用成员凭据无效')
    memberships = deepcopy(previous['memberships']) if previous else {}
    for bundle in tracked_evidence:
        for dated in [*bundle.get('history', []), bundle]:
            for entry in dated['entries']:
                if entry.get('membership'):
                    old = memberships.get(entry['track_id'])
                    if old and any(old[key] != entry['membership'][key]
                                   for key in ('codes', 'reference', 'reference_rows', 'source_hash')):
                        raise ValueError('趋势固定成员发生变更')
                    if not old:
                        memberships[entry['track_id']] = deepcopy(entry['membership'])
    target = record['target_date']
    if previous and (previous['target_date'] >= target or previous['rules'] != RULES):
        raise ValueError('前次趋势日期或规则不符')
    start = previous['calendar_start'] if previous else (date.fromisoformat(
        min([target] + [t['started_date'] for t in record['tracks']])) - timedelta(days=45)).isoformat()
    calendar = fetcher('trade_cal', start, target)
    if not previous:
        opened = sorted(_day(r['cal_date']) for r in calendar if r['is_open'] == 1)
        first_observation = min([target] + [t['started_date'] for t in record['tracks']])
        earlier = [d for d in opened if d <= first_observation]
        start = earlier[-21] if len(earlier) >= 21 else opened[0]
        calendar = [r for r in calendar if _day(r['cal_date']) >= start]
    dates = sorted(_day(r['cal_date']) for r in calendar if r['is_open'] == 1)
    if previous:
        frozen_calendar = {_day(r['cal_date']): r for r in previous['raw']['calendar']}
        if any(frozen_calendar.get(_day(r['cal_date']), r) != r for r in calendar):
            raise ValueError('历史交易日历发生变更')
    codes = {c for m in memberships.values() for c in m['codes']}
    previous_codes = {c for m in (previous or {}).get('memberships', {}).values() for c in m['codes']}
    def daily(day):
        # Keep earlier frozen rows, including their explicit gaps. Query only
        # newly observed members on old dates and the full universe on new dates.
        required = codes - previous_codes if previous and day <= previous['target_date'] else codes
        return [r for r in fetcher('daily', day, day) if r['ts_code'] in required] if required else []
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = [row for part in pool.map(daily, dates) for row in part]
    begin_new = (date.fromisoformat(previous['target_date']) + timedelta(days=1)).isoformat() if previous else start
    market = fetcher('index_daily', begin_new, target, RULES['benchmark_code'])
    indices = {}
    for track in record['tracks']:
        seed = track['seed']
        if seed['data_source'] == 'tushare.ths_daily':
            code = seed['code']
            index_start = begin_new if previous and code in previous['raw']['indices'] else start
            indices[code] = fetcher('ths_daily', index_start, target, code)
    if previous:
        rows = [*deepcopy(previous['raw']['daily']), *rows]
        market = [*deepcopy(previous['raw']['market']), *market]
        for code, old in previous['raw']['indices'].items():
            indices[code] = [*deepcopy(old), *indices.get(code, [])]
    result = build_trend_evidence(record, {'calendar': calendar, 'daily': rows,
                                          'market': market, 'indices': indices}, memberships,
                                  retrieved_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat())
    # Already saved successful supplements remain the reference for their day.
    tracks_by_id = {t['track_id']: t for t in record['tracks']}
    for bundle in tracked_evidence:
        for entry in bundle['entries']:
            if entry.get('fact') and entry.get('membership'):
                codes = entry['membership']['codes']
                same_day = [r for r in rows if _day(r['trade_date']) == target and r['ts_code'] in codes]
                fact = _aggregate(tracks_by_id[entry['track_id']]['seed'], same_day, target, codes)
                if any(fact[key] != entry['fact'][key]
                       for key in ('change_pct', 'up_count', 'stock_count', 'turnover_yi')):
                    raise ValueError('趋势事实与已保存补查结果冲突')
    return result


def trend_path(target_date, ledger_root):
    if not _canonical_date(target_date):
        raise ValueError('趋势记录日期无效')
    return Path(ledger_root) / 'hypothesis-revision' / 'trends' / f'{target_date}.json'


def load_trend_evidence(record, *, ledger_root):
    path = trend_path(record['target_date'], ledger_root)
    if not path.exists():
        return None
    result = json.loads(path.read_text(encoding='utf-8'))
    if not validate_trend_evidence(result, record):
        raise ValueError('趋势记录与日期事实不符')
    return result


def save_trend_evidence(evidence, record, *, ledger_root):
    if not validate_trend_evidence(evidence, record):
        raise ValueError('趋势事实校验失败')
    path = trend_path(record['target_date'], ledger_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        json.dump(evidence, stream, ensure_ascii=False, allow_nan=False, indent=2)
    try:
        try:
            os.link(temporary, path)
        except FileExistsError:
            if json.loads(path.read_text(encoding='utf-8')) != evidence:
                raise ValueError('同日趋势记录已有不同内容，拒绝覆盖')
    finally:
        temporary.unlink(missing_ok=True)
    return path


def price_temperature(change):
    """Seven signed return bands; no claim about sentiment or future returns."""
    if change is None:
        return None
    if change <= -3:
        return -3
    if change <= -1:
        return -2
    if change < 0:
        return -1
    if change >= 3:
        return 3
    if change >= 1:
        return 2
    return 1 if change > 0 else 0


def project_chart_track(source):
    """Review markers use only each day's prefix; none grants participation."""
    rows, pending, streak, early_run, followups = [], False, 0, 0, 0
    for index, original in enumerate(source['path']):
        row = deepcopy(original)
        previous = source['path'][index - 1] if index else None
        known = all(row.get(k) is not None for k in
                    ('level', 'change_pct', 'five_day_pct', 'five_day_excess_pp', 'drawdown_pct'))
        strong = known and row['five_day_pct'] > 0 and row['five_day_excess_pp'] > 0
        streak = streak + 1 if strong else 0
        marker = ''
        if not strong:
            pending = False
        elif row['change_pct'] < 0 and row['drawdown_pct'] < 0 and previous and all(
                previous.get(k) is not None and previous[k] > 0
                for k in ('five_day_pct', 'five_day_excess_pp')):
            if not pending:
                marker = '回踩观察'
            pending = True
        elif pending and row['change_pct'] > 0 and previous and row['drawdown_pct'] > previous['drawdown_pct']:
            breadth = row.get('breadth')
            previous_breadth = previous.get('breadth')
            if breadth is not None and previous_breadth is not None and breadth > .5 and breadth > previous_breadth:
                marker, pending = '价格与扩散恢复', False
            elif breadth is None:
                marker, pending = '仅价格修复', False
        stage = row['judgement'].split('：')[-1]
        relative_day = None
        if (previous and previous.get('market_level') and row.get('market_level') is not None
                and row.get('change_pct') is not None):
            relative_day = row['change_pct'] - (row['market_level'] / previous['market_level'] - 1) * 100
        if row['date'] < source['started_date']:
            progress, early_run = '观察前背景', 0
        elif row['date'] == source['started_date']:
            progress, early_run = '首次出现', 0
        else:
            followups += 1
            daily_strong = relative_day is not None and relative_day > 0 and row['change_pct'] > 0
            early_run = early_run + 1 if daily_strong else 0
            if relative_day is None:
                progress = '缺证暂停'
            elif marker:
                progress = marker
            elif stage == '连续走弱':
                progress = '长段承压·短线续强' if daily_strong else '持续走弱'
            elif daily_strong and row.get('narrowing'):
                progress = '价格续强·扩散收窄'
            elif early_run >= 2:
                progress = '延续增强' if strong else '短线续强·长段待验'
            elif daily_strong:
                progress = '再次走强'
            elif strong:
                progress = '分歧观察'
            else:
                progress = '延续受阻'
        if row['date'] < source['started_date']:
            role = '背景'
        elif row['date'] == source['started_date']:
            role = '新出现·待续证'
        elif followups >= 10 and strong and row.get('cumulative_pct') is not None and row['cumulative_pct'] > 0:
            breadth = row.get('breadth')
            role = '主线候选' if breadth is not None and breadth > .5 else '主线候选·扩散待确认'
        elif stage == '连续走弱':
            role = '走弱'
        elif marker:
            role = '竞争中'
        elif daily_strong or strong:
            role = '轮动观察'
        else:
            role = '竞争中'
        row.update(marker=marker, strong_streak=streak, temperature=price_temperature(row['change_pct']),
                   progress=progress, role=role, early_run=early_run, followup_days=followups,
                   phase={'路径待补齐': 0, '上行证据延续': 1, '上行中分歧': 2,
                          '方向分化': 3, '走势承压': 4, '连续走弱': 4}.get(stage, 0))
        rows.append(row)
    return {key: deepcopy(source[key]) for key in ('track_id', 'name', 'started_date', 'method')} | {'path': rows}


# Match the T0 market convention: red gains and green losses, with lighter
# shades for smaller moves. Neutral zero and unavailable data remain distinct.
_TEMP_BAND_COLORS = (
    ('≤−3%', '#07C160'),
    ('−3~−1%', '#6BD9A2'),
    ('−1~0%', '#B5EDCF'),
    ('0%', '#F7F7F8'),
    ('0~1%', '#F8C9C3'),
    ('1~3%', '#F19A8D'),
    ('≥3%', '#E73922'),
    ('缺数据', '#B9BAC8'),
)


def _temperature_band_pieces():
    """Ordered signed-return bands for the matrix, with a separate gap band."""
    pieces = [
        {'value': band, 'label': label, 'color': color}
        for band, (label, color) in zip(range(-3, 4), _TEMP_BAND_COLORS[:7])
    ]
    pieces.append({'value': -4, 'label': _TEMP_BAND_COLORS[7][0],
                   'color': _TEMP_BAND_COLORS[7][1]})
    return pieces


def _temperature_scale_html():
    cells = ''.join(
        f'<span><i style="background:{color}"></i>{label}</span>'
        for label, color in _TEMP_BAND_COLORS
    )
    return f'<div class="trend-temperature-scale" aria-label="涨跌色阶（红涨绿跌，近白为零，灰色缺失）">{cells}</div>'


def _display_context_view(display_context, tracks, target_date):
    """Build an immutable display-only projection of the dated context.

    Context is supplied by the report assembler after date/source checks.  It
    never changes the evidence roster or any frozen research record.
    """
    if not display_context:
        return None
    focus = display_context.get('focus_track')
    focus_view = project_chart_track(focus) if focus and focus.get('path') else None
    current = display_context.get('current') or {}
    current_date = current.get('date', target_date)
    focus_name = current.get('primary_mainline') or (focus_view or {}).get('name') or ''
    exact = next((t for t in tracks if t.get('name') == focus_name), None)
    return {
        'target_date': display_context.get('target_date', target_date),
        'source_hash': display_context.get('source_hash'),
        'focus_track': focus_view,
        'focus_name': focus_name,
        'current': deepcopy(current),
        'stage_mainline': deepcopy(display_context.get('stage_mainline') or {}),
        'current_date': current_date,
        'trade_dates': deepcopy(display_context.get('trade_dates') or []),
        'exact_track_id': exact.get('track_id') if exact else None,
    }


def _target_gap_summary(tracks, target_date):
    known, missing = [], []
    for track in tracks:
        row = next((r for r in track['path'] if r.get('date') == target_date), None)
        if row and row.get('change_pct') is not None:
            known.append(track['name'])
        else:
            reason = ('固定成员的当日涨跌资料不齐' if '固定成员' in track['method']
                      else '同代码指数缺少当日涨跌记录')
            missing.append({'name': track['name'], 'reason': reason,
                            'original_reason': (row or {}).get('reason')})
    return {'target_date': target_date, 'known_count': len(known),
            'missing_count': len(missing), 'known': known, 'missing': missing}


_TREND_READING_TERMS = (
    ('下调A', '下调上行判断'), ('A保留', '上行判断保留'), ('A获', '上行判断获'),
    ('A未', '上行判断未'), ('B获支持', '转弱判断获支持'), ('保留B/C', '保留其他走势解释'),
)


def _trend_reading_text(text):
    for token, label in _TREND_READING_TERMS:
        text = text.replace(token, label)
    return text


def _trend_fact_scope(track, row):
    if row['date'] < track['started_date']:
        return '观察前历史背景：只用于理解此前走势，不计观察后的续证，也不是事前预测。'
    if row['date'] == track['started_date']:
        return '首次记录：此前历史背景不能算作已验证一次；观察后的续证从下一交易日开始。'
    return '观察后复核：按截至所选日期的滚动5日事实阅读，不使用之后的数据。'


def _trend_fact_number(value, unit='%'):
    return '事实不足' if value is None else f'{value:+.2f}{unit}'


def _trend_fact_breadth(value):
    return '事实不足' if value is None else f'{value * 100:.1f}%'


def leader_board_cache_root():
    """概念指数日行的本地缓存；只存数据源原始行，不存任何判断。"""
    return Path(__file__).resolve().parents[1] / 'cache' / 'ths_daily'


def collect_leader_board(target_date, *, window=LEADER_WINDOW, limit=LEADER_LIMIT, universe='concept',
                         cache_root=None, date_fetcher=None, rows_fetcher=None, index_map=None):
    """取目标日之前最近 window 个交易日同一口径板块指数的当日涨跌，生成冷暖方格数据。

    universe: 'concept' 为同花顺A股概念指数，'industry' 为同花顺A股行业指数。
    只做当日排名并集与原始涨跌回填；任一环节取不到就返回 {}，页面回退到观察板块冷暖格。
    """
    from market_data.tushare_market_activity_service import (
        fetch_tushare_open_trade_dates, fetch_tushare_ths_daily, fetch_tushare_ths_index_map,
    )
    index_type, prefixes = LEADER_UNIVERSES.get(universe) or LEADER_UNIVERSES['concept']
    cache_root = Path(cache_root) if cache_root else leader_board_cache_root()
    date_fetcher = date_fetcher or fetch_tushare_open_trade_dates
    rows_fetcher = rows_fetcher or fetch_tushare_ths_daily
    end = str(target_date)
    if not _canonical_date(end):
        return {}
    try:
        days = date_fetcher((date.fromisoformat(end) - timedelta(days=window * 2 + 20)).isoformat(), end)
    except Exception:
        days = []
    days = [day for day in (days or []) if day <= end][-window:]
    if not days:
        return {}
    if index_map is None:
        index_map = fetch_tushare_ths_index_map(index_type=index_type)
    series = {}
    for day in days:
        cache_file = cache_root / f'{day}.json'
        raw_rows = []
        if cache_file.exists():
            cached = json.loads(cache_file.read_text(encoding='utf-8'))
            raw_rows = cached if cached else []
        if not raw_rows:
            raw_rows = rows_fetcher(day) or []
            if raw_rows:  # 空结果不落盘，避免当天数据尚未发布时把空格子固化
                cache_root.mkdir(parents=True, exist_ok=True)
                cache_file.write_text(json.dumps(raw_rows, ensure_ascii=False) + '\n', encoding='utf-8')
        rows = []
        for raw in raw_rows:
            code = str((raw or {}).get('ts_code') or '').strip().upper()
            meta = index_map.get(code) or {}
            if (not code or code[:3] not in prefixes
                    or str(meta.get('type') or '').strip().upper() != index_type
                    or str(meta.get('exchange') or '').strip().upper() != 'A'):
                continue
            try:
                change = float(raw.get('pct_change'))
            except (TypeError, ValueError):
                continue
            rows.append((str((index_map.get(code) or {}).get('name') or '').strip(), code, round(change, 4)))
        if rows:
            series[day] = rows
    return leader_board(series, target_date=end, window=window, limit=limit) if series else {}


def _heat_view(tracks, leader_board):
    """冷暖方格的行：有本月前三名单时用名单并集，否则沿用观察板块。"""
    if not leader_board or not leader_board.get('rows'):
        return {'source': 'tracks', 'dates': sorted({row['date'] for track in tracks for row in track['path']}),
                'rows': [{'name': track['name'], 'track_id': track['track_id'],
                          'temp': [row.get('temperature') for row in track['path']],
                          'pct': [row.get('change_pct') for row in track['path']],
                          'selected': [False] * len(track['path']), 'path': track['path']}
                         for track in tracks]}
    by_name = {track['name']: track['track_id'] for track in tracks}
    return {'source': 'leader_board', 'dates': list(leader_board['dates']),
            'rows': [{'name': row['name'], 'track_id': by_name.get(row['name']),
                      'temp': row['temp'], 'pct': row['pct'], 'selected': row['selected']}
                     for row in leader_board['rows']]}


def _leader_board_details(leader_board):
    """本月每日前三的名单与全部原始数值，放在同一段的折叠区，便于无图核对。"""
    esc = lambda value: html.escape(str(value), quote=True)
    daily = ''.join(
        f'<li><strong>{esc(item["date"])}</strong>：' + '；'.join(
            f'{leader["rank"]}. {esc(leader["name"])} {leader["change_pct"]:+.2f}%'
            for leader in item['leaders']) + '</li>' for item in leader_board['daily_top'])
    table = ''.join(
        '<tr><td>' + esc(row['name']) + f'<small>{esc(row["code"])} · 入选{row["selected_count"]}次</small></td>' +
        ''.join(f'<td>{"—" if pct is None else f"{pct:+.2f}%"}{"（入选）" if selected else ""}</td>'
                for pct, selected in zip(row['pct'], row['selected'])) + '</tr>'
        for row in leader_board['rows'])
    dates = leader_board['dates']
    return (f'<h4>最近{len(leader_board["dates"])}个交易日每日前三名单</h4>'
            '<ol class="monthly-leader-daily">' + daily + '</ol>'
            '<div class="trend-roster-wrap"><table class="trend-roster"><caption>各板块逐日涨跌与入选标记</caption>'
            '<thead><tr><th>板块</th>' + ''.join(f'<th>{esc(day[5:])}</th>' for day in dates) + '</tr></thead>'
            f'<tbody>{table}</tbody></table></div>')


def render_trend_fragment(evidence, record, *, selected_track_id=None, selected_date=None, display_context=None,
                          leader_board=None):
    """Read-only dated facts; rolling reviews never replace original daily hypotheses.

    Selection only changes the displayed node. All dates remain in the closed
    facts table, including historical context before the observation started.
    """
    if not validate_trend_evidence(evidence, record):
        raise ValueError('趋势事实与原观察不符，停止生成')
    if not evidence['tracks']:
        return '<div class="sector-trend"><h3>整段趋势跟踪</h3><p>尚无已建立的板块观察。</p></div>'
    esc = lambda value: html.escape(str(value), quote=True)
    number = _trend_fact_number
    tracks = [project_chart_track(source) for source in evidence['tracks']]
    context = _display_context_view(display_context, tracks, evidence['target_date'])
    focus = (context or {}).get('focus_track')
    focus_name = (context or {}).get('focus_name') or ''
    choices = tracks + ([focus] if focus and all(t['track_id'] != focus['track_id'] for t in tracks) else [])
    latest = max(tracks, key=lambda t: (max((r['date'] for r in t['path']
                 if r.get('level') is not None), default=''), t['started_date'], t['track_id']))
    default = focus or next((t for t in tracks if t['name'] == focus_name), None)
    explicit = next((t for t in choices if t['track_id'] == selected_track_id), None)
    unavailable_focus = bool(focus_name and not default and not explicit)
    selected_track = explicit or default or latest
    selected_row = next((r for r in selected_track['path'] if r['date'] == selected_date), selected_track['path'][-1])
    selected_id = '' if unavailable_focus else selected_track['track_id']
    group_method = '' if unavailable_focus else selected_track['method']
    gaps = _target_gap_summary(tracks, evidence['target_date'])
    focus_note = (f'当前日报主攻：{focus_name}；仅为报告当日主攻，不等于已确认阶段主线。' +
                  ('缺少同名可比路径，事实不足；可主动选择其他观察板块。' if unavailable_focus else
                   f'当前自主选择观察：{selected_track["name"]}。' if explicit and explicit is not default else
                   '走势使用同名方向与中证全指对照。')
                  if focus_name else f'当前显示观察：{selected_track["name"]}；优先最新有效路径，不代表报告主线。')
    metrics = (
        ('change_pct', '当日涨跌', '%'), ('five_day_pct', '近5日涨跌', '%'),
        ('five_day_excess_pp', '近5日强于全A', '个百分点'),
        ('breadth', '当日上涨面', '%'), ('five_day_breadth', '近5日平均上涨面', '%'),
        ('drawdown_pct', '距窗口此前高点回撤', '%'),
    )
    heat = _heat_view(tracks, leader_board)
    view = {'version': 'trend_chart_review.v2', 'target_date': evidence['target_date'],
            'benchmark': evidence['rules'].get('benchmark_code'),
            'artifact_hash': evidence.get('artifact_hash'), 'tracks': tracks,
            'reading_terms': _TREND_READING_TERMS, 'display_context': context,
            'focus_track': focus, 'selected_track_id': selected_id,
            'selected_date': selected_row['date'], 'target_gaps': gaps,
            'focus_note': focus_note, 'heat': heat,
            'trade_dates': (context or {}).get('trade_dates') or sorted({r['date'] for t in tracks for r in t['path']})}
    encoded = json.dumps(view, ensure_ascii=False, allow_nan=False).replace('<', '\\u003c')
    out = [
        '<div class="sector-trend"><h3>整段趋势跟踪 · 月度对比</h3>',
        f'<p class="hypothesis-origin">{esc(tracks[0]["path"][0]["date"])}—{esc(evidence["target_date"])} · {len(tracks)}个观察样本 · '
        f'{esc(evidence["retrieved_at"][:10])}取得；观察起点前为后选背景，不计事前预测。</p>',
        '<p class="trend-lead">首次冒头就跟踪，后续事实决定保留还是降级。主线是逐步验证的结果；颜色不代表买点。</p>',
        '<p class="trend-fallback">即使图表未加载，也可阅读当前日期的判断依据；全部原始日期保留在下方完整事实表。</p>',
        f'<p id="trend-focus-note" class="trend-focus-note">{esc(focus_note)}</p>',
        '<div class="trend-controls"><label for="sector-trend-group">比较口径</label><select id="sector-trend-group" aria-label="比较口径">' +
        ('<option value="" selected>主攻可比事实不足</option>' if unavailable_focus else '') +
        ''.join(f'<option value="{esc(method)}"{" selected" if method == group_method else ""}>{esc(method)}</option>' for method in dict.fromkeys(t['method'] for t in choices)) + '</select></div>',
        '<div class="trend-chart-card"><div id="sector-trend-comparison" class="trend-echart" role="img" aria-label="观察板块月度相对强弱比较图"></div></div>',
        '<p class="trend-chart-caption">相对全A累计差值（百分点）· 点图例显隐 · 拖动缩放</p>',
        (f'<h4>最近{len(heat["dates"])}个交易日冷暖方格 · 每日涨幅前{leader_board["limit"]}'
         f'（{len(heat["rows"])}个板块）</h4>'
         if leader_board else
         f'<h4>观察板块冷暖方格 · 全部{len(tracks)}个观察板块（点击联动判断）</h4>'),
        (f'<p class="trend-chart-caption">行是最近{len(heat["dates"])}个交易日（窗口{leader_board["window"]}日）每日涨幅前'
         f'{leader_board["limit"]}的板块并集（{heat["dates"][0]} 至 {heat["dates"][-1]}），列是这些交易日；'
         '黑框为当日入选前三，格子是该板块当日真实涨跌。当日普跌时前三即跌幅最小三名，不当作上涨。'
         '颜色不代表情绪冰点或买点。</p>' if leader_board else
         '<p class="trend-chart-caption">每格一天：红色为上涨、绿色为下跌，深浅区分幅度；近白为零涨跌，灰色为缺数据。'
         '这里只看真实当日涨跌，5日资料不全不影响已有日值；颜色不代表情绪冰点或买点。</p>'),
        _temperature_scale_html(),
        f'<p class="trend-gap-summary">{esc(evidence["target_date"])}：{gaps["known_count"]}个有数，{gaps["missing_count"]}个缺数。</p>',
        ('<details class="trend-gap-summary"><summary>当日缺口名单与原因</summary><ul>' +
         ''.join(f'<li>{esc(g["name"])}：{esc(_trend_reading_text(g["reason"]))}</li>' for g in gaps['missing']) + '</ul></details>' if gaps['missing'] else ''),
        '<div class="trend-controls"><label for="trend-matrix-scale">方格大小</label><select id="trend-matrix-scale"><option value="18">紧密</option><option value="23">放大</option><option value="29">大字</option></select></div>',
        '<div class="trend-heat-scroll"><div id="sector-trend-revisions" class="trend-echart" role="img" aria-label="全部观察板块的逐日价格冷暖方格"></div></div>',
        '<p id="trend-heat-note" class="trend-chart-caption" aria-live="polite"></p>',
        ('<p class="trend-chart-caption">全部板块行完整展开 · 窄屏可横向拖动查看整月 · '
         + ('点击方格：属于观察名单的板块联动下方判断，其他板块只显示当日涨跌</p>' if leader_board else
            '点击方格同步板块与日期 · 不同口径不做混合排名</p>')),
        '<h4>这次为什么改变判断</h4>',
        '<p class="trend-chart-caption">这里核对滚动5日走势，不是上方原单日预期的兑现核对；两套结论不合并。切换板块或日期只读取已冻结节点，不重算、不写回判断。</p>',
        '<div class="trend-controls"><label for="sector-trend-selector">查看板块</label><select id="sector-trend-selector" aria-label="选择板块">',
    ]
    if unavailable_focus:
        out.append(f'<option value="" selected>{esc(focus_name)} · 可比事实不足</option>')
    for track in choices:
        out.append(f'<option value="{esc(track["track_id"])}"{" selected" if track["track_id"] == selected_id else ""}>{esc(track["name"])}</option>')
    out += [
        '</select><label for="trend-date-selector">复核日期</label><select id="trend-date-selector" aria-label="选择复核日期">' +
        ''.join(f'<option value="{r["date"]}"{" selected" if r is selected_row else ""}>{r["date"]} · {"历史背景" if r["background"] else "首次记录" if r["date"] == selected_track["started_date"] else "观察后复核"}</option>'
                for r in selected_track['path']) + '</select></div>',
        f'<section id="trend-fact-panel" data-trend-track="{esc(selected_id)}" data-trend-date="{selected_row["date"]}" aria-live="polite"{" hidden" if unavailable_focus else ""}>',
        f'<h4 id="trend-fact-title">{esc(selected_track["name"])} · {selected_row["date"]}</h4>',
        f'<p id="trend-fact-method">{esc(selected_track["method"])} · {selected_track["started_date"]}首次记录</p>',
        f'<p id="trend-fact-scope">{_trend_fact_scope(selected_track, selected_row)}</p>',
        '<div class="trend-fact-transition"><p>上一交易日判断（首节点无前值）<br>'
        f'<strong id="trend-fact-before">{esc(selected_row["before"])}</strong></p><span aria-hidden="true">→</span>'
        f'<p>本日滚动5日判断<br><strong id="trend-fact-judgement">{esc(selected_row["judgement"])}</strong></p></div>',
        '<dl class="trend-fact-metrics">' + ''.join(
            f'<div><dt>{label}</dt><dd id="trend-fact-{key}">{_trend_fact_breadth(selected_row[key]) if key in ("breadth", "five_day_breadth") else number(selected_row[key], unit)}</dd></div>'
            for key, label, unit in metrics) + '</dl>',
        f'<p><strong>本次依据：</strong><span id="trend-fact-reason">{esc(_trend_reading_text(selected_row["reason"]))}</span></p>',
        '<p class="trend-chart-caption">依据中的上行、转弱与分化解释仅属于滚动走势研究，不对应原单日假设结论。相同判断表示本日继续保留，并非每天都要改判。近5日强于全A为收益差，负值表示落后；上涨面为上涨成员占比，回撤以本窗口此前最高收盘为基准。</p>',
        f'<p><strong>下一次看什么：</strong><span id="trend-fact-next">{esc(_trend_reading_text(selected_row["next_test"]))}</span></p></section>',
        '<div class="trend-detail-cards">' + ''.join(
            f'<article class="trend-chart-card"><h4><span data-trend-name></span> · {title}</h4>'
            f'<p class="trend-chart-caption">{purpose}</p><div id="sector-trend-{key}" class="trend-echart" role="img" aria-label="{title}"></div></article>'
            for key, title, purpose in (
                ('price', '走势对照', '实线：所选板块；虚线：中证全指。首日收盘均为100，看谁走得更强。'),
                ('drawdown', '回撤深度', '只有一条线：距离本窗口此前最高收盘跌了多少。0%表示回到该高点。'),
                ('breadth', '上涨面', '实线：当天上涨成员比例；虚线：近5日均值。看上涨是否扩散。'))) + '</div>',
        '<p id="sector-trend-current" class="hypothesis-current" aria-live="polite"></p>',
        '<p class="trend-chart-caption">三角：回踩观察；圆点：价格与扩散恢复；空心圆：仅价格修复。标在当天收盘，不能倒推盘中买点。</p>',
        '<p class="trend-chart-caption">可参与还需原计划、处理窗口、承接、认错线与最大损失；本图不新增买入资格。</p>',
        '<details id="trend-full-facts" class="trend-detail"><summary>完整事实表与原跟踪明细（全部板块、全部日期）</summary>',
        '<p>下表保留各日冻结事实及原始判断文字；观察前仅为历史背景。宽表可横向滚动，各指标独立列示。</p>',
        '<div class="trend-roster-wrap"><table class="trend-roster"><caption>截至报告日的跟踪进度</caption><thead><tr><th>板块与首次记录</th><th>观察后</th><th>阶段</th><th>当前修正</th></tr></thead><tbody>' +
        ''.join(f'<tr><td>{esc(t["name"])}<small>{esc(t["started_date"])}</small></td>'
                f'<td>{t["path"][-1]["followup_days"]}日</td><td>{esc(t["path"][-1]["role"])}</td>'
                f'<td>{esc(t["path"][-1]["progress"])}</td></tr>' for t in tracks) + '</tbody></table></div>',
    ]
    fact_columns = (
        ('change_pct', '当日涨跌（%）', '%'), ('cumulative_pct', '窗口累计（%）', '%'),
        ('since_observation_pct', '观察后累计（%）', '%'), ('excess_pp', '窗口强于全A（百分点）', '个百分点'),
        ('drawdown_pct', '距窗口高点回撤（%）', '%'), ('five_day_pct', '近5日涨跌（%）', '%'),
        ('five_day_excess_pp', '近5日强于全A（百分点）', '个百分点'),
        ('breadth', '当日上涨面（%）', '%'), ('five_day_breadth', '近5日平均上涨面（%）', '%'),
    )
    for source in evidence['tracks']:
        out.append(f'<h4>{esc(source["name"])}</h4><p>{esc(source["method"])} · {source["started_date"]}首次记录</p>'
                   '<div class="trend-summary"><table><thead><tr><th>日期</th><th>日期性质</th>' +
                   ''.join(f'<th>{label}</th>' for _, label, _ in fact_columns) +
                   '<th>上一节点判断</th><th>本日判断</th><th>原始依据</th><th>下一检验</th></tr></thead><tbody>')
        for row in source['path']:
            stage = '历史背景' if row['background'] else '首次记录' if row['date'] == source['started_date'] else '观察后复核'
            out.append(f'<tr data-trend-track="{esc(source["track_id"])}" data-trend-date="{row["date"]}">'
                       f'<td>{row["date"]}</td><td>{stage}</td>' + ''.join(
                           f'<td data-trend-metric="{key}">{_trend_fact_breadth(row[key]) if key in ("breadth", "five_day_breadth") else "不适用（历史背景）" if key == "since_observation_pct" and row["background"] else number(row[key], unit)}</td>'
                           for key, _, unit in fact_columns) +
                       f'<td>{esc(row["before"])}</td><td>{esc(row["judgement"])}</td>'
                       f'<td>{esc(row["reason"])}</td><td>{esc(row["next_test"])}</td></tr>')
        out.append('</tbody></table></div>')
    if leader_board:
        out.append(_leader_board_details(leader_board))
    out.append('</details><details class="hypothesis-rules"><summary>趋势口径与边界</summary>'
               '<p>相对强弱、回撤、上涨面均按目标日前已存在的节点计算；缺日不补零。观察篮子只能回答这些板块之间谁更强，不能回答全市场主线。图上标记不替代时间窗口、承接、认错线和计划损失。</p>'
               '<p>回踩观察：此前与当日5日涨幅、相对全A均为正，而当日下跌并低于此前最高收盘。此后价格上涨、回撤缩小，且上涨面过半并扩大才记价格与扩散恢复；缺成员数据只记仅价格修复。相对优势消失或缺事实则结束本段观察，不事后挪回低点。所有标记为未校准的收盘研究规则。</p>'
               '<p>行业为固定成员每日等权研究组合，指数沿用原代码，分组比较。首日收盘归一100；累计收益分别连乘，相对全A为累计收益之差；回撤为距窗口此前最高收盘的跌幅。观察前路径为背景；强势连续日数只计5日价格与相对表现均为正，不等于胜率。</p>'
               '<p>冷暖格按当日涨跌幅分档：≤−3%、(−3%,−1%]、(−1%,0%)、0%、(0%,1%)、[1%,3%)、≥3%；缺失独立灰格。'
               '红色为上涨、绿色为下跌、近白为零涨跌；阈值只是展示刻度，未校准为市场情绪。线条只平滑连接已有数值，缺口不连线、不补零；多板块曲线颜色仅区分身份，不代表涨跌。</p>'
               '<p>进度从首次记录开始：再次上涨且跑赢全A记再次走强，连续两次续证且5日走势同强才记延续增强；长段仍弱时保留反弹提示。主线、轮动与买价分别核验，不用事后名称批准早期交易。当前每日仅从上涨榜前三新增观察，旧项保留，不保证覆盖全部热点。</p>'
               '<p>主线候选至少观察10个后续交易日，且近5日价格、相对全A与窗口累计收益为正；上涨面缺失或不过半时另标扩散待确认。这是观察名单内的研究条件，未校准，不代表全市场主线或买入时点。</p>'
               f'<p>事实截至{esc(evidence["target_date"])}；规则版本{esc(RULES["version"])}；实际取得于{esc(evidence["retrieved_at"])}。</p></details>')
    out.append(f'<script type="application/json" id="sector-trend-view">{encoded}</script>')
    bands = json.dumps(_temperature_band_pieces(), ensure_ascii=False).replace('<', '\\u003c')
    out.append(f'<script>const TEMPERATURE_BANDS={bands};</script>')
    script = (Path(__file__).resolve().parents[1] / 'templates' / 'sector_trend_charts.js').read_text(encoding='utf-8')
    out.append('<script>\n' + script + '</script></div>')
    return ''.join(out)


def public_trend_evidence(evidence):
    """Return the small read-only projection embedded in HTML.

    Raw member rows remain in the dated sidecar for audit and replay; the
    compact page only needs the validated path and its provenance hash.
    """
    return {key: deepcopy(evidence[key]) for key in
            ('schema_version', 'rules', 'target_date', 'record_hash', 'retrieved_at',
             'source', 'calendar_start', 'tracks', 'artifact_hash')}




def leader_board(series_by_date, *, target_date, window=LEADER_WINDOW, limit=LEADER_LIMIT):
    """最近 window 个交易日每日涨幅前 N 的板块并集，作为冷暖方格的行。

    series_by_date: {日期: [(名称, 代码, 当日涨跌幅), ...]}
    只做当日排名的并集与原始涨跌回填，不产生续证结论，也不改任何观察记录。
    """
    dates = sorted(day for day in series_by_date if day <= target_date)[-window:]
    if not dates:
        return {}
    daily_top, identity = [], {}
    for day in dates:
        ranked = sorted((row for row in series_by_date[day] if row[2] is not None),
                        key=lambda row: (-row[2], row[1]))
        leaders = ranked[:limit]
        daily_top.append({'date': day, 'leaders': [
            {'name': name, 'code': code, 'change_pct': round(change, 4), 'rank': rank}
            for rank, (name, code, change) in enumerate(leaders, start=1)]})
        for name, code, _ in leaders:
            identity.setdefault(code, name)
    by_day = {day: {code: change for _, code, change in rows}
              for day, rows in series_by_date.items()}
    names = {code: by_day[dates[-1]].get(code) for code in identity}
    counts = {code: sum(1 for item in daily_top
                        if any(leader['code'] == code for leader in item['leaders']))
              for code in identity}
    target_changes = {code: (by_day.get(target_date) or {}).get(code) for code in identity}
    ordered = sorted(identity, key=lambda code: (
        -counts[code], -(target_changes[code] if target_changes[code] is not None else -1e9), names[code] or ''))
    rows = [{'name': identity[code], 'code': code,
             'selected_count': counts[code],
             'pct': [None if by_day[day].get(code) is None else round(by_day[day][code], 4) for day in dates],
             'temp': [price_temperature(by_day[day].get(code)) for day in dates],
             'selected': [any(leader['code'] == code for leader in item['leaders']) for item in daily_top]}
            for code in ordered]
    return {'schema_version': 'sector_leader_heat.v2', 'window': window,
            'target_date': target_date, 'limit': limit, 'dates': dates,
            'rows': rows, 'daily_top': daily_top,
            'rule': (f'取目标日之前最近{window}个交易日，每日按当日涨跌幅取前{limit}名；'
                     '行为窗口内曾入选的板块并集，格子为该板块当日涨跌。'
                     '当日普跌时前三即跌幅最小三名，如实显示，不当作上涨。')}
