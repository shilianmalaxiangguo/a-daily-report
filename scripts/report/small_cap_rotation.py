"""The execution plan: small-stock rotation, five cold names with growing revenue and profit, every 20 sessions.

Decision days are every 20th trading session counted from 2024-07-01. On a decision day, eligible stocks (not ST,
listed at least 120 days) are ranked by average turnover over the last 20 sessions; in the lowest fifth, keep those
on the main board or ChiNext whose latest quarter announced on or before that day (and after the quarter ended)
shows revenue and profit growth above zero; the five with the lowest turnover are bought at the next open (a name
opening at the limit is skipped for the next one) and held to the close of the next decision day. Since v0.3
(2026-10-31) a name that closes 10% or more above the price paid is sold at the next open and the money waits for
the next rotation (docs/reviews/2026-10-30-wiki-evidence/sell_rules.py, round sixteen); the same plan without that
rule is kept beside it. Net value is reported against ChiNext, the user's anchor, and the CSI All Share.
"""
from datetime import date, timedelta
import json
from pathlib import Path

import numpy as np

from report.fact_utils import evidence_hash

SCHEMA = 'small_cap_plan.v7'
SCHEMAS = ('small_cap_plan.v1', 'small_cap_plan.v2', 'small_cap_plan.v3', 'small_cap_plan.v4', 'small_cap_plan.v5',
           'small_cap_plan.v6', SCHEMA)
# v2 adds the next session, the next decision day and the day the switch trades; v3 lists only boards the account
# can buy, keeping the all-board list for reference; v4 holds five names and tracks the pool and CSI 2000; v5 keeps
# the first published list of a period for the rest of it and works the plan through the user's 10,000-yuan account;
# v6 adds, on days inside a period, the list ranked at today's close for someone starting only now; v7 sells a name
# at the next open after it closes 10% above the price paid and keeps the result without that rule beside it.
SAME_LIST = ('small_cap_plan.v5', 'small_cap_plan.v6', SCHEMA)   # lists made by the same selection rule
TAKE_PROFIT = 0.10               # the user's take-profit line (2026-10-31, v0.3), against the price paid
SELL_FEE = 0.0001 + 0.00001 + 0.0005   # commission, transfer fee and stamp duty on a sale
WEEKDAYS = ('周一', '周二', '周三', '周四', '周五', '周六', '周日')
BARRED = ('688', '689')          # the user's account (2026-10-30): main board and ChiNext, not STAR
BOARDS_TEXT = '主板和创业板'
FLOOR = 0.7                      # the user's floor for the whole account's net value (2026-10-30)
ACCOUNT_YUAN = 10_000.0          # the user's principal (2026-10-30); the plan is worked through it lot by lot
ACCOUNT_FEE = 0.0001 + 0.00001   # commission 0.01% with no minimum (2026-10-31) plus transfer fee, on buying


def board_of(code):
    return '科创板' if code.startswith(('688', '689')) else '创业板' if code.startswith(('300', '301', '302')) else '主板'
ANCHOR = '2024-07-01'
CYCLE = 20
NAMES = 5                        # the user's account (2026-10-31): 10,000 yuan, commission 0.01% with no minimum
BACKUPS = 3
LISTED_DAYS = 120
COST = 0.002
CASH = 0.015 / 252
ROOT = Path(__file__).resolve().parents[2]
HISTORY = ROOT / '.generated/backtest-history'


def _iso(value):
    value = str(value)
    return f'{value[:4]}-{value[4:6]}-{value[6:]}' if len(value) == 8 and value.isdigit() else value


def day_label(day):
    """'11-02（周一）' for an ISO date; None stays None."""
    return f'{day[5:]}（{WEEKDAYS[date.fromisoformat(day).weekday()]}）' if day else None


def growth_records(fina):
    """Per stock, (announcement date, period, revenue growth, profit growth), oldest announcement first."""
    records = {}
    for period, rows in (fina.get('periods') or {}).items():
        for row in rows:
            ann = row.get('ann_date')
            if not ann or ann <= period or row.get('q_sales_yoy') is None or row.get('q_profit_yoy') is None:
                continue
            records.setdefault(row['ts_code'], []).append((_iso(ann), period, float(row['q_sales_yoy']), float(row['q_profit_yoy'])))
    for rows in records.values():
        rows.sort()
    return records


def latest_growth(records, code, day):
    """The latest period announced on or before day, in its latest version known then."""
    best = None
    for ann, period, sales, profit in records.get(code, ()):
        if ann > day:
            break
        if best is None or period >= best[0]:
            best = (period, sales, profit, ann)
    return best


def average_turnover(amount):
    """Mean of the available amounts over sessions t-19..t, aligned on t (NaN before 20 sessions)."""
    filled = np.where(np.isnan(amount), 0, amount)
    total = np.concatenate([np.zeros((amount.shape[0], 1)), np.cumsum(filled, axis=1)], axis=1)
    count = np.concatenate([np.zeros((amount.shape[0], 1)), np.cumsum(~np.isnan(amount), axis=1)], axis=1)
    out = np.full(amount.shape, np.nan)
    window_count = count[:, 20:] - count[:, :-20]
    window_total = total[:, 20:] - total[:, :-20]
    valid = window_count > 0
    values = np.full(window_count.shape, np.nan)
    values[valid] = window_total[valid] / window_count[valid]
    out[:, 19:] = values
    return out


def ranked_names(codes, day, turnover, eligible, records):
    """Cold names with growing revenue and profit, coldest first; with the size of the cold fifth."""
    ok = eligible & ~np.isnan(turnover)
    if not ok.any():
        return [], 0
    cold = np.flatnonzero(ok & (turnover <= np.quantile(turnover[ok], 0.2)))
    passed = []
    for i in cold:
        found = latest_growth(records, codes[i], day)
        if found and found[1] > 0 and found[2] > 0:
            passed.append((turnover[i], int(i), found))
    passed.sort(key=lambda item: (item[0], item[1]))
    return [(i, found) for _, i, found in passed], len(cold)


def _buyable(h, i, t):
    o, pc, c = h['open'][i, t + 1], h['pre'][i, t + 1], h['close'][i, t + 1]
    return not (np.isnan(o) or np.isnan(pc) or np.isnan(c) or (o / pc - 1) * 100 >= h['limit'][i] - 0.2)


def bought(h, ranked, t, names=NAMES):
    """The first `names` names of the list that can be bought at the next open; names=None takes them all (the pool)."""
    picked = []
    candidates = ranked if names is None else ranked[:names + BACKUPS]
    for i, _ in candidates:
        if _buyable(h, i, t):
            picked.append(i)
            if names and len(picked) == names:
                break
    return picked


def _sellable(h, i, d):
    o, pc, c = h['open'][i, d], h['pre'][i, d], h['close'][i, d]
    return not (np.isnan(o) or np.isnan(pc) or np.isnan(c) or (o / pc - 1) * 100 <= -(h['limit'][i] - 0.2))


def held_path(h, i, t, end, take_profit=TAKE_PROFIT, live=False):
    """A name bought at the open of t+1: its value at each close t+1..end (price paid = 1, dividends counted), the
    session it was sold at the open after closing `take_profit` or more above the price paid (None if not sold), and
    whether such a sale is still due. The close of `end` can call for a sale only when live (end is today, inside the
    period); otherwise the rotation takes over there. An open at the limit down or a suspension makes the sale wait."""
    growth = np.where(np.isnan(h['returns'][i]), 0.0, h['returns'][i] / 100)
    line = None if take_profit is None else 1 + take_profit
    value = h['close'][i, t + 1] / h['open'][i, t + 1]
    path, sold = [value], None
    due = line is not None and value >= line and (live or t + 1 < end)
    for d in range(t + 2, end + 1):
        if sold is None and due and _sellable(h, i, d):
            value *= h['open'][i, d] / h['pre'][i, d]
            sold = d
        elif sold is None:
            value *= 1 + growth[d]
            due = due or (line is not None and value >= line and (live or d < end))
        path.append(value)
    return np.array(path), sold, bool(due and sold is None)


def rotation_curve(h, records, start, eligible=None, barred=BARRED, names=NAMES, take_profit=TAKE_PROFIT):
    """Net value of the plan from session `start` (cash until the first decision day), as in the evidence script;
    names on barred boards are passed over (barred=() gives the all-board rule of the evidence script);
    names=None holds the whole pool in equal weights; take_profit=None holds every name to the next decision day."""
    days, n = h['days'], len(h['days'])
    anchor = days.index(ANCHOR)
    turnover = average_turnover(h['amount'])
    growth = np.where(np.isnan(h['returns']), 0.0, h['returns'] / 100)
    eligible = h['eligible'] if eligible is None else eligible
    decisions = [t for t in range(start, n - 1) if (t - anchor) % CYCLE == 0]
    nav = [1.0]
    for _ in range(start, decisions[0] if decisions else n - 1):
        nav.append(nav[-1] * (1 + CASH))
    for k, t in enumerate(decisions):
        end = decisions[k + 1] if k + 1 < len(decisions) else n - 1
        base = nav[-1]
        usable = eligible[:, t] & ~np.isnan(h['close'][:, t])
        ranked = ranked_names(h['codes'], days[t], turnover[:, t], usable, records)[0]
        if barred:
            ranked = [(i, f) for i, f in ranked if not h['codes'][i].startswith(barred)]
        members = bought(h, ranked, t, names)
        if not members:
            nav += [base * (1 + CASH) ** j for j in range(1, end - t + 1)]
            continue
        if take_profit is None:
            value = np.array([h['close'][i, t + 1] / h['open'][i, t + 1] for i in members])
            nav.append(base * (1 - COST / 2) * value.mean())
            for d in range(t + 2, end + 1):
                value = value * (1 + growth[members, d])
                nav.append(base * (1 - COST / 2) * value.mean())
        else:                                 # a sold name's money waits, at no interest, for the next rotation
            paths = np.array([held_path(h, i, t, end, take_profit)[0] for i in members])
            nav += list(base * (1 - COST / 2) * paths.mean(axis=0))
        nav[-1] *= 1 - COST / 2
    return np.array(nav)


def load_inputs(target_date, history=HISTORY):
    """Trading sessions from the anchor, growth records and ChiNext prices, from the local caches."""
    calendar = json.loads((history / 'calendar.json').read_text(encoding='utf-8'))
    sessions = sorted({_iso(r['cal_date']) for r in calendar['rows'] if int(r['is_open']) == 1})
    fina_path, index_path = history / 'fina_indicator.json', history / 'indices.json'
    records = growth_records(json.loads(fina_path.read_text(encoding='utf-8'))) if fina_path.is_file() else {}
    chinext = {}
    if index_path.is_file():
        rows = (json.loads(index_path.read_text(encoding='utf-8')).get('indices') or {}).get('399006.SZ', {}).get('rows') or []
        chinext = {_iso(r['trade_date']): (float(r['open']), float(r['close'])) for r in rows if _iso(r['trade_date']) <= target_date}
    return sessions, records, chinext


def _eligible(value, h, t):
    st = set(value.get('st_codes') or [])
    profile, day = value['profile'], h['days'][t]
    out = np.zeros(len(h['codes']), dtype=bool)
    for i, code in enumerate(h['codes']):
        name, listed = profile['names'][i], profile['list_dates'][i]
        if code in st or name.upper().startswith(('ST', '*ST')) or not listed:
            continue
        out[i] = (date.fromisoformat(listed) + timedelta(days=LISTED_DAYS)).isoformat() <= day
    return out & ~np.isnan(h['close'][:, t])


def _span_return(h, members, t, end):
    growth = np.where(np.isnan(h['returns']), 0.0, h['returns'] / 100)
    value = np.array([h['close'][i, t + 1] / h['open'][i, t + 1] * np.prod(1 + growth[i, t + 2:end + 1]) for i in members])
    return float(value.mean() - 1) * 100, [float(v - 1) * 100 for v in value]


def _last_close(h, i, end):
    seen = np.flatnonzero(~np.isnan(h['close'][i, :end + 1]))
    return float(h['close'][i, seen[-1]]) if len(seen) else None


def _index_return(prices, days, t, end):
    """Open of t+1 to close of end; None when either price is missing."""
    first, last = prices.get(days[t + 1]), prices.get(days[end])
    if not first or not last or not first[0] or not last[1]:
        return None
    return (last[1] / first[0] - 1) * 100


def account_orders(items, price, cash=ACCOUNT_YUAN, names=NAMES):
    """Whole-lot orders down the list: each empty place gets the cash over the empty places; a name whose lot (100
    shares) costs more than that is passed over. price(item) is the price, or None when it cannot be bought."""
    orders, skipped = [], []
    for item in items:
        if len(orders) == names:
            break
        p = price(item)
        if p is None:
            skipped.append({'code': item['code'], 'name': item['name'], 'reason': '开盘涨停或停牌，买不到'})
            continue
        budget = cash / (names - len(orders))
        lots = int(budget // (p * 100))
        while lots > 0 and lots * 100 * p * (1 + ACCOUNT_FEE) > budget:
            lots -= 1
        if not lots:
            skipped.append({'code': item['code'], 'name': item['name'],
                            'reason': f'一手{p * 100:,.0f}元，超过这一份{budget:,.0f}元'})
            continue
        amount = lots * 100 * p
        cash -= amount * (1 + ACCOUNT_FEE)
        orders.append({'code': item['code'], 'name': item['name'], 'price': round(float(p), 3), 'lots': lots,
                       'amount': round(float(amount), 2)})
    return orders, skipped, cash


def load_index(code, target_date, history=HISTORY):
    """{date: (open, close)} of a cached index up to target_date."""
    path = history / 'indices.json'
    if not path.is_file():
        return {}
    rows = (json.loads(path.read_text(encoding='utf-8')).get('indices') or {}).get(code, {}).get('rows') or []
    return {_iso(r['trade_date']): (float(r['open']), float(r['close'])) for r in rows
            if _iso(r['trade_date']) <= target_date and r.get('open') and r.get('close')}


def build_plan(value, target_date, *, sessions, records, chinext, frozen=None, csi2000=None):
    """None with a reason when the calendar or data window cannot place today in the cycle.

    frozen: earlier official plans by date; the first one published for this period (on the decision day or later)
    gives the lists for the rest of the period, so they cannot change from one day's report to the next."""
    from report.small_cap_history import history_from_artifact
    days = value['trade_dates']
    if not sessions or max(sessions) < days[0]:
        return None, '交易日历不全，不能确定换手日'
    if not records:
        return None, '财报增长数据缺失，不能判断股票是否符合条件'
    all_sessions = sorted({s for s in sessions if s >= ANCHOR} | {d for d in days if d >= ANCHOR})
    position = all_sessions.index(target_date)
    since = position % CYCLE
    decision = all_sessions[position - since]
    if decision not in days or days.index(decision) < 19:
        return None, '换手日不在本次行情窗口内，不能排名单'
    h = history_from_artifact(value)
    turnover = average_turnover(h['amount'])
    csi = {r['date']: (r.get('open'), r['close']) for r in value['benchmark']['rows']}

    def names_at(t):
        eligible = _eligible(value, h, t)
        return ranked_names(h['codes'], days[t], turnover[:, t], eligible, records)

    def describe(i, found, t):
        profile = value['profile']
        return {'code': h['codes'][i], 'name': profile['names'][i], 'industry': profile['industries'][i],
                'turnover_yi': round(float(turnover[i, t]) / 1e5, 3), 'close': float(h['close'][i, t]),
                'period': found[0], 'sales_yoy': round(found[1], 2), 'profit_yoy': round(found[2], 2), 'announced': found[3]}

    t = days.index(decision)
    full, cold = names_at(t)
    ranked = [(i, f) for i, f in full if not h['codes'][i].startswith(BARRED)]
    published = None
    for day, earlier in sorted((frozen or {}).items()):
        if (day >= target_date or not isinstance(earlier, dict) or earlier.get('schema') not in SAME_LIST
                or earlier.get('decision_date') != decision):
            continue                          # another period, or a list published under another rule
        try:
            published = validate_plan(earlier, day)
            break
        except ValueError:
            continue
    if published and since:
        index = {code: k for k, code in enumerate(h['codes'])}
        listed = [p for p in published['picks'] + published['backups'] if p['code'] in index]
        ranked = [(index[p['code']], (p['period'], p['sales_yoy'], p['profit_yoy'], p['announced'])) for p in listed]
    switch = position - since + CYCLE
    plan = {'schema': SCHEMA, 'target_date': target_date, 'anchor': ANCHOR, 'cycle': CYCLE, 'decision_date': decision,
            'sessions_since': since, 'sessions_to_next': CYCLE - since,
            'next_session': all_sessions[position + 1] if position + 1 < len(all_sessions) else None,
            'next_decision': all_sessions[switch] if switch < len(all_sessions) else None,
            'next_switch': all_sessions[switch + 1] if switch + 1 < len(all_sessions) else None,
            'cold_basket': published['cold_basket'] if published and since else cold,
            'qualified': published['qualified'] if published and since else len(ranked), 'boards': BOARDS_TEXT,
            'list_source': 'published' if published and since else 'today' if not since else 'recomputed',
            'list_from': published['target_date'] if published and since else None,
            'picks': published['picks'] if published and since else [describe(i, f, t) for i, f in ranked[:NAMES]],
            'backups': published['backups'] if published and since else [describe(i, f, t) for i, f in ranked[NAMES:NAMES + BACKUPS]],
            'all_boards': published['all_boards'] if published and since else [describe(i, f, t) for i, f in full[:NAMES]],
            'holding': None, 'previous': [], 'take_profit': TAKE_PROFIT}
    end = days.index(target_date)
    index = {code: k for k, code in enumerate(h['codes'])}
    listed = [p for p in plan['picks'] + plan['backups'] if p['code'] in index]
    if not since:
        orders, skipped, cash = account_orders(listed, lambda p: float(h['close'][index[p['code']], t]))
        value_pct = None
    else:
        orders, skipped, cash = account_orders(
            listed, lambda p: float(h['open'][index[p['code']], t + 1]) if _buyable(h, index[p['code']], t) else None)
        growth = np.where(np.isnan(h['returns']), 0.0, h['returns'] / 100)
        worth, hold, cash_now = cash, cash, cash
        for o in orders:
            i = index[o['code']]
            path, sold, due = held_path(h, i, t, end, live=True)
            hold += o['amount'] * h['close'][i, t + 1] / h['open'][i, t + 1] * np.prod(1 + growth[i, t + 2:end + 1])
            back = o['amount'] * float(path[-1]) * (1 - SELL_FEE) if sold else 0.0
            worth += back or o['amount'] * float(path[-1])
            cash_now += back
            o.update({'take_profit_price': round(o['price'] * (1 + TAKE_PROFIT), 2), 'last_close': _last_close(h, i, end),
                      'gain_pct': round(float(path[-1] - 1) * 100, 2), 'status': 'sold' if sold else 'due' if due else 'holding',
                      'sold_date': days[sold] if sold else None, 'sold_price': float(h['open'][i, sold]) if sold else None})
        value_pct = round(float(worth / ACCOUNT_YUAN - 1) * 100, 2)
        hold_pct = round(float(hold / ACCOUNT_YUAN - 1) * 100, 2)
    plan['account'] = {'base': ACCOUNT_YUAN, 'priced': 'close' if not since else 'open', 'date': days[t] if not since else days[t + 1],
                       'orders': orders, 'skipped': skipped, 'cash_left': round(float(cash), 2), 'value_pct': value_pct,
                       'take_profit': TAKE_PROFIT}
    if since:
        plan['account'].update({'cash_now': round(float(cash_now), 2), 'value_hold_pct': hold_pct})
    plan['fresh'] = None
    if since:                                 # someone starting inside the period uses the latest close's ranking
        today = [(i, f) for i, f in names_at(end)[0] if not h['codes'][i].startswith(BARRED)]
        picks = [describe(i, f, end) for i, f in today[:NAMES]]
        backups = [describe(i, f, end) for i, f in today[NAMES:NAMES + BACKUPS]]
        orders, skipped, cash = account_orders(picks + backups, lambda p: float(h['close'][index[p['code']], end]))
        plan['fresh'] = {'date': target_date, 'picks': picks, 'backups': backups, 'orders': orders, 'skipped': skipped,
                         'cash_left': round(float(cash), 2)}
    if since and ranked:
        members = bought(h, ranked, t)
        if members:
            basket, each = _span_return(h, members, t, end)
            paths = [held_path(h, i, t, end, live=True) for i in members]
            pool = bought(h, [(i, f) for i, f in full if not h['codes'][i].startswith(BARRED)], t, None)
            pool_pct = _span_return(h, pool, t, end)[0] if pool else None
            plan['holding'] = {'entry_date': days[t + 1], 'names': [value['profile']['names'][i] for i in members],
                               'codes': [h['codes'][i] for i in members],
                               'each_pct': [round(float(path[-1] - 1) * 100, 2) for path, _, _ in paths],
                               'each_hold_pct': [round(x, 2) for x in each],
                               'status': ['sold' if sold else 'due' if due else 'holding' for _, sold, due in paths],
                               'sold_dates': [days[sold] if sold else None for _, sold, _ in paths],
                               'basket_pct': round(float(np.mean([path[-1] for path, _, _ in paths])) * (1 - COST / 2) * 100 - 100, 2),
                               'basket_hold_pct': round((1 + basket / 100) * (1 - COST / 2) * 100 - 100, 2),
                               'pool_pct': None if pool_pct is None else round((1 + pool_pct / 100) * (1 - COST / 2) * 100 - 100, 2),
                               'pool_size': len(pool), 'csi2000_pct': _index_return(csi2000 or {}, days, t, end),
                               'chinext_pct': _index_return(chinext, days, t, end), 'csi_all_pct': _index_return(csi, days, t, end)}
    for back in (1, 2):
        p = t - back * CYCLE
        if p < 19 or p + CYCLE > len(days) - 1:
            continue
        old = [(i, f) for i, f in names_at(p)[0] if not h['codes'][i].startswith(BARRED)]
        members = bought(h, old, p)
        if not members:
            continue
        basket, _ = _span_return(h, members, p, p + CYCLE)
        with_rule = float(np.mean([held_path(h, i, p, p + CYCLE)[0][-1] for i in members]))
        plan['previous'].append({'decision_date': days[p], 'end_date': days[p + CYCLE], 'names': [value['profile']['names'][i] for i in members],
                                 'basket_pct': round(with_rule * (1 - COST / 2) ** 2 * 100 - 100, 2),
                                 'basket_hold_pct': round((1 + basket / 100) * (1 - COST / 2) ** 2 * 100 - 100, 2),
                                 'chinext_pct': _index_return(chinext, days, p, p + CYCLE),
                                 'csi_all_pct': _index_return(csi, days, p, p + CYCLE)})
    plan['artifact_hash'] = evidence_hash(plan)
    return plan, None


def validate_plan(value, target_date):
    if (not isinstance(value, dict) or value.get('schema') not in SCHEMAS or value.get('target_date') != target_date
            or value.get('artifact_hash') != evidence_hash({k: v for k, v in value.items() if k != 'artifact_hash'})):
        raise ValueError('执行计划日期或指纹不符')
    return value


def refresh_plan_inputs(pro, target_date, *, history=HISTORY):
    """Extend the calendar and refresh four reporting periods.

    The latest two ended quarters may not yet be announced at the decision day;
    the previous two preserve the latest information then available on a cold cache.
    """
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from report.market_returns import _pages
    history.mkdir(parents=True, exist_ok=True)
    path = history / 'calendar.json'
    calendar = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {'rows': []}
    last = max((r['cal_date'] for r in calendar['rows']), default=ANCHOR.replace('-', ''))
    ahead = (date.fromisoformat(target_date) + timedelta(days=45)).strftime('%Y%m%d')
    if last < (date.fromisoformat(target_date) + timedelta(days=30)).strftime('%Y%m%d'):
        known = {r['cal_date'] for r in calendar['rows']}
        rows = _pages(pro, 'trade_cal', exchange='SSE', start_date=last, end_date=ahead, fields='cal_date,is_open')
        calendar['rows'] += [r for r in rows if r['cal_date'] not in known]
        calendar['end'] = _iso(max(r['cal_date'] for r in calendar['rows']))
        calendar['calendar_retrieved_at'] = datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
        path.write_text(json.dumps(calendar, ensure_ascii=False), encoding='utf-8')
    fina_path = history / 'fina_indicator.json'
    fina = json.loads(fina_path.read_text(encoding='utf-8')) if fina_path.is_file() else {'periods': {}}
    day = date.fromisoformat(target_date)
    quarter_ends = sorted({f'{y}{md}' for y in (day.year - 1, day.year) for md in ('0331', '0630', '0930', '1231')
                           if f'{y}{md}' < target_date.replace('-', '')})[-4:]
    for period in quarter_ends:
        fina['periods'][period] = _pages(pro, 'fina_indicator_vip', period=period,
                                         fields='ts_code,ann_date,end_date,q_profit_yoy,q_sales_yoy,netprofit_yoy')
    fina['retrieved_at'] = datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
    temporary = fina_path.with_suffix('.tmp')
    temporary.write_text(json.dumps(fina, ensure_ascii=False), encoding='utf-8')
    temporary.replace(fina_path)
    return quarter_ends


def _pct(value):
    return '—' if value is None else f'{value:+.2f}%'


def render_plan(soup, plan, backtest=None):
    def text(tag, content, cls=None):
        node = soup.new_tag(tag, attrs={'class': cls} if cls else {})
        node.string = content
        return node

    section = soup.new_tag('section', attrs={'id': 'daily-plan', 'class': 'sector-daily-section dash-section'})
    section.append(text('h2', '执行计划：小盘轮换'))
    label = day_label(plan.get('next_session'))
    upcoming = f'下一个交易日{label}' if label else '下一个交易日'
    if plan['sessions_since'] == 0:
        status = (f"今天（{plan['decision_date']}）收盘后定了新名单：{upcoming}开盘，卖出上一期不在新名单里的，"
                  '买入新进名单的，还在名单里的不动；开盘涨停买不到、或一手的钱不够的，按顺序用备选补上。')
    else:
        switch = (f"下次在{day_label(plan['next_decision'])}收盘后定新名单，{day_label(plan.get('next_switch')) or '再下一个交易日'}开盘换股"
                  if plan.get('next_decision') else f"再过{plan['sessions_to_next']}个交易日定新名单，次一个交易日开盘换股")
        status = (f"本期名单在{plan['decision_date']}收盘后定下，今天是持有的第{plan['sessions_since']}个交易日，"
                  f"{upcoming}是第{plan['sessions_since'] + 1}个；{switch}。" + (
                      f"期间不补买，名单每天显示的都是这一期定下的那{len(plan['picks'])}只；持有的股票收盘比买价高10%，下一个交易日开盘卖，卖出的钱留到下一个换手日。"
                      if plan.get('take_profit') else f"期间不加不减，名单每天显示的都是这一期定下的那{len(plan['picks'])}只。"))
    section.append(text('p', status, 'dash-takeaway'))
    due = [o for o in (plan.get('account') or {}).get('orders') or [] if o.get('status') == 'due']
    if due and plan['sessions_since']:
        names = '、'.join(f"{o['name']}（{_pct(o['gain_pct'])}）" for o in due)
        section.append(text('p', f"单期模拟今天收盘到了止盈线：{names}；若真实持仓和原始买价一致，规则是在{upcoming}开盘卖，钱留到下一个换手日。", 'dash-takeaway dash-plan-due'))
    if not plan['picks']:
        section.append(text('p', '本期冻结名单为空，须先核对财报与行情覆盖；不据此推断真实账户应当空仓。'))
    rows = soup.new_tag('table', attrs={'class': 'dash-table dash-table-compact'})
    head = soup.new_tag('tr')
    for label in ('', '股票', '板块', '行业', '20日日均成交额（亿）', '最近一季收入同比', '最近一季利润同比', '报告期', '定名单时收盘', '一手约（元）'):
        head.append(text('th', label))
    thead = soup.new_tag('thead')
    thead.append(head)
    rows.append(thead)
    body = soup.new_tag('tbody')
    for role, items in (('名单', plan['picks']), ('备选', plan['backups'])):
        for item in items:
            row = soup.new_tag('tr', attrs={'class': 'dash-row-plan' if role == '名单' else 'dash-row-backup'})
            for cell in (role, f"{item['name']} {item['code']}", board_of(item['code']), item['industry'] or '—', f"{item['turnover_yi']:.2f}",
                         f"{item['sales_yoy']:+.1f}%", f"{item['profit_yoy']:+.1f}%", item['period'], f"{item['close']:.2f}",
                         f"{item['close'] * (200 if item['code'].startswith(('688', '689')) else 100):,.0f}"):
                row.append(text('td', cell))
            body.append(row)
    rows.append(body)
    wrap = soup.new_tag('div', attrs={'class': 'table-responsive'})
    wrap.append(rows)
    section.append(wrap)
    skipped = [p for p in plan.get('all_boards') or [] if p['code'].startswith(BARRED)]
    if skipped:
        section.append(text('p', f"按全部板块排，前{len(plan['all_boards'])}名里有科创板的{'、'.join(p['name'] for p in skipped)}；你的账户买不了科创板，"
                                 '已跳过、按顺序往下取。用科创板指数基金顶替的做法检验过，相关历史比较已归档，当前不采用。', 'dash-note'))
    elif plan.get('all_boards') is not None:
        section.append(text('p', f"按全部板块排的前{len(plan['all_boards'])}名里没有科创板股票，名单与不限板块时相同。", 'dash-note'))
    source = {'published': f"名单取自{plan.get('list_from') or plan['decision_date']}发布的日报，整期不变。",
              'recomputed': f"{plan['decision_date']}当天没有发布执行计划，名单按当时可知的数据回算；期间若有股票被戴帽，回算结果会和当天不同。"}
    if plan.get('list_source') in source:
        section.append(text('p', source[plan['list_source']], 'dash-note'))
    holding = plan.get('holding')
    if holding:
        pool = (f"股票池（{holding['pool_size']}只等权）{_pct(holding['pool_pct'])}、中证2000{_pct(holding.get('csi2000_pct'))}、"
                if 'pool_pct' in holding else '')
        shadow = f"，不止盈为{_pct(holding['basket_hold_pct'])}" if holding.get('basket_hold_pct') is not None else ''
        section.append(text('p', f"本期等权模拟买入（{holding['entry_date']}开盘）：{'、'.join(holding['names'])}；到今天收盘合计{_pct(holding['basket_pct'])}"
                             f"（{'按止盈10%，' if plan.get('take_profit') else ''}已扣买入成本{shadow}），同期{pool}创业板指{_pct(holding['chinext_pct'])}、中证全指{_pct(holding['csi_all_pct'])}。"))
    if account := plan.get('account'):
        section.append(_account_block(soup, text, plan, account))
    if fresh := plan.get('fresh'):
        section.append(_fresh_block(soup, text, plan, fresh))
    for item in plan['previous']:
        shadow = f"，不止盈为{_pct(item['basket_hold_pct'])}" if item.get('basket_hold_pct') is not None else ''
        section.append(text('p', f"按规则回算的上一期（{item['decision_date']}定名单，持有到{item['end_date']}）：{'、'.join(item['names'])}，"
                             f"合计{_pct(item['basket_pct'])}{f'（按止盈10%{shadow}）' if plan.get('take_profit') else ''}，同期创业板指{_pct(item['chinext_pct'])}、中证全指{_pct(item['csi_all_pct'])}。"
                             '这一功能上线前没有当期冻结的名单，这一行是用当时可知的数据回算的。', 'dash-note'))
    periods = (backtest or {}).get('plan_periods')
    if periods:
        section.append(_period_table(soup, text, periods, (backtest or {}).get('style_check')))
    section.append(text('small', f"规则：每{plan['cycle']}个交易日一次（从{plan['anchor']}起数），在非ST、上市满120天的股票里，取近20日日均成交额最小的五分之一"
                         f"（本期{plan['cold_basket']}只），只留最近一季收入和利润同比都为正的{('、在' + plan['boards'] + '里') if plan.get('boards') else ''}（{plan['qualified']}只），按成交额从小到大取前{len(plan['picks']) or NAMES}只；"
                         '定名单那天收盘后出新名单，下一个交易日开盘卖出不在新名单里的、买入新进的，名单里没变的不动；'
                         f"怎么买：用来做这个计划的钱分成{len(plan['picks']) or NAMES}份，按名单顺序买，每只用“现金÷还空着的名额”；"
                         '一手（100股）的钱超过这一份就跳过，用下一只补；已经拿着、还在名单里的不动，也不补到等额。'
                         + ('持有期间：收盘比买价高10%（含分红送转），下一个交易日开盘卖，卖出的钱留到下一个换手日，这一期不再买回；'
                            '不设止损，被戴帽也不单独卖，到换手日自然换掉；' if plan.get('take_profit') else '持有期间不设止损；')
                         + f"整个账户净值跌破{FLOOR}就全部停下重新检验。"
                         '完整比较见独立回测报告；日报单期演示不代表连续账户或真实成交。'))
    return section


def _period_table(soup, text, periods, style):
    """Plan, pool, CSI 2000 and ChiNext per period, and whether the pool still beats small caps."""
    box = soup.new_tag('div', attrs={'class': 'dash-plan-periods'})
    box.append(text('h3', '对照记账：名单、股票池、小盘指数与创业板指'))
    table = soup.new_tag('table', attrs={'class': 'dash-table dash-table-compact'})
    head = soup.new_tag('tr')
    shadow = any(item.get('plan_hold_pct') is not None for item in periods)
    for label in ('定名单', '到', '名单（按规则）') + (('不止盈（对照）',) if shadow else ()) + ('股票池（等权）', '中证2000', '创业板指', '名单减股票池', '股票池减中证2000'):
        head.append(text('th', label))
    thead = soup.new_tag('thead')
    thead.append(head)
    table.append(thead)
    body = soup.new_tag('tbody')
    for item in periods:
        row = soup.new_tag('tr', attrs={'class': 'dash-row-period' + (' dash-row-current' if item.get('current') else '')})
        gap = lambda a, b: '—' if a is None or b is None else f"{a - b:+.2f}个百分点"
        for cell in (item['decision_date'], item['end_date'] + ('（进行中）' if item.get('current') else ''), _pct(item['plan_pct']),
                     *((_pct(item.get('plan_hold_pct')),) if shadow else ()),
                     _pct(item['pool_pct']), _pct(item['csi2000_pct']), _pct(item['chinext_pct']),
                     gap(item['plan_pct'], item['pool_pct']), gap(item['pool_pct'], item['csi2000_pct'])):
            row.append(text('td', cell))
        body.append(row)
    table.append(body)
    wrap = soup.new_tag('div', attrs={'class': 'table-responsive'})
    wrap.append(table)
    box.append(wrap)
    if style:
        line = (f"最近{style['periods']}期：股票池有{style['pool_beat_csi2000']}期跑赢中证2000，累计多{_pp(style['pool_minus_csi2000_pp'])}；"
                f"名单比股票池累计{_pp(style['plan_minus_pool_pp'])}。")
        if style['warning']:
            line += '股票池最近几期累计跑输中证2000：冷门股的优势可能在消失，或者市场风格在切换。按规则下一个换手日前复核，不急着加钱。'
        else:
            line += '股票池仍跑赢中证2000，说明这个条件还在起作用；名单和股票池的差距主要是只数少带来的运气。'
        box.append(text('p', line, 'dash-takeaway'))
    box.append(text('small', '按规则回算：每期都按收盘排名单、下一个交易日开盘买、到下一个换手日收盘，每期来回0.2%；名单按止盈10%（收盘比买价高10%，次日开盘卖，钱留到期末），'
                             '不止盈是同一份名单一直拿到期末的对照；股票池是同一天符合条件、开盘能买到的全部股票等额。'
                             '名单减股票池看是运气还是规则，股票池减中证2000看这个选股条件还灵不灵。', 'dash-note'))
    return box


def _pp(value):
    return '—' if value is None else f'{value:+.2f}个百分点'


def _account_block(soup, text, plan, account):
    """The plan worked through the user's 10,000 yuan: lots, names passed over, cash left and the result so far."""
    box = soup.new_tag('div', attrs={'class': 'dash-plan-account'})
    box.append(text('h3', f"{account['base']:,.0f}元整手单期模拟（万一免五）"))
    box.append(text('small', '佣金为成交额0.01%，无最低收费；过户费另计0.001%，卖出另计0.05%印花税。', 'dash-note'))
    table = soup.new_tag('table', attrs={'class': 'dash-table dash-table-compact'})
    head = soup.new_tag('tr')
    tracked = account['priced'] == 'open' and 'cash_now' in account
    for label in ('股票', '开盘价' if account['priced'] == 'open' else '收盘价（估算）', '买几手', '金额（元）') + (
            ('止盈价（买价×1.1）', '今天收盘', '买入以来', '状态') if tracked else ()):
        head.append(text('th', label))
    thead = soup.new_tag('thead')
    thead.append(head)
    table.append(thead)
    body = soup.new_tag('tbody')
    upcoming = day_label(plan.get('next_session')) or '下一个交易日'
    for o in account['orders']:
        cells = (f"{o['name']} {o['code']}", f"{o['price']:.2f}", f"{o['lots']}手（{o['lots'] * 100}股）", f"{o['amount']:,.0f}")
        if tracked:
            status = {'holding': '拿着', 'due': f'今天收盘到止盈线，{upcoming}开盘卖',
                      'sold': f"{(o.get('sold_date') or '')[5:]}开盘已止盈卖出（{o.get('sold_price') or 0:.2f}元）"}[o['status']]
            cells += (f"{o['take_profit_price']:.2f}", '—' if o['last_close'] is None else f"{o['last_close']:.2f}", _pct(o['gain_pct']), status)
        row = soup.new_tag('tr', attrs={'class': 'dash-row-order' + {'sold': ' dash-row-sold', 'due': ' dash-row-due'}.get(o.get('status'), '')})
        for cell in cells:
            row.append(text('td', cell))
        body.append(row)
    table.append(body)
    wrap = soup.new_tag('div', attrs={'class': 'table-responsive'})
    wrap.append(table)
    box.append(wrap)
    held = [o for o in account['orders'] if o.get('status') != 'sold'] if tracked else []
    if held:
        due = [o['name'] for o in held if o['status'] == 'due']
        tail = f"今天收盘到线的：{'、'.join(due)}，{upcoming}开盘卖。" if due else '今天收盘都没有到。'
        prices = '、'.join(f"{o['name']}{o['take_profit_price']:.2f}元" for o in held)
        box.append(text('p', f"止盈价（买价×1.1）：{prices}；{tail}", 'dash-takeaway dash-plan-lines'))
    if account['skipped']:
        box.append(text('p', '跳过：' + '；'.join(f"{s['name']}（{s['reason']}）" for s in account['skipped']) + '，按顺序用下一只补上。', 'dash-note'))
    if account['priced'] == 'close':
        line = (f"按今天收盘价估算，实际以{day_label(plan.get('next_session')) or '下一个交易日'}开盘价为准；"
                f"买完约剩现金{account['cash_left']:,.0f}元。")
    elif tracked:
        sold = [o for o in account['orders'] if o['status'] == 'sold']
        line = (f"{account['date']}开盘照规则下单，买完剩现金{account['cash_left']:,.0f}元；"
                + (f"已止盈卖出{len(sold)}只，现金合计{account['cash_now']:,.0f}元，留到下一个换手日；" if sold else '')
                + f"到今天收盘，这1万元合计{_pct(account['value_pct'])}（含现金，已扣已发生的买卖费用；不止盈为{_pct(account['value_hold_pct'])}）。")
    else:
        line = (f"{account['date']}开盘照规则下单，买完剩现金{account['cash_left']:,.0f}元；"
                f"到今天收盘，这1万元合计{_pct(account['value_pct'])}（含剩余现金，已扣买入费用）。")
    box.append(text('p', line, 'dash-takeaway'))
    if tracked:
        box.append(text('small', '“买入以来”和状态按含分红送转的涨幅算；遇到除权除息，止盈价要按除权后的价格重算，以状态这一列为准。', 'dash-note'))
    box.append(text('small', '本表每期按1万元重新起算，未承接上期现金、旧仓和原买价，未实现跨期净值底线卖出流程；不是实际持仓或连续账户。止盈提示须核对真实原买价，不能直接当成账户卖出指令。等权模拟与整手单期模拟的成本和金额口径不同。', 'dash-note'))
    return box


def _fresh_block(soup, text, plan, fresh):
    """For someone starting inside the period: the list ranked at today's close and the 10,000-yuan orders for it."""
    box = soup.new_tag('div', attrs={'class': 'dash-plan-fresh'})
    upcoming = day_label(plan.get('next_session')) or '下一个交易日'
    box.append(text('h3', f"这一期中途才开始的：用{fresh['date']}收盘重新排的名单"))
    box.append(text('p', f"已经在拿的，继续拿上面这一期的名单，不跟着换。第一次买的，{upcoming}开盘按下面这份买，拿到下一个换股日"
                         f"（{day_label(plan.get('next_switch')) or '下一个换股日'}）再按正常节奏换。回测里中途开始时，用最新一天收盘排的名单，"
                         '平均每次多0.3至0.4个百分点，四组结果方向一致，但差距在误差之内。', 'dash-takeaway'))
    listed = {p['code'] for p in plan['picks']}
    table = soup.new_tag('table', attrs={'class': 'dash-table dash-table-compact'})
    head = soup.new_tag('tr')
    for label in ('', '股票', '板块', '最近一季（公告日）', '收盘价', '和本期名单比', '1万元估算'):
        head.append(text('th', label))
    thead = soup.new_tag('thead')
    thead.append(head)
    table.append(thead)
    body = soup.new_tag('tbody')
    lots = {o['code']: o for o in fresh['orders']}
    skips = {s['code']: s for s in fresh['skipped']}
    for role, items in (('名单', fresh['picks']), ('备选', fresh['backups'])):
        for item in items:
            row = soup.new_tag('tr', attrs={'class': 'dash-row-fresh' if role == '名单' else 'dash-row-fresh-backup'})
            order = lots.get(item['code'])
            plan_cell = (f"买{order['lots']}手，约{order['amount']:,.0f}元" if order else
                         ('跳过：' + skips[item['code']]['reason']) if item['code'] in skips else '—')
            for cell in (role, f"{item['name']} {item['code']}", board_of(item['code']),
                         f"收入{item['sales_yoy']:+.1f}%、利润{item['profit_yoy']:+.1f}%（{item['announced']}）", f"{item['close']:.2f}",
                         '本期也有' if item['code'] in listed else '新进', plan_cell):
                row.append(text('td', cell))
            body.append(row)
    table.append(body)
    wrap = soup.new_tag('div', attrs={'class': 'table-responsive'})
    wrap.append(table)
    box.append(wrap)
    box.append(text('small', f"按今天收盘价估算，实际以{upcoming}开盘价为准；买完约剩现金{fresh['cash_left']:,.0f}元。", 'dash-note'))
    return box
