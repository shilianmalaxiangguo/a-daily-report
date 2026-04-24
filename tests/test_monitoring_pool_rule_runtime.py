import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))


class MonitoringPoolRuleRuntimeTest(unittest.TestCase):
    def test_collect_monitoring_pool_candidates_via_nodes_splits_main_and_secondary(self):
        from report.monitoring_pool_rule_nodes import collect_monitoring_pool_candidates_via_nodes
        result = collect_monitoring_pool_candidates_via_nodes(
            {
                'core_stocks': [{'name': '博杰股份', 'code': '002975'}],
                'secondary_stocks': [{'name': '龙蟠科技', 'code': '603906'}],
                'crossline_observation_stocks': [{'name': '石大胜华', 'code': '603026'}],
                'gem_observation_stocks': [{'name': '移为通信', 'code': '300590'}],
                'generic_watch_stocks': [{'name': '津药药业', 'code': '600488'}],
            }
        )
        self.assertEqual([item['stock_code'] for item in result['main_pool']], ['002975', '603906'])
        self.assertEqual([item['stock_code'] for item in result['secondary_pool']], ['603026', '300590', '600488'])

    def test_collect_monitoring_pool_candidates_via_nodes_dedups_secondary_against_main(self):
        from report.monitoring_pool_rule_nodes import collect_monitoring_pool_candidates_via_nodes
        result = collect_monitoring_pool_candidates_via_nodes(
            {
                'core_stocks': [{'name': '博杰股份', 'code': '002975'}],
                'generic_watch_stocks': [{'name': '博杰股份', 'code': '002975'}],
            }
        )
        self.assertEqual(len(result['main_pool']), 1)
        self.assertEqual(len(result['secondary_pool']), 0)


if __name__ == '__main__':
    unittest.main()
