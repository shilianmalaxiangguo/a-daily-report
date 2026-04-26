import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from selection.candidate_bundle_runtime import (
    build_candidate_bundle_contract,
    build_step2_candidate_bundle,
)


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


class CandidateBundleRuntimeTest(unittest.TestCase):
    def test_legacy_step2_candidate_bundle_wrapper_delegates_to_runtime(self):
        result = _run_legacy_entry_probe(
            """
import daily_report_entry_demo
from unittest.mock import patch

with patch.object(daily_report_entry_demo, "run_build_step2_candidate_bundle", return_value={"core_stocks": []}) as bundle_mock:
    bundle = daily_report_entry_demo.build_step2_candidate_bundle(
        {},
        {"sector_name": "军工"},
        [{"code": "000001"}],
        [{"code": "000001"}],
        {"000001": {"follow_state": "跌不下去"}},
        [{"code": "000001"}],
        target_date="2026-04-22",
    )

assert bundle_mock.call_args[0][:6] == (
    {},
    {"sector_name": "军工"},
    [{"code": "000001"}],
    [{"code": "000001"}],
    {"000001": {"follow_state": "跌不下去"}},
    [{"code": "000001"}],
)
assert bundle_mock.call_args.kwargs["target_date"] == "2026-04-22"
assert "helpers" in bundle_mock.call_args.kwargs
assert bundle == {"core_stocks": []}
"""
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_build_step2_candidate_bundle_runtime_delegates_to_contract_with_helpers(self):
        with patch("selection.candidate_bundle_runtime.build_candidate_bundle_contract", return_value={"core_stocks": []}) as contract_mock:
            result = build_step2_candidate_bundle(
                {},
                {"sector_name": "军工"},
                [{"code": "000001"}],
                [{"code": "000001"}],
                {"000001": {"follow_state": "跌不下去"}},
                [{"code": "000001"}],
                target_date="2026-04-22",
                helpers={
                    "normalize_stock_code": lambda code: code,
                    "get_abnormal_rank_adjustment": lambda item: (10, "跌不下去", "rule"),
                    "split_candidates_by_mainline": lambda stocks, mainline_name: (stocks, []),
                    "build_gem_observation_pool": lambda candidates, target_date="": [],
                    "build_sector_trend_snapshot": lambda *args, **kwargs: [],
                    "build_extreme_conviction_list": lambda *args, **kwargs: [],
                },
            )

        self.assertEqual(result, {"core_stocks": []})
        self.assertTrue(callable(contract_mock.call_args.kwargs["normalize_stock_code"]))
        self.assertTrue(callable(contract_mock.call_args.kwargs["build_extreme_conviction_list"]))

    def test_candidate_bundle_contract_builds_mainline_and_crossline_groups(self):
        result = build_candidate_bundle_contract(
            data={
                "lianban_data": {
                    "stocks": [
                        {"code": "000001", "连板数": 2},
                        {"code": "000002", "连板数": 1},
                    ]
                }
            },
            exit_analysis={"sector_name": "军工"},
            candidates=[{"code": "000001"}, {"code": "000002"}],
            watchlist=[
                {"name": "军工一号", "code": "000001", "sector": "军工", "score": 70},
                {"name": "机器人一号", "code": "000002", "sector": "机器人", "score": 60},
            ],
            abnormal_watch_map={
                "000001": {"follow_state": "跌不下去", "abnormal_type": "恐怖阴线异动"},
                "000002": {"follow_state": "缩量消化", "abnormal_type": "长上影异动"},
            },
            dragon_stocks=[{"name": "军工龙头", "code": "000001", "sector": "军工"}],
            zt_pool_by_sector={"军工": [{"代码": "000001"}]},
            gem_breathing_candidates=[{"name": "创业板样本", "code": "300001"}],
            target_date="2026-04-22",
            normalize_stock_code=lambda code: str(code or "").replace(".SZ", ""),
            get_abnormal_rank_adjustment=lambda item: (
                18 if item.get("follow_state") == "跌不下去" else 10,
                item.get("follow_state", ""),
                "rule",
            ),
            split_candidates_by_mainline=lambda stocks, mainline_name: (
                [item for item in stocks if item.get("sector") == mainline_name],
                [item for item in stocks if item.get("sector") != mainline_name],
            ),
            build_gem_observation_pool=lambda candidates, target_date="": [{"code": "300001", "name": "创业板样本"}],
            build_sector_trend_snapshot=lambda *args, **kwargs: [{"sector": "军工", "trend_count": 2}],
            build_extreme_conviction_list=lambda evaluated_stocks, mainline_name, sector_snapshot=None, top_n=3: evaluated_stocks[:1],
        )

        self.assertEqual(result["mainline_name"], "军工")
        self.assertEqual(result["core_stocks"][0]["code"], "000001")
        self.assertEqual(result["crossline_observation_stocks"][0]["code"], "000002")
        self.assertEqual(result["gem_observation_stocks"][0]["code"], "300001")
        self.assertEqual(result["extreme_conviction_list"][0]["code"], "000001")
        self.assertTrue(any(log["step"] == "candidate_scoring" for log in result["module_logs"]))

    def test_candidate_bundle_enriches_core_stock_with_price_shape_and_volume_anomaly(self):
        result = build_candidate_bundle_contract(
            data={
                "stock_full_info": {
                    "300613": {
                        "code": "300613",
                        "open": 55.90,
                        "high": 56.08,
                        "low": 54.21,
                        "close": 56.08,
                        "change_pct": 20.01,
                    }
                },
                "volume_anomalies": [
                    {
                        "stock_code": "300613",
                        "reason": "显著放量6.0倍，涨停，强启动信号",
                    }
                ],
            },
            exit_analysis={"sector_name": "半导体"},
            candidates=[],
            watchlist=[{"name": "富瀚微", "code": "300613", "sector": "半导体", "score": 60}],
            abnormal_watch_map={},
            dragon_stocks=[],
            zt_pool_by_sector={},
            gem_breathing_candidates=[],
            target_date="2026-04-24",
            normalize_stock_code=lambda code: str(code or "").replace(".SZ", ""),
            get_abnormal_rank_adjustment=lambda item: (0, "", ""),
            split_candidates_by_mainline=lambda stocks, mainline_name: (
                [item for item in stocks if item.get("sector") == mainline_name],
                [],
            ),
            build_gem_observation_pool=lambda candidates, target_date="": [],
            build_sector_trend_snapshot=lambda *args, **kwargs: [],
            build_extreme_conviction_list=lambda *args, **kwargs: [],
        )

        core = result["core_stocks"][0]
        self.assertEqual(core["open"], 55.90)
        self.assertEqual(core["high"], 56.08)
        self.assertEqual(core["low"], 54.21)
        self.assertEqual(core["close"], 56.08)
        self.assertEqual(core["change_pct"], 20.01)
        self.assertEqual(core["volume_summary"], "显著放量6.0倍，涨停，强启动信号")


if __name__ == "__main__":
    unittest.main()
