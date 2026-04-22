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
from domains.market_state.registry import (
    MarketStateRegistryBuildError,
    build_market_state_registry,
)
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

        ctx = {"inputs": {"data": {}}}
        result = run_market_state_analysis(ctx)

        self.assertEqual(result["exports"]["exit_analysis"]["sector_name"], "军工")
        execute_mock.assert_called_once()
        args, kwargs = execute_mock.call_args
        self.assertEqual(kwargs, {})
        self.assertEqual(len(args), 3)
        self.assertIsInstance(args[0], dict)
        self.assertIsInstance(args[1], dict)
        self.assertIs(args[2], ctx)
        self.assertEqual(args[0]["workflow_key"], WORKFLOW_KEY)
        self.assertEqual(args[0]["exports"], MARKET_STATE_EXPORT_KEYS)
        self.assertIn(NODE_MAINLINE_CANDIDATES, args[1])
        self.assertIn(NODE_ASSEMBLE_EXIT_ANALYSIS, args[1])

    @patch("domains.market_state.registry.import_module")
    @patch("domains.market_state.registry.build_market_state_node_module_map")
    def test_build_market_state_registry_raises_clear_error_on_import_failure(
        self, map_mock, import_mock
    ):
        map_mock.return_value = {NODE_MAINLINE_CANDIDATES: "missing_node_module"}
        import_mock.side_effect = ImportError("boom")

        with self.assertRaisesRegex(
            MarketStateRegistryBuildError,
            "Unable to load market_state node 'mainline_candidates'",
        ):
            build_market_state_registry()


if __name__ == "__main__":
    unittest.main()
