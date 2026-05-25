import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.candidate_quality_renderer import render_candidate_quality_section
from selection.candidate_quality_contracts import (
    build_daily_quality_decision_panel,
    evaluate_candidate_quality_sample_contract,
)


def _m(*parts):
    return "".join(parts)


class CandidateQualityRendererTest(unittest.TestCase):
    def test_renders_decision_panel_candidate_table_and_single_stock_details(self):
        panel = build_daily_quality_decision_panel(
            market_emotion_label="分歧轮动",
            account_attention_load="高",
            holding_priority_action="先处理汇源通信风险仓",
            daily_new_entry_limit=0,
            primary_buy_candidate=None,
            backup_candidate={"name": "晶方科技", "code": "603005"},
            forbidden_actions=["亏损后补仓", "计划外追高"],
            ignored_noise_items=["外盘上涨但A股未确认"],
        )
        contracts = [
            evaluate_candidate_quality_sample_contract(
                {
                    "name": "晶方科技",
                    "code": "603005",
                    "selection_quality": "高",
                    "entry_cost_state": "高成本",
                    "is_core": True,
                    "cost_flags": ["远离MA/VWAP"],
                    "current_position_shares": 100,
                    "sellable_shares": 0,
                    "locked_shares": 100,
                }
            ),
            evaluate_candidate_quality_sample_contract(
                {
                    "name": "汇源通信",
                    "code": "000586",
                    "selection_quality": "低",
                    "entry_cost_state": "低成本",
                    "risk_flags": ["风险信息缺失"],
                    "cost_flags": ["靠近VWAP"],
                    "current_position_shares": 500,
                    "sellable_shares": 100,
                    "locked_shares": 400,
                }
            ),
        ]

        markdown = render_candidate_quality_section(panel, contracts)

        self.assertIn("## 候选质量与动作分层", markdown)
        self.assertIn("### 今日总决策面板", markdown)
        self.assertIn("| 字段 | 内容 |", markdown)
        self.assertIn("| 市场情绪状态 | 分歧轮动 |", markdown)
        self.assertIn("| 今日新增上限 | 0 |", markdown)
        self.assertIn("| 补位对象 | 晶方科技(603005) |", markdown)
        self.assertIn("### 候选主表", markdown)
        self.assertIn("| 候选 | 当前持仓 | 可卖数量 | 不可卖数量 | 仓位性质 | 账户状态 | 计划仓位档 | 实际仓位 | 仓位偏离 | 周期身份 | 选股质量 | 买点质量 | 风险项 | 成本项 | 动作上限 | 持仓动作 | 新开仓动作 | 恢复条件 | 取关条件 | 最晚复核 |", markdown)
        self.assertIn("| 晶方科技(603005) | 100 | 0 | 100 | 已有仓 | 实际可买 |  |  |  |  | 高 | 不舒服 |  | 成本项：远离MA/VWAP | 核心观察 | 已有仓按失效线处理，可卖0，不可卖100 | 不追高，等回踩确认 |", markdown)
        self.assertIn("| 汇源通信(000586) | 500 | 100 | 400 | 已有仓 | 实际可买 |  |  |  |  | 低 | 看似便宜 | 风险项：风险信息缺失 | 成本项：靠近VWAP | 不参与 |", markdown)
        self.assertIn("### 单票展开", markdown)
        self.assertIn("#### 晶方科技(603005)", markdown)
        self.assertIn("- 选股质量：高", markdown)
        self.assertIn("- 买点质量：不舒服", markdown)
        self.assertIn("- 账户状态：实际可买", markdown)
        self.assertIn("- 计划仓位档：", markdown)
        self.assertIn("- 实际仓位：", markdown)
        self.assertIn("- 仓位偏离：", markdown)
        self.assertIn("- 新开仓动作：不追高，等回踩确认", markdown)
        self.assertIn("#### 汇源通信(000586)", markdown)
        self.assertIn("- 风险项：风险信息缺失", markdown)
        self.assertIn("- 成本项：靠近VWAP", markdown)
        self.assertIn("- 账户状态：实际可买", markdown)
        self.assertNotIn("- 风险项：风险项：风险信息缺失", markdown)
        self.assertNotIn("- 成本项：成本项：靠近VWAP", markdown)
        self.assertIn("- 动作上限：不参与", markdown)
        self.assertNotIn(_m("ga", "te"), markdown.lower())
        self.assertNotIn(_m("状态", "机"), markdown)

    def test_empty_candidates_still_renders_panel_and_empty_table_note(self):
        panel = build_daily_quality_decision_panel(
            market_emotion_label="退潮踩踏",
            account_attention_load="高",
            holding_priority_action="先处理风险仓",
            daily_new_entry_limit=0,
        )

        markdown = render_candidate_quality_section(panel, [])

        self.assertIn("## 候选质量与动作分层", markdown)
        self.assertIn("| 市场情绪状态 | 退潮踩踏 |", markdown)
        self.assertIn("暂无候选进入动作分层。", markdown)

    def test_renderer_can_lower_heading_level_when_nested_in_action_plan(self):
        panel = build_daily_quality_decision_panel(market_emotion_label="分歧轮动")
        contracts = [
            evaluate_candidate_quality_sample_contract(
                {
                    "name": "晶方科技",
                    "code": "603005",
                    "selection_quality": "高",
                    "entry_cost_state": "高成本",
                    "is_core": True,
                }
            )
        ]

        markdown = render_candidate_quality_section(panel, contracts, heading_level=5)

        self.assertIn("##### 候选质量与动作分层", markdown)
        self.assertIn("###### 今日总决策面板", markdown)
        self.assertIn("###### 候选主表", markdown)
        self.assertIn("###### 单票展开", markdown)
        self.assertIn("**晶方科技(603005)**", markdown)
        self.assertNotIn("#######", markdown)
        self.assertNotIn("\n## 候选质量与动作分层", markdown)

    def test_renderer_can_use_compact_candidate_table_when_nested(self):
        panel = build_daily_quality_decision_panel(market_emotion_label="分歧轮动")
        contracts = [
            evaluate_candidate_quality_sample_contract(
                {
                    "name": "汇源通信",
                    "code": "000586",
                    "selection_quality": "低",
                    "entry_cost_state": "低成本",
                    "risk_flags": ["风险信息缺失"],
                    "cost_flags": ["靠近VWAP"],
                    "current_position_shares": 500,
                    "sellable_shares": 100,
                    "locked_shares": 400,
                }
            )
        ]

        markdown = render_candidate_quality_section(
            panel,
            contracts,
            table_fields=["候选", "当前持仓", "可卖数量", "选股质量", "买点质量", "动作上限", "新开仓动作"],
        )

        self.assertIn("| 候选 | 当前持仓 | 可卖数量 | 选股质量 | 买点质量 | 动作上限 | 新开仓动作 |", markdown)
        self.assertIn("| 汇源通信(000586) | 500 | 100 | 低 | 看似便宜 | 不参与 |", markdown)
        self.assertNotIn("| 不可卖数量 |", markdown)
        self.assertNotIn("| 仓位性质 |", markdown)

    def test_renderer_keeps_market_core_visible_when_actual_unbuyable(self):
        panel = build_daily_quality_decision_panel(market_emotion_label="主线活跃")
        contracts = [
            evaluate_candidate_quality_sample_contract(
                {
                    "name": "宏和科技",
                    "code": "603256",
                    "cycle_identity": "市场核心",
                    "quality_role": "主买对象",
                    "selection_quality": "高",
                    "latest_price": 172.87,
                    "available_cash": 10000,
                }
            )
        ]

        markdown = render_candidate_quality_section(panel, contracts)

        self.assertIn("宏和科技(603256)", markdown)
        self.assertIn("| 宏和科技(603256) | 0 | 0 | 0 | 无仓 | 实际不可买 |  |  |  | 市场核心 |", markdown)
        self.assertIn("- 账户状态：实际不可买", markdown)
        self.assertIn("- 新开仓动作：账户条件不适配，只观察强度，不参与", markdown)


if __name__ == "__main__":
    unittest.main()
