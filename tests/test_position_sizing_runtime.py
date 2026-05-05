import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from selection.position_sizing_runtime import build_position_sizing_decision


class PositionSizingRuntimeTest(unittest.TestCase):
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

    def test_build_position_sizing_decision_downgrades_execute_when_multiple_targets_remain(self):
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

        self.assertEqual(result["participation_mode"], "conditional_30")
        self.assertEqual(result["target_position_pct"], 30)
        self.assertEqual(result["single_focus_constraint"]["status"], "multiple_candidates")
        self.assertIn("多候选未缩到唯一对象，只允许30%条件试错/观察", result["sizing_reason"])

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
            best_stock={"name": "军工一号", "code": "000001", "a_grade_candidate": True},
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

        self.assertEqual(result["signal_grade"], "A")
        self.assertEqual(result["participation_mode"], "a_grade_100")
        self.assertEqual(result["target_position_pct"], 100)
        self.assertTrue(result["monthly_rhythm"]["allow_full_attack"])
        self.assertTrue(result["monthly_rhythm"]["profit_cushion"])

    def test_earnings_month_caps_full_a_candidate_to_b_level_trial(self):
        result = build_position_sizing_decision(
            final_gate={"can_new_entry": True},
            state_machine_snapshot={"execution_bias": "allow_execute", "leading_line": "军工", "energy_state": "主线攻击"},
            best_stock={"name": "军工一号", "code": "000001", "a_grade_candidate": True},
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

        self.assertEqual(result["signal_grade"], "B")
        self.assertEqual(result["participation_mode"], "conditional_30")
        self.assertEqual(result["target_position_pct"], 30)
        self.assertFalse(result["monthly_rhythm"]["allow_full_attack"])

    def test_calendar_earnings_month_caps_full_a_candidate_without_manual_context(self):
        result = build_position_sizing_decision(
            final_gate={"can_new_entry": True},
            state_machine_snapshot={"execution_bias": "allow_execute", "leading_line": "军工", "energy_state": "主线攻击"},
            best_stock={"name": "军工一号", "code": "000001", "a_grade_candidate": True},
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
        self.assertEqual(result["signal_grade"], "B")
        self.assertEqual(result["target_position_pct"], 30)


if __name__ == "__main__":
    unittest.main()
