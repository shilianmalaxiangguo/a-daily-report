from copy import deepcopy
from pathlib import Path
import sys, unittest
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from research.alpha_beta.market_alpha_beta import build_alpha_beta
from research.alpha_beta.decision_board import build_decision_board
from research.alpha_beta.strategy_backtest import daily_choices, history_from_artifact, run_backtest, signals, simulate
from tests.test_decision_board import series
from tests.test_market_alpha_beta import facts, sessions

def world(end='2026-09-29', mutate=None):
    days = sessions(end)
    market, values = series(days)
    if mutate:
        mutate(values)
    value = facts(days, market, values, st=())
    projection = build_alpha_beta(value, days[-1])
    board = build_decision_board(value, days[-1], projection)
    return days, market, values, value, projection, board

class BacktestTest(unittest.TestCase):
    def test_signals_match_the_board_and_never_read_later_sessions(self):
            days, _, _, value, _, board = world()
            h = history_from_artifact(value)
            s = signals(h)
            choices = daily_choices(h, s)
            last = choices[-1]
            self.assertEqual([h['codes'][i] for i in last['alpha']],
                             [c['code'] for c in board['candidates'] if c['status'] == 'buy'])
            self.assertEqual([h['codes'][i] for i in last['beta']], [c['code'] for c in board['beta_basket']])
            t = 40
            cut = deepcopy(h)
            for key in ('returns', 'close', 'open', 'amount'):
                cut[key][:, t + 1:] = cut[key][:, t + 1:] * 0 + 3.0
            cut['m_ret'][t + 1:] = -4.0
            later = daily_choices(cut, signals(cut))
            self.assertEqual(list(later[t]['alpha']), list(choices[t]['alpha']))
            self.assertEqual(list(later[t]['beta']), list(choices[t]['beta']))

    def test_recent_edge_matches_the_board_on_the_last_session(self):
            from research.alpha_beta.strategy_backtest import mark_edges
            for end in ('2026-09-29', '2026-09-30'):
                days, _, _, value, _, board = world(end)
                h = history_from_artifact(value)
                choices = daily_choices(h, signals(h))
                mark_edges(h, choices)
                self.assertEqual(bool(choices[-1]['edge']), bool(board['walk_forward']['summary']['alpha_edge']))

    def test_cash_is_conserved_and_costs_are_paid(self):
            days, _, _, value, _, _ = world()
            h = history_from_artifact(value)
            choices = daily_choices(h, signals(h))
            start = next(t for t, c in enumerate(choices) if c is not None and c['stance'] is not None)
            curve, trades, exposure = simulate(h, choices, 'alpha', start)
            self.assertEqual(len(curve), len(days) - start)
            self.assertTrue(all(0 <= e <= 1 for e in exposure))
            closed = [t for t in trades if t['reason'] != 'open']
            held = [t for t in trades if t['reason'] == 'open']
            gains = sum(t['exit_value'] - t['cost_basis'] for t in closed + held)
            self.assertAlmostEqual(curve[-1], 1 + gains, places=9)
            if closed:
                self.assertTrue(all(t['exit_value'] < t['cost_basis'] * 2 for t in closed))

    def test_run_backtest_reports_every_declared_strategy(self):
            _, _, _, value, _, _ = world()
            result, *_ = run_backtest(history_from_artifact(value), design_start=sessions('2026-09-29')[-10], null_seeds=2)
            self.assertEqual(set(result['stats']), set(result['strategies']))
            self.assertEqual(result['curves']['index'][0], 1.0)
            self.assertEqual(len(result['curves']['alpha']), len(result['dates']))
            self.assertIn('out_of_sample', result['stats']['alpha'])
            self.assertEqual(set(result['ic']), {'own', 'own5', 't_alpha', 'beta'})

    def test_comparisons_equal_weight_and_random_control_use_the_same_window(self):
            from research.alpha_beta.strategy_backtest import _metrics
            days, _, _, value, _, _ = world()
            h = history_from_artifact(value)
            closes = {d: 100 * (1 + 0.01 * k) for k, d in enumerate(days)}
            gap = dict(closes)
            gap.pop(days[-3])
            comparisons = {'399006.SZ': {'name': '创业板指', 'closes': closes}, '000688.SH': {'name': '科创50', 'closes': gap}}
            result, *_ = run_backtest(h, design_start=days[-10], comparisons=comparisons, null_seeds=3)
            again, *_ = run_backtest(h, design_start=days[-10], comparisons=comparisons, null_seeds=3)
            self.assertEqual(result['schema'], 'strategy_backtest.v4')
            window = result['dates']
            held = np.array([closes[d] for d in window]) / closes[window[0]]
            self.assertAlmostEqual(result['comparisons']['399006.SZ']['full']['cagr_pct'], _metrics(held, window)['cagr_pct'], places=9)
            self.assertEqual(result['missing_comparisons'], ['科创50'])
            self.assertNotIn('000688.SH', result['curves'])
            start = h['days'].index(window[0])
            daily = [np.nanmean(np.where(h['eligible'][:, t] & ~np.isnan(h['returns'][:, t]), h['returns'][:, t], np.nan)) / 100
                     for t in range(start + 1, len(h['days']))]
            self.assertAlmostEqual(result['curves']['equal_weight'][-1], round(float(np.prod([1 + x for x in daily])), 6), places=6)
            for key in ('random', 'random_offense'):
                item = result['null'][key]
                self.assertEqual(len(item['cagr_runs']), 3)
                self.assertLessEqual(item['cagr_pct']['min'], item['cagr_pct']['median'])
                self.assertLessEqual(item['cagr_pct']['median'], item['cagr_pct']['max'])
            self.assertEqual(set(result['null']['random']['runs_at_least']), {'alpha', 'beta', 'live_rule'})
            self.assertEqual(result['null'], again['null'])
