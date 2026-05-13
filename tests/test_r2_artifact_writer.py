import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class R2ArtifactWriterTest(unittest.TestCase):
    def test_build_put_command_uses_bucket_key_and_file_path(self):
        from export.r2_artifact_writer import R2ArtifactWriter

        writer = R2ArtifactWriter(bucket_name="a-daily-report-artifacts", wrangler_command=["npx", "wrangler"])
        command = writer.build_put_command(
            "exports/turnover/top50-share/latest.json",
            "/tmp/latest.json",
        )

        self.assertEqual(
            command,
            [
                "npx",
                "wrangler",
                "r2",
                "object",
                "put",
                "a-daily-report-artifacts/exports/turnover/top50-share/latest.json",
                "--remote",
                "--file",
                "/tmp/latest.json",
            ],
        )

    def test_upload_local_artifact_can_run_with_injected_runner(self):
        from export.r2_artifact_writer import R2ArtifactWriter

        calls = []

        def fake_runner(command):
            calls.append(command)
            return {"returncode": 0, "stdout": "ok", "stderr": ""}

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "latest.json"
            path.write_text("{}", encoding="utf-8")
            writer = R2ArtifactWriter(bucket_name="bucket", command_runner=fake_runner)
            result = writer.upload_local_artifact("exports/latest.json", path)

        self.assertEqual(result["status"], "success")
        self.assertEqual(calls[0][4], "bucket/exports/latest.json")
        self.assertEqual(calls[0][7], str(path))

    def test_upload_local_artifact_fails_when_file_is_missing(self):
        from export.r2_artifact_writer import R2ArtifactWriter

        writer = R2ArtifactWriter(bucket_name="bucket")

        with self.assertRaises(FileNotFoundError):
            writer.upload_local_artifact("exports/missing.json", "/tmp/definitely-missing.json")


if __name__ == "__main__":
    unittest.main()
