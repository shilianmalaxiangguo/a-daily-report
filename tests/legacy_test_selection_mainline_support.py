import subprocess
import sys
import unittest
from pathlib import Path

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


class SelectionMainlineSupportTest(unittest.TestCase):
    def _load_module(self):
        try:
            return __import__("selection.mainline_support", fromlist=["mainline_support"])
        except ModuleNotFoundError as error:
            self.fail(f"selection.mainline_support should exist: {error}")

    def test_legacy_selection_mainline_wrappers_delegate_to_support_runtime(self):
        result = _run_legacy_entry_probe(
            """
import daily_report_entry_demo
from unittest.mock import patch

watchlist = [{"sector": "军工"}, {"sector": "机器人"}]

with patch.object(daily_report_entry_demo, "run_resolve_primary_mainline_name", return_value="军工") as resolve_mock, \
     patch.object(daily_report_entry_demo, "run_split_candidates_by_mainline", return_value=([watchlist[0]], [watchlist[1]])) as split_mock:
    mainline_name = daily_report_entry_demo._resolve_primary_mainline_name(
        {"observation": {"mainline_candidates": ["暂无明确主线", "军工"]}},
        fallback_mainline="机器人",
    )
    grouped = daily_report_entry_demo._split_candidates_by_mainline(watchlist, "军工")

assert resolve_mock.call_args[0] == ({"observation": {"mainline_candidates": ["暂无明确主线", "军工"]}}, "机器人")
assert "helpers" in resolve_mock.call_args.kwargs
assert split_mock.call_args[0] == (watchlist, "军工")
assert "helpers" in split_mock.call_args.kwargs
assert mainline_name == "军工"
assert grouped == ([watchlist[0]], [watchlist[1]])
"""
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_selection_mainline_support_resolves_and_splits_contract(self):
        support = self._load_module()

        mainline_name = support.resolve_primary_mainline_name(
            {"observation": {"mainline_candidates": ["暂无明确主线", "军工", "机器人"]}},
            fallback_mainline="汽车",
        )
        fallback_name = support.resolve_primary_mainline_name(
            {"observation": {"mainline_candidates": ["暂无明确主线"]}},
            fallback_mainline="机器人",
        )
        empty_name = support.resolve_primary_mainline_name(
            {"observation": {"mainline_candidates": ["暂无明确主线"]}},
            fallback_mainline="暂无明确主线",
        )
        grouped = support.split_candidates_by_mainline(
            [{"sector": "军工"}, {"sector": "机器人"}, {"sector": "军工"}],
            "军工",
            helpers={"_candidate_matches_mainline": lambda item, mainline_name="": item.get("sector") == mainline_name},
        )

        self.assertEqual(mainline_name, "军工")
        self.assertEqual(fallback_name, "机器人")
        self.assertEqual(empty_name, "")
        self.assertEqual(grouped, ([{"sector": "军工"}, {"sector": "军工"}], [{"sector": "机器人"}]))


if __name__ == "__main__":
    unittest.main()
