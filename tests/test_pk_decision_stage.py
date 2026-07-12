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
from domains.execution_chain.pk_decision_nodes.probe_position import build_pk_decision_probe_position_node
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
            format_closed_gate_buy_limit_text("0%不参与", {"allow_attack_50_ready": True}),
            "等固定交易窗口内条件成立；未确认按0%不参与",
        )
        self.assertEqual(
            format_closed_gate_buy_limit_text("0%不参与", {"allow_attack_50_ready": False}),
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
                "position_level": "0%不参与",
                "step0_prediction_cn": "0%不参与",
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
                "position_level": "0%不参与",
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
        self.assertEqual(
            result["exports"]["candidate_quality_panel_fields"]["account_attention_load"],
            "持仓未输入，先确认旧仓情况",
        )
        self.assertEqual(
            result["exports"]["candidate_quality_panel_fields"]["holding_priority_action"],
            "先确认旧仓情况，再看新增",
        )
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

    def test_candidate_quality_scorecard_uses_confirmed_empty_position_context(self):
        result = build_pk_decision_runtime(
            {
                "trade_gate_open": False,
                "position_level": "0%不参与",
                "step0_prediction_cn": "退潮防守",
                "final_gate": {"can_new_entry": False},
                "has_personal_positions": False,
                "position_context_provided": True,
                "best_stock": None,
                "watch_anchor": None,
                "display_observation_candidates": [],
                "waiting_stocks": [],
            },
            {"label": "Step 5", "title": "PK决胜局（期望值模型）"},
            enabled_node_keys=["candidate_quality_scorecard", "export_stage_state"],
        )

        panel_fields = result["exports"]["candidate_quality_panel_fields"]
        self.assertEqual(panel_fields["account_attention_load"], "无持仓负担")
        self.assertEqual(panel_fields["holding_priority_action"], "无旧仓时只等参与窗口")

    def test_candidate_quality_scorecard_keeps_inferred_old_path_separate_from_empty_position(self):
        result = build_pk_decision_runtime(
            {
                "trade_gate_open": False,
                "position_level": "0%不参与",
                "step0_prediction_cn": "退潮防守",
                "final_gate": {"can_new_entry": False},
                "has_personal_positions": False,
                "position_context_provided": True,
                "existing_position_summary": {
                    "has_position": False,
                    "has_pending_position": True,
                    "summary": "前日报计划推定，待成交确认：太极实业(600667)；未确认成交前不视为B1，不新增B2",
                    "default_position_pct": 100.0,
                    "position_source": "previous_report_target_default_1x",
                    "inferred_from_previous_report": True,
                },
                "best_stock": None,
                "watch_anchor": None,
                "display_observation_candidates": [],
                "waiting_stocks": [],
            },
            {"label": "Step 5", "title": "PK决胜局（期望值模型）"},
            enabled_node_keys=["candidate_quality_scorecard", "export_stage_state"],
        )

        panel_fields = result["exports"]["candidate_quality_panel_fields"]
        self.assertEqual(panel_fields["account_attention_load"], "前日报计划对象待成交确认")
        self.assertEqual(panel_fields["holding_priority_action"], "未确认成交前不视为B1；新机会按自身资格判断")

    def test_candidate_quality_scorecard_repairs_cached_inferred_position_fields(self):
        result = build_pk_decision_runtime(
            {
                "trade_gate_open": False,
                "position_level": "0%不参与",
                "step0_prediction_cn": "🟠 只处理旧仓",
                "final_gate": {"can_new_entry": False},
                "has_personal_positions": False,
                "position_context_provided": True,
                "existing_position_summary": {
                    "has_position": False,
                    "has_pending_position": True,
                    "name": "长电科技",
                    "code": "600584",
                    "position_source": "previous_report_target_default_1x",
                },
                "candidate_quality_panel_fields": {
                    "market_emotion_label": "🟠 只处理旧仓",
                    "account_attention_load": "默认1x旧仓需复核",
                    "holding_priority_action": "旧仓按旧路径处理；新机会按自身资格判断",
                    "daily_new_entry_limit": 0,
                    "primary_buy_candidate": None,
                    "backup_candidate": None,
                },
                "candidate_quality_samples": [],
                "display_observation_candidates": [],
                "waiting_stocks": [],
            },
            {"label": "Step 5", "title": "PK决胜局（期望值模型）"},
            enabled_node_keys=["candidate_quality_scorecard", "export_stage_state"],
        )

        panel_fields = result["exports"]["candidate_quality_panel_fields"]
        self.assertEqual(panel_fields["market_emotion_label"], "🟠 0%不参与；先确认成交事实")
        self.assertEqual(panel_fields["account_attention_load"], "前日报计划对象待成交确认")
        self.assertEqual(panel_fields["holding_priority_action"], "未确认成交前不视为B1；新机会按自身资格判断")

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

    def test_pk_decision_probe_position_prefers_leader_like_candidate_over_watch_sample(self):
        result = build_pk_decision_probe_position_node(
            {
                "target_date": "2026-06-04",
                "trade_gate_open": False,
                "mainline_name": "电力",
                "best_stock": None,
                "watch_anchor": {
                    "name": "上海石化",
                    "code": "600688",
                    "watch_source": "watch_anchor",
                    "candidate_layer": "watch_sample",
                    "execution_eligibility": "observation_only",
                },
                "watch_anchor_type": "跨线重点观察谁",
                "display_observation_candidates": [
                    {
                        "name": "上海石化",
                        "code": "600688",
                        "watch_source": "watch_anchor",
                        "candidate_layer": "watch_sample",
                        "execution_eligibility": "observation_only",
                    },
                    {
                        "name": "华电辽能",
                        "code": "600396",
                        "watch_source": "keep_group_watch",
                        "leader_speed_tier": "大容量趋势龙头",
                        "leader_certainty_path": "板块锚定龙 / 承接修复后再看",
                        "conviction_reason": "板块锚定龙 / 首波先锋",
                    },
                ],
                "leader_memory_bank": [
                    {
                        "name": "豫能控股",
                        "code": "001896",
                        "remember_score": 98.0,
                        "remember_reason": "首波先锋，优先做重点观察谁 / 热榜第7 / 2连板已被资金记住",
                    },
                    {
                        "name": "华电辽能",
                        "code": "600396",
                        "remember_score": 97.0,
                        "remember_reason": "首波先锋，优先做重点观察谁 / 热榜第4 / 2连板已被资金记住",
                    },
                ],
                "build_abnormal_probe_group": lambda *args, **kwargs: {"fallback_watch_anchor": {}},
                "build_special_probe_verdict": lambda **kwargs: {"probe_state": "", "summary_text": ""},
                "build_position_sizing_decision": lambda **kwargs: {
                    "target_position_pct": 0,
                    "candidate_feedback_ready": False,
                },
                "safe_float": lambda value, default=0.0: float(default if value in (None, "") else value),
            }
        )

        self.assertEqual(result["exports"]["selected_position_candidate"]["code"], "001896")

    def test_pk_decision_runtime_exports_probe_position_and_front_texts(self):
        candidate = {"name": "军工一号", "code": "000001"}
        result = build_pk_decision_runtime(
            {
                "target_date": "2026-04-22",
                "run_mode": "replay",
                "position_level": "50%条件执行",
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

    def test_pk_decision_runtime_keeps_final_observation_anchor_through_probe_and_render(self):
        captured = {}
        huadian = {
            "name": "华电能源",
            "code": "600726",
            "watch_source": "keep_group_watch",
            "watch_anchor_type": "主线重点观察谁",
            "watch_anchor_note": "趋势续强，连续走势符合强势标准，重点看是否继续创高。",
            "minute_plan": {"confirm_price_60m": 9.21},
            "stop_plan": {"effective_stop": 8.75},
        }

        def render_pk(context):
            captured["pk"] = dict(context)
            return ["pk"]

        def render_action(context):
            captured["action"] = dict(context)
            return ["action"]

        result = build_pk_decision_runtime(
            {
                "target_date": "2026-05-28",
                "render_pk_decision_section": render_pk,
                "render_action_plan_section": render_action,
                "trade_gate_open": False,
                "position_level": "0%不参与",
                "position_reason": "只处理旧仓",
                "step0_prediction": "NEUTRAL",
                "step0_prediction_cn": "0%不参与",
                "final_gate": {"can_new_entry": False, "allow_attack_50_ready": False, "should_reduce": True},
                "has_personal_positions": True,
                "mainline_name": "电力储能",
                "market_research_snapshot": {"state_machine": {}, "style_switch": {}},
                "abnormal_watch_pool_all": [],
                "focus_group": [],
                "keep_group": [],
                "display_observation_candidates": [
                    {
                        "name": "京能电力",
                        "code": "600578",
                        "watch_source": "waiting_layer",
                        "watch_anchor_type": "主线继续看谁",
                        "conviction_reason": "板块锚定龙 / 首波先锋",
                        "minute_plan": {"confirm_price_60m": 10.05},
                        "stop_plan": {"effective_stop": 8.75},
                    },
                    {"name": "金房能源", "code": "001210", "watch_source": "waiting_layer"},
                    {**huadian, "conviction_reason": "板块锚定龙 / 首波先锋"},
                ],
                "extreme_conviction_list": [{**huadian, "conviction_reason": "板块锚定龙 / 首波先锋"}],
                "watch_anchor": {
                    "name": "京能电力",
                    "code": "600578",
                    "watch_anchor_type": "主线继续看谁",
                    "conviction_reason": "板块锚定龙 / 首波先锋",
                    "minute_plan": {"confirm_price_60m": 10.05},
                    "stop_plan": {"effective_stop": 8.75},
                },
                "watch_anchor_type": "主线继续看谁",
                "safe_float": lambda value, default=0.0: float(default if value in (None, "") else value),
                "build_abnormal_probe_group": lambda *args, **kwargs: {"fallback_watch_anchor": {}},
                "build_special_probe_verdict": lambda **kwargs: {"probe_state": "", "summary_text": ""},
                "build_position_sizing_decision": lambda **kwargs: {
                    "target_position_pct": 0,
                    "candidate_feedback_ready": False,
                },
                "build_trade_price_focus": lambda minute_plan, stop_plan: {
                    "compact_text": "盯9.21",
                    "key_zone_display": f"关键位/带{(stop_plan or {}).get('effective_stop')}",
                },
                "build_observation_price_focus_text": lambda price_focus: price_focus.get("key_zone_display", "-"),
                "compose_observation_focus_text": lambda confirm_text, focus_text: f"09:50-10:10观察价{confirm_text}；{focus_text}",
                "should_surface_price_note": lambda price_focus: False,
                "get_execution_framework_text": lambda: "固定交易窗口条件",
                "waiting_stocks": [],
                "today_predictions": [],
                "nextday_predictions": [],
            },
            {"label": "Step 5", "title": "PK决胜局（期望值模型）"},
            enabled_node_keys=["probe_position", "pk_context", "action_plan_context", "render_sections", "export_stage_state"],
        )

        self.assertEqual(result["exports"]["selected_position_candidate"]["code"], "600726")
        pk_text = "\n".join(captured["pk"]["observation_lines"] + captured["pk"]["conclusion_lines"])
        action_text = "\n".join(captured["action"]["observation_priority_lines"] + captured["action"]["pre_market_lines"])
        self.assertIn("观察优先对象**: 华电能源(600726)", pk_text)
        self.assertIn("盘前不抢跑**: 华电能源(600726)", pk_text)
        self.assertLess(action_text.index("华电能源(600726)"), action_text.index("京能电力(600578)"))
        self.assertNotIn("盘前不抢跑**: 京能电力(600578)", pk_text)
        self.assertNotIn("主线继续看谁**: 京能电力(600578)", pk_text)

    def test_action_plan_context_maps_legacy_defense_position_to_zero_or_50_model(self):
        result = build_pk_decision_action_plan_context_node(
            {
                "trade_gate_open": False,
                "position_level": "0%不参与",
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
        self.assertIn("0%不参与", rendered)
        self.assertIn("不新增参与", rendered)
        self.assertIn("固定交易窗口条件", rendered)
        self.assertNotIn("50%条件执行", rendered)
        self.assertNotIn("禁止新开仓", rendered)
        self.assertNotIn(_m("最多", "旧小仓"), rendered)
        self.assertNotIn(_m("旧", "小仓", "条件", "试错"), rendered)
        self.assertNotIn("禁止新开仓", rendered)

    def test_action_plan_context_zero_position_uses_participation_wording(self):
        result = build_pk_decision_action_plan_context_node(
            {
                "trade_gate_open": False,
                "position_level": "0%不参与",
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

    def test_action_plan_context_rewrites_inferred_previous_plan_verdict(self):
        result = build_pk_decision_action_plan_context_node(
            {
                "trade_gate_open": False,
                "position_level": "0%不参与",
                "step0_prediction": "DIFFICULT",
                "step0_prediction_cn": "🟠 只处理旧仓",
                "final_gate": {"can_new_entry": False, "allow_attack_50_ready": False},
                "has_personal_positions": False,
                "position_context_provided": True,
                "existing_position_summary": {
                    "has_position": False,
                    "has_pending_position": True,
                    "summary": "前日报计划推定，待成交确认：长电科技(600584)；未确认成交前不视为B1，不新增B2",
                    "position_source": "previous_report_target_default_1x",
                    "inferred_from_previous_report": True,
                },
                "display_observation_candidates": [],
                "waiting_stocks": [],
                "today_predictions": [],
                "nextday_predictions": [],
                "get_execution_framework_text": lambda: "最终0%时只观察",
            }
        )

        rendered = "\n".join(result["exports"]["position_section_lines"])
        self.assertIn("明日裁决**: 🟠 0%不参与；先确认成交事实", rendered)
        self.assertNotIn("明日裁决**: 🟠 只处理旧仓", rendered)

    def test_action_plan_context_keeps_existing_position_when_no_new_target(self):
        result = build_pk_decision_action_plan_context_node(
            {
                "trade_gate_open": False,
                "position_level": "0%不参与",
                "step0_prediction": "DIFFICULT",
                "step0_prediction_cn": "🟠 只处理旧仓",
                "final_gate": {"can_new_entry": False, "allow_attack_50_ready": False, "should_reduce": False},
                "has_personal_positions": True,
                "position_context_provided": True,
                "existing_position_summary": {
                    "has_position": True,
                    "summary": "持有太极实业(600667)，100%仓位；先看28.89能否守住，09:50-10:10收不回先卖；新开仓0手",
                },
                "display_observation_candidates": [],
                "waiting_stocks": [],
                "today_predictions": [],
                "nextday_predictions": [],
                "get_execution_framework_text": lambda: "固定交易窗口条件",
            }
        )

        exports = result["exports"]
        rendered = "\n".join(
            exports["position_section_lines"]
            + [
                f"{row.get('action')} {row.get('name')} {row.get('trigger')}"
                for row in exports["action_rows"]
            ]
            + exports["pre_market_lines"]
            + exports["opening_lines"]
            + exports["first_hour_lines"]
            + exports["intraday_lines"]
            + exports["closing_lines"]
        )

        self.assertIn("已有旧仓：持有太极实业(600667)，100%仓位", rendered)
        self.assertIn("0%新仓；只处理旧仓，不新增参与", rendered)
        self.assertIn("🟠 只处理旧仓 旧仓", rendered)
        self.assertIn("先看旧仓竞价表态", rendered)
        self.assertNotIn("- **现在到底是什么状态**: 空仓", rendered)
        self.assertNotIn("- **明天仓位放多少**: 0%（保持空仓）", rendered)

    def test_action_plan_context_does_not_render_inferred_plan_as_existing_position(self):
        result = build_pk_decision_action_plan_context_node(
            {
                "trade_gate_open": False,
                "position_level": "0%不参与",
                "step0_prediction": "DIFFICULT",
                "step0_prediction_cn": "暂不跟随",
                "final_gate": {"can_new_entry": False, "allow_attack_50_ready": False, "should_reduce": True},
                "has_personal_positions": True,
                "position_context_provided": True,
                "existing_position_summary": {
                    "has_position": True,
                    "summary": "持有长电科技(600584)，100%仓位",
                    "position_source": "previous_report_target_default_1x",
                },
                "display_observation_candidates": [],
                "waiting_stocks": [],
                "today_predictions": [],
                "nextday_predictions": [],
                "get_execution_framework_text": lambda: "固定交易窗口条件",
            }
        )

        exports = result["exports"]
        rendered = "\n".join(
            exports["position_section_lines"]
            + [
                f"{row.get('action')} {row.get('name')} {row.get('trigger')}"
                for row in exports["action_rows"]
            ]
            + exports["pre_market_lines"]
            + exports["opening_lines"]
            + exports["first_hour_lines"]
            + exports["intraday_lines"]
            + exports["closing_lines"]
        )

        self.assertNotIn("已有旧仓", rendered)
        self.assertNotIn("持有长电科技", rendered)

    def test_action_plan_context_keeps_conviction_candidates_executable_after_ten_confirm(self):
        result = build_pk_decision_action_plan_context_node(
            {
                "trade_gate_open": False,
                "position_level": "0%不参与",
                "step0_prediction": "NEUTRAL",
                "step0_prediction_cn": "0%不参与",
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
        self.assertIn("B1先买参与权，B2只买确认权；B1未变强不补B2，走弱先取消B2并检查B1", rendered)
        self.assertIn("结果进入复盘和下一份日报判断", rendered)
        self.assertNotIn("才评估50%条件执行", rendered)
        self.assertNotIn("明天没有可买对象", rendered)
        self.assertNotIn("必须空仓", rendered)

    def test_action_plan_context_does_not_execute_candidate_with_incomplete_trace(self):
        result = build_pk_decision_action_plan_context_node(
            {
                "trade_gate_open": False,
                "position_level": "0%不参与",
                "step0_prediction": "NEUTRAL",
                "step0_prediction_cn": "0%不参与",
                "final_gate": {"can_new_entry": False, "allow_attack_50_ready": True, "should_reduce": False},
                "has_personal_positions": False,
                "display_observation_candidates": [
                    {
                        "name": "江海股份",
                        "code": "002484",
                        "permission_label": "重点观察名单",
                        "minute_plan": {"confirm_price_60m": 74.07},
                        "stop_plan": {"effective_stop": 70.37},
                        "trace": {
                            "final_action": "市场条件数据缺失；关键数据不完整，停止生成动作",
                        },
                    }
                ],
                "waiting_stocks": [],
                "today_predictions": [],
                "nextday_predictions": [],
                "get_execution_framework_text": lambda: "固定交易窗口条件",
                "build_trade_price_focus": lambda minute_plan, stop_plan: {"key_zone_display": "70.37"},
            }
        )

        action_text = "\n".join(
            " | ".join(str(row.get(key, "")) for key in ("action", "name", "code", "trigger", "risk_window"))
            for row in result["exports"]["action_rows"]
        )

        self.assertIn("明天没有可买对象", action_text)
        self.assertNotIn("确认后执行预案", action_text)
        self.assertNotIn("江海股份 | 002484", action_text)

    def test_action_plan_context_does_not_execute_candidate_with_external_incomplete_trace(self):
        result = build_pk_decision_action_plan_context_node(
            {
                "trade_gate_open": False,
                "position_level": "0%不参与",
                "step0_prediction": "NEUTRAL",
                "step0_prediction_cn": "0%不参与",
                "final_gate": {"can_new_entry": False, "allow_attack_50_ready": True, "should_reduce": True},
                "has_personal_positions": True,
                "display_observation_candidates": [
                    {
                        "name": "京能电力",
                        "code": "600578",
                        "permission_label": "主线观察权",
                        "minute_plan": {"confirm_price_60m": 9.21},
                        "stop_plan": {"effective_stop": 8.75},
                    }
                ],
                "candidate_trace_artifact": {
                    "payload": {
                        "traces": [
                            {
                                "stock_code": "600578",
                                "stock_name": "京能电力",
                                "checks": [{"label": "市场条件", "result": "数据缺失"}],
                                "branch_path": ["市场条件数据缺失", "关键数据不完整，停止生成动作"],
                                "missing_data": ["market_fit"],
                            }
                        ]
                    }
                },
                "waiting_stocks": [],
                "today_predictions": [],
                "nextday_predictions": [],
                "get_execution_framework_text": lambda: "固定交易窗口条件",
                "build_trade_price_focus": lambda minute_plan, stop_plan: {"key_zone_display": "8.75"},
            }
        )

        action_text = "\n".join(
            " | ".join(str(row.get(key, "")) for key in ("action", "name", "code", "trigger", "risk_window"))
            for row in result["exports"]["action_rows"]
        )

        self.assertIn("明天没有可买对象", action_text)
        self.assertNotIn("确认后执行预案", action_text)
        self.assertNotIn("京能电力 | 600578", action_text)

    def test_action_plan_context_keeps_old_position_first_observation_without_50_attack_plan(self):
        result = build_pk_decision_action_plan_context_node(
            {
                "trade_gate_open": False,
                "position_level": "0%不参与",
                "step0_prediction": "NEUTRAL",
                "step0_prediction_cn": "0%不参与",
                "final_gate": {"can_new_entry": False, "allow_attack_50_ready": True, "should_reduce": True},
                "has_personal_positions": True,
                "display_observation_candidates": [
                    {
                        "name": "华电能源",
                        "code": "600726",
                        "watch_anchor_type": "主线重点观察谁",
                        "watch_anchor_note": "趋势续强，连续走势符合强势标准，重点看是否继续创高。",
                        "minute_plan": {"confirm_price_60m": 9.21},
                        "stop_plan": {"effective_stop": 8.75},
                    },
                    {
                        "name": "京能电力",
                        "code": "600578",
                        "watch_anchor_type": "主线继续看谁",
                        "watch_anchor_note": "有辨识度，但最近没有连续走势符合强势标准，先别按趋势续强处理。",
                        "minute_plan": {"confirm_price_60m": 10.05},
                        "stop_plan": {"effective_stop": 8.75},
                    },
                ],
                "waiting_stocks": [],
                "today_predictions": [],
                "nextday_predictions": [],
                "get_execution_framework_text": lambda: "固定交易窗口条件",
                "build_trade_price_focus": lambda minute_plan, stop_plan: {
                    "key_zone_display": f"关键位/带{stop_plan.get('effective_stop')}",
                },
                "build_observation_price_focus_text": lambda price_focus: price_focus.get("key_zone_display", "-"),
                "compose_observation_focus_text": lambda confirm_text, focus_text: f"09:50-10:10观察价{confirm_text}；{focus_text}",
                "append_watch_anchor_note": lambda report_lines, candidate, prefix="  ": report_lines.append(
                    f"{prefix}{candidate.get('watch_anchor_note')}"
                )
                if candidate.get("watch_anchor_note")
                else None,
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

        self.assertIn("明天没有可买对象", action_text)
        self.assertIn("只处理旧仓", rendered)
        self.assertIn("华电能源(600726)", rendered)
        self.assertLess(rendered.index("华电能源(600726)"), rendered.index("京能电力(600578)"))
        self.assertNotIn("确认后执行预案", rendered)
        self.assertNotIn("50%条件执行", rendered)
        self.assertNotIn("条件50", rendered)
        self.assertNotIn("才评估50%", rendered)

    def test_action_plan_context_keeps_display_observation_order_ahead_of_legacy_watch_anchor(self):
        result = build_pk_decision_action_plan_context_node(
            {
                "trade_gate_open": False,
                "position_level": "0%不参与",
                "step0_prediction": "NEUTRAL",
                "step0_prediction_cn": "0%不参与",
                "final_gate": {"can_new_entry": False, "allow_attack_50_ready": False, "should_reduce": False},
                "has_personal_positions": True,
                "watch_anchor": {
                    "name": "京能电力",
                    "code": "600578",
                    "watch_anchor_type": "主线继续看谁",
                    "minute_plan": {"confirm_price_60m": 10.05},
                    "stop_plan": {"effective_stop": 8.75},
                },
                "display_observation_candidates": [
                    {
                        "name": "华电能源",
                        "code": "600726",
                        "watch_anchor_type": "主线重点观察谁",
                        "watch_anchor_note": "趋势续强，连续走势符合强势标准，重点看是否继续创高。",
                        "minute_plan": {"confirm_price_60m": 9.21},
                        "stop_plan": {"effective_stop": 8.75},
                    },
                    {
                        "name": "京能电力",
                        "code": "600578",
                        "watch_anchor_type": "主线继续看谁",
                        "watch_anchor_note": "有辨识度，但最近没有连续走势符合强势标准，先别按趋势续强处理。",
                        "minute_plan": {"confirm_price_60m": 10.05},
                        "stop_plan": {"effective_stop": 8.75},
                    },
                ],
                "waiting_stocks": [],
                "today_predictions": [],
                "nextday_predictions": [],
                "get_execution_framework_text": lambda: "固定交易窗口条件",
                "build_trade_price_focus": lambda minute_plan, stop_plan: {
                    "key_zone_display": f"关键位/带{stop_plan.get('effective_stop')}",
                },
                "build_observation_price_focus_text": lambda price_focus: price_focus.get("key_zone_display", "-"),
                "compose_observation_focus_text": lambda confirm_text, focus_text: f"09:50-10:10观察价{confirm_text}；{focus_text}",
                "append_watch_anchor_note": lambda report_lines, candidate, prefix="  ": report_lines.append(
                    f"{prefix}{candidate.get('watch_anchor_note')}"
                )
                if candidate.get("watch_anchor_note")
                else None,
            }
        )

        lines = result["exports"]["observation_priority_lines"]
        rendered = "\n".join(lines)
        self.assertLess(rendered.index("华电能源(600726)"), rendered.index("京能电力(600578)"))
        self.assertIn("趋势续强，连续走势符合强势标准", rendered)
        self.assertNotIn("连续 走势", rendered)

    def test_action_plan_context_prioritizes_final_observation_anchor_across_plan_surfaces(self):
        huadian = {
            "name": "华电能源",
            "code": "600726",
            "watch_anchor_type": "主线重点观察谁",
            "watch_anchor_note": "趋势续强，连续走势符合强势标准，重点看是否继续创高。",
            "minute_plan": {"confirm_price_60m": 9.21},
            "stop_plan": {"effective_stop": 8.75},
        }
        result = build_pk_decision_action_plan_context_node(
            {
                "trade_gate_open": False,
                "position_level": "0%不参与",
                "step0_prediction": "NEUTRAL",
                "step0_prediction_cn": "0%不参与",
                "final_gate": {"can_new_entry": False, "allow_attack_50_ready": False, "should_reduce": True},
                "has_personal_positions": True,
                "selected_position_candidate": huadian,
                "watch_anchor": {
                    "name": "京能电力",
                    "code": "600578",
                    "watch_anchor_type": "主线继续看谁",
                    "minute_plan": {"confirm_price_60m": 10.05},
                    "stop_plan": {"effective_stop": 8.75},
                },
                "display_observation_candidates": [
                    {
                        "name": "京能电力",
                        "code": "600578",
                        "watch_anchor_type": "主线继续看谁",
                        "minute_plan": {"confirm_price_60m": 10.05},
                        "stop_plan": {"effective_stop": 8.75},
                    },
                    {"name": "金房能源", "code": "001210", "watch_anchor_type": "主线继续看谁"},
                    huadian,
                ],
                "waiting_stocks": [],
                "today_predictions": [],
                "nextday_predictions": [],
                "get_execution_framework_text": lambda: "固定交易窗口条件",
                "build_trade_price_focus": lambda minute_plan, stop_plan: {
                    "key_zone_display": f"关键位/带{stop_plan.get('effective_stop')}",
                }
                if stop_plan
                else {},
                "build_observation_price_focus_text": lambda price_focus: price_focus.get("key_zone_display", "-"),
                "compose_observation_focus_text": lambda confirm_text, focus_text: f"09:50-10:10观察价{confirm_text}；{focus_text}",
            }
        )

        exports = result["exports"]
        priority_text = "\n".join(exports["observation_priority_lines"])
        pre_market_text = "\n".join(exports["pre_market_lines"])
        self.assertLess(priority_text.index("华电能源(600726)"), priority_text.index("京能电力(600578)"))
        self.assertIn("主线重点观察谁", pre_market_text)
        self.assertIn("华电能源(600726)", pre_market_text)
        self.assertNotIn("京能电力(600578) - 09:50-10:10", pre_market_text)
        self.assertEqual(exports["candidate_quality_panel_fields"]["backup_candidate"]["code"], "600726")
        self.assertEqual(exports["candidate_quality_samples"][0]["code"], "600726")

    def test_action_plan_context_exports_candidate_quality_inputs_from_daily_candidates(self):
        result = build_pk_decision_action_plan_context_node(
            {
                "trade_gate_open": False,
                "position_level": "0%不参与",
                "step0_prediction": "NEUTRAL",
                "step0_prediction_cn": "0%不参与",
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
        self.assertEqual(exports["candidate_quality_panel_fields"]["market_emotion_label"], "0%不参与")
        self.assertEqual(exports["candidate_quality_panel_fields"]["account_attention_load"], "有持仓需先处理")
        self.assertEqual(exports["candidate_quality_panel_fields"]["daily_new_entry_limit"], 0)
        self.assertEqual(exports["candidate_quality_panel_fields"]["primary_buy_candidate"]["code"], "603005")
        self.assertEqual(exports["candidate_quality_panel_fields"]["backup_candidate"]["code"], "000672")
        self.assertIn("亏损后补仓", exports["candidate_quality_panel_fields"]["forbidden_actions"])
        self.assertEqual(
            [sample["code"] for sample in exports["candidate_quality_samples"]],
            ["603005", "000672"],
        )

    def test_action_plan_context_does_not_promote_downgraded_sample_to_current_observation(self):
        downgraded_sample = {
            "name": "大有能源",
            "code": "600403",
            "sector": "煤炭开采",
            "watch_anchor_type": "跨线重点观察谁",
            "watch_priority_label": "观察优先",
            "reason": "大阳线封板，只观察承接",
            "candidate_role": "观察样本",
            "anchor_reversal_decision": "降级观察",
            "candidate_layer": "watch_sample",
            "execution_eligibility": "observation_only",
            "final_action": "只观察，不新增参与",
        }

        result = build_pk_decision_action_plan_context_node(
            {
                "trade_gate_open": False,
                "position_level": "0%不参与",
                "step0_prediction": "DIFFICULT",
                "step0_prediction_cn": "0%不参与",
                "final_gate": {"can_new_entry": False},
                "has_personal_positions": True,
                "display_observation_candidates": [downgraded_sample],
                "watch_anchor": {"name": "大有能源", "code": "600403"},
                "waiting_stocks": [],
                "today_predictions": [],
                "nextday_predictions": [],
                "build_trade_price_focus": lambda minute_plan, stop_plan: {},
                "build_observation_price_focus_text": lambda price_focus: "-",
                "compose_observation_focus_text": lambda confirm_text, focus_text: f"{confirm_text} / {focus_text}",
                "get_execution_framework_text": lambda: "只观察指数图形、主攻线承接和观察对象是否重新成立",
            }
        )

        rendered = "\n".join(
            result["exports"]["observation_priority_lines"]
            + result["exports"]["pre_market_lines"]
            + result["exports"]["first_hour_lines"]
            + result["exports"]["intraday_lines"]
        )
        panel_fields = result["exports"]["candidate_quality_panel_fields"]

        self.assertIsNone(panel_fields["backup_candidate"])
        self.assertNotIn("大有能源(600403)", rendered)
        self.assertIn("空仓准备", rendered)

    def test_action_plan_context_respects_empty_selection_workflow_final_before_rendering(self):
        process_candidate = {
            "name": "和远气体",
            "code": "002971",
            "sector": "化学制品",
            "minute_plan": {"confirm_price_60m": 52.75},
            "watch_anchor_type": "观察对象",
            "identity": "过程候选",
            "target_role": "过程候选",
            "source_pools": ["过程候选"],
            "front_observation_qualified": True,
            "observation_layer": "process_observation",
        }

        result = build_pk_decision_action_plan_context_node(
            {
                "trade_gate_open": False,
                "position_level": "0%不参与",
                "step0_prediction": "DIFFICULT",
                "step0_prediction_cn": "0%不参与",
                "final_gate": {"can_new_entry": False, "allow_attack_50_ready": True},
                "has_personal_positions": False,
                "best_stock": process_candidate,
                "watch_anchor": process_candidate,
                "display_observation_candidates": [process_candidate],
                "waiting_stocks": [{"name": "康强电子", "code": "002119"}],
                "selection_workflow": {
                    "schema_version": "selection_workflow.v1",
                    "final": {
                        "execution_object": {},
                        "position_pct": 0,
                        "action_text": "0%不参与",
                    },
                    "candidate_pool": [
                        {
                            "stock": {"name": "和远气体", "code": "002971", "sector": "化学制品"},
                            "identity": "过程候选",
                            "target_role": "过程候选",
                            "source_pools": ["过程候选"],
                            "front_observation_qualified": True,
                            "observation_layer": "process_observation",
                        }
                    ],
                },
                "today_predictions": [],
                "nextday_predictions": [],
                "build_trade_price_focus": lambda minute_plan, stop_plan: {"key_zone_display": "50.11"},
                "build_observation_price_focus_text": lambda price_focus: price_focus.get("key_zone_display", "-"),
                "compose_observation_focus_text": lambda confirm_text, focus_text: f"{confirm_text} / {focus_text}",
                "get_execution_framework_text": lambda: "只观察指数图形、主攻线承接和过程候选回放",
            }
        )

        exports = result["exports"]
        rendered = "\n".join(
            exports["observation_priority_lines"]
            + exports["backup_observation_lines"]
            + exports["pre_market_lines"]
        )

        self.assertEqual(exports["action_rows"][0]["action"], "❌ 明天没有可买对象")
        self.assertEqual(exports["action_rows"][0]["name"], "-")
        self.assertEqual(exports["observation_priority_lines"], [])
        self.assertEqual(exports["backup_observation_lines"], [])
        self.assertIsNone(exports["candidate_quality_panel_fields"]["primary_buy_candidate"])
        self.assertIsNone(exports["candidate_quality_panel_fields"]["backup_candidate"])
        self.assertNotIn("确认后执行预案", rendered)
        self.assertNotIn("和远气体(002971)", rendered)
        self.assertNotIn("康强电子", rendered)

    def test_action_plan_context_enriches_daily_candidates_for_trace_contracts(self):
        result = build_pk_decision_action_plan_context_node(
            {
                "trade_gate_open": False,
                "position_level": "0%不参与",
                "step0_prediction": "NEUTRAL",
                "step0_prediction_cn": "0%不参与",
                "final_gate": {"can_new_entry": False, "allow_attack_50_ready": False, "should_reduce": False},
                "mainline_name": "电力",
                "has_personal_positions": False,
                "best_stock": None,
                "watch_anchor": None,
                "display_observation_candidates": [
                    {
                        "name": "华电能源",
                        "code": "600726",
                        "mainline": "暂无",
                        "sector": "电力",
                        "stock_structure_fit": "数据缺失",
                        "reason": "主线内核 / 板块锚定龙 / 4连板 / 趋势审美 / 平台呼吸",
                    }
                ],
                "waiting_stocks": [],
                "today_predictions": [],
                "nextday_predictions": [],
                "get_execution_framework_text": lambda: "固定交易窗口条件",
            }
        )

        sample = result["exports"]["candidate_quality_samples"][0]
        self.assertEqual(sample["mainline"], "电力")
        self.assertEqual(sample["sector"], "电力")
        self.assertEqual(sample["tier"], "T2")
        self.assertIn("display_observation_candidates", sample["source_pools"])
        self.assertEqual(sample["market_fit"], "未满足")
        self.assertEqual(sample["mainline_fit"], "满足")
        self.assertEqual(sample["stock_structure_fit"], "部分满足")
        self.assertTrue(sample["trigger_condition"])
        self.assertTrue(sample["failure_condition"])

    def test_action_plan_context_clears_backup_candidate_when_same_as_primary(self):
        result = build_pk_decision_action_plan_context_node(
            {
                "trade_gate_open": True,
                "position_level": "50%条件执行",
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
                "position_level": "50%条件执行",
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
                "position_level": "50%条件执行",
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
                "position_level": "50%条件执行",
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
                "position_level": "50%条件执行",
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
                "position_level": "50%条件执行",
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
                "position_level": "0%不参与",
                "step0_prediction": "NEUTRAL",
                "step0_prediction_cn": "0%不参与",
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
                "position_level": "0%不参与",
                "step0_prediction": "NEUTRAL",
                "step0_prediction_cn": "0%不参与",
                "final_gate": {"can_new_entry": False, "allow_attack_50_ready": True},
                "has_personal_positions": True,
                "best_stock": None,
                "watch_anchor": {
                    "name": "观察对象",
                    "code": "000001",
                    "minute_plan": {"confirm_price_60m": 10.5},
                },
                "watch_anchor_type": "重点观察谁",
                "display_observation_candidates": [
                    {
                        "name": "观察对象",
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
                "position_level": "50%条件执行",
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
                    "market_emotion_label": "0%不参与",
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
                    "market_emotion_label": "0%不参与",
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

    def test_render_sections_does_not_surface_backup_candidate_when_final_resolution_waits_empty(self):
        result = build_pk_decision_runtime(
            {
                "render_pk_decision_section": lambda context: ["pk"],
                "render_action_plan_result": render_action_plan_result,
                "render_action_plan_section": render_action_plan_section,
                "action_plan_enabled_node_keys": ["overview", "candidate_quality"],
                "final_target_resolution": {
                    "watch_target": {},
                    "capital_priority_decision": {"capital_priority": "wait"},
                },
                "candidate_quality_panel_fields": {
                    "market_emotion_label": "🚫 暂不跟随",
                    "account_attention_load": "有持仓需先处理",
                    "holding_priority_action": "先处理旧仓，再看新增",
                    "daily_new_entry_limit": 0,
                    "primary_buy_candidate": None,
                    "backup_candidate": {"name": "大有能源", "code": "600403"},
                    "forbidden_actions": ["亏损后补仓", "计划外追高"],
                    "ignored_noise_items": ["外盘大涨但A股未确认", "论坛情绪"],
                },
                "candidate_quality_samples": [
                    {
                        "name": "大有能源",
                        "code": "600403",
                        "selection_quality": "中",
                        "entry_cost_state": "等确认",
                        "final_action": "只观察，不新增参与",
                    }
                ],
            },
            {"label": "Step 5", "title": "PK决胜局（期望值模型）"},
            enabled_node_keys=["render_sections"],
        )

        rendered = "\n".join(result["lines"])

        self.assertIn("| 补位对象 | 暂无 |", rendered)
        self.assertNotIn("| 补位对象 | 大有能源(600403) |", rendered)
        self.assertIn("| 大有能源(600403) |", rendered)

    def test_render_sections_clears_stale_observation_lists_when_final_resolution_waits_empty(self):
        result = build_pk_decision_runtime(
            {
                "render_pk_decision_section": lambda context: ["pk"],
                "render_action_plan_result": render_action_plan_result,
                "render_action_plan_section": render_action_plan_section,
                "action_plan_enabled_node_keys": ["overview", "action_table", "observation_blocks"],
                "final_target_resolution": {
                    "watch_target": {},
                    "capital_priority_decision": {"capital_priority": "wait"},
                },
                "action_rows": [
                    {
                        "action": "⏳ 确认后执行预案",
                        "name": "和远气体",
                        "code": "002971",
                        "trigger": "09:50-10:10站上52.75",
                        "risk_window": "50.11",
                    }
                ],
                "observation_priority_lines": [
                    "- 👀 江丰电子(300666) - 跨线继续看谁，09:50-10:10观察价待盘中确认"
                ],
                "backup_observation_lines": [
                    "- ⏳ 和远气体(002971) - 等观察位出现，09:50-10:10观察价52.75"
                ],
            },
            {"label": "Step 5", "title": "PK决胜局（期望值模型）"},
            enabled_node_keys=["render_sections"],
        )

        rendered = "\n".join(result["lines"])

        self.assertIn("| 暂无执行预案 | - | - | 当前最终对象为空，只回放过程候选，不新增参与 | - |", rendered)
        self.assertNotIn("确认后执行预案", rendered)
        self.assertNotIn("跨线继续看谁", rendered)
        self.assertNotIn("等观察位出现", rendered)
        self.assertNotIn("江丰电子(300666)", rendered)
        self.assertNotIn("和远气体(002971)", rendered)

    def test_render_sections_clears_stale_pk_context_lines_when_final_resolution_waits_empty(self):
        captured = {}

        def _render_pk_section(context):
            captured["observation_lines"] = list(context.get("observation_lines") or [])
            captured["conclusion_lines"] = list(context.get("conclusion_lines") or [])
            return (
                ["pk"]
                + captured["observation_lines"]
                + captured["conclusion_lines"]
            )

        result = build_pk_decision_runtime(
            {
                "render_pk_decision_section": _render_pk_section,
                "render_action_plan_result": render_action_plan_result,
                "render_action_plan_section": render_action_plan_section,
                "action_plan_enabled_node_keys": ["overview", "action_table", "observation_blocks"],
                "final_target_resolution": {
                    "watch_target": {},
                    "capital_priority_decision": {"capital_priority": "wait"},
                },
                "observation_lines": [
                    "**观察优先对象**: 江丰电子(300666)",
                    "- 👀 和远气体(002971) - 跨线继续看谁，09:50-10:10观察价待盘中确认",
                ],
                "conclusion_lines": [
                    "**结论**:",
                    "- **跨线继续看谁**: 江丰电子(300666)",
                    "- **观察对象**: 和远气体(002971)",
                ],
                "action_rows": [
                    {
                        "action": "⏳ 确认后执行预案",
                        "name": "和远气体",
                        "code": "002971",
                        "trigger": "09:50-10:10站上52.75",
                        "risk_window": "50.11",
                    }
                ],
            },
            {"label": "Step 5", "title": "PK决胜局（期望值模型）"},
            enabled_node_keys=["render_sections"],
        )

        rendered = "\n".join(result["lines"])
        self.assertEqual(captured["observation_lines"], [])
        self.assertIn("明天没有可买对象", "\n".join(captured["conclusion_lines"]))
        self.assertIn("空仓观望", "\n".join(captured["conclusion_lines"]))
        self.assertNotIn("江丰电子", rendered)
        self.assertNotIn("和远气体", rendered)
        self.assertNotIn("跨线继续看谁", rendered)
        self.assertNotIn("确认后执行预案", rendered)

    def test_render_sections_reads_empty_selection_workflow_under_old_position_priority(self):
        captured = {}

        def _render_pk_section(context):
            captured["observation_lines"] = list(context.get("observation_lines") or [])
            captured["conclusion_lines"] = list(context.get("conclusion_lines") or [])
            return ["pk", *captured["observation_lines"], *captured["conclusion_lines"]]

        result = build_pk_decision_runtime(
            {
                "render_pk_decision_section": _render_pk_section,
                "render_action_plan_result": render_action_plan_result,
                "render_action_plan_section": render_action_plan_section,
                "action_plan_enabled_node_keys": ["overview", "action_table", "observation_blocks"],
                "selection_workflow": {
                    "schema_version": "selection_workflow.v1",
                    "final": {"execution_object": {}, "position_pct": 0, "action_text": "0%不参与"},
                    "candidate_pool": [
                        {
                            "stock": {"name": "和远气体", "code": "002971"},
                            "identity": "过程候选",
                            "front_observation_qualified": True,
                            "observation_layer": "process_observation",
                        }
                    ],
                },
                "final_target_resolution": {
                    "watch_target": {"name": "和远气体", "code": "002971"},
                    "display_target": {"name": "华电辽能", "code": "600396"},
                    "capital_priority_decision": {"capital_priority": "old_position_t"},
                },
                "observation_lines": [
                    "**观察优先对象**: 和远气体(002971)",
                ],
                "conclusion_lines": [
                    "**结论**:",
                    "- **观察对象**: 和远气体(002971)",
                ],
                "action_rows": [
                    {
                        "action": "⏳ 确认后执行预案",
                        "name": "和远气体",
                        "code": "002971",
                        "trigger": "09:50-10:10站上52.75",
                        "risk_window": "50.11",
                    }
                ],
            },
            {"label": "Step 5", "title": "PK决胜局（期望值模型）"},
            enabled_node_keys=["render_sections"],
        )

        rendered = "\n".join(result["lines"])
        self.assertEqual(captured["observation_lines"], [])
        self.assertIn("明天没有可买对象", "\n".join(captured["conclusion_lines"]))
        self.assertNotIn("和远气体", rendered)
        self.assertNotIn("确认后执行预案", rendered)

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
                "position_level": "0%不参与",
                "step0_prediction": "NEUTRAL",
                "step0_prediction_cn": "0%不参与",
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
                "position_level": "0%不参与",
                "final_gate": {"can_new_entry": False, "allow_attack_50_ready": False},
                "front_structure_layer_text": "盘前0%不参与",
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
        self.assertIn("不买新仓", rendered)
        self.assertIn("不评估新增参与", rendered)
        self.assertNotIn("50%条件执行", rendered)
        self.assertNotIn("明天没有可买对象", rendered)
        self.assertNotIn("当前先不买", rendered)

    def test_pk_context_prioritizes_final_observation_anchor_over_waiting_order(self):
        huadian = {
            "name": "华电能源",
            "code": "600726",
            "watch_source": "keep_group_watch",
            "watch_anchor_type": "主线重点观察谁",
            "watch_priority_label": "趋势续强",
            "reason": "重点看是否继续创高",
            "minute_plan": {"confirm_price_60m": 9.21},
            "stop_plan": {"effective_stop": 8.75},
        }
        result = build_pk_decision_pk_context_node(
            {
                "trade_gate_open": False,
                "display_observation_candidates": [
                    {
                        "name": "京能电力",
                        "code": "600578",
                        "watch_source": "waiting_layer",
                        "watch_anchor_type": "主线继续看谁",
                        "watch_priority_label": "顺势观察",
                        "reason": "先看承接",
                        "minute_plan": {"confirm_price_60m": 10.05},
                    },
                    {"name": "金房能源", "code": "001210", "watch_source": "waiting_layer"},
                    huadian,
                ],
                "selected_position_candidate": huadian,
                "best_stock": None,
                "watch_anchor": {
                    "name": "京能电力",
                    "code": "600578",
                    "watch_anchor_type": "主线继续看谁",
                    "minute_plan": {"confirm_price_60m": 10.05},
                },
                "watch_anchor_type": "主线继续看谁",
                "position_level": "0%不参与",
                "final_gate": {"can_new_entry": False, "allow_attack_50_ready": False},
                "front_structure_layer_text": "只处理旧仓",
                "build_trade_price_focus": lambda minute_plan, stop_plan: {
                    "compact_text": "盯9.21",
                    "key_zone_display": "9.21/8.75",
                    "note_text": "确认价9.21",
                },
                "build_observation_price_focus_text": lambda price_focus: price_focus.get("compact_text", "-"),
                "should_surface_price_note": lambda price_focus: False,
                "compose_observation_focus_text": lambda confirm_text, focus_text: f"{confirm_text} / {focus_text}",
            }
        )

        observation_text = "\n".join(result["exports"]["observation_lines"])
        conclusion_text = "\n".join(result["exports"]["conclusion_lines"])
        self.assertLess(observation_text.index("| 华电能源 |"), observation_text.index("| 京能电力 |"))
        self.assertIn("观察优先对象**: 华电能源(600726)", observation_text)
        self.assertIn("主线重点观察谁**: 华电能源(600726)", conclusion_text)
        self.assertNotIn("主线继续看谁**: 京能电力(600578)", conclusion_text)

    def test_pk_context_does_not_promote_downgraded_sample_to_observation_anchor(self):
        downgraded_sample = {
            "name": "大有能源",
            "code": "600403",
            "sector": "煤炭开采",
            "watch_anchor_type": "跨线重点观察谁",
            "watch_priority_label": "观察优先",
            "reason": "大阳线封板，只观察承接",
            "candidate_role": "观察样本",
            "anchor_reversal_decision": "降级观察",
            "candidate_layer": "watch_sample",
            "execution_eligibility": "observation_only",
            "final_action": "只观察，不新增参与",
        }

        result = build_pk_decision_pk_context_node(
            {
                "trade_gate_open": False,
                "display_observation_candidates": [downgraded_sample],
                "watch_anchor": {"name": "大有能源", "code": "600403"},
                "watch_anchor_type": "跨线重点观察谁",
                "position_level": "0%不参与",
                "final_gate": {"can_new_entry": False},
                "front_structure_layer_text": "保持空仓",
                "build_trade_price_focus": lambda minute_plan, stop_plan: {},
                "build_observation_price_focus_text": lambda price_focus: "-",
                "compose_observation_focus_text": lambda confirm_text, focus_text: f"{confirm_text} / {focus_text}",
            }
        )

        rendered = "\n".join(result["exports"]["observation_lines"] + result["exports"]["conclusion_lines"])

        self.assertNotIn("观察优先" + "锚点**: 大有能源(600403)", rendered)
        self.assertNotIn("跨线重点观察谁**: 大有能源(600403)", rendered)
        self.assertIn("无执行资格候选", rendered)

    def test_pk_context_clears_process_candidates_when_final_workflow_is_empty(self):
        jiangfeng = {
            "name": "江丰电子",
            "code": "300666",
            "watch_anchor_type": "跨线继续看谁",
            "watch_priority_label": "跨线继续看谁",
            "reason": "旧观察行残留",
        }
        heyuan = {
            "name": "和远气体",
            "code": "002971",
            "watch_anchor_type": "观察对象",
            "watch_priority_label": "等观察位出现",
            "reason": "过程候选残留",
        }

        result = build_pk_decision_pk_context_node(
            {
                "trade_gate_open": False,
                "display_observation_candidates": [jiangfeng, heyuan],
                "watch_anchor": jiangfeng,
                "watch_anchor_type": "跨线继续看谁",
                "best_stock": heyuan,
                "position_level": "0%不参与",
                "final_gate": {"can_new_entry": False, "allow_attack_50_ready": True},
                "front_structure_layer_text": "最终对象为空",
                "selection_workflow": {
                    "schema_version": "selection_workflow.v1",
                    "final": {
                        "execution_object": {},
                        "position_pct": 0,
                        "action_text": "0%不参与",
                    },
                    "candidate_pool": [
                        {
                            "stock": {"name": "和远气体", "code": "002971"},
                            "identity": "过程候选",
                            "target_role": "过程候选",
                            "source_pools": ["过程候选"],
                            "front_observation_qualified": True,
                            "observation_layer": "process_observation",
                        }
                    ],
                },
                "build_trade_price_focus": lambda minute_plan, stop_plan: {},
                "build_observation_price_focus_text": lambda price_focus: "-",
                "compose_observation_focus_text": lambda confirm_text, focus_text: f"{confirm_text} / {focus_text}",
            }
        )

        rendered = "\n".join(result["exports"]["observation_lines"] + result["exports"]["conclusion_lines"])
        self.assertIn("无执行资格候选", rendered)
        self.assertIn("明天没有可买对象", rendered)
        self.assertIn("空仓观望", rendered)
        self.assertNotIn("江丰电子", rendered)
        self.assertNotIn("和远气体", rendered)
        self.assertNotIn("跨线继续看谁", rendered)
        self.assertNotIn("等观察位出现", rendered)
        self.assertNotIn("确认后怎么做", rendered)

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
                "position_level": "50%条件执行",
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
                "selected_position_candidate",
                "display_observation_candidates",
                "observation_candidates",
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
                "sniper_target_derivation",
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
                "position_level": "0%不参与",
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
        self.assertIn("- **当前只观察**: 0%不参与，不新增参与", captured_lines)
        self.assertNotIn("不允许新买入", captured_lines)
        self.assertNotIn("为什么先不买", "\n".join(captured["conclusion_lines"]))


if __name__ == "__main__":
    unittest.main()
