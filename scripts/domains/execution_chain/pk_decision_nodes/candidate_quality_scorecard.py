from report.surface_wording import sanitize_user_visible_text


def _candidate_key(candidate):
    candidate = candidate or {}
    return str(candidate.get("code") or candidate.get("代码") or candidate.get("name") or candidate.get("名称") or "").strip()


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


def _build_panel_fields(
    *,
    step0_prediction_cn,
    has_personal_positions,
    position_context_provided,
    daily_new_entry_limit,
    best_stock,
    watch_anchor,
):
    backup_candidate = watch_anchor
    if _candidate_key(best_stock) and _candidate_key(best_stock) == _candidate_key(watch_anchor):
        backup_candidate = None
    if has_personal_positions:
        account_attention_load = "有持仓需先处理"
        holding_priority_action = "先处理旧仓，再看新增"
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
    existing_panel_fields = context.get("candidate_quality_panel_fields")
    existing_samples = context.get("candidate_quality_samples")
    existing_diagnostics = context.get("candidate_quality_scorecard_diagnostics")
    if existing_panel_fields is not None and existing_samples is not None:
        samples = [
            _enrich_candidate_trace_inputs(sample, context)
            for sample in list(existing_samples or [])
            if isinstance(sample, dict)
        ]
        return {
            "candidate_quality_panel_fields": sanitize_user_visible_text(existing_panel_fields),
            "candidate_quality_samples": sanitize_user_visible_text(samples),
            "candidate_quality_scorecard_diagnostics": dict(existing_diagnostics or _build_diagnostics(samples)),
        }

    trade_gate_open = context.get("trade_gate_open", False)
    best_stock = context.get("best_stock")
    watch_anchor = context.get("watch_anchor")
    step0_prediction_cn = str(context.get("step0_prediction_cn", "") or "").strip()
    final_gate = context.get("final_gate", {}) or {}
    has_personal_positions = bool(context.get("has_personal_positions", False))
    position_context_provided = bool(context.get("position_context_provided", False))
    display_observation_candidates = context.get("display_observation_candidates", context.get("observation_candidates", [])) or []
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
        daily_new_entry_limit=daily_new_entry_limit,
        best_stock=best_stock,
        watch_anchor=watch_anchor,
    )
    return {
        "candidate_quality_panel_fields": sanitize_user_visible_text(panel_fields),
        "candidate_quality_samples": sanitize_user_visible_text(samples),
        "candidate_quality_scorecard_diagnostics": _build_diagnostics(samples),
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
