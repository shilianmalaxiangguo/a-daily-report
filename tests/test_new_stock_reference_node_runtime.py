import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from domains.new_stock_reference.node_registry import build_new_stock_reference_node_specs
from domains.new_stock_reference.node_runtime import run_new_stock_reference_nodes


class NewStockReferenceNodeRuntimeTest(unittest.TestCase):
    FULL_NODE_KEYS = [
        "input.new_stock_calendar.request",
        "selection.new_stock_narrative.score",
        "watch_candidates.new_stock_upgrade.merge",
        "report.new_stock_research.render",
        "audit.new_stock_replay.check",
    ]

    def _liqi_calendar(self):
        return [
            {
                "code": "301608",
                "name": "N理奇智能",
                "listing_date": "2026-04-30",
                "issue_price": 20.0,
                "fundraising_yi": 2.944,
                "source": "sina_new_stock_calendar",
                "source_status": "success",
            }
        ]

    def _liqi_context(self, *, cycle_proof=False):
        profile = {
            "sector": "电池",
            "industry": "锂电池设备",
            "concept_tags": ["锂电池", "新能源"],
            "customer_anchors": ["宁德时代", "比亚迪"],
            "supply_chain_role": "锂电池设备/材料链",
            "domestic_advantage": "国产制造和成本优势",
        }
        if cycle_proof:
            profile.update(
                {
                    "new_stock_cycle_state": "扩散",
                    "c_stage_acceptance": "confirmed",
                    "emotion_outlet_status": "market_flag",
                    "new_stock_recognition_status": "emotion_flag",
                }
            )
        return {
            "mainline_name": "电池",
            "potential_mainline": ["锂电池", "新能源"],
            "new_stock_money_making_effect": "strong",
            "sector_resonance": {"status": "strong"},
            "new_stock_profiles": {"301608": profile},
        }

    def test_node_specs_preserve_dependency_order_when_filtered(self):
        node_specs = build_new_stock_reference_node_specs(
            enabled_node_keys=["render", "unknown", "score"]
        )

        self.assertEqual(
            [spec["node_key"] for spec in node_specs],
            [
                "selection.new_stock_narrative.score",
                "report.new_stock_research.render",
            ],
        )

    def test_node_specs_accept_documented_full_key_selection(self):
        node_specs = build_new_stock_reference_node_specs(
            enabled_node_keys=["selection.new_stock_narrative.score"]
        )

        self.assertEqual(len(node_specs), 1)
        self.assertEqual(
            node_specs[0]["node_key"], "selection.new_stock_narrative.score"
        )

    def test_node_specs_accept_mixed_short_and_full_key_selection(self):
        node_specs = build_new_stock_reference_node_specs(
            enabled_node_keys=["render", "selection.new_stock_narrative.score"]
        )

        self.assertEqual(
            [spec["node_key"] for spec in node_specs],
            [
                "selection.new_stock_narrative.score",
                "report.new_stock_research.render",
            ],
        )

    def test_node_specs_use_dependency_order_for_custom_builders(self):
        def fake_builder(_context):
            return None

        node_specs = build_new_stock_reference_node_specs(
            builder_map={"render": fake_builder, "score": fake_builder},
            enabled_node_keys=["render", "score"],
        )

        self.assertEqual(
            [spec["node_key"] for spec in node_specs],
            [
                "selection.new_stock_narrative.score",
                "report.new_stock_research.render",
            ],
        )

    def test_node_specs_respect_explicit_empty_selection(self):
        node_specs = build_new_stock_reference_node_specs(enabled_node_keys=[])

        self.assertEqual(node_specs, [])

    def test_node_specs_respect_explicit_empty_builder_map(self):
        node_specs = build_new_stock_reference_node_specs(builder_map={})

        self.assertEqual(node_specs, [])

    def test_runtime_can_execute_only_selected_score_node(self):
        node_specs = build_new_stock_reference_node_specs(enabled_node_keys=["score"])
        context = {
            "target_date": "2026-04-29",
            "new_stock_calendar": self._liqi_calendar(),
            "new_stock_context": self._liqi_context(cycle_proof=True),
        }

        result = run_new_stock_reference_nodes(node_specs, context)

        self.assertEqual(
            [node["node_key"] for node in result["nodes"]],
            ["selection.new_stock_narrative.score"],
        )
        self.assertIn("new_stock_research_pool", result["context"])
        self.assertIn("new_stock_candidate_upgrades", result["context"])
        self.assertNotIn("new_stock_report_lines", result["context"])
        score_key = "selection.new_stock_narrative.score"
        self.assertEqual(result["diagnostics"][score_key]["research_count"], 1)
        self.assertGreaterEqual(result["diagnostics"][score_key]["upgrade_count"], 1)

    def test_runtime_merges_context_patch_collects_errors_and_keeps_outputs(self):
        def first_builder(context, _node_meta, _node_lookup):
            return {
                "exports": {"shared": "export", "export_only": 1},
                "context_patch": {"shared": "patch", "patch_only": 2},
                "errors": ["first issue"],
            }

        def second_builder(context, _node_meta, _node_lookup):
            return {
                "exports": {"saw_shared": context["shared"]},
                "errors": ["second issue"],
            }

        node_specs = build_new_stock_reference_node_specs(
            builder_map={"score": first_builder, "render": second_builder},
            enabled_node_keys=["score", "render"],
        )

        result = run_new_stock_reference_nodes(node_specs, {"start": True})

        score_key = "selection.new_stock_narrative.score"
        render_key = "report.new_stock_research.render"
        self.assertEqual(result["context"]["shared"], "patch")
        self.assertEqual(result["context"]["export_only"], 1)
        self.assertEqual(result["context"]["patch_only"], 2)
        self.assertEqual(result["context"]["saw_shared"], "patch")
        self.assertEqual(
            result["node_outputs"],
            {
                score_key: {"shared": "export", "export_only": 1},
                render_key: {"saw_shared": "patch"},
            },
        )
        self.assertEqual(result["errors"], ["first issue", "second issue"])

    def test_full_reference_slice_exports_report_and_audit(self):
        node_specs = build_new_stock_reference_node_specs()
        context = {
            "target_date": "2026-04-29",
            "new_stock_calendar": self._liqi_calendar(),
            "new_stock_context": self._liqi_context(cycle_proof=True),
        }

        result = run_new_stock_reference_nodes(node_specs, context)

        self.assertEqual(
            [node["node_key"] for node in result["nodes"]],
            self.FULL_NODE_KEYS,
        )
        self.assertIn("有新股研究升级，进入观察。", result["context"]["new_stock_report_lines"])
        self.assertTrue(result["context"]["new_stock_audit_passed"])
        render_key = "report.new_stock_research.render"
        self.assertEqual(result["diagnostics"][render_key]["upgrade_count"], 1)
        self.assertIn("有新股研究升级，进入观察。", result["report_sections"]["new_stock_research"])

    def test_research_only_slice_explains_absence_reason(self):
        node_specs = build_new_stock_reference_node_specs(
            enabled_node_keys=["score", "render", "audit"]
        )
        context = {
            "target_date": "2026-04-29",
            "new_stock_calendar": self._liqi_calendar(),
            "new_stock_context": self._liqi_context(cycle_proof=False),
        }

        result = run_new_stock_reference_nodes(node_specs, context)

        score_key = "selection.new_stock_narrative.score"
        self.assertEqual(result["diagnostics"][score_key]["research_count"], 1)
        self.assertEqual(result["diagnostics"][score_key]["upgrade_count"], 0)
        research_item = result["context"]["new_stock_research_pool"][0]
        self.assertFalse(research_item["upgrade_eligible"])
        self.assertIn("新股周期证明不足", research_item["candidate_upgrade_reason"])
        self.assertIn(
            "有新股研究池，但今日未形成买入资格。",
            result["context"]["new_stock_report_lines"],
        )
        self.assertTrue(result["context"]["new_stock_audit_passed"])


if __name__ == "__main__":
    unittest.main()
