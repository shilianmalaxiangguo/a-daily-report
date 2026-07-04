import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def _m(*parts):
    return "".join(parts)


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


class StrategyTrackingFollowupsTest(unittest.TestCase):
    def _load_followups_module(self):
        try:
            return __import__("report.strategy_tracking_followups", fromlist=["strategy_tracking_followups"])
        except ModuleNotFoundError as error:
            self.fail(f"report.strategy_tracking_followups should exist: {error}")

    def test_legacy_recent_target_followups_wrapper_delegates_to_runtime(self):
        result = _run_legacy_entry_probe(
            """
import daily_report_entry_demo
from unittest.mock import patch

payload = [{"sample_label": "军工一号(000001)"}]
with patch.object(daily_report_entry_demo, "run_build_recent_target_followups", return_value=payload) as runtime_mock:
    result = daily_report_entry_demo._build_recent_target_followups(
        [{"report_date": "2026-04-22"}],
        "2026-04-23",
        limit=2,
    )

assert runtime_mock.call_args[0][0] == [{"report_date": "2026-04-22"}]
assert runtime_mock.call_args[0][1] == "2026-04-23"
assert runtime_mock.call_args.kwargs["limit"] == 2
assert "helpers" in runtime_mock.call_args.kwargs
assert result == payload
"""
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_legacy_recent_target_review_wrappers_delegate_to_runtime(self):
        result = _run_legacy_entry_probe(
            """
import daily_report_entry_demo
from unittest.mock import patch

reflection_payload = {"headline": "ok"}
review_matrix_payload = [{"sample_label": "样本A"}]
compare_cards_payload = [{"sample_label": "样本B"}]

with patch.object(daily_report_entry_demo, "run_build_recent_target_reflection", return_value=reflection_payload) as reflection_mock, \
     patch.object(daily_report_entry_demo, "run_build_recent_target_review_matrix", return_value=review_matrix_payload) as review_mock, \
     patch.object(daily_report_entry_demo, "run_build_gem_horizontal_compare_cards", return_value=compare_cards_payload) as compare_mock:
    reflection_result = daily_report_entry_demo._build_recent_target_reflection(
        [{"system_fix": "观察链不要偷写成执行链"}]
    )
    review_result = daily_report_entry_demo._build_recent_target_review_matrix(
        {"stock_code": "000001"},
        [{"sample_label": "军工一号(000001)"}],
        limit=3,
    )
    compare_result = daily_report_entry_demo._build_gem_horizontal_compare_cards(
        [{"sample_label": "20cm样本A"}],
        [{"sample_label": "参考样本"}],
        limit=1,
    )

assert reflection_mock.call_args[0][0] == [{"system_fix": "观察链不要偷写成执行链"}]
assert "helpers" in reflection_mock.call_args.kwargs
assert review_mock.call_args[0][0] == {"stock_code": "000001"}
assert review_mock.call_args[0][1] == [{"sample_label": "军工一号(000001)"}]
assert review_mock.call_args.kwargs["limit"] == 3
assert "helpers" in review_mock.call_args.kwargs
assert compare_mock.call_args.kwargs["gem_cycle_cards"] == [{"sample_label": "20cm样本A"}]
assert compare_mock.call_args.kwargs["review_matrix"] == [{"sample_label": "参考样本"}]
assert compare_mock.call_args.kwargs["limit"] == 1
assert "helpers" in compare_mock.call_args.kwargs
assert reflection_result == reflection_payload
assert review_result == review_matrix_payload
assert compare_result == compare_cards_payload
"""
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_recent_target_followups_runtime_exposes_helper_bindings(self):
        followups = self._load_followups_module()
        exec(
            """
def _recent_target_followups_probe(records, as_of_date, limit=3):
    return runtime_test_helper(records, as_of_date, limit)
""",
            followups.__dict__,
        )

        with patch(
            "report.strategy_tracking_followups._build_recent_target_followups_legacy_body",
            followups._recent_target_followups_probe,
        ):
            result = followups.build_recent_target_followups(
                [{"report_date": "2026-04-22"}],
                "2026-04-23",
                limit=2,
                helpers={"runtime_test_helper": lambda records, as_of_date, limit: (records[0]["report_date"], as_of_date, limit)},
            )

        self.assertEqual(result, ("2026-04-22", "2026-04-23", 2))

    def test_recent_target_followup_item_normalizes_as_of_date_before_fetching_bars(self):
        followups = self._load_followups_module()
        captured = {}

        def _fetch_daily_price_bars(code, start_date, end_date, is_index=False):
            captured["end_date"] = end_date
            return [{"date": "2026-04-23", "close": 10.0, "high": 10.3, "low": 9.8}]

        with patch.multiple(
            followups,
            normalize_stock_code=lambda value: value,
            _normalize_kline_date_str=lambda value: str(value).split()[0] if value else "",
            _count_trading_days_between=lambda start_date, end_date: 2,
            fetch_daily_price_bars=_fetch_daily_price_bars,
            _get_last_bar_on_or_before=lambda bars, as_of_date: bars[-1],
            _safe_float=lambda value: float(value or 0),
            _round_or_none=lambda value: value,
            _collect_record_market_path=lambda record, as_of_date: {},
            create=True,
        ):
            followups._build_recent_target_followup_item(
                {
                    "stock_code": "000001",
                    "stock_name": "样本股",
                    "report_date": "2026-04-22",
                },
                "2026-04-23 15:00:00",
            )

        self.assertEqual(captured["end_date"], "2026-04-23")

    def test_recent_target_followup_item_skips_samples_outside_tracking_window(self):
        followups = self._load_followups_module()

        with patch.multiple(
            followups,
            normalize_stock_code=lambda value: value,
            _normalize_kline_date_str=lambda value: str(value).split()[0] if value else "",
            _count_trading_days_between=lambda start_date, end_date: 7,
            fetch_daily_price_bars=lambda *args, **kwargs: [
                {"date": "2026-04-23", "close": 10.0, "high": 10.3, "low": 9.8}
            ],
            _get_last_bar_on_or_before=lambda bars, as_of_date: bars[-1],
            _safe_float=lambda value: float(value or 0),
            _round_or_none=lambda value: value,
            _collect_record_market_path=lambda record, as_of_date: {},
            create=True,
        ):
            result = followups._build_recent_target_followup_item(
                {
                    "stock_code": "000001",
                    "stock_name": "样本股",
                    "report_date": "2026-04-22",
                },
                "2026-04-23",
            )

        self.assertEqual(result, {})

    def test_build_recent_target_reflection_summarizes_multiple_fix_types(self):
        followups = self._load_followups_module()

        result = followups.build_recent_target_reflection(
            [
                {"system_fix": "介入周期偏慢：以后要更快给执行评估。"},
                {"system_fix": "环境过滤过严：不能一直停在纯观察层。"},
                {"system_fix": "观察链不要偷写成执行链：先继续观察。"},
            ]
        )

        self.assertIn("必须分层修正", result["headline"])
        self.assertTrue(any("介入周期" in line for line in result["mistakes"]))
        self.assertTrue(any("跨线对象" in line for line in result["adjustments"]))
        self.assertTrue(any("观察链不要偷写成执行链" in line for line in result["adjustments"]))

    def test_build_gem_horizontal_compare_cards_compares_paths_by_status_family(self):
        followups = self._load_followups_module()

        cards = followups.build_gem_horizontal_compare_cards(
            gem_cycle_cards=[
                {
                    "cycle_label": "2026-04-01 -> 2026-04-10",
                    "sample_label": "20cm样本A",
                    "latest_status_label": "再突破成功但升级偏慢",
                }
            ],
            review_matrix=[
                {"sample_label": "参考样本", "path_label": "已走成 act right"},
            ],
            limit=1,
        )

        self.assertEqual(cards[0]["reference_sample_label"], "参考样本")
        self.assertIn("价格上先证明自己", cards[0]["same_point"])
        self.assertIn("固定交易窗口", cards[0]["system_translation"])
        self.assertIn("复盘和下一份日报判断", cards[0]["system_translation"])
        self.assertIn("0%不参与", cards[0]["system_translation"])
        self.assertNotIn(_m("3", "0%", "条件", "试错"), cards[0]["system_translation"])


if __name__ == "__main__":
    unittest.main()
