import io
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from orchestrator.run_log_runtime import TeeStream, run_with_log_capture


class RunLogRuntimeTest(unittest.TestCase):
    def test_tee_stream_exposes_fileno_from_wrapped_stream(self):
        class _StreamWithFileno(io.StringIO):
            def fileno(self):
                return 42

        tee = TeeStream(_StreamWithFileno(), io.StringIO())

        self.assertEqual(tee.fileno(), 42)

    def test_run_with_log_capture_keeps_logging_after_importing_entry_module(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            def main_fn():
                sys.path.insert(0, str(ROOT / "scripts"))
                __import__("daily_report_entry_demo")
                print("after import still logged")
                print("stderr also logged", file=sys.stderr)
                return 0

            exit_code = run_with_log_capture(
                main_fn,
                argv=["daily_report_entry_demo.py", "--help"],
                logs_root=tmpdir,
                now=datetime(2026, 4, 23, 16, 30, 0),
            )

            self.assertEqual(exit_code, 0)
            run_logs = sorted((Path(tmpdir) / "runs").glob("*.log"))
            self.assertEqual(len(run_logs), 1)
            log_text = run_logs[0].read_text(encoding="utf-8")
            self.assertIn("after import still logged", log_text)
            self.assertIn("stderr also logged", log_text)

    def test_run_with_log_capture_writes_run_log_and_preserves_output(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            stdout_buffer = io.StringIO()
            stderr_buffer = io.StringIO()

            def main_fn():
                print("hello stdout")
                print("hello stderr", file=sys.stderr)
                return 0

            original_stdout = sys.stdout
            original_stderr = sys.stderr
            sys.stdout = stdout_buffer
            sys.stderr = stderr_buffer
            try:
                exit_code = run_with_log_capture(
                    main_fn,
                    argv=["daily_report_entry_demo.py", "2026-04-22", "--replay"],
                    logs_root=tmpdir,
                    now=datetime(2026, 4, 23, 15, 30, 0),
                )
            finally:
                sys.stdout = original_stdout
                sys.stderr = original_stderr

            self.assertEqual(exit_code, 0)
            self.assertIn("hello stdout", stdout_buffer.getvalue())
            self.assertIn("hello stderr", stderr_buffer.getvalue())

            run_logs = sorted((Path(tmpdir) / "runs").glob("*.log"))
            self.assertEqual(len(run_logs), 1)
            log_text = run_logs[0].read_text(encoding="utf-8")
            self.assertIn("hello stdout", log_text)
            self.assertIn("hello stderr", log_text)
            self.assertIn("--replay", log_text)
            latest_run = json.loads((Path(tmpdir) / "latest_run.json").read_text(encoding="utf-8"))
            self.assertEqual(latest_run["status"], "success")
            self.assertEqual(latest_run["exit_code"], 0)
            self.assertEqual(latest_run["run_log_path"], str(run_logs[0]))

    def test_run_with_log_capture_writes_error_summary_when_main_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            stdout_buffer = io.StringIO()

            def main_fn():
                print("before boom")
                raise RuntimeError("boom")

            original_stdout = sys.stdout
            original_stderr = sys.stderr
            sys.stdout = stdout_buffer
            sys.stderr = io.StringIO()
            try:
                with self.assertRaises(RuntimeError):
                    run_with_log_capture(
                        main_fn,
                        argv=["daily_report_entry_demo.py", "2026-04-22"],
                        logs_root=tmpdir,
                        now=datetime(2026, 4, 23, 15, 31, 0),
                    )
            finally:
                sys.stdout = original_stdout
                sys.stderr = original_stderr

            run_logs = sorted((Path(tmpdir) / "runs").glob("*.log"))
            self.assertEqual(len(run_logs), 1)
            log_text = run_logs[0].read_text(encoding="utf-8")
            self.assertIn("before boom", log_text)
            self.assertIn("RuntimeError: boom", log_text)

            error_logs = sorted((Path(tmpdir) / "errors").glob("*.json"))
            self.assertEqual(len(error_logs), 1)
            payload = json.loads(error_logs[0].read_text(encoding="utf-8"))
            self.assertEqual(payload["error_type"], "RuntimeError")
            self.assertEqual(payload["error_message"], "boom")
            self.assertEqual(payload["run_log_path"], str(run_logs[0]))
            latest_run = json.loads((Path(tmpdir) / "latest_run.json").read_text(encoding="utf-8"))
            latest_failure = json.loads((Path(tmpdir) / "latest_failure.json").read_text(encoding="utf-8"))
            self.assertEqual(latest_run["status"], "error")
            self.assertEqual(latest_run["error_type"], "RuntimeError")
            self.assertEqual(latest_failure["run_log_path"], str(run_logs[0]))
            self.assertTrue(any("RuntimeError: boom" in line for line in latest_failure["recent_important_lines"]))

    def test_success_clears_current_failure_summary_and_preserves_error_history(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_stdout = sys.stdout
            original_stderr = sys.stderr
            sys.stdout = io.StringIO()
            sys.stderr = io.StringIO()
            try:
                with self.assertRaises(RuntimeError):
                    run_with_log_capture(
                        lambda: (_ for _ in ()).throw(RuntimeError("first run failed")),
                        argv=["daily_report_entry_demo.py", "2026-07-27"],
                        logs_root=tmpdir,
                        now=datetime(2026, 7, 28, 1, 0, 0),
                    )
                error_paths = sorted((Path(tmpdir) / "errors").glob("*.json"))
                self.assertEqual(len(error_paths), 1)
                self.assertTrue((Path(tmpdir) / "latest_failure.json").exists())

                exit_code = run_with_log_capture(
                    lambda: 0,
                    argv=["daily_report_entry_demo.py", "2026-07-27", "--postgres-only"],
                    logs_root=tmpdir,
                    now=datetime(2026, 7, 28, 1, 5, 0),
                )
            finally:
                sys.stdout = original_stdout
                sys.stderr = original_stderr

            latest_run = json.loads((Path(tmpdir) / "latest_run.json").read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 0)
            self.assertEqual(latest_run["status"], "success")
            self.assertFalse((Path(tmpdir) / "latest_failure.json").exists())
            self.assertTrue(error_paths[0].exists())
            error_payload = json.loads(error_paths[0].read_text(encoding="utf-8"))
            self.assertEqual(error_payload["error_message"], "first run failed")

    def test_run_with_log_capture_keeps_account_day_order_finding_in_error_summary(self):
        from daily_report_render import ReportCriticalDataMissingError

        message = (
            "日报一致性检查未通过：position_day_order_inferred_target_conflict: "
            "Te执行目标沿用了待成交确认对象"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            original_stdout = sys.stdout
            original_stderr = sys.stderr
            sys.stdout = io.StringIO()
            sys.stderr = io.StringIO()
            try:
                with self.assertRaises(ReportCriticalDataMissingError):
                    run_with_log_capture(
                        lambda: (_ for _ in ()).throw(ReportCriticalDataMissingError(message)),
                        argv=["daily_report_entry_demo.py", "2026-07-10", "--replay"],
                        logs_root=tmpdir,
                        now=datetime(2026, 7, 11, 1, 10, 0),
                    )
            finally:
                sys.stdout = original_stdout
                sys.stderr = original_stderr

            error_logs = sorted((Path(tmpdir) / "errors").glob("*.json"))
            self.assertEqual(len(error_logs), 1)
            payload = json.loads(error_logs[0].read_text(encoding="utf-8"))
            self.assertEqual(payload["error_type"], "ReportCriticalDataMissingError")
            self.assertIn("position_day_order_inferred_target_conflict", payload["error_message"])
            self.assertIn("待成交确认", payload["error_message"])

    def test_run_with_log_capture_redacts_tokens_in_latest_failure_lines(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            stdout_buffer = io.StringIO()
            stderr_buffer = io.StringIO()

            def main_fn():
                print("Tushare B 通道: 可生成")
                print(
                    "Tushare失败 Bearer secret-token token=quicktiny-token "
                    "cookie: xq_a_token=cookie-secret"
                )
                print("小写凭证 api_key=lower-secret xueqiu_cookie=lower-cookie-secret")
                print("Tushare失败 postgresql://user:pass@localhost/report")
                raise RuntimeError("QUICKTINY_TOKEN=secret-token XUEQIU_COOKIE=cookie-secret IWENCAI_API_KEY=api-secret")

            original_stdout = sys.stdout
            original_stderr = sys.stderr
            sys.stdout = stdout_buffer
            sys.stderr = stderr_buffer
            try:
                with self.assertRaises(RuntimeError):
                    run_with_log_capture(
                        main_fn,
                        argv=[
                            "daily_report_entry_demo.py",
                            "postgresql://user:pass@localhost/report",
                            "--token=quicktiny-token",
                        ],
                        logs_root=tmpdir,
                        now=datetime(2026, 4, 23, 15, 32, 0),
                    )
            finally:
                sys.stdout = original_stdout
                sys.stderr = original_stderr

            latest_failure = json.loads((Path(tmpdir) / "latest_failure.json").read_text(encoding="utf-8"))
            latest_run = json.loads((Path(tmpdir) / "latest_run.json").read_text(encoding="utf-8"))
            run_logs = sorted((Path(tmpdir) / "runs").glob("*.log"))
            error_logs = sorted((Path(tmpdir) / "errors").glob("*.json"))
            self.assertEqual(len(run_logs), 1)
            self.assertEqual(len(error_logs), 1)
            joined = "\n".join(
                [
                    json.dumps(latest_failure, ensure_ascii=False),
                    json.dumps(latest_run, ensure_ascii=False),
                    run_logs[0].read_text(encoding="utf-8"),
                    error_logs[0].read_text(encoding="utf-8"),
                    str(run_logs[0]),
                    stdout_buffer.getvalue(),
                    stderr_buffer.getvalue(),
                ]
            )
            self.assertIn("Bearer ***", joined)
            self.assertIn("token=***", joined)
            self.assertIn("cookie: ***", joined)
            self.assertIn("api_key=***", joined)
            self.assertIn("xueqiu_cookie=***", joined)
            self.assertIn("postgresql://***", joined)
            self.assertIn("Tushare B 通道: 可生成", joined)
            self.assertNotIn("secret-token", joined)
            self.assertNotIn("quicktiny-token", joined)
            self.assertNotIn("cookie-secret", joined)
            self.assertNotIn("lower-secret", joined)
            self.assertNotIn("lower-cookie-secret", joined)
            self.assertNotIn("user:pass", joined)
            self.assertNotIn("api-secret", joined)

    def test_entry_help_command_stays_usable_with_log_capture(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "daily_report_entry_demo.py"), "--help"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("A股日报数据获取入口", result.stdout)
        self.assertIn("--replay", result.stdout)


if __name__ == "__main__":
    unittest.main()
