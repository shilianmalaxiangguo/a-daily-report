import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report import candidate_trace_artifacts as artifacts
from report.candidate_trace_artifacts import write_candidate_trace_artifact
from selection.candidate_trace_contracts import build_candidate_trace


class CandidateTraceArtifactsTest(unittest.TestCase):
    def test_write_candidate_trace_artifact(self):
        trace = build_candidate_trace({"name": "华天科技", "code": "002185", "tier": "T0"})
        with tempfile.TemporaryDirectory() as tempdir:
            result = write_candidate_trace_artifact(
                trade_date="2026-05-26",
                traces=[trace],
                eliminated_summary=[
                    {"reason": "主线不匹配", "count": 1, "representatives": ["大众公用"], "treatment": "保留观察，不进入动作分层"}
                ],
                root_dir=Path(tempdir),
                generated_at="2026-05-27T00:00:00+08:00",
                source_report={"path": "reports/2026-05-26_A股日报_完整版.md", "variant": "full"},
            )

            path = Path(result["artifact_path"])
            self.assertTrue(path.exists())
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["trade_date"], "2026-05-26")
            self.assertEqual(payload["traces"][0]["stock_code"], "002185")
            self.assertEqual(result["trace_count"], 1)
            self.assertEqual(result["eliminated_group_count"], 1)

    def test_postgres_configured_candidate_trace_uses_database_service(self):
        trace = build_candidate_trace({"name": "华天科技", "code": "002185", "tier": "T0"})

        class StubService:
            def __init__(self):
                self.saved_payload = None

            def is_postgres_backed(self):
                return True

            def replace_candidate_trace_artifact(self, payload):
                self.saved_payload = dict(payload)
                return {
                    "artifact_path": "postgresql://candidate-traces/2026-05-26",
                    "trace_count": len(payload.get("traces") or []),
                    "eliminated_group_count": len(payload.get("eliminated_summary") or []),
                }

        service = StubService()

        class StubDatabaseService:
            @classmethod
            def from_environment(cls, db_path=None):
                return service

        with tempfile.TemporaryDirectory() as tempdir:
            with patch.object(artifacts, "DatabaseService", StubDatabaseService, create=True):
                with patch.dict("os.environ", {"A_DAILY_REPORT_DATABASE_URL": "postgresql://unit/report"}, clear=False):
                    result = write_candidate_trace_artifact(
                        trade_date="2026-05-26",
                        traces=[trace],
                        eliminated_summary=[],
                        root_dir=Path(tempdir),
                        generated_at="2026-05-27T00:00:00+08:00",
                        source_report={"path": "reports/2026-05-26_A股日报_完整版.md", "variant": "full"},
                    )

            json_path = Path(tempdir) / "data" / "candidate-traces" / "2026-05-26.json"

        self.assertEqual(service.saved_payload["trade_date"], "2026-05-26")
        self.assertEqual(result["artifact_path"], "postgresql://candidate-traces/2026-05-26")
        self.assertEqual(result["trace_count"], 1)
        self.assertFalse(json_path.exists())

    def test_postgres_configured_missing_writer_does_not_write_json(self):
        trace = build_candidate_trace({"name": "华天科技", "code": "002185", "tier": "T0"})

        class StubService:
            def is_postgres_backed(self):
                return True

        class StubDatabaseService:
            @classmethod
            def from_environment(cls, db_path=None):
                return StubService()

        with tempfile.TemporaryDirectory() as tempdir:
            with patch.object(artifacts, "DatabaseService", StubDatabaseService, create=True):
                with patch.dict("os.environ", {"A_DAILY_REPORT_DATABASE_URL": "postgresql://unit/report"}, clear=False):
                    with self.assertRaisesRegex(RuntimeError, "candidate trace writer"):
                        write_candidate_trace_artifact(
                            trade_date="2026-05-26",
                            traces=[trace],
                            eliminated_summary=[],
                            root_dir=Path(tempdir),
                            generated_at="2026-05-27T00:00:00+08:00",
                            source_report={"path": "reports/2026-05-26_A股日报_完整版.md", "variant": "full"},
                        )

            json_path = Path(tempdir) / "data" / "candidate-traces" / "2026-05-26.json"
            self.assertFalse(json_path.exists())

    def test_postgres_only_runtime_without_postgres_does_not_write_json(self):
        trace = build_candidate_trace({"name": "华天科技", "code": "002185", "tier": "T0"})

        with tempfile.TemporaryDirectory() as tempdir:
            with patch.dict("os.environ", {"A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME": "1"}, clear=True):
                with self.assertRaisesRegex(RuntimeError, "PostgreSQL-only"):
                    write_candidate_trace_artifact(
                        trade_date="2026-05-26",
                        traces=[trace],
                        eliminated_summary=[],
                        root_dir=Path(tempdir),
                        generated_at="2026-05-27T00:00:00+08:00",
                        source_report={"path": "reports/2026-05-26_A股日报_完整版.md", "variant": "full"},
                    )

            json_path = Path(tempdir) / "data" / "candidate-traces" / "2026-05-26.json"
            self.assertFalse(json_path.exists())


if __name__ == "__main__":
    unittest.main()
