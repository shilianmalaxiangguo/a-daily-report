import subprocess
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


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


class StrategyTrackingEvTest(unittest.TestCase):
    def _load_ev_module(self):
        try:
            return __import__("report.strategy_tracking_ev", fromlist=["strategy_tracking_ev"])
        except ModuleNotFoundError as error:
            self.fail(f"report.strategy_tracking_ev should exist: {error}")

    def test_legacy_strategy_ev_wrappers_delegate_to_runtime(self):
        result = _run_legacy_entry_probe(
            """
import daily_report_entry_demo
from unittest.mock import patch

calibration_payload = {"global": {"sample_size": 3}}
posterior_payload = {"win_rate": 0.6}
scored_payload = {"ev": 1.23}

with patch.object(daily_report_entry_demo, "run_build_strategy_ev_calibration", return_value=calibration_payload) as calibration_mock, \
     patch.object(daily_report_entry_demo, "run_estimate_signal_type_ev", return_value=posterior_payload) as estimate_mock, \
     patch.object(daily_report_entry_demo, "run_score_execution_candidate", return_value=scored_payload) as score_mock:
    calibration_result = daily_report_entry_demo.build_strategy_ev_calibration("2026-04-24", ledger_mode="replay")
    estimate_result = daily_report_entry_demo.estimate_signal_type_ev("base", 0.03, {"global": {}})
    score_result = daily_report_entry_demo.score_execution_candidate({"name": "样本A"}, {"global": {}})

assert calibration_mock.call_args[0][0] == "2026-04-24"
assert calibration_mock.call_args.kwargs["ledger_mode"] == "replay"
assert "helpers" in calibration_mock.call_args.kwargs
assert estimate_mock.call_args[0][0] == "base"
assert estimate_mock.call_args[0][1] == 0.03
assert "helpers" in estimate_mock.call_args.kwargs
assert score_mock.call_args[0][0] == {"name": "样本A"}
assert score_mock.call_args[0][1] == {"global": {}}
assert "helpers" in score_mock.call_args.kwargs
assert calibration_result == calibration_payload
assert estimate_result == posterior_payload
assert score_result == scored_payload
"""
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_strategy_ev_runtime_exposes_helper_bindings(self):
        ev = self._load_ev_module()
        exec(
            """
def _ev_probe(signal_type, loss_space_pct, calibration):
    return runtime_test_helper(signal_type, loss_space_pct, calibration.get("global", {}).get("sample_size"))
""",
            ev.__dict__,
        )

        with patch(
            "report.strategy_tracking_ev._estimate_signal_type_ev_legacy_body",
            ev._ev_probe,
        ):
            result = ev.estimate_signal_type_ev(
                "base",
                0.03,
                {"global": {"sample_size": 4}},
                helpers={"runtime_test_helper": lambda signal_type, loss_space_pct, sample_size: (signal_type, loss_space_pct, sample_size)},
            )

        self.assertEqual(result, ("base", 0.03, 4))

    def test_build_strategy_ev_calibration_filters_future_records_and_groups_by_signal(self):
        ev = self._load_ev_module()

        result = ev.build_strategy_ev_calibration(
            "2026-04-24",
            ledger_mode="replay",
            helpers={
                "load_strategy_performance_ledger": lambda mode="frozen": {
                    "records": [
                        {"report_date": "2026-04-22", "signal_type": "base"},
                        {"report_date": "2026-04-23", "signal_type": "low_suction"},
                        {"report_date": "2026-04-24", "signal_type": "base"},
                    ]
                },
                "_normalize_kline_date_str": lambda value: value,
                "_backfill_strategy_record_market_context": lambda record: {**record, "backfilled": True},
                "_build_trade_return_stats": lambda records: {"sample_size": len(records), "first_signal": (records[0].get("signal_type") if records else "")},
                "EV_SIGNAL_TYPE_PRIORS": {
                    "base": {"label": "基础信号"},
                    "low_suction": {"label": "低吸信号"},
                },
            },
        )

        self.assertEqual(result["global"]["sample_size"], 2)
        self.assertEqual(result["by_signal"]["base"]["sample_size"], 1)
        self.assertEqual(result["by_signal"]["low_suction"]["sample_size"], 1)

    def test_estimate_signal_type_ev_blends_priors_and_samples(self):
        ev = self._load_ev_module()

        result = ev.estimate_signal_type_ev(
            "base",
            0.03,
            {
                "global": {"sample_size": 5, "win_rate": 0.50, "avg_win_pct": 0.08, "avg_loss_pct": 0.03},
                "by_signal": {"base": {"sample_size": 4, "win_rate": 0.65, "avg_win_pct": 0.10, "avg_loss_pct": 0.025}},
            },
            helpers={
                "EV_SIGNAL_TYPE_PRIORS": {"base": {"label": "基础信号", "prior_weight": 8.0, "win_rate": 0.55, "avg_win_pct": 0.09, "avg_loss_pct": 0.03}},
                "_safe_float": lambda value, default=0: float(value if value is not None else default),
                "_clamp": lambda value, lower, upper: max(lower, min(value, upper)),
            },
        )

        self.assertEqual(result["signal_label"], "基础信号")
        self.assertGreaterEqual(result["win_rate"], 0.20)
        self.assertLessEqual(result["win_rate"], 0.80)
        self.assertGreater(result["projected_win_pct"], result["projected_loss_pct"])
        self.assertEqual(result["signal_sample_size"], 4)
        self.assertEqual(result["global_sample_size"], 5)

    def test_score_execution_candidate_uses_posterior_and_handles_missing_entry(self):
        ev = self._load_ev_module()

        signal = types.SimpleNamespace(entry_price=10.0, stop_loss=9.5, position_pct=30.0, signal_type="base")
        scored = ev.score_execution_candidate(
            {"signal": signal},
            {"global": {}},
            helpers={
                "_safe_float": lambda value, default=0: float(value if value is not None else default),
                "estimate_signal_type_ev": lambda signal_type, loss_space_pct, calibration: {
                    "win_rate": 0.6,
                    "reward_multiple": 2.0,
                    "projected_win_pct": 0.12,
                    "projected_loss_pct": 0.05,
                    "source_label": "posterior",
                    "signal_sample_size": 3,
                    "global_sample_size": 7,
                    "confidence": 0.4,
                },
                "MAX_SINGLE_TRADE_LOSS_PCT": 0.05,
            },
        )

        self.assertAlmostEqual(scored["loss_space"], 0.5)
        self.assertAlmostEqual(scored["profit_space"], 1.2)
        self.assertAlmostEqual(scored["ev_pct"], 0.052)
        self.assertEqual(scored["ev_model_source"], "posterior")
        self.assertEqual(scored["signal_type"], "base")

        empty = ev.score_execution_candidate(
            {"entry_price": 0.0},
            {"global": {}},
            helpers={"_safe_float": lambda value, default=0: float(value if value is not None else default), "MAX_SINGLE_TRADE_LOSS_PCT": 0.05},
        )
        self.assertEqual(empty["ev"], 0.0)
        self.assertEqual(empty["ev_model_source"], "无有效从什么价开始算")

    def test_score_execution_candidate_uses_runtime_default_dependencies_when_helpers_omitted(self):
        ev = self._load_ev_module()

        with patch.object(
            ev,
            "_safe_float",
            side_effect=lambda value, default=0: float(value if value is not None else default),
        ) as safe_float_mock, patch.object(
            ev,
            "estimate_signal_type_ev",
            return_value={
                "win_rate": 0.6,
                "reward_multiple": 2.0,
                "projected_win_pct": 0.12,
                "projected_loss_pct": 0.05,
                "source_label": "posterior",
                "signal_sample_size": 3,
                "global_sample_size": 7,
                "confidence": 0.4,
            },
        ) as posterior_mock:
            scored = ev.score_execution_candidate(
                {"entry_price": 10.0, "stop_loss": 9.5, "position_pct": 30.0, "signal_type": "base"},
                {"global": {}},
            )

        self.assertAlmostEqual(scored["loss_space"], 0.5)
        self.assertAlmostEqual(scored["profit_space"], 1.2)
        self.assertEqual(scored["ev_model_source"], "posterior")
        self.assertEqual(scored["signal_type"], "base")
        self.assertGreaterEqual(safe_float_mock.call_count, 3)
        posterior_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
