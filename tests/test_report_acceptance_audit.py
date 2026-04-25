import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.report_acceptance_audit import audit_report_markdown


GOOD_MARKDOWN = """# 2026-04-24 a股市场分析

## 一、交易纪律
| 明日结论 | 默认节奏 | 尾盘例外 | 最大风险 | 核心纪律 |
|----------|----------|----------|----------|----------|
| 轻仓观察 | 09:50-10:10确认 | 仅例外 | 单笔最晚-5% | 只做主线 |

## 二、市场基底
| 项目 | 结论 |
|------|------|
| 市场状态 | 收缩防守 |

## 三、周期与主线
### 5. 主线成交额占比趋势
| 日期 | 周期主线 | 当天主攻线 | 主线成交额 | 两市成交额 | 占比 | 占比变化 | 解读 |
|------|----------|------------|------------|------------|------|----------|------|
| 2026-04-24 | 半导体 | 半导体 | 待累计 | 26414.92亿 | 待累计 | 待累计 | 数据不足 |

## 四、资金意图
| 当前资金状态 | 对主线的态度 | 对明日动作的含义 |
|--------------|--------------|------------------|
| 观察 | 观察 | 观察 |

## 五、个股解读
| 主线内唯一重点 | 跨线对象定位 | 动作原则 |
|----------------|--------------|----------|
| 富瀚微(300613) | 只看外溢 | 10点确认 |

## 六、明日执行计划
| 明日唯一动作 | 标的 | 条件 | 不满足怎么办 |
|--------------|------|------|--------------|
| 只看唯一对象 | 富瀚微(300613) | 主线确认 + 承接 + 60分钟确认 | 不做 |
| 时间窗口 | 要看什么 | 买入权限 | 卖出/风控 | 结论 |
|----------|----------|----------|-----------|------|
| 09:25-09:40 | 竞价强弱 | 默认无 | 处理风险 | 不抢 |
| 09:50-10:10 | 市场底色、主线承接、唯一对象强弱 | 仅主线核心可进入观察买点 | 10:00左右处理弱仓/错仓 | 核心确认窗口 |
| 10:00左右卖 | 弱仓、错仓、破结构仓位 | 无 | 该卖就卖 | 防大亏 |
| 10:00左右买 | 只看周期主线核心，且必须有承接 | 满足60分钟确认才允许 | 买后用30分钟结构止损 | 小仓或不开 |
| 午后 | 看主线是否延续 | 默认谨慎 | 若走弱继续降风险 | 不扩大试错 |
| 尾盘 | 只判断是否量化电风扇行情 | 仅例外 | 非电风扇不尾盘开新仓 | 例外 |

## 七、最终结论
| 明日结论 | 当前盈亏比 | 周期主线 | 当天主攻线 | 当前市场底色 | 唯一重点对象 | 明日执行风格 | 一句话动作 |
|----------|------------|----------|------------|--------------|--------------|--------------|------------|
| 防守观察 | 不主动 | 半导体 | 半导体 | 防守 | 富瀚微(300613) | 空仓 / 短线确认 | 条件不满足就不做 |

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
            "| 防守观察 | 不主动 | 半导体 | 半导体 | 防守 | 富瀚微(300613) | 空仓 / 短线确认 | 条件不满足就不做 |",
            "| 防守观察 | 不主动 | 半导体 | 半导体 | 防守 | 中嘉博创(000889) | 空仓 / 短线确认 | 条件不满足就不做 |",
        )

        result = audit_report_markdown(bad)

        self.assertIn("unique_focus_mismatch", {finding["code"] for finding in result["findings"]})

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

    def test_audit_flags_missing_60_minute_confirmation(self):
        bad = GOOD_MARKDOWN.replace("60分钟确认", "结构确认")

        self.assertExecutionConditionMissing(bad, "60分钟确认")

    def test_audit_flags_missing_30_minute_structural_stop(self):
        bad = GOOD_MARKDOWN.replace("30分钟结构止损", "结构止损")

        self.assertExecutionConditionMissing(bad, "30分钟结构止损")

    def test_audit_flags_missing_no_action_fallback(self):
        bad = GOOD_MARKDOWN.replace("不做", "继续观察").replace("空仓", "等待")

        self.assertExecutionConditionMissing(bad, "不做 / 不开新仓 / 空仓")

    def test_audit_flags_appendix_duplicate_front_page_sections(self):
        bad = GOOD_MARKDOWN.replace(
            "### 附录B：历史主线池",
            "### 附录：一、交易纪律\n\n### 附录B：历史主线池",
        )

        result = audit_report_markdown(bad)

        self.assertIn("appendix_duplicate_front_page_section", {finding["code"] for finding in result["findings"]})


if __name__ == "__main__":
    unittest.main()
