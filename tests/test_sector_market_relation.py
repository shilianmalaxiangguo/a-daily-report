"""Market relationships are separate from within-sector relative returns."""
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import subprocess
import shutil
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from report.sector_market_relation import (
    build_member_history, validate_member_history, build_market_relation, relation_summary, collect_member_history,
)
from report.sector_reading_history import evidence_hash
from tests.test_sector_choice import sample, with_members


class SectorMarketRelationTest(unittest.TestCase):
    def fixture(self):
        days, data = sample()
        with_members(data, days)
        view = data['reading_sector_history']['trend']
        market = []
        close = 100.
        for i, day in enumerate(days):
            close *= 1 + (1 if i % 2 else -1) / 100
            market.append({'date': day, 'close': close})
        inputs = view['price_inputs']
        from report.sector_reading_sources import build_index_view
        rebuilt = build_index_view(inputs['rows'], inputs['metadata'], market, days[-1],
                                   trade_dates=days, index_type='N')
        rebuilt['member_comparison'] = view['member_comparison']
        old = {(r['code'], r['date']): r for r in view['member_comparison']['daily_rows']}
        rows = []
        for code in ('000001.SZ', '000002.SZ', '000003.SZ'):
            for i, day in enumerate(days[-21:]):
                change = old.get((code, day), {}).get('change_pct', 2. if code != '000003.SZ' else -1.)
                rows.append({'code': code, 'date': day, 'change_pct': change,
                             'close': 10 * (1 + change / 100), 'pre_close': 10., 'turnover_yi': 10.})
        return days, rebuilt, rows

    def build(self):
        days, view, rows = self.fixture()
        value = build_member_history(view, rows, trade_dates=days[-21:],
                                     retrieved_at='2026-10-28T12:00:00+08:00', provider_hosts=['example.test'])
        return days, view, rows, value

    def test_twenty_day_history_is_separate_and_old_five_day_projection_is_unchanged(self):
        days, view, rows = self.fixture()
        before = deepcopy(view)
        value = build_member_history(view, rows, trade_dates=days[-21:],
                                     retrieved_at='2026-10-28T12:00:00+08:00')
        self.assertEqual(view, before)
        validate_member_history(value, view)
        self.assertEqual(value['membership_hash'], view['member_comparison']['artifact_hash'])
        self.assertEqual(len(value['trade_dates']), 21)
        self.assertEqual(value['membership_query_date'], view['member_comparison']['query_date'])
        projection = build_market_relation(view, value)
        self.assertEqual(projection['benchmark']['code'], '000985.CSI')
        self.assertEqual(projection['default_window'], 20)
        self.assertEqual(projection['available_windows'], [5, 20])
        self.assertNotIn('daily_rows', projection)
        self.assertNotIn('close', json.dumps(projection))
        self.assertEqual(len(projection['stocks']['000001.SZ']), 21)

    def test_market_and_sector_relationships_are_not_the_same_comparison(self):
        days, view, _, history = self.build()
        projection = build_market_relation(view, history)
        stock = projection['stocks']['000001.SZ'][-20:]
        market = projection['market'][-20:]
        sector = projection['sectors']['index:886001.TI'][-20:]
        result = relation_summary(stock, market)
        relative = relation_summary(stock, sector)
        self.assertEqual(result['valid_days'], 20)
        self.assertEqual(result['same_direction_days'], 10)
        self.assertEqual(relative['same_direction_days'], 20)
        self.assertNotAlmostEqual(result['excess_pp'], relative['excess_pp'])
        self.assertEqual(result['market_up_days'] + result['market_down_days'], 20)
        self.assertNotIn('alpha', result)
        self.assertNotIn('beta', result)

    def test_missing_pair_keeps_coverage_but_not_a_complete_relationship_claim(self):
        result = relation_summary([2., None, -1.], [1., -1., -2.])
        self.assertEqual(result['valid_days'], 2)
        self.assertEqual(result['requested_days'], 3)
        self.assertIsNone(result['same_direction_days'])
        self.assertIsNone(result['stock_pct'])
        self.assertIsNone(result['excess_pp'])
        self.assertIsNone(result['market_up_stock_mean_pct'])
        self.assertEqual(result['stock_path'], [100., 102., None, None])

    def test_zero_market_days_are_not_up_down_or_same_direction(self):
        result = relation_summary([1., -1., 0.], [0., 0., 0.])
        self.assertEqual(result['same_direction_days'], 0)
        self.assertEqual(result['market_flat_days'], 3)
        self.assertIsNone(result['market_up_stock_mean_pct'])
        self.assertIsNone(result['market_down_stock_mean_pct'])

    def test_negative_absolute_return_does_not_become_independent_profit(self):
        result = relation_summary([-1.] * 20, [-2.] * 20)
        self.assertLess(result['stock_pct'], 0)
        self.assertGreater(result['excess_pp'], 0)
        self.assertEqual(result['same_direction_days'], 20)

    def test_resigned_supplement_cannot_replace_old_prices_or_members(self):
        _, view, _, value = self.build()
        bad = deepcopy(value)
        bad['daily_rows'][-1]['change_pct'] = 99.
        bad['artifact_hash'] = evidence_hash({k: v for k, v in bad.items() if k != 'artifact_hash'})
        with self.assertRaisesRegex(ValueError, '价格|冲突'):
            validate_member_history(bad, view)
        other = deepcopy(view)
        other['member_comparison']['artifact_hash'] = 'different'
        with self.assertRaisesRegex(ValueError, '成员|指纹'):
            validate_member_history(value, other)

    def test_wrong_dates_unknown_codes_duplicate_conflicts_are_rejected(self):
        days, view, rows = self.fixture()
        for extra in ({**rows[0], 'date': '2026-10-29'}, {**rows[0], 'code': '999999.SZ'},
                      {**rows[0], 'change_pct': -99., 'close': .1}):
            with self.subTest(extra=extra):
                with self.assertRaises(ValueError):
                    build_member_history(view, rows + [extra], trade_dates=days[-21:],
                                         retrieved_at='2026-10-28T12:00:00+08:00')

    def test_without_supplement_preserves_short_window_and_marks_twenty_days_unavailable(self):
        _, view, _ = self.fixture()
        before = deepcopy(view)
        result = build_market_relation(view)
        self.assertEqual(result['available_windows'], [5])
        self.assertEqual(result['default_window'], 5)
        self.assertTrue(result['short_history'])
        self.assertEqual(view, before)

    def test_collector_uses_only_requested_dates_and_preserves_old_members(self):
        days, view, rows = self.fixture()
        called = []
        def fetch(day):
            called.append(day)
            return [{'ts_code': r['code'], 'trade_date': day, 'close': r['close'], 'pre_close': r['pre_close'],
                     'amount_yi': r['turnover_yi']} for r in rows if r['date'] == day]
        before = deepcopy(view)
        result = collect_member_history(None, view, daily_fetcher=fetch)
        self.assertEqual(called, days[-21:])
        for actual, expected in zip(result['daily_rows'], sorted(rows, key=lambda r: (r['code'], r['date']))):
            self.assertEqual((actual['code'], actual['date']), (expected['code'], expected['date']))
            self.assertAlmostEqual(actual['change_pct'], expected['change_pct'])
        self.assertEqual(view, before)
        validate_member_history(result, view)

    def test_rehashed_benchmark_identity_cannot_change(self):
        _, view, _, history = self.build()
        history['benchmark']['code'] = '000001.SH'
        history['artifact_hash'] = evidence_hash({k: v for k, v in history.items() if k != 'artifact_hash'})
        with self.assertRaises(ValueError):
            validate_member_history(history, view)

    def test_renderer_separates_market_observation_and_original_sector_comparison(self):
        from bs4 import BeautifulSoup
        from report.sector_alpha import build_alpha_comparison, render_alpha_comparison
        from report.sector_choice import build_sector_choice
        days, view, _, history = self.build()
        data = {'reading_sector_history': {'trend': view}}
        choice = build_sector_choice(data, days[-1])
        result = build_alpha_comparison(view, days[-1], choice, market_history=history)
        page = render_alpha_comparison(BeautifulSoup('', 'html.parser'), result, choice)
        text = BeautifulSoup(str(page), 'html.parser').get_text()
        for phrase in ('板块共涨不等于贝塔', '跑赢板块也不等于阿尔法', '不是买入排序', '板块内部扩散'):
            self.assertIn(phrase, text)
        for phrase in (choice['regime'], '撤回增强优先', '先选板块，再问个股值不值得'):
            self.assertNotIn(phrase, text)
        self.assertIsNotNone(page.select_one('#market-relation-chart'))
        self.assertIsNotNone(page.select_one('#alpha-path-chart'))
        buttons = page.select('[data-market-window]')
        self.assertEqual([b['aria-pressed'] for b in buttons], ['false', 'true', 'false'])
        self.assertTrue(buttons[-1].has_attr('disabled'))
        projection = json.loads(page.select_one('#sector-alpha-data').string)['market_relation']
        self.assertNotIn('daily_rows', projection)
        self.assertNotIn('price_inputs', projection)

    def test_verified_history_can_be_added_to_an_existing_page_without_ignoring_other_changes(self):
        from report.sector_daily_report import render_sector_daily
        from report.sector_reading_history import historical_assets
        from report.sector_choice import build_sector_choice
        days, view, _, history = self.build()
        assets = {'target_date': days[-1], 'record_hash': None, 'trend': view}
        assets['source_sha256'] = evidence_hash(assets)
        data = {'reading_sector_history': assets}
        data['reading_choice'] = build_sector_choice(data, days[-1])
        original = {'date': days[-1], 'data': data}
        old_page = render_sector_daily(None, days[-1], snapshot=original)
        augmented = deepcopy(original)
        augmented['data']['reading_member_history'] = history
        self.assertEqual(historical_assets(old_page, augmented, days[-1]), assets)
        page = render_sector_daily(old_page, days[-1], snapshot=augmented)
        self.assertEqual(render_sector_daily(page, days[-1], snapshot=augmented), page)
        unrelated = deepcopy(augmented)
        unrelated['data']['unrelated_fact'] = {'date': days[-1], 'value': 7}
        with self.assertRaises(ValueError):
            historical_assets(old_page, unrelated, days[-1])
        changed = deepcopy(augmented)
        bad = changed['data']['reading_member_history']
        bad['daily_rows'][-1]['change_pct'] = 99
        bad['artifact_hash'] = evidence_hash({k: v for k, v in bad.items() if k != 'artifact_hash'})
        with self.assertRaises(ValueError):
            historical_assets(old_page, changed, days[-1])

    def test_sector_price_gap_does_not_remove_complete_stock_market_relationship(self):
        from bs4 import BeautifulSoup
        from report.sector_alpha import build_alpha_comparison, render_alpha_comparison
        from report.sector_choice import build_sector_choice
        from report.sector_reading_sources import build_index_view
        days, view, rows = self.fixture()
        inputs = view['price_inputs']
        missing = build_index_view([r for r in inputs['rows'] if r['trade_date'] != days[-1]],
            inputs['metadata'], inputs['market_bars'], days[-1], trade_dates=days, index_type='N')
        missing['member_comparison'] = view['member_comparison']
        history = build_member_history(missing, rows, trade_dates=days[-21:], retrieved_at='2026-10-28T12:00:00+08:00')
        choice = build_sector_choice({'reading_sector_history': {'trend': missing}}, days[-1])
        self.assertEqual(choice['daily'][-1]['valid'], 0)
        value = build_alpha_comparison(missing, days[-1], choice, market_history=history)
        relation = value['market_relation']
        self.assertIsNone(relation['sectors']['index:886001.TI'][-1])
        self.assertTrue(relation_summary(relation['stocks']['000001.SZ'][-20:], relation['market'][-20:])['complete'])
        page = render_alpha_comparison(BeautifulSoup('', 'html.parser'), value, choice)
        self.assertIsNotNone(page.select_one('#market-relation-chart'))
        text = BeautifulSoup(str(page), 'html.parser').get_text()
        self.assertIn('不抹掉已取得的个股与大盘比较', text)
        self.assertNotIn('本日0/0', text)
        from tests.test_sector_alpha import SectorAlphaTest
        selected = SectorAlphaTest().chart_driver_results(value)['initial']
        self.assertEqual(selected['stock'], '000001.SZ')

    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for relationship charts')
    def test_browser_calculation_matches_independent_python_and_clears_old_selection(self):
        from report.sector_alpha import build_alpha_comparison
        days, view, _, history = self.build()
        value = build_alpha_comparison(view, days[-1], market_history=history)
        value['selected_stock'] = '000001.SZ'
        driver = (Path(__file__).resolve().parents[1] / 'scripts/templates/sector_market_relation_charts.js').read_text()
        program = r'''
const fs=require('fs'),vm=require('vm'),input=JSON.parse(fs.readFileSync(0,'utf8'));
const node=()=>({style:{},dataset:{},children:[],handlers:{},textContent:'',setAttribute(k,v){this[k]=v;},
 append(...v){this.children.push(...v);},replaceChildren(...v){this.children=v;},addEventListener(n,f){this.handlers[n]=f;}});
const ids=['sector-alpha-data','market-relation-chart','market-relation-summary','market-relation-note','market-relation-metrics'];
const nodes=Object.fromEntries(ids.map(id=>[id,node()]));nodes['sector-alpha-data'].textContent=JSON.stringify(input.value);
const buttons=[5,20,60].map(n=>Object.assign(node(),{dataset:{marketWindow:String(n)}}));
const root=node();root.dataset={selectedSector:input.value.selected_sector,selectedStock:'000001.SZ',selectedDate:input.value.target_date};
root.querySelector=s=>nodes[s.slice(1)];root.querySelectorAll=()=>buttons;
const chart={setOption(o){this.option=o;},resize(){}};
global.window={echarts:{init:()=>chart},addEventListener(){}};
global.document={readyState:'complete',querySelector:()=>root,createElement:node,handlers:{},addEventListener(n,f){this.handlers[n]=f;}};
global.ResizeObserver=class{observe(){}};vm.runInThisContext(input.driver);
const save=()=>({series:chart.option.series?.map(s=>s.data)||[],metrics:nodes['market-relation-metrics'].children.map(n=>n.children.map(c=>c.textContent)),
 note:nodes['market-relation-note'].textContent,summary:nodes['market-relation-summary'].textContent,window:root.dataset.marketWindow});
const twenty=save();buttons[0].handlers.click();const five=save();buttons[2].handlers.click();const unavailable=save();
root.dataset.selectedDate=input.value.dates[1];document.handlers['sector-member-selection']();const historical=save();
root.dataset.selectedDate=input.value.target_date;root.dataset.selectedSector='index:999999.TI';document.handlers['sector-member-selection']();const uncovered=save();
root.dataset.selectedSector=input.value.selected_sector;document.handlers['sector-member-selection']();const restored=save();
console.log(JSON.stringify({twenty,five,unavailable,historical,uncovered,restored}));
'''
        def run(data):
            result = subprocess.run(['node', '-e', program], input=json.dumps({'value': data, 'driver': driver}),
                                    text=True, capture_output=True, check=True)
            return json.loads(result.stdout)
        actual = run(value)
        relation = value['market_relation']
        for window, key in ((20, 'twenty'), (5, 'five')):
            expected = relation_summary(relation['stocks']['000001.SZ'][-window:], relation['market'][-window:])
            self.assertEqual(actual[key]['window'], str(window))
            self.assertEqual(actual[key]['metrics'][0][1], f'{expected["same_direction_days"]} / {window}')
            for got, want in zip(actual[key]['series'][0], expected['stock_path']):
                self.assertAlmostEqual(got, want - 100)
            for got, want in zip(actual[key]['series'][2], expected['market_path']):
                self.assertAlmostEqual(got, want - 100)
        self.assertEqual(actual['five'], actual['unavailable'])
        for key in ('historical', 'uncovered'):
            self.assertEqual(actual[key]['series'], [])
            self.assertEqual(actual[key]['metrics'], [])
        self.assertEqual(actual['restored'], actual['five'])
        damaged = deepcopy(value)
        damaged['market_relation']['stocks']['000001.SZ'][-3] = None
        partial = run(damaged)['twenty']
        self.assertEqual(partial['metrics'][0][1], '未齐（有效 19/20）')
        self.assertIsNone(partial['series'][0][-1])
        self.assertIn('缺失不补零', partial['note'])
        sector_gap = deepcopy(value)
        sector_gap['market_relation']['sectors'][value['selected_sector']][-3] = None
        partial = run(sector_gap)['twenty']
        self.assertIn('三者均有效 19/20', partial['summary'])
        self.assertIsNone(partial['series'][1][-1])


if __name__ == '__main__':
    unittest.main()
