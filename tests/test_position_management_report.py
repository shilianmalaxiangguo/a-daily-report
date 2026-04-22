import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from portfolio.position_management_report import analyze_position_management_report


class PositionManagementReportTest(unittest.TestCase):
    def test_analyze_position_management_report_uses_hot_rank_and_sector_flow(self):
        report = analyze_position_management_report(
            data={
                "sector_fund_flow": {
                    "inflow": [{"name": "军工", "zljlr": 18}],
                    "outflow": [],
                },
                "hot_rank_top30": [
                    {"name": "军工一号", "code": "000001", "change_pct": 3.2, "sector": "军工"},
                ],
                "zt_pool": [],
                "dt_pool": [],
                "turnover_rank": [],
                "lhb_net_buy_top10": [],
                "lhb_net_sell_top10": [],
            },
            positions=[{"name": "军工一号", "position": 28}],
            build_trading_philosophy_lines=lambda include_system_requirement=False, compact=False: [
                "- 只做主线",
                "- 看大做小",
            ],
            display_mvp_mode=False,
        )

        self.assertIn("## 【个人持仓管理】（私密信息，仅供参考）", report)
        self.assertIn("| 军工一号 | 28% | 军工 | +3.20% | 未知天 | 🔥 强势流入 | ✅ **持有**（板块强势+个股上涨） |", report)
        self.assertIn("> 只做主线", report)
        self.assertIn("### 交易策略说明", report)


if __name__ == "__main__":
    unittest.main()
