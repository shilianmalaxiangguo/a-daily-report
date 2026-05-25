import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT / "scripts"))


class Report20260519DecisionSurfaceTest(unittest.TestCase):
    def _read_report(self, relative_path: str) -> str:
        return (ROOT / relative_path).read_text(encoding="utf-8")

    def test_position_strategy_surfaces_ma_buy_sell_stop_strategy(self):
        from portfolio.position_strategy_report import render_position_strategy_report

        report = render_position_strategy_report(
            data={
                "execution_stage_context": {
                    "extreme_conviction_list": [
                        {
                            "code": "000586",
                            "name": "汇源通信",
                            "sector": "通信设备",
                            "conviction_reason": "板块锚定龙 / 首板",
                            "planned_participation": {
                                "buy_window": "09:30-09:35",
                                "entry_timing": "open_core",
                                "attack_state": "50%",
                            },
                        }
                    ]
                },
                "market_research_snapshot": {
                    "observation": {
                        "tracking_memory_status": {
                            "items": [
                                {
                                    "stock_name": "上峰水泥",
                                    "stock_code": "000672",
                                    "reason": "昨日高惯性样本",
                                }
                            ]
                        }
                    }
                },
            },
            target_date="2026-05-19",
            positions=[{"name": "上峰水泥", "position": 100.0}],
        )

        for expected in (
            "买卖点执行锚点",
            "MA3攻击线",
            "MA7分歧线",
            "MA10认错线",
            "MA20环境线",
            "先有板块/资金/承接资格，再看均线执行锚点",
            "放量大跌超7%",
            "成交量确认",
            "上午做超短主动性，下午做短线确认",
            "汇源通信",
            "上峰水泥",
        ):
            self.assertIn(expected, report)

    def test_position_strategy_applies_ma_roles_to_scenarios(self):
        from portfolio.position_strategy_report import render_position_strategy_report

        report = render_position_strategy_report(
            data={
                "execution_stage_context": {
                    "extreme_conviction_list": [
                        {
                            "code": "000586",
                            "name": "汇源通信",
                            "sector": "通信设备",
                            "conviction_reason": "板块锚定龙 / 首板",
                            "planned_participation": {
                                "buy_window": "09:30-09:35",
                                "entry_timing": "open_core",
                                "attack_state": "50%",
                            },
                        }
                    ]
                }
            },
            target_date="2026-05-19",
            positions=[{"name": "上峰水泥", "position": 100.0}],
        )

        for expected in (
            "MA3攻击线 / MA7分歧线 / MA10认错线 / MA20环境线",
            "上升趋势：站上MA3并守MA7才允许持有或加仓",
            "下降趋势：MA20下方不主动开新仓",
            "V反：先站回MA3，再看MA7是否收复",
            "M顶：跌破MA7先降风险，跌破MA10认错",
            "W底：第二脚不破低点，站回MA3/MA7后才试",
            "A杀：放量大跌超7%或同破MA7/MA10，先处理可卖风险仓位",
            "成交量确认优先于均线形态",
        ):
            self.assertIn(expected, report)

    def test_zero_participation_keeps_decision_anchors(self):
        from portfolio.position_strategy_report import render_position_strategy_report

        report = render_position_strategy_report(
            data={"execution_stage_context": {"extreme_conviction_list": []}},
            target_date="2026-05-19",
            positions=[{"name": "上峰水泥", "position": 100.0}],
        )

        self.assertIn("0%不参与不是没有策略", report)
        self.assertIn("不开新仓时也按MA3/MA7/MA10/MA20管理旧仓和观察对象", report)
        self.assertIn("放量大跌超7%", report)


if __name__ == "__main__":
    unittest.main()
