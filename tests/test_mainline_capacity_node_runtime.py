import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from domains.market_state.mainline_capacity.node_registry import build_mainline_capacity_node_specs
from domains.market_state.mainline_capacity.node_runtime import run_mainline_capacity_nodes


class MainlineCapacityNodeRuntimeTest(unittest.TestCase):
    def test_runtime_can_execute_only_selected_summary_node(self):
        node_specs = build_mainline_capacity_node_specs(enabled_node_keys=["summary"])
        context = {
            "target_date": "2026-05-20",
            "current_mainline_history_record": {
                "date": "2026-05-20",
                "primary_mainline": "半导体",
                "secondary_mainline": "CPO",
                "market_regime": "震荡",
            },
            "recent_mainline_history": [
                {"date": "2026-05-18", "primary_mainline": "半导体"},
                {"date": "2026-05-19", "primary_mainline": "半导体"},
            ],
            "current_sector_turnover_snapshot": {
                "date": "2026-05-20",
                "sector_name": "半导体",
                "sector_turnover": 4050.0,
                "total_turnover": 35000.0,
                "turnover_share_pct": 11.57,
                "source_status": "success",
            },
            "recent_sector_turnover_history": [
                {
                    "date": "2026-05-18",
                    "sector_name": "半导体",
                    "sector_turnover": 2744.0,
                    "total_turnover": 28000.0,
                    "turnover_share_pct": 9.8,
                },
                {
                    "date": "2026-05-19",
                    "sector_name": "半导体",
                    "sector_turnover": 3286.0,
                    "total_turnover": 31000.0,
                    "turnover_share_pct": 10.6,
                },
            ],
        }

        result = run_mainline_capacity_nodes(node_specs, context)

        self.assertEqual([node["node_key"] for node in result["nodes"]], ["summary"])
        summary = result["context"]["mainline_turnover_summary"]
        self.assertEqual(summary["current_mainline"], "半导体")
        self.assertEqual(summary["share_trend_label"], "强化")
        self.assertEqual(summary["conclusion"], "主线未切换，半导体仍是中心")

        capacity_summary = result["context"]["mainline_capacity_regime_summary"]
        self.assertEqual(capacity_summary["mainline_capacity"], "双线孕育")
        self.assertEqual(capacity_summary["mainline_regime"], "双主线竞争")
        self.assertEqual(capacity_summary["primary_line"], "半导体")

        diagnostics = result["diagnostics"]["summary"]
        self.assertEqual(diagnostics["current_mainline"], "半导体")
        self.assertEqual(diagnostics["turnover_share_row_count"], 3)
        self.assertEqual(diagnostics["mainline_capacity"], "双线孕育")
        self.assertEqual(diagnostics["mainline_regime"], "双主线竞争")
        self.assertEqual(diagnostics["turnover_share_source_status"], "success")

        self.assertIn("mainline_turnover_summary", result["node_outputs"]["summary"])
        self.assertIn("mainline_capacity_regime_summary", result["node_outputs"]["summary"])
        self.assertEqual(result["report_sections"]["mainline_capacity_regime"], capacity_summary)
        self.assertEqual(result["report_sections"]["mainline_turnover_summary"], summary)

    def test_summary_node_records_degraded_inputs_without_disappearing(self):
        node_specs = build_mainline_capacity_node_specs(enabled_node_keys=["summary"])

        result = run_mainline_capacity_nodes(
            node_specs,
            {
                "target_date": "2026-05-20",
                "current_mainline_history_record": {"date": "2026-05-20", "primary_mainline": "半导体"},
                "current_sector_turnover_snapshot": {
                    "date": "2026-05-20",
                    "sector_name": "半导体",
                    "total_turnover": 35000.0,
                    "source_status": "missing_dependency",
                },
                "sector_attack_evidence_rows": [
                    {
                        "sector_name": "半导体",
                        "net_inflow_rank": 8,
                        "net_inflow_amount": 2.5,
                        "limit_up_count": 1,
                        "high_anchor_height": 1,
                        "broad_rally_pct": 45,
                        "strong_gain_count": 2,
                        "turnover_share_change": 0.2,
                    }
                ],
            },
        )

        summary = result["context"]["mainline_turnover_summary"]
        capacity_summary = result["context"]["mainline_capacity_regime_summary"]
        diagnostics = result["diagnostics"]["summary"]

        self.assertEqual(summary["current_mainline"], "")
        self.assertEqual(capacity_summary["mainline_regime"], "无主线")
        self.assertEqual(capacity_summary["primary_line"], "暂无")
        self.assertEqual(diagnostics["turnover_share_source_status"], "missing_dependency")
        self.assertEqual(diagnostics["attack_state"], "no_attack")
        self.assertEqual(diagnostics["turnover_share_row_count"], 1)
        self.assertIn("mainline_turnover_summary", result["report_sections"])
        self.assertIn("mainline_turnover_share_trend", result["report_sections"])


if __name__ == "__main__":
    unittest.main()
