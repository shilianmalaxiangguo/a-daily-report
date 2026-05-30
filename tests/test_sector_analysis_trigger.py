import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from domains.market_state.sector_analysis_trigger import evaluate_sector_analysis_trigger


class SectorAnalysisTriggerTest(unittest.TestCase):
    def test_observe_phase_does_not_trigger_under_conservative_conditions(self):
        cases = [
            {
                "name": "observe",
                "input": {
                    "window_state": "observe",
                    "mainline_pattern": "单主线聚焦",
                    "turnover_quality": "做多放量",
                },
            },
            {
                "name": "no_mainline",
                "input": {
                    "window_state": "open",
                    "mainline_pattern": "无主线",
                    "turnover_quality": "做多放量",
                },
            },
            {
                "name": "rotation",
                "input": {
                    "window_state": "open",
                    "mainline_pattern": "混沌轮动",
                    "turnover_quality": "做多放量",
                },
            },
            {
                "name": "relay",
                "input": {
                    "window_state": "open",
                    "mainline_pattern": "混沌接力",
                    "turnover_quality": "做多放量",
                },
            },
            {
                "name": "sell_pressure_volume",
                "input": {
                    "window_state": "open",
                    "mainline_pattern": "单主线聚焦",
                    "turnover_quality": "杀跌放量",
                },
            },
            {
                "name": "low_turnover",
                "input": {
                    "window_state": "open",
                    "mainline_pattern": "单主线聚焦",
                    "turnover_quality": "缩量",
                },
            },
            {
                "name": "pending",
                "input": {
                    "window_state": "open",
                    "mainline_pattern": "单主线聚焦",
                    "turnover_quality": "待累计",
                },
            },
        ]

        for case in cases:
            with self.subTest(name=case["name"]):
                result = evaluate_sector_analysis_trigger(case["input"])

                self.assertFalse(result["should_analyze"])
                self.assertEqual(result["phase"], "粘合期")
                self.assertEqual(result["dimensions"], [])
                self.assertEqual(result["reason"], "条件偏观察，先不做板块内部分析。")

    def test_confirm_next_phase_triggers_partial_dimensions(self):
        cases = ["双主线竞争", "主线+背景线", "交替竞争"]

        for mainline_pattern in cases:
            with self.subTest(mainline_pattern=mainline_pattern):
                result = evaluate_sector_analysis_trigger(
                    {
                        "window_state": "confirm_next",
                        "mainline_pattern": mainline_pattern,
                        "turnover_quality": "做多放量",
                    }
                )

                self.assertTrue(result["should_analyze"])
                self.assertEqual(result["phase"], "接替期")
                self.assertEqual(result["dimensions"], ["中军识别与跟踪", "板块间资金流动"])
                self.assertEqual(result["reason"], "接替期看竞争关系，先盯中军和资金流向。")

    def test_summary_mainline_regime_alias_triggers_partial_dimensions(self):
        result = evaluate_sector_analysis_trigger(
            {
                "window_state": "confirm_next",
                "mainline_regime": "主线+背景线",
                "turnover_quality": "做多放量",
            }
        )

        self.assertTrue(result["should_analyze"])
        self.assertEqual(result["phase"], "接替期")
        self.assertEqual(result["dimensions"], ["中军识别与跟踪", "板块间资金流动"])

    def test_summary_sector_relationship_state_alias_triggers_alternating_competition(self):
        result = evaluate_sector_analysis_trigger(
            {
                "window_state": "confirm_next",
                "sector_relationship_state": "交替竞争",
                "turnover_quality": "做多放量",
            }
        )

        self.assertTrue(result["should_analyze"])
        self.assertEqual(result["phase"], "接替期")
        self.assertEqual(result["dimensions"], ["中军识别与跟踪", "板块间资金流动"])

    def test_open_phase_triggers_full_dimensions(self):
        result = evaluate_sector_analysis_trigger(
            {
                "window_state": "open",
                "mainline_pattern": "单主线聚焦",
                "turnover_quality": "做多放量",
            }
        )

        self.assertTrue(result["should_analyze"])
        self.assertEqual(result["phase"], "分化确认期")
        self.assertEqual(
            result["dimensions"],
            [
                "中军识别与跟踪",
                "板块内相对位置",
                "弹性载体识别",
                "后排承接质量",
                "二波创新高群",
            ],
        )
        self.assertEqual(result["reason"], "主线已聚焦，开始看板块内部强弱和接力。")

    def test_open_phase_with_three_days_adds_all_dimensions(self):
        result = evaluate_sector_analysis_trigger(
            {
                "window_state": "open",
                "mainline_pattern": "单主线聚焦",
                "turnover_quality": "做多放量",
                "mainline_days": 3,
            }
        )

        self.assertTrue(result["should_analyze"])
        self.assertEqual(result["phase"], "主线稳定期")
        self.assertEqual(
            result["dimensions"],
            [
                "中军识别与跟踪",
                "板块内相对位置",
                "弹性载体识别",
                "后排承接质量",
                "二波创新高群",
                "板块间资金流动",
            ],
        )
        self.assertEqual(result["reason"], "主线连续3天以上，内部强弱和板块间流向都要看。")

    def test_missing_inputs_fall_back_to_conservative_output(self):
        result = evaluate_sector_analysis_trigger({})

        self.assertFalse(result["should_analyze"])
        self.assertEqual(result["phase"], "粘合期")
        self.assertEqual(result["dimensions"], [])
        self.assertEqual(result["reason"], "条件不完整，先不做板块内部分析。")


if __name__ == "__main__":
    unittest.main()
