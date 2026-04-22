import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from diagnostics.single_stock_runtime import (
    build_single_stock_diagnostic_contract,
    compose_single_stock_final_verdict_contract,
    resolve_single_stock_snapshot_contract,
)


class SingleStockRuntimeTest(unittest.TestCase):
    def test_resolve_single_stock_snapshot_contract_merges_watchlist_hit(self):
        result = resolve_single_stock_snapshot_contract(
            data={
                "target_date": "2026-04-22",
                "zt_pool": [],
                "turnover_rank": [],
                "stocks_with_history": [],
                "hot_rank_top30": [],
                "zt_pool_by_sector": {},
                "lianban_data": {"stocks": []},
                "lhb_details": [],
                "sector_fund_flow": [],
                "dt_pool": [],
            },
            stock_code="1",
            stock_name="军工一号",
            market_research_bundle={
                "watchlist": [{"code": "000001", "name": "军工一号", "sector": "军工", "change": 5.2}],
                "abnormal_watch_pool_all": [],
                "leader_memory_bank": [],
                "hot_stocks": [],
            },
            step2_bundle={"evaluated_stocks": []},
            normalize_stock_code=lambda code: str(code).zfill(6) if code else "",
            get_stock_sector=lambda *args, **kwargs: "fallback-sector",
            fetch_recent_price_bars=lambda *args, **kwargs: [],
            safe_float=lambda value: float(value or 0),
            compute_bar_change_pct=lambda latest_bar, prev_bar: 0,
        )

        self.assertEqual(result["stock"]["code"], "000001")
        self.assertEqual(result["stock"]["sector"], "军工")
        self.assertIn("step1_watchlist", result["stock"]["source_tags"])
        self.assertTrue(any(log["step"] == "resolve.snapshot" for log in result["module_logs"]))

    def test_build_single_stock_diagnostic_contract_outputs_markdown_payload(self):
        result = build_single_stock_diagnostic_contract(
            data={"target_date": "2026-04-22"},
            target_date="2026-04-22",
            stock_code="000001",
            stock_name="军工一号",
            run_mode="frozen",
            build_market_phase_context=lambda data, target_date, emit_logs=False: {
                "exit_analysis": {},
                "final_gate": {"can_new_entry": True, "final_action": "允许强势跟随"},
                "position_level": "三档（进攻档）",
                "main_sectors_info": [{"name": "军工"}],
                "secondary_sectors_info": [],
                "main_sectors": ["军工"],
                "secondary_sectors": [],
                "dragon_stocks": [{"code": "000001", "name": "军工一号"}],
            },
            build_market_research_context_bundle=lambda *args, **kwargs: {
                "mainline_name": "军工",
                "candidates": [{"code": "000001"}],
                "watchlist": [{"code": "000001", "name": "军工一号"}],
                "abnormal_watch_map": {},
                "leader_memory_bank": [],
                "hot_stocks": [],
                "zt_pool_by_sector": {},
                "dt_pool_by_sector": {},
                "market_state_snapshot": {
                    "driver_type": "主升",
                    "pulse_stage": "第一阶段",
                    "acceptance_quality": "强",
                    "pulse_action_bias": "主线优先",
                    "energy_state": "修复",
                },
                "step0_plan": {"step0_prediction_cn": "🟢 明朗"},
            },
            build_step2_candidate_bundle=lambda *args, **kwargs: {
                "core_stocks": [{"code": "000001"}],
                "secondary_stocks": [],
                "crossline_observation_stocks": [],
                "gem_observation_stocks": [],
                "extreme_conviction_list": [],
                "evaluated_stocks": [],
            },
            build_step3_risk_bundle=lambda *args, **kwargs: {
                "by_code": {
                    "000001": {
                        "dest": "可按计划",
                        "risk_level": "低风险",
                        "reason": "量价匹配良好",
                        "tomorrow_risk": "若高开过多则放弃",
                        "risk_penalties": [],
                        "repair_buffers": [],
                        "raw_risk_score": 4,
                        "risk_score": 2,
                    }
                }
            },
            resolve_single_stock_snapshot=lambda *args, **kwargs: {
                "stock": {
                    "code": "000001",
                    "name": "军工一号",
                    "sector": "军工",
                    "change": 4.23,
                    "close": 11.0,
                    "volume": 120000.0,
                    "pattern": "平台突破",
                    "source_tags": ["step1_watchlist"],
                },
                "module_logs": [{"step": "resolve.snapshot", "status": "success"}],
            },
            normalize_stock_code=lambda code: str(code).zfill(6) if code else "",
            get_trade_permission=lambda *args, **kwargs: {
                "can_execute": True,
                "permission_label": "执行权",
                "permission_reason": "主线核心且环境放行",
            },
            fetch_recent_price_bars=lambda *args, **kwargs: [
                {"open": 10.2, "high": 10.8, "low": 10.0, "close": 10.5, "amount": 100000},
                {"open": 10.5, "high": 11.1, "low": 10.3, "close": 11.0, "amount": 120000},
            ],
            evaluate_live_tradability=lambda stock, target_date, recent_bars=None: {
                "can_trade": True,
                "status_label": "可交易",
                "reason": "结构正常",
            },
            get_abnormal_follow_risk_signal=lambda stock: {
                "light": "🟢 绿灯",
                "reason": "承接未坏",
                "forecast": "继续观察",
            },
            safe_float=lambda value: float(value or 0),
            analyze_buy_signal=lambda code, name, close_price, volume_value: types.SimpleNamespace(
                is_valid=True,
                signal_type="breakout",
                reason="突破有效",
            ),
            quant_system_available=True,
            build_intraday_execution_plan=lambda *args, **kwargs: {
                "confirm_price_60m": 12.34,
                "stop_plan": {"effective_stop": 11.8},
            },
            build_stop_execution_plan=lambda close_price: {"effective_stop": 11.7},
            enrich_stop_plan_with_reference_anchors=lambda stop_plan, *args, **kwargs: stop_plan,
            stop_prior_low_trading_days=5,
            score_candidate_decision_stack=lambda candidate, **kwargs: {
                "decision_stack": {"environment_score": 8, "ev_score": 7.5}
            },
            score_execution_candidate=lambda payload, calibration: payload,
            build_strategy_ev_calibration=lambda *args, **kwargs: {},
            build_trade_price_focus=lambda minute_plan, stop_plan: {
                "key_zone_display": "12.10-12.40",
                "execution_stop_display": "11.80",
                "hard_stop_display": "11.70",
                "note_text": "先看12.34是否站稳",
            },
            compose_single_stock_final_verdict=compose_single_stock_final_verdict_contract,
            render_single_stock_diagnostic_markdown=lambda payload: (
                f"{payload['name']}|{payload['system_role']}|{payload['final_verdict']}"
            ),
        )

        self.assertEqual(result["payload"]["system_role"], "明日核心")
        self.assertEqual(result["payload"]["permission_label"], "执行权")
        self.assertEqual(result["payload"]["final_verdict"], "进入执行等待区")
        self.assertEqual(result["markdown"], "军工一号|明日核心|进入执行等待区")
        self.assertTrue(any(log["step"] == "render.markdown" for log in result["module_logs"]))


if __name__ == "__main__":
    unittest.main()
