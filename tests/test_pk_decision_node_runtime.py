import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from domains.execution_chain.pk_decision_node_registry import build_pk_decision_node_specs
from domains.execution_chain.pk_decision_node_runtime import run_pk_decision_nodes


class PkDecisionNodeRuntimeTest(unittest.TestCase):
    def test_registry_filters_enabled_node_keys_in_default_order(self):
        builders = {
            "score_candidates": lambda context, meta, lookup: {},
            "watch_anchor": lambda context, meta, lookup: {},
            "render_sections": lambda context, meta, lookup: {},
        }

        specs = build_pk_decision_node_specs(builders, enabled_node_keys=["render_sections", "score_candidates"])

        self.assertEqual([spec["node_key"] for spec in specs], ["score_candidates", "render_sections"])

    def test_runtime_aggregates_lines_exports_logs_and_updates_context(self):
        def first(context, meta, lookup):
            return {
                "lines": ["first"],
                "exports": {"value": 1},
                "module_logs": [{"module": "first", "step": "run", "status": "success", "message": "ok", "details": {}}],
            }

        def second(context, meta, lookup):
            return {
                "lines": [f"second:{context['value']}"],
                "exports": {"done": True},
                "module_logs": [],
            }

        result = run_pk_decision_nodes(
            [
                {"node_key": "first", "title": "First", "builder": first},
                {"node_key": "second", "title": "Second", "builder": second},
            ],
            {},
        )

        self.assertEqual(result["lines"], ["first", "second:1"])
        self.assertEqual(result["context"]["value"], 1)
        self.assertEqual(result["context"]["done"], True)
        self.assertEqual([node["node_key"] for node in result["nodes"]], ["first", "second"])
        self.assertTrue(any(log["step"] == "run.first" for log in result["module_logs"]))
        self.assertTrue(any(log["step"] == "run.second" for log in result["module_logs"]))
