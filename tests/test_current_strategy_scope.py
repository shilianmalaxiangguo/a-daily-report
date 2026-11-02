"""当前日报仅使用小盘轮换；历史材料不能恢复旧买卖建议。"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import numpy as np
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from report.daily_extras import collect_extras
from report.sector_daily_report import render_sector_daily
from report.small_cap_rotation import ACCOUNT_FEE, account_orders, average_turnover, bought, build_plan, growth_records
from tests.test_sector_daily_report import DATE, SOURCE, snapshot
from tests.test_small_cap_plan import calendar_through, fina, world


class CurrentStrategyTest(unittest.TestCase):
    def test_current_desktop_styles_do_not_restore_phone_breakpoints(self):
        style = (Path(__file__).resolve().parents[1] / 'scripts/templates/daily_report_reading.css').read_text()
        self.assertNotRegex(style, r'@media\s*\([^)]*(?:max-width|width\s*<)')
        self.assertIn('@media print', style)
        self.assertIn('prefers-reduced-motion', style)
        templates = Path(__file__).resolve().parents[1] / 'scripts/templates'
        for name in ('sector_reading_charts.js', 'sector_daily_visuals.js'):
            script = (templates / name).read_text()
            self.assertNotIn('narrow', script, name)
            self.assertNotRegex(script, r'clientWidth\s*<\s*480', name)
        soup = BeautifulSoup(render_sector_daily(SOURCE, DATE, snapshot=snapshot()), 'html.parser')
        self.assertFalse(soup.select('[class*="table-stacked"]'))

    def test_commission_has_no_five_yuan_minimum(self):
        self.assertAlmostEqual(ACCOUNT_FEE, 0.0001 + 0.00001)
        orders, skipped, cash = account_orders([{'code': 'A', 'name': '样例'}], lambda _: 10.0, cash=1001.0, names=1)
        self.assertEqual(orders[0]['lots'], 1)
        self.assertEqual(skipped, [])
        self.assertAlmostEqual(1001.0 - cash - orders[0]['amount'], 0.11)

    def test_missing_turnover_does_not_become_the_coldest_stock(self):
        amount = np.array([[np.nan] * 25, [2.0] * 25])
        mean = average_turnover(amount)
        self.assertTrue(np.isnan(mean[0]).all())
        self.assertEqual(mean[1, -1], 2.0)

    def test_missing_financials_remain_a_data_gap(self):
        _, value = world(DATE)
        plan, reason = build_plan(value, DATE, sessions=calendar_through(DATE), records={}, chinext={})
        self.assertIsNone(plan)
        self.assertIn('财报增长数据缺失', reason)

    def test_only_three_backups_but_the_pool_remains_complete(self):
        h = {key: np.ones((12, 2)) for key in ('open', 'close', 'pre')}
        h['limit'] = np.full(12, 10.0)
        h['open'][:5, 1] = 1.1
        ranked = [(i, None) for i in range(12)]
        self.assertEqual(bought(h, ranked, 0), [5, 6, 7])
        self.assertEqual(bought(h, ranked, 0, names=None), list(range(5, 12)))

    def test_small_cap_collection_does_not_require_the_old_board(self):
        data = {'reading_market_returns': {'trade_dates': [DATE]}}
        with patch('report.daily_extras.reading_core', side_effect=AssertionError('旧判断不应运行')), \
                patch('report.daily_extras.history_backtest', side_effect=AssertionError('旧回测不应日更')), \
                patch('report.small_cap_rotation.load_inputs', return_value=([DATE], {}, {})), \
                patch('report.small_cap_rotation.load_index', return_value={}), \
                patch('report.small_cap_rotation.build_plan', return_value=({'target_date': DATE}, None)) as build:
            collect_extras(data, DATE)
        self.assertEqual(data['reading_small_cap_plan'], {'target_date': DATE})
        self.assertTrue(build.called)
        for key in ('reading_backtest', 'reading_decision_record', 'reading_interpretation'):
            self.assertNotIn(key, data)

    def test_old_frozen_suggestions_do_not_return_when_the_plan_is_missing(self):
        data = snapshot()
        data['data'].update(reading_interpretation={'headline': '旧建议'}, reading_backtest={'old': True},
                            reading_decision_history={'old': True})
        data['data']['reading_market_returns'] = world(DATE)[1]
        before = deepcopy(data)
        with patch('report.decision_board.build_decision_board', side_effect=AssertionError('旧建议不应重建')):
            soup = BeautifulSoup(render_sector_daily(SOURCE, DATE, snapshot=data), 'html.parser')
        self.assertEqual(data, before)
        self.assertIn('小盘计划尚缺', soup.select_one('#daily-plan').get_text())
        self.assertFalse(soup.select('#daily-decision, #daily-pk, #daily-candidates, #daily-ledger, #daily-alphabeta, #daily-backtest'))
        self.assertIsNotNone(soup.select_one('#daily-sectors'))

    def test_plan_displays_without_any_market_regime_or_legacy_record(self):
        _, value = world(DATE)
        plan, reason = build_plan(value, DATE, sessions=calendar_through(DATE), records=growth_records(fina(DATE)), chinext={})
        self.assertIsNone(reason)
        data = snapshot()
        data['data']['reading_small_cap_plan'] = plan
        before = deepcopy(data)
        soup = BeautifulSoup(render_sector_daily(SOURCE, DATE, snapshot=data), 'html.parser')
        self.assertEqual(data, before)
        self.assertEqual(soup.select('.daily-nav-links a')[0]['href'], '#daily-plan')
        text = soup.select_one('#daily-plan').get_text(' ', strip=True)
        self.assertIn('小盘轮换', text)
        self.assertIn('单期模拟', text)
        self.assertIn('未承接上期', text)
        self.assertIn('佣金为成交额0.01%，无最低收费', text)
        self.assertNotIn('本期实际买入', text)
        self.assertNotIn('实际记账', text)
        self.assertNotIn('规则信号', soup.get_text())
        for link in soup.select('.daily-nav a'):
            self.assertIsNotNone(soup.select_one(link['href']))


if __name__ == '__main__':
    unittest.main()
