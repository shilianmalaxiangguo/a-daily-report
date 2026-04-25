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
    def test_build_report_shell_contract_renders_v2_front_page_placeholders_in_order(self):
        result = build_report_shell_contract(
            target_date="2026-04-22",
            run_mode="frozen",
            has_personal_positions=False,
            compact=True,
            use_report_preamble=lambda target_date, run_mode="frozen", has_personal_positions=False, compact=False: [
                f"# {target_date} A股作战简报",
            ],
        )

        rendered = "\n".join(result["report"])
        expected_sections = [
            "## 一、交易纪律",
            "<!-- FRONT_PAGE_MARKET_BASE_PLACEHOLDER -->",
            "## 三、周期与主线",
            "<!-- FRONT_PAGE_CAPITAL_INTENT_PLACEHOLDER -->",
            "<!-- FRONT_PAGE_STOCK_INTERPRETATION_PLACEHOLDER -->",
            "## 六、明日执行计划",
            "<!-- FRONT_PAGE_FINAL_SUMMARY_PLACEHOLDER -->",
        ]

        positions = []
        for section in expected_sections:
            self.assertIn(section, rendered)
            positions.append(rendered.index(section))

        self.assertEqual(positions, sorted(positions))

    def test_build_report_shell_contract_reserves_cycle_calendar_and_interpretation_slots_when_enabled(self):
        result = build_report_shell_contract(
            target_date="2026-04-22",
            run_mode="frozen",
            has_personal_positions=False,
            compact=True,
            enabled_node_keys=[
                "cycle_calendar_placeholder",
                "cycle_interpretation_placeholder",
                "pivot_mainline_placeholder",
            ],
            use_report_preamble=lambda target_date, run_mode="frozen", has_personal_positions=False, compact=False: [
                f"# {target_date} A股作战简报",
            ],
        )

        rendered = "\n".join(result["report"])
        expected_blocks = [
            "### 1. 周期日历主视图",
            "<!-- FRONT_PAGE_CYCLE_CALENDAR_PLACEHOLDER -->",
            "### 2. 周期解读",
            "<!-- FRONT_PAGE_CYCLE_INTERPRETATION_PLACEHOLDER -->",
            "### 3. 中枢与主线解读",
            "<!-- FRONT_PAGE_PIVOT_MAINLINE_PLACEHOLDER -->",
        ]

        positions = []
        for block in expected_blocks:
            self.assertIn(block, rendered)
            positions.append(rendered.index(block))

        self.assertEqual(positions, sorted(positions))

    def test_build_report_shell_contract_default_uses_single_cycle_mainline_slot(self):
        result = build_report_shell_contract(
            target_date="2026-04-22",
            run_mode="frozen",
            has_personal_positions=False,
            compact=True,
            use_report_preamble=lambda target_date, run_mode="frozen", has_personal_positions=False, compact=False: [
                f"# {target_date} A股作战简报",
            ],
        )

        rendered = "\n".join(result["report"])
        self.assertIn("<!-- MARKET_RESEARCH_SNAPSHOT_PLACEHOLDER -->", rendered)
        self.assertNotIn("<!-- FRONT_PAGE_CYCLE_CALENDAR_PLACEHOLDER -->", rendered)
        self.assertNotIn("<!-- FRONT_PAGE_CYCLE_INTERPRETATION_PLACEHOLDER -->", rendered)
        self.assertNotIn("<!-- FRONT_PAGE_PIVOT_MAINLINE_PLACEHOLDER -->", rendered)

    def test_build_report_shell_contract_can_render_only_enabled_nodes(self):
        result = build_report_shell_contract(
            target_date="2026-04-22",
            run_mode="frozen",
            has_personal_positions=False,
            compact=True,
            enabled_node_keys=["preamble", "discipline_header", "discipline_placeholder"],
            use_report_preamble=lambda target_date, run_mode="frozen", has_personal_positions=False, compact=False: [
                f"# {target_date} A股日报",
            ],
        )

        rendered = "\n".join(result["report"])
        self.assertIn("# 2026-04-22 A股日报", rendered)
        self.assertIn("## 一、交易纪律", rendered)
        self.assertIn("<!-- PROHIBITION_PLACEHOLDER -->", rendered)
        self.assertNotIn("次日早盘打开日报，第一眼看这里。", rendered)

    def test_build_report_shell_contract_keeps_discipline_placeholder(self):
        result = build_report_shell_contract(
            target_date="2026-04-22",
            run_mode="frozen",
            has_personal_positions=False,
            compact=True,
            use_report_preamble=lambda target_date, run_mode="frozen", has_personal_positions=False, compact=False: [
                f"# {target_date} A股日报",
            ],
        )

        self.assertIn("## 一、交易纪律", result["report"])
        self.assertIn("<!-- PROHIBITION_PLACEHOLDER -->", result["report"])
        self.assertTrue(any(log["step"] == "build.report_shell" for log in result["module_logs"]))

    def test_build_prohibition_section_contract_can_render_only_enabled_nodes(self):
        result = build_prohibition_section_contract(
            display_position_level="二档（防守档）",
            display_operation_state="观察态",
            environment_headline="先看特殊标的是否继续抗跌",
            has_personal_positions=True,
            final_gate={"should_reduce": True},
            main_sectors=["军工", "机器人"],
            exit_analysis={"risk_sectors": ["地产", "消费"]},
            enabled_node_keys=["environment", "prohibition_header", "prohibition_items"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("**次日市场环境**: 二档（防守档） / 观察态 - 先看特殊标的是否继续抗跌", rendered)
        self.assertIn("**禁止事项**:", rendered)
        self.assertIn("禁止新开仓", rendered)
        self.assertNotIn("**允许事项**:", rendered)
        self.assertNotIn("风险板块（禁止碰）", rendered)

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

    def test_build_prohibition_section_contract_outputs_conditional_defense_mode(self):
        result = build_prohibition_section_contract(
            display_position_level="二档（防守档）",
            display_operation_state="防守态",
            environment_headline="指数上行中枢内，防守观察",
            has_personal_positions=False,
            final_gate={"should_reduce": False, "allow_conditional_30": True},
            main_sectors=["半导体", "电池"],
            exit_analysis={"risk_sectors": []},
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("10点确认后的30%条件试错", rendered)
        self.assertNotIn("二档不允许任何新增买入", rendered)


if __name__ == "__main__":
    unittest.main()
