"""Append-only, fractional-unit forward tracking, independent of any real account.

The user fixes the initial five names. Only subsequent rotation dates use the
current v0.3 shortlist. Each day consumes the preceding trading day's record.
"""
from copy import deepcopy
from datetime import datetime
from html import escape
import json
import math
from zoneinfo import ZoneInfo

from report.fact_utils import evidence_hash
from report.market_returns import _pages, price_rows, sessions_from_calendar
from report.small_cap_rotation import ANCHOR, CYCLE, NAMES, BACKUPS, ACCOUNT_FEE, SELL_FEE, TAKE_PROFIT, FLOOR

SCHEMA = 'small_cap_tracking.v1'
FACTS = 'small_cap_tracking_facts.v1'
MODEL = {'strategy': 'small-cap-v0.3', 'sizing': 'fractional-budget',
         'buy_fee': ACCOUNT_FEE, 'sell_fee': SELL_FEE, 'take_profit': TAKE_PROFIT,
         'floor': FLOOR, 'anchor': ANCHOR, 'cycle': CYCLE, 'names': NAMES, 'backups': BACKUPS,
         'adjustment': 'previous-close/pre-close total-return units', 'cash_interest': 0, 'slippage': 0}


def signed(value):
    value['artifact_hash'] = evidence_hash(value)
    return value


def checked(value, schema, day):
    if (not isinstance(value, dict) or value.get('schema') != schema or value.get('date') != day
            or value.get('artifact_hash') != evidence_hash({k: v for k, v in value.items() if k != 'artifact_hash'})):
        raise ValueError('连续模拟日期、版本或指纹不符，停止生成')
    return value


def positive(value):
    if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError('连续模拟价格缺失或无效，停止生成')
    return float(value)


def load_seed(root):
    path = root / 'config/small-cap-tracking.json'
    if not path.is_file():
        return None
    seed = json.loads(path.read_text(encoding='utf-8'))
    items = seed.get('positions', [])
    if (seed.get('schema') != 'small_cap_tracking_seed.v1' or seed.get('initial_nav') != 1
            or len(items) != NAMES or len({p['code'] for p in items}) != NAMES
            or any(p.get('weight') != .2 for p in items)):
        raise ValueError('连续模拟起点与五只等额配置不符')
    datetime.fromisoformat(seed['start_date'])
    return seed


def directory(root, snapshot_source='official'):
    if snapshot_source not in ('official', 'replay', 'rebuilt'):
        raise ValueError('连续模拟快照来源无效')
    base = root / 'snapshots/small-cap/tracking'
    return base if snapshot_source == 'official' else base / snapshot_source


def is_switch(day, sessions):
    i = sessions.index(day) - sessions.index(ANCHOR)
    return i > 0 and (i - 1) % CYCLE == 0


def required_items(seed, previous, plan, switch):
    items = seed['positions'] if previous is None else previous['positions']
    result = {p['code']: {'code': p['code'], 'name': p['name']} for p in items}
    if switch and previous is not None and not previous['stopped']:
        for p in plan['picks'][:NAMES] + plan['backups'][:BACKUPS]:
            result[p['code']] = {'code': p['code'], 'name': p['name']}
    return result


def collect_facts(pro, data, day, items, root, *, snapshot_source='official'):
    """Freeze only dated prices, exact price limits and opening suspensions."""
    market = data['reading_market_returns']
    bars = {market['codes'][i]: {'open': o, 'close': c, 'pre_close': p}
            for i, c, p, o, _ in price_rows(market, day) if market['codes'][i] in items}
    limits, suspensions = {}, {}
    for endpoint, dest in [('stk_limit', limits), ('suspend_d', suspensions)]:
        for row in _pages(pro, endpoint, trade_date=day.replace('-', '')):
            if row.get('trade_date') != day.replace('-', ''):
                raise ValueError('连续模拟成交条件不是目标日，停止生成')
            code = row.get('ts_code')
            if code not in items:
                continue
            if code in dest and dest[code] != row:
                raise ValueError('连续模拟同日成交条件冲突，停止生成')
            dest[code] = row
    quotes = {}
    for code in items:
        suspension = suspensions.get(code, {})
        timing = suspension.get('suspend_timing') or ''
        suspended = suspension.get('suspend_type') == 'S'
        whole_day = suspended and timing in ('', '全天')
        blocked = suspended and (whole_day or str(timing).startswith(('09:25', '09:30')))
        bar = bars.get(code)
        if bar is None and not whole_day:
            raise ValueError(f'{code} 行情缺失且无全日停牌事实，停止连续模拟')
        limit = limits.get(code)
        if not blocked and limit is None:
            raise ValueError(f'{code} 涨跌停价格缺失，停止连续模拟')
        quotes[code] = {'bar': bar, 'opening_suspended': blocked, 'whole_day_suspended': whole_day,
                        'up_limit': limit.get('up_limit') if limit else None,
                        'down_limit': limit.get('down_limit') if limit else None}
    benchmarks = {}
    for row in market['benchmark']['rows']:
        if row['date'] == day:
            benchmarks['000985.CSI'] = {'name': '中证全指', 'open': row.get('open'), 'close': row['close']}
    path = root / '.generated/backtest-history/indices.json'
    indices = json.loads(path.read_text(encoding='utf-8')).get('indices', {}) if path.is_file() else {}
    for code, name in [('399006.SZ', '创业板指'), ('932000.CSI', '中证2000')]:
        for row in indices.get(code, {}).get('rows', []):
            if row['trade_date'] == day.replace('-', ''):
                benchmarks[code] = {'name': name, 'open': row.get('open'), 'close': row['close']}
    return signed({'schema': FACTS, 'date': day, 'quotes': quotes, 'benchmarks': benchmarks,
                   'snapshot_source': snapshot_source,
                   'market_hash': market['artifact_hash'], 'plan_hash': data['reading_small_cap_plan']['artifact_hash'],
                   'source': 'tushare.daily + stk_limit + suspend_d + index_daily',
                   'market_retrieved_at': market['retrieved_at'],
                   'retrieved_at': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()})


def validate_facts(facts, data, day, items, *, snapshot_source='official'):
    checked(facts, FACTS, day)
    stamp = datetime.fromisoformat(facts['retrieved_at'])
    if (stamp.tzinfo is None or stamp.date().isoformat() < day
            or stamp > datetime.now(ZoneInfo('Asia/Shanghai'))
            or facts['market_hash'] != data['reading_market_returns']['artifact_hash']
            or facts['plan_hash'] != data['reading_small_cap_plan']['artifact_hash']
            or facts.get('snapshot_source') != snapshot_source
            or set(facts['quotes']) != set(items)):
        raise ValueError('连续模拟事实来源或取得时间不符，停止生成')
    for quote in facts['quotes'].values():
        if quote['bar'] is None:
            if not quote['whole_day_suspended'] or not quote['opening_suspended']:
                raise ValueError('行情缺失不能当作停牌，停止生成')
        else:
            for field in ('open', 'close', 'pre_close'):
                positive(quote['bar'][field])
        if not quote['opening_suspended']:
            if positive(quote['down_limit']) >= positive(quote['up_limit']):
                raise ValueError('涨跌停价格相互矛盾，停止生成')
    return facts


def advance(seed, previous, facts, plan, sessions):
    """One trading day; no network, files, old account table or fresh ranking."""
    day = facts['date']
    if ((previous is None and day != seed['start_date'])
            or (previous is not None and previous['date'] != sessions[sessions.index(day) - 1])):
        raise ValueError('连续模拟必须承接前一交易日，不能重新起算')
    if previous and previous['snapshot_source'] != facts['snapshot_source']:
        raise ValueError('连续模拟不能承接另一快照来源的记录')
    switch = is_switch(day, sessions)
    if switch and previous is not None and plan['decision_date'] != sessions[sessions.index(day) - 1]:
        raise ValueError('换手日没有上一交易日的新名单，停止连续模拟')
    positions = deepcopy(previous['positions']) if previous else []
    cash = previous['cash'] if previous else 1.0
    stopped = previous['stopped'] if previous else False
    events, fees, reserved = [], 0.0, 0.0
    closed = set(previous['closed_codes']) if previous and not switch else set()
    picks = {p['code'] for p in plan['picks'][:NAMES]}
    for p in positions:
        q = facts['quotes'][p['code']]
        if q['bar']:
            p['units'] *= p['last_close'] / q['bar']['pre_close']
        if stopped:
            p['pending'] = 'floor'
        elif switch and p['code'] in picks and p['pending'] == 'rotation':
            p['pending'] = None
        elif switch and p['code'] not in picks and not p['pending']:
            p['pending'] = 'rotation'
    retained = []
    for p in positions:
        q, reason = facts['quotes'][p['code']], p['pending']
        bar = q['bar']
        if reason and not q['opening_suspended'] and bar and bar['open'] > q['down_limit'] + 1e-9:
            amount = p['units'] * bar['open']
            fee = amount * SELL_FEE
            cash += amount - fee
            fees += fee
            closed.add(p['code'])
            if reason == 'take_profit':
                reserved += amount - fee
            events.append({'action': 'sell', 'code': p['code'], 'name': p['name'], 'reason': reason,
                           'price': bar['open'], 'amount': amount, 'fee': fee})
        else:
            if reason:
                events.append({'action': 'wait', 'code': p['code'], 'name': p['name'], 'reason': reason})
            retained.append(p)
    positions = retained

    def buy(item, budget):
        nonlocal cash, fees
        q = facts['quotes'][item['code']]
        bar = q['bar']
        if q['opening_suspended'] or not bar or bar['open'] >= q['up_limit'] - 1e-9:
            events.append({'action': 'skip', 'code': item['code'], 'name': item['name']})
            return
        amount = budget / (1 + ACCOUNT_FEE)
        if amount <= 1e-12:
            return
        fee = amount * ACCOUNT_FEE
        cash -= amount + fee
        fees += fee
        positions.append({'code': item['code'], 'name': item['name'], 'entry_date': day,
                          'entry_price': bar['open'], 'entry_amount': amount, 'units': amount / bar['open'],
                          'last_close': bar['open'], 'pending': None})
        events.append({'action': 'buy', 'code': item['code'], 'name': item['name'],
                       'price': bar['open'], 'amount': amount, 'fee': fee})

    if previous is None:
        for item in seed['positions']:
            buy(item, item['weight'])
    elif switch and not stopped:
        sold_today = {e['code'] for e in events if e['action'] == 'sell'}
        for item in plan['picks'][:NAMES] + plan['backups'][:BACKUPS]:
            held = {p['code'] for p in positions}
            if len(held) == NAMES:
                break
            if item['code'] in held or item['code'] in sold_today:
                continue
            buy(item, max(0.0, cash - reserved) / (NAMES - len(held)))
    nav = cash
    for p in positions:
        bar = facts['quotes'][p['code']]['bar']
        if bar:
            p['last_close'] = bar['close']
        p['value'] = p['units'] * p['last_close']
        p['gain_pct'] = (p['value'] / p['entry_amount'] - 1) * 100
        p['take_profit_price'] = p['entry_amount'] * (1 + TAKE_PROFIT) / p['units']
        if p['pending'] in (None, 'rotation') and p['value'] >= p['entry_amount'] * (1 + TAKE_PROFIT) - 1e-12:
            p['pending'] = 'take_profit'
        nav += p['value']
    if nav < FLOOR and not stopped:
        stopped = True
        events.append({'action': 'stop', 'reason': 'floor'})
        for p in positions:
            p['pending'] = 'floor'
    if cash < -1e-10 or not math.isfinite(nav) or nav <= 0:
        raise ValueError('连续模拟现金或净值无效，停止生成')
    benchmarks = deepcopy(previous['benchmarks']) if previous else {}
    for code, name in [('399006.SZ', '创业板指'), ('932000.CSI', '中证2000'), ('000985.CSI', '中证全指')]:
        quote = facts.get('benchmarks', {}).get(code)
        item = benchmarks.setdefault(code, {'name': name, 'entry_open': None, 'nav': None})
        if previous is None and quote and quote.get('open'):
            item['entry_open'] = positive(quote['open'])
        item['nav'] = positive(quote['close']) / item['entry_open'] if quote and item['entry_open'] else None
    decision_today = plan.get('sessions_since') == 0
    return signed({'schema': SCHEMA, 'date': day, 'seed_hash': evidence_hash(seed), 'model': MODEL,
                   'snapshot_source': facts['snapshot_source'],
                   'previous_hash': previous['artifact_hash'] if previous else None, 'facts_hash': facts['artifact_hash'],
                   'plan_hash': plan['artifact_hash'], 'start_date': seed['start_date'], 'initial_nav': 1.0,
                   'cash': max(0.0, cash), 'nav': nav, 'positions': positions, 'events': events,
                   'fees_total': (previous['fees_total'] if previous else 0) + fees, 'fees_today': fees,
                   'stopped': stopped, 'closed_codes': sorted(closed), 'benchmarks': benchmarks,
                   'next_decision': plan['decision_date'] if decision_today else plan.get('next_decision'),
                   'next_switch': plan.get('next_session') if decision_today else plan.get('next_switch')})


def prepare(data, day, *, root, allow_collect=False, pro=None, snapshot_source='official'):
    seed = load_seed(root)
    if seed is None or day < seed['start_date']:
        return None
    rows = json.loads((root / '.generated/backtest-history/calendar.json').read_text(encoding='utf-8'))['rows']
    sessions_from_calendar([r for r in rows if r['cal_date'] <= day.replace('-', '')], day, count=1)
    sessions = sorted({f"{r['cal_date'][:4]}-{r['cal_date'][4:6]}-{r['cal_date'][6:]}"
                       for r in rows if int(r['is_open']) == 1})
    if day not in sessions or seed['start_date'] not in sessions or ANCHOR not in sessions:
        raise ValueError('连续模拟交易日历不完整，停止生成')
    history, previous = [], None
    for earlier in [d for d in sessions if seed['start_date'] <= d < day]:
        path = directory(root, snapshot_source) / f'{earlier}.json'
        if not path.is_file():
            raise ValueError(f'缺少{earlier}连续模拟记录，先补齐这一交易日；不跳日、不重置净值')
        record = checked(json.loads(path.read_text(encoding='utf-8')), SCHEMA, earlier)
        if (record['seed_hash'] != evidence_hash(seed) or record['model'] != MODEL
                or record.get('snapshot_source') != snapshot_source
                or record['previous_hash'] != (previous['artifact_hash'] if previous else None)):
            raise ValueError('连续模拟起点、规则或前一日记录不符，停止生成')
        earlier_facts = directory(root, snapshot_source) / 'facts' / f'{earlier}.json'
        if not earlier_facts.is_file():
            raise ValueError(f'{earlier}连续模拟成交条件记录缺失，停止生成')
        prior_facts = checked(json.loads(earlier_facts.read_text(encoding='utf-8')), FACTS, earlier)
        if (record['facts_hash'] != prior_facts['artifact_hash']
                or record['plan_hash'] != prior_facts['plan_hash']
                or prior_facts.get('snapshot_source') != snapshot_source):
            raise ValueError('前日连续记录与成交条件来源不符，停止生成')
        history.append(record)
        previous = record
    plan = data['reading_small_cap_plan']
    items = required_items(seed, previous, plan, is_switch(day, sessions))
    facts_path = directory(root, snapshot_source) / 'facts' / f'{day}.json'
    if facts_path.is_file():
        facts = json.loads(facts_path.read_text(encoding='utf-8'))
    elif allow_collect:
        if pro is None:
            from market_data.tushare_client import create_tushare_pro_api
            pro = create_tushare_pro_api()
        facts = collect_facts(pro, data, day, items, root, snapshot_source=snapshot_source)
    else:
        raise ValueError(f'{day}连续模拟成交条件尚未冻结，离线不能补采')
    validate_facts(facts, data, day, items, snapshot_source=snapshot_source)
    record = advance(seed, previous, facts, plan, sessions)
    path = directory(root, snapshot_source) / f'{day}.json'
    if path.is_file() and checked(json.loads(path.read_text(encoding='utf-8')), SCHEMA, day) != record:
        raise ValueError('已有同日连续模拟记录不同，停止覆盖')
    return {'record': record, 'facts': facts, 'history': history + [record]}


def save(tracking, root):
    from report.small_cap_report import write_new
    day = tracking['record']['date']
    record = checked(tracking['record'], SCHEMA, day)
    facts = checked(tracking['facts'], FACTS, day)
    if (record['facts_hash'] != facts['artifact_hash'] or record['plan_hash'] != facts['plan_hash']
            or record['snapshot_source'] != facts['snapshot_source']):
        raise ValueError('连续记录与成交条件来源不符，停止保存')
    base = directory(root, tracking['record']['snapshot_source'])
    for path, value in [(base / 'facts' / f'{day}.json', tracking['facts']),
                        (base / f'{day}.json', tracking['record'])]:
        write_new(path, json.dumps(value, ensure_ascii=False, allow_nan=False) + chr(10))


def render_tracking(tracking):
    record = tracking['record']
    opening_nav = 1 - tracking['history'][0]['fees_today']
    def table(headers, rows):
        cells = lambda tag, row: '<tr>' + ''.join(f'<{tag}>{escape(str(c))}</{tag}>' for c in row) + '</tr>'
        return '<div class="table-responsive"><table><thead>' + cells('th', headers) + '</thead><tbody>' + ''.join(cells('td', row) for row in rows) + '</tbody></table></div>'
    labels = {None: '继续持有', 'take_profit': '止盈待卖：下一可卖开盘',
              'rotation': '换出待卖：下一可卖开盘', 'floor': '底线触发：下一可卖开盘卖出'}
    rows = [(p['name'], p['code'], p['entry_date'], f"{p['entry_price']:.2f}",
             f"{p['take_profit_price']:.4f}", f"{p['last_close']:.2f}", f"{p['gain_pct']:+.2f}%",
             f"{p['value'] / record['nav'] * 100:.2f}%", labels[p['pending']]) for p in record['positions']]
    holdings = table(('股票', '代码', '模拟买入日', '原买价', '当前止盈线≥', '收盘价', '含分红送转涨幅', '现权重', '下一步'), rows)
    progress = table(('日期', '策略净值（费用后）', '现金占比', '创业板指', '中证2000', '中证全指'),
                     [(r['date'], f"{r['nav']:.6f}", f"{r['cash'] / r['nav'] * 100:.2f}%",
                       *('—' if r['benchmarks'][c]['nav'] is None else f"{r['benchmarks'][c]['nav']:.6f}"
                         for c in ('399006.SZ', '932000.CSI', '000985.CSI'))) for r in tracking['history'][-20:]])
    event_labels = {'buy': '模拟买入', 'sell': '模拟卖出', 'skip': '开盘不可买，保留现金',
                    'wait': '开盘不可卖，顺延', 'stop': '净值跌破0.7，停用并等待卖出'}
    events = '；'.join(escape(e.get('name', '') + '：' + event_labels[e['action']]) for e in record['events']) or '没有买卖，继续逐日跟踪'
    return (f'<section id="continuous-tracking"><h2>连续模拟跟踪：净值 {record["nav"]:.6f}</h2>'
            f'<p class="source">连续记录来源：{dict(official="正式", replay="旧重建", rebuilt="独立小盘重建")[record["snapshot_source"]]}；与其他快照来源分开累计。</p>'
            f'<p class="dash-takeaway">{record["start_date"]}开盘买入前净值1，每只分配20%预算（含买入费用）；'
            f'至{record["date"]}收盘收益{(record["nav"] - 1) * 100:+.3f}%，'
            f'现金占比{record["cash"] / record["nav"] * 100:.2f}%。'
            f'{"已触发0.7底线，停止新增买入。" if record["stopped"] else "未触发0.7底线。"}</p>'
            '<p>等额碎股模拟，不按一万元整手限制替换初始五只；权重自然变化，不每日调回20%。'
            f'买入后即时净值{opening_nav:.6f}，起始买入费未被抹去；随后买卖均计入万一免五、过户费及卖出印花税。'
            '这不是实际持仓或真实成交。</p>' + holdings + f'<p>{events}</p>'
            f'<p>下次定名单：{escape(record["next_decision"] or "待核实")}收盘；'
            f'下次换股：{escape(record["next_switch"] or "待核实")}开盘。'
            '止盈卖出的资金留到下次换手；换手仍在前五的旧仓保留原买价、不补成等额。</p>'
            '<h3>同日起点对照</h3><p>各指数同以起始日开盘为1，是价格参照，不扣交易费用；未取得的值留空。</p>' + progress +
            '<small>分红送转沿用相邻收盘与除权前收盘的收益链折算模拟份额，不是真实红利到账和税款账本；'
            '不计滑点、红利税和现金利息。停牌持仓仅凭同日全日停牌事实沿用上一估值；'
            '缺行情不猜作停牌。涨跌停采用同日价格。底线相对初始净值1，不随盈利上移，不能保证损失止于30%。</small></section>')
