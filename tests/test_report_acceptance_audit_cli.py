import os
import subprocess
import unittest
from pathlib import Path

from tests.test_report_acceptance_audit import GOOD_MARKDOWN

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / ".generated" / "venv-py314" / "bin" / "python3.14"


def run_audit_cli(*args):
    env = os.environ.copy()
    scripts_path = str(ROOT / "scripts")
    env["PYTHONPATH"] = scripts_path + os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else scripts_path
    return subprocess.run(
        [
            str(PYTHON),
            "-m",
            "report.report_acceptance_audit",
            *(str(arg) for arg in args),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        env=env,
    )


def run_audit_script_direct(*args):
    return subprocess.run(
        [
            str(PYTHON),
            str(ROOT / "scripts" / "report" / "report_acceptance_audit.py"),
            *(str(arg) for arg in args),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )


def zero_position_report():
    return (
        GOOD_MARKDOWN.replace(
            "| 只看唯一对象 | 富瀚微(300613) | 主线确认 + 承接 + 09:50-10:10窗口 | 不做 |",
            "| 只看唯一对象 | 暂无 | 09:50-10:10窗口 | 主线确认 + 承接 + 09:50-10:10窗口未同时满足 | 不做 |",
        )
        .replace(
            "| 进攻仓位三态 | 50% |",
            "| 进攻仓位三态 | 0% |",
        )
        .replace(
            "| 明日最大仓位 | 50% |",
            "| 明日最大仓位 | 0% |",
        )
        .replace(
            "| 50%条件执行 | 固定交易窗口条件 | 仅14:30-14:55例外 | 单笔最晚-5% | 只做主线 |",
            "| 0%不参与 | 固定交易窗口条件 | 仅14:30-14:55例外 | 单笔最晚-5% | 不新增参与 |",
        )
        .replace(
            "| 50%条件执行 | 正盈亏比 | 半导体 | 半导体 | 修复 | 富瀚微(300613) | 50%条件执行 | 50%：只做合格对象，按昨晚预案检查执行资格，B1未变强不补B2，不满足回到0% |",
            "| 0%不参与 | 负盈亏比 | 半导体 | 半导体 | 修复 | 暂无 | 0%不参与 | 0%：不新增参与，等待下一次预演条件重新成立 |",
        )
    )


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
            completed = run_audit_cli(report_path)

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("front_page_heading_order", completed.stdout)
            self.assertIn("duplicate_front_page_heading", completed.stdout)
        finally:
            for path in tmp_dir.glob("*"):
                path.unlink()
            tmp_dir.rmdir()

    def test_cli_flags_chanlun_html_mismatch_when_companion_html_is_given(self):
        tmp_dir = ROOT / "reports" / "_audit_cli_test"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        report_path = tmp_dir / "zero_report.md"
        html_path = tmp_dir / "sh_index_chanlun.html"
        report_path.write_text(zero_position_report(), encoding="utf-8")
        html_path.write_text(
            """
            <h2>明日抉择</h2>
            <table>
              <tr><td>最终执行条件</td><td>可以参与</td></tr>
              <tr><td>明日最大仓位</td><td>50%</td></tr>
              <tr><td>新增参与</td><td>参与</td></tr>
            </table>
            """,
            encoding="utf-8",
        )
        try:
            completed = run_audit_cli(report_path, "--companion-html", html_path)

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("chanlun_tomorrow_decision_conflict", completed.stdout)
        finally:
            for path in tmp_dir.glob("*"):
                path.unlink()
            tmp_dir.rmdir()

    def test_cli_flags_pending_plan_used_as_te_target_without_database_summary(self):
        tmp_dir = ROOT / "reports" / "_audit_cli_test"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        report_path = tmp_dir / "pending_target_conflict.md"
        report_path.write_text(
            (
                "## 账户日序表\n"
                "| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |\n"
                "|------|------|----------|----------|-------------|------|\n"
                "| Td | 2026-07-10（周五） | 报告日：前日报计划推定，待成交确认：长电科技(600584) | 长电科技(600584) | Te不新增参与，B2取消 | 只观察，不新增参与 |\n"
                "| Te | 2026-07-13（周一） | 前日报计划对象待成交确认：长电科技(600584) | 长电科技(600584) | 确认已成交才视为B1；未确认不新增B2 | 先确认成交事实；未成交不补B2 |\n\n"
                "| 成交确认 | 前日报计划推定，待成交确认：长电科技(600584)；未确认成交前不视为B1，不新增B2 |\n"
                + zero_position_report()
            ),
            encoding="utf-8",
        )
        try:
            completed = run_audit_cli(report_path)

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("position_day_order_inferred_target_conflict", completed.stdout)
        finally:
            for path in tmp_dir.glob("*"):
                path.unlink()
            tmp_dir.rmdir()

    def test_cli_flags_elimination_html_mismatch_when_companion_html_is_given(self):
        tmp_dir = ROOT / "reports" / "_audit_cli_test"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        report_path = tmp_dir / "zero_report.md"
        html_path = tmp_dir / "elimination.html"
        report_path.write_text(zero_position_report(), encoding="utf-8")
        html_path.write_text(
            """
            <!doctype html>
            <meta name="artifact" content="elimination-tournament">
            <h1>2026-06-12 明日标的选股淘汰赛</h1>
            <script type="application/json" id="elimination-payload">
            {"final_action": {"label": "50%条件执行", "position_pct": 50, "target": {"name": "和远气体", "code": "002971"}}}
            </script>
            """,
            encoding="utf-8",
        )
        try:
            completed = run_audit_cli(report_path, "--companion-html", html_path)

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("elimination_tournament_final_conflict", completed.stdout)
        finally:
            for path in tmp_dir.glob("*"):
                path.unlink()
            tmp_dir.rmdir()

    def test_direct_script_cli_works_without_manual_pythonpath(self):
        tmp_dir = ROOT / "reports" / "_audit_cli_test"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        report_path = tmp_dir / "bad_report.md"
        report_path.write_text("| 涨跌比 | 0 / 0 | - | 多头仍占优 |\n", encoding="utf-8")
        try:
            completed = run_audit_script_direct(report_path)

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("market_breadth_incomplete", completed.stdout)
            self.assertNotIn("ModuleNotFoundError", completed.stderr)
        finally:
            for path in tmp_dir.glob("*"):
                path.unlink()
            tmp_dir.rmdir()


if __name__ == "__main__":
    unittest.main()
