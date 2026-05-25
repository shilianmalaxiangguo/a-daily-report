import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from selection.position_sizing_runtime import build_position_sizing_decision


class PositionSizingRuntimeTest(unittest.TestCase):
    def test_daily_report_wrapper_accepts_monthly_context(self):
        import daily_report_entry_demo as entry

        captured = {}

        def fake_position_sizing_decision(**kwargs):
            captured["monthly_context"] = kwargs.get("monthly_context")
            return {"target_position_pct": 0}

        with patch.object(entry, "run_build_position_sizing_decision", side_effect=fake_position_sizing_decision):
            result = entry._build_position_sizing_decision(
                final_gate={"can_new_entry": True},
                state_machine_snapshot={},
                best_stock={"name": "电力一号", "code": "000001"},
                mainline_name="电力",
                target_date="2026-05-13",
                monthly_context={"month_mode": "ordinary_attack"},
            )

        self.assertEqual(result["target_position_pct"], 0)
        self.assertEqual(captured["monthly_context"]["month_mode"], "ordinary_attack")

    def test_build_position_sizing_decision_allows_execute_50_for_single_confirmed_target(self):
        result = build_position_sizing_decision(
            final_gate={"can_new_entry": True},
            state_machine_snapshot={"execution_bias": "allow_execute", "leading_line": "军工"},
            best_stock={"name": "军工一号", "code": "000001"},
            watch_anchor_type="明天唯一能买的那只",
            mainline_name="军工",
            target_date="2026-06-22",
            helpers={
                "_build_candidate_feedback_clock": lambda **kwargs: {
                    "confirm_price": 12.34,
                    "support_price": 11.8,
                    "ready": True,
                    "score": 88,
                    "reasons": ["60分钟确认链完整"],
                    "history_feedback": {},
                    "active_watch": True,
                    "second_shot_ready": False,
                },
                "_classify_20cm_branch": lambda **kwargs: {"is_20cm": False},
                "_build_weak_to_strong_context": lambda **kwargs: {"active": False},
                "_is_bridge_priority_setup": lambda candidate, mainline_name="": False,
            },
        )

        self.assertEqual(result["participation_mode"], "execute_50")
        self.assertEqual(result["target_position_pct"], 50)
        self.assertEqual(result["trigger_text"], "首个60分钟站上12.34且不破11.80")
        self.assertTrue(result["candidate_feedback_ready"])
        self.assertEqual(result["candidate_feedback_score"], 88)
        self.assertEqual(result["single_focus_constraint"]["status"], "clear")

    def test_build_position_sizing_decision_uses_runtime_default_dependencies(self):
        from selection import position_sizing_runtime as runtime

        with patch.object(runtime, "_default_build_candidate_feedback_clock", return_value={
            "confirm_price": 12.34,
            "support_price": 11.8,
            "ready": True,
            "score": 88,
            "reasons": ["60分钟确认链完整"],
            "history_feedback": {},
            "active_watch": True,
            "second_shot_ready": False,
        }), \
            patch.object(runtime, "_default_classify_20cm_branch", return_value={"is_20cm": False}), \
            patch.object(runtime, "_default_build_weak_to_strong_context", return_value={"active": False}), \
            patch.object(runtime, "_default_is_bridge_priority_setup", return_value=False):
            result = runtime.build_position_sizing_decision(
                final_gate={"can_new_entry": True},
                state_machine_snapshot={"execution_bias": "allow_execute", "leading_line": "军工"},
                best_stock={"name": "军工一号", "code": "000001"},
                watch_anchor_type="明天唯一能买的那只",
                mainline_name="军工",
                target_date="2026-06-22",
            )

        self.assertEqual(result["participation_mode"], "execute_50")
        self.assertEqual(result["target_position_pct"], 50)

    def test_build_position_sizing_decision_keeps_50_when_multiple_targets_remain_but_feedback_ready(self):
        result = build_position_sizing_decision(
            final_gate={"can_new_entry": True, "unique_target_count": 2},
            state_machine_snapshot={"execution_bias": "allow_execute", "leading_line": "军工"},
            best_stock={"name": "军工一号", "code": "000001"},
            watch_anchor_type="明天唯一能买的那只",
            mainline_name="军工",
            target_date="2026-04-22",
            helpers={
                "_build_candidate_feedback_clock": lambda **kwargs: {
                    "confirm_price": 12.34,
                    "support_price": 11.8,
                    "ready": True,
                    "score": 88,
                    "reasons": ["60分钟确认链完整"],
                    "history_feedback": {},
                    "active_watch": True,
                    "second_shot_ready": False,
                },
                "_classify_20cm_branch": lambda **kwargs: {"is_20cm": False},
                "_build_weak_to_strong_context": lambda **kwargs: {"active": False},
                "_is_bridge_priority_setup": lambda candidate, mainline_name="": False,
            },
        )

        self.assertEqual(result["participation_mode"], "execute_50")
        self.assertEqual(result["target_position_pct"], 50)
        self.assertEqual(result["single_focus_constraint"]["status"], "multiple_candidates")
        self.assertIn("按50%标准进攻", result["sizing_reason"])

    def test_build_position_sizing_decision_marks_missing_target_when_entry_gate_open_without_best_stock(self):
        result = build_position_sizing_decision(
            final_gate={"can_new_entry": True},
            state_machine_snapshot={"execution_bias": "allow_execute", "leading_line": "军工"},
            best_stock=None,
            watch_anchor_type="明天唯一能买的那只",
            mainline_name="军工",
            target_date="2026-04-22",
            helpers={
                "_build_candidate_feedback_clock": lambda **kwargs: {
                    "confirm_price": 12.34,
                    "support_price": 11.8,
                    "ready": True,
                    "score": 88,
                    "reasons": ["60分钟确认链完整"],
                    "history_feedback": {},
                    "active_watch": True,
                    "second_shot_ready": False,
                },
                "_classify_20cm_branch": lambda **kwargs: {"is_20cm": False},
                "_build_weak_to_strong_context": lambda **kwargs: {"active": False},
                "_is_bridge_priority_setup": lambda candidate, mainline_name="": False,
            },
        )

        self.assertEqual(result["participation_mode"], "observe_0")
        self.assertEqual(result["target_position_pct"], 0)
        self.assertEqual(result["single_focus_constraint"]["status"], "missing_target")
        self.assertIn("缺少唯一执行对象", result["single_focus_constraint"]["reason"])

    def test_monthly_rhythm_can_upgrade_confirmed_signal_to_full_a_grade(self):
        result = build_position_sizing_decision(
            final_gate={"can_new_entry": True},
            state_machine_snapshot={"execution_bias": "allow_execute", "leading_line": "军工", "energy_state": "主线攻击"},
            best_stock={
                "name": "军工一号",
                "code": "000001",
                "sector": "军工",
                "a_grade_candidate": True,
                "trend_chain_active": True,
                "participation_window": "竞价表态",
                "acceptance_act_right": True,
            },
            watch_anchor_type="明天唯一能买的那只",
            mainline_name="军工",
            target_date="2026-06-18",
            monthly_context={"month_mode": "ordinary_attack", "month_return_pct": 12.0},
            helpers={
                "_build_candidate_feedback_clock": lambda **kwargs: {
                    "confirm_price": 12.34,
                    "support_price": 11.8,
                    "ready": True,
                    "score": 92,
                    "reasons": ["60分钟确认链完整", "唯一对象"],
                    "history_feedback": {"continuous_days": 3},
                    "active_watch": True,
                    "second_shot_ready": False,
                },
                "_classify_20cm_branch": lambda **kwargs: {"is_20cm": False},
                "_build_weak_to_strong_context": lambda **kwargs: {"active": False},
                "_is_bridge_priority_setup": lambda candidate, mainline_name="": False,
            },
        )

        self.assertEqual(result["signal_grade"], "100")
        self.assertEqual(result["participation_mode"], "full_100")
        self.assertEqual(result["target_position_pct"], 100)
        self.assertTrue(result["monthly_rhythm"]["allow_full_attack"])
        self.assertTrue(result["monthly_rhythm"]["profit_cushion"])

    def test_earnings_month_no_longer_caps_full_candidate_to_small_trial(self):
        result = build_position_sizing_decision(
            final_gate={"can_new_entry": True},
            state_machine_snapshot={"execution_bias": "allow_execute", "leading_line": "军工", "energy_state": "主线攻击"},
            best_stock={
                "name": "军工一号",
                "code": "000001",
                "sector": "军工",
                "a_grade_candidate": True,
                "trend_chain_active": True,
                "participation_window": "竞价表态",
                "acceptance_act_right": True,
            },
            watch_anchor_type="明天唯一能买的那只",
            mainline_name="军工",
            target_date="2026-04-22",
            monthly_context={"earnings_risk": True, "month_return_pct": 0},
            helpers={
                "_build_candidate_feedback_clock": lambda **kwargs: {
                    "confirm_price": 12.34,
                    "support_price": 11.8,
                    "ready": True,
                    "score": 92,
                    "reasons": ["60分钟确认链完整", "唯一对象"],
                    "history_feedback": {"continuous_days": 3},
                    "active_watch": True,
                    "second_shot_ready": False,
                },
                "_classify_20cm_branch": lambda **kwargs: {"is_20cm": False},
                "_build_weak_to_strong_context": lambda **kwargs: {"active": False},
                "_is_bridge_priority_setup": lambda candidate, mainline_name="": False,
            },
        )

        self.assertEqual(result["signal_grade"], "100")
        self.assertEqual(result["participation_mode"], "full_100")
        self.assertEqual(result["target_position_pct"], 100)
        self.assertTrue(result["monthly_rhythm"]["allow_full_attack"])

    def test_calendar_earnings_month_caps_full_a_candidate_without_manual_context(self):
        result = build_position_sizing_decision(
            final_gate={"can_new_entry": True},
            state_machine_snapshot={"execution_bias": "allow_execute", "leading_line": "军工", "energy_state": "主线攻击"},
            best_stock={
                "name": "军工一号",
                "code": "000001",
                "sector": "军工",
                "a_grade_candidate": True,
                "trend_chain_active": True,
                "participation_window": "竞价表态",
                "acceptance_act_right": True,
            },
            watch_anchor_type="明天唯一能买的那只",
            mainline_name="军工",
            target_date="2026-04-22",
            helpers={
                "_build_candidate_feedback_clock": lambda **kwargs: {
                    "confirm_price": 12.34,
                    "support_price": 11.8,
                    "ready": True,
                    "score": 92,
                    "reasons": ["60分钟确认链完整", "唯一对象"],
                    "history_feedback": {"continuous_days": 3},
                    "active_watch": True,
                    "second_shot_ready": False,
                },
                "_classify_20cm_branch": lambda **kwargs: {"is_20cm": False},
                "_build_weak_to_strong_context": lambda **kwargs: {"active": False},
                "_is_bridge_priority_setup": lambda candidate, mainline_name="": False,
            },
        )

        self.assertEqual(result["monthly_rhythm"]["month_mode"], "earnings_defense")
        self.assertEqual(result["signal_grade"], "100")
        self.assertEqual(result["target_position_pct"], 100)

    def test_full_attack_requires_explicit_participation_window_and_trend_chain(self):
        result = build_position_sizing_decision(
            final_gate={"can_new_entry": True},
            state_machine_snapshot={"execution_bias": "allow_execute", "leading_line": "电力", "energy_state": "主线攻击"},
            best_stock={
                "name": "电力一号",
                "code": "000001",
                "a_grade_candidate": True,
                "trend_chain_active": True,
                "acceptance_act_right": True,
                "invalidation_price": 11.8,
            },
            watch_anchor_type="明天唯一能买的那只",
            mainline_name="电力",
            target_date="2026-06-18",
            monthly_context={"month_mode": "ordinary_attack"},
            helpers={
                "_build_candidate_feedback_clock": lambda **kwargs: {
                    "confirm_price": 12.34,
                    "support_price": 11.8,
                    "ready": True,
                    "score": 92,
                    "reasons": ["60分钟确认链完整", "唯一对象"],
                    "history_feedback": {"continuous_days": 3},
                    "active_watch": True,
                    "second_shot_ready": False,
                },
                "_classify_20cm_branch": lambda **kwargs: {"is_20cm": False},
                "_build_weak_to_strong_context": lambda **kwargs: {"active": False},
                "_is_bridge_priority_setup": lambda candidate, mainline_name="": False,
            },
        )

        self.assertEqual(result["participation_mode"], "execute_50")
        self.assertEqual(result["target_position_pct"], 50)
        self.assertFalse(result["full_attack_ready"])
        self.assertIn("参与窗口", result["full_attack_check"]["missing"])

    def test_full_attack_does_not_treat_mainline_sector_and_follow_state_as_independent_100_qualification(self):
        result = build_position_sizing_decision(
            final_gate={"can_new_entry": True},
            state_machine_snapshot={"execution_bias": "allow_execute", "leading_line": "电力", "energy_state": "主线攻击"},
            best_stock={
                "name": "电力一号",
                "code": "000001",
                "sector": "电力",
                "a_grade_candidate": True,
                "abnormal_follow_state": "跌不下去",
                "participation_window": "竞价表态",
                "invalidation_price": 11.8,
            },
            watch_anchor_type="明天唯一能买的那只",
            mainline_name="电力",
            target_date="2026-06-18",
            monthly_context={"month_mode": "ordinary_attack"},
            helpers={
                "_build_candidate_feedback_clock": lambda **kwargs: {
                    "confirm_price": 12.34,
                    "support_price": 11.8,
                    "ready": True,
                    "score": 92,
                    "reasons": ["60分钟确认链完整", "唯一对象"],
                    "history_feedback": {"continuous_days": 3},
                    "active_watch": True,
                    "second_shot_ready": False,
                },
                "_classify_20cm_branch": lambda **kwargs: {"is_20cm": False},
                "_build_weak_to_strong_context": lambda **kwargs: {"active": False},
                "_is_bridge_priority_setup": lambda candidate, mainline_name="": False,
            },
        )

        self.assertEqual(result["participation_mode"], "execute_50")
        self.assertEqual(result["target_position_pct"], 50)
        self.assertEqual(result["signal_grade"], "50")
        self.assertFalse(result["full_attack_ready"])
        self.assertIn("趋势比价链", result["full_attack_check"]["missing"])
        self.assertIn("承接继续正确", result["full_attack_check"]["missing"])

    def test_full_attack_uses_100_when_core_fields_are_complete(self):
        result = build_position_sizing_decision(
            final_gate={"can_new_entry": True},
            state_machine_snapshot={"execution_bias": "allow_execute", "leading_line": "电力", "energy_state": "主线攻击"},
            best_stock={
                "name": "电力一号",
                "code": "000001",
                "a_grade_candidate": True,
                "trend_chain_active": True,
                "participation_window": "竞价表态",
                "acceptance_act_right": True,
                "invalidation_price": 11.8,
            },
            watch_anchor_type="明天唯一能买的那只",
            mainline_name="电力",
            target_date="2026-06-18",
            monthly_context={"month_mode": "ordinary_attack"},
            helpers={
                "_build_candidate_feedback_clock": lambda **kwargs: {
                    "confirm_price": 12.34,
                    "support_price": 11.8,
                    "ready": True,
                    "score": 92,
                    "reasons": ["60分钟确认链完整", "唯一对象"],
                    "history_feedback": {"continuous_days": 3},
                    "active_watch": True,
                    "second_shot_ready": False,
                },
                "_classify_20cm_branch": lambda **kwargs: {"is_20cm": False},
                "_build_weak_to_strong_context": lambda **kwargs: {"active": False},
                "_is_bridge_priority_setup": lambda candidate, mainline_name="": False,
            },
        )

        self.assertEqual(result["participation_mode"], "full_100")
        self.assertEqual(result["target_position_pct"], 100)
        self.assertTrue(result["full_attack_ready"])
        self.assertEqual(result["full_attack_check"]["status"], "ready")

    def test_full_attack_does_not_preserve_legacy_80_or_90_percent_candidates(self):
        result = build_position_sizing_decision(
            final_gate={"can_new_entry": True},
            state_machine_snapshot={"execution_bias": "allow_execute", "leading_line": "电力", "energy_state": "主线攻击"},
            best_stock={
                "name": "电力一号",
                "code": "000001",
                "a_grade_candidate": True,
                "a_grade_position_pct": 90,
                "trend_chain_active": True,
                "participation_window": "竞价表态",
                "acceptance_act_right": True,
                "invalidation_price": 11.8,
            },
            watch_anchor_type="明天唯一能买的那只",
            mainline_name="电力",
            target_date="2026-06-18",
            monthly_context={"month_mode": "ordinary_attack"},
            helpers={
                "_build_candidate_feedback_clock": lambda **kwargs: {
                    "confirm_price": 12.34,
                    "support_price": 11.8,
                    "ready": True,
                    "score": 92,
                    "reasons": ["60分钟确认链完整", "唯一对象"],
                    "history_feedback": {"continuous_days": 3},
                    "active_watch": True,
                    "second_shot_ready": False,
                },
                "_classify_20cm_branch": lambda **kwargs: {"is_20cm": False},
                "_build_weak_to_strong_context": lambda **kwargs: {"active": False},
                "_is_bridge_priority_setup": lambda candidate, mainline_name="": False,
            },
        )

        self.assertEqual(result["participation_mode"], "full_100")
        self.assertEqual(result["target_position_pct"], 100)
        self.assertNotIn(result["target_position_pct"], (80, 90))

    def test_market_ice_point_keeps_position_at_zero_even_for_complete_core_candidate(self):
        result = build_position_sizing_decision(
            final_gate={"can_new_entry": True},
            state_machine_snapshot={"execution_bias": "allow_execute", "leading_line": "电力", "energy_state": "主线攻击"},
            best_stock={
                "name": "电力一号",
                "code": "000001",
                "a_grade_candidate": True,
                "trend_chain_active": True,
                "participation_window": "竞价表态",
                "acceptance_act_right": True,
                "invalidation_price": 11.8,
            },
            watch_anchor_type="明天唯一能买的那只",
            mainline_name="电力",
            target_date="2026-06-18",
            monthly_context={"month_mode": "ordinary_attack", "market_ice_point": True},
            helpers={
                "_build_candidate_feedback_clock": lambda **kwargs: {
                    "confirm_price": 12.34,
                    "support_price": 11.8,
                    "ready": True,
                    "score": 92,
                    "reasons": ["60分钟确认链完整", "唯一对象"],
                    "history_feedback": {"continuous_days": 3},
                    "active_watch": True,
                    "second_shot_ready": False,
                },
                "_classify_20cm_branch": lambda **kwargs: {"is_20cm": False},
                "_build_weak_to_strong_context": lambda **kwargs: {"active": False},
                "_is_bridge_priority_setup": lambda candidate, mainline_name="": False,
            },
        )

        self.assertEqual(result["participation_mode"], "observe_0")
        self.assertEqual(result["target_position_pct"], 0)
        self.assertFalse(result["full_attack_ready"])
        self.assertEqual(result["monthly_rhythm"]["target_role"], "defense_0")

    def test_extreme_conviction_target_keeps_50_attack_preview_in_non_ice_avoid_state(self):
        result = build_position_sizing_decision(
            final_gate={"can_new_entry": False, "should_reduce": True, "market_ice_point": False},
            state_machine_snapshot={
                "execution_bias": "avoid",
                "leading_line": "通信设备",
                "energy_state": "收缩防守",
                "market_ice_point": False,
            },
            watch_anchor={
                "name": "汇源通信",
                "code": "000586",
                "sector": "通信设备",
                "source_tier": "extreme_conviction",
                "participation_window": "竞价表态 + 回封参与",
                "acceptance_act_right": True,
                "invalidation_price": 19.37,
            },
            watch_anchor_type="明日极度看好目标标的",
            mainline_name="通信设备",
            target_date="2026-05-19",
            monthly_context={"market_ice_point": False, "month_mode": "ordinary_attack"},
            helpers={
                "_build_candidate_feedback_clock": lambda **kwargs: {
                    "confirm_price": 20.57,
                    "support_price": 19.37,
                    "ready": True,
                    "score": 88,
                    "reasons": ["极度看好目标进入参与窗口预演"],
                    "history_feedback": {},
                    "active_watch": True,
                    "second_shot_ready": False,
                },
                "_classify_20cm_branch": lambda **kwargs: {"is_20cm": False},
                "_build_weak_to_strong_context": lambda **kwargs: {"active": False},
                "_is_bridge_priority_setup": lambda candidate, mainline_name="": False,
            },
        )

        self.assertEqual(result["participation_mode"], "attack_50_preview")
        self.assertEqual(result["target_position_pct"], 50)
        self.assertEqual(result["signal_grade"], "50")
        self.assertIn("明日极度看好", result["sizing_reason"])
        self.assertEqual(result["single_focus_constraint"]["status"], "clear")

    def test_extreme_conviction_target_is_not_zeroed_by_unconfirmed_special_probe(self):
        result = build_position_sizing_decision(
            final_gate={"can_new_entry": False, "should_reduce": True, "market_ice_point": False},
            state_machine_snapshot={"execution_bias": "avoid", "leading_line": "通信设备", "market_ice_point": False},
            watch_anchor={
                "name": "汇源通信",
                "code": "000586",
                "sector": "通信设备",
                "source_tier": "extreme_conviction",
                "participation_window": "竞价表态 + 回封参与",
            },
            watch_anchor_type="明日极度看好目标标的",
            mainline_name="通信设备",
            target_date="2026-05-19",
            monthly_context={"market_ice_point": False, "month_mode": "ordinary_attack"},
            special_probe_verdict={"probe_state": "probe_flow_unconfirmed"},
            helpers={
                "_build_candidate_feedback_clock": lambda **kwargs: {
                    "confirm_price": 20.57,
                    "support_price": 19.37,
                    "ready": True,
                    "score": 88,
                    "reasons": ["极度看好目标进入参与窗口预演"],
                    "history_feedback": {},
                    "active_watch": True,
                    "second_shot_ready": False,
                },
                "_classify_20cm_branch": lambda **kwargs: {"is_20cm": False},
                "_build_weak_to_strong_context": lambda **kwargs: {"active": False},
                "_is_bridge_priority_setup": lambda candidate, mainline_name="": False,
            },
        )

        self.assertEqual(result["target_position_pct"], 50)
        self.assertIn("50%标准进攻预演", result["sizing_reason"])


if __name__ == "__main__":
    unittest.main()
