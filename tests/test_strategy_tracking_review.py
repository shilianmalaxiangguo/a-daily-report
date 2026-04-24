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


class StrategyTrackingReviewTest(unittest.TestCase):
    def _load_review_module(self):
        try:
            return __import__("report.strategy_tracking_review", fromlist=["strategy_tracking_review"])
        except ModuleNotFoundError as error:
            self.fail(f"report.strategy_tracking_review should exist: {error}")

    def test_legacy_strategy_review_wrappers_delegate_to_runtime(self):
        result = _run_legacy_entry_probe(
            """
import daily_report_entry_demo
from unittest.mock import patch

with patch.object(daily_report_entry_demo, "run_classify_strategy_record_attribution", return_value={"label": "环境过滤过严"}) as classify_mock, \
     patch.object(daily_report_entry_demo, "run_summarize_strategy_attribution", return_value={"items": []}) as attribution_mock, \
     patch.object(daily_report_entry_demo, "run_summarize_gem_breathing_week_review", return_value={"sample_count": 1}) as gem_review_mock, \
     patch.object(daily_report_entry_demo, "run_build_system_graduation_dashboard", return_value={"stage": "研究原型"}) as dashboard_mock:
    classify_result = daily_report_entry_demo._classify_strategy_record_attribution(
        {"report_date": "2026-04-23"},
        "2026-04-24",
    )
    attribution_result = daily_report_entry_demo._summarize_strategy_attribution(
        [{"report_date": "2026-04-23"}],
        "2026-04-21",
        "2026-04-24",
    )
    gem_review_result = daily_report_entry_demo._summarize_gem_breathing_week_review(
        [{"report_date": "2026-04-23"}],
        "2026-04-21",
        "2026-04-24",
    )
    dashboard_result = daily_report_entry_demo._build_system_graduation_dashboard(
        [{"report_date": "2026-04-23"}],
        [{"result_label": "进攻有效"}],
        source_label="当前账本",
    )

assert classify_mock.call_args[0][0] == {"report_date": "2026-04-23"}
assert classify_mock.call_args[0][1] == "2026-04-24"
assert "helpers" in classify_mock.call_args.kwargs
assert attribution_mock.call_args[0][1] == "2026-04-21"
assert attribution_mock.call_args[0][2] == "2026-04-24"
assert "helpers" in attribution_mock.call_args.kwargs
assert gem_review_mock.call_args[0][1] == "2026-04-21"
assert gem_review_mock.call_args[0][2] == "2026-04-24"
assert "helpers" in gem_review_mock.call_args.kwargs
assert dashboard_mock.call_args[0][1] == [{"result_label": "进攻有效"}]
assert dashboard_mock.call_args.kwargs["source_label"] == "当前账本"
assert "helpers" in dashboard_mock.call_args.kwargs
assert classify_result == {"label": "环境过滤过严"}
assert attribution_result == {"items": []}
assert gem_review_result == {"sample_count": 1}
assert dashboard_result == {"stage": "研究原型"}
"""
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_strategy_review_runtime_exposes_helper_bindings(self):
        review = self._load_review_module()
        exec(
            """
def _strategy_review_probe(records, start_date, end_date):
    return runtime_test_helper(records, start_date, end_date)
""",
            review.__dict__,
        )

        with patch(
            "report.strategy_tracking_review._summarize_strategy_attribution_legacy_body",
            review._strategy_review_probe,
        ):
            result = review.summarize_strategy_attribution(
                [{"report_date": "2026-04-23"}],
                "2026-04-21",
                "2026-04-24",
                helpers={"runtime_test_helper": lambda records, start_date, end_date: (records[0]["report_date"], start_date, end_date)},
            )

        self.assertEqual(result, ("2026-04-23", "2026-04-21", "2026-04-24"))

    def test_classify_strategy_record_attribution_marks_env_too_strict_for_strong_watch_only_sample(self):
        review = self._load_review_module()

        result = review.classify_strategy_record_attribution(
            {
                "action_type": "watch_only",
                "simulation": {"benchmark_return": 0.02},
                "factor_snapshot": {"selection": {}},
            },
            "2026-04-24",
            helpers={
                "_collect_record_market_path": lambda record, as_of_date: {"observed_return": 0.06, "max_runup": 0.09, "max_drawdown": -0.03},
                "_safe_float": lambda value: float(value or 0),
                "_round_or_none": lambda value: value,
                "_build_weak_to_strong_context": lambda **kwargs: {"active": False},
            },
        )

        self.assertEqual(result["category"], "env_too_strict")
        self.assertEqual(result["label"], "环境过滤过严")

    def test_summarize_gem_breathing_week_review_counts_upgrade_lag_samples(self):
        review = self._load_review_module()

        with patch(
            "report.strategy_tracking_review._classify_gem_breathing_week_sample_legacy_body",
            side_effect=[
                {
                    "sample_line": "2026-04-22 样本A：升级偏慢",
                    "upgrade_lag": True,
                    "conditional_upgrade": False,
                    "voided": False,
                    "expired": False,
                    "active_observation": False,
                    "right_side_confirmation": True,
                    "rebreak_success": True,
                    "report_date": "2026-04-22",
                },
                {
                    "sample_line": "2026-04-23 样本B：已升级",
                    "upgrade_lag": False,
                    "conditional_upgrade": True,
                    "voided": False,
                    "expired": False,
                    "active_observation": False,
                    "right_side_confirmation": True,
                    "rebreak_success": False,
                    "report_date": "2026-04-23",
                },
            ],
        ):
            result = review.summarize_gem_breathing_week_review(
                [
                    {"report_date": "2026-04-22"},
                    {"report_date": "2026-04-23"},
                ],
                "2026-04-21",
                "2026-04-24",
                helpers={
                    "_normalize_kline_date_str": lambda value: value,
                    "_extract_gem_breathing_contract_snapshot": lambda record: {"sample": True},
                },
            )

        self.assertEqual(result["sample_count"], 2)
        self.assertEqual(result["upgrade_lag_count"], 1)
        self.assertEqual(result["conditional_upgrade_count"], 1)
        self.assertEqual(result["upgrade_lag_samples"], ["2026-04-22 样本A：升级偏慢"])

    def test_build_system_graduation_dashboard_marks_research_proto_when_history_gap_exists(self):
        review = self._load_review_module()

        result = review.build_system_graduation_dashboard(
            [
                {
                    "report_date": "2026-04-23",
                    "factor_snapshot": {},
                    "decision_stack": {},
                    "abnormal_setup_signal_label": "",
                    "attribution": {"category": "defense_correct"},
                    "action_type": "watch_only",
                    "simulation": {},
                }
            ],
            [],
            source_label="当前账本",
            current_plan={
                "factor_snapshot": {"selection": {}},
                "decision_stack": {},
                "defensive_exit_rule": "rule-a",
                "profit_exit_rule": "rule-b",
            },
            helpers={"_safe_float": lambda value: float(value or 0)},
        )

        self.assertEqual(result["stage"], "研究原型")
        self.assertTrue(result["legacy_history_gap"])
        self.assertTrue(result["current_engine_ready"])

    def test_build_system_graduation_dashboard_avoids_logic_wording_in_toy_stage_verdict(self):
        review = self._load_review_module()

        result = review.build_system_graduation_dashboard(
            [],
            [],
            source_label="当前账本",
            current_plan={},
            helpers={"_safe_float": lambda value: float(value or 0)},
        )

        self.assertEqual(result["stage"], "玩具")
        self.assertNotIn("逻辑", result["verdict"])
        self.assertIn("展示层结果", result["verdict"])


if __name__ == "__main__":
    unittest.main()
