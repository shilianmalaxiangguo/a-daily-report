"""Restore dated sector visuals without executing the historical trading report."""
from __future__ import annotations

import hashlib
import html
import json
import math
from copy import deepcopy
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup

from report.hypothesis_revision import (
    HYPOTHESIS_STYLE, _render_observation_flow, _observation_flow, validate_hypothesis_record,
)


def evidence_hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str,
                                    allow_nan=False).encode()).hexdigest()


def _check_chart_snapshot(source, data, target_date):
    """Compare displayed numerical groups, not just the sector input hash."""
    node = source.select_one('#bear-chart-payload')
    charts = json.loads(node.get_text()) if node else {}
    revised_top50 = data.get('reading_top50')
    revised_top50_chart = charts.get('market_turnover_top50_trend', {}).get('schema') == 'sector_top50.v1'
    if revised_top50 is not None:
        from report.sector_top50 import validate_top50_series
        validate_top50_series(revised_top50, target_date)
    if revised_top50_chart and (revised_top50 is None or
            charts['market_turnover_top50_trend'].get('items') != revised_top50['items']):
        raise ValueError('成交占比修订图表与选定快照矛盾')
    revised = data.get('reading_new_high')
    revised_chart = charts.get('new_high_share_trend', {}).get('schema') == 'sector_new_high.v1'
    if revised is not None:
        from report.sector_new_high import validate_new_high_series
        validate_new_high_series(revised, target_date)
    if revised_chart:
        if revised is None or charts['new_high_share_trend'].get('items') != revised['items']:
            raise ValueError('创新高修订图表与选定快照矛盾')
    def equal(left, right):
        a, b = _number(left), _number(right)
        return a is None or b is None or abs(a - b) < .011
    def check(left, right, fields):
        if any(not equal(left.get(a), right.get(b)) for a, b in fields):
            raise ValueError('历史图表数值与选定快照矛盾，不能混合展示')
    for chart, key, fields in (
        ('t0_market_breadth', 'market_stats', (('up_count', 'up_count'), ('down_count', 'down_count'))),
        ('market_turnover_top50_trend', 'turnover_data', (('total_turnover', 'total_turnover_yi'),)),
        ('new_high_share_trend', 'new_high_feedback', (('new_high_count', 'new_high_count'), ('new_high_share_pct', 'all_a_share_pct'))),
    ):
        if chart == 'new_high_share_trend' and revised_chart or chart == 'market_turnover_top50_trend' and revised_top50_chart:
            continue
        row = next((r for r in charts.get(chart, {}).get('items', []) if r.get('date') == target_date), {})
        check(row, data.get(key) or {}, fields)
    ranks = {r.get('code'): r for r in data.get('turnover_rank') or []}
    for row in charts.get('turnover_top30', {}).get('items', []):
        raw = ranks.get(row.get('code'))
        if raw is None and ranks:
            raise ValueError('历史成交图与选定快照名单不同')
        check(row, raw or {}, (('turnover', 'turnover'), ('change_pct', 'change_pct')))
    high = {r.get('date') or r.get('trade_date'): r for r in (data.get('new_high_feedback') or {}).get('trend_rows', [])}
    for row in ([] if revised_chart else charts.get('new_high_share_trend', {}).get('items', [])):
        check(row, high.get(row.get('date')) or {}, (('new_high_count', 'new_high_count'), ('new_high_share_pct', 'all_a_share_pct')))
    shares = {r.get('trade_date'): r for r in (data.get('top50_turnover_share_series') or {}).get('rows', [])}
    for row in ([] if revised_top50_chart else charts.get('market_turnover_top50_trend', {}).get('items', [])):
        check(row, shares.get(row.get('date')) or {}, (('top50_share_pct', 'share_pct'), ('total_turnover', 'market_amount_yi')))
    for side, key in (('buy', 'lhb_net_buy_top10'), ('sell', 'lhb_net_sell_top10')):
        raw = {r['code']: r for r in data.get(key) or []}
        for row in charts.get('lhb_net_flow', {}).get('items', []):
            if row.get('side') == side:
                check(row, raw.get(row.get('code')) or {}, (('amount', 'net_buy_amount_yi'), ('change_pct', 'change_pct')))
    if data.get('cffex_index_futures_position_evidence'):
        from report.sector_snapshot_charts import snapshot_chart_payload
        native = snapshot_chart_payload({'cffex_index_futures_position_evidence': data['cffex_index_futures_position_evidence']}, target_date)
        rows = {r['date']: r for r in native.get('cffex_position_trend', {}).get('items', [])}
        for row in charts.get('cffex_position_trend', {}).get('items', []):
            check(row, rows.get(row['date']) or {}, tuple((k, k) for k in (
                'member_net_short_notional_yi', 'member_net_short_change', 'top20_cross_section_net_short', 'top20_cross_section_change')))


def _check_original_trend(source, record, view, result):
    from report.sector_trend_tracking import project_chart_track, validate_trend_evidence
    node = source.select_one('#sector-trend-evidence')
    if node is None:
        raise ValueError('历史趋势缺少原始凭据投影')
    evidence = json.loads(node.get_text())
    root = Path(__file__).resolve().parents[2] / 'data/hypothesis-revision'
    path = root / 'trends' / (record['target_date'] + '.json')
    if path.is_file():
        base = json.loads(path.read_text(encoding='utf-8'))
        if base.get('artifact_hash') != evidence.get('artifact_hash') or not validate_trend_evidence(base, record):
            raise ValueError('历史趋势凭据与原日期记录不符')
    else:
        base = None
    supplement = source.select_one('#sector-chart-facts')
    public_supplement = json.loads(supplement.get_text()) if supplement else None
    full = None
    if public_supplement:
        digest = public_supplement.get('artifact_hash') or ''
        if len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
            raise ValueError('历史补查指纹格式不符')
        path = root / 'chart-facts' / record['target_date'] / (digest + '.json')
        if path.is_file() and base is not None:
            from report.sector_chart_facts import validate_sector_chart_facts
            full = json.loads(path.read_text(encoding='utf-8'))
            if not validate_sector_chart_facts(full, record, base):
                raise ValueError('历史补查事实指纹不符')
    chosen = full['trend'] if full else base or evidence
    wanted = [project_chart_track(track) for track in chosen['tracks']]
    if view.get('tracks') != wanted or view.get('artifact_hash') != chosen.get('artifact_hash'):
        raise ValueError('历史趋势数值与对应凭据投影不同')
    if full is not None:
        focus = project_chart_track(full['focus_track']) if full.get('focus_track') else None
        if view.get('focus_track') != focus:
            raise ValueError('历史主攻路径与对应补查凭据投影不同')
    elif view.get('focus_track') != (view.get('display_context') or {}).get('focus_track'):
        raise ValueError('历史主攻路径与原页上下文不符')
    if view.get('heat'):
        _check_original_heat(source, view)
        result['heat_provenance'] = {
            'artifact_hash': evidence_hash(view['heat']),
            'source': '原板块页冷暖数值与完整事实表交叉核对；独立于原趋势指纹',
            'verification_note': '原表仅保留两位小数；未据此补造上游查询时间',
        }
    result['trend_provenance'] = {key: evidence.get(key) for key in
        ('target_date', 'record_hash', 'retrieved_at', 'source', 'artifact_hash')}
    result['trend_provenance']['verification_note'] = (
        '与本地原始趋势凭据核对' if base is not None else '仅保留原页投影；本地原始趋势凭据缺失')
    result['chart_provenance'] = public_supplement


def _check_original_heat(source, view):
    """The daily-leader matrix has its own source, not the trend fingerprint."""
    heat = view['heat']
    if heat.get('source') == 'tracks':
        expected = _path_heat(view)
        for field in ('dates', 'rows'):
            actual = heat.get(field)
            if field == 'rows':
                fields = ('name', 'track_id', 'pct', 'temp', 'selected')
                actual = [{key: row.get(key) for key in fields} for row in actual or []]
            if actual != expected[field]:
                raise ValueError('冷暖矩阵与原板块路径不符')
        return
    table = next((table for table in source.select('.sector-trend table')
                  if table.caption and table.caption.get_text(strip=True) == '各板块逐日涨跌与入选标记'), None)
    if table is None:
        raise ValueError('历史冷暖矩阵缺少可核对的完整事实表')
    headers = [cell.get_text(strip=True) for cell in table.select('thead th')][1:]
    rows = table.select('tbody tr')
    if headers != [day[5:] for day in heat['dates']] or len(rows) != len(heat['rows']):
        raise ValueError('历史冷暖矩阵与原事实表的行列不符')
    by_name = {track['name']: track['track_id'] for track in view['tracks']}
    for original, row in zip(rows, heat['rows']):
        cells = original.find_all('td', recursive=False)
        name = ''.join(str(part) for part in cells[0].find_all(string=True, recursive=False)).strip()
        if (name != row['name'] or len(cells) != len(heat['dates']) + 1
                or row.get('track_id') != by_name.get(name)):
            raise ValueError('历史冷暖板块名称或关联路径与原表不符')
        for cell, value, selected in zip(cells[1:], row['pct'], row['selected']):
            text = cell.get_text(strip=True)
            number = _number(text.removesuffix('（入选）').removesuffix('%'))
            if ((number is None) != (value is None) or number is not None and abs(number - value) > .0051
                    or ('（入选）' in text) != selected):
                raise ValueError('历史冷暖数值或入选记录与原事实表不符')


def _path_heat(view):
    from report.sector_trend_tracking import price_temperature
    dates = sorted({row['date'] for track in view['tracks'] for row in track['path']})
    rows = []
    for track in view['tracks']:
        by_day = {row['date']: row.get('change_pct') for row in track['path']}
        values = [by_day.get(day) for day in dates]
        rows.append({'name': track['name'], 'track_id': track['track_id'], 'pct': values,
                     'temp': [price_temperature(value) for value in values], 'selected': [False] * len(dates)})
    return {'source': 'tracks', 'dates': dates, 'rows': rows}


def historical_assets(source_html, snapshot, target_date):
    """Accept historical charts only when their frozen sector input matches."""
    if not source_html:
        return {}
    source = BeautifulSoup(source_html, 'html.parser')
    retained = source.select_one('#sector-retained-history')
    if retained:
        bundle = json.loads(retained.get_text())
        snapshot_matches = bundle.get('snapshot_hash') == evidence_hash(snapshot['data'])
        if not snapshot_matches and snapshot['data'].get('reading_new_high') is not None:
            from report.sector_new_high import validate_new_high_series
            validate_new_high_series(snapshot['data']['reading_new_high'], target_date)
            # A repair may add this one independently verified series. Every
            # other snapshot field must still match the original retained page.
            snapshot_matches = bundle.get('snapshot_hash') == evidence_hash(
                {k: v for k, v in snapshot['data'].items() if k != 'reading_new_high'})
        if not snapshot_matches and snapshot['data'].get('reading_member_history') is not None:
            from report.sector_market_relation import validate_member_history
            native = snapshot['data'].get('reading_sector_history') or {}
            if not native.get('trend'):
                raise ValueError('成员关系补查缺少原始板块事实')
            validate_member_history(snapshot['data']['reading_member_history'], native['trend'])
            original = {k: v for k, v in snapshot['data'].items() if k != 'reading_member_history'}
            snapshot_matches = bundle.get('snapshot_hash') == evidence_hash(original)
            if not snapshot_matches and original.get('reading_new_high') is not None:
                # Both repairs are independently validated; all other facts must match.
                original.pop('reading_new_high')
                snapshot_matches = bundle.get('snapshot_hash') == evidence_hash(original)
        if not snapshot_matches:
            # Separately validated additions (prices by explicit trade date, the frozen reading,
            # backtest and advice records). Every other retained fact must still match the page.
            # Import only validators for fields actually present in the
            # retained snapshot. This keeps historical compatibility checks
            # from loading unrelated retired strategy modules.
            validator_specs = {
                'reading_market_returns': ('report.market_returns', 'validate_market_returns'),
                'reading_interpretation': ('report.daily_interpretation', 'validate_interpretation'),
                'reading_backtest': ('report.daily_extras', 'validate_backtest'),
                'reading_decision_record': ('report.advice_ledger', 'validate_record'),
                'reading_decision_history': ('report.advice_ledger', 'validate_history'),
                'reading_small_cap_plan': ('report.small_cap_rotation', 'validate_plan'),
            }
            import importlib

            additions = {}
            present = []
            for key, (module_name, function_name) in validator_specs.items():
                if snapshot['data'].get(key) is None:
                    continue
                module = importlib.import_module(module_name)
                additions[key] = getattr(module, function_name)
                present.append(key)
            for key in present:
                additions[key](snapshot['data'][key], target_date)
            for dropped in (present, [key for key in present if key != 'reading_market_returns']):
                if dropped and not snapshot_matches:
                    snapshot_matches = bundle.get('snapshot_hash') == evidence_hash(
                        {k: v for k, v in snapshot['data'].items() if k not in dropped})
        if (bundle.get('target_date') != target_date or not snapshot_matches
                or bundle.get('artifact_hash') != evidence_hash({k: v for k, v in bundle.items() if k != 'artifact_hash'})):
            raise ValueError('留存图表与选定快照指纹不符')
        payload_node = source.select_one('#bear-chart-payload')
        if bundle.get('chart_hash') != evidence_hash(json.loads(payload_node.string) if payload_node else {}):
            raise ValueError('留存市场图表指纹不符')
        native = snapshot['data'].get('reading_sector_history')
        result = bundle.get('assets')
        if bundle.get('schema') == 'sector_reading_archive.v2' and 'assets' not in bundle:
            if native is None or bundle.get('assets_hash') != evidence_hash(native):
                raise ValueError('留存图表缺少对应的选定快照事实，不能换用其他来源')
            result = native
        if not isinstance(result, dict):
            raise ValueError('留存板块事实缺失')
        if native is not None:
            if (native.get('target_date') != target_date or native.get('source_sha256') !=
                    evidence_hash({k: v for k, v in native.items() if k != 'source_sha256'})):
                raise ValueError('选定快照的板块历史事实日期或指纹不符')
            if result != native:
                raise ValueError('留存板块事实与选定快照不同，不能混合展示')
        if result.get('trend'):
            numeric_trend_view(result['trend'], target_date)
        if result.get('flow'):
            validated_flow(result['flow'], target_date)
        if result.get('concept_flow'):
            from report.sector_concept_flow import validate_concept_flow
            validate_concept_flow(result['concept_flow'], target_date)
        if bundle.get('schema') == 'sector_reading_archive.v2':
            _check_reading_projections(source, result, snapshot['data'], target_date, bundle)
        _check_chart_snapshot(source, snapshot['data'], target_date)
        return result
    node = source.select_one('#sector-hypothesis-record')
    if node is None:
        return {}
    record = json.loads(node.get_text())
    data = (snapshot or {}).get('data') or {}
    digest = hashlib.sha256(json.dumps(
        {key: data.get(key) for key in ('sector_change_up', 'sector_change_down', 'wind_a_alternative')},
        ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()
    if (not validate_hypothesis_record(record) or record.get('target_date') != target_date
            or (record.get('source_provenance') or {}).get('source_input_hash') != digest):
        raise ValueError('历史板块页与选定快照的事实版本不同，不能混合展示')
    result = {'source_sha256': hashlib.sha256(source_html.encode()).hexdigest(),
              'target_date': target_date, 'record_hash': record.get('artifact_hash')}
    for key, selector in (('trend', '#sector-trend-view'), ('flow', '#observation-flow-data')):
        node = source.select_one(selector)
        if node:
            result[key] = json.loads(node.get_text())
    if result.get('flow'):
        result['flow'] = validated_flow(result['flow'], target_date)
    if result.get('trend'):
        _check_original_trend(source, record, result['trend'], result)
        numeric_trend_view(result['trend'], target_date)
    _check_chart_snapshot(source, data, target_date)
    tournament = source.select_one('[data-compact-item="t2"] table')
    if tournament:
        result['competition_table'] = [[cell.get_text(' ', strip=True) for cell in row.find_all(['th', 'td'])]
                                       for row in tournament.select('tr')]
    return result


def validated_flow(flow, target_date):
    """Check the saved links against their actual dated observation records."""
    dates = flow.get('dates') or []
    if dates != sorted(set(_day(day, target_date) for day in dates)):
        raise ValueError('板块接力日期重复或顺序不符')
    for row in flow.get('history') or []:
        _day(row.get('date'), target_date)
    expected = _observation_flow({'target_date': target_date, 'history': flow.get('history', []),
                                 'trade_dates': dates}, target_date)
    if expected['dates'] != dates or expected['sectors'] != flow.get('sectors'):
        raise ValueError('板块接力日期与原始记录不符')
    for key, fields in (('nodes', ('name', 'date', 'sector', 'depth', 'channels', 'record')),
                        ('links', ('source', 'target', 'source_date', 'target_date', 'value',
                                   'channels', 'source_record', 'target_record'))):
        actual = [{field: row.get(field) for field in fields} for row in flow.get(key, [])]
        wanted = [{field: row.get(field) for field in fields} for row in expected[key]]
        if actual != wanted:
            raise ValueError('板块接力连线与原始日期记录不符')
    for link in flow.get('links') or []:
        for day in link.get('missing_dates') or []:
            _day(day, target_date)
            if not link['source_date'] < day < link['target_date']:
                raise ValueError('接力缺失日期不在两份报告之间')
    return deepcopy(flow)


def _day(value, target_date):
    if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value or value > target_date:
        raise ValueError('历史图表包含无效或未来日期')
    return value


def _number(value):
    from report.sector_reading_content import _strict_number
    return _strict_number(value)


def _fmt(value, suffix='%'):
    value = _number(value)
    return '待确认' if value is None else f'{value:+.2f}{suffix}'


def _description(row):
    return f'当日{_fmt(row.get("change_pct"))}；近5日{_fmt(row.get("five_day_pct"))}；近5日相对全A{_fmt(row.get("five_day_excess_pp"), "个百分点")}'


def _reading_chart_selection(view):
    """Choose reading samples from complete returns, never from future prices."""
    heat = view['heat']
    history = view.get('ranking_returns') or heat
    dates = history['dates']
    rows = {r.get('track_id') or ('name:' + r['name']): r for r in history['rows']}

    def change(row, count, end=None):
        end = len(dates) if end is None else end
        if end < count or not dates or dates[-1] != view['target_date']:
            return None
        values = row['pct'][end - count:end]
        if len(values) != count or any(v is None for v in values):
            return None
        return (math.prod(1 + v / 100 for v in values) - 1) * 100

    gains = {key: {n: change(row, n) for n in (3, 5, 20, 60)} for key, row in rows.items()}
    groups, chosen = [], {}
    for window, side, label in ((5, 'up', '5日涨幅前5'), (5, 'down', '5日跌幅前5'),
                                (20, 'up', '20日涨幅前5'), (60, 'up', '60日涨幅前5')):
        ranked = [(key, g[window]) for key, g in gains.items() if g[window] is not None
                  and (g[window] < 0 if side == 'down' else g[window] > 0)]
        ranked.sort(key=lambda item: (item[1] if side == 'down' else -item[1], item[0]))
        selected = [key for key, _ in ranked[:5]]
        note = (f'完整交易日窗口不足{window}日' if len(dates) < window else
                ('没有完整窗口的累计下跌样本' if side == 'down' else '没有完整窗口的累计上涨样本')) if not selected else ''
        groups.append({'window': window, 'side': side, 'label': label, 'track_ids': selected, 'note': note})
        for key in selected:
            chosen.setdefault(key, []).append(label)
    selected_heat = [{'index': i, 'groups': chosen[key], 'returns': gains[key]}
                     for i, row in enumerate(heat['rows'])
                     if (key := row.get('track_id') or ('name:' + row['name'])) in chosen]
    # Keep group/rank order rather than the source's arbitrary code order.
    selected_heat.sort(key=lambda r: list(chosen).index(
        heat['rows'][r['index']].get('track_id') or ('name:' + heat['rows'][r['index']]['name'])))
    tracks = {t['track_id']: t for t in [*view['tracks'], *([view['focus_track']] if view.get('focus_track') else [])]}
    comparable = {key for key, t in tracks.items() if any(r.get('excess_pp') is not None for r in t['path'])}
    strong = sorted((key for key, g in gains.items() if key in comparable and g[5] is not None and g[5] > 0),
                    key=lambda key: (-gains[key][5], key))[:5]
    turns = sorted((key for key, g in gains.items() if key in comparable and g[3] is not None and g[3] > 0
                    and (prior := change(rows[key], 3, len(dates) - 3)) is not None and prior <= 0),
                   key=lambda key: (-gains[key][3], key))[:5]
    comparison = [{'track_id': key, 'groups': [group for group, ids in (('strong', strong), ('turn', turns)) if key in ids],
                   'five_day_pct': gains[key][5], 'three_day_pct': gains[key][3]}
                  for key in dict.fromkeys([*strong, *turns])]
    return {'comparison': comparison, 'heat_rows': selected_heat, 'heat_groups': groups,
            'as_of': view['target_date'], 'return_dates': dates}


def numeric_trend_view(value, target_date):
    """Keep every numeric node; replace old threshold verdicts with observations."""
    if value.get('target_date') != target_date:
        raise ValueError('板块趋势目标日期不同')
    inputs = value.get('price_inputs')
    if inputs:
        from report.sector_reading_sources import build_index_view
        rebuilt = build_index_view(inputs['rows'], inputs['metadata'], inputs['market_bars'], target_date,
                                   trade_dates=inputs['trade_dates'], index_type=inputs['index_type'])
        if not rebuilt or any(value.get(k) != rebuilt[k] for k in ('tracks', 'heat', 'ranking_returns')):
            raise ValueError('概念价格投影与原始数值不符')
    view = deepcopy(value)
    numeric = ('change_pct', 'level', 'market_level', 'cumulative_pct', 'excess_pp',
               'drawdown_pct', 'since_observation_pct', 'five_day_pct', 'five_day_excess_pp',
               'breadth', 'five_day_breadth')
    tracks = [*view.get('tracks', []), *([view['focus_track']] if view.get('focus_track') else [])]
    name_counts = {}
    for track in tracks:
        name_counts[track['name']] = name_counts.get(track['name'], 0) + 1
    ids = set()
    for track in tracks:
        if not track.get('track_id') or track['track_id'] in ids:
            raise ValueError('板块路径身份重复或缺失')
        ids.add(track['track_id'])
        code = track.get('code') or track['track_id'].removeprefix('index:')
        track['display_name'] = (track['name'] + ' · ' + code
                                 if track.get('index_type') == 'N' or name_counts[track['name']] > 1 else track['name'])
        _day(track['started_date'], target_date)
        previous = '首个记录节点，暂无前值'
        dates = []
        for row in track['path']:
            dates.append(_day(row['date'], target_date))
            for key in numeric:
                row[key] = _number(row.get(key))
            row.update(before=previous, judgement=_description(row), reason='', next_test='',
                       marker='', role='价格观察', progress=_description(row))
            previous = row['judgement']
        if dates != sorted(set(dates)):
            raise ValueError('板块路径日期重复或顺序不符')
    for key in ('trade_dates',):
        dates = view.get(key) or []
        if dates != sorted(set(_day(day, target_date) for day in dates)):
            raise ValueError('板块比较日期不符')
    if not view.get('heat'):
        # Older saved pages derived this matrix in the browser from the paths.
        view['heat'] = _path_heat(view)
    heat = view.get('heat') or {}
    dates = heat.get('dates') or []
    if dates != sorted(set(_day(day, target_date) for day in dates)):
        raise ValueError('冷暖矩阵日期不符')
    for row in heat.get('rows') or []:
        if any(len(row.get(key) or []) != len(dates) for key in ('temp', 'pct', 'selected')):
            raise ValueError('冷暖矩阵行列不一致')
        if row.get('track_id') and row['track_id'] not in ids:
            raise ValueError('冷暖矩阵关联了不存在的板块')
        row['pct'] = [_number(value) for value in row['pct']]
        from report.sector_trend_tracking import price_temperature
        if any((temp not in (None, -4) if value is None else temp != price_temperature(value))
               for value, temp in zip(row['pct'], row['temp'])):
            raise ValueError('冷暖颜色与原始涨跌数值不符')
    ranking = view.get('ranking_returns')
    if ranking:
        rank_dates = ranking.get('dates') or []
        if rank_dates != sorted(set(_day(day, target_date) for day in rank_dates)):
            raise ValueError('累计涨跌窗口日期不符')
        seen = set()
        heat_by_id = {r.get('track_id') or ('name:' + r['name']): r for r in heat['rows']}
        for row in ranking.get('rows') or []:
            key = row.get('track_id') or ('name:' + row['name'])
            if key in seen or key not in heat_by_id or len(row.get('pct') or []) != len(rank_dates):
                raise ValueError('累计涨跌板块重复或窗口不符')
            seen.add(key)
            row['pct'] = [_number(v) for v in row['pct']]
            if any(v is not None and v <= -100 for v in row['pct']):
                raise ValueError('累计涨跌包含无效收益')
            by_day = dict(zip(rank_dates, row['pct']))
            if any(day not in by_day or by_day[day] != v for day, v in zip(dates, heat_by_id[key]['pct'])):
                raise ValueError('累计涨跌窗口与冷暖原值冲突')
        if seen != set(heat_by_id):
            raise ValueError('累计涨跌缺少原板块样本')
    view['chart_selection'] = _reading_chart_selection(view)
    if view.get('member_comparison'):
        from report.sector_member_comparison import validate_member_comparison, member_relative_returns
        view['member_comparison'] = validate_member_comparison(view['member_comparison'], target_date)
        view['member_relative'] = member_relative_returns(view['member_comparison'], view)
    path_groups, member_groups = {}, {}
    for track in tracks:
        points = [(r['date'], r.get('change_pct'), r.get('level')) for r in track['path']]
        if sum(p[1] is not None and p[2] is not None for p in points) >= 2:
            path_groups.setdefault(evidence_hash(points), []).append(track['track_id'])
    for identity, source in (view.get('member_comparison') or {}).get('memberships', {}).items():
        codes = sorted({r['con_code'] for r in source['members']})
        if codes:
            member_groups.setdefault(evidence_hash(codes), []).append(identity)
    view['duplicate_evidence'] = {'paths': [ids for ids in path_groups.values() if len(ids) > 1],
                                  'members': [ids for ids in member_groups.values() if len(ids) > 1]}
    view['reading_terms'] = []
    return view


def choice_track_ids(choice):
    choice = choice or {}
    rows = [choice.get('primary'), choice.get('today_leader'),
            (choice.get('continuity') or {}).get('previous'), *choice.get('alternatives', [])]
    return [row['track_id'] for row in rows if row and row.get('track_id')]


def reading_trend_view(raw_view, target_date, *, preferred_track_id=None, retained_track_ids=()):
    """Validate the entire source before making the browser-only projection."""
    view = numeric_trend_view(raw_view, target_date)
    choices = [*view.get('tracks', []), *([view['focus_track']] if view.get('focus_track') else [])]
    if preferred_track_id and any(t['track_id'] == preferred_track_id for t in choices):
        view['selected_track_id'] = preferred_track_id
        view['selected_date'] = target_date
        view['focus_note'] = '本次优先比较方向；可搜索本页精选概念或点图切换，不代表持仓。'
    selection, heat = view['chart_selection'], view['heat']
    kept = {r['track_id'] for r in selection['comparison']}
    kept.update(heat['rows'][r['index']].get('track_id') for r in selection['heat_rows'])
    kept.update(retained_track_ids)
    kept.update((view.get('member_comparison') or {}).get('sectors', {}))
    kept.update(t['track_id'] for t in choices if any(
        row.get('breadth') is not None or row.get('five_day_breadth') is not None for row in t['path']))
    kept.add(view.get('selected_track_id'))
    if view.get('focus_track'):
        kept.add(view['focus_track']['track_id'])
    tracks = view.get('tracks') or []
    if tracks and not any(t['track_id'] in kept for t in tracks):
        kept.add(tracks[-1]['track_id'])
    view['tracks'] = [t for t in view.get('tracks', []) if t['track_id'] in kept]
    view['reading_scope'] = {'available_paths': len(choices),
                             'selected_paths': sum(t['track_id'] in kept for t in choices)}
    # Heat indexes address the projected rows, not the original universe.
    heat['rows'] = [heat['rows'][r['index']] for r in selection['heat_rows']]
    for index, row in enumerate(selection['heat_rows']):
        row['index'] = index
    for key in ('price_inputs', 'ranking_returns'):
        view.pop(key, None)
    for key, groups in view['duplicate_evidence'].items():
        view['duplicate_evidence'][key] = [shown for group in groups
            if len(shown := [identity for identity in group if identity in kept]) > 1]
    members = view.get('member_comparison')
    if members:
        for key in ('memberships', 'daily_rows', 'artifact_hash', 'schema_version'):
            members.pop(key, None)
        for identity, sector in members['sectors'].items():
            codes = set(sector['gain_codes']) | set(sector['amount_codes'])
            sector['rows'] = [row for row in sector['rows'] if row['code'] in codes]
            relative = view['member_relative']['sectors'][identity]
            relative['rows'] = {code: row for code, row in relative['rows'].items() if code in codes}
    return view


def _check_reading_projections(source, assets, data, target_date, bundle):
    choice = data.get('reading_choice') or {}
    expected = {}
    if assets.get('trend'):
        view = reading_trend_view(assets['trend'], target_date,
            preferred_track_id=(choice.get('primary') or {}).get('track_id'),
            retained_track_ids=choice_track_ids(choice))
        if view['tracks']:
            expected['sector-trend-view'] = view
    if assets.get('concept_flow'):
        from report.sector_concept_flow import concept_flow_view
        view = expected.get('sector-trend-view', {})
        expected['concept-flow-data'] = concept_flow_view(assets['concept_flow'], target_date,
            track_ids=[t['track_id'] for t in view.get('tracks', [])] +
                      ([view['focus_track']['track_id']] if view.get('focus_track') else []))
    expected = json.loads(json.dumps(expected, ensure_ascii=False, allow_nan=False))
    if bundle.get('view_hashes') != {key: evidence_hash(value) for key, value in expected.items()}:
        raise ValueError('阅读投影与选定快照事实不符')
    for key, value in expected.items():
        node = source.select_one('#' + key)
        if node is None or json.loads(node.get_text()) != value:
            raise ValueError('阅读图表数值与选定快照事实投影不同')


def render_numeric_trend(soup, raw_view, target_date, *, preferred_track_id=None, retained_track_ids=()):
    view = reading_trend_view(raw_view, target_date, preferred_track_id=preferred_track_id,
                             retained_track_ids=retained_track_ids)
    tracks = view.get('tracks') or []
    if not tracks:
        return None
    esc = lambda value: html.escape(str(value), quote=True)
    choices = tracks + ([view['focus_track']] if view.get('focus_track') else [])
    selected = next((t for t in choices if t['track_id'] == view.get('selected_track_id')), tracks[-1])
    selected_id = view.get('selected_track_id', selected['track_id'])
    selected_row = next((r for r in selected['path'] if r['date'] == view.get('selected_date')), selected['path'][-1])
    heat = view['heat']
    selection = view['chart_selection']
    has_breadth = any(row.get('breadth') is not None or row.get('five_day_breadth') is not None
                     for track in choices for row in track['path'])
    options = ''.join(f'<option value="{esc(t["track_id"])}"{" selected" if t["track_id"] == selected_id else ""}>{esc(t["display_name"])}</option>' for t in choices)
    if not selected_id:
        options = '<option value="" selected>原主攻方向缺少同名路径</option>' + options
    methods = ''.join(f'<option>{esc(m)}</option>' for m in dict.fromkeys(t['method'] for t in choices))
    if not selected_id:
        methods = '<option value="" selected>主攻可比事实不足</option>' + methods
    def controls(identity, items, current):
        return '<div class="reading-tags" role="group">' + ''.join(
            f'<button type="button" class="reading-tag" data-reading-control="{identity}" '
            f'data-reading-value="{esc(value)}" aria-pressed="{str(value == current).lower()}">{esc(label)}</button>'
            for value, label in items) + '</div>'
    featured_ids = {r['track_id'] for r in selection['comparison']}
    ordered = sorted(choices, key=lambda t: (t['track_id'] != selected_id,
                     t['track_id'] not in featured_ids, t['name'], t['track_id']))
    sector_buttons = '<div class="reading-tags trend-sector-tags" role="group" aria-label="板块名称与近期表现">'
    for track in ordered:
        row = next((r for r in track['path'] if r['date'] == selected_row['date']), None)
        pct = row.get('five_day_pct') if row else None
        recent = f'5日 {pct:+.2f}%' if pct is not None else '同窗未齐'
        if sum(t['name'] == track['name'] for t in choices) > 1:
            recent += ' · ' + track['track_id'].removeprefix('index:')
        sector_buttons += (f'<button type="button" class="reading-tag" data-trend-sector="{esc(track["track_id"])}" '
            f'aria-label="{esc(track["display_name"])}" aria-pressed="{str(track["track_id"] == selected_id).lower()}">'
            f'<strong>{esc(track["name"])}</strong><small data-trend-recent>{esc(recent)}</small></button>')
    sector_buttons += '</div>'
    out = [
        '<div class="sector-trend"><h3>整段趋势跟踪 · 月度对比</h3>',
        f'<small>本页精选{view["reading_scope"]["selected_paths"]}条路径；完整{view["reading_scope"]["available_paths"]}条路径留在冻结来源。观察前路径为后选背景，不是事前推荐。</small>',
        f'<p id="trend-focus-note" class="trend-focus-note">{esc(view.get("focus_note", ""))}</p>',
        '<p class="trend-fallback">图表正在加载。</p>',
        '<div class="trend-controls"><span>比较口径</span>' + controls('sector-trend-group',
            [(m, m) for m in dict.fromkeys(t['method'] for t in choices)], selected['method']) +
            f'<select id="sector-trend-group" hidden>{methods}</select></div>',
        '<div class="trend-controls"><span>比较板块</span>' + controls('trend-comparison-scope',
            [('featured', '近期走强与翘头'), ('strong', '近5日走强'), ('turn', '近期翘头')], 'featured') +
            '<select id="trend-comparison-scope" hidden><option value="featured">近期走强与翘头</option><option value="strong">近5日走强</option><option value="turn">近期翘头</option></select></div>',
        '<div class="trend-chart-card"><div id="sector-trend-comparison" class="trend-echart" role="img" aria-label="板块月度相对全A比较"></div></div>',
        '<p id="trend-comparison-note" class="trend-chart-caption" aria-live="polite"></p>',
        '<p class="trend-chart-caption">走强：近5日累计上涨前5；翘头：近3日转涨且此前3日不涨，按近3日涨幅取前5；合并去重。曲线仍为整段相对全A累计差值，不是预测；图例独立显隐，点曲线联动日期。</p>',
        *(['<details id="trend-duplicate-evidence"><summary>重复证据提示</summary><p>以下样本在本次窗口路径或本次查询成分相同，不作为多份独立扩散证据；不据此合并代码或推断永久相同。</p>' +
           ''.join('<p>' + label + '：' + esc('；'.join(next(t['display_name'] for t in choices if t['track_id'] == identity)
                   for identity in group)) + '</p>' for key, label in (('paths', '同窗价格路径相同'), ('members', '本次查询成分集合相同'))
                   for group in view['duplicate_evidence'][key]) + '</details>']
          if any(view['duplicate_evidence'].values()) else []),
        f'<h4>冷暖方格 · {len(selection["heat_rows"])}个精选板块 × {len(heat["dates"])}个交易日</h4>',
        '<p class="trend-chart-caption">5日涨幅、5日跌幅、20日涨幅、60日涨幅各前5，重复合并；累计涨跌按完整交易日复利计算，非每日涨跌相加。悬浮查看单格日期与当日涨跌。</p>',
        *[f'<p class="trend-chart-caption">{esc(g["label"])}：{esc(g["note"])}</p>' for g in selection['heat_groups'] if g['note']],
        '<p class="trend-chart-caption">红涨绿跌，近白为零，灰色为缺失；蓝框定位当前选择。黑框仅保留原每日涨幅前三标记，不代表必须交易这三名。</p>',
        '<div class="trend-controls"><span>方格大小</span>' + controls('trend-matrix-scale',
            [('18', '紧密'), ('23', '放大'), ('29', '大字')], '18') +
            '<select id="trend-matrix-scale" hidden><option value="18">紧密</option><option value="23">放大</option><option value="29">大字</option></select></div>',
        '<div class="trend-heat-scroll"><div id="sector-trend-revisions" class="trend-echart" role="img" aria-label="精选板块逐日冷暖矩阵"></div></div>',
        '<p id="trend-heat-note" class="trend-chart-caption" aria-live="polite"></p>',
        '<h4 id="trend-selection-heading" tabindex="-1">板块与日期</h4>',
        sector_buttons,
        '<div class="trend-search"><label for="trend-sector-search">搜索本页精选名称或代码，也可点选图中板块</label>'
        '<input id="trend-sector-search" type="search" autocomplete="off" role="combobox" aria-autocomplete="list" '
        'aria-expanded="false" aria-controls="trend-search-results" placeholder="例如：机器人、物理AI、886040">'
        '<div id="trend-search-results" role="listbox" hidden></div><p id="trend-search-status" aria-live="polite"></p></div>',
        '<p id="trend-selected-label" class="trend-selected-label" aria-live="polite"></p>',
        '<div id="trend-date-buttons" class="reading-tags trend-date-tags" role="group" aria-label="选择交易日"></div>',
        '<div class="trend-date-controls"><button type="button" id="trend-date-previous" aria-label="前一交易日">← 前一天</button>'
        '<label for="trend-date-range">查看日期 <output id="trend-date-label" for="trend-date-range"></output></label>'
        '<button type="button" id="trend-date-next" aria-label="后一交易日">后一天 →</button>'
        '<input type="range" id="trend-date-range" min="0" step="1" aria-label="沿交易日查看"></div>',
        f'<select id="sector-trend-selector" aria-label="板块备用选择" hidden>{options}</select>',
        '<select id="trend-date-selector" aria-label="日期备用选择" hidden>' + ''.join(
            f'<option value="{r["date"]}"{" selected" if r is selected_row else ""}>{r["date"]}</option>' for r in selected['path']) + '</select>',
        '<div hidden>',
        f'<section id="trend-fact-panel" data-trend-track="{esc(selected_id)}" data-trend-date="{selected_row["date"]}"{" hidden" if not selected_id else ""} aria-live="polite">',
        '</section></div>',
        '<div class="trend-detail-cards">' + ''.join(
            f'<article class="trend-chart-card"><h4><span data-trend-name></span> · {label}</h4><div id="sector-trend-{key}" class="trend-echart" role="img" aria-label="{label}"></div></article>'
            for key, label in (('price', '走势对照'), ('drawdown', '回撤深度'),
                               *([('breadth', '上涨面')] if has_breadth else []))) + '</div>',
        '<p id="sector-trend-current" aria-live="polite"></p>',
    ]
    out.append('<script type="application/json" id="sector-trend-view">' + json.dumps(view, ensure_ascii=False, allow_nan=False).replace('<', '\\u003c') + '</script>')
    from report.sector_trend_tracking import _temperature_band_pieces
    bands = json.dumps(_temperature_band_pieces(), ensure_ascii=False).replace('<', '\\u003c')
    script = (Path(__file__).resolve().parents[1] / 'templates/sector_trend_charts.js').read_text()
    out.append('<script>const TEMPERATURE_BANDS=' + bands + ';</script><script>' + script + '</script></div>')
    return BeautifulSoup(''.join(out), 'html.parser').div


def historical_observation_section(soup, assets, target_date, *, preferred_track_id=None, retained_track_ids=()):
    from report.sector_reading_primitives import _text
    section = soup.new_tag('section', attrs={'class': 'sector-daily-section', 'id': 'daily-history'})
    section.append(_text(soup, 'h2', '跨日图表'))
    concept_mode = bool(assets.get('concept_flow') or (assets.get('trend') or {}).get('index_type') == 'N')
    section.append(_text(soup, 'small', '概念逐日事实与同代码价格路径' if concept_mode else
                        '历史观察记录 · 通道数不是资金量 · 缺日报不补画连续接力'))
    if assets.get('concept_flow'):
        from report.sector_concept_flow import render_concept_flow
        view = reading_trend_view(assets['trend'], target_date, preferred_track_id=preferred_track_id,
                                 retained_track_ids=retained_track_ids) if assets.get('trend') else {}
        section.append(render_concept_flow(soup, assets['concept_flow'], target_date,
            track_ids=[t['track_id'] for t in view.get('tracks', [])] +
                      ([view['focus_track']['track_id']] if view.get('focus_track') else [])))
    elif concept_mode:
        section.append(_text(soup, 'p', assets.get('concept_flow_missing') or '概念净额事实不足，不以旧接力替代。'))
    flow = assets.get('flow')
    if flow and not concept_mode:
        context = {'target_date': target_date, 'history': flow.get('history', []),
                   'trade_dates': flow.get('dates', []), 'source_hash': flow.get('source_hash', '')}
        section.append(_text(soup, 'h3', '板块跨日报接力'))
        # Preserve the original missing-calendar meaning rather than treating
        # every displayed date column as a verified exchange calendar.
        fragment = BeautifulSoup(_render_observation_flow(context, target_date), 'html.parser')
        encoded = fragment.select_one('#observation-flow-data')
        if encoded:
            encoded.string = json.dumps(flow, ensure_ascii=False, allow_nan=False).replace('<', '\\u003c')
        section.append(fragment)
    if assets.get('trend'):
        trend = render_numeric_trend(soup, assets['trend'], target_date, preferred_track_id=preferred_track_id,
                                     retained_track_ids=retained_track_ids)
        if trend is not None:
            section.append(trend)
    for key, label in (('trend_provenance', '原趋势事实'), ('chart_provenance', '同源补查'),
                       ('heat_provenance', '冷暖矩阵事实'), ('ranking_provenance', '累计排名历史补查')):
        value = assets.get(key)
        if value:
            node = soup.new_tag('script', attrs={'type': 'application/json', 'id': 'sector-' + key.replace('_', '-')})
            node.string = json.dumps(value, ensure_ascii=False).replace('<', '\\u003c')
            section.append(node)
    style = soup.new_tag('style')
    style.string = HYPOTHESIS_STYLE
    section.append(style)
    return section
