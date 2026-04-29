import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from decision.chanlun import structure_nodes


class ChanlunStructureNodesTest(unittest.TestCase):
    def test_identify_platform_requires_three_completed_trend_types_overlap(self):
        trend_types = [
            {"trend_type_id": "t1", "high": 110, "low": 100, "direction": "up", "status": "completed_trend_type"},
            {"trend_type_id": "t2", "high": 108, "low": 98, "direction": "down", "status": "completed_trend_type"},
            {"trend_type_id": "t3", "high": 109, "low": 101, "direction": "up", "status": "completed_trend_type"},
        ]

        segments, platforms = structure_nodes.identify_platforms_from_trend_types(trend_types, level_id="daily")

        self.assertEqual(len(platforms), 1)
        self.assertEqual(platforms[0]["ZD"], 101.0)
        self.assertEqual(platforms[0]["ZG"], 108.0)
        self.assertEqual(platforms[0]["rule_tier"], "original_rule")
        self.assertEqual(segments[0]["role"], "inside_zhongshu")

    def test_no_overlap_returns_connector_not_zhongshu(self):
        trend_types = [
            {"trend_type_id": "t1", "high": 110, "low": 108, "status": "completed_trend_type"},
            {"trend_type_id": "t2", "high": 100, "low": 98, "status": "completed_trend_type"},
            {"trend_type_id": "t3", "high": 90, "low": 88, "status": "completed_trend_type"},
        ]

        segments, platforms = structure_nodes.identify_platforms_from_trend_types(trend_types, level_id="daily")

        self.assertEqual(platforms, [])
        self.assertEqual(segments[0]["segment_type"], "connector")
        self.assertEqual(segments[0]["role"], "connector_move")

    def test_platforms_touching_get_diagnostic_bridge_only(self):
        trend_types = [
            {"trend_type_id": "t1", "high": 110, "low": 100, "status": "completed_trend_type"},
            {"trend_type_id": "t2", "high": 108, "low": 98, "status": "completed_trend_type"},
            {"trend_type_id": "t3", "high": 109, "low": 101, "status": "completed_trend_type"},
            {"trend_type_id": "t4", "high": 130, "low": 120, "status": "completed_trend_type"},
            {"trend_type_id": "t5", "high": 128, "low": 118, "status": "completed_trend_type"},
            {"trend_type_id": "t6", "high": 129, "low": 121, "status": "completed_trend_type"},
        ]

        segments, platforms = structure_nodes.identify_platforms_from_trend_types(trend_types, level_id="daily")

        self.assertEqual(len(platforms), 2)
        self.assertEqual([item["segment_type"] for item in segments], ["zhongshu", "connector", "zhongshu"])
        self.assertEqual(segments[1]["rule_tier"], "diagnostic_heuristic")


if __name__ == "__main__":
    unittest.main()
