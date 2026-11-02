"""What is new today: dated facts ranked by how unusual they are against recent sessions.

Each observation carries a surprise score in [0, 1] (how far today's value sits from the
middle of its own recent history, or how rare a move is for that stock). The page shows
the most unusual few, so each day reads differently because the facts differ, not because
a fixed sentence was chosen.
"""
from math import fsum, sqrt

from report.decision_board import _panel, _select
from report.market_alpha_beta import DEFAULT_WINDOW, _fit, _prefix, _shrink

MOVER_Z = 3.0


def _percentile(values, value):
    values = [v for v in values if v is not None]
    if value is None or len(values) < 5:
        return None
    return sum(v <= value for v in values) / len(values)


def _extremeness(rank):
    return None if rank is None else abs(rank - 0.5) * 2


def _pct(value, digits=2):
    return f'{value:+.{digits}f}%'


def independent_movers(panel, t, window=DEFAULT_WINDOW):
    """Today's move against what the stock's own market relation (fitted up to yesterday) implies."""
    start, end = t - window, t
    if start < 0 or panel['market'][t] is None:
        return []
    fits = []
    for i in panel['eligible']:
        fit = _fit(panel['sums'][i], start, end)
        if fit is not None and panel['returns'][i][t] is not None:
            fits.append((i, fit))
    _shrink([fit for _, fit in fits])
    movers = []
    for i, fit in fits:
        daily = panel['returns'][i][start:end]
        market = panel['market'][start:end]
        residual = [y - fit['intercept'] - fit['beta'] * x for y, x in zip(daily, market)]
        sigma = sqrt(fsum(r * r for r in residual) / (len(residual) - 2))
        if sigma <= 0:
            continue
        surprise = panel['returns'][i][t] - fit['intercept'] - fit['beta'] * panel['market'][t]
        movers.append({'index': i, 'code': panel['codes'][i], 'name': panel['names'][i] or '名称待确认',
                       'industry': panel['industries'][i] or '行业待确认', 'today_pct': panel['returns'][i][t],
                       'expected_pct': fit['intercept'] + fit['beta'] * panel['market'][t],
                       'surprise_pp': surprise, 'z': surprise / sigma})
    return movers


def build_observations(value, projection, board, *, limit_codes=None):
    panel = _panel(value)
    t = len(panel['days']) - 1
    series = projection['series']
    regime = projection['regime']
    today = series[-1]
    out = []

    divergence = [None if p['market_pct'] is None or p['median_pct'] is None else p['market_pct'] - p['median_pct']
                  for p in series]
    rank = _percentile(divergence, divergence[-1])
    if divergence[-1] is not None:
        out.append({'id': 'divergence', 'kind': 'market', 'score': _extremeness(rank),
                    'title': '大盘与多数个股' + ('同步' if abs(divergence[-1]) < 0.3 else '背离'),
                    'text': f"中证全指{_pct(today['market_pct'])}、个股中位数{_pct(today['median_pct'])}，"
                            f"大盘比多数个股{'强' if divergence[-1] > 0 else '弱'}{abs(divergence[-1]):.2f}个百分点"
                            + (f"，在近{len([d for d in divergence if d is not None])}日中排第{round(rank * 100)}百分位" if rank is not None else '') + '。',
                    'values': {'market_pct': today['market_pct'], 'median_pct': today['median_pct'],
                               'gap_pp': divergence[-1], 'rank': rank}})
    shares = [p['same_share'] for p in series]
    rank = _percentile(shares, shares[-1])
    if shares[-1] is not None:
        out.append({'id': 'same_share', 'kind': 'beta', 'score': _extremeness(rank),
                    'title': '个股跟大盘的一致程度',
                    'text': f"{shares[-1]:.0f}%的个股与中证全指同向"
                            + (f"，近{len([s for s in shares if s is not None])}日第{round(rank * 100)}百分位" if rank is not None else '')
                            + '；两者无关时约50%。',
                    'values': {'same_share': shares[-1], 'rank': rank}})
    syncs = [p['sync'] for p in series]
    if len(syncs) > 5 and syncs[-1] is not None and syncs[-6] is not None:
        change = syncs[-1] - syncs[-6]
        changes = [b - a for a, b in zip(syncs[:-5], syncs[5:]) if a is not None and b is not None]
        rank = _percentile(changes, change)
        out.append({'id': 'sync_shift', 'kind': 'beta', 'score': _extremeness(rank),
                    'title': '大盘带动' + ('在增强' if change > 0 else '在减弱'),
                    'text': f"20日共振度由5个交易日前的{syncs[-6]:.2f}变为{syncs[-1]:.2f}（{change:+.2f}）"
                            + (f"，5日变化幅度在近期排第{round(rank * 100)}百分位" if rank is not None else '') + '。',
                    'values': {'sync_before': syncs[-6], 'sync': syncs[-1], 'change': change, 'rank': rank}})
    turnover = board['market']['turnover_yi']
    prior = [v for v in turnover[-21:-1] if v is not None]
    if turnover[-1] is not None and prior:
        average = fsum(prior) / len(prior)
        rank = _percentile(turnover, turnover[-1])
        out.append({'id': 'turnover', 'kind': 'market', 'score': _extremeness(rank),
                    'title': '成交' + ('放大' if turnover[-1] > average else '收缩'),
                    'text': f"两市成交额{turnover[-1] / 1e4:.2f}万亿元，较前20日均值{(turnover[-1] / average - 1) * 100:+.1f}%"
                            + (f"，近{len([v for v in turnover if v is not None])}日第{round(rank * 100)}百分位" if rank is not None else '') + '。',
                    'values': {'turnover_yi': turnover[-1], 'average_yi': average, 'rank': rank}})
    limit_up = []
    for column in range(len(panel['days'])):
        count = 0
        for i in panel['eligible']:
            r = panel['returns'][i][column]
            if r is not None and r >= (20. if panel['codes'][i].startswith(('300', '301', '688', '689')) else 10.) - 0.2:
                count += 1
        limit_up.append(count)
    rank = _percentile(limit_up, limit_up[-1])
    out.append({'id': 'limit_up', 'kind': 'market', 'score': _extremeness(rank),
                'title': '涨停家数',
                'text': f"按涨幅估算的涨停{limit_up[-1]}只（不含ST），前一交易日{limit_up[-2]}只"
                        + (f"，近{len(limit_up)}日第{round(rank * 100)}百分位" if rank is not None else '')
                        + ('；当日涨停名单另计' + str(len(limit_codes)) + '只' if limit_codes is not None else '') + '。',
                'values': {'count': limit_up[-1], 'previous': limit_up[-2], 'rank': rank}})

    movers = independent_movers(panel, t)
    strong = sorted((m for m in movers if m['z'] >= MOVER_Z), key=lambda m: -m['z'])
    weak = sorted((m for m in movers if m['z'] <= -MOVER_Z), key=lambda m: m['z'])
    if movers:
        expected = len(movers) * 0.0027  # two-sided share beyond three standard deviations under normality
        clusters = {}
        for m in strong:
            clusters[m['industry']] = clusters.get(m['industry'], 0) + 1
        top = sorted(clusters.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
        out.append({'id': 'independent_movers', 'kind': 'alpha',
                    'score': min(1., (len(strong) + len(weak)) / max(expected * 10, 1)),
                    'title': '今天走出独立异动的股票',
                    'text': f"按各自截至昨天的贝塔推算，今天超出预期3倍波动以上的上涨{len(strong)}只、下跌{len(weak)}只"
                            + (f"；上涨集中在{'、'.join(f'{k}{v}只' for k, v in top)}" if top else '')
                            + ('；最突出：' + '、'.join(f"{m['name']}{_pct(m['today_pct'])}（推算{_pct(m['expected_pct'])}）" for m in strong[:3])
                               if strong else '') + '。',
                    'values': {'up': len(strong), 'down': len(weak), 'expected_two_sided': expected,
                               'leaders': [{k: m[k] for k in ('code', 'name', 'industry', 'today_pct', 'expected_pct', 'z')}
                                           for m in strong[:5]],
                               'laggards': [{k: m[k] for k in ('code', 'name', 'industry', 'today_pct', 'expected_pct', 'z')}
                                            for m in weak[:5]]}})
    yesterday = _select(panel, t - 1)
    if yesterday is not None:
        before = {row['code']: row for row in yesterday['alpha']}
        now = {row['code']: row for row in board['candidates']}
        entered = [c for c in board['candidates'] if c['status'] == 'buy' and (before.get(c['code']) or {}).get('status') != 'buy']
        left = [before[code] for code in before if before[code]['status'] == 'buy' and (now.get(code) or {}).get('status') != 'buy']
        reasons = {}
        for row in left:
            current = now.get(row['code'])
            if current is None:
                reasons[row['code']] = '不再是独立上涨'
            else:
                failed = [board['checks'][k] for k, v in current['checks'].items() if not v]
                reasons[row['code']] = '未过：' + '、'.join(failed)
        names = {row['code']: panel['names'][row['index']] or row['code'] for row in yesterday['alpha']}
        if entered or left:
            out.append({'id': 'qualified_changes', 'kind': 'alpha', 'score': 0.9,
                        'title': '检查全过的阿尔法有进有出',
                        'text': ('新进入：' + '、'.join(c['name'] for c in entered) if entered else '没有新进入')
                                + '；' + ('退出：' + '、'.join(f"{names[r['code']]}（{reasons[r['code']]}）" for r in left[:5]) + (f'等{len(left)}只' if len(left) > 5 else '')
                                         if left else '没有退出') + '。',
                        'values': {'entered': [c['code'] for c in entered], 'left': [r['code'] for r in left],
                                   'reasons': reasons}})
    concepts = (projection.get('concepts') or {}).get(str(projection['default_window'])) or {}
    stronger = concepts.get('stronger') or []
    if stronger:
        best = max(stronger, key=lambda r: r['own5_pp'])
        out.append({'id': 'concept_strength', 'kind': 'sector', 'score': 0.6,
                    'title': '比大盘推算更强的概念',
                    'text': f"{concepts['counts']['alpha_up'] + concepts['counts']['resilient']}个概念的独立收益显著为正"
                            f"（其中真正上涨的{concepts['counts']['alpha_up']}个）；近5日相对最强的是{best['name']}，"
                            f"近5日独立收益{best['own5_pp']:+.2f}个百分点、20日涨跌{_pct(best['total_pct'])}。",
                    'values': {'alpha_up': concepts['counts']['alpha_up'], 'resilient': concepts['counts']['resilient'],
                               'best': best['name'], 'best_own5_pp': best['own5_pp'], 'best_total_pct': best['total_pct']}})
    for item in out:
        item['score'] = round(item['score'], 4) if item['score'] is not None else 0.
    out.sort(key=lambda item: -item['score'])
    return {'schema': 'daily_observations.v1', 'target_date': value['target_date'], 'items': out,
            'mover_z': MOVER_Z}
