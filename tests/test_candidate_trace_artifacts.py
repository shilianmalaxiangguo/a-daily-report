import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

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


if __name__ == "__main__":
    unittest.main()
