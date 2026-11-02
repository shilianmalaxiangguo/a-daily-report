import json
import sys
import unittest
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from report.hypothesis_revision import _hash
from report.sector_chart_facts import (
    build_sector_display_context, collect_sector_chart_facts,
    load_sector_chart_facts, save_sector_chart_facts, validate_sector_chart_facts,
)
from tests.test_sector_trend_tracking import sample, evidence

STAMP = datetime.fromisoformat('2026-10-14T20:00:00+08:00')


class SectorChartFactsTest(unittest.TestCase):
    def fixture(self):
        record, raw = sample()
        missing = raw['indices']['884240.TI'].pop(2)
        base = evidence(record, raw)
        current = {'date': record['target_date'], 'primary_mainline': '文化传媒'}
        identity = {'name': '文化传媒', 'ts_code': '881164.TI', 'exchange': 'A'}
        focus = [dict(ts_code='881164.TI', trade_date=row['trade_date'], pct_change=2.)
                 for row in raw['market']]
        return record, base, current, identity, missing, focus

    def collect(self, *, replacement=None, focus_change=None):
        record, base, current, identity, missing, focus = self.fixture()
        if focus_change:
            focus_change(focus)
        def fetch(api, start, end, code):
            return focus if code == identity['ts_code'] else [replacement or missing]
        payload = collect_sector_chart_facts(record, base, [], current,
            fetcher=fetch, identity_fetcher=lambda name: identity, now=STAMP)
        return record, base, payload

    def test_dated_hole_is_filled_without_rewriting_frozen_path_or_decision(self):
        record, base, current, identity, missing, focus = self.fixture()
        before = deepcopy((record, base, current))
        payload = collect_sector_chart_facts(record, base, [], current,
            fetcher=lambda api, start, end, code: focus if code == identity['ts_code'] else [missing],
            identity_fetcher=lambda name: identity, now=STAMP)
        self.assertEqual((record, base, current), before)
        self.assertIsNone(base['tracks'][0]['path'][2]['change_pct'])
        self.assertEqual(payload['trend']['tracks'][0]['path'][2]['change_pct'], 1.)
        self.assertEqual(payload['focus_track']['name'], '文化传媒')
        self.assertEqual(payload['focus_track']['path'][0]['level'], 100.)
        self.assertEqual(payload['focus_track']['path'][-1]['change_pct'], 2.)
        self.assertEqual(len(payload['trend']['tracks']), len(base['tracks']))
        self.assertTrue(validate_sector_chart_facts(payload, record, base))

    def test_other_date_or_code_cannot_fill_an_original_hole(self):
        for replacement in (
            dict(ts_code='884240.TI', trade_date='2026-09-04', pct_change=1.),
            dict(ts_code='OTHER.TI', trade_date='2026-09-03', pct_change=1.),
        ):
            with self.subTest(replacement=replacement):
                _, base, payload = self.collect(replacement=replacement)
                self.assertEqual(payload['trend']['tracks'], base['tracks'])
                self.assertIsNone(payload['trend']['tracks'][0]['path'][2]['change_pct'])
                self.assertTrue(payload['issues'])

    def test_focus_rejects_future_and_duplicate_dates_instead_of_fabricating_path(self):
        for change in (
            lambda rows: rows.append(dict(rows[-1], trade_date='2026-10-15')),
            lambda rows: rows.append(dict(rows[-1])),
            lambda rows: rows.append(dict(rows[-1], ts_code='OTHER.TI')),
        ):
            record, base, payload = self.collect(focus_change=change)
            self.assertIsNone(payload['focus_track'])
            self.assertTrue(validate_sector_chart_facts(payload, record, base))

    def test_resigned_payload_cannot_replace_existing_price_or_member_facts(self):
        record, base, payload = self.collect()
        altered = deepcopy(payload)
        altered['trend']['raw']['indices']['884240.TI'][0]['pct_change'] = 3.
        altered['trend'] = evidence(record, altered['trend']['raw'])
        altered['artifact_hash'] = _hash({k: v for k, v in altered.items() if k != 'artifact_hash'})
        self.assertFalse(validate_sector_chart_facts(altered, record, base))
        for key in ('record_hash', 'base_trend_hash', 'target_date'):
            altered = deepcopy(payload)
            altered[key] = 'invalid'
            altered['artifact_hash'] = _hash({k: v for k, v in altered.items() if k != 'artifact_hash'})
            self.assertFalse(validate_sector_chart_facts(altered, record, base))

    def test_failed_or_short_queries_record_their_own_reason(self):
        record, base, current, identity, missing, focus = self.fixture()
        short = collect_sector_chart_facts(record, base, [], {},
            fetcher=lambda api, start, end, code: [], now=STAMP)
        self.assertTrue(short['issues'])
        for issue in short['issues']:
            self.assertEqual(issue['api'], 'ths_daily')
            self.assertEqual(issue['error_type'], 'IncompleteSourceRows')
            self.assertIn('需要1行', issue['error_message'])
            self.assertEqual(issue['issue'], '同源目标日事实仍不完整')

        def unavailable(*args):
            raise RuntimeError('HTTP 401 token已过期')

        failed = collect_sector_chart_facts(record, base, [], {},
            fetcher=unavailable, identity_fetcher=unavailable, now=STAMP)
        self.assertTrue(failed['issues'])
        for issue in failed['issues']:
            self.assertEqual(issue['error_type'], 'RuntimeError')
            self.assertEqual(issue['error_message'], 'HTTP 401 token已过期')

    def test_later_query_failure_cannot_erase_successful_supplement(self):
        record, base, previous = self.collect()
        before = deepcopy(previous)
        def unavailable(*args):
            raise TimeoutError('数据源不可用')
        current = {'date': record['target_date'], 'primary_mainline': '文化传媒'}
        newer = collect_sector_chart_facts(record, base, [], current, previous=previous,
            fetcher=unavailable, identity_fetcher=unavailable,
            now=datetime.fromisoformat('2026-10-14T21:00:00+08:00'))
        self.assertEqual(newer['trend']['tracks'], previous['trend']['tracks'])
        self.assertEqual(newer['focus_track'], previous['focus_track'])
        self.assertEqual(previous, before)
        with TemporaryDirectory() as directory:
            save_sector_chart_facts(previous, record, base, ledger_root=directory)
            save_sector_chart_facts(newer, record, base, ledger_root=directory)
            self.assertEqual(load_sector_chart_facts(record, base, ledger_root=directory), newer)

    def test_saved_supplement_preserves_base_and_detects_disk_tampering(self):
        record, base, payload = self.collect()
        before = deepcopy(base)
        with TemporaryDirectory() as directory:
            path = save_sector_chart_facts(payload, record, base, ledger_root=directory)
            self.assertEqual(load_sector_chart_facts(record, base, ledger_root=directory), payload)
            self.assertEqual(save_sector_chart_facts(payload, record, base, ledger_root=directory), path)
            altered = deepcopy(payload)
            altered['focus_track']['name'] = '地产'
            path.write_text(json.dumps(altered))
            with self.assertRaises(ValueError):
                load_sector_chart_facts(record, base, ledger_root=directory)
        self.assertEqual(base, before)

    def test_display_context_excludes_future_and_keeps_mainline_distinct(self):
        record, base, payload = self.collect()
        day = record['target_date']
        snapshot = {'date': day, 'data': {
            'current_mainline_history_record': {'date': day, 'primary_mainline': '文化传媒'},
            'recent_mainline_history': [
                {'date': '2026-09-09', 'primary_mainline': '通信设备'},
                {'date': '2026-10-15', 'primary_mainline': '未来方向'}],
            'selection_workflow': {'sector_tournament_three_axis': {
                'stage_mainline': {'status': '未形成阶段主线', 'confirmed_directions': []}}}}}
        before = deepcopy(snapshot)
        context = build_sector_display_context(snapshot, day, payload['trend'], payload)
        self.assertEqual([row['date'] for row in context['history']], ['2026-09-09', day])
        self.assertEqual(context['current']['primary_mainline'], '文化传媒')
        self.assertEqual(context['stage_mainline']['confirmed_directions'], [])
        self.assertEqual(snapshot, before)
        snapshot['data']['current_mainline_history_record']['primary_mainline'] = '其他方向'
        with self.assertRaises(ValueError):
            build_sector_display_context(snapshot, day, payload['trend'], payload)
