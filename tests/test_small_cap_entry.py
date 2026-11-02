"""Verify the reduced entry with isolated files, no cached environment or network."""
from contextlib import redirect_stdout
from copy import deepcopy
from datetime import date, datetime, timedelta
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from report.fact_utils import evidence_hash
from report.small_cap_report import (collect, frozen_plans, refresh_indices, render, save_snapshot,
                                     selected_snapshot, write_new)
from report.small_cap_rotation import build_plan, growth_records, refresh_plan_inputs
from tests.test_small_cap_plan import calendar_through, end_with, fina, world
import daily_report_current as entry


def sample():
    day = end_with(5)
    _, market = world(day)
    plan, reason = build_plan(market, day, sessions=calendar_through(day), records=growth_records(fina(day)), chinext={})
    assert reason is None
    return day, {'reading_market_returns': market, 'reading_small_cap_plan': plan}


def old_snapshot(root, day, data, replay=False):
    path = root / ('snapshots/replay' if replay else 'snapshots') / (f'{day}_replay.json' if replay else f'{day}.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'date': day, 'data': data}))
    return path


class SmallCapEntryTest(unittest.TestCase):
    def test_offline_entry_does_not_load_research_or_retired_modules(self):
        code = 'import sys;sys.path.insert(0,"scripts");import daily_report_current;print("\\n".join(sys.modules))'
        modules = subprocess.check_output([sys.executable, '-c', code], cwd=ROOT, text=True)
        for name in ('sector_', 'decision_board', 'strategy_backtest', 'research.', 'storage.', 'observability.', 'execution_chain', 'quant_trading_system'):
            self.assertNotIn(name, modules)

    def test_selected_source_cannot_fall_back_or_consult_html(self):
        day, data = sample()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            official = old_snapshot(root, day, data)
            (root / 'reports').mkdir()
            (root / 'reports' / 'old.html').write_text('无效旧HTML')
            with patch('socket.socket', side_effect=AssertionError('离线不能联网')):
                loaded, source = selected_snapshot(root, day, 'official')
                self.assertEqual(source, official)
                self.assertEqual(loaded, data)
                with self.assertRaisesRegex(ValueError, '不存在'):
                    selected_snapshot(root, day, 'replay')

    def test_replay_does_not_rewrite_frozen_input_and_is_repeatable(self):
        day, data = sample()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            official = old_snapshot(root, day, {**data, 'retired_account': {'anything': 9}})
            before = official.read_bytes()
            with patch('socket.socket', side_effect=AssertionError('离线不能联网')), redirect_stdout(io.StringIO()):
                self.assertEqual(entry.main([day, '--replay'], root=root), 0)
                output = next((root / 'reports/replay/small-cap').glob('*.html'))
                first = output.read_bytes()
                self.assertEqual(entry.main([day, '--replay'], root=root), 0)
            self.assertEqual(official.read_bytes(), before)
            self.assertEqual(output.read_bytes(), first)
            self.assertNotIn('retired_account', first.decode())
            self.assertIn('万一免五', first.decode())
            self.assertIn('单期模拟', first.decode())

    def test_source_outputs_have_separate_names(self):
        day, data = sample()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old_snapshot(root, day, data)
            second = deepcopy(data)
            second['reading_small_cap_plan']['qualified'] += 1
            second['reading_small_cap_plan']['artifact_hash'] = evidence_hash({k: v for k, v in second['reading_small_cap_plan'].items() if k != 'artifact_hash'})
            old_snapshot(root, day, second, replay=True)
            with redirect_stdout(io.StringIO()):
                entry.main([day, '--replay'], root=root)
                entry.main([day, '--replay', '--snapshot-source', 'replay'], root=root)
            paths = list((root / 'reports/replay/small-cap').glob('*.html'))
            self.assertEqual(len(paths), 2)
            self.assertNotEqual(paths[0].read_bytes(), paths[1].read_bytes())

    def test_corrupt_plan_and_market_dates_stop(self):
        day, data = sample()
        for field in ('reading_small_cap_plan', 'reading_market_returns'):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                changed = deepcopy(data); changed[field]['target_date'] = '2026-01-01'
                old_snapshot(root, day, changed)
                with self.assertRaises(ValueError):
                    selected_snapshot(root, day, 'official')

    def test_missing_current_plan_stops_instead_of_rebuilding(self):
        day, data = sample()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data.pop('reading_small_cap_plan')
            old_snapshot(root, day, data)
            with patch.object(entry, 'collect', side_effect=AssertionError('不许重采')), self.assertRaises(ValueError):
                entry.main([day, '--replay'], root=root)

    def test_new_snapshots_and_output_cannot_replace_existing_different_content(self):
        day, data = sample()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = save_snapshot(data, day, root=root)
            self.assertEqual(selected_snapshot(root, day, 'official')[0], data)
            before = path.read_bytes()
            with self.assertRaises(ValueError):
                write_new(path, 'different')
            self.assertEqual(path.read_bytes(), before)
            value = json.loads(before); value['data']['reading_small_cap_plan']['qualified'] += 1
            path.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, '指纹'):
                selected_snapshot(root, day, 'official')

    def test_no_report_does_not_write(self):
        day, data = sample()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); old_snapshot(root, day, data)
            with redirect_stdout(io.StringIO()):
                entry.main([day, '--replay', '--no-report'], root=root)
            self.assertFalse((root / 'reports').exists())

    def test_rebuilt_history_has_explicit_read_path(self):
        day, data = sample()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); save_snapshot(data, day, root=root, historical=True)
            self.assertEqual(selected_snapshot(root, day, 'rebuilt')[0], data)
            with self.assertRaises(ValueError):
                selected_snapshot(root, day, 'official')

    def test_live_collection_bootstraps_only_small_cap_dependencies(self):
        import pandas as pd
        day, data = sample()
        market = data['reading_market_returns']
        from report.market_returns import price_rows
        calls = []
        class Provider:
            def __getattr__(self, endpoint):
                def query(**params):
                    calls.append(endpoint)
                    if endpoint == 'trade_cal':
                        start, end = date.fromisoformat(params['start_date'][:4]+'-'+params['start_date'][4:6]+'-'+params['start_date'][6:]), date.fromisoformat(params['end_date'][:4]+'-'+params['end_date'][4:6]+'-'+params['end_date'][6:])
                        return pd.DataFrame([{'cal_date': (start+timedelta(days=k)).strftime('%Y%m%d'), 'is_open': 1} for k in range((end-start).days+1)])
                    if endpoint == 'fina_indicator_vip':
                        return pd.DataFrame(fina(day)['periods'].get(params['period'], []))
                    if endpoint == 'daily':
                        stamp = params['trade_date']; iso = stamp[:4]+'-'+stamp[4:6]+'-'+stamp[6:]
                        return pd.DataFrame([{'ts_code': market['codes'][i], 'trade_date': stamp, 'close': c, 'pre_close': p, 'open': o, 'amount': a, 'pct_chg': (c/p-1)*100} for i,c,p,o,a in price_rows(market, iso)])
                    if endpoint == 'index_daily':
                        return pd.DataFrame([{'ts_code': params['ts_code'], 'trade_date': r['date'].replace('-',''), 'open': r['open'], 'close': r['close'], 'pre_close': r['pre_close']} for r in market['benchmark']['rows']])
                    if endpoint == 'stock_basic':
                        p = market['profile']; return pd.DataFrame([{'ts_code': c, 'name': p['names'][i], 'industry': p['industries'][i], 'list_date': p['list_dates'][i].replace('-','')} for i,c in enumerate(market['codes'])])
                    if endpoint == 'stock_st':
                        return pd.DataFrame([{'ts_code': c, 'trade_date': params['trade_date']} for c in market['st_codes']])
                    raise AssertionError(endpoint)
                return query
        with tempfile.TemporaryDirectory() as tmp:
            result = collect(day, root=Path(tmp), pro=Provider())
            self.assertEqual(result['reading_small_cap_plan']['picks'], data['reading_small_cap_plan']['picks'])
            self.assertEqual(set(calls), {'daily','trade_cal','fina_indicator_vip','index_daily','stock_basic','stock_st'})

    def test_retired_archive_members_match_manifest(self):
        manifest = json.loads((ROOT/'docs/archive/retired-source-manifest.json').read_text())
        path = ROOT/'docs/archive/retired-source-2026-11-02.tar.gz'
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), manifest['archive_sha256'])
        with tarfile.open(path) as archive:
            self.assertEqual(set(archive.getnames()), {r['path'] for r in manifest['files']})
            for row in manifest['files']:
                self.assertEqual(hashlib.sha256(archive.extractfile(row['path']).read()).hexdigest(), row['sha256'])


if __name__ == '__main__':
    unittest.main()

class FrozenComparisonTest(unittest.TestCase):
    def test_frozen_metrics_and_curve_dates(self):
        from report.render_small_cap_backtest_report import metric, render
        value = json.loads((ROOT/'docs/research/small-cap-v0.3/comparison-inputs.json').read_text())
        result = metric(value['backtest']['curves']['small_cap_plan'])
        self.assertAlmostEqual(result[0], 55.59, delta=.01)
        self.assertAlmostEqual(result[1], 31.75, delta=.01)
        self.assertAlmostEqual(result[2], -16.05, delta=.01)
        page = render(value)
        self.assertIn('2025-02-28', page)
        self.assertIn('2026-10-29', page)
        self.assertIn('不是用户的佣金', page)
        bad = deepcopy(value);bad['backtest']['curves']['small_cap_plan'].pop()
        with self.assertRaises(ValueError):render(bad)

    def test_local_research_archive_matches_manifest(self):
        manifest = json.loads((ROOT/'docs/archive/local-research-manifest.json').read_text())
        path = ROOT/'docs/archive/local-research-2026-11-02.tar.gz'
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), manifest['archive_sha256'])
        with tarfile.open(path) as archive:
            self.assertEqual(set(archive.getnames()), {r['path'] for r in manifest['files']})
            for row in manifest['files']:
                self.assertEqual(hashlib.sha256(archive.extractfile(row['path']).read()).hexdigest(), row['sha256'])

class AuditRegressionTest(unittest.TestCase):
    def test_index_price_conflicts_preserve_original_bytes(self):
        import pandas as pd
        for field in ('open','close','pre_close'):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                row = {'ts_code':'399006.SZ','trade_date':'20261030','open':100.,'close':110.,'pre_close':101.}
                path = root/'indices.json'; path.write_text(json.dumps({'indices':{'399006.SZ':{'rows':[row]}}}))
                before = path.read_bytes()
                class Provider:
                    def index_daily(self, **params):
                        return pd.DataFrame([{**row, field:200.}])
                with self.assertRaisesRegex(ValueError,'冲突'):
                    refresh_indices(Provider(),'2026-10-30',root)
                self.assertEqual(path.read_bytes(), before)

    def test_frozen_list_rejects_invalid_outer_fingerprint_or_version(self):
        day, data = sample()
        later = (date.fromisoformat(day)+timedelta(days=1)).isoformat()
        for change in ({'artifact_hash':'invalid'},{'schema':None}):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); path = save_snapshot(data,day,root=root)
                value = json.loads(path.read_text());value.update(change);path.write_text(json.dumps(value))
                for read in (lambda: selected_snapshot(root,day,'official'), lambda: frozen_plans(root,later,[day,later])):
                    with self.assertRaises(ValueError):read()

    def test_cold_financial_cache_matches_warm_before_new_announcements(self):
        import pandas as pd
        from report.small_cap_rotation import load_inputs
        from tests.test_small_cap_plan import COLD
        day = '2026-04-10'; days, market = world(day)
        records = {
            '20250930':[{'ts_code':c,'ann_date':'20251020','end_date':'20250930','q_sales_yoy':10.,'q_profit_yoy':10.} for c in COLD],
            '20251231':[{'ts_code':c,'ann_date':'20260420','end_date':'20251231','q_sales_yoy':-10.,'q_profit_yoy':-10.} for c in COLD],
            '20260331':[{'ts_code':c,'ann_date':'20260425','end_date':'20260331','q_sales_yoy':-10.,'q_profit_yoy':-10.} for c in COLD]}
        class Provider:
            def trade_cal(self, **params):
                start = date.fromisoformat('2024-07-01');end = date.fromisoformat('2026-05-25')
                return pd.DataFrame([{'cal_date':(start+timedelta(days=k)).strftime('%Y%m%d'),'is_open':1} for k in range((end-start).days+1)])
            def fina_indicator_vip(self, **params):
                return pd.DataFrame(records.get(params['period'],[]))
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); refresh_plan_inputs(Provider(),day,history=root)
            sessions,cold,_=load_inputs(day,history=root)
            warm=growth_records({'periods':records})
            a,why=build_plan(market,day,sessions=sessions,records=cold,chinext={})
            b,_=build_plan(market,day,sessions=sessions,records=warm,chinext={})
            self.assertIsNone(why)
            self.assertEqual(len(a['picks']),5)
            self.assertEqual(a['picks'],b['picks'])
