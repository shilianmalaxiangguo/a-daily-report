import importlib
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
from unittest.mock import patch

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

    result = subprocess.run(
        [sys.executable, "-c", stub_setup + "\n" + script_body],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    return result


class InputRuntimeTest(unittest.TestCase):
    def test_quicktiny_exchange_monitor_fetch_uses_token_from_env(self):
        runtime = importlib.import_module("input.runtime")
        calls = []

        class Response:
            status_code = 200

            def json(self):
                return {"data": [{"code": "000001"}]}

        class RequestsStub:
            @staticmethod
            def get(url, **kwargs):
                calls.append((url, kwargs))
                return Response()

        result = runtime._fetch_quicktiny_exchange_monitor_payload(
            requests_module=RequestsStub,
            env={"QUICKTINY_EXCHANGE_MONITOR_TOKEN": "Bearer token-x"},
            timeout=3,
        )

        self.assertEqual(result["data"][0]["code"], "000001")
        self.assertEqual(calls[0][0], runtime.QUICKTINY_EXCHANGE_MONITOR_URL)
        self.assertEqual(calls[0][1]["timeout"], 3)
        self.assertEqual(calls[0][1]["headers"]["authorization"], "Bearer token-x")
        self.assertEqual(calls[0][1]["headers"]["cookie"], "token=token-x")

    def test_quicktiny_exchange_monitor_reads_token_from_dotenv(self):
        import os
        import tempfile

        runtime = importlib.import_module("input.runtime")
        import market_data.tushare_client as client

        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            env_path.write_text("QUICKTINY_TOKEN=dotenv-quicktiny-token\n", encoding="utf-8")
            with patch.dict(os.environ, {}, clear=True), patch.object(client.Path, "cwd", return_value=Path(tmpdir)):
                headers = runtime._quicktiny_exchange_monitor_headers()

        self.assertEqual(headers["authorization"], "Bearer dotenv-quicktiny-token")
        self.assertEqual(headers["cookie"], "token=dotenv-quicktiny-token")

    def test_margin_pressure_retry_returns_first_available_payload(self):
        runtime = importlib.import_module("input.runtime")
        calls = []

        def _fetcher(**kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                return {"available": False, "rows": []}
            if len(calls) == 2:
                raise TimeoutError("temporary timeout")
            return {"available": True, "rows": [{"trade_date": "2026-06-25"}]}

        result = runtime._fetch_margin_pressure_with_retry(_fetcher, "2026-06-26")

        self.assertTrue(result["available"])
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[0]["target_date"], "2026-06-26")

    def _new_stock_runtime_helpers(
        self,
        *,
        calendar_bundle=None,
        research_pool_builder=None,
        watch_candidate_builder=None,
    ):
        class StepTimer:
            def start(self):
                return None

            def record(self, *args, **kwargs):
                return (0.0, 0.0)

            def print_summary(self):
                return None

            def get_summary(self):
                return []

        class AShareDataCollector:
            def get_wanzhu_top10(self):
                return []

        class TencentFinanceData:
            def get_calendar_events(self, target_date=None):
                return []

            def get_stock_batch_info(self, codes):
                return {}

        def _empty_bundle(*args, **kwargs):
            return {"results": {}, "data_status": {}, "step_status": {}, "module_logs": []}

        def _market_state_bundle(*args, **kwargs):
            return {
                "results": {
                    "total_turnover": 10000.0,
                    "market_state_snapshot": {"leading_line": "机器人"},
                },
                "data_status": {"两市成交额": True},
                "step_status": {"两市成交额获取": True},
                "module_logs": [],
            }

        def _market_activity_pool_bundle(*args, **kwargs):
            return {
                "results": {"zt_pool": [], "dt_pool": []},
                "data_status": {},
                "step_status": {},
                "module_logs": [],
                "artifacts": {"limit_up_df": None, "limit_down_df": None},
            }

        def _sector_snapshot_bundle(*args, **kwargs):
            return {
                "results": {
                    "hot_plates": [{"name": "机器人"}],
                    "sector_change_up": [{"name": "机器人"}],
                    "sector_fund_flow": [{"name": "机器人", "net_inflow": 1.2}],
                },
                "data_status": {},
                "step_status": {},
                "module_logs": [],
            }

        def _calendar_events_bundle(*args, **kwargs):
            return {
                "results": {
                    "calendar_events": [],
                    "market_research_snapshot": {
                        "state_machine": {
                            "leading_line": "机器人",
                            "mainline_candidates": [{"name": "机器人"}],
                        }
                    },
                    "current_mainline_history_record": {
                        "primary_mainline": "机器人",
                        "leading_line": "机器人",
                    },
                },
                "data_status": {},
                "step_status": {},
                "module_logs": [],
            }

        def _calendar_bundle(*args, **kwargs):
            if calendar_bundle is not None:
                return calendar_bundle
            return {
                "results": {
                    "new_stock_calendar": [
                        {
                            "code": "301608",
                            "name": "理奇智能",
                            "listing_window": "tomorrow_listing",
                        }
                    ]
                },
                "data_status": {"新股上市日历": True},
                "step_status": {"新股上市日历获取": True},
                "module_logs": [
                    {
                        "module": "domains.new_stock_calendar.request",
                        "step": "request.new_stock_calendar",
                        "status": "success",
                        "message": "stub",
                        "details": {"target_keys": ["new_stock_calendar"]},
                    }
                ],
            }

        def _research_pool_builder(calendar, *, target_date="", context=None):
            if research_pool_builder is not None:
                return research_pool_builder(calendar, target_date=target_date, context=context)
            return {"new_stock_research_pool": [], "new_stock_candidate_upgrades": []}

        def _watch_candidate_builder(all_data, **kwargs):
            if watch_candidate_builder is not None:
                return watch_candidate_builder(all_data, **kwargs)
            return {
                "results": {"candidates": list(all_data.get("new_stock_candidate_upgrades", []))},
                "module_logs": [],
            }

        return {
            "StepTimer": StepTimer,
            "AShareDataCollector": AShareDataCollector,
            "TencentFinanceData": TencentFinanceData,
            "build_input_request_registry": lambda helpers: {},
            "get_new_high_feedback_from_tushare_first": lambda *args, **kwargs: {},
            "get_top50_turnover_share_series_from_tushare_first": lambda *args, **kwargs: {},
            "get_etf_turnover_series_from_sina_first": lambda *args, **kwargs: {},
            "get_price_band_style_series_from_tushare_first": lambda *args, **kwargs: {},
            "get_margin_pressure_from_tushare_first": lambda *args, **kwargs: {},
            "resolve_request_target_date": lambda target_date=None: str(target_date),
            "collect_market_state_request_bundle": _market_state_bundle,
            "collect_market_activity_pool_request_bundle": _market_activity_pool_bundle,
            "collect_market_activity_hot_rank_request_bundle": _empty_bundle,
            "collect_market_activity_sector_snapshot_request_bundle": _sector_snapshot_bundle,
            "collect_calendar_events_request_bundle": _calendar_events_bundle,
            "collect_new_stock_calendar_request_bundle": _calendar_bundle,
            "fetch_sina_new_stock_calendar_pages": lambda *args, **kwargs: [],
            "build_new_stock_research_pool": _research_pool_builder,
            "collect_monitoring_request_bundle": _empty_bundle,
            "collect_market_activity_capital_snapshot_request_bundle": _empty_bundle,
            "collect_market_activity_stock_quote_request_bundle": _empty_bundle,
            "build_market_activity_sector_analysis_bundle": _empty_bundle,
            "build_watch_candidate_pool_bundle": _watch_candidate_builder,
            "collect_watch_candidate_history_request_bundle": _empty_bundle,
            "build_market_activity_quant_signal_bundle": _empty_bundle,
            "build_request_diagnostics": lambda module_logs, data_status=None, step_status=None: {
                "request_logs": list(module_logs or [])
            },
            "render_request_diagnostics_lines": lambda diagnostics: [],
            "get_llm_call_stats": lambda: {
                "total_calls": 0,
                "event_analysis_calls": 0,
                "event_analysis_time": 0,
                "sector_analysis_calls": 0,
                "sector_analysis_time": 0,
                "total_time": 0,
            },
            "get_sector_quadrant_data": lambda *args, **kwargs: {},
            "get_limit_up_pool": lambda *args, **kwargs: [],
            "get_limit_down_pool": lambda *args, **kwargs: [],
            "fetch_ths_hot_stock": lambda *args, **kwargs: [],
            "get_integrated_hot_list": lambda *args, **kwargs: {},
            "fetch_hot_plate": lambda *args, **kwargs: [],
            "get_sector_change_from_iwencai": lambda *args, **kwargs: ([], []),
            "get_turnover_rank_from_iwencai": lambda *args, **kwargs: [],
            "get_stock_sector": lambda *args, **kwargs: "",
            "XuangubaoIntradayAnalyzer": object,
            "get_cache": lambda *args, **kwargs: {},
            "analyze_volume_anomaly": lambda *args, **kwargs: {},
            "analyze_lhb": lambda *args, **kwargs: {},
            "calculate_resonance": lambda *args, **kwargs: {},
            "generate_trade_signals": lambda *args, **kwargs: {},
        }

    def test_get_daily_data_wrapper_delegates_to_input_runtime(self):
        result = _run_legacy_entry_probe(
            """
import daily_report_entry_demo

with patch.object(
    daily_report_entry_demo,
    "check_tushare_runtime_ready",
    return_value={"ok": True, "provider": "tushare.pro.index_basic", "checks": [{"row_count": 1}]},
) as precheck_mock, patch.object(
    daily_report_entry_demo,
    "run_input_runtime",
    return_value={"target_date": "2026-04-22", "module_logs": []},
) as runtime_mock:
    result = daily_report_entry_demo.get_daily_data("2026-04-22")

assert precheck_mock.call_count == 1
assert runtime_mock.call_args[0] == ("2026-04-22",)
assert "helpers" in runtime_mock.call_args.kwargs
assert "get_new_high_feedback_from_tushare_first" in runtime_mock.call_args.kwargs["helpers"]
assert "get_top50_turnover_share_series_from_tushare_first" in runtime_mock.call_args.kwargs["helpers"]
assert "get_etf_turnover_series_from_sina_first" in runtime_mock.call_args.kwargs["helpers"]
assert "get_price_band_style_series_from_tushare_first" in runtime_mock.call_args.kwargs["helpers"]
assert "get_margin_pressure_from_tushare_first" in runtime_mock.call_args.kwargs["helpers"]
assert "get_csi1000_from_tushare_first" in runtime_mock.call_args.kwargs["helpers"]
assert result["target_date"] == "2026-04-22"
"""
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_get_daily_data_stops_before_runtime_when_tushare_precheck_fails(self):
        result = _run_legacy_entry_probe(
            """
import daily_report_entry_demo
from daily_report_render import ReportCriticalDataMissingError

with patch.object(
    daily_report_entry_demo,
    "check_tushare_runtime_ready",
    return_value={"ok": False, "error_message": "proxy down"},
), patch.object(daily_report_entry_demo, "run_input_runtime") as runtime_mock:
    try:
        daily_report_entry_demo.get_daily_data("2026-04-22")
    except ReportCriticalDataMissingError as exc:
        assert "Tushare跑前检查失败，停止生成：proxy down" in str(exc)
    else:
        raise AssertionError("expected ReportCriticalDataMissingError")

assert runtime_mock.call_count == 0
"""
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_legacy_lhb_snapshot_normalizes_finshare_rows_for_tushare_fallback(self):
        result = _run_legacy_entry_probe(
            """
import daily_report_entry_demo
import sys
import types

class FrameStub:
    def __init__(self, rows):
        self.rows = rows

    def __len__(self):
        return len(self.rows)

    def to_dict(self, orient):
        assert orient == "records"
        return list(self.rows)

rows = [
    {"fs_code": "000636.SZ", "net_buy_amount": 151351267.58, "close_price": 32.37, "change_rate": 9.9898},
    {"fs_code": "000417.SZ", "net_buy_amount": 54875999.06, "close_price": 8.66, "change_rate": 10.0381},
]
calls = []

finshare_stub = types.ModuleType("finshare")
def get_lhb(start_date=None, end_date=None):
    calls.append((start_date, end_date))
    return FrameStub(rows)
finshare_stub.get_lhb = get_lhb
sys.modules["finshare"] = finshare_stub

snapshot = daily_report_entry_demo.get_legacy_lhb_snapshot("2026-05-19")

assert calls == [("20260519", "20260519")]
assert snapshot["provider"] == "finshare.get_lhb"
assert snapshot["lhb_net_buy_top10"][0]["code"] == "000636"
assert snapshot["lhb_net_buy_top10"][0]["net_buy_amount_yi"] == 1.513513
assert snapshot["lhb_analysis"][0]["data_source"] == "finshare.get_lhb"
"""
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_run_input_runtime_returns_result_payload(self):
        input_runtime = importlib.import_module("input.runtime")

        with patch("input.runtime._run_input_runtime_legacy_body", return_value={"target_date": "2026-04-22"}) as body_mock:
            result = input_runtime.run_input_runtime("2026-04-22", helpers={"StepTimer": object}, config={})

        body_mock.assert_called_once()
        self.assertEqual(result["target_date"], "2026-04-22")

    def test_run_input_runtime_body_exposes_new_stock_side_channel_when_helpers_are_injected(self):
        input_runtime = importlib.import_module("input.runtime")
        calls = {}
        upgrade = {
            "code": "301608",
            "name": "理奇智能",
            "watch_source": "new_stock_research_pool",
        }

        def build_new_stock_research_pool(calendar, *, target_date="", context=None):
            calls["calendar"] = calendar
            calls["target_date"] = target_date
            calls["context"] = context
            return {
                "new_stock_research_pool": [{"code": "301608", "name": "理奇智能"}],
                "new_stock_candidate_upgrades": [upgrade],
            }

        def build_watch_candidate_pool_bundle(all_data, **kwargs):
            calls["watch_candidate_saw_upgrades"] = list(all_data.get("new_stock_candidate_upgrades", []))
            return {
                "results": {"candidates": list(all_data.get("new_stock_candidate_upgrades", []))},
                "module_logs": [],
            }

        helpers = self._new_stock_runtime_helpers(
            research_pool_builder=build_new_stock_research_pool,
            watch_candidate_builder=build_watch_candidate_pool_bundle,
        )

        result = input_runtime.run_input_runtime("2026-04-29", helpers=helpers)

        self.assertEqual(
            calls["calendar"],
            [{"code": "301608", "name": "理奇智能", "listing_window": "tomorrow_listing"}],
        )
        self.assertEqual(calls["target_date"], "2026-04-29")
        self.assertEqual(calls["context"]["mainline_name"], "机器人")
        self.assertIn("机器人", calls["context"]["potential_mainlines"])
        self.assertGreaterEqual(calls["context"]["sector_resonance"]["score"], 8)
        self.assertEqual(calls["context"]["sector_resonance"]["supported_sectors"], ["机器人"])
        self.assertEqual(result["new_stock_calendar"], calls["calendar"])
        self.assertEqual(result["new_stock_research_pool"], [{"code": "301608", "name": "理奇智能"}])
        self.assertEqual(result["new_stock_candidate_upgrades"], [upgrade])
        self.assertEqual(calls["watch_candidate_saw_upgrades"], [upgrade])
        self.assertEqual(result["candidates"], [upgrade])

    def test_run_input_runtime_new_stock_scoring_failure_is_non_fatal(self):
        input_runtime = importlib.import_module("input.runtime")
        normal_candidate = {"code": "002001", "name": "正常候选"}

        def build_new_stock_research_pool(calendar, *, target_date="", context=None):
            raise RuntimeError("scoring exploded")

        def build_watch_candidate_pool_bundle(all_data, **kwargs):
            return {"results": {"candidates": [normal_candidate]}, "module_logs": []}

        helpers = self._new_stock_runtime_helpers(
            research_pool_builder=build_new_stock_research_pool,
            watch_candidate_builder=build_watch_candidate_pool_bundle,
        )

        result = input_runtime.run_input_runtime("2026-04-29", helpers=helpers)

        self.assertEqual(result["new_stock_research_pool"], [])
        self.assertEqual(result["new_stock_candidate_upgrades"], [])
        self.assertEqual(result["candidates"], [normal_candidate])
        self.assertTrue(
            any(
                log.get("status") == "error"
                and log.get("step") == "request.new_stock_scoring"
                for log in result.get("module_logs", [])
            )
        )

    def test_run_input_runtime_refreshes_quotes_after_watch_candidates_are_built(self):
        input_runtime = importlib.import_module("input.runtime")
        quote_calls = []
        final_candidate = {"code": "001896", "name": "豫能控股"}

        def collect_stock_quotes(*, existing_results=None, fetch_stock_batch_info=None, fetch_tushare_stock_batch_info=None, target_date=None, timer=None, emit=None):
            del fetch_stock_batch_info, fetch_tushare_stock_batch_info, timer, emit
            quote_calls.append((target_date, sorted((existing_results or {}).keys())))
            if (existing_results or {}).get("selected_position_candidate"):
                return {
                    "results": {
                        "stock_full_info": {
                            "001896": {
                                "name": "豫能控股",
                                "change_pct": -1.41,
                                "high": 21.50,
                                "low": 19.00,
                                "open": 19.87,
                                "close": 19.60,
                            }
                        },
                        "selected_position_candidate": {
                            "code": "001896",
                            "name": "豫能控股",
                            "change_pct": -1.41,
                            "high": 21.50,
                            "low": 19.00,
                            "open": 19.87,
                            "close": 19.60,
                        },
                    },
                    "module_logs": [
                        {
                            "module": "domains.market_activity.request",
                            "step": "request.stock_quotes",
                            "status": "success",
                            "message": "stub",
                            "details": {"target_keys": ["stock_full_info"], "stock_count": 1},
                        }
                    ],
                }
            return {"results": {"stock_full_info": {}}, "module_logs": []}

        helpers = self._new_stock_runtime_helpers(
            watch_candidate_builder=lambda all_data, **kwargs: {
                "results": {
                    "selected_position_candidate": dict(final_candidate),
                },
                "module_logs": [],
            }
        )
        helpers["collect_market_activity_stock_quote_request_bundle"] = collect_stock_quotes

        result = input_runtime.run_input_runtime("2026-06-08", helpers=helpers)

        self.assertGreaterEqual(len(quote_calls), 2)
        self.assertTrue(all(item[0] == "2026-06-08" for item in quote_calls))
        self.assertEqual(result["selected_position_candidate"]["change_pct"], -1.41)
        self.assertEqual(result["selected_position_candidate"]["close"], 19.60)
        self.assertEqual(result["stock_full_info"]["001896"]["high"], 21.50)
        self.assertTrue(any(log.get("step") == "request.stock_quotes" for log in result.get("module_logs", [])))

    def test_run_input_runtime_logs_quicktiny_sector_quadrant_provider(self):
        input_runtime = importlib.import_module("input.runtime")
        helpers = self._new_stock_runtime_helpers()
        helpers["get_sector_quadrant_data"] = lambda *args, **kwargs: {
            "provider": "quicktiny.sector_analysis_quadrant",
            "high_strong_analysis": {
                "total": 1,
                "tier1_count": 1,
                "tier2_count": 0,
                "tier3_count": 0,
                "tier4_count": 0,
            },
            "quadrants": {"highStrong": [{"name": "氟化工"}]},
        }

        result = input_runtime.run_input_runtime("2026-04-29", helpers=helpers)

        provider_by_step = {log.get("step"): (log.get("details") or {}).get("provider") for log in result.get("module_logs", [])}
        self.assertEqual(provider_by_step["request.sector_quadrant"], "quicktiny.sector_analysis_quadrant")
        self.assertTrue(result["data_status"]["板块四象限"])

    def test_run_input_runtime_fetches_top50_turnover_share_series(self):
        input_runtime = importlib.import_module("input.runtime")
        calls = []
        helpers = self._new_stock_runtime_helpers()
        helpers["build_input_request_registry"] = lambda runtime_helpers: {
            "top50_turnover_share_series": lambda *, target_date, window_days=25, limit=50: calls.append(
                (target_date, window_days, limit)
            )
            or {
                "rows": [
                    {
                        "trade_date": "2026-05-18",
                        "top_amount_yi": 6150.0,
                        "market_amount_yi": 30000.0,
                        "share_pct": 20.5,
                    }
                ]
            },
        }

        result = input_runtime.run_input_runtime("2026-05-18", helpers=helpers)

        self.assertEqual(calls, [("2026-05-18", 25, 50)])
        self.assertEqual(result["top50_turnover_share_series"]["rows"][0]["share_pct"], 20.5)
        self.assertTrue(result["data_status"]["Top50成交额占比趋势"])
        self.assertTrue(result["step_status"]["Top50成交额占比趋势获取"])
        provider_by_step = {log.get("step"): (log.get("details") or {}).get("provider") for log in result.get("module_logs", [])}
        self.assertEqual(provider_by_step["request.top50_turnover_share_series"], "storage.turnover_rank_daily")

    def test_run_input_runtime_fetches_price_band_style_series(self):
        input_runtime = importlib.import_module("input.runtime")
        calls = []
        helpers = self._new_stock_runtime_helpers()
        helpers["build_input_request_registry"] = lambda runtime_helpers: {
            "price_band_style_series": lambda *, target_date, window_days=25: calls.append((target_date, window_days))
            or {
                "available": True,
                "source": "tushare.ths_daily.price_band_style",
                "rows": [{"trade_date": "2026-05-18", "spread_pct": 1.1}],
            },
        }

        result = input_runtime.run_input_runtime("2026-05-18", helpers=helpers)

        self.assertEqual(calls, [("2026-05-18", 25)])
        self.assertEqual(result["price_band_style_series"]["rows"][0]["spread_pct"], 1.1)
        self.assertTrue(result["data_status"]["价格带风格趋势"])
        self.assertTrue(result["step_status"]["价格带风格趋势获取"])
        provider_by_step = {log.get("step"): (log.get("details") or {}).get("provider") for log in result.get("module_logs", [])}
        self.assertEqual(provider_by_step["request.price_band_style_series"], "tushare.ths_daily.price_band_style")

    def test_run_input_runtime_fetches_etf_turnover_series(self):
        input_runtime = importlib.import_module("input.runtime")
        calls = []
        helpers = self._new_stock_runtime_helpers()
        helpers["build_input_request_registry"] = lambda runtime_helpers: {
            "etf_turnover_series": lambda *, target_date, window_days=25: calls.append((target_date, window_days))
            or {
                "available": True,
                "source": "sina.etf.daily_amount",
                "rows": [{"trade_date": "2026-05-18", "etf_turnover_yi": 4484.9}],
            },
        }

        result = input_runtime.run_input_runtime("2026-05-18", helpers=helpers)

        self.assertEqual(calls, [("2026-05-18", 25)])
        self.assertEqual(result["etf_turnover_series"]["rows"][0]["etf_turnover_yi"], 4484.9)
        self.assertTrue(result["data_status"]["ETF两市成交额趋势"])
        self.assertTrue(result["step_status"]["ETF两市成交额趋势获取"])
        provider_by_step = {log.get("step"): (log.get("details") or {}).get("provider") for log in result.get("module_logs", [])}
        self.assertEqual(provider_by_step["request.etf_turnover_series"], "sina.etf.daily_amount")

    def test_run_input_runtime_rejects_etf_turnover_coverage_anomaly(self):
        input_runtime = importlib.import_module("input.runtime")
        helpers = self._new_stock_runtime_helpers()
        helpers["build_input_request_registry"] = lambda runtime_helpers: {
            "etf_turnover_series": lambda *, target_date, window_days=25: {
                "available": True,
                "source": "sina.etf.daily_amount",
                "coverage_anomaly": True,
                "coverage_status": "partial",
                "coverage_ratio": 0.44,
                "coverage_reference_count": 1190,
                "latest_covered_etf_count": 520,
                "coverage_anomaly_reason": "目标日有成交ETF数520只，样本覆盖不足",
                "rows": [{"trade_date": "2026-06-11", "etf_turnover_yi": 665.8}],
            },
        }

        result = input_runtime.run_input_runtime("2026-06-11", helpers=helpers)

        self.assertFalse(result["data_status"]["ETF两市成交额趋势"])
        self.assertFalse(result["step_status"]["ETF两市成交额趋势获取"])
        log = next(row for row in result["module_logs"] if row.get("step") == "request.etf_turnover_series")
        self.assertEqual(log["status"], "degraded")
        self.assertEqual(log["message"], "ETF两市成交额趋势样本覆盖不足")
        self.assertEqual(log["details"]["coverage_status"], "partial")

    def test_run_input_runtime_fetches_margin_pressure(self):
        input_runtime = importlib.import_module("input.runtime")
        calls = []
        helpers = self._new_stock_runtime_helpers()
        helpers["build_input_request_registry"] = lambda runtime_helpers: {
            "margin_pressure": lambda *, target_date, window_days=25, calibration_days=250: calls.append(
                (target_date, window_days, calibration_days)
            )
            or {
                "available": True,
                "source": "tushare.margin+tushare.index_daily.market_amount",
                "rows": [{"trade_date": "2026-05-18", "margin_turnover_ratio_pct": 99.0}],
            },
        }

        result = input_runtime.run_input_runtime("2026-05-18", helpers=helpers)

        self.assertEqual(calls, [("2026-05-18", 25, 250)])
        self.assertEqual(result["margin_pressure"]["rows"][0]["margin_turnover_ratio_pct"], 99.0)
        self.assertTrue(result["data_status"]["融资承接压力"])
        self.assertTrue(result["step_status"]["融资承接压力获取"])
        provider_by_step = {log.get("step"): (log.get("details") or {}).get("provider") for log in result.get("module_logs", [])}
        self.assertEqual(provider_by_step["request.margin_pressure"], "tushare.margin+tushare.index_daily.market_amount")

    def test_run_input_runtime_passes_xueqiu_fetchers_to_hot_rank_request(self):
        input_runtime = importlib.import_module("input.runtime")
        captured = {}
        helpers = self._new_stock_runtime_helpers()

        def collect_hot_rank(*args, **kwargs):
            captured["xueqiu_hot_rank_fetcher"] = kwargs.get("xueqiu_hot_rank_fetcher")
            captured["xueqiu_argument_fetcher"] = kwargs.get("xueqiu_argument_fetcher")
            return {"results": {}, "data_status": {}, "step_status": {}, "module_logs": []}

        helpers["collect_market_activity_hot_rank_request_bundle"] = collect_hot_rank

        input_runtime.run_input_runtime("2026-05-22", helpers=helpers)

        self.assertIs(captured["xueqiu_argument_fetcher"], input_runtime.try_fetch_xueqiu_hot_stock_arguments)
        self.assertTrue(callable(captured["xueqiu_hot_rank_fetcher"]))


if __name__ == "__main__":
    unittest.main()
