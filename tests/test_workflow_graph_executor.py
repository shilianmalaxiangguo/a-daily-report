import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from workflow_graph.executor import execute_workflow_graph


class WorkflowGraphExecutorTest(unittest.TestCase):
    def test_execute_workflow_graph_runs_nodes_in_dependency_order_and_merges_state(self):
        workflow = {
            "workflow_key": "demo_v1",
            "nodes": [
                {"key": "start", "kind": "infer"},
                {"key": "double", "kind": "infer"},
            ],
            "edges": [
                {"from": "start", "to": "double"},
            ],
            "exports": ["double_value"],
        }
        call_order = []

        def start_node(ctx):
            call_order.append("start")
            return {
                "value": {"start_value": 3},
                "exports": {"start_value": 3},
                "state_patch": {"start_value": 3},
                "module_logs": [],
                "errors": [],
                "control": {"status": "success"},
            }

        def double_node(ctx):
            call_order.append("double")
            upstream = ctx.get("upstream", {})
            start_value = upstream["start"]["start_value"]
            return {
                "value": {"double_value": start_value * 2},
                "exports": {"double_value": start_value * 2},
                "state_patch": {"double_value": start_value * 2},
                "module_logs": [],
                "errors": [],
                "control": {"status": "success"},
            }

        result = execute_workflow_graph(
            workflow,
            {"start": start_node, "double": double_node},
            {"inputs": {"target_date": "2026-04-22"}},
        )

        self.assertEqual(call_order, ["start", "double"])
        self.assertEqual(result["exports"]["double_value"], 6)
        self.assertEqual(result["state"]["start_value"], 3)
        self.assertEqual(result["state"]["double_value"], 6)

    def test_execute_workflow_graph_normalizes_collections_and_errors_override_status(self):
        workflow = {
            "workflow_key": "demo_v1",
            "nodes": [{"key": "start", "kind": "infer"}],
            "edges": [],
            "exports": [],
        }

        def start_node(ctx):
            return {
                "exports": {},
                "state_patch": {},
                "module_logs": {"kind": "node-log"},
                "errors": "node failed",
                "control": {"status": "success"},
            }

        result = execute_workflow_graph(workflow, {"start": start_node}, {})

        self.assertEqual(result["errors"], ["node failed"])
        self.assertEqual(result["module_logs"][0], {"kind": "node-log"})
        executor_log = result["module_logs"][-1]
        self.assertEqual(executor_log["module"], "workflow_graph.executor")
        self.assertEqual(executor_log["node_key"], "start")
        self.assertEqual(executor_log["status"], "error")


if __name__ == "__main__":
    unittest.main()
