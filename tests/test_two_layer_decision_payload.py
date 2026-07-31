import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.two_layer_decision_payload import (
    _position_stance_payload,
    build_two_layer_decision_payload,
    render_derivation_audit_layer,
    render_front_decision_layer,
)
from report.execution_wording import (
    PREMARKET_50_EXECUTION_TEXT,
    PREMARKET_50_TRIGGER_TEXT,
    PREMARKET_FULL_EXECUTION_TEXT,
    SAME_STOCK_T_CONFIRMATION_CLAUSE,
    TWO_B_CONFIRMATION_CLAUSE,
)
from report.sniper_target_derivation import build_sniper_target_derivation_packet, full_section


class TwoLayerDecisionPayloadTest(unittest.TestCase):
    def test_position_stance_does_not_default_target_without_plan_to_b1(self):
        stance = _position_stance_payload(
            {"name": "深科技", "code": "000021"},
            {},
            "new_entry",
            {},
            {},
            "",
        )

        self.assertEqual(stance["stance"], "0%不参与")
        self.assertIn("结构化仓位缺失", stance["reason_from_funds"])
        self.assertNotIn("已决定50%", stance["passes_forward"])

    def test_target_without_structured_position_plan_does_not_default_to_b1(self):
        payload = build_two_layer_decision_payload(
            target_date="2026-07-19",
            final_target_resolution={
                "display_target": {"name": "深科技", "code": "000021"},
                "capital_priority_decision": {"capital_priority": "new_entry"},
            },
            position_decision={"target_position_pct": 0},
        )

        self.assertEqual(payload["front_decision"]["execution_object"], {})
        self.assertEqual(payload["front_decision"]["position_pct"], 0)
        self.assertEqual(payload["front_decision"]["position_plan"], "0%不参与")
        self.assertEqual(payload["b_level_conditions"], {})

    def test_same_stock_existing_1x_and_planned_1x_renders_zero_new_entry(self):
        target = {"name": "太极实业", "code": "600667", "sector": "半导体"}
        policy = "同股计划总档1x/50%已由现有仓位满足；维持1x/50%，本计划不追加B2"
        exposure_plan = {
            "schema_version": "position_tier_exposure.v2",
            "position_fact_status": "confirmed",
            "old_position_pct": 50,
            "planned_new_entry_pct": 50,
            "planned_new_entry_x": 1,
            "new_entry_pct": 0,
            "new_entry_x": 0,
            "same_stock_target": True,
            "same_stock_t": False,
            "policy": policy,
        }
        payload = build_two_layer_decision_payload(
            target_date="2026-07-19",
            final_target_resolution={
                "new_entry_target": target,
                "display_target": target,
                "existing_position_target": {**target, "position_pct": 50},
                "capital_priority_decision": {"capital_priority": "new_entry", "reason": policy},
                "account_exposure_plan": exposure_plan,
            },
            position_decision={"target_position_pct": 50},
        )

        text = "\n".join(render_front_decision_layer(payload))

        self.assertEqual(payload["account_exposure_plan"], exposure_plan)
        self.assertEqual(payload["front_decision"]["execution_object"]["code"], "600667")
        self.assertEqual(payload["front_decision"]["execution_identity"], "明日计划对象")
        self.assertEqual(payload["front_decision"]["position_pct"], 0)
        self.assertEqual(payload["front_decision"]["planned_position_pct"], 50)
        self.assertEqual(payload["b_level_conditions"], {})
        self.assertIn("| 明日新仓 | 0%新增；现有1x/50%已满足计划总档1x/50%，不追加B2 |", text)
        self.assertIn("| 明日计划对象 | 太极实业(600667) |", text)
        self.assertNotIn(PREMARKET_50_EXECUTION_TEXT, text)

    def test_same_stock_existing_1x_and_planned_2x_renders_only_b2_increment(self):
        target = {"name": "太极实业", "code": "600667", "sector": "半导体"}
        policy = (
            f"同股T：{SAME_STOCK_T_CONFIRMATION_CLAUSE}；"
            "B2确认后总仓位到2x/100%，确认失败保持1x/50%或更低"
        )
        payload = build_two_layer_decision_payload(
            target_date="2026-07-19",
            final_target_resolution={
                "new_entry_target": target,
                "display_target": target,
                "existing_position_target": {**target, "position_pct": 50},
                "capital_priority_decision": {"capital_priority": "new_entry", "reason": policy},
                "account_exposure_plan": {
                    "schema_version": "position_tier_exposure.v2",
                    "position_fact_status": "confirmed",
                    "old_position_pct": 50,
                    "planned_new_entry_pct": 100,
                    "planned_new_entry_x": 2,
                    "new_entry_pct": 50,
                    "new_entry_x": 1,
                    "same_stock_target": True,
                    "same_stock_t": True,
                    "policy": policy,
                },
            },
            position_decision={"target_position_pct": 100},
        )

        text = "\n".join(render_front_decision_layer(payload))

        self.assertEqual(payload["front_decision"]["position_pct"], 50)
        self.assertEqual(payload["front_decision"]["planned_position_pct"], 100)
        self.assertIn("| 明日新仓 | 新增1x/50%=B2；已有1x/50%视为B1，B2确认后总仓位到2x/100% |", text)
        self.assertIn(SAME_STOCK_T_CONFIRMATION_CLAUSE, text)
        self.assertNotIn(PREMARKET_50_EXECUTION_TEXT, text)

    def test_different_stock_existing_2x_keeps_target_waiting_for_release(self):
        target = {"name": "深科技", "code": "000021", "sector": "半导体"}
        policy = "账户已有2x/100%；新仓只在旧仓释放后执行，账户总仓位不超过2x/100%"
        payload = build_two_layer_decision_payload(
            target_date="2026-07-19",
            final_target_resolution={
                "new_entry_target": target,
                "display_target": target,
                "existing_position_target": {"name": "太极实业", "code": "600667", "position_pct": 100},
                "capital_priority_decision": {
                    "capital_priority": "new_entry_after_old_exit",
                    "reason": policy,
                },
                "account_exposure_plan": {
                    "schema_version": "position_tier_exposure.v2",
                    "position_fact_status": "confirmed",
                    "old_position_pct": 100,
                    "planned_new_entry_pct": 50,
                    "planned_new_entry_x": 1,
                    "new_entry_pct": 0,
                    "new_entry_x": 0,
                    "same_stock_target": False,
                    "same_stock_t": False,
                    "policy": policy,
                },
            },
            position_decision={"target_position_pct": 50},
        )

        text = "\n".join(render_front_decision_layer(payload))

        self.assertEqual(payload["front_decision"]["execution_object"]["code"], "000021")
        self.assertEqual(payload["front_decision"]["execution_identity"], "明日计划对象")
        self.assertEqual(payload["front_decision"]["position_pct"], 0)
        self.assertEqual(payload["b_level_conditions"], {})
        self.assertIn("| 明日新仓 | 0%新增；保留计划总档1x/50%，旧仓释放后执行 |", text)
        self.assertIn("| 明日计划对象 | 深科技(000021) |", text)
        self.assertIn("旧仓释放后执行", text)

    def test_front_decision_layer_uses_percent_position_terms_without_legacy_bucket_words(self):
        payload = build_two_layer_decision_payload(
            target_date="2026-06-04",
            final_target_resolution={
                "display_target": {"name": "豫能控股", "code": "001896", "sector": "电力"},
                "capital_priority_decision": {
                    "capital_priority": "new_entry",
                    "reason": "按昨晚预案检查执行资格；不满足回到0%不参与",
                },
            },
            position_decision={"target_position_pct": 50},
            execution_stage_context={},
        )

        text = "\n".join(render_front_decision_layer(payload))

        self.assertEqual(payload["front_decision"]["position_plan"], "50%条件执行")
        self.assertEqual(payload["front_decision"]["position_pct"], 50)
        self.assertIn(f"| 明日新仓 | {PREMARKET_50_EXECUTION_TEXT} |", text)
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

    def test_workflow_candidate_pool_excludes_conflicting_legacy_containers(self):
        workflow = {
            "schema_version": "selection_workflow.v1",
            "final": {
                "execution_object": {"name": "豫能控股", "code": "001896", "sector": "电力"},
                "position_pct": 50,
                "action_text": "50%条件执行",
            },
            "candidate_pool": [
                {
                    "stock": {"name": "豫能控股", "code": "001896", "sector": "电力"},
                    "source_pools": ["sector_derived_candidates"],
                    "status": "最终执行对象",
                    "candidate_origin": "sector_first",
                    "new_entry_qualified": True,
                }
            ],
        }
        payload = build_two_layer_decision_payload(
            target_date="2026-07-29",
            final_target_resolution={
                "display_target": {"name": "明新旭腾", "code": "605068"},
                "capital_priority_decision": {"capital_priority": "new_entry"},
            },
            position_decision={"target_position_pct": 50},
            execution_stage_context={
                "selection_workflow": workflow,
                "step2_bundle": {
                    "core_stocks": [{"name": "明新旭腾", "code": "605068"}],
                },
                "waiting_stocks": [{"name": "上海石化", "code": "600688"}],
            },
        )

        pool_codes = [row["stock"]["code"] for row in payload["candidate_pool_verdict"]["pool_source"]]
        self.assertEqual(pool_codes, ["001896"])
        self.assertEqual(payload["front_decision"]["execution_object"]["code"], "001896")

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

    def test_workflow_empty_final_dict_still_owns_zero_result(self):
        payload = build_two_layer_decision_payload(
            target_date="2026-07-29",
            final_target_resolution={
                "new_entry_target": {"name": "旧对象", "code": "000001"},
                "display_target": {"name": "旧对象", "code": "000001"},
                "capital_priority_decision": {
                    "capital_priority": "new_entry",
                    "reason": "旧解析结果",
                },
            },
            position_decision={"target_position_pct": 50},
            execution_stage_context={
                "selection_workflow": {
                    "schema_version": "selection_workflow.v1",
                    "final": {},
                    "candidate_pool": [],
                }
            },
        )

        self.assertEqual(payload["front_decision"]["execution_object"], {})
        self.assertEqual(payload["front_decision"]["position_pct"], 0)
        self.assertEqual(payload["front_decision"]["position_plan"], "0%不参与")
        self.assertEqual(payload["b_level_conditions"], {})

    def test_zero_position_derivation_uses_process_only_candidate_projection(self):
        workflow = {
            "schema_version": "selection_workflow.v1",
            "final": {
                "execution_object": {},
                "position_pct": 0,
                "action_text": "0%不参与",
            },
            "nodes": [],
            "candidate_pool": [
                {
                    "stock": {"name": "明新旭腾", "code": "605068", "sector": "汽车配件"},
                    "sector": "汽车配件",
                    "source_pools": ["extreme_conviction_list"],
                    "workflow_path": ["N5", "N6", "N7"],
                    "process_rejection_reason": "价格行为未通过确认；未证明来自板块资金方向",
                    "entry_basis": "09:50-10:10站上18.72后可作为主对象",
                    "sector_role": "板块锚",
                    "reversal_decision": "可作为主对象",
                    "eliminated_reason": "失效价17.78",
                    "status": "过程候选",
                }
            ],
        }
        payload = build_two_layer_decision_payload(
            target_date="2026-07-29",
            final_target_resolution={
                "capital_priority_decision": {"capital_priority": "wait"},
            },
            position_decision={"target_position_pct": 0},
            execution_stage_context={"selection_workflow": workflow},
        )

        front_text = "\n".join(render_front_decision_layer(payload))
        audit_text = "\n".join(render_derivation_audit_layer(payload))

        self.assertIn("| 明日执行对象 | 无 |", front_text)
        self.assertIn("### 候选过程回放", audit_text)
        self.assertIn(
            "| 明新旭腾(605068) | 汽车配件 | extreme_conviction_list | N5 -> N6 -> N7 | 价格行为未通过确认；未证明来自板块资金方向 | 只作过程回放，不新增参与 |",
            audit_text,
        )
        self.assertNotIn("板块锚", audit_text)
        self.assertNotIn("可作为主对象", audit_text)
        self.assertNotIn("09:50-10:10", audit_text)
        self.assertNotIn("18.72", audit_text)
        self.assertNotIn("17.78", audit_text)

    def test_workflow_non_tier_position_does_not_create_execution_or_plan_object(self):
        target = {"name": "豫能控股", "code": "001896", "sector": "电力"}
        for position_pct in (33, 75, None):
            with self.subTest(position_pct=position_pct):
                workflow = {
                    "schema_version": "selection_workflow.v1",
                    "final": {
                        "execution_object": target,
                        "position_pct": position_pct,
                        "action_text": "旧文案不能替代结构化仓位",
                        "source_node": "N8",
                    },
                    "nodes": [
                        {
                            "node_id": "N8",
                            "node_name": "仓位与执行条件",
                            "judgement": "仓位待复核",
                        }
                    ],
                    "candidate_pool": [],
                }
                payload = build_two_layer_decision_payload(
                    target_date="2026-07-19",
                    final_target_resolution={
                        "display_target": target,
                        "capital_priority_decision": {
                            "capital_priority": "new_entry",
                            "reason": "对象身份不能替代仓位事实",
                        },
                    },
                    position_decision={
                        "target_position_pct": 50,
                        "final_action": "旧文案不能替代结构化仓位",
                    },
                    execution_stage_context={"selection_workflow": workflow},
                )

                front_text = "\n".join(render_front_decision_layer(payload))
                audit_text = "\n".join(render_derivation_audit_layer(payload))

                self.assertEqual(payload["front_decision"]["execution_object"], {})
                self.assertEqual(payload["front_decision"]["position_pct"], 0)
                self.assertEqual(payload["front_decision"]["position_plan"], "0%不参与")
                self.assertEqual(payload["b_level_conditions"], {})
                self.assertIn("| 明日执行对象 | 无 |", front_text)
                self.assertNotIn(PREMARKET_50_EXECUTION_TEXT, front_text)
                self.assertNotIn(PREMARKET_FULL_EXECUTION_TEXT, front_text)
                self.assertIn("| 最终结果 | N9 / final | 无；0%不参与；0% |", audit_text)
                self.assertNotIn("50%条件执行", audit_text)
                self.assertNotIn("100%核心进攻", audit_text)

    def test_external_pending_trade_zero_position_uses_confirmation_only_action(self):
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
            target_date="2026-07-10",
            final_target_resolution={
                "existing_position_target": {
                    "name": "长电科技",
                    "code": "600584",
                    "has_position": False,
                    "has_pending_position": True,
                    "position_source": "external_trade_pending",
                },
                "new_entry_target": {},
                "display_target": {},
                "capital_priority_decision": {
                    "capital_priority": "wait",
                    "reason": "明日无新增参与对象，外部交易待核实；未核实前按0x",
                },
            },
            position_decision={
                "target_position_pct": 0,
                "signal_grade": "0",
                "participation_mode": "no_trade",
            },
            execution_stage_context={"selection_workflow": workflow},
        )

        self.assertTrue(payload["pending_position_confirmation"])
        self.assertEqual(payload["front_decision"]["attribution"], "账户问题")
        self.assertEqual(payload["front_decision"]["zero_action_text"], "0%不参与；只核实外部交易记录")
        self.assertEqual(
            payload["next_day_action"]["old_position_handling"],
            "只核实外部交易记录；未核实成交前按0x",
        )
        self.assertEqual(payload["derivation_steps"][-1]["action"], "明日动作：0%不参与；只核实外部交易记录")
        front_text = "\n".join(render_front_decision_layer(payload))
        derivation_text = "\n".join(render_derivation_audit_layer(payload))
        self.assertIn("| 明日执行对象 | 无 |", front_text)
        self.assertIn(
            "| 账户先处理 | 只核实外部交易记录；未核实成交前按0x |",
            front_text,
        )
        self.assertIn("| 不参与依据 | 外部交易记录待核实", front_text)
        self.assertIn("| 无执行目标原因 | 新开仓没有执行对象；只核实外部交易是否成交 |", front_text)
        self.assertIn("| 责任归因 | 账户问题 |", front_text)
        self.assertNotIn("前日报计划对象", front_text + "\n" + derivation_text)
        self.assertNotIn("只处理旧仓", front_text + "\n" + derivation_text)

    def test_pure_zero_without_position_does_not_create_old_position_action(self):
        payload = build_two_layer_decision_payload(
            target_date="2026-07-10",
            final_target_resolution={
                "new_entry_target": {},
                "display_target": {},
                "existing_position_target": {},
                "capital_priority_decision": {
                    "capital_priority": "wait",
                    "reason": "无明日执行对象",
                },
            },
            position_decision={"target_position_pct": 0},
            execution_stage_context={},
        )

        self.assertEqual(
            payload["front_decision"]["zero_action_text"],
            "0%不参与；无执行对象",
        )
        self.assertEqual(
            payload["next_day_action"]["old_position_handling"],
            "无旧仓需要处理；保持0%不参与",
        )
        self.assertNotIn("旧仓优先", str(payload))

    def test_same_stock_t_resolution_does_not_override_zero_workflow(self):
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
            target_date="2026-07-06",
            final_target_resolution={
                "new_entry_target": {"name": "太极实业", "code": "600667", "sector": "半导体"},
                "existing_position_target": {"name": "太极实业", "code": "600667", "sector": "半导体"},
                "display_target": {"name": "太极实业", "code": "600667", "sector": "半导体"},
                "capital_priority_decision": {
                    "capital_priority": "same_stock_t",
                    "reason": "已有1x旧仓且今日目标仍是同一只票，只按同股T候选处理",
                },
            },
            position_decision={"target_position_pct": 0},
            execution_stage_context={"selection_workflow": workflow},
        )

        self.assertEqual(payload["front_decision"]["execution_object"], {})
        self.assertEqual(payload["front_decision"]["position_pct"], 0)
        self.assertEqual(payload["front_decision"]["position_plan"], "0%不参与")
        self.assertEqual(payload["b_level_conditions"], {})
        text = "\n".join(render_front_decision_layer(payload))
        self.assertNotIn(SAME_STOCK_T_CONFIRMATION_CLAUSE, text)
        self.assertNotIn("| 明日新仓 | 已决定50%条件执行", text)

    def test_core_attack_front_decision_layer_uses_two_b_position_text(self):
        payload = build_two_layer_decision_payload(
            target_date="2026-07-06",
            final_target_resolution={
                "display_target": {"name": "工业富联", "code": "601138", "sector": "通信设备"},
                "capital_priority_decision": {"capital_priority": "new_entry"},
            },
            position_decision={"target_position_pct": 100, "participation_mode": "core_attack_100"},
        )

        text = "\n".join(render_front_decision_layer(payload))

        self.assertIn(f"| 明日新仓 | {PREMARKET_FULL_EXECUTION_TEXT} |", text)
        self.assertIn(TWO_B_CONFIRMATION_CLAUSE, text)
        self.assertIn(PREMARKET_50_TRIGGER_TEXT, text)

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
        self.assertIn("没有可用明日执行对象", payload["final_object"]["why_this_not_others"])
        self.assertIn("过程候选只保留在后文复盘表", payload["final_object"]["why_this_not_others"])
        self.assertIn("最终不新增参与", payload["final_object"]["why_this_not_others"])
        self.assertIn("没有可用明日执行对象", payload["opening_verdict"]["summary"])
        self.assertIn("过程候选只保留在后文复盘表", payload["opening_verdict"]["summary"])
        self.assertIn("最终不新增参与", payload["opening_verdict"]["summary"])
        self.assertGreater(len(payload["candidate_pool_verdict"]["pool_source"]), 0)
        self.assertEqual(payload["front_decision"]["execution_object"], {})

    def test_zero_position_selection_workflow_keeps_process_summary_visible(self):
        workflow = {
            "schema_version": "selection_workflow.v1",
            "final": {
                "execution_object": {},
                "position_pct": 0,
                "action_text": "0%不参与",
                "source_node": "N8",
            },
            "nodes": [{"node_id": "N5", "judgement": "归一候选1只"}],
            "candidate_pool": [
                {
                    "stock": {"name": "华天科技", "code": "002185", "sector": "半导体"},
                    "source_pools": ["热度观察池"],
                    "status": "被淘汰",
                    "eliminated_reason": "资金确认不足",
                }
            ],
        }

        payload = build_two_layer_decision_payload(
            target_date="2026-07-13",
            final_target_resolution={
                "capital_priority_decision": {"capital_priority": "wait", "reason": "空仓等待"},
            },
            position_decision={"target_position_pct": 0},
            execution_stage_context={"selection_workflow": workflow},
        )

        self.assertEqual(payload["final_object"]["identity"], "无")
        self.assertEqual(payload["candidate_pool_verdict"]["pool_source"][0]["stock"]["code"], "002185")
        self.assertIn("过程候选只保留在后文复盘表", payload["final_object"]["why_this_not_others"])
        self.assertNotIn("也没有过程候选", payload["final_object"]["why_this_not_others"])

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
                "final_action": "已决定50%条件执行；盘中不满足取消，回到0%不参与",
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
        self.assertNotIn("已决定50%条件执行", text)
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
        self.assertEqual(
            payload["next_day_action"]["old_position_handling"],
            "旧仓优先时，新机会只观察，不新增参与",
        )
        self.assertIn("| 明日执行对象 | 无 |", text)
        self.assertIn(
            "| 账户先处理 | 旧仓优先时，新机会只观察，不新增参与 |",
            text,
        )
        self.assertNotIn("| 明日执行对象 | 豫能控股(001896) |", text)

    def test_zero_position_new_entry_priority_does_not_override_structured_zero(self):
        payload = build_two_layer_decision_payload(
            target_date="2026-06-04",
            final_target_resolution={
                "watch_target": {"name": "豫能控股", "code": "001896", "sector": "电力"},
                "display_target": {"name": "豫能控股", "code": "001896", "sector": "电力"},
                "capital_priority_decision": {
                    "capital_priority": "new_entry",
                    "reason": "按昨晚预案检查执行资格；不满足回到0%不参与",
                },
            },
            position_decision={"target_position_pct": 0, "final_action": "已决定50%条件执行；盘中不满足取消，回到0%不参与"},
            execution_stage_context={},
        )

        text = "\n".join(render_front_decision_layer(payload))

        self.assertEqual(payload["front_decision"]["execution_object"], {})
        self.assertEqual(payload["front_decision"]["position_plan"], "0%不参与")
        self.assertEqual(payload["front_decision"]["position_pct"], 0)
        self.assertEqual(payload["b_level_conditions"], {})
        self.assertIn("| 明日新仓 | 0%不参与 |", text)
        self.assertNotIn(PREMARKET_50_EXECUTION_TEXT, text)

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
                    "reason": "按昨晚预案检查执行资格；不满足回到0%不参与",
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
                    "reason": "按昨晚预案检查执行资格；不满足回到0%不参与",
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
        self.assertIn("明日动作：0%不参与；无执行对象", text)
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
        self.assertIn("明日动作：0%不参与；无执行对象", text)
        self.assertNotIn("保留对象：豫能控股(001896)", text)
        self.assertNotIn("明日动作：只观察豫能控股(001896)，不新增参与", text)
        self.assertNotIn("淘汰：上海石化(600688)、豫能控股(001896)", text)
        self.assertNotIn("淘汰对象：上海石化(600688)、豫能控股(001896)", text)
        self.assertIn("不参与", text)

    def test_selection_workflow_derivation_summarizes_premarket_review_without_internal_fields(self):
        payload = {
            "selection_workflow": {
                "schema_version": "selection_workflow.v1",
                "nodes": [
                    {"node_id": "N8", "node_name": "仓位与执行条件", "judgement": "100%核心进攻"},
                    {
                        "node_id": "N8_5",
                        "node_name": "盘前叙事反证复核",
                        "input_refs": ["N8"],
                        "judgement": "不参与：动作上限不参与",
                        "passes_forward": {
                            "position_pct": 0,
                            "premarket_narrative_review": {
                                "status": "不参与",
                                "complete_chain": True,
                                "driver_hit": True,
                                "action_effect": "no_participation",
                                "action_effect_label": "不参与",
                                "summary": "Meta拟对外出售算力，击中AI算力和存储紧缺叙事",
                            },
                        },
                    },
                    {"node_id": "N9", "node_name": "输出一致性复核", "input_refs": ["N8_5"], "judgement": "同源输出"},
                ],
                "premarket_narrative_review": {
                    "status": "不参与",
                    "action_effect_label": "不参与",
                    "summary": "Meta拟对外出售算力，击中AI算力和存储紧缺叙事",
                },
                "final": {
                    "execution_object": {},
                    "position_pct": 0,
                    "action_text": "50%条件执行",
                    "source_node": "N8_5",
                },
            }
        }

        text = "\n".join(render_derivation_audit_layer(payload))

        self.assertIn("| 盘前叙事反证复核 | N8_5 | 不参与", text)
        self.assertIn("复核状态：不参与；动作上限：不参与", text)
        self.assertIn("Meta拟对外出售算力", text)
        self.assertNotIn("driver_hit", text)
        self.assertNotIn("complete_chain", text)
        self.assertNotIn("action_effect", text)
        self.assertNotIn("50%条件执行", text)

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
