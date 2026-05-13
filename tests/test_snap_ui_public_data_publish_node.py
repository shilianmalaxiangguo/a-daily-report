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
            self.assertEqual(calls[-1][0], "contract")

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


if __name__ == "__main__":
    unittest.main()
