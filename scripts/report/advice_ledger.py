"""Freeze each day's advice and later reconcile it with what prices actually did.

A record states what the board said on day D with only the facts known on D. Reconciliation
uses a later day's frozen full-market prices: next-open entry, fifth-session close exit, stop
breaches along the way, against 中证全指 over the same sessions. Records are never rewritten.
"""
from math import prod

from report.market_returns import price_rows
from report.sector_reading_history import evidence_hash

SCHEMA = 'advice_record.v1'
HOLD = 5


def build_record(target_date, board, interpretation=None, plan=None):
    chosen = interpretation['samples'][interpretation['chosen']] if interpretation else None
    value = {
        'schema': SCHEMA, 'target_date': target_date, 'rules': board['schema'],
        'stance': board['stance_text'], 'beta_action': board['action_keys']['beta'],
        'alpha_action': board['action_keys']['alpha'],
        'buy': [{'code': c['code'], 'name': c['name'], 'close': c['close'], 'stop': c['stop']}
                for c in board['candidates'] if c['status'] == 'buy'],
        'beta': [{'code': c['code'], 'name': c['name']} for c in board['beta_basket']],
        'interpretation_stance': chosen['stance'] if chosen else None,
        'interpretation_headline': chosen['headline'] if chosen else None,
    }
    if plan:
        value['plan'] = {'decision_date': plan['decision_date'], 'sessions_since': plan['sessions_since'],
                         'picks': [p['code'] for p in plan['picks']], 'backups': [p['code'] for p in plan['backups']],
                         'holding': (plan.get('holding') or {}).get('codes')}
    value['artifact_hash'] = evidence_hash(value)
    return value


def validate_record(value, target_date=None):
    if (not isinstance(value, dict) or value.get('schema') != SCHEMA
            or value.get('artifact_hash') != evidence_hash({k: v for k, v in value.items() if k != 'artifact_hash'})
            or target_date is not None and value.get('target_date') != target_date):
        raise ValueError('建议记录日期或指纹不符')
    return value


def history_from_snapshots(snapshots, target_date):
    """Earlier official snapshots' frozen records; a malformed one is skipped and reported."""
    records, problems = [], []
    for snapshot in snapshots:
        record = (snapshot.get('data') or {}).get('reading_decision_record')
        if record is None or snapshot.get('date', '') >= target_date:
            continue
        try:
            records.append(validate_record(record, snapshot['date']))
        except ValueError:
            problems.append(snapshot['date'])
    value = {'schema': 'advice_history.v1', 'target_date': target_date,
             'records': sorted(records, key=lambda r: r['target_date']), 'problems': problems}
    value['artifact_hash'] = evidence_hash(value)
    return value


def validate_history(value, target_date):
    if (not isinstance(value, dict) or value.get('schema') != 'advice_history.v1' or value.get('target_date') != target_date
            or value.get('artifact_hash') != evidence_hash({k: v for k, v in value.items() if k != 'artifact_hash'})
            or any(r['target_date'] >= target_date for r in value['records'])):
        raise ValueError('建议历史日期或指纹不符')
    for record in value['records']:
        validate_record(record)
    return value


def reconcile(history, market):
    """Outcomes of earlier records that have a full holding period inside the frozen prices."""
    days = market['trade_dates']
    position = {d: k for k, d in enumerate(days)}
    codes = {c: i for i, c in enumerate(market['codes'])}
    table = {}
    for k, day in enumerate(days):
        for i, close, previous, opened, _ in price_rows(market, day):
            table[(i, k)] = (close, previous, opened)
    bench = {row['date']: row for row in market['benchmark']['rows']}

    def stock_path(code, t):
        i = codes.get(code)
        if i is None or (i, t + 1) not in table:
            return None
        close, previous, opened = table[(i, t + 1)]
        if opened is None:
            return None
        level, closes = close / opened, [close]
        for s in range(t + 2, t + HOLD + 1):
            if (i, s) not in table:
                return None
            c, p, _ = table[(i, s)]
            level *= c / p
            closes.append(c)
        return (level - 1) * 100, closes

    rows = []
    for record in history['records']:
        t = position.get(record['target_date'])
        if t is None or t + HOLD >= len(days):
            rows.append({'date': record['target_date'], 'stance': record['stance'], 'status': '未满5日'})
            continue
        b1 = bench.get(days[t + 1])
        if b1 is None or not b1.get('open'):
            index = None
        else:
            index = (b1['close'] / b1['open'] * prod(bench[days[s]]['close'] / bench[days[s]]['pre_close']
                                                       for s in range(t + 2, t + HOLD + 1)) - 1) * 100
        picks = []
        for item in record['buy']:
            result = stock_path(item['code'], t)
            if result is None:
                continue
            ret, closes = result
            picks.append({'code': item['code'], 'name': item['name'], 'return_pct': ret,
                          'stopped': any(c < item['stop'] for c in closes)})
        betas = [r for item in record['beta'] if (r := stock_path(item['code'], t)) is not None]
        rows.append({'date': record['target_date'], 'stance': record['stance'], 'status': '已对账',
                     'exit_date': days[t + HOLD], 'index_pct': index, 'picks': picks,
                     'alpha_pct': sum(p['return_pct'] for p in picks) / len(picks) if picks else None,
                     'beta_pct': sum(r for r, _ in betas) / len(betas) if betas else None,
                     'stopped': sum(p['stopped'] for p in picks),
                     'interpretation_stance': record.get('interpretation_stance')})
    return rows
