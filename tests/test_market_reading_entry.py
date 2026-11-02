"""The current daily entry reads market facts without reviving old decisions."""
import io
import datetime
import json
import sys
import unittest
from contextlib import ExitStack, redirect_stdout, redirect_stderr
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

import daily_report_entry_demo as entry
from daily_report_render import build_market_reading_preflight
from tests.test_sector_daily_report import DATE, snapshot
from report import sector_fact_loader as loader
from report.sector_reading_content import sector_facts
import daily_report_source_health as health


class MarketReadingEntryTest(unittest.TestCase):
    def test_old_generation_modes_never_enter_collection_or_account_calculation(self):
        for flags in (['--output-mode', 'short'], ['--output-mode', 'short', '--no-report'],
                      ['--output-mode', 'full', '--historical-rebuild']):
            with self.subTest(flags=flags), patch.object(sys, 'argv', ['entry', DATE, *flags]), \
                 patch.object(entry, 'load_data_snapshot') as load, \
                 patch.object(entry, 'collect_market_reading_data') as collect, \
                 patch.object(entry, 'build_report_outputs') as build, \
                 redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                entry.main()
            load.assert_not_called()
            collect.assert_not_called()
            build.assert_not_called()

    def test_full_only_locates_unchanged_historical_originals(self):
        with TemporaryDirectory() as folder:
            original = Path(folder) / 'old.md'
            original.write_text('historical text')
            with patch.object(sys, 'argv', ['entry', DATE, '--output-mode', 'full']), \
                 patch.object(entry, '_existing_legacy_report_paths', return_value=(original, original.with_suffix('.html'))), \
                 patch.object(entry, 'load_data_snapshot') as load, \
                 patch.object(entry, 'build_report_outputs') as build, redirect_stdout(io.StringIO()) as out:
                self.assertEqual(entry.main(), 0)
            load.assert_not_called()
            build.assert_not_called()
            self.assertEqual(original.read_text(), 'historical text')
            self.assertIn('不是当前建议', out.getvalue())
            self.assertEqual(list(Path(folder).iterdir()), [original])

    def test_explicit_replay_source_reuses_rebuilt_facts_without_live_calls(self):
        import daily_report_snapshot_io as snapshot_io
        with TemporaryDirectory() as folder:
            root = Path(folder)
            rebuilt = snapshot()['data']
            rebuilt['sector_change_up'][0]['name'] = '重建事实'
            with patch.object(snapshot_io, '_snapshot_root', return_value=root / 'snapshots'):
                snapshot_io._save_data_snapshot(rebuilt, DATE, mode='replay')
                snapshot_io._save_data_snapshot(snapshot()['data'], DATE)
                with patch.object(sys, 'argv', ['entry', DATE, '--replay', '--snapshot-source', 'replay']), \
                     patch.object(entry, '_get_report_output_path', side_effect=lambda day, mode='frozen':
                         str(root / ('replay' if mode == 'replay' else 'official') / f'{day}_A股日报_完整版_replay.md')), \
                     patch.object(entry, 'run_source_health_check', return_value={'overall_result': 'ready'}) as check, \
                     patch.object(entry, 'build_report_run_observer', return_value=MagicMock()), \
                     patch.object(entry, 'collect_market_reading_data') as collect, redirect_stdout(io.StringIO()):
                    self.assertEqual(entry.main(), 0)
            page = next((root / 'replay').glob('*.html')).read_text()
            self.assertIn('重建事实', page)
            self.assertEqual(check.call_args.kwargs['snapshot_mode'], 'replay')
            collect.assert_not_called()

    def test_default_never_silently_selects_old_account_mode(self):
        for options in ({}, {'position': '空仓'}, {'tomorrow_empty': True}, {'stock': '000001'}):
            with self.subTest(options=options):
                self.assertEqual(entry._resolve_daily_report_output_mode(SimpleNamespace(**options)), 'sector')
        self.assertEqual(entry._resolve_daily_report_output_mode(SimpleNamespace(output_mode='full')), 'full')

    def test_account_and_stock_flags_require_explicit_legacy_mode_before_io(self):
        for flags in (['-p', '空仓'], ['--tomorrow-empty'], ['--stock', '000001'],
                      ['--stock-name', '样本'], ['--overwrite-official'],
                      ['--position', '空仓', '--output-mode', 'full']):
            with self.subTest(flags=flags), patch.object(sys, 'argv', ['entry', DATE, *flags]), \
                 patch.object(entry, '_select_daily_report_data_path') as choose, \
                 redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                entry.main()
            choose.assert_not_called()

    def test_historical_force_live_is_not_accepted_for_sector_reading(self):
        with patch.object(sys, 'argv', ['entry', DATE, '--force-live']), \
             redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            entry.main()

    def _run(self, root, data, flags=(), *, path='replay', collector_error=None):
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(sys, 'argv', ['entry', DATE, *flags]))
        stack.enter_context(patch.object(entry, '_select_daily_report_data_path', return_value={
            'eligible': False, 'selected_path': path, 'data': data if path == 'snapshot' else {},
        }))
        stack.enter_context(patch.object(entry, 'load_data_snapshot', return_value=(data, '')))
        stack.enter_context(patch.object(entry, '_get_report_output_path', side_effect=lambda day, mode='frozen', **kw:
            str(root / ('replay' if mode == 'replay' else 'official') / f'{day}_A股日报_完整版{"_replay" if mode == "replay" else ""}.md')))
        stack.enter_context(patch.object(entry, 'run_get_snapshot_path', return_value=str(root / 'frozen.json')))
        health = stack.enter_context(patch.object(entry, 'run_source_health_check', return_value={'overall_result': 'ready'}))
        observer = MagicMock()
        stack.enter_context(patch.object(entry, 'build_report_run_observer', return_value=observer))
        mocks = {}
        for name in ('get_daily_data', 'replay_from_snapshot', 'build_report_outputs', 'build_report_preflight',
                     '_inject_previous_report_target_as_existing_position',
                     'generate_single_stock_diagnostic_markdown', '_restore_postgres_sector_first_runtime_facts',
                     'import_daily_report_data_to_postgres', 'persist_report_quality_score', 'build_report_quality_score'):
            mocks[name] = stack.enter_context(patch.object(entry, name, side_effect=AssertionError(f'old path: {name}')))
        save = stack.enter_context(patch.object(entry, '_save_data_snapshot_with_observation'))
        collect = stack.enter_context(patch.object(entry, 'collect_market_reading_data', return_value=data,
                                                  side_effect=collector_error))
        with redirect_stdout(io.StringIO()):
            result = entry.main()
        for mock in mocks.values():
            mock.assert_not_called()
        return result, health, save, collect

    def test_default_replay_is_snapshot_only_and_keeps_all_sources_unchanged(self):
        original = snapshot()['data']
        before = deepcopy(original)
        with TemporaryDirectory() as folder:
            root = Path(folder)
            result, health, save, collect = self._run(root, original, ['--replay'])
            self.assertEqual(result, 0)
            page = next((root / 'replay').glob('*_板块日报_replay.html')).read_text()
            self.assertIn('全国地产', page)
            self.assertIn('板块图表', page)
            self.assertIn('sector-visualization-payload', page)
            visible_text = BeautifulSoup(page, 'html.parser').get_text(' ', strip=True)
            for text in ('B1', 'B2', '0%不参与', 'MA5', 'MA7', '09:30-09:35', '明日执行结论'):
                self.assertNotIn(text, visible_text)
            health.assert_called_once()
            self.assertTrue(health.call_args.kwargs['reading_mode'])
            save.assert_not_called()
            collect.assert_not_called()
        self.assertEqual(original, before)

    def test_default_saved_facts_do_not_need_live_health_or_old_rendering(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            result, health, save, collect = self._run(root, snapshot()['data'], path='snapshot')
            self.assertEqual(result, 0)
            self.assertTrue(health.call_args.kwargs['replay'])
            save.assert_not_called()
            collect.assert_not_called()
            self.assertTrue(list((root / 'replay').glob('*.html')))

    def test_historical_collection_saves_facts_before_page_and_never_official(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            result, _, save, collect = self._run(root, snapshot()['data'], ['--historical-rebuild'], path='live')
            self.assertEqual(result, 0)
            collect.assert_called_once_with(DATE)
            self.assertEqual(save.call_args.args[2], 'replay')
            self.assertFalse(list((root / 'official').glob('*.html')))

    def test_current_date_historical_rebuild_also_only_writes_replay(self):
        today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date().isoformat()
        with patch.object(sys, 'argv', ['entry', today, '--historical-rebuild']), \
             patch.object(entry, 'load_data_snapshot') as load, \
             patch.object(entry, 'collect_market_reading_data', return_value={}), \
             patch.object(entry, '_target_close_missing', return_value=False), \
             patch.object(entry, 'run_source_health_check', return_value={'overall_result': 'ready'}), \
             patch.object(entry, 'build_report_run_observer', return_value=MagicMock()), \
             patch.object(entry, '_save_data_snapshot_with_observation') as save, \
             patch.object(entry, '_save_standalone_sector_reading_page', return_value=Path('replay/page.html')) as page, \
             patch.object(entry.Path, 'exists', return_value=False), redirect_stdout(io.StringIO()):
            self.assertEqual(entry.main(), 0)
        load.assert_not_called()
        self.assertEqual(save.call_args.args[2], 'replay')
        self.assertEqual(page.call_args.kwargs['run_mode'], 'replay')

    def test_force_live_page_follows_snapshot_fallback_including_publication_race(self):
        import daily_report_snapshot_io as snapshot_io
        today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date().isoformat()
        for race in (False, True):
            with self.subTest(race=race), TemporaryDirectory() as folder:
                root = Path(folder)
                original = {'target_date': today, 'version': 'original'}
                fresh = {'target_date': today, 'version': 'fresh'}
                with patch.object(snapshot_io, '_snapshot_root', return_value=root / 'snapshots'):
                    official = Path(snapshot_io._get_snapshot_path(today))
                    if not race:
                        snapshot_io._save_data_snapshot(original, today)
                    real_link = snapshot_io.os.link

                    def publish_competing_snapshot(source, destination):
                        if Path(destination) == official and not official.exists():
                            official.write_text(json.dumps({'date': today, 'mode': 'frozen', 'data': original}))
                        return real_link(source, destination)

                    with patch.object(sys, 'argv', ['entry', today, '--force-live']), \
                         patch.object(entry, 'collect_market_reading_data', return_value=fresh), \
                         patch.object(entry, '_target_close_missing', return_value=False), \
                         patch.object(entry, 'run_source_health_check', return_value={'overall_result': 'ready'}), \
                         patch.object(entry, 'build_report_run_observer', return_value=MagicMock()), \
                         patch.object(entry, '_get_report_output_path', return_value=str(root / f'{today}_A股日报_完整版.md')), \
                         patch.object(entry, '_save_standalone_sector_reading_page', return_value=root / 'replay/page.html') as page, \
                         patch.object(snapshot_io.os, 'link', side_effect=publish_competing_snapshot), redirect_stdout(io.StringIO()):
                        self.assertEqual(entry.main(), 0)
                    self.assertEqual(page.call_args.kwargs['run_mode'], 'replay')
                    self.assertEqual(snapshot_io.load_data_snapshot(today)[0], original)
                    self.assertEqual(snapshot_io.load_data_snapshot(today, mode='replay')[0], fresh)

    def test_entry_retries_competing_page_publication_in_replay(self):
        today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date().isoformat()
        with TemporaryDirectory() as folder:
            root = Path(folder)
            official = root / f'{today}_A股日报_板块日报.html'

            def render_with_competitor(*args, **kwargs):
                if not official.exists():
                    official.write_text('competing publication')
                return 'current reading'

            with patch.object(entry, '_get_report_output_path', side_effect=lambda day, mode='frozen':
                str((root / 'replay' if mode == 'replay' else root) / f'{day}_A股日报_完整版{"_replay" if mode == "replay" else ""}.md')), \
                 patch('report.sector_daily_report.render_sector_daily', side_effect=render_with_competitor):
                result = entry._save_standalone_sector_reading_page({}, today, run_mode='frozen')
            self.assertEqual(result.parent, root / 'replay')
            self.assertEqual(result.read_text(), 'current reading')
            self.assertEqual(official.read_text(), 'competing publication')
            self.assertFalse(list(root.rglob('*.tmp')))

    def test_sector_dates_cannot_be_malformed_or_conflict_with_an_extra_date(self):
        for fields in ({'trade_date': '20-26-09-29'}, {'source_date': '2026--09-29'},
                       {'query_date': '20-26-09-29'}, {'date': '2099-01-01'}):
            with self.subTest(fields=fields):
                value = snapshot()
                row = value['data']['sector_change_up'][0]
                row.update(fields)
                result = sector_facts(value, DATE)
                self.assertNotIn(row['name'], [item['name'] for item in result])

    def test_sector_compact_dates_are_explicitly_normalized(self):
        value = snapshot()
        for row in value['data']['sector_change_up']:
            for field in ('trade_date', 'source_date', 'query_date'):
                row[field] = DATE.replace('-', '')
        rows = sector_facts(value, DATE)
        self.assertEqual(len(rows), 4)
        self.assertEqual({row['trade_date'] for row in rows}, {DATE})
        self.assertEqual({row['source_date'] for row in rows}, {DATE})
        self.assertEqual({row['query_date'] for row in rows}, {DATE})

    def test_missing_source_and_unavailable_future_fact_are_unknown(self):
        for key, label in (('wind_a_alternative', '指数背景'), ('market_stats', '涨跌家数'),
                           ('turnover_data', '两市成交额')):
            for change in ({'data_source': ''}, {'available_at': '2099-01-01T00:00:00+08:00'},
                           {'available_at': 'not-a-time'}, {'retrieved_at': '2099-01-01T00:00:00+08:00'}):
                with self.subTest(key=key, change=change):
                    data = snapshot()['data']
                    data[key].update(change)
                    checks = build_market_reading_preflight(data, DATE)['checks']
                    self.assertEqual(next(row['status'] for row in checks if row['label'] == label), 'missing')

    def test_breadth_rejects_impossible_sample_counts_without_an_account_verdict(self):
        from report.sector_daily_report import render_sector_daily
        for counts in ({'stock_count': 1}, {'stock_count': True}, {'stock_count': 0},
                       {'stock_count': -1}, {'stock_count': 5404.5},
                       {'stock_count': 5404, 'flat_count': 1}, {'flat_count': -1}):
            with self.subTest(counts=counts):
                data = snapshot()['data']
                data['market_stats'].update(counts)
                checks = build_market_reading_preflight(data, DATE)['checks']
                self.assertEqual(next(row['status'] for row in checks if row['label'] == '涨跌家数'), 'missing')
                html = render_sector_daily(None, DATE, snapshot={'date': DATE, 'data': data})
                from report.sector_daily_report import market_background_facts
                self.assertIsNone(market_background_facts(data, DATE)['up_count'])
                self.assertNotIn('0%不参与', html)

    def test_breadth_keeps_zero_counts_and_missing_denominator_distinct(self):
        from report.sector_daily_report import market_background_facts
        data = snapshot()['data']
        self.assertEqual(market_background_facts(data, DATE)['up_count'], 3471)
        data['market_stats'].update(up_count=0, down_count=0, stock_count=3, flat_count=3)
        self.assertEqual(market_background_facts(data, DATE)['up_count'], 0)
        data['market_stats']['flat_count'] = 0
        self.assertIsNone(market_background_facts(data, DATE)['up_count'])

    def test_missing_optional_facts_are_unknown_not_an_account_decision(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            result, _, _, _ = self._run(root, {}, ['--replay'])
            self.assertEqual(result, 0)
            text = next((root / 'replay').glob('*.html')).read_text()
            self.assertIn('无可核对的板块', text)
            self.assertIn('本次尚缺', text)
            self.assertNotIn('0%不参与', text)

    def test_preflight_uses_rendered_numeric_and_date_validity_not_field_presence(self):
        data = snapshot()['data']
        data['wind_a_alternative']['query_date'] = '2099-01-01'
        data['market_stats']['up_count'] = True
        data['turnover_data']['total_turnover_yi'] = 0
        result = build_market_reading_preflight(data, DATE)
        status = {row['label']: row['status'] for row in result['checks']}
        self.assertEqual(status['指数背景'], 'missing')
        self.assertEqual(status['涨跌家数'], 'missing')
        self.assertEqual(status['两市成交额'], 'missing')
        self.assertEqual(result['decision_checks'], [])

    def test_later_query_date_is_separate_from_target_day_facts(self):
        data = snapshot()['data']
        query_date = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date().isoformat()
        data['wind_a_alternative']['query_date'] = query_date
        data['market_stats']['query_date'] = query_date
        data['turnover_data']['query_date'] = query_date
        for key in ('sector_change_up', 'sector_change_down'):
            for row in data.get(key) or []:
                row['query_date'] = query_date
        result = build_market_reading_preflight(data, DATE)
        self.assertEqual({row['status'] for row in result['checks']}, {'available'})
        self.assertTrue(sector_facts({'date': DATE, 'data': data}, DATE))

    def test_query_date_before_target_day_is_not_accepted(self):
        data = snapshot()['data']
        data['wind_a_alternative']['query_date'] = '2026-09-28'
        result = build_market_reading_preflight(data, DATE)
        status = {row['label']: row['status'] for row in result['checks']}
        self.assertEqual(status['指数背景'], 'missing')

    def test_missing_source_or_query_dates_are_unknown_not_inferred(self):
        for key, label in (('wind_a_alternative', '指数背景'), ('market_stats', '涨跌家数'),
                           ('turnover_data', '两市成交额')):
            for field in ('source_date', 'query_date'):
                with self.subTest(key=key, field=field):
                    data = snapshot()['data']
                    data[key].pop(field)
                    checks = build_market_reading_preflight(data, DATE)['checks']
                    self.assertEqual(next(item['status'] for item in checks if item['label'] == label), 'missing')
        for field in ('source_date', 'query_date'):
            data = snapshot()['data']
            row = data['sector_change_up'][0]
            row['data_source'] = 'tushare.ths_daily'
            row.pop(field)
            data['sector_change_up'] = [row]
            self.assertEqual(sector_facts({'date': DATE, 'data': data}, DATE), [])

    def test_future_target_stops_preflight_and_cli_before_any_io(self):
        with self.assertRaises((ValueError, RuntimeError)):
            build_market_reading_preflight({}, '2099-01-01')
        for flags in (['--replay'], ['--historical-rebuild']):
            with self.subTest(flags=flags), patch.object(sys, 'argv', ['entry', '2099-01-01', *flags]), \
                 patch.object(entry, 'run_source_health_check') as check, \
                 patch.object(entry, 'collect_market_reading_data') as collect, \
                 redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                entry.main()
            check.assert_not_called()
            collect.assert_not_called()

    def test_invalid_dates_and_contradictory_top_level_dates_stop_before_render(self):
        for data, date in (({}, '2026-02-30'), ({'target_date': '2026-09-28'}, DATE), ([], DATE)):
            with self.subTest(data=data, date=date), self.assertRaises((ValueError, RuntimeError)):
                build_market_reading_preflight(data, date)


class MarketReadingFactLoaderTest(unittest.TestCase):
    def test_index_conflicting_duplicates_and_date_fields_are_not_usable_facts(self):
        base = {'date': DATE, 'close': 100, 'pre_close': 100}
        for rows in ([base, dict(base, close=150)], [dict(base, trade_date='2099-01-01')]):
            with self.subTest(rows=rows), patch.object(loader, 'fetch_daily_price_bars', return_value=rows):
                data, _ = self.collect(index_fact_fetcher=None)
                self.assertFalse(data['wind_a_alternative'])
                self.assertEqual(build_market_reading_preflight(data, DATE)['checks'][1]['status'], 'missing')

    def test_index_identical_duplicates_do_not_replace_the_previous_close(self):
        bars = [{'date': '2026-09-28', 'close': 100}, {'date': DATE, 'close': 110}]
        with patch.object(loader, 'fetch_daily_price_bars', return_value=[*bars, deepcopy(bars[-1])]):
            fact = loader._index_fact(DATE, pro=object(), ts_module=None)
        self.assertEqual(fact['pre_close'], 100)
        self.assertAlmostEqual(fact['change_pct'], 10)

    def daily_rows(self):
        return [
            {'trade_date': DATE, 'ts_code': code, 'market': market,
             'close': close, 'pre_close': 10, 'amount_yi': amount}
            for code, market, close, amount in (
                ('600001.SH', 'SH', 11, 2), ('000001.SZ', 'SZ', 9, 3), ('830001.BJ', 'BJ', 10, 1),
            )
        ]

    def collect(self, **options):
        defaults = dict(
            pro=object(), daily_fetcher=MagicMock(return_value=self.daily_rows()),
            basic_map_fetcher=MagicMock(return_value={}),
            ths_daily_fetcher=MagicMock(return_value=[
                {'ts_code': '881001.TI', 'trade_date': DATE, 'pct_change': 2},
                {'ts_code': '881002.TI', 'trade_date': DATE, 'pct_change': -1},
            ]),
            ths_index_map_fetcher=MagicMock(return_value={
                '881001.TI': {'exchange': 'A', 'type': 'I', 'name': '行业甲'},
                '881002.TI': {'exchange': 'A', 'type': 'I', 'name': '行业乙'},
            }),
            index_fact_fetcher=MagicMock(return_value={'trade_date': DATE, 'change_pct': 0}),
        )
        defaults.update(options)
        return loader.collect_market_reading_data(DATE, **defaults), defaults

    def test_independent_daily_facts_have_explicit_samples_and_no_account_fields(self):
        data, calls = self.collect()
        self.assertEqual(data['market_stats']['up_count'], 1)
        self.assertEqual(data['market_stats']['down_count'], 1)
        self.assertEqual(data['market_stats']['flat_count'], 1)
        self.assertEqual(data['turnover_data']['total_turnover_yi'], 5)
        self.assertIn('北交所', data['turnover_data']['sample_label'])
        self.assertEqual(data['sector_change_up'], [])
        self.assertEqual(data['sector_change_down'], [])
        self.assertEqual([r['name'] for r in data['industry_background']['rows']], ['行业甲', '行业乙'])
        calls['daily_fetcher'].assert_called_once()
        calls['basic_map_fetcher'].assert_called_once()
        self.assertTrue(all(row['name'] == '名称待确认' for row in data['turnover_rank']))
        for key in ('selection_workflow', 'existing_position_summary', 'position_decision', 'final_target_resolution'):
            self.assertNotIn(key, data)

    def test_mixed_date_or_conflicting_daily_records_do_not_become_partial_totals(self):
        for bad in (
            {**self.daily_rows()[0], 'trade_date': '2099-01-01'},
            {**self.daily_rows()[0], 'close': 99},
            {**self.daily_rows()[0], 'trade_date': ''},
        ):
            with self.subTest(bad=bad):
                data, _ = self.collect(daily_fetcher=MagicMock(return_value=[*self.daily_rows(), bad]))
                self.assertNotIn('market_stats', data)
                self.assertNotIn('turnover_data', data)
                self.assertTrue(data['reading_source_notes'])

    def test_identical_daily_duplicates_are_not_double_counted(self):
        rows = self.daily_rows()
        data, _ = self.collect(daily_fetcher=MagicMock(return_value=[*rows, rows[0]]))
        self.assertEqual(data['market_stats']['stock_count'], 3)
        self.assertEqual(data['turnover_data']['total_turnover_yi'], 5)

    def test_conflicting_date_fields_do_not_become_daily_totals(self):
        rows = self.daily_rows()
        rows[0]['date'] = '2099-01-01'
        data, _ = self.collect(daily_fetcher=MagicMock(return_value=rows))
        self.assertNotIn('market_stats', data)
        self.assertNotIn('turnover_data', data)

    def test_future_collection_stops_before_provider_access(self):
        with patch.object(loader, 'create_tushare_pro_api') as connect, self.assertRaises(ValueError):
            loader.collect_market_reading_data('2099-01-01')
        connect.assert_not_called()

    def test_missing_price_does_not_become_unchanged_stock(self):
        rows = self.daily_rows()
        rows[0]['pre_close'] = None
        data, _ = self.collect(daily_fetcher=MagicMock(return_value=rows))
        self.assertEqual(data['market_stats']['stock_count'], 2)
        self.assertEqual(data['market_stats']['flat_count'], 1)

    def test_historical_collection_does_not_apply_current_industry_map(self):
        mapping = {'600001': {'name': '名称甲', 'industry': '不能倒填的行业'},
                   '000001': {'name': '名称乙', 'industry': '不能倒填的行业'}}
        data, calls = self.collect(ths_daily_fetcher=MagicMock(return_value=[]),
                                   basic_map_fetcher=MagicMock(return_value=mapping))
        self.assertEqual(data['sector_change_up'], [])
        calls['basic_map_fetcher'].assert_called_once()
        self.assertIn('名称乙', [row['name'] for row in data['turnover_rank']])
        self.assertTrue(all('sector' not in row for row in data['turnover_rank']))
        self.assertIn('历史日期不借用', ' '.join(data['reading_source_notes']))

    def test_wrong_date_board_and_missing_index_do_not_turn_into_zero_facts(self):
        data, _ = self.collect(
            ths_daily_fetcher=MagicMock(return_value=[{'ts_code': '881001.TI', 'trade_date': '2099-01-01', 'pct_change': 10}]),
            index_fact_fetcher=MagicMock(side_effect=RuntimeError('source unavailable')),
        )
        self.assertEqual(data['sector_change_up'], [])
        self.assertEqual(data['wind_a_alternative'], {})
        self.assertEqual(build_market_reading_preflight(data, DATE)['checks'][1]['status'], 'missing')

    def test_current_day_aggregate_uses_valid_prices_and_same_day_classification(self):
        now = datetime.datetime.fromisoformat(DATE + 'T19:00:00+08:00')
        mapping = {'600001': {'industry': '行业甲'}, '000001': {'industry': '行业甲'}}
        with patch.object(loader._dt, 'datetime') as clock:
            clock.now.return_value = now
            data, calls = self.collect(ths_daily_fetcher=MagicMock(return_value=[]), basic_map_fetcher=MagicMock(return_value=mapping))
        calls['basic_map_fetcher'].assert_called_once()
        self.assertEqual(data['sector_change_up'], [])
        row = data['industry_background']['rows'][0]
        self.assertEqual(row['stock_count'], 2)
        self.assertAlmostEqual(row['change_pct'], -2)
        self.assertEqual(row['turnover_yi'], 5)
        self.assertEqual(row['query_date'], DATE)


class MarketReadingSourceHealthTest(unittest.TestCase):
    def test_reading_health_never_calls_full_report_optional_sources(self):
        optional = MagicMock(side_effect=AssertionError('unexpected optional source'))
        with TemporaryDirectory() as folder:
            root = Path(folder) / 'logs' / 'source_health'
            root.mkdir(parents=True)
            old = root / 'latest_source_health.json'
            old.write_text('legacy-health')
            result = health.run_source_health_check(
                DATE, root_dir=folder, reading_mode=True, include_cffex=True,
                env={'TUSHARE_TOKEN': 'test-token', 'TUSHARE_HTTP_URL': 'https://example.invalid'},
                tushare_checker=lambda **kw: {'ok': True, 'checks': [{'row_count': 1}]},
                xueqiu_hot_fetcher=optional, xueqiu_argument_fetcher=optional,
                quicktiny_fetcher=optional, investor_qa_fetcher=optional,
                postgres_checker=optional, cffex_checker=optional,
            )
            self.assertEqual(result['overall_result'], 'ready')
            self.assertIn('/sector/live/', result['artifacts']['json_path'])
            self.assertEqual(old.read_text(), 'legacy-health')
            optional.assert_not_called()

    def test_reading_replay_checks_only_snapshot_and_isolates_health_record(self):
        with TemporaryDirectory() as folder, patch.object(health, '_replay_snapshot_check', return_value={
            'id': 'replay.snapshot', 'result': 'pass', 'required_for_generation': True,
        }), patch.object(health, '_tushare_check', side_effect=AssertionError('no network')):
            result = health.run_source_health_check(DATE, root_dir=folder, replay=True, reading_mode=True, env={})
            self.assertIn('/sector/replay/', result['artifacts']['json_path'])
            self.assertEqual(len(result['checks']), 1)


if __name__ == '__main__':
    unittest.main()
