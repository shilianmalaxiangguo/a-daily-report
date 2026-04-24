import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.legacy_stage_summary_node_runtime import run_legacy_stage_summary_nodes


class LegacyStageSummaryNodeRuntimeTest(unittest.TestCase):
    def test_run_legacy_stage_summary_nodes_aggregates_rows_exports_and_logs_in_order(self):
        def build_first_node(context, node_meta, node_lookup=None):
            self.assertEqual(context.get("seed"), "legacy-stage-summary")
            self.assertEqual(node_meta["node_key"], "first")
            return {
                "rows": [{"stage_key": "first", "title": "First", "guidance": "1"}],
                "exports": {"first_value": 1},
                "module_logs": [{"module": "legacy_stage_summary.first", "step": "run", "status": "success", "message": "first ok", "details": {}}],
            }

        def build_second_node(context, node_meta, node_lookup=None):
            self.assertEqual(context.get("first_value"), 1)
            self.assertEqual(node_lookup["first"]["title"], "First Node")
            return {
                "rows": [{"stage_key": "second", "title": "Second", "guidance": "2"}],
                "exports": {"second_value": 2},
                "module_logs": [{"module": "legacy_stage_summary.second", "step": "run", "status": "success", "message": "second ok", "details": {}}],
            }

        result = run_legacy_stage_summary_nodes(
            [
                {"node_key": "first", "title": "First Node", "builder": build_first_node},
                {"node_key": "second", "title": "Second Node", "builder": build_second_node},
            ],
            {"seed": "legacy-stage-summary"},
        )

        self.assertEqual(result["rows"], [{"stage_key": "first", "title": "First", "guidance": "1"}, {"stage_key": "second", "title": "Second", "guidance": "2"}])
        self.assertEqual(result["context"]["first_value"], 1)
        self.assertEqual(result["context"]["second_value"], 2)
        self.assertEqual(result["node_outputs"]["first"]["first_value"], 1)
        self.assertEqual(result["node_outputs"]["second"]["second_value"], 2)
        self.assertEqual([node["node_key"] for node in result["nodes"]], ["first", "second"])
        self.assertTrue(any(log["module"] == "legacy_stage_summary.first" for log in result["module_logs"]))
        self.assertTrue(any(log["step"] == "run.second" for log in result["module_logs"]))


if __name__ == "__main__":
    unittest.main()
