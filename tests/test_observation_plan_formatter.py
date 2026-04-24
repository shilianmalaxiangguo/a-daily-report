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


class ObservationPlanFormatterTest(unittest.TestCase):
    def _load_module(self):
        try:
            return __import__("report.observation_plan_formatter", fromlist=["observation_plan_formatter"])
        except ModuleNotFoundError as error:
            self.fail(f"report.observation_plan_formatter should exist: {error}")

    def test_legacy_observation_plan_wrappers_delegate_to_runtime(self):
        result = _run_legacy_entry_probe(
            """
import daily_report_entry_demo
from unittest.mock import patch

with patch.object(daily_report_entry_demo, "run_build_abnormal_follow_rule", return_value="只看确认") as follow_mock, \
     patch.object(daily_report_entry_demo, "run_refine_abnormal_follow_display", return_value=(10.5, "只看回踩")) as refine_mock, \
     patch.object(daily_report_entry_demo, "run_format_abnormal_observation_columns", return_value=("10.10", "10.30")) as abnormal_mock, \
     patch.object(daily_report_entry_demo, "run_format_frozen_plan_columns", return_value=("10.00-10.50", "10.60", "10.30", "10.10", "9.80")) as frozen_mock:
    follow_result = daily_report_entry_demo._build_abnormal_follow_rule("恐怖阴线异动", "跌不下去", 10.1, {"body_mid": 10.4})
    refine_result = daily_report_entry_demo._refine_abnormal_follow_display(10.1, "观察规则", {"confirm_support_60m": 10.5})
    abnormal_result = daily_report_entry_demo._format_abnormal_observation_columns({"anchor_price": 10.1, "display_anchor_price": 10.3})
    frozen_result = daily_report_entry_demo._format_frozen_plan_columns({"entry_range_low": 10.0, "entry_range_high": 10.5})

assert follow_mock.call_args[0][:4] == ("恐怖阴线异动", "跌不下去", 10.1, {"body_mid": 10.4})
assert "helpers" in follow_mock.call_args.kwargs
assert refine_mock.call_args[0][:3] == (10.1, "观察规则", {"confirm_support_60m": 10.5})
assert "helpers" in refine_mock.call_args.kwargs
assert abnormal_mock.call_args[0][0] == {"anchor_price": 10.1, "display_anchor_price": 10.3}
assert "helpers" in abnormal_mock.call_args.kwargs
assert frozen_mock.call_args[0][0] == {"entry_range_low": 10.0, "entry_range_high": 10.5}
assert "helpers" in frozen_mock.call_args.kwargs
assert follow_result == "只看确认"
assert refine_result == (10.5, "只看回踩")
assert abnormal_result == ("10.10", "10.30")
assert frozen_result == ("10.00-10.50", "10.60", "10.30", "10.10", "9.80")
"""
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_observation_plan_formatter_runtime_exposes_helper_bindings(self):
        module = self._load_module()
        exec(
            """
def _follow_rule_probe(abnormal_type, follow_state, anchor_price, abnormal_info):
    return runtime_test_helper(abnormal_type, follow_state, abnormal_info.get("body_mid"))
""",
            module.__dict__,
        )

        with patch(
            "report.observation_plan_formatter._build_abnormal_follow_rule_legacy_body",
            module._follow_rule_probe,
        ):
            result = module.build_abnormal_follow_rule(
                "长上影异动",
                "跌不下去",
                10.2,
                {"body_mid": 10.6},
                helpers={"runtime_test_helper": lambda abnormal_type, follow_state, body_mid: (abnormal_type, follow_state, body_mid)},
            )

        self.assertEqual(result, ("长上影异动", "跌不下去", 10.6))

    def test_build_abnormal_follow_rule_handles_special_cases(self):
        module = self._load_module()

        result = module.build_abnormal_follow_rule(
            "恐怖阴线异动",
            "跌不下去",
            10.2,
            {"body_mid": 10.55},
            helpers={"_safe_float": lambda value, default=0: float(value or default)},
        )

        self.assertEqual(result, "只看首个60分钟能否收回阴线实体一半（约10.55）")

    def test_refine_and_format_frozen_plan_columns_use_dynamic_guards(self):
        module = self._load_module()
        helpers = {"_round_or_none": lambda value, digits=4: None if value is None else round(float(value), digits)}

        refined_anchor, refined_rule = module.refine_abnormal_follow_display(
            10.1,
            "观察规则",
            {"confirm_support_60m": 10.5, "confirm_rule_60m": "站回确认位"},
            helpers=helpers,
        )
        frozen_columns = module.format_frozen_plan_columns(
            {
                "entry_range_low": 10.0,
                "entry_range_high": 10.5,
                "confirm_price_60m": 10.6,
                "anchor_price": 10.1,
                "display_anchor_price": refined_anchor,
                "execution_stop": 9.8,
            },
            helpers=helpers,
        )

        self.assertEqual((refined_anchor, refined_rule), (10.5, "只看站回确认位"))
        self.assertEqual(frozen_columns, ("10.00-10.50", "10.60", "10.50", "10.10", "9.80"))


if __name__ == "__main__":
    unittest.main()
