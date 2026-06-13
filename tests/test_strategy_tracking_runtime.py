import subprocess
import sys
import unittest
from contextlib import ExitStack
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

    result = subprocess.run(
        [sys.executable, "-c", stub_setup + "\n" + script_body],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    return result


class StrategyTrackingRuntimeTest(unittest.TestCase):
    def _load_runtime_module(self):
        try:
            return __import__("report.strategy_tracking_runtime", fromlist=["strategy_tracking_runtime"])
        except ModuleNotFoundError as error:
            self.fail(f"report.strategy_tracking_runtime should exist: {error}")

    def test_legacy_strategy_factor_snapshot_wrapper_delegates_to_runtime(self):
        result = _run_legacy_entry_probe(
            """
import daily_report_entry_demo
from unittest.mock import patch

with patch.object(daily_report_entry_demo, "run_build_strategy_factor_snapshot", return_value={"ok": True}) as runtime_mock:
    result = daily_report_entry_demo._build_strategy_factor_snapshot(
        "2026-04-23",
        {"indices": {}},
        {},
        {},
        {},
        "50%条件执行",
        "环境打开",
        {"best_stock": {"name": "军工一号"}},
    )

assert runtime_mock.call_args[0][0] == "2026-04-23"
assert "helpers" in runtime_mock.call_args.kwargs
assert result == {"ok": True}
"""
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_legacy_timer_normalizer_wrapper_delegates_to_runtime(self):
        result = _run_legacy_entry_probe(
            """
import daily_report_entry_demo
from unittest.mock import patch

payload = [("步骤A", 0.1, 0.1)]
with patch.object(daily_report_entry_demo, "run_normalize_report_timer_steps", return_value=payload) as runtime_mock:
    result = daily_report_entry_demo._normalize_report_timer_steps({"steps": []}, {"步骤A": True})

assert runtime_mock.call_args[0][0] == {"steps": []}
assert runtime_mock.call_args[0][1] == {"步骤A": True}
assert result == payload
"""
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_legacy_strategy_performance_book_wrapper_delegates_to_runtime(self):
        result = _run_legacy_entry_probe(
            """
import daily_report_entry_demo
from unittest.mock import patch

payload = {"score": "summary"}
with patch.object(daily_report_entry_demo, "run_update_strategy_performance_book", return_value=payload) as runtime_mock:
    result = daily_report_entry_demo.update_strategy_performance_book(
        {"foo": "bar"},
        "2026-04-23",
        {"plan": "context"},
        {"signal": {"signal_type": "attack"}},
        ledger_mode="replay",
    )

assert runtime_mock.call_args[0][0] == {"foo": "bar"}
assert runtime_mock.call_args[0][1] == "2026-04-23"
assert runtime_mock.call_args[0][2] == {"plan": "context"}
assert runtime_mock.call_args.kwargs["ledger_mode"] == "replay"
assert "helpers" in runtime_mock.call_args.kwargs
assert result == payload
"""
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_strategy_factor_snapshot_runtime_exposes_helper_bindings(self):
        strategy_tracking_runtime = self._load_runtime_module()
        exec(
            """
def _strategy_factor_snapshot_probe(
    target_date,
    data,
    market_zhongshu,
    final_gate,
    exit_analysis,
    position_level,
    position_reason,
    context,
):
    return runtime_test_helper(target_date, position_reason, context.get("best_stock", {}).get("name"))
""",
            strategy_tracking_runtime.__dict__,
        )

        with patch(
            "report.strategy_tracking_runtime._build_strategy_factor_snapshot_legacy_body",
            strategy_tracking_runtime._strategy_factor_snapshot_probe,
        ):
            result = strategy_tracking_runtime.build_strategy_factor_snapshot(
                "2026-04-23",
                {},
                {},
                {},
                {},
                "50%条件执行",
                "环境打开",
                {"best_stock": {"name": "军工一号"}},
                helpers={"runtime_test_helper": lambda target_date, reason, name: (target_date, reason, name)},
            )

        self.assertEqual(result, ("2026-04-23", "环境打开", "军工一号"))

    def test_strategy_plan_context_runtime_exposes_helper_bindings(self):
        strategy_tracking_runtime = self._load_runtime_module()
        exec(
            """
def _strategy_plan_context_probe(
    target_date,
    data,
    market_zhongshu,
    final_gate,
    exit_analysis,
    position_level,
    position_reason,
    best_stock=None,
    watch_anchor=None,
    watch_anchor_type='重点观察谁',
    factor_snapshot=None,
):
    return {
        "anchor": runtime_test_helper(best_stock, watch_anchor, watch_anchor_type),
        "factor": factor_snapshot,
    }
""",
            strategy_tracking_runtime.__dict__,
        )

        with patch(
            "report.strategy_tracking_runtime._build_strategy_plan_context_legacy_body",
            strategy_tracking_runtime._strategy_plan_context_probe,
        ):
            result = strategy_tracking_runtime.build_strategy_plan_context(
                "2026-04-23",
                {},
                {},
                {},
                {},
                "50%条件执行",
                "环境打开",
                best_stock={"name": "军工一号"},
                watch_anchor={"name": "观察对象"},
                watch_anchor_type="继续看谁",
                factor_snapshot={"factor": "snapshot"},
                helpers={
                    "runtime_test_helper": lambda best_stock, watch_anchor, watch_anchor_type: (
                        best_stock.get("name"),
                        watch_anchor.get("name"),
                        watch_anchor_type,
                    )
                },
            )

        self.assertEqual(result["anchor"], ("军工一号", "观察对象", "继续看谁"))
        self.assertEqual(result["factor"], {"factor": "snapshot"})

    def test_strategy_performance_book_runtime_exposes_helper_bindings(self):
        strategy_tracking_runtime = self._load_runtime_module()
        exec(
            """
def _strategy_performance_book_probe(data, target_date, plan_context, market_zhongshu, ledger_mode="frozen"):
    return runtime_test_helper(data, target_date, plan_context, ledger_mode)
""",
            strategy_tracking_runtime.__dict__,
        )

        with patch(
            "report.strategy_tracking_runtime._update_strategy_performance_book_legacy_body",
            strategy_tracking_runtime._strategy_performance_book_probe,
        ):
            result = strategy_tracking_runtime.update_strategy_performance_book(
                {"foo": "bar"},
                "2026-04-23",
                {"plan": "context"},
                {"signal": {"signal_type": "attack"}},
                ledger_mode="replay",
                helpers={
                    "runtime_test_helper": lambda data, target_date, plan_context, ledger_mode: (
                        data.get("foo"),
                        target_date,
                        plan_context.get("plan"),
                        ledger_mode,
                    )
                },
            )

        self.assertEqual(result, ("bar", "2026-04-23", "context", "replay"))


    def test_strategy_tracking_runtime_summary_includes_monitoring_pools(self):
        runtime = self._load_runtime_module()

        original = runtime.__dict__.copy()
        runtime.LEDGER_MODE_FROZEN = "frozen"
        runtime.LEDGER_MODE_REPLAY = "replay"
        runtime.STRATEGY_FACTOR_SNAPSHOT_VERSION = 1
        runtime.load_strategy_performance_ledger = lambda mode=None: {"records": []}
        runtime._backfill_strategy_record_market_context = lambda record: record
        runtime._upsert_strategy_record = lambda ledger, plan_context, allow_overwrite=True: (dict(plan_context), "created")
        runtime.save_factor_snapshot = lambda target_date, factor_snapshot, mode=None: {"path": "", "mode": mode, "version": 1, "saved_at": ""}
        runtime._strategy_record_core_signature = lambda record: ()
        runtime._format_strategy_record_brief = lambda record: "brief"
        runtime._evaluate_single_strategy_record = lambda record, target_date: {}
        runtime._apply_yizi_chain_rules = lambda records: None
        runtime._classify_strategy_record_attribution = lambda record, target_date: {}
        runtime.save_strategy_performance_ledger = lambda ledger, mode=None: None
        runtime._parse_kline_date = lambda value: __import__("datetime").datetime.strptime(value, "%Y-%m-%d")
        runtime._get_run_mode_label = lambda mode: mode
        runtime._prepare_records_for_review = lambda records, target_date: records
        runtime._summarize_strategy_window = lambda records, start_date, end_date: {}
        runtime._summarize_ev_signal_review = lambda records, start_date, end_date: {}
        runtime._summarize_strategy_attribution = lambda records, start_date, end_date: {}
        runtime._summarize_setup_signal_review = lambda records, start_date, end_date: {}
        runtime._summarize_gem_breathing_week_review = lambda records, start_date, end_date: {}
        runtime.build_strategy_ev_calibration = lambda target_date, ledger_mode=None: {}
        runtime._build_self_calibration_summary = lambda *args, **kwargs: {}
        runtime._summarize_structure_cycles = lambda records, target_date: []
        runtime._build_system_graduation_dashboard = lambda *args, **kwargs: {}
        runtime._build_gem_structure_cycle_cards = lambda records, target_date: []
        runtime._build_recent_target_followups = lambda records, target_date: []
        runtime._build_recent_target_review_matrix = lambda current_record, followups: []
        runtime._build_gem_horizontal_compare_cards = lambda cards, matrix: []
        runtime._build_recent_target_reflection = lambda matrix: {}
        runtime.collect_monitoring_pool_candidates = lambda context: {"main_pool": [{"stock_code": "002975"}], "secondary_pool": [{"stock_code": "603026"}]}
        runtime.build_monitoring_pool_summary = lambda context, target_date, helpers=None: {"main_pool": [{"stock_code": "002975"}], "secondary_pool": [{"stock_code": "603026"}]}

        try:
            summary = runtime._update_strategy_performance_book_legacy_body(
                {},
                "2026-04-24",
                {"report_date": "2026-04-24", "stock_name": "博杰股份", "stock_code": "002975"},
                {},
                ledger_mode="frozen",
            )
        finally:
            runtime.__dict__.clear()
            runtime.__dict__.update(original)

        self.assertEqual(summary["monitoring_pool"]["main_pool"][0]["stock_code"], "002975")
        self.assertEqual(summary["monitoring_pool"]["secondary_pool"][0]["stock_code"], "603026")



if __name__ == "__main__":
    unittest.main()
