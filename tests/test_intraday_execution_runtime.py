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
     patch.object(daily_report_entry_demo, "run_build_waiting_stock_plan", return_value=waiting_payload) as waiting_mock:
    bars = daily_report_entry_demo.fetch_intraday_bars("000001", "2026-04-22", period="60", lookback_bars=6)
    waiting = daily_report_entry_demo.build_waiting_stock_plan({"code": "000001", "close": 10.0}, "2026-04-22", signal_type="breakout")

assert bars_mock.call_args[0][:2] == ("000001", "2026-04-22")
assert bars_mock.call_args.kwargs["period"] == "60"
assert bars_mock.call_args.kwargs["lookback_bars"] == 6
assert "helpers" in bars_mock.call_args.kwargs
assert waiting_mock.call_args[0][:2] == ({"code": "000001", "close": 10.0}, "2026-04-22")
assert waiting_mock.call_args.kwargs["signal_type"] == "breakout"
assert "helpers" in waiting_mock.call_args.kwargs
assert bars == bars_payload
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
        self.assertEqual(plan["confirm_support_60m"], 9.7)
        self.assertEqual(plan["structure_stop_30m"], 9.45)
        self.assertIn("首个60分钟放量站上10.80", plan["confirm_rule_60m"])
        self.assertEqual(plan["volume_ratio_60m"], 1.64)
        self.assertEqual(plan["stop_plan"]["effective_stop"], 9.45)

    def test_build_intraday_execution_plan_returns_empty_for_invalid_entry(self):
        self.assertEqual(build_intraday_execution_plan("000001", "2026-04-22", 0), {})

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

        with patch.dict(sys.modules, {"akshare": fake_akshare}):
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


if __name__ == "__main__":
    unittest.main()
