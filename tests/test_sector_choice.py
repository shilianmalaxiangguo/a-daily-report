"""Dated choices compare persistence, not each day's biggest jump."""
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from report.sector_choice import build_sector_choice, validate_sector_choice
from report.sector_reading_sources import build_index_view
from report.sector_reading_history import evidence_hash
from report.sector_member_comparison import build_member_comparison
from report.sector_choice import render_sector_choice
from bs4 import BeautifulSoup


def sample():
    days = [(date(2026, 9, 1) + timedelta(days=i)).isoformat() for i in range(25)]
    meta = {'886001.TI': {'name': '延续方向', 'exchange': 'A', 'type': 'N'},
            '886002.TI': {'name': '今日跳升', 'exchange': 'A', 'type': 'N'}}
    rows = []
    for code in meta:
        changes = [1.] * 25 if code == '886001.TI' else [-1.] * 24 + [8.]
        close = 100
        for d, change in zip(days, changes):
            close *= 1 + change/100
            rows.append({'ts_code': code, 'trade_date': d, 'close': close, 'pct_change': change})
    view = build_index_view(rows, meta, [{'date': d, 'close': 100} for d in days], days[-1],
                            trade_dates=days, index_type='N')
    assets = {'target_date': days[-1], 'trend': view}
    assets['source_sha256'] = evidence_hash(assets)
    return days, {'sector_universe': 'concept', 'reading_sector_history': assets}


def with_members(data, days, *, broad=True):
    changes = {'000001.SZ': [2.] * 6, '000002.SZ': [10.] * 5 + [-1.],
               '000003.SZ': [1.5 if broad else -1.] * 6}
    members = {'index:886001.TI': {'name': '延续方向', 'index_code': '886001.TI', 'members': [
        {'ts_code': '886001.TI', 'con_code': code, 'con_name': '<'+code+'>'} for code in changes]}}
    rows = [{'code': code, 'date': day, 'change_pct': change, 'turnover_yi': 10}
            for code, values in changes.items() for day, change in zip(days[-6:], values)]
    data['reading_sector_history']['trend']['member_comparison'] = build_member_comparison(
        days[-1], days[-6:], members, rows, retrieved_at='2026-10-27T11:00:00+08:00')
    return data


class SectorChoiceTest(unittest.TestCase):
    def test_today_winner_does_not_replace_persistent_direction(self):
        days, data = sample()
        result = build_sector_choice(data, days[-1])
        self.assertEqual(result['primary']['track_id'], 'index:886001.TI')
        self.assertEqual(result['today_leader']['track_id'], 'index:886002.TI')
        self.assertEqual(result['continuity']['kind'], 'baseline')
        self.assertIsNone(result['stock'])
        self.assertIn('未核实', result['limitations'][0])
        self.assertEqual(validate_sector_choice(result, data, days[-1]), result)

    def test_previous_attention_is_kept_not_reselected_by_rank(self):
        days, data = sample()
        prior = build_sector_choice(data, days[-1])
        prior['target_date'] = days[-2]
        prior['primary']['track_id'] = 'index:886001.TI'
        prior['artifact_hash'] = evidence_hash({k: v for k, v in prior.items() if k != 'artifact_hash'})
        result = build_sector_choice(data, days[-1], previous=prior)
        self.assertEqual(result['continuity']['kind'], 'continue')
        self.assertEqual(result['primary']['track_id'], prior['primary']['track_id'])
        self.assertNotIn('position', result)

    def test_missing_previous_price_does_not_silently_switch(self):
        days, data = sample()
        prior = build_sector_choice(data, days[-1])
        prior['target_date'] = days[-2]
        prior['primary']['track_id'] = 'index:886999.TI'
        prior['artifact_hash'] = evidence_hash({k: v for k, v in prior.items() if k != 'artifact_hash'})
        result = build_sector_choice(data, days[-1], previous=prior)
        self.assertEqual(result['continuity']['kind'], 'unresolved')
        self.assertIn('缺', result['continuity']['reason'])
        self.assertIsNone(result['primary'])
        self.assertIsNone(result['stock'])
        self.assertTrue(result['alternatives'])
        page = render_sector_choice(BeautifulSoup('', 'html.parser'), result)
        self.assertNotIn('板块优先比较', page.get_text())
        self.assertIn('新方向仅作对照', page.get_text())

    def test_unverified_calendar_cannot_be_called_trading_day_persistence(self):
        days, data = sample()
        data['reading_sector_history']['trend']['calendar_verified'] = False
        with self.assertRaises(ValueError): build_sector_choice(data, days[-1])

    def test_no_positive_persistence_is_not_a_forced_stock_or_account_decision(self):
        days, data = sample()
        view = data['reading_sector_history']['trend']
        inputs = view['price_inputs']
        for row in inputs['rows']: row['pct_change'] = -1.
        replacement = build_index_view(inputs['rows'], inputs['metadata'], inputs['market_bars'], days[-1],
                                        trade_dates=days, index_type='N')
        data['reading_sector_history']['trend'] = replacement
        result = build_sector_choice(data, days[-1])
        self.assertIsNone(result['primary'])
        self.assertIsNone(result['stock'])
        self.assertNotIn('不参与', result['participation'])

    def test_missing_target_prices_show_missing_facts_not_market_interpretation(self):
        days, data = sample()
        inputs = data['reading_sector_history']['trend']['price_inputs']
        data['reading_sector_history']['trend'] = build_index_view(
            [row for row in inputs['rows'] if row['trade_date'] != days[-1]],
            inputs['metadata'], inputs['market_bars'], days[-1], trade_dates=days, index_type='N')
        result = build_sector_choice(data, days[-1])
        self.assertEqual(result['daily'][-1]['valid'], 0)
        before = deepcopy(result)
        page = render_sector_choice(BeautifulSoup('', 'html.parser'), result)
        text = page.get_text()
        self.assertIn(days[-1] + '的概念指数行情未取得', text)
        for claim in ('日间强势方向更替明显', '分化，未见概念指数普遍上涨',
                      '0/0', '未找到两窗', '为什么不是每天换热点', '推翻当前倾向'):
            self.assertNotIn(claim, text)
        self.assertIsNone(page.select_one('[data-choice-track]'))
        self.assertEqual(result, before)

    def test_valid_declining_prices_keep_the_actual_market_interpretation(self):
        days, data = sample()
        inputs = data['reading_sector_history']['trend']['price_inputs']
        for row in inputs['rows']:
            row['pct_change'] = -1.
        data['reading_sector_history']['trend'] = build_index_view(
            inputs['rows'], inputs['metadata'], inputs['market_bars'], days[-1],
            trade_dates=days, index_type='N')
        result = build_sector_choice(data, days[-1])
        page = render_sector_choice(BeautifulSoup('', 'html.parser'), result)
        self.assertIn('分化，未见概念指数普遍上涨', page.get_text())
        self.assertIn('0/2个有效概念指数上涨', page.get_text())
        self.assertNotIn('的概念指数行情未取得', page.get_text())

    def test_rehashed_choice_cannot_override_frozen_facts(self):
        days, data = sample()
        result = build_sector_choice(data, days[-1])
        result['primary']['five_day_pct'] += 100
        result['artifact_hash'] = evidence_hash({k: v for k, v in result.items() if k != 'artifact_hash'})
        with self.assertRaises(ValueError): validate_sector_choice(result, data, days[-1])

    def test_daily_outperformance_prefers_continuing_strength_not_the_biggest_old_winner(self):
        days, data = sample()
        with_members(data, days)
        result = build_sector_choice(data, days[-1])
        self.assertEqual(result['stock']['code'], '000001.SZ')
        self.assertEqual(result['stock']['outperform_days'], 5)
        self.assertEqual(result['stock']['trailing_outperform_days'], 5)
        self.assertGreater(result['member_summary']['median_without_top_pct'], 0)
        self.assertEqual(result['member_summary']['query_date'], '2026-10-27')
        self.assertEqual(result['member_summary']['basis'], 'latest_at_query')
        self.assertIn('已覆盖样本', result['participation'])
        self.assertEqual(validate_sector_choice(result, data, days[-1]), result)

    def test_one_winner_does_not_create_a_broad_member_claim(self):
        days, data = sample()
        with_members(data, days, broad=False)
        result = build_sector_choice(data, days[-1])
        summary = result['member_summary']
        self.assertEqual(summary['positive'], 2)
        # Removing the one largest past winner still uses the other actual returns.
        self.assertAlmostEqual(summary['median_without_top_pct'], ((1.02**5-1)+(0.99**5-1))*50)
        self.assertIn('不是目标日当时可知', result['limitations'][1])

    def test_invalid_previous_direction_is_reconsidered_not_inherited_as_a_position(self):
        days, data = sample()
        prior = build_sector_choice(data, days[-1])
        prior['target_date'] = days[-2]
        prior['primary'] = {'track_id': 'index:886002.TI', 'name': '今日跳升'}
        prior['artifact_hash'] = evidence_hash({k: v for k, v in prior.items() if k != 'artifact_hash'})
        result = build_sector_choice(data, days[-1], previous=prior)
        self.assertEqual(result['continuity']['kind'], 'replace')
        self.assertIn('不自动形成', result['continuity']['reason'])
        self.assertEqual(result['primary']['track_id'], 'index:886001.TI')

    def test_later_replay_is_labeled_and_html_names_are_escaped(self):
        days, data = sample()
        with_members(data, days)
        result = build_sector_choice(data, days[-1])
        soup = BeautifulSoup('', 'html.parser')
        page = render_sector_choice(soup, result)
        self.assertIn('历史修订不是当时作出的预测', page.get_text())
        self.assertIn('不是已识别alpha', page.get_text())
        self.assertIn('去掉5日涨幅最高的一只后，其余成员的中间涨幅', page.get_text())
        self.assertIn('不是指数贡献分解', page.get_text())
        self.assertNotIn('赢家', page.get_text())
        self.assertIn('<000001.SZ>', page.get_text())
        self.assertIsNone(page.find('000001.sz'))
        self.assertIsNone(page.select_one('details[open]'))
        self.assertEqual(page.select_one('[data-choice-track]')['data-choice-track'], 'index:886001.TI')

    def test_search_date_controls_omit_empty_breadth_and_keep_original_view(self):
        from report.sector_reading_history import render_numeric_trend
        days, data = sample()
        raw = data['reading_sector_history']['trend']
        before = deepcopy(raw)
        soup = BeautifulSoup('', 'html.parser')
        page = render_numeric_trend(soup, raw, days[-1], preferred_track_id='index:886002.TI')
        for identity in ('trend-sector-search', 'trend-search-results', 'trend-date-range',
                         'trend-date-previous', 'trend-date-next'):
            self.assertIsNotNone(page.select_one('#'+identity))
        self.assertIsNone(page.select_one('#sector-trend-breadth'))
        self.assertIsNone(page.select_one('#trend-fact-breadth, #trend-fact-five_day_breadth'))
        self.assertTrue(page.select_one('#sector-trend-selector').has_attr('hidden'))
        self.assertEqual(page.select_one('#sector-trend-selector option[selected]')['value'], 'index:886002.TI')
        self.assertEqual(raw, before)

    def test_gap_copy_keeps_the_fact_without_technical_exception_suffix(self):
        from report.sector_reading_content import source_note_text
        raw = '缺少有效topdays因子（ValueError）；其余日期保留'
        self.assertEqual(source_note_text(raw), '缺少有效topdays因子；其余日期保留')
        self.assertIn('ValueError', raw)
        for name in ('Exception', 'Error', 'ReadTimeout'):
            self.assertEqual(source_note_text('来源未取得（'+name+'）；保留缺口'), '来源未取得；保留缺口')
        self.assertEqual(source_note_text('2026-10-26（尚未查到）'), '2026-10-26（尚未查到）')

    def test_duplicate_sector_identity_is_text_not_markup(self):
        from report.sector_reading_history import render_numeric_trend
        days, data = sample()
        raw = data['reading_sector_history']['trend']
        raw.pop('price_inputs')
        original = raw['tracks'][0]['track_id']
        malicious = 'index:</small><img src=x onerror="alert(1)">'

        def replace(value):
            if isinstance(value, dict):
                return {key: replace(item) for key, item in value.items()}
            if isinstance(value, list):
                return [replace(item) for item in value]
            return malicious if value == original else value

        raw = replace(raw)
        for track in raw['tracks']:
            track['name'] = '同名板块'
        page = BeautifulSoup(str(render_numeric_trend(BeautifulSoup('', 'html.parser'), raw, days[-1])), 'html.parser')
        self.assertIsNone(page.find('img'))
        button = next(b for b in page.select('[data-trend-sector]') if b['data-trend-sector'] == malicious)
        self.assertIn(malicious.removeprefix('index:'), button.get_text())


if __name__ == '__main__':
    unittest.main()
