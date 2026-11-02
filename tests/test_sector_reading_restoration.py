"""Regression examples for retained facts and independent future generation."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from report.sector_daily_report import render_sector_daily
from report.sector_reading_history import historical_assets, numeric_trend_view
from report.sector_reading_content import recorded_fact
from report.sector_reading_sources import build_index_view, collect_index_view, collect_reading_supplements
from report.sector_fact_loader import collect_market_reading_data
from tests.test_sector_daily_cleanup import snapshot

ROOT = Path(__file__).resolve().parents[1]
DAY = '2026-10-20'


class RetainedFactRegressionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = ROOT / 'reports' / f'{DAY}_A股日报_板块日报.html'
        frozen = ROOT / 'snapshots' / f'{DAY}.json'
        if not source.is_file() or not frozen.is_file():
            raise unittest.SkipTest('Local historical baseline is not installed')
        cls.source = source.read_text(encoding='utf-8')
        cls.snapshot = json.loads(frozen.read_text(encoding='utf-8'))

    def test_conflicting_breadth_and_turnover_do_not_mix_with_original_charts(self):
        for key, field, value in (('market_stats', 'up_count', 999),
                                  ('turnover_data', 'total_turnover_yi', 1)):
            frozen = deepcopy(self.snapshot)
            frozen['data'][key][field] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, '图表数值'):
                render_sector_daily(self.source, DAY, snapshot=frozen)

    def test_changed_trend_number_does_not_keep_original_fingerprint(self):
        soup = BeautifulSoup(self.source, 'html.parser')
        view = json.loads(soup.select_one('#sector-trend-view').string)
        view['tracks'][0]['path'][-1]['change_pct'] = 12345
        soup.select_one('#sector-trend-view').string = json.dumps(view)
        with self.assertRaisesRegex(ValueError, '凭据投影'):
            render_sector_daily(str(soup), DAY, snapshot=self.snapshot)

    def test_changed_heat_number_does_not_inherit_trend_fingerprint(self):
        soup = BeautifulSoup(self.source, 'html.parser')
        view = json.loads(soup.select_one('#sector-trend-view').string)
        # Same color band: checking only the color cannot catch this change.
        view['heat']['rows'][0]['pct'][0] += 1
        soup.select_one('#sector-trend-view').string = json.dumps(view)
        with self.assertRaisesRegex(ValueError, '冷暖'):
            render_sector_daily(str(soup), DAY, snapshot=self.snapshot)

    def test_older_page_without_explicit_heat_retains_paths_and_focus(self):
        day = '2026-10-16'
        source = (ROOT / 'reports' / f'{day}_A股日报_板块日报.html').read_text()
        frozen = json.loads((ROOT / 'snapshots' / f'{day}.json').read_text())
        soup = BeautifulSoup(render_sector_daily(source, day, snapshot=frozen), 'html.parser')
        view = json.loads(soup.select_one('#sector-trend-view').string)
        full = historical_assets(str(soup), frozen, day)['trend']
        self.assertEqual(len(full['tracks']), 24)
        self.assertLess(len(view['tracks']), 24)
        self.assertEqual(len(view['heat']['rows']), len(numeric_trend_view(full, day)['chart_selection']['heat_rows']))
        self.assertEqual(view['focus_track']['name'], '文化传媒')
        self.assertEqual(len(soup.select('[data-bear-chart]')), 7)
        changed = BeautifulSoup(source, 'html.parser')
        original = json.loads(changed.select_one('#sector-trend-view').string)
        original['focus_track']['path'][-1]['level'] = 12345
        changed.select_one('#sector-trend-view').string = json.dumps(original)
        with self.assertRaisesRegex(ValueError, '主攻'):
            render_sector_daily(str(changed), day, snapshot=frozen)

    def test_new_format_can_be_replayed_without_losing_charts_or_actual_query_time(self):
        first = render_sector_daily(self.source, DAY, snapshot=self.snapshot)
        second = BeautifulSoup(render_sector_daily(first, DAY, snapshot=self.snapshot), 'html.parser')
        self.assertEqual(len(second.select('[data-bear-chart]')), 7)
        self.assertLess(len(json.loads(second.select_one('#sector-trend-view').string)['tracks']), 30)
        self.assertEqual(len(historical_assets(str(second), self.snapshot, DAY)['trend']['tracks']), 30)
        self.assertIsNotNone(second.select_one('#observation-flow-data'))
        retained = json.loads(second.select_one('#sector-retained-history').string)
        self.assertIn('2026-10-20T20:32:42.675066+08:00', json.dumps(retained['assets']))
        self.assertIsNone(second.select_one('#sector-history-sources'))
        payload = json.loads(second.select_one('#bear-chart-payload').string)
        self.assertGreater(sum(r.get('status') in ('涨停', '跌停') for r in payload['lhb_net_flow']['items']), 0)
        self.assertIsNone(second.select_one('.sector-cycle-calendar, #daily-competition'))
        self.assertEqual(len(second.select('[data-sector-daily-chart]')), 2)
        self.assertFalse(second.select('#trend-fact-next, #trend-fact-reason'))

    def test_selected_replay_source_is_reusable_and_never_reads_official_fallback(self):
        import daily_report_entry_demo as entry
        with TemporaryDirectory() as folder:
            root = Path(folder)
            replay = root / 'replay'
            replay.mkdir()
            original = replay / f'{DAY}_A股日报_板块日报_replay.html'
            original.write_text(self.source, encoding='utf-8')
            def output(day, mode='frozen'):
                return str((replay if mode == 'replay' else root) / f'{day}_A股日报_完整版{"_replay" if mode == "replay" else ""}.md')
            with patch.object(entry, '_get_report_output_path', side_effect=output), \
                 patch('socket.socket.connect', side_effect=AssertionError('No network')):
                for _ in range(2):
                    path = entry._save_standalone_sector_reading_page(self.snapshot['data'], DAY,
                                                                     run_mode='replay', source_mode='replay')
                    result = BeautifulSoup(path.read_text(), 'html.parser')
                    self.assertEqual(len(result.select('[data-bear-chart]')), 7)
                    self.assertIsNotNone(result.select_one('#sector-trend-view'))
                    self.assertFalse(any('完整版' in a['href'] for a in result.select('footer a[href]')))
                    self.assertFalse(any(a['href'] == path.name for a in result.select('footer a[href]')))

    def test_timestamp_without_query_day_is_preserved_but_never_fabricated(self):
        fact = {'trade_date': DAY, 'retrieved_at': DAY + 'T15:30:00+08:00', 'change_pct': 1}
        self.assertEqual(recorded_fact(fact, DAY), fact)
        self.assertNotIn('query_date', fact)
        bad = {**fact, 'retrieved_at': '2099-01-01T15:30:00+08:00'}
        self.assertFalse(recorded_fact(bad, DAY))


class IndependentSectorInputsTest(unittest.TestCase):
    def setUp(self):
        self.cffex_loader = self.enterContext(patch(
            'report.cffex_index_futures_position_evidence.load_cffex_index_futures_position_evidence', return_value=None))
        self.enterContext(patch('report.sector_member_comparison.collect_member_comparison', return_value=None))
        self.enterContext(patch('report.sector_new_high.collect_new_high_series', return_value=None))
        self.enterContext(patch('report.sector_top50.collect_top50_series', return_value=None))
        self.enterContext(patch('report.market_returns.collect_market_returns', return_value=None))

    def test_futures_without_local_store_can_collect_and_failed_sources_remain_visible(self):
        from report.cffex_index_futures_position_evidence import build_unavailable_cffex_evidence
        class Frame:
            def to_dict(self, kind): return []
        class Pro:
            def query(self, *a, **k): pass
            def limit_list_d(self, **k): return Frame()
        class Service:
            repository = None
        service = Service()
        missing = build_unavailable_cffex_evidence(DAY, reason='官方目标日资料尚未发布', query_date=DAY)
        self.cffex_loader.return_value = missing
        data = {'query_date': DAY, 'reading_collected_at': DAY+'T19:00:00+08:00', 'reading_source_notes': []}
        with TemporaryDirectory() as folder, \
             patch('market_data.tushare_market_activity_service.fetch_tushare_sector_flow', return_value=[]), \
             patch('market_data.tushare_market_activity_service.fetch_tushare_top_list', return_value=[]), \
             patch('report.sector_reading_sources.collect_index_view', return_value=None):
            collect_reading_supplements(data, DAY, pro=Pro(), metadata={}, service=service, snapshot_root=folder)
        self.cffex_loader.assert_called_once_with(DAY, service=service, replay=False, query_date=DAY, allow_fresh_write=False)
        self.assertEqual(data['cffex_index_futures_position_evidence'], missing)
        self.assertIn('官方目标日资料尚未发布', ' '.join(data['reading_source_notes']))

    def test_industry_history_uses_actual_page_cap_and_keeps_the_common_start(self):
        class Frame:
            def __init__(self, rows): self.rows = rows
            def to_dict(self, kind): return self.rows
        first = [{'trade_date': DAY, 'ts_code': f'{i:06d}.TI', 'close': 100, 'pct_change': 1}
                 for i in range(3000)]
        prior = '2026-10-19'
        old = {'trade_date': prior, 'ts_code': '000000.TI', 'close': 80, 'pct_change': 1}
        for full_second_page in (False, True):
            second = [{**row, 'trade_date': prior} for row in first] if full_second_page else [old]
            second[0] = old
            class Pro:
                def __init__(self): self.calls = []
                def ths_daily(self, **kwargs):
                    self.calls.append(kwargs)
                    # Behave like the actual provider cap, including when the
                    # caller incorrectly asks for more than 3,000 rows.
                    return Frame({0: first, 3000: second}.get(kwargs['offset'], []))
            pro = Pro()
            with self.subTest(full_second_page=full_second_page), \
                 patch('market_data.tushare_service.fetch_daily_price_bars', return_value=[
                     {'date': prior, 'close': 100}, {'date': DAY, 'close': 101}]):
                view = collect_index_view(pro, {'000000.TI': {
                    'name': '行业例', 'exchange': 'A', 'type': 'I'}}, DAY)
            self.assertEqual([call['offset'] for call in pro.calls],
                             [0, 3000, 6000] if full_second_page else [0, 3000])
            self.assertEqual({call['limit'] for call in pro.calls}, {3000})
            self.assertEqual(view['trade_dates'], [prior, DAY])
            self.assertEqual(view['tracks'][0]['path'][0]['level'], 100)
            self.assertEqual(view['tracks'][0]['path'][1]['level'], 125)
            self.assertEqual(view['tracks'][0]['path'][1]['excess_pp'], 24)

    def test_sixty_session_history_splits_ranges_before_provider_offset_limit(self):
        from datetime import date, timedelta
        end = date.fromisoformat(DAY)
        days = [(end - timedelta(days=i)).isoformat() for i in reversed(range(100))
                if (end - timedelta(days=i)).weekday() < 5][-60:]

        class Frame:
            def __init__(self, rows): self.rows = rows
            def to_dict(self, kind): return self.rows

        class Pro:
            def __init__(self): self.calls = []
            def trade_cal(self, **kwargs): raise AssertionError('calendar is supplied by the fixture')
            def ths_daily(self, **kwargs):
                self.calls.append(kwargs)
                offset = kwargs['offset']
                if offset > 100000:
                    raise ValueError('参数校验失败, offset')
                window = [day for day in days if kwargs['start_date'] <= day.replace('-', '') <= kwargs['end_date']]
                rows = []
                for index in range(offset, min(offset + kwargs['limit'], len(window) * 2500)):
                    day, code = window[index // 2500], index % 2500
                    rows.append({'trade_date': day, 'ts_code': f'{code:06d}.TI',
                                 'close': 100 + days.index(day), 'pct_change': 1})
                return Frame(rows)

        pro = Pro()
        with patch('market_data.tushare_service.fetch_daily_price_bars', return_value=[
                {'date': day, 'close': 100} for day in days]), \
             patch('market_data.tushare_market_activity_service.fetch_tushare_open_trade_dates', return_value=days):
            view = collect_index_view(pro, {'000000.TI': {'name': '行业例', 'exchange': 'A', 'type': 'I'}}, DAY)
        ranges = list(dict.fromkeys((call['start_date'], call['end_date']) for call in pro.calls))
        self.assertEqual(ranges, [(days[i].replace('-', ''), days[i + 19].replace('-', '')) for i in (0, 20, 40)])
        self.assertTrue(all(call['offset'] <= 48000 for call in pro.calls))
        self.assertEqual(view['ranking_returns']['dates'], days)
        self.assertEqual(view['ranking_returns']['rows'][0]['pct'], [1] * 60)
        self.assertEqual(view['trade_dates'], days[-30:])
        self.assertTrue(all(row['level'] is not None for row in view['tracks'][0]['path']))

    def test_history_segment_rejects_rows_outside_its_own_requested_dates(self):
        class Frame:
            def to_dict(self, kind):
                return [{'trade_date': '2026-10-16', 'ts_code': '000000.TI', 'close': 100, 'pct_change': 1}]
        class Pro:
            def ths_daily(self, **kwargs): return Frame()
        with patch('market_data.tushare_service.fetch_daily_price_bars', return_value=[
                {'date': '2026-10-19', 'close': 100}, {'date': DAY, 'close': 101}]), \
             self.assertRaisesRegex(ValueError, '超出查询分段'):
            collect_index_view(Pro(), {'000000.TI': {'name': '行业例', 'exchange': 'A', 'type': 'I'}}, DAY)

    def test_snapshot_only_series_uses_explicit_target_row_provenance(self):
        value = snapshot()
        day = value['date']
        value['data']['top50_turnover_share_series'] = {
            'source': 'tushare.daily', 'query_date': day,
            'rows': [{'trade_date': day, 'source_date': day, 'query_date': day,
                      'market_amount_yi': 100, 'top_amount_yi': 20, 'share_pct': 20}],
        }
        value['data']['new_high_feedback'] = {
            'data_source': 'frozen-fixture', 'query_date': day,
            'trend_rows': [{'trade_date': day, 'source_date': day, 'query_date': day,
                            'new_high_count': 100, 'all_a_share_pct': 2}],
        }
        soup = BeautifulSoup(render_sector_daily(None, day, snapshot=value), 'html.parser')
        payload = json.loads(soup.select_one('#bear-chart-payload').string)
        self.assertEqual(len(soup.select('[data-bear-chart]')), 3)
        for key in ('market_turnover_top50_trend', 'new_high_share_trend'):
            self.assertEqual(payload[key]['source_date'], day)
            self.assertEqual(payload[key]['items'][0]['source_date'], day)
        del value['data']['top50_turnover_share_series']['rows'][0]['source_date']
        with self.assertRaisesRegex(ValueError, '来源日期'):
            render_sector_daily(None, day, snapshot=value)

    def test_snapshot_rank_keeps_its_real_provenance_without_old_html(self):
        value = snapshot()
        day = value['date']
        value['data']['turnover_rank'] = [{'trade_date': day, 'source_date': day, 'query_date': day,
                                          'data_source': 'tushare.daily', 'rank': 1, 'code': '000001',
                                          'name': '例股', 'turnover': 50, 'change_pct': 1}]
        soup = BeautifulSoup(render_sector_daily(None, day, snapshot=value), 'html.parser')
        fact = json.loads(soup.select_one('#bear-chart-payload').string)['turnover_top30']
        self.assertEqual(fact['query_date'], day)
        self.assertEqual(fact['source_date'], day)

    def test_new_entry_keeps_full_turnover_rank_from_already_fetched_daily_rows(self):
        rows = [{'ts_code': f'{600000+i}.SH', 'trade_date': DAY, 'close': 11, 'pre_close': 10,
                 'amount_yi': i+1} for i in range(60)]
        result = collect_market_reading_data(DAY, pro=object(), daily_fetcher=lambda *a, **k: rows,
            ths_daily_fetcher=lambda *a, **k: [], ths_index_map_fetcher=lambda **k: {},
            index_fact_fetcher=lambda day: {}, supplemental_collector=lambda *a, **k: None)
        self.assertEqual(len(result['turnover_rank']), 50)
        self.assertEqual(result['turnover_rank'][0]['turnover'], 60)
        self.assertAlmostEqual(result['top50_turnover_share_series']['rows'][0]['share_pct'],
                               sum(range(11,61))/sum(range(1,61))*100)

    def test_fresh_sources_render_charts_and_paths_without_full_report_or_old_html(self):
        class Frame:
            def __init__(self, rows): self.rows = rows
            def to_dict(self, kind): return self.rows
        class Pro:
            def query(self, *a, **k): pass
            def ths_daily(self, **k): return Frame([
                {'trade_date': d, 'ts_code': '881001.TI', 'close': close, 'pct_change': change}
                for d, close, change in [('20261019', 100, -1), ('20261020', 102, 2)]])
            def limit_list_d(self, **k): return Frame([])
        class Service:
            repository = None
        data = {'query_date': DAY, 'reading_collected_at': DAY+'T19:00:00+08:00', 'reading_source_notes': [],
                'market_stats': {'trade_date': DAY, 'source_date': DAY, 'query_date': DAY,
                                 'data_source': 'tushare.daily', 'up_count': 10, 'down_count': 5},
                'turnover_data': {'date': DAY, 'source_date': DAY, 'query_date': DAY,
                                  'data_source': 'tushare.daily', 'total_turnover_yi': 100}}
        bars = [{'date': '2026-10-19', 'close': 100}, {'date': DAY, 'close': 101}]
        with TemporaryDirectory() as folder, patch('market_data.tushare_service.fetch_daily_price_bars', return_value=bars), \
             patch('market_data.tushare_market_activity_service.fetch_tushare_sector_flow', return_value=[]), \
             patch('market_data.tushare_market_activity_service.fetch_tushare_top_list', return_value=[]), \
             patch('socket.socket.connect', side_effect=AssertionError('Offline source substitutes')):
            collect_reading_supplements(data, DAY, pro=Pro(), metadata={
                '881001.TI': {'name': '行业例', 'type': 'I', 'exchange': 'A'}}, snapshot_root=folder, service=Service())
            soup = BeautifulSoup(render_sector_daily(None, DAY, snapshot={'date':DAY,'data':data}), 'html.parser')
        self.assertEqual(len(soup.select('[data-bear-chart]')), 3)
        self.assertIsNotNone(soup.select_one('#sector-trend-price'))
        view = json.loads(soup.select_one('#sector-trend-view').string)
        self.assertEqual(view['heat']['rows'], [])
        self.assertEqual(data['reading_sector_history']['trend']['heat']['rows'][0]['pct'], [-1, 2])
        self.assertEqual(view['tracks'][0]['path'][-1]['level'], 102)
        self.assertIsNone(view['tracks'][0]['path'][-1]['breadth'])
        self.assertNotIn('selection_workflow', data)

    def test_history_retains_original_query_and_sample_separately_from_this_read(self):
        class Frame:
            def to_dict(self, kind): return []
        class Pro:
            def query(self, *a, **k): pass
            def ths_daily(self, **k): return Frame()
            def limit_list_d(self, **k): return Frame()
        class Service:
            repository = None
        prior = '2026-10-19'
        old = {'date': prior, 'data': {
            'turnover_data': {'date': prior, 'source_date': prior, 'query_date': prior,
                              'data_source': 'old-source', 'total_turnover_yi': 200,
                              'sample_label': '旧成交样本'},
            'top50_turnover_share_series': {'source': 'old-share', 'query_date': prior,
                'query_window': {'rank_scope': 'old-range'},
                'rows': [{'trade_date': prior, 'source_date': prior, 'share_pct': 30, 'top_amount_yi': 60}]},
        }}
        data = {'query_date': DAY, 'reading_collected_at': DAY+'T19:00:00+08:00', 'reading_source_notes': [],
                'turnover_data': {'date': DAY, 'source_date': DAY, 'query_date': DAY,
                                  'data_source': 'new-source', 'total_turnover_yi': 100}}
        with TemporaryDirectory() as folder, patch('market_data.tushare_service.fetch_daily_price_bars', return_value=[]), \
             patch('market_data.tushare_market_activity_service.fetch_tushare_sector_flow', return_value=[]), \
             patch('market_data.tushare_market_activity_service.fetch_tushare_top_list', return_value=[]):
            Path(folder, prior + '.json').write_text(json.dumps(old))
            collect_reading_supplements(data, DAY, pro=Pro(), metadata={}, snapshot_root=folder, service=Service())
            soup = BeautifulSoup(render_sector_daily(None, DAY, snapshot={'date': DAY, 'data': data}), 'html.parser')
        fact = json.loads(soup.select_one('#bear-chart-payload').string)['market_turnover_top50_trend']
        self.assertEqual(fact['query_date'], DAY)
        row = fact['items'][0]
        self.assertEqual(row['query_date'], prior)
        self.assertEqual(row['sample_label'], '旧成交样本')
        self.assertEqual(row['share_provenance']['query_date'], prior)
        self.assertIn('old-range', row['top50_sample_label'])

    def test_conflicting_and_future_index_rows_are_rejected(self):
        meta = {'881001.TI': {'name': '行业例', 'exchange': 'A', 'type': 'I'}}
        rows = [{'trade_date': DAY, 'ts_code':'881001.TI', 'close':100, 'pct_change':1}]
        for bad in ({**rows[0], 'close': 200}, {**rows[0], 'trade_date':'20990101'}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                build_index_view([*rows,bad], meta, [{'date':DAY,'close':100}], DAY)

    def test_share_group_dates_are_checked_before_inheriting_its_provenance(self):
        class Frame:
            def to_dict(self, kind): return []
        class Pro:
            def query(self, *a, **k): pass
            def ths_daily(self, **k): return Frame()
            def limit_list_d(self, **k): return Frame()
        class Service:
            repository = None
        prior = '2026-10-19'
        for metadata in ({'query_date': '2026-10-18'}, {'query_date': '2099-01-01'},
                         {'query_date': 'not-a-date'}, {'source_date': DAY},
                         {'retrieved_at': '2099-01-01T19:00:00+08:00'}):
            old = {'date': prior, 'data': {
                'turnover_data': {'date': prior, 'query_date': prior,
                                  'data_source': 'old-source', 'total_turnover_yi': 200},
                'top50_turnover_share_series': {'source': 'old-share', **metadata,
                    'rows': [{'trade_date': prior, 'share_pct': 30, 'top_amount_yi': 60}]},
            }}
            data = {'query_date': DAY, 'reading_collected_at': DAY+'T19:00:00+08:00',
                    'reading_source_notes': [], 'turnover_data': {
                        'date': DAY, 'query_date': DAY, 'total_turnover_yi': 100}}
            with self.subTest(metadata=metadata), TemporaryDirectory() as folder, \
                 patch('market_data.tushare_service.fetch_daily_price_bars', return_value=[]), \
                 patch('market_data.tushare_market_activity_service.fetch_tushare_sector_flow', return_value=[]), \
                 patch('market_data.tushare_market_activity_service.fetch_tushare_top_list', return_value=[]):
                Path(folder, prior+'.json').write_text(json.dumps(old))
                collect_reading_supplements(data, DAY, pro=Pro(), metadata={}, snapshot_root=folder, service=Service())
                row = data['reading_chart_payload']['market_turnover_top50_trend']['items'][0]
                self.assertEqual(row['total_turnover'], 200)
                self.assertIsNone(row['top50_share_pct'])
                self.assertEqual(row['share_provenance'], {})

    def test_conflicting_mainline_history_is_a_preserved_gap_in_either_order(self):
        class Frame:
            def __init__(self, rows=()): self.rows = list(rows)
            def to_dict(self, kind): return self.rows
        class Pro:
            def query(self, *a, **k): pass
            def ths_daily(self, **k): return Frame([
                {'trade_date': day, 'ts_code': '881001.TI', 'close': 100, 'pct_change': 1}
                for day in ('20261016', '20261019', '20261020')])
            def limit_list_d(self, **k): return Frame()
        class Service:
            repository = None
        prior = '2026-10-19'
        first = {'date': prior, 'primary_mainline': '行业甲', 'secondary_mainline': '贵金属',
                 'rotation_label': '轮动', 'rotation_summary': '原始说明'}
        changes = ({'primary_mainline': '行业乙'}, {'secondary_mainline': '黄金'},
                   {'rotation_label': '爆发'}, {'rotation_summary': '后续说明'})
        for difference in changes:
            for reverse, split in ((False, False), (True, False), (False, True), (True, True)):
                records = [first, {**first, **difference}]
                ordered = records[::-1] if reverse else records
                unchanged = {'date': '2026-10-16', 'primary_mainline': '另一行业'}
                data = {'query_date': DAY, 'reading_collected_at': DAY+'T19:00:00+08:00',
                        'reading_source_notes': [],
                        'turnover_data': {'date': DAY, 'source_date': DAY, 'query_date': DAY,
                                          'total_turnover_yi': 100, 'data_source': 'tushare.daily'},
                        'recent_mainline_history': [unchanged, *(ordered[1:] if split else ordered)]}
                original = deepcopy(data)
                with self.subTest(difference=difference, reverse=reverse, split=split), TemporaryDirectory() as folder, \
                     patch('market_data.tushare_service.fetch_daily_price_bars', return_value=[
                         {'date': day, 'close': 100} for day in ('2026-10-16', prior, DAY)]), \
                     patch('market_data.tushare_market_activity_service.fetch_tushare_sector_flow', return_value=[]), \
                     patch('market_data.tushare_market_activity_service.fetch_tushare_top_list', return_value=[]), \
                     patch('socket.socket.connect', side_effect=AssertionError('Offline source substitutes')):
                    if split:
                        old = {'date': prior, 'data': {'current_mainline_history_record': ordered[0]}}
                        Path(folder, prior+'.json').write_text(json.dumps(old))
                    collect_reading_supplements(data, DAY, pro=Pro(), metadata={
                        '881001.TI': {'name': '行业例', 'type': 'I', 'exchange': 'A'}},
                        snapshot_root=folder, service=Service())
                self.assertEqual(data['recent_mainline_history'], [unchanged])
                self.assertEqual(data['reading_history_conflicts'][0]['date'], prior)
                versions = data['reading_history_conflicts'][0]['versions']
                self.assertEqual([item['record'] for item in versions], ordered)
                self.assertEqual(versions[0]['snapshot_dates'], [prior if split else DAY])
                self.assertEqual(versions[1]['snapshot_dates'], [DAY])
                self.assertIn(prior, data['reading_source_notes'][0])
                self.assertEqual(data['turnover_data'], original['turnover_data'])
                self.assertEqual(data['reading_chart_payload']['market_turnover_top50_trend']['items'][-1]['total_turnover'], 100)
                flow = data['reading_sector_history']['flow']
                self.assertEqual(flow['history'], [unchanged])
                self.assertIn(prior, flow['dates'])
                self.assertFalse(any(node['date'] == prior for node in flow['nodes']))

    def test_identical_mainline_records_keep_one_verified_relay_record(self):
        class Frame:
            def __init__(self, rows): self.rows = rows
            def to_dict(self, kind): return self.rows
        class Pro:
            def query(self, *a, **k): pass
            def ths_daily(self, **k):
                return Frame([{'trade_date': DAY, 'ts_code': '881001.TI', 'close': 100, 'pct_change': 1}])
            def limit_list_d(self, **k): return Frame([])
        class Service:
            repository = None
        prior = '2026-10-19'
        record = {'date': prior, 'primary_mainline': '行业例'}
        data = {'query_date': DAY, 'reading_collected_at': DAY+'T19:00:00+08:00',
                'reading_source_notes': [], 'recent_mainline_history': [record, deepcopy(record)]}
        with TemporaryDirectory() as folder, \
             patch('market_data.tushare_service.fetch_daily_price_bars', return_value=[{'date': DAY, 'close': 100}]), \
             patch('market_data.tushare_market_activity_service.fetch_tushare_sector_flow', return_value=[]), \
             patch('market_data.tushare_market_activity_service.fetch_tushare_top_list', return_value=[]), \
             patch('socket.socket.connect', side_effect=AssertionError('Offline source substitutes')):
            old = {'date': prior, 'data': {'current_mainline_history_record': record}}
            Path(folder, prior+'.json').write_text(json.dumps(old))
            collect_reading_supplements(data, DAY, pro=Pro(), metadata={
                '881001.TI': {'name': '行业例', 'type': 'I', 'exchange': 'A'}},
                snapshot_root=folder, service=Service())
        self.assertEqual(data['recent_mainline_history'], [record])
        self.assertEqual(data['reading_sector_history']['flow']['history'], [record])
        self.assertEqual(data['reading_sector_history']['flow']['sectors'], ['行业例'])
        self.assertEqual(data['reading_source_notes'], [])

    def test_archived_history_conflicts_remain_excluded_after_a_source_leaves_the_window(self):
        class Frame:
            def to_dict(self, kind): return []
        class Pro:
            def query(self, *a, **k): pass
            def ths_daily(self, **k): return Frame()
            def limit_list_d(self, **k): return Frame()
        class Service:
            repository = None
        prior, containing = '2026-10-16', '2026-10-19'
        first = {'date': prior, 'primary_mainline': '行业甲'}
        second = {**first, 'primary_mainline': '行业乙'}
        data = {'query_date': DAY, 'reading_collected_at': DAY+'T19:00:00+08:00', 'reading_source_notes': []}
        with TemporaryDirectory() as folder, \
             patch('market_data.tushare_service.fetch_daily_price_bars', return_value=[]), \
             patch('market_data.tushare_market_activity_service.fetch_tushare_sector_flow', return_value=[]), \
             patch('market_data.tushare_market_activity_service.fetch_tushare_top_list', return_value=[]):
            Path(folder, prior+'.json').write_text(json.dumps({'date': prior, 'data': {
                'current_mainline_history_record': first}}))
            Path(folder, containing+'.json').write_text(json.dumps({'date': containing, 'data': {
                'recent_mainline_history': [], 'reading_history_conflicts': [{'date': prior, 'versions': [
                    {'record': first, 'snapshot_dates': [prior]},
                    {'record': second, 'snapshot_dates': ['2026-10-18']},
                ]}]}}))
            collect_reading_supplements(data, DAY, pro=Pro(), metadata={}, snapshot_root=folder, service=Service())
        self.assertEqual(data['recent_mainline_history'], [])
        versions = data['reading_history_conflicts'][0]['versions']
        self.assertEqual([item['record'] for item in versions], [first, second])
        self.assertEqual(versions[0]['snapshot_dates'], [prior, containing])
        self.assertEqual(versions[1]['snapshot_dates'], ['2026-10-18', containing])
        self.assertIn(prior, data['reading_source_notes'][0])

    def test_live_seal_missing_numbers_remain_missing_and_render_as_valid_json(self):
        class Frame:
            def __init__(self, rows=()): self.rows = list(rows)
            def to_dict(self, kind): return self.rows
        seals = [
            {'trade_date': DAY, 'ts_code': '600001.SH', 'name': '有效封单',
             'close': 10, 'pct_chg': 10, 'fd_amount': 100000000, 'limit': 'U'},
            {'trade_date': DAY, 'ts_code': '600002.SH', 'name': '缺失封单',
             'close': float('inf'), 'pct_chg': float('nan'), 'fd_amount': float('nan'), 'limit': 'U'},
            {'trade_date': DAY, 'ts_code': '600003.SH', 'name': '零封单',
             'close': 10, 'pct_chg': 0, 'fd_amount': 0, 'limit': 'U'},
        ]
        class Pro:
            def query(self, *a, **k): pass
            def ths_daily(self, **k): return Frame([
                {'trade_date': DAY, 'ts_code': '881001.TI', 'close': 100, 'pct_change': 1}])
            def limit_list_d(self, **k): return Frame(seals)
        class Service:
            repository = None
        data = {'query_date': DAY, 'reading_collected_at': DAY+'T19:00:00+08:00', 'reading_source_notes': []}
        with TemporaryDirectory() as folder, \
             patch('market_data.tushare_service.fetch_daily_price_bars', return_value=[{'date': DAY, 'close': 100}]), \
             patch('market_data.tushare_market_activity_service.fetch_tushare_sector_flow', return_value=[
                 {'trade_date': DAY, 'ts_code': '881001.TI', 'industry': '行业例',
                  'net_amount': 2, 'pct_change': 1, 'company_num': 17}]), \
             patch('market_data.tushare_market_activity_service.fetch_tushare_top_list', return_value=[]):
            collect_reading_supplements(data, DAY, pro=Pro(), metadata={
                '881001.TI': {'name': '行业例', 'type': 'I', 'exchange': 'A'}},
                snapshot_root=folder, service=Service())
            json.dumps(data, allow_nan=False)
            page = render_sector_daily(None, DAY, snapshot={'date': DAY, 'data': data})
        self.assertEqual(data['limit_list_d'][0]['fd_amount'], 100000000)
        self.assertIsNone(data['limit_list_d'][1]['fd_amount'])
        self.assertIsNone(data['limit_list_d'][1]['close'])
        self.assertIsNone(data['limit_list_d'][1]['pct_chg'])
        self.assertEqual(data['limit_list_d'][2]['fd_amount'], 0)
        soup = BeautifulSoup(page, 'html.parser')
        self.assertIsNotNone(soup.select_one('#daily-seal-amount'))
        self.assertEqual(data['sector_fund_flow']['inflow'][0]['stock_count'], 17)
        facts = json.loads(soup.select_one('#sector-visualization-payload').string)
        self.assertIn('"stock_count": 17', json.dumps(facts))

    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for the relay runtime check')
    def test_fresh_relay_initializes_and_keeps_controls_without_source_label_dictionary(self):
        program = r'''
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const script = fs.readFileSync(process.argv[1], 'utf8');
for (const sourceLabels of [undefined, {}, {'frozen-source':'Source & reference'}]) {
  const record = {date:'2026-10-19', source:'frozen-source', rotation_summary:'<original>'};
  const data = {dates:[record.date], history:[record], links:[],
    channels:[{id:'primary_mainline', label:'Primary'}],
    nodes:[{name:'node', date:record.date, sector:'Example', depth:0,
      channels:['primary_mainline'], record}]};
  if (sourceLabels !== undefined) data.source_labels = sourceLabels;
  let changes = 0;
  const elements = {
    '#observation-flow-data':{textContent:JSON.stringify(data)},
    '#observation-flow-chart':{style:{}, clientWidth:600, clientHeight:520,
      parentElement:{clientWidth:600, scrollLeft:0}},
    '#observation-flow-disclosure':{open:false}, '#observation-flow-facts':{innerHTML:''},
    '.observation-flow-fallback':{hidden:false},
  };
  for (const id of ['#observation-track','#observation-channel','#observation-window']) {
    elements[id] = {value:id.endsWith('window') ? '7' : '',
      addEventListener(type) { if (type === 'change') changes++; }};
  }
  const root = {dataset:{}, querySelector(selector) { return elements[selector]; }};
  const chart = {resize(){}, setOption(){}, on(){}};
  const echarts = {init() { return chart; }};
  vm.runInNewContext(script, {
    document:{readyState:'complete', documentElement:{}, querySelector() { return root; }},
    window:{echarts, addEventListener(){}}, echarts,
    getComputedStyle() { return {getPropertyValue() { return ''; }}; },
    ResizeObserver:class {observe(){}},
  });
  assert.equal(root.dataset.ready, 'true');
  assert.equal(changes, 3);
  assert.equal(elements['.observation-flow-fallback'].hidden, true);
  assert.match(elements['#observation-flow-facts'].innerHTML, /&lt;original&gt;/);
  if (sourceLabels && sourceLabels['frozen-source']) {
    assert.match(elements['#observation-flow-facts'].innerHTML, /Source &amp; reference/);
  }
}
'''
        subprocess.run([shutil.which('node'), '-e', program,
                        str(ROOT / 'scripts/templates/sector_observation_flow.js')],
                       check=True, capture_output=True, text=True, timeout=15)


if __name__ == '__main__':
    unittest.main()
