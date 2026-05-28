import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def _m(*parts):
    return "".join(parts)

from domains.execution_chain.pk_decision_stage import (
    build_pk_decision_runtime,
    build_pk_decision_stage,
    format_closed_gate_buy_limit_text,
)
from domains.execution_chain.pk_decision_nodes.action_plan_context import build_pk_decision_action_plan_context_node
from domains.execution_chain.pk_decision_nodes.observation_pool import build_pk_decision_observation_pool_node
from domains.execution_chain.pk_decision_nodes.pk_context import build_pk_decision_pk_context_node
from domains.execution_chain.pk_decision_nodes.watch_anchor import build_pk_decision_watch_anchor_node
from domains.execution_chain.stage_runtime import build_execution_stage_lookup
from report.action_plan_renderer import render_action_plan_result, render_action_plan_section


class PkDecisionStageTest(unittest.TestCase):
    def test_pk_observation_pool_fetches_recent_bars_with_fast_fail(self):
        calls = []

        def _fetch_recent_price_bars(*args, **kwargs):
            calls.append({"args": args, "kwargs": kwargs})
            return []

        result = build_pk_decision_observation_pool_node(
            {
                "target_date": "2026-04-29",
                "final_gate": {"can_new_entry": False},
                "mainline_name": "电池",
                "market_research_snapshot": {"state_machine": {}},
                "keep_group": [{"name": "观察股", "code": "000001", "close": 10}],
                "step2_bundle": {"evaluated_stocks": []},
                "conviction_codes": set(),
                "leader_memory_codes": set(),
                "abnormal_watch_pool_all": [],
                "trade_gate_open": False,
                "ev_calibration": {},
                "scored_executable_stocks": [],
                "scored_waiting_stocks": [],
                "pending_candidates": [],
                "safe_float": lambda value, default=0.0: float(default if value in (None, "") else value),
                "score_execution_candidate": lambda stock, ev_calibration: dict(stock),
                "score_candidate_decision_stack": lambda stock, **kwargs: dict(stock),
                "sort_watch_anchor_candidates": lambda candidates, **kwargs: list(candidates),
                "get_trade_permission": lambda *args, **kwargs: {"permission_label": "观察权", "permission_reason": "等待"},
                "fetch_recent_price_bars": _fetch_recent_price_bars,
                "evaluate_live_tradability": lambda *args, **kwargs: {"can_trade": True, "report_day_is_one_word": False},
                "analyze_buy_signal": lambda *args, **kwargs: None,
                "quant_system_available": False,
                "build_waiting_stock_plan": lambda seed, *args, **kwargs: dict(seed),
                "build_abnormal_watch_anchor_candidates": lambda **kwargs: [],
            }
        )

        self.assertTrue(result["exports"]["scored_keep_watch_stocks"])
        self.assertEqual(calls[0]["kwargs"].get("fast_fail"), True)

    def test_pk_watch_anchor_crossline_fetches_recent_bars_with_fast_fail(self):
        calls = []

        def _fetch_recent_price_bars(*args, **kwargs):
            calls.append({"args": args, "kwargs": kwargs})
            return []

        result = build_pk_decision_watch_anchor_node(
            {
                "target_date": "2026-04-29",
                "final_gate": {"can_new_entry": False},
                "mainline_name": "电池",
                "market_research_snapshot": {"state_machine": {}},
                "step2_bundle": {
                    "crossline_observation_stocks": [
                        {"name": "跨线股", "code": "000002", "close": 12, "tmr_forecast": "只看承接"}
                    ],
                    "gem_observation_stocks": [],
                },
                "conviction_codes": set(),
                "leader_memory_codes": set(),
                "trade_gate_open": False,
                "pending_candidates": [],
                "observation_candidates": [],
                "waiting_stocks": [],
                "abnormal_watch_anchor_candidates": [],
                "safe_float": lambda value, default=0.0: float(default if value in (None, "") else value),
                "get_trade_permission": lambda *args, **kwargs: {"permission_label": "跨线观察权", "permission_reason": "等待"},
                "fetch_recent_price_bars": _fetch_recent_price_bars,
                "evaluate_live_tradability": lambda *args, **kwargs: {"can_trade": True, "report_day_is_one_word": False},
                "analyze_buy_signal": lambda *args, **kwargs: None,
                "quant_system_available": False,
                "build_waiting_stock_plan": lambda seed, *args, **kwargs: dict(seed),
                "derive_watch_anchor_type": lambda candidate, mainline_name="": "跨线重点观察谁",
                "derive_watch_anchor_note": lambda candidate, mainline_name="": "先看承接",
                "select_priority_watch_anchor": lambda **kwargs: ({}, ""),
            }
        )

        self.assertEqual(result["exports"]["watch_anchor"]["code"], "000002")
        self.assertEqual(calls[0]["kwargs"].get("fast_fail"), True)

    def test_conditional_defense_gate_formats_as_participation_window_not_absolute_ban(self):
        self.assertEqual(
            format_closed_gate_buy_limit_text("二档（防守档）", {"allow_attack_50_ready": True}),
            "等固定交易窗口内条件成立；未确认按0%不参与",
        )
        self.assertEqual(
            format_closed_gate_buy_limit_text("一档（空仓档）", {"allow_attack_50_ready": False}),
            "保持空仓，不新增参与",
        )

    def test_pk_decision_runtime_can_run_only_render_node_for_diagnostics(self):
        result = build_pk_decision_runtime(
            {
                "render_pk_decision_section": lambda context: ["pk-rendered"],
                "render_action_plan_section": lambda context: ["action-rendered"],
            },
            {"label": "Step 5", "title": "PK决胜局（期望值模型）"},
            enabled_node_keys=["render_sections"],
        )

        self.assertEqual(result["lines"], ["pk-rendered", "action-rendered", ""])
        self.assertEqual(result["exports"], {})

    def test_pk_decision_runtime_score_candidates_exports_best_stock(self):
        candidate = {"name": "军工一号", "code": "000001"}
        result = build_pk_decision_runtime(
            {
                "target_date": "2026-04-22",
                "run_mode": "replay",
                "final_gate": {"can_new_entry": True},
                "mainline_name": "军工",
                "market_research_snapshot": {"state_machine": {}},
                "executable_stocks": [candidate],
                "waiting_stocks": [],
                "conviction_codes": set(),
                "leader_memory_codes": set(),
                "build_strategy_ev_calibration": lambda target_date, ledger_mode=None: {"source": "ledger"},
                "score_execution_candidate": lambda stock, ev_calibration: {**stock, "score": 90},
                "score_candidate_decision_stack": lambda stock, **kwargs: {**stock, "decision_stack_score": 90},
                "sort_decision_stack_candidates": lambda candidates: list(candidates),
                "sort_watch_anchor_candidates": lambda candidates, **kwargs: list(candidates),
            },
            {"label": "Step 5", "title": "PK决胜局（期望值模型）"},
            enabled_node_keys=["score_candidates", "export_stage_state"],
        )

        self.assertEqual(result["exports"]["best_stock"]["code"], "000001")
        self.assertEqual(result["exports"]["trade_gate_open"], True)

    def test_candidate_quality_scorecard_node_can_run_alone_with_diagnostics(self):
        result = build_pk_decision_runtime(
            {
                "trade_gate_open": False,
                "position_level": "二档（防守档）",
                "step0_prediction_cn": "0%观察",
                "final_gate": {"can_new_entry": False, "allow_attack_50_ready": True},
                "has_personal_positions": True,
                "best_stock": {"name": "晶方科技", "code": "603005"},
                "watch_anchor": {"name": "上峰水泥", "code": "000672"},
                "display_observation_candidates": [
                    {
                        "name": "晶方科技",
                        "code": "603005",
                        "selection_quality": "高",
                        "entry_cost_state": "高成本",
                        "risk_flags": ["公告待确认"],
                    }
                ],
                "waiting_stocks": [
                    {
                        "name": "上峰水泥",
                        "code": "000672",
                        "selection_quality": "中",
                        "entry_cost_state": "确认中",
                    }
                ],
            },
            {"label": "Step 5", "title": "PK决胜局（期望值模型）"},
            enabled_node_keys=["candidate_quality_scorecard", "export_stage_state"],
        )

        self.assertEqual(result["exports"]["candidate_quality_panel_fields"]["daily_new_entry_limit"], 0)
        self.assertEqual(result["exports"]["candidate_quality_panel_fields"]["primary_buy_candidate"]["code"], "603005")
        self.assertEqual(result["exports"]["candidate_quality_panel_fields"]["backup_candidate"]["code"], "000672")
        self.assertEqual(
            [sample["code"] for sample in result["exports"]["candidate_quality_samples"]],
            ["603005", "000672"],
        )
        self.assertEqual(
            result["exports"]["candidate_quality_scorecard_diagnostics"],
            {
                "candidate_count": 2,
                "scored_count": 2,
                "missing_quality_count": 0,
                "degraded": False,
                "source": "pk_decision",
            },
        )

    def test_candidate_quality_scorecard_node_keeps_empty_panel_visible(self):
        result = build_pk_decision_runtime(
            {
                "trade_gate_open": False,
                "position_level": "一档（空仓档）",
                "step0_prediction_cn": "退潮防守",
                "final_gate": {"can_new_entry": False},
                "has_personal_positions": False,
                "best_stock": None,
                "watch_anchor": None,
                "display_observation_candidates": [],
                "waiting_stocks": [],
            },
            {"label": "Step 5", "title": "PK决胜局（期望值模型）"},
            enabled_node_keys=["candidate_quality_scorecard", "export_stage_state"],
        )

        self.assertEqual(result["exports"]["candidate_quality_panel_fields"]["market_emotion_label"], "退潮防守")
        self.assertEqual(result["exports"]["candidate_quality_samples"], [])
        self.assertEqual(
            result["exports"]["candidate_quality_scorecard_diagnostics"],
            {
                "candidate_count": 0,
                "scored_count": 0,
                "missing_quality_count": 0,
                "degraded": True,
                "source": "pk_decision",
            },
        )

    def test_pk_decision_runtime_uses_crossline_fallback_watch_anchor(self):
        result = build_pk_decision_runtime(
            {
                "target_date": "2026-04-22",
                "run_mode": "replay",
                "final_gate": {"can_new_entry": False},
                "mainline_name": "军工",
                "market_research_snapshot": {"state_machine": {}},
                "executable_stocks": [],
                "waiting_stocks": [],
                "keep_group": [],
                "abnormal_watch_pool_all": [],
                "step2_bundle": {
                    "crossline_observation_stocks": [{"name": "跨线股", "code": "000009", "tmr_forecast": "只看承接"}],
                    "evaluated_stocks": [],
                    "gem_observation_stocks": [],
                },
                "conviction_codes": set(),
                "leader_memory_codes": set(),
                "build_strategy_ev_calibration": lambda target_date, ledger_mode=None: {"source": "ledger"},
                "score_execution_candidate": lambda stock, ev_calibration: {**stock, "score": 80},
                "score_candidate_decision_stack": lambda stock, **kwargs: {**stock, "decision_stack_score": 80},
                "sort_decision_stack_candidates": lambda candidates: list(candidates),
                "sort_watch_anchor_candidates": lambda candidates, **kwargs: list(candidates),
                "safe_float": lambda value, default=0.0: float(default if value in (None, "") else value),
                "get_trade_permission": lambda *args, **kwargs: {"permission_label": "跨线观察权", "permission_reason": "只观察"},
                "fetch_recent_price_bars": lambda *args, **kwargs: [],
                "evaluate_live_tradability": lambda *args, **kwargs: {"can_trade": True, "report_day_is_one_word": False},
                "analyze_buy_signal": lambda *args, **kwargs: None,
                "quant_system_available": False,
                "build_waiting_stock_plan": lambda seed, *args, **kwargs: dict(seed),
                "derive_watch_anchor_type": lambda candidate, mainline_name="": "重点观察谁",
                "derive_watch_anchor_note": lambda candidate, mainline_name="": "先看承接",
                "build_abnormal_watch_anchor_candidates": lambda **kwargs: [],
                "select_priority_watch_anchor": lambda **kwargs: ({}, ""),
            },
            {"label": "Step 5", "title": "PK决胜局（期望值模型）"},
            enabled_node_keys=["score_candidates", "observation_pool", "watch_anchor", "export_stage_state"],
        )

        self.assertEqual(result["exports"]["watch_anchor"]["code"], "000009")
        self.assertEqual(result["exports"]["watch_anchor_type"], "重点观察谁")

    def test_pk_decision_runtime_exports_probe_position_and_front_texts(self):
        candidate = {"name": "军工一号", "code": "000001"}
        result = build_pk_decision_runtime(
            {
                "target_date": "2026-04-22",
                "run_mode": "replay",
                "position_level": "三档（进攻档）",
                "position_reason": "环境允许参与",
                "display_mvp_mode": False,
                "high_board_count": 2,
                "final_gate": {"can_new_entry": True, "final_action": "只做唯一动作"},
                "mainline_name": "军工",
                "watchlist": [{"name": "军工一号", "code": "000001"}],
                "core_stocks": [{"name": "军工一号", "code": "000001"}],
                "abnormal_watch_pool": [],
                "abnormal_watch_pool_all": [],
                "market_research_bundle": {
                    "gem_breathing_candidates": [],
                    "filtered_out_gem_breathing_candidates": [],
                },
                "market_research_snapshot": {"state_machine": {}, "style_switch": {}},
                "focus_group": [candidate],
                "keep_group": [],
                "delete_group": [],
                "step2_bundle": {"crossline_observation_stocks": [], "evaluated_stocks": [], "gem_observation_stocks": []},
                "conviction_codes": set(),
                "leader_memory_codes": set(),
                "executable_stocks": [candidate],
                "waiting_stocks": [],
                "safe_float": lambda value, default=0.0: float(default if value in (None, "") else value),
                "build_strategy_ev_calibration": lambda target_date, ledger_mode=None: {"source": "ledger"},
                "score_execution_candidate": lambda stock, ev_calibration: {**stock, "score": 90},
                "score_candidate_decision_stack": lambda stock, **kwargs: {**stock, "decision_stack_score": 90},
                "sort_decision_stack_candidates": lambda candidates: list(candidates),
                "sort_watch_anchor_candidates": lambda candidates, **kwargs: list(candidates),
                "get_trade_permission": lambda *args, **kwargs: {"permission_label": "观察权", "permission_reason": "等待"},
                "fetch_recent_price_bars": lambda *args, **kwargs: [],
                "evaluate_live_tradability": lambda *args, **kwargs: {"can_trade": True, "report_day_is_one_word": False},
                "analyze_buy_signal": lambda *args, **kwargs: None,
                "quant_system_available": False,
                "build_waiting_stock_plan": lambda seed, *args, **kwargs: dict(seed),
                "derive_watch_anchor_type": lambda candidate, mainline_name="": "重点观察谁",
                "derive_watch_anchor_note": lambda candidate, mainline_name="": "先看承接",
                "build_abnormal_watch_anchor_candidates": lambda **kwargs: [],
                "select_priority_watch_anchor": lambda **kwargs: ({}, ""),
                "build_abnormal_probe_group": lambda *args, **kwargs: {"fallback_watch_anchor": {}},
                "build_special_probe_verdict": lambda **kwargs: {"probe_state": "", "summary_text": ""},
                "build_position_sizing_decision": lambda **kwargs: {
                    "target_position_pct": 50,
                    "candidate_feedback_ready": True,
                    "trigger_text": "完成60分钟确认",
                },
                "build_front_structure_layer_text": lambda **kwargs: "环境打开，只等唯一动作",
                "build_front_follow_action_text": lambda **kwargs: "只盯军工一号",
                "build_special_probe_focus_text": lambda **kwargs: "先看主线异动",
                "build_philosophy_constraint_text": lambda **kwargs: "只做主线核心",
                "render_core_mvp_digest": lambda *args, **kwargs: ["core-digest"],
                "render_mvp_focus_summary": lambda *args, **kwargs: ["focus-summary"],
                "get_execution_framework_text": lambda: "先60分钟确认，再看30分钟止损",
            },
            {"label": "Step 5", "title": "PK决胜局（期望值模型）"},
            enabled_node_keys=[
                "score_candidates",
                "watch_anchor",
                "probe_position",
                "front_texts",
                "export_stage_state",
            ],
        )

        self.assertEqual(result["exports"]["front_structure_layer_text"], "环境打开，只等唯一动作")
        self.assertEqual(result["exports"]["core_mvp_digest_lines"], ["core-digest"])
        self.assertEqual(result["exports"]["mvp_focus_summary_lines"], ["focus-summary"])
        self.assertEqual(result["exports"]["position_decision"]["target_position_pct"], 50)
        self.assertEqual(result["exports"]["best_stock"]["position_pct"], 50)
        self.assertEqual(result["exports"]["best_stock"]["candidate_feedback_ready"], True)

    def test_pk_decision_probe_position_passes_focus_keep_counts_to_position_sizing(self):
        captured = {}
        focus_candidate = {"name": "军工一号", "code": "000001"}
        keep_candidate = {"name": "军工二号", "code": "000002"}
        final_gate = {"can_new_entry": True}

        def _build_position_sizing_decision(**kwargs):
            captured["final_gate"] = dict(kwargs.get("final_gate") or {})
            return {
                "target_position_pct": 0,
                "candidate_feedback_ready": False,
                "trigger_text": "多候选观察",
            }

        result = build_pk_decision_runtime(
            {
                "target_date": "2026-04-22",
                "final_gate": final_gate,
                "mainline_name": "军工",
                "market_research_snapshot": {"state_machine": {}, "style_switch": {}},
                "focus_group": [focus_candidate],
                "keep_group": [keep_candidate],
                "abnormal_watch_pool_all": [],
                "best_stock": focus_candidate,
                "watch_anchor": keep_candidate,
                "watch_anchor_type": "重点观察谁",
                "safe_float": lambda value, default=0.0: float(default if value in (None, "") else value),
                "build_abnormal_probe_group": lambda *args, **kwargs: {"fallback_watch_anchor": {}},
                "build_special_probe_verdict": lambda **kwargs: {"probe_state": "", "summary_text": ""},
                "build_position_sizing_decision": _build_position_sizing_decision,
            },
            {"label": "Step 5", "title": "PK决胜局（期望值模型）"},
            enabled_node_keys=["probe_position", "export_stage_state"],
        )

        self.assertEqual(result["exports"]["position_decision"]["trigger_text"], "多候选观察")
        self.assertEqual(captured["final_gate"]["candidate_count"], 2)
        self.assertEqual(captured["final_gate"]["unique_target_count"], 2)
        self.assertNotIn("candidate_count", final_gate)
        self.assertNotIn("unique_target_count", final_gate)

    def test_pk_decision_probe_position_passes_monthly_context_to_position_sizing(self):
        captured = {}

        def _build_position_sizing_decision(**kwargs):
            captured["monthly_context"] = kwargs.get("monthly_context")
            return {
                "target_position_pct": 0,
                "candidate_feedback_ready": False,
                "trigger_text": "月度节奏观察",
            }

        result = build_pk_decision_runtime(
            {
                "target_date": "2026-05-13",
                "final_gate": {"can_new_entry": True},
                "mainline_name": "电力",
                "market_research_snapshot": {"state_machine": {}, "style_switch": {}},
                "focus_group": [],
                "keep_group": [],
                "abnormal_watch_pool_all": [],
                "best_stock": {"name": "电力一号", "code": "000001"},
                "watch_anchor": None,
                "watch_anchor_type": "",
                "monthly_context": {"month_mode": "ordinary_attack", "month_return_pct": 3.5},
                "safe_float": lambda value, default=0.0: float(default if value in (None, "") else value),
                "build_abnormal_probe_group": lambda *args, **kwargs: {"fallback_watch_anchor": {}},
                "build_special_probe_verdict": lambda **kwargs: {"probe_state": "", "summary_text": ""},
                "build_position_sizing_decision": _build_position_sizing_decision,
            },
            {"label": "Step 5", "title": "PK决胜局（期望值模型）"},
            enabled_node_keys=["probe_position", "export_stage_state"],
        )

        self.assertEqual(result["exports"]["position_decision"]["trigger_text"], "月度节奏观察")
        self.assertEqual(captured["monthly_context"]["month_mode"], "ordinary_attack")
        self.assertEqual(captured["monthly_context"]["month_return_pct"], 3.5)

    def test_pk_decision_probe_position_deduplicates_same_code_with_partial_metadata(self):
        captured = {}

        def _build_position_sizing_decision(**kwargs):
            captured["final_gate"] = dict(kwargs.get("final_gate") or {})
            return {
                "target_position_pct": 0,
                "candidate_feedback_ready": False,
                "trigger_text": "同一代码观察",
            }

        build_pk_decision_runtime(
            {
                "target_date": "2026-04-22",
                "final_gate": {"can_new_entry": True},
                "mainline_name": "军工",
                "market_research_snapshot": {"state_machine": {}, "style_switch": {}},
                "focus_group": [{"name": "军工一号", "code": "000001"}],
                "keep_group": [{"name": "军工一号", "code": "000001", "sector": "军工", "direction": "低空经济"}],
                "abnormal_watch_pool_all": [],
                "best_stock": {"name": "军工一号", "code": "000001"},
                "watch_anchor": None,
                "watch_anchor_type": "重点观察谁",
                "safe_float": lambda value, default=0.0: float(default if value in (None, "") else value),
                "build_abnormal_probe_group": lambda *args, **kwargs: {"fallback_watch_anchor": {}},
                "build_special_probe_verdict": lambda **kwargs: {"probe_state": "", "summary_text": ""},
                "build_position_sizing_decision": _build_position_sizing_decision,
            },
            {"label": "Step 5", "title": "PK决胜局（期望值模型）"},
            enabled_node_keys=["probe_position", "export_stage_state"],
        )

        self.assertEqual(captured["final_gate"]["candidate_count"], 2)
        self.assertEqual(captured["final_gate"]["unique_target_count"], 1)

    def test_pk_decision_runtime_builds_pk_and_action_plan_contexts_for_renderers(self):
        captured = {}

        def render_pk(context):
            captured["pk"] = dict(context)
            return ["pk"]

        def render_action(context):
            captured["action"] = dict(context)
            return ["action"]

        result = build_pk_decision_runtime(
            {
                "render_pk_decision_section": render_pk,
                "render_action_plan_section": render_action,
            },
            {"label": "Step 5", "title": "PK决胜局（期望值模型）"},
            enabled_node_keys=["pk_context", "action_plan_context", "render_sections"],
        )

        self.assertEqual(result["lines"], ["pk", "action", ""])
        self.assertIn("conclusion_lines", captured["pk"])
        self.assertIn("action_rows", captured["action"])
        self.assertIn("position_section_lines", captured["action"])

    def test_action_plan_context_maps_legacy_defense_position_to_zero_or_50_model(self):
        result = build_pk_decision_action_plan_context_node(
            {
                "trade_gate_open": False,
                "position_level": "二档（防守档）",
                "step0_prediction": "NEUTRAL",
                "step0_prediction_cn": "中性",
                "final_gate": {"can_new_entry": False, "allow_attack_50_ready": True, "should_reduce": False},
                "has_personal_positions": False,
                "display_observation_candidates": [],
                "waiting_stocks": [],
                "today_predictions": [],
                "nextday_predictions": [],
                "get_execution_framework_text": lambda: "竞价表态 -> 参与窗口 -> 60分钟确认 -> 30分钟止损",
            }
        )

        exports = result["exports"]
        rendered = "\n".join(exports["position_section_lines"] + exports["first_hour_lines"] + exports["intraday_lines"])
        self.assertIn("0%观察", rendered)
        self.assertIn("50%标准进攻", rendered)
        self.assertIn("固定交易窗口条件", rendered)
        self.assertNotIn("禁止新开仓", rendered)
        self.assertNotIn(_m("最多", "30%"), rendered)
        self.assertNotIn(_m("30%", "条件试错"), rendered)
        self.assertNotIn("二档（防守档）", rendered)

    def test_action_plan_context_zero_position_uses_participation_wording(self):
        result = build_pk_decision_action_plan_context_node(
            {
                "trade_gate_open": False,
                "position_level": "一档（空仓档）",
                "step0_prediction": "DIFFICULT",
                "step0_prediction_cn": "暂不跟随",
                "final_gate": {"can_new_entry": False, "allow_attack_50_ready": False, "should_reduce": False},
                "has_personal_positions": False,
                "display_observation_candidates": [],
                "waiting_stocks": [],
                "today_predictions": [],
                "nextday_predictions": [],
                "get_execution_framework_text": lambda: "最终0%时只观察",
            }
        )

        rendered = "\n".join(result["exports"]["position_section_lines"])
        self.assertIn("不新增参与", rendered)
        self.assertNotIn("禁止任何买入", rendered)

    def test_action_plan_context_keeps_conviction_candidates_executable_after_ten_confirm(self):
        result = build_pk_decision_action_plan_context_node(
            {
                "trade_gate_open": False,
                "position_level": "一档（空仓档）",
                "step0_prediction": "NEUTRAL",
                "step0_prediction_cn": "0%观察",
                "final_gate": {"can_new_entry": False, "allow_attack_50_ready": False, "should_reduce": False},
                "has_personal_positions": False,
                "display_observation_candidates": [
                    {
                        "name": "利仁科技",
                        "code": "001259",
                        "permission_label": "极看观察权",
                        "watch_anchor_type": "极度看好先看谁",
                        "minute_plan": {"confirm_price_60m": 60.50},
                        "stop_plan": {"effective_stop": 57.47},
                        "conviction_reason": "板块锚定龙 / 首波先锋",
                    }
                ],
                "waiting_stocks": [],
                "today_predictions": [],
                "nextday_predictions": [],
                "get_execution_framework_text": lambda: "竞价表态 -> 参与窗口 -> 60分钟确认 -> 30分钟止损",
                "build_trade_price_focus": lambda minute_plan, stop_plan: {
                    "key_zone_display": "关键位/带57.47",
                    "invalid_line_display": "观察失效位57.47",
                },
                "build_observation_price_focus_text": lambda price_focus: price_focus.get("key_zone_display", "-"),
                "compose_observation_focus_text": lambda confirm_text, focus_text: f"10点确认价{confirm_text} / {focus_text}",
            }
        )

        exports = result["exports"]
        action_text = "\n".join(
            " | ".join(str(row.get(key, "")) for key in ("action", "name", "code", "trigger", "risk_window"))
            for row in exports["action_rows"]
        )
        rendered = "\n".join(
            [action_text]
            + exports["position_section_lines"]
            + exports["observation_priority_lines"]
            + exports["first_hour_lines"]
            + exports["intraday_lines"]
        )
        self.assertIn("极度看好", rendered)
        self.assertIn("09:50-10:10观察价60.50", rendered)
        self.assertIn("固定交易窗口内条件成立后才评估50%标准进攻", rendered)
        self.assertIn("命中后才评估50%标准进攻", rendered)
        self.assertNotIn("明天没有可买对象", rendered)
        self.assertNotIn("必须空仓", rendered)

    def test_action_plan_context_exports_candidate_quality_inputs_from_daily_candidates(self):
        result = build_pk_decision_action_plan_context_node(
            {
                "trade_gate_open": False,
                "position_level": "二档（防守档）",
                "step0_prediction": "NEUTRAL",
                "step0_prediction_cn": "0%观察",
                "final_gate": {"can_new_entry": False, "allow_attack_50_ready": True, "should_reduce": False},
                "has_personal_positions": True,
                "best_stock": {"name": "晶方科技", "code": "603005"},
                "watch_anchor": {"name": "上峰水泥", "code": "000672"},
                "display_observation_candidates": [
                    {
                        "name": "晶方科技",
                        "code": "603005",
                        "selection_quality": "高",
                        "entry_cost_state": "高成本",
                        "is_core": True,
                        "cost_flags": ["远离MA/VWAP"],
                    }
                ],
                "waiting_stocks": [
                    {
                        "name": "上峰水泥",
                        "code": "000672",
                        "selection_quality": "中",
                        "entry_cost_state": "确认中",
                        "current_position_shares": 400,
                        "sellable_shares": 300,
                        "locked_shares": 100,
                        "trend_context": "冲高后回踩MA/VWAP",
                    }
                ],
                "today_predictions": [],
                "nextday_predictions": [],
                "get_execution_framework_text": lambda: "竞价表态 -> 参与窗口 -> 60分钟确认 -> 30分钟止损",
            }
        )

        exports = result["exports"]
        self.assertEqual(exports["candidate_quality_panel_fields"]["market_emotion_label"], "0%观察")
        self.assertEqual(exports["candidate_quality_panel_fields"]["account_attention_load"], "有持仓需先处理")
        self.assertEqual(exports["candidate_quality_panel_fields"]["daily_new_entry_limit"], 0)
        self.assertEqual(exports["candidate_quality_panel_fields"]["primary_buy_candidate"]["code"], "603005")
        self.assertEqual(exports["candidate_quality_panel_fields"]["backup_candidate"]["code"], "000672")
        self.assertIn("亏损后补仓", exports["candidate_quality_panel_fields"]["forbidden_actions"])
        self.assertEqual(
            [sample["code"] for sample in exports["candidate_quality_samples"]],
            ["603005", "000672"],
        )

    def test_action_plan_context_clears_backup_candidate_when_same_as_primary(self):
        result = build_pk_decision_action_plan_context_node(
            {
                "trade_gate_open": True,
                "position_level": "三档（进攻档）",
                "step0_prediction": "GOOD",
                "step0_prediction_cn": "进攻观察",
                "final_gate": {"can_new_entry": True, "should_reduce": False},
                "has_personal_positions": False,
                "best_stock": {"name": "晶方科技", "code": "603005"},
                "watch_anchor": {"name": "晶方科技", "code": "603005"},
                "display_observation_candidates": [],
                "waiting_stocks": [],
                "today_predictions": [],
                "nextday_predictions": [],
                "get_execution_framework_text": lambda: "竞价表态 -> 参与窗口 -> 60分钟确认 -> 30分钟止损",
            }
        )

        panel_fields = result["exports"]["candidate_quality_panel_fields"]
        self.assertEqual(panel_fields["primary_buy_candidate"]["code"], "603005")
        self.assertIsNone(panel_fields["backup_candidate"])

    def test_action_plan_context_marks_primary_candidate_quality_defaults_without_overwriting_explicit_fields(self):
        result = build_pk_decision_action_plan_context_node(
            {
                "trade_gate_open": True,
                "position_level": "三档（进攻档）",
                "step0_prediction": "GOOD",
                "step0_prediction_cn": "进攻观察",
                "final_gate": {"can_new_entry": True, "should_reduce": False},
                "has_personal_positions": False,
                "best_stock": {"name": "主线核心", "code": "000001"},
                "watch_anchor": {"name": "补位观察", "code": "000002"},
                "display_observation_candidates": [
                    {
                        "name": "主线核心",
                        "code": "000001",
                        "selection_quality": "低",
                        "entry_cost_state": "低成本",
                    }
                ],
                "waiting_stocks": [],
                "today_predictions": [],
                "nextday_predictions": [],
                "get_execution_framework_text": lambda: "竞价表态 -> 参与窗口 -> 60分钟确认 -> 30分钟止损",
            }
        )

        samples = {sample["code"]: sample for sample in result["exports"]["candidate_quality_samples"]}
        self.assertEqual(samples["000001"]["selection_quality"], "高")
        self.assertEqual(samples["000001"]["entry_cost_state"], "确认中")
        self.assertEqual(samples["000001"]["is_core"], True)
        self.assertEqual(samples["000001"]["quality_role"], "主买对象")
        self.assertEqual(samples["000002"]["selection_quality"], "中")
        self.assertEqual(samples["000002"]["entry_cost_state"], "确认中")
        self.assertEqual(samples["000002"]["quality_role"], "补位对象")

    def test_action_plan_context_merges_role_defaults_with_richer_same_code_sample_fields(self):
        result = build_pk_decision_action_plan_context_node(
            {
                "trade_gate_open": True,
                "position_level": "三档（进攻档）",
                "step0_prediction": "GOOD",
                "step0_prediction_cn": "进攻观察",
                "final_gate": {"can_new_entry": True, "should_reduce": False},
                "has_personal_positions": False,
                "best_stock": {"name": "主线核心", "code": "000001"},
                "watch_anchor": None,
                "display_observation_candidates": [
                    {
                        "name": "主线核心",
                        "code": "000001",
                        "risk_flags": ["风险信息缺失"],
                        "cost_flags": ["远离MA/VWAP"],
                        "current_position_shares": 100,
                        "sellable_shares": 0,
                        "locked_shares": 100,
                    }
                ],
                "waiting_stocks": [],
                "today_predictions": [],
                "nextday_predictions": [],
                "get_execution_framework_text": lambda: "竞价表态 -> 参与窗口 -> 60分钟确认 -> 30分钟止损",
            }
        )

        samples = result["exports"]["candidate_quality_samples"]
        self.assertEqual(len([sample for sample in samples if sample["code"] == "000001"]), 1)
        sample = samples[0]
        self.assertEqual(sample["selection_quality"], "高")
        self.assertEqual(sample["entry_cost_state"], "确认中")
        self.assertEqual(sample["quality_role"], "主买对象")
        self.assertEqual(sample["risk_flags"], ["风险信息缺失"])
        self.assertEqual(sample["cost_flags"], ["远离MA/VWAP"])
        self.assertEqual(sample["current_position_shares"], 100)
        self.assertEqual(sample["locked_shares"], 100)

    def test_action_plan_context_merges_risk_and_cost_lists_for_same_code_samples(self):
        result = build_pk_decision_action_plan_context_node(
            {
                "trade_gate_open": True,
                "position_level": "三档（进攻档）",
                "step0_prediction": "GOOD",
                "step0_prediction_cn": "进攻观察",
                "final_gate": {"can_new_entry": True, "should_reduce": False},
                "has_personal_positions": False,
                "best_stock": {
                    "name": "主线核心",
                    "code": "000001",
                    "risk_flags": ["公告待确认"],
                    "cost_flags": ["靠近VWAP"],
                },
                "watch_anchor": None,
                "display_observation_candidates": [
                    {
                        "name": "主线核心",
                        "code": "000001",
                        "risk_flags": ["风险信息缺失", "公告待确认"],
                        "cost_flags": ["远离MA/VWAP", "靠近VWAP"],
                    }
                ],
                "waiting_stocks": [],
                "today_predictions": [],
                "nextday_predictions": [],
                "get_execution_framework_text": lambda: "竞价表态 -> 参与窗口 -> 60分钟确认 -> 30分钟止损",
            }
        )

        sample = result["exports"]["candidate_quality_samples"][0]
        self.assertEqual(sample["risk_flags"], ["公告待确认", "风险信息缺失"])
        self.assertEqual(sample["cost_flags"], ["靠近VWAP", "远离MA/VWAP"])

    def test_action_plan_context_keeps_explicit_high_cost_when_merging_primary_defaults(self):
        result = build_pk_decision_action_plan_context_node(
            {
                "trade_gate_open": True,
                "position_level": "三档（进攻档）",
                "step0_prediction": "GOOD",
                "step0_prediction_cn": "进攻观察",
                "final_gate": {"can_new_entry": True, "should_reduce": False},
                "has_personal_positions": False,
                "best_stock": {"name": "主线核心", "code": "000001"},
                "watch_anchor": None,
                "display_observation_candidates": [
                    {
                        "name": "主线核心",
                        "code": "000001",
                        "entry_cost_state": "高成本",
                        "cost_flags": ["远离MA/VWAP"],
                    }
                ],
                "waiting_stocks": [],
                "today_predictions": [],
                "nextday_predictions": [],
                "get_execution_framework_text": lambda: "竞价表态 -> 参与窗口 -> 60分钟确认 -> 30分钟止损",
            }
        )

        sample = result["exports"]["candidate_quality_samples"][0]
        self.assertEqual(sample["quality_role"], "主买对象")
        self.assertEqual(sample["selection_quality"], "高")
        self.assertEqual(sample["entry_cost_state"], "高成本")
        self.assertEqual(sample["cost_flags"], ["远离MA/VWAP"])

    def test_action_plan_context_does_not_overwrite_primary_own_high_cost_default(self):
        result = build_pk_decision_action_plan_context_node(
            {
                "trade_gate_open": True,
                "position_level": "三档（进攻档）",
                "step0_prediction": "GOOD",
                "step0_prediction_cn": "进攻观察",
                "final_gate": {"can_new_entry": True, "should_reduce": False},
                "has_personal_positions": False,
                "best_stock": {
                    "name": "主线核心",
                    "code": "000001",
                    "entry_cost_state": "高成本",
                    "cost_flags": ["远离MA/VWAP"],
                },
                "watch_anchor": None,
                "display_observation_candidates": [],
                "waiting_stocks": [],
                "today_predictions": [],
                "nextday_predictions": [],
                "get_execution_framework_text": lambda: "竞价表态 -> 参与窗口 -> 60分钟确认 -> 30分钟止损",
            }
        )

        sample = result["exports"]["candidate_quality_samples"][0]
        self.assertEqual(sample["quality_role"], "主买对象")
        self.assertEqual(sample["selection_quality"], "高")
        self.assertEqual(sample["entry_cost_state"], "高成本")
        self.assertEqual(sample["cost_flags"], ["远离MA/VWAP"])

    def test_action_plan_context_reuses_candidate_quality_scorecard_payload_when_present(self):
        result = build_pk_decision_action_plan_context_node(
            {
                "trade_gate_open": False,
                "position_level": "二档（防守档）",
                "step0_prediction": "NEUTRAL",
                "step0_prediction_cn": "0%观察",
                "final_gate": {"can_new_entry": False, "should_reduce": False},
                "has_personal_positions": False,
                "best_stock": {"name": "原始主对象", "code": "000001"},
                "watch_anchor": None,
                "display_observation_candidates": [],
                "waiting_stocks": [],
                "today_predictions": [],
                "nextday_predictions": [],
                "candidate_quality_panel_fields": {
                    "market_emotion_label": "替换节点输出",
                    "daily_new_entry_limit": 0,
                    "primary_buy_candidate": {"name": "替换对象", "code": "999999"},
                    "backup_candidate": None,
                },
                "candidate_quality_samples": [
                    {
                        "name": "替换对象",
                        "code": "999999",
                        "selection_quality": "高",
                        "entry_cost_state": "确认中",
                    }
                ],
                "candidate_quality_scorecard_diagnostics": {
                    "candidate_count": 1,
                    "scored_count": 1,
                    "missing_quality_count": 0,
                    "degraded": False,
                    "source": "replacement",
                },
                "get_execution_framework_text": lambda: "竞价表态 -> 固定交易窗口条件 -> 30分钟止损",
            }
        )

        self.assertEqual(result["exports"]["candidate_quality_panel_fields"]["market_emotion_label"], "替换节点输出")
        self.assertEqual(result["exports"]["candidate_quality_panel_fields"]["primary_buy_candidate"]["code"], "999999")
        self.assertEqual(result["exports"]["candidate_quality_samples"][0]["code"], "999999")
        self.assertEqual(result["exports"]["candidate_quality_scorecard_diagnostics"]["source"], "replacement")

    def test_action_plan_context_node_exports_stable_payload_and_diagnostics(self):
        result = build_pk_decision_runtime(
            {
                "trade_gate_open": False,
                "position_level": "二档（防守档）",
                "step0_prediction": "NEUTRAL",
                "step0_prediction_cn": "0%观察",
                "final_gate": {"can_new_entry": False, "allow_attack_50_ready": True},
                "has_personal_positions": True,
                "best_stock": None,
                "watch_anchor": {
                    "name": "观察锚点",
                    "code": "000001",
                    "minute_plan": {"confirm_price_60m": 10.5},
                },
                "watch_anchor_type": "重点观察谁",
                "display_observation_candidates": [
                    {
                        "name": "观察锚点",
                        "code": "000001",
                        "permission_label": "重点观察权",
                        "minute_plan": {"confirm_price_60m": 10.5},
                    }
                ],
                "waiting_stocks": [{"name": "备选股", "code": "000002"}],
                "today_predictions": [],
                "nextday_predictions": [],
                "build_trade_price_focus": lambda minute_plan, stop_plan: {
                    "compact_text": "盯10.50",
                    "key_zone_display": "10.50",
                },
                "build_observation_price_focus_text": lambda price_focus: price_focus.get("compact_text", "-"),
                "compose_observation_focus_text": lambda confirm_text, focus_text: f"{confirm_text} / {focus_text}",
                "build_candidate_exit_rules": lambda candidate, stop_plan=None: {
                    "holding_days_min": 1,
                    "holding_days_max": 3,
                },
                "format_holding_window_text": lambda min_days, max_days: f"{min_days}-{max_days}天",
                "get_execution_framework_text": lambda: "竞价表态 -> 参与窗口 -> 60分钟确认 -> 30分钟止损",
            },
            {"label": "Step 5", "title": "PK决胜局（期望值模型）"},
            enabled_node_keys=["action_plan_context", "export_stage_state"],
        )

        diagnostics = result["exports"]["action_plan_context_diagnostics"]
        self.assertEqual(diagnostics["source"], "pk_decision")
        self.assertEqual(diagnostics["action_row_count"], 1)
        self.assertEqual(diagnostics["observation_priority_count"], 1)
        self.assertEqual(diagnostics["backup_observation_count"], 1)
        self.assertEqual(diagnostics["alert_count"], 0)
        self.assertEqual(diagnostics["daily_new_entry_limit"], 0)
        self.assertTrue(diagnostics["has_watch_anchor"])
        self.assertFalse(diagnostics["has_best_stock"])

    def test_action_plan_context_reuses_replacement_payload_when_present(self):
        replacement_payload = {
            "action_rows": [{"action": "替换动作", "name": "替换对象", "code": "999999"}],
            "observation_priority_lines": ["替换观察"],
            "backup_observation_lines": [],
            "position_section_lines": ["替换仓位"],
            "pre_market_lines": ["替换盘前"],
            "opening_lines": ["替换开盘"],
            "first_hour_lines": ["替换首小时"],
            "intraday_lines": ["替换盘中"],
            "closing_lines": ["替换尾盘"],
            "alert_rows": [],
            "action_plan_context_diagnostics": {
                "source": "replacement",
                "action_row_count": 1,
                "observation_priority_count": 1,
                "backup_observation_count": 0,
                "alert_count": 0,
                "daily_new_entry_limit": 0,
                "has_best_stock": False,
                "has_watch_anchor": True,
                "degraded": False,
            },
        }

        result = build_pk_decision_action_plan_context_node(
            {
                "trade_gate_open": True,
                "position_level": "三档（进攻档）",
                "step0_prediction": "GOOD",
                "step0_prediction_cn": "进攻观察",
                "final_gate": {"can_new_entry": True},
                "best_stock": {"name": "原始对象", "code": "000001"},
                "watch_anchor": None,
                "display_observation_candidates": [],
                "waiting_stocks": [],
                "today_predictions": [],
                "nextday_predictions": [],
                "action_plan_context_payload": replacement_payload,
            }
        )

        self.assertEqual(result["exports"]["action_rows"][0]["code"], "999999")
        self.assertEqual(result["exports"]["position_section_lines"], ["替换仓位"])
        self.assertEqual(result["exports"]["action_plan_context_diagnostics"]["source"], "replacement")

    def test_render_sections_passes_candidate_quality_inputs_to_action_plan_renderer(self):
        captured = {}

        def render_action(context):
            captured.update(context)
            return ["action"]

        result = build_pk_decision_runtime(
            {
                "render_pk_decision_section": lambda context: ["pk"],
                "render_action_plan_section": render_action,
                "candidate_quality_panel_fields": {
                    "market_emotion_label": "0%观察",
                    "daily_new_entry_limit": 0,
                },
                "candidate_quality_samples": [{"name": "晶方科技", "code": "603005"}],
            },
            {"label": "Step 5", "title": "PK决胜局（期望值模型）"},
            enabled_node_keys=["render_sections"],
        )

        self.assertEqual(result["lines"], ["pk", "action", ""])
        self.assertIn("candidate_quality_panel_fields", captured)
        self.assertIn("candidate_quality_samples", captured)
        self.assertEqual(captured["render_candidate_trace_tables"], True)

    def test_render_sections_passes_action_plan_enabled_nodes_for_candidate_quality(self):
        captured = {}

        def render_action(context):
            captured.update(context)
            return ["action"]

        build_pk_decision_runtime(
            {
                "render_pk_decision_section": lambda context: ["pk"],
                "render_action_plan_section": render_action,
                "action_plan_enabled_node_keys": ["overview", "candidate_quality"],
            },
            {"label": "Step 5", "title": "PK决胜局（期望值模型）"},
            enabled_node_keys=["render_sections"],
        )

        self.assertEqual(captured["enabled_node_keys"], ["overview", "candidate_quality"])

    def test_runtime_can_render_candidate_quality_markdown_when_enabled(self):
        result = build_pk_decision_runtime(
            {
                "render_pk_decision_section": lambda context: ["pk"],
                "render_action_plan_section": render_action_plan_section,
                "action_plan_enabled_node_keys": ["overview", "candidate_quality"],
                "candidate_quality_panel_fields": {
                    "market_emotion_label": "0%观察",
                    "account_attention_load": "中",
                    "holding_priority_action": "先处理旧仓，再看新增",
                    "daily_new_entry_limit": 0,
                    "primary_buy_candidate": {"name": "晶方科技", "code": "603005"},
                },
                "candidate_quality_samples": [
                    {
                        "name": "晶方科技",
                        "code": "603005",
                        "selection_quality": "高",
                        "entry_cost_state": "高成本",
                        "is_core": True,
                        "cost_flags": ["远离MA/VWAP"],
                    }
                ],
            },
            {"label": "Step 5", "title": "PK决胜局（期望值模型）"},
            enabled_node_keys=["render_sections"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("#### 明日操作计划", rendered)
        self.assertIn("##### 候选质量与动作分层", rendered)
        self.assertNotIn("\n## 候选质量与动作分层", rendered)
        self.assertIn("| 主买对象 | 晶方科技(603005) |", rendered)
        self.assertIn("| 晶方科技(603005) | 实际可买 |  |  | 0 | 0 | 高 | 不舒服 | 核心观察 |", rendered)
        self.assertIn("- 成本项：远离MA/VWAP", rendered)

    def test_runtime_renders_and_exports_candidate_selection_traces(self):
        result = build_pk_decision_runtime(
            {
                "render_pk_decision_section": lambda context: ["pk"],
                "render_action_plan_result": render_action_plan_result,
                "render_action_plan_section": render_action_plan_section,
                "action_plan_enabled_node_keys": ["overview", "candidate_quality"],
                "candidate_quality_panel_fields": {
                    "market_emotion_label": "主线活跃",
                    "daily_new_entry_limit": 1,
                },
                "candidate_quality_samples": [
                    {
                        "name": "华天科技",
                        "code": "002185",
                        "tier": "T0",
                        "source_pools": ["主线核心候选"],
                        "mainline": "半导体",
                        "sector": "半导体",
                        "market_fit": "部分满足",
                        "mainline_fit": "满足",
                        "stock_structure_fit": "部分满足",
                        "latest_price": 13.2,
                        "available_cash": 10000,
                        "final_action": "09:50-10:10确认，不满足继续不参与",
                    }
                ],
                "candidate_trace_eliminated_items": [
                    {"name": "大众公用", "reason": "主线不匹配"},
                ],
            },
            {"label": "Step 5", "title": "PK决胜局（期望值模型）"},
            enabled_node_keys=["render_sections", "export_stage_state"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("候选选股轨迹", rendered)
        self.assertIn("未进入分层原因统计", rendered)
        self.assertEqual(result["exports"]["candidate_traces"][0]["stock_code"], "002185")
        self.assertEqual(result["exports"]["candidate_trace_eliminated_summary"][0]["reason"], "主线不匹配")

    def test_runtime_does_not_render_primary_buy_when_daily_new_entry_limit_is_zero(self):
        result = build_pk_decision_runtime(
            {
                "render_pk_decision_section": lambda context: ["pk"],
                "render_action_plan_section": render_action_plan_section,
                "action_plan_enabled_node_keys": ["overview", "candidate_quality"],
                "trade_gate_open": False,
                "position_level": "一档（空仓档）",
                "step0_prediction": "NEUTRAL",
                "step0_prediction_cn": "0%观察",
                "final_gate": {"can_new_entry": False, "allow_attack_50_ready": False},
                "best_stock": {"name": "晶方科技", "code": "603005"},
                "watch_anchor": None,
                "display_observation_candidates": [],
                "waiting_stocks": [],
                "today_predictions": [],
                "nextday_predictions": [],
                "get_execution_framework_text": lambda: "竞价表态 -> 参与窗口 -> 60分钟确认 -> 30分钟止损",
            },
            {"label": "Step 5", "title": "PK决胜局（期望值模型）"},
            enabled_node_keys=["action_plan_context", "render_sections"],
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("| 今日新增上限 | 0 |", rendered)
        self.assertIn("| 主买对象 | 晶方科技(603005) |", rendered)
        self.assertIn("| 晶方科技(603005) | 实际可买 |  |  | 0 | 0 | 高 | 等确认 | 核心观察 |", rendered)
        self.assertNotIn("| 晶方科技(603005) | 实际可买 |  |  | 0 | 0 | 高 | 等确认 | 主买 |", rendered)

    def test_pk_context_keeps_conviction_candidates_executable_after_ten_confirm(self):
        conviction_watch = {
            "name": "利仁科技",
            "code": "001259",
            "permission_label": "极看观察权",
            "watch_anchor_type": "极度看好先看谁",
            "minute_plan": {"confirm_price_60m": 60.50},
            "stop_plan": {"effective_stop": 57.47},
            "conviction_reason": "板块锚定龙 / 首波先锋",
            "reason": "主线核心先看承接",
        }

        result = build_pk_decision_pk_context_node(
            {
                "trade_gate_open": False,
                "display_observation_candidates": [conviction_watch],
                "best_stock": None,
                "watch_anchor": conviction_watch,
                "watch_anchor_type": "极度看好先看谁",
                "position_level": "一档（空仓档）",
                "final_gate": {"can_new_entry": False, "allow_attack_50_ready": False},
                "front_structure_layer_text": "盘前0%观察",
                "build_trade_price_focus": lambda minute_plan, stop_plan: {
                    "compact_text": "盯60.50",
                    "key_zone_display": "60.50/57.47",
                    "note_text": "确认价60.50",
                },
                "build_observation_price_focus_text": lambda price_focus: price_focus.get("compact_text", "-"),
                "should_surface_price_note": lambda price_focus: False,
                "compose_observation_focus_text": lambda confirm_text, focus_text: f"{confirm_text} / {focus_text}",
            }
        )

        rendered = "\n".join(result["exports"]["conclusion_lines"])
        self.assertIn("盘前不抢跑", rendered)
        self.assertIn("09:50-10:10", rendered)
        self.assertIn("50%标准进攻", rendered)
        self.assertNotIn("明天没有可买对象", rendered)
        self.assertNotIn("当前先不买", rendered)

    def test_pk_decision_stage_renders_dynamic_heading_and_exports_best_stock(self):
        stage_lookup = build_execution_stage_lookup(
            [
                {"stage_key": "environment_follow", "title": "明日环境与跟随裁决"},
                {"stage_key": "watch_pool", "title": "明天观察池"},
                {"stage_key": "candidate_selection", "title": "明日核心标的"},
                {"stage_key": "risk_review", "title": "明日风险预判"},
                {"stage_key": "entry_plan", "title": "明日买点预计算"},
                {"stage_key": "pk_decision", "title": "PK决胜局（期望值模型）"},
            ]
        )

        candidate = {
            "name": "军工一号",
            "code": "000001",
            "signal": types.SimpleNamespace(signal_type="sweet_zone", entry_price=10.0, stop_loss=9.5, position_pct=50),
            "entry_range": (9.7, 10.3),
            "minute_plan": {"confirm_price_60m": 10.5},
            "stop_plan": {"summary": "预估9.50", "note_text": "看9.50"},
            "position_pct": 50,
            "ev_model_source": "历史账本",
            "permission_label": "交易资格",
            "reason": "主线最强",
        }

        result = build_pk_decision_stage(
            {
                "target_date": "2026-04-22",
                "run_mode": "replay",
                "position_level": "三档（进攻档）",
                "position_reason": "环境允许参与",
                "step0_prediction": "CLEAR",
                "step0_prediction_cn": "🟢 明朗",
                "step0_action": "允许强势跟随",
                "display_mvp_mode": False,
                "high_board_count": 2,
                "has_personal_positions": False,
                "final_gate": {"can_new_entry": True, "final_action": "只做唯一动作"},
                "mainline_name": "军工",
                "watchlist": [{"name": "军工一号", "code": "000001"}],
                "core_stocks": [{"name": "军工一号", "code": "000001"}],
                "secondary_stocks": [],
                "abnormal_watch_pool": [],
                "abnormal_watch_pool_all": [],
                "market_research_bundle": {
                    "gem_breathing_candidates": [],
                    "filtered_out_gem_breathing_candidates": [],
                },
                "market_research_snapshot": {"state_machine": {"leading_line": "军工"}, "style_switch": {}},
                "focus_group": [candidate],
                "keep_group": [],
                "delete_group": [],
                "step2_bundle": {"crossline_observation_stocks": [], "evaluated_stocks": [], "gem_observation_stocks": []},
                "conviction_codes": {"000001"},
                "leader_memory_codes": set(),
                "executable_stocks": [candidate],
                "waiting_stocks": [],
                "safe_float": lambda value, default=0.0: float(default if value in (None, "") else value),
                "build_strategy_ev_calibration": lambda target_date, ledger_mode=None: {"source": "ledger"},
                "score_execution_candidate": lambda stock, ev_calibration: {**stock, "score": 99},
                "score_candidate_decision_stack": lambda stock, **kwargs: {**stock, "decision_stack_score": 99},
                "sort_decision_stack_candidates": lambda candidates: list(candidates),
                "sort_watch_anchor_candidates": lambda candidates, **kwargs: list(candidates),
                "get_trade_permission": lambda *args, **kwargs: {"permission_label": "观察权", "permission_reason": "等待", "can_execute": False},
                "fetch_recent_price_bars": lambda *args, **kwargs: [],
                "evaluate_live_tradability": lambda *args, **kwargs: {"can_trade": True, "report_day_is_one_word": False},
                "analyze_buy_signal": lambda *args, **kwargs: None,
                "quant_system_available": False,
                "build_waiting_stock_plan": lambda *args, **kwargs: {"name": "观察股", "code": "000002"},
                "derive_watch_anchor_type": lambda candidate, mainline_name="": "重点观察谁",
                "derive_watch_anchor_note": lambda candidate, mainline_name="": "先看承接",
                "build_abnormal_watch_anchor_candidates": lambda **kwargs: [],
                "select_priority_watch_anchor": lambda **kwargs: ({}, ""),
                "build_abnormal_probe_group": lambda *args, **kwargs: {"fallback_watch_anchor": {}},
                "build_special_probe_verdict": lambda **kwargs: {"probe_state": "", "summary_text": ""},
                "build_position_sizing_decision": lambda **kwargs: {"target_position_pct": 50, "candidate_feedback_ready": True, "trigger_text": "完成60分钟确认"},
                "build_front_structure_layer_text": lambda **kwargs: "环境打开，只等唯一动作",
                "build_front_follow_action_text": lambda **kwargs: "只盯军工一号",
                "build_special_probe_focus_text": lambda **kwargs: "先看主线异动",
                "build_philosophy_constraint_text": lambda **kwargs: "只做主线核心",
                "render_core_mvp_digest": lambda *args, **kwargs: ["core-digest"],
                "render_mvp_focus_summary": lambda *args, **kwargs: ["focus-summary"],
                "get_execution_framework_text": lambda: "先60分钟确认，再看30分钟止损",
                "build_trade_price_focus": lambda minute_plan, stop_plan: {"compact_text": "盯10.50", "key_zone_display": "10.00-10.50", "note_text": "看10.50"},
                "build_observation_price_focus_text": lambda price_focus: price_focus.get("compact_text", "-"),
                "should_surface_price_note": lambda price_focus: False,
                "build_observation_price_note_text": lambda price_focus: price_focus.get("note_text", "-"),
                "append_watch_anchor_note": lambda report_lines, candidate, prefix="  ": None,
                "append_observation_price_focus_note": lambda report_lines, price_focus, prefix="  ": None,
                "compose_observation_focus_text": lambda confirm_text, observation_price_focus_text: f"{confirm_text} / {observation_price_focus_text}",
                "build_stop_execution_plan": lambda *args, **kwargs: {"summary": "预估9.50"},
                "build_candidate_exit_rules": lambda candidate, stop_plan=None: {"holding_days_min": 1, "holding_days_max": 3},
                "format_holding_window_text": lambda min_days, max_days: f"{min_days}-{max_days}天",
                "render_pk_decision_section": lambda context: [
                    f"#### {context['stage_label']} - {context['stage_title']}",
                    "pk-section",
                ],
                "render_action_plan_section": lambda context: ["#### 明日操作计划", "action-plan"],
                "decision_stack_order_text": "只保留一只",
                "today_predictions": [],
                "nextday_predictions": [],
            },
            stage_lookup["pk_decision"],
            stage_lookup,
        )

        rendered = "\n".join(result["lines"])
        self.assertEqual(
            result["lines"],
            [
                "#### Step 5 - PK决胜局（期望值模型）",
                "pk-section",
                "#### 明日操作计划",
                "action-plan",
                "",
            ],
        )
        self.assertEqual(
            set(result["exports"]),
            {
                "trade_gate_open",
                "best_stock",
                "runner_up",
                "watch_anchor",
                "watch_anchor_type",
                "abnormal_probe_group",
                "special_probe_verdict",
                "position_decision",
                "front_structure_layer_text",
                "front_follow_action_text",
                "special_probe_text",
                "philosophy_constraint_text",
                "scored_executable_stocks",
                "core_mvp_digest_lines",
                "mvp_focus_summary_lines",
                "action_plan_context_diagnostics",
                "candidate_quality_panel_fields",
                "candidate_quality_samples",
                "candidate_quality_scorecard_diagnostics",
            },
        )
        self.assertIn("#### Step 5 - PK决胜局（期望值模型）", rendered)
        self.assertIn("#### 明日操作计划", rendered)
        self.assertIn("pk-section", rendered)
        self.assertIn("action-plan", rendered)
        self.assertEqual(result["exports"]["trade_gate_open"], True)
        self.assertEqual(result["exports"]["best_stock"]["code"], "000001")
        self.assertEqual(result["exports"]["front_structure_layer_text"], "环境打开，只等唯一动作")
        self.assertEqual(result["exports"]["core_mvp_digest_lines"], ["core-digest"])
        self.assertEqual(result["exports"]["mvp_focus_summary_lines"], ["focus-summary"])
        stage_log = next(log for log in result["module_logs"] if log["module"] == "domains.execution_chain.pk_decision_stage")
        self.assertEqual(
            stage_log["details"],
            {
                "stage_key": "pk_decision",
                "trade_gate_open": True,
                "has_best_stock": True,
                "has_watch_anchor": False,
            },
        )
        self.assertTrue(any(log["module"] == "domains.execution_chain.pk_decision_node_runtime" for log in result["module_logs"]))

    def test_pk_decision_stage_uses_action_label_for_watch_only_conclusion(self):
        stage_lookup = build_execution_stage_lookup(
            [
                {"stage_key": "environment_follow", "title": "明日环境与跟随裁决"},
                {"stage_key": "watch_pool", "title": "明天观察池"},
                {"stage_key": "candidate_selection", "title": "明日核心标的"},
                {"stage_key": "risk_review", "title": "明日风险预判"},
                {"stage_key": "entry_plan", "title": "明日买点预计算"},
                {"stage_key": "pk_decision", "title": "PK决胜局（期望值模型）"},
            ]
        )

        captured = {}
        watch_anchor = {
            "name": "军工观察",
            "code": "000002",
            "minute_plan": {"confirm_price_60m": 10.5},
            "stop_plan": {"summary": "预估9.50"},
        }

        def _render_pk_section(context):
            captured["conclusion_lines"] = list(context.get("conclusion_lines") or [])
            return [f"#### {context['stage_label']} - {context['stage_title']}"]

        result = build_pk_decision_stage(
            {
                "target_date": "2026-04-22",
                "run_mode": "replay",
                "position_level": "一档（空仓档）",
                "position_reason": "环境不支持",
                "step0_prediction": "DIFFICULT",
                "step0_prediction_cn": "🔴 困难",
                "step0_action": "先空仓观察",
                "display_mvp_mode": False,
                "high_board_count": 0,
                "has_personal_positions": False,
                "final_gate": {"can_new_entry": False, "final_action": "空仓观察"},
                "mainline_name": "军工",
                "watchlist": [],
                "core_stocks": [],
                "secondary_stocks": [],
                "abnormal_watch_pool": [],
                "abnormal_watch_pool_all": [],
                "market_research_bundle": {
                    "gem_breathing_candidates": [],
                    "filtered_out_gem_breathing_candidates": [],
                },
                "market_research_snapshot": {"state_machine": {"leading_line": "军工"}, "style_switch": {}},
                "focus_group": [],
                "keep_group": [],
                "delete_group": [],
                "step2_bundle": {"crossline_observation_stocks": [], "evaluated_stocks": [], "gem_observation_stocks": []},
                "conviction_codes": set(),
                "leader_memory_codes": set(),
                "executable_stocks": [],
                "waiting_stocks": [],
                "safe_float": lambda value, default=0.0: float(default if value in (None, "") else value),
                "build_strategy_ev_calibration": lambda target_date, ledger_mode=None: {"source": "ledger"},
                "score_execution_candidate": lambda stock, ev_calibration: {**stock, "score": 99},
                "score_candidate_decision_stack": lambda stock, **kwargs: {**stock, "decision_stack_score": 99},
                "sort_decision_stack_candidates": lambda candidates: list(candidates),
                "sort_watch_anchor_candidates": lambda candidates, **kwargs: list(candidates),
                "get_trade_permission": lambda *args, **kwargs: {"permission_label": "观察权", "permission_reason": "等待", "can_execute": False},
                "fetch_recent_price_bars": lambda *args, **kwargs: [],
                "evaluate_live_tradability": lambda *args, **kwargs: {"can_trade": True, "report_day_is_one_word": False},
                "analyze_buy_signal": lambda *args, **kwargs: None,
                "quant_system_available": False,
                "build_waiting_stock_plan": lambda *args, **kwargs: {"name": "观察股", "code": "000002"},
                "derive_watch_anchor_type": lambda candidate, mainline_name="": "重点观察谁",
                "derive_watch_anchor_note": lambda candidate, mainline_name="": "先看承接",
                "build_abnormal_watch_anchor_candidates": lambda **kwargs: [watch_anchor],
                "select_priority_watch_anchor": lambda **kwargs: (watch_anchor, "重点观察谁"),
                "build_abnormal_probe_group": lambda *args, **kwargs: {"fallback_watch_anchor": {}},
                "build_special_probe_verdict": lambda **kwargs: {"probe_state": "", "summary_text": ""},
                "build_position_sizing_decision": lambda **kwargs: {"target_position_pct": 0, "candidate_feedback_ready": False, "trigger_text": "空仓等待"},
                "build_front_structure_layer_text": lambda **kwargs: "当前只允许观察",
                "build_front_follow_action_text": lambda **kwargs: "空仓等待",
                "build_special_probe_focus_text": lambda **kwargs: "先看主线异动",
                "build_philosophy_constraint_text": lambda **kwargs: "先不出手",
                "render_core_mvp_digest": lambda *args, **kwargs: ["core-digest"],
                "render_mvp_focus_summary": lambda *args, **kwargs: ["focus-summary"],
                "get_execution_framework_text": lambda: "先60分钟确认，再看30分钟止损",
                "build_trade_price_focus": lambda minute_plan, stop_plan: {"compact_text": "盯10.50", "key_zone_display": "10.00-10.50", "note_text": "看10.50"},
                "build_observation_price_focus_text": lambda price_focus: price_focus.get("compact_text", "-"),
                "should_surface_price_note": lambda price_focus: False,
                "build_observation_price_note_text": lambda price_focus: price_focus.get("note_text", "-"),
                "append_watch_anchor_note": lambda report_lines, candidate, prefix="  ": None,
                "append_observation_price_focus_note": lambda report_lines, price_focus, prefix="  ": None,
                "compose_observation_focus_text": lambda confirm_text, observation_price_focus_text: f"{confirm_text} / {observation_price_focus_text}",
                "build_stop_execution_plan": lambda *args, **kwargs: {"summary": "预估9.50"},
                "build_candidate_exit_rules": lambda candidate, stop_plan=None: {"holding_days_min": 1, "holding_days_max": 3},
                "format_holding_window_text": lambda min_days, max_days: f"{min_days}-{max_days}天",
                "render_pk_decision_section": _render_pk_section,
                "render_action_plan_section": lambda context: ["#### 明日操作计划", "action-plan"],
                "decision_stack_order_text": "只保留观察",
                "today_predictions": [],
                "nextday_predictions": [],
            },
            stage_lookup["pk_decision"],
            stage_lookup,
        )

        rendered = "\n".join(result["lines"])
        self.assertIn("#### Step 5 - PK决胜局（期望值模型）", rendered)
        self.assertIn("#### 明日操作计划", rendered)
        captured_lines = "\n".join(captured["conclusion_lines"])
        self.assertIn("- **当前只观察**: 一档（空仓档），不新增参与", captured_lines)
        self.assertNotIn("不允许新买入", captured_lines)
        self.assertNotIn("为什么先不买", "\n".join(captured["conclusion_lines"]))


if __name__ == "__main__":
    unittest.main()
