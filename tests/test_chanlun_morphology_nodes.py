import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from decision.chanlun import morphology_nodes


class ChanlunMorphologyNodesTest(unittest.TestCase):
    def test_merge_inclusion_marks_contained_bars(self):
        rows = [
            {"date": "2026-04-20", "high": 10, "low": 5, "close": 8},
            {"date": "2026-04-21", "high": 9, "low": 6, "close": 7},
            {"date": "2026-04-22", "high": 12, "low": 7, "close": 11},
        ]

        merged = morphology_nodes.merge_inclusion_bars(rows)

        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0]["source_bar_count"], 2)
        self.assertEqual(merged[0]["rule_tier"], "original_rule")

    def test_detect_fractals_uses_processed_bars_only(self):
        processed = [
            {"date": "2026-04-20", "high": 10, "low": 5},
            {"date": "2026-04-21", "high": 12, "low": 7},
            {"date": "2026-04-22", "high": 9, "low": 4},
            {"date": "2026-04-23", "high": 7, "low": 3},
            {"date": "2026-04-24", "high": 8, "low": 4},
        ]

        fractals = morphology_nodes.detect_fractals(processed)

        self.assertEqual(fractals[0]["fractal_type"], "top")
        self.assertEqual(fractals[1]["fractal_type"], "bottom")
        self.assertEqual(fractals[0]["source"], "processed_bars")

    def test_build_strokes_requires_alternating_fractals(self):
        fractals = [
            {"fractal_id": "f1", "fractal_type": "bottom", "index": 0, "date": "2026-04-20", "price": 5},
            {"fractal_id": "f2", "fractal_type": "top", "index": 2, "date": "2026-04-22", "price": 12},
            {"fractal_id": "f3", "fractal_type": "top", "index": 3, "date": "2026-04-23", "price": 13},
            {"fractal_id": "f4", "fractal_type": "bottom", "index": 5, "date": "2026-04-25", "price": 4},
        ]

        strokes = morphology_nodes.build_strokes(fractals)

        self.assertEqual(len(strokes), 2)
        self.assertEqual(strokes[0]["direction"], "up")
        self.assertEqual(strokes[1]["direction"], "down")
        self.assertNotIn("f2", strokes[1]["fractal_ids"])


if __name__ == "__main__":
    unittest.main()
