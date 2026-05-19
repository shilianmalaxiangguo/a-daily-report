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
        "pandas": _stub_module("pandas"),
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

    def test_candidate_bundle_attaches_stock_risk_map_before_conviction_scoring(self):
        captured = {}

        def capture_extreme_conviction(evaluated_stocks, *args, **kwargs):
            captured["evaluated_stocks"] = list(evaluated_stocks)
            return evaluated_stocks[:1]

        result = build_candidate_bundle_contract(
            data={
                "stock_risk_map": {
                    "002342": {
                        "risk_flags": ["holder_reduce"],
                        "risk_summary": "控股股东拟减持不超过3%公司股份",
                        "risk_events": [
                            {
                                "risk_type": "holder_reduce",
                                "title": "控股股东拟减持不超过3%公司股份",
                                "source": "tushare.stk_holdertrade",
                            }
                        ],
                    }
                }
            },
            exit_analysis={"sector_name": "机器人"},
            candidates=[],
            watchlist=[{"name": "巨力索具", "code": "002342", "sector": "机器人", "score": 90}],
            abnormal_watch_map={},
            dragon_stocks=[],
            zt_pool_by_sector={},
            gem_breathing_candidates=[],
            target_date="2026-05-18",
            normalize_stock_code=lambda code: str(code or "").replace(".SZ", ""),
            get_abnormal_rank_adjustment=lambda item: (0, "", ""),
            split_candidates_by_mainline=lambda stocks, mainline_name: (stocks, []),
            build_gem_observation_pool=lambda candidates, target_date="": [],
            build_sector_trend_snapshot=lambda *args, **kwargs: [],
            build_extreme_conviction_list=capture_extreme_conviction,
        )

        evaluated = captured["evaluated_stocks"][0]
        self.assertEqual(evaluated["stock_risk"]["risk_flags"], ["holder_reduce"])
        self.assertIn("拟减持", evaluated["news_risk_summary"])
        self.assertEqual(result["extreme_conviction_list"][0]["stock_risk"]["risk_events"][0]["source"], "tushare.stk_holdertrade")

    def test_candidate_bundle_does_not_default_missing_lianban_to_first_board(self):
        result = build_candidate_bundle_contract(
            data={},
            exit_analysis={"sector_name": "绿色电力"},
            candidates=[],
            watchlist=[
                {
                    "name": "大唐发电",
                    "code": "601991",
                    "sector": "绿色电力",
                    "score": 96,
                    "change_pct": 0.13,
                }
            ],
            abnormal_watch_map={},
            dragon_stocks=[],
            zt_pool_by_sector={},
            gem_breathing_candidates=[],
            target_date="2026-05-18",
            normalize_stock_code=lambda code: str(code or ""),
            get_abnormal_rank_adjustment=lambda item: (0, "", ""),
            split_candidates_by_mainline=lambda stocks, mainline_name: (stocks, []),
            build_gem_observation_pool=lambda candidates, target_date="": [],
            build_sector_trend_snapshot=lambda *args, **kwargs: [],
            build_extreme_conviction_list=lambda evaluated_stocks, *args, **kwargs: evaluated_stocks[:1],
        )

        core = result["core_stocks"][0]
        self.assertEqual(core["连板数"], 0)
        self.assertEqual(core["core_level"], "✓ 溢价候选")
        self.assertEqual(core["tmr_forecast"], "明日可能高开溢价")
        self.assertNotIn("首板", core["core_level"])
        self.assertNotIn("首板形态好", core["tmr_forecast"])

    def test_candidate_bundle_enriches_limit_up_reason_from_xuangubao(self):
        result = build_candidate_bundle_contract(
            data={
                "xuangubao_data": {
                    "xuangubao_limit_up_reasons": [
                        {
                            "symbol": "600676.SS",
                            "name": "交运股份",
                            "stock_reason": "拟置入文旅体育资产",
                            "related_plates": [
                                {"plate_id": 15030162, "plate_name": "资产重组", "plate_reason": "重大资产置换预案"}
                            ],
                            "limit_up_days": 1,
                        }
                    ]
                }
            },
            exit_analysis={"sector_name": "资产重组"},
            candidates=[],
            watchlist=[{"name": "交运股份", "code": "600676", "sector": "资产重组", "score": 60}],
            abnormal_watch_map={},
            dragon_stocks=[],
            zt_pool_by_sector={},
            gem_breathing_candidates=[],
            target_date="2026-05-18",
            normalize_stock_code=lambda code: str(code or "").replace(".SS", ""),
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
        self.assertEqual(core["xuangubao_stock_reason"], "拟置入文旅体育资产")
        self.assertEqual(core["xuangubao_related_plate_names"], ["资产重组"])
        self.assertEqual(core["xuangubao_limit_up_days"], 1)

    def test_candidate_bundle_replaces_market_board_sector_from_xuangubao_plate(self):
        result = build_candidate_bundle_contract(
            data={
                "xuangubao_data": {
                    "xuangubao_limit_up_reasons": [
                        {
                            "symbol": "000988.SZ",
                            "name": "华工科技",
                            "stock_reason": "光模块业务订单增长",
                            "related_plates": [
                                {"plate_id": 123, "plate_name": "光通信", "plate_reason": "CPO方向活跃"}
                            ],
                            "limit_up_days": 1,
                        }
                    ]
                }
            },
            exit_analysis={"sector_name": ""},
            candidates=[],
            watchlist=[{"name": "华工科技", "code": "000988", "sector": "HS", "score": 80}],
            abnormal_watch_map={},
            dragon_stocks=[],
            zt_pool_by_sector={},
            gem_breathing_candidates=[],
            target_date="2026-05-18",
            normalize_stock_code=lambda code: str(code or "").replace(".SZ", ""),
            get_abnormal_rank_adjustment=lambda item: (0, "", ""),
            split_candidates_by_mainline=lambda stocks, mainline_name: (stocks, []),
            build_gem_observation_pool=lambda candidates, target_date="": [],
            build_sector_trend_snapshot=lambda *args, **kwargs: [],
            build_extreme_conviction_list=lambda evaluated_stocks, *args, **kwargs: evaluated_stocks[:1],
        )

        self.assertEqual(result["evaluated_stocks"][0]["sector"], "光通信")
        self.assertEqual(result["extreme_conviction_list"][0]["sector"], "光通信")

    def test_candidate_bundle_infers_sector_from_stock_info_and_limit_up_reason(self):
        result = build_candidate_bundle_contract(
            data={
                "stock_full_info": {
                    "300657": {"code": "300657", "industry": "元器件", "所属行业": "元器件", "change_pct": 19.99}
                },
                "lianban_data": {
                    "stocks": [
                        {
                            "code": "000417",
                            "name": "合百集团",
                            "sector": "待补充板块",
                            "reason": "间接投资长鑫科技+合肥国资+区域零售",
                            "lianban_days": 1,
                        }
                    ]
                },
            },
            exit_analysis={"sector_name": ""},
            candidates=[],
            watchlist=[
                {"name": "合百集团", "code": "000417", "sector": "待补充板块", "score": 80, "reason": "间接投资长鑫科技+合肥国资+区域零售"},
                {"name": "弘信电子", "code": "300657", "sector": "未归类", "score": 78, "reason": "Token工厂+昇腾集群+算力租赁"},
            ],
            abnormal_watch_map={},
            dragon_stocks=[],
            zt_pool_by_sector={},
            gem_breathing_candidates=[],
            target_date="2026-05-18",
            normalize_stock_code=lambda code: str(code or "").replace(".SZ", ""),
            get_abnormal_rank_adjustment=lambda item: (0, "", ""),
            split_candidates_by_mainline=lambda stocks, mainline_name: (stocks, []),
            build_gem_observation_pool=lambda candidates, target_date="": [],
            build_sector_trend_snapshot=lambda *args, **kwargs: [],
            build_extreme_conviction_list=lambda evaluated_stocks, *args, **kwargs: evaluated_stocks[:2],
        )

        sectors = {item["code"]: item["sector"] for item in result["extreme_conviction_list"]}
        self.assertEqual(sectors["000417"], "国产芯片")
        self.assertEqual(sectors["300657"], "算力")


if __name__ == "__main__":
    unittest.main()
