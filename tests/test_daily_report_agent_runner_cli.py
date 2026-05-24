import io
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from agent_runner.daily_report_agent_runner import DailyReportAgentRequest
from agent_runner.run_daily_report_agent import main


class DailyReportAgentRunnerCliTest(unittest.TestCase):
    def test_cli_runs_replay_request_and_prints_run_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            captured = {}

            class FakeRunner:
                def __init__(self, *, root_dir):
                    captured["root_dir"] = root_dir

                def run(self, request):
                    captured["request"] = request
                    return {
                        "status": "success",
                        "run_dir": str(root / "reports" / "runs" / request.target_date),
                        "audit": {"passed": True},
                        "error": None,
                    }

            with patch("agent_runner.run_daily_report_agent.DailyReportAgentRunner", FakeRunner):
                stdout = io.StringIO()
                with redirect_stdout(stdout):
                    exit_code = main(["2026-05-24", "--root-dir", str(root)])

            self.assertEqual(exit_code, 0)
            self.assertIn("status: success", stdout.getvalue())
            self.assertEqual(captured["root_dir"], root)
            self.assertEqual(
                captured["request"],
                DailyReportAgentRequest(target_date="2026-05-24", mode="replay"),
            )

    def test_cli_script_runs_from_repo_root(self):
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "agent_runner" / "run_daily_report_agent.py"),
                "--help",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("target_date", result.stdout)


if __name__ == "__main__":
    unittest.main()
