"""After alpha and beta are compared, the board says what to do, and its rules use no future data."""
from copy import deepcopy
import json
from math import fsum, prod, sin
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from bs4 import BeautifulSoup
from research.alpha_beta.decision_board import (
    COST_PCT, _forward, _panel, _select, _stance, build_decision_board, walk_forward,
)
from research.alpha_beta.market_alpha_beta import build_alpha_beta
from tests.test_market_alpha_beta import facts, sessions

GOOD, SPIKE, THIN, LIMIT, LAGGARD = '600101.SH', '600102.SH', '600103.SH', '600104.SH', '600105.SH'


def series(days):
    market = [-0.4 + 1.1 * sin(0.9 * k) for k in range(len(days))]
    good = [0.2 * m + 0.9 + 0.35 * sin(2.3 * k + 1) for k, m in enumerate(market)]
    values = {GOOD: good, SPIKE: [*good[:-3], 8.5, 8.5, 8.5], THIN: list(good),
              LIMIT: [*good[:-1], 10.0], LAGGARD: [2.0 * m + 1.0 + 0.3 * sin(1.9 * k) for k, m in enumerate(market)]}
    for j in range(12):
        values[f'{600201 + j}.SH'] = [(1.0 + 0.1 * j) * m + 0.3 * sin(1.3 * k + j) for k, m in enumerate(market)]
    for j in range(25):
        values[f'{601000 + j}.SH'] = [(0.8 + 0.02 * j) * m + 0.6 * sin(0.7 * k + j) for k, m in enumerate(market)]
    return market, values


def board(end='2026-09-29'):
    days = sessions(end)
    market, values = series(days)
    value = facts(days, market, values, st=(), amount={THIN: 30000.0})
    projection = build_alpha_beta(value, days[-1])
    return days, market, values, value, projection, build_decision_board(value, days[-1], projection)


class DecisionBoardTest(unittest.TestCase):
    def test_checklist_gives_buying_qualification_and_exit_level(self):
        days, _, values, value, _, result = board()
        status = {c['code']: c['status'] for c in result['candidates']}
        self.assertEqual(status[GOOD], 'buy')
        self.assertEqual(status[SPIKE], 'wait')
        self.assertEqual(status[THIN], 'avoid')
        self.assertEqual(status[LIMIT], 'avoid')
        self.assertEqual(status[LAGGARD], 'watch')
        good = next(c for c in result['candidates'] if c['code'] == GOOD)
        self.assertEqual(good['passes'], 6)
        closes, level = [], 10.
        for r in values[GOOD]:
            level *= 1 + r / 100
            closes.append(level)
        self.assertAlmostEqual(good['stop'], min(closes[-10:]))
        self.assertAlmostEqual(good['stop_distance_pct'], (min(closes[-10:]) / closes[-1] - 1) * 100)
        spike = next(c for c in result['candidates'] if c['code'] == SPIKE)
        self.assertFalse(spike['checks']['not_spiking'])
        self.assertFalse(spike['checks']['stop_near'])
        laggard = next(c for c in result['candidates'] if c['code'] == LAGGARD)
        self.assertEqual([k for k, v in laggard['checks'].items() if not v], ['resists_market'])
        self.assertEqual(result['status_counts']['buy'], sum(c['status'] == 'buy' for c in result['candidates']))
        self.assertEqual(len(result['candidates'][0]['daily']), 20)

    def test_beta_basket_is_the_most_market_levered_liquid_names(self):
        _, _, _, _, _, result = board()
        codes = [row['code'] for row in result['beta_basket']]
        self.assertEqual(len(codes), 10)
        betas = [row['beta'] for row in result['beta_basket']]
        self.assertEqual(betas, sorted(betas, reverse=True))
        self.assertTrue(all(code.startswith('6002') for code in codes[:5]))
        pk = result['pk']
        self.assertAlmostEqual(pk['beta']['down_scenario_pct'], -2 * pk['beta']['beta'])
        self.assertGreater(pk['beta']['beta'], pk['alpha']['beta'])

    def test_next_open_entry_skips_limit_and_chased_opens_and_survives_ex_rights(self):
        days, market, values, value, _, _ = board()
        panel = _panel(value)
        i = panel['codes'].index(GOOD)
        t = 30
        expected = (panel['close'][i][t + 1] / panel['open'][i][t + 1]
                    * prod(1 + panel['returns'][i][k] / 100 for k in range(t + 2, t + 6)) - 1) * 100
        self.assertAlmostEqual(_forward(panel, i, t), expected)
        chased = deepcopy(panel)
        chased['open'][i][t + 1] = chased['previous'][i][t + 1] * 1.035
        self.assertIsNone(_forward(chased, i, t))
        limit = deepcopy(panel)
        limit['open'][i][t + 1] = limit['previous'][i][t + 1] * 1.099
        self.assertIsNone(_forward(limit, i, t))
        gap = deepcopy(panel)
        gap['returns'][i][t + 3] = None
        self.assertIsNone(_forward(gap, i, t))
        # An ex-dividend day lowers the raw close; the daily return chain still uses pre_close.
        dividend = deepcopy(panel)
        dividend['close'][i][t + 3] *= 0.9
        self.assertAlmostEqual(_forward(dividend, i, t), expected)
        self.assertIsNone(_forward(panel, i, len(days) - 3))

    def test_walk_forward_selection_never_reads_later_sessions(self):
        _, _, _, value, _, _ = board()
        panel = _panel(value)
        t = 35
        before = _select(panel, t)
        changed = deepcopy(panel)
        for i in range(len(changed['codes'])):
            for k in range(t + 1, len(changed['days'])):
                if changed['returns'][i][k] is not None:
                    changed['returns'][i][k] = -9.0
                    changed['close'][i][k] = 1.0
                    changed['amount'][i][k] = 0.0
        changed['market'] = [*changed['market'][:t + 1], *[5.0] * (len(changed['days']) - t - 1)]
        from research.alpha_beta.market_alpha_beta import _prefix
        changed['sums'] = {i: _prefix(changed['returns'][i], changed['market']) for i in changed['eligible']}
        self.assertEqual(_select(changed, t), before)

    def test_basket_returns_pay_the_round_trip_cost(self):
        _, _, _, value, _, result = board()
        panel = _panel(value)
        rows, summary = walk_forward(panel)
        self.assertEqual(rows, result['walk_forward']['rows'])
        first = next(row for row in rows if row['alpha'] is not None)
        t = panel['days'].index(first['date'])
        picked = [r['index'] for r in _select(panel, t)['alpha'] if r['status'] == 'buy'][:10]
        raw = [r for i in picked if (r := _forward(panel, i, t)) is not None]
        self.assertAlmostEqual(first['alpha'], fsum(raw) / len(raw) - COST_PCT)
        self.assertEqual(summary['decision_dates'], len(rows))
        self.assertEqual(rows[-1]['exit_date'], panel['days'][-1])

    def test_missing_recent_benchmark_day_leaves_no_board(self):
        days = sessions()
        market, values = series(days)

        def drop(_, bench):
            del bench[-3]
        value = facts(days, market, values, st=(), mutate=drop)
        self.assertIsNone(build_alpha_beta(value, days[-1]))

    def test_long_run_backtest_must_also_support_alpha(self):
        from unittest.mock import patch
        import research.alpha_beta.decision_board as db
        days, _, _, value, projection, _ = board()
        rows, summary = db.walk_forward(db._panel(value))
        summary = {**summary, 'alpha_edge': True, 'alpha': {**summary['alpha'], 'mean_excess': 1.0}}
        evidence = {'start': '2024-01-02', 'design_start': '2026-07-28', 'own_ic': -0.05, 'own_ic_t': -3.0}
        with patch.object(db, 'walk_forward', return_value=(rows, summary)):
            supported = db.build_decision_board(value, days[-1], projection,
                                                long_run={**evidence, 'alpha_oos_cagr': 30.0, 'index_oos_cagr': 10.0})
            refuted = db.build_decision_board(value, days[-1], projection,
                                              long_run={**evidence, 'alpha_oos_cagr': 5.0, 'index_oos_cagr': 20.0})
            unknown = db.build_decision_board(value, days[-1], projection)
        self.assertTrue(supported['alpha_edge'])
        self.assertFalse(refuted['alpha_edge'])
        self.assertTrue(unknown['alpha_edge'])
        self.assertIn('长期回测', refuted['reasons'][-1])
        self.assertIn('-0.050', refuted['reasons'][-1])

    def test_stance_table(self):
        beta = {'verdict': 'beta'}
        self.assertEqual(_stance(beta, True, False, 3), ('defense', 'avoid', 'watch'))
        self.assertEqual(_stance(beta, True, True, 3), ('defense', 'avoid', 'buy_only'))
        self.assertEqual(_stance(beta, True, True, 0), ('defense', 'avoid', 'none_today'))
        self.assertEqual(_stance(beta, False, False, 3), ('offense', 'buy', 'watch'))
        self.assertEqual(_stance(beta, False, True, 3), ('offense', 'buy', 'supplement'))
        self.assertEqual(_stance({'verdict': 'alpha'}, True, True, 2), ('balanced', 'less', 'buy_only'))
        self.assertEqual(_stance({'verdict': 'mixed'}, False, None, 2), ('balanced', 'less', 'watch'))



if __name__ == '__main__':
    unittest.main()
