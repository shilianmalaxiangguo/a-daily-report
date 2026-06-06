import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.report_acceptance_audit import audit_new_stock_visibility, audit_report_markdown


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
| 日期 | 周期主线 | 当天主攻线 | 主线成交额 | 两市成交额 | 占比 | 占比变化 | 解读 |
|------|----------|------------|------------|------------|------|----------|------|
| 2026-04-24 | 半导体 | 半导体 | 待累计 | 26414.92亿 | 待累计 | 待累计 | 数据不足 |

## 明日账户建议
| 项目 | 结论 |
|------|------|
| 明日仓位 | 50%标准进攻 |
| 明日动作 | 只看唯一对象，固定交易窗口条件成立才参与 |

## 一、交易纪律
| 明日结论 | 默认节奏 | 尾盘例外 | 最大风险 | 核心纪律 |
|----------|----------|----------|----------|----------|
| 50%标准进攻 | 固定交易窗口条件 | 仅14:30-14:55例外 | 单笔最晚-5% | 只做主线 |

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
| 当前状态 | 50%标准进攻对象 |
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
| 50%标准进攻 | 正盈亏比 | 半导体 | 半导体 | 修复 | 富瀚微(300613) | 50% / 标准进攻 | 50%：只做合格对象，满足预演情境后执行，不满足回到0% |

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
                "| 当前状态 | 50%标准进攻对象 |",
                "| 当前状态 | 0%观察 |",
            )
            .replace(
                "| 09:50-10:10 | 市场底色、主线承接、唯一对象强弱 | 主线核心承接稳定且个股确认 | 买后用失效价和单笔-5%底线处理风险 | 核心执行窗口 |",
                "| 09:50-10:10 | 市场底色、主线承接、唯一对象强弱 | 无 | 无新增参与止损 | 继续0%观察 |",
            )
            .replace(
                "| 50%标准进攻 | 固定交易窗口条件 | 仅14:30-14:55例外 | 单笔最晚-5% | 只做主线 |",
                "| 0%不参与 | 固定交易窗口条件 | 仅14:30-14:55例外 | 单笔最晚-5% | 不新增参与 |",
            )
            .replace(
                "| 50%标准进攻 | 正盈亏比 | 半导体 | 半导体 | 修复 | 富瀚微(300613) | 50% / 标准进攻 | 50%：只做合格对象，满足预演情境后执行，不满足回到0% |",
                "| 0%不参与 | 负盈亏比 | 半导体 | 半导体 | 修复 | 暂无 | 0% / 不参与 | 0%：不新增参与，等待下一次预演条件重新成立 |",
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
            "| 当前状态 | 0%观察 |\n"
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

    def test_audit_accepts_derivation_chain_process_candidate_when_final_anchor_matches(self):
        markdown = GOOD_MARKDOWN.replace(
            "| 唯一对象 | 富瀚微(300613) |",
            "| 观察对象 | 豫能控股(001896) |",
        ).replace(
            "| 当前状态 | 50%标准进攻对象 |",
            "| 当前状态 | 0%条件观察 |",
        ).replace(
            "| 只看唯一对象 | 富瀚微(300613) | 主线确认 + 承接 + 09:50-10:10窗口 | 不做 |",
            "| 只看观察对象 | 豫能控股(001896) | 09:50-10:10窗口 | 不做 |",
        ).replace(
            "| 50%标准进攻 | 正盈亏比 | 半导体 | 半导体 | 修复 | 富瀚微(300613) | 50% / 标准进攻 | 50%：只做合格对象，满足预演情境后执行，不满足回到0% |",
            "| 0%不参与 | 负盈亏比 | 电力 | 电力 | 混沌 | 观察对象：豫能控股(001896) | 0% / 不参与 | 只观察，不新增参与 |",
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
            "| 当前状态 | 50%标准进攻对象 |",
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
            "| 50%标准进攻 | 正盈亏比 | 半导体 | 半导体 | 修复 | 富瀚微(300613) | 50% / 标准进攻 | 50%：只做合格对象，满足预演情境后执行，不满足回到0% |",
            "| 0%不参与 | 负盈亏比 | 电力 | 电力 | 混沌 | 观察对象：豫能控股(001896) | 0% / 不参与 | 只观察，不新增参与 |",
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
            "| 0%不参与 | 不确定时不值得主动参与 | 电力 | 电力 | 观察聚焦 | 观察对象：豫能控股(001896) | 0% / 不参与 | 盘前0%；只观察豫能控股(001896)，成立才保留观察；未出现执行资格前不新增参与；不满足继续0% |\n\n"
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
            "| 0%不参与 | 不确定时不值得主动参与 | 电力 | 电力 | 观察聚焦 | 观察对象：豫能控股(001896) | 0% / 不参与 | 盘前0%；只观察豫能控股(001896)，成立才保留观察；未出现执行资格前不新增参与；不满足继续0% |\n\n"
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
            "| 50%标准进攻 | 正盈亏比 | 半导体 | 半导体 | 修复 | 富瀚微(300613) | 50% / 标准进攻 | 50%：只做合格对象，满足预演情境后执行，不满足回到0% |",
            "| 0%不参与 | 负盈亏比 | 电力 | 电力 | 混沌 | 观察对象：豫能控股(001896) | 0% / 不参与 | 只观察，不新增参与 |",
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

    def test_audit_flags_final_object_identity_conflict_across_closing_action(self):
        markdown = (
            "# 2026-06-04 a股市场分析\n\n"
            "## 明日执行结论\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 明日仓位 | 条件满足才B档执行；不满足回到0% |\n"
            "| 明日执行对象 | 豫能控股(001896) |\n"
            "| 不满足条件 | 不参与 |\n\n"
            "## B档执行条件\n"
            "| 触发类型 | 必须满足 | 窗口 | 动作 |\n"
            "|----------|----------|------|------|\n"
            "| 低开承接型 | 靠近MA5；收回VWAP/0轴 | 09:50-10:10 | B档执行 |\n"
            "| 主动进攻型 | 大单净流入达标；VWAP上方保持 | 09:30-09:35 | B档执行 |\n\n"
            "## 七、最终结论\n"
            "| 明日结论 | 当前盈亏比 | 周期主线 | 当天主攻线 | 当前市场底色 | 重点对象 | 明日执行风格 | 一句话动作 |\n"
            "|----------|------------|----------|------------|--------------|--------------|--------------|------------|\n"
            "| 条件满足才B档执行；不满足回到0% | 不确定时不值得主动参与 | 电力 | 电力 | 观察聚焦 | 豫能控股(001896) | 50% / 标准进攻 | 条件满足才B档执行；不满足回到0% |\n\n"
            "### 明日行动清单\n"
            "| 项目 | 明日动作 |\n"
            "|------|----------|\n"
            "| 仓位 | 条件满足才B档执行；不满足回到0% |\n"
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
            "| 0%不参与 | 不确定时不值得主动参与 | 电力 | 电力 | 观察聚焦 | 观察对象：豫能控股(001896) | 0% / 不参与 | 只观察，不新增参与 |\n\n"
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
            "| 0%不参与 | 不确定时不值得主动参与 | 电力 | 电力 | 观察聚焦 | 观察对象：豫能控股(001896) | 0% / 不参与 | 只观察，不新增参与 |\n\n"
            "### 明日行动清单\n"
            "| 项目 | 明日动作 |\n"
            "|------|----------|\n"
            "| 最终对象 | 豫能控股(001896) |\n"
        )

        result = audit_report_markdown(markdown)

        self.assertIn("opening_final_object_empty_conflict", {finding["code"] for finding in result["findings"]})

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
            "| 0%不参与 | 不确定时不值得主动参与 | 电力 | 电力 | 观察聚焦 | 观察对象：豫能控股(001896) | 0% / 不参与 | 只观察，不新增参与 |\n\n"
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
            "| 0%不参与 | 不确定时不值得主动参与 | 电力 | 电力 | 观察聚焦 | 观察对象：豫能控股(001896) | 0% / 不参与 | 只观察，不新增参与 |\n\n"
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
            "| 0%不参与 | 不确定时不值得主动参与 | 电力 | 电力 | 观察聚焦 | 观察对象：豫能控股(001896) | 0% / 不参与 | 只观察，不新增参与 |\n\n"
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
            "| 明日仓位 | 条件满足才B档执行；不满足回到0% |\n"
            "| 明日执行对象 | 豫能控股(001896) |\n"
            "| 执行性质 | B档执行，约50%仓位 |\n"
            "| 不满足条件 | 不参与 |\n\n"
            "## 明日账户建议\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 明日动作 | 条件满足才B档执行 |\n"
        )

        result = audit_report_markdown(markdown)

        self.assertIn("b_level_conditions_missing", {finding["code"] for finding in result["findings"]})

    def test_audit_flags_execution_object_mismatch_between_front_and_audit_layer(self):
        markdown = (
            "# 2026-06-04 a股市场分析\n\n"
            "## 明日执行结论\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 明日执行对象 | 豫能控股(001896) |\n\n"
            "## B档执行条件\n"
            "| 触发类型 | 必须满足 | 窗口 | 动作 |\n"
            "|----------|----------|------|------|\n"
            "| 低开承接型 | 靠近MA5；收回VWAP/0轴 | 09:50-10:10 | B档执行 |\n"
            "| 主动进攻型 | 大单净流入达标；VWAP上方保持 | 09:30-09:35 | B档执行 |\n\n"
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
            "| 明日仓位 | 条件满足才B档执行；不满足回到0% |\n"
            "| 明日执行对象 | 豫能控股(001896) |\n\n"
            "## B档执行条件\n"
            "| 触发类型 | 必须满足 | 窗口 | 动作 |\n"
            "|----------|----------|------|------|\n"
            "| 低开承接型 | 靠近MA5；收回VWAP/0轴 | 09:50-10:10 | B档执行 |\n"
            "| 主动进攻型 | 大单净流入达标；VWAP上方保持 | 09:30-09:35 | B档执行 |\n\n"
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
            "| 明日仓位 | 条件满足才B档执行；不满足回到0% |\n"
            "| 明日执行对象 | 豫能控股(001896) |\n\n"
            "## B档执行条件\n"
            "| 触发类型 | 必须满足 | 窗口 | 动作 |\n"
            "|----------|----------|------|------|\n"
            "| 低开承接型 | 靠近MA5；收回VWAP/0轴 | 09:50-10:10 | B档执行 |\n"
            "| 主动进攻型 | 大单净流入达标；VWAP上方保持 | 09:30-09:35 | B档执行 |\n\n"
            "## 六、明日执行计划\n"
            "| 明日观察动作 | 标的 | 观察窗 | 条件 | 不满足怎么办 |\n"
            "|--------------|------|------|------|--------------|\n"
            "| 只看观察对象 | 豫能控股(001896) | 09:50-10:10 | 主线承接 | 不满足继续0% |\n\n"
            "## 七、最终结论\n"
            "| 明日结论 | 当前盈亏比 | 周期主线 | 当天主攻线 | 当前市场底色 | 重点对象 | 明日执行风格 | 一句话动作 |\n"
            "|----------|------------|----------|------------|--------------|--------------|--------------|------------|\n"
            "| 0%不参与 | 不确定时不值得主动参与 | 暂无 | 暂无 | 观察聚焦 | 观察对象：豫能控股(001896) | 0% / 不参与 | 盘前0%；只观察豫能控股，不能转成新增参与 |\n\n"
            "## 八、详细附录\n"
            "```text\n"
            "`-- 最终对象=豫能控股(001896) 身份=观察对象\n"
            "```\n"
        )

        result = audit_report_markdown(markdown)

        self.assertIn("front_execution_object_downgraded", {finding["code"] for finding in result["findings"]})

    def test_audit_allows_two_layer_conditional_execution_on_zero_position_front(self):
        markdown = (
            "# 2026-06-04 a股市场分析\n\n"
            "## 明日执行结论\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 明日仓位 | 条件满足才B档执行；不满足回到0% |\n"
            "| 明日执行对象 | 豫能控股(001896) |\n"
            "| 不满足条件 | 不参与 |\n\n"
            "## B档执行条件\n"
            "| 触发类型 | 必须满足 | 窗口 | 动作 |\n"
            "|----------|----------|------|------|\n"
            "| 低开承接型 | 靠近MA5；收回VWAP/0轴 | 09:50-10:10 | B档执行 |\n"
            "| 主动进攻型 | 大单净流入达标；VWAP上方保持 | 09:30-09:35 | B档执行 |\n\n"
            "## 七、最终结论\n"
            "| 明日结论 | 当前盈亏比 | 周期主线 | 当天主攻线 | 当前市场底色 | 唯一重点对象 | 明日执行风格 | 一句话动作 |\n"
            "|----------|------------|----------|------------|--------------|--------------|--------------|------------|\n"
            "| 0%不参与 | 不确定时不值得主动参与 | 暂无 | 暂无 | 观察聚焦 | 观察对象：豫能控股(001896) | 0% / 不参与 | 条件满足才B档执行；不满足回到0% |\n"
        )

        result = audit_report_markdown(markdown)

        self.assertNotIn("zero_position_decision_attribution_missing", {finding["code"] for finding in result["findings"]})

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

    def test_audit_flags_historical_timing_language_anywhere_in_report(self):
        bad = GOOD_MARKDOWN.replace("09:50-10:10窗口", "60" + "分钟确认", 1)

        result = audit_report_markdown(bad)

        self.assertIn("legacy_trading_time_wording", {finding["code"] for finding in result["findings"]})
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
            "| 2026-04-24 | 半导体 | 半导体 | 待累计 | 26414.92亿 | 待累计 | 待累计 | 数据不足 |",
            "| 2026-04-24 | 半导体 | 半导体 | missing_dependency | 26414.92亿 | 0.00% | 待累计 | 数据缺失 |",
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
                f"| 2026-04-{day:02d} | 半导体 | 半导体 | 3000.00亿 | 30000.00亿 | 10.0% | 待累计 | 继续观察 |"
                for day in range(1, 25)
            ]
            + [
                "| 2026-05-20 | 半导体 | 半导体 | 4050.00亿 | 29764.59亿 | 13.6% | +1.8pct | 继续观察 |"
            ]
        )
        complete_table = (
            "> 近25个交易日主线成交额占比趋势：当前13.6%，区间10.0%-13.6%，主线成交占比抬升，资金聚焦度走强。\n\n"
            "| 日期 | 周期主线 | 当天主攻线 | 主线成交额 | 两市成交额 | 占比 | 占比变化 | 解读 |\n"
            "|------|----------|------------|------------|------------|------|----------|------|\n"
            f"{complete_rows}"
        )
        appendix_table = (
            "##### 附录：主线成交额占比趋势\n"
            "| 日期 | 周期主线 | 当天主攻线 | 主线成交额 | 两市成交额 | 占比 | 占比变化 | 解读 |\n"
            "|------|----------|------------|------------|------------|------|----------|------|\n"
            "| 2026-05-20 | 半导体 | 半导体 | 4050.00亿 | 29764.59亿 | 13.6% | 待累计 | 继续观察 |"
        )
        bad = GOOD_MARKDOWN.replace(
            "| 2026-04-24 | 半导体 | 半导体 | 待累计 | 26414.92亿 | 待累计 | 待累计 | 数据不足 |",
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
                f"| 2026-04-{day:02d} | 半导体 | 半导体 | 3000.00亿 | 30000.00亿 | 10.0% | 待累计 | 继续观察 |"
                for day in range(1, 25)
            ]
            + [
                "| 2026-05-20 | 半导体 | 半导体 | 4050.00亿 | 29764.59亿 | 13.6% | +1.8pct | 继续观察 |"
            ]
        )
        complete_table = (
            "> 近25个交易日主线成交额占比趋势：当前13.6%，区间10.0%-13.6%，主线成交占比抬升，资金聚焦度走强。\n\n"
            "| 日期 | 周期主线 | 当天主攻线 | 主线成交额 | 两市成交额 | 占比 | 占比变化 | 解读 |\n"
            "|------|----------|------------|------------|------------|------|----------|------|\n"
            f"{complete_rows}"
        )
        bad_t52_rows = "\n".join(
            [
                f"| 2026-04-{day:02d} | 半导体 | 半导体 | 3000.00亿 | 30000.00亿 | 10.0% | 待累计 | 继续观察 |"
                for day in range(1, 25)
            ]
            + [
                "| 2026-05-20 | 暂无确认主线 | 暂无确认主攻线 | 4050.00亿 | 29764.59亿 | 13.6% | +1.8pct | 候选方向成交额占比可记录，但未确认主攻线 |"
            ]
        )
        appendix_table = (
            "##### 附录：主线成交额占比趋势\n"
            "> 近25个交易日主线成交额占比趋势：当前13.6%，区间10.0%-13.6%，主线成交占比抬升，资金聚焦度走强。\n\n"
            "**T-052**\n"
            "| 日期 | 周期主线 | 当天主攻线 | 主线成交额 | 两市成交额 | 占比 | 占比变化 | 解读 |\n"
            "|------|----------|------------|------------|------------|------|----------|------|\n"
            f"{bad_t52_rows}"
        )
        bad = GOOD_MARKDOWN.replace(
            "| 2026-04-24 | 半导体 | 半导体 | 待累计 | 26414.92亿 | 待累计 | 待累计 | 数据不足 |",
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
                "| 50%标准进攻 | 正盈亏比 | 半导体 | 半导体 | 修复 | 富瀚微(300613) | 50% / 标准进攻 | 50%：只做合格对象，满足预演情境后执行，不满足回到0% |",
                "| 0%不参与 | 负盈亏比 | 半导体 | 半导体 | 收缩防守 | 暂无 | 0% / 不参与 | 0%：没有合格标的就不参与 |",
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
                "| 50%标准进攻 | 正盈亏比 | 半导体 | 半导体 | 修复 | 富瀚微(300613) | 50% / 标准进攻 | 50%：只做合格对象，满足预演情境后执行，不满足回到0% |",
                "| 0%不参与 | 负盈亏比 | 半导体 | 半导体 | 收缩防守 | 暂无 | 0% / 不参与 | 0%：没有合格标的就不参与 |",
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
                "| 50%标准进攻 | 正盈亏比 | 半导体 | 半导体 | 修复 | 富瀚微(300613) | 50% / 标准进攻 | 50%：只做合格对象，满足预演情境后执行，不满足回到0% |",
                "| 0%不参与 | 负盈亏比 | 半导体 | 半导体 | 收缩防守 | 暂无 | 0% / 不参与 | 0%：没有合格标的就不参与 |",
            )
            .replace(
                "| 10:00左右买 | 只看周期主线核心，且必须有承接 | 竞价表态、参与窗口与结构确认共同成立 | 买后用30分钟结构止损 | 50%/100%或0% |",
                "| 10:00左右观察 | 暂无唯一对象，不做新增参与 | 无 | 无新增参与止损 | 不做 |",
            )
            .replace(
                "| 尾盘 | 只判断是否量化电风扇行情 | 仅例外 | 非电风扇不尾盘开新仓 | 例外 |",
                "| 尾盘 | 只判断是否量化电风扇行情 | 无 | 非电风扇不尾盘新增参与 | 例外，不是常规 |",
            )
            + "\n| 竞价表态 + 回封观察 | 0%观察 | 交易逻辑确认 / 竞价表态 / 回封/打板 |\n"
        )

        result = audit_report_markdown(bad)

        self.assertIn(
            "zero_position_legacy_tomorrow_wording",
            {finding["code"] for finding in result["findings"]},
        )
        self.assertFalse(result["passed"])

    def test_audit_flags_unique_focus_mismatch_between_plan_and_final_summary(self):
        bad = GOOD_MARKDOWN.replace(
            "| 50%标准进攻 | 正盈亏比 | 半导体 | 半导体 | 修复 | 富瀚微(300613) | 50% / 标准进攻 | 50%：只做合格对象，满足预演情境后执行，不满足回到0% |",
            "| 50%标准进攻 | 正盈亏比 | 半导体 | 半导体 | 修复 | 中嘉博创(000889) | 50% / 标准进攻 | 50%：只做合格对象，满足预演情境后执行，不满足回到0% |",
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
                "| 0%不参与 | 负盈亏比 | 半导体 | 半导体 | 修复 | 暂无 | 0% / 不参与 | 0%：不新增参与，等待下一次预演条件重新成立 |",
                "| 0%不参与 | 负盈亏比 | 半导体 | 半导体 | 修复 | 条件观察：300613 富瀚微（半导体） | 0% / 不参与 | 盘前0%；09:50-10:10窗口主线确认 + 承接 + 观察窗口同时成立，才评估50%标准进攻；不满足继续0% |",
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
            + "| ⏳ 确认后执行预案 | 富瀚微 | 300613 | 09:50-10:10站上确认价，且板块承接不塌，固定交易窗口内条件成立后才评估50%标准进攻 | 失效价 |\n"
            + "\n**明天仓位怎么放**:\n"
            + "- **进攻仓位三态**: 50%标准进攻预演\n"
            + "- **明天仓位放多少**: 条件50%；盘前不抢跑，固定交易窗口条件满足后执行，不满足回到0%\n"
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
                "| 0%不参与 | 负盈亏比 | 半导体 | 半导体 | 修复 | 暂无 | 0% / 不参与 | 0%：不新增参与，等待下一次预演条件重新成立 |",
                "| 0%不参与 | 负盈亏比 | 半导体 | 半导体 | 修复 | 观察对象：300613 富瀚微（半导体） | 0% / 不参与 | 盘前0%；只观察300613 富瀚微（半导体），成立才保留观察，不能转成新增参与；不满足继续0% |",
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
            "| 当前状态 | 0%观察 |\n"
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
            "| 0%不参与 | 负盈亏比 | 半导体 | 半导体 | 修复 | 暂无 | 0% / 不参与 | 0%：不新增参与，等待下一次预演条件重新成立 |",
            "| 0%不参与 | 负盈亏比 | 半导体 | 半导体 | 修复 | 观察对象：富瀚微(300613) | 0% / 不参与 | 盘前0%；只观察富瀚微(300613)，条件成立才保留观察，不能转成新增参与；不满足继续0% |",
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
            "| 0%不参与 | 负盈亏比 | 半导体 | 半导体 | 修复 | 暂无 | 0% / 不参与 | 0%：不新增参与，等待下一次预演条件重新成立 |",
            "| 0%不参与 | 负盈亏比 | 半导体 | 半导体 | 修复 | 观察对象：富瀚微(300613) | 0% / 不参与 | 盘前0%；只观察富瀚微(300613)，条件成立才保留观察，不能转成新增参与；不满足继续0% |",
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
            "| 当前状态 | 0%观察 |\n"
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
            "| 0%不参与 | 负盈亏比 | 半导体 | 半导体 | 修复 | 暂无 | 0% / 不参与 | 0%：不新增参与，等待下一次预演条件重新成立 |",
            "| 0%不参与 | 负盈亏比 | 半导体 | 半导体 | 修复 | 观察对象：富瀚微(300613) | 0% / 不参与 | 盘前0%；只观察富瀚微(300613)，条件成立才保留观察，不能转成新增参与；不满足继续0% |",
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
                "| 0%不参与 | 负盈亏比 | 半导体 | 半导体 | 修复 | 暂无 | 0% / 不参与 | 0%：不新增参与，等待下一次预演条件重新成立 |",
                "| 0%不参与 | 负盈亏比 | 半导体 | 半导体 | 修复 | 观察对象：600726 华电能源（电力） | 0% / 不参与 | 盘前0%；只观察600726 华电能源（电力），成立才保留观察，不能转成新增参与；不满足继续0% |",
            )
            + "\n**观察优先锚点**: 京能电力(600578)\n"
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
            "| 50%标准进攻 | 正盈亏比 | 半导体 | 半导体 | 修复 | 富瀚微(300613) | 50% / 标准进攻 | 50%：只做合格对象，满足预演情境后执行，不满足回到0% |",
            "| 50%标准进攻 | 正盈亏比 | 半导体 | 半导体 | 修复 | 暂无 | 50% / 标准进攻 | 50%：只做合格对象，满足预演情境后执行，不满足回到0% |",
        )

        result = audit_report_markdown(report)

        self.assertNotIn("unique_focus_contradiction", {finding["code"] for finding in result["findings"]})
        self.assertTrue(result["passed"], result["findings"])

    def test_audit_flags_empty_unique_focus_with_concrete_buy_candidate(self):
        bad = GOOD_MARKDOWN.replace(
            "| 只看唯一对象 | 富瀚微(300613) | 主线确认 + 承接 + 09:50-10:10窗口 | 不做 |",
            "| 只看唯一对象 | 暂无 | 主线确认 + 承接 + 09:50-10:10窗口未同时满足 | 不做 |",
        ).replace(
            "| 当前状态 | 50%标准进攻对象 |",
            "| 当前状态 | 富瀚微(300613) 唯一买入，09:50-10:10窗口 |",
        ).replace(
            "| 50%标准进攻 | 正盈亏比 | 半导体 | 半导体 | 修复 | 富瀚微(300613) | 50% / 标准进攻 | 50%：只做合格对象，满足预演情境后执行，不满足回到0% |",
            "| 50%标准进攻 | 正盈亏比 | 半导体 | 半导体 | 修复 | 暂无 | 50% / 标准进攻 | 50%：只做合格对象，满足预演情境后执行，不满足回到0% |",
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
            "| 50%标准进攻 | 固定交易窗口条件 | 仅14:30-14:55例外 | 单笔最晚-5% | 只做主线 |",
            "| 0%不参与 | 固定交易窗口条件 | 仅14:30-14:55例外 | 单笔最晚-5% | 不新增参与 |",
        ).replace(
            "| 50%标准进攻 | 正盈亏比 | 半导体 | 半导体 | 修复 | 富瀚微(300613) | 50% / 标准进攻 | 50%：只做合格对象，满足预演情境后执行，不满足回到0% |",
            "| 0%不参与 | 负盈亏比 | 半导体 | 半导体 | 修复 | 暂无 | 0% / 不参与 | 0%：不新增参与，等待下一次预演条件重新成立 |",
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
            "| 明日仓位 | 50%标准进攻 |\n"
            "| 明日动作 | 只看T0主对象，条件满足才新开一手 |\n"
            "| T0主对象 | 华电能源(600726)：固定交易窗口条件 |\n"
            "| T0备用 | 暂无 |\n"
            "| 新增参与上限 | 1 |",
        )

        result = audit_report_markdown(good)

        self.assertNotIn("t0_object_without_holding_context", {finding["code"] for finding in result["findings"]})
        self.assertTrue(result["passed"])

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
            "| 明日仓位 | 50%标准进攻 |\n"
            "| 明日动作 | 先处理旧仓，买华天科技(002185)；固定交易窗口条件成立才参与，不满足回到0% |",
        )

        result = audit_report_markdown(bad)

        self.assertIn("opportunity_comparison_missing", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_flags_positive_participation_with_incomplete_opportunity_risk(self):
        bad = GOOD_MARKDOWN.replace(
            "## 六、明日执行计划",
            "## 旧仓与新机会风险价格对比\n"
            "| 对象 | 身份 | 当前/观察价 | MA5风险 | MA10风险 | VWAP风险 | 作废价 | 上方空间 | 盈亏比 | 账户结论 |\n"
            "|------|------|-------------|---------|----------|----------|--------|----------|--------|----------|\n"
            "| 华电辽能(600396) | old_position | - | - | - | - | - | - | - | repair_once |\n"
            "| 华天科技(002185) | sector_anchor | 19.16 | 18.20 / -5.01% | 17.80 / -6.99% | - | - | - | 待计算 | 只保留观察，等风险价格补齐 |\n\n"
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
            "| ⏳ 确认后执行预案 | 江海股份 | 002484 | 09:50-10:10站上74.07后再评估50%标准进攻 | 70.37 |\n",
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

    def test_audit_flags_duplicate_front_page_long_table_cell(self):
        bad = GOOD_MARKDOWN.replace(
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

        result = audit_report_markdown(bad)

        self.assertIn("front_page_duplicate_long_cell", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

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


if __name__ == "__main__":
    unittest.main()
