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


def _build_runtime_execution_test_helpers(run_registered_execution_stages, **overrides):
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
        "run_registered_execution_stages": run_registered_execution_stages,
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
        "_build_front_mainline_label": lambda *args, **kwargs: "",
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
        "run_report_tail_summary": lambda payload: {"value": {"lines": [], "module_logs": [], "exports": {}}},
        "run_strategy_performance_tail": lambda payload: {"value": {"lines": [], "module_logs": [], "exports": {}}},
        "run_execution_appendix_tail": lambda payload: {"value": {"lines": [], "module_logs": [], "exports": {}}},
    }
    helpers.update(overrides)
    return helpers


class ReportRuntimeTest(unittest.TestCase):
    def test_sanitize_report_lines_deduplicates_repeated_no_trade_action_lines(self):
        lines = [
            "## 八、详细附录",
            "**开盘前动作**: 先观察市场整体，不提前放松资格；未确认不开新仓",
            "其他内容",
            "**开盘前动作**: 先观察市场整体，不提前放松资格；未确认不开新仓",
        ]

        sanitized = report_runtime._sanitize_report_lines(lines)

        self.assertEqual(
            sanitized.count("**开盘前动作**: 先观察市场整体，不提前放松资格；未确认不开新仓"),
            1,
        )

    def test_demote_appendix_headings_demotes_legacy_top_level_title(self):
        lines = [
            "# 2026-04-24 A股日报",
            "## 旧二级标题",
            "### 旧三级标题",
            "### 附录B：历史主线池",
            "## 附录C：个股观察生命周期",
            "正文",
        ]

        demoted = report_runtime._demote_appendix_headings(lines)

        self.assertEqual(
            demoted,
            [
                "### 附录：2026-04-24 A股日报",
                "### 附录：旧二级标题",
                "#### 附录：旧三级标题",
                "#### 附录B：历史主线池",
                "### 附录C：个股观察生命周期",
                "正文",
            ],
        )
        self.assertFalse(any(line.startswith("# ") for line in demoted))

    def test_remove_duplicate_front_page_sections_from_appendix_renames_mirrored_headings(self):
        lines = [
            "## 一、交易纪律",
            "纪律明细",
            "## 三、周期与主线",
            "### 🔬 市场研究快照",
            "## 六、明日执行计划",
            "执行明细",
        ]

        cleaned = report_runtime._remove_duplicate_front_page_sections_from_appendix(lines)
        demoted = report_runtime._demote_appendix_headings(cleaned)

        self.assertIn("### 附录：交易纪律细则", demoted)
        self.assertIn("### 附录：周期与主线依据", demoted)
        self.assertIn("### 附录：执行计划依据", demoted)
        self.assertIn("#### 附录：🔬 市场研究快照", demoted)
        self.assertNotIn("### 附录：一、交易纪律", demoted)
        self.assertNotIn("### 附录：三、周期与主线", demoted)
        self.assertNotIn("### 附录：六、明日执行计划", demoted)

    def test_build_appendix_b_continuity_payload_marks_missing_turnover_share_pending(self):
        payload = report_runtime._build_appendix_b_continuity_payload(
            current_mainline_history_record={"date": "2026-04-24", "primary_mainline": "半导体"},
            current_sector_turnover_snapshot={
                "date": "2026-04-24",
                "sector_name": "半导体",
                "turnover_share_pct": 0.0,
                "source": "thsdk.market_data_block",
                "source_status": "missing_dependency",
                "source_error": "No module named 'thsdk'",
            },
        )

        row = payload["turnover_share_history"][0]
        self.assertEqual(row["mainline"], "半导体")
        self.assertEqual(row["turnover_share_pct"], "待累计")
        self.assertEqual(row["source"], "missing_dependency")

    def test_build_appendix_b_continuity_payload_enriches_structure_mainline_records(self):
        payload = report_runtime._build_appendix_b_continuity_payload(
            pivot_mainline_history=[
                {
                    "date_range": "2026-04-21 ~ 2026-04-24",
                    "pivot_range": "3992-4114",
                    "position": "中枢内",
                    "structure_state": "中枢内修复",
                    "mainline": "半导体",
                    "mainline_degree": "修复接力",
                    "evolution": "[半导体] 接替 [电力]",
                    "replacement": "接替前主线",
                    "interpretation": "[半导体] 在中枢内接替 [电力]，但还未进入攻击段",
                }
            ]
        )

        row = payload["structure_mainline_records"][0]
        self.assertEqual(row["date_range"], "2026-04-21 ~ 2026-04-24")
        self.assertEqual(row["pivot_range"], "3992-4114")
        self.assertEqual(row["position"], "中枢内")
        self.assertEqual(row["mainline"], "半导体")
        self.assertEqual(row["mainline_degree"], "修复接力")
        self.assertEqual(row["evolution"], "[半导体] 接替 [电力]")
        self.assertEqual(row["replacement"], "接替前主线")
        self.assertIn("还未进入攻击段", row["interpretation"])

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

        helpers = _build_runtime_execution_test_helpers(_capture_stage_context)

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

    def test_render_markdown_report_runtime_only_passes_unified_strategy_tail_renderer(self):
        class _StrategyTailCaptured(RuntimeError):
            pass

        def _run_execution_stages(stage_specs, stage_context=None, stage_lookup=None):
            return {"lines": [], "module_logs": [], "context": {}}

        def _capture_strategy_tail(payload):
            helpers = payload["helpers"]
            self.assertIn("render_strategy_performance_nodes", helpers)
            self.assertTrue(callable(helpers["render_strategy_performance_nodes"]))
            self.assertNotIn("append_strategy_performance_section", helpers)
            raise _StrategyTailCaptured("captured")

        helpers = _build_runtime_execution_test_helpers(
            _run_execution_stages,
            run_report_tail_summary=lambda payload: {"value": {"lines": [], "module_logs": [], "exports": {}}},
            run_strategy_performance_tail=_capture_strategy_tail,
            build_legacy_final_conclusion_lines=lambda *args, **kwargs: [],
            render_mainline_discipline_section=lambda *args, **kwargs: [],
            render_supplementary_perspective_section=lambda *args, **kwargs: [],
            render_ai_market_insight_section=lambda *args, **kwargs: [],
            _build_strategy_factor_snapshot=lambda *args, **kwargs: {},
            _build_strategy_plan_context=lambda *args, **kwargs: {},
            update_strategy_performance_book=lambda *args, **kwargs: {},
            render_strategy_performance_nodes=lambda *args, **kwargs: {"lines": [], "summary": {}},
            append_strategy_performance_section=lambda *args, **kwargs: None,
        )

        with self.assertRaises(_StrategyTailCaptured):
            report_runtime.render_markdown_report_runtime(
                {"exchange_monitor_today": [], "exchange_monitor_nextday": []},
                "2026-04-22",
                helpers=helpers,
                config={},
            )

    def test_render_markdown_report_runtime_only_passes_live_tail_summary_renderers(self):
        class _TailSummaryCaptured(RuntimeError):
            pass

        def _run_execution_stages(stage_specs, stage_context=None, stage_lookup=None):
            return {"lines": [], "module_logs": [], "context": {}}

        def _capture_tail_summary(payload):
            helpers = payload["helpers"]
            self.assertIn("render_context_tail_sections", helpers)
            self.assertTrue(callable(helpers["render_context_tail_sections"]))
            self.assertNotIn("render_mainline_discipline_section", helpers)
            self.assertIn("render_supplementary_perspective_section", helpers)
            self.assertIn("render_ai_market_insight_section", helpers)
            raise _TailSummaryCaptured("captured")

        helpers = _build_runtime_execution_test_helpers(
            _run_execution_stages,
            run_report_tail_summary=_capture_tail_summary,
            build_legacy_final_conclusion_lines=lambda *args, **kwargs: [],
            render_context_tail_sections=lambda *args, **kwargs: [],
            render_mainline_discipline_section=lambda *args, **kwargs: [],
            render_supplementary_perspective_section=lambda *args, **kwargs: [],
            render_ai_market_insight_section=lambda *args, **kwargs: [],
        )

        with self.assertRaises(_TailSummaryCaptured):
            report_runtime.render_markdown_report_runtime(
                {"exchange_monitor_today": [], "exchange_monitor_nextday": []},
                "2026-04-22",
                helpers=helpers,
                config={},
            )

    def test_render_markdown_report_runtime_passes_mainline_turnover_atoms_into_tail_summary(self):
        class _TailSummaryCaptured(RuntimeError):
            pass

        def _run_execution_stages(stage_specs, stage_context=None, stage_lookup=None):
            return {
                "lines": [],
                "module_logs": [],
                "context": {
                    "mainline_name": "通信",
                    "market_research_snapshot": {
                        "state_machine": {"leading_line": "通信"},
                        "mainline_turnover_summary": {
                            "conclusion": "主线未切换，通信仍是中心",
                            "data_text": "最近3日主线 通信 -> 通信 -> 通信；成交额占比 12.4% -> 15.8% -> 18.1%",
                            "action_text": "继续围绕通信做减法",
                        },
                    },
                    "market_state_snapshot": {"leading_line": "通信"},
                    "current_mainline_history_record": {"date": "2026-04-24", "primary_mainline": "通信"},
                    "recent_mainline_history": [
                        {"date": "2026-04-22", "primary_mainline": "通信"},
                        {"date": "2026-04-23", "primary_mainline": "通信"},
                    ],
                    "current_sector_turnover_snapshot": {
                        "date": "2026-04-24",
                        "sector_name": "通信",
                        "turnover_share_pct": 18.1,
                    },
                    "recent_sector_turnover_history": [
                        {"date": "2026-04-22", "sector_name": "通信", "turnover_share_pct": 12.4},
                        {"date": "2026-04-23", "sector_name": "通信", "turnover_share_pct": 15.8},
                    ],
                    "mainline_turnover_summary": {
                        "conclusion": "主线未切换，通信仍是中心",
                        "data_text": "最近3日主线 通信 -> 通信 -> 通信；成交额占比 12.4% -> 15.8% -> 18.1%",
                        "action_text": "继续围绕通信做减法",
                    },
                },
            }

        def _capture_tail_summary(payload):
            inputs = payload["inputs"]
            self.assertEqual(inputs["current_mainline_history_record"]["primary_mainline"], "通信")
            self.assertEqual(inputs["current_sector_turnover_snapshot"]["turnover_share_pct"], 18.1)
            self.assertEqual(inputs["mainline_turnover_summary"]["conclusion"], "主线未切换，通信仍是中心")
            raise _TailSummaryCaptured("captured")

        helpers = _build_runtime_execution_test_helpers(
            _run_execution_stages,
            run_report_tail_summary=_capture_tail_summary,
            build_legacy_final_conclusion_lines=lambda *args, **kwargs: [],
            render_context_tail_sections=lambda *args, **kwargs: [],
            render_supplementary_perspective_section=lambda *args, **kwargs: [],
            render_ai_market_insight_section=lambda *args, **kwargs: [],
        )

        with self.assertRaises(_TailSummaryCaptured):
            report_runtime.render_markdown_report_runtime(
                {"exchange_monitor_today": [], "exchange_monitor_nextday": []},
                "2026-04-22",
                helpers=helpers,
                config={},
            )

    def test_render_markdown_report_runtime_derives_appendix_continuity_inputs(self):
        class _ExecutionAppendixCaptured(RuntimeError):
            pass

        def _run_execution_stages(stage_specs, stage_context=None, stage_lookup=None):
            return {
                "lines": [],
                "module_logs": [],
                "context": {
                    "current_mainline_history_record": {
                        "date": "2026-04-24",
                        "primary_mainline": "半导体",
                        "rotation_summary": "[半导体] 接替 [电力]，但仍需放量确认",
                    },
                    "recent_mainline_history": [
                        {"date": "2026-04-22", "primary_mainline": "电力", "market_state": "强化"},
                        {"date": "2026-04-23", "primary_mainline": "电力", "market_state": "退潮"},
                    ],
                    "current_sector_turnover_snapshot": {
                        "date": "2026-04-24",
                        "sector_name": "半导体",
                        "turnover_share_pct": 18.1,
                        "source": "thsdk.market_data_block",
                    },
                    "recent_sector_turnover_history": [
                        {"date": "2026-04-23", "sector_name": "电力", "turnover_share_pct": 15.8, "source": "历史记录"},
                    ],
                    "pivot_mainline_history": [
                        {
                            "date_range": "2026-04-21 ~ 2026-04-24",
                            "pivot_level": "小中枢",
                            "pivot_range": "3992-4114",
                            "mainline": "半导体",
                            "mainline_degree": "小周期主线",
                            "interpretation": "[半导体] 在中枢内接替 [电力]",
                        }
                    ],
                    "core_stocks": [
                        {"name": "富瀚微", "code": "300613", "sector": "半导体", "abnormal_summary": "主线内强度靠前", "current_action": "继续跟踪"},
                    ],
                    "crossline_observation_stocks": [
                        {"name": "恩捷股份", "code": "002812", "sector": "电池", "abnormal_summary": "资金外溢观察"},
                    ],
                    "active_a_kill_records": [
                        {"name": "冷却股", "code": "000003", "a_kill_date": "2026-04-24", "reason": "A杀冷却"},
                    ],
                },
            }

        def _capture_execution_appendix(payload):
            inputs = payload["inputs"]
            appendix_b = inputs["appendix_b"]
            appendix_c = inputs["appendix_c"]
            self.assertEqual(appendix_b["historical_mainline_pool"][-1]["mainline"], "半导体")
            self.assertEqual(appendix_b["mainline_switch_log"][0]["from_mainline"], "电力")
            self.assertEqual(appendix_b["mainline_switch_log"][0]["to_mainline"], "半导体")
            self.assertEqual(appendix_b["turnover_share_history"][-1]["mainline"], "半导体")
            self.assertEqual(appendix_b["turnover_share_history"][-1]["turnover_share_pct"], "18.10%")
            self.assertEqual(appendix_b["structure_mainline_records"][0]["mainline"], "半导体")
            self.assertEqual(appendix_b["structure_mainline_records"][0]["pivot_level"], "小中枢")
            self.assertEqual(appendix_b["structure_mainline_records"][0]["mainline_degree"], "小周期主线")
            self.assertEqual(appendix_c["current_stock_monitoring_pool"][0]["stock_name"], "富瀚微")
            self.assertEqual(appendix_c["current_stock_monitoring_pool"][1]["source_pool"], "跨线观察")
            lifecycle = appendix_c["stock_lifecycle_records"][0]
            self.assertEqual(lifecycle["source_report_date"], "2026-04-24")
            self.assertEqual(lifecycle["tracked_trading_days"], 1)
            self.assertEqual(lifecycle["current_interpretation"], "主线内强度靠前")
            self.assertEqual(appendix_c["a_kill_elimination_records"][0]["stock_code"], "000003")
            entry_cycle = inputs["entry_cycle_calibration"]
            self.assertEqual(entry_cycle["cases"][0]["name"], "中嘉博创")
            self.assertEqual(entry_cycle["cases"][0]["recommended_stop_mode"], "structure_repair_band")
            raise _ExecutionAppendixCaptured("captured")

        helpers = _build_runtime_execution_test_helpers(
            _run_execution_stages,
            build_legacy_final_conclusion_lines=lambda *args, **kwargs: [],
            render_context_tail_sections=lambda *args, **kwargs: [],
            render_supplementary_perspective_section=lambda *args, **kwargs: [],
            render_ai_market_insight_section=lambda *args, **kwargs: [],
            _build_strategy_factor_snapshot=lambda *args, **kwargs: {},
            _build_strategy_plan_context=lambda *args, **kwargs: {},
            update_strategy_performance_book=lambda *args, **kwargs: {},
            _normalize_report_timer_steps=lambda *args, **kwargs: [],
            render_execution_appendix=lambda *args, **kwargs: [],
            run_execution_appendix_tail=_capture_execution_appendix,
            _default_build_entry_cycle_calibrations=lambda as_of_date="": {
                "as_of_date": as_of_date,
                "cases": [
                    {
                        "name": "中嘉博创",
                        "code": "000889",
                        "recommended_stop_mode": "structure_repair_band",
                    }
                ],
            },
        )

        data = {
            "exchange_monitor_today": [],
            "exchange_monitor_nextday": [],
            "appendix_b": {
                "historical_mainline_pool": [],
                "mainline_switch_log": [],
                "turnover_share_history": [],
                "structure_mainline_records": [],
            },
        }

        with self.assertRaises(_ExecutionAppendixCaptured):
            report_runtime.render_markdown_report_runtime(
                data,
                "2026-04-24",
                helpers=helpers,
                config={},
            )

    def test_render_markdown_report_runtime_derives_appendix_structure_mainline_from_market_snapshot(self):
        class _ExecutionAppendixCaptured(RuntimeError):
            pass

        def _run_execution_stages(stage_specs, stage_context=None, stage_lookup=None):
            return {
                "lines": [],
                "module_logs": [],
                "context": {
                    "market_research_snapshot": {
                        "state_machine": {
                            "leading_line": "半导体",
                            "energy_state": "收缩防守",
                        },
                        "recent_mainline_history": [
                            {"date": "2026-04-23", "primary_mainline": "电力", "market_state": "退潮"},
                        ],
                        "current_mainline_history_record": {
                            "date": "2026-04-24",
                            "primary_mainline": "半导体",
                            "market_state": "收缩防守",
                        },
                        "pivot_range": "3992-4114",
                        "pivot_position": "中枢内",
                        "pivot_level": "小中枢",
                    },
                },
            }

        def _capture_execution_appendix(payload):
            records = payload["inputs"]["appendix_b"]["structure_mainline_records"]
            self.assertTrue(records, "附录B必须从结构化市场快照派生中枢-主线记录")
            self.assertEqual(records[0]["date_range"], "04-24")
            self.assertEqual(records[0]["pivot_level"], "小中枢")
            self.assertEqual(records[0]["pivot_range"], "3992-4114")
            self.assertEqual(records[0]["position"], "中枢内")
            self.assertEqual(records[0]["mainline"], "半导体")
            self.assertEqual(records[0]["mainline_degree"], "小周期主线")
            self.assertEqual(records[0]["evolution"], "收缩防守")
            self.assertEqual(records[0]["replacement"], "接替电力")
            self.assertIn("[半导体]", records[0]["interpretation"])
            raise _ExecutionAppendixCaptured("captured")

        helpers = _build_runtime_execution_test_helpers(
            _run_execution_stages,
            build_legacy_final_conclusion_lines=lambda *args, **kwargs: [],
            render_context_tail_sections=lambda *args, **kwargs: [],
            render_supplementary_perspective_section=lambda *args, **kwargs: [],
            render_ai_market_insight_section=lambda *args, **kwargs: [],
            _build_strategy_factor_snapshot=lambda *args, **kwargs: {},
            _build_strategy_plan_context=lambda *args, **kwargs: {},
            update_strategy_performance_book=lambda *args, **kwargs: {},
            _normalize_report_timer_steps=lambda *args, **kwargs: [],
            render_execution_appendix=lambda *args, **kwargs: [],
            run_execution_appendix_tail=_capture_execution_appendix,
        )

        data = {
            "exchange_monitor_today": [],
            "exchange_monitor_nextday": [],
            "appendix_b": {
                "historical_mainline_pool": [],
                "mainline_switch_log": [],
                "turnover_share_history": [],
                "structure_mainline_records": [],
            },
        }

        with self.assertRaises(_ExecutionAppendixCaptured):
            report_runtime.render_markdown_report_runtime(
                data,
                "2026-04-24",
                helpers=helpers,
                config={},
            )



    def test_render_markdown_report_runtime_summary_matches_final_front_page_sketch(self):
        from report.report_document_builder import (
            build_report_shell_contract as _build_report_shell_contract_actual,
            replace_placeholder_lines as _replace_placeholder_lines_actual,
        )

        def _run_execution_stages(stage_specs, stage_context=None, stage_lookup=None):
            return {
                "lines": [
                    "#### Step 0 - 明日环境与跟随裁决",
                    "### 🔬 市场研究快照",
                    "> **Step 0 结论**: 旧结构不应进入执行摘要",
                    "| 股票 | 代码 | 所属方向 | 标志性大阳线 | 近5日状态 | 承接 | 资金痕迹 | 明日资格 |",
                    "| 富瀚微 | 300613 | 半导体 | 放量涨停 | 未完全爆发 | 09:50-10:10看承接 | 周期主线内辨识度较高 | 仅观察 |",
                    "| 股票 | 代码 | 所属方向 | 观察意义 | 明日原则 |",
                    "| 恩捷股份 | 002812 | 电池 | 龙虎榜资金外溢观察 | 只看强弱，不给买入指令 |",
                ],
                "module_logs": [],
                "context": {
                    "market_research_snapshot": {
                        "cycle_calendar_rows": [
                            {"week_label": "当前周期", "monday": {"mainline": "半导体", "state": "接力"}},
                        ],
                        "cycle_interpretation_rows": [
                            {"cycle_label": "当前周期", "date_range": "2026-04-20 ~ 2026-04-24", "trading_days": "5日", "mainline": "半导体", "market_state": "修复接力", "interpretation": "[半导体] 开始接替 [电力]，但还需要承接确认"},
                        ],
                        "pivot_mainline_rows": [
                            {"date_range": "2026-04-20 ~ 2026-04-24", "pivot_range": "3992-4114", "position": "中枢内", "structure_state": "中枢内修复", "mainline": "半导体", "interpretation": "[半导体] 在中枢内接替 [电力]，但还未进入攻击段"},
                        ],
                        "mainline_turnover_summary": {
                            "conclusion": "主线未切换，半导体仍是中心",
                            "action_text": "只看主线核心承接",
                            "double_mainline_summary": {"cycle_mainline": "半导体", "daily_attack_line": "半导体", "relationship": "当天主攻线仍在周期主线内", "tomorrow_action": "10点确认承接"},
                            "turnover_share_trend_rows": [
                                {"date": "2026-04-24", "cycle_mainline": "半导体", "daily_attack_line": "半导体", "mainline_turnover": "数据暂缺", "market_turnover": "26414.92亿", "share": "待累计", "share_change": "待累计", "interpretation": "缺少板块成交额接口，先记录主线归属"},
                            ],
                        },
                        "lhb_capital_status": {"capital_strength": "强", "capital_intensity": "净买入集中", "capital_direction": "电池", "capital_intent": "轮动试探", "style_shift": "资金偏轮动", "event_attribute": "龙虎榜资金行为"},
                        "capital_conclusion": {"current_capital_state": "龙虎榜资金强", "mainline_attitude": "尚未确认主线", "tomorrow_action_meaning": "先观察是否回到主线"},
                    },
                },
            }

        helpers = _build_runtime_execution_test_helpers(
            _run_execution_stages,
            DISPLAY_MVP_MODE=True,
            build_report_shell_contract=_build_report_shell_contract_actual,
            replace_placeholder_lines=_replace_placeholder_lines_actual,
            build_market_trend_sections_contract=lambda *args, **kwargs: {
                "lines": [
                    "## 二、市场基底",
                    "### 1. 指数与市场底色",
                    "| 指标 | 数值 | 涨跌幅 | 解读 |",
                    "| 上证指数 | 4079.90 | -0.33% | 震荡调整 |",
                    "### 2. 市场状态结论",
                    "| 项目 | 结论 |",
                    "| 市场状态 | 收缩防守 |",
                ]
            },
            build_legacy_final_conclusion_lines=lambda *args, **kwargs: [],
            render_supplementary_perspective_section=lambda *args, **kwargs: [],
            render_ai_market_insight_section=lambda *args, **kwargs: [],
            _build_strategy_factor_snapshot=lambda *args, **kwargs: {},
            _build_strategy_plan_context=lambda *args, **kwargs: {},
            update_strategy_performance_book=lambda *args, **kwargs: {},
            _normalize_report_timer_steps=lambda *args, **kwargs: [],
            render_execution_appendix=lambda *args, **kwargs: [],
            run_report_tail_summary=lambda payload: {"value": {"lines": ["#### 最终结论", "| 项目 | 明日指引 |", "| 明日大盘预期 | 空仓等待 |", "| 当前盈亏比 | 不值得主动参与 |", "| 操作风格 | 空仓 |"], "module_logs": [], "exports": {}}},
            run_strategy_performance_tail=lambda payload: {"value": {"lines": [], "module_logs": [], "exports": {}}},
            run_execution_appendix_tail=lambda payload: {"value": {"lines": [], "module_logs": [], "exports": {}}},
            _compact_report_for_mvp=lambda report, stage_lookup=None: report,
        )

        result = report_runtime.render_markdown_report_runtime(
            {"exchange_monitor_today": [], "exchange_monitor_nextday": []},
            "2026-04-24",
            helpers=helpers,
            config={},
        )
        rendered = result["report"]
        required_order = [
            "## 一、交易纪律",
            "## 二、市场基底",
            "## 三、周期与主线",
            "## 四、资金意图",
            "## 五、个股解读",
            "## 六、明日执行计划",
            "## 七、最终结论",
        ]
        positions = [rendered.index(marker) for marker in required_order]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("| 明日结论 | 默认节奏 | 尾盘例外 | 最大风险 | 核心纪律 |", rendered)
        self.assertIn("### 1. 周期日历主视图", rendered)
        self.assertIn("[半导体] 接力", rendered)
        self.assertIn("### 4. 双层主线结论", rendered)
        self.assertIn("### 5. 主线成交额占比趋势", rendered)
        self.assertIn("### 1. 龙虎榜资金状态", rendered)
        self.assertIn("### 1. 主线内观察候选", rendered)
        self.assertNotIn("### 1. 主线内可执行候选", rendered)
        self.assertIn("### 2. 跨线观察候选", rendered)
        self.assertIn("| 时间窗口 | 要看什么 | 买入权限 | 卖出/风控 | 结论 |", rendered)
        self.assertNotIn("### 🔬 市场研究快照", rendered)
        self.assertNotIn("Step 0", rendered)

    def test_render_markdown_report_runtime_full_report_starts_with_final_front_page_sketch(self):
        from report.report_document_builder import (
            build_report_shell_contract as _build_report_shell_contract_actual,
            replace_placeholder_lines as _replace_placeholder_lines_actual,
        )

        def _run_execution_stages(stage_specs, stage_context=None, stage_lookup=None):
            return {
                "lines": [
                    "#### Step 0 - 明日环境与跟随裁决",
                    "### 🔬 市场研究快照",
                    "> **Step 0 结论**: 旧结构只能进附录，不能进首页",
                    "| 股票 | 代码 | 所属方向 | 标志性大阳线 | 近5日状态 | 承接 | 资金痕迹 | 明日资格 |",
                    "| 富瀚微 | 300613 | 半导体 | 放量涨停 | 未完全爆发 | 10:00前看承接 | 主线内强度靠前 | 有 |",
                    "| 股票 | 代码 | 所属方向 | 观察意义 | 明日原则 |",
                    "| 恩捷股份 | 002812 | 电池 | 资金外溢观察 | 只看强弱，不给买入指令 |",
                ],
                "module_logs": [],
                "context": {
                    "market_research_snapshot": {
                        "cycle_calendar_rows": [
                            {"week_label": "当前周期", "monday": {"mainline": "半导体", "state": "接力"}},
                        ],
                        "cycle_interpretation_rows": [
                            {"cycle_label": "当前周期", "date_range": "2026-04-20 ~ 2026-04-24", "trading_days": "5日", "mainline": "半导体", "market_state": "修复接力", "interpretation": "[半导体] 接替旧主线，等待放量确认"},
                        ],
                        "pivot_mainline_rows": [
                            {"date_range": "2026-04-20 ~ 2026-04-24", "pivot_range": "3992-4114", "position": "中枢内", "structure_state": "中枢内修复", "mainline": "半导体", "interpretation": "[半导体] 在中枢内接替旧主线"},
                        ],
                        "mainline_turnover_summary": {
                            "current_mainline": "半导体",
                            "double_mainline_summary": {"cycle_mainline": "半导体", "daily_attack_line": "半导体", "relationship": "周期主线与当天主攻线一致", "tomorrow_action": "继续围绕半导体观察承接"},
                            "turnover_share_trend_rows": [
                                {"date": "2026-04-24", "cycle_mainline": "半导体", "daily_attack_line": "半导体", "mainline_turnover": "数据暂缺", "market_turnover": "26414.92亿", "share": "待累计", "share_change": "待累计", "interpretation": "缺少板块成交额接口，先记录主线归属"},
                            ],
                        },
                        "lhb_capital_status": {"capital_strength": "强", "capital_intensity": "净买入集中", "capital_direction": "电池", "capital_intent": "轮动试探", "style_shift": "资金偏轮动", "event_attribute": "龙虎榜资金行为"},
                        "capital_conclusion": {"current_capital_state": "龙虎榜资金强", "mainline_attitude": "尚未确认主线", "tomorrow_action_meaning": "先观察是否回到主线"},
                    },
                },
            }

        helpers = _build_runtime_execution_test_helpers(
            _run_execution_stages,
            DISPLAY_MVP_MODE=False,
            build_report_shell_contract=_build_report_shell_contract_actual,
            replace_placeholder_lines=_replace_placeholder_lines_actual,
            build_market_trend_sections_contract=lambda *args, **kwargs: {
                "lines": [
                    "## 二、市场基底",
                    "### 1. 指数与市场底色",
                    "| 指标 | 数值 | 涨跌幅 | 解读 |",
                    "| 上证指数 | 4079.90 | -0.33% | 震荡调整 |",
                    "### 2. 市场状态结论",
                    "| 项目 | 结论 |",
                    "| 市场状态 | 收缩防守 |",
                ]
            },
            build_legacy_final_conclusion_lines=lambda *args, **kwargs: [],
            render_supplementary_perspective_section=lambda *args, **kwargs: [],
            render_ai_market_insight_section=lambda *args, **kwargs: [],
            _build_strategy_factor_snapshot=lambda *args, **kwargs: {},
            _build_strategy_plan_context=lambda *args, **kwargs: {},
            update_strategy_performance_book=lambda *args, **kwargs: {},
            _normalize_report_timer_steps=lambda *args, **kwargs: [],
            render_execution_appendix=lambda *args, **kwargs: [],
            run_report_tail_summary=lambda payload: {"value": {"lines": ["#### 最终结论", "| 项目 | 明日指引 |", "| 明日大盘预期 | 空仓等待 |"], "module_logs": [], "exports": {}}},
            run_strategy_performance_tail=lambda payload: {"value": {"lines": [], "module_logs": [], "exports": {}}},
            run_execution_appendix_tail=lambda payload: {"value": {"lines": [], "module_logs": [], "exports": {}}},
        )

        result = report_runtime.render_markdown_report_runtime(
            {"exchange_monitor_today": [], "exchange_monitor_nextday": []},
            "2026-04-24",
            helpers=helpers,
            config={},
        )
        rendered = result["report"]
        front_page = rendered.split("## 八、详细附录", 1)[0]

        self.assertTrue(rendered.startswith("# 2026-04-24 a股市场分析"))
        self.assertIn("## 一、交易纪律", front_page)
        self.assertNotIn("A股狙击手作战简报", front_page)
        self.assertNotIn("## 一、作战纪律", front_page)
        self.assertIn("## 七、最终结论", front_page)
        self.assertIn("### 5. 主线成交额占比趋势", front_page)
        self.assertIn("### 1. 龙虎榜资金状态", front_page)
        self.assertIn("| 时间窗口 | 要看什么 | 买入权限 | 卖出/风控 | 结论 |", front_page)
        self.assertNotIn("### 🔬 市场研究快照", front_page)
        self.assertNotIn("Step 0", front_page)
        self.assertIn("## 八、详细附录", rendered)
        appendix = rendered.split("## 八、详细附录", 1)[1]
        self.assertIn("#### 附录：🔬 市场研究快照", appendix)
        self.assertNotIn("### 附录：二、市场基底", appendix)
        self.assertNotIn("#### 附录：1. 指数与市场底色", appendix)
        top_headings = [line for line in rendered.splitlines() if line.startswith("# ")]
        self.assertEqual(top_headings, ["# 2026-04-24 a股市场分析"])
        self.assertNotIn("# 2026-04-24 A股日报", appendix)

    def test_render_markdown_report_runtime_replaces_front_page_node_placeholders(self):
        from report.report_document_builder import (
            build_report_shell_contract as _build_report_shell_contract_actual,
            replace_placeholder_lines as _replace_placeholder_lines_actual,
        )

        def _run_execution_stages(stage_specs, stage_context=None, stage_lookup=None):
            return {
                "lines": [
                    "| 股票 | 代码 | 所属方向 | 标志性大阳线 | 近5日状态 | 承接 | 资金痕迹 | 明日资格 |",
                    "| 富瀚微 | 300613 | 半导体 | 放量涨停 | 未完全爆发 | 10:00前看承接 | 主线内强度靠前 | 有 |",
                ],
                "module_logs": [],
                "context": {
                    "core_mvp_digest_lines": ["- **先说结论**: 只看主线内强票"],
                    "mvp_focus_summary_lines": ["- **主线研究对象**: 富瀚微"],
                    "market_research_snapshot": {
                        "cycle_calendar": {
                            "weeks": [[{"date": "2026-04-24", "label": "周五", "sector": "半导体", "state": "修复"}]],
                        },
                        "cycle_interpretation": [{"conclusion": "半导体替代低空经济", "evidence": "成交额占比抬升", "action": "只做主线"}],
                        "pivot_mainline_interpretation": [{"segment": "2026-04-20至2026-04-24", "mainline": "半导体", "interpretation": "半导体承接指数中枢修复"}],
                        "lhb_capital_status": [{"direction": "半导体", "state": "资金增强", "strength": "强", "intent": "接力主线", "style": "游资+机构"}],
                        "capital_conclusion": [{"conclusion": "资金仍在主线内", "evidence": "龙虎榜净买入集中", "action": "不追支线"}],
                    },
                },
            }

        helpers = _build_runtime_execution_test_helpers(
            _run_execution_stages,
            build_report_shell_contract=_build_report_shell_contract_actual,
            replace_placeholder_lines=_replace_placeholder_lines_actual,
            build_market_trend_sections_contract=lambda *args, **kwargs: {
                "lines": ["## 二、市场基底", "### 1. 指数与市场底色", "| 指数 | 涨跌幅 | 结论 |", "| 上证指数 | +0.80% | 修复 |"]
            },
            build_legacy_final_conclusion_lines=lambda *args, **kwargs: [],
            render_supplementary_perspective_section=lambda *args, **kwargs: [],
            render_ai_market_insight_section=lambda *args, **kwargs: [],
            _build_strategy_factor_snapshot=lambda *args, **kwargs: {},
            _build_strategy_plan_context=lambda *args, **kwargs: {},
            update_strategy_performance_book=lambda *args, **kwargs: {},
            _normalize_report_timer_steps=lambda *args, **kwargs: [],
            render_execution_appendix=lambda *args, **kwargs: ["## 附录C：个股观察生命周期", "| 股票 | 来自哪天日报 | 当前处理 |"],
            _compact_report_for_mvp=lambda report, stage_lookup=None: report,
            run_report_tail_summary=lambda payload: {"value": {"lines": ["### 最终结论", "| 事项 | 结论 |", "| 明日动作 | 10:00看承接 |"], "module_logs": [], "exports": {}}},
            run_strategy_performance_tail=lambda payload: {"value": {"lines": [], "module_logs": [], "exports": {}}},
            run_execution_appendix_tail=lambda payload: {"value": {"lines": ["## 附录C：个股观察生命周期", "| 股票 | 来自哪天日报 | 当前处理 |"], "module_logs": [], "exports": {}}},
            _render_market_research_snapshot_section=lambda snapshot, compact=False: [
                "### 周期日历主视图",
                "| 日期 | 周五 |",
                "| 2026-04-24 | [半导体] 修复 |",
                "### 周期解读",
                "| 结论 | 依据 | 动作 |",
                "| 半导体替代低空经济 | 成交额占比抬升 | 只做主线 |",
                "### 龙虎榜资金状态",
                "| 方向 | 状态 | 力度 | 意图 | 风格 |",
                "| 半导体 | 资金增强 | 强 | 接力主线 | 游资+机构 |",
            ],
            _render_step0_follow_section=lambda plan, snapshot, compact=False: ["### 明日执行计划", "| 时间 | 动作 |", "| 10:00 | 看承接 |"],
        )

        result = report_runtime.render_markdown_report_runtime(
            {"exchange_monitor_today": [], "exchange_monitor_nextday": []},
            "2026-04-24",
            helpers=helpers,
            config={},
        )
        rendered = result["report"]

        for placeholder in (
            "FRONT_PAGE_",
            "MARKET_RESEARCH_SNAPSHOT_PLACEHOLDER",
            "STEP0_FOLLOW_PLACEHOLDER",
            "PROHIBITION_PLACEHOLDER",
        ):
            self.assertNotIn(placeholder, rendered)
        self.assertEqual(rendered.count("## 二、市场基底"), 1)
        self.assertIn("### 1. 指数与市场底色", rendered)
        self.assertIn("[半导体] 修复", rendered)
        self.assertIn("### 1. 龙虎榜资金状态", rendered)
        self.assertIn("| 股票 | 代码 | 所属方向 | 标志性大阳线 | 近5日状态 | 承接 | 资金痕迹 | 明日资格 |", rendered)
        self.assertIn("### 附录C：个股观察生命周期", rendered)
        self.assertNotIn("附录：附录C", rendered)

    def test_render_markdown_report_runtime_renders_mainline_turnover_text_in_full_and_summary(self):
        from report.front_summary_renderer import render_front_digest as _render_front_digest_actual
        from report.front_summary_support import render_core_mvp_digest as _render_core_mvp_digest_actual
        from report.report_document_builder import (
            build_report_shell_contract as _build_report_shell_contract_actual,
            replace_placeholder_lines as _replace_placeholder_lines_actual,
        )

        def _run_execution_stages(stage_specs, stage_context=None, stage_lookup=None):
            market_research_snapshot = {
                "observation": {},
                "style_switch": {"style_label": "主线抱团", "high_board_count": 2},
                "state_machine": {"leading_line": "通信", "energy_state": "修复", "state_reason": "主线回流"},
                "follow_verdict": {"label": "🟢 跟随主线"},
                "dialectical_decision": {"stage_label": "主升", "stage_action": "继续跟随"},
                "mainline_turnover_summary": {
                    "conclusion": "主线未切换，通信仍是中心",
                    "data_text": "最近3日主线 通信 -> 通信 -> 通信；成交额占比 12.4% -> 15.8% -> 18.1%，节奏偏强化",
                    "action_text": "继续围绕通信做减法",
                    "double_mainline_summary": {
                        "cycle_mainline": "通信",
                        "daily_attack_line": "通信",
                        "relationship": "当天主攻线仍在周期主线内",
                        "tomorrow_action": "继续围绕通信做减法",
                    },
                    "turnover_share_trend_rows": [
                        {
                            "date": "2026-04-24",
                            "cycle_mainline": "通信",
                            "daily_attack_line": "通信",
                            "mainline_turnover": "2180.00亿",
                            "market_turnover": "12834.00亿",
                            "share": "18.1%",
                            "share_change": "+2.3pct",
                            "interpretation": "主线占比继续抬升，节奏偏强化",
                        }
                    ],
                },
            }
            digest_lines = stage_context["render_core_mvp_digest"](
                market_research_snapshot,
                final_gate={"can_new_entry": True, "final_action": "只做核心"},
                position_level="三档（进攻档）",
                position_reason="环境修复",
                exit_analysis={"sector_name": "通信", "overall_level": "黄灯"},
                execution_framework_text="等60分钟确认",
                high_board_count=3,
                structure_layer_text="结构层通过",
                front_follow_action_text="只做核心",
                compact=bool(stage_context.get("display_mvp_mode")),
            )
            return {
                "lines": [] if stage_context.get("display_mvp_mode") else list(digest_lines),
                "module_logs": [],
                "context": {
                    "market_research_snapshot": market_research_snapshot,
                    "core_mvp_digest_lines": digest_lines,
                    "mvp_focus_summary_lines": [],
                },
            }

        def _empty_value_result(payload):
            return {"value": {"lines": [], "module_logs": [], "exports": {}}}

        helpers = _build_runtime_execution_test_helpers(
            _run_execution_stages,
            build_report_shell_contract=_build_report_shell_contract_actual,
            replace_placeholder_lines=_replace_placeholder_lines_actual,
            _render_core_mvp_digest=_render_core_mvp_digest_actual,
            render_front_digest=_render_front_digest_actual,
            build_legacy_final_conclusion_lines=lambda *args, **kwargs: [],
            render_supplementary_perspective_section=lambda *args, **kwargs: [],
            render_ai_market_insight_section=lambda *args, **kwargs: [],
            _build_strategy_factor_snapshot=lambda *args, **kwargs: {},
            _build_strategy_plan_context=lambda *args, **kwargs: {},
            update_strategy_performance_book=lambda *args, **kwargs: {},
            _normalize_report_timer_steps=lambda *args, **kwargs: [],
            render_execution_appendix=lambda *args, **kwargs: [],
            _compact_report_for_mvp=lambda report, stage_lookup=None: report,
            run_report_tail_summary=_empty_value_result,
            run_strategy_performance_tail=_empty_value_result,
            run_execution_appendix_tail=_empty_value_result,
        )

        full_result = report_runtime.render_markdown_report_runtime(
            {"exchange_monitor_today": [], "exchange_monitor_nextday": []},
            "2026-04-22",
            helpers=helpers,
            config={},
        )

        summary_helpers = dict(helpers)
        summary_helpers["DISPLAY_MVP_MODE"] = True
        summary_result = report_runtime.render_markdown_report_runtime(
            {"exchange_monitor_today": [], "exchange_monitor_nextday": []},
            "2026-04-22",
            helpers=summary_helpers,
            config={},
        )

        expected_line = (
            "- **主线更替与占比**: 主线未切换，通信仍是中心；最近3日主线 通信 -> 通信 -> 通信；"
            "成交额占比 12.4% -> 15.8% -> 18.1%，节奏偏强化"
        )
        self.assertIn(expected_line, full_result["report"])
        self.assertIn("### 5. 主线成交额占比趋势", summary_result["report"])
        self.assertIn("### 1. 周期日历主视图", summary_result["report"])
        self.assertIn("| 周次 | 一 | 二 | 三 | 四 | 五 |", summary_result["report"])
        self.assertIn("### 2. 周期解读", summary_result["report"])
        self.assertIn("| 周期 | 时间段 | 交易日数 | 主导主线 | 市场状态 | 周期解读 |", summary_result["report"])
        self.assertIn("### 3. 中枢与主线解读", summary_result["report"])
        self.assertIn("| 时间段 | 中枢级别 | 中枢区间 | 所在位置 | 对应主线 | 主线程度 | 演化状态 | 接替关系 | 结构解读 |", summary_result["report"])
        self.assertIn(
            "| 日期 | 周期主线 | 当天主攻线 | 主线成交额 | 两市成交额 | 占比 | 占比变化 | 解读 |",
            summary_result["report"],
        )
        self.assertIn(
            "| 2026-04-24 | 通信 | 通信 | 2180.00亿 | 12834.00亿 | 18.1% | +2.3pct | 主线占比继续抬升，节奏偏强化 |",
            summary_result["report"],
        )
        self.assertNotIn(expected_line, summary_result["report"])
        self.assertNotIn("### 原最终结论表", summary_result["report"])

    def test_render_markdown_report_runtime_summary_derives_cycle_tables_from_raw_mainline_history(self):
        from report.report_document_builder import (
            build_report_shell_contract as _build_report_shell_contract_actual,
            replace_placeholder_lines as _replace_placeholder_lines_actual,
        )

        def _run_execution_stages(stage_specs, stage_context=None, stage_lookup=None):
            return {
                "lines": [],
                "module_logs": [],
                "context": {
                    "market_research_snapshot": {
                        "state_machine": {"leading_line": "半导体", "energy_state": "修复接力"},
                        "mainline_turnover_summary": {
                            "double_mainline_summary": {
                                "cycle_mainline": "半导体",
                                "daily_attack_line": "半导体",
                                "relationship": "周期主线与当天主攻线一致",
                                "tomorrow_action": "继续围绕半导体观察承接",
                            }
                        },
                    },
                    "current_mainline_history_record": {"date": "2026-04-24", "primary_mainline": "半导体", "market_state": "修复接力"},
                    "recent_mainline_history": [
                        {"date": "2026-04-17", "primary_mainline": "电力", "market_state": "强化"},
                        {"date": "2026-04-20", "primary_mainline": "电力", "market_state": "退潮"},
                        {"date": "2026-04-21", "primary_mainline": "半导体", "market_state": "接力"},
                        {"date": "2026-04-22", "primary_mainline": "半导体", "market_state": "修复"},
                    ],
                    "pivot_mainline_history": [
                        {
                            "date_range": "2026-04-17 ~ 2026-04-20",
                            "pivot_range": "3992-4114",
                            "position": "中枢上沿",
                            "structure_state": "上沿承压",
                            "mainline": "电力",
                            "interpretation": "[电力] 在中枢上沿主导市场，承压后退潮",
                        },
                        {
                            "date_range": "2026-04-21 ~ 2026-04-24",
                            "pivot_range": "3992-4114",
                            "position": "中枢内",
                            "structure_state": "中枢内修复",
                            "mainline": "半导体",
                            "interpretation": "[半导体] 在中枢内接替 [电力]，等待放量确认",
                        },
                    ],
                },
            }

        helpers = _build_runtime_execution_test_helpers(
            _run_execution_stages,
            DISPLAY_MVP_MODE=True,
            build_report_shell_contract=_build_report_shell_contract_actual,
            replace_placeholder_lines=_replace_placeholder_lines_actual,
            build_legacy_final_conclusion_lines=lambda *args, **kwargs: [],
            render_supplementary_perspective_section=lambda *args, **kwargs: [],
            render_ai_market_insight_section=lambda *args, **kwargs: [],
            _build_strategy_factor_snapshot=lambda *args, **kwargs: {},
            _build_strategy_plan_context=lambda *args, **kwargs: {},
            update_strategy_performance_book=lambda *args, **kwargs: {},
            _normalize_report_timer_steps=lambda *args, **kwargs: [],
            render_execution_appendix=lambda *args, **kwargs: [],
            run_report_tail_summary=lambda payload: {"value": {"lines": [], "module_logs": [], "exports": {}}},
            run_strategy_performance_tail=lambda payload: {"value": {"lines": [], "module_logs": [], "exports": {}}},
            run_execution_appendix_tail=lambda payload: {"value": {"lines": [], "module_logs": [], "exports": {}}},
        )

        result = report_runtime.render_markdown_report_runtime(
            {"exchange_monitor_today": [], "exchange_monitor_nextday": []},
            "2026-04-24",
            helpers=helpers,
            config={},
        )
        rendered = result["report"]

        self.assertIn("[电力] 强化", rendered)
        self.assertIn("[电力] 退潮", rendered)
        self.assertIn("[半导体] 接力", rendered)
        self.assertIn("[半导体] 修复", rendered)
        self.assertIn("| 上个周期 | 04-17 ~ 04-20 | 2日 | 电力 | 强化后退潮 |", rendered)
        self.assertIn("| 当前周期 | 04-21 ~ 04-24 | 3日 | 半导体 | 接力后修复接力 |", rendered)
        self.assertIn("| 2026-04-21 ~ 2026-04-24 | 日线中枢 | 3992-4114 | 中枢内 | 半导体 | 周期主线 | 中枢内修复 | 接替电力 | [半导体] 在中枢内接替 [电力]，等待放量确认。 |", rendered)
        self.assertNotIn("主线待累计", rendered)

    def test_render_markdown_report_runtime_persists_mainline_atoms_back_to_data(self):
        def _run_execution_stages(stage_specs, stage_context=None, stage_lookup=None):
            return {
                "lines": [],
                "module_logs": [],
                "context": {
                    "market_research_snapshot": {"state_machine": {"leading_line": "半导体"}},
                    "current_mainline_history_record": {"date": "2026-04-24", "primary_mainline": "半导体"},
                    "recent_mainline_history": [{"date": "2026-04-23", "primary_mainline": "电力"}],
                    "current_sector_turnover_snapshot": {"date": "2026-04-24", "sector_name": "半导体", "turnover_share_pct": 18.1},
                    "recent_sector_turnover_history": [{"date": "2026-04-23", "sector_name": "半导体", "turnover_share_pct": 15.8}],
                    "mainline_turnover_summary": {"current_mainline": "半导体", "conclusion": "主线切换为半导体"},
                },
            }

        data = {"exchange_monitor_today": [], "exchange_monitor_nextday": []}
        helpers = _build_runtime_execution_test_helpers(
            _run_execution_stages,
            build_legacy_final_conclusion_lines=lambda *args, **kwargs: [],
            render_supplementary_perspective_section=lambda *args, **kwargs: [],
            render_ai_market_insight_section=lambda *args, **kwargs: [],
            _build_strategy_factor_snapshot=lambda *args, **kwargs: {},
            _build_strategy_plan_context=lambda *args, **kwargs: {},
            update_strategy_performance_book=lambda *args, **kwargs: {},
            _normalize_report_timer_steps=lambda *args, **kwargs: [],
            render_execution_appendix=lambda *args, **kwargs: [],
            run_report_tail_summary=lambda payload: {"value": {"lines": [], "module_logs": [], "exports": {}}},
            run_strategy_performance_tail=lambda payload: {"value": {"lines": [], "module_logs": [], "exports": {}}},
            run_execution_appendix_tail=lambda payload: {"value": {"lines": [], "module_logs": [], "exports": {}}},
        )

        report_runtime.render_markdown_report_runtime(
            data,
            "2026-04-24",
            helpers=helpers,
            config={},
        )

        self.assertEqual(data["current_mainline_history_record"]["primary_mainline"], "半导体")
        self.assertEqual(data["recent_mainline_history"][0]["primary_mainline"], "电力")
        self.assertEqual(data["current_sector_turnover_snapshot"]["turnover_share_pct"], 18.1)
        self.assertEqual(data["recent_sector_turnover_history"][0]["turnover_share_pct"], 15.8)
        self.assertEqual(data["mainline_turnover_summary"]["current_mainline"], "半导体")

    def test_render_markdown_report_runtime_uses_market_research_snapshot_atoms_when_stage_context_lacks_top_level_atoms(self):
        def _run_execution_stages(stage_specs, stage_context=None, stage_lookup=None):
            return {
                "lines": [],
                "module_logs": [],
                "context": {
                    "market_research_snapshot": {
                        "state_machine": {"leading_line": "半导体"},
                        "current_mainline_history_record": {"date": "2026-04-24", "primary_mainline": "半导体"},
                        "mainline_turnover_summary": {
                            "current_mainline": "半导体",
                            "double_mainline_summary": {
                                "cycle_mainline": "半导体",
                                "daily_attack_line": "半导体",
                                "relationship": "周期主线与当天主攻线一致",
                                "tomorrow_action": "继续围绕半导体观察承接",
                            },
                            "turnover_share_trend_rows": [
                                {
                                    "date": "2026-04-24",
                                    "cycle_mainline": "半导体",
                                    "daily_attack_line": "半导体",
                                    "mainline_turnover": "数据暂缺",
                                    "market_turnover": "26414.92亿",
                                    "share": "待累计",
                                    "share_change": "待累计",
                                    "interpretation": "缺少板块成交额接口，先记录主线归属",
                                }
                            ],
                        },
                    },
                },
            }

        data = {"exchange_monitor_today": [], "exchange_monitor_nextday": []}
        helpers = _build_runtime_execution_test_helpers(
            _run_execution_stages,
            DISPLAY_MVP_MODE=True,
            build_legacy_final_conclusion_lines=lambda *args, **kwargs: [],
            render_supplementary_perspective_section=lambda *args, **kwargs: [],
            render_ai_market_insight_section=lambda *args, **kwargs: [],
            _build_strategy_factor_snapshot=lambda *args, **kwargs: {},
            _build_strategy_plan_context=lambda *args, **kwargs: {},
            update_strategy_performance_book=lambda *args, **kwargs: {},
            _normalize_report_timer_steps=lambda *args, **kwargs: [],
            render_execution_appendix=lambda *args, **kwargs: [],
            run_report_tail_summary=lambda payload: {"value": {"lines": [], "module_logs": [], "exports": {}}},
            run_strategy_performance_tail=lambda payload: {"value": {"lines": [], "module_logs": [], "exports": {}}},
            run_execution_appendix_tail=lambda payload: {"value": {"lines": [], "module_logs": [], "exports": {}}},
        )

        result = report_runtime.render_markdown_report_runtime(
            data,
            "2026-04-24",
            helpers=helpers,
            config={},
        )

        self.assertEqual(data["current_mainline_history_record"]["primary_mainline"], "半导体")
        self.assertIn("| 半导体 | 半导体 | 周期主线与当天主攻线一致 | 继续围绕半导体观察承接 |", result["report"])
        self.assertIn("| 2026-04-24 | 半导体 | 半导体 | 数据暂缺 | 26414.92亿 | 待累计 | 待累计 | 缺少板块成交额接口，先记录主线归属 |", result["report"])

    def test_render_markdown_report_runtime_uses_structured_turnover_history_for_share_change(self):
        def _run_execution_stages(stage_specs, stage_context=None, stage_lookup=None):
            return {
                "lines": [],
                "module_logs": [],
                "context": {
                    "market_research_snapshot": {
                        "state_machine": {"leading_line": "半导体"},
                        "mainline_turnover_summary": {
                            "current_mainline": "半导体",
                            "double_mainline_summary": {
                                "cycle_mainline": "半导体",
                                "daily_attack_line": "半导体",
                                "relationship": "周期主线与当天主攻线一致",
                                "tomorrow_action": "继续围绕半导体观察承接",
                            },
                            "turnover_share_trend_rows": [
                                {
                                    "date": "2026-04-24",
                                    "cycle_mainline": "半导体",
                                    "daily_attack_line": "半导体",
                                    "mainline_turnover": "2180.00亿",
                                    "market_turnover": "12834.00亿",
                                    "share": "18.1%",
                                    "share_change": "待累计",
                                    "interpretation": "主线占比继续抬升",
                                }
                            ],
                        },
                    },
                    "current_mainline_history_record": {"date": "2026-04-24", "primary_mainline": "半导体"},
                    "recent_mainline_history": [{"date": "2026-04-23", "primary_mainline": "半导体"}],
                    "current_sector_turnover_snapshot": {
                        "date": "2026-04-24",
                        "sector_name": "半导体",
                        "turnover_share_pct": 18.1,
                    },
                    "recent_sector_turnover_history": [
                        {"date": "2026-04-23", "sector_name": "半导体", "turnover_share_pct": 15.8},
                    ],
                },
            }

        helpers = _build_runtime_execution_test_helpers(
            _run_execution_stages,
            DISPLAY_MVP_MODE=True,
            build_legacy_final_conclusion_lines=lambda *args, **kwargs: [],
            render_supplementary_perspective_section=lambda *args, **kwargs: [],
            render_ai_market_insight_section=lambda *args, **kwargs: [],
            _build_strategy_factor_snapshot=lambda *args, **kwargs: {},
            _build_strategy_plan_context=lambda *args, **kwargs: {},
            update_strategy_performance_book=lambda *args, **kwargs: {},
            _normalize_report_timer_steps=lambda *args, **kwargs: [],
            render_execution_appendix=lambda *args, **kwargs: [],
            run_report_tail_summary=lambda payload: {"value": {"lines": [], "module_logs": [], "exports": {}}},
            run_strategy_performance_tail=lambda payload: {"value": {"lines": [], "module_logs": [], "exports": {}}},
            run_execution_appendix_tail=lambda payload: {"value": {"lines": [], "module_logs": [], "exports": {}}},
        )

        result = report_runtime.render_markdown_report_runtime(
            {"exchange_monitor_today": [], "exchange_monitor_nextday": []},
            "2026-04-24",
            helpers=helpers,
            config={},
        )

        self.assertIn(
            "| 2026-04-24 | 半导体 | 半导体 | 2180.00亿 | 12834.00亿 | 18.1% | +2.3pct | 主线占比继续抬升 |",
            result["report"],
        )

    def test_render_markdown_report_runtime_does_not_clear_existing_mainline_atoms_when_context_is_empty(self):
        def _run_execution_stages(stage_specs, stage_context=None, stage_lookup=None):
            return {"lines": [], "module_logs": [], "context": {}}

        data = {
            "exchange_monitor_today": [],
            "exchange_monitor_nextday": [],
            "market_research_snapshot": {"state_machine": {"leading_line": "半导体"}},
            "current_mainline_history_record": {"date": "2026-04-24", "primary_mainline": "半导体"},
            "recent_mainline_history": [{"date": "2026-04-23", "primary_mainline": "电力"}],
            "current_sector_turnover_snapshot": {"date": "2026-04-24", "sector_name": "半导体", "turnover_share_pct": 18.1},
            "recent_sector_turnover_history": [{"date": "2026-04-23", "sector_name": "半导体", "turnover_share_pct": 15.8}],
            "mainline_turnover_summary": {
                "current_mainline": "半导体",
                "double_mainline_summary": {
                    "cycle_mainline": "半导体",
                    "daily_attack_line": "半导体",
                    "relationship": "周期主线与当天主攻线一致",
                    "tomorrow_action": "继续围绕半导体观察承接",
                },
                "turnover_share_trend_rows": [
                    {
                        "date": "2026-04-24",
                        "cycle_mainline": "半导体",
                        "daily_attack_line": "半导体",
                        "mainline_turnover": "2180.00亿",
                        "market_turnover": "12834.00亿",
                        "share": "18.1%",
                        "share_change": "+2.3pct",
                        "interpretation": "主线占比继续抬升",
                    }
                ],
            },
        }
        helpers = _build_runtime_execution_test_helpers(
            _run_execution_stages,
            DISPLAY_MVP_MODE=True,
            build_legacy_final_conclusion_lines=lambda *args, **kwargs: [],
            render_supplementary_perspective_section=lambda *args, **kwargs: [],
            render_ai_market_insight_section=lambda *args, **kwargs: [],
            _build_strategy_factor_snapshot=lambda *args, **kwargs: {},
            _build_strategy_plan_context=lambda *args, **kwargs: {},
            update_strategy_performance_book=lambda *args, **kwargs: {},
            _normalize_report_timer_steps=lambda *args, **kwargs: [],
            render_execution_appendix=lambda *args, **kwargs: [],
            run_report_tail_summary=lambda payload: {"value": {"lines": [], "module_logs": [], "exports": {}}},
            run_strategy_performance_tail=lambda payload: {"value": {"lines": [], "module_logs": [], "exports": {}}},
            run_execution_appendix_tail=lambda payload: {"value": {"lines": [], "module_logs": [], "exports": {}}},
        )

        result = report_runtime.render_markdown_report_runtime(
            data,
            "2026-04-24",
            helpers=helpers,
            config={},
        )

        self.assertEqual(data["current_mainline_history_record"]["primary_mainline"], "半导体")
        self.assertEqual(data["mainline_turnover_summary"]["current_mainline"], "半导体")
        self.assertIn("| 半导体 | 半导体 | 周期主线与当天主攻线一致 | 继续围绕半导体观察承接 |", result["report"])
        self.assertIn("| 2026-04-24 | 半导体 | 半导体 | 2180.00亿 | 12834.00亿 | 18.1% | +2.3pct | 主线占比继续抬升 |", result["report"])
        self.assertNotIn("| - | - | 主线待确认 |", result["report"])

    def test_render_markdown_report_runtime_sanitizes_english_jargon_in_full_report_tail(self):
        def _run_execution_stages(stage_specs, stage_context=None, stage_lookup=None):
            return {
                "lines": ["有辨识度，但最近没有连续 act right，先别按趋势续强处理。"],
                "module_logs": [],
                "context": {},
            }

        helpers = _build_runtime_execution_test_helpers(
            _run_execution_stages,
            build_legacy_final_conclusion_lines=lambda *args, **kwargs: [],
            render_supplementary_perspective_section=lambda *args, **kwargs: [],
            render_ai_market_insight_section=lambda *args, **kwargs: [],
            _build_strategy_factor_snapshot=lambda *args, **kwargs: {},
            _build_strategy_plan_context=lambda *args, **kwargs: {},
            update_strategy_performance_book=lambda *args, **kwargs: {},
            _normalize_report_timer_steps=lambda *args, **kwargs: [],
            render_execution_appendix=lambda *args, **kwargs: [],
            _compact_report_for_mvp=lambda report, stage_lookup=None: report,
        )

        result = report_runtime.render_markdown_report_runtime(
            {"exchange_monitor_today": [], "exchange_monitor_nextday": []},
            "2026-04-24",
            helpers=helpers,
            config={},
        )

        self.assertNotIn("act right", result["report"].lower())
        self.assertIn("走势符合强势标准", result["report"])

    def test_render_markdown_report_runtime_front_page_replaces_english_trading_jargon(self):
        from hooks.report.use_report_tail_summary import run as _run_report_tail_summary_actual
        from report.front_summary_renderer import render_front_digest as _render_front_digest_actual
        from report.front_summary_support import render_core_mvp_digest as _render_core_mvp_digest_actual
        from report.report_document_builder import (
            build_report_shell_contract as _build_report_shell_contract_actual,
            replace_placeholder_lines as _replace_placeholder_lines_actual,
        )

        def _run_execution_stages(stage_specs, stage_context=None, stage_lookup=None):
            market_research_snapshot = {
                "observation": {},
                "style_switch": {"style_label": "setup 完整"},
                "state_machine": {"leading_line": "军工", "energy_state": "act right", "state_reason": "probe 后 follow through"},
                "follow_verdict": {"label": "follow through"},
                "dialectical_decision": {"stage_label": "probe", "stage_action": "setup 后执行"},
            }
            digest_lines = stage_context["render_core_mvp_digest"](
                market_research_snapshot,
                final_gate={"can_new_entry": True, "final_action": "follow through"},
                position_level="三档（进攻档）",
                position_reason="act right",
                exit_analysis={"sector_name": "军工", "overall_level": "黄灯"},
                execution_framework_text="setup 后等 act right",
                high_board_count=3,
                structure_layer_text="probe 不追",
                front_follow_action_text="follow through 后执行",
                compact=False,
            )
            return {
                "lines": list(digest_lines),
                "module_logs": [],
                "context": {
                    "core_mvp_digest_lines": digest_lines,
                    "mvp_focus_summary_lines": ["- **特殊标的先看谁**: probe 一号 setup"],
                    "front_structure_layer_text": "setup 后等 act right",
                    "front_follow_action_text": "probe 后 follow through",
                    "market_state_snapshot": {"energy_state": "setup", "flow_direction": "follow through"},
                },
            }

        helpers = _build_runtime_execution_test_helpers(
            _run_execution_stages,
            build_report_shell_contract=_build_report_shell_contract_actual,
            replace_placeholder_lines=_replace_placeholder_lines_actual,
            _render_core_mvp_digest=_render_core_mvp_digest_actual,
            render_front_digest=_render_front_digest_actual,
            build_legacy_final_conclusion_lines=lambda *args, **kwargs: [],
            render_supplementary_perspective_section=lambda *args, **kwargs: [],
            render_ai_market_insight_section=lambda *args, **kwargs: [],
            _build_strategy_factor_snapshot=lambda *args, **kwargs: {},
            _build_strategy_plan_context=lambda *args, **kwargs: {},
            update_strategy_performance_book=lambda *args, **kwargs: {},
            _normalize_report_timer_steps=lambda *args, **kwargs: [],
            render_execution_appendix=lambda *args, **kwargs: [],
            _compact_report_for_mvp=lambda report, stage_lookup=None: report,
            run_report_tail_summary=_run_report_tail_summary_actual,
            run_strategy_performance_tail=lambda payload: {"value": {"lines": [], "module_logs": [], "exports": {}}},
            run_execution_appendix_tail=lambda payload: {"value": {"lines": [], "module_logs": [], "exports": {}}},
        )

        result = report_runtime.render_markdown_report_runtime(
            {"exchange_monitor_today": [], "exchange_monitor_nextday": []},
            "2026-04-22",
            helpers=helpers,
            config={},
        )

        rendered = result["report"].lower()
        for forbidden in ("act right", "setup", "probe", "follow through"):
            self.assertNotIn(forbidden, rendered)
        self.assertIn("走势符合强势标准", result["report"])
        self.assertIn("形态条件", result["report"])
        self.assertIn("优先观察对象", result["report"])
        self.assertIn("延续承接", result["report"])

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
