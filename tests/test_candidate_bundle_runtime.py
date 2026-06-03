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
from selection.trend_snapshot_runtime import build_extreme_conviction_list


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
assert callable(bundle_mock.call_args.kwargs["helpers"]["build_extreme_conviction_groups"])
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

    def test_candidate_bundle_sort_does_not_count_abnormal_bonus_twice(self):
        result = build_candidate_bundle_contract(
            data={"lianban_data": {"stocks": []}},
            exit_analysis={"sector_name": "军工"},
            candidates=[],
            watchlist=[
                {"name": "基础更强", "code": "000001", "sector": "军工", "score": 70},
                {"name": "异动追平", "code": "000002", "sector": "军工", "score": 60},
            ],
            abnormal_watch_map={
                "000001": {"follow_state": "缩量消化"},
                "000002": {"follow_state": "跌不下去"},
            },
            dragon_stocks=[],
            normalize_stock_code=lambda code: str(code or ""),
            get_abnormal_rank_adjustment=lambda item: (
                10 if item.get("follow_state") == "跌不下去" else 0,
                item.get("follow_state", ""),
                "rule",
            ),
            split_candidates_by_mainline=lambda stocks, mainline_name: (stocks, []),
            build_gem_observation_pool=lambda candidates, target_date="": [],
            build_sector_trend_snapshot=lambda *args, **kwargs: [],
            build_extreme_conviction_list=lambda *args, **kwargs: [],
        )

        self.assertEqual([item["code"] for item in result["evaluated_stocks"][:2]], ["000001", "000002"])
        self.assertEqual(result["evaluated_stocks"][0]["tomorrow_strength"], 70)
        self.assertEqual(result["evaluated_stocks"][1]["tomorrow_strength"], 70)

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

    def test_candidate_bundle_attaches_120_day_bars_before_conviction_scoring(self):
        captured = {}

        def capture_extreme_conviction(evaluated_stocks, *args, **kwargs):
            captured["evaluated_stocks"] = list(evaluated_stocks)
            return evaluated_stocks[:1]

        bars = [
            {"date": f"2026-01-{idx:02d}", "open": 10 + idx, "high": 11 + idx, "low": 9 + idx, "close": 10.5 + idx}
            for idx in range(1, 6)
        ]
        result = build_candidate_bundle_contract(
            data={},
            exit_analysis={"sector_name": "光通信"},
            candidates=[],
            watchlist=[{"name": "光迅科技", "code": "002281", "sector": "光通信", "score": 88}],
            abnormal_watch_map={},
            dragon_stocks=[],
            zt_pool_by_sector={},
            gem_breathing_candidates=[],
            target_date="2026-05-21",
            normalize_stock_code=lambda code: str(code or ""),
            get_abnormal_rank_adjustment=lambda item: (0, "", ""),
            split_candidates_by_mainline=lambda stocks, mainline_name: (stocks, []),
            build_gem_observation_pool=lambda candidates, target_date="": [],
            build_sector_trend_snapshot=lambda *args, **kwargs: [],
            build_extreme_conviction_list=capture_extreme_conviction,
            fetch_recent_price_bars=lambda code, target_date, lookback_days=120, fast_fail=False: (
                self.assertFalse(fast_fail) or bars
            ),
        )

        evaluated = captured["evaluated_stocks"][0]
        self.assertEqual(evaluated["recent_bars"], bars)
        self.assertEqual(result["extreme_conviction_list"][0]["recent_bars"], bars)

    def test_candidate_bundle_blocks_cyberfininvest_risk_from_extreme_conviction(self):
        result = build_candidate_bundle_contract(
            data={
                "stock_risk_map": {
                    "002698": {
                        "risk_flags": ["holder_reduce_announcement"],
                        "risk_summary": "博实股份：股东联创未来拟减持不超过3%股份",
                        "risk_events": [
                            {
                                "risk_type": "holder_reduce_announcement",
                                "title": "博实股份：股东联创未来拟减持不超过3%股份",
                                "source": "cyberfininvest.news",
                            }
                        ],
                    }
                }
            },
            exit_analysis={"sector_name": "机器人"},
            candidates=[],
            watchlist=[
                {
                    "name": "博实股份",
                    "code": "002698",
                    "sector": "机器人",
                    "score": 99,
                    "change_pct": 10.0,
                    "pattern": "光头大阳柱涨停",
                    "reason": "龙一",
                },
                {
                    "name": "华工科技",
                    "code": "000988",
                    "sector": "机器人",
                    "score": 88,
                    "change_pct": 10.0,
                    "pattern": "光头大阳柱涨停",
                    "reason": "龙一",
                },
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
            build_extreme_conviction_list=lambda evaluated_stocks, mainline_name, sector_snapshot=None, top_n=3: build_extreme_conviction_list(
                evaluated_stocks,
                mainline_name,
                sector_snapshot=sector_snapshot,
                top_n=top_n,
                helpers={
                    "normalize_stock_code": lambda code: str(code or ""),
                    "sector_name_matches": lambda sector, mainline: sector == mainline,
                    "_safe_float": lambda value, default=0.0: float(value or default),
                },
            ),
        )

        self.assertEqual([item["code"] for item in result["extreme_conviction_list"]], ["000988"])

    def test_candidate_bundle_exposes_shape_repair_pool_from_extreme_groups(self):
        def build_groups(evaluated_stocks, mainline_name, sector_snapshot=None, top_n=3, risk_context=None):
            return {
                "extreme_conviction_list": [{"code": "002281", "name": "光迅科技"}],
                "shape_repair_pool": [
                    {
                        "code": "002975",
                        "name": "博杰股份",
                        "candidate_layer": "shape_repair_pool",
                        "repair_status": "待修复",
                    }
                ],
            }

        result = build_candidate_bundle_contract(
            data={},
            exit_analysis={"sector_name": "光通信"},
            candidates=[],
            watchlist=[
                {"name": "光迅科技", "code": "002281", "sector": "光通信", "score": 88},
                {"name": "博杰股份", "code": "002975", "sector": "光通信", "score": 86},
            ],
            abnormal_watch_map={},
            dragon_stocks=[],
            zt_pool_by_sector={},
            gem_breathing_candidates=[],
            target_date="2026-05-21",
            normalize_stock_code=lambda code: str(code or ""),
            get_abnormal_rank_adjustment=lambda item: (0, "", ""),
            split_candidates_by_mainline=lambda stocks, mainline_name: (stocks, []),
            build_gem_observation_pool=lambda candidates, target_date="": [],
            build_sector_trend_snapshot=lambda *args, **kwargs: [],
            build_extreme_conviction_groups=build_groups,
        )

        self.assertEqual([item["code"] for item in result["extreme_conviction_list"]], ["002281"])
        self.assertEqual([item["code"] for item in result["shape_repair_pool"]], ["002975"])
        self.assertEqual(result["shape_repair_pool"][0]["repair_status"], "待修复")

    def test_candidate_bundle_reviews_recent_extreme_mentions_even_when_not_in_watchlist(self):
        captured = {}

        def build_groups(evaluated_stocks, mainline_name, sector_snapshot=None, top_n=3, risk_context=None):
            captured["codes"] = [item["code"] for item in evaluated_stocks]
            captured["source_tiers"] = {item["code"]: item.get("source_tier") for item in evaluated_stocks}
            captured["recent_bars"] = {item["code"]: list(item.get("recent_bars") or []) for item in evaluated_stocks}
            return {
                "extreme_conviction_list": [],
                "shape_repair_pool": [
                    {
                        "code": "002975",
                        "name": "博杰股份",
                        "candidate_layer": "shape_repair_pool",
                        "repair_status": "待修复",
                    }
                ],
            }

        bars = [{"date": "2026-05-21", "close": 10.0}]
        result = build_candidate_bundle_contract(
            data={
                "recent_extreme_conviction_mentions": [
                    {
                        "stock_name": "博杰股份",
                        "stock_code": "002975",
                        "sector_candidate": "机器人",
                        "reason": "历史好形态 / 龙回头",
                        "planned_window": "09:50-10:10",
                    }
                ]
            },
            exit_analysis={"sector_name": "机器人"},
            candidates=[],
            watchlist=[],
            abnormal_watch_map={},
            dragon_stocks=[],
            zt_pool_by_sector={},
            gem_breathing_candidates=[],
            target_date="2026-05-21",
            normalize_stock_code=lambda code: str(code or ""),
            get_abnormal_rank_adjustment=lambda item: (0, "", ""),
            split_candidates_by_mainline=lambda stocks, mainline_name: (stocks, []),
            build_gem_observation_pool=lambda candidates, target_date="": [],
            build_sector_trend_snapshot=lambda *args, **kwargs: [],
            build_extreme_conviction_groups=build_groups,
            fetch_recent_price_bars=lambda code, target_date, **kwargs: bars if code == "002975" else [],
        )

        self.assertIn("002975", captured["codes"])
        self.assertEqual(captured["source_tiers"]["002975"], "extreme_conviction")
        self.assertEqual(captured["recent_bars"]["002975"], bars)
        self.assertEqual([item["code"] for item in result["shape_repair_pool"]], ["002975"])

    def test_candidate_bundle_dedupes_recent_extreme_mentions_by_stock_code(self):
        result = build_candidate_bundle_contract(
            data={
                "recent_extreme_conviction_mentions": [
                    {
                        "stock_name": "京能电力",
                        "stock_code": "600578",
                        "sector_candidate": "电力",
                        "mention_trade_date": "2026-05-14",
                        "reason": "旧样本",
                    },
                    {
                        "stock_name": "京能电力",
                        "stock_code": "600578",
                        "sector_candidate": "电力",
                        "mention_trade_date": "2026-05-27",
                        "reason": "最新样本",
                    },
                ]
            },
            exit_analysis={"sector_name": "电力"},
            candidates=[],
            watchlist=[
                {"name": "电力一号", "code": "000001", "sector": "电力", "score": 90},
                {"name": "电力二号", "code": "000002", "sector": "电力", "score": 80},
                {"name": "电力三号", "code": "000003", "sector": "电力", "score": 70},
            ],
            abnormal_watch_map={},
            dragon_stocks=[],
            zt_pool_by_sector={},
            gem_breathing_candidates=[],
            target_date="2026-05-29",
            normalize_stock_code=lambda code: str(code or ""),
            get_abnormal_rank_adjustment=lambda item: (0, "", ""),
            split_candidates_by_mainline=lambda stocks, mainline_name: (stocks, []),
            build_gem_observation_pool=lambda candidates, target_date="": [],
            build_sector_trend_snapshot=lambda *args, **kwargs: [],
            build_extreme_conviction_list=lambda *args, **kwargs: [],
        )

        evaluated_codes = [item["code"] for item in result["evaluated_stocks"]]
        secondary_codes = [item["code"] for item in result["secondary_stocks"]]
        self.assertEqual(evaluated_codes.count("600578"), 1)
        self.assertEqual(secondary_codes, ["600578"])
        self.assertEqual(result["secondary_stocks"][0]["recent_extreme_mention"]["mention_trade_date"], "2026-05-27")
        self.assertIn("最新样本", result["secondary_stocks"][0]["reason"])

    def test_candidate_bundle_explains_recent_extreme_review_destinations(self):
        def build_groups(evaluated_stocks, mainline_name, sector_snapshot=None, top_n=3, risk_context=None):
            return {
                "extreme_conviction_list": [
                    {"code": "002281", "name": "光迅科技", "sector": "光通信"}
                ],
                "shape_repair_pool": [
                    {
                        "code": "002975",
                        "name": "博杰股份",
                        "sector": "机器人",
                        "repair_status": "待修复",
                        "trend_aesthetic_review": {"reasons": ["短线承接转弱"], "action": "重新站回短中线承接后再评估"},
                        "next_action": "保留跟踪，重新站回短中线承接后再评估；继续走坏再取关淘汰",
                    }
                ],
                "dragon_rebound_watch_pool": [
                    {
                        "code": "000586",
                        "name": "汇源通信",
                        "sector": "通信设备",
                        "repair_status": "龙回头观察",
                        "trend_aesthetic_review": {"reasons": ["龙回头样本", "A杀未修复"], "action": "A杀未修复前不进正式名单"},
                        "next_action": "单独观察是否重新站回短中线承接；A杀未修复前不进正式名单，继续走坏再取关淘汰",
                    }
                ],
            }

        result = build_candidate_bundle_contract(
            data={
                "recent_extreme_conviction_mentions": [
                    {"stock_name": "光迅科技", "stock_code": "002281", "sector_candidate": "光通信"},
                    {"stock_name": "博杰股份", "stock_code": "002975", "sector_candidate": "机器人"},
                    {
                        "stock_name": "晶方科技",
                        "stock_code": "603005",
                        "sector_candidate": "半导体",
                        "review_status": "预演作废",
                        "invalidation": "有效跌破日K MA20或跌破后9:50-10:10不能收回，取消幻想，按A杀风险处理",
                        "payload": {"is_a_kill_eliminated": False},
                    },
                ],
                "recent_extreme_conviction_mentions_for_review": [
                    {"stock_name": "光迅科技", "stock_code": "002281", "mention_trade_date": "2026-05-20", "source_section": "极度看好名单"},
                    {"stock_name": "博杰股份", "stock_code": "002975", "mention_trade_date": "2026-05-20", "source_section": "极度看好名单"},
                    {"stock_name": "汇源通信", "stock_code": "000586", "mention_trade_date": "2026-05-19", "source_section": "极度看好名单", "is_a_kill_eliminated": True},
                    {
                        "stock_name": "晶方科技",
                        "stock_code": "603005",
                        "mention_trade_date": "2026-05-20",
                        "source_section": "极度看好名单",
                        "review_status": "预演作废",
                        "invalidation": "有效跌破日K MA20或跌破后9:50-10:10不能收回，取消幻想，按A杀风险处理",
                        "next_action": "若已买入，次日先看是否继续强于市场；失效价失守立即卖，不能把短线拿成长线",
                        "payload": {"is_a_kill_eliminated": False},
                    },
                ],
            },
            exit_analysis={"sector_name": "光通信"},
            candidates=[],
            watchlist=[],
            abnormal_watch_map={},
            dragon_stocks=[],
            zt_pool_by_sector={},
            gem_breathing_candidates=[],
            target_date="2026-05-21",
            normalize_stock_code=lambda code: str(code or ""),
            get_abnormal_rank_adjustment=lambda item: (0, "", ""),
            split_candidates_by_mainline=lambda stocks, mainline_name: (stocks, []),
            build_gem_observation_pool=lambda candidates, target_date="": [],
            build_sector_trend_snapshot=lambda *args, **kwargs: [],
            build_extreme_conviction_groups=build_groups,
        )

        rows = {item["code"]: item for item in result["historical_extreme_review"]}
        self.assertEqual(rows["002281"]["destination"], "正式重点观察名单")
        self.assertEqual(rows["002975"]["destination"], "形态待修复池")
        self.assertEqual(rows["000586"]["destination"], "龙回头观察池")
        self.assertEqual(rows["603005"]["destination"], "历史观察")
        self.assertIn("短线承接转弱", rows["002975"]["review_basis"])
        self.assertIn("A杀未修复", rows["000586"]["review_basis"])
        self.assertIn("A杀未修复前不进正式名单", rows["000586"]["next_action"])
        self.assertIn("若已买入", rows["603005"]["review_basis"])
        self.assertNotIn("若已买入", rows["603005"]["next_action"])
        self.assertIn("不写成明日新增参与", rows["603005"]["next_action"])

    def test_candidate_bundle_routes_rank_one_eliminated_anchor_to_dragon_rebound_watch_pool(self):
        result = build_candidate_bundle_contract(
            data={
                "recent_extreme_conviction_mentions_for_review": [
                    {
                        "stock_name": "汇源通信",
                        "stock_code": "000586",
                        "mention_trade_date": "2026-05-19",
                        "source_section": "极度看好名单",
                        "rank_no": 1,
                        "rank": 1,
                        "reason": "板块锚定龙 / 首板",
                        "review_status": "预演作废",
                        "next_action": "若已参与，次日先看是否继续强于市场",
                        "invalidation": "有效跌破日K MA20或跌破后9:50-10:10不能收回，取消幻想，按A杀风险处理",
                        "is_a_kill_eliminated": True,
                        "payload": {"is_a_kill_eliminated": True},
                    },
                    {
                        "stock_name": "可川科技",
                        "stock_code": "603052",
                        "mention_trade_date": "2026-05-19",
                        "source_section": "极度看好名单",
                        "rank_no": 3,
                        "rank": 3,
                        "reason": "普通观察",
                        "is_a_kill_eliminated": True,
                        "payload": {"is_a_kill_eliminated": True},
                    },
                ]
            },
            exit_analysis={"sector_name": "通信设备"},
            candidates=[],
            watchlist=[],
            abnormal_watch_map={},
            dragon_stocks=[],
            zt_pool_by_sector={},
            gem_breathing_candidates=[],
            target_date="2026-05-21",
            normalize_stock_code=lambda code: str(code or ""),
            get_abnormal_rank_adjustment=lambda item: (0, "", ""),
            split_candidates_by_mainline=lambda stocks, mainline_name: (stocks, []),
            build_gem_observation_pool=lambda candidates, target_date="": [],
            build_sector_trend_snapshot=lambda *args, **kwargs: [],
            build_extreme_conviction_groups=lambda *args, **kwargs: {
                "extreme_conviction_list": [],
                "shape_repair_pool": [],
                "dragon_rebound_watch_pool": [],
            },
        )

        rows = {item["code"]: item for item in result["historical_extreme_review"]}
        self.assertEqual(rows["000586"]["destination"], "龙回头观察池")
        self.assertEqual(rows["000586"]["review_status"], "龙回头观察")
        self.assertIn("板块锚定龙", rows["000586"]["review_basis"])
        self.assertIn("A杀未修复前不进正式名单", rows["000586"]["next_action"])
        self.assertEqual(rows["603052"]["destination"], "取关淘汰")

    def test_candidate_bundle_passes_st_resume_systemic_risk_to_extreme_conviction(self):
        captured = {}

        def capture_extreme_conviction(evaluated_stocks, mainline_name, sector_snapshot=None, top_n=3, risk_context=None):
            captured["risk_context"] = risk_context
            return list(evaluated_stocks)[:1]

        build_candidate_bundle_contract(
            data={
                "systemic_risk_warnings": [
                    {
                        "name": "全市场",
                        "risk_level": "high",
                        "risk_source": "st_resume_experience",
                        "reason": "2只突发ST复牌，经验上容易触发量化/风控卖出，明日有4000+下跌风险。",
                    }
                ],
                "risk_theme_impacts": [{"name": "ST股", "risk_source": "st_resume_experience"}],
            },
            exit_analysis={"sector_name": "机器人"},
            candidates=[],
            watchlist=[{"name": "华工科技", "code": "000988", "sector": "机器人", "score": 88}],
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
            build_extreme_conviction_list=capture_extreme_conviction,
        )

        self.assertEqual(captured["risk_context"]["systemic_risk_warnings"][0]["risk_source"], "st_resume_experience")
        self.assertEqual(captured["risk_context"]["risk_theme_impacts"][0]["name"], "ST股")

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

    def test_extreme_conviction_uses_anchor_reversal_before_score_ranking(self):
        result = build_candidate_bundle_contract(
            data={},
            exit_analysis={"sector_name": "电力"},
            candidates=[],
            watchlist=[
                {
                    "name": "京能电力",
                    "code": "600578",
                    "sector": "电力",
                    "score": 98,
                    "change_pct": 9.8,
                    "pattern": "光头大阳柱涨停",
                    "reason": "低位补涨 / 套利工具 / 被板块带动",
                    "trend_aesthetic_status": "通过",
                },
                {
                    "name": "大唐发电",
                    "code": "601991",
                    "sector": "电力",
                    "score": 88,
                    "change_pct": 5.2,
                    "pattern": "强实体",
                    "reason": "电力板块锚定龙 / 趋势比价链锚点",
                    "trend_aesthetic_status": "通过",
                },
                {
                    "name": "华电辽能",
                    "code": "600396",
                    "sector": "电力",
                    "score": 86,
                    "change_pct": 4.8,
                    "pattern": "强趋势",
                    "reason": "大容量趋势龙头 / 中军承接",
                    "capacity_profile": "大容量趋势资金",
                    "why_not_anchor": "大唐发电短线加速过热，华电辽能承接更适合补位",
                    "allow_extreme_conviction": True,
                    "trend_aesthetic_status": "通过",
                },
            ],
            abnormal_watch_map={},
            dragon_stocks=[
                {"name": "大唐发电", "code": "601991", "sector": "电力", "reason": "龙一"},
            ],
            zt_pool_by_sector={"电力": [{"代码": "600578"}]},
            gem_breathing_candidates=[],
            target_date="2026-05-29",
            normalize_stock_code=lambda code: str(code or ""),
            get_abnormal_rank_adjustment=lambda item: (0, "", ""),
            split_candidates_by_mainline=lambda stocks, mainline_name: (stocks, []),
            build_gem_observation_pool=lambda candidates, target_date="": [],
            build_sector_trend_snapshot=build_extreme_conviction_list.__globals__["build_sector_trend_snapshot"],
            build_extreme_conviction_list=lambda evaluated_stocks, mainline_name, sector_snapshot=None, top_n=3, risk_context=None: build_extreme_conviction_list(
                evaluated_stocks,
                mainline_name,
                sector_snapshot=sector_snapshot,
                top_n=top_n,
                risk_context=risk_context,
            ),
        )

        conviction_by_role = {item["sniper_role"]: item for item in result["extreme_conviction_list"]}
        self.assertEqual(conviction_by_role["明日主买对象"]["code"], "601991")
        self.assertEqual(conviction_by_role["明日补位对象"]["code"], "600396")
        self.assertEqual(conviction_by_role["候选观察"]["code"], "600578")
        self.assertEqual(conviction_by_role["候选观察"]["candidate_role"], "套利工具")
        self.assertEqual(conviction_by_role["候选观察"]["anchor_reversal_decision"], "降级观察")
        self.assertIn("不能替代板块锚", conviction_by_role["候选观察"]["anchor_reversal_reason"])
        self.assertEqual([item["code"] for item in result["core_stocks"]], ["601991"])
        self.assertEqual([item["code"] for item in result["secondary_stocks"]], ["600396"])
        self.assertNotIn("600578", {item["code"] for item in result["core_stocks"] + result["secondary_stocks"]})

    def test_mainline_dragon_source_enters_evaluation_before_limit_up_laggard(self):
        result = build_candidate_bundle_contract(
            data={},
            exit_analysis={"sector_name": "电力"},
            candidates=[],
            watchlist=[
                {
                    "name": "京能电力",
                    "code": "600578",
                    "sector": "电力",
                    "score": 98,
                    "change_pct": 10.0,
                    "pattern": "光头大阳柱涨停",
                    "reason": "低位补涨 / 套利工具 / 被板块带动",
                    "trend_aesthetic_status": "通过",
                }
            ],
            abnormal_watch_map={},
            dragon_stocks=[
                {
                    "name": "大唐发电",
                    "code": "601991",
                    "sector": "电力",
                    "score": 82,
                    "change_pct": 1.1,
                    "pattern": "沿MA5趋势推进，缩量回踩不破，低点上移",
                    "reason": "板块锚 / 大容量趋势龙头 / MA5入/MA7清/MA5T / 承接好",
                    "capacity_profile": "大容量趋势资金",
                    "trend_aesthetic_status": "通过",
                }
            ],
            zt_pool_by_sector={"电力": [{"代码": "600578"}]},
            gem_breathing_candidates=[],
            target_date="2026-06-02",
            normalize_stock_code=lambda code: str(code or ""),
            get_abnormal_rank_adjustment=lambda item: (0, "", ""),
            split_candidates_by_mainline=lambda stocks, mainline_name: (
                [item for item in stocks if item.get("sector") == mainline_name],
                [item for item in stocks if item.get("sector") != mainline_name],
            ),
            build_gem_observation_pool=lambda candidates, target_date="": [],
            build_sector_trend_snapshot=build_extreme_conviction_list.__globals__["build_sector_trend_snapshot"],
            build_extreme_conviction_list=lambda evaluated_stocks, mainline_name, sector_snapshot=None, top_n=3, risk_context=None: build_extreme_conviction_list(
                evaluated_stocks,
                mainline_name,
                sector_snapshot=sector_snapshot,
                top_n=top_n,
                risk_context=risk_context,
            ),
        )

        conviction_by_role = {item["sniper_role"]: item for item in result["extreme_conviction_list"]}
        self.assertEqual(conviction_by_role["明日主买对象"]["code"], "601991")
        self.assertEqual(conviction_by_role["候选观察"]["code"], "600578")
        self.assertEqual(conviction_by_role["候选观察"]["candidate_role"], "套利工具")
        self.assertIn("601991", {item["code"] for item in result["evaluated_stocks"]})
        self.assertEqual([item["code"] for item in result["core_stocks"]], ["601991"])

    def test_hot_capacity_source_enters_evaluation_before_limit_up_laggard(self):
        result = build_candidate_bundle_contract(
            data={
                "turnover_rank": [
                    {
                        "rank": 1,
                        "name": "工业富联",
                        "code": "601138",
                        "sector": "通信设备",
                        "turnover": 294.0,
                        "change_pct": 8.49,
                    }
                ],
                "hot_rank_top30": [
                    {
                        "rank": 2,
                        "name": "工业富联",
                        "code": "601138",
                        "concepts": ["共封装光学(CPO)"],
                        "rate": "41257554",
                    }
                ],
                "stock_full_info": {
                    "601138": {
                        "name": "工业富联",
                        "industry": "通信设备",
                        "所属行业": "通信设备",
                        "change_pct": 8.49,
                        "turnover": 294.0,
                    },
                    "002897": {
                        "name": "意华股份",
                        "industry": "通信设备",
                        "所属行业": "通信设备",
                        "change_pct": 10.0,
                        "turnover": 6.44,
                    },
                },
            },
            exit_analysis={"sector_name": "通信设备"},
            candidates=[
                {"name": "工业富联", "code": "601138", "sector": "通信设备", "turnover": 294.0, "_source": "成交额排名"},
                {"name": "意华股份", "code": "002897", "sector": "通信设备", "turnover": 6.44, "_source": "涨停池"},
            ],
            watchlist=[
                {
                    "name": "意华股份",
                    "code": "002897",
                    "sector": "通信设备",
                    "score": 98,
                    "change_pct": 10.0,
                    "pattern": "光头大阳柱涨停",
                    "reason": "首板涨停 / 被主线带动 / 跟风样本",
                    "trend_aesthetic_status": "通过",
                }
            ],
            abnormal_watch_map={},
            dragon_stocks=[],
            zt_pool_by_sector={"通信设备": [{"代码": "002897"}]},
            gem_breathing_candidates=[],
            target_date="2026-06-02",
            normalize_stock_code=lambda code: str(code or ""),
            get_abnormal_rank_adjustment=lambda item: (0, "", ""),
            split_candidates_by_mainline=lambda stocks, mainline_name: (
                [item for item in stocks if item.get("sector") == mainline_name],
                [item for item in stocks if item.get("sector") != mainline_name],
            ),
            build_gem_observation_pool=lambda candidates, target_date="": [],
            build_sector_trend_snapshot=build_extreme_conviction_list.__globals__["build_sector_trend_snapshot"],
            build_extreme_conviction_list=lambda evaluated_stocks, mainline_name, sector_snapshot=None, top_n=3, risk_context=None: build_extreme_conviction_list(
                evaluated_stocks,
                mainline_name,
                sector_snapshot=sector_snapshot,
                top_n=top_n,
                risk_context=risk_context,
            ),
        )

        evaluated_by_code = {item["code"]: item for item in result["evaluated_stocks"]}
        self.assertIn("601138", evaluated_by_code)
        self.assertEqual(evaluated_by_code["601138"]["candidate_role"], "大容量中军")
        self.assertEqual(result["sector_trend_snapshot"][0]["anchor_code"], "601138")
        conviction_by_code = {item["code"]: item for item in result["extreme_conviction_list"]}
        self.assertEqual(conviction_by_code["601138"]["sniper_role"], "明日主买对象")
        self.assertEqual(conviction_by_code["601138"]["anchor_reversal_decision"], "可作为主对象")
        self.assertEqual(conviction_by_code["002897"]["sniper_role"], "候选观察")
        self.assertEqual(conviction_by_code["002897"]["anchor_reversal_decision"], "降级观察")
        self.assertEqual([item["code"] for item in result["core_stocks"]], ["601138"])

    def test_anchor_reversal_downgrade_never_becomes_primary_when_alone(self):
        result = build_extreme_conviction_list(
            [
                {
                    "name": "京能电力",
                    "code": "600578",
                    "sector": "电力",
                    "score": 98,
                    "change_pct": 9.8,
                    "pattern": "光头大阳柱涨停",
                    "reason": "低位补涨 / 套利工具 / 被板块带动",
                    "trend_aesthetic_status": "通过",
                }
            ],
            "电力",
            sector_snapshot=[
                {
                    "sector": "电力",
                    "anchor_name": "大唐发电",
                    "anchor_code": "601991",
                    "anchor_reason": "板块锚定龙",
                }
            ],
            top_n=3,
        )

        self.assertEqual(result[0]["anchor_reversal_decision"], "降级观察")
        self.assertEqual(result[0]["sniper_role"], "候选观察")
        self.assertFalse(result[0]["primary_buy_candidate"])
        self.assertFalse(result[0]["backup_buy_candidate"])

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

    def test_candidate_bundle_uses_ai_server_narrative_over_raw_communication_industry(self):
        result = build_candidate_bundle_contract(
            data={
                "stock_full_info": {
                    "601138": {
                        "code": "601138",
                        "name": "工业富联",
                        "industry": "通信设备",
                        "所属行业": "通信设备",
                        "close": 80.01,
                        "change_pct": 8.49,
                    }
                },
                "xueqiu_hot_stock_arguments": [
                    {
                        "code": "601138",
                        "full_code": "SH601138",
                        "argument": "工业富联获英伟达AI平台大额订单",
                        "provider": "xueqiu.hot_stock.argument",
                    }
                ],
            },
            exit_analysis={"sector_name": "通信设备"},
            candidates=[],
            watchlist=[
                {
                    "name": "工业富联",
                    "code": "601138",
                    "sector": "通信设备",
                    "concepts": ["同花顺果指数", "共封装光学(CPO)", "算力租赁", "液冷服务器"],
                    "score": 90,
                }
            ],
            abnormal_watch_map={},
            dragon_stocks=[],
            zt_pool_by_sector={},
            gem_breathing_candidates=[],
            target_date="2026-06-02",
            normalize_stock_code=lambda code: str(code or "").replace(".SH", ""),
            get_abnormal_rank_adjustment=lambda item: (0, "", ""),
            split_candidates_by_mainline=lambda stocks, mainline_name: (stocks, []),
            build_gem_observation_pool=lambda candidates, target_date="": [],
            build_sector_trend_snapshot=lambda *args, **kwargs: [],
            build_extreme_conviction_list=lambda evaluated_stocks, *args, **kwargs: evaluated_stocks[:1],
        )

        stock = result["extreme_conviction_list"][0]
        self.assertEqual(stock["sector"], "AI算力基础设施")
        self.assertEqual(stock["trade_narrative_sector"], "AI算力基础设施")
        self.assertEqual(stock["raw_sector"], "通信设备")
        self.assertIn("英伟达AI平台", stock["trade_narrative_reason"])


if __name__ == "__main__":
    unittest.main()
