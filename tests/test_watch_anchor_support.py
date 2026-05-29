import subprocess
import sys
import unittest
from pathlib import Path

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

    return subprocess.run(
        [sys.executable, "-c", stub_setup + "\n" + script_body],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )


class WatchAnchorSupportTest(unittest.TestCase):
    def _load_module(self):
        try:
            return __import__("selection.watch_anchor_support", fromlist=["watch_anchor_support"])
        except ModuleNotFoundError as error:
            self.fail(f"selection.watch_anchor_support should exist: {error}")

    def test_legacy_watch_anchor_wrappers_delegate_to_support_runtime(self):
        result = _run_legacy_entry_probe(
            """
import daily_report_entry_demo
from unittest.mock import patch

candidate = {
    "watch_source": "keep_group_watch",
    "risk_level": "🟡 中风险",
    "raw_risk_score": 12,
    "repair_buffers": ["五日线"],
    "follow_state": "跌不下去",
    "setup_signal_id": "burst_hold",
}

def _append_side_effect(lines, wrapped_candidate, prefix="  ", helpers=None):
    lines.append(f"{prefix}runtime-note")

with patch.object(daily_report_entry_demo, "run_classify_watch_anchor_bucket", return_value=(4, "强分歧未坏")) as bucket_mock, \
     patch.object(daily_report_entry_demo, "run_requires_crossline_second_confirmation", return_value=True) as second_mock, \
     patch.object(daily_report_entry_demo, "run_derive_watch_anchor_type", return_value="跨线外溢确认先看谁") as type_mock, \
     patch.object(daily_report_entry_demo, "run_derive_pending_candidate_type", return_value="跨线强分歧先盯哪只") as pending_mock, \
     patch.object(daily_report_entry_demo, "run_derive_watch_anchor_note", return_value="跨线对象，只观察不切线") as note_mock, \
     patch.object(daily_report_entry_demo, "run_append_watch_anchor_note", side_effect=_append_side_effect) as append_mock:
    bucket = daily_report_entry_demo._classify_watch_anchor_bucket(candidate)
    second = daily_report_entry_demo._requires_crossline_second_confirmation(candidate, "军工")
    anchor_type = daily_report_entry_demo._derive_watch_anchor_type(candidate, mainline_name="军工")
    pending_type = daily_report_entry_demo._derive_pending_candidate_type(candidate, mainline_name="军工")
    note = daily_report_entry_demo._derive_watch_anchor_note(candidate, mainline_name="军工")
    lines = []
    daily_report_entry_demo._append_watch_anchor_note(lines, {"watch_anchor_note": "保留"}, prefix=">> ")

assert bucket_mock.call_args[0][0] == candidate
assert "helpers" in bucket_mock.call_args.kwargs
assert second_mock.call_args[0] == (candidate, "军工")
assert "helpers" in second_mock.call_args.kwargs
assert type_mock.call_args[0] == (candidate, "军工")
assert "helpers" in type_mock.call_args.kwargs
assert pending_mock.call_args[0] == (candidate, "军工")
assert "helpers" in pending_mock.call_args.kwargs
assert note_mock.call_args[0] == (candidate, "军工")
assert "helpers" in note_mock.call_args.kwargs
assert append_mock.call_args[0] == (lines, {"watch_anchor_note": "保留"})
assert append_mock.call_args.kwargs["prefix"] == ">> "
assert "helpers" in append_mock.call_args.kwargs
assert bucket == (4, "强分歧未坏")
assert second is True
assert anchor_type == "跨线外溢确认先看谁"
assert pending_type == "跨线强分歧先盯哪只"
assert note == "跨线对象，只观察不切线"
assert lines == [">> runtime-note"]
"""
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_legacy_select_priority_watch_anchor_wrapper_delegates_to_support_runtime(self):
        result = _run_legacy_entry_probe(
            """
import daily_report_entry_demo
from unittest.mock import patch

with patch.object(
    daily_report_entry_demo,
    "run_select_priority_watch_anchor",
    return_value=({"code": "300001"}, "创业板20cm预启动先看谁"),
) as selector_mock:
    selected = daily_report_entry_demo._select_priority_watch_anchor(
        trade_gate_open=False,
        abnormal_watch_anchor_candidates=[],
        pending_candidates=[],
        observation_candidates=[],
        waiting_stocks=[],
        gem_observation_stocks=[{"code": "300001"}],
        target_date="2026-04-22",
        mainline_name="军工",
    )

assert selector_mock.call_args.kwargs["trade_gate_open"] is False
assert selector_mock.call_args.kwargs["gem_observation_stocks"] == [{"code": "300001"}]
assert selector_mock.call_args.kwargs["target_date"] == "2026-04-22"
assert selector_mock.call_args.kwargs["mainline_name"] == "军工"
assert "helpers" in selector_mock.call_args.kwargs
assert selected == ({"code": "300001"}, "创业板20cm预启动先看谁")
"""
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_watch_anchor_support_builds_crossline_contracts(self):
        support = self._load_module()
        candidate = {
            "watch_source": "keep_group_watch",
            "abnormal_light": "🟢 绿灯",
            "risk_level": "🟡 中风险",
            "raw_risk_score": 12,
            "repair_buffers": ["五日线"],
            "sector": "机器人",
            "follow_state": "跌不下去",
            "setup_signal_id": "burst_hold",
            "decision_stack": {
                "washout_reclaim_chain": {"note": "洗盘完成，先看承接。"},
                "trend_continuation_chain": {"note": "趋势续强，但先别抢。"},
            },
        }
        helpers = {
            "_safe_float": lambda value, default=0.0: default if value in (None, "") else float(value),
            "_candidate_matches_mainline": lambda item, mainline_name="": False,
            "_resolve_candidate_setup_id": lambda item: item.get("setup_signal_id"),
            "_resolve_candidate_follow_state": lambda item: item.get("follow_state"),
        }

        bucket = support.classify_watch_anchor_bucket(candidate, helpers=helpers)
        needs_second = support.requires_crossline_second_confirmation(candidate, "军工", helpers=helpers)
        anchor_type = support.derive_watch_anchor_type(candidate, "军工", helpers=helpers)
        pending_type = support.derive_pending_candidate_type(candidate, "军工", helpers=helpers)
        note = support.derive_watch_anchor_note(candidate, "军工", helpers=helpers)
        report_lines = []
        support.append_watch_anchor_note(report_lines, {"watch_anchor_note": note}, prefix="  ")

        self.assertEqual(bucket, (4, "强分歧未坏"))
        self.assertTrue(needs_second)
        self.assertEqual(anchor_type, "跨线外溢确认先看谁")
        self.assertEqual(pending_type, "跨线强分歧先盯哪只")
        self.assertIn("不代表主攻线从军工切换", note)
        self.assertIn("洗盘完成", note)
        self.assertIn("趋势续强", note)
        self.assertEqual(report_lines, [f"  {note}"])

    def test_watch_anchor_support_sorts_candidates_with_weak_to_strong_note(self):
        support = self._load_module()
        candidates = [
            {
                "name": "普通观察",
                "code": "000002",
                "sector": "机器人",
                "watch_source": "waiting_layer",
                "risk_level": "🟡 中风险",
                "raw_risk_score": 4,
                "risk_score": 6,
                "decision_stack": {"trigger_score": 20},
            },
            {
                "name": "军工一号",
                "code": "000001",
                "sector": "军工",
                "watch_source": "keep_group_watch",
                "abnormal_light": "🟢 绿灯",
                "risk_level": "🟡 中风险",
                "raw_risk_score": 18,
                "repair_buffers": ["五日线"],
                "risk_score": 2,
                "setup_signal_id": "burst_hold",
                "follow_state": "跌不下去",
                "decision_stack": {
                    "setup_priority_score": 92,
                    "mainline_score": 8,
                    "memory_score": 7,
                    "trigger_score": 9,
                    "tradability_score": 6,
                },
            },
        ]

        ranked = support.sort_watch_anchor_candidates(
            candidates,
            mainline_name="军工",
            state_machine_snapshot={"energy_state": "扩张确认", "pulse_stage": "进攻"},
        )

        self.assertEqual(ranked[0]["code"], "000001")
        self.assertEqual(ranked[0]["watch_priority_bucket"], 4)
        self.assertGreater(ranked[0]["watch_priority_score"], ranked[1]["watch_priority_score"])
        self.assertTrue(ranked[0]["weak_to_strong_context"]["active"])
        self.assertIn("假弱非真弱", ranked[0]["watch_anchor_note"])
        self.assertEqual(ranked[1]["code"], "000002")

    def test_watch_anchor_support_deduplicates_same_source_shape_advantages(self):
        support = self._load_module()
        ranked = support.sort_watch_anchor_candidates(
            [
                {
                    "name": "重复优势样本",
                    "code": "000001",
                    "sector": "军工",
                    "watch_source": "abnormal_probe",
                    "abnormal_light": "🟢 绿灯",
                    "risk_level": "🟡 中风险",
                    "raw_risk_score": 18,
                    "repair_buffers": ["五日线"],
                    "risk_score": 2,
                    "setup_signal_id": "burst_hold",
                    "follow_state": "跌不下去",
                    "decision_stack": {
                        "setup_priority_score": 92,
                        "mainline_score": 100,
                        "memory_score": 88,
                        "trigger_score": 102,
                        "tradability_score": 75,
                        "has_formal_abnormal_setup": True,
                        "is_resilient_abnormal": True,
                    },
                    "weak_to_strong_context": {"active": True, "score_bonus": 160},
                }
            ],
            mainline_name="军工",
            state_machine_snapshot={"energy_state": "扩张确认", "pulse_stage": "进攻"},
            helpers={
                "_build_weak_to_strong_context": lambda *args, **kwargs: {
                    "active": True,
                    "score_bonus": 160,
                    "note_text": "假弱非真弱",
                },
                "_is_bridge_priority_setup": lambda *args, **kwargs: True,
            },
        )

        anchor = ranked[0]
        self.assertGreaterEqual(anchor["watch_advantage_dedup"]["repeated_advantage_count"], 4)
        self.assertEqual(anchor["watch_advantage_dedup"]["group_scores"]["shape_confirmation"], 180)
        self.assertEqual(anchor["watch_advantage_dedup"]["group_scores"]["market_selection"], 100)

    def test_watch_anchor_support_does_not_promote_weak_setup_to_full_shape_credit(self):
        support = self._load_module()
        ranked = support.sort_watch_anchor_candidates(
            [
                {
                    "name": "弱形态样本",
                    "code": "000003",
                    "sector": "军工",
                    "watch_source": "waiting_layer",
                    "risk_level": "🟡 中风险",
                    "risk_score": 0,
                    "decision_stack": {
                        "setup_priority_score": 18,
                        "trigger_score": 18,
                    },
                }
            ],
            mainline_name="军工",
        )

        self.assertLess(ranked[0]["watch_advantage_dedup"]["group_scores"]["shape_confirmation"], 180)

    def test_watch_anchor_support_prioritizes_current_high_anchor_over_waiting_layer_legacy_name(self):
        support = self._load_module()
        ranked = support.sort_watch_anchor_candidates(
            [
                {
                    "name": "京能电力",
                    "code": "600578",
                    "sector": "电力",
                    "watch_source": "waiting_layer",
                    "risk_score": 0,
                    "decision_stack": {"setup_priority_score": 18, "mainline_score": 8, "memory_score": 6},
                },
                {
                    "name": "华电能源",
                    "code": "600726",
                    "sector": "电力",
                    "watch_source": "keep_group_watch",
                    "risk_score": 0,
                    "limit_up_days": 4,
                    "is_high_anchor": True,
                    "decision_stack": {"setup_priority_score": 30, "mainline_score": 8, "memory_score": 9},
                },
            ],
            mainline_name="电力",
        )

        self.assertEqual(ranked[0]["code"], "600726")
        self.assertGreater(ranked[0]["watch_priority_score"], ranked[1]["watch_priority_score"])

    def test_watch_anchor_support_keeps_negative_weak_to_strong_feedback(self):
        support = self._load_module()
        positive = support.sort_watch_anchor_candidates(
            [
                {
                    "name": "正反馈样本",
                    "code": "000001",
                    "sector": "军工",
                    "watch_source": "abnormal_probe",
                    "risk_level": "🟡 中风险",
                    "risk_score": 0,
                    "decision_stack": {"setup_priority_score": 92, "trigger_score": 92},
                }
            ],
            mainline_name="军工",
            helpers={"_build_weak_to_strong_context": lambda *args, **kwargs: {"score_bonus": 0}},
        )[0]
        negative = support.sort_watch_anchor_candidates(
            [
                {
                    "name": "负反馈样本",
                    "code": "000002",
                    "sector": "军工",
                    "watch_source": "abnormal_probe",
                    "risk_level": "🟡 中风险",
                    "risk_score": 0,
                    "decision_stack": {"setup_priority_score": 92, "trigger_score": 92},
                }
            ],
            mainline_name="军工",
            helpers={"_build_weak_to_strong_context": lambda *args, **kwargs: {"score_bonus": -120}},
        )[0]

        self.assertLess(negative["watch_priority_score"], positive["watch_priority_score"])
        self.assertEqual(negative["watch_advantage_dedup"]["group_scores"]["shape_penalty"], -120)

    def test_watch_anchor_support_tie_break_does_not_reuse_split_source_scores(self):
        support = self._load_module()
        ranked = support.sort_watch_anchor_candidates(
            [
                {
                    "name": "重复标签样本",
                    "code": "000001",
                    "sector": "军工",
                    "watch_source": "waiting_layer",
                    "risk_score": 0,
                    "decision_stack": {
                        "setup_priority_score": 92,
                        "mainline_score": 100,
                        "memory_score": 100,
                        "trigger_score": 92,
                        "tradability_score": 50,
                    },
                },
                {
                    "name": "基础更强样本",
                    "code": "000002",
                    "sector": "军工",
                    "watch_source": "waiting_layer",
                    "risk_score": 0,
                    "decision_stack": {
                        "setup_priority_score": 92,
                        "mainline_score": 80,
                        "memory_score": 80,
                        "trigger_score": 80,
                        "tradability_score": 50,
                    },
                    "composite_score": 0.02,
                },
            ],
            mainline_name="军工",
            helpers={"_build_weak_to_strong_context": lambda *args, **kwargs: {"score_bonus": 0}},
        )

        self.assertEqual(ranked[0]["code"], "000002")

    def test_watch_anchor_support_selects_abnormal_or_gem_anchor_by_trade_gate(self):
        support = self._load_module()

        abnormal_selected = support.select_priority_watch_anchor(
            trade_gate_open=True,
            abnormal_watch_anchor_candidates=[{"code": "000001", "name": "军工一号"}],
            gem_observation_stocks=[{"code": "300001", "name": "弹性龙"}],
            mainline_name="军工",
            helpers={
                "_derive_pending_candidate_type": lambda item, mainline_name="": "明天唯一能买的那只",
                "_derive_watch_anchor_note": lambda item, mainline_name="": f"{item.get('name')}先看承接",
                "_build_gem_breathing_watch_anchor": lambda *args, **kwargs: {"code": "300001", "watch_anchor_type": "创业板20cm预启动先看谁"},
            },
        )
        gem_selected = support.select_priority_watch_anchor(
            trade_gate_open=False,
            abnormal_watch_anchor_candidates=[],
            pending_candidates=[],
            observation_candidates=[],
            waiting_stocks=[],
            gem_observation_stocks=[{"code": "300001", "name": "弹性龙"}],
            target_date="2026-04-22",
            mainline_name="军工",
            helpers={
                "_derive_watch_anchor_type": lambda item, mainline_name="": "重点观察谁",
                "_derive_watch_anchor_note": lambda item, mainline_name="": "先看承接",
                "_build_gem_breathing_watch_anchor": lambda seed, target_date="", mainline_name="": {
                    "code": seed.get("code"),
                    "name": seed.get("name"),
                    "watch_anchor_type": "创业板20cm预启动先看谁",
                },
            },
        )

        self.assertEqual(abnormal_selected[0]["watch_anchor_type"], "明天唯一能买的那只")
        self.assertIn("先看承接", abnormal_selected[0]["watch_anchor_note"])
        self.assertEqual(abnormal_selected[1], "明天唯一能买的那只")
        self.assertEqual(gem_selected, ({"code": "300001", "name": "弹性龙", "watch_anchor_type": "创业板20cm预启动先看谁"}, "创业板20cm预启动先看谁"))

    def test_watch_anchor_support_builds_execute_anchor_window_text(self):
        support = self._load_module()

        text = support.build_execute_anchor_window_text(
            {
                "active_watch": True,
                "second_shot_breakout_price": 12.34,
                "support_price": 10.5,
                "history_feedback": {
                    "active_window_days": 5,
                    "trading_days_since_latest": 2,
                },
            },
            {"display_anchor_price": 10.1},
            "执行候选观察锚点",
        )

        self.assertEqual(
            text,
            "这只票按5日活观察管理，当前还剩3日观察寿命；只有重新站上12.34且固定交易窗口内条件成立，才考虑50%标准进攻；不破10.50继续观察；过期或失守就作废",
        )

    def test_watch_anchor_support_builds_cycle_triplet_for_gem_candidate(self):
        support = self._load_module()

        result = support.build_cycle_triplet_texts(
            {
                "target_position_pct": 30,
                "trigger_text": "09:50-10:10窗口",
                "second_shot_ready": False,
            },
            {
                "watch_source": "gem_breathing_20cm",
                "setup_signal_id": "burst_digest",
                "follow_state": "缩量消化",
                "stop_plan": {"effective_stop": 8.88},
                "gem_breathing_contract": {
                    "active_window_days": 4,
                    "void_price": 9.88,
                },
            },
            "创业板20cm预启动先看谁",
        )

        self.assertIn("先给4日呼吸感观察合同", result["observation_cycle"])
        self.assertEqual(result["intervention_cycle"], "09:50-10:10窗口内满足条件后才评估50%标准进攻，确认后才算被市场指派接货，不满足继续0%观察")
        self.assertNotIn(_m("30%", "条件试错"), result["observation_cycle"] + result["intervention_cycle"] + result["exit_cycle"])
        self.assertIn("失守9.88就作废", result["exit_cycle"])
        self.assertIn("4日观察到期也作废", result["exit_cycle"])
        self.assertIn("不该失守8.88", result["exit_cycle"])


if __name__ == "__main__":
    unittest.main()
