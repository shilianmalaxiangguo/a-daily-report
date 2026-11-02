"""Exercise the real current CLI independently of the historical compatibility module."""
from copy import deepcopy
import io
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from contextlib import redirect_stdout, redirect_stderr
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import daily_report_current as current
from daily_report_reading_checks import ReportCriticalDataMissingError
from report.sector_reading_sources import _compact_history_snapshot
from tests.test_sector_choice import sample
from tests.test_sector_daily_report import DATE, snapshot
from report.sector_choice import build_sector_choice


class CurrentEntryIsolationTest(unittest.TestCase):
    def test_both_cli_commands_start_without_retired_modules_or_external_paths(self):
        # Reject forbidden imports as they occur, including imports later hidden
        # from sys.modules. Each command starts in a fresh interpreter.
        source = '''
import importlib.abc
import runpy
import sys
from pathlib import Path
sys.path.insert(0, str(Path('scripts').resolve()))
retired = ('daily_report_entry_demo', 'daily_report_render',
           'quant_trading_system', 'domains.execution_chain',
           'report.runtime', 'report.formal_account_decision',
           'report.selection_workflow', 'report.position_context',
           'report.compact_bear_report', 'report.decision_board',
           'report.strategy_backtest', 'report.market_alpha_beta')
class BlockRetired(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if any(fullname == name or fullname.startswith(name + '.') for name in retired):
            raise AssertionError('Retired dependency loaded: ' + fullname)
sys.meta_path.insert(0, BlockRetired())
command = sys.argv[1]
sys.argv = [command, '--help']
try:
    runpy.run_path(command, run_name='__main__')
except SystemExit as error:
    assert error.code == 0, error.code
else:
    raise AssertionError('CLI did not exit after help')
assert not any('WorkBuddy/Claw/scripts' in path for path in sys.path)
print('CURRENT_ENTRY_ISOLATED')
'''
        for command in ('scripts/daily_report_current.py', 'scripts/daily_report_entry_demo.py'):
            with self.subTest(command=command):
                result = subprocess.run([sys.executable, '-c', source, command], cwd=ROOT,
                                        capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn('CURRENT_ENTRY_ISOLATED', result.stdout)

    def test_selected_replay_source_never_falls_back_or_collects(self):
        with (
            patch.object(current, 'load_data_snapshot', return_value=(None, {})) as load,
            patch.object(current, 'collect_market_reading_data') as collect,
        ):
            with self.assertRaises(ReportCriticalDataMissingError):
                current.main([DATE, '--replay', '--snapshot-source', 'replay'])
        load.assert_called_once_with(DATE, mode='replay')
        collect.assert_not_called()

    def test_small_cap_matrix_does_not_import_retired_strategy_code(self):
        source = '''
import importlib.abc
import sys
sys.path.insert(0, 'scripts')
class BlockRetired(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in ('report.market_alpha_beta', 'report.strategy_backtest'):
            raise AssertionError('Retired strategy imported: ' + fullname)
sys.meta_path.insert(0, BlockRetired())
from report.small_cap_history import history_from_artifact
import numpy as np
value = {'trade_dates': ['2026-09-28', '2026-09-29'],
         'codes': ['000001.SZ'], 'st_codes': [],
         'profile': {'names': ['sample'], 'list_dates': ['2020-01-01']},
         'prices': {'2026-09-28': '0,10,10,10,', '2026-09-29': '0,11,10,10,0'},
         'benchmark': {'rows': []}, 'artifact_hash': 'frozen-source'}
result = history_from_artifact(value)
assert np.isnan(result['amount'][0, 0])
assert result['amount'][0, 1] == 0
assert result['eligible'].all()
assert result['returns'][0, 1] == 10
assert result['inputs_sha256'] == 'frozen-source'
'''
        result = subprocess.run([sys.executable, '-c', source], cwd=ROOT,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_cffex_chart_projection_does_not_import_retired_renderer_or_wiki(self):
        source = '''
import sys
sys.path.insert(0, 'scripts')
from report.cffex_index_futures_position_evidence import normalize_cffex_position_trend_payload
from report.cffex_index_futures_position_evidence import build_unavailable_cffex_evidence
from report.sector_snapshot_charts import snapshot_chart_payload
payload = {
    'schema_version': 'cffex_index_futures_position_evidence.v1',
    'target_date': '2026-10-20', 'source_date': '2026-10-20',
    'history': {'windows': {
        'member_net_short_change': {'60': {'values': [{'trade_date': '2026-10-20', 'value': 1}]}},
        'member_net_short_notional': {'60': {'values': [{'trade_date': '2026-10-20', 'value': 100000000}]}},
        'top20_cross_section_net_short': {'60': {'values': [{'trade_date': '2026-10-20', 'value': 2}]}},
    }},
}
result = normalize_cffex_position_trend_payload(payload, '2026-10-20')
assert result['items'][0]['member_net_short_change'] == 1
evidence = build_unavailable_cffex_evidence('2026-10-20', reason='缺少冻结事实', query_date='2026-10-20')
assert snapshot_chart_payload({'cffex_index_futures_position_evidence': evidence}, '2026-10-20') == {}
evidence['target_date'] = '2026-10-19'
try:
    snapshot_chart_payload({'cffex_index_futures_position_evidence': evidence}, '2026-10-20')
except ValueError:
    pass
else:
    raise AssertionError('Invalid CFFEX date was accepted')
for module in ('report.markdown_report_html', 'report.candidate_decision_evidence',
               'report.dual_cluster_projection', 'knowledge.llm_wiki_manifest'):
    assert module not in sys.modules, module
'''
        result = subprocess.run([sys.executable, '-c', source], cwd=ROOT,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_current_chart_driver_does_not_read_the_historical_template(self):
        from report.sector_reading_content import chart_driver
        original = Path.read_text

        def read_current(path, *args, **kwargs):
            self.assertNotEqual(path.name, 'daily_report_markdown_reader.html')
            return original(path, *args, **kwargs)

        with patch.object(Path, 'read_text', read_current):
            script = chart_driver()
        self.assertIn('renderCffexPositionTrendChart', script)
        self.assertIn('drawTurnoverTop30', script)

    def test_historical_additions_only_load_present_validators_and_still_check_hashes(self):
        source = '''
import importlib.abc
import json
import sys
sys.path.insert(0, 'scripts')
class BlockRetired(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in ('report.daily_interpretation', 'report.daily_extras',
                        'report.advice_ledger', 'report.market_alpha_beta', 'report.strategy_backtest'):
            raise AssertionError('Unneeded historical validator: ' + fullname)
sys.meta_path.insert(0, BlockRetired())
from report.sector_reading_history import evidence_hash, historical_assets
from report.small_cap_rotation import SCHEMA
day = '2026-10-20'
plan = {'schema': SCHEMA, 'target_date': day}
plan['artifact_hash'] = evidence_hash(plan)
bundle = {'target_date': day, 'snapshot_hash': evidence_hash({}),
          'chart_hash': evidence_hash({}), 'assets': {}}
bundle['artifact_hash'] = evidence_hash(bundle)
html = '<script id="sector-retained-history" type="application/json">' + json.dumps(bundle) + '</script>'
assert historical_assets(html, {'data': {'reading_small_cap_plan': plan}}, day) == {}
plan['target_date'] = '2026-10-19'
try:
    historical_assets(html, {'data': {'reading_small_cap_plan': plan}}, day)
except ValueError:
    pass
else:
    raise AssertionError('Invalid small-cap addition was accepted')
try:
    historical_assets(html, {'data': {'unrecognized_fact': 1}}, day)
except ValueError:
    pass
else:
    raise AssertionError('Changed original facts were accepted')
'''
        result = subprocess.run([sys.executable, '-c', source], cwd=ROOT,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_real_current_replay_preserves_official_output_and_frozen_inputs(self):
        data = snapshot()['data']
        before = deepcopy(data)
        with TemporaryDirectory() as folder:
            root = Path(folder)
            official = root / 'reports' / f'{DATE}_A股日报_板块日报.html'
            official.parent.mkdir()
            official.write_text('protected official history')
            def paths(day, *, replay=False):
                parent = root / 'reports' / 'replay' if replay else root / 'reports'
                stem = day + '_A股日报_完整版' + ('_replay' if replay else '')
                return parent / (stem + '.md'), parent / (stem + '.html')
            with (
                patch.object(current, 'load_data_snapshot', return_value=(data, {})) as load,
                patch.object(current, '_existing_legacy_report_paths', side_effect=paths),
                patch.object(current, 'run_source_health_check', return_value={'overall_result': 'ready'}) as health,
                patch.object(current, 'build_report_run_observer', return_value=MagicMock()),
                patch.object(current, 'collect_market_reading_data', side_effect=AssertionError('No live refresh')),
                patch.object(current, '_save_data_snapshot', side_effect=AssertionError('No snapshot writes')),
                redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(current.main([DATE, '--replay']), 0)
            page = root / 'reports' / 'replay' / f'{DATE}_A股日报_板块日报_replay.html'
            self.assertTrue(page.is_file())
            self.assertEqual(official.read_text(), 'protected official history')
            self.assertEqual(data, before)
            load.assert_called_once_with(DATE, mode='frozen')
            self.assertTrue(health.call_args.kwargs['replay'])
            self.assertIn('小盘计划尚缺', page.read_text())

    def test_retired_or_conflicting_arguments_fail_before_reading(self):
        cases = ([DATE, '--output-mode', 'short'], [DATE, '--position', '空仓'],
                 [DATE, '--replay', '--force-live'], [DATE, '--snapshot-source', 'replay'])
        for args in cases:
            with (
                self.subTest(args=args), patch.object(current, 'load_data_snapshot') as load,
                redirect_stderr(io.StringIO()), self.assertRaises(SystemExit),
            ):
                current.main(args)
            load.assert_not_called()

    def test_history_is_validated_before_large_inputs_are_discarded(self):
        days, data = sample()
        choice = build_sector_choice(data, days[-1])
        data.update(reading_choice=choice, reading_small_cap_plan={'frozen': True},
                    irrelevant_large_payload='x' * 100000)
        original = {'date': days[-1], 'data': data}
        before = deepcopy(original)
        notes = []
        result = _compact_history_snapshot(original, days[-1], notes)
        self.assertEqual(result['data']['reading_choice'], choice)
        self.assertEqual(result['data']['reading_small_cap_plan'], {'frozen': True})
        self.assertNotIn('reading_sector_history', result['data'])
        self.assertNotIn('irrelevant_large_payload', result['data'])
        self.assertEqual(original, before)
        self.assertEqual(notes, [])

    def test_invalid_prior_choice_does_not_remove_independent_history(self):
        days, data = sample()
        choice = build_sector_choice(data, days[-1])
        choice['primary']['name'] = 'tampered'
        data.update(reading_choice=choice, market_stats={'up_count': 1})
        notes = []
        result = _compact_history_snapshot({'date': days[-1], 'data': data}, days[-1], notes)
        self.assertNotIn('reading_choice', result['data'])
        self.assertEqual(result['data']['market_stats'], {'up_count': 1})
        self.assertTrue(notes)
        with self.assertRaises(ValueError):
            _compact_history_snapshot({'date': 'wrong', 'data': data}, days[-1], [])
