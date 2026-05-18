import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from replay.report_replay import build_replay_snapshot_contract
from daily_report_render import REPORT_VARIANT_FULL, REPORT_VARIANT_SUMMARY, build_report_preflight, save_report_outputs


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


class _FakeTencentFinanceData:
    def __init__(self, calendar_events):
        self._calendar_events = calendar_events

    def get_calendar_events(self, target_date=""):
        return list(self._calendar_events)


class _NoArgTencentFinanceData:
    def __init__(self, calendar_events):
        self._calendar_events = calendar_events

    def get_calendar_events(self):
        return list(self._calendar_events)


class ReportReplayTest(unittest.TestCase):
    def _load_module(self):
        try:
            return __import__("replay.report_replay", fromlist=["report_replay"])
        except ModuleNotFoundError as error:
            self.fail(f"replay.report_replay should exist: {error}")

    def test_legacy_replay_wrapper_delegates_to_runtime(self):
        result = _run_legacy_entry_probe(
            """
import daily_report_entry_demo
from unittest.mock import patch

payload = {"data": {"foo": "bar"}, "target_date": "2026-04-23"}
with patch.object(daily_report_entry_demo, "run_replay_from_snapshot", return_value=payload) as runtime_mock:
    data, target_date = daily_report_entry_demo.replay_from_snapshot("2026-04-22", refresh_sources=["major_indices"])

assert runtime_mock.call_args[0][0] == "2026-04-22"
assert runtime_mock.call_args.kwargs["refresh_sources"] == ["major_indices"]
assert "helpers" in runtime_mock.call_args.kwargs
assert data == {"foo": "bar"}
assert target_date == "2026-04-23"
"""
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_replay_runtime_exposes_helper_bindings(self):
        replay_runtime = self._load_module()
        tencent_factory = object()
        major_indices_fetcher = object()
        exec(
            """
def _replay_probe(target_date, refresh_sources=None):
    return runtime_test_helper(target_date, refresh_sources, load_data_snapshot, TencentFinanceData, get_major_indices_from_iwencai, safe_float)
""",
            replay_runtime.__dict__,
        )

        with patch(
            "replay.report_replay._replay_from_snapshot_legacy_body",
            replay_runtime._replay_probe,
        ):
            result = replay_runtime.replay_from_snapshot(
                "2026-04-22",
                refresh_sources=["calendar_events"],
                helpers={
                    "runtime_test_helper": lambda target_date, refresh_sources, load_data_snapshot, tencent_factory, get_major_indices_from_iwencai, safe_float: (
                        target_date,
                        refresh_sources,
                        load_data_snapshot("x")[0],
                        tencent_factory,
                        get_major_indices_from_iwencai,
                        safe_float(1.25),
                    ),
                    "load_data_snapshot": lambda target_date: ({"snapshot": target_date}, ""),
                    "TencentFinanceData": tencent_factory,
                    "get_major_indices_from_iwencai": major_indices_fetcher,
                    "safe_float": lambda value: float(value or 0),
                },
            )

        self.assertEqual(result, ("2026-04-22", ["calendar_events"], {"snapshot": "x"}, tencent_factory, major_indices_fetcher, 1.25))

    def test_build_replay_snapshot_contract_refreshes_calendar_and_indices(self):
        snapshot = {
            "calendar_events": [{"title": "old"}],
            "indices": [],
            "data_status": {},
            "step_status": {},
            "timer_summary": {"steps": [["旧步骤", 1.0, 1.0]]},
        }

        result = build_replay_snapshot_contract(
            "2026-04-22",
            refresh_sources=["calendar_events", "major_indices"],
            load_data_snapshot=lambda target_date: (snapshot, "补充视角"),
            tencent_factory=lambda: _FakeTencentFinanceData([{"title": "new"}]),
            get_major_indices_from_iwencai=lambda target_date="": [{"code": "sh000001"}],
            safe_float=lambda value: float(value or 0),
            print_fn=lambda *args, **kwargs: None,
        )

        self.assertTrue(result["found"])
        self.assertEqual(result["supplementary_perspective"], "补充视角")
        self.assertEqual(result["data"]["calendar_events"], [{"title": "new"}])
        self.assertEqual(result["data"]["indices"], [{"code": "sh000001"}])
        self.assertTrue(result["data"]["data_status"]["预期日历"])
        self.assertTrue(result["data"]["step_status"]["预期日历获取"])
        self.assertTrue(result["data"]["data_status"]["主要指数"])
        self.assertTrue(result["data"]["step_status"]["主要指数获取"])
        request_logs = result["data"]["module_logs"]
        self.assertTrue(
            any(log["step"] == "request.calendar_events" and log["status"] == "success" for log in request_logs)
        )
        self.assertIn("主要指数获取", [row[0] for row in result["data"]["timer_summary"]["steps"]])
        self.assertTrue(any(log["step"] == "refresh.calendar_events" for log in result["module_logs"]))
        self.assertTrue(any(log["step"] == "refresh.major_indices" for log in result["module_logs"]))

    def test_build_replay_snapshot_contract_refreshes_calendar_when_provider_has_no_target_date_arg(self):
        snapshot = {
            "calendar_events": [{"title": "old"}],
            "indices": [{"code": "sh000001"}],
            "data_status": {"主要指数": True},
            "step_status": {"主要指数获取": True},
        }

        result = build_replay_snapshot_contract(
            "2026-05-14",
            refresh_sources=["calendar_events"],
            load_data_snapshot=lambda target_date: (snapshot, ""),
            tencent_factory=lambda: _NoArgTencentFinanceData([{"title": "new"}]),
            get_major_indices_from_iwencai=lambda target_date="": [],
            safe_float=lambda value: float(value or 0),
            print_fn=lambda *args, **kwargs: None,
        )

        self.assertEqual(result["data"]["calendar_events"], [{"title": "new"}])
        self.assertTrue(
            any(
                log["step"] == "refresh.calendar_events" and log["status"] == "success"
                for log in result["module_logs"]
            )
        )
        self.assertFalse(
            any(
                log["step"] == "refresh.calendar_events" and log["status"] == "warning"
                for log in result["module_logs"]
            )
        )

    def test_build_replay_snapshot_contract_backfills_decision_sources_from_stale_snapshot(self):
        snapshot = {
            "hot_rank_top30": [{"rank": 1, "code": "601991", "name": "大唐发电"}],
            "integrated_hot_list": [],
            "xuangubao_data": {},
            "wanzhu_top10": [],
            "lianban_data": [],
            "indices": [{"code": "sh000001"}],
            "data_status": {
                "涨停池": False,
                "跌停池": False,
                "大盘涨跌统计": False,
                "整合热榜": False,
                "选股通盘中异动": False,
                "顽主杯热门前十": False,
            },
            "step_status": {
                "涨停跌停数据获取": False,
                "整合热榜获取": False,
                "选股通盘中异动获取": False,
                "顽主杯热门前十获取": False,
                "连板梯队提取": False,
                "主要指数获取": True,
            },
            "module_logs": [
                {
                    "module": "domains.market_activity.request",
                    "step": "request.integrated_hot_rank",
                    "status": "error",
                    "message": "整合热榜失败",
                    "details": {"provider": "hot_list_integrated.get_integrated_hot_list"},
                },
                {
                    "module": "domains.monitoring.request",
                    "step": "request.xuangubao",
                    "status": "degraded",
                    "message": "选股通为空",
                    "details": {"provider": "xuangubao.fetch_xuangubao_data", "news_count": 0},
                },
                {
                    "module": "domains.monitoring.request",
                    "step": "request.wanzhu_top10",
                    "status": "degraded",
                    "message": "顽主杯为空",
                    "details": {"provider": "AShareDataCollector.get_wanzhu_top10", "stock_count": 0},
                },
            ],
            "timer_summary": {
                "steps": [
                    ["步骤12: 顽主杯热门前十获取(空)", 1.0, 1.0],
                ]
            },
        }

        xgb_calls = []

        result = build_replay_snapshot_contract(
            "2026-05-18",
            refresh_sources=["noop"],
            load_data_snapshot=lambda target_date: (snapshot, ""),
            tencent_factory=lambda: _FakeTencentFinanceData([]),
            get_major_indices_from_iwencai=lambda target_date="": [],
            safe_float=lambda value: float(value or 0),
            print_fn=lambda *args, **kwargs: None,
            helpers={
                "get_limit_pool_snapshot": lambda target_date: {
                    "provider": "tushare.limit_list_ths",
                    "zt_pool": [{"代码": "601991", "名称": "大唐发电", "所属行业": "电力", "涨停统计": "首板"}],
                    "dt_pool": [{"代码": "301588", "名称": "维达利", "所属行业": "消费电子"}],
                    "market_stats": {"up_count": 2375, "down_count": 3003},
                },
                "fetch_wanzhu_top10": lambda target_date: [{"rank": 1, "code": "601991", "name": "大唐发电"}],
                "fetch_xuangubao_data": lambda target_date=None: xgb_calls.append(target_date) or {
                    "xuangubao_news": [],
                    "xuangubao_plates": [{"name": "国产芯片"}],
                    "diagnostics": {"newsflash": "非法的token"},
                },
            },
        )

        data = result["data"]
        self.assertEqual(len(data["zt_pool"]), 1)
        self.assertEqual(len(data["dt_pool"]), 1)
        self.assertTrue(data["data_status"]["涨停池"])
        self.assertTrue(data["step_status"]["涨停跌停数据获取"])
        self.assertEqual(len(data["integrated_hot_list"]), 1)
        self.assertEqual(len(data["xuangubao_data"]["xuangubao_plates"]), 1)
        self.assertEqual(len(data["wanzhu_top10"]), 1)
        self.assertEqual(data["lianban_data"], [])
        self.assertTrue(data["data_status"]["整合热榜"])
        self.assertTrue(data["data_status"]["选股通盘中异动"])
        self.assertTrue(data["data_status"]["顽主杯热门前十"])
        self.assertTrue(data["step_status"]["连板梯队提取"])
        by_step = {
            item["step"]: item
            for item in data["module_logs"]
            if item.get("step") in {"request.integrated_hot_rank", "request.xuangubao", "request.wanzhu_top10", "request.lianban_snapshot"}
        }
        self.assertEqual(by_step["request.integrated_hot_rank"]["status"], "success")
        self.assertEqual(by_step["request.xuangubao"]["details"]["plate_count"], 1)
        self.assertEqual(by_step["request.xuangubao"]["details"]["diagnostic_note"], "newsflash=非法的token")
        self.assertEqual(by_step["request.wanzhu_top10"]["details"]["stock_count"], 1)
        self.assertEqual(by_step["request.lianban_snapshot"]["status"], "success")
        self.assertIn("顽主杯热门前十获取", [row[0] for row in data["timer_summary"]["steps"]])
        self.assertEqual(xgb_calls, ["2026-05-18"])

    def test_build_replay_snapshot_contract_refreshes_xuangubao_when_newsflash_empty(self):
        snapshot = {
            "hot_rank_top30": [{"rank": 1, "code": "601991", "name": "大唐发电"}],
            "integrated_hot_list": [{"rank": 1, "code": "601991", "name": "大唐发电"}],
            "xuangubao_data": {
                "xuangubao_news": [],
                "xuangubao_plates": [{"name": "国产芯片"}],
                "xuangubao_limit_up_reasons": [{"symbol": "600676.SS", "stock_reason": "拟置入文旅体育资产"}],
                "diagnostics": {"newsflash": "missing XUANGUBAO_IVANKA_TOKEN"},
            },
            "wanzhu_top10": [{"rank": 1, "code": "601991", "name": "大唐发电"}],
            "lianban_data": [],
            "indices": [{"code": "sh000001"}],
            "data_status": {
                "整合热榜": True,
                "选股通盘中异动": True,
                "顽主杯热门前十": True,
            },
            "step_status": {
                "整合热榜获取": True,
                "选股通盘中异动获取": True,
                "顽主杯热门前十获取": True,
                "连板梯队提取": True,
                "主要指数获取": True,
            },
            "module_logs": [
                {
                    "module": "domains.monitoring.request",
                    "step": "request.xuangubao",
                    "status": "success",
                    "message": "已回补选股通盘中异动",
                    "details": {
                        "provider": "xuangubao.fetch_xuangubao_data",
                        "news_count": 0,
                        "plate_count": 1,
                        "limit_up_reason_count": 1,
                        "diagnostic_note": "newsflash=missing XUANGUBAO_IVANKA_TOKEN",
                    },
                }
            ],
        }
        xgb_calls = []

        result = build_replay_snapshot_contract(
            "2026-05-18",
            refresh_sources=["noop"],
            load_data_snapshot=lambda target_date: (snapshot, ""),
            tencent_factory=lambda: _FakeTencentFinanceData([]),
            get_major_indices_from_iwencai=lambda target_date="": [],
            safe_float=lambda value: float(value or 0),
            print_fn=lambda *args, **kwargs: None,
            helpers={
                "fetch_xuangubao_data": lambda target_date=None: xgb_calls.append(target_date) or {
                    "xuangubao_news": [{"title": "今日早盘新闻"}],
                    "xuangubao_plates": [{"name": "国产芯片"}],
                    "xuangubao_limit_up_reasons": [{"symbol": "600676.SS", "stock_reason": "拟置入文旅体育资产"}],
                    "diagnostics": {},
                }
            },
        )

        data = result["data"]
        self.assertEqual(xgb_calls, ["2026-05-18"])
        self.assertEqual(data["xuangubao_data"]["xuangubao_news"][0]["title"], "今日早盘新闻")
        xgb_log = next(log for log in data["module_logs"] if log.get("step") == "request.xuangubao")
        self.assertEqual(xgb_log["details"]["news_count"], 1)
        self.assertEqual(xgb_log["details"]["diagnostic_note"], "")

    def test_build_replay_snapshot_contract_returns_not_found_when_snapshot_missing(self):
        result = build_replay_snapshot_contract(
            "2026-04-22",
            load_data_snapshot=lambda target_date: (None, ""),
            tencent_factory=lambda: _FakeTencentFinanceData([]),
            get_major_indices_from_iwencai=lambda target_date="": [],
            safe_float=lambda value: float(value or 0),
            print_fn=lambda *args, **kwargs: None,
        )

        self.assertFalse(result["found"])
        self.assertIsNone(result["data"])
        self.assertTrue(any(log["step"] == "load.snapshot" and log["status"] == "error" for log in result["module_logs"]))

    def test_build_replay_snapshot_contract_hoists_analysis_atoms_for_report_reuse(self):
        snapshot = {
            "analysis": {
                "mainline_history_record": {
                    "date": "2026-04-23",
                    "primary_mainline": "电力",
                    "leading_line": "电力",
                },
                "sector_turnover_snapshot": {
                    "date": "2026-04-23",
                    "sector_name": "电力",
                    "turnover_share_pct": 2.7,
                },
            },
            "indices": [{"code": "sh000001"}],
            "data_status": {"主要指数": True},
            "step_status": {"主要指数获取": True},
        }

        result = build_replay_snapshot_contract(
            "2026-04-23",
            refresh_sources=["noop"],
            load_data_snapshot=lambda target_date: (snapshot, ""),
            tencent_factory=lambda: _FakeTencentFinanceData([]),
            get_major_indices_from_iwencai=lambda target_date="": [],
            safe_float=lambda value: float(value or 0),
            print_fn=lambda *args, **kwargs: None,
        )

        self.assertTrue(result["found"])
        self.assertEqual(result["data"]["current_mainline_history_record"]["primary_mainline"], "电力")
        self.assertEqual(result["data"]["current_sector_turnover_snapshot"]["turnover_share_pct"], 2.7)

    def test_build_replay_snapshot_contract_builds_missing_mainline_atoms_for_report_reuse(self):
        snapshot = {
            "market_research_snapshot": {
                "state_machine": {"leading_line": "半导体"},
                "observation": {},
            },
            "indices": [{"code": "sh000001"}],
            "data_status": {"主要指数": True},
            "step_status": {"主要指数获取": True},
            "total_turnover": 12834.0,
        }

        result = build_replay_snapshot_contract(
            "2026-04-24",
            refresh_sources=["noop"],
            load_data_snapshot=lambda target_date: (snapshot, ""),
            tencent_factory=lambda: _FakeTencentFinanceData([]),
            get_major_indices_from_iwencai=lambda target_date="": [],
            safe_float=lambda value: float(value or 0),
            print_fn=lambda *args, **kwargs: None,
            helpers={
                "build_mainline_history_record": lambda target_date, market_research_snapshot: {
                    "date": target_date,
                    "primary_mainline": "半导体",
                    "leading_line": "半导体",
                },
                "load_recent_mainline_history": lambda target_date, lookback_days=5: [
                    {"date": "2026-04-22", "primary_mainline": "电力"},
                    {"date": "2026-04-23", "primary_mainline": "半导体"},
                ],
                "get_sector_turnover_snapshot_from_ths": lambda sector_name, target_date="", total_turnover=0: {
                    "date": target_date,
                    "sector_name": sector_name,
                    "sector_turnover": 2180.0,
                    "total_turnover": total_turnover,
                    "turnover_share_pct": 18.1,
                },
                "load_recent_sector_turnover_history": lambda target_date, current_mainline_name, lookback_days=5: [
                    {"date": "2026-04-23", "sector_name": current_mainline_name, "turnover_share_pct": 15.8},
                ],
                "build_mainline_turnover_summary": lambda **kwargs: {
                    "current_mainline": kwargs["current_mainline_history_record"]["primary_mainline"],
                    "double_mainline_summary": {
                        "cycle_mainline": "半导体",
                        "daily_attack_line": "半导体",
                        "relationship": "周期主线与当天主攻线一致",
                        "tomorrow_action": "继续围绕半导体观察承接",
                    },
                    "turnover_share_trend_rows": [
                        {
                            "date": "2026-04-24",
                            "cycle_mainline": "半导体",
                            "daily_attack_line": "半导体",
                            "mainline_turnover": "2180.00亿",
                            "market_turnover": "12834.00亿",
                            "share": "18.1%",
                            "share_change": "+2.3pct",
                            "interpretation": "主线占比继续抬升",
                        }
                    ],
                },
            },
        )

        self.assertEqual(result["data"]["current_mainline_history_record"]["primary_mainline"], "半导体")
        self.assertEqual(result["data"]["recent_mainline_history"][0]["primary_mainline"], "电力")
        self.assertEqual(result["data"]["current_sector_turnover_snapshot"]["turnover_share_pct"], 18.1)
        self.assertEqual(result["data"]["recent_sector_turnover_history"][0]["turnover_share_pct"], 15.8)
        self.assertEqual(result["data"]["mainline_turnover_summary"]["current_mainline"], "半导体")

    def test_build_replay_snapshot_contract_rederives_capital_intent_from_top_level_attack_facts(self):
        snapshot = {
            "market_research_snapshot": {
                "state_machine": {"leading_line": "半导体"},
                "observation": {},
                "mainline_turnover_summary": {
                    "current_mainline": "半导体",
                    "mainline_attack_evidence_summary": {
                        "attack_state": "confirmed_attack",
                        "primary_line": "半导体",
                        "confirmation_evidence": "半导体资金净流入靠前，涨停和高标更集中，成交占比扩张",
                    },
                },
                "lhb_capital_status": {
                    "capital_strength": "强",
                    "capital_intensity": "龙虎榜净买入集中在未知，约14.57亿；净卖出端约26.16亿",
                    "capital_direction": "未知",
                    "capital_intent": "尝试外溢或轮动",
                    "style_shift": "资金偏轮动试探",
                    "event_attribute": "龙虎榜资金行为",
                },
                "capital_conclusion": {
                    "current_capital_state": "龙虎榜资金强，方向在未知",
                    "mainline_attitude": "资金没有完全确认主线，先看是否轮动",
                    "tomorrow_action_meaning": "先观察资金是否回到主线，再决定是否给资格",
                },
            },
            "current_mainline_history_record": {"date": "2026-05-14", "primary_mainline": "半导体"},
            "current_sector_turnover_snapshot": {
                "date": "2026-05-14",
                "sector_name": "半导体",
                "sector_turnover": 4206.7,
                "total_turnover": 33880.86,
                "turnover_share_pct": 12.4,
            },
            "recent_sector_turnover_history": [
                {"date": "2026-05-13", "sector_name": "半导体", "turnover_share_pct": 10.8}
            ],
            "mainline_turnover_summary": {
                "current_mainline": "半导体",
                "mainline_attack_evidence_summary": {
                    "attack_state": "confirmed_attack",
                    "primary_line": "半导体",
                    "confirmation_evidence": "半导体资金净流入靠前，涨停和高标更集中，成交占比扩张",
                },
            },
            "sector_fund_flow": {
                "inflow": [
                    {"name": "半导体", "zljlr": 45.0, "turnover_yi": 4206.7},
                    {"name": "电力", "zljlr": 8.0, "turnover_yi": 2300.0},
                ],
                "outflow": [],
            },
            "zt_pool_by_sector": {
                "半导体": [
                    {"名称": "中船特气", "涨停统计": "4连板"},
                    {"名称": "芯片一号", "涨停统计": "首板"},
                    {"名称": "芯片二号", "涨停统计": "首板"},
                    {"名称": "芯片三号", "涨停统计": "首板"},
                    {"名称": "芯片四号", "涨停统计": "首板"},
                ]
            },
            "lhb_net_buy_top10": [
                {"name": "电力一号", "code": "000001", "sector": "电力", "net_buy_amount_yi": 14.57},
            ],
            "lhb_net_sell_top10": [
                {"name": "消费一号", "code": "000002", "sector": "消费", "net_buy_amount_yi": -26.16},
            ],
            "indices": [{"code": "sh000001"}],
            "data_status": {"主要指数": True},
            "step_status": {"主要指数获取": True},
            "total_turnover": 33880.86,
        }

        result = build_replay_snapshot_contract(
            "2026-05-14",
            refresh_sources=["noop"],
            load_data_snapshot=lambda target_date: (snapshot, ""),
            tencent_factory=lambda: _FakeTencentFinanceData([]),
            get_major_indices_from_iwencai=lambda target_date="": [],
            safe_float=lambda value: float(value or 0),
            print_fn=lambda *args, **kwargs: None,
        )

        research = result["data"]["market_research_snapshot"]
        self.assertEqual(research["capital_intent_breakdown"]["capital_consistency"], "板块攻击成立，龙虎榜未验证")
        self.assertEqual(research["capital_conclusion"]["mainline_attitude"], "板块攻击成立，龙虎榜未验证")
        self.assertEqual(research["capital_conclusion"]["tomorrow_action_meaning"], "先按板块攻击线观察，龙虎榜只作为加分，不作为主线否决")
        self.assertNotIn("资金没有完全确认主线", research["capital_conclusion"]["mainline_attitude"])

    def test_build_replay_snapshot_contract_rebuilds_stale_summary_without_attack_evidence(self):
        snapshot = {
            "market_research_snapshot": {
                "state_machine": {"leading_line": "半导体"},
                "observation": {},
                "mainline_turnover_summary": {
                    "current_mainline": "半导体",
                    "conclusion": "主线未切换，半导体仍是中心",
                },
            },
            "current_mainline_history_record": {"date": "2026-05-14", "primary_mainline": "半导体"},
            "recent_mainline_history": [{"date": "2026-05-13", "primary_mainline": "电力"}],
            "current_sector_turnover_snapshot": {
                "date": "2026-05-14",
                "sector_name": "半导体",
                "sector_turnover": 4206.7,
                "total_turnover": 33880.86,
                "turnover_share_pct": 12.4,
            },
            "recent_sector_turnover_history": [
                {"date": "2026-05-13", "sector_name": "半导体", "turnover_share_pct": 10.8}
            ],
            "mainline_turnover_summary": {
                "current_mainline": "半导体",
                "conclusion": "主线未切换，半导体仍是中心",
            },
            "sector_fund_flow": {
                "inflow": [
                    {"name": "养殖业", "zljlr": 7.59, "turnover_yi": 99.91},
                    {"name": "国有大型银行Ⅱ", "zljlr": 4.09, "turnover_yi": 99.97},
                    {"name": "化学制品", "zljlr": 3.39, "turnover_yi": 556.9},
                ],
                "outflow": [],
            },
            "zt_pool_by_sector": {
                "半导体": [{"name": "中船特气", "zt_type": "4/3"}, {"name": "晶升股份", "zt_type": "1/1"}],
                "化学制品": [
                    {"name": "和远气体", "zt_type": "4/2"},
                    {"name": "宏柏新材", "zt_type": "1/1"},
                    {"name": "红 宝 丽", "zt_type": "1/1"},
                    {"name": "晨光新材", "zt_type": "1/1"},
                    {"name": "红墙股份", "zt_type": "1/1"},
                ],
                "家居用品": [{"name": "蒙娜丽莎", "zt_type": "5/5"}, {"name": "麒盛科技", "zt_type": "1/1"}],
            },
            "indices": [{"code": "sh000001"}],
            "data_status": {"主要指数": True},
            "step_status": {"主要指数获取": True},
            "total_turnover": 33880.86,
        }

        result = build_replay_snapshot_contract(
            "2026-05-14",
            refresh_sources=["noop"],
            load_data_snapshot=lambda target_date: (snapshot, ""),
            tencent_factory=lambda: _FakeTencentFinanceData([]),
            get_major_indices_from_iwencai=lambda target_date="": [],
            safe_float=lambda value: float(value or 0),
            print_fn=lambda *args, **kwargs: None,
        )

        top_summary = result["data"]["mainline_turnover_summary"]
        research_summary = result["data"]["market_research_snapshot"]["mainline_turnover_summary"]
        self.assertEqual(top_summary["mainline_attack_evidence_summary"]["attack_state"], "chaotic_rotation")
        self.assertEqual(top_summary["current_mainline"], "")
        self.assertEqual(top_summary["mainline_capacity_regime_summary"]["primary_line"], "暂无")
        self.assertEqual(research_summary["mainline_attack_evidence_summary"]["attack_state"], "chaotic_rotation")
        self.assertEqual(research_summary["current_mainline"], "")

    def test_build_replay_snapshot_contract_refills_zero_total_turnover_from_fact_db(self):
        snapshot = {
            "current_mainline_history_record": {"date": "2026-05-13", "primary_mainline": "电力"},
            "current_sector_turnover_snapshot": {
                "date": "2026-05-13",
                "sector_name": "电力",
                "sector_turnover": 995.13,
                "total_turnover": 0.0,
                "turnover_share_pct": 0.0,
                "source_status": "success",
            },
            "mainline_turnover_summary": {
                "current_mainline": "电力",
                "turnover_share_trend_rows": [
                    {
                        "date": "2026-05-13",
                        "cycle_mainline": "电力",
                        "mainline_turnover": "995.13亿",
                        "market_turnover": "数据暂缺",
                        "share": "待累计",
                    }
                ],
            },
            "total_turnover": 0.0,
            "indices": [{"code": "sh000001"}],
            "data_status": {"主要指数": True},
            "step_status": {"主要指数获取": True},
        }

        result = build_replay_snapshot_contract(
            "2026-05-13",
            refresh_sources=["noop"],
            load_data_snapshot=lambda target_date: (snapshot, ""),
            tencent_factory=lambda: _FakeTencentFinanceData([]),
            get_major_indices_from_iwencai=lambda target_date="": [],
            safe_float=lambda value: float(value or 0),
            print_fn=lambda *args, **kwargs: None,
            helpers={
                "load_recent_mainline_history": lambda target_date, lookback_days=5: [],
                "load_recent_sector_turnover_history": lambda target_date, current_mainline_name, lookback_days=5: [],
                "get_market_total_turnover_from_fact_db": lambda target_date: 32642.12,
            },
        )

        current = result["data"]["current_sector_turnover_snapshot"]
        row = result["data"]["mainline_turnover_summary"]["turnover_share_trend_rows"][0]
        self.assertEqual(result["data"]["total_turnover"], 32642.12)
        self.assertEqual(current["total_turnover"], 32642.12)
        self.assertAlmostEqual(current["turnover_share_pct"], 3.05)
        self.assertEqual(row["market_turnover"], "32642.12亿")
        self.assertEqual(row["share"], "3.0%")

    def test_build_replay_snapshot_contract_restores_critical_tushare_facts_from_fact_db(self):
        snapshot = {
            "indices": [{"code": "sh000001"}],
            "total_turnover": 0.0,
            "turnover_data": {"total_turnover_yi": 0.0, "date": "2026-05-13"},
            "turnover_rank": [],
            "turnover_over_100b": [],
            "wind_a_alternative": {"price": 0.0, "data_source": "akshare.stock_zh_index_daily_em"},
            "data_status": {
                "两市成交额": False,
                "主要指数": True,
                "中证全指": False,
                "成交额排名": False,
                "选股通盘中异动": True,
            },
            "step_status": {
                "两市成交额获取": False,
                "主要指数获取": True,
                "中证全指获取": False,
                "成交额排名获取": False,
                "选股通盘中异动获取": True,
            },
            "module_logs": [
                {
                    "module": "domains.market_state.request",
                    "step": "request.total_turnover",
                    "status": "degraded",
                    "message": "两市成交额为空或无效",
                    "details": {"provider": "akshare.stock_zh_index_daily_em"},
                },
                {
                    "module": "domains.market_state.request",
                    "step": "request.wind_a",
                    "status": "degraded",
                    "message": "中证全指为空或无效",
                    "details": {"provider": "akshare.stock_zh_index_daily_em"},
                },
                {
                    "module": "domains.market_activity.request",
                    "step": "request.turnover_rank",
                    "status": "degraded",
                    "message": "已处理成交额排行请求",
                    "details": {"provider": "eastmoney.turnover_rank", "turnover_count": 0},
                },
                {
                    "module": "domains.monitoring.request",
                    "step": "request.xuangubao",
                    "status": "success",
                    "message": "已处理选股通异动请求",
                    "details": {
                        "provider": "xuangubao.fetch_xuangubao_data",
                        "news_count": 1,
                        "plate_count": 0,
                        "limit_up_reason_count": 0,
                    },
                },
            ],
            "xuangubao_data": {"xuangubao_news": [{"title": "今日新闻"}]},
            "request_diagnostics": {"summary": {"degraded_count": 3}},
        }

        result = build_replay_snapshot_contract(
            "2026-05-13",
            refresh_sources=["noop"],
            load_data_snapshot=lambda target_date: (snapshot, ""),
            tencent_factory=lambda: _FakeTencentFinanceData([]),
            get_major_indices_from_iwencai=lambda target_date="": [],
            safe_float=lambda value: float(value or 0),
            print_fn=lambda *args, **kwargs: None,
            helpers={
                "get_market_daily_total_from_fact_db": lambda target_date: {
                    "trade_date": target_date,
                    "total_amount_yi": 32642.123233,
                    "stock_count": 5493,
                    "source_run_id": 17,
                },
                "get_turnover_rank_from_fact_db": lambda target_date, limit=50: [
                    {
                        "rank": 1,
                        "code": "601318",
                        "name": "中国平安",
                        "turnover": 210.5,
                        "change_pct": 1.3,
                        "sector": "保险",
                        "data_source": "tushare.daily",
                        "trade_date": target_date,
                    },
                    {
                        "rank": 2,
                        "code": "300750",
                        "name": "宁德时代",
                        "turnover": 98.7,
                        "change_pct": -0.4,
                        "sector": "电池",
                        "data_source": "tushare.daily",
                        "trade_date": target_date,
                    },
                ],
                "get_wind_a_from_tushare": lambda target_date: {},
            },
        )

        data = result["data"]
        self.assertEqual(data["total_turnover"], 32642.12)
        self.assertEqual(data["turnover_data"]["total_turnover_yi"], 32642.12)
        self.assertEqual([item["code"] for item in data["turnover_rank"]], ["601318", "300750"])
        self.assertEqual(data["turnover_over_100b"][0]["code"], "601318")
        self.assertTrue(data["data_status"]["两市成交额"])
        self.assertTrue(data["data_status"]["成交额排名"])
        self.assertFalse(data["data_status"]["中证全指"])
        self.assertTrue(data["step_status"]["两市成交额获取"])
        self.assertTrue(data["step_status"]["成交额排名获取"])
        provider_by_step = {
            item["step"]: item["details"]["provider"]
            for item in data["module_logs"]
            if item.get("step") in {"request.total_turnover", "request.turnover_rank", "request.wind_a"}
        }
        self.assertEqual(provider_by_step["request.total_turnover"], "tushare.daily")
        self.assertEqual(provider_by_step["request.turnover_rank"], "tushare.daily")
        self.assertEqual(provider_by_step["request.wind_a"], "akshare.stock_zh_index_daily_em")
        degraded_steps = [item["step"] for item in data["request_diagnostics"]["degraded"]]
        self.assertEqual(degraded_steps, ["request.wind_a"])
        preflight = build_report_preflight(data, "2026-05-13")
        self.assertEqual(preflight["failures"], ["中证全指"])

    def test_build_replay_snapshot_contract_restores_wind_a_from_tushare(self):
        snapshot = {
            "indices": [{"code": "sh000001"}],
            "total_turnover": 32642.12,
            "wind_a_alternative": {"price": 0.0, "data_source": "akshare.stock_zh_index_daily_em"},
            "turnover_rank": [{"code": "601318", "data_source": "tushare.daily"}],
            "data_status": {
                "两市成交额": True,
                "主要指数": True,
                "中证全指": False,
                "成交额排名": True,
                "选股通盘中异动": True,
            },
            "step_status": {
                "两市成交额获取": True,
                "主要指数获取": True,
                "中证全指获取": False,
                "成交额排名获取": True,
                "选股通盘中异动获取": True,
            },
            "module_logs": [
                {
                    "module": "domains.market_state.request",
                    "step": "request.total_turnover",
                    "status": "success",
                    "message": "已获取两市成交额",
                    "details": {"provider": "tushare.daily", "row_count": 5493},
                },
                {
                    "module": "domains.market_state.request",
                    "step": "request.wind_a",
                    "status": "degraded",
                    "message": "中证全指为空或无效",
                    "details": {"provider": "akshare.stock_zh_index_daily_em"},
                },
                {
                    "module": "domains.market_activity.request",
                    "step": "request.turnover_rank",
                    "status": "success",
                    "message": "已处理成交额排行请求",
                    "details": {"provider": "tushare.daily", "row_count": 50},
                },
                {
                    "module": "domains.monitoring.request",
                    "step": "request.xuangubao",
                    "status": "success",
                    "message": "已处理选股通异动请求",
                    "details": {
                        "provider": "xuangubao.fetch_xuangubao_data",
                        "news_count": 1,
                        "plate_count": 0,
                        "limit_up_reason_count": 0,
                    },
                },
            ],
            "xuangubao_data": {"xuangubao_news": [{"title": "今日新闻"}]},
        }

        result = build_replay_snapshot_contract(
            "2026-05-13",
            refresh_sources=["noop"],
            load_data_snapshot=lambda target_date: (snapshot, ""),
            tencent_factory=lambda: _FakeTencentFinanceData([]),
            get_major_indices_from_iwencai=lambda target_date="": [],
            safe_float=lambda value: float(value or 0),
            print_fn=lambda *args, **kwargs: None,
            helpers={
                "get_wind_a_from_tushare": lambda target_date: {
                    "name": "中证全指",
                    "code": "000985",
                    "price": 6686.86,
                    "change_pct": 0.72,
                    "data_source": "tushare.index_daily",
                    "trade_date": target_date,
                },
            },
        )

        data = result["data"]
        self.assertEqual(data["wind_a_alternative"]["price"], 6686.86)
        self.assertTrue(data["data_status"]["中证全指"])
        self.assertTrue(data["step_status"]["中证全指获取"])
        provider_by_step = {
            item["step"]: item["details"]["provider"]
            for item in data["module_logs"]
            if item.get("step") in {"request.total_turnover", "request.turnover_rank", "request.wind_a"}
        }
        self.assertEqual(provider_by_step["request.wind_a"], "tushare.index_daily")
        preflight = build_report_preflight(data, "2026-05-13")
        self.assertEqual(preflight["status"], "success")

    def test_build_replay_report_outputs_contract_writes_mainline_turnover_reports(self):
        replay_runtime = self._load_module()
        captured = {}
        snapshot = {
            "analysis": {
                "mainline_history_record": {
                    "date": "2026-04-23",
                    "primary_mainline": "电力",
                    "leading_line": "电力",
                },
                "sector_turnover_snapshot": {
                    "date": "2026-04-23",
                    "sector_name": "电力",
                    "turnover_share_pct": 2.7,
                },
            },
            "indices": [{"code": "sh000001"}],
            "data_status": {"主要指数": True},
            "step_status": {"主要指数获取": True},
        }

        def _build_report_outputs(data, target_date, supplementary_perspective="", has_personal_positions=False, run_mode="frozen", position_report_text=""):
            captured["target_date"] = target_date
            captured["run_mode"] = run_mode
            captured["mainline"] = data["current_mainline_history_record"]["primary_mainline"]
            captured["share_pct"] = data["current_sector_turnover_snapshot"]["turnover_share_pct"]
            mainline_line = (
                "- **主线更替与占比**: 主线未切换，电力仍是中心；"
                "最近1日主线 电力；成交额占比 2.7%，节奏偏持平"
            )
            return {
                REPORT_VARIANT_FULL: "# 完整版\n" + mainline_line,
                REPORT_VARIANT_SUMMARY: "# 执行摘要\n" + mainline_line,
            }

        with TemporaryDirectory() as output_dir:
            result = replay_runtime.build_replay_report_outputs_contract(
                "2026-04-23",
                refresh_sources=["noop"],
                load_data_snapshot=lambda target_date: (snapshot, ""),
                tencent_factory=lambda: _FakeTencentFinanceData([]),
                get_major_indices_from_iwencai=lambda target_date="": [],
                safe_float=lambda value: float(value or 0),
                build_report_outputs=_build_report_outputs,
                save_report_outputs=save_report_outputs,
                output_dir=output_dir,
                print_fn=lambda *args, **kwargs: None,
            )

            full_path = Path(result["saved_paths"][REPORT_VARIANT_FULL])
            summary_path = Path(result["saved_paths"][REPORT_VARIANT_SUMMARY])

            self.assertTrue(full_path.exists())
            self.assertTrue(summary_path.exists())
            self.assertIn("主线更替与占比", full_path.read_text(encoding="utf-8"))
            self.assertIn("主线更替与占比", summary_path.read_text(encoding="utf-8"))

        self.assertTrue(result["found"])
        self.assertEqual(captured["target_date"], "2026-04-23")
        self.assertEqual(captured["run_mode"], "replay")
        self.assertEqual(captured["mainline"], "电力")
        self.assertEqual(captured["share_pct"], 2.7)
        self.assertTrue(any(log["step"] == "render.report_outputs" for log in result["module_logs"]))
        self.assertTrue(any(log["step"] == "save.report_outputs" for log in result["module_logs"]))


if __name__ == "__main__":
    unittest.main()
