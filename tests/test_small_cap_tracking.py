"""Forward tracking: continuity, executable prices, cash and isolated rules."""
from copy import deepcopy
from datetime import date, timedelta
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from report.fact_utils import evidence_hash
from report.small_cap_rotation import ACCOUNT_FEE, SELL_FEE, ANCHOR, build_plan, growth_records
from report.small_cap_report import render
from report.small_cap_tracking import (SCHEMA, advance, collect_facts, directory, is_switch,
                                       curve_data, load_seed, prepare, render_tracking, save, signed, validate_facts)
from tests.test_small_cap_plan import calendar_through, fina, world

SEED = load_seed(ROOT)
CODES = [p['code'] for p in SEED['positions']]
START = SEED['start_date']
begin, end = date.fromisoformat(ANCHOR), date(2026, 12, 31)
SESSIONS = [(begin + timedelta(days=k)).isoformat() for k in range((end - begin).days + 1)
            if (begin + timedelta(days=k)).weekday() < 5]
DAYS = [d for d in SESSIONS if d >= START]
CALENDAR = [{'cal_date': (begin + timedelta(days=k)).strftime('%Y%m%d'),
             'is_open': int((begin + timedelta(days=k)).weekday() < 5)}
            for k in range((end - begin).days + 1)]


def plan(day):
    index = SESSIONS.index(day)
    decision = SESSIONS[((index - 1) // 20) * 20] if is_switch(day, SESSIONS) else SESSIONS[(index // 20) * 20]
    return {'artifact_hash': 'test-plan', 'decision_date': decision,
            'picks': deepcopy(SEED['positions']), 'backups': [],
            'next_decision': None, 'next_switch': None}


def facts(day, *, price=10.0, close=None, pre=10.0, codes=CODES):
    return signed({'schema': 'small_cap_tracking_facts.v1', 'date': day,
                   'quotes': {c: {'bar': {'open': price, 'close': close if close is not None else price, 'pre_close': pre},
                                  'opening_suspended': False, 'whole_day_suspended': False,
                                  'up_limit': pre * 1.1, 'down_limit': pre * .9} for c in codes},
                   'benchmarks': {'000985.CSI': {'name': '中证全指', 'open': 100, 'close': 101}},
                   'retrieved_at': '2026-11-02T16:00:00+08:00', 'market_hash': 'market',
                   'snapshot_source': 'official', 'plan_hash': 'test-plan'})


def first(close=10.0):
    return advance(SEED, None, facts(START, close=close), plan(START), SESSIONS)


def to_day(target):
    previous = None
    for day in DAYS:
        previous = advance(SEED, previous, facts(day), plan(day), SESSIONS)
        if day == target:
            return previous
    raise AssertionError(target)


class SmallCapTrackingTest(unittest.TestCase):
    def test_five_equal_budgets_include_fees_without_minimum_or_lots(self):
        record = first()
        self.assertEqual([p['code'] for p in record['positions']], CODES)
        self.assertEqual([p['name'] for p in record['positions']], ['福然德', '申通地铁', '长久物流', '钱江水利', '绿城水务'])
        self.assertAlmostEqual(record['nav'], 1 / (1 + ACCOUNT_FEE))
        self.assertAlmostEqual(record['fees_total'], ACCOUNT_FEE / (1 + ACCOUNT_FEE))
        self.assertAlmostEqual(record['cash'], 0)
        for p in record['positions']:
            self.assertAlmostEqual(p['value'] / record['nav'], .2)
            self.assertEqual(p['entry_price'], 10)
            self.assertAlmostEqual(p['take_profit_price'], 11)

    def test_weights_drift_and_no_daily_rebalancing_or_new_ranking(self):
        previous = first()
        q = facts(DAYS[1]); q['quotes'][CODES[0]]['bar']['close'] = 10.5
        different = plan(DAYS[1]); different['picks'] = []; different['fresh'] = {'picks': []}
        record = advance(SEED, previous, q, different, SESSIONS)
        self.assertEqual(len(record['events']), 0)
        self.assertGreater(record['positions'][0]['value'] / record['nav'], .2)
        self.assertEqual([p['units'] for p in previous['positions']], [p['units'] for p in record['positions']])
        self.assertEqual(record['fees_total'], previous['fees_total'])

    def test_take_profit_uses_close_then_next_sellable_open_and_waits_in_cash(self):
        previous = first(close=11)
        self.assertTrue(all(p['pending'] == 'take_profit' for p in previous['positions']))
        record = advance(SEED, previous, facts(DAYS[1], price=9.9, pre=11, close=11.1), plan(DAYS[1]), SESSIONS)
        self.assertEqual(len(record['positions']), 5)
        self.assertTrue(all(e['action'] == 'wait' for e in record['events']))
        record = advance(SEED, record, facts(DAYS[2], price=11.2, pre=11.1), plan(DAYS[2]), SESSIONS)
        self.assertEqual(record['positions'], [])
        self.assertAlmostEqual(record['nav'], 1.12 * (1 - SELL_FEE) / (1 + ACCOUNT_FEE))
        later = advance(SEED, record, facts(DAYS[3]), plan(DAYS[3]), SESSIONS)
        self.assertEqual(later['nav'], record['nav'])
        self.assertEqual(later['positions'], [])

    def test_corporate_adjustment_retains_original_basis_and_moves_price_line(self):
        previous = first()
        record = advance(SEED, previous, facts(DAYS[1], price=5, pre=5), plan(DAYS[1]), SESSIONS)
        self.assertAlmostEqual(record['nav'], previous['nav'])
        for before, after in zip(previous['positions'], record['positions']):
            self.assertAlmostEqual(after['units'], before['units'] * 2)
            self.assertEqual(after['entry_price'], before['entry_price'])
            self.assertAlmostEqual(after['take_profit_price'], 5.5)
            self.assertIsNone(after['pending'])

    def test_floor_sells_next_day_waits_for_suspension_and_stays_stopped(self):
        previous = first(close=6.9)
        self.assertTrue(previous['stopped'])
        q = facts(DAYS[1], price=7, pre=6.9)
        q['quotes'][CODES[0]].update(bar=None, opening_suspended=True, whole_day_suspended=True)
        record = advance(SEED, previous, q, plan(DAYS[1]), SESSIONS)
        self.assertEqual([p['code'] for p in record['positions']], CODES[:1])
        record = advance(SEED, record, facts(DAYS[2], price=10, pre=6.9), plan(DAYS[2]), SESSIONS)
        self.assertEqual(record['positions'], [])
        self.assertTrue(record['stopped'])

    def test_floor_is_initial_capital_not_trailing_high_and_equality_does_not_stop(self):
        previous = first()
        q = facts(DAYS[1], price=7, close=7 * (1 + ACCOUNT_FEE))
        record = advance(SEED, previous, q, plan(DAYS[1]), SESSIONS)
        self.assertAlmostEqual(record['nav'], .7)
        self.assertFalse(record['stopped'])

    def test_rotation_keeps_original_basis_and_uses_at_most_three_backups(self):
        switch = next(d for d in DAYS[1:] if is_switch(d, SESSIONS))
        previous = to_day(SESSIONS[SESSIONS.index(switch) - 1])
        p = plan(switch)
        new_codes = [f'6010{k:02d}.SH' for k in range(8)]
        candidates = [{'code': c, 'name': c} for c in new_codes]
        p['picks'] = p['picks'][:1] + candidates[:4]
        p['backups'] = candidates[4:]  # fourth backup must never enter
        q = facts(switch, codes=CODES + new_codes)
        for c in new_codes[:7]:
            q['quotes'][c]['bar']['open'] = 11  # exact limit up
        record = advance(SEED, previous, q, p, SESSIONS)
        self.assertEqual([x['code'] for x in record['positions']], CODES[:1])
        kept = record['positions'][0]
        self.assertEqual(kept['entry_date'], START)
        self.assertEqual(kept['units'], previous['positions'][0]['units'])
        self.assertGreater(record['cash'], 0)
        self.assertNotIn(new_codes[-1], [e.get('code') for e in record['events']])

    def test_take_profit_on_rotation_day_cannot_immediately_fund_or_rebuy(self):
        switch = next(d for d in DAYS[1:] if is_switch(d, SESSIONS))
        previous = to_day(SESSIONS[SESSIONS.index(switch) - 1])
        for p in previous['positions']:
            p['pending'] = 'take_profit'
        p = plan(switch); new_codes = [f'6010{k:02d}.SH' for k in range(5)]
        p['picks'] = [{'code': c, 'name': c} for c in new_codes]
        record = advance(SEED, previous, facts(switch, codes=CODES + new_codes), p, SESSIONS)
        self.assertEqual(record['positions'], [])
        self.assertTrue(all(e['action'] == 'sell' for e in record['events']))
        self.assertGreater(record['cash'], .99)

    def test_delayed_rotation_sale_is_cancelled_when_new_top_five_keeps_the_stock(self):
        switch = next(d for d in DAYS[1:] if is_switch(d, SESSIONS))
        previous = to_day(SESSIONS[SESSIONS.index(switch) - 1])
        previous['positions'][0]['pending'] = 'rotation'
        record = advance(SEED, previous, facts(switch), plan(switch), SESSIONS)
        self.assertEqual(len(record['positions']), 5)
        self.assertEqual(record['events'], [])
        self.assertEqual(record['positions'][0]['entry_price'], 10)
        self.assertIsNone(record['positions'][0]['pending'])
        previous['positions'][0]['pending'] = 'take_profit'
        record = advance(SEED, previous, facts(switch), plan(switch), SESSIONS)
        self.assertEqual(record['events'][0]['reason'], 'take_profit')

    def test_decision_close_announces_immediate_next_open_not_following_cycle(self):
        day = DAYS[1]; p = plan(day)
        p.update(sessions_since=0, decision_date=day, next_session=DAYS[2], next_decision=None, next_switch=None)
        record = advance(SEED, first(), facts(day), p, SESSIONS)
        self.assertEqual(record['next_decision'], day)
        self.assertEqual(record['next_switch'], DAYS[2])

    def test_prepare_is_repeatable_read_only_offline_and_rejects_missing_days(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'config').mkdir(); (root / 'config/small-cap-tracking.json').write_text(json.dumps(SEED))
            history = root / '.generated/backtest-history'; history.mkdir(parents=True)
            (history / 'calendar.json').write_text(json.dumps({'rows': CALENDAR}))
            data = {'reading_small_cap_plan': plan(START), 'reading_market_returns': {'artifact_hash': 'market'}}
            f = facts(START)
            with patch('report.small_cap_tracking.collect_facts', return_value=f):
                tracking = prepare(data, START, root=root, allow_collect=True, pro=object())
            self.assertFalse(directory(root).exists())
            save(tracking, root)
            before = (directory(root) / f'{START}.json').read_bytes()
            with patch('socket.socket', side_effect=AssertionError('离线不可联网')):
                rerun = prepare(data, START, root=root)
            self.assertEqual(tracking, rerun)
            save(rerun, root)
            self.assertEqual(before, (directory(root) / f'{START}.json').read_bytes())
            for source in ('replay', 'rebuilt'):
                with self.subTest(source=source), self.assertRaisesRegex(ValueError, '先补齐'):
                    prepare(data, DAYS[1], root=root, snapshot_source=source)
            foreign = deepcopy(tracking); foreign['record']['snapshot_source'] = 'rebuilt'
            foreign['facts']['snapshot_source'] = 'rebuilt'
            foreign['facts'].pop('artifact_hash'); signed(foreign['facts'])
            foreign['record']['facts_hash'] = foreign['facts']['artifact_hash']
            foreign['record'].pop('artifact_hash'); signed(foreign['record'])
            save(foreign, root)
            self.assertTrue((directory(root, 'rebuilt') / f'{START}.json').is_file())
            self.assertEqual(before, (directory(root) / f'{START}.json').read_bytes())
            changed_calendar = deepcopy(CALENDAR)
            changed_calendar = [r for r in changed_calendar if r['cal_date'] != START.replace('-', '')]
            (history / 'calendar.json').write_text(json.dumps({'rows': changed_calendar}))
            with self.assertRaisesRegex(ValueError, '缺日'):
                prepare(data, START, root=root)
            (history / 'calendar.json').write_text(json.dumps({'rows': CALENDAR}))
            with self.assertRaisesRegex(ValueError, '先补齐'):
                prepare(data, DAYS[2], root=root)
            altered = json.loads(before); altered['nav'] = 99
            (directory(root) / f'{START}.json').write_text(json.dumps(altered))
            with self.assertRaisesRegex(ValueError, '指纹'):
                prepare(data, DAYS[1], root=root)

    def test_source_mismatch_missing_limits_and_unproven_suspension_stop(self):
        data = {'reading_market_returns': {'artifact_hash': 'market'}, 'reading_small_cap_plan': plan(START)}
        items = {p['code']: p for p in SEED['positions']}
        for mutate in (lambda f: f.update(market_hash='other'),
                       lambda f: f['quotes'][CODES[0]].update(bar=None),
                       lambda f: f['quotes'][CODES[0]].update(up_limit=None)):
            f = facts(START); mutate(f); f.pop('artifact_hash'); signed(f)
            with self.assertRaises(ValueError):
                validate_facts(f, data, START, items)

    def test_current_page_uses_only_tracking_for_holdings_and_hides_period_demo(self):
        with patch('tests.test_market_alpha_beta.RETRIEVED', '2026-11-02T16:00:00+08:00'):
            _, market = world(START)
        p, reason = build_plan(market, START, sessions=calendar_through(START), records=growth_records(fina(START)), chinext={})
        self.assertIsNone(reason)
        record = first()
        data = {'reading_market_returns': market, 'reading_small_cap_plan': p}
        tracking = {'record': record, 'facts': facts(START), 'history': [record]}
        soup = BeautifulSoup(render(data, START, source='合成事实', tracking=tracking), 'html.parser')
        self.assertIsNotNone(soup.select_one('#continuous-tracking'))
        self.assertIsNotNone(soup.select_one('#small-cap-tracking'))
        self.assertIsNone(soup.select_one('#small-cap-plan'))
        self.assertIsNone(soup.select_one('.dash-plan-account'))
        self.assertIsNone(soup.select_one('.dash-plan-fresh'))
        self.assertFalse(soup.select_one('.plan-disclosure').has_attr('open'))
        self.assertNotIn('每期重新起算', soup.get_text())
        self.assertNotIn('未实现跨期', soup.get_text())
        self.assertEqual(json.loads(soup.select_one('#small-cap-tracking').string)['positions'], record['positions'])
        record.update(positions=[], cash=.65, nav=.65, stopped=True)
        stopped = BeautifulSoup(render(data, START, source='合成事实', tracking=tracking), 'html.parser')
        self.assertIsNone(stopped.select_one('#daily-plan'))
        self.assertIn('后续定名单和调仓均停止', stopped.get_text())
        from report.small_cap_rotation import render_plan
        p.update(sessions_since=0, next_session=DAYS[1], next_decision=None, next_switch=None)
        text = render_plan(BeautifulSoup('', 'html.parser'), p, tracked=True).get_text()
        self.assertIn(DAYS[1] + '开盘换股', text)
        self.assertNotIn('下次待核实', text)

    def test_curve_keeps_opening_origin_all_closes_and_missing_index_gaps(self):
        history = []
        for i, day in enumerate(DAYS[:27]):
            record = deepcopy(first())
            record['date'] = day
            record['nav'] = 1 + i * .001
            record['benchmarks']['000985.CSI']['nav'] = None if i == 3 else 1 + i * .002
            history.append(record)
        tracking = {'record': history[-1], 'history': history}
        rows = curve_data(tracking)
        self.assertEqual(len(rows), 28)
        self.assertEqual(rows[0]['values'], [1, None, None, 1])
        self.assertEqual(rows[4]['values'][-1], None)
        self.assertEqual(rows[-1]['values'][0], history[-1]['nav'])
        soup = BeautifulSoup(render_tracking(tracking), 'html.parser')
        self.assertEqual(json.loads(soup.select_one('#nav-curve-data').string), rows)
        index_path = soup.select_one('[data-series="3"] path')['d']
        self.assertEqual(index_path.count('M'), 2)
        self.assertEqual(soup.select_one('[data-series="0"] path')['d'].count('M'), 1)
        self.assertEqual(soup.select_one('input[type=range]')['max'], '27')

    def test_first_day_summary_matches_holdings_and_dates_without_invented_history(self):
        record = first(close=10.1)
        record.update(next_decision='2026-11-20', next_switch='2026-11-23')
        soup = BeautifulSoup(render_tracking({'record': record, 'history': [record]}), 'html.parser')
        overview = soup.select_one('#continuous-tracking')
        self.assertEqual(overview.select_one('.fund-nav').text, f'{record["nav"]:.6f}')
        self.assertEqual(overview.select_one('.fund-return').text, f'{(record["nav"] - 1) * 100:+.3f}%')
        self.assertIn('2026-11-23 开盘', overview.get_text())
        self.assertIn('2026-11-20 收盘定名单', overview.get_text())
        self.assertEqual(len(overview.select('.fund-holdings a')), 5)
        for item in record['positions']:
            self.assertIn(item['name'], overview.get_text())
            self.assertIn(f'{item["value"] / record["nav"] * 100:.2f}%', overview.get_text())
        self.assertEqual(len(json.loads(soup.select_one('#nav-curve-data').string)), 2)
        self.assertIn('尚无跨日轨迹', soup.get_text())

    def test_cash_only_and_stopped_summary_do_not_instruct_new_rotation(self):
        record = first()
        record.update(positions=[], cash=.65, nav=.65, stopped=True, next_decision='2026-11-20', next_switch='2026-11-23')
        soup = BeautifulSoup(render_tracking({'record': record, 'history': [record]}), 'html.parser')
        overview = soup.select_one('#continuous-tracking').get_text()
        self.assertIn('现金 100.00%', overview)
        self.assertIn('已停用，不再调仓', overview)
        self.assertNotIn('2026-11-23 开盘', overview)
        self.assertNotIn('2026-11-20 收盘定名单', overview)
        self.assertNotIn('等待下一可卖开盘退出', overview)
        self.assertIn('已触发0.7底线并清仓', overview)
        self.assertIn('当前无股票持仓', soup.select_one('#fund-positions').get_text())
        self.assertNotIn('下次换手', soup.get_text())
        self.assertNotIn('恢复买入', soup.get_text())
        waiting = first(close=6.5)
        waiting_page = BeautifulSoup(render_tracking({'record': waiting, 'history': [waiting]}), 'html.parser')
        self.assertIn('等待下一可卖开盘退出', waiting_page.get_text())
        self.assertNotIn('下次换手', waiting_page.get_text())

    def test_curve_rejects_non_finite_plot_range_before_emitting_bad_svg(self):
        record = first()
        record['nav'] = 1.79e308
        with self.assertRaisesRegex(ValueError, '曲线范围异常'):
            render_tracking({'record': record, 'history': [record]})


if __name__ == '__main__':
    unittest.main()
