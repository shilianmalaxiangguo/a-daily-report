import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from selection.advantage_dedup_runtime import build_grouped_advantage_score


class AdvantageDedupRuntimeTest(unittest.TestCase):
    def test_same_group_advantages_take_strongest_point_only(self):
        result = build_grouped_advantage_score(
            [
                {"group": "market_selection", "label": "主线核心", "score": 80},
                {"group": "market_selection", "label": "历史记忆", "score": 60},
                {"group": "price_acceptance", "label": "异动抗跌", "score": 70},
            ]
        )

        self.assertEqual(result["total_score"], 150)
        self.assertEqual(result["group_scores"]["market_selection"], 80)
        self.assertEqual(result["group_scores"]["price_acceptance"], 70)
        self.assertEqual(result["repeated_advantage_count"], 1)
        self.assertEqual(result["suppressed_points"][0]["label"], "历史记忆")

    def test_group_caps_limit_small_probability_shape_stack(self):
        result = build_grouped_advantage_score(
            [
                {"group": "shape_confirmation", "label": "正式异动形态", "score": 180},
                {"group": "shape_confirmation", "label": "抗跌样本", "score": 90},
                {"group": "shape_confirmation", "label": "弱转强提示", "score": 160},
            ],
            group_caps={"shape_confirmation": 160},
        )

        self.assertEqual(result["total_score"], 160)
        self.assertEqual(result["group_scores"]["shape_confirmation"], 160)
        self.assertEqual(result["selected_points"][0]["label"], "正式异动形态")
        self.assertEqual(result["selected_points"][0]["raw_score"], 180)
        self.assertEqual(result["repeated_advantage_count"], 2)


if __name__ == "__main__":
    unittest.main()
