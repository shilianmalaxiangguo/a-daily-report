"""Same-universe turnover concentration and independent index alignment."""
from copy import deepcopy
from datetime import date, timedelta
import sys
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from report.sector_top50 import build_top50_series, validate_top50_series, collect_top50_series
from report.sector_reading_history import evidence_hash


def inputs():
    days = [(date(2026, 9, 1) + timedelta(days=i)).isoformat() for i in range(30)]
    stamp = '2026-10-27T11:00:00+08:00'
    calendar = {'rows': [{'date': d, 'is_open': 1} for d in days], 'retrieved_at': stamp}
    pages = {}
    for day in days:
        pages[day] = {'source': 'tushare.daily', 'trade_date': day, 'source_date': day,
            'retrieved_at': stamp, 'amount_unit': '千元', 'rows': [
                {'ts_code': f'{i:06d}.SZ', 'trade_date': day, 'amount': i * 100000}
                for i in range(1, 61)] + [
                {'ts_code': '920001.BJ', 'trade_date': day, 'amount': 9999999999},
                {'ts_code': '000061.SZ', 'trade_date': day, 'amount': 0}]}
        pages[day]['coverage'] = {'source': 'tushare.daily_basic', 'trade_date': day,
            'source_date': day, 'retrieved_at': stamp, 'rows': [
                {'ts_code': f'{i:06d}.SZ', 'trade_date': day, 'turnover_rate': 1.}
                for i in range(1, 61)]}
    index = {'source': 'tushare.index_daily', 'retrieved_at': stamp, 'rows': [
        {'ts_code': '399006.SZ', 'trade_date': d, 'close': 3000+i} for i, d in enumerate(days)]}
    return days, calendar, pages, index, stamp


class SectorTop50Test(unittest.TestCase):
    def build(self, calendar=None, pages=None, index=None):
        days, cal, raw, bars, stamp = inputs()
        return build_top50_series(days[-1], calendar or cal, raw if pages is None else pages,
                                  bars if index is None else index, retrieved_at=stamp)

    def test_twenty_five_open_sessions_recompute_one_universe_and_align_index(self):
        days, cal, pages, index, stamp = inputs()
        result = self.build()
        self.assertEqual(result['trade_dates'], days[-25:])
        self.assertEqual(len(result['items']), 25)
        for row in result['items']:
            self.assertEqual(row['top50_scope'], 'hs_a')
            self.assertEqual(row['sample_count'], 60)
            self.assertEqual(row['coverage_count'], 60)
            self.assertAlmostEqual(row['top50_turnover'], sum(range(11, 61)))
            self.assertAlmostEqual(row['top50_market_amount_yi'], sum(range(1, 61)))
            self.assertAlmostEqual(row['top50_share_pct'], sum(range(11, 61))/sum(range(1, 61))*100)
            self.assertEqual(row['total_turnover'], row['top50_market_amount_yi'])
        self.assertEqual(result['items'][-1]['chinext_close'], 3029)
        self.assertEqual(validate_top50_series(result, days[-1]), result)

    def test_missing_daily_does_not_remove_date_or_borrow_index(self):
        days, cal, pages, index, stamp = inputs()
        del pages[days[-3]]
        index['rows'] = [r for r in index['rows'] if r['trade_date'] != days[-2]]
        result = self.build(pages=pages, index=index)
        self.assertIsNone(result['items'][-3]['top50_share_pct'])
        self.assertEqual(result['items'][-3]['chinext_close'], 3027)
        self.assertIsNone(result['items'][-2]['chinext_close'])
        self.assertIsNotNone(result['items'][-2]['top50_share_pct'])

    def test_reject_wrong_unit_duplicate_wrong_date_and_small_samples(self):
        for mutation in ('unit', 'duplicate', 'wrong_day', 'small', 'nan', 'source_date'):
            days, cal, pages, index, stamp = inputs()
            page = pages[days[-1]]
            if mutation == 'unit': page['amount_unit'] = '元'
            elif mutation == 'duplicate': page['rows'].append(deepcopy(page['rows'][0]))
            elif mutation == 'wrong_day': page['rows'][0]['trade_date'] = days[-2]
            elif mutation == 'small': page['rows'] = page['rows'][:49]
            elif mutation == 'nan': page['rows'][0]['amount'] = float('nan')
            else: page['source_date'] = days[-2]
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.build(pages=pages)

    def test_calendar_holes_conflicts_and_future_are_rejected(self):
        for mutation in ('hole', 'duplicate', 'future', 'index_conflict'):
            days, cal, pages, index, stamp = inputs()
            if mutation == 'hole': del cal['rows'][5]
            elif mutation == 'duplicate': cal['rows'].append(deepcopy(cal['rows'][0]))
            elif mutation == 'future': cal['rows'][-1]['date'] = '2099-01-01'
            else: index['rows'].append(dict(index['rows'][-1], close=9000))
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.build(calendar=cal, index=index)

    def test_legal_but_partial_responses_are_not_a_market_denominator(self):
        for mutation in ('daily', 'coverage', 'missing', 'date', 'duplicate', 'timestamp'):
            days, cal, pages, index, stamp = inputs()
            page = pages[days[-1]]
            if mutation == 'daily': page['rows'] = page['rows'][:50]
            elif mutation == 'coverage': page['coverage']['rows'] = page['coverage']['rows'][:50]
            elif mutation == 'missing': del page['coverage']
            elif mutation == 'date': page['coverage']['rows'][0]['trade_date'] = days[-2]
            elif mutation == 'duplicate': page['coverage']['rows'].append(deepcopy(page['coverage']['rows'][0]))
            else: page['coverage']['retrieved_at'] = '2099-01-01T00:00:00+08:00'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.build(pages=pages)

    def test_collector_does_not_cache_a_partial_response(self):
        days, cal, pages, index, stamp = inputs()
        def fetch(pro, endpoint, **params):
            if endpoint == 'index_daily': return index['rows']
            day = params['trade_date']
            day = day[:4]+'-'+day[4:6]+'-'+day[6:]
            page = pages[day]
            return page['rows'][:50] if endpoint == 'daily' else page['coverage']['rows']
        with tempfile.TemporaryDirectory() as root, \
                patch('report.sector_new_high._calendar', return_value=(days[-25:], cal)), \
                patch('report.sector_new_high._pages', side_effect=fetch):
            result = collect_top50_series(object(), days[-1], cache_root=root)
            self.assertFalse(list(Path(root).glob('*.json')))
            self.assertTrue(all(r['top50_share_pct'] is None and r['missing_reason'] for r in result['items']))
            self.assertTrue(all(r['chinext_close'] is not None for r in result['items']))

    def test_invalid_cached_input_is_preserved_and_replaced_only_by_checked_data(self):
        days, cal, pages, index, stamp = inputs()
        def fetch(pro, endpoint, **params):
            if endpoint == 'index_daily': return index['rows']
            day = params['trade_date']
            day = day[:4]+'-'+day[4:6]+'-'+day[6:]
            return pages[day]['rows'] if endpoint == 'daily' else pages[day]['coverage']['rows']
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / (days[-1]+'.json')
            broken = deepcopy(pages[days[-1]])
            broken['rows'] = broken['rows'][:50]
            original = json.dumps(broken).encode()
            path.write_bytes(original)
            with patch('report.sector_new_high._calendar', return_value=(days[-25:], cal)), \
                    patch('report.sector_new_high._pages', side_effect=fetch):
                result = collect_top50_series(object(), days[-1], cache_root=root)
            self.assertEqual(result['items'][-1]['sample_count'], 60)
            self.assertEqual(json.loads(path.read_text())['coverage']['rows'], pages[days[-1]]['coverage']['rows'])
            self.assertEqual(next(Path(root).glob('*.invalid-*.json')).read_bytes(), original)

    def test_rehashed_projection_is_still_recomputed(self):
        result = self.build()
        result['items'][-1]['top50_share_pct'] += 1
        result['artifact_hash'] = evidence_hash({k: v for k, v in result.items() if k != 'artifact_hash'})
        with self.assertRaises(ValueError):
            validate_top50_series(result, result['target_date'])

    def test_later_collection_is_honest_but_future_or_early_timestamp_is_not(self):
        days, cal, pages, index, stamp = inputs()
        pages[days[-1]]['retrieved_at'] = '2099-01-01T00:00:00+08:00'
        with self.assertRaises(ValueError): self.build(pages=pages)
        pages[days[-1]]['retrieved_at'] = '2026-09-01T00:00:00+08:00'
        with self.assertRaises(ValueError): self.build(pages=pages)


if __name__ == '__main__':
    unittest.main()
