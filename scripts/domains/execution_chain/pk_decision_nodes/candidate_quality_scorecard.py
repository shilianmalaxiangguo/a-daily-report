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
                if field in ("risk_flags", "cost_flags"):
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


def _quality_candidate(candidate, *, quality_role="", selection_quality="", entry_cost_state="", is_core=None):
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
    return enriched


def _build_panel_fields(
    *,
    step0_prediction_cn,
    has_personal_positions,
    daily_new_entry_limit,
    best_stock,
    watch_anchor,
):
    backup_candidate = watch_anchor
    if _candidate_key(best_stock) and _candidate_key(best_stock) == _candidate_key(watch_anchor):
        backup_candidate = None
    return {
        "market_emotion_label": step0_prediction_cn,
        "account_attention_load": "有持仓需先处理" if has_personal_positions else "无持仓负担",
        "holding_priority_action": "先处理旧仓，再看新增" if has_personal_positions else "无旧仓时只等参与窗口",
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
        samples = list(existing_samples or [])
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
            ),
            _quality_candidate(
                watch_anchor,
                quality_role="补位对象",
                selection_quality="中",
                entry_cost_state="确认中",
            ),
        ]
        + list(display_observation_candidates)
        + list(waiting_stocks)
    )

    panel_fields = _build_panel_fields(
        step0_prediction_cn=step0_prediction_cn,
        has_personal_positions=has_personal_positions,
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
