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


class _RuntimeMemoryFactService:
    def __init__(self):
        self.repository = self
        self.mentions = []
        self.daily_quotes = []

    def is_postgres_backed(self):
        return True

    def upsert_stock_daily_quotes_recent(self, rows, *, source_run_id=0):
        self.daily_quotes.extend(dict(row or {}) for row in rows or [])
        return len(rows or [])

    def upsert_extreme_conviction_mentions(self, rows):
        existing_ids = {
            str(row.get("record_id") or f"{row.get('mention_trade_date')}:{row.get('stock_code')}")
            for row in self.mentions
        }
        inserted = 0
        for row in rows or []:
            stored = dict(row or {})
            stored.setdefault("record_id", f"{stored.get('mention_trade_date')}:{stored.get('stock_code')}")
            if stored["record_id"] in existing_ids:
                continue
            self.mentions.append(stored)
            existing_ids.add(stored["record_id"])
            inserted += 1
        return inserted

    def mark_a_kill_shape_extreme_conviction_mentions(self, end_date, *, window_days=25, return_details=False):
        killed_codes = {
            str(row.get("stock_code") or "").strip()
            for row in self.daily_quotes
            if float(row.get("pct_chg") or 0) <= -9.0
        }
        updated_records = []
        for row in self.mentions:
            if str(row.get("stock_code") or "").strip() not in killed_codes:
                continue
            if row.get("is_a_kill_eliminated"):
                continue
            row["is_a_kill_eliminated"] = True
            updated_records.append(dict(row))
        result = {"updated_count": len(updated_records), "updated_records": updated_records}
        return result if return_details else len(updated_records)

    def query_extreme_conviction_mentions(self, end_date, *, window_days=25, include_a_kill=False):
        rows = []
        for row in self.mentions:
            if row.get("is_a_kill_eliminated") and not include_a_kill:
                continue
            rows.append(dict(row))
        rows.sort(key=lambda row: (str(row.get("mention_trade_date") or ""), str(row.get("stock_code") or "")))
        return rows


class NextDayAttributionRuntimeTest(unittest.TestCase):
    def test_runtime_renders_next_day_attribution_when_packet_exists(self):
        lines = report_runtime._render_next_day_attribution_section(
            data={
                "next_day_attribution": {
                    "schema_version": "next_day_attribution.v1",
                    "summary": {"not_counted_as_execution_reason": "报告没有明日执行对象"},
                    "rows": [
                        {
                            "code": "002409",
                            "name": "雅克科技",
                            "report_role_text": "最终观察对象",
                            "next_day_return_pct": 10.0,
                            "counting_bucket": "final_observation_hit",
                            "attribution_summary": "最终观察对象次日表现 +10.00%；因报告仓位为0%，不计为执行命中",
                        }
                    ],
                }
            }
        )

        rendered = "\n".join(lines)
        self.assertIn("## 次日归因闭环", rendered)
        self.assertIn("雅克科技(002409)", rendered)
        self.assertIn("final_observation_hit", rendered)
        self.assertIn("报告没有明日执行对象", rendered)

    def test_runtime_skips_next_day_attribution_without_packet(self):
        self.assertEqual(report_runtime._render_next_day_attribution_section(data={}), [])


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

    def test_number_report_tables_keeps_default_labels_without_postgres_only(self):
        lines = [
            "### 周期解读",
            "| 周期 | 时间段 | 交易日数 | 攻击线 |",
            "|------|--------|----------|--------|",
            "| 第1周期 | 2026-05-01~2026-05-29 | 18 | 半导体 |",
        ]

        numbered = report_runtime._number_report_tables(lines)

        self.assertEqual(numbered[1], "**T-001**")
        self.assertNotIn("（PSQL）", "\n".join(numbered))

    def test_number_report_tables_marks_psql_structured_fact_contexts_in_postgres_only(self):
        lines = [
            "### 周期解读",
            "| 周期 | 时间段 | 交易日数 | 攻击线 |",
            "|------|--------|----------|--------|",
            "| 第1周期 | 2026-05-01~2026-05-29 | 18 | 半导体 |",
            "",
            "**历史过程复盘：明日极度看好近25日跟踪表**",
            "| 入选日 | 股票 | 代码 | 所属方向 | 复盘状态 |",
            "|--------|------|------|----------|----------|",
            "| 2026-05-29 | 新洁能 | 605111 | 半导体 | 跟踪中 |",
        ]

        numbered = report_runtime._number_report_tables(lines, postgres_only=True)

        self.assertEqual(numbered[1], "**T-001（PSQL）**")
        self.assertIn("**T-002（PSQL）**", numbered)

    def test_number_report_tables_marks_psql_context_by_heading_not_dynamic_id(self):
        lines = [
            "## 明日账户建议",
            "| 项目 | 结论 |",
            "|------|------|",
            "| 账户约束 | 先处理旧仓 |",
            "",
            "### 主线成交额占比趋势",
            "| 日期 | 主线 | 占比 |",
            "|------|------|------|",
            "| 2026-05-29 | 电力 | 0.9% |",
            "",
            "**历史过程复盘：明日极度看好近25日跟踪表**（按入选日展示，排除A杀样本）:",
            "| 入选日 | 股票 | 代码 | 所属方向 |",
            "|--------|------|------|----------|",
            "| 2026-05-29 | 粤电力Ａ | 000539 | 电力 |",
        ]

        numbered = report_runtime._number_report_tables(lines, postgres_only=True)
        rendered = "\n".join(numbered)

        self.assertIn("### 主线成交额占比趋势\n**T-002（PSQL）**", rendered)
        self.assertIn("**历史过程复盘：明日极度看好近25日跟踪表**（按入选日展示，排除A杀样本）:\n**T-003（PSQL）**", rendered)

    def test_number_report_tables_marks_pivot_and_sector_flow_contexts(self):
        lines = [
            "### 中枢与主线解读",
            "| 时间段 | 中枢级别 | 对应主线 |",
            "|--------|----------|----------|",
            "| 05-29 | 日线中枢 | 暂无确认主线 |",
            "",
            "#### 中枢对应主线记录",
            "| 时间段 | 中枢级别 | 对应主线 |",
            "|--------|----------|----------|",
            "| 05-29 | 日线中枢 | 暂无确认主线 |",
            "",
            "#### 资金流入TOP10",
            "| 排名 | 板块 | 净流入 |",
            "|------|------|--------|",
            "| 1 | 电力 | +18.2亿 |",
            "",
            "#### 资金流出结果",
            "| 排名 | 板块 | 净流出 |",
            "|------|------|--------|",
            "| 1 | 半导体 | 6.5亿 |",
        ]

        numbered = report_runtime._number_report_tables(lines, postgres_only=True)

        self.assertEqual(numbered[1], "**T-001（PSQL）**")
        self.assertIn("**T-002（PSQL）**", numbered)
        self.assertIn("**T-003（PSQL）**", numbered)
        self.assertIn("**T-004（PSQL）**", numbered)

    def test_number_report_tables_does_not_carry_previous_table_cells_into_psql_context(self):
        lines = [
            "##### 资金结论",
            "| 当前资金状态 | 对明日动作的含义 |",
            "|--------------|------------------|",
            "| 龙虎榜资金强 | 先看板块攻击证据，龙虎榜只作为验证层 |",
            "",
            "**明日裁决**: 暂不跟随",
            "| 证据环节 | 当前证据 | 推导判断 |",
            "|----------|----------|----------|",
            "| 盘面风险偏好 | 49 / 50 | 先观察 |",
        ]

        numbered = report_runtime._number_report_tables(lines, postgres_only=True)

        self.assertIn("**T-001**", numbered)
        self.assertIn("**T-002**", numbered)
        self.assertNotIn("**T-001（PSQL）**", numbered)
        self.assertNotIn("**T-002（PSQL）**", numbered)

    def test_number_report_tables_marks_populated_diffusion_table(self):
        lines = [
            "#### 板块扩散质量评分",
            "| 板块 | 总分 | 评级 |",
            "|------|------|------|",
            "| 银行 | 18 | 弱扩散 |",
        ]

        numbered = report_runtime._number_report_tables(lines, postgres_only=True)

        self.assertEqual(numbered[1], "**T-001（PSQL）**")

    def test_number_report_tables_does_not_mark_placeholder_psql_context(self):
        lines = [
            "### 主线成交额占比趋势",
            "| 日期 | 小周期方向 | 主线成交额 | 两市成交额 | 占比 | 占比变化 | 切换判断 | 解读 |",
            "|------|------------|------------|------------|------|----------|----------|------|",
            "| 今日 | - | 数据暂缺 | - | 待累计 | 待累计 | 小周期待确认 | 今天开始记录，后续日报自动累计 |",
        ]

        numbered = report_runtime._number_report_tables(lines, postgres_only=True)

        self.assertEqual(numbered[1], "**T-001**")

    def test_number_report_tables_does_not_mark_dated_placeholder_psql_context(self):
        lines = [
            "### 主线成交额占比趋势",
            "| 日期 | 小周期方向 | 主线成交额 | 两市成交额 | 占比 | 占比变化 | 切换判断 | 解读 |",
            "|------|------------|------------|------------|------|----------|----------|------|",
            "| 2026-05-08 | 电力 | 数据暂缺 | 26414.92亿 | 待累计 | 待累计 | 大周期延续 | 今天开始记录，后续日报自动累计 |",
        ]

        numbered = report_runtime._number_report_tables(lines, postgres_only=True)

        self.assertEqual(numbered[1], "**T-001**")
        self.assertNotIn("（PSQL）", "\n".join(numbered))

    def test_number_report_tables_does_not_mark_cycle_placeholder_without_facts(self):
        lines = [
            "### 1. 周期日历主视图",
            "| 周次 | 一 | 二 | 三 | 四 | 五 |",
            "|------|------|------|------|------|------|",
            "| 当前周期 | 主线待累计 | 主线待累计 | 主线待累计 | 主线待累计 | 主线待累计 |",
            "",
            "### 2. 周期解读",
            "| 周期 | 时间段 | 交易日数 | 攻击线 | 周期阶段 | 传递性 | 市场状态 | 明日验证点 | 周期解读 |",
            "|------|------|------|------|------|------|------|------|------|",
            "| 当前周期 | 待累计 | 待累计 | 主线待确认 | 待验证 | 待二次验证 | 待确认 | 验证是否二次攻击 | 周期数据不足，只记录攻击线，后续日报继续验证传递性。 |",
        ]

        numbered = report_runtime._number_report_tables(lines, postgres_only=True)

        self.assertIn("**T-001**", numbered)
        self.assertIn("**T-002**", numbered)
        self.assertNotIn("（PSQL）", "\n".join(numbered))

    def test_number_report_tables_does_not_mark_no_sample_observation_pool(self):
        lines = [
            "### 龙回头观察池",
            "| 标的 | 状态 | 观察说明 |",
            "|------|------|----------|",
            "| 暂无 | 无龙回头样本 | 今天没有单独观察对象 |",
        ]

        numbered = report_runtime._number_report_tables(lines, postgres_only=True)

        self.assertEqual(numbered[1], "**T-001**")
        self.assertNotIn("（PSQL）", "\n".join(numbered))

    def test_number_report_tables_marks_sector_turnover_trend_context(self):
        lines = [
            "### 板块成交占比趋势 (近5日)",
            "| 板块 | 最新占比 | 3日趋势 | 5日均线 | 趋势序列 | 结论 |",
            "|------|----------|---------|---------|----------|------|",
            "| 电力 | 18.2% | 强化 | 14.5% | 12.1% → 15.0% → 18.2% (扩张) | 强化 |",
        ]

        numbered = report_runtime._number_report_tables(lines, postgres_only=True)

        self.assertEqual(numbered[1], "**T-001（PSQL）**")

    def test_number_report_tables_marks_candidate_trace_rows_with_missing_reason_as_psql(self):
        lines = [
            "##### 候选主表",
            "| 候选 | 账户状态 | 观察上限 | 新增参与动作 |",
            "|------|----------|----------|--------------|",
            "| 粤电力Ａ(000539) | 仅观察 | 观察 | 只观察，不新增参与 |",
            "",
            "##### 候选选股轨迹明细",
            "| 层级 | 候选 | 主线/板块 | 未满足/缺失 | 分支结果 | 明日动作 |",
            "|------|------|-----------|-------------|----------|----------|",
            "|  | 粤电力Ａ(000539) | 电力 | 市场条件：数据缺失 | 关键数据不完整，停止生成动作 | 关键数据不完整，停止生成动作 |",
        ]

        numbered = report_runtime._number_report_tables(lines, postgres_only=True)

        self.assertEqual(numbered[1], "**T-001（PSQL）**")
        self.assertIn("**T-002（PSQL）**", numbered)

    def test_number_report_tables_marks_compact_candidate_trace_context(self):
        lines = [
            "##### 候选选股轨迹",
            "| 层级 | 候选 | 主线/板块 | 为什么进入这一层 | 卡点 | 明日动作 |",
            "|------|------|-----------|------------------|------|----------|",
            "| T0 | 粤电力Ａ(000539) | 电力 | 市场条件未满足 | 市场条件未满足 | 条件未满足，继续不参与 |",
        ]

        numbered = report_runtime._number_report_tables(lines, postgres_only=True)

        self.assertEqual(numbered[1], "**T-001（PSQL）**")

    def test_number_report_tables_does_not_mark_ordinary_tables_in_postgres_only(self):
        lines = [
            "### 周期解读",
            "| 周期 | 时间段 | 交易日数 | 攻击线 |",
            "|------|--------|----------|--------|",
            "| 第1周期 | 2026-05-01~2026-05-29 | 18 | 半导体 |",
            "",
            "## 一、交易纪律",
            "| 项目 | 结论 |",
            "|------|------|",
            "| 仓位 | 先按纪律处理 |",
            "",
            "## 明日账户建议",
            "| 项目 | 结论 |",
            "|------|------|",
            "| 账户约束 | 先处理旧仓 |",
        ]

        numbered = report_runtime._number_report_tables(lines, postgres_only=True)

        self.assertEqual(numbered[1], "**T-001（PSQL）**")
        self.assertIn("**T-002**", numbered)
        self.assertIn("**T-003**", numbered)
        self.assertNotIn("**T-002（PSQL）**", numbered)
        self.assertNotIn("**T-003（PSQL）**", numbered)

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

    def test_get_or_build_calendar_ai_context_cache_key_includes_event_summary(self):
        calls = []
        original_cache = report_runtime.REPORT_RUNTIME_CACHE
        original_builder = getattr(report_runtime, "_build_calendar_ai_context", None)
        try:
            report_runtime.REPORT_RUNTIME_CACHE = {}
            report_runtime._build_calendar_ai_context = (
                lambda data, print_fn=print: calls.append(
                    (len(data.get("calendar_events", [])), data["calendar_events"][0].get("summary", ""))
                )
                or {
                    "calendar_analysis": [],
                    "top_directions": [],
                    "unique_sectors": [],
                    "bullish_events": [],
                }
            )

            base_event = {"date": "2026-06-05", "title": "某行业交流会议将于6月5日举办", "star": 3}
            report_runtime._get_or_build_calendar_ai_context({"calendar_events": [dict(base_event, summary="")]})
            report_runtime._get_or_build_calendar_ai_context(
                {"calendar_events": [dict(base_event, summary="工信部发布行业高质量发展实施方案。")]}
            )

            self.assertEqual(
                calls,
                [
                    (1, ""),
                    (1, "工信部发布行业高质量发展实施方案。"),
                ],
            )
        finally:
            report_runtime.REPORT_RUNTIME_CACHE = original_cache
            if original_builder is None:
                delattr(report_runtime, "_build_calendar_ai_context")
            else:
                report_runtime._build_calendar_ai_context = original_builder

    def test_get_or_build_calendar_ai_context_cache_key_includes_news_evidence_text(self):
        calls = []
        original_cache = report_runtime.REPORT_RUNTIME_CACHE
        original_builder = getattr(report_runtime, "_build_calendar_ai_context", None)
        try:
            report_runtime.REPORT_RUNTIME_CACHE = {}
            report_runtime._build_calendar_ai_context = (
                lambda data, print_fn=print: calls.append(
                    (len(data.get("calendar_events", [])), data["xuangubao_data"]["xuangubao_news"][0].get("content", ""))
                )
                or {
                    "calendar_analysis": [],
                    "top_directions": [],
                    "unique_sectors": [],
                    "bullish_events": [],
                }
            )

            base_data = {
                "target_date": "2026-06-05",
                "calendar_events": [
                    {"date": "2026-06-05", "title": "量子安全技术大会将于6月5日举办", "star": 3}
                ],
            }
            base_news = {
                "title": "量子安全技术大会召开",
                "summary": "",
                "source_date": "2026-06-05",
            }
            report_runtime._get_or_build_calendar_ai_context(
                {
                    **base_data,
                    "xuangubao_data": {"xuangubao_news": [dict(base_news, content="工信部发布行业高质量发展实施方案。")]},
                }
            )
            report_runtime._get_or_build_calendar_ai_context(
                {
                    **base_data,
                    "xuangubao_data": {"xuangubao_news": [dict(base_news, content="大会讨论量子安全应用场景。")]},
                }
            )

            self.assertEqual(
                calls,
                [
                    (1, "工信部发布行业高质量发展实施方案。"),
                    (1, "大会讨论量子安全应用场景。"),
                ],
            )
        finally:
            report_runtime.REPORT_RUNTIME_CACHE = original_cache
            if original_builder is None:
                delattr(report_runtime, "_build_calendar_ai_context")
            else:
                report_runtime._build_calendar_ai_context = original_builder

    def test_build_calendar_ai_context_keeps_confirmed_policy_evidence_when_batch_returns_other(self):
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

    def test_build_calendar_ai_context_handles_malformed_batch_results_without_policy_guess(self):
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
            self.assertEqual(ai_analysis["main_direction"], "政策催化")
            self.assertIn("政策催化", ai_analysis["related_sectors"])
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

    def test_build_calendar_ai_context_does_not_turn_low_evidence_meeting_titles_into_policy(self):
        class GenericPolicyBatchClient:
            def analyze_events_batch(self, events, batch_size=8):
                return [
                    {
                        "main_direction": "政策催化",
                        "related_sectors": ["政策催化"],
                        "trading_logic": "按会议或活动处理",
                        "expectation": "中性",
                        "confidence": "低",
                    }
                    for _ in events
                ]

        original_get_llm_service = getattr(report_runtime, "get_llm_service", None)
        original_remote_flag = getattr(report_runtime, "ENABLE_REMOTE_CALENDAR_LLM", None)
        try:
            report_runtime.get_llm_service = lambda: GenericPolicyBatchClient()
            report_runtime.ENABLE_REMOTE_CALENDAR_LLM = True

            result = report_runtime._build_calendar_ai_context(
                {
                    "calendar_events": [
                        {"date": "2026-06-05", "title": "华为云创想者大会将于6月5日至6日举办", "star": 3},
                        {"date": "2026-06-06", "title": "东风汽车：OpenVAN无人物流车品牌将于6月6日全球首发", "star": 2},
                        {"date": "2026-06-25", "title": "第21届开源中国·开源世界高峰论坛", "star": 3},
                    ]
                },
                print_fn=lambda *args, **kwargs: None,
            )

            directions = [item["ai_analysis"]["main_direction"] for item in result["calendar_analysis"]]
            related = [sector for item in result["calendar_analysis"] for sector in item["ai_analysis"]["related_sectors"]]
            self.assertNotIn("政策催化", directions)
            self.assertNotIn("政策催化", related)
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

    def test_build_calendar_ai_context_uses_event_summary_as_policy_evidence(self):
        original_remote_flag = getattr(report_runtime, "ENABLE_REMOTE_CALENDAR_LLM", None)
        try:
            report_runtime.ENABLE_REMOTE_CALENDAR_LLM = False

            result = report_runtime._build_calendar_ai_context(
                {
                    "calendar_events": [
                        {
                            "date": "2026-06-05",
                            "title": "某行业交流会议将于6月5日举办",
                            "summary": "工信部发布行业高质量发展实施方案。",
                            "star": 3,
                        }
                    ]
                },
                print_fn=lambda *args, **kwargs: None,
            )

            ai_analysis = result["calendar_analysis"][0]["ai_analysis"]
            self.assertEqual(ai_analysis["main_direction"], "政策催化")
            self.assertIn("政策催化", ai_analysis["related_sectors"])
        finally:
            if original_remote_flag is None:
                if hasattr(report_runtime, "ENABLE_REMOTE_CALENDAR_LLM"):
                    delattr(report_runtime, "ENABLE_REMOTE_CALENDAR_LLM")
            else:
                report_runtime.ENABLE_REMOTE_CALENDAR_LLM = original_remote_flag

    def test_build_calendar_ai_context_uses_same_day_xuangubao_news_as_policy_evidence(self):
        class AcceptingEvidenceClient:
            def __init__(self):
                self.adjudication_calls = []
                self.batch_calls = []

            def adjudicate_calendar_event_news_evidence(self, event, candidates, report_date):
                self.adjudication_calls.append((dict(event), list(candidates), report_date))
                return {
                    "matched": True,
                    "evidence_index": 0,
                    "confidence": "高",
                    "match_reason": "新闻明确对应同一场大会，并含官方文件动作",
                    "classification_hint": "政策催化",
                    "policy_evidence": True,
                }

            def analyze_events_batch(self, events, batch_size=8):
                self.batch_calls.append(list(events))
                return [
                    {
                        "main_direction": "其他",
                        "related_sectors": [],
                        "trading_logic": "AI未识别明确产业链",
                        "expectation": "中性",
                        "confidence": "低",
                    }
                    for _ in events
                ]

        client = AcceptingEvidenceClient()
        original_get_llm_service = getattr(report_runtime, "get_llm_service", None)
        original_remote_flag = getattr(report_runtime, "ENABLE_REMOTE_CALENDAR_LLM", None)
        try:
            report_runtime.get_llm_service = lambda: client
            report_runtime.ENABLE_REMOTE_CALENDAR_LLM = True

            result = report_runtime._build_calendar_ai_context(
                {
                    "target_date": "2026-06-05",
                    "calendar_events": [
                        {
                            "date": "2026-06-05",
                            "title": "量子安全技术大会将于6月5日举办",
                            "star": 3,
                        }
                    ],
                    "xuangubao_data": {
                        "xuangubao_news": [
                            {
                                "title": "量子安全技术大会召开，工信部发布行业高质量发展实施方案",
                                "summary": "工信部在量子安全技术大会期间发布行业高质量发展实施方案。",
                                "source_date": "2026-06-05",
                            }
                        ]
                    },
                },
                print_fn=lambda *args, **kwargs: None,
            )

            item = result["calendar_analysis"][0]
            ai_analysis = item["ai_analysis"]
            self.assertEqual(len(client.adjudication_calls), 1)
            self.assertEqual(client.adjudication_calls[0][2], "2026-06-05")
            self.assertIn("工信部", client.batch_calls[0][0]["summary"])
            self.assertEqual(ai_analysis["main_direction"], "政策催化")
            self.assertIn("政策催化", ai_analysis["related_sectors"])
            self.assertEqual(item["source_evidence"]["provider"], "xuangubao.xuangubao_news")
            self.assertEqual(item["source_evidence"]["query_date"], "2026-06-05")
            self.assertEqual(item["source_evidence"]["source_date"], "2026-06-05")
            self.assertEqual(item["source_evidence"]["source_url"], "")
            self.assertTrue(item["source_evidence"]["source_url_missing"])
            self.assertIn("工信部", item["source_evidence"]["evidence_text"])
            self.assertEqual(item["source_evidence"]["match_confidence"], "高")
            self.assertTrue(item["source_evidence"]["policy_evidence"])
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

    def test_build_calendar_ai_context_rejects_substring_news_when_ai_decision_rejects_it(self):
        class RejectingEvidenceClient:
            def __init__(self):
                self.adjudication_calls = []
                self.batch_calls = []

            def adjudicate_calendar_event_news_evidence(self, event, candidates, report_date):
                self.adjudication_calls.append((dict(event), list(candidates), report_date))
                return {
                    "matched": False,
                    "evidence_index": 0,
                    "confidence": "高",
                    "match_reason": "只是标题词相同，新闻主体不是这场日历事件",
                    "classification_hint": "",
                    "policy_evidence": False,
                }

            def analyze_events_batch(self, events, batch_size=8):
                self.batch_calls.append(list(events))
                return [
                    {
                        "main_direction": "其他",
                        "related_sectors": [],
                        "trading_logic": "AI未识别明确产业链",
                        "expectation": "中性",
                        "confidence": "低",
                    }
                    for _ in events
                ]

        client = RejectingEvidenceClient()
        original_get_llm_service = getattr(report_runtime, "get_llm_service", None)
        original_remote_flag = getattr(report_runtime, "ENABLE_REMOTE_CALENDAR_LLM", None)
        try:
            report_runtime.get_llm_service = lambda: client
            report_runtime.ENABLE_REMOTE_CALENDAR_LLM = True

            result = report_runtime._build_calendar_ai_context(
                {
                    "target_date": "2026-06-05",
                    "calendar_events": [
                        {
                            "date": "2026-06-05",
                            "title": "量子安全技术大会将于6月5日举办",
                            "star": 3,
                        }
                    ],
                    "xuangubao_data": {
                        "xuangubao_news": [
                            {
                                "title": "量子安全技术大会召开，工信部发布行业高质量发展实施方案",
                                "summary": "工信部发布另一项行业高质量发展实施方案。",
                                "source_date": "2026-06-05",
                            }
                        ]
                    },
                },
                print_fn=lambda *args, **kwargs: None,
            )

            self.assertEqual(len(client.adjudication_calls), 1)
            self.assertEqual(client.batch_calls[0][0]["summary"], "")
            item = result["calendar_analysis"][0]
            self.assertEqual(item["ai_analysis"]["main_direction"], "待确认")
            self.assertNotIn("source_evidence", item)
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

    def test_build_calendar_ai_context_accepts_semantic_news_without_exact_include_when_ai_decides_match(self):
        class SemanticEvidenceClient:
            def __init__(self):
                self.adjudication_calls = []
                self.batch_calls = []

            def adjudicate_calendar_event_news_evidence(self, event, candidates, report_date):
                self.adjudication_calls.append((dict(event), list(candidates), report_date))
                return {
                    "matched": True,
                    "evidence_index": 0,
                    "confidence": "中",
                    "match_reason": "新闻补足标题省略的华为云主体，语义对应同一场活动",
                    "classification_hint": "云计算",
                    "related_sectors": ["云服务", "云基础设施"],
                    "policy_evidence": False,
                }

            def analyze_events_batch(self, events, batch_size=8):
                self.batch_calls.append(list(events))
                return [
                    {
                        "main_direction": "其他",
                        "related_sectors": [],
                        "trading_logic": "AI未识别明确产业链",
                        "expectation": "中性",
                        "confidence": "低",
                    }
                    for _ in events
                ]

        client = SemanticEvidenceClient()
        original_get_llm_service = getattr(report_runtime, "get_llm_service", None)
        original_remote_flag = getattr(report_runtime, "ENABLE_REMOTE_CALENDAR_LLM", None)
        try:
            report_runtime.get_llm_service = lambda: client
            report_runtime.ENABLE_REMOTE_CALENDAR_LLM = True

            result = report_runtime._build_calendar_ai_context(
                {
                    "target_date": "2026-06-05",
                    "calendar_events": [
                        {
                            "date": "2026-06-05",
                            "title": "创想者大会将于6月5日至6日举办",
                            "star": 3,
                        }
                    ],
                    "xuangubao_data": {
                        "xuangubao_news": [
                            {
                                "title": "华为云开发者生态活动前瞻",
                                "summary": "华为云创想者大会聚焦云计算、云服务和AI云基础设施。",
                                "source_date": "2026-06-05",
                            }
                        ]
                    },
                },
                print_fn=lambda *args, **kwargs: None,
            )

            self.assertEqual(len(client.adjudication_calls), 1)
            self.assertIn("华为云开发者生态活动", client.adjudication_calls[0][1][0]["title"])
            self.assertIn("华为云创想者大会", client.batch_calls[0][0]["summary"])
            item = result["calendar_analysis"][0]
            self.assertEqual(item["ai_analysis"]["main_direction"], "云计算")
            self.assertEqual(item["source_evidence"]["match_confidence"], "中")
            self.assertFalse(item["source_evidence"]["policy_evidence"])
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

    def test_build_calendar_ai_context_rejects_low_confidence_news_decision(self):
        class LowConfidenceEvidenceClient:
            def __init__(self):
                self.adjudication_calls = []

            def adjudicate_calendar_event_news_evidence(self, event, candidates, report_date):
                self.adjudication_calls.append((dict(event), list(candidates), report_date))
                return {
                    "matched": True,
                    "evidence_index": 0,
                    "confidence": "低",
                    "match_reason": "可能相关但无法确认",
                    "classification_hint": "政策催化",
                    "policy_evidence": True,
                }

            def analyze_events_batch(self, events, batch_size=8):
                return [
                    {
                        "main_direction": "其他",
                        "related_sectors": [],
                        "trading_logic": "AI未识别明确产业链",
                        "expectation": "中性",
                        "confidence": "低",
                    }
                    for _ in events
                ]

        client = LowConfidenceEvidenceClient()
        original_get_llm_service = getattr(report_runtime, "get_llm_service", None)
        original_remote_flag = getattr(report_runtime, "ENABLE_REMOTE_CALENDAR_LLM", None)
        try:
            report_runtime.get_llm_service = lambda: client
            report_runtime.ENABLE_REMOTE_CALENDAR_LLM = True

            result = report_runtime._build_calendar_ai_context(
                {
                    "target_date": "2026-06-05",
                    "calendar_events": [
                        {
                            "date": "2026-06-05",
                            "title": "量子安全技术大会将于6月5日举办",
                            "star": 3,
                        }
                    ],
                    "xuangubao_data": {
                        "xuangubao_news": [
                            {
                                "title": "量子安全技术大会召开，工信部发布行业高质量发展实施方案",
                                "summary": "工信部在量子安全技术大会期间发布行业高质量发展实施方案。",
                                "source_date": "2026-06-05",
                            }
                        ]
                    },
                },
                print_fn=lambda *args, **kwargs: None,
            )

            self.assertEqual(len(client.adjudication_calls), 1)
            item = result["calendar_analysis"][0]
            self.assertEqual(item["ai_analysis"]["main_direction"], "待确认")
            self.assertNotIn("source_evidence", item)
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

    def test_build_calendar_ai_context_does_not_send_invalid_date_news_to_ai_evidence_decision(self):
        class AcceptAnyCandidateClient:
            def __init__(self):
                self.adjudication_calls = []

            def adjudicate_calendar_event_news_evidence(self, event, candidates, report_date):
                self.adjudication_calls.append((dict(event), list(candidates), report_date))
                return {
                    "matched": True,
                    "evidence_index": 0,
                    "confidence": "高",
                    "match_reason": "测试中任何候选都会被接受",
                    "classification_hint": "政策催化",
                    "policy_evidence": True,
                }

            def analyze_events_batch(self, events, batch_size=8):
                return [
                    {
                        "main_direction": "其他",
                        "related_sectors": [],
                        "trading_logic": "AI未识别明确产业链",
                        "expectation": "中性",
                        "confidence": "低",
                    }
                    for _ in events
                ]

        client = AcceptAnyCandidateClient()
        original_get_llm_service = getattr(report_runtime, "get_llm_service", None)
        original_remote_flag = getattr(report_runtime, "ENABLE_REMOTE_CALENDAR_LLM", None)
        try:
            report_runtime.get_llm_service = lambda: client
            report_runtime.ENABLE_REMOTE_CALENDAR_LLM = True

            result = report_runtime._build_calendar_ai_context(
                {
                    "target_date": "2026-06-05",
                    "calendar_events": [
                        {
                            "date": "2026-06-05",
                            "title": "量子安全技术大会将于6月5日举办",
                            "star": 3,
                        }
                    ],
                    "xuangubao_data": {
                        "xuangubao_news": [
                            {
                                "title": "量子安全技术大会召开，工信部发布行业高质量发展实施方案",
                                "summary": "前一日新闻。",
                                "source_date": "2026-06-04",
                            },
                            {
                                "title": "量子安全技术大会召开，工信部发布行业高质量发展实施方案",
                                "summary": "只有查询日期，缺少来源日期。",
                                "query_date": "2026-06-05",
                            },
                            {
                                "title": "量子安全技术大会召开，工信部发布行业高质量发展实施方案",
                                "summary": "未来事件日期新闻。",
                                "source_date": "2026-06-25",
                            },
                        ]
                    },
                },
                print_fn=lambda *args, **kwargs: None,
            )

            self.assertEqual(client.adjudication_calls, [])
            item = result["calendar_analysis"][0]
            self.assertEqual(item["ai_analysis"]["main_direction"], "待确认")
            self.assertNotIn("source_evidence", item)
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

    def test_build_calendar_ai_context_rejects_out_of_range_news_evidence_index(self):
        class OutOfRangeIndexClient:
            def __init__(self):
                self.adjudication_calls = []
                self.batch_calls = []

            def adjudicate_calendar_event_news_evidence(self, event, candidates, report_date):
                self.adjudication_calls.append((dict(event), list(candidates), report_date))
                return {
                    "matched": True,
                    "evidence_index": 99,
                    "confidence": "高",
                    "match_reason": "索引越界时不能采信",
                    "classification_hint": "政策催化",
                    "policy_evidence": True,
                }

            def analyze_events_batch(self, events, batch_size=8):
                self.batch_calls.append(list(events))
                return [
                    {
                        "main_direction": "其他",
                        "related_sectors": [],
                        "trading_logic": "AI未识别明确产业链",
                        "expectation": "中性",
                        "confidence": "低",
                    }
                    for _ in events
                ]

        client = OutOfRangeIndexClient()
        original_get_llm_service = getattr(report_runtime, "get_llm_service", None)
        original_remote_flag = getattr(report_runtime, "ENABLE_REMOTE_CALENDAR_LLM", None)
        try:
            report_runtime.get_llm_service = lambda: client
            report_runtime.ENABLE_REMOTE_CALENDAR_LLM = True

            result = report_runtime._build_calendar_ai_context(
                {
                    "target_date": "2026-06-05",
                    "calendar_events": [
                        {
                            "date": "2026-06-05",
                            "title": "量子安全技术大会将于6月5日举办",
                            "star": 3,
                        }
                    ],
                    "xuangubao_data": {
                        "xuangubao_news": [
                            {
                                "title": "量子安全技术大会召开，工信部发布行业高质量发展实施方案",
                                "summary": "工信部在量子安全技术大会期间发布行业高质量发展实施方案。",
                                "source_date": "2026-06-05",
                            }
                        ]
                    },
                },
                print_fn=lambda *args, **kwargs: None,
            )

            self.assertEqual(len(client.adjudication_calls), 1)
            self.assertEqual(client.batch_calls[0][0]["summary"], "")
            item = result["calendar_analysis"][0]
            self.assertEqual(item["ai_analysis"]["main_direction"], "待确认")
            self.assertNotIn("source_evidence", item)
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

    def test_build_calendar_ai_context_rejects_boolean_news_decision_fields(self):
        class BooleanDecisionClient:
            def __init__(self):
                self.adjudication_calls = []
                self.batch_calls = []

            def adjudicate_calendar_event_news_evidence(self, event, candidates, report_date):
                self.adjudication_calls.append((dict(event), list(candidates), report_date))
                return {
                    "matched": True,
                    "evidence_index": True,
                    "confidence": True,
                    "match_reason": "布尔字段不是合格结构",
                    "classification_hint": "政策催化",
                    "policy_evidence": True,
                }

            def analyze_events_batch(self, events, batch_size=8):
                self.batch_calls.append(list(events))
                return [
                    {
                        "main_direction": "其他",
                        "related_sectors": [],
                        "trading_logic": "AI未识别明确产业链",
                        "expectation": "中性",
                        "confidence": "低",
                    }
                    for _ in events
                ]

        client = BooleanDecisionClient()
        original_get_llm_service = getattr(report_runtime, "get_llm_service", None)
        original_remote_flag = getattr(report_runtime, "ENABLE_REMOTE_CALENDAR_LLM", None)
        try:
            report_runtime.get_llm_service = lambda: client
            report_runtime.ENABLE_REMOTE_CALENDAR_LLM = True

            result = report_runtime._build_calendar_ai_context(
                {
                    "target_date": "2026-06-05",
                    "calendar_events": [
                        {
                            "date": "2026-06-05",
                            "title": "量子安全技术大会将于6月5日举办",
                            "star": 3,
                        }
                    ],
                    "xuangubao_data": {
                        "xuangubao_news": [
                            {
                                "title": "无关产业新闻",
                                "summary": "同日无关新闻。",
                                "source_date": "2026-06-05",
                            },
                            {
                                "title": "量子安全技术大会召开，工信部发布行业高质量发展实施方案",
                                "summary": "工信部在量子安全技术大会期间发布行业高质量发展实施方案。",
                                "source_date": "2026-06-05",
                            },
                        ]
                    },
                },
                print_fn=lambda *args, **kwargs: None,
            )

            self.assertEqual(len(client.adjudication_calls), 1)
            self.assertEqual(len(client.adjudication_calls[0][1]), 2)
            self.assertEqual(client.batch_calls[0][0]["summary"], "")
            item = result["calendar_analysis"][0]
            self.assertEqual(item["ai_analysis"]["main_direction"], "待确认")
            self.assertNotIn("source_evidence", item)
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

    def test_build_calendar_ai_context_requires_report_date_for_news_evidence(self):
        original_remote_flag = getattr(report_runtime, "ENABLE_REMOTE_CALENDAR_LLM", None)
        try:
            report_runtime.ENABLE_REMOTE_CALENDAR_LLM = False

            result = report_runtime._build_calendar_ai_context(
                {
                    "calendar_events": [
                        {
                            "date": "2026-06-05",
                            "title": "量子安全技术大会将于6月5日举办",
                            "star": 3,
                        }
                    ],
                    "xuangubao_data": {
                        "xuangubao_news": [
                            {
                                "title": "量子安全技术大会召开，工信部发布行业高质量发展实施方案",
                                "summary": "工信部在量子安全技术大会期间发布行业高质量发展实施方案。",
                                "source_date": "2026-06-05",
                            }
                        ]
                    },
                },
                print_fn=lambda *args, **kwargs: None,
            )

            item = result["calendar_analysis"][0]
            self.assertEqual(item["ai_analysis"]["main_direction"], "待确认")
            self.assertNotIn("source_evidence", item)
        finally:
            if original_remote_flag is None:
                if hasattr(report_runtime, "ENABLE_REMOTE_CALENDAR_LLM"):
                    delattr(report_runtime, "ENABLE_REMOTE_CALENDAR_LLM")
            else:
                report_runtime.ENABLE_REMOTE_CALENDAR_LLM = original_remote_flag

    def test_build_calendar_ai_context_does_not_match_generic_event_title_to_news(self):
        original_remote_flag = getattr(report_runtime, "ENABLE_REMOTE_CALENDAR_LLM", None)
        try:
            report_runtime.ENABLE_REMOTE_CALENDAR_LLM = False

            result = report_runtime._build_calendar_ai_context(
                {
                    "target_date": "2026-06-05",
                    "calendar_events": [
                        {
                            "date": "2026-06-05",
                            "title": "某行业交流会议将于6月5日举办",
                            "star": 3,
                        }
                    ],
                    "xuangubao_data": {
                        "xuangubao_news": [
                            {
                                "title": "某行业交流会议召开，工信部发布行业高质量发展实施方案",
                                "summary": "工信部在会议期间发布行业高质量发展实施方案。",
                                "source_date": "2026-06-05",
                            }
                        ]
                    },
                },
                print_fn=lambda *args, **kwargs: None,
            )

            item = result["calendar_analysis"][0]
            self.assertEqual(item["ai_analysis"]["main_direction"], "待确认")
            self.assertNotIn("source_evidence", item)
        finally:
            if original_remote_flag is None:
                if hasattr(report_runtime, "ENABLE_REMOTE_CALENDAR_LLM"):
                    delattr(report_runtime, "ENABLE_REMOTE_CALENDAR_LLM")
            else:
                report_runtime.ENABLE_REMOTE_CALENDAR_LLM = original_remote_flag

    def test_build_calendar_ai_context_ignores_xuangubao_news_from_other_source_date(self):
        original_remote_flag = getattr(report_runtime, "ENABLE_REMOTE_CALENDAR_LLM", None)
        try:
            report_runtime.ENABLE_REMOTE_CALENDAR_LLM = False

            result = report_runtime._build_calendar_ai_context(
                {
                    "target_date": "2026-06-05",
                    "calendar_events": [
                        {
                            "date": "2026-06-05",
                            "title": "量子安全技术大会将于6月5日举办",
                            "star": 3,
                        }
                    ],
                    "xuangubao_data": {
                        "xuangubao_news": [
                            {
                                "title": "量子安全技术大会召开，工信部发布行业高质量发展实施方案",
                                "summary": "工信部在量子安全技术大会期间发布行业高质量发展实施方案。",
                                "source_date": "2026-06-04",
                            }
                        ]
                    },
                },
                print_fn=lambda *args, **kwargs: None,
            )

            item = result["calendar_analysis"][0]
            self.assertEqual(item["ai_analysis"]["main_direction"], "待确认")
            self.assertNotIn("source_evidence", item)
        finally:
            if original_remote_flag is None:
                if hasattr(report_runtime, "ENABLE_REMOTE_CALENDAR_LLM"):
                    delattr(report_runtime, "ENABLE_REMOTE_CALENDAR_LLM")
            else:
                report_runtime.ENABLE_REMOTE_CALENDAR_LLM = original_remote_flag

    def test_build_calendar_ai_context_uses_report_date_not_future_event_date_for_news_evidence(self):
        original_remote_flag = getattr(report_runtime, "ENABLE_REMOTE_CALENDAR_LLM", None)
        try:
            report_runtime.ENABLE_REMOTE_CALENDAR_LLM = False

            result = report_runtime._build_calendar_ai_context(
                {
                    "target_date": "2026-06-05",
                    "calendar_events": [
                        {
                            "date": "2026-06-25",
                            "title": "开源世界高峰论坛将于6月25日举办",
                            "star": 3,
                        }
                    ],
                    "xuangubao_data": {
                        "xuangubao_news": [
                            {
                                "title": "开源世界高峰论坛召开，工信部发布开源生态实施方案",
                                "summary": "工信部在开源世界高峰论坛期间发布开源生态实施方案。",
                                "source_date": "2026-06-25",
                            }
                        ]
                    },
                },
                print_fn=lambda *args, **kwargs: None,
            )

            item = result["calendar_analysis"][0]
            self.assertNotEqual(item["ai_analysis"]["main_direction"], "政策催化")
            self.assertNotIn("source_evidence", item)
        finally:
            if original_remote_flag is None:
                if hasattr(report_runtime, "ENABLE_REMOTE_CALENDAR_LLM"):
                    delattr(report_runtime, "ENABLE_REMOTE_CALENDAR_LLM")
            else:
                report_runtime.ENABLE_REMOTE_CALENDAR_LLM = original_remote_flag

    def test_build_calendar_ai_context_ignores_undated_xuangubao_news(self):
        original_remote_flag = getattr(report_runtime, "ENABLE_REMOTE_CALENDAR_LLM", None)
        try:
            report_runtime.ENABLE_REMOTE_CALENDAR_LLM = False

            result = report_runtime._build_calendar_ai_context(
                {
                    "target_date": "2026-06-05",
                    "calendar_events": [
                        {
                            "date": "2026-06-05",
                            "title": "量子安全技术大会将于6月5日举办",
                            "star": 3,
                        }
                    ],
                    "xuangubao_data": {
                        "xuangubao_news": [
                            {
                                "title": "量子安全技术大会召开，工信部发布行业高质量发展实施方案",
                                "summary": "工信部在量子安全技术大会期间发布行业高质量发展实施方案。",
                            }
                        ]
                    },
                },
                print_fn=lambda *args, **kwargs: None,
            )

            item = result["calendar_analysis"][0]
            self.assertEqual(item["ai_analysis"]["main_direction"], "待确认")
            self.assertNotIn("source_evidence", item)
        finally:
            if original_remote_flag is None:
                if hasattr(report_runtime, "ENABLE_REMOTE_CALENDAR_LLM"):
                    delattr(report_runtime, "ENABLE_REMOTE_CALENDAR_LLM")
            else:
                report_runtime.ENABLE_REMOTE_CALENDAR_LLM = original_remote_flag

    def test_build_calendar_ai_context_does_not_treat_query_date_as_news_source_date(self):
        original_remote_flag = getattr(report_runtime, "ENABLE_REMOTE_CALENDAR_LLM", None)
        try:
            report_runtime.ENABLE_REMOTE_CALENDAR_LLM = False

            result = report_runtime._build_calendar_ai_context(
                {
                    "target_date": "2026-06-05",
                    "calendar_events": [
                        {
                            "date": "2026-06-05",
                            "title": "量子安全技术大会将于6月5日举办",
                            "star": 3,
                        }
                    ],
                    "xuangubao_data": {
                        "xuangubao_news": [
                            {
                                "title": "量子安全技术大会召开，工信部发布行业高质量发展实施方案",
                                "summary": "工信部在量子安全技术大会期间发布行业高质量发展实施方案。",
                                "query_date": "2026-06-05",
                            }
                        ]
                    },
                },
                print_fn=lambda *args, **kwargs: None,
            )

            item = result["calendar_analysis"][0]
            self.assertEqual(item["ai_analysis"]["main_direction"], "待确认")
            self.assertNotIn("source_evidence", item)
        finally:
            if original_remote_flag is None:
                if hasattr(report_runtime, "ENABLE_REMOTE_CALENDAR_LLM"):
                    delattr(report_runtime, "ENABLE_REMOTE_CALENDAR_LLM")
            else:
                report_runtime.ENABLE_REMOTE_CALENDAR_LLM = original_remote_flag

    def test_build_calendar_ai_context_does_not_match_weak_title_term_combinations(self):
        original_remote_flag = getattr(report_runtime, "ENABLE_REMOTE_CALENDAR_LLM", None)
        try:
            report_runtime.ENABLE_REMOTE_CALENDAR_LLM = False

            result = report_runtime._build_calendar_ai_context(
                {
                    "target_date": "2026-06-05",
                    "calendar_events": [
                        {
                            "date": "2026-06-05",
                            "title": "中国行业交流大会将于6月5日举办",
                            "star": 3,
                        }
                    ],
                    "xuangubao_data": {
                        "xuangubao_news": [
                            {
                                "title": "全国行业交流活动召开，工信部发布行业高质量发展实施方案",
                                "summary": "工信部在行业交流活动期间发布行业高质量发展实施方案。",
                                "source_date": "2026-06-05",
                            }
                        ]
                    },
                },
                print_fn=lambda *args, **kwargs: None,
            )

            item = result["calendar_analysis"][0]
            self.assertEqual(item["ai_analysis"]["main_direction"], "待确认")
            self.assertNotIn("source_evidence", item)
        finally:
            if original_remote_flag is None:
                if hasattr(report_runtime, "ENABLE_REMOTE_CALENDAR_LLM"):
                    delattr(report_runtime, "ENABLE_REMOTE_CALENDAR_LLM")
            else:
                report_runtime.ENABLE_REMOTE_CALENDAR_LLM = original_remote_flag

    def test_build_calendar_ai_context_passes_matched_xuangubao_news_to_remote_analysis(self):
        class CapturingBatchClient:
            def __init__(self):
                self.calls = []
                self.adjudication_calls = []

            def adjudicate_calendar_event_news_evidence(self, event, candidates, report_date):
                self.adjudication_calls.append((dict(event), list(candidates), report_date))
                return {
                    "matched": True,
                    "evidence_index": 0,
                    "confidence": "高",
                    "match_reason": "同名大会新闻补充了华为云主体",
                    "classification_hint": "云计算",
                    "policy_evidence": False,
                }

            def analyze_events_batch(self, events, batch_size=8):
                self.calls.append(list(events))
                return [
                    {
                        "main_direction": "政策催化",
                        "related_sectors": ["政策催化"],
                        "trading_logic": "按会议或活动处理",
                        "expectation": "中性",
                        "confidence": "低",
                    }
                    for _ in events
                ]

        client = CapturingBatchClient()
        original_get_llm_service = getattr(report_runtime, "get_llm_service", None)
        original_remote_flag = getattr(report_runtime, "ENABLE_REMOTE_CALENDAR_LLM", None)
        try:
            report_runtime.get_llm_service = lambda: client
            report_runtime.ENABLE_REMOTE_CALENDAR_LLM = True

            result = report_runtime._build_calendar_ai_context(
                {
                    "target_date": "2026-06-05",
                    "calendar_events": [
                        {
                            "date": "2026-06-05",
                            "title": "创想者大会将于6月5日至6日举办",
                            "star": 3,
                        }
                    ],
                    "xuangubao_data": {
                        "xuangubao_news": [
                            {
                                "title": "华为云创想者大会将于6月5日开幕",
                                "summary": "大会聚焦云计算、云服务和AI云基础设施。",
                                "source_date": "2026-06-05",
                            }
                        ]
                    },
                },
                print_fn=lambda *args, **kwargs: None,
            )

            self.assertEqual(len(client.adjudication_calls), 1)
            self.assertEqual(len(client.calls), 1)
            self.assertIn("华为云创想者大会", client.calls[0][0]["summary"])
            item = result["calendar_analysis"][0]
            self.assertEqual(item["ai_analysis"]["main_direction"], "云计算")
            self.assertEqual(item["source_evidence"]["provider"], "xuangubao.xuangubao_news")
            self.assertNotIn("政策催化", item["ai_analysis"]["related_sectors"])
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
                "50%条件执行",
                **kwargs,
            )
            second = report_runtime._get_or_build_market_research_bundle(
                data,
                "2026-04-22",
                {"sector_name": "军工"},
                {"can_new_entry": True, "final_action": "聚焦军工"},
                "50%条件执行",
                **kwargs,
            )

            self.assertIs(first, second)
            self.assertEqual(calls, [(id(data), "2026-04-22", "50%条件执行")])
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
                "50%条件执行",
                **kwargs,
            )
            second = report_runtime._get_or_build_market_research_bundle(
                second_data,
                "2026-04-22",
                {"sector_name": "军工"},
                {"can_new_entry": True, "final_action": "聚焦军工"},
                "50%条件执行",
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
                "50%条件执行",
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

    def test_render_markdown_report_runtime_passes_target_date_to_market_analysis(self):
        class _MarketAnalysisCaptured(RuntimeError):
            pass

        captured = {}

        def _capture_market_analysis(*args, **kwargs):
            captured["target_date"] = kwargs.get("target_date")
            raise _MarketAnalysisCaptured("captured")

        helpers = _build_runtime_execution_test_helpers(
            lambda *args, **kwargs: {},
            build_market_and_sector_analysis_contract=_capture_market_analysis,
        )

        with self.assertRaises(_MarketAnalysisCaptured):
            report_runtime.render_markdown_report_runtime(
                {"total_turnover": 27791.64},
                "2026-06-04",
                helpers=helpers,
                config={},
            )

        self.assertEqual(captured["target_date"], "2026-06-04")

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
            self.assertEqual(inputs["selected_position_candidate"], {})
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
                "position_level": "0%不参与",
                "position_reason": "",
                "final_gate": {"final_action": "空仓等待", "operation_state": "观察态", "can_new_entry": False, "should_reduce": True},
                "environment_display": {"position_level": "0%不参与", "operation_state": "观察态"},
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

    def test_query_monthly_account_context_uses_postgres_repository_when_available(self):
        captured = {}

        class _StubRepository:
            def query_monthly_account_ledger(self, end_date, *, account_id="main"):
                captured["end_date"] = end_date
                captured["account_id"] = account_id
                return {
                    "trade_date": "2026-05-20",
                    "account_id": account_id,
                    "month_key": "2026-05",
                    "month_return_pct": 6.8,
                    "simulated_cumulative_return_pct": 9.3632,
                    "source_policy": "manual_review",
                }

        class _StubService:
            def __init__(self, repository):
                self.repository = repository

            def query_monthly_account_ledger(self, end_date, *, account_id="main"):
                return self.repository.query_monthly_account_ledger(end_date, account_id=account_id)

        with patch.object(report_runtime, "query_monthly_account_context", None, create=True):
            with patch(
                "storage.database_service.DatabaseService.fact_store_from_environment",
                return_value=_StubService(_StubRepository()),
            ):
                context = report_runtime._query_monthly_account_context(
                    root_dir=".",
                    target_date="2026-05-20",
                    account_id="main",
                )

        self.assertEqual(captured["end_date"], "2026-05-20")
        self.assertEqual(captured["account_id"], "main")
        self.assertEqual(context["month_return_source"], "manual_review")
        self.assertEqual(context["monthly_ledger_trade_date"], "2026-05-20")
        self.assertEqual(context["monthly_ledger_month_key"], "2026-05")
        self.assertEqual(context["simulated_cumulative_return_pct"], 9.3632)

    def test_front_page_candidate_position_pct_prefers_nested_positive_evidence(self):
        candidate = {
            "target_position_pct": 0,
            "planned_participation": {
                "attack_state": "50%",
                "buy_window": "09:50-10:10",
                "fallback_state": "不满足回到0%",
            },
        }

        self.assertEqual(report_runtime._front_page_candidate_position_pct(candidate), 50)

    def test_front_page_candidate_position_pct_normalizes_to_three_states(self):
        self.assertEqual(report_runtime._front_page_candidate_position_pct({"target_position_pct": 75}), 50)
        self.assertEqual(report_runtime._front_page_candidate_position_pct({"target_position_pct": 150}), 100)
        self.assertEqual(report_runtime._front_page_target_pct({"target_position_pct": 33}), 50)

    def test_runtime_account_unbuyable_uses_cash_and_one_lot_without_knowledge_hit(self):
        data = {"account_profile": {"cash_available": 9800}}
        candidate = {"name": "强核心", "code": "000001", "one_lot_amount": 18000}

        self.assertTrue(
            report_runtime._runtime_account_unbuyable_core_active(
                data=data,
                selected_position_candidate=candidate,
                market_research_snapshot={},
            )
        )

    def test_runtime_account_unbuyable_respects_resolved_account_status(self):
        candidate = {
            "name": "科创核心",
            "code": "688001",
            "account_trade_status": "实际不可买",
            "account_trade_reason": "科创板交易资格不适配",
        }

        self.assertTrue(
            report_runtime._runtime_account_unbuyable_core_active(
                data={"account_profile": {"cash_available": 9800}},
                selected_position_candidate=candidate,
                market_research_snapshot={},
            )
        )

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

    def test_front_page_position_decision_promotes_candidate_with_50pct_evidence_before_zero_context(self):
        position_decision = report_runtime._build_front_page_position_decision(
            position_decision={
                "participation_mode": "observe_0",
                "target_position_pct": 0,
                "signal_grade": "0",
                "monthly_rhythm": {
                    "month_mode": "weak_market_defense",
                    "max_position_pct": 0,
                },
            },
            selected_position_candidate={
                "name": "华电能源",
                "code": "600726",
                "sector": "电力",
                "source_tier": "extreme_conviction",
                "participation_window": "09:50-10:10",
                "required_steps": ["主线承接", "回踩收回MA5"],
                "fallback_state": "不满足回到0%",
                "target_position_pct": 50,
                "target_role": "core",
                "strength_evidence": ["电力资金回流", "板块锚"],
                "probe_entry_price": 10.0,
                "ma5": 9.9,
                "ma10": 9.8,
                "vwap": 9.95,
                "stop_price": 9.6,
                "target_price": 11.0,
            },
            data={},
            market_research_snapshot={},
            final_gate={"can_new_entry": False, "should_reduce": True, "allow_attack_50_ready": True},
        )

        self.assertEqual(position_decision["target_position_pct"], 50)
        self.assertEqual(position_decision["signal_grade"], "50")
        self.assertEqual(position_decision["participation_mode"], "attack_50_preview")
        self.assertIn("50%条件执行", position_decision["sizing_reason"])

    def test_front_page_position_decision_does_not_promote_when_final_gate_blocks_new_entry(self):
        position_decision = report_runtime._build_front_page_position_decision(
            position_decision={
                "participation_mode": "observe_0",
                "target_position_pct": 0,
                "signal_grade": "0",
            },
            selected_position_candidate={
                "name": "和远气体",
                "code": "002971",
                "sector": "化学制品",
                "target_position_pct": 50,
                "participation_window": "09:50-10:10",
                "required_steps": ["板块承接", "站回确认价"],
                "fallback_state": "不满足回到0%",
            },
            data={},
            market_research_snapshot={},
            final_gate={
                "can_new_entry": False,
                "allow_attack_50_ready": False,
                "final_action": "空仓等待，禁止参与；若你有仓位，只做退出不做幻想",
            },
        )

        self.assertEqual(position_decision["target_position_pct"], 0)
        self.assertEqual(position_decision["signal_grade"], "0")
        self.assertEqual(position_decision["participation_mode"], "observe_0")

    def test_front_page_position_decision_keeps_sector_capital_candidate_under_zero_condition(self):
        position_decision = report_runtime._build_front_page_position_decision(
            position_decision={
                "participation_mode": "attack_50_preview",
                "target_position_pct": 50,
                "signal_grade": "50",
            },
            selected_position_candidate={
                "name": "长电科技",
                "code": "600584",
                "sector": "半导体",
                "candidate_origin": "sector_capital_carrier_v1",
                "conditional_execution_source": "sector_capital_carrier_strategy",
                "target_position_pct": 50,
                "participation_window": "09:50-10:10",
                "buy_window": "09:50-10:10",
                "fallback_state": "T+1板块早盘失去扩散或核心掉队，回到0%不参与",
                "anchor_reversal_decision": "可作为主对象",
            },
            data={},
            market_research_snapshot={},
            final_gate={
                "can_new_entry": False,
                "final_action": "空仓等待，禁止参与；若你有仓位，只做退出不做幻想",
            },
        )

        self.assertEqual(position_decision["target_position_pct"], 50)
        self.assertEqual(position_decision["signal_grade"], "50")
        self.assertEqual(position_decision["participation_mode"], "attack_50_preview")

    def test_front_page_position_decision_promotes_candidate_with_100pct_evidence_before_zero_context(self):
        position_decision = report_runtime._build_front_page_position_decision(
            position_decision={
                "participation_mode": "observe_0",
                "target_position_pct": 0,
                "signal_grade": "0",
                "monthly_rhythm": {
                    "month_mode": "weak_market_defense",
                    "max_position_pct": 0,
                },
            },
            selected_position_candidate={
                "name": "华电能源",
                "code": "600726",
                "sector": "电力",
                "source_tier": "extreme_conviction",
                "participation_window": "09:50-10:10",
                "required_steps": ["主线承接", "回踩收回MA5"],
                "fallback_state": "不满足回到0%",
                "target_position_pct": 100,
                "target_role": "core",
                "strength_evidence": ["电力资金回流", "板块锚"],
                "probe_entry_price": 10.0,
                "ma5": 9.9,
                "ma10": 9.8,
                "vwap": 9.95,
                "stop_price": 9.6,
                "target_price": 11.0,
            },
            data={},
            market_research_snapshot={},
            final_gate={"can_new_entry": False, "should_reduce": True, "allow_attack_50_ready": True},
        )

        self.assertEqual(position_decision["target_position_pct"], 100)
        self.assertEqual(position_decision["signal_grade"], "100")
        self.assertEqual(position_decision["participation_mode"], "full_100")
        self.assertEqual(position_decision["monthly_rhythm"]["max_position_pct"], 100)
        self.assertIn("100%核心进攻", position_decision["sizing_reason"])

    def test_front_page_position_decision_keeps_planned_attack_state_from_extreme_list(self):
        selected = report_runtime._build_front_page_selected_position_candidate(
            {
                "position_decision": {
                    "participation_mode": "observe_0",
                    "target_position_pct": 0,
                    "signal_grade": "0",
                },
                "extreme_conviction_list": [
                    {
                        "name": "华电能源",
                        "code": "600726",
                        "sector": "电力",
                        "target_role": "core",
                        "strength_evidence": ["电力资金回流", "板块锚"],
                        "probe_entry_price": 10.0,
                        "ma5": 9.9,
                        "ma10": 9.8,
                        "vwap": 9.95,
                        "stop_price": 9.6,
                        "target_price": 11.0,
                        "planned_participation": {
                            "attack_state": "50%",
                            "buy_window": "09:50-10:10",
                            "required_steps": ["主线承接", "回踩收回MA5"],
                            "fallback_state": "不满足回到0%",
                        },
                    }
                ],
            }
        )

        position_decision = report_runtime._build_front_page_position_decision(
            position_decision={
                "participation_mode": "observe_0",
                "target_position_pct": 0,
                "signal_grade": "0",
            },
            selected_position_candidate=selected,
            data={},
            market_research_snapshot={},
            final_gate={"can_new_entry": False, "should_reduce": True, "allow_attack_50_ready": True},
        )

        self.assertEqual(report_runtime._front_page_candidate_position_pct(selected), 50)
        self.assertEqual(position_decision["target_position_pct"], 50)
        self.assertEqual(position_decision["signal_grade"], "50")
        self.assertEqual(position_decision["participation_mode"], "attack_50_preview")

    def test_front_page_position_decision_keeps_anchor_reversal_observation_at_zero(self):
        selected = report_runtime._build_front_page_selected_position_candidate(
            {
                "position_decision": {
                    "participation_mode": "observe_0",
                    "target_position_pct": 0,
                    "signal_grade": "0",
                },
                "extreme_conviction_list": [
                    {
                        "name": "京能电力",
                        "code": "600578",
                        "sector": "电力",
                        "sniper_role": "候选观察",
                        "anchor_reversal_decision": "降级观察",
                        "candidate_layer": "watch_sample",
                        "execution_eligibility": "anchor_reversal_observation",
                        "planned_participation": {
                            "attack_state": "50%",
                            "buy_window": "09:50-10:10",
                            "required_steps": ["主线承接", "回踩收回MA5"],
                            "fallback_state": "不满足回到0%",
                        },
                    }
                ],
            }
        )

        position_decision = report_runtime._build_front_page_position_decision(
            position_decision={
                "participation_mode": "observe_0",
                "target_position_pct": 0,
                "signal_grade": "0",
            },
            selected_position_candidate=selected,
            data={},
            market_research_snapshot={},
            final_gate={"can_new_entry": False, "should_reduce": True, "allow_attack_50_ready": True},
        )

        self.assertEqual(selected["anchor_reversal_decision"], "降级观察")
        self.assertFalse(report_runtime._front_page_candidate_has_execution_qualification(selected))
        self.assertEqual(position_decision["target_position_pct"], 0)
        self.assertEqual(position_decision["signal_grade"], "0")
        self.assertNotEqual(position_decision.get("participation_mode"), "attack_50_preview")

    def test_front_page_position_decision_keeps_single_backup_candidate_observation_only(self):
        selected = report_runtime._build_front_page_selected_position_candidate(
            {
                "position_decision": {
                    "participation_mode": "observe_0",
                    "target_position_pct": 0,
                    "signal_grade": "0",
                },
                "extreme_conviction_list": [
                    {
                        "name": "华电辽能",
                        "code": "600396",
                        "sector": "电力",
                        "sniper_role": "明日补位对象",
                        "primary_buy_candidate": False,
                        "backup_buy_candidate": True,
                        "anchor_reversal_decision": "可作为补位",
                        "candidate_layer": "executable_candidate",
                        "execution_eligibility": "auction_reseal",
                        "planned_participation": {
                            "attack_state": "50%",
                            "buy_window": "09:50-10:10",
                            "required_steps": ["主线承接", "回踩收回MA5"],
                            "fallback_state": "不满足回到0%",
                        },
                    }
                ],
            }
        )

        position_decision = report_runtime._build_front_page_position_decision(
            position_decision={
                "participation_mode": "observe_0",
                "target_position_pct": 0,
                "signal_grade": "0",
            },
            selected_position_candidate=selected,
            data={},
            market_research_snapshot={},
            final_gate={"can_new_entry": False, "should_reduce": True, "allow_attack_50_ready": True},
        )

        self.assertEqual(selected["sniper_role"], "明日补位对象")
        self.assertFalse(report_runtime._front_page_candidate_has_execution_qualification(selected))
        self.assertEqual(position_decision["target_position_pct"], 0)
        self.assertEqual(position_decision["signal_grade"], "0")
        self.assertNotEqual(position_decision.get("participation_mode"), "attack_50_preview")

    def test_front_page_selected_candidate_prefers_qualified_selected_before_extreme_list(self):
        selected = report_runtime._build_front_page_selected_position_candidate(
            {
                "position_decision": {
                    "participation_mode": "observe_0",
                    "target_position_pct": 0,
                    "signal_grade": "0",
                },
                "selected_position_candidate": {
                    "name": "华电能源",
                    "code": "600726",
                    "sector": "电力",
                    "target_position_pct": 50,
                    "participation_window": "09:50-10:10",
                    "fallback_state": "不满足回到0%",
                },
                "extreme_conviction_list": [
                    {
                        "name": "普通观察",
                        "code": "000001",
                        "planned_participation": {
                            "attack_state": "0%",
                            "buy_window": "09:50-10:10",
                            "fallback_state": "不满足回到0%",
                        },
                    }
                ],
            }
        )

        self.assertEqual(selected["code"], "600726")

    def test_front_page_selected_candidate_keeps_explicit_observation_before_extreme_fallback(self):
        selected = report_runtime._build_front_page_selected_position_candidate(
            {
                "position_decision": {
                    "participation_mode": "observe_0",
                    "target_position_pct": 0,
                    "signal_grade": "0",
                },
                "best_stock": {"name": "双星新材", "code": "002585", "sector": "塑料"},
                "selected_position_candidate": {
                    "name": "中船特气",
                    "code": "688146",
                    "sector": "电子化学品",
                    "sniper_role": "候选观察",
                    "anchor_reversal_decision": "降级观察",
                },
                "extreme_conviction_list": [
                    {
                        "name": "双星新材",
                        "code": "002585",
                        "sector": "塑料",
                        "sniper_role": "候选观察补充",
                        "anchor_reversal_decision": "降级观察",
                    }
                ],
            }
        )

        self.assertEqual(selected["code"], "688146")

    def test_front_page_target_ignores_first_wave_memory_without_leader_proof(self):
        memory_only = {
            "name": "宇环数控",
            "code": "002903",
            "sector": "通用设备",
            "remember_score": 68.0,
            "remember_reason": "首波先锋，优先做重点观察谁 / 首波龙一",
            "remember_window": "10~20个交易日",
            "action_rule": "后续若板块再发力，优先回看它；只在固定交易窗口内做分歧后再转强",
            "candidate_feedback_ready": False,
        }
        market_snapshot = {
            "mainline_turnover_summary": {"current_mainline": "半导体"},
            "current_core_candidate": dict(memory_only),
            "selected_position_candidate": dict(memory_only),
        }
        execution_context = {
            "position_decision": {
                "participation_mode": "observe_0",
                "target_position_pct": 0,
                "signal_grade": "0",
            },
            "mainline_turnover_summary": {"current_mainline": "半导体"},
            "market_research_snapshot": market_snapshot,
            "current_core_candidate": dict(memory_only),
            "selected_position_candidate": dict(memory_only),
            "leader_memory_bank": [dict(memory_only)],
        }

        selected = report_runtime._resolve_front_page_target_candidate(
            data={"market_research_snapshot": market_snapshot},
            execution_stage_context=execution_context,
            report_lines=[],
            target_date="2026-06-05",
        )
        resolution = report_runtime._build_runtime_final_target_resolution(
            data={
                "personal_position_context": {
                    "existing_position_summary": {
                        "has_position": True,
                        "summary": "华电辽能(600396)：旧仓先处理",
                    }
                }
            },
            selected_position_candidate=selected,
            position_decision={"target_position_pct": 0, "signal_grade": "0"},
            market_research_snapshot=market_snapshot,
        )

        self.assertEqual(selected, {})
        self.assertEqual(resolution["new_entry_target"], {})
        self.assertEqual(resolution["watch_target"], {})

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
        self.assertNotIn("50%条件执行", position_decision["sizing_reason"])

    def test_runtime_core_candidate_uses_condition_priority_not_weighted_score(self):
        selected = {
            "name": "已解析对象",
            "code": "600001",
            "sector": "电力",
            "sniper_role": "明日补位对象",
            "anchor_reversal_decision": "可作为补位",
            "candidate_role": "板块锚",
        }
        score_like_competitor = {
            "name": "加分候选",
            "code": "600002",
            "sector": "电力",
            "sniper_role": "明日主买对象",
            "anchor_reversal_decision": "可作为主对象",
            "candidate_role": "板块锚",
            "primary_buy_candidate": True,
            "repair_priority": "优先修复",
            "score": 999,
            "tomorrow_strength": 999,
        }

        resolved = report_runtime._resolve_runtime_current_core_candidate(
            data={
                "position_decision": {"target_position_pct": 50, "signal_grade": "50"},
                "mainline_turnover_summary": {"current_mainline": "电力"},
            },
            execution_stage_context={
                "position_decision": {"target_position_pct": 50, "signal_grade": "50"},
                "mainline_turnover_summary": {"current_mainline": "电力"},
                "selected_position_candidate": dict(selected),
                "extreme_conviction_list": [dict(score_like_competitor)],
            },
            selected_position_candidate=dict(selected),
            extreme_conviction_list=[dict(score_like_competitor)],
        )

        self.assertEqual(resolved["code"], "600001")

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

    def test_prefer_mainline_turnover_summary_keeps_clean_hot_sector_rows_over_conflicted_fallback(self):
        clean_summary = {
            "current_mainline": "新型电力",
            "share_trend_label": "切换",
            "hot_sector_turnover_watch_rows": [
                {
                    "date": "2026-05-29",
                    "sector_name": "新型电力",
                    "sector_turnover": "296.49亿",
                    "market_turnover": "33408.58亿",
                    "total_turnover": "33408.58亿",
                    "share": "0.9%",
                    "share_change": "待累计",
                    "sample_status": "待累计",
                },
                {
                    "date": "2026-05-19",
                    "sector_name": "电力",
                    "sector_turnover": "665.00亿",
                    "market_turnover": "29089.77亿",
                    "total_turnover": "29089.77亿",
                    "share": "2.3%",
                    "share_change": "待累计",
                    "sample_status": "待累计",
                },
            ],
        }
        stale_fallback = {
            "current_mainline": "新型电力",
            "share_trend_label": "切换",
            "hot_sector_turnover_watch_rows": [
                clean_summary["hot_sector_turnover_watch_rows"][0],
                {
                    "date": "2026-05-29",
                    "sector_name": "电力",
                    "sector_turnover": "296.49亿",
                    "market_turnover": "33408.58亿",
                    "total_turnover": "33408.58亿",
                    "share": "0.9%",
                    "share_change": "-1.4pct",
                    "sample_status": "同板块连续",
                },
                {
                    "date": "2026-05-29",
                    "sector_name": "通信设备",
                    "sector_turnover": "3062.15亿",
                    "market_turnover": "33408.58亿",
                    "total_turnover": "33408.58亿",
                    "share": "9.2%",
                    "share_change": "待累计",
                    "sample_status": "待累计",
                },
            ],
        }

        merged = report_runtime._prefer_structured_mainline_turnover_summary(
            clean_summary,
            stale_fallback,
        )

        rows = merged["hot_sector_turnover_watch_rows"]
        self.assertTrue(any(row["sector_name"] == "新型电力" and row["date"] == "2026-05-29" for row in rows))
        self.assertTrue(any(row["sector_name"] == "通信设备" and row["date"] == "2026-05-29" for row in rows))
        self.assertFalse(any(row["sector_name"] == "电力" and row["date"] == "2026-05-29" for row in rows))

    def test_prefer_mainline_turnover_summary_sanitizes_self_conflicted_hot_sector_rows(self):
        conflicted_summary = {
            "share_trend_label": "分化",
            "hot_sector_turnover_watch_summary": "近期热点板块成交额连续跟踪：当前2026-05-29记录3个热点板块，通信设备 9.2%居前；变化只按同一板块自身历史计算。",
            "hot_sector_turnover_watch_rows": [
                {
                    "date": "2026-05-29",
                    "sector_name": "新型电力",
                    "sector_turnover": "296.49亿",
                    "market_turnover": "33408.58亿",
                    "total_turnover": "33408.58亿",
                    "share": "0.9%",
                    "share_change": "待累计",
                    "sample_status": "待累计",
                },
                {
                    "date": "2026-05-29",
                    "sector_name": "电力",
                    "sector_turnover": "296.49亿",
                    "market_turnover": "33408.58亿",
                    "total_turnover": "33408.58亿",
                    "share": "0.9%",
                    "share_change": "-1.4pct",
                    "sample_status": "同板块连续",
                },
                {
                    "date": "2026-05-29",
                    "sector_name": "通信设备",
                    "sector_turnover": "3062.15亿",
                    "market_turnover": "33408.58亿",
                    "total_turnover": "33408.58亿",
                    "share": "9.2%",
                    "share_change": "+2.3pct",
                    "sample_status": "同板块连续",
                },
            ],
        }

        merged = report_runtime._prefer_structured_mainline_turnover_summary(
            conflicted_summary,
            {},
        )

        rows = merged["hot_sector_turnover_watch_rows"]
        self.assertTrue(any(row["sector_name"] == "新型电力" and row["date"] == "2026-05-29" for row in rows))
        self.assertTrue(any(row["sector_name"] == "通信设备" and row["date"] == "2026-05-29" for row in rows))
        self.assertFalse(any(row["sector_name"] == "电力" and row["date"] == "2026-05-29" for row in rows))
        self.assertIn("记录2个热点板块", merged["hot_sector_turnover_watch_summary"])
        self.assertNotIn("记录3个热点板块", merged["hot_sector_turnover_watch_summary"])

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

    def test_appendix_c_uses_crossline_label_when_watch_anchor_note_matches_core_stock(self):
        payload = report_runtime._build_appendix_c_continuity_payload(
            target_date="2026-05-29",
            execution_stage_context={
                "mainline_name": "半导体",
                "core_stocks": [
                    {
                        "name": "华电能源",
                        "code": "600726",
                        "sector": "电力",
                        "current_action": "继续观察",
                    }
                ],
                "watch_anchor": {
                    "name": "华电能源",
                    "code": "600726",
                    "sector": "电力",
                },
                "special_probe_text": "华电能源(600726)：跨线对象（电力），只用于观察强弱，不代表主攻线从半导体切换。",
            },
        )

        pool = payload["current_stock_monitoring_pool"]

        self.assertEqual(pool[0]["source_pool"], "跨线观察")
        self.assertNotEqual(pool[0]["source_pool"], "主线核心")

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
            "## 二、市场基底",
            "## 三、周期与主线",
            "## 明日账户建议",
            "## 一、交易纪律",
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
        self.assertIn("[半导体]</span> 接力", rendered)
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
                position_level="50%条件执行",
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
            "| 日期 | 小周期方向 | 主线成交额 | 两市成交额 | 占比 | 占比变化 | 切换判断 | 解读 |",
            summary_result["report"],
        )
        self.assertIn(
            "[通信]</span> | 2180.00亿 | 12834.00亿 | 18.1% | +2.3pct | 大周期延续 | 主线占比继续抬升，节奏偏强化 |",
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

        self.assertIn("[电力]</span> 强化", rendered)
        self.assertIn("[电力]</span> 退潮", rendered)
        self.assertIn("[半导体]</span> 接力", rendered)
        self.assertIn("[半导体]</span> 修复", rendered)
        self.assertIn(
            "| 周期 | 时间段 | 交易日数 | 攻击线 | 周期阶段 | 传递性 | 市场状态 | 明日验证点 | 周期解读 |",
            rendered,
        )
        self.assertIn("[电力]</span> | 已结束周期 | 背景观察 | 强化后退潮 |", rendered)
        self.assertIn("[半导体]</span> | 延续验证 | 待二次验证 | 接力后修复接力 |", rendered)
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
        self.assertIn("[半导体]</span> | 数据暂缺 | 26414.92亿 | 待累计 | 待累计 | 大周期延续 | 缺少板块成交额接口，先记录主线归属 |", result["report"])

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

        self.assertIn("[半导体]</span> | 2180.00亿 | 12834.00亿 | 18.1% | +2.3pct | 大周期延续 | 主线占比继续抬升 |", result["report"])

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
        self.assertIn("[混沌轮动]</span> | 混沌轮动 | 混沌轮动 |", result["report"])
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
                            "target_role": "core",
                            "strength_evidence": ["电力资金回流", "板块锚"],
                            "probe_entry_price": 10.0,
                            "ma5": 9.9,
                            "ma10": 9.8,
                            "vwap": 9.95,
                            "stop_price": 9.6,
                            "target_price": 11.0,
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
        self.assertIn("[半导体]</span> | 2180.00亿 | 12834.00亿 | 18.1% | +2.3pct | 大周期延续 | 主线占比继续抬升 |", result["report"])
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

    def test_front_page_target_does_not_promote_zero_position_extreme_observation_over_waiting_layer(self):
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
                        "attack_state": "0%不参与",
                    }
                ],
            }
        )

        self.assertIsNone(selected)

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
            "硬" + "门" + "禁",
            "门" + "禁",
            "ga" + "te",
            "hard " + "ga" + "te",
            "状态" + "机",
            "状态" + "机" + "词" + "汇",
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
                position_level="50%条件执行",
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
        self.assertIn("## 交易原则", result["report"])
        self.assertIn("去弱留强是短线执行表达", result["report"])
        self.assertEqual(data["knowledge"]["llm_wiki"]["source"], "llm_wiki")
        self.assertIn("固定交易窗口条件", data["knowledge"]["llm_wiki"]["report_digest_text"])
        self.assertIn("09:50-10:10窗口", data["knowledge"]["llm_wiki"]["report_digest_text"])
        self.assertIn("daily_discipline_lines", data["knowledge"]["llm_wiki"])
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
        self.assertIn("候选质量条件链与动作上限", result["report"])
        self.assertIn("旧分数只作兼容字段", result["report"])

    def test_render_markdown_report_runtime_derives_cull_weak_hit_from_final_resolution(self):
        data = {
            "final_target_resolution": {
                "new_entry_target": {"name": "工业富联", "code": "601138"},
                "existing_position_target": {"name": "华电辽能", "code": "600396"},
                "capital_priority_decision": {
                    "capital_priority": "new_entry_after_old_exit",
                    "reason": "先处理旧仓，买工业富联；固定交易窗口条件成立才参与，不满足回到0%",
                },
            },
        }

        with patch("report.runtime._render_markdown_report_legacy_body", return_value="# runtime report"):
            result = report_runtime.render_markdown_report_runtime(
                data,
                "2026-06-16",
                helpers={"DISPLAY_MVP_MODE": False},
                config={},
            )

        ids = [hit["knowledge_id"] for hit in data["knowledge"]["llm_wiki"]["knowledge_hits"]]
        self.assertIn("position.cull-weak-keep-strong", ids)
        self.assertEqual(result["report"].count("去弱留强是短线执行表达"), 1)
        self.assertIn("## 交易原则", result["report"])
        self.assertIn("## 经验库命中", result["report"])

    def test_render_markdown_report_runtime_does_not_duplicate_daily_discipline_when_body_already_has_it(self):
        with patch(
            "report.runtime._render_markdown_report_legacy_body",
            return_value="# runtime report\n\n## 交易原则\n- 去弱留强是短线执行表达：卖旧仓看旧仓资格，买新仓看新仓资格；不能用FOMO把两笔判断合成一次满仓替换。",
        ):
            result = report_runtime.render_markdown_report_runtime(
                {},
                "2026-06-16",
                helpers={"DISPLAY_MVP_MODE": False},
                config={},
            )

        self.assertEqual(result["report"].count("去弱留强是短线执行表达"), 1)
        self.assertEqual(result["report"].count("## 交易原则"), 1)

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
        self.assertIn("| 明日动作 | 0%不参与；只保留观察对象，不新开 |", report)
        self.assertIn("| 观察对象 | 暂无 |", report)
        self.assertIn("| 明日执行目标 | 无昨日持仓，不涉及明日执行对象 |", report)
        self.assertNotIn("| T0主对象 | 强核心(000001)：当前账户买不了一手，只保留观察 |", report)
        self.assertIn("| 新增参与上限 | 0 |", report)
        self.assertIn("| 实际不可买不降低市场身份 | 实际不可买；市场核心 |", report)
        self.assertIn("| 当前状态 | 0%无合格标的 |", report)
        self.assertIn("| 明日观察动作 | 标的 | 观察窗 | 条件 | 不满足怎么办 |", report)
        self.assertIn("| 0%不参与 | 不确定时不值得主动参与 |", report)
        self.assertNotIn("强核心(000001)：当前账户买不了一手，只保留观察", report)
        self.assertNotIn("50%条件执行，只做合格对象", report)
        self.assertIn("最终执行条件: 观察", stdout.getvalue())
        self.assertNotIn("最终执行条件: 明日目标标的保留50%条件执行", stdout.getvalue())

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

    def test_render_markdown_report_runtime_appends_topic_lifecycle_note(self):
        data = {
            "trade_date": "2026-06-14",
            "realtime_tag_evidence_snapshot": {
                "groups": [
                    {
                        "采用名称": "PCB电子材料",
                        "大方向": "AI算力基础设施",
                        "当日主攻分支": "PCB电子材料",
                        "表层行业名": ["PCB", "电子材料"],
                        "辅助名称": ["AI服务器PCB"],
                        "资金证据": "资金指向：PCB电子材料",
                        "扩散证据": "同分支多只个股上涨",
                    }
                ]
            },
            "candidate_traces": [
                {
                    "stock_name": "胜宏科技",
                    "stock_code": "300476",
                    "sector": "PCB电子材料",
                    "mainline": "AI算力基础设施",
                    "final_action": "沿PCB电子材料核心承接继续观察",
                    "anchor_reversal": {
                        "candidate_role": "趋势核心",
                        "anchor_reversal_decision": "可作为主对象",
                        "anchor_reversal_reason": "核心承接稳定",
                    },
                }
            ],
        }

        with patch("report.runtime._render_markdown_report_legacy_body", return_value="# runtime report"):
            result = report_runtime.render_markdown_report_runtime(
                data,
                "2026-06-14",
                helpers={"DISPLAY_MVP_MODE": False},
                config={},
            )

        report = result["report"]
        self.assertEqual(data["topic_lifecycle"]["cards"][0]["lifecycle_phase"], "主攻期")
        self.assertIn("## 知识复利提示", report)
        self.assertIn("题材生命周期证据层", [item["topic"] for item in data["knowledge_updates"]])
        self.assertIn("PCB电子材料处于主攻期", report)
        self.assertNotIn("7天", report)
        self.assertNotIn("辩论", report)

    def test_topic_lifecycle_uses_late_candidate_trace_evidence(self):
        data = {
            "trade_date": "2026-06-14",
            "realtime_tag_evidence_snapshot": {
                "groups": [
                    {
                        "采用名称": "PCB电子材料",
                        "大方向": "AI算力基础设施",
                        "当日主攻分支": "PCB电子材料",
                        "表层行业名": ["PCB", "电子材料"],
                        "资金证据": "资金指向：PCB电子材料",
                        "扩散证据": "同分支多只个股上涨",
                    }
                ]
            },
            "execution_stage_context": {},
        }

        def _render_body(current_data, *_args, **_kwargs):
            current_data["execution_stage_context"]["candidate_traces"] = [
                {
                    "stock_name": "胜宏科技",
                    "stock_code": "300476",
                    "sector": "PCB电子材料",
                    "mainline": "AI算力基础设施",
                    "final_action": "沿PCB电子材料核心承接继续观察",
                    "anchor_reversal": {
                        "candidate_role": "趋势核心",
                        "anchor_reversal_decision": "可作为主对象",
                        "anchor_reversal_reason": "核心承接稳定",
                    },
                }
            ]
            return "# runtime report"

        with patch("report.runtime._render_markdown_report_legacy_body", side_effect=_render_body):
            report_runtime.render_markdown_report_runtime(
                data,
                "2026-06-14",
                helpers={"DISPLAY_MVP_MODE": False},
                config={},
            )

        card = data["topic_lifecycle"]["cards"][0]
        self.assertEqual(card["lifecycle_phase"], "主攻期")
        self.assertTrue(card["evidence"]["core_stocks"])

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

    def test_render_markdown_report_runtime_keeps_decision_revision_lines_after_front_rebuild(self):
        def _fake_legacy_body(*args, **kwargs):
            return "# Runtime Report\n\n## 八、详细附录\n\n旧正文"

        decision_ledger_artifacts = {
            "revision_ledger": {
                "status": "written",
                "path": "data/decision-ledger/revisions/2026-05-12.jsonl",
                "latest_revision_id": "2026-05-12-r001-demo",
                "entries": [
                    {
                        "revision_id": "2026-05-12-r001-demo",
                        "revision_type": "initial",
                        "diff_summary": "首次结构化决策记录",
                    }
                ],
            }
        }

        helpers = _build_runtime_execution_test_helpers(
            lambda specs, stage_context: {"stages": [], "stage_lookup": {}, "context": stage_context},
            build_report_shell_contract=lambda *args, **kwargs: {"report": ["# Runtime Report"]},
            _build_runtime_selection_workflow=lambda *args, **kwargs: {
                "schema_version": "selection_workflow.v1",
                "candidate_pool": [],
                "final": {"execution_object": {}, "position_pct": 0, "action_text": "0%不参与"},
            },
            _build_runtime_final_target_resolution=lambda *args, **kwargs: {
                "capital_priority_decision": {"capital_priority": "wait", "reason": "无明日执行对象"}
            },
            _build_runtime_elimination_tournament_payload=lambda *args, **kwargs: {
                "schema_version": "elimination_tournament.v1",
                "layers": [],
                "final_action": {"label": "0%不参与", "position_pct": 0, "target": {}, "source": "selection_workflow.final"},
            },
            _build_runtime_sector_capital_preflight_payload=lambda *args, **kwargs: {
                "schema_version": "sector_capital_preflight.v1",
                "layers": [],
                "final_action": {"label": "0%不参与", "position_pct": 0, "target": {}, "source": "selection_workflow.final"},
            },
            render_front_page_v2=lambda lines, **kwargs: list(lines),
        )

        with patch("report.runtime._render_markdown_report_legacy_body", _fake_legacy_body):
            result = report_runtime.render_markdown_report_runtime(
                {
                    "market_research_snapshot": {},
                    "execution_stage_context": {},
                    "decision_ledger_artifacts": decision_ledger_artifacts,
                },
                "2026-05-12",
                helpers=helpers,
                config={"persist_decision_ledger": True},
            )

        self.assertIn("### 决策差异记录", result["report"])
        self.assertIn("- 修订结果：已记录；路径：data/decision-ledger/revisions/2026-05-12.jsonl", result["report"])
        self.assertIn("- 2026-05-12-r001-demo：首次记录；首次结构化决策记录", result["report"])

    def test_calendar_news_source_date_handles_datetime_module_binding(self):
        import datetime as datetime_module

        previous = report_runtime._install_runtime_bindings({"datetime": datetime_module})
        try:
            source_date = report_runtime._calendar_news_source_date({"timestamp": 1780550400})
        finally:
            report_runtime._restore_runtime_bindings(previous)

        self.assertEqual(source_date, "2026-06-04")

    def test_runtime_decision_ledger_hook_builds_and_writes_when_enabled(self):
        captured = {}

        def _fake_build_snapshot(**kwargs):
            captured["build"] = kwargs
            return {"trade_date": kwargs["trade_date"], "cases": []}

        def _fake_write_snapshot(snapshot, *, root_dir=".", write_decision_revision=True):
            captured["write"] = {
                "snapshot": snapshot,
                "root_dir": root_dir,
                "write_decision_revision": write_decision_revision,
            }
            return {
                "snapshot_path": "data/decision-ledger/2026-05-12.json",
                "revision_ledger": {
                    "status": "written",
                    "path": "data/decision-ledger/revisions/2026-05-12.jsonl",
                    "latest_revision_id": "2026-05-12-r001-demo",
                    "entries": [
                        {
                            "revision_id": "2026-05-12-r001-demo",
                            "revision_type": "initial",
                            "diff_summary": "首次结构化决策记录",
                        }
                    ],
                },
            }

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
        self.assertTrue(captured["write"]["write_decision_revision"])
        self.assertIn("### 决策差异记录", result["tracking_lines"])
        self.assertIn("- 修订结果：已记录；路径：data/decision-ledger/revisions/2026-05-12.jsonl", result["tracking_lines"])
        self.assertIn("- 2026-05-12-r001-demo：首次记录；首次结构化决策记录", result["tracking_lines"])

    def test_runtime_decision_ledger_hook_passes_canonical_final_action(self):
        captured = {}

        def _fake_build_snapshot(**kwargs):
            captured["build"] = kwargs
            return {"trade_date": kwargs["trade_date"], "cases": [], "final_action": kwargs.get("final_action")}

        def _fake_write_snapshot(snapshot, *, root_dir=".", write_json_archive=True, write_decision_revision=True):
            captured["write"] = {
                "snapshot": snapshot,
                "root_dir": root_dir,
                "write_json_archive": write_json_archive,
                "write_decision_revision": write_decision_revision,
            }
            return {
                "snapshot_path": "data/decision-ledger/2026-06-12.json",
                "revision_ledger": {"status": "written", "path": "data/decision-ledger/revisions/2026-06-12.jsonl"},
            }

        previous = report_runtime._install_runtime_bindings(
            {
                "persist_decision_ledger": True,
                "decision_ledger_root_dir": "/tmp/decision-ledger-root",
                "build_decision_ledger_snapshot": _fake_build_snapshot,
                "write_decision_ledger_artifacts": _fake_write_snapshot,
            }
        )
        try:
            final_action = report_runtime._decision_ledger_final_action_from_runtime(
                final_target_resolution={"capital_priority_decision": {"capital_priority": "wait"}},
                position_decision={"target_position_pct": 0},
                sector_capital_preflight={
                    "final_action": {
                        "label": "50%条件执行",
                        "position_pct": 50,
                        "target": {"code": "600584", "name": "长电科技", "sector": "半导体"},
                        "source": "sector_capital_carrier_strategy",
                    }
                },
            )
            result = report_runtime._maybe_persist_decision_ledger(
                data={"source_report": {"path": "reports/replay/2026-06-12_A股日报_完整版_replay.md"}},
                target_date="2026-06-12",
                execution_stage_context={"extreme_conviction_list": []},
                market_research_snapshot={},
                final_action=final_action,
            )
        finally:
            report_runtime._restore_runtime_bindings(previous)

        self.assertEqual(result["snapshot_path"], "data/decision-ledger/2026-06-12.json")
        self.assertEqual(captured["build"]["final_action"]["label"], "50%条件执行")
        self.assertEqual(captured["build"]["final_action"]["target"]["code"], "600584")
        self.assertEqual(captured["write"]["snapshot"]["final_action"]["target"]["name"], "长电科技")
        self.assertTrue(captured["write"]["write_decision_revision"])

    def test_runtime_decision_ledger_hook_recovers_final_action_from_existing_preflight(self):
        captured = {}

        def _fake_build_snapshot(**kwargs):
            captured["build"] = kwargs
            return {
                "trade_date": kwargs["trade_date"],
                "cases": [],
                "final_action": kwargs.get("final_action"),
            }

        def _fake_write_snapshot(snapshot, *, root_dir=".", write_json_archive=True, write_decision_revision=True):
            captured["write"] = {
                "snapshot": snapshot,
                "write_decision_revision": write_decision_revision,
            }
            return {
                "snapshot_path": "data/decision-ledger/2026-06-12.json",
                "revision_ledger": {"status": "unchanged", "path": "data/decision-ledger/revisions/2026-06-12.jsonl"},
            }

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
                data={
                    "sector_capital_preflight": {
                        "final_action": {
                            "label": "50%条件执行",
                            "position_pct": 50,
                            "target": {"code": "600584", "name": "长电科技", "sector": "半导体"},
                            "source": "sector_capital_preflight",
                        }
                    }
                },
                target_date="2026-06-12",
                execution_stage_context={"extreme_conviction_list": []},
                market_research_snapshot={},
            )
        finally:
            report_runtime._restore_runtime_bindings(previous)

        self.assertEqual(result["snapshot_path"], "data/decision-ledger/2026-06-12.json")
        self.assertEqual(captured["build"]["final_action"]["label"], "50%条件执行")
        self.assertEqual(captured["build"]["final_action"]["target"]["code"], "600584")
        self.assertEqual(captured["write"]["snapshot"]["final_action"]["target"]["name"], "长电科技")
        self.assertTrue(captured["write"]["write_decision_revision"])

    def test_runtime_decision_ledger_postgres_only_disables_json_archive_and_local_review_files(self):
        captured = {}

        def _fake_build_snapshot(**kwargs):
            return {"trade_date": kwargs["trade_date"], "cases": []}

        def _fake_write_snapshot(snapshot, **kwargs):
            captured["write"] = kwargs
            return {
                "snapshot_path": "postgresql://decision-ledger/2026-05-12",
                "index": {"latest_trade_date": "2026-05-12", "by_stock_code": {}},
            }

        class PostgresService:
            def is_postgres_backed(self):
                return True

            def mark_a_kill_shape_extreme_conviction_mentions(self, end_date, *, window_days=25, return_details=False):
                return {"updated_count": 0, "updated_records": []}

            def query_extreme_conviction_mentions(self, end_date, *, window_days=25, include_a_kill=False):
                return []

        class StubDatabaseService:
            @classmethod
            def from_environment(cls, db_path=None):
                return PostgresService()

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
            with patch.dict("sys.modules", {"storage.database_service": types.SimpleNamespace(DatabaseService=StubDatabaseService)}):
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

    def test_runtime_candidate_traces_can_be_built_from_selection_workflow(self):
        workflow = {
            "schema_version": "selection_workflow.v1",
            "candidate_pool": [
                {
                    "stock": {"name": "上海石化", "code": "600688", "sector": "石化"},
                    "first_seen_node": "N5",
                    "source_pools": ["涨停池"],
                    "entered_reason": "涨停样本",
                    "entry_basis": "涨停样本只能作为过程证据，不能作为新仓入口",
                    "mainline": "电力",
                    "sector": "石化",
                    "status": "降级观察",
                    "eliminated_at": "N6",
                    "eliminated_reason": "不是当前主线核心",
                }
            ],
        }
        traces = report_runtime._candidate_traces_from_selection_workflow(workflow)

        self.assertEqual(traces[0]["stock_code"], "600688")
        self.assertEqual(traces[0]["first_seen_node"], "N5")
        self.assertEqual(traces[0]["entered_reason"], "涨停样本只能作为过程证据，不能作为新仓入口")
        self.assertEqual(traces[0]["eliminated_at"], "N6")

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

        self.assertIn("**过程观察25日跟踪表**", rendered)
        self.assertIn("**历史过程复盘：明日极度看好近25日跟踪表**", rendered)
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
            "0%不参与",
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

        self.assertIn("**过程观察25日跟踪表**", result["report"])
        self.assertIn("**历史过程复盘：明日极度看好近25日跟踪表**", result["report"])
        self.assertIn("**重点观察历史回测表**", result["report"])
        self.assertIn("| 京能电力 | 600578 | D2/25 |", result["report"])

    def test_runtime_appends_five_judgment_statistics_table_from_ledger_index(self):
        def _run_execution_stages(stage_specs, stage_context=None, stage_lookup=None):
            return {"lines": [], "module_logs": [], "context": {}}

        def _fake_load_index(path):
            return {
                "by_stock_code": {
                    "600578": [
                        {
                            "stock_code": "600578",
                            "stock_name": "京能电力",
                            "planned_participation": {"source_tier": "extreme_conviction", "buy_window": "09:30-09:35"},
                            "mentions": [{"mention_trade_date": "2026-05-11", "source_section": "极度看好名单"}],
                            "judgment_reviews": [
                                {
                                    "judgment_type": "market_state",
                                    "report_date": "2026-05-11",
                                    "is_correct": True,
                                },
                                {
                                    "judgment_type": "mainline",
                                    "report_date": "2026-05-11",
                                    "is_correct": False,
                                    "mistake": "资金次日没有继续选择电力",
                                },
                            ],
                        }
                    ],
                    "002806": [
                        {
                            "stock_code": "002806",
                            "stock_name": "华锋股份",
                            "mentions": [{"mention_trade_date": "2026-05-12", "source_section": "极度看好名单"}],
                            "judgment_reviews": [
                                {
                                    "judgment_type": "mainline",
                                    "report_date": "2026-05-12",
                                    "is_correct": False,
                                    "mistake": "当天判断等待下一交易日验证",
                                },
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
            "2026-05-12",
            helpers=helpers,
            config={},
        )

        report = result["report"]
        self.assertIn("**五项判断复盘统计表**", report)
        self.assertIn("| 市场状态判断 | 进攻/退潮/修复/混沌/冰点是否被次日走势验证 |", report)
        self.assertIn("| 判断项 | 统计口径 | 已结算表现 | 最近结论 | 预期 | 实际 | 原因 |", report)
        self.assertNotIn("| 判断项 | 统计口径 | 样本 | 正确 | 错误 | 待补事实 | 已结算表现 | 错在哪 |", report)
        self.assertIn("| 主线判断 | 资金第二天是否继续选择这条线 | 0.00% | 错误 | - | - | 资金次日没有继续选择电力 |", report)

    def test_runtime_inserts_daily_judgment_panel_at_front_before_account_advice(self):
        def _run_execution_stages(stage_specs, stage_context=None, stage_lookup=None):
            return {
                "lines": [],
                "module_logs": [],
                "context": {
                    "market_state_snapshot": {"market_state": "混沌"},
                    "mainline_turnover_summary": {"current_mainline": "新型电力"},
                    "extreme_conviction_list": [
                        {
                            "stock_name": "粤电力Ａ",
                            "stock_code": "000539",
                            "planned_participation": {
                                "buy_window": "09:30-09:35",
                                "cancellation": "竞价表态、开盘承接、板块同步任一失败，按0%不参与",
                            },
                        }
                    ],
                    "position_decision": {"target_position_pct": 100, "signal_grade": "100%核心进攻"},
                },
            }

        def _fake_load_index(path):
            return {
                "available_trade_dates": ["2026-05-28", "2026-05-29", "2026-06-01"],
                "by_stock_code": {
                    "002806": [
                        {
                            "stock_code": "002806",
                            "stock_name": "华锋股份",
                            "mentions": [
                                {
                                    "mention_trade_date": "2026-05-29",
                                    "source_section": "极度看好名单",
                                    "participation_review": {
                                        "status": "预演作废",
                                        "reason": "作废条件出现，原参与方案不再成立。",
                                        "fact_inputs": {"cancellation_triggered": True},
                                    },
                                }
                            ],
                            "judgment_reviews": [
                                {
                                    "judgment_type": "market_state",
                                    "report_date": "2026-05-29",
                                    "is_correct": False,
                                    "mistake": "混沌判断偏乐观",
                                }
                            ],
                        }
                    ],
                    "000539": [
                        {
                            "stock_code": "000539",
                            "stock_name": "粤电力Ａ",
                            "mentions": [{"mention_trade_date": "2026-06-01", "source_section": "极度看好名单"}],
                        }
                    ],
                },
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
            render_front_page_v2=lambda report, **kwargs: ["# front", "", "## 明日账户建议", "| 项目 | 结论 |"],
        )

        result = report_runtime.render_markdown_report_runtime(
            {"exchange_monitor_today": [], "exchange_monitor_nextday": []},
            "2026-06-01",
            helpers=helpers,
            config={},
        )

        report = result["report"]
        self.assertIn("## 判断纠偏与今日五项结论", report)
        self.assertIn("结算上一交易日：2026-05-29", report)
        self.assertIn("今日判断（2026-06-01，等待下一交易日验证）", report)
        self.assertLess(report.index("## 判断纠偏与今日五项结论"), report.index("## 明日账户建议"))
        self.assertIn("| 核心候选判断 | 待补事实 | 下一交易日验证是否进入资金视野 |", report)
        self.assertNotIn("| 核心候选判断 | 粤电力Ａ(000539) | 下一交易日验证是否进入资金视野 |", report)

    def test_runtime_keeps_process_candidate_out_of_t006_when_appendix_mentions_it(self):
        def _run_execution_stages(stage_specs, stage_context=None, stage_lookup=None):
            return {
                "lines": [],
                "module_logs": [],
                "context": {
                    "market_state_snapshot": {"market_state": "混沌"},
                    "mainline_turnover_summary": {"current_mainline": "无确认主线"},
                    "best_stock": {"name": "双星新材", "code": "002585", "sector": "塑料"},
                    "selected_position_candidate": {
                        "name": "中船特气",
                        "code": "688146",
                        "sector": "电子化学品",
                        "sniper_role": "候选观察",
                        "anchor_reversal_decision": "降级观察",
                    },
                    "extreme_conviction_list": [
                        {
                            "name": "中船特气",
                            "code": "688146",
                            "sector": "电子化学品",
                            "sniper_role": "候选观察",
                            "anchor_reversal_decision": "降级观察",
                        },
                        {
                            "name": "双星新材",
                            "code": "002585",
                            "sector": "塑料",
                            "sniper_role": "候选观察补充",
                            "anchor_reversal_decision": "降级观察",
                        },
                    ],
                    "position_decision": {
                        "target_position_pct": 0,
                        "signal_grade": "0",
                        "participation_mode": "observe_0",
                    },
                },
            }

        helpers = _build_runtime_execution_test_helpers(
            _run_execution_stages,
            persist_decision_ledger=False,
            decision_ledger_root_dir="/tmp/decision-ledger-root",
            read_decision_ledger_index=lambda path: {"available_trade_dates": [], "by_stock_code": {}},
            build_report_shell_contract=lambda *args, **kwargs: {
                "report": [
                    "## 旧正文过程候选",
                    "| 股票 | 代码 | 身份 |",
                    "|------|------|------|",
                    "| 双星新材 | 002585 | 过程候选 |",
                ]
            },
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
            run_execution_appendix_tail=lambda payload: {
                "value": {
                    "lines": [
                        "## 附录过程候选复核",
                        "- 双星新材(002585)：过程候选，只保留观察证据。",
                    ],
                    "module_logs": [],
                    "exports": {},
                }
            },
            render_front_page_v2=lambda report, **kwargs: ["# front", "", "## 明日账户建议", "| 项目 | 结论 |"],
            DISPLAY_MVP_MODE=False,
        )
        data = {"exchange_monitor_today": [], "exchange_monitor_nextday": []}

        result = report_runtime.render_markdown_report_runtime(
            data,
            "2026-06-10",
            helpers=helpers,
            config={},
        )

        report = result["report"]
        front_text, appendix_text = report.split("## 八、详细附录", 1)
        self.assertIn("| 最终对象 | 无 |", front_text)
        self.assertIn("| 明日执行对象 | 无 |", front_text)
        self.assertIn("| 核心候选判断 | 待补事实 | 下一交易日验证是否进入资金视野 |", front_text)
        self.assertNotIn("中船特气(688146) | 下一交易日验证是否进入资金视野", front_text)
        self.assertNotIn("双星新材(002585) | 下一交易日验证是否进入资金视野", front_text)
        self.assertIn("双星新材(002585)：过程候选", appendix_text)
        audit = data["final_target_resolution_audit"]
        self.assertEqual(audit["pre_tail"]["key"], "")
        self.assertEqual(audit["front_page"]["key"], "")
        self.assertFalse(audit.get("identity_drift"))

    def test_runtime_moves_candidate_verdict_summary_after_market_spine(self):
        report = report_runtime._insert_two_layer_front_decision_panel(
            [
                "# 2026-06-04 a股市场分析",
                "",
                "### 市场阶段",
                "| 项目 | 结论 |",
                "",
                "### 资金结构",
                "| 层级 | 结论 |",
                "",
                "### 板块关系",
                "| 关系 | 主攻线 |",
                "",
                "### 超车 / 失速 / 窗口",
                "| 项目 | 状态 |",
                "",
                "### 龙头 / 核心验证",
                "| 方向 | 核心锚 |",
                "",
                "## 明日账户建议",
                "| 项目 | 结论 |",
            ],
            [
                "## 日报裁决总览",
                "| 项目 | 结论 |",
                "|------|------|",
                "| 最终对象 | 观察对象：豫能控股(001896) |",
                "",
                "### 候选胜负摘要",
                "| 候选 | 主线/板块 | 个股结构 | 资金确认 | 账户匹配 | 风险/缺失 | 结论 |",
                "|------|-----------|----------|----------|----------|-----------|------|",
                "| 上海石化(600688) | 支线 | T字板 | 资金缺失 | 不适合 | 关键缺失 | 资金确认不足 |",
                "",
                "## 明日执行结论",
                "| 项目 | 结论 |",
                "|------|------|",
                "| 明日执行对象 | 无 |",
            ],
        )
        text = "\n".join(report)

        self.assertLess(text.index("## 日报裁决总览"), text.index("### 市场阶段"))
        self.assertLess(text.index("## 明日执行结论"), text.index("### 市场阶段"))
        self.assertLess(text.index("### 龙头 / 核心验证"), text.index("### 候选胜负摘要"))
        self.assertLess(text.index("### 候选胜负摘要"), text.index("## 明日账户建议"))

    def test_runtime_inserts_single_final_target_solution_before_account_advice(self):
        def _run_execution_stages(stage_specs, stage_context=None, stage_lookup=None):
            return {
                "lines": [],
                "module_logs": [],
                "context": {
                    "market_state_snapshot": {"market_state": "退潮"},
                    "mainline_turnover_summary": {"current_mainline": "通信设备"},
                    "selected_position_candidate": {
                        "name": "工业富联",
                        "code": "601138",
                        "sector": "通信设备",
                        "sniper_role": "明日主买对象",
                        "anchor_reversal_decision": "可作为主对象",
                        "primary_buy_candidate": True,
                        "sector_anchor": "工业富联(601138)",
                        "candidate_role": "板块锚",
                        "relationship_to_anchor": "资金回流优先看板块锚，候选本身就是板块锚",
                        "anchor_reversal_reason": "候选就是板块锚，分歧后资金优先回看",
                        "leader_certainty_path": "板块锚优先，容量和趋势承接优先于一日涨停",
                        "limit_up_evidence_role": "涨停只是证据，不能替代板块锚和承接路径",
                        "target_role": "core",
                        "strength_evidence": ["通信设备资金回流", "板块锚"],
                        "probe_entry_price": 10.0,
                        "ma5": 9.9,
                        "ma10": 9.8,
                        "vwap": 9.95,
                        "stop_price": 9.6,
                        "target_price": 11.0,
                        "planned_participation": {
                            "buy_window": "09:30-09:35",
                            "fallback_state": "不满足回到0%",
                        },
                    },
                    "extreme_conviction_list": [
                        {
                            "name": "工业富联",
                            "code": "601138",
                            "sector": "通信设备",
                            "sniper_role": "明日主买对象",
                            "anchor_reversal_decision": "可作为主对象",
                            "primary_buy_candidate": True,
                            "sector_anchor": "工业富联(601138)",
                            "target_role": "core",
                            "strength_evidence": ["通信设备资金回流", "板块锚"],
                            "probe_entry_price": 10.0,
                            "ma5": 9.9,
                            "ma10": 9.8,
                            "vwap": 9.95,
                            "stop_price": 9.6,
                            "target_price": 11.0,
                        }
                    ],
                    "position_decision": {"target_position_pct": 100, "signal_grade": "100"},
                },
            }

        def _fake_load_index(path):
            return {
                "available_trade_dates": ["2026-06-01", "2026-06-02"],
                "by_stock_code": {},
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
            render_front_page_v2=lambda report, **kwargs: ["# front", "", "## 明日账户建议", "| 项目 | 结论 |"],
        )

        result = report_runtime.render_markdown_report_runtime(
            {"exchange_monitor_today": [], "exchange_monitor_nextday": []},
            "2026-06-02",
            helpers=helpers,
            config={},
        )

        report = result["report"]
        self.assertEqual(report.count("## 最终标的解题过程"), 1)
        self.assertIn("| 最终结果 | 工业富联(601138) |", report)
        self.assertIn("+-- 最终结果: 工业富联(601138)", report)
        self.assertIn("+-- 板块锚: 工业富联(601138)", report)
        self.assertIn("+-- 龙头路径: 板块锚优先，容量和趋势承接优先于一日涨停", report)
        self.assertIn("| 核心候选判断 | 工业富联(601138) | 下一交易日验证是否进入资金视野 |", report)
        self.assertLess(report.index("## 最终标的解题过程"), report.index("## 明日账户建议"))

    def test_runtime_renders_two_layer_front_decision_before_account_advice(self):
        def _run_execution_stages(stage_specs, stage_context=None, stage_lookup=None):
            return {
                "lines": [],
                "module_logs": [],
                "context": {
                    "market_state_snapshot": {"market_state": "退潮"},
                    "mainline_name": "电力",
                    "position_decision": {
                        "target_position_pct": 50,
                        "final_action": "条件满足才50%条件执行；不满足回到0%",
                    },
                    "selected_position_candidate": {
                        "name": "豫能控股",
                        "code": "001896",
                        "sector": "电力",
                        "anchor_reversal_decision": "可作为主对象",
                        "candidate_role": "板块锚",
                        "target_position_pct": 50,
                        "strength_evidence": ["板块锚", "资金回流"],
                        "probe_entry_price": 10.0,
                        "observation_price": 10.0,
                        "ma5": 9.8,
                        "ma10": 9.6,
                        "vwap": 9.9,
                        "stop_price": 9.5,
                        "invalid_price": 9.5,
                        "target_price": 11.5,
                        "planned_participation": {
                            "buy_window": "09:50-10:10",
                            "fallback_state": "条件不满足回到0%",
                        },
                    },
                    "step2_bundle": {
                        "crossline_observation_stocks": [
                            {"name": "上海石化", "code": "600688", "sector": "炼化及贸"},
                            {
                                "name": "豫能控股",
                                "code": "001896",
                                "sector": "电力",
                                "anchor_reversal_decision": "可作为主对象",
                                "candidate_role": "板块锚",
                                "target_position_pct": 50,
                                "strength_evidence": ["板块锚", "资金回流"],
                                "probe_entry_price": 10.0,
                                "observation_price": 10.0,
                                "ma5": 9.8,
                                "ma10": 9.6,
                                "vwap": 9.9,
                                "stop_price": 9.5,
                                "invalid_price": 9.5,
                                "target_price": 11.5,
                                "planned_participation": {
                                    "buy_window": "09:50-10:10",
                                    "fallback_state": "条件不满足回到0%",
                                },
                            },
                        ]
                    },
                    "step3_bundle": {"focus_group": [{"name": "豫能控股", "code": "001896"}]},
                    "executable_stocks": [{"name": "豫能控股", "code": "001896"}],
                    "market_research_snapshot": {},
                },
            }

        helpers = _build_runtime_execution_test_helpers(
            _run_execution_stages,
            persist_decision_ledger=False,
            decision_ledger_root_dir="/tmp/decision-ledger-root",
            read_decision_ledger_index=lambda path: {"available_trade_dates": [], "by_stock_code": {}},
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
            render_front_page_v2=lambda report, **kwargs: ["# front", "", "## 明日账户建议", "| 项目 | 结论 |"],
        )

        data = {
            "target_date": "2026-06-04",
            "best_stock": {"name": "豫能控股", "code": "001896", "sector": "电力"},
            "exchange_monitor_today": [],
            "exchange_monitor_nextday": [],
        }
        result = report_runtime.render_markdown_report_runtime(
            data,
            "2026-06-04",
            helpers=helpers,
            config={},
        )
        report = result["report"]

        self.assertIn("## 明日执行结论", report)
        self.assertIn("| 明日执行对象 | 豫能控股(001896) |", report)
        self.assertIn("## 50%条件执行条件", report)
        self.assertIn("低开承接型", report)
        self.assertIn("主动进攻型", report)
        self.assertIn("## 推导审计层", report)
        self.assertIn("### 主线推导链", report)
        self.assertIn("#### N3 板块关系拆解", report)
        self.assertIn("#### N6 反推龙头", report)
        self.assertIn("#### N8 仓位与执行条件", report)
        self.assertIn("### 候选生命周期证据", report)
        self.assertIn("| 最终结果 | 豫能控股(001896) |", report)
        self.assertNotIn("| 最终结果 | 暂无 |", report)
        self.assertLess(report.index("## 明日执行结论"), report.index("## 判断纠偏与今日五项结论"))
        self.assertLess(report.index("## 明日执行结论"), report.index("## 最终标的解题过程"))
        self.assertLess(report.index("## 明日执行结论"), report.index("## 明日账户建议"))
        self.assertEqual(data["two_layer_decision_payload"]["front_decision"]["execution_object"]["code"], "001896")

    def test_runtime_stores_selection_workflow_on_all_contexts(self):
        def _run_execution_stages(stage_specs, stage_context=None, stage_lookup=None):
            return {
                "lines": [],
                "module_logs": [],
                "context": {
                    "market_state_snapshot": {"market_state": "退潮"},
                    "mainline_name": "电力",
                    "mainline_turnover_summary": {"current_mainline": "电力"},
                    "position_decision": {
                        "target_position_pct": 50,
                        "final_action": "条件满足才50%条件执行；不满足回到0%",
                    },
                    "selected_position_candidate": {
                        "name": "豫能控股",
                        "code": "001896",
                        "sector": "电力",
                        "anchor_reversal_decision": "可作为主对象",
                        "candidate_role": "板块锚",
                        "strength_evidence": ["板块锚", "资金回流"],
                        "probe_entry_price": 10.0,
                        "observation_price": 10.0,
                        "ma5": 9.8,
                        "ma10": 9.6,
                        "vwap": 9.9,
                        "stop_price": 9.5,
                        "invalid_price": 9.5,
                        "target_price": 11.5,
                        "planned_participation": {
                            "buy_window": "09:50-10:10",
                            "fallback_state": "条件不满足回到0%",
                        },
                    },
                    "extreme_conviction_list": [
                        {
                            "name": "豫能控股",
                            "code": "001896",
                            "sector": "电力",
                            "anchor_reversal_decision": "可作为主对象",
                            "candidate_role": "板块锚",
                            "strength_evidence": ["板块锚", "资金回流"],
                            "probe_entry_price": 10.0,
                            "observation_price": 10.0,
                            "ma5": 9.8,
                            "ma10": 9.6,
                            "vwap": 9.9,
                            "stop_price": 9.5,
                            "invalid_price": 9.5,
                            "target_price": 11.5,
                        }
                    ],
                    "market_research_snapshot": {},
                },
            }

        captured = {}

        def _fake_front_page(report, **kwargs):
            captured["snapshot"] = kwargs["market_research_snapshot"]
            return ["# front", "", "## 明日账户建议", "| 项目 | 结论 |"]

        helpers = _build_runtime_execution_test_helpers(
            _run_execution_stages,
            persist_decision_ledger=False,
            decision_ledger_root_dir="/tmp/decision-ledger-root",
            read_decision_ledger_index=lambda path: {"available_trade_dates": [], "by_stock_code": {}},
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
            render_front_page_v2=_fake_front_page,
        )
        data = {
            "target_date": "2026-06-04",
            "exchange_monitor_today": [],
            "exchange_monitor_nextday": [],
        }

        report_runtime.render_markdown_report_runtime(
            data,
            "2026-06-04",
            helpers=helpers,
            config={},
        )

        execution_context = data["execution_stage_context"]
        market_snapshot = data["market_research_snapshot"]
        front_snapshot = captured["snapshot"]
        workflow = data["selection_workflow"]

        self.assertEqual(workflow["schema_version"], "selection_workflow.v1")
        self.assertEqual(workflow["final"]["execution_object"]["code"], "001896")
        self.assertEqual(workflow["final"]["position_pct"], 50)
        self.assertIs(execution_context["selection_workflow"], workflow)
        self.assertIs(market_snapshot["selection_workflow"], workflow)
        self.assertIs(front_snapshot["selection_workflow"], workflow)
        self.assertIs(data["execution_stage_context"], execution_context)
        self.assertIs(execution_context["market_research_snapshot"], market_snapshot)
        self.assertIs(data["execution_stage_context"]["selection_workflow"], workflow)
        self.assertIs(data["market_research_snapshot"]["selection_workflow"], workflow)
        self.assertIs(execution_context["market_research_snapshot"]["selection_workflow"], workflow)

    def test_sector_capital_carrier_strategy_becomes_selection_workflow_final_object(self):
        def _run_execution_stages(stage_specs, stage_context=None, stage_lookup=None):
            return {
                "lines": [],
                "module_logs": [],
                "context": {
                    "market_state_snapshot": {"market_state": "修复"},
                    "mainline_name": "半导体",
                    "mainline_turnover_summary": {"current_mainline": "半导体"},
                    "position_decision": {"target_position_pct": 0, "signal_grade": "0"},
                    "market_research_snapshot": {},
                },
            }

        captured = {}

        def _fake_front_page(report, **kwargs):
            captured["snapshot"] = kwargs["market_research_snapshot"]
            return ["# front", "", "## 明日账户建议", "| 项目 | 结论 |"]

        helpers = _build_runtime_execution_test_helpers(
            _run_execution_stages,
            persist_decision_ledger=False,
            decision_ledger_root_dir="/tmp/decision-ledger-root",
            read_decision_ledger_index=lambda path: {"available_trade_dates": [], "by_stock_code": {}},
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
            render_front_page_v2=_fake_front_page,
        )
        data = {
            "target_date": "2026-06-12",
            "hot_plates": [{"name": "半导体", "order": 1, "tag": "主线"}],
            "sector_fund_flow": {
                "inflow": [{"name": "半导体", "change_pct": 2.1, "net_inflow_yi": 18.0}]
            },
            "turnover_rank": [
                {
                    "code": "600584",
                    "name": "长电科技",
                    "rank": 6,
                    "sector": "半导体",
                    "turnover": 76.0,
                }
            ],
            "integrated_hot_list": [
                {
                    "code": "600584",
                    "name": "长电科技",
                    "rank": 8,
                    "sector": "半导体",
                }
            ],
            "exchange_monitor_today": [],
            "exchange_monitor_nextday": [],
        }

        report_runtime.render_markdown_report_runtime(
            data,
            "2026-06-12",
            helpers=helpers,
            config={},
        )

        workflow = data["selection_workflow"]
        final = workflow["final"]
        execution_context = data["execution_stage_context"]
        preflight = data["sector_capital_preflight"]

        self.assertEqual(final["execution_object"]["code"], "600584")
        self.assertEqual(final["position_pct"], 50)
        self.assertEqual(final["action_text"], "50%条件执行")
        self.assertEqual(execution_context["selected_position_candidate"]["code"], "600584")
        self.assertEqual(execution_context["position_decision"]["target_position_pct"], 50)
        self.assertEqual(preflight["final_action"]["target"]["code"], "600584")
        self.assertEqual(
            preflight["tplus_rehearsal"]["tplus1"]["participation_qualification"],
            "有条件参与",
        )
        self.assertEqual(preflight["final_action"]["label"], "50%条件执行")
        self.assertEqual(preflight["final_action"]["position_pct"], 50)
        self.assertIs(captured["snapshot"]["selection_workflow"], workflow)

    def test_sector_capital_carrier_skips_pseudo_precise_opportunity_comparison(self):
        selected = {
            "name": "长电科技",
            "code": "600584",
            "sector": "半导体",
            "candidate_origin": "sector_capital_carrier_v1",
            "conditional_execution_source": "sector_capital_carrier_strategy",
            "target_position_pct": 50,
            "target_role": "attack_prepare",
            "planned_participation": {
                "buy_window": "09:50-10:10",
                "fallback_state": "T+1板块早盘失去扩散或核心掉队，回到0%不参与",
            },
        }

        position_decision = report_runtime._build_front_page_position_decision(
            position_decision={"target_position_pct": 50, "signal_grade": "50"},
            selected_position_candidate=selected,
            data={},
            market_research_snapshot={},
        )
        resolution = report_runtime._build_runtime_final_target_resolution(
            data={},
            selected_position_candidate=selected,
            position_decision=position_decision,
            market_research_snapshot={},
        )

        self.assertEqual(position_decision["target_position_pct"], 50)
        self.assertEqual(resolution["new_entry_target"]["code"], "600584")
        self.assertEqual(resolution["capital_priority_decision"]["capital_priority"], "new_entry")
        self.assertEqual(resolution["opportunity_comparison"], {})

    def test_sector_capital_carrier_with_old_position_renders_opportunity_comparison(self):
        selected = {
            "name": "长电科技",
            "code": "600584",
            "sector": "半导体",
            "candidate_origin": "sector_capital_carrier_v1",
            "conditional_execution_source": "sector_capital_carrier_strategy",
            "target_position_pct": 50,
            "target_role": "sector_anchor",
            "strength_evidence": ["板块资金扩散", "容量核心"],
            "ma_reversion_entry": 86.0,
            "ma5": 85.6,
            "ma10": 85.88,
            "stop_price": 84.0,
            "high": 91.33,
        }
        data = {
            "personal_position_context": {
                "account_profile": {"capital_text": "约1w账户"},
                "existing_position_summary": {
                    "has_position": True,
                    "summary": "持有太极实业(600667)，100%仓位；先处理旧仓；新开仓0手",
                },
            }
        }

        position_decision = report_runtime._build_front_page_position_decision(
            position_decision={"target_position_pct": 50, "signal_grade": "50"},
            selected_position_candidate=selected,
            data=data,
            market_research_snapshot={},
        )
        resolution = report_runtime._build_runtime_final_target_resolution(
            data=data,
            selected_position_candidate=selected,
            position_decision=position_decision,
            market_research_snapshot={},
        )
        rendered = "\n".join(
            report_runtime._runtime_opportunity_comparison_lines(
                resolution["opportunity_comparison"],
                two_layer_execution_object=selected,
            )
        )

        self.assertEqual(resolution["capital_priority_decision"]["capital_priority"], "new_entry_after_old_exit")
        self.assertIn("## 旧仓与新机会风险价格对比", rendered)
        self.assertIn("| 持有太极实业(600667) | old_position |", rendered)
        self.assertIn("| 长电科技(600584) | 条件执行对象 | 86.00 | 85.60 / -0.47% |", rendered)

    def test_final_target_resolution_uses_selection_workflow_final_object(self):
        stale_selected = {
            "name": "上海石化",
            "code": "600688",
            "sector": "炼化及贸",
            "anchor_reversal_decision": "可作为主对象",
            "candidate_role": "板块锚",
        }
        final_object = {
            "name": "豫能控股",
            "code": "001896",
            "sector": "电力",
            "candidate_role": "观察样本",
            "observation_layer": "process_observation",
            "front_observation_qualified": False,
        }
        data = {
            "selection_workflow": {
                "schema_version": "selection_workflow.v1",
                "final": {
                    "execution_object": final_object,
                    "position_pct": 50,
                    "action_text": "50%条件执行",
                },
            }
        }

        resolution = report_runtime._build_runtime_final_target_resolution(
            data=data,
            selected_position_candidate=stale_selected,
            position_decision={"target_position_pct": 0, "signal_grade": "0"},
            market_research_snapshot={},
        )

        self.assertEqual(resolution["new_entry_target"]["code"], "001896")
        self.assertEqual(resolution["display_target"]["code"], "001896")
        self.assertEqual(resolution["capital_priority_decision"]["capital_priority"], "new_entry")
        self.assertNotEqual(resolution["new_entry_target"]["code"], "600688")
        self.assertEqual(resolution["new_entry_target"]["candidate_role"], "观察样本")

        context_only_resolution = report_runtime._build_runtime_final_target_resolution(
            data={},
            execution_stage_context={"selection_workflow": data["selection_workflow"]},
            selected_position_candidate=stale_selected,
            position_decision={"target_position_pct": 0, "signal_grade": "0"},
            market_research_snapshot={},
        )

        self.assertEqual(context_only_resolution["new_entry_target"]["code"], "001896")
        self.assertNotEqual(context_only_resolution["new_entry_target"]["code"], "600688")

    def test_final_target_resolution_blocks_workflow_object_when_position_is_zero(self):
        stale_selected = {
            "name": "上海石化",
            "code": "600688",
            "sector": "炼化及贸",
            "anchor_reversal_decision": "可作为主对象",
        }
        data = {
            "selection_workflow": {
                "schema_version": "selection_workflow.v1",
                "final": {
                    "execution_object": {},
                    "position_pct": 0,
                    "action_text": "0%不参与",
                },
                "candidate_pool": [],
            }
        }

        resolution = report_runtime._build_runtime_final_target_resolution(
            data=data,
            selected_position_candidate=stale_selected,
            position_decision={"target_position_pct": 50, "signal_grade": "50"},
            market_research_snapshot={},
        )

        self.assertEqual(resolution["new_entry_target"], {})
        self.assertEqual(resolution["process_target"], {})
        self.assertEqual(resolution["ascii_trace_target"], {})
        self.assertEqual(resolution["watch_target"], {})
        self.assertEqual(resolution["display_target"], {})
        self.assertEqual(resolution["capital_priority_decision"]["capital_priority"], "wait")
        self.assertEqual(resolution["opportunity_comparison"], {})

    def test_runtime_final_resolution_suppresses_explicit_candidate_when_workflow_is_zero_position(self):
        selected = {
            "name": "豫能控股",
            "code": "001896",
            "sector": "电力",
            "anchor_reversal_decision": "可作为主对象",
        }
        data = {
            "selection_workflow": {
                "schema_version": "selection_workflow.v1",
                "final": {
                    "execution_object": {},
                    "position_pct": 0,
                    "action_text": "0%不参与",
                },
                "nodes": [{"node_id": "N5", "passes_forward": {"candidate_count": 0}}],
                "candidate_pool": [],
            }
        }

        resolution = report_runtime._build_runtime_final_target_resolution(
            data=data,
            selected_position_candidate=selected,
            position_decision={"target_position_pct": 50, "signal_grade": "50"},
            market_research_snapshot={},
        )

        self.assertEqual(resolution["new_entry_target"], {})
        self.assertEqual(resolution["process_target"], {})
        self.assertEqual(resolution["ascii_trace_target"], {})
        self.assertEqual(resolution["watch_target"], {})
        self.assertEqual(resolution["display_target"], {})
        self.assertEqual(resolution["capital_priority_decision"]["capital_priority"], "wait")
        self.assertEqual(resolution["opportunity_comparison"], {})

    def test_workflow_zero_position_does_not_build_opportunity_comparison_from_process_candidate(self):
        data = {
            "selection_workflow": {
                "schema_version": "selection_workflow.v1",
                "final": {
                    "execution_object": {},
                    "position_pct": 0,
                    "action_text": "0%不参与",
                },
                "candidate_pool": [],
            }
        }
        selected = {
            "name": "和远气体",
            "code": "002971",
            "sector": "化学制品",
            "identity": "过程候选",
            "target_role": "过程候选",
            "source_pools": ["过程候选"],
            "target_position_pct": 50,
            "participation_window": "09:50-10:10",
            "fallback_state": "不满足回到0%",
        }

        resolution = report_runtime._build_runtime_final_target_resolution(
            data=data,
            selected_position_candidate=selected,
            position_decision={"target_position_pct": 50, "signal_grade": "50"},
            market_research_snapshot={},
        )

        self.assertEqual(resolution["new_entry_target"], {})
        self.assertEqual(resolution["process_target"], {})
        self.assertEqual(resolution["ascii_trace_target"], {})
        self.assertEqual(resolution["watch_target"], {})
        self.assertEqual(resolution["display_target"], {})
        self.assertEqual(resolution["opportunity_comparison"], {})

    def test_runtime_final_resolution_keeps_workflow_process_core_out_of_watch_target_when_position_is_zero(self):
        selected = {
            "name": "豫能控股",
            "code": "001896",
            "sector": "电力",
            "anchor_reversal_decision": "可作为主对象",
            "candidate_role": "板块锚",
        }
        data = {
            "selection_workflow": {
                "schema_version": "selection_workflow.v1",
                "final": {
                    "execution_object": {},
                    "position_pct": 0,
                    "action_text": "0%不参与",
                },
                "candidate_pool": [
                    {
                        "stock": {"name": "豫能控股", "code": "001896", "sector": "电力"},
                        "status": "过程候选",
                        "reversal_decision": "可作为主对象",
                        "sector_role": "板块锚",
                    }
                ],
            }
        }

        resolution = report_runtime._build_runtime_final_target_resolution(
            data=data,
            selected_position_candidate=selected,
            position_decision={"target_position_pct": 50, "signal_grade": "50"},
            market_research_snapshot={},
        )

        self.assertEqual(resolution["new_entry_target"], {})
        self.assertEqual(resolution["process_target"], {})
        self.assertEqual(resolution["ascii_trace_target"], {})
        self.assertEqual(resolution["watch_target"], {})
        self.assertEqual(resolution["display_target"], {})
        self.assertEqual(resolution["capital_priority_decision"]["capital_priority"], "wait")

    def test_runtime_final_resolution_rejects_process_identity_even_when_front_observation_qualified(self):
        data = {
            "selection_workflow": {
                "schema_version": "selection_workflow.v1",
                "final": {
                    "execution_object": {},
                    "position_pct": 0,
                    "action_text": "0%不参与",
                },
                "candidate_pool": [
                    {
                        "stock": {"name": "康强电子", "code": "002119", "sector": "半导体"},
                        "identity": "过程候选",
                        "target_role": "过程候选",
                        "source_pools": ["观察样本"],
                        "front_observation_qualified": True,
                        "front_observation_reason": "过程层观察，不是当前对象",
                        "observation_layer": "front_observation",
                    }
                ],
            }
        }

        resolution = report_runtime._build_runtime_final_target_resolution(
            data=data,
            selected_position_candidate={"name": "康强电子", "code": "002119", "sector": "半导体"},
            position_decision={"target_position_pct": 50, "signal_grade": "50"},
            market_research_snapshot={},
        )

        self.assertEqual(resolution["new_entry_target"], {})
        self.assertEqual(resolution["process_target"], {})
        self.assertEqual(resolution["ascii_trace_target"], {})
        self.assertEqual(resolution["watch_target"], {})
        self.assertEqual(resolution["display_target"], {})

    def test_selection_workflow_zero_blocks_surface_candidate_even_with_front_observation(self):
        workflow = {
            "schema_version": "selection_workflow.v1",
            "final": {
                "execution_object": {},
                "position_pct": 0,
                "action_text": "0%不参与",
            },
            "candidate_pool": [
                {
                    "stock": {"name": "和远气体", "code": "002971", "sector": "化学制品"},
                    "status": "观察对象",
                    "front_observation_qualified": True,
                    "front_observation_reason": "明确保留前台观察",
                    "observation_layer": "front_observation",
                }
            ],
        }

        self.assertTrue(
            report_runtime._runtime_selection_workflow_zero_blocks_surface_candidate(
                data={"selection_workflow": workflow}
            )
        )

    def test_runtime_final_resolution_rejects_source_pool_process_identity(self):
        data = {
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
                        "source_pool": "过程候选",
                        "source_pools": ["观察样本"],
                        "front_observation_qualified": True,
                        "front_observation_reason": "过程候选只回放推导",
                        "observation_layer": "front_observation",
                    }
                ],
            }
        }

        resolution = report_runtime._build_runtime_final_target_resolution(
            data=data,
            selected_position_candidate={
                "name": "和远气体",
                "code": "002971",
                "sector": "化学制品",
                "target_position_pct": 50,
                "participation_window": "09:50-10:10",
                "fallback_state": "不满足回到0%",
            },
            position_decision={"target_position_pct": 50, "signal_grade": "50"},
            market_research_snapshot={},
        )

        self.assertEqual(resolution["new_entry_target"], {})
        self.assertEqual(resolution["process_target"], {})
        self.assertEqual(resolution["ascii_trace_target"], {})
        self.assertEqual(resolution["watch_target"], {})
        self.assertEqual(resolution["display_target"], {})
        self.assertEqual(resolution["opportunity_comparison"], {})

    def test_runtime_final_resolution_clears_not_qualified_skip_candidate_when_final_is_zero(self):
        data = {
            "selection_workflow": {
                "schema_version": "selection_workflow.v1",
                "final": {
                    "execution_object": {},
                    "position_pct": 0,
                    "action_text": "0%不参与",
                },
                "candidate_pool": [],
            }
        }
        selected = {
            "name": "和远气体",
            "code": "002971",
            "sector": "化工原料",
            "candidate_role": "板块锚",
            "anchor_reversal_decision": "可作为主对象",
            "market_participation_qualification": "not_qualified",
            "position_plan_pct": 0,
            "planned_participation": {
                "action": "skip",
                "attack_state": "0%不参与",
                "buy_window": "09:30-09:35",
                "fallback_state": "不满足回到0%",
            },
        }

        resolution = report_runtime._build_runtime_final_target_resolution(
            data=data,
            selected_position_candidate=selected,
            position_decision={"target_position_pct": 50, "signal_grade": "50"},
            market_research_snapshot={},
        )

        self.assertEqual(resolution["new_entry_target"], {})
        self.assertEqual(resolution["process_target"], {})
        self.assertEqual(resolution["ascii_trace_target"], {})
        self.assertEqual(resolution["watch_target"], {})
        self.assertEqual(resolution["display_target"], {})
        self.assertEqual(resolution["capital_priority_decision"]["capital_priority"], "wait")

    def test_decision_ledger_not_qualified_skip_record_cannot_be_front_page_target(self):
        data = {
            "target_date": "2026-06-11",
            "decision_ledger_artifacts": {
                "index": {
                    "by_stock_code": {
                        "002971": [
                            {
                                "latest_trade_date": "2026-06-11",
                                "stock_name": "和远气体",
                                "stock_code": "002971",
                                "candidate_role": "板块锚",
                                "anchor_reversal_decision": "可作为主对象",
                                "market_participation_qualification": "not_qualified",
                                "position_plan_pct": 0,
                                "hypothesis": {"sector_candidate": "化工原料"},
                                "planned_participation": {
                                    "action": "skip",
                                    "attack_state": "0%不参与",
                                    "buy_window": "09:30-09:35",
                                    "fallback_state": "不满足回到0%",
                                },
                                "mentions": [
                                    {
                                        "mention_trade_date": "2026-06-11",
                                        "rank": 1,
                                        "source_section": "极度看好名单",
                                    }
                                ],
                            }
                        ]
                    }
                }
            },
        }

        selected = report_runtime._resolve_front_page_target_candidate(
            data=data,
            execution_stage_context={"position_decision": {"target_position_pct": 0}},
            report_lines=[],
            target_date="2026-06-11",
        )

        self.assertEqual(selected, {})

    def test_runtime_replaces_early_pk_stage_after_empty_final_resolution(self):
        original = [
            "##### 附录：Step 4 - 明日观察位预计算",
            "step4",
            "##### 附录：Step 5 - PK决胜局（期望值模型）",
            "**最终动作表**（只展示真正具备参与资格的对象）:",
            "| 明天具体怎么做 | 股票 | 代码 | 触发条件 | 止损/时间 |",
            "| ⏳ 确认后执行预案 | 和远气体 | 002971 | 09:50-10:10站上52.75 | 50.11 |",
            "**先看顺序**（优先盯最能反映主线承接的对象）:",
            "- 👀 和远气体(002971) - 跨线继续看谁，09:50-10:10观察价52.75",
            "**过程观察25日跟踪表**",
            "tracking",
        ]
        replacement = [
            "##### 附录：Step 5 - PK决胜局（期望值模型）",
            "**最终动作表**（只展示真正具备参与资格的对象）:",
            "| 明天具体怎么做 | 股票 | 代码 | 触发条件 | 止损/时间 |",
            "| 暂无执行预案 | - | - | 当前最终对象为空，只回放过程候选，不新增参与 | - |",
        ]

        replaced = report_runtime._replace_pk_decision_stage_lines(original, replacement)
        rendered = "\n".join(replaced)

        self.assertIn("##### 附录：Step 4 - 明日观察位预计算", rendered)
        self.assertIn("**过程观察25日跟踪表**", rendered)
        self.assertIn("| 暂无执行预案 | - | - | 当前最终对象为空，只回放过程候选，不新增参与 | - |", rendered)
        self.assertNotIn("确认后执行预案", rendered)
        self.assertNotIn("和远气体", rendered)

    def test_zero_front_page_triggers_process_candidate_soft_word_cleanup(self):
        lines = [
            "## 日报裁决总览",
            "| 项目 | 结论 |",
            "|------|------|",
            "| 仓位姿态 | 0%不参与 |",
            "| 最终对象 | 无 |",
            "**备用观察**（观察位未触发，明日不操作）:",
            "- ⏳ 和远气体(002971) - 过程候选，等观察位出现，09:50-10:10观察价52.75",
            "- 👀 和远气体(002971) - 跨线继续看谁，09:50-10:10观察价52.75",
        ]

        rendered = "\n".join(report_runtime._sanitize_report_lines(lines))

        self.assertIn("仅保留过程回看", rendered)
        self.assertIn("跨线回看样本", rendered)
        self.assertNotIn("等观察位出现", rendered)
        self.assertNotIn("跨线继续看谁", rendered)

    def test_zero_appendix_relabels_entry_plan_waiting_process_candidate(self):
        lines = [
            "##### 附录：Step 4 - 明日观察位预计算",
            "**明日观察位预计算表**:",
            "| 股票 | 代码 | 观察资格 | 怎么观察 | 日线预设区间 | 09:50-10:10观察价 | 价格怎么盯 | 明天具体怎么做 |",
            "|------|------|----------|----------|------------|--------------|----------|----------|",
            "| 和远气体 | 002971 | 过程候选 | 观察 | - | 52.75 | 关键位/带50.11（支撑/失效） | ⏳明日继续观察 |",
            "**明日触发条件汇总**:",
            "**明日继续观察**（1只，等观察位出现）:",
            "- ⏳ 和远气体(002971) - 过程候选，等观察位出现，09:50-10:10观察价52.75",
        ]

        normalized = report_runtime._normalize_attack_preview_appendix_lines(
            lines,
            final_target_resolution={
                "watch_target": {},
                "capital_priority_decision": {"capital_priority": "wait"},
            },
        )
        rendered = "\n".join(
            report_runtime._sanitize_report_lines(
                [
                    "## 日报裁决总览",
                    "| 项目 | 结论 |",
                    "|------|------|",
                    "| 仓位姿态 | 0%不参与 |",
                    "| 最终对象 | 无 |",
                ]
                + normalized
            )
        )

        self.assertIn("| 和远气体 | 002971 | 过程候选 | 观察 | - | 52.75 | 关键位/带50.11（支撑/失效） | 只作过程回放，不新增参与 |", rendered)
        self.assertIn("**过程候选回看**（1只，不作为明日对象）:（过程证据）", rendered)
        self.assertIn("过程候选，仅保留过程回看", rendered)
        self.assertNotIn("⏳明日继续观察", rendered)
        self.assertNotIn("等观察位出现", rendered)

    def test_workflow_empty_final_dict_suppresses_selected_candidate(self):
        selected = {
            "name": "和远气体",
            "code": "002971",
            "sector": "化学制品",
            "anchor_reversal_decision": "可作为主对象",
            "candidate_role": "板块锚",
        }
        data = {
            "selection_workflow": {
                "schema_version": "selection_workflow.v1",
                "final": {},
                "candidate_pool": [],
            }
        }

        resolution = report_runtime._build_runtime_final_target_resolution(
            data=data,
            selected_position_candidate=selected,
            position_decision={"target_position_pct": 50, "signal_grade": "50"},
            market_research_snapshot={},
        )

        self.assertEqual(resolution["new_entry_target"], {})
        self.assertEqual(resolution["process_target"], {})
        self.assertEqual(resolution["ascii_trace_target"], {})
        self.assertEqual(resolution["watch_target"], {})
        self.assertEqual(resolution["display_target"], {})
        self.assertEqual(resolution["capital_priority_decision"]["capital_priority"], "wait")

    def test_runtime_final_resolution_rejects_qualified_process_observation_candidate(self):
        data = {
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
                        "status": "过程候选",
                        "sector_role": "观察样本",
                        "front_observation_qualified": True,
                        "front_observation_reason": "过程层观察，不是当前对象",
                        "observation_layer": "process_observation",
                    }
                ],
            }
        }

        resolution = report_runtime._build_runtime_final_target_resolution(
            data=data,
            selected_position_candidate={"name": "和远气体", "code": "002971", "sector": "化学制品"},
            position_decision={"target_position_pct": 50, "signal_grade": "50"},
            market_research_snapshot={},
        )

        self.assertEqual(resolution["new_entry_target"], {})
        self.assertEqual(resolution["process_target"], {})
        self.assertEqual(resolution["ascii_trace_target"], {})
        self.assertEqual(resolution["watch_target"], {})
        self.assertEqual(resolution["display_target"], {})
        self.assertEqual(resolution["capital_priority_decision"]["capital_priority"], "wait")

    def test_runtime_final_resolution_clears_explicit_front_observation_when_workflow_final_is_zero(self):
        data = {
            "selection_workflow": {
                "schema_version": "selection_workflow.v1",
                "final": {
                    "execution_object": {},
                    "position_pct": 0,
                    "action_text": "0%不参与",
                },
                "candidate_pool": [
                    {
                        "stock": {"name": "豫能控股", "code": "001896", "sector": "电力"},
                        "status": "观察对象",
                        "reversal_decision": "降级观察",
                        "sector_role": "主线核心",
                        "front_observation_qualified": True,
                        "front_observation_reason": "明确保留前台观察",
                        "observation_layer": "front_observation",
                    }
                ],
            }
        }

        resolution = report_runtime._build_runtime_final_target_resolution(
            data=data,
            selected_position_candidate={"name": "豫能控股", "code": "001896", "sector": "电力"},
            position_decision={"target_position_pct": 50, "signal_grade": "50"},
            market_research_snapshot={},
        )

        self.assertEqual(resolution["new_entry_target"], {})
        self.assertEqual(resolution["watch_target"], {})
        self.assertEqual(resolution["display_target"], {})
        self.assertEqual(resolution["capital_priority_decision"]["capital_priority"], "wait")

    def test_final_target_resolution_skips_process_observation_and_keeps_front_observation(self):
        data = {
            "selection_workflow": {
                "schema_version": "selection_workflow.v1",
                "final": {
                    "execution_object": {},
                    "position_pct": 0,
                    "action_text": "0%不参与",
                },
                "candidate_pool": [
                    {
                        "stock": {"name": "双星新材", "code": "002585", "sector": "塑料"},
                        "status": "降级观察",
                        "reversal_decision": "降级观察",
                        "sector_role": "观察样本",
                        "front_observation_qualified": False,
                        "front_observation_reason": "本板块锚未识别，只能作为过程观察样本",
                        "observation_layer": "process_observation",
                    },
                    {
                        "stock": {"name": "雅克科技", "code": "002409", "sector": "半导体"},
                        "status": "降级观察",
                        "reversal_decision": "降级观察",
                        "sector_role": "大容量中军",
                        "front_observation_qualified": True,
                        "front_observation_reason": "主线内观察对象，仓位结论为0%时只作前台观察",
                        "observation_layer": "front_observation",
                    },
                ],
            }
        }

        resolution = report_runtime._build_runtime_final_target_resolution(
            data=data,
            selected_position_candidate={"name": "双星新材", "code": "002585", "sector": "塑料"},
            position_decision={"target_position_pct": 0, "signal_grade": "0"},
            market_research_snapshot={},
        )

        self.assertEqual(resolution["capital_priority_decision"]["capital_priority"], "wait")
        self.assertEqual(resolution["watch_target"], {})
        self.assertEqual(resolution["new_entry_target"], {})
        self.assertEqual(resolution["display_target"], {})

    def test_selection_workflow_can_feed_two_layer_and_sniper_packets(self):
        data = {"target_date": "2026-06-04"}
        execution_context = {
            "market_state_snapshot": {"market_state": "退潮"},
            "mainline_name": "电力",
            "selected_position_candidate": {"name": "上海石化", "code": "600688", "sector": "炼化及贸"},
            "extreme_conviction_list": [
                {
                    "name": "豫能控股",
                    "code": "001896",
                    "sector": "电力",
                    "anchor_reversal_decision": "可作为主对象",
                    "candidate_role": "板块锚",
                },
                {
                    "name": "上海石化",
                    "code": "600688",
                    "sector": "炼化及贸",
                    "anchor_reversal_decision": "降级观察",
                    "candidate_role": "过程候选",
                },
            ],
        }
        market_snapshot = {}
        workflow = report_runtime._build_runtime_selection_workflow(
            target_date="2026-06-04",
            data=data,
            execution_stage_context=execution_context,
            market_research_snapshot=market_snapshot,
            selected_position_candidate={"name": "豫能控股", "code": "001896", "sector": "电力"},
            position_decision={"target_position_pct": 50, "signal_grade": "50"},
        )
        report_runtime._store_runtime_selection_workflow(
            workflow,
            data=data,
            execution_stage_context=execution_context,
            market_research_snapshot=market_snapshot,
        )

        resolution = report_runtime._build_runtime_final_target_resolution(
            data=data,
            selected_position_candidate={"name": "上海石化", "code": "600688", "sector": "炼化及贸"},
            position_decision={"target_position_pct": 0, "signal_grade": "0"},
            market_research_snapshot=market_snapshot,
        )
        two_layer = report_runtime.build_two_layer_decision_payload(
            target_date="2026-06-04",
            final_target_resolution=resolution,
            position_decision={"target_position_pct": 50, "signal_grade": "50"},
            execution_stage_context=execution_context,
        )
        sniper = report_runtime._build_sniper_target_derivation_packet(
            data=data,
            execution_stage_context=execution_context,
            market_research_snapshot=market_snapshot,
            final_target_resolution=resolution,
            selected_position_candidate={"name": "上海石化", "code": "600688", "sector": "炼化及贸"},
            position_decision={"target_position_pct": 50, "signal_grade": "50"},
            two_layer_decision_payload=two_layer,
        )

        self.assertEqual(workflow["final"]["execution_object"]["code"], "001896")
        self.assertEqual(resolution["new_entry_target"]["code"], "001896")
        self.assertEqual(two_layer["front_decision"]["execution_object"]["code"], "001896")
        self.assertEqual(two_layer["front_decision"]["position_pct"], 50)
        self.assertEqual(sniper["canonical_target"]["code"], "001896")
        self.assertIn("最终执行对象: 豫能控股(001896)", "\n".join(sniper["compact_ascii"]))
        self.assertNotEqual(sniper["canonical_target"]["code"], "600688")

    def test_sniper_target_derivation_uses_selection_workflow_candidate_pool(self):
        workflow = {
            "schema_version": "selection_workflow.v1",
            "candidate_pool": [
                {
                    "stock": {"name": "豫能控股", "code": "001896"},
                    "source_pools": ["主线核心"],
                    "entered_reason": "电力窗口方向",
                    "status": "最终执行对象",
                    "current_reason": "对照胜出",
                },
                {
                    "stock": {"name": "上海石化", "code": "600688"},
                    "source_pools": ["涨停池"],
                    "entered_reason": "涨停样本",
                    "status": "降级观察",
                    "eliminated_reason": "不是当前主线核心",
                },
            ],
            "final": {
                "execution_object": {"name": "豫能控股", "code": "001896"},
                "position_pct": 50,
                "action_text": "50%条件执行，不满足回到0%",
            },
        }
        packet = report_runtime._build_sniper_target_derivation_packet(
            data={"target_date": "2026-06-04", "selection_workflow": workflow},
            execution_stage_context={"selection_workflow": workflow},
            market_research_snapshot={},
            final_target_resolution={},
            selected_position_candidate={},
            position_decision={"target_position_pct": 50},
            two_layer_decision_payload={},
        )

        self.assertEqual(packet["canonical_target"]["code"], "001896")
        step_text = "\n".join(step["reason"] for step in packet["steps"])
        self.assertIn("电力窗口方向", step_text)
        self.assertIn("不是当前主线核心", step_text)

    def test_sniper_target_derivation_suppresses_resolution_target_when_workflow_is_zero_position(self):
        workflow = {
            "schema_version": "selection_workflow.v1",
            "candidate_pool": [],
            "nodes": [{"node_id": "N5", "passes_forward": {"candidate_count": 0}}],
            "final": {
                "execution_object": {},
                "position_pct": 0,
                "action_text": "0%不参与",
            },
        }
        target = {"name": "豫能控股", "code": "001896", "sector": "电力"}
        packet = report_runtime._build_sniper_target_derivation_packet(
            data={"target_date": "2026-06-04", "selection_workflow": workflow},
            execution_stage_context={"selection_workflow": workflow},
            market_research_snapshot={},
            final_target_resolution={
                "display_target": target,
                "new_entry_target": target,
                "capital_priority_decision": {"capital_priority": "new_entry"},
            },
            selected_position_candidate=target,
            position_decision={"target_position_pct": 50, "signal_grade": "50"},
            two_layer_decision_payload={},
        )

        self.assertEqual(packet["canonical_target"], {})
        self.assertEqual(packet["canonical_source"], "selection_workflow.final.execution_object")
        self.assertEqual(packet["final_action"]["position_pct"], 0)

    def test_runtime_elimination_tournament_preserves_replay_variant(self):
        workflow = {
            "schema_version": "selection_workflow.v1",
            "target_date": "2026-06-12",
            "candidate_pool": [
                {
                    "stock": {"name": "和远气体", "code": "002971", "sector": "化工原料"},
                    "candidate_origin": "sector_first",
                    "entry_basis": "来自市场氛围、板块发酵和板块角色推导",
                    "sector": "化工原料",
                    "sector_role": "板块锚",
                    "reversal_decision": "可作为主对象",
                }
            ],
            "final": {
                "execution_object": {},
                "position_pct": 0,
                "action_text": "0%不参与",
            },
        }

        payload = report_runtime._build_runtime_elimination_tournament_payload(
            target_date="2026-06-12",
            run_mode="replay",
            data={"selection_workflow": workflow},
            execution_stage_context={"selection_workflow": workflow},
            market_research_snapshot={},
            selection_workflow=workflow,
            final_target_resolution={},
            position_decision={"target_position_pct": 0},
        )

        self.assertEqual(payload["variant"], "replay")

    def test_runtime_elimination_tournament_reads_same_day_trace_and_ledger_artifacts(self):
        workflow = {
            "schema_version": "selection_workflow.v1",
            "target_date": "2026-06-12",
            "candidate_pool": [
                {
                    "stock": {"name": "和远气体", "code": "002971", "sector": "化工原料"},
                    "candidate_origin": "sector_first",
                    "entry_basis": "来自市场氛围、板块发酵和板块角色推导",
                    "sector": "化工原料",
                    "sector_role": "板块锚",
                    "reversal_decision": "可作为主对象",
                    "brooks_price_action_judge": {"status": "passed", "reason": "风险可控"},
                }
            ],
            "final": {
                "execution_object": {},
                "position_pct": 0,
                "action_text": "0%不参与",
            },
        }
        data = {
            "selection_workflow": workflow,
            "candidate_trace_artifact": {
                "payload": {
                    "trade_date": "2026-06-12",
                    "traces": [
                        {
                            "stock_code": "002971",
                            "stock_name": "和远气体",
                            "missing_data": ["account_context"],
                        }
                    ]
                }
            },
            "decision_ledger_artifacts": {
                "index": {
                    "by_stock_code": {
                        "002971": [
                            {
                                "latest_trade_date": "2026-06-12",
                                "stock_code": "002971",
                                "stock_name": "和远气体",
                                "position_plan_pct": 0,
                                "planned_participation": {
                                    "action": "skip",
                                    "position_plan_pct": 0,
                                },
                            }
                        ]
                    }
                }
            },
        }

        payload = report_runtime._build_runtime_elimination_tournament_payload(
            target_date="2026-06-12",
            run_mode="replay",
            data=data,
            execution_stage_context={"selection_workflow": workflow},
            market_research_snapshot={},
            selection_workflow=workflow,
            final_target_resolution={},
            position_decision={"target_position_pct": 0},
        )

        account_layer = next(layer for layer in payload["layers"] if layer["id"] == "account_execution")
        account_entry = account_layer["entries"][0]

        self.assertEqual(account_entry["status"], "eliminated")
        self.assertIn("关键数据不完整：account_context", account_entry["reason"])
        self.assertIn("决策台账仓位=0%", account_entry["reason"])
        self.assertIn("计划动作=skip", account_entry["reason"])
        self.assertNotIn("账户/仓位事实缺失", account_entry["reason"])

    def test_runtime_elimination_tournament_ignores_future_trace_artifact(self):
        workflow = {
            "schema_version": "selection_workflow.v1",
            "target_date": "2026-06-12",
            "candidate_pool": [
                {
                    "stock": {"name": "中船特气", "code": "688146", "sector": "电子化学品"},
                    "candidate_origin": "sector_first",
                    "entry_basis": "来自市场氛围、板块发酵和板块角色推导",
                    "mainline": "电子化学品",
                    "sector": "电子化学品",
                    "sector_role": "板块锚",
                    "reversal_decision": "可作为主对象",
                    "brooks_price_action_judge": {"status": "passed", "reason": "风险可控"},
                }
            ],
            "final": {
                "execution_object": {},
                "position_pct": 0,
                "action_text": "0%不参与",
            },
        }
        data = {
            "selection_workflow": workflow,
            "candidate_trace_artifact": {
                "payload": {
                    "trade_date": "2026-06-13",
                    "traces": [
                        {
                            "stock_code": "688146",
                            "stock_name": "中船特气",
                            "missing_data": ["future_trace_marker"],
                        }
                    ],
                }
            },
        }

        payload = report_runtime._build_runtime_elimination_tournament_payload(
            target_date="2026-06-12",
            run_mode="replay",
            data=data,
            execution_stage_context={"selection_workflow": workflow},
            market_research_snapshot={},
            selection_workflow=workflow,
            final_target_resolution={},
            position_decision={"target_position_pct": 0},
        )

        account_layer = next(layer for layer in payload["layers"] if layer["id"] == "account_execution")
        account_entry = account_layer["entries"][0]

        self.assertEqual(account_entry["status"], "eliminated")
        self.assertIn("账户/仓位事实缺失", account_entry["reason"])
        self.assertNotIn("future_trace_marker", account_entry["reason"])

    def test_runtime_elimination_tournament_ignores_future_ledger_snapshot(self):
        workflow = {
            "schema_version": "selection_workflow.v1",
            "target_date": "2026-06-12",
            "candidate_pool": [
                {
                    "stock": {"name": "中船特气", "code": "688146", "sector": "电子化学品"},
                    "candidate_origin": "sector_first",
                    "entry_basis": "来自市场氛围、板块发酵和板块角色推导",
                    "mainline": "电子化学品",
                    "sector": "电子化学品",
                    "sector_role": "板块锚",
                    "reversal_decision": "可作为主对象",
                    "brooks_price_action_judge": {"status": "passed", "reason": "风险可控"},
                }
            ],
            "final": {
                "execution_object": {},
                "position_pct": 0,
                "action_text": "0%不参与",
            },
        }
        data = {
            "selection_workflow": workflow,
            "decision_ledger_artifacts": {
                "snapshot": {
                    "trade_date": "2026-06-13",
                    "cases": [
                        {
                            "stock_code": "688146",
                            "stock_name": "中船特气",
                            "position_plan_pct": 0,
                            "planned_participation": {
                                "action": "skip",
                                "position_plan_pct": 0,
                            },
                        }
                    ],
                }
            },
        }

        payload = report_runtime._build_runtime_elimination_tournament_payload(
            target_date="2026-06-12",
            run_mode="replay",
            data=data,
            execution_stage_context={"selection_workflow": workflow},
            market_research_snapshot={},
            selection_workflow=workflow,
            final_target_resolution={},
            position_decision={"target_position_pct": 0},
        )

        account_layer = next(layer for layer in payload["layers"] if layer["id"] == "account_execution")
        account_entry = account_layer["entries"][0]

        self.assertEqual(account_entry["status"], "eliminated")
        self.assertIn("账户/仓位事实缺失", account_entry["reason"])
        self.assertNotIn("决策台账仓位=0%", account_entry["reason"])
        self.assertNotIn("计划动作=skip", account_entry["reason"])

    def test_runtime_elimination_tournament_uses_same_day_workflow_trace_without_fake_ledger(self):
        workflow = {
            "schema_version": "selection_workflow.v1",
            "target_date": "2026-06-12",
            "candidate_pool": [
                {
                    "stock": {"name": "中船特气", "code": "688146", "sector": "电子化学品"},
                    "candidate_origin": "sector_first",
                    "entry_basis": "来自市场氛围、板块发酵和板块角色推导",
                    "mainline": "电子化学品",
                    "sector": "电子化学品",
                    "sector_role": "板块锚",
                    "reversal_decision": "可作为主对象",
                    "brooks_price_action_judge": {"status": "passed", "reason": "风险可控"},
                }
            ],
            "final": {
                "execution_object": {},
                "position_pct": 0,
                "action_text": "0%不参与",
            },
        }

        payload = report_runtime._build_runtime_elimination_tournament_payload(
            target_date="2026-06-12",
            run_mode="replay",
            data={"selection_workflow": workflow},
            execution_stage_context={"selection_workflow": workflow},
            market_research_snapshot={},
            selection_workflow=workflow,
            final_target_resolution={},
            position_decision={"target_position_pct": 0},
        )

        account_layer = next(layer for layer in payload["layers"] if layer["id"] == "account_execution")
        account_entry = account_layer["entries"][0]

        self.assertEqual(account_entry["status"], "eliminated")
        self.assertIn("账户/仓位事实缺失", account_entry["reason"])
        self.assertNotIn("决策台账仓位=0%", account_entry["reason"])

    def test_runtime_stores_sector_capital_preflight_payload_on_all_contexts(self):
        workflow = {
            "schema_version": "selection_workflow.v1",
            "target_date": "2026-06-12",
            "candidate_pool": [
                {
                    "stock": {"name": "和远气体", "code": "002971", "sector": "化工原料"},
                    "candidate_origin": "sector_first",
                    "entry_basis": "来自市场氛围、板块发酵和板块角色推导",
                    "sector": "化工原料",
                    "sector_role": "板块锚",
                    "reversal_decision": "可作为主对象",
                    "front_observation_qualified": True,
                    "front_observation_reason": "板块锚可保留为前台观察",
                    "observation_layer": "front_observation",
                }
            ],
            "final": {
                "execution_object": {},
                "position_pct": 0,
                "action_text": "0%不参与",
            },
        }

        elimination = report_runtime._build_runtime_elimination_tournament_payload(
            target_date="2026-06-12",
            run_mode="replay",
            data={"selection_workflow": workflow},
            execution_stage_context={"selection_workflow": workflow},
            market_research_snapshot={},
            selection_workflow=workflow,
            final_target_resolution={},
            position_decision={"target_position_pct": 0},
        )
        data = {
            "target_date": "2026-06-12",
            "selection_workflow": workflow,
            "final_target_resolution": {"capital_priority_decision": {"capital_priority": "wait"}},
            "two_layer_decision_payload": {"schema_version": "two_layer_daily_decision.v1"},
            "sniper_target_derivation": {"schema_version": "sniper_target_derivation.v1"},
            "elimination_tournament_payload": elimination,
        }
        execution_context = {"selection_workflow": workflow}
        market_snapshot = {}
        carrier_strategy = report_runtime._build_runtime_sector_capital_carrier_strategy(
            target_date="2026-06-12",
            data={
                "target_date": "2026-06-12",
                "hot_plates": [{"name": "化工原料", "order": 1}],
                "sector_fund_flow": {"inflow": [{"name": "化工原料", "change_pct": 1.5, "net_inflow_yi": 9.2}]},
                "turnover_rank": [
                    {
                        "code": "002971",
                        "name": "和远气体",
                        "rank": 4,
                        "sector": "化工原料",
                        "turnover": 62.0,
                    }
                ],
                "integrated_hot_list": [
                    {
                        "code": "002971",
                        "name": "和远气体",
                        "rank": 8,
                        "sector": "化工原料",
                    }
                ],
            },
        )
        stored_strategy = report_runtime._store_runtime_sector_capital_carrier_strategy(
            carrier_strategy,
            data=data,
            execution_stage_context=execution_context,
            market_research_snapshot=market_snapshot,
        )

        payload = report_runtime._build_runtime_sector_capital_preflight_payload(
            target_date="2026-06-12",
            run_mode="replay",
            data=data,
            execution_stage_context=execution_context,
            market_research_snapshot=market_snapshot,
            elimination_tournament_payload=elimination,
            sector_capital_carrier_strategy=carrier_strategy,
        )
        stored = report_runtime._store_runtime_sector_capital_preflight_payload(
            payload,
            data=data,
            execution_stage_context=execution_context,
            market_research_snapshot=market_snapshot,
        )

        self.assertEqual(payload["schema_version"], "sector_capital_preflight.v1")
        self.assertEqual(stored["final_action"]["label"], "0%不参与")
        self.assertEqual(stored["final_action"]["position_pct"], 0)
        self.assertIn("flowchart TD", stored["mermaid"])
        self.assertIn("selection_workflow", stored["source_payloads"])
        self.assertEqual(stored["source_payloads"]["selection_workflow"], workflow)
        self.assertEqual(
            stored["source_payloads"]["final_target_resolution"],
            {"capital_priority_decision": {"capital_priority": "wait"}},
        )
        self.assertEqual(
            stored["source_payloads"]["two_layer_decision_payload"]["schema_version"],
            "two_layer_daily_decision.v1",
        )
        self.assertEqual(
            stored["source_payloads"]["sniper_target_derivation"]["schema_version"],
            "sniper_target_derivation.v1",
        )
        self.assertEqual(
            stored["source_payloads"]["elimination_tournament_payload"]["schema_version"],
            "elimination_tournament.v1",
        )
        self.assertEqual(
            stored["source_payloads"]["sector_capital_carrier_strategy"]["schema_version"],
            "sector_capital_carrier_paper_strategy.v1",
        )
        self.assertEqual(
            stored["sector_capital_carrier_strategy"]["primary_candidate"]["stock_label"],
            "和远气体(002971)",
        )
        self.assertEqual(stored_strategy, carrier_strategy)
        self.assertIs(data["sector_capital_carrier_strategy"], stored_strategy)
        self.assertIs(execution_context["sector_capital_carrier_strategy"], stored_strategy)
        self.assertIs(market_snapshot["sector_capital_carrier_strategy"], stored_strategy)
        self.assertIs(data["sector_capital_preflight"], stored)
        self.assertIs(execution_context["sector_capital_preflight"], stored)
        self.assertIs(market_snapshot["sector_capital_preflight"], stored)
        self.assertEqual(stored["trade_date"], "2026-06-12")
        self.assertEqual(stored["layers"][-1]["id"], "final_action")
        self.assertEqual(stored["tplus_rehearsal"]["schema_version"], "t0_tplus_rehearsal.v1")
        self.assertIn("日报生成日是T0", stored["tplus_rehearsal"]["t0_boundary"])
        self.assertIn("不回写T0", stored["tplus_rehearsal"]["review_boundary"])

    def test_sector_capital_preflight_front_summary_renders_tournament_rows(self):
        payload = {
            "schema_version": "sector_capital_preflight.v1",
                "final_action": {
                    "label": "50%条件执行",
                    "position_pct": 50,
                    "target": {"name": "和远气体", "code": "002971", "sector": "化工原料"},
                    "source": "sector_capital_carrier_strategy",
                    "reason": "板块被资金选择，且主样本同时具备至少两类资金载体证据",
                },
            "tplus_rehearsal": {
                "schema_version": "t0_tplus_rehearsal.v1",
                "t0_boundary": "日报生成日是T0；只使用T0已知事实推演T+1和T+2",
                "review_boundary": "T+1/T+2后验事实只用于复盘批改，不回写T0候选生成或最终动作",
                "tplus1": {
                    "participation_qualification": "有条件参与",
                    "market_emotion": "主线延续观察",
                    "market_cycle": "周期窗口打开",
                    "sector_emotion": "板块延续",
                    "sector_cycle": "主升或二波确认",
                    "buy_windows": ["09:50-10:10优先等回踩MA5/VWAP/0轴后重新站回"],
                    "action": "围绕和远气体(002971)执行，不追无回踩的加速",
                },
                "tplus2": {
                    "market_emotion": "延续后分歧或震荡",
                    "market_cycle": "周期仍在，但进入兑现复核",
                    "sector_emotion": "延续后分歧",
                    "sector_cycle": "强者横住续命，后排先兑现",
                    "sell_windows": ["09:50-10:10看承接是否把分歧修复为延续"],
                    "action": "先按预案处理，再由后验复盘批改",
                },
            },
            "layers": [
                {
                    "id": "market_capital_structure",
                    "title": "市场资金结构",
                    "input_count": 3,
                    "eliminated_count": 1,
                    "survivor_count": 2,
                    "eliminated": [
                        {
                            "stock_label": "旧记忆股(000001)",
                            "elimination_basis": "旧龙头记忆只能作为过程证据",
                        }
                    ],
                    "survivors": [
                        {"stock_label": "和远气体(002971)", "next_basis": "进入板块资金扩散层"},
                        {"stock_label": "云南锗业(002428)", "next_basis": "进入板块资金扩散层"},
                    ],
                },
                {
                    "id": "price_action",
                    "title": "价格行为确认",
                    "input_count": 1,
                    "eliminated_count": 1,
                    "survivor_count": 0,
                    "eliminated": [
                        {
                            "stock_label": "和远气体(002971)",
                            "risk_evidence": "炸板57次且尾盘才回封；高换手连板",
                            "elimination_basis": "炸板57次且尾盘才回封；高换手连板",
                        }
                    ],
                    "survivors": [],
                },
                {
                    "id": "final_action",
                    "title": "唯一明日动作",
                    "input_count": 1,
                    "eliminated_count": 0,
                    "survivor_count": 0,
                    "entries": [{"stock_label": "无执行对象", "status": "final_action"}],
                },
            ],
            "sector_capital_carrier_strategy": {
                "schema_version": "sector_capital_carrier_paper_strategy.v1",
                "action": "paper_participate",
                "action_label": "板块资金载体主样本",
                "action_reason": "板块被资金选择，且主样本同时具备至少两类资金载体证据",
                "primary_candidate": {
                    "stock_label": "和远气体(002971)",
                    "reason": "化工原料进入板块候选；个股证据：热榜关注、容量成交；角色：趋势容量核心、板块锚/资金表领涨",
                },
                "stages": [
                    {
                        "title": "板块线索恢复",
                        "input_count": 1,
                        "eliminated_count": 0,
                        "survivor_count": 1,
                        "survivors": [{"label": "化工原料", "reason": "资金流入与板块涨幅同向"}],
                        "eliminated": [],
                    }
                ],
            },
        }

        rendered = "\n".join(report_runtime._render_sector_capital_preflight_front_summary(payload))

        self.assertIn("## 板块资金扩散淘汰赛", rendered)
        self.assertIn("| 市场资金结构 | 3 | 1 | 2（和远气体(002971)、云南锗业(002428)） | 旧记忆股(000001): 旧龙头记忆只能作为过程证据 | 进入板块资金扩散层 |", rendered)
        self.assertIn("| 价格行为确认 | 1 | 1 | 0（无） | 和远气体(002971): 炸板57次且尾盘才回封；高换手连板 | 进入下一层复核 |", rendered)
        self.assertIn("**最终动作**：50%条件执行；来源=sector_capital_carrier_strategy", rendered)
        self.assertIn("不单独生成明日标的", rendered)
        self.assertIn("## 板块资金载体预案", rendered)
        self.assertIn("| T0同源策略动作 | 板块资金载体主样本 |", rendered)
        self.assertIn("已进入最终动作；按唯一明日动作执行", rendered)
        self.assertIn("| 板块线索恢复 | 1 | 0 | 1 | 化工原料：资金流入与板块涨幅同向 |", rendered)
        self.assertIn("## T0推演T+1/T+2交易环境", rendered)
        self.assertIn("| T+1参与日 | 主线延续观察 | 周期窗口打开 | 板块延续 | 主升或二波确认 | 有条件参与；围绕和远气体(002971)执行，不追无回踩的加速 |", rendered)
        self.assertIn("T+1/T+2后验事实只用于复盘批改，不回写T0候选生成或最终动作", rendered)

    def test_runtime_derivation_chain_keeps_stale_local_candidate_as_process_only(self):
        def _run_execution_stages(stage_specs, stage_context=None, stage_lookup=None):
            return {
                "lines": [],
                "module_logs": [],
                "context": {
                    "market_state_snapshot": {"market_state": "混沌"},
                    "mainline_turnover_summary": {"current_mainline": "电力"},
                    "best_stock": {"name": "上海石化", "code": "600688", "sector": "炼化及贸"},
                    "watch_anchor": {"name": "上海石化", "code": "600688", "sector": "炼化及贸"},
                    "selected_position_candidate": {
                        "name": "豫能控股",
                        "code": "001896",
                        "sector": "电力",
                        "candidate_role": "观察对象",
                    },
                    "executable_stocks": [{"name": "豫能控股", "code": "001896", "sector": "电力"}],
                    "position_decision": {"target_position_pct": 0, "signal_grade": "0"},
                },
            }

        helpers = _build_runtime_execution_test_helpers(
            _run_execution_stages,
            persist_decision_ledger=False,
            decision_ledger_root_dir="/tmp/decision-ledger-root",
            read_decision_ledger_index=lambda path: {"available_trade_dates": [], "by_stock_code": {}},
            build_report_shell_contract=lambda *args, **kwargs: {
                "report": [
                    "## 八、详细附录",
                    "**观察优先" + "锚点**: 上海石化(600688)",
                    "**先看顺序**（优先盯最能反映主线承接的对象）:",
                    "- 👀 上海石化(600688) - 旧过程观察",
                ]
            },
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
            render_front_page_v2=lambda report, **kwargs: ["# front", "", "## 明日账户建议", "| 项目 | 结论 |"],
            DISPLAY_MVP_MODE=False,
        )

        result = report_runtime.render_markdown_report_runtime(
            {"exchange_monitor_today": [], "exchange_monitor_nextday": []},
            "2026-06-04",
            helpers=helpers,
            config={},
        )
        report = result["report"]
        front_text, appendix_text = report.split("## 八、详细附录", 1)

        self.assertIn("| 明日执行对象 | 无 |", front_text)
        self.assertIn("| 最终对象 | 无 |", front_text)
        self.assertNotIn("| 最终对象 | 观察对象：豫能控股(001896) |", front_text)
        self.assertNotIn("仓位不允许50%执行，豫能控股(001896)只保留为观察对象", front_text)
        self.assertNotIn("没有可用明日执行对象，也没有观察对象", front_text)
        self.assertNotIn("`-- 最终观察对象: 豫能控股(001896), 0%只观察", front_text)
        self.assertNotIn("上海石化(600688): 过程候选 / 被替换", front_text)
        self.assertNotIn(
            "| 豫能控股(001896) | 观察对象 | - | - | - | - | - | - | 待计算 | 只保留观察，等风险价格补齐 |",
            front_text,
        )
        self.assertNotIn("## 狙击手最终标的完整路径图（过程证据）", appendix_text)
        self.assertNotIn("来源=执行链最佳候选 候选=上海石化(600688) 身份=过程候选 去向=被替换", appendix_text)
        self.assertNotIn("最终对象=豫能控股(001896) 身份=观察对象", appendix_text)
        self.assertNotIn("阶段一：原始候选", appendix_text)
        self.assertNotIn("阶段二：当前核心解析", appendix_text)
        self.assertNotIn("阶段三：仓位/账户修正", appendix_text)
        self.assertNotIn("阶段四：最终对象解析", appendix_text)
        self.assertNotIn("T0 原始候选", appendix_text)
        self.assertNotIn("T1 当前核心解析", appendix_text)
        self.assertNotIn("T2 仓位/账户修正", appendix_text)
        self.assertNotIn("T3 最终对象解析", appendix_text)
        self.assertNotIn("最终观察" + "锚: 上海石化", report)
        self.assertNotIn("观察" + "锚", report)
        self.assertNotIn("豫能控股(001896) | 观察" + "锚", report)
        self.assertNotIn("| 明日执行对象 | 豫能控股(001896) |", report)

    def test_runtime_builds_final_target_resolution_for_new_entry_after_old_position_exit(self):
        captured = {}

        def _run_execution_stages(stage_specs, stage_context=None, stage_lookup=None):
            return {
                "lines": [],
                "module_logs": [],
                "context": {
                    "market_state_snapshot": {"market_state": "混沌"},
                    "mainline_turnover_summary": {"current_mainline": "通信设备"},
                    "selected_position_candidate": {
                        "name": "工业富联",
                        "code": "601138",
                        "sector": "通信设备",
                        "sniper_role": "明日主买对象",
                        "anchor_reversal_decision": "可作为主对象",
                        "primary_buy_candidate": True,
                        "sector_anchor": "工业富联(601138)",
                        "candidate_role": "板块锚",
                        "target_role": "core",
                        "strength_evidence": ["通信设备资金回流", "板块锚", "趋势核心"],
                        "relationship_to_anchor": "资金回流优先看板块锚",
                        "leader_certainty_path": "板块锚优先，慢即是快",
                        "probe_entry_price": 10.0,
                        "ma5": 9.9,
                        "ma10": 9.8,
                        "vwap": 9.95,
                        "stop_price": 9.6,
                        "target_price": 11.0,
                        "planned_participation": {
                            "buy_window": "09:50-10:10",
                            "fallback_state": "不满足继续观察",
                        },
                    },
                    "extreme_conviction_list": [
                        {
                            "name": "工业富联",
                            "code": "601138",
                            "sector": "通信设备",
                            "sniper_role": "明日主买对象",
                            "anchor_reversal_decision": "可作为主对象",
                            "primary_buy_candidate": True,
                            "sector_anchor": "工业富联(601138)",
                            "candidate_role": "板块锚",
                            "target_role": "core",
                            "planned_participation": {
                                "buy_window": "09:50-10:10",
                                "fallback_state": "不满足继续观察",
                            },
                        }
                    ],
                    "position_decision": {"target_position_pct": 50, "signal_grade": "50"},
                },
            }

        def _fake_front_page(report, **kwargs):
            captured["snapshot"] = kwargs["market_research_snapshot"]
            return [
                "# front",
                "",
                "## 明日账户建议",
                "| 明日动作 | 先处理旧仓，买工业富联(601138)；固定交易窗口条件成立才参与，不满足回到0% |",
                "| 新开仓上限 | 资金释放后1 |",
            ]

        helpers = _build_runtime_execution_test_helpers(
            _run_execution_stages,
            persist_decision_ledger=False,
            decision_ledger_root_dir="/tmp/decision-ledger-root",
            read_decision_ledger_index=lambda path: {"available_trade_dates": [], "by_stock_code": {}},
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
            render_front_page_v2=_fake_front_page,
        )

        result = report_runtime.render_markdown_report_runtime(
            {
                "exchange_monitor_today": [],
                "exchange_monitor_nextday": [],
                "personal_position_context": {
                    "account_profile": {"capital_text": "约1w账户"},
                    "existing_position_summary": {
                        "has_position": True,
                        "summary": "华电辽能(600396)：已有仓先按MA5T处理",
                    },
                },
            },
            "2026-06-03",
            helpers=helpers,
            config={},
        )

        resolution = captured["snapshot"]["final_target_resolution"]
        self.assertEqual(resolution["capital_priority_decision"]["capital_priority"], "new_entry_after_old_exit")
        self.assertEqual(resolution["new_entry_target"]["code"], "601138")
        self.assertEqual(resolution["watch_target"], {})
        self.assertEqual(resolution["existing_position_target"]["name"], "华电辽能")
        self.assertEqual(resolution["display_target"]["code"], "601138")
        self.assertIn("| 最终结果 | 工业富联(601138) |", result["report"])
        self.assertIn("| 明日动作 | 先处理旧仓，买工业富联(601138)；固定交易窗口条件成立才参与，不满足回到0% |", result["report"])
        self.assertIn("+-- 小账户资金取舍: new_entry_after_old_exit", result["report"])
        self.assertIn("+-- 旧仓处理: 华电辽能(600396)", result["report"])
        self.assertIn("+-- 最终结果: 工业富联(601138)", result["report"])

    def test_runtime_stores_sniper_target_derivation_packet_and_renders_compact_chain(self):
        data = {"target_date": "2026-06-04"}
        execution_context = {
            "best_stock": {"name": "上海石化", "code": "600688", "sector": "炼化及贸"},
            "watch_anchor": {"name": "上海石化", "code": "600688", "sector": "炼化及贸"},
        }
        market_snapshot = {
            "selected_position_candidate": {"name": "豫能控股", "code": "001896", "sector": "电力"}
        }
        resolution = {
            "watch_target": {"name": "豫能控股", "code": "001896", "sector": "电力"},
            "new_entry_target": {"name": "豫能控股", "code": "001896", "sector": "电力"},
            "display_target": {"name": "华电辽能", "code": "600396", "sector": "电力"},
            "capital_priority_decision": {
                "capital_priority": "old_position_t",
                "reason": "先处理旧仓，豫能控股只保留观察对象",
            },
        }

        packet = report_runtime._build_sniper_target_derivation_packet(
            data=data,
            execution_stage_context=execution_context,
            market_research_snapshot=market_snapshot,
            final_target_resolution=resolution,
            position_decision={"target_position_pct": 0, "signal_grade": "0"},
            final_gate={"final_action": "只观察，不新增参与"},
        )
        report_runtime._store_runtime_sniper_target_derivation(
            packet,
            data=data,
            execution_stage_context=execution_context,
            market_research_snapshot=market_snapshot,
        )
        compact = "\n".join(report_runtime._render_sniper_target_derivation_compact(packet))

        self.assertEqual(packet["schema_version"], "sniper_target_derivation.v1")
        self.assertEqual(packet["canonical_target"]["code"], "001896")
        self.assertEqual(data["sniper_target_derivation"]["canonical_target"]["name"], "豫能控股")
        self.assertEqual(execution_context["sniper_target_derivation"]["canonical_target"]["code"], "001896")
        self.assertEqual(market_snapshot["sniper_target_derivation"]["canonical_target"]["code"], "001896")
        self.assertIn("最终观察对象: 豫能控股(001896)", compact)
        self.assertIn("上海石化(600688): 过程候选 / 被替换", compact)
        self.assertNotIn("最终观察对象: 上海石化", compact)

    def test_sniper_derivation_uses_proxy_as_canonical_when_display_target_is_proxy(self):
        resolution = {
            "watch_target": {"name": "中际旭创", "code": "300308", "sector": "通信设备"},
            "new_entry_target": {"name": "中际旭创", "code": "300308", "sector": "通信设备"},
            "tradable_proxy_target": {"name": "通信ETF", "code": "515880", "sector": "通信设备"},
            "display_target": {"name": "通信ETF", "code": "515880", "sector": "通信设备"},
            "capital_priority_decision": {
                "capital_priority": "new_entry_after_old_exit",
                "reason": "先处理旧仓，目标标的中际旭创(300308)，小资金账户可用通信ETF(515880)替代",
            },
        }

        packet = report_runtime._build_sniper_target_derivation_packet(
            data={"target_date": "2026-06-03"},
            execution_stage_context={"best_stock": {"name": "中际旭创", "code": "300308", "sector": "通信设备"}},
            market_research_snapshot={},
            final_target_resolution=resolution,
            selected_position_candidate={"name": "中际旭创", "code": "300308", "sector": "通信设备"},
            position_decision={"target_position_pct": 50, "signal_grade": "50"},
            final_gate={"final_action": "先处理旧仓，买通信ETF(515880)"},
        )
        compact = "\n".join(report_runtime._render_sniper_target_derivation_compact(packet))
        full = "\n".join(packet["full_ascii"])

        self.assertEqual(packet["canonical_target"]["code"], "515880")
        self.assertIn("最终执行对象: 通信ETF(515880)", compact)
        self.assertIn("阶段四：最终对象解析", full)
        self.assertIn("最终对象=通信ETF(515880) 身份=执行对象", full)
        self.assertNotIn("T3 最终对象解析", full)
        self.assertNotIn("最终观察" + "锚: 中际旭创", compact)

    def test_runtime_keeps_new_target_observational_when_risk_price_is_missing(self):
        selected = {
            "name": "华天科技",
            "code": "002185",
            "sector": "半导体",
            "target_role": "sector_anchor",
            "candidate_role": "板块锚",
            "strength_evidence": ["半导体资金回流", "板块锚"],
            "participation_window": "竞价表态 + 回封参与",
            "buy_window": "09:30-09:35",
            "fallback_state": "不满足回到0%",
        }
        data = {
            "personal_position_context": {
                "account_profile": {"capital_text": "约1w账户"},
                "existing_position_summary": {
                    "has_position": True,
                    "summary": "持有华电辽能(600396)，200股，T+1仓，今日做T买入2手、卖出2手；先处理旧仓",
                },
            }
        }

        position_decision = report_runtime._build_front_page_position_decision(
            position_decision={"target_position_pct": 100, "signal_grade": "100"},
            selected_position_candidate=selected,
            data=data,
            market_research_snapshot={},
        )
        resolution = report_runtime._build_runtime_final_target_resolution(
            data=data,
            selected_position_candidate=selected,
            position_decision=position_decision,
            market_research_snapshot={},
        )

        self.assertEqual(position_decision["target_position_pct"], 0)
        self.assertEqual(position_decision["signal_grade"], "0")
        self.assertIn("风险价格", position_decision["sizing_reason"])
        self.assertEqual(resolution["capital_priority_decision"]["capital_priority"], "old_position_t")
        self.assertEqual(resolution["display_target"]["code"], "600396")
        self.assertEqual(resolution["watch_target"]["code"], "002185")
        self.assertEqual(resolution["opportunity_comparison"]["new_target"]["risk_reward_state"], "待计算")

    def test_runtime_keeps_new_target_observational_when_risk_price_is_missing_without_old_position(self):
        selected = {
            "name": "和远气体",
            "code": "002971",
            "sector": "化学制品",
            "target_role": "sector_anchor",
            "candidate_role": "板块锚",
            "target_position_pct": 50,
            "participation_window": "09:50-10:10",
            "fallback_state": "不满足回到0%",
            "strength_evidence": ["放量修复", "板块内强度靠前"],
        }

        position_decision = report_runtime._build_front_page_position_decision(
            position_decision={"target_position_pct": 0, "signal_grade": "0"},
            selected_position_candidate=selected,
            data={},
            market_research_snapshot={},
        )
        resolution = report_runtime._build_runtime_final_target_resolution(
            data={},
            selected_position_candidate=selected,
            position_decision=position_decision,
            market_research_snapshot={},
        )

        self.assertEqual(position_decision["target_position_pct"], 0)
        self.assertEqual(position_decision["signal_grade"], "0")
        self.assertIn("风险价格", position_decision["sizing_reason"])
        self.assertEqual(position_decision["opportunity_comparison"]["comparison"]["max_participation_pct"], 0)
        self.assertEqual(resolution["capital_priority_decision"]["capital_priority"], "wait")
        self.assertEqual(resolution["watch_target"]["code"], "002971")
        self.assertEqual(resolution["opportunity_comparison"]["new_target"]["risk_reward_state"], "待计算")

    def test_sector_capital_carrier_with_old_position_blocks_when_risk_price_is_missing(self):
        selected = {
            "name": "长电科技",
            "code": "600584",
            "sector": "半导体",
            "candidate_origin": "sector_capital_carrier_v1",
            "conditional_execution_source": "sector_capital_carrier_strategy",
            "target_position_pct": 50,
            "target_role": "sector_anchor",
            "strength_evidence": ["板块资金扩散", "容量核心"],
            "close": 91.33,
            "high": 91.33,
        }
        data = {
            "personal_position_context": {
                "account_profile": {"capital_text": "约1w账户"},
                "existing_position_summary": {
                    "has_position": True,
                    "summary": "持有太极实业(600667)，100%仓位；先处理旧仓；新开仓0手",
                },
            }
        }

        position_decision = report_runtime._build_front_page_position_decision(
            position_decision={"target_position_pct": 50, "signal_grade": "50"},
            selected_position_candidate=selected,
            data=data,
            market_research_snapshot={},
        )
        resolution = report_runtime._build_runtime_final_target_resolution(
            data=data,
            selected_position_candidate=selected,
            position_decision=position_decision,
            market_research_snapshot={},
        )

        self.assertEqual(position_decision["target_position_pct"], 0)
        self.assertEqual(position_decision["signal_grade"], "0")
        self.assertIn("风险价格", position_decision["sizing_reason"])
        self.assertEqual(resolution["capital_priority_decision"]["capital_priority"], "old_position_t")
        self.assertEqual(resolution["watch_target"]["code"], "600584")
        self.assertEqual(resolution["opportunity_comparison"]["comparison"]["max_participation_pct"], 0)

    def test_front_page_final_gate_keeps_observation_when_opportunity_risk_blocks_target(self):
        gate = report_runtime._build_effective_front_page_final_gate(
            {"final_action": "只保留观察，等风险价格补齐"},
            selected_position_candidate={"name": "兆易创新", "code": "603986"},
            position_decision={"target_position_pct": 100, "signal_grade": "100"},
            opportunity_comparison={
                "comparison": {
                    "max_participation_pct": 0,
                    "final_action": "只保留观察，等风险价格补齐",
                }
            },
        )

        self.assertEqual(gate["final_action"], "只保留观察，等风险价格补齐")
        self.assertFalse(gate["allow_attack_50_ready"])
        self.assertNotIn("100%核心进攻", gate["final_action"])
        self.assertNotIn("50%条件执行", gate["final_action"])


    def test_runtime_final_target_solution_renders_opportunity_cost_table(self):
        selected = {
            "name": "华天科技",
            "code": "002185",
            "sector": "半导体",
            "candidate_role": "板块锚",
        }
        lines = report_runtime._runtime_selected_target_solution_lines(
            selected,
            final_gate={"final_action": "只保留观察，等风险价格补齐"},
            mainline_turnover_summary={"current_mainline": "半导体"},
            final_target_resolution={
                "display_target": {"name": "华电辽能", "code": "600396"},
                "watch_target": selected,
                "existing_position_target": {"name": "华电辽能", "code": "600396"},
                "capital_priority_decision": {"capital_priority": "old_position_t"},
                "opportunity_comparison": {
                    "old_position": {
                        "name": "华电辽能",
                        "code": "600396",
                        "holding_role": "old_position",
                        "old_plan_action": "repair_once",
                    },
                    "new_target": {
                        "name": "华天科技",
                        "code": "002185",
                        "target_role": "sector_anchor",
                        "observation_price": 19.16,
                        "ma5": 18.2,
                        "ma10": 17.8,
                        "vwap": None,
                        "invalid_price": None,
                        "target_price": None,
                        "downside_to_ma5_pct": 5.01,
                        "downside_to_ma10_pct": 6.99,
                        "risk_reward_state": "待计算",
                    },
                    "comparison": {
                        "capital_efficiency_result": "observe",
                        "max_participation_pct": 0,
                        "final_action": "只保留观察，等风险价格补齐",
                    },
                },
            },
        )
        rendered = "\n".join(lines)

        self.assertIn("## 旧仓与新机会风险价格对比", rendered)
        self.assertIn("| 华电辽能(600396) | old_position |", rendered)
        self.assertIn("| 华天科技(002185) | sector_anchor | 19.16 | 18.20 / -5.01% | 17.80 / -6.99% | - | - | - | 待计算 | 只保留观察，等风险价格补齐 |", rendered)

    def test_runtime_final_target_solution_wait_priority_keeps_observation_target_visible(self):
        selected = {"name": "豫能控股", "code": "001896", "sector": "电力"}
        lines = report_runtime._runtime_selected_target_solution_lines(
            selected,
            final_gate={"final_action": "0%不参与；只保留观察"},
            mainline_turnover_summary={"current_mainline": "电力"},
            final_target_resolution={
                "watch_target": selected,
                "process_target": selected,
                "capital_priority_decision": {
                    "capital_priority": "wait",
                    "reason": "空仓等待，条件未出现前不参与",
                },
            },
            market_research_snapshot={
                "two_layer_decision_payload": {
                    "front_decision": {
                        "execution_object": {},
                        "execution_identity": "无明日执行对象",
                        "position_plan": "0%不参与",
                    },
                    "b_level_conditions": {},
                }
            },
        )
        rendered = "\n".join(lines)

        self.assertEqual("", rendered)

    def test_runtime_final_target_solution_wait_priority_ignores_stale_execution_object(self):
        selected = {"name": "豫能控股", "code": "001896", "sector": "电力"}
        lines = report_runtime._runtime_selected_target_solution_lines(
            selected,
            final_gate={"final_action": "0%不参与；只保留观察"},
            mainline_turnover_summary={"current_mainline": "电力"},
            final_target_resolution={
                "watch_target": selected,
                "process_target": selected,
                "capital_priority_decision": {
                    "capital_priority": "wait",
                    "reason": "空仓等待，条件未出现前不参与",
                },
            },
            market_research_snapshot={
                "two_layer_decision_payload": {
                    "front_decision": {
                        "execution_object": {"name": "上海石化", "code": "600688", "sector": "炼化及贸"},
                        "execution_identity": "明日执行对象",
                        "position_plan": "50%条件执行",
                    },
                    "b_level_conditions": {"active_attack": {"trigger": "主动进攻型"}},
                }
            },
        )
        rendered = "\n".join(lines)

        self.assertEqual("", rendered)
        self.assertNotIn("| 最终结果 | 上海石化(600688) |", rendered)
        self.assertNotIn("条件满足才50%条件执行", rendered)

    def test_runtime_final_target_solution_wait_priority_without_watch_target_stays_empty(self):
        selected = {
            "name": "大有能源",
            "code": "600403",
            "sector": "煤炭开采",
            "anchor_reversal_decision": "降级观察",
            "candidate_role": "观察样本",
        }
        lines = report_runtime._runtime_selected_target_solution_lines(
            selected,
            final_gate={"final_action": "空仓等待，禁止参与；若你有仓位，只做退出不做幻想"},
            mainline_turnover_summary={"current_mainline": "半导体"},
            final_target_resolution={
                "watch_target": {},
                "process_target": selected,
                "ascii_trace_target": selected,
                "capital_priority_decision": {
                    "capital_priority": "wait",
                    "reason": "无明日执行对象，保持观察",
                },
            },
        )

        self.assertEqual([], lines)

    def test_runtime_final_target_solution_rejects_process_watch_target_under_old_position_priority(self):
        process_watch = {
            "name": "和远气体",
            "code": "002971",
            "front_observation_qualified": True,
            "observation_layer": "process_observation",
            "identity": "过程候选",
        }

        lines = report_runtime._runtime_selected_target_solution_lines(
            process_watch,
            final_gate={"final_action": "只处理旧仓，不新增参与"},
            mainline_turnover_summary={"current_mainline": "化学制品"},
            final_target_resolution={
                "watch_target": process_watch,
                "display_target": {"name": "华电辽能", "code": "600396"},
                "capital_priority_decision": {"capital_priority": "old_position_t"},
            },
        )

        self.assertEqual([], lines)

    def test_runtime_final_target_solution_keeps_final_execution_object_even_when_front_observation_is_false(self):
        execution_object = {
            "name": "豫能控股",
            "code": "001896",
            "sector": "电力",
            "status": "过程候选",
            "observation_layer": "process_observation",
            "front_observation_qualified": False,
            "candidate_role": "观察样本",
            "anchor_reversal_decision": "可作为主对象",
            "planned_participation": {
                "buy_window": "09:50-10:10",
                "fallback_state": "条件不满足回到0%",
            },
        }

        lines = report_runtime._runtime_selected_target_solution_lines(
            execution_object,
            final_gate={"final_action": "条件满足才50%条件执行；不满足回到0%"},
            mainline_turnover_summary={"current_mainline": "电力"},
            final_target_resolution={
                "new_entry_target": execution_object,
                "display_target": execution_object,
                "capital_priority_decision": {"capital_priority": "new_entry_after_old_exit"},
            },
        )

        rendered = "\n".join(lines)

        self.assertIn("| 最终结果 | 豫能控股(001896) |", rendered)
        self.assertIn("| 明日动作 | 条件满足才50%条件执行；不满足回到0% |", rendered)
        self.assertNotIn("过程候选", rendered)
        self.assertNotIn("观察样本", rendered)

    def test_sniper_target_derivation_wait_priority_without_watch_target_has_no_canonical_target(self):
        selected = {
            "name": "大有能源",
            "code": "600403",
            "sector": "煤炭开采",
            "anchor_reversal_decision": "降级观察",
            "candidate_role": "观察样本",
        }
        packet = report_runtime._build_sniper_target_derivation_packet(
            data={},
            execution_stage_context={"selected_position_candidate": selected},
            market_research_snapshot={},
            final_target_resolution={
                "watch_target": {},
                "capital_priority_decision": {
                    "capital_priority": "wait",
                    "reason": "无明日执行对象，保持观察",
                },
            },
            selected_position_candidate={},
            position_decision={"signal_grade": "0", "target_position_pct": 0},
        )

        self.assertEqual({}, packet["canonical_target"])
        self.assertEqual([], report_runtime._render_sniper_target_derivation_compact(packet))

    def test_sniper_target_derivation_rejects_process_resolution_target_without_workflow(self):
        process_target = {
            "name": "和远气体",
            "code": "002971",
            "front_observation_qualified": True,
            "observation_layer": "process_observation",
            "identity": "过程候选",
        }

        for priority in ("old_position_t", "new_entry", "tradable_proxy"):
            with self.subTest(priority=priority):
                packet = report_runtime._build_sniper_target_derivation_packet(
                    data={},
                    execution_stage_context={"selected_position_candidate": process_target},
                    market_research_snapshot={},
                    final_target_resolution={
                        "watch_target": process_target,
                        "new_entry_target": process_target,
                        "display_target": process_target,
                        "tradable_proxy_target": process_target if priority == "tradable_proxy" else {},
                        "capital_priority_decision": {"capital_priority": priority},
                    },
                    selected_position_candidate=process_target,
                    position_decision={"signal_grade": "50", "target_position_pct": 50},
                    final_gate={"final_action": "固定交易窗口条件成立才参与，不满足回到0%"},
                )

                self.assertEqual({}, packet["canonical_target"])
                self.assertEqual([], report_runtime._render_sniper_target_derivation_compact(packet))

    def test_runtime_wait_resolution_treats_process_watch_target_as_empty(self):
        process_watch = {
            "name": "和远气体",
            "code": "002971",
            "front_observation_qualified": True,
            "observation_layer": "process_observation",
            "identity": "过程候选",
        }
        resolution = {
            "watch_target": process_watch,
            "capital_priority_decision": {"capital_priority": "wait"},
        }

        identity = report_runtime._runtime_final_resolution_identity(resolution)

        self.assertTrue(report_runtime._runtime_final_resolution_waits_without_watch_target(resolution))
        self.assertEqual(identity["source"], "none")
        self.assertEqual(identity["key"], "")
        self.assertEqual(report_runtime._runtime_observation_anchor_label(resolution), "")

    def test_runtime_recovers_huadian_old_position_from_damaged_t_summary(self):
        old_position = report_runtime._runtime_old_position_for_opportunity(
            data={
                "target_date": "2026-06-03",
                "stock_full_info": {"600396": {"name": "华电辽能"}},
                "personal_position_context": {
                    "existing_position_summary": {
                        "has_position": True,
                        "summary": "持有T，200股；先处理旧仓；新开仓0手",
                    }
                },
            },
            market_research_snapshot={},
        )

        self.assertEqual(old_position["name"], "华电辽能")
        self.assertEqual(old_position["code"], "600396")
        self.assertEqual(old_position["summary"], "持有T，200股；先处理旧仓；新开仓0手")

    def test_runtime_opportunity_table_keeps_huatian_calibration_candidate(self):
        selected = {
            "name": "长电科技",
            "code": "600584",
            "sector": "半导体",
            "target_role": "sector_anchor",
            "close": 80.13,
            "stop_price": 76.12,
            "risk_reward_state": "待计算",
        }
        comparison = report_runtime._runtime_opportunity_comparison(
            data={
                "target_date": "2026-06-03",
                "stock_full_info": {
                    "600396": {"name": "华电辽能"},
                    "002185": {
                        "name": "华天科技",
                        "industry": "半导体",
                        "close": 19.16,
                    },
                },
                "candidates": [
                    {
                        "name": "华天科技",
                        "code": "002185",
                        "sector": "未归类",
                        "_source": "热榜",
                    }
                ],
                "personal_position_context": {
                    "existing_position_summary": {
                        "has_position": True,
                        "summary": "持有T，200股；先处理旧仓；新开仓0手",
                    }
                },
            },
            selected_position_candidate=selected,
            position_decision={"target_position_pct": 0, "signal_grade": "0"},
            market_research_snapshot={},
        )
        rendered = "\n".join(report_runtime._runtime_opportunity_comparison_lines(comparison))

        self.assertEqual(comparison["old_position"]["name"], "华电辽能")
        self.assertIn("additional_target_comparisons", comparison)
        self.assertIn("| 华电辽能(600396) | old_position |", rendered)
        self.assertIn("| 长电科技(600584) | sector_anchor | 80.13 |", rendered)
        self.assertIn("| 华天科技(002185) | same_line_candidate | 19.16 |", rendered)

    def test_runtime_keeps_new_candidate_observational_when_existing_position_wins(self):
        resolution = report_runtime._build_runtime_final_target_resolution(
            data={
                "personal_position_context": {
                    "existing_position_summary": {
                        "has_position": True,
                        "summary": "华电辽能(600396)：已有仓先按MA5T处理",
                    }
                }
            },
            selected_position_candidate={
                "name": "工业富联",
                "code": "601138",
                "sector": "通信设备",
            },
            position_decision={"target_position_pct": 0, "signal_grade": "0"},
            market_research_snapshot={},
        )

        self.assertEqual(resolution["capital_priority_decision"]["capital_priority"], "old_position_t")
        self.assertEqual(resolution["display_target"]["name"], "华电辽能")
        self.assertEqual(resolution["watch_target"]["code"], "601138")

    def test_runtime_keeps_independent_etf_holding_from_forcing_old_position_exit(self):
        resolution = report_runtime._build_runtime_final_target_resolution(
            data={
                "personal_position_context": {
                    "existing_position_summary": {
                        "has_position": True,
                        "summary": "持有芯片ETF(159995)，33%仓位；持仓继续独立评估，不因新机会自动处理",
                    }
                }
            },
            selected_position_candidate={
                "name": "太极实业",
                "code": "600667",
                "sector": "半导体",
                "candidate_origin": "sector_capital_carrier_v1",
                "conditional_execution_source": "sector_capital_carrier_strategy",
                "target_position_pct": 50,
            },
            position_decision={"target_position_pct": 50, "signal_grade": "50"},
            market_research_snapshot={},
        )

        self.assertEqual(resolution["capital_priority_decision"]["capital_priority"], "new_entry")
        self.assertEqual(resolution["new_entry_target"]["code"], "600667")
        self.assertEqual(resolution["existing_position_target"]["code"], "159995")
        self.assertNotIn("先处理旧仓", resolution["capital_priority_decision"]["reason"])

    def test_runtime_builds_final_target_resolution_for_unbuyable_core_proxy(self):
        selected = {
            "name": "中际旭创",
            "code": "300308",
            "sector": "通信设备",
            "identity": "市场核心",
            "one_lot_amount": 16800,
            "sniper_role": "明日主买对象",
            "anchor_reversal_decision": "可作为主对象",
            "primary_buy_candidate": True,
            "sector_anchor": "中际旭创(300308)",
            "candidate_role": "板块锚",
            "relationship_to_anchor": "通信设备回流优先看板块锚",
            "leader_certainty_path": "大容量核心优先，慢即是快",
            "planned_participation": {
                "buy_window": "09:50-10:10",
                "fallback_state": "不满足回到0%",
            },
            "tradable_proxy_target": {
                "name": "通信ETF",
                "code": "515880",
                "sector": "通信设备",
                "proxy_effect_type": "行业板块效应",
                "proxy_reason": "跟踪通信设备方向，不退到弱跟风个股",
                "condition": "通信设备承接继续",
                "participation_window": "09:50-10:10",
                "fallback_state": "不满足回到0%",
                "execution_eligible": True,
                "target_position_pct": 50,
            },
        }
        data = {"account_profile": {"cash_available": 9800}}
        position_decision = report_runtime._build_front_page_position_decision(
            position_decision={"target_position_pct": 50, "signal_grade": "50"},
            selected_position_candidate=selected,
            data=data,
            market_research_snapshot={},
        )

        resolution = report_runtime._build_runtime_final_target_resolution(
            data=data,
            selected_position_candidate=selected,
            position_decision=position_decision,
            market_research_snapshot={},
        )
        lines = "\n".join(
            report_runtime._runtime_selected_target_solution_lines(
                selected,
                final_gate={"final_action": "固定交易窗口条件成立才参与，不满足回到0%"},
                mainline_turnover_summary={"current_mainline": "通信设备"},
                final_target_resolution=resolution,
            )
        )

        self.assertEqual(resolution["capital_priority_decision"]["capital_priority"], "tradable_proxy")
        self.assertEqual(resolution["new_entry_target"]["code"], "300308")
        self.assertEqual(resolution["watch_target"]["code"], "300308")
        self.assertEqual(resolution["process_target"]["code"], "300308")
        self.assertEqual(resolution["tradable_proxy_target"]["code"], "515880")
        self.assertEqual(resolution["display_target"]["code"], "515880")
        self.assertIn("| 最终结果 | 通信ETF(515880) |", lines)
        self.assertIn("| 目标标的 | 中际旭创(300308) |", lines)
        self.assertIn("| 小资金替代表达 | 通信ETF(515880) |", lines)
        self.assertIn("目标标的中际旭创(300308)，小资金账户可用通信ETF(515880)替代", lines)
        self.assertIn("+-- 目标标的: 中际旭创(300308)", lines)
        self.assertIn("+-- 小资金账户: 可用通信ETF(515880)替代", lines)
        self.assertIn("+-- 替代效应: 行业板块效应", lines)
        self.assertNotIn("跟风", resolution["display_target"].get("candidate_role", ""))

    def test_runtime_sequences_old_position_before_unbuyable_core_proxy(self):
        selected = {
            "name": "中际旭创",
            "code": "300308",
            "sector": "通信设备",
            "identity": "市场核心",
            "one_lot_amount": 16800,
            "sniper_role": "明日主买对象",
            "anchor_reversal_decision": "可作为主对象",
            "primary_buy_candidate": True,
            "sector_anchor": "中际旭创(300308)",
            "candidate_role": "板块锚",
            "relationship_to_anchor": "通信设备回流优先看板块锚",
            "leader_certainty_path": "大容量核心优先，慢即是快",
            "planned_participation": {
                "buy_window": "09:50-10:10",
                "fallback_state": "不满足回到0%",
            },
            "tradable_proxy_target": {
                "name": "通信ETF",
                "code": "515880",
                "sector": "通信设备",
                "proxy_effect_type": "行业板块效应",
                "proxy_reason": "跟踪通信设备方向，不退到弱跟风个股",
                "condition": "通信设备承接继续",
                "participation_window": "09:50-10:10",
                "fallback_state": "不满足回到0%",
                "execution_eligible": True,
                "target_position_pct": 50,
            },
        }
        data = {
            "account_profile": {"cash_available": 9800},
            "personal_position_context": {
                "existing_position_summary": {
                    "has_position": True,
                    "summary": "华电辽能(600396)：已有仓先按MA5T处理",
                },
            },
        }
        position_decision = report_runtime._build_front_page_position_decision(
            position_decision={"target_position_pct": 50, "signal_grade": "50"},
            selected_position_candidate=selected,
            data=data,
            market_research_snapshot={},
        )

        resolution = report_runtime._build_runtime_final_target_resolution(
            data=data,
            selected_position_candidate=selected,
            position_decision=position_decision,
            market_research_snapshot={},
        )
        lines = "\n".join(
            report_runtime._runtime_selected_target_solution_lines(
                selected,
                final_gate={"final_action": "固定交易窗口条件成立才参与，不满足回到0%"},
                mainline_turnover_summary={"current_mainline": "通信设备"},
                final_target_resolution=resolution,
            )
        )

        self.assertEqual(position_decision["target_position_pct"], 50)
        self.assertEqual(resolution["capital_priority_decision"]["capital_priority"], "new_entry_after_old_exit")
        self.assertEqual(resolution["existing_position_target"]["code"], "600396")
        self.assertEqual(resolution["new_entry_target"]["code"], "300308")
        self.assertEqual(resolution["watch_target"]["code"], "300308")
        self.assertEqual(resolution["tradable_proxy_target"]["code"], "515880")
        self.assertEqual(resolution["display_target"]["code"], "515880")
        self.assertIn("先处理旧仓", resolution["capital_priority_decision"]["reason"])
        self.assertIn("小资金账户可用通信ETF(515880)替代", resolution["capital_priority_decision"]["reason"])
        self.assertIn("| 最终结果 | 通信ETF(515880) |", lines)
        self.assertIn("| 旧仓处理 | 华电辽能(600396) |", lines)
        self.assertIn("| 目标标的 | 中际旭创(300308) |", lines)
        self.assertIn("| 小资金替代表达 | 通信ETF(515880) |", lines)
        self.assertLess(lines.index("+-- 旧仓处理"), lines.index("+-- 小资金账户"))

    def test_daily_judgment_front_panel_uses_anchor_primary_not_same_day_observation_records(self):
        index = {
            "available_trade_dates": ["2026-05-29", "2026-06-01"],
            "by_stock_code": {
                "601138": [{"stock_name": "工业富联", "stock_code": "601138", "report_date": "2026-06-01"}],
                "600487": [{"stock_name": "亨通光电", "stock_code": "600487", "report_date": "2026-06-01"}],
                "600522": [{"stock_name": "中天科技", "stock_code": "600522", "report_date": "2026-06-01"}],
            },
        }

        lines = report_runtime._build_daily_judgment_front_panel_lines(
            index,
            target_date="2026-06-01",
            market_state_snapshot={"market_state": "混沌"},
            mainline_turnover_summary={"current_mainline": "通信设备"},
            selected_position_candidate={
                "name": "工业富联",
                "code": "601138",
                "sniper_role": "明日主买对象",
                "anchor_reversal_decision": "可作为主对象",
            },
            extreme_conviction_list=[
                {
                    "name": "工业富联",
                    "code": "601138",
                    "sniper_role": "明日主买对象",
                    "anchor_reversal_decision": "可作为主对象",
                },
                {
                    "name": "亨通光电",
                    "code": "600487",
                    "sniper_role": "候选观察",
                    "anchor_reversal_decision": "降级观察",
                },
                {
                    "name": "中天科技",
                    "code": "600522",
                    "sniper_role": "候选观察补充",
                    "anchor_reversal_decision": "降级观察",
                },
            ],
        )
        rendered = "\n".join(lines)

        self.assertIn("| 核心候选判断 | 工业富联(601138) | 下一交易日验证是否进入资金视野 |", rendered)
        self.assertNotIn("亨通光电", rendered)
        self.assertNotIn("中天科技", rendered)

    def test_daily_judgment_front_panel_ignores_best_stock_when_final_result_waits(self):
        lines = report_runtime._build_daily_judgment_front_panel_lines(
            {"available_trade_dates": ["2026-06-09", "2026-06-10"], "by_stock_code": {}},
            target_date="2026-06-10",
            execution_stage_context={
                "best_stock": {"name": "双星新材", "code": "002585", "sector": "塑料"},
            },
            market_state_snapshot={"market_state": "混沌"},
            mainline_turnover_summary={"current_mainline": "无确认主线"},
            selected_position_candidate={},
            extreme_conviction_list=[
                {
                    "name": "中船特气",
                    "code": "688146",
                    "sniper_role": "候选观察",
                    "anchor_reversal_decision": "降级观察",
                },
                {
                    "name": "双星新材",
                    "code": "002585",
                    "sniper_role": "候选观察补充",
                    "anchor_reversal_decision": "降级观察",
                },
            ],
            final_target_resolution={
                "new_entry_target": {},
                "tradable_proxy_target": {},
                "watch_target": {"name": "中船特气", "code": "688146"},
                "capital_priority_decision": {"capital_priority": "wait", "reason": "无明日执行对象，保持观察"},
            },
        )
        rendered = "\n".join(lines)

        self.assertIn("| 核心候选判断 | 待补事实 | 下一交易日验证是否进入资金视野 |", rendered)
        self.assertNotIn("双星新材", rendered)
        self.assertNotIn("中船特气(688146) | 下一交易日验证是否进入资金视野", rendered)

    def test_daily_judgment_front_panel_uses_empty_core_when_final_action_blocks_new_entry(self):
        lines = report_runtime._build_daily_judgment_front_panel_lines(
            {"available_trade_dates": ["2026-06-09", "2026-06-10"], "by_stock_code": {}},
            target_date="2026-06-10",
            execution_stage_context={
                "best_stock": {"name": "双星新材", "code": "002585", "sector": "塑料"},
            },
            market_state_snapshot={"market_state": "退潮"},
            mainline_turnover_summary={"current_mainline": "无确认主线"},
            selected_position_candidate={
                "name": "双星新材",
                "code": "002585",
                "sniper_role": "明日主买对象",
                "anchor_reversal_decision": "可作为主对象",
            },
            extreme_conviction_list=[
                {
                    "name": "双星新材",
                    "code": "002585",
                    "sniper_role": "明日主买对象",
                    "anchor_reversal_decision": "可作为主对象",
                },
            ],
            final_target_resolution={
                "new_entry_target": {"name": "双星新材", "code": "002585"},
                "display_target": {"name": "双星新材", "code": "002585"},
                "capital_priority_decision": {"capital_priority": "new_entry", "reason": "过程候选仍在"},
            },
            final_gate={
                "can_new_entry": False,
                "allow_attack_50_ready": False,
                "final_action": "空仓等待，禁止参与；若你有仓位，只做退出不做幻想",
            },
        )
        rendered = "\n".join(lines)

        self.assertIn("| 核心候选判断 | 待补事实 | 下一交易日验证是否进入资金视野 |", rendered)
        self.assertNotIn("双星新材(002585) | 下一交易日验证是否进入资金视野", rendered)

    def test_front_page_target_prefers_current_mainline_primary_over_stale_selected_candidate(self):
        data = {}
        market_snapshot = {
            "mainline_turnover_summary": {"current_mainline": "通信设备"},
            "selected_position_candidate": {
                "name": "大有能源",
                "code": "600403",
                "sector": "煤炭开采",
                "sniper_role": "明日主买对象",
                "anchor_reversal_decision": "可作为主对象",
            },
            "extreme_conviction_list": [
                {
                    "name": "工业富联",
                    "code": "601138",
                    "sector": "通信设备",
                    "sniper_role": "明日主买对象",
                    "anchor_reversal_decision": "可作为主对象",
                    "primary_buy_candidate": True,
                    "sector_anchor": "工业富联(601138)",
                },
                {
                    "name": "意华股份",
                    "code": "002897",
                    "sector": "通信设备",
                    "sniper_role": "候选观察",
                    "anchor_reversal_decision": "降级观察",
                },
            ],
        }
        execution_context = {
            "market_research_snapshot": market_snapshot,
            "mainline_turnover_summary": {"current_mainline": "通信设备"},
            "selected_position_candidate": dict(market_snapshot["selected_position_candidate"]),
            "extreme_conviction_list": list(market_snapshot["extreme_conviction_list"]),
        }

        selected = report_runtime._resolve_front_page_target_candidate(
            data=data,
            execution_stage_context=execution_context,
            report_lines=[],
            target_date="2026-06-02",
        )
        panel_context = report_runtime._build_current_judgment_context_for_panel(
            execution_stage_context=execution_context,
            market_research_snapshot=market_snapshot,
            mainline_turnover_summary={"current_mainline": "通信设备"},
            selected_position_candidate=selected,
            extreme_conviction_list=execution_context["extreme_conviction_list"],
            final_target_resolution={
                "new_entry_target": selected,
                "watch_target": selected,
                "capital_priority_decision": {"capital_priority": "new_entry"},
            },
        )

        self.assertEqual(selected["code"], "601138")
        self.assertEqual(data["current_core_candidate"]["code"], "601138")
        self.assertEqual(execution_context["current_core_candidate"]["code"], "601138")
        self.assertEqual(market_snapshot["current_core_candidate"]["code"], "601138")
        self.assertEqual([item["code"] for item in panel_context["core_candidates"]], ["601138"])

    def test_front_page_target_is_stable_when_current_candidate_order_changes(self):
        stale_selected = {
            "name": "大有能源",
            "code": "600403",
            "sector": "煤炭开采",
            "sniper_role": "明日主买对象",
            "anchor_reversal_decision": "可作为主对象",
        }
        primary = {
            "name": "工业富联",
            "code": "601138",
            "sector": "通信设备",
            "sniper_role": "明日主买对象",
            "anchor_reversal_decision": "可作为主对象",
            "primary_buy_candidate": True,
            "sector_anchor": "工业富联(601138)",
        }
        observation = {
            "name": "意华股份",
            "code": "002897",
            "sector": "通信设备",
            "sniper_role": "候选观察",
            "anchor_reversal_decision": "降级观察",
        }

        resolved_codes = []
        for extreme_list in ([observation, primary], [primary, observation]):
            data = {}
            market_snapshot = {
                "mainline_turnover_summary": {"current_mainline": "通信设备"},
                "selected_position_candidate": dict(stale_selected),
                "extreme_conviction_list": [dict(item) for item in extreme_list],
            }
            execution_context = {
                "market_research_snapshot": market_snapshot,
                "mainline_turnover_summary": {"current_mainline": "通信设备"},
                "selected_position_candidate": dict(stale_selected),
                "extreme_conviction_list": [dict(item) for item in extreme_list],
            }
            selected = report_runtime._resolve_front_page_target_candidate(
                data=data,
                execution_stage_context=execution_context,
                report_lines=[],
                target_date="2026-06-02",
            )
            resolved_codes.append(selected["code"])

        self.assertEqual(resolved_codes, ["601138", "601138"])

    def test_front_page_target_does_not_reverse_extract_from_rendered_report_lines(self):
        data = {}
        execution_context = {}

        selected = report_runtime._resolve_front_page_target_candidate(
            data=data,
            execution_stage_context=execution_context,
            report_lines=[
                "## 明日极度看好名单",
                "| 股票 | 代码 | 所属方向 |",
                "|------|------|----------|",
                "| 双星新材 | 002585 | 塑料 |",
            ],
            target_date="2026-06-10",
        )

        self.assertEqual(selected, {})
        self.assertTrue(data["front_page_text_candidate_fallback_suppressed"])
        self.assertTrue(execution_context["front_page_text_candidate_fallback_suppressed"])

    def test_final_target_resolution_audit_records_front_page_as_canonical_when_identity_changes(self):
        data = {}
        execution_context = {}
        market_snapshot = {}
        first_resolution = {
            "new_entry_target": {"name": "中船特气", "code": "688146"},
            "watch_target": {"name": "中船特气", "code": "688146"},
            "capital_priority_decision": {"capital_priority": "new_entry"},
        }
        final_resolution = {
            "new_entry_target": {},
            "watch_target": {"name": "双星新材", "code": "002585"},
            "capital_priority_decision": {"capital_priority": "wait"},
        }

        report_runtime._store_runtime_final_target_resolution(
            first_resolution,
            data=data,
            execution_stage_context=execution_context,
            market_research_snapshot=market_snapshot,
            phase="pre_tail",
        )
        stored = report_runtime._store_runtime_final_target_resolution(
            final_resolution,
            data=data,
            execution_stage_context=execution_context,
            market_research_snapshot=market_snapshot,
            phase="front_page",
        )

        audit = data["final_target_resolution_audit"]
        self.assertEqual(audit["pre_tail"]["key"], "688146")
        self.assertEqual(audit["front_page"]["key"], "002585")
        self.assertTrue(audit["identity_drift"])
        self.assertEqual(audit["resolution_policy"], "front_page_final_resolution")
        self.assertEqual(stored["resolution_phase"], "front_page")
        self.assertEqual(market_snapshot["final_target_resolution"]["resolution_identity"]["key"], "002585")

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

    def test_postgres_only_decision_ledger_tracking_rejects_non_postgres_without_json_fallback(self):
        class NonPostgresService:
            def is_postgres_backed(self):
                return False

        class StubDatabaseService:
            fact_store_called = False

            @classmethod
            def from_environment(cls, db_path=None):
                return NonPostgresService()

            @classmethod
            def fact_store_from_environment(cls, db_path=None):
                cls.fact_store_called = True
                return NonPostgresService()

        previous = getattr(report_runtime, "decision_ledger_postgres_only", None)
        with TemporaryDirectory() as tempdir:
            ledger_dir = Path(tempdir) / "data" / "decision-ledger"
            ledger_dir.mkdir(parents=True)
            (ledger_dir / "index.json").write_text(
                '{"by_stock_code":{"000001":[{"stock_code":"000001","stock_name":"JSON样本"}]}}',
                encoding="utf-8",
            )
            try:
                report_runtime.decision_ledger_postgres_only = True
                with patch.object(report_runtime, "DatabaseService", StubDatabaseService, create=True):
                    with patch.dict("os.environ", {}, clear=True):
                        with self.assertRaisesRegex(RuntimeError, "PostgreSQL decision ledger index storage"):
                            report_runtime._read_decision_ledger_index_for_tracking(tempdir)
            finally:
                if previous is None:
                    delattr(report_runtime, "decision_ledger_postgres_only")
                else:
                    report_runtime.decision_ledger_postgres_only = previous

        self.assertTrue(StubDatabaseService.fact_store_called)

    def test_postgres_only_decision_ledger_tracking_ignores_injected_json_reader(self):
        captured = {"reader_called": False}

        def injected_reader(_path):
            captured["reader_called"] = True
            return {"by_stock_code": {"000001": [{"stock_code": "000001", "stock_name": "JSON样本"}]}}

        class PostgresService:
            def is_postgres_backed(self):
                return True

            def read_decision_ledger_index(self):
                return {"by_stock_code": {"601991": [{"stock_code": "601991", "stock_name": "大唐发电"}]}}

        class StubDatabaseService:
            @classmethod
            def from_environment(cls, db_path=None):
                return PostgresService()

        previous_reader = getattr(report_runtime, "read_decision_ledger_index", None)
        previous_postgres_only = getattr(report_runtime, "decision_ledger_postgres_only", None)
        try:
            report_runtime.read_decision_ledger_index = injected_reader
            report_runtime.decision_ledger_postgres_only = True
            with patch.object(report_runtime, "DatabaseService", StubDatabaseService, create=True):
                with patch.dict("os.environ", {}, clear=True):
                    index = report_runtime._read_decision_ledger_index_for_tracking("/tmp/daily-report")
        finally:
            if previous_reader is None:
                delattr(report_runtime, "read_decision_ledger_index")
            else:
                report_runtime.read_decision_ledger_index = previous_reader
            if previous_postgres_only is None:
                delattr(report_runtime, "decision_ledger_postgres_only")
            else:
                report_runtime.decision_ledger_postgres_only = previous_postgres_only

        self.assertFalse(captured["reader_called"])
        self.assertIn("601991", index["by_stock_code"])
        self.assertNotIn("000001", index["by_stock_code"])

    def test_runtime_extreme_mention_tracking_prefers_fact_db_rows_for_crud_review(self):
        def _run_execution_stages(stage_specs, stage_context=None, stage_lookup=None):
            return {"lines": [], "module_logs": [], "context": {}}

        def _fake_load_index(path):
            by_stock_code = {
                f"60{day:04d}": [
                    {
                        "stock_code": f"60{day:04d}",
                        "stock_name": f"索引样本{day}",
                        "latest_trade_date": f"2026-05-{day:02d}",
                        "planned_participation": {"source_tier": "extreme_conviction", "buy_window": "09:50-10:10"},
                        "mentions": [
                            {
                                "mention_trade_date": f"2026-05-{day:02d}",
                                "rank": 1,
                                "source_section": "极度看好名单",
                            }
                        ],
                    }
                ]
                for day in range(1, 31)
            }
            by_stock_code["600578"] = [
                {
                    "stock_code": "600578",
                    "stock_name": "索引旧样本",
                    "latest_trade_date": "2026-05-20",
                    "planned_participation": {"source_tier": "extreme_conviction", "buy_window": "09:30-09:35"},
                    "mentions": [{"mention_trade_date": "2026-05-20", "rank": 1, "source_section": "极度看好名单"}],
                }
            ]
            return {
                "latest_trade_date": "2026-05-20",
                "by_stock_code": by_stock_code,
            }

        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            service = _RuntimeMemoryFactService()
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

            with patch("storage.database_service.DatabaseService.fact_store_from_environment", return_value=service):
                result = report_runtime.render_markdown_report_runtime(
                    {"exchange_monitor_today": [], "exchange_monitor_nextday": []},
                    "2026-05-20",
                    helpers=helpers,
                    config={},
                )

        mention_section = result["report"].split("**历史过程复盘：明日极度看好近25日跟踪表**", 1)[1].split(
            "**重点观察历史回测表**", 1
        )[0]
        self.assertIn("当前可复盘样本：31条，覆盖2026-05-01至2026-05-30", mention_section)
        self.assertIn("本表展示最近25个交易日周期内样本", mention_section)
        self.assertIn("| 2026-05-19 | 汇源通信 | 000586 |", mention_section)
        self.assertIn("| 2026-05-20 | 晶方科技 | 603005 |", mention_section)
        self.assertNotIn("| 2026-05-20 | 索引旧样本 | 600578 |", mention_section)

    def test_runtime_marks_a_kill_shape_mentions_before_tracking_query(self):
        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            service = _RuntimeMemoryFactService()
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

            with patch("storage.database_service.DatabaseService.fact_store_from_environment", return_value=service):
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
            fact_store_called = False

            @classmethod
            def from_environment(cls, db_path=None):
                cls.db_path = db_path
                return cls.service

            @classmethod
            def fact_store_from_environment(cls, db_path=None):
                cls.fact_store_called = True
                return cls.service

        with patch.dict("sys.modules", {"storage.database_service": types.SimpleNamespace(DatabaseService=StubDatabaseService)}):
            rows = report_runtime._query_extreme_conviction_mention_rows_for_tracking(
                root_dir="/tmp/daily-report",
                end_date="2026-05-29",
                window_days=25,
                include_a_kill=True,
            )

        self.assertTrue(StubDatabaseService.fact_store_called)
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

    def test_postgres_only_extreme_mention_tracking_rejects_non_postgres_without_legacy_fallback(self):
        class NonPostgresService:
            def is_postgres_backed(self):
                return False

        class StubDatabaseService:
            fact_store_called = False

            @classmethod
            def from_environment(cls, db_path=None):
                return NonPostgresService()

            @classmethod
            def fact_store_from_environment(cls, db_path=None):
                cls.fact_store_called = True
                return NonPostgresService()

        previous = getattr(report_runtime, "decision_ledger_postgres_only", None)
        try:
            report_runtime.decision_ledger_postgres_only = True
            with patch.dict("sys.modules", {"storage.database_service": types.SimpleNamespace(DatabaseService=StubDatabaseService)}):
                with patch.dict("os.environ", {}, clear=True):
                    with self.assertRaisesRegex(RuntimeError, "PostgreSQL extreme conviction storage"):
                        report_runtime._query_extreme_conviction_mention_rows_for_tracking(
                            root_dir="/tmp/daily-report",
                            end_date="2026-05-29",
                            window_days=25,
                        )
        finally:
            if previous is None:
                delattr(report_runtime, "decision_ledger_postgres_only")
            else:
                report_runtime.decision_ledger_postgres_only = previous

        self.assertTrue(StubDatabaseService.fact_store_called)

    def test_postgres_only_extreme_mention_tracking_ignores_injected_query_reader(self):
        captured = {"query_called": False}

        def query_rows(**kwargs):
            captured["query_called"] = True
            return [{"stock_code": "000001", "stock_name": "注入旧样本"}]

        class PostgresService:
            def is_postgres_backed(self):
                return True

            def mark_a_kill_shape_extreme_conviction_mentions(self, end_date, *, window_days=25, return_details=False):
                return {"updated_count": 0, "updated_records": []}

            def query_extreme_conviction_mentions(self, end_date, *, window_days=25, include_a_kill=False):
                return [{"stock_code": "601991", "stock_name": "大唐发电"}]

        class StubDatabaseService:
            @classmethod
            def from_environment(cls, db_path=None):
                return PostgresService()

        previous_query = report_runtime.query_extreme_conviction_mention_rows_for_tracking if hasattr(
            report_runtime, "query_extreme_conviction_mention_rows_for_tracking"
        ) else None
        previous_postgres_only = getattr(report_runtime, "decision_ledger_postgres_only", None)
        try:
            report_runtime.query_extreme_conviction_mention_rows_for_tracking = query_rows
            report_runtime.decision_ledger_postgres_only = True
            with patch.dict("sys.modules", {"storage.database_service": types.SimpleNamespace(DatabaseService=StubDatabaseService)}):
                with patch.dict("os.environ", {}, clear=True):
                    rows = report_runtime._query_extreme_conviction_mention_rows_for_tracking(
                        root_dir="/tmp/daily-report",
                        end_date="2026-05-29",
                        window_days=25,
                    )
        finally:
            if previous_query is None:
                delattr(report_runtime, "query_extreme_conviction_mention_rows_for_tracking")
            else:
                report_runtime.query_extreme_conviction_mention_rows_for_tracking = previous_query
            if previous_postgres_only is None:
                delattr(report_runtime, "decision_ledger_postgres_only")
            else:
                report_runtime.decision_ledger_postgres_only = previous_postgres_only

        self.assertFalse(captured["query_called"])
        self.assertEqual(rows[0]["stock_code"], "601991")

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

        self.assertIn("**历史过程复盘：明日极度看好近25日跟踪表**", result["report"])
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
                    "- **明天仓位放多少**: 盘前0%；参与窗口命中后才评估50%条件执行",
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
                    "selected_position_candidate": {
                        "name": "汇源通信",
                        "code": "000586",
                        "sector": "通信设备",
                        "anchor_reversal_decision": "可作为主对象",
                        "target_role": "core",
                        "strength_evidence": ["通信设备资金回流", "板块锚"],
                        "participation_window": "09:50-10:10",
                        "required_steps": ["主线承接", "回踩收回MA5"],
                        "fallback_state": "不满足回到0%",
                        "target_position_pct": 50,
                        "probe_entry_price": 10.0,
                        "ma5": 9.9,
                        "ma10": 9.8,
                        "vwap": 9.95,
                        "stop_price": 9.6,
                        "target_price": 11.0,
                    },
                    "extreme_conviction_list": [
                        {
                            "name": "汇源通信",
                            "code": "000586",
                            "sector": "通信设备",
                            "anchor_reversal_decision": "可作为主对象",
                            "candidate_role": "板块锚",
                            "target_role": "core",
                            "planned_participation": {
                                "buy_window": "09:50-10:10",
                                "fallback_state": "不满足回到0%",
                            },
                        }
                    ],
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
                "position_level": "0%不参与",
                "position_reason": "普通防守态",
                "final_gate": {
                    "final_action": "空仓等待",
                    "operation_state": "撤退态",
                    "can_new_entry": False,
                    "should_reduce": True,
                },
                "environment_display": {"position_level": "0%不参与", "operation_state": "撤退态"},
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
        self.assertIn("| 明日执行对象 | 汇源通信(000586) |", rendered)
        self.assertIn("| 进攻仓位三态 | 50% |", rendered)
        self.assertIn("| 明日最大仓位 | 50% |", rendered)
        self.assertIn("| 只看明日执行对象 | 汇源通信(000586) | 09:30-09:35或09:50-10:10 |", rendered)
        self.assertIn("| 条件满足才50%条件执行；不满足回到0% |", rendered)
        self.assertIn("- **进攻仓位三态**: 50%条件执行", rendered)
        self.assertIn("- **明天仓位放多少**: 50%条件执行；盘前不抢跑", rendered)
        self.assertNotIn("没有唯一对象，完整候选仅保留在附录和快照", rendered)
        self.assertNotIn("空仓等待，禁止参与；若你有仓位，只做退出不做幻想", rendered)
        self.assertNotIn("- **进攻仓位三态**: 0%不参与", rendered)
        self.assertNotIn("盘前0%；参与窗口命中后才评估50%条件执行", rendered)
        self.assertNotIn("| 明日执行对象 | 无 |", rendered)
        self.assertNotIn("| 进攻仓位三态 | 0% |", rendered)
        self.assertIn("最终执行条件: 明日目标标的保留50%条件执行", stdout.getvalue())
        self.assertNotIn("最终执行条件: 空仓等待", stdout.getvalue())

    def test_positive_final_action_rewrites_stale_appendix_watch_plan(self):
        lines = [
            "##### 附录：Step 5 - 过程候选最终复核",
            "**明天先盯哪只**: 金安国纪(002636)",
            "- **现在是什么情况**: 市场允许出手，但还没有缩到一只可买股，明日先等它自己证明",
            "##### 附录：明日操作计划",
            "**最终动作表**（只展示真正具备参与资格的对象）:",
            "| 明天具体怎么做 | 股票 | 代码 | 触发条件 | 止损/时间 |",
            "|----------|------|------|----------|-----------|",
            "| 👀 明天先盯哪只 | 金安国纪 | 002636 | 09:50-10:10站上97.34后，再看是否走成明天唯一能买的那只 | 92.47 / 3-5天 |",
            "**明天仓位怎么放**:",
            "- **现在到底是什么状态**: 还没有缩到一只可买股",
            "- **明天仓位放多少**: 0%（市场允许出手，但还没有可买股前不开仓）",
            "- **明天具体怎么做**: 只观察明天先盯哪只，等它走成明天唯一能买的那只后再买",
            "| 明日买点预计算 | 先确认重点盯盘股，再看能否缩到一只可买股 |",
            "| 过程候选最终复核 | 跨线明天先盯哪只：金安国纪(002636)；只有走成明天唯一能买的那只才参与 |",
            "**明日继续观察**（1只，等买点出现）:",
            "- **接着做什么**: 进入Step 4，为候选组预计算买点并筛出明天唯一能买的那只",
            "- **出手时怎么做**: 只能等它走成明天唯一能买的那只后再买，盘中强也不允许提前抢跑",
            "- **现在是什么情况**: 市场已允许出手，但还没有缩到一只合格参与对象",
            "- **接着做什么**: 当前还在等待层，先等买点自己长出来，不提前写成执行对象",
            "| 今日关注标的 | 盛龙股份(001257)：主线核心候选，优先观察 |",
            "| 操作风格 | 空仓 |",
            "| 明日核心标的 | 1+1 / 4只 |",
            "| 明日风险预判 | 市场已允许出手，但现在还只有重点盯盘股，还没有缩到一只合格参与对象；主观理解只用于观察，不用于提前硬上 |",
            "| 明日策略 | 不开新仓，只观察：当前裁决不允许新增跟随，先看环境和主线是否继续强化 |",
        ]

        normalized = report_runtime._normalize_attack_preview_appendix_lines(
            lines,
            selected_position_candidate={"name": "云南锗业", "code": "002428", "sector": "小金属"},
            position_decision={"target_position_pct": 50, "signal_grade": "50"},
            final_target_resolution={
                "capital_priority_decision": {"capital_priority": "new_entry"},
            },
        )
        rendered = "\n".join(normalized)

        self.assertIn("过程候选回看样本", rendered)
        self.assertIn("| 只看明日执行对象 | 云南锗业 | 002428 | 固定交易窗口条件成立才50%条件执行；不满足回到0%不参与 |", rendered)
        self.assertIn("- **现在到底是什么状态**: 已收口到唯一明日动作：云南锗业(002428)", rendered)
        self.assertIn("- **明天仓位放多少**: 50%条件执行；固定交易窗口条件不成立回到0%", rendered)
        self.assertIn("先确认唯一明日动作：云南锗业(002428)是否满足固定交易窗口条件", rendered)
        self.assertIn("| 今日关注标的 | 唯一明日动作：云南锗业(002428) |", rendered)
        self.assertIn("| 操作风格 | 50%条件执行；盘前不抢跑 |", rendered)
        self.assertIn("| 明日核心标的 | 唯一明日动作：云南锗业(002428) |", rendered)
        self.assertIn("| 明日策略 | 只看明日执行对象云南锗业(002428)；固定交易窗口条件成立才50%条件执行，不满足回到0%不参与 |", rendered)
        self.assertNotIn("| 👀 明天先盯哪只 | 金安国纪 | 002636 |", rendered)
        self.assertNotIn("明天先盯哪只", rendered)
        self.assertNotIn("唯一能买", rendered)
        self.assertNotIn("还没有缩到一只可买股", rendered)
        self.assertNotIn("还没有缩到一只合格参与对象", rendered)
        self.assertNotIn("当前还在等待层", rendered)
        self.assertNotIn("操作风格 | 空仓", rendered)
        self.assertNotIn("不开新仓，只观察", rendered)
        self.assertNotIn("可买股", rendered)
        self.assertNotIn("买点出现", rendered)
        self.assertNotIn("预计算买点", rendered)
        self.assertNotIn("0%（市场允许出手", rendered)

    def test_positive_final_action_keeps_independent_etf_holding_from_old_position_appendix(self):
        lines = [
            "##### 附录：明日操作计划",
            "**最终动作表**（只展示真正具备参与资格的对象）:",
            "| 明天具体怎么做 | 股票 | 代码 | 触发条件 | 止损/时间 |",
            "|----------|------|------|----------|-----------|",
            "| 只看明日执行对象 | 太极实业 | 600667 | 固定交易窗口条件成立才50%条件执行；不满足回到0%不参与 | 买后用失效价和单笔-5%底线处理风险 |",
            "##### 附录：# 今日总决策面板",
            "| 字段 | 内容 |",
            "|------|------|",
            "| 市场情绪状态 | 🟠 只处理旧仓 |",
            "| 账户后台任务负担 | 有持仓需先处理 |",
            "| 持仓优先动作 | 先处理旧仓，再看新增 |",
            "| 今日新增上限 | 0 |",
            "| 主买对象 | 太极实业(600667) |",
            "| 补位对象 | 过程候选回看样本，不覆盖唯一明日动作 |",
            "| 明天能不能开仓 | 🟠 只处理旧仓 | 环境已转撤退，先退出，等下一轮新脉冲。 | 动作锚定到“明天能不能开仓” |",
            "| 明日大盘预期 | 🟠 只处理旧仓；若你有旧仓先去弱留强，不新增参与 |",
            "| 明日环境与跟随裁决 | 🟠 只处理旧仓；若你有旧仓先去弱留强，不新增参与 |",
            "| 观察层 | 通鼎互联(002491) | watch_anchor | 市场条件：未满足(🟠 只处理旧仓)；主线条件：未满足 |",
            "**明日裁决**: 🟠 只处理旧仓",
            "**开盘前动作**: 先观察市场整体，不提前放松买入资格；若你有旧仓先去弱留强，不新增参与",
            "**明天仓位怎么放**:",
            "- **进攻仓位三态**: 50%条件执行",
            "- **明日裁决**: 🟠 只处理旧仓",
            "- **明天仓位放多少**: 50%条件执行；固定交易窗口条件不成立回到0%（保持空仓）",
            "- **明天具体怎么做**: 不新增参与；若有旧仓只处理旧仓，否则保持空仓",
            "**09:50-10:10买卖窗口（09:50-10:10）**:",
            "- 重点观察优先对象是否继续走强；若你有旧仓，只处理旧仓，不做新增",
        ]

        normalized = report_runtime._normalize_attack_preview_appendix_lines(
            lines,
            selected_position_candidate={"name": "太极实业", "code": "600667", "sector": "半导体"},
            position_decision={"target_position_pct": 50, "signal_grade": "50"},
            final_target_resolution={
                "capital_priority_decision": {"capital_priority": "new_entry"},
                "existing_position_summary": "持有芯片ETF(159995)，33%仓位；持仓继续独立评估，不因新机会自动处理",
            },
        )
        rendered = "\n".join(normalized)

        self.assertIn("| 市场情绪状态 | 50%条件执行；只看太极实业(600667)固定交易窗口条件 |", rendered)
        self.assertIn("| 账户后台任务负担 | 持仓独立评估，不覆盖唯一明日动作 |", rendered)
        self.assertIn("| 持仓优先动作 | 持仓独立评估；新机会按自身条件处理 |", rendered)
        self.assertIn("| 今日新增上限 | 50%条件执行；条件不成立回0% |", rendered)
        self.assertIn("| 明天是否参与 | 50%条件执行 | 只看明日执行对象太极实业(600667)；固定交易窗口条件成立才50%条件执行，不满足回到0%不参与 | 动作锚定到唯一明日动作 |", rendered)
        self.assertIn("| 明日大盘预期 | 只看明日执行对象太极实业(600667)；固定交易窗口条件成立才50%条件执行，不满足回到0%不参与；市场背景只作参考 |", rendered)
        self.assertIn("| 明日环境与跟随裁决 | 只看明日执行对象太极实业(600667)；固定交易窗口条件成立才50%条件执行，不满足回到0%不参与；市场背景只作参考 |", rendered)
        self.assertIn("市场条件：未满足(过程候选不覆盖唯一明日动作)", rendered)
        self.assertIn("**明日裁决**: 50%条件执行；只看太极实业(600667)固定交易窗口条件", rendered)
        self.assertIn("**开盘前动作**: 只看明日执行对象太极实业(600667)；固定交易窗口条件成立才50%条件执行，不满足回到0%不参与；市场背景只作参考", rendered)
        self.assertIn("- **明日裁决**: 50%条件执行；只看太极实业(600667)固定交易窗口条件", rendered)
        self.assertIn("持仓独立评估，不满足固定交易窗口条件就回到0%不参与", rendered)
        self.assertIn("只看太极实业(600667)是否满足固定交易窗口条件", rendered)
        self.assertNotIn("若你有旧仓先去弱留强", rendered)
        self.assertNotIn("先处理旧仓", rendered)
        self.assertNotIn("只处理旧仓", rendered)
        self.assertNotIn("不新增参与；若有旧仓", rendered)

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
        self.assertIn("| 竞价表态 + 回封观察 | 0%不参与 |", rendered)
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
            "- **明天仓位放多少**: 盘前0%；参与窗口命中后才评估50%条件执行",
            "- **现在到底是什么状态**: 0%不参与，禁止抢跑，但保留重点观察名单的盘中确认路径",
            "- 50%条件执行需要先等固定交易窗口内条件成立；未确认前按0%处理，确认后按失效价和单笔-5%底线处理风险",
            "- **确认后怎么做**: 09:50-10:10站上确认价，且板块承接不塌，才评估50%条件执行；未命中继续0%不参与",
            "- **出手时怎么做**: 盘前0%只代表不抢跑；09:50-10:10窗口内条件成立后，再评估50%条件执行",
            "- 以观察和处理持仓为主；新仓只允许固定交易窗口内条件成立后的主线核心50%条件执行",
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

        self.assertIn("明日不新增参与，只观察风险是否钝化、主攻线承接和观察对象是否重新成立", rendered)
        self.assertIn("- **进攻仓位三态**: 0%不参与", rendered)
        self.assertIn("- **明天仓位放多少**: 盘前0%；暂无新增参与资格，只观察风险是否钝化", rendered)
        self.assertIn("0%不参与，不抢跑，只保留候选观察的盘中复核路径", rendered)
        self.assertIn("- 0%不参与：最终结论不允许新增参与，只观察风险是否钝化", rendered)
        self.assertIn("- **确认后怎么做**: 只保留观察；未出现执行资格前不新增参与；未命中继续0%不参与", rendered)
        self.assertIn("- **出手时怎么做**: 盘前0%只代表不抢跑；只观察，不新增参与", rendered)
        self.assertIn("- 以观察和处理持仓为主；不做新开仓", rendered)
        self.assertIn("观察对象是否重新成立", rendered)
        self.assertIn("重点观察复核脚本", rendered)
        self.assertIn("| 观察窗口 | 观察状态 | 检查步骤 | 回封观察 | 作废条件 |", rendered)
        self.assertIn("| 09:50-10:10 | 0%不参与 | 主线承接 / 站上确认价 | 快速回封 | 不满足继续0% |", rendered)
        self.assertNotIn("重点观察参与脚本", rendered)
        self.assertNotIn("条件50", rendered)
        self.assertNotIn("才评估50%", rendered)
        self.assertNotIn("50%条件执行", rendered)
        self.assertNotIn("唯一对象是否", rendered)
        self.assertNotIn("50%条件执行", rendered)

    def test_runtime_appendix_uses_observation_language_when_old_position_wins(self):
        lines = [
            "- **明天具体怎么做**: 明日目标标的保留条件100%核心进攻：只看601138 工业富联，固定交易窗口内条件成立才执行，不满足回到0%",
            "- **明天仓位放多少**: 盘前0%；参与窗口命中后才评估50%条件执行",
            "**重点观察参与脚本**:",
            "| 参与窗口 | 仓位三态 | 检查步骤 | 回封参与 | 作废条件 |",
            "|----------|----------|----------|----------|----------|",
            "| 09:30-09:35 | 100% | 竞价表态 / 回封/打板 | 快速回封 | 不满足继续0% |",
        ]

        normalized = report_runtime._normalize_attack_preview_appendix_lines(
            lines,
            selected_position_candidate={"code": "601138", "name": "工业富联"},
            position_decision={"signal_grade": "100", "target_position_pct": 100, "participation_mode": "full_100"},
            final_target_resolution={
                "capital_priority_decision": {"capital_priority": "old_position_t"},
                "watch_target": {"code": "601138", "name": "工业富联"},
                "existing_position_target": {"code": "600396", "name": "华电辽能"},
            },
        )
        rendered = "\n".join(normalized)

        self.assertIn("不新增参与；只保留观察对象；未出现执行资格前不新增参与", rendered)
        self.assertIn("重点观察复核脚本", rendered)
        self.assertIn("| 观察窗口 | 观察状态 | 检查步骤 | 回封观察 | 作废条件 |", rendered)
        self.assertNotIn("明日目标标的保留条件100%核心进攻", rendered)
        self.assertNotIn("才评估50%条件执行", rendered)
        self.assertNotIn("重点观察参与脚本", rendered)
        self.assertNotIn("参与窗口", rendered)
        self.assertNotIn("回封/打板", rendered)

    def test_runtime_appendix_aligns_observation_anchor_with_final_watch_target(self):
        lines = [
            "**观察优先" + "锚点**: 豫能控股(001896)",
            "**先看顺序**（优先盯最能反映主线承接的对象）:",
            "- 👀 豫能控股(001896) - 主线继续看谁，09:50-10:10观察价9.21",
            "- 👀 华电能源(600726) - 备选观察",
        ]

        normalized = report_runtime._normalize_attack_preview_appendix_lines(
            lines,
            selected_position_candidate={"code": "600688", "name": "上海石化"},
            position_decision={"signal_grade": "0", "target_position_pct": 0, "participation_mode": "observe_0"},
            final_target_resolution={
                "capital_priority_decision": {"capital_priority": "old_position_t"},
                "watch_target": {"code": "600688", "name": "上海石化"},
                "existing_position_target": {"code": "600396", "name": "华电辽能"},
            },
        )
        rendered = "\n".join(normalized)

        self.assertIn("**观察优先对象**: 上海石化(600688)", rendered)
        self.assertIn("- 👀 上海石化(600688) - 主线继续看谁，09:50-10:10观察价9.21", rendered)
        self.assertNotIn("**观察优先对象**: 豫能控股(001896)", rendered)
        self.assertNotIn("观察优先" + "锚点", rendered)
        self.assertNotIn("- 👀 豫能控股(001896) - 主线继续看谁", rendered)

    def test_sanitize_report_lines_aligns_appendix_anchor_from_front_page_observation_anchor(self):
        lines = [
            "## 五、个股解读",
            "| 项目 | 结论 |",
            "|------|------|",
            "| 观察" + "锚 | 600688 上海石化（炼化及贸） |",
            "## 八、详细附录",
            "**观察优先" + "锚点**: 豫能控股(001896)",
            "**先看顺序**（优先盯最能反映主线承接的对象）:",
            "- 👀 豫能控股(001896) - 观察价9.21",
            "- 👀 华电能源(600726) - 备选观察",
        ]

        rendered = "\n".join(report_runtime._sanitize_report_lines(lines))

        self.assertIn("**观察优先对象**: 600688 上海石化（炼化及贸）", rendered)
        self.assertIn("- 👀 600688 上海石化（炼化及贸） - 观察价9.21", rendered)
        self.assertNotIn("**观察优先对象**: 豫能控股(001896)", rendered)
        self.assertNotIn("观察优先" + "锚点", rendered)
        self.assertNotIn("- 👀 豫能控股(001896)", rendered)

    def test_sanitize_report_lines_relabels_legacy_observation_anchor_terms(self):
        lines = [
            "| 观察对象 | 豫能控股(001896)：观察" + "锚，不是执行对象 |",
            "| 只看观察" + "锚 | 豫能控股(001896) | 09:50-10:10 | 主线承接 | 不满足继续0% |",
            "`-- 最终观察" + "锚: 豫能控股(001896), 0%只观察",
            "| 0%不参与 | 不确定时不值得主动参与 | 电力 | 电力 | 观察聚焦 | 观察" + "锚：豫能控股(001896) | 0%不参与 | 盘前0%；只观察豫能控股，不能转成新增参与；不满足继续0% |",
        ]

        rendered = "\n".join(report_runtime._sanitize_report_lines(lines))

        self.assertIn("| 观察对象 | 豫能控股(001896)：观察对象，不是执行目标 |", rendered)
        self.assertIn("| 只看观察对象 | 豫能控股(001896) | 09:50-10:10 | 主线承接 | 不满足继续0% |", rendered)
        self.assertIn("`-- 最终观察对象: 豫能控股(001896), 0%只观察", rendered)
        self.assertIn("观察对象：豫能控股(001896)", rendered)
        self.assertNotIn("观察" + "锚", rendered)
        self.assertNotIn("不是执行对象", rendered)
        self.assertNotIn("不能转成新增参与", rendered)

    def test_candidate_quality_process_panel_prefers_final_watch_target_over_stale_anchor_fields(self):
        from domains.execution_chain.pk_decision_nodes.candidate_quality_scorecard import (
            build_candidate_quality_scorecard_payload,
        )
        from report.action_plan_nodes import build_action_plan_candidate_quality_node

        payload = build_candidate_quality_scorecard_payload(
            {
                "trade_gate_open": False,
                "position_level": "0%不参与",
                "step0_prediction_cn": "0%不参与",
                "final_gate": {"can_new_entry": False},
                "has_personal_positions": False,
                "watch_anchor": {"name": "上海石化", "code": "600688", "sector": "炼化及贸"},
                "candidate_quality_panel_fields": {
                    "market_emotion_label": "0%不参与",
                    "account_attention_load": "无持仓负担",
                    "holding_priority_action": "无旧仓时只等参与窗口",
                    "daily_new_entry_limit": 0,
                    "primary_buy_candidate": {"name": "上海石化", "code": "600688"},
                    "backup_candidate": {"name": "上海石化", "code": "600688"},
                },
                "candidate_quality_samples": [
                    {"name": "上海石化", "code": "600688", "selection_quality": "中", "entry_cost_state": "确认中"},
                ],
                "sniper_target_derivation": {
                    "schema_version": "sniper_target_derivation.v1",
                    "canonical_target": {"name": "豫能控股", "code": "001896", "role": "观察对象"},
                    "steps": [
                        {
                            "step_id": "T0",
                            "label": "原始候选",
                            "source": "execution_stage_context.watch_anchor",
                            "candidate": {"name": "上海石化", "code": "600688"},
                            "role": "过程候选",
                            "decision": "被替换",
                            "reason": "最终解析未选为观察对象",
                        }
                    ],
                },
                "final_target_resolution": {
                    "watch_target": {"name": "豫能控股", "code": "001896", "sector": "电力"},
                },
            }
        )
        rendered = "\n".join(
            build_action_plan_candidate_quality_node(
                {
                    "candidate_quality_panel_fields": payload["candidate_quality_panel_fields"],
                    "candidate_quality_samples": payload["candidate_quality_samples"],
                    "sniper_target_derivation": payload["sniper_target_derivation"],
                    "enabled_node_keys": ["overview", "candidate_quality"],
                }
            )["lines"]
        )

        self.assertIn("| 补位对象 | 豫能控股(001896) |", rendered)
        self.assertIn("| 豫能控股(001896) |", rendered)
        self.assertIn("上海石化(600688): 过程候选 / 被替换", rendered)
        self.assertNotIn("| 补位对象 | 上海石化(600688) |", rendered)

    def test_candidate_quality_generated_panel_prefers_final_watch_target_over_stale_best_stock(self):
        from domains.execution_chain.pk_decision_nodes.candidate_quality_scorecard import (
            build_candidate_quality_scorecard_payload,
        )
        from report.action_plan_nodes import build_action_plan_candidate_quality_node

        payload = build_candidate_quality_scorecard_payload(
            {
                "trade_gate_open": False,
                "position_level": "0%不参与",
                "step0_prediction_cn": "0%不参与",
                "final_gate": {"can_new_entry": False},
                "has_personal_positions": False,
                "best_stock": {"name": "上海石化", "code": "600688", "sector": "炼化及贸"},
                "watch_anchor": {"name": "上海石化", "code": "600688", "sector": "炼化及贸"},
                "final_target_resolution": {
                    "watch_target": {"name": "豫能控股", "code": "001896", "sector": "电力"},
                },
            }
        )
        rendered = "\n".join(
            build_action_plan_candidate_quality_node(
                {
                    "candidate_quality_panel_fields": payload["candidate_quality_panel_fields"],
                    "candidate_quality_samples": payload["candidate_quality_samples"],
                    "sniper_target_derivation": payload["sniper_target_derivation"],
                    "enabled_node_keys": ["overview", "candidate_quality"],
                }
            )["lines"]
        )

        self.assertIn("| 补位对象 | 豫能控股(001896) |", rendered)
        self.assertIn("| 豫能控股(001896) |", rendered)
        self.assertNotIn("上海石化", rendered)

    def test_zero_participation_downgraded_anchor_sample_does_not_become_final_watch_target(self):
        resolution = report_runtime._build_runtime_final_target_resolution(
            data={},
            selected_position_candidate={
                "name": "大有能源",
                "code": "600403",
                "sector": "煤炭开采",
                "target_position_pct": 0,
                "anchor_reversal_decision": "降级观察",
                "candidate_role": "观察样本",
                "relationship_to_anchor": "未证明比兆易创新(603986)更值得参与",
                "final_action": "板块锚反推未通过，只观察承接，不新增参与",
            },
            position_decision={"signal_grade": "0", "target_position_pct": 0},
            market_research_snapshot={},
        )

        self.assertEqual("wait", resolution["capital_priority_decision"]["capital_priority"])
        self.assertEqual({}, resolution["watch_target"])

    def test_zero_position_extreme_candidate_without_front_observation_flag_stays_process_only(self):
        context = {
            "position_decision": {"target_position_pct": 0, "signal_grade": "0"},
            "extreme_conviction_list": [
                {
                    "name": "和远气体",
                    "code": "002971",
                    "sector": "化工原料",
                    "candidate_role": "板块锚",
                    "anchor_reversal_decision": "可作为主对象",
                    "attack_state": "0%不参与",
                    "planned_participation": {
                        "buy_window": "09:50-10:10",
                        "fallback_state": "不满足继续0%",
                    },
                }
            ],
        }

        selected = report_runtime._build_front_page_selected_position_candidate(context)
        resolved = report_runtime._resolve_front_page_target_candidate(
            data={},
            execution_stage_context=context,
            report_lines=["# report"],
            target_date="2026-06-11",
        )

        self.assertIsNone(selected)
        self.assertEqual({}, resolved)

    def test_zero_position_rejects_process_front_observation_candidate(self):
        context = {
            "position_decision": {"target_position_pct": 0, "signal_grade": "0"},
            "extreme_conviction_list": [
                {
                    "name": "和远气体",
                    "code": "002971",
                    "sector": "化工原料",
                    "front_observation_qualified": True,
                    "observation_layer": "process_observation",
                    "identity": "过程候选",
                    "candidate_role": "板块锚",
                    "anchor_reversal_decision": "可作为主对象",
                }
            ],
        }

        selected = report_runtime._build_front_page_selected_position_candidate(context)
        resolved = report_runtime._resolve_front_page_target_candidate(
            data={},
            execution_stage_context=context,
            report_lines=["# report"],
            target_date="2026-06-11",
        )

        self.assertIsNone(selected)
        self.assertEqual({}, resolved)

    def test_runtime_clears_stale_candidate_quality_panel_targets_after_empty_wait_resolution(self):
        stale_candidate = {
            "name": "大有能源",
            "code": "600403",
            "sector": "煤炭开采",
            "anchor_reversal_decision": "降级观察",
            "candidate_role": "观察样本",
        }
        context = {
            "candidate_quality_panel_fields": {
                "primary_buy_candidate": stale_candidate,
                "backup_candidate": stale_candidate,
                "daily_new_entry_limit": 0,
            }
        }

        report_runtime._clear_stale_candidate_quality_panel_targets(
            {
                "watch_target": {},
                "capital_priority_decision": {"capital_priority": "wait"},
            },
            context,
        )

        self.assertIsNone(context["candidate_quality_panel_fields"]["primary_buy_candidate"])
        self.assertIsNone(context["candidate_quality_panel_fields"]["backup_candidate"])

    def test_candidate_quality_panel_does_not_promote_downgraded_sample_when_final_watch_target_is_empty(self):
        from domains.execution_chain.pk_decision_nodes.candidate_quality_scorecard import (
            build_candidate_quality_scorecard_payload,
        )
        from report.action_plan_nodes import build_action_plan_candidate_quality_node

        payload = build_candidate_quality_scorecard_payload(
            {
                "trade_gate_open": False,
                "position_level": "0%不参与",
                "step0_prediction_cn": "0%不参与",
                "final_gate": {"can_new_entry": False},
                "has_personal_positions": False,
                "position_context_provided": True,
                "selected_position_candidate": {
                    "name": "大有能源",
                    "code": "600403",
                    "sector": "煤炭开采",
                    "target_position_pct": 0,
                    "anchor_reversal_decision": "降级观察",
                    "candidate_role": "观察样本",
                    "relationship_to_anchor": "未证明比兆易创新(603986)更值得参与",
                    "final_action": "板块锚反推未通过，只观察承接，不新增参与",
                },
                "final_target_resolution": {
                    "watch_target": {},
                    "capital_priority_decision": {"capital_priority": "wait"},
                },
            }
        )
        rendered = "\n".join(
            build_action_plan_candidate_quality_node(
                {
                    "candidate_quality_panel_fields": payload["candidate_quality_panel_fields"],
                    "candidate_quality_samples": payload["candidate_quality_samples"],
                    "sniper_target_derivation": payload["sniper_target_derivation"],
                    "enabled_node_keys": ["overview", "candidate_quality"],
                }
            )["lines"]
        )

        self.assertIn("| 主买对象 | 暂无 |", rendered)
        self.assertIn("| 补位对象 | 暂无 |", rendered)
        self.assertNotIn("| 补位对象 | 大有能源(600403) |", rendered)

    def test_candidate_quality_existing_panel_clears_stale_targets_when_final_watch_target_is_empty(self):
        from domains.execution_chain.pk_decision_nodes.candidate_quality_scorecard import (
            build_candidate_quality_scorecard_payload,
        )
        from report.action_plan_nodes import build_action_plan_candidate_quality_node

        stale_candidate = {
            "name": "大有能源",
            "code": "600403",
            "sector": "煤炭开采",
            "target_position_pct": 0,
            "anchor_reversal_decision": "降级观察",
            "candidate_role": "观察样本",
        }
        payload = build_candidate_quality_scorecard_payload(
            {
                "trade_gate_open": False,
                "position_level": "0%不参与",
                "step0_prediction_cn": "0%不参与",
                "final_gate": {"can_new_entry": False},
                "has_personal_positions": True,
                "position_context_provided": True,
                "candidate_quality_panel_fields": {
                    "market_emotion_label": "🚫 暂不跟随",
                    "account_attention_load": "有持仓需先处理",
                    "holding_priority_action": "先处理旧仓，再看新增",
                    "daily_new_entry_limit": 0,
                    "primary_buy_candidate": stale_candidate,
                    "backup_candidate": stale_candidate,
                    "forbidden_actions": ["亏损后补仓", "计划外追高"],
                    "ignored_noise_items": ["外盘大涨但A股未确认", "论坛情绪"],
                },
                "candidate_quality_samples": [stale_candidate],
                "final_target_resolution": {
                    "watch_target": {},
                    "capital_priority_decision": {"capital_priority": "wait"},
                },
            }
        )
        rendered = "\n".join(
            build_action_plan_candidate_quality_node(
                {
                    "candidate_quality_panel_fields": payload["candidate_quality_panel_fields"],
                    "candidate_quality_samples": payload["candidate_quality_samples"],
                    "sniper_target_derivation": payload["sniper_target_derivation"],
                    "enabled_node_keys": ["overview", "candidate_quality"],
                }
            )["lines"]
        )

        self.assertIn("| 主买对象 | 暂无 |", rendered)
        self.assertIn("| 补位对象 | 暂无 |", rendered)
        self.assertNotIn("| 主买对象 | 大有能源(600403) |", rendered)
        self.assertNotIn("| 补位对象 | 大有能源(600403) |", rendered)

    def test_candidate_quality_wait_resolution_blocks_bare_selected_candidate_from_panel_targets(self):
        from domains.execution_chain.pk_decision_nodes.candidate_quality_scorecard import (
            build_candidate_quality_scorecard_payload,
        )
        from report.action_plan_nodes import build_action_plan_candidate_quality_node

        degraded_sample = {
            "name": "大有能源",
            "code": "600403",
            "sector": "煤炭开采",
            "anchor_reversal_decision": "降级观察",
            "candidate_role": "观察样本",
            "candidate_layer": "watch_sample",
            "execution_eligibility": "observation_only",
        }
        payload = build_candidate_quality_scorecard_payload(
            {
                "trade_gate_open": False,
                "position_level": "0%不参与",
                "step0_prediction_cn": "🚫 暂不跟随",
                "final_gate": {"can_new_entry": False},
                "has_personal_positions": True,
                "position_context_provided": True,
                "selected_position_candidate": {"name": "大有能源", "code": "600403"},
                "watch_anchor": {"name": "大有能源", "code": "600403"},
                "display_observation_candidates": [degraded_sample],
                "final_target_resolution": {
                    "watch_target": {},
                    "capital_priority_decision": {"capital_priority": "wait"},
                },
            }
        )
        rendered = "\n".join(
            build_action_plan_candidate_quality_node(
                {
                    "candidate_quality_panel_fields": payload["candidate_quality_panel_fields"],
                    "candidate_quality_samples": payload["candidate_quality_samples"],
                    "sniper_target_derivation": payload["sniper_target_derivation"],
                    "enabled_node_keys": ["overview", "candidate_quality"],
                }
            )["lines"]
        )

        self.assertIn("| 主买对象 | 暂无 |", rendered)
        self.assertIn("| 补位对象 | 暂无 |", rendered)
        self.assertNotIn("| 主观察对象 | 大有能源(600403) |", rendered)
        self.assertNotIn("| 观察对象 | 大有能源(600403) |", rendered)

    def test_runtime_attack_preview_relabels_legacy_zero_appendix_lines(self):
        lines = [
            "**次日市场环境**: 0%不参与 / 防守态 - 先看环境，再决定是否保留观察权",
            "- ✅ 不新增参与：当前按0%不参与，固定交易窗口内条件未成立前只观察",
            "- **现在是什么情况**: 0%不参与不开新仓，个股结构未坏，但环境未开",
            "- **明天能不能开仓**: 0%不参与不开新仓，只保留高优先级观察权",
            "- **进攻仓位三态**: 0%不参与",
            "- **现在到底是什么状态**: 0%不参与，等待固定交易窗口内条件",
            "- **明天仓位放多少**: 0%新仓（只处理旧仓，不新增）",
            "- **明天具体怎么做**: 市场级原则是若你有旧仓就去弱留强，不新增参与",
            "**⛔ 当前先不开新仓**: 0%不参与，本轮不做PK出手结论。",
            "- 当前是0%不参与，本时段只确认主线核心是否在固定交易窗口内满足条件",
        ]

        normalized = report_runtime._normalize_attack_preview_appendix_lines(
            lines,
            selected_position_candidate={"code": "600726", "name": "华电能源"},
            position_decision={"signal_grade": "50", "target_position_pct": 50, "participation_mode": "attack_50_preview"},
        )
        rendered = "\n".join(normalized)

        self.assertIn("50%条件执行 / 防守态", rendered)
        self.assertIn("50%条件执行；固定交易窗口内条件成立才执行，不满足回到0%", rendered)
        self.assertIn("- **进攻仓位三态**: 50%条件执行", rendered)
        self.assertIn("当前是50%条件执行", rendered)
        self.assertIn("- **明天仓位放多少**: 50%条件执行；条件不成立回0%", rendered)
        self.assertIn("明日执行目标只按固定交易窗口处理", rendered)
        self.assertIn("**⚠️ 当前不抢跑**: 0%不参与，本轮只等待固定交易窗口条件。", rendered)
        self.assertNotIn("预计", rendered)
        self.assertNotIn("当前按0%不参与", rendered)
        self.assertNotIn("0%不参与不开新仓", rendered)
        self.assertNotIn("0%新仓", rendered)
        self.assertNotIn("不新增参与", rendered)
        self.assertNotIn("当前先不开新仓", rendered)
        self.assertNotIn("- **进攻仓位三态**: 0%不参与", rendered)

    def test_sanitize_report_lines_relabels_legacy_execution_framework_under_zero_participation(self):
        lines = [
            "| 明日结论 | 当前盈亏比 | 周期主线 | 当天主攻线 | 当前市场底色 | 唯一重点对象 | 明日执行风格 | 一句话动作 |",
            "|----------|------------|----------|------------|--------------|--------------|--------------|------------|",
            "| 0%不参与 | 不确定时不值得主动参与 | 半导体 | 半导体 | 先看市场基底 | 暂无 | 0%不参与 | 0%：没有合格标的就不参与 |",
            "- **怎么执行**: 日线结构中枢定环境，强核心走竞价表态、开盘前几分钟或回封；普通结构才等60分钟确认，30分钟定止损",
            "> **怎么执行**：先把价格区间和纪律定好，盘中只按“日线结构中枢定环境，强核心走竞价表态、开盘前几分钟或回封；普通结构才等60分钟确认，30分钟定止损”执行。",
            "- **执行节奏**: 日线结构中枢定环境，强核心走竞价表态、开盘前几分钟或回封；普通结构才等60分钟确认，30分钟定止损",
        ]

        rendered = "\n".join(report_runtime._sanitize_report_lines(lines))

        self.assertIn("最终0%时不按观察窗口执行，只观察指数图形、主攻线承接和观察对象是否重新成立。", rendered)
        self.assertIn("- **执行节奏**: 最终0%时不按观察窗口执行，只观察指数图形、主攻线承接和观察对象是否重新成立。", rendered)
        self.assertNotIn("强核心走竞价表态", rendered)
        self.assertNotIn("普通结构才等60分钟确认", rendered)

    def test_sanitize_report_lines_relabels_zero_schedule_process_candidate_wording(self):
        lines = [
            "| 明日结论 | 当前盈亏比 | 周期主线 | 当天主攻线 | 当前市场底色 | 唯一重点对象 | 明日执行风格 | 一句话动作 |",
            "|----------|------------|----------|------------|--------------|--------------|--------------|------------|",
            "| 0%不参与 | 不确定时不值得主动参与 | 半导体 | 半导体 | 先看市场基底 | 暂无 | 0%不参与 | 0%：没有合格标的就不参与 |",
            "- 观察唯一对象的竞价表态、匹配金额、委托稳定和板块同步",
            "- 若竞价表态和开盘前几分钟承接同时成立，按09:30-09:35窗口处理；不成立回到0%",
            "- 当前是0%不参与，本时段只确认主线核心是否在固定交易窗口内满足条件",
        ]

        rendered = "\n".join(report_runtime._sanitize_report_lines(lines))

        self.assertIn("只观察主攻线承接和过程样本反馈，不把竞价强弱转成新增参与", rendered)
        self.assertIn("也只记为过程证据；不新增参与", rendered)
        self.assertIn("当前是0%不参与，本时段只观察主线核心是否继续证明承接", rendered)
        self.assertNotIn("观察唯一对象", rendered)
        self.assertNotIn("按09:30-09:35窗口处理", rendered)
        self.assertNotIn("固定交易窗口内满足条件", rendered)

    def test_sanitize_report_lines_preserves_repeated_front_page_table_cells(self):
        repeated = (
            "Top20第20名128.51亿，Top20合计3842.81亿，占两市12.86%；"
            "资金集中在大成交趋势核心，作为Top50后的补充观察，只说明资金选择方向，不单独给参与资格。"
        )
        lines = [
            "## 二、市场基底",
            "| 指标 | 数值 | 解读 |",
            "|------|------|------|",
            f"| Top20成交容量 | 14/20只150亿级 | {repeated} |",
            "### 2. 市场状态结论",
            "| 项目 | 结论 | 依据 |",
            "|------|------|------|",
            f"| Top20成交容量 | 容量活跃 | {repeated} |",
            "## 八、详细附录",
            f"| 附录说明 | {repeated} |",
        ]

        rendered = "\n".join(report_runtime._sanitize_report_lines(lines))
        front_text, appendix_text = rendered.split("## 八、详细附录", 1)

        self.assertEqual(front_text.count(repeated), 2)
        self.assertNotIn("同类说明见上方，只看本行数值变化", front_text)
        self.assertIn(repeated, appendix_text)

    def test_sanitize_report_lines_marks_process_tables_as_evidence(self):
        lines = [
            "| 明日结论 | 当前盈亏比 | 周期主线 | 当天主攻线 | 当前市场底色 | 唯一重点对象 | 明日执行风格 | 一句话动作 |",
            "|----------|------------|----------|------------|--------------|--------------|--------------|------------|",
            "| 0%不参与 | 不确定时不值得主动参与 | 电力 | 电力 | 退潮 | 暂无 | 0%不参与 | 0%：只处理旧仓，不新增参与 |",
            "**主线内观察候选**:",
            "**明日次核心预判**（主线内备选观察）:",
            "**跨线观察候选**（只看能量迁移，不作为主线执行对象）:",
            "**重点观察名单**（只保留最心动的少数，每只都绑定固定交易窗口条件）:",
            "**逐只预判明日风险**（基于今日形态）:",
            "**明日风险分组**",
            "**明日观察位预计算表**:",
            "### 主线内观察候选",
            "**重点观察复核脚本**:",
            "**历史过程观察样本去向**（逐个复核，不把走坏样本混进明日执行观察样本）:",
            "##### 附录：# 今日总决策面板",
        ]

        rendered = "\n".join(report_runtime._sanitize_report_lines(lines))

        self.assertIn("**主线内观察候选**:（过程证据）", rendered)
        self.assertIn("**明日次核心预判**（主线内备选观察）:（过程证据）", rendered)
        self.assertIn("**跨线观察候选**（只看能量迁移，不作为主线执行对象）:（过程证据）", rendered)
        self.assertIn("**重点观察名单**（只保留最心动的少数，每只都绑定固定交易窗口条件）:（过程证据）", rendered)
        self.assertIn("**逐只预判明日风险**（基于今日形态）:（过程证据）", rendered)
        self.assertIn("**明日风险分组**（过程证据）", rendered)
        self.assertIn("**明日观察位预计算表**:（过程证据）", rendered)
        self.assertIn("### 主线内观察候选（过程证据）", rendered)
        self.assertIn("**重点观察复核脚本**:（过程证据）", rendered)
        self.assertIn("**历史过程观察样本去向**（逐个复核，不把走坏样本混进明日执行观察样本）:（过程证据）", rendered)
        self.assertIn("##### 附录：# 今日总决策面板（过程证据）", rendered)

    def test_sanitize_report_lines_relabels_conditional_buy_plan_under_zero_with_observation_target(self):
        lines = [
            "| 明日结论 | 当前盈亏比 | 周期主线 | 当天主攻线 | 当前市场底色 | 唯一重点对象 | 明日执行风格 | 一句话动作 |",
            "|----------|------------|----------|------------|--------------|--------------|--------------|------------|",
            "| 0%不参与 | 不确定时不值得主动参与 | 半导体 | 半导体 | 先看市场基底 | 条件观察：605111 新洁能（半导体） | 0%不参与 | 盘前0%；09:50-10:10站上63.22且板块承接不塌，才评估50%条件执行；不满足继续0% |",
            "- **怎么执行**: 日线结构中枢定环境，强核心走竞价表态、开盘前几分钟或回封；普通结构才等60分钟确认，30分钟定止损",
            "- **执行节奏**: 日线结构中枢定环境，强核心走竞价表态、开盘前几分钟或回封；普通结构才等60分钟确认，30分钟定止损",
            "- **明天仓位放多少**: 盘前0%；参与窗口命中后才评估50%条件执行",
            "| 10:00左右买 | 新洁能站上63.22且板块承接不塌 | 50%条件执行 | 买后用60.06做失效 | 不满足继续0% |",
            "| 候选 | 账户状态 | 当前持仓 | 可卖数量 | 选股质量 | 买点质量 | 动作上限 | 新开仓动作 |",
            "| 新洁能(605111) | 实际可买 | 0 | 0 | 中 | 等确认 | 补位 | 触发后50%条件执行 |",
        ]

        rendered = "\n".join(report_runtime._sanitize_report_lines(lines))

        self.assertIn("观察对象：605111 新洁能（半导体）", rendered)
        self.assertIn("只观察605111 新洁能（半导体），成立才保留观察；未出现执行资格前不新增参与；不满足继续0%", rendered)
        self.assertIn("- **明天仓位放多少**: 盘前0%；暂无新增参与资格，只观察风险是否钝化", rendered)
        self.assertNotIn("参与窗口命中", rendered)
        self.assertIn("| 09:50-10:10 | 新洁能站上63.22且板块承接不塌 | 只观察 | 买后用60.06做失效 | 不满足继续0% |", rendered)
        self.assertIn("| 新洁能(605111) | 仅观察 | 0 | 0 | 中 | 等确认 | 观察 | 触发后只观察 |", rendered)
        self.assertIn("最终0%时不按观察窗口执行", rendered)
        self.assertNotIn("主观察对象", rendered)
        self.assertNotIn("条件50", rendered)
        self.assertNotIn("50%条件执行", rendered)
        self.assertNotIn("才评估50%", rendered)

    def test_sanitize_report_lines_relabels_tomorrow_action_soft_words_under_zero_participation(self):
        lines = [
            "| 明日结论 | 当前盈亏比 | 周期主线 | 当天主攻线 | 当前市场底色 | 唯一重点对象 | 明日执行风格 | 一句话动作 |",
            "|----------|------------|----------|------------|--------------|--------------|--------------|------------|",
            "| 0%不参与 | 不确定时不值得主动参与 | 半导体 | 半导体 | 先看市场基底 | 暂无 | 0%不参与 | 0%：没有合格标的就不参与 |",
            "| 明日核心标的 | 1+0 / 4只 |",
            "| PK决胜局（期望值模型） | 1+0 / 4只 |",
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
            "**⛔ 当前先不开新仓**: 0%不参与，本轮不做PK出手结论。",
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
        self.assertIn("| 过程核心样本回放 | 1+0 / 4只 |", rendered)
        self.assertIn("| 过程候选最终复核 | 无当前对象；个股仅保留在过程候选回放 |", rendered)
        self.assertIn("无新增参与止损", rendered)
        self.assertIn("非电风扇不在14:30-14:55新增参与", rendered)
        self.assertIn("| 明日观察位预计算 | 不新增参与，只保留候选观察样本 |", rendered)
        self.assertIn("真允许参与时，只保留唯一动作；不允许时，只保留观察。", rendered)
        self.assertIn("当前先不新增参与", rendered)
        self.assertIn("本轮不做参与结论", rendered)
        self.assertIn("大盘环境没有给到参与条件", rendered)
        self.assertIn("降低明日主动参与预期", rendered)
        self.assertIn("本轮不做参与结论", rendered)
        self.assertIn("| 09:50-10:10 | 暂无唯一对象，不做新增参与 | 无 | 无新增参与止损 | 不做 |", rendered)
        self.assertIn("不把局部强势当成参与资格", rendered)
        self.assertIn("**最终动作表**（只展示真正具备参与资格的对象）:", rendered)
        self.assertIn("无需设置新增参与止损", rendered)
        self.assertIn("未参与的保持观望", rendered)
        self.assertIn("不能因为MA3/MA5/MA10单独参与", rendered)
        self.assertIn("不是所有股票的观察理由", rendered)
        self.assertIn("| 入选日 | 股票 | 代码 | 排名 | 所属方向 | 观察位窗口 | 复盘状态 | 历史复盘动作 | 作废线 | 记录ID |", rendered)
        self.assertIn("| 主观察对象 | 风华高科(000636) |", rendered)
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
        self.assertNotIn("明日核心标的", rendered)
        self.assertNotIn("PK决胜局", rendered)
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

    def test_zero_participation_relabels_extreme_tracking_as_historical_process(self):
        lines = [
            "| 明日结论 | 当前盈亏比 | 周期主线 | 当天主攻线 | 当前市场底色 | 唯一重点对象 | 明日执行风格 | 一句话动作 |",
            "|----------|------------|----------|------------|--------------|--------------|--------------|------------|",
            "| 0%不参与 | 不确定时不值得主动参与 | 半导体 | 半导体 | 先看市场基底 | 暂无 | 0%不参与 | 0%：没有合格标的就不参与 |",
            "**明日极度看好近25日跟踪表**（按入选日展示，排除A杀样本）:",
            "#### 附录A：明日极度看好列表",
        ]

        rendered = "\n".join(report_runtime._sanitize_report_lines(lines))

        self.assertIn("**历史过程复盘：明日极度看好近25日跟踪表**", rendered)
        self.assertIn("#### 附录A：历史过程观察列表（原明日极度看好）", rendered)

    def test_zero_participation_relabels_step2_core_target_words_as_process_replay(self):
        lines = [
            "| 明日结论 | 当前盈亏比 | 周期主线 | 当天主攻线 | 当前市场底色 | 唯一重点对象 | 明日执行风格 | 一句话动作 |",
            "|----------|------------|----------|------------|--------------|--------------|--------------|------------|",
            "| 0%不参与 | 不确定时不值得主动参与 | 半导体 | 半导体 | 先看市场基底 | 暂无 | 0%不参与 | 0%：没有合格标的就不参与 |",
            "- **接着做什么**: 进入Step 2，从观察池识别明日核心标的",
            "##### 附录：Step 2 - 明日核心标的",
        ]

        rendered = "\n".join(report_runtime._sanitize_report_lines(lines))

        self.assertIn("- **接着做什么**: 进入Step 2，从观察池回放过程观察样本", rendered)
        self.assertIn("##### 附录：Step 2 - 过程观察样本", rendered)
        self.assertNotIn("明日核心标的", rendered)

    def test_zero_participation_relabels_pk_stage_title_as_process_review(self):
        lines = [
            "| 明日结论 | 当前盈亏比 | 周期主线 | 当天主攻线 | 当前市场底色 | 唯一重点对象 | 明日执行风格 | 一句话动作 |",
            "|----------|------------|----------|------------|--------------|--------------|--------------|------------|",
            "| 0%不参与 | 不确定时不值得主动参与 | 半导体 | 半导体 | 先看市场基底 | 暂无 | 0%不参与 | 0%：没有合格标的就不参与 |",
            "##### 附录：Step 5 - PK决胜局（期望值模型）",
        ]

        rendered = "\n".join(report_runtime._sanitize_report_lines(lines))

        self.assertIn("##### 附录：Step 5 - 过程候选最终复核", rendered)
        self.assertNotIn("PK决胜局", rendered)

    def test_zero_opening_verdict_does_not_name_single_process_candidate(self):
        payload = report_runtime.build_two_layer_decision_payload(
            target_date="2026-06-23",
            final_target_resolution={},
            position_decision={"target_position_pct": 0},
            execution_stage_context={
                "selection_workflow": {
                    "schema_version": "selection_workflow.v1",
                    "final": {
                        "position_pct": 0,
                        "execution_object": {},
                        "action_text": "0%不参与",
                        "reason": "最终没有新增参与对象",
                    },
                },
                "waiting_stocks": [
                    {
                        "name": "长裕集团",
                        "code": "603407",
                        "stock": {"name": "长裕集团", "code": "603407"},
                        "why_watch": "T字板分歧转一致，明日可能加速+放量+板块前排",
                    }
                ],
            },
        )

        rendered = "\n".join(report_runtime.render_front_decision_layer(payload))

        self.assertIn(
            "| 推导摘要 | 没有可用明日执行对象；过程候选只保留在后文复盘表，不在首屏指定个股；资金载体差异复核对象不覆盖最终动作；最终不新增参与 |",
            rendered,
        )
        summary_line = next(line for line in rendered.splitlines() if line.startswith("| 推导摘要 |"))
        self.assertNotIn("长裕集团", summary_line)

    def test_insert_sector_capital_preflight_front_summary_places_tournament_before_execution_section(self):
        payload = {
            "schema_version": "sector_capital_preflight.v1",
            "final_action": {
                "label": "0%不参与",
                "source": "selection_workflow.final",
                "reason": "最终没有新增参与对象，动作=0%不参与",
            },
            "layers": [
                {
                    "id": "market_capital_structure",
                    "title": "市场资金结构",
                    "input_count": 1,
                    "eliminated_count": 1,
                    "survivor_count": 0,
                    "eliminated": [{"stock_label": "和远气体(002971)", "risk_evidence": "炸板57次且尾盘才回封"}],
                    "survivors": [],
                }
            ],
        }
        report_lines = ["# 标题", "", "## 明日执行结论", "**T-001**"]

        inserted = report_runtime._insert_sector_capital_preflight_front_summary(report_lines, payload)
        rendered = "\n".join(inserted)

        self.assertIn("## 板块资金扩散淘汰赛", rendered)
        self.assertLess(rendered.index("## 板块资金扩散淘汰赛"), rendered.index("## 明日执行结论"))

    def test_zero_preflight_renders_capital_carrier_as_review_not_paper_action(self):
        payload = {
            "schema_version": "sector_capital_preflight.v1",
            "final_action": {
                "label": "0%不参与",
                "position_pct": 0,
                "target": {},
                "source": "selection_workflow.final",
                "reason": "最终没有新增参与对象，动作=0%不参与",
            },
            "layers": [
                {
                    "id": "final_action",
                    "title": "唯一明日动作",
                    "input_count": 1,
                    "eliminated_count": 0,
                    "survivor_count": 0,
                    "survivors": [],
                    "eliminated": [],
                }
            ],
            "sector_capital_carrier_strategy": {
                "action": "paper_participate",
                "action_label": "板块资金载体主样本",
                "action_reason": "板块被资金选择，且主样本同时具备至少两类资金载体证据",
                "primary_candidate": {"stock_label": "长电科技(600584)"},
                "stages": [
                    {
                        "title": "纸面动作",
                        "input_count": 29,
                        "eliminated_count": 28,
                        "survivor_count": 1,
                        "survivors": [
                            {
                                "label": "长电科技(600584)",
                                "reason": "板块被资金选择，且主样本同时具备至少两类资金载体证据",
                            }
                        ],
                    }
                ],
            },
        }

        rendered = "\n".join(report_runtime._render_sector_capital_preflight_front_summary(payload))

        self.assertIn("## 板块资金载体差异复核", rendered)
        self.assertIn("| T0同源策略动作 | 差异复核，不新增参与 |", rendered)
        self.assertIn("| 复核样本 | 长电科技(600584) |", rendered)
        self.assertIn("| 复核环节 | 输入 | 排除 | 记录证据数 | 代表复核事实 |", rendered)
        self.assertIn("| 处理结果 | 不进入明日对象：只作为差异复核记录，不新增参与 |", rendered)
        self.assertIn("| 依据 | 板块被资金选择，且复核样本同时具备至少两类资金载体证据 |", rendered)
        self.assertIn("| 差异复核收口 | 29 | 28 | 1 | 长电科技(600584)：板块被资金选择", rendered)
        self.assertIn("只作差异复核，不进入明日对象", rendered)
        self.assertNotIn("## 板块资金载体预案", rendered)
        self.assertNotIn("主样本", rendered)
        self.assertNotIn("纸面动作", rendered)

    def test_insert_sector_capital_preflight_front_summary_syncs_front_tables_when_action_is_positive(self):
        payload = {
            "schema_version": "sector_capital_preflight.v1",
            "final_action": {
                "label": "50%条件执行",
                "position_pct": 50,
                "target": {"name": "长电科技", "code": "600584", "sector": "半导体"},
                "source": "sector_capital_carrier_strategy",
                "reason": "板块被资金选择，且主样本同时具备至少两类资金载体证据",
            },
            "layers": [
                {
                    "id": "final_action",
                    "title": "唯一明日动作",
                    "input_count": 1,
                    "survivor_count": 1,
                    "entries": [{"stock_label": "长电科技(600584)", "status": "final_action"}],
                }
            ],
        }
        report_lines = [
            "# 标题",
            "",
            "## 日报裁决总览",
            "| 项目 | 结论 |",
            "|------|------|",
            "| 仓位姿态 | 0%不参与 |",
            "| 最终对象 | 无 |",
            "| 对象性质 | 无明日执行对象 |",
            "| 推导摘要 | 没有可用明日执行对象 |",
            "",
            "## 明日执行结论",
            "| 项目 | 结论 |",
            "|------|------|",
            "| 明日仓位 | 0%不参与 |",
            "| 明日执行对象 | 无 |",
            "| 执行性质 | 无明日执行对象 |",
            "| 不满足条件 | 不参与 |",
        ]

        inserted = report_runtime._insert_sector_capital_preflight_front_summary(report_lines, payload)
        rendered = "\n".join(inserted)

        self.assertIn("| 仓位姿态 | 50%条件执行；固定交易窗口条件不成立回到0% |", rendered)
        self.assertIn("| 最终对象 | 明日执行对象：长电科技(600584) |", rendered)
        self.assertIn("| 明日仓位 | 条件满足才50%条件执行；不满足回到0% |", rendered)
        self.assertIn("| 明日执行对象 | 长电科技(600584) |", rendered)

    def test_insert_sector_capital_preflight_front_summary_replaces_stale_existing_section(self):
        payload = {
            "schema_version": "sector_capital_preflight.v1",
            "final_action": {
                "label": "50%条件执行",
                "position_pct": 50,
                "target": {"name": "长电科技", "code": "600584", "sector": "半导体"},
                "source": "sector_capital_carrier_strategy",
                "reason": "板块被资金选择，且主样本同时具备至少两类资金载体证据",
            },
            "layers": [
                {
                    "id": "final_action",
                    "title": "唯一明日动作",
                    "input_count": 1,
                    "survivor_count": 1,
                    "survivors": [{"stock_label": "长电科技(600584)", "status": "final_action"}],
                    "entries": [{"stock_label": "长电科技(600584)", "status": "final_action"}],
                }
            ],
        }
        report_lines = [
            "# 标题",
            "",
            "## 日报裁决总览",
            "| 项目 | 结论 |",
            "|------|------|",
            "| 仓位姿态 | 0%不参与 |",
            "| 最终对象 | 无 |",
            "",
            "## 板块资金扩散淘汰赛",
            "| 层级 | 输入 | 淘汰 | 剩余 | 关键理由 | 下一层依据 |",
            "|---|---:|---|---|---|---|",
            "| 唯一明日动作 | 1 | 0 | 0（无） | 旧结论 | 收口到最终动作 |",
            "",
            "## 明日执行结论",
            "| 项目 | 结论 |",
            "|------|------|",
            "| 明日仓位 | 0%不参与 |",
            "| 明日执行对象 | 无 |",
        ]

        inserted = report_runtime._insert_sector_capital_preflight_front_summary(report_lines, payload)
        rendered = "\n".join(inserted)

        self.assertNotIn("旧结论", rendered)
        self.assertIn("| 仓位姿态 | 50%条件执行；固定交易窗口条件不成立回到0% |", rendered)
        self.assertIn("| 明日执行对象 | 长电科技(600584) |", rendered)
        self.assertIn("| 唯一明日动作 | 1 | 0 | 1（长电科技(600584)）", rendered)

    def test_zero_appendix_clears_candidate_quality_panel_targets_when_final_wait_has_no_target(self):
        lines = [
            "| 明日结论 | 当前盈亏比 | 周期主线 | 当天主攻线 | 当前市场底色 | 唯一重点对象 | 明日执行风格 | 一句话动作 |",
            "|----------|------------|----------|------------|--------------|--------------|--------------|------------|",
            "| 0%不参与 | 不确定时不值得主动参与 | 半导体 | 半导体 | 先看市场基底 | 暂无 | 0%不参与 | 0%：没有合格标的就不参与 |",
            "##### 附录：# 今日总决策面板",
            "| 字段 | 内容 |",
            "|------|------|",
            "| 市场情绪状态 | 🚫 暂不跟随 |",
            "| 主买对象 | 暂无 |",
            "| 补位对象 | 大有能源(600403) |",
            "",
            "##### 附录：# 候选主表",
            "| 候选 | 账户状态 | 选股质量 | 买点质量 | 动作上限 | 新开仓动作 |",
            "|------|------|------|------|------|------|",
            "| 大有能源(600403) | 实际可买 | 中 | 等确认 | 补位 | 只观察，不新增参与 |",
            "",
            "##### 附录：# 候选选股轨迹",
            "| 层级 | 候选 | 主线/板块 | 为什么进入这一层 | 卡点 | 明日动作 |",
            "|------|------|------|------|------|------|",
            "| 观察层 | 大有能源(600403) | 半导体/煤炭开采 | 大有能源：市场条件未满足 | 市场条件未满足 | 关键数据不完整，停止生成动作 |",
            "",
            "##### 附录：# 候选选股轨迹明细",
            "| 层级 | 候选 | 来源池 | 主线/板块 | 分支结果 | 明日动作 |",
            "|------|------|------|------|------|------|",
            "| 观察层 | 大有能源(600403) | watch_anchor | 半导体/煤炭开采 | 市场条件未满足 | 关键数据不完整，停止生成动作 |",
        ]

        normalized = report_runtime._normalize_attack_preview_appendix_lines(
            lines,
            final_target_resolution={
                "watch_target": {},
                "capital_priority_decision": {"capital_priority": "wait"},
            },
        )
        rendered = "\n".join(report_runtime._sanitize_report_lines(normalized))

        self.assertIn("| 当前执行对象 | 暂无 |", rendered)
        self.assertIn("| 过程回看样本 | 见候选主表（过程证据） |", rendered)
        self.assertNotIn("| 主观察对象 |", rendered)
        self.assertNotIn("| 观察对象 |", rendered)
        self.assertNotIn("| 主观察对象 | 大有能源(600403) |", rendered)
        self.assertNotIn("| 观察对象 | 大有能源(600403) |", rendered)
        self.assertIn("| 候选 | 对象口径 | 账户状态 | 选股质量 | 观察位质量 | 观察上限 | 新增参与动作 |", rendered)
        self.assertIn("| 大有能源(600403) | 过程样本，非当前对象 | 仅观察 | 中 | 等确认 | 观察 | 只作过程回放，不新增参与 |", rendered)
        self.assertIn("| 过程样本 | 大有能源(600403) | 半导体/煤炭开采 | 大有能源：市场条件未满足；最终对象为空，本行只解释为什么曾进入筛选 | 市场条件未满足 | 只作过程回放，不新增参与 |", rendered)
        self.assertIn("| 过程样本 | 大有能源(600403) | watch_anchor | 半导体/煤炭开采 | 市场条件未满足；最终对象为空，本行只作筛选回放 | 只作过程回放，不新增参与 |", rendered)

    def test_zero_appendix_removes_current_object_wording_from_action_plan_when_final_wait_has_no_target(self):
        lines = [
            "##### 附录：明日操作计划",
            "| 今日关注标的 | 和远气体(002971)：观察对象，先观察强弱与承接 |",
            "| 明天观察池 | 和远气体(002971)：观察对象，先观察强弱与承接 |",
            "**先看顺序**（优先盯最能反映主线承接的对象）:",
            "- 👀 和远气体(002971) - 观察对象，09:50-10:10观察价待盘中确认",
            "- **跨线继续看谁**: 康强电子(002119) - 09:50-10:10观察价待盘中确认",
            "**观察优先对象**: 和远气体(002971)",
            "**最终动作表**（只展示真正具备参与资格的对象）:",
            "| 明天具体怎么做 | 股票 | 代码 | 触发条件 | 止损/时间 |",
            "|----------|------|------|----------|-----------|",
            "| ⏳ 确认后执行预案 | 和远气体 | 002971 | 09:50-10:10站上52.75 | 50.11 |",
            "##### 附录：# 今日总决策面板",
            "| 字段 | 内容 |",
            "|------|------|",
            "| 主观察对象 | 康强电子(002119) |",
            "| 观察对象 | 康强电子(002119) |",
        ]

        normalized = report_runtime._normalize_attack_preview_appendix_lines(
            lines,
            final_target_resolution={
                "watch_target": {},
                "capital_priority_decision": {"capital_priority": "wait"},
            },
        )
        rendered = "\n".join(report_runtime._sanitize_report_lines(normalized))

        self.assertIn("| 今日关注标的 | 无当前对象；个股仅保留在过程候选回放 |", rendered)
        self.assertIn("| 明天观察池 | 无当前对象；个股仅保留在过程候选回放 |", rendered)
        self.assertIn("- 👀 和远气体(002971) - 过程候选", rendered)
        self.assertIn("- **跨线回看样本**: 康强电子(002119)", rendered)
        self.assertIn("**观察优先对象**: 暂无", rendered)
        self.assertIn("| 暂无执行预案 | - | - | 当前最终对象为空，只回放过程候选，不新增参与 | - |", rendered)
        self.assertIn("| 当前执行对象 | 暂无 |", rendered)
        self.assertIn("| 过程回看样本 | 见候选主表（过程证据） |", rendered)
        self.assertNotIn("| 主观察对象 |", rendered)
        self.assertNotIn("| 观察对象 |", rendered)
        self.assertNotIn("| 主观察对象 | 康强电子(002119) |", rendered)
        self.assertNotIn("| 观察对象 | 康强电子(002119) |", rendered)

    def test_zero_appendix_removes_current_object_when_wait_has_watch_target_but_zero_position(self):
        lines = [
            "##### 附录：明日操作计划",
            "| 今日关注标的 | 和远气体(002971)：观察对象，先观察强弱与承接 |",
            "| 明天观察池 | 和远气体(002971)：观察对象，先观察强弱与承接 |",
            "**先看顺序**（优先盯最能反映主线承接的对象）:",
            "- 👀 和远气体(002971) - 观察对象，09:50-10:10观察价待盘中确认",
            "- **跨线继续看谁**: 康强电子(002119) - 09:50-10:10观察价待盘中确认",
            "**观察优先对象**: 和远气体(002971)",
            "**最终动作表**（只展示真正具备参与资格的对象）:",
            "| 明天具体怎么做 | 股票 | 代码 | 触发条件 | 止损/时间 |",
            "|----------|------|------|----------|-----------|",
            "| ⏳ 确认后执行预案 | 和远气体 | 002971 | 09:50-10:10站上52.75 | 50.11 |",
            "##### 附录：# 今日总决策面板",
            "| 字段 | 内容 |",
            "|------|------|",
            "| 主观察对象 | 康强电子(002119) |",
            "| 观察对象 | 康强电子(002119) |",
        ]

        normalized = report_runtime._normalize_attack_preview_appendix_lines(
            lines,
            position_decision={"target_position_pct": 0, "signal_grade": "0"},
            final_target_resolution={
                "watch_target": {"name": "和远气体", "code": "002971", "sector": "化学制品"},
                "capital_priority_decision": {
                    "capital_priority": "wait",
                    "reason": "空仓等待，禁止参与",
                },
            },
        )
        rendered = "\n".join(report_runtime._sanitize_report_lines(normalized))

        self.assertIn("| 今日关注标的 | 无当前对象；个股仅保留在过程候选回放 |", rendered)
        self.assertIn("| 明天观察池 | 无当前对象；个股仅保留在过程候选回放 |", rendered)
        self.assertIn("- 👀 和远气体(002971) - 过程候选", rendered)
        self.assertIn("- **跨线回看样本**: 康强电子(002119)", rendered)
        self.assertIn("**观察优先对象**: 暂无", rendered)
        self.assertIn("| 暂无执行预案 | - | - | 当前最终对象为空，只回放过程候选，不新增参与 | - |", rendered)
        self.assertIn("| 当前执行对象 | 暂无 |", rendered)
        self.assertIn("| 过程回看样本 | 见候选主表（过程证据） |", rendered)
        self.assertNotIn("| 主观察对象 |", rendered)
        self.assertNotIn("| 观察对象 |", rendered)
        self.assertNotIn("| 最终对象 | 观察对象：和远气体(002971) |", rendered)
        self.assertNotIn("| 主观察对象 | 康强电子(002119) |", rendered)
        self.assertNotIn("| 观察对象 | 康强电子(002119) |", rendered)

    def test_sanitize_does_not_align_observation_anchor_over_positive_execution_object(self):
        lines = [
            "## 明日账户建议",
            "| 项目 | 结论 |",
            "|------|------|",
            "| 明日仓位 | 条件满足才50%条件执行；不满足回到0% |",
            "| 明日执行目标 | 太极实业(600667)：固定交易窗口条件 |",
            "| 观察对象 | 太极实业(600667)：仅作观察对象 |",
            "## 八、详细附录",
            "**先看顺序**（优先盯最能反映主线承接的对象）:",
            "- 👀 通鼎互联(002491) - 跨线回看样本，09:50-10:10观察价31.58",
            "跨线对象（通信设备），只用于观察强弱，不代表主攻线切换。",
        ]

        rendered = "\n".join(report_runtime._sanitize_report_lines(lines))

        self.assertIn("- 👀 通鼎互联(002491) - 跨线回看样本", rendered)
        self.assertNotIn("- 👀 太极实业(600667)：仅作观察对象 - 跨线回看样本", rendered)

    def test_sanitize_report_lines_relabels_new_candidate_table_when_old_position_has_zero_new_entry(self):
        lines = [
            "## 明日账户建议",
            "| 项目 | 结论 |",
            "|------|------|",
            "| 账户约束 | 1w本金；已有昨日持仓优先处理 |",
            "| 明日动作 | 先处理旧仓，不新增参与 |",
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

        self.assertIn("| 主观察对象 | 华天科技(002185) |", rendered)
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
            "| 0%不参与 | 不确定时不值得主动参与 | 半导体 | 半导体 | 先看市场基底 | 暂无 | 0%不参与 | 0%：没有合格标的就不参与 |",
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
            "| 0%不参与 | 不确定时不值得主动参与 | 半导体 | 半导体 | 先看市场基底 | 暂无 | 0%不参与 | 0%：没有合格标的就不参与 |",
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
                    "- **明天仓位放多少**: 盘前0%；参与窗口命中后才评估50%条件执行",
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
                "position_level": "0%不参与",
                "position_reason": "放量下跌，先防踩踏",
                "final_gate": {
                    "final_action": "空仓等待",
                    "operation_state": "撤退态",
                    "can_new_entry": False,
                    "should_reduce": True,
                },
                "environment_display": {"position_level": "0%不参与", "operation_state": "撤退态"},
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
        self.assertIn("| 观察对象 | 暂无 |", rendered)
        self.assertIn("| 进攻仓位三态 | 0% |", rendered)
        self.assertIn("| 明日最大仓位 | 0% |", rendered)
        self.assertIn("| 0%不参与 |", rendered)
        self.assertIn("| 进攻仓位三态 | 0% |", rendered)
        self.assertIn("放量杀跌里的局部逆势活跃", rendered)
        self.assertNotIn("| 50%条件执行，只做合格对象 |", rendered)
        self.assertNotIn("- **进攻仓位三态**: 50%条件执行", rendered)
        self.assertNotIn("最终执行条件: 明日目标标的保留50%条件执行", stdout.getvalue())



if __name__ == "__main__":
    unittest.main()
