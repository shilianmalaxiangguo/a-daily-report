import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from decision.chanlun import confirmation_nodes


class ChanlunConfirmationNodesTest(unittest.TestCase):
    def test_60m_confirms_when_three_child_trend_types_overlap(self):
        result = confirmation_nodes.confirm_with_child_trend_types(
            [{"high": 110, "low": 100}, {"high": 108, "low": 98}, {"high": 109, "low": 101}],
            period="60",
        )

        self.assertTrue(result["confirmed"])
        self.assertEqual(result["confirmation_status"], "confirmed_daily_level_zhongshu")
        self.assertEqual(result["period"], "60")

    def test_15m_is_local_only_for_daily_base(self):
        result = confirmation_nodes.confirm_with_child_trend_types(
            [{"high": 110, "low": 100}, {"high": 108, "low": 98}, {"high": 109, "low": 101}],
            period="15",
        )

        self.assertFalse(result["confirmed"])
        self.assertEqual(result["confirmation_status"], "local_confirmation_only")
        self.assertIn("15", result["explanation"])

    def test_full_mode_request_is_rejected_in_v1(self):
        result = confirmation_nodes.reject_full_recursive_mode()

        self.assertFalse(result["enabled"])
        self.assertEqual(result["mode"], "full_recursive_mode")
        self.assertEqual(result["status"], "deferred")


if __name__ == "__main__":
    unittest.main()
