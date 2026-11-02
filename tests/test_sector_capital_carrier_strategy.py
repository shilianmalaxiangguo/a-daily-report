import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.sector_capital_carrier_strategy import build_sector_capital_carrier_strategy


class SectorCapitalCarrierStrategyTest(unittest.TestCase):
    def test_rejects_rows_with_non_t0_source_dates(self):
        strategy = build_sector_capital_carrier_strategy(
            "2026-06-12",
            {
                "hot_plates": [{"name": "半导体", "order": 1, "trade_date": "2026-06-15"}],
                "sector_fund_flow": {
                    "inflow": [
                        {
                            "name": "半导体",
                            "change_pct": 2.1,
                            "net_inflow_yi": 18.5,
                            "source_date": "2026-06-15",
                        }
                    ]
                },
                "turnover_rank": [
                    {
                        "code": "600584",
                        "name": "长电科技",
                        "rank": 6,
                        "sector": "半导体",
                        "turnover": 76.0,
                        "date": "2026-06-15",
                    }
                ],
                "integrated_hot_list": [
                    {
                        "code": "600584",
                        "name": "长电科技",
                        "rank": 8,
                        "sector": "半导体",
                        "query_date": "2026-06-15",
                    }
                ],
                "zt_pool_by_sector": {
                    "半导体": [
                        {
                            "code": "600584",
                            "name": "长电科技",
                            "trade_date": "2026-06-15",
                        }
                    ]
                },
                "mainline_turnover_summary": {
                    "current_mainline": "半导体",
                    "trade_date": "2026-06-15",
                },
            },
        )

        self.assertEqual(strategy["action"], "paper_skip")
        self.assertEqual(strategy["selected_sectors"], [])
        self.assertEqual(strategy["paper_candidates"], [])
        self.assertGreaterEqual(len(strategy["source_date_mismatches"]), 6)
        self.assertTrue(
            all(item["expected_trade_date"] == "2026-06-12" for item in strategy["source_date_mismatches"])
        )
        self.assertTrue(
            all(item["source_date"] == "2026-06-15" for item in strategy["source_date_mismatches"])
        )

    def test_keeps_t0_and_undated_rows_for_historical_snapshots(self):
        strategy = build_sector_capital_carrier_strategy(
            "2026-06-12",
            {
                "hot_plates": [{"name": "半导体", "order": 1, "trade_date": "20260612"}],
                "sector_fund_flow": {
                    "inflow": [
                        {
                            "name": "半导体",
                            "change_pct": 2.1,
                            "net_inflow_yi": 18.5,
                            "source_date": "2026-06-12",
                        }
                    ]
                },
                "turnover_rank": [
                    {
                        "code": "600584",
                        "name": "长电科技",
                        "rank": 6,
                        "sector": "半导体",
                        "turnover": 76.0,
                    }
                ],
                "integrated_hot_list": [
                    {
                        "code": "600584",
                        "name": "长电科技",
                        "rank": 8,
                        "sector": "半导体",
                    }
                ],
            },
        )

        self.assertEqual(strategy["action"], "paper_participate")
        self.assertEqual(strategy["primary_candidate"]["stock_label"], "长电科技(600584)")
        self.assertEqual(strategy["source_date_mismatches"], [])

    def test_limit_down_candidate_is_kept_as_risk_review_not_positive_carrier(self):
        strategy = build_sector_capital_carrier_strategy(
            "2026-07-16",
            {
                "hot_plates": [{"name": "半导体", "order": 1, "trade_date": "2026-07-16"}],
                "sector_fund_flow": {
                    "inflow": [
                        {
                            "name": "半导体",
                            "change_pct": 1.8,
                            "net_inflow_yi": 12.5,
                            "lzg_name": "华天科技",
                            "source_date": "2026-07-16",
                        }
                    ]
                },
                "hot_rank_top50": [
                    {
                        "code": "002185",
                        "name": "华天科技",
                        "rank": 1,
                        "sector": "半导体",
                        "change_pct": -10.0,
                        "trade_date": "2026-07-16",
                    }
                ],
                "turnover_rank": [
                    {
                        "code": "002185",
                        "name": "华天科技",
                        "rank": 18,
                        "sector": "半导体",
                        "turnover": 108.16,
                        "change_pct": -10.0,
                        "trade_date": "2026-07-16",
                    }
                ],
            },
        )

        self.assertEqual(strategy["action"], "paper_skip")
        self.assertEqual(strategy["primary_candidate"], {})
        self.assertEqual(strategy["paper_candidates"], [])
        self.assertEqual(strategy["risk_review_candidates"][0]["stock_label"], "华天科技(002185)")
        self.assertIn("同日跌幅-10.00%", strategy["risk_review_candidates"][0]["reason"])
        self.assertIn("只作风险复核", strategy["risk_review_candidates"][0]["reason"])
        self.assertNotIn("趋势容量核心", strategy["risk_review_candidates"][0]["reason"])
        self.assertNotIn("板块锚/资金表领涨", strategy["risk_review_candidates"][0]["reason"])
        carrier_stage = next(stage for stage in strategy["stages"] if stage["title"] == "板块内资金载体")
        self.assertEqual(carrier_stage["survivor_count"], 0)
        self.assertEqual(carrier_stage["eliminated"][0]["label"], "华天科技(002185)")

    def test_does_not_promote_backup_when_leading_carrier_is_price_rejected(self):
        strategy = build_sector_capital_carrier_strategy(
            "2026-07-16",
            {
                "hot_plates": [{"name": "半导体", "order": 1, "trade_date": "2026-07-16"}],
                "hot_rank_top50": [
                    {
                        "code": "002185",
                        "name": "华天科技",
                        "rank": 1,
                        "sector": "半导体",
                        "change_pct": -10.0,
                        "trade_date": "2026-07-16",
                    },
                    {
                        "code": "002156",
                        "name": "通富微电",
                        "rank": 2,
                        "sector": "半导体",
                        "change_pct": 2.5,
                        "trade_date": "2026-07-16",
                    },
                ],
                "turnover_rank": [
                    {
                        "code": "002185",
                        "name": "华天科技",
                        "rank": 1,
                        "sector": "半导体",
                        "turnover": 108.16,
                        "change_pct": -10.0,
                        "trade_date": "2026-07-16",
                    },
                    {
                        "code": "002156",
                        "name": "通富微电",
                        "rank": 2,
                        "sector": "半导体",
                        "turnover": 96.0,
                        "change_pct": 2.5,
                        "trade_date": "2026-07-16",
                    },
                ],
            },
        )

        self.assertEqual(strategy["action"], "paper_skip")
        self.assertEqual(strategy["primary_candidate"], {})
        self.assertEqual(strategy["paper_candidates"][0]["stock_label"], "通富微电(002156)")
        self.assertEqual(strategy["risk_review_candidates"][0]["stock_label"], "华天科技(002185)")
        self.assertIn("备选样本不自动递补", strategy["action_reason"])
        action_stage = next(stage for stage in strategy["stages"] if stage["title"] == "纸面动作")
        self.assertEqual(action_stage["survivor_count"], 0)
        self.assertEqual(action_stage["eliminated"][0]["label"], "通富微电(002156)")
        self.assertIn("不自动递补", action_stage["eliminated"][0]["reason"])

    def test_explicit_cancelable_limit_down_reversal_plan_keeps_candidate_path(self):
        strategy = build_sector_capital_carrier_strategy(
            "2026-07-16",
            {
                "hot_plates": [{"name": "半导体", "order": 1, "trade_date": "2026-07-16"}],
                "hot_rank_top50": [
                    {
                        "code": "600667",
                        "name": "太极实业",
                        "rank": 1,
                        "sector": "半导体",
                        "change_pct": -10.0,
                        "trade_date": "2026-07-16",
                        "execution_eligibility": "跌停反包专项",
                        "participation_window": "09:50-10:10跌停反包确认",
                        "cancellation": "继续封死或站不回VWAP就不参与",
                        "fallback_state": "不满足回到0%不参与",
                    }
                ],
            },
        )

        self.assertEqual(strategy["action"], "paper_watch")
        self.assertEqual(strategy["primary_candidate"]["stock_label"], "太极实业(600667)")
        self.assertEqual(strategy["risk_review_candidates"], [])

    def test_explicit_stock_sector_is_not_overridden_by_research_reason(self):
        strategy = build_sector_capital_carrier_strategy(
            "2026-08-17",
            {
                "hot_plates": [
                    {"name": "半导体", "order": 1, "trade_date": "2026-08-17"}
                ],
                "hot_rank_top50": [
                    {
                        "code": "002081",
                        "name": "金螳螂",
                        "rank": 1,
                        "sector": "装修装饰",
                        "xuangubao_stock_reason": "电子半导体客户推进芯片项目",
                        "trade_date": "2026-08-17",
                    }
                ],
                "turnover_rank": [
                    {
                        "code": "002081",
                        "name": "金螳螂",
                        "rank": 10,
                        "sector": "装修装饰",
                        "turnover": 80.0,
                        "trade_date": "2026-08-17",
                    }
                ],
            },
        )

        self.assertEqual(strategy["selected_sectors"][0]["name"], "半导体")
        self.assertEqual(strategy["paper_candidates"], [])
        self.assertEqual(strategy["primary_candidate"], {})
        self.assertEqual(
            strategy["eliminated_candidates"][0]["stock_label"],
            "金螳螂(002081)",
        )
        self.assertIn(
            "没有落在当日已被资金选择的板块内",
            strategy["eliminated_candidates"][0]["reason"],
        )

    def test_treats_none_row_sets_as_empty_facts(self):
        strategy = build_sector_capital_carrier_strategy(
            "2026-06-12",
            {
                "hot_plates": None,
                "sector_change_up": None,
                "hot_rank_top50": None,
                "integrated_hot_list": None,
                "turnover_rank": None,
                "zt_pool": None,
                "lianban_data": None,
                "sector_fund_flow": {"inflow": None, "outflow": None},
                "zt_pool_by_sector": {"半导体": None},
            },
        )

        self.assertEqual(strategy["action"], "paper_skip")
        self.assertEqual(strategy["selected_sectors"], [])
        self.assertEqual(strategy["paper_candidates"], [])
        self.assertEqual(strategy["source_date_mismatches"], [])


if __name__ == "__main__":
    unittest.main()
