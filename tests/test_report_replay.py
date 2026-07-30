import datetime
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def _replay_market_language_artifact(target_date):
    return {
        "schema_version": "market_language_translation.v1",
        "target_date": target_date,
        "analysis_mode": "replay",
    }

from replay.report_replay import (
    _ensure_replay_market_breadth,
    _ensure_replay_price_band_style_series,
    _ensure_replay_stock_quotes,
    _normalize_replay_trade_narrative_sectors,
    build_replay_snapshot_contract,
)
from daily_report_render import REPORT_VARIANT_FULL, REPORT_VARIANT_SUMMARY, build_report_preflight, save_report_outputs
from knowledge.llm_wiki_context import build_llm_wiki_context, build_replay_llm_wiki_context
from knowledge.llm_wiki_router import route_llm_wiki_knowledge_trace


def _frozen_llm_wiki_context(target_date):
    context = build_llm_wiki_context(target_date=target_date, query_date=target_date)
    trace = route_llm_wiki_knowledge_trace(
        {
            "market": {
                "index_trend": "上涨",
                "breadth": "上涨家数偏弱",
                "turnover_distribution": "成交集中",
            }
        },
        manifest=context["manifest"],
        target_date=target_date,
        query_date=target_date,
    )
    context["knowledge_hits"] = list(trace["hits"])
    context["knowledge_trace"] = trace
    return context


def _frozen_historical_prior_wiki_context(target_date):
    context = build_llm_wiki_context(target_date=target_date, query_date=target_date)
    trace = route_llm_wiki_knowledge_trace(
        {
            "market": {
                "market_form": "历史先验只限定范围，实时结构与模型分歧决定当前解释",
                "breadth": "短促反弹不等于稳定修复，需要观察修复质量",
            }
        },
        manifest=context["manifest"],
        target_date=target_date,
        query_date=target_date,
    )
    context["knowledge_hits"] = list(trace["hits"])
    context["knowledge_trace"] = trace
    return context


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


def _target_date_lhb_snapshot(target_date):
    return {
        "lhb_net_buy_top10": [
            {
                "rank": 1,
                "code": "000988",
                "name": "华工科技",
                "net_buy_amount_yi": 16.99,
                "sector": "通信设备",
                "trade_date": target_date,
            }
        ],
        "lhb_net_sell_top10": [],
        "lhb_analysis": [
            {
                "代码": "000988",
                "net_buy_amount": 1699000000,
                "trade_date": target_date,
            }
        ],
        "provider": "tushare.top_list",
        "fallback_used": False,
    }


def _minimal_sector_first_preflight_inputs(target_date):
    target_day = datetime.date.fromisoformat(target_date)
    return {
        "market_state_snapshot": {"trade_date": target_date, "source": "test.fixture"},
        "mainline_turnover_summary": {"trade_date": target_date, "source": "test.fixture"},
        "etf_turnover_series": {
            "available": True,
            "source": "test.fixture",
            "rows": [
                {
                    "trade_date": (target_day - datetime.timedelta(days=offset)).isoformat(),
                    "etf_turnover_yi": 4400 + (24 - offset),
                }
                for offset in range(24, -1, -1)
            ],
        },
        "selected_position_candidate": {"code": "000988", "name": "华工科技", "trade_date": target_date},
        "final_target_resolution": {
            "target": {"code": "000988", "name": "华工科技"},
            "final_action": "观察",
            "trade_date": target_date,
        },
    }


class ReportReplayTest(unittest.TestCase):
    def setUp(self):
        def _offline_xuangubao(target_date, helpers):
            fetcher = (helpers or {}).get("fetch_xuangubao_data")
            if callable(fetcher):
                try:
                    return fetcher(target_date=target_date) or {}
                except TypeError as error:
                    if "target_date" not in str(error):
                        raise
                    return fetcher() or {}
            return {
                "xuangubao_news": [],
                "xuangubao_plates": [],
                "xuangubao_limit_up_reasons": [],
                "diagnostics": {"test": "offline"},
            }

        def _offline_wanzhu(target_date, helpers):
            fetcher = (helpers or {}).get("fetch_wanzhu_top10")
            if callable(fetcher):
                return list(fetcher(target_date) or [])
            return []

        def _offline_lhb(target_date, helpers):
            fetcher = (helpers or {}).get("get_lhb_snapshot_from_tushare")
            if callable(fetcher):
                try:
                    return fetcher(target_date=target_date) or {}
                except TypeError as error:
                    if "target_date" not in str(error):
                        raise
                    return fetcher(target_date) or {}
            return {}

        def _offline_default_mainline_helpers():
            helpers = self._original_load_default_mainline_helpers()
            helpers.update(
                {
                    "load_recent_mainline_history": lambda target_date, lookback_days=25, max_scan_days=60: [],
                    "load_recent_sector_turnover_history": lambda target_date, sector_name, lookback_days=25: [],
                    "get_sector_turnover_snapshot_from_ths": lambda sector_name, target_date="", total_turnover=0: {},
                    "get_wind_a_from_tushare": lambda target_date: {},
                    "get_market_daily_total_from_fact_db": lambda target_date: {},
                    "get_market_total_turnover_from_fact_db": lambda target_date: 0,
                    "get_turnover_rank_from_fact_db": lambda target_date, limit=50: [],
                    "get_market_breadth_from_fact_db": lambda target_date: {},
                    "query_new_high_feedback_series": lambda end_date, window_days=25: [],
                    "get_new_high_feedback_from_tushare": lambda target_date=None, **kwargs: {},
                    "get_price_band_style_series_from_tushare": lambda target_date=None, **kwargs: {},
                }
            )
            return helpers

        import replay.report_replay as replay_runtime

        self._original_load_default_mainline_helpers = replay_runtime._load_default_mainline_helpers
        self._offline_replay_patches = [
            patch(
                "replay.report_replay._load_default_mainline_helpers",
                side_effect=_offline_default_mainline_helpers,
            ),
            patch(
                "replay.report_replay._fetch_replay_xuangubao_data",
                side_effect=_offline_xuangubao,
            ),
            patch("replay.report_replay._fetch_replay_wanzhu_top10", side_effect=_offline_wanzhu),
            patch("replay.report_replay._fetch_replay_lhb_snapshot", side_effect=_offline_lhb),
        ]
        for replay_patch in self._offline_replay_patches:
            replay_patch.start()
        self.addCleanup(lambda: [replay_patch.stop() for replay_patch in reversed(self._offline_replay_patches)])

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

    def test_default_replay_helpers_use_fact_store_without_retired_local_db_path(self):
        replay_runtime = self._load_module()
        calls = []

        class FakeService:
            def query_new_high_feedback_series(self, end_date, *, window_days=25):
                calls.append(("query", end_date, window_days))
                return [{"trade_date": "2026-06-04", "new_high_count": 188}]

        class FakeDatabaseService:
            @classmethod
            def fact_store_from_environment(cls, db_path=None):
                calls.append(("fact_store", db_path))
                return FakeService()

        with patch("storage.database_service.DatabaseService", FakeDatabaseService):
            helpers = self._original_load_default_mainline_helpers()
            rows = helpers["query_new_high_feedback_series"]("2026-06-05", window_days=25)

        self.assertEqual(rows[0]["new_high_count"], 188)
        self.assertEqual(calls, [("fact_store", None), ("query", "2026-06-05", 25)])

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

    def test_build_replay_snapshot_contract_reuses_target_date_frozen_wiki_trace(self):
        frozen_wiki = _frozen_llm_wiki_context("2026-07-16")
        snapshot = {
            "knowledge": {"llm_wiki": frozen_wiki},
            "indices": [{"code": "sh000001"}],
            "data_status": {"主要指数": True},
            "step_status": {"主要指数获取": True},
        }

        result = build_replay_snapshot_contract(
            "2026-07-16",
            refresh_sources=["noop"],
            load_data_snapshot=lambda target_date: (snapshot, ""),
            tencent_factory=lambda: _FakeTencentFinanceData([]),
            get_major_indices_from_iwencai=lambda target_date="": [],
            safe_float=lambda value: float(value or 0),
            print_fn=lambda *args, **kwargs: None,
        )

        replay_wiki = result["data"]["knowledge"]["llm_wiki"]
        self.assertEqual(replay_wiki["artifact_origin"], "frozen_trace")
        self.assertEqual(
            replay_wiki["knowledge_trace"]["trace_hash"],
            frozen_wiki["knowledge_trace"]["trace_hash"],
        )
        self.assertEqual(replay_wiki["knowledge_hits"], frozen_wiki["knowledge_trace"]["hits"])
        self.assertIs(result["llm_wiki"], replay_wiki)
        self.assertTrue(
            any(
                log["step"] == "load.llm_wiki_trace" and log["status"] == "success"
                for log in result["module_logs"]
            )
        )

    def test_replay_reuses_frozen_historical_prior_hit_without_current_routing(self):
        frozen_wiki = _frozen_historical_prior_wiki_context("2026-07-16")
        frozen_trace = frozen_wiki["knowledge_trace"]
        self.assertIn(
            "market.historical-prior-live-structure",
            {item["knowledge_id"] for item in frozen_trace["hits"]},
        )
        snapshot = {
            "knowledge": {"llm_wiki": frozen_wiki},
            "indices": [{"code": "sh000001"}],
            "data_status": {"主要指数": True},
            "step_status": {"主要指数获取": True},
        }

        with patch(
            "replay.report_replay.build_replay_llm_wiki_context",
            wraps=build_replay_llm_wiki_context,
        ) as replay_builder:
            result = build_replay_snapshot_contract(
                "2026-07-16",
                refresh_sources=["noop"],
                load_data_snapshot=lambda target_date: (snapshot, ""),
                tencent_factory=lambda: _FakeTencentFinanceData([]),
                get_major_indices_from_iwencai=lambda target_date="": [],
                safe_float=lambda value: float(value or 0),
                print_fn=lambda *args, **kwargs: None,
            )

        replay_builder.assert_called_once()
        replay_wiki = result["data"]["knowledge"]["llm_wiki"]
        self.assertEqual(replay_wiki["artifact_origin"], "frozen_trace")
        self.assertEqual(replay_wiki["knowledge_trace"], frozen_trace)
        self.assertEqual(replay_wiki["knowledge_hits"], frozen_trace["hits"])

    def test_build_replay_snapshot_contract_rejects_frozen_wiki_trace_from_another_date(self):
        snapshot = {
            "knowledge": {"llm_wiki": _frozen_llm_wiki_context("2026-07-15")},
            "indices": [{"code": "sh000001"}],
            "data_status": {"主要指数": True},
            "step_status": {"主要指数获取": True},
        }

        result = build_replay_snapshot_contract(
            "2026-07-16",
            refresh_sources=["noop"],
            load_data_snapshot=lambda target_date: (snapshot, ""),
            tencent_factory=lambda: _FakeTencentFinanceData([]),
            get_major_indices_from_iwencai=lambda target_date="": [],
            safe_float=lambda value: float(value or 0),
            print_fn=lambda *args, **kwargs: None,
        )

        replay_wiki = result["data"]["knowledge"]["llm_wiki"]
        self.assertEqual(replay_wiki["artifact_origin"], "missing")
        self.assertEqual(replay_wiki["knowledge_hits"], [])
        self.assertIn("冻结知识引用日期与目标交易日不一致", replay_wiki["warnings"][0])
        self.assertTrue(
            any(
                log["step"] == "load.llm_wiki_trace" and log["status"] == "warning"
                for log in result["module_logs"]
            )
        )

    def test_build_replay_snapshot_contract_marks_missing_historical_wiki_trace(self):
        snapshot = {
            "indices": [{"code": "sh000001"}],
            "data_status": {"主要指数": True},
            "step_status": {"主要指数获取": True},
        }

        result = build_replay_snapshot_contract(
            "2026-07-16",
            refresh_sources=["noop"],
            load_data_snapshot=lambda target_date: (snapshot, ""),
            tencent_factory=lambda: _FakeTencentFinanceData([]),
            get_major_indices_from_iwencai=lambda target_date="": [],
            safe_float=lambda value: float(value or 0),
            print_fn=lambda *args, **kwargs: None,
        )

        replay_wiki = result["data"]["knowledge"]["llm_wiki"]
        self.assertEqual(replay_wiki["artifact_origin"], "missing")
        self.assertEqual(replay_wiki["knowledge_hits"], [])
        self.assertEqual(replay_wiki["knowledge_trace"]["availability"], "historical_trace_missing")
        self.assertEqual(replay_wiki["knowledge_trace"]["fact_sources"], {})
        self.assertIn("当时知识引用缺失", replay_wiki["warnings"][0])
        self.assertTrue(
            any(
                log["step"] == "load.llm_wiki_trace" and log["status"] == "warning"
                for log in result["module_logs"]
            )
        )

    def test_missing_historical_wiki_trace_uses_shanghai_query_date(self):
        class FixedDateTime(datetime.datetime):
            @classmethod
            def now(cls, tz=None):
                fixed = cls(2026, 7, 17, 16, 30, tzinfo=datetime.timezone.utc)
                return fixed if tz is None else fixed.astimezone(tz)

        snapshot = {
            "indices": [{"code": "sh000001"}],
            "data_status": {"主要指数": True},
            "step_status": {"主要指数获取": True},
        }
        fake_datetime_module = SimpleNamespace(
            datetime=FixedDateTime,
            timezone=datetime.timezone,
            timedelta=datetime.timedelta,
        )
        with patch("replay.report_replay.datetime", fake_datetime_module):
            result = build_replay_snapshot_contract(
                "2026-07-16",
                refresh_sources=["noop"],
                load_data_snapshot=lambda target_date: (snapshot, ""),
                tencent_factory=lambda: _FakeTencentFinanceData([]),
                get_major_indices_from_iwencai=lambda target_date="": [],
                safe_float=lambda value: float(value or 0),
                print_fn=lambda *args, **kwargs: None,
            )

        replay_wiki = result["data"]["knowledge"]["llm_wiki"]
        self.assertEqual(replay_wiki["knowledge_trace"]["query_date"], "2026-07-18")

    def test_build_replay_snapshot_contract_rejects_non_mapping_snapshot(self):
        result = build_replay_snapshot_contract(
            "2026-07-16",
            refresh_sources=["noop"],
            load_data_snapshot=lambda target_date: (["invalid snapshot"], ""),
            tencent_factory=lambda: _FakeTencentFinanceData([]),
            get_major_indices_from_iwencai=lambda target_date="": [],
            safe_float=lambda value: float(value or 0),
            print_fn=lambda *args, **kwargs: None,
        )

        self.assertFalse(result["found"])
        self.assertIsNone(result["data"])
        self.assertTrue(
            any(
                log["step"] == "load.snapshot" and log["status"] == "error"
                for log in result["module_logs"]
            )
        )

    def test_build_replay_snapshot_contract_marks_non_mapping_nested_wiki_missing(self):
        snapshot = {
            "knowledge": {"llm_wiki": ["invalid wiki context"]},
            "indices": [{"code": "sh000001"}],
            "data_status": {"主要指数": True},
            "step_status": {"主要指数获取": True},
        }

        result = build_replay_snapshot_contract(
            "2026-07-16",
            refresh_sources=["noop"],
            load_data_snapshot=lambda target_date: (snapshot, ""),
            tencent_factory=lambda: _FakeTencentFinanceData([]),
            get_major_indices_from_iwencai=lambda target_date="": [],
            safe_float=lambda value: float(value or 0),
            print_fn=lambda *args, **kwargs: None,
        )

        replay_wiki = result["data"]["knowledge"]["llm_wiki"]
        self.assertEqual(replay_wiki["artifact_origin"], "missing")
        self.assertEqual(replay_wiki["knowledge_hits"], [])
        self.assertIn("当时知识引用缺失", replay_wiki["warnings"][0])

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
                    "available": True,
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

    def test_build_replay_snapshot_contract_refreshes_etf_series_with_future_rows(self):
        snapshot_rows = [
            {"trade_date": f"2026-07-{day:02d}", "etf_turnover_yi": 4400 + day}
            for day in range(5, 30)
        ]
        snapshot_rows.append({"trade_date": "2026-07-30", "etf_turnover_yi": 9999})
        snapshot = {
            "indices": [{"code": "sh000001"}],
            "data_status": {"主要指数": True, "ETF两市成交额趋势": True},
            "step_status": {"主要指数获取": True, "ETF两市成交额趋势获取": True},
            "etf_turnover_series": {"available": True, "rows": snapshot_rows},
        }
        etf_calls = []

        result = build_replay_snapshot_contract(
            "2026-07-29",
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
                    "available": True,
                    "source": "sina.etf.daily_amount",
                    "rows": [
                        {"trade_date": f"2026-07-{day:02d}", "etf_turnover_yi": 4500 + day}
                        for day in range(5, 30)
                    ],
                },
            },
        )

        self.assertEqual(etf_calls, [("2026-07-29", 25)])
        self.assertEqual(result["data"]["etf_turnover_series"]["rows"][-1]["trade_date"], "2026-07-29")

    def test_build_replay_snapshot_contract_rejects_invalid_etf_refresh_result(self):
        snapshot_rows = [
            {"trade_date": f"2026-07-{day:02d}", "etf_turnover_yi": 4400 + day}
            for day in range(5, 30)
        ]
        snapshot = {
            "indices": [{"code": "sh000001"}],
            "data_status": {"主要指数": True, "ETF两市成交额趋势": True},
            "step_status": {"主要指数获取": True, "ETF两市成交额趋势获取": True},
            "etf_turnover_series": {
                "available": False,
                "coverage_anomaly": True,
                "coverage_status": "partial",
                "rows": snapshot_rows,
            },
        }
        etf_calls = []

        result = build_replay_snapshot_contract(
            "2026-07-29",
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
                    "available": False,
                    "source": "sina.etf.daily_amount",
                    "coverage_anomaly": True,
                    "coverage_status": "partial",
                    "rows": [
                        {"trade_date": f"2026-07-{day:02d}", "etf_turnover_yi": 4500 + day}
                        for day in range(5, 30)
                    ],
                },
            },
        )

        data = result["data"]
        self.assertEqual(etf_calls, [("2026-07-29", 25)])
        self.assertFalse(data["data_status"]["ETF两市成交额趋势"])
        self.assertFalse(data["step_status"]["ETF两市成交额趋势获取"])
        self.assertTrue(data["etf_turnover_series"]["coverage_anomaly"])
        log = next(row for row in data["module_logs"] if row.get("step") == "request.etf_turnover_series")
        self.assertEqual(log["status"], "degraded")
        self.assertIn("刷新结果不满足目标日条件", log["message"])

    def test_build_replay_snapshot_contract_rejects_stale_etf_without_refresh_function(self):
        snapshot = {
            "indices": [{"code": "sh000001"}],
            "data_status": {"主要指数": True, "ETF两市成交额趋势": True},
            "step_status": {"主要指数获取": True, "ETF两市成交额趋势获取": True},
            "etf_turnover_series": {
                "available": True,
                "source": "snapshot.etf_turnover_series",
                "rows": [
                    {"trade_date": f"2026-06-{day:02d}", "etf_turnover_yi": 4400 + day}
                    for day in range(1, 26)
                ],
            },
        }

        with patch("replay.report_replay._load_default_mainline_helpers", return_value={}):
            result = build_replay_snapshot_contract(
                "2026-07-29",
                refresh_sources=["noop"],
                load_data_snapshot=lambda target_date: (snapshot, ""),
                tencent_factory=lambda: _FakeTencentFinanceData([]),
                get_major_indices_from_iwencai=lambda target_date="": [],
                safe_float=lambda value: float(value or 0),
                print_fn=lambda *args, **kwargs: None,
                helpers={},
            )

        data = result["data"]
        self.assertFalse(data["data_status"]["ETF两市成交额趋势"])
        self.assertFalse(data["step_status"]["ETF两市成交额趋势获取"])
        log = next(row for row in data["module_logs"] if row.get("step") == "request.etf_turnover_series")
        self.assertEqual(log["status"], "degraded")
        self.assertIn("刷新函数不可用", log["message"])

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
                "get_stock_hot_rank": lambda target_date=None, limit=50: [],
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
        self.assertEqual(data["xuangubao_data"], {})
        self.assertEqual(len(data["wanzhu_top10"]), 1)
        self.assertEqual(data["lianban_data"][0]["code"], "601991")
        self.assertEqual(data["lianban_data"][0]["lianban_days"], 1)
        self.assertEqual(data["lianban_data"][0]["sector"], "电力")
        self.assertTrue(data["data_status"]["整合热榜"])
        self.assertFalse(data["data_status"]["选股通盘中异动"])
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
        self.assertEqual(by_step["request.xuangubao"]["status"], "degraded")
        self.assertEqual(by_step["request.xuangubao"]["details"]["plate_count"], 0)
        self.assertEqual(by_step["request.xuangubao"]["details"]["diagnostic_note"], "target_date_news_missing")
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

    def test_build_replay_snapshot_contract_rejects_xuangubao_refresh_without_target_news(self):
        snapshot = {
            "hot_rank_top30": [{"rank": 1, "code": "601991", "name": "大唐发电"}],
            "integrated_hot_list": [{"rank": 1, "code": "601991", "name": "大唐发电"}],
            "xuangubao_data": {
                "xuangubao_news": [],
                "xuangubao_plates": [],
                "xuangubao_limit_up_reasons": [],
                "diagnostics": {"newsflash": "missing token"},
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
            helpers={
                "fetch_xuangubao_data": lambda target_date=None: {
                    "xuangubao_news": [],
                    "xuangubao_plates": [{"name": "当前板块"}],
                    "xuangubao_limit_up_reasons": [{"symbol": "600676.SS"}],
                    "diagnostics": {"newsflash": "missing target-date news"},
                }
            },
        )

        data = result["data"]
        self.assertEqual(data["xuangubao_data"]["xuangubao_plates"], [])
        self.assertEqual(data["xuangubao_data"]["xuangubao_limit_up_reasons"], [])
        self.assertFalse(data["data_status"]["选股通盘中异动"])
        xgb_log = next(log for log in data["module_logs"] if log.get("step") == "request.xuangubao")
        self.assertEqual(xgb_log["status"], "degraded")
        self.assertEqual(xgb_log["details"]["diagnostic_note"], "target_date_news_missing")

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
        self.assertIsNone(result["data"]["recent_sector_turnover_history"][0]["turnover_share_pct"])
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
            helpers={"get_limit_pool_snapshot": lambda target_date: {}},
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
                "get_limit_pool_snapshot": lambda target_date: {},
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

    def test_build_replay_snapshot_contract_keeps_split_cycle_and_daily_attack_labels(self):
        resolved_summary = {
            "current_mainline": "人形机器人",
            "previous_mainline": "半导体",
            "share_trend_label": "逆势试攻",
            "conclusion": "人形机器人只是放量杀跌中的观察主攻线，不按周期主线切换处理",
            "data_text": "近期被记录方向分列：2026-05-20 半导体 13.6%；2026-05-21 人形机器人 2.5%；这些是各自板块点位，不做连续涨跌判断",
            "action_text": "只观察承接，不新增参与",
            "double_mainline_summary": {
                "cycle_mainline": "半导体",
                "daily_attack_line": "人形机器人",
                "relationship": "人形机器人只是放量杀跌中的观察主攻线，不按周期主线处理",
                "tomorrow_action": "只观察承接，不新增参与",
            },
            "mainline_attack_evidence_summary": {
                "attack_state": "confirmed_attack",
                "primary_line": "人形机器人",
                "confirmation_evidence": "人形机器人资金净流入靠前，涨停更集中",
            },
            "turnover_share_trend_rows": [
                {
                    "date": "2026-05-20",
                    "cycle_mainline": "半导体",
                    "daily_attack_line": "半导体",
                    "mainline_turnover": "4050.00亿",
                    "market_turnover": "29764.59亿",
                    "share": "13.61%",
                },
                {
                    "date": "2026-05-21",
                    "cycle_mainline": "半导体",
                    "daily_attack_line": "人形机器人",
                    "mainline_turnover": "880.00亿",
                    "market_turnover": "35072.80亿",
                    "share": "2.51%",
                },
            ],
        }
        snapshot = {
            "market_research_snapshot": {
                "observation": {"turnover": 35072.8},
                "mainline_turnover_summary": dict(resolved_summary),
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
            "mainline_turnover_summary": dict(resolved_summary),
            "indices": [{"code": "sh000001"}],
            "data_status": {"主要指数": True},
            "step_status": {"主要指数获取": True},
            "total_turnover": 35072.8,
        }

        def _unexpected_rebuild(**kwargs):
            raise AssertionError("已拆分的周期主线和当天主攻线不应触发重建")

        result = build_replay_snapshot_contract(
            "2026-05-21",
            refresh_sources=["noop"],
            load_data_snapshot=lambda target_date: (snapshot, ""),
            tencent_factory=lambda: _FakeTencentFinanceData([]),
            get_major_indices_from_iwencai=lambda target_date="": [],
            safe_float=lambda value: float(value or 0),
            print_fn=lambda *args, **kwargs: None,
            helpers={
                "build_mainline_turnover_summary": _unexpected_rebuild,
                "load_recent_mainline_history": (
                    lambda target_date, lookback_days=25, max_scan_days=60: [
                        {"date": "2026-05-20", "primary_mainline": "半导体", "daily_attack_line": "半导体"}
                    ]
                ),
                "load_recent_sector_turnover_history": lambda target_date, sector_name, lookback_days=25: [],
            },
        )

        top_rows = result["data"]["mainline_turnover_summary"]["turnover_share_trend_rows"]
        research_rows = result["data"]["market_research_snapshot"]["mainline_turnover_summary"]["turnover_share_trend_rows"]
        self.assertEqual(top_rows[-1]["cycle_mainline"], "半导体")
        self.assertEqual(top_rows[-1]["daily_attack_line"], "人形机器人")
        self.assertEqual(research_rows[-1]["cycle_mainline"], "半导体")
        self.assertEqual(research_rows[-1]["daily_attack_line"], "人形机器人")

    def test_build_replay_snapshot_contract_passes_tag_snapshot_into_mainline_rebuild(self):
        snapshot = {
            "market_research_snapshot": {
                "observation": {"turnover": 31006.9},
                "realtime_tag_evidence_snapshot": {
                    "adopted_labels": ["国产芯片替代", "AI算力基础设施"],
                    "groups": [
                        {
                            "采用名称": "国产芯片替代",
                            "当日主攻分支": "国产芯片替代",
                            "表层行业名": ["半导体", "元器件"],
                            "关系判断": "父子",
                        },
                        {
                            "采用名称": "AI算力基础设施",
                            "当日主攻分支": "AI算力基础设施",
                            "表层行业名": ["算力租赁"],
                            "关系判断": "分支",
                        },
                    ],
                },
            },
            "realtime_tag_evidence_snapshot": {
                "adopted_labels": ["国产芯片替代", "AI算力基础设施"],
                "groups": [
                    {
                        "采用名称": "国产芯片替代",
                        "当日主攻分支": "国产芯片替代",
                        "表层行业名": ["半导体", "元器件"],
                        "关系判断": "父子",
                    },
                    {
                        "采用名称": "AI算力基础设施",
                        "当日主攻分支": "AI算力基础设施",
                        "表层行业名": ["算力租赁"],
                        "关系判断": "分支",
                    },
                ],
            },
            "current_mainline_history_record": {
                "date": "2026-06-05",
                "primary_mainline": "半导体",
                "leading_line": "半导体",
            },
            "recent_mainline_history": [
                {"date": "2026-05-29", "primary_mainline": "电力", "daily_attack_line": "电力"},
            ],
            "current_sector_turnover_snapshot": {
                "date": "2026-06-05",
                "sector_name": "半导体",
                "sector_turnover": 4154.85,
                "total_turnover": 31006.9,
                "turnover_share_pct": 13.4,
            },
            "recent_sector_turnover_history": [
                {
                    "date": "2026-05-29",
                    "sector_name": "电力",
                    "cycle_mainline": "电力",
                    "daily_attack_line": "电力",
                    "sector_turnover": 296.49,
                    "total_turnover": 33408.58,
                    "turnover_share_pct": 0.9,
                }
            ],
            "mainline_turnover_summary": {
                "current_mainline": "",
                "turnover_share_trend_rows": [],
            },
            "indices": [{"code": "sh000001"}],
            "data_status": {"主要指数": True},
            "step_status": {"主要指数获取": True},
            "total_turnover": 31006.9,
        }
        captured = {}

        def _build_summary(**kwargs):
            captured.update(kwargs)
            snapshot_arg = kwargs.get("realtime_tag_evidence_snapshot") or {}
            return {
                "current_mainline": "",
                "previous_mainline": "电力",
                "share_trend_label": "分化",
                "conclusion": "主线待确认，暂不输出成交额占比结论",
                "double_mainline_summary": {
                    "cycle_mainline": "-",
                    "daily_attack_line": " / ".join(snapshot_arg.get("adopted_labels") or []),
                    "relationship": "当日观察分支，不按周期主线处理",
                    "tomorrow_action": "先看资金是否继续选择",
                },
                "mainline_attack_evidence_summary": {"attack_state": "chaotic_rotation"},
                "turnover_share_trend_rows": [
                    {
                        "date": "2026-06-05",
                        "cycle_mainline": "半导体",
                        "daily_attack_line": " / ".join(snapshot_arg.get("adopted_labels") or []),
                        "mainline_turnover": "4154.85亿",
                        "market_turnover": "31006.90亿",
                        "share": "13.4%",
                    }
                ],
            }

        result = build_replay_snapshot_contract(
            "2026-06-05",
            refresh_sources=["noop"],
            load_data_snapshot=lambda target_date: (snapshot, ""),
            tencent_factory=lambda: _FakeTencentFinanceData([]),
            get_major_indices_from_iwencai=lambda target_date="": [],
            safe_float=lambda value: float(value or 0),
            print_fn=lambda *args, **kwargs: None,
            helpers={
                "build_mainline_turnover_summary": _build_summary,
                "load_recent_mainline_history": (
                    lambda target_date, lookback_days=25, max_scan_days=60: [
                        {"date": "2026-05-29", "primary_mainline": "电力", "daily_attack_line": "电力"}
                    ]
                ),
                "load_recent_sector_turnover_history": lambda target_date, sector_name, lookback_days=25: [],
            },
        )

        self.assertIn("realtime_tag_evidence_snapshot", captured)
        self.assertEqual(captured["realtime_tag_evidence_snapshot"]["adopted_labels"], ["国产芯片替代", "AI算力基础设施"])
        row = result["data"]["mainline_turnover_summary"]["turnover_share_trend_rows"][-1]
        self.assertEqual(row["cycle_mainline"], "半导体")
        self.assertEqual(row["daily_attack_line"], "国产芯片替代 / AI算力基础设施")

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
                "fetch_stock_batch_quote_info": lambda codes, target_date=None: {},
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

    def test_ensure_replay_price_band_style_series_removes_stale_snapshot_when_refresh_returns_unavailable(self):
        stale_rows = [
            {"trade_date": f"2026-05-{day:02d}", "high_price_pct": -1.55, "low_price_pct": -1.87}
            for day in range(3, 28)
        ]
        snapshot = {
            "indices": [{"code": "sh000001"}],
            "price_band_style_series": {
                "available": True,
                "source": "storage.price_band_style_daily.recent_window",
                "rows": stale_rows,
            },
            "data_status": {"主要指数": True, "价格带风格趋势": True},
            "step_status": {"主要指数获取": True, "价格带风格趋势获取": True},
            "module_logs": [],
        }

        result = _ensure_replay_price_band_style_series(
            snapshot,
            "2026-06-05",
            safe_float=lambda value: float(value or 0),
            helpers={
                "get_price_band_style_series_from_tushare": lambda target_date: {
                    "available": False,
                    "status": "stale_recent_window",
                    "source": "storage.price_band_style_daily.recent_window",
                    "requested_trade_date": "2026-06-05",
                    "latest_trade_date": "2026-05-27",
                    "rows": [],
                    "summary": "价格带风格趋势只到 2026-05-27，未覆盖 2026-06-05 附近交易日；关键数据不完整，停止生成。",
                },
            },
        )

        price_band = result["price_band_style_series"]
        self.assertFalse(price_band["available"])
        self.assertEqual(price_band["rows"], [])
        self.assertEqual(price_band["latest_trade_date"], "2026-05-27")
        self.assertFalse(result["data_status"]["价格带风格趋势"])
        self.assertFalse(result["step_status"]["价格带风格趋势获取"])
        by_step = {item.get("step"): item for item in result.get("module_logs", [])}
        self.assertEqual(by_step["request.price_band_style_series"]["status"], "degraded")

    def test_ensure_replay_price_band_style_series_rejects_nonempty_stale_refresh_rows(self):
        stale_rows = [
            {"trade_date": f"2026-05-{day:02d}", "high_price_pct": -1.55, "low_price_pct": -1.87}
            for day in range(3, 28)
        ]
        snapshot = {
            "indices": [{"code": "sh000001"}],
            "price_band_style_series": {
                "available": True,
                "source": "storage.price_band_style_daily.recent_window",
                "rows": stale_rows,
            },
            "data_status": {"主要指数": True, "价格带风格趋势": True},
            "step_status": {"主要指数获取": True, "价格带风格趋势获取": True},
            "module_logs": [],
        }

        result = _ensure_replay_price_band_style_series(
            snapshot,
            "2026-06-05",
            safe_float=lambda value: float(value or 0),
            helpers={
                "get_price_band_style_series_from_tushare": lambda target_date: {
                    "available": True,
                    "source": "storage.price_band_style_daily.recent_window",
                    "requested_trade_date": "2026-06-05",
                    "latest_trade_date": "2026-05-27",
                    "rows": stale_rows,
                    "summary": "最近可用窗口（截至2026-05-27）：近25个交易日价格带风格。",
                },
            },
        )

        price_band = result["price_band_style_series"]
        self.assertFalse(price_band["available"])
        self.assertEqual(price_band["rows"], [])
        self.assertEqual(price_band["latest_trade_date"], "2026-05-27")
        self.assertFalse(result["data_status"]["价格带风格趋势"])
        self.assertFalse(result["step_status"]["价格带风格趋势获取"])
        by_step = {item.get("step"): item for item in result.get("module_logs", [])}
        self.assertEqual(by_step["request.price_band_style_series"]["status"], "degraded")

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
        self.assertIn("近25个交易日小周期成交额记录", result["data"]["mainline_turnover_summary"]["turnover_share_trend_summary"])
        self.assertIn("不作为大周期主线切换确认", result["data"]["mainline_turnover_summary"]["turnover_share_trend_summary"])

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
            "market_stats": {
                "up_count": 2600,
                "down_count": 2100,
                "flat_count": 120,
                "stock_count": 4820,
                "zt_count": 0,
                "dt_count": 0,
                "trade_date": "2026-05-13",
            },
            "wind_a_alternative": {"price": 0.0, "data_source": "akshare.stock_zh_index_daily_em"},
            "csi1000_index": {
                "name": "中证1000",
                "code": "000852",
                "price": 6123.45,
                "change_pct": 1.1,
                "data_source": "tushare.index_daily",
                "trade_date": "2026-05-13",
            },
            "hot_rank_top50": [
                {
                    "rank": index,
                    "code": f"{index:06d}",
                    "name": f"目标日热榜样本{index}",
                    "data_source": "postgresql.daily_report_facts",
                    "trade_date": "2026-05-13",
                }
                for index in range(1, 51)
            ],
            "hot_rank_sample_size": 50,
            "hot_rank_sample_target": 50,
            **_minimal_sector_first_preflight_inputs("2026-05-13"),
            "data_status": {
                "两市成交额": False,
                "主要指数": True,
                "中证全指": False,
                "中证1000": True,
                "成交额排名": False,
                "大盘涨跌统计": True,
                "涨停池": True,
                "跌停池": True,
                "选股通盘中异动": True,
            },
            "step_status": {
                "两市成交额获取": False,
                "主要指数获取": True,
                "中证全指获取": False,
                "中证1000获取": True,
                "成交额排名获取": False,
                "涨停跌停数据获取": True,
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
                    "module": "domains.market_state.request",
                    "step": "request.csi1000",
                    "status": "success",
                    "message": "已获取中证1000",
                    "details": {"provider": "tushare.index_daily", "price": 6123.45},
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
                "get_lhb_snapshot_from_tushare": _target_date_lhb_snapshot,
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
        self.assertEqual(degraded_steps, ["request.wind_a", "request.stock_quotes"])
        stock_quote_log = next(item for item in data["module_logs"] if item.get("step") == "request.stock_quotes")
        self.assertEqual(stock_quote_log["status"], "degraded")
        self.assertEqual(stock_quote_log["details"]["provider"], "snapshot.stock_full_info")
        preflight = build_report_preflight(data, "2026-05-13")
        self.assertEqual(preflight["failures"], ["中证全指"])

    def test_build_replay_snapshot_contract_restores_market_breadth_from_fact_db(self):
        snapshot = {
            "indices": [{"code": "sh000001"}],
            "total_turnover": 29873.26,
            "turnover_rank": [{"code": "300308", "data_source": "tushare.daily"}],
            "wind_a_alternative": {"price": 6480.47, "data_source": "tushare.index_daily"},
            "market_stats": {"up_count": 0, "down_count": 0, "zt_count": 102, "dt_count": 8},
            "hot_rank_top50": [{"rank": index, "code": f"{index:06d}"} for index in range(1, 51)],
            "hot_rank_sample_size": 50,
            "hot_rank_sample_target": 50,
            "data_status": {
                "两市成交额": True,
                "主要指数": True,
                "中证全指": True,
                "成交额排名": True,
                "大盘涨跌统计": True,
                "热度前50个股": True,
            },
            "step_status": {
                "两市成交额获取": True,
                "主要指数获取": True,
                "中证全指获取": True,
                "成交额排名获取": True,
                "涨停跌停数据获取": True,
                "热度前50个股获取": True,
                "选股通盘中异动获取": True,
            },
            "module_logs": [
                {"module": "domains.market_state.request", "step": "request.total_turnover", "status": "success", "details": {"provider": "tushare.daily"}},
                {"module": "domains.market_state.request", "step": "request.wind_a", "status": "success", "details": {"provider": "tushare.index_daily"}},
                {"module": "domains.market_activity.request", "step": "request.turnover_rank", "status": "success", "details": {"provider": "tushare.daily", "row_count": 50}},
                {
                    "module": "domains.market_activity.request",
                    "step": "request.market_stats",
                    "status": "degraded",
                    "message": "大盘涨跌统计接口异常，使用涨跌停池数量补足",
                    "details": {"provider": "akshare.stock_market_activity_legu", "zt_count": 102, "dt_count": 8},
                },
            ],
            "xuangubao_data": {"xuangubao_news": [{"title": "今日新闻"}]},
        }

        hot_rank_calls = []

        def _date_safe_hot_rank(*, target_date=None, limit=50):
            hot_rank_calls.append((target_date, limit))
            return hot_rank_rows[:limit]

        result = build_replay_snapshot_contract(
            "2026-05-28",
            refresh_sources=["noop"],
            load_data_snapshot=lambda target_date: (snapshot, ""),
            tencent_factory=lambda: _FakeTencentFinanceData([]),
            get_major_indices_from_iwencai=lambda target_date="": [],
            safe_float=lambda value: float(value or 0),
            print_fn=lambda *args, **kwargs: None,
            helpers={
                "get_market_daily_total_from_fact_db": lambda target_date: {},
                "get_turnover_rank_from_fact_db": lambda target_date, limit=50: [],
                "get_wind_a_from_tushare": lambda target_date: {},
                "get_market_breadth_from_fact_db": lambda target_date: {
                    "trade_date": target_date,
                    "stock_count": 5506,
                    "up_count": 3018,
                    "down_count": 2365,
                    "flat_count": 123,
                },
            },
        )

        data = result["data"]
        self.assertEqual(data["market_stats"]["up_count"], 3018)
        self.assertEqual(data["market_stats"]["down_count"], 2365)
        self.assertEqual(data["market_stats"]["flat_count"], 123)
        self.assertTrue(data["data_status"]["大盘涨跌统计"])
        by_step = {item["step"]: item for item in data["module_logs"] if item.get("step") == "request.market_stats"}
        self.assertEqual(by_step["request.market_stats"]["status"], "success")
        self.assertEqual(by_step["request.market_stats"]["details"]["provider"], "storage.stock_daily_quotes_recent.breadth")
        preflight = build_report_preflight(data, "2026-05-28")
        self.assertNotIn("大盘涨跌统计", preflight["failures"])

    def test_replay_market_breadth_refetches_undated_counts_and_preserves_source_dates(self):
        calls = []
        snapshot = {
            "market_stats": {"up_count": 2600, "down_count": 2100},
            "data_status": {"大盘涨跌统计": True},
        }

        result = _ensure_replay_market_breadth(
            snapshot,
            "2026-05-28",
            lambda value: float(value or 0),
            helpers={
                "get_market_breadth_from_fact_db": lambda target_date: calls.append(target_date)
                or {
                    "trade_date": target_date,
                    "source_date": target_date,
                    "query_date": "2026-07-13",
                    "stock_count": 5506,
                    "up_count": 3018,
                    "down_count": 2365,
                    "flat_count": 123,
                }
            },
        )

        self.assertEqual(calls, ["2026-05-28"])
        self.assertEqual(result["market_stats"]["up_count"], 3018)
        self.assertEqual(result["market_stats"]["trade_date"], "2026-05-28")
        self.assertEqual(result["market_stats"]["source_date"], "2026-05-28")
        self.assertEqual(result["market_stats"]["query_date"], "2026-07-13")

    def test_build_replay_snapshot_contract_refills_short_hot_rank_to_top50(self):
        snapshot = {
            "indices": [{"code": "sh000001"}],
            "total_turnover": 29873.26,
            "turnover_rank": [{"code": "300308", "data_source": "tushare.daily"}],
            "wind_a_alternative": {"price": 6480.47, "data_source": "tushare.index_daily"},
            "market_stats": {"up_count": 3018, "down_count": 2365},
            "hot_rank_top30": [{"rank": index, "code": f"{index:06d}", "name": f"热股{index}", "concepts": ["CPO"]} for index in range(1, 31)],
            "hot_rank_sample_size": 30,
            "hot_rank_sample_target": 50,
            "integrated_hot_list": [],
            "tag_distribution": {},
            "data_status": {
                "两市成交额": True,
                "主要指数": True,
                "中证全指": True,
                "成交额排名": True,
                "大盘涨跌统计": True,
                "热度前50个股": False,
                "整合热榜": False,
            },
            "step_status": {
                "两市成交额获取": True,
                "主要指数获取": True,
                "中证全指获取": True,
                "成交额排名获取": True,
                "涨停跌停数据获取": True,
                "热度前50个股获取": False,
                "整合热榜获取": False,
                "选股通盘中异动获取": True,
            },
            "module_logs": [
                {"module": "domains.market_state.request", "step": "request.total_turnover", "status": "success", "details": {"provider": "tushare.daily"}},
                {"module": "domains.market_state.request", "step": "request.wind_a", "status": "success", "details": {"provider": "tushare.index_daily"}},
                {"module": "domains.market_activity.request", "step": "request.turnover_rank", "status": "success", "details": {"provider": "tushare.daily", "row_count": 50}},
                {
                    "module": "domains.market_activity.request",
                    "step": "request.hot_rank.primary",
                    "status": "degraded",
                    "message": "热榜样本不足",
                    "details": {"provider": "同花顺热榜", "hot_rank_count": 30, "required_count": 50},
                },
            ],
            "xuangubao_data": {"xuangubao_news": [{"title": "今日新闻"}]},
        }

        hot_rank_rows = [
            {"rank": index, "code": f"{index:06d}", "name": f"热股{index}", "concepts": ["CPO"] if index <= 4 else ["电力"]}
            for index in range(1, 51)
        ]
        hot_rank_calls = []

        def _date_safe_hot_rank(*, target_date=None, limit=50):
            hot_rank_calls.append((target_date, limit))
            return hot_rank_rows[:limit]

        result = build_replay_snapshot_contract(
            "2026-05-28",
            refresh_sources=["noop"],
            load_data_snapshot=lambda target_date: (snapshot, ""),
            tencent_factory=lambda: _FakeTencentFinanceData([]),
            get_major_indices_from_iwencai=lambda target_date="": [],
            safe_float=lambda value: float(value or 0),
            print_fn=lambda *args, **kwargs: None,
            helpers={
                "get_market_daily_total_from_fact_db": lambda target_date: {},
                "get_turnover_rank_from_fact_db": lambda target_date, limit=50: [],
                "get_wind_a_from_tushare": lambda target_date: {},
                "get_stock_hot_rank": _date_safe_hot_rank,
            },
        )

        data = result["data"]
        self.assertEqual(hot_rank_calls, [("2026-05-28", 50)])
        self.assertEqual(len(data["hot_rank_top50"]), 50)
        self.assertEqual(data["hot_rank_sample_size"], 50)
        self.assertTrue(data["data_status"]["热度前50个股"])
        self.assertTrue(data["step_status"]["热度前50个股获取"])
        self.assertEqual(data["tag_distribution"]["CPO"], 4)
        self.assertEqual(len(data["integrated_hot_list"]), 50)
        by_step = {
            item["step"]: item
            for item in data["module_logs"]
            if item.get("step") in {"request.hot_rank.primary", "request.integrated_hot_rank"}
        }
        self.assertEqual(by_step["request.hot_rank.primary"]["status"], "success")
        self.assertEqual(by_step["request.hot_rank.primary"]["details"]["hot_rank_count"], 50)
        self.assertEqual(by_step["request.integrated_hot_rank"]["details"]["integrated_count"], 50)
        preflight = build_report_preflight(data, "2026-05-28")
        self.assertNotIn("热度前50个股", preflight["failures"])

    def test_build_replay_snapshot_contract_does_not_refill_hot_rank_without_date_safe_helper(self):
        snapshot = {
            "indices": [{"code": "sh000001"}],
            "total_turnover": 29873.26,
            "turnover_rank": [{"code": "300308", "data_source": "tushare.daily"}],
            "wind_a_alternative": {"price": 6480.47, "data_source": "tushare.index_daily"},
            "market_stats": {"up_count": 3018, "down_count": 2365},
            "hot_rank_top30": [
                {"rank": index, "code": f"{index:06d}", "name": f"热股{index}", "concepts": ["CPO"]}
                for index in range(1, 31)
            ],
            "hot_rank_sample_size": 30,
            "hot_rank_sample_target": 50,
            "integrated_hot_list": [],
            "tag_distribution": {},
            "data_status": {
                "两市成交额": True,
                "主要指数": True,
                "中证全指": True,
                "成交额排名": True,
                "大盘涨跌统计": True,
                "热度前50个股": False,
                "整合热榜": False,
            },
            "step_status": {
                "两市成交额获取": True,
                "主要指数获取": True,
                "中证全指获取": True,
                "成交额排名获取": True,
                "涨停跌停数据获取": True,
                "热度前50个股获取": False,
                "整合热榜获取": False,
                "选股通盘中异动获取": True,
            },
            "module_logs": [],
            "xuangubao_data": {"xuangubao_news": [{"title": "今日新闻"}]},
        }

        result = build_replay_snapshot_contract(
            "2026-05-28",
            refresh_sources=["noop"],
            load_data_snapshot=lambda target_date: (snapshot, ""),
            tencent_factory=lambda: _FakeTencentFinanceData([]),
            get_major_indices_from_iwencai=lambda target_date="": [],
            safe_float=lambda value: float(value or 0),
            print_fn=lambda *args, **kwargs: None,
            helpers={
                "get_market_daily_total_from_fact_db": lambda target_date: {},
                "get_turnover_rank_from_fact_db": lambda target_date, limit=50: [],
                "get_wind_a_from_tushare": lambda target_date: {},
            },
        )

        data = result["data"]
        self.assertNotIn("hot_rank_top50", data)
        self.assertEqual(data["hot_rank_sample_size"], 30)
        self.assertEqual(data["hot_rank_sample_target"], 50)
        self.assertFalse(data["data_status"]["热度前50个股"])
        by_step = {item["step"]: item for item in data["module_logs"] if item.get("step") == "request.hot_rank.primary"}
        self.assertEqual(by_step["request.hot_rank.primary"]["status"], "degraded")
        self.assertEqual(by_step["request.hot_rank.primary"]["details"]["provider"], "target_date_hot_rank_only")

    def test_build_replay_snapshot_contract_rejects_legacy_current_hot_rank_helper(self):
        snapshot = {
            "indices": [{"code": "sh000001"}],
            "total_turnover": 29873.26,
            "turnover_rank": [{"code": "300308", "data_source": "tushare.daily"}],
            "wind_a_alternative": {"price": 6480.47, "data_source": "tushare.index_daily"},
            "market_stats": {"up_count": 3018, "down_count": 2365},
            "hot_rank_top30": [
                {"rank": index, "code": f"{index:06d}", "name": f"热股{index}", "concepts": ["CPO"]}
                for index in range(1, 31)
            ],
            "hot_rank_sample_size": 30,
            "hot_rank_sample_target": 50,
            "integrated_hot_list": [],
            "tag_distribution": {},
            "data_status": {
                "两市成交额": True,
                "主要指数": True,
                "中证全指": True,
                "成交额排名": True,
                "大盘涨跌统计": True,
                "热度前50个股": False,
                "整合热榜": False,
            },
            "step_status": {
                "两市成交额获取": True,
                "主要指数获取": True,
                "中证全指获取": True,
                "成交额排名获取": True,
                "涨停跌停数据获取": True,
                "热度前50个股获取": False,
                "整合热榜获取": False,
                "选股通盘中异动获取": True,
            },
            "module_logs": [],
            "xuangubao_data": {"xuangubao_news": [{"title": "今日新闻"}]},
        }
        calls = []

        def _legacy_current_hot_rank(num=50):
            calls.append(num)
            return [
                {"rank": index, "code": f"{index:06d}", "name": f"当前热股{index}"}
                for index in range(1, 51)
            ]

        result = build_replay_snapshot_contract(
            "2026-05-28",
            refresh_sources=["noop"],
            load_data_snapshot=lambda target_date: (snapshot, ""),
            tencent_factory=lambda: _FakeTencentFinanceData([]),
            get_major_indices_from_iwencai=lambda target_date="": [],
            safe_float=lambda value: float(value or 0),
            print_fn=lambda *args, **kwargs: None,
            helpers={
                "get_market_daily_total_from_fact_db": lambda target_date: {},
                "get_turnover_rank_from_fact_db": lambda target_date, limit=50: [],
                "get_wind_a_from_tushare": lambda target_date: {},
                "get_stock_hot_rank": _legacy_current_hot_rank,
            },
        )

        data = result["data"]
        self.assertEqual(calls, [])
        self.assertNotIn("hot_rank_top50", data)
        self.assertEqual(data["hot_rank_sample_size"], 30)
        by_step = {item["step"]: item for item in data["module_logs"] if item.get("step") == "request.hot_rank.primary"}
        self.assertEqual(by_step["request.hot_rank.primary"]["status"], "degraded")
        self.assertEqual(by_step["request.hot_rank.primary"]["details"]["provider"], "target_date_hot_rank_only")

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
                        "trade_date": target_date,
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

    def test_replay_stock_quotes_refresh_all_report_stock_sources(self):
        snapshot = {
            "stock_full_info": {},
            "hot_rank_top50": [{"rank": 46, "code": "sh600255", "name": "鑫科材料", "rate": 12155000}],
            "hot_rank_top30": [],
            "lhb_net_buy_top10": [],
            "lhb_net_sell_top10": [],
            "lianban_data": [],
            "display_observation_candidates": [{"code": "001896", "name": "豫能控股"}],
            "module_logs": [],
        }
        captured_codes = []

        data = _ensure_replay_stock_quotes(
            snapshot,
            "2026-06-08",
            helpers={
                "fetch_stock_batch_quote_info": lambda codes, target_date: (
                    captured_codes.extend(sorted(codes))
                    or {
                        "001896": {
                            "name": "豫能控股",
                            "change_pct": -1.41,
                            "high": 21.50,
                            "low": 19.00,
                            "open": 19.87,
                            "close": 19.60,
                            "zt_status": "正常",
                            "trade_date": target_date,
                            "data_source": "tushare.daily",
                        },
                        "600255": {
                            "name": "鑫科材料",
                            "change_pct": 2.67,
                            "high": 4.83,
                            "low": 4.30,
                            "open": 4.35,
                            "close": 4.61,
                            "zt_status": "正常",
                            "trade_date": target_date,
                            "data_source": "tushare.daily",
                        }
                    }
                ),
            },
        )

        self.assertEqual(captured_codes, ["001896", "600255"])
        self.assertEqual(data["stock_full_info"]["001896"]["close"], 19.60)
        self.assertEqual(data["stock_full_info"]["600255"]["close"], 4.61)
        self.assertEqual(data["hot_rank_top50"][0]["change_pct"], 2.67)
        self.assertEqual(data["hot_rank_top50"][0]["high"], 4.83)
        self.assertEqual(data["hot_rank_top50"][0]["close"], 4.61)
        self.assertEqual(data["display_observation_candidates"][0]["change_pct"], -1.41)
        self.assertEqual(data["display_observation_candidates"][0]["close"], 19.60)

    def test_replay_stock_quotes_refreshes_incomplete_existing_quote(self):
        snapshot = {
            "stock_full_info": {
                "001896": {
                    "name": "豫能控股",
                    "change_pct": 0,
                    "high": 0,
                    "low": 0,
                    "open": 0,
                    "close": 0,
                    "data_source": "old.snapshot",
                }
            },
            "display_observation_candidates": [{"code": "001896", "name": "豫能控股"}],
            "module_logs": [],
        }
        captured_codes = []

        data = _ensure_replay_stock_quotes(
            snapshot,
            "2026-06-08",
            helpers={
                "fetch_stock_batch_quote_info": lambda codes, target_date: (
                    captured_codes.extend(sorted(codes))
                    or {
                        "001896": {
                            "name": "豫能控股",
                            "change_pct": -1.41,
                            "high": 21.50,
                            "low": 19.00,
                            "open": 19.87,
                            "close": 19.60,
                            "zt_status": "正常",
                            "trade_date": target_date,
                            "data_source": "tushare.daily",
                        }
                    }
                ),
            },
        )

        self.assertEqual(captured_codes, ["001896"])
        self.assertEqual(data["stock_full_info"]["001896"]["change_pct"], -1.41)
        self.assertEqual(data["stock_full_info"]["001896"]["close"], 19.60)
        self.assertEqual(data["display_observation_candidates"][0]["change_pct"], -1.41)
        self.assertEqual(data["display_observation_candidates"][0]["close"], 19.60)

    def test_replay_stock_quotes_rejects_refill_without_target_date_proof(self):
        snapshot = {
            "stock_full_info": {},
            "display_observation_candidates": [{"code": "001896", "name": "豫能控股"}],
            "module_logs": [],
        }

        data = _ensure_replay_stock_quotes(
            snapshot,
            "2026-06-08",
            helpers={
                "fetch_stock_batch_quote_info": lambda codes, target_date: {
                    "001896": {
                        "name": "豫能控股",
                        "change_pct": -1.41,
                        "high": 21.50,
                        "low": 19.00,
                        "open": 19.87,
                        "close": 19.60,
                        "data_source": "tushare.daily",
                    }
                },
            },
        )

        self.assertNotIn("001896", data["stock_full_info"])
        self.assertNotIn("change_pct", data["display_observation_candidates"][0])
        by_step = {
            item["step"]: item
            for item in data["module_logs"]
            if item.get("step") == "request.stock_quotes"
        }
        self.assertEqual(by_step["request.stock_quotes"]["status"], "degraded")
        self.assertEqual(by_step["request.stock_quotes"]["details"]["rejected_codes"], ["001896"])

    def test_replay_stock_quotes_rejects_refill_from_wrong_trade_date(self):
        snapshot = {
            "stock_full_info": {},
            "display_observation_candidates": [{"code": "001896", "name": "豫能控股"}],
            "module_logs": [],
        }

        data = _ensure_replay_stock_quotes(
            snapshot,
            "2026-06-08",
            helpers={
                "fetch_stock_batch_quote_info": lambda codes, target_date: {
                    "001896": {
                        "name": "豫能控股",
                        "change_pct": 3.21,
                        "high": 22.00,
                        "low": 20.00,
                        "open": 20.50,
                        "close": 21.80,
                        "trade_date": "2026-06-09",
                        "data_source": "tushare.daily",
                    }
                },
            },
        )

        self.assertNotIn("001896", data["stock_full_info"])
        self.assertNotIn("change_pct", data["display_observation_candidates"][0])
        by_step = {
            item["step"]: item
            for item in data["module_logs"]
            if item.get("step") == "request.stock_quotes"
        }
        self.assertEqual(by_step["request.stock_quotes"]["status"], "degraded")
        self.assertEqual(by_step["request.stock_quotes"]["details"]["rejected_codes"], ["001896"])

    def test_replay_stock_quotes_without_fetcher_clears_undated_snapshot_quote_fields(self):
        snapshot = {
            "stock_full_info": {
                "001896": {
                    "name": "豫能控股",
                    "change_pct": -1.41,
                    "high": 21.50,
                    "low": 19.00,
                    "open": 19.87,
                    "close": 19.60,
                    "data_source": "old.snapshot",
                }
            },
            "display_observation_candidates": [
                {
                    "code": "001896",
                    "name": "豫能控股",
                    "change_pct": -1.41,
                    "high": 21.50,
                    "low": 19.00,
                    "open": 19.87,
                    "close": 19.60,
                }
            ],
            "module_logs": [],
        }

        data = _ensure_replay_stock_quotes(snapshot, "2026-06-08", helpers={})

        self.assertNotIn("001896", data["stock_full_info"])
        self.assertEqual(data["display_observation_candidates"][0]["name"], "豫能控股")
        self.assertNotIn("change_pct", data["display_observation_candidates"][0])
        self.assertNotIn("close", data["display_observation_candidates"][0])
        by_step = {
            item["step"]: item
            for item in data["module_logs"]
            if item.get("step") == "request.stock_quotes"
        }
        self.assertEqual(by_step["request.stock_quotes"]["status"], "degraded")
        self.assertEqual(by_step["request.stock_quotes"]["details"]["provider"], "snapshot.stock_full_info")
        self.assertEqual(by_step["request.stock_quotes"]["details"]["rejected_codes"], ["001896"])

    def test_replay_stock_quotes_fetcher_error_clears_undated_snapshot_quote_fields(self):
        snapshot = {
            "stock_full_info": {
                "001896": {
                    "name": "豫能控股",
                    "change_pct": -1.41,
                    "high": 21.50,
                    "low": 19.00,
                    "open": 19.87,
                    "close": 19.60,
                    "data_source": "old.snapshot",
                }
            },
            "display_observation_candidates": [
                {
                    "code": "001896",
                    "name": "豫能控股",
                    "change_pct": -1.41,
                    "high": 21.50,
                    "low": 19.00,
                    "open": 19.87,
                    "close": 19.60,
                }
            ],
            "module_logs": [],
        }

        def raise_fetch_error(_codes, _target_date):
            raise RuntimeError("quote source unavailable")

        data = _ensure_replay_stock_quotes(
            snapshot,
            "2026-06-08",
            helpers={"fetch_stock_batch_quote_info": raise_fetch_error},
        )

        self.assertNotIn("001896", data["stock_full_info"])
        self.assertEqual(data["display_observation_candidates"][0]["name"], "豫能控股")
        self.assertNotIn("change_pct", data["display_observation_candidates"][0])
        self.assertNotIn("close", data["display_observation_candidates"][0])
        by_step = {
            item["step"]: item
            for item in data["module_logs"]
            if item.get("step") == "request.stock_quotes"
        }
        self.assertEqual(by_step["request.stock_quotes"]["status"], "degraded")
        self.assertEqual(by_step["request.stock_quotes"]["details"]["rejected_codes"], ["001896"])

    def test_replay_stock_quotes_refreshes_partial_zero_ohlc_and_undated_quote(self):
        snapshot = {
            "stock_full_info": {
                "001896": {
                    "name": "豫能控股",
                    "change_pct": 0.0,
                    "high": 21.50,
                    "low": 19.00,
                    "open": 19.87,
                    "close": 19.60,
                    "data_source": "old.snapshot",
                },
                "002585": {
                    "name": "双星新材",
                    "change_pct": 0.0,
                    "high": 10.50,
                    "low": 9.80,
                    "open": 9.87,
                    "close": 10.20,
                    "trade_date": "2026-06-08",
                    "data_source": "tushare.daily",
                },
                "600255": {
                    "name": "鑫科材料",
                    "change_pct": 0.0,
                    "high": 0,
                    "low": 4.30,
                    "open": 4.35,
                    "close": 4.61,
                    "data_source": "old.snapshot",
                },
            },
            "selected_position_candidate": {"code": "001896", "name": "豫能控股"},
            "display_observation_candidates": [{"code": "002585", "name": "双星新材"}],
            "watch_anchor": {"code": "600255", "name": "鑫科材料"},
            "module_logs": [],
        }
        captured_codes = []

        data = _ensure_replay_stock_quotes(
            snapshot,
            "2026-06-08",
            helpers={
                "fetch_stock_batch_quote_info": lambda codes, target_date: (
                    captured_codes.extend(sorted(codes))
                    or {
                        "001896": {
                            "name": "豫能控股",
                            "change_pct": -1.41,
                            "high": 21.50,
                            "low": 19.00,
                            "open": 19.87,
                            "close": 19.60,
                            "trade_date": "2026-06-08",
                            "data_source": "tushare.daily",
                        },
                        "600255": {
                            "name": "鑫科材料",
                            "change_pct": 2.67,
                            "high": 4.83,
                            "low": 4.30,
                            "open": 4.35,
                            "close": 4.61,
                            "trade_date": "2026-06-08",
                            "data_source": "tushare.daily",
                        }
                    }
                ),
            },
        )

        self.assertEqual(captured_codes, ["001896", "600255"])
        self.assertEqual(data["stock_full_info"]["001896"]["trade_date"], "2026-06-08")
        self.assertEqual(data["stock_full_info"]["002585"]["change_pct"], 0.0)
        self.assertEqual(data["selected_position_candidate"]["close"], 19.60)
        self.assertEqual(data["stock_full_info"]["600255"]["high"], 4.83)
        self.assertEqual(data["watch_anchor"]["change_pct"], 2.67)

    def test_replay_stock_quotes_refreshes_existing_quote_from_wrong_trade_date(self):
        snapshot = {
            "stock_full_info": {
                "001896": {
                    "name": "豫能控股",
                    "change_pct": 3.21,
                    "high": 22.00,
                    "low": 20.00,
                    "open": 20.50,
                    "close": 21.80,
                    "trade_date": "2026-06-09",
                    "data_source": "old.snapshot",
                }
            },
            "selected_position_candidate": {"code": "001896", "name": "豫能控股"},
            "module_logs": [],
        }
        captured = {}

        data = _ensure_replay_stock_quotes(
            snapshot,
            "2026-06-08",
            helpers={
                "fetch_stock_batch_quote_info": lambda codes, target_date: captured.update(
                    {"codes": sorted(codes), "target_date": target_date}
                )
                or {
                    "001896": {
                        "name": "豫能控股",
                        "change_pct": -1.41,
                        "high": 21.50,
                        "low": 19.00,
                        "open": 19.87,
                        "close": 19.60,
                        "trade_date": "2026-06-08",
                        "data_source": "tushare.daily",
                    }
                },
            },
        )

        self.assertEqual(captured, {"codes": ["001896"], "target_date": "2026-06-08"})
        self.assertEqual(data["stock_full_info"]["001896"]["trade_date"], "2026-06-08")
        self.assertEqual(data["selected_position_candidate"]["change_pct"], -1.41)
        self.assertEqual(data["selected_position_candidate"]["close"], 19.60)

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
            helpers={
                "get_limit_pool_snapshot": lambda target_date: {
                    "provider": "tushare.limit_list_ths",
                    "zt_pool": [
                        {
                            "代码": "000006",
                            "名称": "深振业A",
                            "所属行业": "房地产",
                            "连板数": 2,
                        }
                    ],
                    "dt_pool": [{"代码": "000007", "名称": "全新好", "所属行业": "房地产"}],
                    "limit_up_codes": ["000006"],
                    "market_stats": {
                        "up_count": 2375,
                        "down_count": 3003,
                        "zt_count": 99,
                        "dt_count": 88,
                    },
                }
            },
        )

        data = result["data"]
        self.assertEqual(data["zt_pool"][0]["代码"], "000988")
        self.assertEqual(data["limit_up_codes"], ["000988"])
        self.assertEqual(data["dt_pool"][0]["代码"], "000007")
        self.assertEqual(data["market_stats"]["up_count"], 2375)
        self.assertEqual(data["market_stats"]["down_count"], 3003)
        self.assertEqual(data["market_stats"]["zt_count"], 1)
        self.assertEqual(data["market_stats"]["dt_count"], 1)
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
        pool_log = next(item for item in data["module_logs"] if item.get("step") == "request.pool_snapshot")
        self.assertNotIn("zt_pool", pool_log["details"]["target_keys"])
        self.assertIn("zt_pool", pool_log["details"]["preserved_keys"])
        self.assertIn("dt_pool", pool_log["details"]["target_keys"])
        self.assertIn("market_stats", pool_log["details"]["target_keys"])

    def test_replay_normalizes_frozen_brain_computer_sector_derivatives(self):
        snapshot = {
            "zt_pool": [
                {
                    "代码": "002195",
                    "名称": "岩山科技",
                    "所属行业": "软件服务",
                    "涨停统计": "脑机接口+AI大模型+AI PC+人形机器人",
                },
                {
                    "代码": "002173",
                    "名称": "创新医疗",
                    "所属行业": "医疗保健",
                    "涨停统计": "脑机接口+医疗器械注册证+医疗服务",
                },
                {
                    "代码": "000988",
                    "名称": "华工科技",
                    "所属行业": "HS",
                    "涨停统计": "光模块放量涨停",
                },
            ],
            "zt_pool_by_sector": {
                "软件服务": [{"code": "002195", "name": "岩山科技"}],
                "医疗保健": [{"code": "002173", "name": "创新医疗"}],
                "光通信": [
                    {
                        "code": "000988",
                        "name": "华工科技",
                        "zt_type": "光模块放量涨停",
                        "frozen_source": "目标日快照",
                    }
                ],
            },
            "lianban_data": [
                {"code": "002195", "name": "岩山科技", "sector": "软件服务", "lianban_days": 1},
                {"code": "002173", "name": "创新医疗", "sector": "医疗保健", "lianban_days": 1},
                {
                    "code": "000988",
                    "name": "华工科技",
                    "sector": "光通信",
                    "lianban_days": 1,
                    "reason": "光模块放量涨停",
                },
            ],
            "xuangubao_data": {
                "xuangubao_limit_up_reasons": [
                    {
                        "symbol": "002195.SZ",
                        "stock_reason": "脑机接口+AI大模型+AI PC+人形机器人",
                        "related_plates": [{"plate_name": "脑科学"}],
                    },
                    {
                        "symbol": "002173.SZ",
                        "stock_reason": "运用脑机接口技术帮助偏瘫患者恢复自主控制",
                        "related_plates": [{"plate_name": "脑科学"}],
                    },
                ]
            },
        }
        frozen_huagon_bucket = list(snapshot["zt_pool_by_sector"]["光通信"])
        frozen_huagon_lianban = dict(snapshot["lianban_data"][2])

        self.assertTrue(_normalize_replay_trade_narrative_sectors(snapshot))
        self.assertEqual(
            {row["code"] for row in snapshot["zt_pool_by_sector"]["脑机接口"]},
            {"002195", "002173"},
        )
        self.assertEqual(snapshot["zt_pool_by_sector"]["光通信"], frozen_huagon_bucket)
        self.assertNotIn("HS", snapshot["zt_pool_by_sector"])
        by_code = {row["code"]: row for row in snapshot["lianban_data"]}
        self.assertEqual(by_code["002195"]["sector"], "脑机接口")
        self.assertEqual(by_code["002195"]["raw_sector"], "软件服务")
        self.assertEqual(by_code["002173"]["sector"], "脑机接口")
        self.assertEqual(by_code["002173"]["raw_sector"], "医疗保健")
        self.assertEqual(by_code["000988"], frozen_huagon_lianban)

    def test_replay_limit_pool_backfill_preserves_confirmed_empty_pool(self):
        replay_runtime = self._load_module()
        snapshot = {
            "zt_pool": [{"代码": "000988", "名称": "华工科技", "所属行业": "光通信"}],
            "dt_pool": [],
            "market_stats": {"up_count": 0, "down_count": 0, "zt_count": 1, "dt_count": 0},
            "data_status": {"涨停池": True, "跌停池": True, "大盘涨跌统计": False},
            "step_status": {"涨停跌停数据获取": True},
            "module_logs": [],
        }

        changed = replay_runtime._apply_replay_limit_pool_snapshot(
            snapshot,
            {
                "provider": "tushare.limit_list_ths",
                "zt_pool": [{"代码": "000006", "名称": "深振业A", "所属行业": "房地产"}],
                "dt_pool": [{"代码": "000007", "名称": "全新好", "所属行业": "房地产"}],
                "market_stats": {
                    "up_count": 2375,
                    "down_count": 3003,
                    "zt_count": 99,
                    "dt_count": 88,
                },
            },
            lambda value: float(value or 0),
        )

        self.assertTrue(changed)
        self.assertEqual([row["代码"] for row in snapshot["zt_pool"]], ["000988"])
        self.assertEqual(snapshot["dt_pool"], [])
        self.assertEqual(snapshot["market_stats"]["zt_count"], 1)
        self.assertEqual(snapshot["market_stats"]["dt_count"], 0)
        pool_log = next(item for item in snapshot["module_logs"] if item.get("step") == "request.pool_snapshot")
        self.assertEqual(pool_log["details"]["target_keys"], ["market_stats"])
        self.assertIn("zt_pool", pool_log["details"]["preserved_keys"])
        self.assertIn("dt_pool", pool_log["details"]["preserved_keys"])

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
            "market_stats": {
                "up_count": 2600,
                "down_count": 2100,
                "flat_count": 120,
                "stock_count": 4820,
                "zt_count": 0,
                "dt_count": 0,
                "trade_date": "2026-05-13",
            },
            "csi1000_index": {
                "name": "中证1000",
                "code": "000852",
                "price": 6123.45,
                "change_pct": 1.1,
                "data_source": "tushare.index_daily",
                "trade_date": "2026-05-13",
            },
            "turnover_rank": [{"code": "601318", "data_source": "tushare.daily"}],
            "hot_rank_top50": [
                {
                    "rank": index,
                    "code": f"{index:06d}",
                    "name": f"目标日热榜样本{index}",
                    "data_source": "postgresql.daily_report_facts",
                    "trade_date": "2026-05-13",
                }
                for index in range(1, 51)
            ],
            "hot_rank_sample_size": 50,
            "hot_rank_sample_target": 50,
            **_minimal_sector_first_preflight_inputs("2026-05-13"),
            "data_status": {
                "两市成交额": True,
                "主要指数": True,
                "中证全指": False,
                "中证1000": True,
                "成交额排名": True,
                "大盘涨跌统计": True,
                "涨停池": True,
                "跌停池": True,
                "选股通盘中异动": True,
            },
            "step_status": {
                "两市成交额获取": True,
                "主要指数获取": True,
                "中证全指获取": False,
                "中证1000获取": True,
                "成交额排名获取": True,
                "涨停跌停数据获取": True,
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
                    "module": "domains.market_state.request",
                    "step": "request.csi1000",
                    "status": "success",
                    "message": "已获取中证1000",
                    "details": {"provider": "tushare.index_daily", "price": 6123.45},
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
                "get_lhb_snapshot_from_tushare": _target_date_lhb_snapshot,
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

        def _build_report_outputs(
            data,
            target_date,
            supplementary_perspective="",
            has_personal_positions=False,
            run_mode="frozen",
            position_report_text="",
            persist_runtime_artifacts=True,
            market_language_translation=None,
        ):
            captured["target_date"] = target_date
            captured["run_mode"] = run_mode
            captured["persist_runtime_artifacts"] = persist_runtime_artifacts
            captured["market_language_translation"] = market_language_translation
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

        def prepare_market_language(data, **kwargs):
            captured["prepare_market_language_root"] = Path(kwargs["root_dir"])
            return _replay_market_language_artifact(kwargs["target_date"])

        def write_market_language(artifact, **kwargs):
            captured["write_market_language_root"] = Path(kwargs["root_dir"])
            return {"artifact_path": "/tmp/market-language.json"}

        with TemporaryDirectory() as output_dir, patch("daily_report_render.assert_report_required_facts_complete", return_value={}):
            result = replay_runtime.build_replay_report_outputs_contract(
                "2026-04-23",
                refresh_sources=["noop"],
                load_data_snapshot=lambda target_date: (snapshot, ""),
                tencent_factory=lambda: _FakeTencentFinanceData([]),
                get_major_indices_from_iwencai=lambda target_date="": [],
                safe_float=lambda value: float(value or 0),
                build_report_outputs=_build_report_outputs,
                save_report_outputs=save_report_outputs,
                audit_report=lambda markdown, **kwargs: {
                    "passed": True,
                    "findings": [],
                    "finding_count": 0,
                },
                output_dir=output_dir,
                print_fn=lambda *args, **kwargs: None,
                prepare_market_language_translation_fn=prepare_market_language,
                write_replay_market_language_translation_fn=write_market_language,
                helpers={
                    "load_recent_mainline_history": lambda target_date, lookback_days=25, max_scan_days=60: [],
                    "load_recent_sector_turnover_history": lambda target_date, sector_name, lookback_days=25: [],
                    "has_resolved_mainline_turnover_summary": lambda summary: True,
                },
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
        self.assertFalse(captured["persist_runtime_artifacts"])
        self.assertEqual(captured["market_language_translation"]["analysis_mode"], "replay")
        self.assertEqual(captured["prepare_market_language_root"], ROOT)
        self.assertEqual(captured["write_market_language_root"], ROOT)
        self.assertNotEqual(captured["prepare_market_language_root"], Path(output_dir))
        self.assertEqual(captured["mainline"], "电力")
        self.assertEqual(captured["share_pct"], 2.7)
        self.assertTrue(any(log["step"] == "render.report_outputs" for log in result["module_logs"]))
        self.assertTrue(any(log["step"] == "audit.report_outputs" for log in result["module_logs"]))
        self.assertTrue(any(log["step"] == "save.report_outputs" for log in result["module_logs"]))

    def test_replay_report_outputs_contract_normalizes_simulated_position_and_prepends_timeline(self):
        replay_runtime = self._load_module()
        calls = []
        snapshot = {
            "personal_position_context": {
                "existing_position_summary": {
                    "has_position": True,
                    "name": "长电科技",
                    "code": "600584",
                    "summary": "持有长电科技(600584)，100%仓位",
                    "position_source": "previous_report_target_default_1x",
                }
            },
            "indices": [{"code": "sh000001"}],
            "data_status": {"主要指数": True},
            "step_status": {"主要指数获取": True},
        }
        position_report_text = (
            "| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |\n"
            "|------|------|----------|----------|-------------|------|\n"
            "| Td | 2026-07-10（周五） | 报告日：旧仓进入复核：长电科技(600584) | 长电科技(600584) | Te不新增参与，B2取消 | 只观察，不新增参与 |\n"
            "| Te | 2026-07-13（周一） | 只处理旧仓风险 | 长电科技(600584) | 没有B2；只处理旧仓风险 | 旧仓未修复则继续降风险 |\n\n"
            "# 持仓策略"
        )

        def build_outputs(data, target_date, **kwargs):
            calls.append("build")
            summary = data["personal_position_context"]["existing_position_summary"]
            self.assertTrue(summary["has_position"])
            self.assertFalse(summary["has_pending_position"])
            self.assertEqual(summary["position"], 50.0)
            self.assertEqual(summary["position_pct"], 50.0)
            self.assertEqual(summary["default_position_pct"], 50.0)
            return {REPORT_VARIANT_FULL: "# 完整版"}

        def audit_report(markdown, **kwargs):
            calls.append("audit")
            self.assertIn("## 账户日序表", markdown)
            self.assertIn("长电科技(600584)", markdown)
            self.assertEqual(kwargs["expected_position_summary"]["code"], "600584")
            return {"passed": True, "findings": [], "finding_count": 0}

        def save_outputs(outputs, *args, **kwargs):
            calls.append("save")
            self.assertIn("## 账户日序表", outputs[REPORT_VARIANT_FULL])
            path = Path(kwargs["output_dir"]) / "replay.md"
            path.write_text(outputs[REPORT_VARIANT_FULL], encoding="utf-8")
            return {REPORT_VARIANT_FULL: str(path)}

        def write_market_language(artifact, **kwargs):
            calls.append("write_market_language")
            return {"artifact_path": "/tmp/market-language.json"}

        with TemporaryDirectory() as output_dir, patch("daily_report_render.assert_report_required_facts_complete", return_value={}):
            result = replay_runtime.build_replay_report_outputs_contract(
                "2026-07-10",
                refresh_sources=["noop"],
                load_data_snapshot=lambda target_date: (snapshot, ""),
                tencent_factory=lambda: _FakeTencentFinanceData([]),
                get_major_indices_from_iwencai=lambda target_date="": [],
                safe_float=lambda value: float(value or 0),
                build_report_outputs=build_outputs,
                save_report_outputs=save_outputs,
                audit_report=audit_report,
                output_dir=output_dir,
                position_report_text=position_report_text,
                print_fn=lambda *args, **kwargs: None,
                prepare_market_language_translation_fn=lambda data, **kwargs: _replay_market_language_artifact(kwargs["target_date"]),
                write_replay_market_language_translation_fn=write_market_language,
                helpers={
                    "load_recent_mainline_history": lambda target_date, lookback_days=25, max_scan_days=60: [],
                    "load_recent_sector_turnover_history": lambda target_date, sector_name, lookback_days=25: [],
                    "has_resolved_mainline_turnover_summary": lambda summary: True,
                },
            )

        self.assertTrue(result["found"])
        self.assertEqual(calls, ["build", "audit", "save", "audit", "write_market_language"])

    def test_replay_report_outputs_contract_stops_before_save_when_acceptance_fails(self):
        replay_runtime = self._load_module()
        calls = []
        snapshot = {
            "indices": [{"code": "sh000001"}],
            "data_status": {"主要指数": True},
            "step_status": {"主要指数获取": True},
        }

        def save_outputs(*args, **kwargs):
            calls.append("save")
            raise AssertionError("invalid replay report must not be saved")

        with TemporaryDirectory() as output_dir, patch("daily_report_render.assert_report_required_facts_complete", return_value={}):
            with self.assertRaisesRegex(RuntimeError, "position_inferred_rendered_as_confirmed_holding"):
                replay_runtime.build_replay_report_outputs_contract(
                    "2026-07-10",
                    refresh_sources=["noop"],
                    load_data_snapshot=lambda target_date: (snapshot, ""),
                    tencent_factory=lambda: _FakeTencentFinanceData([]),
                    get_major_indices_from_iwencai=lambda target_date="": [],
                    safe_float=lambda value: float(value or 0),
                    build_report_outputs=lambda *args, **kwargs: {REPORT_VARIANT_FULL: "# 错误日报"},
                    save_report_outputs=save_outputs,
                    audit_report=lambda markdown, **kwargs: {
                        "passed": False,
                        "findings": [
                            {
                                "code": "position_inferred_rendered_as_confirmed_holding",
                                "message": "前日报计划对象被正文写成确认持仓，停止生成",
                            }
                        ],
                        "finding_count": 1,
                    },
                    output_dir=output_dir,
                    print_fn=lambda *args, **kwargs: None,
                    prepare_market_language_translation_fn=lambda data, **kwargs: _replay_market_language_artifact(kwargs["target_date"]),
                    write_replay_market_language_translation_fn=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("market language must not be written")),
                    helpers={
                        "load_recent_mainline_history": lambda target_date, lookback_days=25, max_scan_days=60: [],
                        "load_recent_sector_turnover_history": lambda target_date, sector_name, lookback_days=25: [],
                        "has_resolved_mainline_turnover_summary": lambda summary: True,
                    },
                )

        self.assertEqual(calls, [])

    def test_replay_report_outputs_contract_stops_before_save_when_required_facts_missing(self):
        replay_runtime = self._load_module()
        calls = []
        snapshot = {
            "analysis": {
                "mainline_history_record": {
                    "date": "2026-04-23",
                    "primary_mainline": "电力",
                },
            },
            "indices": [{"code": "sh000001"}],
            "data_status": {"主要指数": True},
            "step_status": {"主要指数获取": True},
        }

        def _build_report_outputs(*args, **kwargs):
            calls.append("build")
            self.assertFalse(kwargs["persist_runtime_artifacts"])
            return {REPORT_VARIANT_FULL: "# 完整版"}

        def _save_report_outputs(*args, **kwargs):
            calls.append("save")
            raise AssertionError("report save should not run")

        with TemporaryDirectory() as output_dir, patch(
            "daily_report_render.assert_report_required_facts_complete",
            side_effect=RuntimeError("2026-04-23 日报关键数据不完整，停止生成：主线证据"),
        ):
            with self.assertRaises(RuntimeError):
                replay_runtime.build_replay_report_outputs_contract(
                    "2026-04-23",
                    refresh_sources=["noop"],
                    load_data_snapshot=lambda target_date: (snapshot, ""),
                    tencent_factory=lambda: _FakeTencentFinanceData([]),
                    get_major_indices_from_iwencai=lambda target_date="": [],
                    safe_float=lambda value: float(value or 0),
                    build_report_outputs=_build_report_outputs,
                    save_report_outputs=_save_report_outputs,
                    output_dir=output_dir,
                    print_fn=lambda *args, **kwargs: None,
                    prepare_market_language_translation_fn=lambda data, **kwargs: _replay_market_language_artifact(kwargs["target_date"]),
                    write_replay_market_language_translation_fn=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("market language must not be written")),
                    helpers={
                        "load_recent_mainline_history": lambda target_date, lookback_days=25, max_scan_days=60: [],
                        "load_recent_sector_turnover_history": lambda target_date, sector_name, lookback_days=25: [],
                        "has_resolved_mainline_turnover_summary": lambda summary: True,
                    },
                )

        self.assertEqual(calls, ["build"])

    def test_replay_report_outputs_contract_does_not_write_market_language_after_final_check_failure(self):
        replay_runtime = self._load_module()
        audit_count = 0
        write_count = 0
        snapshot = {
            "indices": [{"code": "sh000001"}],
            "data_status": {"主要指数": True},
            "step_status": {"主要指数获取": True},
        }

        def audit_report(markdown, **kwargs):
            nonlocal audit_count
            audit_count += 1
            passed = audit_count == 1
            return {
                "passed": passed,
                "findings": [] if passed else [{"code": "saved_report_failed", "message": "保存后检查未通过"}],
                "finding_count": 0 if passed else 1,
            }

        def save_outputs(outputs, target_date, mode, output_dir=None):
            path = Path(output_dir) / "full.md"
            path.write_text(outputs[REPORT_VARIANT_FULL], encoding="utf-8")
            return {REPORT_VARIANT_FULL: str(path)}

        def write_market_language(*args, **kwargs):
            nonlocal write_count
            write_count += 1
            return {}

        with TemporaryDirectory() as output_dir, patch(
            "daily_report_render.assert_report_required_facts_complete",
            return_value={},
        ):
            with self.assertRaisesRegex(RuntimeError, "saved_report_failed"):
                replay_runtime.build_replay_report_outputs_contract(
                    "2026-07-10",
                    refresh_sources=["noop"],
                    load_data_snapshot=lambda target_date: (snapshot, ""),
                    tencent_factory=lambda: _FakeTencentFinanceData([]),
                    get_major_indices_from_iwencai=lambda target_date="": [],
                    safe_float=lambda value: float(value or 0),
                    build_report_outputs=lambda *args, **kwargs: {REPORT_VARIANT_FULL: "# replay"},
                    save_report_outputs=save_outputs,
                    audit_report=audit_report,
                    output_dir=output_dir,
                    print_fn=lambda *args, **kwargs: None,
                    prepare_market_language_translation_fn=lambda data, **kwargs: _replay_market_language_artifact(kwargs["target_date"]),
                    write_replay_market_language_translation_fn=write_market_language,
                    helpers={
                        "load_recent_mainline_history": lambda target_date, lookback_days=25, max_scan_days=60: [],
                        "load_recent_sector_turnover_history": lambda target_date, sector_name, lookback_days=25: [],
                        "has_resolved_mainline_turnover_summary": lambda summary: True,
                    },
                )

        self.assertEqual(audit_count, 2)
        self.assertEqual(write_count, 0)

    def test_replay_report_outputs_contract_rejects_corrupted_saved_markdown(self):
        replay_runtime = self._load_module()
        write_count = 0
        snapshot = {
            "indices": [{"code": "sh000001"}],
            "data_status": {"主要指数": True},
            "step_status": {"主要指数获取": True},
        }

        def save_outputs(_outputs, _target_date, mode=None, output_dir=None):
            path = Path(output_dir) / "full.md"
            path.write_text("# corrupted", encoding="utf-8")
            return {REPORT_VARIANT_FULL: str(path)}

        def write_market_language(*args, **kwargs):
            nonlocal write_count
            write_count += 1
            return {}

        with TemporaryDirectory() as output_dir, patch(
            "daily_report_render.assert_report_required_facts_complete",
            return_value={},
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "保存后的完整版日报与检查通过的正文不一致",
            ):
                replay_runtime.build_replay_report_outputs_contract(
                    "2026-07-10",
                    refresh_sources=["noop"],
                    load_data_snapshot=lambda target_date: (snapshot, ""),
                    tencent_factory=lambda: _FakeTencentFinanceData([]),
                    get_major_indices_from_iwencai=lambda target_date="": [],
                    safe_float=lambda value: float(value or 0),
                    build_report_outputs=lambda *args, **kwargs: {
                        REPORT_VARIANT_FULL: "# replay"
                    },
                    save_report_outputs=save_outputs,
                    audit_report=lambda markdown, **kwargs: {
                        "passed": True,
                        "findings": [],
                        "finding_count": 0,
                    },
                    output_dir=output_dir,
                    print_fn=lambda *args, **kwargs: None,
                    prepare_market_language_translation_fn=lambda data, **kwargs: (
                        _replay_market_language_artifact(kwargs["target_date"])
                    ),
                    write_replay_market_language_translation_fn=write_market_language,
                    helpers={
                        "load_recent_mainline_history": lambda target_date, lookback_days=25, max_scan_days=60: [],
                        "load_recent_sector_turnover_history": lambda target_date, sector_name, lookback_days=25: [],
                        "has_resolved_mainline_turnover_summary": lambda summary: True,
                    },
                )

        self.assertEqual(write_count, 0)


if __name__ == "__main__":
    unittest.main()
