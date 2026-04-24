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


class DailyPriceRuntimeTest(unittest.TestCase):
    def _load_module(self):
        try:
            return __import__("market_data.daily_price_runtime", fromlist=["daily_price_runtime"])
        except ModuleNotFoundError as error:
            self.fail(f"market_data.daily_price_runtime should exist: {error}")

    def test_legacy_daily_price_wrappers_delegate_to_runtime(self):
        result = _run_legacy_entry_probe(
            """
import daily_report_entry_demo
from unittest.mock import patch

bars_payload = [{"date": "2026-04-22", "close": 10.5}]

with patch.object(daily_report_entry_demo, "run_fetch_daily_price_bars", return_value=bars_payload) as bars_mock, \
     patch.object(daily_report_entry_demo, "run_get_first_bar_on_or_after", return_value={"date": "2026-04-22"}) as on_or_after_mock, \
     patch.object(daily_report_entry_demo, "run_count_trading_days_between", return_value=3) as count_mock, \
     patch.object(daily_report_entry_demo, "run_is_one_word_limit_bar", return_value=True) as one_word_mock, \
     patch.object(daily_report_entry_demo, "run_evaluate_live_tradability", return_value={"can_trade": True}) as tradability_mock:
    bars = daily_report_entry_demo.fetch_daily_price_bars("000001", "2026-04-20", "2026-04-22")
    bar = daily_report_entry_demo._get_first_bar_on_or_after([{"date": "2026-04-22"}], "2026-04-22")
    days = daily_report_entry_demo._count_trading_days_between("2026-04-20", "2026-04-22")
    one_word = daily_report_entry_demo._is_one_word_limit_bar(stock_code="000001")
    tradability = daily_report_entry_demo.evaluate_live_tradability({"code": "000001"}, target_date="2026-04-22")

assert bars_mock.call_args[0][:3] == ("000001", "2026-04-20", "2026-04-22")
assert "helpers" in bars_mock.call_args.kwargs
assert on_or_after_mock.call_args[0][1] == "2026-04-22"
assert "helpers" in on_or_after_mock.call_args.kwargs
assert count_mock.call_args[0][:2] == ("2026-04-20", "2026-04-22")
assert "helpers" in count_mock.call_args.kwargs
assert one_word_mock.call_args.kwargs["stock_code"] == "000001"
assert "helpers" in one_word_mock.call_args.kwargs
assert tradability_mock.call_args[0][0] == {"code": "000001"}
assert tradability_mock.call_args.kwargs["target_date"] == "2026-04-22"
assert "helpers" in tradability_mock.call_args.kwargs
assert bars == bars_payload
assert bar == {"date": "2026-04-22"}
assert days == 3
assert one_word is True
assert tradability == {"can_trade": True}
"""
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_legacy_recent_bar_and_anchor_wrappers_delegate_to_runtime(self):
        result = _run_legacy_entry_probe(
            """
import daily_report_entry_demo
from unittest.mock import patch

bars_payload = [{"date": "2026-04-22", "close": 10.5}]
anchor_payload = (9.8, "2026-04-21", "跌破直接卖")
breakout_payload = {"open_anchor": 10.1, "date": "2026-04-21"}
enriched_payload = {"effective_stop": 9.8, "daily_anchor_stop": 9.8}

with patch.object(daily_report_entry_demo, "run_fetch_recent_price_bars", return_value=bars_payload) as recent_mock, \
     patch.object(daily_report_entry_demo, "run_compute_stop_loss_mainline_anchor", return_value=anchor_payload) as stop_mock, \
     patch.object(daily_report_entry_demo, "run_resolve_big_yang_confluence_anchor", return_value=breakout_payload) as breakout_mock, \
     patch.object(daily_report_entry_demo, "run_enrich_stop_plan_with_reference_anchors", return_value=enriched_payload) as enrich_mock:
    recent = daily_report_entry_demo.fetch_recent_price_bars("000001", "2026-04-22", lookback_days=4)
    stop_line = daily_report_entry_demo.compute_stop_loss_mainline_anchor([{"date": "2026-04-22", "low": 9.8}], window=3)
    breakout = daily_report_entry_demo._resolve_big_yang_confluence_anchor([{"date": "2026-04-22", "open": 10.0, "close": 10.8, "high": 10.9, "low": 9.9}], target_date="2026-04-22", window=6)
    enriched = daily_report_entry_demo._enrich_stop_plan_with_reference_anchors({"effective_stop": 9.9}, "000001", "2026-04-22", recent_bars=bars_payload)

assert recent_mock.call_args[0][:2] == ("000001", "2026-04-22")
assert recent_mock.call_args.kwargs["lookback_days"] == 4
assert "helpers" in recent_mock.call_args.kwargs
assert stop_mock.call_args[0][0] == [{"date": "2026-04-22", "low": 9.8}]
assert stop_mock.call_args.kwargs["window"] == 3
assert "helpers" in stop_mock.call_args.kwargs
assert breakout_mock.call_args[0][0][0]["date"] == "2026-04-22"
assert breakout_mock.call_args.kwargs["target_date"] == "2026-04-22"
assert "helpers" in breakout_mock.call_args.kwargs
assert enrich_mock.call_args[0][:3] == ({"effective_stop": 9.9}, "000001", "2026-04-22")
assert enrich_mock.call_args.kwargs["recent_bars"] == bars_payload
assert "helpers" in enrich_mock.call_args.kwargs
assert recent == bars_payload
assert stop_line == anchor_payload
assert breakout == breakout_payload
assert enriched == enriched_payload
"""
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_daily_price_runtime_exposes_helper_bindings(self):
        runtime = self._load_module()
        exec(
            """
def _tradability_probe(stock, target_date='', recent_bars=None):
    return runtime_test_helper(fetch_daily_price_bars, _compute_bar_change_pct, normalize_stock_code(stock.get('code', '')), target_date)
""",
            runtime.__dict__,
        )

        with patch(
            "market_data.daily_price_runtime._evaluate_live_tradability_legacy_body",
            runtime._tradability_probe,
        ):
            result = runtime.evaluate_live_tradability(
                {"code": "1"},
                target_date="2026-04-22",
                helpers={
                    "runtime_test_helper": lambda fetch_daily_price_bars, compute_bar_change_pct, code, target_date: (
                        fetch_daily_price_bars is runtime.fetch_daily_price_bars,
                        compute_bar_change_pct is runtime._compute_bar_change_pct,
                        code,
                        target_date,
                    ),
                    "normalize_stock_code": lambda code: str(code).zfill(6),
                },
            )

        self.assertEqual(result, (True, True, "000001", "2026-04-22"))

    def test_price_runtime_core_helpers_cover_market_rules(self):
        runtime = self._load_module()
        helpers = {
            "normalize_stock_code": lambda code: str(code or "").zfill(6),
            "_safe_float": lambda value, default=0: float(value or default),
            "_normalize_kline_date_str": lambda value: value,
            "_parse_kline_date": lambda value: __import__("datetime").datetime.strptime(value, "%Y-%m-%d"),
        }

        bs_code = runtime.to_bs_code("1", is_index=False, helpers=helpers)
        limit_pct = runtime.get_limit_up_pct("300001", "创业板一号", helpers=helpers)
        one_word = runtime.is_one_word_limit_bar(
            stock_code="300001",
            stock_name="创业板一号",
            open_price=10.0,
            high_price=10.0,
            low_price=10.0,
            close_price=10.0,
            change_pct=19.8,
            helpers=helpers,
        )
        merged = runtime.merge_daily_price_bars(
            [{"date": "2026-04-22", "close": 10.5}],
            [{"date": "2026-04-21", "close": 10.1}, {"date": "2026-04-22", "close": 9.9}],
            helpers=helpers,
        )
        change_pct = runtime.compute_bar_change_pct(
            {"close": 11.0},
            {"close": 10.0},
            helpers=helpers,
        )

        self.assertEqual(bs_code, "sz.000001")
        self.assertAlmostEqual(limit_pct, 0.198)
        self.assertTrue(one_word)
        self.assertEqual([bar["date"] for bar in merged], ["2026-04-21", "2026-04-22"])
        self.assertAlmostEqual(merged[-1]["close"], 10.5)
        self.assertAlmostEqual(change_pct, 10.0)

    def test_run_with_wall_clock_timeout_is_self_contained_without_extra_helpers(self):
        runtime = self._load_module()
        result = runtime.run_with_wall_clock_timeout(1, lambda: "ok")
        self.assertEqual(result, "ok")

    def test_daily_price_runtime_fetch_recent_price_bars_trims_to_target_window(self):
        runtime = self._load_module()
        fetcher = getattr(runtime, "fetch_recent_price_bars", None)
        self.assertIsNotNone(fetcher)

        with patch(
            "market_data.daily_price_runtime.fetch_daily_price_bars",
            return_value=[
                {"date": "2026-04-18", "close": 9.6},
                {"date": "2026-04-21", "close": 10.1},
                {"date": "2026-04-22", "close": 10.5},
                {"date": "2026-04-23", "close": 10.8},
            ],
        ) as bars_mock:
            result = fetcher("000001", "2026-04-22", lookback_days=2)

        self.assertEqual(bars_mock.call_args[0][:3], ("000001", "2026-04-12", "2026-04-22"))
        self.assertEqual([bar["date"] for bar in result], ["2026-04-21", "2026-04-22"])

    def test_daily_price_runtime_enriches_stop_plan_with_reference_anchors(self):
        runtime = self._load_module()
        enricher = getattr(runtime, "enrich_stop_plan_with_reference_anchors", None)
        self.assertIsNotNone(enricher)

        result = enricher(
            {"effective_stop": 10.2},
            "000001",
            "2026-04-22",
            recent_bars=[
                {"date": "2026-04-17", "open": 9.8, "high": 10.0, "low": 9.6, "close": 9.7},
                {"date": "2026-04-18", "open": 9.7, "high": 10.1, "low": 9.65, "close": 10.05},
                {"date": "2026-04-21", "open": 10.1, "high": 10.9, "low": 10.0, "close": 10.85},
                {"date": "2026-04-22", "open": 10.82, "high": 11.0, "low": 10.3, "close": 10.95},
            ],
        )

        self.assertEqual(result["daily_anchor_stop"], 9.6)
        self.assertEqual(result["daily_anchor_date"], "2026-04-17")
        self.assertEqual(result["breakout_open_anchor"], 10.1)
        self.assertEqual(result["breakout_anchor_date"], "2026-04-21")
