import copy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from hooks.knowledge.use_llm_wiki import run as run_llm_wiki
from hooks.persist.use_snapshot_persistence import run
from knowledge.llm_wiki_manifest import stable_json_hash
from orchestrator.context_store import build_empty_context, merge_hook_patches


def _forge_first_wiki_source_hash(frozen_wiki):
    forged = copy.deepcopy(frozen_wiki)
    manifest = forged["manifest"]
    trace = forged["knowledge_trace"]
    source_path = trace["hits"][0]["source_ref"]["path"]
    forged_hash = "0" * 64
    for source_ref in manifest["sources"]:
        if source_ref.get("path") == source_path:
            source_ref["content_hash"] = forged_hash
    for entry in manifest["entries"]:
        if entry.get("source_ref", {}).get("path") == source_path:
            entry["source_ref"]["content_hash"] = forged_hash
    for hit in trace["hits"]:
        if hit.get("source_ref", {}).get("path") == source_path:
            hit["source_ref"]["content_hash"] = forged_hash
    manifest_hash = stable_json_hash(manifest, excluded_keys={"manifest_hash"})
    manifest["manifest_hash"] = manifest_hash
    forged["manifest_hash"] = manifest_hash
    trace["manifest_hash"] = manifest_hash
    trace["trace_hash"] = stable_json_hash(trace, excluded_keys={"trace_hash"})
    forged["knowledge_hits"] = copy.deepcopy(trace["hits"])
    return forged


class UseSnapshotPersistenceTest(unittest.TestCase):
    def test_snapshot_persistence_hook_saves_rendered_payload(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = build_empty_context({"target_date": "2026-04-21"})
            ctx = merge_hook_patches(
                ctx,
                {
                    "rendered": {"markdown_document": "# report"},
                    "decision": {"execution_permission": {"label": "watch_only"}},
                    "runtime": {
                        "module_logs": [
                            {"hook_name": "infer.execution_permission", "status": "success"}
                        ]
                    },
                },
            )

            with patch("hooks.persist.use_snapshot_persistence._save_data_snapshot", return_value=str(Path(tmpdir) / "snap.json")) as mocked:
                result = run(ctx)

        expected_payload = {
            "rendered": {"markdown_document": "# report"},
            "decision": {"execution_permission": {"label": "watch_only"}},
            "diagnostics": {},
            "runtime": {
                "module_logs": [{"hook_name": "infer.execution_permission", "status": "success"}],
                "trace_events": [],
            },
        }
        self.assertEqual(result["value"]["snapshot_path"], str(Path(tmpdir) / "snap.json"))
        self.assertEqual(result["artifacts"]["snapshot_path"], str(Path(tmpdir) / "snap.json"))
        self.assertEqual(result["patches"], {})
        mocked.assert_called_once_with(expected_payload, "2026-04-21")

    def test_snapshot_persistence_hook_keeps_non_wiki_payload_unchanged(self):
        ctx = build_empty_context({"target_date": "2026-04-21"})
        ctx = merge_hook_patches(
            ctx,
            {"knowledge": {"other_context": {"note": "not llm wiki"}}},
        )

        with patch(
            "hooks.persist.use_snapshot_persistence._save_data_snapshot",
            return_value="/tmp/snapshot.json",
        ) as mocked:
            run(ctx)

        payload = mocked.call_args[0][0]
        self.assertNotIn("knowledge", payload)
        self.assertEqual(mocked.call_args[0][1], "2026-04-21")

    def test_snapshot_persistence_hook_rejects_llm_wiki_without_target_date(self):
        ctx = build_empty_context(
            {
                "query_date": "2026-07-17",
                "knowledge_hit_facts": {
                    "market": {"index_trend": "上涨"},
                },
            }
        )
        ctx = merge_hook_patches(ctx, run_llm_wiki(ctx)["patches"])

        with patch(
            "hooks.persist.use_snapshot_persistence._save_data_snapshot",
            return_value="/tmp/snapshot.json",
        ) as mocked:
            with self.assertRaisesRegex(ValueError, "目标交易日缺失"):
                run(ctx)

        mocked.assert_not_called()

    def test_snapshot_persistence_hook_rejects_incomplete_llm_wiki_trace(self):
        ctx = build_empty_context({"target_date": "2026-07-16"})
        frozen_wiki = {
            "target_date": "2026-07-16",
            "manifest_hash": "manifest-1",
            "knowledge_trace": {
                "schema_version": "knowledge_trace.v1",
                "target_date": "2026-07-16",
                "trace_hash": "trace-1",
                "hits": [{"knowledge_id": "market.low-frequency-focus"}],
            },
        }
        ctx = merge_hook_patches(ctx, {"knowledge": {"llm_wiki": frozen_wiki}})

        with patch(
            "hooks.persist.use_snapshot_persistence._save_data_snapshot",
            return_value="/tmp/snapshot.json",
        ) as mocked:
            with self.assertRaisesRegex(ValueError, "知识引用资料不完整"):
                run(ctx)

        mocked.assert_not_called()

    def test_snapshot_persistence_hook_rejects_self_hashed_impossible_query_date(self):
        ctx = build_empty_context(
            {
                "target_date": "2026-07-16",
                "query_date": "2026-07-17",
                "knowledge_hit_facts": {
                    "market": {"index_trend": "上涨"},
                },
            }
        )
        ctx = merge_hook_patches(ctx, run_llm_wiki(ctx)["patches"])
        frozen_wiki = ctx["knowledge"]["llm_wiki"]
        frozen_wiki["query_date"] = "2026-02-30"
        frozen_wiki["knowledge_trace"]["query_date"] = "2026-02-30"
        frozen_wiki["knowledge_trace"]["trace_hash"] = stable_json_hash(
            frozen_wiki["knowledge_trace"],
            excluded_keys={"trace_hash"},
        )

        with patch(
            "hooks.persist.use_snapshot_persistence._save_data_snapshot",
            return_value="/tmp/snapshot.json",
        ) as mocked:
            with self.assertRaisesRegex(ValueError, "知识引用资料不完整"):
                run(ctx)

        mocked.assert_not_called()

    def test_snapshot_persistence_hook_rejects_self_hashed_forged_source(self):
        ctx = build_empty_context(
            {
                "target_date": "2026-07-16",
                "query_date": "2026-07-17",
                "knowledge_hit_facts": {
                    "market": {
                        "index_trend": "上涨",
                        "breadth": "上涨家数偏弱",
                    },
                },
            }
        )
        ctx = merge_hook_patches(ctx, run_llm_wiki(ctx)["patches"])
        self.assertTrue(ctx["knowledge"]["llm_wiki"]["knowledge_trace"]["hits"])
        ctx["knowledge"]["llm_wiki"] = _forge_first_wiki_source_hash(
            ctx["knowledge"]["llm_wiki"]
        )

        with patch(
            "hooks.persist.use_snapshot_persistence._save_data_snapshot",
            return_value="/tmp/snapshot.json",
        ) as mocked:
            with self.assertRaisesRegex(ValueError, "知识引用资料不完整"):
                run(ctx)

        mocked.assert_not_called()

    def test_snapshot_persistence_freezes_trace_built_by_wiki_hook(self):
        ctx = build_empty_context(
            {
                "target_date": "2026-07-16",
                "query_date": "2026-07-17",
                "knowledge_hit_facts": {
                    "market": {
                        "index_trend": "上涨",
                        "breadth": "上涨家数偏弱",
                    }
                },
            }
        )
        ctx = merge_hook_patches(ctx, run_llm_wiki(ctx)["patches"])

        with patch(
            "hooks.persist.use_snapshot_persistence._save_data_snapshot",
            return_value="/tmp/snapshot.json",
        ) as mocked:
            run(ctx)

        frozen_wiki = mocked.call_args[0][0]["knowledge"]["llm_wiki"]
        self.assertEqual(frozen_wiki["knowledge_trace"]["schema_version"], "knowledge_trace.v1")
        self.assertEqual(frozen_wiki["knowledge_trace"]["target_date"], "2026-07-16")
        self.assertEqual(frozen_wiki["knowledge_hits"], frozen_wiki["knowledge_trace"]["hits"])

    def test_snapshot_persistence_hook_saves_trend_analysis_atoms_when_present(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = build_empty_context({"target_date": "2026-04-24"})
            ctx = merge_hook_patches(
                ctx,
                {
                    "rendered": {"markdown_document": "# report"},
                    "derived": {
                        "mainline": {
                            "primary_line": "通信",
                            "hot_rank_weight": 4,
                            "sector_counts": {"通信": 4, "军工": 2},
                        }
                    },
                    "normalized": {
                        "market_snapshot": {
                            "sector_turnover_snapshot": {
                                "sector_name": "通信",
                                "sector_turnover": 1800.5,
                                "total_turnover": 10000.0,
                                "turnover_share_pct": 18.01,
                                "source": "thsdk.market_data_block",
                            }
                        }
                    },
                },
            )

            with patch(
                "hooks.persist.use_snapshot_persistence._save_data_snapshot",
                return_value=str(Path(tmpdir) / "snap.json"),
            ) as mocked:
                run(ctx)

        payload = mocked.call_args[0][0]
        self.assertEqual(payload["analysis"]["mainline_history_record"]["date"], "2026-04-24")
        self.assertEqual(payload["analysis"]["mainline_history_record"]["primary_mainline"], "通信")
        self.assertEqual(payload["analysis"]["sector_turnover_snapshot"]["sector_name"], "通信")
        self.assertEqual(payload["analysis"]["sector_turnover_snapshot"]["turnover_share_pct"], 18.01)
        self.assertTrue(payload["analysis"]["module_logs"])

    def test_snapshot_persistence_hook_saves_appendix_continuity_payloads(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = build_empty_context({"target_date": "2026-04-25"})
            ctx = merge_hook_patches(
                ctx,
                {
                    "derived": {
                        "execution_appendix": {
                            "appendix_b": {
                                "historical_mainline_pool": [{"mainline": "机器人"}],
                                "mainline_switch_log": [{"from_mainline": "低空经济", "to_mainline": "机器人"}],
                                "turnover_share_history": [{"date": "2026-04-24", "mainline": "机器人", "turnover_share_pct": 18.01}],
                                "structure_mainline_records": [{"structure": "日线中枢", "mainline": "机器人"}],
                            },
                            "appendix_c": {
                                "current_stock_monitoring_pool": [{"stock_name": "博杰股份", "stock_code": "002975"}],
                                "stock_lifecycle_records": [
                                    {
                                        "stock_name": "博杰股份",
                                        "stock_code": "002975",
                                        "first_report_date": "2026-04-22",
                                        "source_report_date": "2026-04-22",
                                        "tracked_trading_days": 3,
                                        "daily_change_series": ["2026-04-23:+3.20%", "2026-04-24:+1.10%"],
                                        "volume_change_summary": "放量",
                                        "cumulative_change_pct": 4.33,
                                        "current_interpretation": "趋势延续",
                                        "current_action": "继续跟踪",
                                    }
                                ],
                                "a_kill_elimination_records": [{"stock_name": "冷却股", "stock_code": "000003", "a_kill_date": "2026-04-24"}],
                            },
                        }
                    }
                },
            )

            with patch(
                "hooks.persist.use_snapshot_persistence._save_data_snapshot",
                return_value=str(Path(tmpdir) / "snap.json"),
            ) as mocked:
                run(ctx)

        payload = mocked.call_args[0][0]
        continuity = payload["analysis"]["appendix_continuity"]
        self.assertEqual(continuity["appendix_b"]["historical_mainline_pool"][0]["mainline"], "机器人")
        lifecycle = continuity["appendix_c"]["stock_lifecycle_records"][0]
        self.assertEqual(lifecycle["first_report_date"], "2026-04-22")
        self.assertEqual(lifecycle["source_report_date"], "2026-04-22")
        self.assertEqual(lifecycle["tracked_trading_days"], 3)
        self.assertEqual(lifecycle["daily_change_series"], ["2026-04-23:+3.20%", "2026-04-24:+1.10%"])
        self.assertEqual(lifecycle["volume_change_summary"], "放量")
        self.assertEqual(lifecycle["cumulative_change_pct"], 4.33)
        self.assertEqual(lifecycle["current_interpretation"], "趋势延续")
        self.assertEqual(lifecycle["current_action"], "继续跟踪")
        self.assertEqual(continuity["appendix_c"]["a_kill_elimination_records"][0]["stock_code"], "000003")
