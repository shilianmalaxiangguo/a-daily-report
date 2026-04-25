import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from hooks.persist.use_snapshot_persistence import run
from orchestrator.context_store import build_empty_context, merge_hook_patches


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
