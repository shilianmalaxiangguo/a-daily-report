import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.execution_chain_overview_node_runtime import run_execution_chain_overview_nodes


class ExecutionChainOverviewNodeRuntimeTest(unittest.TestCase):
    def test_run_execution_chain_overview_nodes_exports_runtime_contract_for_replay(self):
        def build_first_node(context, node_meta, node_lookup=None):
            self.assertEqual(node_meta["node_key"], "first")
            self.assertEqual(node_meta["title"], "First Node")
            self.assertEqual(node_meta["node_no"], 0)
            self.assertEqual(node_lookup["second"]["title"], "Second Node")
            return {
                "lines": ["first line"],
                "exports": {"first_value": 1},
                "module_logs": [{"module": "test", "step": "first", "status": "success"}],
            }

        def build_second_node(context, node_meta, node_lookup=None):
            self.assertEqual(context["first_value"], 1)
            self.assertEqual(node_meta["node_key"], "second")
            return {"lines": ["second line"], "exports": {"second_value": 2}}

        result = run_execution_chain_overview_nodes(
            [
                {"node_key": "first", "title": "First Node", "builder": build_first_node},
                {"node_key": "second", "title": "Second Node", "builder": build_second_node},
            ],
            {"seed": True},
        )

        self.assertEqual(result["lines"], ["first line", "second line"])
        self.assertEqual(result["context"]["first_value"], 1)
        self.assertEqual(result["context"]["second_value"], 2)
        self.assertEqual(result["node_outputs"]["first"]["first_value"], 1)
        self.assertEqual(result["node_outputs"]["second"]["second_value"], 2)
        self.assertEqual([node["node_key"] for node in result["nodes"]], ["first", "second"])
        self.assertEqual(result["node_lookup"]["first"]["title"], "First Node")
        self.assertTrue(any(log.get("step") == "run.first" for log in result["module_logs"]))
        self.assertTrue(any(log.get("step") == "run.second" for log in result["module_logs"]))


if __name__ == "__main__":
    unittest.main()
