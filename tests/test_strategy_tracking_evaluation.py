import subprocess
import sys
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


class StrategyTrackingEvaluationTest(unittest.TestCase):
    def _load_evaluation_module(self):
        try:
            return __import__("report.strategy_tracking_evaluation", fromlist=["strategy_tracking_evaluation"])
        except ModuleNotFoundError as error:
            self.fail(f"report.strategy_tracking_evaluation should exist: {error}")

    def test_legacy_strategy_evaluation_wrappers_delegate_to_runtime(self):
        result = _run_legacy_entry_probe(
            """
import daily_report_entry_demo
from unittest.mock import patch

evaluate_payload = {"status": "closed"}
path_payload = {"observed_return": 0.08}
display_payload = {"alpha_return_best": 0.03}

with patch.object(daily_report_entry_demo, "run_evaluate_single_strategy_record", return_value=evaluate_payload) as evaluate_mock, \
     patch.object(daily_report_entry_demo, "run_collect_record_market_path", return_value=path_payload) as path_mock, \
     patch.object(daily_report_entry_demo, "run_get_recent_record_display_metrics", return_value=display_payload) as display_mock:
    evaluate_result = daily_report_entry_demo._evaluate_single_strategy_record(
        {"report_date": "2026-04-23"},
        "2026-04-24",
    )
    path_result = daily_report_entry_demo._collect_record_market_path(
        {"report_date": "2026-04-23"},
        "2026-04-24",
    )
    display_result = daily_report_entry_demo._get_recent_record_display_metrics(
        {"action_type": "watch_only"}
    )

assert evaluate_mock.call_args[0][1] == "2026-04-24"
assert "helpers" in evaluate_mock.call_args.kwargs
assert path_mock.call_args[0][1] == "2026-04-24"
assert "helpers" in path_mock.call_args.kwargs
assert display_mock.call_args[0][0] == {"action_type": "watch_only"}
assert "helpers" in display_mock.call_args.kwargs
assert evaluate_result == evaluate_payload
assert path_result == path_payload
assert display_result == display_payload
"""
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_strategy_tracking_evaluation_runtime_exposes_helper_bindings(self):
        evaluation = self._load_evaluation_module()
        exec(
            """
def _evaluation_probe(record, as_of_date):
    return runtime_test_helper(record, as_of_date)
""",
            evaluation.__dict__,
        )

        with patch(
            "report.strategy_tracking_evaluation._evaluate_single_strategy_record_legacy_body",
            evaluation._evaluation_probe,
        ):
            result = evaluation.evaluate_single_strategy_record(
                {"report_date": "2026-04-23"},
                "2026-04-24",
                helpers={"runtime_test_helper": lambda record, as_of_date: (record["report_date"], as_of_date)},
            )

        self.assertEqual(result, ("2026-04-23", "2026-04-24"))

    def test_get_nth_bar_after_returns_requested_bar(self):
        evaluation = self._load_evaluation_module()

        result = evaluation.get_nth_bar_after(
            [
                {"date": "2026-04-23"},
                {"date": "2026-04-24"},
                {"date": "2026-04-25"},
            ],
            "2026-04-23",
            nth=2,
            helpers={"_parse_kline_date": lambda value: __import__("datetime").datetime.strptime(value, "%Y-%m-%d")},
        )

        self.assertEqual(result["date"], "2026-04-25")

    def test_apply_yizi_chain_rules_marks_continuation_only_for_valid_same_stock_chain(self):
        evaluation = self._load_evaluation_module()
        records = [
            {
                "report_date": "2026-04-22",
                "action_type": "execute",
                "stock_code": "000001",
                "simulation": {"triggered": True, "status": "closed", "status_note": ""},
                "report_day_is_one_word": False,
            },
            {
                "report_date": "2026-04-23",
                "action_type": "execute",
                "stock_code": "000001",
                "simulation": {"triggered": True, "status": "closed", "status_note": ""},
                "report_day_is_one_word": True,
            },
        ]

        evaluation.apply_yizi_chain_rules(
            records,
            helpers={
                "_normalize_kline_date_str": lambda value: value,
                "normalize_stock_code": lambda value: value,
                "_is_next_trading_day": lambda prev_date, next_date: True,
                "_get_strategy_status_label": lambda status, note="": status,
            },
        )

        self.assertEqual(records[1]["simulation"]["status"], "continuation_only")
        self.assertTrue(records[1]["chain_entry_valid"])

    def test_get_recent_record_display_metrics_recomputes_watch_only_alpha_with_report_change(self):
        evaluation = self._load_evaluation_module()

        result = evaluation.get_recent_record_display_metrics(
            {
                "action_type": "watch_only",
                "benchmark_report_change_pct": 2.0,
                "simulation": {
                    "strategy_return_worst": 0.05,
                    "strategy_return_best": 0.07,
                    "benchmark_return": 0.00,
                },
            },
            helpers={"_safe_float": lambda value: float(value or 0)},
        )

        self.assertAlmostEqual(result["benchmark_return"], 0.02)
        self.assertAlmostEqual(result["alpha_return_worst"], 0.03)
        self.assertAlmostEqual(result["alpha_return_best"], 0.05)


if __name__ == "__main__":
    unittest.main()
