import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))


class MonitoringPoolNodeRuntimeTest(unittest.TestCase):
    def _load_nodes_module(self):
        try:
            return __import__('report.monitoring_pool_nodes', fromlist=['monitoring_pool_nodes'])
        except ModuleNotFoundError as error:
            self.fail(f'report.monitoring_pool_nodes should exist: {error}')

    def test_render_monitoring_pool_nodes_can_render_only_main_summary(self):
        nodes = self._load_nodes_module()
        result = nodes.render_monitoring_pool_nodes(
            {
                'performance_summary': {
                    'monitoring_pool': {
                        'main_pool': [{'stock_name': '博杰股份', 'stock_code': '002975', 'days_since_selected': 11, 'cum_change_pct': 33.18, 'pattern_type': 'trend_continuation', 'current_assessment': '保留'}],
                        'secondary_pool': [{'stock_name': '石大胜华', 'stock_code': '603026', 'days_since_selected': 11, 'cum_change_pct': 22.0, 'pattern_type': 'range_consumption', 'current_assessment': '观察'}],
                    }
                },
                'helpers': {'format_pct': lambda value: '-' if value is None else str(value)},
                'enabled_node_keys': ['main_pool_summary'],
            }
        )
        rendered = '\n'.join(result['lines'])
        self.assertIn('博杰股份(002975)', rendered)
        self.assertNotIn('石大胜华(603026)', rendered)
        self.assertNotIn('主监测池', rendered)

    def test_render_monitoring_pool_nodes_can_render_main_and_secondary_details_separately(self):
        nodes = self._load_nodes_module()
        result = nodes.render_monitoring_pool_nodes(
            {
                'performance_summary': {
                    'monitoring_pool': {
                        'main_pool': [{
                            'stock_name': '博杰股份', 'stock_code': '002975', 'days_since_selected': 11, 'cum_change_pct': 33.18, 'pattern_type': 'trend_continuation', 'current_assessment': '保留', 'assessment_reason': '趋势延续', 'anchor_price': 88.63, 'observation_band_low': 86.16, 'observation_band_high': 91.66, 'failure_line': 85.30, 'monitoring_rows': [{'date': '2026-04-10', 'open': 86.64, 'high': 90.67, 'low': 86.52, 'close': 88.63, 'daily_change_pct': 1.99, 'cum_change_pct_from_next_day': 0.0, 'volume_state': '放量', 'candle_shape': '上影阳线', 'day_label': '震荡'}],
                        }],
                        'secondary_pool': [{
                            'stock_name': '石大胜华', 'stock_code': '603026', 'days_since_selected': 11, 'cum_change_pct': 22.0, 'pattern_type': 'range_consumption', 'current_assessment': '观察', 'assessment_reason': '震荡消耗', 'anchor_price': 85.16, 'observation_band_low': 77.77, 'observation_band_high': 108.02, 'failure_line': 76.99, 'monitoring_rows': [{'date': '2026-04-23', 'open': 104.0, 'high': 108.8, 'low': 100.0, 'close': 102.76, 'daily_change_pct': -1.98, 'cum_change_pct_from_next_day': 20.0, 'volume_state': '平量', 'candle_shape': '下影阴线', 'day_label': '弱修复'}],
                        }],
                    }
                },
                'helpers': {'format_pct': lambda value: '-' if value is None else str(value)},
                'enabled_node_keys': ['main_pool_header', 'main_pool_details', 'secondary_pool_header', 'secondary_pool_details'],
            }
        )
        rendered = '\n'.join(result['lines'])
        self.assertIn('主监测池', rendered)
        self.assertIn('副监测池', rendered)
        self.assertIn('观察锚点', rendered)
        self.assertIn('博杰股份(002975)', rendered)
        self.assertIn('石大胜华(603026)', rendered)
        self.assertNotIn('| 标的 | 交易日数 |', rendered)

    def test_render_monitoring_pool_details_shows_xuangubao_limit_up_reason(self):
        nodes = self._load_nodes_module()
        result = nodes.render_monitoring_pool_nodes(
            {
                'performance_summary': {
                    'monitoring_pool': {
                        'main_pool': [{
                            'stock_name': '交运股份',
                            'stock_code': '600676',
                            'assessment_reason': '首板后观察',
                            'xuangubao_stock_reason': '拟置入文旅体育资产',
                            'xuangubao_related_plate_names': ['资产重组'],
                            'monitoring_rows': [{'date': '2026-05-18'}],
                        }],
                    }
                },
                'enabled_node_keys': ['main_pool_details'],
            }
        )

        rendered = '\n'.join(result['lines'])
        self.assertIn('选股通解释', rendered)
        self.assertIn('拟置入文旅体育资产', rendered)
        self.assertIn('资产重组', rendered)


if __name__ == '__main__':
    unittest.main()
