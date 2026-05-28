import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def _m(*parts):
    return "".join(parts)

from report.front_summary_builder import (
    build_front_mainline_label_contract,
    build_front_style_action_text_contract,
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
    }}
)
""".format(scripts_path=str(ROOT / "scripts"))

    return subprocess.run(
        [sys.executable, "-c", stub_setup + "\n" + script_body],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )


class FrontSummarySupportTest(unittest.TestCase):
    def _load_module(self):
        try:
            return __import__("report.front_summary_support", fromlist=["front_summary_support"])
        except ModuleNotFoundError as error:
            self.fail(f"report.front_summary_support should exist: {error}")

    def test_legacy_entry_front_summary_helpers_resolve_to_support_exports(self):
        result = _run_legacy_entry_probe(
            """
import daily_report_entry_demo
from report import front_summary_support

assert daily_report_entry_demo._build_front_mainline_label is front_summary_support.build_front_mainline_label
assert daily_report_entry_demo._build_front_style_action_text is front_summary_support.build_front_style_action_text
assert daily_report_entry_demo._render_core_mvp_digest is front_summary_support.render_core_mvp_digest
assert daily_report_entry_demo._render_mvp_focus_summary is front_summary_support.render_mvp_focus_summary
"""
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_legacy_entry_front_summary_action_wrappers_stop_injecting_helpers(self):
        result = _run_legacy_entry_probe(
            """
import daily_report_entry_demo
from unittest.mock import patch

with patch.object(daily_report_entry_demo, "run_build_bridge_prep_context", return_value={"active": False}) as bridge_mock, \
     patch.object(daily_report_entry_demo, "run_build_front_follow_action_text", return_value="只做核心") as follow_mock, \
     patch.object(daily_report_entry_demo, "run_build_front_structure_layer_text", return_value="结构只看唯一动作") as structure_mock:
    daily_report_entry_demo._build_bridge_prep_context(position_level="二档（防守档）")
    daily_report_entry_demo._build_front_follow_action_text(final_gate={"can_new_entry": True})
    daily_report_entry_demo._build_front_structure_layer_text(final_gate={"can_new_entry": True})

assert "helpers" not in bridge_mock.call_args.kwargs
assert "helpers" not in follow_mock.call_args.kwargs
assert "helpers" not in structure_mock.call_args.kwargs
"""
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_front_summary_support_label_helpers_reuse_contract_logic(self):
        support = self._load_module()

        self.assertEqual(
            support.build_front_mainline_label(
                {"observation": {"densest_sector": "军工"}, "state_machine": {"leading_line": "军工"}},
                fallback_mainline="",
            ),
            build_front_mainline_label_contract(
                {"observation": {"densest_sector": "军工"}, "state_machine": {"leading_line": "军工"}},
                fallback_mainline="",
            ),
        )
        self.assertEqual(
            support.build_front_style_action_text(
                style_switch={"style_label": "轮动", "primary_action": "先缩范围"},
                final_gate={"final_action": "只做核心"},
                best_stock={"name": "军工一号", "code": "000001"},
            ),
            build_front_style_action_text_contract(
                style_switch={"style_label": "轮动", "primary_action": "先缩范围"},
                final_gate={"final_action": "只做核心"},
                best_stock={"name": "军工一号", "code": "000001"},
            ),
        )

    def test_render_core_mvp_digest_support_injects_helpers_into_contract(self):
        support = self._load_module()

        with patch("report.front_summary_support.render_core_mvp_digest_contract", return_value={"report": "ok"}) as contract_mock:
            result = support.render_core_mvp_digest(
                {"state_machine": {}},
                {"final_action": "只做核心"},
                "三档（进攻档）",
                "环境修复",
                build_gem_textbook_next_step_text=lambda *args, **kwargs: "只观察",
                build_alignment_pool_text=lambda **kwargs: "月度站队池：军工",
                build_mainline_rotation_snapshot=lambda **kwargs: {"summary_text": "军工轮动"},
                resolve_primary_mainline_name=lambda *args, **kwargs: "军工",
                build_weak_to_strong_context=lambda **kwargs: {"active": False, "summary_text": ""},
                get_contract_logic_digest_text=lambda: "环境 -> 主线 -> 执行",
                render_front_digest=lambda payload: payload,
                safe_float=lambda value: float(value or 0),
            )

        self.assertEqual(result, {"report": "ok"})
        self.assertIs(contract_mock.call_args.kwargs["build_front_mainline_label"], support.build_front_mainline_label)
        self.assertIs(contract_mock.call_args.kwargs["build_front_style_action_text"], support.build_front_style_action_text)

    def test_render_mvp_focus_summary_support_injects_helpers_into_contract(self):
        support = self._load_module()

        with patch("report.front_summary_support.render_mvp_focus_summary_contract", return_value={"focus": "ok"}) as contract_mock:
            result = support.render_mvp_focus_summary(
                {"state_machine": {}},
                resolve_primary_mainline_name=lambda *args, **kwargs: "军工",
                split_abnormal_watch_pool=lambda pool: (pool or [], []),
                build_bridge_prep_context=lambda **kwargs: {"active": False},
                build_front_structure_layer_text=lambda **kwargs: "结构层通过",
                build_special_probe_verdict=lambda **kwargs: {"summary_text": "先看主线异动"},
                build_special_probe_focus_text=lambda **kwargs: "先看异动",
                build_mainline_rotation_snapshot=lambda **kwargs: {"summary_text": "军工轮动"},
                split_candidates_by_mainline=lambda watchlist, mainline_name: (watchlist or [], []),
                format_candidate_preview=lambda items, formatter, limit=2: "",
                candidate_matches_mainline=lambda item, mainline_name: True,
                build_position_sizing_decision=lambda **kwargs: {},
                build_cycle_triplet_texts=lambda **kwargs: {},
                build_execute_anchor_window_text=lambda **kwargs: "",
                format_abnormal_probe_text=lambda **kwargs: "",
                build_front_follow_action_text=lambda **kwargs: "只等唯一目标确认",
                render_mvp_focus_summary=lambda payload: payload,
            )

        self.assertEqual(result, {"focus": "ok"})
        self.assertEqual(contract_mock.call_args[0][0], {"state_machine": {}})
        self.assertEqual(contract_mock.call_args.kwargs["build_front_follow_action_text"](), "只等唯一目标确认")

    def test_build_front_follow_action_text_support_returns_execute_message_for_single_target(self):
        support = self._load_module()
        builder = getattr(support, "build_front_follow_action_text", None)
        self.assertIsNotNone(builder)

        result = builder(
            final_gate={"can_new_entry": True, "final_action": "只做核心"},
            best_stock={"name": "军工一号", "code": "000001"},
            watch_anchor_type="明天唯一能买的那只",
            position_level="三档（进攻档）",
            state_machine_snapshot={"execution_bias": "allow_execute", "leading_line": "军工"},
            target_date="2026-04-22",
            helpers={
                "_front_position_guard_label": lambda position_level="": "进攻档",
                "_build_bridge_prep_context": lambda **kwargs: {"active": False},
                "_build_position_sizing_decision": lambda **kwargs: {
                    "target_position_pct": 50,
                    "trigger_text": "09:50-10:10站上12.34且不破11.80",
                },
                "_build_execute_anchor_window_text": lambda **kwargs: "",
                "_build_philosophy_constraint_text": lambda **kwargs: "不为新故事切掉旧事实",
                "_safe_float": lambda value, default=0.0: default if value in (None, "") else float(value),
            },
        )

        self.assertEqual(result, "只做唯一对象，09:50-10:10站上12.34且不破11.80后按50%执行；不为新故事切掉旧事实")

    def test_build_front_follow_action_text_support_uses_runtime_default_dependencies(self):
        support = self._load_module()

        with patch.object(support, "_default_build_position_sizing_decision", return_value={
            "target_position_pct": 50,
            "trigger_text": "09:50-10:10站上12.34且不破11.80",
        }), \
            patch.object(support, "_default_build_philosophy_constraint_text", return_value="不为新故事切掉旧事实"):
            result = support.build_front_follow_action_text(
                final_gate={"can_new_entry": True, "final_action": "只做核心"},
                best_stock={"name": "军工一号", "code": "000001"},
                watch_anchor_type="明天唯一能买的那只",
                position_level="三档（进攻档）",
                state_machine_snapshot={"execution_bias": "allow_execute", "leading_line": "军工"},
                target_date="2026-04-22",
                helpers={
                    "_build_bridge_prep_context": lambda **kwargs: {"active": False},
                },
            )

        self.assertEqual(result, "只做唯一对象，09:50-10:10站上12.34且不破11.80后按50%执行；不为新故事切掉旧事实")

    def test_build_front_structure_layer_text_support_returns_execute_50_message(self):
        support = self._load_module()
        builder = getattr(support, "build_front_structure_layer_text", None)
        self.assertIsNotNone(builder)

        result = builder(
            final_gate={"can_new_entry": True},
            best_stock={"name": "军工一号", "code": "000001"},
            position_level="三档（进攻档）",
            state_machine_snapshot={"leading_line": "军工"},
            target_date="2026-04-22",
            helpers={
                "_build_bridge_prep_context": lambda **kwargs: {"active": False},
                "_build_position_sizing_decision": lambda **kwargs: {
                    "target_position_pct": 50,
                    "trigger_text": "09:50-10:10站上12.34且不破11.80",
                },
                "_build_execute_anchor_window_text": lambda **kwargs: "",
                "_build_philosophy_constraint_text": lambda **kwargs: "不为新故事切掉旧事实",
                "_safe_float": lambda value, default=0.0: default if value in (None, "") else float(value),
                "_front_position_guard_label": lambda position_level="": "进攻档",
            },
        )

        self.assertEqual(result, "市场已允许出手，而且已经缩到一只可买股；只做50%执行仓，09:50-10:10站上12.34且不破11.80后才动手；不为新故事切掉旧事实")

    def test_front_follow_action_text_passes_focus_keep_counts_to_position_sizing(self):
        support = self._load_module()
        captured_final_gate = {}

        result = support.build_front_follow_action_text(
            final_gate={"can_new_entry": True},
            best_stock={"name": "军工一号", "code": "000001"},
            watch_anchor=None,
            watch_anchor_type="明天唯一能买的那只",
            focus_group=[{"name": "军工一号", "code": "000001"}],
            keep_group=[{"name": "军工二号", "code": "000002"}],
            position_level="三档（进攻档）",
            state_machine_snapshot={"execution_bias": "allow_execute", "leading_line": "军工"},
            target_date="2026-04-22",
            helpers={
                "_build_bridge_prep_context": lambda **kwargs: {"active": False},
                "_build_position_sizing_decision": lambda **kwargs: (
                    captured_final_gate.update(kwargs.get("final_gate") or {})
                    or {"target_position_pct": 50, "trigger_text": "固定交易窗口内条件成立"}
                ),
                "_build_execute_anchor_window_text": lambda **kwargs: "",
                "_build_philosophy_constraint_text": lambda **kwargs: "",
                "_safe_float": lambda value, default=0.0: default if value in (None, "") else float(value),
            },
        )

        self.assertEqual(captured_final_gate["candidate_count"], 2)
        self.assertEqual(captured_final_gate["unique_target_count"], 2)
        self.assertIn("50%执行", result)
        self.assertNotIn(_m("30%", "条件试错"), result)

    def test_front_summary_support_maps_legacy_30_position_to_50_attack_window(self):
        support = self._load_module()

        follow_text = support.build_front_follow_action_text(
            final_gate={"can_new_entry": True},
            best_stock=None,
            watch_anchor=None,
            watch_anchor_type="",
            focus_group=[{"name": "军工一号", "code": "000001"}],
            keep_group=[],
            position_level="二档（防守档）",
            state_machine_snapshot={"execution_bias": "allow_execute", "leading_line": "军工"},
            target_date="2026-04-22",
            special_probe_verdict={"probe_state": "probe_crossline_upgrade_ready"},
            helpers={
                "_build_bridge_prep_context": lambda **kwargs: {"active": False},
                "_build_position_sizing_decision": lambda **kwargs: {"target_position_pct": 30, "trigger_text": "固定交易窗口内条件成立"},
                "_build_execute_anchor_window_text": lambda **kwargs: "",
                "_build_philosophy_constraint_text": lambda **kwargs: "",
                "_safe_float": lambda value, default=0.0: default if value in (None, "") else float(value),
            },
        )
        structure_text = support.build_front_structure_layer_text(
            final_gate={"can_new_entry": True},
            focus_group=[{"name": "军工一号", "code": "000001"}],
            keep_group=[],
            best_stock=None,
            watch_anchor=None,
            watch_anchor_type="",
            position_level="二档（防守档）",
            state_machine_snapshot={"execution_bias": "allow_execute", "leading_line": "军工"},
            target_date="2026-04-22",
            special_probe_verdict={"probe_state": "probe_crossline_upgrade_ready"},
            helpers={
                "_build_bridge_prep_context": lambda **kwargs: {"active": False},
                "_build_position_sizing_decision": lambda **kwargs: {"target_position_pct": 30, "trigger_text": "固定交易窗口内条件成立"},
                "_build_execute_anchor_window_text": lambda **kwargs: "",
                "_build_philosophy_constraint_text": lambda **kwargs: "",
                "_safe_float": lambda value, default=0.0: default if value in (None, "") else float(value),
                "_front_position_guard_label": lambda position_level="": "0%观察",
            },
        )

        rendered = f"{follow_text}\n{structure_text}"
        self.assertIn("50%标准进攻", rendered)
        self.assertIn("固定交易窗口", rendered)
        self.assertNotIn(_m("30%", "条件试错"), rendered)
        self.assertNotIn(_m("30%", "条件试错仓"), rendered)

    def test_front_structure_layer_text_deduplicates_same_code_for_position_sizing(self):
        support = self._load_module()
        captured_final_gate = {}

        support.build_front_structure_layer_text(
            final_gate={"can_new_entry": True},
            focus_group=[{"name": "军工一号", "code": "000001"}],
            keep_group=[{"name": "军工一号", "code": "000001", "sector": "军工", "direction": "低空经济"}],
            best_stock={"name": "军工一号", "code": "000001"},
            watch_anchor=None,
            watch_anchor_type="明天唯一能买的那只",
            position_level="三档（进攻档）",
            state_machine_snapshot={"execution_bias": "allow_execute", "leading_line": "军工"},
            target_date="2026-04-22",
            helpers={
                "_build_bridge_prep_context": lambda **kwargs: {"active": False},
                "_build_position_sizing_decision": lambda **kwargs: (
                    captured_final_gate.update(kwargs.get("final_gate") or {})
                    or {"target_position_pct": 50, "trigger_text": "固定交易窗口内条件成立"}
                ),
                "_build_execute_anchor_window_text": lambda **kwargs: "",
                "_build_philosophy_constraint_text": lambda **kwargs: "",
                "_safe_float": lambda value, default=0.0: default if value in (None, "") else float(value),
                "_front_position_guard_label": lambda position_level="": "进攻档",
            },
        )

        self.assertEqual(captured_final_gate["candidate_count"], 2)
        self.assertEqual(captured_final_gate["unique_target_count"], 1)

    def test_front_summary_support_builds_bridge_prep_context(self):
        support = self._load_module()

        result = support.build_bridge_prep_context(
            position_level="二档（防守档）",
            final_gate={"can_new_entry": False},
            watch_anchor={
                "name": "军工一号",
                "code": "000001",
                "follow_state": "跌不下去",
                "setup_signal_id": "burst_hold",
                "minute_plan": {"confirm_price_60m": 12.34},
                "display_anchor_price": 11.8,
            },
            watch_anchor_type="主线重点观察谁",
            state_machine_snapshot={"execution_bias": "prep_only"},
            helpers={
                "_round_or_none": lambda value, digits=2: round(float(value), digits),
                "_resolve_candidate_setup_id": lambda candidate=None: candidate.get("setup_signal_id", ""),
            },
        )

        self.assertTrue(result["active"])
        self.assertTrue(result["priority_keep"])
        self.assertEqual(result["candidate_label"], "军工一号(000001)")
        self.assertIn("12.34", result["upgrade_text"])
        self.assertIn("11.80", result["upgrade_text"])
        self.assertNotIn("防守档", result["summary_text"])

    def test_front_summary_support_formats_candidate_preview_and_guard_label(self):
        support = self._load_module()

        preview = support.format_candidate_preview(
            [{"name": "军工一号"}, {"name": "机器人一号"}],
            lambda item: item["name"],
            limit=2,
        )
        self.assertEqual(preview, "军工一号 / 机器人一号")
        self.assertEqual(support.front_position_guard_label("二档（防守档）"), "0%观察")
        self.assertEqual(support.front_position_guard_label("三档（进攻档）"), "50%进攻")
        self.assertEqual(support.front_position_guard_label(""), "当前档位")


if __name__ == "__main__":
    unittest.main()
