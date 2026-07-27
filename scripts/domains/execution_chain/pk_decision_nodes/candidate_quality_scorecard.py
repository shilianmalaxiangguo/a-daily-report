from report.surface_wording import sanitize_user_visible_text
from report.sniper_target_derivation import stock_key as _derivation_stock_key
from report.position_context import (
    existing_position_summary_from_context,
    position_fact_status,
)
from domains.execution_chain.pk_decision_nodes.candidate_surface_filter import (
    anchor_reversal_payload as _anchor_payload,
    candidate_blocks_current_observation_target as _candidate_blocks_panel_watch_target,
    candidate_can_be_current_observation_target as _candidate_can_be_panel_watch_target,
    candidate_matches_any_key as _candidate_matches_blocked_panel_key,
    candidate_key as _candidate_key,
)


def _clear_blocked_panel_target_fields(panel_fields, candidate_samples=None):
    updated = dict(panel_fields or {})
    blocked_keys = {
        _candidate_key(candidate)
        for candidate in list(candidate_samples or [])
        if _candidate_blocks_panel_watch_target(candidate)
    }
    for key in ("primary_buy_candidate", "backup_candidate"):
        candidate = updated.get(key)
        if _candidate_blocks_panel_watch_target(candidate) or _candidate_matches_blocked_panel_key(candidate, blocked_keys):
            updated[key] = None
    return updated


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _merge_unique_values(existing_value, incoming_value):
    merged = []
    for value in _as_list(existing_value) + _as_list(incoming_value):
        if value not in (None, "") and value not in merged:
            merged.append(value)
    return merged


def _clean_text(value):
    return str(value or "").strip()


def _meaningful_text(value):
    text = _clean_text(value)
    return "" if text in {"-", "暂无", "无主线", "未知", "未归类", "数据缺失"} else text


def _context_mainline(context):
    context = context or {}
    for key in ("mainline_name", "primary_mainline", "leading_line"):
        text = _meaningful_text(context.get(key))
        if text:
            return text
    current = context.get("current_mainline_history_record")
    if isinstance(current, dict):
        text = _meaningful_text(current.get("primary_mainline") or current.get("mainline") or current.get("leading_line"))
        if text:
            return text
    summary = context.get("mainline_turnover_summary")
    if isinstance(summary, dict):
        for key in ("current_mainline", "primary_mainline", "primary_line", "cycle_mainline", "daily_attack_line"):
            text = _meaningful_text(summary.get(key))
            if text:
                return text
        capacity = summary.get("mainline_capacity_regime_summary")
        if isinstance(capacity, dict):
            text = _meaningful_text(capacity.get("primary_line"))
            if text:
                return text
    snapshot = context.get("market_research_snapshot")
    if isinstance(snapshot, dict):
        text = _context_mainline(snapshot)
        if text:
            return text
    market_state = context.get("market_state_snapshot")
    if isinstance(market_state, dict):
        text = _meaningful_text(market_state.get("leading_line") or market_state.get("densest_sector"))
        if text:
            return text
    return ""


def _candidate_sector(candidate):
    candidate = candidate or {}
    return _clean_text(candidate.get("sector") or candidate.get("sector_name") or candidate.get("industry") or candidate.get("板块"))


def _trace_tier(candidate, source_pool):
    tier = _clean_text(candidate.get("tier") or candidate.get("source_tier") or candidate.get("分层")).upper()
    if tier in {"T0", "T1", "T2", "T3"}:
        return tier
    role_text = " ".join(
        _clean_text(candidate.get(key))
        for key in ("quality_role", "watch_anchor_type", "permission_label", "core_level")
    )
    pool_text = _clean_text(source_pool)
    if candidate.get("is_core") or any(marker in role_text for marker in ("主买", "核心", "重点观察")):
        return "T0"
    if pool_text in {"core_stocks", "leader_memory_bank", "extreme_conviction_list"}:
        return "T0"
    if pool_text in {"focus_group", "keep_group"}:
        return "T1"
    if pool_text in {"secondary_stocks", "waiting_stocks", "abnormal_watch_pool", "display_observation_candidates"}:
        return "T2"
    return "T3"


def _market_fit_from_context(context):
    context = context or {}
    final_gate = context.get("final_gate") if isinstance(context.get("final_gate"), dict) else {}
    evidence = _clean_text(context.get("step0_prediction_cn") or context.get("position_reason"))
    if final_gate.get("can_new_entry") or context.get("trade_gate_open"):
        return "满足", evidence or "市场允许新增参与"
    if final_gate.get("allow_attack_50_ready"):
        return "部分满足", evidence or "只保留固定交易窗口内确认路径"
    if final_gate or evidence:
        return "未满足", evidence or "市场条件暂不支持新增参与"
    return "", ""


def _mainline_fit_from_candidate(candidate, mainline, sector):
    if not mainline or not sector:
        return "", ""
    evidence_text = " ".join(
        _clean_text(candidate.get(key))
        for key in ("reason", "action_text", "watch_anchor_note", "conviction_reason")
    )
    if sector == mainline or sector in mainline or mainline in sector or mainline in evidence_text:
        return "满足", f"{sector}与{mainline}同向"
    return "未满足", f"{sector}不在{mainline}主线内"


def _stock_structure_fit_from_candidate(candidate):
    evidence_text = "；".join(
        _clean_text(candidate.get(key))
        for key in ("reason", "action_text", "watch_anchor_note", "conviction_reason", "trend_context")
        if _clean_text(candidate.get(key))
    )
    if not evidence_text:
        return "", ""
    positive_markers = ("趋势审美", "趋势续强", "强势", "MA20", "平台", "首波先锋", "板块锚定龙", "涨停", "风险可控", "跌不下去", "承接")
    if any(marker in evidence_text for marker in positive_markers):
        return "部分满足", evidence_text
    return "", evidence_text


def _default_trigger_condition(candidate):
    minute_plan = candidate.get("minute_plan") if isinstance(candidate.get("minute_plan"), dict) else {}
    confirm_price = minute_plan.get("confirm_price_60m")
    if confirm_price not in (None, ""):
        try:
            return f"固定交易窗口内站上{float(confirm_price):.2f}"
        except (TypeError, ValueError):
            return f"固定交易窗口内站上{confirm_price}"
    for key in ("trigger", "action_text", "reason", "watch_anchor_note"):
        text = _clean_text(candidate.get(key))
        if text:
            return text
    return "固定交易窗口内承接确认"


def _default_failure_condition(candidate):
    removal = candidate.get("removal_conditions")
    if isinstance(removal, (list, tuple)) and removal:
        return "；".join(_clean_text(item) for item in removal if _clean_text(item))
    stop_plan = candidate.get("stop_plan") if isinstance(candidate.get("stop_plan"), dict) else {}
    text = _clean_text(stop_plan.get("summary"))
    if text:
        return text
    return "板块承接转弱或个股条件失效"


def _enrich_candidate_trace_inputs(candidate, context, *, source_pool=""):
    if not isinstance(candidate, dict):
        return candidate
    enriched = dict(candidate)
    if source_pool:
        enriched["source_pools"] = _merge_unique_values(enriched.get("source_pools"), source_pool)
    if "position_context_provided" not in enriched and "position_context_provided" in (context or {}):
        enriched["position_context_provided"] = bool((context or {}).get("position_context_provided"))
    existing_position_summary = existing_position_summary_from_context(context)
    if (
        position_fact_status(existing_position_summary, context_provided=True) == "confirmed"
        and _candidate_identity_keys(existing_position_summary) & _candidate_identity_keys(enriched)
    ):
        enriched["position_fact_status"] = "confirmed"
    mainline = _meaningful_text(enriched.get("mainline") or enriched.get("主线")) or _context_mainline(context)
    sector = _candidate_sector(enriched) or mainline
    if mainline and not _meaningful_text(enriched.get("mainline")):
        enriched["mainline"] = mainline
    if sector and not _meaningful_text(enriched.get("sector")):
        enriched["sector"] = sector
    if not enriched.get("tier"):
        enriched["tier"] = _trace_tier(enriched, source_pool)
    market_fit, market_evidence = _market_fit_from_context(context)
    if market_fit and not _meaningful_text(enriched.get("market_fit")):
        enriched["market_fit"] = market_fit
    if market_evidence and not enriched.get("market_evidence"):
        enriched["market_evidence"] = market_evidence
    if market_fit == "未满足" and not enriched.get("final_action"):
        enriched["final_action"] = "条件未满足，继续不参与"
    mainline_fit, mainline_evidence = _mainline_fit_from_candidate(enriched, mainline, sector)
    if mainline_fit and not _meaningful_text(enriched.get("mainline_fit")):
        enriched["mainline_fit"] = mainline_fit
    if mainline_evidence and not enriched.get("mainline_evidence"):
        enriched["mainline_evidence"] = mainline_evidence
    structure_fit, structure_evidence = _stock_structure_fit_from_candidate(enriched)
    if structure_fit and not _meaningful_text(enriched.get("stock_structure_fit")):
        enriched["stock_structure_fit"] = structure_fit
    if structure_evidence and not enriched.get("stock_structure_evidence"):
        enriched["stock_structure_evidence"] = structure_evidence
    if "latest_price" not in enriched and enriched.get("close") not in (None, ""):
        enriched["latest_price"] = enriched.get("close")
    if not enriched.get("trigger_condition"):
        enriched["trigger_condition"] = _default_trigger_condition(enriched)
    if not enriched.get("failure_condition"):
        enriched["failure_condition"] = _default_failure_condition(enriched)
    return enriched


def _dedupe_candidates(candidates):
    deduped = []
    index_by_key = {}
    seen = set()
    for candidate in candidates:
        if not candidate:
            continue
        key = _candidate_key(candidate)
        if key and key in seen:
            existing = deduped[index_by_key[key]]
            for field, value in candidate.items():
                if value in (None, "", [], {}):
                    continue
                if field == "entry_cost_state" and value == "高成本":
                    existing[field] = value
                    continue
                if field in ("risk_flags", "cost_flags", "source_pools"):
                    existing[field] = _merge_unique_values(existing.get(field), value)
                    continue
                if existing.get(field) in (None, "", [], {}):
                    existing[field] = value
            continue
        if key:
            seen.add(key)
            index_by_key[key] = len(deduped)
        deduped.append(candidate)
    return deduped


def _quality_candidate(candidate, *, quality_role="", selection_quality="", entry_cost_state="", is_core=None, source_pool=""):
    if not candidate:
        return None
    enriched = dict(candidate)
    if selection_quality and not enriched.get("selection_quality"):
        enriched["selection_quality"] = selection_quality
    if entry_cost_state and not enriched.get("entry_cost_state"):
        enriched["entry_cost_state"] = entry_cost_state
    if is_core is not None and "is_core" not in enriched:
        enriched["is_core"] = is_core
    if quality_role and not enriched.get("quality_role"):
        enriched["quality_role"] = quality_role
    if source_pool:
        enriched["source_pools"] = _merge_unique_values(enriched.get("source_pools"), source_pool)
    return enriched


def _current_watch_target(context):
    context = context or {}
    wait_without_watch_target = _final_target_empty_without_current_observation(context)
    blocked_keys = blocked_current_observation_keys_from_context(context)
    derivation = context.get("sniper_target_derivation")
    if isinstance(derivation, dict):
        canonical = derivation.get("canonical_target")
        if _candidate_can_be_panel_watch_target(canonical) and not _candidate_matches_blocked_panel_key(canonical, blocked_keys):
            return canonical
    final_target_resolution = context.get("final_target_resolution")
    if isinstance(final_target_resolution, dict):
        watch_target = final_target_resolution.get("watch_target")
        if _candidate_can_be_panel_watch_target(watch_target) and not _candidate_matches_blocked_panel_key(watch_target, blocked_keys):
            return watch_target
    if wait_without_watch_target:
        return None
    snapshot = context.get("market_research_snapshot")
    if isinstance(snapshot, dict):
        nested_resolution = snapshot.get("final_target_resolution")
        if isinstance(nested_resolution, dict):
            watch_target = nested_resolution.get("watch_target")
            if _candidate_can_be_panel_watch_target(watch_target) and not _candidate_matches_blocked_panel_key(watch_target, blocked_keys):
                return watch_target
        candidate = snapshot.get("selected_position_candidate")
        if _candidate_can_be_panel_watch_target(candidate) and not _candidate_matches_blocked_panel_key(candidate, blocked_keys):
            return candidate
    for key in ("selected_position_candidate", "current_core_candidate", "front_page_selected_position_candidate"):
        candidate = context.get(key)
        if _candidate_can_be_panel_watch_target(candidate) and not _candidate_matches_blocked_panel_key(candidate, blocked_keys):
            return candidate
    return None


def _sniper_target_derivation(context):
    context = context or {}
    packet = context.get("sniper_target_derivation")
    if isinstance(packet, dict):
        return packet
    snapshot = context.get("market_research_snapshot")
    if isinstance(snapshot, dict) and isinstance(snapshot.get("sniper_target_derivation"), dict):
        return snapshot.get("sniper_target_derivation")
    return {}


def _candidate_from_derivation_step(step, canonical_key):
    if not isinstance(step, dict):
        return None
    candidate = step.get("candidate")
    if not isinstance(candidate, dict):
        return None
    if _candidate_key(candidate) == canonical_key or _derivation_stock_key(candidate) == canonical_key:
        return None
    role = _clean_text(step.get("role")) or "过程候选"
    decision = _clean_text(step.get("decision")) or "仅过程证据"
    enriched = dict(candidate)
    enriched["quality_role"] = role
    enriched["selection_quality"] = "过程证据"
    enriched["entry_cost_state"] = "不作为最终对象"
    enriched["source_pools"] = _merge_unique_values(enriched.get("source_pools"), step.get("source") or "sniper_target_derivation")
    enriched["tier"] = enriched.get("tier") or "T3"
    enriched["final_action"] = f"{role} / {decision}"
    enriched["action_ceiling"] = "仅过程证据"
    enriched["new_entry_action"] = f"{role} / {decision}"
    enriched["visible_summary"] = _clean_text(step.get("reason")) or "最终解析未选为观察对象"
    return enriched


def _derivation_process_samples(context, target):
    packet = _sniper_target_derivation(context)
    if not packet:
        return []
    canonical_key = _candidate_key(target) or _derivation_stock_key(packet.get("canonical_target") or {})
    samples = []
    seen = set()
    for step in packet.get("steps") or []:
        sample = _candidate_from_derivation_step(step, canonical_key)
        if not sample:
            continue
        key = _candidate_key(sample) or _derivation_stock_key(sample)
        if key in seen:
            continue
        seen.add(key)
        samples.append(sample)
    return samples


def _replace_or_prepend_candidate(candidates, target):
    if not isinstance(target, dict) or not _candidate_key(target):
        return list(candidates or [])
    target_key = _candidate_key(target)
    merged = [dict(target)]
    for candidate in list(candidates or []):
        if not isinstance(candidate, dict):
            continue
        if _candidate_key(candidate) == target_key:
            continue
        merged.append(candidate)
    return merged


def _replace_with_current_candidate(candidates, target):
    if not isinstance(target, dict) or not _candidate_key(target):
        return list(candidates or [])
    target_key = _candidate_key(target)
    for candidate in list(candidates or []):
        if isinstance(candidate, dict) and _candidate_key(candidate) == target_key:
            merged = dict(candidate)
            merged.update({key: value for key, value in target.items() if value not in (None, "")})
            return [merged]
    return [dict(target)]


def _align_panel_fields_to_current_watch_target(panel_fields, target):
    if not isinstance(target, dict) or not _candidate_key(target):
        return panel_fields
    updated = dict(panel_fields or {})
    primary = updated.get("primary_buy_candidate")
    if _candidate_key(primary) == _candidate_key(target):
        updated["primary_buy_candidate"] = target
        updated["backup_candidate"] = None
    else:
        updated["primary_buy_candidate"] = None
        updated["backup_candidate"] = target
    return updated


def _final_resolution_waits_without_watch_target(context):
    resolution = (context or {}).get("final_target_resolution")
    if not isinstance(resolution, dict):
        return False
    decision = resolution.get("capital_priority_decision") if isinstance(resolution.get("capital_priority_decision"), dict) else {}
    if _clean_text(decision.get("capital_priority")) != "wait":
        return False
    watch_target = resolution.get("watch_target")
    return not _candidate_can_be_panel_watch_target(watch_target)


def _final_target_empty_without_current_observation(context):
    return (
        _selection_workflow_final_is_empty(context)
        or _final_resolution_waits_without_watch_target(context)
        or _selection_workflow_final_empty_without_watch_target(context)
    )


def _selection_workflow_final_empty_without_watch_target(context):
    workflow = _selection_workflow_from_context(context)
    if not workflow:
        return False
    final = workflow.get("final") if isinstance(workflow.get("final"), dict) else {}
    if "final" not in workflow:
        return False
    execution_object = final.get("execution_object") if isinstance(final.get("execution_object"), dict) else {}
    position_pct = _position_pct(final.get("position_pct"))
    if position_pct > 0 and _candidate_key(execution_object):
        return False
    return not bool(_selection_workflow_front_observation_target(workflow))


def _selection_workflow_final_is_empty(context):
    workflow = _selection_workflow_from_context(context)
    if not workflow:
        return False
    final = workflow.get("final") if isinstance(workflow.get("final"), dict) else {}
    if "final" not in workflow:
        return False
    execution_object = final.get("execution_object") if isinstance(final.get("execution_object"), dict) else {}
    position_pct = _position_pct(final.get("position_pct"))
    return position_pct <= 0 or not bool(_candidate_key(execution_object))


def _selection_workflow_from_context(context):
    sources = [context]
    if isinstance(context, dict):
        sources.extend([context.get("market_research_snapshot"), context.get("execution_stage_context")])
    for source in sources:
        if not isinstance(source, dict):
            continue
        workflow = source.get("selection_workflow")
        if isinstance(workflow, dict) and workflow.get("schema_version") == "selection_workflow.v1":
            return workflow
    return {}


def _position_pct(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _selection_workflow_front_observation_target(workflow):
    workflow = workflow if isinstance(workflow, dict) else {}
    for candidate in workflow.get("candidate_pool", []) or []:
        if not isinstance(candidate, dict):
            continue
        if candidate.get("front_observation_qualified") is not True:
            continue
        if _candidate_blocks_panel_watch_target(candidate):
            continue
        stock = candidate.get("stock") if isinstance(candidate.get("stock"), dict) else candidate
        if _candidate_key(stock):
            return stock
    return {}


def blocked_current_observation_keys_from_context(context):
    context = context or {}
    candidates = []
    for key in ("candidate_quality_samples", "display_observation_candidates", "observation_candidates"):
        candidates.extend(list(context.get(key) or []))
    snapshot = context.get("market_research_snapshot")
    if isinstance(snapshot, dict):
        for key in ("candidate_quality_samples", "display_observation_candidates", "observation_candidates"):
            candidates.extend(list(snapshot.get(key) or []))
    return {
        key
        for candidate in candidates
        if _candidate_blocks_panel_watch_target(candidate)
        for key in _candidate_identity_keys(candidate)
    }


def _candidate_identity_keys(candidate):
    from domains.execution_chain.pk_decision_nodes.candidate_surface_filter import candidate_identity_keys

    return candidate_identity_keys(candidate)


def _clear_panel_target_fields(panel_fields):
    updated = dict(panel_fields or {})
    updated["primary_buy_candidate"] = None
    updated["backup_candidate"] = None
    return updated


def _normalize_pending_position_panel_fields(panel_fields, existing_position_summary):
    updated = dict(panel_fields or {})
    if position_fact_status(existing_position_summary, context_provided=True) != "pending_confirmation":
        return updated
    if "只处理旧仓" in str(updated.get("market_emotion_label") or ""):
        updated["market_emotion_label"] = "🟠 0%不参与；先确认成交事实"
    updated["account_attention_load"] = "外部交易记录待核实"
    updated["holding_priority_action"] = "未确认成交前不视为B1；新机会按自身资格判断"
    return updated


def _build_panel_fields(
    *,
    step0_prediction_cn,
    has_personal_positions,
    position_context_provided,
    existing_position_summary=None,
    daily_new_entry_limit,
    best_stock,
    watch_anchor,
):
    backup_candidate = watch_anchor
    if _candidate_key(best_stock) and _candidate_key(best_stock) == _candidate_key(watch_anchor):
        backup_candidate = None
    existing_position_summary = existing_position_summary if isinstance(existing_position_summary, dict) else {}
    position_status = position_fact_status(
        existing_position_summary,
        context_provided=position_context_provided,
    )
    inferred_old_path = bool(
        position_status == "confirmed"
        and any(
            str(existing_position_summary.get(key) or "").strip()
            for key in ("summary", "name", "stock_name", "code", "stock_code")
        )
    )
    pending_position = position_status == "pending_confirmation"
    if pending_position:
        account_attention_load = "外部交易记录待核实"
        holding_priority_action = "未确认成交前不视为B1；新机会按自身资格判断"
    elif has_personal_positions:
        account_attention_load = "有持仓需先处理"
        holding_priority_action = "先处理旧仓，再看新增"
    elif inferred_old_path:
        account_attention_load = "旧仓需复核"
        holding_priority_action = "旧仓与新机会分开处理"
    elif position_context_provided:
        account_attention_load = "无持仓负担"
        holding_priority_action = "无旧仓时只等参与窗口"
    else:
        account_attention_load = "持仓未输入，先确认旧仓情况"
        holding_priority_action = "先确认旧仓情况，再看新增"
    return {
        "market_emotion_label": step0_prediction_cn,
        "account_attention_load": account_attention_load,
        "holding_priority_action": holding_priority_action,
        "daily_new_entry_limit": daily_new_entry_limit,
        "primary_buy_candidate": best_stock,
        "backup_candidate": backup_candidate,
        "forbidden_actions": ["亏损后补仓", "计划外追高"],
        "ignored_noise_items": ["外盘大涨但A股未确认", "论坛情绪"],
    }


def _build_diagnostics(samples):
    missing_quality_count = sum(
        1
        for sample in samples
        if not sample.get("selection_quality") or not sample.get("entry_cost_state")
    )
    return {
        "candidate_count": len(samples),
        "scored_count": len(samples) - missing_quality_count,
        "missing_quality_count": missing_quality_count,
        "degraded": not samples,
        "source": "pk_decision",
    }


def build_candidate_quality_scorecard_payload(context):
    context = context or {}
    current_watch_target = _current_watch_target(context)
    final_empty_without_current_observation = _final_target_empty_without_current_observation(context)
    derivation_packet = _sniper_target_derivation(context)
    existing_panel_fields = context.get("candidate_quality_panel_fields")
    existing_samples = context.get("candidate_quality_samples")
    existing_diagnostics = context.get("candidate_quality_scorecard_diagnostics")
    if existing_panel_fields is not None and existing_samples is not None:
        if final_empty_without_current_observation:
            panel_fields = _clear_panel_target_fields(existing_panel_fields)
        else:
            panel_fields = _clear_blocked_panel_target_fields(existing_panel_fields, existing_samples)
            panel_fields = _align_panel_fields_to_current_watch_target(panel_fields, current_watch_target)
        panel_fields = _normalize_pending_position_panel_fields(
            panel_fields,
            existing_position_summary_from_context(context),
        )
        candidate_samples = (
            list(existing_samples or [])
            if final_empty_without_current_observation
            else _replace_with_current_candidate(existing_samples, current_watch_target)
        )
        candidate_samples.extend(_derivation_process_samples(context, current_watch_target))
        samples = [
            _enrich_candidate_trace_inputs(sample, context)
            for sample in list(candidate_samples or [])
            if isinstance(sample, dict)
        ]
        return {
            "candidate_quality_panel_fields": sanitize_user_visible_text(panel_fields),
            "candidate_quality_samples": sanitize_user_visible_text(samples),
            "candidate_quality_scorecard_diagnostics": dict(existing_diagnostics or _build_diagnostics(samples)),
            "sniper_target_derivation": derivation_packet,
        }

    trade_gate_open = context.get("trade_gate_open", False)
    best_stock = context.get("best_stock")
    blocked_keys = blocked_current_observation_keys_from_context(context)
    if _candidate_blocks_panel_watch_target(best_stock) or _candidate_matches_blocked_panel_key(best_stock, blocked_keys):
        best_stock = None
    raw_watch_anchor = context.get("watch_anchor")
    watch_anchor = current_watch_target or (
        raw_watch_anchor
        if _candidate_can_be_panel_watch_target(raw_watch_anchor)
        and not _candidate_matches_blocked_panel_key(raw_watch_anchor, blocked_keys)
        else None
    )
    if current_watch_target and _candidate_key(best_stock) != _candidate_key(current_watch_target):
        best_stock = None
    step0_prediction_cn = str(context.get("step0_prediction_cn", "") or "").strip()
    final_gate = context.get("final_gate", {}) or {}
    has_personal_positions = bool(context.get("has_personal_positions", False))
    position_context_provided = bool(context.get("position_context_provided", False))
    existing_position_summary = context.get("existing_position_summary")
    if not isinstance(existing_position_summary, dict):
        personal_position_context = context.get("personal_position_context")
        if isinstance(personal_position_context, dict):
            existing_position_summary = personal_position_context.get("existing_position_summary")
    display_observation_candidates = context.get("display_observation_candidates", context.get("observation_candidates", [])) or []
    display_observation_candidates = _replace_or_prepend_candidate(display_observation_candidates, current_watch_target)
    waiting_stocks = context.get("waiting_stocks", []) or []
    daily_new_entry_limit = 1 if final_gate.get("can_new_entry") or trade_gate_open else 0

    samples = _dedupe_candidates(
        [
            _quality_candidate(
                best_stock,
                quality_role="主买对象" if daily_new_entry_limit > 0 else "核心观察",
                selection_quality="高",
                entry_cost_state="确认中",
                is_core=True,
                source_pool="best_stock",
            ),
            _quality_candidate(
                watch_anchor,
                quality_role="补位对象",
                selection_quality="中",
                entry_cost_state="确认中",
                source_pool="watch_anchor",
            ),
        ]
        + _derivation_process_samples(context, current_watch_target)
        + [
            _enrich_candidate_trace_inputs(candidate, context, source_pool="display_observation_candidates")
            for candidate in list(display_observation_candidates)
            if isinstance(candidate, dict)
        ]
        + [
            _enrich_candidate_trace_inputs(candidate, context, source_pool="waiting_stocks")
            for candidate in list(waiting_stocks)
            if isinstance(candidate, dict)
        ]
    )
    samples = [
        _enrich_candidate_trace_inputs(sample, context)
        for sample in samples
        if isinstance(sample, dict)
    ]

    panel_fields = _build_panel_fields(
        step0_prediction_cn=step0_prediction_cn,
        has_personal_positions=has_personal_positions,
        position_context_provided=position_context_provided,
        existing_position_summary=existing_position_summary,
        daily_new_entry_limit=daily_new_entry_limit,
        best_stock=best_stock,
        watch_anchor=watch_anchor,
    )
    panel_fields = _normalize_pending_position_panel_fields(panel_fields, existing_position_summary)
    if final_empty_without_current_observation:
        panel_fields = _clear_panel_target_fields(panel_fields)
    return {
        "candidate_quality_panel_fields": sanitize_user_visible_text(panel_fields),
        "candidate_quality_samples": sanitize_user_visible_text(samples),
        "candidate_quality_scorecard_diagnostics": _build_diagnostics(samples),
        "sniper_target_derivation": derivation_packet,
    }


def build_pk_decision_candidate_quality_scorecard_node(context, node_meta=None, node_lookup=None):
    payload = build_candidate_quality_scorecard_payload(context)
    return {
        "lines": [],
        "exports": payload,
        "module_logs": [
            {
                "module": "domains.execution_chain.pk_decision_nodes.candidate_quality_scorecard",
                "step": "build.scorecard",
                "status": "success",
                "message": "已生成候选质量评分卡",
                "details": payload["candidate_quality_scorecard_diagnostics"],
            }
        ],
    }
