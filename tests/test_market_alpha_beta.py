"""Alpha is a stock's own move; beta is the market carrying it. Labels follow the move."""
from copy import deepcopy
from datetime import date, timedelta
import json
from pathlib import Path
import random
import sys
import unittest

import numpy

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from bs4 import BeautifulSoup
from research.alpha_beta.market_alpha_beta import (
    T_CRITICAL, _regime, build_alpha_beta, concept_alpha_beta, headline, render_alpha_beta,
)
from report.market_returns import (
    build_market_returns, encode_prices, price_rows, sessions_from_calendar, validate_market_returns,
)
from report.fact_utils import evidence_hash

RETRIEVED = '2026-09-30T09:00:00+08:00'
BETA, ALPHA, RESILIENT, DOWN, NOISE = '600001.SH', '600002.SH', '600003.SH', '600004.SH', '600005.SH'
GAP, ST, NEW = '600006.SH', '600007.SH', '600008.SH'


def sessions(end='2026-09-29', count=61):
    first = date.fromisoformat(end) - timedelta(days=count - 1)
    return [(first + timedelta(days=i)).isoformat() for i in range(count)]


def scenario(days):
    rng = random.Random(11)
    market = [rng.gauss(0.1, 1.0) if i < len(days) - 20 else rng.gauss(-1.0, 0.8) for i in range(len(days))]
    series = {
        BETA: [1.5 * m + rng.gauss(0, 0.3) for m in market],
        ALPHA: [0.3 * m + rng.gauss(1.2, 0.8) for m in market],
        RESILIENT: [m + 0.5 + rng.gauss(0, 0.2) for m in market],
        DOWN: [0.2 * m - 1.2 + rng.gauss(0, 0.8) for m in market],
        NOISE: [rng.gauss(0, 2.0) for _ in market],
        GAP: [1.2 * m + rng.gauss(0, 0.5) for m in market],
        ST: [m + rng.gauss(0, 0.5) for m in market],
        NEW: [m + rng.gauss(0, 0.5) for m in market],
    }
    series[GAP][-5] = None
    for i in range(40):
        beta = 0.6 + i * 0.025
        series[f'{601000 + i}.SH'] = [beta * m + rng.gauss(0, 0.8) for m in market]
    return market, series


def facts(days, market, series, *, mutate=None, st=(ST,), listing=None, amount=None):
    amount = amount or {}
    bench, level = [], 1000.
    for day, change in zip(days, market):
        previous, level = level, level * (1 + change / 100)
        bench.append({'ts_code': '000985.CSI', 'trade_date': day.replace('-', ''), 'close': level, 'pre_close': previous,
                      'open': previous * (1 + change / 300)})
    pages, prices = {}, {code: 10. for code in series}
    for column, day in enumerate(days):
        rows = []
        for code, values in series.items():
            if values[column] is None:
                continue
            previous = prices[code]
            prices[code] = close = previous * (1 + values[column] / 100)
            rows.append({'ts_code': code, 'trade_date': day.replace('-', ''), 'close': close, 'open': previous * (1 + values[column] / 300),
                         'pre_close': previous, 'pct_chg': round((close - previous) / previous * 100, 4),
                         'amount': amount.get(code, 200000.0)})
        pages[day] = {'source': 'tushare.daily', 'trade_date': day, 'source_date': day, 'rows': rows}
    if mutate:
        mutate(pages, bench)
    listing = {NEW: days[30].replace('-', ''), **(listing or {})}
    basics = [{'ts_code': code, 'name': f'名称{code[:6]}', 'industry': '行业甲' if int(code[:6]) % 2 else '行业乙',
               'list_date': listing.get(code, '20200101')} for code in series]
    st_rows = [{'ts_code': code, 'trade_date': days[-1].replace('-', '')} for code in st]
    return build_market_returns(days[-1], days, pages, bench, basics, st_rows, retrieved_at=RETRIEVED)


def projection(end='2026-09-29', **kwargs):
    days = sessions(end)
    market, series = scenario(days)
    value = facts(days, market, series, **kwargs)
    return days, market, series, value, build_alpha_beta(value, days[-1])


def row_of(result, code, window='20'):
    for rows in result['windows'][window]['lists'].values():
        for row in rows:
            if row['code'] == code:
                return row
    return None


class MarketAlphaBetaTest(unittest.TestCase):
    def test_labels_follow_what_drove_the_move(self):
        _, _, _, _, result = projection()
        labels = {code: (row_of(result, code) or {}).get('label') for code in (BETA, ALPHA, RESILIENT, DOWN)}
        self.assertEqual(labels[ALPHA], 'alpha_up')
        self.assertEqual(labels[RESILIENT], 'resilient')
        self.assertEqual(labels[DOWN], 'alpha_down')
        self.assertEqual(labels[BETA], 'beta')
        resilient = row_of(result, RESILIENT)
        self.assertLess(resilient['total_pct'], 0)
        self.assertGreater(resilient['own_pp'], 0)
        self.assertGreater(resilient['r2'], 0.5)
        stocks = result['scatter_stocks']['codes']
        noise = next(p for p in result['windows']['20']['scatter'] if stocks[p[3]] == NOISE)
        self.assertEqual(result['label_keys'][noise[2]], 'none')

    def test_independent_recomputation_matches_regression_and_shrinkage(self):
        days, market, series, _, result = projection()
        window = result['windows']['20']
        codes = result['scatter_stocks']['codes']
        x = numpy.array(market[-20:])
        slopes, errors, pairs = {}, {}, {}
        for point in window['scatter']:
            code = codes[point[3]]
            y = numpy.array(series[code][-20:], dtype=float)
            slope, intercept = numpy.polyfit(x, y, 1)
            residual = y - (slope * x + intercept)
            errors[code] = numpy.sqrt(residual @ residual / 18 / ((x - x.mean()) @ (x - x.mean())))
            slopes[code] = slope
            pairs[code] = (y, numpy.corrcoef(x, y)[0, 1] ** 2)
            self.assertAlmostEqual(point[0], round(pairs[code][1], 3), places=9)
        mean = numpy.mean(list(slopes.values()))
        variance = numpy.var(list(slopes.values()), ddof=1)
        self.assertAlmostEqual(window['beta_prior']['mean'], round(mean, 4), places=9)
        for code in (BETA, ALPHA, RESILIENT, DOWN):
            row = row_of(result, code)
            weight = variance / (variance + errors[code] ** 2)
            beta = weight * slopes[code] + (1 - weight) * mean
            y = pairs[code][0]
            self.assertAlmostEqual(row['ols_beta'], slopes[code], places=4)
            self.assertAlmostEqual(row['beta'], beta, places=4)
            self.assertAlmostEqual(row['market_pp'], beta * x.sum(), places=3)
            self.assertAlmostEqual(row['own_pp'] + row['market_pp'], y.sum(), places=3)
            self.assertAlmostEqual(row['total_pct'], (numpy.prod(1 + y / 100) - 1) * 100, places=3)
            self.assertAlmostEqual(row['r2'], pairs[code][1], places=4)

    def test_market_regime_counts_compare_with_chance_and_same_direction(self):
        days, market, series, value, result = projection()
        regime = result['regime']
        eligible = [c for c in series if c not in (ST, NEW)]
        today = [series[c][-1] for c in eligible if series[c][-1] is not None]
        same = sum((r > 0) == (market[-1] > 0) for r in today if r != 0) / len([r for r in today if r != 0]) * 100
        self.assertAlmostEqual(regime['same_share'], same, places=9)
        self.assertEqual(regime['up_count'], sum(r > 0 for r in today))
        self.assertEqual(regime['complete'], len(eligible) - 1)
        self.assertAlmostEqual(regime['expected'], regime['complete'] * 0.025)
        self.assertEqual(regime['outperform'], regime['alpha_up'] + regime['resilient'])
        self.assertEqual(len(result['series']), len(days) - 19)
        self.assertEqual(result['series'][-1]['date'], days[-1])

    def test_regime_bands_need_enough_history_and_both_signals(self):
        def points(syncs, alpha_up, resilient=0, complete=1000):
            rows = [{'sync': s, 'alpha_up': 0, 'resilient': 0, 'complete': complete} for s in syncs[:-1]]
            return rows + [{'sync': syncs[-1], 'alpha_up': alpha_up, 'resilient': resilient, 'complete': complete}]
        rising = [i / 100 for i in range(30)]
        self.assertEqual(_regime(points(rising, 20), {})['verdict'], 'beta')
        self.assertEqual(_regime(points(rising[::-1], 60), {})['verdict'], 'alpha')
        self.assertEqual(_regime(points(rising, 60), {})['verdict'], 'mixed')
        self.assertEqual(_regime(points(rising[::-1], 10, 5), {})['abundance'], '少')
        self.assertIsNone(_regime(points(rising[:10], 20), {})['verdict'])

    def test_incomplete_st_and_new_listings_are_not_judged(self):
        _, _, _, value, result = projection()
        judged = set(result['scatter_stocks']['codes'])
        self.assertNotIn(ST, judged)
        self.assertNotIn(NEW, judged)
        twenty = {result['scatter_stocks']['codes'][p[3]] for p in result['windows']['20']['scatter']}
        self.assertNotIn(GAP, twenty)
        self.assertEqual(result['universe']['excluded'], {'st': 1, 'new_listing': 1})
        index = value['codes'].index(GAP)
        self.assertNotIn(index, [row[0] for row in price_rows(value, value['trade_dates'][-5])])

    def test_placeholder_zero_close_and_mismatched_percent_are_rejected(self):
        days = sessions()
        market, series = scenario(days)

        def mutate(pages, _):
            rows = pages[days[10]]['rows']
            rows[0].update(close=0.0, pct_chg=-100.0)
            rows[1]['pct_chg'] = rows[1]['pct_chg'] + 0.5
        value = facts(days, market, series, mutate=mutate)
        self.assertEqual(value['rejected_rows'], {days[10]: 2})
        kept = {value['codes'][row[0]] for row in price_rows(value, days[10])}
        self.assertEqual(len(kept), len(series) - 2)

    def test_partially_updated_day_stays_missing_and_target_day_is_required(self):
        days = sessions()
        market, series = scenario(days)

        def half(pages, _):
            pages[days[20]]['rows'] = pages[days[20]]['rows'][:10]
        value = facts(days, market, series, mutate=half)
        self.assertNotIn(days[20], value['prices'])
        self.assertIn(days[20], [issue['date'] for issue in value['issues']])

        def no_target(pages, _):
            del pages[days[-1]]
        with self.assertRaises(ValueError):
            facts(days, market, series, mutate=no_target)

        def no_benchmark(_, bench):
            bench.pop()
        with self.assertRaises(ValueError):
            facts(days, market, series, mutate=no_benchmark)

        def other_day(pages, _):
            pages[days[3]]['rows'][0]['trade_date'] = days[4].replace('-', '')
        with self.assertRaises(ValueError):
            facts(days, market, series, mutate=other_day)

    def test_tampered_or_redated_facts_are_rejected(self):
        _, _, _, value, _ = projection()
        validate_market_returns(value, value['target_date'])
        changed = deepcopy(value)
        rows = price_rows(changed, value['target_date'])
        rows[0] = (rows[0][0], rows[0][1] * 1.1, *rows[0][2:])
        changed['prices'][value['target_date']] = encode_prices(rows)
        with self.assertRaises(ValueError):
            validate_market_returns(changed, value['target_date'])
        garbled = deepcopy(value)
        garbled['prices'][value['target_date']] += ';x,y'
        garbled['artifact_hash'] = evidence_hash({k: v for k, v in garbled.items() if k != 'artifact_hash'})
        with self.assertRaises(ValueError):
            validate_market_returns(garbled, value['target_date'])
        with self.assertRaises(ValueError):
            validate_market_returns(value, '2026-09-28')
        rehashed = deepcopy(value)
        rehashed['benchmark']['code'] = '000001.SH'
        rehashed['artifact_hash'] = evidence_hash({k: v for k, v in rehashed.items() if k != 'artifact_hash'})
        with self.assertRaises(ValueError):
            validate_market_returns(rehashed, value['target_date'])

    def test_calendar_cannot_skip_days(self):
        rows = [{'cal_date': d.replace('-', ''), 'is_open': 1} for d in sessions('2026-09-29', 70)]
        self.assertEqual(sessions_from_calendar(rows, '2026-09-29'), sessions('2026-09-29'))
        with self.assertRaises(ValueError):
            sessions_from_calendar(rows[:30] + rows[31:], '2026-09-29')
        with self.assertRaises(ValueError):
            sessions_from_calendar(rows[:-1], '2026-09-29')

    def test_concepts_use_the_same_model_without_summing_baskets(self):
        days, market, series, value, _ = projection()
        concepts = {'dates': days[-25:], 'rows': [
            {'track_id': 'index:886001.TI', 'name': '独立题材', 'pct': series[ALPHA][-25:]},
            {'track_id': 'index:886002.TI', 'name': '跟随题材', 'pct': series[BETA][-25:]},
            {'track_id': 'index:886003.TI', 'name': '缺一天', 'pct': [*series[BETA][-25:-1], None]},
        ]}
        result = concept_alpha_beta(concepts, days, [round(m, 6) for m in market], ['index:886002.TI'])
        twenty = result['20']
        self.assertEqual(twenty['complete'], 2)
        self.assertEqual([r['name'] for r in twenty['stronger']], ['独立题材'])
        self.assertEqual([r['name'] for r in twenty['tracked']], ['跟随题材'])
        self.assertNotIn('60', result)


    def test_alpha_beta_section_alone_still_states_the_verdict(self):
        _, _, _, _, result = projection()
        section = render_alpha_beta(BeautifulSoup('', 'html.parser'), result)
        self.assertIn(result['regime']['verdict_text'], section.select_one('.ab-verdict').get_text())
        self.assertEqual(len(section.select('.ab-metric')), 4)
        self.assertTrue(headline(result).startswith(result['regime']['verdict_text']))








if __name__ == '__main__':
    unittest.main()
