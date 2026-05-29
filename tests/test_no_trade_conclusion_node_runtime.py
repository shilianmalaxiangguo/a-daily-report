import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.no_trade_conclusion_node_runtime import run_no_trade_conclusion_nodes


class NoTradeConclusionNodeRuntimeTest(unittest.TestCase):
    def test_run_no_trade_conclusion_nodes_exports_runtime_contract_for_replay(self):
        def build_first_node(context, node_meta, node_lookup=None):
            self.assertEqual(node_meta["node_key"], "table")
            self.assertEqual(node_meta["title"], "空仓结论表")
            self.assertEqual(node_meta["node_no"], 0)
            self.assertEqual(node_lookup["plan"]["title"], "明日计划")
            return {
                "lines": ["table line"],
                "exports": {"no_trade_reason": "跌停扩散"},
                "module_logs": [{"module": "test", "step": "table", "status": "success"}],
            }

        def build_second_node(context, node_meta, node_lookup=None):
            self.assertEqual(context["no_trade_reason"], "跌停扩散")
            self.assertEqual(node_meta["node_key"], "plan")
            return {"lines": ["plan line"], "exports": {"plan_ready": True}}

        result = run_no_trade_conclusion_nodes(
            [
                {"node_key": "table", "title": "空仓结论表", "builder": build_first_node},
                {"node_key": "plan", "title": "明日计划", "builder": build_second_node},
            ],
            {"seed": True},
        )

        self.assertEqual(result["lines"], ["table line", "plan line"])
        self.assertEqual(result["context"]["no_trade_reason"], "跌停扩散")
        self.assertTrue(result["context"]["plan_ready"])
        self.assertEqual(result["node_outputs"]["table"]["no_trade_reason"], "跌停扩散")
        self.assertTrue(result["node_outputs"]["plan"]["plan_ready"])
        self.assertEqual([node["node_key"] for node in result["nodes"]], ["table", "plan"])
        self.assertEqual(result["node_lookup"]["table"]["title"], "空仓结论表")
        self.assertTrue(any(log.get("step") == "run.table" for log in result["module_logs"]))
        self.assertTrue(any(log.get("step") == "run.plan" for log in result["module_logs"]))


if __name__ == "__main__":
    unittest.main()
