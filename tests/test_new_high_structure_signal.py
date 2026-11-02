import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from domains.market_activity.new_high_structure import (
    build_new_high_breadth_thresholds,
    build_new_high_structure_signal,
    classify_new_high_breadth_level,
)


def _row(trade_date, count, pct, *, source="same-source", sectors=None):
    return {
        "trade_date": trade_date,
        "source_date": trade_date,
        "source": source,
        "new_high_count": count,
        "all_a_share_pct": pct,
        "sector_distribution": sectors or [],
    }


class NewHighStructureSignalTest(unittest.TestCase):
    def test_classifies_exact_absolute_breadth_boundaries(self):
        cases = [
            (250, 5.0, "extreme_diffusion", "极致扩散"),
            (100, 2.0, "effective_diffusion", "有效扩散"),
            (50, 1.0, "cold_diffusion", "扩散偏冷"),
            (10, 0.2, "very_low_diffusion", "极低扩散"),
            (10, 0.19, "diffusion_fracture", "扩散断层"),
            (9, 0.25, "diffusion_fracture", "扩散断层"),
        ]

        for count, pct, code, label in cases:
            with self.subTest(count=count, pct=pct):
                level = classify_new_high_breadth_level(pct, count)
                self.assertEqual(level["breadth_level"], code)
                self.assertEqual(level["breadth_level_label"], label)

        thresholds = build_new_high_breadth_thresholds()
        self.assertEqual(
            [(item["value"], item["label"]) for item in thresholds["mark_lines"]],
            [
                (5.0, "5% 极致扩散线"),
                (2.0, "2% 有效扩散分界"),
                (1.0, "1% 极低扩散分界"),
                (0.2, "0.2% 断层观察线"),
            ],
        )

    def test_distinguishes_high_to_low_contraction_from_low_level_repair(self):
        contraction = build_new_high_structure_signal(
            {
                "available": True,
                "trend_rows": [
                    _row("2026-07-10", 115, 2.30),
                    _row("2026-07-13", 40, 0.80),
                ],
            },
            "2026-07-13",
        )
        repair = build_new_high_structure_signal(
            {
                "available": True,
                "trend_rows": [
                    _row("2026-07-01", 100, 2.00),
                    _row("2026-07-10", 20, 0.40),
                    _row("2026-07-13", 40, 0.80),
                ],
            },
            "2026-07-13",
        )

        self.assertEqual(contraction["breadth_level_label"], "极低扩散")
        self.assertEqual(contraction["breadth_direction"], "扩散收缩")
        self.assertEqual(contraction["state"], "扩散收缩")
        self.assertEqual(repair["breadth_level_label"], "极低扩散")
        self.assertEqual(repair["breadth_direction"], "低位修复")
        self.assertEqual(repair["state"], "低位修复")

    def test_marks_first_single_digit_rapid_contraction_and_fragmentation(self):
        sectors = [
            {"sector": sector, "new_high_count": 1}
            for sector in ["半导体", "水运", "纺织", "医药", "银行", "机械"]
        ]
        signal = build_new_high_structure_signal(
            {
                "available": True,
                "trend_rows": [
                    _row("2026-07-01", 116, 2.32),
                    _row("2026-07-10", 18, 0.36),
                    _row("2026-07-13", 6, 0.12, sectors=sectors),
                ],
            },
            "2026-07-13",
        )

        self.assertEqual(signal["state"], "扩散断层预警")
        self.assertEqual(signal["breadth_level"], "diffusion_fracture")
        self.assertEqual(signal["breadth_level_label"], "扩散断层")
        self.assertEqual(signal["breadth_direction"], "扩散收缩")
        self.assertEqual(signal["current_count"], 6)
        self.assertEqual(signal["previous_count"], 18)
        self.assertEqual(signal["change_count"], -12)
        self.assertEqual(signal["change_ratio_pct"], -66.67)
        self.assertEqual(signal["window_peak_count"], 116)
        self.assertEqual(signal["peak_retention_pct"], 5.17)
        self.assertTrue(signal["single_digit"])
        self.assertTrue(signal["first_single_digit_in_window"])
        self.assertTrue(signal["rapid_contraction"])
        self.assertTrue(signal["sector_fragmented"])
        self.assertEqual(signal["sector_count"], 6)
        self.assertEqual(signal["top_sector_share_pct"], 16.67)

    def test_hides_precise_cross_day_speed_when_sources_are_not_comparable(self):
        signal = build_new_high_structure_signal(
            {
                "available": True,
                "trend_rows": [
                    {"trade_date": "2026-07-10", "source": "tushare", "new_high_count": 18, "all_a_share_pct": 0.36},
                    {"trade_date": "2026-07-13", "source": "akshare", "new_high_count": 6, "all_a_share_pct": 0.12},
                ],
            },
            "2026-07-13",
        )

        self.assertFalse(signal["history_comparable"])
        self.assertEqual(signal["change_count"], -12)
        self.assertIsNone(signal["change_ratio_pct"])
        self.assertIsNone(signal["peak_retention_pct"])
        self.assertFalse(signal["rapid_contraction"])
        self.assertEqual(signal["breadth_direction"], "待累计")
        self.assertIn("窗口逐日来源未形成同口径，峰值保留率不计算", signal["summary"])
        self.assertIn("逐日采集来源或来源日期未统一", signal["summary"])
        self.assertIn("跨日速度和峰值保留率不计算", signal["summary"])
        self.assertNotIn("事实不足", signal["summary"])
        self.assertNotIn("-66.67%", signal["summary"])
        self.assertNotIn("窗口峰值保留率33.33%", signal["summary"])

    def test_does_not_mark_low_repair_when_adjacent_sources_are_not_comparable(self):
        signal = build_new_high_structure_signal(
            {
                "available": True,
                "trend_rows": [
                    _row("2026-07-10", 20, 0.40, source="tushare"),
                    _row("2026-07-13", 30, 0.60, source="akshare"),
                ],
            },
            "2026-07-13",
        )

        self.assertFalse(signal["history_comparable"])
        self.assertEqual(signal["breadth_direction"], "待累计")
        self.assertEqual(signal["state"], "扩散震荡")
        self.assertIsNone(signal["breadth_level_change_steps"])

    def test_classifies_sustained_low_level_recovery_as_repair(self):
        signal = build_new_high_structure_signal(
            {
                "available": True,
                "trend_rows": [
                    _row("2026-07-01", 20, 0.40),
                    _row("2026-07-02", 5, 0.10),
                    _row("2026-07-03", 6, 0.12),
                    _row("2026-07-06", 8, 0.16),
                ],
            },
            "2026-07-06",
        )

        self.assertEqual(signal["state"], "低位修复")
        self.assertTrue(signal["single_digit"])
        self.assertIn("低位修复", signal["summary"])
        self.assertIn("同源数据连续回升", signal["counterevidence"])

    def test_target_date_mismatch_stops_structure_claim(self):
        signal = build_new_high_structure_signal(
            {
                "available": True,
                "trend_rows": [_row("2026-07-13", 6, 0.12)],
            },
            "2026-07-17",
        )

        self.assertFalse(signal["target_date_match"])
        self.assertEqual(signal["state"], "待累计")
        self.assertIn("目标日未在创新高趋势行中匹配", signal["summary"])
        self.assertNotIn("半导体主导", signal["summary"])

    def test_missing_history_and_sector_ownership_remain_fact_insufficient(self):
        signal = build_new_high_structure_signal(
            {
                "available": True,
                "new_high_count": 6,
                "all_a_share_pct": 0.12,
                "sector_distribution": [
                    {"sector": "待补充板块", "new_high_count": 6, "share_pct": 100.0}
                ],
                "trend_rows": [],
            },
            "2026-07-13",
        )

        self.assertEqual(signal["state"], "待累计")
        self.assertFalse(signal["sector_data_available"])
        self.assertEqual(signal["top_sector"], "")
        self.assertIn("缺少前序创新高趋势行", signal["summary"])
        self.assertNotIn("半导体", signal["summary"])

    def test_top_level_sector_distribution_without_date_is_not_used(self):
        signal = build_new_high_structure_signal(
            {
                "available": True,
                "sector_distribution": [{"sector": "过期板块", "new_high_count": 6}],
                "trend_rows": [
                    _row("2026-07-16", 11, 0.22),
                    {
                        "trade_date": "2026-07-17",
                        "source_date": "2026-07-17",
                        "source": "same-source",
                        "new_high_count": 6,
                        "all_a_share_pct": 0.12,
                    },
                ],
            },
            "2026-07-17",
        )

        self.assertFalse(signal["sector_data_available"])
        self.assertEqual(signal["top_sector"], "")

    def test_top_level_sector_distribution_with_other_date_is_not_used(self):
        signal = build_new_high_structure_signal(
            {
                "available": True,
                "trade_date": "2026-07-16",
                "source_date": "2026-07-16",
                "sector_distribution": [{"sector": "过期板块", "new_high_count": 6}],
                "trend_rows": [
                    _row("2026-07-16", 11, 0.22),
                    {
                        "trade_date": "2026-07-17",
                        "source_date": "2026-07-17",
                        "source": "same-source",
                        "new_high_count": 6,
                        "all_a_share_pct": 0.12,
                    },
                ],
            },
            "2026-07-17",
        )

        self.assertFalse(signal["sector_data_available"])
        self.assertEqual(signal["top_sector"], "")

    def test_top_level_sector_distribution_with_target_date_is_used(self):
        signal = build_new_high_structure_signal(
            {
                "available": True,
                "trade_date": "2026-07-17",
                "source_date": "2026-07-17",
                "sector_distribution": [{"sector": "半导体", "new_high_count": 6}],
                "trend_rows": [
                    _row("2026-07-16", 11, 0.22),
                    {
                        "trade_date": "2026-07-17",
                        "source_date": "2026-07-17",
                        "source": "same-source",
                        "new_high_count": 6,
                        "all_a_share_pct": 0.12,
                    },
                ],
            },
            "2026-07-17",
        )

        self.assertTrue(signal["sector_data_available"])
        self.assertEqual(signal["top_sector"], "半导体")

    def test_unknown_sector_rows_do_not_become_a_false_cluster(self):
        signal = build_new_high_structure_signal(
            {
                "available": True,
                "source": "same-source",
                "trend_rows": [
                    _row("2026-07-16", 11, 0.22),
                    _row(
                        "2026-07-17",
                        9,
                        0.18,
                        sectors=[{"sector": "待补充板块", "new_high_count": 9}],
                    ),
                ],
            },
            "2026-07-17",
        )

        self.assertFalse(signal["sector_data_available"])
        self.assertFalse(signal["sector_fragmented"])
        self.assertFalse(signal["sector_clustered"])
        self.assertIn("不能判断板块成群或主导", signal["summary"])

    def test_duplicate_sector_rows_are_aggregated_before_fragmentation_check(self):
        signal = build_new_high_structure_signal(
            {
                "available": True,
                "trend_rows": [
                    _row("2026-07-16", 11, 0.22),
                    _row(
                        "2026-07-17",
                        6,
                        0.12,
                        sectors=[
                            {"sector": "半导体", "new_high_count": 1},
                            {"sector": "半导体", "new_high_count": 1},
                            {"sector": "水运", "new_high_count": 1},
                            {"sector": "纺织", "new_high_count": 1},
                            {"sector": "医药", "new_high_count": 1},
                            {"sector": "银行", "new_high_count": 1},
                        ],
                    ),
                ],
            },
            "2026-07-17",
        )

        self.assertEqual(signal["sector_count"], 5)
        self.assertEqual(signal["sector_covered_count"], 6)
        self.assertTrue(signal["sector_coverage_valid"])
        self.assertTrue(signal["sector_fragmented"])
        self.assertEqual(signal["top_sector_share_pct"], 33.33)

    def test_sector_coverage_overflow_is_fact_insufficient(self):
        signal = build_new_high_structure_signal(
            {
                "available": True,
                "trend_rows": [
                    _row("2026-07-16", 11, 0.22),
                    _row(
                        "2026-07-17",
                        6,
                        0.12,
                        sectors=[
                            {"sector": "半导体", "new_high_count": 4},
                            {"sector": "半导体", "new_high_count": 4},
                        ],
                    ),
                ],
            },
            "2026-07-17",
        )

        self.assertEqual(signal["sector_count"], 1)
        self.assertEqual(signal["sector_covered_count"], 8)
        self.assertFalse(signal["sector_coverage_valid"])
        self.assertFalse(signal["sector_data_available"])
        self.assertFalse(signal["sector_clustered"])
        self.assertIn("覆盖数8只超过当前新高6只", signal["summary"])
        self.assertNotIn("半导体主导", signal["summary"])


if __name__ == "__main__":
    unittest.main()
