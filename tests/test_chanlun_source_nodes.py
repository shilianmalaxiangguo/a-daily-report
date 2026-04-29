import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from decision.chanlun import source_nodes


def _rows(count):
    return [
        {
            "date": f"2026-01-{(idx % 28) + 1:02d}",
            "datetime": f"2026-01-{(idx % 28) + 1:02d} 15:00:00",
            "open": 100 + idx,
            "high": 105 + idx,
            "low": 95 + idx,
            "close": 101 + idx,
            "volume": 1000 + idx,
            "amount": 10000 + idx,
        }
        for idx in range(count)
    ]


class ChanlunSourceNodesTest(unittest.TestCase):
    def test_select_practical_daily_window_uses_250_base_and_120_focus(self):
        window = source_nodes.select_practical_daily_window(_rows(300))

        self.assertEqual(window["mode"], "practical_daily_mode")
        self.assertEqual(len(window["base_rows"]), 250)
        self.assertEqual(len(window["focus_rows"]), 120)
        self.assertFalse(window["minute_data_required"])
        self.assertEqual(window["data_capability"]["capability_status"], "sufficient")

    def test_daily_window_reports_data_insufficient_without_failing_shape(self):
        window = source_nodes.select_practical_daily_window(_rows(80))

        self.assertEqual(len(window["base_rows"]), 80)
        self.assertEqual(len(window["focus_rows"]), 80)
        self.assertEqual(window["data_capability"]["capability_status"], "data_insufficient")
        self.assertEqual(window["data_capability"]["requested_bars"], 250)
        self.assertEqual(window["data_capability"]["returned_bars"], 80)

    def test_build_minute_capability_marks_15m_as_local_only(self):
        capability = source_nodes.build_minute_capability(
            provider="akshare.stock_zh_a_minute",
            period="15",
            requested_bars=2500,
            returned_bars=1970,
            returned_trading_days=124,
            first_datetime="2025-10-27 11:15:00",
            last_datetime="2026-04-29 11:30:00",
        )

        self.assertEqual(capability["period"], "15")
        self.assertEqual(capability["capability_status"], "local_confirmation_only")
        self.assertFalse(capability["supports_250_day_base"])


if __name__ == "__main__":
    unittest.main()
