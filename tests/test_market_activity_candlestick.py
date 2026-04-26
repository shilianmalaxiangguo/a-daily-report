import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from domains.market_activity.candlestick import analyze_candlestick_pattern


class MarketActivityCandlestickTest(unittest.TestCase):
    def test_analyze_candlestick_pattern_scores_early_limit_boards(self):
        name, score, suggestion = analyze_candlestick_pattern(
            10.0,
            10.0,
            10.0,
            10.0,
            9.95,
            first_limit_time="09:32:00",
        )

        self.assertEqual(name, "一字板加速(9:35前封板+3)")
        self.assertEqual(score, 13)
        self.assertIn("最强加速", suggestion)

    def test_analyze_candlestick_pattern_penalizes_upper_shadow_big_yang(self):
        name, score, suggestion = analyze_candlestick_pattern(
            10.0,
            10.8,
            11.3,
            9.9,
            6.2,
        )

        self.assertEqual(name, "放量大阳线+长上影线(4.6%)")
        self.assertEqual(score, 0)
        self.assertIn("长上影线", suggestion)

    def test_analyze_candlestick_pattern_treats_near_limit_open_break_and_reseal_as_t_board(self):
        name, score, suggestion = analyze_candlestick_pattern(
            55.90,
            56.08,
            56.08,
            54.21,
            20.01,
        )

        self.assertEqual(name, "T字板分歧转一致")
        self.assertEqual(score, 8)
        self.assertIn("炸板后回封", suggestion)

    def test_analyze_candlestick_pattern_handles_shock_and_downtrend(self):
        self.assertEqual(
            analyze_candlestick_pattern(10.0, 10.05, 10.08, 9.98, 1.0)[0],
            "震荡整理",
        )
        self.assertEqual(
            analyze_candlestick_pattern(10.0, 9.6, 10.1, 9.4, -4.0)[0],
            "下跌趋势",
        )


if __name__ == "__main__":
    unittest.main()
