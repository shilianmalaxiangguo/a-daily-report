import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class SnapUiPublicDataPublishNodeTest(unittest.TestCase):
    def test_publish_snap_ui_public_data_writes_manifest_and_checked_tasks(self):
        from publish.snap_ui_public_data import publish_snap_ui_public_data

        calls = []

        def fake_turnover_pipeline(trade_date, **kwargs):
            calls.append(("turnover", trade_date, kwargs))
            return {
                "trade_date": trade_date,
                "quote_count": 5490,
                "rank_count": 100,
                "export": {
                    "r2_key": "exports/turnover/top50-share/latest.json",
                    "local_path": str(Path(kwargs["artifact_root"]) / "exports/turnover/top50-share/latest.json"),
                    "content_hash": "abc123",
                },
            }

        def fake_static_export(root, snap_ui_dir):
            calls.append(("static_export", str(root), str(snap_ui_dir)))
            return {"command": ["npm", "run", "export:static-data"], "returncode": 0}

        def fake_contract_check(root, snap_ui_dir, target_date):
            calls.append(("contract", target_date, str(snap_ui_dir)))
            return {"command": ["npm", "test"], "returncode": 0}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "snap-ui").mkdir()
            result = publish_snap_ui_public_data(
                "2026-05-12",
                root=root,
                turnover_pipeline_runner=fake_turnover_pipeline,
                static_export_runner=fake_static_export,
                contract_check_runner=fake_contract_check,
            )

            manifest_path = Path(result["manifest_path"])
            tasks_path = Path(result["tasks_path"])
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            tasks_markdown = tasks_path.read_text(encoding="utf-8")

            self.assertEqual(result["status"], "success")
            self.assertEqual(manifest["status"], "success")
            self.assertEqual(manifest["target_date"], "2026-05-12")
            self.assertEqual(manifest["data_source"], "tushare")
            self.assertEqual(manifest["turnover"]["quote_count"], 5490)
            self.assertEqual(manifest["turnover"]["rank_count"], 100)
            self.assertEqual(manifest["turnover"]["r2_key"], "exports/turnover/top50-share/latest.json")
            self.assertTrue(manifest_path.exists())
            self.assertTrue(tasks_path.exists())
            self.assertIn("- [x] Fetch Tushare turnover data", tasks_markdown)
            self.assertIn("- [x] Run local data contract check", tasks_markdown)
            self.assertNotIn("Failure:", tasks_markdown)
            self.assertEqual(calls[0][0:2], ("turnover", "2026-05-12"))
            self.assertEqual(Path(calls[0][2]["db_path"]), root / "data" / "cloudflare_free_daily.db")
            self.assertEqual(calls[-1][0], "contract")

    def test_publish_snap_ui_public_data_checks_current_public_latest_when_target_is_historical(self):
        from publish.snap_ui_public_data import publish_snap_ui_public_data

        calls = []

        def fake_turnover_pipeline(trade_date, **kwargs):
            calls.append(("turnover", trade_date))
            return {
                "trade_date": trade_date,
                "quote_count": 5490,
                "rank_count": 100,
                "export": {"r2_key": "exports/turnover/top50-share/latest.json"},
            }

        def fake_static_export(root, snap_ui_dir):
            calls.append(("static_export",))
            return {"command": ["npm", "run", "export:static-data"], "returncode": 0}

        def fake_contract_check(root, snap_ui_dir, expected_latest_date):
            calls.append(("contract", expected_latest_date))
            return {"command": ["npm", "test"], "returncode": 0}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            public_data_dir = root / "snap-ui" / "public" / "data" / "daily-reports"
            public_data_dir.mkdir(parents=True)
            (public_data_dir / "index.json").write_text(
                json.dumps({"reports": [{"date": "2026-05-14"}, {"date": "2026-05-13"}]}),
                encoding="utf-8",
            )

            publish_snap_ui_public_data(
                "2026-05-13",
                root=root,
                turnover_pipeline_runner=fake_turnover_pipeline,
                static_export_runner=fake_static_export,
                contract_check_runner=fake_contract_check,
            )

        self.assertIn(("turnover", "2026-05-14"), calls)
        self.assertNotIn(("turnover", "2026-05-13"), calls)
        self.assertIn(("contract", "2026-05-14"), calls)
        self.assertNotIn(("contract", "2026-05-13"), calls)

    def test_publish_snap_ui_public_data_checks_latest_after_static_export_updates_index(self):
        from publish.snap_ui_public_data import publish_snap_ui_public_data

        calls = []

        def fake_turnover_pipeline(trade_date, **kwargs):
            calls.append(("turnover", trade_date))
            return {
                "trade_date": trade_date,
                "quote_count": 5490,
                "rank_count": 100,
                "export": {"r2_key": "exports/turnover/top50-share/latest.json"},
            }

        def fake_contract_check(root, snap_ui_dir, expected_latest_date):
            calls.append(("contract", expected_latest_date))
            return {"command": ["npm", "test"], "returncode": 0}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            public_data_dir = root / "snap-ui" / "public" / "data" / "daily-reports"
            public_data_dir.mkdir(parents=True)
            index_path = public_data_dir / "index.json"
            index_path.write_text(
                json.dumps({"reports": [{"date": "2026-05-14"}]}),
                encoding="utf-8",
            )

            def fake_static_export(root_arg, snap_ui_dir):
                calls.append(("static_export",))
                index_path.write_text(
                    json.dumps({"reports": [{"date": "2026-05-15"}, {"date": "2026-05-14"}]}),
                    encoding="utf-8",
                )
                return {"command": ["npm", "run", "export:static-data"], "returncode": 0}

            publish_snap_ui_public_data(
                "2026-05-15",
                root=root,
                turnover_pipeline_runner=fake_turnover_pipeline,
                static_export_runner=fake_static_export,
                contract_check_runner=fake_contract_check,
            )

        self.assertIn(("turnover", "2026-05-15"), calls)
        self.assertIn(("contract", "2026-05-15"), calls)

    def test_publish_snap_ui_public_data_records_failure_and_stops_on_contract_error(self):
        from publish.snap_ui_public_data import SnapUiPublicDataPublishError, publish_snap_ui_public_data

        def fake_turnover_pipeline(trade_date, **kwargs):
            return {
                "trade_date": trade_date,
                "quote_count": 10,
                "rank_count": 10,
                "export": {"r2_key": "exports/turnover/top50-share/latest.json"},
            }

        def fake_static_export(root, snap_ui_dir):
            return {"command": ["npm", "run", "export:static-data"], "returncode": 0}

        def failing_contract_check(root, snap_ui_dir, target_date):
            raise subprocess.CalledProcessError(
                returncode=1,
                cmd=["npm", "test"],
                stderr="missing static data",
            )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "snap-ui").mkdir()

            with self.assertRaises(SnapUiPublicDataPublishError):
                publish_snap_ui_public_data(
                    "2026-05-12",
                    root=root,
                    turnover_pipeline_runner=fake_turnover_pipeline,
                    static_export_runner=fake_static_export,
                    contract_check_runner=failing_contract_check,
                )

            manifest_path = root / ".generated/snap-ui-public-data/2026-05-12/snap-ui_publish_manifest.json"
            tasks_path = root / ".generated/snap-ui-public-data/2026-05-12/snap-ui_publish_tasks.md"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            tasks_markdown = tasks_path.read_text(encoding="utf-8")

            self.assertEqual(manifest["status"], "failed")
            self.assertIn("missing static data", manifest["failure"])
            self.assertIn("- [ ] Run local data contract check", tasks_markdown)
            self.assertIn("Failure:", tasks_markdown)

    def test_publish_snap_ui_public_data_normalizes_decision_ledger_index_before_export(self):
        from publish.snap_ui_public_data import publish_snap_ui_public_data

        def fake_turnover_pipeline(trade_date, **kwargs):
            return {
                "trade_date": trade_date,
                "quote_count": 10,
                "rank_count": 10,
                "export": {"r2_key": "exports/turnover/top50-share/latest.json"},
            }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "snap-ui").mkdir()
            ledger_dir = root / "data" / "decision-ledger"
            ledger_dir.mkdir(parents=True)
            stale_index = {
                "artifact_version": 1,
                "latest_trade_date": "2026-05-18",
                "selection_rule_version": "extreme-conviction-ledger-v1",
                "available_trade_dates": ["2026-05-18"],
                "snapshots": [{"trade_date": "2026-05-18", "path": "data/decision-ledger/2026-05-18.json"}],
                "selection_input_hash_by_trade_date": {"2026-05-18": "a" * 64},
                "by_stock_code": {
                    "002342": [
                        {
                            "case_id": "2026-05-18-002342-01",
                            "stock_code": "002342",
                            "stock_name": "巨力索具",
                            "mentions": [
                                {
                                    "mention_trade_date": "2026-05-18",
                                    "source_section": "极度看好名单",
                                    "planned_participation": {"source_tier": "extreme_conviction", "buy_window": "09:50-10:10"},
                                }
                            ],
                        }
                    ]
                },
                "extreme_conviction_backtest_rows": [
                    {
                        "mention_trade_date": "2026-05-18",
                        "stock_code": "002342",
                        "stock_name": "巨力索具",
                        "selection_quality": "高惯性",
                        "buy_window": "09:50-10:10",
                        "risk_reward": "待计算",
                        "buy_point_quality": "等待事实",
                        "review_status": "等待复盘",
                        "standard_action": "等待计划窗口事实回写",
                    }
                ],
            }
            snapshot = {
                "artifact_version": 1,
                "frozen": True,
                "trade_date": "2026-05-18",
                "selection_rule_version": "extreme-conviction-ledger-v1",
                "selection_input_hash": "b" * 64,
                "cases": [
                    {
                        "case_id": "2026-05-18-001259-01",
                        "stock_code": "001259",
                        "stock_name": "利仁科技",
                        "first_seen_trade_date": "2026-05-18",
                        "cycle_start_trade_date": "2026-05-18",
                        "cycle_day": 1,
                        "cycle_length_trade_days": 25,
                        "hypothesis": {
                            "stock_setup": "板块锚定龙",
                            "sector_candidate": "股权转让",
                            "market_branch": "收缩防守",
                        },
                        "validation": {"status": "等待市场选择"},
                        "planned_participation": {
                            "source_tier": "extreme_conviction",
                            "participation_window": "竞价表态 + 回封参与",
                            "participation_window_type": "auction_reseal",
                            "attack_state": "50%",
                            "buy_window": "09:30-09:35",
                            "risk_reward_state": "待计算",
                            "risk_reward_ratio": 2,
                        },
                        "mentions": [
                            {
                                "mention_trade_date": "2026-05-18",
                                "rank": 1,
                                "reason": "板块锚定龙",
                                "source_section": "极度看好名单",
                                "planned_participation": {
                                    "source_tier": "extreme_conviction",
                                    "buy_window": "09:30-09:35",
                                    "risk_reward_state": "待计算",
                                    "risk_reward_ratio": 2,
                                },
                            }
                        ],
                    }
                ],
            }
            (ledger_dir / "index.json").write_text(json.dumps(stale_index, ensure_ascii=False), encoding="utf-8")
            (ledger_dir / "2026-05-18.json").write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")

            export_seen = {}

            def fake_static_export(root_arg, snap_ui_dir):
                export_seen["index"] = json.loads((Path(root_arg) / "data" / "decision-ledger" / "index.json").read_text(encoding="utf-8"))
                return {"command": ["npm", "run", "export:static-data"], "returncode": 0}

            publish_snap_ui_public_data(
                "2026-05-18",
                root=root,
                turnover_pipeline_runner=fake_turnover_pipeline,
                static_export_runner=fake_static_export,
                contract_check_runner=lambda root_arg, snap_ui_dir, target_date: {"command": ["npm", "test"], "returncode": 0},
            )

            rows = export_seen["index"]["extreme_conviction_backtest_rows"]
            self.assertEqual([row["stock_code"] for row in rows], ["001259"])
            self.assertNotIn("002342", export_seen["index"]["by_stock_code"])
            self.assertEqual(export_seen["index"]["selection_input_hash_by_trade_date"]["2026-05-18"], "b" * 64)


if __name__ == "__main__":
    unittest.main()
