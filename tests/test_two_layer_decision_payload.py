import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.two_layer_decision_payload import (
    build_two_layer_decision_payload,
    render_derivation_audit_layer,
    render_front_decision_layer,
)
from report.sniper_target_derivation import build_sniper_target_derivation_packet, full_section


class TwoLayerDecisionPayloadTest(unittest.TestCase):
    def test_front_decision_layer_uses_percent_position_terms_without_legacy_bucket_words(self):
        payload = build_two_layer_decision_payload(
            target_date="2026-06-04",
            final_target_resolution={
                "display_target": {"name": "豫能控股", "code": "001896", "sector": "电力"},
                "capital_priority_decision": {
                    "capital_priority": "new_entry",
                    "reason": "固定交易窗口条件成立才参与，不满足回到0%",
                },
            },
            position_decision={"target_position_pct": 50},
            execution_stage_context={},
        )

        text = "\n".join(render_front_decision_layer(payload))

        self.assertEqual(payload["front_decision"]["position_plan"], "50%条件执行")
        self.assertEqual(payload["front_decision"]["position_pct"], 50)
        self.assertIn("| 明日仓位 | 条件满足才50%条件执行；不满足回到0% |", text)
        self.assertIn("## 50%条件执行条件", text)
        for forbidden in ("A" + "档", "B" + "档", "C" + "档", "一" + "档", "二" + "档", "三" + "档", "50%" + " / 条件执行"):
            self.assertNotIn(forbidden, text)

    def test_front_decision_uses_selection_workflow_final_object(self):
        workflow = {
            "schema_version": "selection_workflow.v1",
            "final": {
                "execution_object": {"name": "豫能控股", "code": "001896", "sector": "电力"},
                "position_pct": 50,
                "action_text": "50%条件执行，不满足回到0%",
                "source_node": "N8",
            },
            "nodes": [{"node_id": "N8", "node_name": "仓位与执行条件", "judgement": "50%条件执行"}],
            "candidate_pool": [],
        }
        payload = build_two_layer_decision_payload(
            target_date="2026-06-04",
            final_target_resolution={
                "display_target": {"name": "上海石化", "code": "600688"},
                "capital_priority_decision": {"capital_priority": "new_entry"},
            },
            position_decision={"target_position_pct": 50},
            execution_stage_context={"selection_workflow": workflow},
        )

        self.assertEqual(payload["front_decision"]["execution_object"]["code"], "001896")
        self.assertEqual(payload["front_decision"]["position_plan"], "50%条件执行")

    def test_workflow_zero_position_does_not_create_front_execution_object(self):
        workflow = {
            "schema_version": "selection_workflow.v1",
            "final": {
                "execution_object": {},
                "position_pct": 0,
                "action_text": "0%不参与",
                "source_node": "N8",
            },
            "nodes": [{"node_id": "N8", "node_name": "仓位与执行条件", "judgement": "0%不参与"}],
            "candidate_pool": [],
        }
        payload = build_two_layer_decision_payload(
            target_date="2026-06-04",
            final_target_resolution={
                "display_target": {"name": "上海石化", "code": "600688"},
                "capital_priority_decision": {"capital_priority": "new_entry"},
            },
            position_decision={"target_position_pct": 50},
            execution_stage_context={"selection_workflow": workflow},
        )

        self.assertEqual(payload["front_decision"]["execution_object"], {})
        self.assertEqual(payload["front_decision"]["position_plan"], "0%不参与")
        self.assertEqual(payload["b_level_conditions"], {})

    def test_workflow_zero_position_suppresses_stale_resolution_observation_target(self):
        workflow = {
            "schema_version": "selection_workflow.v1",
            "final": {
                "execution_object": {},
                "position_pct": 0,
                "action_text": "0%不参与",
                "source_node": "N8",
            },
            "nodes": [{"node_id": "N8", "node_name": "仓位与执行条件", "judgement": "0%不参与"}],
            "candidate_pool": [],
        }
        payload = build_two_layer_decision_payload(
            target_date="2026-06-04",
            final_target_resolution={
                "watch_target": {"name": "上海石化", "code": "600688", "sector": "炼化及贸"},
                "capital_priority_decision": {"capital_priority": "wait", "reason": "空仓等待"},
            },
            position_decision={"target_position_pct": 50},
            execution_stage_context={"selection_workflow": workflow},
        )

        self.assertEqual(payload["final_object"]["identity"], "无")
        self.assertEqual(payload["final_object"]["stock"], {})
        self.assertEqual(payload["candidate_pool_verdict"]["winner"], {})
        self.assertEqual(payload["front_decision"]["execution_object"], {})
        self.assertEqual(payload["front_decision"]["position_plan"], "0%不参与")

    def test_workflow_zero_position_with_stale_final_object_still_suppresses_observation_target(self):
        workflow = {
            "schema_version": "selection_workflow.v1",
            "final": {
                "execution_object": {"name": "和远气体", "code": "002971", "sector": "化学制品"},
                "position_pct": 0,
                "action_text": "0%不参与",
                "source_node": "N8",
            },
            "nodes": [{"node_id": "N8", "node_name": "仓位与执行条件", "judgement": "0%不参与"}],
            "candidate_pool": [],
        }
        payload = build_two_layer_decision_payload(
            target_date="2026-06-11",
            final_target_resolution={
                "watch_target": {
                    "name": "和远气体",
                    "code": "002971",
                    "sector": "化学制品",
                    "front_observation_qualified": True,
                },
                "capital_priority_decision": {"capital_priority": "wait", "reason": "空仓等待"},
            },
            position_decision={"target_position_pct": 50},
            execution_stage_context={"selection_workflow": workflow},
        )

        self.assertTrue(payload["workflow_zero_position"])
        self.assertEqual(payload["final_object"]["identity"], "无")
        self.assertEqual(payload["final_object"]["stock"], {})
        self.assertEqual(payload["front_decision"]["execution_object"], {})
        self.assertEqual(payload["front_decision"]["position_plan"], "0%不参与")

    def test_workflow_zero_position_suppresses_conflicting_explicit_process_observation(self):
        workflow = {
            "schema_version": "selection_workflow.v1",
            "final": {
                "execution_object": {},
                "position_pct": 0,
                "action_text": "0%不参与",
                "source_node": "N8",
            },
            "nodes": [{"node_id": "N8", "node_name": "仓位与执行条件", "judgement": "0%不参与"}],
            "candidate_pool": [],
        }
        payload = build_two_layer_decision_payload(
            target_date="2026-06-11",
            final_target_resolution={
                "watch_target": {
                    "name": "和远气体",
                    "code": "002971",
                    "sector": "化学制品",
                    "front_observation_qualified": True,
                    "observation_layer": "process_observation",
                    "candidate_role": "过程候选",
                },
                "capital_priority_decision": {"capital_priority": "wait", "reason": "空仓等待"},
            },
            position_decision={"target_position_pct": 50},
            execution_stage_context={"selection_workflow": workflow},
        )

        self.assertEqual(payload["final_object"]["identity"], "无")
        self.assertEqual(payload["final_object"]["stock"], {})
        self.assertEqual(payload["candidate_pool_verdict"]["winner"], {})

    def test_wait_priority_with_process_candidates_keeps_process_summary_visible(self):
        payload = build_two_layer_decision_payload(
            target_date="2026-06-11",
            final_target_resolution={
                "capital_priority_decision": {"capital_priority": "wait", "reason": "空仓等待"},
            },
            position_decision={"target_position_pct": 0},
            execution_stage_context={
                "step2_bundle": {
                    "crossline_observation_stocks": [
                        {"name": "和远气体", "code": "002971", "sector": "化学制品"},
                        {"name": "康强电子", "code": "002119", "sector": "半导体"},
                    ]
                }
            },
        )

        self.assertEqual(payload["final_object"]["identity"], "无")
        self.assertEqual(payload["final_object"]["stock"], {})
        self.assertIn("没有可用明日执行对象；和远气体(002971)保留为过程候选", payload["final_object"]["why_this_not_others"])
        self.assertIn("没有可用明日执行对象；和远气体(002971)保留为过程候选", payload["opening_verdict"]["summary"])
        self.assertGreater(len(payload["candidate_pool_verdict"]["pool_source"]), 0)
        self.assertEqual(payload["front_decision"]["execution_object"], {})

    def test_zero_position_selection_workflow_suppresses_explicit_resolution_target(self):
        workflow = {
            "schema_version": "selection_workflow.v1",
            "final": {
                "execution_object": {},
                "position_pct": 0,
                "action_text": "0%不参与",
                "source_node": "N8",
            },
            "nodes": [{"node_id": "N5", "passes_forward": {"candidate_count": 0}}],
            "candidate_pool": [],
        }
        payload = build_two_layer_decision_payload(
            target_date="2026-06-04",
            final_target_resolution={
                "display_target": {"name": "豫能控股", "code": "001896", "sector": "电力"},
                "capital_priority_decision": {"capital_priority": "new_entry"},
            },
            position_decision={"target_position_pct": 50},
            execution_stage_context={"selection_workflow": workflow},
        )
        text = "\n".join(render_derivation_audit_layer(payload))

        self.assertEqual(payload["front_decision"]["execution_object"], {})
        self.assertEqual(payload["front_decision"]["position_plan"], "0%不参与")
        self.assertEqual(payload["front_decision"]["position_pct"], 0)
        self.assertIn("### 主线推导链", text)
        self.assertIn("#### N5", text)

    def test_front_decision_preserves_selection_workflow_full_position_terms(self):
        workflow = {
            "schema_version": "selection_workflow.v1",
            "final": {
                "execution_object": {"name": "豫能控股", "code": "001896", "sector": "电力"},
                "position_pct": 100,
                "action_text": "100%核心进攻",
                "source_node": "N8",
            },
            "nodes": [{"node_id": "N8", "node_name": "仓位与执行条件", "judgement": "100%核心进攻"}],
            "candidate_pool": [],
        }

        payload = build_two_layer_decision_payload(
            target_date="2026-06-04",
            final_target_resolution={},
            position_decision={"target_position_pct": 0},
            execution_stage_context={"selection_workflow": workflow},
        )
        text = "\n".join(render_front_decision_layer(payload))

        self.assertEqual(payload["front_decision"]["position_pct"], 100)
        self.assertEqual(payload["front_decision"]["position_plan"], "100%核心进攻")
        self.assertEqual(payload["position_stance"]["stance"], "100%核心进攻")
        self.assertIn("| 仓位姿态 | 100%核心进攻 |", text)
        self.assertIn("| 执行性质 | 100%核心进攻 |", text)
        self.assertNotIn("| 仓位姿态 | 50%条件执行 |", text)

    def test_derivation_layer_renders_selection_workflow_nodes_and_candidate_pool(self):
        workflow = {
            "schema_version": "selection_workflow.v1",
            "nodes": [
                {
                    "node_id": "N1",
                    "node_name": "市场周期判断",
                    "judgement": "允许继续诊断",
                    "passes_forward": {"x": "y"},
                    "cannot_conclude": ["不能指定个股"],
                },
                {
                    "node_id": "N6",
                    "node_name": "反推龙头",
                    "judgement": "保留豫能控股",
                    "passes_forward": {},
                    "cannot_conclude": ["不能直接给仓位"],
                },
                {
                    "node_id": "N8",
                    "node_name": "仓位与执行条件",
                    "judgement": "50%条件执行",
                    "passes_forward": {},
                    "cannot_conclude": [],
                },
            ],
            "candidate_pool": [
                {
                    "stock": {"name": "豫能控股", "code": "001896"},
                    "source_pools": ["主线核心"],
                    "entered_reason": "电力窗口方向",
                    "sector_role": "板块锚",
                    "reversal_decision": "可作为主对象",
                    "status": "最终执行对象",
                    "eliminated_reason": "",
                },
                {
                    "stock": {"name": "上海石化", "code": "600688"},
                    "source_pools": ["涨停池"],
                    "entered_reason": "涨停样本",
                    "entry_basis": "涨停样本只能作为过程证据，不能作为新仓入口",
                    "sector_role": "过程候选",
                    "reversal_decision": "降级观察",
                    "status": "降级观察",
                    "eliminated_reason": "不是当前主线核心",
                },
            ],
            "final": {"execution_object": {"name": "豫能控股", "code": "001896"}, "position_pct": 50},
        }
        payload = build_two_layer_decision_payload(
            target_date="2026-06-04",
            final_target_resolution={},
            position_decision={"target_position_pct": 50},
            execution_stage_context={"selection_workflow": workflow},
        )

        text = "\n".join(render_derivation_audit_layer(payload))

        self.assertIn("N1 市场周期判断", text)
        self.assertIn("N6 反推龙头", text)
        self.assertIn("候选生命周期证据", text)
        self.assertIn("豫能控股(001896)", text)
        self.assertIn("上海石化(600688)", text)
        self.assertIn("| 股票 | 首次来源 | 入口处理 |", text)
        self.assertIn("涨停样本只能作为过程证据，不能作为新仓入口", text)
        self.assertLess(text.index("N1 市场周期判断"), text.index("N6 反推龙头"))

    def test_builds_conditional_execution_object_with_b_level_conditions(self):
        payload = build_two_layer_decision_payload(
            target_date="2026-06-04",
            final_target_resolution={
                "watch_target": {"name": "豫能控股", "code": "001896", "sector": "电力"},
                "display_target": {"name": "豫能控股", "code": "001896", "sector": "电力"},
            },
            position_decision={
                "target_position_pct": 50,
                "final_action": "条件满足才50%条件执行；不满足回到0%",
            },
            execution_stage_context={
                "market_state_snapshot": {"market_state": "退潮"},
                "mainline_name": "电力",
                "step2_bundle": {
                    "crossline_observation_stocks": [
                        {"name": "上海石化", "code": "600688", "sector": "炼化及贸"},
                        {"name": "豫能控股", "code": "001896", "sector": "电力"},
                    ]
                },
                "step3_bundle": {
                    "focus_group": [{"name": "豫能控股", "code": "001896"}],
                    "delete_group": [],
                    "keep_group": [],
                },
                "executable_stocks": [{"name": "豫能控股", "code": "001896"}],
                "waiting_stocks": [],
                "rejected_stocks": [],
            },
        )

        self.assertEqual(payload["front_decision"]["execution_object"]["code"], "001896")
        self.assertEqual(payload["front_decision"]["execution_identity"], "明日执行对象")
        self.assertEqual(payload["front_decision"]["position_plan"], "50%条件执行")
        self.assertEqual(payload["front_decision"]["if_fail"], "不参与")
        self.assertIn("low_open_acceptance", payload["b_level_conditions"])
        self.assertIn("active_attack", payload["b_level_conditions"])
        self.assertEqual(payload["position_stance"]["stance"], "50%条件执行")
        self.assertEqual(payload["final_object"]["identity"], "明日执行对象")
        self.assertEqual(payload["final_object"]["stock"]["code"], "001896")
        self.assertEqual(payload["final_object"]["stock"], payload["front_decision"]["execution_object"])
        self.assertEqual(payload["final_object"]["position_stance"], payload["position_stance"]["stance"])
        self.assertIn("execution_conditions", payload["final_object"])
        self.assertIn("failure_conditions", payload["final_object"])
        self.assertTrue(payload["final_object"]["execution_conditions"])
        self.assertTrue(payload["next_day_action"]["checklist"])
        checklist_text = "\n".join(payload["next_day_action"]["checklist"])
        self.assertIn("低开承接型", checklist_text)
        self.assertIn("主动进攻型", checklist_text)
        self.assertIn("09:50-10:10", checklist_text)
        self.assertIn("MA5未收回", checklist_text)

    def test_money_bucket_uses_large_core_threshold_when_amount_is_large(self):
        payload = build_two_layer_decision_payload(
            target_date="2026-06-04",
            final_target_resolution={
                "display_target": {
                    "name": "工业富联",
                    "code": "601138",
                    "sector": "AI算力基础设施",
                    "market_value": 900000000000,
                    "turnover_amount": 18000000000,
                }
            },
            position_decision={"target_position_pct": 50},
            execution_stage_context={},
        )

        active_attack = payload["b_level_conditions"]["active_attack"]
        self.assertEqual(active_attack["money_bucket"], "大市值或高成交核心")
        self.assertIn("1亿+", active_attack["money_confirmation"])

    def test_zero_wait_with_observation_target_does_not_create_b_level_execution(self):
        resolution = {
            "watch_target": {"name": "豫能控股", "code": "001896", "sector": "电力"},
            "capital_priority_decision": {
                "capital_priority": "wait",
                "reason": "空仓等待，禁止参与",
            },
        }
        position_decision = {"target_position_pct": 0, "final_action": "空仓等待"}
        payload = build_two_layer_decision_payload(
            target_date="2026-06-04",
            final_target_resolution=resolution,
            position_decision=position_decision,
            execution_stage_context={},
        )
        packet = build_sniper_target_derivation_packet(
            data={},
            execution_stage_context={},
            market_research_snapshot={},
            final_target_resolution=resolution,
            position_decision=position_decision,
            two_layer_decision_payload=payload,
        )

        text = "\n".join(render_front_decision_layer(payload))

        self.assertEqual(payload["front_decision"]["execution_object"], {})
        self.assertEqual(payload["front_decision"]["execution_identity"], "无明日执行对象")
        self.assertEqual(payload["front_decision"]["position_plan"], "0%不参与")
        self.assertEqual(payload["front_decision"]["position_pct"], 0)
        self.assertEqual(payload["b_level_conditions"], {})
        self.assertEqual(payload["position_stance"]["stance"], "0%不参与")
        self.assertEqual(payload["final_object"]["identity"], "无")
        self.assertEqual(payload["final_object"]["stock"], {})
        self.assertEqual(payload["final_object"]["execution_conditions"], [])
        self.assertEqual(payload["final_object"]["observation_conditions"], [])
        self.assertEqual(payload["next_day_action"]["buy_conditions"], [])
        self.assertTrue(payload["next_day_action"]["checklist"])
        self.assertIn("| 明日执行对象 | 无 |", text)
        self.assertNotIn("| 明日执行对象 | 豫能控股(001896) |", text)
        self.assertNotIn("| 最终对象 | 观察对象：豫能控股(001896) |", text)
        self.assertNotIn("条件满足才50%条件执行", text)
        self.assertEqual(packet["canonical_role"], "观察对象")
        self.assertEqual(packet["canonical_target"], {})
        self.assertEqual(packet["final_action"]["position_pct"], 0)

    def test_downgraded_watch_target_does_not_create_observation_final_object(self):
        payload = build_two_layer_decision_payload(
            target_date="2026-06-05",
            final_target_resolution={
                "watch_target": {
                    "name": "大有能源",
                    "code": "600403",
                    "sector": "煤炭开采",
                    "anchor_reversal_decision": "降级观察",
                    "candidate_role": "观察样本",
                    "candidate_layer": "watch_sample",
                    "execution_eligibility": "observation_only",
                },
                "capital_priority_decision": {
                    "capital_priority": "wait",
                    "reason": "空仓等待，禁止参与",
                },
            },
            position_decision={"target_position_pct": 0, "final_action": "空仓等待"},
            execution_stage_context={},
        )

        self.assertEqual(payload["front_decision"]["execution_object"], {})
        self.assertEqual(payload["final_object"]["identity"], "无")
        self.assertEqual(payload["final_object"]["stock"], {})
        self.assertEqual(payload["position_stance"]["stance"], "0%不参与")

    def test_watch_target_without_execution_priority_stays_observation_even_with_position_pct(self):
        payload = build_two_layer_decision_payload(
            target_date="2026-06-04",
            final_target_resolution={
                "watch_target": {"name": "豫能控股", "code": "001896", "sector": "电力"}
            },
            position_decision={"target_position_pct": 50},
            execution_stage_context={},
        )

        text = "\n".join(render_front_decision_layer(payload))

        self.assertEqual(payload["front_decision"]["execution_object"], {})
        self.assertEqual(payload["front_decision"]["position_plan"], "0%不参与")
        self.assertEqual(payload["b_level_conditions"], {})
        self.assertEqual(payload["final_object"]["identity"], "观察对象")
        self.assertEqual(payload["final_object"]["stock"]["code"], "001896")
        self.assertIn("| 明日执行对象 | 无 |", text)
        self.assertNotIn("| 明日执行对象 | 豫能控股(001896) |", text)

    def test_old_position_priority_with_watch_target_does_not_create_b_level_execution(self):
        payload = build_two_layer_decision_payload(
            target_date="2026-06-04",
            final_target_resolution={
                "display_target": {"name": "华电辽能", "code": "600396", "sector": "电力"},
                "watch_target": {"name": "豫能控股", "code": "001896", "sector": "电力"},
                "capital_priority_decision": {
                    "capital_priority": "old_position_t",
                    "reason": "先处理旧仓，新机会只保留观察对象",
                },
            },
            position_decision={"target_position_pct": 0, "final_action": "旧仓优先；新机会0%不参与"},
            execution_stage_context={
                "executable_stocks": [{"name": "豫能控股", "code": "001896", "sector": "电力"}],
            },
        )
        text = "\n".join(render_front_decision_layer(payload))

        self.assertEqual(payload["front_decision"]["execution_object"], {})
        self.assertEqual(payload["front_decision"]["execution_identity"], "无明日执行对象")
        self.assertEqual(payload["front_decision"]["position_plan"], "0%不参与")
        self.assertEqual(payload["b_level_conditions"], {})
        self.assertIn("| 明日执行对象 | 无 |", text)
        self.assertNotIn("| 明日执行对象 | 豫能控股(001896) |", text)

    def test_zero_position_new_entry_priority_can_render_conditional_b_level_execution(self):
        payload = build_two_layer_decision_payload(
            target_date="2026-06-04",
            final_target_resolution={
                "watch_target": {"name": "豫能控股", "code": "001896", "sector": "电力"},
                "display_target": {"name": "豫能控股", "code": "001896", "sector": "电力"},
                "capital_priority_decision": {
                    "capital_priority": "new_entry",
                    "reason": "固定交易窗口条件成立才参与，不满足回到0%",
                },
            },
            position_decision={"target_position_pct": 0, "final_action": "条件满足才50%条件执行；不满足回到0%"},
            execution_stage_context={},
        )

        text = "\n".join(render_front_decision_layer(payload))

        self.assertEqual(payload["front_decision"]["position_plan"], "50%条件执行")
        self.assertEqual(payload["front_decision"]["position_pct"], 50)
        self.assertIn("| 明日仓位 | 条件满足才50%条件执行；不满足回到0% |", text)
        self.assertNotIn("条件满足才0%不参与", text)

    def test_process_target_only_does_not_create_execution_object(self):
        payload = build_two_layer_decision_payload(
            target_date="2026-05-21",
            final_target_resolution={
                "new_entry_target": {"name": "华微电子", "code": "600360", "sector": "半导体"},
                "process_target": {"name": "华微电子", "code": "600360", "sector": "半导体"},
                "capital_priority_decision": {
                    "capital_priority": "wait",
                    "reason": "缺少可执行对象，保持观察",
                },
            },
            position_decision={
                "target_position_pct": 0,
                "final_action": "0%不参与；只保留观察",
            },
            execution_stage_context={},
        )

        text = "\n".join(render_front_decision_layer(payload))

        self.assertEqual(payload["front_decision"]["execution_object"], {})
        self.assertEqual(payload["front_decision"]["execution_identity"], "无明日执行对象")
        self.assertEqual(payload["front_decision"]["position_plan"], "0%不参与")
        self.assertEqual(payload["b_level_conditions"], {})
        self.assertEqual(payload["final_object"]["identity"], "无")
        self.assertEqual(payload["final_object"]["stock"], {})
        self.assertEqual(payload["final_object"]["execution_conditions"], [])
        self.assertEqual(payload["candidate_pool_verdict"]["winner"], {})
        self.assertTrue(payload["next_day_action"]["checklist"])
        self.assertIn("| 明日执行对象 | 无 |", text)

    def test_candidate_pool_loser_reason_uses_available_dimensions(self):
        payload = build_two_layer_decision_payload(
            target_date="2026-06-04",
            final_target_resolution={
                "display_target": {"name": "豫能控股", "code": "001896", "sector": "电力"},
                "capital_priority_decision": {
                    "capital_priority": "new_entry",
                    "reason": "固定交易窗口条件成立才参与，不满足回到0%",
                },
            },
            position_decision={"target_position_pct": 50},
            execution_stage_context={
                "step2_bundle": {
                    "crossline_observation_stocks": [
                        {
                            "name": "上海石化",
                            "code": "600688",
                            "sector": "炼化及贸",
                            "reason": "最终解析未选为观察对象",
                            "funds_confirmation": "脉冲",
                            "stock_structure": "失速",
                        },
                        {"name": "豫能控股", "code": "001896", "sector": "电力"},
                    ],
                }
            },
        )

        verdict = payload["candidate_pool_verdict"]
        loser = verdict["important_losers"][0]

        self.assertEqual(verdict["winner"]["stock"]["code"], "001896")
        self.assertIn("dimension_labels", verdict["winner"])
        self.assertIn("dimension_labels", loser)
        self.assertIn("dimension_results", verdict["winner"])
        self.assertIn("dimension_results", loser)
        self.assertIn("loss_reason", loser)
        self.assertNotIn("最终解析", loser["loss_reason"])
        self.assertIn(loser["dimension_labels"]["funds_confirmation"], loser["loss_reason"])
        self.assertIn(loser["dimension_labels"]["stock_structure"], loser["loss_reason"])
        self.assertIn("上海石化(600688)未胜出", payload["final_object"]["why_this_not_others"])
        self.assertNotIn("最终解析", payload["final_object"]["why_this_not_others"])

    def test_candidate_pool_winner_and_top3_losers_share_five_dimensions(self):
        payload = build_two_layer_decision_payload(
            target_date="2026-06-04",
            final_target_resolution={
                "display_target": {
                    "name": "豫能控股",
                    "code": "001896",
                    "sector": "电力",
                    "stock_structure": "承接",
                    "funds_confirmation": "可用",
                },
                "capital_priority_decision": {"capital_priority": "new_entry"},
            },
            position_decision={"target_position_pct": 50},
            execution_stage_context={
                "mainline_name": "电力",
                "waiting_stocks": [
                    {
                        "name": "上海石化",
                        "code": "600688",
                        "sector": "炼化及贸",
                        "stock_structure": "失速",
                        "funds_confirmation": "脉冲",
                    },
                    {
                        "name": "东方精工",
                        "code": "002611",
                        "sector": "机器人",
                        "risk_missing_data": "风险偏高",
                    },
                ],
                "rejected_stocks": [
                    {
                        "name": "广安爱众",
                        "code": "600979",
                        "sector": "电力",
                        "account_fit": "不适合",
                    }
                ],
            },
        )

        expected_keys = {
            "mainline_sector",
            "stock_structure",
            "funds_confirmation",
            "account_fit",
            "risk_missing_data",
        }
        verdict = payload["candidate_pool_verdict"]
        rows = [verdict["winner"], *verdict["downgraded_or_rejected_top3"]]

        self.assertEqual(verdict["winner"]["stock"]["code"], payload["final_object"]["stock"]["code"])
        self.assertGreaterEqual(len(verdict["downgraded_or_rejected_top3"]), 3)
        for row in rows:
            with self.subTest(stock=row["stock"]):
                self.assertEqual(set(row["dimension_results"]), expected_keys)

    def test_duplicate_candidate_sources_are_merged_in_same_pool(self):
        payload = build_two_layer_decision_payload(
            target_date="2026-06-04",
            final_target_resolution={
                "display_target": {"name": "豫能控股", "code": "001896", "sector": "电力"},
                "process_target": {"name": "上海石化", "code": "600688", "sector": "炼化及贸"},
                "capital_priority_decision": {"capital_priority": "new_entry"},
            },
            position_decision={"target_position_pct": 50},
            execution_stage_context={
                "step2_bundle": {
                    "crossline_observation_stocks": [
                        {"name": "上海石化", "code": "600688", "sector": "炼化及贸"}
                    ]
                },
                "waiting_stocks": [{"name": "上海石化", "code": "600688", "sector": "炼化及贸"}],
            },
        )

        loser = payload["candidate_pool_verdict"]["downgraded_or_rejected_top3"][0]

        self.assertEqual(loser["stock"]["code"], "600688")
        self.assertIn("过程候选", loser["pool_source"])
        self.assertIn("跨线观察池", loser["pool_source"])
        self.assertIn("等待池", loser["pool_source"])
        self.assertIn("过程候选", loser["pool_sources"])
        self.assertIn("跨线观察池", loser["pool_sources"])
        self.assertIn("等待池", loser["pool_sources"])

    def test_why_this_not_others_names_loser_and_dimension_reason(self):
        payload = build_two_layer_decision_payload(
            target_date="2026-06-04",
            final_target_resolution={
                "display_target": {"name": "豫能控股", "code": "001896", "sector": "电力"},
                "capital_priority_decision": {"capital_priority": "new_entry"},
            },
            position_decision={"target_position_pct": 50},
            execution_stage_context={
                "mainline_name": "电力",
                "waiting_stocks": [
                    {
                        "name": "上海石化",
                        "code": "600688",
                        "sector": "炼化及贸",
                        "reason": "最终解析未选为观察对象",
                        "stock_structure": "失速",
                        "funds_confirmation": "脉冲",
                    }
                ],
            },
        )

        why = payload["final_object"]["why_this_not_others"]

        self.assertIn("豫能控股(001896)", why)
        self.assertIn("上海石化(600688)", why)
        self.assertIn("失速", why)
        self.assertIn("脉冲", why)
        self.assertNotIn("最终解析", why)

    def test_opening_final_and_next_day_action_use_same_identity(self):
        payload = build_two_layer_decision_payload(
            target_date="2026-06-04",
            final_target_resolution={
                "display_target": {"name": "豫能控股", "code": "001896", "sector": "电力"},
                "capital_priority_decision": {
                    "capital_priority": "new_entry",
                    "reason": "固定交易窗口条件成立才参与，不满足回到0%",
                },
            },
            position_decision={"target_position_pct": 50},
            execution_stage_context={
                "waiting_stocks": [{"name": "上海石化", "code": "600688", "sector": "炼化及贸"}],
            },
        )

        final_object = payload["final_object"]

        self.assertEqual(payload["opening_verdict"]["final_object_identity"], final_object["identity"])
        self.assertEqual(payload["opening_verdict"]["stock"]["code"], final_object["stock"]["code"])
        self.assertEqual(payload["next_day_action"]["final_object_identity"], final_object["identity"])
        self.assertEqual(payload["next_day_action"]["stock"]["code"], final_object["stock"]["code"])
        self.assertEqual(payload["candidate_pool_verdict"]["winner"]["stock"]["code"], final_object["stock"]["code"])

    def test_front_decision_layer_renders_opening_verdict_summary(self):
        payload = build_two_layer_decision_payload(
            target_date="2026-06-04",
            final_target_resolution={
                "display_target": {"name": "豫能控股", "code": "001896", "sector": "电力"},
                "capital_priority_decision": {"capital_priority": "new_entry"},
            },
            position_decision={"target_position_pct": 50},
            execution_stage_context={
                "waiting_stocks": [
                    {
                        "name": "上海石化",
                        "code": "600688",
                        "sector": "炼化及贸",
                        "stock_structure": "失速",
                        "funds_confirmation": "脉冲",
                    }
                ],
            },
        )

        text = "\n".join(render_front_decision_layer(payload))

        self.assertLess(text.index("## 日报裁决总览"), text.index("## 明日执行结论"))
        self.assertIn("| 最终对象 | 明日执行对象：豫能控股(001896) |", text)
        self.assertIn("### 候选胜负摘要", text)
        self.assertIn("上海石化(600688)", text)
        self.assertIn("失速", text)
        self.assertIn("脉冲", text)

    def test_empty_execution_object_derivation_stays_zero_position_without_placeholder_target(self):
        payload = build_two_layer_decision_payload(
            target_date="2026-05-21",
            final_target_resolution={
                "new_entry_target": {"name": "华微电子", "code": "600360", "sector": "半导体"},
                "process_target": {"name": "华微电子", "code": "600360", "sector": "半导体"},
            },
            position_decision={"target_position_pct": 0},
            execution_stage_context={
                "waiting_stocks": [{"name": "华微电子", "code": "600360", "sector": "半导体"}],
                "rejected_stocks": [{"name": "上海石化", "code": "600688", "sector": "炼化及贸"}],
            },
        )

        text = "\n".join(render_derivation_audit_layer(payload))

        self.assertIn("### Step 1：市场是否值得出手", text)
        self.assertIn("- 不做新仓", text)
        self.assertIn("- 不新增参与", text)
        self.assertIn("### Step 4：明天只做什么", text)
        self.assertIn("明日动作：空仓等待或只处理旧仓", text)
        self.assertNotIn("条件执行对象：暂无", text)
        self.assertNotIn("暂无作为条件执行对象", text)
        self.assertNotIn("暂无进入50%条件执行计划", text)

    def test_wait_zero_watch_target_stays_process_evidence_in_derivation_audit(self):
        payload = build_two_layer_decision_payload(
            target_date="2026-06-04",
            final_target_resolution={
                "watch_target": {"name": "豫能控股", "code": "001896", "sector": "电力"},
                "capital_priority_decision": {"capital_priority": "wait", "reason": "空仓等待"},
            },
            position_decision={"target_position_pct": 0},
            execution_stage_context={
                "step2_bundle": {
                    "crossline_observation_stocks": [
                        {"name": "上海石化", "code": "600688"},
                        {"name": "豫能控股", "code": "001896"},
                    ]
                },
            },
        )

        text = "\n".join(render_derivation_audit_layer(payload))

        self.assertIn("无保留对象", text)
        self.assertIn("明日动作：空仓等待或只处理旧仓", text)
        self.assertNotIn("保留对象：豫能控股(001896)", text)
        self.assertNotIn("明日动作：只观察豫能控股(001896)，不新增参与", text)
        self.assertNotIn("淘汰：上海石化(600688)、豫能控股(001896)", text)
        self.assertNotIn("淘汰对象：上海石化(600688)、豫能控股(001896)", text)
        self.assertIn("不参与", text)

    def test_placeholder_target_names_do_not_create_execution_object(self):
        for placeholder in ("无", "暂无", "-"):
            with self.subTest(placeholder=placeholder):
                payload = build_two_layer_decision_payload(
                    target_date="2026-05-21",
                    final_target_resolution={
                        "display_target": {"name": placeholder, "code": ""},
                    },
                    position_decision={"target_position_pct": 50},
                    execution_stage_context={},
                )

                text = "\n".join(render_derivation_audit_layer(payload))

                self.assertEqual(payload["front_decision"]["execution_object"], {})
                self.assertEqual(payload["front_decision"]["position_plan"], "0%不参与")
                self.assertNotIn(f"条件执行对象：{placeholder}", text)

    def test_wait_priority_executable_stock_does_not_create_execution_object(self):
        payload = build_two_layer_decision_payload(
            target_date="2026-06-04",
            final_target_resolution={
                "new_entry_target": {"name": "豫能控股", "code": "001896", "sector": "电力"},
                "process_target": {"name": "豫能控股", "code": "001896", "sector": "电力"},
                "capital_priority_decision": {
                    "capital_priority": "wait",
                    "reason": "盘中条件确认后执行",
                },
            },
            position_decision={"target_position_pct": 0},
            execution_stage_context={
                "executable_stocks": [{"name": "豫能控股", "code": "001896", "sector": "电力"}],
            },
        )

        text = "\n".join(render_front_decision_layer(payload))

        self.assertEqual(payload["front_decision"]["execution_object"], {})
        self.assertEqual(payload["front_decision"]["execution_identity"], "无明日执行对象")
        self.assertEqual(payload["front_decision"]["position_plan"], "0%不参与")
        self.assertIn("| 明日执行对象 | 无 |", text)

    def test_executable_stock_without_final_resolution_does_not_create_winner(self):
        payload = build_two_layer_decision_payload(
            target_date="2026-06-04",
            final_target_resolution={
                "process_target": {"name": "豫能控股", "code": "001896", "sector": "电力"},
                "capital_priority_decision": {
                    "capital_priority": "new_entry",
                    "reason": "盘中条件确认后执行",
                },
            },
            position_decision={"target_position_pct": 50},
            execution_stage_context={
                "executable_stocks": [{"name": "豫能控股", "code": "001896", "sector": "电力"}],
            },
        )

        text = "\n".join(render_front_decision_layer(payload))

        self.assertEqual(payload["front_decision"]["execution_object"], {})
        self.assertEqual(payload["front_decision"]["execution_identity"], "无明日执行对象")
        self.assertEqual(payload["front_decision"]["position_plan"], "0%不参与")
        self.assertEqual(payload["candidate_pool_verdict"]["winner"], {})
        self.assertEqual(payload["final_object"]["stock"], {})
        self.assertIn("| 明日执行对象 | 无 |", text)

    def test_render_front_decision_layer_uses_execution_object_not_passive_wording(self):
        payload = build_two_layer_decision_payload(
            target_date="2026-06-04",
            final_target_resolution={
                "watch_target": {"name": "豫能控股", "code": "001896", "sector": "电力"},
                "capital_priority_decision": {"capital_priority": "new_entry"},
            },
            position_decision={"target_position_pct": 50},
            execution_stage_context={},
        )

        text = "\n".join(render_front_decision_layer(payload))

        self.assertIn("## 明日执行结论", text)
        self.assertIn("| 明日执行对象 | 豫能控股(001896) |", text)
        self.assertIn("## 50%条件执行条件", text)
        self.assertIn("低开承接型", text)
        self.assertIn("主动进攻型", text)
        self.assertNotIn("观察" + "锚", text)

    def test_render_derivation_audit_layer_uses_required_step_template(self):
        payload = build_two_layer_decision_payload(
            target_date="2026-06-04",
            final_target_resolution={
                "watch_target": {"name": "豫能控股", "code": "001896", "sector": "电力"}
            },
            position_decision={"target_position_pct": 50},
            execution_stage_context={
                "step2_bundle": {
                    "crossline_observation_stocks": [
                        {"name": "上海石化", "code": "600688"},
                        {"name": "豫能控股", "code": "001896"},
                    ]
                },
                "step3_bundle": {"focus_group": [{"name": "豫能控股", "code": "001896"}]},
            },
        )

        text = "\n".join(render_derivation_audit_layer(payload))

        self.assertIn("## 推导审计层", text)
        self.assertIn("### Step 1：市场是否值得出手", text)
        self.assertIn("### Step 2：主线与龙头身份是否清楚", text)
        self.assertIn("### Step 3：承接和证据是否撑得住", text)
        self.assertIn("### Step 4：明天只做什么", text)
        self.assertNotIn("### Step 0", text)
        self.assertNotIn("### Step 5", text)
        self.assertNotIn("#### 输入数据", text)
        self.assertNotIn("#### 保留与淘汰", text)
        self.assertIn("#### 结论", text)
        self.assertIn("#### 证据", text)
        self.assertIn("#### 动作", text)
        self.assertLess(text.index("主线与龙头身份是否清楚"), text.index("承接和证据是否撑得住"))
        self.assertIn("豫能控股(001896)", text)

    def test_derivation_layer_places_limit_up_evidence_after_anchor_identity(self):
        payload = build_two_layer_decision_payload(
            target_date="2026-06-05",
            final_target_resolution={
                "watch_target": {"name": "大有能源", "code": "600403", "sector": "煤炭"},
                "capital_priority_decision": {"capital_priority": "wait", "reason": "0%不参与"},
            },
            position_decision={"target_position_pct": 0, "final_action": "0%不参与"},
            execution_stage_context={
                "market_state_snapshot": {"market_state": "收缩防守"},
                "mainline_name": "无确认主攻线",
                "step2_bundle": {
                    "crossline_observation_stocks": [
                        {
                            "name": "大有能源",
                            "code": "600403",
                            "sector": "煤炭",
                            "pattern": "涨停",
                            "anchor_reversal_decision": "降级观察",
                            "sector_anchor": "兆易创新(603986)",
                            "candidate_role": "跟风样本",
                            "why_not_anchor": "无法替代板块锚",
                            "limit_up_evidence_role": "涨停只作观察证据",
                        }
                    ]
                },
            },
        )

        text = "\n".join(render_derivation_audit_layer(payload))

        self.assertLess(text.index("板块锚"), text.index("涨停"))
        self.assertIn("无法替代板块锚", text)
        self.assertIn("涨停只作观察证据", text)
        self.assertIn("无保留对象", text)

    def test_sniper_derivation_uses_candidate_loss_reason_for_replaced_process_candidate(self):
        payload = build_two_layer_decision_payload(
            target_date="2026-06-04",
            final_target_resolution={
                "watch_target": {"name": "豫能控股", "code": "001896", "sector": "电力"},
                "capital_priority_decision": {"capital_priority": "wait", "reason": "空仓等待"},
            },
            position_decision={"target_position_pct": 0},
            execution_stage_context={
                "watch_anchor": {"name": "上海石化", "code": "600688", "sector": "炼化及贸"},
                "step2_bundle": {
                    "crossline_observation_stocks": [
                        {
                            "name": "上海石化",
                            "code": "600688",
                            "sector": "炼化及贸",
                            "stock_structure": "放量T字板",
                            "funds_confirmation": "资金脉冲",
                        },
                        {"name": "豫能控股", "code": "001896", "sector": "电力"},
                    ]
                },
            },
        )
        packet = build_sniper_target_derivation_packet(
            data={},
            execution_stage_context={
                "watch_anchor": {"name": "上海石化", "code": "600688", "sector": "炼化及贸"},
            },
            market_research_snapshot={},
            final_target_resolution={
                "watch_target": {"name": "豫能控股", "code": "001896", "sector": "电力"},
                "capital_priority_decision": {"capital_priority": "wait", "reason": "空仓等待"},
            },
            position_decision={"target_position_pct": 0},
            two_layer_decision_payload=payload,
        )

        text = "\n".join(full_section(packet))

        self.assertEqual("", text)
        self.assertNotIn("候选=上海石化(600688) 身份=过程候选 去向=被替换", text)
        self.assertNotIn("放量T字板", text)
        self.assertNotIn("资金脉冲", text)
        self.assertNotIn("最终解析未选为最终观察对象", text)


if __name__ == "__main__":
    unittest.main()
