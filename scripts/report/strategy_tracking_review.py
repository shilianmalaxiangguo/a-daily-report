from __future__ import annotations

__all__ = [
    "NEAT_FREAK_ATTRIBUTION_BUCKETS",
    "build_gem_structure_cycle_cards",
    "build_self_calibration_summary",
    "build_structure_cycle_gem_summary",
    "build_system_graduation_dashboard",
    "classify_gem_breathing_week_sample",
    "classify_neat_freak_attribution_bucket",
    "classify_strategy_record_attribution",
    "classify_structure_cycle_result",
    "extract_gem_breathing_contract_snapshot",
    "normalize_neat_freak_attribution_bucket",
    "summarize_gem_breathing_week_review",
    "summarize_setup_signal_review",
    "summarize_strategy_attribution",
    "summarize_structure_cycles",
]

_MISSING = object()

NEAT_FREAK_ATTRIBUTION_BUCKETS = {
    "handoff_buying_misjudged": {"category": "handoff_buying_misjudged", "label": "后手买盘错估"},
    "reward_space_insufficient": {"category": "reward_space_insufficient", "label": "收益空间不足"},
    "focus_scattered": {"category": "focus_scattered", "label": "火力分散"},
    "state_judgment_lag": {"category": "state_judgment_lag", "label": "状态判断慢"},
    "trigger_too_strict": {"category": "trigger_too_strict", "label": "触发过严"},
    "stop_loss_not_executed": {"category": "stop_loss_not_executed", "label": "止损不执行"},
    "data_error": {"category": "data_error", "label": "数据错误"},
}
NEAT_FREAK_ATTRIBUTION_BUCKET_ORDER = {
    category: index
    for index, category in enumerate(NEAT_FREAK_ATTRIBUTION_BUCKETS)
}

_NEAT_FREAK_CATEGORY_MAP = {
    "env_too_strict": "trigger_too_strict",
    "stock_right_env_blocked": "trigger_too_strict",
    "trigger_too_strict": "trigger_too_strict",
    "signal_not_triggered": "trigger_too_strict",
    "weak_to_strong_missed": "state_judgment_lag",
    "gem_prep_upgrade_lag": "state_judgment_lag",
    "entry_cycle_lag": "state_judgment_lag",
    "special_probe_lag": "state_judgment_lag",
    "state_misread": "state_judgment_lag",
    "profit_take_early": "reward_space_insufficient",
    "profit_take_correct": "reward_space_insufficient",
    "exit_cycle_too_early": "reward_space_insufficient",
    "execution_flat": "reward_space_insufficient",
}

_DATA_ERROR_MARKERS = ("data_error", "invalid_data", "数据错误")
_EXIT_ACTION_MARKERS = ("exit", "sell", "止损", "退出", "卖出")


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


def _copy_neat_freak_bucket(category):
    bucket = NEAT_FREAK_ATTRIBUTION_BUCKETS.get(category) or NEAT_FREAK_ATTRIBUTION_BUCKETS["state_judgment_lag"]
    return dict(bucket)


def _string_has_any_marker(value, markers):
    text = str(value or "").strip().lower()
    return bool(text and any(str(marker).lower() in text for marker in markers))


def _any_field_has_marker(payload, fields, markers):
    return any(_string_has_any_marker((payload or {}).get(field), markers) for field in fields)


def _mapping_get_nested(mapping, path):
    current = mapping or {}
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _as_positive_int(value):
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _neat_freak_safe_float(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _factor_snapshot_for_neat_freak(record):
    factor_snapshot = (record or {}).get("factor_snapshot", {}) or {}
    return factor_snapshot if isinstance(factor_snapshot, dict) else {}


def _non_empty_mapping(value):
    return bool(isinstance(value, dict) and value)


def _list_len(value):
    return len(value) if isinstance(value, list) else 0


def _has_neat_freak_data_error(record):
    record = record or {}
    sim = record.get("simulation", {}) or {}
    fields = ("source_status", "status", "data_status", "error_type", "category", "label", "reason")
    return _any_field_has_marker(record, fields, _DATA_ERROR_MARKERS) or _any_field_has_marker(sim, fields, _DATA_ERROR_MARKERS)


def _has_neat_freak_focus_scattered(record):
    record = record or {}
    factor_snapshot = _factor_snapshot_for_neat_freak(record)
    unique_target_count = max(
        _as_positive_int(record.get("unique_target_count")),
        _as_positive_int(factor_snapshot.get("unique_target_count")),
        _as_positive_int(_mapping_get_nested(factor_snapshot, ("selection", "unique_target_count"))),
    )
    single_focus_status = (
        record.get("single_focus_constraint_status")
        or _mapping_get_nested(record, ("single_focus_constraint", "status"))
        or _mapping_get_nested(factor_snapshot, ("single_focus_constraint", "status"))
        or _mapping_get_nested(factor_snapshot, ("selection", "single_focus_constraint", "status"))
    )
    execute_candidate_count = max(
        _list_len(_mapping_get_nested(record, ("candidate_stack", "execute_candidates"))),
        _list_len(_mapping_get_nested(factor_snapshot, ("candidate_stack", "execute_candidates"))),
    )
    has_runner_up = any(
        _non_empty_mapping(value)
        for value in (
            record.get("runner_up"),
            _mapping_get_nested(record, ("selection", "runner_up")),
            _mapping_get_nested(factor_snapshot, ("selection", "runner_up")),
        )
    )
    return unique_target_count > 1 or single_focus_status == "multiple_candidates" or execute_candidate_count > 1 or has_runner_up


def _handoff_buying_evidence(record):
    record = record or {}
    factor_snapshot = _factor_snapshot_for_neat_freak(record)
    return (
        record.get("handoff_buying_evidence")
        or _mapping_get_nested(record, ("handoff_buying", "evidence"))
        or _mapping_get_nested(record, ("reasoning_decision", "handoff_buying_evidence"))
        or factor_snapshot.get("handoff_buying_evidence")
        or _mapping_get_nested(factor_snapshot, ("handoff_buying", "evidence"))
        or _mapping_get_nested(factor_snapshot, ("reasoning_decision", "handoff_buying_evidence"))
        or _mapping_get_nested(factor_snapshot, ("selection", "handoff_buying_evidence"))
    )


def _has_neat_freak_handoff_misjudged(record):
    record = record or {}
    evidence = str(_handoff_buying_evidence(record) or "").strip().lower()
    if not evidence or evidence in ("clear", "明确", "strong", "confirmed"):
        return False
    sim = record.get("simulation", {}) or {}
    action_type = str(record.get("action_type", "") or "").strip()
    triggered = bool(sim.get("triggered"))
    executed = action_type == "execute" or triggered
    loss = any(
        _neat_freak_safe_float(sim.get(field)) < 0
        for field in ("strategy_return_worst", "strategy_return_best", "alpha_return_worst", "alpha_return_best")
    )
    return bool(executed and loss)


def _has_neat_freak_stop_loss_not_executed(record):
    record = record or {}
    sim = record.get("simulation", {}) or {}
    breached = bool(
        record.get("stop_loss_breached")
        or sim.get("stop_loss_breached")
        or _string_has_any_marker(record.get("status"), ("stop_loss_breached",))
        or _string_has_any_marker(sim.get("status"), ("stop_loss_breached",))
    )
    action_text = " ".join(
        str(value or "")
        for value in (
            record.get("action"),
            record.get("action_type"),
            record.get("actual_action"),
            sim.get("action"),
            sim.get("exit_reason"),
        )
    )
    return bool(breached and not _string_has_any_marker(action_text, _EXIT_ACTION_MARKERS))


def classify_neat_freak_attribution_bucket(record, attribution=None):
    attribution = attribution or {}
    if _has_neat_freak_data_error(record):
        return _copy_neat_freak_bucket("data_error")
    if _has_neat_freak_stop_loss_not_executed(record):
        return _copy_neat_freak_bucket("stop_loss_not_executed")
    if _has_neat_freak_handoff_misjudged(record):
        return _copy_neat_freak_bucket("handoff_buying_misjudged")
    if _has_neat_freak_focus_scattered(record):
        return _copy_neat_freak_bucket("focus_scattered")

    category = str(attribution.get("category", "") or "").strip()
    label = str(attribution.get("label", "") or "").strip()
    if category in _NEAT_FREAK_CATEGORY_MAP:
        return _copy_neat_freak_bucket(_NEAT_FREAK_CATEGORY_MAP[category])
    if category == "data_error" or label == "数据错误":
        return _copy_neat_freak_bucket("data_error")
    if category == "stop_loss_not_executed" or label == "止损不执行":
        return _copy_neat_freak_bucket("stop_loss_not_executed")
    if category == "handoff_buying_misjudged" or label == "后手买盘错估":
        return _copy_neat_freak_bucket("handoff_buying_misjudged")
    if category == "focus_scattered" or label == "火力分散":
        return _copy_neat_freak_bucket("focus_scattered")
    if category == "reward_space_insufficient" or label == "收益空间不足":
        return _copy_neat_freak_bucket("reward_space_insufficient")
    if category == "trigger_too_strict" or "触发过严" in label:
        return _copy_neat_freak_bucket("trigger_too_strict")
    return _copy_neat_freak_bucket("state_judgment_lag")


def normalize_neat_freak_attribution_bucket(record, attribution=None):
    attribution = attribution or {}
    existing = attribution.get("neat_freak_bucket") if isinstance(attribution, dict) else {}
    if isinstance(existing, dict):
        existing_category = str(existing.get("category", "") or "").strip()
        if existing_category in NEAT_FREAK_ATTRIBUTION_BUCKETS:
            return _copy_neat_freak_bucket(existing_category)
    return classify_neat_freak_attribution_bucket(record, attribution)


def _attach_neat_freak_attribution_bucket(record, attribution):
    attribution = dict(attribution or {})
    attribution["neat_freak_bucket"] = normalize_neat_freak_attribution_bucket(record, attribution)
    return attribution


def classify_strategy_record_attribution(record, as_of_date, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        attribution = _classify_strategy_record_attribution_legacy_body(record, as_of_date)
        return _attach_neat_freak_attribution_bucket(record, attribution)
    finally:
        _restore_runtime_bindings(previous)


def summarize_strategy_attribution(records, start_date, end_date, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _summarize_strategy_attribution_legacy_body(records, start_date, end_date)
    finally:
        _restore_runtime_bindings(previous)


def summarize_setup_signal_review(records, start_date, end_date, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _summarize_setup_signal_review_legacy_body(records, start_date, end_date)
    finally:
        _restore_runtime_bindings(previous)


def extract_gem_breathing_contract_snapshot(record, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _extract_gem_breathing_contract_snapshot_legacy_body(record)
    finally:
        _restore_runtime_bindings(previous)


def classify_gem_breathing_week_sample(record, as_of_date, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _classify_gem_breathing_week_sample_legacy_body(record, as_of_date)
    finally:
        _restore_runtime_bindings(previous)


def summarize_gem_breathing_week_review(records, start_date, end_date, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _summarize_gem_breathing_week_review_legacy_body(records, start_date, end_date)
    finally:
        _restore_runtime_bindings(previous)


def build_self_calibration_summary(
    records,
    start_date,
    end_date,
    windows=None,
    attribution_summary=None,
    setup_summary=None,
    ev_summary=None,
    gem_week_review=None,
    *,
    helpers=None,
):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _build_self_calibration_summary_legacy_body(
            records,
            start_date,
            end_date,
            windows=windows,
            attribution_summary=attribution_summary,
            setup_summary=setup_summary,
            ev_summary=ev_summary,
            gem_week_review=gem_week_review,
        )
    finally:
        _restore_runtime_bindings(previous)


def classify_structure_cycle_result(window_summary, attribution_summary, gem_cycle_review=None, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _classify_structure_cycle_result_legacy_body(
            window_summary,
            attribution_summary,
            gem_cycle_review=gem_cycle_review,
        )
    finally:
        _restore_runtime_bindings(previous)


def build_structure_cycle_gem_summary(gem_cycle_review, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _build_structure_cycle_gem_summary_legacy_body(gem_cycle_review)
    finally:
        _restore_runtime_bindings(previous)


def build_gem_structure_cycle_cards(records, as_of_date, limit=6, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _build_gem_structure_cycle_cards_legacy_body(records, as_of_date, limit=limit)
    finally:
        _restore_runtime_bindings(previous)


def summarize_structure_cycles(records, as_of_date, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _summarize_structure_cycles_legacy_body(records, as_of_date)
    finally:
        _restore_runtime_bindings(previous)


def build_system_graduation_dashboard(
    records,
    cycle_reviews,
    source_label="当前账本",
    current_plan=None,
    gem_week_review=None,
    *,
    helpers=None,
):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _build_system_graduation_dashboard_legacy_body(
            records,
            cycle_reviews,
            source_label=source_label,
            current_plan=current_plan,
            gem_week_review=gem_week_review,
        )
    finally:
        _restore_runtime_bindings(previous)


def _classify_strategy_record_attribution(record, as_of_date):
    attribution = _classify_strategy_record_attribution_legacy_body(record, as_of_date)
    return _attach_neat_freak_attribution_bucket(record, attribution)


def _summarize_strategy_attribution(records, start_date, end_date):
    return _summarize_strategy_attribution_legacy_body(records, start_date, end_date)


def _summarize_setup_signal_review(records, start_date, end_date):
    return _summarize_setup_signal_review_legacy_body(records, start_date, end_date)


def _extract_gem_breathing_contract_snapshot(record):
    return _extract_gem_breathing_contract_snapshot_legacy_body(record)


def _classify_gem_breathing_week_sample(record, as_of_date):
    return _classify_gem_breathing_week_sample_legacy_body(record, as_of_date)


def _summarize_gem_breathing_week_review(records, start_date, end_date):
    return _summarize_gem_breathing_week_review_legacy_body(records, start_date, end_date)


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
    return _build_self_calibration_summary_legacy_body(
        records,
        start_date,
        end_date,
        windows=windows,
        attribution_summary=attribution_summary,
        setup_summary=setup_summary,
        ev_summary=ev_summary,
        gem_week_review=gem_week_review,
    )


def _classify_structure_cycle_result(window_summary, attribution_summary, gem_cycle_review=None):
    return _classify_structure_cycle_result_legacy_body(
        window_summary,
        attribution_summary,
        gem_cycle_review=gem_cycle_review,
    )


def _build_structure_cycle_gem_summary(gem_cycle_review):
    return _build_structure_cycle_gem_summary_legacy_body(gem_cycle_review)


def _build_gem_structure_cycle_cards(records, as_of_date, limit=6):
    return _build_gem_structure_cycle_cards_legacy_body(records, as_of_date, limit=limit)


def _summarize_structure_cycles(records, as_of_date):
    return _summarize_structure_cycles_legacy_body(records, as_of_date)


def _build_system_graduation_dashboard(records, cycle_reviews, source_label="当前账本", current_plan=None, gem_week_review=None):
    return _build_system_graduation_dashboard_legacy_body(
        records,
        cycle_reviews,
        source_label=source_label,
        current_plan=current_plan,
        gem_week_review=gem_week_review,
    )


def _classify_strategy_record_attribution_legacy_body(record, as_of_date):
    action_type = record.get("action_type", "no_trade")
    sim = record.get("simulation", {}) or {}
    path_metrics = _collect_record_market_path(record, as_of_date)
    observed_return = path_metrics.get("observed_return")
    benchmark_return = _safe_float(sim.get("benchmark_return"))
    anchor_alpha = (observed_return - benchmark_return) if observed_return is not None else None

    attribution = {
        "category": "unclassified",
        "label": "待归因",
        "reason": "记录不够，暂无法归因",
        "observed_stock_return": observed_return,
        "anchor_alpha": anchor_alpha,
        "max_runup": path_metrics.get("max_runup"),
        "max_drawdown": path_metrics.get("max_drawdown"),
        "post_exit_extension": path_metrics.get("post_exit_extension"),
    }
    market_energy_state = record.get("market_energy_state", "")
    record_mainline_name = str(record.get("mainline_name", "") or "").strip()

    if action_type in ("watch_only", "no_trade"):
        selection_snapshot = (record.get("factor_snapshot", {}) or {}).get("selection", {}) or {}
        feedback_ready = bool(record.get("candidate_feedback_ready") or selection_snapshot.get("candidate_feedback_ready"))
        participation_mode = str(record.get("participation_mode", "") or selection_snapshot.get("participation_mode", "") or "").strip()
        anchor_type = str(record.get("anchor_type", "") or "").strip()
        contract_kind = str(record.get("contract_kind", "") or selection_snapshot.get("contract_kind", "") or "").strip()
        contract_right_side_trigger_price = _round_or_none(record.get("contract_right_side_trigger_price") or selection_snapshot.get("contract_right_side_trigger_price"))
        contract_reset_breakout_price = _round_or_none(record.get("contract_reset_breakout_price") or selection_snapshot.get("contract_reset_breakout_price"))
        contract_void_price = _round_or_none(record.get("contract_void_price") or selection_snapshot.get("contract_void_price"))
        max_drawdown = path_metrics.get("max_drawdown")
        weak_to_strong_context = _build_weak_to_strong_context(
            candidate={
                "name": record.get("stock_name", ""),
                "code": record.get("stock_code", ""),
                "sector": record.get("stock_sector", ""),
                "abnormal_follow_state": record.get("abnormal_follow_state", ""),
                "abnormal_setup_signal_id": record.get("abnormal_setup_signal_id", ""),
            },
            mainline_name=record_mainline_name,
            state_machine_snapshot={
                "leading_line": record_mainline_name,
                "energy_state": market_energy_state,
                "pulse_stage": record.get("mainline_pulse_stage", ""),
            },
        )
        if (
            weak_to_strong_context.get("active")
            and participation_mode == "observe_0"
            and observed_return is not None
            and observed_return >= 0.06
            and (anchor_alpha is not None and anchor_alpha > 0.02)
            and (path_metrics.get("max_runup") is None or path_metrics.get("max_runup") >= 0.08)
            and (max_drawdown is None or max_drawdown >= -0.05)
        ):
            attribution.update({
                "category": "weak_to_strong_missed",
                "label": "弱转强识别偏慢",
                "reason": "主线内强基底假弱样本后续已经走成超预期转强，说明它原本是假弱非真弱，但系统仍停在观察层，弱转强识别偏慢。",
            })
        elif (
            contract_kind == "gem_breathing_20cm"
            and participation_mode == "observe_0"
            and observed_return is not None
            and observed_return >= 0.03
            and (anchor_alpha is not None and anchor_alpha > 0.015)
            and (path_metrics.get("max_runup") is None or path_metrics.get("max_runup") >= 0.05)
            and (max_drawdown is None or max_drawdown >= -0.05)
        ):
            breakout_text = f"重新站上{contract_reset_breakout_price:.2f}再突破位" if contract_reset_breakout_price is not None else "走成右侧确认/再突破"
            guard_text = f"且始终没失守{contract_void_price:.2f}观察边界" if contract_void_price is not None else ""
            trigger_text = f"右侧确认位{contract_right_side_trigger_price:.2f}" if contract_right_side_trigger_price is not None else "右侧确认"
            attribution.update({
                "category": "gem_prep_upgrade_lag",
                "label": "20cm右侧确认偏慢",
                "reason": f"创业板20cm预启动样本已经{breakout_text}{guard_text}，但系统仍停在观察层，说明{trigger_text}后的升级偏慢。",
            })
        elif (
            anchor_type in ("受限观察对象", "明天唯一能买的那只", "主线异常先看谁")
            and feedback_ready
            and participation_mode == "observe_0"
            and observed_return is not None
            and observed_return >= 0.03
            and (anchor_alpha is not None and anchor_alpha > 0.02)
            and (path_metrics.get("max_runup") is None or path_metrics.get("max_runup") >= 0.08)
            and (max_drawdown is None or max_drawdown >= -0.05)
        ):
            attribution.update({
                "category": "entry_cycle_lag",
                "label": "介入周期偏慢",
                "reason": "唯一对象已经在次日给出确认成功的价格行为，但系统仍停在观察层，说明介入周期判断偏慢。",
            })
        elif feedback_ready and participation_mode == "observe_0" and observed_return is not None and observed_return >= 0.08:
            attribution.update({
                "category": "special_probe_lag",
                "label": "特殊探针已先行但仍停在观察层",
                "reason": "特殊标的反馈已经明显走强，但系统仍停在0%不参与层，说明探针到执行层的切换偏慢。",
            })
        elif (
            observed_return is not None
            and observed_return >= 0.08
            and benchmark_return >= 0.03
            and market_energy_state in ("收缩防守", "试探修复")
        ):
            attribution.update({
                "category": "state_misread",
                "label": "状态判断偏差",
                "reason": "后续市场进入明显扩张，但报告日仍按收缩/观察处理，说明对状态变化反应偏慢。",
            })
        elif observed_return is not None and observed_return >= 0.05 and benchmark_return >= 0.015:
            attribution.update({
                "category": "env_too_strict",
                "label": "环境过滤过严",
                "reason": "系统没有出手，但重点观察谁与指数同步走强，说明环境过滤偏严。",
            })
        elif observed_return is not None and observed_return >= 0.05:
            attribution.update({
                "category": "stock_right_env_blocked",
                "label": "个股对了但环境条件未满足",
                "reason": "重点观察谁本身走强，但环境条件还没满足，属于少赚不是做错。",
            })
        elif benchmark_return <= 0 or (anchor_alpha is not None and anchor_alpha <= 0.02):
            attribution.update({
                "category": "defense_correct",
                "label": "防守正确",
                "reason": "不交易没有明显吃亏，避免了逆势或低质量出手。",
            })
        else:
            attribution.update({
                "category": "wait_and_see",
                "label": "继续等待",
                "reason": "观察对象没有形成足够强的相对优势，继续等待并不吃亏。",
            })
        return attribution

    if sim.get("status") in ("invalid_report_day_one_word", "invalid_consecutive_one_word", "continuation_only"):
        attribution.update({
            "category": "tradability_invalid",
            "label": "可交易性无效",
            "reason": "一字链条或延续持有只计观察，不计新增执行质量。",
        })
        return attribution

    if not sim.get("triggered"):
        if path_metrics.get("max_runup") is not None and path_metrics.get("max_runup") >= 0.08:
            attribution.update({
                "category": "trigger_too_strict",
                "label": "触发条件过严",
                "reason": "计划没有成交，但后续仍给出较大上冲，说明触发门槛偏紧。",
            })
        else:
            attribution.update({
                "category": "signal_not_triggered",
                "label": "信号未触发",
                "reason": "计划冻结正确，但盘中没有真正给到执行条件。",
            })
        return attribution

    midpoint_return = (
        _safe_float(sim.get("strategy_return_worst")) + _safe_float(sim.get("strategy_return_best"))
    ) / 2.0
    midpoint_alpha = (
        _safe_float(sim.get("alpha_return_worst")) + _safe_float(sim.get("alpha_return_best"))
    ) / 2.0
    exit_reason = sim.get("exit_reason", "")
    stock_sector = record.get("stock_sector", "")
    mainline_name = record.get("mainline_name", "")

    if (
        action_type == "execute"
        and midpoint_alpha <= -0.05
        and benchmark_return <= 0
        and exit_reason in ("stop_loss", "day5_close", "mark_to_market")
        and market_energy_state in ("扩张聚焦", "迁移竞争", "试探修复")
    ):
        attribution.update({
            "category": "state_misread",
            "label": "状态判断偏差",
            "reason": "报告日把环境理解得偏乐观，后续市场实际进入收缩，属于状态层判断过早进攻。",
        })
        return attribution

    if exit_reason == "stop_loss":
        if (path_metrics.get("post_exit_extension") or 0.0) >= 0.05:
            attribution.update({
                "category": "stop_then_rebound",
                "label": "止损正确但踏空",
                "reason": "先按纪律止损，后续价格又明显反抽，属于防守没错但有踏空。",
            })
        else:
            attribution.update({
                "category": "cut_loss_correct",
                "label": "错了就跑",
                "reason": "执行后不及预期，按照防守纪律快速离场是正确动作。",
            })
        return attribution

    if exit_reason == "active_sell_big_yang":
        if (path_metrics.get("post_exit_extension") or 0.0) >= 0.05:
            attribution.update({
                "category": "profit_take_early",
                "label": "赚了但卖早",
                "reason": "主动兑现没有错，但卖出后还有明显延伸空间。",
            })
        else:
            attribution.update({
                "category": "profit_take_correct",
                "label": "赚了主动卖",
                "reason": "盈利兑现与模式一致，收益兑现没有拖泥带水。",
            })
        return attribution

    if exit_reason in ("day3_close", "day4_close", "day5_close", "mark_to_market") and (path_metrics.get("post_exit_extension") or 0.0) >= 0.08:
        attribution.update({
            "category": "exit_cycle_too_early",
            "label": "退出周期过早结束",
            "reason": "这笔交易在固定日历退出后仍出现明显延伸，说明退出周期没有给横住续命/再突破重置留空间。",
        })
        return attribution

    if midpoint_alpha < -0.02:
        if stock_sector and mainline_name and not sector_name_matches(stock_sector, mainline_name):
            attribution.update({
                "category": "mainline_bias",
                "label": "主线判断偏差",
                "reason": "执行对象没有贴住主线，导致出手质量明显弱于环境。",
            })
        else:
            attribution.update({
                "category": "wrong_trade",
                "label": "做了但根本不该做",
                "reason": "执行后没有跑赢环境，说明这笔交易本身质量不够。",
            })
        return attribution

    if midpoint_alpha > 0:
        if (path_metrics.get("post_exit_extension") or 0.0) >= 0.05:
            attribution.update({
                "category": "profit_take_early",
                "label": "赚了但卖早",
                "reason": "整体交易是赚钱的，但退出节奏仍可以更耐心。",
            })
        else:
            attribution.update({
                "category": "execution_valid",
                "label": "执行有效",
                "reason": "执行结果跑赢环境，说明计划和执行都基本有效。",
            })
        return attribution

    attribution.update({
        "category": "execution_flat",
        "label": "执行一般",
        "reason": "交易没有明显犯错，但也没有形成足够超额。",
    })
    return attribution


def _summarize_strategy_attribution_legacy_body(records, start_date, end_date):
    scoped = [
        record for record in (records or [])
        if start_date <= _normalize_kline_date_str(record.get("report_date")) <= end_date
    ]

    grouped = {}
    highlights = []
    for record in scoped:
        attribution = record.get("attribution", {}) or {}
        neat_freak_bucket = attribution.get("neat_freak_bucket") if isinstance(attribution, dict) else {}
        if (
            not isinstance(neat_freak_bucket, dict)
            or neat_freak_bucket.get("category") not in NEAT_FREAK_ATTRIBUTION_BUCKETS
            or not neat_freak_bucket.get("label")
        ):
            neat_freak_bucket = normalize_neat_freak_attribution_bucket(record, attribution)
        label = neat_freak_bucket.get("label") or "状态判断慢"
        category = neat_freak_bucket.get("category") or "state_judgment_lag"
        legacy_label = attribution.get("label", "待归因")
        group = grouped.setdefault(category, {
            "category": category,
            "label": label,
            "count": 0,
            "sample": "",
            "legacy_label": legacy_label,
            "reason": attribution.get("reason", ""),
        })
        group["count"] += 1
        if not group.get("sample"):
            sample_name = record.get("stock_name") or record.get("anchor_type") or "无标的"
            if record.get("stock_code"):
                sample_name = f"{sample_name}({record.get('stock_code')})"
            group["sample"] = f"{record.get('report_date')} {sample_name}"
        if category not in ("defense_correct", "wait_and_see") and len(highlights) < 3:
            sample_name = record.get("stock_name") or record.get("anchor_type") or "无标的"
            if record.get("stock_code"):
                sample_name = f"{sample_name}({record.get('stock_code')})"
            highlights.append({
                "date": record.get("report_date", ""),
                "label": label,
                "stock": sample_name,
                "reason": attribution.get("reason", ""),
            })

    items = sorted(
        grouped.values(),
        key=lambda x: (-x.get("count", 0), NEAT_FREAK_ATTRIBUTION_BUCKET_ORDER.get(x.get("category", ""), 99)),
    )
    return {
        "start_date": start_date,
        "end_date": end_date,
        "total_count": len(scoped),
        "items": items,
        "highlights": highlights,
    }


def _summarize_setup_signal_review_legacy_body(records, start_date, end_date):
    scoped = [
        record for record in (records or [])
        if start_date <= _normalize_kline_date_str(record.get("report_date")) <= end_date
    ]

    grouped = {}
    for record in scoped:
        setup_id = str(record.get("abnormal_setup_signal_id", "") or "").strip()
        setup_label = str(record.get("abnormal_setup_signal_label", "") or "").strip()
        if not setup_id and not setup_label:
            continue

        item = grouped.setdefault(setup_id or setup_label, {
            "setup_id": setup_id or setup_label,
            "setup_label": setup_label or setup_id,
            "plan_count": 0,
            "execute_count": 0,
            "sample_count": 0,
            "strong_count": 0,
            "relative_win_count": 0,
            "return_sum": 0.0,
            "alpha_sum": 0.0,
        })
        item["plan_count"] += 1
        if record.get("action_type") == "execute":
            item["execute_count"] += 1

        attribution = record.get("attribution", {}) or {}
        observed_return = attribution.get("observed_stock_return")
        anchor_alpha = attribution.get("anchor_alpha")
        if observed_return is None and anchor_alpha is None:
            continue

        item["sample_count"] += 1
        item["return_sum"] += _safe_float(observed_return)
        item["alpha_sum"] += _safe_float(anchor_alpha)
        if observed_return is not None and observed_return >= 0.05:
            item["strong_count"] += 1
        if anchor_alpha is not None and anchor_alpha > 0.02:
            item["relative_win_count"] += 1

    items = []
    for item in grouped.values():
        sample_count = item.get("sample_count", 0)
        items.append({
            **item,
            "strong_rate": (item.get("strong_count", 0) / sample_count) if sample_count > 0 else None,
            "relative_win_rate": (item.get("relative_win_count", 0) / sample_count) if sample_count > 0 else None,
            "avg_return": (item.get("return_sum", 0.0) / sample_count) if sample_count > 0 else None,
            "avg_alpha": (item.get("alpha_sum", 0.0) / sample_count) if sample_count > 0 else None,
        })

    items.sort(
        key=lambda x: (
            x.get("sample_count", 0),
            _safe_float(x.get("avg_alpha")),
            _safe_float(x.get("relative_win_rate")),
        ),
        reverse=True,
    )
    return {
        "start_date": start_date,
        "end_date": end_date,
        "total_plan_count": len(scoped),
        "items": items,
    }


def _extract_gem_breathing_contract_snapshot_legacy_body(record):
    record = record or {}
    selection_snapshot = (record.get("factor_snapshot", {}) or {}).get("selection", {}) or {}
    contract_kind = str(record.get("contract_kind", "") or selection_snapshot.get("contract_kind", "") or "").strip()
    if contract_kind != "gem_breathing_20cm":
        return {}

    active_window_days = int(_safe_float(record.get("contract_active_window_days") or selection_snapshot.get("contract_active_window_days") or 0))
    participation_mode = str(record.get("participation_mode", "") or selection_snapshot.get("participation_mode", "") or "").strip()
    target_position_pct = int(_safe_float(record.get("target_position_pct") or selection_snapshot.get("target_position_pct") or 0))
    stock_code = normalize_stock_code(record.get("stock_code", ""))
    stock_name = str(record.get("stock_name") or record.get("anchor_type") or "无标的").strip()

    return {
        "contract_kind": contract_kind,
        "report_date": _normalize_kline_date_str(record.get("report_date")),
        "stock_code": stock_code,
        "stock_name": stock_name,
        "sample_label": f"{stock_name}({stock_code})" if stock_code else stock_name,
        "active_window_days": active_window_days or 5,
        "right_side_trigger_price": _round_or_none(record.get("contract_right_side_trigger_price") or selection_snapshot.get("contract_right_side_trigger_price")),
        "void_price": _round_or_none(record.get("contract_void_price") or selection_snapshot.get("contract_void_price")),
        "reset_breakout_price": _round_or_none(record.get("contract_reset_breakout_price") or selection_snapshot.get("contract_reset_breakout_price")),
        "upgrade_condition_text": str(record.get("contract_upgrade_condition_text", "") or selection_snapshot.get("contract_upgrade_condition_text", "") or "").strip(),
        "participation_mode": participation_mode,
        "target_position_pct": target_position_pct,
        "action_type": str(record.get("action_type", "") or "").strip(),
        "attribution_label": str((record.get("attribution", {}) or {}).get("label", "") or "").strip(),
    }


def _classify_gem_breathing_week_sample_legacy_body(record, as_of_date):
    snapshot = _extract_gem_breathing_contract_snapshot(record)
    if not snapshot:
        return {}

    report_date = snapshot.get("report_date")
    stock_code = snapshot.get("stock_code")
    if not report_date or not stock_code or not as_of_date:
        return {}

    tracking_days = _count_trading_days_between(report_date, as_of_date)
    bars = fetch_daily_price_bars(stock_code, report_date, as_of_date, is_index=False)
    bars = [
        bar for bar in (bars or [])
        if report_date <= _normalize_kline_date_str(bar.get("date")) <= as_of_date
    ]
    if not bars:
        return {}

    latest_bar = _get_last_bar_on_or_before(bars, as_of_date) or bars[-1]
    latest_close = _safe_float(latest_bar.get("close"))
    latest_high = max(_safe_float(bar.get("high")) for bar in bars if _safe_float(bar.get("high")) > 0)
    latest_low = min(_safe_float(bar.get("low")) for bar in bars if _safe_float(bar.get("low")) > 0)

    trigger_price = snapshot.get("right_side_trigger_price")
    void_price = snapshot.get("void_price")
    reset_breakout_price = snapshot.get("reset_breakout_price")
    active_window_days = snapshot.get("active_window_days", 5)
    participation_mode = snapshot.get("participation_mode", "")
    target_position_pct = snapshot.get("target_position_pct", 0)
    action_type = snapshot.get("action_type", "")
    attribution_label = snapshot.get("attribution_label", "")

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
        target_position_pct > 0
        or participation_mode == "attack_50_ready"
        or (action_type == "execute" and target_position_pct > 0)
    )
    upgrade_lag = bool(
        not conditional_upgrade
        and not voided
        and (
            attribution_label == "20cm右侧确认偏慢"
            or (participation_mode == "observe_0" and rebreak_success)
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
        price_map_parts.append(f"trigger {trigger_price:.2f}")
    if void_price is not None:
        price_map_parts.append(f"void {void_price:.2f}")
    if reset_breakout_price is not None:
        price_map_parts.append(f"reset {reset_breakout_price:.2f}")
    price_map = " / ".join(price_map_parts) if price_map_parts else "-"

    if conditional_upgrade:
        status_label = "已升级到50%条件执行"
        note = "这条20cm合同已经进入50%条件执行，不再只是纯观察样本。"
    elif voided:
        status_label = "窗口内失守作废"
        note = f"盘中跌破{void_price:.2f}作废价，合同应按失效处理。" if void_price is not None else "合同已经失效。"
    elif upgrade_lag:
        status_label = "再突破成功但升级偏慢"
        note = (
            f"已重新站上{reset_breakout_price:.2f}再突破位，但系统仍停在观察层。"
            if reset_breakout_price is not None
            else "价格已经走成右侧确认，但系统仍停在观察层。"
        )
    elif expired:
        status_label = "窗口到期自然作废"
        note = f"{active_window_days}日观察窗口到期仍未确认，不应继续维持高优先级跟踪。"
    elif rebreak_success:
        status_label = "已走成再突破"
        note = f"已经重新站上{reset_breakout_price:.2f}再突破位，后续只差升级动作。" if reset_breakout_price is not None else "已经走成再突破。"
    elif right_side_confirmation:
        status_label = "已触发右侧确认"
        note = f"已经摸到{trigger_price:.2f}右侧确认位，进入升级观察。" if trigger_price is not None else "已经触发右侧确认。"
    elif active_observation:
        status_label = "仍在观察窗口"
        note = f"仍在{active_window_days}日合同窗口内，先看右侧确认是否出现。"
    else:
        status_label = "记录待补全"
        note = "合同字段已存在，但当前样本还缺少足够后验数据。"

    return {
        **snapshot,
        "tracking_days": tracking_days,
        "latest_close": _round_or_none(latest_close),
        "right_side_confirmation": right_side_confirmation,
        "rebreak_success": rebreak_success,
        "voided": voided,
        "conditional_upgrade": conditional_upgrade,
        "upgrade_lag": upgrade_lag,
        "expired": expired,
        "active_observation": active_observation,
        "status_label": status_label,
        "price_map": price_map,
        "note": note,
        "sample_line": f"{report_date} {snapshot.get('sample_label')}：{note}",
    }


def _summarize_gem_breathing_week_review_legacy_body(records, start_date, end_date):
    scoped = []
    for record in (records or []):
        report_date = _normalize_kline_date_str(record.get("report_date"))
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
            x.get("conditional_upgrade", False),
            x.get("upgrade_lag", False),
            x.get("rebreak_success", False),
            x.get("right_side_confirmation", False),
            x.get("report_date", ""),
        ),
        reverse=True,
    )

    return {
        "start_date": start_date,
        "end_date": end_date,
        "sample_count": len(items),
        "right_side_confirmation_count": sum(1 for item in items if item.get("right_side_confirmation")),
        "rebreak_success_count": sum(1 for item in items if item.get("rebreak_success")),
        "conditional_upgrade_count": sum(1 for item in items if item.get("conditional_upgrade")),
        "voided_count": sum(1 for item in items if item.get("voided")),
        "expired_count": sum(1 for item in items if item.get("expired")),
        "upgrade_lag_count": sum(1 for item in items if item.get("upgrade_lag")),
        "active_observation_count": sum(1 for item in items if item.get("active_observation")),
        "upgrade_lag_samples": [item.get("sample_line") for item in items if item.get("upgrade_lag")],
        "voided_samples": [item.get("sample_line") for item in items if item.get("voided")],
        "expired_samples": [item.get("sample_line") for item in items if item.get("expired")],
        "items": items,
    }


def _build_self_calibration_summary_legacy_body(
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
        item.get("label", ""): int(item.get("count", 0))
        for item in (attribution_summary.get("items", []) or [])
    }
    total_count = int(attribution_summary.get("total_count", 0) or 0)
    gate_too_strict = (
        label_counts.get("环境过滤过严", 0)
        + label_counts.get("个股对了但环境条件未满足", 0)
        + label_counts.get("介入周期偏慢", 0)
    )
    weak_to_strong_lag = label_counts.get("弱转强识别偏慢", 0)
    gem_upgrade_lag = label_counts.get("20cm右侧确认偏慢", 0)
    gem_week_sample_count = int(_safe_float(gem_week_review.get("sample_count", 0)))
    gem_week_upgrade_count = int(_safe_float(gem_week_review.get("conditional_upgrade_count", 0)))
    gem_week_upgrade_lag = int(_safe_float(gem_week_review.get("upgrade_lag_count", 0)))
    gem_week_voided = int(_safe_float(gem_week_review.get("voided_count", 0)))
    gem_week_expired = int(_safe_float(gem_week_review.get("expired_count", 0)))
    state_misread = label_counts.get("状态判断偏差", 0)
    trigger_too_strict = label_counts.get("触发条件过严", 0)
    selection_bias = label_counts.get("主线判断偏差", 0) + label_counts.get("做了但根本不该做", 0)
    exit_too_early = label_counts.get("赚了但卖早", 0) + label_counts.get("退出周期过早结束", 0)
    stop_rebound = label_counts.get("止损正确但踏空", 0)
    defense_correct = label_counts.get("防守正确", 0)

    week_window = None
    month_window = None
    cycle_window = None
    for item in windows:
        if item.get("name") == "本周":
            week_window = item
        elif item.get("name") == "本月":
            month_window = item
        elif item.get("name") == "本次结构周期":
            cycle_window = item

    suggestions = []

    if gate_too_strict >= 2 or (total_count > 0 and gate_too_strict / max(total_count, 1) >= 0.4):
        suggestions.append({
            "area": "环境过滤",
            "bias": "偏严",
            "why": "多次出现“环境过滤过严 / 个股对了但环境条件未满足 / 介入周期偏慢”，说明当前环境过滤与介入升级都挡掉了部分有效观察对象。",
            "action": "先不要直接放开买入资格，而是在0%不参与下保留更明确的高优先级重点观察谁；对已经给出次日确认成功的唯一对象，要单独复盘介入周期是否偏慢。",
        })
    elif defense_correct >= max(2, gate_too_strict):
        suggestions.append({
            "area": "环境过滤",
            "bias": "有效",
            "why": "近期“防守正确”占优，说明市场过滤本身没有明显失真。",
            "action": "环境过滤先维持，不因为少赚就强行放松；优先继续积累记录。",
        })

    if weak_to_strong_lag >= 1:
        suggestions.append({
            "area": "弱转强识别",
            "bias": "偏慢",
            "why": "已经出现“弱转强识别偏慢”，说明主线内强基底假弱样本后续走成超预期转强时，系统还停在观察层。",
            "action": "以后对强基底+假弱非真弱+主线共振未坏的对象，要单独复盘从观察权到执行评估的升级时点，不要等它完全走出来才承认弱转强。",
        })

    gem_chain_bias_count = max(gem_upgrade_lag, gem_week_upgrade_lag)
    if gem_chain_bias_count >= 1 or (gem_week_sample_count >= 3 and gem_week_upgrade_count <= 1):
        why_parts = []
        action_parts = []
        if gem_week_sample_count > 0:
            why_parts.append(
                f"本周{gem_week_sample_count}只创业板20cm合同样本里，升级到50%条件执行只有{gem_week_upgrade_count}只，"
                f"窗口内作废{gem_week_voided}只，窗口到期{gem_week_expired}只。"
            )
        if gem_chain_bias_count >= 1:
            why_parts.append(
                f"已经出现{gem_chain_bias_count}只“20cm右侧确认偏慢”，说明创业板20cm预启动样本在走成右侧确认/再突破后，系统仍停在观察层。"
            )
            action_parts.append(
                f"优先回放升级偏慢{gem_chain_bias_count}只样本，逐个检查右侧确认位、再突破位与50%条件执行之间的升级链，不要长期停在只观察。"
            )
        else:
            action_parts.append("继续盯住右侧确认位到50%条件执行之间的升级链，避免20cm样本长期堆在观察层。")
        if gem_week_voided >= gem_week_upgrade_count and gem_week_voided > 0:
            action_parts.append("同时复盘作废价是否过松或对象本身边界不清，避免把不该留在高优先级观察里的20cm样本拖太久。")
        if gem_week_expired > 0:
            action_parts.append("对窗口到期仍未确认的20cm合同，要及时降权，不再占用高优先级注意力。")
        suggestions.append({
            "area": "创业板20cm升级链",
            "bias": "偏慢",
            "why": "".join(why_parts) or "创业板20cm升级链仍偏慢。",
            "action": "".join(action_parts) or "继续复盘创业板20cm从观察到50%条件执行的升级链。",
        })

    if state_misread >= 1:
        suggestions.append({
            "area": "状态层判断",
            "bias": "偏慢/偏早",
            "why": "已经出现“状态判断偏差”，说明系统在扩张与收缩切换时，仍有节奏判断失真的情况。",
            "action": "优先复盘“市场能量状态”和“异常投影”是否同步，再决定是放松还是收紧执行层。",
        })

    if trigger_too_strict >= 1:
        suggestions.append({
            "area": "触发条件",
            "bias": "偏紧",
            "why": "计划没成交，但后续仍给出明显上冲，说明09:50-10:10窗口或入场区间可能抬得过高。",
            "action": "接下来重点复盘确认价和回踩区的距离，不动环境过滤，先优化触发层。",
        })

    if selection_bias >= 1:
        suggestions.append({
            "area": "主线/选股",
            "bias": "有偏",
            "why": "出现“主线判断偏差 / 做了但根本不该做”，说明出手对象和市场主线贴合度不够。",
            "action": "继续收紧“看大做小”的约束，只给主线内最强和有记忆资产的标的买入资格。",
        })

    if exit_too_early >= 1 or stop_rebound >= 1:
        suggestions.append({
            "area": "退出节奏",
            "bias": "可优化",
            "why": "最近有“赚了但卖早 / 止损正确但踏空”记录，说明纪律没错，但退出后的二次观察还能更细。",
            "action": "保留原有止损纪律不放松，同时在日报里继续跟踪“止损后是否快速收复 / 卖出后是否继续加速”。",
        })

    if not suggestions:
        suggestions.append({
            "area": "系统状态",
            "bias": "学习期",
            "why": "当前记录仍少，系统还没有足够证据对参数做大动作。",
            "action": "先继续冻结计划和归因，不急着大改规则。",
        })

    setup_items = setup_summary.get("items", []) or []
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
    if top_setup and top_setup.get("sample_count", 0) > 0:
        setup_comment = (
            f"当前最值得继续观察的固定 setup 是 {top_setup.get('setup_label')}，"
            f"记录{top_setup.get('sample_count', 0)}笔，平均相对超额{_format_pct(top_setup.get('avg_alpha'))}。"
        )
    elif weak_setup and weak_setup.get("sample_count", 0) > 0:
        setup_comment = (
            f"当前最弱的固定 setup 是 {weak_setup.get('setup_label')}，"
            f"记录{weak_setup.get('sample_count', 0)}笔，平均相对超额{_format_pct(weak_setup.get('avg_alpha'))}。"
        )

    ev_items = ev_summary.get("items", []) or []
    ev_comment = ""
    if ev_items:
        best_ev_item = max(
            ev_items,
            key=lambda x: (
                _safe_float(x.get("avg_alpha"), -99.0),
                _safe_float(x.get("hit_rate"), -99.0),
            ),
        )
        if best_ev_item.get("sample_count", 0) > 0:
            ev_comment = (
                f"EV 侧当前更稳的是 {best_ev_item.get('signal_label')}，"
                f"平均超额{_format_pct(best_ev_item.get('avg_alpha'))}。"
            )

    return {
        "start_date": start_date,
        "end_date": end_date,
        "overview": "；".join([part for part in overview_parts if part]) or "暂无足够窗口记录。",
        "setup_comment": setup_comment,
        "ev_comment": ev_comment,
        "suggestions": suggestions,
    }


def _classify_structure_cycle_result_legacy_body(window_summary, attribution_summary, gem_cycle_review=None):
    attribution_items = attribution_summary.get("items", []) or []
    dominant_label = attribution_items[0].get("label", "") if attribution_items else ""
    gem_cycle_review = gem_cycle_review or {}
    gem_sample_count = int(_safe_float(gem_cycle_review.get("sample_count", 0)))
    gem_upgrade_count = int(_safe_float(gem_cycle_review.get("conditional_upgrade_count", 0)))
    gem_upgrade_lag = int(_safe_float(gem_cycle_review.get("upgrade_lag_count", 0)))
    gem_voided_count = int(_safe_float(gem_cycle_review.get("voided_count", 0)))
    gem_expired_count = int(_safe_float(gem_cycle_review.get("expired_count", 0)))
    alpha_mid = None
    alpha_low = window_summary.get("alpha_return_worst")
    alpha_high = window_summary.get("alpha_return_best")
    if alpha_low is not None and alpha_high is not None:
        alpha_mid = (_safe_float(alpha_low) + _safe_float(alpha_high)) / 2.0

    if window_summary.get("triggered_count", 0) > 0:
        if alpha_mid is not None and alpha_mid > 0.01:
            return "进攻有效"
        if alpha_mid is not None and alpha_mid < -0.02:
            return "进攻失真"
        return "进攻待验证"

    if gem_sample_count > 0:
        if gem_upgrade_lag >= 1:
            return "20cm升级偏慢"
        if gem_upgrade_count >= 1 and gem_voided_count + gem_expired_count < gem_sample_count:
            return "20cm支链成形"
        if gem_upgrade_count == 0 and gem_voided_count + gem_expired_count >= max(1, gem_sample_count - 1):
            return "20cm仍待收敛"

    if dominant_label == "防守正确":
        return "防守有效"
    if dominant_label in ("环境过滤过严", "个股对了但环境条件未满足", "介入周期偏慢"):
        return "过滤偏严"
    return "观察学习"


def _build_structure_cycle_gem_summary_legacy_body(gem_cycle_review):
    gem_cycle_review = gem_cycle_review or {}
    gem_sample_count = int(_safe_float(gem_cycle_review.get("sample_count", 0)))
    if gem_sample_count <= 0:
        return "-"
    gem_upgrade_count = int(_safe_float(gem_cycle_review.get("conditional_upgrade_count", 0)))
    gem_upgrade_lag = int(_safe_float(gem_cycle_review.get("upgrade_lag_count", 0)))
    gem_voided_count = int(_safe_float(gem_cycle_review.get("voided_count", 0)))
    gem_expired_count = int(_safe_float(gem_cycle_review.get("expired_count", 0)))
    return (
        f"20cm样本{gem_sample_count} / 升级{gem_upgrade_count} / 偏慢{gem_upgrade_lag} / "
        f"作废{gem_voided_count} / 到期{gem_expired_count}"
    )


def _build_gem_structure_cycle_cards_legacy_body(records, as_of_date, limit=6):
    grouped = {}
    for record in records or []:
        snapshot = _extract_gem_breathing_contract_snapshot(record)
        if not snapshot:
            continue
        cycle_start = _normalize_kline_date_str(record.get("structure_cycle_start")) or _normalize_kline_date_str(record.get("report_date"))
        stock_code = snapshot.get("stock_code") or snapshot.get("sample_label")
        if not cycle_start or not stock_code:
            continue
        grouped.setdefault((cycle_start, stock_code), []).append(record)

    cards = []
    for (cycle_start, _stock_code), group_records in grouped.items():
        sorted_records = sorted(group_records, key=lambda x: _normalize_kline_date_str(x.get("report_date")))
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
            status_label = str(item.get("status_label", "") or "").strip()
            if status_label and (not status_chain or status_chain[-1] != status_label):
                status_chain.append(status_label)

        first_date = _normalize_kline_date_str(sorted_records[0].get("report_date"))
        last_date = _normalize_kline_date_str(sorted_records[-1].get("report_date"))
        occurrence_count = len(sorted_records)
        cycle_end = last_date or cycle_start
        timeline_text = f"{first_date} -> {last_date}" if first_date and last_date and first_date != last_date else (first_date or cycle_start)
        timeline_text = f"{timeline_text}（同周期出现{occurrence_count}次）"
        cycle_label = f"{cycle_start} -> {cycle_end}" if cycle_start != cycle_end else cycle_start

        cards.append({
            "cycle_start": cycle_start,
            "cycle_end": cycle_end,
            "cycle_label": cycle_label,
            "sample_label": latest_item.get("sample_label") or latest_item.get("stock_name") or "-",
            "occurrence_count": occurrence_count,
            "timeline_text": timeline_text,
            "evolution_text": " → ".join(status_chain) if status_chain else latest_item.get("status_label", "-"),
            "latest_status_label": latest_item.get("status_label", "-"),
            "price_map": latest_item.get("price_map", "-") or "-",
            "note": latest_item.get("note", "-") or "-",
        })

    status_priority = {
        "再突破成功但升级偏慢": 5,
        "已升级到50%条件执行": 4,
        "已走成再突破": 3,
        "已触发右侧确认": 2,
        "仍在观察窗口": 1,
        "窗口内失守作废": 0,
        "窗口到期自然作废": 0,
    }
    cards.sort(
        key=lambda x: (
            x.get("occurrence_count", 0),
            status_priority.get(x.get("latest_status_label", ""), 0),
            x.get("cycle_start", ""),
            x.get("sample_label", ""),
        ),
        reverse=True,
    )
    return cards[:limit]


def _summarize_structure_cycles_legacy_body(records, as_of_date):
    grouped = {}
    for record in records or []:
        cycle_start = _normalize_kline_date_str(record.get("structure_cycle_start")) or _normalize_kline_date_str(record.get("report_date"))
        if not cycle_start:
            continue
        grouped.setdefault(cycle_start, []).append(record)

    cycle_items = []
    for cycle_start in sorted(grouped.keys()):
        cycle_records = sorted(grouped.get(cycle_start, []), key=lambda x: _normalize_kline_date_str(x.get("report_date")))
        if not cycle_records:
            continue

        cycle_end = max(_normalize_kline_date_str(record.get("report_date")) for record in cycle_records)
        window_summary = _summarize_strategy_window(records, cycle_start, cycle_end)
        attribution_summary = _summarize_strategy_attribution(records, cycle_start, cycle_end)
        setup_summary = _summarize_setup_signal_review(records, cycle_start, cycle_end)
        gem_cycle_review = _summarize_gem_breathing_week_review(records, cycle_start, cycle_end)
        dominant_attribution = (attribution_summary.get("items", []) or [{}])[0].get("label", "")
        top_setup = (setup_summary.get("items", []) or [{}])[0].get("setup_label", "")
        gem_cycle_summary = _build_structure_cycle_gem_summary(gem_cycle_review)

        alpha_mid = None
        if window_summary.get("alpha_return_worst") is not None and window_summary.get("alpha_return_best") is not None:
            alpha_mid = (
                _safe_float(window_summary.get("alpha_return_worst"))
                + _safe_float(window_summary.get("alpha_return_best"))
            ) / 2.0

        cycle_items.append({
            "cycle_start": cycle_start,
            "cycle_end": cycle_end,
            "plan_count": len(cycle_records),
            "execute_count": sum(1 for record in cycle_records if record.get("action_type") == "execute"),
            "triggered_count": int(window_summary.get("triggered_count", 0)),
            "benchmark_return": window_summary.get("benchmark_return"),
            "alpha_return_worst": window_summary.get("alpha_return_worst"),
            "alpha_return_best": window_summary.get("alpha_return_best"),
            "alpha_mid": alpha_mid,
            "dominant_attribution": dominant_attribution or "-",
            "top_setup": top_setup or "-",
            "gem_20cm_sample_count": int(_safe_float(gem_cycle_review.get("sample_count", 0))),
            "gem_20cm_summary": gem_cycle_summary,
            "mainline_preview": " / ".join([
                record.get("mainline_name", "")
                for record in cycle_records[-3:]
                if record.get("mainline_name")
            ]) or "-",
            "result_label": _classify_structure_cycle_result(window_summary, attribution_summary, gem_cycle_review),
        })

    return cycle_items


def _build_system_graduation_dashboard_legacy_body(records, cycle_reviews, source_label="当前账本", current_plan=None, gem_week_review=None):
    total_records = len(records or [])
    cycle_count = len(cycle_reviews or [])
    gem_week_review = gem_week_review or {}
    frozen_count = sum(1 for record in (records or []) if record.get("factor_snapshot") or record.get("factor_snapshot_path"))
    attribution_count = sum(1 for record in (records or []) if (record.get("attribution", {}) or {}).get("category"))
    decision_stack_count = sum(1 for record in (records or []) if record.get("decision_stack") or (record.get("factor_snapshot", {}) or {}).get("selection"))
    setup_count = sum(1 for record in (records or []) if record.get("abnormal_setup_signal_label") or ((record.get("factor_snapshot", {}) or {}).get("abnormal", {}) or {}).get("selected_setup"))
    execute_count = sum(1 for record in (records or []) if record.get("action_type") == "execute")
    triggered_count = sum(1 for record in (records or []) if (record.get("simulation", {}) or {}).get("triggered"))
    positive_cycles = sum(1 for item in (cycle_reviews or []) if item.get("result_label") in ("进攻有效", "防守有效"))
    strict_cycles = sum(1 for item in (cycle_reviews or []) if item.get("result_label") == "过滤偏严")
    gem_sample_count = int(_safe_float(gem_week_review.get("sample_count", 0)))
    gem_upgrade_count = int(_safe_float(gem_week_review.get("conditional_upgrade_count", 0)))
    gem_upgrade_lag = int(_safe_float(gem_week_review.get("upgrade_lag_count", 0)))
    gem_voided_count = int(_safe_float(gem_week_review.get("voided_count", 0)))
    gem_expired_count = int(_safe_float(gem_week_review.get("expired_count", 0)))

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
    current_factor_snapshot = current_plan.get("factor_snapshot", {}) or {}
    current_engine_ready = bool(
        current_factor_snapshot
        and current_plan.get("decision_stack", {}) is not None
        and current_plan.get("defensive_exit_rule")
        and current_plan.get("profit_exit_rule")
    )
    legacy_history_gap = current_engine_ready and total_records > 0 and frozen_cov < 0.2 and setup_cov < 0.2

    if total_score < 35:
        if legacy_history_gap:
            stage = "研究原型"
            verdict = "当前引擎已经脱离玩具，但官方冻结记录大多还是旧版本，毕业证据仍然不足。"
        else:
            stage = "玩具"
            verdict = "还没过研究门槛，当前更多是展示层结果，不足以稳定辅助。"
    elif total_score < 65:
        stage = "研究原型"
        verdict = "已经脱离玩具，但还处在记录积累和参数校准阶段。"
    elif total_score < 82:
        stage = "可长期辅助决策"
        verdict = "已经能稳定辅助复盘和筛错，但仍不适合完全托管执行。"
    else:
        stage = "接近成熟系统"
        verdict = "流程、记录和跨周期表现都较完整，已接近成熟辅助系统。"

    graduation_checks = [
        {
            "item": "历史冻结完整性",
            "status": "通过" if frozen_cov >= 0.9 else "待加强",
            "detail": f"{frozen_count}/{total_records} 条记录有冻结因子快照",
        },
        {
            "item": "跨结构周期广度",
            "status": "通过" if cycle_count >= 3 else "待加强",
            "detail": f"当前覆盖 {cycle_count} 个结构周期",
        },
        {
            "item": "归因闭环",
            "status": "通过" if attribution_cov >= 0.9 else "待加强",
            "detail": f"{attribution_count}/{total_records} 条记录已有错因归属",
        },
        {
            "item": "Setup标准化",
            "status": "通过" if setup_cov >= 0.6 else "待加强",
            "detail": f"{setup_count}/{total_records} 条记录已有固定 setup",
        },
        {
            "item": "执行记录深度",
            "status": "通过" if execute_count >= 10 and triggered_count >= 5 else "待加强",
            "detail": f"执行计划 {execute_count} 条，真实触发 {triggered_count} 条",
        },
        {
            "item": "跨周期结果稳定性",
            "status": "通过" if positive_cycle_ratio >= 0.5 and cycle_count >= 2 else "待加强",
            "detail": f"正向周期 {positive_cycles}/{cycle_count}",
        },
    ]
    if gem_sample_count > 0:
        gem_check_pass = gem_upgrade_count >= 1 and gem_upgrade_lag <= max(1, gem_sample_count // 3)
        graduation_checks.append({
            "item": "创业板20cm支链",
            "status": "通过" if gem_check_pass else "待加强",
            "detail": f"{gem_sample_count}只样本 / 升级{gem_upgrade_count}只 / 升级偏慢{gem_upgrade_lag}只 / 作废{gem_voided_count}只 / 到期{gem_expired_count}只",
        })

    next_actions = []
    if cycle_count < 3:
        next_actions.append("至少继续积累 2 个以上完整结构周期，再判断是否毕业。")
    if execute_count < 10 or triggered_count < 5:
        next_actions.append("继续沉淀真实执行记录，否则 EV 和退出节奏都没有统计意义。")
    if strict_cycles >= 1:
        next_actions.append("重点复盘“过滤偏严”的周期，判断环境条件是否错杀了主线机会。")
    if gem_sample_count > 0 and gem_upgrade_lag >= 1:
        next_actions.append(f"优先修正创业板20cm从右侧确认到50%条件执行的升级链；本周升级偏慢{gem_upgrade_lag}只，不能继续长期停在观察层。")
    if gem_sample_count > 0 and gem_voided_count >= gem_upgrade_count and gem_voided_count > 0:
        next_actions.append("复盘创业板20cm合同的作废价与样本筛法，避免高优先级观察样本大量在窗口内失效。")
    if not next_actions:
        next_actions.append("开始按固定周期复查 stage 是否能从辅助系统继续向成熟系统升级。")

    return {
        "source_label": source_label,
        "stage": stage,
        "verdict": verdict,
        "total_score": total_score,
        "dimension_scores": [
            {"name": "过程完整性", "score": integrity_score, "detail": f"冻结覆盖{frozen_cov:.0%} / 归因覆盖{attribution_cov:.0%}"},
            {"name": "标准化程度", "score": standard_score, "detail": f"决策栈覆盖{decision_cov:.0%} / Setup覆盖{setup_cov:.0%}" + (f" / 20cm样本{gem_sample_count} 升级{gem_upgrade_count} 偏慢{gem_upgrade_lag}" if gem_sample_count > 0 else "")},
            {"name": "跨周期广度", "score": breadth_score, "detail": f"{total_records}条记录 / {cycle_count}个结构周期"},
            {"name": "执行记录深度", "score": execution_score, "detail": f"{execute_count}条执行计划 / {triggered_count}条真实触发"},
            {"name": "跨周期稳定性", "score": performance_score, "detail": f"正向周期{positive_cycles}/{cycle_count}"},
        ],
        "checks": graduation_checks,
        "next_actions": next_actions,
        "legacy_history_gap": legacy_history_gap,
        "current_engine_ready": current_engine_ready,
    }
