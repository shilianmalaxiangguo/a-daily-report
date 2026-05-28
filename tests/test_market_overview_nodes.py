import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.market_overview_nodes import render_market_overview_section


class MarketOverviewNodesTest(unittest.TestCase):
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
            "| ETF容量协同 | 中性偏收缩 | ETF容量、Top50集中度、创新高扩散、融资承接四项未形成同向强化，市场仍按震荡处理。 |",
            rendered,
        )


if __name__ == "__main__":
    unittest.main()
