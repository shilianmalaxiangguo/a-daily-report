import sys
import unittest
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.front_page_v2_renderer import render_front_page_v2  # noqa: E402
from report.position_context import (  # noqa: E402
    OLD_POSITION_REVIEW_CONDITIONS,
    build_old_position_plan,
    build_tomorrow_empty_account_action,
    normalize_inferred_previous_target_records,
    old_position_action_rows,
    position_fact_status,
)
from report.runtime import (  # noqa: E402
    _build_runtime_final_target_resolution,
    _build_runtime_selection_workflow,
    _runtime_full_or_empty_exposure_plan,
)
from report.two_layer_decision_payload import (  # noqa: E402
    build_two_layer_decision_payload,
    render_front_decision_layer,
)


def _confirmed_summary(text, **extra):
    return {
        "has_position": True,
        "name": "长电科技",
        "code": "600584",
        "position_pct": 100,
        "summary": text,
        **extra,
    }


class PositionActionSemanticsTest(unittest.TestCase):
    def test_position_fact_does_not_change_selection_workflow_for_same_market_input(self):
        selected = {
            "name": "华天科技",
            "code": "002185",
            "sector": "半导体",
            "candidate_role": "板块锚",
            "sector_derivation_evidence": "板块资金扩散与价格承接已确认",
        }
        execution_context = {
            "mainline_name": "半导体",
            "sector_derived_candidates": [selected],
        }
        final_resolution = {
            "new_entry_target": selected,
            "capital_priority_decision": {"capital_priority": "new_entry"},
        }

        def build_workflow(position_summary):
            return _build_runtime_selection_workflow(
                target_date="2026-07-15",
                data={
                    "position_context_provided": True,
                    "personal_position_context": {
                        "existing_position_summary": position_summary,
                    },
                },
                execution_stage_context=deepcopy(execution_context),
                market_research_snapshot={},
                selected_position_candidate=deepcopy(selected),
                position_decision={"target_position_pct": 50},
                final_target_resolution=deepcopy(final_resolution),
            )

        empty_workflow = build_workflow(
            {
                "has_position": False,
                "summary": "已确认今日空仓",
                "position_source": "explicit_empty_input",
            }
        )
        confirmed_workflow = build_workflow(
            _confirmed_summary("已确认持有长电科技(600584)")
        )

        self.assertEqual(empty_workflow, confirmed_workflow)

    def test_same_market_input_keeps_new_entry_fields_when_only_current_position_fact_changes(self):
        selected = {
            "name": "华天科技",
            "code": "002185",
            "sector": "半导体",
            "candidate_role": "板块锚",
            "sector_derivation_evidence": "板块资金扩散与价格承接已确认",
        }
        execution_context = {
            "mainline_name": "半导体",
            "sector_derived_candidates": [selected],
        }
        workflow = _build_runtime_selection_workflow(
            target_date="2026-07-15",
            data={},
            execution_stage_context=deepcopy(execution_context),
            market_research_snapshot={},
            selected_position_candidate=deepcopy(selected),
            position_decision={"target_position_pct": 50},
            final_target_resolution={
                "new_entry_target": selected,
                "capital_priority_decision": {"capital_priority": "new_entry"},
            },
        )

        def project(summary):
            context = {**deepcopy(execution_context), "selection_workflow": deepcopy(workflow)}
            resolution = _build_runtime_final_target_resolution(
                data={
                    "position_context_provided": True,
                    "personal_position_context": {"existing_position_summary": summary},
                    "selection_workflow": deepcopy(workflow),
                },
                selected_position_candidate=deepcopy(selected),
                position_decision={"target_position_pct": 50},
                market_research_snapshot={"selection_workflow": deepcopy(workflow)},
                execution_stage_context=context,
            )
            payload = build_two_layer_decision_payload(
                target_date="2026-07-15",
                final_target_resolution=resolution,
                position_decision={"target_position_pct": 50},
                execution_stage_context=context,
            )
            return {
                "selection_workflow": workflow,
                "new_entry_target": resolution["new_entry_target"],
                "execution_object": payload["front_decision"]["execution_object"],
                "position_pct": payload["front_decision"]["position_pct"],
                "b_level_conditions": payload["b_level_conditions"],
            }

        empty_projection = project(
            {
                "has_position": False,
                "summary": "已确认今日空仓",
                "position_source": "explicit_empty_input",
            }
        )
        confirmed_projection = project(
            _confirmed_summary("已确认持有长电科技(600584)；正常存活")
        )

        self.assertEqual(empty_projection, confirmed_projection)

    def test_explicit_tomorrow_empty_overrides_confirmed_old_position_without_rewriting_selection(self):
        selected = {
            "name": "华天科技",
            "code": "002185",
            "sector": "半导体",
        }
        directive = build_tomorrow_empty_account_action(source="explicit_test")
        resolution = _build_runtime_final_target_resolution(
            data={
                "tomorrow_account_action": directive,
                "position_context_provided": True,
                "personal_position_context": {
                    "existing_position_summary": _confirmed_summary(
                        "已确认持有长电科技(600584)；正常存活；今日为T+2，按尾盘预案退出"
                    ),
                },
            },
            selected_position_candidate=selected,
            position_decision={"target_position_pct": 50},
            market_research_snapshot={},
            execution_stage_context={},
        )

        self.assertEqual(resolution["tomorrow_account_action"], directive)
        self.assertEqual(
            resolution["capital_priority_decision"]["capital_priority"],
            "tomorrow_empty",
        )
        self.assertEqual(resolution["new_entry_target"], {})
        self.assertEqual(resolution["process_target"], {})

        payload = build_two_layer_decision_payload(
            target_date="2026-07-15",
            final_target_resolution=resolution,
            position_decision={"target_position_pct": 50},
            execution_stage_context={},
        )
        rendered = "\n".join(render_front_decision_layer(payload))

        self.assertEqual(payload["tomorrow_account_action"], directive)
        self.assertEqual(payload["front_decision"]["position_pct"], 0)
        self.assertEqual(payload["front_decision"]["execution_object"], {})
        self.assertIn("| 明日账户结果 | 明日空仓 |", rendered)
        self.assertIn("| 明日新仓 | 0%不参与 |", rendered)
        self.assertIn("集合竞价卖清全部可卖旧仓", rendered)
        self.assertIn("不做T", rendered)
        self.assertIn("未清完不能称空仓", rendered)
        self.assertNotIn("14:30-14:55按T+2预案退出", rendered)

    def test_current_empty_fact_does_not_create_tomorrow_empty_action(self):
        resolution = _build_runtime_final_target_resolution(
            data={
                "position_context_provided": True,
                "personal_position_context": {
                    "existing_position_summary": {
                        "has_position": False,
                        "summary": "已确认今日空仓",
                        "position_source": "explicit_empty_input",
                    },
                },
            },
            selected_position_candidate={},
            position_decision={"target_position_pct": 0},
            market_research_snapshot={},
            execution_stage_context={},
        )

        self.assertEqual(resolution.get("tomorrow_account_action", {}), {})
        self.assertNotEqual(
            resolution["capital_priority_decision"]["capital_priority"],
            "tomorrow_empty",
        )

    def test_explicit_tomorrow_empty_is_consistent_in_front_page_and_position_strategy(self):
        directive = build_tomorrow_empty_account_action(source="explicit_test")
        summary = _confirmed_summary("已确认持有长电科技(600584)；正常存活")
        resolution = {
            "tomorrow_account_action": directive,
            "existing_position_target": summary,
            "old_position_plan": build_old_position_plan(summary),
            "new_entry_target": {},
            "process_target": {},
            "display_target": {},
            "watch_target": {},
            "capital_priority_decision": {
                "capital_priority": "tomorrow_empty",
                "reason": "显式明日空仓",
            },
            "account_exposure_plan": {
                "position_fact_status": "confirmed",
                "old_position_1x": True,
                "max_runtime_exposure_x": 1,
                "policy": "当前旧仓1x；明日卖清后0x",
            },
        }
        data = {
            "tomorrow_account_action": directive,
            "position_context_provided": True,
            "personal_position_context": {"existing_position_summary": summary},
            "existing_position_summary": summary,
            "final_target_resolution": resolution,
            "position_decision": {"signal_grade": "0", "target_position_pct": 0},
        }
        front = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-07-15",
                market_research_snapshot=data,
            )
        )
        with TemporaryDirectory() as tempdir:
            strategy = __import__(
                "portfolio.position_strategy_report",
                fromlist=["render_position_strategy_report"],
            ).render_position_strategy_report(
                data,
                "2026-07-15",
                [summary],
                output_root=Path(tempdir),
            )

        for rendered in (front, strategy):
            self.assertIn("| 明日账户结果 | 明日空仓 |", rendered)
            self.assertIn("集合竞价卖清全部可卖旧仓", rendered)
            self.assertIn("不做T", rendered)
            self.assertIn("未清完不能称空仓", rendered)
        self.assertIn(
            "| Te | 2026-07-16（周四） | 明日空仓 | 无 | 没有B1/B2；不买新股、不做T |",
            strategy,
        )

    def test_position_fact_status_separates_unknown_none_external_pending_and_confirmed(self):
        self.assertEqual(position_fact_status({}, context_provided=False), "unknown")
        for summary in (
            {"summary": "账户风险暴露待核对"},
            {"summary": "昨日计划长电科技"},
        ):
            with self.subTest(summary=summary["summary"]):
                self.assertEqual(
                    position_fact_status(summary, context_provided=True),
                    "unknown",
                )
                self.assertEqual(build_old_position_plan(summary), {})
        self.assertEqual(
            position_fact_status({"has_position": False, "summary": "已确认无旧仓"}, context_provided=True),
            "none",
        )
        self.assertEqual(
            position_fact_status(
                {
                    "has_position": False,
                    "has_pending_position": False,
                    "summary": "持仓未输入",
                },
                context_provided=True,
            ),
            "unknown",
        )
        self.assertEqual(
            position_fact_status(
                {
                    "has_position": False,
                    "has_pending_position": True,
                    "position_source": "external_trade_pending",
                    "summary": "外部成交记录待确认：长电科技(600584)",
                },
                context_provided=True,
            ),
            "pending_confirmation",
        )
        self.assertEqual(
            position_fact_status(
                {"summary": "外部成交记录待确认：长电科技(600584)"},
                context_provided=True,
            ),
            "pending_confirmation",
        )
        self.assertEqual(
            position_fact_status(
                {"summary": "持有长电科技(600584)，100%仓位"},
                context_provided=True,
            ),
            "confirmed",
        )
        self.assertEqual(
            position_fact_status(_confirmed_summary("持有长电科技(600584)"), context_provided=True),
            "confirmed",
        )

    def test_failed_old_position_exits_by_10_10_without_tail_default(self):
        plan = build_old_position_plan(
            _confirmed_summary("持有长电科技(600584)；T失败；买点失效；必须卖")
        )

        self.assertEqual(plan["schema_version"], "old_position_plan.v1")
        self.assertEqual(plan["decision_class"], "failed")
        self.assertEqual(plan["action"], "exit")
        self.assertEqual(plan["primary_action_window"], "09:50-10:10")
        self.assertFalse(plan["tail_exit_allowed"])
        self.assertEqual(plan["closing_target_position_pct"], 0)

    def test_actual_position_outside_tier_band_keeps_fact_without_gaining_b1(self):
        for position_pct in (30, 39.6, 60.4, 99.6):
            with self.subTest(position_pct=position_pct):
                plan = build_old_position_plan(
                    _confirmed_summary(
                        f"持有长电科技(600584)，实际仓位{position_pct}%",
                        position_pct=position_pct,
                    )
                )

                self.assertEqual(plan["holding"]["position_pct"], position_pct)
                self.assertEqual(plan["account_exposure_mode"], "unknown")
                self.assertEqual(plan["position_sizing_rule"], "unknown")

    def test_failure_evidence_in_summary_survives_additional_holding_notes(self):
        plan = build_old_position_plan(
            _confirmed_summary("持有长电科技(600584)；买点失效；必须卖"),
            holding={"holding_note": "100股待处理"},
        )

        self.assertEqual(plan["decision_class"], "failed")
        self.assertEqual(plan["primary_action_window"], "09:50-10:10")

    def test_review_old_position_requires_three_layers_for_tail_exception(self):
        plan = build_old_position_plan(
            _confirmed_summary("持有长电科技(600584)；09:50-10:10收不回分时均价先卖")
        )

        self.assertEqual(plan["decision_class"], "review_at_10_10")
        self.assertEqual(plan["action"], "wait_for_repair")
        self.assertEqual(plan["review_conditions"], list(OLD_POSITION_REVIEW_CONDITIONS))
        self.assertTrue(plan["tail_exit_allowed"])
        self.assertIn("三层承接全部成立", plan["tail_exit_condition"])
        self.assertIsNone(plan["closing_target_position_pct"])

    def test_explicit_normal_tplus2_position_keeps_tail_exit(self):
        plan = build_old_position_plan(
            _confirmed_summary("持有长电科技(600584)；正常存活；今日为T+2，按尾盘预案退出")
        )

        self.assertEqual(plan["decision_class"], "normal")
        self.assertEqual(plan["trade_role"], "tplus2_exit")
        self.assertEqual(plan["action"], "exit")
        self.assertEqual(plan["primary_action_window"], "14:30-14:55")
        self.assertEqual(plan["closing_target_position_pct"], 0)

    def test_completes_legacy_structured_failed_plan_without_guessing_from_price(self):
        summary = _confirmed_summary("持有长电科技(600584)")
        summary["old_position_plan"] = {
            "schema_version": "old_position_plan.v1",
            "holding": {"name": "长电科技", "code": "600584", "position_pct": 100},
            "trade_role": "failed_buy",
            "action": "exit",
            "tail_exit_allowed": False,
        }

        plan = build_old_position_plan(summary)

        self.assertEqual(plan["decision_class"], "failed")
        self.assertEqual(plan["primary_action_window"], "09:50-10:10")
        self.assertEqual(plan["closing_target_position_pct"], 0)

    def test_explicit_old_plan_recomputes_tier_from_raw_holding_fact(self):
        cases = (
            (39.6, "1x", "position_tier", "unknown", "unknown"),
            (60.4, "1x", "position_tier", "unknown", "unknown"),
            (99.6, "2x", "position_tier", "unknown", "unknown"),
            (50, "2x", "position_tier", "1x", "position_tier"),
            (100, "1x", "position_tier", "2x", "position_tier"),
        )
        for position_pct, cached_mode, cached_rule, expected_mode, expected_rule in cases:
            with self.subTest(position_pct=position_pct):
                summary = _confirmed_summary("持有长电科技(600584)")
                summary["old_position_plan"] = {
                    "schema_version": "old_position_plan.v1",
                    "holding": {
                        "name": "长电科技",
                        "code": "600584",
                        "position_pct": position_pct,
                    },
                    "account_exposure_mode": cached_mode,
                    "position_sizing_rule": cached_rule,
                    "decision_class": "incomplete",
                }

                plan = build_old_position_plan(summary)

                self.assertEqual(plan["holding"]["position_pct"], position_pct)
                self.assertEqual(plan["account_exposure_mode"], expected_mode)
                self.assertEqual(plan["position_sizing_rule"], expected_rule)

    def test_structured_plan_normalizes_fields_that_conflict_with_decision_class(self):
        cases = (
            (
                {
                    "decision_class": "failed",
                    "trade_role": "failed_buy",
                    "action": "hold",
                    "primary_action_window": "14:30-14:55",
                    "tail_exit_allowed": True,
                    "closing_target_position_pct": 100,
                },
                {
                    "action": "exit",
                    "primary_action_window": "09:50-10:10",
                    "tail_exit_allowed": False,
                    "closing_target_position_pct": 0,
                },
            ),
            (
                {
                    "decision_class": "review_at_10_10",
                    "trade_role": "old_position",
                    "action": "exit",
                    "primary_action_window": "14:30-14:55",
                    "tail_exit_allowed": False,
                    "review_conditions": [],
                },
                {
                    "action": "wait_for_repair",
                    "primary_action_window": "09:50-10:10",
                    "tail_exit_allowed": True,
                    "review_conditions": list(OLD_POSITION_REVIEW_CONDITIONS),
                },
            ),
            (
                {
                    "decision_class": "normal",
                    "trade_role": "tplus2_exit",
                    "action": "hold",
                    "primary_action_window": "09:50-10:10",
                    "tail_exit_allowed": False,
                    "closing_target_position_pct": 100,
                },
                {
                    "action": "exit",
                    "primary_action_window": "14:30-14:55",
                    "tail_exit_allowed": True,
                    "closing_target_position_pct": 0,
                },
            ),
            (
                {
                    "decision_class": "incomplete",
                    "trade_role": "unknown",
                    "action": "exit",
                    "primary_action_window": "09:50-10:10",
                    "tail_exit_allowed": True,
                    "closing_target_position_pct": 0,
                },
                {
                    "action": "hold",
                    "primary_action_window": "none",
                    "tail_exit_allowed": False,
                    "closing_target_position_pct": None,
                },
            ),
        )
        for fields, expected in cases:
            with self.subTest(decision_class=fields["decision_class"]):
                summary = _confirmed_summary("持有长电科技(600584)")
                summary["old_position_plan"] = {
                    "schema_version": "old_position_plan.v1",
                    "holding": {"name": "长电科技", "code": "600584", "position_pct": 100},
                    **fields,
                }

                plan = build_old_position_plan(summary)

                for key, value in expected.items():
                    self.assertEqual(plan[key], value)

    def test_legacy_review_and_tplus2_plans_gain_complete_contract_fields(self):
        cases = (
            (
                {"action": "wait_for_repair", "trade_role": "old_position"},
                "review_at_10_10",
                "09:50-10:10",
            ),
            (
                {"action": "hold", "trade_role": "tplus2_exit"},
                "normal",
                "14:30-14:55",
            ),
        )
        for fields, decision_class, window in cases:
            with self.subTest(decision_class=decision_class):
                summary = _confirmed_summary("持有长电科技(600584)")
                summary["old_position_plan"] = {
                    "schema_version": "old_position_plan.v1",
                    "holding": {"name": "长电科技", "code": "600584", "position_pct": 100},
                    **fields,
                }

                plan = build_old_position_plan(summary)

                self.assertEqual(plan["decision_class"], decision_class)
                self.assertEqual(plan["primary_action_window"], window)
                if decision_class == "review_at_10_10":
                    self.assertEqual(plan["action"], "wait_for_repair")
                    self.assertEqual(plan["review_conditions"], list(OLD_POSITION_REVIEW_CONDITIONS))
                else:
                    self.assertEqual(plan["action"], "exit")
                    self.assertEqual(plan["closing_target_position_pct"], 0)

    def test_external_pending_trade_has_no_old_position_sell_action(self):
        pending = {
            "has_position": False,
            "has_pending_position": True,
            "position_source": "external_trade_pending",
            "summary": "外部成交记录待确认：长电科技(600584)",
        }

        self.assertEqual(build_old_position_plan(pending), {})
        rows = old_position_action_rows(
            position_fact_status="pending_confirmation",
            existing_position=pending,
            old_position_plan={},
        )
        self.assertEqual(rows["旧仓事实"], "外部交易待核实")
        self.assertEqual(rows["旧仓判断"], "外部交易待核实，不视为旧仓")
        self.assertEqual(rows["旧仓动作"], "只核实成交记录；未确认成交前不卖、不新增B2")
        self.assertEqual(rows["收盘目标仓位"], "0x（未确认成交前，不代表已确认空仓）")
        self.assertNotIn("退出", rows["旧仓动作"])

    def test_external_pending_visible_text_stays_pending_without_structured_flags(self):
        self.assertEqual(
            position_fact_status(
                {"summary": "外部交易待核实：长电科技(600584)"},
                context_provided=True,
            ),
            "pending_confirmation",
        )

    def test_runtime_promotes_previous_report_target_to_simulated_default_old_position(self):
        summary = {
            "has_position": True,
            "has_pending_position": False,
            "name": "长电科技",
            "code": "600584",
            "position_pct": 100,
            "position_source": "previous_report_target_default_1x",
            "inferred_from_previous_report": True,
            "summary": "持有长电科技(600584)，100%仓位，上一份日报明日标的默认1x旧仓",
        }

        normalize_inferred_previous_target_records(summary)

        resolution = _build_runtime_final_target_resolution(
            data={
                "position_context_provided": True,
                "personal_position_context": {"existing_position_summary": summary},
            },
            selected_position_candidate={},
            position_decision={"target_position_pct": 0},
            market_research_snapshot={},
            execution_stage_context={},
        )

        exposure = resolution["account_exposure_plan"]
        self.assertEqual(summary["has_position"], True)
        self.assertEqual(summary["has_pending_position"], False)
        self.assertEqual(summary["position"], 50.0)
        self.assertEqual(summary["position_pct"], 50.0)
        self.assertEqual(summary["default_position_pct"], 50)
        self.assertIn("1x/50%半仓", summary["summary"])
        self.assertEqual(exposure["schema_version"], "position_tier_exposure.v2")
        self.assertEqual(exposure["position_fact_status"], "confirmed")
        self.assertTrue(exposure["old_position_1x"])
        self.assertEqual(exposure["old_position_pct"], 50)
        self.assertEqual(exposure["old_position_x"], 1)
        self.assertEqual(exposure["max_runtime_exposure_pct"], 50)
        self.assertEqual(exposure["max_runtime_exposure_x"], 1)
        self.assertEqual(resolution["existing_position_target"]["role"], "旧仓处理")
        self.assertEqual(resolution["existing_position_target"]["position_pct"], 50.0)
        self.assertEqual(resolution["old_position_plan"]["schema_version"], "old_position_plan.v1")
        self.assertEqual(
            resolution["old_position_plan"]["holding"],
            {"name": "长电科技", "code": "600584", "position_pct": 50},
        )

    def test_previous_report_target_with_zero_actual_fields_restores_simulated_1x(self):
        summary = {
            "has_position": True,
            "has_pending_position": False,
            "name": "长电科技",
            "code": "600584",
            "position": 0,
            "position_pct": 0,
            "default_position_pct": 0,
            "position_source": "previous_report_target_default_1x",
        }

        normalize_inferred_previous_target_records(summary)

        self.assertEqual(summary["default_position_pct"], 50.0)
        self.assertEqual(summary["position"], 50.0)
        self.assertEqual(summary["position_pct"], 50.0)
        self.assertTrue(summary["has_position"])
        self.assertFalse(summary["has_pending_position"])
        self.assertEqual(summary["role"], "旧仓处理")

    def test_runtime_normalizes_previous_report_target_without_mutating_input(self):
        summary = {
            "has_position": True,
            "has_pending_position": False,
            "name": "长电科技",
            "code": "600584",
            "position": 0,
            "position_pct": 0,
            "default_position_pct": 0,
            "position_source": "previous_report_target_default_1x",
            "old_position_plan": {"schema_version": "old_position_plan.v1"},
        }

        resolution = _build_runtime_final_target_resolution(
            data={
                "position_context_provided": True,
                "personal_position_context": {"existing_position_summary": summary},
            },
            selected_position_candidate={},
            position_decision={"target_position_pct": 0},
            market_research_snapshot={},
            execution_stage_context={},
        )

        self.assertTrue(summary["has_position"])
        self.assertFalse(summary["has_pending_position"])
        self.assertEqual(summary["default_position_pct"], 0)
        self.assertIn("old_position_plan", summary)
        self.assertTrue(resolution["existing_position_target"]["has_position"])
        self.assertFalse(resolution["existing_position_target"]["has_pending_position"])
        self.assertEqual(resolution["existing_position_target"]["default_position_pct"], 50.0)
        self.assertEqual(resolution["existing_position_target"]["position_pct"], 50.0)
        self.assertEqual(
            resolution["account_exposure_plan"]["position_fact_status"],
            "confirmed",
        )
        self.assertTrue(resolution["account_exposure_plan"]["old_position_1x"])
        self.assertEqual(resolution["account_exposure_plan"]["old_position_pct"], 50)
        self.assertEqual(resolution["account_exposure_plan"]["max_runtime_exposure_x"], 1)

    def test_explicit_real_full_position_stays_2x_and_100_percent(self):
        summary = {
            "has_position": True,
            "has_pending_position": False,
            "name": "长电科技",
            "code": "600584",
            "position": 100,
            "position_pct": 100,
            "position_source": "explicit_position_input",
            "summary": "已确认持有长电科技(600584)，实际仓位100%",
        }

        normalize_inferred_previous_target_records(summary)
        resolution = _build_runtime_final_target_resolution(
            data={
                "position_context_provided": True,
                "personal_position_context": {"existing_position_summary": summary},
            },
            selected_position_candidate={},
            position_decision={"target_position_pct": 0},
            market_research_snapshot={},
            execution_stage_context={},
        )

        self.assertEqual(summary["position_pct"], 100)
        exposure = resolution["account_exposure_plan"]
        self.assertEqual(exposure["old_position_pct"], 100)
        self.assertEqual(exposure["old_position_x"], 2)
        self.assertEqual(exposure["max_runtime_exposure_pct"], 100)
        self.assertEqual(exposure["max_runtime_exposure_x"], 2)

    def test_confirmed_non_tier_actual_position_keeps_fact_without_gaining_tier(self):
        for actual_position_pct in (30, 39.6, 60.4, 99.6, None):
            with self.subTest(actual_position_pct=actual_position_pct):
                existing = {"name": "长电科技", "code": "600584"}
                if actual_position_pct is not None:
                    existing["position_pct"] = actual_position_pct
                exposure = _runtime_full_or_empty_exposure_plan(
                    existing=existing,
                    new_entry={"name": "深科技", "code": "000021"},
                    priority="new_entry",
                    position_fact_status="confirmed",
                    new_entry_position_pct=50,
                )

                self.assertEqual(exposure["old_position_actual_pct"], actual_position_pct)
                self.assertIsNone(exposure["old_position_pct"])
                self.assertIsNone(exposure["old_position_x"])
                self.assertFalse(exposure["old_position_1x"])
                self.assertEqual(exposure["planned_new_entry_pct"], 50)
                self.assertEqual(exposure["new_entry_pct"], 0)
                self.assertEqual(exposure["new_entry_x"], 0)
                self.assertIsNone(exposure["max_runtime_exposure_pct"])
                self.assertIsNone(exposure["max_runtime_exposure_x"])
                self.assertIn("账户风险暴露待确认", exposure["policy"])

    def test_confirmed_actual_40_to_60_percent_maps_to_one_x_exposure(self):
        for actual_position_pct in (40, 60):
            with self.subTest(actual_position_pct=actual_position_pct):
                exposure = _runtime_full_or_empty_exposure_plan(
                    existing={
                        "name": "长电科技",
                        "code": "600584",
                        "position_pct": actual_position_pct,
                    },
                    new_entry={},
                    priority="wait",
                    position_fact_status="confirmed",
                )

                self.assertEqual(exposure["old_position_actual_pct"], actual_position_pct)
                self.assertEqual(exposure["old_position_pct"], 50)
                self.assertEqual(exposure["old_position_x"], 1)
                self.assertTrue(exposure["old_position_1x"])

    def test_unknown_position_keeps_exposure_and_closing_target_unresolved(self):
        exposure = _runtime_full_or_empty_exposure_plan(
            position_fact_status="unknown",
            existing={},
            new_entry={},
            priority="wait",
        )
        rows = old_position_action_rows(
            position_fact_status="unknown",
            existing_position={},
            old_position_plan={},
        )

        self.assertIsNone(exposure["max_runtime_exposure_x"])
        self.assertEqual(exposure["policy"], "持仓未输入；账户风险暴露待确认")
        self.assertEqual(rows["旧仓事实"], "持仓未输入")
        self.assertEqual(rows["收盘目标仓位"], "待确认")

    def test_inferred_previous_plan_defaults_to_simulated_old_position_when_status_is_omitted(self):
        exposure = _runtime_full_or_empty_exposure_plan(
            existing={"name": "长电科技", "code": "600584"},
            new_entry={},
            priority="wait",
            inferred_default_old_position=True,
        )

        self.assertEqual(exposure["position_fact_status"], "confirmed")
        self.assertTrue(exposure["old_position_1x"])
        self.assertEqual(exposure["max_runtime_exposure_x"], 1)
        self.assertFalse(exposure["pending_position_confirmation"])

    def test_two_layer_and_front_page_render_same_old_position_action(self):
        summary = _confirmed_summary("持有长电科技(600584)；09:50-10:10收不回分时均价先卖")
        plan = build_old_position_plan(summary)
        resolution = {
            "existing_position_target": summary,
            "old_position_plan": plan,
            "account_exposure_plan": {
                "position_fact_status": "confirmed",
                "old_position_1x": True,
                "max_runtime_exposure_x": 1,
                "policy": "旧仓1x；明日不新增参与",
            },
            "capital_priority_decision": {
                "capital_priority": "old_position_t",
                "reason": "明日无新增参与对象，先处理已确认旧仓",
            },
        }
        payload = build_two_layer_decision_payload(
            target_date="2026-07-14",
            final_target_resolution=resolution,
            position_decision={"target_position_pct": 0},
            execution_stage_context={},
        )
        two_layer_text = "\n".join(render_front_decision_layer(payload))
        front_text = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-07-14",
                market_research_snapshot={
                    "position_context_provided": True,
                    "existing_position_summary": {**summary, "old_position_plan": plan},
                    "position_decision": {"signal_grade": "0", "target_position_pct": 0},
                    "final_target_resolution": resolution,
                },
            )
        )

        for rendered in (two_layer_text, front_text):
            self.assertIn("| 明日新仓 | 0%", rendered)
            self.assertIn("| 旧仓事实 | 已确认持有长电科技(600584) |", rendered)
            self.assertIn("| 旧仓判断 | 待10:10复核 |", rendered)
            self.assertIn("| 旧仓动作 | 09:50-10:10只复核一次", rendered)
            self.assertIn("| 收盘目标仓位 | 待10:10复核后确定 |", rendered)


if __name__ == "__main__":
    unittest.main()
