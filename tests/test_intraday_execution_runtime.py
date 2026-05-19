import subprocess
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from execution.intraday_execution_runtime import build_intraday_execution_plan


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

    return subprocess.run(
        [sys.executable, "-c", stub_setup + "\n" + script_body],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )


class IntradayExecutionRuntimeTest(unittest.TestCase):
    def test_legacy_intraday_wrappers_delegate_to_runtime(self):
        result = _run_legacy_entry_probe(
            """
import daily_report_entry_demo
from unittest.mock import patch

bars_payload = [{"datetime": "2026-04-22 10:00", "close": 10.0}]
waiting_payload = {"entry_price": 10.0, "stop_loss": 9.5}

with patch.object(daily_report_entry_demo, "run_fetch_intraday_bars", return_value=bars_payload) as bars_mock, \
     patch.object(daily_report_entry_demo, "run_build_waiting_stock_plan", return_value=waiting_payload) as waiting_mock, \
     patch.object(daily_report_entry_demo, "run_build_intraday_execution_plan", return_value={"ok": True}) as plan_mock:
    bars = daily_report_entry_demo.fetch_intraday_bars("000001", "2026-04-22", period="60", lookback_bars=6)
    plan = daily_report_entry_demo.build_intraday_execution_plan(
        "000889",
        "2026-04-22",
        4.35,
        entry_cycle_profile={"recommended_stop_mode": "structure_repair_band"},
    )
    waiting = daily_report_entry_demo.build_waiting_stock_plan({"code": "000001", "close": 10.0}, "2026-04-22", signal_type="breakout")

assert bars_mock.call_args[0][:2] == ("000001", "2026-04-22")
assert bars_mock.call_args.kwargs["period"] == "60"
assert bars_mock.call_args.kwargs["lookback_bars"] == 6
assert "helpers" in bars_mock.call_args.kwargs
assert plan_mock.call_args[0][:3] == ("000889", "2026-04-22", 4.35)
assert plan_mock.call_args.kwargs["entry_cycle_profile"] == {"recommended_stop_mode": "structure_repair_band"}
assert waiting_mock.call_args[0][:2] == ({"code": "000001", "close": 10.0}, "2026-04-22")
assert waiting_mock.call_args.kwargs["signal_type"] == "breakout"
assert "helpers" in waiting_mock.call_args.kwargs
assert bars == bars_payload
assert plan == {"ok": True}
assert waiting == waiting_payload
"""
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_build_intraday_execution_plan_builds_breakout_confirmation_and_stop(self):
        plan = build_intraday_execution_plan(
            "000001",
            "2026-04-22",
            10.0,
            signal_type="breakout",
            fallback_stop=9.5,
            helpers={
                "INTRADAY_CONFIRM_LOOKBACK_60M": 8,
                "INTRADAY_STOP_LOOKBACK_30M": 12,
                "fetch_intraday_bars": lambda code, target_date, period="30", lookback_bars=12: [
                    {"datetime": "2026-04-22 10:00", "open": 9.8, "high": 10.1, "low": 9.8, "close": 10.0, "volume": 100},
                    {"datetime": "2026-04-22 11:00", "open": 10.0, "high": 10.4, "low": 9.7, "close": 10.3, "volume": 120},
                    {"datetime": "2026-04-22 14:00", "open": 10.2, "high": 10.8, "low": 9.9, "close": 10.7, "volume": 180},
                ] if period == "60" else [
                    {"datetime": "2026-04-22 10:00", "low": 9.65, "high": 10.1, "close": 9.9, "volume": 90},
                    {"datetime": "2026-04-22 10:30", "low": 9.45, "high": 10.2, "close": 10.0, "volume": 110},
                    {"datetime": "2026-04-22 11:00", "low": 9.7, "high": 10.3, "close": 10.2, "volume": 120},
                ],
                "build_stop_execution_plan": lambda entry, structure_stop=None, structure_label="结构止损": {
                    "entry": entry,
                    "effective_stop": structure_stop,
                    "summary": f"{structure_label}:{structure_stop}",
                },
            },
        )

        self.assertEqual(plan["confirm_price_60m"], 10.8)
        self.assertEqual(plan["confirm_basis_60m"], "entry_or_recent_high")
        self.assertEqual(plan["confirm_inputs_60m"]["entry_price"], 10.0)
        self.assertEqual(plan["confirm_inputs_60m"]["recent_high"], 10.8)
        self.assertEqual(plan["confirm_support_60m"], 9.7)
        self.assertEqual(plan["structure_stop_30m"], 9.45)
        self.assertIn("首个60分钟放量站上10.80", plan["confirm_rule_60m"])
        self.assertEqual(plan["volume_ratio_60m"], 1.64)
        self.assertEqual(plan["stop_plan"]["effective_stop"], 9.45)

    def test_build_intraday_execution_plan_marks_structure_repair_band_as_calibrated(self):
        plan = build_intraday_execution_plan(
            "000889",
            "2026-04-22",
            4.35,
            signal_type="breakout",
            fallback_stop=4.13,
            entry_cycle_profile={
                "recommended_stop_mode": "structure_repair_band",
                "fixed_5pct_stop_result": "would_false_kill",
                "interpretation": "中嘉博创说明固定-5%会误杀",
            },
            helpers={
                "fetch_intraday_bars": lambda code, target_date, period="30", lookback_bars=12: [
                    {"datetime": "2026-04-22 10:00", "open": 4.2, "high": 4.35, "low": 4.1, "close": 4.25, "volume": 100},
                    {"datetime": "2026-04-22 11:00", "open": 4.25, "high": 4.5, "low": 4.18, "close": 4.46, "volume": 130},
                    {"datetime": "2026-04-22 14:00", "open": 4.46, "high": 4.62, "low": 4.38, "close": 4.58, "volume": 180},
                ],
                "build_stop_execution_plan": lambda entry, structure_stop=None, structure_label="结构止损": {
                    "entry_price": entry,
                    "structure_stop": structure_stop,
                    "hard_stop": 4.13,
                    "effective_stop": structure_stop,
                    "summary": f"{structure_label}:{structure_stop}",
                },
            },
        )

        self.assertEqual(plan["confirm_basis_60m"], "entry_cycle_calibrated")
        self.assertEqual(plan["entry_cycle_stop_policy"]["recommended_stop_mode"], "structure_repair_band")
        self.assertEqual(plan["entry_cycle_stop_policy"]["hard_stop_role"], "风险底线，不是观察淘汰线")
        self.assertEqual(plan["entry_cycle_stop_policy"]["primary_exit_mode"], "结构修复带")
        self.assertNotIn("-5%", plan["entry_cycle_stop_policy"]["primary_exit_mode"])

    def test_build_intraday_execution_plan_marks_reclaim_failure_as_primary_exit(self):
        plan = build_intraday_execution_plan(
            "000791",
            "2026-04-22",
            8.00,
            signal_type="breakout",
            fallback_stop=7.60,
            entry_cycle_profile={
                "recommended_stop_mode": "reclaim_failure_exit",
                "interpretation": "甘肃能源没有站稳8.34-8.42",
            },
            helpers={
                "fetch_intraday_bars": lambda code, target_date, period="30", lookback_bars=12: [
                    {"datetime": "2026-04-22 10:00", "open": 8.06, "high": 8.34, "low": 7.84, "close": 8.15, "volume": 100},
                    {"datetime": "2026-04-22 11:00", "open": 8.15, "high": 8.20, "low": 7.96, "close": 8.02, "volume": 120},
                    {"datetime": "2026-04-22 14:00", "open": 8.02, "high": 8.13, "low": 7.88, "close": 8.03, "volume": 110},
                ],
                "build_stop_execution_plan": lambda entry, structure_stop=None, structure_label="结构止损": {
                    "entry_price": entry,
                    "structure_stop": structure_stop,
                    "hard_stop": 7.60,
                    "effective_stop": structure_stop,
                    "summary": f"{structure_label}:{structure_stop}",
                },
            },
        )

        self.assertEqual(plan["entry_cycle_stop_policy"]["recommended_stop_mode"], "reclaim_failure_exit")
        self.assertEqual(plan["entry_cycle_stop_policy"]["primary_exit_mode"], "关键区失败降级")
        self.assertIn("不是继续等待-5%", plan["entry_cycle_stop_policy"]["display_rule"])

    def test_build_intraday_execution_plan_marks_a_kill_as_primary_exit(self):
        plan = build_intraday_execution_plan(
            "600488",
            "2026-04-22",
            6.97,
            signal_type="breakout",
            fallback_stop=6.62,
            entry_cycle_profile={
                "recommended_stop_mode": "a_kill_exit",
                "interpretation": "津药药业已经出现结构失真",
            },
            helpers={
                "fetch_intraday_bars": lambda code, target_date, period="30", lookback_bars=12: [
                    {"datetime": "2026-04-22 10:00", "open": 6.7, "high": 6.99, "low": 6.37, "close": 6.42, "volume": 100},
                    {"datetime": "2026-04-22 11:00", "open": 6.4, "high": 6.48, "low": 5.96, "close": 6.06, "volume": 130},
                    {"datetime": "2026-04-22 14:00", "open": 6.1, "high": 6.2, "low": 5.91, "close": 5.96, "volume": 120},
                ],
                "build_stop_execution_plan": lambda entry, structure_stop=None, structure_label="结构止损": {
                    "entry_price": entry,
                    "structure_stop": structure_stop,
                    "hard_stop": 6.62,
                    "effective_stop": structure_stop,
                    "summary": f"{structure_label}:{structure_stop}",
                },
            },
        )

        self.assertEqual(plan["entry_cycle_stop_policy"]["recommended_stop_mode"], "a_kill_exit")
        self.assertEqual(plan["entry_cycle_stop_policy"]["primary_exit_mode"], "A杀出清")
        self.assertNotIn("趋势持有", plan["entry_cycle_stop_policy"]["report_action_text"])

    def test_build_intraday_execution_plan_marks_time_stop_as_downgrade(self):
        plan = build_intraday_execution_plan(
            "603026",
            "2026-04-22",
            98.52,
            signal_type="breakout",
            fallback_stop=93.59,
            entry_cycle_profile={
                "recommended_stop_mode": "time_stop_or_downgrade",
                "interpretation": "石大胜华不是趋势持有样本",
            },
            helpers={
                "fetch_intraday_bars": lambda code, target_date, period="30", lookback_bars=12: [
                    {"datetime": "2026-04-22 10:00", "open": 98.0, "high": 100.0, "low": 95.8, "close": 96.11, "volume": 100},
                    {"datetime": "2026-04-22 11:00", "open": 97.5, "high": 100.38, "low": 94.06, "close": 99.14, "volume": 140},
                    {"datetime": "2026-04-22 14:00", "open": 99.15, "high": 105.83, "low": 99.06, "close": 104.84, "volume": 150},
                ],
                "build_stop_execution_plan": lambda entry, structure_stop=None, structure_label="结构止损": {
                    "entry_price": entry,
                    "structure_stop": structure_stop,
                    "hard_stop": 93.59,
                    "effective_stop": structure_stop,
                    "summary": f"{structure_label}:{structure_stop}",
                },
            },
        )

        self.assertEqual(plan["entry_cycle_stop_policy"]["recommended_stop_mode"], "time_stop_or_downgrade")
        self.assertEqual(plan["entry_cycle_stop_policy"]["primary_exit_mode"], "时间止损/降级")
        self.assertNotIn("趋势持有", plan["entry_cycle_stop_policy"]["report_action_text"])

    def test_build_intraday_execution_plan_returns_empty_for_invalid_entry(self):
        self.assertEqual(build_intraday_execution_plan("000001", "2026-04-22", 0), {})

    def test_fetch_intraday_bars_uses_tushare_before_akshare(self):
        from execution import intraday_execution_runtime as runtime

        runtime._intraday_bar_cache = {}
        akshare_calls = []
        fake_akshare = types.SimpleNamespace(
            stock_zh_a_hist_min_em=lambda symbol, period="30", adjust="": akshare_calls.append((symbol, period, adjust)) or (_ for _ in ()).throw(
                AssertionError("AkShare should only run after Tushare stock_mins fails")
            )
        )
        tushare_bars = [
            {
                "datetime": "2026-04-22 10:00:00",
                "date": "2026-04-22",
                "open": 9.8,
                "high": 10.1,
                "low": 9.7,
                "close": 10.0,
                "volume": 100.0,
                "amount": 1000.0,
            },
            {
                "datetime": "2026-04-22 10:30:00",
                "date": "2026-04-22",
                "open": 10.0,
                "high": 10.3,
                "low": 9.9,
                "close": 10.2,
                "volume": 120.0,
                "amount": 1200.0,
            },
        ]

        with patch.dict(sys.modules, {"akshare": fake_akshare}), patch.object(
            runtime,
            "fetch_tushare_minute_bars",
            return_value=tushare_bars,
            create=True,
        ) as tushare_mock:
            result = runtime.fetch_intraday_bars("000001", "2026-04-22", period="30", lookback_bars=2)

        tushare_mock.assert_called_once_with("000001", period="30", target_date="2026-04-22", is_index=False)
        self.assertEqual(akshare_calls, [])
        self.assertEqual([bar["datetime"] for bar in result], ["2026-04-22 10:00:00", "2026-04-22 10:30:00"])

    def test_fetch_intraday_bars_filters_future_rows_and_caches(self):
        from execution import intraday_execution_runtime as runtime

        runtime._intraday_bar_cache = {}
        fake_akshare = types.SimpleNamespace(
            stock_zh_a_hist_min_em=lambda symbol, period="30", adjust="": types.SimpleNamespace(
                to_dict=lambda orient: [
                    {"时间": "2026-04-22 10:00", "开盘": 9.8, "最高": 10.1, "最低": 9.7, "收盘": 10.0, "成交量": 100, "成交额": 1000},
                    {"时间": "2026-04-22 10:30", "开盘": 10.0, "最高": 10.3, "最低": 9.9, "收盘": 10.2, "成交量": 120, "成交额": 1200},
                    {"时间": "2026-04-23 10:00", "开盘": 10.3, "最高": 10.6, "最低": 10.2, "收盘": 10.5, "成交量": 140, "成交额": 1400},
                ]
            )
        )

        with patch.dict(sys.modules, {"akshare": fake_akshare}), patch.object(runtime, "fetch_tushare_minute_bars", return_value=[], create=True):
            first = runtime.fetch_intraday_bars("000001", "2026-04-22", period="30", lookback_bars=2)
            second = runtime.fetch_intraday_bars("000001", "2026-04-22", period="30", lookback_bars=2)

        self.assertEqual([bar["datetime"] for bar in first], ["2026-04-22 10:00", "2026-04-22 10:30"])
        self.assertEqual(second, first)

    def test_build_waiting_stock_plan_enriches_minute_and_stop_plan(self):
        from execution.intraday_execution_runtime import build_waiting_stock_plan

        result = build_waiting_stock_plan(
            {"code": "000001", "close": 10.0},
            "2026-04-22",
            signal_type="breakout",
            recent_bars=[{"date": "2026-04-22", "close": 10.0}],
            helpers={
                "build_intraday_execution_plan": lambda code, target_date, entry_price, signal_type="", fallback_stop=None: {
                    "stop_plan": {"effective_stop": 9.6}
                },
                "build_stop_execution_plan": lambda entry_price: {"effective_stop": 9.5},
                "enrich_stop_plan_with_reference_anchors": lambda stop_plan, code, target_date, recent_bars=None: {
                    **stop_plan,
                    "daily_anchor_stop": 9.4,
                },
                "MAX_SINGLE_TRADE_LOSS_PCT": 0.08,
            },
        )

        self.assertEqual(result["entry_price"], 10.0)
        self.assertEqual(result["stop_loss"], 9.6)
        self.assertEqual(result["stop_plan"]["daily_anchor_stop"], 9.4)
        self.assertEqual(result["reason"], "等待信号")

    def test_build_waiting_stock_plan_uses_default_entry_cycle_profile_by_code(self):
        from execution.intraday_execution_runtime import build_waiting_stock_plan

        result = build_waiting_stock_plan(
            {"code": "000889", "close": 4.35},
            "2026-04-22",
            signal_type="breakout",
            helpers={
                "fetch_intraday_bars": lambda code, target_date, period="30", lookback_bars=12: [
                    {"datetime": "2026-04-22 10:00", "open": 4.2, "high": 4.35, "low": 4.1, "close": 4.25, "volume": 100},
                    {"datetime": "2026-04-22 11:00", "open": 4.25, "high": 4.5, "low": 4.18, "close": 4.46, "volume": 130},
                    {"datetime": "2026-04-22 14:00", "open": 4.46, "high": 4.62, "low": 4.38, "close": 4.58, "volume": 180},
                ],
                "build_stop_execution_plan": lambda entry, structure_stop=None, structure_label="结构止损": {
                    "entry_price": entry,
                    "structure_stop": structure_stop,
                    "hard_stop": 4.13,
                    "effective_stop": structure_stop,
                    "summary": f"{structure_label}:{structure_stop}",
                },
                "enrich_stop_plan_with_reference_anchors": lambda stop_plan, code, target_date, recent_bars=None: stop_plan,
            },
        )

        self.assertEqual(result["minute_plan"]["entry_cycle_stop_policy"]["recommended_stop_mode"], "structure_repair_band")
        self.assertEqual(result["minute_plan"]["confirm_basis_60m"], "entry_cycle_calibrated")


if __name__ == "__main__":
    unittest.main()
