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

    def test_renderer_outputs_candidate_trace_tables(self):
        panel = build_daily_quality_decision_panel(market_emotion_label="主线活跃")
        contracts = [
            evaluate_candidate_quality_sample_contract(
                {
                    "name": "华天科技",
                    "code": "002185",
                    "tier": "T0",
                    "source_pools": ["主线核心候选"],
                    "mainline": "半导体",
                    "sector": "半导体",
                    "market_fit": "部分满足",
                    "mainline_fit": "满足",
                    "stock_structure_fit": "部分满足",
                    "latest_price": 13.2,
                    "available_cash": 10000,
                    "final_action": "09:50-10:10确认，不满足继续不参与",
                    "failure_condition": "主线回落或放量不承接",
                }
            ),
            evaluate_candidate_quality_sample_contract(
                {
                    "name": "步步高",
                    "code": "002251",
                    "tier": "T3",
                    "source_pools": ["异动线索"],
                    "mainline": "消费",
                    "sector": "消费",
                    "market_fit": "未满足",
                    "mainline_fit": "未满足",
                    "stock_structure_fit": "部分满足",
                    "final_action": "不参与，只记录观察线索",
                }
            ),
        ]

        markdown = render_candidate_quality_section(panel, contracts, render_trace_tables=True)

        self.assertIn("### 候选选股轨迹", markdown)
        self.assertIn("| 层级 | 候选 | 主线/板块 | 板块锚反推 | 为什么进入这一层 | 卡点 | 明日动作 |", markdown)
        self.assertIn("| 观察层 | 华天科技(002185) | 半导体 |", markdown)
        self.assertNotIn("| T3 | 步步高(002251) | 消费 | 为什么进入这一层 |", markdown)
        self.assertIn("### 候选选股轨迹明细", markdown)
        self.assertIn("| 层级 | 候选 | 来源池 | 主线/板块 | 板块锚反推 | 关键输入 | 满足条件 | 未满足/缺失 | 分支结果 | 明日动作 | 失效条件 |", markdown)
        self.assertIn("| 观察层 | 步步高(002251) | 异动线索 | 消费 |", markdown)

    def test_renderer_marks_process_samples_when_final_target_is_empty(self):
        panel = build_daily_quality_decision_panel(
            market_emotion_label="0%不参与",
            daily_new_entry_limit=0,
            primary_buy_candidate={"name": "明新旭腾", "code": "605068"},
            backup_candidate={"name": "华天酒店", "code": "000428"},
        )
        contracts = [
            evaluate_candidate_quality_sample_contract(
                {
                    "name": "明新旭腾",
                    "code": "605068",
                    "tier": "T1",
                    "source_pools": ["watch_anchor"],
                    "mainline": "国产芯片替代",
                    "sector": "汽车配件",
                    "market_fit": "未满足",
                    "mainline_fit": "未满足",
                    "stock_structure_fit": "数据缺失",
                    "candidate_role": "板块锚",
                    "sector_anchor": "明新旭腾(605068)",
                    "relationship_to_anchor": "候选本身就是板块锚",
                    "anchor_reversal_decision": "可作为主对象",
                    "anchor_reversal_reason": "分歧后资金优先回看",
                    "workflow_path": ["N5", "N6", "N7"],
                    "process_rejection_reason": "价格行为未通过确认；未证明来自板块资金方向",
                    "latest_price": 18.72,
                    "participation_window": "09:50-10:10",
                    "failure_condition": "预估17.78 / 最晚17.78",
                    "final_action": "09:50-10:10确认后可作为主对象",
                }
            )
        ]

        markdown = render_candidate_quality_section(
            panel,
            contracts,
            table_fields=["候选", "账户状态", "动作上限", "新开仓动作"],
            render_trace_tables=True,
            final_target_empty=True,
        )

        self.assertIn("当前最终对象为空；下表只回放筛选过程", markdown)
        self.assertIn("| 主买对象 | 无 |", markdown)
        self.assertIn("| 补位对象 | 无 |", markdown)
        self.assertIn("| 候选 | 板块 | 历史来源 | 筛选路径 | 淘汰原因 | 过程处理 |", markdown)
        self.assertIn(
            "| 明新旭腾(605068) | 汽车配件 | watch_anchor | N5 -> N6 -> N7 | 价格行为未通过确认；未证明来自板块资金方向 | 只作过程回放，不新增参与 |",
            markdown,
        )
        self.assertNotIn("狙击手最终标的路径图", markdown)
        self.assertNotIn("候选选股轨迹", markdown)
        self.assertNotIn("单票展开", markdown)
        self.assertNotIn("板块锚", markdown)
        self.assertNotIn("可作为主对象", markdown)
        self.assertNotIn("09:50-10:10", markdown)
        self.assertNotIn("18.72", markdown)
        self.assertNotIn("17.78", markdown)

    def test_renderer_outputs_sniper_ascii_selection_graph(self):
        panel = build_daily_quality_decision_panel(market_emotion_label="主线活跃")
        contracts = [
            evaluate_candidate_quality_sample_contract(
                {
                    "name": "大唐发电",
                    "code": "601991",
                    "tier": "T0",
                    "source_pools": ["涨停池", "成交额排名"],
                    "mainline": "电力",
                    "sector": "电力",
                    "quality_role": "主买对象",
                    "sector_anchor": "大唐发电(601991)",
                    "candidate_role": "板块锚",
                    "relationship_to_anchor": "自身就是资金回流锚",
                    "anchor_reversal_decision": "可作为主对象",
                    "anchor_reversal_reason": "板块锚承接和MA5入/MA7清/MA5T路径明确",
                    "final_action": "09:50-10:10确认，条件不满足继续0%",
                }
            ),
            evaluate_candidate_quality_sample_contract(
                {
                    "name": "华电辽能",
                    "code": "600396",
                    "tier": "T1",
                    "source_pools": ["成交额排名"],
                    "mainline": "电力",
                    "sector": "电力",
                    "sector_anchor": "大唐发电(601991)",
                    "candidate_role": "大容量中军",
                    "relationship_to_anchor": "跟随板块锚承接，承担容量确认",
                    "why_not_anchor": "大唐发电短线加速过热，华电辽能承接更适合补位",
                    "anchor_reversal_decision": "可作为补位",
                    "anchor_reversal_reason": "容量承接可作为备选比较",
                    "final_action": "只在09:50-10:10承接确认后补位",
                }
            ),
            evaluate_candidate_quality_sample_contract(
                {
                    "name": "京能电力",
                    "code": "600578",
                    "tier": "T1",
                    "source_pools": ["涨停池"],
                    "mainline": "电力",
                    "sector": "电力",
                    "sector_anchor": "大唐发电(601991)",
                    "candidate_role": "套利工具",
                    "relationship_to_anchor": "被大唐发电(601991)带动，只能反馈板块强度",
                    "why_not_anchor": "不能证明比大唐发电更值得参与",
                    "anchor_reversal_decision": "降级观察",
                    "anchor_reversal_reason": "套利工具不能替代板块锚",
                    "final_action": "只观察，不新增参与",
                }
            ),
        ]

        markdown = render_candidate_quality_section(panel, contracts, render_trace_tables=True)

        self.assertIn("### 狙击手最终标的路径图", markdown)
        self.assertIn("```text", markdown)
        self.assertIn("原始候选池", markdown)
        self.assertIn("+-- 主线/板块: 电力", markdown)
        self.assertIn("+-- 板块锚: 大唐发电(601991)", markdown)
        self.assertIn("+-- 明日主买对象: 大唐发电(601991)", markdown)
        self.assertIn("+-- 明日补位对象: 华电辽能(600396)", markdown)
        self.assertIn("+-- 观察/不参与: 京能电力(600578)", markdown)
        self.assertIn("+-- 身份: 套利工具", markdown)
        self.assertIn("+-- 偏差/卡点: 不能证明比大唐发电更值得参与", markdown)
        self.assertIn("+-- 处理: 降级观察", markdown)
        self.assertLess(markdown.index("### 狙击手最终标的路径图"), markdown.index("### 候选选股轨迹"))

    def test_renderer_does_not_label_unmet_anchor_trace_as_main_buy_in_graph(self):
        panel = build_daily_quality_decision_panel(market_emotion_label="暂不跟随")
        contracts = [
            evaluate_candidate_quality_sample_contract(
                {
                    "name": "工业富联",
                    "code": "601138",
                    "tier": "T0",
                    "mainline": "通信设备",
                    "sector": "AI算力基础设施",
                    "sector_anchor": "工业富联(601138)",
                    "candidate_role": "板块锚",
                    "relationship_to_anchor": "资金回流优先看板块锚，候选本身就是板块锚",
                    "anchor_reversal_decision": "可作为主对象",
                    "anchor_reversal_reason": "候选就是板块锚，分歧后资金优先回看",
                    "market_fit": "未满足",
                    "mainline_fit": "未满足",
                    "stock_structure_fit": "部分满足",
                    "final_action": "条件未满足，继续不参与",
                }
            )
        ]

        markdown = render_candidate_quality_section(panel, contracts, render_trace_tables=True)

        self.assertIn("+-- 观察/不参与: 工业富联(601138)", markdown)
        self.assertNotIn("+-- 明日主买对象: 工业富联(601138)", markdown)

    def test_renderer_outputs_eliminated_summary(self):
        panel = build_daily_quality_decision_panel(market_emotion_label="主线活跃")

        markdown = render_candidate_quality_section(
            panel,
            [],
            eliminated_summary=[
                {"reason": "主线不匹配", "count": 2, "representatives": ["大众公用", "红星发展"], "treatment": "保留观察，不进入动作分层"}
            ],
            render_trace_tables=True,
        )

        self.assertIn("### 未进入分层原因统计", markdown)
        self.assertIn("| 主线不匹配 | 2 | 大众公用、红星发展 | 保留观察，不进入动作分层 |", markdown)


if __name__ == "__main__":
    unittest.main()
