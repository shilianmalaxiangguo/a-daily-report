import datetime
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

PERMISSION_LABEL = "主线参与资格"


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


class StrategyTrackingSupportTest(unittest.TestCase):
    def _load_support_module(self):
        try:
            return __import__("report.strategy_tracking_support", fromlist=["strategy_tracking_support"])
        except ModuleNotFoundError as error:
            self.fail(f"report.strategy_tracking_support should exist: {error}")

    def test_legacy_strategy_support_wrappers_delegate_to_runtime(self):
        result = _run_legacy_entry_probe(
            """
import daily_report_entry_demo
from unittest.mock import patch

backfill_payload = {"report_date": "2026-04-23", "benchmark_report_close": 3200.0}
review_payload = {"items": []}

with patch.object(daily_report_entry_demo, "run_backfill_strategy_record_market_context", return_value=backfill_payload) as backfill_mock, \
     patch.object(daily_report_entry_demo, "run_get_strategy_status_label", return_value="待评估") as status_mock, \
     patch.object(daily_report_entry_demo, "run_get_plan_action_label", return_value="50%标准进攻预演") as action_mock, \
     patch.object(daily_report_entry_demo, "run_summarize_ev_signal_review", return_value=review_payload) as review_mock, \
     patch.object(daily_report_entry_demo, "run_compound_returns", return_value=0.06) as compound_mock:
    backfill_result = daily_report_entry_demo._backfill_strategy_record_market_context({"report_date": "2026-04-23"})
    status_result = daily_report_entry_demo._get_strategy_status_label("pending", "note")
    action_result = daily_report_entry_demo._get_plan_action_label("execute", 30)
    review_result = daily_report_entry_demo._summarize_ev_signal_review([{"report_date": "2026-04-23"}], "2026-04-21", "2026-04-24")
    compound_result = daily_report_entry_demo._compound_returns([0.02, 0.03])

assert backfill_mock.call_args[0][0] == {"report_date": "2026-04-23"}
assert "helpers" not in backfill_mock.call_args.kwargs
assert status_mock.call_args[0][0] == "pending"
assert status_mock.call_args[0][1] == "note"
assert "helpers" not in status_mock.call_args.kwargs
assert action_mock.call_args[0][0] == "execute"
assert action_mock.call_args[0][1] == 30
assert "helpers" not in action_mock.call_args.kwargs
assert review_mock.call_args[0][1] == "2026-04-21"
assert review_mock.call_args[0][2] == "2026-04-24"
assert "helpers" not in review_mock.call_args.kwargs
assert compound_mock.call_args[0][0] == [0.02, 0.03]
assert "helpers" not in compound_mock.call_args.kwargs
assert backfill_result == backfill_payload
assert status_result == "待评估"
assert action_result == "50%标准进攻预演"
assert review_result == review_payload
assert compound_result == 0.06
"""
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_legacy_strategy_support_format_wrappers_delegate_to_runtime(self):
        result = _run_legacy_entry_probe(
            """
import daily_report_entry_demo
from unittest.mock import patch

with patch.object(daily_report_entry_demo, "run_format_pct", return_value="+5.00%") as pct_mock, \
     patch.object(daily_report_entry_demo, "run_format_pct_range", return_value="+1.00% ~ +3.00%") as range_mock, \
     patch.object(daily_report_entry_demo, "run_get_run_mode_label", return_value="实验重放") as mode_mock:
    pct_result = daily_report_entry_demo._format_pct(0.05)
    range_result = daily_report_entry_demo._format_pct_range(0.01, 0.03)
    mode_result = daily_report_entry_demo._get_run_mode_label("replay")

assert pct_mock.call_args[0][0] == 0.05
assert "helpers" not in pct_mock.call_args.kwargs
assert range_mock.call_args[0][:2] == (0.01, 0.03)
assert "helpers" not in range_mock.call_args.kwargs
assert mode_mock.call_args[0][0] == "replay"
assert "helpers" not in mode_mock.call_args.kwargs
assert pct_result == "+5.00%"
assert range_result == "+1.00% ~ +3.00%"
assert mode_result == "实验重放"
"""
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_strategy_tracking_support_runtime_exposes_helper_bindings(self):
        support = self._load_support_module()
        exec(
            """
def _support_probe(records, start_date, end_date):
    return runtime_test_helper(records, start_date, end_date)
""",
            support.__dict__,
        )

        with patch(
            "report.strategy_tracking_support._summarize_ev_signal_review_legacy_body",
            support._support_probe,
        ):
            result = support.summarize_ev_signal_review(
                [{"report_date": "2026-04-23"}],
                "2026-04-21",
                "2026-04-24",
                helpers={"runtime_test_helper": lambda records, start_date, end_date: (records[0]["report_date"], start_date, end_date)},
            )

        self.assertEqual(result, ("2026-04-23", "2026-04-21", "2026-04-24"))

    def test_status_and_action_labels_cover_note_and_position_variants(self):
        support = self._load_support_module()

        status_label = support.get_strategy_status_label("pending", "等待确认")
        action_30 = support.get_plan_action_label("execute", 30, helpers={"_safe_float": lambda value, default=0: float(value or default)})
        action_50 = support.get_plan_action_label("execute", 50, helpers={"_safe_float": lambda value, default=0: float(value or default)})
        action_watch = support.get_plan_action_label("watch_only", None)

        self.assertEqual(status_label, "待评估（等待确认）")
        self.assertEqual(action_30, "50%标准进攻预演")
        self.assertEqual(action_50, "50%执行计划")
        self.assertEqual(action_watch, "仅观察")

    def test_format_pct_helpers_cover_none_range_and_mode_label(self):
        support = self._load_support_module()

        pct_text = support.format_pct(0.0525)
        range_text = support.format_pct_range(-0.01, 0.03)
        none_text = support.format_pct(None)
        mode_text = support.get_run_mode_label("replay", helpers={"LEDGER_MODE_FROZEN": "frozen"})

        self.assertEqual(pct_text, "+5.25%")
        self.assertEqual(range_text, "-1.00% ~ +3.00%")
        self.assertEqual(none_text, "-")
        self.assertEqual(mode_text, "实验重放")

    def test_backfill_strategy_record_market_context_fills_benchmark_and_defaults(self):
        support = self._load_support_module()

        result = support.backfill_strategy_record_market_context(
            {"report_date": "2026-04-23"},
            helpers={
                "_normalize_kline_date_str": lambda value: value,
                "_safe_float": lambda value, default=0: float(value or default),
                "_parse_kline_date": lambda value: datetime.datetime.strptime(value, "%Y-%m-%d"),
                "fetch_daily_price_bars": lambda *args, **kwargs: [{"date": "2026-04-23", "close": 3200.5}],
                "_get_first_bar_on_or_after": lambda bars, target_date: bars[0],
                "datetime": datetime,
                "DEFENSIVE_EXIT_RULE_TEXT": "def-rule",
                "PROFIT_EXIT_RULE_TEXT": "profit-rule",
                "STRATEGY_HOLDING_DAYS_MIN": 3,
                "STRATEGY_HOLDING_DAYS_MAX": 5,
            },
        )

        self.assertAlmostEqual(result["benchmark_report_close"], 3200.5)
        self.assertEqual(result["defensive_exit_rule"], "def-rule")
        self.assertEqual(result["profit_exit_rule"], "profit-rule")
        self.assertEqual(result["holding_days_min"], 3)
        self.assertEqual(result["holding_days_max"], 5)
        self.assertEqual(result["decision_stack"], {})

    def test_build_trade_return_stats_counts_wins_losses_and_neutral(self):
        support = self._load_support_module()

        result = support.build_trade_return_stats(
            [
                {"action_type": "execute", "simulation": {"triggered": True, "status": "closed", "strategy_return_worst": 0.04, "strategy_return_best": 0.06}},
                {"action_type": "execute", "simulation": {"triggered": True, "status": "open_mark_to_market", "strategy_return_worst": -0.04, "strategy_return_best": -0.02}},
                {"action_type": "execute", "simulation": {"triggered": True, "status": "closed", "strategy_return_worst": 0.00, "strategy_return_best": 0.00}},
                {"action_type": "watch_only", "simulation": {"triggered": True, "status": "closed", "strategy_return_worst": 0.10, "strategy_return_best": 0.12}},
            ],
            helpers={"_safe_float": lambda value, default=0: float(value or default)},
        )

        self.assertEqual(result["sample_size"], 3)
        self.assertEqual(result["wins"], 1)
        self.assertEqual(result["losses"], 1)
        self.assertEqual(result["neutral"], 1)
        self.assertAlmostEqual(result["win_rate"], 1 / 3)
        self.assertAlmostEqual(result["avg_win_pct"], 0.05)
        self.assertAlmostEqual(result["avg_loss_pct"], 0.03)

    def test_summarize_ev_signal_review_aggregates_by_signal_type(self):
        support = self._load_support_module()

        result = support.summarize_ev_signal_review(
            [
                {
                    "report_date": "2026-04-22",
                    "action_type": "execute",
                    "signal_type": "base",
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
                    "signal_type": "base",
                    "simulation": {
                        "triggered": False,
                        "status": "not_triggered",
                    },
                },
                {
                    "report_date": "2026-04-24",
                    "action_type": "execute",
                    "signal_type": "low_suction",
                    "simulation": {
                        "triggered": True,
                        "status": "open_mark_to_market",
                        "strategy_return_worst": -0.03,
                        "strategy_return_best": -0.01,
                        "alpha_return_worst": -0.02,
                        "alpha_return_best": 0.00,
                    },
                },
            ],
            "2026-04-22",
            "2026-04-24",
            helpers={
                "_normalize_kline_date_str": lambda value: value,
                "_safe_float": lambda value, default=0: float(value or default),
                "_get_signal_type_label": lambda signal_type: {"base": "基础信号", "low_suction": "低吸信号"}.get(signal_type, signal_type),
            },
        )

        self.assertEqual(result["total_plan_count"], 3)
        self.assertEqual(result["items"][0]["signal_label"], "基础信号")
        self.assertEqual(result["items"][0]["plan_count"], 2)
        self.assertEqual(result["items"][0]["triggered_count"], 1)
        self.assertAlmostEqual(result["items"][0]["avg_return"], 0.03)
        self.assertAlmostEqual(result["items"][0]["avg_alpha"], 0.02)

    def test_legacy_candidate_feedback_support_wrappers_delegate_to_runtime(self):
        result = _run_legacy_entry_probe(
            """
import daily_report_entry_demo
from unittest.mock import patch

probe_payload = [{"code": "000001", "role_family": "watch_anchor"}]
history_payload = {"continuous_days": 2, "active_watch": True}
clock_payload = {"ready": True, "score": 5}

with patch.object(daily_report_entry_demo, "run_iter_record_probe_candidates", return_value=probe_payload) as probe_mock, \
     patch.object(daily_report_entry_demo, "run_build_candidate_history_feedback", return_value=history_payload) as history_mock, \
     patch.object(daily_report_entry_demo, "run_build_candidate_feedback_clock", return_value=clock_payload) as clock_mock:
    probe_result = daily_report_entry_demo._iter_record_probe_candidates({"stock_code": "000001"})
    history_result = daily_report_entry_demo._build_candidate_history_feedback({"code": "000001"}, "2026-04-23", "validation_probe", "承接验证")
    clock_result = daily_report_entry_demo._build_candidate_feedback_clock(
        {"code": "000001"},
        "承接验证",
        {"leading_line": "机器人"},
        "机器人",
        "2026-04-23",
    )

assert probe_mock.call_args[0][0] == {"stock_code": "000001"}
assert "helpers" not in probe_mock.call_args.kwargs
assert history_mock.call_args[0][1] == "2026-04-23"
assert history_mock.call_args[0][2] == "validation_probe"
assert history_mock.call_args[0][3] == "承接验证"
assert "helpers" not in history_mock.call_args.kwargs
assert clock_mock.call_args[0][1] == "承接验证"
assert clock_mock.call_args[0][2] == {"leading_line": "机器人"}
assert clock_mock.call_args[0][3] == "机器人"
assert clock_mock.call_args[0][4] == "2026-04-23"
assert "helpers" not in clock_mock.call_args.kwargs
assert probe_result == probe_payload
assert history_result == history_payload
assert clock_result == clock_payload
"""
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_build_candidate_feedback_clock_runtime_exposes_helper_bindings(self):
        support = self._load_support_module()
        exec(
            """
def _candidate_feedback_clock_probe(candidate=None, watch_anchor_type='', state_machine_snapshot=None, mainline_name='', target_date=''):
    confirmation = _candidate_confirmation_chain(candidate)
    role_family = _resolve_probe_role_family(watch_anchor_type=watch_anchor_type, anchor_type=candidate.get('watch_anchor_type', ''))
    prices = _extract_candidate_report_prices(candidate)
    history = _build_candidate_history_feedback(candidate, target_date, role_family, watch_anchor_type)
    return runtime_test_helper(confirmation, role_family, prices, history, mainline_name)
""",
            support.__dict__,
        )

        with patch(
            "report.strategy_tracking_support._build_candidate_feedback_clock_legacy_body",
            support._candidate_feedback_clock_probe,
        ):
            result = support.build_candidate_feedback_clock(
                {
                    "watch_anchor_type": "主线观察",
                    "report_day_close": 12.3,
                    "display_anchor_price": 11.5,
                    "minute_plan": {"confirm_price_60m": 12.1},
                },
                "主线观察",
                {"leading_line": "机器人"},
                "机器人",
                "2026-04-23",
                helpers={
                    "_candidate_confirmation_chain": lambda candidate=None: {"has_confirmation_chain": True, "confirm_price": 12.1, "support_price": 11.5},
                    "_resolve_probe_role_family": lambda **kwargs: "mainline_abnormal_probe",
                    "_extract_candidate_report_prices": lambda candidate=None: {"close": 12.3, "high": 12.5, "low": 11.9},
                    "_build_candidate_history_feedback": lambda *args, **kwargs: {"continuous_days": 2, "active_watch": True},
                    "runtime_test_helper": lambda confirmation, role_family, prices, history, mainline_name: (
                        confirmation["confirm_price"],
                        role_family,
                        prices["close"],
                        history["continuous_days"],
                        mainline_name,
                    ),
                },
            )

        self.assertEqual(result, (12.1, "mainline_abnormal_probe", 12.3, 2, "机器人"))

    def test_build_candidate_history_feedback_uses_runtime_default_dependencies_when_helpers_omitted(self):
        support = self._load_support_module()

        with patch.object(support, "normalize_stock_code", side_effect=lambda value: value) as code_mock, \
             patch.object(support, "_normalize_kline_date_str", side_effect=lambda value: value) as normalize_mock, \
             patch.object(support, "load_strategy_performance_ledger", return_value={"records": []}) as ledger_mock, \
             patch.object(support, "_resolve_probe_role_family", return_value="watch_anchor") as role_mock:
            result = support.build_candidate_history_feedback(
                {"code": "000001", "abnormal_setup_signal_id": "burst_hold"},
                "2026-04-23",
                "watch_anchor",
                "执行候选观察锚点",
            )

        self.assertEqual(result["matched_records"], 0)
        self.assertEqual(result["continuous_days"], 0)
        self.assertEqual(result["role_family"], "watch_anchor")
        self.assertFalse(result["active_watch"])
        code_mock.assert_called()
        normalize_mock.assert_called()
        ledger_mock.assert_called_once_with(mode=support.LEDGER_MODE_FROZEN)
        role_mock.assert_called_once()

    def test_build_candidate_feedback_clock_uses_runtime_default_dependencies_when_helpers_omitted(self):
        support = self._load_support_module()

        with patch.object(support, "_resolve_candidate_follow_state", return_value="跌不下去") as follow_mock, \
             patch.object(
                 support,
                 "_candidate_confirmation_chain",
                 return_value={"has_confirmation_chain": True, "confirm_price": 11.0, "support_price": 10.3},
             ) as confirmation_mock, \
             patch.object(
                 support,
                 "_build_candidate_history_feedback",
                 return_value={
                     "continuous_days": 2,
                     "reasons": ["历史连续候选反馈确认成立"],
                     "active_watch": True,
                     "contract_kind": "execute_anchor",
                     "latest_match": {
                         "confirm_price_60m": 11.1,
                         "entry_range_high": 11.3,
                         "confirm_support_60m": 10.4,
                         "effective_stop": 10.2,
                     },
                 },
             ) as history_mock, \
             patch.object(support, "_resolve_probe_role_family", return_value="watch_anchor") as role_mock, \
             patch.object(support, "_candidate_matches_mainline", return_value=True) as mainline_mock, \
             patch.object(
                 support,
                 "_extract_candidate_report_prices",
                 return_value={"close": 11.4, "high": 11.5, "low": 10.6},
             ) as prices_mock, \
             patch.object(
                 support,
                 "_round_or_none",
                 side_effect=lambda value, digits=4: None if value is None else round(float(value), digits),
             ) as round_mock, \
             patch.object(
                 support,
                 "_safe_float",
                 side_effect=lambda value, default=0.0: float(default) if value in (None, "") else float(value),
             ) as safe_float_mock:
            result = support.build_candidate_feedback_clock(
                {
                    "code": "000001",
                    "watch_anchor_type": "执行候选观察锚点",
                    "permission_label": PERMISSION_LABEL,
                    "report_day_close": 11.4,
                    "report_day_high": 11.5,
                    "report_day_low": 10.6,
                    "decision_stack": {"trigger_score": 88},
                },
                "执行候选观察锚点",
                {"leading_line": "机器人"},
                "机器人",
                "2026-04-23",
            )

        self.assertTrue(result["ready"])
        self.assertTrue(result["second_shot_ready"])
        self.assertEqual(result["second_shot_breakout_price"], 11.3)
        self.assertIn("已重新站上11.30，触发二次突破条件", result["reasons"])
        follow_mock.assert_called_once()
        confirmation_mock.assert_called_once()
        history_mock.assert_called_once()
        role_mock.assert_called_once()
        mainline_mock.assert_called()
        prices_mock.assert_called_once()
        self.assertGreaterEqual(round_mock.call_count, 3)
        self.assertGreaterEqual(safe_float_mock.call_count, 1)

    def test_build_candidate_history_feedback_tracks_continuity_and_active_watch(self):
        support = self._load_support_module()

        ledger = {
            "records": [
                {
                    "report_date": "2026-04-22",
                    "action_type": "watch_only",
                    "stock_code": "000001",
                    "abnormal_setup_signal_id": "burst_hold",
                    "anchor_type": "执行候选观察锚点",
                    "holding_days_max": 4,
                    "confirm_price_60m": 10.8,
                    "confirm_support_60m": 10.1,
                    "entry_range_high": 10.9,
                    "entry_range_low": 10.2,
                    "effective_stop": 9.9,
                },
                {
                    "report_date": "2026-04-21",
                    "action_type": "execute",
                    "stock_code": "000001",
                    "abnormal_setup_signal_id": "burst_hold",
                    "anchor_type": "执行候选观察锚点",
                    "holding_days_max": 4,
                    "confirm_price_60m": 10.6,
                    "confirm_support_60m": 10.0,
                    "entry_range_high": 10.7,
                    "entry_range_low": 10.1,
                    "effective_stop": 9.8,
                },
            ]
        }

        result = support.build_candidate_history_feedback(
            {"code": "000001", "abnormal_setup_signal_id": "burst_hold"},
            "2026-04-23",
            "watch_anchor",
            "执行候选观察锚点",
            helpers={
                "normalize_stock_code": lambda value: value,
                "_normalize_kline_date_str": lambda value: value,
                "load_strategy_performance_ledger": lambda mode=None: ledger,
                "LEDGER_MODE_FROZEN": "frozen",
                "_iter_record_probe_candidates": lambda record: [{
                    "code": record.get("stock_code", ""),
                    "setup_id": record.get("abnormal_setup_signal_id", ""),
                    "role_family": "watch_anchor",
                }],
                "_resolve_probe_role_family": lambda **kwargs: "watch_anchor",
                "_safe_float": lambda value, default=0: float(value or default),
                "STRATEGY_HOLDING_DAYS_MAX": 5,
                "_round_or_none": lambda value, digits=4: None if value is None else round(float(value), digits),
                "_is_next_trading_day": lambda prev_date, curr_date: (prev_date, curr_date) in {
                    ("2026-04-22", "2026-04-23"),
                    ("2026-04-21", "2026-04-22"),
                },
                "_count_trading_days_between": lambda start_date, end_date: 2 if (start_date, end_date) == ("2026-04-22", "2026-04-23") else 0,
            },
        )

        self.assertEqual(result["matched_records"], 2)
        self.assertEqual(result["continuous_days"], 2)
        self.assertTrue(result["active_watch"])
        self.assertEqual(result["contract_kind"], "execute_anchor")
        self.assertIn("历史连续候选反馈确认成立", result["reasons"])
        self.assertIn("执行候选观察锚点仍在4日活观察窗口内", result["reasons"])

    def test_build_candidate_feedback_clock_marks_second_shot_ready_inside_active_window(self):
        support = self._load_support_module()

        result = support.build_candidate_feedback_clock(
            {
                "code": "000001",
                "watch_anchor_type": "执行候选观察锚点",
                "permission_label": PERMISSION_LABEL,
                "abnormal_setup_signal_id": "burst_hold",
                "minute_plan": {"confirm_price_60m": 11.0, "confirm_support_60m": 10.3},
                "report_day_close": 11.4,
                "report_day_high": 11.5,
                "report_day_low": 10.6,
                "decision_stack": {"trigger_score": 88},
            },
            "执行候选观察锚点",
            {"leading_line": "机器人"},
            "机器人",
            "2026-04-23",
            helpers={
                "_resolve_candidate_follow_state": lambda candidate=None: "跌不下去",
                "_candidate_confirmation_chain": lambda candidate=None: {"has_confirmation_chain": True, "confirm_price": 11.0, "support_price": 10.3},
                "_safe_float": lambda value, default=0: float(value or default),
                "_build_candidate_history_feedback": lambda *args, **kwargs: {
                    "continuous_days": 2,
                    "reasons": ["历史连续候选反馈确认成立"],
                    "active_watch": True,
                    "contract_kind": "execute_anchor",
                    "latest_match": {
                        "confirm_price_60m": 11.1,
                        "entry_range_high": 11.3,
                        "confirm_support_60m": 10.4,
                        "effective_stop": 10.2,
                    },
                },
                "_resolve_probe_role_family": lambda **kwargs: "watch_anchor",
                "_candidate_matches_mainline": lambda candidate, mainline_name='': True,
                "_extract_candidate_report_prices": lambda candidate=None: {"close": 11.4, "high": 11.5, "low": 10.6},
                "_round_or_none": lambda value, digits=4: None if value is None else round(float(value), digits),
            },
        )

        self.assertTrue(result["ready"])
        self.assertTrue(result["second_shot_ready"])
        self.assertEqual(result["second_shot_breakout_price"], 11.3)
        self.assertGreaterEqual(result["score"], 7)
        self.assertIn("已重新站上11.30，触发二次突破条件", result["reasons"])
        self.assertIn("历史连续候选反馈确认成立", result["reasons"])


if __name__ == "__main__":
    unittest.main()
