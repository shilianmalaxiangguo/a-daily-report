import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from agent_runner.daily_report_agent_runner import (
    DailyReportAgentDependencies,
    DailyReportAgentRequest,
    DailyReportAgentRunner,
)


class DailyReportAgentRunnerTest(unittest.TestCase):
    def test_runner_defaults_to_replay_mode_without_live_data(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            def load_data(request):
                self.assertEqual(request.mode, "replay")
                return {}

            def save_outputs(outputs, target_date, mode, output_dir=None):
                output_root = Path(output_dir)
                output_root.mkdir(parents=True, exist_ok=True)
                report_path = output_root / "full.md"
                report_path.write_text(outputs["full"], encoding="utf-8")
                return {"full": str(report_path)}

            runner = DailyReportAgentRunner(
                root_dir=root,
                dependencies=DailyReportAgentDependencies(
                    load_data=load_data,
                    build_report_outputs=lambda data, target_date, **kwargs: {"full": "# report"},
                    save_report_outputs=save_outputs,
                    write_decision_ledger_from_markdown=lambda report_path, **kwargs: {"case_count": 0},
                    audit_run=lambda **kwargs: {
                        "target_date": kwargs["target_date"],
                        "passed": True,
                        "usable": True,
                        "findings": [],
                        "finding_count": 0,
                    },
                    now=lambda: datetime(2026, 5, 24, 15, 1, 2),
                ),
            )

            result = runner.run(DailyReportAgentRequest(target_date="2026-05-24"))

            self.assertEqual(result["mode"], "replay")
            self.assertEqual(result["status"], "error")

    def test_runner_rejects_non_replay_mode_without_live_data(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            runner = DailyReportAgentRunner(
                root_dir=root,
                dependencies=DailyReportAgentDependencies(
                    now=lambda: datetime(2026, 5, 24, 15, 1, 2),
                ),
            )

            result = runner.run(DailyReportAgentRequest(target_date="2026-05-24", mode="fresh"))

            self.assertEqual(result["status"], "error")
            self.assertEqual(result["error"]["message"], "当前 runner 仅支持 replay 模式")
            self._assert_error_run_artifacts(root, expected_code="unsupported_run_mode")

    def test_runner_stops_when_replay_snapshot_data_is_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            def build_outputs(data, target_date, **kwargs):
                raise AssertionError("report rendering should not run without replay data")

            runner = DailyReportAgentRunner(
                root_dir=root,
                dependencies=DailyReportAgentDependencies(
                    load_data=lambda request: {},
                    build_report_outputs=build_outputs,
                    now=lambda: datetime(2026, 5, 24, 15, 1, 2),
                ),
            )

            result = runner.run(DailyReportAgentRequest(target_date="2026-05-24", mode="replay"))

            self.assertEqual(result["status"], "error")
            self.assertEqual(result["error"]["message"], "回放数据不存在，停止生成：2026-05-24")
            self._assert_error_run_artifacts(root, expected_code="replay_data_missing")

    def test_runner_writes_run_artifacts_and_pending_participation_review(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            def load_data(request):
                self.assertEqual(request.target_date, "2026-05-24")
                self.assertEqual(request.mode, "replay")
                return {"sections": {"summary": "## 七、最终结论\n50% / 标准进攻"}}

            def build_outputs(data, target_date, **kwargs):
                self.assertFalse(kwargs["emit_preflight"])
                self.assertEqual(kwargs["run_mode"], "replay")
                return {
                    "full": "# full report\n\n## 七、最终结论\n50% / 标准进攻",
                    "summary": "# summary",
                }

            def save_outputs(outputs, target_date, mode, output_dir=None):
                output_root = Path(output_dir)
                output_root.mkdir(parents=True, exist_ok=True)
                full_path = output_root / f"{target_date}_A股日报_完整版_replay.md"
                summary_path = output_root / f"{target_date}_A股日报_执行摘要_replay.md"
                full_path.write_text(outputs["full"], encoding="utf-8")
                summary_path.write_text(outputs["summary"], encoding="utf-8")
                return {"full": str(full_path), "summary": str(summary_path)}

            def write_ledger(report_path, **kwargs):
                self.assertTrue(str(report_path).endswith("2026-05-24_A股日报_完整版_replay.md"))
                self.assertEqual(kwargs["trade_date"], "2026-05-24")
                self.assertEqual(kwargs["root_dir"], str(root))
                self.assertEqual(kwargs["generated_at"], "2026-05-24T15:01:02")
                return {
                    "snapshot_path": str(root / "data" / "decision-ledger" / "2026-05-24.json"),
                    "index_path": str(root / "data" / "decision-ledger" / "index.json"),
                    "case_count": 1,
                    "fact_db_sync": {"status": "success", "rows": 1},
                    "index": {
                        "by_stock_code": {
                            "300000": [
                                {
                                    "stock_code": "300000",
                                    "stock_name": "测试股份",
                                    "participation_review_status": "等待复盘",
                                }
                            ]
                        }
                    },
                }

            def audit_run(**kwargs):
                self.assertEqual(kwargs["decision_ledger_result"]["case_count"], 1)
                return {
                    "target_date": kwargs["target_date"],
                    "passed": True,
                    "usable": True,
                    "findings": [],
                    "finding_count": 0,
                    "preflight": {"status": "success", "failures": []},
                    "report_acceptance": {"passed": True, "findings": [], "finding_count": 0},
                    "decision_ledger": {"passed": True, "case_count": 1, "findings": []},
                }

            runner = DailyReportAgentRunner(
                root_dir=root,
                dependencies=DailyReportAgentDependencies(
                    load_data=load_data,
                    build_report_outputs=build_outputs,
                    save_report_outputs=save_outputs,
                    write_decision_ledger_from_markdown=write_ledger,
                    audit_run=audit_run,
                    now=lambda: datetime(2026, 5, 24, 15, 1, 2),
                ),
            )

            result = runner.run(DailyReportAgentRequest(target_date="2026-05-24", mode="replay"))

            run_dir = root / "reports" / "runs" / "2026-05-24"
            self.assertEqual(result["run_dir"], str(run_dir))
            self.assertTrue((run_dir / "overview.md").exists())
            self.assertTrue((run_dir / "run.json").exists())
            self.assertTrue((run_dir / "audit.json").exists())
            self.assertTrue((run_dir / "review_queue.md").exists())

            payload = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "success")
            self.assertTrue(payload["audit"]["passed"])
            self.assertEqual(payload["decision_ledger"]["case_count"], 1)

            audit_payload = json.loads((run_dir / "audit.json").read_text(encoding="utf-8"))
            self.assertTrue(audit_payload["passed"])

            review_queue = (run_dir / "review_queue.md").read_text(encoding="utf-8")
            self.assertIn("测试股份", review_queue)
            self.assertIn("300000", review_queue)

    def test_runner_records_audit_failure_in_review_queue(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            def save_outputs(outputs, target_date, mode, output_dir=None):
                output_root = Path(output_dir)
                output_root.mkdir(parents=True, exist_ok=True)
                report_path = output_root / "full.md"
                report_path.write_text(outputs["full"], encoding="utf-8")
                return {"full": str(report_path)}

            runner = DailyReportAgentRunner(
                root_dir=root,
                dependencies=DailyReportAgentDependencies(
                    load_data=lambda request: {"sample": True},
                    build_report_outputs=lambda data, target_date, **kwargs: {"full": "# report"},
                    save_report_outputs=save_outputs,
                    write_decision_ledger_from_markdown=lambda report_path, **kwargs: {"case_count": 0},
                    audit_run=lambda **kwargs: {
                        "target_date": kwargs["target_date"],
                        "passed": False,
                        "usable": False,
                        "findings": [
                            {
                                "source": "preflight",
                                "code": "critical_data_incomplete",
                                "message": "关键数据不完整，停止生成：中证全指",
                            }
                        ],
                        "finding_count": 1,
                        "preflight": {"status": "failed", "failures": ["中证全指"]},
                        "report_acceptance": {"passed": True, "findings": [], "finding_count": 0},
                        "decision_ledger": {"passed": True, "case_count": 0, "findings": []},
                    },
                    now=lambda: datetime(2026, 5, 24, 15, 1, 2),
                ),
            )

            runner.run(DailyReportAgentRequest(target_date="2026-05-24", mode="replay"))

            review_queue = root / "reports" / "runs" / "2026-05-24" / "review_queue.md"
            review_text = review_queue.read_text(encoding="utf-8")
            self.assertIn("critical_data_incomplete", review_text)
            self.assertIn("关键数据不完整，停止生成：中证全指", review_text)

    def test_runner_writes_error_artifacts_when_rendering_fails_without_live_data(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            def build_outputs(data, target_date, **kwargs):
                raise RuntimeError("render boom")

            runner = DailyReportAgentRunner(
                root_dir=root,
                dependencies=DailyReportAgentDependencies(
                    load_data=lambda request: {"sample": True},
                    build_report_outputs=build_outputs,
                    now=lambda: datetime(2026, 5, 24, 15, 1, 2),
                ),
            )

            runner.run(DailyReportAgentRequest(target_date="2026-05-24", mode="replay"))

            self._assert_error_run_artifacts(root)

    def test_runner_writes_error_artifacts_when_audit_fails_without_live_data(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            def save_outputs(outputs, target_date, mode, output_dir=None):
                output_root = Path(output_dir)
                output_root.mkdir(parents=True, exist_ok=True)
                report_path = output_root / "full.md"
                report_path.write_text(outputs["full"], encoding="utf-8")
                return {"full": str(report_path)}

            def audit_run(**kwargs):
                raise RuntimeError("audit boom")

            runner = DailyReportAgentRunner(
                root_dir=root,
                dependencies=DailyReportAgentDependencies(
                    load_data=lambda request: {"sample": True},
                    build_report_outputs=lambda data, target_date, **kwargs: {"full": "# report"},
                    save_report_outputs=save_outputs,
                    write_decision_ledger_from_markdown=lambda report_path, **kwargs: {"case_count": 0},
                    audit_run=audit_run,
                    now=lambda: datetime(2026, 5, 24, 15, 1, 2),
                ),
            )

            runner.run(DailyReportAgentRequest(target_date="2026-05-24", mode="replay"))

            self._assert_error_run_artifacts(root)

    def _assert_error_run_artifacts(self, root, expected_code="runner_error"):
        run_dir = root / "reports" / "runs" / "2026-05-24"
        self.assertTrue((run_dir / "run.json").exists())
        self.assertTrue((run_dir / "audit.json").exists())
        self.assertTrue((run_dir / "overview.md").exists())
        self.assertTrue((run_dir / "review_queue.md").exists())

        payload = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["audit"]["findings"][0]["code"], expected_code)

        audit_payload = json.loads((run_dir / "audit.json").read_text(encoding="utf-8"))
        self.assertEqual(audit_payload["findings"][0]["code"], expected_code)


if __name__ == "__main__":
    unittest.main()
