from copy import deepcopy
from datetime import date, timedelta
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from report.sector_new_high import build_new_high_day, collect_new_high_series, validate_new_high_series
from report.sector_reading_history import evidence_hash

DAY = '2026-10-22'
STAMP = '2026-10-23T10:00:00+08:00'


def raw_day(day=DAY):
    return {'trade_date': day, 'retrieved_at': STAMP,
            'daily_rows': [{'ts_code': f'{i:06}.SZ', 'trade_date': day, 'high': 10, 'vol': 100, 'amount': 100}
                           for i in range(1, 5)],
            'factor_rows': [{'ts_code': f'{i:06}.SZ', 'trade_date': day, 'topdays': v}
                            for i, v in ((1, 250), (2, 249), (3, 300))],
            'st_rows': [{'ts_code': '000003.SZ', 'trade_date': day}],
            'list_dates': {f'{i:06}.SZ': '2020-01-01' if i < 4 else day for i in range(1, 5)}}


class SectorNewHighTest(unittest.TestCase):
    def test_actual_daily_denominator_and_exact_date_exclusions(self):
        raw = raw_day()
        day = build_new_high_day(raw)
        self.assertEqual(day['new_high_count'], 1)
        self.assertEqual(day['all_a_denominator'], 4)
        self.assertEqual(day['new_high_share_pct'], 25)
        self.assertEqual(day['eligible_count'], 2)
        self.assertEqual(day['excluded_counts'], {'st': 1, 'recent_listing': 1})
        self.assertEqual(day['query_date'], '2026-10-23')
        self.assertEqual(day['source_date'], DAY)
        raw['factor_rows'][0]['topdays'] = 0
        self.assertEqual(build_new_high_day(raw)['new_high_count'], 0)

    def test_missing_or_invalid_eligible_factor_is_not_zero(self):
        for value in (None, '', float('nan'), -1, True):
            raw = raw_day()
            raw['factor_rows'][0]['topdays'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                build_new_high_day(raw)
        raw = raw_day()
        raw['factor_rows'].pop(0)
        with self.assertRaisesRegex(ValueError, '因子'):
            build_new_high_day(raw)
        for field in ('daily_rows', 'st_rows'):
            raw = raw_day()
            raw[field] = []
            with self.subTest(field=field), self.assertRaises(ValueError):
                build_new_high_day(raw)
        raw = raw_day()
        raw['daily_rows'].pop(0)
        with self.assertRaisesRegex(ValueError, '覆盖'):
            build_new_high_day(raw)

    def test_wrong_dates_duplicates_and_unknown_listing_are_rejected(self):
        for field in ('factor_rows', 'daily_rows', 'st_rows'):
            raw = raw_day()
            raw[field][0]['trade_date'] = '2026-10-21'
            with self.subTest(field=field), self.assertRaises(ValueError):
                build_new_high_day(raw)
        raw = raw_day()
        raw['factor_rows'].append(dict(raw['factor_rows'][0], topdays=1))
        with self.assertRaises(ValueError):
            build_new_high_day(raw)
        raw = raw_day()
        del raw['list_dates']['000001.SZ']
        with self.assertRaises(ValueError):
            build_new_high_day(raw)
        raw = raw_day()
        raw['retrieved_at'] = '2026-10-21T10:00:00+08:00'
        with self.assertRaises(ValueError):
            build_new_high_day(raw)

    def collect(self, pro, root, days=('2026-10-21', DAY)):
        start = date.fromisoformat(DAY) - timedelta(days=70)
        rows = [{'cal_date': (start + timedelta(days=i)).isoformat(),
                 'is_open': int((start + timedelta(days=i)).isoformat() in days)} for i in range(71)]
        frame = Mock()
        frame.to_dict.return_value = rows
        pro.trade_cal.return_value = frame
        return collect_new_high_series(pro, DAY, cache_root=root, window_days=max(1, len(days)))

    def test_cache_is_recomputed_and_missing_target_remains_dated_with_reason(self):
        with tempfile.TemporaryDirectory() as root:
            raw = raw_day('2026-10-21')
            Path(root, '2026-10-21.json').write_text(json.dumps(raw))
            pro = Mock()
            pro.stock_basic.side_effect = RuntimeError('source unavailable')
            series = self.collect(pro, root)
        self.assertEqual([r['date'] for r in series['items']], ['2026-10-21', DAY])
        self.assertEqual(series['items'][0]['new_high_count'], 1)
        self.assertIsNone(series['items'][-1]['new_high_count'])
        self.assertIn('RuntimeError', series['items'][-1]['missing_reason'])
        validate_new_high_series(series, DAY)
        corrupt = deepcopy(series)
        corrupt['items'][0]['new_high_share_pct'] = 99
        corrupt['artifact_hash'] = evidence_hash({k: v for k, v in corrupt.items() if k != 'artifact_hash'})
        with self.assertRaises(ValueError):
            validate_new_high_series(corrupt, DAY)

    def test_fresh_collection_retries_failed_day_and_reuses_complete_raw_days(self):
        pro = Mock()
        raw = raw_day()
        raw['list_dates']['000004.SZ'] = '2026-10-01'
        pro.stock_basic.return_value.to_dict.return_value = []
        def basics(**kwargs):
            frame = Mock()
            frame.to_dict.return_value = ([{'ts_code': c, 'list_date': d} for c, d in raw['list_dates'].items()]
                                          if kwargs['list_status'] == 'L' else [])
            return frame
        pro.stock_basic.side_effect = basics
        for endpoint, field in (('daily', 'daily_rows'), ('stk_factor_pro', 'factor_rows'), ('stock_st', 'st_rows')):
            def fetch(field=field, **kwargs):
                frame = Mock()
                frame.to_dict.return_value = [dict(r, trade_date=kwargs['trade_date']) for r in raw[field]]
                return frame
            getattr(pro, endpoint).side_effect = fetch
        original = pro.stk_factor_pro.side_effect
        def failing(**kwargs):
            if kwargs['trade_date'] == DAY.replace('-', ''):
                raise RuntimeError('temporary upstream failure')
            return original(**kwargs)
        pro.stk_factor_pro.side_effect = failing
        with tempfile.TemporaryDirectory() as root:
            first = self.collect(pro, root)
            self.assertEqual(first['items'][0]['new_high_count'], 1)
            self.assertIsNone(first['items'][1]['new_high_count'])
            self.assertFalse(Path(root, DAY + '.json').exists())
            pro.stk_factor_pro.side_effect = original
            pro.daily.reset_mock()
            second = self.collect(pro, root)
            self.assertEqual([r['new_high_count'] for r in second['items']], [1, 1])
            self.assertEqual(pro.daily.call_count, 1)
            self.assertEqual(pro.daily.call_args.kwargs['trade_date'], '20261022')

    def test_page_offsets_and_unproven_calendar_do_not_silently_drop_dates(self):
        from report.sector_new_high import _pages
        pro = Mock()
        first, second = Mock(), Mock()
        first.to_dict.return_value, second.to_dict.return_value = [{'id': 1}, {'id': 2}], [{'id': 3}]
        pro.daily.side_effect = [first, second]
        self.assertEqual(len(_pages(pro, 'daily', limit=2)), 3)
        self.assertEqual([call.kwargs['offset'] for call in pro.daily.call_args_list], [0, 2])
        for days in ([], ['2026-10-21'], [DAY, DAY], [DAY, '2026-10-23']):
            with self.subTest(days=days), tempfile.TemporaryDirectory() as root, self.assertRaises(ValueError):
                self.collect(pro, root, days)
        pro = Mock()
        pro.trade_cal.return_value.to_dict.return_value = [{'cal_date': DAY, 'is_open': 1}]
        with tempfile.TemporaryDirectory() as root, self.assertRaisesRegex(ValueError, '日历不完整'):
            collect_new_high_series(pro, DAY, cache_root=root)
        start = date.fromisoformat(DAY) - timedelta(days=70)
        rows = [{'cal_date': (start + timedelta(days=i)).isoformat(), 'is_open': int(i == 70)} for i in range(71)]
        pro.trade_cal.return_value.to_dict.return_value = rows
        with tempfile.TemporaryDirectory() as root, self.assertRaisesRegex(ValueError, '开放日不足'):
            collect_new_high_series(pro, DAY, cache_root=root)
        pro.trade_cal.return_value.to_dict.return_value = [dict(r, is_open=1) for r in rows if r['cal_date'] != '2026-10-21']
        with tempfile.TemporaryDirectory() as root, self.assertRaisesRegex(ValueError, '日历不完整'):
            collect_new_high_series(pro, DAY, cache_root=root)

    def test_bad_cache_is_preserved_and_retried_not_permanently_missing(self):
        pro = Mock()
        pro.stock_basic.side_effect = RuntimeError('source temporarily unavailable')
        with tempfile.TemporaryDirectory() as root:
            path = Path(root, DAY + '.json')
            path.write_text('{"trade_date":')
            for _ in range(2):
                series = self.collect(pro, root, (DAY,))
                self.assertIsNone(series['items'][0]['new_high_count'])
                self.assertIn('RuntimeError', series['items'][0]['missing_reason'])
            self.assertEqual(pro.stock_basic.call_count, 2)
            self.assertEqual(len(list(Path(root).glob('*.invalid-*.json'))), 1)
            raw = raw_day()
            def basics(**kwargs):
                frame = Mock()
                frame.to_dict.return_value = ([{'ts_code': c, 'list_date': d} for c, d in raw['list_dates'].items()]
                                              if kwargs['list_status'] == 'L' else [])
                return frame
            pro.stock_basic.side_effect = basics
            for endpoint, field in (('daily', 'daily_rows'), ('stk_factor_pro', 'factor_rows'), ('stock_st', 'st_rows')):
                getattr(pro, endpoint).return_value.to_dict.return_value = raw[field]
            repaired = self.collect(pro, root, (DAY,))
            self.assertEqual(repaired['items'][0]['new_high_count'], 1)
            pro.reset_mock()
            self.assertEqual(self.collect(pro, root, (DAY,))['items'][0]['new_high_count'], 1)
            pro.daily.assert_not_called()

    def test_validated_snapshot_overrides_only_new_high_in_existing_html(self):
        from report.sector_reading_content import chart_evidence
        with tempfile.TemporaryDirectory() as root:
            Path(root, DAY + '.json').write_text(json.dumps(raw_day()))
            series = self.collect(Mock(), root, (DAY,))
        old = {'new_high_share_trend': {'target_date': DAY, 'items': [{'date': DAY, 'new_high_share_pct': None}]},
               't0_market_breadth': {'target_date': DAY, 'items': [{'date': DAY, 'up_count': 1, 'down_count': 2}]}}
        source = f'<html><head><title>{DAY}</title></head><body><script id="bear-chart-payload">{json.dumps(old)}</script><section data-bear-chart-card="t0_market_breadth"></section></body></html>'
        soup, cards = chart_evidence(source, DAY, recorded=True, snapshot_payload={'new_high_share_trend': series})
        charts = json.loads(soup.select_one('#bear-chart-payload').string)
        self.assertEqual(charts['new_high_share_trend']['items'][0]['new_high_count'], 1)
        self.assertEqual(charts['new_high_share_trend']['items'][0]['all_a_denominator'], 4)
        self.assertEqual(charts['t0_market_breadth']['items'][0]['up_count'], 1)
        caption = next(card for card in cards if card['data-bear-chart-card'] == 'new_high_share_trend').get_text()
        self.assertIn('当日有成交A股样本', caption)
        self.assertIn('不拼接历史混合统计', caption)
        self.assertNotIn('固定5000分母', caption)

    def test_repeated_render_uses_repair_but_rejects_unrelated_snapshot_changes(self):
        from bs4 import BeautifulSoup
        from report.sector_daily_report import render_sector_daily
        data = {'target_date': DAY, 'reading_source_notes': []}
        old_chart = {'new_high_share_trend': {'target_date': DAY, 'items': [
            {'date': DAY, 'new_high_share_pct': None}]}}
        assets = {'target_date': DAY, 'source_sha256': 'a' * 64, 'record_hash': None}
        retained = {'target_date': DAY, 'snapshot_hash': evidence_hash(data), 'assets': assets,
                    'chart_hash': evidence_hash(old_chart)}
        retained['artifact_hash'] = evidence_hash(retained)
        source = f'<html><head><title>{DAY}</title></head><body><script id="bear-chart-payload">{json.dumps(old_chart)}</script><script id="sector-retained-history">{json.dumps(retained)}</script></body></html>'
        with tempfile.TemporaryDirectory() as root:
            Path(root, DAY + '.json').write_text(json.dumps(raw_day()))
            data['reading_new_high'] = self.collect(Mock(), root, (DAY,))
        snapshot = {'date': DAY, 'data': data}
        original = source
        with patch('socket.socket.connect', side_effect=AssertionError('offline replay')):
            for _ in range(2):
                source = render_sector_daily(source, DAY, snapshot=snapshot, historical_snapshot=True)
                soup = BeautifulSoup(source, 'html.parser')
                self.assertEqual(json.loads(soup.select_one('#bear-chart-payload').string)[
                    'new_high_share_trend']['items'][0]['new_high_count'], 1)
        data['unrelated_change'] = True
        with self.assertRaisesRegex(ValueError, '指纹'):
            render_sector_daily(original, DAY, snapshot=snapshot, historical_snapshot=True)

    def test_live_supplement_calls_independent_collection_without_old_history_query(self):
        from report.sector_reading_sources import collect_reading_supplements
        with tempfile.TemporaryDirectory() as root:
            Path(root, DAY + '.json').write_text(json.dumps(raw_day()))
            series = self.collect(Mock(), root, (DAY,))
            pro, service = Mock(), Mock()
            pro.limit_list_d.return_value.to_dict.return_value = []
            data = {'query_date': '2026-10-23', 'reading_collected_at': STAMP, 'reading_source_notes': []}
            with patch('report.sector_new_high.collect_new_high_series', return_value=series) as collect, \
                 patch('market_data.tushare_market_activity_service.fetch_tushare_sector_flow', return_value=[]), \
                 patch('market_data.tushare_market_activity_service.fetch_tushare_top_list', return_value=[]), \
                 patch('report.sector_reading_sources.collect_index_view', return_value=None), \
                 patch('report.cffex_index_futures_position_evidence.load_cffex_index_futures_position_evidence', return_value=None):
                collect_reading_supplements(data, DAY, pro=pro, metadata={}, service=service, snapshot_root=root)
            collect.assert_called_once_with(pro, DAY)
            service.query_new_high_feedback_series.assert_not_called()
            self.assertEqual(data['reading_new_high'], series)
            self.assertEqual(data['reading_chart_payload']['new_high_share_trend'], series)

    def test_failed_new_collection_never_reuses_old_target_value(self):
        from report.sector_reading_sources import collect_reading_supplements
        pro, service = Mock(), Mock()
        pro.limit_list_d.return_value.to_dict.return_value = []
        data = {'query_date': '2026-10-23', 'reading_collected_at': STAMP, 'reading_source_notes': [],
                'new_high_feedback': {'trade_date': DAY, 'new_high_count': 999, 'all_a_share_pct': 19.98}}
        with tempfile.TemporaryDirectory() as root, \
             patch('report.sector_new_high.collect_new_high_series', side_effect=ValueError('日历缺失')), \
             patch('market_data.tushare_market_activity_service.fetch_tushare_sector_flow', return_value=[]), \
             patch('market_data.tushare_market_activity_service.fetch_tushare_top_list', return_value=[]), \
             patch('report.sector_reading_sources.collect_index_view', return_value=None), \
             patch('report.cffex_index_futures_position_evidence.load_cffex_index_futures_position_evidence', return_value=None):
            collect_reading_supplements(data, DAY, pro=pro, metadata={}, service=service, snapshot_root=root)
        row = data['reading_chart_payload']['new_high_share_trend']['items'][-1]
        self.assertEqual(row['date'], DAY)
        self.assertIsNone(row['new_high_count'])
        self.assertIsNone(row['new_high_share_pct'])
        self.assertTrue(row['missing_reason'])


if __name__ == '__main__':
    unittest.main()
