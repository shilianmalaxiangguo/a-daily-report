import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from domains.execution_chain.pk_decision_stage import (
    build_pk_decision_runtime,
    build_pk_decision_stage,
    format_closed_gate_buy_limit_text,
)
from domains.execution_chain.pk_decision_nodes.observation_pool import build_pk_decision_observation_pool_node
from domains.execution_chain.pk_decision_nodes.watch_anchor import build_pk_decision_watch_anchor_node
from domains.execution_chain.stage_runtime import build_execution_stage_lookup


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

    def test_conditional_defense_gate_formats_as_ten_oclock_confirmation_not_absolute_ban(self):
        self.assertEqual(
            format_closed_gate_buy_limit_text("二档（防守档）", {"allow_conditional_30": True}),
            "等10点确认，未确认不开",
        )
        self.assertEqual(
            format_closed_gate_buy_limit_text("一档（空仓档）", {"allow_conditional_30": False}),
            "⛔一档（空仓档）禁止新开仓",
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
        self.assertIn("- **当前先不买**: 一档（空仓档），当前只允许观察，不允许新买入", "\n".join(captured["conclusion_lines"]))
        self.assertNotIn("为什么先不买", "\n".join(captured["conclusion_lines"]))


if __name__ == "__main__":
    unittest.main()
