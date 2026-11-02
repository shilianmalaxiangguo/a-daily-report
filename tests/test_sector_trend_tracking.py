import json
import sys
import shutil
import subprocess
import unittest
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from bs4 import BeautifulSoup
from report.hypothesis_revision import build_hypothesis_revision, _hash
from report.sector_trend_tracking import (
    RULES, build_trend_evidence, collect_trend_evidence, project_trend,
    load_trend_evidence, save_trend_evidence, validate_trend_evidence, public_trend_evidence,
    project_chart_track, render_trend_fragment, price_temperature,
)
from report.sector_daily_report import save_sector_daily
from tests.test_sector_daily_report import SOURCE


def dates(count=10):
    return [(date(2026, 9, 1) + timedelta(days=i)).isoformat() for i in range(count)]


def sample(count=10):
    days = dates(count)
    record = build_hypothesis_revision([dict(name='样本板块', code='884240.TI',
        trade_date=days[-1], change_pct=1., up_count=None, stock_count=None, turnover_yi=None,
        data_source='tushare.ths_daily')], target_date=days[-1], market_change=.1)
    raw = {'calendar': [dict(exchange='SSE', cal_date=d, is_open=1) for d in days], 'daily': [],
           'market': [dict(ts_code=RULES['benchmark_code'], trade_date=d, pct_chg=.1) for d in days],
           'indices': {'884240.TI': [dict(ts_code='884240.TI', trade_date=d, pct_change=1.) for d in days]}}
    return record, raw


def evidence(record, raw, memberships=None):
    return build_trend_evidence(record, raw, memberships or {}, retrieved_at='2026-10-06T12:00:00+08:00')


class SectorTrendTest(unittest.TestCase):
    def project(self, returns, *, width=None, market=None, start=None):
        days = dates(len(returns))
        track = {'started_date': start or days[0]}
        return project_trend(track, days, dict(zip(days, returns)),
            dict(zip(days, market or [.1] * len(returns))), dict(zip(days, width or [.8] * len(returns))))

    def chart_options(self, page, actions=()):
        """Exercise the emitted JavaScript against a minimal DOM/chart adapter."""
        if not shutil.which('node'):
            self.skipTest('chart behavior checks require node')
        payload = {
            'scripts': [script.string for script in page.select('script')
                        if script.get('type') != 'application/json'],
            'view': page.select_one('#sector-trend-view').string,
            'elements': [{'id': el['id'], 'value': (el.select_one('option[selected]') or
                          el.select_one('option')).get('value', '') if el.name == 'select' else '',
                          'dataset': {key.removeprefix('data-').replace('-track', 'Track').replace('-date', 'Date'): val
                                      for key, val in el.attrs.items() if key.startswith('data-')}}
                         for el in page.select('[id]')],
            'actions': list(actions),
        }
        script = r'''
const fs=require('fs'),vm=require('vm'),input=JSON.parse(fs.readFileSync(0,'utf8'));
const charts={}, elements={}, tooltips=[];
function element(id){return {id,value:'',dataset:{},style:{},hidden:false,handlers:{},textContent:'',
  clientWidth:800,scrollLeft:0,addEventListener(name,fn){this.handlers[name]=fn;},
  replaceChildren(...children){this.children=children;}};}
for(const source of input.elements)elements[source.id]=Object.assign(element(source.id),source);
elements['sector-trend-view'].textContent=input.view;
const root=element('root');root.querySelector=selector=>elements[selector.slice(1)];
root.querySelectorAll=()=>[];root.dispatchEvent=event=>root.handlers[event.type]?.(event);
elements['.trend-fallback']=element('fallback');
const query=root.querySelector;
root.querySelector=selector=>selector==='.trend-fallback'?elements['.trend-fallback']:query(selector);
for(const el of Object.values(elements))el.parentElement=element('scroller');
global.document={readyState:'complete',documentElement:{},querySelector:()=>root,addEventListener(){}};
global.getComputedStyle=()=>({getPropertyValue:()=>''});
global.CustomEvent=class{constructor(type){this.type=type;}};
global.Option=class{constructor(text,value){this.text=text;this.value=value;}};
global.ResizeObserver=class{observe(){}};
global.echarts={init:node=>{
  const chart={option:null,handlers:{},resize(){},setOption(option){this.option=option;},
    on(name,fn){this.handlers[name]=fn;},getZr(){return {on(){}};}};
  charts[node.id]=chart;return chart;
}};
global.window={echarts:global.echarts,addEventListener(){}};
for(const source of input.scripts)vm.runInThisContext(source);
for(const action of input.actions){
  if(action.tooltip){
    const option=charts[action.tooltip].option;
    const params=option.series.map(s=>({seriesId:s.id,name:option.xAxis.data[action.index],
      axisValue:option.xAxis.data[action.index],marker:'',value:s.data[action.index]}));
    tooltips.push(option.tooltip.formatter(option.tooltip.trigger==='axis'?params:params[action.series]));
  }
  else if(action.chart)charts[action.chart].handlers.click(action.event);
  else {const el=elements[action.id];el.value=action.value;el.handlers.change({target:el});}
}
process.stdout.write(JSON.stringify({charts:Object.fromEntries(Object.entries(charts).map(([id,c])=>[id,c.option])),
  tooltips,matrixStyle:elements['sector-trend-revisions'].style,
  selection:elements['sector-trend-selector'].value,date:elements['trend-date-selector'].value,
  panelHidden:elements['trend-fact-panel'].hidden,note:elements['trend-heat-note'].textContent,
  memberHTML:elements['trend-member-content']?.innerHTML,
  group:elements['sector-trend-group'].value}));
'''
        result = subprocess.run(['node', '-e', script], input=json.dumps(payload), text=True,
                                capture_output=True, check=True)
        return json.loads(result.stdout)

    def focus_context(self, value, name='文化传媒'):
        source = deepcopy(value['tracks'][0])
        source.update(track_id='focus:tushare.ths_daily:881164.TI', name=name,
                      method='同代码板块指数', started_date=value['target_date'])
        return {'target_date': value['target_date'], 'source_hash': 'dated-context-hash',
                'current': {'date': value['target_date'], 'primary_mainline': name},
                'stage_mainline': {}, 'focus_track': source,
                'trade_dates': [r['date'] for r in source['path']]}

    def test_focus_is_separate_from_twenty_observations_and_540_fact_rows(self):
        record, raw = sample(27)
        facts = [dict(record['facts'][0], name=f'观察{i}', code=f'{884240+i}.TI') for i in range(20)]
        previous = None
        for offset in range(0, 20, 3):
            day = dates(27)[offset // 3]
            previous = build_hypothesis_revision(
                [dict(f, trade_date=day) for f in facts[offset:offset + 3]],
                target_date=day, previous_record=previous)
        record = build_hypothesis_revision(facts, target_date=record['target_date'], previous_record=previous)
        for fact in facts:
            raw['indices'][fact['code']] = [dict(r, ts_code=fact['code']) for r in raw['indices']['884240.TI']]
        value = evidence(record, raw)
        context = self.focus_context(value)
        original, original_context = deepcopy(value), deepcopy(context)
        page = BeautifulSoup(render_trend_fragment(value, record, display_context=context), 'html.parser')
        view = json.loads(page.select_one('#sector-trend-view').string)
        self.assertEqual(len(view['tracks']), 20)
        self.assertEqual(len(page.select('#trend-full-facts tr[data-trend-date]')), 540)
        self.assertEqual(len(page.select('.trend-roster tbody tr')), 20)
        self.assertEqual(view['artifact_hash'], value['artifact_hash'])
        self.assertEqual(view['selected_track_id'], context['focus_track']['track_id'])
        self.assertEqual(page.select_one('#sector-trend-group option[selected]')['value'], '同代码板块指数')
        self.assertEqual(value, original)
        self.assertEqual(context, original_context)
        charts = self.chart_options(page)
        self.assertEqual(len(charts['charts']['sector-trend-revisions']['series'][0]['data']), 540)
        price = charts['charts']['sector-trend-price']['series'][0]
        self.assertEqual(price['name'], '文化传媒')
        self.assertEqual(price['data'], [r['level'] for r in context['focus_track']['path']])

    def test_comparison_tooltip_keeps_only_hovered_sector_and_escapes_name(self):
        record, raw = sample()
        facts = [record['facts'][0], dict(record['facts'][0], name='<i>另一板块</i>', code='884241.TI', change_pct=2.)]
        record = build_hypothesis_revision(facts, target_date=record['target_date'])
        raw['indices']['884241.TI'] = [dict(row, ts_code='884241.TI', pct_change=2.)
                                     for row in raw['indices']['884240.TI']]
        value = evidence(record, raw)
        page = BeautifulSoup(render_trend_fragment(value, record), 'html.parser')
        for index, track in enumerate(value['tracks']):
            with self.subTest(sector=track['name']):
                result = self.chart_options(page, [{'tooltip': 'sector-trend-comparison',
                                                   'series': index, 'index': 5}])
                tip = BeautifulSoup(result['tooltips'][0], 'html.parser')
                text = tip.get_text(' ')
                self.assertIn(track['name'], text)
                self.assertNotIn(value['tracks'][1 - index]['name'], text)
                self.assertIn(track['path'][5]['date'], text)
                self.assertIn(f"{track['path'][5]['excess_pp']:.2f}个百分点", text)
                self.assertIsNone(tip.find('i'))

    def test_missing_named_focus_never_selects_another_sector_implicitly(self):
        record, raw = sample()
        value = evidence(record, raw)
        context = self.focus_context(value)
        del context['focus_track']
        page = BeautifulSoup(render_trend_fragment(value, record, display_context=context), 'html.parser')
        self.assertEqual(page.select_one('#sector-trend-selector option[selected]')['value'], '')
        self.assertTrue(page.select_one('#trend-fact-panel').has_attr('hidden'))
        self.assertIn('文化传媒', page.select_one('#trend-focus-note').text)
        initial = self.chart_options(page)
        self.assertEqual(initial['charts']['sector-trend-comparison']['series'], [])
        self.assertNotIn('series', initial['charts']['sector-trend-price'])
        track = value['tracks'][0]
        selected = self.chart_options(page, [{'id': 'sector-trend-selector', 'value': track['track_id']}])
        self.assertEqual(selected['selection'], track['track_id'])
        self.assertFalse(selected['panelHidden'])
        self.assertEqual(selected['charts']['sector-trend-price']['series'][0]['name'], track['name'])

    def test_focus_exact_name_match_and_explicit_override(self):
        record, raw = sample()
        value = evidence(record, raw)
        track = value['tracks'][0]
        context = self.focus_context(value, track['name'])
        del context['focus_track']
        page = BeautifulSoup(render_trend_fragment(value, record, display_context=context), 'html.parser')
        self.assertEqual(page.select_one('#sector-trend-selector option[selected]')['value'], track['track_id'])
        context['current']['primary_mainline'] = track['name'] + '概念'
        unmatched = BeautifulSoup(render_trend_fragment(value, record, display_context=context), 'html.parser')
        self.assertEqual(unmatched.select_one('#sector-trend-selector option[selected]')['value'], '')
        explicit = BeautifulSoup(render_trend_fragment(value, record, display_context=context,
                                  selected_track_id=track['track_id']), 'html.parser')
        self.assertEqual(explicit.select_one('#sector-trend-selector option[selected]')['value'], track['track_id'])

    def test_daily_grid_retains_real_returns_across_five_day_gaps_and_zero(self):
        record, raw = sample()
        raw['indices']['884240.TI'].pop(7)
        raw['indices']['884240.TI'][-2]['pct_change'] = 0
        value = evidence(record, raw)
        page = BeautifulSoup(render_trend_fragment(value, record), 'html.parser')
        view = json.loads(page.select_one('#sector-trend-view').string)
        self.assertIsNone(view['tracks'][0]['path'][8]['five_day_pct'])
        self.assertEqual(view['tracks'][0]['path'][8]['temperature'], 0)
        self.assertEqual(view['tracks'][0]['path'][9]['temperature'], 2)
        self.assertEqual(view['target_gaps']['known_count'], 1)
        options = self.chart_options(page)
        cells = options['charts']['sector-trend-revisions']['series'][0]['data']
        self.assertEqual([cell[2] for cell in cells[7:]], [-4, 0, 2])
        pieces = options['charts']['sector-trend-revisions']['visualMap']['pieces']
        self.assertEqual(len({p['color'] for p in pieces}), 8)
        self.assertEqual({p['value'] for p in pieces}, set(range(-4, 4)))
        self.assertEqual({p['value']: p['color'] for p in pieces}, {
            -4: '#B9BAC8', -3: '#07C160', -2: '#6BD9A2', -1: '#B5EDCF',
            0: '#F7F7F8', 1: '#F8C9C3', 2: '#F19A8D', 3: '#E73922'})
        self.assertIn('红色为上涨、绿色为下跌', page.get_text())
        target = options['charts']['sector-trend-revisions']['xAxis'][0]['axisLabel']['rich']['target']
        self.assertEqual(target['color'], options['charts']['sector-trend-price']['textStyle']['color'])
        for key in ('comparison', 'price', 'drawdown', 'breadth'):
            chart = options['charts']['sector-trend-' + key]
            self.assertEqual(chart['backgroundColor'], 'transparent')
            self.assertIn('Avenir Next', chart['textStyle']['fontFamily'])
            self.assertEqual(chart['tooltip']['textStyle']['fontSize'], 12)
            self.assertEqual(chart['legend']['left'], 'center')
            self.assertEqual(chart['legend']['textStyle']['fontSize'], 11)
            self.assertTrue(chart['legend']['selectedMode'])
            self.assertEqual(chart['yAxis']['splitLine']['lineStyle']['type'], 'dashed')
            if key == 'price':
                self.assertNotIn('dataZoom', chart)
            else:
                self.assertEqual([zoom['type'] for zoom in chart['dataZoom']], ['inside', 'slider'])
            for series in options['charts']['sector-trend-' + key]['series']:
                if series['type'] == 'line':
                    self.assertTrue(series['smooth'])
                    self.assertFalse(series['connectNulls'])
                    self.assertEqual(series['lineStyle']['width'], 2.2)
        self.assertIsNone(options['charts']['sector-trend-price']['series'][0]['data'][7])
        self.assertEqual(options['charts']['sector-trend-price']['series'][0]['data'],
                         [r['level'] for r in value['tracks'][0]['path']])
        drawdown = options['charts']['sector-trend-drawdown']['series'][0]
        self.assertEqual(drawdown['itemStyle']['color'], '#07C160')
        self.assertEqual(drawdown['data'], [r['drawdown_pct'] for r in view['tracks'][0]['path']])
        breadth, average = options['charts']['sector-trend-breadth']['series']
        self.assertEqual(breadth['itemStyle']['color'], '#E73922')
        self.assertEqual(average['itemStyle']['color'], '#2364AA')
        self.assertEqual(average['lineStyle']['type'], 'dashed')
        price, benchmark = options['charts']['sector-trend-price']['series'][:2]
        self.assertNotEqual(price['itemStyle']['color'], benchmark['itemStyle']['color'])
        self.assertEqual(benchmark['lineStyle']['type'], 'dashed')
        clicked = self.chart_options(page, [{'chart': 'sector-trend-revisions',
                                   'event': {'componentType': 'series', 'value': cells[7]}}])
        self.assertEqual(clicked['date'], dates()[7])

    def test_target_gap_summary_lists_only_missing_daily_values(self):
        record, raw = sample()
        raw['indices']['884240.TI'].pop()
        value = evidence(record, raw)
        page = BeautifulSoup(render_trend_fragment(value, record), 'html.parser')
        view = json.loads(page.select_one('#sector-trend-view').string)
        self.assertEqual(view['target_gaps']['known_count'], 0)
        self.assertEqual(view['target_gaps']['missing_count'], 1)
        self.assertEqual(view['target_gaps']['missing'][0]['name'], value['tracks'][0]['name'])
        self.assertTrue(page.select_one('.trend-gap-summary + details li').text)

    def test_series_identity_color_survives_manual_selection(self):
        record, raw = sample()
        value = evidence(record, raw)
        context = self.focus_context(value)
        page = BeautifulSoup(render_trend_fragment(value, record, display_context=context), 'html.parser')
        initial = self.chart_options(page)
        other = self.chart_options(page, [{'id': 'sector-trend-selector', 'value': value['tracks'][0]['track_id']}])
        restored = self.chart_options(page, [
            {'id': 'sector-trend-selector', 'value': value['tracks'][0]['track_id']},
            {'id': 'sector-trend-selector', 'value': context['focus_track']['track_id']}])
        self.assertEqual(initial['charts']['sector-trend-price']['series'][0]['itemStyle'],
                         restored['charts']['sector-trend-price']['series'][0]['itemStyle'])
        self.assertEqual(other['group'], value['tracks'][0]['method'])
        self.assertEqual(restored['group'], context['focus_track']['method'])

    def test_empty_context_prefers_latest_valid_observation_not_first_roster_item(self):
        record, raw = sample()
        first = dict(record['facts'][0], name='全国地产')
        second = dict(first, name='较新有效观察', code='884241.TI')
        raw['indices'][second['code']] = [dict(r, ts_code=second['code']) for r in raw['indices']['884240.TI']]
        raw['indices']['884240.TI'].pop()
        record = build_hypothesis_revision([first, second], target_date=record['target_date'])
        value = evidence(record, raw)
        page = BeautifulSoup(render_trend_fragment(value, record, display_context={}), 'html.parser')
        self.assertEqual(page.select_one('#sector-trend-selector option[selected]').text, second['name'])
        self.assertEqual(len(page.select('#trend-full-facts tr[data-trend-date]')), 20)
        self.assertEqual(json.loads(page.select_one('#sector-trend-view').string)['target_gaps']['missing_count'], 1)

    def test_one_down_day_does_not_erase_multi_day_upward_path(self):
        rows = self.project([1] * 8 + [-.5])
        self.assertEqual(rows[-1]['judgement'], '上行中分歧')
        self.assertGreater(rows[-1]['five_day_pct'], 0)
        self.assertAlmostEqual(rows[-1]['drawdown_pct'], -.5)

    def test_one_rebound_does_not_relabel_a_declining_path(self):
        rows = self.project([-2] * 8 + [1])
        self.assertEqual(rows[-1]['judgement'], '连续走弱')
        self.assertLess(rows[-1]['five_day_pct'], 0)

    def test_breadth_narrowing_is_distinct_from_price_continuation(self):
        rows = self.project([1] * 9, width=[.9]*8+[.6])
        self.assertTrue(rows[-1]['narrowing'])
        self.assertEqual(rows[-1]['judgement'], '上行中分歧')
        self.assertAlmostEqual(rows[-1]['five_day_breadth'], .84)

    def test_cumulative_and_excess_compound_separately_and_ignore_anchor_day_return(self):
        rows = self.project([99, 10, -10], market=[99, 5, -5])
        self.assertEqual(rows[0]['level'], 100)
        self.assertAlmostEqual(rows[-1]['cumulative_pct'], -1)
        self.assertAlmostEqual(rows[-1]['excess_pp'], -.75)
        self.assertAlmostEqual(rows[-1]['drawdown_pct'], -10)

    def test_missing_day_breaks_cumulative_without_turning_into_zero(self):
        rows = self.project([1, 1, None] + [1]*8)
        self.assertIsNone(rows[2]['level'])
        self.assertIsNone(rows[-1]['cumulative_pct'])
        self.assertGreater(rows[-1]['five_day_pct'], 0)

    def test_future_append_cannot_rewrite_any_previous_revision(self):
        prefix = self.project([1]*8+[-2])
        extended = self.project([1]*8+[-2, 3, -4])
        self.assertEqual(prefix, extended[:len(prefix)])

    def chart(self, returns, *, width=None, market=None, start=None):
        return project_chart_track({'track_id': 'sample', 'name': '样本',
            'started_date': start or dates()[0], 'method': '固定成员每日等权研究组合',
            'path': self.project(returns, width=width, market=market, start=start)})['path']

    def test_pullback_and_recovery_are_dated_on_observation_without_repainting(self):
        returns = [1] * 8 + [-.5, .8, 4]
        width = [.8] * 8 + [.4, .7, .9]
        prefix = self.chart(returns[:9], width=width[:9])
        full = self.chart(returns, width=width)
        self.assertEqual(prefix, full[:9])
        self.assertEqual(full[8]['marker'], '回踩观察')
        self.assertEqual(full[9]['marker'], '价格与扩散恢复')
        self.assertEqual(full[10]['marker'], '')
        self.assertEqual(full[8]['date'], dates(11)[8])

    def test_price_repair_without_breadth_does_not_claim_diffusion(self):
        rows = self.chart([1]*8 + [-.5, .8], width=[None]*10)
        self.assertEqual(rows[-1]['marker'], '仅价格修复')
        self.assertIsNone(rows[-1]['breadth'])

    def test_missing_path_or_lost_advantage_ends_pullback_observation(self):
        for returns in ([1]*8+[-.5,None,.8], [1]*8+[-.5,-20,.8]):
            rows=self.chart(returns)
            self.assertEqual(rows[-1]['marker'], '')
        self.assertIsNone(self.chart([1]*8+[-.5,None,.8])[-1]['level'])

    def test_rebound_in_weak_trend_is_not_a_pullback_entry(self):
        rows=self.chart([-1]*8+[.5,1])
        self.assertTrue(all(not r['marker'] for r in rows))
        self.assertEqual(rows[-1]['strong_streak'], 0)

    def test_narrowing_during_price_repair_does_not_claim_diffusion(self):
        rows=self.chart([1]*8+[-.5,.8],width=[.8]*8+[.7,.6])
        self.assertEqual(rows[-1]['marker'], '')
        self.assertEqual(rows[-1]['phase'], 2)

    def test_chart_projection_keeps_sources_and_escapes_embedded_labels(self):
        record, raw = sample()
        value = evidence(record, raw)
        original = deepcopy(value)
        fragment = BeautifulSoup(render_trend_fragment(value, record),'html.parser')
        self.assertEqual(value, original)
        self.assertEqual(len(fragment.select('.trend-echart')),5)
        self.assertEqual(len(fragment.select('.trend-detail-cards article')),3)
        self.assertIsNone(fragment.select_one('#sector-trend-detail'))
        self.assertFalse(fragment.select('svg.trend-chart'))
        self.assertFalse(fragment.select_one('.trend-summary').find_parent('details').has_attr('open'))
        view=json.loads(fragment.select_one('#sector-trend-view').string)
        self.assertEqual(view['version'],'trend_chart_review.v2')
        self.assertEqual(fragment.select_one('.trend-roster tbody tr').select('td')[2].text,'新出现·待续证')
        self.assertEqual(view['artifact_hash'],value['artifact_hash'])
        self.assertEqual(view['tracks'][0]['path'],project_chart_track(value['tracks'][0])['path'])
        hostile='板块</script><img src=x onerror=alert(1)>'
        record['facts'][0]['name']=hostile
        record=build_hypothesis_revision(record['facts'],target_date=record['target_date'])
        value=evidence(record,raw)
        fragment=BeautifulSoup(render_trend_fragment(value,record),'html.parser')
        self.assertFalse(fragment.select('img'))
        self.assertEqual(json.loads(fragment.select_one('#sector-trend-view').string)['tracks'][0]['name'],hostile)

    def test_fact_selection_reads_exact_dated_node_without_mutating_payload(self):
        record, raw = sample()
        second = dict(record['facts'][0], name='另一板块', code='884241.TI')
        record = build_hypothesis_revision(record['facts'] + [second], target_date=record['target_date'])
        raw['indices'][second['code']] = [dict(r, ts_code=second['code']) for r in raw['indices']['884240.TI']]
        value = evidence(record, raw)
        original = deepcopy(value)
        for source in value['tracks']:
            for row in (source['path'][0], source['path'][6], source['path'][-1]):
                with self.subTest(track=source['track_id'], day=row['date']):
                    page = BeautifulSoup(render_trend_fragment(value, record,
                        selected_track_id=source['track_id'], selected_date=row['date']), 'html.parser')
                    panel = page.select_one('#trend-fact-panel')
                    self.assertEqual(panel['data-trend-track'], source['track_id'])
                    self.assertEqual(panel['data-trend-date'], row['date'])
                    self.assertEqual(page.select_one('#sector-trend-selector option[selected]')['value'], source['track_id'])
                    self.assertEqual(page.select_one('#trend-date-selector option[selected]')['value'], row['date'])
                    self.assertEqual(page.select_one('#trend-fact-before').text, row['before'])
                    self.assertEqual(page.select_one('#trend-fact-judgement').text, row['judgement'])
                    self.assertEqual(page.select_one('#trend-fact-change_pct').text, f'{row["change_pct"]:+.2f}%')
        self.assertEqual(value, original)

    def test_complete_facts_keep_all_dates_and_separate_metric_cells(self):
        record, raw = sample()
        value = evidence(record, raw)
        page = BeautifulSoup(render_trend_fragment(value, record), 'html.parser')
        archive = page.select_one('#trend-full-facts')
        self.assertFalse(archive.has_attr('open'))
        self.assertIsNotNone(archive.select_one('.trend-roster'))
        rows = archive.select('.trend-summary tbody tr')
        self.assertEqual(len(rows), sum(len(t['path']) for t in value['tracks']))
        source = value['tracks'][0]
        self.assertEqual([r['data-trend-date'] for r in rows], [r['date'] for r in source['path']])
        for rendered, frozen in zip(rows, source['path']):
            cells = rendered.select('td')
            self.assertEqual([c.text for c in cells[-4:]],
                             [frozen[k] for k in ('before', 'judgement', 'reason', 'next_test')])
            for cell in rendered.select('[data-trend-metric]'):
                key = cell['data-trend-metric']
                if key == 'since_observation_pct' and frozen['background']:
                    expected = '不适用（历史背景）'
                elif frozen[key] is None:
                    expected = '事实不足'
                elif key in ('breadth', 'five_day_breadth'):
                    expected = f'{frozen[key] * 100:.1f}%'
                else:
                    unit = '个百分点' if key in ('excess_pp', 'five_day_excess_pp') else '%'
                    expected = f'{frozen[key]:+.2f}{unit}'
                self.assertEqual(cell.text, expected)

    def test_selected_background_does_not_become_prior_confirmation(self):
        record, raw = sample()
        value = evidence(record, raw)
        source = value['tracks'][0]
        page = BeautifulSoup(render_trend_fragment(value, record,
            selected_date=source['path'][-2]['date']), 'html.parser')
        self.assertIn('观察前历史背景', page.select_one('#trend-fact-scope').text)
        self.assertIn('不计观察后的续证', page.select_one('#trend-fact-scope').text)
        self.assertTrue(page.select_one('#trend-fact-judgement').text.startswith('历史背景：'))
        first = BeautifulSoup(render_trend_fragment(value, record,
            selected_date=source['started_date']), 'html.parser')
        self.assertIn('不能算作已验证一次', first.select_one('#trend-fact-scope').text)
        self.assertTrue(first.select_one('#trend-fact-before').text.startswith('历史背景：'))
        self.assertIn('不是上方原单日预期', first.get_text())

    def test_missing_selected_facts_remain_insufficient_instead_of_zero(self):
        record, raw = sample()
        raw['indices']['884240.TI'].pop(7)
        value = evidence(record, raw)
        page = BeautifulSoup(render_trend_fragment(value, record,
            selected_date=dates()[7]), 'html.parser')
        for key in ('change_pct', 'five_day_pct', 'five_day_excess_pp', 'drawdown_pct', 'breadth', 'five_day_breadth'):
            self.assertEqual(page.select_one('#trend-fact-' + key).text, '事实不足')
        self.assertIn('缺本日或完整5日比较', page.select_one('#trend-fact-reason').text)
        self.assertEqual(page.select_one('#trend-fact-panel')['data-trend-date'], dates()[7])

    def test_temperature_is_signed_return_with_explicit_missing_and_boundaries(self):
        values=[None,-4,-3,-2,-1,-.01,0,.01,.99,1,2.99,3,4]
        self.assertEqual([price_temperature(v) for v in values],
                         [None,-3,-3,-2,-2,-1,0,1,1,2,2,3,3])

    def test_early_followups_do_not_count_background_as_prior_confirmation(self):
        rows=self.chart([1]*11,start=dates()[8])
        self.assertEqual(rows[7]['progress'],'观察前背景')
        self.assertEqual(rows[8]['progress'],'首次出现')
        self.assertEqual(rows[8]['early_run'],0)
        self.assertEqual(rows[9]['progress'],'再次走强')
        self.assertEqual(rows[10]['progress'],'延续增强')
        self.assertEqual(rows[10]['followup_days'],2)

    def test_early_rebound_does_not_hide_weak_longer_path(self):
        rows=self.chart([-2]*8+[.6,.8],start=dates()[7])
        self.assertNotEqual(rows[-1]['progress'],'延续增强')
        self.assertIn('长段承压',rows[-1]['progress'])
        self.assertEqual(rows[-1]['role'],'走弱')

    def test_mainline_candidate_requires_followup_time_and_preserves_breadth_gap(self):
        rows=self.chart([1]*20,start=dates()[8])
        self.assertEqual(rows[8]['role'],'新出现·待续证')
        self.assertEqual(rows[17]['role'],'轮动观察')
        self.assertEqual(rows[18]['role'],'主线候选')
        self.assertEqual(self.chart([1]*20,start=dates()[8],width=[None]*20)[-1]['role'],
                         '主线候选·扩散待确认')
        self.assertEqual(self.chart([1]*20,start=dates()[8],width=[.4]*20)[-1]['role'],
                         '主线候选·扩散待确认')
        self.assertNotIn('主线候选',self.chart([1]*19+[-20])[-1]['role'])

    def test_short_term_price_strength_preserves_breadth_counterevidence(self):
        rows=self.chart([1]*10,width=[.9]*9+[.6],start=dates()[8])
        self.assertEqual(rows[-1]['progress'],'价格续强·扩散收窄')

    def test_missing_day_resets_early_followup_sequence(self):
        rows=self.chart([1]*8+[None,1],start=dates()[6])
        self.assertEqual(rows[8]['progress'],'缺证暂停')
        self.assertEqual(rows[8]['early_run'],0)
        self.assertEqual(rows[-1]['early_run'],1)

    def test_new_hot_sectors_join_without_removing_earlier_observations(self):
        record,raw=sample(10)
        old=evidence(record,raw)
        day=dates(11)[-1]
        fresh=[dict(record['facts'][0],name=f'新板块{i}',code=f'{884300+i}.TI',trade_date=day)
               for i in range(3)]
        updated=build_hypothesis_revision(fresh,target_date=day,previous_record=record,market_change=.1)
        self.assertEqual(len(updated['tracks']),4)
        new_raw=deepcopy(raw)
        new_raw['calendar'].append(dict(exchange='SSE',cal_date=day,is_open=1))
        new_raw['market'].append(dict(ts_code=RULES['benchmark_code'],trade_date=day,pct_chg=.1))
        new_raw['indices']['884240.TI'].append(dict(ts_code='884240.TI',trade_date=day,pct_change=1.))
        for row in fresh:
            new_raw['indices'][row['code']]=[dict(ts_code=row['code'],trade_date=d,pct_change=1.) for d in dates(11)]
        value=evidence(updated,new_raw)
        fragment=BeautifulSoup(render_trend_fragment(value,updated),'html.parser')
        self.assertEqual(len(fragment.select('.trend-roster tbody tr')),4)
        self.assertEqual(value['tracks'][0]['path'][:-1],old['tracks'][0]['path'])
        self.assertEqual(project_chart_track(value['tracks'][1])['path'][-1]['progress'],'首次出现')
        self.assertTrue(all(r['progress']=='观察前背景' for r in project_chart_track(value['tracks'][1])['path'][:-1]))

    def test_background_is_not_a_prior_forecast_or_longer_observation(self):
        rows = self.project([1]*10, start=dates(10)[-2])
        self.assertTrue(rows[0]['background'])
        self.assertFalse(rows[-2]['background'])
        self.assertEqual(rows[-2]['since_observation_pct'], 0)
        self.assertTrue(rows[-1]['judgement'].startswith('观察后1日：'))
        self.assertIn('不确认新趋势', rows[-1]['reason'])

    def test_validation_rejects_future_wrong_identity_duplicates_calendar_gaps_and_changed_rules(self):
        record, raw = sample()
        for mutation in ('future', 'code', 'duplicate', 'calendar', 'nan'):
            changed = deepcopy(raw)
            row = changed['indices']['884240.TI'][-1]
            if mutation == 'future': row['trade_date'] = '2026-10-08'
            if mutation == 'code': row['ts_code'] = '999999.TI'
            if mutation == 'duplicate': changed['indices']['884240.TI'].append(dict(row))
            if mutation == 'calendar': changed['calendar'].pop(2)
            if mutation == 'nan': row['pct_change'] = float('nan')
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                evidence(record, changed)
        value = evidence(record, raw)
        value['rules']['comparison_intervals'] = 1
        value['artifact_hash'] = _hash({k:v for k,v in value.items() if k!='artifact_hash'})
        self.assertFalse(validate_trend_evidence(value, record))

    def test_industry_uses_equal_weight_and_missing_member_is_not_zero(self):
        record, raw = sample()
        day = record['target_date']
        row = dict(name='地产', code='', trade_date=day, change_pct=2.5,
                   up_count=2, stock_count=2, turnover_yi=4., data_source='tushare.daily.industry_aggregate')
        record = build_hypothesis_revision([row], target_date=day)
        reference = [dict(ts_code=c, trade_date=day, pct_chg=r, amount=a)
                     for c,r,a in [('000002.SZ',1.,100000),('600048.SH',3.,300000)]]
        membership = {'codes':[r['ts_code'] for r in reference], 'reference_rows':reference}
        raw['daily'] = [{**r,'trade_date':d} for d in dates() for r in reference]
        result = evidence(record, raw, {record['tracks'][0]['track_id']:membership})
        self.assertEqual(result['tracks'][0]['path'][-1]['change_pct'],2.)
        self.assertAlmostEqual(result['tracks'][0]['path'][-1]['cumulative_pct'],(1.02**9-1)*100)
        raw['daily'].pop()
        result = evidence(record, raw, {record['tracks'][0]['track_id']:membership})
        self.assertIsNone(result['tracks'][0]['path'][-1]['change_pct'])

    def test_storage_is_immutable_and_replay_does_not_read_official(self):
        record, raw = sample()
        value = evidence(record,raw)
        with TemporaryDirectory() as folder:
            path = save_trend_evidence(value,record,ledger_root=folder)
            before = path.read_bytes()
            save_trend_evidence(value,record,ledger_root=folder)
            raw['indices']['884240.TI'][0]['pct_change']=2.
            with self.assertRaises(ValueError):
                save_trend_evidence(evidence(record,raw),record,ledger_root=folder)
            self.assertEqual(before,path.read_bytes())
            self.assertIsNone(load_trend_evidence(record,ledger_root=Path(folder)/'replay'))

    def test_later_collection_reuses_frozen_history_and_old_revisions(self):
        previous_record, previous_raw = sample(9)
        previous = evidence(previous_record,previous_raw)
        day = dates()[-1]
        seed = dict(previous_record['facts'][0], trade_date=day)
        current = build_hypothesis_revision([seed],target_date=day,previous_record=previous_record,market_change=.1)
        _, raw = sample()
        def fetch(api,start,end,code=None):
            if api=='trade_cal':return raw['calendar']
            self.assertEqual(start,day)
            if api=='index_daily':return raw['market'][-1:]
            if api=='ths_daily':return raw['indices'][code][-1:]
            self.fail('无行业不应查询个股')
        result=collect_trend_evidence(current,[],previous=previous,fetcher=fetch)
        self.assertEqual(result['tracks'][0]['path'][:-1],previous['tracks'][0]['path'])

    def test_current_page_can_read_explicit_historical_prices_without_old_actions(self):
        record, raw=sample()
        day=record['target_date']
        source=SOURCE.replace('2026-09-29',day)
        snapshot={'date':day,'data':{'sector_change_up':record['facts'],
                                   'wind_a_alternative':{'trade_date':day,'change_pct':.1}}}
        with TemporaryDirectory() as folder:
            full=Path(folder)/f'{day}_A股日报_完整版.html'
            value=evidence(record,raw)
            before=deepcopy(value)
            with patch('report.sector_trend_tracking.collect_trend_evidence',side_effect=AssertionError('已有事实不重复查询')):
                sector=save_sector_daily(source,day,snapshot=snapshot,full_html_path=full,
                                        hypothesis_record=record,trend_evidence=value)
            page=BeautifulSoup(sector.read_text(),'html.parser')
            self.assertIn('历史样本', page.get_text())
            self.assertEqual(len(page.select('#daily-evidence tbody tr')),10)
            self.assertNotIn('0%不参与', page.get_text())
            self.assertIsNone(page.select_one('#sector-hypothesis-record'))
            self.assertFalse((Path(folder)/'data').exists())
            self.assertEqual(value,before)


if __name__=='__main__':
    unittest.main()


class MonthlyLeaderHeatTest(unittest.TestCase):
    """本月每日前三板块的并集方格：只看当日排名与当日涨跌。"""

    def board(self):
        from report.sector_trend_tracking import leader_board
        return leader_board({
            '2026-10-09': [('AI视频', '885001.TI', 5.48), ('转基因', '885002.TI', 5.45),
                           ('短剧游戏', '885003.TI', 5.41), ('钠离子电池', '885004.TI', 1.9)],
            '2026-10-12': [('短剧游戏', '885003.TI', 1.86), ('AI视频', '885001.TI', 1.53),
                           ('知识产权保护', '885005.TI', 1.44)],
            '2026-10-15': [('青蒿素', '885006.TI', -0.43), ('证金持股', '885007.TI', -0.52),
                           ('同花顺漂亮100', '885008.TI', -0.85)],
            '2026-10-16': [('兵装重组概念', '886101.TI', 5.89), ('飞行汽车(eVTOL)', '886066.TI', 4.01),
                           ('成飞概念', '886030.TI', 3.82)],
        }, target_date='2026-10-16')

    def test_rows_are_union_of_daily_top_three(self):
        board = self.board()
        self.assertEqual(board['dates'], ['2026-10-09', '2026-10-12', '2026-10-15', '2026-10-16'])
        self.assertEqual(len(board['rows']), 10)
        names = [row['name'] for row in board['rows']]
        self.assertEqual([row['name'] for row in board['rows'] if row['selected_count'] == 2],
                         ['AI视频', '短剧游戏'])  # 入选2次的最先，同数按名称
        self.assertIn('兵装重组概念', names)
        self.assertEqual(sum(row['selected_count'] for row in board['rows']), 12)

    def test_cells_keep_real_change_and_missing_gaps(self):
        board = self.board()
        rows = {row['name']: row for row in board['rows']}
        self.assertEqual(rows['兵装重组概念']['pct'], [None, None, None, 5.89])
        self.assertEqual(rows['短剧游戏']['pct'], [5.41, 1.86, None, None])
        self.assertEqual(rows['短剧游戏']['selected'], [True, True, False, False])
        self.assertEqual(rows['短剧游戏']['temp'], [3, 2, None, None])

    def test_window_slices_last_trading_days_and_drops_future(self):
        from report.sector_trend_tracking import leader_board
        days = [(date(2026, 8, 1) + timedelta(days=i)).isoformat() for i in range(35)]
        series = {day: [(f'板块{i}', f'{i:06d}', 1.0 + i % 3)] for i, day in enumerate(days)}
        board = leader_board(series, target_date=days[33], window=30)
        self.assertEqual(board['window'], 30)
        self.assertEqual(board['dates'], days[4:34])          # 目标日之后不计入
        self.assertEqual(len(board['dates']), 30)
        self.assertEqual(len(board['daily_top']), 30)
        self.assertNotIn('板块34', [row['name'] for row in board['rows']])

        short = leader_board(series, target_date=days[10], window=5)
        self.assertEqual(short['dates'], days[6:11])

        fewer = leader_board({days[30]: [('甲', '1', 2.0)]}, target_date=days[32], window=30)
        self.assertEqual(fewer['dates'], [days[30]])          # 缺行日期不补 0

    def page(self, board, **kwargs):
        record, raw = sample(10)
        value = evidence(record, raw)
        return BeautifulSoup(render_trend_fragment(value, record, leader_board=board, **kwargs), 'html.parser')

    def test_heat_rows_follow_board_and_map_known_tracks(self):
        from report.sector_trend_tracking import _heat_view
        tracks = [{'name': '兵装重组概念', 'track_id': 't1', 'path': [{'date': '2026-10-16', 'change_pct': 5.8}]},
                  {'name': '样本板块', 'track_id': 't2', 'path': []}]
        heat = _heat_view(tracks, self.board())
        self.assertEqual(heat['source'], 'leader_board')
        self.assertEqual(heat['dates'], ['2026-10-09', '2026-10-12', '2026-10-15', '2026-10-16'])
        first = heat['rows'][0]
        self.assertEqual(first['name'], 'AI视频')
        self.assertIsNone(first['track_id'])  # 不在观察名单
        mapped = {row['name']: row['track_id'] for row in heat['rows']}
        self.assertEqual(mapped['兵装重组概念'], 't1')

    def test_fragment_replaces_observation_grid_in_place(self):
        page = self.page(self.board())
        headings = [h.get_text() for h in page.select('h4')]
        self.assertIn('最近4个交易日冷暖方格 · 每日涨幅前3（10个板块）', headings)
        self.assertNotIn('观察板块冷暖方格 · 全部1个观察板块（点击联动判断）', headings)
        self.assertTrue(page.select_one('#sector-trend-revisions'))  # 仍是原图容器
        self.assertIsNone(page.select_one('#sector-monthly-leaders'))
        view = json.loads(page.select_one('#sector-trend-view').string)
        self.assertEqual(view['heat']['dates'], ['2026-10-09', '2026-10-12', '2026-10-15', '2026-10-16'])
        rows = {row['name']: row for row in view['heat']['rows']}
        self.assertEqual(rows['短剧游戏']['selected'], [True, True, False, False])
        self.assertEqual(rows['短剧游戏']['temp'], [3, 2, None, None])
        self.assertEqual(rows['兵装重组概念']['pct'], [None, None, None, 5.89])
        self.assertIn('（入选）', page.get_text())
        self.assertIn('当日普跌时前三即跌幅最小三名', page.get_text())

    def test_fragment_without_board_keeps_observation_rows(self):
        page = self.page(None)
        self.assertIn('观察板块冷暖方格 · 全部1个观察板块（点击联动判断）',
                      [h.get_text() for h in page.select('h4')])
        view = json.loads(page.select_one('#sector-trend-view').string)
        self.assertEqual(view['heat']['source'], 'tracks')
        self.assertEqual([row['name'] for row in view['heat']['rows']], ['样本板块'])
        self.assertFalse(any(view['heat']['rows'][0]['selected']))

    def test_click_links_known_track_and_notes_unknown(self):
        from report.sector_trend_tracking import leader_board
        board = leader_board({'2026-10-09': [('样本板块', '884240.TI', 1.0),
                                                     ('外部板块', '885001.TI', 2.0)]},
                                     target_date='2026-10-09')
        page = self.page(board)
        names = [row['name'] for row in json.loads(page.select_one('#sector-trend-view').string)['heat']['rows']]
        self.assertEqual(names, ['外部板块', '样本板块'])  # 同分按目标日涨跌排序

        other = SectorTrendTest.chart_options(self, page, [
            {'chart': 'sector-trend-revisions',
             'event': {'componentType': 'series', 'value': [0, names.index('外部板块'), 1]}}])
        self.assertIn('外部板块', other['note'])
        self.assertIn('不在观察名单', other['note'])

        linked = SectorTrendTest.chart_options(self, page, [
            {'chart': 'sector-trend-revisions',
             'event': {'componentType': 'series', 'value': [0, names.index('样本板块'), 1]}}])
        self.assertEqual(linked['note'], '')
        self.assertEqual(linked['selection'], page.select('#sector-trend-selector option')[0]['value'])

    def test_board_names_are_escaped(self):
        from report.sector_trend_tracking import leader_board
        board = leader_board({'2026-10-16': [('<b>注入</b>', '885001.TI', 1.0)]},
                                     target_date='2026-10-16')
        page = self.page(board)
        self.assertNotIn('<b>注入</b>', str(page))
        self.assertIn('&lt;b&gt;注入&lt;/b&gt;', str(page))


if __name__ == '__main__':
    unittest.main()


class LeaderBoardCollectionTest(unittest.TestCase):
    """板块榜单采集：窗口、口径过滤、缓存与回退。"""

    def days(self, count=35):
        return [(date(2026, 8, 1) + timedelta(days=i)).isoformat() for i in range(count)]

    def index_map(self):
        return {'885001.TI': {'ts_code': '885001.TI', 'name': '甲概念', 'type': 'N', 'exchange': 'A'},
                '886002.TI': {'ts_code': '886002.TI', 'name': '乙概念', 'type': 'N', 'exchange': 'A'},
                '865003.TI': {'ts_code': '865003.TI', 'name': '美股指数', 'type': 'N', 'exchange': 'US'},
                '883004.TI': {'ts_code': '883004.TI', 'name': '样本指数', 'type': 'N', 'exchange': 'A'},
                '884005.TI': {'ts_code': '884005.TI', 'name': '丙行业', 'type': 'I', 'exchange': 'A'},
                '700006.TI': {'ts_code': '700006.TI', 'name': '丁行业', 'type': 'I', 'exchange': 'A'}}

    def test_window_filtering_and_cache(self):
        from report.sector_trend_tracking import collect_leader_board
        days = self.days()
        calls = []

        def rows(day):
            calls.append(day)
            return [{'ts_code': '885001.TI', 'pct_change': '2.5'},
                    {'ts_code': '886002.TI', 'pct_change': -1.0},
                    {'ts_code': '884005.TI', 'pct_change': 3.0},
                    {'ts_code': '700006.TI', 'pct_change': 1.5},
                    {'ts_code': '865003.TI', 'pct_change': 8.0},
                    {'ts_code': '883004.TI', 'pct_change': 9.0},
                    {'ts_code': '885001.TI', 'pct_change': 'bad'}]

        with TemporaryDirectory() as root:
            board = collect_leader_board(days[-1], window=30, cache_root=root,
                                         date_fetcher=lambda start, end: days,
                                         rows_fetcher=rows, index_map=self.index_map())
            self.assertEqual(len(calls), 30)                       # 只取最近 30 个交易日
            self.assertEqual(calls[0], days[-30])
            self.assertEqual(board['dates'], days[-30:])
            self.assertEqual([row['name'] for row in board['rows']], ['甲概念', '乙概念'])  # 非 885/886 剔除

            industry = collect_leader_board(days[-1], window=5, universe='industry', cache_root=root,
                                            date_fetcher=lambda start, end: days, rows_fetcher=rows,
                                            index_map=self.index_map())
            self.assertEqual([row['name'] for row in industry['rows']], ['丙行业', '丁行业'])
            self.assertTrue(Path(root, f'{days[-1]}.json').exists())
            calls.clear()
            again = collect_leader_board(days[-1], window=30, cache_root=root,
                                         date_fetcher=lambda start, end: days,
                                         rows_fetcher=rows, index_map=self.index_map())
            self.assertEqual(calls, [])                            # 命中缓存不再取数
            self.assertEqual(again['rows'], board['rows'])

    def test_universe_follows_report_codes(self):
        from report.sector_trend_tracking import leader_board_universe
        self.assertEqual(leader_board_universe([{'code': '884182.TI'}]), 'industry')
        self.assertEqual(leader_board_universe([{'code': '700515.TI'}]), 'industry')
        self.assertEqual(leader_board_universe([{'code': '885001.TI'}]), 'concept')
        self.assertEqual(leader_board_universe([{'code': '885001.TI'}, {'code': '884182.TI'}]), 'concept')
        self.assertEqual(leader_board_universe([{'code': '', 'name': '汽车服务',
                                                 'data_source': 'tushare.daily.industry_aggregate'}]), 'industry')
        self.assertEqual(leader_board_universe([{'code': '', 'name': '汽车服务'}]), 'concept')
        self.assertEqual(leader_board_universe([]), 'concept')

    def test_empty_rows_are_not_cached(self):
        from report.sector_trend_tracking import collect_leader_board
        days = self.days(3)
        with TemporaryDirectory() as root:
            first = {}
            def rows(day):
                if day == days[-1] and not first:
                    first['seen'] = True
                    return []
                return [{'ts_code': '885001.TI', 'pct_change': 1.0}]
            collect_leader_board(days[-1], window=30, cache_root=root,
                                 date_fetcher=lambda start, end: days, rows_fetcher=rows,
                                 index_map=self.index_map())
            self.assertFalse(Path(root, f'{days[-1]}.json').exists())  # 空结果不落盘
            again = collect_leader_board(days[-1], window=30, cache_root=root,
                                         date_fetcher=lambda start, end: days, rows_fetcher=rows,
                                         index_map=self.index_map())
            self.assertEqual(len(again['dates']), 3)                   # 数据发布后正常成列
            self.assertTrue(Path(root, f'{days[-1]}.json').exists())

    def test_missing_dates_and_source_failure_fall_back(self):
        from report.sector_trend_tracking import collect_leader_board
        days = self.days(5)
        with TemporaryDirectory() as root:
            empty = collect_leader_board(days[-1], window=30, cache_root=root,
                                         date_fetcher=lambda start, end: days,
                                         rows_fetcher=lambda day: [], index_map=self.index_map())
            self.assertEqual(empty, {})
            broken = collect_leader_board(days[-1], window=30, cache_root=root,
                                          date_fetcher=lambda start, end: (_ for _ in ()).throw(RuntimeError('x')),
                                          rows_fetcher=lambda day: [], index_map=self.index_map())
            self.assertEqual(broken, {})
            wrong_date = collect_leader_board('2026/10/16', window=30, cache_root=root,
                                              date_fetcher=lambda start, end: days,
                                              rows_fetcher=lambda day: [], index_map=self.index_map())
            self.assertEqual(wrong_date, {})
