import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.market_fit_calibration import build_market_fit_calibration


class MarketFitCalibrationTest(unittest.TestCase):
    def test_marks_mainline_effective_but_pool_narrow_when_strong_samples_hit_mainline_not_watch_pool(self):
        result = build_market_fit_calibration(
            strong_samples=[
                {"name": "富瀚微", "code": "300613", "sector": "半导体", "shape": "放量涨停"},
                {"name": "华特气体", "code": "688268", "sector": "半导体", "shape": "放量大阳线"},
                {"name": "中嘉博创", "code": "000889", "sector": "通信服务", "shape": "涨停"},
            ],
            current_mainline="半导体",
            observation_pool=[{"name": "旧观察", "code": "000001", "sector": "半导体"}],
        )

        self.assertEqual(result["fit_label"], "主线有效，池子偏窄")
        self.assertIn("强势样本3只", result["evidence_text"])
        self.assertIn("主线命中2只", result["evidence_text"])
        self.assertIn("观察池命中0只", result["evidence_text"])
        self.assertIn("强势样本集中半导体", result["cycle_note"])
        self.assertEqual(result["action_text"], "只扩主线内强票池")

    def test_marks_data_missing_when_no_strong_samples(self):
        result = build_market_fit_calibration(
            strong_samples=[],
            current_mainline="半导体",
            observation_pool=[],
        )

        self.assertEqual(result["fit_label"], "数据不足")
        self.assertEqual(result["action_text"], "先累计强势样本")


if __name__ == "__main__":
    unittest.main()
