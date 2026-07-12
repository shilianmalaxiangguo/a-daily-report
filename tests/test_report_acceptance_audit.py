import sys
import unittest
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.execution_wording import PREMARKET_50_TRIGGER_TEXT
import report.report_acceptance_audit as report_acceptance_audit
from report.report_acceptance_audit import audit_new_stock_visibility, audit_report_markdown
from report.markdown_report_html import render_markdown_report_html


GOOD_MARKDOWN = """# 2026-04-24 a股市场分析

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
| 日期 | 小周期方向 | 主线成交额 | 两市成交额 | 占比 | 占比变化 | 切换判断 | 解读 |
|------|------------|------------|------------|------|----------|----------|------|
| 2026-04-24 | 半导体 | 待累计 | 26414.92亿 | 待累计 | 待累计 | 大周期延续 | 数据不足 |

## 明日账户建议
| 项目 | 结论 |
|------|------|
| 明日仓位 | 50%条件执行；最大上限50%；B1参与权，B2确认权 |
| 明日动作 | 只看唯一对象，按昨晚预案检查执行资格；B1先买参与权，B2只买确认权；B1未变强不补B2，走弱先取消B2并检查B1；不满足取消 |

## 一、交易纪律
| 明日结论 | 默认节奏 | 尾盘例外 | 最大风险 | 核心纪律 |
|----------|----------|----------|----------|----------|
| 50%条件执行 | 固定交易窗口条件 | 仅14:30-14:55例外 | 单笔最晚-5% | 只做主线 |

### 月度攻防与进攻仓位
| 项目 | 结论 |
|------|------|
| 本月模式 | 财报/季报高筛选月 |
| 当月收益 | +0.00% |
| 盈利垫 | 未触发（阈值+10.00%） |
| 进攻仓位三态 | 50% |
| 明日最大仓位 | 50% |

## 四、资金意图
| 当前资金状态 | 对主线的态度 | 对明日动作的含义 |
|--------------|--------------|------------------|
| 观察 | 观察 | 观察 |

## 五、个股解读
### 1. 个股裁决
| 项目 | 结论 |
|------|------|
| 唯一对象 | 富瀚微(300613) |
| 当前状态 | 50%条件执行对象 |
| 备用观察 | 暂无 |
| 今日不买原因 | 等09:50-10:10窗口 |
| 明日触发 | 主线确认 + 承接 + 09:50-10:10窗口 |
| 明日失效 | 主线回落 |

## 六、明日执行计划
| 明日唯一动作 | 标的 | 条件 | 不满足怎么办 |
|--------------|------|------|--------------|
| 只看唯一对象 | 富瀚微(300613) | 主线确认 + 承接 + 09:50-10:10窗口 | 不做 |
| 时间窗口 | 要看什么 | 买入资格 | 卖出/风控 | 结论 |
|----------|----------|----------|-----------|------|
| 09:30-09:35 | 竞价强弱、主攻线承接 | 默认无 | 处理风险 | 不抢开盘 |
| 09:50-10:10 | 市场底色、主线承接、唯一对象强弱 | 主线核心承接稳定且个股确认 | 买后用失效价和单笔-5%底线处理风险 | 核心执行窗口 |
| 14:30-14:55 | 只判断是否量化电风扇行情 | 仅例外 | 非电风扇不新增参与 | 例外 |

## 七、最终结论
| 明日结论 | 当前盈亏比 | 周期主线 | 当天主攻线 | 当前市场底色 | 唯一重点对象 | 明日执行风格 | 一句话动作 |
|----------|------------|----------|------------|--------------|--------------|--------------|------------|
| 50%条件执行 | 正盈亏比 | 半导体 | 半导体 | 修复 | 富瀚微(300613) | 50%条件执行 | 50%：只做合格对象，按昨晚预案检查执行资格，B1未变强不补B2，不满足回到0% |

## 八、详细附录
**明日极度看好近25日跟踪表**（按入选日展示，排除A杀样本）（过程证据）:
| 入选日 | 股票 | 代码 | 排名 | 所属方向 | 观察位窗口 | 复盘状态 | 历史复盘动作 | 作废线 | 记录ID |
|--------|------|------|------|----------|----------|----------|------------|--------|--------|
| 2026-04-24 | 富瀚微 | 300613 | 1 | 半导体 | 09:50-10:10 | 等待复盘 | 等待计划窗口事实回写 | 按原计划作废条件处理 | 2026-04-24:300613 |

### 附录B：历史主线池
"""


def _replace_account_advice(markdown, replacement):
    start = markdown.index("## 明日账户建议")
    end = markdown.index("## 一、交易纪律", start)
    replacement = replacement.strip("\n")
    return markdown[:start] + replacement + "\n\n" + markdown[end:]


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

    def zero_position_report(self):
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
                "| 当前状态 | 50%条件执行对象 |",
                "| 当前状态 | 0%不参与 |",
            )
            .replace(
                "| 09:50-10:10 | 市场底色、主线承接、唯一对象强弱 | 主线核心承接稳定且个股确认 | 买后用失效价和单笔-5%底线处理风险 | 核心执行窗口 |",
                "| 09:50-10:10 | 市场底色、主线承接、唯一对象强弱 | 无 | 无新增参与止损 | 继续0%不参与 |",
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

    def zero_position_report_with_decision_attribution(self):
        report = _replace_account_advice(
            self.zero_position_report(),
            "## 明日账户建议\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 明日仓位 | 0%不参与 |\n"
            "| 执行目标 | 无 |\n"
            "| 观察对象 | 暂无 |\n"
            "| 不参与依据 | 候选全部未达参与资格，需要复盘候选筛选。 |\n"
            "| 无执行目标原因 | 候选池没有选出足够强的核心 |\n"
            "| 责任归因 | 决策问题 |\n"
            "| 明日动作 | 0%不参与；不新增参与 |",
        )
        return report.replace(
            "## 五、个股解读\n"
            "### 1. 个股裁决\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 唯一对象 | 富瀚微(300613) |\n"
            "| 当前状态 | 0%不参与 |\n"
            "| 备用观察 | 暂无 |\n"
            "| 今日不买原因 | 等09:50-10:10窗口 |\n",
            "## 五、个股解读\n"
            "### 1. 个股裁决\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 明日仓位 | 0%不参与 |\n"
            "| 执行目标 | 无 |\n"
            "| 观察对象 | 暂无 |\n"
            "| 不参与依据 | 候选全部未达参与资格，需要复盘候选筛选。 |\n"
            "| 无执行目标原因 | 候选池没有选出足够强的核心 |\n"
            "| 责任归因 | 决策问题 |\n"
            "| 当前状态 | 0%无合格标的 |\n"
            "| 备用观察 | 暂无 |\n"
            "| 今日不买原因 | 没有观察对象，完整候选仅保留在附录和快照 |\n",
        )

    def test_audit_accepts_valid_front_page_contract(self):
        result = audit_report_markdown(GOOD_MARKDOWN)

        self.assertEqual(result["findings"], [])
        self.assertTrue(result["passed"])

    def test_audit_flags_limit_down_execution_object_without_reversal_plan(self):
        markdown = (
            GOOD_MARKDOWN.replace(
                "| 明日动作 | 只看唯一对象，按昨晚预案检查执行资格；B1先买参与权，B2只买确认权；B1未变强不补B2，走弱先取消B2并检查B1；不满足取消 |",
                "| 明日动作 | 只看唯一对象，按昨晚预案检查执行资格；B1先买参与权，B2只买确认权；B1未变强不补B2，走弱先取消B2并检查B1；不满足取消 |\n"
                "| 明日执行对象 | 富瀚微(300613) |",
            )
            + "\n### 附录：热度核心结果\n"
            + "| 排名 | 股票 | 代码 | 涨跌幅 | 连板标签 |\n"
            + "|------|------|------|--------|----------|\n"
            + "| 1 | 富瀚微 | 300613 | -10.00% | 跌停 |\n"
        )

        result = audit_report_markdown(markdown)
        codes = {finding["code"] for finding in result["findings"]}

        self.assertIn("front_execution_object_limit_down_without_reversal_plan", codes)

    def test_audit_ignores_limit_down_process_candidate_tail_reference_to_execution_object(self):
        markdown = (
            GOOD_MARKDOWN.replace(
                "| 明日动作 | 只看唯一对象，按昨晚预案检查执行资格；B1先买参与权，B2只买确认权；B1未变强不补B2，走弱先取消B2并检查B1；不满足取消 |",
                "| 明日动作 | 只看唯一对象，按昨晚预案检查执行资格；B1先买参与权，B2只买确认权；B1未变强不补B2，走弱先取消B2并检查B1；不满足取消 |\n"
                "| 明日执行对象 | 富瀚微(300613) |",
            )
            + "\n### 附录：狙击手最终标的完整路径图（过程证据）\n"
            + "|-- 来源序号=34 来源=selection_workflow.candidate_pool 候选=多氟多(002407) 身份=过程候选 去向=被淘汰 "
            + "原因=热榜第4+涨幅-10.0%，仅作热度观察；同日跌幅-10.00%，按跌停/接近跌停处理；"
            + "如要参与必须写成跌停反包专项，并给出执行窗口、作废线和回到0%的条件"
            + "（过程证据，不覆盖唯一明日动作：富瀚微(300613)）\n"
        )

        result = audit_report_markdown(markdown)
        codes = {finding["code"] for finding in result["findings"]}

        self.assertNotIn("front_execution_object_limit_down_without_reversal_plan", codes)

    def test_audit_ignores_market_limit_down_clause_after_execution_object_clause(self):
        markdown = (
            GOOD_MARKDOWN.replace(
                "| 明日动作 | 只看唯一对象，按昨晚预案检查执行资格；B1先买参与权，B2只买确认权；B1未变强不补B2，走弱先取消B2并检查B1；不满足取消 |",
                "| 明日动作 | 只看唯一对象，按昨晚预案检查执行资格；B1先买参与权，B2只买确认权；B1未变强不补B2，走弱先取消B2并检查B1；不满足取消 |\n"
                "| 明日执行对象 | 富瀚微(300613) |",
            )
            + "\n**状态依据**：最终只看明日执行对象富瀚微(300613)的执行资格；"
            + "收缩防守；跌停、涨跌比或仓位限制已经进入收缩区，市场先谈防守。\n"
        )

        result = audit_report_markdown(markdown)
        codes = {finding["code"] for finding in result["findings"]}

        self.assertNotIn("front_execution_object_limit_down_without_reversal_plan", codes)

    def test_audit_allows_limit_down_execution_object_with_explicit_reversal_plan(self):
        markdown = (
            GOOD_MARKDOWN.replace(
                "| 明日动作 | 只看唯一对象，按昨晚预案检查执行资格；B1先买参与权，B2只买确认权；B1未变强不补B2，走弱先取消B2并检查B1；不满足取消 |",
                "| 明日动作 | 跌停反包专项：只看09:50-10:10窗口，站不回VWAP或跌破认错线就回到0%不参与 |\n"
                "| 明日执行对象 | 富瀚微(300613) |",
            )
            + "\n### 附录：热度核心结果\n"
            + "| 排名 | 股票 | 代码 | 涨跌幅 | 连板标签 |\n"
            + "|------|------|------|--------|----------|\n"
            + "| 1 | 富瀚微 | 300613 | -10.00% | 跌停 |\n"
        )

        result = audit_report_markdown(markdown)
        codes = {finding["code"] for finding in result["findings"]}

        self.assertNotIn("front_execution_object_limit_down_without_reversal_plan", codes)

    def test_audit_allows_explicit_limit_down_reversal_plan_with_tail_window(self):
        markdown = (
            GOOD_MARKDOWN.replace(
                "| 明日动作 | 只看唯一对象，按昨晚预案检查执行资格；B1先买参与权，B2只买确认权；B1未变强不补B2，走弱先取消B2并检查B1；不满足取消 |",
                "| 明日动作 | 跌停反包专项：只看14:30-14:55窗口，站不回VWAP或跌破认错线就回到0%不参与 |\n"
                "| 明日执行对象 | 富瀚微(300613) |",
            )
            + "\n### 附录：热度核心结果\n"
            + "| 排名 | 股票 | 代码 | 涨跌幅 | 连板标签 |\n"
            + "|------|------|------|--------|----------|\n"
            + "| 1 | 富瀚微 | 300613 | -10.00% | 跌停 |\n"
        )

        result = audit_report_markdown(markdown)
        codes = {finding["code"] for finding in result["findings"]}

        self.assertNotIn("front_execution_object_limit_down_without_reversal_plan", codes)

    def test_audit_flags_bare_anti_nuclear_without_special_reversal_contract(self):
        markdown = (
            GOOD_MARKDOWN.replace(
                "| 明日动作 | 只看唯一对象，按昨晚预案检查执行资格；B1先买参与权，B2只买确认权；B1未变强不补B2，走弱先取消B2并检查B1；不满足取消 |",
                "| 明日动作 | 反核：只看09:50-10:10窗口，失败就不参与 |\n"
                "| 明日执行对象 | 富瀚微(300613) |",
            )
            + "\n### 附录：热度核心结果\n"
            + "| 排名 | 股票 | 代码 | 涨跌幅 | 连板标签 |\n"
            + "|------|------|------|--------|----------|\n"
            + "| 1 | 富瀚微 | 300613 | -10.00% | 跌停 |\n"
        )

        result = audit_report_markdown(markdown)
        codes = {finding["code"] for finding in result["findings"]}

        self.assertIn("front_execution_object_limit_down_without_reversal_plan", codes)

    def test_audit_flags_bare_reversal_special_without_limit_down_contract(self):
        markdown = (
            GOOD_MARKDOWN.replace(
                "| 明日动作 | 只看唯一对象，按昨晚预案检查执行资格；B1先买参与权，B2只买确认权；B1未变强不补B2，走弱先取消B2并检查B1；不满足取消 |",
                "| 明日动作 | 反包专项：只看09:50-10:10窗口，跌破认错线回到0%不参与 |\n"
                "| 明日执行对象 | 富瀚微(300613) |",
            )
            + "\n### 附录：热度核心结果\n"
            + "| 排名 | 股票 | 代码 | 涨跌幅 | 连板标签 |\n"
            + "|------|------|------|--------|----------|\n"
            + "| 1 | 富瀚微 | 300613 | -10.00% | 跌停 |\n"
        )

        result = audit_report_markdown(markdown)
        codes = {finding["code"] for finding in result["findings"]}

        self.assertIn("front_execution_object_limit_down_without_reversal_plan", codes)

    def test_audit_flags_plain_reversal_text_combined_with_limit_down_fact(self):
        markdown = (
            GOOD_MARKDOWN.replace(
                "| 明日动作 | 只看唯一对象，按昨晚预案检查执行资格；B1先买参与权，B2只买确认权；B1未变强不补B2，走弱先取消B2并检查B1；不满足取消 |",
                "| 明日动作 | 普通反包观察：只看09:50-10:10窗口，跌破认错线回到0%不参与 |\n"
                "| 明日执行对象 | 富瀚微(300613) |",
            )
            + "\n### 附录：热度核心结果\n"
            + "| 排名 | 股票 | 代码 | 涨跌幅 | 连板标签 |\n"
            + "|------|------|------|--------|----------|\n"
            + "| 1 | 富瀚微 | 300613 | -10.00% | 跌停 |\n"
        )

        result = audit_report_markdown(markdown)
        codes = {finding["code"] for finding in result["findings"]}

        self.assertIn("front_execution_object_limit_down_without_reversal_plan", codes)

    def test_audit_accepts_derivation_chain_process_candidate_when_final_anchor_matches(self):
        markdown = GOOD_MARKDOWN.replace(
            "| 唯一对象 | 富瀚微(300613) |",
            "| 观察对象 | 豫能控股(001896) |",
        ).replace(
            "| 当前状态 | 50%条件执行对象 |",
            "| 当前状态 | 0%条件观察 |",
        ).replace(
            "| 只看唯一对象 | 富瀚微(300613) | 主线确认 + 承接 + 09:50-10:10窗口 | 不做 |",
            "| 只看观察对象 | 豫能控股(001896) | 09:50-10:10窗口 | 不做 |",
        ).replace(
            "| 50%条件执行 | 正盈亏比 | 半导体 | 半导体 | 修复 | 富瀚微(300613) | 50%条件执行 | 50%：只做合格对象，按昨晚预案检查执行资格，B1未变强不补B2，不满足回到0% |",
            "| 0%不参与 | 负盈亏比 | 电力 | 电力 | 混沌 | 观察对象：豫能控股(001896) | 0%不参与 | 只观察，不新增参与 |",
        ).replace(
            "## 八、详细附录\n",
            "## 八、详细附录\n"
            "## 狙击手最终标的完整路径图（过程证据）\n"
            "```text\n"
            "阶段一：原始候选\n"
            "|-- 来源=执行链最佳候选 候选=上海石化(600688) 身份=过程候选 去向=被替换 原因=资金确认不足，账户匹配不适合\n"
            "|\n"
            "阶段四：最终对象解析\n"
            "`-- 最终对象=豫能控股(001896) 身份=观察对象\n"
            "```\n\n",
        )

        result = audit_report_markdown(markdown)

        codes = {finding["code"] for finding in result["findings"]}
        self.assertNotIn("sniper_target_derivation_mismatch", codes)

    def test_audit_accepts_front_page_compact_derivation_chain_without_process_marker(self):
        markdown = GOOD_MARKDOWN.replace(
            "| 唯一对象 | 富瀚微(300613) |",
            "| 观察对象 | 豫能控股(001896) |",
        ).replace(
            "| 当前状态 | 50%条件执行对象 |",
            "| 当前状态 | 0%条件观察 |",
        ).replace(
            "| 只看唯一对象 | 富瀚微(300613) | 主线确认 + 承接 + 09:50-10:10窗口 | 不做 |",
            "| 只看观察对象 | 豫能控股(001896) | 09:50-10:10窗口 | 不做 |",
        ).replace(
            "## 一、交易纪律\n",
            "### 最终标的传导链\n\n"
            "```text\n"
            "原始候选\n"
            "|\n"
            "+-- 上海石化(600688): 过程候选 / 被替换\n"
            "|\n"
            "+-- 过程候选A(000001): 过程候选 / 被替换\n"
            "|\n"
            "+-- 过程候选B(000002): 过程候选 / 被替换\n"
            "|\n"
            "+-- 过程候选C(000003): 过程候选 / 被替换\n"
            "|\n"
            "+-- 过程候选D(000004): 过程候选 / 被替换\n"
            "|\n"
            "`-- 最终观察对象: 豫能控股(001896), 0%只观察\n"
            "```\n\n"
            "## 一、交易纪律\n",
            1,
        ).replace(
            "| 50%条件执行 | 正盈亏比 | 半导体 | 半导体 | 修复 | 富瀚微(300613) | 50%条件执行 | 50%：只做合格对象，按昨晚预案检查执行资格，B1未变强不补B2，不满足回到0% |",
            "| 0%不参与 | 负盈亏比 | 电力 | 电力 | 混沌 | 观察对象：豫能控股(001896) | 0%不参与 | 只观察，不新增参与 |",
        )

        result = audit_report_markdown(markdown)

        codes = {finding["code"] for finding in result["findings"]}
        self.assertNotIn("process_evidence_heading_missing_marker", codes)
        self.assertNotIn("sniper_target_derivation_mismatch", codes)

    def test_audit_allows_zero_position_observation_target_with_empty_execution_target(self):
        markdown = (
            "# 2026-06-04 a股市场分析\n\n"
            "### 最终标的传导链\n\n"
            "```text\n"
            "原始候选\n"
            "|\n"
            "+-- 上海石化(600688): 过程候选 / 被替换\n"
            "|\n"
            "`-- 最终观察对象: 豫能控股(001896), 0%只观察\n"
            "```\n\n"
            "## 明日执行结论\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 明日仓位 | 0%不参与 |\n"
            "| 明日执行对象 | 无 |\n"
            "| 执行性质 | 无明日执行对象 |\n\n"
            "## 一、交易纪律\n"
            "| 明日结论 | 默认节奏 | 尾盘例外 | 最大风险 | 核心纪律 |\n"
            "|----------|----------|----------|----------|----------|\n"
            "| 0%不参与 | 观察 | 无 | 不新增参与 | 只观察 |\n\n"
            "## 三、周期与主线\n"
            "### 4. 主线容量与格局判断\n"
            "| 主线容量 | 主线格局 | 主攻线 | 竞争线/背景线 | 主线确认依据 | 板块关系状态 | 主线进程 | 明日动作 |\n"
            "|----------|----------|--------|----------------|--------------|--------------|----------|----------|\n"
            "| 容量待累计 | 单主线聚焦 | 电力 | - | 待验证 | 暂未分出 | 待观察 | 只观察 |\n\n"
            "## 五、个股解读\n"
            "### 1. 个股裁决\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 观察对象 | 豫能控股(001896) |\n"
            "| 当前状态 | 0%条件观察 |\n"
            "| 不参与依据 | 市场条件未到，只保留观察对象。 |\n"
            "| 无执行目标原因 | 市场条件未到，只保留观察对象 |\n"
            "| 责任归因 | 市场问题 |\n"
            "| 观察对象性质 | 强弱参照，不是执行目标 |\n"
            "| 今日不买原因 | 有观察对象，只等观察窗口确认；条件不满足继续0% |\n\n"
            "## 六、明日执行计划\n"
            "| 明日观察动作 | 标的 | 观察窗 | 条件 | 不满足怎么办 |\n"
            "|--------------|------|------|------|--------------|\n"
            "| 只看观察对象 | 豫能控股(001896) | 09:50-10:10 | 主线承接 + 个股强弱重新确认 | 不满足继续0% |\n\n"
            "## 七、最终结论\n"
            "| 明日结论 | 当前盈亏比 | 周期主线 | 当天主攻线 | 当前市场底色 | 重点对象 | 明日执行风格 | 一句话动作 |\n"
            "|----------|------------|----------|------------|--------------|--------------|--------------|------------|\n"
            "| 0%不参与 | 不确定时不值得主动参与 | 电力 | 电力 | 观察聚焦 | 观察对象：豫能控股(001896) | 0%不参与 | 盘前0%；只观察豫能控股(001896)，成立才保留观察；未出现执行资格前不新增参与；不满足继续0% |\n\n"
            "## 八、详细附录\n"
            "## 狙击手最终标的完整路径图（过程证据）\n"
            "```text\n"
            "`-- 最终对象=豫能控股(001896) 身份=观察对象\n"
            "```\n"
        )

        result = audit_report_markdown(markdown)

        codes = {finding["code"] for finding in result["findings"]}
        self.assertNotIn("unique_focus_mismatch", codes)
        self.assertNotIn("process_evidence_heading_missing_marker", codes)

    def test_audit_flags_conflicting_derivation_chain_final_observation_targets(self):
        markdown = (
            "# 2026-06-04 a股市场分析\n\n"
            "### 最终标的传导链\n\n"
            "```text\n"
            "`-- 最终观察对象: 豫能控股(001896), 0%只观察\n"
            "```\n\n"
            "## 明日执行结论\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 明日仓位 | 0%不参与 |\n"
            "| 明日执行对象 | 无 |\n\n"
            "## 七、最终结论\n"
            "| 明日结论 | 当前盈亏比 | 周期主线 | 当天主攻线 | 当前市场底色 | 重点对象 | 明日执行风格 | 一句话动作 |\n"
            "|----------|------------|----------|------------|--------------|--------------|--------------|------------|\n"
            "| 0%不参与 | 不确定时不值得主动参与 | 电力 | 电力 | 观察聚焦 | 观察对象：豫能控股(001896) | 0%不参与 | 盘前0%；只观察豫能控股(001896)，成立才保留观察；未出现执行资格前不新增参与；不满足继续0% |\n\n"
            "## 八、详细附录\n"
            "##### 附录：# 最终标的传导链（过程证据）\n\n"
            "```text\n"
            "`-- 最终观察对象: 暂无, 0%只观察\n"
            "```\n"
        )

        result = audit_report_markdown(markdown)

        self.assertIn("sniper_target_derivation_mismatch", {finding["code"] for finding in result["findings"]})

    def test_audit_flags_derivation_chain_final_anchor_mismatch(self):
        markdown = GOOD_MARKDOWN.replace(
            "| 50%条件执行 | 正盈亏比 | 半导体 | 半导体 | 修复 | 富瀚微(300613) | 50%条件执行 | 50%：只做合格对象，按昨晚预案检查执行资格，B1未变强不补B2，不满足回到0% |",
            "| 0%不参与 | 负盈亏比 | 电力 | 电力 | 混沌 | 观察对象：豫能控股(001896) | 0%不参与 | 只观察，不新增参与 |",
        ).replace(
            "## 八、详细附录\n",
            "## 八、详细附录\n"
            "## 狙击手最终标的完整路径图（过程证据）\n"
            "```text\n"
            "`-- 最终对象=上海石化(600688) 身份=观察对象\n"
            "```\n\n",
        )

        result = audit_report_markdown(markdown)

        self.assertIn("sniper_target_derivation_mismatch", {finding["code"] for finding in result["findings"]})

    def test_audit_flags_selection_workflow_mismatch(self):
        markdown = (
            "# 2026-06-04 a股市场分析\n\n"
            "## 明日执行结论\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 明日仓位 | 已决定50%条件执行；盘中不满足取消，回到0%不参与 |\n"
            "| 明日执行对象 | 豫能控股(001896) |\n\n"
            "## 推导审计层\n"
            "### 候选流水账\n"
            "| 上海石化(600688) | 涨停池 | 涨停样本 | 过程候选 | 降级观察 | 被淘汰 | 不参与 |\n"
            "```json\n"
            '{"selection_workflow":{"schema_version":"selection_workflow.v1","final":{"execution_object":{"name":"上海石化","code":"600688"},"position_pct":50}}}\n'
            "```\n"
        )

        result = audit_report_markdown(markdown)

        self.assertIn("selection_workflow_mismatch", {finding["code"] for finding in result["findings"]})

    def test_audit_flags_selection_workflow_object_when_front_execution_object_is_empty(self):
        markdown = (
            "# 2026-06-04 a股市场分析\n\n"
            "## 明日执行结论\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 明日仓位 | 0%不参与 |\n"
            "| 明日执行对象 | 无 |\n\n"
            "## 推导审计层\n"
            "```json\n"
            '{"selection_workflow":{"schema_version":"selection_workflow.v1","final":{"execution_object":{"name":"双星新材","code":"002585"},"position_pct":50}}}\n'
            "```\n"
        )

        result = audit_report_markdown(markdown)

        self.assertIn("selection_workflow_mismatch", {finding["code"] for finding in result["findings"]})

    def test_audit_flags_selection_workflow_text_mismatch(self):
        markdown = (
            "# 2026-06-04 a股市场分析\n\n"
            "## 明日执行结论\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 明日仓位 | 已决定50%条件执行；盘中不满足取消，回到0%不参与 |\n"
            "| 明日执行对象 | 豫能控股(001896) |\n\n"
            "## 推导审计层\n"
            "### 工作流链条\n"
            "#### N8 仓位与执行条件\n"
            "- 结论：50%条件执行\n"
            "- 传给下一步：{'execution_object': {'name': '上海石化', 'code': '600688'}, 'position_pct': 50}\n"
            "### 候选流水账\n"
            "| 股票 | 首次来源 | 进入理由 | 板块角色 | 反推结论 | 对照结果 | 最终动作 |\n"
            "|---|---|---|---|---|---|---|\n"
            "| 上海石化(600688) | 涨停池 | 涨停样本 | 过程候选 | 可作为主对象 | 最终执行对象 | 最终执行对象 |\n"
        )

        result = audit_report_markdown(markdown)

        self.assertIn("selection_workflow_mismatch", {finding["code"] for finding in result["findings"]})

    def test_audit_flags_current_selection_workflow_text_when_front_execution_object_is_empty(self):
        markdown = (
            "# 2026-06-04 a股市场分析\n\n"
            "## 明日执行结论\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 明日仓位 | 0%不参与 |\n"
            "| 明日执行对象 | 无 |\n\n"
            "## 推导审计层\n"
            "### 主线推导链\n"
            "#### N8 仓位与执行条件\n"
            "- 结论：50%条件执行\n"
            "- 传给下一步：{'execution_object': {'name': '双星新材', 'code': '002585'}, 'position_pct': 50}\n"
            "### 候选生命周期证据\n"
            "| 股票 | 首次来源 | 进入理由 | 板块角色 | 反推结论 | 对照结果 | 最终动作 |\n"
            "|---|---|---|---|---|---|---|\n"
            "| 双星新材(002585) | extreme_conviction_list | 2连板 | 过程候选 | 可作为主对象 | 最终执行对象 | 最终执行对象 |\n"
        )

        result = audit_report_markdown(markdown)

        self.assertIn("selection_workflow_mismatch", {finding["code"] for finding in result["findings"]})

    def test_audit_flags_final_object_identity_conflict_across_closing_action(self):
        markdown = (
            "# 2026-06-04 a股市场分析\n\n"
            "## 明日执行结论\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 明日仓位 | 已决定50%条件执行；盘中不满足取消，回到0%不参与 |\n"
            "| 明日执行对象 | 豫能控股(001896) |\n"
            "| 不满足条件 | 不参与 |\n\n"
            "## 50%条件执行条件\n"
            "| 触发类型 | 必须满足 | 窗口 | 动作 |\n"
            "|----------|----------|------|------|\n"
            "| 低开承接型 | 靠近MA5；收回VWAP/0轴 | 09:50-10:10 | 50%条件执行 |\n"
            "| 主动进攻型 | 大单净流入达标；VWAP上方保持 | 09:30-09:35 | 50%条件执行 |\n\n"
            "## 七、最终结论\n"
            "| 明日结论 | 当前盈亏比 | 周期主线 | 当天主攻线 | 当前市场底色 | 重点对象 | 明日执行风格 | 一句话动作 |\n"
            "|----------|------------|----------|------------|--------------|--------------|--------------|------------|\n"
            "| 已决定50%条件执行；盘中不满足取消，回到0%不参与 | 不确定时不值得主动参与 | 电力 | 电力 | 观察聚焦 | 豫能控股(001896) | 50%条件执行 | 条件满足才50%条件执行；不满足回到0% |\n\n"
            "### 明日行动清单\n"
            "| 项目 | 明日动作 |\n"
            "|------|----------|\n"
            "| 仓位 | 已决定50%条件执行；盘中不满足取消，回到0%不参与 |\n"
            "| 最终对象 | 上海石化(600688) |\n"
            "| 执行/观察条件 | 09:50-10:10；主线承接 |\n"
            "| 不参与条件 | 不满足回到0%不参与 |\n"
            "| 旧仓处理 | 持仓未输入，执行前先确认旧仓情况 |\n"
            "| 复盘点 | 记录三段窗口是否满足条件 |\n\n"
            "## 八、详细附录\n"
            "## 狙击手最终标的完整路径图（过程证据）\n"
            "```text\n"
            "`-- 最终对象=豫能控股(001896) 身份=观察对象\n"
            "```\n"
        )

        result = audit_report_markdown(markdown)

        self.assertIn("final_object_identity_conflict", {finding["code"] for finding in result["findings"]})

    def test_audit_flags_chain_final_execution_object_identity_conflict(self):
        markdown = (
            "# 2026-06-04 a股市场分析\n\n"
            "## 日报裁决总览\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 最终对象 | 观察对象：豫能控股(001896) |\n\n"
            "## 七、最终结论\n"
            "| 明日结论 | 当前盈亏比 | 周期主线 | 当天主攻线 | 当前市场底色 | 重点对象 | 明日执行风格 | 一句话动作 |\n"
            "|----------|------------|----------|------------|--------------|--------------|--------------|------------|\n"
            "| 0%不参与 | 不确定时不值得主动参与 | 电力 | 电力 | 观察聚焦 | 观察对象：豫能控股(001896) | 0%不参与 | 只观察，不新增参与 |\n\n"
            "## 八、详细附录\n"
            "## 狙击手最终标的完整路径图（过程证据）\n"
            "```text\n"
            "`-- 最终对象=上海石化(600688) 身份=执行对象\n"
            "```\n"
        )

        result = audit_report_markdown(markdown)

        self.assertIn("final_object_identity_conflict", {finding["code"] for finding in result["findings"]})

    def test_audit_flags_empty_opening_final_object_when_later_surface_names_observation_object(self):
        markdown = (
            "# 2026-06-04 a股市场分析\n\n"
            "## 日报裁决总览\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 仓位姿态 | 0%不参与 |\n"
            "| 最终对象 | 无 |\n"
            "| 推导摘要 | 没有可用明日执行对象，也没有观察对象 |\n\n"
            "## 最终标的解题过程\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 最终结果 | 观察对象：豫能控股(001896) |\n\n"
            "## 七、最终结论\n"
            "| 明日结论 | 当前盈亏比 | 周期主线 | 当天主攻线 | 当前市场底色 | 重点对象 | 明日执行风格 | 一句话动作 |\n"
            "|----------|------------|----------|------------|--------------|--------------|--------------|------------|\n"
            "| 0%不参与 | 不确定时不值得主动参与 | 电力 | 电力 | 观察聚焦 | 观察对象：豫能控股(001896) | 0%不参与 | 只观察，不新增参与 |\n\n"
            "### 明日行动清单\n"
            "| 项目 | 明日动作 |\n"
            "|------|----------|\n"
            "| 最终对象 | 豫能控股(001896) |\n"
        )

        result = audit_report_markdown(markdown)

        self.assertIn("opening_final_object_empty_conflict", {finding["code"] for finding in result["findings"]})

    def test_audit_flags_front_observation_when_selection_workflow_final_is_empty(self):
        markdown = (
            "# 2026-06-11 a股市场分析\n\n"
            "## 日报裁决总览\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 仓位姿态 | 0%不参与 |\n"
            "| 最终对象 | 观察对象：和远气体(002971) |\n\n"
            "## 明日执行结论\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 明日仓位 | 0%不参与 |\n"
            "| 明日执行对象 | 无 |\n\n"
            "## 七、最终结论\n"
            "| 明日结论 | 当前盈亏比 | 周期主线 | 当天主攻线 | 当前市场底色 | 重点对象 | 明日执行风格 | 一句话动作 |\n"
            "|----------|------------|----------|------------|--------------|--------------|--------------|------------|\n"
            "| 0%不参与 | 不确定时不值得主动参与 | 国产芯片替代 | 国产芯片替代 | 观察聚焦 | 观察对象：和远气体(002971) | 0%不参与 | 只观察，不新增参与 |\n\n"
            "## 推导审计层\n"
            "| 层级 | 节点 | 结论 |\n"
            "|---|---|---|\n"
            "| 最终结果 | N9 / final | 无；0%不参与；0% |\n\n"
            "```mermaid\n"
            "flowchart TD\n"
            "  FINAL[\"最终：暂无\\n仓位：0%\"]\n"
            "```\n"
        )

        result = audit_report_markdown(markdown)
        codes = {finding["code"] for finding in result["findings"]}

        self.assertIn("selection_workflow_mismatch", codes)

    def test_audit_also_flags_appendix_when_front_observation_and_selection_workflow_empty_conflict(self):
        markdown = (
            "# 2026-06-11 a股市场分析\n\n"
            "## 日报裁决总览\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 仓位姿态 | 0%不参与 |\n"
            "| 最终对象 | 观察对象：和远气体(002971) |\n\n"
            "## 明日执行结论\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 明日仓位 | 0%不参与 |\n"
            "| 明日执行对象 | 无 |\n\n"
            "## 推导审计层\n"
            "| 层级 | 节点 | 结论 |\n"
            "|---|---|---|\n"
            "| 最终结果 | N9 / final | 无；0%不参与；0% |\n\n"
            "## 八、详细附录\n"
            "**最终动作表**（只展示真正具备参与资格的对象）:\n"
            "| 明天具体怎么做 | 股票 | 代码 | 触发条件 | 止损/时间 |\n"
            "|----------|------|------|----------|-----------|\n"
            "| ⏳ 确认后执行预案 | 和远气体 | 002971 | 09:50-10:10站上52.75 | 50.11 |\n"
            "| 主观察对象 | 康强电子(002119) |\n"
        )

        result = audit_report_markdown(markdown)
        codes = {finding["code"] for finding in result["findings"]}

        self.assertIn("selection_workflow_mismatch", codes)
        self.assertIn("empty_final_object_appendix_current_object_conflict", codes)

    def test_audit_flags_appendix_current_object_when_front_final_object_is_empty(self):
        markdown = (
            "# 2026-06-11 a股市场分析\n\n"
            "## 日报裁决总览\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 仓位姿态 | 0%不参与 |\n"
            "| 最终对象 | 无 |\n"
            "| 对象性质 | 无明日执行对象 |\n\n"
            "## 明日执行结论\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 明日仓位 | 0%不参与 |\n"
            "| 明日执行对象 | 无 |\n"
            "| 执行性质 | 无明日执行对象 |\n\n"
            "## 七、最终结论\n"
            "| 明日结论 | 当前盈亏比 | 周期主线 | 当天主攻线 | 当前市场底色 | 重点对象 | 明日执行风格 | 一句话动作 |\n"
            "|----------|------------|----------|------------|--------------|--------------|--------------|------------|\n"
            "| 0%不参与 | 不确定时不值得主动参与 | 暂无确认主线 | 暂无确认主攻线 | 观察聚焦 | 暂无 | 0%不参与 | 0%：没有合格标的就不参与 |\n\n"
            "## 八、详细附录\n"
            "##### 附录：最终结论\n"
            "| 项目 | 明日指引 |\n"
            "|------|----------|\n"
            "| 今日关注标的 | 和远气体(002971)：观察对象，先观察强弱与承接 |\n"
            "| 明天观察池 | 和远气体(002971)：观察对象，先观察强弱与承接 |\n"
            "| PK决胜局（期望值模型） | 和远气体(002971)；先观察强弱，不抢跑 |\n\n"
            "**观察优先对象**: 和远气体(002971)\n"
            "- 👀 和远气体(002971) - 观察对象，09:50-10:10观察价待盘中确认\n"
            "- **跨线继续看谁**: 康强电子(002119)\n\n"
            "**最终动作表**（只展示真正具备参与资格的对象）:\n"
            "| 明天具体怎么做 | 股票 | 代码 | 触发条件 | 止损/时间 |\n"
            "|----------|------|------|----------|-----------|\n"
            "| ⏳ 确认后执行预案 | 和远气体 | 002971 | 09:50-10:10站上52.75 | 50.11 |\n\n"
            "##### 附录：# 今日总决策面板（过程证据）\n"
            "| 字段 | 内容 |\n"
            "|------|------|\n"
            "| 主观察对象 | 康强电子(002119) |\n"
            "| 观察对象 | 康强电子(002119) |\n"
        )

        result = audit_report_markdown(markdown)
        codes = {finding["code"] for finding in result["findings"]}

        self.assertIn("empty_final_object_appendix_current_object_conflict", codes)

    def test_audit_flags_stale_appendix_when_front_has_positive_final_action(self):
        markdown = (
            "# 2026-06-15 a股市场分析\n\n"
            "## 日报裁决总览\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 仓位姿态 | 50%条件执行；固定交易窗口条件不成立回到0% |\n"
            "| 最终对象 | 明日执行对象：云南锗业(002428) |\n\n"
            "## 明日执行结论\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 明日仓位 | 已决定50%条件执行；盘中不满足取消，回到0%不参与 |\n"
            "| 明日执行对象 | 云南锗业(002428) |\n\n"
            "## 六、明日执行计划\n"
            "| 明日唯一动作 | 标的 | 参与窗 | 条件 | 不满足怎么办 |\n"
            "|--------------|------|------|------|--------------|\n"
            "| 只看明日执行对象 | 云南锗业(002428) | 09:50-10:10 | 固定交易窗口条件 | 不做 |\n\n"
            "## 七、最终结论\n"
            "| 明日结论 | 当前盈亏比 | 周期主线 | 当天主攻线 | 当前市场底色 | 重点对象 | 明日执行风格 | 一句话动作 |\n"
            "|----------|------------|----------|------------|--------------|--------------|--------------|------------|\n"
            "| 已决定50%条件执行；盘中不满足取消，回到0%不参与 | 合适 | 国产芯片替代 | 国产芯片替代 | 积极聚焦 | 云南锗业(002428) | 50%条件执行 | 按昨晚预案检查执行资格 |\n\n"
            "## 八、详细附录\n"
            "##### 附录：Step 5 - 过程候选最终复核\n"
            "- **现在是什么情况**: 市场允许出手，但还没有缩到一只可买股，明日先等它自己证明\n"
            "\n"
            "**最终动作表**（只展示真正具备参与资格的对象）:\n"
            "| 明天具体怎么做 | 股票 | 代码 | 触发条件 | 止损/时间 |\n"
            "|----------|------|------|----------|-----------|\n"
            "| 👀 明天先盯哪只 | 金安国纪 | 002636 | 09:50-10:10站上97.34后，再看是否走成明天唯一能买的那只 | 92.47 |\n"
        )

        result = audit_report_markdown(markdown)
        codes = {finding["code"] for finding in result["findings"]}

        self.assertIn("positive_final_action_appendix_conflict", codes)
        self.assertFalse(result["passed"])

    def test_audit_flags_positive_appendix_legacy_buy_words_without_zero_wording(self):
        markdown = (
            "# 2026-06-15 a股市场分析\n\n"
            "## 日报裁决总览\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 仓位姿态 | 50%条件执行；固定交易窗口条件不成立回到0% |\n"
            "| 最终对象 | 明日执行对象：云南锗业(002428) |\n\n"
            "## 明日执行结论\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 明日仓位 | 已决定50%条件执行；盘中不满足取消，回到0%不参与 |\n"
            "| 明日执行对象 | 云南锗业(002428) |\n\n"
            "## 六、明日执行计划\n"
            "| 明日唯一动作 | 标的 | 参与窗 | 条件 | 不满足怎么办 |\n"
            "|--------------|------|------|------|--------------|\n"
            "| 只看明日执行对象 | 云南锗业(002428) | 09:50-10:10 | 固定交易窗口条件 | 不做 |\n\n"
            "## 七、最终结论\n"
            "| 明日结论 | 当前盈亏比 | 周期主线 | 当天主攻线 | 当前市场底色 | 重点对象 | 明日执行风格 | 一句话动作 |\n"
            "|----------|------------|----------|------------|--------------|--------------|--------------|------------|\n"
            "| 已决定50%条件执行；盘中不满足取消，回到0%不参与 | 合适 | 国产芯片替代 | 国产芯片替代 | 积极聚焦 | 云南锗业(002428) | 50%条件执行 | 按昨晚预案检查执行资格 |\n\n"
            "## 八、详细附录\n"
            "##### 附录：Step 4 - 明日买点预计算\n"
            "**明日继续观察**（1只，等买点出现）:\n"
            "- **现在是什么情况**: 市场已允许出手，但还没有缩到一只合格参与对象\n"
            "- **接着做什么**: 当前还在等待层，先等买点自己长出来，不提前写成执行对象\n"
            "- **接着做什么**: 进入Step 4，为候选组预计算买点并筛出明天唯一能买的那只\n"
            "- **明天没有可买对象**: 仍等待候选证明\n"
        )

        result = audit_report_markdown(markdown)
        codes = {finding["code"] for finding in result["findings"]}

        self.assertIn("positive_final_action_appendix_conflict", codes)
        self.assertFalse(result["passed"])

    def test_audit_flags_positive_final_target_downgraded_to_watch_row(self):
        markdown = (
            "# 2026-06-24 a股市场分析\n\n"
            "## 日报裁决总览\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 仓位姿态 | 50%条件执行；固定交易窗口条件不成立回到0% |\n"
            "| 最终对象 | 明日执行对象：长电科技(600584) |\n\n"
            "## 明日执行结论\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 明日仓位 | 已决定50%条件执行；盘中不满足取消，回到0%不参与 |\n"
            "| 明日执行对象 | 长电科技(600584) |\n\n"
            "## 六、明日执行计划\n"
            "| 明日唯一动作 | 标的 | 参与窗 | 条件 | 不满足怎么办 |\n"
            "|--------------|------|------|------|--------------|\n"
            "| 只看明日执行对象 | 长电科技(600584) | 09:50-10:10 | 固定交易窗口条件 | 不做 |\n\n"
            "## 七、最终结论\n"
            "| 明日结论 | 当前盈亏比 | 周期主线 | 当天主攻线 | 当前市场底色 | 重点对象 | 明日执行风格 | 一句话动作 |\n"
            "|----------|------------|----------|------------|--------------|--------------|--------------|------------|\n"
            "| 已决定50%条件执行；盘中不满足取消，回到0%不参与 | 合适 | 国产芯片替代 | 国产芯片替代 | 积极聚焦 | 长电科技(600584) | 50%条件执行 | 按昨晚预案检查执行资格 |\n\n"
            "## 八、详细附录\n"
            "**次日市场环境**: 50%条件执行 / 撤退态 - 环境关闭，只做等待，不做新增参与\n"
            "- ✅ 保持空仓：当前不新增参与\n"
            "- ✅ 禁止买入任何方向：无论题材多热，都先等环境重新打开\n"
            "| 明日观察位预计算 | 不开新仓，只保留重点观察谁 |\n"
            "> **真到盘中怎么做**：日报这里只做盘前预案。明日不新增参与，只观察指数图形、主攻线承接；结果进入复盘和下一份日报判断，继续0%不参与。\n"
            "**暂不关注**: 11只（条件链不足）\n"
            "- 长电科技(600584) - 明日执行对象 - 已进入明日执行计划 - 按昨晚预案检查执行资格；不满足回到0%不参与\n"
            "\n**明天仓位怎么放**:\n"
            "- **明天仓位放多少**: 明日买入决定：不买新仓；观察对象只复盘，不参与\n"
            "- **进攻仓位**: 0%不参与；无合格标的或取消条件已经出现\n"
        )

        result = audit_report_markdown(markdown)
        codes = {finding["code"] for finding in result["findings"]}

        self.assertIn("positive_final_action_appendix_conflict", codes)
        self.assertFalse(result["passed"])

    def test_audit_flags_positive_final_action_with_empty_table_and_second_targets(self):
        markdown = (
            "# 2026-06-24 a股市场分析\n\n"
            "## 日报裁决总览\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 仓位姿态 | 已决定50%条件执行；盘中不满足取消，回到0%不参与 |\n"
            "| 最终对象 | 明日执行对象：长电科技(600584) |\n\n"
            "## 明日执行结论\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 明日仓位 | 已决定50%条件执行；盘中不满足取消，回到0%不参与 |\n"
            "| 明日执行对象 | 长电科技(600584) |\n\n"
            "## 六、明日执行计划\n"
            "| 明日唯一动作 | 标的 | 参与窗 | 条件 | 不满足怎么办 |\n"
            "|--------------|------|------|------|--------------|\n"
            "| 只看明日执行对象 | 长电科技(600584) | 09:50-10:10 | 承接确认 | 不做 |\n\n"
            "## 七、最终结论\n"
            "| 明日结论 | 当前盈亏比 | 周期主线 | 当天主攻线 | 当前市场底色 | 重点对象 | 明日执行风格 | 一句话动作 |\n"
            "|----------|------------|----------|------------|--------------|--------------|--------------|------------|\n"
            "| 已决定50%条件执行；盘中不满足取消，回到0%不参与 | 合适 | 半导体 | 半导体 | 积极聚焦 | 长电科技(600584) | 50%条件执行 | 按昨晚预案检查执行资格 |\n\n"
            "## 八、详细附录\n"
            "### 2. 明日条件执行对象\n"
            "| 角色 | 标的 | 速度档 | 买点线 | 卖点线 | 承接修复条件 | 最终复核 | 参与窗 |\n"
            "|------|------|--------|--------|--------|--------------|----------|--------|\n"
            "| 暂无 | - | - | - | - | - | - | - |\n"
            "| 明日主买对象 | 海南海药(000566) | 观察样本 | MA10 | MA20 | 缩量回撤到MA10附近 | 通过 |\n"
            "| 明日补位对象 | 金安国纪(002636) | 极致加速龙头 | MA3 | MA5 | 缩量回撤到MA3附近 | 通过 |\n"
            "**观察优先对象**: 海南海药(000566)\n"
            "- **出手时怎么做**: 盘前0%就是不买新仓；09:50-10:10窗口只记录承接，不评估新增参与\n"
            "- 当前是0%不参与，本时段只观察主线核心是否在固定交易窗口内满足条件\n"
            "- 重点观察优先对象是否继续走强；确认后也只进入复盘和下一份日报判断，未确认保持0%\n"
        )

        result = audit_report_markdown(markdown)
        codes = {finding["code"] for finding in result["findings"]}

        self.assertIn("positive_final_action_appendix_conflict", codes)
        self.assertFalse(result["passed"])

    def test_audit_flags_appendix_code_block_final_object_when_front_final_object_is_empty(self):
        markdown = (
            "# 2026-06-11 a股市场分析\n\n"
            "## 日报裁决总览\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 仓位姿态 | 0%不参与 |\n"
            "| 最终对象 | 无 |\n\n"
            "## 明日执行结论\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 明日仓位 | 0%不参与 |\n"
            "| 明日执行对象 | 无 |\n\n"
            "## 七、最终结论\n"
            "| 明日结论 | 当前盈亏比 | 周期主线 | 当天主攻线 | 当前市场底色 | 重点对象 | 明日执行风格 | 一句话动作 |\n"
            "|----------|------------|----------|------------|--------------|--------------|--------------|------------|\n"
            "| 0%不参与 | 不确定时不值得主动参与 | 暂无确认主线 | 暂无确认主攻线 | 观察聚焦 | 暂无 | 0%不参与 | 0%：没有合格标的就不参与 |\n\n"
            "## 八、详细附录\n"
            "```text\n"
            "阶段四：最终对象解析\n"
            "`-- 最终对象=和远气体(002971) 身份=观察对象\n"
            "```\n"
        )

        result = audit_report_markdown(markdown)
        codes = {finding["code"] for finding in result["findings"]}

        self.assertIn("empty_final_object_appendix_current_object_conflict", codes)

    def test_audit_allows_appendix_process_candidates_when_front_final_object_is_empty(self):
        markdown = (
            "# 2026-06-11 a股市场分析\n\n"
            "## 日报裁决总览\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 仓位姿态 | 0%不参与 |\n"
            "| 最终对象 | 无 |\n\n"
            "## 明日执行结论\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 明日仓位 | 0%不参与 |\n"
            "| 明日执行对象 | 无 |\n\n"
            "## 七、最终结论\n"
            "| 明日结论 | 当前盈亏比 | 周期主线 | 当天主攻线 | 当前市场底色 | 重点对象 | 明日执行风格 | 一句话动作 |\n"
            "|----------|------------|----------|------------|--------------|--------------|--------------|------------|\n"
            "| 0%不参与 | 不确定时不值得主动参与 | 暂无确认主线 | 暂无确认主攻线 | 观察聚焦 | 暂无 | 0%不参与 | 0%：没有合格标的就不参与 |\n\n"
            "## 八、详细附录\n"
            "| 今日关注标的 | 无当前对象；个股仅保留在过程候选回放 |\n"
            "| 明天观察池 | 无当前对象；个股仅保留在过程候选回放 |\n"
            "**观察优先对象**: 暂无\n"
            "- 👀 和远气体(002971) - 过程候选，09:50-10:10观察价待盘中确认\n"
            "- **跨线回看样本**: 康强电子(002119)（过程证据，不是当前对象）\n"
            "| 明天具体怎么做 | 股票 | 代码 | 触发条件 | 止损/时间 |\n"
            "|----------|------|------|----------|-----------|\n"
            "| 暂无执行预案 | - | - | 当前最终对象为空，只回放过程候选，不新增参与 | - |\n"
            "| 主观察对象 | 暂无 |\n"
            "| 观察对象 | 暂无 |\n"
        )

        result = audit_report_markdown(markdown)
        codes = {finding["code"] for finding in result["findings"]}

        self.assertNotIn("empty_final_object_appendix_current_object_conflict", codes)

    def test_audit_allows_final_execution_object_in_history_table_when_not_downgraded(self):
        markdown = GOOD_MARKDOWN.replace(
            "| 2026-04-24 | 富瀚微 | 300613 | 1 | 半导体 | 09:50-10:10 | 等待复盘 | 等待计划窗口事实回写 | 按原计划作废条件处理 | 2026-04-24:300613 |",
            f"| 2026-04-24 | 富瀚微 | 300613 | 1 | 半导体 | 09:50-10:10 | 等待复盘 | 富瀚微(300613)已进入明日执行计划；{PREMARKET_50_TRIGGER_TEXT} | 按原计划作废条件处理 | 2026-04-24:300613 |",
        ) + (
            "\n**重点观察历史回测表**（拆分选股样本、观察位质量、执行复盘）:（过程证据）\n"
            "| 入选日 | 股票 | 代码 | 选股样本 | 识别评价 | 观察位窗口 | 盈亏比 | 观察位质量 | 执行复盘 | 后续1日 | 后续3日 | 后续5日 | 最大回撤5日 | 来源日期 | 缺失字段 | 历史标准动作 |\n"
            "|--------|------|------|----------|----------|----------|--------|----------|----------|----------|----------|----------|------------|----------|----------|----------|\n"
            f"| 2026-04-24 | 富瀚微 | 300613 | 明日执行对象 | 待验证 | 09:50-10:10 | 待计算 | 待补事实 | 等待复盘 | 待补事实 | 待补事实 | 待补事实 | 待补事实 | 2026-04-24 | T+1/T+3/T+5表现与回撤字段 | 富瀚微(300613)已进入明日执行计划；{PREMARKET_50_TRIGGER_TEXT} |\n"
        )

        result = audit_report_markdown(markdown)
        codes = {finding["code"] for finding in result["findings"]}

        self.assertNotIn("front_execution_object_downgraded", codes)
        self.assertTrue(result["passed"], result["findings"])

    def test_audit_flags_current_daily_judgment_core_candidate_mismatch(self):
        markdown = (
            "# 2026-06-10 a股市场分析\n\n"
            "## 日报裁决总览\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 仓位姿态 | 0%不参与 |\n"
            "| 最终对象 | 观察对象：中船特气(688146) |\n\n"
            "**今日判断（2026-06-10，等待下一交易日验证）**\n"
            "| 判断项 | 今日结论 | 下一交易日验证点 |\n"
            "|--------|----------|------------------|\n"
            "| 核心候选判断 | 双星新材(002585) | 下一交易日验证是否进入资金视野 |\n\n"
            "## 七、最终结论\n"
            "| 明日结论 | 当前盈亏比 | 周期主线 | 当天主攻线 | 当前市场底色 | 重点对象 | 明日执行风格 | 一句话动作 |\n"
            "|----------|------------|----------|------------|--------------|--------------|--------------|------------|\n"
            "| 0%不参与 | 不确定时不值得主动参与 | 暂无确认主线 | 暂无确认主攻线 | 观察聚焦 | 观察对象：中船特气(688146) | 0%不参与 | 只观察，不新增参与 |\n"
        )

        result = audit_report_markdown(markdown)
        codes = {finding["code"] for finding in result["findings"]}

        self.assertIn("daily_judgment_core_candidate_mismatch", codes)
        self.assertIn("daily_judgment_core_candidate_without_execution", codes)

    def test_audit_flags_concrete_core_candidate_even_when_it_matches_zero_position_observation_object(self):
        markdown = (
            "# 2026-06-10 a股市场分析\n\n"
            "## 日报裁决总览\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 仓位姿态 | 0%不参与 |\n"
            "| 最终对象 | 观察对象：双星新材(002585) |\n\n"
            "**今日判断（2026-06-10，等待下一交易日验证）**\n"
            "| 判断项 | 今日结论 | 下一交易日验证点 |\n"
            "|--------|----------|------------------|\n"
            "| 核心候选判断 | 双星新材(002585) | 下一交易日验证是否进入资金视野 |\n\n"
            "## 七、最终结论\n"
            "| 明日结论 | 当前盈亏比 | 周期主线 | 当天主攻线 | 当前市场底色 | 重点对象 | 明日执行风格 | 一句话动作 |\n"
            "|----------|------------|----------|------------|--------------|--------------|--------------|------------|\n"
            "| 0%不参与 | 不确定时不值得主动参与 | 暂无确认主线 | 暂无确认主攻线 | 观察聚焦 | 观察对象：双星新材(002585) | 0%不参与 | 只观察，不新增参与 |\n"
        )

        result = audit_report_markdown(markdown)
        codes = {finding["code"] for finding in result["findings"]}

        self.assertNotIn("daily_judgment_core_candidate_mismatch", codes)
        self.assertIn("daily_judgment_core_candidate_without_execution", codes)

    def test_audit_accepts_empty_current_daily_judgment_core_candidate_when_zero_position(self):
        markdown = (
            "# 2026-06-10 a股市场分析\n\n"
            "## 日报裁决总览\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 仓位姿态 | 0%不参与 |\n"
            "| 最终对象 | 观察对象：中船特气(688146) |\n\n"
            "**今日判断（2026-06-10，等待下一交易日验证）**\n"
            "| 判断项 | 今日结论 | 下一交易日验证点 |\n"
            "|--------|----------|------------------|\n"
            "| 核心候选判断 | 待补事实 | 下一交易日验证是否进入资金视野 |\n\n"
            "## 七、最终结论\n"
            "| 明日结论 | 当前盈亏比 | 周期主线 | 当天主攻线 | 当前市场底色 | 重点对象 | 明日执行风格 | 一句话动作 |\n"
            "|----------|------------|----------|------------|--------------|--------------|--------------|------------|\n"
            "| 0%不参与 | 不确定时不值得主动参与 | 暂无确认主线 | 暂无确认主攻线 | 观察聚焦 | 观察对象：中船特气(688146) | 0%不参与 | 只观察，不新增参与 |\n"
        )

        result = audit_report_markdown(markdown)
        codes = {finding["code"] for finding in result["findings"]}

        self.assertNotIn("daily_judgment_core_candidate_mismatch", codes)
        self.assertNotIn("daily_judgment_core_candidate_without_execution", codes)

    def test_audit_flags_unresolved_fact_in_settled_daily_judgment_tables(self):
        markdown = (
            GOOD_MARKDOWN
            + "\n## 判断纠偏与今日五项结论\n"
            + "**近1个已结算交易日复盘表现（2026-05-29至2026-05-29）**\n"
            + "| 判断项 | 已结算表现 | 最近结论 | 预期 | 实际 | 原因 |\n"
            + "|--------|--------|----------|------|------|------|\n"
            + "| 市场状态判断 | 待补事实 | 待补事实 | - | - | 缺少市场状态复盘事实 |\n\n"
            + "**结算上一交易日：2026-05-29**\n"
            + "| 判断项 | 结论 | 预期 | 实际 | 原因 |\n"
            + "|--------|------|------|------|------|\n"
            + "| 主线判断 | 待补事实 | 未归类 | 等待市场选择 | 缺少事实：mainline_review |\n\n"
            + "**上一交易日未完成结算**\n"
            + "| 判断项 | 状态 | 缺少事实 |\n"
            + "|--------|------|----------|\n"
            + "| 主线判断 | 待补事实 | mainline_review |\n\n"
            + "**今日判断（2026-06-10，等待下一交易日验证）**\n"
            + "| 判断项 | 今日结论 | 下一交易日验证点 |\n"
            + "|--------|----------|------------------|\n"
            + "| 核心候选判断 | 待补事实 | 下一交易日验证是否进入资金视野 |\n"
        )

        result = audit_report_markdown(markdown)
        codes = [finding["code"] for finding in result["findings"]]

        self.assertGreaterEqual(codes.count("daily_judgment_settled_table_unresolved_fact"), 2)
        self.assertFalse(result["passed"])

    def test_audit_flags_final_observation_object_in_derivation_rejected_list(self):
        markdown = (
            "# 2026-06-04 a股市场分析\n\n"
            "## 日报裁决总览\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 仓位姿态 | 0%不参与 |\n"
            "| 最终对象 | 观察对象：豫能控股(001896) |\n\n"
            "## 七、最终结论\n"
            "| 明日结论 | 当前盈亏比 | 周期主线 | 当天主攻线 | 当前市场底色 | 重点对象 | 明日执行风格 | 一句话动作 |\n"
            "|----------|------------|----------|------------|--------------|--------------|--------------|------------|\n"
            "| 0%不参与 | 不确定时不值得主动参与 | 电力 | 电力 | 观察聚焦 | 观察对象：豫能控股(001896) | 0%不参与 | 只观察，不新增参与 |\n\n"
            "## 推导审计层\n"
            "### Step 4：候选收缩\n"
            "#### 本步判断\n"
            "- 淘汰对象：上海石化(600688)、豫能控股(001896)\n"
        )

        result = audit_report_markdown(markdown)

        self.assertIn("final_object_rejected_in_derivation_audit", {finding["code"] for finding in result["findings"]})

    def test_audit_flags_circular_process_candidate_loss_reason(self):
        markdown = (
            "# 2026-06-04 a股市场分析\n\n"
            "## 日报裁决总览\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 最终对象 | 观察对象：豫能控股(001896) |\n\n"
            "## 七、最终结论\n"
            "| 明日结论 | 当前盈亏比 | 周期主线 | 当天主攻线 | 当前市场底色 | 重点对象 | 明日执行风格 | 一句话动作 |\n"
            "|----------|------------|----------|------------|--------------|--------------|--------------|------------|\n"
            "| 0%不参与 | 不确定时不值得主动参与 | 电力 | 电力 | 观察聚焦 | 观察对象：豫能控股(001896) | 0%不参与 | 只观察，不新增参与 |\n\n"
            "## 八、详细附录\n"
            "## 狙击手最终标的完整路径图（过程证据）\n"
            "```text\n"
            "|-- 来源序号=1 来源=执行链观察对象 候选=上海石化(600688) 身份=过程候选 去向=被替换 原因=最终解析未选为最终观察对象\n"
            "`-- 最终对象=豫能控股(001896) 身份=观察对象\n"
            "```\n"
        )

        result = audit_report_markdown(markdown)

        self.assertIn("process_candidate_loss_reason_circular", {finding["code"] for finding in result["findings"]})

    def test_audit_flags_result_only_kept_process_reason(self):
        markdown = (
            "# 2026-06-04 a股市场分析\n\n"
            "## 日报裁决总览\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 最终对象 | 观察对象：豫能控股(001896) |\n\n"
            "## 七、最终结论\n"
            "| 明日结论 | 当前盈亏比 | 周期主线 | 当天主攻线 | 当前市场底色 | 重点对象 | 明日执行风格 | 一句话动作 |\n"
            "|----------|------------|----------|------------|--------------|--------------|--------------|------------|\n"
            "| 0%不参与 | 不确定时不值得主动参与 | 电力 | 电力 | 观察聚焦 | 观察对象：豫能控股(001896) | 0%不参与 | 只观察，不新增参与 |\n\n"
            "## 八、详细附录\n"
            "## 狙击手最终标的完整路径图（过程证据）\n"
            "```text\n"
            "|-- 来源序号=2 来源=候选质量面板备用观察 候选=豫能控股(001896) 身份=过程候选 去向=保留 原因=进入最终观察对象\n"
            "`-- 最终对象=豫能控股(001896) 身份=观察对象\n"
            "```\n"
        )

        result = audit_report_markdown(markdown)

        self.assertIn("process_candidate_loss_reason_circular", {finding["code"] for finding in result["findings"]})

    def test_audit_flags_b_level_without_conditions(self):
        markdown = (
            "# 2026-06-04 a股市场分析\n\n"
            "## 明日执行结论\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 明日仓位 | 已决定50%条件执行；盘中不满足取消，回到0%不参与 |\n"
            "| 明日执行对象 | 豫能控股(001896) |\n"
            "| 执行性质 | 50%条件执行，约50%仓位 |\n"
            "| 不满足条件 | 不参与 |\n\n"
            "## 明日账户建议\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 明日动作 | 已决定50%条件执行 |\n"
        )

        result = audit_report_markdown(markdown)

        self.assertIn("b_level_conditions_missing", {finding["code"] for finding in result["findings"]})

    def test_audit_accepts_full_or_empty_account_conditions(self):
        markdown = (
            "# 2026-06-04 a股市场分析\n\n"
            "## 明日执行结论\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 明日仓位 | 已决定满仓条件执行；盘中不满足取消，回到0%不参与 |\n"
            "| 明日执行对象 | 豫能控股(001896) |\n"
            "| 执行性质 | 满仓条件执行 |\n"
            "| 不满足条件 | 不参与 |\n\n"
            "## 满仓条件执行条件\n"
            "| 触发类型 | 必须满足 | 窗口 | 动作 |\n"
            "|----------|----------|------|------|\n"
            "| 低开承接型 | 靠近MA5；收回VWAP/0轴 | 09:50-10:10 | 满仓条件执行 |\n"
            "| 主动进攻型 | 大单净流入达标；VWAP上方保持 | 09:30-09:35 | 满仓条件执行 |\n\n"
            "## 七、最终结论\n"
            "| 明日结论 | 当前盈亏比 | 周期主线 | 当天主攻线 | 当前市场底色 | 重点对象 | 明日执行风格 | 一句话动作 |\n"
            "|----------|------------|----------|------------|--------------|--------------|--------------|------------|\n"
            f"| 已决定满仓条件执行；盘中不满足取消，回到0%不参与 | 不确定时不值得主动参与 | 电力 | 电力 | 观察聚焦 | 豫能控股(001896) | 满仓条件执行 | {PREMARKET_50_TRIGGER_TEXT} |\n"
        )

        result = audit_report_markdown(markdown)

        codes = {finding["code"] for finding in result["findings"]}
        self.assertNotIn("b_level_conditions_missing", codes)
        self.assertNotIn("position_style_missing_grade", codes)

    def test_audit_flags_execution_object_mismatch_between_front_and_audit_layer(self):
        markdown = (
            "# 2026-06-04 a股市场分析\n\n"
            "## 明日执行结论\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 明日执行对象 | 豫能控股(001896) |\n\n"
            "## 50%条件执行条件\n"
            "| 触发类型 | 必须满足 | 窗口 | 动作 |\n"
            "|----------|----------|------|------|\n"
            "| 低开承接型 | 靠近MA5；收回VWAP/0轴 | 09:50-10:10 | 50%条件执行 |\n"
            "| 主动进攻型 | 大单净流入达标；VWAP上方保持 | 09:30-09:35 | 50%条件执行 |\n\n"
            "## 推导审计层\n"
            "### Step 2：主方向与候选收缩\n"
            "#### 传给下一步\n"
            "- 条件执行对象：上海石化(600688)\n"
        )

        result = audit_report_markdown(markdown)

        self.assertIn("two_layer_execution_object_mismatch", {finding["code"] for finding in result["findings"]})

    def test_audit_treats_empty_two_layer_execution_object_as_no_target(self):
        markdown = (
            "# 2026-06-04 a股市场分析\n\n"
            "## 明日执行结论\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 明日仓位 | 0%不参与 |\n"
            "| 明日执行对象 | 无 |\n"
            "| 执行性质 | 无明日执行对象 |\n\n"
            "## 明日账户建议\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 旧口径残留 | 当前不是执行对象，不能定义明日执行对象 |\n\n"
            "## 推导审计层\n"
            "### Step 2：主方向与候选收缩\n"
            "#### 本步判断\n"
            "- 本步判断：当前无明日执行对象\n"
            "#### 传给下一步\n"
            "- 传给下一步：无明日执行对象，保持0%不参与\n"
        )

        result = audit_report_markdown(markdown)

        codes = {finding["code"] for finding in result["findings"]}
        self.assertNotIn("two_layer_execution_object_mismatch", codes)
        self.assertNotIn("front_execution_object_negated", codes)
        self.assertNotIn("front_execution_object_downgraded", codes)

    def test_audit_flags_front_page_that_negates_declared_execution_object(self):
        markdown = (
            "# 2026-06-04 a股市场分析\n\n"
            "## 明日执行结论\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 明日仓位 | 已决定50%条件执行；盘中不满足取消，回到0%不参与 |\n"
            "| 明日执行对象 | 豫能控股(001896) |\n\n"
            "## 50%条件执行条件\n"
            "| 触发类型 | 必须满足 | 窗口 | 动作 |\n"
            "|----------|----------|------|------|\n"
            "| 低开承接型 | 靠近MA5；收回VWAP/0轴 | 09:50-10:10 | 50%条件执行 |\n"
            "| 主动进攻型 | 大单净流入达标；VWAP上方保持 | 09:30-09:35 | 50%条件执行 |\n\n"
            "## 明日账户建议\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 观察对象 | 豫能控股(001896)：观察对象，不是执行对象 |\n"
            "| 明日执行目标 | 持仓未输入，不能定义明日执行对象 |\n"
        )

        result = audit_report_markdown(markdown)

        self.assertIn("front_execution_object_negated", {finding["code"] for finding in result["findings"]})

    def test_audit_flags_declared_execution_object_reduced_to_observation_anchor(self):
        markdown = (
            "# 2026-06-04 a股市场分析\n\n"
            "## 明日执行结论\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 明日仓位 | 已决定50%条件执行；盘中不满足取消，回到0%不参与 |\n"
            "| 明日执行对象 | 豫能控股(001896) |\n\n"
            "## 50%条件执行条件\n"
            "| 触发类型 | 必须满足 | 窗口 | 动作 |\n"
            "|----------|----------|------|------|\n"
            "| 低开承接型 | 靠近MA5；收回VWAP/0轴 | 09:50-10:10 | 50%条件执行 |\n"
            "| 主动进攻型 | 大单净流入达标；VWAP上方保持 | 09:30-09:35 | 50%条件执行 |\n\n"
            "## 六、明日执行计划\n"
            "| 明日观察动作 | 标的 | 观察窗 | 条件 | 不满足怎么办 |\n"
            "|--------------|------|------|------|--------------|\n"
            "| 只看观察对象 | 豫能控股(001896) | 09:50-10:10 | 主线承接 | 不满足继续0% |\n\n"
            "## 七、最终结论\n"
            "| 明日结论 | 当前盈亏比 | 周期主线 | 当天主攻线 | 当前市场底色 | 重点对象 | 明日执行风格 | 一句话动作 |\n"
            "|----------|------------|----------|------------|--------------|--------------|--------------|------------|\n"
            "| 0%不参与 | 不确定时不值得主动参与 | 暂无 | 暂无 | 观察聚焦 | 观察对象：豫能控股(001896) | 0%不参与 | 盘前0%；只观察豫能控股，不能转成新增参与 |\n\n"
            "## 八、详细附录\n"
            "```text\n"
            "`-- 最终对象=豫能控股(001896) 身份=观察对象\n"
            "```\n"
        )

        result = audit_report_markdown(markdown)

        self.assertIn("front_execution_object_downgraded", {finding["code"] for finding in result["findings"]})

    def test_audit_flags_two_layer_conditional_execution_on_zero_position_front(self):
        markdown = (
            "# 2026-06-04 a股市场分析\n\n"
            "## 明日执行结论\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 明日仓位 | 已决定50%条件执行；盘中不满足取消，回到0%不参与 |\n"
            "| 明日执行对象 | 豫能控股(001896) |\n"
            "| 不满足条件 | 不参与 |\n\n"
            "## 50%条件执行条件\n"
            "| 触发类型 | 必须满足 | 窗口 | 动作 |\n"
            "|----------|----------|------|------|\n"
            "| 低开承接型 | 靠近MA5；收回VWAP/0轴 | 09:50-10:10 | 50%条件执行 |\n"
            "| 主动进攻型 | 大单净流入达标；VWAP上方保持 | 09:30-09:35 | 50%条件执行 |\n\n"
            "## 七、最终结论\n"
            "| 明日结论 | 当前盈亏比 | 周期主线 | 当天主攻线 | 当前市场底色 | 唯一重点对象 | 明日执行风格 | 一句话动作 |\n"
            "|----------|------------|----------|------------|--------------|--------------|--------------|------------|\n"
            "| 0%不参与 | 不确定时不值得主动参与 | 暂无 | 暂无 | 观察聚焦 | 观察对象：豫能控股(001896) | 0%不参与 | 条件满足才50%条件执行；不满足回到0% |\n"
        )

        result = audit_report_markdown(markdown)

        codes = {finding["code"] for finding in result["findings"]}
        self.assertIn("zero_position_tomorrow_action_conflict", codes)
        self.assertIn("premarket_fixed_decision_legacy_wording", codes)

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
            "| 50%条件执行 | 正盈亏比 | 半导体 | 半导体 | 修复 | 富瀚微(300613) | 50%条件执行 | 50%：只做合格对象，按昨晚预案检查执行资格，B1未变强不补B2，不满足回到0% |",
            "| 50%条件执行 | 正盈亏比 | 半导体 | 半导体 | 修复 | 富瀚微(300613) | 空仓 / 短线确认 | 条件不满足就不做 |",
        )

        result = audit_report_markdown(bad)

        self.assertIn("legacy_position_style", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_flags_market_fit_row_outside_status_table(self):
        bad = GOOD_MARKDOWN.replace(
            "## 二、市场基底\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 市场状态 | 收缩防守 |\n",
            "## 二、市场基底\n"
            "### 2. 市场状态结论\n"
            "| 市场贴合度 | 主线偏差 |\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 市场状态 | 收缩防守 |\n",
        )

        result = audit_report_markdown(bad)

        codes = {finding["code"] for finding in result["findings"]}
        self.assertIn("market_fit_row_outside_status_table", codes)
        self.assertIn("market_status_table_basis_missing", codes)
        self.assertFalse(result["passed"])

    def test_audit_flags_front_margin_pressure_pending_when_appendix_has_rows(self):
        bad = GOOD_MARKDOWN.replace(
            "## 二、市场基底\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 市场状态 | 收缩防守 |\n",
            "## 二、市场基底\n"
            "### 2. 市场状态结论\n"
            "| 项目 | 结论 | 依据 |\n"
            "|------|------|------|\n"
            "| 市场情绪总状态 | 震荡 | 看盘面亏钱效应 |\n"
            "| 融资承接压力 | 待累计 | 待累计 |\n",
        ).replace(
            "### 附录B：历史主线池\n",
            "#### 附录A：融资承接压力完整25日表\n"
            "| 日期 | 融资余额 | 两市成交额 | 融资承接比 | 压力差 | 状态 | 较前日 |\n"
            "|------|----------|------------|------------|--------|------|--------|\n"
            + "\n".join(
                f"| 2026-05-{day:02d} | 28000.00亿 | 30000.00亿 | 93.00% | -7.00% | 中性 | +0.10pct |"
                for day in range(1, 26)
            )
            + "\n\n### 附录B：历史主线池\n",
        )

        result = audit_report_markdown(bad)

        self.assertIn("market_status_margin_pressure_stale", {finding["code"] for finding in result["findings"]})
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
            ("满仓条件执行", "满仓或0%不参与"),
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

    def test_audit_flags_full_or_empty_account_fractional_surface(self):
        bad = GOOD_MARKDOWN.replace(
            "| 明日仓位 | 50%条件执行；最大上限50%；B1参与权，B2确认权 |",
            "| 明日仓位 | 已决定满仓条件执行；盘中不满足取消，回到0%不参与 |",
        )

        result = audit_report_markdown(bad)

        self.assertIn("full_or_empty_account_fractional_surface", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_flags_market_snapshot_no_risk_conflict(self):
        bad = GOOD_MARKDOWN + "\n### 附录：十四、市场快照\n- **核心特征**: 跌停12只\n- **风险点**: 暂无明确风险\n"

        result = audit_report_markdown(bad)

        self.assertIn("market_snapshot_risk_conflict", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_flags_legacy_timeline_qualification_wording(self):
        bad = GOOD_MARKDOWN + "\n| 旧仓处理 | 新仓是否叠加单独看Tb/Tc资格 |\n"

        result = audit_report_markdown(bad)

        self.assertIn("legacy_timeline_qualification_wording", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_flags_legacy_execution_object_surface_wording(self):
        bad = GOOD_MARKDOWN + "\n- 过程原因：已进入明日执行对象\n"

        result = audit_report_markdown(bad)

        self.assertIn("legacy_execution_object_surface_wording", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_flags_sector_fund_flow_visible_all_zero_table(self):
        bad = GOOD_MARKDOWN + (
            "\n### 资金流入TOP10\n"
            "| 排名 | 板块 | 净流入 | 涨跌幅 |\n"
            "|------|------|--------|--------|\n"
            "| 1 | 半导体 | +0.00亿 | +0.00% |\n"
            "| 2 | 通信设备 | +0.00亿 | +0.00% |\n"
            "| 3 | 消费电子 | +0.00亿 | +0.00% |\n"
            "\n### 资金流出结果\n"
            "| 排名 | 板块 | 净流出 | 涨跌幅 |\n"
            "|------|------|--------|--------|\n"
            "| 1 | 化学制药 | 0.00亿 | +0.00% |\n"
            "| 2 | 医疗服务 | 0.00亿 | +0.00% |\n"
            "| 3 | 工业金属 | 0.00亿 | +0.00% |\n"
        )

        result = audit_report_markdown(bad)

        self.assertIn("sector_fund_flow_visible_all_zero", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_flags_html_timeline_missing_from_markdown(self):
        html = (
            '<div class="position-timeline-shell">'
            '<tr class="timeline-row timeline-row-ta">'
            '<span class="timeline-asset-name">太极实业</span><span class="timeline-asset-code">600667</span>'
            '</tr>'
            '<tr class="timeline-row timeline-row-tb">'
            '<span class="timeline-asset-name">深科技</span><span class="timeline-asset-code">000021</span>'
            '</tr>'
            '<tr class="timeline-row timeline-row-tc"><span class="timeline-asset-empty">无</span></tr>'
            '</div>'
        )

        result = audit_report_markdown(GOOD_MARKDOWN, companion_html=html)

        self.assertIn("position_timeline_markdown_missing", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_accepts_timeline_section_after_report_heading(self):
        markdown = (
            "# 2026-04-24 a股市场分析\n\n"
            "## 账户日序表\n"
            "| 轨道 | 标的 | 2026-04-24（周五） | 2026-04-27（周一） | 2026-04-28（周二） | 2026-04-29（周三） |\n"
            "|------|------|------|------|------|------|\n"
            "| Ta旧仓 | 持仓未输入 | 先确认旧仓 | 确认后再处理 | 未确认前不假定空仓 | 空仓 |\n"
            "| Tb明日目标 | 富瀚微(300613) | 空仓 | Tb+0 明日目标 | Tb+1 只按昨晚预案执行或取消 | Tb+2 未执行则回到空仓 |\n"
            "| Tc复核位 | 无 | 空仓 | 空仓 | 没有Tc+0，不提前占用 | 空仓 |\n\n"
            + self.zero_position_report_with_decision_attribution()
        )
        html = (
            '<div class="position-timeline-shell">'
            '<tr class="timeline-row timeline-row-ta">'
            '<span class="timeline-asset-name">持仓未输入</span>'
            '</tr>'
            '<tr class="timeline-row timeline-row-tb">'
            '<span class="timeline-asset-name">富瀚微</span><span class="timeline-asset-code">300613</span>'
            '</tr>'
            '<tr class="timeline-row timeline-row-tc"><span class="timeline-asset-empty">无</span></tr>'
            '</div>'
        )

        result = audit_report_markdown(markdown, companion_html=html)

        codes = {finding["code"] for finding in result["findings"]}
        self.assertNotIn("position_timeline_markdown_missing", codes)
        self.assertNotIn("known_old_position_conflicts_with_unknown_holding", codes)

    def test_audit_flags_explicit_bear_html_without_position_timeline(self):
        markdown = (
            "## 账户日序表\n"
            "| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |\n"
            "|------|------|----------|----------|-------------|------|\n"
            "| Td | 2026-07-10（周五） | 报告日：前日报计划推定，待成交确认：长电科技(600584) | 长电科技(600584) | Te不新增参与，B2取消 | 只观察，不新增参与 |\n"
            "| Te | 2026-07-13（周一） | 前日报计划对象待成交确认：长电科技(600584) | 长电科技(600584) | 确认已成交才视为B1；未确认不新增B2 | 先确认成交事实；未成交不补B2 |\n\n"
            + GOOD_MARKDOWN
        )

        result = audit_report_markdown(
            markdown,
            companion_html="<html><body>缠论伴随页</body></html>",
            position_companion_html="<html><body>日报正文</body></html>",
        )

        self.assertIn("position_timeline_html_missing", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_does_not_require_position_timeline_from_chanlun_companion(self):
        markdown = (
            "## 账户日序表\n"
            "| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |\n"
            "|------|------|----------|----------|-------------|------|\n"
            "| Td | 2026-07-10（周五） | 报告日：空仓 | - | 无B1占用 | 只观察，不新增参与 |\n"
            "| Te | 2026-07-13（周一） | 继续空仓 | - | 不生成B1/B2 | 只观察，不新增参与 |\n\n"
            + GOOD_MARKDOWN
        )

        result = audit_report_markdown(
            markdown,
            companion_html="<html><body>缠论伴随页</body></html>",
        )

        self.assertNotIn("position_timeline_html_missing", {finding["code"] for finding in result["findings"]})

    def test_audit_flags_tb_timeline_target_when_final_action_is_zero_position(self):
        markdown = (
            "## 账户日序表\n"
            "| 轨道 | 标的 | 2026-07-05（周日） | 2026-07-06（周一） | 2026-07-07（周二） | 2026-07-08（周三） |\n"
            "|------|------|------|------|------|------|\n"
            "| Ta旧仓 | 空仓 | Ta+0 空仓 | 空仓 | 空仓 | 空仓 |\n"
            "| Tb明日目标 | 长电科技(600584) | 空仓 | 报告日确认明日目标 | Tb+0 条件买入，不是无条件买入 | Tb+1 只按昨晚预案执行或取消 |\n"
            "| Tc复核位 | 无 | 空仓 | 空仓 | 没有Tc+0，不提前占用 | 下一份日报再复核 |\n\n"
            + self.zero_position_report_with_decision_attribution()
            + "\n## 选股流程最终推导\n| 最终结果 | N9 / final | 无；0%不参与；0% |\n"
        )

        result = audit_report_markdown(markdown)

        self.assertIn("position_timeline_final_conflict", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_flags_tb_timeline_target_when_final_object_is_different(self):
        markdown = (
            "## 账户日序表\n"
            "| 轨道 | 标的 | 2026-07-07（周二） | 2026-07-08（周三） | 2026-07-09（周四） | 2026-07-10（周五） |\n"
            "|------|------|------|------|------|------|\n"
            "| Ta旧仓 | 空仓 | Ta+0 空仓 | 空仓 | 空仓 | 空仓 |\n"
            "| Tb明日目标 | 和远气体(002971) | 空仓 | Tb+0 明日目标 | Tb+1 只按昨晚预案执行或取消 | Tb+2 未执行则回到空仓 |\n"
            "| Tc复核位 | 无 | 空仓 | 空仓 | 没有Tc+0，不提前占用 | 空仓 |\n\n"
            + GOOD_MARKDOWN
        )

        result = audit_report_markdown(markdown)

        self.assertIn("position_timeline_final_conflict", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_flags_missing_history_path_in_day_order_table(self):
        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            (root / "2026-07-08_A股日报_执行摘要.md").write_text(
                "\n".join(
                    [
                        "| 明日执行对象 | 无 |",
                        "| 对象性质 | 无明日执行对象 |",
                        "| 旧仓处理 | 持有华天科技(002185)，100%仓位，上一份日报明日标的默认1x旧仓 |",
                    ]
                ),
                encoding="utf-8",
            )
            path = root / "2026-07-09_A股日报_完整版.md"
            markdown = (
                "## 账户日序表\n"
                "| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |\n"
                "|------|------|----------|----------|-------------|------|\n"
                "| Ta | 2026-07-06（周一） | 最远复盘日 | - | 不生成B1/B2 | 只作路径校对，不改变Te动作 |\n"
                "| Tb | 2026-07-07（周二） | 历史复盘日 | - | 不生成B1/B2 | 只作路径校对，不改变Te动作 |\n"
                "| Tc | 2026-07-08（周三） | 前一交易日空仓 | - | 无B1占用 | 等待Td报告确认 |\n"
                "| Td | 2026-07-09（周四） | 报告日：空仓 | 无 | 只定Te预案，不下单；B2不存在直到Te确认 | 写清执行资格和取消条件 |\n"
                "| Te | 2026-07-10（周五） | 新目标单独看B1，不用旧仓亏损补仓 | 长电科技(600584) | B1参与权；B2确认权 | B1未变强则取消B2；只检查B1 |\n\n"
                + GOOD_MARKDOWN
            )

            result = audit_report_markdown(markdown, source_path=path)

        self.assertIn("position_day_order_history_path_missing", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_flags_missing_postgres_inferred_history_path(self):
        markdown = (
            "## 账户日序表\n"
            "| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |\n"
            "|------|------|----------|----------|-------------|------|\n"
            "| Ta | 2026-07-07（周二） | 最远复盘日 | - | 不生成B1/B2 | 只作路径校对，不改变Te动作 |\n"
            "| Tb | 2026-07-08（周三） | 历史复盘日 | - | 不生成B1/B2 | 只作路径校对，不改变Te动作 |\n"
            "| Tc | 2026-07-09（周四） | 前一交易日空仓 | - | 无B1占用 | 等待Td报告确认 |\n"
            "| Td | 2026-07-10（周五） | 报告日：空仓 | 无 | Te不新增参与，B2取消 | 只观察，不新增参与 |\n"
            "| Te | 2026-07-13（周一） | 空仓等待B1资格 | 无 | 没有B1/B2；保持空仓 | 空仓等待下一份日报 |\n\n"
            + GOOD_MARKDOWN
        )

        def account_state(trade_date, **_kwargs):
            if trade_date == "2026-07-07":
                return {
                    "state": "inferred",
                    "target": {"name": "长电科技", "code": "600584"},
                    "source": "postgresql.daily_report_facts",
                }
            return {"state": "unknown", "target": {}}

        with patch.object(report_acceptance_audit, "_read_day_order_account_state", side_effect=account_state):
            result = audit_report_markdown(
                markdown,
                source_path=Path("/tmp/2026-07-10_A股日报_完整版_replay.md"),
                prefer_postgres_history=True,
            )

        self.assertIn("position_day_order_history_path_missing", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_rejects_inferred_history_path_rendered_as_confirmed_holding(self):
        markdown = (
            "## 账户日序表\n"
            "| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |\n"
            "|------|------|----------|----------|-------------|------|\n"
            "| Ta | 2026-07-07（周二） | 历史持仓：长电科技(600584) | 长电科技(600584) | 可能形成B1旧仓 | 只作路径校对，不改变Te动作 |\n"
            "| Tb | 2026-07-08（周三） | 历史复盘日 | - | 不生成B1/B2 | 只作路径校对，不改变Te动作 |\n"
            "| Tc | 2026-07-09（周四） | 前一交易日空仓 | - | 无B1占用 | 等待Td报告确认 |\n"
            "| Td | 2026-07-10（周五） | 报告日：空仓 | 无 | Te不新增参与，B2取消 | 只观察，不新增参与 |\n"
            "| Te | 2026-07-13（周一） | 空仓等待B1资格 | 无 | 没有B1/B2；保持空仓 | 空仓等待下一份日报 |\n\n"
            + GOOD_MARKDOWN
        )

        def account_state(trade_date, **_kwargs):
            if trade_date == "2026-07-07":
                return {
                    "state": "inferred",
                    "target": {"name": "长电科技", "code": "600584"},
                    "source": "postgresql.daily_report_facts",
                }
            return {"state": "unknown", "target": {}}

        with patch.object(report_acceptance_audit, "_read_day_order_account_state", side_effect=account_state):
            result = audit_report_markdown(
                markdown,
                source_path=Path("/tmp/2026-07-10_A股日报_完整版_replay.md"),
                prefer_postgres_history=True,
            )

        self.assertIn(
            "position_day_order_history_inferred_confirmation_missing",
            {finding["code"] for finding in result["findings"]},
        )
        self.assertFalse(result["passed"])

    def test_audit_flags_known_empty_history_day_rendered_as_stock(self):
        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            (root / "2026-07-07_持仓策略.md").write_text(
                "\n".join(
                    [
                        "| 轨道 | 标的 | 2026-07-07（周二） | 2026-07-08（周三） |",
                        "|------|------|------|------|",
                        "| Ta旧仓 | 持仓未输入 | 先确认旧仓 | 确认后再处理 |",
                        "| Tb明日目标 | 华天科技(002185) | 空仓 | Tb+0 明日目标 |",
                        "| Tc复核位 | 无 | 空仓 | 空仓 |",
                    ]
                ),
                encoding="utf-8",
            )
            path = root / "2026-07-09_A股日报_完整版.md"
            markdown = (
                "## 账户日序表\n"
                "| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |\n"
                "|------|------|----------|----------|-------------|------|\n"
                "| Ta | 2026-07-06（周一） | 最远复盘日 | - | 不生成B1/B2 | 只作路径校对，不改变Te动作 |\n"
                "| Tb | 2026-07-07（周二） | 历史复盘日：华天科技(002185) | 华天科技(002185) | 历史路径校对 | 只作路径校对，不改变Te动作 |\n"
                "| Tc | 2026-07-08（周三） | 上一交易日路径：华天科技(002185) | 华天科技(002185) | 可能形成B1旧仓 | 进入Td复核，不临场补B2 |\n"
                "| Td | 2026-07-09（周四） | 报告日：空仓 | 无 | 只定Te预案，不下单；B2不存在直到Te确认 | 写清执行资格和取消条件 |\n"
                "| Te | 2026-07-10（周五） | 新目标单独看B1，不用旧仓亏损补仓 | 长电科技(600584) | B1参与权；B2确认权 | B1未变强则取消B2；只检查B1 |\n\n"
                + GOOD_MARKDOWN
            )

            result = audit_report_markdown(markdown, source_path=path)

        self.assertIn("position_day_order_history_empty_conflict", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_flags_unknown_history_day_rendered_as_stock(self):
        markdown = (
            "## 账户日序表\n"
            "| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |\n"
            "|------|------|----------|----------|-------------|------|\n"
            "| Ta | 2026-07-07（周二） | 最远复盘日：持仓未输入 | - | B1事实待确认 | 只作路径校对，不改变Te动作 |\n"
            "| Tb | 2026-07-08（周三） | 历史复盘日：持仓未输入 | - | B1事实待确认 | 只作路径校对，不改变Te动作 |\n"
            "| Tc | 2026-07-09（周四） | 上一交易日路径：长电科技(600584) | 长电科技(600584) | 可能形成B1旧仓 | 进入Td复核，不临场补B2 |\n"
            "| Td | 2026-07-10（周五） | 报告日：空仓 | 无 | 只定Te预案，不下单；B2不存在直到Te确认 | 写清执行资格和取消条件 |\n"
            "| Te | 2026-07-13（周一） | 新目标单独看B1，不用旧仓亏损补仓 | 富瀚微(300613) | B1参与权；B2确认权 | B1未变强则取消B2；只检查B1 |\n\n"
            + GOOD_MARKDOWN
        )

        with TemporaryDirectory() as tempdir, patch.object(
            report_acceptance_audit,
            "_read_day_order_account_state",
            return_value={"state": "unknown", "target": {}},
        ):
            result = audit_report_markdown(
                markdown,
                source_path=Path(tempdir) / "2026-07-10_A股日报_完整版_replay.md",
                prefer_postgres_history=True,
            )

        self.assertIn(
            "position_day_order_history_unknown_conflict",
            {finding["code"] for finding in result["findings"]},
        )
        self.assertFalse(result["passed"])

    def test_audit_flags_unknown_history_day_rendered_as_stock_name_without_code(self):
        markdown = (
            "## 账户日序表\n"
            "| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |\n"
            "|------|------|----------|----------|-------------|------|\n"
            "| Ta | 2026-07-07（周二） | 最远复盘日：持仓未输入 | - | B1事实待确认 | 只作路径校对，不改变Te动作 |\n"
            "| Tb | 2026-07-08（周三） | 历史复盘日：持仓未输入 | - | B1事实待确认 | 只作路径校对，不改变Te动作 |\n"
            "| Tc | 2026-07-09（周四） | 上一交易日路径：长电科技 | - | 可能形成B1旧仓 | 进入Td复核 |\n"
            "| Td | 2026-07-10（周五） | 报告日：空仓 | 无 | Te不新增参与 | 只观察 |\n"
            "| Te | 2026-07-13（周一） | 空仓等待 | 无 | 没有B1/B2 | 0%不参与 |\n\n"
            + GOOD_MARKDOWN
        )

        with TemporaryDirectory() as tempdir, patch.object(
            report_acceptance_audit,
            "_read_day_order_account_state",
            return_value={"state": "unknown", "target": {}},
        ):
            result = audit_report_markdown(
                markdown,
                source_path=Path(tempdir) / "2026-07-10_A股日报_完整版_replay.md",
                prefer_postgres_history=True,
            )

        self.assertIn(
            "position_day_order_history_unknown_conflict",
            {finding["code"] for finding in result["findings"]},
        )
        self.assertFalse(result["passed"])

    def test_audit_flags_bear_unknown_history_rendered_as_empty(self):
        markdown = (
            "## 账户日序表\n"
            "| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |\n"
            "|------|------|----------|----------|-------------|------|\n"
            "| Ta | 2026-07-07（周二） | 最远复盘日：持仓未输入 | - | B1事实待确认 | 只作路径校对 |\n"
            "| Tb | 2026-07-08（周三） | 历史复盘日：空仓 | - | 不生成B1/B2 | 只作路径校对 |\n"
            "| Tc | 2026-07-09（周四） | 前一交易日持仓未输入 | - | B1事实待确认 | 先确认账户事实 |\n"
            "| Td | 2026-07-10（周五） | 报告日：空仓 | 无 | Te不新增参与 | 只观察 |\n"
            "| Te | 2026-07-13（周一） | 空仓等待 | 无 | 没有B1/B2 | 0%不参与 |\n\n"
            + GOOD_MARKDOWN
        )
        companion_html = (
            '<div class="position-timeline-shell">'
            '<tr class="timeline-row timeline-row-ta"><span class="timeline-asset-empty">无</span></tr>'
            '<tr class="timeline-row timeline-row-tb"><span class="timeline-asset-empty">空仓</span></tr>'
            '<tr class="timeline-row timeline-row-tc"><span class="timeline-asset-empty">无</span></tr>'
            '<tr class="timeline-row timeline-row-td"><span class="timeline-asset-empty">空仓</span></tr>'
            '<tr class="timeline-row timeline-row-te"><span class="timeline-asset-empty">无</span></tr>'
            "</div>"
        )

        with TemporaryDirectory() as tempdir, patch.object(
            report_acceptance_audit,
            "_read_day_order_account_state",
            return_value={"state": "unknown", "target": {}},
        ):
            result = audit_report_markdown(
                markdown,
                source_path=Path(tempdir) / "2026-07-10_A股日报_完整版_replay.md",
                position_companion_html=companion_html,
                prefer_postgres_history=True,
            )

        self.assertIn(
            "position_day_order_html_unknown_rendered_as_empty",
            {finding["code"] for finding in result["findings"]},
        )
        self.assertFalse(result["passed"])

    def test_audit_accepts_unknown_history_day_without_stock_identity(self):
        markdown = (
            "## 账户日序表\n"
            "| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |\n"
            "|------|------|----------|----------|-------------|------|\n"
            "| Ta | 2026-07-07（周二） | 最远复盘日：持仓未输入 | - | B1事实待确认 | 只作路径校对，不改变Te动作 |\n"
            "| Tb | 2026-07-08（周三） | 历史复盘日：持仓未输入 | - | B1事实待确认 | 只作路径校对，不改变Te动作 |\n"
            "| Tc | 2026-07-09（周四） | 前一交易日持仓未输入 | - | B1事实待确认 | 先确认账户事实，不从当前计划反推历史持仓 |\n"
            "| Td | 2026-07-10（周五） | 报告日：空仓 | 无 | 只定Te预案，不下单；B2不存在直到Te确认 | 写清执行资格和取消条件 |\n"
            "| Te | 2026-07-13（周一） | 新目标单独看B1，不用旧仓亏损补仓 | 富瀚微(300613) | B1参与权；B2确认权 | B1未变强则取消B2；只检查B1 |\n\n"
            + GOOD_MARKDOWN
        )

        with TemporaryDirectory() as tempdir, patch.object(
            report_acceptance_audit,
            "_read_day_order_account_state",
            return_value={"state": "unknown", "target": {}},
        ):
            result = audit_report_markdown(
                markdown,
                source_path=Path(tempdir) / "2026-07-10_A股日报_完整版_replay.md",
                prefer_postgres_history=True,
            )

        self.assertNotIn(
            "position_day_order_history_unknown_conflict",
            {finding["code"] for finding in result["findings"]},
        )
        self.assertTrue(result["passed"], result["findings"])

    def test_audit_requires_source_path_for_day_order_history_check(self):
        markdown = (
            "## 账户日序表\n"
            "| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |\n"
            "|------|------|----------|----------|-------------|------|\n"
            "| Ta | 2026-07-06（周一） | 最远复盘日 | - | 不生成B1/B2 | 只作路径校对，不改变Te动作 |\n"
            "| Tb | 2026-07-07（周二） | 历史复盘日：华天科技(002185) | 华天科技(002185) | 历史路径校对 | 只作路径校对，不改变Te动作 |\n"
            "| Tc | 2026-07-08（周三） | 上一交易日路径：华天科技(002185) | 华天科技(002185) | 可能形成B1旧仓 | 进入Td复核，不临场补B2 |\n"
            "| Td | 2026-07-09（周四） | 报告日：空仓 | 无 | 只定Te预案，不下单；B2不存在直到Te确认 | 写清执行资格和取消条件 |\n"
            "| Te | 2026-07-10（周五） | 新目标单独看B1，不用旧仓亏损补仓 | 长电科技(600584) | B1参与权；B2确认权 | B1未变强则取消B2；只检查B1 |\n\n"
            + GOOD_MARKDOWN
        )

        result = audit_report_markdown(markdown)

        self.assertIn("position_day_order_history_source_path_missing", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_flags_postgres_current_position_missing_from_td(self):
        markdown = (
            "## 账户日序表\n"
            "| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |\n"
            "|------|------|----------|----------|-------------|------|\n"
            "| Ta | 2026-07-07（周二） | 最远复盘日：空仓 | - | 不生成B1/B2 | 只作路径校对，不改变Te动作 |\n"
            "| Tb | 2026-07-08（周三） | 历史复盘日：空仓 | - | 不生成B1/B2 | 只作路径校对，不改变Te动作 |\n"
            "| Tc | 2026-07-09（周四） | 前一交易日空仓 | - | 无B1占用 | 等待Td报告确认 |\n"
            "| Td | 2026-07-10（周五） | 报告日：旧仓进入复核 | 无 | Te不新增参与，B2取消 | 只观察，不新增参与 |\n"
            "| Te | 2026-07-13（周一） | 只处理旧仓风险 | 无 | 没有B2；只处理旧仓风险 | 旧仓未修复则继续降风险 |\n\n"
            "| 旧仓处理 | 持有长电科技(600584)，100%仓位 |\n"
            + GOOD_MARKDOWN
        )

        result = audit_report_markdown(
            markdown,
            expected_position_summary={
                "has_position": True,
                "name": "长电科技",
                "code": "600584",
                "summary": "持有长电科技(600584)，100%仓位",
            },
        )

        self.assertIn(
            "position_day_order_current_position_missing",
            {finding["code"] for finding in result["findings"]},
        )
        self.assertFalse(result["passed"])

    def test_audit_accepts_postgres_current_position_in_td(self):
        markdown = (
            "## 账户日序表\n"
            "| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |\n"
            "|------|------|----------|----------|-------------|------|\n"
            "| Ta | 2026-07-07（周二） | 最远复盘日：空仓 | - | 不生成B1/B2 | 只作路径校对，不改变Te动作 |\n"
            "| Tb | 2026-07-08（周三） | 历史复盘日：空仓 | - | 不生成B1/B2 | 只作路径校对，不改变Te动作 |\n"
            "| Tc | 2026-07-09（周四） | 前一交易日空仓 | - | 无B1占用 | 等待Td报告确认 |\n"
            "| Td | 2026-07-10（周五） | 报告日：旧仓进入复核：长电科技(600584) | 长电科技(600584) | Te不新增参与，B2取消 | 只观察，不新增参与 |\n"
            "| Te | 2026-07-13（周一） | 只处理旧仓风险 | 长电科技(600584) | 没有B2；只处理旧仓风险 | 旧仓未修复则继续降风险 |\n\n"
            "| 旧仓处理 | 持有长电科技(600584)，100%仓位 |\n"
            + GOOD_MARKDOWN
        )

        with TemporaryDirectory() as tempdir:
            result = audit_report_markdown(
                markdown,
                source_path=Path(tempdir) / "2026-07-10_A股日报_完整版_replay.md",
                expected_position_summary={
                    "has_position": True,
                    "name": "长电科技",
                    "code": "600584",
                },
            )

        self.assertNotIn(
            "position_day_order_current_position_missing",
            {finding["code"] for finding in result["findings"]},
        )
        self.assertTrue(result["passed"], result["findings"])

    def test_audit_rejects_inferred_plan_rendered_as_confirmed_holding(self):
        markdown = (
            "## 账户日序表\n"
            "| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |\n"
            "|------|------|----------|----------|-------------|------|\n"
            "| Ta | 2026-07-07（周二） | 最远复盘日：空仓 | - | 不生成B1/B2 | 只作路径校对，不改变Te动作 |\n"
            "| Tb | 2026-07-08（周三） | 历史复盘日：空仓 | - | 不生成B1/B2 | 只作路径校对，不改变Te动作 |\n"
            "| Tc | 2026-07-09（周四） | 前一交易日空仓 | - | 无B1占用 | 等待Td报告确认 |\n"
            "| Td | 2026-07-10（周五） | 报告日：旧仓进入复核：长电科技(600584) | 长电科技(600584) | Te不新增参与，B2取消 | 只观察，不新增参与 |\n"
            "| Te | 2026-07-13（周一） | 只处理旧仓风险 | 长电科技(600584) | 已有1x视为B1 | 旧仓未修复则继续降风险 |\n\n"
            "| 旧仓处理 | 持有长电科技(600584)，100%仓位 |\n"
            + GOOD_MARKDOWN
        )

        result = audit_report_markdown(
            markdown,
            expected_position_summary={
                "has_position": True,
                "name": "长电科技",
                "code": "600584",
                "position_source": "previous_report_target_default_1x",
                "inferred_from_previous_report": True,
            },
        )

        codes = {finding["code"] for finding in result["findings"]}
        self.assertIn("position_day_order_inferred_confirmation_missing", codes)
        self.assertIn("position_inferred_rendered_as_confirmed_holding", codes)
        self.assertFalse(result["passed"])

    def test_audit_accepts_inferred_plan_with_confirmation_language(self):
        markdown = (
            "## 账户日序表\n"
            "| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |\n"
            "|------|------|----------|----------|-------------|------|\n"
            "| Ta | 2026-07-07（周二） | 最远复盘日：空仓 | - | 不生成B1/B2 | 只作路径校对，不改变Te动作 |\n"
            "| Tb | 2026-07-08（周三） | 历史复盘日：空仓 | - | 不生成B1/B2 | 只作路径校对，不改变Te动作 |\n"
            "| Tc | 2026-07-09（周四） | 前一交易日空仓 | - | 无B1占用 | 等待Td报告确认 |\n"
            "| Td | 2026-07-10（周五） | 报告日：前日报计划推定，待成交确认：长电科技(600584) | 长电科技(600584) | Te不新增参与，B2取消 | 只观察，不新增参与 |\n"
            "| Te | 2026-07-13（周一） | 前日报计划对象待成交确认（只核实记录）：长电科技(600584) | 无 | 确认已成交才视为B1；未确认不新增B2 | 0%不参与；只核实成交记录 |\n\n"
            "| 成交确认 | 前日报计划推定，待成交确认：长电科技(600584)；未确认成交前不视为B1，不新增B2 |\n"
            + self.zero_position_report_with_decision_attribution()
        )

        with TemporaryDirectory() as tempdir:
            result = audit_report_markdown(
                markdown,
                source_path=Path(tempdir) / "2026-07-10_A股日报_完整版_replay.md",
                expected_position_summary={
                    "has_position": False,
                    "has_pending_position": True,
                    "name": "长电科技",
                    "code": "600584",
                    "position_source": "previous_report_target_default_1x",
                    "inferred_from_previous_report": True,
                },
            )

        codes = {finding["code"] for finding in result["findings"]}
        self.assertNotIn("position_day_order_inferred_confirmation_missing", codes)
        self.assertNotIn("position_inferred_rendered_as_confirmed_holding", codes)
        self.assertTrue(result["passed"], result["findings"])

    def test_audit_rejects_inferred_plan_in_compact_current_action_lines(self):
        timeline = (
            "## 账户日序表\n"
            "| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |\n"
            "|------|------|----------|----------|-------------|------|\n"
            "| Td | 2026-07-10（周五） | 报告日：前日报计划推定，待成交确认：长电科技(600584) | 长电科技(600584) | Te不新增参与，B2取消 | 只观察，不新增参与 |\n"
            "| Te | 2026-07-13（周一） | 前日报计划对象待成交确认（只核实记录）：长电科技(600584) | 无 | 确认已成交才视为B1；未确认不新增B2 | 0%不参与；只核实成交记录 |\n\n"
            "| 成交确认 | 前日报计划推定，待成交确认：长电科技(600584)；未确认成交前不视为B1，不新增B2 |\n"
        )
        stale_lines = (
            "- **明天能不能开仓**: 🟠 只处理旧仓；环境已转撤退",
            "- 明日动作：空仓等待或只处理旧仓",
        )

        for stale_line in stale_lines:
            with self.subTest(stale_line=stale_line), TemporaryDirectory() as tempdir:
                result = audit_report_markdown(
                    timeline + stale_line + "\n" + self.zero_position_report_with_decision_attribution(),
                    source_path=Path(tempdir) / "2026-07-10_A股日报_完整版_replay.md",
                    expected_position_summary={
                        "has_position": False,
                        "has_pending_position": True,
                        "name": "长电科技",
                        "code": "600584",
                        "position_source": "previous_report_target_default_1x",
                        "inferred_from_previous_report": True,
                    },
                )

            self.assertIn(
                "position_inferred_rendered_as_confirmed_holding",
                {finding["code"] for finding in result["findings"]},
            )
            self.assertFalse(result["passed"])

    def test_audit_rejects_inferred_te_without_zero_position_verification_action(self):
        markdown = (
            "## 账户日序表\n"
            "| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |\n"
            "|------|------|----------|----------|-------------|------|\n"
            "| Ta | 2026-07-07（周二） | 最远复盘日：空仓 | - | 不生成B1/B2 | 只作路径校对，不改变Te动作 |\n"
            "| Tb | 2026-07-08（周三） | 历史复盘日：空仓 | - | 不生成B1/B2 | 只作路径校对，不改变Te动作 |\n"
            "| Tc | 2026-07-09（周四） | 前一交易日空仓 | - | 无B1占用 | 等待Td报告确认 |\n"
            "| Td | 2026-07-10（周五） | 报告日：前日报计划推定，待成交确认：长电科技(600584) | 长电科技(600584) | Te不新增参与，B2取消 | 只观察，不新增参与 |\n"
            "| Te | 2026-07-13（周一） | 前日报计划对象待成交确认（只核实记录）：长电科技(600584) | 无 | 确认已成交才视为B1；未确认不新增B2 | 等待 |\n\n"
            "| 成交确认 | 前日报计划推定，待成交确认：长电科技(600584)；未确认成交前不视为B1，不新增B2 |\n"
            + self.zero_position_report_with_decision_attribution()
        )

        result = audit_report_markdown(
            markdown,
            expected_position_summary={
                "has_position": False,
                "has_pending_position": True,
                "name": "长电科技",
                "code": "600584",
                "position_source": "previous_report_target_default_1x",
            },
        )

        self.assertIn(
            "position_day_order_inferred_confirmation_missing",
            {finding["code"] for finding in result["findings"]},
        )
        self.assertFalse(result["passed"])

    def test_audit_rejects_inferred_bear_participation_badges(self):
        markdown = (
            "## 账户日序表\n"
            "| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |\n"
            "|------|------|----------|----------|-------------|------|\n"
            "| Td | 2026-07-10（周五） | 报告日：前日报计划推定，待成交确认：长电科技(600584) | 长电科技(600584) | Te不新增参与，B2取消 | 只观察，不新增参与 |\n"
            "| Te | 2026-07-13（周一） | 前日报计划对象待成交确认（只核实记录）：长电科技(600584) | 无 | 确认已成交才视为B1；未确认不新增B2 | 0%不参与；只核实成交记录 |\n\n"
            "| 成交确认 | 前日报计划推定，待成交确认：长电科技(600584)；未确认成交前不视为B1，不新增B2 |\n"
            + self.zero_position_report_with_decision_attribution()
        )
        companion_html = (
            '<div class="position-timeline-shell">'
            '<span class="timeline-date-intent is-buy">参与权</span>'
            '<tr class="timeline-row timeline-row-td"><span class="timeline-asset-name">长电科技</span>'
            '<span class="timeline-asset-code">600584</span><span>前日报计划推定 待成交确认</span></tr>'
            '<tr class="timeline-row timeline-row-te"><span class="timeline-asset-empty">无</span>'
            '<span>待成交确认 确认已成交才视为B1 未确认不新增B2 0%不参与 只核实成交记录</span>'
            '<span class="timeline-action-badge is-participate">参与权</span></tr>'
            "</div>"
        )

        result = audit_report_markdown(
            markdown,
            position_companion_html=companion_html,
            expected_position_summary={
                "has_position": False,
                "has_pending_position": True,
                "name": "长电科技",
                "code": "600584",
                "position_source": "previous_report_target_default_1x",
            },
        )

        self.assertIn(
            "position_day_order_html_inferred_confirmation_missing",
            {finding["code"] for finding in result["findings"]},
        )
        self.assertFalse(result["passed"])

    def test_audit_rejects_inferred_plan_used_as_te_target_when_final_object_is_empty(self):
        markdown = (
            "## 账户日序表\n"
            "| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |\n"
            "|------|------|----------|----------|-------------|------|\n"
            "| Td | 2026-07-10（周五） | 报告日：前日报计划推定，待成交确认：长电科技(600584) | 长电科技(600584) | Te不新增参与，B2取消 | 只观察，不新增参与 |\n"
            "| Te | 2026-07-13（周一） | 前日报计划对象待成交确认：长电科技(600584) | 长电科技(600584) | 确认已成交才视为B1；未确认不新增B2 | 先确认成交事实；未成交不补B2 |\n\n"
            "| 成交确认 | 前日报计划推定，待成交确认：长电科技(600584)；未确认成交前不视为B1，不新增B2 |\n"
            + self.zero_position_report_with_decision_attribution()
        )

        result = audit_report_markdown(
            markdown,
            expected_position_summary={
                "has_position": False,
                "has_pending_position": True,
                "name": "长电科技",
                "code": "600584",
                "position_source": "previous_report_target_default_1x",
            },
        )

        self.assertIn(
            "position_day_order_inferred_target_conflict",
            {finding["code"] for finding in result["findings"]},
        )
        self.assertFalse(result["passed"])

    def test_audit_rejects_inferred_plan_target_without_external_position_summary(self):
        markdown = (
            "## 账户日序表\n"
            "| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |\n"
            "|------|------|----------|----------|-------------|------|\n"
            "| Td | 2026-07-10（周五） | 报告日：前日报计划推定，待成交确认：长电科技(600584) | 长电科技(600584) | Te不新增参与，B2取消 | 只观察，不新增参与 |\n"
            "| Te | 2026-07-13（周一） | 前日报计划对象待成交确认：长电科技(600584) | 长电科技(600584) | 确认已成交才视为B1；未确认不新增B2 | 先确认成交事实；未成交不补B2 |\n\n"
            "| 成交确认 | 前日报计划推定，待成交确认：长电科技(600584)；未确认成交前不视为B1，不新增B2 |\n"
            + self.zero_position_report_with_decision_attribution()
        )

        result = audit_report_markdown(markdown)

        self.assertIn(
            "position_day_order_inferred_target_conflict",
            {finding["code"] for finding in result["findings"]},
        )
        self.assertFalse(result["passed"])

    def test_audit_accepts_distinct_final_target_in_te_while_td_keeps_pending_plan(self):
        markdown = (
            "## 账户日序表\n"
            "| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |\n"
            "|------|------|----------|----------|-------------|------|\n"
            "| Ta | 2026-07-07（周二） | 最远复盘日：空仓 | - | 不生成B1/B2 | 只作路径校对，不改变Te动作 |\n"
            "| Tb | 2026-07-08（周三） | 历史复盘日：空仓 | - | 不生成B1/B2 | 只作路径校对，不改变Te动作 |\n"
            "| Tc | 2026-07-09（周四） | 前一交易日空仓 | - | 无B1占用 | 等待Td报告确认 |\n"
            "| Td | 2026-07-10（周五） | 报告日：前日报计划推定，待成交确认：长电科技(600584) | 长电科技(600584) | 只定Te预案，不下单；B2不存在直到Te确认 | 写清执行资格和取消条件 |\n"
            "| Te | 2026-07-13（周一） | 新目标单独看B1，不用旧仓亏损补仓 | 富瀚微(300613) | B1参与权；B2确认权 | B1未变强则取消B2；只检查B1 |\n\n"
            "| 成交确认 | 前日报计划推定，待成交确认：长电科技(600584)；未确认成交前不视为B1，不新增B2 |\n"
            + GOOD_MARKDOWN
        )

        with TemporaryDirectory() as tempdir:
            result = audit_report_markdown(
                markdown,
                source_path=Path(tempdir) / "2026-07-10_A股日报_完整版_replay.md",
                expected_position_summary={
                    "has_position": False,
                    "has_pending_position": True,
                    "name": "长电科技",
                    "code": "600584",
                    "position_source": "previous_report_target_default_1x",
                },
            )

        codes = {finding["code"] for finding in result["findings"]}
        self.assertNotIn("position_day_order_inferred_target_conflict", codes)
        self.assertNotIn("position_day_order_inferred_confirmation_missing", codes)
        self.assertTrue(result["passed"], result["findings"])

    def test_audit_accepts_bear_distinct_final_target_while_td_keeps_pending_plan(self):
        markdown = (
            "## 账户日序表\n"
            "| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |\n"
            "|------|------|----------|----------|-------------|------|\n"
            "| Ta | 2026-07-07（周二） | 最远复盘日：空仓 | - | 不生成B1/B2 | 只作路径校对，不改变Te动作 |\n"
            "| Tb | 2026-07-08（周三） | 历史复盘日：空仓 | - | 不生成B1/B2 | 只作路径校对，不改变Te动作 |\n"
            "| Tc | 2026-07-09（周四） | 前一交易日空仓 | - | 无B1占用 | 等待Td报告确认 |\n"
            "| Td | 2026-07-10（周五） | 报告日：前日报计划推定，待成交确认：长电科技(600584) | 长电科技(600584) | 只定Te预案，不下单；B2不存在直到Te确认 | 写清执行资格和取消条件 |\n"
            "| Te | 2026-07-13（周一） | 新目标单独看B1，不用旧仓亏损补仓 | 富瀚微(300613) | B1参与权；B2确认权 | B1未变强则取消B2；只检查B1 |\n\n"
            "| 成交确认 | 前日报计划推定，待成交确认：长电科技(600584)；未确认成交前不视为B1，不新增B2 |\n"
            + GOOD_MARKDOWN
        )
        companion_html = render_markdown_report_html(markdown, trade_date="2026-07-10")

        with TemporaryDirectory() as tempdir:
            result = audit_report_markdown(
                markdown,
                position_companion_html=companion_html,
                source_path=Path(tempdir) / "2026-07-10_A股日报_完整版_replay.md",
                expected_position_summary={
                    "has_position": False,
                    "has_pending_position": True,
                    "name": "长电科技",
                    "code": "600584",
                    "position_source": "previous_report_target_default_1x",
                },
            )

        self.assertTrue(result["passed"], result["findings"])

    def test_audit_accepts_bear_same_stock_positive_final_after_pending_plan(self):
        positive_report = GOOD_MARKDOWN.replace("富瀚微(300613)", "长电科技(600584)")
        markdown = (
            "## 账户日序表\n"
            "| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |\n"
            "|------|------|----------|----------|-------------|------|\n"
            "| Ta | 2026-07-07（周二） | 最远复盘日：空仓 | - | 不生成B1/B2 | 只作路径校对，不改变Te动作 |\n"
            "| Tb | 2026-07-08（周三） | 历史复盘日：空仓 | - | 不生成B1/B2 | 只作路径校对，不改变Te动作 |\n"
            "| Tc | 2026-07-09（周四） | 前一交易日空仓 | - | 无B1占用 | 等待Td报告确认 |\n"
            "| Td | 2026-07-10（周五） | 报告日：前日报计划推定，待成交确认：长电科技(600584) | 长电科技(600584) | 只定Te预案，不下单；B2不存在直到Te确认 | 写清执行资格和取消条件 |\n"
            "| Te | 2026-07-13（周一） | 前日报计划对象待成交确认：长电科技(600584) | 长电科技(600584) | 确认已成交才视为B1；未确认不新增B2 | 先确认成交事实；未成交不补B2 |\n\n"
            "| 成交确认 | 前日报计划推定，待成交确认：长电科技(600584)；未确认成交前不视为B1，不新增B2 |\n"
            + positive_report
        )
        companion_html = render_markdown_report_html(markdown, trade_date="2026-07-10")

        with TemporaryDirectory() as tempdir:
            result = audit_report_markdown(
                markdown,
                position_companion_html=companion_html,
                source_path=Path(tempdir) / "2026-07-10_A股日报_完整版_replay.md",
                expected_position_summary={
                    "has_position": False,
                    "has_pending_position": True,
                    "name": "长电科技",
                    "code": "600584",
                    "position_source": "previous_report_target_default_1x",
                },
            )

        self.assertTrue(result["passed"], result["findings"])

    def test_audit_rejects_bear_inferred_plan_used_as_te_target_when_final_object_is_empty(self):
        markdown = (
            "## 账户日序表\n"
            "| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |\n"
            "|------|------|----------|----------|-------------|------|\n"
            "| Td | 2026-07-10（周五） | 报告日：前日报计划推定，待成交确认：长电科技(600584) | 长电科技(600584) | Te不新增参与，B2取消 | 只观察，不新增参与 |\n"
            "| Te | 2026-07-13（周一） | 前日报计划对象待成交确认（只核实记录）：长电科技(600584) | 无 | 确认已成交才视为B1；未确认不新增B2 | 0%不参与；只核实成交记录 |\n\n"
            "| 成交确认 | 前日报计划推定，待成交确认：长电科技(600584)；未确认成交前不视为B1，不新增B2 |\n"
            + self.zero_position_report_with_decision_attribution()
        )
        companion_html = (
            '<div class="position-timeline-shell">'
            '<tr class="timeline-row timeline-row-td"><span class="timeline-asset-name">长电科技</span>'
            '<span class="timeline-asset-code">600584</span><span>前日报计划推定 待成交确认</span></tr>'
            '<tr class="timeline-row timeline-row-te"><span class="timeline-asset-name">长电科技</span>'
            '<span class="timeline-asset-code">600584</span><span>待成交确认 确认已成交才视为B1 未确认不新增B2</span></tr>'
            "</div>"
        )

        result = audit_report_markdown(
            markdown,
            companion_html=companion_html,
            expected_position_summary={
                "has_position": False,
                "has_pending_position": True,
                "name": "长电科技",
                "code": "600584",
                "position_source": "previous_report_target_default_1x",
            },
        )

        self.assertIn(
            "position_day_order_html_inferred_target_conflict",
            {finding["code"] for finding in result["findings"]},
        )
        self.assertFalse(result["passed"])

        result_without_external_summary = audit_report_markdown(
            markdown,
            companion_html=companion_html,
        )
        self.assertIn(
            "position_day_order_html_inferred_target_conflict",
            {finding["code"] for finding in result_without_external_summary["findings"]},
        )
        self.assertFalse(result_without_external_summary["passed"])

    def test_audit_rejects_bear_te_target_different_from_markdown_without_pending_plan(self):
        markdown = (
            "## 账户日序表\n"
            "| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |\n"
            "|------|------|----------|----------|-------------|------|\n"
            "| Td | 2026-07-10（周五） | 报告日：空仓 | 无 | 只定Te预案，不下单；B2不存在直到Te确认 | 写清执行资格和取消条件 |\n"
            "| Te | 2026-07-13（周一） | 新目标单独看B1 | 富瀚微(300613) | B1参与权；B2确认权 | B1未变强则取消B2；只检查B1 |\n\n"
            + GOOD_MARKDOWN
        )
        companion_html = (
            '<div class="position-timeline-shell">'
            '<tr class="timeline-row timeline-row-td"><span class="timeline-asset-empty">无</span></tr>'
            '<tr class="timeline-row timeline-row-te"><span class="timeline-asset-name">长电科技</span>'
            '<span class="timeline-asset-code">600584</span></tr>'
            "</div>"
        )

        result = audit_report_markdown(markdown, position_companion_html=companion_html)

        self.assertIn(
            "position_day_order_html_target_conflict",
            {finding["code"] for finding in result["findings"]},
        )
        self.assertFalse(result["passed"])

    def test_audit_rejects_inferred_plan_confirmed_holding_wording_in_appendix(self):
        markdown = (
            "## 账户日序表\n"
            "| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |\n"
            "|------|------|----------|----------|-------------|------|\n"
            "| Ta | 2026-07-07（周二） | 最远复盘日：空仓 | - | 不生成B1/B2 | 只作路径校对，不改变Te动作 |\n"
            "| Tb | 2026-07-08（周三） | 历史复盘日：空仓 | - | 不生成B1/B2 | 只作路径校对，不改变Te动作 |\n"
            "| Tc | 2026-07-09（周四） | 前一交易日空仓 | - | 无B1占用 | 等待Td报告确认 |\n"
            "| Td | 2026-07-10（周五） | 报告日：前日报计划推定，待成交确认：长电科技(600584) | 长电科技(600584) | Te不新增参与，B2取消 | 只观察，不新增参与 |\n"
            "| Te | 2026-07-13（周一） | 前日报计划对象待成交确认：长电科技(600584) | 长电科技(600584) | 确认已成交才视为B1；未确认不新增B2 | 先确认成交事实；未成交不补B2 |\n\n"
            "| 成交确认 | 前日报计划推定，待成交确认：长电科技(600584)；未确认成交前不视为B1，不新增B2 |\n"
            + GOOD_MARKDOWN
            + "\n## 八、详细附录\n"
            "| 账户后台任务负担 | 上一份日报明日标的默认1x旧仓需复核 |\n"
            "| 持仓优先动作 | 旧仓按旧路径处理 |\n"
        )

        result = audit_report_markdown(
            markdown,
            expected_position_summary={
                "has_position": False,
                "has_pending_position": True,
                "name": "长电科技",
                "code": "600584",
                "position_source": "previous_report_target_default_1x",
            },
        )

        self.assertIn(
            "position_inferred_rendered_as_confirmed_holding",
            {finding["code"] for finding in result["findings"]},
        )
        self.assertFalse(result["passed"])

    def test_audit_accepts_pending_confirmation_wording_in_appendix(self):
        markdown = (
            "## 账户日序表\n"
            "| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |\n"
            "|------|------|----------|----------|-------------|------|\n"
            "| Td | 2026-07-10（周五） | 报告日：前日报计划推定，待成交确认：长电科技(600584) | 长电科技(600584) | Te不新增参与，B2取消 | 只观察，不新增参与 |\n"
            "| Te | 2026-07-13（周一） | 前日报计划对象待成交确认（只核实记录）：长电科技(600584) | 无 | 确认已成交才视为B1；未确认不新增B2 | 0%不参与；只核实成交记录 |\n\n"
            "| 成交确认 | 前日报计划推定，待成交确认：长电科技(600584)；未确认成交前不视为B1，不新增B2 |\n"
            + self.zero_position_report_with_decision_attribution()
            + "\n## 八、详细附录\n"
            "| 账户后台任务负担 | 前日报计划对象待成交确认 |\n"
            "| 持仓优先动作 | 未确认成交前不视为B1；新机会按自身资格判断 |\n"
        )

        with TemporaryDirectory() as tempdir:
            result = audit_report_markdown(
                markdown,
                source_path=Path(tempdir) / "2026-07-10_A股日报_完整版_replay.md",
                expected_position_summary={
                    "has_position": False,
                    "has_pending_position": True,
                    "name": "长电科技",
                    "code": "600584",
                    "position_source": "previous_report_target_default_1x",
                },
            )

        self.assertNotIn(
            "position_inferred_rendered_as_confirmed_holding",
            {finding["code"] for finding in result["findings"]},
        )
        self.assertTrue(result["passed"], result["findings"])

    def test_audit_rejects_stale_inferred_old_position_wording_on_other_surfaces(self):
        markdown = (
            "## 账户日序表\n"
            "| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |\n"
            "|------|------|----------|----------|-------------|------|\n"
            "| Td | 2026-07-10（周五） | 报告日：前日报计划推定，待成交确认：长电科技(600584) | 长电科技(600584) | Te不新增参与，B2取消 | 只观察，不新增参与 |\n"
            "| Te | 2026-07-13（周一） | 前日报计划对象待成交确认：长电科技(600584) | 长电科技(600584) | 确认已成交才视为B1；未确认不新增B2 | 先确认成交事实；未成交不补B2 |\n\n"
            "| 成交确认 | 前日报计划推定，待成交确认：长电科技(600584)；未确认成交前不视为B1，不新增B2 |\n"
            + GOOD_MARKDOWN
            + "\n## 八、详细附录\n"
            "|-- 层级=资金层 输入=明日无新增参与对象，默认1x旧仓按旧路径处理；不新增参与\n"
            "| 明天是否参与 | 🟠 只处理旧仓 | 环境已转撤退 | 当前动作 |\n"
            "**明日裁决**: 🟠 只处理旧仓\n"
        )

        result = audit_report_markdown(
            markdown,
            expected_position_summary={
                "has_position": False,
                "has_pending_position": True,
                "name": "长电科技",
                "code": "600584",
                "position_source": "previous_report_target_default_1x",
            },
        )

        self.assertIn(
            "position_inferred_rendered_as_confirmed_holding",
            {finding["code"] for finding in result["findings"]},
        )
        self.assertFalse(result["passed"])

    def test_audit_rejects_inferred_plan_that_mixes_pending_and_confirmed_position_language(self):
        markdown = (
            "## 账户日序表\n"
            "| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |\n"
            "|------|------|----------|----------|-------------|------|\n"
            "| Ta | 2026-07-07（周二） | 最远复盘日：空仓 | - | 不生成B1/B2 | 只作路径校对，不改变Te动作 |\n"
            "| Tb | 2026-07-08（周三） | 历史复盘日：空仓 | - | 不生成B1/B2 | 只作路径校对，不改变Te动作 |\n"
            "| Tc | 2026-07-09（周四） | 前一交易日空仓 | - | 无B1占用 | 等待Td报告确认 |\n"
            "| Td | 2026-07-10（周五） | 报告日：前日报计划推定，待成交确认：长电科技(600584) | 长电科技(600584) | Te不新增参与，B2取消 | 只观察，不新增参与 |\n"
            "| Te | 2026-07-13（周一） | 前日报计划对象待成交确认：长电科技(600584) | 长电科技(600584) | 确认已成交才视为B1；未确认不新增B2；已有1x视为B1 | 先确认成交事实；未成交不补B2 |\n\n"
            "| 明日仓位 | 同股T候选；已有1x视为B1 |\n"
            "| 成交确认 | 前日报计划推定，待成交确认：长电科技(600584)；未确认成交前不视为B1，不新增B2 |\n"
            + GOOD_MARKDOWN
        )

        result = audit_report_markdown(
            markdown,
            expected_position_summary={
                "has_position": False,
                "has_pending_position": True,
                "name": "长电科技",
                "code": "600584",
                "position_source": "previous_report_target_default_1x",
                "inferred_from_previous_report": True,
            },
        )

        self.assertIn(
            "position_day_order_inferred_confirmation_missing",
            {finding["code"] for finding in result["findings"]},
        )
        self.assertIn(
            "position_inferred_rendered_as_confirmed_holding",
            {finding["code"] for finding in result["findings"]},
        )
        self.assertFalse(result["passed"])

    def test_audit_rejects_bear_inferred_plan_without_confirmation_language(self):
        markdown = (
            "## 账户日序表\n"
            "| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |\n"
            "|------|------|----------|----------|-------------|------|\n"
            "| Ta | 2026-07-07（周二） | 最远复盘日：空仓 | - | 不生成B1/B2 | 只作路径校对，不改变Te动作 |\n"
            "| Tb | 2026-07-08（周三） | 历史复盘日：空仓 | - | 不生成B1/B2 | 只作路径校对，不改变Te动作 |\n"
            "| Tc | 2026-07-09（周四） | 前一交易日空仓 | - | 无B1占用 | 等待Td报告确认 |\n"
            "| Td | 2026-07-10（周五） | 报告日：前日报计划推定，待成交确认：长电科技(600584) | 长电科技(600584) | Te不新增参与，B2取消 | 只观察，不新增参与 |\n"
            "| Te | 2026-07-13（周一） | 前日报计划对象待成交确认：长电科技(600584) | 长电科技(600584) | 确认已成交才视为B1；未确认不新增B2 | 先确认成交事实；未成交不补B2 |\n\n"
            "| 成交确认 | 前日报计划推定，待成交确认：长电科技(600584)；未确认成交前不视为B1，不新增B2 |\n"
            + GOOD_MARKDOWN
        )
        companion_html = (
            '<div class="position-timeline-shell">'
            '<tr class="timeline-row timeline-row-td"><span class="timeline-asset-name">长电科技</span>'
            '<span class="timeline-asset-code">600584</span><span>旧仓进入复核</span></tr>'
            '<tr class="timeline-row timeline-row-te"><span class="timeline-asset-name">长电科技</span>'
            '<span class="timeline-asset-code">600584</span><span>只处理旧仓风险</span></tr>'
            '</div>'
        )

        result = audit_report_markdown(
            markdown,
            companion_html=companion_html,
            expected_position_summary={
                "has_position": True,
                "name": "长电科技",
                "code": "600584",
                "position_source": "previous_report_target_default_1x",
                "inferred_from_previous_report": True,
            },
        )

        self.assertIn(
            "position_day_order_html_inferred_confirmation_missing",
            {finding["code"] for finding in result["findings"]},
        )
        self.assertFalse(result["passed"])

    def test_audit_does_not_treat_te_old_position_as_new_entry_target(self):
        markdown = (
            "## 账户日序表\n"
            "| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |\n"
            "|------|------|----------|----------|-------------|------|\n"
            "| Ta | 2026-07-07（周二） | 最远复盘日：空仓 | - | 不生成B1/B2 | 只作路径校对，不改变Te动作 |\n"
            "| Tb | 2026-07-08（周三） | 历史复盘日：空仓 | - | 不生成B1/B2 | 只作路径校对，不改变Te动作 |\n"
            "| Tc | 2026-07-09（周四） | 前一交易日空仓 | - | 无B1占用 | 等待Td报告确认 |\n"
            "| Td | 2026-07-10（周五） | 报告日：旧仓进入复核：长电科技(600584) | 长电科技(600584) | Te不新增参与，B2取消 | 只观察，不新增参与 |\n"
            "| Te | 2026-07-13（周一） | 只处理旧仓风险 | 长电科技(600584) | 没有B2；只处理旧仓风险 | 旧仓未修复则继续降风险 |\n\n"
            "| 旧仓处理 | 持有长电科技(600584)，100%仓位 |\n"
            + self.zero_position_report_with_decision_attribution()
            + "\n## 选股流程最终推导\n| 最终结果 | N9 / final | 无；0%不参与；0% |\n"
        )

        result = audit_report_markdown(
            markdown,
            expected_position_summary={
                "has_position": True,
                "name": "长电科技",
                "code": "600584",
            },
        )

        self.assertNotIn(
            "position_timeline_final_conflict",
            {finding["code"] for finding in result["findings"]},
        )

    def test_audit_flags_bear_html_current_position_missing_from_td(self):
        markdown = (
            "## 账户日序表\n"
            "| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |\n"
            "|------|------|----------|----------|-------------|------|\n"
            "| Ta | 2026-07-07（周二） | 最远复盘日：空仓 | - | 不生成B1/B2 | 只作路径校对，不改变Te动作 |\n"
            "| Tb | 2026-07-08（周三） | 历史复盘日：空仓 | - | 不生成B1/B2 | 只作路径校对，不改变Te动作 |\n"
            "| Tc | 2026-07-09（周四） | 前一交易日空仓 | - | 无B1占用 | 等待Td报告确认 |\n"
            "| Td | 2026-07-10（周五） | 报告日：旧仓进入复核：长电科技(600584) | 长电科技(600584) | Te不新增参与，B2取消 | 只观察，不新增参与 |\n"
            "| Te | 2026-07-13（周一） | 只处理旧仓风险 | 长电科技(600584) | 没有B2；只处理旧仓风险 | 旧仓未修复则继续降风险 |\n\n"
            + GOOD_MARKDOWN
        )
        html = (
            '<div class="position-timeline-shell">'
            '<tr class="timeline-row timeline-row-td">'
            '<span class="timeline-asset-empty">无</span>'
            '</tr>'
            '</div>'
        )

        result = audit_report_markdown(
            markdown,
            companion_html=html,
            expected_position_summary={
                "has_position": True,
                "name": "长电科技",
                "code": "600584",
            },
        )

        self.assertIn(
            "position_day_order_html_current_position_missing",
            {finding["code"] for finding in result["findings"]},
        )
        self.assertFalse(result["passed"])

    def test_audit_flags_known_old_position_conflicting_with_unknown_holding(self):
        markdown = (
            "| 轨道 | 标的 | 2026-06-28（周日） | 2026-06-29（周一） | 2026-06-30（周二） | 2026-07-01（周三） |\n"
            "|------|------|------|------|------|------|\n"
            "| Ta旧仓 | 太极实业(600667) | 上一份日报目标，进入旧仓/旧路径复核 | Ta+1 继续处理旧仓或取消路径 | Ta+2 默认按昨晚预案尾盘卖出；失去持有资格才提前处理 | 空仓 |\n"
            "| Tb明日目标 | 深科技(000021) | 空仓 | 报告日确认明日目标 | Tb+0 条件买入，不是无条件买入 | Tb+1 只按昨晚预案执行或取消 |\n"
            "| Tc复核位 | 无 | 空仓 | 空仓 | 没有Tc+0，不提前占用 | 下一份日报再复核 |\n\n"
            + GOOD_MARKDOWN
            + "\n## 明日账户建议\n| 项目 | 结论 |\n|------|------|\n| 持仓确认 | 持仓未输入，执行前先确认旧仓情况 |\n"
        )
        html = (
            '<div class="position-timeline-shell">'
            '<tr class="timeline-row timeline-row-ta">'
            '<span class="timeline-asset-name">太极实业</span><span class="timeline-asset-code">600667</span>'
            '</tr>'
            '</div>'
        )

        result = audit_report_markdown(markdown, companion_html=html)

        self.assertIn("known_old_position_conflicts_with_unknown_holding", {finding["code"] for finding in result["findings"]})
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
            "硬" + "门" + "禁",
            "门" + "禁",
            "ga" + "te",
            "hard " + "ga" + "te",
            "状态" + "机",
            "状态" + "机" + "词" + "汇",
            "门" + "控",
            "闸" + "门",
            "开" + "闸",
            "放" + "行",
        ):
            with self.subTest(marker=marker):
                bad = GOOD_MARKDOWN.replace("50%条件执行", marker, 1)

                result = audit_report_markdown(bad)

                self.assertIn("legacy_surface_wording", {finding["code"] for finding in result["findings"]})
                self.assertFalse(result["passed"])

    def test_audit_flags_historical_timing_language_anywhere_in_report(self):
        bad = GOOD_MARKDOWN.replace("09:50-10:10窗口", "60" + "分钟确认", 1)

        result = audit_report_markdown(bad)

        self.assertIn("legacy_trading_time_wording", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_flags_legacy_surface_wording_in_appendix(self):
        bad = GOOD_MARKDOWN + "\n\n## 八、详细附录\n\n执行" + "权限必须统一改写。\n"

        result = audit_report_markdown(bad)

        self.assertIn("legacy_surface_wording", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_flags_residual_legacy_timing_fragments_from_generated_report(self):
        legacy_fragments = (
            "30分钟定止损",
            "30分钟结构失守",
            "30分钟结构止损线",
            "09:35-10:30",
            "10:30-14:30",
            "结构确认窗口",
            "盘中执行（10:30-14:30）",
        )
        for fragment in legacy_fragments:
            with self.subTest(fragment=fragment):
                bad = GOOD_MARKDOWN + f"\n{fragment}\n"

                result = audit_report_markdown(bad)

                self.assertIn("legacy_trading_time_wording", {finding["code"] for finding in result["findings"]})
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
            "| 2026-04-24 | 半导体 | 待累计 | 26414.92亿 | 待累计 | 待累计 | 大周期延续 | 数据不足 |",
            "| 2026-04-24 | 半导体 | missing_dependency | 26414.92亿 | 0.00% | 待累计 | 大周期延续 | 数据缺失 |",
        )

        result = audit_report_markdown(bad)

        self.assertIn("degraded_fake_zero_percent", {finding["code"] for finding in result["findings"]})

    def test_audit_flags_top50_table_not_reaching_report_target_date(self):
        rows = "\n".join(
            f"| 2026-05-{day:02d} | 19.00% | 震荡 | 待累计 | 5000.00亿 | 26000.00亿 |"
            for day in range(13, 20)
        )
        bad = GOOD_MARKDOWN.replace(
            "| 市场状态 | 收缩防守 |",
            "| 市场状态 | 收缩防守 |\n\n"
            "| 日期 | Top50占比 | 状态 | 较前日 | Top50成交额 | 两市成交额 |\n"
            "|------|-----------|------|--------|-------------|------------|\n"
            f"{rows}",
        ).replace("# 2026-04-24 a股市场分析", "# 2026-05-20 a股市场分析")

        result = audit_report_markdown(bad)

        codes = {finding["code"] for finding in result["findings"]}
        self.assertIn("top50_target_date_missing", codes)
        self.assertIn("top50_recent_window_incomplete", codes)
        self.assertFalse(result["passed"])

    def test_audit_flags_mainline_turnover_table_not_reaching_report_target_date(self):
        rows = "\n".join(
            f"| 2026-05-{day:02d} | 半导体 | 半导体 | 4000.00亿 | 30000.00亿 | 13.3% | 待累计 | 继续观察 |"
            for day in range(13, 20)
        )
        bad = GOOD_MARKDOWN.replace(
            "| 2026-04-24 | 半导体 | 半导体 | 待累计 | 26414.92亿 | 待累计 | 待累计 | 数据不足 |",
            rows,
        ).replace("# 2026-04-24 a股市场分析", "# 2026-05-20 a股市场分析")

        result = audit_report_markdown(bad)

        codes = {finding["code"] for finding in result["findings"]}
        self.assertIn("mainline_turnover_target_date_missing", codes)
        self.assertIn("mainline_turnover_recent_window_incomplete", codes)
        self.assertIn("mainline_turnover_trend_summary_missing", codes)
        self.assertFalse(result["passed"])

    def test_audit_flags_incomplete_appendix_mainline_turnover_table(self):
        complete_rows = "\n".join(
            [
                f"| 2026-04-{day:02d} | 半导体 | 3000.00亿 | 30000.00亿 | 10.0% | 待累计 | 大周期延续 | 继续观察 |"
                for day in range(1, 25)
            ]
            + [
                "| 2026-05-20 | 半导体 | 4050.00亿 | 29764.59亿 | 13.6% | +1.8pct | 大周期延续 | 继续观察 |"
            ]
        )
        complete_table = (
            "> 近25个交易日主线成交额占比趋势：当前13.6%，区间10.0%-13.6%，主线成交占比抬升，资金聚焦度走强。\n\n"
            "| 日期 | 小周期方向 | 主线成交额 | 两市成交额 | 占比 | 占比变化 | 切换判断 | 解读 |\n"
            "|------|------------|------------|------------|------|----------|----------|------|\n"
            f"{complete_rows}"
        )
        appendix_table = (
            "##### 附录：主线成交额占比趋势\n"
            "| 日期 | 小周期方向 | 主线成交额 | 两市成交额 | 占比 | 占比变化 | 切换判断 | 解读 |\n"
            "|------|------------|------------|------------|------|----------|----------|------|\n"
            "| 2026-05-20 | 半导体 | 4050.00亿 | 29764.59亿 | 13.6% | 待累计 | 大周期延续 | 继续观察 |"
        )
        bad = GOOD_MARKDOWN.replace(
            "| 2026-04-24 | 半导体 | 待累计 | 26414.92亿 | 待累计 | 待累计 | 大周期延续 | 数据不足 |",
            complete_table,
        ).replace("## 四、资金意图", f"{appendix_table}\n\n## 四、资金意图").replace(
            "# 2026-04-24 a股市场分析",
            "# 2026-05-20 a股市场分析",
        )

        result = audit_report_markdown(bad)

        codes = {finding["code"] for finding in result["findings"]}
        self.assertIn("mainline_turnover_recent_window_incomplete", codes)
        self.assertFalse(result["passed"])

    def test_audit_flags_unconfirmed_mainline_turnover_rows_with_real_amounts_in_any_duplicate_table(self):
        complete_rows = "\n".join(
            [
                f"| 2026-04-{day:02d} | 半导体 | 3000.00亿 | 30000.00亿 | 10.0% | 待累计 | 大周期延续 | 继续观察 |"
                for day in range(1, 25)
            ]
            + [
                "| 2026-05-20 | 半导体 | 4050.00亿 | 29764.59亿 | 13.6% | +1.8pct | 大周期延续 | 继续观察 |"
            ]
        )
        complete_table = (
            "> 近25个交易日主线成交额占比趋势：当前13.6%，区间10.0%-13.6%，主线成交占比抬升，资金聚焦度走强。\n\n"
            "| 日期 | 小周期方向 | 主线成交额 | 两市成交额 | 占比 | 占比变化 | 切换判断 | 解读 |\n"
            "|------|------------|------------|------------|------|----------|----------|------|\n"
            f"{complete_rows}"
        )
        bad_t52_rows = "\n".join(
            [
                f"| 2026-04-{day:02d} | 半导体 | 3000.00亿 | 30000.00亿 | 10.0% | 待累计 | 大周期延续 | 继续观察 |"
                for day in range(1, 25)
            ]
            + [
                "| 2026-05-20 | 小周期待确认 | 4050.00亿 | 29764.59亿 | 13.6% | +1.8pct | 小周期待确认 | 候选方向成交额占比可记录，但未确认主攻线 |"
            ]
        )
        appendix_table = (
            "##### 附录：主线成交额占比趋势\n"
            "> 近25个交易日主线成交额占比趋势：当前13.6%，区间10.0%-13.6%，主线成交占比抬升，资金聚焦度走强。\n\n"
            "**T-052**\n"
            "| 日期 | 小周期方向 | 主线成交额 | 两市成交额 | 占比 | 占比变化 | 切换判断 | 解读 |\n"
            "|------|------------|------------|------------|------|----------|----------|------|\n"
            f"{bad_t52_rows}"
        )
        bad = GOOD_MARKDOWN.replace(
            "| 2026-04-24 | 半导体 | 待累计 | 26414.92亿 | 待累计 | 待累计 | 大周期延续 | 数据不足 |",
            complete_table,
        ).replace("## 四、资金意图", f"{appendix_table}\n\n## 四、资金意图").replace(
            "# 2026-04-24 a股市场分析",
            "# 2026-05-20 a股市场分析",
        )

        result = audit_report_markdown(bad)

        codes = {finding["code"] for finding in result["findings"]}
        self.assertIn("mainline_turnover_unconfirmed_label_with_real_amount", codes)
        self.assertFalse(result["passed"])

    def test_audit_flags_new_high_feedback_using_previous_factor_date(self):
        bad = GOOD_MARKDOWN.replace(
            "| 市场状态 | 收缩防守 |",
            "| 市场状态 | 收缩防守 |\n\n"
            "### 3. 创新高趋势反馈\n"
            "> 最近可用因子日 2026-05-19：该日非ST非新股非次新阶段新高 164 只。\n\n"
            "| 日期 | 新高数 | 全A占比 | 较前日 | 主导板块 |\n"
            "|------|--------|---------|--------|----------|\n"
            "| 2026-05-19 | 164 | 3.28% | 待累计 | 半导体 |\n",
        ).replace("# 2026-04-24 a股市场分析", "# 2026-05-20 a股市场分析")

        result = audit_report_markdown(bad)

        codes = {finding["code"] for finding in result["findings"]}
        self.assertIn("new_high_previous_factor_date_substitute", codes)
        self.assertIn("new_high_target_date_missing", codes)
        self.assertFalse(result["passed"])

    def test_audit_flags_price_band_style_using_stale_recent_window(self):
        rows = "\n".join(
            f"| 2026-05-{day:02d} | -1.55% | -1.87% | +0.32pct | 震荡 | 同步回落 |"
            for day in range(3, 28)
        )
        bad = GOOD_MARKDOWN.replace(
            "| 市场状态 | 收缩防守 |",
            "| 市场状态 | 收缩防守 |\n\n"
            "### 3. 价格带风格\n"
            "> 最近可用窗口（截至2026-05-27）：近25个交易日价格带风格：最新差值 +0.32pct，当前为震荡。\n\n"
            "| 日期 | 百元股涨跌幅 | 低价股涨跌幅 | 当日差值 | 相对风格 | 绝对状态 |\n"
            "|------|--------------|--------------|--------------|----------|----------|\n"
            f"{rows}",
        ).replace("# 2026-04-24 a股市场分析", "# 2026-06-05 a股市场分析")

        result = audit_report_markdown(bad)

        codes = {finding["code"] for finding in result["findings"]}
        self.assertIn("price_band_style_target_date_missing", codes)
        self.assertIn("price_band_style_recent_window_stale", codes)
        self.assertFalse(result["passed"])

    def test_audit_flags_missing_extreme_conviction_recent_tracking_table(self):
        bad = GOOD_MARKDOWN.replace(
            "**明日极度看好近25日跟踪表**（按入选日展示，排除A杀样本）（过程证据）:\n"
            "| 入选日 | 股票 | 代码 | 排名 | 所属方向 | 观察位窗口 | 复盘状态 | 历史复盘动作 | 作废线 | 记录ID |\n"
            "|--------|------|------|------|----------|----------|----------|------------|--------|--------|\n"
            "| 2026-04-24 | 富瀚微 | 300613 | 1 | 半导体 | 09:50-10:10 | 等待复盘 | 等待计划窗口事实回写 | 按原计划作废条件处理 | 2026-04-24:300613 |\n\n",
            "",
        )

        result = audit_report_markdown(bad)

        self.assertIn("extreme_conviction_tracking_missing", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_flags_a_kill_sample_inside_extreme_conviction_recent_tracking_table(self):
        bad = GOOD_MARKDOWN.replace(
            "| 2026-04-24 | 富瀚微 | 300613 | 1 | 半导体 | 09:50-10:10 | 等待复盘 | 等待计划窗口事实回写 | 按原计划作废条件处理 | 2026-04-24:300613 |",
            "| 2026-04-24 | 冷却股 | 000003 | 1 | 军工 | 09:50-10:10 | A杀淘汰 | 不参与 | A杀冷却 | 2026-04-24:000003 |",
        )

        result = audit_report_markdown(bad)

        self.assertIn("extreme_conviction_tracking_contains_a_kill", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_flags_non_historical_action_wording_inside_extreme_tracking_table(self):
        bad = GOOD_MARKDOWN.replace(
            "| 2026-04-24 | 富瀚微 | 300613 | 1 | 半导体 | 09:50-10:10 | 等待复盘 | 等待计划窗口事实回写 | 按原计划作废条件处理 | 2026-04-24:300613 |",
            "| 2026-04-24 | 富瀚微 | 300613 | 1 | 半导体 | 09:50-10:10 | 预演命中 | 若已买入，次日先看是否继续强于市场 | 按原计划作废条件处理 | 2026-04-24:300613 |",
        )

        result = audit_report_markdown(bad)

        self.assertIn(
            "extreme_conviction_tracking_action_wording_not_historical",
            {finding["code"] for finding in result["findings"]},
        )
        self.assertFalse(result["passed"])

    def test_audit_flags_zero_position_appendix_action_wording(self):
        bad = (
            GOOD_MARKDOWN.replace(
                "| 50%条件执行 | 正盈亏比 | 半导体 | 半导体 | 修复 | 富瀚微(300613) | 50%条件执行 | 50%：只做合格对象，按昨晚预案检查执行资格，B1未变强不补B2，不满足回到0% |",
                "| 0%不参与 | 负盈亏比 | 半导体 | 半导体 | 收缩防守 | 暂无 | 0%不参与 | 0%：没有合格标的就不参与 |",
            )
            + "\n| ST洲际(600759) | 2026-05-14 | 热榜第11+涨幅0.0%，明日可能反包 |\n"
            + "| 2026-05-22 | 产业链供需改善 | ⭐⭐ | 半导体 | 📈利好 | 关注埋伏 |\n"
        )

        result = audit_report_markdown(bad)

        self.assertIn(
            "zero_position_legacy_tomorrow_wording",
            {finding["code"] for finding in result["findings"]},
        )
        self.assertFalse(result["passed"])

    def test_audit_flags_zero_position_legacy_buy_action_wording(self):
        bad = (
            GOOD_MARKDOWN.replace(
                "| 50%条件执行 | 正盈亏比 | 半导体 | 半导体 | 修复 | 富瀚微(300613) | 50%条件执行 | 50%：只做合格对象，按昨晚预案检查执行资格，B1未变强不补B2，不满足回到0% |",
                "| 0%不参与 | 负盈亏比 | 半导体 | 半导体 | 收缩防守 | 暂无 | 0%不参与 | 0%：没有合格标的就不参与 |",
            )
            + "\n##### 附录：Step 4 - 明日买点预计算\n"
            + "| 入选日 | 股票 | 代码 | 排名 | 所属方向 | 买入窗口 | 复盘状态 | 历史复盘动作 | 作废线 | 记录ID |\n"
            + "**最终动作表**（只展示真正可执行对象）:\n"
            + "| 尾盘 | 只判断是否量化电风扇行情 | 无 | 非电风扇不尾盘开新仓 | 例外，不是常规 |\n"
            + "| 板块 | 龙虎榜净买入 | 结论 |\n"
        )

        result = audit_report_markdown(bad)

        self.assertIn(
            "zero_position_legacy_tomorrow_wording",
            {finding["code"] for finding in result["findings"]},
        )
        self.assertFalse(result["passed"])

    def test_audit_flags_zero_position_backtest_hit_board_wording(self):
        bad = (
            GOOD_MARKDOWN.replace(
                "| 50%条件执行 | 正盈亏比 | 半导体 | 半导体 | 修复 | 富瀚微(300613) | 50%条件执行 | 50%：只做合格对象，按昨晚预案检查执行资格，B1未变强不补B2，不满足回到0% |",
                "| 0%不参与 | 负盈亏比 | 半导体 | 半导体 | 收缩防守 | 暂无 | 0%不参与 | 0%：没有合格标的就不参与 |",
            )
            .replace(
                "| 10:00左右买 | 只看周期主线核心，且必须有承接 | 竞价表态、参与窗口与结构确认共同成立 | 买后用30分钟结构止损 | 50%/100%或0% |",
                "| 10:00左右观察 | 暂无唯一对象，不做新增参与 | 无 | 无新增参与止损 | 不做 |",
            )
            .replace(
                "| 尾盘 | 只判断是否量化电风扇行情 | 仅例外 | 非电风扇不尾盘开新仓 | 例外 |",
                "| 尾盘 | 只判断是否量化电风扇行情 | 无 | 非电风扇不尾盘新增参与 | 例外，不是常规 |",
            )
            + "\n| 竞价表态 + 回封观察 | 0%不参与 | 交易逻辑确认 / 竞价表态 / 回封/打板 |\n"
        )

        result = audit_report_markdown(bad)

        self.assertIn(
            "zero_position_legacy_tomorrow_wording",
            {finding["code"] for finding in result["findings"]},
        )
        self.assertFalse(result["passed"])

    def test_audit_flags_unique_focus_mismatch_between_plan_and_final_summary(self):
        bad = GOOD_MARKDOWN.replace(
            "| 50%条件执行 | 正盈亏比 | 半导体 | 半导体 | 修复 | 富瀚微(300613) | 50%条件执行 | 50%：只做合格对象，按昨晚预案检查执行资格，B1未变强不补B2，不满足回到0% |",
            "| 50%条件执行 | 正盈亏比 | 半导体 | 半导体 | 修复 | 中嘉博创(000889) | 50%条件执行 | 50%：只做合格对象，按昨晚预案检查执行资格，B1未变强不补B2，不满足回到0% |",
        )

        result = audit_report_markdown(bad)

        self.assertIn("unique_focus_mismatch", {finding["code"] for finding in result["findings"]})

    def test_audit_allows_same_unique_focus_with_different_label_format(self):
        report = GOOD_MARKDOWN.replace(
            "| 只看唯一对象 | 富瀚微(300613) | 主线确认 + 承接 + 09:50-10:10窗口 | 不做 |",
            "| 只看唯一对象 | 300613 富瀚微（半导体） | 主线确认 + 承接 + 09:50-10:10窗口 | 不做 |",
        )

        result = audit_report_markdown(report)

        self.assertNotIn("unique_focus_mismatch", {finding["code"] for finding in result["findings"]})
        self.assertTrue(result["passed"], result["findings"])

    def test_audit_flags_zero_position_conditional_observation_target_as_participation_plan(self):
        report = (
            self.zero_position_report_with_decision_attribution()
            .replace(
                "| 明日唯一动作 | 标的 | 条件 | 不满足怎么办 |\n"
                "|--------------|------|------|--------------|\n"
                "| 只看唯一对象 | 暂无 | 09:50-10:10窗口 | 主线确认 + 承接 + 09:50-10:10窗口未同时满足 | 不做 |",
                "| 明日观察动作 | 标的 | 观察窗 | 条件 | 不满足怎么办 |\n"
                "|--------------|------|------|------|--------------|\n"
                "| 只看条件观察对象 | 300613 富瀚微（半导体） | 09:50-10:10 | 主线确认 + 承接 + 观察窗口同时成立 | 不满足继续0% |",
            )
            .replace(
                "| 0%不参与 | 负盈亏比 | 半导体 | 半导体 | 修复 | 暂无 | 0%不参与 | 0%：不新增参与，等待下一次预演条件重新成立 |",
                "| 0%不参与 | 负盈亏比 | 半导体 | 半导体 | 修复 | 条件观察：300613 富瀚微（半导体） | 0%不参与 | 盘前0%；09:50-10:10窗口主线确认 + 承接 + 观察窗口同时成立，才评估50%条件执行；不满足继续0% |",
            )
            + "\n##### 附录：# 今日总决策面板（过程证据）\n"
            + "| 字段 | 内容 |\n"
            + "|------|------|\n"
            + "| 今日新增上限 | 0 |\n"
            + "| 主买对象 | 暂无 |\n"
            + "| 补位对象 | 富瀚微(300613) |\n"
            + "\n**最终动作表**（只展示真正具备参与资格的对象）:\n"
            + "| 明天具体怎么做 | 股票 | 代码 | 触发条件 | 止损/时间 |\n"
            + "|----------|------|------|----------|-----------|\n"
            + "| ⏳ 确认后执行预案 | 富瀚微 | 300613 | 09:50-10:10站上确认价，且板块承接不塌，固定交易窗口内条件成立后才评估50%条件执行 | 失效价 |\n"
            + "\n**明天仓位怎么放**:\n"
            + "- **进攻仓位三态**: 50%条件执行\n"
            + "- **明天仓位放多少**: 50%条件执行；盘前不抢跑，固定交易窗口条件满足后执行，不满足回到0%\n"
        )

        result = audit_report_markdown(report)

        codes = {finding["code"] for finding in result["findings"]}
        self.assertIn("zero_position_tomorrow_action_conflict", codes)
        self.assertFalse(result["passed"])

    def test_audit_allows_zero_position_observation_anchor_without_participation_plan(self):
        report = (
            self.zero_position_report_with_decision_attribution()
            .replace(
                "| 明日唯一动作 | 标的 | 条件 | 不满足怎么办 |\n"
                "|--------------|------|------|--------------|\n"
                "| 只看唯一对象 | 暂无 | 09:50-10:10窗口 | 主线确认 + 承接 + 09:50-10:10窗口未同时满足 | 不做 |",
                "| 明日观察动作 | 标的 | 观察窗 | 条件 | 不满足怎么办 |\n"
                "|--------------|------|------|------|--------------|\n"
                "| 只看观察对象 | 300613 富瀚微（半导体） | 09:50-10:10 | 主线确认 + 承接 + 观察窗口同时成立 | 不满足继续0% |",
            )
            .replace(
                "| 0%不参与 | 负盈亏比 | 半导体 | 半导体 | 修复 | 暂无 | 0%不参与 | 0%：不新增参与，等待下一次预演条件重新成立 |",
                "| 0%不参与 | 负盈亏比 | 半导体 | 半导体 | 修复 | 观察对象：300613 富瀚微（半导体） | 0%不参与 | 盘前0%；只观察300613 富瀚微（半导体），成立才保留观察，不能转成新增参与；不满足继续0% |",
            )
            .replace("| 观察对象 | 暂无 |", "| 观察对象 | 300613 富瀚微（半导体） |")
            .replace(
                "| 不参与依据 | 候选全部未达参与资格，需要复盘候选筛选。 |",
                "| 不参与依据 | 弱市场或趋势失效时，只允许0%保护本金。 |",
            )
            .replace("| 无执行目标原因 | 候选池没有选出足够强的核心 |", "| 无执行目标原因 | 市场条件未到，只保留观察对象 |")
            .replace("| 责任归因 | 决策问题 |", "| 责任归因 | 市场问题 |")
            .replace(
                "| 责任归因 | 市场问题 |\n"
                "| 当前状态 | 0%无合格标的 |",
                "| 责任归因 | 市场问题 |\n"
                "| 观察对象性质 | 强弱参照，不是执行目标 |\n"
                "| 恢复评估条件 | 主线确认 + 承接 + 观察窗口同时成立 |\n"
                "| 观察对象去留 | 明日收盘前未满足恢复评估条件，移出前台观察 |\n"
                "| 当前状态 | 0%无合格标的 |",
            )
            + "\n##### 附录：# 今日总决策面板（过程证据）\n"
            + "| 字段 | 内容 |\n"
            + "|------|------|\n"
            + "| 今日新增上限 | 0 |\n"
            + "| 主观察对象 | 暂无 |\n"
            + "| 观察对象 | 富瀚微(300613) |\n"
            + "\n**最终动作表**（只展示真正具备参与资格的对象）:\n"
            + "| 明天具体怎么做 | 股票 | 代码 | 触发条件 | 止损/时间 |\n"
            + "|----------|------|------|----------|-----------|\n"
            + "| ❌ 明天没有可买对象 | - | - | 无符合条件标的 | - |\n"
            + "\n**明天仓位怎么放**:\n"
            + "- **进攻仓位三态**: 0%不参与\n"
            + "- **明天仓位放多少**: 盘前0%；暂无新增参与资格，只观察风险是否钝化\n"
        )

        result = audit_report_markdown(report)

        codes = {finding["code"] for finding in result["findings"]}
        self.assertNotIn("unique_focus_mismatch", codes)
        self.assertNotIn("execution_condition_missing", codes)
        self.assertNotIn("zero_position_tomorrow_action_conflict", codes)
        self.assertNotIn("zero_position_legacy_tomorrow_wording", codes)
        self.assertTrue(result["passed"], result["findings"])

    def test_audit_flags_zero_position_schedule_that_turns_observation_into_action(self):
        report = (
            self.zero_position_report_with_decision_attribution()
            + "\n**竞价表态与开盘买卖窗口（09:20-09:35，买卖只在09:30-09:35）**:\n"
            + "- 观察唯一对象的竞价表态、匹配金额、委托稳定和板块同步\n"
            + "- 若竞价表态和开盘前几分钟承接同时成立，按09:30-09:35窗口处理；不成立回到0%\n"
            + "\n**09:50-10:10买卖窗口（09:50-10:10）**:\n"
            + "- 当前是0%不参与，本时段只确认主线核心是否在固定交易窗口内满足条件\n"
        )

        result = audit_report_markdown(report)

        self.assertIn("zero_position_legacy_tomorrow_wording", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_flags_zero_position_without_decision_attribution(self):
        result = audit_report_markdown(self.zero_position_report())

        self.assertIn("zero_position_decision_attribution_missing", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_allows_zero_position_with_observation_anchor_and_attribution(self):
        report = _replace_account_advice(
            self.zero_position_report(),
            "## 明日账户建议\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 明日仓位 | 0%不参与 |\n"
            "| 执行目标 | 无 |\n"
            "| 观察对象 | 富瀚微(300613) |\n"
            "| 不参与依据 | 弱市场或趋势失效时，只允许0%保护本金。 |\n"
            "| 无执行目标原因 | 市场条件未到，只保留观察对象 |\n"
            "| 责任归因 | 市场问题 |\n"
            "| 观察对象性质 | 强弱参照，不是执行目标 |\n"
            "| 恢复评估条件 | 主线确认 + 承接 + 09:50-10:10窗口未同时满足 |\n"
            "| 观察对象去留 | 明日收盘前未满足恢复评估条件，移出前台观察 |\n"
            "| 明日动作 | 0%不参与；只保留观察对象，不新增参与 |",
        ).replace(
            "## 五、个股解读\n"
            "### 1. 个股裁决\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 唯一对象 | 富瀚微(300613) |\n"
            "| 当前状态 | 0%不参与 |\n"
            "| 备用观察 | 暂无 |\n"
            "| 今日不买原因 | 等09:50-10:10窗口 |\n",
            "## 五、个股解读\n"
            "### 1. 个股裁决\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 明日仓位 | 0%不参与 |\n"
            "| 执行目标 | 无 |\n"
            "| 观察对象 | 富瀚微(300613) |\n"
            "| 不参与依据 | 弱市场或趋势失效时，只允许0%保护本金。 |\n"
            "| 无执行目标原因 | 市场条件未到，只保留观察对象 |\n"
            "| 责任归因 | 市场问题 |\n"
            "| 观察对象性质 | 强弱参照，不是执行目标 |\n"
            "| 恢复评估条件 | 主线确认 + 承接 + 09:50-10:10窗口未同时满足 |\n"
            "| 观察对象去留 | 明日收盘前未满足恢复评估条件，移出前台观察 |\n"
            "| 当前状态 | 0%条件观察 |\n"
            "| 备用观察 | 暂无 |\n"
            "| 今日不买原因 | 等09:50-10:10窗口 |\n",
        ).replace(
            "| 只看唯一对象 | 暂无 | 09:50-10:10窗口 | 主线确认 + 承接 + 09:50-10:10窗口未同时满足 | 不做 |",
            "| 只看观察对象 | 富瀚微(300613) | 09:50-10:10 | 主线确认 + 承接 + 09:50-10:10窗口未同时满足 | 不满足继续0% |",
        ).replace(
            "| 0%不参与 | 负盈亏比 | 半导体 | 半导体 | 修复 | 暂无 | 0%不参与 | 0%：不新增参与，等待下一次预演条件重新成立 |",
            "| 0%不参与 | 负盈亏比 | 半导体 | 半导体 | 修复 | 观察对象：富瀚微(300613) | 0%不参与 | 盘前0%；只观察富瀚微(300613)，条件成立才保留观察，不能转成新增参与；不满足继续0% |",
        )

        result = audit_report_markdown(report)

        codes = {finding["code"] for finding in result["findings"]}
        self.assertNotIn("zero_position_decision_attribution_missing", codes)
        self.assertNotIn("zero_position_observation_anchor_lifecycle_missing", codes)

    def test_audit_flags_zero_position_observation_anchor_without_strong_basis(self):
        report = _replace_account_advice(
            self.zero_position_report_with_decision_attribution(),
            "## 明日账户建议\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 明日仓位 | 0%不参与 |\n"
            "| 执行目标 | 无 |\n"
            "| 观察对象 | 富瀚微(300613) |\n"
            "| 不参与依据 | 市场条件未到，只保留观察对象 |\n"
            "| 无执行目标原因 | 市场条件未到，只保留观察对象 |\n"
            "| 责任归因 | 市场问题 |\n"
            "| 观察对象性质 | 强弱参照，不是执行目标 |\n"
            "| 恢复评估条件 | 主线确认 + 承接 + 09:50-10:10窗口未同时满足 |\n"
            "| 观察对象去留 | 明日收盘前未满足恢复评估条件，移出前台观察 |\n"
            "| 明日动作 | 0%不参与；只保留观察对象，不新增参与 |",
        ).replace(
            "| 观察对象 | 暂无 |",
            "| 观察对象 | 富瀚微(300613) |",
        ).replace(
            "| 不参与依据 | 候选全部未达参与资格，需要复盘候选筛选。 |",
            "| 不参与依据 | 市场条件未到，只保留观察对象 |",
        ).replace(
            "| 无执行目标原因 | 候选池没有选出足够强的核心 |",
            "| 无执行目标原因 | 市场条件未到，只保留观察对象 |",
        ).replace(
            "| 责任归因 | 决策问题 |",
            "| 责任归因 | 市场问题 |",
        ).replace(
            "| 责任归因 | 市场问题 |\n"
            "| 当前状态 | 0%无合格标的 |",
            "| 责任归因 | 市场问题 |\n"
            "| 观察对象性质 | 强弱参照，不是执行目标 |\n"
            "| 恢复评估条件 | 主线确认 + 承接 + 09:50-10:10窗口未同时满足 |\n"
            "| 观察对象去留 | 明日收盘前未满足恢复评估条件，移出前台观察 |\n"
            "| 当前状态 | 0%无合格标的 |",
        ).replace(
            "| 只看唯一对象 | 暂无 | 09:50-10:10窗口 | 主线确认 + 承接 + 09:50-10:10窗口未同时满足 | 不做 |",
            "| 只看观察对象 | 富瀚微(300613) | 09:50-10:10 | 主线确认 + 承接 + 09:50-10:10窗口未同时满足 | 不满足继续0% |",
        ).replace(
            "| 0%不参与 | 负盈亏比 | 半导体 | 半导体 | 修复 | 暂无 | 0%不参与 | 0%：不新增参与，等待下一次预演条件重新成立 |",
            "| 0%不参与 | 负盈亏比 | 半导体 | 半导体 | 修复 | 观察对象：富瀚微(300613) | 0%不参与 | 盘前0%；只观察富瀚微(300613)，条件成立才保留观察，不能转成新增参与；不满足继续0% |",
        )

        result = audit_report_markdown(report)

        self.assertIn("zero_position_strong_basis_missing", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_flags_observation_anchor_without_lifecycle(self):
        report = self.zero_position_report().replace(
            "## 五、个股解读\n"
            "### 1. 个股裁决\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 唯一对象 | 富瀚微(300613) |\n"
            "| 当前状态 | 0%不参与 |\n"
            "| 备用观察 | 暂无 |\n"
            "| 今日不买原因 | 等09:50-10:10窗口 |\n",
            "## 五、个股解读\n"
            "### 1. 个股裁决\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 明日仓位 | 0%不参与 |\n"
            "| 执行目标 | 无 |\n"
            "| 观察对象 | 富瀚微(300613) |\n"
            "| 不参与依据 | 弱市场或趋势失效时，只允许0%保护本金。 |\n"
            "| 无执行目标原因 | 市场条件未到，只保留观察对象 |\n"
            "| 责任归因 | 市场问题 |\n"
            "| 当前状态 | 0%条件观察 |\n"
            "| 备用观察 | 暂无 |\n"
            "| 今日不买原因 | 等09:50-10:10窗口 |\n",
        ).replace(
            "| 只看唯一对象 | 暂无 | 09:50-10:10窗口 | 主线确认 + 承接 + 09:50-10:10窗口未同时满足 | 不做 |",
            "| 只看观察对象 | 富瀚微(300613) | 09:50-10:10 | 主线确认 + 承接 + 09:50-10:10窗口未同时满足 | 不满足继续0% |",
        ).replace(
            "| 0%不参与 | 负盈亏比 | 半导体 | 半导体 | 修复 | 暂无 | 0%不参与 | 0%：不新增参与，等待下一次预演条件重新成立 |",
            "| 0%不参与 | 负盈亏比 | 半导体 | 半导体 | 修复 | 观察对象：富瀚微(300613) | 0%不参与 | 盘前0%；只观察富瀚微(300613)，条件成立才保留观察，不能转成新增参与；不满足继续0% |",
        )

        result = audit_report_markdown(report)

        self.assertIn("zero_position_observation_anchor_lifecycle_missing", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_flags_observation_anchor_mismatch_between_front_and_appendix(self):
        bad = (
            self.zero_position_report()
            .replace(
                "| 明日唯一动作 | 标的 | 条件 | 不满足怎么办 |\n"
                "|--------------|------|------|--------------|\n"
                "| 只看唯一对象 | 暂无 | 09:50-10:10窗口 | 主线确认 + 承接 + 09:50-10:10窗口未同时满足 | 不做 |",
                "| 明日观察动作 | 标的 | 观察窗 | 条件 | 不满足怎么办 |\n"
                "|--------------|------|------|------|--------------|\n"
                "| 只看观察对象 | 600726 华电能源（电力） | 09:50-10:10 | 主线确认 + 承接 + 观察窗口同时成立 | 不满足继续0% |",
            )
            .replace(
                "| 0%不参与 | 负盈亏比 | 半导体 | 半导体 | 修复 | 暂无 | 0%不参与 | 0%：不新增参与，等待下一次预演条件重新成立 |",
                "| 0%不参与 | 负盈亏比 | 半导体 | 半导体 | 修复 | 观察对象：600726 华电能源（电力） | 0%不参与 | 盘前0%；只观察600726 华电能源（电力），成立才保留观察，不能转成新增参与；不满足继续0% |",
            )
            + "\n**观察优先对象**: 京能电力(600578)\n"
            + "**先看顺序**（优先盯最能反映主线承接的对象）:\n"
            + "- 👀 京能电力(600578) - 主线继续看谁，09:50-10:10观察价9.21\n"
        )

        result = audit_report_markdown(bad)

        self.assertIn("observation_anchor_mismatch", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

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
            "| 只看唯一对象 | 富瀚微(300613) | 主线确认 + 承接 + 09:50-10:10窗口 | 不做 |",
            "| 只看唯一对象 | 暂无 | 主线确认 + 承接 + 09:50-10:10窗口未同时满足 | 不做 |",
        ).replace(
            "| 50%条件执行 | 正盈亏比 | 半导体 | 半导体 | 修复 | 富瀚微(300613) | 50%条件执行 | 50%：只做合格对象，按昨晚预案检查执行资格，B1未变强不补B2，不满足回到0% |",
            "| 50%条件执行 | 正盈亏比 | 半导体 | 半导体 | 修复 | 暂无 | 50%条件执行 | 50%：只做合格对象，按昨晚预案检查执行资格，B1未变强不补B2，不满足回到0% |",
        )

        result = audit_report_markdown(report)

        self.assertNotIn("unique_focus_contradiction", {finding["code"] for finding in result["findings"]})
        self.assertTrue(result["passed"], result["findings"])

    def test_audit_flags_empty_unique_focus_with_concrete_buy_candidate(self):
        bad = GOOD_MARKDOWN.replace(
            "| 只看唯一对象 | 富瀚微(300613) | 主线确认 + 承接 + 09:50-10:10窗口 | 不做 |",
            "| 只看唯一对象 | 暂无 | 主线确认 + 承接 + 09:50-10:10窗口未同时满足 | 不做 |",
        ).replace(
            "| 当前状态 | 50%条件执行对象 |",
            "| 当前状态 | 富瀚微(300613) 唯一买入，09:50-10:10窗口 |",
        ).replace(
            "| 50%条件执行 | 正盈亏比 | 半导体 | 半导体 | 修复 | 富瀚微(300613) | 50%条件执行 | 50%：只做合格对象，按昨晚预案检查执行资格，B1未变强不补B2，不满足回到0% |",
            "| 50%条件执行 | 正盈亏比 | 半导体 | 半导体 | 修复 | 暂无 | 50%条件执行 | 50%：只做合格对象，按昨晚预案检查执行资格，B1未变强不补B2，不满足回到0% |",
        )

        result = audit_report_markdown(bad)

        self.assertIn("unique_focus_contradiction", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_flags_final_zero_position_with_tomorrow_participation_action(self):
        bad = GOOD_MARKDOWN.replace(
            "| 只看唯一对象 | 富瀚微(300613) | 主线确认 + 承接 + 09:50-10:10窗口 | 不做 |",
            "| 明日主买对象 | 富瀚微(300613) | 主线确认 + 承接 + 09:50-10:10窗口 | 新增参与 |",
        ).replace(
            "| 进攻仓位三态 | 50% |",
            "| 进攻仓位三态 | 0% |",
        ).replace(
            "| 明日最大仓位 | 50% |",
            "| 明日最大仓位 | 0% |",
        ).replace(
            "| 50%条件执行 | 固定交易窗口条件 | 仅14:30-14:55例外 | 单笔最晚-5% | 只做主线 |",
            "| 0%不参与 | 固定交易窗口条件 | 仅14:30-14:55例外 | 单笔最晚-5% | 不新增参与 |",
        ).replace(
            "| 50%条件执行 | 正盈亏比 | 半导体 | 半导体 | 修复 | 富瀚微(300613) | 50%条件执行 | 50%：只做合格对象，按昨晚预案检查执行资格，B1未变强不补B2，不满足回到0% |",
            "| 0%不参与 | 负盈亏比 | 半导体 | 半导体 | 修复 | 暂无 | 0%不参与 | 0%：不新增参与，等待下一次预演条件重新成立 |",
        )

        result = audit_report_markdown(bad)

        self.assertIn("zero_position_tomorrow_action_conflict", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_flags_zero_position_with_current_backup_candidate_named_in_appendix(self):
        bad = self.zero_position_report() + (
            "\n##### 附录：# 今日总决策面板（过程证据）\n"
            "| 字段 | 内容 |\n"
            "|------|------|\n"
            "| 今日新增上限 | 0 |\n"
            "| 主买对象 | 暂无 |\n"
            "| 补位对象 | 风华高科(000636) |\n"
        )

        result = audit_report_markdown(bad)

        self.assertIn("zero_position_tomorrow_action_conflict", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_allows_zero_position_plan_without_new_position_stop(self):
        report = self.zero_position_report_with_decision_attribution()

        result = audit_report_markdown(report)

        self.assertNotIn("execution_window_missing", {finding["code"] for finding in result["findings"]})
        self.assertNotIn("execution_condition_missing", {finding["code"] for finding in result["findings"]})
        self.assertNotIn("zero_position_tomorrow_action_conflict", {finding["code"] for finding in result["findings"]})
        self.assertTrue(result["passed"], result["findings"])

    def test_audit_flags_chanlun_html_zero_position_mismatch(self):
        report = self.zero_position_report_with_decision_attribution()
        html = """
        <h2>明日抉择</h2>
        <table>
          <tr><td>最终执行条件</td><td>可以参与</td></tr>
          <tr><td>明日最大仓位</td><td>50%</td></tr>
          <tr><td>新增参与</td><td>参与</td></tr>
        </table>
        """

        result = audit_report_markdown(report, companion_html=html)

        self.assertIn("chanlun_tomorrow_decision_conflict", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_allows_chanlun_html_matching_zero_position(self):
        report = self.zero_position_report_with_decision_attribution()
        html = """
        <h2>明日抉择</h2>
        <table>
          <tr><td>最终执行条件</td><td>空仓等待，禁止参与；若你有仓位，只做退出不做幻想</td></tr>
          <tr><td>操作状态</td><td>撤退态</td></tr>
          <tr><td>明日最大仓位</td><td>0%</td></tr>
          <tr><td>新增参与</td><td>不参与</td></tr>
        </table>
        """

        result = audit_report_markdown(report, companion_html=html)

        self.assertNotIn("chanlun_tomorrow_decision_conflict", {finding["code"] for finding in result["findings"]})
        self.assertTrue(result["passed"], result["findings"])

    def test_audit_flags_missing_chanlun_tomorrow_decision_when_html_provided_for_zero_position(self):
        report = self.zero_position_report()
        html = "<h2>核心核对</h2><table><tr><td>指数</td><td>上证指数</td></tr></table>"

        result = audit_report_markdown(report, companion_html=html)

        self.assertIn("chanlun_tomorrow_decision_missing", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_allows_elimination_html_matching_zero_position(self):
        report = self.zero_position_report_with_decision_attribution()
        html = """
        <!doctype html>
        <meta name="artifact" content="elimination-tournament">
        <h1>2026-06-12 明日标的选股淘汰赛</h1>
        <script type="application/json" id="elimination-payload">
        {"final_action": {"label": "0%不参与", "position_pct": 0, "target": {}, "source": "selection_workflow.final"}}
        </script>
        """

        result = audit_report_markdown(report, companion_html=html)

        self.assertNotIn("elimination_tournament_final_conflict", {finding["code"] for finding in result["findings"]})
        self.assertNotIn("chanlun_tomorrow_decision_missing", {finding["code"] for finding in result["findings"]})
        self.assertTrue(result["passed"], result["findings"])

    def test_audit_flags_elimination_html_positive_final_when_report_is_zero_position(self):
        report = self.zero_position_report_with_decision_attribution()
        html = """
        <!doctype html>
        <meta name="artifact" content="elimination-tournament">
        <h1>2026-06-12 明日标的选股淘汰赛</h1>
        <script type="application/json" id="elimination-payload">
        {"final_action": {"label": "50%条件执行", "position_pct": 50, "target": {"name": "和远气体", "code": "002971"}}}
        </script>
        """

        result = audit_report_markdown(report, companion_html=html)

        self.assertIn("elimination_tournament_final_conflict", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_allows_sector_capital_preflight_html_matching_zero_position(self):
        report = self.zero_position_report_with_decision_attribution()
        html = self._sector_capital_preflight_html(
            final_action='{"label": "0%不参与", "position_pct": 0, "target": {}, "source": "selection_workflow.final"}'
        )

        result = audit_report_markdown(report, companion_html=html)

        self.assertNotIn("sector_capital_preflight_final_conflict", {finding["code"] for finding in result["findings"]})
        self.assertNotIn("chanlun_tomorrow_decision_missing", {finding["code"] for finding in result["findings"]})
        self.assertTrue(result["passed"], result["findings"])

    def test_audit_allows_zero_position_final_action_note_with_zero_input_count(self):
        report = self.zero_position_report_with_decision_attribution()
        html = self._sector_capital_preflight_html(
            final_action='{"label": "0%不参与", "position_pct": 0, "target": {}, "source": "selection_workflow.final"}',
            final_layer_input_count=0,
        )

        result = audit_report_markdown(report, companion_html=html)
        codes = {finding["code"] for finding in result["findings"]}

        self.assertNotIn("sector_capital_preflight_layer_count_mismatch", codes)
        self.assertNotIn("sector_capital_preflight_final_conflict", codes)
        self.assertTrue(result["passed"], result["findings"])

    def test_audit_counts_positive_final_action_entry_as_final_survivor(self):
        html = self._sector_capital_preflight_html(
            final_action='{"label": "50%条件执行", "position_pct": 50, "target": {"name": "富瀚微", "code": "300613"}}',
            final_layer_input_count=1,
            final_layer_survivor_count=1,
            final_layer_stock_code="300613",
            final_layer_stock_name="富瀚微",
            final_layer_sector="半导体",
            final_layer_reason="最终对象=富瀚微(300613)，动作=50%条件执行",
            previous_stock_code="300613",
            previous_stock_name="富瀚微",
            previous_sector="半导体",
        )

        result = audit_report_markdown(GOOD_MARKDOWN, companion_html=html)
        codes = {finding["code"] for finding in result["findings"]}

        self.assertNotIn("sector_capital_preflight_layer_count_mismatch", codes)
        self.assertNotIn("sector_capital_preflight_final_conflict", codes)
        self.assertTrue(result["passed"], result["findings"])

    def test_audit_flags_incomplete_sector_capital_preflight_payload(self):
        report = self.zero_position_report_with_decision_attribution()
        html = """
        <!doctype html>
        <meta name="artifact" content="sector-capital-preflight">
        <h1>2026-06-12 板块资金扩散生成前复核</h1>
        <script type="application/json" id="sector-capital-preflight-payload">
        {"schema_version": "sector_capital_preflight.v1", "final_action": {"label": "0%不参与", "position_pct": 0, "target": {}, "source": "selection_workflow.final"}}
        </script>
        """

        result = audit_report_markdown(report, companion_html=html)
        codes = {finding["code"] for finding in result["findings"]}

        self.assertIn("sector_capital_preflight_layers_missing", codes)
        self.assertIn("sector_capital_preflight_decision_list_missing", codes)
        self.assertIn("sector_capital_preflight_idiot_index_missing", codes)
        self.assertIn("sector_capital_preflight_tplus_rehearsal_missing", codes)
        self.assertFalse(result["passed"])

    def test_audit_flags_sector_capital_preflight_positive_final_when_report_is_zero_position(self):
        report = self.zero_position_report_with_decision_attribution()
        html = """
        <!doctype html>
        <meta name="artifact" content="sector-capital-preflight">
        <h1>2026-06-12 板块资金扩散生成前复核</h1>
        <script type="application/json" id="sector-capital-preflight-payload">
        {"schema_version": "sector_capital_preflight.v1", "final_action": {"label": "50%条件执行", "position_pct": 50, "target": {"name": "和远气体", "code": "002971"}}}
        </script>
        """

        result = audit_report_markdown(report, companion_html=html)

        self.assertIn("sector_capital_preflight_final_conflict", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_flags_missing_sector_capital_preflight_payload(self):
        report = self.zero_position_report_with_decision_attribution()
        html = """
        <!doctype html>
        <meta name="artifact" content="sector-capital-preflight">
        <h1>2026-06-12 板块资金扩散生成前复核</h1>
        """

        result = audit_report_markdown(report, companion_html=html)

        self.assertIn("sector_capital_preflight_payload_missing", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_flags_sector_capital_preflight_non_monotonic_stock_jump(self):
        report = self.zero_position_report_with_decision_attribution()
        html = """
        <!doctype html>
        <meta name="artifact" content="sector-capital-preflight">
        <h1>2026-06-12 板块资金扩散生成前复核</h1>
        <script type="application/json" id="sector-capital-preflight-payload">
        {
          "schema_version": "sector_capital_preflight.v1",
          "derivation_contract": "sector_capital_diffusion_first.v1",
          "mermaid": "周期窗口 唯一明日动作或不参与 T+1参与预案 T+2情绪周期推演 只批改不回写T0 白痴指数复核 压缩/合并/降级低价值高成本层",
          "final_action": {"label": "0%不参与", "position_pct": 0, "target": {}, "source": "selection_workflow.final"},
          "tplus_rehearsal": {
            "schema_version": "t0_tplus_rehearsal.v1",
            "tplus1": {"market_emotion":"分歧轮动","market_cycle":"周期窗口待确认","sector_emotion":"板块扩散不足","sector_cycle":"一日脉冲待验证","action":"观察"},
            "tplus2": {"market_emotion":"震荡","market_cycle":"待确认","sector_emotion":"分歧","sector_cycle":"待确认","action":"后验批改"}
          },
          "decision_list": [
            {"item":"市场能否进攻","conclusion":"待确认","evidence":"事实","counter_evidence":"反方","tomorrow_check":"明日验证","action":"观察"},
            {"item":"哪个板块被选择","conclusion":"待确认","evidence":"事实","counter_evidence":"反方","tomorrow_check":"明日验证","action":"观察"},
            {"item":"谁是资金载体","conclusion":"待确认","evidence":"事实","counter_evidence":"反方","tomorrow_check":"明日验证","action":"观察"},
            {"item":"是否有量化参与痕迹","conclusion":"待确认","evidence":"事实","counter_evidence":"反方","tomorrow_check":"明日验证","action":"观察"},
            {"item":"价格行为是否接受","conclusion":"待确认","evidence":"事实","counter_evidence":"反方","tomorrow_check":"明日验证","action":"观察"},
            {"item":"周期窗口是否打开","conclusion":"待确认","evidence":"事实","counter_evidence":"反方","tomorrow_check":"明日验证","action":"观察"},
            {"item":"账户是否适配","conclusion":"待确认","evidence":"事实","counter_evidence":"反方","tomorrow_check":"明日验证","action":"观察"}
          ],
          "idiot_index_review": [{"step":"涨停池起点","cost_proxy":"高","decision_value":"低","idiot_index_signal":"高","action":"降为证据层"}],
          "layers": [
            {"id":"market_capital_structure","input_count":1,"eliminated_count":1,"survivor_count":0,
             "entries":[{"stock_code":"600403","stock_name":"大有能源","sector":"煤炭开采","status":"eliminated","reason":"不属于当日方向","next_basis":"","elimination_basis":"第一层淘汰"}]},
            {"id":"sector_capital_diffusion","input_count":0,"eliminated_count":0,"survivor_count":0,"entries":[]},
            {"id":"capital_carrier","input_count":1,"eliminated_count":0,"survivor_count":1,
             "entries":[{"stock_code":"601991","stock_name":"大唐发电","sector":"火力发电","status":"survived","reason":"坏数据：上一层为0后又出现","next_basis":"进入下一层","elimination_basis":""}]},
            {"id":"carrier_role","input_count":0,"eliminated_count":0,"survivor_count":0,"entries":[]},
            {"id":"quant_trace","input_count":0,"eliminated_count":0,"survivor_count":0,"entries":[]},
            {"id":"price_action","input_count":0,"eliminated_count":0,"survivor_count":0,"entries":[]},
            {"id":"cycle_window","input_count":0,"eliminated_count":0,"survivor_count":0,"entries":[]},
            {"id":"counter_evidence_account","input_count":0,"eliminated_count":0,"survivor_count":0,"entries":[]},
            {"id":"final_action","input_count":0,"eliminated_count":0,"survivor_count":0,
             "entries":[{"stock_code":"","stock_name":"无执行对象","sector":"","status":"final_action","reason":"0%不参与","next_basis":"","elimination_basis":""}]}
          ]
        }
        </script>
        """

        result = audit_report_markdown(report, companion_html=html)

        self.assertIn(
            "sector_capital_preflight_layer_sequence_mismatch",
            {finding["code"] for finding in result["findings"]},
        )
        self.assertFalse(result["passed"])

    def test_audit_flags_sector_capital_preflight_final_action_stock_jump(self):
        report = self.zero_position_report_with_decision_attribution()
        html = self._sector_capital_preflight_html(
            final_action='{"label": "50%条件执行", "position_pct": 50, "target": {"name": "新冒出", "code": "000001"}}',
            final_layer_input_count=1,
            final_layer_survivor_count=1,
            final_layer_stock_code="000001",
            final_layer_stock_name="新冒出",
            final_layer_sector="未知",
            final_layer_reason="最终层不应新增上一层没有留下的股票",
        )

        result = audit_report_markdown(report, companion_html=html)

        self.assertIn(
            "sector_capital_preflight_layer_sequence_mismatch",
            {finding["code"] for finding in result["findings"]},
        )
        self.assertFalse(result["passed"])

    def _sector_capital_preflight_html(
        self,
        *,
        final_action,
        final_layer_input_count=0,
        final_layer_survivor_count=0,
        final_layer_stock_code="",
        final_layer_stock_name="无执行对象",
        final_layer_sector="",
        final_layer_reason="0%不参与",
        previous_stock_code="002971",
        previous_stock_name="和远气体",
        previous_sector="化工原料",
    ):
        layer_ids = (
            "market_capital_structure",
            "sector_capital_diffusion",
            "capital_carrier",
            "carrier_role",
            "quant_trace",
            "price_action",
            "cycle_window",
            "counter_evidence_account",
            "final_action",
        )
        layers = ",".join(
            (
                '{"id":"%s","input_count":1,"eliminated_count":0,"survivor_count":1,'
                '"entries":[{"stock_code":"%s","stock_name":"%s","sector":"%s",'
                '"status":"survived","reason":"板块资金扩散","next_basis":"进入下一层","elimination_basis":""}]}'
            )
            % (layer_id, previous_stock_code, previous_stock_name, previous_sector)
            for layer_id in layer_ids[:-1]
        )
        layers += (
            ',{"id":"final_action","input_count":%d,"eliminated_count":0,"survivor_count":%d,'
            '"entries":[{"stock_code":"%s","stock_name":"%s","sector":"%s","status":"final_action",'
            '"reason":"%s","next_basis":"","elimination_basis":""}]}'
        ) % (
            final_layer_input_count,
            final_layer_survivor_count,
            final_layer_stock_code,
            final_layer_stock_name,
            final_layer_sector,
            final_layer_reason,
        )
        decisions = ",".join(
            '{"item":"%s","conclusion":"待确认","evidence":"事实","counter_evidence":"反方","tomorrow_check":"明日验证","action":"观察"}'
            % item
            for item in (
                "市场能否进攻",
                "哪个板块被选择",
                "谁是资金载体",
                "是否有量化参与痕迹",
                "价格行为是否接受",
                "周期窗口是否打开",
                "账户是否适配",
            )
        )
        return f"""
        <!doctype html>
        <meta name="artifact" content="sector-capital-preflight">
        <h1>2026-06-12 板块资金扩散生成前复核</h1>
        <script type="application/json" id="sector-capital-preflight-payload">
        {{
          "schema_version": "sector_capital_preflight.v1",
          "derivation_contract": "sector_capital_diffusion_first.v1",
          "mermaid": "周期窗口 唯一明日动作或不参与 T+1参与预案 T+2情绪周期推演 只批改不回写T0 白痴指数复核 压缩/合并/降级低价值高成本层",
          "final_action": {final_action},
          "tplus_rehearsal": {{
            "schema_version": "t0_tplus_rehearsal.v1",
            "tplus1": {{"market_emotion":"分歧轮动","market_cycle":"周期窗口待确认","sector_emotion":"板块扩散不足","sector_cycle":"一日脉冲待验证","action":"观察"}},
            "tplus2": {{"market_emotion":"震荡","market_cycle":"待确认","sector_emotion":"分歧","sector_cycle":"待确认","action":"后验批改"}}
          }},
          "decision_list": [{decisions}],
          "idiot_index_review": [{{"step":"涨停池起点","cost_proxy":"高","decision_value":"低","idiot_index_signal":"高","action":"降为证据层"}}],
          "layers": [{layers}]
        }}
        </script>
        """

    def test_audit_flags_sector_capital_preflight_position_mismatch(self):
        html = """
        <!doctype html>
        <meta name="artifact" content="sector-capital-preflight">
        <h1>2026-04-24 板块资金扩散生成前复核</h1>
        <script type="application/json" id="sector-capital-preflight-payload">
        {"schema_version": "sector_capital_preflight.v1", "final_action": {"label": "100%核心进攻", "position_pct": 100, "target": {"name": "富瀚微", "code": "300613"}}}
        </script>
        """

        result = audit_report_markdown(GOOD_MARKDOWN, companion_html=html)

        self.assertIn("sector_capital_preflight_final_conflict", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_flags_missing_execution_windows(self):
        bad = GOOD_MARKDOWN.replace(
            "| 09:30-09:35 | 竞价强弱、主攻线承接 | 默认无 | 处理风险 | 不抢开盘 |\n",
            "",
        )

        result = audit_report_markdown(bad)

        self.assertIn("execution_window_missing", {finding["code"] for finding in result["findings"]})

    def test_audit_flags_missing_second_window_condition(self):
        bad = GOOD_MARKDOWN.replace("09:50-10:10窗口", "开盘确认")

        self.assertExecutionConditionMissing(bad, "09:50-10:10窗口")

    def test_audit_flags_missing_fixed_execution_window_condition(self):
        bad = (
            GOOD_MARKDOWN
            .replace("固定交易窗口条件", "结构确认")
            .replace("竞价强弱、主攻线承接", "主攻线承接")
            .replace("09:30-09:35", "开盘前")
            .replace("09:50-10:10窗口", "结构确认")
        )

        self.assertExecutionConditionMissing(bad, "固定交易窗口条件")

    def test_audit_flags_fast_window_polluted_by_structure_condition(self):
        bad = GOOD_MARKDOWN.replace(
            "| 只看唯一对象 | 富瀚微(300613) | 主线确认 + 承接 + 09:50-10:10窗口 | 不做 |",
            "| 只看唯一对象 | 富瀚微(300613) | 竞价表态 + 回封 | 主线确认 + 承接 + 09:50-10:10窗口 | 不做 |",
        )

        result = audit_report_markdown(bad)

        self.assertIn("fast_window_polluted_by_structure_condition", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_flags_missing_invalidation_and_risk_bottom_line(self):
        bad = GOOD_MARKDOWN.replace("买后用失效价和单笔-5%底线处理风险", "结构止损")

        self.assertExecutionConditionMissing(bad, "失效价 / 单笔-5%底线")

    def test_audit_flags_missing_no_action_fallback(self):
        bad = GOOD_MARKDOWN.replace("不做", "继续观察").replace("空仓", "等待")

        self.assertExecutionConditionMissing(bad, "不参与 / 不做 / 空仓")

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
            "| 触发条件 | 09:50-10:10窗口 |\n"
            "| 失败条件 | 主线回落 |\n"
            "| 排除对象 | 富瀚微(300613)：09:50-10:10窗口未满足 |\n"
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

    def test_audit_flags_zero_zero_breadth_as_incomplete_data(self):
        bad = GOOD_MARKDOWN.replace(
            "## 八、详细附录",
            "| 涨跌比 | 0 / 0 | - | 多头仍占优 |\n\n## 八、详细附录",
        )

        result = audit_report_markdown(bad)

        self.assertIn("market_breadth_incomplete", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_flags_zero_zero_board_tag_breadth_sentence_as_incomplete_data(self):
        bad = GOOD_MARKDOWN.replace(
            "### 附录B：历史主线池",
            "### 附录：十一、板块标签分析\n"
            "- **资金偏好**：上涨0家、下跌0家，热榜标签集中度优先看前排承接。\n\n"
            "### 附录B：历史主线池",
        )

        result = audit_report_markdown(bad)

        self.assertIn("market_breadth_incomplete", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_flags_unknown_position_context_rendered_as_no_holding(self):
        bad = _replace_account_advice(
            GOOD_MARKDOWN,
            "## 明日账户建议\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 账户约束 | 约1w账户；未输入持仓 |\n"
            "| 账户后台任务负担 | 无持仓负担 |",
        )

        result = audit_report_markdown(bad)

        self.assertIn("unknown_position_rendered_as_no_holding", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_allows_t0_main_object_when_no_yesterday_holding_and_position_is_50(self):
        good = _replace_account_advice(
            GOOD_MARKDOWN,
            "## 明日账户建议\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 账户约束 | 约1w账户；无昨日持仓先看T0对象 |\n"
            "| 明日仓位 | 50%条件执行；最大上限50%；B1参与权，B2确认权 |\n"
            "| 明日动作 | 已决定执行；按昨晚预案检查执行资格；B1先买参与权，B2只买确认权；B1未变强不补B2，走弱先取消B2并检查B1；不满足取消，回到0%不参与 |\n"
            "| T0主对象 | 华电能源(600726)：固定交易窗口条件 |\n"
            "| T0备用 | 暂无 |\n"
            "| 新增参与上限 | 1 |",
        )

        result = audit_report_markdown(good)

        self.assertNotIn("t0_object_without_holding_context", {finding["code"] for finding in result["findings"]})
        self.assertTrue(result["passed"])

    def test_audit_flags_positive_position_undecided_new_entry_wording(self):
        bad = _replace_account_advice(
            GOOD_MARKDOWN,
            "## 明日账户建议\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 账户约束 | 约1w账户；无昨日持仓先看T0对象 |\n"
            "| 明日仓位 | 50%条件执行；最大上限50%；B1参与权，B2确认权 |\n"
            "| 明日动作 | 只看T0主对象，条件满足才新开一手 |\n"
            "| T0主对象 | 华电能源(600726)：固定交易窗口条件 |\n"
            "| T0备用 | 暂无 |\n"
            "| 新增参与上限 | 1 |",
        )

        result = audit_report_markdown(bad)

        self.assertIn("positive_premarket_action_undecided_wording", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_flags_unmarked_process_evidence_headings(self):
        bad = GOOD_MARKDOWN.replace(
            "**明日极度看好近25日跟踪表**（按入选日展示，排除A杀样本）（过程证据）:",
            "**明日极度看好近25日跟踪表**（按入选日展示，排除A杀样本）:",
        )

        result = audit_report_markdown(bad)

        self.assertIn("process_evidence_heading_missing_marker", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_flags_account_advice_without_position_line(self):
        bad = _replace_account_advice(
            GOOD_MARKDOWN,
            "## 明日账户建议\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 账户约束 | 约1w账户；未输入持仓，先确认旧仓再看T0对象 |\n"
            "| 明日动作 | 0%不参与；只保留观察对象，不新开 |\n"
            "| 观察对象 | 华电能源(600726)：观察对象，不是T0 |\n"
            "| 新增参与上限 | 0 |",
        )

        result = audit_report_markdown(bad)

        self.assertIn("account_advice_missing_position", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_flags_old_position_switch_without_opportunity_comparison(self):
        bad = _replace_account_advice(
            GOOD_MARKDOWN,
            "## 明日账户建议\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 持仓确认 | 已有旧仓华电辽能(600396) |\n"
            "| 明日仓位 | 50%条件执行；最大上限50%；B1参与权，B2确认权 |\n"
            "| 明日动作 | 先处理旧仓，买华天科技(002185)；按昨晚预案检查执行资格；B1未变强不补B2，走弱先取消B2；不满足回到0%不参与 |",
        )

        result = audit_report_markdown(bad)

        self.assertIn("opportunity_comparison_missing", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_allows_observation_opportunity_row_with_incomplete_risk(self):
        good = GOOD_MARKDOWN.replace(
            "## 六、明日执行计划",
            "## 旧仓与新机会风险价格对比\n"
            "| 对象 | 身份 | 当前/观察价 | MA5风险 | MA10风险 | VWAP风险 | 作废价 | 上方空间 | 盈亏比 | 账户结论 |\n"
            "|------|------|-------------|---------|----------|----------|--------|----------|--------|----------|\n"
            "| 华电辽能(600396) | old_position | - | - | - | - | - | - | - | repair_once |\n"
            "| 华天科技(002185) | sector_anchor | 19.16 | 18.20 / -5.01% | 17.80 / -6.99% | - | - | - | 待计算 | 只保留观察，等风险价格补齐 |\n\n"
            "## 六、明日执行计划",
        )

        result = audit_report_markdown(good)

        self.assertNotIn("opportunity_comparison_incomplete_risk", {finding["code"] for finding in result["findings"]})

    def test_audit_flags_positive_participation_with_incomplete_opportunity_risk(self):
        bad = GOOD_MARKDOWN.replace(
            "## 六、明日执行计划",
            "## 旧仓与新机会风险价格对比\n"
            "| 对象 | 身份 | 当前/观察价 | MA5风险 | MA10风险 | VWAP风险 | 作废价 | 上方空间 | 盈亏比 | 账户结论 |\n"
            "|------|------|-------------|---------|----------|----------|--------|----------|--------|----------|\n"
            "| 华电辽能(600396) | old_position | - | - | - | - | - | - | - | repair_once |\n"
            "| 华天科技(002185) | sector_anchor | 19.16 | 18.20 / -5.01% | 17.80 / -6.99% | - | - | - | 待计算 | 50%条件执行 |\n\n"
            "## 六、明日执行计划",
        )

        result = audit_report_markdown(bad)

        self.assertIn("opportunity_comparison_incomplete_risk", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_flags_incomplete_candidate_trace_with_execution_plan(self):
        bad = GOOD_MARKDOWN.replace(
            "## 八、详细附录",
            "## 八、详细附录\n"
            "| 层级 | 候选 | 来源池 | 主线/板块 | 关键输入 | 满足条件 | 未满足/缺失 | 分支结果 | 明日动作 | 失效条件 |\n"
            "|------|------|------|------|------|------|------|------|------|------|\n"
            "|  | 江海股份(002484) |  | 元件 | 账户适配：实际可买 |  | 市场条件：数据缺失 | 关键数据不完整，停止生成动作 | 等触发条件成立 |  |\n\n"
            "| 明天具体怎么做 | 股票 | 代码 | 触发条件 | 止损/时间 |\n"
            "|----------|------|------|----------|-----------|\n"
            "| ⏳ 确认后执行预案 | 江海股份 | 002484 | 09:50-10:10站上74.07后再评估50%条件执行 | 70.37 |\n",
        )

        result = audit_report_markdown(bad)

        self.assertIn("incomplete_candidate_has_execution_plan", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_flags_crossline_candidate_rendered_as_mainline_core(self):
        bad = GOOD_MARKDOWN.replace(
            "## 八、详细附录",
            "- 👀 江海股份(002484) - 跨线继续看谁\n"
            "跨线对象（元件），只用于观察强弱，不代表主攻线切换。\n\n"
            "## 八、详细附录\n"
            "| 标的 | 来源池 | 当前处理 |\n"
            "|------|------|------|\n"
            "| 江海股份(002484) | 主线核心 | 2进3，观察竞价是否超预期 |\n",
        )

        result = audit_report_markdown(bad)

        self.assertIn("candidate_identity_conflict", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_allows_crossline_row_with_negative_mainline_core_reason(self):
        ok = GOOD_MARKDOWN.replace(
            "## 八、详细附录",
            "- 👀 江海股份(002484) - 跨线继续看谁\n"
            "跨线对象（元件），只用于观察强弱，不代表主攻线切换。\n\n"
            "## 八、详细附录\n"
            "| 层级 | 候选 | 来源池 | 未满足/缺失 |\n"
            "|------|------|------|------|\n"
            "| 观察层 | 江海股份(002484) | watch_anchor | 不是主线核心，继续观察 |",
        )

        result = audit_report_markdown(ok)

        self.assertNotIn("candidate_identity_conflict", {finding["code"] for finding in result["findings"]})

    def test_audit_flags_success_rates_that_ignore_request_degradation(self):
        bad = GOOD_MARKDOWN.replace(
            "## 八、详细附录",
            "## 八、详细附录\n"
            "- **数据源获取成功率**: 29/29 (100.0%)\n"
            "- **步骤执行成功率**: 27/27 (100.0%)\n\n"
            "| 请求步骤 | 状态 | 实际 provider | 目标字段 | 耗时 | 是否回退 | 上游异常 | 诊断明细 |\n"
            "|------|------|------|------|------|------|------|------|\n"
            "| request.market_stats | ⚠️ degraded | akshare.stock_market_activity_legu | market_stats | - | 否 | empty_result | - |\n",
        )

        result = audit_report_markdown(bad)

        self.assertIn("success_rate_ignores_request_issues", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_flags_observation_hits_exceed_visible_observation_pool(self):
        bad = GOOD_MARKDOWN.replace(
            "## 八、详细附录",
            "| 明天观察池 | 15只；江海股份(002484)：先观察 |\n"
            "| 市场贴合度 | 主线偏差 | 强势样本102只，主线命中0只，观察池命中99只 |\n\n"
            "## 八、详细附录",
        )

        result = audit_report_markdown(bad)

        self.assertIn("market_fit_observation_hits_exceed_visible_pool", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_flags_zero_position_front_page_rr_as_participation(self):
        bad = self.zero_position_report().replace(
            "## 三、周期与主线",
            "### 2. 市场状态结论\n"
            "| 项目 | 结论 | 依据 |\n"
            "|------|------|------|\n"
            "| 当前盈亏比 | 勉强可参与 | 参与只看主线、承接和个股结构同时成立。 |\n\n"
            "## 三、周期与主线",
        )

        result = audit_report_markdown(bad)

        self.assertIn("zero_position_participation_language", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_flags_zero_position_appendix_searching_participation_language(self):
        bad = (
            self.zero_position_report()
            + "\n##### 附录：超车窗口判断\n"
            + "| 对手方向 | 我方方向 | 明日验证 |\n"
            + "|----------|----------|----------|\n"
            + "| 旧主线 | 半导体 | 只在半导体核心里找参与资格 |\n"
        )

        result = audit_report_markdown(bad)

        self.assertIn("zero_position_participation_language", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_flags_incomplete_candidate_trace_waiting_for_trigger(self):
        bad = GOOD_MARKDOWN.replace(
            "## 八、详细附录",
            "## 八、详细附录\n"
            "| 层级 | 候选 | 来源池 | 主线/板块 | 关键输入 | 满足条件 | 未满足/缺失 | 分支结果 | 明日动作 | 失效条件 |\n"
            "|------|------|------|------|------|------|------|------|------|------|\n"
            "|  | 江海股份(002484) |  | 元件 | 账户适配：实际可买 |  | 市场条件：数据缺失 | 关键数据不完整，停止生成动作 | 等触发条件成立 |  |\n",
        )

        result = audit_report_markdown(bad)

        self.assertIn("incomplete_candidate_waits_for_trigger", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_allows_duplicate_front_page_long_table_cell(self):
        report = GOOD_MARKDOWN.replace(
            "## 二、市场基底\n| 项目 | 结论 |",
            "## 二、市场基底\n"
            "| 指标 | 数值 | 解读 |\n"
            "|------|------|------|\n"
            "| Top20成交容量 | 14/20只150亿级 | Top20第20名128.51亿，Top20合计3842.81亿，占两市12.86%；资金集中在大成交趋势核心，作为Top50后的补充观察，只说明资金选择方向，不单独给参与资格。 |\n"
            "### 2. 市场状态结论\n"
            "| 项目 | 结论 | 依据 |\n"
            "|------|------|------|\n"
            "| Top20成交容量 | 容量活跃 | Top20第20名128.51亿，Top20合计3842.81亿，占两市12.86%；资金集中在大成交趋势核心，作为Top50后的补充观察，只说明资金选择方向，不单独给参与资格。 |\n\n"
            "| 项目 | 结论 |",
        )

        result = audit_report_markdown(report)

        self.assertNotIn("front_page_duplicate_long_cell", {finding["code"] for finding in result["findings"]})

    def test_audit_allows_repeated_long_cells_inside_cycle_calendar(self):
        repeated = "连续记录同一个板块和状态时，周期日历也要每天明示板块，不写同上"
        markdown = GOOD_MARKDOWN.replace(
            "## 二、市场基底\n| 项目 | 结论 |",
            "## 二、市场基底\n"
            "### 1. 周期日历主视图\n"
            "| 周次 | 一 | 二 | 三 | 四 | 五 |\n"
            "|------|------|------|------|------|------|\n"
            f"| 06-01当周 | {repeated} | {repeated} | {repeated} | {repeated} | {repeated} |\n\n"
            "| 项目 | 结论 |",
        )

        result = audit_report_markdown(markdown)

        self.assertNotIn("front_page_duplicate_long_cell", {finding["code"] for finding in result["findings"]})

    def test_audit_accepts_pure_stopped_report_notice(self):
        stopped = """# 2026-05-28 A股日报

关键数据不完整，停止生成。

本日旧版日报已作废，不能作为交易计划或复盘依据继续使用。

## 停止原因

| 字段 | 当前状态 | 说明 |
|------|----------|------|
| 大盘涨跌统计 | 0 / 0 | 上涨、下跌家数未取到 |
| 热度前50个股 | 30 / 50 | 热榜样本不足 |

## 当前处理

2026-05-28 不生成日报，不给明日策略，不给个股执行计划。
"""

        result = audit_report_markdown(stopped)

        self.assertTrue(result["passed"], result["findings"])

    def test_audit_does_not_accept_stopped_notice_with_trade_plan_content(self):
        bad = """# 2026-05-28 A股日报

关键数据不完整，停止生成。

## 明日账户建议
| 项目 | 结论 |
|------|------|
| T0主对象 | 江海股份(002484)：条件观察 |

处理结论：不生成日报，不给明日策略，不给个股执行计划。
"""

        result = audit_report_markdown(bad)

        self.assertIn("stopped_report_contains_trade_plan", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])


class NewStockReportVisibilityAuditTest(unittest.TestCase):
    def test_accepts_upgrade_marker(self):
        result = audit_new_stock_visibility(
            "### 附录A：新股周期判定\n\n有新股研究升级，进入观察。\n"
        )

        self.assertEqual(result["findings"], [])
        self.assertTrue(result["passed"])

    def test_accepts_absence_marker(self):
        result = audit_new_stock_visibility(
            "### 附录A：新股周期判定\n\n有新股研究池，但今日未形成买入资格。\n"
        )

        self.assertEqual(result["findings"], [])
        self.assertTrue(result["passed"])

    def test_fails_when_heading_has_no_upgrade_or_absence_reason(self):
        result = audit_new_stock_visibility("### 附录A：新股周期判定\n\n今日跟踪新股研究池。\n")

        self.assertIn("new_stock_visibility_missing", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_fails_when_only_other_section_has_upgrade_marker(self):
        result = audit_new_stock_visibility(
            "## 五、个股解读\n"
            "\n"
            "有新股研究升级，进入观察。\n"
            "\n"
            "### 附录A：新股周期判定\n"
            "\n"
            "今日跟踪新股研究池。\n"
        )

        self.assertIn("new_stock_visibility_missing", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])


class BayesianDiagnosisAuditTest(unittest.TestCase):
    def _report_with_diagnosis(self, diagnosis_section, final_target="豫能控股(001896)"):
        return f"""# 2026-06-04 a股市场分析

## 七、最终结论
| 明日结论 | 当前盈亏比 | 周期主线 | 当天主攻线 | 当前市场底色 | 重点对象 | 明日执行风格 | 一句话动作 |
|----------|------------|----------|------------|--------------|--------------|--------------|------------|
| 已决定50%条件执行 | 不确定时不值得主动参与 | 电力 | 电力 | 修复但分歧仍在 | {final_target} | 50%条件执行 | 已决定50%条件执行；盘中不满足取消，回到0%不参与 |

{diagnosis_section}
"""

    def test_audit_rejects_bayesian_path_without_source_date(self):
        diagnosis = """### 路径诊断复盘
| 项目 | 结论 |
|------|------|
| 路径结论 | 条件执行 |
| 最终动作一致性 | 一致 |
| 执行对象 | 豫能控股(001896) |
| 动作 | 已决定50%条件执行；盘中不满足取消，回到0%不参与 |
| 来源日期 | 来源日期缺失 |
"""

        result = audit_report_markdown(self._report_with_diagnosis(diagnosis))

        self.assertIn("bayesian_path_source_date_missing", {finding["code"] for finding in result["findings"]})

    def test_audit_rejects_probability_band_in_bayesian_diagnosis(self):
        diagnosis = """### 路径诊断复盘
| 项目 | 结论 |
|------|------|
| 路径结论 | 胜率70% |
| 最终动作一致性 | 一致 |
| 执行对象 | 豫能控股(001896) |
| 动作 | 已决定50%条件执行；盘中不满足取消，回到0%不参与 |
| 来源日期 | 2026-06-04 |
"""

        result = audit_report_markdown(self._report_with_diagnosis(diagnosis))

        self.assertIn("bayesian_probability_band_forbidden", {finding["code"] for finding in result["findings"]})

    def test_audit_rejects_reversed_probability_wording_in_bayesian_diagnosis(self):
        diagnosis = """### 路径诊断复盘
| 项目 | 结论 |
|------|------|
| 路径结论 | 70%胜率 |
| 最终动作一致性 | 一致 |
| 执行对象 | 豫能控股(001896) |
| 动作 | 已决定50%条件执行；盘中不满足取消，回到0%不参与 |
| 来源日期 | 2026-06-04 |
"""

        result = audit_report_markdown(self._report_with_diagnosis(diagnosis))

        self.assertIn("bayesian_probability_band_forbidden", {finding["code"] for finding in result["findings"]})

    def test_audit_rejects_missing_source_date_marker_in_bayesian_appendix(self):
        report = """# 2026-06-04 a股市场分析

## 附录

```text
路径诊断复盘
|-- 路径结论=条件执行 最终动作一致性=一致 仓位=50% 动作=已决定50%条件执行
|-- 层级=市场层 日期=- 输入=市场信息待确认 判断=市场层信息待确认 传递=不能单独推出参与资格
```
"""

        result = audit_report_markdown(report)

        self.assertIn("bayesian_path_source_date_missing", {finding["code"] for finding in result["findings"]})

    def test_audit_rejects_path_consistent_with_counter_evidence(self):
        diagnosis = """### 路径诊断复盘
| 项目 | 结论 |
|------|------|
| 路径结论 | 路径一致 |
| 最终动作一致性 | 一致 |
| 执行对象 | 豫能控股(001896) |
| 动作 | 已决定50%条件执行；盘中不满足取消，回到0%不参与 |
| 来源日期 | 2026-06-04 |

#### 关键反证
- 固定交易窗口未确认
"""

        result = audit_report_markdown(self._report_with_diagnosis(diagnosis))

        self.assertIn(
            "bayesian_path_conclusion_conflicts_with_counter_evidence",
            {finding["code"] for finding in result["findings"]},
        )

    def test_audit_rejects_hidden_bayesian_object_conflict(self):
        diagnosis = """### 路径诊断复盘
| 项目 | 结论 |
|------|------|
| 路径结论 | 条件执行 |
| 最终动作一致性 | 一致 |
| 执行对象 | 豫能控股(001896) |
| 动作 | 已决定50%条件执行；盘中不满足取消，回到0%不参与 |
| 来源日期 | 2026-06-04 |
"""

        result = audit_report_markdown(self._report_with_diagnosis(diagnosis, final_target="上海石化(600688)"))

        self.assertIn("bayesian_final_object_conflict_hidden", {finding["code"] for finding in result["findings"]})

    def test_audit_allows_visible_bayesian_object_conflict(self):
        diagnosis = """### 路径诊断复盘
| 项目 | 结论 |
|------|------|
| 路径结论 | 条件执行 |
| 最终动作一致性 | 不一致 |
| 执行对象 | 豫能控股(001896) |
| 动作 | 已决定50%条件执行；盘中不满足取消，回到0%不参与 |
| 来源日期 | 2026-06-04 |
"""

        result = audit_report_markdown(self._report_with_diagnosis(diagnosis, final_target="上海石化(600688)"))

        self.assertNotIn("bayesian_final_object_conflict_hidden", {finding["code"] for finding in result["findings"]})


if __name__ == "__main__":
    unittest.main()
