import subprocess
import sys
import unittest
from datetime import datetime
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

    return subprocess.run(
        [sys.executable, "-c", stub_setup + "\n" + script_body],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )


class CandidateContextSupportTest(unittest.TestCase):
    def _load_module(self):
        try:
            return __import__("selection.candidate_context_support", fromlist=["candidate_context_support"])
        except ModuleNotFoundError as error:
            self.fail(f"selection.candidate_context_support should exist: {error}")

    def test_legacy_candidate_context_wrappers_delegate_to_support_runtime(self):
        result = _run_legacy_entry_probe(
            """
import daily_report_entry_demo
from unittest.mock import patch

candidate = {"code": "000001", "setup_signal_id": "burst_hold"}

with patch.object(daily_report_entry_demo, "run_build_washout_reclaim_context", return_value={"stage_label": "洗盘完成型修复"}) as washout_mock, \
     patch.object(daily_report_entry_demo, "run_build_trend_continuation_context", return_value={"stage_label": "趋势续强"}) as trend_mock:
    washout = daily_report_entry_demo._build_washout_reclaim_context(candidate, "军工", {"000001"}, {"000001"}, "2026-04-22")
    trend = daily_report_entry_demo._build_trend_continuation_context(candidate, "军工", {"000001"}, {"000001"}, "2026-04-22")

assert washout_mock.call_args[0] == (candidate, "军工", {"000001"}, {"000001"}, "2026-04-22")
assert "helpers" in washout_mock.call_args.kwargs
assert trend_mock.call_args[0] == (candidate, "军工", {"000001"}, {"000001"}, "2026-04-22")
assert "helpers" in trend_mock.call_args.kwargs
assert washout["stage_label"] == "洗盘完成型修复"
assert trend["stage_label"] == "趋势续强"
"""
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_candidate_context_support_builds_washout_and_trend_contracts(self):
        support = self._load_module()
        helpers = {
            "normalize_stock_code": lambda code: str(code or "").strip(),
            "_candidate_matches_mainline": lambda item, mainline_name="": item.get("sector") == mainline_name,
            "_resolve_candidate_setup_id": lambda item: item.get("setup_signal_id", ""),
            "_resolve_candidate_follow_state": lambda item: item.get("follow_state", ""),
            "_normalize_kline_date_str": lambda value: str(value or "").strip(),
            "_parse_kline_date": lambda value: datetime.strptime(str(value), "%Y-%m-%d") if value else None,
            "fetch_recent_price_bars": lambda code, target_date, lookback_days=4, fast_fail=True: [],
            "_safe_float": lambda value, default=0.0: default if value in (None, "") else float(value),
            "_round_or_none": lambda value, digits=4: None if value is None else round(float(value), digits),
        }

        washout = support.build_washout_reclaim_context(
            {
                "code": "000001",
                "sector": "军工",
                "setup_signal_id": "burst_hold",
                "follow_state": "跌不下去",
                "abnormal_date": "2026-04-20",
                "abnormal_subtype": "entity_bear_reclaim",
            },
            "军工",
            {"000001"},
            set(),
            "2026-04-22",
            helpers=helpers,
        )

        trend = support.build_trend_continuation_context(
            {
                "code": "000001",
                "sector": "军工",
                "recent_bars": [
                    {"date": "2026-04-17", "close": 10.0, "high": 10.1, "low": 9.8},
                    {"date": "2026-04-18", "close": 10.1, "high": 10.2, "low": 9.95},
                    {"date": "2026-04-21", "close": 10.2, "high": 10.35, "low": 10.0},
                    {"date": "2026-04-22", "close": 10.4, "high": 10.5, "low": 10.15},
                ],
            },
            "军工",
            {"000001"},
            set(),
            "2026-04-22",
            helpers=helpers,
        )

        self.assertTrue(washout["active"])
        self.assertTrue(washout["recognition_ok"])
        self.assertTrue(washout["within_3d_window"])
        self.assertEqual(washout["subtype_label"], "实体阴线后反包")
        self.assertIn("三日内快速收复", washout["note"])
        self.assertTrue(trend["active"])
        self.assertTrue(trend["act_right"])
        self.assertTrue(trend["near_new_high"])
        self.assertEqual(trend["stage_label"], "趋势续强")
        self.assertEqual(trend["latest_close"], 10.4)
        self.assertIn("连续 act right", trend["note"])

    def test_candidate_context_support_uses_runtime_default_dependencies_when_helpers_omitted(self):
        support = self._load_module()

        with patch.object(support, "normalize_stock_code", side_effect=lambda code: str(code or "").strip()) as normalize_mock, \
             patch.object(support, "_candidate_matches_mainline", side_effect=lambda item, mainline_name="": item.get("sector") == mainline_name) as mainline_mock, \
             patch.object(support, "_resolve_candidate_setup_id", side_effect=lambda item: item.get("setup_signal_id", "")) as setup_mock, \
             patch.object(support, "_resolve_candidate_follow_state", side_effect=lambda item: item.get("follow_state", "")) as follow_mock, \
             patch.object(support, "_normalize_kline_date_str", side_effect=lambda value: str(value or "").strip()) as normalize_date_mock, \
             patch.object(support, "_parse_kline_date", side_effect=lambda value: datetime.strptime(str(value), "%Y-%m-%d") if value else None) as parse_date_mock, \
             patch.object(
                 support,
                 "fetch_recent_price_bars",
                 return_value=[
                     {"date": "2026-04-17", "close": 10.0, "high": 10.1, "low": 9.8},
                     {"date": "2026-04-18", "close": 10.1, "high": 10.2, "low": 9.95},
                     {"date": "2026-04-21", "close": 10.2, "high": 10.35, "low": 10.0},
                     {"date": "2026-04-22", "close": 10.4, "high": 10.5, "low": 10.15},
                 ],
             ) as recent_mock, \
             patch.object(support, "_safe_float", side_effect=lambda value, default=0.0: default if value in (None, "") else float(value)) as safe_float_mock, \
             patch.object(support, "_round_or_none", side_effect=lambda value, digits=4: None if value is None else round(float(value), digits)) as round_mock:
            washout = support.build_washout_reclaim_context(
                {
                    "code": "000001",
                    "sector": "军工",
                    "setup_signal_id": "burst_hold",
                    "follow_state": "跌不下去",
                    "abnormal_date": "2026-04-20",
                    "abnormal_subtype": "entity_bear_reclaim",
                },
                "军工",
                {"000001"},
                set(),
                "2026-04-22",
            )
            trend = support.build_trend_continuation_context(
                {
                    "code": "000001",
                    "sector": "军工",
                },
                "军工",
                {"000001"},
                set(),
                "2026-04-22",
            )

        self.assertTrue(washout["active"])
        self.assertTrue(washout["recognition_ok"])
        self.assertTrue(trend["active"])
        self.assertTrue(trend["act_right"])
        self.assertEqual(trend["latest_close"], 10.4)
        normalize_mock.assert_called()
        mainline_mock.assert_called()
        setup_mock.assert_called_once()
        follow_mock.assert_called_once()
        self.assertGreaterEqual(normalize_date_mock.call_count, 3)
        self.assertGreaterEqual(parse_date_mock.call_count, 2)
        recent_mock.assert_called_once()
        self.assertGreaterEqual(safe_float_mock.call_count, 6)
        round_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
