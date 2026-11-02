import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from hooks.knowledge.use_llm_wiki import run


class LlmWikiHookTest(unittest.TestCase):
    def test_hook_preserves_target_and_query_dates_with_manifest_diagnostics(self):
        result = run(
            {
                "request": {
                    "target_date": "2026-07-16",
                    "query_date": "2026-07-17",
                }
            }
        )

        snapshot = result["value"]["llm_wiki"]
        derivation = result["patches"]["diagnostics"]["derivations"]["llm_wiki"]
        self.assertEqual(snapshot["target_date"], "2026-07-16")
        self.assertEqual(snapshot["query_date"], "2026-07-17")
        self.assertEqual(derivation["availability"], snapshot["availability"])
        self.assertEqual(derivation["confidence"], snapshot["confidence"])
        self.assertEqual(derivation["warnings"], snapshot["warnings"])
        self.assertEqual(result["diagnostics"]["warnings"], snapshot["warnings"])
        self.assertIs(result["artifacts"]["llm_wiki"], snapshot)
        self.assertEqual(snapshot["knowledge_trace"]["schema_version"], "knowledge_trace.v1")
        self.assertEqual(snapshot["knowledge_trace"]["target_date"], "2026-07-16")
        self.assertEqual(snapshot["knowledge_hits"], snapshot["knowledge_trace"]["hits"])

    def test_hook_routes_explicit_facts_into_a_frozen_trace(self):
        result = run(
            {
                "request": {
                    "target_date": "2026-07-16",
                    "query_date": "2026-07-17",
                    "knowledge_hit_facts": {
                        "market": {
                            "index_trend": "上涨",
                            "breadth": "上涨家数偏弱",
                        }
                    },
                }
            }
        )

        snapshot = result["value"]["llm_wiki"]
        trace = snapshot["knowledge_trace"]
        self.assertEqual(trace["facts_source"], "explicit")
        self.assertTrue(trace["trace_hash"])
        self.assertIn(
            "market.low-frequency-focus",
            {item["knowledge_id"] for item in trace["hits"]},
        )

    def test_hook_keeps_missing_target_date_warning_in_snapshot(self):
        result = run({"request": {"query_date": "2026-07-17"}})

        snapshot = result["value"]["llm_wiki"]
        warning = "目标交易日缺失，知识引用日期无法核对"
        self.assertIn(warning, snapshot["warnings"])
        self.assertIn(warning, snapshot["knowledge_trace"]["warnings"])
        self.assertEqual(snapshot["availability"], "invalid")
        self.assertEqual(snapshot["confidence"], 0.0)
        self.assertEqual(snapshot["knowledge_hits"], [])
        self.assertEqual(
            result["patches"]["diagnostics"]["derivations"]["llm_wiki"]["confidence"],
            0.0,
        )
        self.assertEqual(result["diagnostics"]["warnings"], snapshot["warnings"])

    def test_hook_reduces_confidence_when_required_sources_are_missing(self):
        snapshot = {
            "target_date": "2026-07-16",
            "query_date": "2026-07-17",
            "availability": "missing_sources",
            "warnings": ["source_missing:wiki/交易思想/缺失.md"],
            "manifest": {},
        }
        with patch(
            "hooks.knowledge.use_llm_wiki.build_llm_wiki_context",
            return_value=snapshot,
        ), patch(
            "hooks.knowledge.use_llm_wiki.route_llm_wiki_knowledge_trace",
            return_value={
                "availability": "missing_sources",
                "warnings": list(snapshot["warnings"]),
                "hits": [],
            },
        ):
            result = run(
                {
                    "request": {
                        "target_date": "2026-07-16",
                        "query_date": "2026-07-17",
                    }
                }
            )

        derivation = result["patches"]["diagnostics"]["derivations"]["llm_wiki"]
        self.assertEqual(derivation["confidence"], 0.4)
        self.assertEqual(derivation["availability"], "missing_sources")
        self.assertEqual(derivation["warnings"], snapshot["warnings"])

    def test_hook_rejects_ready_snapshot_without_a_manifest(self):
        for invalid_manifest in (None, [], {"errors": 1}, {"warnings": 1}):
            with self.subTest(manifest=invalid_manifest):
                snapshot = {
                    "target_date": "2026-07-16",
                    "query_date": "2026-07-17",
                    "availability": "ready",
                    "warnings": [],
                }
                if invalid_manifest is not None:
                    snapshot["manifest"] = invalid_manifest
                with patch(
                    "hooks.knowledge.use_llm_wiki.build_llm_wiki_context",
                    return_value=snapshot,
                ):
                    result = run(
                        {
                            "request": {
                                "target_date": "2026-07-16",
                                "query_date": "2026-07-17",
                            }
                        }
                    )

                actual = result["value"]["llm_wiki"]
                self.assertEqual(actual["availability"], "invalid")
                self.assertEqual(actual["confidence"], 0.0)
                self.assertEqual(actual.get("knowledge_hits"), [])
                self.assertEqual(
                    actual["knowledge_trace"]["schema_version"],
                    "knowledge_trace.v1",
                )
                self.assertEqual(actual["knowledge_trace"]["availability"], "invalid")
                self.assertEqual(actual["knowledge_trace"]["hits"], [])
                self.assertEqual(
                    actual["knowledge_trace"]["decision_scope"],
                    "explanation_only",
                )
                self.assertTrue(actual["knowledge_trace"]["trace_hash"])
                self.assertIn(
                    "知识清单缺失或格式无效，停止生成知识引用",
                    actual["warnings"],
                )

    def test_hook_rejects_malformed_context_warnings_without_raising(self):
        snapshot = {
            "target_date": "2026-07-16",
            "query_date": "2026-07-17",
            "availability": "ready",
            "warnings": 1,
            "manifest": {"errors": 1},
        }
        with patch(
            "hooks.knowledge.use_llm_wiki.build_llm_wiki_context",
            return_value=snapshot,
        ):
            result = run(
                {
                    "request": {
                        "target_date": "2026-07-16",
                        "query_date": "2026-07-17",
                    }
                }
            )

        actual = result["value"]["llm_wiki"]
        self.assertEqual(actual["availability"], "invalid")
        self.assertEqual(actual["confidence"], 0.0)
        self.assertEqual(actual["knowledge_hits"], [])
        self.assertEqual(actual["knowledge_trace"]["schema_version"], "knowledge_trace.v1")
        self.assertEqual(actual["knowledge_trace"]["availability"], "invalid")
        self.assertEqual(actual["knowledge_trace"]["hits"], [])
        self.assertEqual(actual["knowledge_trace"]["target_date"], "2026-07-16")
        self.assertEqual(actual["knowledge_trace"]["query_date"], "2026-07-17")
        self.assertTrue(actual["knowledge_trace"]["trace_hash"])
        self.assertIn(
            "知识上下文提醒格式无效，停止生成知识引用",
            actual["warnings"],
        )


if __name__ == "__main__":
    unittest.main()
