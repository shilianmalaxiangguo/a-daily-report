import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.final_conclusion_node_runtime import run_final_conclusion_nodes


class FinalConclusionNodeRuntimeTest(unittest.TestCase):
    def test_run_final_conclusion_nodes_aggregates_lines_exports_and_logs_in_order(self):
        def build_first_node(context, node_meta, node_lookup=None):
            self.assertEqual(context.get("seed"), "final-conclusion")
            self.assertEqual(node_meta["node_key"], "first")
            return {
                "lines": ["first-line"],
                "exports": {"first_value": 1},
                "module_logs": [{"module": "final_conclusion.first", "step": "run", "status": "success", "message": "first ok", "details": {}}],
            }

        def build_second_node(context, node_meta, node_lookup=None):
            self.assertEqual(context.get("first_value"), 1)
            self.assertEqual(node_lookup["first"]["title"], "First Node")
            return {
                "lines": ["second-line"],
                "exports": {"second_value": 2},
                "module_logs": [{"module": "final_conclusion.second", "step": "run", "status": "success", "message": "second ok", "details": {}}],
            }

        result = run_final_conclusion_nodes(
            [
                {"node_key": "first", "title": "First Node", "builder": build_first_node},
                {"node_key": "second", "title": "Second Node", "builder": build_second_node},
            ],
            {"seed": "final-conclusion"},
        )

        self.assertEqual(result["lines"], ["first-line", "second-line"])
        self.assertEqual(result["context"]["first_value"], 1)
        self.assertEqual(result["context"]["second_value"], 2)
        self.assertEqual(result["node_outputs"]["first"]["first_value"], 1)
        self.assertEqual(result["node_outputs"]["second"]["second_value"], 2)
        self.assertEqual([node["node_key"] for node in result["nodes"]], ["first", "second"])
        self.assertTrue(any(log["module"] == "final_conclusion.first" for log in result["module_logs"]))
        self.assertTrue(any(log["step"] == "run.second" for log in result["module_logs"]))


if __name__ == "__main__":
    unittest.main()
