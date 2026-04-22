import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from domains.market_activity.report_sections import (
    build_advanced_activity_report_sections,
    build_market_activity_report_sections,
)


class MarketActivityDomainReportSectionsTest(unittest.TestCase):
    def test_build_market_activity_report_sections_renders_hot_rank_and_lhb(self):
        result = build_market_activity_report_sections(
            data={
                "hot_rank_top30": [{"name": "军工一号", "code": "000001", "rate": 230000, "concepts": ["军工"], "popularity_tag": "龙头"}],
                "zt_pool": [],
                "dt_pool": [],
                "turnover_over_100b": [{"name": "军工一号", "code": "sz000001", "turnover": 123.4}],
                "turnover_rank": [],
                "sector_fund_flow": {
                    "inflow": [{"name": "军工", "zljlr": 12.3, "zdf": 1.23}],
                    "outflow": [{"name": "消费", "zljlr": -9.8, "zdf": -1.8}],
                },
                "lhb_net_buy_top10": [{"rank": 1, "code": "000001", "net_buy_amount_yi": 3.2, "name": "军工一号", "zt_status": "正常", "sector": "军工"}],
                "lhb_net_sell_top10": [{"rank": 1, "code": "000002", "net_buy_amount_yi": -2.1, "name": "消费一号", "zt_status": "正常", "sector": "消费"}],
                "lianban_data": [],
            },
            target_date="2026-04-22",
            stock_full_info={
                "000001": {"change_pct": 5.2, "high": 12.3, "low": 11.1, "open": 11.2, "close": 12.0, "name": "军工一号"},
                "000002": {"change_pct": -3.1, "high": 8.5, "low": 7.9, "open": 8.4, "close": 8.0, "name": "消费一号"},
            },
            get_stock_status=lambda *args, **kwargs: "正常",
            get_stock_sector=lambda *args, **kwargs: "军工",
            analyze_candlestick_pattern=lambda *args, **kwargs: ("阳线", 80, "强"),
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("## 四、热度前三十个股", rendered)
        self.assertIn("| 1 | 军工一号 | 000001 | 23.0w | 军工 | +5.20% |", rendered)
        self.assertIn("## 七、龙虎榜数据", rendered)
        self.assertIn("| 1 | 军工一号 | 000001 | 3.20亿 | 军工 | +5.20% |", rendered)
        self.assertTrue(any(log["step"] == "render.market_activity_sections" for log in result["module_logs"]))

    def test_build_advanced_activity_report_sections_renders_lianban_and_signals(self):
        result = build_advanced_activity_report_sections(
            data={
                "lianban_data": [
                    {
                        "lianban_days": 2,
                        "name": "军工二号",
                        "code": "000003",
                        "first_limit_time": "09:45",
                        "reason": "军工主升",
                        "plates": ["军工"],
                    }
                ],
                "volume_anomalies": [{"stock_name": "军工二号", "anomaly_type": "放量突破", "strength": "高", "volume_percentile": 98, "price_change": 6.5, "reason": "量价齐升"}],
                "lhb_analysis": [{"stock_name": "军工二号", "net_buy": 1.5, "money_type": "游资", "pattern": "接力", "recent_appearances": 2, "signal_strength": "强"}],
                "resonance_scores": {
                    "军工": {
                        "total_score": 8.0,
                        "strength_dimensions": ["fund_flow", "limit_up"],
                        "dimension_scores": {"fund_flow": 4, "limit_up": 3, "lhb": 1},
                        "resonance_level": "强共振",
                    }
                },
                "trade_signals": [{"signal_type": "sector", "sector_name": "军工", "score": 8.5, "action": "关注", "reason": "共振最强", "risk_level": "中"}],
            },
            stock_full_info={"000003": {"change_pct": 9.9, "high": 10.0, "low": 9.1, "open": 9.2, "close": 9.9}},
            get_stock_sector=lambda *args, **kwargs: "军工",
            analyze_candlestick_pattern=lambda *args, **kwargs: ("涨停", 95, "强"),
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("## 九、连板梯队", rendered)
        self.assertIn("## 十、AI多维量化分析", rendered)
        self.assertIn("| 军工 | 8.0 | 🔥 强共振 |", rendered)
        self.assertIn("| sector | 军工 | 8.5 | 关注 | 共振最强 | 中 |", rendered)
        self.assertTrue(any(log["step"] == "render.advanced_activity_sections" for log in result["module_logs"]))


if __name__ == "__main__":
    unittest.main()
