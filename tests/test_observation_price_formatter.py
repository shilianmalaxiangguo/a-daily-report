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


class ObservationPriceFormatterTest(unittest.TestCase):
    def _load_module(self):
        try:
            return __import__("report.observation_price_formatter", fromlist=["observation_price_formatter"])
        except ModuleNotFoundError as error:
            self.fail(f"report.observation_price_formatter should exist: {error}")

    def test_legacy_observation_price_wrappers_delegate_to_runtime(self):
        result = _run_legacy_entry_probe(
            """
import daily_report_entry_demo
from unittest.mock import patch

payload_text = "关键位/带10.00-10.30（前低/失效）"
payload_note = "前低/失效靠近，视为同一关键带。"

with patch.object(daily_report_entry_demo, "run_build_observation_price_focus_text", return_value=payload_text) as focus_mock, \
     patch.object(daily_report_entry_demo, "run_build_observation_price_note_text", return_value=payload_note) as note_mock, \
     patch.object(daily_report_entry_demo, "run_should_surface_price_note", return_value=True) as surface_mock, \
     patch.object(daily_report_entry_demo, "run_append_price_focus_note", return_value=None) as append_mock, \
     patch.object(daily_report_entry_demo, "run_append_observation_price_focus_note", return_value=None) as append_obs_mock, \
     patch.object(daily_report_entry_demo, "run_compose_observation_focus_text", return_value="60分钟确认点10.50；关键位/带10.00-10.30") as compose_mock:
    focus_result = daily_report_entry_demo._build_observation_price_focus_text({"key_zone_display": "10.00-10.30"})
    note_result = daily_report_entry_demo._build_observation_price_note_text({"zone_badge": "前低/止损"})
    surface_result = daily_report_entry_demo._should_surface_price_note({"zone_badge": "前低"})
    lines = []
    daily_report_entry_demo._append_price_focus_note(lines, {"note_text": "看10.30"})
    daily_report_entry_demo._append_observation_price_focus_note(lines, {"zone_badge": "前低/止损"})
    compose_result = daily_report_entry_demo._compose_observation_focus_text("10.50", "关键位/带10.00-10.30")

assert focus_mock.call_args[0][0] == {"key_zone_display": "10.00-10.30"}
assert "helpers" in focus_mock.call_args.kwargs
assert note_mock.call_args[0][0] == {"zone_badge": "前低/止损"}
assert "helpers" in note_mock.call_args.kwargs
assert surface_mock.call_args[0][0] == {"zone_badge": "前低"}
assert "helpers" in surface_mock.call_args.kwargs
assert append_mock.call_args[0][0] == []
assert "helpers" in append_mock.call_args.kwargs
assert append_obs_mock.call_args[0][0] == []
assert "helpers" in append_obs_mock.call_args.kwargs
assert compose_mock.call_args[0][:2] == ("10.50", "关键位/带10.00-10.30")
assert "helpers" in compose_mock.call_args.kwargs
assert focus_result == payload_text
assert note_result == payload_note
assert surface_result is True
assert compose_result == "60分钟确认点10.50；关键位/带10.00-10.30"
"""
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_observation_price_formatter_runtime_exposes_helper_bindings(self):
        module = self._load_module()
        exec(
            """
def _compose_probe(confirm_text, price_focus_text=''):
    return runtime_test_helper(confirm_text, price_focus_text)
""",
            module.__dict__,
        )

        with patch(
            "report.observation_price_formatter._compose_observation_focus_text_legacy_body",
            module._compose_probe,
        ):
            result = module.compose_observation_focus_text(
                "10.50",
                "关键位/带10.00-10.30",
                helpers={"runtime_test_helper": lambda confirm_text, price_focus_text: (confirm_text, price_focus_text)},
            )

        self.assertEqual(result, ("10.50", "关键位/带10.00-10.30"))

    def test_build_observation_price_focus_text_and_note_text_render_expected_contract(self):
        module = self._load_module()
        helpers = {
            "_safe_float": lambda value, default=0: float(value or default),
            "_same_price_level": lambda a, b, tolerance=0.011: abs(float(a or 0) - float(b or 0)) <= tolerance,
        }

        price_focus = {
            "key_zone_display": "10.00-10.30",
            "zone_badge": "前低/止损",
            "execution_stop": 10.15,
            "hard_stop": 9.8,
            "key_zone_low": 10.0,
            "key_zone_high": 10.3,
            "confluence_reasons": ["前低", "缺口"],
        }
        focus_text = module.build_observation_price_focus_text(price_focus, helpers=helpers)
        note_text = module.build_observation_price_note_text(price_focus, helpers=helpers)

        self.assertEqual(focus_text, "关键位/带10.00-10.30（前低/失效）；最晚失效位9.80")
        self.assertEqual(note_text, "前低/失效靠近，视为同一关键带。该位置贴近前低、缺口附近。如果这个观察对象继续强，就不该失守这条关键位。")

    def test_build_trade_price_focus_builds_zone_and_stop_contract(self):
        module = self._load_module()
        builder = getattr(module, "build_trade_price_focus", None)
        self.assertIsNotNone(builder)

        price_focus = builder(
            {
                "confirm_price_60m": 10.8,
                "confirm_support_60m": 10.18,
                "structure_stop_30m": 10.1,
            },
            {
                "structure_stop": 10.12,
                "structure_label": "30分钟结构止损",
                "daily_anchor_stop": 10.15,
                "breakout_open_anchor": 10.16,
                "breakout_limit_anchor": 10.17,
                "effective_stop": 10.12,
                "hard_stop": 9.85,
            },
            helpers={
                "_safe_float": lambda value, default=0.0: default if value in (None, "") else float(value),
                "_round_or_none": lambda value, digits=2: round(float(value), digits),
                "_same_price_level": lambda a, b, tolerance=0.011: abs(float(a or 0) - float(b or 0)) <= tolerance,
                "_is_near_anchor_price": lambda value, anchor, pct=0.01, min_abs=0.03: abs(float(value or 0) - float(anchor or 0)) <= max(abs(float(anchor or 0)) * pct, min_abs),
            },
        )

        self.assertEqual(price_focus["key_zone_display"], "10.12~10.18")
        self.assertEqual(price_focus["execution_stop_display"], "10.12")
        self.assertEqual(price_focus["hard_stop_display"], "9.85")
        self.assertEqual(price_focus["zone_badge"], "前低/支撑/止损")
        self.assertEqual(price_focus["compact_text"], "关键位/带10.12~10.18（前低/支撑/止损）；执行止损10.12；最晚硬止损9.85")
        self.assertIn("关键大阳开盘价", price_focus["note_text"])
        self.assertIn("涨停价", price_focus["note_text"])

    def test_append_and_compose_helpers_surface_note_only_when_needed(self):
        module = self._load_module()
        lines = []

        module.append_price_focus_note(
            lines,
            {"zone_badge": "前低", "note_text": "看10.30"},
            helpers={"_should_surface_price_note": lambda price_focus: True},
        )
        module.append_observation_price_focus_note(
            lines,
            {"zone_badge": "前低"},
            helpers={
                "_should_surface_price_note": lambda price_focus: True,
                "_build_observation_price_note_text": lambda price_focus: "观察对象别破前低",
            },
        )
        composed = module.compose_observation_focus_text("10.50", "关键位/带10.00-10.30")

        self.assertEqual(lines, ["  价格怎么看：看10.30", "  价格怎么看：观察对象别破前低"])
        self.assertEqual(composed, "09:50-10:10观察价10.50；关键位/带10.00-10.30")


if __name__ == "__main__":
    unittest.main()
