import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ReportAcceptanceAuditCliTest(unittest.TestCase):
    def test_cli_returns_nonzero_for_bad_report_and_prints_finding_code(self):
        tmp_dir = ROOT / "reports" / "_audit_cli_test"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        report_path = tmp_dir / "bad_report.md"
        report_path.write_text(
            """# bad

## 一、交易纪律
## 三、周期与主线
## 三、周期与主线
## 四、资金意图
## 五、个股解读
## 六、明日执行计划
## 七、最终结论
""",
            encoding="utf-8",
        )
        try:
            completed = subprocess.run(
                [
                    str(ROOT / "venv" / "bin" / "python"),
                    str(ROOT / "scripts" / "report" / "report_acceptance_audit.py"),
                    str(report_path),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("front_page_heading_order", completed.stdout)
            self.assertIn("duplicate_front_page_heading", completed.stdout)
        finally:
            for path in tmp_dir.glob("*"):
                path.unlink()
            tmp_dir.rmdir()


if __name__ == "__main__":
    unittest.main()
