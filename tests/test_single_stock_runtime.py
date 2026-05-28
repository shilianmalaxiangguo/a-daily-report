import subprocess
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

PERMISSION_LABEL = "参与资格"

from diagnostics.single_stock_runtime import (
    build_single_stock_diagnostic_contract,
    compose_single_stock_final_verdict_contract,
    generate_single_stock_diagnostic_markdown,
    resolve_single_stock_snapshot,
    resolve_single_stock_snapshot_contract,
)


def _run_legacy_entry_probe(script_body):
    stub_setup = """
import sys
import types

def _stub_module(name, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    return module

sys.path.insert(0, {scripts_path!r})
sys.modules.update(
    {{
        "data_collector": _stub_module("data_collector", AShareDataCollector=type("AShareDataCollector", (), {{}})),
        "ths_hot_stock": _stub_module(
            "ths_hot_stock",
            fetch_ths_hot_stock=lambda *args, **kwargs: [],
            fetch_hot_stock_with_fallback=lambda *args, **kwargs: [],
        ),
        "ths_hot_list": _stub_module("ths_hot_list", fetch_hot_plate=lambda *args, **kwargs: []),
        "tencent_finance_data": _stub_module("tencent_finance_data", TencentFinanceData=type("TencentFinanceData", (), {{}})),
        "xuangubao_intraday": _stub_module(
            "xuangubao_intraday",
            XuangubaoIntradayAnalyzer=type("XuangubaoIntradayAnalyzer", (), {{}}),
        ),
        "limit_up_down_pool": _stub_module(
            "limit_up_down_pool",
            get_limit_up_pool=lambda *args, **kwargs: ([], set()),
            get_limit_down_pool=lambda *args, **kwargs: ([], set()),
            mark_limit_status=lambda *args, **kwargs: {{}},
        ),
        "strong_stock_pool": _stub_module(
            "strong_stock_pool",
            get_strong_stock_pool=lambda *args, **kwargs: [],
            analyze_strong_stocks_by_sector=lambda *args, **kwargs: {{}},
        ),
        "data_validator": _stub_module("data_validator", DataValidator=type("DataValidator", (), {{}})),
        "quantitative_analyzer": _stub_module(
            "quantitative_analyzer",
            VolumeAnomalyDetector=type("VolumeAnomalyDetector", (), {{}}),
            LHBAnalyzer=type("LHBAnalyzer", (), {{}}),
            ResonanceAnalyzer=type("ResonanceAnalyzer", (), {{}}),
            SignalGenerator=type("SignalGenerator", (), {{}}),
            analyze_volume_anomaly=lambda *args, **kwargs: {{}},
            analyze_lhb=lambda *args, **kwargs: {{}},
            calculate_resonance=lambda *args, **kwargs: {{}},
            generate_trade_signals=lambda *args, **kwargs: {{}},
        ),
        "hot_list_integrated": _stub_module(
            "hot_list_integrated",
            get_integrated_hot_list=lambda *args, **kwargs: {{}},
            analyze_sector_distribution=lambda *args, **kwargs: {{}},
        ),
        "history_cache": _stub_module(
            "history_cache",
            get_cache=lambda *args, **kwargs: {{}},
            HistoryCache=type("HistoryCache", (), {{}}),
        ),
        "llm_service": _stub_module("llm_service", get_llm_service=lambda *args, **kwargs: None),
    }}
)
""".format(scripts_path=str(ROOT / "scripts"))

    result = subprocess.run(
        [sys.executable, "-c", stub_setup + "\n" + script_body],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    return result


class SingleStockRuntimeTest(unittest.TestCase):
    def _load_runtime_module(self):
        try:
            return __import__("diagnostics.single_stock_runtime", fromlist=["single_stock_runtime"])
        except ModuleNotFoundError as error:
            self.fail(f"diagnostics.single_stock_runtime should exist: {error}")

    def test_legacy_single_stock_wrappers_delegate_to_runtime(self):
        result = _run_legacy_entry_probe(
            """
import daily_report_entry_demo
from unittest.mock import patch

snapshot_payload = {"code": "000001", "name": "军工一号"}

with patch.object(daily_report_entry_demo, "run_resolve_single_stock_snapshot", return_value=snapshot_payload) as resolve_mock, \
     patch.object(daily_report_entry_demo, "run_generate_single_stock_diagnostic_markdown", return_value="# stock") as markdown_mock:
    snapshot = daily_report_entry_demo.resolve_single_stock_snapshot(
        {"target_date": "2026-04-22"},
        "000001",
        stock_name="军工一号",
        market_research_bundle={"watchlist": []},
        step2_bundle={"evaluated_stocks": []},
    )
    markdown = daily_report_entry_demo.generate_single_stock_diagnostic_markdown(
        {"target_date": "2026-04-22"},
        "2026-04-22",
        "000001",
        stock_name="军工一号",
        run_mode="replay",
    )

assert resolve_mock.call_args[0][1] == "000001"
assert resolve_mock.call_args.kwargs["stock_name"] == "军工一号"
assert "helpers" in resolve_mock.call_args.kwargs
assert markdown_mock.call_args[0][:3] == ({"target_date": "2026-04-22"}, "2026-04-22", "000001")
assert markdown_mock.call_args.kwargs["stock_name"] == "军工一号"
assert markdown_mock.call_args.kwargs["run_mode"] == "replay"
assert "helpers" in markdown_mock.call_args.kwargs
assert snapshot == snapshot_payload
assert markdown == "# stock"
"""
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_single_stock_runtime_wrappers_expose_helper_bindings(self):
        runtime = self._load_runtime_module()
        exec(
            """
def _single_stock_markdown_probe(data, target_date, stock_code, stock_name='', run_mode='frozen'):
    return runtime_test_helper(target_date, stock_name, normalize_stock_code(stock_code), run_mode)
""",
            runtime.__dict__,
        )

        with patch(
            "diagnostics.single_stock_runtime._generate_single_stock_diagnostic_markdown_legacy_body",
            runtime._single_stock_markdown_probe,
        ):
            result = runtime.generate_single_stock_diagnostic_markdown(
                {"target_date": "2026-04-22"},
                "2026-04-22",
                "1",
                stock_name="军工一号",
                run_mode="replay",
                helpers={
                    "runtime_test_helper": lambda target_date, stock_name, stock_code, run_mode: (
                        target_date,
                        stock_name,
                        stock_code,
                        run_mode,
                    ),
                    "normalize_stock_code": lambda code: str(code).zfill(6),
                },
            )

        self.assertEqual(result, ("2026-04-22", "军工一号", "000001", "replay"))

    def test_generate_single_stock_diagnostic_markdown_has_default_safe_float(self):
        captured = {}

        def fake_contract(*args, **kwargs):
            captured["safe_float"] = kwargs["safe_float"]
            return {"markdown": str(kwargs["safe_float"]("3.5"))}

        with patch("diagnostics.single_stock_runtime.build_single_stock_diagnostic_contract", fake_contract):
            result = generate_single_stock_diagnostic_markdown(
                {"target_date": "2026-05-27"},
                "2026-05-27",
                "603005",
                stock_name="晶方科技",
                helpers={
                    "build_market_phase_context": lambda *args, **kwargs: {},
                    "build_market_research_context_bundle": lambda *args, **kwargs: {},
                    "build_step2_candidate_bundle": lambda *args, **kwargs: {},
                    "build_step3_risk_bundle": lambda *args, **kwargs: {},
                    "resolve_single_stock_snapshot": lambda *args, **kwargs: {},
                    "normalize_stock_code": lambda code: code,
                    "get_trade_permission": lambda *args, **kwargs: {},
                    "fetch_recent_price_bars": lambda *args, **kwargs: [],
                    "evaluate_live_tradability": lambda *args, **kwargs: {},
                    "get_abnormal_follow_risk_signal": lambda *args, **kwargs: {},
                    "analyze_buy_signal": lambda *args, **kwargs: None,
                    "quant_system_available": False,
                    "build_intraday_execution_plan": lambda *args, **kwargs: {},
                    "build_stop_execution_plan": lambda *args, **kwargs: {},
                    "enrich_stop_plan_with_reference_anchors": lambda *args, **kwargs: {},
                    "stop_prior_low_trading_days": 5,
                    "score_candidate_decision_stack": lambda *args, **kwargs: {},
                    "score_execution_candidate": lambda *args, **kwargs: {},
                    "build_strategy_ev_calibration": lambda *args, **kwargs: {},
                    "build_trade_price_focus": lambda *args, **kwargs: {},
                    "render_single_stock_diagnostic_markdown": lambda *args, **kwargs: "",
                },
            )

        self.assertEqual(result, "3.5")
        self.assertEqual(captured["safe_float"]("", 2.0), 2.0)

    def test_generate_single_stock_diagnostic_markdown_has_default_quant_system_unavailable(self):
        captured = {}

        def fake_contract(*args, **kwargs):
            captured["quant_system_available"] = kwargs["quant_system_available"]
            return {"markdown": "quant unavailable"}

        with patch("diagnostics.single_stock_runtime.build_single_stock_diagnostic_contract", fake_contract):
            result = generate_single_stock_diagnostic_markdown(
                {"target_date": "2026-05-27"},
                "2026-05-27",
                "603005",
                stock_name="晶方科技",
                helpers={
                    "build_market_phase_context": lambda *args, **kwargs: {},
                    "build_market_research_context_bundle": lambda *args, **kwargs: {},
                    "build_step2_candidate_bundle": lambda *args, **kwargs: {},
                    "build_step3_risk_bundle": lambda *args, **kwargs: {},
                    "resolve_single_stock_snapshot": lambda *args, **kwargs: {},
                    "normalize_stock_code": lambda code: code,
                    "get_trade_permission": lambda *args, **kwargs: {},
                    "fetch_recent_price_bars": lambda *args, **kwargs: [],
                    "evaluate_live_tradability": lambda *args, **kwargs: {},
                    "get_abnormal_follow_risk_signal": lambda *args, **kwargs: {},
                    "analyze_buy_signal": lambda *args, **kwargs: None,
                    "build_intraday_execution_plan": lambda *args, **kwargs: {},
                    "build_stop_execution_plan": lambda *args, **kwargs: {},
                    "enrich_stop_plan_with_reference_anchors": lambda *args, **kwargs: {},
                    "stop_prior_low_trading_days": 5,
                    "score_candidate_decision_stack": lambda *args, **kwargs: {},
                    "score_execution_candidate": lambda *args, **kwargs: {},
                    "build_strategy_ev_calibration": lambda *args, **kwargs: {},
                    "build_trade_price_focus": lambda *args, **kwargs: {},
                    "render_single_stock_diagnostic_markdown": lambda *args, **kwargs: "",
                },
            )

        self.assertEqual(result, "quant unavailable")
        self.assertFalse(captured["quant_system_available"])

    def test_generate_single_stock_diagnostic_markdown_resolves_single_stock_helper_aliases(self):
        captured = {}

        def fake_contract(*args, **kwargs):
            captured["enriched"] = kwargs["enrich_stop_plan_with_reference_anchors"]({"effective_stop": 1})
            captured["stop_days"] = kwargs["stop_prior_low_trading_days"]
            captured["price_focus"] = kwargs["build_trade_price_focus"]()
            return {"markdown": "aliases resolved"}

        def enrich_alias(stop_plan, *args, **kwargs):
            return {"from_alias": True, **(stop_plan or {})}

        def price_focus_alias(*args, **kwargs):
            return {"key_zone_display": "alias"}

        with patch("diagnostics.single_stock_runtime.build_single_stock_diagnostic_contract", fake_contract):
            result = generate_single_stock_diagnostic_markdown(
                {"target_date": "2026-05-27"},
                "2026-05-27",
                "603005",
                stock_name="晶方科技",
                helpers={
                    "build_market_phase_context": lambda *args, **kwargs: {},
                    "build_market_research_context_bundle": lambda *args, **kwargs: {},
                    "build_step2_candidate_bundle": lambda *args, **kwargs: {},
                    "build_step3_risk_bundle": lambda *args, **kwargs: {},
                    "resolve_single_stock_snapshot": lambda *args, **kwargs: {},
                    "normalize_stock_code": lambda code: code,
                    "get_trade_permission": lambda *args, **kwargs: {},
                    "fetch_recent_price_bars": lambda *args, **kwargs: [],
                    "evaluate_live_tradability": lambda *args, **kwargs: {},
                    "get_abnormal_follow_risk_signal": lambda *args, **kwargs: {},
                    "analyze_buy_signal": lambda *args, **kwargs: None,
                    "build_intraday_execution_plan": lambda *args, **kwargs: {},
                    "build_stop_execution_plan": lambda *args, **kwargs: {},
                    "_enrich_stop_plan_with_reference_anchors": enrich_alias,
                    "STOP_PRIOR_LOW_TRADING_DAYS": 5,
                    "score_candidate_decision_stack": lambda *args, **kwargs: {},
                    "score_execution_candidate": lambda *args, **kwargs: {},
                    "build_strategy_ev_calibration": lambda *args, **kwargs: {},
                    "_build_trade_price_focus": price_focus_alias,
                    "render_single_stock_diagnostic_markdown": lambda *args, **kwargs: "",
                },
            )

        self.assertEqual(result, "aliases resolved")
        self.assertEqual(captured["enriched"]["from_alias"], True)
        self.assertEqual(captured["stop_days"], 5)
        self.assertEqual(captured["price_focus"]["key_zone_display"], "alias")

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

    def test_resolve_single_stock_snapshot_uses_compute_bar_change_pct_alias(self):
        result = resolve_single_stock_snapshot(
            {
                "target_date": "2026-05-27",
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
            "603005",
            stock_name="晶方科技",
            market_research_bundle={
                "watchlist": [],
                "abnormal_watch_pool_all": [],
                "leader_memory_bank": [],
                "hot_stocks": [],
            },
            step2_bundle={"evaluated_stocks": []},
            helpers={
                "normalize_stock_code": lambda code: str(code).zfill(6) if code else "",
                "get_stock_sector": lambda *args, **kwargs: "半导体",
                "fetch_recent_price_bars": lambda *args, **kwargs: [
                    {"open": 20.0, "high": 20.8, "low": 19.8, "close": 20.0, "amount": 100000},
                    {"open": 20.2, "high": 21.8, "low": 20.1, "close": 21.0, "amount": 120000},
                ],
                "_compute_bar_change_pct": lambda latest_bar, prev_bar=None: 5.0,
            },
        )

        self.assertEqual(result["code"], "603005")
        self.assertEqual(result["change"], 5.0)
        self.assertEqual(result["sector"], "半导体")

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
                "permission_label": PERMISSION_LABEL,
                "permission_reason": "主线核心且环境可做",
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
        self.assertEqual(result["payload"]["permission_label"], PERMISSION_LABEL)
        self.assertEqual(result["payload"]["final_verdict"], "进入执行等待区")
        self.assertEqual(result["markdown"], "军工一号|明日核心|进入执行等待区")
        self.assertTrue(any(log["step"] == "render.markdown" for log in result["module_logs"]))


if __name__ == "__main__":
    unittest.main()
