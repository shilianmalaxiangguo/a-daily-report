import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from domains.new_stock_reference.node_registry import build_new_stock_reference_node_specs
from domains.new_stock_reference.node_runtime import run_new_stock_reference_nodes


class NewStockReferenceNodeRuntimeTest(unittest.TestCase):
    def test_runtime_can_execute_only_selected_score_node(self):
        node_specs = build_new_stock_reference_node_specs(enabled_node_keys=["score"])
        context = {
            "target_date": "2026-04-29",
            "new_stock_calendar": [
                {
                    "code": "301608",
                    "name": "N理奇智能",
                    "listing_date": "2026-04-30",
                    "issue_price": 20.0,
                    "fundraising_yi": 2.944,
                    "source": "sina_new_stock_calendar",
                    "source_status": "success",
                }
            ],
            "new_stock_context": {
                "mainline_name": "电池",
                "potential_mainline": ["锂电池", "新能源"],
                "new_stock_money_making_effect": "strong",
                "sector_resonance": {"status": "strong"},
                "new_stock_profiles": {
                    "301608": {
                        "sector": "电池",
                        "concept_tags": ["锂电池", "新能源"],
                        "customer_anchors": ["宁德时代", "比亚迪"],
                        "supply_chain_role": "锂电池设备/材料链",
                        "domestic_advantage": "国产制造和成本优势",
                        "new_stock_cycle_state": "扩散",
                        "c_stage_acceptance": "confirmed",
                        "emotion_outlet_status": "market_flag",
                        "new_stock_recognition_status": "emotion_flag",
                    }
                },
            },
        }

        result = run_new_stock_reference_nodes(node_specs, context)

        self.assertEqual([node["node_key"] for node in result["nodes"]], ["score"])
        self.assertIn("new_stock_research_pool", result["context"])
        self.assertIn("new_stock_candidate_upgrades", result["context"])
        self.assertNotIn("new_stock_report_lines", result["context"])
        self.assertEqual(result["diagnostics"]["score"]["research_count"], 1)
        self.assertGreaterEqual(result["diagnostics"]["score"]["upgrade_count"], 1)


if __name__ == "__main__":
    unittest.main()
