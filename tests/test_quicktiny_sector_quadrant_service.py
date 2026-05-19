import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class _ResponseStub:
    status_code = 200

    def json(self):
        return {
            "quadrants": {
                "highStrong": [
                    {
                        "name": "氟化工",
                        "positionInRange": 100,
                        "recentChange": 6.6,
                        "volumeRatio": 4.1,
                    },
                    {
                        "name": "弱放量",
                        "positionInRange": 72,
                        "recentChange": 3.2,
                        "volumeRatio": 1.0,
                    },
                ],
                "highWeak": [],
                "lowStrong": [],
                "lowWeak": [],
            }
        }


class QuickTinySectorQuadrantServiceTest(unittest.TestCase):
    def test_fetch_sector_quadrant_data_uses_quicktiny_endpoint_and_scores_high_strong(self):
        from market_data.quicktiny_sector_quadrant_service import (
            QUICKTINY_SECTOR_QUADRANT_PROVIDER,
            fetch_sector_quadrant_data,
        )

        calls = []

        result = fetch_sector_quadrant_data(
            period=20,
            strength_period=3,
            request_get=lambda url, timeout=10: calls.append((url, timeout)) or _ResponseStub(),
        )

        self.assertEqual(calls[0][1], 10)
        self.assertIn("stock.quicktiny.cn/api/sector-analysis/quadrant", calls[0][0])
        self.assertIn("period=20", calls[0][0])
        self.assertIn("strengthPeriod=3", calls[0][0])
        self.assertEqual(result["provider"], QUICKTINY_SECTOR_QUADRANT_PROVIDER)
        self.assertEqual(result["high_strong_analysis"]["total"], 2)
        self.assertEqual(result["high_strong_analysis"]["tier1_best"][0]["name"], "氟化工")
        self.assertEqual(result["high_strong_analysis"]["tier1_best"][0]["quality_score"], 90)
        self.assertEqual(result["high_strong_analysis"]["tier3_normal"][0]["name"], "弱放量")


if __name__ == "__main__":
    unittest.main()
