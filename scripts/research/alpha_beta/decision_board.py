"""备用阿尔法／贝塔研究；不进入小盘日报。原规则和成本仅供历史比较。"""
"""Decision board: after alpha and beta are compared, what to do next session.

Rules are fixed before looking at outcomes (docs/plans/2026-10-30-decision-dashboard-prd.md):
a five-item buying-qualification checklist for independent risers, a high-beta basket,
beta-exposure scenarios, and a walk-forward check that buys at the next open, sells five
sessions later and pays a round-trip cost. Nothing here infers an account or a position size.
"""
from math import fsum, prod, sqrt
from statistics import median, stdev

from research.alpha_beta.market_alpha_beta import DEFAULT_WINDOW, _eligible, _fit, _prefix, _shrink, _stock_detail
from report.market_returns import price_rows, validate_market_returns

CHECKS = {'strengthening': '仍在走强', 'resists_market': '大盘跌时不跟跌', 'not_spiking': '不是急涨末端',
          'stop_near': '止损距离可承受', 'liquid': '成交额足够', 'buyable': '目标日能买到'}
STATUS = {'buy': '检查全过', 'wait': '等回调', 'watch': '观察', 'avoid': '不做'}
STANCE = {'defense': '防守', 'balanced': '均衡', 'offense': '进攻'}
LIQUIDITY_K = 100_000.   # 20-session average amount in thousand yuan: 1亿元
COST_PCT = 0.2           # round-trip commission, stamp duty and slippage estimate
HOLD = 5
BASKET = 10
SCENARIO_PCT = 2.0
CHASE_PCT = 3.0          # a next-day open above +3% is not chased
STOP_LOOKBACK = 10
STOP_MAX_PCT = 15.0      # the exit level may sit at most 15% below the last close
LIMIT_MARGIN = 0.2


def _limit_pct(code):
    return 20. if code.startswith(('300', '301', '688', '689')) else 10.


def _panel(value):
    days, codes = value['trade_dates'], value['codes']
    size = len(days)
    blank = lambda: [[None] * size for _ in codes]
    close, opened, amount, previous, returns = blank(), blank(), blank(), blank(), blank()
    for column, day in enumerate(days):
        for index, c, p, o, a in price_rows(value, day):
            close[index][column], previous[index][column] = c, p
            opened[index][column], amount[index][column] = o, a
            returns[index][column] = (c - p) / p * 100
    bench = {row['date']: row for row in value['benchmark']['rows']}
    market = [(bench[d]['close'] - bench[d]['pre_close']) / bench[d]['pre_close'] * 100 if d in bench else None
              for d in days]
    eligible, _ = _eligible(value)
    return {'days': days, 'codes': codes, 'names': value['profile']['names'],
            'industries': value['profile']['industries'], 'close': close, 'open': opened, 'amount': amount,
            'previous': previous, 'returns': returns, 'market': market,
            'market_open': [bench[d].get('open') if d in bench else None for d in days],
            'market_close': [bench[d]['close'] if d in bench else None for d in days],
            'eligible': eligible, 'sums': {i: _prefix(returns[i], market) for i in eligible}}


def _select(panel, t, window=DEFAULT_WINDOW):
    """Candidates and the beta basket using only sessions up to and including index t."""
    start, end = t - window + 1, t + 1
    if start < 0:
        return None
    fits = [(i, fit) for i in panel['eligible'] if (fit := _fit(panel['sums'][i], start, end)) is not None]
    if not fits:
        return None
    _shrink([fit for _, fit in fits])
    alpha, beta = [], []
    for i, fit in fits:
        detail = _stock_detail(fit, panel['returns'][i], panel['market'], start, end, window)
        if detail['label'] not in ('alpha_up', 'beta'):
            continue
        code = panel['codes'][i]
        amounts = [a for a in panel['amount'][i][start:end] if a is not None]
        average = fsum(amounts) / len(amounts) if amounts else None
        liquid = average is not None and average >= LIQUIDITY_K
        buyable = panel['returns'][i][t] < _limit_pct(code) - LIMIT_MARGIN
        if detail['label'] == 'beta':
            if liquid and buyable:
                beta.append({'index': i, 'code': code, 'beta': detail['beta'], 'r2': detail['r2'],
                             'total_pct': detail['total_pct'], 'own_pp': detail['own_pp'],
                             'down_mean_pct': detail['down_mean_pct'], 'amount_yi': average / 1e5})
            continue
        daily = panel['returns'][i][start:end]
        recent = (prod(1 + r / 100 for r in daily[-3:]) - 1) * 100
        # A spike is acceleration beyond the stock's own pace, not a steady trend.
        acceleration = fsum(daily[-3:]) - 3 * fsum(daily) / len(daily)
        spike = 2 * stdev(daily) * sqrt(3)
        closes = [c for c in panel['close'][i][max(0, t - STOP_LOOKBACK + 1):t + 1] if c is not None]
        last = panel['close'][i][t]
        stop = min(closes)
        distance = (stop / last - 1) * 100
        checks = {'strengthening': detail['own5_pp'] > 0,
                  'resists_market': detail['down_days'] == 0 or detail['down_mean_pct'] >= 0,
                  'not_spiking': acceleration < spike, 'stop_near': distance >= -STOP_MAX_PCT,
                  'liquid': liquid, 'buyable': buyable}
        failed = [key for key, passed in checks.items() if not passed]
        # A pullback cures both an extended run and a far exit level; illiquid or limit-up names are not traded.
        status = ('buy' if not failed else 'avoid' if not liquid or not buyable
                  else 'wait' if set(failed) <= {'not_spiking', 'stop_near'} else 'watch')
        alpha.append({'index': i, 'code': code, 'checks': checks, 'passes': len(checks) - len(failed),
                      'status': status, 'beta': detail['beta'], 'r2': detail['r2'], 't_alpha': detail['t_alpha'],
                      'total_pct': detail['total_pct'], 'market_pp': detail['market_pp'], 'own_pp': detail['own_pp'],
                      'own5_pp': detail['own5_pp'], 'down_mean_pct': detail['down_mean_pct'],
                      'down_days': detail['down_days'], 'recent3_pct': recent, 'acceleration_pp': acceleration,
                      'spike_pp': spike,
                      'amount_yi': average / 1e5 if average is not None else None,
                      'close': last, 'stop': stop, 'stop_distance_pct': distance,
                      'today_pct': panel['returns'][i][t]})
    alpha.sort(key=lambda row: (-row['passes'], -(row['t_alpha'] or 0), row['code']))
    beta.sort(key=lambda row: (-row['beta'], row['code']))
    return {'alpha': alpha, 'beta': beta[:BASKET]}


def _forward(panel, i, t):
    """Next-open entry, fifth-session close exit; a limit-up or chased open is not bought."""
    if t + HOLD >= len(panel['days']):
        return None
    if i is None:
        opened, close, previous = panel['market_open'][t + 1], panel['market_close'][t + 1], None
        returns, code = panel['market'], ''
    else:
        opened, close, previous = panel['open'][i][t + 1], panel['close'][i][t + 1], panel['previous'][i][t + 1]
        returns, code = panel['returns'][i], panel['codes'][i]
    if opened is None or close is None:
        return None
    if previous is not None:
        gap = (opened / previous - 1) * 100
        if gap >= _limit_pct(code) - LIMIT_MARGIN or gap > CHASE_PCT:
            return None
    level = close / opened
    for k in range(t + 2, t + HOLD + 1):
        if returns[k] is None:
            return None
        level *= 1 + returns[k] / 100
    return (level - 1) * 100


def _basket(panel, members, t):
    values = [r for i in members if (r := _forward(panel, i, t)) is not None]
    return (fsum(values) / len(values) - COST_PCT, len(values)) if values else (None, 0)


def _summary(rows, key):
    excess = [row[key] - row['index'] for row in rows if row[key] is not None and row['index'] is not None]
    returns = [row[key] for row in rows if row[key] is not None]
    if not excess:
        return {'dates': 0, 'mean_excess': None, 'median_excess': None, 'hit_rate': None, 'mean_return': None}
    return {'dates': len(excess), 'mean_excess': fsum(excess) / len(excess), 'median_excess': median(excess),
            'hit_rate': sum(e > 0 for e in excess) / len(excess), 'mean_return': fsum(returns) / len(returns)}


def walk_forward(panel, window=DEFAULT_WINDOW):
    rows = []
    for t in range(window - 1, len(panel['days']) - HOLD):
        picked = _select(panel, t, window)
        if picked is None:
            continue
        buys = [row['index'] for row in picked['alpha'] if row['status'] == 'buy'][:BASKET]
        alpha, alpha_n = _basket(panel, buys, t)
        beta, beta_n = _basket(panel, [row['index'] for row in picked['beta']], t)
        rows.append({'date': panel['days'][t], 'exit_date': panel['days'][t + HOLD], 'alpha_candidates': len(buys),
                     'alpha': alpha, 'alpha_bought': alpha_n, 'beta': beta, 'beta_bought': beta_n,
                     'index': _forward(panel, None, t)})
    both = [row for row in rows if row['alpha'] is not None and row['beta'] is not None]
    gaps = [row['alpha'] - row['beta'] for row in both]
    summary = {'alpha': _summary(rows, 'alpha'), 'beta': _summary(rows, 'beta'), 'decision_dates': len(rows),
               'alpha_minus_beta': {'dates': len(gaps), 'mean': fsum(gaps) / len(gaps) if gaps else None,
                                    'hit_rate': sum(g > 0 for g in gaps) / len(gaps) if gaps else None},
               'hold': HOLD, 'cost_pct': COST_PCT, 'basket': BASKET}
    alpha = summary['alpha']
    summary['alpha_edge'] = (None if alpha['dates'] < 5 else
                             alpha['mean_excess'] > 0 and alpha['hit_rate'] >= 0.5)
    return rows, summary


def _exposure(rows, label):
    if not rows:
        return None
    beta = fsum(row['beta'] for row in rows) / len(rows)
    downs = [row['down_mean_pct'] for row in rows if row['down_mean_pct'] is not None]
    return {'label': label, 'count': len(rows), 'beta': beta,
            'total_pct': fsum(row['total_pct'] for row in rows) / len(rows),
            'own_pp': fsum(row['own_pp'] for row in rows) / len(rows),
            'down_mean_pct': fsum(downs) / len(downs) if downs else None,
            'down_scenario_pct': -SCENARIO_PCT * beta, 'up_scenario_pct': SCENARIO_PCT * beta}


def _stance(regime, trend_down, edge, buy_count):
    if regime['verdict'] == 'beta' and trend_down:
        overall, beta = 'defense', 'avoid'
        alpha = 'buy_only' if edge else 'watch'
    elif regime['verdict'] == 'beta':
        overall, beta = 'offense', 'buy'
        alpha = 'supplement' if edge else 'watch'
    else:
        overall, beta = 'balanced', 'less'
        alpha = 'buy_only' if edge else 'watch'
    if alpha in ('buy_only', 'supplement') and not buy_count:
        alpha = 'none_today'
    return overall, beta, alpha


BETA_TEXT = {'avoid': '贝塔：不做。大盘带着跌，跟随大盘的股票和板块先回避。',
             'buy': '贝塔：可做。顺着大盘，优先跟随大盘最紧、成交活跃的方向。',
             'less': '贝塔：少做。大盘带动不强，跟着大盘买收益有限。'}
ALPHA_TEXT = {'buy_only': '阿尔法：可做，只买“检查全过”的几只，收盘跌破失效价就走。',
              'supplement': '阿尔法：作为补充，只买“检查全过”的几只。',
              'watch': '阿尔法：先观察。“检查全过”的{buys}只是相对最好的，但同一规则近两个月买入后5日平均{edge}，'
                       '现在买胜算不够；若一定要做，只选检查全过的，收盘跌破失效价就走。',
              'none_today': '阿尔法：今天没有检查全过的股票，不买，等名单出现。'}
HEADLINES = {
    ('defense', 'watch'): '防守：大盘带着跌，贝塔不做，阿尔法也先观察',
    ('defense', 'buy_only'): '防守：大盘带着跌，贝塔不做，只买检查全过的阿尔法',
    ('defense', 'none_today'): '防守：大盘带着跌，贝塔不做，今天没有合格的阿尔法',
    ('offense', 'supplement'): '进攻：大盘带动上涨，顺着贝塔做，阿尔法作补充',
    ('offense', 'none_today'): '进攻：大盘带动上涨，顺着贝塔做',
    ('offense', 'watch'): '进攻：大盘带动上涨，顺着贝塔做，阿尔法只观察',
    ('balanced', 'buy_only'): '均衡：大盘带动不强，以检查全过的阿尔法为主',
    ('balanced', 'watch'): '均衡：大盘带动不强，阿尔法规则近期也无优势，少做为主',
    ('balanced', 'none_today'): '均衡：大盘带动不强，今天没有合格的阿尔法，少做为主',
}
DISCIPLINE = ('纪律：次日高开超过3%不追；执行计划的股票收盘比买价高10%，下一个交易日开盘卖，钱留到下一个换手日'
              '（2026-10-31起代替高开兑现）；执行计划不设止损；阿尔法观察收盘跌破失效价即退出；整个账户净值跌破0.7就全部停下。')


def long_run_evidence(backtest):
    """Out-of-sample results of the long backtest that bear on whether alpha chasing has an edge."""
    if not backtest:
        return None
    # Test the rule actually in use; an older backtest without it falls back to plain alpha buying.
    used = 'live_rule' if 'live_rule' in backtest['stats'] else 'alpha'
    alpha = backtest['stats'][used].get('out_of_sample') or {}
    index = backtest['stats']['index'].get('out_of_sample') or {}
    own = backtest['ic'].get('own') or {}
    return {'start': backtest['start'], 'design_start': backtest['design_start'], 'strategy': used,
            'alpha_oos_cagr': alpha.get('cagr_pct'), 'index_oos_cagr': index.get('cagr_pct'),
            'own_ic': own.get('mean_ic'), 'own_ic_t': own.get('t_stat')}


def build_decision_board(value, target_date, projection, long_run=None):
    """projection is build_alpha_beta() for the same frozen facts; this adds what to do.
    long_run (from the frozen long backtest) must also support alpha before it is marked tradable."""
    validate_market_returns(value, target_date)
    panel = _panel(value)
    last = len(panel['days']) - 1
    today = _select(panel, last)
    if today is None:
        # Without a complete recent window there is nothing to choose; the page keeps its detail view.
        return None
    rows, summary = walk_forward(panel)
    regime = projection['regime']
    closes = [c for c in panel['market_close'] if c is not None]
    average20 = fsum(closes[-20:]) / 20 if len(closes) >= 20 else None
    market20 = (prod(1 + r / 100 for r in panel['market'][-20:]) - 1) * 100 if None not in panel['market'][-20:] else None
    trend_down = market20 is not None and market20 < 0
    gap20 = (closes[-1] / average20 - 1) * 100 if average20 else None
    buys = [row for row in today['alpha'] if row['status'] == 'buy']
    long_ok = (long_run is None or long_run['alpha_oos_cagr'] is None or long_run['index_oos_cagr'] is None
               or long_run['alpha_oos_cagr'] > long_run['index_oos_cagr'])
    edge = summary['alpha_edge'] and long_ok
    overall, beta_action, alpha_action = _stance(regime, trend_down, edge, len(buys))

    def public(row):
        i = row['index']
        start = last - DEFAULT_WINDOW + 1
        return {**{k: v for k, v in row.items() if k != 'index'}, 'name': panel['names'][i] or '名称待确认',
                'industry': panel['industries'][i] or '行业待确认',
                'daily': [round(r, 4) for r in panel['returns'][i][start:last + 1]]}

    candidates = [public(row) for row in today['alpha']]
    beta_rows = [public(row) for row in today['beta']]
    alpha_basket = buys[:BASKET] or today['alpha'][:BASKET]
    series = projection['series']
    shares = [p['same_share'] for p in series[-3:]]
    turnover = []
    for column, day in enumerate(panel['days']):
        amounts = [a for a in (row[column] for row in panel['amount']) if a is not None]
        turnover.append(fsum(amounts) / 1e5 if amounts else None)
    alpha_stats, beta_stats = summary['alpha'], summary['beta']
    evidence = ('近两个月按同一规则没有出现检查全过的名单，无法检验' if not alpha_stats['dates'] else
                f"近两个月{alpha_stats['dates']}个决策日按同一规则买入“检查全过”名单，5日后扣成本平均相对中证全指"
                f"{alpha_stats['mean_excess']:+.2f}个百分点、跑赢{alpha_stats['hit_rate'] * 100:.0f}%的日期")
    if beta_stats['dates']:
        evidence += f"；贝塔篮子同口径平均{beta_stats['mean_excess']:+.2f}个百分点"
    sync = f"{regime['sync']:.2f}" if regime['sync'] is not None else '待确认'
    same = f"{regime['same_share']:.0f}%" if regime['same_share'] is not None else '待确认比例的'
    reasons = [
        f"大盘带动{regime['strength'] or '待确认'}：近20日共振度{sync}"
        + (f"（近两个月第{round(regime['sync_rank'] * 100)}百分位）" if regime['sync_rank'] is not None else '')
        + f"，今日{same}个股与中证全指同向。",
        (f"大盘方向：中证全指近20日{market20:+.2f}%，收盘较20日均价{gap20:+.2f}%。"
         if market20 is not None and gap20 is not None else '大盘方向：中证全指近20日资料不全。'),
        f"阿尔法证据：{evidence}。",
    ]
    if long_run and long_run['alpha_oos_cagr'] is not None:
        reasons.append(f"长期回测（{long_run['start']}起、设计期前的样本外）：{'当前规则' if long_run.get('strategy') == 'live_rule' else '阿尔法每天买'}年化{long_run['alpha_oos_cagr']:.1f}%，"
                       f"中证全指{long_run['index_oos_cagr']:.1f}%"
                       + (f"；近20日独立收益的IC为{long_run['own_ic']:.3f}（t值{long_run['own_ic_t']:.1f}）" if long_run['own_ic'] is not None else '')
                       + '。')
    triggers = [
        {'text': '同向比例连续3日低于60%（大盘带动减弱）',
         'now': '最近3日 ' + ' / '.join('—' if s is None else f'{s:.0f}%' for s in shares),
         'met': bool(shares) and all(s is not None and s < 60 for s in shares)},
        {'text': '中证全指收盘重新站上20日均价（趋势转好）',
         'now': f'现在{gap20:+.2f}%' if gap20 is not None else '资料不足', 'met': gap20 is not None and gap20 > 0},
        {'text': '显著独立收益只数超过随机预期2倍（阿尔法变多）',
         'now': f"现在{regime['ratio']:.1f}倍" if regime['ratio'] is not None else '资料不足',
         'met': regime['ratio'] is not None and regime['ratio'] >= 2},
    ]
    return {
        'schema': 'decision_board.v1', 'target_date': target_date, 'source_hash': value['artifact_hash'],
        'stance': overall, 'stance_text': STANCE[overall], 'headline': HEADLINES[(overall, alpha_action)],
        'actions': {'beta': BETA_TEXT[beta_action], 'discipline': DISCIPLINE,
                    'alpha': ALPHA_TEXT[alpha_action].format(
                        buys=len(buys), edge=('跑输中证全指' if (alpha_stats['mean_excess'] or 0) <= 0 else '跑赢中证全指')
                        + (f"{abs(alpha_stats['mean_excess']):.2f}个百分点" if alpha_stats['mean_excess'] is not None else ''))},
        'action_keys': {'beta': beta_action, 'alpha': alpha_action},
        'reasons': reasons, 'triggers': triggers, 'long_run': long_run, 'alpha_edge': edge,
        'market': {'return20_pct': market20, 'gap_to_ma20_pct': gap20, 'trend_down': trend_down,
                   'closes': [None if c is None else round(c, 4) for c in panel['market_close']],
                   'turnover_yi': [None if v is None else round(v, 2) for v in turnover], 'dates': panel['days']},
        'candidates': candidates, 'status_counts': {k: sum(c['status'] == k for c in candidates) for k in STATUS},
        'beta_basket': beta_rows,
        'pk': {'alpha': _exposure(alpha_basket, '检查全过阿尔法' if buys else '阿尔法（无检查全过，取前10参考）'),
               'beta': _exposure(today['beta'], '高贝塔'),
               'index': {'label': '中证全指', 'beta': 1.0, 'down_scenario_pct': -SCENARIO_PCT,
                         'up_scenario_pct': SCENARIO_PCT, 'total_pct': market20}},
        'walk_forward': {'rows': rows, 'summary': summary},
        'checks': CHECKS, 'status_names': STATUS,
        'rules': {'liquidity_yi': LIQUIDITY_K / 1e5, 'cost_pct': COST_PCT, 'hold': HOLD, 'basket': BASKET,
                  'scenario_pct': SCENARIO_PCT, 'chase_pct': CHASE_PCT, 'stop_lookback': STOP_LOOKBACK,
                  'stop_max_pct': STOP_MAX_PCT},
    }
