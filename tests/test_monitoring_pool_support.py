import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))


class MonitoringPoolSupportTest(unittest.TestCase):
    def _load_module(self):
        try:
            return __import__('report.monitoring_pool_support', fromlist=['monitoring_pool_support'])
        except ModuleNotFoundError as error:
            self.fail(f'report.monitoring_pool_support should exist: {error}')

    def test_build_monitoring_row_computes_ohlc_shape_volume_and_returns(self):
        support = self._load_module()

        row = support.build_monitoring_row(
            {
                'date': '2026-04-16',
                'open': 86.66,
                'high': 91.66,
                'low': 86.16,
                'close': 90.88,
                'volume': 107134.10,
            },
            previous_bar={
                'date': '2026-04-15',
                'close': 86.92,
                'volume': 91552.05,
            },
            selected_next_day_close=88.63,
            day_index=5,
        )

        self.assertEqual(row['date'], '2026-04-16')
        self.assertEqual(row['candle_shape'], '大阳柱')
        self.assertEqual(row['volume_state'], '放量')
        self.assertEqual(row['trading_days_since_selected'], 5)
        self.assertAlmostEqual(row['daily_change_pct'], 4.5564, places=3)
        self.assertAlmostEqual(row['cum_change_pct_from_next_day'], 2.5386, places=3)
        self.assertGreater(row['close_position_in_range'], 0.8)



    def test_collect_monitoring_pool_candidates_splits_main_and_secondary_sources(self):
        support = self._load_module()

        result = support.collect_monitoring_pool_candidates(
            {
                'core_stocks': [{'name': '博杰股份', 'code': '002975'}],
                'secondary_stocks': [{'name': '龙蟠科技', 'code': '603906'}],
                'crossline_observation_stocks': [{'name': '石大胜华', 'code': '603026'}],
                'gem_observation_stocks': [{'name': '中嘉博创', 'code': '000889'}],
                'generic_watch_stocks': [{'name': '津药药业', 'code': '600488'}],
            }
        )

        self.assertEqual([item['stock_code'] for item in result['main_pool']], ['002975', '603906'])
        self.assertEqual([item['stock_code'] for item in result['secondary_pool']], ['603026', '000889', '600488'])
        self.assertEqual(result['main_pool'][0]['source_pool'], 'main')
        self.assertEqual(result['secondary_pool'][0]['source_pool'], 'secondary')

    def test_classify_monitoring_pattern_distinguishes_trend_fast_and_range(self):
        support = self._load_module()

        trend = support.classify_monitoring_pattern(
            [
                {'date': '2026-04-10', 'close': 88.63},
                {'date': '2026-04-15', 'close': 86.92},
                {'date': '2026-04-24', 'close': 115.73},
            ],
            pattern_hint='bojie',
        )
        fast = support.classify_monitoring_pattern(
            [
                {'date': '2026-04-10', 'close': 4.35},
                {'date': '2026-04-13', 'close': 3.92},
                {'date': '2026-04-24', 'close': 4.79},
            ],
            pattern_hint='zhongjia',
        )
        rng = support.classify_monitoring_pattern(
            [
                {'date': '2026-04-10', 'close': 85.16},
                {'date': '2026-04-15', 'close': 98.65},
                {'date': '2026-04-24', 'close': 104.06},
            ],
            pattern_hint='shida',
        )

        self.assertEqual(trend, 'trend_continuation')
        self.assertEqual(fast, 'fast_in_fast_out')
        self.assertEqual(rng, 'range_consumption')

    def test_assess_monitoring_status_maps_pattern_to_status(self):
        support = self._load_module()

        trend_result = support.assess_monitoring_status('trend_continuation', latest_close=115.73, anchor_price=86.9)
        fast_result = support.assess_monitoring_status('fast_in_fast_out', latest_close=4.35, anchor_price=5.29)
        range_result = support.assess_monitoring_status('range_consumption', latest_close=104.06, anchor_price=108.02)

        self.assertEqual(trend_result['tracking_status'], 'active')
        self.assertEqual(fast_result['tracking_status'], 'watch')
        self.assertEqual(range_result['tracking_status'], 'watch')
        self.assertIn('趋势', trend_result['assessment_reason'])
        self.assertIn('快进快出', fast_result['assessment_reason'])
        self.assertIn('震荡消耗', range_result['assessment_reason'])


if __name__ == '__main__':
    unittest.main()
