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

    def test_replay_runtime_forwards_etf_refresh_helper_to_snapshot_contract(self):
        replay_runtime = self._load_module()
        etf_fetcher = lambda **kwargs: {}

        with patch(
            "replay.report_replay.build_replay_snapshot_contract",
            return_value={"found": True, "data": {"ok": True}, "target_date": "2026-05-25"},
        ) as contract_mock:
            replay_runtime.replay_from_snapshot(
                "2026-05-25",
                helpers={
                    "load_data_snapshot": lambda target_date: ({"snapshot": target_date}, ""),
                    "TencentFinanceData": lambda: _FakeTencentFinanceData([]),
                    "get_major_indices_from_iwencai": lambda target_date="": [],
                    "safe_float": lambda value: float(value or 0),
                    "get_etf_turnover_series_from_sina": etf_fetcher,
                },
            )

        self.assertIs(
            contract_mock.call_args.kwargs["helpers"]["get_etf_turnover_series_from_sina"],
            etf_fetcher,
        )

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

    def test_build_replay_snapshot_contract_backfills_etf_turnover_series_when_missing(self):
        snapshot = {
            "indices": [{"code": "sh000001"}],
            "data_status": {"主要指数": True},
            "step_status": {"主要指数获取": True},
            "timer_summary": {"steps": [["旧步骤", 1.0, 1.0]]},
            "module_logs": [
                {
                    "module": "input.runtime",
                    "step": "request.etf_turnover_series",
                    "status": "degraded",
                    "message": "ETF两市成交额趋势缺失",
                    "details": {"provider": "snapshot.missing", "row_count": 0},
                }
            ],
        }
        etf_calls = []

        result = build_replay_snapshot_contract(
            "2026-05-25",
            refresh_sources=["noop"],
            load_data_snapshot=lambda target_date: (snapshot, ""),
            tencent_factory=lambda: _FakeTencentFinanceData([]),
            get_major_indices_from_iwencai=lambda target_date="": [],
            safe_float=lambda value: float(value or 0),
            print_fn=lambda *args, **kwargs: None,
            helpers={
                "get_etf_turnover_series_from_sina": lambda *, target_date, window_days=25: etf_calls.append(
                    (target_date, window_days)
                )
                or {
                    "source": "sina.etf.daily_amount",
                    "rows": [
                        {
                            "trade_date": f"2026-05-{day:02d}",
                            "etf_turnover_yi": 4400 + day,
                            "covered_etf_count": 1500 + day,
                        }
                        for day in range(1, 26)
                    ],
                    "usable_etf_count": 1530,
                    "empty_etf_count": 3,
                },
            },
        )

        data = result["data"]
        self.assertEqual(etf_calls, [("2026-05-25", 25)])
        self.assertEqual(data["etf_turnover_series"]["rows"][-1]["etf_turnover_yi"], 4425)
        self.assertTrue(data["data_status"]["ETF两市成交额趋势"])
        self.assertTrue(data["step_status"]["ETF两市成交额趋势获取"])
        by_step = {item["step"]: item for item in data["module_logs"]}
        self.assertEqual(by_step["request.etf_turnover_series"]["status"], "success")
        self.assertEqual(by_step["request.etf_turnover_series"]["details"]["provider"], "sina.etf.daily_amount")
        self.assertEqual(by_step["request.etf_turnover_series"]["details"]["row_count"], 25)
        self.assertIn("ETF两市成交额趋势获取", [row[0] for row in data["timer_summary"]["steps"]])

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
        self.assertEqual(data["lianban_data"][0]["code"], "601991")
        self.assertEqual(data["lianban_data"][0]["lianban_days"], 1)
        self.assertEqual(data["lianban_data"][0]["sector"], "电力")
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
        self.assertEqual(by_step["request.integrated_hot_rank"]["details"]["provider"], "primary_hot_rank.derived")
        self.assertFalse(by_step["request.integrated_hot_rank"]["details"]["fallback_used"])
        self.assertEqual(by_step["request.xuangubao"]["details"]["plate_count"], 1)
        self.assertEqual(by_step["request.xuangubao"]["details"]["diagnostic_note"], "newsflash=非法的token")
        self.assertEqual(by_step["request.wanzhu_top10"]["details"]["stock_count"], 1)
        self.assertEqual(by_step["request.lianban_snapshot"]["status"], "success")
        self.assertIn("顽主杯热门前十获取", [row[0] for row in data["timer_summary"]["steps"]])
        self.assertEqual(xgb_calls, ["2026-05-18"])

    def test_build_replay_snapshot_contract_backfills_concept_fund_flow_from_hot_plates(self):
        snapshot = {
            "hot_plates": [
                {"name": "半导体设备", "code": "884229", "rank": 1},
                {"name": "汽车零部件", "code": "881126", "rank": 2},
            ],
            "concept_fund_flow": {"rows": [], "inflow": [], "outflow": []},
            "indices": [{"code": "sh000001"}],
            "data_status": {"概念资金流向": False, "主要指数": True},
            "step_status": {"概念资金流向获取": False, "主要指数获取": True},
            "module_logs": [
                {
                    "module": "domains.market_activity.request",
                    "step": "request.concept_fund_flow",
                    "status": "degraded",
                    "message": "概念板块资金流为空",
                    "details": {"provider": "tushare.ths_member+tushare.moneyflow", "row_count": 0},
                }
            ],
            "timer_summary": {"steps": [["步骤7.5: 概念资金流向获取(空)", 1.0, 1.0]]},
        }
        concept_calls = []

        result = build_replay_snapshot_contract(
            "2026-05-21",
            refresh_sources=["noop"],
            load_data_snapshot=lambda target_date: (snapshot, ""),
            tencent_factory=lambda: _FakeTencentFinanceData([]),
            get_major_indices_from_iwencai=lambda target_date="": [],
            safe_float=lambda value: float(value or 0),
            print_fn=lambda *args, **kwargs: None,
            helpers={
                "get_hot_concept_fund_flow_from_tushare": lambda target_date=None, hot_plates=None, limit=20: concept_calls.append(
                    (target_date, tuple(item.get("code") for item in hot_plates or []), limit)
                )
                or {
                    "provider": "tushare.ths_member+tushare.moneyflow",
                    "rows": [
                        {
                            "name": "半导体设备",
                            "code": "884229.TI",
                            "net_inflow": -14.25,
                            "data_source": "tushare.ths_member+tushare.moneyflow",
                        }
                    ],
                    "inflow": [
                        {
                            "name": "半导体设备",
                            "code": "884229.TI",
                            "net_inflow": -14.25,
                        }
                    ],
                    "outflow": [
                        {
                            "name": "半导体设备",
                            "code": "884229.TI",
                            "net_inflow": -14.25,
                        }
                    ],
                },
            },
        )

        data = result["data"]
        self.assertEqual(concept_calls, [("2026-05-21", ("884229", "881126"), 20)])
        self.assertTrue(data["data_status"]["概念资金流向"])
        self.assertTrue(data["step_status"]["概念资金流向获取"])
        self.assertEqual(data["concept_fund_flow"]["rows"][0]["code"], "884229.TI")
        by_step = {item["step"]: item for item in data["module_logs"]}
        self.assertEqual(by_step["request.concept_fund_flow"]["status"], "success")
        self.assertEqual(by_step["request.concept_fund_flow"]["details"]["row_count"], 1)
        self.assertIn("概念资金流向获取", [row[0] for row in data["timer_summary"]["steps"]])

    def test_build_replay_snapshot_contract_uses_existing_replay_concept_fund_flow_when_official_is_empty(self):
        official_snapshot = {
            "concept_fund_flow": {"rows": [], "inflow": [], "outflow": []},
            "indices": [{"code": "sh000001"}],
            "data_status": {"概念资金流向": False, "主要指数": True},
            "step_status": {"概念资金流向获取": False, "主要指数获取": True},
            "module_logs": [
                {
                    "module": "domains.market_activity.request",
                    "step": "request.concept_fund_flow",
                    "status": "degraded",
                    "message": "概念板块资金流为空",
                    "details": {"provider": "tushare.ths_member+tushare.moneyflow", "row_count": 0},
                }
            ],
            "timer_summary": {"steps": [["步骤7.5: 概念资金流向获取(空)", 1.0, 1.0]]},
        }
        replay_snapshot = {
            "concept_fund_flow": {
                "provider": "tushare.ths_member+tushare.moneyflow",
                "rows": [
                    {
                        "name": "半导体设备",
                        "code": "884229.TI",
                        "net_inflow": -14.25,
                    }
                ],
                "inflow": [{"name": "半导体设备", "code": "884229.TI", "net_inflow": -14.25}],
                "outflow": [],
            },
            "data_status": {"概念资金流向": True},
            "step_status": {"概念资金流向获取": True},
        }

        result = build_replay_snapshot_contract(
            "2026-05-21",
            refresh_sources=["noop"],
            load_data_snapshot=lambda target_date: (official_snapshot, ""),
            tencent_factory=lambda: _FakeTencentFinanceData([]),
            get_major_indices_from_iwencai=lambda target_date="": [],
            safe_float=lambda value: float(value or 0),
            print_fn=lambda *args, **kwargs: None,
            helpers={
                "load_replay_snapshot_data": lambda target_date: replay_snapshot,
                "get_hot_concept_fund_flow_from_tushare": lambda **kwargs: self.fail(
                    "existing replay concept fund flow should be used before live refresh"
                ),
            },
        )

        data = result["data"]
        self.assertTrue(data["data_status"]["概念资金流向"])
        self.assertTrue(data["step_status"]["概念资金流向获取"])
        self.assertEqual(data["concept_fund_flow"]["rows"][0]["code"], "884229.TI")
        by_step = {item["step"]: item for item in data["module_logs"]}
        self.assertEqual(by_step["request.concept_fund_flow"]["status"], "success")
        self.assertEqual(by_step["request.concept_fund_flow"]["details"]["provider"], "replay.concept_fund_flow")
        self.assertEqual(by_step["request.concept_fund_flow"]["details"]["row_count"], 1)

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

    def test_build_replay_snapshot_contract_keeps_existing_xuangubao_news_when_refresh_has_no_news(self):
        snapshot = {
            "hot_rank_top30": [{"rank": 1, "code": "601991", "name": "大唐发电"}],
            "integrated_hot_list": [{"rank": 1, "code": "601991", "name": "大唐发电"}],
            "xuangubao_data": {
                "xuangubao_news": [{"title": "旧快照新闻"}],
                "xuangubao_plates": [{"name": "国产芯片"}],
                "xuangubao_limit_up_reasons": [{"symbol": "600676.SS"}],
                "diagnostics": {},
            },
            "wanzhu_top10": [{"rank": 1, "code": "601991", "name": "大唐发电"}],
            "lianban_data": [],
            "indices": [{"code": "sh000001"}],
            "data_status": {
                "整合热榜": True,
                "选股通盘中异动": False,
                "顽主杯热门前十": True,
            },
            "step_status": {
                "整合热榜获取": True,
                "选股通盘中异动获取": False,
                "顽主杯热门前十获取": True,
                "连板梯队提取": True,
                "主要指数获取": True,
            },
            "module_logs": [
                {
                    "module": "domains.monitoring.request",
                    "step": "request.xuangubao",
                    "status": "degraded",
                    "message": "旧状态失败",
                    "details": {"provider": "xuangubao.fetch_xuangubao_data", "news_count": 1},
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
                    "xuangubao_news": [],
                    "xuangubao_plates": [{"name": "国产芯片"}, {"name": "光通信"}],
                    "xuangubao_limit_up_reasons": [{"symbol": "600676.SS"}],
                    "diagnostics": {"newsflash": "非法的token"},
                }
            },
        )

        data = result["data"]
        self.assertEqual(xgb_calls, ["2026-05-18"])
        self.assertEqual(data["xuangubao_data"]["xuangubao_news"], [{"title": "旧快照新闻"}])
        self.assertTrue(data["data_status"]["选股通盘中异动"])
        self.assertTrue(data["step_status"]["选股通盘中异动获取"])
        xgb_log = next(log for log in data["module_logs"] if log.get("step") == "request.xuangubao")
        self.assertEqual(xgb_log["status"], "success")
        self.assertEqual(xgb_log["details"]["news_count"], 1)

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
        sector_turnover_calls = []
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
                "load_recent_sector_turnover_history": lambda target_date, current_mainline_name, lookback_days=5: sector_turnover_calls.append(
                    (target_date, current_mainline_name, lookback_days)
                )
                or [
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
        self.assertEqual(result["data"]["recent_sector_turnover_history"][0]["turnover_share_pct"], 0.0)
        self.assertEqual(result["data"]["recent_sector_turnover_history"][1]["turnover_share_pct"], 15.8)
        self.assertEqual(result["data"]["mainline_turnover_summary"]["current_mainline"], "半导体")
        self.assertEqual(
            sector_turnover_calls,
            [("2026-04-24", "电力", 25), ("2026-04-24", "半导体", 25)],
        )

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

    def test_build_replay_snapshot_contract_rebuilds_switch_summary_when_current_record_is_countertrend_attack(self):
        snapshot = {
            "market_research_snapshot": {
                "state_machine": {"leading_line": "半导体"},
                "observation": {"turnover": 35072.8},
                "mainline_turnover_summary": {
                    "current_mainline": "人形机器人",
                    "previous_mainline": "半导体",
                    "share_trend_label": "切换",
                    "conclusion": "主线切换为人形机器人，旧主线半导体退出中心",
                    "data_text": "最近3日主线 电力 -> 半导体 -> 人形机器人；成交额占比 2.3% -> 13.6% -> 2.5%，节奏偏切换",
                    "action_text": "只围绕新主线人形机器人重新收缩，不对旧主线做回流预判",
                    "mainline_attack_evidence_summary": {
                        "attack_state": "confirmed_attack",
                        "primary_line": "人形机器人",
                        "confirmation_evidence": "人形机器人资金净流入靠前，涨停更集中",
                    },
                    "turnover_share_trend_rows": [
                        {"date": "2026-05-20", "cycle_mainline": "半导体", "daily_attack_line": "半导体"},
                        {"date": "2026-05-21", "cycle_mainline": "人形机器人", "daily_attack_line": "人形机器人"},
                    ],
                },
            },
            "current_mainline_history_record": {
                "date": "2026-05-21",
                "primary_mainline": "人形机器人",
                "leading_line": "人形机器人",
                "rotation_label": "逆势攻击",
                "rotation_summary": "人形机器人资金净流入靠前，涨停更集中",
            },
            "recent_mainline_history": [
                {"date": "2026-05-20", "primary_mainline": "半导体", "daily_attack_line": "半导体"},
            ],
            "current_sector_turnover_snapshot": {
                "date": "2026-05-21",
                "sector_name": "人形机器人",
                "sector_turnover": 880.0,
                "total_turnover": 35072.8,
                "turnover_share_pct": 2.51,
            },
            "recent_sector_turnover_history": [
                {
                    "date": "2026-05-20",
                    "sector_name": "半导体",
                    "cycle_mainline": "半导体",
                    "daily_attack_line": "半导体",
                    "sector_turnover": 4050.0,
                    "total_turnover": 29764.59,
                    "turnover_share_pct": 13.61,
                }
            ],
            "mainline_turnover_summary": {
                "current_mainline": "人形机器人",
                "previous_mainline": "半导体",
                "share_trend_label": "切换",
                "conclusion": "主线切换为人形机器人，旧主线半导体退出中心",
                "data_text": "最近3日主线 电力 -> 半导体 -> 人形机器人；成交额占比 2.3% -> 13.6% -> 2.5%，节奏偏切换",
                "action_text": "只围绕新主线人形机器人重新收缩，不对旧主线做回流预判",
                "mainline_attack_evidence_summary": {
                    "attack_state": "confirmed_attack",
                    "primary_line": "人形机器人",
                    "confirmation_evidence": "人形机器人资金净流入靠前，涨停更集中",
                },
                "turnover_share_trend_rows": [
                    {"date": "2026-05-20", "cycle_mainline": "半导体", "daily_attack_line": "半导体"},
                    {"date": "2026-05-21", "cycle_mainline": "人形机器人", "daily_attack_line": "人形机器人"},
                ],
            },
            "sector_fund_flow": {
                "inflow": [
                    {"name": "汽车零部件", "zljlr": 30.0, "turnover_yi": 778.0},
                    {"name": "电机", "zljlr": 9.0, "turnover_yi": 102.0},
                ],
                "outflow": [],
            },
            "zt_pool_by_sector": {
                "汽车零部件": [
                    {"name": "三花智控", "zt_type": "1/1"},
                    {"name": "拓普集团", "zt_type": "1/1"},
                    {"name": "五洲新春", "zt_type": "1/1"},
                ],
                "电机": [
                    {"name": "鸣志电器", "zt_type": "1/1"},
                    {"name": "昊志机电", "zt_type": "1/1"},
                ],
            },
            "indices": [{"code": "sh000001"}],
            "data_status": {"主要指数": True},
            "step_status": {"主要指数获取": True},
            "total_turnover": 35072.8,
        }

        result = build_replay_snapshot_contract(
            "2026-05-21",
            refresh_sources=["noop"],
            load_data_snapshot=lambda target_date: (snapshot, ""),
            tencent_factory=lambda: _FakeTencentFinanceData([]),
            get_major_indices_from_iwencai=lambda target_date="": [],
            safe_float=lambda value: float(value or 0),
            print_fn=lambda *args, **kwargs: None,
            helpers={
                "load_recent_sector_turnover_history": lambda target_date, sector_name, lookback_days=25: [],
                "mainline_turnover_summary_conflicts_with_current_record": lambda summary, current_record: (
                    "逆势攻击" in str((current_record or {}).get("rotation_label") or "")
                    and "主线切换" in str((summary or {}).get("conclusion") or "")
                ),
            },
        )

        top_summary = result["data"]["mainline_turnover_summary"]
        research_summary = result["data"]["market_research_snapshot"]["mainline_turnover_summary"]
        self.assertEqual(top_summary["share_trend_label"], "逆势试攻")
        self.assertIn("观察主攻线", top_summary["conclusion"])
        self.assertNotIn("主线切换为人形机器人", top_summary["conclusion"])
        self.assertEqual(top_summary["double_mainline_summary"]["cycle_mainline"], "半导体")
        self.assertEqual(top_summary["double_mainline_summary"]["daily_attack_line"], "人形机器人")
        self.assertEqual(research_summary["share_trend_label"], "逆势试攻")
        self.assertNotIn("主线切换为人形机器人", research_summary["conclusion"])

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

    def test_build_replay_snapshot_contract_refreshes_stale_new_high_trend_rows(self):
        snapshot = {
            "new_high_feedback": {
                "available": True,
                "new_high_count": 169,
                "all_a_share_pct": 3.38,
                "trend_rows": [
                    {
                        "trade_date": "2026-05-20",
                        "new_high_count": 169,
                        "all_a_share_pct": 3.38,
                        "change_text": "待累计",
                        "leading_sectors": "半导体、元器件、专用机械",
                    }
                ],
            },
            "indices": [{"code": "sh000001"}],
            "data_status": {"主要指数": True},
            "step_status": {"主要指数获取": True},
        }
        refreshed_rows = [
            {
                "trade_date": f"2026-04-{day:02d}",
                "new_high_count": 80 + index,
                "all_a_share_pct": 1.6 + index * 0.02,
                "change_text": "+1",
                "leading_sectors": "电力",
            }
            for index, day in enumerate(range(13, 31))
        ] + [
            {
                "trade_date": f"2026-05-{day:02d}",
                "new_high_count": 120 + index,
                "all_a_share_pct": 2.4 + index * 0.03,
                "change_text": "+2",
                "leading_sectors": "半导体",
            }
            for index, day in enumerate(range(1, 7))
        ] + [
            {
                "trade_date": "2026-05-20",
                "new_high_count": 169,
                "all_a_share_pct": 3.38,
                "change_text": "+5",
                "leading_sectors": "半导体、元器件、专用机械",
            }
        ]

        result = build_replay_snapshot_contract(
            "2026-05-20",
            refresh_sources=["noop"],
            load_data_snapshot=lambda target_date: (snapshot, ""),
            tencent_factory=lambda: _FakeTencentFinanceData([]),
            get_major_indices_from_iwencai=lambda target_date="": [],
            safe_float=lambda value: float(value or 0),
            print_fn=lambda *args, **kwargs: None,
            helpers={
                "get_new_high_feedback_from_tushare": lambda target_date: {
                    "available": True,
                    "new_high_count": 169,
                    "all_a_share_pct": 3.38,
                    "trend_rows": refreshed_rows,
                },
            },
        )

        feedback = result["data"]["new_high_feedback"]
        self.assertEqual(len(feedback["trend_rows"]), 25)
        self.assertEqual(feedback["trend_rows"][0]["trade_date"], "2026-04-13")
        self.assertEqual(feedback["trend_rows"][-1]["trade_date"], "2026-05-20")
        self.assertTrue(result["data"]["data_status"]["创新高趋势反馈"])
        self.assertTrue(result["data"]["step_status"]["创新高趋势反馈获取"])

    def test_build_replay_snapshot_contract_keeps_snapshot_when_new_high_refresh_fails(self):
        snapshot = {
            "new_high_feedback": {
                "available": True,
                "new_high_count": 169,
                "all_a_share_pct": 3.38,
                "trend_rows": [
                    {
                        "trade_date": "2026-05-20",
                        "new_high_count": 169,
                        "all_a_share_pct": 3.38,
                        "change_text": "待累计",
                        "leading_sectors": "半导体、元器件、专用机械",
                    }
                ],
            },
            "indices": [{"code": "sh000001"}],
            "data_status": {"主要指数": True},
            "step_status": {"主要指数获取": True},
            "module_logs": [],
        }

        def _raise_timeout(target_date=None):
            raise TimeoutError("proxy timeout")

        result = build_replay_snapshot_contract(
            "2026-05-20",
            refresh_sources=["noop"],
            load_data_snapshot=lambda target_date: (snapshot, ""),
            tencent_factory=lambda: _FakeTencentFinanceData([]),
            get_major_indices_from_iwencai=lambda target_date="": [],
            safe_float=lambda value: float(value or 0),
            print_fn=lambda *args, **kwargs: None,
            helpers={
                "load_replay_snapshot_data": lambda target_date: None,
                "get_new_high_feedback_from_tushare": _raise_timeout,
            },
        )

        feedback = result["data"]["new_high_feedback"]
        self.assertEqual(feedback["new_high_count"], 169)
        self.assertEqual(feedback["trend_rows"][0]["trade_date"], "2026-05-20")
        self.assertFalse(result["data"]["step_status"]["创新高趋势反馈获取"])
        self.assertEqual(
            [
                item["status"]
                for item in result["data"]["module_logs"]
                if item.get("step") == "request.new_high_feedback"
            ],
            ["degraded"],
        )

    def test_build_replay_snapshot_contract_uses_existing_replay_new_high_when_official_is_short(self):
        official_snapshot = {
            "new_high_feedback": {
                "available": True,
                "new_high_count": 169,
                "all_a_share_pct": 3.38,
                "trend_rows": [
                    {
                        "trade_date": "2026-05-20",
                        "new_high_count": 169,
                        "all_a_share_pct": 3.38,
                        "change_text": "待累计",
                        "leading_sectors": "半导体、元器件、专用机械",
                    }
                ],
            },
            "indices": [{"code": "sh000001"}],
            "data_status": {"主要指数": True},
            "step_status": {"主要指数获取": True},
        }
        replay_rows = [
            {
                "trade_date": f"2026-05-{day:02d}",
                "new_high_count": 120 + day,
                "all_a_share_pct": 2.4 + day / 100,
                "change_text": "+1",
                "leading_sectors": "半导体",
            }
            for day in range(1, 26)
        ]
        replay_rows[-1]["trade_date"] = "2026-05-20"
        replay_snapshot = {
            "new_high_feedback": {
                "available": True,
                "new_high_count": 169,
                "all_a_share_pct": 3.38,
                "trend_rows": replay_rows,
            }
        }

        result = build_replay_snapshot_contract(
            "2026-05-20",
            refresh_sources=["noop"],
            load_data_snapshot=lambda target_date: (official_snapshot, ""),
            tencent_factory=lambda: _FakeTencentFinanceData([]),
            get_major_indices_from_iwencai=lambda target_date="": [],
            safe_float=lambda value: float(value or 0),
            print_fn=lambda *args, **kwargs: None,
            helpers={
                "load_replay_snapshot_data": lambda target_date: replay_snapshot,
                "get_new_high_feedback_from_tushare": lambda target_date: (_ for _ in ()).throw(TimeoutError("proxy timeout")),
            },
        )

        feedback = result["data"]["new_high_feedback"]
        self.assertEqual(len(feedback["trend_rows"]), 25)
        self.assertEqual(feedback["trend_rows"][-1]["trade_date"], "2026-05-20")
        self.assertTrue(result["data"]["data_status"]["创新高趋势反馈"])
        self.assertTrue(result["data"]["step_status"]["创新高趋势反馈获取"])

    def test_build_replay_snapshot_contract_refreshes_new_high_when_fact_row_differs(self):
        stale_rows = [
            {
                "trade_date": f"2026-05-{day:02d}",
                "new_high_count": 100 + day,
                "all_a_share_pct": 2.0,
                "change_text": "+1",
                "leading_sectors": "半导体",
            }
            for day in range(1, 26)
        ]
        stale_rows[-1] = {
            "trade_date": "2026-05-21",
            "new_high_count": 629,
            "all_a_share_pct": 11.43,
            "change_text": "+460",
            "leading_sectors": "元器件、半导体、专用机械",
        }
        official_snapshot = {
            "new_high_feedback": {
                "available": True,
                "new_high_count": 629,
                "all_a_share_pct": 11.43,
                "trend_rows": stale_rows,
            },
            "indices": [{"code": "sh000001"}],
            "data_status": {"主要指数": True},
            "step_status": {"主要指数获取": True},
        }
        fresh_rows = list(stale_rows)
        fresh_rows[-1] = {
            "trade_date": "2026-05-21",
            "new_high_count": 267,
            "all_a_share_pct": 4.85,
            "change_text": "+98",
            "leading_sectors": "半导体、元器件、专用机械",
        }

        result = build_replay_snapshot_contract(
            "2026-05-21",
            refresh_sources=["noop"],
            load_data_snapshot=lambda target_date: (official_snapshot, ""),
            tencent_factory=lambda: _FakeTencentFinanceData([]),
            get_major_indices_from_iwencai=lambda target_date="": [],
            safe_float=lambda value: float(value or 0),
            print_fn=lambda *args, **kwargs: None,
            helpers={
                "query_new_high_feedback_series": lambda end_date, window_days=25: [
                    {
                        "trade_date": "2026-05-21",
                        "new_high_count": 267,
                        "all_a_share_pct": 4.85,
                        "leading_sectors": "半导体、元器件、专用机械",
                    }
                ],
                "get_new_high_feedback_from_tushare": lambda target_date: {
                    "available": True,
                    "new_high_count": 267,
                    "all_a_share_pct": 4.85,
                    "leading_sectors": "半导体、元器件、专用机械",
                    "trend_rows": fresh_rows,
                },
            },
        )

        feedback = result["data"]["new_high_feedback"]
        self.assertEqual(feedback["new_high_count"], 267)
        self.assertEqual(feedback["all_a_share_pct"], 4.85)
        self.assertEqual(feedback["trend_rows"][-1]["new_high_count"], 267)

    def test_build_replay_snapshot_contract_backfills_missing_price_band_style_series(self):
        snapshot = {
            "indices": [{"code": "sh000001"}],
            "data_status": {"主要指数": True},
            "step_status": {"主要指数获取": True},
            "module_logs": [],
        }

        result = build_replay_snapshot_contract(
            "2026-05-20",
            refresh_sources=["noop"],
            load_data_snapshot=lambda target_date: (snapshot, ""),
            tencent_factory=lambda: _FakeTencentFinanceData([]),
            get_major_indices_from_iwencai=lambda target_date="": [],
            safe_float=lambda value: float(value or 0),
            print_fn=lambda *args, **kwargs: None,
            helpers={
                "get_price_band_style_series_from_tushare": lambda target_date: {
                    "available": True,
                    "source": "storage.price_band_style_daily",
                    "rows": [
                        {"trade_date": "2026-05-19", "high_price_pct": 0.5, "low_price_pct": 0.1},
                        {"trade_date": "2026-05-20", "high_price_pct": 1.2, "low_price_pct": -0.4},
                    ],
                },
                "get_wind_a_from_tushare": lambda target_date: {},
            },
        )

        self.assertEqual(result["data"]["price_band_style_series"]["rows"][-1]["trade_date"], "2026-05-20")
        self.assertTrue(result["data"]["data_status"]["价格带风格趋势"])
        self.assertTrue(result["data"]["step_status"]["价格带风格趋势获取"])
        by_step = {item.get("step"): item for item in result["data"].get("module_logs", [])}
        self.assertEqual(by_step["request.price_band_style_series"]["details"]["provider"], "storage.price_band_style_daily")

    def test_build_replay_snapshot_contract_rebuilds_mainline_turnover_when_history_labels_drift(self):
        snapshot = {
            "current_mainline_history_record": {"date": "2026-05-20", "primary_mainline": "半导体"},
            "recent_mainline_history": [
                {"date": "2026-05-18", "primary_mainline": "电力", "daily_attack_line": "电力"},
                {"date": "2026-05-19", "primary_mainline": "电力", "daily_attack_line": "电力"},
            ],
            "current_sector_turnover_snapshot": {
                "date": "2026-05-20",
                "sector_name": "半导体",
                "sector_turnover": 4050.0,
                "total_turnover": 29764.59,
                "turnover_share_pct": 13.61,
            },
            "recent_sector_turnover_history": [
                {"date": "2026-05-18", "sector_name": "半导体", "turnover_share_pct": 11.8},
                {"date": "2026-05-19", "sector_name": "半导体", "turnover_share_pct": 11.8},
            ],
            "mainline_turnover_summary": {
                "current_mainline": "半导体",
                "turnover_share_trend_rows": [
                    {"date": "2026-05-18", "cycle_mainline": "半导体", "daily_attack_line": "半导体"},
                    {"date": "2026-05-19", "cycle_mainline": "半导体", "daily_attack_line": "半导体"},
                    {"date": "2026-05-20", "cycle_mainline": "半导体", "daily_attack_line": "半导体"},
                ],
            },
            "market_research_snapshot": {
                "observation": {},
                "mainline_turnover_summary": {
                    "current_mainline": "半导体",
                    "turnover_share_trend_rows": [
                        {"date": "2026-05-18", "cycle_mainline": "半导体", "daily_attack_line": "半导体"},
                    ],
                },
            },
            "indices": [{"code": "sh000001"}],
            "data_status": {"主要指数": True},
            "step_status": {"主要指数获取": True},
            "total_turnover": 29764.59,
        }

        result = build_replay_snapshot_contract(
            "2026-05-20",
            refresh_sources=["noop"],
            load_data_snapshot=lambda target_date: (snapshot, ""),
            tencent_factory=lambda: _FakeTencentFinanceData([]),
            get_major_indices_from_iwencai=lambda target_date="": [],
            safe_float=lambda value: float(value or 0),
            print_fn=lambda *args, **kwargs: None,
            helpers={
                "load_recent_sector_turnover_history": lambda target_date, sector_name, lookback_days=25: {
                    "电力": [
                        {
                            "date": "2026-05-18",
                            "sector_name": "电力",
                            "sector_turnover": 2800.0,
                            "total_turnover": 29170.74,
                            "turnover_share_pct": 9.6,
                        },
                        {
                            "date": "2026-05-19",
                            "sector_name": "电力",
                            "sector_turnover": 2700.0,
                            "total_turnover": 29089.77,
                            "turnover_share_pct": 9.3,
                        },
                    ],
                    "半导体": [
                        {
                            "date": "2026-05-20",
                            "sector_name": "半导体",
                            "sector_turnover": 4050.0,
                            "total_turnover": 29764.59,
                            "turnover_share_pct": 13.61,
                        }
                    ],
                }.get(sector_name, []),
            },
        )

        rows = result["data"]["mainline_turnover_summary"]["turnover_share_trend_rows"]
        by_date = {row["date"]: row for row in rows}
        self.assertEqual(by_date["2026-05-18"]["cycle_mainline"], "电力")
        self.assertEqual(by_date["2026-05-19"]["cycle_mainline"], "电力")
        self.assertEqual(by_date["2026-05-20"]["cycle_mainline"], "半导体")
        research_rows = result["data"]["market_research_snapshot"]["mainline_turnover_summary"]["turnover_share_trend_rows"]
        self.assertEqual({row["date"]: row for row in research_rows}["2026-05-18"]["cycle_mainline"], "电力")

    def test_build_replay_snapshot_contract_keeps_25_mainline_turnover_rows_with_placeholders(self):
        recent_mainline_history = [
            {"date": f"2026-04-{day:02d}", "primary_mainline": "电力", "daily_attack_line": "电力"}
            for day in range(1, 25)
        ]
        snapshot = {
            "current_mainline_history_record": {"date": "2026-05-20", "primary_mainline": "半导体"},
            "recent_mainline_history": recent_mainline_history,
            "current_sector_turnover_snapshot": {
                "date": "2026-05-20",
                "sector_name": "半导体",
                "sector_turnover": 4050.0,
                "total_turnover": 29764.59,
                "turnover_share_pct": 13.61,
            },
            "recent_sector_turnover_history": [
                {
                    "date": "2026-04-01",
                    "sector_name": "电力",
                    "cycle_mainline": "电力",
                    "daily_attack_line": "电力",
                    "sector_turnover": 1000.0,
                    "total_turnover": 20000.0,
                    "turnover_share_pct": 5.0,
                }
            ],
            "mainline_turnover_summary": {
                "current_mainline": "半导体",
                "turnover_share_trend_rows": [
                    {"date": "2026-05-20", "cycle_mainline": "半导体", "daily_attack_line": "半导体"},
                ],
            },
            "indices": [{"code": "sh000001"}],
            "data_status": {"主要指数": True},
            "step_status": {"主要指数获取": True},
            "total_turnover": 29764.59,
        }

        result = build_replay_snapshot_contract(
            "2026-05-20",
            refresh_sources=["noop"],
            load_data_snapshot=lambda target_date: (snapshot, ""),
            tencent_factory=lambda: _FakeTencentFinanceData([]),
            get_major_indices_from_iwencai=lambda target_date="": [],
            safe_float=lambda value: float(value or 0),
            print_fn=lambda *args, **kwargs: None,
            helpers={
                "load_recent_sector_turnover_history": lambda target_date, sector_name, lookback_days=25: [],
            },
        )

        rows = result["data"]["mainline_turnover_summary"]["turnover_share_trend_rows"]
        self.assertEqual(len(rows), 25)
        self.assertEqual(rows[0]["date"], "2026-04-01")
        self.assertEqual(rows[-1]["date"], "2026-05-20")
        self.assertEqual(rows[1]["cycle_mainline"], "电力")
        self.assertEqual(rows[1]["mainline_turnover"], "数据暂缺")
        self.assertIn("近25个交易日主线成交额占比趋势", result["data"]["mainline_turnover_summary"]["turnover_share_trend_summary"])

    def test_build_replay_snapshot_contract_rebuilds_short_mainline_turnover_summary(self):
        recent_mainline_history = [
            {"date": f"2026-04-{day:02d}", "primary_mainline": "电力", "daily_attack_line": "电力"}
            for day in range(1, 25)
        ]
        snapshot = {
            "current_mainline_history_record": {"date": "2026-05-20", "primary_mainline": "半导体"},
            "recent_mainline_history": recent_mainline_history,
            "current_sector_turnover_snapshot": {
                "date": "2026-05-20",
                "sector_name": "半导体",
                "sector_turnover": 4050.0,
                "total_turnover": 29764.59,
                "turnover_share_pct": 13.61,
            },
            "mainline_turnover_summary": {
                "current_mainline": "半导体",
                "turnover_share_trend_rows": [
                    {"date": "2026-05-20", "cycle_mainline": "半导体", "daily_attack_line": "半导体"},
                ],
            },
            "indices": [{"code": "sh000001"}],
            "data_status": {"主要指数": True},
            "step_status": {"主要指数获取": True},
            "total_turnover": 29764.59,
        }

        result = build_replay_snapshot_contract(
            "2026-05-20",
            refresh_sources=["noop"],
            load_data_snapshot=lambda target_date: (snapshot, ""),
            tencent_factory=lambda: _FakeTencentFinanceData([]),
            get_major_indices_from_iwencai=lambda target_date="": [],
            safe_float=lambda value: float(value or 0),
            print_fn=lambda *args, **kwargs: None,
            helpers={
                "load_recent_sector_turnover_history": lambda target_date, sector_name, lookback_days=25: [],
            },
        )

        rows = result["data"]["mainline_turnover_summary"]["turnover_share_trend_rows"]
        self.assertEqual(len(rows), 25)
        self.assertEqual(rows[0]["date"], "2026-04-01")
        self.assertEqual(rows[-1]["date"], "2026-05-20")

    def test_build_replay_snapshot_contract_reloads_short_recent_mainline_history(self):
        short_history = [
            {"date": "2026-05-18", "primary_mainline": "电力", "daily_attack_line": "电力"},
            {"date": "2026-05-19", "primary_mainline": "电力", "daily_attack_line": "电力"},
        ]
        full_history = [
            {"date": f"2026-04-{day:02d}", "primary_mainline": "电力", "daily_attack_line": "电力"}
            for day in range(1, 25)
        ]
        snapshot = {
            "current_mainline_history_record": {"date": "2026-05-20", "primary_mainline": "半导体"},
            "recent_mainline_history": short_history,
            "current_sector_turnover_snapshot": {
                "date": "2026-05-20",
                "sector_name": "半导体",
                "sector_turnover": 4050.0,
                "total_turnover": 29764.59,
                "turnover_share_pct": 13.61,
            },
            "mainline_turnover_summary": {
                "current_mainline": "半导体",
                "turnover_share_trend_rows": [
                    {"date": "2026-05-18", "cycle_mainline": "电力", "daily_attack_line": "电力"},
                    {"date": "2026-05-19", "cycle_mainline": "电力", "daily_attack_line": "电力"},
                    {"date": "2026-05-20", "cycle_mainline": "半导体", "daily_attack_line": "半导体"},
                ],
            },
            "indices": [{"code": "sh000001"}],
            "data_status": {"主要指数": True},
            "step_status": {"主要指数获取": True},
            "total_turnover": 29764.59,
        }

        result = build_replay_snapshot_contract(
            "2026-05-20",
            refresh_sources=["noop"],
            load_data_snapshot=lambda target_date: (snapshot, ""),
            tencent_factory=lambda: _FakeTencentFinanceData([]),
            get_major_indices_from_iwencai=lambda target_date="": [],
            safe_float=lambda value: float(value or 0),
            print_fn=lambda *args, **kwargs: None,
            helpers={
                "load_recent_mainline_history": lambda target_date, lookback_days=25, max_scan_days=60: full_history,
                "load_recent_sector_turnover_history": lambda target_date, sector_name, lookback_days=25: [],
                "fetch_stock_batch_quote_info": lambda codes, target_date=None: {},
            },
        )

        self.assertEqual(len(result["data"]["recent_mainline_history"]), 24)
        rows = result["data"]["mainline_turnover_summary"]["turnover_share_trend_rows"]
        self.assertEqual(len(rows), 25)
        self.assertEqual(rows[0]["date"], "2026-04-01")

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

    def test_build_replay_snapshot_contract_refills_empty_lhb_from_tushare(self):
        snapshot = {
            "indices": [{"code": "sh000001"}],
            "total_turnover": 29170.74,
            "turnover_rank": [{"code": "000988", "data_source": "tushare.daily"}],
            "xuangubao_data": {"xuangubao_news": [{"title": "今日新闻"}]},
            "lhb_net_buy_top10": [],
            "lhb_net_sell_top10": [],
            "lhb_analysis": {},
            "data_status": {
                "两市成交额": True,
                "主要指数": True,
                "中证全指": True,
                "成交额排名": True,
                "选股通盘中异动": True,
            },
            "step_status": {
                "两市成交额获取": True,
                "主要指数获取": True,
                "中证全指获取": True,
                "成交额排名获取": True,
                "选股通盘中异动获取": True,
                "龙虎榜数据获取": True,
            },
            "module_logs": [
                {
                    "module": "domains.market_activity.request",
                    "step": "request.lhb_snapshot",
                    "status": "success",
                    "message": "已处理龙虎榜请求",
                    "details": {
                        "provider": "legacy.lhb_snapshot",
                        "target_keys": ["lhb_net_buy_top10", "lhb_net_sell_top10", "lhb_analysis"],
                        "lhb_count": 0,
                    },
                }
            ],
            "request_diagnostics": {"summary": {"degraded_count": 0}},
        }

        result = build_replay_snapshot_contract(
            "2026-05-18",
            refresh_sources=["noop"],
            load_data_snapshot=lambda target_date: (snapshot, ""),
            tencent_factory=lambda: _FakeTencentFinanceData([]),
            get_major_indices_from_iwencai=lambda target_date="": [],
            safe_float=lambda value: float(value or 0),
            print_fn=lambda *args, **kwargs: None,
            helpers={
                "get_lhb_snapshot_from_tushare": lambda target_date: {
                    "lhb_net_buy_top10": [
                        {"rank": 1, "code": "000988", "name": "华工科技", "net_buy_amount_yi": 16.99, "sector": "通信设备"}
                    ],
                    "lhb_net_sell_top10": [
                        {"rank": 1, "code": "688807", "name": "优迅股份", "net_buy_amount_yi": -4.93, "sector": "半导体"}
                    ],
                    "lhb_analysis": [{"代码": "000988", "net_buy_amount": 1699000000}],
                    "provider": "tushare.top_list",
                    "fallback_used": False,
                },
            },
        )

        data = result["data"]
        self.assertEqual(data["lhb_net_buy_top10"][0]["code"], "000988")
        self.assertEqual(data["lhb_net_sell_top10"][0]["code"], "688807")
        self.assertTrue(data["step_status"]["龙虎榜数据获取"])
        provider_by_step = {
            item["step"]: item["details"]["provider"]
            for item in data["module_logs"]
            if item.get("step") == "request.lhb_snapshot"
        }
        self.assertEqual(provider_by_step["request.lhb_snapshot"], "tushare.top_list")

    def test_build_replay_snapshot_contract_refreshes_missing_stock_quotes_for_existing_lhb_rows(self):
        snapshot = {
            "indices": [{"code": "sh000001"}],
            "total_turnover": 29170.74,
            "turnover_rank": [{"code": "000988", "data_source": "tushare.daily"}],
            "xuangubao_data": {"xuangubao_news": [{"title": "今日新闻"}]},
            "stock_full_info": {
                "000988": {
                    "name": "华工科技",
                    "change_pct": 10.0,
                    "high": 147.38,
                    "low": 137.03,
                    "open": 137.53,
                    "close": 147.38,
                    "data_source": "tushare.daily",
                }
            },
            "lhb_net_buy_top10": [
                {"rank": 1, "code": "000988", "name": "华工科技", "net_buy_amount_yi": 16.99, "sector": "通信设备"},
                {"rank": 2, "code": "688409", "name": "富创精密", "net_buy_amount_yi": 7.28, "sector": "半导体"},
            ],
            "lhb_net_sell_top10": [],
            "lhb_analysis": [{"stock_name": "华工科技", "net_buy": 16.99}],
            "lianban_data": [],
            "data_status": {
                "两市成交额": True,
                "主要指数": True,
                "中证全指": True,
                "成交额排名": True,
                "选股通盘中异动": True,
            },
            "step_status": {
                "两市成交额获取": True,
                "主要指数获取": True,
                "中证全指获取": True,
                "成交额排名获取": True,
                "选股通盘中异动获取": True,
                "龙虎榜数据获取": True,
            },
            "module_logs": [
                {
                    "module": "domains.market_activity.request",
                    "step": "request.stock_quotes",
                    "status": "success",
                    "message": "旧快照股票补数不完整",
                    "details": {"provider": "tushare.daily", "stock_count": 1},
                }
            ],
        }

        result = build_replay_snapshot_contract(
            "2026-05-18",
            refresh_sources=["noop"],
            load_data_snapshot=lambda target_date: (snapshot, ""),
            tencent_factory=lambda: _FakeTencentFinanceData([]),
            get_major_indices_from_iwencai=lambda target_date="": [],
            safe_float=lambda value: float(value or 0),
            print_fn=lambda *args, **kwargs: None,
            helpers={
                "fetch_stock_batch_quote_info": lambda codes, target_date: {
                    "688409": {
                        "name": "富创精密",
                        "change_pct": 4.67,
                        "high": 176.8,
                        "low": 155.74,
                        "open": 158.09,
                        "close": 169.85,
                        "data_source": "tushare.daily",
                    }
                },
            },
        )

        data = result["data"]
        self.assertEqual(data["stock_full_info"]["688409"]["high"], 176.8)
        self.assertEqual(data["lhb_net_buy_top10"][1]["high"], 176.8)
        self.assertEqual(data["lhb_net_buy_top10"][1]["close"], 169.85)
        by_step = {
            item["step"]: item
            for item in data["module_logs"]
            if item.get("step") == "request.stock_quotes"
        }
        self.assertEqual(by_step["request.stock_quotes"]["details"]["stock_count"], 2)

    def test_build_replay_snapshot_contract_derives_lianban_from_replayed_limit_pool(self):
        snapshot = {
            "indices": [{"code": "sh000001"}],
            "zt_pool": [
                {
                    "代码": "000988",
                    "名称": "华工科技",
                    "所属行业": "光通信",
                    "涨跌幅": 10.0,
                    "成交额": 88.8,
                    "连板数": 1,
                    "涨停统计": "光模块+CPO",
                    "开盘价": 137.53,
                    "最新价": 147.38,
                    "最高价": 147.38,
                    "最低价": 137.03,
                    "首次封板时间": "2026-05-18 09:25:00",
                }
            ],
            "lianban_data": [],
            "xuangubao_data": {
                "xuangubao_news": [{"title": "光通信方向异动"}],
                "xuangubao_limit_up_reasons": [
                    {
                        "symbol": "000988.SZ",
                        "stock_reason": "光模块放量涨停",
                        "related_plates": [{"plate_name": "光通信"}],
                        "limit_up_days": 1,
                    }
                ],
            },
            "data_status": {"主要指数": True, "选股通盘中异动": True},
            "step_status": {
                "主要指数获取": True,
                "选股通盘中异动获取": True,
                "连板梯队提取": True,
            },
            "module_logs": [],
        }

        result = build_replay_snapshot_contract(
            "2026-05-18",
            refresh_sources=["noop"],
            load_data_snapshot=lambda target_date: (snapshot, ""),
            tencent_factory=lambda: _FakeTencentFinanceData([]),
            get_major_indices_from_iwencai=lambda target_date="": [],
            safe_float=lambda value: float(value or 0),
            print_fn=lambda *args, **kwargs: None,
            helpers={},
        )

        data = result["data"]
        self.assertEqual(data["lianban_data"][0]["code"], "000988")
        self.assertEqual(data["lianban_data"][0]["lianban_days"], 1)
        self.assertEqual(data["lianban_data"][0]["first_limit_time"], "09:25:00")
        self.assertEqual(data["lianban_data"][0]["reason"], "光模块放量涨停")
        by_step = {
            item["step"]: item
            for item in data["module_logs"]
            if item.get("step") == "request.lianban_snapshot"
        }
        self.assertEqual(by_step["request.lianban_snapshot"]["details"]["lianban_count"], 1)
        self.assertEqual(by_step["request.lianban_snapshot"]["details"]["provider"], "replay.zt_pool.derived")

    def test_build_replay_snapshot_contract_derives_lianban_sector_from_limit_reason(self):
        snapshot = {
            "indices": [{"code": "sh000001"}],
            "zt_pool": [
                {
                    "代码": "000417",
                    "名称": "合百集团",
                    "所属行业": "未知",
                    "涨跌幅": 10.0,
                    "成交额": 230000000,
                    "连板数": 1,
                    "涨停统计": "间接投资长鑫科技+合肥国资+区域零售",
                    "开盘价": 7.87,
                    "最新价": 7.87,
                    "最高价": 7.87,
                    "最低价": 7.87,
                    "首次封板时间": "09:25:00",
                },
                {
                    "代码": "001259",
                    "名称": "利仁科技",
                    "所属行业": "待补充板块",
                    "涨跌幅": 10.0,
                    "成交额": 180000000,
                    "连板数": 1,
                    "涨停统计": "股份转让+小家电+露营经济",
                    "开盘价": 66.55,
                    "最新价": 66.55,
                    "最高价": 66.55,
                    "最低价": 63.01,
                    "首次封板时间": "09:25:00",
                },
                {
                    "代码": "605218",
                    "名称": "伟时电子",
                    "所属行业": "未知",
                    "涨跌幅": 10.0,
                    "成交额": 120000000,
                    "连板数": 1,
                    "涨停统计": "MiniLED车载背光+VR背光+减持终止",
                    "开盘价": 19.35,
                    "最新价": 19.35,
                    "最高价": 19.35,
                    "最低价": 19.35,
                    "首次封板时间": "09:33:24",
                },
            ],
            "lianban_data": [],
            "xuangubao_data": {
                "xuangubao_news": [{"title": "今日新闻"}],
                "xuangubao_limit_up_reasons": [],
            },
            "data_status": {"主要指数": True, "选股通盘中异动": True},
            "step_status": {
                "主要指数获取": True,
                "选股通盘中异动获取": True,
                "连板梯队提取": True,
            },
            "module_logs": [],
        }

        result = build_replay_snapshot_contract(
            "2026-05-18",
            refresh_sources=["noop"],
            load_data_snapshot=lambda target_date: (snapshot, ""),
            tencent_factory=lambda: _FakeTencentFinanceData([]),
            get_major_indices_from_iwencai=lambda target_date="": [],
            safe_float=lambda value: float(value or 0),
            print_fn=lambda *args, **kwargs: None,
            helpers={},
        )

        by_code = {item["code"]: item for item in result["data"]["lianban_data"]}
        self.assertEqual(by_code["000417"]["sector"], "国产芯片")
        self.assertEqual(by_code["000417"]["plates"], ["国产芯片"])
        self.assertEqual(by_code["000417"]["reason"], "间接投资长鑫科技+合肥国资+区域零售")
        self.assertEqual(by_code["001259"]["sector"], "家用电器")
        self.assertEqual(by_code["001259"]["plates"], ["家用电器"])
        self.assertNotEqual(by_code["001259"]["sector"], "待补充板块")
        self.assertEqual(by_code["605218"]["sector"], "消费电子")
        self.assertEqual(by_code["605218"]["plates"], ["消费电子"])

    def test_build_replay_snapshot_contract_derives_advanced_activity_when_snapshot_has_empty_tables(self):
        snapshot = {
            "indices": [{"code": "sh000001"}],
            "stocks_with_history": [
                {
                    "code": "300433",
                    "name": "蓝思科技",
                    "turnover": 120.0,
                    "change_pct": 13.12,
                    "sector": "消费电子",
                    "hist_turnover": [40.0, 50.0, 55.0, 60.0, 70.0],
                },
                {
                    "code": "603986",
                    "name": "兆易创新",
                    "turnover": 100.0,
                    "change_pct": 6.57,
                    "sector": "半导体",
                    "hist_turnover": [90.0, 95.0, 96.0, 98.0, 99.0],
                },
            ],
            "lhb_net_buy_top10": [],
            "lhb_net_sell_top10": [],
            "lhb_analysis": {},
            "volume_anomalies": [],
            "xuangubao_data": {"xuangubao_news": [{"title": "今日新闻"}]},
            "data_status": {"主要指数": True, "选股通盘中异动": True},
            "step_status": {
                "主要指数获取": True,
                "选股通盘中异动获取": True,
                "龙虎榜数据获取": True,
            },
            "module_logs": [
                {
                    "module": "domains.market_activity.request",
                    "step": "request.lhb_snapshot",
                    "status": "success",
                    "message": "旧快照空龙虎榜",
                    "details": {"provider": "legacy.lhb_snapshot", "lhb_count": 0},
                }
            ],
        }

        result = build_replay_snapshot_contract(
            "2026-05-18",
            refresh_sources=["noop"],
            load_data_snapshot=lambda target_date: (snapshot, ""),
            tencent_factory=lambda: _FakeTencentFinanceData([]),
            get_major_indices_from_iwencai=lambda target_date="": [],
            safe_float=lambda value: float(value or 0),
            print_fn=lambda *args, **kwargs: None,
            helpers={
                "get_lhb_snapshot_from_tushare": lambda target_date: {
                    "lhb_net_buy_top10": [
                        {"rank": 1, "code": "000988", "name": "华工科技", "net_buy_amount_yi": 16.99, "sector": "光通信"}
                    ],
                    "lhb_net_sell_top10": [
                        {"rank": 1, "code": "688807", "name": "优迅股份", "net_buy_amount_yi": -4.93, "sector": "半导体"}
                    ],
                    "lhb_analysis": [{"代码": "000988", "net_buy_amount": 1699000000}],
                    "provider": "tushare.top_list",
                },
            },
        )

        data = result["data"]
        self.assertEqual(data["volume_anomalies"][0]["stock_code"], "300433")
        self.assertEqual(data["volume_anomalies"][0]["anomaly_type"], "放量突破")
        self.assertGreaterEqual(data["volume_anomalies"][0]["volume_percentile"], 95)
        self.assertEqual(data["lhb_analysis"][0]["stock_name"], "华工科技")
        self.assertAlmostEqual(data["lhb_analysis"][0]["net_buy"], 16.99)
        self.assertEqual(data["lhb_analysis"][0]["money_type"], "龙虎榜净买入")
        self.assertEqual(data["lhb_analysis"][1]["stock_name"], "优迅股份")
        self.assertAlmostEqual(data["lhb_analysis"][1]["net_buy"], -4.93)
        by_step = {
            item["step"]: item
            for item in data["module_logs"]
            if item.get("step") in {"infer.volume_anomalies", "infer.lhb_analysis"}
        }
        self.assertEqual(by_step["infer.volume_anomalies"]["details"]["volume_anomaly_count"], 1)
        self.assertEqual(by_step["infer.lhb_analysis"]["details"]["lhb_count"], 2)

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
