import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class EntryCycleCalibrationRuntimeTest(unittest.TestCase):
    def _load_runtime(self):
        try:
            return __import__("research.entry_cycle_calibration_runtime", fromlist=["entry_cycle_calibration_runtime"])
        except ModuleNotFoundError as error:
            self.fail(f"research.entry_cycle_calibration_runtime should exist: {error}")

    def test_success_case_marks_fixed_five_percent_stop_as_false_kill_when_recovery_breaks_out(self):
        runtime = self._load_runtime()

        result = runtime.build_entry_cycle_case(
            {
                "name": "中嘉博创",
                "code": "000889",
                "case_type": "success",
                "first_report_date": "2026-04-10",
                "breakout_date": "2026-04-15",
                "reference_price": 4.35,
            },
            [
                {"date": "2026-04-10", "open": 4.35, "high": 4.35, "low": 4.10, "close": 4.35, "volume": 1000},
                {"date": "2026-04-13", "open": 4.28, "high": 4.35, "low": 3.92, "close": 3.92, "volume": 1800},
                {"date": "2026-04-14", "open": 3.89, "high": 4.31, "low": 3.89, "close": 4.31, "volume": 1200},
                {"date": "2026-04-15", "open": 4.32, "high": 4.74, "low": 4.03, "close": 4.74, "volume": 2600},
            ],
        )

        self.assertEqual(result["cycle_gap_trading_days"], 3)
        self.assertEqual(result["fixed_5pct_stop_result"], "would_false_kill")
        self.assertEqual(result["recommended_stop_mode"], "structure_repair_band")
        self.assertLess(result["max_drawdown_before_breakout_pct"], -5.0)
        self.assertGreater(result["breakout_return_pct"], 8.0)

    def test_counterexample_prefers_reclaim_failure_over_waiting_for_fixed_stop(self):
        runtime = self._load_runtime()

        result = runtime.build_entry_cycle_case(
            {
                "name": "甘肃能源",
                "code": "000791",
                "case_type": "counterexample",
                "first_report_date": "2026-04-13",
                "reference_price": 8.00,
                "reclaim_zone_low": 8.34,
                "reclaim_zone_high": 8.42,
            },
            [
                {"date": "2026-04-13", "open": 7.97, "high": 8.00, "low": 7.97, "close": 8.00, "volume": 1000},
                {"date": "2026-04-14", "open": 8.06, "high": 8.34, "low": 7.84, "close": 8.15, "volume": 3600},
                {"date": "2026-04-15", "open": 8.06, "high": 8.13, "low": 7.82, "close": 8.02, "volume": 1700},
                {"date": "2026-04-16", "open": 8.00, "high": 8.29, "low": 7.88, "close": 8.13, "volume": 1300},
            ],
        )

        self.assertEqual(result["fixed_5pct_stop_result"], "would_not_warn")
        self.assertEqual(result["recommended_stop_mode"], "reclaim_failure_exit")
        self.assertIn("没有站稳", result["interpretation"])

    def test_default_samples_keep_gansu_as_external_memory_case_not_fake_report_record(self):
        runtime = self._load_runtime()

        samples = {item["code"]: item for item in runtime.get_default_entry_cycle_cases()}

        self.assertEqual(
            ["002975", "603906", "000889", "603026", "000791", "600488"],
            list(samples.keys()),
        )
        self.assertEqual(samples["000791"]["first_report_date_source"], "memory_manual")
        self.assertNotEqual(samples["000791"]["first_report_date_source"], "strategy_ledger")

    def test_counterexample_with_early_breakout_keeps_post_breakout_daily_path_to_today(self):
        runtime = self._load_runtime()

        result = runtime.build_entry_cycle_case(
            {
                "name": "津药药业",
                "code": "600488",
                "case_type": "counterexample",
                "first_report_date": "2026-04-03",
                "breakout_date": "2026-04-07",
                "as_of_date": "2026-04-10",
                "reference_price": 6.97,
            },
            [
                {"date": "2026-04-03", "open": 6.96, "high": 6.97, "low": 6.85, "close": 6.97, "volume": 1000},
                {"date": "2026-04-07", "open": 7.30, "high": 7.67, "low": 7.10, "close": 7.67, "volume": 1800},
                {"date": "2026-04-08", "open": 8.36, "high": 8.44, "low": 7.13, "close": 7.36, "volume": 2600},
                {"date": "2026-04-09", "open": 7.15, "high": 7.72, "low": 6.84, "close": 7.08, "volume": 2500},
                {"date": "2026-04-10", "open": 6.67, "high": 6.99, "low": 6.37, "close": 6.42, "volume": 2400},
            ],
        )

        self.assertEqual(result["cycle_gap_trading_days"], 1)
        self.assertEqual([row["date"] for row in result["day_rows"]], ["2026-04-07", "2026-04-08", "2026-04-09", "2026-04-10"])
        self.assertEqual(result["fixed_5pct_stop_result"], "would_cut_loss")
        self.assertEqual(result["recommended_stop_mode"], "a_kill_exit")


if __name__ == "__main__":
    unittest.main()
