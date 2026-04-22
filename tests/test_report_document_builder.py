import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.report_document_builder import (
    build_prohibition_section_contract,
    build_report_shell_contract,
)


class ReportDocumentBuilderTest(unittest.TestCase):
    def test_build_report_shell_contract_keeps_discipline_placeholder(self):
        result = build_report_shell_contract(
            target_date="2026-04-22",
            run_mode="frozen",
            has_personal_positions=False,
            compact=True,
            use_report_preamble=lambda target_date, run_mode="frozen", has_personal_positions=False, compact=False: [
                f"# {target_date} A股日报",
                "## 🧭 交易理念底线",
            ],
        )

        self.assertIn("## 🚫 次日操作纪律（第一眼看这里）", result["report"])
        self.assertIn("<!-- PROHIBITION_PLACEHOLDER -->", result["report"])
        self.assertTrue(any(log["step"] == "build.report_shell" for log in result["module_logs"]))

    def test_build_prohibition_section_contract_outputs_defensive_mode(self):
        result = build_prohibition_section_contract(
            display_position_level="二档（防守档）",
            display_operation_state="观察态",
            environment_headline="先看特殊标的是否继续抗跌",
            has_personal_positions=True,
            final_gate={"should_reduce": True},
            main_sectors=["军工", "机器人"],
            exit_analysis={"risk_sectors": ["地产", "消费"]},
        )

        lines = result["lines"]
        rendered = "\n".join(lines)

        self.assertIn("二档（防守档） / 观察态", rendered)
        self.assertIn("禁止新开仓", rendered)
        self.assertIn("主攻线只盯军工", rendered)
        self.assertIn("风险板块（禁止碰）", rendered)
        self.assertTrue(any(log["step"] == "build.prohibition_section" for log in result["module_logs"]))


if __name__ == "__main__":
    unittest.main()
