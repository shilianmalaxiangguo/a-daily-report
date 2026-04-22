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
sys.stderr = os.fdopen(sys.stderr.fileno(), 'w', 1)

"""
A股日报数据获取入口 - 严格按照SKILL.md声明使用数据源（2026-03-31重写版）

严格按照SKILL.md中声明的数据源优先级调用：
1. 热度前十个股：同花顺个股热榜（首选）→ 腾讯财经热股排行（备用）
2. 板块热榜：同花顺板块热榜
3. 指数数据：TencentDataSource（混合方案）
4. 两市成交额：腾讯行情API（实时）+ BaoStock（历史）
5. 涨停跌停数据：akshare涨停跌停池
6. 行业资金流向：腾讯财经板块资金流向
7. 板块涨跌幅排行：同花顺问财API（首选）→ 腾讯财经板块涨跌幅排行（备用）
8. 成交额排名：腾讯财经成交额排行
9. 预期日历：财联社预期日历（CLS接口，封装在 TencentFinanceData.get_calendar_events）
10. 选股通异动：选股通盘中异动分析
11. 顽主杯热门前十：顽主杯API
12. 龙虎榜数据：finshare龙虎榜接口

使用方法：
    python daily_report_entry_demo.py [YYYY-MM-DD]
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
from daily_report_snapshot_io import (
    _save_data_snapshot,
    add_supplementary_perspective,
    load_data_snapshot,
)
from decision.runtime_contracts import (
    get_trade_permission_contract,
    resolve_environment_display_contract,
    resolve_environment_reason_contract,
)
from domains.market_activity.report_sections import (
    build_advanced_activity_report_sections,
    build_market_activity_report_sections,
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
from decision.market_phase_context import build_market_phase_context_contract
from research.market_research_runtime import (
    build_market_research_snapshot_contract,
    derive_step0_follow_plan_contract,
)
from research.market_research_context_bundle import build_market_research_context_bundle_contract
from diagnostics.single_stock_runtime import (
    build_single_stock_diagnostic_contract,
    resolve_single_stock_snapshot_contract,
)
from portfolio.position_management_report import analyze_position_management_report
from replay.report_replay import build_replay_snapshot_contract
from risk.a_kill_blacklist_store import (
    get_active_a_kill_records,
    is_stock_in_a_kill_cooldown,
    load_a_kill_blacklist,
    save_a_kill_blacklist,
    update_a_kill_blacklist,
)
from selection.candidate_bundle_runtime import build_candidate_bundle_contract
from risk.risk_bundle_runtime import build_risk_bundle_contract
from report.action_plan_renderer import render_action_plan_section
from report.appendix_renderer import render_execution_appendix
from report.context_sections_renderer import (
    render_ai_market_insight_section,
    render_mainline_discipline_section,
    render_supplementary_perspective_section,
)
from report.final_conclusion_renderer import build_legacy_final_conclusion_lines
from report.front_summary_renderer import render_front_digest, render_mvp_focus_summary
from report.front_summary_builder import (
    build_front_mainline_label_contract,
    build_front_style_action_text_contract,
    render_core_mvp_digest_contract,
    render_mvp_focus_summary_contract,
)
from report.report_document_builder import (
    build_prohibition_section_contract,
    build_report_shell_contract,
    replace_placeholder_lines,
)
from report.market_research_renderer import (
    render_gem_breathing_pool_section,
    render_gem_breathing_step2_section,
    render_market_research_snapshot_section,
    render_step0_follow_section,
)
from report.board_tag_analysis_builder import build_board_tag_analysis_sections_contract
from report.exchange_monitor_builder import build_exchange_monitor_sections_contract
from report.market_analysis_builder import build_market_and_sector_analysis_contract
from report.market_overview_builder import build_market_trend_sections_contract
from report.pk_decision_renderer import render_pk_decision_section
from report.single_stock_diagnostic_renderer import render_single_stock_diagnostic_markdown
from report.strategy_performance_renderer import render_strategy_performance_section

MARKET_ZHONGSHU_LOOKBACK_DAYS = 120
MARKET_ZHONGSHU_MIN_KLINES = 5
MAX_SINGLE_TRADE_LOSS_PCT = 0.05
# Hook strings moved to daily_report_markdown_hooks.py; wrappers below keep legacy call sites working.
DEFENSIVE_EXIT_RULE_TEXT = "错了就跑：30分钟结构失守立即卖，最晚不超过单笔-5%"
PROFIT_EXIT_RULE_TEXT = "赚了主动卖：3~5日窗口内出现放量大阳优先兑现，最晚第5日收盘评估"
DECISION_STACK_ORDER_TEXT = "环境 -> 主线 -> 记忆 -> 触发 -> 可交易性 -> EV"


def _build_trading_philosophy_lines(include_system_requirement=True, compact=False):
    return markdown_hooks.use_trading_philosophy_lines(
        include_system_requirement=include_system_requirement,
        compact=compact,
    )


def _build_strategy_positioning_lines(compact=False):
    return markdown_hooks.use_strategy_positioning_lines(compact=compact)


def _get_contract_logic_digest_text():
    return markdown_hooks.use_contract_logic_digest_text()


def _build_alignment_pool_text(market_research_snapshot=None, watch_anchor=None, special_probe_verdict=None):
    market_research_snapshot = market_research_snapshot or {}
    observation = market_research_snapshot.get('observation', {}) or {}
    state_machine = market_research_snapshot.get('state_machine', {}) or {}
    watch_anchor = watch_anchor or {}
    special_probe_verdict = special_probe_verdict or {}

    monthly_pool = []
    fermentation_pool = []
    seen = set()

    def append_unique(target, value):
        name = str(value or '').strip()
        if not name or name in seen:
            return
        target.append(name)
        seen.add(name)

    for item in observation.get('mainline_competition_snapshot', []) or []:
        role = str(item.get('role', '') or '').strip()
        sector = str(item.get('sector', '') or '').strip()
        if role in ('主攻线', '次强线'):
            append_unique(monthly_pool, sector)
        elif role == '竞争线':
            append_unique(fermentation_pool, sector)

    if not monthly_pool:
        append_unique(monthly_pool, state_machine.get('leading_line', ''))
        for name in observation.get('mainline_candidates', []) or []:
            append_unique(monthly_pool, name)
            if len(monthly_pool) >= 2:
                break

    for name in observation.get('secondary_candidates', []) or []:
        append_unique(fermentation_pool, name)
        if len(fermentation_pool) >= 3:
            break

    for item in observation.get('sector_trend_snapshot', []) or []:
        append_unique(fermentation_pool, item.get('sector', ''))
        if len(fermentation_pool) >= 3:
            break

    probe_candidate = special_probe_verdict.get('probe_candidate', {}) or {}
    probe_sector = str(
        watch_anchor.get('sector')
        or watch_anchor.get('sector_name')
        or probe_candidate.get('sector')
        or probe_candidate.get('sector_name')
        or ''
    ).strip()
    if not probe_sector and fermentation_pool:
        probe_sector = fermentation_pool[0]

    parts = []
    if monthly_pool:
        parts.append(f"月度站队池：{' / '.join(monthly_pool[:2])}")
    if fermentation_pool:
        parts.append(f"本周发酵方向：{' / '.join(fermentation_pool[:3])}")
    if probe_sector:
        parts.append(f"探针方向：{probe_sector}")
    return '；'.join(parts)


def _build_mainline_rotation_snapshot(observation=None, state_machine=None, style_switch=None, sector_ai_analysis=None):
    observation = observation or {}
    state_machine = state_machine or {}
    style_switch = style_switch or {}
    sector_ai_analysis = sector_ai_analysis or {}

    from collections import Counter

    competition_rows = observation.get('mainline_competition_snapshot', []) or []
    role_counts = Counter()
    role_sectors = {}
    for item in competition_rows:
        role = str(item.get('role', '') or '').strip()
        sector = str(item.get('sector', '') or '').strip()
        if not role:
            continue
        role_counts[role] += 1
        if sector and role not in role_sectors:
            role_sectors[role] = sector

    mainline_sector = str(
        state_machine.get('leading_line', '')
        or role_sectors.get('主攻线', '')
        or (observation.get('mainline_candidates', []) or [''])[0]
        or ''
    ).strip()
    secondary_sector = str(
        role_sectors.get('次强线', '')
        or (observation.get('secondary_candidates', []) or [''])[0]
        or ''
    ).strip()
    competition_sector = str(role_sectors.get('竞争线', '') or '').strip()

    role_counts_text = ' / '.join(
        f"{role}{role_counts.get(role, 0)}条"
        for role in ('主攻线', '次强线', '竞争线', '回避线')
        if role_counts.get(role, 0)
    ) or '暂无接力统计'
    relay_sector_parts = [part for part in (
        f"主攻线{mainline_sector}" if mainline_sector else '',
        f"次强线{secondary_sector}" if secondary_sector else '',
        f"竞争线{competition_sector}" if competition_sector else '',
    ) if part]
    relay_sector_text = ' / '.join(relay_sector_parts) or (mainline_sector or '暂无主线')
    relay_text = f"{relay_sector_text}；接力统计：{role_counts_text}"

    trend_density = int(_safe_float(observation.get('densest_sector_trend_count', 0)))
    resilient_count = int(_safe_float(observation.get('resilient_abnormal_count', 0)))
    failed_count = int(_safe_float(observation.get('failed_abnormal_count', 0)))
    style_code = str(style_switch.get('style_code', '') or '').strip()
    turnover_state = str(style_switch.get('turnover_state', '') or '').strip()
    turnover_label = str(style_switch.get('turnover_label', '') or '').strip()
    pulse_stage = str(state_machine.get('pulse_stage', '') or '').strip()
    state_code = str(state_machine.get('state_code', '') or '').strip()

    if state_code == 'expand':
        rotation_label = '爆发'
        rotation_reason = f"{turnover_label or turnover_state or '量能'}仍支持主线集中，{relay_sector_text}，趋势密度{trend_density}只，接力还在主线内部。"
        rotation_action = f"继续围着{mainline_sector or '主线'}做减法，只盯主攻线承接，不把支线当新中心。"
    elif state_code == 'migrate':
        rotation_label = '分化整理'
        rotation_reason = f"{turnover_label or turnover_state or '量能'}下，主攻线{mainline_sector or '仍在'}，次强线开始分流，市场先整理再决定谁留在中心。"
        rotation_action = f"先看{mainline_sector or '主线'}能否重新聚焦，支线只算轮动，不把分化误判成退潮。"
    elif state_code == 'probe':
        rotation_label = '支线轮动'
        rotation_reason = f"{turnover_label or turnover_state or '量能'}偏分歧，资金在{secondary_sector or '支线'}和{competition_sector or '竞争线'}之间轮换，主线内部开始接力切段。"
        rotation_action = '只跟最有承接的支线，不把每一次轮动都理解成新主线。'
    else:
        if style_code == 'trend' or pulse_stage in ('启动', '加速'):
            rotation_label = '爆发'
            rotation_reason = f"{turnover_label or turnover_state or '量能'}仍支持主线集中，{relay_sector_text}，趋势密度{trend_density}只，接力还在主线内部。"
            rotation_action = f"继续围着{mainline_sector or '主线'}做减法，只盯主攻线承接，不把支线当新中心。"
        elif style_code == 'dual' or pulse_stage == '分歧承接':
            rotation_label = '支线轮动'
            rotation_reason = f"{turnover_label or turnover_state or '量能'}偏分歧，资金在{secondary_sector or '支线'}和{competition_sector or '竞争线'}之间轮换，主线内部开始接力切段。"
            rotation_action = '只跟最有承接的支线，不把每一次轮动都理解成新主线。'
        else:
            rotation_label = '再聚焦'
            rotation_reason = f"{turnover_label or turnover_state or '量能'}收敛后，市场在把权重重新压回少数方向；谁能继续承接，谁就重新拿回中心。"
            rotation_action = f"先等{mainline_sector or '主线'}或新的核心节点重新聚焦，再谈执行。"

    lifecycle_text = '爆发 → 分化整理 → 支线轮动 → 再聚焦'
    style_note = str(style_switch.get('style_reason', '') or turnover_label or turnover_state or '').strip()
    summary_bits = [lifecycle_text, f"当前{rotation_label}"]
    if style_note:
        summary_bits.append(style_note)
    summary_bits.extend([relay_text, f"趋势密度{trend_density}只", f"承接{resilient_count}强/{failed_count}弱"])
    summary_text = '；'.join(summary_bits)

    relationships = sector_ai_analysis.get('relationships', {}) or {}
    mapping = sector_ai_analysis.get('mapping', {}) or {}
    standard_sectors = sector_ai_analysis.get('standard_sectors', []) or []
    node_source = mainline_sector or str(state_machine.get('leading_line', '') or '').strip()
    relation_entry = {}
    relation_name = ''
    if node_source:
        for raw_name, item in relationships.items():
            if raw_name == node_source or sector_name_matches(raw_name, node_source) or sector_name_matches(node_source, raw_name):
                relation_entry = item if isinstance(item, dict) else {}
                relation_name = raw_name
                break
    standard_name = str(
        (relation_entry.get('standard_name', '') if isinstance(relation_entry, dict) else '')
        or mapping.get(node_source, '')
        or mainline_sector
        or node_source
        or ''
    ).strip()
    related = [str(item).strip() for item in (relation_entry.get('related', []) or []) if str(item).strip()][:3]
    parent_name = str(relation_entry.get('parent', '') or '').strip()
    type_name = str(relation_entry.get('type', '') or '').strip()
    if standard_name and standard_name != node_source:
        narrative_label = f"{standard_name}节点"
    elif node_source:
        narrative_label = f"{node_source}节点"
    else:
        narrative_label = '产业叙事节点'
    if relation_entry:
        node_reason_bits = []
        if type_name:
            node_reason_bits.append(type_name)
        if parent_name:
            node_reason_bits.append(f"上看{parent_name}")
        if related:
            node_reason_bits.append(f"相关环节{' / '.join(related)}")
        extra_reason = f"；{'，'.join(node_reason_bits)}" if node_reason_bits else ''
        narrative_reason = f"{relation_name or node_source or '主线'}在归链里更接近{standard_name or node_source or '主线'}这一节点{extra_reason}。"
    elif standard_sectors:
        narrative_reason = f"AI归链把多条板块压到{standard_sectors[0]}等标准方向，当前交易的是{node_source or '主线'}这个承接节点，而不是泛题材扩散。"
    else:
        narrative_reason = f"当前交易的是{node_source or '主线'}这个承接节点，而不是泛题材扩散。"
    narrative_action = f"先盯{node_source or '主线'}的承接是否继续，别把节点切换误当成主线切换。"
    narrative_text = f"{narrative_label}：{narrative_reason}"

    return {
        'rotation_label': rotation_label,
        'rotation_reason': rotation_reason,
        'rotation_action': rotation_action,
        'relay_text': relay_text,
        'relay_counts_text': role_counts_text,
        'rotation_lifecycle_text': lifecycle_text,
        'summary_text': summary_text,
        'narrative_label': narrative_label,
        'narrative_reason': narrative_reason,
        'narrative_action': narrative_action,
        'narrative_text': narrative_text,
    }


def _build_gem_textbook_reference_text(label=''):
    label = str(label or '').strip()
    if label != 'A级教材':
        return ''
    return (
        '参考样本：东山精密（元件/CPO双主线、业绩预增、历史新高）、'
        '朗特智能（消费电子/液冷推进、量价转强）、'
        '均胜电子（汽零/智驾+机器人双曲线、机构调研支撑）；'
        '反例：常友科技（风电设备，板块热度和持续性都弱）'
    )


def _build_gem_textbook_front_text(candidate=None, position_decision=None):
    candidate = candidate or {}
    position_decision = position_decision or {}
    if str(candidate.get('watch_source', '') or '').strip() != 'gem_breathing_20cm' and not candidate.get('textbook_label'):
        return ''

    label = str(candidate.get('textbook_label', '') or '').strip()
    profile = candidate.get('textbook_profile', {}) or {}
    last_active_date = str(profile.get('last_active_date', '') or '').strip()
    total_active_count = int(_safe_float(profile.get('total_active_count', 0)))
    tight_count = int(_safe_float(profile.get('tight_count', 0)))
    loose_count = int(_safe_float(profile.get('loose_count', 0)))
    target_position_pct = int(_safe_float(position_decision.get('target_position_pct', 0)))
    trigger_text = str(position_decision.get('trigger_text', '') or '完成60分钟确认').strip()
    ready = bool(position_decision.get('candidate_feedback_ready'))

    prefix_parts = []
    if label:
        prefix_parts.append(label)
    if total_active_count:
        prefix_parts.append(f"近60日{total_active_count}次")
    if tight_count or loose_count:
        prefix_parts.append(f"tight {tight_count} / loose {loose_count}")
    if last_active_date:
        prefix_parts.append(f"最近一次{last_active_date}")
    prefix = '，'.join(prefix_parts) if prefix_parts else '20cm教材样本'

    reference_text = _build_gem_textbook_reference_text(label)
    if reference_text:
        prefix = f"{prefix}；{reference_text}"

    if target_position_pct == 30:
        next_step = f"当前已进入30%条件试错候选，{trigger_text}后才允许试错"
    elif label == 'A级教材':
        next_step = f"当前还差右侧确认和60分钟确认，确认后才评估30%条件试错" if not ready else f"反馈已接近到位，{trigger_text}后可评估30%条件试错"
    elif label == 'B级教材':
        next_step = '先保留观察合同，等它走成右侧确认后再考虑升级'
    elif label == 'C级观察样本':
        next_step = '不提前升级，只跟踪它会不会再次复现并走成右侧确认'
    else:
        next_step = '先保留观察合同，不直接给执行权'

    return f"{prefix}；{next_step}"


def _build_gem_textbook_next_step_text(candidate=None, position_decision=None):
    front_text = _build_gem_textbook_front_text(candidate=candidate, position_decision=position_decision)
    if not front_text:
        return ''
    parts = [part.strip() for part in str(front_text).split('；') if part.strip()]
    return parts[-1] if parts else ''


def _build_weak_to_strong_context(candidate=None, mainline_name='', state_machine_snapshot=None):
    candidate = candidate or {}
    state_machine_snapshot = state_machine_snapshot or {}
    mainline_name = str(mainline_name or state_machine_snapshot.get('leading_line', '') or '').strip()
    name = str(candidate.get('name', '-') or '-').strip()
    code = str(candidate.get('code', '-') or '-').strip()
    setup_id = str(_resolve_candidate_setup_id(candidate) or '').strip()
    follow_state = str(_resolve_candidate_follow_state(candidate) or '').strip()
    energy_state = str(state_machine_snapshot.get('energy_state', '') or '').strip()
    pulse_stage = str(state_machine_snapshot.get('pulse_stage', '') or '').strip()
    strong_base = setup_id in (
        'burst_hold', 'burst_digest', 'upper_shadow_reclaim', 'upper_shadow_digest', 'horror_wash_hold', 'horror_wash_digest'
    ) or '核心' in str(candidate.get('core_level', '') or '')
    fake_weak = follow_state in ('跌不下去', '缩量消化')
    mainline_support = _candidate_matches_mainline(candidate, mainline_name) if mainline_name else False
    retreat_risk = energy_state == '收缩防守' or pulse_stage == '退潮'

    if strong_base and fake_weak and mainline_support and not retreat_risk:
        return {
            'active': True,
            'scenario': 'active',
            'summary_text': f"{name}({code})，第一波强势基础还在，当前是假弱非真弱；只在{mainline_name or '主线'}板块共振未坏时看后续超预期转强",
            'note_text': '强基底+假弱非真弱，只在主线共振未坏时继续等超预期转强',
            'score_bonus': 160,
            'lone_hero': False,
        }
    if strong_base and follow_state == '已经转弱':
        return {
            'active': False,
            'scenario': 'true_weak',
            'summary_text': f"{name}({code}) 前面虽有强基底，但现在已经转弱，更像真弱，不再按弱转强处理",
            'note_text': '已经转弱，更像真弱，先从顶级买点序列降级',
            'score_bonus': -120,
            'lone_hero': False,
        }
    if strong_base and fake_weak and retreat_risk:
        return {
            'active': False,
            'scenario': 'retreat_downgrade',
            'summary_text': f"{name}({code}) 虽有强基底和假弱特征，但当前环境更像退潮/防守期，弱转强先降级为观察",
            'note_text': '当前处于退潮/防守期，弱转强先降级为观察，不按顶级买点处理',
            'score_bonus': 0,
            'lone_hero': False,
        }
    if strong_base and fake_weak and not mainline_support:
        return {
            'active': False,
            'scenario': 'lone_hero',
            'summary_text': f"{name}({code}) 虽有假弱转强形态，但当前更像孤胆英雄，缺少板块共振，不按顶级买点处理",
            'note_text': '形态虽像假弱转强，但缺少板块共振，只保留观察权',
            'score_bonus': 0,
            'lone_hero': True,
        }
    return {
        'active': False,
        'scenario': 'inactive',
        'summary_text': '',
        'note_text': '',
        'score_bonus': 0,
        'lone_hero': False,
    }


def _build_philosophy_constraint_text(
    final_gate=None,
    best_stock=None,
    watch_anchor=None,
    watch_anchor_type='',
    state_machine_snapshot=None,
):
    final_gate = final_gate or {}
    state_machine_snapshot = state_machine_snapshot or {}
    watch_anchor_type = str(watch_anchor_type or '').strip()
    energy_state = str(state_machine_snapshot.get('energy_state', '') or '').strip()
    execution_bias = str(state_machine_snapshot.get('execution_bias', '') or '').strip()
    fragments = []

    if best_stock:
        fragments.append('不为新故事切掉旧事实，只围绕已被市场证明的主线强者行动')
        if final_gate.get('can_new_entry'):
            fragments.append('这更像切入的钱，不是到处换故事的钱')
        else:
            fragments.append('若你已有主线核心，更先想卖不卖，而不是买不买')
    elif watch_anchor and '跨线' in watch_anchor_type:
        fragments.append('不为新故事切掉旧事实')

    if final_gate.get('can_new_entry') and any(key in energy_state for key in ('扩张', '进攻')):
        fragments.append('外部风险若已被市场脱敏，只保留背景作用')

    if execution_bias in ('watch_only', 'divergence_only', 'avoid') or (watch_anchor and '跨线' in watch_anchor_type):
        fragments.append('主观理解只用于观察，不用于提前硬上')

    ordered = []
    for fragment in fragments:
        text = str(fragment or '').strip()
        if text and text not in ordered:
            ordered.append(text)
    return '；'.join(ordered)

INTRADAY_CONFIRM_LOOKBACK_60M = 8
INTRADAY_STOP_LOOKBACK_30M = 12
TRACKING_MEMORY_KEEP_DAYS = 20
TRACKING_MEMORY_TENTATIVE_EXPIRE_DAYS = 5
TRACKING_MEMORY_MAX_ITEMS = 40
TRACKING_MEMORY_PROMOTE_CONFIRMATIONS = 2
STRATEGY_HOLDING_DAYS_MIN = 3
STRATEGY_HOLDING_DAYS_MAX = 5
STRATEGY_PERFORMANCE_LEDGER_VERSION = "v2"
STRATEGY_FACTOR_SNAPSHOT_VERSION = "v3"
DISPLAY_MVP_MODE = True
DECISION_STRICT_MODE = True
ALLOW_DISPLAY_DEGRADED_ABNORMAL_SNAPSHOT = False
LEDGER_MODE_FROZEN = "frozen"
LEDGER_MODE_REPLAY = "replay"
REPORT_VARIANT_FULL = "full"
REPORT_VARIANT_SUMMARY = "summary"
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
ABNORMAL_SETUP_LIBRARY = {
    'burst_hold': {
        'label': '大阳后抗跌',
        'phase': 'hold',
        'group': 'burst',
    },
    'burst_digest': {
        'label': '大阳后缩量消化',
        'phase': 'digest',
        'group': 'burst',
    },
    'upper_shadow_reclaim': {
        'label': '长上影后收复',
        'phase': 'hold',
        'group': 'upper_shadow',
    },
    'upper_shadow_digest': {
        'label': '长上影后消化',
        'phase': 'digest',
        'group': 'upper_shadow',
    },
    'horror_wash_hold': {
        'label': '恐怖阴线后抗跌',
        'phase': 'hold',
        'group': 'horror_wash',
    },
    'horror_wash_digest': {
        'label': '恐怖阴线后消化',
        'phase': 'digest',
        'group': 'horror_wash',
    },
    'fresh_abnormal_probe': {
        'label': '新异动试盘',
        'phase': 'probe',
        'group': 'fresh',
    },
    'abnormal_failed': {
        'label': '异动失效',
        'phase': 'failed',
        'group': 'failed',
    },
}

SETUP_EXECUTION_CONTRACTS = {
    'burst_hold': {
        'holding_days_min': 2,
        'holding_days_max': 4,
        'profit_take_pct': 0.05,
        'profit_exit_rule': '赚了主动卖：2~4日内若再走放量大阳/加速，优先兑现；次日不继续强化就主动收紧。',
    },
    'burst_digest': {
        'holding_days_min': 2,
        'holding_days_max': 4,
        'profit_take_pct': 0.04,
        'profit_exit_rule': '赚了主动卖：2~4日内只接受缩量消化后再转强；拖成横盘就减，不把短线拿成长线。',
    },
    'upper_shadow_reclaim': {
        'holding_days_min': 1,
        'holding_days_max': 3,
        'profit_take_pct': 0.04,
        'profit_exit_rule': '赚了主动卖：1~3日内若重新站回实体并继续冲高，优先兑现；收不回实体就不恋战。',
    },
    'upper_shadow_digest': {
        'holding_days_min': 2,
        'holding_days_max': 3,
        'profit_take_pct': 0.035,
        'profit_exit_rule': '赚了主动卖：只接受短暂消化后再收复实体；超过3日还磨蹭，主动结束交易。',
    },
    'horror_wash_hold': {
        'holding_days_min': 1,
        'holding_days_max': 3,
        'profit_take_pct': 0.05,
        'profit_exit_rule': '赚了主动卖：恐怖阴线后的修复只看快修复，1~3日内不能连续拔高就先兑现，不等二次回落。',
    },
    'horror_wash_digest': {
        'holding_days_min': 2,
        'holding_days_max': 4,
        'profit_take_pct': 0.04,
        'profit_exit_rule': '赚了主动卖：先接受缩量稳住，再等转强兑现；若迟迟不能转强，按短线节奏离场。',
    },
    'fresh_abnormal_probe': {
        'holding_days_min': 1,
        'holding_days_max': 2,
        'profit_take_pct': 0.03,
        'profit_exit_rule': '赚了主动卖：新异动试盘只给1~2天验证，能放大就留，不能放大就撤。',
    },
    'abnormal_failed': {
        'holding_days_min': 1,
        'holding_days_max': 1,
        'profit_take_pct': 0.02,
        'profit_exit_rule': '异动失效不做利润预期，只保留失败记录。',
    },
}

SETUP_PRIORITY_SCORE_MAP = {
    'horror_wash_hold': 100,
    'upper_shadow_reclaim': 96,
    'burst_hold': 92,
    'horror_wash_digest': 82,
    'upper_shadow_digest': 78,
    'burst_digest': 74,
    'fresh_abnormal_probe': 58,
    'abnormal_failed': 0,
}

FOLLOW_STATE_PRIORITY_SCORE_MAP = {
    '跌不下去': 86,
    '缩量消化': 72,
    '新异动待观察': 50,
    '已经转弱': 0,
}


def _resolve_candidate_setup_id(candidate):
    candidate = candidate or {}
    return str(
        candidate.get('abnormal_setup_signal_id')
        or candidate.get('setup_signal_id')
        or ''
    ).strip()


def _resolve_candidate_follow_state(candidate):
    candidate = candidate or {}
    return str(
        candidate.get('abnormal_follow_state')
        or candidate.get('follow_state')
        or ''
    ).strip()


def _candidate_has_formal_abnormal_setup(candidate):
    setup_id = _resolve_candidate_setup_id(candidate)
    return bool(setup_id and setup_id not in ('abnormal_failed',))


def _candidate_is_resilient_abnormal(candidate):
    return _resolve_candidate_follow_state(candidate) in ('跌不下去', '缩量消化')


def _is_bridge_priority_setup(candidate, mainline_name=''):
    candidate = candidate or {}
    if not (candidate.get('is_mainline') or _candidate_matches_mainline(candidate, mainline_name)):
        return False
    return (
        _resolve_candidate_setup_id(candidate) == 'burst_hold'
        and _resolve_candidate_follow_state(candidate) == '跌不下去'
    )


def _get_setup_execution_contract(setup_id='', follow_state=''):
    setup_id = str(setup_id or '').strip()
    follow_state = str(follow_state or '').strip()

    contract = dict(SETUP_EXECUTION_CONTRACTS.get(setup_id, {}))
    if not contract:
        contract = {
            'holding_days_min': STRATEGY_HOLDING_DAYS_MIN,
            'holding_days_max': STRATEGY_HOLDING_DAYS_MAX,
            'profit_take_pct': 0.05,
            'profit_exit_rule': PROFIT_EXIT_RULE_TEXT,
        }

    if follow_state == '新异动待观察':
        contract['holding_days_min'] = min(contract.get('holding_days_min', 1), 1)
        contract['holding_days_max'] = min(contract.get('holding_days_max', 2), 2)
    elif follow_state == '已经转弱':
        contract['holding_days_min'] = 1
        contract['holding_days_max'] = 1

    contract.setdefault('holding_days_min', STRATEGY_HOLDING_DAYS_MIN)
    contract.setdefault('holding_days_max', STRATEGY_HOLDING_DAYS_MAX)
    contract.setdefault('profit_take_pct', 0.05)
    contract.setdefault('profit_exit_rule', PROFIT_EXIT_RULE_TEXT)
    return contract


def _get_setup_priority_score(setup_id='', follow_state=''):
    setup_id = str(setup_id or '').strip()
    follow_state = str(follow_state or '').strip()
    if setup_id:
        return SETUP_PRIORITY_SCORE_MAP.get(
            setup_id,
            FOLLOW_STATE_PRIORITY_SCORE_MAP.get(follow_state, 24),
        )
    return FOLLOW_STATE_PRIORITY_SCORE_MAP.get(follow_state, 18)


def _infer_risk_level_from_abnormal_follow_state(follow_state):
    follow_state = str(follow_state or '').strip()
    if follow_state == '跌不下去':
        return '🟢 低风险'
    if follow_state == '缩量消化':
        return '🟡 中风险'
    if follow_state == '新异动待观察':
        return '🟠 待确认'
    if follow_state == '已经转弱':
        return '🔴 高风险'
    return '🟡 中风险'


def _map_setup_id_to_signal_type(setup_id=''):
    setup_id = str(setup_id or '').strip()
    if setup_id in ('horror_wash_hold', 'horror_wash_digest'):
        return 'panic_buy'
    if setup_id in ('upper_shadow_reclaim', 'upper_shadow_digest'):
        return 'sweet_zone'
    if setup_id in ('burst_hold', 'burst_digest', 'fresh_abnormal_probe'):
        return 'breakout'
    return ''


def _format_holding_window_text(min_days, max_days):
    min_days = int(_safe_float(min_days, STRATEGY_HOLDING_DAYS_MIN) or STRATEGY_HOLDING_DAYS_MIN)
    max_days = int(_safe_float(max_days, STRATEGY_HOLDING_DAYS_MAX) or STRATEGY_HOLDING_DAYS_MAX)
    if min_days >= max_days:
        return f"{max_days}天内"
    return f"{min_days}-{max_days}天"


def _build_candidate_exit_rules(candidate=None, stop_plan=None):
    candidate = candidate or {}
    follow_state = _resolve_candidate_follow_state(candidate)
    setup_id = _resolve_candidate_setup_id(candidate)
    contract = _get_setup_execution_contract(setup_id, follow_state)

    effective_stop = None
    if stop_plan:
        effective_stop = _round_or_none(stop_plan.get('effective_stop'))
    if effective_stop is None:
        effective_stop = _round_or_none(candidate.get('stop_loss'))

    defensive_rule = DEFENSIVE_EXIT_RULE_TEXT
    if effective_stop is not None:
        defensive_rule = (
            f"错了就跑：这笔交易如果还对，就不该失守{effective_stop:.2f}；"
            f"30分钟结构失守立即卖，最晚不超过单笔-5%"
        )

    return {
        'holding_days_min': contract.get('holding_days_min', STRATEGY_HOLDING_DAYS_MIN),
        'holding_days_max': contract.get('holding_days_max', STRATEGY_HOLDING_DAYS_MAX),
        'profit_take_pct': contract.get('profit_take_pct', 0.05),
        'defensive_exit_rule': defensive_rule,
        'profit_exit_rule': contract.get('profit_exit_rule', PROFIT_EXIT_RULE_TEXT),
    }


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

def ai_analyze_sector_relationships(sector_list, context_info=""):
    """AI智能分析板块关系，识别产业链聚集效应
    
    使用DeepSeek LLM API进行真正的智能分析，不是简单的规则匹配。
    
    Args:
        sector_list: 板块标签列表，如 ['化学制药', '医药流通', '光模块', 'CPO']
        context_info: 上下文信息（如市场背景、日期等）
    
    Returns:
        dict: {
            'groups': [
                {
                    'name': '大方向名称',
                    'sectors': ['板块1', '板块2'],
                    'reason': '归类理由（产业链逻辑）',
                    'investment_logic': '资金博弈逻辑'
                }
            ],
            'insights': 'AI深度洞察'
        }
    """
    global _llm_call_stats
    start_time = time.time()
    
    try:
        client = get_llm_service()
        result = client.analyze_sector_relationships(sector_list, context_info)
        
        # 记录统计
        elapsed = time.time() - start_time
        _llm_call_stats['total_calls'] += 1
        _llm_call_stats['total_time'] += elapsed
        _llm_call_stats['sector_analysis_calls'] += 1
        _llm_call_stats['sector_analysis_time'] += elapsed
        
        return result
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"[ai_analyze_sector_relationships] LLM调用失败({elapsed:.2f}s)，使用兜底方案: {e}")
        return {'groups': [], 'insights': 'LLM分析失败，无法生成产业链洞察'}


def _llm_sector_analysis(sectors, context):
    """模拟LLM分析过程（实际可替换为真实LLM调用）
    
    基于业务逻辑进行智能分析，识别：
    1. 产业链关系（上游/中游/下游）
    2. 技术路线关系（同一技术不同环节）
    3. 应用场景关系（同一应用不同组件）
    """
    # 产业链知识库（内置逻辑，可扩展）
    industry_chains = {
        '医药医疗': {
            'keywords': ['医药', '医疗', '制药', '生物', 'CXO', 'CRO', '中药', '化学制药', '生物制品', '医疗器械', '医药商业', '医药流通', '医疗服务', '创新药', '重组蛋白', '仿制药', '疫苗'],
            'segments': {
                '研发服务': ['CRO', 'CXO', '医疗研发外包'],
                '药品制造': ['化学制药', '生物制品', '中药', '创新药', '重组蛋白', '仿制药', '疫苗'],
                '流通销售': ['医药商业', '医药流通'],
                '医疗服务': ['医疗服务', '医疗器械', '其他医疗服务', '创新医疗服务']
            }
        },
        '光通信': {
            'keywords': ['光通信', '光模块', '光纤', '光缆', 'CPO', '通信线缆', '光芯片', '光器件', '光引擎', '硅光', '激光雷达', '光通信模块', '通信网络设备', 'OCS', '全光交换'],
            'segments': {
                '传输介质': ['光纤', '光缆', '通信线缆', '通信线缆及配套'],
                '核心器件': ['光模块', '光通信模块', '光芯片', '光器件', '光引擎', 'CPO', '共封装光学'],
                '系统设备': ['光通信', '通信网络设备', '通信网络设备及器件', 'OCS', '全光交换'],
                '终端应用': ['激光雷达']
            }
        },
        'AI算力': {
            'keywords': ['算力', 'AI芯片', '服务器', '数据中心', '云计算', '液冷', '存储芯片', '半导体', '芯片', '通信设备', '通信'],
            'segments': {
                '芯片算力': ['AI芯片', '芯片', '半导体', '存储芯片'],
                '基础设施': ['服务器', '数据中心', '云计算', '液冷', '液冷服务器'],
                '网络通信': ['通信设备', '通信', '算力']
            }
        },
        '人形机器人': {
            'keywords': ['机器人', '人形机器人', '具身智能', '减速器', '伺服电机', '执行器', '传感器', '电机'],
            'segments': {
                '核心零部件': ['减速器', '伺服电机', '执行器', '传感器', '电机'],
                '整机系统': ['机器人', '人形机器人', '具身智能']
            }
        },
        '新能源': {
            'keywords': ['光伏', '储能', '锂电池', '电池', '电力', '电网', '风电', '核电', '氢能源', '固态电池', '电网设备'],
            'segments': {
                '发电端': ['光伏', '风电', '核电', '氢能源'],
                '储能端': ['储能', '锂电池', '电池', '固态电池'],
                '输配电': ['电力', '电网', '电网设备']
            }
        },
        '汽车产业链': {
            'keywords': ['汽车', '汽车零部件', '整车', '新能源车', '智能驾驶', '无人驾驶', '车联网'],
            'segments': {
                '整车制造': ['整车', '汽车', '新能源车'],
                '零部件': ['汽车零部件'],
                '智能系统': ['智能驾驶', '无人驾驶', '车联网']
            }
        }
    }
    
    # 执行智能匹配
    matched_groups = {}
    unmatched = []
    
    for sector in sectors:
        matched = False
        for chain_name, chain_info in industry_chains.items():
            # 检查是否匹配该产业链
            for keyword in chain_info['keywords']:
                if keyword in sector or sector in keyword:
                    if chain_name not in matched_groups:
                        matched_groups[chain_name] = {
                            'sectors': [],
                            'segments': {k: [] for k in chain_info['segments'].keys()}
                        }
                    matched_groups[chain_name]['sectors'].append(sector)
                    
                    # 进一步细分到产业链环节
                    for segment_name, segment_keywords in chain_info['segments'].items():
                        for sk in segment_keywords:
                            if sk in sector or sector in sk:
                                matched_groups[chain_name]['segments'][segment_name].append(sector)
                                break
                    
                    matched = True
                    break
            if matched:
                break
        
        if not matched:
            unmatched.append(sector)
    
    # 构建分析结果
    groups = []
    for chain_name, data in matched_groups.items():
        # 生成归类理由
        segments_with_data = {k: v for k, v in data['segments'].items() if v}
        if segments_with_data:
            segment_desc = '、'.join([f"{k}({'、'.join(v[:2])}等)" for k, v in list(segments_with_data.items())[:2]])
            reason = f"同属{chain_name}产业链，涵盖{segment_desc}"
        else:
            reason = f"同属{chain_name}大方向"
        
        # 生成资金博弈逻辑
        if chain_name == '医药医疗':
            investment_logic = "防守属性，博弈医药改革/创新药政策预期"
        elif chain_name == '光通信':
            investment_logic = "AI算力基建受益方向，高速光互联需求驱动"
        elif chain_name == 'AI算力':
            investment_logic = "AI产业核心基础设施，算力需求持续增长"
        elif chain_name == '人形机器人':
            investment_logic = "智能制造新方向，产业政策支持"
        elif chain_name == '新能源':
            investment_logic = "能源转型大趋势，政策+需求双驱动"
        elif chain_name == '汽车产业链':
            investment_logic = "新能源汽车渗透率提升，智能化加速"
        else:
            investment_logic = "产业链景气度提升，资金关注度高"
        
        groups.append({
            'name': chain_name,
            'sectors': data['sectors'],
            'reason': reason,
            'investment_logic': investment_logic
        })
    
    # 未匹配的单独列出
    for sector in unmatched:
        groups.append({
            'name': sector,
            'sectors': [sector],
            'reason': '独立板块，暂无明确产业链关联',
            'investment_logic': '需单独分析其驱动逻辑'
        })
    
    # 生成AI深度洞察
    insights = _generate_ai_insights(groups, context)
    
    return {
        'groups': groups,
        'insights': insights
    }


def _generate_ai_insights(groups, context):
    """生成AI深度洞察"""
    insights = []
    
    # 分析资金聚集方向
    if len(groups) >= 2:
        insights.append(f"资金在博弈{len(groups)}个大方向：")
        for g in groups:
            insights.append(f"- **{g['name']}**：{g['investment_logic']}")
    
    # 分析板块关系
    has_defensive = any(g['name'] in ['医药医疗'] for g in groups)
    has_growth = any(g['name'] in ['光通信', 'AI算力', '人形机器人'] for g in groups)
    
    if has_defensive and has_growth:
        insights.append("\n**配置特征**：资金在'防守+进攻'双向布局，成长与价值兼顾")
    elif has_defensive:
        insights.append("\n**配置特征**：偏向防守，市场风险偏好较低")
    elif has_growth:
        insights.append("\n**配置特征**：偏向进攻，看好科技成长方向")
    
    # 主线一致性判断
    mainline_consistency = "分散" if len(groups) > 2 else "相对集中"
    insights.append(f"\n**主线判断**：资金聚集{mainline_consistency}，{'缺乏明确主线，需观察哪个方向能走出持续性' if len(groups) > 2 else '有明确主线方向'}")
    
    return '\n'.join(insights)


# ============================================================


def get_execution_framework_text():
    """统一的盘前预案执行框架文案。"""
    return markdown_hooks.use_execution_framework_text()


def build_stop_execution_plan(entry_price, structure_stop=None, structure_label='结构止损'):
    return analysis_utils.build_stop_execution_plan(entry_price, structure_stop=structure_stop, structure_label=structure_label)


def calculate_price_range(stock_data):
    return analysis_utils.calculate_price_range(stock_data)


def get_sector_change_from_iwencai(rank_type='up', limit=10, target_date=None):
    """
    获取板块涨跌幅排行 - 使用同花顺问财API
    
    Args:
        rank_type: 'up' 涨幅，'down' 跌幅
        limit: 返回数量，默认10
        target_date: 目标日期（YYYY-MM-DD格式），默认None表示今天
    
    Returns:
        板块列表，包含名称、涨跌幅、主力净流入、领涨股
        格式与腾讯财经API保持一致
    """
    try:
        import urllib.request
        import json
        from datetime import datetime, timedelta
        
        # 确定查询日期
        if target_date:
            # 解析目标日期
            if isinstance(target_date, str):
                # 支持YYYY-MM-DD格式
                query_date = datetime.strptime(target_date, '%Y-%m-%d')
            else:
                query_date = target_date
            
            # 构建日期字符串
            date_str = query_date.strftime('%Y-%m-%d')
            date_compact = query_date.strftime('%Y%m%d')
            
            # 判断是今天、昨天还是其他日期
            today = datetime.now().date()
            query_date_only = query_date.date()
            
            if query_date_only == today:
                date_keyword = "今日"
            elif query_date_only == today - timedelta(days=1):
                date_keyword = "昨日"
            else:
                # 其他历史日期，使用具体日期
                date_keyword = date_str
        else:
            # 默认今天
            date_keyword = "今日"
            date_compact = datetime.now().strftime('%Y%m%d')
        
        # 构建查询语句
        if rank_type == 'up':
            query = f"{date_keyword}涨幅前{limit}的板块，包括主力净流入、领涨股、领涨股涨跌幅"
        else:
            query = f"{date_keyword}跌幅前{limit}的板块，包括主力净流入、领涨股、领涨股涨跌幅"
        
        url = "https://openapi.iwencai.com/v1/query2data"
        headers = {
            "Authorization": f"Bearer {os.environ.get('IWENCAI_API_KEY', '')}",
            "Content-Type": "application/json"
        }
        payload = {
            "query": query,
            "page": "1",
            "limit": str(limit),
            "is_cache": "1",
            "expand_index": "true"
        }
        
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=data, headers=headers, method="POST")
        response = urllib.request.urlopen(request, timeout=30)
        result = json.loads(response.read().decode("utf-8"))
        
        if result.get("status_code", 0) == 0 and result.get('datas'):
            sectors = []
            for item in result['datas']:
                # 解析问财返回的数据格式
                sector_name = item.get('指数简称', '?')
                
                # 涨跌幅（优先使用带日期的字段）
                change_pct = item.get(f'涨跌幅[{date_compact}]', item.get('最新涨跌幅:前复权', 0))
                if isinstance(change_pct, str):
                    change_pct = float(change_pct.replace('%', ''))
                
                # 主力净买入额（单位：元，转换为亿）
                net_inflow = item.get(f'主力净买入额[{date_compact}]', 0)
                if isinstance(net_inflow, (int, float)):
                    net_inflow = net_inflow / 1e8  # 元转换为亿
                elif isinstance(net_inflow, str):
                    if '亿' in net_inflow:
                        net_inflow = float(net_inflow.replace('亿', ''))
                    elif '万' in net_inflow:
                        net_inflow = float(net_inflow.replace('万', '')) / 10000
                    else:
                        net_inflow = float(net_inflow)
                
                # 领涨股
                lzg_name = item.get(f'领涨股简称[{date_compact}]', '?')
                lzg_code = item.get(f'领涨股代码[{date_compact}]', '?')
                
                sectors.append({
                    'name': sector_name,
                    'code': item.get('指数代码', '?'),
                    'zdf': change_pct,
                    'zljlr': net_inflow,  # 单位：亿
                    'lzg_name': lzg_name,
                    'lzg_zdf': 0,  # 问财API不返回领涨股涨跌幅，设为0
                })
            return sectors
        else:
            print(f"[问财API] 板块涨跌幅查询失败: {result.get('status_msg', 'unknown error')}")
            return []
            
    except Exception as e:
        print(f"[问财API] 板块涨跌幅查询异常: {e}")
        return []


def _normalize_kline_date_str(date_value):
    """标准化K线日期到 YYYY-MM-DD，兼容 YYYYMMDD / YYYY-MM-DD / datetime"""
    if date_value is None:
        return ""

    if hasattr(date_value, 'strftime'):
        return date_value.strftime('%Y-%m-%d')

    date_str = str(date_value).strip()
    if not date_str:
        return ""

    date_str = date_str.split(' ')[0].replace('/', '-')

    if len(date_str) == 8 and date_str.isdigit():
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"

    if len(date_str) >= 10 and date_str[4] == '-' and date_str[7] == '-':
        return date_str[:10]

    return date_str


def _parse_kline_date(date_value):
    """解析K线日期，失败时返回None"""
    normalized = _normalize_kline_date_str(date_value)
    if not normalized:
        return None

    try:
        return datetime.datetime.strptime(normalized, '%Y-%m-%d').date()
    except ValueError:
        return None


def _split_zhongshu_history_and_today(df, recent_days=120, target_date=None):
    """
    将K线数据拆分为“历史中枢窗口”和“比较日”

    核心规则：
    1. 先按target_date截断，只保留目标日及之前的数据
    2. 再取最近N+1根K线
    3. 最后一根作为比较日，前N根用于计算中枢
    """
    if df is None or len(df) == 0:
        raise ValueError("K线数据为空")
    if 'date' not in df.columns:
        raise ValueError("K线数据缺少date列")

    prepared_df = df.copy()
    prepared_df['date'] = prepared_df['date'].map(_normalize_kline_date_str)
    prepared_df['_date_obj'] = prepared_df['date'].map(_parse_kline_date)
    prepared_df = prepared_df.dropna(subset=['_date_obj']).sort_values('_date_obj').reset_index(drop=True)

    if target_date:
        target_dt = _parse_kline_date(target_date)
        if target_dt is None:
            raise ValueError(f"无法解析target_date: {target_date}")
        prepared_df = prepared_df[prepared_df['_date_obj'] <= target_dt].reset_index(drop=True)

    if len(prepared_df) < 2:
        raise ValueError("可用K线不足，无法拆分历史中枢和比较日")

    recent_df = prepared_df.tail(recent_days + 1).reset_index(drop=True)
    hist_df = recent_df.iloc[:-1].copy()
    today_df = recent_df.iloc[-1].copy()

    return recent_df, hist_df, today_df


def _build_structure_segment(hist_df, start_idx, end_idx, segment_type, zg=None, zd=None, reason=""):
    """构建结构分段，确保每根K线都能归属到中枢或连接段"""
    start_row = hist_df.iloc[start_idx]
    end_row = hist_df.iloc[end_idx]
    segment_slice = hist_df.iloc[start_idx:end_idx + 1]
    segment_high = float(segment_slice['high'].max())
    segment_low = float(segment_slice['low'].min())
    start_close = float(start_row['close'])
    end_close = float(end_row['close'])
    segment = {
        'segment_type': segment_type,
        'start_idx': int(start_idx),
        'end_idx': int(end_idx),
        'start_date': start_row['date'],
        'end_date': end_row['date'],
        'kline_count': int(end_idx - start_idx + 1),
        'segment_high': segment_high,
        'segment_low': segment_low,
        'start_close': start_close,
        'end_close': end_close,
        'reason': reason,
    }

    if segment_type == 'zhongshu':
        segment['zg'] = float(zg)
        segment['zd'] = float(zd)

    return segment


def _build_zhongshu_structure(hist_df, min_zhongshu_klines=5, min_overlap_bars=3):
    """
    沿用连续重叠分段识别中枢，并保留全部非中枢K线为连接段

    说明：
    1. 保持现有“相邻K线连续重叠”这套分段边界，避免中枢大框架突变
    2. 任何未形成确认中枢的K线，也必须保留为连接段，不能直接丢弃
    """
    if hist_df is None or len(hist_df) == 0:
        return [], []

    total = len(hist_df)
    structure_segments = []
    zhongshu_list = []
    run_start = 0
    run_high = float(hist_df.iloc[0]['high'])
    run_low = float(hist_df.iloc[0]['low'])

    for idx in range(1, total):
        prev_row = hist_df.iloc[idx - 1]
        row = hist_df.iloc[idx]
        overlap_high = min(float(prev_row['high']), float(row['high']))
        overlap_low = max(float(prev_row['low']), float(row['low']))

        if overlap_high > overlap_low:
            run_high = max(run_high, float(row['high']))
            run_low = min(run_low, float(row['low']))
            continue

        run_end = idx - 1
        segment_type = 'zhongshu' if (run_end - run_start + 1) >= min_zhongshu_klines else 'connector'
        segment_reason = (
            '连续重叠区间达到确认长度，识别为中枢'
            if segment_type == 'zhongshu'
            else '连续重叠长度不足确认中枢，保留为连接段'
        )
        segment = _build_structure_segment(
            hist_df,
            run_start,
            run_end,
            segment_type,
            zg=run_high if segment_type == 'zhongshu' else None,
            zd=run_low if segment_type == 'zhongshu' else None,
            reason=segment_reason,
        )
        structure_segments.append(segment)
        if segment_type == 'zhongshu':
            zhongshu_list.append(segment.copy())

        run_start = idx
        run_high = float(row['high'])
        run_low = float(row['low'])

    run_end = total - 1
    segment_type = 'zhongshu' if (run_end - run_start + 1) >= min_zhongshu_klines else 'connector'
    segment_reason = (
        '连续重叠区间达到确认长度，识别为中枢'
        if segment_type == 'zhongshu'
        else '历史尾部尚未达到确认中枢长度，作为连接段保留'
    )
    segment = _build_structure_segment(
        hist_df,
        run_start,
        run_end,
        segment_type,
        zg=run_high if segment_type == 'zhongshu' else None,
        zd=run_low if segment_type == 'zhongshu' else None,
        reason=segment_reason,
    )
    structure_segments.append(segment)
    if segment_type == 'zhongshu':
        zhongshu_list.append(segment.copy())

    for idx, segment in enumerate(structure_segments):
        if segment['segment_type'] != 'connector':
            continue

        has_prev_zhongshu = any(s['segment_type'] == 'zhongshu' for s in structure_segments[:idx])
        has_next_zhongshu = any(s['segment_type'] == 'zhongshu' for s in structure_segments[idx + 1:])
        if has_prev_zhongshu and has_next_zhongshu:
            segment['connector_role'] = 'between'
        elif has_prev_zhongshu:
            segment['connector_role'] = 'trailing'
        else:
            segment['connector_role'] = 'leading'

    return structure_segments, zhongshu_list


def _short_date(date_str):
    """将 YYYY-MM-DD 缩短为 MM-DD，便于ASCII结构图展示"""
    normalized = _normalize_kline_date_str(date_str)
    if len(normalized) >= 10:
        return normalized[5:10]
    return normalized


def _build_zhongshu_ascii_diagram(structure_segments, today_date, today_price, signal, max_segments=5):
    """构建极简箱体ASCII图：中长方形代表结构中枢区域，x轴代表时间，y轴代表价格位置"""
    if not structure_segments:
        return ""

    recent_segments = structure_segments[-max_segments:]
    latest_zhongshu_pos = None
    latest_zhongshu_segment = None
    for idx, seg in enumerate(recent_segments):
        if seg.get('segment_type') == 'zhongshu':
            latest_zhongshu_pos = idx
            latest_zhongshu_segment = seg

    chart_rows = 9
    plot_width_target = 56
    gap_between_segments = 2
    gap_before_today = 4

    price_points = [today_price]
    for seg in recent_segments:
        price_points.extend([
            float(seg.get('segment_high', 0.0)),
            float(seg.get('segment_low', 0.0)),
            float(seg.get('start_close', 0.0)),
            float(seg.get('end_close', 0.0)),
        ])
        if seg.get('segment_type') == 'zhongshu':
            price_points.extend([float(seg.get('zg', 0.0)), float(seg.get('zd', 0.0))])

    min_price = min(price_points)
    max_price = max(price_points)
    if max_price <= min_price:
        max_price = min_price + 1.0
    padding = (max_price - min_price) * 0.08
    max_price += padding
    min_price -= padding

    def _price_to_row(value):
        ratio = (max_price - float(value)) / (max_price - min_price)
        row = int(round(ratio * (chart_rows - 1)))
        return max(0, min(chart_rows - 1, row))

    def _put(grid, row, col, ch):
        if 0 <= row < chart_rows and 0 <= col < chart_width:
            grid[row][col] = ch

    def _draw_line(grid, col1, row1, col2, row2):
        if col1 == col2:
            _put(grid, row1, col1, '|')
            return

        step_count = max(abs(col2 - col1), abs(row2 - row1))
        if step_count == 0:
            _put(grid, row1, col1, '.')
            return

        for step in range(step_count + 1):
            t = step / step_count
            col = int(round(col1 + (col2 - col1) * t))
            row = int(round(row1 + (row2 - row1) * t))
            if row2 < row1:
                ch = '/'
            elif row2 > row1:
                ch = '\\'
            else:
                ch = '-'
            _put(grid, row, col, ch)

    weights = [max(1, int(seg.get('kline_count', 1))) for seg in recent_segments]
    min_widths = [10 if seg.get('segment_type') == 'zhongshu' else 4 for seg in recent_segments]
    base_width = sum(min_widths) + gap_between_segments * max(0, len(recent_segments) - 1)
    extra = max(0, plot_width_target - base_width)
    total_weight = max(1, sum(weights))
    segment_widths = []
    for base, weight in zip(min_widths, weights):
        segment_widths.append(base + int(round(extra * weight / total_weight)))

    cursor = 0
    seg_layouts = []
    for seg, width in zip(recent_segments, segment_widths):
        start_col = cursor
        end_col = start_col + width - 1
        mid_col = (start_col + end_col) // 2
        seg_layouts.append({
            'segment': seg,
            'start_col': start_col,
            'end_col': end_col,
            'mid_col': mid_col,
        })
        cursor = end_col + 1 + gap_between_segments

    today_col = cursor + gap_before_today
    chart_width = today_col + 1

    grid = [[' ' for _ in range(chart_width)] for _ in range(chart_rows)]
    axis_row = ['-' for _ in range(chart_width)]
    tag_row = [' ' for _ in range(chart_width)]
    date_row = [' ' for _ in range(chart_width)]
    legend_parts = []

    segment_points = []
    zhongshu_idx = 0
    connector_idx = 0

    for idx, layout in enumerate(seg_layouts):
        seg = layout['segment']
        start_col = layout['start_col']
        end_col = layout['end_col']
        mid_col = layout['mid_col']
        axis_row[start_col] = '|'
        axis_row[end_col] = '|'

        start_row = _price_to_row(float(seg.get('start_close', today_price)))
        end_row = _price_to_row(float(seg.get('end_close', today_price)))

        if seg.get('segment_type') == 'zhongshu':
            zhongshu_idx += 1
            top_row = _price_to_row(float(seg.get('zg', seg.get('segment_high', 0.0))))
            bottom_row = _price_to_row(float(seg.get('zd', seg.get('segment_low', 0.0))))
            if top_row > bottom_row:
                top_row, bottom_row = bottom_row, top_row

            is_latest_confirmed = (idx == latest_zhongshu_pos)
            horizontal = '=' if is_latest_confirmed else '-'
            vertical = '!' if is_latest_confirmed else '|'

            for col in range(start_col, end_col + 1):
                _put(grid, top_row, col, horizontal)
                _put(grid, bottom_row, col, horizontal)
            for row in range(top_row + 1, bottom_row):
                _put(grid, row, start_col, vertical)
                _put(grid, row, end_col, vertical)

            _draw_line(grid, start_col, start_row, end_col, end_row)
            center_row = (top_row + bottom_row) // 2
            label = f"ZS{zhongshu_idx}" + ("*" if is_latest_confirmed else "")
            label_start = max(start_col + 1, mid_col - len(label) // 2)
            for offset, ch in enumerate(label):
                col = label_start + offset
                if col < end_col:
                    _put(grid, center_row, col, ch)
            tag = label
            legend_parts.append(f"{tag}={_short_date(seg['start_date'])}->{_short_date(seg['end_date'])} [{seg.get('zd', 0):.2f},{seg.get('zg', 0):.2f}]")
        else:
            connector_idx += 1
            _draw_line(grid, start_col, start_row, end_col, end_row)
            tag = f"TR{connector_idx}"
            delta = float(seg.get('end_close', 0.0)) - float(seg.get('start_close', 0.0))
            direction = 'up' if delta > 0 else 'down' if delta < 0 else 'flat'
            legend_parts.append(f"{tag}={_short_date(seg['start_date'])}->{_short_date(seg['end_date'])} transition-{direction}")

        tag_start = max(0, mid_col - len(tag) // 2)
        for offset, ch in enumerate(tag):
            if tag_start + offset < chart_width:
                tag_row[tag_start + offset] = ch

        date_label = _short_date(seg['start_date'])
        date_start = max(0, mid_col - len(date_label) // 2)
        for offset, ch in enumerate(date_label):
            if date_start + offset < chart_width:
                date_row[date_start + offset] = ch

        segment_points.append({
            'start_col': start_col,
            'start_row': start_row,
            'end_col': end_col,
            'end_row': end_row,
        })

    for idx in range(len(segment_points) - 1):
        left = segment_points[idx]
        right = segment_points[idx + 1]
        _draw_line(grid, left['end_col'] + 1, left['end_row'], right['start_col'] - 1, right['start_row'])

    axis_row[today_col] = '|'
    today_row = _price_to_row(today_price)
    if segment_points:
        last = segment_points[-1]
        _draw_line(grid, last['end_col'] + 1, last['end_row'], today_col - 1, today_row)

    _put(grid, today_row, today_col, 'T')
    comparison_state = signal.get('comparison_state', '') if signal else ''
    if comparison_state == 'breakout':
        _put(grid, max(today_row - 1, 0), today_col, '^')
    elif comparison_state == 'down':
        _put(grid, min(today_row + 1, chart_rows - 1), today_col, 'v')

    today_tag = 'TODAY'
    today_tag_start = max(0, today_col - len(today_tag) // 2)
    for offset, ch in enumerate(today_tag):
        if today_tag_start + offset < chart_width:
            tag_row[today_tag_start + offset] = ch

    today_date_label = _short_date(today_date)
    today_date_start = max(0, today_col - len(today_date_label) // 2)
    for offset, ch in enumerate(today_date_label):
        if today_date_start + offset < chart_width:
            date_row[today_date_start + offset] = ch

    latest_zg = float(latest_zhongshu_segment.get('zg', 0.0)) if latest_zhongshu_segment else None
    latest_zd = float(latest_zhongshu_segment.get('zd', 0.0)) if latest_zhongshu_segment else None
    latest_zg_row = _price_to_row(latest_zg) if latest_zg is not None else None
    latest_zd_row = _price_to_row(latest_zd) if latest_zd is not None else None

    labeled_rows = []
    for row_idx, line in enumerate(grid):
        if latest_zg_row is not None and row_idx == latest_zg_row:
            label = f"ZG {latest_zg:7.0f} | "
        elif latest_zd_row is not None and row_idx == latest_zd_row:
            label = f"ZD {latest_zd:7.0f} | "
        elif row_idx == 0:
            label = f"MAX{max_price:7.0f} | "
        elif row_idx == chart_rows - 1:
            label = f"MIN{min_price:7.0f} | "
        else:
            label = "           | "
        labeled_rows.append(label + ''.join(line).rstrip())

    labeled_rows.append("        +-" + ''.join(axis_row))
    labeled_rows.append("          " + ''.join(tag_row).rstrip())
    labeled_rows.append("          " + ''.join(date_row).rstrip())
    if latest_zhongshu_segment:
        labeled_rows.append(
            f"          最新确认结构中枢: {_short_date(latest_zhongshu_segment['start_date'])}->{_short_date(latest_zhongshu_segment['end_date'])} "
            f"ZG={latest_zg:.2f} / ZD={latest_zd:.2f}"
        )
    comparison = signal.get('comparison_result', 'unknown') if signal else 'unknown'
    labeled_rows.append(f"          TODAY={_short_date(today_date)} {today_price:.2f} => {comparison}")
    labeled_rows.append("          " + " | ".join(legend_parts))
    return "\n".join(labeled_rows)


def analyze_market_zhongshu(
    index_code='sh000001',
    recent_days=MARKET_ZHONGSHU_LOOKBACK_DAYS,
    min_zhongshu_klines=MARKET_ZHONGSHU_MIN_KLINES,
    target_date=None,
):
    """
    分析大盘中枢结构（双中枢识别）- 使用akshare同花顺数据源
    
    核心逻辑：
    1. 近120根K线可能包含多个中枢/箱体
    2. 识别出当前所处的最新中枢
    3. 判断当前价格相对中枢的突破/跌破状态
    
    Args:
        index_code: 指数代码，默认上证指数（sh000001）
        recent_days: 分析最近多少根K线（默认120天）
        min_zhongshu_klines: 最小中枢K线数
        target_date: 比较日期，默认None表示使用数据源最后一个交易日

    Returns:
        dict: {
            'zhongshu_list': 中枢列表,
            'current_zhongshu': 当前中枢,
            'today_price': 今日价格,
            'signal': 信号类型,
            'position_level': 仓位建议
        }
    """
    try:
        import urllib.request
        import json
        import re
        import pandas as pd
        from datetime import datetime, timedelta
        
        # v2.3.43: 首选同花顺问财API，备用BaoStock
        print(f"[大盘结构] 尝试使用同花顺问财API获取{index_code}指数数据...")
        df = None
        data_source = 'unknown'
        
        try:
            # 首选：同花顺问财API
            url = "https://openapi.iwencai.com/v1/query2data"
            headers = {
                "Authorization": f"Bearer {os.environ.get('IWENCAI_API_KEY', '')}",
                "Content-Type": "application/json"
            }
            payload = {
                "query": f"上证指数近{recent_days}天K线数据，包括日期、开盘价、最高价、最低价、收盘价、成交量",
                "page": "1",
                "limit": str(recent_days),
                "is_cache": "1",
                "expand_index": "true"
            }
            
            data = json.dumps(payload).encode("utf-8")
            request = urllib.request.Request(url, data=data, headers=headers, method="POST")
            response = urllib.request.urlopen(request, timeout=30)
            result = json.loads(response.read().decode("utf-8"))
            
            if result.get("status_code", 0) == 0:
                # 解析数据
                raw_data = result['datas'][0]
                
                # 提取所有日期
                dates = set()
                for key in raw_data.keys():
                    match = re.search(r'\[(\d{8})\]', key)
                    if match:
                        dates.add(match.group(1))
                
                # 按日期排序
                dates = sorted(list(dates))
                
                # 构建DataFrame
                klines = []
                for date in dates:
                    kline = {
                        'date': date,
                        'open': raw_data.get(f'开盘价[{date}]', None),
                        'high': raw_data.get(f'最高价[{date}]', None),
                        'low': raw_data.get(f'最低价[{date}]', None),
                        'close': raw_data.get(f'收盘价[{date}]', None),
                        'volume': raw_data.get(f'成交量[{date}]', None),
                        'amount': raw_data.get(f'成交额[{date}]', None)
                    }
                    if kline['high'] and kline['low'] and kline['close']:
                        klines.append(kline)
                
                df = pd.DataFrame(klines)
                data_source = '同花顺问财API'
            else:
                raise Exception(f"API错误: {result.get('status_msg', 'unknown error')}")
                
        except Exception as e:
            print(f"[大盘结构] 同花顺问财API获取失败: {e}，切换到BaoStock备用...")
            
            # 备用：BaoStock数据源
            import baostock as bs
            lg = bs.login()
            if lg.error_code == '0':
                # 转换指数代码格式：兼容 sh000001 / sh.000001
                if index_code.startswith(('sh.', 'sz.')):
                    bs_code = index_code
                elif index_code.startswith('sh'):
                    bs_code = f"sh.{index_code[2:]}"
                elif index_code.startswith('sz'):
                    bs_code = f"sz.{index_code[2:]}"
                else:
                    bs_code = index_code
                
                end_date = datetime.now().strftime('%Y-%m-%d')
                start_date = (datetime.now() - timedelta(days=recent_days + 30)).strftime('%Y-%m-%d')
                
                rs = bs.query_history_k_data_plus(bs_code,
                    'date,open,high,low,close,volume',
                    start_date=start_date, end_date=end_date,
                    frequency='d', adjustflag='3')
                
                if rs.error_code == '0':
                    data_list = []
                    while (rs.error_code == '0') & rs.next():
                        data_list.append(rs.get_row_data())
                    
                    df = pd.DataFrame(data_list, columns=rs.fields)
                    df[['open', 'high', 'low', 'close']] = df[['open', 'high', 'low', 'close']].astype(float)
                    data_source = 'BaoStock'
                
                bs.logout()
        
        if df is None or len(df) == 0:
            return {'success': False, 'error': '所有数据源均无法获取指数数据'}

        for price_col in ['open', 'high', 'low', 'close', 'volume', 'amount']:
            if price_col in df.columns:
                df[price_col] = pd.to_numeric(df[price_col], errors='coerce')
        df = df.dropna(subset=['high', 'low', 'close'])

        # 先按target_date截断，再拆成“历史K线”和“比较日”
        recent_df, hist_df, today_df = _split_zhongshu_history_and_today(
            df,
            recent_days=recent_days,
            target_date=target_date,
        )

        # 用“确认中枢 + 连接段保留”的结构分段，避免任何K线被忽略
        structure_segments, zhongshu_list = _build_zhongshu_structure(
            hist_df,
            min_zhongshu_klines=min_zhongshu_klines,
            min_overlap_bars=3,
        )
        
        # 获取今日价格（单独处理）
        today_price = float(today_df['close'])
        today_date = today_df['date']
        
        # 获取最近确认中枢（基于历史K线）
        current = zhongshu_list[-1] if zhongshu_list else None
        latest_structure_segment = structure_segments[-1] if structure_segments else None
        
        # 判断突破/跌破信号（今天 vs 历史中枢）
        signal = {}
        if current:
            zg = current['zg']  # 历史ZG（不含今天）
            zd = current['zd']  # 历史ZD（不含今天）
            dist_to_zg = (today_price - zg) / zg
            dist_to_zd = (today_price - zd) / zd
            
            signal['zg'] = zg
            signal['zd'] = zd
            signal['dist_to_zg'] = dist_to_zg
            signal['dist_to_zd'] = dist_to_zd
            signal['today_price'] = today_price
            signal['today_date'] = today_date

            # 突破判断（取消+2%门槛，只要收盘>ZG就算突破）
            if dist_to_zg > 0:
                signal['comparison_result'] = '突破'
                signal['comparison_state'] = 'breakout'
                signal['status'] = '✅ 突破中枢'
                signal['signal_type'] = '大盘突破'
                signal['position_level'] = '三档进攻档（50%）'
                signal['action'] = '积极做多'

            # 跌破判断（取消-3%门槛，只要收盘<ZD就算跌破）
            elif dist_to_zd < 0:
                # 核心原则：跌破中枢后一律空仓观望！
                # 原因：
                #   1. 跌破可能只是开始跌（半山腰接飞刀）
                #   2. 可能直接掉进下一个中枢区间（如3/20->3/23案例）
                #   3. 当天无法判断是"底部中枢"还是"下跌中继"
                # 抄底必须等确认信号：连续止跌、放量长下影线等

                signal['comparison_result'] = '下跌'
                signal['comparison_state'] = 'down'
                signal['status'] = '⚠️ 跌破中枢'
                signal['signal_type'] = '跌破支撑'
                signal['position_level'] = '一档空仓档（0%）'
                signal['action'] = '清仓观望'

                # 检查是否已经掉进下一个中枢区间（最危险的情况）
                signal['fell_into_next_zone'] = False
                if len(zhongshu_list) >= 2:
                    for prev_zs in reversed(zhongshu_list[:-1]):
                        if today_price <= prev_zs['zg'] and today_price >= prev_zs['zd']:
                            signal['status'] = '🚨 跌破并落入下中枢区间'
                            signal['signal_type'] = '暴跌至下一中枢'
                            signal['action'] = '严禁抄底，等待企稳'
                            signal['fell_into_next_zone'] = True
                            break
            else:
                signal['comparison_result'] = '震荡'
                signal['comparison_state'] = 'range'
                signal['status'] = '➖ 中枢内震荡'
                signal['signal_type'] = '按个股信号操作'
                signal['position_level'] = '二档防守档（30%）'
                signal['action'] = '精选个股'
        
        print(f"[大盘结构] 数据源: {data_source}，识别到{len(zhongshu_list)}个结构中枢，当前价格{today_price:.2f}")
        
        return {
            'zhongshu_list': zhongshu_list,
            'current_zhongshu': current,
            'structure_segments': structure_segments,
            'latest_structure_segment': latest_structure_segment,
            'today_price': today_price,
            'today_date': today_date,
            'signal': signal,
            'success': True,
            'data_source': data_source
        }
        
    except Exception as e:
        print(f"大盘结构分析失败: {e}")
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e)}


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


# ========== 蜡烛图形态判断函数 ==========
def analyze_candlestick_pattern(open_price, close_price, high_price, low_price, change_pct, first_limit_time=None):
    """
    判断蜡烛图形态
    
    Args:
        open_price: 开盘价
        close_price: 收盘价
        high_price: 最高价
        low_price: 最低价
        change_pct: 涨跌幅（百分比）
        first_limit_time: 首次封板时间（格式"HH:MM:SS"），用于涨停时间加分
    
    Returns:
        pattern_name: 形态名称
        score: 形态得分（2-10分）
        suggestion: 操作建议
    """
    # 计算振幅
    amplitude = high_price - low_price
    
    # ========== 涨停时间加分机制 ==========
    # 越早涨停说明越强，给予额外加分
    # 分档：9:35前(+3) > 10:00前(+2) > 11:30前(+1) > 14:30前(+0.5) > 15:00前(+0)
    time_bonus = 0
    time_desc = ""
    if first_limit_time and change_pct >= 9.9:
        try:
            # 解析时间
            time_parts = first_limit_time.split(':')
            if len(time_parts) >= 2:
                hour = int(time_parts[0])
                minute = int(time_parts[1])
                total_minutes = hour * 60 + minute
                
                # 9:35之前 (+3分)
                if total_minutes <= 9 * 60 + 35:
                    time_bonus = 3
                    time_desc = "(9:35前封板+3)"
                # 10:00之前 (+2分)
                elif total_minutes <= 10 * 60:
                    time_bonus = 2
                    time_desc = "(10:00前封板+2)"
                # 11:30之前 (+1分)
                elif total_minutes <= 11 * 60 + 30:
                    time_bonus = 1
                    time_desc = "(11:30前封板+1)"
                # 14:30之前 (+0.5分)
                elif total_minutes <= 14 * 60 + 30:
                    time_bonus = 0.5
                    time_desc = "(14:30前封板+0.5)"
                # 15:00之前 (无加分)
                else:
                    time_bonus = 0
                    time_desc = ""
        except:
            pass
    
    # ========== 技术形态分级评分（0基础 + 加分制） ==========
    # 强度排序：一字板(10) > T字板(8) >> 光头大阳柱(4) > 放量大阳线(2) >> 温和(0)
    # >> 表示跨等级巨大台阶（≥4分差距），> 表示同档递减
    # 温和及以下 = 0分（不加分）

    # S级：一字板加速（10分 + 时间加分）
    # 严格条件：开盘=收盘=最高=最低（全天一条线，涨停开盘无任何波动）
    if change_pct >= 9.9 and open_price == close_price == high_price == low_price:
        final_score = 10 + time_bonus
        return f"一字板加速{time_desc}", final_score, "最强加速形态，次日可能继续加速或分歧"
    
    # A级：T字板分歧转一致（8分 + 时间加分）
    # 严格定义：涨停价开盘（open==close==high==涨停价），且最低价<收盘价（有下影线）
    if change_pct >= 9.9 and open_price == close_price == high_price and low_price < close_price:
        final_score = 8 + time_bonus
        return f"T字板分歧转一致{time_desc}", final_score, "涨停价开盘，盘中炸板后回封，分歧转一致"
    
    # C级：光头大阳柱涨停（4分 + 时间加分）
    # 低位拉板封涨停：open<close（非涨停开盘），high==close（无上影线），涨停
    if change_pct >= 9.9 and high_price == close_price and open_price < close_price:
        final_score = 4 + time_bonus
        return f"光头大阳柱涨停{time_desc}", final_score, "低位拉板封涨停，强势吸筹，分歧较小"
    
    # 计算振幅百分比（用于判断）
    amplitude_pct = (amplitude / open_price) * 100 if open_price > 0 else 0
    
    # 计算上影线长度（最高价-收盘价）/ 收盘价 * 100
    upper_shadow_pct = ((high_price - max(open_price, close_price)) / close_price) * 100 if close_price > 0 else 0
    
    # D级：放量大阳线（2分）- 涨幅>5%且振幅>5%
    if change_pct > 5 and amplitude_pct > 5:
        base_score = 2  # 基础分2分
        # 判断是否有长上影线（上影线是减分项，说明主力试盘或遇压）
        if upper_shadow_pct > 3:
            # 长上影线减2分，最低0分
            score = max(base_score - 2, 0)
            return f"放量大阳线+长上影线({upper_shadow_pct:.1f}%)", score, "放量上涨但长上影线，主力试盘或遇强压，信号减弱"
        elif upper_shadow_pct > 1:
            # 上影线减1分
            score = max(base_score - 1, 0)
            return f"放量大阳线+上影线({upper_shadow_pct:.1f}%)", score, "放量上涨但有上影线，有一定抛压，信号打折"
        else:
            return "放量大阳线", base_score, "强势上涨形态，次日可能延续"
    
    # 温和放量+多头排列（2分）- 涨幅>0%且振幅2-5%
    if change_pct > 0 and 2 <= amplitude_pct <= 5:
        return "温和放量+多头排列", 2, "温和上涨形态"
    
    # 震荡整理（0分）- 涨跌幅-2%~2%
    if -2 <= change_pct <= 2:
        return "震荡整理", 0, "震荡整理，观望为主"
    
    # 缩量调整（0分）- 振幅<2%
    if amplitude_pct < 2:
        return "缩量调整", 0, "量能萎缩，观望情绪浓厚"
    
    # 下跌趋势（0分）- 跌幅>2%
    if change_pct < -2:
        return "下跌趋势", 0, "下跌趋势，回避为主"
    
    # 高位大绿棒放量（0分）- 跌幅>3%且振幅大
    if change_pct < -3 and amplitude > 5:
        return "高位大绿棒放量", 0, "出货形态，风险较大，坚决回避"
    
    # 默认：普通形态（0分）
    return "普通形态", 0, "无明显特征"


def get_turnover_rank_from_iwencai(limit=50, target_date=None):
    """
    获取成交额排名 - 使用同花顺问财API
    
    Args:
        limit: 返回数量，默认50
        target_date: 目标日期（YYYY-MM-DD格式），默认None表示今天
    
    Returns:
        成交额排名列表，格式与腾讯财经API保持一致
    """
    try:
        import urllib.request
        import json
        from datetime import datetime
        
        # 确定查询日期
        if target_date:
            if isinstance(target_date, str):
                query_date = datetime.strptime(target_date, '%Y-%m-%d')
            else:
                query_date = target_date
            date_str = query_date.strftime('%Y-%m-%d')
            query = f"{date_str}成交额前{limit}的股票，包括股票代码、股票简称、成交额、涨跌幅、所属行业"
            date_compact = query_date.strftime('%Y%m%d')
        else:
            query = f"今日成交额前{limit}的股票，包括股票代码、股票简称、成交额、涨跌幅、所属行业"
            date_compact = datetime.now().strftime('%Y%m%d')
        
        # API配置
        import os
        api_key = os.environ.get('IWENCAI_API_KEY')
        if not api_key:
            print("⚠️ 未设置IWENCAI_API_KEY，返回空数据")
            return []
        
        url = "https://openapi.iwencai.com/v1/query2data"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "query": query,
            "page": "1",
            "limit": str(limit),
            "is_cache": "1"
        }
        
        # 发送请求
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=data, headers=headers, method="POST")
        response = urllib.request.urlopen(request, timeout=30)
        result = json.loads(response.read().decode("utf-8"))
        
        # 解析数据
        turnover_rank = []
        if result.get('datas'):
            for item in result['datas']:
                # 处理行业信息
                industry_list = item.get('所属同花顺行业', [])
                sector = industry_list[0] if industry_list else '未知'
                
                turnover_rank.append({
                    'code': item.get('股票代码', '').replace('.SZ', '').replace('.SH', '').replace('.BJ', ''),
                    'name': item.get('股票简称', ''),
                    'turnover': item.get(f'成交额[{date_compact}]', 0) / 1e8,  # 转换为亿
                    'change_pct': item.get(f'涨跌幅[{date_compact}]', 0),
                    'sector': sector
                })
        
        return turnover_rank
    
    except Exception as e:
        print(f"⚠️ iwencai成交额排名获取失败: {e}")
        import traceback
        traceback.print_exc()
        return []


def get_total_turnover_from_iwencai(target_date=None):
    """
    获取两市成交额 - 使用同花顺问财API
    
    Args:
        target_date: 目标日期（YYYY-MM-DD格式），默认None表示今天
    
    Returns:
        两市成交额（亿元）
    """
    try:
        import urllib.request
        import json
        from datetime import datetime
        
        # 确定查询日期
        if target_date:
            if isinstance(target_date, str):
                query_date = datetime.strptime(target_date, '%Y-%m-%d')
            else:
                query_date = target_date
            date_str = query_date.strftime('%Y-%m-%d')
            query = f"{date_str}两市成交额"
            date_compact = query_date.strftime('%Y%m%d')
        else:
            query = "今日两市成交额"
            date_compact = datetime.now().strftime('%Y%m%d')
        
        # API配置
        import os
        api_key = os.environ.get('IWENCAI_API_KEY')
        if not api_key:
            print("⚠️ 未设置IWENCAI_API_KEY，返回0")
            return 0.0
        
        url = "https://openapi.iwencai.com/v1/query2data"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "query": query,
            "page": "1",
            "limit": "10",
            "is_cache": "1"
        }
        
        # 发送请求
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=data, headers=headers, method="POST")
        response = urllib.request.urlopen(request, timeout=30)
        result = json.loads(response.read().decode("utf-8"))
        
        # 解析数据
        total_turnover = 0.0
        if result.get('datas'):
            for item in result['datas']:
                turnover = item.get(f'成交额[{date_compact}]', 0)
                total_turnover += turnover / 1e8  # 转换为亿
        
        return total_turnover
    
    except Exception as e:
        print(f"⚠️ iwencai两市成交额获取失败: {e}")
        import traceback
        traceback.print_exc()
        return 0.0


def get_major_indices_from_iwencai(target_date=None):
    """
    获取主要指数 - 使用同花顺问财API
    
    Args:
        target_date: 目标日期（YYYY-MM-DD格式），默认None表示今天
    
    Returns:
        主要指数列表，格式与finshare API保持一致
    """
    def _build_major_index_bar_fallback():
        from datetime import datetime, timedelta

        try:
            if target_date:
                if isinstance(target_date, str):
                    query_date = datetime.strptime(target_date, '%Y-%m-%d')
                else:
                    query_date = target_date
            else:
                query_date = datetime.now()

            end_date = query_date.strftime('%Y-%m-%d')
            start_date = (query_date - timedelta(days=15)).strftime('%Y-%m-%d')
            index_map = {
                '上证指数': '000001',
                '深证成指': '399001',
                '创业板指': '399006',
            }
            indices = {}

            for name, code in index_map.items():
                bars = fetch_daily_price_bars(code, start_date, end_date, is_index=True)
                valid_bars = [
                    bar for bar in (bars or [])
                    if _normalize_kline_date_str(bar.get('date')) <= end_date
                ]
                if not valid_bars:
                    continue

                latest_bar = valid_bars[-1]
                prev_close = 0.0
                if len(valid_bars) >= 2:
                    prev_close = _safe_float(valid_bars[-2].get('close'))

                close_price = _safe_float(latest_bar.get('close'))
                open_price = _safe_float(latest_bar.get('open'))
                if prev_close > 0:
                    change_pct = (close_price - prev_close) / prev_close * 100
                elif open_price > 0:
                    change_pct = (close_price - open_price) / open_price * 100
                else:
                    change_pct = 0.0

                indices[name] = {
                    'name': name,
                    'code': code,
                    'price': close_price,
                    'open': open_price,
                    'close': close_price,
                    'high': _safe_float(latest_bar.get('high')),
                    'low': _safe_float(latest_bar.get('low')),
                    'change_pct': change_pct,
                    'turnover': 0.0,
                    '涨跌幅': change_pct,
                    'data_source': 'price_bar_fallback',
                    'trade_date': _normalize_kline_date_str(latest_bar.get('date')),
                }

            if indices:
                print(f"ℹ️ 主要指数已切换到历史K线回补，共获取{len(indices)}个指数")
            return indices
        except Exception as fallback_error:
            print(f"⚠️ 主要指数历史K线回补失败: {fallback_error}")
            return {}

    try:
        import urllib.request
        import json
        from datetime import datetime
        
        # 确定查询日期
        if target_date:
            if isinstance(target_date, str):
                query_date = datetime.strptime(target_date, '%Y-%m-%d')
            else:
                query_date = target_date
            date_str = query_date.strftime('%Y-%m-%d')
            query = f"{date_str}上证指数、深证成指、创业板指的开盘价、收盘价、最高价、最低价、涨跌幅、成交额"
            date_compact = query_date.strftime('%Y%m%d')
        else:
            query = "今日上证指数、深证成指、创业板指的开盘价、收盘价、最高价、最低价、涨跌幅、成交额"
            date_compact = datetime.now().strftime('%Y%m%d')
        
        # API配置
        import os
        api_key = os.environ.get('IWENCAI_API_KEY')
        if not api_key:
            print("⚠️ 未设置IWENCAI_API_KEY，切换到历史K线回补")
            return _build_major_index_bar_fallback()
        
        url = "https://openapi.iwencai.com/v1/query2data"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "query": query,
            "page": "1",
            "limit": "10",
            "is_cache": "1"
        }
        
        # 发送请求
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=data, headers=headers, method="POST")
        response = urllib.request.urlopen(request, timeout=30)
        result = json.loads(response.read().decode("utf-8"))
        
        # 解析数据 - 返回字典格式（与finshare API保持一致）
        indices = {}
        if result.get('datas'):
            for item in result['datas']:
                name = item.get('指数简称', '')
                close_price = item.get(f'收盘价[{date_compact}]', 0)
                indices[name] = {
                    'name': name,
                    'code': item.get('指数代码', '').replace('.SH', '').replace('.SZ', ''),
                    'price': close_price,  # 添加price字段，保持兼容性
                    'open': item.get(f'开盘价[{date_compact}]', 0),
                    'close': close_price,
                    'high': item.get(f'最高价[{date_compact}]', 0),
                    'low': item.get(f'最低价[{date_compact}]', 0),
                    'change_pct': item.get(f'涨跌幅[{date_compact}]', 0),
                    'turnover': item.get(f'成交额[{date_compact}]', 0) / 1e8,  # 转换为亿
                    '涨跌幅': item.get(f'涨跌幅[{date_compact}]', 0)  # 添加中文别名
                }

        if len(indices) < 3:
            fallback_indices = _build_major_index_bar_fallback()
            for name, payload in fallback_indices.items():
                indices.setdefault(name, payload)

        return indices
    
    except Exception as e:
        print(f"⚠️ iwencai主要指数获取失败: {e}")
        import traceback
        traceback.print_exc()
        return _build_major_index_bar_fallback()


def get_wind_a_from_iwencai(target_date=None):
    """
    获取中证全指 - 使用同花顺问财API
    
    Args:
        target_date: 目标日期（YYYY-MM-DD格式），默认None表示今天
    
    Returns:
        中证全指数据，格式与finshare API保持一致
    """
    try:
        import urllib.request
        import json
        from datetime import datetime
        
        # 确定查询日期
        if target_date:
            if isinstance(target_date, str):
                query_date = datetime.strptime(target_date, '%Y-%m-%d')
            else:
                query_date = target_date
            date_str = query_date.strftime('%Y-%m-%d')
            query = f"{date_str}中证全指的点位、涨跌幅"
            date_compact = query_date.strftime('%Y%m%d')
        else:
            query = "今日中证全指的点位、涨跌幅"
            date_compact = datetime.now().strftime('%Y%m%d')
        
        # API配置
        import os
        api_key = os.environ.get('IWENCAI_API_KEY')
        if not api_key:
            print("⚠️ 未设置IWENCAI_API_KEY，返回空数据")
            return {'price': 0, 'change_pct': 0}
        
        url = "https://openapi.iwencai.com/v1/query2data"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "query": query,
            "page": "1",
            "limit": "10",
            "is_cache": "1"
        }
        
        # 发送请求
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=data, headers=headers, method="POST")
        response = urllib.request.urlopen(request, timeout=30)
        result = json.loads(response.read().decode("utf-8"))
        
        # 解析数据
        if result.get('datas') and len(result['datas']) > 0:
            item = result['datas'][0]
            # iwencai返回的字段名是"收盘价"而不是"点位"
            return {
                'price': item.get(f'收盘价[{date_compact}]', 0),
                'change_pct': item.get(f'涨跌幅[{date_compact}]', 0)
            }
        
        return {'price': 0, 'change_pct': 0}
    
    except Exception as e:
        print(f"⚠️ iwencai中证全指获取失败: {e}")
        import traceback
        traceback.print_exc()
        return {'price': 0, 'change_pct': 0}


def get_sector_quadrant_data(period=20, strength_period=3):
    """
    获取板块四象限数据（击球区分析）
    
    Args:
        period: 高低位置周期（默认20日）
        strength_period: 强弱动量周期（默认3日）
    
    Returns:
        dict: 包含四象限数据和击球区质量分析
    """
    import requests
    
    try:
        url = f"https://stock.quicktiny.cn/api/sector-analysis/quadrant?source=dongcai_concept&period={period}&strengthPeriod={strength_period}"
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            print(f"   ⚠️ 板块四象限API返回状态码: {response.status_code}")
            return None
        
        data = response.json()
        
        if not data.get('quadrants'):
            print(f"   ⚠️ 板块四象限数据格式异常")
            return None
        
        quadrants = data['quadrants']
        
        # 分析高强区间（击球区）质量
        high_strong = quadrants.get('highStrong', [])
        
        # 计算质量得分
        def calculate_quality_score(sector):
            score = 0
            
            # 位置得分（0-30分）
            if sector['positionInRange'] >= 90:
                score += 30
            elif sector['positionInRange'] >= 80:
                score += 25
            elif sector['positionInRange'] >= 70:
                score += 15
            else:
                score += 5
            
            # 动量得分（0-40分）
            if sector['recentChange'] >= 8:
                score += 40
            elif sector['recentChange'] >= 5:
                score += 30
            elif sector['recentChange'] >= 3:
                score += 20
            else:
                score += 10
            
            # 量比得分（0-30分）
            if sector['volumeRatio'] >= 2.0:
                score += 30
            elif sector['volumeRatio'] >= 1.5:
                score += 20
            elif sector['volumeRatio'] >= 1.0:
                score += 10
            else:
                score += 0
            
            return score
        
        # 为每个板块计算质量得分
        for sector in high_strong:
            sector['quality_score'] = calculate_quality_score(sector)
        
        # 分层统计
        tier1 = [s for s in high_strong if s['quality_score'] >= 80]  # 最佳击球区
        tier2 = [s for s in high_strong if 60 <= s['quality_score'] < 80]  # 优质击球区
        tier3 = [s for s in high_strong if 40 <= s['quality_score'] < 60]  # 普通击球区
        tier4 = [s for s in high_strong if s['quality_score'] < 40]  # 边缘击球区
        
        return {
            'quadrants': quadrants,
            'high_strong_analysis': {
                'total': len(high_strong),
                'tier1_best': sorted(tier1, key=lambda x: x['quality_score'], reverse=True),
                'tier2_good': sorted(tier2, key=lambda x: x['quality_score'], reverse=True),
                'tier3_normal': sorted(tier3, key=lambda x: x['quality_score'], reverse=True),
                'tier4_edge': sorted(tier4, key=lambda x: x['quality_score'], reverse=True),
                'tier1_count': len(tier1),
                'tier2_count': len(tier2),
                'tier3_count': len(tier3),
                'tier4_count': len(tier4)
            }
        }
        
    except Exception as e:
        print(f"   ⚠️ 板块四象限数据获取失败: {e}")
        return None


def get_daily_data(target_date=None):
    """
    获取指定日期的A股市场数据 - 严格按照SKILL.md声明
    
    Args:
        target_date: 目标日期字符串，格式 "YYYY-MM-DD"
                    如果为None，则获取前一天的数据
    """
    # 初始化计时器
    timer = StepTimer()
    timer.start()
    
    print("🚀 A股日报数据获取入口 - SKILL.md对齐版", flush=True)
    print("=" * 60, flush=True)
    
    # ========== 初始化状态跟踪字典 ==========
    data_status = {}  # 数据获取状态
    step_status = {}  # 执行步骤状态
    
    # 确定目标日期
    if target_date is None:
        import datetime as _dt
        today = _dt.datetime.now()
        yesterday = today - _dt.timedelta(days=1)
        target_date = yesterday.strftime("%Y-%m-%d")
    
    print("📅 目标日期: {}".format(target_date), flush=True)
    print("=" * 60, flush=True)
    
    # 创建数据收集器
    collector = AShareDataCollector()
    tencent = TencentFinanceData()
    
    print("🔍 开始获取市场数据...", flush=True)
    
    results = {}
    
    try:
        # ========== 1. 两市成交额（iwencai API）==========
        step_status['两市成交额获取'] = False
        print("  1️⃣ 获取两市成交额（iwencai API）...", flush=True)
        # 使用iwencai API获取两市成交额（支持历史日期）
        total_turnover_float = get_total_turnover_from_iwencai(target_date=target_date)
        results['total_turnover'] = total_turnover_float
        results['turnover_data'] = {
            'total_turnover_yi': total_turnover_float,
            'date': target_date
        }
        if total_turnover_float > 0:
            data_status['两市成交额'] = True
            step_status['两市成交额获取'] = True
            elapsed, cum = timer.record("两市成交额获取", 1)
            print("   ✅ 成交额获取完成: {:.2f}亿元 [⏱ {:.2f}s]".format(total_turnover_float, elapsed))
        else:
            data_status['两市成交额'] = False
            elapsed, cum = timer.record("两市成交额获取(失败)", 1)
            print("   ❌ 成交额获取失败 [⏱ {:.2f}s]".format(elapsed))
        
        # ========== 2. 主要指数（iwencai API）==========
        step_status['主要指数获取'] = False
        print("  2️⃣ 获取三大指数（iwencai API）...", flush=True)
        # 使用iwencai API获取主要指数（支持历史日期）
        indices = get_major_indices_from_iwencai(target_date=target_date)
        results['indices'] = indices
        if indices and len(indices) > 0:
            data_status['主要指数'] = True
            step_status['主要指数获取'] = True
            elapsed, cum = timer.record("主要指数获取", 2)
            print(f"   ✅ 获取到 {len(indices)} 个指数数据 [⏱ {elapsed:.2f}s]")
        else:
            data_status['主要指数'] = False
            elapsed, cum = timer.record("主要指数获取(失败)", 2)
            print(f"   ❌ 主要指数获取失败 [⏱ {elapsed:.2f}s]")
        
        # ========== 3. 中证全指（iwencai API）==========
        step_status['中证全指获取'] = False
        print("  3️⃣ 获取中证全指（iwencai API）...", flush=True)
        # 使用iwencai API获取中证全指（支持历史日期）
        wind_a_alt = get_wind_a_from_iwencai(target_date=target_date)
        results['wind_a_alternative'] = wind_a_alt
        wind_a_price = wind_a_alt.get('price', wind_a_alt.get('点位', 0))
        wind_a_change = wind_a_alt.get('change_pct', wind_a_alt.get('涨跌幅', 0))
        if wind_a_price > 0:
            data_status['中证全指'] = True
            step_status['中证全指获取'] = True
            elapsed, cum = timer.record("中证全指获取", 3)
            print(f"   ✅ 中证全指: {wind_a_price:.2f}点 ({wind_a_change:+.2f}%) [⏱ {elapsed:.2f}s]")
        else:
            data_status['中证全指'] = False
            elapsed, cum = timer.record("中证全指获取(失败)", 3)
            print(f"   ❌ 中证全指获取失败 [⏱ {elapsed:.2f}s]")
        
        # ========== 4. 涨停跌停数据（akshare涨停跌停池模块）==========
        step_status['涨停跌停数据获取'] = False
        print(f"  4️⃣ 获取涨停跌停数据（akshare涨停跌停池模块）...")
        try:
            date_str = target_date.replace("-", "")
            
            # 使用 limit_up_down_pool 模块获取涨停池
            limit_up_df, limit_up_codes = get_limit_up_pool(date_str)
            if not limit_up_df.empty:
                results['zt_pool'] = limit_up_df.to_dict('records')
                results['limit_up_codes'] = limit_up_codes
                data_status['涨停池'] = True
                print(f"   ✅ 涨停池: {len(limit_up_df)} 只")
            else:
                results['zt_pool'] = []
                results['limit_up_codes'] = set()
                data_status['涨停池'] = False
                print("   ❌ 涨停池为空", flush=True)
            
            # 使用 limit_up_down_pool 模块获取跌停池
            limit_down_df, limit_down_codes = get_limit_down_pool(date_str)
            if not limit_down_df.empty:
                results['dt_pool'] = limit_down_df.to_dict('records')
                results['limit_down_codes'] = limit_down_codes
                data_status['跌停池'] = True
                print(f"   ✅ 跌停池: {len(limit_down_df)} 只")
            else:
                results['dt_pool'] = []
                results['limit_down_codes'] = set()
                data_status['跌停池'] = False
                print("   ❌ 跌停池为空", flush=True)
            
            # 统计涨停股板块分布
            if not limit_up_df.empty:
                zt_pool_by_sector = {}
                for _, row in limit_up_df.iterrows():
                    sector = row.get('所属行业', '未知')
                    if sector not in zt_pool_by_sector:
                        zt_pool_by_sector[sector] = []
                    zt_pool_by_sector[sector].append({
                        'code': row.get('代码', ''),
                        'name': row.get('名称', ''),
                        'zt_type': row.get('涨停统计', '')
                    })
                results['zt_pool_by_sector'] = zt_pool_by_sector
                data_status['涨停股板块分布'] = True
                print(f"   ✅ 涨停股板块分布: {len(zt_pool_by_sector)} 个板块")
            
            # 统计跌停股板块分布
            if not limit_down_df.empty:
                dt_pool_by_sector = {}
                for _, row in limit_down_df.iterrows():
                    sector = row.get('所属行业', '未知')
                    if sector not in dt_pool_by_sector:
                        dt_pool_by_sector[sector] = []
                    dt_pool_by_sector[sector].append({
                        'code': row.get('代码', ''),
                        'name': row.get('名称', '')
                    })
                results['dt_pool_by_sector'] = dt_pool_by_sector
                data_status['跌停股板块分布'] = True
                print(f"   ✅ 跌停股板块分布: {len(dt_pool_by_sector)} 个板块")
            
            # 获取大盘涨跌统计数据（关键：用于市场情绪判断）
            try:
                import akshare as ak
                import pandas as pd  # 需要导入pandas用于pd.isna()
                
                market_activity_df = ak.stock_market_activity_legu()
                print(f"   📊 大盘涨跌统计原始数据: {len(market_activity_df)} 行")
                
                if not market_activity_df.empty:
                    # 解析数据
                    market_stats = {}
                    for idx, row in market_activity_df.iterrows():
                        # 获取item和value
                        item = row.iloc[0] if len(row) > 0 else ''  # 第一列是item
                        value = row.iloc[1] if len(row) > 1 else 0  # 第二列是value
                        
                        # 类型转换（value可能是float或str）
                        try:
                            if isinstance(value, str):
                                # 处理百分比字符串
                                if '%' in value:
                                    value = float(value.replace('%', ''))
                                else:
                                    value = float(value)
                            numeric_value = int(value) if not pd.isna(value) else 0
                        except Exception as conv_err:
                            numeric_value = 0
                        
                        if item == '上涨':
                            market_stats['up_count'] = numeric_value
                        elif item == '下跌':
                            market_stats['down_count'] = numeric_value
                        elif item == '涨停':
                            market_stats['zt_count'] = numeric_value
                        elif item == '跌停':
                            market_stats['dt_count'] = numeric_value
                    
                    results['market_stats'] = market_stats
                    data_status['大盘涨跌统计'] = True
                    print(f"   ✅ 大盘涨跌统计: 上涨{market_stats.get('up_count', 0)}家 vs 下跌{market_stats.get('down_count', 0)}家")
                else:
                    print(f"   ⚠️ 大盘涨跌统计数据为空")
                    results['market_stats'] = {}
                    data_status['大盘涨跌统计'] = False
            except Exception as e:
                print(f"   ⚠️ 大盘涨跌统计获取失败: {e}")
                import traceback
                traceback.print_exc()
                results['market_stats'] = {}
                data_status['大盘涨跌统计'] = False
            
            step_status['涨停跌停数据获取'] = True
            elapsed, cum = timer.record("涨停跌停数据获取", 4)
            print(f"   ✅ 涨停跌停数据完成 [⏱ {elapsed:.2f}s]")
        except Exception as e:
            elapsed, cum = timer.record("涨停跌停数据获取(失败)", 4)
            print(f"   ❌ 涨停跌停数据失败: {e} [⏱ {elapsed:.2f}s]")
            results['zt_pool'] = []
            results['dt_pool'] = []
            results['limit_up_codes'] = set()
            results['limit_down_codes'] = set()
            data_status['涨停池'] = False
            data_status['跌停池'] = False
        
        # ========== 5. 热度前三十个股（同花顺首选）==========
        step_status['热度前三十个股获取'] = False
        print(f"  5️⃣ 获取{target_date}热度前三十个股（同花顺首选）...")
        try:
            # 首选：同花顺个股热榜
            hot_stocks = fetch_ths_hot_stock(num=30)
            if hot_stocks:
                # 构建全局 code_to_sector 映射（行业维度，用于主线方向匹配）
                # 数据源：涨停池 + 连板梯队 + 龙虎榜 → 覆盖涨停股、连板股、活跃股
                code_to_sector = {}
                if results.get('zt_pool'):
                    for stock in results['zt_pool']:
                        code = stock.get('代码', '')
                        sector = stock.get('所属行业', '')
                        if code and sector:
                            code_to_sector[code] = sector
                # 注：lianban_data的数据已经包含在zt_pool中，无需重复遍历
                if results.get('lhb_net_buy_top10'):
                    for stock in results['lhb_net_buy_top10']:
                        code = stock.get('code', '').replace('.SZ', '').replace('.SS', '')
                        sector = stock.get('sector', '')
                        if code and sector and sector != '未知':
                            code_to_sector[code] = sector
                if results.get('lhb_net_sell_top10'):
                    for stock in results['lhb_net_sell_top10']:
                        code = stock.get('code', '').replace('.SZ', '').replace('.SS', '')
                        sector = stock.get('sector', '')
                        if code and sector and sector != '未知':
                            code_to_sector[code] = sector
                results['code_to_sector'] = code_to_sector  # 全局共享
                
                # 为热榜股票补充板块信息
                for stock in hot_stocks:
                    if stock.get('code') in code_to_sector:
                        stock['sector'] = code_to_sector[stock.get('code')]
                
                results['hot_rank_top30'] = hot_stocks
                data_status['热度前三十个股'] = True
                step_status['热度前三十个股获取'] = True
                elapsed, cum = timer.record("热度前三十个股获取", 5)
                print(f"   ✅ 同花顺热榜成功: {len(hot_stocks)} 只 [⏱ {elapsed:.2f}s]")
                for i, stock in enumerate(hot_stocks[:3], 1):
                    # rate需要÷10000转换为万单位
                    rate_val = int(stock.get('rate', 0)) if isinstance(stock.get('rate'), str) else stock.get('rate', 0)
                    rate_w = rate_val / 10000
                    concepts = "、".join(stock.get('concepts', [])[:2]) if stock.get('concepts') else '-'
                    # popularity_tag已经包含完整的标签信息（如"5天3板"、"首板涨停"、"持续上榜"等）
                    tag_str = stock.get('popularity_tag', '-')
                    sector = stock.get('sector', concepts)  # 优先用sector，否则用概念标签
                    print(f"      {i}. {stock.get('name')} ({stock.get('code')}): 热度{rate_w:.1f}w | 行业:{sector:<16} | 【{tag_str}】")
            else:
                # 备用：腾讯财经热股排行
                print("   ⚠️ 同花顺返回空，尝试腾讯备用...", flush=True)
                hot_stocks = tencent.get_hot_stocks(num=30)
                if hot_stocks:
                    results['hot_rank_top30'] = hot_stocks
                    data_status['热度前三十个股'] = True
                    step_status['热度前三十个股获取'] = True
                    print(f"   ✅ 腾讯热榜成功: {len(hot_stocks)} 只")
                else:
                    results['hot_rank_top30'] = []
                    data_status['热度前三十个股'] = False
                    print("   ❌ 所有热榜数据源失败", flush=True)
        except Exception as e:
            print(f"   ❌ 热榜获取失败: {e}")
            results['hot_rank_top30'] = []
            data_status['热度前三十个股'] = False
        
        # ========== 5.5. 整合热榜数据（新数据源）==========
        step_status['整合热榜获取'] = False
        print(f"  5️⃣.5️⃣ 获取整合热榜数据（新数据源）...")
        try:
            integrated_hot_list, tag_distribution, status_distribution, high_lianban_stocks = get_integrated_hot_list(limit=100)
            if integrated_hot_list:
                results['integrated_hot_list'] = integrated_hot_list
                results['tag_distribution'] = tag_distribution
                results['status_distribution'] = status_distribution
                results['high_lianban_stocks'] = high_lianban_stocks
                data_status['整合热榜'] = True
                step_status['整合热榜获取'] = True
                print(f"   ✅ 整合热榜成功: {len(integrated_hot_list)} 只")
                print(f"   ✅ 板块标签分布: {len(tag_distribution)} 个板块，{len(status_distribution)} 个状态标签")
                if high_lianban_stocks:
                    print(f"   ✅ 高位连板股: {len(high_lianban_stocks)} 只（非ST股，10天以上）")
                for i, stock in enumerate(integrated_hot_list[:3], 1):
                    tags_str = "、".join(stock['sector_tags'][:3])
                    print(f"      {i}. {stock['name']} ({stock['code']}): {stock['change_pct']:+.2f}% | {tags_str}")
            else:
                results['integrated_hot_list'] = []
                results['tag_distribution'] = {}
                results['status_distribution'] = {}
                data_status['整合热榜'] = False
                print("   ⚠️ 整合热榜返回空", flush=True)
        except Exception as e:
            print(f"   ⚠️ 整合热榜失败: {e}")
            results['integrated_hot_list'] = []
            results['tag_distribution'] = {}
            results['status_distribution'] = {}
            data_status['整合热榜'] = False
        
        # ========== 6. 板块热榜（同花顺）==========
        step_status['板块热榜获取'] = False
        print(f"  6️⃣ 获取板块热榜（同花顺）...")
        try:
            hot_plates = fetch_hot_plate()
            if hot_plates:
                results['hot_plates'] = hot_plates
                data_status['板块热榜'] = True
                step_status['板块热榜获取'] = True
                elapsed, cum = timer.record("板块热榜获取", 6)
                print(f"   ✅ 板块热榜成功: {len(hot_plates)} 条 [⏱ {elapsed:.2f}s]")
                for i, plate in enumerate(hot_plates[:3], 1):
                    # rate已是万为单位，tag包含涨停家数，hot_tag包含连续上榜信息
                    rate_w = float(plate.get('rate', 0)) if isinstance(plate.get('rate'), str) else plate.get('rate', 0)
                    tag = plate.get('tag', '-')
                    hot_tag = plate.get('hot_tag', '-')
                    print(f"      {i}. {plate.get('name')} 热度{rate_w:.0f}w {tag} {hot_tag}")
            else:
                results['hot_plates'] = []
                data_status['板块热榜'] = False
                print("   ❌ 板块热榜返回空", flush=True)
        except Exception as e:
            print(f"   ❌ 板块热榜失败: {e}")
            results['hot_plates'] = []
            data_status['板块热榜'] = False
        
        # ========== 7. 行业资金流向（腾讯财经/替代方案）==========
        step_status['行业资金流向获取'] = False
        print(f"  7️⃣ 获取行业资金流向...")
        try:
            from datetime import datetime, timedelta
            today = datetime.now().strftime('%Y-%m-%d')
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            
            # v2.3.40修复：允许获取前一个交易日的数据（凌晨生成报告时，昨天的数据应该可以获取）
            if target_date == today or target_date == yesterday:
                # 当日数据：使用腾讯API（实时）
                print(f"   📅 获取当日({target_date})资金流向...")
                sector_fund_in = tencent.get_sector_fund_flow(flow_type='in', limit=50)
                sector_fund_out = tencent.get_sector_fund_flow(flow_type='out', limit=50)
                source_name = "腾讯财经"
                
                # 合并数据
                sector_fund = {
                    'inflow': sector_fund_in,
                    'outflow': sector_fund_out
                }
                results['sector_fund_flow'] = sector_fund
                
                if sector_fund_in or sector_fund_out:
                    data_status['行业资金流向'] = True
                    step_status['行业资金流向获取'] = True
                    elapsed, cum = timer.record("行业资金流向获取", 7)
                    print(f"   ✅ {source_name}成功: 净流入{len(sector_fund_in)}条, 净流出{len(sector_fund_out)}条 [⏱ {elapsed:.2f}s]")
                    # 显示净流入前3
                    for i, s in enumerate(sector_fund_in[:3], 1):
                        print(f"      净流入{i}. {s.get('name')} +{s.get('zljlr', 0):.2f}亿")
                    # 显示净流出前3
                    for i, s in enumerate(sector_fund_out[:3], 1):
                        print(f"      净流出{i}. {s.get('name')} {s.get('zljlr', 0):.2f}亿")
                else:
                    results['sector_fund_flow'] = {'inflow': [], 'outflow': []}
                    data_status['行业资金流向'] = False
                    print("   ❌ 行业资金流向返回空", flush=True)
            else:
                # 历史日期：板块资金流向API不支持历史数据
                # 标记为历史数据不支持，报告生成时会显示提示
                print(f"   ⚠️ 历史({target_date})板块资金流向暂不支持，将在报告中提示")
                results['sector_fund_flow'] = {
                    'inflow': [], 
                    'outflow': [],
                    'is_historical': True,  # 标记为历史日期
                    'target_date': target_date
                }
                data_status['行业资金流向'] = True  # 标记为已处理
                step_status['行业资金流向获取'] = True
                elapsed, cum = timer.record("行业资金流向获取", 7)
        except Exception as e:
            print(f"   ❌ 行业资金流向失败: {e}")
            import traceback
            traceback.print_exc()
            results['sector_fund_flow'] = {'inflow': [], 'outflow': []}
            data_status['行业资金流向'] = False
        
        # ========== 8. 板块涨跌幅排行（同花顺问财API）==========
        step_status['板块涨跌幅排行获取'] = False
        print(f"  8️⃣ 获取板块涨跌幅排行（同花顺问财API）...")
        try:
            # 涨幅前10
            sector_up = get_sector_change_from_iwencai(rank_type='up', limit=10)
            # 跌幅前10
            sector_down = get_sector_change_from_iwencai(rank_type='down', limit=10)
            
            if sector_up:
                results['sector_change_up'] = sector_up
                data_status['板块涨幅排行'] = True
                print(f"   ✅ 涨幅前10板块: {len(sector_up)} 条")
            else:
                results['sector_change_up'] = []
                data_status['板块涨幅排行'] = False
                print("   ❌ 涨幅前10板块为空", flush=True)
            
            if sector_down:
                results['sector_change_down'] = sector_down
                data_status['板块跌幅排行'] = True
                print(f"   ✅ 跌幅前10板块: {len(sector_down)} 条")
            else:
                results['sector_change_down'] = []
                data_status['板块跌幅排行'] = False
                print("   ❌ 跌幅前10板块为空", flush=True)
            
            if sector_up or sector_down:
                step_status['板块涨跌幅排行获取'] = True
                elapsed, cum = timer.record("板块涨跌幅排行获取", 8)
                print(f"   ✅ 板块涨跌幅排行成功 [⏱ {elapsed:.2f}s]")
        except Exception as e:
            elapsed, cum = timer.record("板块涨跌幅排行获取(失败)", 8)
            print(f"   ❌ 板块涨跌幅排行失败: {e} [⏱ {elapsed:.2f}s]")
            results['sector_change_up'] = []
            results['sector_change_down'] = []
            data_status['板块涨幅排行'] = False
            data_status['板块跌幅排行'] = False
        
        # ========== 9. 成交额排名（iwencai API）==========
        step_status['成交额排名获取'] = False
        print(f"  9️⃣ 获取成交额排名（iwencai API）...")
        try:
            # 使用iwencai API获取成交额排名（支持历史日期）
            turnover_rank = get_turnover_rank_from_iwencai(limit=50, target_date=target_date)
            if turnover_rank:
                # 筛选成交额>100亿的个股，不限数量
                over_100b = [s for s in turnover_rank if s.get('turnover', 0) > 100]
                results['turnover_rank'] = turnover_rank  # 保留完整排名
                results['turnover_over_100b'] = over_100b  # 新增：>100亿单独存储
                data_status['成交额排名'] = True
                step_status['成交额排名获取'] = True
                elapsed, cum = timer.record("成交额排名获取", 9)
                print(f"   ✅ 成交额排名成功: {len(turnover_rank)} 条，>100亿: {len(over_100b)} 只 [⏱ {elapsed:.2f}s]")
                for i, stock in enumerate(over_100b[:5], 1):
                    print(f"      {i}. {stock.get('name')} ({stock.get('code')}): {stock.get('turnover', 0):.2f}亿")
            else:
                results['turnover_rank'] = []
                results['turnover_over_100b'] = []
                data_status['成交额排名'] = False
                print("   ❌ 成交额排名返回空", flush=True)
        except Exception as e:
            print(f"   ❌ 成交额排名失败: {e}")
            results['turnover_rank'] = []
            results['turnover_over_100b'] = []
            data_status['成交额排名'] = False
        
        # ========== 10. 预期日历（财联社CLS）==========
        step_status['预期日历获取'] = False
        print(f"  🔟 获取预期日历（财联社CLS）...")
        try:
            # 根据是否是复盘模式传入target_date
            calendar_target_date = target_date if 'target_date' in locals() or 'target_date' in globals() else None
            calendar = tencent.get_calendar_events(target_date=calendar_target_date)
            if calendar:
                results['calendar_events'] = calendar
                data_status['预期日历'] = True
                step_status['预期日历获取'] = True
                elapsed, cum = timer.record("预期日历获取", 10)
                print(f"   ✅ 预期日历成功: {len(calendar)} 条 [⏱ {elapsed:.2f}s]")
            else:
                results['calendar_events'] = []
                data_status['预期日历'] = False
                elapsed, cum = timer.record("预期日历获取(失败)", 10)
                print(f"   ❌ 预期日历返回空 [⏱ {elapsed:.2f}s]")
        except Exception as e:
            print(f"   ❌ 预期日历失败: {e}")
            results['calendar_events'] = []
            data_status['预期日历'] = False
        
        # ========== 11. 选股通盘中异动（可选）==========
        step_status['选股通盘中异动获取'] = False
        print(f"  1️⃣1️⃣ 获取选股通盘中异动（可选）...")
        try:
            analyzer = XuangubaoIntradayAnalyzer()
            xuangubao_data = analyzer.fetch_xuangubao_data()
            if xuangubao_data and xuangubao_data.get('xuangubao_news'):
                results['xuangubao_data'] = xuangubao_data
                data_status['选股通盘中异动'] = True
                step_status['选股通盘中异动获取'] = True
                elapsed, cum = timer.record("选股通盘中异动获取", 11)
                print(f"   ✅ 选股通数据成功: {len(xuangubao_data.get('xuangubao_news', []))} 条新闻 [⏱ {elapsed:.2f}s]")
            else:
                results['xuangubao_data'] = {}
                data_status['选股通盘中异动'] = False
                elapsed, cum = timer.record("选股通盘中异动获取(空)", 11)
                print(f"   ⚠️ 选股通数据返回空（可选模块） [⏱ {elapsed:.2f}s]")
        except Exception as e:
            print(f"   ⚠️ 选股通数据失败（可选模块）: {e}")
            results['xuangubao_data'] = {}
            data_status['选股通盘中异动'] = False
        
        # ========== 12. 顽主杯热门前十 ==========
        step_status['顽主杯热门前十获取'] = False
        print(f"  1️⃣2️⃣ 获取顽主杯热门前十...")
        try:
            wanzhu_top10 = collector.get_wanzhu_top10(target_date)
            results['wanzhu_top10'] = wanzhu_top10
            if wanzhu_top10:
                data_status['顽主杯热门前十'] = True
                step_status['顽主杯热门前十获取'] = True
                elapsed, cum = timer.record("顽主杯热门前十获取", 12)
                print(f"   ✅ 顽主杯前十成功: {len(wanzhu_top10)} 只 [⏱ {elapsed:.2f}s]")
            else:
                data_status['顽主杯热门前十'] = False
                elapsed, cum = timer.record("顽主杯热门前十获取(空)", 12)
                print(f"   ⚠️ 顽主杯数据为空 [⏱ {elapsed:.2f}s]")
        except Exception as e:
            print(f"   ⚠️ 顽主杯失败: {e}")
            results['wanzhu_top10'] = []
            data_status['顽主杯热门前十'] = False
        
        # ========== 11. 选股通盘中异动（可选）==========
        print(f"  1️⃣1️⃣ 获取选股通盘中异动（可选）...")
        try:
            analyzer = XuangubaoIntradayAnalyzer()
            xuangubao_data = analyzer.fetch_xuangubao_data()
            if xuangubao_data and xuangubao_data.get('xuangubao_news'):
                results['xuangubao_data'] = xuangubao_data
                print(f"   ✅ 选股通数据成功: {len(xuangubao_data.get('xuangubao_news', []))} 条新闻")
            else:
                results['xuangubao_data'] = {}
                print("   ⚠️ 选股通数据返回空", flush=True)
        except Exception as e:
            print(f"   ⚠️ 选股通数据失败（可选模块）: {e}")
            results['xuangubao_data'] = {}
        
        # ========== 12. 顽主杯热门前十 ==========
        print(f"  1️⃣2️⃣ 获取顽主杯热门前十...")
        try:
            wanzhu_top10 = collector.get_wanzhu_top10(target_date)
            results['wanzhu_top10'] = wanzhu_top10
            if wanzhu_top10:
                print(f"   ✅ 顽主杯前十成功: {len(wanzhu_top10)} 只")
            else:
                print("   ⚠️ 顽主杯数据为空", flush=True)
        except Exception as e:
            print(f"   ⚠️ 顽主杯失败: {e}")
            results['wanzhu_top10'] = []
        
        # ========== 13. 从涨停池提取连板梯队（改用akshare，支持历史日期）==========
        step_status['连板梯队提取'] = False
        print(f"  1️⃣3️⃣ 从涨停池提取连板梯队... (依赖: 步骤4)")
        try:
            # 从涨停池数据提取连板梯队
            if limit_up_df is not None and not limit_up_df.empty:
                lianban_data = []
                for _, row in limit_up_df.iterrows():
                    lianban_days = row.get('连板数', 1)
                    # 只保留连板数>=2的股票
                    if lianban_days >= 2:
                        # 首次封板时间处理 (如 "092500" -> "09:25:00")
                        first_limit_time_raw = str(row.get('首次封板时间', '')).strip()
                        if first_limit_time_raw and len(first_limit_time_raw) >= 6:
                            first_limit_time = f"{first_limit_time_raw[:2]}:{first_limit_time_raw[2:4]}:{first_limit_time_raw[4:6]}"
                        elif first_limit_time_raw and len(first_limit_time_raw) == 4:
                            first_limit_time = f"{first_limit_time_raw[:2]}:{first_limit_time_raw[2:4]}:00"
                        else:
                            first_limit_time = '15:00:00'  # 默认收盘时间
                        
                        lianban_data.append({
                            'code': row['代码'],
                            'name': row['名称'],
                            'lianban_days': lianban_days,
                            'change_pct': row.get('涨跌幅', 0),
                            'turnover': row.get('成交额', 0),
                            'sector': row.get('所属行业', '未知'),
                            'reason': row.get('涨停统计', ''),
                            'open_price': row.get('开盘价', 0),
                            'close_price': row.get('最新价', 0),
                            'high_price': row.get('最高价', 0),
                            'low_price': row.get('最低价', 0),
                            'first_limit_time': first_limit_time,  # 首次封板时间
                        })
                
                # 按连板数降序，同连板数按首次封板时间升序（越早越好）
                lianban_data.sort(key=lambda x: (-x['lianban_days'], x['first_limit_time']))
                
                results['lianban_data'] = lianban_data
                if lianban_data:
                    print(f"   ✅ 连板梯队提取成功: {len(lianban_data)} 只（最高{lianban_data[0]['lianban_days']}连板）")
                    step_status['连板梯队提取'] = True
                else:
                    print("   ⚠️ 连板梯队数据为空（无连板股）", flush=True)
            else:
                print("   ⚠️ 涨停池数据为空，无法提取连板梯队", flush=True)
                results['lianban_data'] = []
        except Exception as e:
            print(f"   ⚠️ 连板梯队提取失败: {e}")
            results['lianban_data'] = []
        
        # ========== 13. 龙虎榜数据 ==========
        print(f"  1️⃣3️⃣ 获取龙虎榜数据...")
        sys.stdout.flush()  # 立即输出

        try:
            from finshare import get_lhb
            # 日期格式需要是YYYYMMDD
            lhb_date = target_date.replace('-', '')
            lhb_df = get_lhb(start_date=lhb_date, end_date=lhb_date)
            if lhb_df is not None and len(lhb_df) > 0:
                # 列名是英文: fs_code(代码), net_buy_amount(净买入), buy_amount(买入金额), sell_amount(卖出金额)
                lhb_df['代码'] = lhb_df['fs_code'].str.replace('.SZ', '').str.replace('.SH', '').str.replace('.BJ', '')
                
                # v2.3.40修复：去重 - 同一只股票可能有多个营业部的记录，需要合并
                # 按代码分组，净买入金额求和
                lhb_df_grouped = lhb_df.groupby('代码').agg({
                    'net_buy_amount': 'sum',
                    'close_price': 'first',
                    'change_rate': 'first',
                    'fs_code': 'first'
                }).reset_index()
                
                # 获取已收集的数据用于板块查找
                zt_pool_raw = results.get('zt_pool', [])
                dt_pool_raw = results.get('dt_pool', [])
                zt_pool_by_sector = results.get('zt_pool_by_sector', {})
                
                # 净买入前10
                net_buy_df = lhb_df_grouped.nlargest(10, 'net_buy_amount')[['代码', 'net_buy_amount', 'close_price', 'change_rate']]
                net_buy_top10 = []
                for rank, (_, row) in enumerate(net_buy_df.iterrows(), 1):
                    code = row['代码']
                    # 优先从涨停池/跌停池查找板块
                    sector = '未知'
                    for stock in zt_pool_raw:
                        if stock.get('代码') == code:
                            sector = stock.get('所属行业', '未知')
                            break
                    if sector == '未知' and dt_pool_raw:
                        for stock in dt_pool_raw:
                            if stock.get('代码') == code:
                                sector = stock.get('所属行业', '未知')
                                break
                    
                    net_buy_top10.append({
                        'rank': rank,
                        'code': code,
                        'name': '',  # 将在批量查询后补充
                        'net_buy_amount_yi': row['net_buy_amount'] / 1e8,  # 转换为亿
                        'change_pct': row['change_rate'],
                        'zt_status': '正常',
                        'sector': sector
                    })
                
                # 净流出前10（净买入为负的）
                net_sell_df = lhb_df_grouped.nsmallest(10, 'net_buy_amount')[['代码', 'net_buy_amount', 'close_price', 'change_rate']]
                net_sell_top10 = []
                for rank, (_, row) in enumerate(net_sell_df.iterrows(), 1):
                    code = row['代码']
                    # 优先从涨停池/跌停池查找板块
                    sector = '未知'
                    for stock in zt_pool_raw:
                        if stock.get('代码') == code:
                            sector = stock.get('所属行业', '未知')
                            break
                    if sector == '未知' and dt_pool_raw:
                        for stock in dt_pool_raw:
                            if stock.get('代码') == code:
                                sector = stock.get('所属行业', '未知')
                                break
                    
                    net_sell_top10.append({
                        'rank': rank,
                        'code': code,
                        'name': '',  # 将在批量查询后补充
                        'net_buy_amount_yi': row['net_buy_amount'] / 1e8,  # 转换为亿
                        'change_pct': row['change_rate'],
                        'zt_status': '正常',
                        'sector': sector
                    })
                
                results['lhb_net_buy_top10'] = net_buy_top10
                results['lhb_net_sell_top10'] = net_sell_top10
                results['lhb_analysis'] = lhb_df_grouped.to_dict('records')
                print(f"   ✅ 龙虎榜: 净买{len(net_buy_top10)}只/净卖{len(net_sell_top10)}只（已去重）")
            else:
                results['lhb_net_buy_top10'] = []
                results['lhb_net_sell_top10'] = []
                results['lhb_analysis'] = []
                print("   ⚠️ 龙虎榜数据为空")
        except Exception as e:
            print(f"   ⚠️ 龙虎榜获取失败: {e}")
            import traceback
            traceback.print_exc()
            results['lhb_net_buy_top10'] = []
            results['lhb_net_sell_top10'] = []
            results['lhb_analysis'] = []
        elapsed, cum = timer.record("龙虎榜数据获取", 13)

        # 原始代码（暂时注释）
        '''
        try:
            import finshare as fs
            import requests

            # 获取龙虎榜数据
            lhb_date = target_date.replace('-', '')
            print(f"   📅 调用finshare.get_lhb({lhb_date})...")
            sys.stdout.flush()
            df = fs.get_lhb(lhb_date, lhb_date)
            print(f"   ✅ 龙虎榜数据获取完成: {len(df)}条")
            sys.stdout.flush()

            if df.empty:
                results['lhb_net_buy_top10'] = []
                results['lhb_net_sell_top10'] = []
                print("   ⚠️ 龙虎榜数据为空", flush=True)
            else:
                print(f"   📊 开始排序龙虎榜数据...")
                # 净买入前10
                df_sorted_buy = df.sort_values('net_buy_amount', ascending=False)
                top10_buy = df_sorted_buy.head(10)
                print(f"   ✅ 净买入前10筛选完成")

                # 净流出前10（净买入为负的，取绝对值最大的10个）
                df_sorted_sell = df.sort_values('net_buy_amount', ascending=True)
                top10_sell = df_sorted_sell.head(10)
                print(f"   ✅ 净流出前10筛选完成")

                # 提取所有股票代码
                print(f"   📝 提取股票代码...")
                buy_codes = [str(row['fs_code']).replace('.SZ', '').replace('.SH', '') for _, row in top10_buy.iterrows()]
                sell_codes = [str(row['fs_code']).replace('.SZ', '').replace('.SH', '') for _, row in top10_sell.iterrows()]
                all_codes = list(set(buy_codes + sell_codes))
                print(f"   ✅ 提取完成: {len(all_codes)} 只股票")

                # 批量获取股票信息（名称、涨跌幅、涨停状态）
                print(f"   📡 腾讯API批量查询 {len(all_codes)} 只股票...")
                codes_with_market = []
                for code in all_codes:
                    if code.startswith('6'):
                        codes_with_market.append(f'sh{code}')
                    else:
                        codes_with_market.append(f'sz{code}')

                # 腾讯API批量查询
                url = f"http://qt.gtimg.cn/q={','.join(codes_with_market)}"
                response = requests.get(url, timeout=10)
                response.encoding = 'gbk'
                lines = response.text.strip().split('\n')
                print(f"   ✅ 腾讯API返回 {len(lines)} 行数据")

                stock_info = {}
                for line in lines:
                    if not line.startswith('v_'):
                        continue
                    parts = line.split('~')
                    if len(parts) < 35:
                        continue

                    code = parts[2]
                    name = parts[1]
                    change_pct = float(parts[32])
                    zt_status = '涨停' if change_pct >= 9.9 else ('跌停' if change_pct <= -9.9 else '正常')

                    stock_info[code] = {
                        'name': name,
                        'change_pct': round(change_pct, 2),
                        'zt_status': zt_status
                    }

                # 构建净买入前10
                print(f"   📊 构建龙虎榜净买入前10...")
                lhb_net_buy = []
                for rank, (_, row) in enumerate(top10_buy.iterrows(), 1):
                    stock_code = str(row['fs_code']).replace('.SZ', '').replace('.SH', '')
                    info = stock_info.get(stock_code, {})
                    stock_name = info.get('name', '')

                    # 使用get_stock_sector获取板块（跳过API调用，避免批量处理卡死）
                    sector = get_stock_sector(
                        stock_name,
                        stock_code,
                        hot_rank_data=results.get('hot_rank_top30'),
                        zt_pool_data=results.get('zt_pool_by_sector'),
                        zt_pool_raw=results.get('zt_pool'),
                        dt_pool_raw=results.get('dt_pool'),
                        lianban_data=results.get('lianban_data'),
                        lhb_data=None,  # 避免循环
                        sector_fund_flow=results.get('sector_fund_flow'),
                        skip_api_call=True  # 跳过东方财富API调用
                    )
                    print(f"      {rank}. {stock_name}({stock_code}) - 板块: {sector}")

                    item = {
                        'rank': rank,
                        'code': stock_code,
                        'net_buy_amount_yi': row['net_buy_amount'] / 100000000,
                        'name': stock_name,
                        'change_pct': info.get('change_pct', 0),
                        'zt_status': info.get('zt_status', '正常'),
                        'sector': sector
                    }
                    lhb_net_buy.append(item)

                # 构建净流出前10
                print(f"   📊 构建龙虎榜净流出前10...")
                lhb_net_sell = []
                for rank, (_, row) in enumerate(top10_sell.iterrows(), 1):
                    stock_code = str(row['fs_code']).replace('.SZ', '').replace('.SH', '')
                    info = stock_info.get(stock_code, {})
                    stock_name = info.get('name', '')

                    # 使用get_stock_sector获取板块（跳过API调用，避免批量处理卡死）
                    sector = get_stock_sector(
                        stock_name,
                        stock_code,
                        hot_rank_data=results.get('hot_rank_top30'),
                        zt_pool_data=results.get('zt_pool_by_sector'),
                        zt_pool_raw=results.get('zt_pool'),
                        dt_pool_raw=results.get('dt_pool'),
                        lianban_data=results.get('lianban_data'),
                        lhb_data=None,  # 避免循环
                        sector_fund_flow=results.get('sector_fund_flow'),
                        skip_api_call=True  # 跳过东方财富API调用
                    )
                    print(f"      {rank}. {stock_name}({stock_code}) - 板块: {sector}")

                    item = {
                        'rank': rank,
                        'code': stock_code,
                        'net_sell_amount_yi': abs(row['net_buy_amount']) / 100000000,
                        'name': stock_name,
                        'change_pct': info.get('change_pct', 0),
                        'zt_status': info.get('zt_status', '正常'),
                        'sector': sector
                    }
                    lhb_net_sell.append(item)

                results['lhb_net_buy_top10'] = lhb_net_buy
                results['lhb_net_sell_top10'] = lhb_net_sell
                elapsed, cum = timer.record("龙虎榜数据获取", 13)
                print(f"   ✅ 龙虎榜净买入前十: {len(lhb_net_buy)} 只")
                print(f"   ✅ 龙虎榜净流出前十: {len(lhb_net_sell)} 只 [⏱ {elapsed:.2f}s]")
        except Exception as e:
            elapsed, cum = timer.record("龙虎榜数据获取(失败)", 13)
            print(f"   ⚠️ 龙虎榜失败: {e} [⏱ {elapsed:.2f}s]")
            import traceback
            traceback.print_exc()
            results['lhb_net_buy_top10'] = []
            results['lhb_net_sell_top10'] = []
        '''
        # ========== 14. 异动检测数据 ==========
        print(f"  1️⃣4️⃣ 获取异动检测数据...")
        try:
            import requests
            
            # 异动检测API
            url = "https://stock.quicktiny.cn/api/ladder/exchange-monitor/prediction"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # 解析数据
                today_predictions = []  # 当日预测
                nextday_predictions = []  # 次日预测
                
                if data and 'data' in data:
                    for item in data['data']:
                        stock_code = item.get('code', '')
                        stock_name = item.get('name', '')
                        deviation_days = item.get('max_days', 0)  # 修正字段名
                        deviation_pct = item.get('deviation_value', 0)  # 修正字段名
                        is_today = item.get('is_today', False)
                        is_nextday = item.get('is_nextday', False)
                        trigger_pct = item.get('change_rate_target', 0)  # 修正字段名
                        
                        prediction_item = {
                            'code': stock_code,
                            'name': stock_name,
                            'deviation_days': deviation_days,
                            'deviation_pct': deviation_pct,
                            'trigger_pct': trigger_pct
                        }
                        
                        if is_today:
                            today_predictions.append(prediction_item)
                        
                        if is_nextday:
                            nextday_predictions.append(prediction_item)
                
                results['exchange_monitor_today'] = today_predictions
                results['exchange_monitor_nextday'] = nextday_predictions
                
                # 获取异动股票的实时行情，判断今天是否已触发
                if today_predictions:
                    print(f"   📊 获取异动股票实时行情，判断触发状态...")
                    exchange_codes = [p['code'] for p in today_predictions]
                    try:
                        tencent_temp = TencentFinanceData()
                        exchange_quotes = tencent_temp.get_stock_batch_info(exchange_codes)
                        
                        # 更新today_predictions，添加实际涨幅和触发状态
                        for pred in today_predictions:
                            code = pred['code']
                            trigger_pct = pred.get('trigger_pct', 0)
                            if code in exchange_quotes:
                                actual_change = exchange_quotes[code].get('change_pct', 0)
                                pred['actual_change_pct'] = actual_change
                                # 判断是否已触发异动（实际涨幅 >= 触发条件）
                                pred['is_triggered'] = actual_change >= trigger_pct
                            else:
                                pred['actual_change_pct'] = None
                                pred['is_triggered'] = None
                        
                        triggered_count = sum(1 for p in today_predictions if p.get('is_triggered') == True)
                        print(f"   ✅ 已触发: {triggered_count}/{len(today_predictions)}只")
                    except Exception as eq_e:
                        print(f"   ⚠️ 获取异动股票行情失败: {eq_e}")
                
                elapsed, cum = timer.record("异动检测数据获取", 14)
                print(f"   ✅ 异动检测: 当日{len(today_predictions)}只，次日{len(nextday_predictions)}只 [⏱ {elapsed:.2f}s]")
            else:
                elapsed, cum = timer.record("异动检测数据获取(失败)", 14)
                print(f"   ⚠️ 异动检测API请求失败: {response.status_code} [⏱ {elapsed:.2f}s]")
                results['exchange_monitor_today'] = []
                results['exchange_monitor_nextday'] = []
        except Exception as e:
            elapsed, cum = timer.record("异动检测数据获取(异常)", 14)
            print(f"   ⚠️ 异动检测失败: {e} [⏱ {elapsed:.2f}s]")
            results['exchange_monitor_today'] = []
            results['exchange_monitor_nextday'] = []
        
        # ========== 批量获取所有股票的完整信息 ==========
        print("\n📊 批量获取股票完整信息（涨跌幅、最高价、最低价、开盘价、收盘价）...", flush=True)
        all_stock_codes = set()
        
        # 收集所有股票代码
        if results.get('hot_rank_top30'):
            for stock in results['hot_rank_top30']:
                code = stock.get('code', '').replace('sz', '').replace('sh', '').replace('bj', '')
                if code:
                    all_stock_codes.add(code)
        
        if results.get('turnover_rank'):
            for stock in results['turnover_rank']:
                code = stock.get('code', '').replace('sz', '').replace('sh', '')
                if code:
                    all_stock_codes.add(code)
        
        if results.get('lhb_net_buy_top10'):
            for stock in results['lhb_net_buy_top10']:
                code = stock.get('code', '').replace('.SZ', '').replace('.SS', '').replace('sz', '').replace('sh', '')
                if code:
                    all_stock_codes.add(code)
        
        if results.get('lhb_net_sell_top10'):
            for stock in results['lhb_net_sell_top10']:
                code = stock.get('code', '').replace('.SZ', '').replace('.SS', '').replace('sz', '').replace('sh', '')
                if code:
                    all_stock_codes.add(code)
        
        if results.get('lianban_data'):
            for stock in results['lianban_data']:
                code = stock.get('code', '').replace('.SZ', '').replace('.SS', '')
                if code:
                    all_stock_codes.add(code)
        
        # 批量查询股票信息
        if all_stock_codes:
            try:
                tencent = TencentFinanceData()
                stock_full_info = tencent.get_stock_batch_info(list(all_stock_codes))
                results['stock_full_info'] = stock_full_info
                elapsed, cum = timer.record("批量获取股票信息", 15)
                print(f"   ✅ 成功获取 {len(stock_full_info)} 只股票的完整信息 [⏱ {elapsed:.2f}s]")
            except Exception as e:
                elapsed, cum = timer.record("批量获取股票信息(失败)", 15)
                print(f"   ⚠️ 批量查询失败: {e} [⏱ {elapsed:.2f}s]")
                results['stock_full_info'] = {}
        else:
            elapsed, cum = timer.record("批量获取股票信息(跳过)", 15)
            results['stock_full_info'] = {}
        
        # 回填龙虎榜股票名称（从批量查询结果中获取）
        stock_full_info_for_fill = results.get('stock_full_info', {})
        if stock_full_info_for_fill:
            fill_count = 0
            for lhb_list_key in ('lhb_net_buy_top10', 'lhb_net_sell_top10'):
                for item in results.get(lhb_list_key, []):
                    code = item.get('code', '').replace('.SZ', '').replace('.SS', '')
                    if not item.get('name') and code and code in stock_full_info_for_fill:
                        info = stock_full_info_for_fill[code]
                        name_from_info = info.get('name') or info.get('名称', '')
                        if name_from_info:
                            item['name'] = name_from_info
                            fill_count += 1
            if fill_count > 0:
                print(f"   ✅ 回填龙虎榜股票名称: {fill_count} 只")
        
        print("\n🎉 所有数据获取完成!", flush=True)
        
        # ========== 全局板块AI分析 ==========
        print("\n🧠 进行全局板块AI分析...", flush=True)
        sector_analysis = analyze_sectors_comprehensive(results)
        results['sector_ai_analysis'] = sector_analysis
        elapsed, cum = timer.record("全局板块AI分析", 16)
        print(f"   ✅ 标准化板块: {len(sector_analysis['standard_sectors'])} 个 [⏱ {elapsed:.2f}s]")
        print(f"   ✅ 标准化板块: {len(sector_analysis['standard_sectors'])} 个")
        print(f"   ✅ 板块映射: {len(sector_analysis['mapping'])} 条")
        
        # ========== 15. AI多维量化分析（升级版）==========
        print("\n🔬 进行AI多维量化分析... (依赖: 步骤4, 步骤7, 步骤9, 步骤13)", flush=True)
        
        # 1. 放量异常检测（需要历史成交额数据）
        print("  1️⃣ 放量异常检测... (依赖: 候选池 - 连板梯队+热榜+龙虎榜)", flush=True)
        try:
            # 从候选池筛选（涨停池+成交额排名+连板+热榜+龙虎榜）
            # v2.3.32修复：补全各数据源的缺失字段（code/turnover不匹配问题）
            candidates_dict = {}
            
            # 预构建代码→成交额映射表（用于补全缺失字段）
            # 从成交额排名获取 {name: (turnover_亿, code)}
            tr_name_map = {}
            for s in results.get('turnover_rank', []):
                name = s.get('name', '')
                t = s.get('turnover', 0)
                if name and t > 0:
                    tr_name_map[name] = t  # 已经是亿单位
            
            # 从stock_full_info获取 {code: change_pct}
            sfi_map = results.get('stock_full_info', {})
            
            def safe_add_candidate(stock, source_name, default_turnover=None):
                """安全添加候选股，自动补全缺失的code/turnover"""
                code = stock.get('code', '') or stock.get('代码', '')
                name = stock.get('name', '') or stock.get('名称', '')
                turnover = stock.get('turnover', 0) or stock.get('成交额', 0) or default_turnover or 0
                
                # 统一转换为亿单位
                if turnover > 10000:
                    turnover = turnover / 1e8
                
                # 补全：如果没code但有name，从成交额排名反查
                if not code and name:
                    for s in results.get('turnover_rank', []):
                        if s.get('name') == name:
                            code = s.get('code', '')
                            break
                
                # 补全：如果没turnover但有code/name，从成交额排名反查
                if turnover < 1 and name:
                    turnover = tr_name_map.get(name, 0)
                
                if not code or turnover < 1:  # 降低最低门槛到1亿
                    return False
                if code not in candidates_dict:
                    candidates_dict[code] = {
                        'code': code,
                        'name': name,
                        'turnover': turnover,
                        'sector': stock.get('sector', ''),
                        '_source': source_name
                    }
                    return True
                return False
            
            added_count = {'zt': 0, 'tr': 0, 'lb': 0, 'hot': 0, 'lhb': 0}
            
            # 1. 涨停池（最核心：有完整code+成交额+板块）
            for zt in results.get('zt_pool', []):
                if safe_add_candidate(zt, '涨停池'):
                    added_count['zt'] += 1
            
            # 2. 成交额排名前20（高成交额股票，放量分析的核心对象）
            for s in results.get('turnover_rank', [])[:20]:
                if safe_add_candidate(s, '成交额排名'):
                    added_count['tr'] += 1
            
            # 3. 连板梯队（补充龙头股）
            for stock in results.get('lianban_data', []):
                if safe_add_candidate(stock, '连板'):
                    added_count['lb'] += 1
            
            # 4. 热榜前30（补全turnover从tr_name_map）
            for stock in results.get('hot_rank_top30', []):
                if safe_add_candidate(stock, '热榜'):
                    added_count['hot'] += 1
            
            # 5. 龙虎榜净买前10（资金关注标的）
            for stock in results.get('lhb_net_buy_top10', []):
                if safe_add_candidate(stock, '龙虎榜'):
                    added_count['lhb'] += 1
            
            candidates = list(candidates_dict.values())
            print(f"   📊 候选池: 涨停{added_count['zt']}只 + 成交额{added_count['tr']}只 + 连板{added_count['lb']}只 + 热榜{added_count['hot']}只 + 龙虎榜{added_count['lhb']}只 = {len(candidates)}只")
            
            if candidates:
                # 获取历史成交额数据（近20日）
                print(f"   📊 获取 {len(candidates)} 只候选股的历史成交额...")
                print(f"   📝 策略：QuickTiny API优先 → BaoStock兜底 | 最近3天实时，更早数据用缓存")
                
                # 初始化缓存
                cache = get_cache()
                cache.clean_old_cache(keep_days=7)  # 清理7天前的过期缓存
                
                # 显示缓存统计
                cache_stats = cache.get_cache_stats(target_date)
                if cache_stats['count'] > 0:
                    print(f"   💾 今日缓存: {cache_stats['count']}只股票, {cache_stats['size_mb']}MB")
                
                # 延迟导入，需要时才加载
                bs = None
                
                stocks_with_history = []
                
                # 统计
                quicktiny_success = 0
                quicktiny_fail = 0
                baostock_success = 0
                baostock_fail = 0
                cache_hits = 0
                cache_partial = 0
                
                for stock in candidates[:20]:  # 限制前20只，避免请求过多
                    code = stock.get('code', '')
                    name = stock.get('name', '')
                    current_turnover = stock.get('turnover', 0)
                    
                    code_for_lookup = code.replace('sz', '').replace('sh', '')
                    full_code = f"{'sh' if code_for_lookup.startswith('6') else 'sz'}{code_for_lookup}"
                    
                    try:
                        # 用dt别名避免与可能被遮蔽的datetime冲突（v2.3.33修复）
                        # 注意：第1283行有 from datetime import datetime，所以datetime已经是类而非模块
                        _target_dt = datetime.strptime(target_date, "%Y-%m-%d")
                        
                        # 1. 尝试从缓存获取历史数据（3天以前）
                        cached_data = cache.get(code_for_lookup, target_date)  # target_date是字符串
                        historical_part = []
                        
                        if cached_data and len(cached_data) > 3:
                            # 使用缓存的大部分数据（排除最后3天）
                            historical_part = cached_data[:-3] if len(cached_data) > 3 else []
                            cache_hits += 1
                            print(f"      💾 缓存命中({len(historical_part)}天): {code}")
                        
                        # 2. 实时获取最近数据（优先QuickTiny API，失败用BaoStock）
                        recent_part = []
                        data_source = "未知"
                        
                        # 2.1 首先尝试 QuickTiny API（更快）
                        try:
                            import requests
                            url = f"https://stock.quicktiny.cn/api/tushare/merged-kline/{full_code}?days=30"
                            resp = requests.get(url, timeout=10)
                            resp.raise_for_status()
                            data = resp.json()
                            
                            if data.get('success') and data.get('data'):
                                bars = data['data']
                                # 转换格式：提取成交额（亿元）
                                amounts = []
                                for d in bars:
                                    # 找到目标日期及之前的数据
                                    bar_date = d.get('date', '')  # QuickTiny API返回字段是date
                                    if bar_date and bar_date <= target_date.replace('-', ''):
                                        amount = d.get('amount') or 0
                                        if amount:
                                            amounts.append(float(amount) / 1e8)  # 转为亿元
                                
                                if amounts:
                                    recent_part = amounts
                                    quicktiny_success += 1
                                    data_source = "QuickTiny"
                                    print(f"      ⚡ QuickTiny成功: {code} ({len(recent_part)}天)")
                        except Exception as qt_err:
                            quicktiny_fail += 1
                            print(f"      ⚡ QuickTiny失败: {code}, 将使用BaoStock兜底")
                        
                        # 2.2 QuickTiny失败，使用BaoStock兜底
                        if not recent_part:
                            try:
                                if bs is None:
                                    from finshare.sources.baostock_source import BaoStockDataSource
                                    bs = BaoStockDataSource()
                                
                                recent_start = _target_dt - datetime.timedelta(days=25)
                                recent_end = _target_dt
                                
                                recent_data = bs.get_historical_data(
                                    code_for_lookup,
                                    recent_start.date(),
                                    recent_end.date()
                                )
                                
                                if recent_data and len(recent_data) > 0:
                                    recent_part = [h.amount / 1e8 for h in recent_data if h.amount and h.amount > 0]
                                    baostock_success += 1
                                    data_source = "BaoStock"
                                    print(f"      🔄 BaoStock兜底成功: {code} ({len(recent_part)}天)")
                                else:
                                    baostock_fail += 1
                            except Exception as bs_err:
                                baostock_fail += 1
                                print(f"      ❌ BaoStock也失败: {code} - {bs_err}")
                        
                        # 3. 合并数据：历史缓存 + 最近实时（防膨胀）
                        #    历史缓存已含最近3天时直接用，避免重复拼接
                        if historical_part and recent_part:
                            # 取历史部分最后3天，如果与实时数据重叠则不重复追加
                            hist_tail = historical_part[-3:] if len(historical_part) >= 3 else historical_part
                            # 简单策略：历史部分截去尾部3天(会被recent替代)，再拼接
                            combined = historical_part[:-3] + recent_part if len(historical_part) > 3 else recent_part
                            cache_partial += 1
                            data_source = f"缓存+{data_source}"
                        elif recent_part:
                            combined = recent_part
                        elif historical_part:
                            combined = historical_part
                            data_source = "缓存"
                        else:
                            print(f"      ⚠️ {code} 无数据可用")
                            continue
                        
                        # 4. 更新缓存（保存合并后的数据，供下次使用历史部分）
                        if len(combined) > 3:
                            cache_data_to_save = combined[:-3]  # 排除最近3天
                            cache.set(code_for_lookup, target_date, cache_data_to_save, source="mixed_partial", max_length=120)
                        
                        full_info = results.get('stock_full_info', {}).get(code_for_lookup, {})
                        stocks_with_history.append({
                            'code': code,
                            'name': name,
                            'turnover': current_turnover,
                            'change_pct': full_info.get('change_pct', 0),
                            'sector': stock.get('sector', 'unknown'),
                            'hist_turnover': combined,
                            'data_source': data_source
                        })
                        
                    except Exception as e:
                        print(f"      ⚠️ {name} 历史数据获取失败: {e}")
                
                # 打印统计
                print(f"   📈 数据源统计: QuickTiny成功{quicktiny_success}只/失败{quicktiny_fail}只, BaoStock兜底成功{baostock_success}只/失败{baostock_fail}只, 缓存命中{cache_hits}只")
                
                # 输出统计
                print(f"   📊 数据统计: 缓存完整命中{cache_hits}只, 混合获取{cache_partial}只, QuickTiny成功{quicktiny_success}只, BaoStock成功{baostock_success}只")
                
                volume_anomalies = analyze_volume_anomaly(stocks_with_history, {})
                results['volume_anomalies'] = volume_anomalies
                results['stocks_with_history'] = stocks_with_history  # 保存供后续使用
                print(f"   ✅ 检测到 {len(volume_anomalies)} 个放量异常, 历史数据覆盖{len(stocks_with_history)}只")
                
                # 调试：显示前3只股票的数据
                if stocks_with_history:
                    print(f"   📊 调试信息（前3只股票）:")
                    for i, stock in enumerate(stocks_with_history[:3], 1):
                        current = stock.get('turnover', 0)
                        hist = stock.get('hist_turnover', [])
                        avg_5d = sum(hist[-5:]) / len(hist[-5:]) if len(hist) >= 5 else 0
                        ratio = current / avg_5d if avg_5d > 0 else 0
                        print(f"      {i}. {stock.get('name', '?')}: 当日{current:.1f}亿, 5日均值{avg_5d:.1f}亿, 放量{ratio:.2f}倍")
            else:
                print("   ⚠️ 无成交额>50亿的候选股", flush=True)
                results['volume_anomalies'] = []
        except Exception as e:
            print(f"   ⚠️ 放量异常检测失败: {e}")
            import traceback
            traceback.print_exc()
            results['volume_anomalies'] = []
        
        # 2. 龙虎榜深度分析
        print("  2️⃣ 龙虎榜深度分析... (依赖: 步骤13-龙虎榜数据)", flush=True)
        try:
            lhb_analysis = analyze_lhb(
                results.get('lhb_net_buy_top10', []) + results.get('lhb_net_sell_top10', []),
                {}
            )
            results['lhb_analysis'] = lhb_analysis
            print(f"   ✅ 分析 {len(lhb_analysis)} 只龙虎榜股票")
        except Exception as e:
            print(f"   ⚠️ 龙虎榜分析失败: {e}")
            results['lhb_analysis'] = []
        
        # 3. 板块共振评分
        print("  3️⃣ 板块共振评分... (依赖: 步骤4-涨停池, 步骤7-板块资金流向)", flush=True)
        try:
            # 准备板块数据（使用标准化板块名称）
            sectors_data = {}
            sector_ai = results.get('sector_ai_analysis', {})
            
            # 调试：打印板块名称
            zt_sectors = list(results.get('zt_pool_by_sector', {}).keys())
            fund_sectors = [flow.get('name') for flow in results.get('sector_fund_flow', {}).get('inflow', [])]
            print(f"   📊 涨停池板块: {zt_sectors[:5]}")
            print(f"   📊 资金流向板块: {fund_sectors[:5]}")
            
            # 构建标准化板块名称映射（资金流向）- 合并同一标准化板块的数据
            fund_flow_by_standard = {}
            for flow in results.get('sector_fund_flow', {}).get('inflow', []):
                original_name = flow.get('name', '')
                standard_name = get_standardized_sector(original_name, sector_ai)
                
                # 合并同一标准化板块的资金流向数据
                if standard_name not in fund_flow_by_standard:
                    fund_flow_by_standard[standard_name] = flow.copy()
                else:
                    # 合并资金流向数据（累加主力净流入）
                    existing = fund_flow_by_standard[standard_name]
                    existing['zljlr'] = existing.get('zljlr', 0) + flow.get('zljlr', 0)
                    # 保留涨跌幅较大的板块数据
                    if abs(flow.get('zdf', 0)) > abs(existing.get('zdf', 0)):
                        existing['zdf'] = flow.get('zdf', 0)
            
            match_count = 0
            matched_sectors = []
            unmatched_sectors = []
            for sector_name, zt_stocks in results.get('zt_pool_by_sector', {}).items():
                # 标准化板块名称
                standard_sector = get_standardized_sector(sector_name, sector_ai)
                
                # 获取资金流向（使用标准化名称匹配）
                fund_flow = fund_flow_by_standard.get(standard_sector, {})
                if fund_flow:
                    match_count += 1
                    matched_sectors.append(f"{sector_name}({standard_sector})")
                else:
                    unmatched_sectors.append(f"{sector_name}({standard_sector})")
                
                # 获取龙虎榜数据
                sector_lhb = [
                    lhb for lhb in results.get('lhb_analysis', [])
                    if any(lhb.stock_code == s.get('code', '') for s in zt_stocks)
                ]
                
                # 统计热榜数量
                hot_rank_count = sum(
                    1 for s in results.get('hot_rank', [])
                    if s.get('sector') == sector_name
                )
                
                # 计算板块成交额变化（优先从涨停池数据获取）
                sector_volume_change = 0
                try:
                    # 方法1：从涨停池数据获取当日成交额（最准确）
                    zt_pool = results.get('zt_pool', [])
                    sector_zt_stocks = [
                        stock for stock in zt_pool
                        if stock.get('所属行业', '') == sector_name
                    ]
                    
                    if sector_zt_stocks:
                        # 计算板块当日总成交额（涨停股成交额之和）
                        current_sector_volume = sum(
                            stock.get('成交额', 0) for stock in sector_zt_stocks
                        )
                        
                        # 转换为亿单位（成交额单位是元）
                        current_sector_volume = current_sector_volume / 1e8
                        
                        # 方法2：从stocks_with_history获取历史成交额
                        # 标准化代码格式进行匹配（处理sz/sh前缀差异）
                        def normalize_code_for_match(code):
                            if not code:
                                return ''
                            code = str(code).replace('.SZ', '').replace('.SS', '').replace('.SH', '').lower()
                            return code.lstrip('szsh')
                        
                        sector_stocks_with_history = [
                            s for s in stocks_with_history
                            if any(
                                normalize_code_for_match(s.get('code', '')) == normalize_code_for_match(zt.get('代码', zt.get('code', '')))
                                for zt in zt_stocks
                            )
                        ]
                        
                        if sector_stocks_with_history:
                            # 计算板块历史平均成交额（5日）
                            hist_sector_volumes = []
                            for i in range(5):  # 取最近5天
                                day_volume = sum(
                                    s.get('hist_turnover', [])[-(i+1)] if len(s.get('hist_turnover', [])) > i else 0
                                    for s in sector_stocks_with_history
                                )
                                if day_volume > 0:
                                    hist_sector_volumes.append(day_volume)
                            
                            if hist_sector_volumes:
                                avg_sector_volume = sum(hist_sector_volumes) / len(hist_sector_volumes)
                                if avg_sector_volume > 0:
                                    sector_volume_change = ((current_sector_volume / avg_sector_volume) - 1) * 100
                                    print(f"      📊 {sector_name} 板块放量: 当日{current_sector_volume:.1f}亿 vs 5日均值{avg_sector_volume:.1f}亿, 变化{sector_volume_change:+.1f}%")
                except Exception as e:
                    print(f"      ⚠️ {sector_name} 板块成交量计算失败: {e}")
                    pass  # 计算失败时保持为0
                
                sectors_data[sector_name] = {
                    'fund_flow': fund_flow,
                    'zt_stocks': zt_stocks,
                    'lhb_data': sector_lhb,
                    'hot_rank_count': hot_rank_count,
                    'volume_change': sector_volume_change,  # 板块成交量变化
                    'price_change': fund_flow.get('zdf', 0)
                }
            
            print(f"   📊 板块匹配统计: {match_count}/{len(zt_sectors)} 个板块成功匹配资金流向（标准化后）")
            print(f"   ✅ 匹配成功: {matched_sectors[:5]}")
            print(f"   ❌ 匹配失败: {unmatched_sectors[:5]}")
            
            resonance_scores = calculate_resonance(sectors_data)
            results['resonance_scores'] = resonance_scores
            print(f"   ✅ 计算 {len(resonance_scores)} 个板块共振评分")
        except Exception as e:
            print(f"   ⚠️ 共振评分失败: {e}")
            results['resonance_scores'] = {}
        
        # 4. 生成交易信号
        print("  4️⃣ 生成交易信号...", flush=True)
        try:
            all_data_for_signals = {
                'sectors': sectors_data,
                'stocks': stocks_with_history,
                'lhb': results.get('lhb_analysis', []),
                'lhb_history': {},
                'calendar': results.get('calendar', []),
                'sector_avg_volume': {}
            }
            
            trade_signals = generate_trade_signals(all_data_for_signals)
            results['trade_signals'] = trade_signals
            elapsed, cum = timer.record("AI多维量化分析", 17)
            print(f"   ✅ 生成 {len(trade_signals)} 个交易信号 [⏱ {elapsed:.2f}s]")
            
            # 显示前5个信号
            for i, signal in enumerate(trade_signals[:5], 1):
                print(f"      {i}. [{signal.signal_type.value}] {signal.sector_name} - {signal.action}")
        except Exception as e:
            print(f"   ⚠️ 交易信号生成失败: {e}")
            results['trade_signals'] = []
        
        print("   ✅ AI多维量化分析完成!", flush=True)
        
        # ========== 数据摘要 ==========
        print("\n" + "=" * 60)
        print("📊 数据摘要", flush=True)
        print("=" * 60)
        print(f"💰 两市总成交额: {results['total_turnover']:.2f}亿元")
        
        if results.get('indices'):
            print("📈 主要指数:", flush=True)
            for name, data in results['indices'].items():
                price = data.get('点位', data.get('price', 0))
                change_pct = data.get('涨跌幅', data.get('change_pct', 0))
                print(f"  {name}: {price:.2f}点 ({change_pct:+.2f}%)")
        
        if results.get('wind_a_alternative'):
            wa = results['wind_a_alternative']
            print(f"🌐 中证全指(Wind全A平替): {wa.get('点位', wa.get('price', 0)):.2f}点 ({wa.get('涨跌幅', wa.get('change_pct', 0)):+.2f}%)")
        
        if results.get('hot_rank_top30'):
            print(f"🔥 热度前三十: {len(results['hot_rank_top30'])} 只")
        
        if results.get('hot_plates'):
            print(f"📊 板块热榜: {len(results['hot_plates'])} 条")
        
        if results.get('zt_pool'):
            print(f"📈 涨停池: {len(results['zt_pool'])} 只")
        
        if results.get('dt_pool'):
            print(f"📉 跌停池: {len(results['dt_pool'])} 只")
        
        if results.get('sector_fund_flow'):
            print(f"💹 行业资金流向: {len(results['sector_fund_flow'])} 条")
        
        if results.get('sector_change_up'):
            print(f"📊 涨幅前10板块: {len(results['sector_change_up'])} 条")
        
        if results.get('sector_change_down'):
            print(f"📊 跌幅前10板块: {len(results['sector_change_down'])} 条")
        
        if results.get('turnover_rank'):
            print(f"💵 成交额排名: {len(results['turnover_rank'])} 条")
        
        if results.get('calendar_events'):
            print(f"📅 预期日历: {len(results['calendar_events'])} 条")
        
        if results.get('xuangubao_data') and results['xuangubao_data'].get('xuangubao_news'):
            print(f"📡 选股通异动: {len(results['xuangubao_data'].get('xuangubao_news', []))} 条新闻")
        
        if results.get('wanzhu_top10'):
            print(f"🏆 顽主杯前十: {len(results['wanzhu_top10'])} 只")
        
        if results.get('lhb_net_buy_top10'):
            print(f"🐉 龙虎榜净买入前十: {len(results['lhb_net_buy_top10'])} 只")
        
        # ========== 18. 板块四象限数据（击球区分析）==========
        step_status['板块四象限数据获取'] = False
        print("  1️⃣5️⃣ 获取板块四象限数据（击球区分析）...", flush=True)
        try:
            quadrant_data = get_sector_quadrant_data(period=20, strength_period=3)
            if quadrant_data:
                results['sector_quadrant'] = quadrant_data
                hs_analysis = quadrant_data['high_strong_analysis']
                print(f"   ✅ 板块四象限数据获取成功")
                print(f"   📊 高强区间: {hs_analysis['total']}个板块")
                print(f"      🏆 最佳击球区（≥80分）: {hs_analysis['tier1_count']}个")
                print(f"      ⭐ 优质击球区（60-79分）: {hs_analysis['tier2_count']}个")
                print(f"      ✓ 普通击球区（40-59分）: {hs_analysis['tier3_count']}个")
                print(f"      ⚠️ 边缘击球区（<40分）: {hs_analysis['tier4_count']}个")
                step_status['板块四象限数据获取'] = True
                data_status['板块四象限'] = True
            else:
                print(f"   ⚠️ 板块四象限数据获取失败")
                data_status['板块四象限'] = False
        except Exception as e:
            print(f"   ⚠️ 板块四象限数据获取异常: {e}")
            data_status['板块四象限'] = False
        
        # ========== 添加状态跟踪字典到结果 ==========
        results['data_status'] = data_status
        results['step_status'] = step_status
        
        # 打印状态统计
        print("\n" + "=" * 60)
        print("📊 数据获取状态统计", flush=True)
        print("=" * 60)
        success_count = sum(1 for v in data_status.values() if v)
        total_count = len(data_status)
        print(f"数据源获取成功: {success_count}/{total_count}")
        for key, value in data_status.items():
            status_icon = "✅" if value else "❌"
            print(f"  {status_icon} {key}")
        
        print("\n" + "=" * 60)
        print("📋 执行步骤状态统计", flush=True)
        print("=" * 60)
        step_success_count = sum(1 for v in step_status.values() if v)
        step_total_count = len(step_status)
        print(f"步骤执行成功: {step_success_count}/{step_total_count}")
        for key, value in step_status.items():
            status_icon = "✅" if value else "❌"
            print(f"  {status_icon} {key}")
        
        # 打印计时摘要
        timer.print_summary()
        
        # 打印LLM调用统计
        llm_stats = get_llm_call_stats()
        if llm_stats['total_calls'] > 0:
            print("\n" + "=" * 80)
            print("LLM调用统计", flush=True)
            print("-" * 80)
            print(f"{'类型':<30} {'调用次数':>10} {'总耗时':>12} {'平均耗时':>12}")
            print("-" * 80)
            if llm_stats['event_analysis_calls'] > 0:
                avg_time = llm_stats['event_analysis_time'] / llm_stats['event_analysis_calls']
                print(f"{'事件板块分析':<30} {llm_stats['event_analysis_calls']:>10} {llm_stats['event_analysis_time']:>11.2f}s {avg_time:>11.2f}s")
            if llm_stats['sector_analysis_calls'] > 0:
                avg_time = llm_stats['sector_analysis_time'] / llm_stats['sector_analysis_calls']
                print(f"{'板块关系分析':<30} {llm_stats['sector_analysis_calls']:>10} {llm_stats['sector_analysis_time']:>11.2f}s {avg_time:>11.2f}s")
            print("-" * 80)
            avg_total = llm_stats['total_time'] / llm_stats['total_calls']
            print(f"{'总计':<30} {llm_stats['total_calls']:>10} {llm_stats['total_time']:>11.2f}s {avg_total:>11.2f}s")
            print("=" * 80)
        
        # 将计时数据保存到results中供报告使用
        results['timer_summary'] = timer.get_summary()
        results['llm_stats'] = llm_stats
        
        # 将状态跟踪数据保存到results中供报告使用
        results['data_status'] = data_status
        results['step_status'] = step_status
        
        return results
        
    except Exception as e:
        print(f"\n❌ 数据获取失败: {e}")
        import traceback
        traceback.print_exc()
        return results


def analyze_sectors_comprehensive(all_data: dict) -> dict:
    """
    全局板块AI分析：对所有数据源中的板块进行统一分析
    
    1. 收集所有数据源中的板块名称
    2. AI分析板块之间的关系（父子、包含、关联）
    3. 生成标准化映射表
    
    Returns:
        {
            'relationships': {原始板块: 分析结果},
            'mapping': {原始板块: 标准板块},
            'standard_sectors': [标准板块列表]
        }
    """
    
    # Step 1: 收集所有板块
    all_sectors = set()
    sector_sources = {}  # 记录板块来源
    
    # 从资金流向收集
    if all_data.get('sector_fund_flow'):
        for item in all_data['sector_fund_flow'].get('inflow', []):
            name = item.get('name', '')
            if name:
                all_sectors.add(name)
                sector_sources[name] = 'fund_flow'
        for item in all_data['sector_fund_flow'].get('outflow', []):
            name = item.get('name', '')
            if name:
                all_sectors.add(name)
                sector_sources[name] = 'fund_flow'
    
    # 从板块热榜收集
    if all_data.get('hot_plates'):
        for plate in all_data['hot_plates']:
            name = plate.get('name', '')
            if name:
                all_sectors.add(name)
                sector_sources[name] = 'hot_plate'
    
    # 从涨停池板块分布收集
    if all_data.get('zt_pool_by_sector'):
        for sector_name in all_data['zt_pool_by_sector'].keys():
            if sector_name:
                all_sectors.add(sector_name)
                sector_sources[sector_name] = 'zt_pool'
    
    # 从选股通收集（新闻中提取的）
    if all_data.get('xuangubao_data'):
        for plate in all_data['xuangubao_data'].get('xuangubao_plates', []):
            name = plate.get('name', '')
            if name:
                all_sectors.add(name)
                sector_sources[name] = 'xuangubao'
    
    # 从连板梯队收集
    if all_data.get('lianban_data'):
        for stock in all_data['lianban_data']:
            plates = stock.get('plates', [])
            for plate in plates:
                if plate:
                    all_sectors.add(plate)
                    sector_sources[plate] = 'lianban'
    
    # Step 2: AI分析板块关系
    sector_relationships = {}
    
    for sector in all_sectors:
        if not sector:
            continue
        
        analysis = analyze_single_sector_ai(sector, all_sectors)
        analysis['source'] = sector_sources.get(sector, 'unknown')
        sector_relationships[sector] = analysis
    
    # Step 3: 生成映射表（原始名称 -> 标准名称）
    mapping = {}
    for original, analysis in sector_relationships.items():
        mapping[original] = analysis['standard_name']
    
    # Step 4: 识别父子关系，建立板块树
    sector_tree = build_sector_tree(sector_relationships)
    
    return {
        'relationships': sector_relationships,
        'mapping': mapping,
        'standard_sectors': list(set(mapping.values())),  # 去重后的标准板块列表
        'sector_tree': sector_tree,
        'sector_count': len(all_sectors),
        'standard_count': len(set(mapping.values()))
    }


def analyze_single_sector_ai(sector_name: str, all_sectors: set) -> dict:
    """
    AI分析单个板块
    
    基于名称相似性、包含关系、市场常识进行判断
    """
    
    analysis = {
        'original_name': sector_name,
        'standard_name': sector_name,  # 默认不变
        'parent': None,
        'children': [],
        'related': [],
        'type': 'unknown',
        'confidence': 0.5
    }
    
    # ========== 轨道交通产业链 ==========
    if any(keyword in sector_name for keyword in ['轨交', '轨道交通', '高铁', '铁路', '城轨']):
        analysis['standard_name'] = '轨道交通'
        analysis['type'] = '行业'
        analysis['confidence'] = 0.95
        
        # 判断细分关系
        if '高铁' in sector_name:
            analysis['parent'] = '轨道交通'
        elif '城轨' in sector_name or '地铁' in sector_name:
            analysis['parent'] = '轨道交通'
        elif '设备' in sector_name:
            analysis['parent'] = '轨道交通'
            analysis['related'] = ['机械', '装备制造']
    
    # ========== 电力/绿电产业链 ==========
    elif any(keyword in sector_name for keyword in ['绿电', '电力', '电网', '发电', '供电']):
        analysis['standard_name'] = '绿电'
        analysis['type'] = '行业'
        analysis['confidence'] = 0.9
        
        if '算电' in sector_name or '协同' in sector_name:
            analysis['standard_name'] = '算电协同'
            analysis['parent'] = '绿电'
            analysis['related'] = ['算力', '数据中心']
        elif '光伏' in sector_name:
            analysis['parent'] = '绿电'
            analysis['related'] = ['储能']
        elif '储能' in sector_name:
            analysis['parent'] = '绿电'
            analysis['related'] = ['光伏', '风电']
    
    # ========== 商业航天产业链 ==========
    elif any(keyword in sector_name for keyword in ['航天', '卫星', '太空', '商业航天', '火箭']):
        analysis['standard_name'] = '商业航天'
        analysis['type'] = '概念'
        analysis['confidence'] = 0.9
        
        if '光伏' in sector_name and ('太空' in sector_name or '卫星' in sector_name):
            analysis['standard_name'] = '太空光伏'
            analysis['parent'] = '商业航天'
        elif '卫星' in sector_name:
            analysis['parent'] = '商业航天'
        elif '火箭' in sector_name or '发射' in sector_name:
            analysis['parent'] = '商业航天'
    
    # ========== 算力产业链 ==========
    elif any(keyword in sector_name for keyword in ['算力', 'AI', '智算', '数据中心', '服务器']):
        analysis['standard_name'] = '算力'
        analysis['type'] = '概念'
        analysis['confidence'] = 0.9
        
        if '液冷' in sector_name:
            analysis['standard_name'] = '液冷服务器'
            analysis['parent'] = '算力'
        elif 'AI' in sector_name or '人工智能' in sector_name:
            analysis['related'] = ['大模型', '算法']
    
    # ========== AI应用产业链 ==========
    elif any(keyword in sector_name for keyword in ['AI应用', '大模型', 'AIGC', 'ChatGPT']):
        analysis['standard_name'] = 'AI应用'
        analysis['type'] = '概念'
        analysis['confidence'] = 0.85
        analysis['related'] = ['算力', '大模型']
    
    # ========== 光通信产业链 ==========
    elif any(keyword in sector_name for keyword in ['光通信', '光模块', 'CPO', '光纤', '光缆', '光芯片', '光器件', '光学元件']):
        analysis['standard_name'] = '光通信'
        analysis['type'] = '行业'
        analysis['confidence'] = 0.9
        
        if '光纤' in sector_name or '光缆' in sector_name:
            analysis['parent'] = '光通信'
            analysis['related'] = ['通信设备']
    
    # ========== 半导体产业链 ==========
    elif any(keyword in sector_name for keyword in ['半导体', '芯片', '集成电路', '晶圆', '元件', '被动元件', '电子元件']):
        analysis['standard_name'] = '半导体'
        analysis['type'] = '行业'
        analysis['confidence'] = 0.9
        
        if '设备' in sector_name:
            analysis['parent'] = '半导体'
        elif '材料' in sector_name:
            analysis['parent'] = '半导体'
    
    # ========== 消费电子产业链 ==========
    elif any(keyword in sector_name for keyword in ['消费电子', '手机', '苹果', '华为', '小米']):
        analysis['standard_name'] = '消费电子'
        analysis['type'] = '行业'
        analysis['confidence'] = 0.85
    
    # ========== 新能源汽车产业链 ==========
    elif any(keyword in sector_name for keyword in ['电池', '锂电池', '固态电池', '新能源车', '电动车']):
        analysis['standard_name'] = '新能源车'
        analysis['type'] = '行业'
        analysis['confidence'] = 0.85
        
        if '电池' in sector_name:
            analysis['parent'] = '新能源车'
    
    # ========== 机器人产业链 ==========
    elif any(keyword in sector_name for keyword in ['机器人', '人形机器人', '工业机器人', '减速器']):
        analysis['standard_name'] = '人形机器人'
        analysis['type'] = '概念'
        analysis['confidence'] = 0.85
    
    # ========== 金融相关 ==========
    elif any(keyword in sector_name for keyword in ['银行', '券商', '保险', '金融']):
        analysis['standard_name'] = '大金融'
        analysis['type'] = '行业'
        analysis['confidence'] = 0.8
        
        if '银行' in sector_name:
            analysis['standard_name'] = '银行'
        elif '券商' in sector_name:
            analysis['standard_name'] = '券商'
    
    # ========== 医药相关 ==========
    elif any(keyword in sector_name for keyword in ['医药', '医疗', '药', '生物']):
        analysis['standard_name'] = '医药'
        analysis['type'] = '行业'
        analysis['confidence'] = 0.8
        
        if '创新药' in sector_name:
            analysis['standard_name'] = '创新药'
            analysis['parent'] = '医药'
    
    return analysis


def build_sector_tree(sector_relationships: dict) -> dict:
    """
    构建板块树结构
    
    基于父子关系构建层次结构
    """
    tree = {}
    
    # 首先收集所有父板块
    parents = set()
    for analysis in sector_relationships.values():
        if analysis['parent']:
            parents.add(analysis['parent'])
        parents.add(analysis['standard_name'])
    
    # 构建树
    for parent in parents:
        tree[parent] = {
            'children': [],
            'all_sectors': []
        }
    
    # 填充子板块
    for original, analysis in sector_relationships.items():
        standard = analysis['standard_name']
        parent = analysis['parent']
        
        if parent and parent in tree:
            tree[parent]['children'].append({
                'name': standard,
                'original': original,
                'type': analysis['type']
            })
        
        if standard in tree:
            tree[standard]['all_sectors'].append(original)
    
    return tree


def get_standardized_sector(sector_name: str, sector_analysis: dict) -> str:
    """
    获取标准化后的板块名称
    
    如果板块在映射表中，返回标准名称；否则返回原名称
    """
    if not sector_analysis or not sector_name:
        return sector_name
    
    mapping = sector_analysis.get('mapping', {})
    return mapping.get(sector_name, sector_name)


def _minimal_fallback_analysis(event_title: str, event_summary: str = "") -> dict:
    """极简兜底分析：仅在LLM调用失败时使用，基于事件文本进行基础推断
    
    与关键词映射不同，这里使用规则推理而非硬编码匹配表
    """
    full_text = f"{event_title} {event_summary}".lower()
    
    # 仅保留最基础的推理规则（不是关键词映射表）
    # 规则1：包含"原油/油价/石油"等 -> 石油/能源
    if any(term in full_text for term in ['原油', '油价', '石油', '燃油', 'opec', '伊朗']):
        return {
            'main_direction': '周期资源',
            'related_sectors': ['石油', '能源'],
            'trading_logic': '涉及原油/油价相关事件，影响石油产业链',
            'expectation': '根据具体事件判断',
            'confidence': '中'
        }
    
    # 规则2：包装/印刷相关 -> 包装印刷
    if any(term in full_text for term in ['包装', '印刷', '纸箱']):
        return {
            'main_direction': '消费',
            'related_sectors': ['包装印刷', '轻工制造'],
            'trading_logic': '涉及包装行业发展，利好相关产业链',
            'expectation': '根据具体事件判断',
            'confidence': '中'
        }
    
    # 规则3：机床/数控/工业设备 -> 机械设备（关联机器人）
    if any(term in full_text for term in ['机床', '数控', '工业母机', '装备制造']):
        return {
            'main_direction': '机械设备',
            'related_sectors': ['工业母机', '机床', '自动化', '人形机器人'],
            'trading_logic': '涉及机床/工业设备展览，利好装备制造及机器人产业链',
            'expectation': '根据具体事件判断',
            'confidence': '中'
        }
    
    # 规则4：海峡两岸/台湾/国台办 -> 海峡概念
    if any(term in full_text for term in ['海峡', '台湾', '国台办', '两岸', '闽台', '对台', '台海']):
        return {
            'main_direction': '海峡概念',
            'related_sectors': ['福建板块', '平潭综合实验区', '两岸金融'],
            'trading_logic': '涉及两岸关系事件，利好福建及海峡相关板块',
            'expectation': '根据具体事件判断',
            'confidence': '中'
        }
    
    # 规则5：消防/救援/应急 -> 消防设备
    if any(term in full_text for term in ['消防', '救援', '应急', '防火', '灭火']):
        return {
            'main_direction': '消防设备',
            'related_sectors': ['消防设备', '应急救援', '安防'],
            'trading_logic': '涉及消防/应急政策，利好消防设备产业链',
            'expectation': '根据具体事件判断',
            'confidence': '中'
        }
    
    # 规则6：光通信/6G/5G/CPO -> 光通信
    if any(term in full_text for term in ['光通信', '6g', '5g', 'cpo', '光模块', '光芯片']):
        return {
            'main_direction': '光通信',
            'related_sectors': ['光模块', 'CPO', '光芯片', '通信设备'],
            'trading_logic': '涉及光通信技术/标准进展，利好光通信产业链',
            'expectation': '根据具体事件判断',
            'confidence': '中'
        }
    
    # 规则7：机器人/具身智能 -> 人形机器人
    if any(term in full_text for term in ['机器人', '具身智能', '减速器', '伺服电机']):
        return {
            'main_direction': '人形机器人',
            'related_sectors': ['减速器', '伺服电机', '传感器', '执行器'],
            'trading_logic': '涉及机器人产业进展，利好人形机器人产业链',
            'expectation': '根据具体事件判断',
            'confidence': '中'
        }
    
    # 无法推断时返回其他（不强匹配）
    return {
        'main_direction': '其他',
        'related_sectors': [],
        'trading_logic': '事件产业链方向不明确',
        'expectation': '中性',
        'confidence': '低'
    }


def ai_analyze_event_sectors(event_title, event_summary=""):
    """AI智能分析事件所属的产业链方向和炒作预期（纯AI推理，无硬编码映射）
    
    使用DeepSeek LLM API进行真正的语义分析，完全依赖AI自主推理能力识别产业链方向。
    不再使用任何硬编码关键词映射表，让AI基于事件内容的真实含义进行判断。
    
    Args:
        event_title: 事件标题
        event_summary: 事件摘要/内容
    
    Returns:
        dict: {
            'main_direction': '主要产业链方向',
            'related_sectors': ['细分板块1', '细分板块2'],
            'trading_logic': '炒作逻辑',
            'expectation': '预期分析（利好/利空/中性）',
            'confidence': '高/中/低'
        }
    """
    global _llm_call_stats
    full_text = f"{event_title} {event_summary}".strip()
    start_time = time.time()
    
    try:
        client = get_llm_service()
        result = client.analyze_event_sectors(event_title, event_summary)
        
        # 记录统计
        elapsed = time.time() - start_time
        _llm_call_stats['total_calls'] += 1
        _llm_call_stats['total_time'] += elapsed
        _llm_call_stats['event_analysis_calls'] += 1
        _llm_call_stats['event_analysis_time'] += elapsed
        
        # 【C修复】当AI返回"其他"时，使用极简规则兜底
        if result.get('main_direction') == '其他':
            # 尝试用极简兜底规则识别
            fallback_result = _minimal_fallback_analysis(event_title, event_summary)
            if fallback_result.get('main_direction') != '其他':
                print(f"  [AI兜底] '{event_title[:30]}...' -> {fallback_result['main_direction']}（极简规则兜底）")
                return fallback_result
            else:
                print(f"  [AI分析] '{event_title[:30]}...' -> 其他（AI无法识别明确产业链）")
        else:
            print(f"  [AI分析] '{event_title[:30]}...' -> {result.get('main_direction')}（置信度:{result.get('confidence', '中')}）")
        
        return result
        
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"[ai_analyze_event_sectors] LLM调用失败({elapsed:.2f}s): {e}")
        # LLM调用失败时，使用极简兜底（仅区分已知大类）
        return _minimal_fallback_analysis(event_title, event_summary)


def _llm_analyze_event(event_text):
    """【已弃用】原硬编码分析函数，现通过ai_analyze_event_sectors调用真实LLM
    
    保留此函数仅用于兼容，实际分析已迁移至LLMClient.analyze_event_sectors
    """
    return ai_analyze_event_sectors(event_text)


def _fallback_sector_analysis(text):
    """Fallback分析：当主要关键词未匹配时，基于事件类型和常见模式推断产业链方向"""
    # 经济数据类事件 -> 金融/周期
    if any(term in text for term in ['gdp', 'cpi', 'ppi', 'pmi', '非农', '就业', '失业', '通胀', '通缩', 
                                      '经济数据', '经济指标', '统计', '公布', '财报', '业绩']):
        if any(term in text for term in ['cpi', 'ppi', '通胀', '物价']):
            return '消费'
        elif any(term in text for term in ['gdp', 'pmi', '工业']):
            return '周期资源'
        else:
            return '金融'
    
    # 政策/监管类事件 -> 金融
    if any(term in text for term in ['监管', '证监会', '银保监会', '央行', '政策', '新规', '办法', '条例']):
        return '金融'
    
    # 国际贸易/关税类 -> 周期资源/出口链
    if any(term in text for term in ['关税', '贸易', '出口', '进口', '海关总署', '中美', '欧盟']):
        return '周期资源'
    
    # 会议/峰会类 -> 根据会议主题推断
    if any(term in text for term in ['峰会', '论坛', '大会', '会议', ' expo', ' conference']):
        if any(term in text for term in ['ai', '智能', '科技', '数字']):
            return 'AI算力'
        elif any(term in text for term in ['医疗', '医药', '健康']):
            return '医药医疗'
        elif any(term in text for term in ['能源', '环境', '气候', '碳']):
            return '新能源'
        elif any(term in text for term in ['金融', '经济', '投资', '银行']):
            return '金融'
    
    # 产品发布类 -> 消费电子/汽车
    if any(term in text for term in ['发布', '新品', '上市', '预售', '发布会']):
        if any(term in text for term in ['车', '汽车', '电动']):
            return '汽车产业链'
        elif any(term in text for term in ['手机', '电脑', '平板', '耳机', '手表']):
            return '消费电子'
    
    # 无法推断
    return None


def _infer_related_sectors(text):
    """从文本中推断相关板块"""
    sectors = []
    # 基于文本内容提取可能的板块标签
    sector_mapping = {
        'ai': ['AI应用', '大模型', '算力', 'AI芯片'],
        '医药': ['化学制药', '生物制品', '医疗器械', 'CXO'],
        '光通信': ['光模块', 'CPO', '光芯片', '光纤光缆'],
        '机器人': ['人形机器人', '减速器', '伺服电机', '传感器'],
        '新能源': ['光伏', '储能', '锂电池', '电网设备'],
        '半导体': ['半导体设备', '半导体材料', '存储芯片', '先进封装'],
        '汽车': ['汽车零部件', '智能驾驶', '整车', '锂电池'],
        '消费电子': ['手机产业链', '面板', 'VR/AR', '穿戴设备'],
    }
    
    for key, vals in sector_mapping.items():
        if key in text.lower():
            sectors.extend(vals)
    
    return list(set(sectors))[:5] if sectors else []


def _generate_related_sectors(direction, text):
    """根据方向生成相关细分板块"""
    sector_map = {
        'AI算力': ['AI芯片', '服务器', '液冷', '数据中心', '云计算', '光模块'],
        '医药医疗': ['创新药', 'CXO', '化学制药', '医疗器械', '中药', '生物制品'],
        '光通信': ['光模块', 'CPO', '光芯片', '光纤光缆', '通信设备'],
        '人形机器人': ['减速器', '伺服电机', '传感器', '执行器', '灵巧手'],
        '新能源': ['光伏组件', '储能', '锂电池', '电网设备', '逆变器'],
        '半导体': ['半导体设备', '光刻胶', '存储芯片', '先进封装', 'EDA'],
        '汽车产业链': ['汽车零部件', '智能驾驶', '激光雷达', '整车', '充电桩'],
        '消费电子': ['手机产业链', '面板', 'VR/AR', '穿戴设备', '折叠屏'],
        '商业航天': ['卫星制造', '火箭发射', '卫星互联网', '遥感导航', '地面设备'],
        '周期资源': ['有色金属', '稀土永磁', '化工新材料', '贵金属', '能源金属'],
        '金融': ['券商', '银行', '保险', '金融科技', '数字货币'],
        '消费': ['白酒', '免税', '旅游酒店', '食品饮料', '家电'],
        '房地产': ['房地产开发', '建材', '物业管理', '家居', '基建'],
        '军工': ['航空装备', '航天装备', '船舶', '军工电子', '地面兵装']
    }
    return sector_map.get(direction, ['相关产业链标的'])


def _generate_trading_logic(direction, text):
    """基于理解和推理生成炒作逻辑"""
    logic_map = {
        'AI算力': 'AI产业核心基础设施，算力需求持续增长，大模型迭代驱动',
        '医药医疗': '政策驱动+防守属性，博弈医药改革/创新药政策预期',
        '光通信': 'AI算力基建受益方向，高速光互联需求爆发，海外订单驱动',
        '人形机器人': '智能制造新方向，特斯拉/华为等产业巨头布局，商业化加速',
        '新能源': '能源转型大趋势，政策+需求双驱动，关注产能出清进度',
        '半导体': '国产替代加速，产业链自主可控，设备材料率先受益',
        '汽车产业链': '新能源汽车渗透率提升，智能化加速，出海逻辑顺畅',
        '消费电子': '新品周期驱动，AI终端渗透预期，华为/苹果产业链催化',
        '商业航天': '卫星互联网建设加速，商业航天政策放开，星座组网需求',
        '周期资源': '供需格局变化，涨价预期驱动，关注库存周期和产能变化',
        '金融': '政策宽松预期，资本市场改革受益，市场活跃度提升',
        '消费': '经济复苏预期，节假日/旺季催化，关注政策刺激力度',
        '房地产': '政策边际放松，销售数据改善预期，城中村改造催化',
        '军工': '国防预算增长，装备更新周期，人事调整落地后订单恢复'
    }
    
    base_logic = logic_map.get(direction, '产业链景气度变化，需结合资金流向判断')
    
    # 根据文本内容添加补充逻辑
    if '发布' in text or '出台' in text:
        base_logic += '，政策发布短期催化'
    elif '会议' in text or '峰会' in text:
        base_logic += '，事件驱动短期博弈'
    elif '获批' in text or '通过' in text:
        base_logic += '，审批进展利好兑现'
    
    return base_logic


def _infer_expectation(text):
    """基于语义推断预期"""
    # 积极信号词
    positive = ['利好', '发布', '启动', '开幕', '获批', '突破', '增长', '支持', 
                '鼓励', '推进', '加速', '通过', '落地', '实施', '提升', '扩大']
    # 消极信号词
    negative = ['收紧', '监管', '限制', '禁止', '下滑', '下降', '利空', '风险', 
                '暂停', '终止', '取消', '调查', '处罚', '违规', '暴雷']
    
    pos_count = sum(1 for p in positive if p in text)
    neg_count = sum(1 for n in negative if n in text)
    
    if pos_count > neg_count:
        return '利好'
    elif neg_count > pos_count:
        return '利空'
    else:
        return '中性'


def _has_clear_signal(text):
    """判断是否有明确的信号词"""
    clear_signals = ['发布', '启动', '开幕', '获批', '利好', '政策', '大会', '会议']
    return any(s in text for s in clear_signals)


def analyze_event_sector(event_title, event_summary="", xuangubao_data=None, hot_rank_data=None):
    """AI智能分析事件所属板块
    
    基于事件标题、内容以及选股通、热榜等数据进行智能分析
    """
    # 先检查是否有选股通数据可参考
    if xuangubao_data:
        # 从选股通新闻中查找相关板块
        for news in xuangubao_data.get('xuangubao_news', [])[:20]:  # 检查前20条
            if event_title.lower() in news.get('title', '').lower() or event_title.lower() in news.get('summary', '').lower():
                # 尝试从新闻中提取板块信息
                news_summary = news.get('summary', '')
                # 常见板块关键词
                for sector_keyword in ['绿电', '电力', '半导体', '芯片', '消费电子', '轨交', '铁路', '航天', '卫星', 
                                      'AI', '人工智能', '液冷', '服务器', '算力', '光伏', '储能', '机器人', 
                                      '医药', '医疗', '银行', '金融', '汽车', '通信', '有色', '金属', '煤炭', '农业',
                                      '旅游', '食品', '饮料', '地产', '建筑', '传媒', '教育', '环保', '军工', '化工']:
                    if sector_keyword in news_summary:
                        return sector_keyword
    
    # 如果选股通没有，检查热榜数据中的概念标签
    if hot_rank_data:
        for stock in hot_rank_data[:10]:
            concepts = stock.get('concepts', [])
            if concepts:
                # 检查事件标题是否包含这些概念
                for concept in concepts:
                    if concept in event_title:
                        return concept
    
    # 最后基于标题关键词智能判断（2026年4月最新板块方向）
    title_lower = event_title.lower()
    
    # 1. AI产业链（AI应用、短剧、大模型）
    if any(keyword in title_lower for keyword in ['AI应用', '人工智能应用', '短剧', 'AIGC', '生成式AI', 'ChatGPT', '大模型', '文生视频', '多模态']):
        return 'AI应用'
    
    # 2. AI算力产业链（算力、液冷服务器、AI芯片）
    if any(keyword in title_lower for keyword in ['算力', '计算', '云计算', '数据中心', '服务器', '液冷', 'AI芯片', '智算中心']):
        return '算力'
    
    # 3. 半导体设备材料（光刻机、光刻胶、玻璃布、PCB）
    if any(keyword in title_lower for keyword in ['光刻机', '光刻胶', '玻璃布', 'PCB', '封装', '测试设备', '半导体材料', '晶圆制造', '先进封装']):
        return '半导体设备材料'
    
    # 4. 绿色电力产业链（核聚变、特高压、电气、风电）
    if any(keyword in title_lower for keyword in ['核聚变', '可控核聚变', '人造太阳', '特高压', '电网设备', '电气设备', '智能电网', '输配电']):
        return '绿色电力'
    
    # 5. 航天军工产业链（商业航天、卫星导航、大飞机）
    if any(keyword in title_lower for keyword in ['航天', '卫星', '火箭', '商业航天', '太空', '飞船', '大飞机', '军工', '北斗', '导弹']):
        return '航天军工'
    
    # 6. 机器人产业链（人形机器人、具身智能）
    if any(keyword in title_lower for keyword in ['人形机器人', '具身智能', '减速器', '伺服电机', '机器人']):
        return '机器人'
    
    # 7. 新能源汽车产业链（无人驾驶、智能驾驶）
    if any(keyword in title_lower for keyword in ['无人驾驶', '自动驾驶', '智能驾驶', '激光雷达', '车载芯片', '新能源车']):
        return '新能源汽车'
    
    # 8. 医药生物产业链（脑机接口）
    if any(keyword in title_lower for keyword in ['脑机接口', '脑科学', '神经接口', '医疗AI', '创新药', 'CXO']):
        return '医药生物'
    
    # 9. 光电产业链
    if any(keyword in title_lower for keyword in ['光电', '光学', '激光', 'LED', '显示面板', '光通信', 'CPO', '光模块']):
        return '光电'
    
    # 10. 消费产业链（旅游、户外、冰雪经济）
    if any(keyword in title_lower for keyword in ['冰雪经济', '户外', '露营', '滑雪', '旅游', '景区', '免税']):
        return '消费'
    
    # 11. 金融产业链（数字金融、稳定币、非银金融）
    if any(keyword in title_lower for keyword in ['数字金融', '稳定币', '数字货币', '非银金融', '支付', '金融科技']):
        return '金融'
    
    # 12. 海峡概念（两岸融合）
    if any(keyword in title_lower for keyword in ['海峡', '两岸', '福建', '台湾', '平潭', '闽台']):
        return '海峡概念'
    
    # 13. 周期资源（有色、稀土、化工）
    if any(keyword in title_lower for keyword in ['有色', '稀土', '稀土永磁', '化工', '化学原料', '新材料']):
        return '周期资源'
    
    # 14. 绿电/新能源相关（光伏、储能、风电）
    if any(keyword in title_lower for keyword in ['绿电', '电力', '电网', '发电', '新能源', '光伏', '风电', '储能', '能源', '碳中和']):
        return '绿电'
    
    # 15. 半导体芯片相关
    if any(keyword in title_lower for keyword in ['半导体', '芯片', '集成电路', '存储芯片', '晶圆']):
        return '半导体'
    
    # 16. 消费电子相关
    if any(keyword in title_lower for keyword in ['消费电子', '苹果', '华为', '小米', '手机', '耳机', '穿戴', '电子']):
        return '消费电子'
    
    # 17. 轨交设备相关
    if any(keyword in title_lower for keyword in ['轨交', '铁路', '高铁', '地铁', '轨道交通', '中车']):
        return '轨交设备'
    
    # 其他常见板块
    if any(keyword in title_lower for keyword in ['医药', '医疗', '生物', '疫苗', '创新药']):
        return '医药'
    
    if any(keyword in title_lower for keyword in ['银行', '金融', '券商', '保险', '证券']):
        return '银行'
    
    if any(keyword in title_lower for keyword in ['汽车', '新能源车', '电动车', '自动驾驶']):
        return '汽车'
    
    # 旅游相关
    if any(keyword in title_lower for keyword in ['旅游', '团队旅游', '出境游', '入境游', '景区', '酒店', '免税', '旅行社', '文旅', '休闲']):
        return '旅游'
    
    # 食品饮料相关
    if any(keyword in title_lower for keyword in ['食品', '饮料', '白酒', '啤酒', '乳业', '调味品', '预制菜', '餐饮']):
        return '食品饮料'
    
    # 房地产相关
    if any(keyword in title_lower for keyword in ['房地产', '地产', '物业', '住房', '楼市', '保障房']):
        return '房地产'
    
    # 建筑建材相关
    if any(keyword in title_lower for keyword in ['建筑', '建材', '水泥', '玻璃', '钢结构', '基建']):
        return '建筑建材'
    
    # 传媒娱乐相关
    if any(keyword in title_lower for keyword in ['传媒', '娱乐', '游戏', '影视', '短视频', '直播', '广告']):
        return '传媒娱乐'
    
    # 教育相关
    if any(keyword in title_lower for keyword in ['教育', '培训', '职业', '学校', '在线教育']):
        return '教育'
    
    # 环保相关
    if any(keyword in title_lower for keyword in ['环保', '环境', '污水处理', '垃圾处理', '碳中和', '碳交易']):
        return '环保'
    
    # 军工相关
    if any(keyword in title_lower for keyword in ['军工', '国防', '武器', '装备', '舰船', '战机']):
        return '军工'
    
    # 化工相关
    if any(keyword in title_lower for keyword in ['化工', '化学', '化纤', '塑料', '橡胶', '农药', '化肥']):
        return '化工'
    
    # 轻工制造相关
    if any(keyword in title_lower for keyword in ['轻工', '造纸', '包装', '家具', '家电', '纺织', '服装']):
        return '轻工制造'
    
    # 电力设备相关
    if any(keyword in title_lower for keyword in ['电力设备', '变压器', '开关', '电缆', '输配电']):
        return '电力设备'
    
    # 通信相关
    if any(keyword in title_lower for keyword in ['通信', '5G', '6G', '光通信', '物联网', '运营商']):
        return '通信'
    
    # 计算机相关
    if any(keyword in title_lower for keyword in ['计算机', '软件', '信创', '网络安全', '大数据', '区块链']):
        return '计算机'
    
    # 如果都无法判断，返回"其他"
    return "其他"


def get_stock_status(stock_name, stock_code, zt_pool, dt_pool, change_pct=None):
    """判断股票的涨停/跌停状态，并显示涨跌幅
    
    Args:
        stock_name: 股票名称
        stock_code: 股票代码
        zt_pool: 涨停池数据
        dt_pool: 跌停池数据
        change_pct: 涨跌幅（可选）
    
    Returns:
        状态字符串："+3.21%"（正常）、"+10.00% 涨停(首板)"（涨停）、"-10.00% 跌停"（跌停）
    """
    # 检查涨停池
    if zt_pool:
        for stock in zt_pool:
            # 精确匹配代码或名称
            if stock.get('代码') == stock_code or stock.get('名称') == stock_name:
                # 返回涨停类型（如"首板"、"2板"等）
                zt_type = stock.get('涨停统计', '')
                if change_pct is not None:
                    if zt_type:
                        return f"{change_pct:+.2f}% 涨停({zt_type})"
                    return f"{change_pct:+.2f}% 涨停"
                else:
                    if zt_type:
                        return f"涨停({zt_type})"
                    return "涨停"
    
    # 检查跌停池
    if dt_pool:
        for stock in dt_pool:
            # 精确匹配代码或名称
            if stock.get('代码') == stock_code or stock.get('名称') == stock_name:
                if change_pct is not None:
                    return f"{change_pct:+.2f}% 跌停"
                return "跌停"
    
    # 正常状态，返回涨跌幅
    if change_pct is not None:
        return f"{change_pct:+.2f}%"
    return "-"
    
    # 如果选股通没有，检查热榜数据中的概念标签
    if hot_rank_data:
        for stock in hot_rank_data[:10]:
            concepts = stock.get('concepts', [])
            if concepts:
                # 检查事件标题是否包含这些概念
                for concept in concepts:
                    if concept in event_title:
                        return concept
    
    # 最后基于标题关键词智能判断
    title_lower = event_title.lower()
    
    # 绿电/新能源相关（绿色经济、碳中和、清洁能源）
    if any(keyword in title_lower for keyword in ['绿电', '电力', '电网', '发电', '新能源', '光伏', '风电', '储能', '特高压', '能源', '绿色经济', '清洁能源', '碳中和', '碳达峰']):
        return '绿电'
    
    # 半导体芯片相关
    if any(keyword in title_lower for keyword in ['半导体', '芯片', '集成电路', '光刻胶', '存储芯片', '晶圆']):
        return '半导体'
    
    # 消费电子相关
    if any(keyword in title_lower for keyword in ['消费电子', '苹果', '华为', '小米', '手机', '耳机', '穿戴', '电子']):
        return '消费电子'
    
    # 轨交设备相关
    if any(keyword in title_lower for keyword in ['轨交', '铁路', '高铁', '地铁', '轨道交通', '中车']):
        return '轨交设备'
    
    # 商业航天相关
    if any(keyword in title_lower for keyword in ['航天', '卫星', '火箭', '商业航天', '太空', '飞船']):
        return '商业航天'
    
    # AI相关
    if any(keyword in title_lower for keyword in ['AI', '人工智能', '大模型', '智能', '算法', '机器学习']):
        return 'AI应用'
    
    # 算力相关
    if any(keyword in title_lower for keyword in ['算力', '计算', '云计算', '数据中心', '服务器', '液冷']):
        return '算力'
    
    # 光伏储能相关
    if any(keyword in title_lower for keyword in ['光伏', '储能', '电池', '锂电', '新能源车', '电动车']):
        return '光伏储能'
    
    # 人形机器人相关
    if any(keyword in title_lower for keyword in ['机器人', '人形', '自动化', '智能制造']):
        return '人形机器人'
    
    # 其他常见板块
    if any(keyword in title_lower for keyword in ['医药', '医疗', '生物', '疫苗', '创新药']):
        return '医药'
    
    if any(keyword in title_lower for keyword in ['银行', '金融', '券商', '保险', '证券']):
        return '银行'
    
    if any(keyword in title_lower for keyword in ['汽车', '新能源车', '电动车', '自动驾驶']):
        return '汽车'
    
    # 旅游相关
    if any(keyword in title_lower for keyword in ['旅游', '团队旅游', '出境游', '入境游', '景区', '酒店', '免税', '旅行社', '文旅', '休闲']):
        return '旅游'
    
    # 食品饮料相关
    if any(keyword in title_lower for keyword in ['食品', '饮料', '白酒', '啤酒', '乳业', '调味品', '预制菜', '餐饮']):
        return '食品饮料'
    
    # 房地产相关
    if any(keyword in title_lower for keyword in ['房地产', '地产', '物业', '住房', '楼市', '保障房']):
        return '房地产'
    
    # 建筑建材相关
    if any(keyword in title_lower for keyword in ['建筑', '建材', '水泥', '玻璃', '钢结构', '基建']):
        return '建筑建材'
    
    # 传媒娱乐相关
    if any(keyword in title_lower for keyword in ['传媒', '娱乐', '游戏', '影视', '短视频', '直播', '广告']):
        return '传媒娱乐'
    
    # 教育相关
    if any(keyword in title_lower for keyword in ['教育', '培训', '职业', '学校', '在线教育']):
        return '教育'
    
    # 环保相关
    if any(keyword in title_lower for keyword in ['环保', '环境', '污水处理', '垃圾处理', '碳中和', '碳交易']):
        return '环保'
    
    # 军工相关
    if any(keyword in title_lower for keyword in ['军工', '国防', '武器', '装备', '舰船', '战机']):
        return '军工'
    
    # 化工相关
    if any(keyword in title_lower for keyword in ['化工', '化学', '化纤', '塑料', '橡胶', '农药', '化肥']):
        return '化工'
    
    # 轻工制造相关
    if any(keyword in title_lower for keyword in ['轻工', '造纸', '包装', '家具', '家电', '纺织', '服装']):
        return '轻工制造'
    
    # 电力设备相关
    if any(keyword in title_lower for keyword in ['电力设备', '变压器', '开关', '电缆', '输配电']):
        return '电力设备'
    
    # 通信相关
    if any(keyword in title_lower for keyword in ['通信', '5G', '6G', '光通信', '物联网', '运营商']):
        return '通信'
    
    # 计算机相关
    if any(keyword in title_lower for keyword in ['计算机', '软件', '信创', '网络安全', '大数据', '区块链']):
        return '计算机'
    
    # 如果都无法判断，返回"其他"
    return "其他"


def analyze_market_and_sectors(data):
    """市场与板块智能分析（狙击手视角之前）
    
    基于所有数据源进行综合分析：
    1. 资金流向分析
    2. 板块强度分析
    3. 主线识别
    4. 风险识别
    """
    analysis = {
        'market_status': '',
        'main_sectors': [],
        'secondary_sectors': [],
        'risk_sectors': [],
        'sector_analysis': {},
        'unified_sector_rows': [],
    }
    
    # 1. 市场整体状态判断
    if data.get('indices'):
        sh_change = data['indices'].get('上证指数', {}).get('涨跌幅', 0)
        sz_change = data['indices'].get('深证成指', {}).get('涨跌幅', 0)
        cy_change = data['indices'].get('创业板指', {}).get('涨跌幅', 0)
        
        # 判断市场整体状态
        if sh_change > 1.0 and sz_change > 1.0:
            analysis['market_status'] = '强势上涨'
        elif sh_change > 0.5 or sz_change > 0.5:
            analysis['market_status'] = '小幅上涨'
        elif sh_change < -1.0 and sz_change < -1.0:
            analysis['market_status'] = '大幅下跌'
        elif sh_change < -0.5 or sz_change < -0.5:
            analysis['market_status'] = '小幅下跌'
        else:
            analysis['market_status'] = '震荡整理'
    
    # 2. 主线板块识别（统一主线评分引擎）
    # 不再是“涨停潮空了就看资金、资金空了再看热度”的回退链，
    # 而是把涨停广度、资金、热榜、板块热度、击球区质量放到同一张分数表里。
    unified_sector_rows = _build_unified_sector_strength_rows(data)
    analysis['unified_sector_rows'] = unified_sector_rows[:12]
    analysis['sector_analysis'] = {
        row.get('name', ''): row
        for row in unified_sector_rows
        if row.get('name')
    }

    main_rows = [row for row in unified_sector_rows if row.get('role') == 'main']
    secondary_rows = [row for row in unified_sector_rows if row.get('role') == 'secondary']

    if not main_rows and unified_sector_rows:
        top_row = unified_sector_rows[0]
        if top_row.get('unified_score', 0) >= 35 or top_row.get('hot_plate_rank'):
            forced_row = dict(top_row)
            forced_row['role'] = 'main'
            main_rows = [forced_row]
            secondary_rows = [row for row in unified_sector_rows[1:] if row.get('unified_score', 0) >= 28][:4]

    analysis['main_sectors'] = [dict(item) for item in main_rows[:5]]
    analysis['secondary_sectors'] = [dict(item) for item in secondary_rows[:5]]
    
    # 识别风险板块（净流出多且跌幅大）
    if data.get('sector_fund_flow'):
        outflow = data['sector_fund_flow'].get('outflow', [])
        for sector in outflow[:10]:
            name = sector.get('name', '')
            zljlr = abs(sector.get('zljlr', 0))  # 净流出绝对值
            zdf = sector.get('zdf', 0)           # 涨跌幅（通常为负）
            
            # 风险标准：净流出>10亿或跌幅>3%
            if zljlr > 10 or zdf < -3:
                analysis['risk_sectors'].append({
                    'name': name,
                    'net_outflow': zljlr,
                    'change': zdf,
                    'risk_level': 'high' if zljlr > 20 or zdf < -5 else 'medium'
                })
    
    # 4. 热榜数据分析（市场关注度）
    if data.get('hot_rank_top30'):
        hot_sectors = {}
        for stock in data['hot_rank_top30'][:10]:
            concepts = stock.get('concepts', [])
            for concept in concepts[:2]:  # 取前两个概念
                if concept not in hot_sectors:
                    hot_sectors[concept] = 0
                hot_sectors[concept] += 1
        
        # 热榜关注度高的板块
        analysis['hot_sectors'] = sorted(hot_sectors.items(), key=lambda x: x[1], reverse=True)[:5]
    
    return analysis


def _build_dragon_stocks_from_zt_pool(data):
    dragon_stocks = []
    for zt in (data or {}).get('zt_pool', []) or []:
        code = zt.get('代码', zt.get('code', ''))
        name = zt.get('名称', zt.get('name', ''))
        lianban = int(_safe_float(zt.get('连板数', zt.get('lianban', 0))) or 0)
        if lianban >= 2:
            dragon_stocks.append({
                'code': normalize_stock_code(code),
                'name': name,
                'sector': zt.get('所属板块', zt.get('sector', '')),
                'lianban': lianban,
            })
    dragon_stocks.sort(key=lambda x: x.get('lianban', 0), reverse=True)
    return dragon_stocks


def _resolve_market_mainline_context(data, market_analysis):
    market_analysis = market_analysis or {}
    main_sectors_info = [dict(item) for item in (market_analysis.get('main_sectors', []) or [])]
    secondary_sectors_info = [dict(item) for item in (market_analysis.get('secondary_sectors', []) or [])]
    unified_rows = market_analysis.get('unified_sector_rows', []) or []

    if not main_sectors_info and unified_rows:
        top_row = unified_rows[0]
        if top_row.get('unified_score', 0) >= 35 or top_row.get('hot_plate_rank'):
            forced_main = dict(top_row)
            forced_main['role'] = 'main'
            main_sectors_info = [forced_main]
        if len(unified_rows) > 1:
            secondary_sectors_info = [dict(item) for item in unified_rows[1:4]]

    main_sectors = [item.get('name', '') for item in main_sectors_info if item.get('name')][:3]
    secondary_sectors = [item.get('name', '') for item in secondary_sectors_info if item.get('name')][:3]
    dragon_stocks = _build_dragon_stocks_from_zt_pool(data)

    return {
        'main_sectors_info': main_sectors_info,
        'secondary_sectors_info': secondary_sectors_info,
        'main_sectors': main_sectors,
        'secondary_sectors': secondary_sectors,
        'dragon_stocks': dragon_stocks,
    }


def ai_group_concepts_into_chains(concepts_list):
    """AI归纳：将概念板块归纳为产业链（使用内置LLM智能分析）
    
    不再使用硬编码规则，而是调用ai_analyze_sector_relationships进行真正的智能分析。
    
    Args:
        concepts_list: 概念板块列表，如 ['商业航天', '卫星导航', '大飞机', '超超临界发电', '绿色电力']
    
    Returns:
        dict: {产业链名称: [所属概念列表]}
    
    示例：
        输入: ['商业航天', '卫星导航', '大飞机', '超超临界发电', '绿色电力']
        输出: {
            '航天军工产业链': ['商业航天', '卫星导航', '大飞机'],
            '绿色电力产业链': ['超超临界发电', '绿色电力']
        }
    """
    if not concepts_list:
        return {}

    # MVP模式优先走本地归链，避免前台已经不展示的昂贵LLM调用拖慢整份日报写盘。
    if DISPLAY_MVP_MODE:
        ai_result = _llm_sector_analysis(concepts_list, "MVP模式使用本地归链")
    else:
        ai_result = ai_analyze_sector_relationships(concepts_list)
        if not ai_result.get('groups'):
            ai_result = _llm_sector_analysis(concepts_list, "LLM失败后回退本地归链")
    
    # 转换为原函数返回格式
    chains = {}
    for group in ai_result.get('groups', []):
        chain_name = group['name']
        sectors = group['sectors']
        chains[chain_name] = sectors
    
    return chains


# 个股行业信息缓存
_stock_industry_cache = {}
_gem_stock_universe_cache = None

def get_stock_sector(stock_name, stock_code, hot_rank_data=None, zt_pool_data=None, lianban_data=None, lhb_data=None, sector_fund_flow=None, zt_pool_raw=None, dt_pool_raw=None, skip_api_call=False):
    """获取股票所属板块（从真实数据源获取，不用猜测）
    
    数据源优先级（必须返回真实板块，不猜测）：
    1. 涨停池原始数据（zt_pool列表）- 最优先，因为包含真实的所属行业
    2. 跌停池原始数据（dt_pool列表）- 第二优先
    3. 热榜数据概念标签（实时热榜）
    4. 涨停池数据板块分布（涨停股板块字典）
    5. 连板梯队数据板块标签（连板股板块）
    6. 龙虎榜数据板块信息（龙虎榜个股）
    7. 板块资金流向领涨股（板块领涨股）
    8. 东方财富CompanySurvey接口（个股所属行业）- 可通过skip_api_call禁用
    9. 如果以上都找不到 → 返回"未知"（不猜测）
    
    Args:
        zt_pool_raw: 涨停池原始数据（列表格式，包含'所属行业'字段）
        dt_pool_raw: 跌停池原始数据（列表格式，包含'所属行业'字段）
        skip_api_call: 是否跳过API调用（避免在批量处理时卡死）
    """

    # 1. 从涨停池原始数据查找板块（最优先，因为包含真实的所属行业）
    if zt_pool_raw:
        for stock in zt_pool_raw:
            if stock.get('代码') == stock_code or stock.get('名称') == stock_name:
                sector = stock.get('所属行业', '')
                if sector and sector != '未知':
                    return sector
    
    # 2. 从跌停池原始数据查找板块
    if dt_pool_raw:
        for stock in dt_pool_raw:
            if stock.get('代码') == stock_code or stock.get('名称') == stock_name:
                sector = stock.get('所属行业', '')
                if sector and sector != '未知':
                    return sector
    
    # 3. 从热榜数据中查找概念标签
    if hot_rank_data:
        for stock in hot_rank_data:
            if stock.get('code') == stock_code or stock.get('name') == stock_name:
                concepts = stock.get('concepts', [])
                if concepts:
                    return concepts[0]
    
    # 4. 从涨停池数据字典中查找板块分布
    if zt_pool_data:
        for sector_name, stocks in zt_pool_data.items():
            for stock in stocks:
                if stock.get('code') == stock_code or stock.get('name') == stock_name:
                    return sector_name
    
    # 5. 从连板梯队数据中查找板块标签
    if lianban_data:
        for stock in lianban_data:
            if stock.get('code') == stock_code or stock.get('name') == stock_name:
                plates = stock.get('plates', [])
                if plates:
                    return plates[0]
                # 从涨停原因中精确提取板块（不猜测，只提取明确提到的）
                reason = stock.get('reason', '')
                if reason:
                    # 只提取明确包含"概念"、"板块"等关键词的
                    if '概念' in reason:
                        # 提取"XX概念"格式的
                        import re
                        match = re.search(r'(\S+?概念)', reason)
                        if match:
                            return match.group(1)
    
    # 6. 从龙虎榜数据中查找板块信息
    if lhb_data:
        for stock in lhb_data:
            if stock.get('code') == stock_code or stock.get('name') == stock_name:
                sector = stock.get('sector', '')
                if sector and sector != '未知':
                    return sector
    
    # 7. 从板块资金流向领涨股中查找
    if sector_fund_flow:
        for flow in sector_fund_flow.get('inflow', []):
            leading_stock = flow.get('leading_stock', '')
            if stock_name in leading_stock or stock_code in leading_stock:
                return flow.get('name', '')
    
    # 6. 从东方财富获取个股所属行业（添加缓存）
    # 如果skip_api_call=True，跳过API调用（避免批量处理时卡死）
    if not skip_api_call:
        global _stock_industry_cache
        cache_key = stock_code if stock_code else stock_name
        
        if cache_key in _stock_industry_cache:
            return _stock_industry_cache[cache_key]
        
        # 尝试从东方财富获取个股所属行业
        try:
            import requests
            
            # 提取股票代码（去掉市场前缀）
            pure_code = stock_code.replace('sz', '').replace('sh', '').replace('SZ', '').replace('SH', '') if stock_code else ''
            
            if pure_code:
                # 市场代码判断（支持沪深北交所）
                if pure_code.startswith('0') or pure_code.startswith('3'):
                    market = 'SZ'  # 深市：0主板、3创业板
                elif pure_code.startswith('6'):
                    market = 'SH'  # 沪市主板
                elif pure_code.startswith('68'):
                    market = 'SH'  # 科创板
                elif pure_code.startswith('8') or pure_code.startswith('9'):
                    market = 'BJ'  # 北交所：8开头或92开头
                else:
                    market = 'SH'  # 默认沪市
                full_code = f"{market}{pure_code}"
                
                # 东方财富CompanySurvey接口
                url = 'https://emweb.eastmoney.com/PC_HSF10/CompanySurvey/CompanySurveyAjax'
                params = {'code': full_code}
                
                resp = requests.get(url, params=params, timeout=5)
                data = resp.json()
                
                if data.get('jbzl'):
                    # sshy: 所属行业
                    industry = data['jbzl'].get('sshy', '')
                    if industry:
                        _stock_industry_cache[cache_key] = industry
                        return industry
        except Exception as e:
            # 获取失败，不报错，继续返回"未知"
            pass
    
    # 如果以上都找不到，返回"未知"，不猜测
    # AI归纳应该在更高层做，不在个股级别猜测
    return "未知"


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


def _extract_sector_signed_flow(snapshot_data, sector_name):
    if not snapshot_data or not sector_name:
        return None

    sector_fund_flow = snapshot_data.get('sector_fund_flow', {}) or {}
    inflow_sectors = sector_fund_flow.get('inflow', []) if sector_fund_flow else []
    outflow_sectors = sector_fund_flow.get('outflow', []) if sector_fund_flow else []

    for item in inflow_sectors:
        name = item.get('name', '')
        if sector_name_matches(name, sector_name):
            return abs(_safe_float(item.get('zljlr', 0.0)))

    for item in outflow_sectors:
        name = item.get('name', '')
        if sector_name_matches(name, sector_name):
            return -abs(_safe_float(item.get('zljlr', 0.0)))

    return 0.0


def load_recent_sector_flow_history(target_date, sector_name, lookback_days=2, max_scan_days=8):
    """从本地快照加载主线近几日资金流向，用于连续评分，而不是只看单日阈值。"""
    history = []
    cursor = _normalize_kline_date_str(target_date)
    scanned_days = 0

    while cursor and len(history) < lookback_days and scanned_days < max_scan_days:
        cursor = get_previous_date_str(cursor)
        if not cursor:
            break
        scanned_days += 1
        snapshot_data, _ = load_data_snapshot(cursor)
        if not snapshot_data:
            continue

        flow_value = _extract_sector_signed_flow(snapshot_data, sector_name)
        if flow_value is None:
            continue
        history.append({
            'date': cursor,
            'inflow': round(_safe_float(flow_value), 2),
        })

    history.reverse()
    return history


def load_recent_market_turnover_history(target_date, lookback_days=2, max_scan_days=8):
    """从本地快照加载近几日两市成交额，用于判断是偏趋势还是偏投机。"""
    history = []
    cursor = _normalize_kline_date_str(target_date)
    scanned_days = 0

    while cursor and len(history) < lookback_days and scanned_days < max_scan_days:
        cursor = get_previous_date_str(cursor)
        if not cursor:
            break
        scanned_days += 1
        snapshot_data, _ = load_data_snapshot(cursor)
        if not snapshot_data:
            continue

        turnover = _safe_float(snapshot_data.get('total_turnover'))
        if turnover <= 0:
            continue
        history.append({
            'date': cursor,
            'turnover': round(turnover, 2),
        })

    history.reverse()
    return history


def _extract_market_breadth_snapshot(data):
    market_stats = data.get('market_stats', {}) or {}
    raw_up_count = market_stats.get('up_count')
    raw_down_count = market_stats.get('down_count')

    up_count = int(_safe_float(raw_up_count)) if raw_up_count not in (None, '') else 0
    down_count = int(_safe_float(raw_down_count)) if raw_down_count not in (None, '') else 0
    breadth_available = bool(market_stats) and (up_count > 0 or down_count > 0)

    rise_fall_ratio = None
    if breadth_available:
        if down_count > 0:
            rise_fall_ratio = up_count / down_count
        elif up_count > 0:
            rise_fall_ratio = float(up_count)
        else:
            rise_fall_ratio = 0.0

    rise_fall_ratio_text = f"{rise_fall_ratio:.2f}" if rise_fall_ratio is not None else "暂无"
    up_down_text = f"{up_count}:{down_count}" if breadth_available else "暂无"

    return {
        'up_count': up_count,
        'down_count': down_count,
        'breadth_available': breadth_available,
        'rise_fall_ratio': round(rise_fall_ratio, 4) if rise_fall_ratio is not None else None,
        'rise_fall_ratio_text': rise_fall_ratio_text,
        'up_down_text': up_down_text,
    }


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


def _count_keyword_hits_in_items(items, keywords, fields):
    normalized_keywords = [str(keyword or '').upper() for keyword in (keywords or []) if keyword]
    if not normalized_keywords:
        return 0

    seen = set()
    total = 0
    for item in items or []:
        if isinstance(item, dict):
            code = normalize_stock_code(
                item.get('code', item.get('代码', item.get('stock_code', '')))
            )
            name = str(item.get('name', item.get('名称', '')) or '').strip()
            unique_key = code or name.upper()
            texts = []
            for field in fields:
                value = item.get(field)
                if isinstance(value, (list, tuple, set)):
                    texts.extend([str(entry or '') for entry in value])
                elif value not in (None, ''):
                    texts.append(str(value))
        else:
            unique_key = str(item or '').strip().upper()
            texts = [str(item or '')]

        if not unique_key or unique_key in seen:
            continue
        seen.add(unique_key)

        joined_text = " ".join(texts).upper()
        if any(keyword in joined_text for keyword in normalized_keywords):
            total += 1
    return total


def _build_market_style_switch_snapshot(target_date, data, observation_snapshot=None, abnormal_projection=None):
    observation_snapshot = observation_snapshot or {}
    abnormal_projection = abnormal_projection or {}

    current_turnover = _safe_float(data.get('total_turnover'))
    turnover_history = load_recent_market_turnover_history(target_date, lookback_days=2, max_scan_days=8)
    turnover_series = list(turnover_history)
    if current_turnover > 0:
        turnover_series.append({
            'date': _normalize_kline_date_str(target_date),
            'turnover': round(current_turnover, 2),
        })

    prev_turnover = _safe_float(turnover_history[-1].get('turnover')) if turnover_history else 0.0
    prev2_turnover = _safe_float(turnover_history[-2].get('turnover')) if len(turnover_history) >= 2 else 0.0
    turnover_delta_pct = (current_turnover / prev_turnover - 1.0) if current_turnover > 0 and prev_turnover > 0 else None

    turnover_state = 'unknown'
    turnover_label = '量能历史不足'
    if current_turnover > 0 and prev_turnover > 0:
        if prev2_turnover > 0 and current_turnover < prev_turnover * 0.97 and prev_turnover < prev2_turnover * 0.97:
            turnover_state = 'shrinking'
            turnover_label = '成交额连续回落'
        elif prev2_turnover > 0 and current_turnover > prev_turnover * 1.03 and prev_turnover >= prev2_turnover * 0.98:
            turnover_state = 'rising'
            turnover_label = '成交额继续回升'
        elif current_turnover < prev_turnover * 0.97:
            turnover_state = 'pullback'
            turnover_label = '成交额冲高后回落'
        elif current_turnover > prev_turnover * 1.03:
            turnover_state = 'rebound'
            turnover_label = '成交额重新放大'
        else:
            turnover_state = 'flat'
            turnover_label = '成交额横向波动'

    status_distribution = data.get('status_distribution', {}) or {}
    tag_distribution = data.get('tag_distribution', {}) or {}
    high_board_count = sum(
        int(_safe_float(count))
        for label, count in status_distribution.items()
        if _parse_status_board_count(label) >= 3
    )
    subnew_tag_count = max(
        _count_keyword_hits_in_mapping(tag_distribution, ['次新']),
        _count_keyword_hits_in_items(
            data.get('integrated_hot_list', []) or [],
            ['次新'],
            fields=['all_tags', 'sector_tags', 'status_tags', 'sector'],
        ),
    )
    reorg_tag_count = max(
        _count_keyword_hits_in_mapping(tag_distribution, ['重组', '并购', '借壳']),
        _count_keyword_hits_in_items(
            data.get('integrated_hot_list', []) or [],
            ['重组', '并购', '借壳'],
            fields=['all_tags', 'sector_tags', 'status_tags', 'sector'],
        ),
    )
    st_stock_count = _count_keyword_hits_in_items(
        (data.get('zt_pool', []) or []) + (data.get('hot_rank_top30', []) or []) + (data.get('integrated_hot_list', []) or []),
        ['ST'],
        fields=['name', '名称'],
    )

    resilient_count = int(_safe_float(observation_snapshot.get('resilient_abnormal_count', 0)))
    failed_count = int(_safe_float(observation_snapshot.get('failed_abnormal_count', 0)))
    trend_density_count = int(_safe_float(observation_snapshot.get('densest_sector_trend_count', 0)))
    leader_memory_count = int(_safe_float(observation_snapshot.get('leader_memory_count', 0)))
    trusted_tracking_count = int(_safe_float(observation_snapshot.get('trusted_tracking_count', 0)))

    trend_signal_count = 0
    trend_evidence = []
    if resilient_count >= 2:
        trend_signal_count += 1
        trend_evidence.append(f"异常承接{resilient_count}强/{failed_count}弱")
    if trend_density_count >= 2:
        trend_signal_count += 1
        trend_evidence.append(
            f"{observation_snapshot.get('densest_sector', '最强方向')}有{trend_density_count}只活跃趋势股"
        )
    if leader_memory_count >= 3:
        trend_signal_count += 1
        trend_evidence.append(f"龙头记忆保留{leader_memory_count}只")
    if trusted_tracking_count >= 1:
        trend_signal_count += 1
        trend_evidence.append(f"可信跟踪记录{trusted_tracking_count}只")

    speculative_signal_count = 0
    speculative_evidence = []
    if high_board_count >= 3:
        speculative_signal_count += 1
        speculative_evidence.append(f"3板及以上{high_board_count}只")
    if subnew_tag_count > 0:
        speculative_signal_count += 1
        speculative_evidence.append(f"次新热度{int(subnew_tag_count)}")
    if reorg_tag_count > 0:
        speculative_signal_count += 1
        speculative_evidence.append(f"重组热度{int(reorg_tag_count)}")
    if st_stock_count > 0:
        speculative_signal_count += 1
        speculative_evidence.append(f"ST活跃{int(st_stock_count)}只")

    if turnover_state in ('rising', 'rebound') and trend_signal_count >= max(2, speculative_signal_count):
        style_code = 'trend'
        style_label = '趋势分歧优先'
        style_reason = (
            f"{turnover_label}，而异常承接和趋势密度都还在，明天更适合等主线趋势分歧，不适合抢纯情绪一致加速。"
        )
        primary_action = "优先做主线趋势股的分歧承接，宁可慢一点，也不抢一致高潮。"
        switch_action = "若首小时量能明显回落，再把关注重心降到高辨识投机先手。"
    elif turnover_state == 'shrinking' and speculative_signal_count >= max(2, trend_signal_count):
        style_code = 'speculation'
        style_label = '投机先手优先'
        style_reason = (
            f"{turnover_label}，情绪端更适合快进快出，明天重点看高辨识投机先手，不接受买后磨蹭。"
        )
        primary_action = "优先做高辨识投机先手，买后不爆发就撤，不把仓位耗在磨蹭票上。"
        switch_action = "若首小时量能重新放大且主线承接更集中，再切回趋势分歧。"
    else:
        style_code = 'dual'
        style_label = '双轨准备'
        style_reason = (
            f"{turnover_label}，但趋势承接没有塌，连板/次新等情绪端也在冒头，明天需要先看量能再决定跟哪一侧。"
        )
        primary_action = "两手准备：量缩偏投机先手，量增回主线趋势分歧。"
        switch_action = "开盘先看首小时量能和主线承接，谁更强，就把执行权给谁。"

    turnover_series_text = " -> ".join(
        f"{item.get('date', '')}:{_safe_float(item.get('turnover')):.0f}亿"
        for item in turnover_series
        if _safe_float(item.get('turnover')) > 0
    ) or "暂无量能序列"

    evidence_parts = [turnover_series_text]
    if trend_evidence:
        evidence_parts.append(trend_evidence[0])
    if speculative_evidence:
        evidence_parts.append(speculative_evidence[0])

    return {
        'style_code': style_code,
        'style_label': style_label,
        'style_reason': style_reason,
        'primary_action': primary_action,
        'switch_action': switch_action,
        'turnover_state': turnover_state,
        'turnover_label': turnover_label,
        'turnover_series': turnover_series,
        'turnover_series_text': turnover_series_text,
        'turnover_delta_pct': _round_or_none(turnover_delta_pct, 4),
        'trend_signal_count': trend_signal_count,
        'trend_evidence': trend_evidence[:4],
        'speculative_signal_count': speculative_signal_count,
        'speculative_evidence': speculative_evidence[:4],
        'high_board_count': high_board_count,
        'subnew_tag_count': int(subnew_tag_count),
        'reorg_tag_count': int(reorg_tag_count),
        'st_stock_count': int(st_stock_count),
        'projection_label': abnormal_projection.get('projection_label', ''),
        'evidence_text': "；".join([part for part in evidence_parts if part]),
    }


def get_mainline_star_level(net_inflow, zt_count, dt_count=0, hot_weight=0.0, inflow_history=None):
    """根据资金、涨停/跌停、热度和资金连续性生成主线连续评分。"""
    inflow_history = inflow_history or []
    flow_values = [
        _safe_float(item.get('inflow'))
        for item in inflow_history
        if item.get('inflow') is not None
    ]

    inflow_score = _clamp((net_inflow + 3.0) / 15.0 * 100.0, 0.0, 100.0)
    zt_score = _clamp(zt_count / 12.0 * 100.0, 0.0, 100.0)
    breadth_score = _clamp((zt_count - dt_count + 3.0) / 12.0 * 100.0, 0.0, 100.0)
    hot_score = _clamp(hot_weight / 8.0 * 100.0, 0.0, 100.0)

    trend_score = 50.0
    trend_label = '无历史流向对照'
    flow_trend = 'unknown'
    if flow_values:
        last_value = flow_values[-1]
        deltas = [net_inflow - last_value]
        if len(flow_values) >= 2:
            deltas.append(flow_values[-1] - flow_values[-2])
        avg_delta = sum(deltas) / len(deltas)
        trend_score = _clamp(50.0 + avg_delta * 4.0, 0.0, 100.0)

        if len(flow_values) >= 2 and net_inflow < flow_values[-1] < flow_values[-2]:
            flow_trend = 'shrinking'
            trend_label = (
                f"资金连续收缩（{flow_values[-2]:+.1f}亿→{flow_values[-1]:+.1f}亿→{net_inflow:+.1f}亿）"
            )
        elif net_inflow > last_value:
            flow_trend = 'improving'
            trend_label = f"资金回流增强（{last_value:+.1f}亿→{net_inflow:+.1f}亿）"
        elif net_inflow < last_value:
            flow_trend = 'weakening'
            trend_label = f"资金略有回落（{last_value:+.1f}亿→{net_inflow:+.1f}亿）"
        else:
            flow_trend = 'flat'
            trend_label = f"资金持平（{net_inflow:+.1f}亿）"

    score_pct = (
        inflow_score * 0.36
        + zt_score * 0.24
        + breadth_score * 0.18
        + hot_score * 0.12
        + trend_score * 0.10
    )
    if net_inflow <= 0 and zt_count < 5:
        score_pct -= 6.0
    if dt_count >= 3:
        score_pct -= 8.0
    score_pct = _clamp(score_pct, 0.0, 100.0)

    star_rank = _score_to_star_rank(score_pct)
    return {
        'star_level': '⭐' * star_rank,
        'star_rank': star_rank,
        'score_pct': round(score_pct, 1),
        'trend_label': trend_label,
        'flow_trend': flow_trend,
        'component_scores': {
            '资金': round(inflow_score, 1),
            '涨停广度': round(zt_score, 1),
            '涨跌停结构': round(breadth_score, 1),
            '热度': round(hot_score, 1),
            '连续性': round(trend_score, 1),
        },
    }


def get_sector_hotlist_weight(sector_name, tag_distribution):
    """获取板块在热榜中的占比
    
    支持概念标签到板块名称的映射，例如：
    - 通信设备 <- 光纤概念、CPO、5G、6G概念
    - 医药医疗 <- 创新药、仿制药、生物制品
    - AI算力 <- 算力租赁、光模块、CPO
    """
    if not sector_name or not tag_distribution:
        return 0
    total_tags = sum(tag_distribution.values())
    if total_tags <= 0:
        return 0
    
    # 直接匹配
    if sector_name in tag_distribution:
        return tag_distribution[sector_name] / total_tags * 100
    
    # 概念标签到板块名称的映射
    sector_to_concepts = {
        '通信设备': ['光纤概念', '共封装光学', 'CPO', 'F5G概念', '5G', '6G概念', '光模块', '光通信', '通信', '高速光互联'],
        '医药医疗': ['创新药', '仿制药', '生物制品', '中药', '化学制药', '医疗器械', 'CRO', 'CXO', '医疗服务', '重组蛋白'],
        'AI算力': ['算力租赁', '光模块', 'CPO', '液冷服务器', 'AI芯片', '智算中心', '数据中心', '云计算', '东数西算'],
        '人形机器人': ['减速器', '伺服系统', '传感器', '执行器', '灵巧手', '谐波减速器', 'RV减速器'],
        '新能源': ['光伏', '储能', '锂电池', '固态电池', '钠离子电池', 'TOPCON电池', '钙钛矿电池', 'HJT电池', '风电', '氢能源'],
        '半导体': ['存储芯片', '先进封装', 'Chiplet', '光刻胶', '光刻机', '半导体设备', 'EDA', '三代半导'],
        '汽车产业链': ['汽车零部件', '智能驾驶', '激光雷达', '毫米波雷达', '车载芯片', '一体化压铸', '热管理'],
        '消费电子': ['MR', 'AR', 'VR', '折叠屏', '面板', 'OLED', 'MiniLED', '手机产业链'],
        '商业航天': ['卫星互联网', '火箭发射', '卫星导航', '北斗', '遥感', '星链'],
        '周期资源': ['有色金属', '稀土', '贵金属', '黄金', '铜', '铝', '锂', '钴', '镍', '化工'],
        '金融': ['券商', '银行', '保险', '数字货币', '金融科技', '跨境支付', '稳定币'],
        '消费': ['白酒', '免税', '旅游', '酒店', '食品饮料', '家电', '零售'],
        '房地产': ['房地产开发', '物业管理', '建材', '家居', '基建'],
        '军工': ['航空装备', '航天装备', '船舶', '军工电子', '无人机'],
    }
    
    # 获取该板块对应的概念标签
    related_concepts = sector_to_concepts.get(sector_name, [])
    
    # 累计所有相关概念标签的权重
    total_weight = 0
    matched_tags = []
    for tag, count in tag_distribution.items():
        # 直接包含关系
        if sector_name in tag or tag in sector_name:
            total_weight += count
            matched_tags.append(tag)
            continue
        # 通过概念映射匹配
        for concept in related_concepts:
            if concept in tag or tag in concept:
                total_weight += count
                matched_tags.append(tag)
                break
    
    if total_weight > 0:
        return total_weight / total_tags * 100
    
    return 0


def _get_or_create_sector_bucket(sector_buckets, sector_name):
    sector_name = str(sector_name or '').strip()
    if not sector_name:
        return None

    for bucket in sector_buckets:
        if sector_name_matches(bucket.get('name', ''), sector_name):
            aliases = bucket.setdefault('aliases', set())
            aliases.add(sector_name)
            current_name = bucket.get('name', '')
            if '(分散型)' in current_name and '(分散型)' not in sector_name:
                bucket['name'] = sector_name
            elif sector_name and len(sector_name) < len(current_name or sector_name):
                bucket['name'] = sector_name
            return bucket

    bucket = {
        'name': sector_name,
        'aliases': {sector_name},
        'zt_count': 0,
        'dt_count': 0,
        'dragon_count': 0,
        'net_inflow': 0.0,
        'change': 0.0,
        'hot_plate_rank': None,
        'hot_plate_heat': 0.0,
        'hot_weight': 0.0,
        'hot_stock_count': 0,
        'quadrant_quality_score': 0.0,
        'quadrant_label': '',
        'quadrant_position': None,
        'quadrant_recent_change': None,
    }
    sector_buckets.append(bucket)
    return bucket


def _match_sector_quadrant_snapshot(sector_name, sector_quadrant):
    if not sector_name or not sector_quadrant:
        return {}

    hs_analysis = (sector_quadrant.get('high_strong_analysis') or {}) if isinstance(sector_quadrant, dict) else {}
    tier_label_map = {
        'tier1_best': '最佳击球区',
        'tier2_good': '优质击球区',
        'tier3_normal': '普通击球区',
        'tier4_edge': '边缘击球区',
    }
    for tier_key, tier_label in tier_label_map.items():
        for item in hs_analysis.get(tier_key, []) or []:
            item_name = item.get('name', '')
            if sector_name_matches(item_name, sector_name):
                return {
                    'quality_score': _safe_float(item.get('quality_score', 0)),
                    'label': tier_label,
                    'position_in_range': _safe_float(item.get('positionInRange')),
                    'recent_change': _safe_float(item.get('recentChange')),
                }

    quadrants = (sector_quadrant.get('quadrants') or {}) if isinstance(sector_quadrant, dict) else {}
    for quadrant_name, quadrant_items in quadrants.items():
        for item in quadrant_items or []:
            item_name = item.get('name', '')
            if sector_name_matches(item_name, sector_name):
                return {
                    'quality_score': _safe_float(item.get('quality_score', 0)),
                    'label': quadrant_name,
                    'position_in_range': _safe_float(item.get('positionInRange')),
                    'recent_change': _safe_float(item.get('recentChange')),
                }
    return {}


def _build_unified_sector_strength_rows(data):
    data = data or {}
    target_date = str(data.get('target_date', '') or '')
    zt_pool_by_sector = data.get('zt_pool_by_sector', {}) or {}
    dt_pool_by_sector = data.get('dt_pool_by_sector', {}) or {}
    sector_fund_flow = data.get('sector_fund_flow', {}) or {}
    hot_plates = data.get('hot_plates', []) or []
    hot_rank_top30 = data.get('hot_rank_top30', []) or []
    tag_distribution = data.get('tag_distribution', {}) or {}
    sector_quadrant = data.get('sector_quadrant', {}) or {}

    sector_buckets = []

    for sector_name, stocks in zt_pool_by_sector.items():
        bucket = _get_or_create_sector_bucket(sector_buckets, sector_name)
        if not bucket:
            continue
        bucket['zt_count'] = max(bucket.get('zt_count', 0), len(stocks or []))
        dragon_count = sum(
            1 for stock in (stocks or [])
            if int(_safe_float(stock.get('连板数', stock.get('lianban', 0)))) >= 2
        )
        bucket['dragon_count'] = max(bucket.get('dragon_count', 0), dragon_count)

    for sector_name, stocks in dt_pool_by_sector.items():
        bucket = _get_or_create_sector_bucket(sector_buckets, sector_name)
        if not bucket:
            continue
        bucket['dt_count'] = max(bucket.get('dt_count', 0), len(stocks or []))

    for item in sector_fund_flow.get('inflow', []) or []:
        bucket = _get_or_create_sector_bucket(sector_buckets, item.get('name', ''))
        if not bucket:
            continue
        bucket['net_inflow'] = _safe_float(item.get('zljlr', bucket.get('net_inflow', 0.0)))
        bucket['change'] = _safe_float(item.get('zdf', bucket.get('change', 0.0)))

    for item in sector_fund_flow.get('outflow', []) or []:
        bucket = _get_or_create_sector_bucket(sector_buckets, item.get('name', ''))
        if not bucket:
            continue
        if abs(_safe_float(bucket.get('net_inflow', 0.0))) < 1e-9:
            bucket['net_inflow'] = _safe_float(item.get('zljlr', 0.0))
        if abs(_safe_float(bucket.get('change', 0.0))) < 1e-9:
            bucket['change'] = _safe_float(item.get('zdf', 0.0))

    for plate in hot_plates[:20]:
        bucket = _get_or_create_sector_bucket(sector_buckets, plate.get('name', ''))
        if not bucket:
            continue
        plate_rank = int(_safe_float(plate.get('order', 0)) or 0) or None
        current_rank = bucket.get('hot_plate_rank')
        if current_rank is None or (plate_rank and plate_rank < current_rank):
            bucket['hot_plate_rank'] = plate_rank
        bucket['hot_plate_heat'] = max(bucket.get('hot_plate_heat', 0.0), _safe_float(plate.get('rate', 0.0)))

    for bucket in sector_buckets:
        bucket['hot_weight'] = _safe_float(get_sector_hotlist_weight(bucket.get('name', ''), tag_distribution))
        quadrant_snapshot = _match_sector_quadrant_snapshot(bucket.get('name', ''), sector_quadrant)
        bucket['quadrant_quality_score'] = _safe_float(quadrant_snapshot.get('quality_score', 0.0))
        bucket['quadrant_label'] = quadrant_snapshot.get('label', '')
        bucket['quadrant_position'] = quadrant_snapshot.get('position_in_range')
        bucket['quadrant_recent_change'] = quadrant_snapshot.get('recent_change')

    for stock in hot_rank_top30[:30]:
        for bucket in sector_buckets:
            if stock_matches_sector(stock, bucket.get('name', '')):
                bucket['hot_stock_count'] = int(bucket.get('hot_stock_count', 0)) + 1

    rows = []
    for bucket in sector_buckets:
        sector_name = bucket.get('name', '')
        if not sector_name:
            continue

        inflow_history = load_recent_sector_flow_history(target_date, sector_name, lookback_days=2) if target_date else []
        star_snapshot = get_mainline_star_level(
            bucket.get('net_inflow', 0.0),
            bucket.get('zt_count', 0),
            dt_count=bucket.get('dt_count', 0),
            hot_weight=bucket.get('hot_weight', 0.0),
            inflow_history=inflow_history,
        )

        base_score = _safe_float(star_snapshot.get('score_pct', 0.0))
        hot_plate_rank = bucket.get('hot_plate_rank')
        hot_plate_bonus = 0.0
        if hot_plate_rank:
            hot_plate_bonus += max(18.0 - (hot_plate_rank - 1) * 2.0, 0.0)
            if hot_plate_rank <= 3:
                hot_plate_bonus += 4.0
        hot_stock_bonus = min(bucket.get('hot_stock_count', 0) * 4.0, 14.0)
        dragon_bonus = min(bucket.get('dragon_count', 0) * 4.0, 10.0)
        quadrant_bonus = min(bucket.get('quadrant_quality_score', 0.0) * 0.18, 16.0)
        heat_bonus = min(bucket.get('hot_weight', 0.0) * 0.4, 8.0)
        change_bonus = _clamp(_safe_float(bucket.get('change', 0.0)) * 1.8, -6.0, 8.0)
        outflow_penalty = 6.0 if bucket.get('net_inflow', 0.0) < 0 and bucket.get('zt_count', 0) < 2 else 0.0
        dt_penalty = min(bucket.get('dt_count', 0) * 4.0, 12.0)
        unified_score = _clamp(
            base_score * 0.62
            + hot_plate_bonus
            + hot_stock_bonus
            + dragon_bonus
            + quadrant_bonus
            + heat_bonus
            + change_bonus
            - outflow_penalty
            - dt_penalty,
            0.0,
            100.0,
        )

        is_main = (
            unified_score >= 55
            or (
                hot_plate_rank
                and hot_plate_rank <= 3
                and (
                    bucket.get('zt_count', 0) >= 2
                    or bucket.get('hot_stock_count', 0) >= 2
                    or bucket.get('quadrant_quality_score', 0.0) >= 60
                )
            )
            or (bucket.get('zt_count', 0) >= 5 and bucket.get('net_inflow', 0.0) > 0)
        )
        is_secondary = (
            not is_main
            and (
                unified_score >= 38
                or (hot_plate_rank and hot_plate_rank <= 6)
                or bucket.get('zt_count', 0) >= 2
                or bucket.get('hot_stock_count', 0) >= 2
                or bucket.get('quadrant_quality_score', 0.0) >= 50
            )
        )
        if is_main:
            role = 'main'
        elif is_secondary:
            role = 'secondary'
        else:
            role = 'observe'

        strength = 'strong' if unified_score >= 70 else 'medium' if unified_score >= 55 else 'probe' if unified_score >= 40 else 'weak'
        evidence_parts = []
        if bucket.get('zt_count', 0):
            evidence_parts.append(f"涨停{bucket.get('zt_count', 0)}")
        if abs(_safe_float(bucket.get('net_inflow', 0.0))) > 0:
            evidence_parts.append(f"资金{bucket.get('net_inflow', 0.0):+.1f}亿")
        if hot_plate_rank:
            evidence_parts.append(f"板块热榜#{hot_plate_rank}")
        if bucket.get('hot_stock_count', 0):
            evidence_parts.append(f"热股{bucket.get('hot_stock_count', 0)}")
        if bucket.get('quadrant_label'):
            evidence_parts.append(f"{bucket.get('quadrant_label')}")

        rows.append({
            'name': sector_name,
            'zt_count': int(bucket.get('zt_count', 0)),
            'dt_count': int(bucket.get('dt_count', 0)),
            'change': round(_safe_float(bucket.get('change', 0.0)), 2),
            'net_inflow': round(_safe_float(bucket.get('net_inflow', 0.0)), 2),
            'strength': strength,
            'star_level': star_snapshot.get('star_level', '⭐'),
            'star_score_pct': round(base_score, 1),
            'unified_score': round(unified_score, 1),
            'role': role,
            'dragon_count': int(bucket.get('dragon_count', 0)),
            'hot_plate_rank': hot_plate_rank,
            'hot_stock_count': int(bucket.get('hot_stock_count', 0)),
            'hot_weight': round(_safe_float(bucket.get('hot_weight', 0.0)), 2),
            'quadrant_quality_score': round(_safe_float(bucket.get('quadrant_quality_score', 0.0)), 1),
            'quadrant_label': bucket.get('quadrant_label', ''),
            'trend_label': star_snapshot.get('trend_label', ''),
            'flow_trend': star_snapshot.get('flow_trend', ''),
            'score_detail': {
                '连续主线分': round(base_score, 1),
                '板块热榜加分': round(hot_plate_bonus, 1),
                '热股加分': round(hot_stock_bonus, 1),
                '龙头加分': round(dragon_bonus, 1),
                '击球区加分': round(quadrant_bonus, 1),
                '热度加分': round(heat_bonus, 1),
                '涨跌幅修正': round(change_bonus, 1),
                '风险扣分': round(outflow_penalty + dt_penalty, 1),
            },
            'evidence': " / ".join(evidence_parts) if evidence_parts else '结构证据不足',
        })

    rows.sort(
        key=lambda item: (
            item.get('unified_score', 0),
            item.get('zt_count', 0),
            item.get('net_inflow', 0.0),
            -int(item.get('hot_plate_rank') or 999),
        ),
        reverse=True,
    )
    return rows


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
    """为主线核心股准备行情快照（止损价由 K 线按趋势理念另行计算）"""
    if not core_stock:
        return None

    code = normalize_stock_code(core_stock.get('code', ''))
    info = stock_full_info.get(code, {}) if stock_full_info else {}
    close_price = info.get('close', 0) or core_stock.get('close', 0) or 0
    low_price = info.get('low', 0) or core_stock.get('low', 0) or 0

    if not close_price:
        return None

    stop_loss = low_price if low_price and low_price > 0 else close_price * 0.95

    return {
        'code': code,
        'close_price': close_price,
        'stop_loss': round(stop_loss, 2),
    }


def compute_trend_article_stop_loss(bars):
    """
    趋势性交易理念下的备用止损（无可靠放量信号时使用）：
    - 窗口内从最近往前数，第一根阴线（收盘 < 开盘）的最低价；
    - 若窗口内全是阳线：用前一交易日最低价；
    - 仅一日数据：用该日最低价兜底。
    返回 (stop_loss, anchor_date, rule_hint)
    """
    if not bars:
        return None, None, ''
    sorted_bars = sorted(bars, key=lambda x: str(x.get('date', '')))
    for i in range(len(sorted_bars) - 1, -1, -1):
        b = sorted_bars[i]
        o = float(b.get('open') or 0)
        c = float(b.get('close') or 0)
        if o > 0 and c > 0 and c < o:
            low = float(b.get('low') or 0)
            if low > 0:
                return round(low, 2), b.get('date'), '最近阴线最低价，跌破=大本营失守/模式失效，直接卖'
    if len(sorted_bars) >= 2:
        prev = sorted_bars[-2]
        low = float(prev.get('low') or 0)
        if low > 0:
            return round(low, 2), prev.get('date'), '窗口内无阴线，用前一交易日最低价，跌破即卖'
    last = sorted_bars[-1]
    low = float(last.get('low') or 0)
    if low > 0:
        return round(low, 2), last.get('date'), '仅最近一日数据，用该日最低价，跌破即卖'
    return None, None, ''


# 止损「最近前低」= 与 3~5 日观察期同尺度的短期前低（默认取满 5 个交易日，避免连板股被 20 日远古低点拉得过远）
STOP_PRIOR_LOW_TRADING_DAYS = 5


def compute_stop_loss_mainline_anchor(bars, window=None):
    """
    主线锚定价止损 = 「最近前低」之日报量化：
    取近 window 个交易日内的最低价（默认 STOP_PRIOR_LOW_TRADING_DAYS=5，对齐观察期上沿）；
    K 线不足 window 根时用已有全部 K 线；若有同日并列最低，取更靠后一根。
    无有效 low 时回退阴线/前一日法则。
    """
    if window is None:
        window = STOP_PRIOR_LOW_TRADING_DAYS
    if not bars:
        return None, None, ''
    sorted_bars = sorted(bars, key=lambda x: str(x.get('date', '')))
    w = sorted_bars[-window:] if len(sorted_bars) > window else sorted_bars
    best = None
    best_bar = None
    for b in w:
        lo = float(b.get('low') or 0)
        if lo <= 0:
            continue
        if best is None or lo < best:
            best = lo
            best_bar = b
        elif abs(lo - best) < 1e-9:
            best_bar = b
    if best is None or not best_bar:
        return compute_trend_article_stop_loss(w)
    hint = (
        f"近{len(w)}个交易日最低价（与3~5日观察期同尺度前低）；跌破直接卖。"
        "买入侧看放量异常；持有仅3~5日观察，不及预期也卖；大阳线为理想主动卖点"
    )
    return round(best, 2), best_bar.get('date'), hint


def _resolve_daily_price_anchor(stock_code, target_date, recent_bars=None, window=None):
    if window is None:
        window = STOP_PRIOR_LOW_TRADING_DAYS

    bars = recent_bars
    if bars is None and stock_code:
        bars = fetch_recent_price_bars(
            stock_code,
            target_date,
            lookback_days=max(window + 5, 10),
        )
    bars = _trim_bars_to_target_date(bars or [], target_date)

    stop_loss, anchor_date, rule_hint = compute_stop_loss_mainline_anchor(bars or [], window=window)
    if stop_loss is None or stop_loss <= 0:
        return {
            'stop': None,
            'anchor_date': '',
            'hint': '',
        }

    return {
        'stop': round(stop_loss, 2),
        'anchor_date': anchor_date or '',
        'hint': rule_hint or '',
    }


def _attach_daily_price_anchor(stop_plan, daily_anchor):
    if not stop_plan:
        return stop_plan

    enriched = dict(stop_plan)
    daily_anchor = daily_anchor or {}
    daily_stop = _safe_float(daily_anchor.get('stop'))
    if daily_stop > 0:
        enriched['daily_anchor_stop'] = round(daily_stop, 2)
        enriched['daily_anchor_date'] = daily_anchor.get('anchor_date', '') or ''
        enriched['daily_anchor_hint'] = daily_anchor.get('hint', '') or ''
    return enriched


def _resolve_big_yang_confluence_anchor(recent_bars, target_date='', window=6):
    bars = _trim_bars_to_target_date(recent_bars or [], target_date)
    if not bars:
        return {}

    sorted_bars = sorted(bars, key=lambda x: str(x.get('date', '')))
    start_idx = max(0, len(sorted_bars) - max(int(window or 0), 1))
    candidate = None

    for idx in range(start_idx, len(sorted_bars)):
        bar = sorted_bars[idx]
        open_price = _safe_float(bar.get('open'))
        high_price = _safe_float(bar.get('high'))
        low_price = _safe_float(bar.get('low'))
        close_price = _safe_float(bar.get('close'))
        if open_price <= 0 or high_price <= 0 or low_price <= 0 or close_price <= 0:
            continue
        if close_price <= open_price:
            continue

        prev_close = _safe_float(sorted_bars[idx - 1].get('close')) if idx > 0 else 0.0
        change_pct = ((close_price / prev_close) - 1) * 100 if prev_close > 0 else ((close_price / open_price) - 1) * 100
        full_range = max(high_price - low_price, 0.0)
        body_ratio = (close_price - open_price) / full_range if full_range > 0 else 0.0
        close_near_high = high_price > 0 and (high_price - close_price) <= max(high_price * 0.01, 0.05)

        is_key_big_yang = (
            change_pct >= 5.0
            and body_ratio >= 0.45
            and close_near_high
        )
        is_limit_like = change_pct >= 9.5 and close_near_high

        if not is_key_big_yang and not is_limit_like:
            continue

        candidate = {
            'open_anchor': round(open_price, 2),
            'limit_anchor': round(close_price, 2) if is_limit_like else None,
            'date': bar.get('date', ''),
            'change_pct': round(change_pct, 2),
        }

    return candidate or {}


def _attach_breakout_confluence_anchor(stop_plan, breakout_anchor):
    if not stop_plan:
        return stop_plan

    enriched = dict(stop_plan)
    breakout_anchor = breakout_anchor or {}
    open_anchor = _safe_float(breakout_anchor.get('open_anchor'))
    limit_anchor = _safe_float(breakout_anchor.get('limit_anchor'))
    if open_anchor > 0:
        enriched['breakout_open_anchor'] = round(open_anchor, 2)
    if limit_anchor > 0:
        enriched['breakout_limit_anchor'] = round(limit_anchor, 2)
    if breakout_anchor.get('date'):
        enriched['breakout_anchor_date'] = breakout_anchor.get('date', '')
    return enriched


def _enrich_stop_plan_with_reference_anchors(stop_plan, stock_code, target_date, recent_bars=None):
    if not stop_plan:
        return stop_plan

    bars = _trim_bars_to_target_date(recent_bars or [], target_date)
    if not bars and stock_code:
        bars = fetch_recent_price_bars(
            stock_code,
            target_date,
            lookback_days=max(STOP_PRIOR_LOW_TRADING_DAYS + 5, 10),
        )
        bars = _trim_bars_to_target_date(bars or [], target_date)

    enriched = _attach_daily_price_anchor(
        stop_plan,
        _resolve_daily_price_anchor(stock_code, target_date, recent_bars=bars),
    )
    enriched = _attach_breakout_confluence_anchor(
        enriched,
        _resolve_big_yang_confluence_anchor(bars, target_date=target_date),
    )
    return enriched


def fetch_recent_price_bars(stock_code, target_date, lookback_days=10, fast_fail=False):
    """获取个股最近若干日K线（QuickTiny API优先，BaoStock兜底）"""
    code = normalize_stock_code(stock_code)
    if not code or not target_date:
        return []

    if fast_fail:
        return []

    full_code = f"{'sh' if code.startswith('6') else 'sz'}{code}"
    try:
        import requests
        url = f"https://stock.quicktiny.cn/api/tushare/merged-kline/{full_code}?days={lookback_days + 5}"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        result = resp.json()
        if result.get('success') and isinstance(result.get('data'), list) and len(result['data']) > 0:
            target_norm = _normalize_kline_date_str(target_date)
            sorted_data = sorted(result['data'], key=lambda x: x.get('date', ''))
            cleaned = []
            for d in sorted_data:
                date_text = _normalize_kline_date_str(d.get('date', ''))
                if target_norm and date_text and date_text > target_norm:
                    continue
                cleaned.append({
                    'date': date_text or d.get('date', ''),
                    'open': d.get('open', 0) or 0,
                    'high': d.get('high', 0) or 0,
                    'low': d.get('low', 0) or 0,
                    'close': d.get('close', 0) or 0,
                    'volume': float(d.get('vol') or d.get('volume') or 0),
                    'amount': float(d.get('amount') or 0),
                })
            return cleaned[-lookback_days:]
    except Exception:
        pass

    try:
        from finshare.sources.baostock_source import BaoStockDataSource
        bs = BaoStockDataSource()
        target_dt = datetime.datetime.strptime(target_date, "%Y-%m-%d").date()
        start_dt = target_dt - datetime.timedelta(days=max(lookback_days * 2, 10))
        bars = bs.get_historical_data(code, start_dt, target_dt)
        if not bars:
            return []
        cleaned = []
        for bar in bars:
            date_text = _normalize_kline_date_str(getattr(bar, 'trade_date', None))
            if date_text and date_text > _normalize_kline_date_str(target_date):
                continue
            cleaned.append({
                'date': date_text,
                'open': getattr(bar, 'open_price', 0) or 0,
                'high': getattr(bar, 'high_price', 0) or 0,
                'low': getattr(bar, 'low_price', 0) or 0,
                'close': getattr(bar, 'close_price', 0) or 0,
                'volume': float(getattr(bar, 'volume', 0) or 0),
                'amount': float(getattr(bar, 'amount', 0) or 0),
            })
        return cleaned[-lookback_days:]
    except Exception:
        return []


_intraday_bar_cache = {}


def fetch_intraday_bars(stock_code, target_date, period='30', lookback_bars=12):
    """获取分钟级K线，优先使用 akshare 东财分钟线接口。"""
    code = normalize_stock_code(stock_code)
    period = str(period)
    cache_key = (code, target_date, period, lookback_bars)
    if cache_key in _intraday_bar_cache:
        return list(_intraday_bar_cache[cache_key])

    if not code or not target_date:
        return []

    cleaned = []
    try:
        import akshare as ak

        df = ak.stock_zh_a_hist_min_em(symbol=code, period=period, adjust='')
        if df is not None and len(df) > 0:
            for row in df.to_dict('records'):
                dt_text = str(row.get('时间', '') or '').strip()
                if not dt_text:
                    continue
                date_text = _normalize_kline_date_str(dt_text.split(' ')[0])
                if not date_text or date_text > target_date:
                    continue
                cleaned.append({
                    'datetime': dt_text,
                    'date': date_text,
                    'open': float(row.get('开盘', 0) or 0),
                    'high': float(row.get('最高', 0) or 0),
                    'low': float(row.get('最低', 0) or 0),
                    'close': float(row.get('收盘', 0) or 0),
                    'volume': float(row.get('成交量', 0) or 0),
                    'amount': float(row.get('成交额', 0) or 0),
                })
    except Exception:
        cleaned = []

    result = cleaned[-lookback_bars:] if lookback_bars and len(cleaned) > lookback_bars else cleaned
    _intraday_bar_cache[cache_key] = list(result)
    return result


def _find_latest_intraday_pivot(bars, mode='low'):
    """寻找最近一个分钟级拐点，找不到时回退最近窗口极值。"""
    if not bars:
        return None, None

    field = 'low' if mode == 'low' else 'high'
    comparator = min if mode == 'low' else max

    for idx in range(len(bars) - 2, 0, -1):
        prev_val = float(bars[idx - 1].get(field) or 0)
        curr_val = float(bars[idx].get(field) or 0)
        next_val = float(bars[idx + 1].get(field) or 0)
        if curr_val <= 0:
            continue

        if mode == 'low':
            is_pivot = curr_val <= prev_val and curr_val <= next_val and (curr_val < prev_val or curr_val < next_val)
        else:
            is_pivot = curr_val >= prev_val and curr_val >= next_val and (curr_val > prev_val or curr_val > next_val)

        if is_pivot:
            return round(curr_val, 2), bars[idx].get('datetime') or bars[idx].get('date')

    recent = bars[-4:] if len(bars) >= 4 else bars
    values = [float(b.get(field) or 0) for b in recent if float(b.get(field) or 0) > 0]
    if not values:
        return None, None

    fallback_value = round(comparator(values), 2)
    for b in reversed(recent):
        val = round(float(b.get(field) or 0), 2)
        if abs(val - fallback_value) < 1e-9:
            return fallback_value, b.get('datetime') or b.get('date')
    return fallback_value, recent[-1].get('datetime') or recent[-1].get('date')


def _compute_avg_volume(bars, sample_size=5, exclude_last=False):
    sample = bars[:-1] if exclude_last and len(bars) > 1 else bars
    if not sample:
        return 0.0
    sample = sample[-sample_size:] if len(sample) > sample_size else sample
    vols = [float(b.get('volume') or 0) for b in sample if float(b.get('volume') or 0) >= 0]
    return sum(vols) / len(vols) if vols else 0.0


def build_intraday_execution_plan(stock_code, target_date, entry_price, signal_type='', fallback_stop=None):
    """基于 60 分钟和 30 分钟K线，生成次日执行预案。"""
    try:
        entry = float(entry_price or 0)
    except (TypeError, ValueError):
        entry = 0

    if entry <= 0:
        return {}

    bars_60m = fetch_intraday_bars(
        stock_code, target_date, period='60', lookback_bars=INTRADAY_CONFIRM_LOOKBACK_60M
    )
    bars_30m = fetch_intraday_bars(
        stock_code, target_date, period='30', lookback_bars=INTRADAY_STOP_LOOKBACK_30M
    )

    latest_60m = bars_60m[-1] if bars_60m else None
    latest_30m = bars_30m[-1] if bars_30m else None

    support_60m, support_60m_dt = _find_latest_intraday_pivot(bars_60m, mode='low')
    recent_high_60m, recent_high_60m_dt = _find_latest_intraday_pivot(bars_60m, mode='high')
    structure_stop_30m, structure_stop_30m_dt = _find_latest_intraday_pivot(bars_30m, mode='low')

    if structure_stop_30m is None and fallback_stop:
        try:
            structure_stop_30m = round(float(fallback_stop), 2)
        except (TypeError, ValueError):
            structure_stop_30m = None

    if support_60m is None and structure_stop_30m is not None:
        support_60m = structure_stop_30m
        support_60m_dt = structure_stop_30m_dt

    recent_high_60m = recent_high_60m or round(entry, 2)
    confirm_price_60m = round(max(entry, recent_high_60m), 2)

    latest_60m_close = round(float(latest_60m.get('close') or 0), 2) if latest_60m else None
    latest_60m_open = round(float(latest_60m.get('open') or 0), 2) if latest_60m else None
    latest_60m_high = round(float(latest_60m.get('high') or 0), 2) if latest_60m else None
    latest_60m_low = round(float(latest_60m.get('low') or 0), 2) if latest_60m else None

    avg_volume_60m = _compute_avg_volume(bars_60m, sample_size=5, exclude_last=True)
    volume_ratio_60m = None
    if latest_60m and avg_volume_60m > 0:
        volume_ratio_60m = round(float(latest_60m.get('volume') or 0) / avg_volume_60m, 2)

    if signal_type == 'breakout':
        confirm_rule = f"首个60分钟放量站上{confirm_price_60m:.2f}"
        if support_60m:
            confirm_rule += f"，且不破{support_60m:.2f}"
        confirm_state = "60分钟突破雏形" if (
            latest_60m_close and latest_60m_close >= entry and (volume_ratio_60m or 0) >= 1.0
        ) else "等待60分钟放量确认"
    elif signal_type == 'panic_buy':
        confirm_rule = f"首个60分钟不破{support_60m:.2f}并收回{confirm_price_60m:.2f}" if support_60m else f"首个60分钟收回{confirm_price_60m:.2f}"
        confirm_state = "60分钟尾盘已回稳" if (
            latest_60m_close and latest_60m_open and latest_60m_close >= latest_60m_open
        ) else "等待60分钟转强"
    elif signal_type == 'sweet_zone':
        confirm_rule = f"首个60分钟回踩不破{support_60m:.2f}后再站上{confirm_price_60m:.2f}" if support_60m else f"首个60分钟站上{confirm_price_60m:.2f}"
        confirm_state = "60分钟尾盘偏强" if (
            latest_60m_close and latest_60m_open and latest_60m_close >= latest_60m_open
        ) else "60分钟仍待确认"
    else:
        confirm_rule = f"首个60分钟站上{confirm_price_60m:.2f}"
        if support_60m:
            confirm_rule += f"，且不破{support_60m:.2f}"
        confirm_state = "可按60分钟确认" if latest_60m_close else "分钟数据不足"

    stop_plan = build_stop_execution_plan(
        entry,
        structure_stop_30m,
        structure_label='30分钟结构止损'
    )

    return {
        'bars_60m': bars_60m,
        'bars_30m': bars_30m,
        'latest_60m_datetime': latest_60m.get('datetime') if latest_60m else '',
        'latest_60m_close': latest_60m_close,
        'latest_60m_high': latest_60m_high,
        'latest_60m_low': latest_60m_low,
        'latest_30m_datetime': latest_30m.get('datetime') if latest_30m else '',
        'confirm_price_60m': confirm_price_60m,
        'confirm_support_60m': support_60m,
        'confirm_support_60m_datetime': support_60m_dt,
        'confirm_high_60m_datetime': recent_high_60m_dt,
        'confirm_rule_60m': confirm_rule,
        'confirm_state_60m': confirm_state,
        'volume_ratio_60m': volume_ratio_60m,
        'structure_stop_30m': structure_stop_30m,
        'structure_stop_30m_datetime': structure_stop_30m_dt,
        'stop_plan': stop_plan,
    }


def build_waiting_stock_plan(stock_item, target_date, reason='', signal_type='', recent_bars=None):
    """为观察股生成分钟级预案。"""
    code = stock_item.get('code', '')
    entry_price = float(stock_item.get('close', 0) or stock_item.get('entry_price', 0) or 0)
    minute_plan = build_intraday_execution_plan(
        code,
        target_date,
        entry_price,
        signal_type=signal_type,
        fallback_stop=entry_price * (1 - MAX_SINGLE_TRADE_LOSS_PCT) if entry_price > 0 else None,
    )
    stop_plan = minute_plan.get('stop_plan') or build_stop_execution_plan(entry_price)
    stop_plan = _enrich_stop_plan_with_reference_anchors(
        stop_plan,
        code,
        target_date,
        recent_bars=recent_bars,
    )
    return {
        **stock_item,
        'entry_price': entry_price,
        'reason': reason or stock_item.get('reason') or stock_item.get('condition', '等待信号'),
        'minute_plan': minute_plan,
        'stop_plan': stop_plan,
        'stop_loss': stop_plan['effective_stop'] if stop_plan else 0,
    }


def get_sector_core_hot_stock(sector_name, hot_rank_top30):
    """获取主线板块在热榜中的核心股"""
    if not sector_name or not hot_rank_top30:
        return None
    for idx, stock in enumerate(hot_rank_top30, 1):
        if stock_matches_sector(stock, sector_name):
            core_stock = dict(stock)
            core_stock['hot_rank'] = idx
            return core_stock
    return None


def get_sector_leader(sector_name, dragon_stocks, dt_pool_by_sector):
    """获取板块龙头，优先使用涨停梯队，其次使用跌停池识别失守龙头"""
    sector_dragons = [s for s in dragon_stocks if s.get('sector') == sector_name]
    if sector_dragons:
        sector_dragons.sort(key=lambda x: x.get('lianban', 0), reverse=True)
        leader = dict(sector_dragons[0])
        leader['is_limit_down'] = False
        return leader
    dt_stocks = dt_pool_by_sector.get(sector_name, []) if dt_pool_by_sector else []
    if dt_stocks:
        first_dt = dt_stocks[0]
        return {
            'name': first_dt.get('name', '未知'),
            'code': normalize_stock_code(first_dt.get('code', '')),
            'sector': sector_name,
            'lianban': 0,
            'zt_type': '跌停',
            'is_limit_down': True
        }
    return None


def _safe_float(value, default=0.0):
    """安全转 float，失败时回退默认值。"""
    try:
        if value in (None, ''):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _pick_sector_anchor_stock(sector_name, sector_stocks, dragon_stocks):
    """从当前候选中选出最适合做后续跟踪锚点的个股。"""
    if not sector_stocks:
        return None

    dragon_by_code = {
        normalize_stock_code(stock.get('code', '')): stock
        for stock in (dragon_stocks or [])
        if stock_matches_sector(stock, sector_name)
    }

    def _priority(stock):
        code = normalize_stock_code(stock.get('code', ''))
        dragon = dragon_by_code.get(code, {})
        lianban = int(
            stock.get('连板数', stock.get('lianban', dragon.get('lianban', 0))) or 0
        )
        tomorrow_strength = _safe_float(stock.get('tomorrow_strength', stock.get('score', 0)))
        raw_score = _safe_float(stock.get('score', 0))
        change = _safe_float(stock.get('change', 0))
        volume = _safe_float(stock.get('volume', 0))
        reason = str(stock.get('reason', ''))
        pattern = str(stock.get('pattern', ''))
        is_anchor = 1 if ('龙一' in reason or '前排' in reason or code in dragon_by_code) else 0
        pattern_rank = 0
        if pattern == '一字板':
            pattern_rank = 3
        elif pattern == 'T字板':
            pattern_rank = 2
        elif '涨停' in pattern:
            pattern_rank = 1
        return (lianban, is_anchor, tomorrow_strength, raw_score, pattern_rank, change, volume)

    return max(sector_stocks, key=_priority)


def build_sector_trend_snapshot(candidates, watchlist, evaluated_stocks, dragon_stocks, zt_pool_by_sector=None, top_n=5):
    """统计每条线的趋势股密度，并给出优先锚定的龙头。"""
    sector_buckets = {}

    def _ensure_bucket(sector_name):
        if not sector_name:
            return None
        bucket = sector_buckets.setdefault(
            sector_name,
            {
                'candidates': [],
                'watchlist': [],
                'evaluated': [],
                'candidate_codes': set(),
                'watch_codes': set(),
                'strong_codes': set(),
                'core_codes': set(),
            }
        )
        return bucket

    for stock in candidates or []:
        sector = str(stock.get('sector', '') or '').strip()
        bucket = _ensure_bucket(sector)
        if not bucket:
            continue
        code = normalize_stock_code(stock.get('code', ''))
        bucket['candidates'].append(stock)
        if code:
            bucket['candidate_codes'].add(code)
            if _safe_float(stock.get('score', 0)) >= 50:
                bucket['strong_codes'].add(code)

    for stock in watchlist or []:
        sector = str(stock.get('sector', '') or '').strip()
        bucket = _ensure_bucket(sector)
        if not bucket:
            continue
        code = normalize_stock_code(stock.get('code', ''))
        bucket['watchlist'].append(stock)
        if code:
            bucket['watch_codes'].add(code)

    for stock in evaluated_stocks or []:
        sector = str(stock.get('sector', '') or '').strip()
        bucket = _ensure_bucket(sector)
        if not bucket:
            continue
        code = normalize_stock_code(stock.get('code', ''))
        bucket['evaluated'].append(stock)
        lianban = int(stock.get('连板数', stock.get('lianban', 0)) or 0)
        if code and (_safe_float(stock.get('tomorrow_strength', 0)) >= 60 or lianban >= 2):
            bucket['core_codes'].add(code)

    snapshot = []
    for sector, bucket in sector_buckets.items():
        trend_count = len(bucket['candidate_codes'])
        watch_count = len(bucket['watch_codes'])
        strong_count = len(bucket['strong_codes'])
        core_count = len(bucket['core_codes'])
        limit_up_count = len((zt_pool_by_sector or {}).get(sector, []))
        strength_sum = sum(_safe_float(s.get('tomorrow_strength', s.get('score', 0))) for s in bucket['evaluated'][:5])

        anchor_source = bucket['evaluated'] or bucket['watchlist'] or bucket['candidates']
        anchor_stock = _pick_sector_anchor_stock(sector, anchor_source, dragon_stocks or [])
        anchor_name = anchor_stock.get('name', '-') if anchor_stock else '-'
        anchor_code = normalize_stock_code(anchor_stock.get('code', '')) if anchor_stock else ''
        anchor_lianban = int(anchor_stock.get('连板数', anchor_stock.get('lianban', 0)) or 0) if anchor_stock else 0
        anchor_pattern = str(anchor_stock.get('pattern', '')) if anchor_stock else ''
        anchor_reason = "板块辨识度最高"
        if anchor_lianban >= 3:
            anchor_reason = "板块高标，资金已记住"
        elif anchor_lianban == 2:
            anchor_reason = "连板先锋，后续优先回看"
        elif '龙一' in str(anchor_stock.get('reason', '')):
            anchor_reason = "首波先锋，优先做重点观察谁"
        elif anchor_pattern in ['一字板', 'T字板']:
            anchor_reason = "强异动已出现，等分歧后再看转强"

        density_score = (
            trend_count * 10
            + watch_count * 8
            + strong_count * 10
            + core_count * 12
            + min(limit_up_count, 6) * 4
            + int(strength_sum / 20)
        )

        snapshot.append({
            'sector': sector,
            'trend_count': trend_count,
            'watch_count': watch_count,
            'strong_count': strong_count,
            'core_count': core_count,
            'limit_up_count': limit_up_count,
            'density_score': density_score,
            'anchor_name': anchor_name,
            'anchor_code': anchor_code,
            'anchor_lianban': anchor_lianban,
            'anchor_reason': anchor_reason,
        })

    snapshot.sort(
        key=lambda x: (
            x.get('density_score', 0),
            x.get('core_count', 0),
            x.get('strong_count', 0),
            x.get('trend_count', 0),
        ),
        reverse=True,
    )
    return snapshot[:top_n]


def build_extreme_conviction_list(evaluated_stocks, mainline_name, sector_snapshot=None, top_n=3):
    """从候选中聚焦出极少数最值得盯的标的。"""
    if not evaluated_stocks:
        return []

    anchor_codes = {
        normalize_stock_code(item.get('anchor_code', ''))
        for item in (sector_snapshot or [])
        if item.get('anchor_code')
    }

    conviction_list = []
    for stock in evaluated_stocks:
        code = normalize_stock_code(stock.get('code', ''))
        sector = stock.get('sector', '')
        tomorrow_strength = _safe_float(stock.get('tomorrow_strength', stock.get('score', 0)))
        lianban = int(stock.get('连板数', stock.get('lianban', 0)) or 0)
        reason = str(stock.get('reason', ''))
        pattern = str(stock.get('pattern', ''))
        is_mainline = sector_name_matches(sector, mainline_name)
        is_anchor = code in anchor_codes

        conviction_score = tomorrow_strength
        if is_mainline:
            conviction_score += 18
        if is_anchor:
            conviction_score += 12
        if lianban >= 2:
            conviction_score += 8
        if '龙一' in reason:
            conviction_score += 6
        if pattern == 'T字板':
            conviction_score += 4

        reason_parts = []
        if is_mainline:
            reason_parts.append("主线内核")
        if is_anchor:
            reason_parts.append("板块锚定龙")
        if lianban >= 2:
            reason_parts.append(f"{lianban}连板")
        elif '龙一' in reason:
            reason_parts.append("首波先锋")
        if pattern == 'T字板':
            reason_parts.append("分歧转一致形态")
        elif pattern == '一字板':
            reason_parts.append("资金顶出辨识度")
        elif '光头' in pattern:
            reason_parts.append("强实体异动")
        if not reason_parts:
            reason_parts.append("趋势辨识度高")

        action_rule = "只盯分歧后的转强，不追情绪顶点"
        if is_anchor and is_mainline:
            action_rule = "优先盯首个60分钟确认，若继续强就只做它"
        elif lianban >= 2:
            action_rule = "先看竞价承接，再等60分钟确认"

        conviction_list.append({
            **stock,
            'conviction_score': round(conviction_score, 1),
            'conviction_reason': " / ".join(reason_parts),
            'conviction_rule': action_rule,
        })

    conviction_list.sort(
        key=lambda x: (
            x.get('conviction_score', 0),
            x.get('tomorrow_strength', 0),
            x.get('连板数', x.get('lianban', 0)),
        ),
        reverse=True,
    )
    return conviction_list[:top_n]


def build_leader_memory_bank(sector_snapshot, watchlist, dragon_stocks, hot_rank_top30=None, top_n=5):
    """构建“龙头记忆库”，记录值得在后续10~20日持续回看的锚定股。"""
    if not sector_snapshot:
        return []

    hot_rank_map = {
        normalize_stock_code(stock.get('code', '')): idx
        for idx, stock in enumerate(hot_rank_top30 or [], 1)
        if stock.get('code')
    }
    watch_map = {
        normalize_stock_code(stock.get('code', '')): stock
        for stock in (watchlist or [])
        if stock.get('code')
    }
    dragon_map = {
        normalize_stock_code(stock.get('code', '')): stock
        for stock in (dragon_stocks or [])
        if stock.get('code')
    }

    memory_bank = []
    seen_codes = set()
    for item in sector_snapshot:
        code = normalize_stock_code(item.get('anchor_code', ''))
        if not code or code in seen_codes:
            continue
        seen_codes.add(code)

        watch_stock = watch_map.get(code, {})
        dragon_stock = dragon_map.get(code, {})
        sector = item.get('sector', '') or watch_stock.get('sector', '') or dragon_stock.get('sector', '')
        lianban = int(
            watch_stock.get('连板数', watch_stock.get('lianban', dragon_stock.get('lianban', item.get('anchor_lianban', 0)))) or 0
        )
        hot_rank = hot_rank_map.get(code)

        remember_reason_parts = [item.get('anchor_reason', '板块辨识度最高')]
        if hot_rank and hot_rank <= 20:
            remember_reason_parts.append(f"热榜第{hot_rank}")
        if lianban >= 2:
            remember_reason_parts.append(f"{lianban}连板已被资金记住")
        elif '龙一' in str(watch_stock.get('reason', '')):
            remember_reason_parts.append("首波龙一")

        remember_score = _safe_float(item.get('density_score', 0))
        remember_score += 12 if hot_rank and hot_rank <= 10 else 6 if hot_rank and hot_rank <= 20 else 0
        remember_score += lianban * 4

        memory_bank.append({
            'name': item.get('anchor_name', '-') or watch_stock.get('name', '-') or dragon_stock.get('name', '-'),
            'code': code,
            'sector': sector,
            'remember_score': round(remember_score, 1),
            'remember_reason': " / ".join([part for part in remember_reason_parts if part]),
            'remember_window': "10~20个交易日",
            'action_rule': "后续若板块再发力，优先回看它；只做分歧后的60分钟再转强",
        })

    memory_bank.sort(
        key=lambda item: (
            item.get('remember_score', 0),
            item.get('sector', ''),
        ),
        reverse=True,
    )
    return memory_bank[:top_n]


def _tracking_memory_path():
    return os.path.join(os.path.dirname(__file__), '..', 'data', 'tracking_memory.json')


def _safe_parse_report_date(date_text):
    try:
        return datetime.datetime.strptime(str(date_text), "%Y-%m-%d").date()
    except Exception:
        return None


def _load_tracking_memory_state():
    import json

    path = _tracking_memory_path()
    if not os.path.exists(path):
        return {'items': []}

    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict):
            data.setdefault('items', [])
            return data
    except Exception:
        pass
    return {'items': []}


def _save_tracking_memory_state(state):
    import json

    path = _tracking_memory_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def refresh_tracking_memory(target_date, watchlist, leader_memory_bank, abnormal_watch_pool, stock_meta_map=None):
    """跨日维护“跟踪记忆簿”。

    设计原则：
    1. 新记录先是“假设”，不能直接获得执行权
    2. 只有反复被今日数据再次验证，才升级为“可信记忆”
    3. 今日一旦明确转弱，旧记忆立即失效，不允许错上加错
    """
    state = _load_tracking_memory_state()
    previous_items = state.get('items', []) if isinstance(state, dict) else []
    previous_map = {}
    for item in previous_items:
        code = normalize_stock_code(item.get('code', ''))
        if code:
            previous_map[code] = item

    today_entries = {}
    follow_state_rank = {
        '已经转弱': 4,
        '跌不下去': 3,
        '缩量消化': 2,
        '新异动待观察': 1,
        '': 0,
    }

    def register_entry(stock, source, raw_score=0, reason='', follow_state=''):
        code = normalize_stock_code(stock.get('code', stock.get('代码', '')))
        if not code:
            return

        meta = (stock_meta_map or {}).get(code, {})
        entry = today_entries.setdefault(
            code,
            {
                'code': code,
                'name': stock.get('name', stock.get('名称', '')) or meta.get('name', ''),
                'sector': stock.get('sector', stock.get('所属板块', '')) or meta.get('sector', ''),
                'sources': set(),
                'reasons': [],
                'raw_scores': [],
                'follow_state': '',
            }
        )
        entry['name'] = entry.get('name') or stock.get('name', stock.get('名称', '')) or meta.get('name', '')
        entry['sector'] = entry.get('sector') or stock.get('sector', stock.get('所属板块', '')) or meta.get('sector', '')
        entry['sources'].add(source)
        if reason:
            entry['reasons'].append(str(reason))
        if raw_score:
            entry['raw_scores'].append(_safe_float(raw_score, 0))
        if follow_state_rank.get(str(follow_state), 0) > follow_state_rank.get(entry.get('follow_state', ''), 0):
            entry['follow_state'] = str(follow_state)

    for item in leader_memory_bank or []:
        register_entry(
            item,
            source='leader_memory',
            raw_score=item.get('remember_score', 0),
            reason=item.get('remember_reason', ''),
        )

    for rank, item in enumerate(watchlist or [], 1):
        if rank > 12:
            break
        register_entry(
            item,
            source='watchlist',
            raw_score=max(0, 30 - rank),
            reason=item.get('tomorrow_expectation', '') or item.get('core_logic', ''),
        )

    for item in abnormal_watch_pool or []:
        register_entry(
            item,
            source='abnormal_watch',
            raw_score=item.get('abnormal_score', 0),
            reason=item.get('action_rule', ''),
            follow_state=item.get('follow_state', ''),
        )

    today_date_obj = _safe_parse_report_date(target_date)
    new_items = []
    promoted_items = []
    dropped_items = []
    kept_items = []
    today_validated_items = []
    today_tentative_items = []

    for code, entry in today_entries.items():
        previous = previous_map.get(code, {})
        previous_status = previous.get('status', 'tentative')
        same_day_refresh = previous.get('last_seen_date') == target_date
        confirmations = int(previous.get('confirmations', 0) or 0)
        failures = int(previous.get('failures', 0) or 0)
        appearances = int(previous.get('appearances', 0) or 0)
        if not same_day_refresh:
            appearances += 1

        evidence_score = 0
        if 'leader_memory' in entry['sources']:
            evidence_score += 2
        if 'watchlist' in entry['sources']:
            evidence_score += 1
        if 'abnormal_watch' in entry['sources']:
            evidence_score += 1
        if len(entry['sources']) >= 2:
            evidence_score += 1
        if max(entry['raw_scores'] or [0]) >= 70:
            evidence_score += 1

        follow_state = entry.get('follow_state', '')
        if follow_state == '跌不下去':
            evidence_score += 2
        elif follow_state == '缩量消化':
            evidence_score += 1
        elif follow_state == '已经转弱':
            evidence_score -= 4

        if follow_state == '已经转弱':
            verdict = 'fail'
            if not same_day_refresh:
                failures += 1
        elif evidence_score >= 4:
            verdict = 'confirm'
            if not same_day_refresh:
                confirmations += 1
                failures = max(0, failures - 1)
        else:
            verdict = 'tentative'

        if verdict == 'fail':
            dropped_items.append({
                'name': entry.get('name', ''),
                'code': code,
                'reason': '今日已经转弱，旧记忆失效',
            })
            continue

        if previous_status == 'validated' or confirmations >= TRACKING_MEMORY_PROMOTE_CONFIRMATIONS:
            status = 'validated'
        else:
            status = 'tentative'

        memory_item = {
            'name': entry.get('name', ''),
            'code': code,
            'sector': entry.get('sector', ''),
            'status': status,
            'first_seen_date': previous.get('first_seen_date', target_date),
            'last_seen_date': target_date,
            'confirmations': confirmations,
            'failures': failures,
            'appearances': appearances,
            'sources': sorted(entry.get('sources', [])),
            'last_reason': " / ".join(entry.get('reasons', [])[:3]),
            'follow_state': follow_state,
            'evidence_score': evidence_score,
        }
        kept_items.append(memory_item)

        if code not in previous_map:
            new_items.append(memory_item)
        elif previous_status != 'validated' and status == 'validated':
            promoted_items.append(memory_item)

        if status == 'validated':
            today_validated_items.append(memory_item)
        else:
            today_tentative_items.append(memory_item)

    for code, previous in previous_map.items():
        if code in today_entries:
            continue

        last_seen_obj = _safe_parse_report_date(previous.get('last_seen_date', ''))
        days_missing = 0
        if today_date_obj and last_seen_obj:
            days_missing = max((today_date_obj - last_seen_obj).days, 0)

        previous_status = previous.get('status', 'tentative')
        should_drop = (
            (previous_status == 'tentative' and days_missing > TRACKING_MEMORY_TENTATIVE_EXPIRE_DAYS)
            or days_missing > TRACKING_MEMORY_KEEP_DAYS
        )
        if should_drop:
            dropped_items.append({
                'name': previous.get('name', ''),
                'code': code,
                'reason': '连续多日未再次进入今日候选，自动清除',
            })
            continue

        carried = {
            **previous,
            'days_since_seen': days_missing,
        }
        kept_items.append(carried)

    kept_items.sort(
        key=lambda item: (
            1 if item.get('status') == 'validated' else 0,
            item.get('confirmations', 0),
            item.get('evidence_score', 0),
            item.get('last_seen_date', ''),
        ),
        reverse=True,
    )
    kept_items = kept_items[:TRACKING_MEMORY_MAX_ITEMS]

    _save_tracking_memory_state({
        'updated_at': target_date,
        'items': kept_items,
    })

    validated_items = [item for item in kept_items if item.get('status') == 'validated']
    tentative_items = [item for item in kept_items if item.get('status') == 'tentative']
    return {
        'validated_items': validated_items,
        'tentative_items': tentative_items,
        'today_validated_items': today_validated_items,
        'today_tentative_items': today_tentative_items,
        'new_items': new_items,
        'promoted_items': promoted_items,
        'dropped_items': dropped_items,
        'total_items': kept_items,
        'today_seen_count': len(today_entries),
    }


def _average_numeric(values):
    """计算均值，空列表返回0。"""
    cleaned = []
    for value in values or []:
        try:
            cleaned.append(float(value))
        except (TypeError, ValueError):
            continue
    return sum(cleaned) / len(cleaned) if cleaned else 0.0


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


def _identify_latest_abnormal_bar(recent_bars):
    """识别最近4根日K中最值得跟踪的异动K线。"""
    if not recent_bars or len(recent_bars) < 2:
        return None

    abnormal_candidates = []
    start_idx = max(1, len(recent_bars) - 4)

    for idx in range(start_idx, len(recent_bars)):
        bar = recent_bars[idx]
        prev_bar = recent_bars[idx - 1]

        open_price = _safe_float(bar.get('open', 0))
        high_price = _safe_float(bar.get('high', 0))
        low_price = _safe_float(bar.get('low', 0))
        close_price = _safe_float(bar.get('close', 0))
        volume = _safe_float(bar.get('volume', 0))
        prev_close = _safe_float(prev_bar.get('close', 0))

        if min(open_price, high_price, low_price, close_price) <= 0:
            continue

        change_pct = ((close_price - prev_close) / prev_close * 100) if prev_close > 0 else (
            (close_price - open_price) / open_price * 100
        )
        amplitude_pct = ((high_price - low_price) / low_price * 100) if low_price > 0 else 0.0
        body_pct = (abs(close_price - open_price) / open_price * 100) if open_price > 0 else 0.0
        upper_shadow_pct = (
            (high_price - max(open_price, close_price)) / max(open_price, close_price) * 100
            if max(open_price, close_price) > 0 else 0.0
        )

        prev_volumes = [
            _safe_float(item.get('volume', 0))
            for item in recent_bars[max(0, idx - 3):idx]
            if _safe_float(item.get('volume', 0)) > 0
        ]
        avg_volume = _average_numeric(prev_volumes)
        volume_ratio = (volume / avg_volume) if avg_volume > 0 else 0.0

        abnormal_type = ""
        abnormal_note = ""
        abnormal_priority = 0

        if (
            close_price < open_price and change_pct <= -5
            and amplitude_pct >= 6 and volume_ratio >= 1.2
        ):
            abnormal_type = "恐怖阴线异动"
            abnormal_note = "大阴大振幅，重点看后续还能不能继续杀"
            abnormal_priority = 4
        elif upper_shadow_pct >= 3 and amplitude_pct >= 5 and volume_ratio >= 1.2:
            abnormal_type = "长上影异动"
            abnormal_note = "盘中冲高遇压，重点看承接和回收能力"
            abnormal_priority = 3
        elif (
            close_price > open_price and change_pct >= 5.5
            and body_pct >= 3.5 and volume_ratio >= 1.25
        ):
            abnormal_type = "放量大阳异动"
            abnormal_note = "第一波异动已出现，重点看回踩后是否抗跌"
            abnormal_priority = 2

        if not abnormal_type:
            continue

        abnormal_candidates.append({
            'index': idx,
            'date': _normalize_kline_date_str(bar.get('date')),
            'type': abnormal_type,
            'note': abnormal_note,
            'priority': abnormal_priority,
            'change_pct': round(change_pct, 2),
            'volume_ratio': round(volume_ratio, 2),
            'open': round(open_price, 2),
            'high': round(high_price, 2),
            'low': round(low_price, 2),
            'close': round(close_price, 2),
            'body_mid': round((open_price + close_price) / 2, 2),
            'bar': bar,
        })

    if not abnormal_candidates:
        return None

    abnormal_candidates.sort(
        key=lambda item: (
            item.get('index', 0),
            item.get('priority', 0),
            item.get('volume_ratio', 0),
            abs(item.get('change_pct', 0)),
        ),
        reverse=True,
    )
    return abnormal_candidates[0]


def _detect_washout_reclaim_subtype(recent_bars, abnormal_info):
    recent_bars = recent_bars or []
    abnormal_info = abnormal_info or {}
    abnormal_idx = int(_safe_float(abnormal_info.get('index', -1), -1))
    if abnormal_idx < 0 or abnormal_idx >= len(recent_bars):
        return ''

    post_bars = recent_bars[abnormal_idx + 1:]
    if not post_bars:
        return ''

    abnormal_bar = recent_bars[abnormal_idx]
    abnormal_high = _safe_float(abnormal_bar.get('high'))
    abnormal_low = _safe_float(abnormal_bar.get('low'))
    abnormal_open = _safe_float(abnormal_bar.get('open'))
    abnormal_close = _safe_float(abnormal_bar.get('close'))
    latest_bar = post_bars[-1]
    latest_open = _safe_float(latest_bar.get('open'))
    latest_high = _safe_float(latest_bar.get('high'))
    latest_low = _safe_float(latest_bar.get('low'))
    latest_close = _safe_float(latest_bar.get('close'))
    if min(abnormal_high, abnormal_low, abnormal_open, abnormal_close, latest_open, latest_high, latest_low, latest_close) <= 0:
        return ''

    body_top = max(abnormal_open, abnormal_close)
    body_bottom = min(abnormal_open, abnormal_close)
    strong_reclaim = latest_close >= body_top * 0.995
    close_near_high = latest_high <= 0 or (latest_high - latest_close) / latest_close <= 0.01
    low_open_reclaim = latest_open <= abnormal_close * 0.985 and latest_close >= body_top * 0.995 and close_near_high

    gap_down_seen = any(_safe_float(bar.get('open')) < abnormal_low * 0.995 for bar in post_bars)
    gap_up_seen = False
    if len(post_bars) >= 2:
        for idx, bar in enumerate(post_bars[1:], start=1):
            prev_high = _safe_float(post_bars[idx - 1].get('high'))
            bar_open = _safe_float(bar.get('open'))
            if prev_high > 0 and bar_open > prev_high * 1.01:
                gap_up_seen = True
                break
    if gap_down_seen and gap_up_seen and strong_reclaim:
        return 'gap_reclaim'
    if low_open_reclaim:
        return 'flush_open_reclaim'
    if abnormal_close < abnormal_open and strong_reclaim:
        return 'entity_bear_reclaim'
    if abnormal_info.get('type') == '长上影异动' and strong_reclaim:
        return 'upper_shadow_eat'
    return ''


def _classify_abnormal_follow_state(recent_bars, abnormal_info):
    """判断异动K线后续是抗跌、消化，还是已经转弱。"""
    abnormal_idx = abnormal_info.get('index', -1)
    if abnormal_idx < 0 or abnormal_idx >= len(recent_bars):
        return "新异动待观察", abnormal_info.get('low', 0)

    post_bars = recent_bars[abnormal_idx + 1:]
    anchor_price = round(_safe_float(abnormal_info.get('low', 0)), 2)
    if not post_bars:
        return "新异动待观察", anchor_price

    latest_bar = post_bars[-1]
    latest_close = _safe_float(latest_bar.get('close', 0))
    post_lows = [_safe_float(bar.get('low', 0)) for bar in post_bars if _safe_float(bar.get('low', 0)) > 0]
    post_volumes = [_safe_float(bar.get('volume', 0)) for bar in post_bars if _safe_float(bar.get('volume', 0)) > 0]

    post_min_low = min(post_lows) if post_lows else anchor_price
    post_avg_volume = _average_numeric(post_volumes)
    abnormal_volume = _safe_float(abnormal_info.get('bar', {}).get('volume', 0))
    volume_shrunk = abnormal_volume > 0 and post_avg_volume > 0 and post_avg_volume <= abnormal_volume * 0.75
    holds_anchor = post_min_low >= anchor_price * 0.99

    abnormal_type = abnormal_info.get('type', '')
    strong_line = _safe_float(abnormal_info.get('body_mid', anchor_price))
    digest_line = anchor_price * 1.03

    if abnormal_type == "放量大阳异动":
        strong_line = _safe_float(abnormal_info.get('close', strong_line)) * 0.98
        digest_line = min(
            _safe_float(abnormal_info.get('open', anchor_price)),
            _safe_float(abnormal_info.get('close', anchor_price)),
        ) * 0.99
    elif abnormal_type == "长上影异动":
        strong_line = max(
            _safe_float(abnormal_info.get('open', strong_line)),
            _safe_float(abnormal_info.get('close', strong_line)),
        ) * 0.995
        digest_line = _safe_float(abnormal_info.get('body_mid', digest_line)) * 0.99

    if not holds_anchor or latest_close < anchor_price * 0.995:
        return "已经转弱", anchor_price
    if latest_close >= strong_line:
        return "跌不下去", anchor_price
    if volume_shrunk and latest_close >= digest_line:
        return "缩量消化", anchor_price
    if latest_close >= anchor_price * 1.02:
        return ("缩量消化", anchor_price) if volume_shrunk else ("跌不下去", anchor_price)
    return "已经转弱", anchor_price


def _build_abnormal_follow_rule(abnormal_type, follow_state, anchor_price, abnormal_info):
    """给出异动后次日观察原则。"""
    anchor_text = f"{anchor_price:.2f}" if anchor_price else "-"
    body_mid = _safe_float(abnormal_info.get('body_mid', 0))
    body_mid_text = f"{body_mid:.2f}" if body_mid else anchor_text

    if abnormal_type == "恐怖阴线异动":
        if follow_state == "跌不下去":
            return f"只看首个60分钟能否收回阴线实体一半（约{body_mid_text}）"
        if follow_state == "缩量消化":
            return f"只做缩量后再转强，锚点不破{anchor_text}"
        if follow_state == "新异动待观察":
            return "先看次日是否继续缩量，不急着接"
        return f"跌破{anchor_text}说明异动后无承接，先取关"

    if abnormal_type == "长上影异动":
        if follow_state == "跌不下去":
            return f"只看60分钟能否重新站回实体区（约{body_mid_text}以上）"
        if follow_state == "缩量消化":
            return f"等缩量后再收复实体，不破{anchor_text}才有资格继续看"
        if follow_state == "新异动待观察":
            return "先看次日能否站回实体，不追长上影当天"
        return f"承接已经走弱，跌回{anchor_text}附近以下就先放弃"

    if follow_state == "跌不下去":
        return f"只看回踩不破{anchor_text}后的60分钟再转强"
    if follow_state == "缩量消化":
        return f"缩量消化后再等60分钟确认，锚点{anchor_text}"
    if follow_state == "新异动待观察":
        return "先看次日承接，不追大阳当天"
    return f"跌破{anchor_text}说明第一波异动失效"


def _refine_abnormal_follow_display(anchor_price, action_rule, minute_plan=None):
    minute_plan = minute_plan or {}
    minute_guard = _round_or_none(
        minute_plan.get('confirm_support_60m') or minute_plan.get('structure_stop_30m')
    )
    base_anchor = _round_or_none(anchor_price)
    if minute_guard is not None and base_anchor is not None:
        display_anchor_price = max(base_anchor, minute_guard)
    else:
        display_anchor_price = minute_guard if minute_guard is not None else base_anchor
    display_rule = str(action_rule or '').strip()
    confirm_rule = str(minute_plan.get('confirm_rule_60m', '') or '').strip()
    if confirm_rule:
        display_rule = confirm_rule if confirm_rule.startswith('只看') else f"只看{confirm_rule}"
    return display_anchor_price, display_rule or str(action_rule or '').strip()


def _format_abnormal_observation_columns(item):
    item = item or {}
    history_anchor = _round_or_none(item.get('anchor_price'))
    nextday_guard = _round_or_none(item.get('display_anchor_price'))
    if nextday_guard is None:
        nextday_guard = history_anchor
    history_text = f"{history_anchor:.2f}" if history_anchor is not None else "-"
    nextday_text = f"{nextday_guard:.2f}" if nextday_guard is not None else "-"
    return history_text, nextday_text


def _format_frozen_plan_columns(plan):
    plan = plan or {}
    entry_low = _round_or_none(plan.get('entry_range_low'))
    entry_high = _round_or_none(plan.get('entry_range_high'))
    if entry_low is not None and entry_high is not None:
        entry_text = f"{entry_low:.2f}-{entry_high:.2f}"
    elif entry_low is not None:
        entry_text = f"{entry_low:.2f}"
    else:
        entry_text = "-"
    confirm_price = _round_or_none(plan.get('confirm_price_60m'))
    confirm_text = f"{confirm_price:.2f}" if confirm_price is not None else "-"
    history_anchor_text, nextday_guard_text = _format_abnormal_observation_columns(plan)
    execution_stop = _round_or_none(plan.get('execution_stop') or plan.get('effective_stop'))
    execution_text = f"{execution_stop:.2f}" if execution_stop is not None else "-"
    return entry_text, confirm_text, nextday_guard_text, history_anchor_text, execution_text


def build_abnormal_watch_pool(
    target_date,
    candidate_stocks,
    mainline_name='',
    top_n=5,
    scan_limit=None,
    allow_degraded_snapshot=False,
    fast_fail=False,
):
    """构建“异动后能不能跌下去”的观察池。"""
    if not candidate_stocks:
        return []

    state_score_map = {
        '跌不下去': 40,
        '缩量消化': 32,
        '新异动待观察': 24,
        '已经转弱': 8,
    }
    type_score_map = {
        '恐怖阴线异动': 12,
        '长上影异动': 9,
        '放量大阳异动': 8,
    }

    watch_pool = []
    seen_codes = set()

    candidate_iter = candidate_stocks[:scan_limit] if scan_limit else candidate_stocks

    for stock in candidate_iter:
        code = normalize_stock_code(stock.get('code', ''))
        if not code or code in seen_codes:
            continue
        seen_codes.add(code)

        recent_bars = fetch_recent_price_bars(
            code,
            target_date,
            lookback_days=10,
            fast_fail=fast_fail,
        )
        if len(recent_bars) < 4:
            if allow_degraded_snapshot:
                sector = stock.get('sector', '') or stock.get('所属行业', '') or stock.get('所属板块', '')
                is_mainline = sector_name_matches(sector, mainline_name) if mainline_name else False
                base_score = _safe_float(stock.get('tomorrow_strength', stock.get('score', 0)))
                follow_state = '跌不下去' if (is_mainline or base_score >= 70) else '新异动待观察'
                abnormal_type = '放量大阳异动'
                setup_signal = _resolve_abnormal_setup_signal(abnormal_type, follow_state)
                anchor_price = _safe_float(stock.get('close', stock.get('price', 0)))
                abnormal_score = (
                    state_score_map.get(follow_state, 0)
                    + type_score_map.get(abnormal_type, 0)
                    + min(int(base_score / 10), 12)
                    + (8 if is_mainline else 0)
                )
                watch_pool.append({
                    'name': stock.get('name', '未知'),
                    'code': code,
                    'sector': sector or '未知',
                    'abnormal_date': target_date,
                    'abnormal_type': abnormal_type,
                    'follow_state': follow_state,
                    'setup_signal_id': setup_signal.get('id', ''),
                    'setup_signal_label': setup_signal.get('label', ''),
                    'setup_signal_phase': setup_signal.get('phase', ''),
                    'anchor_price': round(anchor_price, 2) if anchor_price else 0,
                    'action_rule': "MVP快照回退：先看次日是否继续强于市场，再等60分钟确认。",
                    'abnormal_note': '缺少近期K线，先按强势/主线优先级纳入异常观察。',
                    'abnormal_score': abnormal_score,
                    'source': stock.get('source', ''),
                    'is_mainline': is_mainline,
                    'is_degraded_snapshot': True,
                    'degraded_reason': 'missing_recent_bars',
                    'formal_decision_eligible': False,
                })
            continue

        abnormal_info = _identify_latest_abnormal_bar(recent_bars)
        if not abnormal_info:
            continue

        washout_reclaim_subtype = _detect_washout_reclaim_subtype(recent_bars, abnormal_info)
        follow_state, anchor_price = _classify_abnormal_follow_state(recent_bars, abnormal_info)
        setup_signal = _resolve_abnormal_setup_signal(abnormal_info.get('type', ''), follow_state)
        signal_type = _map_setup_id_to_signal_type(setup_signal.get('id', ''))
        latest_close = _safe_float(recent_bars[-1].get('close', 0))
        minute_plan = build_intraday_execution_plan(
            code,
            target_date,
            latest_close,
            signal_type=signal_type,
            fallback_stop=latest_close * (1 - MAX_SINGLE_TRADE_LOSS_PCT) if latest_close > 0 else None,
        ) if latest_close > 0 else {}
        base_action_rule = _build_abnormal_follow_rule(
            abnormal_info.get('type', ''),
            follow_state,
            anchor_price,
            abnormal_info,
        )
        display_anchor_price, display_action_rule = _refine_abnormal_follow_display(
            anchor_price,
            base_action_rule,
            minute_plan,
        )
        sector = stock.get('sector', '') or stock.get('所属行业', '') or stock.get('所属板块', '')
        is_mainline = sector_name_matches(sector, mainline_name) if mainline_name else False
        base_score = _safe_float(stock.get('tomorrow_strength', stock.get('score', 0)))
        abnormal_score = (
            state_score_map.get(follow_state, 0)
            + type_score_map.get(abnormal_info.get('type', ''), 0)
            + min(int(base_score / 10), 12)
            + (8 if is_mainline else 0)
        )

        watch_pool.append({
            'name': stock.get('name', '未知'),
            'code': code,
            'sector': sector or '未知',
            'abnormal_date': abnormal_info.get('date', ''),
            'abnormal_type': abnormal_info.get('type', ''),
            'abnormal_follow_state': follow_state,
            'follow_state': follow_state,
            'setup_signal_id': setup_signal.get('id', ''),
            'setup_signal_label': setup_signal.get('label', ''),
            'setup_signal_phase': setup_signal.get('phase', ''),
            'anchor_price': round(anchor_price, 2) if anchor_price else 0,
            'display_anchor_price': display_anchor_price,
            'confirm_price_60m': _round_or_none(minute_plan.get('confirm_price_60m')),
            'confirm_support_60m': _round_or_none(minute_plan.get('confirm_support_60m')),
            'structure_stop_30m': _round_or_none(minute_plan.get('structure_stop_30m')),
            'confirm_rule_60m': str(minute_plan.get('confirm_rule_60m', '') or '').strip(),
            'washout_reclaim_subtype': washout_reclaim_subtype,
            'action_rule': display_action_rule,
            'raw_action_rule': base_action_rule,
            'abnormal_note': abnormal_info.get('note', ''),
            'abnormal_score': abnormal_score,
            'source': stock.get('source', ''),
            'is_mainline': is_mainline,
            'is_degraded_snapshot': False,
            'degraded_reason': '',
            'formal_decision_eligible': True,
        })

    watch_pool.sort(
        key=lambda item: (
            item.get('abnormal_score', 0),
            item.get('is_mainline', False),
            item.get('abnormal_date', ''),
        ),
        reverse=True,
    )
    return watch_pool[:top_n]


def get_abnormal_rank_adjustment(abnormal_item):
    return analysis_utils.get_abnormal_rank_adjustment(abnormal_item)


def get_abnormal_follow_risk_signal(stock):
    """将异动后状态映射成 Step 3 风险灯号和风险修正。"""
    if _is_degraded_abnormal_snapshot(stock) or bool(stock.get('abnormal_is_degraded_snapshot')):
        return {
            'light': '🟠 橙灯',
            'delta': 8,
            'reason': '当前仅有降级异常快照，不能把它当正式承接证据',
            'forecast': '先补齐真实K线承接证据，再决定是否继续跟踪',
        }

    state = str(stock.get('abnormal_follow_state', '') or '').strip()
    abnormal_type = str(stock.get('abnormal_type', '') or '').strip()
    setup_label = str(stock.get('abnormal_setup_signal_label', '') or '').strip()
    signal_name = setup_label or abnormal_type or '异动'
    watch_source = str(stock.get('watch_source', '') or '').strip()

    if watch_source == 'gem_breathing_20cm' or state == '预启动呼吸感':
        return {
            'light': '🟡 黄灯',
            'delta': -4,
            'reason': '创业板20cm预启动仍在收拢观察期，先确认它有没有走成右侧确认',
            'forecast': '先看右侧确认和60分钟确认，再决定是否升级到30%条件试错',
        }

    if not state:
        return {
            'light': '🟡 黄灯',
            'delta': 0,
            'reason': '无异动承接信息',
            'forecast': '',
        }

    if state == '跌不下去':
        return {
            'light': '🟢 绿灯',
            'delta': -12,
            'reason': f"{signal_name}承接强，暂未看到继续下杀",
            'forecast': '异动后承接强，明日重点等60分钟确认',
        }
    if state == '缩量消化':
        return {
            'light': '🟡 黄灯',
            'delta': -6,
            'reason': f"{signal_name}正在缩量消化，暂未失守锚点",
            'forecast': '正在缩量消化，明日先看能否再转强',
        }
    if state == '新异动待观察':
        return {
            'light': '🟠 橙灯',
            'delta': 6,
            'reason': f"{signal_name}刚出现，承接尚未被验证",
            'forecast': '异动刚出现，明日先看承接，不宜直接乐观',
        }
    return {
        'light': '🔴 红灯',
        'delta': 22,
        'reason': f"{signal_name}已经转弱，承接明显不够",
        'forecast': '异动后承接转弱，明日易低开或继续下杀',
    }


def get_trade_permission(
    stock,
    mainline_name='',
    conviction_codes=None,
    leader_memory_codes=None,
    final_gate=None,
    state_machine_snapshot=None,
):
    """根据环境闸门 + 主线脉冲阶段 + 个股承接，分配执行权限。"""
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
    """构建主线衰竭跟踪表和退出等级
    
    Args:
        data: 全量数据
        market_analysis: AI分析结果(原始)
        dragon_stocks: 连板龙头股列表
        enhanced_main_sectors: 增强版主线名称列表（含资金流向fallback），与报告开头一致
    """
    # 灯号语义映射（趋势狙击版）
    # 绿灯=主线健康，黄灯=主升强化，橙灯=退潮预警，红灯=退潮确认
    action_map = {
        '绿灯': '主线健康，可继续做',
        '黄灯': '主升强化，优先做核心',
        '橙灯': '退潮预警，禁止新增',
        '红灯': '退潮确认，尽快退出'
    }
    severity_map = {'绿灯': 0, '黄灯': 1, '橙灯': 2, '红灯': 3}

    sector_fund_flow = data.get('sector_fund_flow', {})
    inflow_sectors = sector_fund_flow.get('inflow', []) if sector_fund_flow else []
    outflow_sectors = sector_fund_flow.get('outflow', []) if sector_fund_flow else []
    
    # v2.3.33统一：优先使用增强版主线（与报告开头一致）
    if enhanced_main_sectors:
        tracked_sector = enhanced_main_sectors[0] if enhanced_main_sectors else ''
    else:
        main_sectors = market_analysis.get('main_sectors', []) if market_analysis else []
        tracked_sector = main_sectors[0].get('name', '') if main_sectors else ''
    
    if not tracked_sector and inflow_sectors:
        tracked_sector = inflow_sectors[0].get('name', '')

    if not tracked_sector:
        return {
            'sector_name': '暂无明确主线',
            'star_level': '-',
            'leader_name': '-',
            'event_risk_summary': '无主线，无需评估事件兑现风险',
            'overall_level': '红灯',
            'overall_action': action_map['红灯'],
            'exit_conditions': ['暂无明确主线，不值得死在里面，优先空仓或等待新主线'],
            'signals': [
                {'layer': '主线地位复核', 'status': '暂无明确主线', 'level': '红灯', 'action': '没有主线就不能参与，已有仓位也要退出'},
                {'layer': '龙头健康度', 'status': '无可跟踪龙头', 'level': '红灯', 'action': '不能新开仓，已有仓位不做旧线自救'},
                {'layer': '板块内部结构', 'status': '主线结构不存在', 'level': '红灯', 'action': '不参与杂毛补涨，已有仓位按退场处理'},
                {'layer': '持仓个股承接', 'status': '无主线核心可跟踪', 'level': '红灯', 'action': '没有承接就不参与，已有仓位直接退出'},
                {'layer': '事件落地风险', 'status': '无主线，无需评估事件风险', 'level': '黄灯', 'action': action_map['黄灯']},
                {'layer': '替代主线流向', 'status': '等待新主线承接', 'level': '黄灯', 'action': action_map['黄灯']},
            ]
        }

    inflow_map = {s.get('name', ''): s.get('zljlr', 0) for s in inflow_sectors}
    outflow_map = {s.get('name', ''): abs(s.get('zljlr', 0)) for s in outflow_sectors}

    target_date = str(data.get('target_date', '') or '')
    sector_inflow = inflow_map.get(tracked_sector, 0)
    sector_outflow = outflow_map.get(tracked_sector, 0)
    zt_pool_by_sector = data.get('zt_pool_by_sector', {})
    dt_pool_by_sector = data.get('dt_pool_by_sector', {})
    sector_zt_count = len(zt_pool_by_sector.get(tracked_sector, []))
    sector_dt_count = len(dt_pool_by_sector.get(tracked_sector, []))
    hot_weight = get_sector_hotlist_weight(tracked_sector, data.get('tag_distribution', {}))
    inflow_history = load_recent_sector_flow_history(target_date, tracked_sector, lookback_days=2)
    mainline_snapshot = get_mainline_star_level(
        sector_inflow,
        sector_zt_count,
        dt_count=sector_dt_count,
        hot_weight=hot_weight,
        inflow_history=inflow_history,
    )
    star_level = mainline_snapshot.get('star_level', '⭐')
    star_rank = mainline_snapshot.get('star_rank', 1)
    mainline_score_pct = _safe_float(mainline_snapshot.get('score_pct'))

    prev_inflow = inflow_history[-1]['inflow'] if inflow_history else None
    prev2_inflow = inflow_history[-2]['inflow'] if len(inflow_history) >= 2 else None
    inflow_shrinking_two_days = mainline_snapshot.get('flow_trend') == 'shrinking'

    signals = []

    # 1. 主线地位复核
    mainline_status = (
        f"{tracked_sector} {star_level}（综合{mainline_score_pct:.0f}分），"
        f"净流入{sector_inflow:+.1f}亿，涨停{sector_zt_count}只，跌停{sector_dt_count}只，热榜占比{hot_weight:.1f}%"
    )
    if sector_outflow > 12 and sector_dt_count >= 2:
        mainline_level = '红灯'
    else:
        mainline_level = _score_to_level(mainline_score_pct)
    if inflow_shrinking_two_days and mainline_level == '绿灯':
        mainline_level = '黄灯'
    elif inflow_shrinking_two_days and mainline_level == '黄灯':
        mainline_level = '橙灯'
    if mainline_snapshot.get('trend_label'):
        mainline_status += f"，{mainline_snapshot.get('trend_label')}"
    signals.append({
        'layer': '主线地位复核',
        'status': mainline_status,
        'level': mainline_level,
        'action': action_map[mainline_level]
    })

    # 2. 龙头健康度
    leader = get_sector_leader(tracked_sector, dragon_stocks, dt_pool_by_sector)
    lhb_net_sell_codes = {
        normalize_stock_code(item.get('code', ''))
        for item in data.get('lhb_net_sell_top10', [])
    }
    leader_name = '-'
    if leader:
        leader_name = leader.get('name', '-')
        leader_status = f"{leader.get('name', '-')}" \
                        f"({leader.get('zt_type', '-')})"
        if leader.get('is_limit_down'):
            leader_level = '红灯'
            leader_status += "，龙头已跌停失守"
        elif leader.get('code', '') in lhb_net_sell_codes:
            leader_level = '橙灯'
            leader_status += "，龙虎榜出现净卖出"
        elif leader.get('lianban', 0) >= 3:
            leader_level = '绿灯'
            leader_status += f"，连板高度{leader.get('lianban', 0)}板"
        else:
            leader_level = '黄灯'
            leader_status += "，出现分歧但未失守"
    else:
        leader_level = '红灯' if sector_dt_count >= 1 else '橙灯'
        leader_status = f"{tracked_sector}暂无明确涨停龙头，板块承接偏弱"
    signals.append({
        'layer': '龙头健康度',
        'status': leader_status,
        'level': leader_level,
        'action': action_map[leader_level]
    })

    # 3. 板块内部结构
    structure_status = f"涨停{sector_zt_count}只 / 跌停{sector_dt_count}只"
    if sector_zt_count >= 15 and sector_dt_count == 0:
        structure_level = '绿灯'
        structure_status += "，主升结构完整"
    elif sector_zt_count >= 5 and sector_dt_count <= 1:
        structure_level = '黄灯'
        structure_status += "，正常分歧，仍有反复空间"
    elif sector_dt_count >= 3 or (sector_outflow > 10 and sector_zt_count < 5):
        structure_level = '红灯'
        structure_status += "，跌停扩散，退潮明显"
    else:
        structure_level = '橙灯'
        structure_status += "，涨停回落，结构开始松动"
    signals.append({
        'layer': '板块内部结构',
        'status': structure_status,
        'level': structure_level,
        'action': action_map[structure_level]
    })

    # 4. 持仓个股承接（用主线核心股代理）
    core_stock = get_sector_core_hot_stock(tracked_sector, data.get('hot_rank_top30', []))
    price_lines = None
    price_anchor_stock = leader if leader else None
    if core_stock:
        change_pct = core_stock.get('change_pct', 0)
        hot_rank = core_stock.get('hot_rank', 0)
        core_status = f"{core_stock.get('name', '-')}" \
                      f"热榜第{hot_rank}，涨幅{change_pct:+.2f}%"
        if not price_anchor_stock:
            price_anchor_stock = core_stock
        price_lines = calculate_exit_price_lines(price_anchor_stock, data.get('stock_full_info', {}))
        recent_bars = fetch_recent_price_bars(
            price_anchor_stock.get('code', ''), target_date, lookback_days=max(STOP_PRIOR_LOW_TRADING_DAYS + 8, 15)
        )
        stop_loss, anchor_d, rule_hint = compute_stop_loss_mainline_anchor(recent_bars)
        if price_lines and stop_loss:
            price_lines.update({
                'anchor_name': price_anchor_stock.get('name', '-'),
                'stop_loss': stop_loss,
                'stop_anchor_date': anchor_d,
                'stop_rule': f"跌破{stop_loss:.2f}直接卖出（{rule_hint}）",
            })
        elif price_lines:
            price_lines.update({
                'anchor_name': price_anchor_stock.get('name', '-'),
                'stop_rule': 'K线不足，暂用行情低点作参考，有完整K线后按近5个交易日前低/阴线规则重算',
            })
        if change_pct <= -9.5:
            core_level = '红灯'
            core_status += "，核心股跌停"
        elif hot_rank <= 10 and change_pct > 0:
            core_level = '绿灯'
            core_status += "，仍是板块交易核心"
        elif hot_rank <= 20 and change_pct >= -2:
            core_level = '黄灯'
            core_status += "，承接尚可但需要盯紧"
        else:
            core_level = '橙灯'
            core_status += "，放量不涨或失去核心地位"
    else:
        core_status = f"{tracked_sector}在热榜核心区缺少明确承接"
        if hot_weight >= 3:
            core_level = '黄灯'
            core_status += f"，但热榜占比仍有{hot_weight:.1f}%"
        elif hot_weight >= 1:
            core_level = '橙灯'
            core_status += f"，热榜占比仅{hot_weight:.1f}%"
        else:
            core_level = '红灯'
            core_status += "，主线关注度明显流失"
    signals.append({
        'layer': '持仓个股承接',
        'status': core_status,
        'level': core_level,
        'action': action_map[core_level]
    })

    # 5. 事件落地风险
    event_level = '绿灯'
    event_status = "未发现与当前主线强相关的临近兑现事件"
    target_dt = None
    try:
        target_dt = datetime.datetime.strptime(str(data.get('target_date', '') or ''), "%Y-%m-%d").date()
    except Exception:
        target_dt = None

    related_event_hits = []
    xuangubao_data = data.get('xuangubao_data')
    hot_rank_data = data.get('hot_rank_top30', [])
    for event in data.get('calendar_events', [])[:10]:
        event_title = event.get('title', '')
        if not event_title:
            continue
        event_sector = analyze_event_sector(event_title, "", xuangubao_data, hot_rank_data)
        if not event_sector:
            continue
        if tracked_sector not in event_sector and event_sector not in tracked_sector:
            continue

        event_date_raw = str(event.get('date', '') or '')
        days_to_event = None
        if target_dt and event_date_raw:
            try:
                clean_date = event_date_raw.replace('/', '-')
                event_dt = datetime.datetime.strptime(clean_date, "%Y-%m-%d").date()
                days_to_event = (event_dt - target_dt).days
            except Exception:
                days_to_event = None

        star = event.get('star', 0) or 0
        if days_to_event is not None and days_to_event <= 2 and star >= 4 and (sector_inflow <= 0 or sector_dt_count >= 1):
            risk_level = '红灯'
            summary = f"{event_title}临近且{tracked_sector}承接失败，警惕利好出尽"
        elif days_to_event is not None and days_to_event <= 2 and star >= 4:
            risk_level = '橙灯'
            summary = f"{event_title}临近，{tracked_sector}已进入兑现敏感区"
        elif days_to_event is not None and days_to_event <= 5 and star >= 3:
            risk_level = '黄灯'
            summary = f"{event_title}进入博弈窗口，注意抢跑后兑现"
        else:
            risk_level = '绿灯'
            summary = f"{event_title}仍属中期催化，暂未进入兑现压力区"

        related_event_hits.append({
            'level': risk_level,
            'summary': summary,
            'days_to_event': days_to_event if days_to_event is not None else 99,
            'star': star
        })

    if related_event_hits:
        related_event_hits.sort(
            key=lambda x: (severity_map[x['level']], -x['star'], -x['days_to_event']),
            reverse=True
        )
        top_event_hit = related_event_hits[0]
        event_level = top_event_hit['level']
        event_status = top_event_hit['summary']

    if leader and leader.get('is_limit_down') and event_level in ('黄灯', '橙灯'):
        event_level = '红灯'
        event_status = f"{leader.get('name', tracked_sector)}首次跌停且事件临近，直接按退潮处理"
    elif inflow_shrinking_two_days and event_level in ('黄灯', '橙灯'):
        event_level = '橙灯'
        event_status = (
            f"{tracked_sector}资金连续两天收缩且事件临近"
            f"（{prev2_inflow:+.1f}亿→{prev_inflow:+.1f}亿→{sector_inflow:+.1f}亿）"
        )

    signals.append({
        'layer': '事件落地风险',
        'status': event_status,
        'level': event_level,
        'action': action_map[event_level]
    })

    # 6. 替代主线流向
    replacement_candidates = []
    for sector in inflow_sectors:
        sector_name = sector.get('name', '')
        if not sector_name or sector_name == tracked_sector:
            continue
        replacement_candidates.append({
            'name': sector_name,
            'inflow': sector.get('zljlr', 0),
            'zt_count': len(zt_pool_by_sector.get(sector_name, [])),
            'hot_weight': get_sector_hotlist_weight(sector_name, data.get('tag_distribution', {}))
        })
    replacement_candidates.sort(
        key=lambda x: (x.get('inflow', 0), x.get('zt_count', 0), x.get('hot_weight', 0)),
        reverse=True
    )

    replacement_sector = replacement_candidates[0] if replacement_candidates else None
    replacement_name = ''
    if not replacement_sector:
        replacement_level = '绿灯'
        replacement_status = "未见明显替代主线，资金仍未完成切换"
    else:
        replacement_name = replacement_sector.get('name', '')
        replacement_status = (
            f"{replacement_name} 净流入+{replacement_sector.get('inflow', 0):.1f}亿，"
            f"涨停{replacement_sector.get('zt_count', 0)}只，"
            f"热榜占比{replacement_sector.get('hot_weight', 0):.1f}%"
        )
        if sector_inflow <= 0 and replacement_sector.get('inflow', 0) > 5 and replacement_sector.get('zt_count', 0) >= 5:
            replacement_level = '红灯'
            replacement_status += "，新主线已明显承接旧主线资金"
        elif replacement_sector.get('inflow', 0) > sector_inflow and replacement_sector.get('zt_count', 0) >= max(5, sector_zt_count):
            replacement_level = '橙灯'
            replacement_status += "，资金开始切向替代主线"
        elif replacement_sector.get('inflow', 0) > sector_inflow or replacement_sector.get('hot_weight', 0) > hot_weight + 1:
            replacement_level = '黄灯'
            replacement_status += "，替代方向开始试探"
        else:
            replacement_level = '绿灯'
            replacement_status += "，暂未形成有效替代"
    signals.append({
        'layer': '替代主线流向',
        'status': replacement_status,
        'level': replacement_level,
        'action': action_map[replacement_level]
    })

    leader_lianban = _safe_float(leader.get('lianban', 0)) if leader else 0.0
    leader_score = _clamp(
        _level_to_score(leader_level)
        + max(leader_lianban - 2, 0) * 6.0
        - (10.0 if leader and leader.get('code', '') in lhb_net_sell_codes else 0.0),
        0.0,
        100.0,
    )
    structure_score = _clamp(
        _level_to_score(structure_level)
        + min(sector_zt_count, 15) * 1.2
        - min(sector_dt_count, 4) * 8.0,
        0.0,
        100.0,
    )
    core_score = _clamp(
        _level_to_score(core_level)
        + (_safe_float(core_stock.get('change_pct')) * 2.0 if core_stock else -6.0)
        - (6.0 if not core_stock else 0.0),
        0.0,
        100.0,
    )
    event_score = _clamp(_level_to_score(event_level), 0.0, 100.0)
    replacement_score = _clamp(_level_to_score(replacement_level), 0.0, 100.0)
    overall_score = (
        mainline_score_pct * 0.26
        + leader_score * 0.18
        + structure_score * 0.18
        + core_score * 0.16
        + event_score * 0.12
        + replacement_score * 0.10
    )

    core_signal_levels = [signals[0]['level'], signals[1]['level'], signals[2]['level'], signals[4]['level']]
    core_orange_or_red = sum(1 for level in core_signal_levels if severity_map[level] >= 2)
    max_level = max(signals, key=lambda x: severity_map[x['level']])['level']

    if event_level == '红灯' or leader_level == '红灯' or structure_level == '红灯':
        overall_level = '红灯'
    elif overall_score < 32:
        overall_level = '红灯'
    elif event_level == '橙灯' and mainline_level in ('黄灯', '橙灯', '红灯'):
        overall_level = '橙灯'
    elif replacement_level in ('橙灯', '红灯') and mainline_level in ('黄灯', '橙灯', '红灯'):
        overall_level = '橙灯'
    elif overall_score < 52 or core_orange_or_red >= 2:
        overall_level = '橙灯'
    elif overall_score < 70 or severity_map[max_level] >= 2:
        overall_level = '黄灯'
    else:
        overall_level = '绿灯'

    personal_exit = [
        '跌破止损线（最近前低）立即卖出，不讨论',
        '买入后仅3~5个交易日观察期，走势不及预期即卖（卖出线即止损线）',
        '当日放量大阳线为理想主动卖点：他人眼中的确定性买点，本模式作减仓/清仓点',
    ]
    exit_conditions = []
    if sector_inflow <= 0 or star_rank <= 2:
        exit_conditions.append(f"{tracked_sector}资金转负或主线星级跌破⭐⭐⭐")
    if leader and leader.get('is_limit_down'):
        exit_conditions.append(f"{leader.get('name', tracked_sector)}首次跌停或龙头失守")
    elif leader and leader.get('code', '') in lhb_net_sell_codes:
        exit_conditions.append(f"{leader.get('name', tracked_sector)}出现龙虎榜净卖出")
    if event_level in ('橙灯', '红灯'):
        exit_conditions.append(event_status)
    if sector_dt_count >= 2:
        exit_conditions.append(f"{tracked_sector}板块跌停扩散到{sector_dt_count}只")
    if replacement_name and replacement_level in ('橙灯', '红灯'):
        exit_conditions.append(f"资金切向{replacement_name}，旧主线不再独占")
    if not exit_conditions:
        exit_conditions.append(f"{tracked_sector}仍是主线，允许正常分歧，继续待在主线里")
    exit_conditions = personal_exit + exit_conditions

    # 灯号语义映射（趋势狙击版）
    action_map = {
        '绿灯': '主线健康，可继续做',
        '黄灯': '主升强化，优先做核心',
        '橙灯': '退潮预警，禁止新增',
        '红灯': '退潮确认，尽快退出'
    }
    
    participation_advice = {
        '绿灯': "可参与，可继续粘住最强趋势",
        '黄灯': "优先围绕主线核心，继续持有最强",
        '橙灯': "禁止新增，旧仓去弱留强，不强就卖",
        '红灯': "停止参与，已有仓位尽快退出"
    }

    return {
        'sector_name': tracked_sector,
        'star_level': star_level,
        'leader_name': leader_name,
        'event_risk_summary': event_status,
        'overall_level': overall_level,
        'overall_score': round(overall_score, 1),
        'mainline_score_pct': round(mainline_score_pct, 1),
        'score_detail': {
            '主线': round(mainline_score_pct, 1),
            '龙头': round(leader_score, 1),
            '结构': round(structure_score, 1),
            '承接': round(core_score, 1),
            '事件': round(event_score, 1),
            '替代': round(replacement_score, 1),
        },
        'mainline_component_scores': mainline_snapshot.get('component_scores', {}),
        'mainline_trend_label': mainline_snapshot.get('trend_label', ''),
        'overall_action': action_map[overall_level],
        'participation_advice': participation_advice[overall_level],
        'exit_conditions': exit_conditions[:8],
        'price_lines': price_lines,
        'signals': signals
    }


def merge_position_gate(position_level, exit_analysis):
    return analysis_utils.merge_position_gate(position_level, exit_analysis)


def build_market_phase_context(data, target_date, emit_logs=True):
    """构建日报/单票共用的市场环境上下文，避免不同入口各自推导。"""
    result = build_market_phase_context_contract(
        data,
        target_date,
        analyze_market_zhongshu=analyze_market_zhongshu,
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


def _trim_bars_to_target_date(bars, target_date):
    target_norm = _normalize_kline_date_str(target_date)
    if not bars:
        return []

    trimmed = []
    for bar in bars:
        date_text = _normalize_kline_date_str(bar.get('date') or bar.get('datetime') or '')
        if target_norm and date_text and date_text > target_norm:
            continue
        normalized = dict(bar)
        if date_text:
            normalized['date'] = date_text
        trimmed.append(normalized)
    return sorted(trimmed, key=lambda x: str(x.get('date', '')))


def _same_price_level(a, b, tolerance=0.011):
    a = _safe_float(a, 0.0)
    b = _safe_float(b, 0.0)
    if a <= 0 or b <= 0:
        return False
    return abs(a - b) <= tolerance


def _is_near_anchor_price(value, anchor, pct=0.01, min_abs=0.03):
    value = _safe_float(value, 0.0)
    anchor = _safe_float(anchor, 0.0)
    if value <= 0 or anchor <= 0:
        return False
    return abs(value - anchor) <= max(abs(anchor) * pct, min_abs)


def _append_trade_price_component(components, label, price):
    price = _round_or_none(price)
    if price is None or price <= 0:
        return
    for item in components:
        if _same_price_level(item.get('price'), price):
            labels = item.setdefault('labels', [])
            if label and label not in labels:
                labels.append(label)
            return
    components.append({
        'price': price,
        'labels': [label] if label else [],
    })


def _order_trade_price_labels(labels):
    preferred = ['前低', '支撑', '止损']
    ordered = []
    for label in preferred:
        if label in labels and label not in ordered:
            ordered.append(label)
    for label in labels:
        if label not in ordered:
            ordered.append(label)
    return ordered


def _build_trade_price_focus(minute_plan=None, stop_plan=None):
    minute_plan = minute_plan or {}
    stop_plan = stop_plan or {}

    confirm_price = _safe_float(minute_plan.get('confirm_price_60m'))
    support_price = _safe_float(minute_plan.get('confirm_support_60m'))
    structure_stop_30m = _safe_float(minute_plan.get('structure_stop_30m'))
    plan_structure_stop = _safe_float(stop_plan.get('structure_stop'))
    plan_structure_label = str(stop_plan.get('structure_label', '') or '').strip()
    daily_anchor_stop = _safe_float(stop_plan.get('daily_anchor_stop'))
    breakout_open_anchor = _safe_float(stop_plan.get('breakout_open_anchor'))
    breakout_limit_anchor = _safe_float(stop_plan.get('breakout_limit_anchor'))
    effective_stop = _safe_float(stop_plan.get('effective_stop'))
    hard_stop = _safe_float(stop_plan.get('hard_stop'))

    raw_structure_stop = structure_stop_30m or plan_structure_stop
    execution_stop = effective_stop if effective_stop > 0 else (raw_structure_stop or hard_stop or 0.0)
    stop_overridden_to_hard = (
        raw_structure_stop > 0 and hard_stop > 0 and execution_stop > 0
        and _same_price_level(execution_stop, hard_stop)
        and raw_structure_stop < hard_stop - 0.011
    )

    components = []
    confluence_reasons = []
    if execution_stop > 0:
        _append_trade_price_component(components, '止损', execution_stop)

    if not stop_overridden_to_hard and execution_stop > 0:
        if support_price > 0 and _is_near_anchor_price(support_price, execution_stop):
            _append_trade_price_component(components, '支撑', support_price)
        if daily_anchor_stop > 0 and _is_near_anchor_price(daily_anchor_stop, execution_stop):
            _append_trade_price_component(components, '前低', daily_anchor_stop)
        if breakout_open_anchor > 0 and _is_near_anchor_price(breakout_open_anchor, execution_stop, pct=0.015, min_abs=0.05):
            _append_trade_price_component(components, '支撑', breakout_open_anchor)
            confluence_reasons.append('关键大阳开盘价')
        if breakout_limit_anchor > 0 and _is_near_anchor_price(breakout_limit_anchor, execution_stop, pct=0.015, min_abs=0.05):
            _append_trade_price_component(components, '支撑', breakout_limit_anchor)
            confluence_reasons.append('涨停价')
        if plan_structure_stop > 0 and not _same_price_level(plan_structure_stop, structure_stop_30m):
            anchor_label = '前低' if plan_structure_label and '30分钟' not in plan_structure_label else '止损'
            if _is_near_anchor_price(plan_structure_stop, execution_stop):
                _append_trade_price_component(components, anchor_label, plan_structure_stop)

    if not components and support_price > 0:
        _append_trade_price_component(components, '支撑', support_price)

    zone_prices = [item.get('price') for item in components if item.get('price')]
    zone_low = min(zone_prices) if zone_prices else 0.0
    zone_high = max(zone_prices) if zone_prices else 0.0
    key_zone_display = "-"
    if zone_low > 0 and zone_high > 0:
        if _same_price_level(zone_low, zone_high):
            key_zone_display = f"{zone_low:.2f}"
        else:
            key_zone_display = f"{zone_low:.2f}~{zone_high:.2f}"

    raw_labels = []
    for item in components:
        raw_labels.extend(item.get('labels', []))
    ordered_labels = _order_trade_price_labels(raw_labels)

    zone_badge = ""
    note_text = ""
    if stop_overridden_to_hard:
        zone_badge = "结构过深"
        note_text = "原结构止损过深，执行上收至单笔-5%硬止损。"
    elif len(ordered_labels) >= 2:
        zone_badge = "/".join(ordered_labels)
        note_text = f"{zone_badge}靠近，视为同一关键带。"
    elif ordered_labels:
        note_text = f"当前关键位主要看{ordered_labels[0]}。"
    if confluence_reasons:
        confluence_text = "、".join(dict.fromkeys(confluence_reasons))
        note_text = f"{note_text}且贴近{confluence_text}附近。" if note_text else f"该位置贴近{confluence_text}附近。"

    discipline_text = ""
    if execution_stop > 0:
        discipline_text = "如果这笔交易还对，不该失守执行止损。"
        note_text = f"{note_text}{discipline_text}" if note_text else discipline_text

    execution_stop_display = f"{execution_stop:.2f}" if execution_stop > 0 else "-"
    hard_stop_display = "-"
    if hard_stop > 0:
        hard_stop_display = "同执行止损" if execution_stop > 0 and _same_price_level(hard_stop, execution_stop) else f"{hard_stop:.2f}"

    compact_parts = []
    if key_zone_display != "-":
        zone_part = f"关键位/带{key_zone_display}"
        if zone_badge:
            zone_part += f"（{zone_badge}）"
        compact_parts.append(zone_part)
    if execution_stop_display != "-":
        compact_parts.append(f"执行止损{execution_stop_display}")
    if hard_stop_display not in ("-", "同执行止损"):
        compact_parts.append(f"最晚硬止损{hard_stop_display}")
    compact_text = "；".join(compact_parts) if compact_parts else "-"

    action_stop_text = "-"
    if execution_stop_display != "-":
        action_stop_text = f"执行止损{execution_stop_display}"
    elif hard_stop_display not in ("-", "同执行止损"):
        action_stop_text = f"最晚硬止损{hard_stop_display}"

    return {
        'confirm_price': _round_or_none(confirm_price),
        'support_price': _round_or_none(support_price),
        'key_zone_low': _round_or_none(zone_low) if zone_low > 0 else None,
        'key_zone_high': _round_or_none(zone_high) if zone_high > 0 else None,
        'key_zone_display': key_zone_display,
        'execution_stop': _round_or_none(execution_stop) if execution_stop > 0 else None,
        'execution_stop_display': execution_stop_display,
        'hard_stop': _round_or_none(hard_stop) if hard_stop > 0 else None,
        'hard_stop_display': hard_stop_display,
        'zone_badge': zone_badge,
        'note_text': note_text,
        'compact_text': compact_text,
        'action_stop_text': action_stop_text,
        'stop_overridden_to_hard': stop_overridden_to_hard,
        'confluence_reasons': list(dict.fromkeys(confluence_reasons)),
    }


def _normalize_observation_zone_badge(zone_badge):
    badge_text = str(zone_badge or '').strip()
    if not badge_text:
        return ''

    labels = []
    for raw_label in badge_text.split('/'):
        label = '失效' if raw_label == '止损' else raw_label
        if label and label not in labels:
            labels.append(label)
    return "/".join(labels)


def _build_observation_price_focus_text(price_focus):
    price_focus = price_focus or {}

    key_zone_display = str(price_focus.get('key_zone_display', '-') or '-')
    zone_badge = _normalize_observation_zone_badge(price_focus.get('zone_badge', ''))
    execution_stop = _safe_float(price_focus.get('execution_stop'))
    hard_stop = _safe_float(price_focus.get('hard_stop'))
    key_zone_low = _safe_float(price_focus.get('key_zone_low'))
    key_zone_high = _safe_float(price_focus.get('key_zone_high'))

    compact_parts = []
    if key_zone_display != "-":
        zone_part = f"关键位/带{key_zone_display}"
        if zone_badge:
            zone_part += f"（{zone_badge}）"
        compact_parts.append(zone_part)

    zone_covers_execution = False
    if execution_stop > 0 and key_zone_low > 0 and key_zone_high > 0:
        zone_covers_execution = (
            execution_stop >= min(key_zone_low, key_zone_high) - 0.011
            and execution_stop <= max(key_zone_low, key_zone_high) + 0.011
        )
    if execution_stop > 0 and (key_zone_display == "-" or not zone_covers_execution or '失效' not in zone_badge):
        compact_parts.append(f"观察失效位{execution_stop:.2f}")

    if hard_stop > 0 and not _same_price_level(hard_stop, execution_stop):
        compact_parts.append(f"最晚失效位{hard_stop:.2f}")

    return "；".join(compact_parts) if compact_parts else "-"


def _build_observation_price_note_text(price_focus):
    price_focus = price_focus or {}
    note_parts = []

    if price_focus.get('stop_overridden_to_hard'):
        note_parts.append("原结构过深，前台先看最晚失效位。")
    else:
        zone_badge = _normalize_observation_zone_badge(price_focus.get('zone_badge', ''))
        if '/' in zone_badge:
            note_parts.append(f"{zone_badge}靠近，视为同一关键带。")

    confluence_reasons = price_focus.get('confluence_reasons') or []
    if confluence_reasons:
        note_parts.append(f"该位置贴近{'、'.join(dict.fromkeys(confluence_reasons))}附近。")

    if _safe_float(price_focus.get('execution_stop')) > 0:
        note_parts.append("如果这个观察对象继续强，就不该失守这条关键位。")

    return "".join(note_parts)


def _should_surface_price_note(price_focus):
    if not price_focus:
        return False
    if price_focus.get('confluence_reasons'):
        return True
    zone_badge = str(price_focus.get('zone_badge', '') or '')
    return '前低' in zone_badge


def _append_price_focus_note(lines, price_focus, prefix='  '):
    if not _should_surface_price_note(price_focus):
        return
    note_text = str(price_focus.get('note_text', '') or '').strip()
    if note_text:
        lines.append(f"{prefix}价格怎么看：{note_text}")


def _append_observation_price_focus_note(lines, price_focus, prefix='  '):
    if not _should_surface_price_note(price_focus):
        return
    note_text = _build_observation_price_note_text(price_focus)
    if note_text:
        lines.append(f"{prefix}价格怎么看：{note_text}")


def _get_run_mode_label(mode):
    return "官方冻结" if mode == LEDGER_MODE_FROZEN else "实验重放"


def _get_strategy_performance_path(mode=LEDGER_MODE_FROZEN):
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    os.makedirs(data_dir, exist_ok=True)
    if mode == LEDGER_MODE_REPLAY:
        return os.path.join(data_dir, 'strategy_performance_replay.json')
    return os.path.join(data_dir, 'strategy_performance.json')


def _get_report_output_path(target_date, mode=LEDGER_MODE_FROZEN, variant=REPORT_VARIANT_FULL):
    from daily_report_render import _get_report_output_path as _render_get_report_output_path

    return _render_get_report_output_path(target_date, mode=mode, variant=variant)


def _get_snapshot_path(target_date, mode=LEDGER_MODE_FROZEN):
    snapshots_dir = os.path.join(os.path.dirname(__file__), '..', 'snapshots')
    if mode == LEDGER_MODE_REPLAY:
        snapshots_dir = os.path.join(snapshots_dir, 'replay')
    os.makedirs(snapshots_dir, exist_ok=True)
    suffix = "_replay" if mode == LEDGER_MODE_REPLAY else ""
    return os.path.join(snapshots_dir, f"{target_date}{suffix}.json")


def _get_factor_snapshot_path(target_date, mode=LEDGER_MODE_FROZEN):
    factor_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'factor_snapshots')
    if mode == LEDGER_MODE_REPLAY:
        factor_dir = os.path.join(factor_dir, 'replay')
    os.makedirs(factor_dir, exist_ok=True)
    suffix = "_replay" if mode == LEDGER_MODE_REPLAY else ""
    return os.path.join(factor_dir, f"{target_date}{suffix}.json")


def load_strategy_performance_ledger(mode=LEDGER_MODE_FROZEN):
    import json

    path = _get_strategy_performance_path(mode=mode)
    default_data = {
        'version': STRATEGY_PERFORMANCE_LEDGER_VERSION,
        'updated_at': '',
        'mode': mode,
        'records': [],
    }
    if not os.path.exists(path):
        return default_data

    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return default_data
        data.setdefault('version', STRATEGY_PERFORMANCE_LEDGER_VERSION)
        data.setdefault('updated_at', '')
        data.setdefault('mode', mode)
        data.setdefault('records', [])
        if not isinstance(data.get('records'), list):
            data['records'] = []
        return data
    except Exception as e:
        print(f"⚠️ 策略绩效账本读取失败，重置为空: {e}")
        return default_data


def save_strategy_performance_ledger(ledger, mode=LEDGER_MODE_FROZEN):
    import json
    import datetime as _dt

    path = _get_strategy_performance_path(mode=mode)
    ledger = dict(ledger or {})
    ledger['version'] = STRATEGY_PERFORMANCE_LEDGER_VERSION
    ledger['updated_at'] = _dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ledger['mode'] = mode
    ledger.setdefault('records', [])
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(ledger, f, ensure_ascii=False, indent=2)
    return path


def save_factor_snapshot(target_date, factor_snapshot, mode=LEDGER_MODE_FROZEN):
    import json
    import datetime as _dt

    snapshot = dict(factor_snapshot or {})
    if not snapshot:
        return {
            'path': '',
            'mode': mode,
            'saved': False,
        }

    snapshot.setdefault('report_date', target_date)
    snapshot_path = _get_factor_snapshot_path(target_date, mode=mode)
    payload = {
        'version': STRATEGY_FACTOR_SNAPSHOT_VERSION,
        'mode': mode,
        'saved_at': _dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'snapshot': _make_serializable(snapshot),
    }

    if mode == LEDGER_MODE_FROZEN and os.path.exists(snapshot_path):
        return {
            'path': snapshot_path,
            'mode': mode,
            'saved': False,
            'frozen': True,
            'saved_at': payload['saved_at'],
            'version': STRATEGY_FACTOR_SNAPSHOT_VERSION,
        }

    with open(snapshot_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return {
        'path': snapshot_path,
        'mode': mode,
        'saved': True,
        'saved_at': payload['saved_at'],
        'version': STRATEGY_FACTOR_SNAPSHOT_VERSION,
    }


def _to_bs_code(security_code, is_index=False):
    code = str(security_code or '').strip()
    if not code:
        return ''

    if code.startswith(('sh.', 'sz.', 'bj.')):
        return code
    if code.startswith(('sh', 'sz', 'bj')) and len(code) > 2 and '.' not in code:
        return f"{code[:2]}.{code[2:]}"

    normalized = normalize_stock_code(code)
    if is_index:
        if normalized == '399001':
            return 'sz.399001'
        if normalized == '399006':
            return 'sz.399006'
        if normalized == '000001':
            return 'sh.000001'
        market = 'sh'
    else:
        if normalized.startswith(('8', '4')):
            market = 'bj'
        elif normalized.startswith(('6', '9', '5')):
            market = 'sh'
        else:
            market = 'sz'
    return f"{market}.{normalized}"


def _run_with_wall_clock_timeout(seconds, fn, *args, default=None, **kwargs):
    seconds = _safe_float(seconds)
    if seconds <= 0:
        return fn(*args, **kwargs)

    if os.name != 'posix' or threading.current_thread() is not threading.main_thread():
        return fn(*args, **kwargs)

    class _WallClockTimeoutError(TimeoutError):
        pass

    def _timeout_handler(signum, frame):
        raise _WallClockTimeoutError(f"wall clock timeout after {seconds}s")

    previous_handler = signal.getsignal(signal.SIGALRM)
    try:
        signal.signal(signal.SIGALRM, _timeout_handler)
        signal.setitimer(signal.ITIMER_REAL, seconds)
        return fn(*args, **kwargs)
    except _WallClockTimeoutError:
        return default
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)


def _fetch_quicktiny_daily_price_bars(security_code, start_date, end_date, is_index=False):
    code = _to_bs_code(security_code, is_index=is_index).replace('.', '')
    start_date = _normalize_kline_date_str(start_date)
    end_date = _normalize_kline_date_str(end_date)
    if not code or not start_date or not end_date:
        return []

    try:
        import requests

        start_dt = _parse_kline_date(start_date)
        end_dt = _parse_kline_date(end_date)
        days = 20
        if start_dt and end_dt:
            days = max((end_dt - start_dt).days + 10, 20)
        url = f"https://stock.quicktiny.cn/api/tushare/merged-kline/{code}?days={days}"
        with requests.Session() as session:
            session.trust_env = False
            resp = session.get(url, timeout=(2, 6))
        resp.raise_for_status()
        result = resp.json()
        data = result.get('data', []) if isinstance(result, dict) else []
        bars = []
        for item in data:
            date_text = _normalize_kline_date_str(item.get('date'))
            if not date_text or not (start_date <= date_text <= end_date):
                continue
            bars.append({
                'date': date_text,
                'open': _safe_float(item.get('open')),
                'high': _safe_float(item.get('high')),
                'low': _safe_float(item.get('low')),
                'close': _safe_float(item.get('close')),
                'volume': _safe_float(item.get('volume') or item.get('vol')),
            })
        return sorted(bars, key=lambda x: x.get('date', ''))
    except Exception:
        return []


def _merge_daily_price_bars(primary_bars, fallback_bars):
    merged_by_date = {}
    for bar in fallback_bars or []:
        date_text = _normalize_kline_date_str(bar.get('date'))
        if date_text:
            merged_by_date[date_text] = {
                'date': date_text,
                'open': _safe_float(bar.get('open')),
                'high': _safe_float(bar.get('high')),
                'low': _safe_float(bar.get('low')),
                'close': _safe_float(bar.get('close')),
                'volume': _safe_float(bar.get('volume')),
            }
    for bar in primary_bars or []:
        date_text = _normalize_kline_date_str(bar.get('date'))
        if date_text:
            merged_by_date[date_text] = {
                'date': date_text,
                'open': _safe_float(bar.get('open')),
                'high': _safe_float(bar.get('high')),
                'low': _safe_float(bar.get('low')),
                'close': _safe_float(bar.get('close')),
                'volume': _safe_float(bar.get('volume')),
            }
    return [merged_by_date[key] for key in sorted(merged_by_date.keys())]


def fetch_daily_price_bars(
    security_code,
    start_date,
    end_date,
    is_index=False,
    prefer_fast=False,
    allow_baostock_fallback=True,
):
    """获取日线数据。

    默认保持原行为：优先 BaoStock，缺失时再用 QuickTiny/最近K线补齐。
    对全市场 20cm 扫描这类大批量调用，可打开 prefer_fast 并关闭 BaoStock 兜底，
    先走有超时保护的 QuickTiny，避免单只股票把正式链整体卡死。
    """
    bs_code = _to_bs_code(security_code, is_index=is_index)
    start_date = _normalize_kline_date_str(start_date)
    end_date = _normalize_kline_date_str(end_date)
    if not bs_code or not start_date or not end_date:
        return []

    cache_key = (bs_code, start_date, end_date, bool(is_index), bool(prefer_fast), bool(allow_baostock_fallback))
    if cache_key in _daily_price_bar_cache:
        return [dict(item) for item in _daily_price_bar_cache[cache_key]]

    def _finalize(result_bars):
        result_bars = sorted(result_bars or [], key=lambda x: x.get('date', ''))
        last_bar_date = _normalize_kline_date_str((result_bars[-1] or {}).get('date')) if result_bars else ''
        if result_bars and last_bar_date >= end_date:
            _daily_price_bar_cache[cache_key] = [dict(item) for item in result_bars]
        else:
            _daily_price_bar_cache.pop(cache_key, None)
        return [dict(item) for item in result_bars]

    quicktiny_bars = []
    if prefer_fast:
        quicktiny_bars = _run_with_wall_clock_timeout(
            3,
            _fetch_quicktiny_daily_price_bars,
            security_code,
            start_date,
            end_date,
            is_index=is_index,
            default=[],
        ) or []
        quicktiny_last_date = _normalize_kline_date_str((quicktiny_bars[-1] or {}).get('date')) if quicktiny_bars else ''
        if quicktiny_bars and quicktiny_last_date >= end_date:
            return _finalize(quicktiny_bars)
        if not allow_baostock_fallback:
            return _finalize(quicktiny_bars)

    bars = []
    try:
        import baostock as bs

        if _ensure_baostock_login():
            if is_index:
                rs = bs.query_history_k_data_plus(
                    bs_code,
                    'date,open,high,low,close,volume',
                    start_date=start_date,
                    end_date=end_date,
                    frequency='d',
                )
            else:
                rs = bs.query_history_k_data_plus(
                    bs_code,
                    'date,open,high,low,close,volume',
                    start_date=start_date,
                    end_date=end_date,
                    frequency='d',
                    adjustflag='3',
                )

            if rs.error_code == '0':
                while (rs.error_code == '0') and rs.next():
                    row = rs.get_row_data()
                    bars.append({
                        'date': _normalize_kline_date_str(row[0]),
                        'open': _safe_float(row[1]),
                        'high': _safe_float(row[2]),
                        'low': _safe_float(row[3]),
                        'close': _safe_float(row[4]),
                        'volume': _safe_float(row[5]),
                    })
    except Exception:
        bars = []

    if not bars and not is_index:
        try:
            start_dt = _parse_kline_date(start_date)
            end_dt = _parse_kline_date(end_date)
            lookback_days = 20
            if start_dt and end_dt:
                lookback_days = max((end_dt - start_dt).days + 10, 20)
            recent = fetch_recent_price_bars(security_code, end_date, lookback_days=lookback_days)
            for bar in recent:
                date_text = _normalize_kline_date_str(bar.get('date'))
                if start_date <= date_text <= end_date:
                    bars.append({
                        'date': date_text,
                        'open': _safe_float(bar.get('open')),
                        'high': _safe_float(bar.get('high')),
                        'low': _safe_float(bar.get('low')),
                        'close': _safe_float(bar.get('close')),
                        'volume': _safe_float(bar.get('volume')),
                    })
        except Exception:
            bars = []

    needs_supplement = not bars or _normalize_kline_date_str((bars[-1] or {}).get('date')) < end_date
    if needs_supplement:
        if not quicktiny_bars:
            quicktiny_bars = _run_with_wall_clock_timeout(
                3,
                _fetch_quicktiny_daily_price_bars,
                security_code,
                start_date,
                end_date,
                is_index=is_index,
                default=[],
            ) or []
        if quicktiny_bars:
            bars = _merge_daily_price_bars(bars, quicktiny_bars)

    return _finalize(bars)


def _get_first_bar_after(bars, after_date):
    after_dt = _parse_kline_date(after_date)
    if after_dt is None:
        return None
    for bar in bars or []:
        bar_dt = _parse_kline_date(bar.get('date'))
        if bar_dt and bar_dt > after_dt:
            return bar
    return None


def _get_first_bar_on_or_after(bars, target_date):
    target_dt = _parse_kline_date(target_date)
    if target_dt is None:
        return None
    for bar in bars or []:
        bar_dt = _parse_kline_date(bar.get('date'))
        if bar_dt and bar_dt >= target_dt:
            return bar
    return None


def _get_last_bar_on_or_before(bars, target_date):
    target_dt = _parse_kline_date(target_date)
    if target_dt is None:
        return None
    result = None
    for bar in bars or []:
        bar_dt = _parse_kline_date(bar.get('date'))
        if bar_dt and bar_dt <= target_dt:
            result = bar
        elif bar_dt and bar_dt > target_dt:
            break
    return result


def _is_next_trading_day(prev_date, curr_date):
    prev_date = _normalize_kline_date_str(prev_date)
    curr_date = _normalize_kline_date_str(curr_date)
    if not prev_date or not curr_date or prev_date >= curr_date:
        return False

    bars = fetch_daily_price_bars('sh.000001', prev_date, curr_date, is_index=True)
    dates = [bar.get('date') for bar in bars if bar.get('date')]
    return len(dates) == 2 and dates[0] == prev_date and dates[-1] == curr_date


def _count_trading_days_between(start_date, end_date):
    start_date = _normalize_kline_date_str(start_date)
    end_date = _normalize_kline_date_str(end_date)
    if not start_date or not end_date or start_date > end_date:
        return 0

    bars = fetch_daily_price_bars('sh.000001', start_date, end_date, is_index=True)
    dates = [bar.get('date') for bar in bars if bar.get('date')]
    return len(dates)


def _get_limit_up_pct(stock_code='', stock_name=''):
    code = normalize_stock_code(stock_code)
    name = str(stock_name or '').upper()
    if 'ST' in name:
        return 0.048
    if code.startswith(('43', '83', '87', '88', '89', '92')):
        return 0.298
    if code.startswith(('30', '68')):
        return 0.198
    return 0.098


def _is_one_word_limit_bar(stock_code='', stock_name='', open_price=None, high_price=None, low_price=None, close_price=None, change_pct=None):
    open_price = _safe_float(open_price)
    high_price = _safe_float(high_price)
    low_price = _safe_float(low_price)
    close_price = _safe_float(close_price)
    change_pct = _safe_float(change_pct)

    if min(open_price, high_price, low_price, close_price) <= 0:
        return False

    tolerance = max(close_price * 0.001, 0.01)
    flat_line = (
        abs(open_price - close_price) <= tolerance
        and abs(open_price - high_price) <= tolerance
        and abs(open_price - low_price) <= tolerance
    )
    limit_up_pct = _get_limit_up_pct(stock_code, stock_name) * 100
    return flat_line and change_pct >= limit_up_pct


def _compute_bar_change_pct(current_bar, prev_bar=None):
    current_close = _safe_float((current_bar or {}).get('close'))
    prev_close = _safe_float((prev_bar or {}).get('close'))
    if current_close <= 0 or prev_close <= 0:
        return 0.0
    return (current_close / prev_close - 1.0) * 100.0


def evaluate_live_tradability(stock, target_date='', recent_bars=None):
    stock = stock or {}
    code = normalize_stock_code(stock.get('code', ''))
    name = stock.get('name', '')
    recent_bars = list(recent_bars or [])
    normalized_target_date = _normalize_kline_date_str(target_date)

    sorted_bars = sorted(
        [bar for bar in recent_bars if bar.get('date')],
        key=lambda item: _normalize_kline_date_str(item.get('date')),
    )
    if normalized_target_date:
        sorted_bars = [
            bar for bar in sorted_bars
            if _normalize_kline_date_str(bar.get('date')) <= normalized_target_date
        ]

    report_bar = sorted_bars[-1] if sorted_bars else {}
    prev_bar = sorted_bars[-2] if len(sorted_bars) >= 2 else {}
    prev_prev_bar = sorted_bars[-3] if len(sorted_bars) >= 3 else {}

    report_change = stock.get('change')
    if report_change is None and report_bar:
        report_change = _compute_bar_change_pct(report_bar, prev_bar)

    report_day_is_one_word = _is_one_word_limit_bar(
        stock_code=code,
        stock_name=name,
        open_price=stock.get('open', report_bar.get('open')),
        high_price=stock.get('high', report_bar.get('high')),
        low_price=stock.get('low', report_bar.get('low')),
        close_price=stock.get('close', stock.get('price', report_bar.get('close'))),
        change_pct=report_change,
    )

    prev_day_is_one_word = False
    if prev_bar:
        prev_day_is_one_word = _is_one_word_limit_bar(
            stock_code=code,
            stock_name=name,
            open_price=prev_bar.get('open'),
            high_price=prev_bar.get('high'),
            low_price=prev_bar.get('low'),
            close_price=prev_bar.get('close'),
            change_pct=_compute_bar_change_pct(prev_bar, prev_prev_bar),
        )

    if report_day_is_one_word and prev_day_is_one_word:
        status = 'invalid_consecutive_one_word'
        reason = '连续一字，默认买不进去，只记强势观察，不计正式执行。'
    elif report_day_is_one_word:
        status = 'invalid_report_day_one_word'
        reason = '当日一字，次日默认买不进去，只保留观察/记忆。'
    else:
        status = 'tradeable'
        reason = '当前至少具备基本交易可达性。'

    return {
        'can_trade': status == 'tradeable',
        'status': status,
        'status_label': _get_strategy_status_label(status) if status != 'tradeable' else '可交易',
        'reason': reason,
        'report_day_is_one_word': bool(report_day_is_one_word),
        'prev_day_is_one_word': bool(prev_day_is_one_word),
    }


def _compound_returns(values):
    nav = 1.0
    for value in values or []:
        nav *= (1.0 + _safe_float(value, 0.0))
    return nav - 1.0


def _format_pct(value):
    if value is None:
        return "-"
    return f"{value * 100:+.2f}%"


def _format_pct_range(low_value, high_value):
    if low_value is None or high_value is None:
        return "-"
    return f"{low_value * 100:+.2f}% ~ {high_value * 100:+.2f}%"


def _get_strategy_status_label(status, note=''):
    label_map = {
        'pending': '待评估',
        'invalid': '无效计划',
        'watch_only': '仅观察',
        'no_trade': '无交易',
        'not_triggered': '未触发',
        'closed': '已平仓',
        'open_mark_to_market': '持仓中',
        'continuation_only': '延续持有',
        'invalid_report_day_one_word': '无效：当日一字',
        'invalid_consecutive_one_word': '无效：连续一字',
    }
    base = label_map.get(status, status or '-')
    if note:
        return f"{base}（{note}）"
    return base


def _get_plan_action_label(action_type, position_pct=None):
    action_type = action_type or ''
    position_pct = int(_safe_float(position_pct, 0)) if position_pct is not None else None
    if action_type == 'execute' and position_pct == 30:
        return '30%条件试错仓'
    if action_type == 'execute' and position_pct == 50:
        return '50%执行计划'
    label_map = {
        'execute': '执行计划',
        'watch_only': '仅观察',
        'no_trade': '无交易',
    }
    return label_map.get(action_type, action_type or '-')


def _get_signal_type_label(signal_type):
    signal_type = signal_type or 'base'
    prior = EV_SIGNAL_TYPE_PRIORS.get(signal_type, EV_SIGNAL_TYPE_PRIORS['base'])
    return prior.get('label', signal_type)


def _backfill_strategy_record_market_context(record):
    record = record or {}
    report_date = _normalize_kline_date_str(record.get('report_date'))
    if not report_date:
        return record

    if _safe_float(record.get('benchmark_report_close')) <= 0:
        report_dt = _parse_kline_date(report_date)
        end_probe_date = report_date
        if report_dt is not None:
            end_probe_date = (report_dt + datetime.timedelta(days=7)).strftime('%Y-%m-%d')
        benchmark_bars = fetch_daily_price_bars('sh.000001', report_date, end_probe_date, is_index=True)
        benchmark_bar = _get_first_bar_on_or_after(benchmark_bars, report_date)
        if benchmark_bar:
            record['benchmark_report_close'] = round(_safe_float(benchmark_bar.get('close')), 4)

    record.setdefault('signal_type', '')
    record.setdefault('permission_label', '')
    record.setdefault('ev_model_source', '')
    record.setdefault('ev_sample_size', 0)
    record.setdefault('ev_global_sample_size', 0)
    record.setdefault('ev_confidence', 0.0)
    record.setdefault('abnormal_setup_signal_id', '')
    record.setdefault('abnormal_setup_signal_label', '')
    record.setdefault('abnormal_follow_state', '')
    record.setdefault('stock_sector', '')
    record.setdefault('defensive_exit_rule', DEFENSIVE_EXIT_RULE_TEXT)
    record.setdefault('profit_exit_rule', PROFIT_EXIT_RULE_TEXT)
    record.setdefault('holding_days_min', STRATEGY_HOLDING_DAYS_MIN)
    record.setdefault('holding_days_max', STRATEGY_HOLDING_DAYS_MAX)
    record.setdefault('profit_take_pct', 0.05)
    record.setdefault('contract_kind', '')
    record.setdefault('contract_active_window_days', 0)
    record.setdefault('contract_right_side_trigger_price', None)
    record.setdefault('contract_void_price', None)
    record.setdefault('contract_reset_breakout_price', None)
    record.setdefault('contract_upgrade_condition_text', '')
    record.setdefault('decision_stack', {})
    record.setdefault('factor_snapshot', {})
    record.setdefault('factor_snapshot_path', '')
    record.setdefault('factor_snapshot_mode', '')
    record.setdefault('factor_snapshot_version', '')
    record.setdefault('factor_snapshot_saved_at', '')
    record.setdefault('mainline_driver_type', '')
    record.setdefault('mainline_pulse_stage', '')
    record.setdefault('mainline_acceptance_quality', '')
    record.setdefault('mainline_passivation_risk', '')
    record.setdefault('mainline_execution_bias', '')
    record.setdefault('mainline_pulse_action_bias', '')
    record.setdefault('mainline_pulse_action_reason', '')
    return record


def _build_trade_return_stats(records):
    stats = {
        'sample_size': 0,
        'wins': 0,
        'losses': 0,
        'neutral': 0,
        'win_rate': None,
        'avg_win_pct': None,
        'avg_loss_pct': None,
    }
    if not records:
        return stats

    win_returns = []
    loss_returns = []
    sample_size = 0
    for record in records:
        if record.get('action_type') != 'execute':
            continue
        sim = record.get('simulation', {}) or {}
        if not sim.get('triggered'):
            continue
        if sim.get('status') not in ('closed', 'open_mark_to_market'):
            continue

        low = sim.get('strategy_return_worst')
        high = sim.get('strategy_return_best')
        if low is None or high is None:
            continue
        midpoint_return = (_safe_float(low) + _safe_float(high)) / 2.0
        sample_size += 1
        if midpoint_return > 0:
            win_returns.append(midpoint_return)
        elif midpoint_return < 0:
            loss_returns.append(abs(midpoint_return))
        else:
            stats['neutral'] += 1

    stats['sample_size'] = sample_size
    stats['wins'] = len(win_returns)
    stats['losses'] = len(loss_returns)
    if sample_size > 0:
        stats['win_rate'] = len(win_returns) / sample_size
    if win_returns:
        stats['avg_win_pct'] = sum(win_returns) / len(win_returns)
    if loss_returns:
        stats['avg_loss_pct'] = sum(loss_returns) / len(loss_returns)
    return stats


def _summarize_ev_signal_review(records, start_date, end_date):
    scoped = [
        record for record in (records or [])
        if start_date <= _normalize_kline_date_str(record.get('report_date')) <= end_date
        and record.get('action_type') == 'execute'
    ]

    grouped = {}
    for record in scoped:
        signal_type = record.get('signal_type') or 'base'
        group = grouped.setdefault(signal_type, {
            'signal_type': signal_type,
            'signal_label': _get_signal_type_label(signal_type),
            'plan_count': 0,
            'triggered_count': 0,
            'sample_count': 0,
            'hit_count': 0,
            'flat_count': 0,
            'miss_count': 0,
            'return_sum': 0.0,
            'alpha_sum': 0.0,
        })
        group['plan_count'] += 1

        sim = record.get('simulation', {}) or {}
        if sim.get('triggered'):
            group['triggered_count'] += 1

        if not sim.get('triggered') or sim.get('status') not in ('closed', 'open_mark_to_market'):
            continue

        midpoint_return = (
            _safe_float(sim.get('strategy_return_worst')) + _safe_float(sim.get('strategy_return_best'))
        ) / 2.0
        midpoint_alpha = (
            _safe_float(sim.get('alpha_return_worst')) + _safe_float(sim.get('alpha_return_best'))
        ) / 2.0
        group['sample_count'] += 1
        group['return_sum'] += midpoint_return
        group['alpha_sum'] += midpoint_alpha

        if midpoint_return > 0:
            group['hit_count'] += 1
        elif midpoint_return < 0:
            group['miss_count'] += 1
        else:
            group['flat_count'] += 1

    items = []
    for item in grouped.values():
        sample_count = item.get('sample_count', 0)
        hit_rate = item.get('hit_count', 0) / sample_count if sample_count > 0 else None
        avg_return = item.get('return_sum', 0.0) / sample_count if sample_count > 0 else None
        avg_alpha = item.get('alpha_sum', 0.0) / sample_count if sample_count > 0 else None
        items.append({
            **item,
            'hit_rate': hit_rate,
            'avg_return': avg_return,
            'avg_alpha': avg_alpha,
        })

    items.sort(
        key=lambda x: (
            x.get('sample_count', 0),
            x.get('hit_rate') if x.get('hit_rate') is not None else -1,
            x.get('plan_count', 0),
        ),
        reverse=True,
    )
    return {
        'start_date': start_date,
        'end_date': end_date,
        'total_plan_count': len(scoped),
        'items': items,
    }


def build_strategy_ev_calibration(as_of_date, ledger_mode=LEDGER_MODE_FROZEN):
    ledger = load_strategy_performance_ledger(mode=ledger_mode)
    cutoff_date = _normalize_kline_date_str(as_of_date)
    historical_records = [
        _backfill_strategy_record_market_context(dict(record))
        for record in ledger.get('records', [])
        if _normalize_kline_date_str(record.get('report_date')) < cutoff_date
    ]

    global_stats = _build_trade_return_stats(historical_records)
    by_signal = {}
    for signal_type in EV_SIGNAL_TYPE_PRIORS.keys():
        signal_records = [
            record for record in historical_records
            if (record.get('signal_type') or 'base') == signal_type
        ]
        by_signal[signal_type] = _build_trade_return_stats(signal_records)

    return {
        'global': global_stats,
        'by_signal': by_signal,
    }


def estimate_signal_type_ev(signal_type, loss_space_pct, calibration):
    signal_type = signal_type or 'base'
    prior = EV_SIGNAL_TYPE_PRIORS.get(signal_type, EV_SIGNAL_TYPE_PRIORS['base'])
    global_stats = (calibration or {}).get('global', {}) or {}
    signal_stats = ((calibration or {}).get('by_signal', {}) or {}).get(signal_type, {}) or {}

    prior_weight = _safe_float(prior.get('prior_weight'), 8.0)
    global_weight = min(_safe_float(global_stats.get('sample_size')), 6.0)
    signal_weight = min(_safe_float(signal_stats.get('sample_size')), 12.0)
    total_weight = prior_weight + global_weight + signal_weight

    def _blend_metric(key):
        weighted_sum = _safe_float(prior.get(key)) * prior_weight
        if global_weight > 0 and global_stats.get(key) is not None:
            weighted_sum += _safe_float(global_stats.get(key)) * global_weight
        if signal_weight > 0 and signal_stats.get(key) is not None:
            weighted_sum += _safe_float(signal_stats.get(key)) * signal_weight
        return weighted_sum / total_weight if total_weight > 0 else _safe_float(prior.get(key))

    win_rate = _clamp(_blend_metric('win_rate'), 0.20, 0.80)
    avg_win_pct = _clamp(_blend_metric('avg_win_pct'), 0.02, 0.20)
    avg_loss_pct = _clamp(_blend_metric('avg_loss_pct'), 0.015, 0.10)
    reward_multiple = _clamp(avg_win_pct / max(avg_loss_pct, 0.01), 1.2, 4.0)

    projected_loss_pct = max(_safe_float(loss_space_pct), avg_loss_pct * 0.8)
    projected_win_pct = max(projected_loss_pct * reward_multiple, avg_win_pct * 0.6)
    confidence = _clamp((signal_weight + global_weight) / max(total_weight, 1.0), 0.0, 0.85)

    signal_samples = int(_safe_float(signal_stats.get('sample_size')))
    global_samples = int(_safe_float(global_stats.get('sample_size')))
    if signal_samples > 0:
        source_label = f"同类账本{signal_samples}笔 + 全局{global_samples}笔校准"
    elif global_samples > 0:
        source_label = f"全局账本{global_samples}笔 + 类型先验"
    else:
        source_label = "类型先验（暂无历史成交）"

    return {
        'signal_type': signal_type,
        'signal_label': prior.get('label', signal_type),
        'win_rate': win_rate,
        'avg_win_pct': avg_win_pct,
        'avg_loss_pct': avg_loss_pct,
        'projected_win_pct': projected_win_pct,
        'projected_loss_pct': projected_loss_pct,
        'reward_multiple': reward_multiple,
        'confidence': confidence,
        'signal_sample_size': signal_samples,
        'global_sample_size': global_samples,
        'source_label': source_label,
    }


def score_execution_candidate(candidate, ev_calibration):
    scored = dict(candidate or {})
    signal = scored.get('signal')

    if signal:
        entry_price = _safe_float(signal.entry_price)
        stop_loss = _safe_float(scored.get('stop_loss', signal.stop_loss))
        position_pct = _safe_float(signal.position_pct, 0.0)
        signal_type = getattr(signal, 'signal_type', '') or 'base'
    else:
        entry_price = _safe_float(scored.get('entry_price', scored.get('close', 0.0)))
        stop_loss = _safe_float(scored.get('stop_loss', entry_price * (1 - MAX_SINGLE_TRADE_LOSS_PCT)))
        position_pct = _safe_float(scored.get('position_pct', 20.0))
        signal_type = scored.get('signal_type') or 'base'

    if entry_price <= 0:
        scored['win_rate'] = 0.0
        scored['r_reward_ratio'] = 0.0
        scored['ev'] = 0.0
        scored['composite_score'] = 0.0
        scored['profit_space'] = 0.0
        scored['loss_space'] = 0.0
        scored['projected_win_pct'] = 0.0
        scored['projected_loss_pct'] = 0.0
        scored['ev_model_source'] = '无有效从什么价开始算'
        scored['ev_sample_size'] = 0
        scored['ev_global_sample_size'] = 0
        scored['ev_confidence'] = 0.0
        scored['signal_type'] = signal_type
        return scored

    loss_space_pct = max((entry_price - stop_loss) / entry_price, 0.0)
    if loss_space_pct <= 0:
        loss_space_pct = MAX_SINGLE_TRADE_LOSS_PCT

    posterior = estimate_signal_type_ev(signal_type, loss_space_pct, ev_calibration)
    projected_loss_pct = max(loss_space_pct, posterior.get('projected_loss_pct', loss_space_pct))
    projected_win_pct = max(projected_loss_pct * posterior.get('reward_multiple', 2.0), posterior.get('projected_win_pct', 0.0))

    profit_space = entry_price * projected_win_pct
    loss_space = entry_price * projected_loss_pct
    ev_pct = posterior.get('win_rate', 0.0) * projected_win_pct - (1 - posterior.get('win_rate', 0.0)) * projected_loss_pct
    composite_score = ev_pct * (position_pct / 100.0) * (1.0 + posterior.get('confidence', 0.0) * 0.15)
    r_reward_ratio = projected_win_pct / projected_loss_pct if projected_loss_pct > 0 else 0.0

    scored['win_rate'] = posterior.get('win_rate', 0.0)
    scored['r_reward_ratio'] = r_reward_ratio
    scored['ev'] = entry_price * ev_pct
    scored['ev_pct'] = ev_pct
    scored['composite_score'] = composite_score
    scored['profit_space'] = profit_space
    scored['loss_space'] = loss_space
    scored['projected_win_pct'] = projected_win_pct
    scored['projected_loss_pct'] = projected_loss_pct
    scored['ev_model_source'] = posterior.get('source_label', '')
    scored['ev_sample_size'] = posterior.get('signal_sample_size', 0)
    scored['ev_global_sample_size'] = posterior.get('global_sample_size', 0)
    scored['ev_confidence'] = posterior.get('confidence', 0.0)
    scored['signal_type'] = signal_type
    return scored


def score_candidate_decision_stack(
    candidate,
    final_gate=None,
    mainline_name='',
    conviction_codes=None,
    leader_memory_codes=None,
    state_machine_snapshot=None,
    target_date='',
):
    conviction_codes = conviction_codes or set()
    leader_memory_codes = leader_memory_codes or set()
    state_machine_snapshot = state_machine_snapshot or {}

    scored = dict(candidate or {})
    code = normalize_stock_code(scored.get('code', ''))
    name = scored.get('name', '')
    sector = str(scored.get('sector', '') or '').strip()
    abnormal_state = _resolve_candidate_follow_state(scored)
    setup_id = _resolve_candidate_setup_id(scored)
    permission_label = str(scored.get('permission_label', '') or '').strip()
    signal = scored.get('signal')
    minute_plan = scored.get('minute_plan') or {}
    stop_plan = scored.get('stop_plan') or {}
    entry_range = scored.get('entry_range')
    tradability_guard = scored.get('tradability_guard') or {}

    if not entry_range and signal:
        entry_range = (signal.entry_price, signal.entry_price)

    is_mainline = bool(mainline_name and sector_name_matches(sector, mainline_name))
    is_conviction = code in conviction_codes
    is_memory = code in leader_memory_codes
    report_day_is_one_word = _is_one_word_limit_bar(
        stock_code=code,
        stock_name=name,
        open_price=scored.get('open'),
        high_price=scored.get('high'),
        low_price=scored.get('low'),
        close_price=scored.get('close'),
        change_pct=scored.get('change'),
    ) if code and name else False

    execution_bias = str(state_machine_snapshot.get('execution_bias', '') or '').strip()
    if execution_bias == 'allow_execute':
        environment_score = 100
    elif execution_bias == 'divergence_only':
        environment_score = 76
    elif execution_bias == 'prep_only':
        environment_score = 58
    elif execution_bias == 'watch_only':
        environment_score = 28
    elif execution_bias == 'reduce_only':
        environment_score = 16
    elif execution_bias == 'avoid':
        environment_score = 0
    else:
        environment_score = 100 if final_gate and final_gate.get('can_new_entry') else 35 if final_gate else 50
    mainline_score = 100 if is_mainline else 55 if not mainline_name else 20
    memory_score = 100 if is_conviction else 82 if is_memory else 62 if is_mainline else 25
    trigger_score = _get_setup_priority_score(setup_id, abnormal_state)
    if not setup_id and not abnormal_state:
        trigger_score = 18

    washout_reclaim_chain = _build_washout_reclaim_context(
        scored,
        mainline_name=mainline_name,
        conviction_codes=conviction_codes,
        leader_memory_codes=leader_memory_codes,
        target_date=target_date,
    )
    if washout_reclaim_chain.get('active'):
        if washout_reclaim_chain.get('recognition_ok'):
            memory_score = max(memory_score, 82 if not is_conviction else 100)
        if washout_reclaim_chain.get('recognition_ok') and washout_reclaim_chain.get('within_3d_window'):
            trigger_score += 10
        elif washout_reclaim_chain.get('recognition_ok'):
            trigger_score += 2
        else:
            trigger_score = max(trigger_score - 10, 12)

    trend_continuation_chain = _build_trend_continuation_context(
        scored,
        mainline_name=mainline_name,
        conviction_codes=conviction_codes,
        leader_memory_codes=leader_memory_codes,
        target_date=target_date,
    )
    if trend_continuation_chain.get('active'):
        memory_score = max(memory_score, 88 if not is_conviction else 100)
        trigger_score += 8
    elif trend_continuation_chain.get('recognition_ok') and trend_continuation_chain.get('act_right'):
        trigger_score += 3

    tradability_score = 0
    if tradability_guard and not tradability_guard.get('can_trade', True):
        tradability_score = 0
    else:
        if entry_range and entry_range[0] is not None and entry_range[1] is not None:
            tradability_score += 35
        if minute_plan.get('confirm_price_60m'):
            tradability_score += 25
        if minute_plan.get('confirm_support_60m'):
            tradability_score += 5
        if (stop_plan.get('effective_stop') if stop_plan else None) or scored.get('stop_loss'):
            tradability_score += 20
        if permission_label and '执行权' in permission_label:
            tradability_score += 10
        if not report_day_is_one_word:
            tradability_score += 10
        tradability_score = min(tradability_score, 100)

    ev_score = _clamp(_safe_float(scored.get('ev_pct')) * 3000, 0, 100)
    scored['report_day_is_one_word'] = bool(report_day_is_one_word)
    scored['tradability_blocked'] = bool(tradability_guard and not tradability_guard.get('can_trade', True))
    scored['tradability_block_reason'] = tradability_guard.get('reason', '')
    scored['decision_stack'] = {
        'environment_score': environment_score,
        'mainline_score': mainline_score,
        'memory_score': memory_score,
        'trigger_score': trigger_score,
        'tradability_score': tradability_score,
        'ev_score': ev_score,
        'setup_priority_score': trigger_score,
        'setup_id': setup_id,
        'has_formal_abnormal_setup': _candidate_has_formal_abnormal_setup(scored),
        'is_resilient_abnormal': _candidate_is_resilient_abnormal(scored),
        'washout_reclaim_chain': washout_reclaim_chain,
        'trend_continuation_chain': trend_continuation_chain,
        'order_text': DECISION_STACK_ORDER_TEXT,
    }
    return scored


def sort_decision_stack_candidates(candidates):
    return sorted(
        candidates or [],
        key=lambda item: (
            (item.get('decision_stack', {}) or {}).get('environment_score', 0),
            (item.get('decision_stack', {}) or {}).get('mainline_score', 0),
            (item.get('decision_stack', {}) or {}).get('memory_score', 0),
            (item.get('decision_stack', {}) or {}).get('trigger_score', 0),
            (item.get('decision_stack', {}) or {}).get('tradability_score', 0),
            _safe_float(item.get('composite_score')),
            _safe_float(item.get('ev')),
            _safe_float(item.get('tomorrow_strength')),
        ),
        reverse=True,
    )


def _classify_watch_anchor_bucket(candidate):
    candidate = candidate or {}
    abnormal_light = str(candidate.get('abnormal_light', '') or '').strip()
    risk_level = str(candidate.get('risk_level', '') or '').strip()
    raw_risk_score = _safe_float(candidate.get('raw_risk_score', 0))
    repair_count = len(candidate.get('repair_buffers', []) or [])

    if abnormal_light == '🟢 绿灯' and repair_count > 0 and risk_level == '🟡 中风险':
        return 4, '强分歧未坏'
    if abnormal_light == '🟢 绿灯' and repair_count > 0 and raw_risk_score >= 12:
        return 3, '分歧后承接'
    if risk_level == '🟢 低风险':
        return 2, '顺势观察'
    if risk_level == '🟡 中风险':
        return 1, '一般观察'
    return 0, '低优先级'


def _candidate_matches_mainline(candidate, mainline_name=''):
    return analysis_utils._candidate_matches_mainline(candidate, mainline_name)


def _requires_crossline_second_confirmation(candidate, mainline_name=''):
    candidate = candidate or {}
    if not mainline_name:
        return False
    if _candidate_matches_mainline(candidate, mainline_name) or candidate.get('is_mainline'):
        return False
    return (
        _resolve_candidate_setup_id(candidate) == 'burst_hold'
        and _resolve_candidate_follow_state(candidate) == '跌不下去'
    )


def _is_washout_reclaim_setup_id(setup_id=''):
    return str(setup_id or '').strip() in ('burst_hold', 'upper_shadow_reclaim', 'horror_wash_hold')


def _build_washout_reclaim_context(candidate, mainline_name='', conviction_codes=None, leader_memory_codes=None, target_date=''):
    candidate = candidate or {}
    conviction_codes = conviction_codes or set()
    leader_memory_codes = leader_memory_codes or set()
    setup_id = _resolve_candidate_setup_id(candidate)
    follow_state = _resolve_candidate_follow_state(candidate)
    code = normalize_stock_code(candidate.get('code', ''))
    is_mainline = bool(candidate.get('is_mainline')) or _candidate_matches_mainline(candidate, mainline_name)
    is_conviction = code in conviction_codes
    is_memory = code in leader_memory_codes
    abnormal_date = _normalize_kline_date_str(candidate.get('abnormal_date'))
    target_date = _normalize_kline_date_str(target_date)
    subtype = str(candidate.get('washout_reclaim_subtype') or candidate.get('abnormal_subtype') or '').strip()
    subtype_label_map = {
        'entity_bear_reclaim': '实体阴线后反包',
        'upper_shadow_eat': '上影线后吃上影',
        'gap_reclaim': '向下跳空+向上跳空',
        'flush_open_reclaim': '一步到位低开高走',
    }
    subtype_label = subtype_label_map.get(subtype, '')

    active = _is_washout_reclaim_setup_id(setup_id) and follow_state == '跌不下去'
    recognition_ok = bool(is_mainline or is_conviction or is_memory)
    days_since_abnormal = None
    within_3d_window = False
    if abnormal_date and target_date:
        abnormal_dt = _parse_kline_date(abnormal_date)
        target_dt = _parse_kline_date(target_date)
        if abnormal_dt and target_dt and target_dt >= abnormal_dt:
            days_since_abnormal = (target_dt - abnormal_dt).days
            within_3d_window = days_since_abnormal <= 3

    note = ''
    action_bias = ''
    if active:
        subtype_prefix = f"{subtype_label}，" if subtype_label else ''
        if recognition_ok and within_3d_window:
            note = f"{subtype_prefix}洗盘完成型修复，重点看三日内快速收复，不拖节奏。"
            action_bias = f"{subtype_prefix}洗盘完成型异动已进入三日内快速修复窗口，优先观察是否继续强化。"
        elif recognition_ok:
            note = f"{subtype_prefix}洗盘完成型修复，但已经超出三日快速修复窗口，后续若再动更像新周期，不按原节奏硬等。"
            action_bias = f"{subtype_prefix}洗盘完成型异动已过快速修复窗口，不能再把旧异动当作当前主驱动。"
        else:
            note = f"{subtype_prefix}洗盘完成型异动，但缺少辨识度/记忆资产前提，只能做背景观察，不提级。"
            action_bias = f"{subtype_prefix}缺少辨识度前提，洗盘修复只能看，不能按狙击手主目标处理。"

    return {
        'active': active,
        'recognition_ok': recognition_ok,
        'is_mainline': is_mainline,
        'is_conviction': is_conviction,
        'is_memory': is_memory,
        'days_since_abnormal': days_since_abnormal,
        'within_3d_window': within_3d_window,
        'stage_label': '洗盘完成型修复' if active else '',
        'subtype': subtype,
        'subtype_label': subtype_label,
        'note': note,
        'action_bias': action_bias,
    }


def _build_trend_continuation_context(candidate, mainline_name='', conviction_codes=None, leader_memory_codes=None, target_date=''):
    candidate = candidate or {}
    conviction_codes = conviction_codes or set()
    leader_memory_codes = leader_memory_codes or set()
    code = normalize_stock_code(candidate.get('code', ''))
    is_mainline = bool(candidate.get('is_mainline')) or _candidate_matches_mainline(candidate, mainline_name)
    is_conviction = code in conviction_codes
    is_memory = code in leader_memory_codes
    recognition_ok = bool(is_mainline or is_conviction or is_memory)

    recent_bars = list(candidate.get('recent_bars') or [])
    target_date = _normalize_kline_date_str(target_date)
    if not recent_bars and code and target_date:
        recent_bars = fetch_recent_price_bars(code, target_date, lookback_days=4, fast_fail=True)
    recent_bars = [bar for bar in recent_bars if _normalize_kline_date_str(bar.get('date'))]
    recent_bars = sorted(recent_bars, key=lambda x: _normalize_kline_date_str(x.get('date')))[-4:]

    act_right = False
    near_new_high = False
    active = False
    latest_close = 0.0
    if len(recent_bars) >= 3:
        closes = [_safe_float(bar.get('close')) for bar in recent_bars if _safe_float(bar.get('close')) > 0]
        highs = [_safe_float(bar.get('high')) for bar in recent_bars if _safe_float(bar.get('high')) > 0]
        lows = [_safe_float(bar.get('low')) for bar in recent_bars if _safe_float(bar.get('low')) > 0]
        latest_bar = recent_bars[-1]
        prev_bar = recent_bars[-2]
        latest_close = _safe_float(latest_bar.get('close'))
        latest_high = _safe_float(latest_bar.get('high'))
        prev_close = _safe_float(prev_bar.get('close'))
        prev_lows = lows[:-1] if len(lows) >= 2 else []
        rise_count = 0
        for idx in range(1, len(closes)):
            if closes[idx] >= closes[idx - 1] * 0.995:
                rise_count += 1
        act_right = rise_count >= max(2, len(closes) - 2) and latest_close >= prev_close * 0.995
        if prev_lows:
            act_right = act_right and _safe_float(latest_bar.get('low')) >= min(prev_lows) * 0.98
        prior_highs = highs[:-1] if len(highs) >= 2 else []
        if prior_highs and latest_high > 0:
            near_new_high = latest_high >= max(prior_highs) * 0.995 or latest_close >= max(prior_highs) * 0.985
        active = recognition_ok and act_right and near_new_high

    note = ''
    action_bias = ''
    if recognition_ok and act_right and near_new_high:
        note = '趋势续强，连续 act right，重点看是否继续创高。'
        action_bias = '高辨识度强趋势对象持续 act right，优先看顺势确认，不按普通观察票处理。'
    elif recognition_ok and act_right:
        note = '趋势未坏，但还没重新逼近新高，先等再次证明自己。'
        action_bias = '先等靠近关键高点再确认，不提前把趋势续强写成执行。'
    elif recognition_ok:
        note = '有辨识度，但最近没有连续 act right，先别按趋势续强处理。'
        action_bias = '趋势续强链暂未成立，避免把记忆资产错当成继续领涨。'

    return {
        'active': active,
        'recognition_ok': recognition_ok,
        'is_mainline': is_mainline,
        'is_conviction': is_conviction,
        'is_memory': is_memory,
        'act_right': act_right,
        'near_new_high': near_new_high,
        'latest_close': _round_or_none(latest_close) if latest_close > 0 else None,
        'stage_label': '趋势续强' if active else '',
        'note': note,
        'action_bias': action_bias,
    }


def _resolve_primary_mainline_name(market_research_snapshot=None, fallback_mainline=''):
    market_research_snapshot = market_research_snapshot or {}
    observation = market_research_snapshot.get('observation', {}) or {}
    mainline_candidates = observation.get('mainline_candidates', []) or []
    for name in mainline_candidates:
        name = str(name or '').strip()
        if name and '暂无明确主线' not in name:
            return name
    fallback_mainline = str(fallback_mainline or '').strip()
    return '' if '暂无明确主线' in fallback_mainline else fallback_mainline


def _split_candidates_by_mainline(candidates, mainline_name=''):
    mainline_items = []
    crossline_items = []
    for item in candidates or []:
        if _candidate_matches_mainline(item, mainline_name):
            mainline_items.append(item)
        else:
            crossline_items.append(item)
    return mainline_items, crossline_items


def _candidate_confirmation_chain(candidate=None):
    candidate = candidate or {}
    minute_plan = candidate.get('minute_plan') or {}
    confirm_price = _round_or_none(minute_plan.get('confirm_price_60m'))
    support_price = _round_or_none(
        minute_plan.get('confirm_support_60m')
        or candidate.get('display_anchor_price')
        or candidate.get('execution_stop')
        or candidate.get('effective_stop')
    )
    return {
        'has_confirmation_chain': confirm_price is not None and support_price is not None,
        'confirm_price': confirm_price,
        'support_price': support_price,
    }


def _resolve_probe_role_family(probe_role='', watch_anchor_type='', anchor_type=''):
    role_text = ' / '.join(
        str(part or '').strip()
        for part in (probe_role, watch_anchor_type, anchor_type)
        if str(part or '').strip()
    )
    if probe_role in ('mainline_abnormal_probe', 'crossline_abnormal_probe', 'validation_probe'):
        return probe_role
    if '承接验证' in role_text:
        return 'validation_probe'
    if '跨线' in role_text:
        return 'crossline_abnormal_probe'
    if '主线' in role_text:
        return 'mainline_abnormal_probe'
    return 'watch_anchor'


def _iter_record_probe_candidates(record):
    record = record or {}
    factor_snapshot = record.get('factor_snapshot', {}) or {}
    selection = factor_snapshot.get('selection', {}) or {}
    candidates = []

    def append_candidate(candidate, role_family='watch_anchor'):
        candidate = candidate or {}
        code = normalize_stock_code(candidate.get('code') or candidate.get('stock_code', ''))
        setup_id = str(candidate.get('setup_signal_id', '') or candidate.get('abnormal_setup_signal_id', '') or '').strip()
        if not code and not setup_id:
            return
        candidates.append({
            'code': code,
            'setup_id': setup_id,
            'role_family': role_family,
        })

    append_candidate({
        'code': record.get('stock_code', ''),
        'setup_signal_id': record.get('abnormal_setup_signal_id', ''),
    }, _resolve_probe_role_family(anchor_type=record.get('anchor_type', '')))
    append_candidate(
        selection.get('selected_candidate') or {},
        _resolve_probe_role_family(anchor_type=selection.get('anchor_type', '')),
    )
    abnormal_probes = selection.get('abnormal_probes', {}) or {}
    append_candidate(abnormal_probes.get('mainline_abnormal_probe') or {}, 'mainline_abnormal_probe')
    append_candidate(abnormal_probes.get('crossline_abnormal_probe') or {}, 'crossline_abnormal_probe')
    append_candidate(abnormal_probes.get('validation_probe') or {}, 'validation_probe')
    return candidates


def _build_candidate_history_feedback(candidate=None, target_date='', probe_role='', watch_anchor_type=''):
    candidate = candidate or {}
    code = normalize_stock_code(candidate.get('code', ''))
    setup_id = str(candidate.get('abnormal_setup_signal_id', '') or candidate.get('setup_signal_id', '') or '').strip()
    target_date = _normalize_kline_date_str(target_date)
    role_family = _resolve_probe_role_family(probe_role=probe_role, watch_anchor_type=watch_anchor_type, anchor_type=candidate.get('watch_anchor_type', ''))
    feedback = {
        'continuous_days': 0,
        'matched_records': 0,
        'role_family': role_family,
        'reasons': [],
        'latest_match': {},
        'active_watch': False,
        'active_window_days': 0,
        'trading_days_since_latest': 0,
        'contract_kind': '',
    }
    if not target_date or (not code and not setup_id):
        return feedback

    try:
        ledger = load_strategy_performance_ledger(mode=LEDGER_MODE_FROZEN)
    except Exception:
        return feedback

    matched_records = []
    for record in ledger.get('records', []) or []:
        report_date = _normalize_kline_date_str(record.get('report_date'))
        if not report_date or report_date >= target_date:
            continue
        if record.get('action_type') not in ('watch_only', 'execute'):
            continue
        match_type = ''
        for item in _iter_record_probe_candidates(record):
            item_code = normalize_stock_code(item.get('code', ''))
            item_setup = str(item.get('setup_id', '') or '').strip()
            item_role = str(item.get('role_family', '') or '').strip()
            if code and item_code and item_code == code:
                match_type = 'same_stock'
                break
            if setup_id and item_setup == setup_id and role_family and item_role == role_family:
                match_type = 'same_setup_role'
                break
        if match_type:
            matched_records.append({
                'report_date': report_date,
                'match_type': match_type,
                'anchor_type': str(record.get('anchor_type', '') or '').strip(),
                'holding_days_max': max(int(_safe_float(record.get('holding_days_max', STRATEGY_HOLDING_DAYS_MAX) or STRATEGY_HOLDING_DAYS_MAX)), 1),
                'confirm_price_60m': _round_or_none(record.get('confirm_price_60m')),
                'confirm_support_60m': _round_or_none(record.get('confirm_support_60m')),
                'entry_range_high': _round_or_none(record.get('entry_range_high')),
                'entry_range_low': _round_or_none(record.get('entry_range_low')),
                'effective_stop': _round_or_none(record.get('effective_stop')),
            })

    matched_records.sort(key=lambda x: x.get('report_date', ''), reverse=True)
    feedback['matched_records'] = len(matched_records)
    if matched_records:
        latest_same_stock = next((dict(item) for item in matched_records if item.get('match_type') == 'same_stock'), None)
        feedback['latest_match'] = latest_same_stock or dict(matched_records[0])
    previous_anchor = target_date
    continuous_days = 0
    continuity_match_types = []
    for record in matched_records:
        record_date = record.get('report_date', '')
        if not _is_next_trading_day(record_date, previous_anchor):
            break
        continuous_days += 1
        continuity_match_types.append(record.get('match_type', ''))
        previous_anchor = record_date
    feedback['continuous_days'] = continuous_days
    if continuous_days >= 2:
        if 'same_setup_role' in continuity_match_types:
            feedback['reasons'].append('历史连续探针/Setup反馈确认成立')
        else:
            feedback['reasons'].append('历史连续候选反馈确认成立')
    elif continuous_days == 1:
        feedback['reasons'].append('仅有1个前序候选日，连续性仍偏弱')

    latest_match = feedback.get('latest_match', {}) or {}
    latest_anchor_type = str(latest_match.get('anchor_type', '') or '').strip()
    if latest_match and ('执行候选观察锚点' in latest_anchor_type or '创业板20cm预启动' in latest_anchor_type):
        active_window_days = min(max(int(_safe_float(latest_match.get('holding_days_max', STRATEGY_HOLDING_DAYS_MAX) or STRATEGY_HOLDING_DAYS_MAX)), 3), 5)
        trading_span = _count_trading_days_between(latest_match.get('report_date', ''), target_date)
        trading_days_since_latest = max(trading_span - 1, 0) if trading_span else 0
        feedback['active_window_days'] = active_window_days
        feedback['trading_days_since_latest'] = trading_days_since_latest
        contract_kind = 'gem_breathing_20cm' if '创业板20cm预启动' in latest_anchor_type else 'execute_anchor'
        feedback['contract_kind'] = contract_kind
        if 0 < trading_days_since_latest <= active_window_days:
            feedback['active_watch'] = True
            if contract_kind == 'gem_breathing_20cm':
                feedback['reasons'].append(f'创业板20cm预启动仍在{active_window_days}日观察窗口内')
            else:
                feedback['reasons'].append(f'执行候选观察锚点仍在{active_window_days}日活观察窗口内')
        elif trading_days_since_latest > active_window_days:
            if contract_kind == 'gem_breathing_20cm':
                feedback['reasons'].append(f'创业板20cm预启动已超过{active_window_days}日观察窗口')
            else:
                feedback['reasons'].append(f'执行候选观察锚点已超过{active_window_days}日活观察窗口')
    return feedback


def _extract_candidate_report_prices(candidate=None):
    candidate = candidate or {}
    close_price = _round_or_none(
        candidate.get('close')
        or candidate.get('report_day_close')
        or candidate.get('price')
        or candidate.get('latest_price')
    )
    high_price = _round_or_none(candidate.get('high') or candidate.get('report_day_high') or close_price)
    low_price = _round_or_none(candidate.get('low') or candidate.get('report_day_low'))
    return {
        'close': close_price,
        'high': high_price,
        'low': low_price,
    }


def _build_candidate_feedback_clock(candidate=None, watch_anchor_type='', state_machine_snapshot=None, mainline_name='', target_date=''):
    candidate = candidate or {}
    state_machine_snapshot = state_machine_snapshot or {}
    mainline_name = str(mainline_name or state_machine_snapshot.get('leading_line', '') or '').strip()
    watch_anchor_type = str(watch_anchor_type or candidate.get('watch_anchor_type', '') or '').strip()
    permission_label = str(candidate.get('permission_label', '') or '').strip()
    follow_state = _resolve_candidate_follow_state(candidate)
    confirmation = _candidate_confirmation_chain(candidate)
    tradability_guard = candidate.get('tradability_guard') or {}
    can_trade = tradability_guard.get('can_trade', True)
    decision_stack = candidate.get('decision_stack', {}) or {}
    strong_trigger = (
        bool(candidate.get('abnormal_setup_signal_id'))
        or _safe_float(decision_stack.get('trigger_score', decision_stack.get('setup_priority_score', 0))) >= 80
    )
    history_feedback = _build_candidate_history_feedback(
        candidate=candidate,
        target_date=target_date,
        probe_role=_resolve_probe_role_family(watch_anchor_type=watch_anchor_type, anchor_type=candidate.get('watch_anchor_type', '')),
        watch_anchor_type=watch_anchor_type,
    )
    is_priority_candidate = (
        _candidate_matches_mainline(candidate, mainline_name)
        or candidate.get('is_mainline')
        or '主线' in permission_label
        or '龙头' in permission_label
        or '极看' in permission_label
        or ('主线' in watch_anchor_type and '跨线' not in watch_anchor_type)
    )

    score = 0
    reasons = []
    if is_priority_candidate:
        score += 1
        reasons.append('属于主线/龙头/极看优先对象')
    if follow_state in ('跌不下去', '缩量消化'):
        score += 1
        reasons.append(f'承接状态为{follow_state}')
    if confirmation.get('has_confirmation_chain'):
        score += 1
        reasons.append('具备60分钟确认链')
    if can_trade and not candidate.get('report_day_is_one_word', False):
        score += 1
        reasons.append('可交易性正常')
    if strong_trigger:
        score += 1
        reasons.append('具备正式setup/高触发优先级')
    if history_feedback.get('continuous_days', 0) >= 2:
        score += 1
        reasons.append(f"已连续{history_feedback.get('continuous_days', 0)}个报告日进入候选")

    active_watch = bool(history_feedback.get('active_watch'))
    contract_kind = str(history_feedback.get('contract_kind', '') or '').strip()
    second_shot_ready = False
    second_shot_breakout_price = None
    if active_watch:
        latest_match = history_feedback.get('latest_match', {}) or {}
        prior_confirm = _round_or_none(latest_match.get('confirm_price_60m'))
        prior_range_high = _round_or_none(latest_match.get('entry_range_high'))
        prior_support = _round_or_none(latest_match.get('confirm_support_60m') or latest_match.get('effective_stop'))
        report_prices = _extract_candidate_report_prices(candidate)
        report_close = report_prices.get('close')
        report_high = report_prices.get('high')
        report_low = report_prices.get('low')
        breakout_candidates = [price for price in (prior_range_high, prior_confirm) if price is not None]
        second_shot_breakout_price = max(breakout_candidates) if breakout_candidates else None
        guard_still_holds = prior_support is None or report_low is None or report_low >= prior_support
        if guard_still_holds:
            score += 1
            if contract_kind == 'gem_breathing_20cm':
                reasons.append('创业板20cm预启动在观察窗口内仍未失守guard')
            else:
                reasons.append('执行候选观察锚点在活观察窗口内仍未失守初始guard')
        if (
            guard_still_holds
            and second_shot_breakout_price is not None
            and report_close is not None
            and report_close >= second_shot_breakout_price
        ):
            second_shot_ready = True
            score += 1
            if contract_kind == 'gem_breathing_20cm':
                reasons.append(f'已重新站上{second_shot_breakout_price:.2f}，触发右侧确认/再突破条件')
            else:
                reasons.append(f'已重新站上{second_shot_breakout_price:.2f}，触发二次突破条件')
        elif (
            guard_still_holds
            and prior_confirm is not None
            and report_close is not None
            and report_close >= prior_confirm * 0.985
        ):
            if contract_kind == 'gem_breathing_20cm':
                reasons.append('创业板20cm预启动仍贴着右侧确认位运行，继续保留观察合同')
            else:
                reasons.append('执行候选观察锚点仍贴着初始确认位运行，继续保留活观察')

    reasons.extend(history_feedback.get('reasons', []) or [])

    explicit_ready = candidate.get('candidate_feedback_ready')
    if explicit_ready is None:
        base_ready = bool(
            is_priority_candidate
            and follow_state in ('跌不下去', '缩量消化')
            and confirmation.get('has_confirmation_chain')
            and can_trade
            and not candidate.get('report_day_is_one_word', False)
            and strong_trigger
        )
        ready = bool(
            base_ready
            or second_shot_ready
            or (history_feedback.get('continuous_days', 0) >= 2 and confirmation.get('has_confirmation_chain') and can_trade and strong_trigger)
        )
    else:
        ready = bool(explicit_ready)
        reasons.append('显式标记为反馈已就绪' if ready else '显式标记为反馈未就绪')

    return {
        'ready': ready,
        'score': score,
        'reasons': reasons,
        'confirm_price': confirmation.get('confirm_price'),
        'support_price': confirmation.get('support_price'),
        'has_confirmation_chain': confirmation.get('has_confirmation_chain'),
        'history_feedback': history_feedback,
        'contract_kind': contract_kind,
        'active_watch': active_watch,
        'second_shot_ready': second_shot_ready,
        'second_shot_breakout_price': second_shot_breakout_price,
    }


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
):
    final_gate = final_gate or {}
    state_machine_snapshot = state_machine_snapshot or {}
    special_probe_verdict = special_probe_verdict or {}
    mainline_name = str(mainline_name or state_machine_snapshot.get('leading_line', '') or '').strip()
    execution_bias = str(state_machine_snapshot.get('execution_bias', '') or '').strip()
    candidate = best_stock or watch_anchor or {}
    feedback_clock = _build_candidate_feedback_clock(
        candidate=candidate,
        watch_anchor_type=watch_anchor_type,
        state_machine_snapshot=state_machine_snapshot,
        mainline_name=mainline_name,
        target_date=target_date,
    )
    confirm_price = feedback_clock.get('confirm_price')
    support_price = feedback_clock.get('support_price')
    if confirm_price is not None and support_price is not None:
        trigger_text = f'首个60分钟站上{confirm_price:.2f}且不破{support_price:.2f}'
    elif confirm_price is not None:
        trigger_text = f'首个60分钟站上{confirm_price:.2f}'
    else:
        trigger_text = '完成60分钟确认'

    probe_state = str(special_probe_verdict.get('probe_state', '') or '').strip()
    probe_code = str(special_probe_verdict.get('code', '') or '').strip()
    probe_allows_conditional_30 = bool(special_probe_verdict.get('allows_conditional_30'))
    probe_allows_execute_50 = bool(special_probe_verdict.get('allows_execute_50'))
    pre_allow_conditional_30 = bool(final_gate.get('allow_conditional_30')) or bool(final_gate.get('can_new_entry')) or probe_allows_conditional_30
    branch_20cm = _classify_20cm_branch(
        candidate=candidate,
        mainline_name=mainline_name,
        confirm_price=confirm_price,
        support_price=support_price,
        feedback_ready=bool(feedback_clock.get('ready')),
        allow_conditional_30=pre_allow_conditional_30,
        target_date=target_date,
        mainline_anchor=mainline_anchor,
    )
    weak_to_strong_context = _build_weak_to_strong_context(
        candidate=candidate,
        mainline_name=mainline_name,
        state_machine_snapshot=state_machine_snapshot,
    )
    weak_to_strong_upgrade_ready = bool(
        candidate
        and weak_to_strong_context.get('active')
        and feedback_clock.get('ready')
        and feedback_clock.get('has_confirmation_chain')
        and not branch_20cm.get('is_20cm')
    )

    decision = {
        'participation_mode': 'observe_0',
        'target_position_pct': 0,
        'candidate_feedback_ready': bool(feedback_clock.get('ready')),
        'candidate_feedback_score': feedback_clock.get('score', 0),
        'candidate_feedback_reasons': list(feedback_clock.get('reasons', []) or []),
        'history_feedback': dict(feedback_clock.get('history_feedback', {}) or {}),
        'active_watch': bool(feedback_clock.get('active_watch')),
        'second_shot_ready': bool(feedback_clock.get('second_shot_ready')),
        'second_shot_breakout_price': _round_or_none(feedback_clock.get('second_shot_breakout_price')),
        'trigger_text': trigger_text,
        'sizing_reason': '当前只保留观察权。',
        'special_probe_state': probe_state,
        'special_probe_allows_conditional_30': probe_allows_conditional_30,
        'support_price': support_price,
        'branch_20cm': branch_20cm,
        'weak_to_strong_context': dict(weak_to_strong_context or {}),
        'weak_to_strong_upgrade_ready': weak_to_strong_upgrade_ready,
    }

    if branch_20cm.get('direct_ban'):
        decision['sizing_reason'] = branch_20cm.get('reason') or '20cm 高波动样本当前禁做。'
        return decision

    if probe_state == 'probe_deep_fall':
        decision['sizing_reason'] = '特殊探针已经深跌失效，继续维持0%观察。'
        return decision
    if probe_state == 'probe_flow_unconfirmed' and special_probe_verdict:
        decision['sizing_reason'] = '特殊探针只到承接/观察阶段，外溢确认不足，继续维持0%。'
        return decision

    if execution_bias == 'allow_execute' and best_stock and final_gate.get('can_new_entry') and (not special_probe_verdict or probe_allows_execute_50 or not probe_state):
        if branch_20cm.get('is_20cm'):
            if branch_20cm.get('allow_conditional_30'):
                decision.update({
                    'participation_mode': 'conditional_30',
                    'target_position_pct': 30,
                    'sizing_reason': branch_20cm.get('reason') or '20cm 只允许30%条件试错，不直接给50%。',
                })
            else:
                decision['sizing_reason'] = branch_20cm.get('reason') or '20cm 当前只保留观察权，不直接给50%。'
            return decision
        decision.update({
            'participation_mode': 'execute_50',
            'target_position_pct': 50,
            'sizing_reason': '环境、主线和唯一对象已经同时对齐，只做50%正常执行仓。',
        })
        return decision

    allow_conditional_30 = bool(final_gate.get('allow_conditional_30')) or bool(final_gate.get('can_new_entry')) or probe_allows_conditional_30
    history_continuity_ready = feedback_clock.get('history_feedback', {}).get('continuous_days', 0) >= 2
    second_shot_ready = bool(feedback_clock.get('second_shot_ready'))
    second_shot_breakout_price = _round_or_none(feedback_clock.get('second_shot_breakout_price'))
    bridge_priority_candidate = _is_bridge_priority_setup(candidate, mainline_name=mainline_name)
    bridge_prep_observe_only = execution_bias == 'prep_only' and bridge_priority_candidate
    conditional_probe_ok = (
        (not special_probe_verdict)
        or probe_allows_conditional_30
        or not probe_state
        or probe_code in ('fallback_probe_watch', 'mainline_probe_watch', 'validation_probe_watch', 'no_probe')
    )

    def _conditional_30_reason():
        if second_shot_ready and second_shot_breakout_price is not None:
            return f'执行候选观察锚点仍在活观察窗口内，且已完成{second_shot_breakout_price:.2f}二次突破，只允许30%条件试错仓。'
        if weak_to_strong_upgrade_ready:
            return '主线弱转强样本已具备60分钟确认链：强基底假弱非真弱，只允许30%条件试错仓；后续继续 act right 再评估是否升级到唯一动作。'
        if probe_state == 'probe_crossline_upgrade_ready':
            return '跨线对象已先 act right，只允许30%条件试错，不直接当成主攻线切换。'
        if probe_allows_conditional_30:
            return '环境尚未完全放行，但候选已具备可升级探针反馈，只允许30%条件试错仓。'
        if execution_bias in ('prep_only', 'divergence_only'):
            return '环境未完全共振，但最强对象已经先证明自己，只允许30%条件试错仓。'
        return '环境尚未完全放行，但候选已连续多日报告并保持承接，只允许30%条件试错仓。'

    if (
        execution_bias in ('prep_only', 'divergence_only')
        and candidate
        and allow_conditional_30
        and feedback_clock.get('ready')
        and conditional_probe_ok
        and not bridge_prep_observe_only
    ):
        decision.update({
            'participation_mode': 'conditional_30',
            'target_position_pct': 30,
            'sizing_reason': _conditional_30_reason(),
        })
        return decision
    if execution_bias == 'watch_only' and candidate and allow_conditional_30 and feedback_clock.get('ready') and (history_continuity_ready or probe_allows_conditional_30 or second_shot_ready or weak_to_strong_upgrade_ready) and conditional_probe_ok:
        decision.update({
            'participation_mode': 'conditional_30',
            'target_position_pct': 30,
            'sizing_reason': _conditional_30_reason(),
        })
        return decision

    if execution_bias == 'avoid':
        decision['sizing_reason'] = '主线脉冲已退潮，维持0%观察。'
    elif execution_bias == 'reduce_only':
        decision['sizing_reason'] = '当前只处理旧仓，不给新增仓位。'
    elif execution_bias == 'watch_only':
        if branch_20cm.get('observe_only'):
            decision['sizing_reason'] = branch_20cm.get('reason') or '创业板20cm 当前只保留观察权。'
        elif special_probe_verdict and not conditional_probe_ok:
            decision['sizing_reason'] = '特殊探针反馈还没走到可升级阶段，当前只有观察权，没有执行仓位。'
        else:
            decision['sizing_reason'] = '当前只有观察权，没有执行仓位。'
    elif execution_bias == 'prep_only':
        if bridge_prep_observe_only:
            decision['sizing_reason'] = '当前只保留条件执行预备态，仍需次日继续观察与60分钟确认，不直接升级30%。'
        else:
            decision['sizing_reason'] = '虽有条件执行预备态，但反馈时钟未成熟，维持0%。'
    return decision


def _build_execute_anchor_window_text(position_decision=None, watch_anchor=None, watch_anchor_type=''):
    position_decision = position_decision or {}
    watch_anchor = watch_anchor or {}
    watch_anchor_type = str(watch_anchor_type or '').strip()
    if '执行候选观察锚点' not in watch_anchor_type:
        return ''

    history_feedback = position_decision.get('history_feedback', {}) or {}
    active_watch = bool(position_decision.get('active_watch') or history_feedback.get('active_watch'))
    if not active_watch:
        return ''

    active_window_days = max(int(_safe_float(history_feedback.get('active_window_days', 0))), 0)
    trading_days_since_latest = max(int(_safe_float(history_feedback.get('trading_days_since_latest', 0))), 0)
    remaining_days = max(active_window_days - trading_days_since_latest, 0) if active_window_days else 0
    latest_match = history_feedback.get('latest_match', {}) or {}
    support_price = _round_or_none(
        position_decision.get('support_price')
        or latest_match.get('confirm_support_60m')
        or latest_match.get('effective_stop')
        or watch_anchor.get('execution_stop')
        or watch_anchor.get('display_anchor_price')
    )
    second_shot_breakout_price = _round_or_none(position_decision.get('second_shot_breakout_price'))
    second_shot_ready = bool(position_decision.get('second_shot_ready'))

    prefix = f'这只票按{active_window_days}日活观察管理' if active_window_days else '这只票仍按活观察管理'
    if second_shot_ready and second_shot_breakout_price is not None:
        text = f'{prefix}；已完成{second_shot_breakout_price:.2f}二次突破，只允许30%条件试错'
    else:
        wait_text = f'，当前还剩{remaining_days}日观察寿命' if remaining_days else ''
        trigger_text = f'只有重新站上{second_shot_breakout_price:.2f}才考虑30%条件试错' if second_shot_breakout_price is not None else '只有重新完成二次突破才考虑30%条件试错'
        text = f'{prefix}{wait_text}；{trigger_text}'
    if support_price is not None:
        text += f'；不破{support_price:.2f}继续观察'
    text += '；过期或失守就作废'
    return text


def _build_cycle_triplet_texts(position_decision=None, candidate=None, watch_anchor_type=''):
    position_decision = position_decision or {}
    candidate = candidate or {}
    watch_anchor_type = str(watch_anchor_type or '').strip()
    watch_source = str(candidate.get('watch_source', '') or '').strip()
    gem_contract = candidate.get('gem_breathing_contract') or {}
    target_position_pct = int(_safe_float(position_decision.get('target_position_pct', 0)))
    trigger_text = str(position_decision.get('trigger_text', '') or '完成60分钟确认').strip()
    execute_anchor_window_text = _build_execute_anchor_window_text(
        position_decision=position_decision,
        watch_anchor=candidate,
        watch_anchor_type=watch_anchor_type,
    )
    stop_plan = candidate.get('stop_plan') or {}
    exit_rules = _build_candidate_exit_rules(candidate, stop_plan) if candidate else {
        'holding_days_min': STRATEGY_HOLDING_DAYS_MIN,
        'holding_days_max': STRATEGY_HOLDING_DAYS_MAX,
        'defensive_exit_rule': DEFENSIVE_EXIT_RULE_TEXT,
        'profit_exit_rule': PROFIT_EXIT_RULE_TEXT,
    }
    holding_window_text = _format_holding_window_text(
        exit_rules.get('holding_days_min', STRATEGY_HOLDING_DAYS_MIN),
        exit_rules.get('holding_days_max', STRATEGY_HOLDING_DAYS_MAX),
    )

    observation_cycle = ''
    if watch_source == 'gem_breathing_20cm' and candidate:
        contract_window = max(int(_safe_float(gem_contract.get('active_window_days', 0))), 0)
        if contract_window:
            observation_cycle = f'先给{contract_window}日呼吸感观察合同，重点看均线是否继续收拢、量价是否温和放大、能否走成右侧确认'
        else:
            observation_cycle = f'先给{holding_window_text}呼吸感观察合同，重点看均线是否继续收拢、量价是否温和放大、能否走成右侧确认'
    elif execute_anchor_window_text:
        observation_cycle = execute_anchor_window_text
    elif candidate:
        if target_position_pct == 50:
            observation_cycle = f'先给{holding_window_text}主线观察合同，重点看它是否继续 act right'
        elif target_position_pct == 30:
            observation_cycle = f'先给{holding_window_text}主线观察合同，重点看它是否继续 act right，再决定是否只做30%条件试错'
        else:
            observation_cycle = f'先给{holding_window_text}观察合同，只观察不追，等它自己继续证明'

    intervention_cycle = ''
    second_shot_ready = bool(position_decision.get('second_shot_ready'))
    second_shot_breakout_price = _round_or_none(position_decision.get('second_shot_breakout_price'))
    if target_position_pct == 50:
        intervention_cycle = f'{trigger_text}后按50%执行，才算被市场正式指派接货，不做模糊试单'
    elif target_position_pct == 30:
        if second_shot_ready and second_shot_breakout_price is not None:
            intervention_cycle = f'已完成{second_shot_breakout_price:.2f}二次突破，{trigger_text}后只做30%条件试错接货'
        else:
            intervention_cycle = f'{trigger_text}后才允许30%条件试错，确认后才算小仓位接货，不满足继续观察'
    elif execute_anchor_window_text:
        if second_shot_breakout_price is not None:
            intervention_cycle = f'只有重新站上{second_shot_breakout_price:.2f}并完成60分钟确认，才进入30%条件试错接货'
        else:
            intervention_cycle = f'{trigger_text}后再评估是否进入30%条件试错接货'
    elif candidate:
        if watch_source == 'gem_breathing_20cm':
            upgrade_text = str(gem_contract.get('upgrade_condition_text', '') or '').strip()
            reset_price = _round_or_none(gem_contract.get('reset_breakout_price'))
            if target_position_pct == 30:
                intervention_cycle = f'{trigger_text}后才允许30%条件试错，确认后才算小仓位接货，不满足继续观察'
            elif second_shot_breakout_price is not None:
                intervention_cycle = f'只有重新站上{second_shot_breakout_price:.2f}并完成60分钟确认，才进入30%条件试错接货'
            elif reset_price is not None:
                intervention_cycle = f'只有重新站上{reset_price:.2f}并完成60分钟确认，才进入30%条件试错接货'
            elif upgrade_text:
                intervention_cycle = f'{upgrade_text}；确认后才算进入30%条件试错接货'
            else:
                intervention_cycle = f'{trigger_text}后才评估是否出手，确认前不提前接货'
        else:
            intervention_cycle = f'当前还没进入介入周期；{trigger_text}后才评估是否出手，确认前不提前接货'

    exit_cycle_parts = []
    history_feedback = position_decision.get('history_feedback', {}) or {}
    if execute_anchor_window_text:
        support_price = _round_or_none(
            position_decision.get('support_price')
            or history_feedback.get('latest_match', {}).get('confirm_support_60m')
            or history_feedback.get('latest_match', {}).get('effective_stop')
            or candidate.get('execution_stop')
            or candidate.get('display_anchor_price')
        )
        active_window_days = max(int(_safe_float(history_feedback.get('active_window_days', 0))), 0)
        if support_price is not None:
            exit_cycle_parts.append(f'失守{support_price:.2f}就作废')
        if active_window_days:
            exit_cycle_parts.append(f'{active_window_days}日观察到期也作废')
        if target_position_pct > 0:
            exit_cycle_parts.append(exit_rules.get('defensive_exit_rule', DEFENSIVE_EXIT_RULE_TEXT))
            exit_cycle_parts.append(exit_rules.get('profit_exit_rule', PROFIT_EXIT_RULE_TEXT))
    elif candidate:
        if watch_source == 'gem_breathing_20cm':
            support_price = _round_or_none(
                gem_contract.get('void_price')
                or candidate.get('execution_stop')
                or candidate.get('display_anchor_price')
            )
            contract_window = max(int(_safe_float(gem_contract.get('active_window_days', 0))), 0)
            if support_price is not None:
                exit_cycle_parts.append(f'失守{support_price:.2f}就作废')
            if contract_window:
                exit_cycle_parts.append(f'{contract_window}日观察到期也作废')
            elif holding_window_text:
                exit_cycle_parts.append(f'{holding_window_text}观察到期也作废')
        exit_cycle_parts.append(exit_rules.get('defensive_exit_rule', DEFENSIVE_EXIT_RULE_TEXT))
        exit_cycle_parts.append(exit_rules.get('profit_exit_rule', PROFIT_EXIT_RULE_TEXT))

    exit_cycle = '；'.join([part for part in exit_cycle_parts if str(part or '').strip()])
    return {
        'observation_cycle': observation_cycle,
        'intervention_cycle': intervention_cycle,
        'exit_cycle': exit_cycle,
    }


def _format_candidate_preview(candidates, formatter, limit=3):
    parts = []
    for item in (candidates or [])[:limit]:
        parts.append(formatter(item))
    return " / ".join(parts)


def _derive_watch_anchor_type(candidate, mainline_name=''):
    watch_source = str((candidate or {}).get('watch_source', '') or '').strip()
    bucket, _ = _classify_watch_anchor_bucket(candidate)
    is_mainline = _candidate_matches_mainline(candidate, mainline_name)
    requires_second_confirmation = _requires_crossline_second_confirmation(candidate, mainline_name)

    if watch_source == 'gem_breathing_20cm':
        return '创业板20cm预启动先看谁'
    if requires_second_confirmation:
        if watch_source == 'keep_group_watch' and bucket >= 4:
            return '跨线外溢确认先看谁'
        return '跨线承接成立先看谁'
    if watch_source == 'abnormal_probe':
        return '主线异常先看谁' if is_mainline else '跨线异常先看谁'
    if watch_source == 'keep_group_watch' and bucket >= 4:
        return '主线强分歧先看谁' if is_mainline else '跨线强分歧先看谁'
    if watch_source == 'execute_layer':
        return '主线执行预案先看谁' if is_mainline else '跨线执行预案先看谁'
    if watch_source == 'waiting_layer':
        return '主线继续看谁' if is_mainline else '跨线继续看谁'
    if watch_source == 'keep_group_watch':
        return '主线重点观察谁' if is_mainline else '跨线重点观察谁'
    if is_mainline:
        return '主线重点观察谁'
    return '重点观察谁'


def _derive_pending_candidate_type(candidate, mainline_name=''):
    bucket, _ = _classify_watch_anchor_bucket(candidate)
    is_mainline = _candidate_matches_mainline(candidate, mainline_name)

    if str((candidate or {}).get('watch_source', '') or '').strip() == 'abnormal_probe':
        return '主线异常先盯哪只' if is_mainline else '跨线异常先盯哪只'
    if bucket >= 4:
        return '主线强分歧先盯哪只' if is_mainline else '跨线强分歧先盯哪只'
    if str((candidate or {}).get('watch_source', '') or '').strip() == 'execute_layer':
        return '主线执行预案先盯哪只' if is_mainline else '跨线执行预案先盯哪只'
    return '主线明天先盯哪只' if is_mainline else '跨线明天先盯哪只'


def _derive_watch_anchor_note(candidate, mainline_name=''):
    candidate = candidate or {}
    mainline_name = str(mainline_name or '').strip()
    decision_stack = candidate.get('decision_stack', {}) or {}
    washout_context = decision_stack.get('washout_reclaim_chain', {}) or {}
    trend_context = decision_stack.get('trend_continuation_chain', {}) or {}
    washout_note = str(washout_context.get('note', '') or '').strip()
    trend_note = str(trend_context.get('note', '') or '').strip()
    watch_source = str(candidate.get('watch_source', '') or '').strip()
    if watch_source == 'gem_breathing_20cm':
        base_note = str(candidate.get('watch_anchor_note', '') or candidate.get('note', '') or candidate.get('abnormal_summary', '') or '创业板20cm预启动观察。').strip()
        suffix = '只先进观察池，先看右侧确认和60分钟确认，不满足继续观察'
        return f"{base_note}；{suffix}" if base_note else suffix
    if (not mainline_name or _candidate_matches_mainline(candidate, mainline_name)) and trend_note:
        if washout_note:
            return f"{trend_note}；{washout_note}"
        return trend_note
    if (not mainline_name or _candidate_matches_mainline(candidate, mainline_name)) and washout_note:
        return washout_note
    if not mainline_name or _candidate_matches_mainline(candidate, mainline_name):
        return ''

    sector = str(candidate.get('sector', '') or candidate.get('sector_name', '') or '').strip()
    watch_source = str(candidate.get('watch_source', '') or '').strip()
    bucket, _ = _classify_watch_anchor_bucket(candidate)

    scope_text = f"跨线对象（{sector}）" if sector else "跨线对象"
    if _requires_crossline_second_confirmation(candidate, mainline_name):
        if watch_source == 'keep_group_watch' and bucket >= 4:
            note = (
                f"{scope_text}，当前已进入外溢确认阶段，但仍不代表主攻线从{mainline_name}切换；"
                "只有资金外溢继续扩大且竞争线承接持续，被市场再确认后才评估是否升级"
            )
        else:
            note = (
                f"{scope_text}，当前只到承接成立阶段，不代表主攻线从{mainline_name}切换；"
                "至少再看一天资金外溢是否被市场承认，不满足只观察不升级"
            )
        extra_note = '；'.join([part for part in (washout_note, trend_note) if part])
        return f"{note}；{extra_note}" if extra_note else note
    if watch_source == 'keep_group_watch' and bucket >= 4:
        note = f"{scope_text}，只用于观察市场承接，不代表主攻线从{mainline_name}切换"
    else:
        note = f"{scope_text}，只用于观察强弱，不代表主攻线从{mainline_name}切换"
    extra_note = '；'.join([part for part in (washout_note, trend_note) if part])
    return f"{note}；{extra_note}" if extra_note else note


def _append_watch_anchor_note(report_lines, candidate, prefix='  '):
    note = str((candidate or {}).get('watch_anchor_note', '') or '').strip()
    if note:
        report_lines.append(f"{prefix}{note}")


def _compose_observation_focus_text(confirm_text, price_focus_text=''):
    parts = [f"60分钟确认点{confirm_text}"]
    price_focus_text = str(price_focus_text or '').strip()
    if price_focus_text and price_focus_text != '-':
        parts.append(price_focus_text)
    return "；".join(parts)


def _build_bridge_prep_context(
    position_level='',
    final_gate=None,
    watch_anchor=None,
    watch_anchor_type='',
    state_machine_snapshot=None,
):
    final_gate = final_gate or {}
    watch_anchor = watch_anchor or {}
    state_machine_snapshot = state_machine_snapshot or {}
    position_text = str(position_level or '').strip()
    watch_anchor_type = str(watch_anchor_type or '').strip()
    execution_bias = str(state_machine_snapshot.get('execution_bias', '') or '').strip()
    transition_signal = str(state_machine_snapshot.get('transition_signal', '') or '').strip()
    state_code = str(state_machine_snapshot.get('state_code', '') or '').strip()

    if execution_bias != 'prep_only':
        return {'active': False}
    if not position_text or '二档' not in position_text:
        return {'active': False}
    if final_gate.get('can_new_entry'):
        return {'active': False}
    if not watch_anchor:
        return {'active': False}
    if '跨线' in watch_anchor_type:
        return {'active': False}
    if '主线' not in watch_anchor_type:
        return {'active': False}

    follow_state = str(
        watch_anchor.get('abnormal_follow_state')
        or watch_anchor.get('follow_state')
        or ''
    ).strip()
    if follow_state not in ('跌不下去', '缩量消化'):
        return {'active': False}

    minute_plan = watch_anchor.get('minute_plan') or {}
    confirm_price = _round_or_none(minute_plan.get('confirm_price_60m'))
    guard_price = _round_or_none(
        watch_anchor.get('display_anchor_price')
        or watch_anchor.get('execution_stop')
        or watch_anchor.get('effective_stop')
    )
    if confirm_price is None or guard_price is None:
        return {'active': False}

    name = watch_anchor.get('name', '-')
    code = watch_anchor.get('code', '-')
    priority_keep = (
        _resolve_candidate_setup_id(watch_anchor) == 'burst_hold'
        and follow_state == '跌不下去'
        and '主线' in watch_anchor_type
    )
    upgrade_text = f"若次日首个60分钟站上{confirm_price:.2f}且不破{guard_price:.2f}，才升级为唯一执行候选"
    summary_prefix = '防守档默认不开新仓，但优先保留一只条件执行预备态对象：' if priority_keep else '防守档默认不开新仓，但保留一只条件执行预备态对象：'
    return {
        'active': True,
        'label': '条件执行预备态',
        'candidate_label': f"{name}({code})",
        'upgrade_text': upgrade_text,
        'summary_text': f"{summary_prefix}{upgrade_text}",
        'priority_keep': priority_keep,
    }


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
    final_gate = final_gate or {}
    state_machine_snapshot = state_machine_snapshot or {}
    fallback_text = str(fallback_text or final_gate.get('final_action', '') or '').strip()
    watch_anchor_type = str(watch_anchor_type or '').strip()
    focus_group = focus_group or []
    keep_group = keep_group or []
    delete_group = delete_group or []
    guard_label = _front_position_guard_label(position_level)
    execution_bias = str(state_machine_snapshot.get('execution_bias', '') or '').strip()
    pulse_stage = str(state_machine_snapshot.get('pulse_stage', '') or '').strip()
    bridge_prep = _build_bridge_prep_context(
        position_level=position_level,
        final_gate=final_gate,
        watch_anchor=watch_anchor,
        watch_anchor_type=watch_anchor_type,
        state_machine_snapshot=state_machine_snapshot,
    )
    position_decision = _build_position_sizing_decision(
        final_gate=final_gate,
        state_machine_snapshot=state_machine_snapshot,
        best_stock=best_stock,
        watch_anchor=watch_anchor,
        watch_anchor_type=watch_anchor_type,
        mainline_name=str(state_machine_snapshot.get('leading_line', '') or ''),
        target_date=target_date,
        special_probe_verdict=special_probe_verdict,
    )
    target_position_pct = int(_safe_float(position_decision.get('target_position_pct', 0)))
    trigger_text = position_decision.get('trigger_text', '完成60分钟确认')
    execute_anchor_window_text = _build_execute_anchor_window_text(
        position_decision=position_decision,
        watch_anchor=watch_anchor,
        watch_anchor_type=watch_anchor_type,
    )
    watch_source = str((watch_anchor or {}).get('watch_source', '') or '').strip()
    philosophy_constraint_text = _build_philosophy_constraint_text(
        final_gate=final_gate,
        best_stock=best_stock,
        watch_anchor=watch_anchor,
        watch_anchor_type=watch_anchor_type,
        state_machine_snapshot=state_machine_snapshot,
    )

    if watch_anchor and watch_source == 'gem_breathing_20cm':
        note_text = str((watch_anchor or {}).get('watch_anchor_note', '') or '').strip()
        text = '不开新仓，只观察创业板20cm预启动是否走成右侧确认；完成60分钟确认后才评估30%条件试错，不直接给执行权'
        if note_text:
            text = f"{text}；{note_text}"
        return f"{text}；{philosophy_constraint_text}" if philosophy_constraint_text else text

    if target_position_pct == 50 and best_stock:
        text = f"只做唯一对象，{trigger_text}后按50%执行"
        return f"{text}；{philosophy_constraint_text}" if philosophy_constraint_text else text
    probe_state = str((special_probe_verdict or {}).get('probe_state', '') or '').strip()

    if target_position_pct == 30:
        if execute_anchor_window_text:
            return execute_anchor_window_text
        if probe_state == 'probe_crossline_upgrade_ready':
            return f"跨线对象已先 act right，只允许30%条件试错；{trigger_text}后才执行，不直接当成主攻线切换"
        return f"只允许一只按30%条件试错；{trigger_text}后才执行，不满足继续观察"
    if execution_bias == 'avoid':
        text = '0%，先不跟随，继续观察，等下一轮真正的新启动'
        return f"{text}；{philosophy_constraint_text}" if philosophy_constraint_text else text
    if bridge_prep.get('active'):
        return f"默认不开新仓；{bridge_prep.get('upgrade_text', '')}；否则继续仅观察"
    if watch_anchor and '跨线承接成立' in watch_anchor_type:
        text = '不开新仓，只观察跨线承接有没有继续成立；没有外溢确认前不升级'
        return f"{text}；{philosophy_constraint_text}" if philosophy_constraint_text else text
    if watch_anchor and '跨线外溢确认' in watch_anchor_type:
        text = '不开新仓，只观察跨线资金外溢能否继续扩大；没有主攻线切换证据前仍不升级执行权'
        return f"{text}；{philosophy_constraint_text}" if philosophy_constraint_text else text
    if watch_anchor and '跨线异常' in watch_anchor_type:
        if final_gate.get('can_new_entry'):
            text = '不开仓，先看特殊标的有没有深跌/抗跌，再决定这轮调整是继续收还是重新攻；只有它走成明天唯一能买的那只才考虑买入'
            return f"{text}；{philosophy_constraint_text}" if philosophy_constraint_text else text
        text = '不开新仓，只观察特殊标的有没有深跌/抗跌，再决定这轮调整何时结束'
        return f"{text}；{philosophy_constraint_text}" if philosophy_constraint_text else text
    if watch_anchor and '异常' in watch_anchor_type:
        if final_gate.get('can_new_entry'):
            return '不开仓，先看特殊标的有没有深跌/抗跌，再决定这轮调整是继续收还是重新攻；只有它走成明天唯一能买的那只才考虑买入'
        return '不开新仓，只观察特殊标的有没有深跌/抗跌，再决定这轮调整何时结束'
    if execution_bias == 'watch_only' and final_gate.get('can_new_entry'):
        text = f"0%，主线脉冲已进入{pulse_stage or '钝化'}段，只观察不加仓"
        return f"{text}；{philosophy_constraint_text}" if philosophy_constraint_text else text
    if execution_bias == 'divergence_only' and final_gate.get('can_new_entry') and not best_stock:
        return '0%，先等主线分歧承接成立，不做一致加速追价'
    if best_stock:
        if execution_bias == 'divergence_only':
            return '0%，只做主线分歧承接后的唯一对象，不做一致加速追价'
        return fallback_text

    if final_gate.get('can_new_entry'):
        if focus_group or keep_group:
            return '不开仓，先缩小范围，等市场自己选出明天唯一能买的那只'
        if delete_group:
            return '不开仓，先回避走弱对象，等新的强票走出来'
        return '不开仓，继续观察，等市场自己选出明天唯一能买的那只'

    if focus_group:
        return f'{guard_label}不开新仓，只盯最强那几只，先不抢跑'
    if keep_group:
        return f'{guard_label}不开新仓，只保留观察名单，不给买入资格'
    if delete_group:
        return f'{guard_label}不开新仓，先回避走弱对象'
    return fallback_text


def _front_position_guard_label(position_level=''):
    text = str(position_level or '').strip()
    if not text:
        return '当前档位'
    if '防守' in text:
        return '防守档'
    if '进攻' in text:
        return '进攻档'
    return text


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
    final_gate = final_gate or {}
    focus_group = focus_group or []
    keep_group = keep_group or []
    delete_group = delete_group or []
    state_machine_snapshot = state_machine_snapshot or {}
    bridge_prep = _build_bridge_prep_context(
        position_level=position_level,
        final_gate=final_gate,
        watch_anchor=watch_anchor,
        watch_anchor_type=watch_anchor_type,
        state_machine_snapshot=state_machine_snapshot,
    )
    position_decision = _build_position_sizing_decision(
        final_gate=final_gate,
        state_machine_snapshot=state_machine_snapshot,
        best_stock=best_stock,
        watch_anchor=watch_anchor,
        watch_anchor_type=watch_anchor_type,
        mainline_name=str(state_machine_snapshot.get('leading_line', '') or ''),
        target_date=target_date,
        special_probe_verdict=special_probe_verdict,
    )
    target_position_pct = int(_safe_float(position_decision.get('target_position_pct', 0)))
    trigger_text = position_decision.get('trigger_text', '完成60分钟确认')
    execute_anchor_window_text = _build_execute_anchor_window_text(
        position_decision=position_decision,
        watch_anchor=watch_anchor,
        watch_anchor_type=watch_anchor_type,
    )
    execution_bias = str(state_machine_snapshot.get('execution_bias', '') or '').strip()
    probe_state = str((special_probe_verdict or {}).get('probe_state', '') or '').strip()
    philosophy_constraint_text = _build_philosophy_constraint_text(
        final_gate=final_gate,
        best_stock=best_stock,
        watch_anchor=watch_anchor,
        watch_anchor_type=watch_anchor_type,
        state_machine_snapshot=state_machine_snapshot,
    )
    watch_source = str((watch_anchor or {}).get('watch_source', '') or '').strip()

    if watch_anchor and watch_source == 'gem_breathing_20cm':
        note_text = str((watch_anchor or {}).get('watch_anchor_note', '') or '').strip()
        if target_position_pct == 30:
            text = f"创业板20cm预启动已升级为30%条件试错候选；{trigger_text}后才允许试错，不满足继续观察"
        else:
            text = '创业板20cm预启动只先进观察池；先看右侧确认和60分钟确认，再决定是否只做30%条件试错'
        if note_text:
            text = f"{text}；{note_text}"
        return f"{text}；{philosophy_constraint_text}" if philosophy_constraint_text else text

    if target_position_pct == 50 and best_stock:
        text = f"市场已允许出手，而且已经缩到一只可买股；只做50%执行仓，{trigger_text}后才动手"
        return f"{text}；{philosophy_constraint_text}" if philosophy_constraint_text else text
    if target_position_pct == 30:
        if execute_anchor_window_text:
            return "30%条件试错仓；执行候选观察锚点已进入二次突破升级阶段，仍不直接给50%执行仓"
        if probe_state == 'probe_crossline_upgrade_ready':
            return f"30%条件试错仓；跨线对象已先 act right，{trigger_text}后才允许试错，不直接当成主攻线切换"
        return f"30%条件试错仓；{trigger_text}后才允许试错，不满足继续观察"
    if execution_bias == 'avoid':
        text = '0%，先不跟随，继续观察，等下一轮真正的新启动'
        return f"{text}；{philosophy_constraint_text}" if philosophy_constraint_text else text

    if final_gate.get('can_new_entry'):
        if best_stock:
            text = "市场已允许出手，而且已经缩到一只可买股"
            return f"{text}；{philosophy_constraint_text}" if philosophy_constraint_text else text
        if watch_anchor:
            if '异常' in str(watch_anchor_type or ''):
                text = "市场已允许出手，但现在只剩特殊标的观察层，还没有唯一执行对象"
                return f"{text}；{philosophy_constraint_text}" if philosophy_constraint_text else text
            text = "市场已允许出手，但现在还只有重点盯盘股，还没有缩到一只可买股"
            return f"{text}；{philosophy_constraint_text}" if philosophy_constraint_text else text
        if focus_group:
            return "市场已允许出手，但还没有缩到一只可买股"
        if keep_group:
            return "市场已允许出手，但当前只有观察层，还没有清晰执行对象"
        if delete_group:
            return "市场已允许出手，但当前这批票偏弱，先回避，不抢反弹"
        return "市场已允许出手，但当前还没有可买股"

    guard_label = _front_position_guard_label(position_level)
    if bridge_prep.get('active'):
        summary_text = str(bridge_prep.get('summary_text', '') or '').strip()
        if summary_text:
            return summary_text
        return f"{guard_label}默认不开新仓，但保留一只条件执行预备态对象：{bridge_prep.get('upgrade_text', '')}"
    if watch_anchor:
        if '跨线' in str(watch_anchor_type or ''):
            return f"{guard_label}不开新仓，只保留高优先级观察权，先看资金会不会向竞争线外溢"
        return f"{guard_label}不开新仓，只保留高优先级观察权，先看主线对象能否继续证明自己"
    if focus_group:
        return f"{guard_label}不开新仓，个股结构未坏，但环境未开"
    if keep_group:
        return f"{guard_label}不开新仓，当前只保留观察层，不给执行权"
    if delete_group:
        return f"{guard_label}不开新仓，主线对象偏弱，先不出手"
    return f"{guard_label}不开新仓，只保留市场研究与观察权"


def sort_watch_anchor_candidates(candidates, mainline_name='', state_machine_snapshot=None):
    prepared = []
    state_machine_snapshot = state_machine_snapshot or {}
    for item in candidates or []:
        candidate = dict(item or {})
        stack = candidate.get('decision_stack', {}) or {}
        bucket, label = _classify_watch_anchor_bucket(candidate)
        raw_risk_score = _safe_float(candidate.get('raw_risk_score', 0))
        risk_score = _safe_float(candidate.get('risk_score', 0))
        repair_count = len(candidate.get('repair_buffers', []) or [])
        risk_penalty_count = len(candidate.get('risk_penalties', []) or [])
        watch_source = str(candidate.get('watch_source', '') or '').strip()
        abnormal_priority_score = _safe_float(stack.get('setup_priority_score', stack.get('trigger_score', 0)))
        has_formal_setup = bool(stack.get('has_formal_abnormal_setup', _candidate_has_formal_abnormal_setup(candidate)))
        is_resilient_abnormal = bool(stack.get('is_resilient_abnormal', _candidate_is_resilient_abnormal(candidate)))

        weak_to_strong_context = _build_weak_to_strong_context(
            candidate=candidate,
            mainline_name=mainline_name,
            state_machine_snapshot={
                **state_machine_snapshot,
                'leading_line': mainline_name or state_machine_snapshot.get('leading_line', ''),
            },
        )
        observation_priority_score = (
            bucket * 1000
            + abnormal_priority_score * 12
            + _safe_float(stack.get('mainline_score', 0)) * 8
            + _safe_float(stack.get('memory_score', 0)) * 6
            + _safe_float(stack.get('trigger_score', 0)) * 5
            + _safe_float(stack.get('tradability_score', 0)) * 3
            + min(raw_risk_score, 40) * 1.2
            + repair_count * 25
            - risk_score * 4
            - risk_penalty_count * 4
            + _safe_float(candidate.get('composite_score', 0)) * 100
            + _safe_float(weak_to_strong_context.get('score_bonus', 0))
        )
        if has_formal_setup:
            observation_priority_score += 180
        if is_resilient_abnormal:
            observation_priority_score += 90
        if watch_source == 'keep_group_watch':
            observation_priority_score += 40
        if watch_source == 'waiting_layer':
            observation_priority_score -= 20
        if watch_source == 'abnormal_probe':
            observation_priority_score += 120
        if _is_bridge_priority_setup(candidate, mainline_name=mainline_name):
            observation_priority_score += 180

        candidate['watch_priority_bucket'] = bucket
        candidate['watch_priority_label'] = label
        candidate['watch_priority_score'] = round(observation_priority_score, 2)
        candidate['watch_anchor_type'] = _derive_watch_anchor_type(candidate, mainline_name=mainline_name)
        base_watch_anchor_note = _derive_watch_anchor_note(candidate, mainline_name=mainline_name)
        weak_note = str(weak_to_strong_context.get('note_text', '') or '').strip()
        if weak_note and weak_note not in base_watch_anchor_note:
            candidate['watch_anchor_note'] = '；'.join(part for part in (base_watch_anchor_note, weak_note) if part)
        else:
            candidate['watch_anchor_note'] = base_watch_anchor_note
        candidate['weak_to_strong_context'] = weak_to_strong_context
        prepared.append(candidate)

    return sorted(
        prepared,
        key=lambda item: (
            _safe_float(item.get('watch_priority_score', 0)),
            (item.get('decision_stack', {}) or {}).get('setup_priority_score', 0),
            (item.get('decision_stack', {}) or {}).get('mainline_score', 0),
            (item.get('decision_stack', {}) or {}).get('memory_score', 0),
            (item.get('decision_stack', {}) or {}).get('trigger_score', 0),
            -( _safe_float(item.get('risk_score', 0)) ),
            _safe_float(item.get('composite_score', 0)),
        ),
        reverse=True,
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
    abnormal_watch_pool, _ = _split_abnormal_watch_pool(abnormal_watch_pool)
    state_machine_snapshot = state_machine_snapshot or {}
    if not abnormal_watch_pool:
        return []

    candidate_lookup = {}
    for item in existing_candidates or []:
        code = normalize_stock_code((item or {}).get('code', ''))
        if code and code not in candidate_lookup:
            candidate_lookup[code] = dict(item or {})

    seed_lookup = {}
    for item in seed_candidates or []:
        code = normalize_stock_code((item or {}).get('code', ''))
        if code and code not in seed_lookup:
            seed_lookup[code] = dict(item or {})

    prepared = []
    seen_codes = set()
    for abnormal_item in abnormal_watch_pool or []:
        code = normalize_stock_code(abnormal_item.get('code', ''))
        if not code or code in seen_codes:
            continue
        seen_codes.add(code)

        if candidate_lookup.get(code):
            candidate = dict(candidate_lookup[code] or {})
        else:
            seed = dict(seed_lookup.get(code, {}) or {})
            entry_price = _safe_float(
                seed.get('close')
                or seed.get('price')
                or abnormal_item.get('anchor_price')
            )
            if entry_price <= 0:
                continue

            recent_bars = fetch_recent_price_bars(code, target_date, lookback_days=4)
            daily_anchor_bars = fetch_recent_price_bars(
                code,
                target_date,
                lookback_days=max(STOP_PRIOR_LOW_TRADING_DAYS + 5, 10),
            )
            tradability_guard = evaluate_live_tradability(
                {
                    **seed,
                    'code': code,
                    'name': abnormal_item.get('name', seed.get('name', '')),
                    'close': entry_price,
                },
                target_date,
                recent_bars=recent_bars,
            )
            candidate = build_waiting_stock_plan(
                {
                    **seed,
                    'name': abnormal_item.get('name', seed.get('name', '未知')),
                    'code': code,
                    'sector': seed.get('sector') or abnormal_item.get('sector', ''),
                    'close': entry_price,
                    'entry_price': entry_price,
                    'condition': abnormal_item.get('action_rule') or '只跟踪异常承接，不直接下单',
                    'tradability_guard': tradability_guard,
                    'report_day_is_one_word': tradability_guard.get('report_day_is_one_word', False),
                },
                target_date,
                reason=abnormal_item.get('action_rule') or '只跟踪异常承接，不直接下单',
                signal_type=_map_setup_id_to_signal_type(abnormal_item.get('setup_signal_id', '')),
                recent_bars=daily_anchor_bars,
            )
            candidate.update({
                'permission_label': '异常观察权',
                'permission_reason': '当前只跟踪异常承接，不自动授予执行权',
                'tradability_guard': tradability_guard,
                'report_day_is_one_word': tradability_guard.get('report_day_is_one_word', False),
            })

        candidate.update({
            'name': abnormal_item.get('name', candidate.get('name', '未知')),
            'code': code,
            'sector': candidate.get('sector') or abnormal_item.get('sector', ''),
            'abnormal_date': abnormal_item.get('abnormal_date', ''),
            'abnormal_type': abnormal_item.get('abnormal_type', ''),
            'abnormal_follow_state': abnormal_item.get('follow_state', candidate.get('abnormal_follow_state', '')),
            'abnormal_setup_signal_id': abnormal_item.get('setup_signal_id', candidate.get('abnormal_setup_signal_id', '')),
            'abnormal_setup_signal_label': abnormal_item.get('setup_signal_label', candidate.get('abnormal_setup_signal_label', '')),
            'abnormal_setup_signal_phase': abnormal_item.get('setup_signal_phase', candidate.get('abnormal_setup_signal_phase', '')),
            'abnormal_score': abnormal_item.get('abnormal_score', candidate.get('abnormal_score', 0)),
            'anchor_price': abnormal_item.get('anchor_price', candidate.get('anchor_price')),
            'display_anchor_price': abnormal_item.get('display_anchor_price', candidate.get('display_anchor_price')),
            'is_mainline': bool(abnormal_item.get('is_mainline')),
            'action_rule': abnormal_item.get('action_rule') or candidate.get('action_rule') or '',
            'reason': abnormal_item.get('action_rule') or candidate.get('reason') or '',
            'watch_source': 'abnormal_probe',
        })
        minute_plan = dict(candidate.get('minute_plan', {}) or {})
        if abnormal_item.get('confirm_price_60m') is not None:
            minute_plan['confirm_price_60m'] = abnormal_item.get('confirm_price_60m')
        if abnormal_item.get('confirm_support_60m') is not None:
            minute_plan['confirm_support_60m'] = abnormal_item.get('confirm_support_60m')
        if abnormal_item.get('structure_stop_30m') is not None:
            minute_plan['structure_stop_30m'] = abnormal_item.get('structure_stop_30m')
        if abnormal_item.get('confirm_rule_60m'):
            minute_plan['confirm_rule_60m'] = abnormal_item.get('confirm_rule_60m')
        if minute_plan:
            candidate['minute_plan'] = minute_plan

        risk_signal = get_abnormal_follow_risk_signal(candidate)
        candidate.setdefault('abnormal_light', risk_signal.get('light', ''))
        candidate.setdefault(
            'risk_level',
            _infer_risk_level_from_abnormal_follow_state(candidate.get('abnormal_follow_state', '')),
        )
        if not candidate.get('raw_risk_score'):
            candidate['raw_risk_score'] = 18 if _candidate_is_resilient_abnormal(candidate) else 8
        if _candidate_is_resilient_abnormal(candidate) and not candidate.get('repair_buffers'):
            candidate['repair_buffers'] = ['异常承接未坏']

        if not candidate.get('decision_stack'):
            candidate = score_candidate_decision_stack(
                score_execution_candidate(candidate, ev_calibration or {}),
                final_gate=final_gate,
                mainline_name=mainline_name,
                conviction_codes=conviction_codes,
                leader_memory_codes=leader_memory_codes,
                state_machine_snapshot=state_machine_snapshot,
                target_date=target_date,
            )

        prepared.append(candidate)

    return sort_watch_anchor_candidates(
        prepared,
        mainline_name=mainline_name,
        state_machine_snapshot=state_machine_snapshot,
    )


def _build_abnormal_probe_group(
    style_switch_snapshot=None,
    abnormal_watch_pool=None,
    mainline_name='',
    watch_anchor=None,
):
    style_switch_snapshot = style_switch_snapshot or {}
    abnormal_watch_pool, degraded_pool = _split_abnormal_watch_pool(abnormal_watch_pool)
    formal_pool = [item for item in (abnormal_watch_pool or []) if not _is_degraded_abnormal_snapshot(item)]
    if not formal_pool:
        return {}

    mainline_name = str(mainline_name or '').strip()
    follow_state_rank = {
        '跌不下去': 4,
        '缩量消化': 3,
        '新异动待观察': 2,
        '已经转弱': 1,
    }

    def abnormal_sort_key(item):
        follow_state = str(item.get('follow_state', '') or '').strip()
        sector_name = str(item.get('sector', '') or '').strip()
        return (
            follow_state_rank.get(follow_state, 0),
            1 if sector_name and sector_name != '未知' else 0,
            1 if item.get('is_mainline') or _candidate_matches_mainline(item, mainline_name) else 0,
            _safe_float(item.get('abnormal_score', 0)),
            item.get('abnormal_date', ''),
        )

    sorted_pool = sorted(formal_pool, key=abnormal_sort_key, reverse=True)
    resilient_pool = [
        item for item in sorted_pool
        if str(item.get('follow_state', '') or '').strip() in ('跌不下去', '缩量消化')
    ]

    mainline_pool = [
        item for item in sorted_pool
        if item.get('is_mainline') or _candidate_matches_mainline(item, mainline_name)
    ]
    crossline_pool = [
        item for item in sorted_pool
        if item not in mainline_pool
    ]

    selected_codes = {
        normalize_stock_code((mainline_pool[0] if mainline_pool else {}).get('code', '')),
        normalize_stock_code((crossline_pool[0] if crossline_pool else {}).get('code', '')),
    }
    validation_probe = None
    for item in resilient_pool or sorted_pool:
        code = normalize_stock_code(item.get('code', ''))
        if code and code in selected_codes:
            continue
        validation_probe = item
        break
    if not validation_probe:
        validation_probe = resilient_pool[0] if resilient_pool else (sorted_pool[0] if sorted_pool else None)

    return {
        'style_code': style_switch_snapshot.get('style_code', ''),
        'style_label': style_switch_snapshot.get('style_label', ''),
        'mainline_abnormal_probe': mainline_pool[0] if mainline_pool else None,
        'crossline_abnormal_probe': crossline_pool[0] if crossline_pool else None,
        'validation_probe': validation_probe,
        'fallback_watch_anchor': watch_anchor or {},
        'mainline_missing_reason': (
            f"{mainline_name}方向今天没有进入异常库的放量异常"
            if mainline_name and not mainline_pool else ''
        ),
        'pool_size': len(sorted_pool),
        'degraded_count': len(degraded_pool),
    }


def _format_abnormal_probe_text(
    probe,
    role_label='',
    mainline_name='',
    fallback_watch_anchor=None,
):
    fallback_watch_anchor = fallback_watch_anchor or {}
    if not probe:
        if role_label == '主线异动里先看谁':
            fallback_name = fallback_watch_anchor.get('name')
            fallback_code = fallback_watch_anchor.get('code')
            if fallback_name:
                fallback_text = f"{fallback_name}({fallback_code})" if fallback_code else fallback_name
                fallback_is_mainline = (
                    not mainline_name
                    or _candidate_matches_mainline(fallback_watch_anchor, mainline_name)
                )
                fallback_is_abnormal = _candidate_has_formal_abnormal_setup(fallback_watch_anchor)
                if mainline_name:
                    if fallback_is_mainline and fallback_is_abnormal:
                        return f"暂无，{mainline_name}方向今天没有进入异常库的放量异常；主线暂只保留异常承接观察{fallback_text}"
                    if fallback_is_mainline:
                        return f"暂无，{mainline_name}方向今天没有进入异常库的放量异常；主线只保留普通盯盘股{fallback_text}"
                    if fallback_is_abnormal:
                        return f"暂无，{mainline_name}方向今天没有进入异常库的放量异常；当前只保留跨线异常观察{fallback_text}"
                    return f"暂无，{mainline_name}方向今天没有进入异常库的放量异常"
                return f"暂无，当前只保留普通盯盘股{fallback_text}"
            if mainline_name:
                return f"暂无，{mainline_name}方向今天没有进入异常库的放量异常"
            return "暂无，当前没有进入异常库的主线放量异常"
        return ''

    name = probe.get('name', '-')
    code = probe.get('code', '-')
    setup_label = probe.get('setup_signal_label', probe.get('abnormal_type', '异常')) or '异常'
    follow_state = probe.get('follow_state', '-') or '-'
    action_rule = str(probe.get('action_rule', '') or '').strip()
    watch_anchor_note = str(probe.get('watch_anchor_note', '') or '').strip()
    if (
        not watch_anchor_note
        and role_label == '跨线异动里先看谁'
        and mainline_name
        and not (probe.get('is_mainline') or _candidate_matches_mainline(probe, mainline_name))
    ):
        sector = str(probe.get('sector', '') or '').strip()
        if sector:
            watch_anchor_note = f"跨线对象（{sector}），只用于观察强弱，不代表主攻线从{mainline_name}切换"
        else:
            watch_anchor_note = f"跨线对象，只用于观察强弱，不代表主攻线从{mainline_name}切换"

    text = f"{name}({code})，{setup_label} / {follow_state}"
    if action_rule:
        text += f"，{action_rule}"
    if watch_anchor_note:
        text += f"；{watch_anchor_note}"
    return text


def _build_mainline_upgrade_probe_context(candidate=None, mainline_name='', target_date=''):
    candidate = candidate or {}
    mainline_name = str(mainline_name or '').strip()
    follow_state = str(candidate.get('follow_state', '') or candidate.get('abnormal_follow_state', '') or '').strip()
    watch_anchor_type = str(candidate.get('watch_anchor_type', '') or '').strip()
    decision_stack = candidate.get('decision_stack', {}) or {}
    washout_chain = decision_stack.get('washout_reclaim_chain', {}) or {}
    trend_chain = decision_stack.get('trend_continuation_chain', {}) or {}
    strong_setup = bool(candidate.get('abnormal_setup_signal_id')) or _safe_float(decision_stack.get('trigger_score', 0)) >= 80
    is_mainline = (
        bool(candidate.get('is_mainline'))
        or _candidate_matches_mainline(candidate, mainline_name)
        or ('主线' in watch_anchor_type and '跨线' not in watch_anchor_type)
    )
    feedback_clock = _build_candidate_feedback_clock(
        candidate=candidate,
        watch_anchor_type=watch_anchor_type,
        state_machine_snapshot={'leading_line': mainline_name},
        mainline_name=mainline_name,
        target_date=target_date,
    )
    active = bool(is_mainline and follow_state in ('跌不下去', '缩量消化') and strong_setup)
    history_continuity = int(_safe_float((feedback_clock.get('history_feedback', {}) or {}).get('continuous_days', 0)))
    upgrade_ready = bool(
        active and feedback_clock.get('ready') and (
            trend_chain.get('active')
            or (washout_chain.get('active') and washout_chain.get('recognition_ok') and washout_chain.get('within_3d_window'))
            or history_continuity >= 2
        )
    )
    if upgrade_ready:
        probe_state = 'probe_mainline_upgrade_ready'
        note = '主线探针已具备升级条件：承接未坏、确认链完整，且已出现连续反馈/主线修复证据。'
        action = '保留主线可升级探针；若次日继续 act right，可进入30%条件试错观察。'
    elif active:
        probe_state = 'probe_resilient_hold'
        note = '主线探针仍在观察阶段：承接未坏，但升级证据还不够。'
        action = '继续盯主线探针能否给出连续反馈，再决定是否升级。'
    else:
        probe_state = 'probe_flow_unconfirmed'
        note = '主线探针尚未形成可升级条件。'
        action = '先观察主线探针是否抗跌，不提前升级。'
    return {
        'active': active,
        'is_mainline': is_mainline,
        'upgrade_ready': upgrade_ready,
        'probe_state': probe_state,
        'allows_conditional_30': upgrade_ready,
        'allows_execute_50': False,
        'note': note,
        'action': action,
        'feedback_clock': feedback_clock,
    }


def _is_20cm_stock(candidate=None):
    candidate = candidate or {}
    code = normalize_stock_code(candidate.get('code') or candidate.get('stock_code') or '')
    return code.startswith('30')


def _evaluate_gem_breathing_window(bars=None, lookback_days=10):
    bars = list(bars or [])
    min_required_bars = max(lookback_days, 8)
    if len(bars) < min_required_bars:
        return {'active': False}

    window = bars[-lookback_days:]
    closes = [_safe_float(bar.get('close')) for bar in window]
    highs = [_safe_float(bar.get('high')) for bar in window]
    lows = [_safe_float(bar.get('low')) for bar in window]
    if any(price <= 0 for price in closes):
        return {'active': False}

    def _ma(values, n, idx):
        if idx + 1 < n:
            return None
        arr = values[idx - n + 1: idx + 1]
        return sum(arr) / len(arr)

    spread_values = []
    abs_pct_values = []
    amp_values = []
    sign_changes = 0
    prev_sign = 0
    sign_series = []
    for i in range(1, len(closes)):
        pct = closes[i] / closes[i - 1] - 1 if closes[i - 1] > 0 else 0.0
        abs_pct_values.append(abs(pct) * 100)
        amp_values.append((highs[i] - lows[i]) / closes[i - 1] * 100 if closes[i - 1] > 0 else 0.0)
        mas = []
        for n in (3, 5, 10):
            m = _ma(closes, n, i)
            if m is not None:
                mas.append(m)
        if len(mas) == 3:
            spread_values.append((max(mas) - min(mas)) / closes[i] * 100)
        sign = 1 if pct > 0 else (-1 if pct < 0 else 0)
        sign_series.append(sign)
        if prev_sign and sign and prev_sign != sign:
            sign_changes += 1
        if sign:
            prev_sign = sign

    if not spread_values:
        return {'active': False}

    avg_spread = sum(spread_values) / len(spread_values)
    avg_abs_pct = sum(abs_pct_values) / len(abs_pct_values) if abs_pct_values else 0.0
    avg_amp = sum(amp_values) / len(amp_values) if amp_values else 0.0

    recent_window = min(5, len(abs_pct_values))
    if recent_window < 4 or len(spread_values) < 1:
        return {'active': False}
    recent_abs_pct = sum(abs_pct_values[-recent_window:]) / recent_window
    recent_amp = sum(amp_values[-recent_window:]) / recent_window
    recent_spread_window = min(recent_window, len(spread_values))
    recent_spread = sum(spread_values[-recent_spread_window:]) / recent_spread_window

    prior_abs_slice = abs_pct_values[-recent_window * 2:-recent_window] if len(abs_pct_values) >= recent_window * 2 else abs_pct_values[:-recent_window]
    prior_amp_slice = amp_values[-recent_window * 2:-recent_window] if len(amp_values) >= recent_window * 2 else amp_values[:-recent_window]
    if not prior_abs_slice or not prior_amp_slice:
        return {'active': False}
    prior_abs_pct = sum(prior_abs_slice) / len(prior_abs_slice)
    prior_amp = sum(prior_amp_slice) / len(prior_amp_slice)

    recent_sign_changes = 0
    recent_sign_slice = sign_series[-recent_window:]
    prev_recent_sign = 0
    for sign in recent_sign_slice:
        if prev_recent_sign and sign and prev_recent_sign != sign:
            recent_sign_changes += 1
        if sign:
            prev_recent_sign = sign

    relative_compression_ready = (
        recent_spread <= 3.0
        and recent_abs_pct <= min(2.4, prior_abs_pct * 0.8)
        and recent_amp <= min(4.0, prior_amp * 0.95)
        and recent_sign_changes >= 2
    )
    absolute_compression_ready = (
        recent_spread <= 2.0
        and recent_abs_pct <= 1.5
        and recent_amp <= 2.8
        and recent_sign_changes >= 3
    )
    wide_reacceleration_ready = (
        recent_spread <= 3.0
        and recent_abs_pct <= 2.9
        and recent_amp <= 7.2
        and recent_sign_changes >= 3
        and avg_abs_pct <= 3.4
        and avg_amp <= 8.0
        and recent_amp <= prior_amp * 0.85
    )
    compression_ready = relative_compression_ready or absolute_compression_ready or wide_reacceleration_ready
    active = (
        compression_ready
        and avg_spread <= 5.0
        and sign_changes >= 3
        and avg_abs_pct <= 5.5
        and avg_amp <= 8.5
    )
    tier = 'tight' if active and recent_spread <= 2.0 and recent_abs_pct <= 1.8 and recent_amp <= 3.2 and recent_sign_changes >= 3 else 'loose' if active else ''
    note = ''
    if active:
        note = '创业板20cm均线粘合+蛇形走位，属于预启动呼吸感观察。' if tier == 'tight' else '创业板20cm存在均线收拢与蛇形呼吸，适合先纳入预启动观察。'

    return {
        'active': active,
        'tier': tier,
        'avg_spread_pct': round(avg_spread, 2),
        'avg_abs_pct': round(avg_abs_pct, 2),
        'avg_amp_pct': round(avg_amp, 2),
        'sign_changes': sign_changes,
        'recent_spread_pct': round(recent_spread, 2),
        'recent_abs_pct': round(recent_abs_pct, 2),
        'recent_amp_pct': round(recent_amp, 2),
        'recent_sign_changes': recent_sign_changes,
        'prior_abs_pct': round(prior_abs_pct, 2),
        'prior_amp_pct': round(prior_amp, 2),
        'compression_ready': compression_ready,
        'note': note,
    }


def _build_gem_breathing_prep_context(candidate=None, target_date='', lookback_days=10):
    candidate = candidate or {}
    if not _is_20cm_stock(candidate):
        return {'active': False}

    code = normalize_stock_code(candidate.get('code') or candidate.get('stock_code') or '')
    target_date = _normalize_kline_date_str(target_date)
    if not code or not target_date:
        return {'active': False}

    min_required_bars = max(lookback_days, 8)
    target_dt = _parse_kline_date(target_date)
    recent_scan_start = target_date
    if target_dt:
        recent_scan_start = (target_dt - datetime.timedelta(days=max(lookback_days * 5, 45))).strftime('%Y-%m-%d')
    bars = fetch_daily_price_bars(
        code,
        recent_scan_start,
        target_date,
        is_index=False,
        prefer_fast=True,
        allow_baostock_fallback=False,
    )
    bars = [bar for bar in (bars or []) if _normalize_kline_date_str(bar.get('date')) <= target_date]
    return _evaluate_gem_breathing_window(bars, lookback_days=lookback_days)


def _get_gem_stock_universe():
    global _gem_stock_universe_cache
    if _gem_stock_universe_cache is not None:
        return [dict(item) for item in _gem_stock_universe_cache]
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
    stock_meta_map = stock_meta_map or {}
    items = []
    base_candidates = {}
    for code, meta in (stock_meta_map or {}).items():
        norm_code = normalize_stock_code(code)
        if not norm_code.startswith('30'):
            continue
        candidate = dict(meta or {})
        candidate['code'] = normalize_stock_code(candidate.get('code') or norm_code)
        base_candidates[candidate['code']] = candidate
    for item in _get_gem_stock_universe():
        code = normalize_stock_code(item.get('code', ''))
        if not code.startswith('30') or code not in base_candidates:
            continue
        merged = dict(base_candidates.get(code, {}))
        merged.update({k: v for k, v in (item or {}).items() if v not in (None, '')})
        merged['code'] = code
        base_candidates[code] = merged
    for code, candidate in base_candidates.items():
        if not _is_20cm_stock(candidate):
            continue
        ctx = _build_gem_breathing_prep_context(candidate, target_date=target_date)
        if not ctx.get('active'):
            continue
        items.append({
            'name': candidate.get('name', ''),
            'code': candidate.get('code', ''),
            'sector': candidate.get('sector', ''),
            'tier': ctx.get('tier', ''),
            'note': ctx.get('note', ''),
            'score': _safe_float(candidate.get('score', 0)),
            'close': _safe_float(candidate.get('close', candidate.get('latest_price', candidate.get('最新价', 0)))),
            'volume': _safe_float(candidate.get('volume', candidate.get('成交额', 0))),
            'change_pct': _safe_float(candidate.get('change_pct', candidate.get('涨跌幅', 0))),
            'avg_spread_pct': _safe_float(ctx.get('avg_spread_pct', 0)),
            'sign_changes': int(_safe_float(ctx.get('sign_changes', 0))),
        })
    items.sort(key=lambda x: (1 if x.get('tier') == 'tight' else 0, x.get('score', 0), -x.get('avg_spread_pct', 99), x.get('sign_changes', 0)), reverse=True)
    return items


def _discover_gem_breathing_candidates(stock_meta_map, target_date='', mainline_name='', limit=3):
    all_items = _discover_all_gem_breathing_candidates(stock_meta_map, target_date=target_date)
    if mainline_name:
        all_items = [item for item in all_items if _candidate_matches_mainline(item, mainline_name)]
    return all_items[:limit]


def _discover_filtered_out_gem_breathing_candidates(stock_meta_map, target_date='', mainline_name='', limit=3):
    if not mainline_name:
        return []
    all_items = _discover_all_gem_breathing_candidates(stock_meta_map, target_date=target_date)
    items = []
    for item in all_items:
        if _candidate_matches_mainline(item, mainline_name):
            continue
        filtered_item = dict(item)
        filtered_item['filtered_reason'] = f'当前主线是{mainline_name}，该样本不在主线内，因此不纳入正式观察池。'
        items.append(filtered_item)
    return items[:limit]


def _build_gem_breathing_textbook_profile(candidate=None, target_date='', lookback_days=10, review_days=60):
    candidate = candidate or {}
    if not _is_20cm_stock(candidate):
        return {
            'label': '',
            'total_active_count': 0,
            'tight_count': 0,
            'loose_count': 0,
            'last_active_date': '',
            'score_bonus': 0,
            'summary_text': '',
        }

    code = normalize_stock_code(candidate.get('code') or candidate.get('stock_code') or '')
    target_date = _normalize_kline_date_str(target_date)
    if not code or not target_date:
        return {
            'label': '',
            'total_active_count': 0,
            'tight_count': 0,
            'loose_count': 0,
            'last_active_date': '',
            'score_bonus': 0,
            'summary_text': '',
        }

    bars = fetch_daily_price_bars(
        code,
        '2025-01-01',
        target_date,
        is_index=False,
        prefer_fast=True,
        allow_baostock_fallback=False,
    ) or []
    bars = [bar for bar in bars if _normalize_kline_date_str(bar.get('date')) <= target_date]
    min_required_bars = max(lookback_days, 8)
    if len(bars) < min_required_bars:
        return {
            'label': '',
            'total_active_count': 0,
            'tight_count': 0,
            'loose_count': 0,
            'last_active_date': '',
            'score_bonus': 0,
            'summary_text': '',
        }

    start_idx = max(min_required_bars - 1, len(bars) - max(review_days, min_required_bars))
    active_points = []
    for idx in range(start_idx, len(bars)):
        window_bars = bars[:idx + 1]
        ctx = _evaluate_gem_breathing_window(window_bars, lookback_days=lookback_days)
        if not ctx.get('active'):
            continue
        active_points.append({
            'date': _normalize_kline_date_str(bars[idx].get('date')),
            'tier': ctx.get('tier', ''),
        })

    total_active_count = len(active_points)
    tight_count = len([item for item in active_points if item.get('tier') == 'tight'])
    loose_count = len([item for item in active_points if item.get('tier') == 'loose'])
    last_active_date = active_points[-1]['date'] if active_points else ''

    if tight_count >= 2 or (tight_count >= 1 and total_active_count >= 4):
        label = 'A级教材'
        score_bonus = 8
    elif total_active_count >= 3:
        label = 'B级教材'
        score_bonus = 4
    elif total_active_count >= 1:
        label = 'C级观察样本'
        score_bonus = 1
    else:
        label = ''
        score_bonus = 0

    summary_text = ''
    if label:
        summary_text = (
            f"{label}：近{review_days}日出现{total_active_count}次，"
            f"tight {tight_count}次 / loose {loose_count}次，最近一次{last_active_date}"
        )

    return {
        'label': label,
        'total_active_count': total_active_count,
        'tight_count': tight_count,
        'loose_count': loose_count,
        'last_active_date': last_active_date,
        'score_bonus': score_bonus,
        'summary_text': summary_text,
    }


def _build_gem_20cm_observation_pool(gem_breathing_candidates=None, target_date=''):
    pool = []
    textbook_rank_map = {'A级教材': 3, 'B级教材': 2, 'C级观察样本': 1}
    for raw in (gem_breathing_candidates or []):
        item = dict(raw or {})
        tier = str(item.get('tier', '') or '').strip()
        base_score = _safe_float(item.get('score', 0))
        strength_bonus = 12 if tier == 'tight' else 6
        note = str(item.get('note', '') or '').strip() or '创业板20cm预启动观察。'
        textbook_profile = _build_gem_breathing_textbook_profile(item, target_date=target_date) if target_date else {
            'label': '',
            'total_active_count': 0,
            'tight_count': 0,
            'loose_count': 0,
            'last_active_date': '',
            'score_bonus': 0,
            'summary_text': '',
        }
        textbook_summary = str(textbook_profile.get('summary_text', '') or '').strip()
        watch_anchor_note = str(item.get('watch_anchor_note', '') or '先看右侧确认和60分钟确认，不直接给执行权').strip()
        if textbook_summary:
            watch_anchor_note = f"{watch_anchor_note}；{textbook_summary}"
        item.update({
            'pattern': '创业板20cm预启动',
            'core_level': f"🫁 20cm预启动观察{' / ' + textbook_profile.get('label', '') if textbook_profile.get('label') else ''}",
            'abnormal_summary': note,
            'abnormal_follow_state': '预启动呼吸感',
            'tmr_forecast': '先看右侧确认和60分钟确认是否成立，确认前只观察不执行',
            'tomorrow_strength': round(base_score + strength_bonus + _safe_float(textbook_profile.get('score_bonus', 0)), 1),
            'watch_source': 'gem_breathing_20cm',
            'close': _safe_float(item.get('close', 0)),
            'volume': _safe_float(item.get('volume', 0)),
            'change_pct': _safe_float(item.get('change_pct', 0)),
            'entry_price': _safe_float(item.get('close', 0)),
            'watch_anchor_note': watch_anchor_note,
            'textbook_label': str(textbook_profile.get('label', '') or '').strip(),
            'textbook_summary': textbook_summary,
            'textbook_profile': textbook_profile,
            'textbook_rank': textbook_rank_map.get(str(textbook_profile.get('label', '') or '').strip(), 0),
        })
        pool.append(item)
    pool.sort(
        key=lambda x: (
            _safe_float(x.get('textbook_rank', 0)),
            _safe_float((x.get('textbook_profile') or {}).get('tight_count', 0)),
            _safe_float((x.get('textbook_profile') or {}).get('total_active_count', 0)),
            _safe_float(x.get('tomorrow_strength', 0)),
        ),
        reverse=True,
    )
    return pool


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
    candidate = candidate or {}
    minute_plan = candidate.get('minute_plan') or {}
    stop_plan = candidate.get('stop_plan') or {}
    confirm_price = _round_or_none(
        minute_plan.get('confirm_price_60m')
        or candidate.get('confirm_price_60m')
    )
    support_price = _round_or_none(
        minute_plan.get('confirm_support_60m')
        or candidate.get('execution_stop')
        or candidate.get('display_anchor_price')
        or candidate.get('effective_stop')
    )
    entry_range = candidate.get('entry_range') or ()
    reset_breakout_price = None
    if isinstance(entry_range, (list, tuple)) and len(entry_range) >= 2:
        reset_breakout_price = _round_or_none(entry_range[1])
    if reset_breakout_price is None:
        reset_breakout_price = _round_or_none(candidate.get('entry_range_high') or confirm_price)
    holding_days_max = int(_safe_float(
        candidate.get('holding_days_max')
        or stop_plan.get('holding_days_max')
        or STRATEGY_HOLDING_DAYS_MAX
    ) or STRATEGY_HOLDING_DAYS_MAX)
    active_window_days = min(max(holding_days_max, 3), 5)
    if confirm_price is not None and support_price is not None:
        upgrade_condition_text = f'首个60分钟站上{confirm_price:.2f}且不破{support_price:.2f}，才评估升级到30%条件试错'
    elif confirm_price is not None:
        upgrade_condition_text = f'首个60分钟站上{confirm_price:.2f}，才评估升级到30%条件试错'
    else:
        upgrade_condition_text = '先完成右侧确认和60分钟确认，才评估升级到30%条件试错'
    return {
        'active': bool(confirm_price or support_price or reset_breakout_price),
        'contract_kind': 'gem_breathing_20cm',
        'active_window_days': active_window_days,
        'right_side_trigger_price': confirm_price,
        'upgrade_condition_text': upgrade_condition_text,
        'void_price': support_price,
        'reset_breakout_price': reset_breakout_price,
    }


def _build_gem_breathing_watch_anchor(gem_candidate=None, target_date='', mainline_name=''):
    gem_candidate = dict(gem_candidate or {})
    code = normalize_stock_code(gem_candidate.get('code', ''))
    close_price = _safe_float(gem_candidate.get('close', 0))
    if not code:
        return {}

    recent_bars = fetch_recent_price_bars(code, target_date, lookback_days=4)
    daily_anchor_bars = fetch_recent_price_bars(
        code, target_date, lookback_days=max(STOP_PRIOR_LOW_TRADING_DAYS + 5, 10)
    )
    tradability_guard = evaluate_live_tradability(
        gem_candidate,
        target_date,
        recent_bars=recent_bars,
    )
    signal = analyze_buy_signal(
        code,
        gem_candidate.get('name', ''),
        close_price,
        _safe_float(gem_candidate.get('volume')),
    ) if (QUANT_SYSTEM_AVAILABLE and close_price > 0 and code) else None
    signal_type = getattr(signal, 'signal_type', '') if signal and signal.is_valid else ''
    entry_seed_price = signal.entry_price if signal and signal.is_valid else close_price

    watch_anchor = build_waiting_stock_plan(
        {
            **gem_candidate,
            'entry_price': entry_seed_price,
            'condition': gem_candidate.get('tmr_forecast') or gem_candidate.get('note') or '先看创业板20cm呼吸感是否升级成右侧确认',
            'tradability_guard': tradability_guard,
            'report_day_is_one_word': tradability_guard.get('report_day_is_one_word', False),
        },
        target_date,
        reason=gem_candidate.get('tmr_forecast') or gem_candidate.get('note') or '先看创业板20cm呼吸感是否升级成右侧确认',
        signal_type=signal_type,
        recent_bars=daily_anchor_bars,
    )
    watch_anchor.update({
        'watch_source': 'gem_breathing_20cm',
        'permission_label': '创业板20cm预启动观察权',
        'permission_reason': '只先进观察池，先看右侧确认和60分钟确认，不直接给执行权',
        'watch_anchor_type': '创业板20cm预启动先看谁',
        'watch_anchor_note': (
            f"{str(gem_candidate.get('note', '') or '创业板20cm预启动观察。').strip()}；"
            '只先进观察池，先看右侧确认和60分钟确认，不满足继续观察'
        ),
        'tradability_guard': tradability_guard,
        'report_day_is_one_word': tradability_guard.get('report_day_is_one_word', False),
        'abnormal_follow_state': gem_candidate.get('abnormal_follow_state', '预启动呼吸感'),
        'breathing_tier': gem_candidate.get('tier', ''),
    })
    if signal and signal.is_valid:
        watch_anchor['signal'] = signal
        watch_anchor['signal_type'] = getattr(signal, 'signal_type', '')
        watch_anchor['position_pct'] = _safe_float(signal.position_pct, 0.0)
        watch_anchor['entry_price'] = signal.entry_price
        watch_anchor['entry_range'] = (signal.entry_price * 0.97, signal.entry_price * 1.03)
    watch_anchor['gem_breathing_contract'] = _build_gem_breathing_contract(watch_anchor)
    gem_contract = watch_anchor.get('gem_breathing_contract', {}) or {}
    upgrade_text = str(gem_contract.get('upgrade_condition_text', '') or '').strip()
    void_price = _round_or_none(gem_contract.get('void_price'))
    reset_breakout_price = _round_or_none(gem_contract.get('reset_breakout_price'))
    note_parts = [str(gem_candidate.get('note', '') or '创业板20cm预启动观察。').strip()]
    textbook_summary = str(gem_candidate.get('textbook_summary', '') or '').strip()
    if textbook_summary:
        note_parts.append(textbook_summary)
    if upgrade_text:
        note_parts.append(upgrade_text)
    if void_price is not None:
        note_parts.append(f'失守{void_price:.2f}作废')
    elif reset_breakout_price is not None:
        note_parts.append(f'失守后至少重新站回{reset_breakout_price:.2f}再评估')
    note_parts.append('确认前只先进观察池，先看右侧确认和60分钟确认，不直接给执行权')
    watch_anchor['watch_anchor_note'] = '；'.join(part for part in note_parts if part)
    return watch_anchor


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
    abnormal_watch_anchor_candidates = abnormal_watch_anchor_candidates or []
    pending_candidates = pending_candidates or []
    observation_candidates = observation_candidates or []
    waiting_stocks = waiting_stocks or []
    gem_observation_stocks = gem_observation_stocks or []

    def _build_gem_anchor():
        if not gem_observation_stocks:
            return None, ''
        gem_watch_seed = dict(gem_observation_stocks[0] or {})
        watch_anchor = _build_gem_breathing_watch_anchor(
            gem_watch_seed,
            target_date=target_date,
            mainline_name=mainline_name,
        )
        watch_anchor_type = watch_anchor.get('watch_anchor_type', '创业板20cm预启动先看谁')
        return watch_anchor, watch_anchor_type

    if trade_gate_open:
        if abnormal_watch_anchor_candidates:
            watch_anchor = abnormal_watch_anchor_candidates[0]
            watch_anchor_type = _derive_pending_candidate_type(watch_anchor, mainline_name=mainline_name)
            watch_anchor['watch_anchor_type'] = watch_anchor_type
            watch_anchor['watch_anchor_note'] = _derive_watch_anchor_note(watch_anchor, mainline_name=mainline_name)
            return watch_anchor, watch_anchor_type
        gem_anchor, gem_anchor_type = _build_gem_anchor()
        if gem_anchor:
            return gem_anchor, gem_anchor_type
        if pending_candidates:
            watch_anchor = pending_candidates[0]
            watch_anchor_type = _derive_pending_candidate_type(watch_anchor, mainline_name=mainline_name)
            watch_anchor['watch_anchor_type'] = watch_anchor_type
            watch_anchor['watch_anchor_note'] = _derive_watch_anchor_note(watch_anchor, mainline_name=mainline_name)
            return watch_anchor, watch_anchor_type
        return None, ''

    if abnormal_watch_anchor_candidates:
        watch_anchor = abnormal_watch_anchor_candidates[0]
        watch_anchor_type = watch_anchor.get('watch_anchor_type', _derive_watch_anchor_type(watch_anchor, mainline_name=mainline_name))
        watch_anchor['watch_anchor_type'] = watch_anchor_type
        watch_anchor['watch_anchor_note'] = _derive_watch_anchor_note(watch_anchor, mainline_name=mainline_name)
        return watch_anchor, watch_anchor_type

    gem_anchor, gem_anchor_type = _build_gem_anchor()
    if gem_anchor:
        return gem_anchor, gem_anchor_type

    if observation_candidates:
        watch_anchor = observation_candidates[0]
        watch_anchor_type = watch_anchor.get('watch_anchor_type', '重点观察谁')
        return watch_anchor, watch_anchor_type

    if waiting_stocks:
        watch_anchor = waiting_stocks[0]
        watch_anchor_type = _derive_watch_anchor_type(watch_anchor, mainline_name=mainline_name) or '继续看谁'
        watch_anchor['watch_anchor_note'] = _derive_watch_anchor_note(watch_anchor, mainline_name=mainline_name)
        return watch_anchor, watch_anchor_type

    return None, ''


def _build_gem_elasticity_context(candidate=None, mainline_name='', mainline_anchor=None):
    candidate = candidate or {}
    mainline_name = str(mainline_name or '').strip()
    sector = str(candidate.get('sector', '') or candidate.get('sector_name', '') or '').strip()
    if not mainline_name or not sector:
        return {'active': False}
    if not sector_name_matches(sector, mainline_name):
        return {'active': False}
    anchor_name = str((mainline_anchor or {}).get('name', '') or '').strip() or mainline_name
    return {
        'active': True,
        'label': '主板强锚对应的创业板弹性标的',
        'anchor_name': anchor_name,
        'reason': f'{anchor_name}仍是主板强锚时，创业板更像这条主线里的白银弹性层。',
    }


def _should_hide_gem_execution_entry_range(candidate=None):
    candidate = candidate or {}
    if str(candidate.get('watch_source', '') or '').strip() != 'gem_breathing_20cm':
        return False
    position_pct = int(_safe_float(candidate.get('position_pct', 0)))
    participation_mode = str(candidate.get('participation_mode', '') or '').strip()
    action_type = str(candidate.get('action_type', '') or '').strip()
    return position_pct <= 0 and participation_mode not in ('conditional_30', 'execute_50') and action_type != 'execute'


def _resolve_candidate_contract_prices(candidate=None, signal=None, expose_execution_entry_range=None):
    candidate = candidate or {}
    minute_plan = candidate.get('minute_plan') or {}
    gem_contract = candidate.get('gem_breathing_contract') or {}
    entry_range = candidate.get('entry_range')
    if not entry_range and signal:
        entry_range = (signal.entry_price, signal.entry_price)

    observe_anchor_price = _round_or_none(
        candidate.get('entry_price')
        or (signal.entry_price if signal else None)
        or (entry_range[0] if isinstance(entry_range, (list, tuple)) and entry_range else None)
    )
    upgrade_trigger_price = _round_or_none(
        gem_contract.get('right_side_trigger_price')
        or minute_plan.get('confirm_price_60m')
    )
    invalidation_price = _round_or_none(
        gem_contract.get('void_price')
        or minute_plan.get('confirm_support_60m')
        or candidate.get('execution_stop')
        or candidate.get('display_anchor_price')
        or candidate.get('effective_stop')
        or candidate.get('stop_loss')
    )
    reset_breakout_price = _round_or_none(
        gem_contract.get('reset_breakout_price')
        or candidate.get('entry_range_high')
        or (entry_range[1] if isinstance(entry_range, (list, tuple)) and len(entry_range) >= 2 else None)
        or minute_plan.get('confirm_price_60m')
    )

    if expose_execution_entry_range is None:
        expose_execution_entry_range = not _should_hide_gem_execution_entry_range(candidate)

    entry_range_low = _round_or_none(entry_range[0]) if expose_execution_entry_range and isinstance(entry_range, (list, tuple)) and len(entry_range) >= 1 else None
    entry_range_high = _round_or_none(entry_range[1]) if expose_execution_entry_range and isinstance(entry_range, (list, tuple)) and len(entry_range) >= 2 else None

    return {
        'entry_range_low': entry_range_low,
        'entry_range_high': entry_range_high,
        'observe_anchor_price': observe_anchor_price,
        'upgrade_trigger_price': upgrade_trigger_price,
        'invalidation_price': invalidation_price,
        'reset_breakout_price': reset_breakout_price,
    }


def _classify_20cm_branch(candidate=None, mainline_name='', confirm_price=None, support_price=None, feedback_ready=False, allow_conditional_30=False, target_date='', mainline_anchor=None):
    candidate = candidate or {}
    if not _is_20cm_stock(candidate):
        return {
            'is_20cm': False,
            'allow_watch_pool': False,
            'allow_conditional_30': False,
            'observe_only': False,
            'direct_ban': False,
            'reason': '',
        }

    follow_state = str(candidate.get('abnormal_follow_state', candidate.get('follow_state', '')) or '').strip()
    sector = str(candidate.get('sector', '') or '').strip()
    textbook_label = str(candidate.get('textbook_label', '') or '').strip()
    textbook_summary = str(candidate.get('textbook_summary', '') or '').strip()
    lianban = int(_safe_float(candidate.get('lianban', candidate.get('连板数', 0)) or 0))
    change_pct = abs(_safe_float(candidate.get('change_pct', candidate.get('涨跌幅', 0.0))))
    clear_boundary = confirm_price is not None and support_price is not None and confirm_price > 0 and support_price > 0
    mainline_match = bool(mainline_name and sector and sector_name_matches(sector, mainline_name))
    right_side_ok = follow_state in ('跌不下去', '缩量消化', '长上影后收复')
    breathing_prep = _build_gem_breathing_prep_context(candidate, target_date=target_date)
    elasticity_context = _build_gem_elasticity_context(candidate, mainline_name=mainline_name, mainline_anchor=mainline_anchor)
    textbook_ready = textbook_label == 'A级教材' and breathing_prep.get('active') and elasticity_context.get('active')
    risky_chase = lianban >= 2 or change_pct >= 15 or follow_state in ('一致加速', '高位加速') or not clear_boundary

    if risky_chase:
        return {
            'is_20cm': True,
            'allow_watch_pool': False,
            'allow_conditional_30': False,
            'observe_only': False,
            'direct_ban': True,
            'reason': '20cm 高波动接力/边界不清样本直接禁做，只保留远离情绪顶点后的后续观察。',
            'breathing_prep': breathing_prep,
            'elasticity_context': elasticity_context,
        }

    allow_watch_pool = mainline_match and clear_boundary and (right_side_ok or breathing_prep.get('active'))
    allow_conditional = allow_watch_pool and allow_conditional_30 and ((right_side_ok and feedback_ready) or (textbook_ready and feedback_ready))
    if allow_conditional:
        if textbook_ready and not right_side_ok:
            reason = f"{textbook_summary or textbook_label}；属于反复验证过的20cm教材样本，当前边界清楚且反馈就绪，可先进入30%条件试错。"
        else:
            reason = '20cm 只作为右侧补充分支；主线、确认链和风险边界都清楚时，只允许30%条件试错。'
    elif breathing_prep.get('active') and elasticity_context.get('active'):
        reason = f"{breathing_prep.get('note') or '创业板20cm呼吸感预启动。'}；{elasticity_context.get('reason', '')}"
    elif breathing_prep.get('active'):
        reason = breathing_prep.get('note') or '创业板20cm呼吸感预启动，只先进观察池，不直接执行。'
    else:
        reason = '20cm 样本可进观察池，但当前只保留观察权，不直接给执行仓位。'

    return {
        'is_20cm': True,
        'allow_watch_pool': allow_watch_pool,
        'allow_conditional_30': allow_conditional,
        'observe_only': allow_watch_pool and not allow_conditional,
        'direct_ban': False,
        'reason': reason,
        'breathing_prep': breathing_prep,
        'elasticity_context': elasticity_context,
    }


def _build_special_probe_verdict(
    abnormal_probe_group=None,
    watch_anchor=None,
    watch_anchor_type='',
    mainline_name='',
    target_date='',
):
    abnormal_probe_group = abnormal_probe_group or {}
    watch_anchor = watch_anchor or {}
    watch_anchor_type = str(watch_anchor_type or '').strip()
    mainline_name = str(mainline_name or '').strip()
    if '执行候选观察锚点' in watch_anchor_type:
        return {
            'code': 'no_probe',
            'label': '特殊探针',
            'summary_text': '',
            'action': '',
            'probe_candidate': {},
            'probe_state': 'no_probe',
            'allows_conditional_30': False,
            'allows_execute_50': False,
        }
    mainline_probe = abnormal_probe_group.get('mainline_abnormal_probe') or {}
    crossline_probe = abnormal_probe_group.get('crossline_abnormal_probe') or {}
    validation_probe = abnormal_probe_group.get('validation_probe') or {}
    fallback_watch_anchor = abnormal_probe_group.get('fallback_watch_anchor') or watch_anchor or {}

    def _probe_contract(probe=None, default_state='probe_flow_unconfirmed'):
        probe = probe or {}
        follow_state = str(probe.get('follow_state', '') or probe.get('abnormal_follow_state', '') or '').strip()
        note_text = str(probe.get('watch_anchor_note', '') or '').strip()
        if follow_state == '已经转弱':
            probe_state = 'probe_deep_fall'
        elif '外溢确认阶段' in note_text or '外溢继续扩大' in note_text or '跨线外溢确认' in watch_anchor_type:
            probe_state = 'probe_flow_confirmed'
        elif follow_state in ('跌不下去', '缩量消化'):
            probe_state = 'probe_resilient_hold' if '主线' in watch_anchor_type and '跨线' not in watch_anchor_type else default_state
        else:
            probe_state = default_state
        allows_conditional_30 = probe_state == 'probe_flow_confirmed'
        allows_execute_50 = probe_state == 'probe_mainline_confirmed'
        return probe_state, allows_conditional_30, allows_execute_50

    if crossline_probe:
        note = str(crossline_probe.get('watch_anchor_note', '') or _derive_watch_anchor_note(crossline_probe, mainline_name)).strip()
        if '不代表主攻线从' in note and '切换' in note:
            prefix, suffix = note.split('不代表主攻线从', 1)
            suffix = suffix.split('切换', 1)[1] if '切换' in suffix else suffix
            note = f"{prefix}不代表主攻线切换{suffix}"
        name = crossline_probe.get('name', '-')
        code = crossline_probe.get('code', '-')
        probe_state, allows_conditional_30, allows_execute_50 = _probe_contract(crossline_probe, default_state='probe_flow_unconfirmed')
        crossline_feedback = _build_candidate_feedback_clock(
            candidate=crossline_probe,
            watch_anchor_type=watch_anchor_type,
            state_machine_snapshot={'leading_line': mainline_name},
            mainline_name=mainline_name,
            target_date=target_date,
        )
        history_days = int(_safe_float((crossline_feedback.get('history_feedback', {}) or {}).get('continuous_days', 0)))
        crossline_upgrade_ready = bool(
            _requires_crossline_second_confirmation(crossline_probe, mainline_name)
            and crossline_feedback.get('ready')
            and crossline_feedback.get('has_confirmation_chain')
            and history_days >= 2
            and probe_state != 'probe_deep_fall'
        )
        if crossline_upgrade_ready:
            return {
                'code': 'crossline_probe_upgrade_ready',
                'label': '跨线可升级探针',
                'summary_text': f"{name}({code}) 虽然仍属跨线对象，但已经先 act right：承接未坏、确认链完整，且连续反馈已出现，只允许升级到30%条件试错，不直接当成主攻线切换。",
                'action': '先按跨线可升级探针对待；若继续 act right，只允许30%条件试错，不直接放到50%执行。',
                'probe_candidate': crossline_probe,
                'probe_state': 'probe_crossline_upgrade_ready',
                'allows_conditional_30': True,
                'allows_execute_50': False,
            }
        return {
            'code': 'crossline_probe_only',
            'label': '跨线特殊探针',
            'summary_text': f"{name}({code}) 只是跨线市场探针，{note or '只观察跨线强弱，不代表主攻线切换'}",
            'action': '只观察跨线强弱和资金外溢，不升级执行权',
            'probe_candidate': crossline_probe,
            'probe_state': probe_state,
            'allows_conditional_30': allows_conditional_30,
            'allows_execute_50': allows_execute_50,
        }

    if mainline_probe:
        name = mainline_probe.get('name', '-')
        code = mainline_probe.get('code', '-')
        follow_state = str(mainline_probe.get('follow_state', '') or '').strip() or '待观察'
        upgrade_probe_context = _build_mainline_upgrade_probe_context(
            mainline_probe,
            mainline_name=mainline_name,
            target_date=target_date,
        )
        if upgrade_probe_context.get('upgrade_ready'):
            return {
                'code': 'mainline_probe_upgrade_ready',
                'label': '主线可升级探针',
                'summary_text': f"{name}({code}) 已被识别成主线可升级探针：承接未坏、确认链完整，且出现连续反馈/修复证据，若次日继续 act right，才允许升级到30%条件试错。",
                'action': '先盯主线可升级探针是否继续证明自己；若次日继续 act right，再考虑30%条件试错，不直接给50%执行。',
                'probe_candidate': mainline_probe,
                'probe_state': upgrade_probe_context.get('probe_state'),
                'allows_conditional_30': bool(upgrade_probe_context.get('allows_conditional_30')),
                'allows_execute_50': False,
            }
        probe_state, allows_conditional_30, allows_execute_50 = _probe_contract(mainline_probe, default_state='probe_resilient_hold')
        return {
            'code': 'mainline_probe_watch',
            'label': '主线特殊探针',
            'summary_text': f"{name}({code}) 是主线特殊探针，当前处于{follow_state}；若它也跌下去，这轮修复继续收，若它抗跌才保留后续升级预期",
            'action': '先盯主线特殊标的能不能跌下去，再决定观察权是否保留',
            'probe_candidate': mainline_probe,
            'probe_state': probe_state,
            'allows_conditional_30': allows_conditional_30,
            'allows_execute_50': allows_execute_50,
        }

    if validation_probe:
        name = validation_probe.get('name', '-')
        code = validation_probe.get('code', '-')
        probe_state, allows_conditional_30, allows_execute_50 = _probe_contract(validation_probe, default_state='probe_resilient_hold')
        return {
            'code': 'validation_probe_watch',
            'label': '承接验证探针',
            'summary_text': f"{name}({code}) 用来验证这轮调整是良性承接还是继续转弱",
            'action': '先看验证探针是否抗跌，再决定是否保留观察权',
            'probe_candidate': validation_probe,
            'probe_state': probe_state,
            'allows_conditional_30': allows_conditional_30,
            'allows_execute_50': allows_execute_50,
        }

    if fallback_watch_anchor:
        name = fallback_watch_anchor.get('name', '-')
        code = fallback_watch_anchor.get('code', '-')
        probe_state, allows_conditional_30, allows_execute_50 = _probe_contract(fallback_watch_anchor, default_state='probe_flow_unconfirmed')
        return {
            'code': 'fallback_probe_watch',
            'label': '特殊探针',
            'summary_text': f"{name}({code}) 先看它是深跌还是抗跌，再决定这轮调整是继续收还是重新攻",
            'action': '先观察这个特殊对象对调整的反馈，不直接升级执行权',
            'probe_candidate': fallback_watch_anchor,
            'probe_state': probe_state,
            'allows_conditional_30': allows_conditional_30,
            'allows_execute_50': allows_execute_50,
        }

    return {
        'code': 'no_probe',
        'label': '特殊探针',
        'summary_text': '当前没有明确特殊探针，只保留普通观察。',
        'action': '先观察市场整体，不提前放松执行权',
        'probe_candidate': {},
        'probe_state': 'no_probe',
        'allows_conditional_30': False,
        'allows_execute_50': False,
    }


def _build_special_probe_focus_text(
    abnormal_probe_group=None,
    watch_anchor=None,
    watch_anchor_type='',
    mainline_name='',
    target_date='',
):
    abnormal_probe_group = abnormal_probe_group or {}
    watch_anchor = watch_anchor or {}
    fallback_watch_anchor = abnormal_probe_group.get('fallback_watch_anchor') or watch_anchor or {}
    special_probe_verdict = _build_special_probe_verdict(
        abnormal_probe_group=abnormal_probe_group,
        watch_anchor=watch_anchor,
        watch_anchor_type=watch_anchor_type,
        mainline_name=mainline_name,
        target_date=target_date,
    )
    if '执行候选观察锚点' in str(watch_anchor_type or ''):
        return ''
    if special_probe_verdict.get('code') == 'crossline_probe_upgrade_ready':
        probe_candidate = special_probe_verdict.get('probe_candidate') or {}
        name = probe_candidate.get('name', '-')
        code = probe_candidate.get('code', '-')
        return f"{name}({code})，跨线可升级探针：已经先 act right，只允许30%条件试错，不直接当成主攻线切换"
    probe_specs = [
        ('mainline_abnormal_probe', '主线异动里先看谁'),
        ('crossline_abnormal_probe', '跨线异动里先看谁'),
        ('validation_probe', '承接验证先看谁'),
    ]
    for probe_key, role_label in probe_specs:
        text = str(_format_abnormal_probe_text(
            abnormal_probe_group.get(probe_key),
            role_label=role_label,
            mainline_name=mainline_name,
            fallback_watch_anchor=fallback_watch_anchor if role_label == '主线异动里先看谁' else None,
        ) or '').strip()
        if text and not text.startswith('暂无'):
            return text

    if fallback_watch_anchor:
        name = fallback_watch_anchor.get('name', '-')
        code = fallback_watch_anchor.get('code', '-')
        note = str(fallback_watch_anchor.get('watch_anchor_note', '') or '').strip()
        action_rule = str(fallback_watch_anchor.get('action_rule', '') or '').strip()
        text = f"{name}({code})，先看它是深跌还是抗跌，再决定这轮调整是继续收还是重新攻"
        if action_rule:
            text += f"；{action_rule}"
        if note:
            text += f"；{note}"
        return text
    return ''


def _build_abnormal_setup_distribution(abnormal_watch_pool):
    abnormal_watch_pool, _ = _split_abnormal_watch_pool(abnormal_watch_pool)
    grouped = {}
    for item in abnormal_watch_pool or []:
        setup_id = item.get('setup_signal_id') or 'unknown'
        entry = grouped.setdefault(setup_id, {
            'id': setup_id,
            'label': item.get('setup_signal_label', setup_id),
            'count': 0,
        })
        entry['count'] += 1
    return sorted(grouped.values(), key=lambda x: (x.get('count', 0), x.get('label', '')), reverse=True)


def _snapshot_candidate_brief(candidate):
    if not candidate:
        return {}

    signal = candidate.get('signal')
    minute_plan = candidate.get('minute_plan') or {}
    stop_plan = candidate.get('stop_plan') or {}
    contract_prices = _resolve_candidate_contract_prices(candidate, signal=signal)
    price_focus = _build_trade_price_focus(minute_plan, stop_plan)

    return {
        'name': candidate.get('name', ''),
        'code': normalize_stock_code(candidate.get('code', '')),
        'sector': candidate.get('sector', ''),
        'permission_label': candidate.get('permission_label', ''),
        'watch_anchor_type': candidate.get('watch_anchor_type', ''),
        'watch_anchor_note': candidate.get('watch_anchor_note', ''),
        'signal_type': candidate.get('signal_type') or (getattr(signal, 'signal_type', '') if signal else ''),
        'setup_signal_id': candidate.get('abnormal_setup_signal_id', candidate.get('setup_signal_id', '')),
        'setup_signal_label': candidate.get('abnormal_setup_signal_label', candidate.get('setup_signal_label', '')),
        'abnormal_follow_state': candidate.get('abnormal_follow_state', candidate.get('follow_state', '')),
        'entry_range_low': contract_prices.get('entry_range_low'),
        'entry_range_high': contract_prices.get('entry_range_high'),
        'observe_anchor_price': contract_prices.get('observe_anchor_price'),
        'upgrade_trigger_price': contract_prices.get('upgrade_trigger_price'),
        'invalidation_price': contract_prices.get('invalidation_price'),
        'reset_breakout_price': contract_prices.get('reset_breakout_price'),
        'confirm_price_60m': _round_or_none(minute_plan.get('confirm_price_60m')),
        'confirm_support_60m': _round_or_none(minute_plan.get('confirm_support_60m')),
        'key_zone_low': price_focus.get('key_zone_low'),
        'key_zone_high': price_focus.get('key_zone_high'),
        'key_zone_display': price_focus.get('key_zone_display'),
        'execution_stop': price_focus.get('execution_stop'),
        'price_note': price_focus.get('note_text', ''),
        'price_confluence_reasons': list(price_focus.get('confluence_reasons', []) or []),
        'effective_stop': _round_or_none((stop_plan or {}).get('effective_stop') or candidate.get('stop_loss')),
        'report_day_is_one_word': bool(candidate.get('report_day_is_one_word')),
        'tomorrow_strength': _round_or_none(candidate.get('tomorrow_strength'), 2),
        'composite_score': _round_or_none(candidate.get('composite_score'), 6),
        'ev_pct': _round_or_none(candidate.get('ev_pct'), 6),
        'decision_stack': dict(candidate.get('decision_stack', {}) or {}),
    }


def _score_environment_snapshot(final_gate, position_level):
    if final_gate and final_gate.get('can_new_entry'):
        score = 85
    elif '二档' in str(position_level or ''):
        score = 45
    elif '一档' in str(position_level or ''):
        score = 15
    else:
        score = 55
    if final_gate and final_gate.get('should_reduce'):
        score = max(score - 15, 0)
    return score


def _score_structure_snapshot(market_zhongshu):
    signal = market_zhongshu.get('signal', {}) if market_zhongshu else {}
    signal_type = str(signal.get('signal_type', '') or '')
    status = str(signal.get('status', '') or '')
    text = f"{signal_type} {status}"
    if any(keyword in text for keyword in ['下跌', '向下', '破位']):
        return 18
    if any(keyword in text for keyword in ['突破', '向上', '上涨']):
        return 78
    return 48


def _score_mainline_snapshot(mainline_name, mainline_score, sector_trend_snapshot):
    if not mainline_name:
        return 20
    matched_sector = None
    for item in sector_trend_snapshot or []:
        if sector_name_matches(item.get('sector', ''), mainline_name):
            matched_sector = item
            break

    base_score = _safe_float(mainline_score, 0.0)
    if matched_sector:
        density_score = (
            _safe_float(matched_sector.get('trend_count')) * 5
            + _safe_float(matched_sector.get('strong_count')) * 4
            + _safe_float(matched_sector.get('limit_up_count')) * 3
        )
        base_score = max(base_score, 35 + density_score)
    elif base_score <= 0:
        base_score = 35
    return int(_clamp(base_score, 0, 100))


def _score_memory_snapshot(leader_memory_bank, tracking_memory_status):
    validated_count = len((tracking_memory_status or {}).get('today_validated_items', []) or [])
    tentative_count = len((tracking_memory_status or {}).get('today_tentative_items', []) or [])
    leader_count = len(leader_memory_bank or [])
    return int(_clamp(leader_count * 8 + validated_count * 14 + tentative_count * 4, 0, 100))


def _score_abnormal_snapshot(abnormal_watch_pool, selected_candidate):
    abnormal_watch_pool, _ = _split_abnormal_watch_pool(abnormal_watch_pool)
    selected_state = ''
    if selected_candidate:
        selected_state = str(
            selected_candidate.get('abnormal_follow_state', selected_candidate.get('follow_state', '')) or ''
        ).strip()
    resilient_count = len([
        item for item in (abnormal_watch_pool or [])
        if item.get('follow_state') in ('跌不下去', '缩量消化')
    ])
    base_score = {
        '跌不下去': 85,
        '缩量消化': 65,
        '新异动待观察': 38,
        '已经转弱': 10,
    }.get(selected_state, 30)
    return int(_clamp(base_score + resilient_count * 4, 0, 100))


def _normalize_flow_to_yi(value):
    value = _safe_float(value, 0.0)
    if abs(value) >= 1000:
        return value / 10000.0
    return value


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
    final_gate = final_gate or {}
    state_code = str(state_code or '').strip()
    leading_line = str(leading_line or '').strip()
    transition_signal = str(transition_signal or '').strip()
    can_new_entry = bool(final_gate.get('can_new_entry'))
    should_reduce = bool(final_gate.get('should_reduce'))
    operation_state = str(final_gate.get('operation_state', '') or '').strip()

    if trend_density >= 3 and resilient_count >= 2 and zt_count <= 25:
        driver_type = '趋势抱团驱动'
    elif leading_line and trend_density >= 2 and resilient_count >= 1:
        driver_type = '逻辑催化驱动'
    elif zt_count >= 30:
        driver_type = '情绪驱动'
    else:
        driver_type = '混合驱动'

    if state_code == 'contract':
        pulse_stage = '退潮'
    elif state_code == 'expand':
        pulse_stage = '加速' if (zt_count >= 40 or trend_density >= 3) else '启动'
    elif state_code == 'migrate':
        pulse_stage = '钝化' if transition_signal == 'downgrade_risk' else '高位分歧'
    elif state_code == 'probe':
        pulse_stage = '分歧承接' if resilient_count >= 2 else '启动'
    else:
        pulse_stage = '启动'

    if resilient_count >= 2 and failed_count == 0:
        acceptance_quality = '强承接'
    elif resilient_count >= 1 and failed_count <= 1:
        acceptance_quality = '分歧承接'
    elif failed_count >= max(2, resilient_count):
        acceptance_quality = '承接转弱'
    else:
        acceptance_quality = '承接一般'

    if state_code == 'contract' or transition_signal == 'downgrade_risk' or dt_count >= 8:
        passivation_risk = '高'
    elif state_code in {'migrate', 'probe'} or failed_count > 0:
        passivation_risk = '中'
    else:
        passivation_risk = '低'

    if not can_new_entry:
        if state_code == 'migrate' and transition_signal == 'upgrade_ready':
            execution_bias = 'prep_only'
            pulse_action_bias = '只保留条件执行预备态'
            pulse_action_reason = (
                f"{leading_line or '主线'}优势开始拉开，但环境闸门仍未正式放行；"
                "只能保留条件执行预备态，等待次日60分钟确认。"
            )
        elif operation_state == '撤退态':
            execution_bias = 'avoid'
            pulse_action_bias = '禁止参与'
            pulse_action_reason = '环境已转撤退，先退出，等下一轮新脉冲。'
        elif should_reduce or state_code == 'contract':
            execution_bias = 'reduce_only'
            pulse_action_bias = '只减不加'
            pulse_action_reason = '环境未开且主线偏弱，当前只允许处理旧仓，不再给新增执行权。'
        else:
            execution_bias = 'watch_only'
            pulse_action_bias = '只观察不出手'
            pulse_action_reason = '环境尚未正式放行，研究与观察优先于执行。'
    else:
        if pulse_stage == '退潮':
            execution_bias = 'avoid'
            pulse_action_bias = '禁止参与'
            pulse_action_reason = '主线脉冲已经进入退潮段，继续参与性价比极差。'
        elif pulse_stage == '钝化':
            execution_bias = 'watch_only'
            pulse_action_bias = '只减不加'
            pulse_action_reason = '主线脉冲已经钝化，逻辑未必错，但这段不再适合追。'
        elif pulse_stage in {'高位分歧', '分歧承接'}:
            execution_bias = 'divergence_only'
            pulse_action_bias = '只做分歧承接'
            pulse_action_reason = '当前只能等主线分歧承接后的确认，不做一致加速追价。'
        else:
            execution_bias = 'allow_execute'
            pulse_action_bias = '允许做启动/强化段'
            pulse_action_reason = '主线仍处于可参与的启动或强化段，可以继续围绕最强对象做减法。'

    return {
        'driver_type': driver_type,
        'pulse_stage': pulse_stage,
        'acceptance_quality': acceptance_quality,
        'passivation_risk': passivation_risk,
        'execution_bias': execution_bias,
        'pulse_action_bias': pulse_action_bias,
        'pulse_action_reason': pulse_action_reason,
    }


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
    main_sectors_info = main_sectors_info or []
    secondary_sectors_info = secondary_sectors_info or []
    sector_trend_snapshot = sector_trend_snapshot or []
    abnormal_watch_pool, degraded_abnormal_watch_pool = _split_abnormal_watch_pool(abnormal_watch_pool)

    indices = data.get('indices', {}) or {}
    sh_index = indices.get('上证指数', {}) or {}
    breadth_snapshot = _extract_market_breadth_snapshot(data)
    up_count = int(_safe_float(breadth_snapshot.get('up_count', 0)))
    down_count = int(_safe_float(breadth_snapshot.get('down_count', 0)))
    rise_fall_ratio = breadth_snapshot.get('rise_fall_ratio')
    breadth_available = bool(breadth_snapshot.get('breadth_available'))
    zt_count = len(data.get('zt_pool', []) or [])
    dt_count = len(data.get('dt_pool', []) or [])
    turnover = _safe_float(data.get('total_turnover', 0.0))
    sh_change = _safe_float(sh_index.get('涨跌幅', sh_index.get('change_pct', 0.0)))
    quadrant_data = data.get('sector_quadrant') or {}
    hs_total = 0
    high_strong_sector_text = '暂无'
    if quadrant_data and quadrant_data.get('high_strong_analysis'):
        hs_total = int(_safe_float((quadrant_data.get('high_strong_analysis') or {}).get('total', 0)))
        high_strong_sector_text = f"{hs_total}个"

    mainline_name = exit_analysis.get('sector_name', '') if exit_analysis else ''
    mainline_candidates = [item.get('name', '') for item in main_sectors_info if item.get('name')]
    secondary_candidates = [item.get('name', '') for item in secondary_sectors_info if item.get('name')]
    leading_line = mainline_name or (mainline_candidates[0] if mainline_candidates else '')

    resilient_count = len([
        item for item in abnormal_watch_pool
        if item.get('follow_state') in ('跌不下去', '缩量消化')
    ])
    failed_count = len([
        item for item in abnormal_watch_pool
        if item.get('follow_state') == '已经转弱'
    ])

    densest_sector = (sector_trend_snapshot or [None])[0] or {}
    densest_sector_name = densest_sector.get('sector', '')
    trend_density = int(_safe_float(densest_sector.get('trend_count', 0)))

    if (
        final_gate.get('can_new_entry')
        and zt_count >= 30
        and breadth_available
        and rise_fall_ratio is not None
        and rise_fall_ratio >= 1.2
        and hs_total >= 15
        and leading_line
    ):
        energy_state = '扩张聚焦'
        state_code = 'expand'
        flow_direction = f"能量继续向{leading_line}集中"
        state_reason = "涨停、涨跌比和有势板块数量同步走强，主线具备继续承接能力。"
        reflection_focus = "只盯主线内异常后跌不下去的对象，等60分钟确认，不做支线分流。"
        transition_signal = ''
        transition_reason = ''
        transition_action = ''
    elif (
        dt_count >= 15
        or (breadth_available and rise_fall_ratio is not None and rise_fall_ratio < 0.8)
        or position_level == "一档（空仓档）"
        or final_gate.get('operation_state') == '撤退态'
    ):
        energy_state = '收缩防守'
        state_code = 'contract'
        flow_direction = "风险释放优先，先等能量重新回流"
        state_reason = "跌停、涨跌比或仓位限制已经进入收缩区，市场先谈防守，不谈进攻。"
        reflection_focus = "先观察恐慌是否结束，再看哪条线最先恢复承接；当前不放执行权。"
        transition_signal = ''
        transition_reason = ''
        transition_action = ''
    elif leading_line and secondary_candidates:
        energy_state = '迁移竞争'
        state_code = 'migrate'
        flow_direction = f"能量在{leading_line}与{secondary_candidates[0]}之间做选择"
        state_reason = "市场并非全面扩张，而是在主线与竞争线之间重排权重。"
        reflection_focus = f"先看能量最终是否继续回流{leading_line}，胜负未定前只给观察权。"
        secondary_sector_name = secondary_candidates[0] if secondary_candidates else ''
        secondary_trend_item = {}
        for item in sector_trend_snapshot or []:
            if sector_name_matches(item.get('sector', ''), secondary_sector_name):
                secondary_trend_item = item
                break
        secondary_trend_count = int(_safe_float(secondary_trend_item.get('trend_count', 0)))
        upgrade_ready = (
            trend_density >= max(2, secondary_trend_count + 1)
            and resilient_count >= 2
            and failed_count == 0
            and breadth_available
            and rise_fall_ratio is not None
            and rise_fall_ratio >= 1.2
            and dt_count <= 6
        )
        downgrade_risk = (
            failed_count >= max(2, resilient_count)
            or dt_count >= 8
            or (breadth_available and rise_fall_ratio is not None and rise_fall_ratio < 1.0)
            or (secondary_trend_count > trend_density and secondary_trend_count >= 2)
        )
        if upgrade_ready:
            transition_signal = 'upgrade_ready'
            transition_reason = '主攻线优势已经拉开，但环境层仍未正式放行；更适合进入条件执行预备态，而不是继续无差别仅观察。'
            transition_action = '默认不开新仓，只为主攻线内最强对象保留条件执行预备态。'
        elif downgrade_risk:
            transition_signal = 'downgrade_risk'
            transition_reason = '竞争并没有结束，且主攻线承接出现恶化迹象；若继续走坏，应从迁移竞争降回收缩防守。'
            transition_action = '先收缩观察名单，优先确认是否需要重新回到防守。'
        else:
            transition_signal = 'hold_watch'
            transition_reason = '主攻线虽在领先，但胜负还没拉开到足以升级；继续保持高质量观察，不提前放松。'
            transition_action = '先看主攻线与竞争线谁继续胜出，维持观察层减法。'
    else:
        energy_state = '试探修复'
        state_code = 'probe'
        flow_direction = f"局部试探{leading_line}" if leading_line else "局部试探，尚未形成统一方向"
        state_reason = "局部异常和热点开始出现，但还没有形成足够稳定的全面扩张。"
        reflection_focus = "重点看异常信号是否继续跌不下去，若没有承接，修复就只是噪音。"
        transition_signal = ''
        transition_reason = ''
        transition_action = ''

    observation_summary = (
        f"上证{sh_change:+.2f}% / 涨停{zt_count} / 跌停{dt_count} / "
        f"涨跌比{breadth_snapshot.get('rise_fall_ratio_text', '暂无')} / 有势板块{high_strong_sector_text}"
    )
    if densest_sector_name:
        flow_direction = f"{flow_direction}；趋势密度最强的是{densest_sector_name}"

    pulse_snapshot = _derive_mainline_pulse_snapshot(
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

    return {
        'state_code': state_code,
        'energy_state': energy_state,
        'flow_direction': flow_direction,
        'state_reason': state_reason,
        'reflection_focus': reflection_focus,
        'observation_summary': observation_summary,
        'leading_line': leading_line,
        'mainline_candidates': mainline_candidates[:3],
        'secondary_candidates': secondary_candidates[:3],
        'zt_count': zt_count,
        'dt_count': dt_count,
        'up_count': up_count,
        'down_count': down_count,
        'breadth_available': breadth_available,
        'rise_fall_ratio': round(rise_fall_ratio, 4) if rise_fall_ratio is not None else None,
        'rise_fall_ratio_text': breadth_snapshot.get('rise_fall_ratio_text', '暂无'),
        'turnover': round(turnover, 2),
        'benchmark_change_pct': _round_or_none(sh_change, 4),
        'high_strong_sector_count': hs_total,
        'high_strong_sector_text': high_strong_sector_text,
        'resilient_abnormal_count': resilient_count,
        'failed_abnormal_count': failed_count,
        'degraded_abnormal_count': len(degraded_abnormal_watch_pool),
        'densest_sector': densest_sector_name,
        'densest_sector_trend_count': trend_density,
        'transition_signal': transition_signal,
        'transition_reason': transition_reason,
        'transition_action': transition_action,
        'driver_type': pulse_snapshot.get('driver_type', ''),
        'pulse_stage': pulse_snapshot.get('pulse_stage', ''),
        'acceptance_quality': pulse_snapshot.get('acceptance_quality', ''),
        'passivation_risk': pulse_snapshot.get('passivation_risk', ''),
        'execution_bias': pulse_snapshot.get('execution_bias', ''),
        'pulse_action_bias': pulse_snapshot.get('pulse_action_bias', ''),
        'pulse_action_reason': pulse_snapshot.get('pulse_action_reason', ''),
        'decision_action': final_gate.get('final_action', '') if final_gate else '',
        'operation_state': final_gate.get('operation_state', '') if final_gate else '',
    }


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
    main_sectors_info = main_sectors_info or []
    secondary_sectors_info = secondary_sectors_info or []
    sector_trend_snapshot = sector_trend_snapshot or []
    risk_sectors = risk_sectors or []

    trend_map = {}
    for item in sector_trend_snapshot:
        sector = item.get('sector', '')
        if sector:
            trend_map[sector] = item

    rows = []
    used_names = set()

    def resolve_trend_item(sector_name):
        for key, item in trend_map.items():
            if sector_name_matches(key, sector_name):
                return item
        return {}

    def append_sector(item, role, default_action):
        sector_name = item.get('name', item.get('sector', '')) if isinstance(item, dict) else str(item or '')
        if not sector_name or sector_name in used_names:
            return
        used_names.add(sector_name)
        trend_item = resolve_trend_item(sector_name)
        flow_yi = _normalize_flow_to_yi(
            item.get('inflow', item.get('fund_flow', item.get('zljlr', item.get('net_inflow_yi', 0.0))))
            if isinstance(item, dict) else 0.0
        )
        change_pct = _safe_float(
            item.get('change_pct', item.get('zdf', item.get('涨跌幅', 0.0)))
            if isinstance(item, dict) else 0.0,
            0.0,
        )
        trend_count = int(_safe_float(trend_item.get('trend_count', 0)))
        strong_count = int(_safe_float(trend_item.get('strong_count', 0)))
        limit_up_count = int(
            _safe_float(
                trend_item.get(
                    'limit_up_count',
                    item.get('limit_up_count', item.get('zt_count', 0)) if isinstance(item, dict) else 0,
                )
            )
        )

        evidence_parts = []
        if flow_yi:
            evidence_parts.append(f"资金{flow_yi:+.1f}亿")
        if change_pct:
            evidence_parts.append(f"涨幅{change_pct:+.2f}%")
        if trend_count:
            evidence_parts.append(f"趋势{trend_count}只")
        if strong_count:
            evidence_parts.append(f"强势{strong_count}只")
        if limit_up_count:
            evidence_parts.append(f"涨停{limit_up_count}只")
        evidence_text = " / ".join(evidence_parts) if evidence_parts else "暂无足够结构证据"

        if role == '主攻线':
            judgement = "当前最值得粘住的方向"
        elif role == '竞争线':
            judgement = "仍在争夺主线地位"
        elif role == '次强线':
            judgement = "有承接，但还不是唯一中心"
        else:
            judgement = "能量外流，优先回避"

        rows.append({
            'role': role,
            'sector': sector_name,
            'evidence': evidence_text,
            'judgement': judgement,
            'action': default_action,
        })

    if main_sectors_info:
        append_sector(main_sectors_info[0], '主攻线', '只在这条线里找执行权')
    if len(main_sectors_info) >= 2:
        append_sector(main_sectors_info[1], '次强线', '有共振才看，不抢主攻线风头')
    if secondary_sectors_info:
        append_sector(secondary_sectors_info[0], '竞争线', '先观察胜负，不急着给执行权')
    if risk_sectors:
        append_sector({'name': risk_sectors[0]}, '回避线', '只做风险观察，不做出手方向')

    return rows


def _build_abnormal_projection_summary(abnormal_watch_pool=None):
    abnormal_watch_pool, degraded_abnormal_watch_pool = _split_abnormal_watch_pool(abnormal_watch_pool)
    if not abnormal_watch_pool:
        return {
            'projection_label': '异常稀薄',
            'projection_reason': '今天还没有形成足够密集的异常投影，暂时看不到更高维的明确迁移方向。',
            'action': '先看主线是否继续集中，再等新的异常信号出现。',
            'resilient_count': 0,
            'failed_count': 0,
            'setup_breakdown': [],
            'degraded_count': len(degraded_abnormal_watch_pool),
        }

    resilient_count = len([
        item for item in abnormal_watch_pool
        if item.get('follow_state') in ('跌不下去', '缩量消化')
    ])
    failed_count = len([
        item for item in abnormal_watch_pool
        if item.get('follow_state') == '已经转弱'
    ])
    setup_counter = {}
    for item in abnormal_watch_pool:
        setup_label = item.get('setup_signal_label', item.get('abnormal_type', '未分类')) or '未分类'
        setup_counter[setup_label] = setup_counter.get(setup_label, 0) + 1
    setup_breakdown = sorted(setup_counter.items(), key=lambda x: (-x[1], x[0]))

    if resilient_count >= 2 and failed_count == 0:
        projection_label = '异常承接强化'
        projection_reason = '多个异常信号在后续没有继续塌陷，说明高维主线状态仍在强化。'
        action = '优先盯“跌不下去/缩量消化”的对象，再等60分钟确认。'
    elif failed_count >= max(2, resilient_count + 1):
        projection_label = '异常失败转弱'
        projection_reason = '异常信号大面积转弱，说明高维状态更像衰减或切换，而不是继续强化。'
        action = '降权这些异常股，防守优先，不因为漂亮K线强行出手。'
    else:
        projection_label = '异常分化观察'
        projection_reason = '异常有出现，但承接和失败并存，说明高维状态还在选择方向。'
        action = '继续观察，不放松执行权；等更清晰的承接胜出。'

    return {
        'projection_label': projection_label,
        'projection_reason': projection_reason,
        'action': action,
        'resilient_count': resilient_count,
        'failed_count': failed_count,
        'setup_breakdown': setup_breakdown[:5],
        'degraded_count': len(degraded_abnormal_watch_pool),
    }


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
    main_sectors_info = main_sectors_info or []
    secondary_sectors_info = secondary_sectors_info or []
    sector_trend_snapshot = sector_trend_snapshot or []
    abnormal_watch_pool, degraded_abnormal_watch_pool = _split_abnormal_watch_pool(abnormal_watch_pool)
    leader_memory_bank = leader_memory_bank or []
    tracking_memory_status = tracking_memory_status or {}
    mainline_competition_snapshot = mainline_competition_snapshot or []

    indices = data.get('indices', {}) or {}
    sh_index = indices.get('上证指数', {}) or {}
    breadth_snapshot = _extract_market_breadth_snapshot(data)
    up_count = int(_safe_float(breadth_snapshot.get('up_count', 0)))
    down_count = int(_safe_float(breadth_snapshot.get('down_count', 0)))
    rise_fall_ratio = breadth_snapshot.get('rise_fall_ratio')
    zt_count = len(data.get('zt_pool', []) or [])
    dt_count = len(data.get('dt_pool', []) or [])
    turnover = _safe_float(data.get('total_turnover', 0.0))

    densest_sector = (sector_trend_snapshot or [None])[0] or {}
    resilient_count = len([
        item for item in abnormal_watch_pool
        if item.get('follow_state') in ('跌不下去', '缩量消化')
    ])
    failed_count = len([
        item for item in abnormal_watch_pool
        if item.get('follow_state') == '已经转弱'
    ])

    return {
        'benchmark_change_pct': _round_or_none(sh_index.get('涨跌幅', sh_index.get('change_pct', 0.0)), 4),
        'zt_count': zt_count,
        'dt_count': dt_count,
        'up_count': up_count,
        'down_count': down_count,
        'breadth_available': bool(breadth_snapshot.get('breadth_available')),
        'rise_fall_ratio': round(rise_fall_ratio, 4) if rise_fall_ratio is not None else None,
        'rise_fall_ratio_text': breadth_snapshot.get('rise_fall_ratio_text', '暂无'),
        'turnover': round(turnover, 2),
        'main_sectors_info': main_sectors_info[:5],
        'secondary_sectors_info': secondary_sectors_info[:5],
        'mainline_candidates': [item.get('name', '') for item in main_sectors_info if item.get('name')][:3],
        'secondary_candidates': [item.get('name', '') for item in secondary_sectors_info if item.get('name')][:3],
        'sector_trend_snapshot': sector_trend_snapshot[:5],
        'abnormal_watch_pool': abnormal_watch_pool[:5],
        'degraded_abnormal_watch_pool': degraded_abnormal_watch_pool[:3],
        'leader_memory_bank': leader_memory_bank[:5],
        'tracking_memory_status': tracking_memory_status,
        'mainline_competition_snapshot': mainline_competition_snapshot[:5],
        'competition_focus': (mainline_competition_snapshot or [None])[0] or {},
        'densest_sector': densest_sector.get('sector', ''),
        'densest_sector_trend_count': int(_safe_float(densest_sector.get('trend_count', 0))),
        'resilient_abnormal_count': resilient_count,
        'failed_abnormal_count': failed_count,
        'degraded_abnormal_count': len(degraded_abnormal_watch_pool),
        'leader_memory_count': len(leader_memory_bank or []),
        'trusted_tracking_count': len(tracking_memory_status.get('today_validated_items', []) or []),
        'tentative_tracking_count': len(tracking_memory_status.get('today_tentative_items', []) or []),
    }


def _build_follow_verdict(final_gate, position_level, state_machine_snapshot, special_probe_verdict=None):
    final_gate = final_gate or {}
    state_machine_snapshot = state_machine_snapshot or {}
    special_probe_verdict = special_probe_verdict or {}
    energy_state = state_machine_snapshot.get('energy_state', '未知状态')
    state_code = state_machine_snapshot.get('state_code', '')
    pulse_stage = str(state_machine_snapshot.get('pulse_stage', '') or '').strip()
    execution_bias = str(state_machine_snapshot.get('execution_bias', '') or '').strip()
    pulse_action_reason = str(state_machine_snapshot.get('pulse_action_reason', '') or '').strip()
    leading_line = str(state_machine_snapshot.get('leading_line', '') or '').strip()
    special_probe_action = str(special_probe_verdict.get('action', '') or '').strip()
    special_probe_summary = str(special_probe_verdict.get('summary_text', '') or '').strip()

    if not final_gate.get('can_new_entry'):
        if execution_bias == 'prep_only' or (
            state_code == 'migrate' and state_machine_snapshot.get('transition_signal') == 'upgrade_ready'
        ):
            return {
                'code': 'bridge_prep',
                'label': '🟡 条件执行预备态',
                'reason': pulse_action_reason or state_machine_snapshot.get('transition_reason') or f"当前处于{energy_state}，但主攻线优势已经开始拉开。",
                'action': '先不开新仓，只为最强对象保留条件执行预备态；若次日完成60分钟确认，再升级唯一执行候选',
            }
        if position_level == "一档（空仓档）" or final_gate.get('operation_state') == '撤退态':
            return {
                'code': 'avoid',
                'label': '🚫 暂不跟随',
                'reason': f"当前处于{energy_state}，新增执行权已经关闭，先研究市场，不做新增参与。",
                'action': '空仓观察，禁止新开仓',
            }
        if final_gate.get('should_reduce') or execution_bias == 'reduce_only':
            action_text = '若你有旧仓先去弱留强，禁止新开仓'
            if special_probe_action:
                action_text = f"{special_probe_action}；{action_text}"
            return {
                'code': 'reduce_only',
                'label': '🟠 只处理旧仓',
                'reason': pulse_action_reason or f"当前处于{energy_state}，系统只保留旧仓处理权，不给新增执行权。",
                'action': action_text,
            }
        action_text = '先看环境；若你有持仓，只处理持仓，禁止新开仓'
        if special_probe_action:
            action_text = f"{special_probe_action}；{action_text}"
        return {
            'code': 'research_only',
            'label': '🟡 只研究不跟随',
            'reason': pulse_action_reason or f"当前处于{energy_state}，可以继续研究和跟踪，但还不到新增执行的时候。",
            'action': action_text,
        }

    if execution_bias == 'avoid':
        reason_text = pulse_action_reason or f"{leading_line or '主线'}已经进入{pulse_stage or '退潮'}，继续参与性价比很差。"
        if special_probe_summary:
            reason_text = f"{reason_text}；{special_probe_summary}"
        action_text = '不参与新脉冲，先等下一轮真正的新启动'
        if special_probe_action:
            action_text = f"{special_probe_action}；{action_text}"
        return {
            'code': 'avoid',
            'label': '🚫 暂不跟随',
            'reason': reason_text,
            'action': action_text,
        }
    if execution_bias == 'watch_only':
        reason_text = pulse_action_reason or f"{leading_line or '主线'}脉冲已进入{pulse_stage or '钝化'}，逻辑未必错，但再追更像接最后一棒。"
        if special_probe_summary:
            reason_text = f"{reason_text}；{special_probe_summary}"
        action_text = '只处理旧仓或等待下一次新脉冲，不追新的一致加速'
        if special_probe_action:
            action_text = f"{special_probe_action}；{action_text}"
        return {
            'code': 'no_chase',
            'label': '🟠 只减不加',
            'reason': reason_text,
            'action': action_text,
        }
    if execution_bias == 'divergence_only':
        return {
            'code': 'pullback_only',
            'label': '🟡 只做分歧承接',
            'reason': pulse_action_reason or f"{leading_line or '主线'}仍在，但当前处于{pulse_stage or '高位分歧'}，只能等分歧承接，不能追一致加速。",
            'action': '只等主线分歧承接后的60分钟确认，不追一致加速',
        }

    if state_code == 'expand':
        return {
            'code': 'follow',
            'label': '🟢 跟随主线',
            'reason': '热点、趋势密度和异常承接正在同向共振，可以跟，但只能跟最强方向。',
            'action': '只在主线和异常承接对象里等60分钟确认后再买',
        }
    if state_code == 'migrate':
        return {
            'code': 'single_line_follow',
            'label': '🟡 只跟唯一胜出方向',
            'reason': '热点和趋势还在重排，先研究胜负，不能同时押主线和竞争线。',
            'action': '先看主线与竞争线谁胜出，60分钟确认前不分散出手',
        }
    if state_code == 'probe':
        return {
            'code': 'conditional_follow',
            'label': '🟡 条件跟随',
            'reason': '市场还在试探修复，只有异常继续跌不下去，才允许从研究切到跟随。',
            'action': '轻跟随也必须等60分钟确认，不追一致高潮',
        }
    return {
        'code': 'observe',
        'label': '⚠️ 先看环境',
        'reason': f"当前处于{energy_state}，先确认市场没有继续恶化，再谈跟随。",
        'action': '前30分钟只看环境，60分钟后再定执行',
    }


def _build_dialectical_decision_snapshot(
    observation=None,
    style_switch=None,
    state_machine=None,
    follow_verdict=None,
    final_gate=None,
):
    observation = observation or {}
    style_switch = style_switch or {}
    state_machine = state_machine or {}
    follow_verdict = follow_verdict or {}
    final_gate = final_gate or {}

    benchmark_change = _safe_float(observation.get('benchmark_change_pct', 0.0), 0.0)
    zt_count = int(_safe_float(observation.get('zt_count', 0)))
    dt_count = int(_safe_float(observation.get('dt_count', 0)))
    rise_fall_ratio = observation.get('rise_fall_ratio')
    trend_count = int(_safe_float(observation.get('densest_sector_trend_count', 0)))
    resilient_count = int(_safe_float(observation.get('resilient_abnormal_count', 0)))
    failed_count = int(_safe_float(observation.get('failed_abnormal_count', 0)))
    densest_sector = str(observation.get('densest_sector', '') or '').strip()
    follow_code = str(follow_verdict.get('code', '') or '').strip()
    state_code = str(state_machine.get('state_code', '') or '').strip()
    can_new_entry = bool(final_gate.get('can_new_entry'))
    operation_state = str(final_gate.get('operation_state', '') or '').strip()

    profit_effect_strong = any([
        trend_count >= 2,
        resilient_count >= 2,
        zt_count >= 20,
        follow_code in {'follow', 'single_line_follow', 'conditional_follow'},
        can_new_entry,
    ])

    if state_code == 'expand':
        stage_label = '扩张确认'
        stage_reason = '热点、趋势密度和异常承接已经同向共振，市场不再只是局部修复。'
        stage_action = '可以顺着最强方向做减法，但真正出手仍要等60分钟确认。'
    elif state_code == 'migrate':
        stage_label = '分歧迁移'
        stage_reason = '市场不是全面转弱，而是在主攻线和竞争线之间重新分配权重。'
        stage_action = '先看谁胜出，不同时押两边。'
    elif state_code == 'probe':
        if can_new_entry or operation_state == '进攻态' or zt_count >= 25 or trend_count >= 3 or resilient_count >= 2:
            stage_label = '负重前行'
            stage_reason = '市场开始修复，但指数、广度和主线承接还没全面顺滑，先按修复初期处理。'
            stage_action = '只做顺势跟随，不把试探修复误判成全面主升。'
        else:
            stage_label = '试探修复'
            stage_reason = '局部有修复迹象，但证据还不够密，更多是研究价值，不是全面执行价值。'
            stage_action = '先研究，再等主线和异常承接继续补证据。'
    else:
        stage_label = '收缩防守'
        stage_reason = '风险释放仍优先，市场还没回到可以放大试错的状态。'
        stage_action = '先防守，不给新增执行权。'

    if benchmark_change <= -0.1 and profit_effect_strong:
        index_profit_relation = '指数承压，但赚钱效应还在主线里'
        index_profit_reason = (
            f"上证{benchmark_change:+.2f}%时，热点没有一起塌；真正该盯的是{densest_sector or '当前最强方向'}内部承接有没有继续。"
        )
        index_profit_action = '别被指数单独带偏，优先看主线内部承接是否延续。'
    elif benchmark_change >= 0.2 and profit_effect_strong:
        index_profit_relation = '指数和赚钱效应同步修复'
        index_profit_reason = '指数、热点聚焦和异常承接在同向改善，这种环境更适合顺势跟随。'
        index_profit_action = '可以沿着最强方向做减法，但依旧只做最强对象。'
    elif benchmark_change >= 0.2 and not profit_effect_strong:
        index_profit_relation = '指数回暖了，但赚钱效应还没跟上'
        index_profit_reason = '指数变好看，不代表主线已经清晰，更不代表随便买都能赚钱。'
        index_profit_action = '先看热点聚焦和趋势密度，不因指数变红就提前出手。'
    else:
        index_profit_relation = '指数和赚钱效应都偏弱'
        index_profit_reason = '指数没有给出正反馈，主线承接也还不够集中。'
        index_profit_action = '先观察，不把局部反抽当成可执行机会。'

    if densest_sector and trend_count >= 2:
        focus_label = f'赚钱效应继续向{densest_sector}聚集'
        focus_reason = f"{densest_sector}当前有{trend_count}只活跃趋势股，异常承接{resilient_count}强/{failed_count}弱。"
        focus_action = f"只在{densest_sector}和相关异常承接对象里继续做减法。"
    elif densest_sector:
        focus_label = f'{densest_sector}暂时领先，但聚集还不够'
        focus_reason = f"{densest_sector}虽然领先，但趋势密度只有{trend_count}只，更多还是观察优势，不是绝对优势。"
        focus_action = '先把它当研究重点，不急着授予普遍执行权。'
    else:
        focus_label = '赚钱效应还没真正聚集'
        focus_reason = '热点仍偏散，主线没有形成足够稳定的中心。'
        focus_action = '先观察胜出方向，不在分散题材里乱试错。'

    if profit_effect_strong:
        candidate_focus = '优先率先转强、分歧后仍有承接、异常后跌不下去的对象'
        candidate_action = '长期阴跌后的孤立首板默认只观察；只有后续继续强化，才考虑升级。'
    else:
        candidate_focus = '先分清谁只是反抽，谁真正率先转强'
        candidate_action = '观察池优先保留率先转强和异常承接对象，不给低位幻想执行权。'

    falsification_conditions = []
    if densest_sector:
        falsification_conditions.append(f"{densest_sector}的趋势密度和承接同时走弱，热点重新变散。")
    else:
        falsification_conditions.append('热点没有继续聚焦，赚钱效应重新变散。')
    falsification_conditions.append('异常对象次日明显转弱，原先“跌不下去”的信号没有继续保住。')
    falsification_conditions.append('首个60分钟不能确认，或者买点只剩情绪顶点可以追。')
    if rise_fall_ratio is not None and _safe_float(rise_fall_ratio, 0.0) > 0:
        falsification_conditions.append(
            f"涨跌比重新恶化到{observation.get('rise_fall_ratio_text', '明显转弱')}附近，且跌停继续增加。"
        )
    else:
        falsification_conditions.append(f'跌停快速增加到{max(dt_count + 5, 8)}只以上，修复链说明显断掉。')

    return {
        'stage_label': stage_label,
        'stage_reason': stage_reason,
        'stage_action': stage_action,
        'index_profit_relation': index_profit_relation,
        'index_profit_reason': index_profit_reason,
        'index_profit_action': index_profit_action,
        'focus_label': focus_label,
        'focus_reason': focus_reason,
        'focus_action': focus_action,
        'candidate_focus': candidate_focus,
        'candidate_action': candidate_action,
        'falsification_conditions': falsification_conditions[:4],
        'style_label': style_switch.get('style_label', ''),
        'style_action': style_switch.get('primary_action', ''),
        'follow_label': follow_verdict.get('label', ''),
    }


def _build_market_research_snapshot(data, final_gate, position_level, exit_analysis, observation_snapshot=None, target_date=''):
    return build_market_research_snapshot_contract(
        data,
        final_gate,
        position_level,
        exit_analysis,
        observation_snapshot=observation_snapshot,
        target_date=target_date,
        build_abnormal_projection_summary=_build_abnormal_projection_summary,
        build_market_style_switch_snapshot=_build_market_style_switch_snapshot,
        build_market_state_machine_snapshot=_build_market_state_machine_snapshot,
        build_mainline_rotation_snapshot=_build_mainline_rotation_snapshot,
        build_abnormal_probe_group=_build_abnormal_probe_group,
        build_special_probe_verdict=_build_special_probe_verdict,
        build_follow_verdict=_build_follow_verdict,
        build_dialectical_decision_snapshot=_build_dialectical_decision_snapshot,
    )


def _derive_step0_follow_plan(market_research_snapshot, final_gate, position_level):
    return derive_step0_follow_plan_contract(
        market_research_snapshot,
        final_gate,
        position_level,
    )


def _render_market_research_snapshot_section(market_research_snapshot, compact=False):
    market_research_snapshot = market_research_snapshot or {}
    observation = market_research_snapshot.get('observation', {}) or {}
    style_switch = market_research_snapshot.get('style_switch', {}) or {}
    state_machine = market_research_snapshot.get('state_machine', {}) or {}
    abnormal_projection = market_research_snapshot.get('abnormal_projection', {}) or {}
    follow_verdict = market_research_snapshot.get('follow_verdict', {}) or {}
    competition_focus = observation.get('competition_focus', {}) or {}
    rotation_snapshot = market_research_snapshot.get('mainline_rotation_snapshot', {}) or _build_mainline_rotation_snapshot(
        observation=observation,
        state_machine=state_machine,
        style_switch=style_switch,
        sector_ai_analysis=market_research_snapshot.get('sector_ai_analysis', {}) or {},
    )
    dialectical_decision = market_research_snapshot.get('dialectical_decision') or _build_dialectical_decision_snapshot(
        observation=observation,
        style_switch=style_switch,
        state_machine=state_machine,
        follow_verdict=follow_verdict,
        final_gate=market_research_snapshot.get('final_gate', {}) or {},
    )
    competition_result = "主线待定"
    competition_evidence = "先看趋势密度、异常承接和资金聚焦谁先胜出"
    if competition_focus:
        competition_result = f"{competition_focus.get('role', '观察线')} {competition_focus.get('sector', '-')}"
        competition_evidence = competition_focus.get('evidence', competition_evidence)

    return render_market_research_snapshot_section(
        {
            "compact": compact,
            "benchmark_change": _safe_float(observation.get('benchmark_change_pct', 0.0)),
            "turnover": _safe_float(observation.get('turnover', 0.0)),
            "observation": observation,
            "competition_result": competition_result,
            "competition_evidence": competition_evidence,
            "rotation_label": rotation_snapshot.get('rotation_label', '-'),
            "rotation_summary_text": rotation_snapshot.get('summary_text', rotation_snapshot.get('rotation_reason', '-')),
            "rotation_action": rotation_snapshot.get('rotation_action', '-'),
            "narrative_label": rotation_snapshot.get('narrative_label', '-'),
            "narrative_reason": rotation_snapshot.get('narrative_reason', '-'),
            "narrative_action": rotation_snapshot.get('narrative_action', '-'),
            "style_label": style_switch.get('style_label', '-'),
            "style_reason": style_switch.get('style_reason', '-'),
            "style_evidence_text": style_switch.get('evidence_text', '-'),
            "abnormal_projection_label": abnormal_projection.get('projection_label', '-'),
            "abnormal_projection_reason": abnormal_projection.get('projection_reason', '-'),
            "follow_verdict_label": follow_verdict.get('label', '-'),
            "follow_verdict_reason": follow_verdict.get('reason', '-'),
            "state_energy": state_machine.get('energy_state', '-'),
            "state_reason": state_machine.get('state_reason', '-'),
            "state_flow_direction": state_machine.get('flow_direction', '-'),
            "dialectical_decision": dialectical_decision,
        }
    )


def _render_step0_follow_section(step0_plan, market_research_snapshot, compact=False):
    step0_plan = step0_plan or {}
    market_research_snapshot = market_research_snapshot or {}
    observation = market_research_snapshot.get('observation', {}) or {}
    style_switch = market_research_snapshot.get('style_switch', {}) or {}
    state_machine = market_research_snapshot.get('state_machine', {}) or {}
    abnormal_projection = market_research_snapshot.get('abnormal_projection', {}) or {}
    return render_step0_follow_section(
        {
            "compact": compact,
            "step0_prediction_cn": step0_plan.get('step0_prediction_cn', '-'),
            "step0_reason": step0_plan.get('step0_reason', '-'),
            "step0_action": step0_plan.get('step0_action', '-'),
            "zt_count": observation.get('zt_count', 0),
            "dt_count": observation.get('dt_count', 0),
            "observation_summary": state_machine.get('observation_summary', '-'),
            "style_label": style_switch.get('style_label', '-'),
            "style_reason": style_switch.get('style_reason', '-'),
            "densest_sector": observation.get('densest_sector', '暂无明确主线'),
            "densest_sector_trend_count": observation.get('densest_sector_trend_count', 0),
            "resilient_abnormal_count": observation.get('resilient_abnormal_count', 0),
            "failed_abnormal_count": observation.get('failed_abnormal_count', 0),
            "abnormal_projection_label": abnormal_projection.get('projection_label', '-'),
            "state_energy": state_machine.get('energy_state', '-'),
            "state_reason": state_machine.get('state_reason', '-'),
        }
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
):
    """构建 Step0/Step1 共用的市场研究上下文，供日报与单票诊断复用。"""
    return build_market_research_context_bundle_contract(
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
        get_active_a_kill_records=get_active_a_kill_records,
        normalize_stock_code=normalize_stock_code,
        safe_float=_safe_float,
        is_stock_in_a_kill_cooldown=is_stock_in_a_kill_cooldown,
        sector_name_matches=sector_name_matches,
        build_abnormal_watch_pool=build_abnormal_watch_pool,
        decision_strict_mode=DECISION_STRICT_MODE,
        allow_display_degraded_abnormal_snapshot=ALLOW_DISPLAY_DEGRADED_ABNORMAL_SNAPSHOT,
        is_degraded_abnormal_snapshot=_is_degraded_abnormal_snapshot,
        build_sector_trend_snapshot=build_sector_trend_snapshot,
        build_leader_memory_bank=build_leader_memory_bank,
        refresh_tracking_memory=refresh_tracking_memory,
        discover_all_gem_breathing_candidates=_discover_all_gem_breathing_candidates,
        candidate_matches_mainline=_candidate_matches_mainline,
        build_gem_observation_pool=_build_gem_20cm_observation_pool,
        build_mainline_competition_snapshot=_build_mainline_competition_snapshot,
        build_market_observation_snapshot=_build_market_observation_snapshot,
        build_market_research_snapshot=_build_market_research_snapshot,
        derive_step0_follow_plan=_derive_step0_follow_plan,
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
    return build_candidate_bundle_contract(
        data,
        exit_analysis,
        candidates,
        watchlist,
        abnormal_watch_map,
        dragon_stocks,
        zt_pool_by_sector=zt_pool_by_sector,
        gem_breathing_candidates=gem_breathing_candidates,
        target_date=target_date,
        normalize_stock_code=normalize_stock_code,
        get_abnormal_rank_adjustment=get_abnormal_rank_adjustment,
        split_candidates_by_mainline=_split_candidates_by_mainline,
        build_gem_observation_pool=_build_gem_20cm_observation_pool,
        build_sector_trend_snapshot=build_sector_trend_snapshot,
        build_extreme_conviction_list=build_extreme_conviction_list,
    )


def _append_unique_text(container, text):
    text = str(text or '').strip()
    if text and text not in container:
        container.append(text)


def _format_step3_risk_reason(risk_penalties=None, repair_buffers=None, risk_level=''):
    risk_penalties = [str(item).strip() for item in (risk_penalties or []) if str(item or '').strip()]
    repair_buffers = [str(item).strip() for item in (repair_buffers or []) if str(item or '').strip()]

    if risk_penalties and repair_buffers:
        if risk_level == "🟢 低风险":
            return f"虽有{'、'.join(risk_penalties)}，但{'、'.join(repair_buffers)}，净风险可控"
        if risk_level == "🟡 中风险":
            return f"风险项：{'、'.join(risk_penalties)}；缓冲项：{'、'.join(repair_buffers)}；仍需观察"
        return f"风险项：{'、'.join(risk_penalties)}；虽有{'、'.join(repair_buffers)}，但不足以对冲"

    if risk_penalties:
        prefix = "风险项：" if len(risk_penalties) >= 2 else ""
        return f"{prefix}{'、'.join(risk_penalties)}"

    if repair_buffers:
        return f"修复项：{'、'.join(repair_buffers)}，净风险可控"

    return "风险可控"


def _parse_limit_time_to_minutes(time_text):
    digits = ''.join(ch for ch in str(time_text or '') if ch.isdigit())
    if len(digits) >= 6:
        digits = digits[:6]
        hours = int(digits[:2])
        minutes = int(digits[2:4])
        return hours * 60 + minutes
    if len(digits) == 4:
        hours = int(digits[:2])
        minutes = int(digits[2:4])
        return hours * 60 + minutes
    return None


def _evaluate_limit_up_friction(zhaban, last_limit_time='', turnover=0.0, board_count=1):
    zhaban = int(_safe_float(zhaban) or 0)
    turnover = _safe_float(turnover)
    board_count = int(_safe_float(board_count) or 1)

    if zhaban <= 0:
        return {
            'penalty': 0,
            'reason': '',
        }

    if zhaban == 1:
        penalty = 8
    elif zhaban == 2:
        penalty = 16
    elif zhaban == 3:
        penalty = 24
    else:
        penalty = 36 + min((zhaban - 4) * 2, 6)

    last_limit_minutes = _parse_limit_time_to_minutes(last_limit_time)
    if last_limit_minutes is not None:
        if last_limit_minutes <= 9 * 60 + 40:
            penalty -= 8
        elif last_limit_minutes <= 10 * 60 + 30:
            penalty -= 4
        elif last_limit_minutes >= 14 * 60 + 30:
            penalty += 8
        elif last_limit_minutes >= 13 * 60 + 30:
            penalty += 4

    if turnover >= 15:
        penalty += 4
    elif turnover >= 10:
        penalty += 2
    elif turnover <= 5:
        penalty -= 4
    elif turnover <= 8:
        penalty -= 2

    if board_count >= 3 and last_limit_minutes is not None and last_limit_minutes <= 10 * 60:
        penalty -= 2

    penalty = int(_clamp(penalty, 0, 48))

    if zhaban >= 4 and last_limit_minutes is not None:
        if last_limit_minutes >= 14 * 60 + 30:
            reason = f"炸板{zhaban}次且尾盘才回封"
        elif last_limit_minutes <= 10 * 60 + 30:
            reason = f"炸板{zhaban}次但上午回封"
        else:
            reason = f"炸板{zhaban}次且回封不算早"
    elif zhaban == 3 and last_limit_minutes is not None and last_limit_minutes <= 10 * 60:
        reason = "炸板3次但快速回封"
    else:
        reason = f"炸板{zhaban}次"

    return {
        'penalty': penalty,
        'reason': reason,
    }


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
    return build_risk_bundle_contract(
        data,
        target_date,
        mainline_name,
        core_stocks,
        secondary_stocks,
        gem_observation_stocks=gem_observation_stocks,
        zt_pool_by_sector=zt_pool_by_sector,
        dt_pool_by_sector=dt_pool_by_sector,
        persist_a_kill=persist_a_kill,
        normalize_stock_code=normalize_stock_code,
        safe_float=_safe_float,
        clamp=_clamp,
        get_abnormal_follow_risk_signal=get_abnormal_follow_risk_signal,
        format_risk_reason=_format_step3_risk_reason,
        update_a_kill_blacklist=update_a_kill_blacklist,
    )


def _build_front_mainline_label(market_research_snapshot, fallback_mainline=''):
    return build_front_mainline_label_contract(market_research_snapshot, fallback_mainline=fallback_mainline)


def _build_front_style_action_text(style_switch=None, final_gate=None, best_stock=None, watch_anchor=None, watch_anchor_type=''):
    return build_front_style_action_text_contract(
        style_switch=style_switch,
        final_gate=final_gate,
        best_stock=best_stock,
        watch_anchor=watch_anchor,
        watch_anchor_type=watch_anchor_type,
    )


def _render_core_mvp_digest(
    market_research_snapshot,
    final_gate,
    position_level,
    position_reason,
    exit_analysis=None,
    execution_framework_text='',
    high_board_count=0,
    structure_layer_text='',
    front_follow_action_text='',
    special_probe_text='',
    philosophy_constraint_text='',
    best_stock=None,
    watch_anchor=None,
    watch_anchor_type='',
    target_date='',
    compact=False,
):
    return render_core_mvp_digest_contract(
        market_research_snapshot,
        final_gate,
        position_level,
        position_reason,
        exit_analysis=exit_analysis,
        execution_framework_text=execution_framework_text,
        high_board_count=high_board_count,
        structure_layer_text=structure_layer_text,
        front_follow_action_text=front_follow_action_text,
        special_probe_text=special_probe_text,
        philosophy_constraint_text=philosophy_constraint_text,
        best_stock=best_stock,
        watch_anchor=watch_anchor,
        watch_anchor_type=watch_anchor_type,
        target_date=target_date,
        compact=compact,
        build_front_mainline_label=_build_front_mainline_label,
        build_gem_textbook_next_step_text=_build_gem_textbook_next_step_text,
        build_front_style_action_text=_build_front_style_action_text,
        build_alignment_pool_text=_build_alignment_pool_text,
        build_mainline_rotation_snapshot=_build_mainline_rotation_snapshot,
        resolve_primary_mainline_name=_resolve_primary_mainline_name,
        build_weak_to_strong_context=_build_weak_to_strong_context,
        get_contract_logic_digest_text=_get_contract_logic_digest_text,
        render_front_digest=render_front_digest,
        safe_float=_safe_float,
    )


def _render_mvp_focus_summary(
    market_research_snapshot,
    watchlist=None,
    abnormal_watch_pool=None,
    leader_memory_bank=None,
    core_stocks=None,
    crossline_observation_stocks=None,
    gem_breathing_candidates=None,
    filtered_out_gem_candidates=None,
    structure_layer_text='',
    focus_group=None,
    keep_group=None,
    delete_group=None,
    best_stock=None,
    watch_anchor=None,
    watch_anchor_type='重点观察谁',
    abnormal_probe_group=None,
    final_gate=None,
    position_level='',
    target_date='',
    compact=False,
):
    return render_mvp_focus_summary_contract(
        market_research_snapshot,
        watchlist=watchlist,
        abnormal_watch_pool=abnormal_watch_pool,
        leader_memory_bank=leader_memory_bank,
        core_stocks=core_stocks,
        crossline_observation_stocks=crossline_observation_stocks,
        gem_breathing_candidates=gem_breathing_candidates,
        filtered_out_gem_candidates=filtered_out_gem_candidates,
        structure_layer_text=structure_layer_text,
        focus_group=focus_group,
        keep_group=keep_group,
        delete_group=delete_group,
        best_stock=best_stock,
        watch_anchor=watch_anchor,
        watch_anchor_type=watch_anchor_type,
        abnormal_probe_group=abnormal_probe_group,
        final_gate=final_gate,
        position_level=position_level,
        target_date=target_date,
        compact=compact,
        resolve_primary_mainline_name=_resolve_primary_mainline_name,
        split_abnormal_watch_pool=_split_abnormal_watch_pool,
        build_bridge_prep_context=_build_bridge_prep_context,
        build_front_structure_layer_text=_build_front_structure_layer_text,
        build_special_probe_verdict=_build_special_probe_verdict,
        build_special_probe_focus_text=_build_special_probe_focus_text,
        build_mainline_rotation_snapshot=_build_mainline_rotation_snapshot,
        split_candidates_by_mainline=_split_candidates_by_mainline,
        format_candidate_preview=_format_candidate_preview,
        candidate_matches_mainline=_candidate_matches_mainline,
        build_position_sizing_decision=_build_position_sizing_decision,
        build_cycle_triplet_texts=_build_cycle_triplet_texts,
        build_execute_anchor_window_text=_build_execute_anchor_window_text,
        format_abnormal_probe_text=_format_abnormal_probe_text,
        build_front_follow_action_text=_build_front_follow_action_text,
        render_mvp_focus_summary=render_mvp_focus_summary,
    )


def _find_report_line_index(lines, marker, start=0, match_mode='equals'):
    for idx in range(start, len(lines)):
        line = lines[idx]
        if match_mode == 'equals' and line == marker:
            return idx
        if match_mode == 'startswith' and line.startswith(marker):
            return idx
        if match_mode == 'contains' and marker in line:
            return idx
    return -1


def _remove_report_section(lines, start_marker, end_marker=None, start_mode='equals', end_mode='equals'):
    start_idx = _find_report_line_index(lines, start_marker, match_mode=start_mode)
    if start_idx < 0:
        return lines
    if end_marker is None:
        del lines[start_idx:]
        return lines
    end_idx = _find_report_line_index(lines, end_marker, start=start_idx + 1, match_mode=end_mode)
    if end_idx < 0:
        del lines[start_idx:]
    else:
        del lines[start_idx:end_idx]
    return lines


def _squeeze_report_blank_lines(lines):
    squeezed = []
    blank_count = 0
    for line in lines:
        if line == "":
            blank_count += 1
            if blank_count > 1:
                continue
        else:
            blank_count = 0
        squeezed.append(line)
    return squeezed


def _compact_report_for_mvp(report):
    compacted = list(report)

    removal_rules = [
        ("## 二、预期日历（AI智能分析板块）", "## 十三、统一执行链（狙击手视角）", 'equals', 'equals'),
        ("### 总-市场整体判断", "#### Step 0 - 明日环境与跟随裁决", 'equals', 'equals'),
        ("#### Step 1 - 明天观察池", "#### 最终结论", 'equals', 'equals'),
        ("#### 💡 核心交易哲学：看好A，干A！", "## 十四、AI市场洞察总结", 'equals', 'equals'),
        ("## 十四、AI市场洞察总结", "## 十五、策略计划账本", 'equals', 'equals'),
        ("**Step 1.01 主线竞争格局", "**Step 1.05 龙头记忆库", 'startswith', 'startswith'),
        ("**Step 1.06 跟踪记忆校验", "**Step 1.1 明日预期强度排序", 'startswith', 'startswith'),
        ("**Step 1.2 明日预期分组**:", "**Step 1.3 异动后观察池", 'equals', 'startswith'),
        ("**Step 2.0 主线趋势密度复核", "**Step 2.1 明日核心预判", 'startswith', 'startswith'),
        ("**Step 2.3 暂不关注**", "**Step 2.4 明日核心方向预判", 'startswith', 'startswith'),
        ("**Step 2.7 AI智能板块归一化分析**", "**Step 2 结论**", 'equals', 'startswith'),
        ("#### 1.1 冻结因子快照", "### 2. 最近计划回放", 'equals', 'equals'),
        ("### 5. 固定Setup信号库回顾", "### 7. 系统自校准建议", 'equals', 'equals'),
        ("### 8. 跨结构周期毕业看板", "## 附录：数据获取与执行步骤清单", 'equals', 'equals'),
        ("## 附录：数据获取与执行步骤清单", None, 'equals', 'equals'),
    ]

    for start_marker, end_marker, start_mode, end_mode in removal_rules:
        compacted = _remove_report_section(
            compacted,
            start_marker,
            end_marker=end_marker,
            start_mode=start_mode,
            end_mode=end_mode,
        )

    compacted = [
        "## 二、统一执行链" if line == "## 十三、统一执行链（狙击手视角）" else
        "## 三、策略计划账本" if line == "## 十五、策略计划账本" else
        line
        for line in compacted
    ]

    return _squeeze_report_blank_lines(compacted)


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
    context = context or {}
    indices = data.get('indices', {}) or {}
    sh_index = indices.get('上证指数', {}) or {}
    mainline_name = exit_analysis.get('sector_name', '') if exit_analysis else ''
    best_stock = context.get('best_stock')
    watch_anchor = context.get('watch_anchor')
    selected_candidate = best_stock or watch_anchor
    selected_brief = {}
    setup_distribution = _build_abnormal_setup_distribution(context.get('abnormal_watch_pool', []))

    environment_score = _score_environment_snapshot(final_gate, position_level)
    structure_score = _score_structure_snapshot(market_zhongshu)
    mainline_score = _score_mainline_snapshot(
        mainline_name,
        context.get('mainline_score', 0),
        context.get('sector_trend_snapshot', []),
    )
    memory_score = _score_memory_snapshot(
        context.get('leader_memory_bank', []),
        context.get('tracking_memory_status', {}),
    )
    abnormal_score = _score_abnormal_snapshot(context.get('abnormal_watch_pool', []), selected_candidate)
    market_research_snapshot = context.get('market_research_snapshot', {}) or {}
    state_machine_snapshot = market_research_snapshot.get('state_machine') or _build_market_state_machine_snapshot(
        data,
        final_gate,
        position_level,
        exit_analysis,
        main_sectors_info=context.get('main_sectors_info', []),
        secondary_sectors_info=context.get('secondary_sectors_info', []),
        sector_trend_snapshot=context.get('sector_trend_snapshot', []),
        abnormal_watch_pool=context.get('abnormal_watch_pool', []),
    )
    abnormal_projection = market_research_snapshot.get('abnormal_projection') or _build_abnormal_projection_summary(
        context.get('abnormal_watch_pool', [])
    )
    style_switch_snapshot = market_research_snapshot.get('style_switch') or _build_market_style_switch_snapshot(
        target_date,
        data,
        observation_snapshot=market_research_snapshot.get('observation', {}) or {},
        abnormal_projection=abnormal_projection,
    )
    abnormal_probe_group = context.get('abnormal_probe_group', {}) or {}
    special_probe_verdict = context.get('special_probe_verdict') or market_research_snapshot.get('special_probe_verdict') or _build_special_probe_verdict(
        abnormal_probe_group=abnormal_probe_group,
        watch_anchor=watch_anchor,
        watch_anchor_type=context.get('watch_anchor_type', ''),
        mainline_name=mainline_name,
        target_date=target_date,
    )
    selected_candidate_obj = best_stock or context.get('watch_anchor')
    position_decision = context.get('position_decision') or _build_position_sizing_decision(
        final_gate=final_gate,
        state_machine_snapshot=state_machine_snapshot,
        best_stock=best_stock,
        watch_anchor=watch_anchor,
        watch_anchor_type=context.get('watch_anchor_type', ''),
        mainline_name=mainline_name,
        target_date=target_date,
        special_probe_verdict=special_probe_verdict,
    )
    selected_exit_rules = _build_candidate_exit_rules(
        selected_candidate_obj,
        (selected_candidate_obj or {}).get('stop_plan') if selected_candidate_obj else None,
    )
    selected_gem_contract = (selected_candidate_obj or {}).get('gem_breathing_contract') or {}

    selection_target_position = int(_safe_float(position_decision.get('target_position_pct', 0)))
    selection_mode = str(position_decision.get('participation_mode', '') or 'observe_0').strip()
    selection_action_type = 'execute' if selection_target_position > 0 and selected_candidate else 'watch_only' if selected_candidate else 'no_trade'
    selected_snapshot_candidate = dict(selected_candidate or {}) if selected_candidate else {}
    if selected_snapshot_candidate:
        selected_snapshot_candidate['position_pct'] = max(int(_safe_float(selected_snapshot_candidate.get('position_pct', 0))), selection_target_position)
        selected_snapshot_candidate['participation_mode'] = selection_mode or selected_snapshot_candidate.get('participation_mode', '')
        selected_snapshot_candidate['action_type'] = selection_action_type or selected_snapshot_candidate.get('action_type', '')
    selected_brief = _snapshot_candidate_brief(selected_snapshot_candidate) if selected_snapshot_candidate else {}
    if selection_target_position == 50 and best_stock:
        selection_anchor_type = '明天唯一能买的那只'
    elif selection_target_position == 30 and selected_candidate:
        selection_anchor_type = '30%条件试错仓'
    else:
        selection_anchor_type = context.get('watch_anchor_type', '')

    return {
        'version': STRATEGY_FACTOR_SNAPSHOT_VERSION,
        'report_date': target_date,
        'environment': {
            'score': environment_score,
            'position_level': position_level,
            'gate_status': final_gate.get('gate_status', '') if final_gate else '',
            'gate_reason': final_gate.get('gate_reason', '') if final_gate else '',
            'final_action': final_gate.get('final_action', '') if final_gate else '',
            'can_new_entry': bool(final_gate.get('can_new_entry')) if final_gate else False,
            'position_reason': position_reason,
            'benchmark_change_pct': _round_or_none(sh_index.get('涨跌幅', sh_index.get('change_pct', 0.0)), 4),
        },
        'structure': {
            'score': structure_score,
            'signal_type': market_zhongshu.get('signal', {}).get('signal_type', '') if market_zhongshu else '',
            'signal_status': market_zhongshu.get('signal', {}).get('status', '') if market_zhongshu else '',
            'current_zhongshu_start': (market_zhongshu.get('current_zhongshu', {}) or {}).get('start_date', '') if market_zhongshu else '',
            'current_zhongshu_end': (market_zhongshu.get('current_zhongshu', {}) or {}).get('end_date', '') if market_zhongshu else '',
        },
        'mainline': {
            'score': mainline_score,
            'name': mainline_name,
            'quadrant_label': context.get('mainline_in_quadrant', ''),
            'quadrant_quality_score': _round_or_none(context.get('mainline_score'), 2),
            'trend_snapshot_top': (context.get('sector_trend_snapshot', []) or [None])[0] or {},
        },
        'memory': {
            'score': memory_score,
            'leader_memory_count': len(context.get('leader_memory_bank', []) or []),
            'trusted_tracking_count': len((context.get('tracking_memory_status', {}) or {}).get('today_validated_items', []) or []),
            'tentative_tracking_count': len((context.get('tracking_memory_status', {}) or {}).get('today_tentative_items', []) or []),
            'leader_memory_names': [item.get('name', '') for item in (context.get('leader_memory_bank', []) or [])[:3]],
        },
        'abnormal': {
            'score': abnormal_score,
            'top_setups': setup_distribution[:5],
            'selected_setup': {
                'id': selected_brief.get('setup_signal_id', ''),
                'label': selected_brief.get('setup_signal_label', ''),
                'follow_state': selected_brief.get('abnormal_follow_state', ''),
            },
            'projection': abnormal_projection,
        },
        'style': style_switch_snapshot,
        'state_machine': state_machine_snapshot,
        'selection': {
            'action_type': selection_action_type,
            'anchor_type': selection_anchor_type,
            'participation_mode': selection_mode,
            'target_position_pct': selection_target_position,
            'candidate_feedback_ready': bool(position_decision.get('candidate_feedback_ready')),
            'candidate_feedback_score': int(_safe_float(position_decision.get('candidate_feedback_score', 0))),
            'candidate_feedback_reasons': list(position_decision.get('candidate_feedback_reasons', []) or []),
            'weak_to_strong_upgrade_ready': bool(position_decision.get('weak_to_strong_upgrade_ready')),
            'weak_to_strong_scenario': str(((position_decision.get('weak_to_strong_context') or {}).get('scenario', '') or '')).strip(),
            'weak_to_strong_summary': str(((position_decision.get('weak_to_strong_context') or {}).get('summary_text', '') or '')).strip(),
            'trigger_text': position_decision.get('trigger_text', ''),
            'contract_kind': str(selected_gem_contract.get('contract_kind', '') or ''),
            'contract_active_window_days': int(_safe_float(selected_gem_contract.get('active_window_days', 0))),
            'contract_right_side_trigger_price': _round_or_none(selected_gem_contract.get('right_side_trigger_price')),
            'contract_void_price': _round_or_none(selected_gem_contract.get('void_price')),
            'contract_reset_breakout_price': _round_or_none(selected_gem_contract.get('reset_breakout_price')),
            'contract_upgrade_condition_text': str(selected_gem_contract.get('upgrade_condition_text', '') or '').strip(),
            'selected_candidate': selected_brief,
            'runner_up': _snapshot_candidate_brief(context.get('runner_up')),
            'abnormal_probes': {
                'mainline_abnormal_probe': _snapshot_candidate_brief(abnormal_probe_group.get('mainline_abnormal_probe')),
                'crossline_abnormal_probe': _snapshot_candidate_brief(abnormal_probe_group.get('crossline_abnormal_probe')),
                'validation_probe': _snapshot_candidate_brief(abnormal_probe_group.get('validation_probe')),
            },
        },
        'candidate_stack': {
            'order_text': DECISION_STACK_ORDER_TEXT,
            'execute_candidates': [
                _snapshot_candidate_brief({
                    **(item or {}),
                    'action_type': 'execute',
                    'participation_mode': str(position_decision.get('participation_mode', '') or 'conditional_30').strip(),
                    'position_pct': max(int(_safe_float((item or {}).get('position_pct', 0))), selection_target_position),
                })
                for item in (context.get('scored_executable_stocks', []) or [])[:3]
            ],
        },
        'exit_rules': {
            'defensive_exit_rule': selected_exit_rules.get('defensive_exit_rule', DEFENSIVE_EXIT_RULE_TEXT),
            'profit_exit_rule': selected_exit_rules.get('profit_exit_rule', PROFIT_EXIT_RULE_TEXT),
            'holding_days_min': selected_exit_rules.get('holding_days_min', STRATEGY_HOLDING_DAYS_MIN),
            'holding_days_max': selected_exit_rules.get('holding_days_max', STRATEGY_HOLDING_DAYS_MAX),
            'profit_take_pct': selected_exit_rules.get('profit_take_pct', 0.05),
        },
    }


def _simulate_exit_for_entry(
    entry_price,
    bars,
    structure_stop=None,
    holding_days_min=STRATEGY_HOLDING_DAYS_MIN,
    holding_days_max=STRATEGY_HOLDING_DAYS_MAX,
    profit_take_pct=0.05,
):
    """用 setup 对应的短线纪律模拟退出：先防守，再看主动兑现，最后到持有窗口上限。"""
    entry_price = _safe_float(entry_price, 0.0)
    if entry_price <= 0 or not bars:
        return {
            'exit_price': None,
            'exit_date': '',
            'exit_reason': 'invalid',
            'status': 'pending',
            'return_pct': 0.0,
        }

    hard_stop = round(entry_price * (1 - MAX_SINGLE_TRADE_LOSS_PCT), 2)
    structure_stop = _safe_float(structure_stop, 0.0)
    effective_stop = round(max(structure_stop, hard_stop), 2) if structure_stop > 0 else hard_stop
    holding_days_min = max(int(_safe_float(holding_days_min, STRATEGY_HOLDING_DAYS_MIN) or STRATEGY_HOLDING_DAYS_MIN), 1)
    holding_days_max = max(int(_safe_float(holding_days_max, STRATEGY_HOLDING_DAYS_MAX) or STRATEGY_HOLDING_DAYS_MAX), holding_days_min)
    profit_take_pct = max(_safe_float(profit_take_pct, 0.05), 0.02)

    window_bars = list(bars[:holding_days_max])
    for idx, bar in enumerate(window_bars):
        low_price = _safe_float(bar.get('low'))
        close_price = _safe_float(bar.get('close'))
        if low_price > 0 and low_price <= effective_stop:
            return {
                'exit_price': effective_stop,
                'exit_date': bar.get('date', ''),
                'exit_reason': 'stop_loss',
                'status': 'closed',
                'return_pct': effective_stop / entry_price - 1,
                'effective_stop': effective_stop,
            }

        if close_price >= entry_price * (1 + profit_take_pct):
            return {
                'exit_price': round(close_price, 2),
                'exit_date': bar.get('date', ''),
                'exit_reason': 'active_sell_big_yang',
                'status': 'closed',
                'return_pct': close_price / entry_price - 1,
                'effective_stop': effective_stop,
            }

        if idx + 1 >= holding_days_min and idx + 1 == len(window_bars) and len(window_bars) < holding_days_max:
            return {
                'exit_price': round(close_price, 2),
                'exit_date': bar.get('date', ''),
                'exit_reason': 'mark_to_market',
                'status': 'open_mark_to_market',
                'return_pct': close_price / entry_price - 1,
                'effective_stop': effective_stop,
            }

    if len(window_bars) >= holding_days_max:
        exit_bar = window_bars[holding_days_max - 1]
        exit_close = _safe_float(exit_bar.get('close'))
        exit_low = _safe_float(exit_bar.get('low'))
        extra_bars = list(bars[holding_days_max:])
        sideways_hold = bool(
            extra_bars
            and exit_low > effective_stop
            and exit_close >= entry_price * 0.995
        )
        if sideways_hold:
            rebreak_reference = max(_safe_float(bar.get('close')) for bar in window_bars)
            extension_budget = min(max(holding_days_min - 1, 1), 2)
            for extra_offset, extra_bar in enumerate(extra_bars[:extension_budget], start=holding_days_max):
                extra_low = _safe_float(extra_bar.get('low'))
                extra_close = _safe_float(extra_bar.get('close'))
                if extra_low > 0 and extra_low <= effective_stop:
                    return {
                        'exit_price': effective_stop,
                        'exit_date': extra_bar.get('date', ''),
                        'exit_reason': 'stop_loss',
                        'status': 'closed',
                        'return_pct': effective_stop / entry_price - 1,
                        'effective_stop': effective_stop,
                    }
                if extra_close >= entry_price * (1 + profit_take_pct):
                    return {
                        'exit_price': round(extra_close, 2),
                        'exit_date': extra_bar.get('date', ''),
                        'exit_reason': 'active_sell_big_yang',
                        'status': 'closed',
                        'return_pct': extra_close / entry_price - 1,
                        'effective_stop': effective_stop,
                    }
                if extra_close >= rebreak_reference:
                    reset_result = _simulate_exit_for_entry(
                        entry_price=entry_price,
                        bars=bars[extra_offset:],
                        structure_stop=effective_stop,
                        holding_days_min=max(holding_days_min, 2),
                        holding_days_max=max(holding_days_min, 2),
                        profit_take_pct=profit_take_pct,
                    )
                    if reset_result.get('exit_date'):
                        return reset_result
                    break
            extension_exit_bar = extra_bars[min(extension_budget, len(extra_bars)) - 1]
            extension_exit_price = round(_safe_float(extension_exit_bar.get('close')), 2)
            return {
                'exit_price': extension_exit_price,
                'exit_date': extension_exit_bar.get('date', ''),
                'exit_reason': f'day{holding_days_max + min(extension_budget, len(extra_bars))}_close',
                'status': 'closed',
                'return_pct': extension_exit_price / entry_price - 1 if entry_price > 0 else 0.0,
                'effective_stop': effective_stop,
            }
        exit_price = round(exit_close, 2)
        return {
            'exit_price': exit_price,
            'exit_date': exit_bar.get('date', ''),
            'exit_reason': f'day{holding_days_max}_close',
            'status': 'closed',
            'return_pct': exit_price / entry_price - 1 if entry_price > 0 else 0.0,
            'effective_stop': effective_stop,
        }

    last_bar = window_bars[-1]
    last_close = round(_safe_float(last_bar.get('close')), 2)
    return {
        'exit_price': last_close,
        'exit_date': last_bar.get('date', ''),
        'exit_reason': 'mark_to_market',
        'status': 'open_mark_to_market',
        'return_pct': last_close / entry_price - 1 if entry_price > 0 else 0.0,
        'effective_stop': effective_stop,
    }


def _compute_benchmark_return(report_date, end_date, benchmark_report_close):
    report_date = _normalize_kline_date_str(report_date)
    end_date = _normalize_kline_date_str(end_date)
    benchmark_report_close = _safe_float(benchmark_report_close)
    if not report_date or not end_date:
        return 0.0

    benchmark_bars = fetch_daily_price_bars('sh.000001', report_date, end_date, is_index=True)
    if report_date == end_date:
        same_day_bar = _get_first_bar_on_or_after(benchmark_bars, report_date)
        if same_day_bar:
            change_pct = same_day_bar.get('change_pct', same_day_bar.get('涨跌幅'))
            if change_pct is not None:
                return _safe_float(change_pct) / 100.0
            open_price = _safe_float(same_day_bar.get('open'))
            close_price = _safe_float(same_day_bar.get('close'))
            if open_price > 0 and close_price > 0:
                return close_price / open_price - 1
        return 0.0

    if benchmark_report_close <= 0:
        benchmark_start_bar = _get_first_bar_on_or_after(benchmark_bars, report_date)
        if benchmark_start_bar:
            benchmark_report_close = _safe_float(benchmark_start_bar.get('close'))
        else:
            return 0.0
    benchmark_end_bar = _get_last_bar_on_or_before(benchmark_bars, end_date)
    if not benchmark_end_bar:
        return 0.0

    benchmark_end_close = _safe_float(benchmark_end_bar.get('close'))
    if benchmark_end_close <= 0:
        return 0.0
    return benchmark_end_close / benchmark_report_close - 1


def _get_nth_bar_after(bars, after_date, nth=1):
    after_dt = _parse_kline_date(after_date)
    if after_dt is None or nth <= 0:
        return None

    seen = 0
    for bar in bars or []:
        bar_dt = _parse_kline_date(bar.get('date'))
        if bar_dt and bar_dt > after_dt:
            seen += 1
            if seen == nth:
                return bar
    return None


def _compute_watch_outcome_metrics(record, as_of_date):
    record = record or {}
    report_date = _normalize_kline_date_str(record.get('report_date'))
    as_of_date = _normalize_kline_date_str(as_of_date)
    stock_code = normalize_stock_code(record.get('stock_code', ''))
    metrics = {
        'observation_baseline_price': None,
        'next_day_date': None,
        'next_day_stock_return': None,
        'next_day_benchmark_return': None,
        'next_day_alpha_return': None,
        'window_3d_end_date': None,
        'window_3d_stock_return': None,
        'window_3d_benchmark_return': None,
        'window_3d_alpha_return': None,
    }
    if not report_date or not as_of_date or not stock_code or as_of_date <= report_date:
        return metrics

    stock_bars = fetch_daily_price_bars(stock_code, report_date, as_of_date, is_index=False)
    report_close = _safe_float(record.get('report_day_close'))
    if report_close <= 0:
        report_close = _safe_float(record.get('entry_price_anchor'))
    if report_close <= 0:
        report_bar = _get_first_bar_on_or_after(stock_bars, report_date)
        if report_bar:
            report_close = _safe_float(report_bar.get('close'))
    if report_close <= 0:
        return metrics

    metrics['observation_baseline_price'] = round(report_close, 4)

    benchmark_bars = fetch_daily_price_bars('sh.000001', report_date, as_of_date, is_index=True)
    benchmark_report_close = _safe_float(record.get('benchmark_report_close'))
    if benchmark_report_close <= 0:
        benchmark_report_bar = _get_first_bar_on_or_after(benchmark_bars, report_date)
        if benchmark_report_bar:
            benchmark_report_close = _safe_float(benchmark_report_bar.get('close'))

    next_day_bar = _get_nth_bar_after(stock_bars, report_date, nth=1)
    if next_day_bar:
        next_day_close = _safe_float(next_day_bar.get('close'))
        if next_day_close > 0:
            metrics['next_day_date'] = next_day_bar.get('date') or None
            metrics['next_day_stock_return'] = next_day_close / report_close - 1
            benchmark_next_bar = _get_nth_bar_after(benchmark_bars, report_date, nth=1)
            if benchmark_report_close > 0 and benchmark_next_bar:
                benchmark_next_close = _safe_float(benchmark_next_bar.get('close'))
                if benchmark_next_close > 0:
                    metrics['next_day_benchmark_return'] = benchmark_next_close / benchmark_report_close - 1
                    metrics['next_day_alpha_return'] = (
                        metrics['next_day_stock_return'] - metrics['next_day_benchmark_return']
                    )

    day3_bar = _get_nth_bar_after(stock_bars, report_date, nth=3)
    if day3_bar:
        day3_close = _safe_float(day3_bar.get('close'))
        if day3_close > 0:
            metrics['window_3d_end_date'] = day3_bar.get('date') or None
            metrics['window_3d_stock_return'] = day3_close / report_close - 1
            benchmark_day3_bar = _get_nth_bar_after(benchmark_bars, report_date, nth=3)
            if benchmark_report_close > 0 and benchmark_day3_bar:
                benchmark_day3_close = _safe_float(benchmark_day3_bar.get('close'))
                if benchmark_day3_close > 0:
                    metrics['window_3d_benchmark_return'] = benchmark_day3_close / benchmark_report_close - 1
                    metrics['window_3d_alpha_return'] = (
                        metrics['window_3d_stock_return'] - metrics['window_3d_benchmark_return']
                    )

    return metrics


def _evaluate_single_strategy_record(record, as_of_date):
    report_date = _normalize_kline_date_str(record.get('report_date'))
    action_type = record.get('action_type', 'no_trade')
    benchmark_report_close = _safe_float(record.get('benchmark_report_close'))
    benchmark_report_change_pct = _safe_float(record.get('benchmark_report_change_pct'))
    as_of_date = _normalize_kline_date_str(as_of_date)
    result = {
        'status': 'pending',
        'status_label': _get_strategy_status_label('pending'),
        'status_note': '',
        'triggered': False,
        'trade_date': '',
        'confirm_triggered': False,
        'confirm_datetime': '',
        'entry_price_best': None,
        'entry_price_worst': None,
        'exit_date': '',
        'exit_reason': '',
        'strategy_return_best': 0.0,
        'strategy_return_worst': 0.0,
        'benchmark_return': 0.0,
        'alpha_return_best': 0.0,
        'alpha_return_worst': 0.0,
        'used_intraday': False,
        'as_of_date': as_of_date,
        'observation_baseline_price': None,
        'next_day_date': None,
        'next_day_stock_return': None,
        'next_day_benchmark_return': None,
        'next_day_alpha_return': None,
        'window_3d_end_date': None,
        'window_3d_stock_return': None,
        'window_3d_benchmark_return': None,
        'window_3d_alpha_return': None,
    }

    if not report_date:
        result['status'] = 'invalid'
        result['status_label'] = _get_strategy_status_label('invalid')
        return result

    if report_date == as_of_date and benchmark_report_change_pct:
        default_benchmark_return = benchmark_report_change_pct / 100.0
    else:
        default_benchmark_return = _compute_benchmark_return(report_date, as_of_date, benchmark_report_close)
    result['benchmark_return'] = default_benchmark_return
    result['alpha_return_best'] = result['strategy_return_best'] - default_benchmark_return
    result['alpha_return_worst'] = result['strategy_return_worst'] - default_benchmark_return

    if action_type != 'execute':
        result.update(_compute_watch_outcome_metrics(record, as_of_date))
        result['status'] = action_type
        result['status_label'] = _get_strategy_status_label(action_type)
        return result

    stock_code = normalize_stock_code(record.get('stock_code', ''))
    if not stock_code:
        result['status'] = 'invalid'
        result['status_label'] = _get_strategy_status_label('invalid')
        return result

    trade_bars = fetch_daily_price_bars(stock_code, report_date, as_of_date, is_index=False)
    trade_bar = _get_first_bar_after(trade_bars, report_date)
    if not trade_bar:
        result['status'] = 'pending'
        result['status_label'] = _get_strategy_status_label('pending')
        return result

    trade_date = trade_bar.get('date', '')
    result['trade_date'] = trade_date

    entry_low = _safe_float(record.get('entry_range_low'))
    entry_high = _safe_float(record.get('entry_range_high'))
    if entry_low <= 0 or entry_high <= 0:
        entry_anchor = _safe_float(record.get('entry_price_anchor'))
        if entry_anchor > 0:
            entry_low = entry_high = entry_anchor

    if entry_low > entry_high > 0:
        entry_low, entry_high = entry_high, entry_low

    confirm_price = _safe_float(record.get('confirm_price_60m'))
    support_price = _safe_float(record.get('confirm_support_60m'))

    day_60m = [
        bar for bar in fetch_intraday_bars(stock_code, trade_date, period='60', lookback_bars=10)
        if _normalize_kline_date_str(bar.get('date')) == trade_date
    ]
    day_30m = [
        bar for bar in fetch_intraday_bars(stock_code, trade_date, period='30', lookback_bars=20)
        if _normalize_kline_date_str(bar.get('date')) == trade_date
    ]

    confirm_triggered = False
    confirm_datetime = ''
    if day_60m:
        result['used_intraday'] = True
        if confirm_price > 0:
            for bar in day_60m:
                high_price = _safe_float(bar.get('high'))
                low_price = _safe_float(bar.get('low'))
                close_price = _safe_float(bar.get('close'))
                if high_price >= confirm_price and (
                    support_price <= 0 or low_price >= support_price or close_price >= support_price
                ):
                    confirm_triggered = True
                    confirm_datetime = bar.get('datetime', '')
                    break
        else:
            confirm_triggered = True
            confirm_datetime = day_60m[0].get('datetime', '')

    if not confirm_triggered:
        day_high = _safe_float(trade_bar.get('high'))
        day_low = _safe_float(trade_bar.get('low'))
        day_close = _safe_float(trade_bar.get('close'))
        if (confirm_price <= 0 or day_high >= confirm_price) and (
            support_price <= 0 or day_low >= support_price or day_close >= support_price
        ):
            confirm_triggered = True
            confirm_datetime = trade_date

    result['confirm_triggered'] = confirm_triggered
    result['confirm_datetime'] = confirm_datetime
    if not confirm_triggered:
        result['status'] = 'not_triggered'
        result['status_label'] = _get_strategy_status_label('not_triggered')
        return result

    entry_candidates = []
    if day_30m:
        result['used_intraday'] = True
        for bar in day_30m:
            bar_dt = str(bar.get('datetime', ''))
            if confirm_datetime and len(confirm_datetime) > 10 and bar_dt and bar_dt < confirm_datetime:
                continue
            high_price = _safe_float(bar.get('high'))
            low_price = _safe_float(bar.get('low'))
            if high_price >= entry_low and low_price <= entry_high:
                entry_candidates.append(bar)

    if entry_candidates:
        actual_entry_low = min(max(entry_low, _safe_float(bar.get('low'))) for bar in entry_candidates)
        actual_entry_high = max(min(entry_high, _safe_float(bar.get('high'))) for bar in entry_candidates)
    else:
        day_high = _safe_float(trade_bar.get('high'))
        day_low = _safe_float(trade_bar.get('low'))
        if day_high >= entry_low and day_low <= entry_high:
            actual_entry_low = max(entry_low, day_low)
            actual_entry_high = min(entry_high, day_high)
        else:
            result['status'] = 'not_triggered'
            result['status_label'] = _get_strategy_status_label('not_triggered')
            return result

    if actual_entry_low <= 0 or actual_entry_high <= 0 or actual_entry_low > actual_entry_high:
        result['status'] = 'not_triggered'
        result['status_label'] = _get_strategy_status_label('not_triggered')
        return result

    window_bars = [bar for bar in trade_bars if _normalize_kline_date_str(bar.get('date')) >= trade_date]
    if not window_bars:
        result['status'] = 'pending'
        result['status_label'] = _get_strategy_status_label('pending')
        return result

    structure_stop = _safe_float(record.get('structure_stop_30m') or record.get('effective_stop'))
    best_exit = _simulate_exit_for_entry(
        actual_entry_low,
        window_bars,
        structure_stop=structure_stop,
        holding_days_min=record.get('holding_days_min', STRATEGY_HOLDING_DAYS_MIN),
        holding_days_max=record.get('holding_days_max', STRATEGY_HOLDING_DAYS_MAX),
        profit_take_pct=record.get('profit_take_pct', 0.05),
    )
    worst_exit = _simulate_exit_for_entry(
        actual_entry_high,
        window_bars,
        structure_stop=structure_stop,
        holding_days_min=record.get('holding_days_min', STRATEGY_HOLDING_DAYS_MIN),
        holding_days_max=record.get('holding_days_max', STRATEGY_HOLDING_DAYS_MAX),
        profit_take_pct=record.get('profit_take_pct', 0.05),
    )

    result['triggered'] = True
    result['status'] = worst_exit.get('status', 'closed')
    if best_exit.get('status') == 'open_mark_to_market' or worst_exit.get('status') == 'open_mark_to_market':
        result['status'] = 'open_mark_to_market'
    result['status_label'] = _get_strategy_status_label(result['status'])
    result['entry_price_best'] = round(actual_entry_low, 2)
    result['entry_price_worst'] = round(actual_entry_high, 2)
    result['exit_date'] = worst_exit.get('exit_date') or best_exit.get('exit_date') or ''
    result['exit_reason'] = worst_exit.get('exit_reason') or best_exit.get('exit_reason') or ''
    result['strategy_return_best'] = best_exit.get('return_pct', 0.0)
    result['strategy_return_worst'] = worst_exit.get('return_pct', 0.0)

    benchmark_end_date = result['exit_date'] or trade_date
    if report_date == benchmark_end_date and benchmark_report_change_pct:
        benchmark_return = benchmark_report_change_pct / 100.0
    else:
        benchmark_return = _compute_benchmark_return(report_date, benchmark_end_date, benchmark_report_close)
    result['benchmark_return'] = benchmark_return
    result['alpha_return_best'] = result['strategy_return_best'] - benchmark_return
    result['alpha_return_worst'] = result['strategy_return_worst'] - benchmark_return
    return result


def _collect_record_market_path(record, as_of_date):
    code = normalize_stock_code(record.get('stock_code', ''))
    report_date = _normalize_kline_date_str(record.get('report_date'))
    as_of_date = _normalize_kline_date_str(as_of_date)
    if not code or not report_date or not as_of_date:
        return {}

    sim = record.get('simulation', {}) or {}
    baseline_price = _safe_float(record.get('report_day_close') or record.get('entry_price_anchor'))
    start_date = report_date
    if sim.get('triggered'):
        entry_low = _safe_float(sim.get('entry_price_best'))
        entry_high = _safe_float(sim.get('entry_price_worst'))
        if entry_low > 0 and entry_high > 0:
            baseline_price = (entry_low + entry_high) / 2.0
        elif entry_low > 0 or entry_high > 0:
            baseline_price = max(entry_low, entry_high)
        start_date = _normalize_kline_date_str(sim.get('trade_date')) or report_date

    if baseline_price <= 0:
        return {}

    bars = fetch_daily_price_bars(code, start_date, as_of_date, is_index=False)
    bars = [
        bar for bar in bars or []
        if start_date <= _normalize_kline_date_str(bar.get('date')) <= as_of_date
    ]
    if not bars:
        return {}

    end_bar = _get_last_bar_on_or_before(bars, as_of_date) or bars[-1]
    end_close = _safe_float(end_bar.get('close'))
    observed_return = (end_close / baseline_price - 1) if end_close > 0 else None

    highs = [_safe_float(bar.get('high')) for bar in bars if _safe_float(bar.get('high')) > 0]
    lows = [_safe_float(bar.get('low')) for bar in bars if _safe_float(bar.get('low')) > 0]
    max_runup = (max(highs) / baseline_price - 1) if highs else None
    max_drawdown = (min(lows) / baseline_price - 1) if lows else None

    midpoint_return = None
    if sim.get('triggered'):
        midpoint_return = (
            _safe_float(sim.get('strategy_return_worst')) + _safe_float(sim.get('strategy_return_best'))
        ) / 2.0

    post_exit_extension = None
    exit_date = _normalize_kline_date_str(sim.get('exit_date'))
    if exit_date:
        post_exit_bars = [
            bar for bar in bars
            if _normalize_kline_date_str(bar.get('date')) > exit_date
        ]
        if post_exit_bars and midpoint_return is not None:
            post_exit_high = max(_safe_float(bar.get('high')) for bar in post_exit_bars if _safe_float(bar.get('high')) > 0)
            if post_exit_high > 0:
                post_exit_extension = post_exit_high / baseline_price - 1 - midpoint_return

    return {
        'baseline_price': round(baseline_price, 4),
        'observed_return': observed_return,
        'max_runup': max_runup,
        'max_drawdown': max_drawdown,
        'post_exit_extension': post_exit_extension,
    }


def _build_recent_target_followup_item(record, as_of_date):
    record = record or {}
    code = normalize_stock_code(record.get('stock_code', ''))
    report_date = _normalize_kline_date_str(record.get('report_date'))
    as_of_date = _normalize_kline_date_str(as_of_date)
    stock_name = str(record.get('stock_name') or '').strip()
    if not code or not report_date or not as_of_date or not stock_name:
        return {}

    tracking_days = _count_trading_days_between(report_date, as_of_date)
    if tracking_days <= 1 or tracking_days > 6:
        return {}

    bars = fetch_daily_price_bars(code, report_date, as_of_date, is_index=False)
    bars = [
        bar for bar in (bars or [])
        if report_date <= _normalize_kline_date_str(bar.get('date')) <= as_of_date
    ]
    if not bars:
        return {}

    latest_bar = _get_last_bar_on_or_before(bars, as_of_date) or bars[-1]
    latest_close = _safe_float(latest_bar.get('close'))
    latest_high = _safe_float(latest_bar.get('high'))
    latest_low = _safe_float(latest_bar.get('low'))
    if latest_close <= 0:
        return {}

    confirm_price = _round_or_none(record.get('confirm_price_60m') or record.get('entry_price_anchor'))
    support_price = _round_or_none(
        record.get('confirm_support_60m')
        or record.get('execution_stop')
        or record.get('effective_stop')
        or record.get('display_anchor_price')
    )
    contract_kind = str(record.get('contract_kind', '') or '').strip()
    contract_window_days = max(int(_safe_float(record.get('contract_active_window_days', 0))), 0)
    contract_trigger_price = _round_or_none(record.get('contract_right_side_trigger_price') or confirm_price)
    contract_void_price = _round_or_none(record.get('contract_void_price') or support_price)
    contract_reset_breakout_price = _round_or_none(record.get('contract_reset_breakout_price'))
    attribution_label = str((record.get('attribution', {}) or {}).get('label', '') or '').strip()
    path_metrics = _collect_record_market_path(record, as_of_date) or {}
    observed_return = path_metrics.get('observed_return')
    max_runup = path_metrics.get('max_runup')

    support_broken = bool(
        support_price is not None
        and support_price > 0
        and (latest_close < support_price or latest_low < support_price)
    )
    confirm_reclaimed = bool(confirm_price is not None and confirm_price > 0 and latest_close >= confirm_price)
    confirm_tested = bool(confirm_price is not None and confirm_price > 0 and latest_high >= confirm_price)

    current_position = f'收于{latest_close:.2f}'
    timeline_text = '从选出日到今天，价格还在继续演化。'
    if support_broken and support_price is not None:
        path_label = '已失守观察边界'
        current_position = f'收于{latest_close:.2f}，已跌破{support_price:.2f}观察边界'
        focus_text = (
            f'未来1-3天先按作废处理；只有重新站回{support_price:.2f}'
            f"{'并再次站上' + format(confirm_price, '.2f') if confirm_price is not None else ''}后，才重新评估。"
        )
        timeline_text = f'选出后价格一度反复，但到今天已经失守{support_price:.2f}观察边界。'
        review_hint = '这说明观察权已经失效，后续复盘不要把失守对象继续误当成可执行候选。'
    elif contract_kind == 'gem_breathing_20cm' and contract_reset_breakout_price is not None and latest_close >= contract_reset_breakout_price and (contract_void_price is None or latest_close >= contract_void_price):
        path_label = '右侧确认/再突破已出现'
        current_position = f'收于{latest_close:.2f}，已重新站上{contract_reset_breakout_price:.2f}再突破位'
        trigger_ref = contract_trigger_price if contract_trigger_price is not None else confirm_price
        if trigger_ref is not None and contract_void_price is not None:
            focus_text = f'未来1-3天重点看{contract_void_price:.2f}不能破，并继续站稳{trigger_ref:.2f}之上；当前已重新站上{contract_reset_breakout_price:.2f}再突破位，确认稳住后才考虑30%条件试错'
            timeline_text = f'预启动观察后价格一直没失守{contract_void_price:.2f}，到今天已重新站上{contract_reset_breakout_price:.2f}再突破位。'
        else:
            focus_text = '未来1-3天重点看再突破后能否继续横住，不满足继续只观察。'
            timeline_text = f'预启动观察后价格到今天已重新站上{contract_reset_breakout_price:.2f}再突破位。'
        review_hint = f'这说明创业板20cm预启动合同仍在{contract_window_days or 5}日窗口内，后续重点看它会不会从观察权升级到30%条件试错。'
    elif attribution_label == '个股对了但环境不放行':
        path_label = '个股先走出来了'
        if confirm_price is not None:
            current_position = f'收于{latest_close:.2f}，明显站在{confirm_price:.2f}确认位之上'
            focus_text = f'未来1-3天重点看{confirm_price:.2f}之上能否继续强势；若继续扩张，要回查环境过滤是否过严'
            timeline_text = f'选出当天已经完成{confirm_price:.2f}确认，之后连续几天都站在确认位之上。'
        else:
            focus_text = '未来1-3天重点看是否继续强势；若继续扩张，要回查环境过滤是否过严'
            timeline_text = '选出后价格持续走强，明显快于最初的观察口径。'
        review_hint = '这说明对象先强于环境，后续要反查环境过滤/桥接层是不是拦得过严。'
    elif attribution_label == '弱转强识别偏慢':
        path_label = '假弱后超预期转强'
        if confirm_price is not None:
            current_position = f'收于{latest_close:.2f}，已经沿着{confirm_price:.2f}确认位上方继续走强'
            focus_text = f'未来1-3天重点看{confirm_price:.2f}之上能否继续 act right；若继续强势，下次要更早把这类假弱样本纳入升级评估'
            timeline_text = f'前面假弱承接住后，价格又重新站稳{confirm_price:.2f}并继续走强。'
        else:
            focus_text = '未来1-3天重点看是否继续 act right；若继续强势，下次要更早把这类假弱样本纳入升级评估'
            timeline_text = '前面假弱承接住后，价格又给出超预期转强。'
        review_hint = '这说明它本来就是强基底上的假弱，后续又走成超预期转强；以后不能等它完全走出来才承认弱转强。'
    elif attribution_label == '介入周期偏慢':
        path_label = '已走成 act right'
        if confirm_price is not None:
            current_position = f'收于{latest_close:.2f}，仍在{confirm_price:.2f}确认位之上'
            focus_text = f'未来1-3天重点看{confirm_price:.2f}之上能否继续横住并给利润缓冲'
            timeline_text = f'选出后很快完成{confirm_price:.2f}确认，随后一直没有失去确认位。'
        else:
            focus_text = '未来1-3天重点看是否继续横住并给利润缓冲'
            timeline_text = '选出后价格很快按强股方式替判断作证。'
        review_hint = '这说明票本身没看错，慢在介入权给慢了。'
    elif confirm_reclaimed and observed_return is not None and observed_return >= 0.03:
        path_label = '已走成 act right'
        if confirm_price is not None:
            current_position = f'收于{latest_close:.2f}，仍在{confirm_price:.2f}确认位之上'
            focus_text = f'未来1-3天重点看{confirm_price:.2f}之上能否继续横住并给利润缓冲'
            timeline_text = f'价格已经重新站稳{confirm_price:.2f}，并且到今天还维持在确认位上方。'
        else:
            focus_text = '未来1-3天重点看是否继续横住并给利润缓冲'
            timeline_text = '价格已经明显转强，今天仍保持强势结构。'
        review_hint = '这说明价格已经替判断作证，后续复盘不能再把它和普通观察对象混在一起。'
    elif (confirm_reclaimed and max_runup is not None and max_runup >= 0.08):
        path_label = '个股先走出来了'
        if confirm_price is not None:
            current_position = f'收于{latest_close:.2f}，明显站在{confirm_price:.2f}确认位之上'
            focus_text = f'未来1-3天重点看{confirm_price:.2f}之上能否继续强势；若继续扩张，要回查环境过滤是否过严'
            timeline_text = f'价格已经越过{confirm_price:.2f}并明显展开，但系统当时没有给执行权。'
        else:
            focus_text = '未来1-3天重点看是否继续强势；若继续扩张，要回查环境过滤是否过严'
            timeline_text = '价格已经明显展开，但系统当时没有给执行权。'
        review_hint = '这说明对象先强于环境，后续要反查环境过滤/桥接层是不是拦得过严。'
    elif confirm_tested and support_price is not None and latest_close >= support_price:
        path_label = '先强后回，进入二次确认'
        if confirm_price is not None:
            current_position = f'收于{latest_close:.2f}，未破{support_price:.2f}，但还没重新站稳{confirm_price:.2f}'
            focus_text = f'未来1-3天重点看{support_price:.2f}不能破，重新站回{confirm_price:.2f}才算重新亮起介入权'
            timeline_text = f'选出后先摸到{confirm_price:.2f}，但后面没有继续强扩张；到今天仍未重新站稳确认位。'
        else:
            current_position = f'收于{latest_close:.2f}，仍在观察边界{support_price:.2f}之上'
            focus_text = f'未来1-3天重点看{support_price:.2f}不能破，再看是否重新转强'
            timeline_text = f'价格曾经有过转强尝试，但到今天更像二次确认阶段。'
        review_hint = '这说明防守不一定错，但后续要继续跟踪它会不会从观察对象重新走回唯一动作。'
    elif support_price is not None and latest_close >= support_price:
        path_label = '仍在观察周期'
        if confirm_price is not None:
            current_position = f'收于{latest_close:.2f}，未破{support_price:.2f}观察边界，但还没重新站回{confirm_price:.2f}'
            focus_text = f'未来1-3天先看{support_price:.2f}不破，再看能否重新站上{confirm_price:.2f}'
            timeline_text = f'到今天还没失守{support_price:.2f}，但也还没重新完成{confirm_price:.2f}确认。'
        else:
            current_position = f'收于{latest_close:.2f}，仍在观察边界{support_price:.2f}之上'
            focus_text = f'未来1-3天先看{support_price:.2f}不破，再看有没有继续转强'
            timeline_text = f'到今天仍在观察边界之上，但还没有形成明确升级信号。'
        review_hint = '这说明它还没彻底走坏，但也不能把观察权误写成执行权。'
    else:
        path_label = '继续跟踪'
        focus_text = '未来1-3天继续看是否重新转强，不急着提前下结论。'
        timeline_text = '这段时间价格既没有彻底走坏，也没有给出足够强的升级证据。'
        review_hint = '这说明样本还没给出足够清晰的后验信号，先继续跟踪。'

    return {
        'report_date': report_date,
        'stock_label': f'{stock_name}({code})',
        'sample_label': f'{stock_name}({code})',
        'tracking_days': tracking_days,
        'phase_label': f'第{tracking_days}个交易日',
        'path_label': path_label,
        'current_position': current_position,
        'today_view': current_position,
        'timeline_text': timeline_text,
        'focus_text': focus_text,
        'next_focus': focus_text,
        'review_hint': review_hint,
        'attribution_label': attribution_label or '-',
    }


def _build_recent_target_followups(records, as_of_date, limit=3):
    items = []
    for record in sorted(
        records or [],
        key=lambda x: _normalize_kline_date_str(x.get('report_date')),
        reverse=True,
    ):
        item = _build_recent_target_followup_item(record, as_of_date)
        if item:
            items.append(item)
        if len(items) >= limit:
            break
    return items


def _build_current_target_review_item(current_plan):
    current_plan = current_plan or {}
    code = normalize_stock_code(current_plan.get('stock_code', ''))
    report_date = _normalize_kline_date_str(current_plan.get('report_date'))
    stock_name = str(current_plan.get('stock_name') or '').strip()
    if not code or not report_date or not stock_name:
        return {}

    bars = fetch_daily_price_bars(code, report_date, report_date, is_index=False)
    bars = [bar for bar in (bars or []) if _normalize_kline_date_str(bar.get('date')) == report_date]
    if not bars:
        return {}

    bar = bars[-1]
    close_price = _safe_float(bar.get('close'))
    high_price = _safe_float(bar.get('high'))
    low_price = _safe_float(bar.get('low'))
    if close_price <= 0:
        return {}

    confirm_price = _round_or_none(current_plan.get('confirm_price_60m') or current_plan.get('entry_price_anchor'))
    support_price = _round_or_none(
        current_plan.get('confirm_support_60m')
        or current_plan.get('execution_stop')
        or current_plan.get('effective_stop')
        or current_plan.get('display_anchor_price')
    )
    trigger_text = str(current_plan.get('trigger_text', '') or '').strip()

    if confirm_price is not None and support_price is not None and high_price >= confirm_price and low_price < support_price:
        path_label = '确认不干净，继续观察'
        timeline_text = f'今天打到{confirm_price:.2f}，但盘中低点{low_price:.2f}先破{support_price:.2f}。'
        today_view = '收盘打到确认位，不代表确认链完整。'
        next_focus = f'未来1-3天先看{support_price:.2f}能否重新站稳，再看有没有更干净的确认。'
        review_hint = '不能因为今天收得高，就提前把它当成航天工程。'
    elif confirm_price is not None and support_price is not None and high_price >= confirm_price and low_price >= support_price:
        path_label = '日内确认相对干净'
        timeline_text = f'今天已经打到{confirm_price:.2f}，且日内没有破{support_price:.2f}。'
        today_view = f'收于{close_price:.2f}，确认链相对干净，但还缺后续连续 act right。'
        next_focus = f'未来1-3天重点看{confirm_price:.2f}之上能否继续 act right。'
        review_hint = '这时可以继续跟踪，但还不能只凭一天就认定它已经完成升级。'
    elif support_price is not None and low_price < support_price:
        path_label = '先破观察边界，暂不升级'
        timeline_text = f'今天盘中最低{low_price:.2f}，已经先破{support_price:.2f}观察边界。'
        today_view = f'收于{close_price:.2f}，但链路已经被日内破坏。'
        next_focus = f'未来1-3天先看能否重新站回{support_price:.2f}，否则按作废处理。'
        review_hint = '这说明今天更多只是探针，不该提前抬成执行对象。'
    else:
        path_label = '还在等待确认'
        if confirm_price is not None:
            timeline_text = f'今天还没有把{confirm_price:.2f}这道确认链走完整。'
            next_focus = f'未来1-3天继续看能否站上{confirm_price:.2f}并保持不破。'
        else:
            timeline_text = '今天还没把确认链走完整。'
            next_focus = '未来1-3天继续看能否给出更清楚的确认。'
        today_view = f'收于{close_price:.2f}，当前仍以观察为主。'
        review_hint = '这说明现在更适合继续观察，不适合抢着给执行权。'

    return {
        'sample_label': f'{stock_name}({code})',
        'report_date': report_date,
        'phase_label': '报告日当天',
        'path_label': path_label,
        'timeline_text': timeline_text,
        'today_view': today_view,
        'next_focus': next_focus,
        'review_hint': review_hint,
        'trigger_text': trigger_text,
    }


def _derive_target_review_system_fix(item):
    item = item or {}
    sample_label = str(item.get('sample_label', '') or '')
    path_label = str(item.get('path_label', '') or '')
    review_hint = str(item.get('review_hint', '') or '')

    if '彩虹股份' in sample_label or '观察链不要偷写成执行链' in review_hint or '提前把它当成航天工程' in review_hint:
        return '观察链不要偷写成执行链：先继续观察，不提前升级成航天工程那种已证明样本。'
    if '弱转强识别偏慢' in review_hint or '假弱后超预期转强' in path_label or ('假弱' in review_hint and '弱转强' in review_hint):
        return '弱转强识别偏慢：对强基底+假弱非真弱、且主线共振未坏的对象，要更早从观察权升级到执行评估。'
    if '介入权给慢了' in review_hint or '已走成 act right' in path_label:
        return '介入周期偏慢：对已经确认成功且继续 act right 的唯一对象，要更快给到执行评估。'
    if '环境过滤' in review_hint or '个股先走出来了' in path_label:
        return '环境过滤过严：跨线对象若已连续 act right，不能一直停在纯观察层。'
    if '二次确认' in path_label:
        return '二次确认样本单独管理：先盯 guard 不破，再看能否重新站回 confirm，不要和已成功样本混为一类。'
    if '失守' in path_label:
        return '作废样本及时出清：失守 guard 后不要继续在观察池里占位置。'
    return '继续积累样本：暂不改大规则，先把后续1-3天路径继续跟清楚。'


def _build_recent_target_reflection(review_matrix):
    review_matrix = review_matrix or []
    if not review_matrix:
        return {}

    fixes = [str(item.get('system_fix', '') or '') for item in review_matrix]
    mistakes = []
    adjustments = []

    if any('介入周期偏慢' in fix for fix in fixes):
        mistakes.append('- 龙蟠科技这类样本说明我对唯一对象的介入周期仍然偏慢。')
        adjustments.append('- 下次再遇到唯一对象次日确认成功且继续 act right，要更快给执行评估。')
    if any('环境过滤过严' in fix for fix in fixes):
        mistakes.append('- 航天工程这类样本说明我对跨线连续 act right 样本的环境过滤仍然偏严。')
        adjustments.append('- 下次再遇到跨线对象连续 act right，不能一直停在纯观察层。')
    if any('弱转强识别偏慢' in fix for fix in fixes):
        mistakes.append('- 弱转强样本说明我对强基底假弱对象的识别仍然偏慢，容易等它彻底走出来后才承认。')
        adjustments.append('- 下次再遇到强基底+假弱非真弱+主线共振未坏的对象，要更早从观察权升级到执行评估。')
    if any('二次确认' in fix for fix in fixes):
        mistakes.append('- 石大胜华这类样本说明我过去容易把“先强后回”样本压成一句防守正确，没有单独拆出二次确认。')
        adjustments.append('- 下次再遇到先强后回样本，要单独按 guard/confirm 的二次确认链路管理。')
    if any('观察链不要偷写成执行链' in fix for fix in fixes):
        mistakes.append('- 彩虹股份这类样本说明我容易因为当天收盘强，就提前把观察对象脑补成成功样本。')
        adjustments.append('- 观察链不要偷写成执行链：下次再遇到确认不干净的当日探针，先继续观察，不提前升格。')

    headline = '这批样本已经告诉我，错不在同一个地方，必须分层修正。'
    if not mistakes:
        mistakes.append('- 当前后验样本还不够多，暂时先继续积累。')
    if not adjustments:
        adjustments.append('- 先继续跟踪样本，不急着改大规则。')

    return {
        'headline': headline,
        'mistakes': mistakes,
        'adjustments': adjustments,
    }


def _build_recent_target_review_matrix(current_plan, recent_followups, limit=4):
    items = []
    for item in (recent_followups or [])[:max(limit - 1, 0)]:
        items.append({
            'sample_label': item.get('sample_label') or item.get('stock_label') or '-',
            'report_date': item.get('report_date', '-'),
            'phase_label': item.get('phase_label') or f"第{item.get('tracking_days', 0)}个交易日",
            'path_label': item.get('path_label', '-'),
            'timeline_text': item.get('timeline_text', item.get('current_position', '-')),
            'today_view': item.get('today_view', item.get('current_position', '-')),
            'next_focus': item.get('next_focus', item.get('focus_text', '-')),
            'review_hint': item.get('review_hint', '-'),
        })
    current_item = _build_current_target_review_item(current_plan)
    if current_item:
        items.append(current_item)
    final_items = items[:limit]
    for item in final_items:
        item['system_fix'] = _derive_target_review_system_fix(item)
    return final_items


def _classify_strategy_record_attribution(record, as_of_date):
    action_type = record.get('action_type', 'no_trade')
    sim = record.get('simulation', {}) or {}
    path_metrics = _collect_record_market_path(record, as_of_date)
    observed_return = path_metrics.get('observed_return')
    benchmark_return = _safe_float(sim.get('benchmark_return'))
    anchor_alpha = (observed_return - benchmark_return) if observed_return is not None else None

    attribution = {
        'category': 'unclassified',
        'label': '待归因',
        'reason': '记录不够，暂无法归因',
        'observed_stock_return': observed_return,
        'anchor_alpha': anchor_alpha,
        'max_runup': path_metrics.get('max_runup'),
        'max_drawdown': path_metrics.get('max_drawdown'),
        'post_exit_extension': path_metrics.get('post_exit_extension'),
    }
    market_energy_state = record.get('market_energy_state', '')
    record_mainline_name = str(record.get('mainline_name', '') or '').strip()

    if action_type in ('watch_only', 'no_trade'):
        selection_snapshot = (record.get('factor_snapshot', {}) or {}).get('selection', {}) or {}
        feedback_ready = bool(record.get('candidate_feedback_ready') or selection_snapshot.get('candidate_feedback_ready'))
        participation_mode = str(record.get('participation_mode', '') or selection_snapshot.get('participation_mode', '') or '').strip()
        anchor_type = str(record.get('anchor_type', '') or '').strip()
        contract_kind = str(record.get('contract_kind', '') or selection_snapshot.get('contract_kind', '') or '').strip()
        contract_right_side_trigger_price = _round_or_none(record.get('contract_right_side_trigger_price') or selection_snapshot.get('contract_right_side_trigger_price'))
        contract_reset_breakout_price = _round_or_none(record.get('contract_reset_breakout_price') or selection_snapshot.get('contract_reset_breakout_price'))
        contract_void_price = _round_or_none(record.get('contract_void_price') or selection_snapshot.get('contract_void_price'))
        max_drawdown = path_metrics.get('max_drawdown')
        weak_to_strong_context = _build_weak_to_strong_context(
            candidate={
                'name': record.get('stock_name', ''),
                'code': record.get('stock_code', ''),
                'sector': record.get('stock_sector', ''),
                'abnormal_follow_state': record.get('abnormal_follow_state', ''),
                'abnormal_setup_signal_id': record.get('abnormal_setup_signal_id', ''),
            },
            mainline_name=record_mainline_name,
            state_machine_snapshot={
                'leading_line': record_mainline_name,
                'energy_state': market_energy_state,
                'pulse_stage': record.get('mainline_pulse_stage', ''),
            },
        )
        if (
            weak_to_strong_context.get('active')
            and participation_mode == 'observe_0'
            and observed_return is not None
            and observed_return >= 0.06
            and (anchor_alpha is not None and anchor_alpha > 0.02)
            and (path_metrics.get('max_runup') is None or path_metrics.get('max_runup') >= 0.08)
            and (max_drawdown is None or max_drawdown >= -0.05)
        ):
            attribution.update({
                'category': 'weak_to_strong_missed',
                'label': '弱转强识别偏慢',
                'reason': '主线内强基底假弱样本后续已经走成超预期转强，说明它原本是假弱非真弱，但系统仍停在观察层，弱转强识别偏慢。',
            })
        elif (
            contract_kind == 'gem_breathing_20cm'
            and participation_mode == 'observe_0'
            and observed_return is not None
            and observed_return >= 0.03
            and (anchor_alpha is not None and anchor_alpha > 0.015)
            and (path_metrics.get('max_runup') is None or path_metrics.get('max_runup') >= 0.05)
            and (max_drawdown is None or max_drawdown >= -0.05)
        ):
            breakout_text = f"重新站上{contract_reset_breakout_price:.2f}再突破位" if contract_reset_breakout_price is not None else '走成右侧确认/再突破'
            guard_text = f"且始终没失守{contract_void_price:.2f}观察边界" if contract_void_price is not None else ''
            trigger_text = f"右侧确认位{contract_right_side_trigger_price:.2f}" if contract_right_side_trigger_price is not None else '右侧确认'
            attribution.update({
                'category': 'gem_prep_upgrade_lag',
                'label': '20cm右侧确认偏慢',
                'reason': f'创业板20cm预启动样本已经{breakout_text}{guard_text}，但系统仍停在观察层，说明{trigger_text}后的升级偏慢。',
            })
        elif (
            anchor_type in ('受限观察对象', '明天唯一能买的那只', '主线异常先看谁')
            and feedback_ready
            and participation_mode == 'observe_0'
            and observed_return is not None
            and observed_return >= 0.03
            and (anchor_alpha is not None and anchor_alpha > 0.02)
            and (path_metrics.get('max_runup') is None or path_metrics.get('max_runup') >= 0.08)
            and (max_drawdown is None or max_drawdown >= -0.05)
        ):
            attribution.update({
                'category': 'entry_cycle_lag',
                'label': '介入周期偏慢',
                'reason': '唯一对象已经在次日给出确认成功的价格行为，但系统仍停在观察层，说明介入周期判断偏慢。',
            })
        elif feedback_ready and participation_mode == 'observe_0' and observed_return is not None and observed_return >= 0.08:
            attribution.update({
                'category': 'special_probe_lag',
                'label': '特殊探针已先行但仍停在观察层',
                'reason': '特殊标的反馈已经明显走强，但系统仍停在0%观察层，说明探针到执行层的切换偏慢。',
            })
        elif (
            observed_return is not None
            and observed_return >= 0.08
            and benchmark_return >= 0.03
            and market_energy_state in ('收缩防守', '试探修复')
        ):
            attribution.update({
                'category': 'state_misread',
                'label': '状态判断偏差',
                'reason': '后续市场进入明显扩张，但报告日仍按收缩/观察处理，说明对状态变化反应偏慢。',
            })
        elif observed_return is not None and observed_return >= 0.05 and benchmark_return >= 0.015:
            attribution.update({
                'category': 'env_too_strict',
                'label': '环境过滤过严',
                'reason': '系统没有出手，但重点观察谁与指数同步走强，说明环境过滤偏严。',
            })
        elif observed_return is not None and observed_return >= 0.05:
            attribution.update({
                'category': 'stock_right_env_blocked',
                'label': '个股对了但环境不放行',
                'reason': '重点观察谁本身走强，但环境过滤还没放行，属于少赚不是做错。',
            })
        elif benchmark_return <= 0 or (anchor_alpha is not None and anchor_alpha <= 0.02):
            attribution.update({
                'category': 'defense_correct',
                'label': '防守正确',
                'reason': '不交易没有明显吃亏，避免了逆势或低质量出手。',
            })
        else:
            attribution.update({
                'category': 'wait_and_see',
                'label': '继续等待',
                'reason': '观察对象没有形成足够强的相对优势，继续等待并不吃亏。',
            })
        return attribution

    if sim.get('status') in ('invalid_report_day_one_word', 'invalid_consecutive_one_word', 'continuation_only'):
        attribution.update({
            'category': 'tradability_invalid',
            'label': '可交易性无效',
            'reason': '一字链条或延续持有只计观察，不计新增执行质量。',
        })
        return attribution

    if not sim.get('triggered'):
        if path_metrics.get('max_runup') is not None and path_metrics.get('max_runup') >= 0.08:
            attribution.update({
                'category': 'trigger_too_strict',
                'label': '触发条件过严',
                'reason': '计划没有成交，但后续仍给出较大上冲，说明触发门槛偏紧。',
            })
        else:
            attribution.update({
                'category': 'signal_not_triggered',
                'label': '信号未触发',
                'reason': '计划冻结正确，但盘中没有真正给到执行条件。',
            })
        return attribution

    midpoint_return = (
        _safe_float(sim.get('strategy_return_worst')) + _safe_float(sim.get('strategy_return_best'))
    ) / 2.0
    midpoint_alpha = (
        _safe_float(sim.get('alpha_return_worst')) + _safe_float(sim.get('alpha_return_best'))
    ) / 2.0
    exit_reason = sim.get('exit_reason', '')
    stock_sector = record.get('stock_sector', '')
    mainline_name = record.get('mainline_name', '')

    if (
        action_type == 'execute'
        and midpoint_alpha <= -0.05
        and benchmark_return <= 0
        and exit_reason in ('stop_loss', 'day5_close', 'mark_to_market')
        and market_energy_state in ('扩张聚焦', '迁移竞争', '试探修复')
    ):
        attribution.update({
            'category': 'state_misread',
            'label': '状态判断偏差',
            'reason': '报告日把环境理解得偏乐观，后续市场实际进入收缩，属于状态层判断过早进攻。',
        })
        return attribution

    if exit_reason == 'stop_loss':
        if (path_metrics.get('post_exit_extension') or 0.0) >= 0.05:
            attribution.update({
                'category': 'stop_then_rebound',
                'label': '止损正确但踏空',
                'reason': '先按纪律止损，后续价格又明显反抽，属于防守没错但有踏空。',
            })
        else:
            attribution.update({
                'category': 'cut_loss_correct',
                'label': '错了就跑',
                'reason': '执行后不及预期，按照防守纪律快速离场是正确动作。',
            })
        return attribution

    if exit_reason == 'active_sell_big_yang':
        if (path_metrics.get('post_exit_extension') or 0.0) >= 0.05:
            attribution.update({
                'category': 'profit_take_early',
                'label': '赚了但卖早',
                'reason': '主动兑现没有错，但卖出后还有明显延伸空间。',
            })
        else:
            attribution.update({
                'category': 'profit_take_correct',
                'label': '赚了主动卖',
                'reason': '盈利兑现与模式一致，收益兑现没有拖泥带水。',
            })
        return attribution

    if exit_reason in ('day3_close', 'day4_close', 'day5_close', 'mark_to_market') and (path_metrics.get('post_exit_extension') or 0.0) >= 0.08:
        attribution.update({
            'category': 'exit_cycle_too_early',
            'label': '退出周期过早结束',
            'reason': '这笔交易在固定日历退出后仍出现明显延伸，说明退出周期没有给横住续命/再突破重置留空间。',
        })
        return attribution

    if midpoint_alpha < -0.02:
        if stock_sector and mainline_name and not sector_name_matches(stock_sector, mainline_name):
            attribution.update({
                'category': 'mainline_bias',
                'label': '主线判断偏差',
                'reason': '执行对象没有贴住主线，导致出手质量明显弱于环境。',
            })
        else:
            attribution.update({
                'category': 'wrong_trade',
                'label': '做了但根本不该做',
                'reason': '执行后没有跑赢环境，说明这笔交易本身质量不够。',
            })
        return attribution

    if midpoint_alpha > 0:
        if (path_metrics.get('post_exit_extension') or 0.0) >= 0.05:
            attribution.update({
                'category': 'profit_take_early',
                'label': '赚了但卖早',
                'reason': '整体交易是赚钱的，但退出节奏仍可以更耐心。',
            })
        else:
            attribution.update({
                'category': 'execution_valid',
                'label': '执行有效',
                'reason': '执行结果跑赢环境，说明计划和执行都基本有效。',
            })
        return attribution

    attribution.update({
        'category': 'execution_flat',
        'label': '执行一般',
        'reason': '交易没有明显犯错，但也没有形成足够超额。',
    })
    return attribution


def _summarize_strategy_attribution(records, start_date, end_date):
    scoped = [
        record for record in (records or [])
        if start_date <= _normalize_kline_date_str(record.get('report_date')) <= end_date
    ]

    grouped = {}
    highlights = []
    for record in scoped:
        attribution = record.get('attribution', {}) or {}
        label = attribution.get('label', '待归因')
        group = grouped.setdefault(label, {
            'label': label,
            'count': 0,
            'sample': '',
            'reason': attribution.get('reason', ''),
        })
        group['count'] += 1
        if not group.get('sample'):
            sample_name = record.get('stock_name') or record.get('anchor_type') or '无标的'
            if record.get('stock_code'):
                sample_name = f"{sample_name}({record.get('stock_code')})"
            group['sample'] = f"{record.get('report_date')} {sample_name}"
        if attribution.get('category') not in ('defense_correct', 'wait_and_see') and len(highlights) < 3:
            sample_name = record.get('stock_name') or record.get('anchor_type') or '无标的'
            if record.get('stock_code'):
                sample_name = f"{sample_name}({record.get('stock_code')})"
            highlights.append({
                'date': record.get('report_date', ''),
                'label': label,
                'stock': sample_name,
                'reason': attribution.get('reason', ''),
            })

    items = sorted(grouped.values(), key=lambda x: (x.get('count', 0), x.get('label', '')), reverse=True)
    return {
        'start_date': start_date,
        'end_date': end_date,
        'total_count': len(scoped),
        'items': items,
        'highlights': highlights,
    }


def _summarize_setup_signal_review(records, start_date, end_date):
    scoped = [
        record for record in (records or [])
        if start_date <= _normalize_kline_date_str(record.get('report_date')) <= end_date
    ]

    grouped = {}
    for record in scoped:
        setup_id = str(record.get('abnormal_setup_signal_id', '') or '').strip()
        setup_label = str(record.get('abnormal_setup_signal_label', '') or '').strip()
        if not setup_id and not setup_label:
            continue

        item = grouped.setdefault(setup_id or setup_label, {
            'setup_id': setup_id or setup_label,
            'setup_label': setup_label or setup_id,
            'plan_count': 0,
            'execute_count': 0,
            'sample_count': 0,
            'strong_count': 0,
            'relative_win_count': 0,
            'return_sum': 0.0,
            'alpha_sum': 0.0,
        })
        item['plan_count'] += 1
        if record.get('action_type') == 'execute':
            item['execute_count'] += 1

        attribution = record.get('attribution', {}) or {}
        observed_return = attribution.get('observed_stock_return')
        anchor_alpha = attribution.get('anchor_alpha')
        if observed_return is None and anchor_alpha is None:
            continue

        item['sample_count'] += 1
        item['return_sum'] += _safe_float(observed_return)
        item['alpha_sum'] += _safe_float(anchor_alpha)
        if observed_return is not None and observed_return >= 0.05:
            item['strong_count'] += 1
        if anchor_alpha is not None and anchor_alpha > 0.02:
            item['relative_win_count'] += 1

    items = []
    for item in grouped.values():
        sample_count = item.get('sample_count', 0)
        items.append({
            **item,
            'strong_rate': (item.get('strong_count', 0) / sample_count) if sample_count > 0 else None,
            'relative_win_rate': (item.get('relative_win_count', 0) / sample_count) if sample_count > 0 else None,
            'avg_return': (item.get('return_sum', 0.0) / sample_count) if sample_count > 0 else None,
            'avg_alpha': (item.get('alpha_sum', 0.0) / sample_count) if sample_count > 0 else None,
        })

    items.sort(
        key=lambda x: (
            x.get('sample_count', 0),
            _safe_float(x.get('avg_alpha')),
            _safe_float(x.get('relative_win_rate')),
        ),
        reverse=True,
    )
    return {
        'start_date': start_date,
        'end_date': end_date,
        'total_plan_count': len(scoped),
        'items': items,
    }


def _extract_gem_breathing_contract_snapshot(record):
    record = record or {}
    selection_snapshot = (record.get('factor_snapshot', {}) or {}).get('selection', {}) or {}
    contract_kind = str(record.get('contract_kind', '') or selection_snapshot.get('contract_kind', '') or '').strip()
    if contract_kind != 'gem_breathing_20cm':
        return {}

    active_window_days = int(_safe_float(record.get('contract_active_window_days') or selection_snapshot.get('contract_active_window_days') or 0))
    participation_mode = str(record.get('participation_mode', '') or selection_snapshot.get('participation_mode', '') or '').strip()
    target_position_pct = int(_safe_float(record.get('target_position_pct') or selection_snapshot.get('target_position_pct') or 0))
    stock_code = normalize_stock_code(record.get('stock_code', ''))
    stock_name = str(record.get('stock_name') or record.get('anchor_type') or '无标的').strip()

    return {
        'contract_kind': contract_kind,
        'report_date': _normalize_kline_date_str(record.get('report_date')),
        'stock_code': stock_code,
        'stock_name': stock_name,
        'sample_label': f'{stock_name}({stock_code})' if stock_code else stock_name,
        'active_window_days': active_window_days or 5,
        'right_side_trigger_price': _round_or_none(record.get('contract_right_side_trigger_price') or selection_snapshot.get('contract_right_side_trigger_price')),
        'void_price': _round_or_none(record.get('contract_void_price') or selection_snapshot.get('contract_void_price')),
        'reset_breakout_price': _round_or_none(record.get('contract_reset_breakout_price') or selection_snapshot.get('contract_reset_breakout_price')),
        'upgrade_condition_text': str(record.get('contract_upgrade_condition_text', '') or selection_snapshot.get('contract_upgrade_condition_text', '') or '').strip(),
        'participation_mode': participation_mode,
        'target_position_pct': target_position_pct,
        'action_type': str(record.get('action_type', '') or '').strip(),
        'attribution_label': str((record.get('attribution', {}) or {}).get('label', '') or '').strip(),
    }


def _classify_gem_breathing_week_sample(record, as_of_date):
    snapshot = _extract_gem_breathing_contract_snapshot(record)
    if not snapshot:
        return {}

    report_date = snapshot.get('report_date')
    stock_code = snapshot.get('stock_code')
    sample_label = snapshot.get('sample_label')
    if not report_date or not stock_code or not as_of_date:
        return {}

    tracking_days = _count_trading_days_between(report_date, as_of_date)
    bars = fetch_daily_price_bars(stock_code, report_date, as_of_date, is_index=False)
    bars = [
        bar for bar in (bars or [])
        if report_date <= _normalize_kline_date_str(bar.get('date')) <= as_of_date
    ]
    if not bars:
        return {}

    latest_bar = _get_last_bar_on_or_before(bars, as_of_date) or bars[-1]
    latest_close = _safe_float(latest_bar.get('close'))
    latest_high = max(_safe_float(bar.get('high')) for bar in bars if _safe_float(bar.get('high')) > 0)
    latest_low = min(_safe_float(bar.get('low')) for bar in bars if _safe_float(bar.get('low')) > 0)

    trigger_price = snapshot.get('right_side_trigger_price')
    void_price = snapshot.get('void_price')
    reset_breakout_price = snapshot.get('reset_breakout_price')
    active_window_days = snapshot.get('active_window_days', 5)
    participation_mode = snapshot.get('participation_mode', '')
    target_position_pct = snapshot.get('target_position_pct', 0)
    action_type = snapshot.get('action_type', '')
    attribution_label = snapshot.get('attribution_label', '')

    right_side_confirmation = bool(
        trigger_price is not None
        and trigger_price > 0
        and (latest_high >= trigger_price or latest_close >= trigger_price)
    )
    rebreak_success = bool(
        reset_breakout_price is not None
        and reset_breakout_price > 0
        and (latest_high >= reset_breakout_price or latest_close >= reset_breakout_price)
    )
    voided = bool(
        void_price is not None
        and void_price > 0
        and (latest_low < void_price or latest_close < void_price)
    )
    conditional_upgrade = bool(
        target_position_pct >= 30
        or participation_mode == 'conditional_30'
        or (action_type == 'execute' and target_position_pct > 0)
    )
    upgrade_lag = bool(
        not conditional_upgrade
        and not voided
        and (
            attribution_label == '20cm右侧确认偏慢'
            or (participation_mode == 'observe_0' and rebreak_success)
        )
    )
    expired = bool(
        not conditional_upgrade
        and not voided
        and not upgrade_lag
        and tracking_days > active_window_days
    )
    active_observation = bool(
        not conditional_upgrade
        and not voided
        and not expired
        and not upgrade_lag
    )

    price_map_parts = []
    if trigger_price is not None:
        price_map_parts.append(f'trigger {trigger_price:.2f}')
    if void_price is not None:
        price_map_parts.append(f'void {void_price:.2f}')
    if reset_breakout_price is not None:
        price_map_parts.append(f'reset {reset_breakout_price:.2f}')
    price_map = ' / '.join(price_map_parts) if price_map_parts else '-'

    if conditional_upgrade:
        status_label = '已升级到30%条件试错'
        note = '这条20cm合同已经进入30%条件试错，不再只是纯观察样本。'
    elif voided:
        status_label = '窗口内失守作废'
        note = f'盘中跌破{void_price:.2f}作废价，合同应按失效处理。' if void_price is not None else '合同已经失效。'
    elif upgrade_lag:
        status_label = '再突破成功但升级偏慢'
        note = (
            f'已重新站上{reset_breakout_price:.2f}再突破位，但系统仍停在观察层。'
            if reset_breakout_price is not None
            else '价格已经走成右侧确认，但系统仍停在观察层。'
        )
    elif expired:
        status_label = '窗口到期自然作废'
        note = f'{active_window_days}日观察窗口到期仍未确认，不应继续维持高优先级跟踪。'
    elif rebreak_success:
        status_label = '已走成再突破'
        note = f'已经重新站上{reset_breakout_price:.2f}再突破位，后续只差升级动作。' if reset_breakout_price is not None else '已经走成再突破。'
    elif right_side_confirmation:
        status_label = '已触发右侧确认'
        note = f'已经摸到{trigger_price:.2f}右侧确认位，进入升级观察。' if trigger_price is not None else '已经触发右侧确认。'
    elif active_observation:
        status_label = '仍在观察窗口'
        note = f'仍在{active_window_days}日合同窗口内，先看右侧确认是否出现。'
    else:
        status_label = '记录待补全'
        note = '合同字段已存在，但当前样本还缺少足够后验数据。'

    return {
        **snapshot,
        'tracking_days': tracking_days,
        'latest_close': _round_or_none(latest_close),
        'right_side_confirmation': right_side_confirmation,
        'rebreak_success': rebreak_success,
        'voided': voided,
        'conditional_upgrade': conditional_upgrade,
        'upgrade_lag': upgrade_lag,
        'expired': expired,
        'active_observation': active_observation,
        'status_label': status_label,
        'price_map': price_map,
        'note': note,
        'sample_line': f"{report_date} {sample_label}：{note}",
    }


def _summarize_gem_breathing_week_review(records, start_date, end_date):
    scoped = []
    for record in (records or []):
        report_date = _normalize_kline_date_str(record.get('report_date'))
        if not (start_date <= report_date <= end_date):
            continue
        if _extract_gem_breathing_contract_snapshot(record):
            scoped.append(record)

    items = []
    for record in scoped:
        item = _classify_gem_breathing_week_sample(record, end_date)
        if item:
            items.append(item)

    items.sort(
        key=lambda x: (
            x.get('conditional_upgrade', False),
            x.get('upgrade_lag', False),
            x.get('rebreak_success', False),
            x.get('right_side_confirmation', False),
            x.get('report_date', ''),
        ),
        reverse=True,
    )

    return {
        'start_date': start_date,
        'end_date': end_date,
        'sample_count': len(items),
        'right_side_confirmation_count': sum(1 for item in items if item.get('right_side_confirmation')),
        'rebreak_success_count': sum(1 for item in items if item.get('rebreak_success')),
        'conditional_upgrade_count': sum(1 for item in items if item.get('conditional_upgrade')),
        'voided_count': sum(1 for item in items if item.get('voided')),
        'expired_count': sum(1 for item in items if item.get('expired')),
        'upgrade_lag_count': sum(1 for item in items if item.get('upgrade_lag')),
        'active_observation_count': sum(1 for item in items if item.get('active_observation')),
        'upgrade_lag_samples': [item.get('sample_line') for item in items if item.get('upgrade_lag')],
        'voided_samples': [item.get('sample_line') for item in items if item.get('voided')],
        'expired_samples': [item.get('sample_line') for item in items if item.get('expired')],
        'items': items,
    }


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
    windows = windows or []
    attribution_summary = attribution_summary or {}
    setup_summary = setup_summary or {}
    ev_summary = ev_summary or {}
    gem_week_review = gem_week_review or {}

    label_counts = {
        item.get('label', ''): int(item.get('count', 0))
        for item in (attribution_summary.get('items', []) or [])
    }
    total_count = int(attribution_summary.get('total_count', 0) or 0)
    gate_too_strict = (
        label_counts.get('环境过滤过严', 0)
        + label_counts.get('个股对了但环境不放行', 0)
        + label_counts.get('介入周期偏慢', 0)
    )
    weak_to_strong_lag = label_counts.get('弱转强识别偏慢', 0)
    gem_upgrade_lag = label_counts.get('20cm右侧确认偏慢', 0)
    gem_week_sample_count = int(_safe_float(gem_week_review.get('sample_count', 0)))
    gem_week_upgrade_count = int(_safe_float(gem_week_review.get('conditional_upgrade_count', 0)))
    gem_week_upgrade_lag = int(_safe_float(gem_week_review.get('upgrade_lag_count', 0)))
    gem_week_voided = int(_safe_float(gem_week_review.get('voided_count', 0)))
    gem_week_expired = int(_safe_float(gem_week_review.get('expired_count', 0)))
    state_misread = label_counts.get('状态判断偏差', 0)
    trigger_too_strict = label_counts.get('触发条件过严', 0)
    selection_bias = label_counts.get('主线判断偏差', 0) + label_counts.get('做了但根本不该做', 0)
    exit_too_early = label_counts.get('赚了但卖早', 0) + label_counts.get('退出周期过早结束', 0)
    stop_rebound = label_counts.get('止损正确但踏空', 0)
    defense_correct = label_counts.get('防守正确', 0)

    week_window = None
    month_window = None
    cycle_window = None
    for item in windows:
        if item.get('name') == '本周':
            week_window = item
        elif item.get('name') == '本月':
            month_window = item
        elif item.get('name') == '本次结构周期':
            cycle_window = item

    suggestions = []

    if gate_too_strict >= 2 or (total_count > 0 and gate_too_strict / max(total_count, 1) >= 0.4):
        suggestions.append({
            'area': '环境过滤',
            'bias': '偏严',
            'why': '多次出现“环境过滤过严 / 个股对了但环境不放行 / 介入周期偏慢”，说明当前环境过滤与介入升级都挡掉了部分有效观察对象。',
            'action': '先不要直接放开买入权限，而是在二档下保留更明确的高优先级重点观察谁；对已经给出次日确认成功的唯一对象，要单独复盘介入周期是否偏慢。',
        })
    elif defense_correct >= max(2, gate_too_strict):
        suggestions.append({
            'area': '环境过滤',
            'bias': '有效',
            'why': '近期“防守正确”占优，说明市场过滤本身没有明显失真。',
            'action': '环境过滤先维持，不因为少赚就强行放松；优先继续积累记录。',
        })

    if weak_to_strong_lag >= 1:
        suggestions.append({
            'area': '弱转强识别',
            'bias': '偏慢',
            'why': '已经出现“弱转强识别偏慢”，说明主线内强基底假弱样本后续走成超预期转强时，系统还停在观察层。',
            'action': '以后对强基底+假弱非真弱+主线共振未坏的对象，要单独复盘从观察权到执行评估的升级时点，不要等它完全走出来才承认弱转强。',
        })

    gem_chain_bias_count = max(gem_upgrade_lag, gem_week_upgrade_lag)
    if gem_chain_bias_count >= 1 or (gem_week_sample_count >= 3 and gem_week_upgrade_count <= 1):
        why_parts = []
        action_parts = []
        if gem_week_sample_count > 0:
            why_parts.append(
                f"本周{gem_week_sample_count}只创业板20cm合同样本里，升级到30%只有{gem_week_upgrade_count}只，"
                f"窗口内作废{gem_week_voided}只，窗口到期{gem_week_expired}只。"
            )
        if gem_chain_bias_count >= 1:
            why_parts.append(
                f"已经出现{gem_chain_bias_count}只“20cm右侧确认偏慢”，说明创业板20cm预启动样本在走成右侧确认/再突破后，系统仍停在观察层。"
            )
            action_parts.append(
                f"优先回放升级偏慢{gem_chain_bias_count}只样本，逐个检查右侧确认位、再突破位与30%条件试错之间的升级链，不要长期停在只观察。"
            )
        else:
            action_parts.append('继续盯住右侧确认位到30%条件试错之间的升级链，避免20cm样本长期堆在观察层。')
        if gem_week_voided >= gem_week_upgrade_count and gem_week_voided > 0:
            action_parts.append('同时复盘作废价是否过松或对象本身边界不清，避免把不该留在高优先级观察里的20cm样本拖太久。')
        if gem_week_expired > 0:
            action_parts.append('对窗口到期仍未确认的20cm合同，要及时降权，不再占用高优先级注意力。')
        suggestions.append({
            'area': '创业板20cm升级链',
            'bias': '偏慢',
            'why': ''.join(why_parts) or '创业板20cm升级链仍偏慢。',
            'action': ''.join(action_parts) or '继续复盘创业板20cm从观察到30%条件试错的升级链。',
        })

    if state_misread >= 1:
        suggestions.append({
            'area': '状态层判断',
            'bias': '偏慢/偏早',
            'why': '已经出现“状态判断偏差”，说明系统在扩张与收缩切换时，仍有节奏判断失真的情况。',
            'action': '优先复盘“市场能量状态”和“异常投影”是否同步，再决定是放松还是收紧执行层。',
        })

    if trigger_too_strict >= 1:
        suggestions.append({
            'area': '触发条件',
            'bias': '偏紧',
            'why': '计划没成交，但后续仍给出明显上冲，说明60分钟确认或入场区间可能抬得过高。',
            'action': '接下来重点复盘确认价和回踩区的距离，不动环境过滤，先优化触发层。',
        })

    if selection_bias >= 1:
        suggestions.append({
            'area': '主线/选股',
            'bias': '有偏',
            'why': '出现“主线判断偏差 / 做了但根本不该做”，说明出手对象和市场主线贴合度不够。',
            'action': '继续收紧“看大做小”的约束，只给主线内最强和有记忆资产的标的执行权。',
        })

    if exit_too_early >= 1 or stop_rebound >= 1:
        suggestions.append({
            'area': '退出节奏',
            'bias': '可优化',
            'why': '最近有“赚了但卖早 / 止损正确但踏空”记录，说明纪律没错，但退出后的二次观察还能更细。',
            'action': '保留原有止损纪律不放松，同时在日报里继续跟踪“止损后是否快速收复 / 卖出后是否继续加速”。',
        })

    if not suggestions:
        suggestions.append({
            'area': '系统状态',
            'bias': '学习期',
            'why': '当前记录仍少，系统还没有足够证据对参数做大动作。',
            'action': '先继续冻结计划和归因，不急着大改规则。',
        })

    setup_items = setup_summary.get('items', []) or []
    top_setup = setup_items[0] if setup_items else {}
    weak_setup = setup_items[-1] if len(setup_items) >= 2 else {}

    overview_parts = []
    if week_window:
        overview_parts.append(
            f"本周超额{_format_pct_range(week_window.get('alpha_return_worst'), week_window.get('alpha_return_best'))}"
        )
    if month_window:
        overview_parts.append(
            f"本月超额{_format_pct_range(month_window.get('alpha_return_worst'), month_window.get('alpha_return_best'))}"
        )
    if cycle_window:
        overview_parts.append(
            f"结构周期超额{_format_pct_range(cycle_window.get('alpha_return_worst'), cycle_window.get('alpha_return_best'))}"
        )

    setup_comment = ""
    if top_setup and top_setup.get('sample_count', 0) > 0:
        setup_comment = (
            f"当前最值得继续观察的固定 setup 是 {top_setup.get('setup_label')}，"
            f"记录{top_setup.get('sample_count', 0)}笔，平均相对超额{_format_pct(top_setup.get('avg_alpha'))}。"
        )
    elif weak_setup and weak_setup.get('sample_count', 0) > 0:
        setup_comment = (
            f"当前最弱的固定 setup 是 {weak_setup.get('setup_label')}，"
            f"记录{weak_setup.get('sample_count', 0)}笔，平均相对超额{_format_pct(weak_setup.get('avg_alpha'))}。"
        )

    ev_items = ev_summary.get('items', []) or []
    ev_comment = ""
    if ev_items:
        best_ev_item = max(
            ev_items,
            key=lambda x: (
                _safe_float(x.get('avg_alpha'), -99.0),
                _safe_float(x.get('hit_rate'), -99.0),
            ),
        )
        if best_ev_item.get('sample_count', 0) > 0:
            ev_comment = (
                f"EV 侧当前更稳的是 {best_ev_item.get('signal_label')}，"
                f"平均超额{_format_pct(best_ev_item.get('avg_alpha'))}。"
            )

    return {
        'start_date': start_date,
        'end_date': end_date,
        'overview': "；".join([part for part in overview_parts if part]) or "暂无足够窗口记录。",
        'setup_comment': setup_comment,
        'ev_comment': ev_comment,
        'suggestions': suggestions,
    }


def _apply_yizi_chain_rules(records):
    prev_execute_record = None
    for record in sorted(records or [], key=lambda x: _normalize_kline_date_str(x.get('report_date'))):
        if record.get('action_type') != 'execute':
            continue

        sim = record.get('simulation', {}) or {}
        report_day_is_one_word = bool(record.get('report_day_is_one_word'))
        same_stock_chain = (
            prev_execute_record
            and normalize_stock_code(prev_execute_record.get('stock_code')) == normalize_stock_code(record.get('stock_code'))
            and _is_next_trading_day(prev_execute_record.get('report_date'), record.get('report_date'))
        )
        prev_chain_valid = bool(prev_execute_record.get('chain_entry_valid')) if prev_execute_record else False
        prev_day_one_word = bool(prev_execute_record.get('report_day_is_one_word')) if prev_execute_record else False

        if report_day_is_one_word:
            if same_stock_chain and prev_chain_valid and not prev_day_one_word:
                sim['status'] = 'continuation_only'
                sim['status_note'] = '昨日已是同一有效链，今天一字只计延续不计新开仓'
                sim['status_label'] = _get_strategy_status_label(sim['status'], sim['status_note'])
                sim['triggered'] = False
                sim['confirm_triggered'] = False
                sim['entry_price_best'] = None
                sim['entry_price_worst'] = None
                sim['strategy_return_best'] = 0.0
                sim['strategy_return_worst'] = 0.0
                sim['benchmark_return'] = 0.0
                sim['alpha_return_best'] = 0.0
                sim['alpha_return_worst'] = 0.0
                record['chain_entry_valid'] = True
            else:
                sim['status'] = 'invalid_consecutive_one_word' if same_stock_chain and prev_day_one_word else 'invalid_report_day_one_word'
                sim['status_note'] = '当日一字板，次日默认买不进去；连续一字链条不计收益'
                sim['status_label'] = _get_strategy_status_label(sim['status'], sim['status_note'])
                sim['triggered'] = False
                sim['confirm_triggered'] = False
                sim['entry_price_best'] = None
                sim['entry_price_worst'] = None
                sim['strategy_return_best'] = 0.0
                sim['strategy_return_worst'] = 0.0
                sim['benchmark_return'] = 0.0
                sim['alpha_return_best'] = 0.0
                sim['alpha_return_worst'] = 0.0
                record['chain_entry_valid'] = False
        else:
            record['chain_entry_valid'] = bool(sim.get('triggered'))
            sim['status_label'] = _get_strategy_status_label(sim.get('status'), sim.get('status_note', ''))

        record['simulation'] = sim
        prev_execute_record = record


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
    indices = data.get('indices', {}) or {}
    sh_index = indices.get('上证指数', {}) or {}
    current_zhongshu = market_zhongshu.get('current_zhongshu', {}) if market_zhongshu else {}
    latest_structure_segment = market_zhongshu.get('latest_structure_segment', {}) if market_zhongshu else {}
    selection_snapshot = (factor_snapshot or {}).get('selection', {}) or {}
    target_position_pct = int(_safe_float(selection_snapshot.get('target_position_pct', 0)))
    participation_mode = str(selection_snapshot.get('participation_mode', '') or 'observe_0').strip()
    candidate_feedback_ready = bool(selection_snapshot.get('candidate_feedback_ready'))
    plan_contract_kind = str(selection_snapshot.get('contract_kind', '') or '').strip()
    plan_contract_active_window_days = int(_safe_float(selection_snapshot.get('contract_active_window_days', 0)))
    plan_contract_right_side_trigger_price = _round_or_none(selection_snapshot.get('contract_right_side_trigger_price'))
    plan_contract_void_price = _round_or_none(selection_snapshot.get('contract_void_price'))
    plan_contract_reset_breakout_price = _round_or_none(selection_snapshot.get('contract_reset_breakout_price'))
    plan_contract_upgrade_condition_text = str(selection_snapshot.get('contract_upgrade_condition_text', '') or '').strip()

    action_type = 'no_trade'
    plan_stock = None
    anchor_type = ''
    if target_position_pct >= 50 and best_stock:
        action_type = 'execute'
        plan_stock = best_stock
        anchor_type = '明天唯一能买的那只'
    elif target_position_pct == 30 and (best_stock or watch_anchor):
        action_type = 'execute'
        plan_stock = best_stock or watch_anchor
        anchor_type = '30%条件试错仓'
    elif best_stock:
        action_type = 'watch_only'
        plan_stock = best_stock
        anchor_type = '受限观察对象'
    elif watch_anchor:
        action_type = 'watch_only'
        plan_stock = watch_anchor
        anchor_type = watch_anchor_type or '重点观察谁'

    minute_plan = plan_stock.get('minute_plan') if plan_stock else {}
    stop_plan = plan_stock.get('stop_plan') if plan_stock else {}
    signal = plan_stock.get('signal') if plan_stock else None
    plan_gem_contract = (plan_stock.get('gem_breathing_contract') if plan_stock else None) or {}
    if not plan_contract_kind and plan_gem_contract:
        plan_contract_kind = str(plan_gem_contract.get('contract_kind', '') or '').strip()
        plan_contract_active_window_days = int(_safe_float(plan_gem_contract.get('active_window_days', 0)))
        plan_contract_right_side_trigger_price = _round_or_none(plan_gem_contract.get('right_side_trigger_price'))
        plan_contract_void_price = _round_or_none(plan_gem_contract.get('void_price'))
        plan_contract_reset_breakout_price = _round_or_none(plan_gem_contract.get('reset_breakout_price'))
        plan_contract_upgrade_condition_text = str(plan_gem_contract.get('upgrade_condition_text', '') or '').strip()
    contract_prices_candidate = dict(plan_stock or {}) if plan_stock else {}
    if contract_prices_candidate:
        contract_prices_candidate['position_pct'] = max(int(_safe_float(contract_prices_candidate.get('position_pct', 0))), target_position_pct)
        contract_prices_candidate['participation_mode'] = participation_mode or contract_prices_candidate.get('participation_mode', '')
        contract_prices_candidate['action_type'] = action_type or contract_prices_candidate.get('action_type', '')
    contract_prices = _resolve_candidate_contract_prices(
        contract_prices_candidate,
        signal=signal,
    ) if plan_stock else {
        'entry_range_low': None,
        'entry_range_high': None,
        'observe_anchor_price': None,
        'upgrade_trigger_price': None,
        'invalidation_price': None,
        'reset_breakout_price': None,
    }
    entry_low = contract_prices.get('entry_range_low')
    entry_high = contract_prices.get('entry_range_high')

    stock_name = plan_stock.get('name', '') if plan_stock else ''
    stock_code = normalize_stock_code(plan_stock.get('code', '')) if plan_stock else ''
    stock_full_info = data.get('stock_full_info', {}) or {}
    quote_info = stock_full_info.get(stock_code, {}) if stock_code else {}
    report_day_open = _round_or_none(
        plan_stock.get('open', quote_info.get('open')) if plan_stock else quote_info.get('open')
    )
    report_day_high = _round_or_none(
        plan_stock.get('high', quote_info.get('high')) if plan_stock else quote_info.get('high')
    )
    report_day_low = _round_or_none(
        plan_stock.get('low', quote_info.get('low')) if plan_stock else quote_info.get('low')
    )
    report_day_close = _round_or_none(
        plan_stock.get('close', quote_info.get('close', quote_info.get('price'))) if plan_stock else quote_info.get('close', quote_info.get('price'))
    )
    report_day_change_pct = _round_or_none(
        plan_stock.get('change', quote_info.get('change_pct')) if plan_stock else quote_info.get('change_pct'),
        4,
    )
    report_day_is_one_word = _is_one_word_limit_bar(
        stock_code=stock_code,
        stock_name=stock_name,
        open_price=report_day_open,
        high_price=report_day_high,
        low_price=report_day_low,
        close_price=report_day_close,
        change_pct=report_day_change_pct,
    ) if stock_code and stock_name else False

    trigger_text = ''
    if action_type == 'execute' and plan_stock:
        confirm_price = _round_or_none(minute_plan.get('confirm_price_60m'))
        if target_position_pct == 30:
            if confirm_price:
                trigger_text = f"30%条件试错：首个60分钟站上{confirm_price:.2f}后再执行"
            else:
                trigger_text = "30%条件试错：先完成60分钟确认后再执行"
        elif confirm_price:
            trigger_text = f"首个60分钟站上{confirm_price:.2f}后，再回到{entry_low:.2f}-{entry_high:.2f}区间内执行"
        elif entry_low is not None and entry_high is not None:
            trigger_text = f"触及{entry_low:.2f}-{entry_high:.2f}并完成60分钟确认"
    elif plan_stock:
        if final_gate.get('can_new_entry') and '候选' in anchor_type:
            confirm_price = _round_or_none(minute_plan.get('confirm_price_60m'))
            if confirm_price:
                trigger_text = f"{anchor_type}，先看首个60分钟站上{confirm_price:.2f}，再判断能否走成明天唯一能买的那只"
            else:
                trigger_text = f"{anchor_type}，先看盘中承接，再判断能否走成明天唯一能买的那只"
        else:
            trigger_text = f"{anchor_type}，仅观察不下单"

    state_machine_snapshot = (factor_snapshot or {}).get('state_machine', {}) or {}
    abnormal_projection = ((factor_snapshot or {}).get('abnormal', {}) or {}).get('projection', {}) or {}
    style_snapshot = (factor_snapshot or {}).get('style', {}) or {}
    price_focus = _build_trade_price_focus(minute_plan, stop_plan)
    exit_rules = _build_candidate_exit_rules(plan_stock, stop_plan) if plan_stock else {
        'holding_days_min': STRATEGY_HOLDING_DAYS_MIN,
        'holding_days_max': STRATEGY_HOLDING_DAYS_MAX,
        'profit_take_pct': 0.05,
        'defensive_exit_rule': DEFENSIVE_EXIT_RULE_TEXT,
        'profit_exit_rule': PROFIT_EXIT_RULE_TEXT,
    }
    action_rule = str(plan_stock.get('action_rule', '') or plan_stock.get('reason', '') or '').strip() if plan_stock else ''
    if action_rule and action_rule not in trigger_text:
        trigger_text = f"{trigger_text}；{action_rule}" if trigger_text else action_rule

    plan_context = {
        'report_date': target_date,
        'action_type': action_type,
        'anchor_type': anchor_type,
        'position_level': position_level,
        'operation_state': final_gate.get('operation_state', ''),
        'gate_status': final_gate.get('gate_status', ''),
        'can_new_entry': bool(final_gate.get('can_new_entry')),
        'gate_reason': final_gate.get('gate_reason', ''),
        'final_action': final_gate.get('final_action', ''),
        'position_reason': position_reason,
        'mainline_name': exit_analysis.get('sector_name', ''),
        'market_energy_state': state_machine_snapshot.get('energy_state', ''),
        'market_flow_direction': state_machine_snapshot.get('flow_direction', ''),
        'market_state_reason': state_machine_snapshot.get('state_reason', ''),
        'mainline_driver_type': state_machine_snapshot.get('driver_type', ''),
        'mainline_pulse_stage': state_machine_snapshot.get('pulse_stage', ''),
        'mainline_acceptance_quality': state_machine_snapshot.get('acceptance_quality', ''),
        'mainline_passivation_risk': state_machine_snapshot.get('passivation_risk', ''),
        'mainline_execution_bias': state_machine_snapshot.get('execution_bias', ''),
        'mainline_pulse_action_bias': state_machine_snapshot.get('pulse_action_bias', ''),
        'mainline_pulse_action_reason': state_machine_snapshot.get('pulse_action_reason', ''),
        'state_reflection_focus': state_machine_snapshot.get('reflection_focus', ''),
        'market_style_label': style_snapshot.get('style_label', ''),
        'market_style_reason': style_snapshot.get('style_reason', ''),
        'market_style_action': style_snapshot.get('primary_action', ''),
        'market_turnover_label': style_snapshot.get('turnover_label', ''),
        'market_signal_type': market_zhongshu.get('signal', {}).get('signal_type', '') if market_zhongshu else '',
        'market_signal_status': market_zhongshu.get('signal', {}).get('status', '') if market_zhongshu else '',
        'structure_cycle_start': current_zhongshu.get('start_date', ''),
        'structure_cycle_anchor_end': current_zhongshu.get('end_date', ''),
        'structure_latest_segment_end': latest_structure_segment.get('end_date', ''),
        'benchmark_report_close': _round_or_none(sh_index.get('close', sh_index.get('price', 0.0)), 4) or 0.0,
        'benchmark_report_change_pct': _round_or_none(sh_index.get('涨跌幅', sh_index.get('change_pct', 0.0)), 4) or 0.0,
        'stock_name': stock_name,
        'stock_code': stock_code,
        'stock_sector': plan_stock.get('sector', '') if plan_stock else '',
        'signal_type': getattr(signal, 'signal_type', '') if signal else (plan_stock.get('signal_type', '') if plan_stock else ''),
        'abnormal_setup_signal_id': plan_stock.get('abnormal_setup_signal_id', plan_stock.get('setup_signal_id', '')) if plan_stock else '',
        'abnormal_setup_signal_label': plan_stock.get('abnormal_setup_signal_label', plan_stock.get('setup_signal_label', '')) if plan_stock else '',
        'abnormal_follow_state': plan_stock.get('abnormal_follow_state', plan_stock.get('follow_state', '')) if plan_stock else '',
        'abnormal_projection_label': abnormal_projection.get('projection_label', ''),
        'permission_label': plan_stock.get('permission_label', '') if plan_stock else '',
        'permission_reason': plan_stock.get('permission_reason', '') if plan_stock else '',
        'ev_model_source': plan_stock.get('ev_model_source', '') if plan_stock else '',
        'ev_sample_size': int(_safe_float(plan_stock.get('ev_sample_size', 0))) if plan_stock else 0,
        'ev_global_sample_size': int(_safe_float(plan_stock.get('ev_global_sample_size', 0))) if plan_stock else 0,
        'ev_confidence': _round_or_none(plan_stock.get('ev_confidence'), 4) if plan_stock else None,
        'report_day_open': report_day_open,
        'report_day_high': report_day_high,
        'report_day_low': report_day_low,
        'report_day_close': report_day_close,
        'report_day_change_pct': report_day_change_pct,
        'report_day_is_one_word': bool(report_day_is_one_word),
        'entry_price_anchor': _round_or_none(plan_stock.get('entry_price', signal.entry_price if signal else 0.0)) if plan_stock else None,
        'entry_range_low': entry_low,
        'entry_range_high': entry_high,
        'observe_anchor_price': contract_prices.get('observe_anchor_price'),
        'upgrade_trigger_price': contract_prices.get('upgrade_trigger_price'),
        'invalidation_price': contract_prices.get('invalidation_price'),
        'reset_breakout_price': contract_prices.get('reset_breakout_price'),
        'confirm_price_60m': _round_or_none(minute_plan.get('confirm_price_60m')),
        'confirm_support_60m': _round_or_none(minute_plan.get('confirm_support_60m')),
        'structure_stop_30m': _round_or_none(minute_plan.get('structure_stop_30m')),
        'anchor_price': _round_or_none(plan_stock.get('anchor_price')) if plan_stock else None,
        'display_anchor_price': _round_or_none(plan_stock.get('display_anchor_price')) if plan_stock else None,
        'key_zone_low': price_focus.get('key_zone_low'),
        'key_zone_high': price_focus.get('key_zone_high'),
        'key_zone_display': price_focus.get('key_zone_display'),
        'execution_stop': price_focus.get('execution_stop'),
        'price_note': price_focus.get('note_text', ''),
        'price_confluence_reasons': list(price_focus.get('confluence_reasons', []) or []),
        'effective_stop': _round_or_none(stop_plan.get('effective_stop') if stop_plan else plan_stock.get('stop_loss') if plan_stock else None),
        'hard_stop': _round_or_none(stop_plan.get('hard_stop') if stop_plan else None),
        'position_pct': target_position_pct if target_position_pct > 0 else 0,
        'participation_mode': participation_mode,
        'candidate_feedback_ready': candidate_feedback_ready,
        'weak_to_strong_upgrade_ready': bool(selection_snapshot.get('weak_to_strong_upgrade_ready')),
        'weak_to_strong_scenario': str(selection_snapshot.get('weak_to_strong_scenario', '') or '').strip(),
        'weak_to_strong_summary': str(selection_snapshot.get('weak_to_strong_summary', '') or '').strip(),
        'contract_kind': plan_contract_kind,
        'contract_active_window_days': plan_contract_active_window_days,
        'contract_right_side_trigger_price': plan_contract_right_side_trigger_price,
        'contract_void_price': plan_contract_void_price,
        'contract_reset_breakout_price': plan_contract_reset_breakout_price,
        'contract_upgrade_condition_text': plan_contract_upgrade_condition_text,
        'holding_days_min': exit_rules.get('holding_days_min', STRATEGY_HOLDING_DAYS_MIN),
        'holding_days_max': exit_rules.get('holding_days_max', STRATEGY_HOLDING_DAYS_MAX),
        'profit_take_pct': exit_rules.get('profit_take_pct', 0.05),
        'defensive_exit_rule': exit_rules.get('defensive_exit_rule', DEFENSIVE_EXIT_RULE_TEXT),
        'profit_exit_rule': exit_rules.get('profit_exit_rule', PROFIT_EXIT_RULE_TEXT),
        'trigger_text': trigger_text,
        'decision_stack': dict(plan_stock.get('decision_stack', {}) or {}) if plan_stock else {},
        'factor_snapshot': dict(factor_snapshot or {}),
    }
    return plan_context


def _find_strategy_record(records, report_date):
    report_date = _normalize_kline_date_str(report_date)
    for record in records or []:
        if _normalize_kline_date_str(record.get('report_date')) == report_date:
            return record
    return None


def _format_strategy_record_brief(record):
    if not record:
        return "无"
    stock_name = record.get('stock_name') or record.get('anchor_type') or '无标的'
    stock_code = record.get('stock_code', '')
    action_label = _get_plan_action_label(record.get('action_type', ''), record.get('position_pct'))
    if stock_code:
        stock_name = f"{stock_name}({stock_code})"
    return f"{action_label} / {stock_name}"


def _strategy_record_core_signature(record):
    if not record:
        return ()
    return (
        _normalize_kline_date_str(record.get('report_date')),
        record.get('action_type', ''),
        record.get('anchor_type', ''),
        record.get('stock_name', ''),
        record.get('stock_code', ''),
        _round_or_none(record.get('entry_range_low'), 4),
        _round_or_none(record.get('entry_range_high'), 4),
        _round_or_none(record.get('confirm_price_60m'), 4),
        _round_or_none(record.get('effective_stop'), 4),
        record.get('trigger_text', ''),
    )


def _upsert_strategy_record(ledger, plan_context, allow_overwrite=True):
    records = ledger.setdefault('records', [])
    report_date = plan_context.get('report_date')
    for idx, record in enumerate(records):
        if record.get('report_date') == report_date:
            if not allow_overwrite:
                return record, 'preserved_existing'
            previous_simulation = record.get('simulation', {})
            updated = dict(record)
            updated.update(plan_context)
            if previous_simulation:
                updated['simulation'] = previous_simulation
            records[idx] = updated
            return updated, 'updated'
    records.append(dict(plan_context))
    return records[-1], 'created'


def _merge_strategy_record_sources(base_records, override_records):
    merged_by_date = {}
    for record in base_records or []:
        report_date = _normalize_kline_date_str(record.get('report_date'))
        if report_date:
            merged_by_date[report_date] = dict(record)

    for record in override_records or []:
        report_date = _normalize_kline_date_str(record.get('report_date'))
        if report_date:
            merged_by_date[report_date] = dict(record)

    return [
        merged_by_date[report_date]
        for report_date in sorted(merged_by_date.keys())
    ]


def _summarize_strategy_window(records, start_date, end_date):
    scoped = [
        record for record in (records or [])
        if start_date <= _normalize_kline_date_str(record.get('report_date')) <= end_date
    ]
    actionable = [record for record in scoped if record.get('action_type') == 'execute']
    triggered = [
        record for record in actionable
        if record.get('simulation', {}).get('triggered')
    ]
    evaluated = [
        record for record in actionable
        if record.get('simulation', {}).get('status') in ('closed', 'open_mark_to_market', 'not_triggered')
    ]
    included = [
        record for record in evaluated
        if record.get('simulation', {}).get('triggered')
    ]
    strategy_worst = _compound_returns(
        [record.get('simulation', {}).get('strategy_return_worst', 0.0) for record in included]
    )
    strategy_best = _compound_returns(
        [record.get('simulation', {}).get('strategy_return_best', 0.0) for record in included]
    )

    benchmark_bars = fetch_daily_price_bars('sh.000001', start_date, end_date, is_index=True)
    benchmark_start = _get_first_bar_on_or_after(benchmark_bars, start_date)
    benchmark_end = _get_last_bar_on_or_before(benchmark_bars, end_date)
    benchmark_return = None
    if benchmark_start and benchmark_end:
        start_close = _safe_float(benchmark_start.get('close'))
        end_close = _safe_float(benchmark_end.get('close'))
        if start_close > 0:
            benchmark_return = end_close / start_close - 1

    alpha_worst = strategy_worst - benchmark_return if benchmark_return is not None else None
    alpha_best = strategy_best - benchmark_return if benchmark_return is not None else None
    positive_alpha_count = 0
    for record in included:
        sim = record.get('simulation', {})
        midpoint = (
            _safe_float(sim.get('alpha_return_worst')) + _safe_float(sim.get('alpha_return_best'))
        ) / 2.0
        if midpoint > 0:
            positive_alpha_count += 1

    return {
        'start_date': start_date,
        'end_date': end_date,
        'plan_count': len(scoped),
        'actionable_count': len(actionable),
        'triggered_count': len(triggered),
        'evaluated_count': len(evaluated),
        'strategy_return_worst': strategy_worst,
        'strategy_return_best': strategy_best,
        'benchmark_return': benchmark_return,
        'alpha_return_worst': alpha_worst,
        'alpha_return_best': alpha_best,
        'positive_alpha_count': positive_alpha_count,
        'open_count': sum(
            1 for record in included if record.get('simulation', {}).get('status') == 'open_mark_to_market'
        ),
    }


def _prepare_records_for_review(records, as_of_date):
    prepared = []
    for record in records or []:
        prepared.append(_backfill_strategy_record_market_context(dict(record)))

    prepared.sort(key=lambda x: _normalize_kline_date_str(x.get('report_date')))
    for record in prepared:
        record['simulation'] = _evaluate_single_strategy_record(record, as_of_date)
    _apply_yizi_chain_rules(prepared)
    for record in prepared:
        record['attribution'] = _classify_strategy_record_attribution(record, as_of_date)
    return prepared


def _classify_structure_cycle_result(window_summary, attribution_summary, gem_cycle_review=None):
    attribution_items = attribution_summary.get('items', []) or []
    dominant_label = attribution_items[0].get('label', '') if attribution_items else ''
    gem_cycle_review = gem_cycle_review or {}
    gem_sample_count = int(_safe_float(gem_cycle_review.get('sample_count', 0)))
    gem_upgrade_count = int(_safe_float(gem_cycle_review.get('conditional_upgrade_count', 0)))
    gem_upgrade_lag = int(_safe_float(gem_cycle_review.get('upgrade_lag_count', 0)))
    gem_voided_count = int(_safe_float(gem_cycle_review.get('voided_count', 0)))
    gem_expired_count = int(_safe_float(gem_cycle_review.get('expired_count', 0)))
    alpha_mid = None
    alpha_low = window_summary.get('alpha_return_worst')
    alpha_high = window_summary.get('alpha_return_best')
    if alpha_low is not None and alpha_high is not None:
        alpha_mid = (_safe_float(alpha_low) + _safe_float(alpha_high)) / 2.0

    if window_summary.get('triggered_count', 0) > 0:
        if alpha_mid is not None and alpha_mid > 0.01:
            return '进攻有效'
        if alpha_mid is not None and alpha_mid < -0.02:
            return '进攻失真'
        return '进攻待验证'

    if gem_sample_count > 0:
        if gem_upgrade_lag >= 1:
            return '20cm升级偏慢'
        if gem_upgrade_count >= 1 and gem_voided_count + gem_expired_count < gem_sample_count:
            return '20cm支链成形'
        if gem_upgrade_count == 0 and gem_voided_count + gem_expired_count >= max(1, gem_sample_count - 1):
            return '20cm仍待收敛'

    if dominant_label == '防守正确':
        return '防守有效'
    if dominant_label in ('环境过滤过严', '个股对了但环境不放行', '介入周期偏慢'):
        return '过滤偏严'
    return '观察学习'


def _build_structure_cycle_gem_summary(gem_cycle_review):
    gem_cycle_review = gem_cycle_review or {}
    gem_sample_count = int(_safe_float(gem_cycle_review.get('sample_count', 0)))
    if gem_sample_count <= 0:
        return '-'
    gem_upgrade_count = int(_safe_float(gem_cycle_review.get('conditional_upgrade_count', 0)))
    gem_upgrade_lag = int(_safe_float(gem_cycle_review.get('upgrade_lag_count', 0)))
    gem_voided_count = int(_safe_float(gem_cycle_review.get('voided_count', 0)))
    gem_expired_count = int(_safe_float(gem_cycle_review.get('expired_count', 0)))
    return (
        f"20cm样本{gem_sample_count} / 升级{gem_upgrade_count} / 偏慢{gem_upgrade_lag} / "
        f"作废{gem_voided_count} / 到期{gem_expired_count}"
    )


def _build_gem_structure_cycle_cards(records, as_of_date, limit=6):
    grouped = {}
    for record in records or []:
        snapshot = _extract_gem_breathing_contract_snapshot(record)
        if not snapshot:
            continue
        cycle_start = _normalize_kline_date_str(record.get('structure_cycle_start')) or _normalize_kline_date_str(record.get('report_date'))
        stock_code = snapshot.get('stock_code') or snapshot.get('sample_label')
        if not cycle_start or not stock_code:
            continue
        grouped.setdefault((cycle_start, stock_code), []).append(record)

    cards = []
    for (cycle_start, _stock_code), group_records in grouped.items():
        sorted_records = sorted(group_records, key=lambda x: _normalize_kline_date_str(x.get('report_date')))
        classified_items = []
        for record in sorted_records:
            item = _classify_gem_breathing_week_sample(record, as_of_date)
            if item:
                classified_items.append(item)
        if not classified_items:
            continue

        latest_item = classified_items[-1]
        status_chain = []
        for item in classified_items:
            status_label = str(item.get('status_label', '') or '').strip()
            if status_label and (not status_chain or status_chain[-1] != status_label):
                status_chain.append(status_label)

        first_date = _normalize_kline_date_str(sorted_records[0].get('report_date'))
        last_date = _normalize_kline_date_str(sorted_records[-1].get('report_date'))
        occurrence_count = len(sorted_records)
        cycle_end = last_date or cycle_start
        timeline_text = f"{first_date} -> {last_date}" if first_date and last_date and first_date != last_date else (first_date or cycle_start)
        timeline_text = f"{timeline_text}（同周期出现{occurrence_count}次）"
        cycle_label = f"{cycle_start} -> {cycle_end}" if cycle_start != cycle_end else cycle_start

        cards.append({
            'cycle_start': cycle_start,
            'cycle_end': cycle_end,
            'cycle_label': cycle_label,
            'sample_label': latest_item.get('sample_label') or latest_item.get('stock_name') or '-',
            'occurrence_count': occurrence_count,
            'timeline_text': timeline_text,
            'evolution_text': ' → '.join(status_chain) if status_chain else latest_item.get('status_label', '-'),
            'latest_status_label': latest_item.get('status_label', '-'),
            'price_map': latest_item.get('price_map', '-') or '-',
            'note': latest_item.get('note', '-') or '-',
        })

    status_priority = {
        '再突破成功但升级偏慢': 5,
        '已升级到30%条件试错': 4,
        '已走成再突破': 3,
        '已触发右侧确认': 2,
        '仍在观察窗口': 1,
        '窗口内失守作废': 0,
        '窗口到期自然作废': 0,
    }
    cards.sort(
        key=lambda x: (
            x.get('occurrence_count', 0),
            status_priority.get(x.get('latest_status_label', ''), 0),
            x.get('cycle_start', ''),
            x.get('sample_label', ''),
        ),
        reverse=True,
    )
    return cards[:limit]


def _build_gem_horizontal_compare_cards(gem_cycle_cards=None, review_matrix=None, limit=4):
    gem_cycle_cards = gem_cycle_cards or []
    review_matrix = review_matrix or []
    if not gem_cycle_cards or not review_matrix:
        return []

    def _pick_reference(latest_status_label=''):
        latest_status_label = str(latest_status_label or '').strip()
        if latest_status_label in ('再突破成功但升级偏慢', '已升级到30%条件试错', '已走成再突破'):
            preferred = ('已走成 act right', '个股先走出来了')
        elif latest_status_label in ('仍在观察窗口', '已触发右侧确认'):
            preferred = ('先强后回，进入二次确认', '还在等待确认', '日内确认相对干净', '仍在观察周期')
        else:
            preferred = ('已失守观察边界', '先破观察边界，暂不升级', '确认不干净，继续观察')

        for label in preferred:
            for item in review_matrix:
                if str(item.get('path_label', '') or '').strip() == label:
                    return item
        return review_matrix[0] if review_matrix else {}

    cards = []
    for gem_card in gem_cycle_cards[:limit]:
        latest_status_label = str(gem_card.get('latest_status_label', '') or '').strip()
        reference = _pick_reference(latest_status_label)
        if not reference:
            continue

        if latest_status_label in ('再突破成功但升级偏慢', '已升级到30%条件试错', '已走成再突破'):
            same_point = '两者都属于价格上先证明自己的样本，都是市场先替判断作证。'
            key_difference = '区别是20cm弹性和波动都更大，不能直接按10cm唯一动作给50%，必须先过右侧确认、void、reset这条合同链。'
            system_translation = '系统里要先核对void/trigger/reset三价，再决定是否只给30%条件试错，不能把20cm再突破直接翻译成10cm唯一执行。'
        elif latest_status_label in ('仍在观察窗口', '已触发右侧确认'):
            same_point = '两者都还停在“有观察权、没执行权”的阶段，本质都还没走成唯一动作。'
            key_difference = '区别是20cm多了一层呼吸感合同窗口；窗口过期或失守void，就要比10cm更快降权。'
            system_translation = '把20cm先当成二次确认/等待确认样本，除非后续再突破并完成60分钟确认，否则继续观察，不提前抬仓位。'
        else:
            same_point = '两者都说明观察链已经被破坏，继续脑补升级都容易犯错。'
            key_difference = '区别是20cm失守后伤害放大更快，所以破void或窗口到期时必须更果断降权。'
            system_translation = '一旦20cm合同失守或过期，直接从高优先级观察里拿掉，不再把它留成“也许还有戏”的对象。'

        cards.append({
            'cycle_label': gem_card.get('cycle_label', '-'),
            'sample_label': gem_card.get('sample_label', '-'),
            'gem_path_label': latest_status_label or '-',
            'reference_sample_label': reference.get('sample_label', '-'),
            'reference_path_label': reference.get('path_label', '-'),
            'same_point': same_point,
            'key_difference': key_difference,
            'system_translation': system_translation,
        })
    return cards


def _summarize_structure_cycles(records, as_of_date):
    grouped = {}
    for record in records or []:
        cycle_start = _normalize_kline_date_str(record.get('structure_cycle_start')) or _normalize_kline_date_str(record.get('report_date'))
        if not cycle_start:
            continue
        grouped.setdefault(cycle_start, []).append(record)

    cycle_items = []
    for cycle_start in sorted(grouped.keys()):
        cycle_records = sorted(grouped.get(cycle_start, []), key=lambda x: _normalize_kline_date_str(x.get('report_date')))
        if not cycle_records:
            continue

        cycle_end = max(_normalize_kline_date_str(record.get('report_date')) for record in cycle_records)
        window_summary = _summarize_strategy_window(records, cycle_start, cycle_end)
        attribution_summary = _summarize_strategy_attribution(records, cycle_start, cycle_end)
        setup_summary = _summarize_setup_signal_review(records, cycle_start, cycle_end)
        gem_cycle_review = _summarize_gem_breathing_week_review(records, cycle_start, cycle_end)
        dominant_attribution = (attribution_summary.get('items', []) or [{}])[0].get('label', '')
        top_setup = (setup_summary.get('items', []) or [{}])[0].get('setup_label', '')
        gem_cycle_summary = _build_structure_cycle_gem_summary(gem_cycle_review)

        alpha_mid = None
        if window_summary.get('alpha_return_worst') is not None and window_summary.get('alpha_return_best') is not None:
            alpha_mid = (
                _safe_float(window_summary.get('alpha_return_worst'))
                + _safe_float(window_summary.get('alpha_return_best'))
            ) / 2.0

        cycle_items.append({
            'cycle_start': cycle_start,
            'cycle_end': cycle_end,
            'plan_count': len(cycle_records),
            'execute_count': sum(1 for record in cycle_records if record.get('action_type') == 'execute'),
            'triggered_count': int(window_summary.get('triggered_count', 0)),
            'benchmark_return': window_summary.get('benchmark_return'),
            'alpha_return_worst': window_summary.get('alpha_return_worst'),
            'alpha_return_best': window_summary.get('alpha_return_best'),
            'alpha_mid': alpha_mid,
            'dominant_attribution': dominant_attribution or '-',
            'top_setup': top_setup or '-',
            'gem_20cm_sample_count': int(_safe_float(gem_cycle_review.get('sample_count', 0))),
            'gem_20cm_summary': gem_cycle_summary,
            'mainline_preview': " / ".join([
                record.get('mainline_name', '')
                for record in cycle_records[-3:]
                if record.get('mainline_name')
            ]) or '-',
            'result_label': _classify_structure_cycle_result(window_summary, attribution_summary, gem_cycle_review),
        })

    return cycle_items


def _build_system_graduation_dashboard(records, cycle_reviews, source_label='当前账本', current_plan=None, gem_week_review=None):
    total_records = len(records or [])
    cycle_count = len(cycle_reviews or [])
    gem_week_review = gem_week_review or {}
    frozen_count = sum(1 for record in (records or []) if record.get('factor_snapshot') or record.get('factor_snapshot_path'))
    attribution_count = sum(1 for record in (records or []) if (record.get('attribution', {}) or {}).get('category'))
    decision_stack_count = sum(1 for record in (records or []) if record.get('decision_stack') or (record.get('factor_snapshot', {}) or {}).get('selection'))
    setup_count = sum(1 for record in (records or []) if record.get('abnormal_setup_signal_label') or ((record.get('factor_snapshot', {}) or {}).get('abnormal', {}) or {}).get('selected_setup'))
    execute_count = sum(1 for record in (records or []) if record.get('action_type') == 'execute')
    triggered_count = sum(1 for record in (records or []) if (record.get('simulation', {}) or {}).get('triggered'))
    positive_cycles = sum(1 for item in (cycle_reviews or []) if item.get('result_label') in ('进攻有效', '防守有效'))
    strict_cycles = sum(1 for item in (cycle_reviews or []) if item.get('result_label') == '过滤偏严')
    gem_sample_count = int(_safe_float(gem_week_review.get('sample_count', 0)))
    gem_upgrade_count = int(_safe_float(gem_week_review.get('conditional_upgrade_count', 0)))
    gem_upgrade_lag = int(_safe_float(gem_week_review.get('upgrade_lag_count', 0)))
    gem_voided_count = int(_safe_float(gem_week_review.get('voided_count', 0)))
    gem_expired_count = int(_safe_float(gem_week_review.get('expired_count', 0)))

    frozen_cov = frozen_count / total_records if total_records > 0 else 0.0
    attribution_cov = attribution_count / total_records if total_records > 0 else 0.0
    decision_cov = decision_stack_count / total_records if total_records > 0 else 0.0
    setup_cov = setup_count / total_records if total_records > 0 else 0.0
    positive_cycle_ratio = positive_cycles / cycle_count if cycle_count > 0 else 0.0

    integrity_score = round((frozen_cov * 0.55 + attribution_cov * 0.45) * 25)
    standard_score = round((decision_cov * 0.45 + setup_cov * 0.55) * 15)
    breadth_score = round((min(total_records / 24.0, 1.0) * 0.55 + min(cycle_count / 3.0, 1.0) * 0.45) * 20)
    execution_score = round((min(execute_count / 10.0, 1.0) * 0.55 + min(triggered_count / 6.0, 1.0) * 0.45) * 20)
    performance_score = round((positive_cycle_ratio * 0.75 + min(max(cycle_count - strict_cycles, 0) / max(cycle_count, 1), 1.0) * 0.25) * 20)
    total_score = integrity_score + standard_score + breadth_score + execution_score + performance_score

    current_plan = current_plan or {}
    current_factor_snapshot = current_plan.get('factor_snapshot', {}) or {}
    current_engine_ready = bool(
        current_factor_snapshot
        and current_plan.get('decision_stack', {}) is not None
        and current_plan.get('defensive_exit_rule')
        and current_plan.get('profit_exit_rule')
    )
    legacy_history_gap = current_engine_ready and total_records > 0 and frozen_cov < 0.2 and setup_cov < 0.2

    if total_score < 35:
        if legacy_history_gap:
            stage = '研究原型'
            verdict = '当前引擎已经脱离玩具，但官方冻结记录大多还是旧版本，毕业证据仍然不足。'
        else:
            stage = '玩具'
            verdict = '还没过研究门槛，当前更多是展示逻辑，不足以稳定辅助。'
    elif total_score < 65:
        stage = '研究原型'
        verdict = '已经脱离玩具，但还处在记录积累和参数校准阶段。'
    elif total_score < 82:
        stage = '可长期辅助决策'
        verdict = '已经能稳定辅助复盘和筛错，但仍不适合完全托管执行。'
    else:
        stage = '接近成熟系统'
        verdict = '流程、记录和跨周期表现都较完整，已接近成熟辅助系统。'

    graduation_checks = [
        {
            'item': '历史冻结完整性',
            'status': '通过' if frozen_cov >= 0.9 else '待加强',
            'detail': f"{frozen_count}/{total_records} 条记录有冻结因子快照",
        },
        {
            'item': '跨结构周期广度',
            'status': '通过' if cycle_count >= 3 else '待加强',
            'detail': f"当前覆盖 {cycle_count} 个结构周期",
        },
        {
            'item': '归因闭环',
            'status': '通过' if attribution_cov >= 0.9 else '待加强',
            'detail': f"{attribution_count}/{total_records} 条记录已有错因归属",
        },
        {
            'item': 'Setup标准化',
            'status': '通过' if setup_cov >= 0.6 else '待加强',
            'detail': f"{setup_count}/{total_records} 条记录已有固定 setup",
        },
        {
            'item': '执行记录深度',
            'status': '通过' if execute_count >= 10 and triggered_count >= 5 else '待加强',
            'detail': f"执行计划 {execute_count} 条，真实触发 {triggered_count} 条",
        },
        {
            'item': '跨周期结果稳定性',
            'status': '通过' if positive_cycle_ratio >= 0.5 and cycle_count >= 2 else '待加强',
            'detail': f"正向周期 {positive_cycles}/{cycle_count}",
        },
    ]
    if gem_sample_count > 0:
        gem_check_pass = gem_upgrade_count >= 1 and gem_upgrade_lag <= max(1, gem_sample_count // 3)
        graduation_checks.append({
            'item': '创业板20cm支链',
            'status': '通过' if gem_check_pass else '待加强',
            'detail': f"{gem_sample_count}只样本 / 升级{gem_upgrade_count}只 / 升级偏慢{gem_upgrade_lag}只 / 作废{gem_voided_count}只 / 到期{gem_expired_count}只",
        })

    next_actions = []
    if cycle_count < 3:
        next_actions.append('至少继续积累 2 个以上完整结构周期，再判断是否毕业。')
    if execute_count < 10 or triggered_count < 5:
        next_actions.append('继续沉淀真实执行记录，否则 EV 和退出节奏都没有统计意义。')
    if strict_cycles >= 1:
        next_actions.append('重点复盘“过滤偏严”的周期，判断环境门控是否错杀了主线机会。')
    if gem_sample_count > 0 and gem_upgrade_lag >= 1:
        next_actions.append(f'优先修正创业板20cm从右侧确认到30%条件试错的升级链；本周升级偏慢{gem_upgrade_lag}只，不能继续长期停在观察层。')
    if gem_sample_count > 0 and gem_voided_count >= gem_upgrade_count and gem_voided_count > 0:
        next_actions.append('复盘创业板20cm合同的作废价与样本筛法，避免高优先级观察样本大量在窗口内失效。')
    if not next_actions:
        next_actions.append('开始按固定周期复查 stage 是否能从辅助系统继续向成熟系统升级。')

    return {
        'source_label': source_label,
        'stage': stage,
        'verdict': verdict,
        'total_score': total_score,
        'dimension_scores': [
            {'name': '过程完整性', 'score': integrity_score, 'detail': f"冻结覆盖{frozen_cov:.0%} / 归因覆盖{attribution_cov:.0%}"},
            {'name': '标准化程度', 'score': standard_score, 'detail': f"决策栈覆盖{decision_cov:.0%} / Setup覆盖{setup_cov:.0%}" + (f" / 20cm样本{gem_sample_count} 升级{gem_upgrade_count} 偏慢{gem_upgrade_lag}" if gem_sample_count > 0 else '')},
            {'name': '跨周期广度', 'score': breadth_score, 'detail': f"{total_records}条记录 / {cycle_count}个结构周期"},
            {'name': '执行记录深度', 'score': execution_score, 'detail': f"{execute_count}条执行计划 / {triggered_count}条真实触发"},
            {'name': '跨周期稳定性', 'score': performance_score, 'detail': f"正向周期{positive_cycles}/{cycle_count}"},
        ],
        'checks': graduation_checks,
        'next_actions': next_actions,
        'legacy_history_gap': legacy_history_gap,
        'current_engine_ready': current_engine_ready,
    }


def update_strategy_performance_book(data, target_date, plan_context, market_zhongshu, ledger_mode=LEDGER_MODE_FROZEN):
    import datetime as _dt

    ledger = load_strategy_performance_ledger(mode=ledger_mode)
    official_ledger = None
    plan_context = _backfill_strategy_record_market_context(dict(plan_context))
    existing_official_record = None
    if ledger_mode == LEDGER_MODE_REPLAY:
        official_ledger = load_strategy_performance_ledger(mode=LEDGER_MODE_FROZEN)
        existing_official_record = _find_strategy_record(official_ledger.get('records', []), target_date)

    current_record, write_status = _upsert_strategy_record(
        ledger,
        plan_context,
        allow_overwrite=(ledger_mode == LEDGER_MODE_REPLAY),
    )
    factor_snapshot_meta = save_factor_snapshot(
        target_date,
        current_record.get('factor_snapshot', {}),
        mode=ledger_mode,
    )
    current_record['factor_snapshot_path'] = factor_snapshot_meta.get('path', '')
    current_record['factor_snapshot_mode'] = factor_snapshot_meta.get('mode', ledger_mode)
    current_record['factor_snapshot_version'] = factor_snapshot_meta.get('version', STRATEGY_FACTOR_SNAPSHOT_VERSION)
    current_record['factor_snapshot_saved_at'] = factor_snapshot_meta.get('saved_at', '')
    current_record = _backfill_strategy_record_market_context(dict(current_record))

    history_lock_note = ''
    if ledger_mode == LEDGER_MODE_FROZEN and write_status == 'preserved_existing':
        if _strategy_record_core_signature(current_record) != _strategy_record_core_signature(plan_context):
            history_lock_note = (
                f"该日期官方历史已冻结，继续沿用原计划：{_format_strategy_record_brief(current_record)}；"
                f"本次重算结果不会覆盖历史。"
            )
        else:
            history_lock_note = "该日期官方历史已冻结，本次仅复用原计划，不改写历史。"
    elif ledger_mode == LEDGER_MODE_REPLAY:
        history_lock_note = "当前为实验重放账本，可覆盖实验结果，但不会改写官方历史。"

    for record in ledger.get('records', []):
        _backfill_strategy_record_market_context(record)
        record['simulation'] = _evaluate_single_strategy_record(record, target_date)

    ledger['records'].sort(key=lambda x: _normalize_kline_date_str(x.get('report_date')))
    _apply_yizi_chain_rules(ledger.get('records', []))
    for record in ledger.get('records', []):
        record['attribution'] = _classify_strategy_record_attribution(record, target_date)
    save_strategy_performance_ledger(ledger, mode=ledger_mode)

    target_dt = _parse_kline_date(target_date)
    week_start = target_dt - _dt.timedelta(days=target_dt.weekday()) if target_dt else None
    month_start = target_dt.replace(day=1) if target_dt else None
    current_zhongshu = market_zhongshu.get('current_zhongshu', {}) if market_zhongshu else {}
    structure_cycle_start = current_zhongshu.get('start_date') or (month_start.strftime('%Y-%m-%d') if month_start else target_date)

    summary = {
        'current_plan': dict(current_record),
        'windows': [],
        'recent_records': [],
        'ledger_mode': ledger_mode,
        'ledger_label': _get_run_mode_label(ledger_mode),
        'write_status': write_status,
        'history_lock_note': history_lock_note,
        'existing_official_record': existing_official_record,
        'proposed_plan': dict(plan_context),
    }

    summary_source_records = _prepare_records_for_review(ledger.get('records', []), target_date)
    summary_source_label = '当前账本'
    if ledger_mode == LEDGER_MODE_REPLAY and official_ledger:
        merged_records = _merge_strategy_record_sources(
            official_ledger.get('records', []),
            ledger.get('records', []),
        )
        summary_source_records = _prepare_records_for_review(merged_records, target_date)
        summary_source_label = '官方冻结历史 + 当前实验推演'
    summary['summary_source_label'] = summary_source_label

    if week_start:
        summary['windows'].append({
            'name': '本周',
            **_summarize_strategy_window(
                summary_source_records,
                week_start.strftime('%Y-%m-%d'),
                target_date,
            ),
        })
    if month_start:
        summary['windows'].append({
            'name': '本月',
            **_summarize_strategy_window(
                summary_source_records,
                month_start.strftime('%Y-%m-%d'),
                target_date,
            ),
        })
    summary['windows'].append({
        'name': '本次结构周期',
        **_summarize_strategy_window(
            summary_source_records,
            structure_cycle_start,
            target_date,
        ),
    })
    summary['structure_cycle_start'] = structure_cycle_start
    if week_start:
        summary['ev_week_review'] = _summarize_ev_signal_review(
            summary_source_records,
            week_start.strftime('%Y-%m-%d'),
            target_date,
        )
        summary['attribution_week_review'] = _summarize_strategy_attribution(
            summary_source_records,
            week_start.strftime('%Y-%m-%d'),
            target_date,
        )
        summary['setup_week_review'] = _summarize_setup_signal_review(
            summary_source_records,
            week_start.strftime('%Y-%m-%d'),
            target_date,
        )
        summary['gem_20cm_week_review'] = _summarize_gem_breathing_week_review(
            summary_source_records,
            week_start.strftime('%Y-%m-%d'),
            target_date,
        )
    else:
        summary['ev_week_review'] = {
            'start_date': target_date,
            'end_date': target_date,
            'total_plan_count': 0,
            'items': [],
        }
        summary['attribution_week_review'] = {
            'start_date': target_date,
            'end_date': target_date,
            'total_count': 0,
            'items': [],
            'highlights': [],
        }
        summary['setup_week_review'] = {
            'start_date': target_date,
            'end_date': target_date,
            'total_plan_count': 0,
            'items': [],
        }
        summary['gem_20cm_week_review'] = {
            'start_date': target_date,
            'end_date': target_date,
            'sample_count': 0,
            'right_side_confirmation_count': 0,
            'rebreak_success_count': 0,
            'conditional_upgrade_count': 0,
            'voided_count': 0,
            'expired_count': 0,
            'upgrade_lag_count': 0,
            'active_observation_count': 0,
            'upgrade_lag_samples': [],
            'voided_samples': [],
            'expired_samples': [],
            'items': [],
        }
    summary['ev_calibration_snapshot'] = build_strategy_ev_calibration(target_date, ledger_mode=ledger_mode)
    summary['self_calibration'] = _build_self_calibration_summary(
        summary_source_records,
        week_start.strftime('%Y-%m-%d') if week_start else target_date,
        target_date,
        windows=summary.get('windows', []),
        attribution_summary=summary.get('attribution_week_review', {}),
        setup_summary=summary.get('setup_week_review', {}),
        ev_summary=summary.get('ev_week_review', {}),
        gem_week_review=summary.get('gem_20cm_week_review', {}),
    )
    graduation_source_records = ledger.get('records', [])
    graduation_source_label = '当前账本'
    if ledger_mode == LEDGER_MODE_REPLAY and official_ledger and official_ledger.get('records'):
        graduation_source_records = _prepare_records_for_review(official_ledger.get('records', []), target_date)
        graduation_source_label = '官方冻结账本'
    else:
        graduation_source_records = _prepare_records_for_review(ledger.get('records', []), target_date)
    summary['structure_cycle_reviews'] = _summarize_structure_cycles(graduation_source_records, target_date)
    summary['graduation_dashboard'] = _build_system_graduation_dashboard(
        graduation_source_records,
        summary.get('structure_cycle_reviews', []),
        source_label=graduation_source_label,
        current_plan=current_record,
        gem_week_review=summary.get('gem_20cm_week_review', {}),
    )
    summary['gem_20cm_cycle_cards'] = _build_gem_structure_cycle_cards(
        graduation_source_records,
        target_date,
    )

    recent_records = []
    for record in sorted(
        summary_source_records,
        key=lambda x: _normalize_kline_date_str(x.get('report_date')),
        reverse=True,
    ):
        sim = record.get('simulation', {})
        if record.get('action_type') == 'execute' or sim.get('status') in ('watch_only', 'no_trade'):
            recent_records.append(record)
        if len(recent_records) >= 5:
            break
    summary['recent_records'] = recent_records
    summary['recent_target_followups'] = _build_recent_target_followups(recent_records, target_date)
    summary['recent_target_review_matrix'] = _build_recent_target_review_matrix(
        current_record,
        summary.get('recent_target_followups', []),
    )
    summary['gem_horizontal_compare_cards'] = _build_gem_horizontal_compare_cards(
        summary.get('gem_20cm_cycle_cards', []),
        summary.get('recent_target_review_matrix', []),
    )
    summary['recent_target_reflection'] = _build_recent_target_reflection(
        summary.get('recent_target_review_matrix', []),
    )
    return summary


def _get_recent_record_display_metrics(record):
    record = record or {}
    sim = record.get('simulation', {}) or {}
    strategy_return_worst = sim.get('strategy_return_worst')
    strategy_return_best = sim.get('strategy_return_best')
    benchmark_return = sim.get('benchmark_return')

    if record.get('action_type') != 'execute':
        raw_benchmark_change_pct = record.get('benchmark_report_change_pct')
        if raw_benchmark_change_pct not in (None, ''):
            benchmark_return = _safe_float(raw_benchmark_change_pct) / 100.0

    alpha_return_worst = sim.get('alpha_return_worst')
    alpha_return_best = sim.get('alpha_return_best')
    if benchmark_return is not None:
        alpha_return_worst = _safe_float(strategy_return_worst) - _safe_float(benchmark_return)
        alpha_return_best = _safe_float(strategy_return_best) - _safe_float(benchmark_return)

    return {
        'strategy_return_worst': strategy_return_worst,
        'strategy_return_best': strategy_return_best,
        'benchmark_return': benchmark_return,
        'alpha_return_worst': alpha_return_worst,
        'alpha_return_best': alpha_return_best,
    }


def append_strategy_performance_section(report, performance_summary):
    report.extend(
        render_strategy_performance_section(
            performance_summary,
            {
                "ledger_mode_frozen": LEDGER_MODE_FROZEN,
                "ledger_mode_replay": LEDGER_MODE_REPLAY,
                "defensive_exit_rule_text": DEFENSIVE_EXIT_RULE_TEXT,
                "format_strategy_record_brief": _format_strategy_record_brief,
                "format_frozen_plan_columns": _format_frozen_plan_columns,
                "get_plan_action_label": _get_plan_action_label,
                "get_recent_record_display_metrics": _get_recent_record_display_metrics,
                "format_pct_range": _format_pct_range,
                "format_pct": _format_pct,
                "safe_float": _safe_float,
            },
        )
    )


def generate_markdown_report(
    data,
    target_date,
    supplementary_perspective="",
    has_personal_positions=False,
    run_mode=LEDGER_MODE_FROZEN,
    persist_strategy_tracking=True,
):
    """生成Markdown格式的A股日报报告
    
    严格遵循SKILL.md中的9步格式要求，增强AI分析能力
    
    Args:
        data: 所有数据源的结果字典
        target_date: 数据日期，格式 YYYY-MM-DD
        supplementary_perspective: 补充视角文字（复盘时使用），默认为空
    """
    print("\n" + "=" * 60)
    print("📄 生成A股日报报告...", flush=True)
    print("=" * 60)
    data['target_date'] = target_date
    
    report_shell = build_report_shell_contract(
        target_date,
        run_mode=run_mode,
        has_personal_positions=has_personal_positions,
        compact=DISPLAY_MVP_MODE,
        use_report_preamble=markdown_hooks.use_report_preamble,
    )
    report = report_shell.get('report', [])
    
    # ========== 提前计算最终档位（v2.3.51重构）==========
    # 目的：确保报告开头显示的档位和Step 4一致
    phase_context = build_market_phase_context(data, target_date, emit_logs=True)
    market_zhongshu = phase_context.get('market_zhongshu', {})
    market_analysis = phase_context.get('market_analysis', {})
    market_trend = phase_context.get('market_trend', '震荡整理')
    mainline_context = phase_context.get('mainline_context', {}) or {}
    main_sectors_info = phase_context.get('main_sectors_info', [])
    secondary_sectors_info = phase_context.get('secondary_sectors_info', [])
    main_sectors = phase_context.get('main_sectors', [])
    secondary_sectors = phase_context.get('secondary_sectors', [])
    dragon_stocks = phase_context.get('dragon_stocks', [])
    exit_analysis = phase_context.get('exit_analysis', {}) or {}
    turnover = phase_context.get('turnover', 0)
    zt_count = phase_context.get('zt_count', 0)
    dt_count = phase_context.get('dt_count', 0)
    indices = phase_context.get('indices', {}) or {}
    sh_change = phase_context.get('sh_change', 0)
    market_stats = phase_context.get('market_stats', {}) or {}
    up_count = phase_context.get('up_count', 0)
    down_count = phase_context.get('down_count', 0)
    rise_fall_ratio = phase_context.get('rise_fall_ratio', 0)
    zs_signal_type = phase_context.get('zs_signal_type')
    zs_signal_status = phase_context.get('zs_signal_status')
    is_dt_panic = phase_context.get('is_dt_panic', False)
    base_position_level = phase_context.get('base_position_level', '')
    base_position_reason = phase_context.get('base_position_reason', '')
    position_level = phase_context.get('position_level', '')
    position_reason = phase_context.get('position_reason', '')
    final_gate = phase_context.get('final_gate', {}) or {}
    environment_display = phase_context.get('environment_display', {}) or {}
    display_position_level = str(environment_display.get('position_level', '') or position_level).strip()
    display_operation_state = str(environment_display.get('operation_state', '') or final_gate.get('operation_state', '观察态')).strip()
    environment_headline = str(environment_display.get('headline', '') or '').strip()
    display_position_reason = _resolve_environment_reason_contract(
        position_reason=position_reason,
        environment_display=environment_display,
        state_machine_snapshot=phase_context.get('preliminary_state_machine', {}) or {},
    )
    overall_level = phase_context.get('overall_level', '红灯')
    price_info = phase_context.get('price_info')
    
    # ========== 📈 大盘中枢分析（一打开就能看到） ==========
    
    if market_zhongshu and market_zhongshu.get('success'):
        zhongshu_list = market_zhongshu.get('zhongshu_list', [])
        current = market_zhongshu.get('current_zhongshu', {})
        structure_segments = market_zhongshu.get('structure_segments', [])
        latest_structure_segment = market_zhongshu.get('latest_structure_segment', {})
        signal = market_zhongshu.get('signal', {})
        ascii_diagram = _build_zhongshu_ascii_diagram(
            structure_segments,
            market_zhongshu.get('today_date', ''),
            market_zhongshu.get('today_price', 0.0),
            signal,
        )
        
        report.append("## 📈 明天仓位怎么放（基于日线结构中枢）")
        report.append("")
        report.append(f"**怎么执行**：{get_execution_framework_text()}")
        report.append("> **说明**：这里的“结构中枢”是缠论启发版的日线价格结构工具，不是严格笔/线段缠论。它只负责环境过滤、仓位判断和能不能开仓。")
        report.append("> **真到盘中怎么做**：日报这里只做盘前预案。明日先看前30分钟环境是否匹配，再等首个60分钟K线确认买点，买入后再用30分钟结构刷新止损。")
        report.append("")
        
        # 显示当前中枢状态和最终档位（v2.3.51重构）
        # position_level已经在前面的综合计算中确定（中枢+情绪+Step 4退出分析）
        if current and signal:
            status = signal.get('status', '未知')
            signal_type = signal.get('signal_type', '未知')
            
            # 根据最终档位显示不同的emoji
            if '进攻' in display_position_level:
                emoji = "🟢"
            elif '空仓' in display_position_level:
                emoji = "🔴"
            else:
                emoji = "🟡"
            
            # 显示最终环境状态（这里只表达环境放行，不直接等于已经有可买对象）
            report.append(f"### {emoji} 明日市场环境：{display_position_level} / {display_operation_state}")
            report.append("")
            report.append(f"**大盘状态**：{status}")
            report.append(f"**信号类型**：{signal_type}")
            if signal.get('comparison_result'):
                report.append(f"**结构对比结果**：{signal['comparison_result']}")
            report.append("")
            
            # 显示结构区间
            zone_label = "最近确认结构区间" if latest_structure_segment and latest_structure_segment.get('segment_type') == 'connector' else "当前结构区间"
            report.append(f"- **{zone_label}**：[{signal['zd']:.2f}, {signal['zg']:.2f}]")
            report.append(f"- **今日收盘**：{signal['today_price']:.2f}")
            report.append(f"- **相对ZG**：{signal['dist_to_zg']*100:+.2f}%")
            if current:
                report.append(f"- **最近确认中枢**：{current.get('start_date', '-') }~{current.get('end_date', '-')}")
            if latest_structure_segment and latest_structure_segment.get('segment_type') == 'connector':
                report.append(f"- **最新历史结构**：{latest_structure_segment['start_date']}~{latest_structure_segment['end_date']} 为过渡结构（{latest_structure_segment['kline_count']}根K线）")
            report.append("")

            if ascii_diagram and not DISPLAY_MVP_MODE:
                report.append("**ASCII结构图**：")
                report.append("```text")
                report.append(ascii_diagram)
                report.append("```")
                report.append("")
            
            # 显示状态判断依据
            report.append(f"**状态依据**：{display_position_reason}")
            report.append("**执行说明**：这里的档位只代表环境是否放行，不代表已经有可买标的；真正能不能买，要看后文有没有缩到一只可买股。")
            report.append("")
            
            # 显示识别的中枢列表（简化版）
            if DISPLAY_MVP_MODE:
                report.append(f"- **结构识别概览**：历史共识别 {len(zhongshu_list)} 个结构中枢；当前只跟踪最近确认中枢与尾部过渡。")
                report.append("")
            elif len(zhongshu_list) >= 1:
                report.append(f"**识别出 {len(zhongshu_list)} 个结构中枢**：")
                report.append("| 结构中枢 | 时间区间 | ZG | ZD | 性质 |")
                report.append("|------|----------|-----|-----|------|")
                
                for i, zs in enumerate(zhongshu_list):
                    is_current = (i == len(zhongshu_list) - 1)
                    if is_current:
                        # 当前中枢，根据signal状态添加标注
                        status = signal.get('status', '')
                        if latest_structure_segment and latest_structure_segment.get('segment_type') == 'connector':
                            nature = f"**最近确认结构中枢**（后续过渡结构延伸至{latest_structure_segment['end_date']}）"
                        elif '突破中枢' in status:
                            nature = "**当前结构中枢**（🔥今日突破）"
                        elif '跌破并落入下中枢区间' in status:
                            nature = "**当前结构中枢**（🚨今日暴跌·已落入下一中枢）"
                        elif '跌破中枢' in status:
                            nature = "**当前结构中枢**（⚠️今日跌破·空仓观望）"
                        else:
                            nature = "**当前结构中枢**"
                    else:
                        nature = "已完成"
                    report.append(f"| 第{i+1}结构中枢 | {zs['start_date']}~{zs['end_date']} | {zs['zg']:.2f} | {zs['zd']:.2f} | {nature} |")
                
                report.append("")

            connector_segments = [s for s in structure_segments if s.get('segment_type') == 'connector']
            if connector_segments and not DISPLAY_MVP_MODE:
                report.append("**过渡结构保留**：")
                report.append("| 过渡结构 | 时间区间 | K线数 | 角色 |")
                report.append("|--------|----------|-------|------|")
                for idx, seg in enumerate(connector_segments[-3:], 1):
                    role_map = {
                        'leading': '前置过渡',
                        'between': '中枢间过渡',
                        'trailing': '尾部过渡',
                    }
                    role = role_map.get(seg.get('connector_role', ''), '过渡结构')
                    report.append(f"| 第{idx}过渡结构 | {seg['start_date']}~{seg['end_date']} | {seg['kline_count']} | {role} |")
                report.append("")
        else:
            report.append("> **⚠️ 大盘中枢分析**：数据异常，请查看详细分析")
            report.append("")
    else:
        report.append("> **⚠️ 大盘中枢分析**：数据获取失败，基于情绪指标判断仓位")
        report.append("")
    
    report.append("---")
    report.append("")
    
    # ========== 1. 智能分析阶段 ==========
    # 调用智能分析函数
    # ========== 一、核心结论（决策看板） ==========
    report.append("## 一、核心结论（决策看板）")
    report.append("")
    
    # 这里直接复用前面已构建的市场相位上下文，避免日报前后半段各自推导。
    
    report.append("<!-- MARKET_RESEARCH_SNAPSHOT_PLACEHOLDER -->")
    report.append("")

    # 资金偏好（从整合热榜分析）
    integrated_hot_data = data.get('integrated_hot_data', {})
    high_board_count = integrated_hot_data.get('high_board_count', 0)

    if DISPLAY_MVP_MODE:
        report.append("<!-- CORE_MVP_DIGEST_PLACEHOLDER -->")
        report.append("")
    else:
        # ========== 🎯 主线方向 ==========
        report.append("### 🎯 主线方向")
        primary_mainline = exit_analysis.get('sector_name', '') or (main_sectors[0] if main_sectors else '')
        if primary_mainline:
            report.append(f"- **核心主攻线**: {primary_mainline}")
        else:
            report.append("- **核心主攻线**: 暂无明确主线")

        if high_board_count > 3:
            report.append(f"- **资金偏好**: 高位连板股（资金追高意愿强，{high_board_count}只高位连板）")
        else:
            report.append(f"- **资金偏好**: 低位启动股（资金谨慎，高位连板仅{high_board_count}只）")

        report.append("")

        # ========== 💰 仓位决策 ==========
        report.append("### 💰 仓位决策")
        report.append(f"- **市场环境档位**: {position_level}")
        report.append(f"- **主线状态**: {overall_level}（{exit_analysis.get('overall_action', '未知')}）")
        if exit_analysis.get('overall_score') is not None and exit_analysis.get('mainline_score_pct') is not None:
            report.append(
                f"- **主线连续评分**: 主线{exit_analysis.get('mainline_score_pct'):.1f}分 / 总体{exit_analysis.get('overall_score'):.1f}分"
            )
        score_detail = exit_analysis.get('score_detail', {}) or {}
        if score_detail:
            score_parts = [f"{name}{_safe_float(score):.1f}" for name, score in score_detail.items()]
            if score_parts:
                report.append(f"- **六维拆解**: {' / '.join(score_parts)}")
            strongest = max(score_detail.items(), key=lambda x: _safe_float(x[1]))
            weakest = min(score_detail.items(), key=lambda x: _safe_float(x[1]))
            report.append(f"- **当前强项**: {strongest[0]} {_safe_float(strongest[1]):.1f}分")
            report.append(f"- **当前短板**: {weakest[0]} {_safe_float(weakest[1]):.1f}分")
        mainline_components = exit_analysis.get('mainline_component_scores', {}) or {}
        if mainline_components:
            component_parts = [f"{name}{_safe_float(score):.1f}" for name, score in mainline_components.items()]
            report.append(f"- **主线内部分项**: {' / '.join(component_parts)}")
        if exit_analysis.get('mainline_trend_label'):
            report.append(f"- **主线连续性**: {exit_analysis.get('mainline_trend_label')}")
        report.append(f"- **最终操作状态**: {final_gate.get('operation_state', position_level)}")
        report.append(f"- **明天具体怎么做**: {final_gate['final_action']}")
        report.append(f"- **环境推导**: {display_position_reason}")
        if final_gate.get('gate_reason'):
            report.append(f"- **主线修正**: {final_gate.get('gate_reason')}")
        report.append(f"- **怎么执行**: {get_execution_framework_text()}")

        # 如果有价格区间信息且允许新开仓，才显示
        if price_info and final_gate['can_new_entry']:
            report.append(f"- **日线预估买入区间**: {price_info['buy_range']}元")
            report.append(f"- **硬止损底线**: {price_info['stop_loss']}元")
            report.append(f"- **止盈观察位**: {price_info['take_profit']}元")
            report.append(f"- **执行说明**: {price_info.get('stop_rule', '盘中以30分钟结构止损为准')}")

        report.append("")

        # ========== ⚠️ 明天要防什么 ==========
        report.append("### ⚠️ 明天要防什么")
        risk_count = 0

        # 高位连板股风险
        if high_board_count > 5:
            report.append(f"- 🔴 高位连板股占比过高（{high_board_count}只），需警惕分歧风险")
            risk_count += 1

        # 跌停数风险
        if dt_count > 5:
            report.append(f"- 🔴 跌停数较多（{dt_count}只），市场风险偏好下降")
            risk_count += 1

        # 成交额风险
        if turnover < 7000:
            report.append(f"- 🟡 成交额不足（{turnover:.0f}亿），市场参与度低")
            risk_count += 1

        # 涨跌比风险
        if rise_fall_ratio < 0.5:
            report.append(f"- 🔴 涨跌比过低（{up_count}:{down_count}），市场情绪低迷")
            risk_count += 1

        # 异动监控风险
        abnormal_risk = data.get('abnormal_risk', [])
        if abnormal_risk:
            report.append(f"- 🟡 异动监控显示{len(abnormal_risk)}只股票存在潜在风险")
            risk_count += 1

        if risk_count == 0:
            report.append("- ✅ 暂无明显风险信号")

        report.append("")
    
    prohibition_position_level = display_position_level or position_level
    prohibition_operation_state = display_operation_state or final_gate.get('operation_state', '观察态')
    prohibition_result = build_prohibition_section_contract(
        prohibition_position_level,
        prohibition_operation_state,
        environment_headline=environment_headline,
        has_personal_positions=has_personal_positions,
        final_gate=final_gate,
        main_sectors=main_sectors,
        exit_analysis=exit_analysis,
    )
    replace_placeholder_lines(report, "<!-- PROHIBITION_PLACEHOLDER -->", prohibition_result.get('lines', []))
    
    report.append("")
    
    # ========== 二、预期日历（AI智能分析板块） ==========
    report.append("## 二、预期日历（AI智能分析板块）")
    report.append("")
    
    if data.get('calendar_events'):
        # 收集所有事件涉及的产业链方向
        all_directions = []
        calendar_analysis = []
        
        # 智能重打分关键词
        HIGH_IMPACT_KEYWORDS = ['证监会', '美联储', '央行', '政策', '监管', '重磅', '突发', '危机']
        MEDIUM_IMPACT_KEYWORDS = ['大会', '博览会', '展览', '峰会', '论坛', '发布会', '新品', '调价', '涨价']
        
        def smart_score_event(title: str, original_star: int) -> int:
            """基于事件内容进行智能重打分"""
            # 如果原始星级<=3，保持原样（财联社已经打过低分）
            if original_star <= 3:
                return original_star
            
            # 对原始5星事件进行细分
            title_lower = title.lower()
            
            # 高影响力事件（5星）
            if any(kw in title_lower for kw in HIGH_IMPACT_KEYWORDS):
                return 5
            
            # 涉及具体公司/产品发布的（4星）
            if any(kw in title_lower for kw in ['开启', '上市', '预售', '推出', '发布']):
                return 4
            
            # 行业会议/展览（3星）
            if any(kw in title_lower for kw in MEDIUM_IMPACT_KEYWORDS):
                return 3
            
            # 其他（2星）
            return 2
        
        # 批量分析所有事件（减少API调用次数）
        event_count = len(data['calendar_events'])
        estimated_time = max(15, event_count * 1.5)  # 预估每事件1.5秒，最少15秒
        batch_size = 8
        total_batches = (event_count + batch_size - 1) // batch_size
        
        print(f"   🤖 LLM智能分析 {event_count} 个财经事件...")
        print(f"      ⏱  预计耗时 {estimated_time:.0f}-{estimated_time*1.5:.0f} 秒（分{total_batches}批处理，每批约10-15秒）")
        print(f"      💡 分析内容包括：产业链方向识别、细分板块归类、炒作逻辑生成...")
        batch_start = time.time()
        
        # 准备批量分析数据
        events_for_analysis = [
            {'title': e.get('title', ''), 'summary': ''}
            for e in data['calendar_events']
        ]
        
        # 批量调用LLM
        try:
            client = get_llm_service()
            batch_results = client.analyze_events_batch(events_for_analysis, batch_size=batch_size)
            batch_elapsed = time.time() - batch_start
            print(f"   ✅ 批量分析完成 [⏱ {batch_elapsed:.2f}s]")
            
            # 更新LLM统计（批量分析）
            global _llm_call_stats
            _llm_call_stats['total_calls'] += 1  # 统计为1次批量调用
            _llm_call_stats['total_time'] += batch_elapsed
            _llm_call_stats['event_analysis_calls'] += len(events_for_analysis)  # 但按事件数统计
            _llm_call_stats['event_analysis_time'] += batch_elapsed
        except Exception as e:
            print(f"   ⚠️ 批量分析失败: {e}，回退到关键词匹配")
            batch_results = [_keyword_match_event_sectors(e.get('title', '')) for e in data['calendar_events']]
        
        # 处理结果
        for i, event in enumerate(data['calendar_events']):
            date = event.get('date', '')
            title = event.get('title', '')
            original_star = event.get('star', 0)
            
            # 智能重打分
            smart_star = smart_score_event(title, original_star)
            star = "⭐" * min(smart_star, 5)
            
            # 获取批量分析结果
            ai_analysis = batch_results[i] if i < len(batch_results) else _keyword_match_event_sectors(title)
            
            calendar_analysis.append({
                'date': date,
                'title': title,
                'star': star,
                'ai_analysis': ai_analysis
            })
            
            all_directions.append(ai_analysis['main_direction'])
        
        # 统计产业链方向分布（排除"其他"）
        from collections import Counter
        direction_counts = Counter(all_directions)
        # 过滤掉"其他"分类，只展示真正的产业链方向
        top_directions = [(d, c) for d, c in direction_counts.most_common(10) if d != "其他"][:5]
        
        # 显示产业链方向统计（排除"其他"）
        if top_directions:
            report.append("### 近期产业链热点分布")
            report.append("| 产业链方向 | 事件数量 | 热度 |")
            report.append("|-----------|---------|------|")
            for direction, count in top_directions:
                heat = "🔥" * min(count, 5)
                report.append(f"| {direction} | {count}个事件 | {heat} |")
            report.append("")
        
        # 显示详细事件列表
        report.append("### 重点事件明细")
        report.append("| 日期 | 事件 | 重要度 | 产业链方向 | 预期 | 博弈方向 |")
        report.append("|------|------|--------|-----------|------|---------|")
        
        # 显示所有事件明细（未来30天内）
        for item in calendar_analysis:
            date = item['date']
            title = item['title']
            star = item['star']
            ai = item['ai_analysis']
            
            # 构建预期标识
            expectation_icon = {"利好": "📈", "利空": "📉", "中性": "➖"}.get(ai['expectation'], "➖")
            
            # 智能判断博弈方向
            if any(keyword in title for keyword in ['会议', '发布', '启动', '开幕']):
                direction = "抢跑/兑现"
            elif any(keyword in title for keyword in ['风险', '警告', '谨慎', '监管']):
                direction = "回避"
            elif ai['expectation'] == '利好':
                direction = "关注埋伏"
            elif ai['expectation'] == '利空':
                direction = "回避/对冲"
            else:
                direction = "观望"
            
            report.append(f"| {date} | {title} | {star} | {ai['main_direction']} | {expectation_icon}{ai['expectation']} | {direction} |")
        
        report.append("")
        
        # AI深度分析总结
        report.append("### AI板块关联分析")
        # 提取所有涉及的细分板块（过滤空值和占位符）
        all_sectors = []
        for item in calendar_analysis:
            sectors = item['ai_analysis'].get('related_sectors', [])
            # 过滤空字符串和占位符
            filtered = [s for s in sectors if s and s not in ['需盘面确认', '相关产业链标的', '其他']]
            all_sectors.extend(filtered)
        unique_sectors = list(set(all_sectors))[:10]
        
        if unique_sectors:
            report.append(f"**涉及细分板块**：{'、'.join(unique_sectors)}")
            report.append("")
        
        # 炒作预期总结
        bullish_events = [item for item in calendar_analysis if item['ai_analysis']['expectation'] == '利好']
        if bullish_events:
            report.append(f"**利好预期方向**：{len(bullish_events)}个事件")
            for item in bullish_events[:3]:
                report.append(f"- {item['ai_analysis']['main_direction']}: {item['title'][:30]}...")
            report.append("")
        
        # 产业链方向AI归纳
        if len(top_directions) >= 2 and not DISPLAY_MVP_MODE:
            # 使用ai_analyze_sector_relationships进行板块归纳
            sectors_for_analysis = [d[0] for d in top_directions if d[0] != '其他']
            if sectors_for_analysis:
                chain_analysis = ai_analyze_sector_relationships(sectors_for_analysis, "日历事件产业链分析")
                if chain_analysis.get('insights'):
                    report.append(f"**产业链洞察**：")
                    report.append(f"> {chain_analysis['insights']}")
                    report.append("")
    else:
        report.append("| - | 暂无重要事件 | - | - | - | - |")
    report.append("")
    
    market_trend_section = build_market_trend_sections_contract(data, target_date)
    report.extend(market_trend_section.get('lines', []))
    
    stock_full_info = data.get('stock_full_info', {})
    market_activity_sections = build_market_activity_report_sections(
        data,
        target_date,
        stock_full_info,
        get_stock_status=get_stock_status,
        get_stock_sector=get_stock_sector,
        analyze_candlestick_pattern=analyze_candlestick_pattern,
    )
    report.extend(market_activity_sections.get('lines', []))
    
    market_and_sector_analysis = build_market_and_sector_analysis_contract(
        data,
        market_analysis,
        sh_change,
        indices,
        exit_analysis,
        main_sectors_info,
        secondary_sectors_info,
        ai_group_concepts_into_chains=ai_group_concepts_into_chains,
    )
    report.extend(market_and_sector_analysis.get('lines', []))
    
    advanced_activity_sections = build_advanced_activity_report_sections(
        data,
        stock_full_info,
        get_stock_sector=get_stock_sector,
        analyze_candlestick_pattern=analyze_candlestick_pattern,
    )
    report.extend(advanced_activity_sections.get('lines', []))
    
    board_tag_analysis_sections = build_board_tag_analysis_sections_contract(
        data,
        analyze_sector_distribution=analyze_sector_distribution,
    )
    report.extend(board_tag_analysis_sections.get('lines', []))
    
    exchange_monitor_sections = build_exchange_monitor_sections_contract(data)
    report.extend(exchange_monitor_sections.get('lines', []))

    execution_stage_lookup = build_execution_stage_lookup(DEFAULT_EXECUTION_STAGE_SPECS)
    candidate_stage_label = get_execution_stage_label(execution_stage_lookup, "candidate_selection")

    # 辅助函数：当Step 0预判为DIFFICULT且环境极端恶劣时，输出空仓结论
    def _build_no_trade_conclusion(report, target_date, prediction, reason, dt_count, up_down_ratio):
        # 此时report已经包含狙击手视角标题和Step 0内容，只需追加结论部分
        report.append("#### 最终结论")
        report.append("| 项目 | 结论 | 理由 |")
        report.append("|------|------|------|")
        report.append(f"| 明日环境预判 | 🔴 极度困难 | {reason} |")
        report.append("| 明天观察池 | 无 | 环境恶劣，没有活口 |")
        report.append(f"| 明日核心股 | 无 | 未进入{candidate_stage_label} |")
        report.append("| 明日策略 | 空仓观望 | 等待市场情绪修复 |")
        report.append("")
        report.append("**明日计划**: 等待市场情绪修复，跌停<15只、涨跌比>0.8时再评估。即使修复，也只轻仓试错。")
        report.append("")
        return "\n".join(report)

    # 十三、统一执行链（原狙击手视角）
    report.append("## 十三、统一执行链（狙击手视角）")
    report.append("### 总-市场整体判断")
    report.append("")

    # 获取中证全指数据
    csci_change = 0
    if data.get('wind_a_alternative'):
        csci_change = data['wind_a_alternative'].get('涨跌幅', data['wind_a_alternative'].get('change_pct', 0))
    
    # 主线退出分析和最终门控已在前面构建，此处直接使用
    print(f"   ✅ 龙头股票: {len(dragon_stocks)} 只")
    print(f"   ✅ 主线退出分析完成: {exit_analysis.get('sector_name', '未知')}")
    print(f"   ✅ 最终执行门控: {final_gate.get('final_action', '未知')}")

    report.append(f"- **基准指数**: 中证全指涨跌幅{csci_change:+.2f}%")
    # 更新市场特征描述，基于智能分析
    primary_mainline = exit_analysis.get('sector_name', '') or (main_sectors[0] if main_sectors else '')
    if '暂无明确主线' in str(primary_mainline):
        primary_mainline = ''
    if primary_mainline:
        report.append(f"- **市场特征**: {market_trend}，主攻线{primary_mainline}领涨")
    else:
        report.append(f"- **市场特征**: {market_trend}，板块轮动快速")
    report.append("")
    
    report.append("### 分-六步决策路径")
    report.append("")
    
    
    # 狙击手视角主骨架（v3.0隔日预判模式重构）
    # ========================================
    # 核心交易哲学：在热点纷呈的中国一二级资本市场，如果没有定力，不能保持智力上的独立与诚实，很难不随波逐流。
    # 任何事件、题材、预期日历都只能作为辅助偏向性因子，不能凌驾于价格、趋势、抗性和转折确认之上。
    # 
    # v3.0重大改进：从"当日分析"改为"隔日预判"
    # 基于今日收盘数据 → 预判明日开盘环境 → 给出明日操作指引
    # ========================================
    
    market_research_bundle = build_market_research_context_bundle(
        data,
        target_date,
        exit_analysis=exit_analysis,
        final_gate=final_gate,
        position_level=position_level,
        main_sectors_info=main_sectors_info,
        secondary_sectors_info=secondary_sectors_info,
        main_sectors=main_sectors,
        secondary_sectors=secondary_sectors,
        dragon_stocks=dragon_stocks,
    )
    execution_stage_specs = build_execution_stage_specs(
        {
            "environment_follow": build_environment_follow_stage,
            "watch_pool": build_watch_pool_stage,
            "candidate_selection": build_candidate_selection_stage,
            "risk_review": build_risk_review_stage,
            "entry_plan": build_entry_plan_stage,
            "pk_decision": build_pk_decision_stage,
        },
        enabled_stage_keys=["environment_follow", "watch_pool", "candidate_selection", "risk_review", "entry_plan", "pk_decision"],
    )
    execution_stage_result = run_registered_execution_stages(
        execution_stage_specs,
        stage_context={
            "data": data,
            "target_date": target_date,
            "exit_analysis": exit_analysis,
            "dragon_stocks": dragon_stocks,
            "main_sectors": main_sectors,
            "position_level": position_level,
            "display_mvp_mode": DISPLAY_MVP_MODE,
            "market_research_bundle": market_research_bundle,
            "final_gate": final_gate,
            "render_market_research_snapshot_section": _render_market_research_snapshot_section,
            "render_step0_follow_section": _render_step0_follow_section,
            "is_degraded_abnormal_snapshot": _is_degraded_abnormal_snapshot,
            "format_abnormal_observation_columns": _format_abnormal_observation_columns,
            "build_step2_candidate_bundle": build_step2_candidate_bundle,
            "render_gem_breathing_step2_section": _render_gem_breathing_step2_section,
            "build_step3_risk_bundle": build_step3_risk_bundle,
            "render_gem_breathing_pool_section": _render_gem_breathing_pool_section,
            "quant_system_available": QUANT_SYSTEM_AVAILABLE,
            "stop_prior_low_trading_days": STOP_PRIOR_LOW_TRADING_DAYS,
            "run_mode": run_mode,
            "position_reason": position_reason,
            "step0_prediction": step0_prediction if 'step0_prediction' in locals() else '',
            "step0_prediction_cn": step0_prediction_cn if 'step0_prediction_cn' in locals() else '',
            "step0_action": step0_action if 'step0_action' in locals() else '',
            "high_board_count": high_board_count,
            "has_personal_positions": has_personal_positions,
            "normalize_stock_code": normalize_stock_code,
            "get_execution_framework_text": get_execution_framework_text,
            "get_trade_permission": get_trade_permission,
            "fetch_recent_price_bars": fetch_recent_price_bars,
            "evaluate_live_tradability": evaluate_live_tradability,
            "build_intraday_execution_plan": build_intraday_execution_plan,
            "build_stop_execution_plan": build_stop_execution_plan,
            "enrich_stop_plan_with_reference_anchors": _enrich_stop_plan_with_reference_anchors,
            "build_waiting_stock_plan": build_waiting_stock_plan,
            "finalize_waiting_candidate": _finalize_waiting_candidate,
            "build_trade_price_focus": _build_trade_price_focus,
            "build_observation_price_focus_text": _build_observation_price_focus_text,
            "append_price_focus_note": _append_price_focus_note,
            "append_observation_price_focus_note": _append_observation_price_focus_note,
            "compose_observation_focus_text": _compose_observation_focus_text,
            "build_front_structure_layer_text": _build_front_structure_layer_text,
            "analyze_buy_signal": analyze_buy_signal if QUANT_SYSTEM_AVAILABLE else None,
            "safe_float": _safe_float,
            "ai_analyze_sector_relationships": ai_analyze_sector_relationships,
            "score_execution_candidate": score_execution_candidate,
            "score_candidate_decision_stack": score_candidate_decision_stack,
            "sort_decision_stack_candidates": sort_decision_stack_candidates,
            "sort_watch_anchor_candidates": sort_watch_anchor_candidates,
            "build_strategy_ev_calibration": build_strategy_ev_calibration,
            "build_abnormal_watch_anchor_candidates": _build_abnormal_watch_anchor_candidates,
            "select_priority_watch_anchor": _select_priority_watch_anchor,
            "derive_watch_anchor_type": _derive_watch_anchor_type,
            "derive_watch_anchor_note": _derive_watch_anchor_note,
            "build_abnormal_probe_group": _build_abnormal_probe_group,
            "build_special_probe_verdict": _build_special_probe_verdict,
            "build_position_sizing_decision": _build_position_sizing_decision,
            "build_front_follow_action_text": _build_front_follow_action_text,
            "build_special_probe_focus_text": _build_special_probe_focus_text,
            "build_philosophy_constraint_text": _build_philosophy_constraint_text,
            "render_core_mvp_digest": _render_core_mvp_digest,
            "render_mvp_focus_summary": _render_mvp_focus_summary,
            "should_surface_price_note": _should_surface_price_note,
            "build_observation_price_note_text": _build_observation_price_note_text,
            "append_watch_anchor_note": _append_watch_anchor_note,
            "build_candidate_exit_rules": _build_candidate_exit_rules,
            "format_holding_window_text": _format_holding_window_text,
            "render_pk_decision_section": render_pk_decision_section,
            "render_action_plan_section": render_action_plan_section,
            "decision_stack_order_text": DECISION_STACK_ORDER_TEXT,
            "today_predictions": today_predictions,
            "nextday_predictions": nextday_predictions,
        },
        stage_lookup=execution_stage_lookup,
    )
    report.extend(execution_stage_result.get("lines", []))
    data.setdefault("module_logs", []).extend(execution_stage_result.get("module_logs", []))

    execution_stage_context = execution_stage_result.get("context", {}) or {}
    zt_pool_by_sector = execution_stage_context.get('zt_pool_by_sector', {}) or {}
    dt_pool_by_sector = execution_stage_context.get('dt_pool_by_sector', {}) or {}
    zt_pool = execution_stage_context.get('zt_pool', []) or []
    hot_stocks = execution_stage_context.get('hot_stocks', []) or []
    active_a_kill_records = execution_stage_context.get('active_a_kill_records', []) or []
    candidates = execution_stage_context.get('candidates', []) or []
    watchlist = execution_stage_context.get('watchlist', []) or []
    filtered_by_a_kill = execution_stage_context.get('filtered_by_a_kill', []) or []
    mainline_name = execution_stage_context.get('mainline_name', '')
    stock_meta_map = execution_stage_context.get('stock_meta_map', {}) or {}
    abnormal_watch_pool_all = execution_stage_context.get('abnormal_watch_pool_all', []) or []
    abnormal_watch_pool = execution_stage_context.get('abnormal_watch_pool', []) or []
    abnormal_watch_map = execution_stage_context.get('abnormal_watch_map', {}) or {}
    sector_trend_snapshot_step1 = execution_stage_context.get('sector_trend_snapshot_step1', []) or []
    leader_memory_bank = execution_stage_context.get('leader_memory_bank', []) or []
    tracking_memory_status = execution_stage_context.get('tracking_memory_status', {}) or {}
    mainline_competition_snapshot = execution_stage_context.get('mainline_competition_snapshot', []) or []
    observation_snapshot = execution_stage_context.get('observation_snapshot', {}) or {}
    market_research_snapshot = execution_stage_context.get('market_research_snapshot', {}) or {}
    market_state_snapshot = execution_stage_context.get('market_state_snapshot', {}) or {}
    abnormal_projection_summary = execution_stage_context.get('abnormal_projection_summary', {}) or {}
    step0_plan = execution_stage_context.get('step0_plan', {}) or {}
    step0_prediction = execution_stage_context.get('step0_prediction', 'NEUTRAL')
    step0_prediction_cn = execution_stage_context.get('step0_prediction_cn', step0_prediction)
    step0_reason = execution_stage_context.get('step0_reason', '')
    step0_action = execution_stage_context.get('step0_action', '')
    step2_bundle = execution_stage_context.get('step2_bundle', {}) or {}
    evaluated_stocks = execution_stage_context.get('evaluated_stocks', []) or []
    core_stocks = execution_stage_context.get('core_stocks', []) or []
    secondary_stocks = execution_stage_context.get('secondary_stocks', []) or []
    ignored_stocks = execution_stage_context.get('ignored_stocks', []) or []
    crossline_observation_stocks = execution_stage_context.get('crossline_observation_stocks', []) or []
    gem_observation_stocks = execution_stage_context.get('gem_observation_stocks', []) or []
    sector_trend_snapshot = execution_stage_context.get('sector_trend_snapshot', []) or []
    extreme_conviction_list = execution_stage_context.get('extreme_conviction_list', []) or []
    mainline_in_quadrant = execution_stage_context.get('mainline_in_quadrant')
    mainline_score = execution_stage_context.get('mainline_score', 0)
    step3_bundle = execution_stage_context.get('step3_bundle', {}) or {}
    delete_group = execution_stage_context.get('delete_group', []) or []
    keep_group = execution_stage_context.get('keep_group', []) or []
    focus_group = execution_stage_context.get('focus_group', []) or []
    abnormal_green_count = execution_stage_context.get('abnormal_green_count', 0)
    abnormal_red_count = execution_stage_context.get('abnormal_red_count', 0)
    risk_sectors_from_dt = execution_stage_context.get('risk_sectors_from_dt', []) or []
    mainline_a_kill = execution_stage_context.get('mainline_a_kill', False)
    mainline_dt_stocks = execution_stage_context.get('mainline_dt_stocks', []) or []
    structural_a_kill = execution_stage_context.get('structural_a_kill', False)
    structural_reason = execution_stage_context.get('structural_reason', '')
    a_kill_blacklist_updates = execution_stage_context.get('a_kill_blacklist_updates', []) or []
    conviction_codes = execution_stage_context.get('conviction_codes', set()) or set()
    leader_memory_codes = execution_stage_context.get('leader_memory_codes', set()) or set()
    executable_stocks = execution_stage_context.get('executable_stocks', []) or []
    waiting_stocks = execution_stage_context.get('waiting_stocks', []) or []
    untradable_stocks = execution_stage_context.get('untradable_stocks', []) or []
    rejected_stocks = execution_stage_context.get('rejected_stocks', []) or []
    trade_gate_open = execution_stage_context.get('trade_gate_open', False)
    best_stock = execution_stage_context.get('best_stock')
    runner_up = execution_stage_context.get('runner_up')
    watch_anchor = execution_stage_context.get('watch_anchor')
    watch_anchor_type = execution_stage_context.get('watch_anchor_type', '')
    abnormal_probe_group = execution_stage_context.get('abnormal_probe_group', {}) or {}
    special_probe_verdict = execution_stage_context.get('special_probe_verdict', {}) or {}
    position_decision = execution_stage_context.get('position_decision', {}) or {}
    front_structure_layer_text = execution_stage_context.get('front_structure_layer_text', '')
    front_follow_action_text = execution_stage_context.get('front_follow_action_text', '')
    special_probe_text = execution_stage_context.get('special_probe_text', '')
    philosophy_constraint_text = execution_stage_context.get('philosophy_constraint_text', '')
    scored_executable_stocks = execution_stage_context.get('scored_executable_stocks', []) or []
    replace_placeholder_lines(
        report,
        "<!-- CORE_MVP_DIGEST_PLACEHOLDER -->",
        execution_stage_context.get("core_mvp_digest_lines", []),
    )
    replace_placeholder_lines(
        report,
        "<!-- MVP_FOCUS_SUMMARY_PLACEHOLDER -->",
        execution_stage_context.get("mvp_focus_summary_lines", []),
    )
    abnormal_probe_parts = []
    if abnormal_probe_group:
        mainline_probe_text = _format_abnormal_probe_text(
            abnormal_probe_group.get('mainline_abnormal_probe'),
            role_label='主线异动里先看谁',
            mainline_name=mainline_name,
            fallback_watch_anchor=abnormal_probe_group.get('fallback_watch_anchor'),
        )
        crossline_probe_text = _format_abnormal_probe_text(
            abnormal_probe_group.get('crossline_abnormal_probe'),
            role_label='跨线异动里先看谁',
            mainline_name=mainline_name,
        )
        validation_probe_text = _format_abnormal_probe_text(
            abnormal_probe_group.get('validation_probe'),
            role_label='承接验证先看谁',
            mainline_name=mainline_name,
        )
        if mainline_probe_text:
            abnormal_probe_parts.append(f"主线异动里先看谁：{mainline_probe_text}")
        if crossline_probe_text:
            abnormal_probe_parts.append(f"跨线异动里先看谁：{crossline_probe_text}")
        if validation_probe_text:
            abnormal_probe_parts.append(f"承接验证先看谁：{validation_probe_text}")

    report.extend(
        build_legacy_final_conclusion_lines(
            {
                "display_mvp_mode": DISPLAY_MVP_MODE,
                "step0_prediction": step0_prediction,
                "step0_prediction_cn": step0_prediction_cn,
                "step0_action": step0_action,
                "final_gate": final_gate,
                "mainline_name": mainline_name,
                "mainline_label": _build_front_mainline_label(
                    market_research_snapshot,
                    fallback_mainline=mainline_name or "",
                ),
                "watchlist_count": len(watchlist),
                "core_count": len(core_stocks),
                "secondary_count": len(secondary_stocks),
                "crossline_count": len(step2_bundle.get('crossline_observation_stocks', [])),
                "abnormal_watch_count": len(abnormal_watch_pool),
                "front_structure_layer_text": front_structure_layer_text,
                "trade_gate_open": trade_gate_open,
                "best_stock": best_stock,
                "watch_anchor": watch_anchor,
                "watch_anchor_type": watch_anchor_type,
                "front_follow_action_text": front_follow_action_text,
                "abnormal_probe_parts": abnormal_probe_parts,
            }
        )
    )
    
    # 核心交易哲学 / 补充视角 / AI市场洞察总结
    mainline_name = exit_analysis.get('sector_name', '')
    report.extend(render_mainline_discipline_section(mainline_name))
    report.extend(render_supplementary_perspective_section(supplementary_perspective))

    mainline_from_exit = exit_analysis.get('sector_name', '') if exit_analysis else ''
    if mainline_from_exit:
        main_sectors_str = mainline_from_exit
    elif main_sectors_info:
        main_sector_names = [s['name'] for s in main_sectors_info[:2]]
        main_sectors_str = "、".join(main_sector_names)
    else:
        main_sectors_str = "暂无明确主线"
    
    if risk_sectors:
        risk_sector_names = [s['name'] for s in risk_sectors[:2]]
        risk_sectors_str = "、".join(risk_sector_names)
    else:
        risk_sectors_str = "暂无明确风险"

    report.extend(
        render_ai_market_insight_section(
            {
                "market_trend": market_trend,
                "zt_count": zt_count,
                "dt_count": dt_count,
                "energy_state": market_state_snapshot.get('energy_state', '未知'),
                "flow_direction": market_state_snapshot.get('flow_direction', '-'),
                "mainline_text": main_sectors_str,
                "risk_text": risk_sectors_str,
                "focus_text": f"{main_sectors_str if main_sectors_str != '暂无明确主线' else '市场整体'}持续性，量能变化，板块轮动",
            }
        )
    )

    strategy_factor_snapshot = _build_strategy_factor_snapshot(
        target_date,
        data,
        market_zhongshu,
        final_gate,
        exit_analysis,
        position_level,
        position_reason,
        {
            'best_stock': best_stock,
            'runner_up': runner_up,
            'watch_anchor': watch_anchor,
            'watch_anchor_type': watch_anchor_type,
            'abnormal_probe_group': abnormal_probe_group,
            'market_research_snapshot': market_research_snapshot,
            'abnormal_watch_pool': abnormal_watch_pool,
            'leader_memory_bank': leader_memory_bank,
            'tracking_memory_status': tracking_memory_status,
            'sector_trend_snapshot': sector_trend_snapshot,
            'main_sectors_info': main_sectors_info or [{'name': name} for name in main_sectors[:2]],
            'secondary_sectors_info': secondary_sectors_info or [{'name': name} for name in secondary_sectors[:2]],
            'mainline_in_quadrant': mainline_in_quadrant,
            'mainline_score': mainline_score,
            'scored_executable_stocks': scored_executable_stocks,
            'position_decision': position_decision,
        },
    )
    strategy_plan_context = _build_strategy_plan_context(
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
        factor_snapshot=strategy_factor_snapshot,
    )
    if persist_strategy_tracking:
        strategy_performance_summary = update_strategy_performance_book(
            data,
            target_date,
            strategy_plan_context,
            market_zhongshu,
            ledger_mode=run_mode,
        )
        data['strategy_tracking'] = {
            'plan': strategy_plan_context,
            'performance_summary': strategy_performance_summary,
        }
    else:
        strategy_tracking = data.get('strategy_tracking', {}) or {}
        strategy_performance_summary = strategy_tracking.get('performance_summary')
        if not strategy_performance_summary:
            strategy_performance_summary = update_strategy_performance_book(
                data,
                target_date,
                strategy_plan_context,
                market_zhongshu,
                ledger_mode=run_mode,
            )
            data['strategy_tracking'] = {
                'plan': strategy_plan_context,
                'performance_summary': strategy_performance_summary,
            }
    append_strategy_performance_section(report, strategy_performance_summary)
    
    # 【已删除v2.3.34】十五、隔日操作计划（功能与狙击手视角重复，用户要求移除）
    

    timer_summary = data.get('timer_summary', {})
    step_status = data.get('step_status', {})
    normalized_timer_steps = _normalize_report_timer_steps(timer_summary, step_status) if timer_summary else []
    total_time = timer_summary.get('total_time', 0) if timer_summary else 0
    import datetime as _dt
    report.extend(
        render_execution_appendix(
            {
                "data_status": data.get('data_status', {}),
                "step_status": step_status,
                "normalized_timer_steps": normalized_timer_steps,
                "total_time": total_time,
                "target_date": target_date,
                "generated_at": _dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "report_version": "v2.5.0",
            }
        )
    )

    if DISPLAY_MVP_MODE:
        report = _compact_report_for_mvp(report)

    return "\n".join(report)


def _normalize_report_timer_steps(timer_summary, step_status=None):
    step_status = step_status or {}
    ordered_keys = []
    steps_by_key = {}

    for item in (timer_summary.get('steps', []) or []):
        if not isinstance(item, (list, tuple)) or len(item) < 3:
            continue

        label = str(item[0] or '').strip()
        elapsed = _safe_float(item[1])
        cumulative = _safe_float(item[2])
        matched_key = ''

        for key, value in step_status.items():
            if key and key in label:
                matched_key = key
                if value:
                    label = label.replace('(失败)', '').strip()
                break

        dedup_key = matched_key or label
        existing = steps_by_key.get(dedup_key)
        candidate = [label, elapsed, cumulative]

        if not existing:
            ordered_keys.append(dedup_key)
            steps_by_key[dedup_key] = candidate
            continue

        existing_label = existing[0]
        if '步骤' in existing_label and '步骤' not in label:
            steps_by_key[dedup_key] = [
                existing_label,
                elapsed if elapsed > 0 else existing[1],
                max(existing[2], cumulative),
            ]
        else:
            steps_by_key[dedup_key] = candidate

    return [tuple(steps_by_key[key]) for key in ordered_keys]


def parse_position_string(position_str):
    """解析持仓字符串
    
    Args:
        position_str: 持仓字符串，格式: "我的仓位是神剑股份 28% 通达股份 23% 新中港 12% 北大医药 7%"
    
    Returns:
        list: 持仓列表，每个元素是 {"name": "股票名称", "position": 仓位比例}
    """
    import re
    
    # 移除"我的仓位是"前缀
    position_str = position_str.replace("我的仓位是", "").strip()
    
    # 使用正则匹配"股票名称 仓位%"格式
    pattern = r'([^\d\s]+)\s+(\d+(?:\.\d+)?)\s*%'
    matches = re.findall(pattern, position_str)
    
    positions = []
    for name, position in matches:
        positions.append({
            "name": name.strip(),
            "position": float(position)
        })
    
    return positions


def analyze_position_management(data, target_date, positions):
    return analyze_position_management_report(
        data=data,
        positions=positions,
        build_trading_philosophy_lines=_build_trading_philosophy_lines,
        display_mvp_mode=DISPLAY_MVP_MODE,
    )

def replay_from_snapshot(target_date, refresh_sources=None):
    """从快照读数据，只重新拉指定数据源，然后用最新skill逻辑重新生成报告"""
    result = build_replay_snapshot_contract(
        target_date,
        refresh_sources=refresh_sources,
        load_data_snapshot=load_data_snapshot,
        tencent_factory=TencentFinanceData,
        get_major_indices_from_iwencai=get_major_indices_from_iwencai,
        safe_float=_safe_float,
    )
    return result.get('data'), result.get('target_date', target_date)


def _inject_report_variant_banner(report_text, variant):
    from daily_report_render import _inject_report_variant_banner as _render_inject_report_variant_banner

    return _render_inject_report_variant_banner(report_text, variant)


def _render_report_with_display_mode(
    display_mvp_mode,
    data,
    target_date,
    supplementary_perspective="",
    has_personal_positions=False,
    run_mode=LEDGER_MODE_FROZEN,
    persist_strategy_tracking=True,
):
    from daily_report_render import _render_report_with_display_mode as _render_report_with_display_mode_impl

    return _render_report_with_display_mode_impl(
        display_mvp_mode,
        data,
        target_date,
        supplementary_perspective=supplementary_perspective,
        has_personal_positions=has_personal_positions,
        run_mode=run_mode,
        persist_strategy_tracking=persist_strategy_tracking,
    )


def build_report_outputs(
    data,
    target_date,
    supplementary_perspective="",
    has_personal_positions=False,
    run_mode=LEDGER_MODE_FROZEN,
    position_report_text="",
):
    from daily_report_render import build_report_outputs as _build_report_outputs_impl

    return _build_report_outputs_impl(
        data,
        target_date,
        supplementary_perspective=supplementary_perspective,
        has_personal_positions=has_personal_positions,
        run_mode=run_mode,
        position_report_text=position_report_text,
    )


def save_report_output(report_text, target_date, mode=LEDGER_MODE_FROZEN, variant=REPORT_VARIANT_FULL):
    from daily_report_render import save_report_output as _save_report_output_impl

    return _save_report_output_impl(report_text, target_date, mode=mode, variant=variant)


def save_report_outputs(report_outputs, target_date, mode=LEDGER_MODE_FROZEN):
    from daily_report_render import save_report_outputs as _save_report_outputs_impl

    return _save_report_outputs_impl(report_outputs, target_date, mode=mode)


def _get_stock_diagnostic_output_path(target_date, stock_code, mode=LEDGER_MODE_FROZEN):
    from daily_report_render import _get_stock_diagnostic_output_path as _render_get_stock_diagnostic_output_path

    return _render_get_stock_diagnostic_output_path(target_date, stock_code, mode=mode)


def save_stock_diagnostic_output(report_text, target_date, stock_code, mode=LEDGER_MODE_FROZEN):
    from daily_report_render import save_stock_diagnostic_output as _save_stock_diagnostic_output_impl

    return _save_stock_diagnostic_output_impl(report_text, target_date, stock_code, mode=mode)


def resolve_single_stock_snapshot(data, stock_code, stock_name='', market_research_bundle=None, step2_bundle=None):
    result = resolve_single_stock_snapshot_contract(
        data,
        stock_code,
        stock_name=stock_name,
        market_research_bundle=market_research_bundle,
        step2_bundle=step2_bundle,
        normalize_stock_code=normalize_stock_code,
        get_stock_sector=get_stock_sector,
        fetch_recent_price_bars=fetch_recent_price_bars,
        safe_float=_safe_float,
        compute_bar_change_pct=_compute_bar_change_pct,
    )
    return result.get('stock', {})


def generate_single_stock_diagnostic_markdown(
    data,
    target_date,
    stock_code,
    stock_name='',
    run_mode=LEDGER_MODE_FROZEN,
):
    """生成和日报同一推导链的单票诊断。"""
    result = build_single_stock_diagnostic_contract(
        data,
        target_date,
        stock_code,
        stock_name=stock_name,
        run_mode=run_mode,
        build_market_phase_context=build_market_phase_context,
        build_market_research_context_bundle=build_market_research_context_bundle,
        build_step2_candidate_bundle=build_step2_candidate_bundle,
        build_step3_risk_bundle=build_step3_risk_bundle,
        resolve_single_stock_snapshot=resolve_single_stock_snapshot,
        normalize_stock_code=normalize_stock_code,
        get_trade_permission=get_trade_permission,
        fetch_recent_price_bars=fetch_recent_price_bars,
        evaluate_live_tradability=evaluate_live_tradability,
        get_abnormal_follow_risk_signal=get_abnormal_follow_risk_signal,
        safe_float=_safe_float,
        analyze_buy_signal=analyze_buy_signal,
        quant_system_available=QUANT_SYSTEM_AVAILABLE,
        build_intraday_execution_plan=build_intraday_execution_plan,
        build_stop_execution_plan=build_stop_execution_plan,
        enrich_stop_plan_with_reference_anchors=_enrich_stop_plan_with_reference_anchors,
        stop_prior_low_trading_days=STOP_PRIOR_LOW_TRADING_DAYS,
        score_candidate_decision_stack=score_candidate_decision_stack,
        score_execution_candidate=score_execution_candidate,
        build_strategy_ev_calibration=build_strategy_ev_calibration,
        build_trade_price_focus=_build_trade_price_focus,
        render_single_stock_diagnostic_markdown=render_single_stock_diagnostic_markdown,
    )
    return result.get('markdown', '')


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='A股日报数据获取入口 - SKILL.md对齐版')
    parser.add_argument('date', nargs='?', default=None,
                       help='目标日期，格式: YYYY-MM-DD (默认: 昨天)')
    parser.add_argument('--no-report', action='store_true',
                       help='不生成报告文件，只获取数据')
    parser.add_argument('-p', '--position', type=str, default=None,
                       help='持仓信息，格式: "我的仓位是股票1 仓位1% 股票2 仓位2% ..."')
    parser.add_argument('--replay', action='store_true',
                       help='复盘模式：从快照读数据，只重新拉财联社日历，用最新skill生成报告')
    parser.add_argument('--stock', type=str, default=None,
                       help='生成单票诊断，输入股票代码，如 002364')
    parser.add_argument('--stock-name', type=str, default='',
                       help='单票诊断可选股票名称，提升可读性')
    
    args = parser.parse_args()
    
    if args.date:
        target_date = args.date
    else:
        import datetime as _dt
        today = _dt.datetime.now()
        yesterday = today - _dt.timedelta(days=1)
        target_date = yesterday.strftime("%Y-%m-%d")

    if args.replay:
        data, target_date = replay_from_snapshot(target_date)
    else:
        print(f"📅 获取数据: {target_date}")
        data = get_daily_data(target_date)
    run_mode = LEDGER_MODE_REPLAY if args.replay else LEDGER_MODE_FROZEN
    if run_mode == LEDGER_MODE_FROZEN:
        official_ledger = load_strategy_performance_ledger(mode=LEDGER_MODE_FROZEN)
        official_record = _find_strategy_record(official_ledger.get('records', []), target_date)
        official_report_path = _get_report_output_path(target_date, mode=LEDGER_MODE_FROZEN)
        if official_record or os.path.exists(official_report_path):
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
            else:
                print(f"   ⚠️ 持仓信息解析失败，请检查格式")

        position_report = ""
        if positions:
            position_report = analyze_position_management(data, target_date, positions)

        report_outputs = build_report_outputs(
            data,
            target_date,
            supplementary_perspective="",
            has_personal_positions=bool(positions),
            run_mode=run_mode,
            position_report_text=position_report,
        )
        save_report_outputs(report_outputs, target_date, mode=run_mode)

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
        _save_data_snapshot(data, target_date, mode=run_mode)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
