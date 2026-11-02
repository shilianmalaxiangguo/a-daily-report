"""The execution plan picks the coldest stocks with growing revenue and profit, using only what was known then."""
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from bs4 import BeautifulSoup
from report.sector_reading_history import evidence_hash
from report.small_cap_rotation import (ACCOUNT_FEE, ANCHOR, BACKUPS, NAMES, SELL_FEE, account_orders, build_plan, day_label,
                                       growth_records, held_path, render_plan, rotation_curve, validate_plan)
from report.strategy_backtest import history_from_artifact
from tests.test_market_alpha_beta import NEW, ST, facts, scenario, sessions

COLD = [f'{601000 + i}.SH' for i in range(10)]
GROWING = COLD[3:10]                         # the cold names whose latest quarter grew, coldest first


def calendar_through(end):
    first = date.fromisoformat(ANCHOR)
    return [(first + timedelta(days=k)).isoformat() for k in range((date.fromisoformat(end) - first).days + 1)]


def end_with(since):
    """A date whose position from the anchor leaves `since` sessions after the latest decision day."""
    day = date(2026, 9, 29)                      # the synthetic facts were retrieved on 2026-09-30
    while (day - date.fromisoformat(ANCHOR)).days % 20 != since:
        day -= timedelta(days=1)
    return day.isoformat()


def world(end, changes=None):
    """changes: {code: {session index: daily change in %}} written over the scenario before prices are built."""
    days = sessions(end)
    market, series = scenario(days)
    for code, moves in (changes or {}).items():
        for k, change in moves.items():
            series[code][k] = change
    amount = {code: 1000.0 * (k + 1) for k, code in enumerate(COLD)}
    amount[ST] = 500.0
    return days, facts(days, market, series, amount=amount)


def fina(decision):
    later = (date.fromisoformat(decision) + timedelta(days=3)).strftime('%Y%m%d')
    rows = [{'ts_code': COLD[0], 'ann_date': '20260815', 'q_sales_yoy': 30.0, 'q_profit_yoy': -5.0},   # profit falling
            {'ts_code': COLD[1], 'ann_date': later, 'q_sales_yoy': 30.0, 'q_profit_yoy': 20.0},       # announced later
            {'ts_code': COLD[2], 'ann_date': '20260630', 'q_sales_yoy': 30.0, 'q_profit_yoy': 20.0},  # not after period end
            {'ts_code': ST, 'ann_date': '20260815', 'q_sales_yoy': 30.0, 'q_profit_yoy': 20.0}]
    rows += [{'ts_code': code, 'ann_date': '20260820', 'q_sales_yoy': 10.0 + k, 'q_profit_yoy': 5.0 + k}
             for k, code in enumerate(COLD[3:10])]
    return {'periods': {'20260630': [{**row, 'end_date': '20260630'} for row in rows]}}


class PlanTest(unittest.TestCase):
    def test_cold_growing_names_in_order_with_what_was_known_then(self):
        end = end_with(5)
        days, value = world(end)
        decision = days[-6]
        plan, reason = build_plan(value, end, sessions=calendar_through(end), records=growth_records(fina(decision)), chinext={})
        self.assertIsNone(reason)
        self.assertEqual(plan['decision_date'], decision)
        self.assertEqual((plan['sessions_since'], plan['sessions_to_next']), (5, 15))
        self.assertEqual([p['code'] for p in plan['picks']], GROWING[:NAMES])
        self.assertEqual([p['code'] for p in plan['backups']], GROWING[NAMES:NAMES + BACKUPS])
        self.assertNotIn(ST, [p['code'] for p in plan['picks'] + plan['backups']])
        h = history_from_artifact(value)
        t, final = days.index(decision), len(days) - 1
        rets = np.where(np.isnan(h['returns']), 0.0, h['returns'] / 100)
        each = [h['close'][i, t + 1] / h['open'][i, t + 1] * np.prod(1 + rets[i, t + 2:final + 1]) for i in
                (h['codes'].index(c) for c in GROWING[:NAMES])]
        self.assertAlmostEqual(plan['holding']['basket_pct'], round((np.mean(each) * (1 - 0.001) - 1) * 100, 2), places=6)
        self.assertEqual(plan['holding']['codes'], GROWING[:NAMES])
        pool = [h['close'][i, t + 1] / h['open'][i, t + 1] * np.prod(1 + rets[i, t + 2:final + 1]) for i in
                (h['codes'].index(c) for c in GROWING)]
        self.assertEqual(plan['holding']['pool_size'], len(GROWING))
        account = plan['account']
        self.assertEqual((account['priced'], account['date']), ('open', days[t + 1]))
        worth = account['cash_left'] + sum(o['amount'] * h['close'][h['codes'].index(o['code']), t + 1] / h['open'][h['codes'].index(o['code']), t + 1]
                                           * np.prod(1 + rets[h['codes'].index(o['code']), t + 2:final + 1]) for o in account['orders'])
        self.assertAlmostEqual(account['value_pct'], round((worth / 10_000 - 1) * 100, 2), places=6)
        self.assertEqual([o['code'] for o in account['orders']], [c for c in GROWING if c in [o['code'] for o in account['orders']]])
        self.assertAlmostEqual(plan['holding']['pool_pct'], round((np.mean(pool) * (1 - 0.001) - 1) * 100, 2), places=6)
        self.assertEqual(len(plan['previous']), 1)
        validate_plan(plan, end)

    def test_decision_day_has_no_holding_and_changes_are_refused(self):
        end = end_with(0)
        days, value = world(end)
        plan, _ = build_plan(value, end, sessions=calendar_through(end), records=growth_records(fina(end)), chinext={})
        self.assertEqual(plan['decision_date'], end)
        self.assertEqual((plan['sessions_since'], plan['sessions_to_next']), (0, 20))
        self.assertIsNone(plan['holding'])
        changed = deepcopy(plan)
        changed['picks'][0]['name'] = '改过'
        with self.assertRaises(ValueError):
            validate_plan(changed, end)
        with self.assertRaises(ValueError):
            validate_plan(plan, days[-2])
        self.assertEqual(build_plan(value, end, sessions=[], records={}, chinext={})[0], None)

    def test_rotation_curve_follows_the_picks_between_decision_days(self):
        days, value = world('2024-08-30')
        self.assertEqual(days[0], ANCHOR)
        rows = [{'ts_code': code, 'ann_date': '20240425', 'end_date': '20240331', 'q_sales_yoy': 10.0 + k, 'q_profit_yoy': 5.0}
                for k, code in enumerate(COLD)]
        records = growth_records({'periods': {'20240331': rows}})
        h = history_from_artifact(value)
        nav = rotation_curve(h, records, 0, eligible=np.broadcast_to(h['eligible'][:, :1], h['eligible'].shape).copy(), take_profit=None)
        self.assertEqual(len(nav), len(days))
        cash = (1 + 0.015 / 252) ** 20
        self.assertAlmostEqual(nav[20], cash, places=12)
        rets = np.where(np.isnan(h['returns']), 0.0, h['returns'] / 100)
        picks = [h['codes'].index(c) for c in COLD[:NAMES]]
        each = [h['close'][i, 21] / h['open'][i, 21] * np.prod(1 + rets[i, 22:41]) for i in picks]
        self.assertAlmostEqual(nav[40], cash * (1 - 0.001) * np.mean(each) * (1 - 0.001), places=10)

    def test_page_shows_the_plan_and_its_rules(self):
        end = end_with(5)
        days, value = world(end)
        plan, _ = build_plan(value, end, sessions=calendar_through(end), records=growth_records(fina(days[-6])), chinext={})
        section = render_plan(BeautifulSoup('', 'html.parser'), plan)
        text = section.get_text(' ', strip=True)
        for phrase in ('执行计划：小盘轮换', '持有的第5个交易日', '再过15个交易日定新名单', '名单', '备选', '本期等权模拟买入', '净值跌破0.7',
                       '一手约（元）', f'名单每天显示的都是这一期定下的那{NAMES}只', '怎么买', '一手（100股）的钱超过这一份就跳过'):
            self.assertIn(phrase, text)
        self.assertEqual(len(section.select('tr.dash-row-plan')), NAMES)
        self.assertEqual(len(section.select('tr.dash-row-backup')), len(GROWING) - NAMES)

    def test_plan_knows_the_next_session_and_the_next_switch(self):
        end = end_with(5)
        days, value = world(end)
        after = lambda k: (date.fromisoformat(end) + timedelta(days=k)).isoformat()
        plan, _ = build_plan(value, end, sessions=calendar_through(after(30)), records=growth_records(fina(days[-6])), chinext={})
        self.assertEqual((plan['next_session'], plan['next_decision'], plan['next_switch']), (after(1), after(15), after(16)))
        text = render_plan(BeautifulSoup('', 'html.parser'), plan).get_text(' ', strip=True)
        self.assertIn(f'下一个交易日{day_label(after(1))}是第6个', text)
        self.assertIn(f'下次在{day_label(after(15))}收盘后定新名单，{day_label(after(16))}开盘换股', text)
        validate_plan(plan, end)

    def test_the_list_passes_over_star_names_the_account_cannot_buy(self):
        end = end_with(5)
        days, value = world(end)
        renamed = {COLD[3]: '688003.SH', COLD[4]: '300004.SZ'}
        value['codes'] = [renamed.get(code, code) for code in value['codes']]
        rows = fina(days[-6])
        for period in rows['periods'].values():
            for row in period:
                row['ts_code'] = renamed.get(row['ts_code'], row['ts_code'])
        plan, _ = build_plan(value, end, sessions=calendar_through(end), records=growth_records(rows), chinext={})
        tradable = ['300004.SZ'] + COLD[5:10]
        self.assertEqual([p['code'] for p in plan['picks']], tradable[:NAMES])
        self.assertEqual([p['code'] for p in plan['backups']], tradable[NAMES:NAMES + BACKUPS])
        self.assertEqual([p['code'] for p in plan['all_boards']], (['688003.SH'] + tradable)[:NAMES])
        self.assertEqual(plan['holding']['codes'], tradable[:NAMES])
        section = render_plan(BeautifulSoup('', 'html.parser'), plan)
        text = section.get_text(' ', strip=True)
        self.assertIn(f'前{NAMES}名里有科创板的名称601003', text)
        self.assertIn('在主板和创业板里', text)
        cells = [td.get_text() for td in section.select('tr.dash-row-plan')[0].select('td')]
        self.assertIn('创业板', cells)

    def test_the_list_published_on_the_decision_day_holds_for_the_period(self):
        end = end_with(5)
        days, value = world(end)
        decision = days[-6]
        records = growth_records(fina(decision))
        _, first = world(decision)
        published, _ = build_plan(first, decision, sessions=calendar_through(decision), records=records, chinext={})
        self.assertEqual(published['list_source'], 'today')
        value['st_codes'] = list(value.get('st_codes') or []) + [COLD[3]]          # named ST after the list was published
        again, _ = build_plan(value, end, sessions=calendar_through(end), records=records, chinext={})
        self.assertEqual(again['list_source'], 'recomputed')
        self.assertNotIn(COLD[3], [p['code'] for p in again['picks']])
        kept, _ = build_plan(value, end, sessions=calendar_through(end), records=records, chinext={}, frozen={decision: published})
        self.assertEqual(kept['list_source'], 'published')
        self.assertEqual(kept['picks'], published['picks'])
        self.assertEqual(kept['holding']['codes'], [p['code'] for p in published['picks']])
        self.assertIn(f'名单取自{decision}发布的日报，整期不变', render_plan(BeautifulSoup('', 'html.parser'), kept).get_text())
        middle = days[-4]                                                         # first published two sessions later
        _, window = world(middle)
        mid_plan, _ = build_plan(window, middle, sessions=calendar_through(middle), records=records, chinext={})
        self.assertEqual(mid_plan['sessions_since'], 2)
        later, _ = build_plan(value, end, sessions=calendar_through(end), records=records, chinext={}, frozen={middle: mid_plan})
        self.assertEqual((later['list_source'], later['list_from']), ('published', middle))
        self.assertEqual(later['picks'], mid_plan['picks'])
        same_rule = {**mid_plan, 'schema': 'small_cap_plan.v6'}                    # v6 lists follow the same selection rule
        same_rule['artifact_hash'] = evidence_hash({k: v for k, v in same_rule.items() if k != 'artifact_hash'})
        self.assertEqual(build_plan(value, end, sessions=calendar_through(end), records=records, chinext={},
                                    frozen={middle: same_rule})[0]['list_source'], 'published')
        other_rule = {**mid_plan, 'schema': 'small_cap_plan.v4'}
        self.assertEqual(build_plan(value, end, sessions=calendar_through(end), records=records, chinext={},
                                    frozen={middle: other_rule})[0]['list_source'], 'recomputed')

    def test_someone_starting_mid_period_gets_the_latest_close_ranking(self):
        end = end_with(5)
        days, value = world(end)
        decision = days[-6]
        records = growth_records(fina(decision))
        _, first = world(decision)
        published, _ = build_plan(first, decision, sessions=calendar_through(decision), records=records, chinext={})
        self.assertIsNone(published['fresh'])                                    # on the decision day the two are the same
        value['st_codes'] = list(value.get('st_codes') or []) + [COLD[3]]
        plan, _ = build_plan(value, end, sessions=calendar_through(end), records=records, chinext={}, frozen={decision: published})
        self.assertIn(COLD[3], [p['code'] for p in plan['picks']])               # holders keep the period's list
        fresh = plan['fresh']
        self.assertEqual(fresh['date'], end)
        # COLD[1] reported three days after the decision day, so today it qualifies; COLD[3] is now ST
        self.assertEqual([p['code'] for p in fresh['picks']], [COLD[1]] + [c for c in GROWING if c != COLD[3]][:NAMES - 1])
        self.assertEqual(len(fresh['orders']), NAMES)
        text = render_plan(BeautifulSoup('', 'html.parser'), plan).get_text(' ', strip=True)
        self.assertIn('这一期中途才开始的', text)
        self.assertIn('已经在拿的，继续拿上面这一期的名单', text)
        self.assertIn('新进', text)

    def test_ten_thousand_yuan_buys_whole_lots_down_the_list(self):
        items = [{'code': c, 'name': n} for c, n in (('A', '福然德'), ('B', '天新药业'), ('C', '申通地铁'), ('D', '长久物流'),
                                                       ('E', '钱江水利'), ('F', '绿城水务'))]
        prices = {'A': 9.77, 'B': 24.62, 'C': 7.36, 'D': 5.68, 'E': 7.74, 'F': 4.41}
        orders, skipped, cash = account_orders(items, lambda p: prices[p['code']])
        self.assertEqual([(o['code'], o['lots']) for o in orders], [('A', 2), ('C', 2), ('D', 3), ('E', 3), ('F', 5)])
        self.assertEqual([s['code'] for s in skipped], ['B'])
        self.assertIn('一手2,462元', skipped[0]['reason'])
        spent = sum(o['amount'] for o in orders) * (1 + ACCOUNT_FEE)
        self.assertAlmostEqual(cash, 10_000 - spent, places=6)
        orders, skipped, _ = account_orders(items, lambda p: None if p['code'] == 'A' else prices[p['code']])
        self.assertEqual(skipped[0]['reason'], '开盘涨停或停牌，买不到')
        self.assertEqual(orders[0]['code'], 'C')

    def test_period_check_tells_whether_the_pool_still_beats_small_caps(self):
        from report.strategy_backtest import plan_periods
        days = calendar_through((date.fromisoformat(ANCHOR) + timedelta(days=129)).isoformat())
        steps = np.arange(len(days))
        curves = {'small_cap_plan': 1.002 ** steps, 'small_cap_plan_hold': 1.0015 ** steps, 'small_cap_pool': 1.003 ** steps,
                  '932000.CSI': 1.001 ** steps, '399006.SZ': 0.999 ** steps}
        periods, style = plan_periods({'days': days}, curves, 0)
        self.assertEqual([p['decision_date'] for p in periods], days[0:121:20])
        self.assertEqual([p['current'] for p in periods], [False] * 6 + [True])
        self.assertAlmostEqual(periods[0]['pool_pct'], round((1.003 ** 20 - 1) * 100, 2))
        self.assertAlmostEqual(periods[0]['plan_hold_pct'], round((1.0015 ** 20 - 1) * 100, 2))
        self.assertEqual((style['periods'], style['pool_beat_csi2000'], style['warning']), (6, 6, False))
        self.assertAlmostEqual(style['pool_minus_csi2000_pp'], (1.003 ** 120 - 1.001 ** 120) * 100, delta=0.1)   # periods rounded to 0.01%
        end = end_with(5)
        _, value = world(end)
        plan, _ = build_plan(value, end, sessions=calendar_through(end), records=growth_records(fina(end)), chinext={})
        section = render_plan(BeautifulSoup('', 'html.parser'), plan, {'plan_periods': periods, 'style_check': style})
        self.assertEqual(len(section.select('tr.dash-row-period')), 7)
        self.assertIn('股票池仍跑赢中证2000', section.get_text())
        self.assertIn('不止盈（对照）', [th.get_text() for th in section.select('.dash-plan-periods th')])
        curves['932000.CSI'] = 1.004 ** steps
        periods, style = plan_periods({'days': days}, curves, 0)
        self.assertEqual((style['pool_beat_csi2000'], style['warning']), (0, True))
        section = render_plan(BeautifulSoup('', 'html.parser'), plan, {'plan_periods': periods, 'style_check': style})
        self.assertIn('风格在切换', section.get_text())

    def test_full_page_leads_with_the_plan(self):
        from report.sector_daily_report import render_sector_daily
        from tests.test_sector_daily_report import DATE, SOURCE, snapshot
        days, value = world(DATE)
        plan, reason = build_plan(value, DATE, sessions=calendar_through(DATE), records=growth_records(fina(DATE)), chinext={})
        self.assertIsNone(reason)
        data = snapshot()
        data['data']['reading_market_returns'] = value
        data['data']['reading_small_cap_plan'] = plan
        soup = BeautifulSoup(render_sector_daily(SOURCE, DATE, snapshot=data), 'html.parser')
        self.assertIn('执行计划：小盘轮换', soup.select_one('#daily-plan h2').get_text())
        rule = soup.select_one('#daily-plan').get_text()
        self.assertIn('收盘比买价高10%', rule)
        self.assertNotIn('高开5%以上', rule)
        self.assertIsNone(soup.select_one('#daily-decision'))
        self.assertIsNotNone(soup.select_one('#daily-plan'))
        self.assertIn('#daily-plan', [a['href'] for a in soup.select('.daily-nav-links a')])

    def test_take_profit_sells_at_the_next_open_and_waits_past_a_limit_down(self):
        def history(opens, closes):
            close, opened = np.array([closes], dtype=float), np.array([opens], dtype=float)
            pre = np.concatenate([[[np.nan]], close[:, :-1]], axis=1)
            return {'open': opened, 'close': close, 'pre': pre, 'returns': (close / pre - 1) * 100, 'limit': np.array([10.0])}

        h = history([10.0, 10.0, 10.3, 11.0, 11.6, 11.8], [10.0, 10.2, 11.1, 11.5, 11.7, 12.0])
        path, sold, due = held_path(h, 0, 0, 5)
        np.testing.assert_allclose(path, [1.02, 1.11, 1.10, 1.10, 1.10])                  # line reached on session 2, sold at the next open
        self.assertEqual((sold, due), (3, False))
        self.assertEqual(held_path(h, 0, 0, 2, live=True)[1:], (None, True))                # reached at today's close: sell at the next open
        self.assertEqual(held_path(h, 0, 0, 2)[1:], (None, False))                          # reached on the period's last close: the rotation takes over
        path, sold, _ = held_path(h, 0, 0, 5, take_profit=None)
        np.testing.assert_allclose(path, [1.02, 1.11, 1.15, 1.17, 1.20])
        self.assertIsNone(sold)
        h = history([10.0, 10.0, 10.3, 9.99, 11.6, 11.8], [10.0, 10.2, 11.1, 11.5, 11.7, 12.0])   # session 3 opens at the limit down
        path, sold, _ = held_path(h, 0, 0, 5)
        np.testing.assert_allclose(path, [1.02, 1.11, 1.15, 1.16, 1.16])
        self.assertEqual(sold, 4)

    def test_the_plan_takes_profit_and_keeps_the_money_for_the_next_switch(self):
        end = end_with(5)
        entry = len(sessions(end)) - 5                                             # bought at the open of days[-5]
        first, second = GROWING[0], GROWING[1]
        changes = {first: {entry: 0.0, entry + 1: 6.0, entry + 2: 6.0, entry + 3: 0.0, entry + 4: -5.0},   # +12.36% by days[-3]
                   second: {entry: 0.0, entry + 1: 0.0, entry + 2: 0.0, entry + 3: 5.0, entry + 4: 5.0}}   # +10.25% at today's close
        days, value = world(end, changes)
        plan, _ = build_plan(value, end, sessions=calendar_through(end), records=growth_records(fina(days[-6])), chinext={})
        holding = plan['holding']
        self.assertEqual(holding['codes'][:2], [first, second])
        self.assertEqual((holding['status'][:2], holding['sold_dates'][:2]), (['sold', 'due'], [days[-2], None]))
        self.assertAlmostEqual(holding['each_pct'][0], round((1.06 * 1.06 - 1) * 100, 2), places=6)
        self.assertAlmostEqual(holding['each_hold_pct'][0], round((1.06 * 1.06 * 0.95 - 1) * 100, 2), places=6)
        self.assertAlmostEqual(holding['basket_pct'] - holding['basket_hold_pct'],
                               round((1 + np.mean(holding['each_pct']) / 100) * 0.999 * 100 - 100, 2)
                               - round((1 + np.mean(holding['each_hold_pct']) / 100) * 0.999 * 100 - 100, 2), places=1)
        account = plan['account']
        orders = {o['code']: o for o in account['orders']}
        self.assertEqual((orders[first]['status'], orders[second]['status']), ('sold', 'due'))
        self.assertEqual(orders[first]['sold_date'], days[-2])
        sold = orders[first]
        self.assertAlmostEqual(account['cash_now'], account['cash_left'] + sold['amount'] * 1.06 * 1.06 * (1 - SELL_FEE), places=1)
        self.assertGreater(account['value_pct'], account['value_hold_pct'])
        section = render_plan(BeautifulSoup('', 'html.parser'), plan)
        text = section.get_text(' ', strip=True)
        for phrase in ('今天收盘到了止盈线', '开盘已止盈卖出', '止盈价（买价×1.1）', '不止盈为', '收盘比买价高10%', '卖出的钱留到下一个换手日',
                       '止盈价要按除权后的价格重算'):
            self.assertIn(phrase, text)
        self.assertEqual((len(section.select('tr.dash-row-sold')), len(section.select('tr.dash-row-due'))), (1, 1))
        lines = section.select_one('.dash-plan-lines').get_text()
        self.assertIn(f"今天收盘到线的：{orders[second]['name']}", lines)
        self.assertNotIn(orders[first]['name'], lines)                          # already sold, no line left to watch
        validate_plan(plan, end)


if __name__ == '__main__':
    unittest.main()
