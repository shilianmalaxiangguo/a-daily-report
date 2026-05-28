from __future__ import annotations

from report.monitoring_pool_support import (
    build_monitoring_pool_summary,
    collect_monitoring_pool_candidates,
)

__all__ = [
    "append_strategy_performance_section",
    "build_strategy_factor_snapshot",
    "build_strategy_plan_context",
    "normalize_report_timer_steps",
    "update_strategy_performance_book",
]

_MISSING = object()


def _install_runtime_bindings(bindings):
    previous = {}
    module_globals = globals()
    for key, value in (bindings or {}).items():
        if key.startswith("__") and key.endswith("__"):
            continue
        previous[key] = module_globals.get(key, _MISSING)
        module_globals[key] = value
    return previous


def _restore_runtime_bindings(previous):
    module_globals = globals()
    for key, value in (previous or {}).items():
        if value is _MISSING:
            module_globals.pop(key, None)
        else:
            module_globals[key] = value


def build_strategy_factor_snapshot(
    target_date,
    data,
    market_zhongshu,
    final_gate,
    exit_analysis,
    position_level,
    position_reason,
    context,
    *,
    helpers=None,
):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _build_strategy_factor_snapshot_legacy_body(
            target_date,
            data,
            market_zhongshu,
            final_gate,
            exit_analysis,
            position_level,
            position_reason,
            context,
        )
    finally:
        _restore_runtime_bindings(previous)


def build_strategy_plan_context(
    target_date,
    data,
    market_zhongshu,
    final_gate,
    exit_analysis,
    position_level,
    position_reason,
    best_stock=None,
    watch_anchor=None,
    watch_anchor_type="重点观察谁",
    factor_snapshot=None,
    *,
    helpers=None,
):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _build_strategy_plan_context_legacy_body(
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
        )
    finally:
        _restore_runtime_bindings(previous)


def append_strategy_performance_section(report, performance_summary, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _append_strategy_performance_section_legacy_body(report, performance_summary)
    finally:
        _restore_runtime_bindings(previous)


def update_strategy_performance_book(data, target_date, plan_context, market_zhongshu, ledger_mode="frozen", *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _update_strategy_performance_book_legacy_body(
            data,
            target_date,
            plan_context,
            market_zhongshu,
            ledger_mode=ledger_mode,
        )
    finally:
        _restore_runtime_bindings(previous)


def normalize_report_timer_steps(timer_summary, step_status=None, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _normalize_report_timer_steps_legacy_body(timer_summary, step_status=step_status)
    finally:
        _restore_runtime_bindings(previous)


def _build_strategy_factor_snapshot_legacy_body(
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
        selection_anchor_type = '50%标准进攻预演'
    else:
        selection_anchor_type = context.get('watch_anchor_type', '')

    return {
        'version': STRATEGY_FACTOR_SNAPSHOT_VERSION,
        'report_date': target_date,
        'core_stocks': [dict(item) for item in (context.get('core_stocks', []) or [])],
        'secondary_stocks': [dict(item) for item in (context.get('secondary_stocks', []) or [])],
        'crossline_observation_stocks': [dict(item) for item in (context.get('crossline_observation_stocks', []) or [])],
        'gem_observation_stocks': [dict(item) for item in (context.get('gem_observation_stocks', []) or [])],
        'generic_watch_stocks': [dict(item) for item in (context.get('generic_watch_stocks', []) or [])],
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
                    'participation_mode': str(position_decision.get('participation_mode', '') or 'attack_50_ready').strip(),
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


def _build_strategy_plan_context_legacy_body(
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
        anchor_type = '50%标准进攻预演'
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
                trigger_text = f"50%标准进攻预演：09:50-10:10窗口内站上{confirm_price:.2f}且条件成立后再执行"
            else:
                trigger_text = "50%标准进攻预演：固定交易窗口内条件成立后再执行，普通结构只看09:50-10:10窗口"
        elif confirm_price:
            trigger_text = f"09:50-10:10站上{confirm_price:.2f}后，再回到{entry_low:.2f}-{entry_high:.2f}区间内执行"
        elif entry_low is not None and entry_high is not None:
            trigger_text = f"触及{entry_low:.2f}-{entry_high:.2f}并09:50-10:10窗口满足条件"
    elif plan_stock:
        if final_gate.get('can_new_entry') and '候选' in anchor_type:
            confirm_price = _round_or_none(minute_plan.get('confirm_price_60m'))
            if confirm_price:
                trigger_text = f"{anchor_type}，先看09:50-10:10站上{confirm_price:.2f}，再判断能否走成明天唯一能买的那只"
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


def _append_strategy_performance_section_legacy_body(report, performance_summary):
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


def _update_strategy_performance_book_legacy_body(data, target_date, plan_context, market_zhongshu, ledger_mode="frozen"):
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
    monitoring_context = {
        'core_stocks': current_record.get('factor_snapshot', {}).get('core_stocks', []) or current_record.get('core_stocks', []) or [],
        'secondary_stocks': current_record.get('factor_snapshot', {}).get('secondary_stocks', []) or current_record.get('secondary_stocks', []) or [],
        'crossline_observation_stocks': current_record.get('factor_snapshot', {}).get('crossline_observation_stocks', []) or current_record.get('crossline_observation_stocks', []) or [],
        'gem_observation_stocks': current_record.get('factor_snapshot', {}).get('gem_observation_stocks', []) or current_record.get('gem_observation_stocks', []) or [],
        'generic_watch_stocks': current_record.get('factor_snapshot', {}).get('generic_watch_stocks', []) or current_record.get('generic_watch_stocks', []) or [],
    }
    if 'build_monitoring_pool_summary' in globals() and callable(build_monitoring_pool_summary):
        monitoring_helpers = {}
        if 'fetch_daily_price_bars' in globals() and callable(fetch_daily_price_bars):
            monitoring_helpers['fetch_daily_price_bars'] = fetch_daily_price_bars
        summary['monitoring_pool'] = build_monitoring_pool_summary(
            monitoring_context,
            target_date,
            helpers=monitoring_helpers,
        )
    elif 'collect_monitoring_pool_candidates' in globals() and callable(collect_monitoring_pool_candidates):
        summary['monitoring_pool'] = collect_monitoring_pool_candidates(monitoring_context)
    else:
        summary['monitoring_pool'] = {'main_pool': [], 'secondary_pool': []}
    return summary


def _normalize_report_timer_steps_legacy_body(timer_summary, step_status=None):
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
