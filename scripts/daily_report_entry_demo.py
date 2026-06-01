#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# 强制无缓冲输出，确保日志实时显示
import sys
import os

# 方法1: 设置环境变量
os.environ['PYTHONUNBUFFERED'] = '1'

# 方法2: 重新配置stdout
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True)
else:
    sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 1)

# 方法3: 强制stderr也无缓冲
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(line_buffering=True)
else:
    sys.stderr = os.fdopen(sys.stderr.fileno(), 'w', 1)

_POSTGRES_ONLY_RUNTIME = False

"""
A股日报数据获取入口 - 严格按照SKILL.md声明使用数据源（2026-03-31重写版）

严格按照SKILL.md中声明的数据源优先级调用：
0. 基础市场事实与 snap-ui public data：Tushare-first；AkShare / iwencai 仅作为 fallback only
1. 热度前十个股：Tushare ths_hot 热股（首选）→ 本地同花顺脚本 / 腾讯财经热股排行（备用）
2. 板块热榜：Tushare ths_hot 概念板块/行业板块（首选）→ 本地同花顺板块脚本（兜底）
3. 指数数据：Tushare index_daily（首选）→ AkShare / 同花顺问财 / 历史K线（兜底）
4. 两市成交额：Tushare daily amount（首选）→ AkShare / 同花顺问财（兜底）
5. 涨停跌停数据：Tushare limit_list_ths / limit_list_d（首选）→ akshare涨停跌停池（兜底）
6. 行业资金流向：Tushare moneyflow_ind_ths（首选）→ 腾讯财经板块资金流向（兜底）
7. 板块涨跌幅排行：Tushare ths_index + ths_daily（首选）→ 同花顺问财/AkShare/Tencent（兜底）
8. 成交额排名：Tushare daily amount（首选）→ 东方财富 / 同花顺问财 / AkShare（兜底）
9. 预期日历：财联社预期日历（CLS接口，封装在 TencentFinanceData.get_calendar_events）
10. 选股通异动：选股通盘中异动分析
11. 顽主杯热门前十：顽主杯API
12. 龙虎榜数据：Tushare top_list（首选）→ finshare龙虎榜接口（兜底）
13. 新股日历：Tushare new_share（首选）→ Sina 新股日历 / 本地解析（兜底）

使用方法：
    python3 daily_report_entry_demo.py [YYYY-MM-DD]
    默认获取昨天数据
"""

import sys
import os
import datetime
import types
import time
import signal
import threading
from enum import Enum
from pathlib import Path

# 添加项目脚本路径，用于导入量化交易系统
sys.path.insert(0, '/Users/chaixixi/WorkBuddy/Claw/scripts')

# ============================================================
# 量化交易系统（价格结构+箱体辅助方案）
# ============================================================
try:
    from quant_trading_system import (
        analyze_buy_signal,
        check_sell_signal,
        format_step4_report,
        step4_quantitative_analysis,
        TradeSignal
    )
    QUANT_SYSTEM_AVAILABLE = True
except ImportError as e:
    print(f"[警告] 量化交易系统加载失败: {e}")
    QUANT_SYSTEM_AVAILABLE = False

import daily_report_analysis_utils as analysis_utils
import daily_report_markdown_hooks as markdown_hooks
from daily_report_render import (
    _get_report_output_path,
    _get_stock_diagnostic_output_path,
    _inject_report_variant_banner,
    _render_report_with_display_mode,
    build_report_outputs,
    build_report_preflight,
    finalize_run_log_text,
    render_report_preflight_lines,
    ReportCriticalDataMissingError,
    save_report_output,
    save_report_outputs,
    save_stock_diagnostic_output,
)
from daily_report_snapshot_io import (
    _get_snapshot_path as run_get_snapshot_path,
    _save_data_snapshot,
    add_supplementary_perspective,
    load_data_snapshot,
)
from decision.runtime_contracts import (
    get_trade_permission_contract,
    resolve_environment_display_contract,
    resolve_environment_reason_contract,
)
from domains.calendar_events.infer import (
    ai_analyze_event_sectors as run_ai_analyze_event_sectors,
    analyze_event_sector as run_analyze_event_sector,
    llm_analyze_event as run_llm_analyze_event,
    minimal_fallback_analysis as run_minimal_fallback_analysis,
)
from domains.watch_candidates.infer import (
    build_abnormal_watch_pool as run_build_abnormal_watch_pool,
)
from domains.market_activity.report_sections import (
    build_advanced_activity_report_sections,
    build_market_activity_report_sections,
)
from domains.market_activity.support import (
    get_stock_sector as run_get_stock_sector,
    get_stock_status as run_get_stock_status,
)
from domains.market_state.runtime import run_market_state_analysis
from domains.market_state.support import (
    _extract_market_breadth_snapshot as run_extract_market_breadth_snapshot,
    build_market_style_switch_snapshot as run_build_market_style_switch_snapshot,
    build_market_state_machine_snapshot as run_build_market_state_machine_snapshot,
    build_unified_sector_strength_rows as run_build_unified_sector_strength_rows,
    calculate_exit_price_lines as run_calculate_exit_price_lines,
    derive_mainline_pulse_snapshot as run_derive_mainline_pulse_snapshot,
    get_mainline_star_level as run_get_mainline_star_level,
    get_sector_core_hot_stock as run_get_sector_core_hot_stock,
    get_sector_leader as run_get_sector_leader,
    get_sector_hotlist_weight as run_get_sector_hotlist_weight,
    load_recent_market_turnover_history as run_load_recent_market_turnover_history,
    load_recent_sector_flow_history as run_load_recent_sector_flow_history,
    normalize_flow_to_yi as run_normalize_flow_to_yi,
    score_abnormal_snapshot as run_score_abnormal_snapshot,
    score_environment_snapshot as run_score_environment_snapshot,
    score_mainline_snapshot as run_score_mainline_snapshot,
    score_memory_snapshot as run_score_memory_snapshot,
    score_structure_snapshot as run_score_structure_snapshot,
)
from domains.execution_chain.candidate_selection_stage import build_candidate_selection_stage
from domains.execution_chain.entry_plan_stage import build_entry_plan_stage
from domains.execution_chain.environment_follow_stage import build_environment_follow_stage
from domains.execution_chain.pk_decision_stage import build_pk_decision_stage
from domains.execution_chain.risk_review_stage import build_risk_review_stage
from domains.execution_chain.stage_registry import (
    DEFAULT_EXECUTION_STAGE_SPECS,
    build_execution_stage_specs,
)
from domains.execution_chain.stage_runtime import (
    build_execution_stage_lookup,
    get_execution_stage_label,
    run_registered_execution_stages,
)
from domains.execution_chain.watch_pool_stage import build_watch_pool_stage
from domains.market_activity.candlestick import (
    analyze_candlestick_pattern as run_analyze_candlestick_pattern,
)
from domains.market_activity.infer import (
    analyze_market_and_sectors as run_analyze_market_and_sectors,
    resolve_market_mainline_context as run_resolve_market_mainline_context,
)
from domains.market_activity.sector_chain_runtime import (
    ai_analyze_sector_relationships as run_ai_analyze_sector_relationships,
    ai_group_concepts_into_chains as run_ai_group_concepts_into_chains,
)
from execution.intraday_execution_runtime import (
    build_waiting_stock_plan as run_build_waiting_stock_plan,
    build_intraday_execution_plan as run_build_intraday_execution_plan,
    compute_avg_volume as run_compute_avg_volume,
    fetch_intraday_bars as run_fetch_intraday_bars,
    find_latest_intraday_pivot as run_find_latest_intraday_pivot,
)
from decision.market_phase_context import build_market_phase_context_contract
from decision.zhongshu_runtime import (
    analyze_market_zhongshu,
    build_structure_segment as _build_structure_segment,
    build_zhongshu_ascii_diagram as _build_zhongshu_ascii_diagram,
    build_zhongshu_structure as _build_zhongshu_structure,
    split_zhongshu_history_and_today as _split_zhongshu_history_and_today,
)
from research.market_research_support import (
    build_abnormal_projection_summary as run_build_abnormal_projection_summary,
    build_mainline_rotation_snapshot as run_build_mainline_rotation_snapshot,
    build_mainline_competition_snapshot as run_build_mainline_competition_snapshot,
    build_follow_verdict as run_build_follow_verdict,
    build_market_research_context_bundle as run_build_market_research_context_bundle,
    build_dialectical_decision_snapshot as run_build_dialectical_decision_snapshot,
    build_market_observation_snapshot as run_build_market_observation_snapshot,
    build_market_research_snapshot as run_build_market_research_snapshot,
    derive_step0_follow_plan as run_derive_step0_follow_plan,
    render_market_research_snapshot_section as run_render_market_research_snapshot_section,
    render_step0_follow_section as run_render_step0_follow_section,
)
from diagnostics.single_stock_runtime import (
    generate_single_stock_diagnostic_markdown as run_generate_single_stock_diagnostic_markdown,
    resolve_single_stock_snapshot as run_resolve_single_stock_snapshot,
)
from portfolio.position_management_report import (
    analyze_position_management as run_analyze_position_management,
    build_personal_position_context as run_build_personal_position_context,
    parse_position_string as run_parse_position_string,
)
from portfolio.position_strategy_report import (
    render_position_strategy_report,
    save_position_strategy_report,
)
from publish.snap_ui_public_data import publish_snap_ui_public_data
from export.sh_index_chanlun_html import (
    DEFAULT_INDEX_CODE,
    normalize_visual_payload,
    render_sh_index_chanlun_html,
    run_analysis as run_sh_index_chanlun_analysis,
    save_sh_index_chanlun_html_report,
)
from replay.report_replay import replay_from_snapshot as run_replay_from_snapshot
from report.report_acceptance_audit import audit_report_markdown
from market_data.daily_price_runtime import (
    compute_bar_change_pct as run_compute_bar_change_pct,
    compute_stop_loss_mainline_anchor as run_compute_stop_loss_mainline_anchor,
    count_trading_days_between as run_count_trading_days_between,
    enrich_stop_plan_with_reference_anchors as run_enrich_stop_plan_with_reference_anchors,
    evaluate_live_tradability as run_evaluate_live_tradability,
    fetch_daily_price_bars as run_fetch_daily_price_bars,
    fetch_recent_price_bars as run_fetch_recent_price_bars,
    fetch_quicktiny_daily_price_bars as run_fetch_quicktiny_daily_price_bars,
    get_first_bar_after as run_get_first_bar_after,
    get_first_bar_on_or_after as run_get_first_bar_on_or_after,
    get_last_bar_on_or_before as run_get_last_bar_on_or_before,
    get_limit_up_pct as run_get_limit_up_pct,
    is_next_trading_day as run_is_next_trading_day,
    is_one_word_limit_bar as run_is_one_word_limit_bar,
    merge_daily_price_bars as run_merge_daily_price_bars,
    resolve_big_yang_confluence_anchor as run_resolve_big_yang_confluence_anchor,
    run_with_wall_clock_timeout as run_run_with_wall_clock_timeout,
    to_bs_code as run_to_bs_code,
)
from market_data.tushare_turnover_service import (
    fetch_stock_basic_map as run_fetch_stock_basic_map,
)
from risk.a_kill_blacklist_store import (
    get_active_a_kill_records,
    is_stock_in_a_kill_cooldown,
    load_a_kill_blacklist,
    save_a_kill_blacklist,
    update_a_kill_blacklist,
)
from selection.candidate_bundle_runtime import build_step2_candidate_bundle as run_build_step2_candidate_bundle
from selection.candidate_context_support import (
    build_trend_continuation_context as run_build_trend_continuation_context,
    build_washout_reclaim_context as run_build_washout_reclaim_context,
)
from selection.candidate_execution_contracts import (
    ABNORMAL_SETUP_LIBRARY as RUN_ABNORMAL_SETUP_LIBRARY,
    DEFENSIVE_EXIT_RULE_TEXT as RUN_DEFENSIVE_EXIT_RULE_TEXT,
    FOLLOW_STATE_PRIORITY_SCORE_MAP as RUN_FOLLOW_STATE_PRIORITY_SCORE_MAP,
    PROFIT_EXIT_RULE_TEXT as RUN_PROFIT_EXIT_RULE_TEXT,
    SETUP_EXECUTION_CONTRACTS as RUN_SETUP_EXECUTION_CONTRACTS,
    SETUP_PRIORITY_SCORE_MAP as RUN_SETUP_PRIORITY_SCORE_MAP,
    STRATEGY_HOLDING_DAYS_MAX as RUN_STRATEGY_HOLDING_DAYS_MAX,
    STRATEGY_HOLDING_DAYS_MIN as RUN_STRATEGY_HOLDING_DAYS_MIN,
    build_candidate_exit_rules as run_build_candidate_exit_rules,
    build_gem_textbook_front_text as run_build_gem_textbook_front_text,
    build_gem_textbook_next_step_text as run_build_gem_textbook_next_step_text,
    build_gem_textbook_reference_text as run_build_gem_textbook_reference_text,
    build_philosophy_constraint_text as run_build_philosophy_constraint_text,
    build_weak_to_strong_context as run_build_weak_to_strong_context,
    candidate_has_formal_abnormal_setup as run_candidate_has_formal_abnormal_setup,
    candidate_is_resilient_abnormal as run_candidate_is_resilient_abnormal,
    format_holding_window_text as run_format_holding_window_text,
    get_setup_execution_contract as run_get_setup_execution_contract,
    get_setup_priority_score as run_get_setup_priority_score,
    infer_risk_level_from_abnormal_follow_state as run_infer_risk_level_from_abnormal_follow_state,
    is_bridge_priority_setup as run_is_bridge_priority_setup,
    map_setup_id_to_signal_type as run_map_setup_id_to_signal_type,
    resolve_candidate_follow_state as run_resolve_candidate_follow_state,
    resolve_candidate_setup_id as run_resolve_candidate_setup_id,
)
from selection.gem_breathing_runtime import (
    build_gem_elasticity_context as run_build_gem_elasticity_context,
    build_gem_breathing_contract as run_build_gem_breathing_contract,
    build_gem_breathing_textbook_profile as run_build_gem_breathing_textbook_profile,
    build_gem_breathing_watch_anchor as run_build_gem_breathing_watch_anchor,
    build_gem_observation_pool as run_build_gem_observation_pool,
    build_gem_breathing_prep_context as run_build_gem_breathing_prep_context,
    classify_20cm_branch as run_classify_20cm_branch,
    discover_all_gem_breathing_candidates as run_discover_all_gem_breathing_candidates,
    discover_filtered_out_gem_breathing_candidates as run_discover_filtered_out_gem_breathing_candidates,
    discover_gem_breathing_candidates as run_discover_gem_breathing_candidates,
    evaluate_gem_breathing_window as run_evaluate_gem_breathing_window,
    is_20cm_stock as run_is_20cm_stock,
    resolve_candidate_contract_prices as run_resolve_candidate_contract_prices,
    should_hide_gem_execution_entry_range as run_should_hide_gem_execution_entry_range,
)
from selection.mainline_support import (
    resolve_primary_mainline_name as run_resolve_primary_mainline_name,
    split_candidates_by_mainline as run_split_candidates_by_mainline,
)
from selection.position_sizing_runtime import (
    build_position_sizing_decision as run_build_position_sizing_decision,
)
from selection.special_probe_runtime import (
    build_abnormal_watch_anchor_candidates as run_build_abnormal_watch_anchor_candidates,
    build_abnormal_probe_group as run_build_abnormal_probe_group,
    build_mainline_upgrade_probe_context as run_build_mainline_upgrade_probe_context,
    build_special_probe_focus_text as run_build_special_probe_focus_text,
    build_special_probe_verdict as run_build_special_probe_verdict,
    format_abnormal_probe_text as run_format_abnormal_probe_text,
    get_abnormal_follow_risk_signal as run_get_abnormal_follow_risk_signal,
    score_candidate_decision_stack as run_score_candidate_decision_stack,
    sort_decision_stack_candidates as run_sort_decision_stack_candidates,
)
from selection.trend_snapshot_runtime import (
    build_extreme_conviction_groups as run_build_extreme_conviction_groups,
    build_extreme_conviction_list as run_build_extreme_conviction_list,
    build_leader_memory_bank as run_build_leader_memory_bank,
    build_sector_trend_snapshot as run_build_sector_trend_snapshot,
)
from selection.watch_anchor_support import (
    append_watch_anchor_note as run_append_watch_anchor_note,
    build_cycle_triplet_texts as run_build_cycle_triplet_texts,
    build_execute_anchor_window_text as run_build_execute_anchor_window_text,
    classify_watch_anchor_bucket as run_classify_watch_anchor_bucket,
    derive_pending_candidate_type as run_derive_pending_candidate_type,
    derive_watch_anchor_note as run_derive_watch_anchor_note,
    derive_watch_anchor_type as run_derive_watch_anchor_type,
    requires_crossline_second_confirmation as run_requires_crossline_second_confirmation,
    select_priority_watch_anchor as run_select_priority_watch_anchor,
    sort_watch_anchor_candidates as run_sort_watch_anchor_candidates,
)
from risk.risk_bundle_runtime import (
    build_step3_risk_bundle as run_build_step3_risk_bundle,
    evaluate_limit_up_friction as run_evaluate_limit_up_friction,
    format_step3_risk_reason as run_format_step3_risk_reason,
    parse_limit_time_to_minutes as run_parse_limit_time_to_minutes,
)
from hooks.report.use_execution_appendix_tail import run as run_execution_appendix_tail
from hooks.report.use_strategy_performance_tail import run as run_strategy_performance_tail
from hooks.report.use_report_tail_summary import run as run_report_tail_summary
from input.iwencai_runtime import (
    get_major_indices_from_iwencai,
    get_sector_change_from_iwencai,
    get_sector_quadrant_data,
    get_total_turnover_from_iwencai,
    get_turnover_rank_from_iwencai,
    get_wind_a_from_iwencai,
    get_csi1000_from_iwencai,
)
from input.tushare_runtime import (
    get_csi1000_from_tushare_first,
    get_margin_pressure_from_tushare_first,
    get_etf_turnover_series_from_sina_first,
    get_hot_concept_fund_flow_from_tushare_first,
    get_lhb_snapshot_from_tushare_first,
    get_major_indices_from_tushare_first,
    get_new_stock_calendar_from_tushare_first,
    get_limit_pool_snapshot_from_tushare_first,
    get_sector_change_rank_from_tushare_first,
    get_sector_fund_flow_from_tushare_first,
    get_sector_hot_plates_from_tushare_first,
    get_stock_hot_rank_from_tushare_first,
    get_new_high_feedback_from_tushare_first,
    get_price_band_style_series_from_tushare_first,
    get_stock_risk_map_from_tushare_first,
    get_top50_turnover_share_series_from_tushare_first,
    get_total_turnover_from_tushare_first,
    get_turnover_rank_from_tushare_first,
    get_wind_a_from_tushare_first,
)
from input.runtime import run_input_runtime
from market_data.kline_dates import (
    normalize_kline_date_str as _normalize_kline_date_str,
    parse_kline_date as _parse_kline_date,
    short_kline_date as _short_date,
)
from report.action_plan_renderer import render_action_plan_result, render_action_plan_section
from report.appendix_renderer import render_execution_appendix
from report.context_sections_renderer import (
    render_ai_market_insight_section,
    render_mainline_discipline_section,
    render_supplementary_perspective_section,
)
from report.final_conclusion_renderer import build_legacy_final_conclusion_lines
from report.front_summary_renderer import render_front_digest, render_mvp_focus_summary
from report.front_summary_support import (
    build_bridge_prep_context as run_build_bridge_prep_context,
    build_front_follow_action_text as run_build_front_follow_action_text,
    build_front_structure_layer_text as run_build_front_structure_layer_text,
    build_front_mainline_label as _build_front_mainline_label,
    build_front_style_action_text as _build_front_style_action_text,
    format_candidate_preview as run_format_candidate_preview,
    front_position_guard_label as run_front_position_guard_label,
    render_core_mvp_digest as _render_core_mvp_digest,
    render_mvp_focus_summary as _render_mvp_focus_summary,
)
from report.strategy_contract_support import (
    build_alignment_pool_text as _build_alignment_pool_text,
    build_strategy_positioning_lines as _build_strategy_positioning_lines,
    build_trading_philosophy_lines as _build_trading_philosophy_lines,
    get_contract_logic_digest_text as _get_contract_logic_digest_text,
)
from report.mvp_compactor import compact_report_for_mvp as _compact_report_for_mvp
from report.report_document_builder import (
    build_prohibition_section_contract,
    build_report_shell_contract,
    replace_placeholder_lines,
)
from report.runtime import render_markdown_report_runtime
from report.market_research_renderer import (
    render_gem_breathing_pool_section,
    render_gem_breathing_step2_section,
)
from report.strategy_tracking_runtime import (
    append_strategy_performance_section as run_append_strategy_performance_section,
    build_strategy_factor_snapshot as run_build_strategy_factor_snapshot,
    build_strategy_plan_context as run_build_strategy_plan_context,
    normalize_report_timer_steps as run_normalize_report_timer_steps,
    update_strategy_performance_book as run_update_strategy_performance_book,
)
from report.strategy_tracking_snapshot_support import (
    build_abnormal_setup_distribution as run_build_abnormal_setup_distribution,
    snapshot_candidate_brief as run_snapshot_candidate_brief,
)
from report.strategy_tracking_store import (
    get_factor_snapshot_path as run_get_factor_snapshot_path,
    get_strategy_performance_path as run_get_strategy_performance_path,
    load_strategy_performance_ledger as run_load_strategy_performance_ledger,
    save_factor_snapshot as run_save_factor_snapshot,
    save_strategy_performance_ledger as run_save_strategy_performance_ledger,
)
from report.strategy_tracking_followups import (
    build_gem_horizontal_compare_cards as run_build_gem_horizontal_compare_cards,
    build_recent_target_followups as run_build_recent_target_followups,
    build_recent_target_reflection as run_build_recent_target_reflection,
    build_recent_target_review_matrix as run_build_recent_target_review_matrix,
)
from report.strategy_tracking_records import (
    find_strategy_record as run_find_strategy_record,
    format_strategy_record_brief as run_format_strategy_record_brief,
    merge_strategy_record_sources as run_merge_strategy_record_sources,
    prepare_records_for_review as run_prepare_records_for_review,
    strategy_record_core_signature as run_strategy_record_core_signature,
    summarize_strategy_window as run_summarize_strategy_window,
    upsert_strategy_record as run_upsert_strategy_record,
)
from report.strategy_tracking_evaluation import (
    apply_yizi_chain_rules as run_apply_yizi_chain_rules,
    collect_record_market_path as run_collect_record_market_path,
    evaluate_single_strategy_record as run_evaluate_single_strategy_record,
    get_nth_bar_after as run_get_nth_bar_after,
    get_recent_record_display_metrics as run_get_recent_record_display_metrics,
    simulate_exit_for_entry as run_simulate_exit_for_entry,
    compute_benchmark_return as run_compute_benchmark_return,
    compute_watch_outcome_metrics as run_compute_watch_outcome_metrics,
)
from report.strategy_tracking_support import (
    backfill_strategy_record_market_context as run_backfill_strategy_record_market_context,
    build_candidate_feedback_clock as run_build_candidate_feedback_clock,
    build_candidate_history_feedback as run_build_candidate_history_feedback,
    build_trade_return_stats as run_build_trade_return_stats,
    candidate_confirmation_chain as run_candidate_confirmation_chain,
    compound_returns as run_compound_returns,
    extract_candidate_report_prices as run_extract_candidate_report_prices,
    format_pct as run_format_pct,
    format_pct_range as run_format_pct_range,
    get_plan_action_label as run_get_plan_action_label,
    get_run_mode_label as run_get_run_mode_label,
    get_signal_type_label as run_get_signal_type_label,
    get_strategy_status_label as run_get_strategy_status_label,
    iter_record_probe_candidates as run_iter_record_probe_candidates,
    resolve_probe_role_family as run_resolve_probe_role_family,
    summarize_ev_signal_review as run_summarize_ev_signal_review,
)
from storage.database_service import DatabaseService
from report.strategy_tracking_ev import (
    build_strategy_ev_calibration as run_build_strategy_ev_calibration,
    estimate_signal_type_ev as run_estimate_signal_type_ev,
    score_execution_candidate as run_score_execution_candidate,
)
from report.strategy_tracking_review import (
    build_gem_structure_cycle_cards as run_build_gem_structure_cycle_cards,
    build_self_calibration_summary as run_build_self_calibration_summary,
    build_structure_cycle_gem_summary as run_build_structure_cycle_gem_summary,
    build_system_graduation_dashboard as run_build_system_graduation_dashboard,
    classify_gem_breathing_week_sample as run_classify_gem_breathing_week_sample,
    classify_strategy_record_attribution as run_classify_strategy_record_attribution,
    classify_structure_cycle_result as run_classify_structure_cycle_result,
    extract_gem_breathing_contract_snapshot as run_extract_gem_breathing_contract_snapshot,
    summarize_gem_breathing_week_review as run_summarize_gem_breathing_week_review,
    summarize_setup_signal_review as run_summarize_setup_signal_review,
    summarize_strategy_attribution as run_summarize_strategy_attribution,
    summarize_structure_cycles as run_summarize_structure_cycles,
)
from report.observation_plan_formatter import (
    build_abnormal_follow_rule as run_build_abnormal_follow_rule,
    format_abnormal_observation_columns as run_format_abnormal_observation_columns,
    format_frozen_plan_columns as run_format_frozen_plan_columns,
    refine_abnormal_follow_display as run_refine_abnormal_follow_display,
)
from report.observation_price_formatter import (
    append_observation_price_focus_note as run_append_observation_price_focus_note,
    append_price_focus_note as run_append_price_focus_note,
    build_trade_price_focus as run_build_trade_price_focus,
    build_observation_price_focus_text as run_build_observation_price_focus_text,
    build_observation_price_note_text as run_build_observation_price_note_text,
    compose_observation_focus_text as run_compose_observation_focus_text,
    normalize_observation_zone_badge as run_normalize_observation_zone_badge,
    should_surface_price_note as run_should_surface_price_note,
)
from report.board_tag_analysis_builder import build_board_tag_analysis_sections_contract
from report.exchange_monitor_builder import build_exchange_monitor_sections_contract
from report.market_analysis_builder import build_market_and_sector_analysis_contract
from report.market_overview_builder import build_market_trend_sections_contract
from report.pk_decision_renderer import render_pk_decision_section
from report.single_stock_diagnostic_renderer import render_single_stock_diagnostic_markdown
from report.strategy_performance_renderer import render_strategy_performance_section
from research.tracking_memory_runtime import refresh_tracking_memory

MARKET_ZHONGSHU_LOOKBACK_DAYS = 250
MARKET_ZHONGSHU_MIN_KLINES = 20
MAX_SINGLE_TRADE_LOSS_PCT = 0.05
# Hook strings moved to daily_report_markdown_hooks.py; wrappers below keep legacy call sites working.
DEFENSIVE_EXIT_RULE_TEXT = RUN_DEFENSIVE_EXIT_RULE_TEXT
PROFIT_EXIT_RULE_TEXT = RUN_PROFIT_EXIT_RULE_TEXT
DECISION_STACK_ORDER_TEXT = "环境 -> 主线 -> 记忆 -> 触发 -> 可交易性 -> EV"
_STRATEGY_REVIEW_HELPER_EXCLUDES = {
    "_build_gem_structure_cycle_cards",
    "_build_self_calibration_summary",
    "_build_structure_cycle_gem_summary",
    "_build_system_graduation_dashboard",
    "_classify_gem_breathing_week_sample",
    "_classify_strategy_record_attribution",
    "_classify_structure_cycle_result",
    "_extract_gem_breathing_contract_snapshot",
    "_summarize_gem_breathing_week_review",
    "_summarize_setup_signal_review",
    "_summarize_strategy_attribution",
    "_summarize_structure_cycles",
}
_STRATEGY_EVAL_HELPER_EXCLUDES = {
    "_apply_yizi_chain_rules",
    "_collect_record_market_path",
    "_compute_benchmark_return",
    "_compute_watch_outcome_metrics",
    "_evaluate_single_strategy_record",
    "_get_nth_bar_after",
    "_get_recent_record_display_metrics",
    "_simulate_exit_for_entry",
}
_STRATEGY_EV_HELPER_EXCLUDES = {
    "build_strategy_ev_calibration",
    "estimate_signal_type_ev",
    "score_execution_candidate",
}
_STRATEGY_STORE_HELPER_EXCLUDES = {
    "_get_factor_snapshot_path",
    "_get_strategy_performance_path",
}
_OBSERVATION_PLAN_FORMATTER_HELPER_EXCLUDES = {
    "_build_abnormal_follow_rule",
    "_format_abnormal_observation_columns",
    "_format_frozen_plan_columns",
    "_refine_abnormal_follow_display",
}
_OBSERVATION_PRICE_FORMATTER_HELPER_EXCLUDES = {
    "_append_observation_price_focus_note",
    "_append_price_focus_note",
    "_build_observation_price_focus_text",
    "_build_observation_price_note_text",
    "_compose_observation_focus_text",
    "_normalize_observation_zone_badge",
    "_should_surface_price_note",
}
_SINGLE_STOCK_RUNTIME_HELPER_EXCLUDES = {
    "generate_single_stock_diagnostic_markdown",
    "resolve_single_stock_snapshot",
}
_POSITION_MANAGEMENT_HELPER_EXCLUDES = {
    "analyze_position_management",
    "parse_position_string",
}
_DAILY_PRICE_RUNTIME_HELPER_EXCLUDES = {
    "_compute_bar_change_pct",
    "_count_trading_days_between",
    "_enrich_stop_plan_with_reference_anchors",
    "_fetch_quicktiny_daily_price_bars",
    "_get_first_bar_after",
    "_get_first_bar_on_or_after",
    "_get_last_bar_on_or_before",
    "_get_limit_up_pct",
    "_is_next_trading_day",
    "_is_one_word_limit_bar",
    "_merge_daily_price_bars",
    "_resolve_big_yang_confluence_anchor",
    "_run_with_wall_clock_timeout",
    "_to_bs_code",
    "compute_stop_loss_mainline_anchor",
    "evaluate_live_tradability",
    "fetch_daily_price_bars",
    "fetch_recent_price_bars",
}


def _collect_runtime_helpers(excluded_names=None):
    excluded_names = set(excluded_names or ())
    return {
        key: value
        for key, value in globals().items()
        if key not in excluded_names and not (key.startswith("__") and key.endswith("__"))
    }


def _build_mainline_rotation_snapshot(observation=None, state_machine=None, style_switch=None, sector_ai_analysis=None):
    return run_build_mainline_rotation_snapshot(
        observation=observation,
        state_machine=state_machine,
        style_switch=style_switch,
        sector_ai_analysis=sector_ai_analysis,
        helpers={
            "_safe_float": _safe_float,
            "sector_name_matches": sector_name_matches,
        },
    )


_build_gem_textbook_reference_text = run_build_gem_textbook_reference_text
_build_gem_textbook_front_text = run_build_gem_textbook_front_text
_build_gem_textbook_next_step_text = run_build_gem_textbook_next_step_text
_build_weak_to_strong_context = run_build_weak_to_strong_context
_build_philosophy_constraint_text = run_build_philosophy_constraint_text

INTRADAY_CONFIRM_LOOKBACK_60M = 8
INTRADAY_STOP_LOOKBACK_30M = 12
TRACKING_MEMORY_KEEP_DAYS = 20
TRACKING_MEMORY_TENTATIVE_EXPIRE_DAYS = 5
TRACKING_MEMORY_MAX_ITEMS = 40
TRACKING_MEMORY_PROMOTE_CONFIRMATIONS = 2
STRATEGY_HOLDING_DAYS_MIN = RUN_STRATEGY_HOLDING_DAYS_MIN
STRATEGY_HOLDING_DAYS_MAX = RUN_STRATEGY_HOLDING_DAYS_MAX
STRATEGY_PERFORMANCE_LEDGER_VERSION = "v2"
STRATEGY_FACTOR_SNAPSHOT_VERSION = "v3"
DISPLAY_MVP_MODE = True
EMIT_HELPER_DIAGNOSTICS = True
REPORT_RUNTIME_CACHE = None
DECISION_STRICT_MODE = True
ALLOW_DISPLAY_DEGRADED_ABNORMAL_SNAPSHOT = False
LEDGER_MODE_FROZEN = "frozen"
LEDGER_MODE_REPLAY = "replay"
REPORT_VARIANT_FULL = "full"
REPORT_VARIANT_SUMMARY = "summary"
REPORT_VARIANT_RUN_LOG = "run_log"
EV_SIGNAL_TYPE_PRIORS = {
    'sweet_zone': {
        'win_rate': 0.53,
        'avg_win_pct': 0.085,
        'avg_loss_pct': 0.034,
        'prior_weight': 8.0,
        'label': '甜品区',
    },
    'breakout': {
        'win_rate': 0.49,
        'avg_win_pct': 0.078,
        'avg_loss_pct': 0.039,
        'prior_weight': 8.0,
        'label': '突破',
    },
    'panic_buy': {
        'win_rate': 0.44,
        'avg_win_pct': 0.118,
        'avg_loss_pct': 0.046,
        'prior_weight': 8.0,
        'label': '恐慌盘',
    },
    'base': {
        'win_rate': 0.50,
        'avg_win_pct': 0.080,
        'avg_loss_pct': 0.040,
        'prior_weight': 10.0,
        'label': '基础',
    },
}
ABNORMAL_SETUP_LIBRARY = RUN_ABNORMAL_SETUP_LIBRARY
SETUP_EXECUTION_CONTRACTS = RUN_SETUP_EXECUTION_CONTRACTS
SETUP_PRIORITY_SCORE_MAP = RUN_SETUP_PRIORITY_SCORE_MAP
FOLLOW_STATE_PRIORITY_SCORE_MAP = RUN_FOLLOW_STATE_PRIORITY_SCORE_MAP
_resolve_candidate_setup_id = run_resolve_candidate_setup_id
_resolve_candidate_follow_state = run_resolve_candidate_follow_state
_candidate_has_formal_abnormal_setup = run_candidate_has_formal_abnormal_setup
_candidate_is_resilient_abnormal = run_candidate_is_resilient_abnormal
_is_bridge_priority_setup = run_is_bridge_priority_setup
_get_setup_execution_contract = run_get_setup_execution_contract
_get_setup_priority_score = run_get_setup_priority_score
_infer_risk_level_from_abnormal_follow_state = run_infer_risk_level_from_abnormal_follow_state
_map_setup_id_to_signal_type = run_map_setup_id_to_signal_type
_format_holding_window_text = run_format_holding_window_text
_build_candidate_exit_rules = run_build_candidate_exit_rules


def _is_degraded_abnormal_snapshot(item):
    return analysis_utils._is_degraded_abnormal_snapshot(item)


def _split_abnormal_watch_pool(abnormal_watch_pool):
    formal_items = []
    degraded_items = []
    for item in abnormal_watch_pool or []:
        if _is_degraded_abnormal_snapshot(item):
            degraded_items.append(item)
        else:
            formal_items.append(item)
    return formal_items, degraded_items


# ============================================================
# AI智能分析模块（内置LLM能力）
# ============================================================

# LLM调用统计（全局）
_llm_call_stats = {
    'total_calls': 0,
    'total_time': 0.0,
    'event_analysis_calls': 0,
    'event_analysis_time': 0.0,
    'sector_analysis_calls': 0,
    'sector_analysis_time': 0.0,
}

def get_llm_call_stats():
    """获取LLM调用统计"""
    return _llm_call_stats.copy()

def reset_llm_call_stats():
    """重置LLM调用统计"""
    global _llm_call_stats
    _llm_call_stats = {
        'total_calls': 0,
        'total_time': 0.0,
        'event_analysis_calls': 0,
        'event_analysis_time': 0.0,
        'sector_analysis_calls': 0,
        'sector_analysis_time': 0.0,
    }

def ai_analyze_sector_relationships(sector_list, context_info="", tag_evidence_snapshot=None):
    return run_ai_analyze_sector_relationships(
        sector_list,
        context_info=context_info,
        tag_evidence_snapshot=tag_evidence_snapshot,
        helpers={
            "_llm_call_stats": _llm_call_stats,
            "get_llm_service": get_llm_service,
        },
    )


# ============================================================


def get_execution_framework_text():
    """统一的盘前预案执行框架文案。"""
    return markdown_hooks.use_execution_framework_text()


def build_stop_execution_plan(entry_price, structure_stop=None, structure_label='结构止损'):
    return analysis_utils.build_stop_execution_plan(entry_price, structure_stop=structure_stop, structure_label=structure_label)


def calculate_price_range(stock_data):
    return analysis_utils.calculate_price_range(stock_data)


# 添加路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ========== 计时器类 ==========
class StepTimer:
    """步骤计时器 - 记录每个步骤的耗时"""
    def __init__(self):
        self.step_times = []
        self.start_time = None
        self.total_start_time = time.time()
    
    def start(self):
        """开始计时"""
        self.start_time = time.time()
    
    def record(self, step_name, step_num=None):
        """记录步骤耗时"""
        if self.start_time is None:
            self.start()
        
        elapsed = time.time() - self.start_time
        total_elapsed = time.time() - self.total_start_time
        
        if step_num:
            prefix = f"步骤{step_num}: "
        else:
            prefix = ""
        self.step_times.append((f"{prefix}{step_name}", elapsed, total_elapsed))
        
        # 重置计时器用于下一步
        self.start_time = time.time()
        
        return elapsed, total_elapsed
    
    def get_summary(self):
        """获取计时摘要"""
        total_time = time.time() - self.total_start_time
        return {
            'steps': self.step_times,
            'total_time': total_time,
            'step_count': len(self.step_times)
        }
    
    def print_summary(self):
        """打印计时摘要"""
        print("\n" + "=" * 80)
        print("执行时间统计", flush=True)
        print("=" * 80)
        print(f"{'步骤':<40} {'耗时':>10} {'累计':>10} {'占比':>8}")
        print("-" * 80)
        
        total_time = time.time() - self.total_start_time
        for step_name, elapsed, cumulative in self.step_times:
            percentage = (elapsed / total_time * 100) if total_time > 0 else 0
            print(f"{step_name:<40} {elapsed:>9.2f}s {cumulative:>9.2f}s {percentage:>7.1f}%")
        
        print("-" * 80)
        print(f"{'总计':<40} {total_time:>9.2f}s")
        print("=" * 80)

# 导入核心模块
from data_collector import AShareDataCollector
from ths_hot_stock import fetch_ths_hot_stock, fetch_hot_stock_with_fallback
from ths_hot_list import fetch_hot_plate
from tencent_finance_data import TencentFinanceData
from xuangubao_intraday import XuangubaoIntradayAnalyzer
from limit_up_down_pool import get_limit_up_pool, get_limit_down_pool, mark_limit_status
from strong_stock_pool import get_strong_stock_pool, analyze_strong_stocks_by_sector
from data_validator import DataValidator
from quantitative_analyzer import (
    VolumeAnomalyDetector, LHBAnalyzer, ResonanceAnalyzer, SignalGenerator,
    analyze_volume_anomaly, analyze_lhb, calculate_resonance, generate_trade_signals
)
from hot_list_integrated import get_integrated_hot_list, analyze_sector_distribution
from history_cache import get_cache, HistoryCache
from llm_service import get_llm_service


def _resolve_remote_calendar_llm_enabled():
    raw = os.getenv("A_DAILY_REPORT_ENABLE_REMOTE_CALENDAR_LLM")
    if raw is not None and str(raw).strip():
        return str(raw).strip().lower() in {"1", "true", "yes", "on"}
    return bool(str(os.getenv("DEEPSEEK_API_KEY", "") or "").strip())


# ========== 蜡烛图形态判断函数 ==========
def analyze_candlestick_pattern(open_price, close_price, high_price, low_price, change_pct, first_limit_time=None):
    return run_analyze_candlestick_pattern(
        open_price,
        close_price,
        high_price,
        low_price,
        change_pct,
        first_limit_time=first_limit_time,
    )


def get_daily_data(target_date=None):
    return run_input_runtime(
        target_date,
        helpers={
            key: value
            for key, value in globals().items()
            if not (key.startswith("__") and key.endswith("__"))
        },
        config={},
    )


def _load_runtime_data_snapshot(target_date):
    if not _POSTGRES_ONLY_RUNTIME:
        return load_data_snapshot(str(target_date or ""))
    service = _postgres_daily_report_service()
    result = service.load_daily_report_snapshot(str(target_date or ""))
    data = result.get("data") if isinstance(result, dict) else {}
    if not isinstance(data, dict) or not data:
        return {}, result.get("source", "") if isinstance(result, dict) else ""
    data["postgres_source"] = result.get("source") or data.get("postgres_source") or ""
    data["postgres_field_count"] = result.get("field_count", 0)
    data["postgres_only"] = True
    return data, data.get("postgres_source", "")


def get_concept_fund_flow_from_snapshot(target_date=None):
    snapshot_data, _ = _load_runtime_data_snapshot(str(target_date or ""))
    if not isinstance(snapshot_data, dict):
        return {}
    concept_flow = snapshot_data.get("concept_fund_flow")
    if not isinstance(concept_flow, dict):
        return {}
    rows = [dict(row) for row in (concept_flow.get("rows") or []) if isinstance(row, dict)]
    if not rows:
        return {}
    return {
        "rows": rows,
        "inflow": list(concept_flow.get("inflow") or rows),
        "outflow": list(concept_flow.get("outflow") or []),
        "provider": concept_flow.get("provider") or "snapshot.concept_fund_flow",
    }


def _normalize_lhb_code(fs_code):
    text = str(fs_code or "").strip().upper()
    if "." in text:
        text = text.split(".", 1)[0]
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits.zfill(6) if digits else ""


def get_legacy_lhb_snapshot(target_date=None):
    from finshare import get_lhb

    lhb_date = str(target_date or "").replace("-", "")
    lhb_df = get_lhb(start_date=lhb_date, end_date=lhb_date)
    if lhb_df is None or len(lhb_df) == 0:
        return {
            "lhb_net_buy_top10": [],
            "lhb_net_sell_top10": [],
            "lhb_analysis": [],
            "provider": "finshare.get_lhb",
        }
    grouped = {}
    for row in lhb_df.to_dict("records") or []:
        code = _normalize_lhb_code(row.get("fs_code") or row.get("ts_code") or row.get("code"))
        if not code:
            continue
        bucket = grouped.setdefault(
            code,
            {
                "代码": code,
                "fs_code": row.get("fs_code") or row.get("ts_code") or "",
                "name": row.get("name", ""),
                "net_buy_amount": 0.0,
                "close_price": 0.0,
                "change_rate": 0.0,
                "reasons": [],
                "data_source": "finshare.get_lhb",
            },
        )
        bucket["net_buy_amount"] += _safe_float(row.get("net_buy_amount"), 0.0)
        bucket["close_price"] = bucket.get("close_price") or _safe_float(row.get("close_price"), 0.0)
        bucket["change_rate"] = bucket.get("change_rate") or _safe_float(row.get("change_rate"), 0.0)
        reason = str(row.get("reason") or "").strip()
        if reason and reason not in bucket["reasons"]:
            bucket["reasons"].append(reason)

    grouped_rows = list(grouped.values())
    buy_rows = sorted(grouped_rows, key=lambda item: item.get("net_buy_amount", 0), reverse=True)[:10]
    sell_rows = sorted(grouped_rows, key=lambda item: item.get("net_buy_amount", 0))[:10]

    def _ranked(rows):
        return [
            {
                "rank": rank,
                "code": row["代码"],
                "name": row.get("name", ""),
                "net_buy_amount_yi": round(_safe_float(row.get("net_buy_amount"), 0.0) / 1e8, 6),
                "change_pct": _safe_float(row.get("change_rate"), 0.0),
                "zt_status": "正常",
                "sector": "未知",
                "data_source": "finshare.get_lhb",
            }
            for rank, row in enumerate(rows, start=1)
        ]

    return {
        "lhb_net_buy_top10": _ranked(buy_rows),
        "lhb_net_sell_top10": _ranked(sell_rows),
        "lhb_analysis": grouped_rows,
        "provider": "finshare.get_lhb",
    }



def _minimal_fallback_analysis(event_title: str, event_summary: str = "") -> dict:
    return run_minimal_fallback_analysis(event_title, event_summary)


def ai_analyze_event_sectors(event_title, event_summary=""):
    return run_ai_analyze_event_sectors(
        event_title,
        event_summary,
        helpers={
            "_llm_call_stats": _llm_call_stats,
            "_default_get_llm_service": get_llm_service,
        },
    )


def _llm_analyze_event(event_text):
    return run_llm_analyze_event(
        event_text,
        helpers={
            "_llm_call_stats": _llm_call_stats,
            "_default_get_llm_service": get_llm_service,
        },
    )


def analyze_event_sector(event_title, event_summary="", xuangubao_data=None, hot_rank_data=None):
    return run_analyze_event_sector(
        event_title,
        event_summary=event_summary,
        xuangubao_data=xuangubao_data,
        hot_rank_data=hot_rank_data,
    )


def get_stock_status(stock_name, stock_code, zt_pool, dt_pool, change_pct=None):
    return run_get_stock_status(stock_name, stock_code, zt_pool, dt_pool, change_pct)


def analyze_market_and_sectors(data):
    return run_analyze_market_and_sectors(
        data,
        helpers={
            "_build_unified_sector_strength_rows": _build_unified_sector_strength_rows,
        },
    )


def _build_dragon_stocks_from_zt_pool(data):
    return _resolve_market_mainline_context(data, {}).get('dragon_stocks', [])


def _resolve_market_mainline_context(data, market_analysis):
    return run_resolve_market_mainline_context(
        data,
        market_analysis,
        helpers={
            "normalize_stock_code": normalize_stock_code,
        },
    )


def ai_group_concepts_into_chains(concepts_list):
    return run_ai_group_concepts_into_chains(
        concepts_list,
        helpers={
            "DISPLAY_MVP_MODE": DISPLAY_MVP_MODE,
            "ai_analyze_sector_relationships": ai_analyze_sector_relationships,
        },
    )


_gem_stock_universe_cache = None

def get_stock_sector(stock_name, stock_code, hot_rank_data=None, zt_pool_data=None, lianban_data=None, lhb_data=None, sector_fund_flow=None, zt_pool_raw=None, dt_pool_raw=None, xuangubao_data=None, skip_api_call=False):
    return run_get_stock_sector(
        stock_name,
        stock_code,
        hot_rank_data=hot_rank_data,
        zt_pool_data=zt_pool_data,
        lianban_data=lianban_data,
        lhb_data=lhb_data,
        sector_fund_flow=sector_fund_flow,
        zt_pool_raw=zt_pool_raw,
        dt_pool_raw=dt_pool_raw,
        xuangubao_data=xuangubao_data,
        skip_api_call=skip_api_call,
    )


def normalize_stock_code(code):
    return analysis_utils.normalize_stock_code(code)


def parse_lianban_num(zt_type):
    """解析涨停类型中的连板数"""
    if not zt_type:
        return 0
    try:
        if '/' in str(zt_type):
            parts = str(zt_type).split('/')
            if len(parts) > 1 and parts[1].isdigit():
                return int(parts[1])
            if parts[0].isdigit():
                return int(parts[0])
        return int(str(zt_type).replace('板', '').replace('首', '1'))
    except Exception:
        return 0


def _clamp(value, low, high):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return low
    return max(low, min(high, value))


def _score_to_star_rank(score_pct):
    score_pct = _clamp(score_pct, 0.0, 100.0)
    if score_pct >= 84:
        return 5
    if score_pct >= 72:
        return 4
    if score_pct >= 58:
        return 3
    if score_pct >= 42:
        return 2
    return 1


def _score_to_level(score_pct):
    score_pct = _clamp(score_pct, 0.0, 100.0)
    if score_pct >= 76:
        return '绿灯'
    if score_pct >= 60:
        return '黄灯'
    if score_pct >= 42:
        return '橙灯'
    return '红灯'


def _level_to_score(level):
    return {
        '绿灯': 84.0,
        '黄灯': 66.0,
        '橙灯': 44.0,
        '红灯': 18.0,
    }.get(level, 50.0)


def load_recent_sector_flow_history(target_date, sector_name, lookback_days=2, max_scan_days=8):
    return run_load_recent_sector_flow_history(
        target_date,
        sector_name,
        lookback_days=lookback_days,
        max_scan_days=max_scan_days,
        helpers={
            "_normalize_kline_date_str": _normalize_kline_date_str,
            "get_previous_date_str": get_previous_date_str,
            "load_data_snapshot": _load_runtime_data_snapshot,
            "sector_name_matches": sector_name_matches,
            "_safe_float": _safe_float,
            "postgres_only_runtime": _POSTGRES_ONLY_RUNTIME,
        },
    )


def load_recent_market_turnover_history(target_date, lookback_days=2, max_scan_days=8):
    return run_load_recent_market_turnover_history(
        target_date,
        lookback_days=lookback_days,
        max_scan_days=max_scan_days,
        helpers={
            "_normalize_kline_date_str": _normalize_kline_date_str,
            "get_previous_date_str": get_previous_date_str,
            "load_data_snapshot": _load_runtime_data_snapshot,
            "_safe_float": _safe_float,
            "postgres_only_runtime": _POSTGRES_ONLY_RUNTIME,
        },
    )


def _parse_status_board_count(status_label):
    text = str(status_label or '').strip()
    if not text:
        return 0
    if '首板' in text:
        return 1
    if '天' in text and '板' in text:
        after_tian = text.split('天', 1)[1]
        digits = ''.join(ch for ch in after_tian if ch.isdigit())
        if digits:
            return int(digits)
    digits = ''.join(ch for ch in text if ch.isdigit())
    return int(digits) if digits else 0


def _count_keyword_hits_in_mapping(mapping, keywords):
    mapping = mapping or {}
    normalized_keywords = [str(keyword or '').upper() for keyword in (keywords or []) if keyword]
    total = 0
    for key, value in mapping.items():
        text = str(key or '').upper()
        if any(keyword in text for keyword in normalized_keywords):
            total += int(_safe_float(value))
    return total


def _extract_market_breadth_snapshot(data):
    return run_extract_market_breadth_snapshot(
        data,
        helpers={"_safe_float": _safe_float},
    )


def get_mainline_star_level(net_inflow, zt_count, dt_count=0, hot_weight=0.0, inflow_history=None):
    return run_get_mainline_star_level(
        net_inflow,
        zt_count,
        dt_count=dt_count,
        hot_weight=hot_weight,
        inflow_history=inflow_history,
        helpers={
            "_safe_float": _safe_float,
            "_clamp": _clamp,
            "_score_to_star_rank": _score_to_star_rank,
        },
    )


def get_sector_hotlist_weight(sector_name, tag_distribution):
    return run_get_sector_hotlist_weight(sector_name, tag_distribution)


def _build_market_style_switch_snapshot(target_date, data, observation_snapshot=None, abnormal_projection=None):
    return run_build_market_style_switch_snapshot(
        target_date,
        data,
        observation_snapshot=observation_snapshot,
        abnormal_projection=abnormal_projection,
        helpers={
            "_safe_float": _safe_float,
            "_round_or_none": _round_or_none,
            "_normalize_kline_date_str": _normalize_kline_date_str,
            "get_previous_date_str": get_previous_date_str,
            "load_data_snapshot": _load_runtime_data_snapshot,
            "_parse_status_board_count": _parse_status_board_count,
            "_count_keyword_hits_in_mapping": _count_keyword_hits_in_mapping,
            "normalize_stock_code": normalize_stock_code,
            "postgres_only_runtime": _POSTGRES_ONLY_RUNTIME,
        },
    )


def _build_unified_sector_strength_rows(data):
    return run_build_unified_sector_strength_rows(
        data,
        helpers={
            "_safe_float": _safe_float,
            "_clamp": _clamp,
            "_score_to_star_rank": _score_to_star_rank,
            "stock_matches_sector": stock_matches_sector,
            "get_previous_date_str": get_previous_date_str,
            "load_data_snapshot": _load_runtime_data_snapshot,
            "sector_name_matches": sector_name_matches,
            "postgres_only_runtime": _POSTGRES_ONLY_RUNTIME,
        },
    )


def get_sector_change_from_quadrant(sector_name, sector_quadrant):
    """从四象限数据获取板块涨跌幅（仅用于内部击球区分析，不用于报告展示）
    
    ⚠️ 重要：为了保持报告数据一致性，展示给用户的涨跌幅统一使用腾讯资金流向数据的zdf字段。
    四象限数据仅用于判断板块是否在击球区、计算质量得分等内部逻辑。
    
    Args:
        sector_name: 板块名称（如"通信设备"）
        sector_quadrant: 四象限数据
    
    Returns:
        float: 涨跌幅，如果未找到返回None
    """
    if not sector_name or not sector_quadrant:
        return None
    
    quadrants = sector_quadrant.get('quadrants', {})
    
    # 在四象限所有区间中查找
    for quadrant_name in ['highStrong', 'highWeak', 'lowStrong', 'lowWeak']:
        for sector in quadrants.get(quadrant_name, []):
            quad_name = sector.get('name', '')
            # 直接匹配或包含关系
            if sector_name == quad_name or sector_name in quad_name or quad_name in sector_name:
                return sector.get('todayChange')
    
    return None


def stock_matches_sector(stock, sector_name):
    """判断股票是否属于指定板块"""
    if not stock or not sector_name:
        return False
    sector = str(stock.get('sector', '') or '')
    if sector and (sector_name in sector or sector in sector_name):
        return True
    for concept in stock.get('concepts', [])[:5]:
        concept = str(concept)
        if concept and (sector_name in concept or concept in sector_name):
            return True
    return False


def sector_name_matches(sector_a, sector_b):
    return analysis_utils.sector_name_matches(sector_a, sector_b)


def get_previous_date_str(target_date):
    """获取前一个交易日近似日期字符串（按自然日回退）"""
    try:
        dt = datetime.datetime.strptime(target_date, "%Y-%m-%d").date()
        prev_dt = dt - datetime.timedelta(days=1)
        return prev_dt.strftime("%Y-%m-%d")
    except Exception:
        return None


def calculate_exit_price_lines(core_stock, stock_full_info):
    return run_calculate_exit_price_lines(
        core_stock,
        stock_full_info,
        helpers={"normalize_stock_code": normalize_stock_code},
    )


# 止损「最近前低」= 与 3~5 日观察期同尺度的短期前低（默认取满 5 个交易日，避免连板股被 20 日远古低点拉得过远）
STOP_PRIOR_LOW_TRADING_DAYS = 5


def compute_stop_loss_mainline_anchor(bars, window=None):
    return run_compute_stop_loss_mainline_anchor(
        bars,
        window=window,
        helpers=_collect_runtime_helpers(_DAILY_PRICE_RUNTIME_HELPER_EXCLUDES),
    )


def _resolve_big_yang_confluence_anchor(recent_bars, target_date='', window=6):
    return run_resolve_big_yang_confluence_anchor(
        recent_bars,
        target_date=target_date,
        window=window,
        helpers=_collect_runtime_helpers(_DAILY_PRICE_RUNTIME_HELPER_EXCLUDES),
    )


def _enrich_stop_plan_with_reference_anchors(stop_plan, stock_code, target_date, recent_bars=None):
    return run_enrich_stop_plan_with_reference_anchors(
        stop_plan,
        stock_code,
        target_date,
        recent_bars=recent_bars,
        helpers=_collect_runtime_helpers(_DAILY_PRICE_RUNTIME_HELPER_EXCLUDES),
    )


def fetch_recent_price_bars(stock_code, target_date, lookback_days=10, fast_fail=False):
    return run_fetch_recent_price_bars(
        stock_code,
        target_date,
        lookback_days=lookback_days,
        fast_fail=fast_fail,
        helpers=_collect_runtime_helpers(_DAILY_PRICE_RUNTIME_HELPER_EXCLUDES),
    )


def fetch_intraday_bars(stock_code, target_date, period='30', lookback_bars=12):
    return run_fetch_intraday_bars(
        stock_code,
        target_date,
        period=period,
        lookback_bars=lookback_bars,
        helpers={"_normalize_kline_date_str": _normalize_kline_date_str},
    )


def _find_latest_intraday_pivot(bars, mode='low'):
    return run_find_latest_intraday_pivot(bars, mode=mode)


def _compute_avg_volume(bars, sample_size=5, exclude_last=False):
    return run_compute_avg_volume(
        bars,
        sample_size=sample_size,
        exclude_last=exclude_last,
    )


def build_intraday_execution_plan(stock_code, target_date, entry_price, signal_type='', fallback_stop=None, entry_cycle_profile=None):
    return run_build_intraday_execution_plan(
        stock_code,
        target_date,
        entry_price,
        signal_type=signal_type,
        fallback_stop=fallback_stop,
        entry_cycle_profile=entry_cycle_profile,
        helpers={
            "fetch_intraday_bars": fetch_intraday_bars,
            "build_stop_execution_plan": build_stop_execution_plan,
            "INTRADAY_CONFIRM_LOOKBACK_60M": INTRADAY_CONFIRM_LOOKBACK_60M,
            "INTRADAY_STOP_LOOKBACK_30M": INTRADAY_STOP_LOOKBACK_30M,
        },
    )


def build_waiting_stock_plan(stock_item, target_date, reason='', signal_type='', recent_bars=None):
    return run_build_waiting_stock_plan(
        stock_item,
        target_date,
        reason=reason,
        signal_type=signal_type,
        recent_bars=recent_bars,
        helpers={
            "build_intraday_execution_plan": build_intraday_execution_plan,
            "build_stop_execution_plan": build_stop_execution_plan,
            "enrich_stop_plan_with_reference_anchors": _enrich_stop_plan_with_reference_anchors,
            "MAX_SINGLE_TRADE_LOSS_PCT": MAX_SINGLE_TRADE_LOSS_PCT,
        },
    )


def get_sector_core_hot_stock(sector_name, hot_rank_top30):
    return run_get_sector_core_hot_stock(
        sector_name,
        hot_rank_top30,
        helpers={"stock_matches_sector": stock_matches_sector},
    )


def get_sector_leader(sector_name, dragon_stocks, dt_pool_by_sector):
    return run_get_sector_leader(
        sector_name,
        dragon_stocks,
        dt_pool_by_sector,
        helpers={"normalize_stock_code": normalize_stock_code},
    )


def _safe_float(value, default=0.0):
    """安全转 float，失败时回退默认值。"""
    try:
        if value in (None, ''):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def build_sector_trend_snapshot(candidates, watchlist, evaluated_stocks, dragon_stocks, zt_pool_by_sector=None, top_n=5):
    return run_build_sector_trend_snapshot(
        candidates,
        watchlist,
        evaluated_stocks,
        dragon_stocks,
        zt_pool_by_sector=zt_pool_by_sector,
        top_n=top_n,
        helpers={
            "normalize_stock_code": normalize_stock_code,
            "stock_matches_sector": stock_matches_sector,
            "_safe_float": _safe_float,
        },
    )


def build_extreme_conviction_list(evaluated_stocks, mainline_name, sector_snapshot=None, top_n=3, risk_context=None):
    return run_build_extreme_conviction_list(
        evaluated_stocks,
        mainline_name,
        sector_snapshot=sector_snapshot,
        top_n=top_n,
        risk_context=risk_context,
        helpers={
            "normalize_stock_code": normalize_stock_code,
            "sector_name_matches": sector_name_matches,
            "_safe_float": _safe_float,
        },
    )


def build_extreme_conviction_groups(evaluated_stocks, mainline_name, sector_snapshot=None, top_n=3, risk_context=None):
    return run_build_extreme_conviction_groups(
        evaluated_stocks,
        mainline_name,
        sector_snapshot=sector_snapshot,
        top_n=top_n,
        risk_context=risk_context,
        helpers={
            "normalize_stock_code": normalize_stock_code,
            "sector_name_matches": sector_name_matches,
            "_safe_float": _safe_float,
        },
    )


def build_leader_memory_bank(sector_snapshot, watchlist, dragon_stocks, hot_rank_top30=None, top_n=5):
    return run_build_leader_memory_bank(
        sector_snapshot,
        watchlist,
        dragon_stocks,
        hot_rank_top30=hot_rank_top30,
        top_n=top_n,
        helpers={
            "normalize_stock_code": normalize_stock_code,
            "_safe_float": _safe_float,
        },
    )


def _resolve_abnormal_setup_signal(abnormal_type, follow_state):
    abnormal_type = str(abnormal_type or '').strip()
    follow_state = str(follow_state or '').strip()

    if follow_state == '新异动待观察':
        setup_id = 'fresh_abnormal_probe'
    elif follow_state == '已经转弱':
        setup_id = 'abnormal_failed'
    elif abnormal_type == '放量大阳异动':
        setup_id = 'burst_hold' if follow_state == '跌不下去' else 'burst_digest'
    elif abnormal_type == '长上影异动':
        setup_id = 'upper_shadow_reclaim' if follow_state == '跌不下去' else 'upper_shadow_digest'
    elif abnormal_type == '恐怖阴线异动':
        setup_id = 'horror_wash_hold' if follow_state == '跌不下去' else 'horror_wash_digest'
    else:
        setup_id = 'abnormal_failed' if follow_state == '已经转弱' else 'fresh_abnormal_probe'

    setup_meta = ABNORMAL_SETUP_LIBRARY.get(setup_id, ABNORMAL_SETUP_LIBRARY['abnormal_failed'])
    return {
        'id': setup_id,
        'label': setup_meta.get('label', setup_id),
        'phase': setup_meta.get('phase', ''),
        'group': setup_meta.get('group', ''),
        'abnormal_type': abnormal_type,
        'follow_state': follow_state,
    }


def _build_abnormal_follow_rule(abnormal_type, follow_state, anchor_price, abnormal_info):
    return run_build_abnormal_follow_rule(
        abnormal_type,
        follow_state,
        anchor_price,
        abnormal_info,
        helpers=_collect_runtime_helpers(_OBSERVATION_PLAN_FORMATTER_HELPER_EXCLUDES),
    )


def _refine_abnormal_follow_display(anchor_price, action_rule, minute_plan=None):
    return run_refine_abnormal_follow_display(
        anchor_price,
        action_rule,
        minute_plan,
        helpers=_collect_runtime_helpers(_OBSERVATION_PLAN_FORMATTER_HELPER_EXCLUDES),
    )


def _format_abnormal_observation_columns(item):
    return run_format_abnormal_observation_columns(
        item,
        helpers=_collect_runtime_helpers(_OBSERVATION_PLAN_FORMATTER_HELPER_EXCLUDES),
    )


def _format_frozen_plan_columns(plan):
    return run_format_frozen_plan_columns(
        plan,
        helpers=_collect_runtime_helpers(_OBSERVATION_PLAN_FORMATTER_HELPER_EXCLUDES),
    )


def build_abnormal_watch_pool(
    target_date,
    candidate_stocks,
    mainline_name='',
    top_n=5,
    scan_limit=None,
    allow_degraded_snapshot=False,
    fast_fail=False,
):
    return run_build_abnormal_watch_pool(
        target_date,
        candidate_stocks,
        mainline_name=mainline_name,
        top_n=top_n,
        scan_limit=scan_limit,
        allow_degraded_snapshot=allow_degraded_snapshot,
        fast_fail=fast_fail,
        helpers={
            "normalize_stock_code": normalize_stock_code,
            "fetch_recent_price_bars": fetch_recent_price_bars,
            "sector_name_matches": sector_name_matches,
            "_safe_float": _safe_float,
            "_resolve_abnormal_setup_signal": _resolve_abnormal_setup_signal,
            "_map_setup_id_to_signal_type": _map_setup_id_to_signal_type,
            "build_intraday_execution_plan": build_intraday_execution_plan,
            "MAX_SINGLE_TRADE_LOSS_PCT": MAX_SINGLE_TRADE_LOSS_PCT,
            "_build_abnormal_follow_rule": _build_abnormal_follow_rule,
            "_refine_abnormal_follow_display": _refine_abnormal_follow_display,
            "_round_or_none": _round_or_none,
        },
    )


def get_abnormal_rank_adjustment(abnormal_item):
    return analysis_utils.get_abnormal_rank_adjustment(abnormal_item)


def get_abnormal_follow_risk_signal(stock):
    return run_get_abnormal_follow_risk_signal(
        stock,
        helpers={
            "_is_degraded_abnormal_snapshot": _is_degraded_abnormal_snapshot,
        },
    )


def get_trade_permission(
    stock,
    mainline_name='',
    conviction_codes=None,
    leader_memory_codes=None,
    final_gate=None,
    state_machine_snapshot=None,
):
    """根据环境条件 + 主线脉冲阶段 + 个股承接，分配交易资格。"""
    weak_to_strong_context = _build_weak_to_strong_context(
        candidate=stock,
        mainline_name=mainline_name,
        state_machine_snapshot=state_machine_snapshot,
    )
    return get_trade_permission_contract(
        stock,
        mainline_name=mainline_name,
        conviction_codes=conviction_codes,
        leader_memory_codes=leader_memory_codes,
        final_gate=final_gate,
        state_machine_snapshot=state_machine_snapshot,
        weak_to_strong_context=weak_to_strong_context,
    )


def build_mainline_exit_analysis(data, market_analysis, dragon_stocks, enhanced_main_sectors=None):
    result = run_market_state_analysis(
        {
            "inputs": {
                "data": data,
                "market_analysis": market_analysis,
                "dragon_stocks": dragon_stocks,
                "enhanced_main_sectors": enhanced_main_sectors or [],
            },
            "helpers": {
                "action_map": {
                    "绿灯": "主线健康，可继续做",
                    "黄灯": "主升强化，优先做核心",
                    "橙灯": "退潮预警，禁止新增",
                    "红灯": "退潮确认，尽快退出",
                },
                "get_sector_hotlist_weight": get_sector_hotlist_weight,
                "load_recent_sector_flow_history": load_recent_sector_flow_history,
                "get_mainline_star_level": get_mainline_star_level,
                "score_to_level": _score_to_level,
                "level_to_score": _level_to_score,
                "safe_float": _safe_float,
                "clamp": _clamp,
                "get_sector_leader": get_sector_leader,
                "get_sector_core_hot_stock": get_sector_core_hot_stock,
                "normalize_stock_code": normalize_stock_code,
                "calculate_exit_price_lines": calculate_exit_price_lines,
                "fetch_recent_price_bars": fetch_recent_price_bars,
                "compute_stop_loss_mainline_anchor": compute_stop_loss_mainline_anchor,
                "analyze_event_sector": analyze_event_sector,
            },
        }
    )
    return (result.get("exports") or {}).get("exit_analysis") or {}


def merge_position_gate(position_level, exit_analysis):
    return analysis_utils.merge_position_gate(position_level, exit_analysis)


def build_market_phase_context(data, target_date, emit_logs=True):
    """构建日报/单票共用的市场环境上下文，避免不同入口各自推导。"""
    zhongshu_analyzer = (
        _postgres_only_analyze_market_zhongshu
        if _POSTGRES_ONLY_RUNTIME
        else analyze_market_zhongshu
    )
    result = build_market_phase_context_contract(
        data,
        target_date,
        analyze_market_zhongshu=zhongshu_analyzer,
        analyze_market_and_sectors=analyze_market_and_sectors,
        resolve_market_mainline_context=_resolve_market_mainline_context,
        build_mainline_exit_analysis=build_mainline_exit_analysis,
        merge_position_gate=merge_position_gate,
        build_market_state_machine_snapshot=_build_market_state_machine_snapshot,
        resolve_environment_display_contract=_resolve_environment_display_contract,
        calculate_price_range=calculate_price_range,
        market_zhongshu_lookback_days=MARKET_ZHONGSHU_LOOKBACK_DAYS,
        market_zhongshu_min_klines=MARKET_ZHONGSHU_MIN_KLINES,
    )
    if emit_logs:
        for log in result.get('module_logs', []):
            message = str(log.get('message', '') or '').strip()
            if message:
                print(f"   🧩 {message}")
    return result


_daily_price_bar_cache = {}
_baostock_runtime_state = {
    'logged_in': False,
    'logout_registered': False,
}


def _logout_baostock_silently():
    try:
        import baostock as bs
        import contextlib
        import io

        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            bs.logout()
    except Exception:
        pass
    finally:
        _baostock_runtime_state['logged_in'] = False


def _ensure_baostock_login():
    if _baostock_runtime_state.get('logged_in'):
        return True

    try:
        import atexit
        import baostock as bs
        import contextlib
        import io

        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            login_result = bs.login()
        success = getattr(login_result, 'error_code', '') == '0'
        if success:
            _baostock_runtime_state['logged_in'] = True
            if not _baostock_runtime_state.get('logout_registered'):
                atexit.register(_logout_baostock_silently)
                _baostock_runtime_state['logout_registered'] = True
        return success
    except Exception:
        _baostock_runtime_state['logged_in'] = False
        return False


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _round_or_none(value, digits=2):
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def _build_trade_price_focus(minute_plan=None, stop_plan=None):
    return run_build_trade_price_focus(
        minute_plan,
        stop_plan,
        helpers={
            "_safe_float": _safe_float,
            "_round_or_none": _round_or_none,
            "_same_price_level": analysis_utils._same_price_level,
            "_is_near_anchor_price": analysis_utils._is_near_anchor_price,
        },
    )


def _normalize_observation_zone_badge(zone_badge):
    return run_normalize_observation_zone_badge(
        zone_badge,
        helpers=_collect_runtime_helpers(_OBSERVATION_PRICE_FORMATTER_HELPER_EXCLUDES),
    )


def _build_observation_price_focus_text(price_focus):
    return run_build_observation_price_focus_text(
        price_focus,
        helpers=_collect_runtime_helpers(_OBSERVATION_PRICE_FORMATTER_HELPER_EXCLUDES),
    )


def _build_observation_price_note_text(price_focus):
    return run_build_observation_price_note_text(
        price_focus,
        helpers=_collect_runtime_helpers(_OBSERVATION_PRICE_FORMATTER_HELPER_EXCLUDES),
    )


def _should_surface_price_note(price_focus):
    return run_should_surface_price_note(
        price_focus,
        helpers=_collect_runtime_helpers(_OBSERVATION_PRICE_FORMATTER_HELPER_EXCLUDES),
    )


def _append_price_focus_note(lines, price_focus, prefix='  '):
    return run_append_price_focus_note(
        lines,
        price_focus,
        prefix,
        helpers=_collect_runtime_helpers(_OBSERVATION_PRICE_FORMATTER_HELPER_EXCLUDES),
    )


def _append_observation_price_focus_note(lines, price_focus, prefix='  '):
    return run_append_observation_price_focus_note(
        lines,
        price_focus,
        prefix,
        helpers=_collect_runtime_helpers(_OBSERVATION_PRICE_FORMATTER_HELPER_EXCLUDES),
    )


def _get_run_mode_label(mode):
    return run_get_run_mode_label(mode)


def _get_strategy_performance_path(mode=LEDGER_MODE_FROZEN):
    return run_get_strategy_performance_path(mode=mode, helpers=_collect_runtime_helpers(_STRATEGY_STORE_HELPER_EXCLUDES))


def _get_snapshot_path(target_date, mode=LEDGER_MODE_FROZEN):
    return run_get_snapshot_path(target_date, mode=mode)


def _get_factor_snapshot_path(target_date, mode=LEDGER_MODE_FROZEN):
    return run_get_factor_snapshot_path(target_date, mode=mode, helpers=_collect_runtime_helpers(_STRATEGY_STORE_HELPER_EXCLUDES))


def load_strategy_performance_ledger(mode=LEDGER_MODE_FROZEN):
    return run_load_strategy_performance_ledger(mode=mode, helpers=_collect_runtime_helpers())


def save_strategy_performance_ledger(ledger, mode=LEDGER_MODE_FROZEN):
    return run_save_strategy_performance_ledger(ledger, mode=mode, helpers=_collect_runtime_helpers())


def save_factor_snapshot(target_date, factor_snapshot, mode=LEDGER_MODE_FROZEN):
    return run_save_factor_snapshot(target_date, factor_snapshot, mode=mode, helpers=_collect_runtime_helpers())


def _to_bs_code(security_code, is_index=False):
    return run_to_bs_code(security_code, is_index=is_index, helpers=_collect_runtime_helpers(_DAILY_PRICE_RUNTIME_HELPER_EXCLUDES))


def _run_with_wall_clock_timeout(seconds, fn, *args, default=None, **kwargs):
    return run_run_with_wall_clock_timeout(
        seconds,
        fn,
        *args,
        default=default,
        helpers=_collect_runtime_helpers(_DAILY_PRICE_RUNTIME_HELPER_EXCLUDES),
        **kwargs,
    )


def _fetch_quicktiny_daily_price_bars(security_code, start_date, end_date, is_index=False):
    return run_fetch_quicktiny_daily_price_bars(
        security_code,
        start_date,
        end_date,
        is_index=is_index,
        helpers=_collect_runtime_helpers(_DAILY_PRICE_RUNTIME_HELPER_EXCLUDES),
    )


def _merge_daily_price_bars(primary_bars, fallback_bars):
    return run_merge_daily_price_bars(
        primary_bars,
        fallback_bars,
        helpers=_collect_runtime_helpers(_DAILY_PRICE_RUNTIME_HELPER_EXCLUDES),
    )


def fetch_daily_price_bars(
    security_code,
    start_date,
    end_date,
    is_index=False,
    prefer_fast=False,
    allow_baostock_fallback=True,
):
    return run_fetch_daily_price_bars(
        security_code,
        start_date,
        end_date,
        is_index=is_index,
        prefer_fast=prefer_fast,
        allow_baostock_fallback=allow_baostock_fallback,
        helpers=_collect_runtime_helpers(_DAILY_PRICE_RUNTIME_HELPER_EXCLUDES),
    )


def _get_first_bar_after(bars, after_date):
    return run_get_first_bar_after(bars, after_date, helpers=_collect_runtime_helpers(_DAILY_PRICE_RUNTIME_HELPER_EXCLUDES))


def _get_first_bar_on_or_after(bars, target_date):
    return run_get_first_bar_on_or_after(bars, target_date, helpers=_collect_runtime_helpers(_DAILY_PRICE_RUNTIME_HELPER_EXCLUDES))


def _get_last_bar_on_or_before(bars, target_date):
    return run_get_last_bar_on_or_before(bars, target_date, helpers=_collect_runtime_helpers(_DAILY_PRICE_RUNTIME_HELPER_EXCLUDES))


def _is_next_trading_day(prev_date, curr_date):
    return run_is_next_trading_day(prev_date, curr_date, helpers=_collect_runtime_helpers(_DAILY_PRICE_RUNTIME_HELPER_EXCLUDES))


def _count_trading_days_between(start_date, end_date):
    return run_count_trading_days_between(start_date, end_date, helpers=_collect_runtime_helpers(_DAILY_PRICE_RUNTIME_HELPER_EXCLUDES))


def _get_limit_up_pct(stock_code='', stock_name=''):
    return run_get_limit_up_pct(stock_code=stock_code, stock_name=stock_name, helpers=_collect_runtime_helpers(_DAILY_PRICE_RUNTIME_HELPER_EXCLUDES))


def _is_one_word_limit_bar(stock_code='', stock_name='', open_price=None, high_price=None, low_price=None, close_price=None, change_pct=None):
    return run_is_one_word_limit_bar(
        stock_code=stock_code,
        stock_name=stock_name,
        open_price=open_price,
        high_price=high_price,
        low_price=low_price,
        close_price=close_price,
        change_pct=change_pct,
        helpers=_collect_runtime_helpers(_DAILY_PRICE_RUNTIME_HELPER_EXCLUDES),
    )


def _compute_bar_change_pct(current_bar, prev_bar=None):
    return run_compute_bar_change_pct(current_bar, prev_bar=prev_bar, helpers=_collect_runtime_helpers(_DAILY_PRICE_RUNTIME_HELPER_EXCLUDES))


def evaluate_live_tradability(stock, target_date='', recent_bars=None):
    return run_evaluate_live_tradability(
        stock,
        target_date=target_date,
        recent_bars=recent_bars,
        helpers=_collect_runtime_helpers(_DAILY_PRICE_RUNTIME_HELPER_EXCLUDES),
    )


def _compound_returns(values):
    return run_compound_returns(values)


def _format_pct(value):
    return run_format_pct(value)


def _format_pct_range(low_value, high_value):
    return run_format_pct_range(low_value, high_value)


def _get_strategy_status_label(status, note=''):
    return run_get_strategy_status_label(status, note)


def _get_plan_action_label(action_type, position_pct=None):
    return run_get_plan_action_label(action_type, position_pct)


def _get_signal_type_label(signal_type):
    return run_get_signal_type_label(signal_type)


def _backfill_strategy_record_market_context(record):
    return run_backfill_strategy_record_market_context(record)


def _build_trade_return_stats(records):
    return run_build_trade_return_stats(records)


def _summarize_ev_signal_review(records, start_date, end_date):
    return run_summarize_ev_signal_review(records, start_date, end_date)


def build_strategy_ev_calibration(as_of_date, ledger_mode=LEDGER_MODE_FROZEN):
    return run_build_strategy_ev_calibration(
        as_of_date,
        ledger_mode=ledger_mode,
        helpers=_collect_runtime_helpers(_STRATEGY_EV_HELPER_EXCLUDES),
    )


def estimate_signal_type_ev(signal_type, loss_space_pct, calibration):
    return run_estimate_signal_type_ev(
        signal_type,
        loss_space_pct,
        calibration,
        helpers=_collect_runtime_helpers(_STRATEGY_EV_HELPER_EXCLUDES),
    )


def score_execution_candidate(candidate, ev_calibration):
    return run_score_execution_candidate(
        candidate,
        ev_calibration,
        helpers=_collect_runtime_helpers(_STRATEGY_EV_HELPER_EXCLUDES),
    )


def score_candidate_decision_stack(
    candidate,
    final_gate=None,
    mainline_name='',
    conviction_codes=None,
    leader_memory_codes=None,
    state_machine_snapshot=None,
    target_date='',
):
    return run_score_candidate_decision_stack(
        candidate,
        final_gate=final_gate,
        mainline_name=mainline_name,
        conviction_codes=conviction_codes,
        leader_memory_codes=leader_memory_codes,
        state_machine_snapshot=state_machine_snapshot,
        target_date=target_date,
        helpers={
            "normalize_stock_code": normalize_stock_code,
            "sector_name_matches": sector_name_matches,
            "_resolve_candidate_follow_state": _resolve_candidate_follow_state,
            "_resolve_candidate_setup_id": _resolve_candidate_setup_id,
            "_is_one_word_limit_bar": _is_one_word_limit_bar,
            "_get_setup_priority_score": _get_setup_priority_score,
            "_build_washout_reclaim_context": _build_washout_reclaim_context,
            "_build_trend_continuation_context": _build_trend_continuation_context,
            "_candidate_has_formal_abnormal_setup": _candidate_has_formal_abnormal_setup,
            "_candidate_is_resilient_abnormal": _candidate_is_resilient_abnormal,
            "_safe_float": _safe_float,
            "_clamp": _clamp,
            "DECISION_STACK_ORDER_TEXT": DECISION_STACK_ORDER_TEXT,
        },
    )


def sort_decision_stack_candidates(candidates):
    return run_sort_decision_stack_candidates(
        candidates,
        helpers={"_safe_float": _safe_float},
    )


def _classify_watch_anchor_bucket(candidate):
    return run_classify_watch_anchor_bucket(
        candidate,
        helpers={"_safe_float": _safe_float},
    )


def _candidate_matches_mainline(candidate, mainline_name=''):
    return analysis_utils._candidate_matches_mainline(candidate, mainline_name)


def _requires_crossline_second_confirmation(candidate, mainline_name=''):
    return run_requires_crossline_second_confirmation(
        candidate,
        mainline_name,
        helpers={
            "_candidate_matches_mainline": _candidate_matches_mainline,
            "_resolve_candidate_setup_id": _resolve_candidate_setup_id,
            "_resolve_candidate_follow_state": _resolve_candidate_follow_state,
        },
    )


def _is_washout_reclaim_setup_id(setup_id=''):
    return str(setup_id or '').strip() in ('burst_hold', 'upper_shadow_reclaim', 'horror_wash_hold')


def _build_washout_reclaim_context(candidate, mainline_name='', conviction_codes=None, leader_memory_codes=None, target_date=''):
    return run_build_washout_reclaim_context(
        candidate,
        mainline_name,
        conviction_codes,
        leader_memory_codes,
        target_date,
        helpers={
            "normalize_stock_code": normalize_stock_code,
            "_candidate_matches_mainline": _candidate_matches_mainline,
            "_resolve_candidate_setup_id": _resolve_candidate_setup_id,
            "_resolve_candidate_follow_state": _resolve_candidate_follow_state,
            "_normalize_kline_date_str": _normalize_kline_date_str,
            "_parse_kline_date": _parse_kline_date,
        },
    )


def _build_trend_continuation_context(candidate, mainline_name='', conviction_codes=None, leader_memory_codes=None, target_date=''):
    return run_build_trend_continuation_context(
        candidate,
        mainline_name,
        conviction_codes,
        leader_memory_codes,
        target_date,
        helpers={
            "normalize_stock_code": normalize_stock_code,
            "_candidate_matches_mainline": _candidate_matches_mainline,
            "_normalize_kline_date_str": _normalize_kline_date_str,
            "fetch_recent_price_bars": fetch_recent_price_bars,
            "_safe_float": _safe_float,
            "_round_or_none": _round_or_none,
        },
    )


def _resolve_primary_mainline_name(market_research_snapshot=None, fallback_mainline=''):
    return run_resolve_primary_mainline_name(
        market_research_snapshot,
        fallback_mainline,
        helpers={},
    )


def _split_candidates_by_mainline(candidates, mainline_name=''):
    return run_split_candidates_by_mainline(
        candidates,
        mainline_name,
        helpers={"_candidate_matches_mainline": _candidate_matches_mainline},
    )


def _candidate_confirmation_chain(candidate=None):
    return run_candidate_confirmation_chain(candidate)


def _resolve_probe_role_family(probe_role='', watch_anchor_type='', anchor_type=''):
    return run_resolve_probe_role_family(probe_role, watch_anchor_type, anchor_type)


def _iter_record_probe_candidates(record):
    return run_iter_record_probe_candidates(record)


def _build_candidate_history_feedback(candidate=None, target_date='', probe_role='', watch_anchor_type=''):
    return run_build_candidate_history_feedback(candidate, target_date, probe_role, watch_anchor_type)


def _extract_candidate_report_prices(candidate=None):
    return run_extract_candidate_report_prices(candidate)


def _build_candidate_feedback_clock(candidate=None, watch_anchor_type='', state_machine_snapshot=None, mainline_name='', target_date=''):
    return run_build_candidate_feedback_clock(candidate, watch_anchor_type, state_machine_snapshot, mainline_name, target_date)


def _build_position_sizing_decision(
    final_gate=None,
    state_machine_snapshot=None,
    best_stock=None,
    watch_anchor=None,
    watch_anchor_type='',
    mainline_name='',
    target_date='',
    special_probe_verdict=None,
    mainline_anchor=None,
    monthly_context=None,
):
    return run_build_position_sizing_decision(
        final_gate=final_gate,
        state_machine_snapshot=state_machine_snapshot,
        best_stock=best_stock,
        watch_anchor=watch_anchor,
        watch_anchor_type=watch_anchor_type,
        mainline_name=mainline_name,
        target_date=target_date,
        special_probe_verdict=special_probe_verdict,
        mainline_anchor=mainline_anchor,
        monthly_context=monthly_context,
        helpers={
            "_build_candidate_feedback_clock": _build_candidate_feedback_clock,
            "_classify_20cm_branch": _classify_20cm_branch,
            "_build_weak_to_strong_context": _build_weak_to_strong_context,
            "_is_bridge_priority_setup": _is_bridge_priority_setup,
            "_round_or_none": _round_or_none,
        },
    )


def _build_execute_anchor_window_text(position_decision=None, watch_anchor=None, watch_anchor_type=''):
    return run_build_execute_anchor_window_text(
        position_decision=position_decision,
        watch_anchor=watch_anchor,
        watch_anchor_type=watch_anchor_type,
        helpers={
            "_safe_float": _safe_float,
            "_round_or_none": _round_or_none,
        },
    )


def _build_cycle_triplet_texts(position_decision=None, candidate=None, watch_anchor_type=''):
    return run_build_cycle_triplet_texts(
        position_decision=position_decision,
        candidate=candidate,
        watch_anchor_type=watch_anchor_type,
        helpers={
            "_safe_float": _safe_float,
            "_round_or_none": _round_or_none,
            "_build_execute_anchor_window_text": _build_execute_anchor_window_text,
            "_build_candidate_exit_rules": _build_candidate_exit_rules,
            "_format_holding_window_text": _format_holding_window_text,
        },
    )


def _format_candidate_preview(candidates, formatter, limit=3):
    return run_format_candidate_preview(candidates, formatter, limit=limit, helpers={})


def _derive_watch_anchor_type(candidate, mainline_name=''):
    return run_derive_watch_anchor_type(
        candidate,
        mainline_name,
        helpers={
            "_safe_float": _safe_float,
            "_candidate_matches_mainline": _candidate_matches_mainline,
            "_resolve_candidate_setup_id": _resolve_candidate_setup_id,
            "_resolve_candidate_follow_state": _resolve_candidate_follow_state,
        },
    )


def _derive_pending_candidate_type(candidate, mainline_name=''):
    return run_derive_pending_candidate_type(
        candidate,
        mainline_name,
        helpers={
            "_safe_float": _safe_float,
            "_candidate_matches_mainline": _candidate_matches_mainline,
        },
    )


def _derive_watch_anchor_note(candidate, mainline_name=''):
    return run_derive_watch_anchor_note(
        candidate,
        mainline_name,
        helpers={
            "_safe_float": _safe_float,
            "_candidate_matches_mainline": _candidate_matches_mainline,
            "_resolve_candidate_setup_id": _resolve_candidate_setup_id,
            "_resolve_candidate_follow_state": _resolve_candidate_follow_state,
        },
    )


def _append_watch_anchor_note(report_lines, candidate, prefix='  '):
    return run_append_watch_anchor_note(
        report_lines,
        candidate,
        prefix=prefix,
        helpers={},
    )


def _compose_observation_focus_text(confirm_text, price_focus_text=''):
    return run_compose_observation_focus_text(
        confirm_text,
        price_focus_text,
        helpers=_collect_runtime_helpers(_OBSERVATION_PRICE_FORMATTER_HELPER_EXCLUDES),
    )


def _build_bridge_prep_context(
    position_level='',
    final_gate=None,
    watch_anchor=None,
    watch_anchor_type='',
    state_machine_snapshot=None,
):
    return run_build_bridge_prep_context(
        position_level=position_level,
        final_gate=final_gate,
        watch_anchor=watch_anchor,
        watch_anchor_type=watch_anchor_type,
        state_machine_snapshot=state_machine_snapshot,
    )


def _build_front_follow_action_text(
    final_gate=None,
    best_stock=None,
    watch_anchor=None,
    watch_anchor_type='',
    fallback_text='',
    focus_group=None,
    keep_group=None,
    delete_group=None,
    position_level='',
    state_machine_snapshot=None,
    target_date='',
    special_probe_verdict=None,
):
    return run_build_front_follow_action_text(
        final_gate=final_gate,
        best_stock=best_stock,
        watch_anchor=watch_anchor,
        watch_anchor_type=watch_anchor_type,
        fallback_text=fallback_text,
        focus_group=focus_group,
        keep_group=keep_group,
        delete_group=delete_group,
        position_level=position_level,
        state_machine_snapshot=state_machine_snapshot,
        target_date=target_date,
        special_probe_verdict=special_probe_verdict,
    )


def _front_position_guard_label(position_level=''):
    return run_front_position_guard_label(position_level, helpers={})


def _build_front_structure_layer_text(
    final_gate=None,
    focus_group=None,
    keep_group=None,
    delete_group=None,
    best_stock=None,
    watch_anchor=None,
    watch_anchor_type='',
    position_level='',
    state_machine_snapshot=None,
    target_date='',
    special_probe_verdict=None,
):
    return run_build_front_structure_layer_text(
        final_gate=final_gate,
        focus_group=focus_group,
        keep_group=keep_group,
        delete_group=delete_group,
        best_stock=best_stock,
        watch_anchor=watch_anchor,
        watch_anchor_type=watch_anchor_type,
        position_level=position_level,
        state_machine_snapshot=state_machine_snapshot,
        target_date=target_date,
        special_probe_verdict=special_probe_verdict,
    )


def sort_watch_anchor_candidates(candidates, mainline_name='', state_machine_snapshot=None):
    return run_sort_watch_anchor_candidates(
        candidates,
        mainline_name=mainline_name,
        state_machine_snapshot=state_machine_snapshot,
        helpers={
            "_safe_float": _safe_float,
            "_classify_watch_anchor_bucket": _classify_watch_anchor_bucket,
            "_candidate_has_formal_abnormal_setup": _candidate_has_formal_abnormal_setup,
            "_candidate_is_resilient_abnormal": _candidate_is_resilient_abnormal,
            "_build_weak_to_strong_context": _build_weak_to_strong_context,
            "_is_bridge_priority_setup": _is_bridge_priority_setup,
            "_derive_watch_anchor_type": _derive_watch_anchor_type,
            "_derive_watch_anchor_note": _derive_watch_anchor_note,
        },
    )


def _decorate_probe_candidate(candidate, mainline_name='', pending_mode=False, explicit_type=''):
    if not candidate:
        return None

    probe = dict(candidate or {})
    if explicit_type:
        probe['watch_anchor_type'] = explicit_type
    elif not probe.get('watch_anchor_type'):
        if pending_mode:
            probe['watch_anchor_type'] = _derive_pending_candidate_type(probe, mainline_name=mainline_name)
        else:
            probe['watch_anchor_type'] = _derive_watch_anchor_type(probe, mainline_name=mainline_name)
    if (
        probe.get('watch_anchor_type') == '重点观察谁'
        and mainline_name
        and not _candidate_matches_mainline(probe, mainline_name)
    ):
        probe['watch_anchor_type'] = '跨线重点观察谁'

    if not probe.get('watch_anchor_note'):
        probe['watch_anchor_note'] = _derive_watch_anchor_note(probe, mainline_name=mainline_name)
    return probe


def _build_abnormal_watch_anchor_candidates(
    abnormal_watch_pool=None,
    existing_candidates=None,
    seed_candidates=None,
    target_date='',
    mainline_name='',
    final_gate=None,
    conviction_codes=None,
    leader_memory_codes=None,
    ev_calibration=None,
    state_machine_snapshot=None,
):
    return run_build_abnormal_watch_anchor_candidates(
        abnormal_watch_pool=abnormal_watch_pool,
        existing_candidates=existing_candidates,
        seed_candidates=seed_candidates,
        target_date=target_date,
        mainline_name=mainline_name,
        final_gate=final_gate,
        conviction_codes=conviction_codes,
        leader_memory_codes=leader_memory_codes,
        ev_calibration=ev_calibration,
        state_machine_snapshot=state_machine_snapshot,
    )


def _build_abnormal_probe_group(
    style_switch_snapshot=None,
    abnormal_watch_pool=None,
    mainline_name='',
    watch_anchor=None,
):
    return run_build_abnormal_probe_group(
        style_switch_snapshot=style_switch_snapshot,
        abnormal_watch_pool=abnormal_watch_pool,
        mainline_name=mainline_name,
        watch_anchor=watch_anchor,
    )


def _format_abnormal_probe_text(
    probe,
    role_label='',
    mainline_name='',
    fallback_watch_anchor=None,
):
    return run_format_abnormal_probe_text(
        probe,
        role_label=role_label,
        mainline_name=mainline_name,
        fallback_watch_anchor=fallback_watch_anchor,
        helpers={
            "_candidate_matches_mainline": _candidate_matches_mainline,
        },
    )


def _build_mainline_upgrade_probe_context(candidate=None, mainline_name='', target_date=''):
    return run_build_mainline_upgrade_probe_context(
        candidate=candidate,
        mainline_name=mainline_name,
        target_date=target_date,
        helpers={
            "_candidate_matches_mainline": _candidate_matches_mainline,
            "_build_candidate_feedback_clock": _build_candidate_feedback_clock,
            "_safe_float": _safe_float,
        },
    )


def _is_20cm_stock(candidate=None):
    return run_is_20cm_stock(candidate, helpers={"normalize_stock_code": normalize_stock_code})


def _evaluate_gem_breathing_window(bars=None, lookback_days=10):
    return run_evaluate_gem_breathing_window(
        bars,
        lookback_days=lookback_days,
        helpers={"_safe_float": _safe_float},
    )


def _build_gem_breathing_prep_context(candidate=None, target_date='', lookback_days=10):
    return run_build_gem_breathing_prep_context(
        candidate=candidate,
        target_date=target_date,
        lookback_days=lookback_days,
        helpers={
            "normalize_stock_code": normalize_stock_code,
            "_normalize_kline_date_str": _normalize_kline_date_str,
            "_parse_kline_date": _parse_kline_date,
            "fetch_daily_price_bars": fetch_daily_price_bars,
            "_evaluate_gem_breathing_window": _evaluate_gem_breathing_window,
        },
    )


def _get_gem_stock_universe():
    global _gem_stock_universe_cache
    if _gem_stock_universe_cache is not None:
        return [dict(item) for item in _gem_stock_universe_cache]

    items = []
    try:
        basic_map = run_fetch_stock_basic_map() or {}
        seen_codes = set()
        for raw_code, meta in basic_map.items():
            code = normalize_stock_code(raw_code)
            if not code.startswith('30') or code in seen_codes:
                continue
            seen_codes.add(code)
            items.append({
                'code': code,
                'name': str((meta or {}).get('name', '') or '').strip(),
            })
    except Exception:
        items = []
    if items:
        _gem_stock_universe_cache = [dict(item) for item in items]
        return [dict(item) for item in items]

    try:
        import akshare as ak
        df = ak.stock_info_a_code_name()
    except Exception:
        return []
    items = []
    for _, row in df.iterrows():
        code = normalize_stock_code(row.get('code', ''))
        if not code.startswith('30'):
            continue
        items.append({
            'code': code,
            'name': str(row.get('name', '') or '').strip(),
        })
    _gem_stock_universe_cache = [dict(item) for item in items]
    return [dict(item) for item in items]


def _discover_all_gem_breathing_candidates(stock_meta_map, target_date=''):
    return run_discover_all_gem_breathing_candidates(
        stock_meta_map,
        target_date=target_date,
        helpers={
            "normalize_stock_code": normalize_stock_code,
            "_get_gem_stock_universe": _get_gem_stock_universe,
            "_build_gem_breathing_prep_context": _build_gem_breathing_prep_context,
            "_safe_float": _safe_float,
        },
    )


def _discover_gem_breathing_candidates(stock_meta_map, target_date='', mainline_name='', limit=3):
    return run_discover_gem_breathing_candidates(
        stock_meta_map,
        target_date=target_date,
        mainline_name=mainline_name,
        limit=limit,
        helpers={
            "_discover_all_gem_breathing_candidates": _discover_all_gem_breathing_candidates,
            "_candidate_matches_mainline": _candidate_matches_mainline,
        },
    )


def _discover_filtered_out_gem_breathing_candidates(stock_meta_map, target_date='', mainline_name='', limit=3):
    return run_discover_filtered_out_gem_breathing_candidates(
        stock_meta_map,
        target_date=target_date,
        mainline_name=mainline_name,
        limit=limit,
        helpers={
            "_discover_all_gem_breathing_candidates": _discover_all_gem_breathing_candidates,
            "_candidate_matches_mainline": _candidate_matches_mainline,
        },
    )


def _build_gem_breathing_textbook_profile(candidate=None, target_date='', lookback_days=10, review_days=60):
    return run_build_gem_breathing_textbook_profile(
        candidate=candidate,
        target_date=target_date,
        lookback_days=lookback_days,
        review_days=review_days,
        helpers={
            "normalize_stock_code": normalize_stock_code,
            "_normalize_kline_date_str": _normalize_kline_date_str,
            "fetch_daily_price_bars": fetch_daily_price_bars,
            "_evaluate_gem_breathing_window": _evaluate_gem_breathing_window,
        },
    )


def _build_gem_20cm_observation_pool(gem_breathing_candidates=None, target_date=''):
    return run_build_gem_observation_pool(
        gem_breathing_candidates,
        target_date=target_date,
        helpers={
            "build_gem_breathing_textbook_profile": _build_gem_breathing_textbook_profile,
            "_safe_float": _safe_float,
        },
    )


def _render_gem_breathing_step2_section(gem_observation_stocks=None, filtered_out_gem_candidates=None, display_mvp_mode=None):
    return render_gem_breathing_step2_section(
        {
            "gem_observation_stocks": gem_observation_stocks or [],
            "filtered_out_gem_candidates": filtered_out_gem_candidates or [],
            "display_mvp_mode": DISPLAY_MVP_MODE if display_mvp_mode is None else display_mvp_mode,
        }
    )


def _render_gem_breathing_pool_section(gem_observation_stocks=None, filtered_out_gem_candidates=None):
    return render_gem_breathing_pool_section(
        {
            "gem_observation_stocks": gem_observation_stocks or [],
            "filtered_out_gem_candidates": filtered_out_gem_candidates or [],
        }
    )


def _build_gem_breathing_contract(candidate=None):
    return run_build_gem_breathing_contract(
        candidate,
        helpers={
            "_safe_float": _safe_float,
            "_round_or_none": _round_or_none,
            "STRATEGY_HOLDING_DAYS_MAX": STRATEGY_HOLDING_DAYS_MAX,
        },
    )


def _build_gem_breathing_watch_anchor(gem_candidate=None, target_date='', mainline_name=''):
    return run_build_gem_breathing_watch_anchor(
        gem_candidate,
        target_date=target_date,
        mainline_name=mainline_name,
        helpers={
            "normalize_stock_code": normalize_stock_code,
            "_safe_float": _safe_float,
            "_round_or_none": _round_or_none,
            "fetch_recent_price_bars": fetch_recent_price_bars,
            "evaluate_live_tradability": evaluate_live_tradability,
            "analyze_buy_signal": analyze_buy_signal,
            "QUANT_SYSTEM_AVAILABLE": QUANT_SYSTEM_AVAILABLE,
            "build_waiting_stock_plan": build_waiting_stock_plan,
            "_build_gem_breathing_contract": _build_gem_breathing_contract,
            "STOP_PRIOR_LOW_TRADING_DAYS": STOP_PRIOR_LOW_TRADING_DAYS,
        },
    )


def _finalize_waiting_candidate(waiting_item=None, original_candidate=None, permission=None):
    waiting_item = dict(waiting_item or {})
    original_candidate = original_candidate or {}
    permission = permission or {}

    waiting_item['permission_label'] = permission.get('permission_label', waiting_item.get('permission_label', ''))
    waiting_item['permission_reason'] = permission.get('permission_reason', waiting_item.get('permission_reason', ''))

    if str(original_candidate.get('watch_source', '') or '').strip() == 'gem_breathing_20cm':
        waiting_item['watch_source'] = 'gem_breathing_20cm'
        waiting_item['watch_anchor_type'] = '创业板20cm预启动先看谁'
        base_note = str(
            original_candidate.get('watch_anchor_note', '')
            or waiting_item.get('watch_anchor_note', '')
            or original_candidate.get('note', '')
            or '创业板20cm预启动观察。'
        ).strip()
        gem_contract = waiting_item.get('gem_breathing_contract') or original_candidate.get('gem_breathing_contract') or _build_gem_breathing_contract(waiting_item)
        waiting_item['gem_breathing_contract'] = gem_contract
        if base_note:
            waiting_item['watch_anchor_note'] = base_note
        if '右侧确认' not in str(waiting_item.get('watch_anchor_note', '') or ''):
            extra = str(permission.get('permission_reason', '') or '').strip()
            waiting_item['watch_anchor_note'] = '；'.join(part for part in [waiting_item.get('watch_anchor_note', ''), extra] if part)
        waiting_item['permission_label'] = permission.get('permission_label', '') or '创业板20cm预启动观察权'
        return waiting_item

    waiting_item['watch_source'] = waiting_item.get('watch_source', '') or 'waiting_layer'
    return waiting_item


def _select_priority_watch_anchor(
    trade_gate_open=False,
    abnormal_watch_anchor_candidates=None,
    pending_candidates=None,
    observation_candidates=None,
    waiting_stocks=None,
    gem_observation_stocks=None,
    target_date='',
    mainline_name='',
):
    return run_select_priority_watch_anchor(
        trade_gate_open=trade_gate_open,
        abnormal_watch_anchor_candidates=abnormal_watch_anchor_candidates,
        pending_candidates=pending_candidates,
        observation_candidates=observation_candidates,
        waiting_stocks=waiting_stocks,
        gem_observation_stocks=gem_observation_stocks,
        target_date=target_date,
        mainline_name=mainline_name,
        helpers={
            "_derive_pending_candidate_type": _derive_pending_candidate_type,
            "_derive_watch_anchor_type": _derive_watch_anchor_type,
            "_derive_watch_anchor_note": _derive_watch_anchor_note,
            "_build_gem_breathing_watch_anchor": _build_gem_breathing_watch_anchor,
        },
    )


def _build_gem_elasticity_context(candidate=None, mainline_name='', mainline_anchor=None):
    return run_build_gem_elasticity_context(
        candidate,
        mainline_name=mainline_name,
        mainline_anchor=mainline_anchor,
        helpers={
            "sector_name_matches": sector_name_matches,
        },
    )


def _should_hide_gem_execution_entry_range(candidate=None):
    return run_should_hide_gem_execution_entry_range(
        candidate,
        helpers={
            "_safe_float": _safe_float,
        },
    )


def _resolve_candidate_contract_prices(candidate=None, signal=None, expose_execution_entry_range=None):
    return run_resolve_candidate_contract_prices(
        candidate,
        signal=signal,
        expose_execution_entry_range=expose_execution_entry_range,
        helpers={
            "_round_or_none": _round_or_none,
            "_should_hide_gem_execution_entry_range": _should_hide_gem_execution_entry_range,
        },
    )


def _classify_20cm_branch(candidate=None, mainline_name='', confirm_price=None, support_price=None, feedback_ready=False, allow_attack_50_ready=False, target_date='', mainline_anchor=None):
    return run_classify_20cm_branch(
        candidate,
        mainline_name=mainline_name,
        confirm_price=confirm_price,
        support_price=support_price,
        feedback_ready=feedback_ready,
        allow_attack_50_ready=allow_attack_50_ready,
        target_date=target_date,
        mainline_anchor=mainline_anchor,
        helpers={
            "_is_20cm_stock": _is_20cm_stock,
            "_safe_float": _safe_float,
            "sector_name_matches": sector_name_matches,
            "_build_gem_breathing_prep_context": _build_gem_breathing_prep_context,
            "_build_gem_elasticity_context": _build_gem_elasticity_context,
        },
    )


def _build_special_probe_verdict(
    abnormal_probe_group=None,
    watch_anchor=None,
    watch_anchor_type='',
    mainline_name='',
    target_date='',
):
    return run_build_special_probe_verdict(
        abnormal_probe_group=abnormal_probe_group,
        watch_anchor=watch_anchor,
        watch_anchor_type=watch_anchor_type,
        mainline_name=mainline_name,
        target_date=target_date,
    )


def _build_special_probe_focus_text(
    abnormal_probe_group=None,
    watch_anchor=None,
    watch_anchor_type='',
    mainline_name='',
    target_date='',
):
    return run_build_special_probe_focus_text(
        abnormal_probe_group=abnormal_probe_group,
        watch_anchor=watch_anchor,
        watch_anchor_type=watch_anchor_type,
        mainline_name=mainline_name,
        target_date=target_date,
        helpers={
            "build_special_probe_verdict": _build_special_probe_verdict,
            "format_abnormal_probe_text": _format_abnormal_probe_text,
        },
    )


def _build_abnormal_setup_distribution(abnormal_watch_pool):
    return run_build_abnormal_setup_distribution(
        abnormal_watch_pool,
        helpers={"_split_abnormal_watch_pool": _split_abnormal_watch_pool},
    )


def _snapshot_candidate_brief(candidate):
    return run_snapshot_candidate_brief(
        candidate,
        helpers={
            "normalize_stock_code": normalize_stock_code,
            "_resolve_candidate_contract_prices": _resolve_candidate_contract_prices,
            "_build_trade_price_focus": _build_trade_price_focus,
            "_round_or_none": _round_or_none,
        },
    )


def _score_environment_snapshot(final_gate, position_level):
    return run_score_environment_snapshot(final_gate, position_level)


def _score_structure_snapshot(market_zhongshu):
    return run_score_structure_snapshot(market_zhongshu)


def _score_mainline_snapshot(mainline_name, mainline_score, sector_trend_snapshot):
    return run_score_mainline_snapshot(
        mainline_name,
        mainline_score,
        sector_trend_snapshot,
        helpers={
            "sector_name_matches": sector_name_matches,
            "_safe_float": _safe_float,
            "_clamp": _clamp,
        },
    )


def _score_memory_snapshot(leader_memory_bank, tracking_memory_status):
    return run_score_memory_snapshot(
        leader_memory_bank,
        tracking_memory_status,
        helpers={"_clamp": _clamp},
    )


def _score_abnormal_snapshot(abnormal_watch_pool, selected_candidate):
    return run_score_abnormal_snapshot(
        abnormal_watch_pool,
        selected_candidate,
        helpers={
            "_split_abnormal_watch_pool": _split_abnormal_watch_pool,
            "_clamp": _clamp,
        },
    )


def _normalize_flow_to_yi(value):
    return run_normalize_flow_to_yi(value, helpers={"_safe_float": _safe_float})


def _derive_mainline_pulse_snapshot(
    final_gate=None,
    state_code='',
    leading_line='',
    trend_density=0,
    resilient_count=0,
    failed_count=0,
    zt_count=0,
    dt_count=0,
    transition_signal='',
):
    return run_derive_mainline_pulse_snapshot(
        final_gate=final_gate,
        state_code=state_code,
        leading_line=leading_line,
        trend_density=trend_density,
        resilient_count=resilient_count,
        failed_count=failed_count,
        zt_count=zt_count,
        dt_count=dt_count,
        transition_signal=transition_signal,
    )


def _build_market_state_machine_snapshot(
    data,
    final_gate,
    position_level,
    exit_analysis,
    main_sectors_info=None,
    secondary_sectors_info=None,
    sector_trend_snapshot=None,
    abnormal_watch_pool=None,
):
    return run_build_market_state_machine_snapshot(
        data,
        final_gate,
        position_level,
        exit_analysis,
        main_sectors_info=main_sectors_info,
        secondary_sectors_info=secondary_sectors_info,
        sector_trend_snapshot=sector_trend_snapshot,
        abnormal_watch_pool=abnormal_watch_pool,
        helpers={
            "_split_abnormal_watch_pool": _split_abnormal_watch_pool,
            "_safe_float": _safe_float,
            "_round_or_none": _round_or_none,
            "_derive_mainline_pulse_snapshot": _derive_mainline_pulse_snapshot,
            "sector_name_matches": sector_name_matches,
        },
    )


def _resolve_environment_display_contract(position_level='', final_gate=None, state_machine_snapshot=None):
    return resolve_environment_display_contract(
        position_level=position_level,
        final_gate=final_gate,
        state_machine_snapshot=state_machine_snapshot,
    )


def _resolve_environment_reason_contract(position_reason='', environment_display=None, state_machine_snapshot=None):
    return resolve_environment_reason_contract(
        position_reason=position_reason,
        environment_display=environment_display,
        state_machine_snapshot=state_machine_snapshot,
    )


def _build_mainline_competition_snapshot(
    main_sectors_info=None,
    secondary_sectors_info=None,
    sector_trend_snapshot=None,
    risk_sectors=None,
):
    return run_build_mainline_competition_snapshot(
        main_sectors_info=main_sectors_info,
        secondary_sectors_info=secondary_sectors_info,
        sector_trend_snapshot=sector_trend_snapshot,
        risk_sectors=risk_sectors,
        helpers={
            "sector_name_matches": sector_name_matches,
            "_normalize_flow_to_yi": _normalize_flow_to_yi,
            "_safe_float": _safe_float,
        },
    )


def _build_abnormal_projection_summary(abnormal_watch_pool=None):
    return run_build_abnormal_projection_summary(
        abnormal_watch_pool,
        helpers={"_split_abnormal_watch_pool": _split_abnormal_watch_pool},
    )


def _build_market_observation_snapshot(
    data,
    main_sectors_info=None,
    secondary_sectors_info=None,
    sector_trend_snapshot=None,
    abnormal_watch_pool=None,
    leader_memory_bank=None,
    tracking_memory_status=None,
    mainline_competition_snapshot=None,
):
    return run_build_market_observation_snapshot(
        data,
        main_sectors_info=main_sectors_info,
        secondary_sectors_info=secondary_sectors_info,
        sector_trend_snapshot=sector_trend_snapshot,
        abnormal_watch_pool=abnormal_watch_pool,
        leader_memory_bank=leader_memory_bank,
        tracking_memory_status=tracking_memory_status,
        mainline_competition_snapshot=mainline_competition_snapshot,
        helpers={
            "_split_abnormal_watch_pool": _split_abnormal_watch_pool,
            "_extract_market_breadth_snapshot": _extract_market_breadth_snapshot,
            "_safe_float": _safe_float,
            "_round_or_none": _round_or_none,
        },
    )


def _build_follow_verdict(final_gate, position_level, state_machine_snapshot, special_probe_verdict=None):
    return run_build_follow_verdict(
        final_gate,
        position_level,
        state_machine_snapshot,
        special_probe_verdict=special_probe_verdict,
        helpers={},
    )


def _build_dialectical_decision_snapshot(
    observation=None,
    style_switch=None,
    state_machine=None,
    follow_verdict=None,
    final_gate=None,
):
    return run_build_dialectical_decision_snapshot(
        observation=observation,
        style_switch=style_switch,
        state_machine=state_machine,
        follow_verdict=follow_verdict,
        final_gate=final_gate,
        helpers={"_safe_float": _safe_float},
    )


def _build_market_research_snapshot(data, final_gate, position_level, exit_analysis, observation_snapshot=None, target_date=''):
    return run_build_market_research_snapshot(
        data,
        final_gate,
        position_level,
        exit_analysis,
        observation_snapshot=observation_snapshot,
        target_date=target_date,
        helpers={
            "_build_abnormal_projection_summary": _build_abnormal_projection_summary,
            "_build_market_style_switch_snapshot": _build_market_style_switch_snapshot,
            "_build_market_state_machine_snapshot": _build_market_state_machine_snapshot,
            "_build_mainline_rotation_snapshot": _build_mainline_rotation_snapshot,
            "_build_abnormal_probe_group": _build_abnormal_probe_group,
            "_build_special_probe_verdict": _build_special_probe_verdict,
            "_build_follow_verdict": _build_follow_verdict,
            "_build_dialectical_decision_snapshot": _build_dialectical_decision_snapshot,
            "postgres_only_runtime": _POSTGRES_ONLY_RUNTIME,
        },
    )


def _derive_step0_follow_plan(market_research_snapshot, final_gate, position_level):
    return run_derive_step0_follow_plan(
        market_research_snapshot,
        final_gate,
        position_level,
    )


def _render_market_research_snapshot_section(market_research_snapshot, compact=False):
    return run_render_market_research_snapshot_section(
        market_research_snapshot,
        compact=compact,
        helpers={
            "_build_mainline_rotation_snapshot": _build_mainline_rotation_snapshot,
            "_build_dialectical_decision_snapshot": _build_dialectical_decision_snapshot,
            "_safe_float": _safe_float,
        },
    )


def _render_step0_follow_section(step0_plan, market_research_snapshot, compact=False):
    return run_render_step0_follow_section(
        step0_plan,
        market_research_snapshot,
        compact=compact,
        helpers={},
    )


def build_market_research_context_bundle(
    data,
    target_date,
    exit_analysis,
    final_gate,
    position_level,
    main_sectors_info=None,
    secondary_sectors_info=None,
    main_sectors=None,
    secondary_sectors=None,
    dragon_stocks=None,
    decision_strict_mode=None,
    allow_display_degraded_abnormal_snapshot=None,
):
    """构建 Step0/Step1 共用的市场研究上下文，供日报与单票诊断复用。"""
    return run_build_market_research_context_bundle(
        data,
        target_date,
        exit_analysis,
        final_gate,
        position_level,
        main_sectors_info=main_sectors_info,
        secondary_sectors_info=secondary_sectors_info,
        main_sectors=main_sectors,
        secondary_sectors=secondary_sectors,
        dragon_stocks=dragon_stocks,
        decision_strict_mode=decision_strict_mode,
        allow_display_degraded_abnormal_snapshot=allow_display_degraded_abnormal_snapshot,
        helpers={
            "get_active_a_kill_records": get_active_a_kill_records,
            "normalize_stock_code": normalize_stock_code,
            "safe_float": _safe_float,
            "is_stock_in_a_kill_cooldown": is_stock_in_a_kill_cooldown,
            "sector_name_matches": sector_name_matches,
            "build_abnormal_watch_pool": build_abnormal_watch_pool,
            "decision_strict_mode": DECISION_STRICT_MODE,
            "allow_display_degraded_abnormal_snapshot": ALLOW_DISPLAY_DEGRADED_ABNORMAL_SNAPSHOT,
            "is_degraded_abnormal_snapshot": _is_degraded_abnormal_snapshot,
            "build_sector_trend_snapshot": build_sector_trend_snapshot,
            "build_leader_memory_bank": build_leader_memory_bank,
            "refresh_tracking_memory": refresh_tracking_memory,
            "discover_all_gem_breathing_candidates": _discover_all_gem_breathing_candidates,
            "candidate_matches_mainline": _candidate_matches_mainline,
            "build_gem_observation_pool": _build_gem_20cm_observation_pool,
            "build_mainline_competition_snapshot": _build_mainline_competition_snapshot,
            "build_market_observation_snapshot": _build_market_observation_snapshot,
            "_build_abnormal_projection_summary": _build_abnormal_projection_summary,
            "_build_market_style_switch_snapshot": _build_market_style_switch_snapshot,
            "_build_market_state_machine_snapshot": _build_market_state_machine_snapshot,
            "_build_mainline_rotation_snapshot": _build_mainline_rotation_snapshot,
            "_build_abnormal_probe_group": _build_abnormal_probe_group,
            "_build_special_probe_verdict": _build_special_probe_verdict,
            "_build_follow_verdict": _build_follow_verdict,
            "_build_dialectical_decision_snapshot": _build_dialectical_decision_snapshot,
        },
    )


def build_step2_candidate_bundle(
    data,
    exit_analysis,
    candidates,
    watchlist,
    abnormal_watch_map,
    dragon_stocks,
    zt_pool_by_sector=None,
    gem_breathing_candidates=None,
    target_date='',
):
    """构建 Step2 共用候选上下文，供日报与单票诊断复用。"""
    return run_build_step2_candidate_bundle(
        data,
        exit_analysis,
        candidates,
        watchlist,
        abnormal_watch_map,
        dragon_stocks,
        zt_pool_by_sector=zt_pool_by_sector,
        gem_breathing_candidates=gem_breathing_candidates,
        target_date=target_date,
        helpers={
            "normalize_stock_code": normalize_stock_code,
            "get_abnormal_rank_adjustment": get_abnormal_rank_adjustment,
            "split_candidates_by_mainline": _split_candidates_by_mainline,
            "build_gem_observation_pool": _build_gem_20cm_observation_pool,
            "build_sector_trend_snapshot": build_sector_trend_snapshot,
            "build_extreme_conviction_list": build_extreme_conviction_list,
            "build_extreme_conviction_groups": build_extreme_conviction_groups,
            "fetch_recent_price_bars": fetch_recent_price_bars,
        },
    )


def _format_step3_risk_reason(risk_penalties=None, repair_buffers=None, risk_level=''):
    return run_format_step3_risk_reason(
        risk_penalties,
        repair_buffers,
        risk_level,
        helpers={},
    )


def _parse_limit_time_to_minutes(time_text):
    return run_parse_limit_time_to_minutes(time_text)


def _evaluate_limit_up_friction(zhaban, last_limit_time='', turnover=0.0, board_count=1):
    return run_evaluate_limit_up_friction(
        zhaban,
        last_limit_time=last_limit_time,
        turnover=turnover,
        board_count=board_count,
        helpers={
            "safe_float": _safe_float,
            "clamp": _clamp,
        },
    )


def build_step3_risk_bundle(
    data,
    target_date,
    mainline_name,
    core_stocks,
    secondary_stocks,
    gem_observation_stocks=None,
    zt_pool_by_sector=None,
    dt_pool_by_sector=None,
    persist_a_kill=False,
):
    """构建 Step3 风险预判上下文，供日报与单票诊断共用。"""
    return run_build_step3_risk_bundle(
        data,
        target_date,
        mainline_name,
        core_stocks,
        secondary_stocks,
        gem_observation_stocks=gem_observation_stocks,
        zt_pool_by_sector=zt_pool_by_sector,
        dt_pool_by_sector=dt_pool_by_sector,
        persist_a_kill=persist_a_kill,
        helpers={
            "normalize_stock_code": normalize_stock_code,
            "safe_float": _safe_float,
            "clamp": _clamp,
            "get_abnormal_follow_risk_signal": get_abnormal_follow_risk_signal,
            "format_risk_reason": _format_step3_risk_reason,
            "update_a_kill_blacklist": update_a_kill_blacklist,
        },
    )


def _build_strategy_factor_snapshot(
    target_date,
    data,
    market_zhongshu,
    final_gate,
    exit_analysis,
    position_level,
    position_reason,
    context,
):
    return run_build_strategy_factor_snapshot(
        target_date,
        data,
        market_zhongshu,
        final_gate,
        exit_analysis,
        position_level,
        position_reason,
        context,
        helpers={
            key: value
            for key, value in globals().items()
            if not (key.startswith("__") and key.endswith("__"))
        },
    )


def _simulate_exit_for_entry(
    entry_price,
    bars,
    structure_stop=None,
    holding_days_min=STRATEGY_HOLDING_DAYS_MIN,
    holding_days_max=STRATEGY_HOLDING_DAYS_MAX,
    profit_take_pct=0.05,
):
    return run_simulate_exit_for_entry(
        entry_price,
        bars,
        structure_stop=structure_stop,
        holding_days_min=holding_days_min,
        holding_days_max=holding_days_max,
        profit_take_pct=profit_take_pct,
        helpers=_collect_runtime_helpers(_STRATEGY_EVAL_HELPER_EXCLUDES),
    )


def _compute_benchmark_return(report_date, end_date, benchmark_report_close):
    return run_compute_benchmark_return(
        report_date,
        end_date,
        benchmark_report_close,
        helpers=_collect_runtime_helpers(_STRATEGY_EVAL_HELPER_EXCLUDES),
    )


def _get_nth_bar_after(bars, after_date, nth=1):
    return run_get_nth_bar_after(
        bars,
        after_date,
        nth=nth,
        helpers=_collect_runtime_helpers(_STRATEGY_EVAL_HELPER_EXCLUDES),
    )


def _compute_watch_outcome_metrics(record, as_of_date):
    return run_compute_watch_outcome_metrics(
        record,
        as_of_date,
        helpers=_collect_runtime_helpers(_STRATEGY_EVAL_HELPER_EXCLUDES),
    )


def _evaluate_single_strategy_record(record, as_of_date):
    return run_evaluate_single_strategy_record(
        record,
        as_of_date,
        helpers=_collect_runtime_helpers(_STRATEGY_EVAL_HELPER_EXCLUDES),
    )


def _collect_record_market_path(record, as_of_date):
    return run_collect_record_market_path(
        record,
        as_of_date,
        helpers=_collect_runtime_helpers(_STRATEGY_EVAL_HELPER_EXCLUDES),
    )


def _build_recent_target_followups(records, as_of_date, limit=3):
    return run_build_recent_target_followups(
        records,
        as_of_date,
        limit=limit,
        helpers={
            key: value
            for key, value in globals().items()
            if not (key.startswith("__") and key.endswith("__"))
        },
    )


def _build_recent_target_reflection(review_matrix):
    return run_build_recent_target_reflection(
        review_matrix,
        helpers={
            key: value
            for key, value in globals().items()
            if not (key.startswith("__") and key.endswith("__"))
        },
    )


def _build_recent_target_review_matrix(current_plan, recent_followups, limit=4):
    return run_build_recent_target_review_matrix(
        current_plan,
        recent_followups,
        limit=limit,
        helpers={
            key: value
            for key, value in globals().items()
            if not (key.startswith("__") and key.endswith("__"))
        },
    )


def _classify_strategy_record_attribution(record, as_of_date):
    return run_classify_strategy_record_attribution(
        record,
        as_of_date,
        helpers=_collect_runtime_helpers(_STRATEGY_REVIEW_HELPER_EXCLUDES),
    )


def _summarize_strategy_attribution(records, start_date, end_date):
    return run_summarize_strategy_attribution(
        records,
        start_date,
        end_date,
        helpers=_collect_runtime_helpers(_STRATEGY_REVIEW_HELPER_EXCLUDES),
    )


def _summarize_setup_signal_review(records, start_date, end_date):
    return run_summarize_setup_signal_review(
        records,
        start_date,
        end_date,
        helpers=_collect_runtime_helpers(_STRATEGY_REVIEW_HELPER_EXCLUDES),
    )


def _extract_gem_breathing_contract_snapshot(record):
    return run_extract_gem_breathing_contract_snapshot(
        record,
        helpers=_collect_runtime_helpers(_STRATEGY_REVIEW_HELPER_EXCLUDES),
    )


def _classify_gem_breathing_week_sample(record, as_of_date):
    return run_classify_gem_breathing_week_sample(
        record,
        as_of_date,
        helpers=_collect_runtime_helpers(_STRATEGY_REVIEW_HELPER_EXCLUDES),
    )


def _summarize_gem_breathing_week_review(records, start_date, end_date):
    return run_summarize_gem_breathing_week_review(
        records,
        start_date,
        end_date,
        helpers=_collect_runtime_helpers(_STRATEGY_REVIEW_HELPER_EXCLUDES),
    )


def _build_self_calibration_summary(
    records,
    start_date,
    end_date,
    windows=None,
    attribution_summary=None,
    setup_summary=None,
    ev_summary=None,
    gem_week_review=None,
):
    return run_build_self_calibration_summary(
        records,
        start_date,
        end_date,
        windows=windows,
        attribution_summary=attribution_summary,
        setup_summary=setup_summary,
        ev_summary=ev_summary,
        gem_week_review=gem_week_review,
        helpers=_collect_runtime_helpers(_STRATEGY_REVIEW_HELPER_EXCLUDES),
    )


def _apply_yizi_chain_rules(records):
    return run_apply_yizi_chain_rules(
        records,
        helpers=_collect_runtime_helpers(_STRATEGY_EVAL_HELPER_EXCLUDES),
    )


def _build_strategy_plan_context(
    target_date,
    data,
    market_zhongshu,
    final_gate,
    exit_analysis,
    position_level,
    position_reason,
    best_stock=None,
    watch_anchor=None,
    watch_anchor_type='重点观察谁',
    factor_snapshot=None,
):
    return run_build_strategy_plan_context(
        target_date,
        data,
        market_zhongshu,
        final_gate,
        exit_analysis,
        position_level,
        position_reason,
        best_stock=best_stock,
        watch_anchor=watch_anchor,
        watch_anchor_type=watch_anchor_type,
        factor_snapshot=factor_snapshot,
        helpers={
            key: value
            for key, value in globals().items()
            if not (key.startswith("__") and key.endswith("__"))
        },
    )


def _find_strategy_record(records, report_date):
    return run_find_strategy_record(
        records,
        report_date,
        helpers={
            key: value
            for key, value in globals().items()
            if not (key.startswith("__") and key.endswith("__"))
        },
    )


def _format_strategy_record_brief(record):
    return run_format_strategy_record_brief(
        record,
        helpers={
            key: value
            for key, value in globals().items()
            if not (key.startswith("__") and key.endswith("__"))
        },
    )


def _strategy_record_core_signature(record):
    return run_strategy_record_core_signature(
        record,
        helpers={
            key: value
            for key, value in globals().items()
            if not (key.startswith("__") and key.endswith("__"))
        },
    )


def _upsert_strategy_record(ledger, plan_context, allow_overwrite=True):
    return run_upsert_strategy_record(
        ledger,
        plan_context,
        allow_overwrite=allow_overwrite,
        helpers={
            key: value
            for key, value in globals().items()
            if not (key.startswith("__") and key.endswith("__"))
        },
    )


def _merge_strategy_record_sources(base_records, override_records):
    return run_merge_strategy_record_sources(
        base_records,
        override_records,
        helpers={
            key: value
            for key, value in globals().items()
            if not (key.startswith("__") and key.endswith("__"))
        },
    )


def _summarize_strategy_window(records, start_date, end_date):
    return run_summarize_strategy_window(
        records,
        start_date,
        end_date,
        helpers={
            key: value
            for key, value in globals().items()
            if not (key.startswith("__") and key.endswith("__"))
        },
    )


def _prepare_records_for_review(records, as_of_date):
    return run_prepare_records_for_review(
        records,
        as_of_date,
        helpers={
            key: value
            for key, value in globals().items()
            if not (key.startswith("__") and key.endswith("__"))
        },
    )


def _classify_structure_cycle_result(window_summary, attribution_summary, gem_cycle_review=None):
    return run_classify_structure_cycle_result(
        window_summary,
        attribution_summary,
        gem_cycle_review=gem_cycle_review,
        helpers=_collect_runtime_helpers(_STRATEGY_REVIEW_HELPER_EXCLUDES),
    )


def _build_structure_cycle_gem_summary(gem_cycle_review):
    return run_build_structure_cycle_gem_summary(
        gem_cycle_review,
        helpers=_collect_runtime_helpers(_STRATEGY_REVIEW_HELPER_EXCLUDES),
    )


def _build_gem_structure_cycle_cards(records, as_of_date, limit=6):
    return run_build_gem_structure_cycle_cards(
        records,
        as_of_date,
        limit=limit,
        helpers=_collect_runtime_helpers(_STRATEGY_REVIEW_HELPER_EXCLUDES),
    )


def _build_gem_horizontal_compare_cards(gem_cycle_cards=None, review_matrix=None, limit=4):
    return run_build_gem_horizontal_compare_cards(
        gem_cycle_cards=gem_cycle_cards,
        review_matrix=review_matrix,
        limit=limit,
        helpers={
            key: value
            for key, value in globals().items()
            if not (key.startswith("__") and key.endswith("__"))
        },
    )


def _summarize_structure_cycles(records, as_of_date):
    return run_summarize_structure_cycles(
        records,
        as_of_date,
        helpers=_collect_runtime_helpers(_STRATEGY_REVIEW_HELPER_EXCLUDES),
    )


def _build_system_graduation_dashboard(records, cycle_reviews, source_label='当前账本', current_plan=None, gem_week_review=None):
    return run_build_system_graduation_dashboard(
        records,
        cycle_reviews,
        source_label=source_label,
        current_plan=current_plan,
        gem_week_review=gem_week_review,
        helpers=_collect_runtime_helpers(_STRATEGY_REVIEW_HELPER_EXCLUDES),
    )


def update_strategy_performance_book(data, target_date, plan_context, market_zhongshu, ledger_mode=LEDGER_MODE_FROZEN):
    return run_update_strategy_performance_book(
        data,
        target_date,
        plan_context,
        market_zhongshu,
        ledger_mode=ledger_mode,
        helpers={
            key: value
            for key, value in globals().items()
            if not (key.startswith("__") and key.endswith("__"))
        },
    )


def _get_recent_record_display_metrics(record):
    return run_get_recent_record_display_metrics(
        record,
        helpers=_collect_runtime_helpers(_STRATEGY_EVAL_HELPER_EXCLUDES),
    )


def append_strategy_performance_section(report, performance_summary):
    return run_append_strategy_performance_section(
        report,
        performance_summary,
        helpers={
            key: value
            for key, value in globals().items()
            if not (key.startswith("__") and key.endswith("__"))
        },
    )


def generate_markdown_report(
    data,
    target_date,
    supplementary_perspective="",
    has_personal_positions=False,
    run_mode=LEDGER_MODE_FROZEN,
    persist_strategy_tracking=True,
    persist_decision_ledger=False,
    decision_ledger_root_dir=None,
    persist_candidate_traces=False,
    candidate_trace_root_dir=None,
    postgres_only=False,
):
    runtime_result = render_markdown_report_runtime(
        data,
        target_date,
        supplementary_perspective=supplementary_perspective,
        has_personal_positions=has_personal_positions,
        run_mode=run_mode,
        persist_strategy_tracking=persist_strategy_tracking,
        helpers={
            key: value
            for key, value in globals().items()
            if not (key.startswith("__") and key.endswith("__"))
        },
        config={
            "persist_decision_ledger": persist_decision_ledger,
            "decision_ledger_root_dir": decision_ledger_root_dir or str(Path(__file__).resolve().parents[1]),
            "persist_candidate_traces": persist_candidate_traces,
            "candidate_trace_root_dir": candidate_trace_root_dir or str(Path(__file__).resolve().parents[1]),
            "decision_ledger_postgres_only": postgres_only,
            "ENABLE_REMOTE_CALENDAR_LLM": _resolve_remote_calendar_llm_enabled(),
        },
    )
    return runtime_result["report"]



def _normalize_report_timer_steps(timer_summary, step_status=None):
    return run_normalize_report_timer_steps(
        timer_summary,
        step_status,
        helpers={
            key: value
            for key, value in globals().items()
            if not (key.startswith("__") and key.endswith("__"))
        },
    )


def parse_position_string(position_str):
    return run_parse_position_string(position_str)


def analyze_position_management(data, target_date, positions):
    return run_analyze_position_management(
        data,
        target_date,
        positions,
        helpers={
            "build_trading_philosophy_lines": _build_trading_philosophy_lines,
            "display_mvp_mode": DISPLAY_MVP_MODE,
        },
    )


def build_personal_position_context(data, positions):
    return run_build_personal_position_context(data, positions)

def replay_from_snapshot(target_date, refresh_sources=None):
    result = run_replay_from_snapshot(
        target_date,
        refresh_sources=refresh_sources,
        helpers={
            "load_data_snapshot": load_data_snapshot,
            "TencentFinanceData": TencentFinanceData,
            "get_major_indices_from_iwencai": get_major_indices_from_iwencai,
            "get_etf_turnover_series_from_sina": get_etf_turnover_series_from_sina_first,
            "safe_float": _safe_float,
        },
    )
    return result.get('data'), result.get('target_date', target_date)


def _postgres_daily_report_service():
    service = DatabaseService.from_environment()
    if not service.is_postgres_backed():
        raise ReportCriticalDataMissingError("PostgreSQL-only 需要 A_DAILY_REPORT_DATABASE_URL 或 DATABASE_URL 指向 PostgreSQL")
    return service


def load_daily_report_data_from_postgres(target_date):
    service = _postgres_daily_report_service()
    result = service.load_daily_report_snapshot(target_date)
    data = result.get("data") if isinstance(result, dict) else {}
    if not isinstance(data, dict) or not data:
        raise ReportCriticalDataMissingError(f"{target_date} PostgreSQL 日报事实缺失，停止生成")
    csi1000 = data.get("csi1000_index") or {}
    if isinstance(csi1000, dict) and _safe_float(csi1000.get("price", csi1000.get("点位", 0))) > 0:
        data_status = data.setdefault("data_status", {})
        if isinstance(data_status, dict):
            data_status["中证1000"] = True
        step_status = data.setdefault("step_status", {})
        if isinstance(step_status, dict):
            step_status["中证1000获取"] = True
    data["postgres_source"] = result.get("source") or data.get("postgres_source") or ""
    data["postgres_field_count"] = result.get("field_count", 0)
    data["postgres_only"] = True
    return data


def save_daily_report_data_to_postgres(target_date, data):
    service = _postgres_daily_report_service()
    return service.save_daily_report_snapshot(target_date, data or {})


def import_daily_report_data_to_postgres(target_date, data):
    service = _postgres_daily_report_service()
    return service.import_daily_report_facts(target_date, data or {})


def resolve_single_stock_snapshot(data, stock_code, stock_name='', market_research_bundle=None, step2_bundle=None):
    return run_resolve_single_stock_snapshot(
        data,
        stock_code,
        stock_name=stock_name,
        market_research_bundle=market_research_bundle,
        step2_bundle=step2_bundle,
        helpers={
            "normalize_stock_code": normalize_stock_code,
            "get_stock_sector": get_stock_sector,
            "fetch_recent_price_bars": fetch_recent_price_bars,
            "safe_float": _safe_float,
            "compute_bar_change_pct": _compute_bar_change_pct,
        },
    )


def generate_single_stock_diagnostic_markdown(
    data,
    target_date,
    stock_code,
    stock_name='',
    run_mode=LEDGER_MODE_FROZEN,
):
    return run_generate_single_stock_diagnostic_markdown(
        data,
        target_date,
        stock_code,
        stock_name=stock_name,
        run_mode=run_mode,
        helpers=_collect_runtime_helpers(_SINGLE_STOCK_RUNTIME_HELPER_EXCLUDES),
    )


def _resolve_chanlun_tomorrow_decision(data):
    snapshot = data.get("market_research_snapshot") if isinstance(data, dict) else {}
    if isinstance(snapshot, dict):
        for key in ("front_page_final_gate", "final_gate"):
            decision = snapshot.get(key)
            if isinstance(decision, dict) and decision:
                return decision
    final_gate = data.get("final_gate") if isinstance(data, dict) else {}
    return final_gate if isinstance(final_gate, dict) and final_gate else None


def _has_existing_position_context(data):
    if not isinstance(data, dict):
        return False
    context = data.get("personal_position_context")
    if not isinstance(context, dict):
        return False
    summary = context.get("existing_position_summary")
    return bool(isinstance(summary, dict) and summary.get("has_position"))


def _postgres_index_bar_service():
    database_url = (
        os.environ.get("A_DAILY_REPORT_DATABASE_URL")
        or os.environ.get("DATABASE_URL")
        or ""
    ).strip()
    if not database_url.startswith(("postgres://", "postgresql://")):
        return None
    service = DatabaseService.from_environment()
    return service if service.is_postgres_backed() else None


def _postgres_only_index_daily_loader(index_code, target_date, recent_days):
    service = _postgres_index_bar_service()
    if service is None:
        return [], "postgresql.index_daily_bars"
    rows = service.query_index_daily_bars(index_code, target_date, window_days=recent_days)
    return rows, "postgresql.index_daily_bars"


def _postgres_only_index_daily_dataframe_loader(
    *,
    index_code="sh.000001",
    recent_days=250,
    min_zhongshu_klines=None,
    target_date=None,
    **_kwargs,
):
    del min_zhongshu_klines
    import pandas as pd

    rows, source = _postgres_only_index_daily_loader(index_code, target_date, recent_days)
    required_rows = max(int(recent_days or 0), 1)
    if len(rows or []) < required_rows:
        raise ReportCriticalDataMissingError(
            f"{target_date} PostgreSQL指数日K不足：{len(rows or [])}/{required_rows}，停止生成"
        )
    return pd.DataFrame(rows or []), source


def _postgres_only_index_minute_fetcher(*, index_code="sh.000001", period="60", target_date=None, **_kwargs):
    service = _postgres_index_bar_service()
    symbol = str(index_code or "").replace(".", "")
    if service is None or not target_date:
        return {
            "success": False,
            "status": "postgres_minute_missing",
            "source": "postgresql.index_minute_bars",
            "symbol": symbol,
            "period": str(period),
            "trade_date": str(target_date or ""),
            "bars": [],
        }
    rows = service.query_index_minute_bars(index_code, target_date, period=str(period))
    if rows:
        return {
            "success": True,
            "status": "success",
            "source": "postgresql.index_minute_bars",
            "symbol": symbol,
            "period": str(period),
            "trade_date": str(target_date),
            "bars": rows,
        }
    return {
        "success": False,
        "status": "postgres_minute_missing",
        "source": "postgresql.index_minute_bars",
        "symbol": symbol,
        "period": str(period),
        "trade_date": str(target_date or ""),
        "bars": [],
    }


def _postgres_only_analyze_market_zhongshu(**kwargs):
    kwargs = dict(kwargs or {})
    kwargs["fetch_dataframe"] = _postgres_only_index_daily_dataframe_loader
    kwargs["fetch_minute_bars"] = _postgres_only_index_minute_fetcher
    result = analyze_market_zhongshu(**kwargs)
    if not (result or {}).get("success"):
        error_text = str((result or {}).get("error") or "")
        if "PostgreSQL指数日K不足" in error_text:
            raise ReportCriticalDataMissingError(error_text)
    return result


def _build_sh_index_chanlun_html_for_audit(
    target_date,
    *,
    index_code=DEFAULT_INDEX_CODE,
    tomorrow_decision=None,
    runner=run_sh_index_chanlun_analysis,
):
    if _POSTGRES_ONLY_RUNTIME:
        market_zhongshu, rows = runner(
            target_date,
            index_code,
            sse_loader=_postgres_only_index_daily_loader,
            fetch_minute_bars=_postgres_only_index_minute_fetcher,
            allow_live_fallback=False,
        )
    else:
        market_zhongshu, rows = runner(target_date, index_code)
    if _POSTGRES_ONLY_RUNTIME and not (market_zhongshu or {}).get("success"):
        raise ReportCriticalDataMissingError(
            (market_zhongshu or {}).get("error") or f"{target_date} PostgreSQL指数结构缺失，停止生成缠论HTML"
        )
    payload = normalize_visual_payload(market_zhongshu, rows, date=target_date, index_code=index_code)
    if tomorrow_decision:
        payload["tomorrow_decision"] = dict(tomorrow_decision)
    return render_sh_index_chanlun_html(payload)


def _audit_generated_report_with_chanlun_html(report_outputs, chanlun_html_path=None, companion_html=None):
    full_report = (report_outputs or {}).get(REPORT_VARIANT_FULL, "")
    if companion_html is None and chanlun_html_path:
        companion_html = Path(chanlun_html_path).read_text(encoding="utf-8")
    result = audit_report_markdown(full_report, companion_html=companion_html)
    if result.get("passed"):
        print("日报一致性检查通过")
        return result
    for finding in result.get("findings", []):
        line_suffix = f":{finding['line']}" if "line" in finding else ""
        print(f"{finding['code']}{line_suffix} {finding['message']}")
    raise ReportCriticalDataMissingError("日报一致性检查未通过，停止生成")


def _audit_existing_official_report_or_raise(target_date, official_report_path):
    path = Path(official_report_path)
    if not path.exists():
        return None
    result = audit_report_markdown(path.read_text(encoding="utf-8"))
    if result.get("passed"):
        return result
    for finding in result.get("findings", []):
        line_suffix = f":{finding['line']}" if "line" in finding else ""
        print(f"{finding['code']}{line_suffix} {finding['message']}")
    raise ReportCriticalDataMissingError(f"{target_date} 已有正式日报一致性检查未通过，停止生成")


def _daily_report_data_path_label(args):
    if getattr(args, "postgres_only", False):
        return "PostgreSQL-only"
    if getattr(args, "replay", False):
        return "replay-json"
    return "live"


def _format_elapsed_seconds(elapsed_seconds):
    return f"{max(0.0, float(elapsed_seconds)) + 1e-9:.2f}"


def _append_daily_report_duration_log(saved_paths, *, target_date, elapsed_seconds, data_path_label, report_write_label):
    elapsed_text = _format_elapsed_seconds(elapsed_seconds)
    print(
        f"⏱ 日报生成总耗时: {elapsed_text} 秒 | 日期: {target_date} | 数据路径: {data_path_label} | 报告: {report_write_label}"
    )
    run_log_path = (saved_paths or {}).get(REPORT_VARIANT_RUN_LOG)
    if not run_log_path:
        return None
    path = Path(run_log_path)
    try:
        current_text = path.read_text(encoding="utf-8")
        append_text = "\n".join(
            [
                "## 耗时统计",
                "",
                "| 项目 | 值 |",
                "|------|------|",
                f"| 开始到完成 | {elapsed_text} 秒 |",
                f"| 日期 | {target_date} |",
                f"| 数据路径 | {data_path_label} |",
                f"| 报告写入 | {report_write_label} |",
            ]
        )
        path.write_text(f"{current_text.rstrip()}\n\n{append_text}\n", encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        print(f"⚠️ 耗时统计写入失败，已保留日报正文: {exc}")
        return None
    return str(path)


def main():
    """主函数"""
    import argparse
    report_started_at = time.perf_counter()
    
    parser = argparse.ArgumentParser(description='A股日报数据获取入口 - SKILL.md对齐版')
    parser.add_argument('date', nargs='?', default=None,
                       help='目标日期，格式: YYYY-MM-DD (默认: 昨天)')
    parser.add_argument('--no-report', action='store_true',
                       help='不生成报告文件，只获取数据')
    parser.add_argument('-p', '--position', type=str, default=None,
                       help='持仓信息，格式: "我的仓位是股票1 仓位1%% 股票2 仓位2%% ..."')
    parser.add_argument('--replay', action='store_true',
                       help='复盘模式：从快照读数据，只重新拉财联社日历，用最新skill生成报告')
    parser.add_argument('--postgres-only', action='store_true',
                       help='PostgreSQL-only 模式：从 PostgreSQL 读取日报事实，不读取 JSON 快照主来源')
    parser.add_argument('--import-json-to-postgres', action='store_true',
                       help='把指定日期的历史快照筛选为复盘取证事实后导入 PostgreSQL，不生成日报')
    parser.add_argument('--stock', type=str, default=None,
                       help='生成单票诊断，输入股票代码，如 002364')
    parser.add_argument('--stock-name', type=str, default='',
                       help='单票诊断可选股票名称，提升可读性')
    parser.add_argument('--publish-snap-ui', action='store_true',
                       help='显式发布 snap-ui 静态数据并运行契约检查；默认只生成日报与快照')
    parser.add_argument('--overwrite-official', action='store_true',
                       help='显式覆盖该日期正式日报；默认保护已有正式历史')
    
    args = parser.parse_args()
    
    if args.date:
        target_date = args.date
    else:
        import datetime as _dt
        today = _dt.datetime.now()
        yesterday = today - _dt.timedelta(days=1)
        target_date = yesterday.strftime("%Y-%m-%d")

    if args.postgres_only and args.replay:
        raise ReportCriticalDataMissingError("PostgreSQL-only 不能与 --replay 同时使用")
    if args.postgres_only and args.publish_snap_ui:
        raise ReportCriticalDataMissingError("PostgreSQL-only 不发布 snap-ui 静态数据")
    if args.import_json_to_postgres and (args.postgres_only or args.replay):
        raise ReportCriticalDataMissingError("--import-json-to-postgres 不能与 --postgres-only 或 --replay 同时使用")

    if args.import_json_to_postgres:
        snapshot_data, _ = load_data_snapshot(target_date)
        if not isinstance(snapshot_data, dict) or not snapshot_data:
            raise ReportCriticalDataMissingError(f"{target_date} 历史快照缺失，无法导入 PostgreSQL")
        result = import_daily_report_data_to_postgres(target_date, snapshot_data)
        print(f"🐘 PostgreSQL 复盘取证事实已导入: {result.get('source', '')} / fields={result.get('field_count', 0)}")
        print(f"   structured={result.get('structured_counts', {})}")
        return 0

    global _POSTGRES_ONLY_RUNTIME
    _POSTGRES_ONLY_RUNTIME = bool(args.postgres_only)
    previous_postgres_only_guard = os.environ.get("A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME")
    if args.postgres_only:
        os.environ["A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME"] = "1"

    saved_report_paths = {}
    try:
        if args.postgres_only:
            print(f"📅 从 PostgreSQL 读取日报事实: {target_date}")
            data = load_daily_report_data_from_postgres(target_date)
        elif args.replay:
            data, target_date = replay_from_snapshot(target_date)
        else:
            print(f"📅 获取数据: {target_date}")
            data = get_daily_data(target_date)
        if data:
            report_preflight = build_report_preflight(data, target_date)
            for line in render_report_preflight_lines(report_preflight):
                print(line)
            if report_preflight.get("failures"):
                raise ReportCriticalDataMissingError(
                    "{} 日报生成已终止：关键数据缺失或获取失败（{}）。\n{}".format(
                        target_date,
                        "、".join(report_preflight.get("failures") or []),
                        "\n".join(render_report_preflight_lines(report_preflight)),
                    )
                )

        run_mode = LEDGER_MODE_REPLAY if args.replay else LEDGER_MODE_FROZEN
        if run_mode == LEDGER_MODE_FROZEN and not args.overwrite_official:
            official_ledger = load_strategy_performance_ledger(mode=LEDGER_MODE_FROZEN)
            official_record = _find_strategy_record(official_ledger.get('records', []), target_date)
            official_report_path = _get_report_output_path(target_date, mode=LEDGER_MODE_FROZEN)
            if official_record or os.path.exists(official_report_path):
                _audit_existing_official_report_or_raise(target_date, official_report_path)
                run_mode = LEDGER_MODE_REPLAY
                print("🧊 检测到该日期已有官方历史，本次自动切换为实验模式，不改写历史。")

        # 生成日报（除非指定不生成）
        if not args.no_report and data:
            positions = []
            if args.position:
                print(f"\n📊 解析持仓信息...")
                positions = parse_position_string(args.position)
                if positions:
                    print(f"   ✅ 解析到 {len(positions)} 只持仓股票")
                    data["personal_position_context"] = build_personal_position_context(data, positions)
                else:
                    print(f"   ⚠️ 持仓信息解析失败，请检查格式")
            else:
                data["position_context_provided"] = False

            has_personal_positions = bool(positions) or _has_existing_position_context(data)
            if has_personal_positions:
                data["position_context_provided"] = True

            report_outputs = build_report_outputs(
                data,
                target_date,
                supplementary_perspective="",
                has_personal_positions=has_personal_positions,
                run_mode=run_mode,
                position_report_text="",
            )
            tomorrow_decision = _resolve_chanlun_tomorrow_decision(data)
            chanlun_html = _build_sh_index_chanlun_html_for_audit(
                target_date,
                tomorrow_decision=tomorrow_decision,
            )
            audit_result = _audit_generated_report_with_chanlun_html(report_outputs, companion_html=chanlun_html)
            report_outputs[REPORT_VARIANT_RUN_LOG] = finalize_run_log_text(
                report_outputs.get(REPORT_VARIANT_RUN_LOG, ""),
                audit_result,
            )
            saved_report_paths = save_report_outputs(
                report_outputs,
                target_date,
                mode=run_mode,
                overwrite_existing=bool(args.overwrite_official and run_mode == LEDGER_MODE_FROZEN),
                postgres_only=bool(args.postgres_only),
            )
            chanlun_html_path = save_sh_index_chanlun_html_report(
                target_date,
                root=Path(__file__).resolve().parents[1],
                tomorrow_decision=tomorrow_decision,
                fetch_minute_bars=_postgres_only_index_minute_fetcher if args.postgres_only else None,
                sse_loader=_postgres_only_index_daily_loader if args.postgres_only else None,
                allow_live_fallback=not args.postgres_only,
            )
            print(f"上证指数缠论HTML已生成: {chanlun_html_path}")
            if positions:
                position_strategy_report = render_position_strategy_report(
                    data,
                    target_date,
                    positions,
                    source_report_markdown=report_outputs.get(REPORT_VARIANT_FULL, ""),
                )
                save_position_strategy_report(position_strategy_report, target_date, mode=run_mode)

        if args.stock and data:
            stock_report = generate_single_stock_diagnostic_markdown(
                data,
                target_date,
                stock_code=args.stock,
                stock_name=args.stock_name,
                run_mode=run_mode,
            )
            save_stock_diagnostic_output(stock_report, target_date, args.stock, mode=run_mode)

        # 保存数据快照JSON（供复盘使用，无论是否生成报告都保存）
        if data:
            if args.postgres_only:
                result = import_daily_report_data_to_postgres(target_date, data)
                print(f"🐘 PostgreSQL 日报事实已同步: {result.get('source', '')} / fields={result.get('field_count', 0)}")
            else:
                _save_data_snapshot(data, target_date, mode=run_mode)
            if args.publish_snap_ui:
                publish_snap_ui_public_data(target_date, root=Path(__file__).resolve().parents[1])
            else:
                print("ℹ️ 已跳过 snap-ui 静态数据发布；如需维护前端数据，请显式传入 --publish-snap-ui。")

            elapsed_seconds = time.perf_counter() - report_started_at
            _append_daily_report_duration_log(
                saved_report_paths,
                target_date=target_date,
                elapsed_seconds=elapsed_seconds,
                data_path_label=_daily_report_data_path_label(args),
                report_write_label=run_mode if not args.no_report else "未生成",
            )

        return 0
    finally:
        _POSTGRES_ONLY_RUNTIME = False
        if previous_postgres_only_guard is None:
            os.environ.pop("A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME", None)
        else:
            os.environ["A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME"] = previous_postgres_only_guard


if __name__ == "__main__":
    from orchestrator.run_log_runtime import run_with_log_capture

    sys.exit(run_with_log_capture(main, argv=sys.argv))
