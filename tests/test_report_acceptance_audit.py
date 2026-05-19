import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.report_acceptance_audit import audit_report_markdown


GOOD_MARKDOWN = """# 2026-04-24 a股市场分析

## 一、交易纪律
| 明日结论 | 默认节奏 | 尾盘例外 | 最大风险 | 核心纪律 |
|----------|----------|----------|----------|----------|
| 50%标准进攻 | 09:50-10:10确认 | 仅例外 | 单笔最晚-5% | 只做主线 |

### 月度攻防与进攻仓位
| 项目 | 结论 |
|------|------|
| 本月模式 | 财报/季报高筛选月 |
| 当月收益 | +0.00% |
| 盈利垫 | 未触发（阈值+10.00%） |
| 进攻仓位三态 | 50% |
| 明日最大仓位 | 50% |

## 二、市场基底
| 项目 | 结论 |
|------|------|
| 市场状态 | 收缩防守 |

## 三、周期与主线
### 4. 主线容量与格局判断
| 主线容量 | 主线格局 | 主攻线 | 竞争线/背景线 | 主线确认依据 | 板块关系状态 | 主线进程 | 明日动作 |
|----------|----------|--------|----------------|--------------|--------------|----------|----------|
| 单线容量 | 单主线聚焦 | 半导体 | - | 半导体资金净流入靠前，高标和涨停更集中，成交占比扩张 | 单主线聚焦 | 启动 | 只围绕半导体做减法 |

#### 主线攻击证据
| 板块 | 攻击状态 | 净流入排名 | 净流入 | 涨停数 | 高标高度 | 成交占比变化 | 结论 |
|------|----------|------------|--------|--------|----------|--------------|------|
| 半导体 | 确认主攻线 | 第1 | +45.00亿 | 5 | 4 | +1.6pct | 半导体资金净流入靠前，涨停和高标更集中，成交占比扩张 |

### 5. 主线成交额占比趋势
| 日期 | 周期主线 | 当天主攻线 | 主线成交额 | 两市成交额 | 占比 | 占比变化 | 解读 |
|------|----------|------------|------------|------------|------|----------|------|
| 2026-04-24 | 半导体 | 半导体 | 待累计 | 26414.92亿 | 待累计 | 待累计 | 数据不足 |

## 四、资金意图
| 当前资金状态 | 对主线的态度 | 对明日动作的含义 |
|--------------|--------------|------------------|
| 观察 | 观察 | 观察 |

## 五、个股解读
### 1. 个股裁决
| 项目 | 结论 |
|------|------|
| 唯一对象 | 富瀚微(300613) |
| 当前状态 | 50%标准进攻对象 |
| 备用观察 | 暂无 |
| 今日不买原因 | 等10点确认 |
| 明日触发 | 主线确认 + 承接 + 60分钟确认 |
| 明日失效 | 主线回落 |

## 六、明日执行计划
| 明日唯一动作 | 标的 | 条件 | 不满足怎么办 |
|--------------|------|------|--------------|
| 只看唯一对象 | 富瀚微(300613) | 主线确认 + 承接 + 60分钟确认 | 不做 |
| 时间窗口 | 要看什么 | 买入资格 | 卖出/风控 | 结论 |
|----------|----------|----------|-----------|------|
| 09:25-09:40 | 竞价强弱 | 默认无 | 处理风险 | 不抢 |
| 09:50-10:10 | 市场底色、主线承接、唯一对象强弱 | 仅主线核心可进入观察买点 | 10:00左右处理弱仓/错仓 | 核心确认窗口 |
| 10:00左右卖 | 弱仓、错仓、破结构仓位 | 无 | 该卖就卖 | 防大亏 |
| 10:00左右买 | 只看周期主线核心，且必须有承接 | 竞价表态、参与窗口与结构确认共同成立 | 买后用30分钟结构止损 | 50%/100%或0% |
| 午后 | 看主线是否延续 | 默认谨慎 | 若走弱继续降风险 | 不扩大试错 |
| 尾盘 | 只判断是否量化电风扇行情 | 仅例外 | 非电风扇不尾盘开新仓 | 例外 |

## 七、最终结论
| 明日结论 | 当前盈亏比 | 周期主线 | 当天主攻线 | 当前市场底色 | 唯一重点对象 | 明日执行风格 | 一句话动作 |
|----------|------------|----------|------------|--------------|--------------|--------------|------------|
| 50%标准进攻 | 正盈亏比 | 半导体 | 半导体 | 修复 | 富瀚微(300613) | 50% / 标准进攻 | 50%：只做合格对象，满足预演情境后执行，不满足回到0% |

## 八、详细附录
### 附录B：历史主线池
"""


class ReportAcceptanceAuditTest(unittest.TestCase):
    def assertExecutionConditionMissing(self, markdown, expected_text):
        result = audit_report_markdown(markdown)

        matching_findings = [
            finding
            for finding in result["findings"]
            if finding["code"] == "execution_condition_missing" and expected_text in finding["message"]
        ]
        self.assertTrue(matching_findings, result["findings"])
        self.assertFalse(result["passed"])

    def test_audit_accepts_valid_front_page_contract(self):
        result = audit_report_markdown(GOOD_MARKDOWN)

        self.assertEqual(result["findings"], [])
        self.assertTrue(result["passed"])

    def test_audit_flags_missing_mainline_capacity_regime_table(self):
        bad = GOOD_MARKDOWN.replace(
            "### 4. 主线容量与格局判断\n"
            "| 主线容量 | 主线格局 | 主攻线 | 竞争线/背景线 | 主线确认依据 | 板块关系状态 | 主线进程 | 明日动作 |\n"
            "|----------|----------|--------|----------------|--------------|--------------|----------|----------|\n"
            "| 单线容量 | 单主线聚焦 | 半导体 | - | 半导体资金净流入靠前，高标和涨停更集中，成交占比扩张 | 单主线聚焦 | 启动 | 只围绕半导体做减法 |\n\n",
            "",
        )

        result = audit_report_markdown(bad)

        self.assertIn("mainline_capacity_regime_missing", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_flags_missing_mainline_attack_evidence_table(self):
        bad = GOOD_MARKDOWN.replace(
            "#### 主线攻击证据\n"
            "| 板块 | 攻击状态 | 净流入排名 | 净流入 | 涨停数 | 高标高度 | 成交占比变化 | 结论 |\n"
            "|------|----------|------------|--------|--------|----------|--------------|------|\n"
            "| 半导体 | 确认主攻线 | 第1 | +45.00亿 | 5 | 4 | +1.6pct | 半导体资金净流入靠前，涨停和高标更集中，成交占比扩张 |\n\n",
            "",
        )

        result = audit_report_markdown(bad)

        self.assertIn("mainline_attack_evidence_missing", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_flags_legacy_double_mainline_table_on_front_page(self):
        bad = GOOD_MARKDOWN.replace(
            "| 主线容量 | 主线格局 | 主攻线 | 竞争线/背景线 | 主线确认依据 | 板块关系状态 | 主线进程 | 明日动作 |",
            "| 周期主线 | 当天主攻线 | 两者关系 | 明日动作 |",
        )

        result = audit_report_markdown(bad)

        self.assertIn("legacy_double_mainline_table", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_flags_legacy_empty_short_style_in_final_summary(self):
        bad = GOOD_MARKDOWN.replace(
            "| 50%标准进攻 | 正盈亏比 | 半导体 | 半导体 | 修复 | 富瀚微(300613) | 50% / 标准进攻 | 50%：只做合格对象，满足预演情境后执行，不满足回到0% |",
            "| 50%标准进攻 | 正盈亏比 | 半导体 | 半导体 | 修复 | 富瀚微(300613) | 空仓 / 短线确认 | 条件不满足就不做 |",
        )

        result = audit_report_markdown(bad)

        self.assertIn("legacy_position_style", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_flags_missing_monthly_rhythm_section(self):
        bad = GOOD_MARKDOWN.replace(
            "\n### 月度攻防与进攻仓位\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 本月模式 | 财报/季报高筛选月 |\n"
            "| 当月收益 | +0.00% |\n"
            "| 盈利垫 | 未触发（阈值+10.00%） |\n"
            "| 进攻仓位三态 | 50% |\n"
            "| 明日最大仓位 | 50% |\n",
            "\n",
        )

        result = audit_report_markdown(bad)

        self.assertIn("monthly_rhythm_missing", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_flags_missing_position_attack_grade(self):
        bad = GOOD_MARKDOWN.replace("| 进攻仓位三态 | 50% |\n", "")

        result = audit_report_markdown(bad)

        self.assertIn("monthly_rhythm_field_missing", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_accepts_all_fixed_position_attack_grades(self):
        cases = (
            ("0%", "0%"),
            ("50%", "50%"),
            ("100%", "100%"),
        )
        for label, max_position in cases:
            with self.subTest(label=label):
                report = (
                    GOOD_MARKDOWN.replace("| 进攻仓位三态 | 50% |", f"| 进攻仓位三态 | {label} |")
                    .replace("| 明日最大仓位 | 50% |", f"| 明日最大仓位 | {max_position} |")
                )

                result = audit_report_markdown(report)

                self.assertNotIn("position_attack_grade_invalid", {finding["code"] for finding in result["findings"]})
                self.assertTrue(result["passed"], result["findings"])

    def test_audit_flags_invalid_position_attack_grade_value(self):
        bad = GOOD_MARKDOWN.replace("| 进攻仓位三态 | 50% |", "| 进攻仓位三态 | A" + "档90% |")

        result = audit_report_markdown(bad)

        self.assertIn("position_attack_grade_invalid", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_flags_position_attack_grade_above_max_position(self):
        bad = GOOD_MARKDOWN.replace("| 进攻仓位三态 | 50% |", "| 进攻仓位三态 | 100% |")

        result = audit_report_markdown(bad)

        self.assertIn("position_attack_grade_exceeds_max_position", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_flags_legacy_signal_grade_label_on_front_page(self):
        bad = GOOD_MARKDOWN.replace("| 进攻仓位三态 | 50% |", "| 今日信号等级 | B |")

        result = audit_report_markdown(bad)

        self.assertIn("monthly_rhythm_field_missing", {finding["code"] for finding in result["findings"]})
        self.assertIn("legacy_signal_grade_label", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_flags_legacy_position_grade_label_on_front_page(self):
        bad = GOOD_MARKDOWN.replace("| 进攻仓位三态 | 50% |", "| 仓位攻击等级 | B" + "档30% |")

        result = audit_report_markdown(bad)

        self.assertIn("monthly_rhythm_field_missing", {finding["code"] for finding in result["findings"]})
        self.assertIn("legacy_position_grade_label", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_flags_old_candidate_titles_on_front_page(self):
        bad = GOOD_MARKDOWN.replace("### 1. 个股裁决", "### 1. 主线内观察候选")

        result = audit_report_markdown(bad)

        self.assertIn("legacy_candidate_section_title", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_flags_buy_permission_wording_on_front_page(self):
        bad = GOOD_MARKDOWN.replace("买入资格", "买入" + "权限")

        result = audit_report_markdown(bad)

        self.assertIn("legacy_surface_wording", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_flags_all_legacy_surface_wording_markers_on_front_page(self):
        for marker in (
            "买入" + "权限",
            "执行" + "权",
            "执行" + "权限",
            "门" + "控",
            "闸" + "门",
            "开" + "闸",
            "放" + "行",
        ):
            with self.subTest(marker=marker):
                bad = GOOD_MARKDOWN.replace("50%标准进攻", marker, 1)

                result = audit_report_markdown(bad)

                self.assertIn("legacy_surface_wording", {finding["code"] for finding in result["findings"]})
                self.assertFalse(result["passed"])

    def test_audit_flags_front_page_heading_order_and_duplicates(self):
        bad = GOOD_MARKDOWN.replace("## 二、市场基底", "## 三、周期与主线", 1)

        result = audit_report_markdown(bad)

        codes = {finding["code"] for finding in result["findings"]}
        self.assertIn("front_page_heading_order", codes)
        self.assertIn("duplicate_front_page_heading", codes)

    def test_audit_flags_repeated_no_trade_sentence(self):
        bad = GOOD_MARKDOWN.replace(
            "## 八、详细附录",
            "没有唯一对象就不做；绝不为了不确定性承担大亏\n"
            "没有唯一对象就不做；绝不为了不确定性承担大亏\n\n"
            "## 八、详细附录",
        )

        result = audit_report_markdown(bad)

        self.assertIn("duplicate_no_trade_conclusion", {finding["code"] for finding in result["findings"]})

    def test_audit_flags_degraded_fake_zero_percent(self):
        bad = GOOD_MARKDOWN.replace(
            "| 2026-04-24 | 半导体 | 半导体 | 待累计 | 26414.92亿 | 待累计 | 待累计 | 数据不足 |",
            "| 2026-04-24 | 半导体 | 半导体 | missing_dependency | 26414.92亿 | 0.00% | 待累计 | 数据缺失 |",
        )

        result = audit_report_markdown(bad)

        self.assertIn("degraded_fake_zero_percent", {finding["code"] for finding in result["findings"]})

    def test_audit_flags_unique_focus_mismatch_between_plan_and_final_summary(self):
        bad = GOOD_MARKDOWN.replace(
            "| 50%标准进攻 | 正盈亏比 | 半导体 | 半导体 | 修复 | 富瀚微(300613) | 50% / 标准进攻 | 50%：只做合格对象，满足预演情境后执行，不满足回到0% |",
            "| 50%标准进攻 | 正盈亏比 | 半导体 | 半导体 | 修复 | 中嘉博创(000889) | 50% / 标准进攻 | 50%：只做合格对象，满足预演情境后执行，不满足回到0% |",
        )

        result = audit_report_markdown(bad)

        self.assertIn("unique_focus_mismatch", {finding["code"] for finding in result["findings"]})

    def test_audit_allows_same_unique_focus_with_different_label_format(self):
        report = GOOD_MARKDOWN.replace(
            "| 只看唯一对象 | 富瀚微(300613) | 主线确认 + 承接 + 60分钟确认 | 不做 |",
            "| 只看唯一对象 | 300613 富瀚微（半导体） | 主线确认 + 承接 + 60分钟确认 | 不做 |",
        )

        result = audit_report_markdown(report)

        self.assertNotIn("unique_focus_mismatch", {finding["code"] for finding in result["findings"]})
        self.assertTrue(result["passed"], result["findings"])

    def test_audit_flags_concrete_unique_focus_without_required_decision_evidence(self):
        bad = GOOD_MARKDOWN.replace("承接", "强弱")

        result = audit_report_markdown(bad)

        matching_findings = [
            finding for finding in result["findings"] if finding["code"] == "unique_focus_evidence_missing"
        ]
        self.assertTrue(matching_findings, result["findings"])
        self.assertIn("承接", matching_findings[0]["message"])
        self.assertFalse(result["passed"])

    def test_audit_allows_empty_unique_focus_with_observation_only_rows(self):
        report = GOOD_MARKDOWN.replace(
            "| 只看唯一对象 | 富瀚微(300613) | 主线确认 + 承接 + 60分钟确认 | 不做 |",
            "| 只看唯一对象 | 暂无 | 主线确认 + 承接 + 60分钟确认未同时满足 | 不做 |",
        ).replace(
            "| 50%标准进攻 | 正盈亏比 | 半导体 | 半导体 | 修复 | 富瀚微(300613) | 50% / 标准进攻 | 50%：只做合格对象，满足预演情境后执行，不满足回到0% |",
            "| 50%标准进攻 | 正盈亏比 | 半导体 | 半导体 | 修复 | 暂无 | 50% / 标准进攻 | 50%：只做合格对象，满足预演情境后执行，不满足回到0% |",
        )

        result = audit_report_markdown(report)

        self.assertNotIn("unique_focus_contradiction", {finding["code"] for finding in result["findings"]})
        self.assertTrue(result["passed"], result["findings"])

    def test_audit_flags_empty_unique_focus_with_concrete_buy_candidate(self):
        bad = GOOD_MARKDOWN.replace(
            "| 只看唯一对象 | 富瀚微(300613) | 主线确认 + 承接 + 60分钟确认 | 不做 |",
            "| 只看唯一对象 | 暂无 | 主线确认 + 承接 + 60分钟确认未同时满足 | 不做 |",
        ).replace(
            "| 当前状态 | 50%标准进攻对象 |",
            "| 当前状态 | 富瀚微(300613) 唯一买入，10点确认 |",
        ).replace(
            "| 50%标准进攻 | 正盈亏比 | 半导体 | 半导体 | 修复 | 富瀚微(300613) | 50% / 标准进攻 | 50%：只做合格对象，满足预演情境后执行，不满足回到0% |",
            "| 50%标准进攻 | 正盈亏比 | 半导体 | 半导体 | 修复 | 暂无 | 50% / 标准进攻 | 50%：只做合格对象，满足预演情境后执行，不满足回到0% |",
        )

        result = audit_report_markdown(bad)

        self.assertIn("unique_focus_contradiction", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_flags_missing_execution_windows(self):
        bad = GOOD_MARKDOWN.replace(
            "| 09:25-09:40 | 竞价强弱 | 默认无 | 处理风险 | 不抢 |\n",
            "",
        )

        result = audit_report_markdown(bad)

        self.assertIn("execution_window_missing", {finding["code"] for finding in result["findings"]})

    def test_audit_flags_missing_10_point_confirmation(self):
        bad = GOOD_MARKDOWN.replace("10点确认", "开盘确认")

        self.assertExecutionConditionMissing(bad, "10点确认")

    def test_audit_flags_missing_participation_window(self):
        bad = (
            GOOD_MARKDOWN
            .replace("60分钟确认", "结构确认")
            .replace("竞价表态、参与窗口与结构确认共同成立", "结构确认共同成立")
        )

        self.assertExecutionConditionMissing(bad, "参与窗口")

    def test_audit_flags_fast_window_polluted_by_structure_condition(self):
        bad = GOOD_MARKDOWN.replace(
            "| 只看唯一对象 | 富瀚微(300613) | 主线确认 + 承接 + 60分钟确认 | 不做 |",
            "| 只看唯一对象 | 富瀚微(300613) | 竞价表态 + 回封参与 | 主线确认 + 承接 + 60分钟确认 | 不做 |",
        )

        result = audit_report_markdown(bad)

        self.assertIn("fast_window_polluted_by_structure_condition", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_flags_missing_30_minute_structural_stop(self):
        bad = GOOD_MARKDOWN.replace("30分钟结构止损", "结构止损")

        self.assertExecutionConditionMissing(bad, "30分钟结构止损")

    def test_audit_flags_missing_no_action_fallback(self):
        bad = GOOD_MARKDOWN.replace("不做", "继续观察").replace("空仓", "等待")

        self.assertExecutionConditionMissing(bad, "不做 / 不开新仓 / 空仓")

    def test_audit_flags_reasoning_surface_missing_required_rows(self):
        bad = GOOD_MARKDOWN.replace(
            "| 明日唯一动作 | 标的 | 条件 | 不满足怎么办 |",
            "### 0. 推理裁决\n"
            "| 项目 | 内容 |\n"
            "|------|------|\n"
            "| 裁决 | observe |\n"
            "| 结论 | 主线仍需确认。 |\n\n"
            "| 明日唯一动作 | 标的 | 条件 | 不满足怎么办 |",
        )

        result = audit_report_markdown(bad)

        self.assertIn("reasoning_surface_incomplete", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_accepts_reasoning_surface_without_action_or_mainline_state_rows(self):
        report = GOOD_MARKDOWN.replace(
            "| 明日唯一动作 | 标的 | 条件 | 不满足怎么办 |",
            "### 0. 推理裁决\n"
            "| 项目 | 内容 |\n"
            "|------|------|\n"
            "| 结论 | 主线仍需确认。 |\n"
            "| 关键证据 | 主线为半导体 |\n"
            "| 触发条件 | 10点确认 |\n"
            "| 失败条件 | 主线回落 |\n"
            "| 排除对象 | 富瀚微(300613)：60分钟确认未完成 |\n"
            "| 推理深度 | xhigh |\n\n"
            "| 明日唯一动作 | 标的 | 条件 | 不满足怎么办 |",
        )

        result = audit_report_markdown(report)

        self.assertNotIn("reasoning_surface_incomplete", {finding["code"] for finding in result["findings"]})
        self.assertTrue(result["passed"], result["findings"])

    def test_audit_flags_reasoning_chain_leakage(self):
        for marker in ("思维链", "Chain-of-Thought", "CHAIN-OF-THOUGHT"):
            with self.subTest(marker=marker):
                bad = GOOD_MARKDOWN.replace(
                    "## 七、最终结论",
                    "### 0. 推理裁决\n"
                    f"{marker}：先这样想，再那样想。\n\n"
                    "## 七、最终结论",
                )

                result = audit_report_markdown(bad)

                self.assertIn("reasoning_chain_leakage", {finding["code"] for finding in result["findings"]})
                self.assertFalse(result["passed"])

    def test_audit_flags_front_page_simulation_noise_language(self):
        noisy_phrases = [
            "多智能体一致认为主线明天会修复。",
            "沙盘推演显示半导体可能爆发。",
            "模型认为胜率提高，所以明天提高仓位。",
            "虽然规则未满足，但推演偏乐观，可以先买。",
        ]

        for phrase in noisy_phrases:
            with self.subTest(phrase=phrase):
                bad = GOOD_MARKDOWN.replace(
                    "## 七、最终结论",
                    f"{phrase}\n\n## 七、最终结论",
                )

                result = audit_report_markdown(bad)

                self.assertIn("simulation_noise_language", {finding["code"] for finding in result["findings"]})
                self.assertFalse(result["passed"])

    def test_audit_flags_front_page_simulation_tool_names_and_consensus_terms(self):
        noisy_phrases = [
            "MiroFish提示半导体明天可能加强。",
            "多智能体共识认为可以放宽观察条件。",
            "沙盘推演偏乐观，先看是否试错。",
        ]

        for phrase in noisy_phrases:
            with self.subTest(phrase=phrase):
                bad = GOOD_MARKDOWN.replace(
                    "## 七、最终结论",
                    f"{phrase}\n\n## 七、最终结论",
                )

                result = audit_report_markdown(bad)

                self.assertIn("simulation_noise_language", {finding["code"] for finding in result["findings"]})
                self.assertFalse(result["passed"])

    def test_audit_deduplicates_simulation_findings_per_line(self):
        noisy_line = "多智能体一致认为主线明天会修复。"
        bad = GOOD_MARKDOWN.replace(
            "## 七、最终结论",
            f"{noisy_line}\n\n## 七、最终结论",
        )
        inserted_line = bad.splitlines().index(noisy_line) + 1

        result = audit_report_markdown(bad)

        simulation_counts = Counter(
            (finding.get("line"), finding["code"])
            for finding in result["findings"]
            if finding["code"] == "simulation_noise_language"
        )
        self.assertEqual(
            simulation_counts,
            {
                (inserted_line, "simulation_noise_language"): 1,
            },
        )
        self.assertFalse(result["passed"])

    def test_audit_flags_front_page_theory_concept_noise_language(self):
        noisy_phrases = [
            "能量学判断显示承接转强。",
            "能量释放完成，明天提高仓位。",
            "群体行为共振，候选资格上调。",
        ]

        for phrase in noisy_phrases:
            with self.subTest(phrase=phrase):
                bad = GOOD_MARKDOWN.replace(
                    "## 七、最终结论",
                    f"{phrase}\n\n## 七、最终结论",
                )

                result = audit_report_markdown(bad)

                self.assertIn("theory_noise_language", {finding["code"] for finding in result["findings"]})
                self.assertFalse(result["passed"])

    def test_audit_flags_unfieldized_theory_terms_without_action_context(self):
        noisy_phrases = [
            "群体行为正在扩散，主线承接改善",
            "能量释放对应为放量突破",
            "能量学解释为趋势启动",
        ]

        for phrase in noisy_phrases:
            with self.subTest(phrase=phrase):
                bad = GOOD_MARKDOWN.replace(
                    "## 七、最终结论",
                    f"{phrase}\n\n## 七、最终结论",
                )

                result = audit_report_markdown(bad)

                self.assertIn("theory_noise_language", {finding["code"] for finding in result["findings"]})
                self.assertFalse(result["passed"])

    def test_audit_flags_theory_driven_buy_language(self):
        bad = GOOD_MARKDOWN.replace(
            "## 七、最终结论",
            "能量释放，所以可以买；群体行为共振，所以提高仓位。\n\n## 七、最终结论",
        )

        result = audit_report_markdown(bad)

        self.assertIn("theory_driven_action_language", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_deduplicates_theory_findings_per_line(self):
        noisy_line = "能量释放，所以可以买；群体行为共振，所以提高仓位。"
        bad = GOOD_MARKDOWN.replace(
            "## 七、最终结论",
            f"{noisy_line}\n\n## 七、最终结论",
        )
        inserted_line = bad.splitlines().index(noisy_line) + 1

        result = audit_report_markdown(bad)

        theory_counts = Counter(
            (finding.get("line"), finding["code"])
            for finding in result["findings"]
            if finding["code"] in ("theory_driven_action_language", "theory_noise_language")
        )
        self.assertEqual(
            theory_counts,
            {
                (inserted_line, "theory_driven_action_language"): 1,
                (inserted_line, "theory_noise_language"): 1,
            },
        )
        self.assertFalse(result["passed"])

    def test_audit_flags_theory_concepts_in_action_context(self):
        noisy_phrases = [
            "能量学，所以可以买。",
            "能量释放推动候选资格上调。",
            "群体行为显示主线可以提高仓位。",
        ]

        for phrase in noisy_phrases:
            with self.subTest(phrase=phrase):
                bad = GOOD_MARKDOWN.replace(
                    "## 七、最终结论",
                    f"{phrase}\n\n## 七、最终结论",
                )

                result = audit_report_markdown(bad)

                self.assertIn("theory_driven_action_language", {finding["code"] for finding in result["findings"]})
                self.assertFalse(result["passed"])

    def test_audit_allows_fieldized_price_action_language(self):
        report = GOOD_MARKDOWN.replace(
            "## 七、最终结论",
            "上涨斜率强，但回撤比例仍需验证；突破后承接改善，不追高；加速后衰竭风险仍在，板块内扩散不足。\n\n## 七、最终结论",
        )

        result = audit_report_markdown(report)

        self.assertTrue(result["passed"], result["findings"])

    def test_audit_flags_appendix_duplicate_front_page_sections(self):
        bad = GOOD_MARKDOWN.replace(
            "### 附录B：历史主线池",
            "### 附录：一、交易纪律\n\n### 附录B：历史主线池",
        )

        result = audit_report_markdown(bad)

        self.assertIn("appendix_duplicate_front_page_section", {finding["code"] for finding in result["findings"]})


if __name__ == "__main__":
    unittest.main()
