"""Sector-wide participation and stock excess must use the same actual days."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import shutil
import subprocess
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from bs4 import BeautifulSoup
from tests.test_sector_choice import sample, with_members
from report.sector_choice import build_sector_choice
from report.sector_member_comparison import build_member_comparison
from report.sector_alpha import build_alpha_comparison, render_alpha_comparison


class SectorAlphaTest(unittest.TestCase):
    def fixture(self):
        days, data = sample()
        with_members(data, days)
        choice = build_sector_choice(data, days[-1])
        return days, data, choice

    def test_same_window_paths_explain_extra_return_and_preserve_input(self):
        days, data, choice = self.fixture()
        before = deepcopy(data)
        result = build_alpha_comparison(data['reading_sector_history']['trend'], days[-1], choice)
        sector = result['sectors']['index:886001.TI']
        stock = next(r for r in sector['stocks'] if r['code'] == '000001.SZ')
        self.assertEqual(result['dates'], days[-6:])
        self.assertAlmostEqual(sector['sector_pct'], (1.01**5-1)*100)
        self.assertAlmostEqual(stock['path'][-1], (1.02**5-1)*100)
        self.assertAlmostEqual(stock['excess_pp'], stock['path'][-1]-sector['sector_pct'])
        self.assertEqual(stock['daily_excess'], [None, 1., 1., 1., 1., 1.])
        self.assertEqual(stock['outperform_days'], 5)
        self.assertEqual(stock['trailing_days'], 5)
        self.assertEqual(result['selected_stock'], choice['stock']['code'])
        self.assertEqual(data, before)

    def test_big_old_winner_has_visible_last_day_failure_and_drawdown(self):
        days, data, choice = self.fixture()
        result = build_alpha_comparison(data['reading_sector_history']['trend'], days[-1], choice)
        sector = result['sectors']['index:886001.TI']
        stock = next(r for r in sector['stocks'] if r['code'] == '000002.SZ')
        self.assertGreater(stock['excess_pp'], 0)
        self.assertEqual(stock['daily_excess'][-1], -2.)
        self.assertEqual(stock['trailing_days'], 0)
        self.assertAlmostEqual(stock['max_drawdown_pct'], -1.)
        self.assertLess(sector['median_without_top_pct'], sector['median_pct'])

    def test_proved_delisting_keeps_directory_count_and_effective_coverage_visible(self):
        days, data, choice = self.fixture()
        view = data['reading_sector_history']['trend']
        raw = view['member_comparison']
        view['member_comparison'] = build_member_comparison(days[-1], raw['trade_dates'], raw['memberships'],
            [r for r in raw['daily_rows'] if r['code'] != '000001.SZ'], retrieved_at=raw['retrieved_at'],
            listing_evidence={'source': 'tushare.stock_basic', 'retrieved_at': raw['retrieved_at'],
                'rows': [{'ts_code': '000001.SZ', 'list_status': 'D', 'list_date': '20000101', 'delist_date': '20260714'}]})
        result = build_alpha_comparison(view, days[-1])
        sector = result['sectors']['index:886001.TI']
        self.assertEqual(sector['member_count'], sector['directory_member_count'] - 1)
        self.assertEqual(sector['excluded_members'][0]['code'], '000001.SZ')
        page = render_alpha_comparison(BeautifulSoup('', 'html.parser'), result, choice)
        button = page.select_one('[data-alpha-sector="index:886001.TI"]')
        self.assertIn('原目录另含1只已摘牌', button.get_text())
        self.assertIn(f'成员 {sector["valid_count"]}/{sector["member_count"]}', button.get_text())

    def test_missing_stock_day_does_not_resume_a_cumulative_path_or_count_as_zero(self):
        days, data, choice = self.fixture()
        raw = data['reading_sector_history']['trend']['member_comparison']
        rows = [r for r in raw['daily_rows'] if not (r['code'] == '000001.SZ' and r['date'] == days[-3])]
        data['reading_sector_history']['trend']['member_comparison'] = build_member_comparison(
            days[-1], raw['trade_dates'], raw['memberships'], rows, retrieved_at=raw['retrieved_at'])
        result = build_alpha_comparison(data['reading_sector_history']['trend'], days[-1])
        sector = result['sectors']['index:886001.TI']
        stock = next(r for r in sector['stocks'] if r['code'] == '000001.SZ')
        self.assertIsNone(stock['excess_pp'])
        self.assertEqual(stock['path'][-3:], [None, None, None])
        self.assertIsNone(stock['outperform_days'])
        self.assertEqual(sector['valid_count'], 2)
        self.assertEqual(sector['member_count'], 3)

    def test_no_calendar_or_members_does_not_invent_a_relationship(self):
        days, data = sample()
        self.assertIsNone(build_alpha_comparison(data['reading_sector_history']['trend'], days[-1]))
        with_members(data, days)
        data['reading_sector_history']['trend']['calendar_verified'] = False
        self.assertIsNone(build_alpha_comparison(data['reading_sector_history']['trend'], days[-1]))

    def test_empty_collected_members_do_not_create_empty_comparison_controls(self):
        days, data = sample()
        view = data['reading_sector_history']['trend']
        view['member_comparison'] = build_member_comparison(
            days[-1], days[-6:], {}, [], retrieved_at='2026-10-27T11:00:00+08:00')
        before = deepcopy(view)
        self.assertIsNone(build_alpha_comparison(view, days[-1]))
        self.assertEqual(view, before)

    def test_report_with_missing_target_prices_uses_missing_fact_notice(self):
        from report.sector_reading_sources import build_index_view
        from report.sector_reading_history import evidence_hash
        from report.sector_daily_report import render_sector_daily
        days, data = sample()
        inputs = data['reading_sector_history']['trend']['price_inputs']
        view = build_index_view(
            [r for r in inputs['rows'] if r['trade_date'] != days[-1]],
            inputs['metadata'], inputs['market_bars'], days[-1], trade_dates=days, index_type='N')
        view['member_comparison'] = build_member_comparison(
            days[-1], days[-6:], {}, [], retrieved_at='2026-10-27T11:00:00+08:00')
        assets = data['reading_sector_history']
        assets['trend'] = view
        assets['record_hash'] = None
        assets['source_sha256'] = evidence_hash({k: v for k, v in assets.items() if k != 'source_sha256'})
        data['reading_choice'] = build_sector_choice(data, days[-1])
        before = deepcopy(data)
        html = render_sector_daily(None, days[-1], snapshot={'date': days[-1], 'data': data})
        page = BeautifulSoup(html, 'html.parser')
        notice = page.select_one('#daily-choice')
        self.assertIn(days[-1] + '的概念指数行情未取得', notice.get_text())
        for claim in ('日间强势方向更替明显', '0/0', '昨日上涨前五仅', '未找到两窗'):
            self.assertNotIn(claim, notice.get_text())
        self.assertIsNone(page.select_one('[data-alpha-chart], #alpha-sidebar-toggle'))
        self.assertEqual(data, before)

    def test_missing_concept_notice_preserves_independent_stock_market_chart(self):
        days, data, choice = self.fixture()
        value = build_alpha_comparison(data['reading_sector_history']['trend'], days[-1], choice)
        choice['daily'][-1].update(up=0, valid=0, leaders=[])
        page = render_alpha_comparison(BeautifulSoup('', 'html.parser'), value, choice)
        self.assertIn('的概念指数行情未取得', page.get_text())
        text = BeautifulSoup(str(page), 'html.parser').get_text()
        self.assertNotIn(choice['regime'], text)
        self.assertNotIn('本日0/0', text)
        self.assertIsNotNone(page.select_one('#market-relation-chart'))

    def test_positive_relative_difference_can_still_be_an_absolute_loss(self):
        from report.sector_reading_sources import build_index_view
        days, data, _ = self.fixture()
        inputs = data['reading_sector_history']['trend']['price_inputs']
        rows = []
        for identity in inputs['metadata']:
            close = 100.
            for day in days:
                close *= .98
                rows.append({'ts_code': identity, 'trade_date': day, 'close': close, 'pct_change': -2.})
        view = build_index_view(rows, inputs['metadata'], inputs['market_bars'], days[-1], trade_dates=days, index_type='N')
        members = data['reading_sector_history']['trend']['member_comparison']
        stock_rows = [{**r, 'change_pct': -1.} for r in members['daily_rows']]
        view['member_comparison'] = build_member_comparison(days[-1], members['trade_dates'], members['memberships'],
                                                          stock_rows, retrieved_at=members['retrieved_at'])
        result = build_alpha_comparison(view, days[-1])
        stock = result['sectors']['index:886001.TI']['stocks'][0]
        self.assertLess(stock['stock_pct'], 0)
        self.assertGreater(stock['excess_pp'], 0)
        self.assertEqual(stock['outperform_days'], 5)

    def test_render_uses_charts_not_member_tables_and_escapes_names(self):
        days, data, choice = self.fixture()
        result = build_alpha_comparison(data['reading_sector_history']['trend'], days[-1], choice)
        page = render_alpha_comparison(BeautifulSoup('', 'html.parser'), result, choice)
        self.assertEqual(len(page.select('[data-alpha-chart]')), 3)
        self.assertIsNone(page.select_one('table, select'))
        self.assertTrue(page.select('[data-alpha-sector]'))
        self.assertIn('最新成员', page.get_text())
        self.assertIn('不是已识别', page.get_text())
        self.assertEqual(json.loads(page.select_one('#sector-alpha-data').string), result)
        self.assertIsNone(page.find('000001.sz'))
        self.assertLess(str(page).index('id="alpha-path-chart"'), str(page).index('板块整体表现与个股相对表现可以同时存在'))

    def test_script_closing_names_remain_text_after_serialization(self):
        days, data, choice = self.fixture()
        result = build_alpha_comparison(data['reading_sector_history']['trend'], days[-1], choice)
        result['sectors']['index:886001.TI']['stocks'][0]['name'] = '</script><img src=x onerror=alert(1)>'
        fragment = render_alpha_comparison(BeautifulSoup('', 'html.parser'), result, choice)
        parsed = BeautifulSoup(str(fragment), 'html.parser')
        self.assertIsNone(parsed.img)
        self.assertEqual(json.loads(parsed.select_one('#sector-alpha-data').string), result)

    def test_member_sidebar_is_local_with_two_views_and_external_reopen_control(self):
        days, data, choice = self.fixture()
        result = build_alpha_comparison(data['reading_sector_history']['trend'], days[-1], choice)
        page = render_alpha_comparison(BeautifulSoup('', 'html.parser'), result, choice)
        sidebar = page.select_one('.alpha-comparison-grid > aside#alpha-member-sidebar')
        self.assertIsNotNone(sidebar)
        self.assertIsNotNone(sidebar.select_one('#alpha-stock-chart'))
        self.assertIsNotNone(sidebar.select_one('#alpha-stock-buttons[hidden]'))
        self.assertIsNotNone(page.select_one('.alpha-comparison-grid > article #alpha-path-chart'))
        toggle = page.select_one('#alpha-sidebar-toggle')
        self.assertEqual(toggle['aria-controls'], sidebar['id'])
        self.assertEqual(toggle['aria-expanded'], 'true')
        self.assertNotIn(sidebar, toggle.parents)
        views = sidebar.select('[data-alpha-view]')
        self.assertEqual([b['data-alpha-view'] for b in views], ['chart', 'list'])
        self.assertEqual([b['aria-pressed'] for b in views], ['true', 'false'])
        self.assertTrue(all(page.select_one('#' + b['aria-controls']) for b in views))
        self.assertEqual(json.loads(page.select_one('#sector-alpha-data').string), result)

    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for chart behavior')
    def chart_driver_results(self, value, render_widths=()):
        driver = (Path(__file__).resolve().parents[1] / 'scripts/templates/sector_alpha_charts.js').read_text()
        program = r'''
const fs=require('fs'),vm=require('vm'),input=JSON.parse(fs.readFileSync(0,'utf8'));
const realEcharts=input.renderWidths.length?require(input.vendor):null;
const nodes={},charts={},events=[];
const element=()=>({style:{},dataset:{},hidden:false,children:[],handlers:{},setAttribute(k,v){this[k]=v;},
  addEventListener(n,f){this.handlers[n]=f;},append(...v){this.children.push(...v);},
  replaceChildren(...v){if(this.children.includes(global.document?.activeElement))global.document.activeElement=null;this.children=v;},
  focus(){global.document.activeElement=this;},
  querySelectorAll(){return this.children;}});
for(const id of ['alpha-sector-chart','alpha-stock-chart','alpha-path-chart','alpha-sector-summary','alpha-stock-summary',
 'alpha-stock-buttons','alpha-risk-note','sector-alpha-data','alpha-member-sidebar','alpha-sidebar-toggle',
 'alpha-stock-chart-panel'])nodes[id]=Object.assign(element(),{id});
const views=['chart','list'].map(view=>Object.assign(element(),{dataset:{alphaView:view}}));
nodes['alpha-stock-buttons'].hidden=true;
nodes['sector-alpha-data'].textContent=JSON.stringify(input.value);
const root=element();root.querySelector=s=>nodes[s.slice(1)];root.querySelectorAll=s=>s==='[data-alpha-view]'?views:[];
const trend=element(),panel=element();
global.document={readyState:'complete',querySelector:s=>s==='.daily-alpha'?root:s==='.sector-trend'?trend:null,
 getElementById:()=>panel,createElement:element,dispatchEvent:e=>events.push(e)};
global.window={echarts:{},addEventListener(){}};global.ResizeObserver=class{observe(){}};
global.CustomEvent=class{constructor(type,options){this.type=type;this.detail=options?.detail;}};
global.echarts={init:n=>(charts[n.id]={resizes:0,resize(){this.resizes++;},setOption(o){this.option=o;},handlers:{},on(k,f){this.handlers[k]=f;}})};
vm.runInThisContext(input.driver);
const saved=()=>({identity:root.dataset.selectedSector,stock:root.dataset.selectedStock,date:root.dataset.selectedDate,
 summary:nodes['alpha-stock-summary'].textContent,note:nodes['alpha-sector-summary'].textContent,
 pathSeries:charts['alpha-path-chart'].option.series?.length||0,stockHeight:nodes['alpha-stock-chart'].style.height});
const initial=saved();
const choose=(identity,date)=>{panel.dataset={trendTrack:identity,trendDate:date};trend.handlers['trend-selection-change']();return saved();};
const historical=choose(input.value.selected_sector,input.value.dates[1]);
const uncovered=choose('index:999999.TI',input.value.target_date);
const restored=choose(input.value.selected_sector,input.value.target_date);
const button=nodes['alpha-stock-buttons'].children.find(b=>b.dataset.alphaStock==='000002.SZ');
button.focus();button.handlers.click();
const keyboard={stock:root.dataset.selectedStock,focused:document.activeElement?.dataset.alphaStock,
  pressed:nodes['alpha-stock-buttons'].children.find(b=>b.dataset.alphaStock==='000002.SZ')['aria-pressed']};
charts['alpha-stock-chart'].handlers.click({componentType:'series',data:{code:'000002.SZ'}});
const stockClick=saved();
const last=charts['alpha-path-chart'].option.series[2].data.at(-1).value;
const layout=()=>({...saved(),collapsed:root.dataset.membersCollapsed,view:root.dataset.memberView,
  expanded:nodes['alpha-sidebar-toggle']['aria-expanded'],sidebarHidden:nodes['alpha-member-sidebar'].hidden,
  listHidden:nodes['alpha-stock-buttons'].hidden,chartHidden:nodes['alpha-stock-chart-panel'].hidden,
  pathResizes:charts['alpha-path-chart'].resizes,stockResizes:charts['alpha-stock-chart'].resizes,
  pressed:views.map(b=>b['aria-pressed'])});
let memberLayouts=null;
if(views.every(b=>b.handlers.click)&&nodes['alpha-sidebar-toggle'].handlers.click){
  const before=layout();views[1].handlers.click();const list=layout();
  nodes['alpha-sidebar-toggle'].handlers.click();const collapsed=layout();
  const focusedOnToggle=document.activeElement===nodes['alpha-sidebar-toggle'];
  nodes['alpha-sidebar-toggle'].handlers.click();const reopened=layout();
  views[0].handlers.click();const chart=layout();
  memberLayouts={before,list,collapsed,reopened,chart,focusedOnToggle};
}
const memberTextColors=nodes['alpha-stock-buttons'].children.map(b=>({
  label:b['aria-label'],color:b.children.find(n=>n.className==='alpha-stock-excess')?.style.color}));
const stockTips=charts['alpha-stock-chart'].option.series[0].data.map((point,i)=>({
  code:point.code,color:point.itemStyle.color,tip:charts['alpha-stock-chart'].option.tooltip.formatter({dataIndex:i})}));
const pathOption=charts['alpha-path-chart'].option;
const comparison=pathOption.series?.[3]?.data?.map(point=>point.value)||[];
const comparisonMeta={axes:pathOption.series?.map(s=>[s.xAxisIndex,s.yAxisIndex]),axisName:pathOption.xAxis?.[0]?.name,
 labels:pathOption.yAxis?.[0]?.data,tips:pathOption.series?.[3]?.data?.map((_,i)=>pathOption.series[3].tooltip.formatter({dataIndex:i}))};
delete global.document;delete global.window;
const labelBounds=input.renderWidths.map(width=>{
 const chart=realEcharts.init(null,null,{renderer:'svg',ssr:true,width,height:660});chart.setOption(pathOption);
 const labels=chart.getZr().storage.getDisplayList().filter(el=>el.type==='tspan'&&
   (/^[+\-]?\d+\.\d{2}(?:%|个百分点)$/.test(el.style.text))).map(el=>{
    const bounds=el.getBoundingRect().clone();const transform=el.getComputedTransform();
    if(transform)bounds.applyTransform(transform);
    return {text:el.style.text,x:bounds.x,right:bounds.x+bounds.width};
   });chart.dispose();return {width,labels};
});
console.log(JSON.stringify({initial,historical,uncovered,restored,stockClick,last,keyboard,memberLayouts,memberTextColors,stockTips,comparison,comparisonMeta,labelBounds}));
'''
        vendor = Path(__file__).resolve().parents[1] / '.generated/vendor/echarts/echarts.min.js'
        output = subprocess.run(['node', '-e', program], text=True,
                                input=json.dumps({'value': value, 'driver': driver,
                                                  'renderWidths': render_widths, 'vendor': str(vendor)}),
                                capture_output=True, check=True)
        return json.loads(output.stdout)

    def test_chart_selection_clears_uncovered_dates_and_sectors_and_restores(self):
        days, data, choice = self.fixture()
        with_members(data, days, broad=False)
        choice = build_sector_choice(data, days[-1])
        value = build_alpha_comparison(data['reading_sector_history']['trend'], days[-1], choice)
        results = self.chart_driver_results(value)
        self.assertEqual(results['initial']['stock'], choice['stock']['code'])
        for key in ('historical', 'uncovered'):
            self.assertEqual(results[key]['stock'], '')
            self.assertEqual(results[key]['pathSeries'], 0)
            self.assertEqual(results[key]['stockHeight'], '210px')
        self.assertEqual(results['restored']['stock'], choice['stock']['code'])
        self.assertEqual(results['stockClick']['stock'], '000002.SZ')
        self.assertEqual(results['last'], -2.)
        selected_sector = value['sectors'][value['selected_sector']]
        selected_stock = next(row for row in selected_sector['stocks'] if row['code'] == '000002.SZ')
        self.assertEqual(len(results['comparison']), 3)
        for actual, expected in zip(results['comparison'], [selected_sector['sector_pct'],
                                                              selected_stock['excess_pp'],
                                                              selected_stock['stock_pct']]):
            self.assertAlmostEqual(actual, expected)
        self.assertEqual(results['keyboard'], {'stock': '000002.SZ', 'focused': '000002.SZ', 'pressed': 'true'})
        layouts = results['memberLayouts']
        self.assertIsNotNone(layouts)
        before = layouts['before']
        for name in ('list', 'collapsed', 'reopened', 'chart'):
            self.assertEqual({k: layouts[name][k] for k in ('identity', 'stock', 'date')},
                             {k: before[k] for k in ('identity', 'stock', 'date')})
            self.assertGreater(layouts[name]['pathResizes'], before['pathResizes'])
        self.assertEqual(layouts['list']['pressed'], ['false', 'true'])
        self.assertFalse(layouts['list']['listHidden'])
        self.assertTrue(layouts['list']['chartHidden'])
        self.assertTrue(layouts['collapsed']['sidebarHidden'])
        self.assertEqual(layouts['collapsed']['expanded'], 'false')
        self.assertTrue(layouts['focusedOnToggle'])
        self.assertFalse(layouts['reopened']['sidebarHidden'])
        self.assertEqual(layouts['reopened']['view'], 'list')
        self.assertEqual(layouts['reopened']['expanded'], 'true')
        self.assertFalse(layouts['reopened']['listHidden'])
        self.assertEqual(layouts['chart']['pressed'], ['true', 'false'])
        self.assertFalse(layouts['chart']['chartHidden'])
        self.assertTrue(layouts['chart']['listHidden'])
        self.assertGreater(layouts['chart']['stockResizes'], layouts['reopened']['stockResizes'])
        def luminance(color):
            rgb = [int(color[i:i+2], 16) / 255 for i in (1, 3, 5)]
            linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in rgb]
            return sum(a * b for a, b in zip(linear, (.2126, .7152, .0722)))
        self.assertEqual(len({row['color'] for row in results['memberTextColors']}), 2)
        for row in results['memberTextColors']:
            for background in ('#ffffff', '#f4f3f6', '#edf4fa'):
                light, dark = sorted((luminance(row['color']), luminance(background)), reverse=True)
                self.assertGreaterEqual((light + .05) / (dark + .05), 4.5, row)

    def test_same_window_chart_preserves_units_signs_missing_values_and_separate_axes(self):
        days, data, choice = self.fixture()
        value = build_alpha_comparison(data['reading_sector_history']['trend'], days[-1], choice)
        scenarios = [(-10., 5., -5.), (0., 0., 0.), (3., None, None)]
        for sector_pct, excess, stock_pct in scenarios:
            with self.subTest(sector_pct=sector_pct, excess=excess, stock_pct=stock_pct):
                scenario = deepcopy(value)
                sector = scenario['sectors'][scenario['selected_sector']]
                sector.update(sector_pct=sector_pct)
                stock = next(row for row in sector['stocks'] if row['code'] == '000002.SZ')
                stock.update(stock_pct=stock_pct, excess_pp=excess)
                result = self.chart_driver_results(scenario)
                self.assertEqual(result['comparison'], [sector_pct, excess, stock_pct])
                meta = result['comparisonMeta']
                self.assertEqual(meta['axes'], [[1, 1], [1, 1], [2, 2], [0, 0]])
                self.assertEqual(meta['labels'], ['板块收益', '个股−板块差', '个股收益'])
                self.assertIn('百分点', meta['axisName'])
                self.assertIn('%', meta['axisName'])
                if excess is None:
                    self.assertIn('未齐', meta['tips'][1])
                    self.assertNotIn('0.00', meta['tips'][1])
                else:
                    self.assertIn('个百分点', meta['tips'][1])
                self.assertIn('%', meta['tips'][0])
                self.assertIn('不代表因果归因', meta['tips'][2])

    def test_near_zero_values_render_neutral_instead_of_negative_zero(self):
        days, data, choice = self.fixture()
        value = build_alpha_comparison(data['reading_sector_history']['trend'], days[-1], choice)
        sector = value['sectors'][value['selected_sector']]
        sector.update(sector_pct=-1e-14)
        stock = next(row for row in sector['stocks'] if row['code'] == '000002.SZ')
        stock.update(stock_pct=-1e-14, excess_pp=-1e-14)
        result = self.chart_driver_results(value)
        self.assertTrue(all('-0.00' not in tip for tip in result['comparisonMeta']['tips']))
        self.assertTrue(any('0.00%' in tip for tip in result['comparisonMeta']['tips']))
        self.assertNotIn('绝对收益仍下跌', result['stockClick']['summary'])
        button = next(r for r in result['memberTextColors'] if '000002.SZ' in r['label'])
        self.assertEqual(button['color'], '#625e6b')
        chart = next(r for r in result['stockTips'] if r['code'] == '000002.SZ')
        self.assertEqual(chart['color'], '#747281')
        self.assertNotIn('绝对收益仍下跌', chart['tip'])

    def test_display_zero_boundary_preserves_real_loss_and_missing(self):
        days, data, choice = self.fixture()
        value = build_alpha_comparison(data['reading_sector_history']['trend'], days[-1], choice)
        for excess, sign, text in [(-.005, '#087a42', '-0.01'), (.005, '#b62a1b', '+0.01'),
                                   (-.0049, '#625e6b', '0.00'), (None, '#625e6b', '未齐')]:
            with self.subTest(excess=excess):
                scenario = deepcopy(value)
                sector = scenario['sectors'][scenario['selected_sector']]
                stock = next(r for r in sector['stocks'] if r['code'] == '000002.SZ')
                stock.update(excess_pp=excess, stock_pct=excess)
                result = self.chart_driver_results(scenario)
                button = next(r for r in result['memberTextColors'] if '000002.SZ' in r['label'])
                self.assertEqual(button['color'], sign)
                self.assertIn(text, button['label'])

    def test_actual_echarts_keeps_comparison_labels_with_units_inside_canvas(self):
        vendor = Path(__file__).resolve().parents[1] / '.generated/vendor/echarts/echarts.min.js'
        if not vendor.exists():
            self.skipTest('The fixed offline ECharts file is required for label bounds')
        days, data, choice = self.fixture()
        value = build_alpha_comparison(data['reading_sector_history']['trend'], days[-1], choice)
        sector = value['sectors'][value['selected_sector']]
        sector['sector_pct'] = -10.
        stock = next(row for row in sector['stocks'] if row['code'] == '000002.SZ')
        stock.update(stock_pct=-5., excess_pp=5.)
        result = self.chart_driver_results(value, render_widths=(600, 800, 926, 1406))
        for rendering in result['labelBounds']:
            with self.subTest(width=rendering['width']):
                self.assertEqual({r['text'] for r in rendering['labels']}, {'-10.00%', '+5.00个百分点', '-5.00%'})
                for label in rendering['labels']:
                    self.assertGreaterEqual(label['x'], 0, label)
                    self.assertLessEqual(label['right'], rendering['width'], label)


if __name__ == '__main__':
    unittest.main()
