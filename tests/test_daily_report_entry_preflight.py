import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class DailyReportEntryPreflightTest(unittest.TestCase):
    def test_main_aborts_before_snapshot_and_public_publish_when_critical_data_missing_even_without_report(self):
        import daily_report_entry_demo
        from daily_report_render import ReportCriticalDataMissingError

        bad_data = {
            "data_status": {
                "两市成交额": False,
                "中证全指": False,
                "成交额排名": False,
            },
            "total_turnover": 0,
            "wind_a_alternative": {"price": 0},
            "turnover_rank": [],
        }

        with patch.object(sys, "argv", ["daily_report_entry_demo.py", "2026-05-13", "--no-report"]), \
             patch.object(daily_report_entry_demo, "get_daily_data", return_value=bad_data), \
             patch.object(daily_report_entry_demo, "_save_data_snapshot") as save_snapshot_mock, \
             patch.object(daily_report_entry_demo, "publish_snap_ui_public_data") as publish_mock:
            with self.assertRaises(ReportCriticalDataMissingError):
                daily_report_entry_demo.main()

        save_snapshot_mock.assert_not_called()
        publish_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
