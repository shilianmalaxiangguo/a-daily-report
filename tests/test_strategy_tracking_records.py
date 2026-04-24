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


class StrategyTrackingRecordsTest(unittest.TestCase):
    def _load_records_module(self):
        try:
            return __import__("report.strategy_tracking_records", fromlist=["strategy_tracking_records"])
        except ModuleNotFoundError as error:
            self.fail(f"report.strategy_tracking_records should exist: {error}")

    def test_legacy_strategy_record_wrappers_delegate_to_records_runtime(self):
        result = _run_legacy_entry_probe(
            """
import daily_report_entry_demo
from unittest.mock import patch

find_payload = {"report_date": "2026-04-23"}
upsert_payload = ({"report_date": "2026-04-23"}, "updated")
prepare_payload = [{"report_date": "2026-04-23"}]

with patch.object(daily_report_entry_demo, "run_find_strategy_record", return_value=find_payload) as find_mock, \
     patch.object(daily_report_entry_demo, "run_upsert_strategy_record", return_value=upsert_payload) as upsert_mock, \
     patch.object(daily_report_entry_demo, "run_prepare_records_for_review", return_value=prepare_payload) as prepare_mock:
    find_result = daily_report_entry_demo._find_strategy_record(
        [{"report_date": "2026-04-23"}],
        "2026-04-23",
    )
    upsert_result = daily_report_entry_demo._upsert_strategy_record(
        {"records": []},
        {"report_date": "2026-04-23"},
        allow_overwrite=False,
    )
    prepare_result = daily_report_entry_demo._prepare_records_for_review(
        [{"report_date": "2026-04-23"}],
        "2026-04-24",
    )

assert find_mock.call_args[0][0] == [{"report_date": "2026-04-23"}]
assert find_mock.call_args[0][1] == "2026-04-23"
assert "helpers" in find_mock.call_args.kwargs
assert upsert_mock.call_args[0][0] == {"records": []}
assert upsert_mock.call_args[0][1] == {"report_date": "2026-04-23"}
assert upsert_mock.call_args.kwargs["allow_overwrite"] is False
assert "helpers" in upsert_mock.call_args.kwargs
assert prepare_mock.call_args[0][0] == [{"report_date": "2026-04-23"}]
assert prepare_mock.call_args[0][1] == "2026-04-24"
assert "helpers" in prepare_mock.call_args.kwargs
assert find_result == find_payload
assert upsert_result == upsert_payload
assert prepare_result == prepare_payload
"""
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_strategy_tracking_records_runtime_exposes_helper_bindings(self):
        records = self._load_records_module()
        exec(
            """
def _prepare_records_probe(records, as_of_date):
    return runtime_test_helper(records, as_of_date)
""",
            records.__dict__,
        )

        with patch(
            "report.strategy_tracking_records._prepare_records_for_review_legacy_body",
            records._prepare_records_probe,
        ):
            result = records.prepare_records_for_review(
                [{"report_date": "2026-04-23"}],
                "2026-04-24",
                helpers={"runtime_test_helper": lambda items, as_of_date: (items[0]["report_date"], as_of_date)},
            )

        self.assertEqual(result, ("2026-04-23", "2026-04-24"))

    def test_find_strategy_record_matches_normalized_report_date(self):
        records = self._load_records_module()

        result = records.find_strategy_record(
            [{"report_date": "2026-04-23"}],
            "2026-04-23 15:00:00",
            helpers={"_normalize_kline_date_str": lambda value: str(value).split()[0] if value else ""},
        )

        self.assertEqual(result["report_date"], "2026-04-23")

    def test_upsert_strategy_record_preserves_existing_simulation_on_overwrite(self):
        records = self._load_records_module()

        ledger = {
            "records": [
                {
                    "report_date": "2026-04-23",
                    "stock_name": "旧样本",
                    "simulation": {"status": "closed"},
                }
            ]
        }

        result_record, write_status = records.upsert_strategy_record(
            ledger,
            {"report_date": "2026-04-23", "stock_name": "新样本"},
        )

        self.assertEqual(write_status, "updated")
        self.assertEqual(result_record["stock_name"], "新样本")
        self.assertEqual(result_record["simulation"], {"status": "closed"})

    def test_merge_strategy_record_sources_uses_override_and_sorts(self):
        records = self._load_records_module()

        merged = records.merge_strategy_record_sources(
            [
                {"report_date": "2026-04-24", "stock_name": "旧B"},
                {"report_date": "2026-04-22", "stock_name": "旧A"},
            ],
            [
                {"report_date": "2026-04-23", "stock_name": "新C"},
                {"report_date": "2026-04-24", "stock_name": "新B"},
            ],
            helpers={"_normalize_kline_date_str": lambda value: value},
        )

        self.assertEqual(
            [(item["report_date"], item["stock_name"]) for item in merged],
            [
                ("2026-04-22", "旧A"),
                ("2026-04-23", "新C"),
                ("2026-04-24", "新B"),
            ],
        )

    def test_summarize_strategy_window_compounds_triggered_records_only(self):
        records = self._load_records_module()

        result = records.summarize_strategy_window(
            [
                {
                    "report_date": "2026-04-22",
                    "action_type": "execute",
                    "simulation": {
                        "triggered": True,
                        "status": "closed",
                        "strategy_return_worst": 0.02,
                        "strategy_return_best": 0.04,
                        "alpha_return_worst": 0.01,
                        "alpha_return_best": 0.03,
                    },
                },
                {
                    "report_date": "2026-04-23",
                    "action_type": "execute",
                    "simulation": {
                        "triggered": False,
                        "status": "not_triggered",
                        "strategy_return_worst": 0.08,
                        "strategy_return_best": 0.10,
                    },
                },
                {
                    "report_date": "2026-04-24",
                    "action_type": "watch_only",
                    "simulation": {"status": "watch_only"},
                },
            ],
            "2026-04-22",
            "2026-04-24",
            helpers={
                "_normalize_kline_date_str": lambda value: value,
                "_compound_returns": lambda values: round(sum(values), 4),
                "fetch_daily_price_bars": lambda *args, **kwargs: [
                    {"date": "2026-04-22", "close": 100.0},
                    {"date": "2026-04-24", "close": 103.0},
                ],
                "_get_first_bar_on_or_after": lambda bars, start_date: bars[0],
                "_get_last_bar_on_or_before": lambda bars, end_date: bars[-1],
                "_safe_float": lambda value: float(value or 0),
            },
        )

        self.assertEqual(result["plan_count"], 3)
        self.assertEqual(result["actionable_count"], 2)
        self.assertEqual(result["triggered_count"], 1)
        self.assertEqual(result["strategy_return_worst"], 0.02)
        self.assertEqual(result["strategy_return_best"], 0.04)
        self.assertAlmostEqual(result["benchmark_return"], 0.03)
        self.assertAlmostEqual(result["alpha_return_worst"], -0.01)
        self.assertAlmostEqual(result["alpha_return_best"], 0.01)
        self.assertEqual(result["positive_alpha_count"], 1)

    def test_prepare_records_for_review_applies_backfill_simulation_and_attribution(self):
        records = self._load_records_module()

        def _apply_yizi_chain_rules(items):
            for item in items:
                item["chain_applied"] = True

        result = records.prepare_records_for_review(
            [
                {"report_date": "2026-04-24", "stock_name": "样本B"},
                {"report_date": "2026-04-22", "stock_name": "样本A"},
            ],
            "2026-04-24",
            helpers={
                "_backfill_strategy_record_market_context": lambda record: {**record, "backfilled": True},
                "_normalize_kline_date_str": lambda value: value,
                "_evaluate_single_strategy_record": lambda record, as_of_date: {"status": f"sim:{record['report_date']}"},
                "_apply_yizi_chain_rules": _apply_yizi_chain_rules,
                "_classify_strategy_record_attribution": lambda record, as_of_date: {"label": f"attr:{record['report_date']}"},
            },
        )

        self.assertEqual([item["report_date"] for item in result], ["2026-04-22", "2026-04-24"])
        self.assertTrue(all(item["backfilled"] for item in result))
        self.assertTrue(all(item["chain_applied"] for item in result))
        self.assertEqual(result[0]["simulation"]["status"], "sim:2026-04-22")
        self.assertEqual(result[0]["attribution"]["label"], "attr:2026-04-22")

    def test_summarize_strategy_window_skips_benchmark_fetch_when_no_actionable_records(self):
        records = self._load_records_module()

        def _unexpected_fetch(*args, **kwargs):
            raise AssertionError("benchmark fetch should not run when there are no actionable execute records")

        result = records.summarize_strategy_window(
            [
                {
                    "report_date": "2026-04-22",
                    "action_type": "no_trade",
                    "simulation": {"status": "no_trade"},
                }
            ],
            "2026-04-22",
            "2026-04-22",
            helpers={
                "_normalize_kline_date_str": lambda value: value,
                "_compound_returns": lambda values: round(sum(values), 4),
                "fetch_daily_price_bars": _unexpected_fetch,
                "_get_first_bar_on_or_after": lambda bars, start_date: None,
                "_get_last_bar_on_or_before": lambda bars, end_date: None,
                "_safe_float": lambda value: float(value or 0),
            },
        )

        self.assertEqual(result["plan_count"], 1)
        self.assertEqual(result["actionable_count"], 0)
        self.assertIsNone(result["benchmark_return"])
        self.assertEqual(result["positive_alpha_count"], 0)


    def test_upsert_strategy_record_preserves_monitoring_fields_on_overwrite(self):
        records = self._load_records_module()

        ledger = {
            "records": [
                {
                    "report_date": "2026-04-23",
                    "stock_name": "旧样本",
                    "monitoring_rows": [{"date": "2026-04-24"}],
                    "source_pool": "main",
                    "tracking_status": "active",
                    "pattern_type": "trend_continuation",
                }
            ]
        }

        result_record, write_status = records.upsert_strategy_record(
            ledger,
            {"report_date": "2026-04-23", "stock_name": "新样本"},
        )

        self.assertEqual(write_status, "updated")
        self.assertEqual(result_record["monitoring_rows"], [{"date": "2026-04-24"}])
        self.assertEqual(result_record["source_pool"], "main")
        self.assertEqual(result_record["tracking_status"], "active")
        self.assertEqual(result_record["pattern_type"], "trend_continuation")


if __name__ == "__main__":
    unittest.main()
