import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.market_overview_nodes import evaluate_turnover_quality, render_market_overview_section


class MarketOverviewNodesTest(unittest.TestCase):
    def test_evaluate_turnover_quality_classifies_sell_pressure_volume(self):
        cases = [
            {
                "trade_date": "2026-05-26",
                "total_turnover": 32643.59,
                "up_count": 1354,
                "down_count": 4082,
            },
            {
                "trade_date": "2026-05-27",
                "total_turnover": 32599.04,
                "up_count": 974,
                "down_count": 4489,
            },
        ]

        for case in cases:
            with self.subTest(trade_date=case["trade_date"]):
                result = evaluate_turnover_quality(
                    {
                        "total_turnover": case["total_turnover"],
                        "market_stats": {
                            "up_count": case["up_count"],
                            "down_count": case["down_count"],
                        },
                    }
                )

                self.assertEqual(result["turnover_quality"], "杀跌放量")
                self.assertEqual(result["turnover_quality_desc"], "成交量充沛但上涨家数不足，赚钱效应不足")

    def test_evaluate_turnover_quality_classifies_buying_volume(self):
        result = evaluate_turnover_quality(
            {
                "total_turnover": 31000.0,
                "market_stats": {"up_count": 3200, "down_count": 1200},
            }
        )

        self.assertEqual(result["turnover_quality"], "做多放量")
        self.assertEqual(result["turnover_quality_desc"], "成交量充沛且上涨家数占优，赚钱效应较强")

    def test_evaluate_turnover_quality_classifies_low_turnover(self):
        result = evaluate_turnover_quality(
            {
                "total_turnover": 29246.59,
                "market_stats": {"up_count": 2600, "down_count": 2100},
            }
        )

        self.assertEqual(result["turnover_quality"], "缩量")
        self.assertEqual(result["turnover_quality_desc"], "成交量不足，先按缩量处理")

    def test_evaluate_turnover_quality_handles_missing_breadth(self):
        result = evaluate_turnover_quality({"total_turnover": 32643.59})

        self.assertEqual(result["turnover_quality"], "待累计")
        self.assertEqual(result["turnover_quality_desc"], "成交量或涨跌家数数据不足，暂不判断成交量质量")

    def test_evaluate_turnover_quality_accepts_turnover_data_and_root_breadth(self):
        result = evaluate_turnover_quality(
            {
                "turnover_data": {"total_turnover_yi": 34660.27},
                "up_count": 3200,
                "down_count": 1800,
            }
        )

        self.assertEqual(result["turnover_quality"], "做多放量")
        self.assertEqual(result["turnover_quality_desc"], "成交量充沛且上涨家数占优，赚钱效应较强")

    def test_market_base_renders_etf_turnover_capacity_with_existing_25_day_metrics(self):
        rows = [
            {"trade_date": "2026-05-19", "etf_turnover_yi": 4672.8, "change_pct": "待累计", "covered_etf_count": 1518},
            {"trade_date": "2026-05-20", "etf_turnover_yi": 4362.5, "change_pct": -6.64, "covered_etf_count": 1521},
            {"trade_date": "2026-05-21", "etf_turnover_yi": 5146.8, "change_pct": 17.98, "covered_etf_count": 1525},
            {"trade_date": "2026-05-22", "etf_turnover_yi": 5036.2, "change_pct": -2.15, "covered_etf_count": 1527},
            {"trade_date": "2026-05-25", "etf_turnover_yi": 4484.9, "change_pct": -10.95, "covered_etf_count": 1529},
        ]
        lines = render_market_overview_section(
            {
                "target_date": "2026-05-25",
                "enabled_node_keys": ["header", "indices", "volume"],
                "data": {
                    "total_turnover": 29246.59,
                    "indices": {"上证指数": {"点位": 3900.0, "涨跌幅": 0.18}},
                    "market_stats": {"up_count": 2600, "down_count": 2100},
                    "turnover_rank": [
                        {"turnover": 150.0} for _ in range(50)
                    ],
                    "new_high_feedback": {
                        "available": True,
                        "all_a_share_pct": 3.2,
                    },
                    "margin_pressure": {
                        "available": True,
                        "latest_pressure_label": "中性",
                        "latest_margin_turnover_ratio_pct": 93.5,
                        "latest_data_date": "2026-05-25",
                        "rows": [
                            {
                                "trade_date": "2026-05-25",
                                "margin_turnover_ratio_pct": 93.5,
                                "pressure_label": "中性",
                                "market_turnover_yi": 29246.59,
                            }
                        ],
                    },
                    "etf_turnover_series": {
                        "available": True,
                        "source": "sina.etf.daily_amount",
                        "rows": rows,
                    },
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn(
            "| ETF两市成交额 | 4484.90亿 | 机构容量中性偏收缩 | 近5日-4.02%，区间4362.50亿-5146.80亿，机构容量流量未明显放大。 |",
            rendered,
        )
        self.assertIn(
            "| 成交量质量 | 缩量 | - | 成交量不足，先按缩量处理 |",
            rendered,
        )
        self.assertIn(
            "| ETF容量协同 | 中性偏收缩 | ETF容量、Top50集中度、创新高扩散、融资承接四项未形成同向强化，市场仍按震荡处理。 |",
            rendered,
        )

    def test_market_base_excludes_etf_turnover_rows_after_target_date(self):
        lines = render_market_overview_section(
            {
                "target_date": "2026-07-29",
                "enabled_node_keys": ["header", "indices", "volume"],
                "data": {
                    "total_turnover": 29246.59,
                    "indices": {"上证指数": {"点位": 3900.0, "涨跌幅": 0.18}},
                    "market_stats": {"up_count": 2600, "down_count": 2100},
                    "turnover_rank": [{"turnover": 150.0} for _ in range(50)],
                    "new_high_feedback": {"available": True, "all_a_share_pct": 3.2},
                    "etf_turnover_series": {
                        "available": True,
                        "rows": [
                            {"trade_date": "2026-07-29", "etf_turnover_yi": 4484.9},
                            {"trade_date": "2026-07-30", "etf_turnover_yi": 9000.0},
                        ],
                    },
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("| ETF两市成交额 | 4484.90亿 |", rendered)
        self.assertNotIn("9000.00亿", rendered)

    def test_market_base_sorts_etf_rows_and_ignores_invalid_dates(self):
        lines = render_market_overview_section(
            {
                "target_date": "2026-07-29",
                "enabled_node_keys": ["header", "indices", "volume"],
                "data": {
                    "total_turnover": 29246.59,
                    "indices": {"上证指数": {"点位": 3900.0, "涨跌幅": 0.18}},
                    "market_stats": {"up_count": 2600, "down_count": 2100},
                    "turnover_rank": [{"turnover": 150.0} for _ in range(50)],
                    "new_high_feedback": {"available": True, "all_a_share_pct": 3.2},
                    "etf_turnover_series": {
                        "available": True,
                        "rows": [
                            {"trade_date": "2026-07-29", "etf_turnover_yi": 4484.9},
                            {"trade_date": "07/30/2026", "etf_turnover_yi": 9999.0},
                            {"trade_date": "2026-07-28", "etf_turnover_yi": 4100.0},
                        ],
                    },
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("| ETF两市成交额 | 4484.90亿 |", rendered)
        self.assertNotIn("9999.00亿", rendered)

    def test_market_base_rejects_etf_turnover_when_target_date_row_is_missing(self):
        lines = render_market_overview_section(
            {
                "target_date": "2026-07-29",
                "enabled_node_keys": ["header", "indices", "volume"],
                "data": {
                    "total_turnover": 29246.59,
                    "indices": {"上证指数": {"点位": 3900.0, "涨跌幅": 0.18}},
                    "market_stats": {"up_count": 2600, "down_count": 2100},
                    "turnover_rank": [{"turnover": 150.0} for _ in range(50)],
                    "new_high_feedback": {"available": True, "all_a_share_pct": 3.2},
                    "etf_turnover_series": {
                        "available": True,
                        "rows": [
                            {"trade_date": "2026-07-24", "etf_turnover_yi": 4484.9},
                            {"trade_date": "2026-07-28", "etf_turnover_yi": 4600.0},
                        ],
                    },
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertNotIn("| ETF两市成交额 |", rendered)
        self.assertNotIn("4484.90亿", rendered)
        self.assertNotIn("4600.00亿", rendered)

    def test_market_base_marks_etf_turnover_coverage_anomaly_as_review_needed(self):
        rows = [
            {"trade_date": "2026-06-05", "etf_turnover_yi": 2300.93, "change_pct": "待累计", "covered_etf_count": 1142},
            {"trade_date": "2026-06-08", "etf_turnover_yi": 2091.97, "change_pct": -9.08, "covered_etf_count": 1144},
            {"trade_date": "2026-06-09", "etf_turnover_yi": 1833.32, "change_pct": -12.36, "covered_etf_count": 1150},
            {"trade_date": "2026-06-10", "etf_turnover_yi": 1863.6, "change_pct": 1.65, "covered_etf_count": 1153},
            {
                "trade_date": "2026-06-11",
                "etf_turnover_yi": 665.8,
                "change_pct": -64.28,
                "covered_etf_count": 520,
                "coverage_anomaly": True,
                "coverage_anomaly_reason": "目标日有成交ETF数520只，低于近10个前序样本中位数1150只的70%，样本覆盖不足",
            },
        ]

        lines = render_market_overview_section(
            {
                "target_date": "2026-06-11",
                "enabled_node_keys": ["header", "indices", "volume"],
                "data": {
                    "total_turnover": 30000.0,
                    "indices": {"上证指数": {"点位": 3900.0, "涨跌幅": 0.18}},
                    "market_stats": {"up_count": 2600, "down_count": 2100},
                    "turnover_rank": [{"turnover": 150.0} for _ in range(50)],
                    "new_high_feedback": {"available": True, "all_a_share_pct": 3.2},
                    "margin_pressure": {
                        "available": True,
                        "latest_pressure_label": "中性",
                        "latest_margin_turnover_ratio_pct": 93.5,
                        "latest_data_date": "2026-06-11",
                        "rows": [
                            {
                                "trade_date": "2026-06-11",
                                "margin_turnover_ratio_pct": 93.5,
                                "pressure_label": "中性",
                                "market_turnover_yi": 30000.0,
                            }
                        ],
                    },
                    "etf_turnover_series": {
                        "available": True,
                        "source": "sina.etf.daily_amount",
                        "coverage_anomaly": True,
                        "coverage_status": "partial",
                        "coverage_anomaly_reason": "目标日有成交ETF数520只，低于近10个前序样本中位数1150只的70%，样本覆盖不足",
                        "rows": rows,
                    },
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("| ETF两市成交额 | 665.80亿 | 样本覆盖不足 |", rendered)
        self.assertNotIn("机构容量中性偏收缩 | 近5日", rendered)
        self.assertIn("| ETF容量协同 | 待复核 | ETF容量数据样本不足，暂不判断与其他市场指标的配合。 |", rendered)

    def test_market_base_accepts_list_indices_and_turnover_data_snapshot_shape(self):
        lines = render_market_overview_section(
            {
                "target_date": "2026-06-23",
                "enabled_node_keys": ["header", "indices", "volume"],
                "data": {
                    "turnover_data": {
                        "total_turnover_yi": 34660.27,
                        "date": "2026-06-23",
                    },
                    "up_count": 3200,
                    "down_count": 1800,
                    "indices": [
                        {
                            "code": "000001",
                            "latest_price": 4120.28,
                            "source_change_pct": 0.93,
                            "open": 4090.1,
                            "high": 4133.097,
                            "low": 4075.492,
                            "close": 4120.28,
                        },
                        {
                            "name": "深证成指",
                            "value": 12500.5,
                            "pct_chg": 1.26,
                            "open": 12380.0,
                            "high": 12560.0,
                            "low": 12310.0,
                            "close": 12500.5,
                        },
                        {
                            "index_code": "399006",
                            "price": 2688.81,
                            "change_pct": -0.44,
                            "open": 2701.0,
                            "high": 2705.0,
                            "low": 2679.0,
                            "close": 2688.81,
                        },
                    ],
                    "market_stats": {},
                    "turnover_rank": [{"turnover": 150.0} for _ in range(50)],
                    "new_high_feedback": {"available": True, "all_a_share_pct": 3.2},
                    "margin_pressure": {
                        "available": True,
                        "latest_pressure_label": "中性",
                        "latest_margin_turnover_ratio_pct": 93.5,
                        "latest_data_date": "2026-06-23",
                        "rows": [
                            {
                                "trade_date": "2026-06-23",
                                "margin_turnover_ratio_pct": 93.5,
                                "pressure_label": "中性",
                                "market_turnover_yi": 34660.27,
                            }
                        ],
                    },
                },
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("| 上证指数 | 4120.28 | +0.93% |", rendered)
        self.assertIn("| 深证成指 | 12500.50 | +1.26% |", rendered)
        self.assertIn("| 创业板指 | 2688.81 | -0.44% |", rendered)
        self.assertIn("| 两市成交额 | 34660.27亿 |", rendered)
        self.assertIn("| 成交量质量 | 做多放量 | - | 成交量充沛且上涨家数占优，赚钱效应较强 |", rendered)


if __name__ == "__main__":
    unittest.main()
