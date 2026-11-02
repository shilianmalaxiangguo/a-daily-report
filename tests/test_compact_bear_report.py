import sys
import json
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from bs4 import BeautifulSoup
from report.compact_bear_report import SELECTION, seal_rows, render_compact

class CompactBearTest(unittest.TestCase):
    def test_seal_filter_sort_and_date(self):
        def row(name, amount, code='000001.SZ'):
            return dict(name=name,fd_amount=amount,ts_code=code,limit='U',trade_date='20260918')
        rows=[{**row('正常',1e8),'close':10},{**row('第二',2e8,'000002.SZ'),'close':20},row('*ST甲',9e8),row('st乙',8e8),row('空值',None),row('零',0)]
        self.assertEqual([r['name'] for r in seal_rows(rows,'2026-09-18')],['第二','正常'])
        self.assertAlmostEqual(seal_rows(rows,'2026-09-18')[0]['hands_wan'], 10.0)
        with self.assertRaises(ValueError):seal_rows(rows,'2026-09-17')
    def test_only_selected_surfaces_and_no_input_mutation(self):
        source='<html><head><title>2026-09-18日报</title></head><body><h2>长篇附录</h2><p>不要保留</p><section data-bear-chart-card="turnover_top30">图</section><section data-bear-chart-card="sector_cycle_swimlane">不要保留</section><h2>板块资金扩散淘汰赛</h2><table><tr><td>证据</td></tr></table><h2>其他</h2><h3>1. 周期日历主视图</h3><table><tr><td>日历</td></tr></table><h3>周期解读</h3></body></html>'
        result=render_compact(source,[],'2026-09-18')
        self.assertNotIn('不要保留',result)
        self.assertIn('证据',result);self.assertIn('日历',result)
        self.assertIn('目标日事实不足',result)
    def test_unregistered_day_is_not_reported_as_verified(self):
        import daily_report_entry_demo as entry
        self.assertIsNone(entry._assert_historical_rebuild_decision({},'2026-09-18')['passed'])

    def test_confirmed_order_preserves_execution_and_folds_tournament(self):
        source = '''<html><head><title>2026-09-18日报</title></head><body>
        <h2>明日执行结论</h2><table><tr><td>旧仓待确认</td></tr></table>
        <h2>板块资金扩散淘汰赛</h2><div class="reader-table"><table><tr><td>摘要事实</td></tr></table></div>
        <p>反方证据不能删除</p><h3>明细</h3><table><tr><td>尚未确认</td></tr></table>
        <h2>其他</h2><section data-bear-chart-card="board_tag_rank_bar">未选标签热度</section>
        </body></html>'''
        result = BeautifulSoup(render_compact(source, [], '2026-09-18'), 'html.parser')
        self.assertEqual(
            [node['data-compact-item'] for node in result.select('[data-compact-item]')],
            ['execution', 'execution_diagnostic', *[key for key, _ in SELECTION if key != 'execution']],
        )
        self.assertEqual(len(SELECTION), 12)
        self.assertEqual(result.select_one('[data-compact-item="execution"] table').get_text(), '旧仓待确认')
        tournament = result.select_one('[data-compact-item="t2"]')
        self.assertIsNone(tournament.select_one('table').find_parent('details'))
        details = tournament.select_one('details')
        self.assertFalse(details.has_attr('open'))
        self.assertIn('反方证据不能删除', details.get_text())
        self.assertIn('尚未确认', details.get_text())
        self.assertNotIn('未选标签热度', result.get_text())
        self.assertIsNone(result.select_one('#seal-amount-chart'))

    def test_execution_diagnostic_uses_frozen_candidate_and_gap_facts(self):
        source = '''<html><head><title>2026-09-18日报</title></head><body>
        <h2>明日执行结论</h2><table><tr><td>明日新仓</td><td>0%不参与</td></tr></table>
        </body></html>'''
        snapshot = {
            'date': '2026-09-18',
            'data': {
                'selection_workflow': {
                    'target_date': '2026-09-18',
                    'final': {'action_text': '0%不参与'},
                    'candidate_pool': [{'status': 'legacy_signal_only'}],
                    'local_trend_sector_proof': {'evidence_gaps': ['内部扩散']},
                },
                'candidate_trace_artifact': {'payload': {'traces': []}},
            },
        }
        soup = BeautifulSoup(render_compact(source, [], '2026-09-18', snapshot=snapshot), 'html.parser')
        diagnostic = soup.select_one('[data-compact-item="execution_diagnostic"]')
        self.assertIn('候选池有 1 只', diagnostic.get_text())
        self.assertIn('当前阻塞：内部扩散', diagnostic.get_text())
        self.assertIn('当前动作：0%不参与', diagnostic.get_text())

    def test_execution_diagnostic_is_hidden_for_positive_execution(self):
        source = '''<html><head><title>2026-09-18日报</title></head><body>
        <h2>明日执行结论</h2><table><tr><td>明日新仓</td><td>50%条件执行</td></tr></table>
        </body></html>'''
        snapshot = {
            'date': '2026-09-18',
            'data': {
                'target_date': '2026-09-18',
                'selection_workflow': {
                    'target_date': '2026-09-18',
                    'final': {
                        'action_text': '50%条件执行',
                        'position_pct': 50,
                        'execution_object': {'code': '000001'},
                    },
                },
            },
        }
        soup = BeautifulSoup(render_compact(source, [], '2026-09-18', snapshot=snapshot), 'html.parser')
        self.assertIsNone(soup.select_one('[data-compact-item="execution_diagnostic"]'))

    def test_execution_diagnostic_rejects_mismatched_workflow_date(self):
        source = '''<html><head><title>2026-09-18日报</title></head><body>
        <h2>明日执行结论</h2><table><tr><td>明日新仓</td><td>0%不参与</td></tr></table>
        </body></html>'''
        snapshot = {
            'date': '2026-09-18',
            'data': {
                'selection_workflow': {
                    'target_date': '2026-09-17',
                    'candidate_pool': [{'status': 'legacy_signal_only'}],
                    'final': {'action_text': '0%不参与'},
                },
            },
        }
        soup = BeautifulSoup(render_compact(source, [], '2026-09-18', snapshot=snapshot), 'html.parser')
        diagnostic = soup.select_one('[data-compact-item="execution_diagnostic"]')
        self.assertIn('冻结诊断事实不足', diagnostic.get_text())
        self.assertNotIn('候选池有 1 只', diagnostic.get_text())

    def test_seal_chart_labels_amount_and_hands(self):
        source = '<html><head><title>2026-09-18日报</title></head><body></body></html>'
        html = render_compact(source, [{
            'name': '样本', 'ts_code': '000001.SZ', 'fd_amount': 100000000,
            'close': 10, 'pct_chg': 10, 'limit': 'U', 'trade_date': '20260918',
        }], '2026-09-18')
        soup = BeautifulSoup(html, 'html.parser')
        script = soup.find_all('script')[-1].string
        item = json.loads(script.split('const rows=', 1)[1].split('; let showAll=', 1)[0])[0]
        self.assertEqual(item['amount_yi'], 1.0)
        self.assertEqual(item['hands_wan'], 10.0)
        self.assertIn('柱尾标注金额与手数', soup.get_text())
        self.assertIn('万手', soup.get_text())

    def test_seal_invalid_values_and_conflicting_duplicates(self):
        base = dict(name='测试', ts_code='000001.SZ', trade_date='20260918', limit='U')
        for value in [None, float('inf'), float('nan'), -1, 0]:
            self.assertEqual(seal_rows([{**base, 'fd_amount': value}], '2026-09-18'), [])
        self.assertEqual(seal_rows([{**base, 'limit': 'Z', 'fd_amount': 10}], '2026-09-18'), [])
        with self.assertRaises(ValueError):
            seal_rows([{**base, 'fd_amount': 1}, {**base, 'fd_amount': 2}], '2026-09-18')

    def test_seal_missing_price_preserves_amount_without_inventing_hands(self):
        base = dict(name='样本', ts_code='000001.SZ', trade_date='20260918', limit='U', fd_amount=1e8)
        for value in [None, '', '未知', 0, -1, float('nan'), float('inf')]:
            with self.subTest(value=value):
                item = seal_rows([{**base, 'close': value, 'pct_chg': value}], '2026-09-18')[0]
                self.assertEqual(item['amount_yi'], 1.0)
                self.assertIsNone(item['hands_wan'])
                self.assertIsNone(item['close'])
                json.dumps(item, allow_nan=False)

    def test_seal_only_filters_warning_prefix_and_normalizes_code(self):
        base = dict(name='BEST科技', ts_code=' 000001.SZ ', trade_date='20260918', limit='U', fd_amount=1e8)
        self.assertEqual(seal_rows([base], '2026-09-18')[0]['code'], '000001.SZ')
        for name in ['ST样本', '*ST样本', '* st 样本']:
            self.assertEqual(seal_rows([{**base, 'name': name}], '2026-09-18'), [])
        with self.assertRaises(ValueError):
            seal_rows([{**base, 'ts_code': '   '}], '2026-09-18')
        with self.assertRaises(ValueError):
            seal_rows([base, {**base, 'ts_code': '000001.SZ'}], '2026-09-18')

    def test_seal_serialization_cannot_end_script(self):
        name = '</script><img src=x onerror=alert(1)>'
        source = '<html><head><title>2026-09-18日报</title></head><body></body></html>'
        result = BeautifulSoup(render_compact(source, [{
            'name': name, 'ts_code': '000001.SZ', 'trade_date': '20260918',
            'limit': 'U', 'fd_amount': 1e8, 'close': 10,
        }], '2026-09-18'), 'html.parser')
        self.assertIsNone(result.select_one('img'))
        script = result.find_all('script')[-1].string
        payload = script.split('const rows=', 1)[1].split('; let showAll=', 1)[0]
        self.assertEqual(json.loads(payload)[0]['name'], name)
        self.assertIn('换算（1手=100股）', result.get_text())

    def test_compact_preserves_futures_card_and_frozen_chart_values(self):
        from report.markdown_report_html import render_markdown_report_html
        from tests.legacy_test_daily_report_markdown_html import _cffex_position_evidence
        evidence = _cffex_position_evidence(target_date='2026-09-18', item_count=30)
        before = json.dumps(evidence, sort_keys=True)
        source = render_markdown_report_html(
            '# 2026-09-18日报\n\n## 股指期货持仓结构（研究证据）\n\n目标日持仓。',
            title='2026-09-18日报', trade_date='2026-09-18',
            cffex_index_futures_position_evidence=evidence,
        )
        full = BeautifulSoup(source, 'html.parser')
        compact = BeautifulSoup(render_compact(source, [], '2026-09-18'), 'html.parser')
        card = '[data-bear-chart-card="cffex_position_trend"]'
        self.assertIsNotNone(compact.select_one(card + ' canvas, ' + card + ' [data-bear-chart]'))
        self.assertEqual(compact.select_one(card).get_text(), full.select_one(card).get_text().replace(
            '目标日精确值与名义金额复核见下表', '目标日精确值与名义金额复核见完整版持仓表',
        ))
        full_payload = json.loads(full.select_one('#bear-chart-payload').get_text())['cffex_position_trend']
        compact_payload = json.loads(compact.select_one('#bear-chart-payload').get_text())['cffex_position_trend']
        self.assertEqual(compact_payload['items'], full_payload['items'])
        self.assertEqual(json.dumps(evidence, sort_keys=True), before)

    def test_compact_historical_futures_keeps_short_and_long_samples_and_other_charts(self):
        from datetime import date, timedelta

        for count in (7, 30, 75):
            with self.subTest(count=count):
                items = [{
                    'date': (date(2026, 9, 18) - timedelta(days=count - index - 1)).isoformat(),
                    'member_net_short_notional_yi': None if index == 3 else index + 800,
                    'member_net_short_change': None if index == 3 else index,
                    'top20_cross_section_net_short': None if index == 3 else index + 1000,
                } for index in range(count)]
                payload = {
                    'cffex_position_trend': {
                        'schema': 'cffex_position_trend.v1',
                        'default_window': min(20, count), 'max_window': count,
                        'target_date': '2026-09-18', 'items': items,
                    },
                    'market_turnover_trend': {'default_window': 20, 'items': [{'date': '2026-09-18', 'value': None}]},
                }
                source = '''<html><head><title>2026-09-18日报</title></head><body>
                <section data-bear-chart-card="cffex_position_trend">
                  <div data-bear-chart-window-control="cffex_position_trend">
                    <button data-window-size="20" aria-pressed="true">20日</button>
                    <button data-window-size="60" aria-pressed="false">60日</button>
                  </div>
                  <div data-bear-chart="cffex_position_trend"></div>
                  <p class="bear-chart-footnote">默认显示最近20日，可切换到最多60日；缺失值不补0</p>
                </section>
                <script type="application/json" id="bear-chart-payload">''' + json.dumps(payload) + '</script></body></html>'
                if count <= 20:
                    historical = BeautifulSoup(source, 'html.parser')
                    historical.select_one('[data-bear-chart-window-control]').decompose()
                    source = str(historical)
                compact = BeautifulSoup(render_compact(source, [], '2026-09-18'), 'html.parser')
                extracted = json.loads(compact.select_one('#bear-chart-payload').get_text())
                self.assertEqual(extracted['market_turnover_trend'], payload['market_turnover_trend'])
                frozen = payload['cffex_position_trend']
                chart = extracted['cffex_position_trend']
                self.assertEqual(chart, frozen)
                self.assertEqual(len(chart['items']), count)
                self.assertIsNone(chart['items'][3]['member_net_short_notional_yi'])
                self.assertEqual(
                    {button['data-window-size'] for button in compact.select('[data-bear-chart-window-control] button')},
                    {'20', '60'},
                )
                original = BeautifulSoup(source, 'html.parser')
                self.assertEqual(json.loads(original.select_one('#bear-chart-payload').get_text()), payload)

    def test_historical_inline_renderer_is_refreshed_without_changing_payload(self):
        from report.markdown_report_html import render_markdown_report_html
        from tests.legacy_test_daily_report_markdown_html import _cffex_position_evidence, cffex_chart_states

        source = render_markdown_report_html(
            '# 2026-09-18日报\n\n## 股指期货持仓结构（研究证据）\n\n目标日持仓。',
            title='2026-09-18日报', trade_date='2026-09-18',
            cffex_index_futures_position_evidence=_cffex_position_evidence(target_date='2026-09-18', item_count=60),
        )
        start = source.index('const renderCffexPositionTrendChart =')
        end = source.index('const renderMarketTurnoverTrendChart =')
        historical = source[:start] + 'const renderCffexPositionTrendChart = () => { throw Error("old renderer"); };\n' + source[end:]
        frozen = BeautifulSoup(historical, 'html.parser').select_one('#bear-chart-payload').string
        compact = render_compact(historical, [], '2026-09-18')
        self.assertEqual(BeautifulSoup(compact, 'html.parser').select_one('#bear-chart-payload').string, frozen)
        states = cffex_chart_states(compact, json.loads(frozen)['cffex_position_trend'])
        self.assertEqual([len(state['option']['xAxis'][0]['data']) for state in states], [60, 20, 60])
        self.assertTrue(all(not state['option'].get('dataZoom') for state in states))

    def _sector_snapshot(self, **row_overrides):
        row = dict(name='全国地产', change_pct=6.08, up_count=25,
                   stock_count=26, turnover_yi=124.46,
                   trade_date='2026-09-18', source_date='2026-09-18',
                   query_date='2026-09-18', data_source='tushare.daily.industry_aggregate')
        return {'date': '2026-09-18', 'data': {
            'target_date': '2026-09-18', 'source_date': '2026-09-18',
            'sector_change_up': [{**row, **row_overrides}],
            'final_target_resolution': {'new_entry_target': None},
            'volume_anomalies': [{'name': '未经日期核对的股票', 'volume_ratio': 2}],
        }}

    def _hypothesis_result(self, snapshot):
        source = '''<html><head><title>2026-09-18日报</title></head><body>
        <h2>明日执行结论</h2><table><tr><td>明日新仓</td><td>0%不参与</td></tr>
        <tr><td>旧仓动作</td><td>待核实</td></tr></table><h2>后续</h2></body></html>'''
        return BeautifulSoup(render_compact(source, [], '2026-09-18', snapshot=snapshot), 'html.parser')

    def test_sector_hypotheses_follow_action_and_keep_facts_and_decisions_separate(self):
        snapshot = self._sector_snapshot()
        before = json.dumps(snapshot, sort_keys=True)
        soup = self._hypothesis_result(snapshot)
        items = soup.select('[data-compact-item]')
        self.assertEqual([n['data-compact-item'] for n in items[:3]], ['execution', 'execution_diagnostic', 'sector_hypotheses'])
        self.assertEqual(items[0].select_one('table').get_text('', strip=True), '明日新仓0%不参与旧仓动作待核实')
        section = items[2]
        self.assertIn('bear-section-evidence', section.h2['class'])
        self.assertEqual(len(section.select('.compact-hypothesis-card')), 3)
        self.assertEqual(len(section.select('.sector-daily-hypotheses tbody tr')), 3)
        self.assertIn('全国地产', section.get_text())
        self.assertIn('25/26', section.get_text())
        self.assertIn('未校准不填写概率', section.get_text())
        self.assertIn('最大计划损失', section.get_text())
        self.assertIn('成交额不等于放量或资金净流入', section.get_text())
        self.assertNotIn('未经日期核对的股票', section.get_text())
        self.assertFalse(section.details.has_attr('open'))
        self.assertEqual(json.dumps(snapshot, sort_keys=True), before)

    def test_sector_facts_require_own_dates_and_exact_source_and_sort_valid_rows(self):
        snapshot = self._sector_snapshot()
        base = snapshot['data']['sector_change_up'][0]
        snapshot['data']['sector_change_up'] += [
            {**base, 'name': '未来板块', 'trade_date': '2026-09-21'},
            {**base, 'name': '过去板块', 'source_date': '2026-09-17'},
            {**base, 'name': '晚查板块', 'query_date': '2026-09-21'},
            {**base, 'name': '无日期板块', 'trade_date': '', 'source_date': ''},
            {**base, 'name': '无查询日板块', 'query_date': ''},
            {**base, 'name': '无来源日板块', 'source_date': ''},
            {**base, 'name': '未知来源板块', 'data_source': ''},
            {**base, 'name': '低涨幅', 'change_pct': 1.2},
            {**base, 'name': '最高涨幅', 'change_pct': 8.0, 'trade_date': '20260918'},
        ]
        section = self._hypothesis_result(snapshot).select_one('[data-compact-item="sector_hypotheses"]')
        names = [tr.td.get_text() for tr in section.select('.compact-sector-facts tbody tr')]
        self.assertEqual(names, ['最高涨幅', '全国地产', '低涨幅'])
        for text in ('未来板块', '过去板块', '晚查板块', '无日期板块', '无查询日板块', '无来源日板块', '未知来源板块'):
            self.assertNotIn(text, section.get_text())

    def test_missing_sector_facts_and_invalid_metrics_do_not_invent_evidence(self):
        for value in (None, float('nan'), float('inf'), True):
            with self.subTest(value=value):
                section = self._hypothesis_result(self._sector_snapshot(change_pct=value)).select_one('[data-compact-item="sector_hypotheses"]')
                self.assertIn('目标日板块事实不足', section.get_text())
        for overrides in ({'up_count': None}, {'up_count': 30}, {'up_count': 25.5}, {'stock_count': 0}, {'turnover_yi': None}):
            with self.subTest(overrides=overrides):
                section = self._hypothesis_result(self._sector_snapshot(**overrides)).select_one('[data-compact-item="sector_hypotheses"]')
                self.assertIn('待确认', section.get_text())
        section = self._hypothesis_result(None).select_one('[data-compact-item="sector_hypotheses"]')
        self.assertEqual(len(section.select('.compact-hypothesis-card')), 3)
        self.assertIn('目标日板块事实不足', section.get_text())

    def test_ths_index_facts_use_own_trade_date_without_inventing_breadth(self):
        value = self._sector_snapshot()
        value['data']['sector_change_up'] = [{
            'name': '疫苗', 'change_pct': 4.8234, 'data_source': 'tushare.ths_daily',
            'trade_date': '20260918', 'turnover_rate': 4.07,
            'up_count': 99, 'stock_count': 100, 'turnover_yi': 100,
        }]
        before = json.dumps(value, sort_keys=True)
        soup = self._hypothesis_result(value)
        section = soup.select_one('[data-compact-item="sector_hypotheses"]')
        self.assertEqual([td.get_text() for td in section.select('tbody tr')[0].select('td')],
                         ['疫苗', '+4.82%'])
        self.assertIn('缺成员上涨/总数，无法判断扩散', section.get_text())
        self.assertIn('缺同口径成交额与历史基准，无法判断放量', section.get_text())
        self.assertIn('指数当日收益', section.get_text())
        self.assertNotIn('加权涨跌幅', section.get_text())
        self.assertEqual(json.dumps(value, sort_keys=True), before)
        index_fact = value['data']['sector_change_up'][0]
        value['data']['sector_change_up'] = [
            {**index_fact, 'code': '700833.TI'}, {**index_fact, 'code': '700720.TI'},
        ]
        self.assertEqual(len(self._hypothesis_result(value).select('.compact-sector-facts tbody tr')), 2)
        value['data']['sector_change_up'][1]['code'] = '700833.TI'
        with self.assertRaises(ValueError):
            self._hypothesis_result(value)
        for overrides in ({'trade_date': ''}, {'trade_date': '2026-09-21'},
                          {'source_date': '2026-09-17'}, {'query_date': '2026-09-21'}):
            with self.subTest(overrides=overrides):
                value['data']['sector_change_up'] = [{
                    'name': '疫苗', 'change_pct': 4.8234, 'data_source': 'tushare.ths_daily',
                    'trade_date': '20260918', **overrides,
                }]
                self.assertIn('目标日板块事实不足', self._hypothesis_result(value).get_text())

    def test_overlapping_rankings_keep_each_dated_sector_once(self):
        from report.compact_bear_report import _frozen_sector_facts
        for source in ('tushare.ths_daily', 'tushare.daily.industry_aggregate'):
            with self.subTest(source=source):
                snapshot = self._sector_snapshot(data_source=source, code='700711.TI', rank=1)
                first = snapshot['data']['sector_change_up'][0]
                second = {**first, 'name': '另一板块', 'code': '700778.TI', 'change_pct': -1.0, 'rank': 2}
                snapshot['data']['sector_change_up'].append(second)
                snapshot['data']['sector_change_down'] = [{**second, 'rank': 1}, {**first, 'rank': 2}]
                before = json.dumps(snapshot, sort_keys=True)
                rows, _ = _frozen_sector_facts(snapshot, '2026-09-18', include_nonpositive=True)
                self.assertEqual([(row['name'], row['change_pct']) for row in rows],
                                 [('全国地产', 6.08), ('另一板块', -1.0)])
                soup = self._hypothesis_result(snapshot)
                self.assertEqual(
                    [tr.td.get_text() for tr in soup.select('.compact-sector-facts tbody tr')],
                    ['全国地产'],
                )
                self.assertEqual(json.dumps(snapshot, sort_keys=True), before)

    def test_overlapping_rankings_reject_conflicting_facts_and_same_list_duplicates(self):
        for field, value in (('change_pct', -2), ('up_count', 24), ('turnover_yi', 99), ('close', 123)):
            with self.subTest(field=field):
                snapshot = self._sector_snapshot(rank=1)
                first = snapshot['data']['sector_change_up'][0]
                snapshot['data']['sector_change_down'] = [{**first, 'rank': 2, field: value}]
                with self.assertRaises(ValueError):
                    self._hypothesis_result(snapshot)
        snapshot = self._sector_snapshot(rank=1)
        first = snapshot['data']['sector_change_up'][0]
        snapshot['data']['sector_change_down'] = [{**first, 'rank': 2}, {**first, 'rank': 3}]
        with self.assertRaises(ValueError):
            self._hypothesis_result(snapshot)

    def test_snapshot_wrong_date_or_duplicate_industry_stops_rendering(self):
        for snapshot in ([1], {'date': '2026-09-17', 'data': {}}, {'date': '2026-09-18', 'data': {'source_date': '2026-09-21'}}):
            with self.subTest(snapshot=snapshot), self.assertRaises(ValueError):
                self._hypothesis_result(snapshot)
        snapshot = self._sector_snapshot()
        snapshot['data']['sector_change_up'] *= 2
        with self.assertRaises(ValueError):
            self._hypothesis_result(snapshot)

    def test_sector_labels_escape_html_and_invalid_frozen_direction_is_not_used(self):
        snapshot = self._sector_snapshot(name='<img src=x onerror=alert(1)>')
        snapshot['data']['selection_workflow'] = {'sector_tournament_three_axis': {
            'target_date': '2026-09-18', 'direction': '未经校验的方向', 'artifact_hash': 'invalid',
        }}
        section = self._hypothesis_result(snapshot).select_one('[data-compact-item="sector_hypotheses"]')
        self.assertIsNone(section.select_one('img'))
        self.assertIn('<img src=x onerror=alert(1)>', section.get_text())
        self.assertNotIn('未经校验的方向', section.get_text())

    def test_retired_compact_cli_stops_without_reading_or_writing(self):
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            # Missing inputs would raise file errors if the retired path ran.
            result = subprocess.run([
                sys.executable, str(Path(__file__).resolve().parents[1] / 'scripts/report/compact_bear_report.py'),
                str(root / 'source.html'), str(root / 'seal.json'), '2026-09-18', str(root / 'output.html'),
                '--snapshot', str(root / 'snapshot.json'),
            ], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn('已停止生成', result.stderr)
            self.assertEqual(list(root.iterdir()), [])

    def test_verified_research_direction_stays_separate_and_tampering_is_rejected(self):
        from report.candidate_decision_evidence import (
            build_sector_diffusion_stage_evidence, build_sector_tournament_three_axis,
        )
        proof = {'direction': '原研究方向', 'source_date': '2026-09-18',
                 'direction_source_date': '2026-09-18',
                 'internal_expansion_status': 'failed', 'divergence_acceptance_status': 'failed'}
        stage = build_sector_diffusion_stage_evidence(
            target_date='2026-09-18', local_trend_sector_proof=proof,
        )
        axis = build_sector_tournament_three_axis(
            target_date='2026-09-18', sector_diffusion_stage_evidence=stage,
            local_trend_sector_proof=proof,
            market_participation_limit={'source_date': '2026-09-18'},
        )
        snapshot = self._sector_snapshot()
        snapshot['data']['selection_workflow'] = {'sector_tournament_three_axis': axis}
        before = json.dumps(snapshot, sort_keys=True)
        section = self._hypothesis_result(snapshot).select_one('[data-compact-item="sector_hypotheses"]')
        self.assertEqual(section['data-sector-source-hash'], axis['artifact_hash'])
        self.assertIn('原研究方向：原研究方向', section.get_text())
        self.assertIn('全国地产', section.get_text())
        self.assertIn('A｜持续走强', section.get_text())
        self.assertEqual(json.dumps(snapshot, sort_keys=True), before)
        axis['direction'] = '被篡改方向'
        section = self._hypothesis_result(snapshot).select_one('[data-compact-item="sector_hypotheses"]')
        self.assertNotIn('data-sector-source-hash', section.attrs)
        self.assertNotIn('被篡改方向', section.get_text())
