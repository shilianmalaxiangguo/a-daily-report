import sys
import unittest
from datetime import date, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class MarginPressureRuntimeTest(unittest.TestCase):
    def test_build_margin_pressure_snapshot_calibrates_25_and_250_day_pressure(self):
        from domains.market_state.margin_pressure_runtime import build_margin_pressure_snapshot

        history_rows = []
        start_date = date(2025, 5, 19)
        for index in range(250):
            ratio = 0.70 + index * 0.002
            history_rows.append(
                {
                    "trade_date": (start_date + timedelta(days=index)).isoformat(),
                    "margin_balance_yi": 28000.0 + index,
                    "margin_trading_balance_yi": 28200.0 + index,
                    "short_selling_balance_yi": 200.0,
                    "market_turnover_yi": (28000.0 + index) / ratio,
                    "exchange_count": 3,
                }
            )

        snapshot = build_margin_pressure_snapshot(history_rows)

        self.assertTrue(snapshot["available"])
        self.assertEqual(len(snapshot["rows"]), 25)
        self.assertEqual(snapshot["rows"][-1]["trade_date"], "2026-01-23")
        self.assertAlmostEqual(snapshot["rows"][-1]["margin_turnover_ratio_pct"], 119.8, places=2)
        self.assertEqual(snapshot["rows"][-1]["pressure_label"], "高压")
        self.assertEqual(snapshot["latest_pressure_label"], "高压")
        self.assertGreater(snapshot["calibration"]["latest_percentile"], 99.0)
        self.assertIn("250日分位", snapshot["summary"])
        self.assertIn("融资余额上升、成交额下降", snapshot["usage_note"])

    def test_build_margin_pressure_snapshot_rejects_incomplete_exchange_rows(self):
        from domains.market_state.margin_pressure_runtime import build_margin_pressure_snapshot

        snapshot = build_margin_pressure_snapshot(
            [
                {
                    "trade_date": "2026-05-22",
                    "margin_balance_yi": 15000.0,
                    "market_turnover_yi": 29000.0,
                    "exchange_count": 1,
                }
            ]
        )

        self.assertFalse(snapshot["available"])
        self.assertEqual(snapshot["status"], "incomplete_exchange_rows")
        self.assertIn("交易所融资数据不完整", snapshot["message"])

    def test_build_margin_pressure_snapshot_accepts_market_level_margin_balance_source(self):
        from domains.market_state.margin_pressure_runtime import build_margin_pressure_snapshot

        snapshot = build_margin_pressure_snapshot(
            [
                {
                    "trade_date": "2026-05-21",
                    "margin_balance_yi": 28752.80,
                    "market_turnover_yi": 34816.05,
                    "exchange_count": 1,
                    "source_policy": "eastmoney.rzrq.total.RZYE",
                }
            ],
            target_date="2026-05-22",
        )

        self.assertTrue(snapshot["available"])
        self.assertEqual(snapshot["latest_data_date"], "2026-05-21")
        self.assertEqual(snapshot["target_date"], "2026-05-22")
        self.assertTrue(snapshot["is_stale_for_target"])
        self.assertIn("截至2026-05-21", snapshot["summary"])
        self.assertEqual(snapshot["stale_trade_days"], 1)
        self.assertIn("较目标日2026-05-22滞后1个交易日", snapshot["usage_note"])
        self.assertEqual(snapshot["source"], "eastmoney.rzrq.total.RZYE")

    def test_build_margin_pressure_snapshot_reports_actual_stale_trade_days(self):
        from domains.market_state.margin_pressure_runtime import build_margin_pressure_snapshot

        snapshot = build_margin_pressure_snapshot(
            [
                {
                    "trade_date": "2026-07-23",
                    "margin_balance_yi": 26666.03,
                    "market_turnover_yi": 17577.86,
                    "exchange_count": 3,
                }
            ],
            target_date="2026-07-27",
        )

        self.assertFalse(snapshot["available"])
        self.assertEqual(snapshot["status"], "stale_fact_date")
        self.assertEqual(snapshot["stale_trade_days"], 2)
        self.assertIn("较目标日2026-07-27滞后2个交易日", snapshot["message"])

    def test_build_margin_pressure_snapshot_allows_one_trade_day_lag_from_trade_calendar(self):
        from domains.market_state.margin_pressure_runtime import build_margin_pressure_snapshot

        snapshot = build_margin_pressure_snapshot(
            [
                {
                    "trade_date": "2026-07-24",
                    "margin_balance_yi": 26666.03,
                    "market_turnover_yi": 15379.48,
                    "exchange_count": 3,
                }
            ],
            target_date="2026-07-27",
            trade_dates=["2026-07-24", "2026-07-27"],
        )

        self.assertTrue(snapshot["available"])
        self.assertEqual(snapshot["stale_trade_days"], 1)
        self.assertIn("较目标日2026-07-27滞后1个交易日", snapshot["usage_note"])


if __name__ == "__main__":
    unittest.main()
