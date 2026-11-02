from copy import deepcopy
from datetime import date, timedelta
import sys
import json
import subprocess
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from report.sector_member_comparison import build_member_comparison, collect_member_comparison, validate_member_comparison

DAYS = [(date(2026, 10, 15) + timedelta(days=i)).isoformat() for i in range(6)]
TARGET = DAYS[-1]


def sample():
    members = {'index:881277.TI': {'name': '<电机>', 'index_code': '881277.TI', 'members': [
        {'ts_code': '881277.TI', 'con_code': '000001.SZ', 'con_name': '<甲>'},
        {'ts_code': '881277.TI', 'con_code': '000002.SZ', 'con_name': '乙'},
    ]}}
    rows = [{'code': code, 'date': day, 'change_pct': 10 if code == '000001.SZ' else -1,
             'turnover_yi': (6 if day == TARGET else 2) if code == '000001.SZ' else 10}
            for code in ('000001.SZ', '000002.SZ') for day in DAYS]
    return members, rows


class SectorMemberComparisonTest(unittest.TestCase):
    def build(self, members=None, rows=None, days=DAYS):
        original_members, original_rows = sample()
        return build_member_comparison(TARGET, days, members if members is not None else original_members,
                                       rows if rows is not None else original_rows,
                                       retrieved_at='2026-10-23T02:00:00+08:00')

    def test_compounds_five_sessions_and_keeps_both_boards_and_prior_average(self):
        payload = self.build()
        sector = payload['sectors']['index:881277.TI']
        self.assertEqual(sector['gain_codes'], ['000001.SZ', '000002.SZ'])
        self.assertEqual(sector['amount_codes'], ['000002.SZ', '000001.SZ'])
        first = sector['rows'][0]
        self.assertAlmostEqual(first['five_day_pct'], (1.1 ** 5 - 1) * 100)
        self.assertEqual(first['activity_ratio'], 3)
        self.assertEqual(payload['membership_basis'], 'latest_at_query')
        self.assertEqual(payload['query_date'], '2026-10-23')
        validate_member_comparison(payload, TARGET)

    def test_preserves_raw_price_pair_and_rejects_mismatched_derived_change(self):
        members, rows = sample()
        priced = []
        for row in rows:
            previous = 10.0
            close = 11.0 if row['code'] == '000001.SZ' else 9.9
            priced.append({**row, 'close': close, 'pre_close': previous})
        payload = self.build(members, priced)
        stored = payload['daily_rows'][0]
        self.assertEqual(stored['close'], 11.0 if stored['code'] == '000001.SZ' else 9.9)
        self.assertEqual(stored['pre_close'], 10.0)
        validate_member_comparison(payload, TARGET)

        bad = [dict(row) for row in priced]
        bad[0]['close'] = 12.0
        with self.assertRaisesRegex(ValueError, '原始价格与涨跌不一致'):
            self.build(members, bad)

    def test_partial_raw_price_pair_keeps_other_members_and_turnover(self):
        members, rows = sample()
        view = {'target_date': TARGET, 'chart_selection': {'comparison': [{'track_id': 'index:881277.TI'}]},
                'tracks': [{'track_id': 'index:881277.TI', 'name': '样本'}]}
        for missing in (None, 0, float('nan')):
            with self.subTest(missing=missing):
                def daily(day):
                    return [{'ts_code': code, 'trade_date': day, 'close': 11,
                             'pre_close': missing if code == '000001.SZ' and day == TARGET else 10,
                             'amount': 100000}
                            for code in ('000001.SZ', '000002.SZ')]
                with patch('report.sector_reading_history.numeric_trend_view', return_value=view), \
                     patch('market_data.tushare_market_activity_service.fetch_tushare_open_trade_dates', return_value=DAYS):
                    value = collect_member_comparison(None, view, retrieved_at='2026-10-23T02:00:00+08:00',
                        member_fetcher=lambda code: members['index:' + code]['members'], daily_fetcher=daily)
                sector = value['sectors']['index:881277.TI']
                self.assertEqual(sector['coverage'], {'five_day': 1, 'amount': 2})
                self.assertEqual(sector['member_count'], 2)
                stock = next(r for r in sector['rows'] if r['code'] == '000001.SZ')
                self.assertIsNone(stock['five_day_pct'])
                self.assertIsNone(stock['change_pct'])
                self.assertEqual(stock['turnover_yi'], 1)
                saved = next(r for r in value['daily_rows'] if r['code'] == '000001.SZ' and r['date'] == TARGET)
                self.assertIsNone(saved['pre_close'])
                self.assertEqual(saved['close'], 11)
                validate_member_comparison(value, TARGET)

        priced = [{**r, 'close': 11, 'pre_close': 10, 'change_pct': 10} for r in rows]
        priced[0]['pre_close'] = None
        with self.assertRaisesRegex(ValueError, '原始价格'):
            self.build(members, priced)

    def test_reference_previous_price_is_not_replaced_by_previous_unadjusted_close(self):
        members, rows = sample()
        for row in rows:
            if row['code'] != '000001.SZ':
                continue
            close, previous = (2.76, 2.78) if row['date'] == TARGET else (2.81, 2.81)
            row.update(close=close, pre_close=previous, change_pct=(close - previous) / previous * 100)
        payload = self.build(members, rows)
        stock = next(r for r in payload['sectors']['index:881277.TI']['rows'] if r['code'] == '000001.SZ')
        self.assertAlmostEqual(stock['five_day_pct'], (2.76 / 2.78 - 1) * 100)
        self.assertNotAlmostEqual(stock['five_day_pct'], (2.76 / 2.81 - 1) * 100)
        validate_member_comparison(payload, TARGET)

    def test_missing_session_excludes_gain_but_keeps_target_amount(self):
        members, rows = sample()
        rows = [r for r in rows if not (r['code'] == '000001.SZ' and r['date'] == DAYS[2])]
        sector = self.build(members, rows)['sectors']['index:881277.TI']
        self.assertEqual(sector['gain_codes'], ['000002.SZ'])
        self.assertEqual(len(sector['amount_codes']), 2)
        self.assertIsNone(sector['rows'][0]['five_day_pct'])
        self.assertIsNone(sector['rows'][0]['activity_ratio'])
        self.assertEqual(sector['coverage']['five_day'], 1)
        self.assertEqual(sector['member_count'], 2)

    def test_proved_delisting_before_window_is_not_missing_daily_prices(self):
        members, rows = sample()
        rows = [r for r in rows if r['code'] != '000001.SZ']
        evidence = {'source': 'tushare.stock_basic', 'retrieved_at': '2026-10-23T02:00:00+08:00',
                    'rows': [{'ts_code': '000001.SZ', 'name': '甲退', 'list_status': 'D',
                              'list_date': '20000101', 'delist_date': '20260714'}]}
        value = build_member_comparison(TARGET, DAYS, members, rows,
            retrieved_at='2026-10-23T02:00:00+08:00', listing_evidence=evidence)
        sector = value['sectors']['index:881277.TI']
        self.assertEqual((sector['coverage']['five_day'], sector['member_count']), (1, 1))
        self.assertEqual(sector['directory_member_count'], 2)
        self.assertEqual(sector['excluded_members'][0]['delist_date'], '2026-07-14')
        self.assertEqual(len(value['memberships']['index:881277.TI']['members']), 2)
        validate_member_comparison(value, TARGET)
        evidence['rows'][0]['delist_date'] = '20261016'
        later = build_member_comparison(TARGET, DAYS, members, rows,
            retrieved_at='2026-10-23T02:00:00+08:00', listing_evidence=evidence)
        self.assertEqual(later['sectors']['index:881277.TI']['member_count'], 2)
        evidence['rows'][0]['delist_date'] = '20260714'
        with self.assertRaisesRegex(ValueError, '冲突'):
            build_member_comparison(TARGET, DAYS, members, sample()[1],
                retrieved_at='2026-10-23T02:00:00+08:00', listing_evidence=evidence)

    def test_foreign_members_and_conflicting_daily_rows_are_rejected(self):
        members, rows = sample()
        members['index:881277.TI']['members'][0]['ts_code'] = '885800.TI'
        with self.assertRaisesRegex(ValueError, '成分'):
            self.build(members, rows)
        members, rows = sample()
        rows.append(dict(rows[0], change_pct=99))
        with self.assertRaisesRegex(ValueError, '冲突'):
            self.build(members, rows)

    def test_collection_checks_only_completely_absent_members_and_preserves_failed_checks(self):
        members, rows = sample()
        view = {'target_date': TARGET, 'chart_selection': {'comparison': [{'track_id': 'index:881277.TI'}]},
                'tracks': [{'track_id': 'index:881277.TI', 'name': '样本'}]}
        valid = {'ts_code': '000001.SZ', 'list_status': 'D', 'list_date': '20000101', 'delist_date': '20260714'}
        for answer in ([valid], [], [dict(valid, list_status='L')],
                       [dict(valid, ts_code='000003.SZ')], [dict(valid, delist_date='20990101')], RuntimeError('不可用')):
            with self.subTest(answer=answer):
                check = Mock(side_effect=answer) if isinstance(answer, Exception) else Mock(return_value=answer)
                daily = lambda day: [{'ts_code': '000002.SZ', 'trade_date': day, 'close': 10, 'pre_close': 9,
                                      'amount': 100000}]
                with patch('report.sector_reading_history.numeric_trend_view', return_value=view), \
                     patch('market_data.tushare_market_activity_service.fetch_tushare_open_trade_dates', return_value=DAYS):
                    value = collect_member_comparison(None, view, retrieved_at='2026-10-23T02:00:00+08:00',
                        member_fetcher=lambda code: members['index:' + code]['members'],
                        daily_fetcher=daily, listing_fetcher=check)
                check.assert_called_once_with('000001.SZ')
                sector = value['sectors']['index:881277.TI']
                self.assertEqual(sector['member_count'], 1 if answer == [valid] else 2)
                self.assertEqual(len(value['memberships']['index:881277.TI']['members']), 2)
                validate_member_comparison(value, TARGET)

    def test_future_price_and_short_calendar_do_not_become_complete_returns(self):
        members, rows = sample()
        with self.assertRaisesRegex(ValueError, '日期'):
            self.build(members, rows + [dict(rows[0], date='2026-10-21')])
        rows = [r for r in rows if r['date'] in DAYS[-4:]]
        sector = self.build(members, rows, DAYS[-4:])['sectors']['index:881277.TI']
        self.assertEqual(sector['gain_codes'], [])
        self.assertEqual(len(sector['amount_codes']), 2)

    def test_projection_and_fingerprint_are_verified_without_mutation(self):
        from report.sector_reading_history import evidence_hash
        payload = self.build()
        original = deepcopy(payload)
        validate_member_comparison(payload, TARGET)
        self.assertEqual(payload, original)
        payload['sectors']['index:881277.TI']['rows'][0]['five_day_pct'] = 999
        payload['artifact_hash'] = evidence_hash({k: v for k, v in payload.items() if k != 'artifact_hash'})
        with self.assertRaisesRegex(ValueError, '投影'):
            validate_member_comparison(payload, TARGET)

    def test_empty_members_and_unavailable_amounts_are_not_zero_rankings(self):
        members, rows = sample()
        members['index:881277.TI']['members'] = []
        sector = self.build(members, rows)['sectors']['index:881277.TI']
        self.assertEqual(sector['member_count'], 0)
        self.assertEqual(sector['amount_codes'], [])
        members, rows = sample()
        for row in rows:
            row['turnover_yi'] = None
        sector = self.build(members, rows)['sectors']['index:881277.TI']
        self.assertEqual(sector['amount_codes'], [])
        self.assertTrue(all(r['activity_ratio'] is None for r in sector['rows']))

    def test_current_monthly_hover_is_focused_and_keeps_member_facts_out_of_the_tooltip(self):
        from bs4 import BeautifulSoup
        from report.sector_reading_sources import build_index_view
        from report.sector_reading_history import render_numeric_trend
        from tests.test_sector_trend_tracking import SectorTrendTest
        view = build_index_view(
            [{'ts_code': '881277.TI', 'trade_date': day, 'close': 100 + i, 'pct_change': 1}
             for i, day in enumerate(DAYS)],
            {'881277.TI': {'name': '<电机>', 'type': 'I', 'exchange': 'A'}},
            [{'date': day, 'close': 100} for day in DAYS], TARGET, trade_dates=DAYS)
        view['member_comparison'] = self.build()
        page = render_numeric_trend(BeautifulSoup('', 'html.parser'), view, TARGET)
        adapter = SectorTrendTest()
        result = adapter.chart_options(page, [
            {'tooltip': 'sector-trend-comparison', 'series': 0, 'index': 1},
            {'chart': 'sector-trend-comparison', 'event': {
                'componentType': 'series', 'seriesId': 'index:881277.TI', 'name': DAYS[1]}},
        ])
        tip = BeautifulSoup(result['tooltips'][0], 'html.parser')
        self.assertIsNone(tip.find('甲'))
        self.assertNotIn('<甲>', tip.get_text())
        self.assertIn('<电机>', tip.get_text())
        self.assertIn('相对全A累计差值', tip.get_text())
        self.assertNotIn('memberHTML', result)
        self.assertIsNone(page.select_one('#trend-member-panel, #trend-full-facts'))
        stored = json.loads(page.select_one('#sector-trend-view').string)['member_comparison']
        original = self.build()
        self.assertNotIn('daily_rows', stored)
        self.assertNotIn('memberships', stored)
        for identity, sector in stored['sectors'].items():
            source = original['sectors'][identity]
            codes = set(source['gain_codes']) | set(source['amount_codes'])
            self.assertEqual(sector['rows'], [r for r in source['rows'] if r['code'] in codes])
            self.assertEqual(sector['coverage'], source['coverage'])
        self.assertEqual(view['member_comparison'], original)
        self.assertEqual(stored['query_date'], '2026-10-23')
        self.assertNotIn('dataZoom', result['charts']['sector-trend-price'])
        self.assertEqual(result['date'], DAYS[1])

    def test_return_colors_follow_their_own_period_and_zero_missing_are_neutral(self):
        from bs4 import BeautifulSoup
        script = (Path(__file__).resolve().parents[1] / 'scripts/templates/sector_trend_charts.js').read_text()
        script = script.split('const initFacts =')[0] + '\nglobalThis.memberMarkup=memberMarkup;})();'
        sector = {'name': '样本', 'member_count': 4, 'coverage': {'five_day': 4, 'amount': 4},
                  'gain_codes': list('abcd'), 'amount_codes': list('abcd'), 'rows': [
                      {'code': code, 'name': '<' + code + '>', 'five_day_pct': five,
                       'change_pct': daily, 'turnover_yi': 1, 'activity_ratio': 2}
                      for code, five, daily in [('a', 10, -1), ('b', -2, 3), ('c', 0, 0), ('d', None, None)]]}
        data = {'member_comparison': {'target_date': TARGET, 'query_date': '2026-10-23',
                                     'notes': [], 'sectors': {'s': sector}}}
        program = "const vm=require('vm'),fs=require('fs'),d=JSON.parse(fs.readFileSync(0,'utf8'));vm.runInThisContext(d.script);console.log(memberMarkup(d.data,'s',d.day,true));"
        output = subprocess.run(['node', '-e', program], input=json.dumps({'script': script, 'data': data, 'day': TARGET}),
                                capture_output=True, text=True, check=True).stdout
        rows = BeautifulSoup(output, 'html.parser').select('tbody tr')[:4]
        self.assertEqual([[n['data-return-sign'] for n in row.select('span[data-return-sign]')] for row in rows],
                         [['down', 'up', 'down'], ['up', 'down', 'up'], ['flat'] * 3, ['missing'] * 3])
        self.assertTrue(all(not row.select('td')[3].select('span') for row in rows))
        self.assertIn('&lt;a&gt;', output)
