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
    "run_input_runtime",
    return_value={"target_date": "2026-04-22", "module_logs": []},
) as runtime_mock:
    result = daily_report_entry_demo.get_daily_data("2026-04-22")

assert runtime_mock.call_args[0] == ("2026-04-22",)
assert "helpers" in runtime_mock.call_args.kwargs
assert result["target_date"] == "2026-04-22"
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


if __name__ == "__main__":
    unittest.main()
