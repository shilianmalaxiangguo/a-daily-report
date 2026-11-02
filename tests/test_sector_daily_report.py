import json
import subprocess
import sys
import unittest
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from bs4 import BeautifulSoup
from report.sector_daily_report import market_background_facts, render_sector_daily, save_sector_daily, sector_daily_output_path


DATE = '2026-09-29'
SOURCE = '''<html><head><title>2026-09-29日报</title></head><body>
<h2>明日执行结论</h2><table><tr><th>明日新仓</th><td>0%不参与</td></tr>
<tr><th>旧仓动作</th><td>持仓未输入，先核实</td></tr></table>
<h2>板块资金扩散淘汰赛</h2><table><tr><td>原始板块证据</td></tr></table><p>原始反证</p>
<h2>其他</h2><section data-bear-chart-card="market_turnover_trend">原图表</section>
<script id="bear-chart-payload" type="application/json">{"sample":[1,null,3]}</script>
</body></html>'''


def snapshot():
    base = {'data_source': 'tushare.daily.industry_aggregate', 'trade_date': DATE,
            'source_date': DATE, 'query_date': DATE, 'turnover_yi': 10}
    return {'date': DATE, 'data': {
        'sector_change_up': [
            {**base, 'name': name, 'change_pct': change, 'up_count': up, 'stock_count': count}
            for name, change, up, count in [('全国地产', 6.09, 25, 26), ('区域地产', 4.56, 41, 43),
                                           ('软饮料', 4.45, 5, 9), ('房产服务', 3.59, 10, 13)]
        ],
        'wind_a_alternative': {'trade_date': DATE, 'source_date': DATE, 'query_date': DATE,
                               'data_source': 'tushare.index_daily', 'change_pct': 0.36},
        'market_stats': {'trade_date': DATE, 'source_date': DATE, 'query_date': DATE,
                         'data_source': 'tushare.daily', 'up_count': 3471, 'down_count': 1933,
                         'flat_count': 0, 'stock_count': 5404,
                         'sample_label': '有效日线样本'},
        'turnover_data': {'date': DATE, 'source_date': DATE, 'query_date': DATE,
                          'data_source': 'tushare.daily', 'total_turnover_yi': 14215.96},
        'selection_workflow': {'final': {'position_pct': 0, 'b2_allowed': False}},
    }}


class SectorDailyReportTest(unittest.TestCase):
    def render(self, value=None, source=SOURCE):
        return BeautifulSoup(render_sector_daily(source, DATE, snapshot=value), 'html.parser')

    def test_current_surface_is_chart_first_and_keeps_sector_facts(self):
        value = snapshot()
        before = deepcopy(value)
        soup = self.render(value)
        facts = json.loads(soup.select_one('#sector-reading-facts').get_text())
        self.assertEqual([row['name'] for row in facts['rows']], ['全国地产', '区域地产', '软饮料', '房产服务'])
        self.assertEqual(len(facts['rows']), 4)
        self.assertEqual(facts['rows'][0]['change_pct'], 6.09)
        self.assertEqual(value, before)
        self.assertFalse(soup.select('.execution-overview, .sector-daily-hypotheses, #sector-hypothesis-record, '
                                     '#daily-market, #daily-next, #daily-sector-flows, #daily-cycle-history, #daily-competition'))
        self.assertIsNotNone(soup.select_one('[data-sector-daily-chart="change"]'))
        self.assertFalse(soup.select('#daily-sectors table, #daily-sectors p'))

    def test_bootstrap_navigation_and_direct_chart_sections_remain(self):
        soup = self.render(snapshot())
        self.assertIsNotNone(soup.select_one('main.sector-daily.container'))
        self.assertEqual(soup.select_one('#bootstrap-css')['data-version'], '6.0.0-alpha.1')
        self.assertEqual(soup.select_one('.daily-header time')['datetime'], DATE)
        for link in soup.select('.daily-nav a'):
            self.assertIsNotNone(soup.select_one(link['href']))
        self.assertEqual(soup.select_one('#daily-evidence').name, 'section')
        self.assertIn('未提供可核对的市场图表', soup.select_one('#daily-evidence').get_text())
        self.assertIsNone(soup.select_one('#bear-chart-payload'))
        self.assertIsNotNone(soup.select_one('[data-bear-echarts-loader]'))
        empty = self.render()
        self.assertIsNone(empty.select_one('[data-bear-echarts-loader]'))

    def test_reading_page_omits_manual_annotation_script_controls_and_styles(self):
        soup = self.render(snapshot())
        self.assertIsNone(soup.select_one('#sector-reader-annotations'))
        for marker in ('__dailyReportAnnotations', 'daily-report-annotations:v1:',
                       'data-reader-annotation', 'reader-note-', '我的标注'):
            self.assertNotIn(marker, str(soup))
        self.assertIsNotNone(soup.select_one('#sector-visual-chart-driver'))
        self.assertIsNotNone(soup.select_one('#sector-daily-archive-resize'))
        styles = '\n'.join(node.get_text() for node in soup.find_all('style'))
        self.assertIn('.reader-key-condition', styles)
        self.assertNotIn('.reader-note-', styles)

    def test_reading_page_does_not_install_selection_or_annotation_storage_handlers(self):
        soup = self.render(snapshot())
        scripts = '\n'.join(node.get_text() for node in soup.find_all('script')
                            if not node.has_attr('data-bear-echarts-loader'))
        for marker in ('selectionchange', 'localStorage', 'reader_annotations.js'):
            self.assertNotIn(marker, scripts)

    def test_manual_annotations_are_also_absent_for_other_report_dates(self):
        other = '2026-09-28'
        value = snapshot()
        value['date'] = other
        for item in value['data']['sector_change_up']:
            for key in ('trade_date', 'source_date', 'query_date'):
                item[key] = other
        value['data']['wind_a_alternative']['trade_date'] = other
        value['data']['market_stats']['trade_date'] = other
        value['data']['market_stats']['source_date'] = other
        value['data']['turnover_data']['date'] = other
        soup = BeautifulSoup(render_sector_daily(SOURCE.replace(DATE, other), other, snapshot=value), 'html.parser')
        self.assertIsNone(soup.select_one('#sector-reader-annotations'))
        self.assertNotIn('daily-report-annotations:v1:', str(soup))
        self.assertEqual(soup.select_one('.daily-header time')['datetime'], other)

    def test_reading_page_loads_no_external_resources(self):
        soup = self.render(snapshot())
        for tag in soup.find_all(True):
            for attribute in ('src', 'href', 'data-src', 'poster'):
                value = str(tag.get(attribute) or '').lower()
                # data-source 只是内联 ECharts 的来源标注，不是请求；这里只查真正的资源引用。
                self.assertFalse(value.startswith(('http://', 'https://', '//')),
                                 f'{tag.name} {attribute} 指向站外资源: {value}')
        styles = '\n'.join(node.get_text() for node in soup.find_all('style'))
        self.assertNotIn('@import', styles)
        self.assertNotIn('url(http', styles)

    def test_daily_sector_chart_preserves_original_values_without_a_repeated_table(self):
        soup = self.render(snapshot())
        payload = json.loads(soup.select_one('#sector-visualization-payload').string)
        row = payload['change_groups']['tushare.daily.industry_aggregate'][0]
        self.assertEqual([row[key] for key in ('name', 'change_pct', 'up_count', 'stock_count', 'turnover_yi')],
                         ['全国地产', 6.09, 25, 26, 10])
        self.assertEqual(payload['all_a_change_pct'], 0.36)
        self.assertFalse(soup.select('#daily-sectors table'))

    def test_factual_gaps_do_not_generate_template_observations(self):
        value = snapshot()
        value['data']['selection_workflow']['local_trend_sector_proof'] = {'evidence_gaps': ['旧规则缺口']}
        value['data']['sector_change_up'][0]['up_count'] = None
        value['data']['sector_change_up'][1]['turnover_yi'] = None
        value['data'].pop('wind_a_alternative')
        soup = self.render(value)
        payload = json.loads(soup.select_one('#sector-visualization-payload').string)
        self.assertIsNone(payload['all_a_change_pct'])
        group = payload['change_groups']['tushare.daily.industry_aggregate']
        self.assertIsNone(group[0]['stock_count'])
        self.assertIsNone(group[1]['turnover_yi'])
        self.assertIsNone(soup.select_one('#daily-next'))
        self.assertNotIn('旧规则缺口', str(soup))

    def test_ths_and_industry_are_separate_groups_and_ties_survive(self):
        value = snapshot()
        value['data']['sector_change_up'].extend([
            {'name': name, 'change_pct': change, 'trade_date': DATE, 'source_date': DATE,
             'query_date': DATE, 'data_source': 'tushare.ths_daily'}
            for name, change in [('疫苗', 4.9), ('研究指数', 4.9), ('其他', 1)]])
        soup = self.render(value)
        groups = json.loads(soup.select_one('#sector-visualization-payload').string)['change_groups']
        self.assertEqual({source: len(rows) for source, rows in groups.items()},
                         {'tushare.ths_daily': 3, 'tushare.daily.industry_aggregate': 4})
        self.assertEqual(len(soup.select('[data-sector-daily-chart="change"]')), 2)
        self.assertEqual([r['change_pct'] for r in groups['tushare.ths_daily'][:2]], [4.9, 4.9])
        self.assertIsNone(soup.select_one('.sector-reading-conclusion'))

    def test_market_requires_own_dates_and_retains_zero_change(self):
        value = snapshot()
        value['data']['wind_a_alternative']['change_pct'] = 0
        self.assertEqual(market_background_facts(value['data'], DATE)['change_pct'], 0)
        for field, key in [('wind_a_alternative', 'trade_date'), ('market_stats', 'source_date'), ('turnover_data', 'date')]:
            for day in ['', '2026-09-30', '2026-09-28']:
                with self.subTest(field=field, day=day):
                    value = snapshot()
                    value['data'][field][key] = day
                    expected = {'wind_a_alternative': 'change_pct', 'market_stats': 'up_count', 'turnover_data': 'amount_yi'}
                    self.assertIsNone(market_background_facts(value['data'], DATE)[expected[field]])

    def test_invalid_facts_are_missing_not_zero_or_no_trade(self):
        self.assertIn('无可核对的板块', self.render().get_text())
        value = snapshot()
        value['data']['sector_change_up'][0]['query_date'] = '2026-09-30'
        value['data']['sector_change_up'][1]['change_pct'] = True
        value['data']['market_stats']['up_count'] = True
        soup = self.render(value)
        text = soup.get_text()
        # A later retrieval date can still describe a target-date fact; the
        # malformed numeric row remains excluded.
        names = [row['name'] for row in json.loads(soup.select_one('#sector-reading-facts').string)['rows']]
        self.assertIn('全国地产', names)
        self.assertNotIn('区域地产', names)
        self.assertIsNone(market_background_facts(value['data'], DATE)['up_count'])
        self.assertNotIn('0%不参与', text)

    def test_missing_execution_is_valid_but_wrong_dates_fail(self):
        self.assertIsNotNone(self.render(snapshot(), SOURCE.replace('明日执行结论', '其他标题')))
        for source in [SOURCE.replace(DATE, '2026-09-28'), '<html></html>']:
            with self.assertRaises(ValueError):
                self.render(snapshot(), source)
        value = snapshot()
        value['date'] = '2026-09-30'
        with self.assertRaises(ValueError):
            self.render(value)
        with self.assertRaises(ValueError):
            render_sector_daily(None, '2026-02-30', snapshot=None)

    def test_duplicates_and_cross_list_conflicts_fail(self):
        value = snapshot()
        row = value['data']['sector_change_up'][0]
        value['data']['sector_change_down'] = [deepcopy(row)]
        self.assertEqual(len(json.loads(self.render(value).select_one('#sector-reading-facts').string)['rows']), 4)
        value['data']['sector_change_down'][0]['change_pct'] = -1
        with self.assertRaises(ValueError):
            self.render(value)
        value = snapshot()
        value['data']['sector_change_up'].append(deepcopy(value['data']['sector_change_up'][0]))
        with self.assertRaises(ValueError):
            self.render(value)

    def test_labels_are_escaped_and_no_probability_or_order_is_invented(self):
        value = snapshot()
        value['data']['sector_change_up'][0]['name'] = '<img src=x onerror=alert(1)>'
        soup = self.render(value)
        self.assertIsNone(soup.img)
        self.assertEqual(json.loads(soup.select_one('#sector-reading-facts').string)['rows'][0]['name'],
                         '<img src=x onerror=alert(1)>')
        self.assertNotIn('<img src=x onerror=alert(1)>', str(soup))
        for invented in ['概率60%', '已确认龙头', '主力吸筹', '明日执行对象']:
            self.assertNotIn(invented, soup.get_text())

    def test_old_tracking_gaps_are_not_current_requirements_and_no_records_are_written(self):
        with TemporaryDirectory() as folder:
            full = Path(folder) / 'replay' / f'{DATE}_A股日报_完整版_replay.html'
            before = snapshot()
            with patch('report.tracked_sector_facts.collect_tracked_facts', side_effect=AssertionError('不得取数')):
                path = save_sector_daily(SOURCE, DATE, snapshot=before, full_html_path=full,
                    previous_record={'tracks': [{'name': '历史缺失对象'}]}, ledger_root=Path(folder) / 'data')
            self.assertTrue(path.exists())
            self.assertFalse((Path(folder) / 'data').exists())
            self.assertNotIn('历史缺失对象', path.read_text())
            self.assertEqual(before, snapshot())

    def test_refresh_requests_are_rejected_without_writing(self):
        with TemporaryDirectory() as folder:
            full = Path(folder) / f'{DATE}_A股日报_完整版.html'
            with self.assertRaises(ValueError):
                save_sector_daily(SOURCE, DATE, snapshot=snapshot(), full_html_path=full, refresh_trend=True)
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_cli_keeps_replay_local_and_preserves_full_report(self):
        with TemporaryDirectory() as folder:
            full = Path(folder) / 'replay' / f'{DATE}_A股日报_完整版_replay.html'
            full.parent.mkdir()
            full.write_text(SOURCE)
            frozen = Path(folder) / 'snapshot.json'
            frozen.write_text(json.dumps(snapshot()))
            result = subprocess.run([sys.executable, 'scripts/report/sector_daily_report.py', str(full), str(frozen)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            path = sector_daily_output_path(full)
            self.assertTrue(path.exists())
            self.assertEqual(full.read_text(), SOURCE)
            soup = BeautifulSoup(path.read_text(), 'html.parser')
            self.assertIsNone(soup.footer.a)
            self.assertIn('历史修订不冒充当时预测', soup.footer.get_text())
            self.assertFalse(list(full.parent.glob('*.tmp')))

    def test_write_failure_leaves_existing_replay_page_and_removes_temporary(self):
        with TemporaryDirectory() as folder:
            full = Path(folder) / 'replay' / f'{DATE}_A股日报_完整版_replay.html'
            full.parent.mkdir()
            output = sector_daily_output_path(full)
            output.write_text('prior')
            with patch.object(Path, 'replace', side_effect=OSError('write failed')):
                with self.assertRaises(OSError):
                    save_sector_daily(SOURCE, DATE, snapshot=snapshot(), full_html_path=full)
            self.assertEqual(output.read_text(), 'prior')
            self.assertFalse(list(full.parent.glob('*.tmp')))

    def test_existing_official_page_is_not_overwritten(self):
        with TemporaryDirectory() as folder:
            full = Path(folder) / f'{DATE}_A股日报_完整版.html'
            output = sector_daily_output_path(full)
            output.write_text('历史板块页')
            with self.assertRaises(ValueError):
                save_sector_daily(SOURCE, DATE, snapshot=snapshot(), full_html_path=full)
            self.assertEqual(output.read_text(), '历史板块页')

    def test_current_official_page_is_not_overwritten_even_with_publication_origin(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        today = datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat()
        with TemporaryDirectory() as folder:
            full = Path(folder) / f'{today}_A股日报_完整版.html'
            output = sector_daily_output_path(full)
            output.write_text('first publication')
            with self.assertRaises(ValueError):
                save_sector_daily(None, today, snapshot={'date': today, 'data': {}},
                                  full_html_path=full, origin='as_of_report')
            self.assertEqual(output.read_text(), 'first publication')

    def test_competing_official_publication_is_never_replaced(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        today = datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat()
        with TemporaryDirectory() as folder:
            full = Path(folder) / f'{today}_A股日报_完整版.html'
            output = sector_daily_output_path(full)

            def competing_render(*args, **kwargs):
                output.write_text('competing publication')
                return 'this attempt'

            with patch('report.sector_daily_report.render_sector_daily', side_effect=competing_render), self.assertRaises(ValueError):
                save_sector_daily(None, today, snapshot={'date': today, 'data': {}},
                                  full_html_path=full, origin='as_of_report')
            self.assertEqual(output.read_text(), 'competing publication')
            self.assertFalse(list(Path(folder).glob('*.tmp')))

    def test_entry_helper_uses_frozen_runtime_data_and_report_directory(self):
        import daily_report_entry_demo as entry
        with TemporaryDirectory() as folder:
            full = Path(folder) / 'replay' / f'{DATE}_A股日报_完整版_replay.md'
            value = snapshot()['data']
            before = deepcopy(value)
            path = entry._save_sector_daily_reading_page(value, DATE, source_html=SOURCE,
                        saved_report_paths={entry.REPORT_VARIANT_FULL: str(full)})
            self.assertEqual(path, full.with_name(f'{DATE}_A股日报_板块日报_replay.html'))
            self.assertEqual(value, before)
            self.assertIn('全国地产', path.read_text())
            with self.assertRaises(entry.ReportCriticalDataMissingError):
                entry._save_sector_daily_reading_page(value, DATE, source_html='<html></html>',
                    saved_report_paths={entry.REPORT_VARIANT_FULL: str(full)})

    def test_entry_save_hook_creates_reading_page_without_research(self):
        import daily_report_entry_demo as entry
        with TemporaryDirectory() as folder:
            full = Path(folder) / f'{DATE}_A股日报_完整版.md'
            value = snapshot()
            before = deepcopy(value)
            result = entry._try_save_daily_report_html_from_saved_markdown(
                DATE, saved_report_paths={entry.REPORT_VARIANT_FULL: str(full)}, html_text=SOURCE, sector_snapshot=value)
            self.assertEqual(result, full.with_suffix('.html'))
            self.assertEqual(value, before)
            self.assertEqual(result.read_text(), SOURCE)
            self.assertEqual(set(Path(folder).glob('*.html')), {result, sector_daily_output_path(result)})
            self.assertFalse((Path(folder) / 'data').exists())

    def test_entry_save_hook_rejects_wrong_snapshot_before_writing(self):
        import daily_report_entry_demo as entry
        with TemporaryDirectory() as folder:
            full = Path(folder) / f'{DATE}_A股日报_完整版.md'
            value = snapshot()
            value['date'] = '2026-09-30'
            with self.assertRaises(entry.ReportCriticalDataMissingError):
                entry._try_save_daily_report_html_from_saved_markdown(
                    DATE, saved_report_paths={entry.REPORT_VARIANT_FULL: str(full)}, html_text=SOURCE, sector_snapshot=value)
            self.assertFalse(full.with_suffix('.html').exists())


if __name__ == '__main__':
    unittest.main()
