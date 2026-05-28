import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def _m(*parts):
    return "".join(parts)

from daily_report_analysis_utils import merge_position_gate
from decision.market_phase_context import build_market_phase_context_contract


class MarketPhaseContextContractTest(unittest.TestCase):
    def test_daily_report_entry_uses_250_day_zhongshu_lookback(self):
        import daily_report_entry_demo

        captured_kwargs = {}

        def fake_market_phase_contract(*args, **kwargs):
            captured_kwargs.update(kwargs)
            return {"module_logs": []}

        with patch.object(
            daily_report_entry_demo,
            "build_market_phase_context_contract",
            side_effect=fake_market_phase_contract,
        ):
            daily_report_entry_demo.build_market_phase_context(
                {"zt_pool": [], "dt_pool": []},
                "2026-04-27",
                emit_logs=False,
            )

        self.assertEqual(captured_kwargs["market_zhongshu_lookback_days"], 250)
        self.assertEqual(captured_kwargs["market_zhongshu_min_klines"], 20)

    def test_default_zhongshu_request_uses_250_day_structural_base(self):
        captured_kwargs = {}

        def analyze_market_zhongshu(**kwargs):
            captured_kwargs.update(kwargs)
            return {"success": False}

        build_market_phase_context_contract(
            data={"zt_pool": [], "dt_pool": [], "market_stats": {"up_count": 1000, "down_count": 2000}},
            target_date="2026-04-27",
            analyze_market_zhongshu=analyze_market_zhongshu,
            analyze_market_and_sectors=lambda data: {"market_status": "震荡整理"},
            resolve_market_mainline_context=lambda data, market_analysis: {
                "main_sectors": [],
                "secondary_sectors": [],
                "main_sectors_info": [],
                "secondary_sectors_info": [],
                "dragon_stocks": [],
            },
            build_mainline_exit_analysis=lambda data, market_analysis, dragon_stocks, main_sectors: {"overall_level": "黄灯"},
            merge_position_gate=lambda position_level, exit_analysis: {
                "position_level": position_level,
                "operation_state": "防守态",
                "can_new_entry": False,
                "gate_reason": "",
            },
            build_market_state_machine_snapshot=lambda **kwargs: {},
            resolve_environment_display_contract=lambda **kwargs: {
                "position_level": kwargs["position_level"],
                "operation_state": kwargs["final_gate"]["operation_state"],
            },
            calculate_price_range=lambda item: {},
        )

        self.assertEqual(captured_kwargs["recent_days"], 250)
        self.assertEqual(captured_kwargs["min_zhongshu_klines"], 20)

    def test_rising_index_inside_zhongshu_does_not_force_empty_position_from_breadth_divergence(self):
        result = build_market_phase_context_contract(
            {
                "zt_pool": [{"code": "000001"}] * 59,
                "dt_pool": [{"code": "000002"}] * 20,
                "indices": {"上证指数": {"涨跌幅": -0.33}},
                "market_stats": {"up_count": 1994, "down_count": 3085},
                "total_turnover": 26414.92,
                "hot_rank_top30": [{"close": 10.0, "open": 10.0, "high": 10.5, "low": 9.8, "change_pct": 3.5}],
                "sector_trend_snapshot": [{"sector": "半导体", "trend_count": 2}],
            },
            "2026-04-24",
            analyze_market_zhongshu=lambda **kwargs: {
                "success": True,
                "current_zhongshu": {
                    "start_date": "2026-04-14",
                    "end_date": "2026-04-23",
                    "start_close": 4026.62,
                    "end_close": 4093.25,
                    "zd": 3992.40,
                    "zg": 4114.84,
                },
                "signal": {
                    "signal_type": "按个股信号操作",
                    "status": "➖ 中枢内震荡",
                    "comparison_state": "range",
                    "today_price": 4079.90,
                    "dist_to_zd": 0.0219,
                    "dist_to_zg": -0.0085,
                },
            },
            analyze_market_and_sectors=lambda data: {"market_status": "震荡整理"},
            resolve_market_mainline_context=lambda data, market_analysis: {
                "main_sectors_info": [{"name": "半导体"}],
                "secondary_sectors_info": [{"name": "电池"}],
                "main_sectors": ["半导体"],
                "secondary_sectors": ["电池"],
                "dragon_stocks": [],
            },
            build_mainline_exit_analysis=lambda data, market_analysis, dragon_stocks, main_sectors: {
                "overall_level": "黄灯",
                "sector_name": "半导体",
            },
            merge_position_gate=merge_position_gate,
            build_market_state_machine_snapshot=lambda **kwargs: {
                "execution_bias": "divergence_only",
                "operation_state": kwargs["final_gate"]["operation_state"],
                "energy_state": "分歧防守",
            },
            resolve_environment_display_contract=lambda **kwargs: {
                "position_level": kwargs["position_level"],
                "operation_state": kwargs["final_gate"]["operation_state"],
                "headline": "指数上行中枢内，防守观察",
            },
            calculate_price_range=lambda stock: {"buy_range": "9.8 - 10.2"},
        )

        self.assertEqual(result["position_level"], "二档（防守档）")
        self.assertTrue(result["final_gate"]["can_hold"])
        self.assertFalse(result["final_gate"]["can_new_entry"])
        self.assertIn("09:50-10:10窗口", result["final_gate"]["final_action"])
        self.assertIn("50%标准进攻", result["final_gate"]["final_action"])
        self.assertNotIn(_m("30%", "条件试错"), result["final_gate"]["final_action"])
        self.assertIn("指数仍在上行中枢内", result["position_reason"])
        self.assertTrue(any(log["step"] == "index_recovery_guard" for log in result["module_logs"]))

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
                "headline": "环境可做",
            },
            calculate_price_range=lambda stock: {"buy_range": "9.8 - 10.2"},
        )

        self.assertEqual(result["position_level"], "三档（进攻档）")
        self.assertTrue(result["final_gate"]["can_new_entry"])
        self.assertIn("普涨行情允许围绕最强趋势参与", result["final_gate"]["final_action"])
        self.assertEqual(result["environment_display"]["headline"], "环境可做")
        self.assertGreaterEqual(len(result["module_logs"]), 3)
        self.assertTrue(any(log["step"] == "gate_override" for log in result["module_logs"]))

    def test_forming_current_zhongshu_does_not_upgrade_breakout_to_attack_gate(self):
        result = build_market_phase_context_contract(
            {
                "zt_pool": [{"code": "000001"}] * 30,
                "dt_pool": [],
                "indices": {"上证指数": {"涨跌幅": 1.23}},
                "market_stats": {"up_count": 3200, "down_count": 1200},
                "hot_rank_top30": [{"close": 10.0, "open": 10.0, "high": 10.5, "low": 9.8, "change_pct": 3.5}],
                "sector_trend_snapshot": [],
            },
            "2026-04-22",
            analyze_market_zhongshu=lambda **kwargs: {
                "success": True,
                "signal": {
                    "signal_type": "大盘突破",
                    "status": "⏳ 当前中枢形成中（6/20，原信号：✅ 突破中枢，仅观察）",
                    "structure_confirmation": "forming",
                },
            },
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
                "position_level": position_level,
                "operation_state": "防守态",
                "can_new_entry": False,
                "can_hold": True,
                "should_reduce": False,
                "gate_reason": "当前中枢未确认，先防守",
            },
            build_market_state_machine_snapshot=lambda **kwargs: {
                "execution_bias": "observe",
                "operation_state": "防守态",
                "energy_state": "形成中观察",
            },
            resolve_environment_display_contract=lambda **kwargs: {
                "position_level": kwargs["position_level"],
                "operation_state": "防守态",
                "headline": "形成中观察",
            },
            calculate_price_range=lambda stock: {"buy_range": "9.8 - 10.2"},
        )

        self.assertEqual(result["position_level"], "二档（防守档）")
        self.assertFalse(result["final_gate"]["can_new_entry"])
        self.assertNotIn("中枢突破是最高优先级信号", result["final_gate"].get("gate_reason", ""))
        self.assertIn("未满20根", result["position_reason"])

    def test_daily_candidate_with_unconfirmed_60m_stays_defensive(self):
        result = build_market_phase_context_contract(
            data={"zt_pool": [], "dt_pool": [], "market_stats": {"up_count": 1000, "down_count": 2000}},
            target_date="2026-04-27",
            analyze_market_zhongshu=lambda **kwargs: {
                "success": True,
                "daily_structure_current": {
                    "candidate_status": "daily_candidate_forming",
                    "kline_count": 9,
                    "required_kline_count": 20,
                },
                "chanlun_confirmation": {
                    "confirmation_status": "forming_daily_level_zhongshu",
                    "confirmed": False,
                },
                "signal": {
                    "signal_type": "按个股信号操作",
                    "status": "⏳ 日K候选形成中（9/20，结构确认：forming_daily_level_zhongshu）",
                    "comparison_state": "range",
                },
            },
            analyze_market_and_sectors=lambda data: {"market_status": "震荡整理"},
            resolve_market_mainline_context=lambda data, market_analysis: {
                "main_sectors": ["半导体"],
                "secondary_sectors": [],
                "main_sectors_info": [],
                "secondary_sectors_info": [],
                "dragon_stocks": [],
            },
            build_mainline_exit_analysis=lambda data, market_analysis, dragon_stocks, main_sectors: {"overall_level": "黄灯"},
            merge_position_gate=lambda position_level, exit_analysis: {
                "position_level": position_level,
                "operation_state": "防守态",
                "can_new_entry": False,
                "gate_reason": "日K候选未确认",
            },
            build_market_state_machine_snapshot=lambda **kwargs: {},
            resolve_environment_display_contract=lambda **kwargs: {"position_level": kwargs["position_level"], "operation_state": "防守态"},
            calculate_price_range=lambda item: {},
        )

        self.assertIn("防守", result["position_level"])
        self.assertFalse(result["final_gate"]["can_new_entry"])
        self.assertIn("未确认", result["position_reason"])

    def test_unconfirmed_60m_chanlun_downgrades_breakout_to_defensive(self):
        result = build_market_phase_context_contract(
            data={
                "zt_pool": [{"code": "000001"}] * 12,
                "dt_pool": [],
                "market_stats": {"up_count": 3200, "down_count": 900},
            },
            target_date="2026-04-27",
            analyze_market_zhongshu=lambda **kwargs: {
                "success": True,
                "chanlun_confirmation": {
                    "confirmation_status": "forming_daily_level_zhongshu",
                    "confirmed": False,
                },
                "signal": {
                    "signal_type": "大盘突破",
                    "status": "突破中枢",
                    "comparison_state": "above",
                },
            },
            analyze_market_and_sectors=lambda data: {"market_status": "强势上涨"},
            resolve_market_mainline_context=lambda data, market_analysis: {
                "main_sectors": [],
                "secondary_sectors": [],
                "main_sectors_info": [],
                "secondary_sectors_info": [],
                "dragon_stocks": [],
            },
            build_mainline_exit_analysis=lambda data, market_analysis, dragon_stocks, main_sectors: {
                "overall_level": "红灯",
                "sector_name": "暂无明确主线",
            },
            merge_position_gate=lambda position_level, exit_analysis: {
                "position_level": position_level,
                "operation_state": "防守态",
                "can_new_entry": False,
                "gate_reason": "暂无明确主线，先防守",
            },
            build_market_state_machine_snapshot=lambda **kwargs: {},
            resolve_environment_display_contract=lambda **kwargs: {
                "position_level": kwargs["position_level"],
                "operation_state": kwargs["final_gate"]["operation_state"],
            },
            calculate_price_range=lambda item: {},
        )

        self.assertEqual(result["position_level"], "二档（防守档）")
        self.assertFalse(result["final_gate"]["can_new_entry"])
        self.assertNotIn("中枢突破是最高优先级信号", result["final_gate"].get("gate_reason", ""))
        self.assertNotIn("积极做多", result["position_reason"])
        self.assertIn("日K结构证据", result["position_reason"])
        self.assertIn("未确认", result["position_reason"])

    def test_index_recovery_preserves_unconfirmed_60m_chanlun_warning(self):
        result = build_market_phase_context_contract(
            data={
                "zt_pool": [{"code": "000001"}] * 25,
                "dt_pool": [{"code": "000002"}] * 20,
                "market_stats": {"up_count": 1600, "down_count": 2600},
            },
            target_date="2026-04-27",
            analyze_market_zhongshu=lambda **kwargs: {
                "success": True,
                "chanlun_confirmation": {
                    "confirmation_status": "forming_daily_level_zhongshu",
                    "confirmed": False,
                },
                "current_zhongshu": {
                    "start_close": 100.0,
                    "end_close": 102.0,
                    "zd": 99.0,
                    "zg": 103.0,
                },
                "signal": {
                    "signal_type": "按个股信号操作",
                    "status": "➖ 中枢内震荡",
                    "comparison_state": "range",
                    "today_price": 101.5,
                },
            },
            analyze_market_and_sectors=lambda data: {"market_status": "调整"},
            resolve_market_mainline_context=lambda data, market_analysis: {
                "main_sectors": [],
                "secondary_sectors": [],
                "main_sectors_info": [],
                "secondary_sectors_info": [],
                "dragon_stocks": [],
            },
            build_mainline_exit_analysis=lambda data, market_analysis, dragon_stocks, main_sectors: {"overall_level": "黄灯"},
            merge_position_gate=lambda position_level, exit_analysis: {
                "position_level": position_level,
                "operation_state": "防守态",
                "can_new_entry": False,
                "gate_reason": "",
            },
            build_market_state_machine_snapshot=lambda **kwargs: {},
            resolve_environment_display_contract=lambda **kwargs: {
                "position_level": kwargs["position_level"],
                "operation_state": kwargs["final_gate"]["operation_state"],
            },
            calculate_price_range=lambda item: {},
        )

        self.assertEqual(result["position_level"], "二档（防守档）")
        self.assertTrue(any(log["step"] == "index_recovery_guard" for log in result["module_logs"]))
        self.assertIn("日K结构证据", result["position_reason"])
        self.assertIn("未确认", result["position_reason"])

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
