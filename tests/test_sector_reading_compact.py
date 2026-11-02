"""A reading page carries selected facts, not another copy of the fact archive."""
from copy import deepcopy
from datetime import date, timedelta
import json
from pathlib import Path
import sys
import unittest

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from report.sector_daily_report import render_sector_daily
from report.sector_reading_history import evidence_hash, historical_assets, numeric_trend_view, render_numeric_trend
from report.sector_reading_sources import build_index_view
from tests import test_sector_trend_tracking as trend_tests


class CompactReadingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        days = [(date(2026, 6, 1) + timedelta(days=i)).isoformat() for i in range(65)]
        metadata, rows = {}, []
        for i in range(70):
            code = f'{886000+i}.TI'
            metadata[code] = {'name': f'概念{i}', 'exchange': 'A', 'type': 'N'}
            changes = [(i - 35) / 100] * len(days)
            if i == 2:
                changes[-6:] = [-2, -2, -2, 2, 2, 2]
            close = 100
            for day, change in zip(days, changes):
                close *= 1 + change / 100
                rows.append({'ts_code': code, 'trade_date': day, 'close': close, 'pct_change': change})
        cls.day = days[-1]
        cls.raw = build_index_view(rows, metadata, [{'date': d, 'close': 100} for d in days],
                                   cls.day, trade_dates=days, index_type='N')
        cls.assets = {'target_date': cls.day, 'record_hash': None, 'trend': cls.raw}
        cls.assets['source_sha256'] = evidence_hash(cls.assets)
        cls.snapshot = {'date': cls.day, 'data': {'reading_sector_history': cls.assets}}

    def render(self):
        return render_sector_daily(None, self.day, snapshot=self.snapshot)

    def test_large_universe_is_validated_but_only_reading_candidates_are_embedded(self):
        before = deepcopy(self.snapshot)
        page = BeautifulSoup(self.render(), 'html.parser')
        view = json.loads(page.select_one('#sector-trend-view').string)
        full = numeric_trend_view(self.raw, self.day)
        self.assertLess(len(view['tracks']), 30)
        self.assertNotIn('price_inputs', view)
        self.assertNotIn('ranking_returns', view)
        self.assertEqual(len(view['heat']['rows']), len(full['chart_selection']['heat_rows']))
        self.assertIsNone(page.select_one('#trend-full-facts'))
        self.assertEqual(self.snapshot, before)
        self.assertLess(len(str(page).encode()), 2_500_000)

    def test_reindexed_last_heat_row_and_recent_turn_keep_identity_and_values(self):
        page = BeautifulSoup(self.render(), 'html.parser')
        view = json.loads(page.select_one('#sector-trend-view').string)
        original = numeric_trend_view(self.raw, self.day)
        expected = [original['heat']['rows'][r['index']] for r in original['chart_selection']['heat_rows']]
        self.assertEqual(view['heat']['rows'], expected)
        self.assertEqual([r['index'] for r in view['chart_selection']['heat_rows']], list(range(len(expected))))
        result = trend_tests.SectorTrendTest().chart_options(page.select_one('.sector-trend'), [
            {'chart': 'sector-trend-revisions', 'event': {
                'componentType': 'series', 'value': [29, len(expected)-1, 0]}}])
        self.assertEqual(result['selection'], expected[-1]['track_id'])
        turns = {r['track_id'] for r in view['chart_selection']['comparison'] if 'turn' in r['groups']}
        self.assertIn('index:886002.TI', turns)
        self.assertTrue(turns <= {t['track_id'] for t in view['tracks']})

    def test_preferred_attention_outside_rank_groups_keeps_its_path(self):
        identity = 'index:886030.TI'
        page = render_numeric_trend(None, self.raw, self.day, preferred_track_id=identity)
        view = json.loads(page.select_one('#sector-trend-view').string)
        self.assertEqual(view['selected_track_id'], identity)
        self.assertIn(identity, {t['track_id'] for t in view['tracks']})
        self.assertLess(len(view['tracks']), 30)

    def test_alternative_and_actual_breadth_outside_ranks_remain_selectable(self):
        raw = deepcopy(self.raw)
        raw.pop('price_inputs')
        raw['tracks'][31]['path'][-1]['breadth'] = .4
        page = render_numeric_trend(None, raw, self.day, retained_track_ids=['index:886030.TI'])
        view = json.loads(page.select_one('#sector-trend-view').string)
        self.assertTrue({'index:886030.TI', 'index:886031.TI'} <= {t['track_id'] for t in view['tracks']})
        self.assertIsNotNone(page.select_one('#sector-trend-breadth'))
        self.assertLess(len(view['tracks']), 30)

    def test_sparse_history_preserves_focus_controls_and_its_concept_link(self):
        from report.sector_concept_flow import build_concept_flow
        days = ['2026-10-21', '2026-10-22', '2026-10-23', '2026-10-26']
        metadata = {code: {'name': code, 'type': 'N', 'exchange': 'A'}
                    for code in ('886001.TI', '886002.TI')}
        raw = build_index_view([
            {'ts_code': code, 'trade_date': day, 'close': 100+i, 'pct_change': 1}
            for code in metadata for i, day in enumerate(days)], metadata,
            [{'date': d, 'close': 100} for d in days], days[-1], trade_dates=days, index_type='N')
        raw.pop('price_inputs')
        raw['focus_track'] = raw['tracks'].pop()
        identity = raw['selected_track_id'] = raw['focus_track']['track_id']
        stamp = '2026-10-26T19:00:00+08:00'
        flow = build_concept_flow(days[-1], days, metadata, [
            {'trade_date': day, 'retrieved_at': stamp, 'rows': [
                {'ts_code': code, 'trade_date': day, 'net_amount': 1} for code in metadata]}
            for day in days], retrieved_at=stamp)
        assets = {'target_date': days[-1], 'record_hash': None, 'trend': raw, 'concept_flow': flow}
        assets['source_sha256'] = evidence_hash(assets)
        snapshot = {'date': days[-1], 'data': {'reading_sector_history': assets}}
        page = render_sector_daily(None, days[-1], snapshot=snapshot)
        soup = BeautifulSoup(page, 'html.parser')
        self.assertIsNotNone(soup.select_one('#sector-trend-view'))
        view = json.loads(soup.select_one('#sector-trend-view').string)
        self.assertEqual(view['selected_track_id'], identity)
        self.assertEqual(view['selected_date'], days[-1])
        self.assertEqual(view['heat']['rows'], [])
        options = trend_tests.SectorTrendTest().chart_options(soup.select_one('.sector-trend'))
        self.assertEqual(options['selection'], identity)
        self.assertEqual(options['date'], days[-1])
        self.assertEqual(len(options['charts']['sector-trend-price']['series'][0]['data']), 4)
        compact_flow = json.loads(soup.select_one('#concept-flow-data').string)
        self.assertIn(identity, {r['track_id'] for r in compact_flow['rows']})
        self.assertEqual(historical_assets(page, snapshot, days[-1]), assets)
        self.assertEqual(render_sector_daily(page, days[-1], snapshot=snapshot), page)

    def test_native_snapshot_is_referenced_not_duplicated_and_replays_twice(self):
        page = self.render()
        for _ in range(2):
            soup = BeautifulSoup(page, 'html.parser')
            bundle = json.loads(soup.select_one('#sector-retained-history').string)
            self.assertNotIn('assets', bundle)
            self.assertEqual(bundle['assets_hash'], evidence_hash(self.assets))
            self.assertEqual(historical_assets(page, self.snapshot, self.day), self.assets)
            page = render_sector_daily(page, self.day, snapshot=self.snapshot)
        self.assertEqual(page, self.render())

    def test_missing_or_different_selected_source_is_not_replaced_by_the_page(self):
        page = self.render()
        with self.assertRaises(ValueError):
            historical_assets(page, {'date': self.day, 'data': {}}, self.day)
        different = deepcopy(self.snapshot)
        different['data']['reading_sector_history']['trend']['tracks'][0]['path'][0]['level'] = 999
        with self.assertRaises(ValueError):
            historical_assets(page, different, self.day)

    def test_rehashed_display_tampering_cannot_replace_snapshot_prices(self):
        soup = BeautifulSoup(self.render(), 'html.parser')
        node = soup.select_one('#sector-trend-view')
        view = json.loads(node.string)
        view['tracks'][0]['path'][-1]['change_pct'] = 999
        node.string = json.dumps(view)
        retained = soup.select_one('#sector-retained-history')
        bundle = json.loads(retained.string)
        if 'view_hashes' in bundle:
            bundle['view_hashes']['sector-trend-view'] = evidence_hash(view)
        bundle['artifact_hash'] = evidence_hash({k: v for k, v in bundle.items() if k != 'artifact_hash'})
        retained.string = json.dumps(bundle)
        with self.assertRaisesRegex(ValueError, '投影|事实|数值'):
            historical_assets(str(soup), self.snapshot, self.day)

    def test_inconsistent_unselected_fact_still_fails_full_validation(self):
        raw = deepcopy(self.raw)
        raw['tracks'][30]['path'][0]['change_pct'] = 999
        with self.assertRaisesRegex(ValueError, '投影'):
            render_numeric_trend(None, raw, self.day)


if __name__ == '__main__':
    unittest.main()
