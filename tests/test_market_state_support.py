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

    return subprocess.run(
        [sys.executable, "-c", stub_setup + "\n" + script_body],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )


class MarketStateSupportTest(unittest.TestCase):
    def _load_module(self):
        try:
            return __import__("domains.market_state.support", fromlist=["support"])
        except ModuleNotFoundError as error:
            self.fail(f"domains.market_state.support should exist: {error}")

    def test_legacy_market_state_wrappers_delegate_to_support_runtime(self):
        result = _run_legacy_entry_probe(
            """
import daily_report_entry_demo
from unittest.mock import patch

with patch.object(daily_report_entry_demo, "run_score_environment_snapshot", return_value=85) as env_mock, \
     patch.object(daily_report_entry_demo, "run_score_mainline_snapshot", return_value=91) as mainline_mock, \
     patch.object(daily_report_entry_demo, "run_normalize_flow_to_yi", return_value=12.3) as flow_mock, \
     patch.object(daily_report_entry_demo, "run_build_market_state_machine_snapshot", return_value={"state_code": "expand"}) as state_mock:
    env_score = daily_report_entry_demo._score_environment_snapshot({"can_new_entry": True}, "三档（进攻档）")
    mainline_score = daily_report_entry_demo._score_mainline_snapshot("军工", 40, [{"sector": "军工"}])
    flow_yi = daily_report_entry_demo._normalize_flow_to_yi(123000)
    snapshot = daily_report_entry_demo._build_market_state_machine_snapshot({}, {"can_new_entry": True}, "三档（进攻档）", {"sector_name": "军工"})

assert env_mock.call_args[0] == ({"can_new_entry": True}, "三档（进攻档）")
assert mainline_mock.call_args[0][:3] == ("军工", 40, [{"sector": "军工"}])
assert "helpers" in mainline_mock.call_args.kwargs
assert flow_mock.call_args[0][0] == 123000
assert "helpers" in flow_mock.call_args.kwargs
assert state_mock.call_args[0][:4] == ({}, {"can_new_entry": True}, "三档（进攻档）", {"sector_name": "军工"})
assert "helpers" in state_mock.call_args.kwargs
assert env_score == 85
assert mainline_score == 91
assert flow_yi == 12.3
assert snapshot == {"state_code": "expand"}
"""
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_legacy_market_state_history_and_leader_wrappers_delegate_to_support_runtime(self):
        result = _run_legacy_entry_probe(
            """
import daily_report_entry_demo
from unittest.mock import patch

with patch.object(daily_report_entry_demo, "run_load_recent_sector_flow_history", return_value=[{"date": "2026-04-21", "inflow": 12.5}]) as flow_mock, \
     patch.object(daily_report_entry_demo, "run_load_recent_market_turnover_history", return_value=[{"date": "2026-04-21", "turnover": 11000}]) as turnover_mock, \
     patch.object(daily_report_entry_demo, "run_calculate_exit_price_lines", return_value={"code": "000001", "close_price": 10.2, "stop_loss": 9.8}) as exit_mock, \
     patch.object(daily_report_entry_demo, "run_get_sector_core_hot_stock", return_value={"name": "军工一号", "hot_rank": 3}) as core_mock, \
     patch.object(daily_report_entry_demo, "run_get_sector_leader", return_value={"name": "军工龙头", "is_limit_down": False}) as leader_mock:
    flow_history = daily_report_entry_demo.load_recent_sector_flow_history("2026-04-22", "军工", lookback_days=2)
    turnover_history = daily_report_entry_demo.load_recent_market_turnover_history("2026-04-22", lookback_days=2)
    exit_lines = daily_report_entry_demo.calculate_exit_price_lines({"code": "000001"}, {"000001": {"close": 10.2, "low": 9.8}})
    core_stock = daily_report_entry_demo.get_sector_core_hot_stock("军工", [{"name": "军工一号"}])
    leader = daily_report_entry_demo.get_sector_leader("军工", [{"name": "军工龙头"}], {})

assert flow_mock.call_args[0][:2] == ("2026-04-22", "军工")
assert "helpers" in flow_mock.call_args.kwargs
assert turnover_mock.call_args[0][0] == "2026-04-22"
assert "helpers" in turnover_mock.call_args.kwargs
assert exit_mock.call_args[0][:2] == ({"code": "000001"}, {"000001": {"close": 10.2, "low": 9.8}})
assert "helpers" in exit_mock.call_args.kwargs
assert core_mock.call_args[0][:2] == ("军工", [{"name": "军工一号"}])
assert "helpers" in core_mock.call_args.kwargs
assert leader_mock.call_args[0][:3] == ("军工", [{"name": "军工龙头"}], {})
assert "helpers" in leader_mock.call_args.kwargs
assert flow_history == [{"date": "2026-04-21", "inflow": 12.5}]
assert turnover_history == [{"date": "2026-04-21", "turnover": 11000}]
assert exit_lines["stop_loss"] == 9.8
assert core_stock["hot_rank"] == 3
assert leader["name"] == "军工龙头"
"""
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_market_state_support_core_scores_and_flow_normalization(self):
        support = self._load_module()

        env_score = support.score_environment_snapshot({"can_new_entry": True}, "三档（进攻档）")
        mainline_score = support.score_mainline_snapshot(
            "军工",
            40,
            [{"sector": "军工", "trend_count": 3, "strong_count": 2, "limit_up_count": 1}],
            helpers={
                "sector_name_matches": lambda left, right: left == right,
                "_safe_float": lambda value, default=0.0: default if value in (None, "") else float(value),
                "_clamp": lambda value, low, high: max(low, min(high, value)),
            },
        )
        memory_score = support.score_memory_snapshot(
            [{"code": "000001"}],
            {"today_validated_items": [{"code": "000001"}], "today_tentative_items": [{"code": "000002"}]},
            helpers={"_clamp": lambda value, low, high: max(low, min(high, value))},
        )
        abnormal_score = support.score_abnormal_snapshot(
            [{"follow_state": "跌不下去"}, {"follow_state": "缩量消化"}],
            {"abnormal_follow_state": "跌不下去"},
            helpers={
                "_split_abnormal_watch_pool": lambda pool: (pool, []),
                "_clamp": lambda value, low, high: max(low, min(high, value)),
            },
        )
        flow_yi = support.normalize_flow_to_yi(123000, helpers={"_safe_float": lambda value, default=0.0: float(value or default)})
        pulse = support.derive_mainline_pulse_snapshot(
            final_gate={"can_new_entry": True},
            state_code="expand",
            leading_line="军工",
            trend_density=3,
            resilient_count=2,
            failed_count=0,
            zt_count=28,
            dt_count=2,
        )

        self.assertEqual(env_score, 85)
        self.assertEqual(mainline_score, 61)
        self.assertEqual(memory_score, 26)
        self.assertEqual(abnormal_score, 93)
        self.assertEqual(flow_yi, 12.3)
        self.assertEqual(pulse["driver_type"], "逻辑催化驱动")
        self.assertEqual(pulse["pulse_stage"], "加速")
        self.assertEqual(pulse["execution_bias"], "allow_execute")

    def test_build_market_state_machine_snapshot_support_builds_transition_contract(self):
        support = self._load_module()

        result = support.build_market_state_machine_snapshot(
            {
                "indices": {"上证指数": {"涨跌幅": 0.5}},
                "zt_pool": [{"code": "000001"}] * 32,
                "dt_pool": [{"code": "000009"}] * 2,
                "total_turnover": 12345.6,
                "sector_quadrant": {"high_strong_analysis": {"total": 16}},
            },
            {"can_new_entry": True, "final_action": "只做核心", "operation_state": "进攻态"},
            "三档（进攻档）",
            {"sector_name": "军工"},
            main_sectors_info=[{"name": "军工"}],
            secondary_sectors_info=[{"name": "机器人"}],
            sector_trend_snapshot=[{"sector": "军工", "trend_count": 3}],
            abnormal_watch_pool=[{"follow_state": "跌不下去"}, {"follow_state": "缩量消化"}],
            helpers={
                "_split_abnormal_watch_pool": lambda pool: (pool, []),
                "_extract_market_breadth_snapshot": lambda data: {
                    "up_count": 3200,
                    "down_count": 1800,
                    "breadth_available": True,
                    "rise_fall_ratio": 1.5,
                    "rise_fall_ratio_text": "1.5:1",
                },
                "_safe_float": lambda value, default=0.0: default if value in (None, "") else float(value),
                "_round_or_none": lambda value, digits=4: round(float(value), digits) if value is not None else None,
                "_derive_mainline_pulse_snapshot": lambda **kwargs: {
                    "driver_type": "趋势抱团驱动",
                    "pulse_stage": "启动",
                    "acceptance_quality": "强承接",
                    "passivation_risk": "低",
                    "execution_bias": "allow_execute",
                    "pulse_action_bias": "允许做启动/强化段",
                    "pulse_action_reason": "主线仍处于可参与段",
                },
            },
        )

        self.assertEqual(result["state_code"], "expand")
        self.assertEqual(result["energy_state"], "扩张聚焦")
        self.assertEqual(result["leading_line"], "军工")
        self.assertEqual(result["resilient_abnormal_count"], 2)
        self.assertEqual(result["driver_type"], "趋势抱团驱动")
        self.assertEqual(result["pulse_action_reason"], "主线仍处于可参与段")

    def test_build_market_style_switch_snapshot_support_prefers_trend_when_turnover_and_resilience_align(self):
        support = self._load_module()
        builder = getattr(support, "build_market_style_switch_snapshot", None)
        self.assertIsNotNone(builder)

        result = builder(
            "2026-04-22",
            {
                "total_turnover": 12300,
                "status_distribution": {"3板": 1, "2板": 2},
                "tag_distribution": {"军工": 3},
                "integrated_hot_list": [],
                "zt_pool": [{"name": "军工一号"}],
                "hot_rank_top30": [],
            },
            observation_snapshot={
                "resilient_abnormal_count": 2,
                "failed_abnormal_count": 0,
                "densest_sector_trend_count": 3,
                "densest_sector": "军工",
                "leader_memory_count": 3,
                "trusted_tracking_count": 1,
            },
            abnormal_projection={"projection_label": "异常承接强化"},
            helpers={
                "_safe_float": lambda value, default=0.0: default if value in (None, "") else float(value),
                "_round_or_none": lambda value, digits=2: round(float(value), digits),
                "_normalize_kline_date_str": lambda value: str(value),
                "load_recent_market_turnover_history": lambda target_date, lookback_days=2, max_scan_days=8: [
                    {"date": "2026-04-20", "turnover": 11000},
                    {"date": "2026-04-21", "turnover": 11800},
                ],
                "_parse_status_board_count": lambda label: int(str(label).replace("板", "")) if str(label).replace("板", "").isdigit() else 0,
                "_count_keyword_hits_in_mapping": lambda mapping, keywords: 0,
                "_count_keyword_hits_in_items": lambda items, keywords, fields: 0,
            },
        )

        self.assertEqual(result["style_code"], "trend")
        self.assertEqual(result["style_label"], "趋势分歧优先")
        self.assertEqual(result["turnover_state"], "rising")
        self.assertEqual(result["trend_signal_count"], 4)
        self.assertEqual(result["speculative_signal_count"], 0)
        self.assertEqual(result["projection_label"], "异常承接强化")
        self.assertIn("2026-04-20:11000亿", result["turnover_series_text"])
        self.assertIn("异常承接2强/0弱", result["evidence_text"])

    def test_market_state_support_loads_recent_sector_flow_history_from_snapshots(self):
        support = self._load_module()

        result = support.load_recent_sector_flow_history(
            "2026-04-22",
            "军工",
            lookback_days=2,
            helpers={
                "_normalize_kline_date_str": lambda value: str(value),
                "get_previous_date_str": lambda value: {
                    "2026-04-22": "2026-04-21",
                    "2026-04-21": "2026-04-20",
                    "2026-04-20": "",
                }.get(value, ""),
                "load_data_snapshot": lambda cursor: (
                    {
                        "2026-04-21": {
                            "sector_fund_flow": {
                                "inflow": [{"name": "军工", "zljlr": 12.5}],
                                "outflow": [],
                            }
                        },
                        "2026-04-20": {
                            "sector_fund_flow": {
                                "inflow": [],
                                "outflow": [{"name": "军工", "zljlr": -3.2}],
                            }
                        },
                    }.get(cursor, {}),
                    None,
                ),
                "sector_name_matches": lambda left, right: left == right,
                "_safe_float": lambda value, default=0.0: default if value in (None, "") else float(value),
            },
        )

        self.assertEqual(
            result,
            [
                {"date": "2026-04-20", "inflow": -3.2},
                {"date": "2026-04-21", "inflow": 12.5},
            ],
        )

    def test_market_state_support_loads_recent_market_turnover_history_from_snapshots(self):
        support = self._load_module()

        result = support.load_recent_market_turnover_history(
            "2026-04-22",
            lookback_days=2,
            helpers={
                "_normalize_kline_date_str": lambda value: str(value),
                "get_previous_date_str": lambda value: {
                    "2026-04-22": "2026-04-21",
                    "2026-04-21": "2026-04-20",
                    "2026-04-20": "",
                }.get(value, ""),
                "load_data_snapshot": lambda cursor: (
                    {
                        "2026-04-21": {"total_turnover": 11000},
                        "2026-04-20": {"total_turnover": 10500.5},
                    }.get(cursor, {}),
                    None,
                ),
                "_safe_float": lambda value, default=0.0: default if value in (None, "") else float(value),
            },
        )

        self.assertEqual(
            result,
            [
                {"date": "2026-04-20", "turnover": 10500.5},
                {"date": "2026-04-21", "turnover": 11000.0},
            ],
        )

    def test_market_state_support_history_helpers_use_runtime_defaults_when_omitted(self):
        support = self._load_module()
        snapshots = {
            "2026-04-21": {
                "sector_fund_flow": {
                    "inflow": [{"name": "军工", "zljlr": 12.5}],
                    "outflow": [],
                },
                "total_turnover": 11000,
            },
            "2026-04-20": {
                "sector_fund_flow": {
                    "inflow": [],
                    "outflow": [{"name": "军工", "zljlr": -3.2}],
                },
                "total_turnover": 10500.5,
            },
        }

        with patch.object(support, "_normalize_kline_date_str", side_effect=lambda value: str(value)) as normalize_mock, \
             patch.object(
                 support,
                 "get_previous_date_str",
                 side_effect=lambda value: {
                     "2026-04-22": "2026-04-21",
                     "2026-04-21": "2026-04-20",
                     "2026-04-20": "",
                 }.get(value, ""),
             ) as previous_date_mock, \
             patch.object(
                 support,
                 "load_data_snapshot",
                 side_effect=lambda cursor: (snapshots.get(cursor, {}), None),
             ) as snapshot_mock, \
             patch.object(support, "sector_name_matches", side_effect=lambda left, right: left == right) as sector_match_mock, \
             patch.object(
                 support,
                 "_safe_float",
                 side_effect=lambda value, default=0.0: default if value in (None, "") else float(value),
             ) as safe_float_mock:
            flow_result = support.load_recent_sector_flow_history("2026-04-22", "军工", lookback_days=2)
            turnover_result = support.load_recent_market_turnover_history("2026-04-22", lookback_days=2)

        self.assertEqual(
            flow_result,
            [
                {"date": "2026-04-20", "inflow": -3.2},
                {"date": "2026-04-21", "inflow": 12.5},
            ],
        )
        self.assertEqual(
            turnover_result,
            [
                {"date": "2026-04-20", "turnover": 10500.5},
                {"date": "2026-04-21", "turnover": 11000.0},
            ],
        )
        self.assertGreaterEqual(normalize_mock.call_count, 2)
        self.assertGreaterEqual(previous_date_mock.call_count, 4)
        self.assertGreaterEqual(snapshot_mock.call_count, 4)
        self.assertGreaterEqual(sector_match_mock.call_count, 2)
        self.assertGreaterEqual(safe_float_mock.call_count, 4)

    def test_market_state_support_builds_exit_and_leader_helpers_locally(self):
        support = self._load_module()

        exit_lines = support.calculate_exit_price_lines(
            {"code": "SZ000001", "close": 10.0, "low": 9.7},
            {"000001": {"close": 10.3, "low": 9.9}},
            helpers={"normalize_stock_code": lambda code: str(code or "").replace("SZ", "")},
        )
        core_stock = support.get_sector_core_hot_stock(
            "军工",
            [{"name": "其他", "sector": "机器人"}, {"name": "军工一号", "sector": "军工"}],
            helpers={"stock_matches_sector": lambda stock, sector_name: stock.get("sector") == sector_name},
        )
        leader = support.get_sector_leader(
            "军工",
            [{"name": "军工龙头", "sector": "军工", "lianban": 3}],
            {},
            helpers={"normalize_stock_code": lambda code: str(code or "").replace("SZ", "")},
        )

        self.assertEqual(exit_lines, {"code": "000001", "close_price": 10.3, "stop_loss": 9.9})
        self.assertEqual(core_stock["name"], "军工一号")
        self.assertEqual(core_stock["hot_rank"], 2)
        self.assertEqual(leader["name"], "军工龙头")
        self.assertFalse(leader["is_limit_down"])

    def test_build_market_style_switch_snapshot_support_uses_local_keyword_item_counter(self):
        support = self._load_module()

        result = support.build_market_style_switch_snapshot(
            "2026-04-22",
            {
                "total_turnover": 9800,
                "status_distribution": {"3板": 1},
                "tag_distribution": {},
                "integrated_hot_list": [
                    {
                        "code": "000002",
                        "name": "重组次新A",
                        "all_tags": ["次新", "并购重组"],
                        "sector_tags": ["次新"],
                    }
                ],
                "zt_pool": [{"code": "000001", "name": "ST华通"}],
                "hot_rank_top30": [],
            },
            observation_snapshot={},
            abnormal_projection={},
            helpers={
                "_safe_float": lambda value, default=0.0: default if value in (None, "") else float(value),
                "_round_or_none": lambda value, digits=2: round(float(value), digits) if value is not None else None,
                "_normalize_kline_date_str": lambda value: str(value),
                "load_recent_market_turnover_history": lambda target_date, lookback_days=2, max_scan_days=8: [
                    {"date": "2026-04-21", "turnover": 10000}
                ],
                "_parse_status_board_count": lambda label: int(str(label).replace("板", "")) if str(label).replace("板", "").isdigit() else 0,
                "_count_keyword_hits_in_mapping": lambda mapping, keywords: 0,
                "normalize_stock_code": lambda code: str(code or "").strip(),
            },
        )

        self.assertEqual(result["subnew_tag_count"], 1)
        self.assertEqual(result["reorg_tag_count"], 1)
        self.assertEqual(result["st_stock_count"], 1)

    def test_build_market_state_machine_snapshot_support_uses_local_breadth_snapshot(self):
        support = self._load_module()

        result = support.build_market_state_machine_snapshot(
            {
                "indices": {"上证指数": {"涨跌幅": 0.5}},
                "market_stats": {"up_count": 3200, "down_count": 1600},
                "zt_pool": [{"code": "000001"}] * 28,
                "dt_pool": [{"code": "000009"}] * 2,
                "total_turnover": 12345.6,
                "sector_quadrant": {"high_strong_analysis": {"total": 16}},
            },
            {"can_new_entry": True, "final_action": "只做核心", "operation_state": "进攻态"},
            "三档（进攻档）",
            {"sector_name": "军工"},
            main_sectors_info=[{"name": "军工"}],
            secondary_sectors_info=[{"name": "机器人"}],
            sector_trend_snapshot=[{"sector": "军工", "trend_count": 3}],
            abnormal_watch_pool=[{"follow_state": "跌不下去"}, {"follow_state": "缩量消化"}],
            helpers={
                "_split_abnormal_watch_pool": lambda pool: (pool, []),
                "_safe_float": lambda value, default=0.0: default if value in (None, "") else float(value),
                "_round_or_none": lambda value, digits=4: round(float(value), digits) if value is not None else None,
                "_derive_mainline_pulse_snapshot": lambda **kwargs: {
                    "driver_type": "趋势抱团驱动",
                    "pulse_stage": "启动",
                    "acceptance_quality": "强承接",
                    "passivation_risk": "低",
                    "execution_bias": "allow_execute",
                    "pulse_action_bias": "允许做启动/强化段",
                    "pulse_action_reason": "主线仍处于可参与段",
                },
                "sector_name_matches": lambda left, right: left == right,
            },
        )

        self.assertEqual(result["rise_fall_ratio"], 2.0)
        self.assertEqual(result["rise_fall_ratio_text"], "2.00")
        self.assertEqual(result["up_count"], 3200)
        self.assertEqual(result["down_count"], 1600)

    def test_build_unified_sector_strength_rows_support_uses_local_sector_strength_helpers(self):
        support = self._load_module()

        result = support.build_unified_sector_strength_rows(
            {
                "target_date": "2026-04-22",
                "zt_pool_by_sector": {
                    "通信设备": [{"连板数": 2}, {"连板数": 1}],
                    "地产": [{"连板数": 1}],
                },
                "dt_pool_by_sector": {"地产": [{}]},
                "sector_fund_flow": {
                    "inflow": [{"name": "通信设备", "zljlr": 8.0, "zdf": 3.1}],
                    "outflow": [{"name": "地产", "zljlr": -2.0, "zdf": -1.5}],
                },
                "hot_plates": [{"name": "通信设备", "order": 2, "rate": 7.8}],
                "hot_rank_top30": [{"code": "000001", "sector": "通信设备"}],
                "tag_distribution": {"光模块": 4, "CPO": 2, "地产": 1},
                "sector_quadrant": {
                    "high_strong_analysis": {
                        "tier1_best": [
                            {"name": "通信设备", "quality_score": 75, "positionInRange": 88, "recentChange": 3.2}
                        ]
                    }
                },
            },
            helpers={
                "_safe_float": lambda value, default=0.0: default if value in (None, "") else float(value),
                "_clamp": lambda value, low, high: max(low, min(high, value)),
                "_score_to_star_rank": lambda score: 5 if score >= 84 else 4 if score >= 72 else 3 if score >= 58 else 2 if score >= 42 else 1,
                "sector_name_matches": lambda left, right: left == right,
                "stock_matches_sector": lambda stock, sector_name: stock.get("sector") == sector_name,
                "load_recent_sector_flow_history": lambda target_date, sector_name, lookback_days=2: [
                    {"date": "2026-04-21", "inflow": 5.0}
                ],
            },
        )

        self.assertEqual(result[0]["name"], "通信设备")
        self.assertEqual(result[0]["role"], "main")
        self.assertAlmostEqual(result[0]["hot_weight"], 85.71, places=2)
        self.assertEqual(result[0]["quadrant_label"], "最佳击球区")
        self.assertIn("资金回流增强", result[0]["trend_label"])
        self.assertEqual(result[1]["name"], "地产")

    def test_build_unified_sector_strength_rows_support_sorts_main_secondary_and_observe(self):
        support = self._load_module()
        builder = getattr(support, "build_unified_sector_strength_rows", None)
        self.assertIsNotNone(builder)

        def fake_get_or_create_sector_bucket(sector_buckets, sector_name):
            sector_name = str(sector_name or "").strip()
            if not sector_name:
                return None
            for bucket in sector_buckets:
                if bucket.get("name") == sector_name:
                    return bucket
            bucket = {
                "name": sector_name,
                "zt_count": 0,
                "dt_count": 0,
                "dragon_count": 0,
                "net_inflow": 0.0,
                "change": 0.0,
                "hot_plate_rank": None,
                "hot_plate_heat": 0.0,
                "hot_weight": 0.0,
                "hot_stock_count": 0,
                "quadrant_quality_score": 0.0,
                "quadrant_label": "",
            }
            sector_buckets.append(bucket)
            return bucket

        result = builder(
            {
                "target_date": "2026-04-22",
                "zt_pool_by_sector": {
                    "军工": [{"连板数": 2}, {"连板数": 1}],
                    "机器人": [{"连板数": 1}],
                },
                "dt_pool_by_sector": {
                    "地产": [{}, {}],
                    "机器人": [{}],
                },
                "sector_fund_flow": {
                    "inflow": [
                        {"name": "军工", "zljlr": 12.0, "zdf": 4.2},
                        {"name": "机器人", "zljlr": 2.5, "zdf": 1.8},
                    ],
                    "outflow": [
                        {"name": "地产", "zljlr": -4.0, "zdf": -2.2},
                    ],
                },
                "hot_plates": [
                    {"name": "军工", "order": 1, "rate": 9.5},
                    {"name": "机器人", "order": 4, "rate": 5.2},
                ],
                "hot_rank_top30": [
                    {"code": "000001", "sector": "军工"},
                    {"code": "000002", "sector": "军工"},
                    {"code": "000003", "sector": "机器人"},
                ],
                "tag_distribution": {"军工": 6, "机器人": 2},
                "sector_quadrant": {},
            },
            helpers={
                "_get_or_create_sector_bucket": fake_get_or_create_sector_bucket,
                "_safe_float": lambda value, default=0.0: default if value in (None, "") else float(value),
                "_clamp": lambda value, low, high: max(low, min(high, value)),
                "get_sector_hotlist_weight": lambda sector_name, tag_distribution: {"军工": 60.0, "机器人": 5.0, "地产": 0.0}.get(sector_name, 0.0),
                "_match_sector_quadrant_snapshot": lambda sector_name, sector_quadrant: {
                    "军工": {"quality_score": 70.0, "label": "最佳击球区"},
                    "机器人": {"quality_score": 40.0, "label": "普通击球区"},
                    "地产": {"quality_score": 10.0, "label": "边缘击球区"},
                }.get(sector_name, {}),
                "stock_matches_sector": lambda stock, sector_name: stock.get("sector") == sector_name,
                "load_recent_sector_flow_history": lambda target_date, sector_name, lookback_days=2: [{"date": "2026-04-21", "inflow": 6.0}],
                "get_mainline_star_level": lambda net_inflow, zt_count, dt_count=0, hot_weight=0.0, inflow_history=None: {
                    "star_level": "⭐⭐⭐⭐" if net_inflow >= 10 else ("⭐⭐" if net_inflow > 0 else "⭐"),
                    "score_pct": 80.0 if net_inflow >= 10 else (30.0 if net_inflow > 0 else 10.0),
                    "trend_label": "资金回流增强" if net_inflow > 0 else "资金连续收缩",
                    "flow_trend": "improving" if net_inflow > 0 else "weakening",
                },
            },
        )

        self.assertEqual([item["name"] for item in result[:3]], ["军工", "机器人", "地产"])
        self.assertEqual(result[0]["role"], "main")
        self.assertEqual(result[0]["hot_stock_count"], 2)
        self.assertEqual(result[0]["dragon_count"], 1)
        self.assertIn("板块热榜#1", result[0]["evidence"])
        self.assertEqual(result[1]["role"], "secondary")
        self.assertEqual(result[1]["strength"], "probe")
        self.assertEqual(result[2]["role"], "observe")
        self.assertLess(result[2]["unified_score"], result[1]["unified_score"])


if __name__ == "__main__":
    unittest.main()
