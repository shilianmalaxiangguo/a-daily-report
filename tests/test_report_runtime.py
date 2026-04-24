import importlib
import subprocess
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report import runtime as report_runtime


def _run_legacy_entry_probe(script_body):
    stub_setup = """
import sys
import types
from unittest.mock import patch

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


class ReportRuntimeTest(unittest.TestCase):
    def test_get_or_build_calendar_ai_context_reuses_shared_runtime_cache(self):
        calls = []
        original_cache = report_runtime.REPORT_RUNTIME_CACHE
        original_builder = getattr(report_runtime, "_build_calendar_ai_context", None)
        try:
            report_runtime.REPORT_RUNTIME_CACHE = {}
            report_runtime._build_calendar_ai_context = lambda data, print_fn=print: calls.append(len(data.get("calendar_events", []))) or {
                "calendar_analysis": [{"title": "大会", "ai_analysis": {"main_direction": "军工", "expectation": "利好", "related_sectors": ["军工"]}, "star": "⭐⭐⭐", "date": "2026-04-22"}],
                "top_directions": [("军工", 1)],
                "unique_sectors": ["军工"],
                "bullish_events": [{"title": "大会", "ai_analysis": {"main_direction": "军工", "expectation": "利好", "related_sectors": ["军工"]}}],
            }

            data = {"calendar_events": [{"date": "2026-04-22", "title": "大会", "star": 5}]}
            first = report_runtime._get_or_build_calendar_ai_context(data)
            second = report_runtime._get_or_build_calendar_ai_context(data)

            self.assertIs(first, second)
            self.assertEqual(calls, [1])
            self.assertEqual(first["top_directions"][0][0], "军工")
        finally:
            report_runtime.REPORT_RUNTIME_CACHE = original_cache
            if original_builder is None:
                delattr(report_runtime, "_build_calendar_ai_context")
            else:
                report_runtime._build_calendar_ai_context = original_builder

    def test_get_or_build_market_phase_context_reuses_shared_runtime_cache(self):
        calls = []
        original_cache = report_runtime.REPORT_RUNTIME_CACHE
        original_builder = getattr(report_runtime, "build_market_phase_context", None)
        try:
            report_runtime.REPORT_RUNTIME_CACHE = {}
            report_runtime.build_market_phase_context = lambda data, target_date, emit_logs=True: calls.append((target_date, emit_logs)) or {
                "target_date": target_date,
                "market_trend": "震荡整理",
            }

            data = {"foo": "bar"}
            first = report_runtime._get_or_build_market_phase_context(data, "2026-04-22")
            second = report_runtime._get_or_build_market_phase_context(data, "2026-04-22")

            self.assertEqual(first["target_date"], "2026-04-22")
            self.assertIs(first, second)
            self.assertEqual(calls, [("2026-04-22", True)])
        finally:
            report_runtime.REPORT_RUNTIME_CACHE = original_cache
            if original_builder is None:
                delattr(report_runtime, "build_market_phase_context")
            else:
                report_runtime.build_market_phase_context = original_builder

    def test_get_or_build_market_phase_context_does_not_reuse_cache_across_different_data_objects(self):
        calls = []
        original_cache = report_runtime.REPORT_RUNTIME_CACHE
        original_builder = getattr(report_runtime, "build_market_phase_context", None)
        try:
            report_runtime.REPORT_RUNTIME_CACHE = {}
            report_runtime.build_market_phase_context = lambda data, target_date, emit_logs=True: calls.append(id(data)) or {
                "target_date": target_date,
                "payload_id": id(data),
            }

            first_data = {"foo": 1}
            second_data = {"foo": 2}
            first = report_runtime._get_or_build_market_phase_context(first_data, "2026-04-22")
            second = report_runtime._get_or_build_market_phase_context(second_data, "2026-04-22")

            self.assertNotEqual(first["payload_id"], second["payload_id"])
            self.assertEqual(len(calls), 2)
        finally:
            report_runtime.REPORT_RUNTIME_CACHE = original_cache
            if original_builder is None:
                delattr(report_runtime, "build_market_phase_context")
            else:
                report_runtime.build_market_phase_context = original_builder

    def test_get_or_build_market_research_bundle_reuses_shared_runtime_cache(self):
        calls = []
        original_cache = report_runtime.REPORT_RUNTIME_CACHE
        original_builder = getattr(report_runtime, "build_market_research_context_bundle", None)
        try:
            report_runtime.REPORT_RUNTIME_CACHE = {}
            report_runtime.build_market_research_context_bundle = (
                lambda data, target_date, exit_analysis, final_gate, position_level, **kwargs: calls.append(
                    (id(data), target_date, position_level)
                )
                or {
                    "target_date": target_date,
                    "payload_id": id(data),
                    "position_level": position_level,
                }
            )

            data = {"foo": "bar"}
            kwargs = {
                "main_sectors_info": [{"name": "军工"}],
                "secondary_sectors_info": [{"name": "机器人"}],
                "main_sectors": ["军工"],
                "secondary_sectors": ["机器人"],
                "dragon_stocks": [{"code": "000001", "name": "平安银行"}],
            }

            first = report_runtime._get_or_build_market_research_bundle(
                data,
                "2026-04-22",
                {"sector_name": "军工"},
                {"can_new_entry": True, "final_action": "聚焦军工"},
                "三档（进攻档）",
                **kwargs,
            )
            second = report_runtime._get_or_build_market_research_bundle(
                data,
                "2026-04-22",
                {"sector_name": "军工"},
                {"can_new_entry": True, "final_action": "聚焦军工"},
                "三档（进攻档）",
                **kwargs,
            )

            self.assertIs(first, second)
            self.assertEqual(calls, [(id(data), "2026-04-22", "三档（进攻档）")])
        finally:
            report_runtime.REPORT_RUNTIME_CACHE = original_cache
            if original_builder is None:
                delattr(report_runtime, "build_market_research_context_bundle")
            else:
                report_runtime.build_market_research_context_bundle = original_builder

    def test_get_or_build_market_research_bundle_does_not_reuse_cache_across_different_data_objects(self):
        calls = []
        original_cache = report_runtime.REPORT_RUNTIME_CACHE
        original_builder = getattr(report_runtime, "build_market_research_context_bundle", None)
        try:
            report_runtime.REPORT_RUNTIME_CACHE = {}
            report_runtime.build_market_research_context_bundle = (
                lambda data, target_date, exit_analysis, final_gate, position_level, **kwargs: calls.append(id(data))
                or {
                    "target_date": target_date,
                    "payload_id": id(data),
                }
            )

            kwargs = {
                "main_sectors_info": [{"name": "军工"}],
                "secondary_sectors_info": [{"name": "机器人"}],
                "main_sectors": ["军工"],
                "secondary_sectors": ["机器人"],
                "dragon_stocks": [{"code": "000001", "name": "平安银行"}],
            }

            first_data = {"foo": 1}
            second_data = {"foo": 2}
            first = report_runtime._get_or_build_market_research_bundle(
                first_data,
                "2026-04-22",
                {"sector_name": "军工"},
                {"can_new_entry": True, "final_action": "聚焦军工"},
                "三档（进攻档）",
                **kwargs,
            )
            second = report_runtime._get_or_build_market_research_bundle(
                second_data,
                "2026-04-22",
                {"sector_name": "军工"},
                {"can_new_entry": True, "final_action": "聚焦军工"},
                "三档（进攻档）",
                **kwargs,
            )

            self.assertNotEqual(first["payload_id"], second["payload_id"])
            self.assertEqual(len(calls), 2)
        finally:
            report_runtime.REPORT_RUNTIME_CACHE = original_cache
            if original_builder is None:
                delattr(report_runtime, "build_market_research_context_bundle")
            else:
                report_runtime.build_market_research_context_bundle = original_builder

    def test_get_or_build_market_research_bundle_requests_display_safe_abnormal_snapshot_mode(self):
        captured = {}
        original_cache = report_runtime.REPORT_RUNTIME_CACHE
        original_builder = getattr(report_runtime, "build_market_research_context_bundle", None)
        try:
            report_runtime.REPORT_RUNTIME_CACHE = {}

            def _capture_builder(data, target_date, exit_analysis, final_gate, position_level, **kwargs):
                captured.update(kwargs)
                return {"target_date": target_date}

            report_runtime.build_market_research_context_bundle = _capture_builder

            report_runtime._get_or_build_market_research_bundle(
                {"foo": "bar"},
                "2026-04-22",
                {"sector_name": "军工"},
                {"can_new_entry": True, "final_action": "聚焦军工"},
                "三档（进攻档）",
                main_sectors_info=[{"name": "军工"}],
                secondary_sectors_info=[{"name": "机器人"}],
                main_sectors=["军工"],
                secondary_sectors=["机器人"],
                dragon_stocks=[{"code": "000001", "name": "平安银行"}],
            )

            self.assertEqual(captured["decision_strict_mode"], False)
            self.assertEqual(captured["allow_display_degraded_abnormal_snapshot"], True)
        finally:
            report_runtime.REPORT_RUNTIME_CACHE = original_cache
            if original_builder is None:
                delattr(report_runtime, "build_market_research_context_bundle")
            else:
                report_runtime.build_market_research_context_bundle = original_builder

    def test_finalize_helper_diagnostics_merges_helper_logs_into_data(self):
        captured = []
        report_runtime._drain_helper_logs = lambda: [
            {
                "module": "domains.market_activity.support",
                "step": "helper.stock_sector.eastmoney",
                "status": "error",
                "message": "Eastmoney行业接口失败",
                "details": {
                    "provider": "eastmoney.company_survey",
                    "target_keys": ["sector"],
                    "error": "timeout",
                },
            }
        ]
        report_runtime._build_helper_diagnostics = lambda logs: {
            "summary": {"helper_log_count": len(logs), "error_count": 1}
        }
        report_runtime._render_helper_diagnostics_lines = lambda diagnostics: [
            "辅助接口体检摘要",
            f"errors={diagnostics['summary']['error_count']}",
        ]

        data = {"module_logs": []}
        diagnostics = report_runtime._finalize_helper_diagnostics(data, print_fn=captured.append)

        self.assertEqual(diagnostics["summary"]["helper_log_count"], 1)
        self.assertEqual(data["helper_diagnostics"]["summary"]["error_count"], 1)
        self.assertEqual(data["module_logs"][0]["step"], "helper.stock_sector.eastmoney")
        self.assertEqual(captured, ["辅助接口体检摘要", "errors=1"])

    def test_render_markdown_report_runtime_uses_exchange_monitor_lists_from_data(self):
        class _StageContextCaptured(RuntimeError):
            pass

        def _capture_stage_context(stage_specs, stage_context=None, stage_lookup=None):
            self.assertEqual(stage_context["today_predictions"], [{"code": "000001"}])
            self.assertEqual(stage_context["nextday_predictions"], [{"code": "000002"}])
            digest_kwargs = stage_context["render_core_mvp_digest"](
                {},
                final_gate={},
                position_level="",
                position_reason="",
            )
            focus_kwargs = stage_context["render_mvp_focus_summary"]({})
            self.assertIn("build_gem_textbook_next_step_text", digest_kwargs)
            self.assertIn("resolve_primary_mainline_name", digest_kwargs)
            self.assertIn("split_abnormal_watch_pool", focus_kwargs)
            self.assertIn("split_candidates_by_mainline", focus_kwargs)
            raise _StageContextCaptured("captured")

        helpers = {
            "DISPLAY_MVP_MODE": False,
            "markdown_hooks": types.SimpleNamespace(use_report_preamble=lambda *args, **kwargs: []),
            "build_report_shell_contract": lambda *args, **kwargs: {"report": []},
            "build_market_phase_context": lambda *args, **kwargs: {
                "market_zhongshu": {},
                "market_analysis": {},
                "market_trend": "震荡整理",
                "mainline_context": {},
                "main_sectors_info": [],
                "secondary_sectors_info": [],
                "main_sectors": [],
                "secondary_sectors": [],
                "dragon_stocks": [],
                "exit_analysis": {},
                "turnover": 0,
                "zt_count": 0,
                "dt_count": 0,
                "indices": {},
                "sh_change": 0,
                "market_stats": {},
                "up_count": 0,
                "down_count": 0,
                "rise_fall_ratio": 0,
                "zs_signal_type": "",
                "zs_signal_status": "",
                "is_dt_panic": False,
                "base_position_level": "",
                "base_position_reason": "",
                "position_level": "",
                "position_reason": "",
                "final_gate": {"final_action": "观察", "operation_state": "观察态", "can_new_entry": False},
                "environment_display": {"position_level": "", "operation_state": "观察态"},
                "overall_level": "红灯",
                "price_info": {},
            },
            "_resolve_environment_reason_contract": lambda **kwargs: "",
            "build_exchange_monitor_sections_contract": lambda data: {"lines": []},
            "build_execution_stage_lookup": lambda specs: {},
            "get_execution_stage_label": lambda lookup, key: "Step 2",
            "build_market_research_context_bundle": lambda *args, **kwargs: {},
            "build_execution_stage_specs": lambda *args, **kwargs: [],
            "run_registered_execution_stages": _capture_stage_context,
            "_render_core_mvp_digest": lambda *args, **kwargs: kwargs,
            "_render_mvp_focus_summary": lambda *args, **kwargs: kwargs,
            "_render_market_research_snapshot_section": lambda *args, **kwargs: "",
            "_render_step0_follow_section": lambda *args, **kwargs: "",
            "_is_degraded_abnormal_snapshot": lambda *args, **kwargs: False,
            "_format_abnormal_observation_columns": lambda *args, **kwargs: ("", ""),
            "_render_gem_breathing_step2_section": lambda *args, **kwargs: "",
            "_render_gem_breathing_pool_section": lambda *args, **kwargs: "",
            "build_prohibition_section_contract": lambda *args, **kwargs: {"lines": []},
            "replace_placeholder_lines": lambda report, placeholder, lines: report,
            "build_market_trend_sections_contract": lambda *args, **kwargs: {"lines": []},
            "build_market_activity_report_sections": lambda *args, **kwargs: {"lines": []},
            "build_market_and_sector_analysis_contract": lambda *args, **kwargs: {"lines": []},
            "build_advanced_activity_report_sections": lambda *args, **kwargs: {"lines": []},
            "build_board_tag_analysis_sections_contract": lambda *args, **kwargs: {"lines": []},
            "analyze_sector_distribution": lambda *args, **kwargs: {},
            "get_stock_status": lambda *args, **kwargs: "",
            "get_stock_sector": lambda *args, **kwargs: "",
            "analyze_candlestick_pattern": lambda *args, **kwargs: {},
            "ai_group_concepts_into_chains": lambda *args, **kwargs: {},
            "build_environment_follow_stage": object(),
            "build_watch_pool_stage": object(),
            "build_candidate_selection_stage": object(),
            "build_risk_review_stage": object(),
            "build_entry_plan_stage": object(),
            "build_pk_decision_stage": object(),
            "DEFAULT_EXECUTION_STAGE_SPECS": {},
            "_build_zhongshu_ascii_diagram": lambda *args, **kwargs: "",
            "get_execution_framework_text": lambda: "",
            "_build_gem_textbook_next_step_text": lambda *args, **kwargs: "",
            "_build_alignment_pool_text": lambda *args, **kwargs: "",
            "_build_mainline_rotation_snapshot": lambda *args, **kwargs: {},
            "_resolve_primary_mainline_name": lambda *args, **kwargs: "",
            "_build_weak_to_strong_context": lambda *args, **kwargs: {},
            "_get_contract_logic_digest_text": lambda *args, **kwargs: "",
            "render_front_digest": lambda payload: payload,
            "render_mvp_focus_summary": lambda payload: payload,
            "QUANT_SYSTEM_AVAILABLE": False,
            "STOP_PRIOR_LOW_TRADING_DAYS": 3,
            "render_gem_breathing_step2_section": lambda *args, **kwargs: "",
            "build_step2_candidate_bundle": lambda *args, **kwargs: {},
            "build_step3_risk_bundle": lambda *args, **kwargs: {},
            "render_gem_breathing_pool_section": lambda *args, **kwargs: "",
            "normalize_stock_code": lambda value: value,
            "get_trade_permission": lambda *args, **kwargs: {},
            "fetch_recent_price_bars": lambda *args, **kwargs: [],
            "evaluate_live_tradability": lambda *args, **kwargs: {},
            "build_intraday_execution_plan": lambda *args, **kwargs: {},
            "build_stop_execution_plan": lambda *args, **kwargs: {},
            "_enrich_stop_plan_with_reference_anchors": lambda *args, **kwargs: {},
            "build_waiting_stock_plan": lambda *args, **kwargs: {},
            "_finalize_waiting_candidate": lambda *args, **kwargs: {},
            "_build_trade_price_focus": lambda *args, **kwargs: {},
            "_build_observation_price_focus_text": lambda *args, **kwargs: "",
            "_append_price_focus_note": lambda *args, **kwargs: None,
            "_append_observation_price_focus_note": lambda *args, **kwargs: None,
            "_compose_observation_focus_text": lambda *args, **kwargs: "",
            "_build_front_structure_layer_text": lambda *args, **kwargs: "",
            "analyze_buy_signal": None,
            "_safe_float": lambda value, default=0.0: default if value in (None, "") else float(value),
            "ai_analyze_sector_relationships": lambda *args, **kwargs: {},
            "score_execution_candidate": lambda *args, **kwargs: 0,
            "score_candidate_decision_stack": lambda *args, **kwargs: {},
            "sort_decision_stack_candidates": lambda items: items,
            "sort_watch_anchor_candidates": lambda items, **kwargs: items,
            "build_strategy_ev_calibration": lambda *args, **kwargs: {},
            "_build_abnormal_watch_anchor_candidates": lambda *args, **kwargs: [],
            "_select_priority_watch_anchor": lambda *args, **kwargs: ({}, ""),
            "_derive_watch_anchor_type": lambda *args, **kwargs: "",
            "_derive_watch_anchor_note": lambda *args, **kwargs: "",
            "_build_abnormal_probe_group": lambda *args, **kwargs: {},
            "_build_special_probe_verdict": lambda *args, **kwargs: {},
            "_build_position_sizing_decision": lambda *args, **kwargs: {},
            "_split_abnormal_watch_pool": lambda pool: (pool or [], []),
            "_split_candidates_by_mainline": lambda items, mainline_name="": (items or [], []),
            "_build_bridge_prep_context": lambda *args, **kwargs: {},
            "_build_front_follow_action_text": lambda *args, **kwargs: "",
            "_build_special_probe_focus_text": lambda *args, **kwargs: "",
            "_build_philosophy_constraint_text": lambda *args, **kwargs: "",
            "_should_surface_price_note": lambda *args, **kwargs: False,
            "_build_observation_price_note_text": lambda *args, **kwargs: "",
            "_append_watch_anchor_note": lambda *args, **kwargs: None,
            "_build_candidate_exit_rules": lambda *args, **kwargs: {},
            "_format_holding_window_text": lambda *args, **kwargs: "",
            "_format_candidate_preview": lambda *args, **kwargs: "",
            "_candidate_matches_mainline": lambda *args, **kwargs: False,
            "_build_cycle_triplet_texts": lambda *args, **kwargs: {},
            "_build_execute_anchor_window_text": lambda *args, **kwargs: "",
            "_format_abnormal_probe_text": lambda *args, **kwargs: "",
            "render_pk_decision_section": lambda *args, **kwargs: "",
            "render_action_plan_section": lambda *args, **kwargs: "",
            "DECISION_STACK_ORDER_TEXT": "",
        }

        with self.assertRaises(_StageContextCaptured):
            report_runtime.render_markdown_report_runtime(
                {
                    "exchange_monitor_today": [{"code": "000001"}],
                    "exchange_monitor_nextday": [{"code": "000002"}],
                },
                "2026-04-22",
                helpers=helpers,
                config={},
            )

    def test_legacy_report_output_helpers_resolve_to_daily_report_render_exports(self):
        result = _run_legacy_entry_probe(
            """
import daily_report_entry_demo
import daily_report_render

assert daily_report_entry_demo._get_report_output_path is daily_report_render._get_report_output_path
assert daily_report_entry_demo._inject_report_variant_banner is daily_report_render._inject_report_variant_banner
assert daily_report_entry_demo._render_report_with_display_mode is daily_report_render._render_report_with_display_mode
assert daily_report_entry_demo.build_report_outputs is daily_report_render.build_report_outputs
assert daily_report_entry_demo.save_report_output is daily_report_render.save_report_output
assert daily_report_entry_demo.save_report_outputs is daily_report_render.save_report_outputs
assert daily_report_entry_demo._get_stock_diagnostic_output_path is daily_report_render._get_stock_diagnostic_output_path
assert daily_report_entry_demo.save_stock_diagnostic_output is daily_report_render.save_stock_diagnostic_output
"""
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_legacy_generate_markdown_report_wrapper_delegates_to_report_runtime(self):
        result = _run_legacy_entry_probe(
            """
import daily_report_entry_demo

with patch.object(daily_report_entry_demo, "render_markdown_report_runtime", return_value={"report": "# migrated"}) as runtime_mock:
    rendered = daily_report_entry_demo.generate_markdown_report({"foo": "bar"}, "2026-04-22")

assert runtime_mock.call_args[0][:2] == ({"foo": "bar"}, "2026-04-22")
assert "helpers" in runtime_mock.call_args.kwargs
assert rendered == "# migrated"
"""
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_render_markdown_report_runtime_returns_report_payload(self):
        with patch("report.runtime._render_markdown_report_legacy_body", return_value="# runtime report") as render_mock:
            result = report_runtime.render_markdown_report_runtime(
                {"foo": "bar"},
                "2026-04-22",
                helpers={"DISPLAY_MVP_MODE": False},
                config={},
            )

        render_mock.assert_called_once()
        self.assertEqual(result["report"], "# runtime report")

    def test_render_markdown_report_runtime_exposes_helper_bindings_to_legacy_body(self):
        exec(
            """
def _runtime_binding_probe(
    data,
    target_date,
    supplementary_perspective="",
    has_personal_positions=False,
    run_mode=LEDGER_MODE_FROZEN,
    persist_strategy_tracking=True,
):
    return runtime_test_helper(target_date)
""",
            report_runtime.__dict__,
        )

        with patch("report.runtime._render_markdown_report_legacy_body", report_runtime._runtime_binding_probe):
            result = report_runtime.render_markdown_report_runtime(
                {"foo": "bar"},
                "2026-04-22",
                helpers={"runtime_test_helper": lambda target_date: f"# Runtime Report {target_date}"},
                config={},
            )

        self.assertEqual(result["report"], "# Runtime Report 2026-04-22")

    def test_runtime_body_does_not_hand_append_report_copy(self):
        runtime_source = (ROOT / "scripts" / "report" / "runtime.py").read_text()
        non_empty_report_appends = [
            line.strip()
            for line in runtime_source.splitlines()
            if "report.append(" in line and 'report.append("")' not in line and "report.append('')" not in line
        ]

        self.assertEqual([], non_empty_report_appends)



if __name__ == "__main__":
    unittest.main()
