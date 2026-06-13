import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def _m(*parts):
    return "".join(parts)

from selection.special_probe_runtime import (
    build_abnormal_watch_anchor_candidates,
    build_abnormal_probe_group,
    build_special_probe_focus_text,
    build_special_probe_verdict,
    get_abnormal_follow_risk_signal,
    score_candidate_decision_stack,
    sort_decision_stack_candidates,
)


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
        "pandas": _stub_module("pandas"),
    }}
)
""".format(scripts_path=str(ROOT / "scripts"))

    return subprocess.run(
        [sys.executable, "-c", stub_setup + "\n" + script_body],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )


class SpecialProbeRuntimeTest(unittest.TestCase):
    def test_legacy_special_probe_wrappers_stop_injecting_runtime_defaults(self):
        result = _run_legacy_entry_probe(
            """
import daily_report_entry_demo
from unittest.mock import patch

with patch.object(daily_report_entry_demo, "run_build_abnormal_watch_anchor_candidates", return_value=[]) as anchor_mock, \
     patch.object(daily_report_entry_demo, "run_build_abnormal_probe_group", return_value={}) as group_mock, \
     patch.object(daily_report_entry_demo, "run_build_special_probe_verdict", return_value={"summary_text": ""}) as verdict_mock:
    daily_report_entry_demo._build_abnormal_watch_anchor_candidates(abnormal_watch_pool=[{"code": "000001"}], target_date="2026-04-22")
    daily_report_entry_demo._build_abnormal_probe_group(abnormal_watch_pool=[{"code": "000001"}], mainline_name="军工")
    daily_report_entry_demo._build_special_probe_verdict(abnormal_probe_group={"pool_size": 1}, mainline_name="军工")

assert "helpers" not in anchor_mock.call_args.kwargs
assert "helpers" not in group_mock.call_args.kwargs
assert "helpers" not in verdict_mock.call_args.kwargs
"""
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_build_abnormal_watch_anchor_candidates_uses_runtime_default_dependencies(self):
        from selection import special_probe_runtime as runtime

        with patch.object(runtime, "_default_fetch_recent_price_bars", side_effect=[[{"date": "2026-04-22"}], [{"date": "2026-04-22"}]]), \
             patch.object(runtime, "_default_evaluate_live_tradability", return_value={"report_day_is_one_word": False}), \
             patch.object(runtime, "_default_build_waiting_stock_plan", return_value={"stop_plan": {}, "decision_stack": {"setup_priority_score": 90}}), \
             patch.object(runtime, "_default_score_execution_candidate", side_effect=lambda candidate, ev_calibration=None: dict(candidate)), \
             patch.object(runtime, "_default_sort_watch_anchor_candidates", side_effect=lambda items, **kwargs: list(items)):
            candidates = runtime.build_abnormal_watch_anchor_candidates(
                abnormal_watch_pool=[
                    {
                        "code": "000001",
                        "name": "军工一号",
                        "sector": "军工",
                        "follow_state": "跌不下去",
                        "setup_signal_id": "burst_hold",
                        "setup_signal_label": "大阳后抗跌",
                        "setup_signal_phase": "hold",
                        "abnormal_score": 88,
                        "anchor_price": 12.3,
                        "display_anchor_price": 11.8,
                        "action_rule": "只跟踪异常承接，不直接下单",
                        "confirm_price_60m": 12.66,
                        "confirm_support_60m": 11.95,
                        "structure_stop_30m": 11.5,
                        "confirm_rule_60m": "60分钟站稳",
                        "is_mainline": True,
                    }
                ],
                existing_candidates=[],
                seed_candidates=[{"code": "000001", "name": "军工一号", "sector": "军工", "close": 12.3}],
                target_date="2026-04-22",
                mainline_name="军工",
                final_gate={"can_new_entry": False},
                state_machine_snapshot={"leading_line": "军工"},
                helpers={"_split_abnormal_watch_pool": lambda pool: (list(pool), [])},
            )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["code"], "000001")

    def test_get_abnormal_follow_risk_signal_handles_degraded_snapshot_and_gem_breathing(self):
        degraded = get_abnormal_follow_risk_signal(
            {"abnormal_is_degraded_snapshot": True},
            helpers={"_is_degraded_abnormal_snapshot": lambda item: bool(item.get("abnormal_is_degraded_snapshot"))},
        )
        gem = get_abnormal_follow_risk_signal(
            {"watch_source": "gem_breathing_20cm", "abnormal_follow_state": "预启动呼吸感"},
            helpers={"_is_degraded_abnormal_snapshot": lambda item: False},
        )

        self.assertEqual(degraded["light"], "🟠 橙灯")
        self.assertIn("降级异常快照", degraded["reason"])
        self.assertEqual(gem["light"], "🟡 黄灯")
        self.assertIn("创业板20cm预启动", gem["reason"])

    def test_get_abnormal_follow_risk_signal_maps_follow_states_to_risk(self):
        strong = get_abnormal_follow_risk_signal(
            {"abnormal_follow_state": "跌不下去", "abnormal_setup_signal_label": "大阳后抗跌"},
            helpers={"_is_degraded_abnormal_snapshot": lambda item: False},
        )
        weak = get_abnormal_follow_risk_signal(
            {"abnormal_follow_state": "已经转弱", "abnormal_type": "放量大阳异动"},
            helpers={"_is_degraded_abnormal_snapshot": lambda item: False},
        )

        self.assertEqual(strong["light"], "🟢 绿灯")
        self.assertEqual(strong["delta"], -12)
        self.assertIn("承接强", strong["reason"])
        self.assertEqual(weak["light"], "🔴 红灯")
        self.assertEqual(weak["delta"], 22)
        self.assertIn("已经转弱", weak["reason"])

    def test_score_candidate_decision_stack_builds_contextual_scores(self):
        scored = score_candidate_decision_stack(
            {
                "code": "000001",
                "name": "军工一号",
                "sector": "军工",
                "entry_range": (12.1, 12.6),
                "minute_plan": {"confirm_price_60m": 12.66, "confirm_support_60m": 11.88},
                "stop_plan": {"effective_stop": 11.55},
                "permission_label": "明天参与资格",
                "ev_pct": 0.02,
                "open": 12.0,
                "high": 12.8,
                "low": 11.9,
                "close": 12.5,
                "change": 4.2,
            },
            final_gate={"can_new_entry": True},
            mainline_name="军工",
            conviction_codes={"000001"},
            leader_memory_codes=set(),
            state_machine_snapshot={"execution_bias": "divergence_only"},
            target_date="2026-04-22",
            helpers={
                "normalize_stock_code": lambda code: str(code or ""),
                "sector_name_matches": lambda left, right: left == right,
                "_resolve_candidate_follow_state": lambda item: "跌不下去",
                "_resolve_candidate_setup_id": lambda item: "burst_hold",
                "_is_one_word_limit_bar": lambda **kwargs: False,
                "_get_setup_priority_score": lambda setup_id="", follow_state="": 92,
                "_build_washout_reclaim_context": lambda *args, **kwargs: {
                    "active": True,
                    "recognition_ok": True,
                    "within_3d_window": True,
                },
                "_build_trend_continuation_context": lambda *args, **kwargs: {
                    "active": False,
                    "recognition_ok": False,
                    "act_right": False,
                },
                "_candidate_has_formal_abnormal_setup": lambda item: True,
                "_candidate_is_resilient_abnormal": lambda item: True,
                "_safe_float": lambda value, default=0.0: float(default if value in (None, "") else value),
                "_clamp": lambda value, low, high: max(low, min(high, value)),
                "DECISION_STACK_ORDER_TEXT": "环境 -> 主线 -> 记忆 -> 触发 -> 可交易性 -> EV",
            },
        )

        stack = scored["decision_stack"]
        self.assertEqual(stack["environment_score"], 76)
        self.assertEqual(stack["mainline_score"], 100)
        self.assertEqual(stack["memory_score"], 100)
        self.assertEqual(stack["trigger_score"], 102)
        self.assertEqual(stack["tradability_score"], 100)
        self.assertEqual(stack["ev_score"], 60.0)
        self.assertTrue(stack["has_formal_abnormal_setup"])
        self.assertTrue(scored["report_day_is_one_word"] is False)

    def test_score_candidate_decision_stack_uses_single_confirmation_bonus_when_washout_and_trend_overlap(self):
        scored = score_candidate_decision_stack(
            {
                "code": "000001",
                "name": "军工一号",
                "sector": "军工",
                "entry_range": (12.1, 12.6),
                "minute_plan": {"confirm_price_60m": 12.66},
                "stop_plan": {"effective_stop": 11.55},
                "ev_pct": 0.02,
            },
            final_gate={"can_new_entry": True},
            mainline_name="军工",
            conviction_codes={"000001"},
            leader_memory_codes={"000001"},
            target_date="2026-04-22",
            helpers={
                "normalize_stock_code": lambda code: str(code or ""),
                "sector_name_matches": lambda left, right: left == right,
                "_resolve_candidate_follow_state": lambda item: "跌不下去",
                "_resolve_candidate_setup_id": lambda item: "burst_hold",
                "_is_one_word_limit_bar": lambda **kwargs: False,
                "_get_setup_priority_score": lambda setup_id="", follow_state="": 92,
                "_build_washout_reclaim_context": lambda *args, **kwargs: {
                    "active": True,
                    "recognition_ok": True,
                    "within_3d_window": True,
                },
                "_build_trend_continuation_context": lambda *args, **kwargs: {
                    "active": True,
                    "recognition_ok": True,
                    "act_right": True,
                },
                "_candidate_has_formal_abnormal_setup": lambda item: True,
                "_candidate_is_resilient_abnormal": lambda item: True,
                "_safe_float": lambda value, default=0.0: float(default if value in (None, "") else value),
                "_clamp": lambda value, low, high: max(low, min(high, value)),
            },
        )

        stack = scored["decision_stack"]
        self.assertEqual(stack["trigger_score"], 102)
        self.assertEqual(stack["setup_priority_score"], 92)
        self.assertNotEqual(stack["setup_priority_score"], stack["trigger_score"])
        self.assertGreaterEqual(stack["advantage_dedup"]["repeated_advantage_count"], 1)
        self.assertEqual(stack["advantage_dedup"]["group_scores"]["price_acceptance_bonus"], 10)
        self.assertEqual(stack["market_selection_score"], 100)

    def test_sort_decision_stack_candidates_uses_stack_then_composite_tiebreakers(self):
        ordered = sort_decision_stack_candidates(
            [
                {
                    "code": "000002",
                    "decision_stack": {
                        "environment_score": 70,
                        "mainline_score": 80,
                        "memory_score": 70,
                        "trigger_score": 60,
                        "tradability_score": 50,
                    },
                    "composite_score": 91,
                    "ev": 0.06,
                    "tomorrow_strength": 88,
                },
                {
                    "code": "000001",
                    "decision_stack": {
                        "environment_score": 76,
                        "mainline_score": 100,
                        "memory_score": 100,
                        "trigger_score": 102,
                        "tradability_score": 100,
                    },
                    "composite_score": 90,
                    "ev": 0.05,
                    "tomorrow_strength": 86,
                },
            ],
            helpers={"_safe_float": lambda value, default=0.0: float(default if value in (None, "") else value)},
        )

        self.assertEqual([item["code"] for item in ordered], ["000001", "000002"])

    def test_build_abnormal_watch_anchor_candidates_builds_seed_probe_candidate(self):
        candidates = build_abnormal_watch_anchor_candidates(
            abnormal_watch_pool=[
                {
                    "code": "000001",
                    "name": "军工一号",
                    "sector": "军工",
                    "follow_state": "跌不下去",
                    "setup_signal_id": "burst_hold",
                    "setup_signal_label": "大阳后抗跌",
                    "setup_signal_phase": "hold",
                    "abnormal_score": 88,
                    "anchor_price": 12.3,
                    "display_anchor_price": 11.8,
                    "action_rule": "只跟踪异常承接，不直接下单",
                    "confirm_price_60m": 12.66,
                    "confirm_support_60m": 11.95,
                    "structure_stop_30m": 11.5,
                    "confirm_rule_60m": "60分钟站稳",
                    "is_mainline": True,
                }
            ],
            existing_candidates=[],
            seed_candidates=[{"code": "000001", "name": "军工一号", "sector": "军工", "close": 12.3}],
            target_date="2026-04-22",
            mainline_name="军工",
            final_gate={"can_new_entry": False},
            state_machine_snapshot={"leading_line": "军工"},
            helpers={
                "_split_abnormal_watch_pool": lambda pool: (list(pool), []),
                "fetch_recent_price_bars": lambda *args, **kwargs: [],
                "evaluate_live_tradability": lambda *args, **kwargs: {"report_day_is_one_word": False},
                "build_waiting_stock_plan": lambda payload, *args, **kwargs: {
                    "name": payload["name"],
                    "code": payload["code"],
                    "sector": payload["sector"],
                    "stop_plan": {},
                    "decision_stack": {"setup_priority_score": 90},
                },
                "get_abnormal_follow_risk_signal": lambda stock: {"light": "🟢 绿灯"},
                "sort_watch_anchor_candidates": lambda items, **kwargs: list(items),
            },
        )

        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        self.assertEqual(candidate["code"], "000001")
        self.assertEqual(candidate["watch_source"], "abnormal_probe")
        self.assertEqual(candidate["permission_label"], "异常观察权")
        self.assertEqual(candidate["risk_level"], "🟢 低风险")
        self.assertEqual(candidate["raw_risk_score"], 18)
        self.assertEqual(candidate["minute_plan"]["confirm_price_60m"], 12.66)
        self.assertEqual(candidate["minute_plan"]["confirm_support_60m"], 11.95)

    def test_build_abnormal_probe_group_selects_mainline_crossline_and_validation_probe(self):
        group = build_abnormal_probe_group(
            style_switch_snapshot={"style_code": "dual", "style_label": "双轨准备"},
            abnormal_watch_pool=[
                {"code": "000001", "sector": "军工", "follow_state": "跌不下去", "abnormal_score": 88, "is_mainline": True},
                {"code": "000002", "sector": "消费", "follow_state": "缩量消化", "abnormal_score": 77, "is_mainline": False},
                {"code": "000003", "sector": "军工", "follow_state": "跌不下去", "abnormal_score": 66, "is_mainline": False},
            ],
            mainline_name="军工",
            watch_anchor={"code": "000009", "name": "备用锚点"},
            helpers={
                "_split_abnormal_watch_pool": lambda pool: (list(pool), []),
                "_is_degraded_abnormal_snapshot": lambda item: False,
                "_candidate_matches_mainline": lambda item, mainline_name="": item.get("sector") == mainline_name,
                "_safe_float": lambda value, default=0.0: float(value or default),
                "normalize_stock_code": lambda code: str(code or ""),
            },
        )

        self.assertEqual(group["mainline_abnormal_probe"]["code"], "000001")
        self.assertEqual(group["crossline_abnormal_probe"]["code"], "000002")
        self.assertEqual(group["validation_probe"]["code"], "000003")
        self.assertEqual(group["style_code"], "dual")

    def test_crossline_upgrade_ready_probe_surfaces_upgrade_verdict_and_focus_text(self):
        abnormal_probe_group = {
            "crossline_abnormal_probe": {
                "code": "300001",
                "name": "跨线探针",
                "follow_state": "跌不下去",
                "watch_anchor_note": "跨线对象，只用于观察强弱，不代表主攻线从军工切换",
            },
            "fallback_watch_anchor": {"code": "000009", "name": "备用锚点"},
        }
        helpers = {
            "_derive_watch_anchor_note": lambda probe, mainline_name="": probe.get("watch_anchor_note", ""),
            "_build_candidate_feedback_clock": lambda **kwargs: {
                "ready": True,
                "has_confirmation_chain": True,
                "history_feedback": {"continuous_days": 2},
            },
            "_requires_crossline_second_confirmation": lambda candidate, mainline_name="": True,
            "_safe_float": lambda value, default=0.0: float(value or default),
            "_candidate_matches_mainline": lambda candidate, mainline_name="": False,
            "build_mainline_upgrade_probe_context": lambda *args, **kwargs: {},
            "format_abnormal_probe_text": lambda *args, **kwargs: "",
        }

        verdict = build_special_probe_verdict(
            abnormal_probe_group=abnormal_probe_group,
            watch_anchor_type="跨线外溢确认先看谁",
            mainline_name="军工",
            target_date="2026-04-23",
            helpers=helpers,
        )
        focus_text = build_special_probe_focus_text(
            abnormal_probe_group=abnormal_probe_group,
            watch_anchor_type="跨线外溢确认先看谁",
            mainline_name="军工",
            target_date="2026-04-23",
            helpers=helpers,
        )

        self.assertEqual(verdict["code"], "crossline_probe_upgrade_ready")
        self.assertTrue(verdict["allows_attack_50_ready"])
        self.assertIn("50%条件执行", focus_text)
        self.assertIn("固定交易窗口", focus_text)
        self.assertNotIn(_m("3", "0%", "条件", "试错"), focus_text)
        self.assertIn("跨线探针(300001)", focus_text)


if __name__ == "__main__":
    unittest.main()
