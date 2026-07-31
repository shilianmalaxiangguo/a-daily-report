import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.selection_workflow import (
    _action_text,
    _apply_premarket_review_position,
    _position_pct,
    build_selection_workflow,
    candidate_limit_down_risk_review_reason,
    render_selection_workflow_mermaid,
)


def _complete_local_trend_sector_proof(direction):
    return {
        "direction": direction,
        "cross_day_continuity": True,
        "divergence_acceptance": True,
        "internal_expansion": True,
        "competition_comparison": True,
        "competition_state": "单主线聚焦",
    }


def _qualified_sector_context(*, direction="电力", candidate_sector=None, **market_fields):
    context = {
        "market_state_snapshot": {
            "market_state": "收缩防守",
            "execution_bias": "avoid",
            "pulse_stage": "退潮",
            "operation_state": "观察态",
        },
        "mainline_name": direction,
        "local_trend_sector_proof": _complete_local_trend_sector_proof(direction),
        "sector_derived_candidates": [
            {
                "name": "豫能控股",
                "code": "001896",
                "sector": candidate_sector or direction,
                "anchor_reversal_decision": "可作为主对象",
                "candidate_role": "板块锚",
                "sector_derivation_evidence": "跨日持续、分歧承接、内部扩散并完成竞争方向对照",
                "participation_window": "09:50-10:10",
                "fallback_state": "条件不满足回到0%不参与",
            }
        ],
    }
    context.update(market_fields)
    return context


class SelectionWorkflowTest(unittest.TestCase):
    def test_position_decision_rejects_non_tier_plans_before_selection(self):
        for position_pct in (1, 33, 39, 40, 60, 61, 75, 99, 150):
            with self.subTest(position_pct=position_pct):
                self.assertEqual(_position_pct({"target_position_pct": position_pct}), 0)
        for position_pct, expected in ((0, 0), (50, 50), (100, 100)):
            with self.subTest(position_pct=position_pct):
                self.assertEqual(
                    _position_pct({"target_position_pct": position_pct}),
                    expected,
                )

    def test_premarket_position_cap_keeps_final_position_on_an_exact_tier(self):
        for cap_pct, expected in ((0, 0), (40, 0), (50, 50), (60, 50), (75, 50), (100, 100)):
            with self.subTest(cap_pct=cap_pct):
                position_pct = _apply_premarket_review_position(
                    100,
                    {"position_cap_pct": cap_pct},
                )
                self.assertEqual(position_pct, expected)
                self.assertEqual(
                    _action_text(position_pct),
                    {0: "0%不参与", 50: "50%条件执行", 100: "100%核心进攻"}[expected],
                )
        for position_pct in (33, 40, 60, 75):
            with self.subTest(position_pct=position_pct):
                self.assertEqual(_action_text(position_pct), "0%不参与")

    def test_weak_market_with_complete_local_trend_allows_b1_only(self):
        workflow = build_selection_workflow(
            target_date="2026-07-27",
            execution_stage_context=_qualified_sector_context(),
            position_decision={"target_position_pct": 100},
        )

        self.assertEqual(workflow["final"]["execution_object"]["code"], "001896")
        self.assertEqual(workflow["final"]["position_pct"], 50)
        self.assertTrue(workflow["final"]["b1_only"])
        self.assertFalse(workflow["final"]["b2_allowed"])
        self.assertEqual(workflow["market_participation_limit"]["max_position_pct"], 50)

    def test_stale_sector_fact_date_cannot_create_target_day_participation(self):
        context = _qualified_sector_context()
        context["source_date"] = "2026-07-26"
        context["sector_derived_candidates"][0]["source_date"] = "2026-07-26"

        workflow = build_selection_workflow(
            target_date="2026-07-27",
            execution_stage_context=context,
            position_decision={"target_position_pct": 100},
        )

        self.assertEqual(workflow["final"]["execution_object"], {})
        self.assertEqual(workflow["final"]["position_pct"], 0)
        self.assertEqual(workflow["data_completeness"]["status"], "failed")
        self.assertIn("板块事实日期", workflow["data_completeness"]["missing_fields"])
        self.assertEqual(workflow["source_dates"]["report_date"], "2026-07-27")
        self.assertEqual(workflow["source_dates"]["sector_source_date"], "2026-07-26")

    def test_broad_market_confirmation_with_complete_local_trend_allows_b2(self):
        workflow = build_selection_workflow(
            target_date="2026-07-27",
            execution_stage_context=_qualified_sector_context(
                broad_market_confirmation=True,
            ),
            position_decision={"target_position_pct": 100},
        )

        self.assertEqual(workflow["final"]["position_pct"], 100)
        self.assertFalse(workflow["final"]["b1_only"])
        self.assertTrue(workflow["final"]["b2_allowed"])

    def test_weak_market_without_complete_local_trend_stays_out(self):
        context = _qualified_sector_context()
        context["local_trend_sector_proof"]["competition_comparison"] = False

        workflow = build_selection_workflow(
            target_date="2026-07-27",
            execution_stage_context=context,
            position_decision={"target_position_pct": 100},
        )

        self.assertEqual(workflow["final"]["execution_object"], {})
        self.assertEqual(workflow["final"]["position_pct"], 0)
        self.assertIn("竞争方向对照", workflow["local_trend_sector_proof"]["evidence_gaps"])

    def test_systemic_risk_blocks_even_complete_local_trend(self):
        workflow = build_selection_workflow(
            target_date="2026-07-27",
            execution_stage_context=_qualified_sector_context(
                systemic_risk_active=True,
            ),
            position_decision={"target_position_pct": 100},
        )

        self.assertEqual(workflow["final"]["execution_object"], {})
        self.assertEqual(workflow["final"]["position_pct"], 0)
        self.assertTrue(workflow["market_participation_limit"]["systemic_risk"])

    def test_candidate_outside_proven_direction_stays_out(self):
        workflow = build_selection_workflow(
            target_date="2026-07-27",
            execution_stage_context=_qualified_sector_context(candidate_sector="半导体"),
            position_decision={"target_position_pct": 50},
        )

        self.assertEqual(workflow["final"]["execution_object"], {})
        self.assertEqual(workflow["final"]["position_pct"], 0)
        self.assertIn("个股与已证明方向不匹配", workflow["final"]["failure_conditions"])

    def test_builds_required_nodes_and_final_source(self):
        workflow = build_selection_workflow(
            target_date="2026-06-04",
            data={"target_date": "2026-06-04"},
            execution_stage_context={
                "market_state_snapshot": {"market_state": "发酵"},
                "mainline_name": "电力",
                "local_trend_sector_proof": _complete_local_trend_sector_proof("电力"),
                "mainline_turnover_summary": {"current_mainline": "电力"},
                "sector_trend_snapshot": [
                    {
                        "sector": "电力",
                        "anchor_name": "豫能控股",
                        "anchor_code": "001896",
                        "anchor_reason": "板块锚，资金更容易反复回看",
                    }
                ],
                "extreme_conviction_list": [
                    {
                        "name": "豫能控股",
                        "code": "001896",
                        "sector": "电力",
                        "source_pools": ["主线核心"],
                        "anchor_reversal_decision": "可作为主对象",
                        "candidate_role": "板块锚",
                        "sector_anchor": "豫能控股(001896)",
                        "volume_summary": "放量",
                        "pattern": "突破后强收盘",
                        "conviction_rule": "固定窗口条件成立才参与",
                    }
                ],
            },
            position_decision={"target_position_pct": 50},
        )

        self.assertEqual(workflow["schema_version"], "selection_workflow.v1")
        self.assertEqual(workflow["derivation_contract"], "sector_first_strict.v1")
        self.assertEqual(
            [node["node_id"] for node in workflow["nodes"]],
            [f"N{i}" for i in range(10)],
        )
        self.assertLess(
            [node["node_id"] for node in workflow["nodes"]].index("N6"),
            [node["node_id"] for node in workflow["nodes"]].index("N7"),
        )
        for node in workflow["nodes"]:
            self.assertIn("input_summary", node)
            self.assertIsInstance(node["input_summary"], list)
            self.assertIn("conflicts", node)
            self.assertIsInstance(node["conflicts"], list)
        self.assertEqual(workflow["final"]["source_node"], "N8")
        self.assertEqual(workflow["final"]["execution_object"]["code"], "001896")
        self.assertEqual(workflow["final"]["position_pct"], 50)
        self.assertEqual(workflow["candidate_pool"][0]["first_seen_node"], "N5")
        self.assertEqual(workflow["candidate_pool"][0]["source_pools"], ["主线核心"])
        self.assertEqual(workflow["candidate_pool"][0]["entered_reason"], "固定窗口条件成立才参与")
        self.assertEqual(workflow["candidate_pool"][0]["workflow_path"], ["N5", "N6", "N7", "N8"])
        self.assertTrue(workflow["candidate_pool"][0]["new_entry_qualified"])
        self.assertEqual(workflow["candidate_pool"][0]["candidate_origin"], "sector_first")
        self.assertEqual(workflow["candidate_pool"][0]["leader_debate"]["question"], "为什么做它，为什么不做板块锚")
        self.assertEqual(workflow["candidate_pool"][0]["brooks_price_action_judge"]["verdict"], "资金表态被价格接受")
        self.assertEqual(workflow["candidate_pool"][0]["brooks_price_action_judge"]["volume_signal"], "放量")
        self.assertEqual(workflow["candidate_pool"][0]["common_selection_consistency"]["status"], "待复核")
        self.assertEqual(workflow["candidate_pool"][0]["status"], "最终执行对象")
        self.assertEqual(
            workflow["candidate_pool"][0]["front_observation_reason"],
            "已归入明日执行结论，后续只按B1/B2执行计划展示",
        )
        self.assertNotIn("已进入明日执行对象", workflow["candidate_pool"][0]["front_observation_reason"])
        n6 = next(node for node in workflow["nodes"] if node["node_id"] == "N6")
        n7 = next(node for node in workflow["nodes"] if node["node_id"] == "N7")
        self.assertEqual(workflow["market_layer"]["market_atmosphere"], "发酵")
        self.assertEqual(workflow["sector_layer"]["selected_direction"], "电力")
        self.assertEqual(workflow["leader_layer"]["leader_source"], "板块发酵推导")
        self.assertEqual(workflow["data_completeness"]["status"], "success")
        self.assertIn("market_layer", n6["passes_forward"])
        self.assertEqual(n6["passes_forward"]["leader_debate"], "先问为什么做它，再问为什么不做板块锚")
        self.assertIn("布鲁克斯价格行为裁判：价格确认1只", n7["judgement"])
        self.assertIn("成交量不能单独生成买入资格", n7["cannot_conclude"])
        self.assertEqual(n7["passes_forward"]["brooks_price_action"]["volume_role"], "资金表态证据")

    def test_limit_up_without_reversal_cannot_be_final_object(self):
        workflow = build_selection_workflow(
            target_date="2026-06-05",
            execution_stage_context={
                "market_state_snapshot": {"market_state": "收缩防守"},
                "mainline_name": "半导体",
                "extreme_conviction_list": [
                    {
                        "name": "大有能源",
                        "code": "600403",
                        "sector": "煤炭",
                        "pattern": "涨停",
                        "score": 140,
                        "anchor_reversal_decision": "降级观察",
                        "limit_up_evidence_role": "涨停只作观察证据",
                        "why_not_anchor": "无法替代板块锚",
                    }
                ],
            },
            position_decision={"target_position_pct": 50},
        )

        self.assertEqual(workflow["final"]["position_pct"], 0)
        self.assertEqual(workflow["final"]["execution_object"], {})
        self.assertEqual(workflow["candidate_pool"][0]["status"], "降级观察")
        self.assertEqual(workflow["candidate_pool"][0]["eliminated_at"], "N6")
        self.assertEqual(workflow["candidate_pool"][0]["brooks_price_action_judge"]["verdict"], "价格行为证据不足")
        self.assertFalse(workflow["candidate_pool"][0]["new_entry_qualified"])
        self.assertEqual(workflow["candidate_pool"][0]["candidate_origin"], "legacy_signal_only")
        self.assertFalse(workflow["candidate_pool"][0]["front_observation_qualified"])
        self.assertEqual(workflow["candidate_pool"][0]["observation_layer"], "process_observation")

    def test_weak_close_risk_first_candidate_cannot_be_final_execution_object(self):
        workflow = build_selection_workflow(
            target_date="2026-07-10",
            execution_stage_context={
                "market_state_snapshot": {"market_state": "收缩防守"},
                "mainline_name": "半导体",
                "sector_derived_candidates": [
                    {
                        "name": "华天科技",
                        "code": "002185",
                        "sector": "半导体",
                        "anchor_reversal_decision": "可作为主对象",
                        "candidate_role": "板块锚",
                        "sector_derivation_evidence": "半导体进入板块候选，容量成交",
                        "participation_window": "09:50-10:10",
                        "fallback_state": "不满足回到0%不参与",
                        "open": 26.10,
                        "high": 26.10,
                        "low": 25.10,
                        "close": 25.31,
                    }
                ],
            },
            position_decision={"target_position_pct": 50},
        )

        row = workflow["candidate_pool"][0]
        self.assertEqual(row["brooks_price_action_judge"]["status"], "risk_first")
        self.assertEqual(row["brooks_price_action_judge"]["verdict"], "先处理风险")
        self.assertIn("价格否定优先", row["price_action_block_reason"])
        self.assertNotIn("跌停反包专项", row["eliminated_reason"])
        self.assertEqual(workflow["final"]["execution_object"], {})
        self.assertEqual(workflow["final"]["position_pct"], 0)
        self.assertNotEqual(row["status"], "最终执行对象")

    def test_target_date_quote_ohlc_overrides_stale_candidate_ohlc(self):
        workflow = build_selection_workflow(
            target_date="2026-07-10",
            data={
                "selection_workflow_quote_rows": [
                    {
                        "trade_date": "2026-07-10",
                        "stock_code": "002185",
                        "name": "华天科技",
                        "open": 26.10,
                        "high": 26.10,
                        "low": 25.10,
                        "close": 25.31,
                    }
                ]
            },
            execution_stage_context={
                "market_state_snapshot": {"market_state": "收缩防守"},
                "mainline_name": "半导体",
                "sector_derived_candidates": [
                    {
                        "name": "华天科技",
                        "code": "002185",
                        "sector": "半导体",
                        "pattern": "放量",
                        "anchor_reversal_decision": "可作为主对象",
                        "candidate_role": "板块锚",
                        "sector_derivation_evidence": "半导体进入板块候选，容量成交",
                        "participation_window": "09:50-10:10",
                        "fallback_state": "不满足回到0%不参与",
                        "front_observation_qualified": False,
                        "front_observation_reason": "已归入明日执行结论，后续只按B1/B2执行计划展示",
                        "open": 25.00,
                        "high": 25.60,
                        "low": 24.80,
                        "close": 25.60,
                    }
                ],
            },
            position_decision={"target_position_pct": 50},
        )

        row = workflow["candidate_pool"][0]
        self.assertEqual(row["brooks_price_action_judge"]["candlestick_consequence"], "弱收盘")
        self.assertEqual(row["brooks_price_action_judge"]["status"], "risk_first")
        self.assertEqual(row["front_observation_reason"], row["process_rejection_reason"])
        self.assertIn("价格行为未通过确认", row["process_rejection_reason"])
        self.assertNotIn("已归入明日执行结论", row["front_observation_reason"])
        self.assertNotIn("B1/B2执行", row["front_observation_reason"])
        self.assertEqual(workflow["final"]["execution_object"], {})
        self.assertEqual(workflow["final"]["position_pct"], 0)

    def test_zero_position_candidate_cannot_keep_stale_final_conclusion_reason(self):
        workflow = build_selection_workflow(
            target_date="2026-07-13",
            execution_stage_context={
                "market_state_snapshot": {"market_state": "撤退"},
                "mainline_name": "半导体",
                "sector_derived_candidates": [
                    {
                        "name": "华天科技",
                        "code": "002185",
                        "sector": "半导体",
                        "anchor_reversal_decision": "可作为主对象",
                        "candidate_role": "板块锚",
                        "sector_derivation_evidence": "半导体进入板块候选，容量成交",
                        "front_observation_qualified": False,
                        "front_observation_reason": "已归入明日执行结论，后续只按B1/B2执行计划展示",
                        "pattern": "长上影",
                    }
                ],
            },
            position_decision={"target_position_pct": 0},
        )

        row = workflow["candidate_pool"][0]
        self.assertEqual(workflow["final"]["execution_object"], {})
        self.assertEqual(workflow["final"]["position_pct"], 0)
        self.assertEqual(row["status"], "过程候选")
        self.assertNotIn("已归入明日执行结论", row["front_observation_reason"])
        self.assertNotIn("B1/B2执行计划", row["front_observation_reason"])
        self.assertEqual(row["front_observation_reason"], row["process_rejection_reason"])

    def test_price_rejected_candidate_cannot_be_final_execution_object(self):
        workflow = build_selection_workflow(
            target_date="2026-07-10",
            execution_stage_context={
                "market_state_snapshot": {"market_state": "震荡"},
                "mainline_name": "半导体",
                "sector_derived_candidates": [
                    {
                        "name": "样本乙",
                        "code": "000002",
                        "sector": "半导体",
                        "anchor_reversal_decision": "可作为主对象",
                        "candidate_role": "板块锚",
                        "sector_derivation_evidence": "半导体进入板块候选，容量成交",
                        "participation_window": "09:50-10:10",
                        "fallback_state": "不满足回到0%不参与",
                        "volume_summary": "放量",
                        "pattern": "冲高回落，长上影",
                    }
                ],
            },
            position_decision={"target_position_pct": 50},
        )

        row = workflow["candidate_pool"][0]
        self.assertEqual(row["brooks_price_action_judge"]["status"], "price_rejected")
        self.assertIn("降级观察", row["price_action_block_reason"])
        self.assertNotIn("跌停反包专项", row["eliminated_reason"])
        self.assertEqual(workflow["final"]["execution_object"], {})
        self.assertEqual(workflow["final"]["position_pct"], 0)

    def test_t_board_or_one_line_limit_cannot_create_new_entry_without_sector_derivation(self):
        workflow = build_selection_workflow(
            target_date="2026-06-11",
            execution_stage_context={
                "market_state_snapshot": {"market_state": "局部活跃"},
                "mainline_name": "机器人",
                "extreme_conviction_list": [
                    {
                        "name": "样本丁",
                        "code": "000004",
                        "sector": "机器人",
                        "source_pools": ["T字板", "涨停池"],
                        "pattern": "T字板，放量强收盘",
                        "anchor_reversal_decision": "可作为主对象",
                        "candidate_role": "明日主买对象",
                        "participation_window": "09:50-10:10",
                        "fallback_state": "不满足回到0%",
                    }
                ],
            },
            position_decision={"target_position_pct": 50},
        )

        row = workflow["candidate_pool"][0]

        self.assertEqual(workflow["final"]["execution_object"], {})
        self.assertEqual(workflow["final"]["position_pct"], 0)
        self.assertEqual(row["candidate_origin"], "legacy_signal_only")
        self.assertFalse(row["new_entry_qualified"])
        self.assertIn("不能作为新仓入口", row["entry_basis"])
        self.assertEqual(row["status"], "过程候选")

    def test_runtime_observation_anchor_does_not_become_front_observation_without_explicit_mark(self):
        workflow = build_selection_workflow(
            target_date="2026-06-11",
            execution_stage_context={
                "market_state_snapshot": {"market_state": "收缩防守"},
                "mainline_name": "国产芯片替代",
                "sector_trend_snapshot": [
                    {
                        "sector": "化工原料",
                        "anchor_name": "和远气体",
                        "anchor_code": "002971",
                    }
                ],
            },
            selected_position_candidate={
                "name": "和远气体",
                "code": "002971",
                "sector": "化工原料",
                "anchor_reversal_decision": "可作为主对象",
                "candidate_role": "板块锚",
                "anchor_reversal_reason": "候选就是板块锚，分歧后资金优先回看",
                "pattern": "T字板分歧转一致",
            },
            position_decision={"target_position_pct": 0},
        )

        row = workflow["candidate_pool"][0]

        self.assertEqual(workflow["final"]["execution_object"], {})
        self.assertEqual(workflow["final"]["position_pct"], 0)
        self.assertEqual(row["status"], "过程候选")
        self.assertFalse(row["front_observation_qualified"])
        self.assertEqual(row["observation_layer"], "process_observation")

    def test_conflicting_explicit_front_observation_mark_stays_process_observation(self):
        workflow = build_selection_workflow(
            target_date="2026-06-11",
            execution_stage_context={
                "market_state_snapshot": {"market_state": "收缩防守"},
                "mainline_name": "国产芯片替代",
                "extreme_conviction_list": [
                    {
                        "name": "和远气体",
                        "code": "002971",
                        "sector": "化工原料",
                        "front_observation_qualified": True,
                        "front_observation_reason": "上游误标首页观察",
                        "observation_layer": "process_observation",
                        "candidate_role": "过程候选",
                        "anchor_reversal_decision": "降级观察",
                    }
                ],
            },
            position_decision={"target_position_pct": 0},
        )

        row = workflow["candidate_pool"][0]

        self.assertFalse(row["front_observation_qualified"])
        self.assertEqual(row["observation_layer"], "process_observation")
        self.assertEqual(row["front_observation_reason"], row["process_rejection_reason"])
        self.assertIn("未证明来自板块资金方向", row["process_rejection_reason"])

    def test_sector_derived_candidate_can_be_final_when_price_and_execution_qualify(self):
        workflow = build_selection_workflow(
            target_date="2026-06-11",
            execution_stage_context={
                "market_state_snapshot": {"market_state": "板块发酵"},
                "mainline_name": "AI算力",
                "local_trend_sector_proof": _complete_local_trend_sector_proof("AI算力"),
                "sector_trend_snapshot": [
                    {
                        "sector": "AI算力",
                        "anchor_name": "工业富联",
                        "anchor_code": "601138",
                        "anchor_reason": "板块成交扩散后反复承接的容量核心",
                    }
                ],
                "sector_derived_candidates": [
                    {
                        "name": "工业富联",
                        "code": "601138",
                        "sector": "AI算力",
                        "anchor_reversal_decision": "可作为主对象",
                        "candidate_role": "板块锚",
                        "sector_derivation_evidence": "板块成交扩散，后排承接，容量核心横住",
                        "volume_summary": "放量",
                        "pattern": "突破后强收盘",
                        "participation_window": "09:50-10:10",
                        "fallback_state": "不满足回到0%",
                    }
                ],
            },
            position_decision={"target_position_pct": 50},
        )

        row = workflow["candidate_pool"][0]

        self.assertEqual(workflow["final"]["execution_object"]["code"], "601138")
        self.assertEqual(workflow["final"]["position_pct"], 50)
        self.assertEqual(row["candidate_origin"], "sector_first")
        self.assertTrue(row["new_entry_qualified"])
        self.assertIn("板块成交扩散", row["entry_basis"])

    def test_limit_down_anchor_without_reversal_plan_stays_repair_observation(self):
        workflow = build_selection_workflow(
            target_date="2026-07-02",
            data={
                "date": "2026-07-02",
                "hot_rank_top50": [
                    {
                        "name": "太极实业",
                        "code": "600667",
                        "change_pct": -10.0,
                        "open": 29.62,
                        "high": 31.05,
                        "low": 28.89,
                        "close": 28.89,
                        "zt_status": "跌停",
                    }
                ]
            },
            execution_stage_context={
                "market_state_snapshot": {"market_state": "收缩防守"},
                "mainline_name": "半导体",
                "sector_derived_candidates": [
                    {
                        "name": "太极实业",
                        "code": "600667",
                        "sector": "半导体",
                        "anchor_reversal_decision": "可作为主对象",
                        "candidate_role": "板块锚",
                        "sector_derivation_evidence": "半导体进入板块候选，容量成交",
                        "participation_window": "09:50-10:10",
                        "fallback_state": "不满足回到0%",
                    }
                ],
            },
            position_decision={"target_position_pct": 50},
        )

        row = workflow["candidate_pool"][0]

        self.assertEqual(workflow["final"]["execution_object"], {})
        self.assertEqual(workflow["final"]["position_pct"], 0)
        self.assertFalse(row["new_entry_qualified"])
        self.assertEqual(row["status"], "风险复核样本")
        self.assertEqual(row["eliminated_at"], "N7")
        self.assertEqual(row["observation_layer"], "process_observation")
        self.assertIn("跌停", row["price_action_block_reason"])
        self.assertEqual(row["brooks_price_action_judge"]["verdict"], "跌停风险优先")
        self.assertIn("反包专项", row["eliminated_reason"])

    def test_bare_reversal_plan_boolean_cannot_bypass_limit_down_risk(self):
        reason = candidate_limit_down_risk_review_reason(
            {
                "name": "华天科技",
                "code": "002185",
                "change_pct": -10.0,
                "limit_down_reversal_plan": True,
            }
        )

        self.assertIn("跌停", reason)

    def test_limit_down_quote_backfill_blocks_sector_candidate(self):
        class FakeService:
            def query_stock_daily_quotes_recent(self, trade_date, stock_codes=None):
                assert trade_date == "2026-07-02"
                assert stock_codes == ["600667"]
                return [
                    {
                        "trade_date": "2026-07-02",
                        "stock_code": "600667",
                        "code": "600667",
                        "name": "太极实业",
                        "open": 29.62,
                        "high": 31.05,
                        "low": 28.89,
                        "close": 28.89,
                        "pct_chg": -10.0,
                    }
                ]

        with patch("storage.database_service.DatabaseService.fact_store_from_environment", return_value=FakeService()):
            workflow = build_selection_workflow(
                target_date="2026-07-02",
                data={
                    "target_date": "2026-07-02",
                    "enable_selection_workflow_quote_backfill": True,
                },
                execution_stage_context={
                    "market_state_snapshot": {"market_state": "收缩防守"},
                    "mainline_name": "半导体",
                    "sector_derived_candidates": [
                        {
                            "name": "太极实业",
                            "code": "600667",
                            "sector": "半导体",
                            "anchor_reversal_decision": "可作为主对象",
                            "candidate_role": "板块锚",
                            "sector_derivation_evidence": "半导体进入板块候选，容量成交",
                            "participation_window": "09:50-10:10",
                            "fallback_state": "不满足回到0%",
                        }
                    ],
                },
                position_decision={"target_position_pct": 50},
            )

        row = workflow["candidate_pool"][0]

        self.assertEqual(workflow["final"]["execution_object"], {})
        self.assertEqual(workflow["final"]["position_pct"], 0)
        self.assertIn("跌停", row["price_action_block_reason"])
        self.assertIn("反包专项", row["eliminated_reason"])

    def test_same_day_quote_overrides_stale_candidate_change_pct(self):
        workflow = build_selection_workflow(
            target_date="2026-07-02",
            data={
                "selection_workflow_quote_rows": [
                    {
                        "trade_date": "2026-07-02",
                        "stock_code": "600667",
                        "code": "600667",
                        "name": "太极实业",
                        "open": 29.62,
                        "high": 31.05,
                        "low": 28.89,
                        "close": 28.89,
                        "pct_chg": -10.0,
                    }
                ]
            },
            execution_stage_context={
                "market_state_snapshot": {"market_state": "收缩防守"},
                "mainline_name": "半导体",
                "sector_derived_candidates": [
                    {
                        "name": "太极实业",
                        "code": "600667",
                        "sector": "半导体",
                        "change_pct": 3.2,
                        "limit_status": "强势修复",
                        "anchor_reversal_decision": "可作为主对象",
                        "candidate_role": "板块锚",
                        "sector_derivation_evidence": "半导体进入板块候选，容量成交",
                        "participation_window": "09:50-10:10",
                        "fallback_state": "不满足回到0%",
                    }
                ],
            },
            position_decision={"target_position_pct": 50},
        )

        row = workflow["candidate_pool"][0]

        self.assertEqual(workflow["final"]["execution_object"], {})
        self.assertEqual(workflow["final"]["position_pct"], 0)
        self.assertFalse(row["new_entry_qualified"])
        self.assertIn("跌停", row["price_action_block_reason"])

    def test_bare_reversal_special_text_does_not_override_limit_down_quote(self):
        workflow = build_selection_workflow(
            target_date="2026-07-02",
            data={
                "selection_workflow_quote_rows": [
                    {
                        "trade_date": "2026-07-02",
                        "stock_code": "600667",
                        "code": "600667",
                        "name": "太极实业",
                        "pct_chg": -10.0,
                    }
                ]
            },
            execution_stage_context={
                "market_state_snapshot": {"market_state": "收缩防守"},
                "mainline_name": "半导体",
                "sector_derived_candidates": [
                    {
                        "name": "太极实业",
                        "code": "600667",
                        "sector": "半导体",
                        "anchor_reversal_decision": "可作为主对象",
                        "candidate_role": "板块锚",
                        "sector_derivation_evidence": "半导体进入板块候选，容量成交",
                        "execution_eligibility": "反包专项",
                        "participation_window": "09:50-10:10",
                        "fallback_state": "跌破认错线回到0%不参与",
                        "cancellation": "站不回VWAP就取消",
                    }
                ],
            },
            position_decision={"target_position_pct": 50},
        )

        row = workflow["candidate_pool"][0]

        self.assertEqual(workflow["final"]["execution_object"], {})
        self.assertEqual(workflow["final"]["position_pct"], 0)
        self.assertIn("跌停", row["price_action_block_reason"])

    def test_generated_elimination_reason_does_not_become_reversal_contract(self):
        workflow = build_selection_workflow(
            target_date="2026-07-02",
            data={
                "selection_workflow_quote_rows": [
                    {
                        "trade_date": "2026-07-02",
                        "stock_code": "600667",
                        "code": "600667",
                        "name": "太极实业",
                        "pct_chg": -10.0,
                    }
                ]
            },
            execution_stage_context={
                "market_state_snapshot": {"market_state": "收缩防守"},
                "mainline_name": "半导体",
                "sector_derived_candidates": [
                    {
                        "name": "太极实业",
                        "code": "600667",
                        "sector": "半导体",
                        "anchor_reversal_decision": "可作为主对象",
                        "candidate_role": "板块锚",
                        "sector_derivation_evidence": "半导体进入板块候选，容量成交",
                        "participation_window": "09:50-10:10",
                        "fallback_state": "不满足回到0%",
                        "price_action_block_reason": "同日跌幅-10.00%，按跌停/接近跌停处理",
                        "eliminated_reason": "如要参与必须写成跌停反包专项，并给出确认窗口、作废线和回到0%的条件",
                    }
                ],
            },
            position_decision={"target_position_pct": 50},
        )

        row = workflow["candidate_pool"][0]

        self.assertEqual(workflow["final"]["execution_object"], {})
        self.assertEqual(workflow["final"]["position_pct"], 0)
        self.assertFalse(row["new_entry_qualified"])
        self.assertIn("跌停", row["price_action_block_reason"])

    def test_stale_quote_date_does_not_block_target_date_candidate(self):
        workflow = build_selection_workflow(
            target_date="2026-07-02",
            data={
                "selection_workflow_quote_rows": [
                    {
                        "trade_date": "2026-07-01",
                        "stock_code": "600667",
                        "code": "600667",
                        "name": "太极实业",
                        "pct_chg": -10.0,
                    }
                ]
            },
            execution_stage_context={
                "market_state_snapshot": {"market_state": "修复"},
                "mainline_name": "半导体",
                "local_trend_sector_proof": _complete_local_trend_sector_proof("半导体"),
                "sector_derived_candidates": [
                    {
                        "name": "太极实业",
                        "code": "600667",
                        "sector": "半导体",
                        "anchor_reversal_decision": "可作为主对象",
                        "candidate_role": "板块锚",
                        "sector_derivation_evidence": "半导体进入板块候选，容量成交",
                        "participation_window": "09:50-10:10",
                        "fallback_state": "不满足回到0%",
                    }
                ],
            },
            position_decision={"target_position_pct": 50},
        )

        row = workflow["candidate_pool"][0]

        self.assertEqual(workflow["final"]["execution_object"]["code"], "600667")
        self.assertEqual(workflow["final"]["position_pct"], 50)
        self.assertEqual(row["price_action_block_reason"], "")

    def test_undated_quote_does_not_block_target_date_candidate(self):
        workflow = build_selection_workflow(
            target_date="2026-07-02",
            data={
                "selection_workflow_quote_rows": [
                    {
                        "stock_code": "600667",
                        "code": "600667",
                        "name": "太极实业",
                        "pct_chg": -10.0,
                    }
                ]
            },
            execution_stage_context={
                "market_state_snapshot": {"market_state": "修复"},
                "mainline_name": "半导体",
                "local_trend_sector_proof": _complete_local_trend_sector_proof("半导体"),
                "sector_derived_candidates": [
                    {
                        "name": "太极实业",
                        "code": "600667",
                        "sector": "半导体",
                        "anchor_reversal_decision": "可作为主对象",
                        "candidate_role": "板块锚",
                        "sector_derivation_evidence": "半导体进入板块候选，容量成交",
                        "participation_window": "09:50-10:10",
                        "fallback_state": "不满足回到0%",
                    }
                ],
            },
            position_decision={"target_position_pct": 50},
        )

        row = workflow["candidate_pool"][0]

        self.assertEqual(workflow["final"]["execution_object"]["code"], "600667")
        self.assertEqual(workflow["final"]["position_pct"], 50)
        self.assertEqual(row["price_action_block_reason"], "")

    def test_undated_hot_rank_without_container_date_does_not_block_target_date_candidate(self):
        workflow = build_selection_workflow(
            target_date="2026-07-02",
            data={
                "hot_rank_top50": [
                    {
                        "stock_code": "600667",
                        "code": "600667",
                        "name": "太极实业",
                        "pct_chg": -10.0,
                        "zt_status": "跌停",
                    }
                ]
            },
            execution_stage_context={
                "market_state_snapshot": {"market_state": "修复"},
                "mainline_name": "半导体",
                "local_trend_sector_proof": _complete_local_trend_sector_proof("半导体"),
                "sector_derived_candidates": [
                    {
                        "name": "太极实业",
                        "code": "600667",
                        "sector": "半导体",
                        "anchor_reversal_decision": "可作为主对象",
                        "candidate_role": "板块锚",
                        "sector_derivation_evidence": "半导体进入板块候选，容量成交",
                        "participation_window": "09:50-10:10",
                        "fallback_state": "不满足回到0%",
                    }
                ],
            },
            position_decision={"target_position_pct": 50},
        )

        row = workflow["candidate_pool"][0]

        self.assertEqual(workflow["final"]["execution_object"]["code"], "600667")
        self.assertEqual(workflow["final"]["position_pct"], 50)
        self.assertEqual(row["price_action_block_reason"], "")

    def test_plain_reversal_text_does_not_combine_with_quote_limit_down(self):
        workflow = build_selection_workflow(
            target_date="2026-07-02",
            data={
                "date": "2026-07-02",
                "hot_rank_top50": [
                    {
                        "name": "太极实业",
                        "code": "600667",
                        "change_pct": -10.0,
                        "zt_status": "跌停",
                    }
                ]
            },
            execution_stage_context={
                "market_state_snapshot": {"market_state": "收缩防守"},
                "mainline_name": "半导体",
                "sector_derived_candidates": [
                    {
                        "name": "太极实业",
                        "code": "600667",
                        "sector": "半导体",
                        "anchor_reversal_decision": "可作为主对象",
                        "candidate_role": "板块锚",
                        "sector_derivation_evidence": "半导体进入板块候选，容量成交",
                        "pattern": "反包强收盘",
                        "participation_window": "09:50-10:10",
                        "fallback_state": "跌破认错线回到0%不参与",
                    }
                ],
            },
            position_decision={"target_position_pct": 50},
        )

        row = workflow["candidate_pool"][0]

        self.assertEqual(workflow["final"]["execution_object"], {})
        self.assertEqual(workflow["final"]["position_pct"], 0)
        self.assertIn("跌停", row["price_action_block_reason"])

    def test_bare_anti_nuclear_text_without_special_contract_stays_observation(self):
        workflow = build_selection_workflow(
            target_date="2026-07-02",
            data={
                "date": "2026-07-02",
                "hot_rank_top50": [
                    {
                        "name": "太极实业",
                        "code": "600667",
                        "change_pct": -10.0,
                        "zt_status": "跌停",
                    }
                ]
            },
            execution_stage_context={
                "market_state_snapshot": {"market_state": "收缩防守"},
                "mainline_name": "半导体",
                "sector_derived_candidates": [
                    {
                        "name": "太极实业",
                        "code": "600667",
                        "sector": "半导体",
                        "anchor_reversal_decision": "可作为主对象",
                        "candidate_role": "板块锚",
                        "sector_derivation_evidence": "半导体进入板块候选，容量成交",
                        "execution_eligibility": "反核",
                        "participation_window": "09:50-10:10",
                        "fallback_state": "不满足就不参与",
                    }
                ],
            },
            position_decision={"target_position_pct": 50},
        )

        row = workflow["candidate_pool"][0]

        self.assertEqual(workflow["final"]["execution_object"], {})
        self.assertEqual(workflow["final"]["position_pct"], 0)
        self.assertIn("反包专项", row["eliminated_reason"])

    def test_limit_down_reversal_plan_can_remain_final_when_explicit_and_cancelable(self):
        workflow = build_selection_workflow(
            target_date="2026-07-02",
            data={
                "date": "2026-07-02",
                "hot_rank_top50": [
                    {
                        "name": "太极实业",
                        "code": "600667",
                        "change_pct": -10.0,
                        "open": 29.62,
                        "high": 31.05,
                        "low": 28.89,
                        "close": 28.89,
                        "zt_status": "跌停",
                    }
                ]
            },
            execution_stage_context={
                "market_state_snapshot": {"market_state": "收缩防守"},
                "mainline_name": "半导体",
                "local_trend_sector_proof": _complete_local_trend_sector_proof("半导体"),
                "sector_derived_candidates": [
                    {
                        "name": "太极实业",
                        "code": "600667",
                        "sector": "半导体",
                        "anchor_reversal_decision": "可作为主对象",
                        "candidate_role": "板块锚",
                        "sector_derivation_evidence": "半导体进入板块候选，容量成交",
                        "execution_eligibility": "跌停反包专项",
                        "participation_window": "09:50-10:10跌停反包确认",
                        "fallback_state": "不满足回到0%不参与",
                        "cancellation": "继续封死或站不回VWAP就不参与",
                    }
                ],
            },
            position_decision={"target_position_pct": 50},
        )

        row = workflow["candidate_pool"][0]

        self.assertEqual(workflow["final"]["execution_object"]["code"], "600667")
        self.assertEqual(workflow["final"]["position_pct"], 50)
        self.assertTrue(row["new_entry_qualified"])
        self.assertEqual(row["status"], "最终执行对象")
        self.assertTrue(row["limit_down_reversal_plan"])
        self.assertEqual(row["price_action_block_reason"], "")
        self.assertEqual(row["brooks_price_action_judge"]["verdict"], "跌停后反包修复待确认")

    def test_limit_down_reversal_plan_accepts_tail_window_when_explicit(self):
        workflow = build_selection_workflow(
            target_date="2026-07-02",
            data={
                "date": "2026-07-02",
                "hot_rank_top50": [
                    {
                        "name": "太极实业",
                        "code": "600667",
                        "change_pct": -10.0,
                        "zt_status": "跌停",
                    }
                ]
            },
            execution_stage_context={
                "market_state_snapshot": {"market_state": "收缩防守"},
                "mainline_name": "半导体",
                "local_trend_sector_proof": _complete_local_trend_sector_proof("半导体"),
                "sector_derived_candidates": [
                    {
                        "name": "太极实业",
                        "code": "600667",
                        "sector": "半导体",
                        "anchor_reversal_decision": "可作为主对象",
                        "candidate_role": "板块锚",
                        "sector_derivation_evidence": "半导体进入板块候选，容量成交",
                        "execution_eligibility": "跌停反包专项",
                        "participation_window": "14:30-14:55跌停反包确认",
                        "fallback_state": "不满足回到0%不参与",
                        "cancellation": "继续封死或站不回VWAP就不参与",
                    }
                ],
            },
            position_decision={"target_position_pct": 50},
        )

        row = workflow["candidate_pool"][0]

        self.assertEqual(workflow["final"]["execution_object"]["code"], "600667")
        self.assertEqual(workflow["final"]["position_pct"], 50)
        self.assertTrue(row["new_entry_qualified"])
        self.assertEqual(row["price_action_block_reason"], "")

    def test_missing_critical_data_stops_workflow_final_output(self):
        workflow = build_selection_workflow(
            target_date="2026-06-11",
            data={"selection_workflow_missing_fields": ["板块发酵数据", "市场情绪线承接"]},
            execution_stage_context={
                "market_state_snapshot": {"market_state": "局部活跃"},
                "mainline_name": "机器人",
                "sector_derived_candidates": [
                    {
                        "name": "样本戊",
                        "code": "000005",
                        "sector": "机器人",
                        "anchor_reversal_decision": "可作为主对象",
                        "candidate_role": "板块锚",
                        "participation_window": "09:50-10:10",
                        "fallback_state": "不满足回到0%",
                    }
                ],
            },
            position_decision={"target_position_pct": 50},
        )

        n8 = next(node for node in workflow["nodes"] if node["node_id"] == "N8")

        self.assertEqual(workflow["data_completeness"]["status"], "failed")
        self.assertEqual(workflow["final"]["execution_object"], {})
        self.assertEqual(workflow["final"]["position_pct"], 0)
        self.assertIn("板块发酵数据", workflow["final"]["failure_conditions"])
        self.assertIn("关键数据不完整，停止生成", n8["judgement"])

    def test_volume_alone_enters_brooks_evidence_without_creating_participation(self):
        workflow = build_selection_workflow(
            target_date="2026-06-11",
            execution_stage_context={
                "market_state_snapshot": {"market_state": "震荡"},
                "mainline_name": "AI硬件",
                "extreme_conviction_list": [
                    {
                        "name": "样本甲",
                        "code": "000001",
                        "sector": "AI硬件",
                        "volume_summary": "突然放量，资金开始表态",
                        "anchor_reversal_decision": "",
                        "candidate_role": "观察样本",
                    }
                ],
            },
            position_decision={"target_position_pct": 50},
        )

        row = workflow["candidate_pool"][0]
        self.assertEqual(workflow["final"]["execution_object"], {})
        self.assertEqual(workflow["final"]["position_pct"], 0)
        self.assertEqual(row["brooks_price_action_judge"]["volume_signal"], "放量")
        self.assertEqual(row["brooks_price_action_judge"]["verdict"], "价格行为证据不足")
        self.assertIn("不新增资格", row["brooks_price_action_judge"]["participation_effect"])
        n7 = next(node for node in workflow["nodes"] if node["node_id"] == "N7")
        self.assertIn("价格确认0只", n7["judgement"])

    def test_brooks_records_volume_rejection_as_process_evidence(self):
        workflow = build_selection_workflow(
            target_date="2026-06-11",
            execution_stage_context={
                "mainline_name": "半导体",
                "extreme_conviction_list": [
                    {
                        "name": "样本乙",
                        "code": "000002",
                        "sector": "半导体",
                        "volume_summary": "放量",
                        "pattern": "冲高回落，长上影",
                        "anchor_reversal_decision": "降级观察",
                        "candidate_role": "大容量中军",
                        "why_not_anchor": "不能替代板块锚",
                    }
                ],
            },
            position_decision={"target_position_pct": 0},
        )

        row = workflow["candidate_pool"][0]
        self.assertEqual(row["brooks_price_action_judge"]["verdict"], "资金表态未被价格接受")
        self.assertIn("等待后续行情重新确认", row["brooks_price_action_judge"]["participation_effect"])
        n7 = next(node for node in workflow["nodes"] if node["node_id"] == "N7")
        self.assertEqual(n7["passes_forward"]["brooks_price_action"]["risk_or_rejection_count"], 1)

    def test_legacy_extreme_candidates_remain_process_evidence_without_sector_proof(self):
        workflow = build_selection_workflow(
            target_date="2026-06-10",
            execution_stage_context={
                "mainline_name": "半导体",
                "extreme_conviction_list": [
                    {
                        "name": "雅克科技",
                        "code": "002409",
                        "sector": "半导体",
                        "entered_reason": "主线内核 / 首板 / 趋势审美 / 蛇形走位 / 高低点上移",
                        "anchor_reversal_decision": "降级观察",
                        "candidate_role": "大容量中军",
                        "why_not_anchor": "不能替代板块锚；无法说明为什么不做海光信息(688041)",
                        "candidate_layer": "front_observation",
                        "front_observation_qualified": True,
                        "front_observation_reason": "上游明确只保留首页观察，用于盯半导体容量承接，并继续对照海光信息",
                    },
                    {
                        "name": "双星新材",
                        "code": "002585",
                        "sector": "塑料",
                        "entered_reason": "2连板 / 趋势审美 / 蛇形走位 / 高低点上移",
                        "anchor_reversal_decision": "降级观察",
                        "candidate_role": "观察样本",
                        "why_not_anchor": "本板块锚未识别，不能说明为什么不做本板块锚",
                    },
                ],
            },
            position_decision={"target_position_pct": 0},
        )

        by_code = {row["stock"]["code"]: row for row in workflow["candidate_pool"]}

        self.assertEqual(workflow["final"]["execution_object"], {})
        self.assertFalse(by_code["002409"]["front_observation_qualified"])
        self.assertEqual(by_code["002409"]["observation_layer"], "process_observation")
        self.assertEqual(
            by_code["002409"]["front_observation_reason"],
            by_code["002409"]["process_rejection_reason"],
        )
        self.assertNotIn("海光信息", by_code["002409"]["front_observation_reason"])
        self.assertFalse(by_code["002585"]["front_observation_qualified"])
        self.assertEqual(by_code["002585"]["observation_layer"], "process_observation")
        self.assertEqual(
            by_code["002585"]["front_observation_reason"],
            by_code["002585"]["process_rejection_reason"],
        )

    def test_selected_candidate_not_in_pool_cannot_fallback_to_other_candidate(self):
        workflow = build_selection_workflow(
            target_date="2026-06-05",
            execution_stage_context={
                "mainline_name": "电力",
                "extreme_conviction_list": [
                    {
                        "name": "候选乙",
                        "code": "000002",
                        "sector": "电力",
                        "anchor_reversal_decision": "可作为主对象",
                    }
                ],
            },
            selected_position_candidate={"name": "显式对象甲", "code": "000001"},
            position_decision={"target_position_pct": 50},
        )

        self.assertEqual(workflow["final"]["execution_object"], {})
        self.assertEqual(workflow["final"]["position_pct"], 0)
        n6 = next(node for node in workflow["nodes"] if node["node_id"] == "N6")
        n9 = next(node for node in workflow["nodes"] if node["node_id"] == "N9")
        self.assertIsInstance(n6["conflicts"], list)
        self.assertIsInstance(n9["conflicts"], list)
        self.assertTrue(any("显式对象不在候选池" in item for item in n6["conflicts"]))
        self.assertTrue(any("000001" in item for item in n9["conflicts"]))

    def test_unqualified_selected_pool_candidate_yields_to_qualified_sector_candidate(self):
        workflow = build_selection_workflow(
            target_date="2026-07-27",
            execution_stage_context={
                "mainline_name": "电力",
                "local_trend_sector_proof": _complete_local_trend_sector_proof("电力"),
                "sector_derived_candidates": [
                    {
                        "name": "豫能控股",
                        "code": "001896",
                        "sector": "电力",
                        "anchor_reversal_decision": "可作为主对象",
                        "candidate_role": "板块锚",
                    }
                ],
                "extreme_conviction_list": [
                    {
                        "name": "上海石化",
                        "code": "600688",
                        "sector": "炼化及贸",
                        "anchor_reversal_decision": "可作为主对象",
                        "candidate_role": "板块锚",
                        "participation_window": "09:50-10:10",
                        "fallback_state": "条件不满足回到0%",
                    }
                ],
            },
            selected_position_candidate={
                "name": "上海石化",
                "code": "600688",
                "sector": "炼化及贸",
            },
            position_decision={"target_position_pct": 50},
        )

        self.assertEqual(workflow["final"]["execution_object"]["code"], "001896")
        self.assertEqual(workflow["final"]["position_pct"], 50)
        by_code = {item["stock"]["code"]: item for item in workflow["candidate_pool"]}
        self.assertEqual(by_code["001896"]["status"], "最终执行对象")
        self.assertEqual(by_code["600688"]["status"], "过程候选")

    def test_explicit_legacy_target_does_not_reorder_qualified_sector_candidates(self):
        context = _qualified_sector_context(direction="电力")
        context["sector_derived_candidates"].append(
            {
                "name": "上海电力",
                "code": "600021",
                "sector": "电力",
                "anchor_reversal_decision": "可作为主对象",
                "candidate_role": "板块锚",
                "sector_derivation_evidence": "同一资金方向内的次序候选",
                "participation_window": "09:50-10:10",
                "fallback_state": "条件不满足回到0%不参与",
            }
        )

        workflow = build_selection_workflow(
            target_date="2026-07-27",
            execution_stage_context=context,
            selected_position_candidate={
                "name": "上海电力",
                "code": "600021",
                "sector": "电力",
            },
            position_decision={"target_position_pct": 50},
        )

        self.assertEqual(
            [row["stock"]["code"] for row in workflow["candidate_pool"][:2]],
            ["001896", "600021"],
        )
        self.assertEqual(workflow["final"]["execution_object"]["code"], "001896")

    def test_same_stock_merges_legacy_and_nested_sector_sources_without_losing_qualification(self):
        context = _qualified_sector_context(direction="电力")
        sector_candidate = context.pop("sector_derived_candidates")[0]
        context["extreme_conviction_list"] = [
            {
                "name": "豫能控股",
                "code": "001896",
                "sector": "电力",
                "conviction_reason": "旧强势名单来源",
            }
        ]
        context["step2_bundle"] = {
            "sector_derived_candidates": [sector_candidate],
        }

        workflow = build_selection_workflow(
            target_date="2026-07-27",
            execution_stage_context=context,
            position_decision={"target_position_pct": 50},
        )

        self.assertEqual(workflow["final"]["execution_object"]["code"], "001896")
        self.assertEqual(len(workflow["candidate_pool"]), 1)
        row = workflow["candidate_pool"][0]
        self.assertEqual(row["candidate_origin"], "sector_first")
        self.assertTrue(row["new_entry_qualified"])
        self.assertEqual(
            row["source_pools"],
            ["extreme_conviction_list", "step2_bundle.sector_derived_candidates"],
        )

    def test_single_emotion_leader_without_multiple_capital_carriers_is_not_qualified(self):
        workflow = build_selection_workflow(
            target_date="2026-07-29",
            execution_stage_context={
                "market_state_snapshot": {"market_state": "普跌抱团"},
                "mainline_name": "情绪抱团",
                "market_emotion_line_proof": {
                    "complete": True,
                    "scarcity_recognition": True,
                    "capacity_evidence": True,
                    "public_participation": True,
                    "divergence_acceptance": True,
                    "capital_carriers": [
                        {"name": "明新旭腾", "code": "605068"},
                    ],
                    "leader": {"name": "明新旭腾", "code": "605068"},
                },
                "market_emotion_candidates": [
                    {
                        "name": "明新旭腾",
                        "code": "605068",
                        "sector": "汽车零部件",
                        "anchor_reversal_decision": "可作为主对象",
                        "candidate_role": "情绪高标",
                        "participation_window": "09:50-10:10",
                        "fallback_state": "条件不满足回到0%不参与",
                    }
                ],
            },
            position_decision={"target_position_pct": 50},
        )

        row = workflow["candidate_pool"][0]
        self.assertEqual(workflow["final"]["execution_object"], {})
        self.assertEqual(workflow["final"]["position_pct"], 0)
        self.assertEqual(row["candidate_origin"], "legacy_signal_only")
        self.assertFalse(row["new_entry_qualified"])
        self.assertEqual(row["observation_layer"], "process_observation")

    def test_complete_market_emotion_direction_does_not_report_direction_mismatch(self):
        context = _qualified_sector_context(direction="电力")
        context.pop("sector_derived_candidates")
        context["market_emotion_line_proof"] = {
            "complete": True,
            "direction": "情绪抱团",
            "scarcity_recognition": True,
            "capacity_evidence": True,
            "public_participation": True,
            "divergence_acceptance": True,
            "competition_comparison": True,
            "capital_carriers": [
                {"name": "明新旭腾", "code": "605068"},
                {"name": "北汽蓝谷", "code": "600733"},
            ],
            "leader": {"name": "明新旭腾", "code": "605068"},
        }
        context["market_emotion_candidates"] = [
            {
                "name": "明新旭腾",
                "code": "605068",
                "sector": "汽车零部件",
                "anchor_reversal_decision": "可作为主对象",
                "candidate_role": "情绪核心",
                "participation_window": "09:50-10:10",
                "fallback_state": "条件不满足回到0%不参与",
            }
        ]

        workflow = build_selection_workflow(
            target_date="2026-07-29",
            execution_stage_context=context,
            position_decision={"target_position_pct": 50},
        )

        self.assertEqual(workflow["final"]["execution_object"]["code"], "605068")
        self.assertEqual(workflow["final"]["position_pct"], 50)
        self.assertTrue(workflow["candidate_pool"][0]["new_entry_qualified"])
        self.assertNotIn("个股与已证明方向不匹配", workflow["final"]["failure_conditions"])
        self.assertNotEqual(workflow["final"]["reason"], "个股与已证明方向不匹配")

    def test_selected_candidate_needs_execution_evidence_even_when_reversal_passes(self):
        workflow = build_selection_workflow(
            target_date="2026-06-05",
            execution_stage_context={
                "mainline_name": "电力",
                "extreme_conviction_list": [
                    {
                        "name": "豫能控股",
                        "code": "001896",
                        "sector": "电力",
                        "anchor_reversal_decision": "可作为主对象",
                    }
                ],
            },
            selected_position_candidate={"name": "豫能控股", "code": "001896", "sector": "电力"},
            position_decision={"target_position_pct": 50},
        )

        self.assertEqual(workflow["final"]["execution_object"], {})
        self.assertEqual(workflow["final"]["position_pct"], 0)
        self.assertEqual(workflow["candidate_pool"][0]["status"], "过程候选")

    def test_selected_candidate_needs_reversal_proof_even_with_execution_window(self):
        workflow = build_selection_workflow(
            target_date="2026-06-05",
            execution_stage_context={
                "mainline_name": "电力",
            },
            selected_position_candidate={
                "name": "显式对象甲",
                "code": "000001",
                "sector": "电力",
                "participation_window": "09:50-10:10",
                "fallback_state": "不满足回到0%",
            },
            position_decision={"target_position_pct": 50},
        )

        self.assertEqual(workflow["final"]["execution_object"], {})
        self.assertEqual(workflow["final"]["position_pct"], 0)
        self.assertEqual(workflow["candidate_pool"][0]["source_pools"], ["运行时观察对象"])
        self.assertNotIn("执行对象", workflow["candidate_pool"][0]["source_pools"][0])

    def test_selected_candidate_outside_pool_cannot_be_final_even_with_reversal_and_execution_window(self):
        workflow = build_selection_workflow(
            target_date="2026-06-05",
            execution_stage_context={
                "mainline_name": "电力",
            },
            selected_position_candidate={
                "name": "显式对象甲",
                "code": "000001",
                "sector": "电力",
                "anchor_reversal_decision": "可作为主对象",
                "participation_window": "09:50-10:10",
                "fallback_state": "不满足回到0%",
            },
            position_decision={"target_position_pct": 50},
        )

        self.assertEqual(workflow["final"]["execution_object"], {})
        self.assertEqual(workflow["final"]["position_pct"], 0)
        n6 = next(node for node in workflow["nodes"] if node["node_id"] == "N6")
        self.assertTrue(any("显式对象不在候选池" in item for item in n6["conflicts"]))

    def test_position_rejects_outside_contract_and_accepts_exact_full_tier(self):
        workflow = build_selection_workflow(
            target_date="2026-06-04",
            execution_stage_context={
                "mainline_name": "电力",
                "extreme_conviction_list": [
                    {
                        "name": "豫能控股",
                        "code": "001896",
                        "sector": "电力",
                        "anchor_reversal_decision": "可作为主对象",
                        "candidate_role": "板块锚",
                    }
                ],
            },
            position_decision={"target_position_pct": 70},
        )

        self.assertEqual(workflow["final"]["position_pct"], 0)
        self.assertEqual(workflow["final"]["execution_object"], {})
        self.assertNotIn("70", workflow["final"]["action_text"])

        full_workflow = build_selection_workflow(
            target_date="2026-06-04",
            execution_stage_context={
                "mainline_name": "电力",
                "broad_market_confirmation": True,
                "local_trend_sector_proof": _complete_local_trend_sector_proof("电力"),
                "sector_derived_candidates": [
                    {
                        "name": "豫能控股",
                        "code": "001896",
                        "sector": "电力",
                        "anchor_reversal_decision": "可作为主对象",
                        "candidate_role": "板块锚",
                    }
                ],
            },
            position_decision={"target_position_pct": 100},
        )
        empty_workflow = build_selection_workflow(
            target_date="2026-06-04",
            execution_stage_context={
                "mainline_name": "电力",
                "extreme_conviction_list": [
                    {
                        "name": "豫能控股",
                        "code": "001896",
                        "sector": "电力",
                        "anchor_reversal_decision": "可作为主对象",
                        "candidate_role": "板块锚",
                    }
                ],
            },
            position_decision={"target_position_pct": 39},
        )

        self.assertEqual(full_workflow["final"]["position_pct"], 100)
        self.assertEqual(full_workflow["final"]["action_text"], "100%核心进攻")
        self.assertEqual(empty_workflow["final"]["position_pct"], 0)
        self.assertEqual(empty_workflow["final"]["action_text"], "0%不参与")
        self.assertEqual(empty_workflow["final"]["execution_object"], {})
        self.assertEqual(empty_workflow["candidate_pool"][0]["status"], "过程候选")

    def test_premarket_narrative_review_ignores_plain_external_weakness(self):
        workflow = build_selection_workflow(
            target_date="2026-07-01",
            data={
                "premarket_narrative_review": {
                    "review_window": "2026-07-01 18:00 -> 2026-07-02 09:25",
                    "overseas_pricing": ["纳指科技股回落", "美股半导体下跌"],
                    "asia_confirmation": ["韩国指数低开"],
                    "reason_chain": ["外盘风险偏好走弱"],
                }
            },
            execution_stage_context={
                "market_state_snapshot": {"market_state": "进攻分歧"},
                "mainline_name": "AI算力基础设施",
                "broad_market_confirmation": True,
                "local_trend_sector_proof": _complete_local_trend_sector_proof("AI算力基础设施"),
                "sector_derived_candidates": [
                    {
                        "name": "太极实业",
                        "code": "600667",
                        "sector": "AI算力基础设施",
                        "anchor_reversal_decision": "可作为主对象",
                        "candidate_role": "板块锚",
                        "sector_derivation_evidence": "AI算力链成交扩散，PCB供应商承接",
                        "volume_summary": "放量",
                        "pattern": "突破后强收盘",
                        "participation_window": "09:30-09:35",
                        "fallback_state": "不满足回到0%",
                    }
                ],
            },
            position_decision={"target_position_pct": 100},
        )

        review = workflow["premarket_narrative_review"]
        n8_5 = next(node for node in workflow["nodes"] if node["node_id"] == "N8_5")

        self.assertEqual(review["status"], "未触发")
        self.assertEqual(review["action_effect"], "keep")
        self.assertEqual(workflow["final"]["position_pct"], 100)
        self.assertEqual(workflow["final"]["source_node"], "N8")
        self.assertIn("未触发", n8_5["judgement"])
        mermaid = render_selection_workflow_mermaid(workflow)
        self.assertIn("N8 --> N8_5", mermaid)
        self.assertIn("N8 --> N9", mermaid)
        self.assertIn("N8 --> FINAL", mermaid)
        self.assertNotIn("N8_5 --> N9", mermaid)
        self.assertNotIn("N8_5 --> FINAL", mermaid)

    def test_premarket_narrative_review_keeps_broad_us_selloff_as_external_noise(self):
        workflow = build_selection_workflow(
            target_date="2026-07-01",
            data={
                "premarket_narrative_review": {
                    "review_window": "2026-07-01 18:00 -> 2026-07-02 09:25",
                    "original_driver": "AI算力和存储紧缺",
                    "counter_event": {"title": "美股半导体大跌", "source": "market"},
                    "overseas_pricing": ["费城半导体指数下跌", "英伟达盘前回落"],
                    "asia_confirmation": ["韩国指数低开"],
                    "a_share_mapping": ["半导体", "AI算力基础设施"],
                    "target_exposure": "direct",
                    "reason_chain": ["美股半导体大跌", "外盘风险偏好走弱", "A股半导体承压"],
                }
            },
            execution_stage_context={
                "market_state_snapshot": {"market_state": "进攻分歧"},
                "mainline_name": "AI算力基础设施",
                "broad_market_confirmation": True,
                "local_trend_sector_proof": _complete_local_trend_sector_proof("AI算力基础设施"),
                "sector_derived_candidates": [
                    {
                        "name": "太极实业",
                        "code": "600667",
                        "sector": "AI算力基础设施",
                        "anchor_reversal_decision": "可作为主对象",
                        "candidate_role": "板块锚",
                        "sector_derivation_evidence": "AI算力链成交扩散，PCB供应商承接",
                        "current_driver_tags": ["AI算力", "半导体"],
                        "participation_window": "09:30-09:35",
                        "fallback_state": "不满足回到0%",
                    }
                ],
            },
            position_decision={"target_position_pct": 100},
        )

        review = workflow["premarket_narrative_review"]

        self.assertEqual(review["status"], "未触发")
        self.assertEqual(review["action_effect"], "keep")
        self.assertFalse(review["complete_chain"])
        self.assertEqual(workflow["final"]["position_pct"], 100)
        self.assertEqual(workflow["final"]["source_node"], "N8")

    def test_premarket_narrative_review_cancels_complete_meta_compute_chain(self):
        workflow = build_selection_workflow(
            target_date="2026-07-01",
            data={
                "premarket_narrative_review": {
                    "review_window": "2026-07-01 18:00 -> 2026-07-02 09:25",
                    "original_driver": "AI算力和存储紧缺",
                    "counter_event": {
                        "title": "Meta据悉布局AI云业务，拟对外出售算力",
                        "source": "CLS",
                        "source_time": "2026-07-01 20:35:04",
                        "level": "B",
                        "url": "https://www.cls.cn/detail/2414547",
                    },
                    "overseas_pricing": [
                        "CoreWeave/Nebius盘前跌超9%",
                        "美光/闪迪带动存储链下跌",
                    ],
                    "asia_confirmation": ["KOSPI跌超5%，SK海力士跌8%，三星电子跌7%"],
                    "a_share_mapping": ["半导体", "PCB", "AI算力基础设施"],
                    "target_exposure": "direct",
                    "restore_conditions": ["同链板块不继续负反馈", "太极实业开盘承接独立"],
                    "cancel_conditions": ["同链板块继续负反馈", "标的无法修复承接"],
                    "reason_chain": [
                        "AI算力和存储紧缺",
                        "Meta拟对外出售算力",
                        "海外算力租赁和存储链下跌",
                        "韩国海力士和三星确认",
                        "A股半导体/PCB/AI算力基础设施承压",
                        "太极实业直接暴露",
                        "满仓条件执行取消为不参与",
                    ],
                }
            },
            execution_stage_context={
                "market_state_snapshot": {"market_state": "进攻分歧"},
                "mainline_name": "AI算力基础设施",
                "broad_market_confirmation": True,
                "local_trend_sector_proof": _complete_local_trend_sector_proof("AI算力基础设施"),
                "sector_derived_candidates": [
                    {
                        "name": "太极实业",
                        "code": "600667",
                        "sector": "AI算力基础设施",
                        "anchor_reversal_decision": "可作为主对象",
                        "candidate_role": "板块锚",
                        "sector_derivation_evidence": "AI算力链成交扩散，PCB供应商承接",
                        "current_driver_tags": ["AI算力", "PCB", "半导体"],
                        "volume_summary": "放量",
                        "pattern": "突破后强收盘",
                        "participation_window": "09:30-09:35",
                        "fallback_state": "不满足回到0%",
                    }
                ],
            },
            position_decision={"target_position_pct": 100},
        )

        review = workflow["premarket_narrative_review"]
        n8_5 = next(node for node in workflow["nodes"] if node["node_id"] == "N8_5")
        mermaid = render_selection_workflow_mermaid(workflow)

        self.assertEqual(review["status"], "不参与")
        self.assertEqual(review["action_effect"], "no_participation")
        self.assertEqual(review["position_cap_pct"], 0)
        self.assertEqual(workflow["final"]["position_pct"], 0)
        self.assertEqual(workflow["final"]["execution_object"], {})
        self.assertEqual(workflow["final"]["source_node"], "N8_5")
        self.assertEqual(workflow["final"]["premarket_narrative_review"]["target_exposure"], "direct")
        self.assertIn("0%不参与", n8_5["judgement"])
        self.assertIn("N8_5", mermaid)

    def test_premarket_narrative_review_complete_chain_ignores_keep_effect(self):
        workflow = build_selection_workflow(
            target_date="2026-07-01",
            data={
                "premarket_narrative_review": {
                    "original_driver": "AI算力和存储紧缺",
                    "counter_event": {"title": "Meta拟对外出售算力", "source": "CLS", "level": "B"},
                    "overseas_pricing": ["算力租赁商盘前下跌"],
                    "asia_confirmation": ["韩国存储核心低开"],
                    "a_share_mapping": ["半导体", "PCB", "AI算力基础设施"],
                    "target_exposure": "direct",
                    "action_effect": "keep",
                    "status": "保持原计划",
                    "reason_chain": [
                        "AI算力和存储紧缺",
                        "Meta拟对外出售算力",
                        "海外同链下跌",
                        "韩国存储核心确认",
                        "A股AI算力基础设施承压",
                        "太极实业直接暴露",
                    ],
                }
            },
            execution_stage_context={
                "mainline_name": "AI算力基础设施",
                "local_trend_sector_proof": _complete_local_trend_sector_proof("AI算力基础设施"),
                "sector_derived_candidates": [
                    {
                        "name": "太极实业",
                        "code": "600667",
                        "sector": "AI算力基础设施",
                        "anchor_reversal_decision": "可作为主对象",
                        "candidate_role": "板块锚",
                        "sector_derivation_evidence": "AI算力链成交扩散",
                        "current_driver_tags": ["AI算力", "PCB", "半导体"],
                    }
                ],
            },
            position_decision={"target_position_pct": 50},
        )

        review = workflow["premarket_narrative_review"]

        self.assertEqual(review["status"], "不参与")
        self.assertEqual(review["action_effect"], "no_participation")
        self.assertEqual(workflow["final"]["position_pct"], 0)
        self.assertEqual(workflow["final"]["action_text"], "0%不参与")
        self.assertEqual(workflow["final"]["execution_object"], {})
        self.assertEqual(workflow["final"]["source_node"], "N8_5")

    def test_premarket_narrative_review_requires_driver_hit_before_downgrade(self):
        workflow = build_selection_workflow(
            target_date="2026-07-01",
            data={
                "premarket_narrative_review": {
                    "original_driver": "AI算力和存储紧缺",
                    "counter_event": {"title": "国际油价下跌拖累能源链", "source": "CLS", "level": "B"},
                    "overseas_pricing": ["海外能源股走弱"],
                    "asia_confirmation": ["日本航运和能源链低开"],
                    "a_share_mapping": ["航运", "能源"],
                    "target_exposure": "direct",
                    "reason_chain": [
                        "国际油价下跌",
                        "海外能源股走弱",
                        "日本航运和能源链低开",
                        "A股航运能源承压",
                    ],
                }
            },
            execution_stage_context={
                "mainline_name": "AI算力基础设施",
                "broad_market_confirmation": True,
                "local_trend_sector_proof": _complete_local_trend_sector_proof("AI算力基础设施"),
                "sector_derived_candidates": [
                    {
                        "name": "太极实业",
                        "code": "600667",
                        "sector": "AI算力基础设施",
                        "anchor_reversal_decision": "可作为主对象",
                        "candidate_role": "板块锚",
                        "sector_derivation_evidence": "AI算力链成交扩散",
                        "current_driver_tags": ["AI算力", "PCB", "半导体"],
                        "participation_window": "09:30-09:35",
                        "fallback_state": "不满足回到0%",
                    }
                ],
            },
            position_decision={"target_position_pct": 100},
        )

        review = workflow["premarket_narrative_review"]

        self.assertEqual(review["status"], "观察信号")
        self.assertFalse(review["driver_hit"])
        self.assertEqual(review["action_effect"], "keep")
        self.assertEqual(workflow["final"]["position_pct"], 100)
        self.assertEqual(workflow["final"]["source_node"], "N8")

    def test_premarket_narrative_review_keeps_incomplete_chain_observational(self):
        workflow = build_selection_workflow(
            target_date="2026-07-01",
            data={
                "premarket_narrative_review": {
                    "original_driver": "AI算力和存储紧缺",
                    "counter_event": {"title": "Meta拟对外出售算力", "source": "CLS", "level": "B"},
                    "overseas_pricing": ["算力租赁商盘前下跌"],
                    "target_exposure": "unknown",
                    "reason_chain": ["Meta拟对外出售算力", "海外算力租赁商下跌"],
                }
            },
            execution_stage_context={
                "mainline_name": "AI算力基础设施",
                "broad_market_confirmation": True,
                "local_trend_sector_proof": _complete_local_trend_sector_proof("AI算力基础设施"),
                "sector_derived_candidates": [
                    {
                        "name": "太极实业",
                        "code": "600667",
                        "sector": "AI算力基础设施",
                        "anchor_reversal_decision": "可作为主对象",
                        "candidate_role": "板块锚",
                        "sector_derivation_evidence": "AI算力链成交扩散",
                        "participation_window": "09:30-09:35",
                        "fallback_state": "不满足回到0%",
                    }
                ],
            },
            position_decision={"target_position_pct": 100},
        )

        review = workflow["premarket_narrative_review"]

        self.assertEqual(review["status"], "观察信号")
        self.assertEqual(review["action_effect"], "keep")
        self.assertEqual(workflow["final"]["position_pct"], 100)
        self.assertEqual(workflow["final"]["source_node"], "N8")

    def test_render_mermaid_from_workflow_nodes(self):
        workflow = {
            "schema_version": "selection_workflow.v1",
            "nodes": [
                {"node_id": "N1", "node_name": "市场周期判断", "judgement": "允许继续诊断"},
                {"node_id": "N3", "node_name": "板块关系拆解", "judgement": "电力成为窗口方向"},
                {"node_id": "N7", "node_name": "候选对照淘汰", "judgement": "布鲁克斯裁判：价格确认1只"},
                {"node_id": "N8", "node_name": "仓位与执行条件", "judgement": "50%条件执行"},
            ],
            "final": {"execution_object": {"name": "豫能控股", "code": "001896"}, "position_pct": 50},
        }

        mermaid = render_selection_workflow_mermaid(workflow)

        self.assertIn("flowchart TD", mermaid)
        self.assertIn("N1[\"N1 市场周期判断", mermaid)
        self.assertIn("N7[\"N7 候选对照淘汰", mermaid)
        self.assertIn("布鲁克斯", mermaid)
        self.assertIn("布鲁克斯裁判：价格确认1只", mermaid)
        self.assertIn("N8[\"N8 仓位与执行条件", mermaid)
        self.assertIn("豫能控股(001896)", mermaid)
        self.assertIn(
            'N1["N1 市场周期判断<br/>允许继续诊断"]',
            mermaid,
        )
        self.assertIn(
            'FINAL["最终：豫能控股(001896)<br/>仓位：50%"]',
            mermaid,
        )
        self.assertNotIn(r"\n", mermaid)

    def test_render_mermaid_wraps_long_judgement_with_explicit_line_breaks(self):
        workflow = {
            "nodes": [
                {
                    "node_id": "N7",
                    "node_name": "候选对照淘汰",
                    "judgement": "布鲁克斯价格行为裁判：价格确认6只，二次确认0只，风险/分歧0只；共同选择待复核37只",
                }
            ],
            "final": {"position_pct": 0},
        }

        mermaid = render_selection_workflow_mermaid(workflow)
        node_line = next(line for line in mermaid.splitlines() if line.strip().startswith('N7['))
        judgement_lines = node_line.split("<br/>")[1:]

        self.assertGreaterEqual(len(judgement_lines), 3)
        self.assertTrue(all(len(line.rstrip('"]')) <= 22 for line in judgement_lines))


if __name__ == "__main__":
    unittest.main()
