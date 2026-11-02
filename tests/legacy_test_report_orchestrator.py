import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from orchestrator.report_orchestrator import build_report


def stub_hot_rank(ctx):
    return {
        "value": {"hot_rank": [{"code": "000001", "sector": "军工"}]},
        "patches": {
            "raw": {"hot_rank": [{"code": "000001", "sector": "军工"}]},
            "normalized": {"market_snapshot": {"hot_rank_count": 1}},
            "diagnostics": {
                "derivations": {
                    "input.hot_rank": {"hook_name": "input.hot_rank", "stage": "input"}
                }
            },
        },
        "diagnostics": {"hook_name": "input.hot_rank", "status": "success", "warnings": []},
        "artifacts": {},
    }


def stub_market_phase(ctx):
    return {
        "value": {"market_phase": "observe"},
        "patches": {
            "derived": {"market_phase": {"phase": "observe"}},
            "diagnostics": {
                "derivations": {
                    "market_phase": {"hook_name": "infer.market_phase", "phase": "observe"}
                }
            },
        },
        "diagnostics": {"hook_name": "infer.market_phase", "status": "success", "warnings": []},
        "artifacts": {},
    }


def stub_mainline(ctx):
    return {
        "value": {"mainline": "军工"},
        "patches": {
            "derived": {"mainline": {"primary_line": "军工"}},
            "diagnostics": {
                "derivations": {
                    "mainline": {"hook_name": "infer.mainline", "primary_line": "军工"}
                }
            },
        },
        "diagnostics": {"hook_name": "infer.mainline", "status": "success", "warnings": []},
        "artifacts": {},
    }


def stub_execution_permission(ctx):
    return {
        "value": {"execution_permission": "watch_only"},
        "patches": {
            "derived": {"execution_permission": {"label": "watch_only"}},
            "decision": {"execution_permission": {"label": "watch_only"}},
            "diagnostics": {
                "derivations": {
                    "execution_permission": {
                        "hook_name": "infer.execution_permission",
                        "label": "watch_only",
                    }
                }
            },
        },
        "diagnostics": {
            "hook_name": "infer.execution_permission",
            "status": "success",
            "warnings": [],
        },
        "artifacts": {},
    }


def stub_markdown_document(ctx):
    sections = ctx.get("sections") or {}
    markdown = "\n\n".join(
        str(sections.get(key, "") or "").strip()
        for key in ["preamble", "environment", "observation", "execution", "review", "summary"]
        if sections.get(key)
    )
    return {
        "value": {"markdown_document": markdown},
        "patches": {"rendered": {"markdown_document": markdown}},
        "diagnostics": {"hook_name": "report.markdown_document", "status": "success", "warnings": []},
        "artifacts": {},
    }


def stub_snapshot(ctx):
    return {
        "value": {"snapshot_path": "/tmp/report-snapshot.json"},
        "patches": {},
        "diagnostics": {"hook_name": "persist.snapshot", "status": "success", "warnings": []},
        "artifacts": {"snapshot_path": "/tmp/report-snapshot.json"},
    }


class ReportOrchestratorTest(unittest.TestCase):
    def test_build_report_runs_full_chain_and_preserves_nested_derivations(self):
        with patch("orchestrator.report_orchestrator.run_hot_rank", stub_hot_rank), patch(
            "orchestrator.report_orchestrator.run_market_phase", stub_market_phase
        ), patch("orchestrator.report_orchestrator.run_mainline_analysis", stub_mainline), patch(
            "orchestrator.report_orchestrator.run_execution_permission", stub_execution_permission
        ), patch(
            "orchestrator.report_orchestrator.run_markdown_document", stub_markdown_document
        ), patch(
            "orchestrator.report_orchestrator.run_snapshot_persistence", stub_snapshot
        ):
            ctx = build_report({"target_date": "2026-04-21"})

        self.assertEqual(ctx["raw"]["hot_rank"][0]["code"], "000001")
        self.assertEqual(ctx["derived"]["market_phase"]["phase"], "observe")
        self.assertEqual(ctx["derived"]["mainline"]["primary_line"], "军工")
        self.assertEqual(ctx["derived"]["execution_permission"]["label"], "watch_only")
        self.assertEqual(
            ctx["diagnostics"]["derivations"]["market_phase"]["hook_name"],
            "infer.market_phase",
        )
        self.assertEqual(
            ctx["diagnostics"]["derivations"]["mainline"]["hook_name"],
            "infer.mainline",
        )
        self.assertEqual(
            ctx["diagnostics"]["derivations"]["strategy_contract"]["hook_name"],
            "infer.strategy_contract",
        )
        self.assertEqual(
            ctx["diagnostics"]["derivations"]["action_plan"]["hook_name"],
            "decision.action_plan",
        )
        self.assertEqual(
            ctx["diagnostics"]["derivations"]["execution_permission"]["hook_name"],
            "infer.execution_permission",
        )
        self.assertEqual(ctx["knowledge"]["trading_philosophy"]["source"], "skillhub")
        self.assertEqual(ctx["knowledge"]["llm_wiki"]["source"], "llm_wiki")
        self.assertIn("固定交易窗口条件", ctx["knowledge"]["llm_wiki"]["report_digest_text"])
        self.assertIn("09:50-10:10窗口", ctx["knowledge"]["llm_wiki"]["report_digest_text"])
        self.assertIn("process_flows", ctx["knowledge"]["llm_wiki"])
        self.assertEqual(
            ctx["knowledge"]["llm_wiki"]["knowledge_trace"]["schema_version"],
            "knowledge_trace.v1",
        )
        self.assertEqual(
            ctx["knowledge"]["llm_wiki"]["knowledge_hits"],
            ctx["knowledge"]["llm_wiki"]["knowledge_trace"]["hits"],
        )
        self.assertIn("选股形态审美 ASCII 流程图", "\n".join(ctx["knowledge"]["llm_wiki"]["process_flows"]))
        self.assertIn("环境条件满足", ctx["knowledge"]["trading_philosophy"]["decision_gate_chain"])
        self.assertIn("#", ctx["rendered"]["markdown_document"])
        self.assertIn("watch_only", ctx["rendered"]["markdown_document"])
        self.assertIn(
            f"LLM Wiki版本：{ctx['knowledge']['llm_wiki']['version']}",
            ctx["rendered"]["markdown_document"],
        )
        self.assertIn("选股形态审美 ASCII 流程图", ctx["rendered"]["markdown_document"])
        self.assertIn("fetch_recent_price_bars", ctx["rendered"]["markdown_document"])
        self.assertNotIn("交易理念底线", ctx["rendered"]["markdown_document"])
        self.assertNotIn("教你炒股票", ctx["rendered"]["markdown_document"])
        self.assertNotIn("能量学", ctx["rendered"]["markdown_document"])
        hook_names = [item["hook_name"] for item in ctx["runtime"]["module_logs"]]
        self.assertIn("persist.snapshot", hook_names)
        self.assertLess(
            hook_names.index("decision.action_plan"),
            hook_names.index("knowledge.llm_wiki"),
        )

    def test_postgres_only_request_skips_json_snapshot_hook(self):
        with patch("orchestrator.report_orchestrator.run_hot_rank", stub_hot_rank), patch(
            "orchestrator.report_orchestrator.run_market_phase", stub_market_phase
        ), patch("orchestrator.report_orchestrator.run_mainline_analysis", stub_mainline), patch(
            "orchestrator.report_orchestrator.run_execution_permission", stub_execution_permission
        ), patch(
            "orchestrator.report_orchestrator.run_markdown_document", stub_markdown_document
        ), patch(
            "orchestrator.report_orchestrator.run_snapshot_persistence", side_effect=stub_snapshot
        ) as snapshot_mock:
            ctx = build_report({"target_date": "2026-04-21", "postgres_only": True})

        hook_names = [item["hook_name"] for item in ctx["runtime"]["module_logs"]]
        self.assertNotIn("persist.snapshot", hook_names)
        snapshot_mock.assert_not_called()
