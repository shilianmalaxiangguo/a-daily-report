"""Quant-style backtest of the decision-board rules over a long daily history.

Signals on day t use only sessions up to t and the same definitions as the daily board:
20-session market model with Vasicek-shrunk beta, the six buying-qualification checks,
the high-beta basket and the regime stance. Trades: buy at the next open (no limit-up or
>3% gap opens), sell at the fifth session's close, or at the next open after a close below
the exit level; limit-down opens cannot be sold. Ten equal slots, 0.2% round-trip cost.
Strategies are a fixed, pre-declared set; none is selected after the fact. Each is compared with holding
the CSI All Share, ChiNext and STAR 50, with the daily-rebalanced equal-weight average, and with the same
execution applied to names drawn at random (20 seeds).
"""
from datetime import date, timedelta
import hashlib
import json
from math import sqrt
from pathlib import Path
import re

import numpy as np

WINDOW = 20
T_CRIT = 2.1009
HOLD = 5
SLOTS = 10
BUY_COST = 0.00075        # commission + slippage
SELL_COST = 0.00125       # commission + stamp duty + slippage
CHASE = 3.0
LIMIT_MARGIN = 0.2
LIQUIDITY_K = 100_000.
STOP_LOOKBACK = 10
STOP_MAX = 15.0
REGIME_POINTS = 42
LISTED_DAYS = 120
MIN_COMPLETE = 20
A_SHARE = re.compile(r'(6\d{5}\.SH|[03]\d{5}\.SZ)')
STRATEGIES = {
    'alpha': '检查全过阿尔法，每天按规则买',
    'alpha_regime': '检查全过阿尔法，防守期不买',
    'beta': '高贝塔篮子，每天按规则买',
    'beta_offense': '高贝塔篮子，只在进攻期买',
    'stance': '按总体建议轮换（进攻买贝塔、均衡买阿尔法、防守空仓）',
    'live_rule': '当前规则（进攻买贝塔；其余只在阿尔法近期有优势时买；否则空仓）',
    'index': '中证全指持有',
}
EDGE_DATES = 37
SCHEMA = 'strategy_backtest.v4'           # v4: the plan sells at the next open after a close 10% above the price paid; plan_hold keeps it without
COMPARISONS = {'399006.SZ': '创业板指', '000688.SH': '科创50', '932000.CSI': '中证2000'}
NULL_SEEDS = 20


def _iso(value):
    value = str(value)
    return f'{value[:4]}-{value[4:6]}-{value[6:8]}' if len(value) == 8 and value.isdigit() else value


def load_history(cache_root, days, benchmark_rows, basics_rows, namechange_rows):
    """Matrices (stock × session) from cached explicit-date pages; missing stays NaN."""
    pages, digest = {}, hashlib.sha256()
    for day in days:
        raw = (Path(cache_root) / f'{day}.json').read_bytes()
        digest.update(day.encode() + hashlib.sha256(raw).digest())
        pages[day] = json.loads(raw)
    codes = sorted({r['ts_code'] for p in pages.values() for r in p['rows'] if A_SHARE.fullmatch(r.get('ts_code') or '')})
    index = {c: i for i, c in enumerate(codes)}
    shape = (len(codes), len(days))
    close, pre, opened, amount = (np.full(shape, np.nan) for _ in range(4))
    for j, day in enumerate(days):
        for r in pages[day]['rows']:
            i = index.get(r.get('ts_code'))
            if i is None:
                continue
            c, p, o, s = r.get('close'), r.get('pre_close'), r.get('open'), r.get('pct_chg')
            if not (isinstance(c, (int, float)) and isinstance(p, (int, float)) and c > 0 and p > 0):
                continue
            if isinstance(s, (int, float)) and abs((c - p) / p * 100 - s) > 0.011:
                continue
            close[i, j], pre[i, j] = c, p
            if isinstance(o, (int, float)) and o > 0:
                opened[i, j] = o
            if isinstance(r.get('amount'), (int, float)) and r['amount'] >= 0:
                amount[i, j] = r['amount']
    bench = {_iso(r['trade_date']): r for r in benchmark_rows}
    m_close = np.array([bench[d]['close'] if d in bench else np.nan for d in days], dtype=float)
    m_pre = np.array([bench[d]['pre_close'] if d in bench else np.nan for d in days], dtype=float)
    m_open = np.array([bench[d]['open'] if d in bench and bench[d].get('open') else np.nan for d in days], dtype=float)
    listed = {r['ts_code']: _iso(r['list_date']) for r in basics_rows if r.get('list_date')}
    st = np.zeros(shape, dtype=bool)
    for r in namechange_rows:
        i = index.get(r.get('ts_code'))
        name = str(r.get('name') or '').upper()
        if i is None or not name.lstrip('S*').startswith('ST') and not name.startswith(('ST', '*ST', 'SST', 'S*ST')):
            continue
        start = _iso(r.get('start_date') or '00000000')
        end = _iso(r.get('end_date')) if r.get('end_date') else '9999-12-31'
        for j, day in enumerate(days):
            if start <= day <= end:
                st[i, j] = True
    old_enough = np.zeros(shape, dtype=bool)
    for i, code in enumerate(codes):
        listed_on = listed.get(code)
        if not listed_on:
            continue
        cutoff = (date.fromisoformat(listed_on) + timedelta(days=LISTED_DAYS)).isoformat()
        old_enough[i] = [day >= cutoff for day in days]
    returns = (close - pre) / pre * 100
    m_ret = (m_close - m_pre) / m_pre * 100
    limit = np.array([20. if c.startswith(('300', '301', '688', '689')) else 10. for c in codes])
    return {'days': list(days), 'codes': codes, 'close': close, 'pre': pre, 'open': opened, 'amount': amount,
            'returns': returns, 'm_ret': m_ret, 'm_open': m_open, 'm_close': m_close, 'm_pre': m_pre,
            'eligible': ~st & old_enough, 'limit': limit, 'inputs_sha256': digest.hexdigest()}


def _rolling(values, valid, window):
    filled = np.where(valid, values, 0.)
    cs = np.concatenate([np.zeros((values.shape[0], 1)), np.cumsum(filled, axis=1)], axis=1)
    return cs[:, window:] - cs[:, :-window]


def signals(h):
    """Per-session vectors of everything the board uses, computed with only past sessions."""
    Y, X = h['returns'], h['m_ret'][None, :]
    valid = ~np.isnan(Y) & ~np.isnan(X)
    Xb = np.broadcast_to(X, Y.shape)
    W = WINDOW
    n = _rolling(np.ones_like(Y), valid, W)
    sx, sy = _rolling(Xb, valid, W), _rolling(Y, valid, W)
    sxx, syy, sxy = _rolling(Xb * Xb, valid, W), _rolling(Y * Y, valid, W), _rolling(Xb * Y, valid, W)
    growth = _rolling(np.log1p(np.where(valid, Y, 0.) / 100), valid, W)
    down = valid & (Xb < 0)
    s_down, n_down = _rolling(Y, down, W), _rolling(np.ones_like(Y), down, W)
    sy5, sx5 = _rolling(Y, valid, 5), _rolling(Xb, valid, 5)
    sy3 = _rolling(Y, valid, 3)
    amount_valid = ~np.isnan(h['amount'])
    amt_sum, amt_n = _rolling(h['amount'], amount_valid, W), _rolling(np.ones_like(Y), amount_valid, W)
    # Align every rolling window on its last session: index k corresponds to session k + W - 1.
    off5, off3 = W - 5, W - 3
    sy5, sx5, sy3 = sy5[:, off5:], sx5[:, off5:], sy3[:, off3:]
    with np.errstate(invalid='ignore', divide='ignore'):
        vx = sxx - sx * sx / W
        vy = syy - sy * sy / W
        cxy = sxy - sx * sy / W
        beta = cxy / vx
        corr = np.clip(cxy / np.sqrt(vx * vy), -1, 1)
        resid = np.maximum(vy - beta * cxy, 0) / (W - 2)
        se_beta = np.sqrt(resid / vx)
        t_corr = corr * np.sqrt((W - 2) / (1 - corr * corr))
    sessions = Y.shape[1]
    out = {k: np.full(Y.shape, np.nan) for k in ('beta', 'r2', 't_alpha', 'total', 'own5', 'down_mean', 'accel',
                                                   'spike', 'amount', 'own')}
    out['complete'] = np.zeros(Y.shape, dtype=bool)
    out['n_down'] = np.zeros(Y.shape)
    for k in range(sessions - W + 1):
        t = k + W - 1
        ok = (n[:, k] == W) & h['eligible'][:, t] & (vx[:, k] > 1e-12)
        if not ok.any():
            continue
        b = beta[ok, k]
        mean, var = b.mean(), b.var(ddof=1) if b.size > 1 else 0.
        se2 = se_beta[ok, k] ** 2
        weight = np.where(var + se2 > 0, var / (var + se2), 1.)
        shrunk = weight * b + (1 - weight) * mean
        mx, my = sx[ok, k] / W, sy[ok, k] / W
        intercept = my - shrunk * mx
        res = np.maximum(vy[ok, k] - 2 * shrunk * cxy[ok, k] + shrunk ** 2 * vx[ok, k], 0) / (W - 2)
        se = np.sqrt(res * (1 / W + mx ** 2 / vx[ok, k]))
        with np.errstate(invalid='ignore', divide='ignore'):
            out['t_alpha'][ok, t] = np.where(se > 0, intercept / se, np.nan)
            out['down_mean'][ok, t] = np.where(n_down[ok, k] > 0, s_down[ok, k] / np.maximum(n_down[ok, k], 1), np.nan)
        out['beta'][ok, t] = shrunk
        out['r2'][ok, t] = np.where(vy[ok, k] > 1e-12, corr[ok, k] ** 2, 0.)
        out['total'][ok, t] = (np.exp(growth[ok, k]) - 1) * 100
        out['own'][ok, t] = sy[ok, k] - shrunk * sx[ok, k]
        out['own5'][ok, t] = sy5[ok, k] - shrunk * sx5[ok, k]
        std = np.sqrt(np.maximum(vy[ok, k], 0) / (W - 1))
        out['accel'][ok, t] = sy3[ok, k] - 3 * my
        out['spike'][ok, t] = 2 * std * sqrt(3)
        out['amount'][ok, t] = amt_sum[ok, k] / np.maximum(amt_n[ok, k], 1)
        out['n_down'][ok, t] = n_down[ok, k]
        out['complete'][ok, t] = True
        tcorr = np.where(vy[ok, k] > 1e-12, t_corr[ok, k], np.nan)
        out.setdefault('t_corr', np.full(Y.shape, np.nan))[ok, t] = tcorr
    return out


def _rolling_min(values, window):
    result = np.full(values.shape, np.nan)
    for t in range(values.shape[1]):
        block = values[:, max(0, t - window + 1):t + 1]
        with np.errstate(all='ignore'):
            result[:, t] = np.where(np.all(np.isnan(block), axis=1), np.nan, np.nanmin(np.where(np.isnan(block), np.inf, block), axis=1))
    return result


def daily_choices(h, s):
    """Alpha buy lists, beta baskets and stance for every session, from past data only."""
    days, sessions = h['days'], len(h['days'])
    stop_level = _rolling_min(h['close'], STOP_LOOKBACK)
    syncs, choices = [], []
    for t in range(sessions):
        complete = s['complete'][:, t]
        if complete.sum() < MIN_COMPLETE:
            syncs.append(np.nan)
            choices.append(None)
            continue
        ta, total, tcorr = s['t_alpha'][:, t], s['total'][:, t], s['t_corr'][:, t]
        alpha_up = complete & (ta >= T_CRIT) & (total > 0)
        resilient = complete & (ta >= T_CRIT) & (total <= 0)
        beta_label = complete & (np.abs(ta) < T_CRIT) & (tcorr >= T_CRIT)
        liquid = s['amount'][:, t] >= LIQUIDITY_K
        buyable = h['returns'][:, t] < h['limit'] - LIMIT_MARGIN
        distance = (stop_level[:, t] / h['close'][:, t] - 1) * 100
        checks = (alpha_up & (s['own5'][:, t] > 0) & ((s['n_down'][:, t] == 0) | (s['down_mean'][:, t] >= 0))
                  & (s['accel'][:, t] < s['spike'][:, t]) & (distance >= -STOP_MAX) & liquid & buyable)
        buys = np.flatnonzero(checks)
        buys = buys[np.argsort(-ta[buys], kind='stable')]
        bets = np.flatnonzero(beta_label & liquid & buyable)
        bets = bets[np.argsort(-s['beta'][bets, t], kind='stable')][:SLOTS]
        sync = float(np.median(s['r2'][complete, t]))
        syncs.append(sync)
        recent = [v for v in syncs[-REGIME_POINTS:] if not np.isnan(v)]
        rank = sum(v <= sync for v in recent) / len(recent) if len(recent) >= 20 else None
        strength = None if rank is None else '强' if rank >= 2 / 3 else '弱' if rank <= 1 / 3 else '中'
        ratio = (alpha_up.sum() + resilient.sum()) / (complete.sum() * 0.025)
        if strength is None:
            verdict = None
        elif strength == '强' and ratio < 2:
            verdict = 'beta'
        elif strength == '弱' and ratio >= 1:
            verdict = 'alpha'
        else:
            verdict = 'mixed'
        window = h['m_ret'][max(0, t - WINDOW + 1):t + 1]
        trend20 = (np.prod(1 + window / 100) - 1) * 100 if t >= WINDOW - 1 and not np.isnan(window).any() else np.nan
        stance = ('defense' if verdict == 'beta' and trend20 < 0 else 'offense' if verdict == 'beta'
                  else 'balanced' if verdict else None)
        choices.append({'alpha': buys, 'beta': bets, 'stance': stance, 'stop': stop_level[:, t], 'sync': sync,
                        'trend20': trend20, 'verdict': verdict})
    return choices


def _picks(strategy, choice):
    if choice is None or choice['stance'] is None:
        return np.array([], dtype=int)
    stance = choice['stance']
    if strategy == 'alpha':
        return choice['alpha']
    if strategy == 'alpha_regime':
        return choice['alpha'] if stance != 'defense' else np.array([], dtype=int)
    if strategy == 'beta':
        return choice['beta']
    if strategy == 'beta_offense':
        return choice['beta'] if stance == 'offense' else np.array([], dtype=int)
    if strategy == 'stance':
        return (choice['beta'] if stance == 'offense' else choice['alpha'] if stance == 'balanced'
                else np.array([], dtype=int))
    if strategy == 'live_rule':
        alpha = choice['alpha'] if choice.get('edge') else np.array([], dtype=int)
        return np.concatenate([choice['beta'], alpha]) if stance == 'offense' else alpha
    raise ValueError(strategy)


def _basket_forward(h, members, t):
    """Equal-weight next-open-to-fifth-close return after cost; None when nothing could be bought."""
    if t + HOLD >= len(h['days']):
        return None
    values = []
    for i in list(members)[:SLOTS]:
        o, pc, c = h['open'][i, t + 1], h['pre'][i, t + 1], h['close'][i, t + 1]
        chain = h['returns'][i, t + 2:t + HOLD + 1]
        if np.isnan(o) or np.isnan(pc) or np.isnan(c) or np.isnan(chain).any():
            continue
        gap = (o / pc - 1) * 100
        if gap >= h['limit'][i] - LIMIT_MARGIN or gap > CHASE:
            continue
        values.append((c / o * np.prod(1 + chain / 100) - 1) * 100)
    return float(np.mean(values)) - (BUY_COST + SELL_COST) * 100 if values else None


def mark_edges(h, choices):
    """The board's recent-edge test at each session, using only holding periods already finished."""
    index_fwd, alpha_fwd = {}, {}
    for t, choice in enumerate(choices):
        if choice is None or t + HOLD >= len(h['days']):
            continue
        m = h['m_ret'][t + 2:t + HOLD + 1]
        if not np.isnan(h['m_open'][t + 1]) and not np.isnan(m).any():
            index_fwd[t] = (h['m_close'][t + 1] / h['m_open'][t + 1] * np.prod(1 + m / 100) - 1) * 100
        value = _basket_forward(h, choice['alpha'], t)
        if value is not None:
            alpha_fwd[t] = value
    for t, choice in enumerate(choices):
        if choice is None:
            continue
        done = [d for d in range(max(0, t - HOLD - EDGE_DATES + 1), t - HOLD + 1) if d in alpha_fwd and d in index_fwd]
        excess = [alpha_fwd[d] - index_fwd[d] for d in done]
        choice['edge'] = len(excess) >= 5 and np.mean(excess) > 0 and np.mean([e > 0 for e in excess]) >= 0.5


def simulate(h, choices, strategy, start):
    """Event-driven daily simulation; returns equity by session, closed trades and invested share."""
    days, sessions = h['days'], len(h['days'])
    cash, equity, positions, trades, exposure = 1.0, [], [], [], []
    orders, exits = [], set()          # orders: (stock, money, exit level) chosen at yesterday's close

    def close_trade(position, value, day, reason):
        trades.append({'code': position['code'], 'entry': position['entry'], 'exit': day, 'reason': reason,
                       'cost_basis': position['cost_basis'], 'exit_value': value})

    for d in range(start, sessions):
        kept = []
        for position in positions:
            i = position['i']
            if i in exits:
                o, pc = h['open'][i, d], h['pre'][i, d]
                if not np.isnan(o) and not np.isnan(pc) and (o / pc - 1) * 100 > -(h['limit'][i] - LIMIT_MARGIN):
                    value = position['value'] * o / pc * (1 - SELL_COST)
                    cash += value
                    close_trade(position, value, days[d], position['exit_reason'])
                    continue
            kept.append(position)
        positions, exits = kept, set()
        held = {position['i'] for position in positions}
        for i, money, level in orders:
            o, pc = h['open'][i, d], h['pre'][i, d]
            if i in held or len(positions) >= SLOTS or np.isnan(o) or np.isnan(pc) or cash < money * 0.5:
                continue
            gap = (o / pc - 1) * 100
            if gap >= h['limit'][i] - LIMIT_MARGIN or gap > CHASE:
                continue
            spend = min(money, cash)
            cash -= spend
            positions.append({'i': i, 'code': h['codes'][i], 'entry': days[d], 'entry_index': d, 'open': o,
                              'cost_basis': spend, 'value': spend * (1 - BUY_COST), 'stop': level})
            held.add(i)
        for position in positions:
            i = position['i']
            c, pc = h['close'][i, d], h['pre'][i, d]
            if not np.isnan(c) and not np.isnan(pc):
                position['value'] *= c / position['open'] if position['entry_index'] == d else c / pc
        kept = []
        for position in positions:
            i = position['i']
            due = d - position['entry_index'] + 1 >= HOLD
            r, c = h['returns'][i, d], h['close'][i, d]
            if due and not np.isnan(r) and r > -(h['limit'][i] - LIMIT_MARGIN):
                value = position['value'] * (1 - SELL_COST)
                cash += value
                close_trade(position, value, days[d], 'time')
                continue
            if due:
                exits.add(i)
                position['exit_reason'] = 'time'
            elif not np.isnan(c) and not np.isnan(position['stop']) and c < position['stop']:
                exits.add(i)
                position['exit_reason'] = 'stop'
            kept.append(position)
        positions = kept
        value = cash + sum(position['value'] for position in positions)
        equity.append(value)
        exposure.append(1 - cash / value if value > 0 else 0.)
        picks = _picks(strategy, choices[d])
        free = SLOTS - len(positions) + len(exits)
        stops = choices[d]['stop'] if choices[d] is not None else None
        orders = [(int(i), value / SLOTS, float(stops[i]) if stops is not None else np.nan)
                  for i in list(picks)[:max(free, 0) + 3]]
    for position in positions:
        trades.append({'code': position['code'], 'entry': position['entry'], 'exit': None, 'reason': 'open',
                       'cost_basis': position['cost_basis'], 'exit_value': position['value']})
    return np.array(equity), trades, np.array(exposure)


def _metrics(curve, days, exposure=None, trades=None):
    curve = np.asarray(curve, dtype=float)
    daily = curve[1:] / curve[:-1] - 1
    years = len(daily) / 252
    total = curve[-1] / curve[0] - 1
    peak = np.maximum.accumulate(curve)
    drawdown = curve / peak - 1
    out = {'total_pct': total * 100, 'cagr_pct': ((curve[-1] / curve[0]) ** (1 / years) - 1) * 100 if years > 0 else None,
           'vol_pct': float(daily.std(ddof=1) * sqrt(252) * 100) if len(daily) > 1 else None,
           'sharpe': float(daily.mean() / daily.std(ddof=1) * sqrt(252)) if len(daily) > 1 and daily.std(ddof=1) > 0 else None,
           'max_drawdown_pct': float(drawdown.min() * 100), 'sessions': len(curve)}
    if out['cagr_pct'] is not None and out['max_drawdown_pct'] < 0:
        out['calmar'] = out['cagr_pct'] / abs(out['max_drawdown_pct'])
    if exposure is not None and len(exposure):
        out['exposure_pct'] = float(np.mean(exposure) * 100)
    if trades is not None:
        closed = [t for t in trades if t['reason'] != 'open']
        returns = [t['exit_value'] / t['cost_basis'] - 1 for t in closed]
        out.update(trades=len(closed), win_rate=(sum(r > 0 for r in returns) / len(returns)) if returns else None,
                   avg_trade_pct=float(np.mean(returns) * 100) if returns else None,
                   stop_exits=sum(t['reason'] == 'stop' for t in closed))
    return out


def information_coefficients(h, s, start):
    """Daily Spearman rank IC of signals against next-open-to-fifth-close returns."""
    days, sessions = h['days'], len(h['days'])
    fwd = np.full(h['returns'].shape, np.nan)
    for t in range(start, sessions - HOLD):
        entry = h['close'][:, t + 1] / h['open'][:, t + 1]
        chain = np.prod(1 + h['returns'][:, t + 2:t + HOLD + 1] / 100, axis=1)
        fwd[:, t] = (entry * chain - 1) * 100
    def rank(a):
        order = a.argsort(kind='stable')
        ranks = np.empty(len(a))
        ranks[order] = np.arange(len(a))
        return ranks
    result = {}
    for name in ('own', 'own5', 't_alpha', 'beta'):
        ics, spreads = [], []
        for t in range(start, sessions - HOLD):
            ok = s['complete'][:, t] & ~np.isnan(fwd[:, t]) & ~np.isnan(s[name][:, t])
            if ok.sum() < 200:
                continue
            x, y = s[name][ok, t], fwd[ok, t]
            ics.append(float(np.corrcoef(rank(x), rank(y))[0, 1]))
            q = np.quantile(x, [0.2, 0.8])
            spreads.append(float(y[x >= q[1]].mean() - y[x <= q[0]].mean()))
        ics = np.array(ics)
        n_eff = max(len(ics) / HOLD, 1)
        result[name] = {'days': len(ics), 'mean_ic': float(ics.mean()) if len(ics) else None,
                        'ic_std': float(ics.std(ddof=1)) if len(ics) > 1 else None,
                        'icir': float(ics.mean() / ics.std(ddof=1)) if len(ics) > 1 and ics.std(ddof=1) > 0 else None,
                        't_stat': float(ics.mean() / (ics.std(ddof=1) / sqrt(n_eff))) if len(ics) > 1 and ics.std(ddof=1) > 0 else None,
                        'positive_share': float((ics > 0).mean()) if len(ics) else None,
                        'top_minus_bottom_pct': float(np.mean(spreads)) if spreads else None}
    return result


def _period_stats(curve, days, split, full):
    out = {'full': full}
    if 2 < split < len(days) - 2:
        out['out_of_sample'] = _metrics(curve[:split + 1], days[:split + 1])
        out['design_period'] = _metrics(curve[split:], days[split:])
    years = {}
    for year in sorted({d[:4] for d in days}):
        idx = [k for k, d in enumerate(days) if d[:4] == year]
        first = idx[0] - 1 if idx[0] > 0 else idx[0]
        years[year] = float((curve[idx[-1]] / curve[first] - 1) * 100)
    out['years'] = years
    return out


def equal_weight_curve(h, start):
    """Every eligible stock at the same weight, rebalanced daily, no cost: a reference, not a tradable result."""
    r = np.where(h['eligible'] & ~np.isnan(h['returns']), h['returns'], np.nan)
    with np.errstate(all='ignore'):
        daily = np.nanmean(r, axis=0)[start + 1:] / 100
    return np.concatenate([[1.0], np.cumprod(1 + np.where(np.isnan(daily), 0., daily))])


def _spread(values):
    values = [v for v in values if v is not None]
    if not values:
        return {'median': None, 'min': None, 'max': None}
    return {'median': float(np.median(values)), 'min': float(min(values)), 'max': float(max(values))}


def random_null(h, s, choices, start, seeds=NULL_SEEDS):
    """The same execution, slots and costs with names drawn at random from the pool every list draws from."""
    days, result, curves = h['days'][start:], {}, {}
    for name, field, strategy in (('random', 'alpha', 'alpha'), ('random_offense', 'beta', 'beta_offense')):
        runs, paths = [], []
        for seed in range(seeds):
            rng = np.random.default_rng(seed)
            drawn = []
            for t, choice in enumerate(choices):
                if choice is None:
                    drawn.append(None)
                    continue
                pool = np.flatnonzero(s['complete'][:, t] & (s['amount'][:, t] >= LIQUIDITY_K)
                                      & (h['returns'][:, t] < h['limit'] - LIMIT_MARGIN))
                drawn.append({**choice, field: rng.permutation(pool)[:SLOTS + 3]})
            curve, trades, exposure = simulate(h, drawn, strategy, start)
            runs.append(_metrics(curve, days, exposure, trades))
            paths.append(curve)
        result[name] = {metric: _spread([r.get(metric) for r in runs])
                        for metric in ('cagr_pct', 'max_drawdown_pct', 'sharpe', 'exposure_pct')}
        result[name]['cagr_runs'] = [None if r.get('cagr_pct') is None else float(r['cagr_pct']) for r in runs]
        curves[name] = np.median(np.vstack(paths), axis=0)
    result['seeds'] = seeds
    return result, curves


def plan_periods(h, curves, start, recent=6):
    """Per period of the plan's schedule: plan, pool, CSI 2000 and ChiNext (decision-day close to the next one);
    the last `recent` complete periods and the one in progress, plus whether the pool still beats small caps."""
    from report.small_cap_rotation import ANCHOR, CYCLE
    days = h['days']
    anchor = days.index(ANCHOR)
    marks = [t for t in range(max(start, anchor), len(days)) if (t - anchor) % CYCLE == 0]
    if not marks:
        return None, None
    ends = marks[1:] + ([len(days) - 1] if marks[-1] < len(days) - 1 else [])

    def change(key, a, b):
        curve = curves.get(key)
        if curve is None:
            return None
        return round(float(curve[b - start] / curve[a - start] - 1) * 100, 2)

    rows = [{'decision_date': days[a], 'end_date': days[b], 'current': (k == len(marks) - 1),
             'plan_pct': change('small_cap_plan', a, b), 'plan_hold_pct': change('small_cap_plan_hold', a, b),
             'pool_pct': change('small_cap_pool', a, b),
             'csi2000_pct': change('932000.CSI', a, b), 'chinext_pct': change('399006.SZ', a, b)}
            for k, (a, b) in enumerate(zip(marks, ends))]
    done = [r for r in rows if not r['current']][-recent:]
    shown = done + [r for r in rows if r['current']]
    if not done or any(r[key] is None for r in done for key in ('plan_pct', 'pool_pct', 'csi2000_pct')):
        return shown, None
    grow = lambda key: float(np.prod([1 + r[key] / 100 for r in done]))
    style = {'periods': len(done), 'pool_beat_csi2000': int(sum(r['pool_pct'] > r['csi2000_pct'] for r in done)),
             'pool_minus_csi2000_pp': round((grow('pool_pct') - grow('csi2000_pct')) * 100, 2),
             'plan_minus_pool_pp': round((grow('plan_pct') - grow('pool_pct')) * 100, 2)}
    style['warning'] = bool(style['pool_minus_csi2000_pp'] < 0)
    return shown, style


def run_backtest(h, *, design_start='2026-07-28', comparisons=None, null_seeds=NULL_SEEDS, plan_records=None):
    """comparisons: {code: {'name', 'closes': {date: close}}}; an index missing any session is left out.
    plan_records: growth records for the execution plan (small_cap_rotation); without them the plan is left out."""
    s = signals(h)
    choices = daily_choices(h, s)
    mark_edges(h, choices)
    start = next(t for t, c in enumerate(choices) if c is not None and c['stance'] is not None)
    days = h['days'][start:]
    curves, stats, trades_out = {}, {}, {}
    for strategy in STRATEGIES:
        if strategy == 'index':
            curve = h['m_close'][start:] / h['m_close'][start]
            curves[strategy] = curve
            stats[strategy] = {'full': _metrics(curve, days)}
            continue
        curve, trades, exposure = simulate(h, choices, strategy, start)
        curves[strategy] = curve
        stats[strategy] = {'full': _metrics(curve, days, exposure, trades)}
        trades_out[strategy] = trades
    split = days.index(next(d for d in days if d >= design_start)) if any(d >= design_start for d in days) else len(days)
    for strategy, curve in curves.items():
        stats[strategy] = _period_stats(curve, days, split, stats[strategy]['full'])
    compared, missing = {}, []
    for code, item in (comparisons or {}).items():
        closes = np.array([item['closes'].get(d, np.nan) for d in days], dtype=float)
        if np.isnan(closes).any() or not closes[0] > 0:
            missing.append(item['name'])
            continue
        curves[code] = closes / closes[0]
        compared[code] = {'name': item['name'], **_period_stats(curves[code], days, split, _metrics(curves[code], days))}
    curves['equal_weight'] = equal_weight_curve(h, start)
    compared['equal_weight'] = {'name': '等权平均持有全部可交易A股', **_period_stats(
        curves['equal_weight'], days, split, _metrics(curves['equal_weight'], days))}
    null, null_curves = random_null(h, s, choices, start, null_seeds)
    curves.update(null_curves)
    plan = plan_hold = pool = periods = style = None
    if plan_records and '2024-07-01' in h['days']:
        from report.small_cap_rotation import NAMES, rotation_curve
        curves['small_cap_plan'] = rotation_curve(h, plan_records, start)
        plan = {'name': f'执行计划：小盘轮换（{NAMES}只，主板和创业板，止盈10%）', **_period_stats(curves['small_cap_plan'], days, split,
                                                                               _metrics(curves['small_cap_plan'], days))}
        curves['small_cap_plan_hold'] = rotation_curve(h, plan_records, start, take_profit=None)
        plan_hold = {'name': '执行计划不止盈（对照）', **_period_stats(curves['small_cap_plan_hold'], days, split,
                                                                     _metrics(curves['small_cap_plan_hold'], days))}
        curves['small_cap_pool'] = rotation_curve(h, plan_records, start, names=None, take_profit=None)
        pool = {'name': '股票池：主板和创业板里冷门且业绩增长的全部股票（等权）',
                **_period_stats(curves['small_cap_pool'], days, split, _metrics(curves['small_cap_pool'], days))}
        anchor = compared.get('399006.SZ')
        if anchor:
            plan['beats_chinext'] = bool(plan['full']['cagr_pct'] > anchor['full']['cagr_pct']
                                         and plan['full']['max_drawdown_pct'] > anchor['full']['max_drawdown_pct'])
        periods, style = plan_periods(h, curves, start)
    for name, key in (('random', 'alpha'), ('random', 'beta'), ('random', 'live_rule'), ('random_offense', 'beta_offense')):
        target = stats[key]['full']['cagr_pct']
        null[name].setdefault('runs_at_least', {})[key] = (None if target is None else
                                                           int(sum(v is not None and v >= target for v in null[name]['cagr_runs'])))
    stance_days = {k: sum(c is not None and c['stance'] == k for c in choices[start:]) for k in ('defense', 'balanced', 'offense')}
    stance_days['alpha_edge'] = sum(c is not None and bool(c.get('edge')) for c in choices[start:])
    return {'schema': SCHEMA, 'start': days[0], 'end': days[-1], 'sessions': len(days),
            'design_start': design_start, 'strategies': STRATEGIES, 'stats': stats,
            'comparisons': compared, 'missing_comparisons': missing, 'null': null, 'plan': plan, 'plan_hold': plan_hold, 'pool': pool,
            'plan_periods': periods, 'style_check': style,
            'curves': {k: [round(float(v), 6) for v in c] for k, c in curves.items()}, 'dates': days,
            'stance_days': stance_days, 'ic': information_coefficients(h, s, start),
            'rules': {'window': WINDOW, 'hold': HOLD, 'slots': SLOTS, 'buy_cost_pct': BUY_COST * 100,
                      'sell_cost_pct': SELL_COST * 100, 'chase_pct': CHASE, 'stop_lookback': STOP_LOOKBACK,
                      'stop_max_pct': STOP_MAX, 'liquidity_yi': LIQUIDITY_K / 1e5, 'listed_days': LISTED_DAYS},
            'inputs_sha256': h['inputs_sha256'], 'universe': len(h['codes'])}, s, choices, trades_out


from report.small_cap_history import history_from_artifact
