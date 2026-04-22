import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from domains.market_state.contracts import (
    MARKET_STATE_EXPORT_KEYS,
    NODE_ASSEMBLE_EXIT_ANALYSIS,
    NODE_ENVIRONMENT_SIGNAL,
    NODE_MAINLINE_CANDIDATES,
    NODE_MAINLINE_CONTINUITY,
    NODE_RISK_PRESSURE,
    NODE_SECTOR_COMPETITION,
    WORKFLOW_KEY,
)
from domains.market_state.graph import build_market_state_graph
from domains.market_state.runtime import run_market_state_analysis


class MarketStateWorkflowGraphTest(unittest.TestCase):
    def test_build_market_state_graph_declares_expected_nodes_and_exports(self):
        workflow = build_market_state_graph()
        node_keys = [item["key"] for item in workflow["nodes"]]

        self.assertEqual(workflow["workflow_key"], WORKFLOW_KEY)
        self.assertEqual(
            node_keys,
            [
                NODE_MAINLINE_CANDIDATES,
                NODE_ENVIRONMENT_SIGNAL,
                NODE_MAINLINE_CONTINUITY,
                NODE_RISK_PRESSURE,
                NODE_SECTOR_COMPETITION,
                NODE_ASSEMBLE_EXIT_ANALYSIS,
            ],
        )
        self.assertEqual(workflow["exports"], MARKET_STATE_EXPORT_KEYS)

    @patch("domains.market_state.runtime.execute_workflow_graph")
    def test_run_market_state_analysis_delegates_to_graph_executor(self, execute_mock):
        execute_mock.return_value = {
            "workflow_key": WORKFLOW_KEY,
            "exports": {"exit_analysis": {"sector_name": "军工"}},
            "state": {},
            "node_results": {},
            "module_logs": [],
            "errors": [],
        }

        result = run_market_state_analysis({"inputs": {"data": {}}})

        self.assertEqual(result["exports"]["exit_analysis"]["sector_name"], "军工")
        execute_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
