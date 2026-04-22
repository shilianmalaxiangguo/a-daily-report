import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from decision.market_phase_context import build_market_phase_context_contract


class MarketPhaseContextContractTest(unittest.TestCase):
    def test_breakout_without_clear_mainline_upgrades_final_gate(self):
        result = build_market_phase_context_contract(
            {
                "zt_pool": [{"code": "000001"}] * 8,
                "dt_pool": [],
                "indices": {"上证指数": {"涨跌幅": 1.23}},
                "market_stats": {"up_count": 3200, "down_count": 1200},
                "hot_rank_top30": [{"close": 10.0, "open": 10.0, "high": 10.5, "low": 9.8, "change_pct": 3.5}],
                "sector_trend_snapshot": [],
            },
            "2026-04-22",
            analyze_market_zhongshu=lambda **kwargs: {"success": True, "signal": {"signal_type": "大盘突破", "status": "突破中枢"}},
            analyze_market_and_sectors=lambda data: {"market_status": "震荡整理"},
            resolve_market_mainline_context=lambda data, market_analysis: {
                "main_sectors_info": [],
                "secondary_sectors_info": [],
                "main_sectors": [],
                "secondary_sectors": [],
                "dragon_stocks": [],
            },
            build_mainline_exit_analysis=lambda data, market_analysis, dragon_stocks, main_sectors: {
                "overall_level": "红灯",
                "sector_name": "暂无明确主线",
            },
            merge_position_gate=lambda position_level, exit_analysis: {
                "gate_status": "防守",
                "position_level": "二档（防守档）",
                "operation_state": "防守态",
                "can_new_entry": False,
                "can_hold": True,
                "should_reduce": False,
                "gate_reason": "暂无明确主线，先防守",
            },
            build_market_state_machine_snapshot=lambda **kwargs: {
                "execution_bias": "allow_execute",
                "operation_state": "进攻态",
                "energy_state": "扩张聚焦",
            },
            resolve_environment_display_contract=lambda **kwargs: {
                "position_level": kwargs["position_level"],
                "operation_state": "进攻态",
                "headline": "环境放行",
            },
            calculate_price_range=lambda stock: {"buy_range": "9.8 - 10.2"},
        )

        self.assertEqual(result["position_level"], "三档（进攻档）")
        self.assertTrue(result["final_gate"]["can_new_entry"])
        self.assertIn("普涨行情允许围绕最强趋势参与", result["final_gate"]["final_action"])
        self.assertEqual(result["environment_display"]["headline"], "环境放行")
        self.assertGreaterEqual(len(result["module_logs"]), 3)
        self.assertTrue(any(log["step"] == "gate_override" for log in result["module_logs"]))

    def test_defensive_position_skips_price_plan_and_keeps_logs(self):
        result = build_market_phase_context_contract(
            {
                "zt_pool": [{"code": "000001"}] * 2,
                "dt_pool": [{"code": "000002"}] * 12,
                "indices": {"上证指数": {"涨跌幅": -1.23}},
                "market_stats": {"up_count": 1200, "down_count": 3200},
                "hot_rank_top30": [{"close": 10.0, "open": 10.0, "high": 10.5, "low": 9.8, "change_pct": 3.5}],
                "sector_trend_snapshot": [],
            },
            "2026-04-22",
            analyze_market_zhongshu=lambda **kwargs: {"success": True, "signal": {"signal_type": "跌破支撑", "status": "跌破支撑"}},
            analyze_market_and_sectors=lambda data: {"market_status": "调整"},
            resolve_market_mainline_context=lambda data, market_analysis: {
                "main_sectors_info": [{"name": "军工"}],
                "secondary_sectors_info": [],
                "main_sectors": ["军工"],
                "secondary_sectors": [],
                "dragon_stocks": [],
            },
            build_mainline_exit_analysis=lambda data, market_analysis, dragon_stocks, main_sectors: {
                "overall_level": "橙灯",
                "sector_name": "军工",
            },
            merge_position_gate=lambda position_level, exit_analysis: {
                "gate_status": "撤退",
                "position_level": "一档（空仓档）",
                "operation_state": "撤退态",
                "can_new_entry": False,
                "can_hold": False,
                "should_reduce": True,
                "gate_reason": "主线退潮确认",
            },
            build_market_state_machine_snapshot=lambda **kwargs: {
                "execution_bias": "avoid",
                "operation_state": "撤退态",
                "energy_state": "收缩防守",
            },
            resolve_environment_display_contract=lambda **kwargs: {
                "position_level": "一档（空仓档）",
                "operation_state": "撤退态",
                "headline": "环境关闭",
            },
            calculate_price_range=lambda stock: {"buy_range": "9.8 - 10.2"},
        )

        self.assertEqual(result["position_level"], "一档（空仓档）")
        self.assertIsNone(result["price_info"])
        self.assertIn("主线退潮确认", result["position_reason"])
        self.assertTrue(any(log["step"] == "final_position" for log in result["module_logs"]))


if __name__ == "__main__":
    unittest.main()
