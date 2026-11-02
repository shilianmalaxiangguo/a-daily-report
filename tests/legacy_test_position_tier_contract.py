import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.position_tier_contract import (  # noqa: E402
    normalize_planned_position_tier_pct,
    normalize_position_tier_pct,
    position_tier_label,
    position_tier_pct_to_x,
    position_x_to_tier_pct,
)


class PositionTierContractTest(unittest.TestCase):
    def test_position_pct_and_x_use_one_three_tier_contract(self):
        cases = ((0, 0), (50, 1), (100, 2))

        for position_pct, position_x in cases:
            with self.subTest(position_pct=position_pct):
                self.assertEqual(normalize_position_tier_pct(position_pct), position_pct)
                self.assertEqual(position_tier_pct_to_x(position_pct), position_x)
                self.assertEqual(position_x_to_tier_pct(position_x), position_pct)

    def test_half_position_actual_granularity_stays_in_the_1x_tier(self):
        for position_pct in (40, 50, 60, "50%"):
            with self.subTest(position_pct=position_pct):
                self.assertEqual(normalize_position_tier_pct(position_pct), 50)
                self.assertEqual(position_tier_pct_to_x(position_pct), 1)

    def test_planned_position_accepts_only_exact_tiers(self):
        for position_pct in (0, 50, 100, "50%"):
            with self.subTest(position_pct=position_pct):
                expected = 50 if position_pct == "50%" else position_pct
                self.assertEqual(normalize_planned_position_tier_pct(position_pct), expected)
        self.assertEqual(normalize_planned_position_tier_pct(None), 0)
        for position_pct in (1, 33, 40, 60, 75, 99):
            with self.subTest(position_pct=position_pct):
                with self.assertRaises(ValueError):
                    normalize_planned_position_tier_pct(position_pct)

    def test_labels_keep_b1_and_b2_meaning_explicit(self):
        self.assertEqual(position_tier_label(0), "0%不参与")
        self.assertEqual(position_tier_label(50), "1x/50%半仓/B1参与权")
        self.assertEqual(position_tier_label(100), "2x/100%满仓/B1+B2")

    def test_out_of_range_values_are_rejected_instead_of_becoming_200_percent(self):
        for value in (-1, 101, 200):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    normalize_position_tier_pct(value)
        for value in (-1, 3, "3x"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    position_x_to_tier_pct(value)

    def test_non_tier_positive_values_do_not_gain_b1_or_b2_authority(self):
        for value in (0.1, 1, 39, 61, 75, 99):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    normalize_position_tier_pct(value)
                with self.assertRaises(ValueError):
                    position_tier_pct_to_x(value)


if __name__ == "__main__":
    unittest.main()
