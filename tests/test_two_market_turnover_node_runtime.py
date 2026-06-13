import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from domains.market_state.two_market_turnover.node_registry import build_two_market_turnover_node_specs
from domains.market_state.two_market_turnover.node_runtime import run_two_market_turnover_nodes


class TwoMarketTurnoverNodeRuntimeTest(unittest.TestCase):
    def test_runtime_can_execute_only_selected_compare_node(self):
        node_specs = build_two_market_turnover_node_specs(enabled_node_keys=["compare"])
        context = {
            "target_date": "2026-05-21",
            "data": {
                "total_turnover": 35072.8,
                "market_stats": {"up_count": 800, "down_count": 4600},
                "dt_pool": [{"code": "000001"}] * 65,
                "market_turnover_history": [
                    {"date": "2026-05-19", "turnover": 29089.77},
                    {"date": "2026-05-20", "turnover": 29764.59},
                ],
            },
        }

        result = run_two_market_turnover_nodes(node_specs, context)

        self.assertEqual([node["node_key"] for node in result["nodes"]], ["compare"])
        summary = result["context"]["two_market_turnover_comparison"]
        self.assertEqual(summary["state"], "rising")
        self.assertEqual(summary["label"], "成交额继续回升")
        self.assertEqual(summary["latest_turnover_yi"], 35072.8)
        self.assertAlmostEqual(summary["previous_change_pct"], 17.83, places=2)
        self.assertEqual(result["diagnostics"]["compare"]["history_count"], 2)
        self.assertEqual(result["diagnostics"]["compare"]["source"], "context.market_turnover_history")
        self.assertIn("two_market_turnover", result["report_sections"])

    def test_compare_node_marks_missing_history_as_insufficient_sample(self):
        node_specs = build_two_market_turnover_node_specs(enabled_node_keys=["compare"])
        result = run_two_market_turnover_nodes(
            node_specs,
            {
                "target_date": "2026-05-21",
                "data": {
                    "total_turnover": 16888.0,
                    "market_stats": {"up_count": 3600, "down_count": 1600},
                    "dt_pool": [],
                },
            },
        )

        summary = result["context"]["two_market_turnover_comparison"]
        self.assertEqual(summary["state"], "unknown")
        self.assertEqual(summary["label"], "量能历史不足")
        self.assertIsNone(summary["previous_change_pct"])
        self.assertEqual(result["diagnostics"]["compare"]["history_count"], 0)
        self.assertEqual(result["diagnostics"]["compare"]["source"], "missing")

    def test_compare_node_uses_top50_series_market_amount_when_turnover_history_missing(self):
        node_specs = build_two_market_turnover_node_specs(enabled_node_keys=["compare"])
        result = run_two_market_turnover_nodes(
            node_specs,
            {
                "target_date": "2026-06-04",
                "data": {
                    "total_turnover": 27791.64,
                    "top50_turnover_share_series": {
                        "rows": [
                            {"trade_date": "2026-06-03", "market_amount_yi": 31531.25, "share_pct": 20.0},
                            {"trade_date": "2026-06-04", "market_amount_yi": 27791.64, "share_pct": 19.0},
                        ]
                    },
                    "market_stats": {"up_count": 1800, "down_count": 3600},
                    "dt_pool": [{"code": "000001"}] * 5,
                },
            },
        )

        summary = result["context"]["two_market_turnover_comparison"]
        self.assertEqual(summary["state"], "pullback")
        self.assertEqual(summary["label"], "成交额冲高后回落")
        self.assertEqual(summary["previous_turnover_yi"], 31531.25)
        self.assertAlmostEqual(summary["previous_change_pct"], -11.86, places=2)
        self.assertEqual(result["diagnostics"]["compare"]["history_count"], 1)
        self.assertEqual(result["diagnostics"]["compare"]["source"], "context.top50_turnover_share_series.market_amount_yi")


if __name__ == "__main__":
    unittest.main()
