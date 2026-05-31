import contextlib
import importlib
import io
import subprocess
import sys
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report import runtime as report_runtime
from report.front_page_v2_renderer import render_front_page_v2


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
        "pandas": _stub_module("pandas"),
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
        "_default_build_entry_cycle_calibrations": lambda as_of_date="": {},
    }
    helpers.update(overrides)
    return helpers


class ReportRuntimeTest(unittest.TestCase):
    def test_prefer_confirmed_attack_mainline_history_record_over_stale_execution_record(self):
        result = report_runtime._prefer_confirmed_attack_mainline_history_record(
            execution_record={
                "date": "2026-05-21",
                "primary_mainline": "半导体",
                "leading_line": "半导体",
                "rotation_summary": "主攻线半导体 / 次强线电力 / 竞争线证券",
            },
            snapshot_record={
                "date": "2026-05-21",
                "primary_mainline": "人形机器人",
                "leading_line": "人形机器人",
                "rotation_summary": "人形机器人资金净流入靠前，涨停更集中",
            },
            mainline_turnover_summary={
                "mainline_attack_evidence_summary": {
                    "attack_state": "confirmed_attack",
                    "primary_line": "人形机器人",
                }
            },
            target_date="2026-05-21",
        )

        self.assertEqual(result["primary_mainline"], "人形机器人")
        self.assertEqual(result["leading_line"], "人形机器人")
        self.assertNotIn("主攻线半导体", result["rotation_summary"])

    def test_number_report_tables_inserts_dynamic_t_numbers(self):
        lines = [
            "## 一、市场基底",
            "| 字段 | 结论 |",
            "|------|------|",
            "| 两市成交额 | 29764.59亿 |",
            "",
            "### 3. 创新高趋势反馈",
            "| 日期 | 新高数 | 全A占比 |",
            "|------|--------|---------|",
            "| 2026-05-20 | 169 | 3.38% |",
        ]

        numbered = report_runtime._number_report_tables(lines)

        self.assertEqual(
            numbered,
            [
                "## 一、市场基底",
                "**T-001**",
                "| 字段 | 结论 |",
                "|------|------|",
                "| 两市成交额 | 29764.59亿 |",
                "",
                "### 3. 创新高趋势反馈",
                "**T-002**",
                "| 日期 | 新高数 | 全A占比 |",
                "|------|--------|---------|",
                "| 2026-05-20 | 169 | 3.38% |",
            ],
        )

    def test_number_report_tables_renumbers_after_previous_table_removed(self):
        lines = [
            "### 3. 创新高趋势反馈",
            "| 日期 | 新高数 | 全A占比 |",
            "|------|--------|---------|",
            "| 2026-05-20 | 169 | 3.38% |",
        ]

        numbered = report_runtime._number_report_tables(lines)

        self.assertEqual(numbered[1], "**T-001**")
        self.assertNotIn("**T-002**", numbered)

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

    def test_build_appendix_b_continuity_payload_prefers_summary_turnover_row_for_current_date(self):
        payload = report_runtime._build_appendix_b_continuity_payload(
            current_mainline_history_record={"date": "2026-05-21", "primary_mainline": "人形机器人"},
            current_sector_turnover_snapshot={
                "date": "2026-05-21",
                "sector_name": "半导体",
                "turnover_share_pct": 13.27,
                "source_status": "success",
            },
            mainline_turnover_summary={
                "turnover_share_trend_rows": [
                    {
                        "date": "2026-05-21",
                        "cycle_mainline": "人形机器人",
                        "daily_attack_line": "人形机器人",
                        "share": "2.5%",
                    }
                ]
            },
            target_date="2026-05-21",
        )

        row = payload["turnover_share_history"][0]
        self.assertEqual(row["mainline"], "人形机器人")
        self.assertEqual(row["turnover_share_pct"], "2.5%")
        self.assertEqual(row["source"], "mainline_turnover_summary")

    def test_merge_appendix_b_payload_replaces_stale_zero_turnover_share_for_same_date(self):
        existing = {
            "turnover_share_history": [
                {
                    "date": "2026-05-13",
                    "mainline": "电力",
                    "turnover_share_pct": "0.00%",
                    "source": "success",
                }
            ]
        }
        derived = {
            "turnover_share_history": [
                {
                    "date": "2026-05-13",
                    "mainline": "电力",
                    "turnover_share_pct": "3.05%",
                    "source": "tushare.daily",
                }
            ]
        }

        merged = report_runtime._merge_appendix_b_payload(existing, derived)

        self.assertEqual(merged["turnover_share_history"][0]["turnover_share_pct"], "3.05%")
        self.assertEqual(merged["turnover_share_history"][0]["source"], "tushare.daily")

    def test_merge_appendix_b_payload_prefers_summary_turnover_share_for_same_date(self):
        existing = {
            "turnover_share_history": [
                {
                    "date": "2026-05-21",
                    "mainline": "半导体",
                    "turnover_share_pct": "13.27%",
                    "source": "success",
                }
            ]
        }
        derived = {
            "turnover_share_history": [
                {
                    "date": "2026-05-21",
                    "mainline": "人形机器人",
                    "turnover_share_pct": "2.5%",
                    "source": "mainline_turnover_summary",
                }
            ]
        }

        merged = report_runtime._merge_appendix_b_payload(existing, derived)

        self.assertEqual(merged["turnover_share_history"][0]["mainline"], "人形机器人")
        self.assertEqual(merged["turnover_share_history"][0]["turnover_share_pct"], "2.5%")

    def test_merge_appendix_b_payload_replaces_structure_record_for_same_date(self):
        existing = {
            "structure_mainline_records": [
                {
                    "date": "05-14",
                    "date_range": "05-14",
                    "mainline": "半导体",
                    "mainline_degree": "周期主线",
                }
            ]
        }
        derived = {
            "structure_mainline_records": [
                {
                    "date": "05-14",
                    "date_range": "05-14",
                    "mainline": "暂无确认主线",
                    "mainline_degree": "待确认",
                }
            ]
        }

        merged = report_runtime._merge_appendix_b_payload(existing, derived)

        self.assertEqual(len(merged["structure_mainline_records"]), 1)
        self.assertEqual(merged["structure_mainline_records"][0]["mainline"], "暂无确认主线")
        self.assertEqual(merged["structure_mainline_records"][0]["mainline_degree"], "待确认")

    def test_merge_appendix_b_payload_replaces_historical_mainline_for_same_date(self):
        existing = {
            "historical_mainline_pool": [
                {
                    "date": "2026-05-21",
                    "mainline": "半导体",
                    "status": "爆发",
                    "note": "主攻线半导体 / 次强线电力 / 竞争线证券",
                }
            ]
        }
        derived = {
            "historical_mainline_pool": [
                {
                    "date": "2026-05-21",
                    "mainline": "人形机器人",
                    "status": "爆发",
                    "note": "人形机器人资金净流入靠前，涨停更集中",
                }
            ]
        }

        merged = report_runtime._merge_appendix_b_payload(existing, derived)

        self.assertEqual(len(merged["historical_mainline_pool"]), 1)
        self.assertEqual(merged["historical_mainline_pool"][0]["mainline"], "人形机器人")
        self.assertNotIn("主攻线半导体", merged["historical_mainline_pool"][0]["note"])

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

    def test_build_appendix_b_continuity_payload_downgrades_current_structure_when_attack_evidence_is_chaotic(self):
        payload = report_runtime._build_appendix_b_continuity_payload(
            target_date="2026-05-14",
            mainline_turnover_summary={
                "mainline_attack_evidence_summary": {
                    "attack_state": "chaotic_rotation",
                    "primary_line": "",
                    "candidate_lines": ["化学制品", "养殖业", "家居用品"],
                    "confirmation_evidence": "多方向局部活跃但资金未明显胜出",
                }
            },
            pivot_mainline_history=[
                {
                    "date_range": "05-14",
                    "pivot_level": "日线中枢",
                    "pivot_range": "-",
                    "position": "中枢内",
                    "mainline": "半导体",
                    "mainline_degree": "周期主线",
                    "evolution": "观察",
                    "replacement": "待确认",
                    "interpretation": "中枢是主线周期载体：[半导体] 承载在日线中枢。",
                }
            ],
        )

        record = payload["structure_mainline_records"][0]
        self.assertEqual(record["mainline"], "暂无确认主线")
        self.assertEqual(record["mainline_degree"], "待确认")
        self.assertEqual(record["replacement"], "待确认")
        self.assertEqual(record["interpretation"], "中枢只记录候选方向，不把单日热度升级为周期主线；多方向局部活跃但资金未明显胜出。")

    def test_appendix_b_renders_daily_candidate_not_confirmed_zhongshu(self):
        rows = report_runtime._derive_appendix_pivot_mainline_history(
            current_mainline_history_record={"date": "2026-04-27", "primary_mainline": "半导体"},
            data={
                "target_date": "2026-04-27",
                "market_zhongshu": {
                    "success": True,
                    "daily_structure_current": {
                        "start_date": "2026-04-14",
                        "end_date": "2026-04-24",
                        "kline_count": 9,
                        "required_kline_count": 20,
                        "zd_candidate": 3992.41,
                        "zg_candidate": 4114.84,
                        "candidate_status": "daily_candidate_forming",
                    },
                    "chanlun_confirmation": {
                        "confirmation_status": "forming_daily_level_zhongshu",
                        "confirmed": False,
                    },
                },
            },
        )

        self.assertEqual(rows[0]["pivot_level"], "日K结构候选（9/20）")
        self.assertNotEqual(rows[0]["pivot_level"], "日线中枢")

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

    def test_build_calendar_ai_context_normalizes_batch_other_to_concrete_sector(self):
        class OtherBatchClient:
            def analyze_events_batch(self, events, batch_size=8):
                return [
                    {
                        "main_direction": "其他",
                        "related_sectors": ["其他"],
                        "trading_logic": "AI无法识别明确产业链",
                        "expectation": "中性",
                        "confidence": "低",
                    }
                    for _ in events
                ]

        original_get_llm_service = getattr(report_runtime, "get_llm_service", None)
        original_stats = getattr(report_runtime, "_llm_call_stats", None)
        try:
            report_runtime.get_llm_service = lambda: OtherBatchClient()
            report_runtime._llm_call_stats = {
                "total_calls": 0,
                "total_time": 0.0,
                "event_analysis_calls": 0,
                "event_analysis_time": 0.0,
            }

            result = report_runtime._build_calendar_ai_context(
                {"calendar_events": [{"date": "2026-05-07", "title": "未知行业政策发布", "star": 5}]},
                print_fn=lambda *args, **kwargs: None,
            )

            ai_analysis = result["calendar_analysis"][0]["ai_analysis"]
            self.assertEqual(ai_analysis["main_direction"], "政策催化")
            self.assertNotIn("其他", ai_analysis["related_sectors"])
            self.assertEqual(result["top_directions"], [("政策催化", 1)])
            self.assertIn("政策催化", result["unique_sectors"])
        finally:
            if original_get_llm_service is None:
                delattr(report_runtime, "get_llm_service")
            else:
                report_runtime.get_llm_service = original_get_llm_service
            if original_stats is None:
                if hasattr(report_runtime, "_llm_call_stats"):
                    delattr(report_runtime, "_llm_call_stats")
            else:
                report_runtime._llm_call_stats = original_stats

    def test_build_calendar_ai_context_handles_malformed_batch_results_without_other(self):
        class MalformedBatchClient:
            def analyze_events_batch(self, events, batch_size=8):
                return [None]

        original_get_llm_service = getattr(report_runtime, "get_llm_service", None)
        original_stats = getattr(report_runtime, "_llm_call_stats", None)
        try:
            report_runtime.get_llm_service = lambda: MalformedBatchClient()
            report_runtime._llm_call_stats = {
                "total_calls": 0,
                "total_time": 0.0,
                "event_analysis_calls": 0,
                "event_analysis_time": 0.0,
            }

            result = report_runtime._build_calendar_ai_context(
                {"calendar_events": [{"date": "2026-05-07", "title": "某区域发展规划发布", "star": 5}]},
                print_fn=lambda *args, **kwargs: None,
            )

            ai_analysis = result["calendar_analysis"][0]["ai_analysis"]
            self.assertNotEqual(ai_analysis["main_direction"], "其他")
            self.assertTrue(ai_analysis["related_sectors"])
            self.assertTrue(result["top_directions"])
            self.assertTrue(result["unique_sectors"])
        finally:
            if original_get_llm_service is None:
                delattr(report_runtime, "get_llm_service")
            else:
                report_runtime.get_llm_service = original_get_llm_service
            if original_stats is None:
                if hasattr(report_runtime, "_llm_call_stats"):
                    delattr(report_runtime, "_llm_call_stats")
            else:
                report_runtime._llm_call_stats = original_stats

    def test_build_calendar_ai_context_uses_local_rules_by_default_without_llm(self):
        class ExplodingBatchClient:
            def analyze_events_batch(self, events, batch_size=8):
                raise AssertionError("DeepSeek should not be called by default")

        original_get_llm_service = getattr(report_runtime, "get_llm_service", None)
        original_remote_flag = getattr(report_runtime, "ENABLE_REMOTE_CALENDAR_LLM", None)
        try:
            report_runtime.get_llm_service = lambda: ExplodingBatchClient()
            report_runtime.ENABLE_REMOTE_CALENDAR_LLM = False

            result = report_runtime._build_calendar_ai_context(
                {
                    "calendar_events": [
                        {"date": "2026-05-07", "title": "人形机器人产业大会召开", "star": 5}
                    ]
                },
                print_fn=lambda *args, **kwargs: None,
            )

            ai_analysis = result["calendar_analysis"][0]["ai_analysis"]
            self.assertEqual(result["analysis_source"], "local_rules")
            self.assertEqual(ai_analysis["main_direction"], "人形机器人")
            self.assertIn("减速器", ai_analysis["related_sectors"])
        finally:
            if original_get_llm_service is None:
                delattr(report_runtime, "get_llm_service")
            else:
                report_runtime.get_llm_service = original_get_llm_service
            if original_remote_flag is None:
                if hasattr(report_runtime, "ENABLE_REMOTE_CALENDAR_LLM"):
                    delattr(report_runtime, "ENABLE_REMOTE_CALENDAR_LLM")
            else:
                report_runtime.ENABLE_REMOTE_CALENDAR_LLM = original_remote_flag

    def test_build_calendar_ai_context_falls_back_to_local_rules_when_remote_llm_fails(self):
        class FailingBatchClient:
            def analyze_events_batch(self, events, batch_size=8):
                raise RuntimeError("deepseek timeout")

        original_get_llm_service = getattr(report_runtime, "get_llm_service", None)
        original_remote_flag = getattr(report_runtime, "ENABLE_REMOTE_CALENDAR_LLM", None)
        emitted = []
        try:
            report_runtime.get_llm_service = lambda: FailingBatchClient()
            report_runtime.ENABLE_REMOTE_CALENDAR_LLM = True

            result = report_runtime._build_calendar_ai_context(
                {
                    "calendar_events": [
                        {"date": "2026-05-07", "title": "人形机器人产业大会召开", "star": 5}
                    ]
                },
                print_fn=emitted.append,
            )

            ai_analysis = result["calendar_analysis"][0]["ai_analysis"]
            self.assertEqual(result["analysis_source"], "local_rules")
            self.assertEqual(result["remote_llm_error"], "deepseek timeout")
            self.assertEqual(ai_analysis["main_direction"], "人形机器人")
            self.assertTrue(any("远程LLM失败" in line for line in emitted))
        finally:
            if original_get_llm_service is None:
                delattr(report_runtime, "get_llm_service")
            else:
                report_runtime.get_llm_service = original_get_llm_service
            if original_remote_flag is None:
                if hasattr(report_runtime, "ENABLE_REMOTE_CALENDAR_LLM"):
                    delattr(report_runtime, "ENABLE_REMOTE_CALENDAR_LLM")
            else:
                report_runtime.ENABLE_REMOTE_CALENDAR_LLM = original_remote_flag

    def test_build_calendar_ai_context_normalizes_remote_generic_policy_to_specific_events(self):
        class GenericPolicyBatchClient:
            def __init__(self):
                self.calls = []

            def analyze_events_batch(self, events, batch_size=8):
                self.calls.append(list(events))
                return [
                    {
                        "main_direction": "政策催化",
                        "related_sectors": ["政策催化"],
                        "trading_logic": "按会议或规则事件处理",
                        "expectation": "中性",
                        "confidence": "低",
                    }
                    for _ in events
                ]

        client = GenericPolicyBatchClient()
        original_get_llm_service = getattr(report_runtime, "get_llm_service", None)
        original_remote_flag = getattr(report_runtime, "ENABLE_REMOTE_CALENDAR_LLM", None)
        try:
            report_runtime.get_llm_service = lambda: client
            report_runtime.ENABLE_REMOTE_CALENDAR_LLM = True

            result = report_runtime._build_calendar_ai_context(
                {
                    "calendar_events": [
                        {"date": "2026-05-21", "title": "第四届中国能源周——绿色燃料未来论坛将于5月21日举办", "star": 3},
                        {"date": "2026-06-02", "title": "台北电脑展（Computex 2026）将于6月2日至5日举行", "star": 2},
                        {"date": "2026-06-08", "title": "LME将铅和锌直接合约单日涨跌幅限制从15%下调至12%，新规将于6月8日起生效", "star": 2},
                    ]
                },
                print_fn=lambda *args, **kwargs: None,
            )

            directions = [item["ai_analysis"]["main_direction"] for item in result["calendar_analysis"]]
            self.assertEqual(result["analysis_source"], "remote_llm")
            self.assertEqual(len(client.calls), 1)
            self.assertEqual(directions, ["新能源", "消费电子", "有色金属"])
            self.assertNotIn(("政策催化", 3), result["top_directions"])
        finally:
            if original_get_llm_service is None:
                delattr(report_runtime, "get_llm_service")
            else:
                report_runtime.get_llm_service = original_get_llm_service
            if original_remote_flag is None:
                if hasattr(report_runtime, "ENABLE_REMOTE_CALENDAR_LLM"):
                    delattr(report_runtime, "ENABLE_REMOTE_CALENDAR_LLM")
            else:
                report_runtime.ENABLE_REMOTE_CALENDAR_LLM = original_remote_flag

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

    def test_render_markdown_report_runtime_passes_market_risk_context_to_execution_data(self):
        class _RiskContextCaptured(RuntimeError):
            pass

        systemic_warnings = [
            {
                "name": "全市场",
                "risk_level": "high",
                "risk_source": "st_resume_experience",
                "reason": "2只突发ST复牌，经验上容易触发量化/风控卖出，明日有4000+下跌风险。",
            }
        ]
        risk_theme_impacts = [
            {
                "name": "ST股",
                "risk_level": "high",
                "risk_source": "st_resume_experience",
                "reason": "2只突发ST复牌，经验上容易带动ST股与风险偏好杀跌。",
            }
        ]
        risk_sectors = systemic_warnings + risk_theme_impacts

        def _run_execution_stages(stage_specs, stage_context=None, stage_lookup=None):
            execution_data = stage_context["data"]
            self.assertEqual(execution_data["systemic_risk_warnings"], systemic_warnings)
            self.assertEqual(execution_data["risk_theme_impacts"], risk_theme_impacts)
            self.assertEqual(execution_data["risk_sectors"], risk_sectors)
            raise _RiskContextCaptured("captured")

        base_helpers = _build_runtime_execution_test_helpers(_run_execution_stages)
        base_market_phase_context = base_helpers["build_market_phase_context"]

        def _build_market_phase_context(*args, **kwargs):
            context = base_market_phase_context(*args, **kwargs)
            context["market_analysis"] = {
                "systemic_risk_warnings": systemic_warnings,
                "risk_theme_impacts": risk_theme_impacts,
                "risk_sectors": risk_sectors,
            }
            return context

        helpers = _build_runtime_execution_test_helpers(
            _run_execution_stages,
            build_market_phase_context=_build_market_phase_context,
        )

        with self.assertRaises(_RiskContextCaptured):
            report_runtime.render_markdown_report_runtime(
                {
                    "exchange_monitor_today": [],
                    "exchange_monitor_nextday": [],
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

    def test_render_markdown_report_runtime_passes_effective_selected_target_into_tail_summary(self):
        class _TailSummaryCaptured(RuntimeError):
            pass

        def _run_execution_stages(stage_specs, stage_context=None, stage_lookup=None):
            return {
                "lines": [],
                "module_logs": [],
                "context": {
                    "mainline_name": "半导体",
                    "market_research_snapshot": {},
                    "watchlist": [{"name": "汇源通信", "code": "000586"}],
                    "core_stocks": [{"name": "景兴纸业", "code": "002067"}],
                    "selected_position_candidate": {
                        "name": "汇源通信",
                        "code": "000586",
                        "sector": "通信设备",
                    },
                    "position_decision": {},
                },
            }

        def _capture_tail_summary(payload):
            inputs = payload["inputs"]
            self.assertEqual(inputs["selected_position_candidate"]["code"], "000586")
            self.assertEqual(inputs["position_decision"]["target_position_pct"], 0)
            self.assertEqual(inputs["position_decision"]["signal_grade"], "0")
            self.assertFalse(inputs["final_gate"].get("allow_attack_50_ready"))
            self.assertIn("缺少独立参与证据", inputs["position_decision"]["sizing_reason"])
            raise _TailSummaryCaptured("captured")

        def _build_market_phase_context(*args, **kwargs):
            return {
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
                "position_level": "一档（空仓档）",
                "position_reason": "",
                "final_gate": {"final_action": "空仓等待", "operation_state": "观察态", "can_new_entry": False, "should_reduce": True},
                "environment_display": {"position_level": "一档（空仓档）", "operation_state": "观察态"},
                "overall_level": "红灯",
                "price_info": {},
            }

        helpers = _build_runtime_execution_test_helpers(
            _run_execution_stages,
            build_market_phase_context=_build_market_phase_context,
            run_report_tail_summary=_capture_tail_summary,
            build_legacy_final_conclusion_lines=lambda *args, **kwargs: [],
            render_context_tail_sections=lambda *args, **kwargs: [],
            render_supplementary_perspective_section=lambda *args, **kwargs: [],
            render_ai_market_insight_section=lambda *args, **kwargs: [],
        )

        with self.assertRaises(_TailSummaryCaptured):
            report_runtime.render_markdown_report_runtime(
                {"exchange_monitor_today": [], "exchange_monitor_nextday": []},
                "2026-05-19",
                helpers=helpers,
                config={},
            )

    def test_render_markdown_report_runtime_passes_monthly_account_record_to_position_sizing(self):
        class _MonthlyContextCaptured(RuntimeError):
            pass

        captured = {}

        def _run_execution_stages(stage_specs, stage_context=None, stage_lookup=None):
            captured["monthly_context"] = dict((stage_context or {}).get("monthly_context") or {})
            raise _MonthlyContextCaptured("captured")

        helpers = _build_runtime_execution_test_helpers(
            _run_execution_stages,
            query_monthly_account_context=lambda **kwargs: {
                "month_return_pct": 6.8,
                "month_return_source": "manual_review",
                "monthly_ledger_trade_date": "2026-05-20",
            },
        )

        with self.assertRaises(_MonthlyContextCaptured):
            report_runtime.render_markdown_report_runtime(
                {"exchange_monitor_today": [], "exchange_monitor_nextday": []},
                "2026-05-20",
                helpers=helpers,
                config={},
            )

        self.assertEqual(captured["monthly_context"]["month_return_pct"], 6.8)
        self.assertEqual(captured["monthly_context"]["month_return_source"], "manual_review")

    def test_postgres_only_runtime_keeps_monthly_context_without_local_account_lookup(self):
        class _MonthlyContextCaptured(RuntimeError):
            pass

        captured = {}

        def _run_execution_stages(stage_specs, stage_context=None, stage_lookup=None):
            captured["monthly_context"] = dict((stage_context or {}).get("monthly_context") or {})
            raise _MonthlyContextCaptured("captured")

        def fail_query(**kwargs):
            raise AssertionError("local monthly account lookup should not run")

        helpers = _build_runtime_execution_test_helpers(
            _run_execution_stages,
            query_monthly_account_context=fail_query,
        )

        with self.assertRaises(_MonthlyContextCaptured):
            report_runtime.render_markdown_report_runtime(
                {
                    "postgres_only": True,
                    "monthly_context": {
                        "month_return_pct": 3.2,
                        "month_return_source": "postgresql.daily_report_facts",
                    },
                    "exchange_monitor_today": [],
                    "exchange_monitor_nextday": [],
                },
                "2026-05-20",
                helpers=helpers,
                config={},
            )

        self.assertEqual(captured["monthly_context"]["month_return_pct"], 3.2)
        self.assertEqual(captured["monthly_context"]["month_return_source"], "postgresql.daily_report_facts")

    def test_front_page_position_decision_keeps_zero_context_for_extreme_candidate(self):
        position_decision = report_runtime._build_front_page_position_decision(
            position_decision={
                "participation_mode": "observe_0",
                "target_position_pct": 0,
                "single_focus_constraint": {
                    "status": "missing_target",
                    "reason": "缺少唯一执行对象，当前只能保持观察。",
                },
                "full_attack_check": {
                    "status": "incomplete",
                    "missing": ["唯一对象", "参与窗口"],
                    "required": ["唯一对象", "参与窗口"],
                },
            },
            selected_position_candidate={
                "name": "晶方科技",
                "code": "603005",
                "sector": "半导体",
                "source_tier": "extreme_conviction",
                "participation_window": "竞价表态 + 回封参与",
            },
            data={},
            market_research_snapshot={},
            final_gate={"can_new_entry": False, "should_reduce": True},
        )

        self.assertEqual(position_decision["target_position_pct"], 0)
        self.assertEqual(position_decision["signal_grade"], "0")
        self.assertEqual(position_decision["single_focus_constraint"]["status"], "observe")
        self.assertIn("唯一对象", position_decision["full_attack_check"]["missing"])

    def test_front_page_position_decision_does_not_upgrade_observation_target_without_independent_evidence(self):
        position_decision = report_runtime._build_front_page_position_decision(
            position_decision={},
            selected_position_candidate={
                "name": "汇源通信",
                "code": "000586",
                "sector": "通信设备",
                "source_tier": "extreme_conviction",
                "participation_window": "竞价表态 + 回封参与",
                "required_steps": ["竞价表态", "开盘前几分钟承接", "回封/打板"],
            },
            data={},
            market_research_snapshot={},
            final_gate={"can_new_entry": False, "should_reduce": True},
        )

        self.assertEqual(position_decision["target_position_pct"], 0)
        self.assertEqual(position_decision["signal_grade"], "0")
        self.assertEqual(position_decision["participation_mode"], "observe_0")
        self.assertIn("缺少独立参与证据", position_decision["sizing_reason"])
        self.assertNotIn("50%标准进攻", position_decision["sizing_reason"])

    def test_front_page_position_decision_keeps_countertrend_attack_observation_only(self):
        position_decision = report_runtime._build_front_page_position_decision(
            position_decision={
                "participation_mode": "attack_50_preview",
                "target_position_pct": 50,
                "signal_grade": "50",
                "monthly_rhythm": {
                    "month_mode": "attack_prepare",
                    "max_position_pct": 50,
                },
            },
            selected_position_candidate={
                "name": "华微电子",
                "code": "600360",
                "sector": "半导体",
                "source_tier": "extreme_conviction",
                "participation_window": "09:50-10:10",
            },
            data={},
            market_research_snapshot={
                "mainline_turnover_summary": {
                    "share_trend_label": "逆势试攻",
                    "conclusion": "半导体只是放量杀跌中的局部逆势攻击，不按周期主线切换处理",
                },
                "state_machine": {
                    "style_label": "放量杀跌",
                    "primary_action": "先防踩踏，等指数图形和主攻线承接同时修复后再给买入资格。",
                },
            },
            final_gate={"can_new_entry": False, "should_reduce": True},
        )

        self.assertEqual(position_decision["target_position_pct"], 0)
        self.assertEqual(position_decision["signal_grade"], "0")
        self.assertEqual(position_decision["monthly_rhythm"]["max_position_pct"], 0)
        self.assertIn("局部逆势活跃", position_decision["sizing_reason"])
        self.assertIn("不把局部强势当成参与资格", position_decision["sizing_reason"])
        self.assertNotIn("可执行爆发", position_decision["sizing_reason"])

    def test_prefer_mainline_turnover_summary_keeps_countertrend_over_stale_switch(self):
        stale_switch_summary = {
            "current_mainline": "人形机器人",
            "previous_mainline": "半导体",
            "share_trend_label": "切换",
            "conclusion": "主线切换为人形机器人，旧主线半导体退出中心",
            "data_text": "最近3日主线 电力 -> 半导体 -> 人形机器人；成交额占比 2.3% -> 13.6% -> 2.5%，节奏偏切换",
            "action_text": "只围绕新主线人形机器人重新收缩，不对旧主线做回流预判",
            "mainline_attack_evidence_summary": {
                "attack_state": "confirmed_attack",
                "primary_line": "人形机器人",
                "confirmation_evidence": "人形机器人资金净流入靠前，涨停更集中",
            },
        }
        countertrend_summary = {
            "current_mainline": "人形机器人",
            "previous_mainline": "半导体",
            "share_trend_label": "逆势试攻",
            "conclusion": "人形机器人只是放量杀跌中的观察主攻线，不按周期主线切换处理",
            "data_text": "最近2日主线 半导体 -> 人形机器人；成交额占比 13.6% -> 2.5%，节奏偏逆势试攻",
            "action_text": "人形机器人只按观察主攻线处理，先防踩踏，再看次日是否修复承接",
            "mainline_attack_evidence_summary": {
                "attack_state": "confirmed_attack",
                "primary_line": "人形机器人",
                "confirmation_evidence": "人形机器人资金净流入靠前，涨停更集中",
            },
        }

        self.assertEqual(
            report_runtime._prefer_structured_mainline_turnover_summary(
                stale_switch_summary,
                countertrend_summary,
            )["share_trend_label"],
            "逆势试攻",
        )
        self.assertEqual(
            report_runtime._prefer_structured_mainline_turnover_summary(
                countertrend_summary,
                stale_switch_summary,
            )["share_trend_label"],
            "逆势试攻",
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
                    "extreme_conviction_list": [
                        {"name": "风华高科", "code": "000636", "sector": "元器件"},
                    ],
                    "dragon_rebound_watch_pool": [
                        {"name": "汇源通信", "code": "000586", "sector": "通信设备"},
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
            self.assertEqual(inputs["extreme_conviction_list"][0]["code"], "000636")
            self.assertEqual(inputs["dragon_rebound_watch_pool"][0]["code"], "000586")
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

    def test_render_markdown_report_runtime_derives_appendix_c_from_tuple_a_kill_records(self):
        class _ExecutionAppendixCaptured(RuntimeError):
            pass

        def _run_execution_stages(stage_specs, stage_context=None, stage_lookup=None):
            return {
                "lines": [],
                "module_logs": [],
                "context": {
                    "filtered_by_a_kill": [
                        (
                            {"name": "冷却股", "code": "000003", "sector": "军工"},
                            {"a_kill_date": "2026-04-20", "remaining_days": 20, "reason": "A杀冷却期"},
                        )
                    ],
                },
            }

        def _capture_execution_appendix(payload):
            appendix_c = payload["inputs"]["appendix_c"]
            record = appendix_c["a_kill_elimination_records"][0]
            self.assertEqual(record["stock_name"], "冷却股")
            self.assertEqual(record["stock_code"], "000003")
            self.assertEqual(record["a_kill_date"], "2026-04-20")
            self.assertEqual(record["reason"], "A杀冷却期")
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
            _default_build_entry_cycle_calibrations=lambda as_of_date="": {},
        )

        data = {
            "exchange_monitor_today": [],
            "exchange_monitor_nextday": [],
        }

        with self.assertRaises(_ExecutionAppendixCaptured):
            report_runtime.render_markdown_report_runtime(
                data,
                "2026-04-22",
                helpers=helpers,
                config={},
            )

    def test_appendix_c_downgrades_unconfirmed_core_and_limit_down_watch_items(self):
        payload = report_runtime._build_appendix_c_continuity_payload(
            target_date="2026-05-18",
            execution_stage_context={
                "mainline_name": "",
                "core_stocks": [
                    {
                        "name": "大唐发电",
                        "code": "601991",
                        "sector": "绿色电力",
                        "change_pct": 0.13,
                        "pattern": "震荡整理(0分)",
                        "tmr_forecast": "需看明日竞价强弱",
                    },
                    {
                        "name": "巨力索具",
                        "code": "002342",
                        "sector": "商业航天",
                        "change_pct": -9.98,
                        "pattern": "缩量调整(0分)",
                        "tmr_forecast": "需看明日竞价强弱",
                    },
                ],
            },
        )

        pool = payload["current_stock_monitoring_pool"]
        lifecycle = payload["stock_lifecycle_records"]
        self.assertEqual(pool[0]["source_pool"], "候选观察")
        self.assertEqual(pool[0]["current_action"], "仅观察，等待重新转强")
        self.assertEqual(pool[1]["source_pool"], "风险回避")
        self.assertEqual(pool[1]["current_action"], "跌停/接近跌停，取消明日参与")
        self.assertEqual(lifecycle[1]["current_interpretation"], "跌停/接近跌停，不是明日核心")

    def test_appendix_c_keeps_crossline_identity_when_same_code_also_in_core_pool(self):
        payload = report_runtime._build_appendix_c_continuity_payload(
            target_date="2026-05-28",
            execution_stage_context={
                "mainline_name": "电力",
                "core_stocks": [
                    {
                        "name": "华电能源",
                        "code": "600726",
                        "sector": "电力",
                        "current_action": "继续观察",
                    }
                ],
                "crossline_observation_stocks": [
                    {
                        "name": "华电能源",
                        "code": "600726",
                        "sector": "电力",
                        "current_action": "跨线承接观察",
                    }
                ],
            },
        )

        pool = payload["current_stock_monitoring_pool"]

        self.assertEqual(len([item for item in pool if item["stock_code"] == "600726"]), 1)
        self.assertEqual(pool[0]["source_pool"], "跨线观察")
        self.assertNotEqual(pool[0]["source_pool"], "主线核心")

    def test_appendix_c_relabels_core_item_when_crossline_context_names_it(self):
        payload = report_runtime._build_appendix_c_continuity_payload(
            target_date="2026-05-29",
            execution_stage_context={
                "mainline_name": "电力",
                "core_stocks": [
                    {
                        "name": "金房能源",
                        "code": "001210",
                        "sector": "电力",
                        "current_action": "只观察承接",
                    }
                ],
                "observation_candidates": [
                    {
                        "name": "金房能源",
                        "code": "001210",
                        "watch_anchor_note": "跨线对象（电力），只用于观察强弱，不代表主攻线切换",
                    }
                ],
            },
        )

        pool = payload["current_stock_monitoring_pool"]

        self.assertEqual(pool[0]["stock_code"], "001210")
        self.assertEqual(pool[0]["source_pool"], "跨线观察")

    def test_appendix_c_keeps_core_identity_when_observation_text_is_not_crossline(self):
        payload = report_runtime._build_appendix_c_continuity_payload(
            target_date="2026-05-29",
            execution_stage_context={
                "mainline_name": "电力",
                "core_stocks": [
                    {
                        "name": "金房能源",
                        "code": "001210",
                        "sector": "电力",
                        "current_action": "只观察承接",
                    }
                ],
                "observation_candidates": [
                    {
                        "name": "金房能源",
                        "code": "001210",
                        "watch_anchor_note": "电力核心观察，等待承接确认",
                    }
                ],
            },
        )

        pool = payload["current_stock_monitoring_pool"]

        self.assertEqual(pool[0]["stock_code"], "001210")
        self.assertEqual(pool[0]["source_pool"], "主线核心")

    def test_render_markdown_report_runtime_rebuilds_appendix_c_when_snapshot_has_stale_pool(self):
        class _ExecutionAppendixCaptured(RuntimeError):
            pass

        def _run_execution_stages(stage_specs, stage_context=None, stage_lookup=None):
            return {
                "lines": [],
                "module_logs": [],
                "context": {
                    "mainline_name": "",
                    "core_stocks": [
                        {
                            "name": "大唐发电",
                            "code": "601991",
                            "sector": "绿色电力",
                            "change_pct": 0.13,
                            "pattern": "震荡整理(0分)",
                            "tmr_forecast": "需看明日竞价强弱",
                        },
                        {
                            "name": "巨力索具",
                            "code": "002342",
                            "sector": "商业航天",
                            "change_pct": -9.98,
                            "pattern": "缩量调整(0分)",
                            "tmr_forecast": "需看明日竞价强弱",
                        },
                    ],
                },
            }

        def _capture_execution_appendix(payload):
            appendix_c = payload["inputs"]["appendix_c"]
            pool = appendix_c["current_stock_monitoring_pool"]
            self.assertEqual(pool[0]["source_pool"], "候选观察")
            self.assertEqual(pool[0]["current_action"], "仅观察，等待重新转强")
            self.assertEqual(pool[1]["source_pool"], "风险回避")
            self.assertEqual(pool[1]["current_action"], "跌停/接近跌停，取消明日参与")
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
            _default_build_entry_cycle_calibrations=lambda as_of_date="": {},
        )

        data = {
            "exchange_monitor_today": [],
            "exchange_monitor_nextday": [],
            "appendix_c": {
                "current_stock_monitoring_pool": [
                    {"stock_name": "大唐发电", "stock_code": "601991", "source_pool": "主线核心", "current_action": "需看明日竞价强弱"},
                    {"stock_name": "巨力索具", "stock_code": "002342", "source_pool": "主线核心", "current_action": "需看明日竞价强弱"},
                ],
                "stock_lifecycle_records": [],
                "a_kill_elimination_records": [],
            },
        }

        with self.assertRaises(_ExecutionAppendixCaptured):
            report_runtime.render_markdown_report_runtime(
                data,
                "2026-05-18",
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
            _default_build_entry_cycle_calibrations=lambda as_of_date="": {},
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
                    "position_decision": {
                        "signal_grade": "50",
                        "target_position_pct": 50,
                        "monthly_rhythm": {
                            "month_mode": "ordinary_attack",
                            "month_return_pct": 6.5,
                            "max_position_pct": 100,
                        },
                        "sizing_reason": "月度允许进攻，但仍需唯一对象确认。",
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
        self.assertIn("### 月度攻防与进攻仓位", rendered)
        self.assertIn("| 本月模式 | 普通进攻月 |", rendered)
        self.assertIn("| 进攻仓位三态 | 0% |", rendered)
        self.assertIn("### 1. 周期日历主视图", rendered)
        self.assertIn("[半导体] 接力", rendered)
        self.assertIn("### 4. 主线容量与格局判断", rendered)
        self.assertIn("| 主线容量 | 主线格局 | 主攻线 | 竞争线/背景线 | 主线确认依据 | 板块关系状态 | 主线进程 | 明日动作 |", rendered)
        self.assertNotIn("### 4. 双层主线结论", rendered)
        self.assertIn("### 5. 主线成交额占比趋势", rendered)
        self.assertIn("### 1. 龙虎榜资金状态", rendered)
        self.assertIn("### 1. 个股裁决", rendered)
        self.assertNotIn("### 1. 主线内可执行候选", rendered)
        self.assertIn("### 2. 明日候选观察", rendered)
        self.assertIn("### 3. 备用观察", rendered)
        self.assertIn("| 时间窗口 | 要看什么 | 观察资格 | 卖出/风控 | 结论 |", rendered)
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
        self.assertIn("| 时间窗口 | 要看什么 | 观察资格 | 卖出/风控 | 结论 |", front_page)
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
                execution_framework_text="等参与窗口确认",
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
        self.assertIn(
            "| 周期 | 时间段 | 交易日数 | 攻击线 | 周期阶段 | 传递性 | 市场状态 | 明日验证点 | 周期解读 |",
            summary_result["report"],
        )
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
            DISPLAY_MVP_MODE=False,
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
        self.assertIn(
            "| 周期 | 时间段 | 交易日数 | 攻击线 | 周期阶段 | 传递性 | 市场状态 | 明日验证点 | 周期解读 |",
            rendered,
        )
        self.assertIn("| 近5周期-1 | 04-17 ~ 04-20 | 2日 | 电力 | 已结束周期 | 背景观察 | 强化后退潮 |", rendered)
        self.assertIn("| 当前周期 | 04-21 ~ 04-24 | 3日 | 半导体 | 延续验证 | 待二次验证 | 接力后修复接力 |", rendered)
        self.assertIn("不能由单日攻击自动升级周期主线", rendered)
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
            DISPLAY_MVP_MODE=False,
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
        self.assertIn("| 容量待累计 | 单主线聚焦 | 半导体 | - | 主线确认依据待补充 | 周期主线与当天主攻线一致 | 待观察 | 继续围绕半导体观察承接 |", result["report"])
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

    def test_render_markdown_report_runtime_prefers_structured_attack_summary_over_stale_stage_summary(self):
        from report.front_page_v2_renderer import render_front_page_v2 as _render_front_page_v2_actual
        from report.report_document_builder import build_report_shell_contract as _build_report_shell_contract_actual

        def _run_execution_stages(stage_specs, stage_context=None, stage_lookup=None):
            return {
                "lines": [],
                "module_logs": [],
                "context": {
                    "market_research_snapshot": {
                        "state_machine": {"leading_line": "半导体", "energy_state": "观察"},
                        "mainline_turnover_summary": {
                            "current_mainline": "",
                            "conclusion": "主线待确认，暂不输出成交额占比结论",
                            "mainline_attack_evidence_summary": {
                                "attack_state": "chaotic_rotation",
                                "primary_line": "",
                                "candidate_lines": ["化学制品", "养殖业", "家居用品"],
                                "confirmation_evidence": "多方向局部活跃但资金未明显胜出",
                                "sector_evidence_rows": [
                                    {
                                        "sector_name": "化学制品",
                                        "net_inflow_amount": 3.39,
                                        "net_inflow_rank": 3,
                                        "limit_up_count": 5,
                                        "high_anchor_height": 2,
                                        "turnover_share_change": 0.0,
                                    }
                                ],
                            },
                            "mainline_capacity_regime_summary": {
                                "mainline_capacity": "单线容量",
                                "mainline_regime": "无主线",
                                "primary_line": "暂无",
                                "other_lines": "电力 / 光伏设备",
                                "confirmation_evidence": "多方向局部活跃但资金未明显胜出",
                                "sector_relationship_state": "混沌接力",
                                "mainline_process": "无",
                                "tomorrow_action": "不强行找主线，只保留异常观察",
                            },
                        },
                    },
                    "mainline_turnover_summary": {
                        "current_mainline": "半导体",
                        "conclusion": "主线未切换，半导体仍是中心",
                    },
                    "current_mainline_history_record": {"date": "2026-05-14", "primary_mainline": "半导体", "market_state": "观察"},
                    "recent_mainline_history": [{"date": "2026-05-13", "primary_mainline": "电力", "market_state": "观察"}],
                },
            }

        helpers = _build_runtime_execution_test_helpers(
            _run_execution_stages,
            DISPLAY_MVP_MODE=True,
            build_report_shell_contract=_build_report_shell_contract_actual,
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
            render_front_page_v2=_render_front_page_v2_actual,
        )

        data = {"exchange_monitor_today": [], "exchange_monitor_nextday": []}
        result = report_runtime.render_markdown_report_runtime(data, "2026-05-14", helpers=helpers, config={})

        self.assertEqual(data["mainline_turnover_summary"]["mainline_attack_evidence_summary"]["attack_state"], "chaotic_rotation")
        self.assertIn("| 当前周期 | 05-14 | 1日 | 混沌轮动 | 混沌轮动 | 混沌轮动 |", result["report"])
        self.assertIn("| 单线容量 | 无主线 | 暂无 | 电力 / 光伏设备 | 多方向局部活跃但资金未明显胜出 |", result["report"])
        self.assertIn("| 化学制品 | 候选线 | 第3 | +3.39亿 | 5 | 2 | +0.0pct |", result["report"])
        self.assertNotIn("半导体今日攻击成立", result["report"])
        self.assertNotIn("| 单线容量 | 混沌接力 | 半导体 |", result["report"])

    def test_render_markdown_report_runtime_passes_extreme_conviction_list_to_front_page(self):
        captured = {}

        def _run_execution_stages(stage_specs, stage_context=None, stage_lookup=None):
            return {
                "lines": [],
                "module_logs": [],
                "context": {
                    "market_research_snapshot": {"mainline_turnover_summary": {"current_mainline": "电力"}},
                    "position_decision": {"signal_grade": "50", "target_position_pct": 50},
                    "extreme_conviction_list": [
                        {
                            "name": "大唐发电",
                            "code": "601991",
                            "sector": "电力",
                            "sniper_role": "明日主买对象",
                            "leader_speed_tier": "极致加速龙头",
                            "buy_ma_line": "MA3",
                            "sell_ma_line": "MA5",
                            "acceptance_repair_required": "缩量回撤到MA3附近，站回VWAP",
                            "final_risk_review": {"status": "通过"},
                            "participation_window": "竞价表态 + 回封参与",
                        }
                    ],
                },
            }

        def _capture_front_page(report, **kwargs):
            captured["snapshot"] = kwargs.get("market_research_snapshot") or {}
            return ["# front"]

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
            render_front_page_v2=_capture_front_page,
        )

        report_runtime.render_markdown_report_runtime(
            {"exchange_monitor_today": [], "exchange_monitor_nextday": []},
            "2026-05-21",
            helpers=helpers,
            config={},
        )

        self.assertEqual(captured["snapshot"]["extreme_conviction_list"][0]["code"], "601991")
        self.assertEqual(
            captured["snapshot"]["candidate_snapshot"]["extreme_conviction_list"][0]["sniper_role"],
            "明日主买对象",
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
        self.assertIn("| 容量待累计 | 单主线聚焦 | 半导体 | - | 主线确认依据待补充 | 周期主线与当天主攻线一致 | 待观察 | 继续围绕半导体观察承接 |", result["report"])
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
        self.assertIn("连续走势符合强势标准", result["report"])
        self.assertNotIn("连续 走势", result["report"])

    def test_front_page_target_prefers_zero_position_extreme_observation_over_waiting_layer(self):
        selected = report_runtime._build_front_page_selected_position_candidate(
            {
                "trade_gate_open": False,
                "position_decision": {
                    "participation_mode": "observe_0",
                    "signal_grade": "0",
                    "target_position_pct": 0,
                },
                "best_stock": {"name": "京能电力", "code": "600578", "watch_source": "waiting_layer"},
                "display_observation_candidates": [
                    {"name": "京能电力", "code": "600578", "watch_source": "waiting_layer"},
                ],
                "extreme_conviction_list": [
                    {
                        "name": "华电能源",
                        "code": "600726",
                        "sector": "电力",
                        "source_tier": "extreme_conviction",
                        "attack_state": "0%观察",
                    }
                ],
            }
        )

        self.assertEqual(selected["code"], "600726")
        self.assertIn("回封观察", selected["condition"])
        self.assertNotIn("回封/打板", selected["condition"])

    def test_render_markdown_report_runtime_sanitizes_legacy_surface_words_in_report_and_logs(self):
        def _run_execution_stages(stage_specs, stage_context=None, stage_lookup=None):
            return {
                "lines": [
                    (
                        "当前" + "门" + "控不允许新开仓，"
                        + "执行" + "权关闭；等"
                        + "开" + "闸" + "放" + "行后再看。"
                    ),
                ],
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

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = report_runtime.render_markdown_report_runtime(
                {"exchange_monitor_today": [], "exchange_monitor_nextday": []},
                "2026-04-24",
                helpers=helpers,
                config={},
            )

        combined = result["report"] + "\n" + stdout.getvalue()
        forbidden_terms = (
            "买入" + "权限",
            "执行" + "权",
            "执行" + "权限",
            "门" + "控",
            "闸" + "门",
            "开" + "闸",
            "放" + "行",
        )
        for term in forbidden_terms:
            self.assertNotIn(term, combined)
        self.assertIn("最终执行条件", stdout.getvalue())

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
            data = {"foo": "bar"}
            result = report_runtime.render_markdown_report_runtime(
                data,
                "2026-04-22",
                helpers={"DISPLAY_MVP_MODE": False},
                config={},
            )

        render_mock.assert_called_once()
        self.assertTrue(result["report"].startswith("# runtime report"))
        self.assertIn("## 知识复利候选", result["report"])
        self.assertEqual(data["knowledge"]["llm_wiki"]["source"], "llm_wiki")
        self.assertIn("固定交易窗口条件", data["knowledge"]["llm_wiki"]["report_digest_text"])
        self.assertIn("09:50-10:10窗口", data["knowledge"]["llm_wiki"]["report_digest_text"])
        self.assertIn("process_flows", data["knowledge"]["llm_wiki"])
        self.assertIn("选股形态审美 ASCII 流程图", "\n".join(data["knowledge"]["llm_wiki"]["process_flows"]))
        self.assertIn("knowledge_compounding_candidates", data["knowledge"]["llm_wiki"])
        self.assertEqual(result["artifacts"]["llm_wiki"]["version"], data["knowledge"]["llm_wiki"]["version"])

    def test_render_markdown_report_runtime_attaches_knowledge_hits_from_facts(self):
        with patch("report.runtime._render_markdown_report_legacy_body", return_value="# runtime report"):
            data = {
                "knowledge_hit_facts": {
                    "market": {
                        "index_trend": "上涨",
                        "breadth": "上涨家数偏弱",
                        "turnover_distribution": "成交集中",
                    }
                }
            }
            result = report_runtime.render_markdown_report_runtime(
                data,
                "2026-05-29",
                helpers={"DISPLAY_MVP_MODE": False},
                config={},
            )

        hits = data["knowledge"]["llm_wiki"]["knowledge_hits"]
        self.assertEqual(hits[0]["knowledge_id"], "market.low-frequency-focus")
        self.assertIn("指数上涨", hits[0]["triggered_by"])
        self.assertIn("## 经验库命中", result["report"])
        self.assertIn("| 指数强但赚钱效应弱 | 指数上涨；上涨家数偏弱；成交集中 |", result["report"])
        self.assertEqual(result["artifacts"]["llm_wiki"]["knowledge_hits"], hits)

    def test_render_markdown_report_runtime_derives_market_structure_knowledge_hits(self):
        data = {
            "indices": {"创业板指": {"涨跌幅": 1.2}},
            "total_turnover": 32600.0,
            "market_stats": {"up_count": 947, "down_count": 4300},
            "market_research_snapshot": {
                "market_structure_inputs": {
                    "opposition_rotation": ["消费", "白酒"],
                    "old_mainline": "科技",
                    "old_mainline_fatigue": True,
                }
            },
        }

        with patch("report.runtime._render_markdown_report_legacy_body", return_value="# runtime report"):
            result = report_runtime.render_markdown_report_runtime(
                data,
                "2026-05-29",
                helpers={"DISPLAY_MVP_MODE": False},
                config={},
            )

        hits = data["knowledge"]["llm_wiki"]["knowledge_hits"]
        self.assertEqual(hits[0]["knowledge_id"], "market.low-frequency-focus")
        self.assertIn("指数上涨", hits[0]["triggered_by"])
        self.assertIn("上涨家数偏弱", hits[0]["triggered_by"])
        self.assertIn("成交集中", hits[0]["triggered_by"])
        self.assertIn("## 经验库命中", result["report"])

    def test_render_markdown_report_runtime_derives_account_and_candidate_knowledge_hits(self):
        data = {
            "account_profile": {
                "cash_available": 9800,
                "capital_text": "约1w账户",
            },
            "selected_position_candidate": {
                "name": "强核心",
                "identity": "市场核心",
                "one_lot_amount": 18000,
                "action_limit": "核心观察",
                "risk_items": ["公告风险待确认"],
                "recover_condition": "重新站回MA5",
                "drop_condition": "跌破MA10",
            },
        }

        with patch("report.runtime._render_markdown_report_legacy_body", return_value="# runtime report"):
            result = report_runtime.render_markdown_report_runtime(
                data,
                "2026-05-29",
                helpers={"DISPLAY_MVP_MODE": False},
                config={},
            )

        ids = [hit["knowledge_id"] for hit in data["knowledge"]["llm_wiki"]["knowledge_hits"]]
        self.assertIn("account.unbuyable-core-anchor", ids)
        self.assertIn("candidate.quality-action-layer", ids)
        self.assertIn("实际不可买不降低市场身份", result["report"])
        self.assertIn("先挣分、再扣分、再看动作上限", result["report"])

    def test_runtime_front_page_uses_account_knowledge_hit_for_real_action(self):
        from report.report_document_builder import (
            build_report_shell_contract as _build_report_shell_contract_actual,
            replace_placeholder_lines as _replace_placeholder_lines_actual,
        )

        selected_candidate = {
            "name": "强核心",
            "code": "000001",
            "sector": "半导体",
            "identity": "市场核心",
            "one_lot_amount": 18000,
        }
        position_decision = {
            "signal_grade": "50",
            "target_position_pct": 50,
        }
        data = {
            "personal_position_context": {
                "account_profile": {
                    "cash_available": 9800,
                    "capital_text": "约1w账户",
                },
                "existing_position_summary": {
                    "has_position": False,
                },
            },
            "market_research_snapshot": {
                "position_decision": position_decision,
            },
        }

        def _run_execution_stages(stage_specs, stage_context=None, stage_lookup=None):
            return {
                "lines": [],
                "module_logs": [],
                "context": {
                    "market_research_snapshot": {
                        "selected_position_candidate": selected_candidate,
                        "position_decision": position_decision,
                    },
                    "selected_position_candidate": selected_candidate,
                    "position_decision": position_decision,
                },
            }

        helpers = _build_runtime_execution_test_helpers(
            _run_execution_stages,
            DISPLAY_MVP_MODE=False,
            EMIT_HELPER_DIAGNOSTICS=False,
            build_report_shell_contract=_build_report_shell_contract_actual,
            replace_placeholder_lines=_replace_placeholder_lines_actual,
            build_legacy_final_conclusion_lines=lambda *args, **kwargs: [],
            render_context_tail_sections=lambda *args, **kwargs: [],
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
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = report_runtime.render_markdown_report_runtime(
                data,
                "2026-05-29",
                helpers=helpers,
                config={},
            )

        report = result["report"]
        self.assertIn("| 明日动作 | 当前账户不参与；强核心仍保留市场核心观察 |", report)
        self.assertIn("| 观察对象 | 强核心(000001)：当前账户买不了一手，只保留观察 |", report)
        self.assertIn("| T0对象 | 无昨日持仓，不涉及T0 |", report)
        self.assertNotIn("| T0主对象 | 强核心(000001)：当前账户买不了一手，只保留观察 |", report)
        self.assertIn("| 新增参与上限 | 0 |", report)
        self.assertIn("| 经验库依据 | 实际不可买不降低市场身份 |", report)
        self.assertIn("| 当前状态 | 0%条件观察 |", report)
        self.assertIn("| 明日观察动作 | 标的 | 观察窗 | 条件 | 不满足怎么办 |", report)
        self.assertIn("| 0%不参与 | 不确定时不值得主动参与 |", report)
        self.assertNotIn("50%标准进攻，只做预演命中的合格对象", report)
        self.assertIn("最终执行条件: 观察", stdout.getvalue())
        self.assertNotIn("最终执行条件: 明日目标标的保留条件50%预演", stdout.getvalue())

    def test_render_markdown_report_runtime_appends_ai_friction_knowledge_note_when_requested(self):
        with patch("report.runtime._render_markdown_report_legacy_body", return_value="# runtime report"):
            data = {
                "knowledge_updates": [
                    {
                        "topic": "AI摩擦与知识复利",
                        "source_path": "wiki/交易思想/AI摩擦与知识复利.md",
                    }
                ]
            }
            result = report_runtime.render_markdown_report_runtime(
                data,
                "2026-05-26",
                helpers={"DISPLAY_MVP_MODE": False},
                config={},
            )

        report = result["report"]
        self.assertIn("## 知识复利提示", report)
        self.assertIn("复利方向：用反馈机制校准新知识，避免只堆积结论。", report)
        self.assertIn("必要认知摩擦：复述、重写、对比或沉淀成知识节点。", report)
        self.assertIn("日报落点：只记录字段化结论，不把文章长文带入交易主链。", report)
        self.assertNotIn("摩擦是资产不是成本", report)
        self.assertNotIn("认知投降", report)

    def test_render_markdown_report_runtime_attaches_market_structure_and_knowledge_update(self):
        def _legacy_body(data, target_date, **kwargs):
            snapshot = data["market_research_snapshot"]
            return "\n".join(
                render_front_page_v2(
                    ["## 二、市场基底", "### 1. 指数与市场底色"],
                    target_date=target_date,
                    market_research_snapshot=snapshot,
                )
            )

        data = {
            "indices": {"创业板指": {"涨跌幅": 1.2}},
            "total_turnover": 32600.0,
            "market_stats": {"up_count": 947, "down_count": 4300},
            "market_research_snapshot": {
                "market_structure_inputs": {
                    "opposition_rotation": ["消费", "白酒"],
                    "old_mainline": "科技",
                    "old_mainline_fatigue": True,
                },
                "mainline_turnover_summary": {"current_mainline": "科技"},
            },
        }

        with patch("report.runtime._render_markdown_report_legacy_body", side_effect=_legacy_body):
            result = report_runtime.render_markdown_report_runtime(
                data,
                "2026-05-27",
                helpers={"DISPLAY_MVP_MODE": False},
                config={},
            )

        report = result["report"]
        self.assertIn("### 3. 市场结构判断", report)
        self.assertIn("低频聚焦", report)
        self.assertIn("## 知识复利提示", report)
        self.assertIn("新增判断：指数新高不等于真实赚钱效应改善", report)
        self.assertEqual(data["market_structure_judgement"]["tomorrow_rhythm"], "低频聚焦")

    def test_render_markdown_report_runtime_normalizes_non_list_knowledge_updates(self):
        data = {
            "indices": {"创业板指": {"涨跌幅": 1.2}},
            "total_turnover": 32600.0,
            "market_stats": {"up_count": 947, "down_count": 4300},
            "knowledge_updates": {"topic": "旧格式"},
            "market_research_snapshot": {
                "market_structure_inputs": {
                    "opposition_rotation": ["消费", "白酒"],
                    "old_mainline": "科技",
                    "old_mainline_fatigue": True,
                }
            },
        }

        with patch("report.runtime._render_markdown_report_legacy_body", return_value="# runtime report"):
            result = report_runtime.render_markdown_report_runtime(
                data,
                "2026-05-27",
                helpers={"DISPLAY_MVP_MODE": False},
                config={},
            )

        report = result["report"]
        self.assertIsInstance(data["knowledge_updates"], list)
        self.assertEqual(data["knowledge_updates"][0]["topic"], "市场结构判断")
        self.assertIn("## 知识复利提示", report)
        self.assertIn("新增判断：指数新高不等于真实赚钱效应改善", report)

    def test_attach_market_structure_restores_existing_judgement_to_replaced_snapshot(self):
        data = {
            "indices": {"创业板指": {"涨跌幅": 1.2}},
            "total_turnover": 32600.0,
            "market_stats": {"up_count": 947, "down_count": 4300},
            "market_research_snapshot": {
                "market_structure_inputs": {
                    "opposition_rotation": ["消费", "白酒"],
                    "old_mainline": "科技",
                    "old_mainline_fatigue": True,
                },
                "mainline_turnover_summary": {"current_mainline": "科技"},
            },
        }

        first_judgement = report_runtime._attach_market_structure_judgement(data)
        data["market_research_snapshot"] = {
            "mainline_turnover_summary": {"current_mainline": "科技"},
            "position_decision": {"signal_grade": "50"},
            "front_page_final_gate": {"final_action": "观察"},
        }

        restored_judgement = report_runtime._attach_market_structure_judgement(data)
        rendered = "\n".join(
            render_front_page_v2(
                ["## 二、市场基底", "### 1. 指数与市场底色"],
                target_date="2026-05-27",
                market_research_snapshot=data["market_research_snapshot"],
            )
        )

        self.assertIs(restored_judgement, first_judgement)
        self.assertIs(data["market_research_snapshot"]["market_structure_judgement"], first_judgement)
        self.assertIn("### 3. 市场结构判断", rendered)
        self.assertIn("低频聚焦", rendered)
        self.assertEqual(
            [item["topic"] for item in data["knowledge_updates"] if isinstance(item, dict)],
            ["市场结构判断"],
        )

    def test_render_markdown_report_runtime_appends_knowledge_compounding_candidates(self):
        with patch("report.runtime._render_markdown_report_legacy_body", return_value="# runtime report"):
            result = report_runtime.render_markdown_report_runtime(
                {},
                "2026-05-26",
                helpers={"DISPLAY_MVP_MODE": False},
                config={},
            )

        report = result["report"]
        self.assertIn("## 知识复利候选", report)
        self.assertIn("AI摩擦与知识复利 + 判断样本与市场演变", report)
        self.assertIn("待确认", report)
        self.assertIn("判断样本是日报里的反馈机制，用来把 AI 省掉的认知摩擦补回来。", report)
        self.assertIn("只进入知识复利候选，不自动写入正式 wiki，不改变交易动作。", report)
        self.assertNotIn("摩擦是资产不是成本", report)
        self.assertNotIn("认知投降", report)

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

        self.assertTrue(result["report"].startswith("# Runtime Report 2026-04-22"))

    def test_runtime_decision_ledger_hook_builds_and_writes_when_enabled(self):
        captured = {}

        def _fake_build_snapshot(**kwargs):
            captured["build"] = kwargs
            return {"trade_date": kwargs["trade_date"], "cases": []}

        def _fake_write_snapshot(snapshot, *, root_dir="."):
            captured["write"] = {"snapshot": snapshot, "root_dir": root_dir}
            return {"snapshot_path": "data/decision-ledger/2026-05-12.json"}

        previous = report_runtime._install_runtime_bindings(
            {
                "persist_decision_ledger": True,
                "decision_ledger_root_dir": "/tmp/decision-ledger-root",
                "build_decision_ledger_snapshot": _fake_build_snapshot,
                "write_decision_ledger_artifacts": _fake_write_snapshot,
            }
        )
        try:
            result = report_runtime._maybe_persist_decision_ledger(
                data={"source_report": {"path": "reports/2026-05-12_A股日报_完整版.md", "variant": "full"}},
                target_date="2026-05-12",
                execution_stage_context={
                    "extreme_conviction_list": [
                        {
                            "code": "601991",
                            "name": "大唐发电",
                            "sector": "电力",
                            "conviction_reason": "趋势辨识度高",
                        }
                    ],
                    "mainline_turnover_summary": {"relationship": "混沌接力"},
                },
                market_research_snapshot={"market_branch": "指数高位停顿轮动"},
            )
        finally:
            report_runtime._restore_runtime_bindings(previous)

        self.assertEqual(result["snapshot_path"], "data/decision-ledger/2026-05-12.json")
        self.assertEqual(captured["build"]["trade_date"], "2026-05-12")
        self.assertEqual(captured["build"]["market_branch"], "指数高位停顿轮动")
        self.assertEqual(captured["build"]["sector_relationship_state"], "混沌接力")
        self.assertEqual(captured["build"]["extreme_conviction_list"][0]["code"], "601991")
        self.assertEqual(captured["write"]["root_dir"], "/tmp/decision-ledger-root")

    def test_runtime_decision_ledger_postgres_only_disables_json_archive_and_local_review_files(self):
        captured = {}

        def _fake_build_snapshot(**kwargs):
            return {"trade_date": kwargs["trade_date"], "cases": []}

        def _fake_write_snapshot(snapshot, **kwargs):
            captured["write"] = kwargs
            return {"snapshot_path": "postgresql://decision-ledger/2026-05-12", "index": {}}

        previous = report_runtime._install_runtime_bindings(
            {
                "persist_decision_ledger": True,
                "decision_ledger_postgres_only": True,
                "decision_ledger_root_dir": "/tmp/decision-ledger-root",
                "build_decision_ledger_snapshot": _fake_build_snapshot,
                "write_decision_ledger_artifacts": _fake_write_snapshot,
            }
        )
        try:
            report_runtime._maybe_persist_decision_ledger(
                data={},
                target_date="2026-05-12",
                execution_stage_context={"extreme_conviction_list": []},
                market_research_snapshot={},
            )
        finally:
            report_runtime._restore_runtime_bindings(previous)

        self.assertFalse(captured["write"]["write_json_archive"])
        self.assertEqual(captured["write"]["review_market_facts_by_stock_code"], {})

    def test_runtime_candidate_trace_hook_writes_when_enabled(self):
        captured = {}

        def _fake_write_candidate_trace_artifact(**kwargs):
            captured["write"] = kwargs
            return {
                "artifact_path": "data/candidate-traces/2026-05-12.json",
                "trace_count": len(kwargs.get("traces") or []),
            }

        previous = report_runtime._install_runtime_bindings(
            {
                "persist_candidate_traces": True,
                "candidate_trace_root_dir": "/tmp/candidate-trace-root",
                "write_candidate_trace_artifact": _fake_write_candidate_trace_artifact,
            }
        )
        try:
            result = report_runtime._maybe_persist_candidate_traces(
                data={"source_report": {"path": "reports/2026-05-12_A股日报_完整版.md", "variant": "full"}},
                target_date="2026-05-12",
                execution_stage_context={
                    "candidate_traces": [{"stock_code": "002185", "tier": "T0"}],
                    "candidate_trace_eliminated_summary": [
                        {"reason": "主线不匹配", "count": 1, "representatives": ["大众公用"]}
                    ],
                },
            )
        finally:
            report_runtime._restore_runtime_bindings(previous)

        self.assertEqual(result["artifact_path"], "data/candidate-traces/2026-05-12.json")
        self.assertEqual(captured["write"]["trade_date"], "2026-05-12")
        self.assertEqual(captured["write"]["traces"][0]["stock_code"], "002185")
        self.assertEqual(captured["write"]["eliminated_summary"][0]["reason"], "主线不匹配")
        self.assertEqual(captured["write"]["root_dir"], "/tmp/candidate-trace-root")

    def test_runtime_candidate_trace_hook_builds_default_source_report(self):
        captured = {}

        def _fake_write_candidate_trace_artifact(**kwargs):
            captured["write"] = kwargs
            return {"artifact_path": "data/candidate-traces/2026-05-12.json"}

        previous = report_runtime._install_runtime_bindings(
            {
                "persist_candidate_traces": True,
                "candidate_trace_root_dir": "/tmp/candidate-trace-root",
                "write_candidate_trace_artifact": _fake_write_candidate_trace_artifact,
            }
        )
        try:
            report_runtime._maybe_persist_candidate_traces(
                data={},
                target_date="2026-05-12",
                execution_stage_context={
                    "candidate_traces": [{"stock_code": "002185", "tier": "T0"}],
                    "candidate_trace_eliminated_summary": [],
                },
                run_mode="replay",
            )
        finally:
            report_runtime._restore_runtime_bindings(previous)

        self.assertEqual(
            captured["write"]["source_report"],
            {"path": "reports/replay/2026-05-12_A股日报_完整版_replay.md", "variant": "full"},
        )

    def test_runtime_candidate_trace_hook_marks_postgres_only(self):
        captured = {}

        def _fake_write_candidate_trace_artifact(**kwargs):
            captured["write"] = kwargs
            return {"artifact_path": "postgresql://candidate-traces/2026-05-12"}

        previous = report_runtime._install_runtime_bindings(
            {
                "persist_candidate_traces": True,
                "candidate_trace_root_dir": "/tmp/candidate-trace-root",
                "write_candidate_trace_artifact": _fake_write_candidate_trace_artifact,
            }
        )
        try:
            report_runtime._maybe_persist_candidate_traces(
                data={"postgres_only": True},
                target_date="2026-05-12",
                execution_stage_context={
                    "candidate_traces": [{"stock_code": "002185", "tier": "T0"}],
                    "candidate_trace_eliminated_summary": [],
                },
                run_mode="replay",
            )
        finally:
            report_runtime._restore_runtime_bindings(previous)

        self.assertTrue(captured["write"]["postgres_only"])

    def test_runtime_loads_recent_extreme_mentions_before_candidate_selection(self):
        captured = {}

        def _run_execution_stages(stage_specs, stage_context=None, stage_lookup=None):
            stage_data = (stage_context or {}).get("data") or {}
            captured["recent_mentions"] = list(stage_data.get("recent_extreme_conviction_mentions") or [])
            return {"lines": [], "module_logs": [], "context": {}}

        def query_rows(root_dir=".", end_date="", window_days=25):
            captured["query"] = {
                "root_dir": root_dir,
                "end_date": end_date,
                "window_days": window_days,
            }
            return [
                {
                    "mention_trade_date": "2026-05-11",
                    "stock_code": "002975",
                    "stock_name": "博杰股份",
                    "sector_candidate": "机器人",
                    "source_section": "极度看好名单",
                    "buy_window": "09:50-10:10",
                }
            ]

        helpers = _build_runtime_execution_test_helpers(
            _run_execution_stages,
            persist_decision_ledger=False,
            decision_ledger_root_dir="/tmp/decision-ledger-root",
            query_extreme_conviction_mention_rows_for_tracking=query_rows,
            build_legacy_final_conclusion_lines=lambda *args, **kwargs: [],
            render_supplementary_perspective_section=lambda *args, **kwargs: [],
            render_ai_market_insight_section=lambda *args, **kwargs: [],
            _build_strategy_factor_snapshot=lambda *args, **kwargs: {},
            _build_strategy_plan_context=lambda *args, **kwargs: {},
            update_strategy_performance_book=lambda *args, **kwargs: {},
            _normalize_report_timer_steps=lambda *args, **kwargs: [],
            render_execution_appendix=lambda *args, **kwargs: [],
            render_front_page_v2=lambda report, **kwargs: ["# front"],
        )

        report_runtime.render_markdown_report_runtime(
            {"exchange_monitor_today": [], "exchange_monitor_nextday": []},
            "2026-05-21",
            helpers=helpers,
            config={},
        )

        self.assertEqual(captured["query"]["root_dir"], "/tmp/decision-ledger-root")
        self.assertEqual(captured["query"]["end_date"], "2026-05-21")
        self.assertEqual(captured["query"]["window_days"], 25)
        self.assertEqual(captured["recent_mentions"][0]["stock_code"], "002975")

    def test_runtime_loads_eliminated_recent_extreme_mentions_for_destination_review(self):
        captured = {"include_calls": []}

        def _run_execution_stages(stage_specs, stage_context=None, stage_lookup=None):
            stage_data = (stage_context or {}).get("data") or {}
            captured["active_mentions"] = list(stage_data.get("recent_extreme_conviction_mentions") or [])
            captured["review_mentions"] = list(stage_data.get("recent_extreme_conviction_mentions_for_review") or [])
            return {"lines": [], "module_logs": [], "context": {}}

        def query_rows(root_dir=".", end_date="", window_days=25, include_a_kill=False):
            captured["include_calls"].append(bool(include_a_kill))
            active = {
                "mention_trade_date": "2026-05-20",
                "stock_code": "603005",
                "stock_name": "晶方科技",
                "source_section": "极度看好名单",
                "is_a_kill_eliminated": False,
            }
            eliminated = {
                "mention_trade_date": "2026-05-19",
                "stock_code": "000586",
                "stock_name": "汇源通信",
                "source_section": "极度看好名单",
                "is_a_kill_eliminated": True,
            }
            return [active, eliminated] if include_a_kill else [active]

        helpers = _build_runtime_execution_test_helpers(
            _run_execution_stages,
            persist_decision_ledger=False,
            decision_ledger_root_dir="/tmp/decision-ledger-root",
            query_extreme_conviction_mention_rows_for_tracking=query_rows,
            build_legacy_final_conclusion_lines=lambda *args, **kwargs: [],
            render_supplementary_perspective_section=lambda *args, **kwargs: [],
            render_ai_market_insight_section=lambda *args, **kwargs: [],
            _build_strategy_factor_snapshot=lambda *args, **kwargs: {},
            _build_strategy_plan_context=lambda *args, **kwargs: {},
            update_strategy_performance_book=lambda *args, **kwargs: {},
            _normalize_report_timer_steps=lambda *args, **kwargs: [],
            render_execution_appendix=lambda *args, **kwargs: [],
            render_front_page_v2=lambda report, **kwargs: ["# front"],
        )

        report_runtime.render_markdown_report_runtime(
            {"exchange_monitor_today": [], "exchange_monitor_nextday": []},
            "2026-05-21",
            helpers=helpers,
            config={},
        )

        self.assertIn(True, captured["include_calls"])
        self.assertEqual([item["stock_code"] for item in captured["active_mentions"]], ["603005"])
        self.assertEqual({item["stock_code"] for item in captured["review_mentions"]}, {"603005", "000586"})

    def test_recent_extreme_loader_refreshes_review_rows_when_active_mentions_already_exist(self):
        captured = {"include_calls": []}

        def query_rows(root_dir=".", end_date="", window_days=25, include_a_kill=False):
            captured["include_calls"].append(bool(include_a_kill))
            return [
                {"stock_code": "603005", "stock_name": "晶方科技", "is_a_kill_eliminated": False},
                {"stock_code": "000586", "stock_name": "汇源通信", "is_a_kill_eliminated": True},
            ]

        previous = report_runtime._install_runtime_bindings(
            {"query_extreme_conviction_mention_rows_for_tracking": query_rows}
        )
        try:
            data = {
                "recent_extreme_conviction_mentions": [
                    {"stock_code": "603005", "stock_name": "晶方科技"}
                ]
            }
            report_runtime._load_recent_extreme_conviction_mentions_for_selection(
                data,
                root_dir="/tmp/decision-ledger-root",
                target_date="2026-05-21",
            )
        finally:
            report_runtime._restore_runtime_bindings(previous)

        self.assertIn(True, captured["include_calls"])
        self.assertEqual([item["stock_code"] for item in data["recent_extreme_conviction_mentions"]], ["603005"])
        self.assertEqual(
            {item["stock_code"] for item in data["recent_extreme_conviction_mentions_for_review"]},
            {"603005", "000586"},
        )

    def test_runtime_appends_extreme_conviction_tracking_table_after_ledger_write(self):
        captured = {}

        def _fake_build_snapshot(**kwargs):
            captured["build"] = kwargs
            return {"trade_date": kwargs["trade_date"], "cases": []}

        def _fake_write_snapshot(snapshot, *, root_dir="."):
            captured["write"] = {"snapshot": snapshot, "root_dir": root_dir}
            return {
                "snapshot_path": "data/decision-ledger/2026-05-12.json",
                "index": {
                    "by_stock_code": {
                        "600578": [
                            {
                                "stock_code": "600578",
                                "stock_name": "京能电力",
                                "cycle_start_trade_date": "2026-05-11",
                                "latest_trade_date": "2026-05-12",
                                "cycle_day": 2,
                                "cycle_length_trade_days": 25,
                                "cycle_closed": False,
                                "planned_participation": {
                                    "source_tier": "extreme_conviction",
                                    "participation_window": "竞价表态 + 回封参与",
                                    "buy_window": "09:30-09:35",
                                    "ma20_invalidation": "有效跌破日K MA20取消幻想",
                                },
                                "participation_review_status": "预演命中",
                                "participation_review": {"status": "预演命中", "next_action": "次日看是否继续强于市场"},
                                "mentions": [{"mention_trade_date": "2026-05-11", "source_section": "极度看好名单"}],
                            }
                        ]
                    }
                },
            }

        def _run_execution_stages(stage_specs, stage_context=None, stage_lookup=None):
            return {
                "lines": [],
                "module_logs": [],
                "context": {
                    "extreme_conviction_list": [{"code": "600578", "name": "京能电力", "sector": "电力", "conviction_reason": "板块锚定龙"}],
                },
            }

        helpers = _build_runtime_execution_test_helpers(
            _run_execution_stages,
            build_decision_ledger_snapshot=_fake_build_snapshot,
            write_decision_ledger_artifacts=_fake_write_snapshot,
            persist_decision_ledger=True,
            decision_ledger_root_dir="/tmp/decision-ledger-root",
            build_report_shell_contract=lambda *args, **kwargs: {"report": []},
            build_market_trend_sections_contract=lambda *args, **kwargs: {"lines": []},
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
            render_front_page_v2=lambda report, **kwargs: ["# front"],
        )

        result = report_runtime.render_markdown_report_runtime(
            {"exchange_monitor_today": [], "exchange_monitor_nextday": []},
            "2026-05-12",
            helpers=helpers,
            config={},
        )
        rendered = result["report"]

        self.assertIn("**重点观察25日跟踪表**", rendered)
        self.assertIn("**明日极度看好近25日跟踪表**", rendered)
        self.assertIn("**重点观察历史回测表**", rendered)
        self.assertIn("| 京能电力 | 600578 | D2/25 | 2026-05-11 | 2026-05-12 | 竞价表态 + 回封观察 | 09:30-09:35 | 预演命中 | 次日看是否继续强于市场 | 有效跌破日K MA20取消幻想 |", rendered)
        self.assertIn("| 2026-05-11 | 京能电力 | 600578 |", rendered)
        self.assertIn("| 2026-05-11 | 京能电力 | 600578 |", rendered)
        self.assertEqual(captured["write"]["root_dir"], "/tmp/decision-ledger-root")

    def test_runtime_persists_extreme_conviction_from_market_snapshot_when_stage_context_lacks_top_level_list(self):
        captured = {}

        def _fake_build_snapshot(**kwargs):
            captured["build"] = kwargs
            return {"trade_date": kwargs["trade_date"], "cases": []}

        def _fake_write_snapshot(snapshot, *, root_dir="."):
            captured["write"] = {"snapshot": snapshot, "root_dir": root_dir}
            return {"snapshot_path": "data/decision-ledger/2026-05-20.json", "index": {}}

        def _run_execution_stages(stage_specs, stage_context=None, stage_lookup=None):
            return {
                "lines": [],
                "module_logs": [],
                "context": {
                    "market_research_snapshot": {
                        "candidate_snapshot": {
                            "extreme_conviction_list": [
                                {
                                    "code": "603005",
                                    "name": "晶方科技",
                                    "sector": "半导体",
                                    "sniper_role": "明日主买对象",
                                    "leader_speed_tier": "极致加速龙头",
                                }
                            ]
                        }
                    }
                },
            }

        helpers = _build_runtime_execution_test_helpers(
            _run_execution_stages,
            build_decision_ledger_snapshot=_fake_build_snapshot,
            write_decision_ledger_artifacts=_fake_write_snapshot,
            persist_decision_ledger=True,
            decision_ledger_root_dir="/tmp/decision-ledger-root",
            build_report_shell_contract=lambda *args, **kwargs: {"report": []},
            build_market_trend_sections_contract=lambda *args, **kwargs: {"lines": []},
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
            render_front_page_v2=lambda report, **kwargs: ["# front"],
        )
        data = {"exchange_monitor_today": [], "exchange_monitor_nextday": []}

        report_runtime.render_markdown_report_runtime(
            data,
            "2026-05-20",
            helpers=helpers,
            config={},
        )

        self.assertEqual(captured["build"]["extreme_conviction_list"][0]["code"], "603005")
        self.assertEqual(data["extreme_conviction_list"][0]["sniper_role"], "候选观察")
        self.assertEqual(data["execution_stage_context"]["extreme_conviction_list"][0]["code"], "603005")

    def test_runtime_downgrades_structured_extreme_conviction_when_final_position_is_zero(self):
        captured = {}

        def _fake_build_snapshot(**kwargs):
            captured["build"] = kwargs
            return {"trade_date": kwargs["trade_date"], "cases": []}

        def _fake_write_snapshot(snapshot, *, root_dir="."):
            captured["write"] = {"snapshot": snapshot, "root_dir": root_dir}
            return {"snapshot_path": "data/decision-ledger/2026-05-21.json", "index": {}}

        def _run_execution_stages(stage_specs, stage_context=None, stage_lookup=None):
            return {
                "lines": [],
                "module_logs": [],
                "context": {
                    "market_research_snapshot": {"mainline_turnover_summary": {"current_mainline": "汽车配件"}},
                    "position_decision": {
                        "signal_grade": "0",
                        "target_position_pct": 0,
                        "participation_mode": "observe_0",
                    },
                    "extreme_conviction_list": [
                        {
                            "code": "002703",
                            "name": "浙江世宝",
                            "sector": "汽车配件",
                            "sniper_role": "明日主买对象",
                            "reason": "明日主买对象 / 极致加速龙头",
                            "stock_setup": "明日主买对象 / 极致加速龙头",
                            "source_tier": "ordinary_watch",
                            "planned_participation": {"source_tier": "ordinary_watch"},
                            "primary_buy_candidate": True,
                            "backup_buy_candidate": False,
                        },
                        {
                            "code": "600936",
                            "name": "北投科技",
                            "sector": "软件服务",
                            "sniper_role": "明日补位对象",
                            "reason": "明日补位对象 / 极致加速龙头",
                            "stock_setup": "明日补位对象 / 极致加速龙头",
                            "primary_buy_candidate": False,
                            "backup_buy_candidate": True,
                        },
                    ],
                    "step2_bundle": {
                        "extreme_conviction_list": [
                            {
                                "code": "002703",
                                "name": "浙江世宝",
                                "sector": "汽车配件",
                                "sniper_role": "明日主买对象",
                                "reason": "明日主买对象 / 极致加速龙头",
                                "stock_setup": "明日主买对象 / 极致加速龙头",
                                "primary_buy_candidate": True,
                                "backup_buy_candidate": False,
                            },
                            {
                                "code": "600936",
                                "name": "北投科技",
                                "sector": "软件服务",
                                "sniper_role": "明日补位对象",
                                "reason": "明日补位对象 / 极致加速龙头",
                                "stock_setup": "明日补位对象 / 极致加速龙头",
                                "primary_buy_candidate": False,
                                "backup_buy_candidate": True,
                            },
                        ],
                    },
                },
            }

        helpers = _build_runtime_execution_test_helpers(
            _run_execution_stages,
            build_decision_ledger_snapshot=_fake_build_snapshot,
            write_decision_ledger_artifacts=_fake_write_snapshot,
            persist_decision_ledger=True,
            decision_ledger_root_dir="/tmp/decision-ledger-root",
            build_report_shell_contract=lambda *args, **kwargs: {"report": []},
            build_market_trend_sections_contract=lambda *args, **kwargs: {"lines": []},
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
            render_front_page_v2=lambda report, **kwargs: ["# front"],
        )
        data = {"exchange_monitor_today": [], "exchange_monitor_nextday": []}

        report_runtime.render_markdown_report_runtime(
            data,
            "2026-05-21",
            helpers=helpers,
            config={},
        )

        self.assertEqual([item["sniper_role"] for item in data["extreme_conviction_list"]], ["候选观察", "候选观察补充"])
        self.assertFalse(data["extreme_conviction_list"][0]["primary_buy_candidate"])
        self.assertFalse(data["extreme_conviction_list"][1]["backup_buy_candidate"])
        self.assertEqual(
            captured["build"]["extreme_conviction_list"][0]["zero_position_role_original"],
            "明日主买对象",
        )
        self.assertEqual(
            data["market_research_snapshot"]["candidate_snapshot"]["extreme_conviction_list"][1]["sniper_role"],
            "候选观察补充",
        )
        self.assertEqual(
            [
                item["sniper_role"]
                for item in data["execution_stage_context"]["step2_bundle"]["extreme_conviction_list"]
            ],
            ["候选观察", "候选观察补充"],
        )
        self.assertEqual(
            data["execution_stage_context"]["step2_bundle"]["extreme_conviction_list"][0]["execution_eligibility"],
            "observation_only",
        )
        self.assertEqual(
            data["execution_stage_context"]["step2_bundle"]["extreme_conviction_list"][0]["source_tier"],
            "extreme_conviction",
        )
        self.assertEqual(
            captured["build"]["extreme_conviction_list"][0]["source_tier"],
            "extreme_conviction",
        )
        self.assertEqual(
            captured["build"]["extreme_conviction_list"][0]["execution_eligibility"],
            "observation_only",
        )
        self.assertEqual(
            captured["build"]["extreme_conviction_list"][0]["attack_state"],
            "0%观察",
        )
        self.assertEqual(
            data["execution_stage_context"]["step2_bundle"]["extreme_conviction_list"][0]["reason"],
            "候选观察 / 极致加速龙头",
        )
        self.assertEqual(
            data["execution_stage_context"]["step2_bundle"]["extreme_conviction_list"][1]["stock_setup"],
            "候选观察补充 / 极致加速龙头",
        )

    def test_runtime_replay_can_render_tracking_table_from_existing_ledger_index(self):
        def _run_execution_stages(stage_specs, stage_context=None, stage_lookup=None):
            return {"lines": [], "module_logs": [], "context": {}}

        def _fake_load_index(path):
            return {
                "by_stock_code": {
                    "600578": [
                        {
                            "stock_code": "600578",
                            "stock_name": "京能电力",
                            "cycle_start_trade_date": "2026-05-11",
                            "latest_trade_date": "2026-05-12",
                            "cycle_day": 2,
                            "cycle_length_trade_days": 25,
                            "cycle_closed": False,
                            "planned_participation": {
                                "source_tier": "extreme_conviction",
                                "participation_window": "竞价表态 + 回封参与",
                                "buy_window": "09:30-09:35",
                                "ma20_invalidation": "有效跌破日K MA20取消幻想",
                            },
                            "participation_review_status": "预演命中",
                            "participation_review": {"status": "预演命中", "next_action": "次日看是否继续强于市场"},
                            "mentions": [{"mention_trade_date": "2026-05-11", "source_section": "极度看好名单"}],
                        }
                    ]
                }
            }

        helpers = _build_runtime_execution_test_helpers(
            _run_execution_stages,
            persist_decision_ledger=False,
            decision_ledger_root_dir="/tmp/decision-ledger-root",
            read_decision_ledger_index=_fake_load_index,
            build_report_shell_contract=lambda *args, **kwargs: {"report": []},
            build_market_trend_sections_contract=lambda *args, **kwargs: {"lines": []},
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
            render_front_page_v2=lambda report, **kwargs: ["# front"],
        )

        result = report_runtime.render_markdown_report_runtime(
            {"exchange_monitor_today": [], "exchange_monitor_nextday": []},
            "2026-05-12",
            helpers=helpers,
            config={},
        )

        self.assertIn("**重点观察25日跟踪表**", result["report"])
        self.assertIn("**明日极度看好近25日跟踪表**", result["report"])
        self.assertIn("**重点观察历史回测表**", result["report"])
        self.assertIn("| 京能电力 | 600578 | D2/25 |", result["report"])

    def test_postgres_configured_decision_ledger_tracking_reads_database_not_json(self):
        class StubService:
            def is_postgres_backed(self):
                return True

            def read_decision_ledger_index(self, end_date=None, window_days=25):
                return {
                    "latest_trade_date": "2026-05-29",
                    "by_stock_code": {"601991": [{"stock_code": "601991", "stock_name": "大唐发电"}]},
                }

        class StubDatabaseService:
            @classmethod
            def from_environment(cls, db_path=None):
                return StubService()

        with TemporaryDirectory() as tempdir:
            ledger_dir = Path(tempdir) / "data" / "decision-ledger"
            ledger_dir.mkdir(parents=True)
            (ledger_dir / "index.json").write_text(
                '{"by_stock_code":{"000001":[{"stock_code":"000001","stock_name":"JSON样本"}]}}',
                encoding="utf-8",
            )
            with patch.object(report_runtime, "DatabaseService", StubDatabaseService, create=True):
                with patch.dict("os.environ", {"A_DAILY_REPORT_DATABASE_URL": "postgresql://unit/report"}, clear=False):
                    index = report_runtime._read_decision_ledger_index_for_tracking(tempdir)

        self.assertIn("601991", index["by_stock_code"])
        self.assertNotIn("000001", index["by_stock_code"])

    def test_postgres_configured_decision_ledger_tracking_failure_does_not_read_json(self):
        class BrokenDatabaseService:
            @classmethod
            def from_environment(cls, db_path=None):
                raise RuntimeError("database unavailable")

        with TemporaryDirectory() as tempdir:
            ledger_dir = Path(tempdir) / "data" / "decision-ledger"
            ledger_dir.mkdir(parents=True)
            (ledger_dir / "index.json").write_text(
                '{"by_stock_code":{"000001":[{"stock_code":"000001","stock_name":"JSON样本"}]}}',
                encoding="utf-8",
            )
            with patch.object(report_runtime, "DatabaseService", BrokenDatabaseService, create=True):
                with patch.dict("os.environ", {"A_DAILY_REPORT_DATABASE_URL": "postgresql://unit/report"}, clear=False):
                    with self.assertRaisesRegex(RuntimeError, "database unavailable"):
                        report_runtime._read_decision_ledger_index_for_tracking(tempdir)

    def test_runtime_extreme_mention_tracking_prefers_fact_db_rows_for_crud_review(self):
        from storage.database_service import DatabaseService

        def _run_execution_stages(stage_specs, stage_context=None, stage_lookup=None):
            return {"lines": [], "module_logs": [], "context": {}}

        def _fake_load_index(path):
            return {
                "latest_trade_date": "2026-05-20",
                "by_stock_code": {
                    "600578": [
                        {
                            "stock_code": "600578",
                            "stock_name": "索引旧样本",
                            "latest_trade_date": "2026-05-20",
                            "planned_participation": {"source_tier": "extreme_conviction", "buy_window": "09:30-09:35"},
                            "mentions": [{"mention_trade_date": "2026-05-20", "rank": 1, "source_section": "极度看好名单"}],
                        }
                    ]
                },
            }

        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            service = DatabaseService.sqlite_d1_compatible(root / "data" / "cloudflare_free_daily.db")
            service.upsert_extreme_conviction_mentions(
                [
                    {
                        "mention_trade_date": "2026-05-19",
                        "stock_code": "000586",
                        "stock_name": "汇源通信",
                        "rank": 1,
                        "sector_candidate": "通信设备",
                        "buy_window": "09:50-10:10",
                        "review_status": "等待复盘",
                        "next_action": "等待计划窗口事实回写",
                        "invalidation": "有效跌破日K MA20取消幻想",
                    },
                    {
                        "mention_trade_date": "2026-05-20",
                        "stock_code": "603005",
                        "stock_name": "晶方科技",
                        "rank": 1,
                        "sector_candidate": "半导体",
                        "buy_window": "09:30-09:35",
                        "review_status": "等待复盘",
                        "next_action": "等待计划窗口事实回写",
                        "invalidation": "有效跌破日K MA20取消幻想",
                    },
                ]
            )

            helpers = _build_runtime_execution_test_helpers(
                _run_execution_stages,
                persist_decision_ledger=False,
                decision_ledger_root_dir=str(root),
                read_decision_ledger_index=_fake_load_index,
                build_report_shell_contract=lambda *args, **kwargs: {"report": []},
                build_market_trend_sections_contract=lambda *args, **kwargs: {"lines": []},
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
                render_front_page_v2=lambda report, **kwargs: ["# front"],
            )

            result = report_runtime.render_markdown_report_runtime(
                {"exchange_monitor_today": [], "exchange_monitor_nextday": []},
                "2026-05-20",
                helpers=helpers,
                config={},
            )

        mention_section = result["report"].split("**明日极度看好近25日跟踪表**", 1)[1].split(
            "**重点观察历史回测表**", 1
        )[0]
        self.assertIn("| 2026-05-19 | 汇源通信 | 000586 |", mention_section)
        self.assertIn("| 2026-05-20 | 晶方科技 | 603005 |", mention_section)
        self.assertNotIn("| 2026-05-20 | 索引旧样本 | 600578 |", mention_section)

    def test_runtime_marks_a_kill_shape_mentions_before_tracking_query(self):
        from storage.database_service import DatabaseService

        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            service = DatabaseService.sqlite_d1_compatible(root / "data" / "cloudflare_free_daily.db")
            bars = []
            for idx in range(40):
                if idx < 20:
                    close = 28 + idx * 0.1
                    pct_chg = 0.5
                elif idx < 39:
                    close = 25 - idx * 0.1
                    pct_chg = -1.0
                else:
                    close = 18.0
                    pct_chg = -10.0
                bars.append(
                    {
                        "trade_date": f"2026-05-{idx + 1:02d}",
                        "ts_code": "000586.SZ",
                        "stock_code": "000586",
                        "market": "SZ",
                        "name": "汇源通信",
                        "open": close + 0.2,
                        "high": close + 0.4,
                        "low": close - 0.4,
                        "close": close,
                        "pct_chg": pct_chg,
                        "vol": 10000 + idx,
                        "amount_yi": 1.0,
                    }
                )
            service.repository.upsert_stock_daily_quotes_recent(bars)
            service.upsert_extreme_conviction_mentions(
                [
                    {
                        "record_id": "2026-05-19:000586",
                        "mention_trade_date": "2026-05-19",
                        "stock_code": "000586",
                        "stock_name": "汇源通信",
                        "rank": 1,
                        "sector_candidate": "通信设备",
                        "buy_window": "09:50-10:10",
                        "review_status": "预演作废",
                    }
                ]
            )

            rows = report_runtime._query_extreme_conviction_mention_rows_for_tracking(
                root_dir=str(root),
                end_date="2026-06-10",
                window_days=25,
            )
            raw_rows = service.query_extreme_conviction_mentions("2026-06-10", window_days=25, include_a_kill=True)

        self.assertEqual(rows, [])
        self.assertEqual(raw_rows[0]["is_a_kill_eliminated"], True)

    def test_runtime_extreme_mention_tracking_uses_configured_database_service(self):
        class StubService:
            def __init__(self):
                self.marked = []
                self.queries = []

            def mark_a_kill_shape_extreme_conviction_mentions(self, end_date, *, window_days=25, return_details=False):
                self.marked.append((end_date, window_days, return_details))
                return {"updated_count": 0, "updated_records": []}

            def query_extreme_conviction_mentions(self, end_date, *, window_days=25, include_a_kill=False):
                self.queries.append((end_date, window_days, include_a_kill))
                return [
                    {
                        "mention_trade_date": "2026-05-29",
                        "stock_code": "601991",
                        "stock_name": "大唐发电",
                    }
                ]

        class StubDatabaseService:
            service = StubService()
            sqlite_called = False

            @classmethod
            def from_environment(cls, db_path=None):
                cls.db_path = db_path
                return cls.service

            @classmethod
            def sqlite_d1_compatible(cls, db_path=None):
                cls.sqlite_called = True
                return cls.service

        with patch.dict("sys.modules", {"storage.database_service": types.SimpleNamespace(DatabaseService=StubDatabaseService)}):
            rows = report_runtime._query_extreme_conviction_mention_rows_for_tracking(
                root_dir="/tmp/daily-report",
                end_date="2026-05-29",
                window_days=25,
                include_a_kill=True,
            )

        self.assertFalse(StubDatabaseService.sqlite_called)
        self.assertEqual(rows[0]["stock_code"], "601991")
        self.assertEqual(StubDatabaseService.service.marked, [("2026-05-29", 25, True)])
        self.assertEqual(StubDatabaseService.service.queries, [("2026-05-29", 25, True)])

    def test_postgres_configured_extreme_mention_tracking_failure_does_not_hide_error(self):
        class BrokenDatabaseService:
            @classmethod
            def from_environment(cls, db_path=None):
                raise RuntimeError("database unavailable")

        with patch.dict("sys.modules", {"storage.database_service": types.SimpleNamespace(DatabaseService=BrokenDatabaseService)}):
            with patch.dict("os.environ", {"A_DAILY_REPORT_DATABASE_URL": "postgresql://unit/report"}, clear=False):
                with self.assertRaisesRegex(RuntimeError, "database unavailable"):
                    report_runtime._query_extreme_conviction_mention_rows_for_tracking(
                        root_dir="/tmp/daily-report",
                        end_date="2026-05-29",
                        window_days=25,
                    )

    def test_runtime_records_a_kill_shape_mark_details_for_tracking_query(self):
        captured = {}

        def query_rows(root_dir=".", end_date="", window_days=25):
            captured["root_dir"] = root_dir
            captured["end_date"] = end_date
            captured["window_days"] = window_days
            return {
                "updated_count": 1,
                "updated_records": [
                    {
                        "record_id": "2026-05-19:000586",
                        "mention_trade_date": "2026-05-19",
                        "stock_code": "000586",
                        "stock_name": "汇源通信",
                    }
                ],
                "rows": [{"stock_code": "603005", "stock_name": "晶方科技"}],
            }

        previous = report_runtime.query_extreme_conviction_mention_rows_for_tracking if hasattr(
            report_runtime, "query_extreme_conviction_mention_rows_for_tracking"
        ) else None
        try:
            report_runtime.query_extreme_conviction_mention_rows_for_tracking = query_rows
            result = report_runtime._query_extreme_conviction_mention_rows_for_tracking(
                root_dir="/tmp/daily-report",
                end_date="2026-05-21",
                window_days=25,
            )
        finally:
            if previous is None:
                delattr(report_runtime, "query_extreme_conviction_mention_rows_for_tracking")
            else:
                report_runtime.query_extreme_conviction_mention_rows_for_tracking = previous

        self.assertEqual(result, [{"stock_code": "603005", "stock_name": "晶方科技"}])
        self.assertEqual(captured["end_date"], "2026-05-21")
        self.assertEqual(
            report_runtime._last_extreme_conviction_a_kill_mark_result["updated_records"][0]["stock_code"],
            "000586",
        )

    def test_runtime_filters_stale_same_day_ledger_lines_after_extreme_list_changes(self):
        def _run_execution_stages(stage_specs, stage_context=None, stage_lookup=None):
            return {
                "lines": [],
                "module_logs": [],
                "context": {
                    "extreme_conviction_list": [
                        {"code": "001259", "name": "利仁科技", "sector": "股权转让", "conviction_reason": "板块锚定龙"}
                    ],
                },
            }

        def _fake_load_index(path):
            return {
                "by_stock_code": {
                    "601991": [
                        {
                            "stock_code": "601991",
                            "stock_name": "大唐发电",
                            "cycle_start_trade_date": "2026-05-12",
                            "latest_trade_date": "2026-05-18",
                            "cycle_day": 2,
                            "cycle_length_trade_days": 25,
                            "cycle_closed": False,
                            "planned_participation": {
                                "source_tier": "extreme_conviction",
                                "participation_window": "60分钟确认",
                                "buy_window": "09:50-10:10",
                                "ma20_invalidation": "有效跌破日K MA20取消幻想",
                            },
                            "participation_review_status": "等待复盘",
                            "mentions": [
                                {"mention_trade_date": "2026-05-12", "source_section": "极度看好名单", "reason": "旧的有效样本"},
                                {
                                    "mention_trade_date": "2026-05-18",
                                    "source_section": "极度看好名单",
                                    "reason": "趋势辨识度高",
                                    "planned_participation": {
                                        "source_tier": "extreme_conviction",
                                        "participation_window": "60分钟确认",
                                        "buy_window": "09:50-10:10",
                                    },
                                },
                            ],
                        }
                    ],
                    "001259": [
                        {
                            "stock_code": "001259",
                            "stock_name": "利仁科技",
                            "cycle_start_trade_date": "2026-05-18",
                            "latest_trade_date": "2026-05-18",
                            "cycle_day": 1,
                            "cycle_length_trade_days": 25,
                            "cycle_closed": False,
                            "planned_participation": {
                                "source_tier": "extreme_conviction",
                                "participation_window": "竞价表态 + 回封参与",
                                "buy_window": "09:30-09:35",
                                "ma20_invalidation": "有效跌破日K MA20取消幻想",
                            },
                            "participation_review_status": "等待复盘",
                            "mentions": [
                                {"mention_trade_date": "2026-05-18", "source_section": "极度看好名单", "reason": "板块锚定龙"}
                            ],
                        }
                    ],
                }
            }

        helpers = _build_runtime_execution_test_helpers(
            _run_execution_stages,
            persist_decision_ledger=False,
            decision_ledger_root_dir="/tmp/decision-ledger-root",
            read_decision_ledger_index=_fake_load_index,
            build_report_shell_contract=lambda *args, **kwargs: {"report": []},
            build_market_trend_sections_contract=lambda *args, **kwargs: {"lines": []},
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
            render_front_page_v2=lambda report, **kwargs: ["# front"],
        )

        result = report_runtime.render_markdown_report_runtime(
            {"exchange_monitor_today": [], "exchange_monitor_nextday": []},
            "2026-05-18",
            helpers=helpers,
            config={},
        )

        self.assertIn("| 2026-05-18 | 利仁科技 | 001259 |", result["report"])
        self.assertNotIn("| 2026-05-18 | 大唐发电 | 601991 |", result["report"])
        self.assertIn("| 2026-05-12 | 大唐发电 | 601991 |", result["report"])

    def test_runtime_decision_ledger_tracking_excludes_a_kill_records_from_extreme_table(self):
        def _run_execution_stages(stage_specs, stage_context=None, stage_lookup=None):
            return {"lines": [], "module_logs": [], "context": {}}

        def _fake_load_index(path):
            return {
                "by_stock_code": {
                    "000003": [
                        {
                            "stock_code": "000003",
                            "stock_name": "冷却股",
                            "cycle_closed": True,
                            "latest_trade_date": "2026-05-12",
                            "planned_participation": {"source_tier": "extreme_conviction", "buy_window": "09:50-10:10"},
                            "trend_fate": {"elimination_event": {"type": "a_kill", "date": "2026-05-12"}},
                            "mentions": [{"mention_trade_date": "2026-05-12", "rank": 1, "source_section": "极度看好名单"}],
                        }
                    ],
                    "600578": [
                        {
                            "stock_code": "600578",
                            "stock_name": "京能电力",
                            "cycle_closed": False,
                            "latest_trade_date": "2026-05-12",
                            "planned_participation": {
                                "source_tier": "extreme_conviction",
                                "buy_window": "09:30-09:35",
                                "ma20_invalidation": "有效跌破日K MA20取消幻想",
                            },
                            "mentions": [{"mention_trade_date": "2026-05-12", "rank": 2, "source_section": "极度看好名单"}],
                        }
                    ],
                }
            }

        helpers = _build_runtime_execution_test_helpers(
            _run_execution_stages,
            persist_decision_ledger=False,
            decision_ledger_root_dir="/tmp/decision-ledger-root",
            read_decision_ledger_index=_fake_load_index,
            build_report_shell_contract=lambda *args, **kwargs: {"report": []},
            build_market_trend_sections_contract=lambda *args, **kwargs: {"lines": []},
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
            render_front_page_v2=lambda report, **kwargs: ["# front"],
        )

        result = report_runtime.render_markdown_report_runtime(
            {"exchange_monitor_today": [], "exchange_monitor_nextday": []},
            "2026-05-12",
            helpers=helpers,
            config={},
        )

        self.assertIn("**明日极度看好近25日跟踪表**", result["report"])
        self.assertIn("| 2026-05-12 | 京能电力 | 600578 |", result["report"])
        self.assertNotIn("| 2026-05-12 | 冷却股 | 000003 |", result["report"])

    def test_runtime_body_does_not_hand_append_report_copy(self):
        runtime_source = (ROOT / "scripts" / "report" / "runtime.py").read_text()
        non_empty_report_appends = [
            line.strip()
            for line in runtime_source.splitlines()
            if "report.append(" in line and 'report.append("")' not in line and "report.append('')" not in line
        ]

        self.assertEqual([], non_empty_report_appends)

    def test_runtime_front_page_keeps_explicit_position_decision_with_selected_target(self):
        from report.report_document_builder import (
            build_report_shell_contract as _build_report_shell_contract_actual,
            replace_placeholder_lines as _replace_placeholder_lines_actual,
        )

        def _run_execution_stages(stage_specs, stage_context=None, stage_lookup=None):
            return {
                "lines": [
                    "### 旧仓位决策",
                    "- **明天具体怎么做**: 空仓等待，禁止参与；若你有仓位，只做退出不做幻想",
                    "- **进攻仓位三态**: 0%不参与",
                    "- **明天仓位放多少**: 盘前0%；参与窗口命中后才评估50%标准进攻",
                    "",
                    "**主线内可执行候选**:",
                    "| 排名 | 股票 | 代码 | 所属方向 | 角色 | 明日资格 | 身份 | 明日原则 |",
                    "|------|------|------|----------|------|----------|------|----------|",
                    "| 1 | 汇源通信 | 000586 | 通信设备 | 核心传导者 / 中位传导 | 可执行候选 | 板块锚定龙 / 首板 | 修复观察只看09:50-10:10窗口，未确认不参与 |",
                ],
                "module_logs": [],
                "context": {
                    "market_research_snapshot": {
                        "state_machine": {"leading_line": "通信设备", "energy_state": "收缩防守"},
                        "mainline_turnover_summary": {
                            "current_mainline": "通信设备",
                            "double_mainline_summary": {
                                "cycle_mainline": "通信设备",
                                "daily_attack_line": "通信设备",
                                "relationship": "候选方向在周期主线内",
                                "tomorrow_action": "只看核心对象承接",
                            },
                        },
                    },
                    "position_decision": {
                        "participation_mode": "observe_0",
                        "target_position_pct": 50,
                        "signal_grade": "50",
                        "sizing_reason": "特殊探针只到承接/观察阶段，外溢确认不足，继续维持0%。",
                        "monthly_rhythm": {
                            "month_mode": "weak_market_defense",
                            "max_position_pct": 0,
                            "reason": "大盘冰点、弱市场或趋势失效时，三态模型只允许0%保护本金。",
                        },
                    },
                },
            }

        helpers = _build_runtime_execution_test_helpers(
            _run_execution_stages,
            DISPLAY_MVP_MODE=False,
            build_report_shell_contract=_build_report_shell_contract_actual,
            replace_placeholder_lines=_replace_placeholder_lines_actual,
            build_market_phase_context=lambda *args, **kwargs: {
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
                "position_level": "一档（空仓档）",
                "position_reason": "普通防守态",
                "final_gate": {
                    "final_action": "空仓等待",
                    "operation_state": "撤退态",
                    "can_new_entry": False,
                    "should_reduce": True,
                },
                "environment_display": {"position_level": "一档（空仓档）", "operation_state": "撤退态"},
                "overall_level": "红灯",
                "price_info": {},
            },
            build_market_trend_sections_contract=lambda *args, **kwargs: {
                "lines": ["## 二、市场基底", "| 项目 | 结论 |", "|------|------|", "| 市场状态 | 普通防守态 |"]
            },
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
            _compact_report_for_mvp=lambda report, stage_lookup=None: report,
        )

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = report_runtime.render_markdown_report_runtime(
                {"exchange_monitor_today": [], "exchange_monitor_nextday": []},
                "2026-05-19",
                helpers=helpers,
                config={},
            )

        rendered = result["report"]
        self.assertIn("| 唯一对象 | 000586 汇源通信（通信设备） |", rendered)
        self.assertIn("| 进攻仓位三态 | 50% |", rendered)
        self.assertIn("| 明日最大仓位 | 50% |", rendered)
        self.assertIn("| 只看唯一对象 | 000586 汇源通信（通信设备） | 09:50-10:10 |", rendered)
        self.assertIn("| 50%标准进攻，只做预演命中的合格对象 |", rendered)
        self.assertIn("- **进攻仓位三态**: 50%标准进攻预演", rendered)
        self.assertIn("- **明天仓位放多少**: 条件50%；盘前不抢跑", rendered)
        self.assertNotIn("没有唯一对象，完整候选仅保留在附录和快照", rendered)
        self.assertNotIn("空仓等待，禁止参与；若你有仓位，只做退出不做幻想", rendered)
        self.assertNotIn("- **进攻仓位三态**: 0%不参与", rendered)
        self.assertNotIn("盘前0%；参与窗口命中后才评估50%标准进攻", rendered)
        self.assertNotIn("| 唯一对象 | 暂无 |", rendered)
        self.assertNotIn("| 进攻仓位三态 | 0% |", rendered)
        self.assertIn("最终执行条件: 明日目标标的保留条件50%预演", stdout.getvalue())
        self.assertNotIn("最终执行条件: 空仓等待", stdout.getvalue())

    def test_runtime_appendix_relabels_tomorrow_buy_rows_when_zero_participation(self):
        lines = [
            "**重点观察名单**（只保留最心动的少数，每只都绑定参与窗口）:",
            "| 角色 | 标的 | 速度档 | 买点线 | 卖点线 | 承接修复条件 | 最终复核 |",
            "|------|------|--------|--------|--------|--------------|----------|",
            "| 明日主买对象 | 豫能控股(001896) | 极致加速龙头 | MA3 | MA5 | 缩量回撤到MA3附近 | 通过 |",
            "| 明日补位对象 | 浙江世宝(002703) | 极致加速龙头 | MA3 | MA5 | 缩量回撤到MA3附近 | 通过 |",
            "",
            "**主线内可执行候选**:",
            "| 优先级 | 股票 | 代码 | 所属板块 | 核心身份 | 执行分层 | 观察理由 | 明日原则 |",
            "|--------|------|------|----------|----------|----------|----------|----------|",
            "| 1 | 豫能控股 | 001896 | 火力发电 | 核心传导者 / 中位传导 | 可执行候选 | 板块锚定龙 / 首板 | 修复观察只看09:50-10:10窗口，未确认不参与 |",
            "",
            "**重点观察参与脚本**:",
            "| 参与窗口 | 仓位三态 | 检查步骤 | 回封参与 | 作废条件 |",
            "|----------|----------|----------|----------|----------|",
            "| 竞价表态 + 回封参与 | 50% | 交易逻辑确认 / 竞价表态 / 开盘前几分钟承接 / MA执行锚点 / 回封/打板；买入资格后才看均线；给出买入资格的样本；优化买点；均线回归试错；打板策略；才算试错条件 | 开板释放抛压后快速回封 | 竞价表态、开盘承接、板块同步任一失败，按0%不参与 |",
        ]

        normalized = report_runtime._normalize_attack_preview_appendix_lines(
            lines,
            selected_position_candidate=None,
            position_decision={"signal_grade": "0", "target_position_pct": 0, "participation_mode": "observe_0"},
        )
        rendered = "\n".join(normalized)

        self.assertIn("**候选观察名单**（最终0%时只作观察样本，不构成明日新增参与）:", rendered)
        self.assertIn("| 候选观察 | 豫能控股(001896) |", rendered)
        self.assertIn("| 候选观察补充 | 浙江世宝(002703) |", rendered)
        self.assertIn("**主线内观察候选**:", rendered)
        self.assertIn("| 观察候选 | 板块锚定龙 / 首板 |", rendered)
        self.assertIn("**重点观察复核脚本**:", rendered)
        self.assertIn("| 观察窗口 | 观察状态 | 检查步骤 | 回封观察 | 作废条件 |", rendered)
        self.assertIn("| 竞价表态 + 回封观察 | 0%观察 |", rendered)
        self.assertIn("MA执行锚点 / 回封/封板观察", rendered)
        self.assertNotIn("明日主买对象", rendered)
        self.assertNotIn("明日补位对象", rendered)
        self.assertNotIn("可执行候选", rendered)
        self.assertNotIn("重点观察参与脚本", rendered)
        self.assertNotIn("参与窗口", rendered)
        self.assertNotIn("仓位三态", rendered)
        self.assertNotIn("回封参与", rendered)
        self.assertNotIn("买入资格后", rendered)
        self.assertNotIn("给出买入资格", rendered)
        self.assertNotIn("优化买点", rendered)
        self.assertNotIn("均线回归试错", rendered)
        self.assertNotIn("打板策略", rendered)
        self.assertNotIn("回封/打板", rendered)
        self.assertNotIn("试错条件", rendered)
        self.assertNotIn("| 50% |", rendered)

    def test_runtime_appendix_keeps_selected_candidate_observation_only_under_zero_participation(self):
        lines = [
            "- **明天具体怎么做**: 空仓等待，禁止参与；若你有仓位，只做退出不做幻想",
            "- **进攻仓位三态**: 0%不参与",
            "- **明天仓位放多少**: 盘前0%；参与窗口命中后才评估50%标准进攻",
            "- **现在到底是什么状态**: 0%观察，禁止抢跑，但保留重点观察名单的盘中确认路径",
            "- 50%标准进攻需要先等固定交易窗口内条件成立；未确认前按0%处理，确认后按失效价和单笔-5%底线处理风险",
            "- **确认后怎么做**: 09:50-10:10站上确认价，且板块承接不塌，才评估50%标准进攻；未命中继续0%观察",
            "- **出手时怎么做**: 盘前0%只代表不抢跑；09:50-10:10窗口内条件成立后，再评估50%标准进攻",
            "- 以观察和处理持仓为主；新仓只允许固定交易窗口内条件成立后的主线核心50%标准进攻",
            "- **执行节奏**: 最终0%时不按观察窗口执行，只观察指数图形、主攻线承接和唯一对象是否重新成立。",
            "**重点观察参与脚本**:",
            "| 参与窗口 | 仓位三态 | 检查步骤 | 回封参与 | 作废条件 |",
            "|----------|----------|----------|----------|----------|",
            "| 09:50-10:10 | 50% | 主线承接 / 站上确认价 | 快速回封 | 不满足继续0% |",
        ]

        normalized = report_runtime._normalize_attack_preview_appendix_lines(
            lines,
            selected_position_candidate={"code": "605111", "name": "新洁能"},
            position_decision={"signal_grade": "0", "target_position_pct": 0, "participation_mode": "observe_0"},
        )
        rendered = "\n".join(normalized)

        self.assertIn("明日不新增参与，只观察风险是否钝化、主攻线承接和观察锚是否重新成立", rendered)
        self.assertIn("- **进攻仓位三态**: 0%不参与", rendered)
        self.assertIn("- **明天仓位放多少**: 盘前0%；暂无新增参与资格，只观察风险是否钝化", rendered)
        self.assertIn("0%观察，不抢跑，只保留候选观察的盘中复核路径", rendered)
        self.assertIn("- 0%不参与：最终结论不允许新增参与，只观察风险是否钝化", rendered)
        self.assertIn("- **确认后怎么做**: 只保留观察，不能转成新增参与；未命中继续0%观察", rendered)
        self.assertIn("- **出手时怎么做**: 盘前0%只代表不抢跑；只观察，不新增参与", rendered)
        self.assertIn("- 以观察和处理持仓为主；不做新开仓", rendered)
        self.assertIn("观察锚是否重新成立", rendered)
        self.assertIn("重点观察复核脚本", rendered)
        self.assertIn("| 观察窗口 | 观察状态 | 检查步骤 | 回封观察 | 作废条件 |", rendered)
        self.assertIn("| 09:50-10:10 | 0%观察 | 主线承接 / 站上确认价 | 快速回封 | 不满足继续0% |", rendered)
        self.assertNotIn("重点观察参与脚本", rendered)
        self.assertNotIn("条件50", rendered)
        self.assertNotIn("才评估50%", rendered)
        self.assertNotIn("50%标准进攻", rendered)
        self.assertNotIn("唯一对象是否", rendered)
        self.assertNotIn("50%标准进攻预演", rendered)

    def test_runtime_attack_preview_relabels_legacy_zero_appendix_lines(self):
        lines = [
            "**次日市场环境**: 0%观察 / 防守态 - 先看环境，再决定是否保留观察权",
            "- ✅ 不新增参与：当前按0%不参与，固定交易窗口内条件未成立前只观察",
            "- **现在是什么情况**: 0%观察不开新仓，个股结构未坏，但环境未开",
            "- **明天能不能开仓**: 0%观察不开新仓，只保留高优先级观察权",
            "- **进攻仓位三态**: 0%观察",
            "- **现在到底是什么状态**: 0%观察，等待固定交易窗口内条件",
            "- **明天仓位放多少**: 0%新仓（只处理旧仓，不新增）",
            "- **明天具体怎么做**: 市场级原则是若你有旧仓就去弱留强，不新增参与",
            "**⛔ 当前先不开新仓**: 二档（防守档），本轮不做PK出手结论。",
            "- 当前是0%观察，本时段只确认主线核心是否在固定交易窗口内满足条件",
        ]

        normalized = report_runtime._normalize_attack_preview_appendix_lines(
            lines,
            selected_position_candidate={"code": "600726", "name": "华电能源"},
            position_decision={"signal_grade": "50", "target_position_pct": 50, "participation_mode": "attack_50_preview"},
        )
        rendered = "\n".join(normalized)

        self.assertIn("预计50%标准进攻 / 防守态", rendered)
        self.assertIn("预计50%标准进攻；固定交易窗口内条件成立才执行，不满足回到0%", rendered)
        self.assertIn("- **进攻仓位三态**: 50%标准进攻预演", rendered)
        self.assertIn("当前是预计50%标准进攻预演", rendered)
        self.assertIn("- **明天仓位放多少**: 预计50%标准进攻；条件不成立回0%", rendered)
        self.assertIn("明日执行目标只按固定交易窗口处理", rendered)
        self.assertIn("**⚠️ 当前不抢跑**: 二档（防守档），本轮只保留固定交易窗口预演。", rendered)
        self.assertNotIn("当前按0%不参与", rendered)
        self.assertNotIn("0%观察不开新仓", rendered)
        self.assertNotIn("0%新仓", rendered)
        self.assertNotIn("不新增参与", rendered)
        self.assertNotIn("当前先不开新仓", rendered)
        self.assertNotIn("- **进攻仓位三态**: 0%观察", rendered)

    def test_sanitize_report_lines_relabels_legacy_execution_framework_under_zero_participation(self):
        lines = [
            "| 明日结论 | 当前盈亏比 | 周期主线 | 当天主攻线 | 当前市场底色 | 唯一重点对象 | 明日执行风格 | 一句话动作 |",
            "|----------|------------|----------|------------|--------------|--------------|--------------|------------|",
            "| 0%不参与 | 不确定时不值得主动参与 | 半导体 | 半导体 | 先看市场基底 | 暂无 | 0% / 不参与 | 0%：没有合格标的就不参与 |",
            "- **怎么执行**: 日线结构中枢定环境，强核心走竞价表态、开盘前几分钟或回封；普通结构才等60分钟确认，30分钟定止损",
            "> **怎么执行**：先把价格区间和纪律定好，盘中只按“日线结构中枢定环境，强核心走竞价表态、开盘前几分钟或回封；普通结构才等60分钟确认，30分钟定止损”执行。",
            "- **执行节奏**: 日线结构中枢定环境，强核心走竞价表态、开盘前几分钟或回封；普通结构才等60分钟确认，30分钟定止损",
        ]

        rendered = "\n".join(report_runtime._sanitize_report_lines(lines))

        self.assertIn("最终0%时不按观察窗口执行，只观察指数图形、主攻线承接和观察锚是否重新成立。", rendered)
        self.assertIn("- **执行节奏**: 最终0%时不按观察窗口执行，只观察指数图形、主攻线承接和观察锚是否重新成立。", rendered)
        self.assertNotIn("强核心走竞价表态", rendered)
        self.assertNotIn("普通结构才等60分钟确认", rendered)

    def test_sanitize_report_lines_relabels_conditional_buy_plan_under_zero_with_observation_target(self):
        lines = [
            "| 明日结论 | 当前盈亏比 | 周期主线 | 当天主攻线 | 当前市场底色 | 唯一重点对象 | 明日执行风格 | 一句话动作 |",
            "|----------|------------|----------|------------|--------------|--------------|--------------|------------|",
            "| 0%不参与 | 不确定时不值得主动参与 | 半导体 | 半导体 | 先看市场基底 | 条件观察：605111 新洁能（半导体） | 0% / 不参与 | 盘前0%；09:50-10:10站上63.22且板块承接不塌，才评估50%标准进攻；不满足继续0% |",
            "- **怎么执行**: 日线结构中枢定环境，强核心走竞价表态、开盘前几分钟或回封；普通结构才等60分钟确认，30分钟定止损",
            "- **执行节奏**: 日线结构中枢定环境，强核心走竞价表态、开盘前几分钟或回封；普通结构才等60分钟确认，30分钟定止损",
            "- **明天仓位放多少**: 盘前0%；参与窗口命中后才评估50%标准进攻",
            "| 10:00左右买 | 新洁能站上63.22且板块承接不塌 | 条件50% | 买后用60.06做失效 | 不满足继续0% |",
            "| 候选 | 账户状态 | 当前持仓 | 可卖数量 | 选股质量 | 买点质量 | 动作上限 | 新开仓动作 |",
            "| 新洁能(605111) | 实际可买 | 0 | 0 | 中 | 等确认 | 补位 | 触发后50%标准进攻 |",
        ]

        rendered = "\n".join(report_runtime._sanitize_report_lines(lines))

        self.assertIn("观察锚：605111 新洁能（半导体）", rendered)
        self.assertIn("只观察605111 新洁能（半导体），成立才保留观察，不能转成新增参与；不满足继续0%", rendered)
        self.assertIn("- **明天仓位放多少**: 盘前0%；暂无新增参与资格，只观察风险是否钝化", rendered)
        self.assertNotIn("参与窗口命中", rendered)
        self.assertIn("| 09:50-10:10 | 新洁能站上63.22且板块承接不塌 | 只观察 | 买后用60.06做失效 | 不满足继续0% |", rendered)
        self.assertIn("| 新洁能(605111) | 仅观察 | 0 | 0 | 中 | 等确认 | 观察 | 触发后只观察 |", rendered)
        self.assertIn("最终0%时不按观察窗口执行", rendered)
        self.assertNotIn("主观察对象", rendered)
        self.assertNotIn("条件50", rendered)
        self.assertNotIn("50%标准进攻", rendered)
        self.assertNotIn("才评估50%", rendered)

    def test_sanitize_report_lines_relabels_tomorrow_action_soft_words_under_zero_participation(self):
        lines = [
            "| 明日结论 | 当前盈亏比 | 周期主线 | 当天主攻线 | 当前市场底色 | 唯一重点对象 | 明日执行风格 | 一句话动作 |",
            "|----------|------------|----------|------------|--------------|--------------|--------------|------------|",
            "| 0%不参与 | 不确定时不值得主动参与 | 半导体 | 半导体 | 先看市场基底 | 暂无 | 0% / 不参与 | 0%：没有合格标的就不参与 |",
            "| 角色 | 标的 | 速度档 | 买点线 | 卖点线 | 承接修复条件 | 观察复核 | 观察窗 |",
            "- **明天重点候选**: 1只（形态健康，允许进入Step 4继续筛到可买股）",
            "- **接着做什么**: 进入Step 4，为候选组预计算买点并筛出明天唯一能买的那只",
            "##### 附录：Step 4 - 明日买点预计算",
            "- **盯盘优先级**: 核心可买 > 龙头回看 > 主线盯盘 > 普通观察。没有买入资格，买点到了也只能看。",
            "| 股票 | 代码 | 买入资格 | 怎么买 | 日线预设区间 | 60分钟确认点 | 价格怎么盯 | 明天具体怎么做 |",
            "**执行说明**：这里的档位只代表环境条件是否满足，不代表已经有可买标的；真正能不能买，要看后文有没有缩到一只可买股。",
            "- **明天没有可买对象**: 明日不产生买入动作",
            "| ❌ 明天没有可买对象 | - | - | 保持空仓，不新增参与 | - |",
            "- ✅ 禁止一看到市场转强就直接下单：没有缩到一只可买股之前，一律不开仓",
            "- ✅ 新开仓前提：只有缩到一只可买股时，才允许按计划买入",
            "| 明天能不能开仓 | 🚫 暂不跟随 | 当前处于收缩防守，新增观察资格未满足，先研究市场，不做新增参与。 | 动作锚定到“明天能不能开仓” |",
            "| 明日风险预判 | 0%，先不跟随，继续观察，等下一轮真正的新启动；主观理解只用于观察，不用于提前硬上 |",
            "- ✅ 禁止买入任何方向：无论题材多热，都先等环境重新打开",
            "- 当前条件不允许新开仓，本时段只确认环境是否继续支持持仓/观察",
            "| 10:00左右买 | 暂无唯一对象，不做新增参与 | 无 | 无新仓止损 | 不做 |",
            "- **仓位理由**: 不把局部强势当成可执行爆发，等指数图形与主攻线承接同时修复后再给参与资格。",
            "> **明日纪律**: 放量杀跌里先防踩踏，只看次日承接修复，不把局部强势当成可执行爆发。",
            "**最终动作表**（只展示真正可执行对象）:",
            "- 0%不参与：无合格标的或取消条件已经出现，无需设置新仓止损",
            "- 未买入的保持观望",
            "| 尾盘 | 只判断是否量化电风扇行情 | 无 | 非电风扇不尾盘开新仓 | 例外，不是常规 |",
            "| 明日观察位预计算 | 不开新仓，只保留重点观察谁 |",
            "> **先看结论**：真允许出手时，只保留唯一动作；不允许时，只保留观察。",
            "**⛔ 当前先不开新仓**: 一档（空仓档），本轮不做PK出手结论。",
            "- **主线修正**: 大盘环境没有给到出手条件，先离场再等下一次趋势",
            "降低明日主动出手预期，先看跌停/ST扩散是否钝化",
            "| 均线回归观察 | MA只是执行锚点，不能因为MA3/MA5/MA10单独买入；不是所有股票的低吸理由 |",
            "| 入选日 | 股票 | 代码 | 排名 | 所属方向 | 买入窗口 | 复盘状态 | 历史复盘动作 | 作废线 | 记录ID |",
            "| 字段 | 内容 |",
            "| 主买对象 | 暂无 |",
            "| 补位对象 | 风华高科(000636) |",
            "| 候选 | 账户状态 | 当前持仓 | 可卖数量 | 选股质量 | 买点质量 | 动作上限 | 新开仓动作 |",
            "| 风华高科(000636) | 实际可买 | 0 | 0 | 中 | 等确认 | 补位 | 等触发条件成立 |",
            "- 账户状态：实际可买",
            "- 动作上限：补位",
        ]

        rendered = "\n".join(report_runtime._sanitize_report_lines(lines))

        self.assertIn("| 角色 | 标的 | 速度档 | 观察线 | 失效线 | 承接修复条件 | 观察复核 | 观察窗 |", rendered)
        self.assertIn("- **明天重点候选**: 1只（形态健康，只进入Step 4继续观察复核）", rendered)
        self.assertIn("- **接着做什么**: 进入Step 4，为候选组预计算观察位并筛出明天唯一观察对象", rendered)
        self.assertIn("##### 附录：Step 4 - 明日观察位预计算", rendered)
        self.assertIn("核心观察 > 龙头回看 > 主线盯盘 > 普通观察", rendered)
        self.assertIn("| 股票 | 代码 | 观察资格 | 怎么观察 | 日线预设区间 | 09:50-10:10窗口点 | 价格怎么盯 | 明天具体怎么做 |", rendered)
        self.assertIn("不代表已经有合格参与对象；真正是否参与，要看后文有没有缩到唯一合格对象", rendered)
        self.assertIn("- **明天没有合格参与对象**: 明日不产生新增参与动作", rendered)
        self.assertIn("| ❌ 明天没有合格参与对象 | - | - | 保持空仓，不新增参与 | - |", rendered)
        self.assertIn("没有缩到唯一合格对象之前，一律不新增参与", rendered)
        self.assertIn("新增参与前提：只有缩到唯一合格对象时，才允许按计划参与", rendered)
        self.assertIn("| 明天是否参与 | 🚫 暂不跟随 | 当前处于收缩防守，新增观察资格未满足，先研究市场，不做新增参与。 | 动作锚定到“明天是否参与” |", rendered)
        self.assertIn("主观理解只用于观察，不用于提前参与", rendered)
        self.assertIn("不参与任何方向：无论题材多热，都先等环境重新打开", rendered)
        self.assertIn("当前条件不允许新增参与", rendered)
        self.assertIn("无新增参与止损", rendered)
        self.assertIn("非电风扇不在14:30-14:55新增参与", rendered)
        self.assertIn("| 明日观察位预计算 | 不新增参与，只保留候选观察样本 |", rendered)
        self.assertIn("真允许参与时，只保留唯一动作；不允许时，只保留观察。", rendered)
        self.assertIn("当前先不新增参与", rendered)
        self.assertIn("本轮不做PK参与结论", rendered)
        self.assertIn("大盘环境没有给到参与条件", rendered)
        self.assertIn("降低明日主动参与预期", rendered)
        self.assertIn("| 09:50-10:10 | 暂无唯一对象，不做新增参与 | 无 | 无新增参与止损 | 不做 |", rendered)
        self.assertIn("不把局部强势当成参与资格", rendered)
        self.assertIn("**最终动作表**（只展示真正具备参与资格的对象）:", rendered)
        self.assertIn("无需设置新增参与止损", rendered)
        self.assertIn("未参与的保持观望", rendered)
        self.assertIn("不能因为MA3/MA5/MA10单独参与", rendered)
        self.assertIn("不是所有股票的观察理由", rendered)
        self.assertIn("| 入选日 | 股票 | 代码 | 排名 | 所属方向 | 观察位窗口 | 复盘状态 | 历史复盘动作 | 作废线 | 记录ID |", rendered)
        self.assertIn("| 主观察对象 | 暂无 |", rendered)
        self.assertIn("| 观察对象 | 风华高科(000636) |", rendered)
        self.assertIn("| 候选 | 账户状态 | 当前持仓 | 可卖数量 | 选股质量 | 观察位质量 | 观察上限 | 新增参与动作 |", rendered)
        self.assertIn("| 风华高科(000636) | 仅观察 | 0 | 0 | 中 | 等确认 | 观察 | 等触发条件成立 |", rendered)
        self.assertNotIn("买点线", rendered)
        self.assertNotIn("买入资格", rendered)
        self.assertNotIn("买入窗口", rendered)
        self.assertNotIn("买入动作", rendered)
        self.assertNotIn("禁止买入任何方向", rendered)
        self.assertNotIn("筛到可买股", rendered)
        self.assertNotIn("核心可买", rendered)
        self.assertNotIn("唯一能买", rendered)
        self.assertNotIn("可买标的", rendered)
        self.assertNotIn("可买股", rendered)
        self.assertNotIn("可买对象", rendered)
        self.assertNotIn("真正能不能买", rendered)
        self.assertNotIn("明天能不能开仓", rendered)
        self.assertNotIn("提前硬上", rendered)
        self.assertNotIn("新开仓", rendered)
        self.assertNotIn("开新仓", rendered)
        self.assertNotIn("无新仓止损", rendered)
        self.assertNotIn("允许出手", rendered)
        self.assertNotIn("PK出手结论", rendered)
        self.assertNotIn("出手条件", rendered)
        self.assertNotIn("主动出手预期", rendered)
        self.assertNotIn("10:00左右买", rendered)
        self.assertNotIn("可执行爆发", rendered)
        self.assertNotIn("真正可执行对象", rendered)
        self.assertNotIn("未买入的保持观望", rendered)
        self.assertNotIn("单独买入", rendered)
        self.assertNotIn("低吸理由", rendered)
        self.assertNotIn("主买对象", rendered)
        self.assertNotIn("补位对象", rendered)
        self.assertNotIn("实际可买", rendered)
        self.assertNotIn("动作上限", rendered)

    def test_sanitize_report_lines_relabels_new_candidate_table_when_old_position_has_zero_new_entry(self):
        lines = [
            "## 明日账户建议",
            "| 项目 | 结论 |",
            "|------|------|",
            "| 账户约束 | 1w本金；已有昨日持仓优先处理 |",
            "| 明日动作 | 先处理旧仓，不为新候选分散资金 |",
            "| T0主对象 | 持有晶方科技(603005)，100股，成本44.256；新开仓0手 |",
            "| T0备用 | 华天科技(002185)：仅作条件观察 |",
            "| 新开仓上限 | 0 |",
            "| 字段 | 内容 |",
            "| 主买对象 | 暂无 |",
            "| 补位对象 | 华天科技(002185) |",
            "| 候选 | 账户状态 | 当前持仓 | 可卖数量 | 选股质量 | 买点质量 | 动作上限 | 新开仓动作 |",
            "| 华天科技(002185) | 实际可买 | 0 | 0 | 中 | 等确认 | 补位 | 等触发条件成立 |",
            "- **重点观察优先**: 步步高(002251), 大众公用(600635), 红星发展(600367)",
            "- **先后顺序怎么排**: 先做主线锚定龙，再看普通候选；若重点观察名单全天都不给确认，其余标的宁可继续观察。",
            "| 超市连锁 | 2只 | 1只 | 2只 | 步步高(002251) | 首波先锋，优先做重点观察谁 |",
            "| 明日观察位预计算 | 不新增参与，只保留重点观察谁 |",
        ]

        rendered = "\n".join(report_runtime._sanitize_report_lines(lines))

        self.assertIn("| 主观察对象 | 暂无 |", rendered)
        self.assertIn("新开仓0手", rendered)
        self.assertIn("| 观察对象 | 华天科技(002185) |", rendered)
        self.assertIn("| 候选 | 账户状态 | 当前持仓 | 可卖数量 | 选股质量 | 观察位质量 | 观察上限 | 新增参与动作 |", rendered)
        self.assertIn("| 华天科技(002185) | 仅观察 | 0 | 0 | 中 | 等确认 | 观察 | 等触发条件成立 |", rendered)
        self.assertIn("- **候选观察样本**: 步步高(002251), 大众公用(600635), 红星发展(600367)", rendered)
        self.assertIn("若候选观察样本全天都不给确认，其余标的宁可继续观察", rendered)
        self.assertIn("首波先锋，仅作承接观察", rendered)
        self.assertIn("| 明日观察位预计算 | 不新增参与，只保留候选观察样本 |", rendered)
        self.assertNotIn("补位对象", rendered)
        self.assertNotIn("实际可买", rendered)
        self.assertNotIn("新开仓动作", rendered)
        self.assertNotIn("新增参与0手", rendered)
        self.assertNotIn("重点观察优先", rendered)
        self.assertNotIn("优先做重点观察谁", rendered)

    def test_sanitize_report_lines_relabels_premium_expectation_under_zero_participation(self):
        lines = [
            "| 明日结论 | 当前盈亏比 | 周期主线 | 当天主攻线 | 当前市场底色 | 唯一重点对象 | 明日执行风格 | 一句话动作 |",
            "|----------|------------|----------|------------|--------------|--------------|--------------|------------|",
            "| 0%不参与 | 不确定时不值得主动参与 | 半导体 | 半导体 | 先看市场基底 | 暂无 | 0% / 不参与 | 0%：没有合格标的就不参与 |",
            "| 1 | 华微电子 | 600360 | 半导体 | 大阳线 | 50分 | 溢价预期 | 大阳线封板，明日有溢价+板块龙一 |",
            "| 华微电子 | 600360 | 大阳线 | 黄灯 | 形态正常，明日看竞价 | 低风险 | 可按计划 |",
            "| 华微电子(600360) | 主线核心 | 明日可能高开溢价 |",
            "- 华微电子(600360) - 风险可控 - 形态正常，明日看竞价",
        ]

        rendered = "\n".join(report_runtime._sanitize_report_lines(lines))

        self.assertIn("承接观察", rendered)
        self.assertIn("条件未满足，只观察", rendered)
        self.assertNotIn("溢价预期", rendered)
        self.assertNotIn("明日有溢价", rendered)
        self.assertNotIn("明日可能高开溢价", rendered)
        self.assertNotIn("形态正常，明日看竞价", rendered)
        self.assertNotIn("可按计划", rendered)

    def test_sanitize_report_lines_relabels_appendix_observation_words_under_zero_participation(self):
        lines = [
            "| 明日结论 | 当前盈亏比 | 周期主线 | 当天主攻线 | 当前市场底色 | 唯一重点对象 | 明日执行风格 | 一句话动作 |",
            "|----------|------------|----------|------------|--------------|--------------|--------------|------------|",
            "| 0%不参与 | 不确定时不值得主动参与 | 半导体 | 半导体 | 先看市场基底 | 暂无 | 0% / 不参与 | 0%：没有合格标的就不参与 |",
            "| 华微电子 | 600360 | 半导体 | 大阳线 | - | 只观察承接 | ✓ 溢价候选 | 仅观察，条件未满足 |",
            "| 华微电子 | 600360 | 半导体 | 2026-05-21 | 大阳后抗跌（降级快照，仅观察） | 跌不下去 | 0.00 | 0.00 | MVP快照回退：先看次日是否继续强于市场，再按预演观察窗口确认。 |",
        ]

        rendered = "\n".join(report_runtime._sanitize_report_lines(lines))

        self.assertIn("观察样本", rendered)
        self.assertIn("观察样本：先看是否强于市场，不预设参与。", rendered)
        self.assertNotIn("溢价候选", rendered)
        self.assertNotIn("MVP快照回退", rendered)
        self.assertNotIn("预演观察窗口确认", rendered)

    def test_runtime_front_page_keeps_countertrend_attack_report_observation_only(self):
        from report.report_document_builder import (
            build_report_shell_contract as _build_report_shell_contract_actual,
            replace_placeholder_lines as _replace_placeholder_lines_actual,
        )

        def _run_execution_stages(stage_specs, stage_context=None, stage_lookup=None):
            return {
                "lines": [
                    "### 旧仓位决策",
                    "- **明天具体怎么做**: 空仓等待，禁止参与；若你有仓位，只做退出不做幻想",
                    "- **进攻仓位三态**: 0%不参与",
                    "- **明天仓位放多少**: 盘前0%；参与窗口命中后才评估50%标准进攻",
                    "",
                    "**主线内可执行候选**:",
                    "| 排名 | 股票 | 代码 | 所属方向 | 角色 | 明日资格 | 身份 | 明日原则 |",
                    "|------|------|------|----------|------|----------|------|----------|",
                    "| 1 | 华微电子 | 600360 | 半导体 | 局部逆势 | 观察候选 | 反弹锚 | 只有指数图形和板块承接同时修复才重新评估 |",
                ],
                "module_logs": [],
                "context": {
                    "market_research_snapshot": {
                        "state_machine": {
                            "leading_line": "半导体",
                            "style_label": "放量杀跌",
                            "primary_action": "先防踩踏，等指数图形和主攻线承接同时修复后再给买入资格。",
                        },
                        "mainline_turnover_summary": {
                            "current_mainline": "半导体",
                            "share_trend_label": "逆势试攻",
                            "conclusion": "半导体只是放量杀跌中的局部逆势攻击，不按周期主线切换处理",
                            "mainline_attack_evidence_summary": {
                                "attack_state": "countertrend_attack",
                                "primary_line": "半导体",
                                "confirmation_evidence": "放量杀跌中只有半导体局部逆势活跃",
                            },
                        },
                    },
                    "selected_position_candidate": {
                        "name": "华微电子",
                        "code": "600360",
                        "sector": "半导体",
                        "source_tier": "extreme_conviction",
                        "participation_window": "09:50-10:10",
                    },
                    "position_decision": {
                        "participation_mode": "attack_50_preview",
                        "target_position_pct": 50,
                        "signal_grade": "50",
                        "monthly_rhythm": {
                            "month_mode": "attack_prepare",
                            "max_position_pct": 50,
                        },
                    },
                },
            }

        helpers = _build_runtime_execution_test_helpers(
            _run_execution_stages,
            DISPLAY_MVP_MODE=False,
            build_report_shell_contract=_build_report_shell_contract_actual,
            replace_placeholder_lines=_replace_placeholder_lines_actual,
            build_market_phase_context=lambda *args, **kwargs: {
                "market_zhongshu": {},
                "market_analysis": {},
                "market_trend": "放量下跌",
                "mainline_context": {},
                "main_sectors_info": [],
                "secondary_sectors_info": [],
                "main_sectors": [],
                "secondary_sectors": [],
                "dragon_stocks": [],
                "exit_analysis": {},
                "turnover": 35072.8,
                "zt_count": 31,
                "dt_count": 48,
                "indices": {},
                "sh_change": -1.9,
                "market_stats": {},
                "up_count": 612,
                "down_count": 4620,
                "rise_fall_ratio": 0.13,
                "zs_signal_type": "",
                "zs_signal_status": "",
                "is_dt_panic": True,
                "base_position_level": "",
                "base_position_reason": "",
                "position_level": "一档（空仓档）",
                "position_reason": "放量下跌，先防踩踏",
                "final_gate": {
                    "final_action": "空仓等待",
                    "operation_state": "撤退态",
                    "can_new_entry": False,
                    "should_reduce": True,
                },
                "environment_display": {"position_level": "一档（空仓档）", "operation_state": "撤退态"},
                "overall_level": "红灯",
                "price_info": {},
            },
            build_market_trend_sections_contract=lambda *args, **kwargs: {
                "lines": ["## 二、市场基底", "| 项目 | 结论 |", "|------|------|", "| 市场状态 | 放量下跌 |"]
            },
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
            _compact_report_for_mvp=lambda report, stage_lookup=None: report,
        )

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = report_runtime.render_markdown_report_runtime(
                {"exchange_monitor_today": [], "exchange_monitor_nextday": []},
                "2026-05-21",
                helpers=helpers,
                config={},
            )

        rendered = result["report"]
        self.assertIn("| 观察锚 | 暂无 |", rendered)
        self.assertIn("| 进攻仓位三态 | 0% |", rendered)
        self.assertIn("| 明日最大仓位 | 0% |", rendered)
        self.assertIn("| 0%不参与 |", rendered)
        self.assertIn("| 进攻仓位三态 | 0% |", rendered)
        self.assertIn("放量杀跌里的局部逆势活跃", rendered)
        self.assertNotIn("| 50%标准进攻，只做预演命中的合格对象 |", rendered)
        self.assertNotIn("- **进攻仓位三态**: 50%标准进攻预演", rendered)
        self.assertNotIn("最终执行条件: 明日目标标的保留条件50%预演", stdout.getvalue())



if __name__ == "__main__":
    unittest.main()
