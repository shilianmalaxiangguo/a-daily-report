import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def _m(*parts):
    return "".join(parts)

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
            display_position_level="0%不参与",
            display_operation_state="观察态",
            environment_headline="先看特殊标的是否继续抗跌",
            has_personal_positions=True,
            final_gate={"should_reduce": True},
            main_sectors=["军工", "机器人"],
            exit_analysis={"risk_sectors": ["地产", "消费"]},
            enabled_node_keys=["environment", "prohibition_header", "prohibition_items"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("**次日市场环境**: 0%不参与 / 观察态 - 先看特殊标的是否继续抗跌", rendered)
        self.assertIn("**禁止事项**:", rendered)
        self.assertIn("不新增参与", rendered)
        self.assertNotIn("禁止新开仓", rendered)
        self.assertNotIn("**允许事项**:", rendered)
        self.assertNotIn("风险板块（禁止碰）", rendered)

    def test_build_prohibition_section_contract_outputs_defensive_mode(self):
        result = build_prohibition_section_contract(
            display_position_level="0%不参与",
            display_operation_state="观察态",
            environment_headline="先看特殊标的是否继续抗跌",
            has_personal_positions=True,
            final_gate={"should_reduce": True},
            main_sectors=["军工", "机器人"],
            exit_analysis={"risk_sectors": ["地产", "消费"]},
        )

        lines = result["lines"]
        rendered = "\n".join(lines)

        self.assertIn("0%不参与 / 观察态", rendered)
        self.assertIn("不新增参与", rendered)
        self.assertNotIn("禁止新开仓", rendered)
        self.assertIn("禁止买入任何方向", rendered)
        self.assertIn("风险板块（禁止碰）", rendered)
        self.assertTrue(any(log["step"] == "build.prohibition_section" for log in result["module_logs"]))

    def test_build_prohibition_section_distinguishes_new_entry_from_existing_position_t0(self):
        result = build_prohibition_section_contract(
            display_position_level="0%不参与",
            display_operation_state="观察态",
            environment_headline="环境关闭，只做等待",
            has_personal_positions=True,
        )

        rendered = "\n".join(result["lines"])

        self.assertIn("新开仓不做日内回转；旧仓只按持仓策略处理", rendered)
        self.assertNotIn("禁止做T：次日不做日内回转", rendered)

    def test_build_prohibition_section_does_not_call_confirmed_old_position_empty(self):
        result = build_prohibition_section_contract(
            display_position_level="0%不参与",
            display_operation_state="观察态",
            environment_headline="环境关闭，只做等待",
            has_personal_positions=True,
        )

        rendered = "\n".join(result["lines"])

        self.assertIn("不新增参与：先处理旧仓，不新增仓位", rendered)
        self.assertNotIn("保持空仓：当前不新增参与", rendered)

    def test_build_prohibition_section_keeps_empty_account_wording_without_old_position(self):
        result = build_prohibition_section_contract(
            display_position_level="0%不参与",
            display_operation_state="观察态",
            environment_headline="环境关闭，只做等待",
            has_personal_positions=False,
        )

        rendered = "\n".join(result["lines"])

        self.assertIn("保持空仓：当前不新增参与", rendered)

    def test_build_prohibition_section_keeps_old_position_action_unknown_without_position_input(self):
        result = build_prohibition_section_contract(
            display_position_level="0%不参与",
            display_operation_state="观察态",
            environment_headline="环境关闭，只做等待",
            has_personal_positions=False,
            position_context_provided=False,
        )

        rendered = "\n".join(result["lines"])

        self.assertIn("持仓未输入，先核对实际旧仓", rendered)
        self.assertIn("未确认前不生成卖出、持有或日内回转动作", rendered)
        self.assertNotIn("若你有旧仓，只做退出", rendered)
        self.assertNotIn("保持空仓：当前不新增参与", rendered)

    def test_build_prohibition_section_contract_maps_conditional_defense_to_zero_or_50_model(self):
        result = build_prohibition_section_contract(
            display_position_level="0%不参与",
            display_operation_state="防守态",
            environment_headline="指数上行中枢内，防守观察",
            has_personal_positions=False,
            final_gate={"should_reduce": False, "allow_attack_50_ready": True},
            main_sectors=["半导体", "电池"],
            exit_analysis={"risk_sectors": []},
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("0%不参与", rendered)
        self.assertNotIn("50%条件执行", rendered)
        self.assertIn("禁止买入任何方向", rendered)
        self.assertNotIn("参与窗口和60分钟确认", rendered)
        self.assertNotIn("同时成立", rendered)
        self.assertNotIn(_m("10点确认后的", "3", "0%", "条件", "试错"), rendered)
        self.assertNotIn(_m("3", "0%", "小仓", "试错"), rendered)
        self.assertNotIn("0%不参与不允许任何新增买入", rendered)


if __name__ == "__main__":
    unittest.main()
