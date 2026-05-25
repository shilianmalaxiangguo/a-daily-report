import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from research.margin_pressure_index_relation import build_margin_pressure_index_relation


class MarginPressureIndexRelationTest(unittest.TestCase):
    def test_build_margin_pressure_index_relation_uses_250_days_for_index_relationship(self):
        rows = []
        for index in range(12):
            date = f"2026-05-{index + 1:02d}"
            ratio = 80.0 + index * 2
            turnover = 30000.0 - index * 400
            rows.append(
                {
                    "trade_date": date,
                    "margin_turnover_ratio_pct": ratio,
                    "margin_balance_yi": turnover * ratio / 100,
                    "market_turnover_yi": turnover,
                    "sh_close": 3000.0 + index * 10,
                    "all_a_close": 5000.0 + index * 20,
                }
            )

        result = build_margin_pressure_index_relation(rows, sample_days=10)

        self.assertEqual(result["sample_days"], 10)
        self.assertEqual(result["display_window_days"], 25)
        self.assertEqual(result["research_window_days"], 250)
        self.assertIn("融资承接比高压", result["buckets"])
        self.assertIn("融资升成交降", result["buckets"])
        self.assertIn("上证指数", result["index_results"])
        self.assertIn("中证全指", result["index_results"])
        self.assertIn("forward_1d", result["index_results"]["上证指数"]["overall"])
        self.assertIsNotNone(result["index_results"]["上证指数"]["overall"]["forward_1d"]["ratio_corr"])
        self.assertIsNotNone(result["index_results"]["中证全指"]["overall"]["forward_3d"]["ratio_corr"])
        self.assertEqual(result["latest"]["trade_date"], "2026-05-12")


if __name__ == "__main__":
    unittest.main()
