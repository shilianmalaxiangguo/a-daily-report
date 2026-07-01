import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from observability.report_quality import build_report_quality_score, persist_report_quality_score


class ReportQualityObservabilityTest(unittest.TestCase):
    def test_quality_score_passes_complete_run(self):
        score = build_report_quality_score(
            target_date="2026-05-24",
            run_status="success",
            mode="replay",
            preflight={"status": "success", "failures": []},
            audit_result={
                "passed": True,
                "findings": [],
                "finding_count": 0,
                "decision_ledger": {"passed": True},
            },
            decision_ledger_result={"case_count": 1, "fact_db_sync": {"status": "success"}},
            output_paths={"full": "/tmp/full.md"},
        )

        self.assertEqual(score["schema_version"], "report_quality_score.v1")
        self.assertEqual(score["status"], "pass")
        self.assertEqual(score["score"], 100)
        self.assertTrue(score["categories"]["data_readiness"]["passed"])

    def test_quality_score_surfaces_data_and_acceptance_findings(self):
        score = build_report_quality_score(
            target_date="2026-05-24",
            run_status="needs_review",
            mode="replay",
            preflight={"status": "failed", "failures": ["中证全指"]},
            audit_result={
                "passed": False,
                "findings": [
                    {
                        "source": "report_acceptance",
                        "code": "final_action_conflict",
                        "message": "最终结论不一致",
                    }
                ],
                "finding_count": 1,
                "decision_ledger": {"passed": False},
            },
            decision_ledger_result={"findings": [{"code": "decision_ledger_missing"}]},
            output_paths={},
        )

        self.assertEqual(score["status"], "fail")
        self.assertFalse(score["categories"]["data_readiness"]["passed"])
        self.assertFalse(score["categories"]["report_acceptance"]["passed"])
        self.assertEqual(score["finding_count"], 2)
        self.assertEqual(score["top_findings"][0]["code"], "critical_data_incomplete")

    def test_quality_score_marks_run_error(self):
        score = build_report_quality_score(
            target_date="2026-05-24",
            run_status="error",
            error="关键数据不完整，停止生成",
        )

        self.assertEqual(score["status"], "error")
        self.assertFalse(score["categories"]["run_completion"]["passed"])
        self.assertEqual(score["top_findings"][-1]["source"], "run")

    def test_quality_score_does_not_penalize_skipped_report_artifacts(self):
        score = build_report_quality_score(
            target_date="2026-05-24",
            run_status="success",
            preflight={"status": "success", "failures": []},
            report_expected=False,
            decision_ledger_expected=False,
        )

        self.assertTrue(score["categories"]["artifact_integrity"]["passed"])
        self.assertTrue(score["categories"]["decision_ledger"]["passed"])

    def test_persist_quality_score_writes_snapshot_and_index(self):
        score = build_report_quality_score(
            target_date="2026-05-24",
            run_status="success",
            mode="replay",
            preflight={"status": "success", "failures": []},
            audit_result={"passed": True, "findings": [], "finding_count": 0},
            decision_ledger_result={"case_count": 1, "fact_db_sync": {"status": "success"}},
            output_paths={"full": "/tmp/full.md"},
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            result = persist_report_quality_score(
                score,
                root_dir=Path(tmpdir),
                run_id="unit-run",
                recorded_at="2026-05-24T15:01:02",
            )

            self.assertEqual(result["status"], "written")
            score_path = Path(result["score_path"])
            index_path = Path(result["index_path"])
            self.assertTrue(score_path.exists())
            self.assertTrue(index_path.exists())
            self.assertEqual(score_path.name, "2026-05-24_replay.json")

            snapshot = json.loads(score_path.read_text(encoding="utf-8"))
            self.assertEqual(snapshot["schema_version"], "report_quality_ledger_record.v1")
            self.assertEqual(snapshot["run_id"], "unit-run")
            self.assertEqual(snapshot["report_quality_score"]["schema_version"], "report_quality_score.v1")

            index_lines = index_path.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(index_lines), 1)
            record = json.loads(index_lines[0])
            self.assertEqual(record["target_date"], "2026-05-24")
            self.assertEqual(record["mode"], "replay")
            self.assertEqual(record["status"], "pass")
            self.assertEqual(record["score"], 100)


if __name__ == "__main__":
    unittest.main()
