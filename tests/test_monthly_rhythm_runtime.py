import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from selection.monthly_rhythm_runtime import build_monthly_rhythm_decision


class MonthlyRhythmRuntimeTest(unittest.TestCase):
    def test_earnings_month_defaults_to_defense_and_blocks_full_attack(self):
        result = build_monthly_rhythm_decision(
            target_date="2026-04-22",
            monthly_context={"earnings_risk": True, "month_return_pct": 0},
            state_machine_snapshot={"execution_bias": "allow_execute", "energy_state": "主线攻击"},
        )

        self.assertEqual(result["month_mode"], "earnings_defense")
        self.assertEqual(result["max_position_pct"], 30)
        self.assertFalse(result["allow_full_attack"])
        self.assertEqual(result["target_role"], "defense_0")

    def test_calendar_earnings_month_defaults_to_defense_without_explicit_context(self):
        result = build_monthly_rhythm_decision(
            target_date="2026-04-22",
            monthly_context={},
            state_machine_snapshot={"execution_bias": "allow_execute", "energy_state": "主线攻击"},
        )

        self.assertTrue(result["calendar_earnings_month"])
        self.assertEqual(result["month_mode"], "earnings_defense")
        self.assertEqual(result["max_position_pct"], 30)
        self.assertFalse(result["allow_full_attack"])

    def test_attack_month_allows_full_attack_before_profit_target_is_reached(self):
        result = build_monthly_rhythm_decision(
            target_date="2026-06-18",
            monthly_context={"month_mode": "ordinary_attack", "month_return_pct": 3.2},
            state_machine_snapshot={"execution_bias": "allow_execute", "energy_state": "主线攻击"},
        )

        self.assertEqual(result["month_mode"], "ordinary_attack")
        self.assertEqual(result["max_position_pct"], 100)
        self.assertTrue(result["allow_full_attack"])
        self.assertEqual(result["target_role"], "attack_confirmed")

    def test_month_profit_near_target_keeps_attack_when_trend_is_right(self):
        result = build_monthly_rhythm_decision(
            target_date="2026-06-25",
            monthly_context={"month_mode": "ordinary_attack", "month_return_pct": 10.4},
            state_machine_snapshot={"execution_bias": "allow_execute", "energy_state": "主线攻击"},
        )

        self.assertEqual(result["month_mode"], "ordinary_attack")
        self.assertEqual(result["max_position_pct"], 100)
        self.assertTrue(result["allow_full_attack"])
        self.assertTrue(result["profit_cushion"])
        self.assertEqual(result["target_role"], "attack_confirmed")

    def test_profit_cushion_downgrades_only_when_trend_invalidates(self):
        result = build_monthly_rhythm_decision(
            target_date="2026-06-25",
            monthly_context={"month_mode": "ordinary_attack", "month_return_pct": 10.4, "trend_invalid": True},
            state_machine_snapshot={"execution_bias": "allow_execute", "energy_state": "主线攻击"},
        )

        self.assertEqual(result["month_mode"], "profit_protection")
        self.assertEqual(result["max_position_pct"], 50)
        self.assertFalse(result["allow_full_attack"])
        self.assertTrue(result["profit_cushion"])
        self.assertEqual(result["target_role"], "protect_profit")

    def test_explicit_earnings_defense_overrides_existing_month_profit(self):
        result = build_monthly_rhythm_decision(
            target_date="2026-04-25",
            monthly_context={"month_mode": "earnings_defense", "month_return_pct": 12.0},
            state_machine_snapshot={"execution_bias": "allow_execute", "energy_state": "主线攻击"},
        )

        self.assertEqual(result["month_mode"], "earnings_defense")
        self.assertEqual(result["max_position_pct"], 30)
        self.assertFalse(result["allow_full_attack"])


if __name__ == "__main__":
    unittest.main()
