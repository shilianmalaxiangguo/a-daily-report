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
