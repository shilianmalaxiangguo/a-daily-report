from __future__ import annotations

from domains.execution_chain.pk_decision_nodes.candidate_surface_filter import (
    candidate_blocks_current_observation_target,
)
from report.execution_wording import (
    PREMARKET_50_EXECUTION_TEXT,
    PREMARKET_50_TRIGGER_TEXT,
    SAME_STOCK_T_CONFIRMATION_CLAUSE,
)


SCHEMA_VERSION = "sniper_target_derivation.v1"

FULL_STEP_HEADINGS = {
    "T0": "阶段一：原始候选",
    "T1": "阶段二：当前核心解析",
    "T2": "阶段三：仓位/账户修正",
    "T3": "阶段四：最终对象解析",
}

SOURCE_LABELS = {
    "execution_stage_context.best_stock": "执行链最佳候选",
    "execution_stage_context.watch_anchor": "执行链观察对象",
    "data.best_stock": "日报最佳候选",
    "data.watch_anchor": "日报观察对象",
    "market_research_snapshot.best_stock": "研究快照最佳候选",
    "market_research_snapshot.watch_anchor": "研究快照观察对象",
    "candidate_quality_panel_fields.primary_buy_candidate": "候选质量面板主对象",
    "candidate_quality_panel_fields.backup_candidate": "候选质量面板备用观察",
    "runtime.selected_position_candidate": "运行时当前核心",
    "final_target_resolution.watch_target": "最终解析观察对象",
    "final_target_resolution.display_target": "最终解析显示对象",
    "two_layer_decision_payload.front_decision.execution_object": "双层决策明日执行对象",
}

DIAGNOSIS_LAYER_LABELS = {
    "market": "市场层",
    "mainline": "主线层",
    "capital": "资金层",
    "stock": "个股层",
    "counter_evidence": "反证层",
}
DIAGNOSIS_SOURCE_DATE_MISSING = "来源日期缺失"


def clean_text(value, default=""):
    text = " ".join(str(value or "").replace("|", "｜").split()).strip()
    return text if text else default


def normalize_stock_code(value):
    text = str(value or "").strip()
    if "." in text:
        text = text.split(".", 1)[0]
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits[-6:] if len(digits) >= 6 else text


def stock_payload(value):
    if not isinstance(value, dict):
        return {}
    name = clean_text(value.get("name") or value.get("stock_name") or value.get("名称"))
    code = normalize_stock_code(value.get("code") or value.get("stock_code") or value.get("代码") or value.get("symbol"))
    if not (name or code):
        return {}
    payload = {
        "name": name,
        "code": code,
    }
    for key, aliases in {
        "sector": ("sector", "sector_name", "industry", "板块", "所属板块"),
        "role": ("role", "candidate_role", "quality_role", "target_role", "sniper_role"),
    }.items():
        text = clean_text(next((value.get(alias) for alias in aliases if value.get(alias) not in (None, "")), ""))
        if text:
            payload[key] = text
    return payload


def stock_key(value):
    payload = stock_payload(value)
    return payload.get("code") or payload.get("name") or ""


def stock_label(value):
    payload = stock_payload(value)
    name = payload.get("name", "")
    code = payload.get("code", "")
    if name and code:
        return f"{name}({code})"
    return name or code or "暂无"


def source_label(value):
    text = clean_text(value)
    if not text:
        return "-"
    if text in SOURCE_LABELS:
        return SOURCE_LABELS[text]
    for prefix, label in (
        ("execution_stage_context.candidate_quality_samples", "执行链候选质量样本"),
        ("data.candidate_quality_samples", "日报候选质量样本"),
        ("market_research_snapshot.candidate_quality_samples", "研究快照候选质量样本"),
    ):
        if text.startswith(prefix):
            suffix = text[len(prefix):]
            return f"{label}{suffix}"
    return text


def full_step_heading(step_id, label=""):
    key = clean_text(step_id)
    return FULL_STEP_HEADINGS.get(key) or clean_text(label) or key


def _first_stock_payload(*values):
    for value in values:
        payload = stock_payload(value)
        if payload:
            return payload
    return {}


def _first_allowed_stock_payload(*values, allow_process=False):
    for value in values:
        if not isinstance(value, dict):
            continue
        if not allow_process and candidate_blocks_current_observation_target(value):
            continue
        payload = stock_payload(value)
        if payload:
            return payload
    return {}


def _candidate_quality_field_sources(panel_fields):
    if not isinstance(panel_fields, dict):
        return []
    return [
        ("candidate_quality_panel_fields.primary_buy_candidate", panel_fields.get("primary_buy_candidate")),
        ("candidate_quality_panel_fields.backup_candidate", panel_fields.get("backup_candidate")),
    ]


def _raw_source_candidates(data=None, execution_stage_context=None, market_research_snapshot=None):
    rows = []
    sources = [
        ("execution_stage_context.best_stock", (execution_stage_context or {}).get("best_stock")),
        ("execution_stage_context.watch_anchor", (execution_stage_context or {}).get("watch_anchor")),
        ("data.best_stock", (data or {}).get("best_stock")),
        ("data.watch_anchor", (data or {}).get("watch_anchor")),
        ("market_research_snapshot.best_stock", (market_research_snapshot or {}).get("best_stock")),
        ("market_research_snapshot.watch_anchor", (market_research_snapshot or {}).get("watch_anchor")),
    ]
    sources.extend(_candidate_quality_field_sources((execution_stage_context or {}).get("candidate_quality_panel_fields")))
    sources.extend(_candidate_quality_field_sources((data or {}).get("candidate_quality_panel_fields")))
    sources.extend(_candidate_quality_field_sources((market_research_snapshot or {}).get("candidate_quality_panel_fields")))
    for source, candidate in sources:
        payload = stock_payload(candidate)
        if payload:
            rows.append((source, payload))
    for source_name, source in (
        ("execution_stage_context.candidate_quality_samples", execution_stage_context),
        ("data.candidate_quality_samples", data),
        ("market_research_snapshot.candidate_quality_samples", market_research_snapshot),
    ):
        samples = (source or {}).get("candidate_quality_samples")
        if not isinstance(samples, list):
            continue
        for index, candidate in enumerate(samples[:8], start=1):
            payload = stock_payload(candidate)
            if payload:
                rows.append((f"{source_name}[{index}]", payload))
    return rows


def _selected_candidate(data=None, execution_stage_context=None, market_research_snapshot=None, selected_position_candidate=None):
    return _first_allowed_stock_payload(
        selected_position_candidate,
        (execution_stage_context or {}).get("current_core_candidate"),
        (market_research_snapshot or {}).get("current_core_candidate"),
        (data or {}).get("current_core_candidate"),
        (execution_stage_context or {}).get("selected_position_candidate"),
        (market_research_snapshot or {}).get("selected_position_candidate"),
        (data or {}).get("selected_position_candidate"),
    )


def _capital_priority(final_target_resolution=None):
    resolution = final_target_resolution if isinstance(final_target_resolution, dict) else {}
    decision = resolution.get("capital_priority_decision")
    if not isinstance(decision, dict):
        return ""
    return clean_text(decision.get("capital_priority"))


def _stocks_match(left, right):
    left_payload = stock_payload(left)
    right_payload = stock_payload(right)
    left_code = left_payload.get("code")
    right_code = right_payload.get("code")
    if left_code and right_code and left_code == right_code:
        return True
    left_name = left_payload.get("name")
    right_name = right_payload.get("name")
    return bool(left_name and right_name and left_name == right_name)


def _display_target_is_proxy(resolution):
    return bool(
        isinstance(resolution, dict)
        and _stocks_match(resolution.get("display_target"), resolution.get("tradable_proxy_target"))
    )


def _canonical_resolution(final_target_resolution=None, selected_candidate=None):
    resolution = final_target_resolution if isinstance(final_target_resolution, dict) else {}
    priority = _capital_priority(resolution)
    if priority == "wait":
        target = _first_allowed_stock_payload(resolution.get("watch_target"))
        return target, "final_target_resolution.watch_target", "观察对象"
    if priority in {"old_position_t", "old_position", "existing_position", "existing_position_t"} and not _display_target_is_proxy(resolution):
        target = _first_allowed_stock_payload(
            resolution.get("watch_target"),
            resolution.get("new_entry_target"),
            resolution.get("process_target"),
            selected_candidate,
        )
        return target, "final_target_resolution.watch_target", "观察对象"
    if priority == "tradable_proxy" or _display_target_is_proxy(resolution):
        target = _first_allowed_stock_payload(
            resolution.get("display_target"),
            resolution.get("tradable_proxy_target"),
            resolution.get("watch_target"),
            selected_candidate,
        )
        return target, "final_target_resolution.display_target", "执行对象"
    if priority in {"new_entry", "new_entry_after_old_exit"}:
        target = _first_allowed_stock_payload(
            resolution.get("display_target"),
            resolution.get("new_entry_target"),
            resolution.get("watch_target"),
            resolution.get("process_target"),
            selected_candidate,
        )
        return target, "final_target_resolution.display_target", "执行对象"
    target = _first_allowed_stock_payload(
        resolution.get("watch_target"),
        resolution.get("display_target"),
        resolution.get("new_entry_target"),
        resolution.get("process_target"),
        selected_candidate,
    )
    return target, "final_target_resolution.watch_target", "观察对象"


def _canonical_target(final_target_resolution=None, selected_candidate=None):
    target, _, _ = _canonical_resolution(
        final_target_resolution=final_target_resolution,
        selected_candidate=selected_candidate,
    )
    return target


def _final_label(role):
    role = clean_text(role)
    if role == "无":
        return "无最终对象"
    return "最终执行对象" if role == "执行对象" else "最终观察对象"


def _final_reason(role, *, kept):
    label = _final_label(role)
    if kept:
        return f"同池比较后保留为{label}，等待资金、板块和承接继续确认"
    return "同池维度证据不足，未能通过最终对象比较"


def _candidate_loss_reason_map(two_layer_decision_payload=None):
    payload = two_layer_decision_payload if isinstance(two_layer_decision_payload, dict) else {}
    verdict = payload.get("candidate_pool_verdict") if isinstance(payload.get("candidate_pool_verdict"), dict) else {}
    rows = []
    for key in ("important_losers", "downgraded_or_rejected_top3"):
        value = verdict.get(key)
        if isinstance(value, list):
            rows.extend(value)
    reasons = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = stock_key(row.get("stock"))
        reason = clean_text(row.get("loss_reason"))
        if key and reason and key not in reasons:
            reasons[key] = reason
    return reasons


def _step_reason_for_candidate(candidate, canonical_role, *, kept, loss_reasons=None):
    if kept:
        return _final_reason(canonical_role, kept=True)
    key = stock_key(candidate)
    reason = (loss_reasons or {}).get(key, "")
    return reason or _final_reason(canonical_role, kept=False)


def _canonical_role(packet):
    packet = packet if isinstance(packet, dict) else {}
    target = packet.get("canonical_target") if isinstance(packet.get("canonical_target"), dict) else {}
    role = clean_text(packet.get("canonical_role"))
    if role:
        return role
    role = clean_text(target.get("role"))
    return role or "观察对象"


def _canonical_role_label(packet):
    return _final_label(_canonical_role(packet))


def _canonical_role_text(packet):
    role = _canonical_role(packet)
    if role == "无":
        return "无"
    return "执行对象" if role == "执行对象" else "观察对象"


def _canonical_role_for_action(role, position_pct):
    if role == "执行对象":
        return "执行对象"
    try:
        return "执行对象" if int(position_pct or 0) > 0 else "观察对象"
    except (TypeError, ValueError):
        return "观察对象"


def _with_role(target, role):
    payload = dict(target or {})
    if payload:
        payload["role"] = role
    return payload


def _two_layer_execution_target(two_layer_decision_payload=None):
    payload = two_layer_decision_payload if isinstance(two_layer_decision_payload, dict) else {}
    front = payload.get("front_decision") if isinstance(payload.get("front_decision"), dict) else {}
    raw_target = front.get("execution_object")
    if candidate_blocks_current_observation_target(raw_target):
        return {}
    target = stock_payload(raw_target)
    if not target:
        return {}
    identity = clean_text(front.get("execution_identity"))
    position_plan = clean_text(front.get("position_plan"))
    if identity != "明日执行对象" and position_plan != "50%条件执行":
        return {}
    return target


def _canonical_for_packet(
    final_target_resolution=None,
    selected_candidate=None,
    position_decision=None,
    two_layer_decision_payload=None,
):
    two_layer_target = _two_layer_execution_target(two_layer_decision_payload)
    if two_layer_target:
        return (
            _with_role(two_layer_target, "执行对象"),
            "two_layer_decision_payload.front_decision.execution_object",
            "执行对象",
        )
    priority = _capital_priority(final_target_resolution)
    resolution = final_target_resolution if isinstance(final_target_resolution, dict) else {}
    has_watch_target = bool(_first_allowed_stock_payload(resolution.get("watch_target")))
    if _position_pct(position_decision) <= 0 and (priority == "wait" or (priority == "" and not has_watch_target)):
        return {}, "position_decision", "观察对象"
    target, source, role = _canonical_resolution(
        final_target_resolution=final_target_resolution,
        selected_candidate=selected_candidate,
    )
    role = _canonical_role_for_action(role, _position_pct(position_decision))
    return _with_role(target, role), source, role


def _position_pct(position_decision=None):
    if not isinstance(position_decision, dict):
        return 0
    try:
        value = str(position_decision.get("target_position_pct") or position_decision.get("position_pct") or 0)
        return int(float(value.replace("%", "").strip() or 0))
    except (TypeError, ValueError):
        return 0


def _final_action(position_decision=None, final_gate=None, final_target_resolution=None, two_layer_decision_payload=None):
    two_layer_target = _two_layer_execution_target(two_layer_decision_payload)
    if two_layer_target:
        return {
            "position_pct": 50,
            "action": PREMARKET_50_EXECUTION_TEXT,
            "reason": "双层决策已给出明日执行对象和50%条件执行条件",
        }
    pct = _position_pct(position_decision)
    gate = final_gate if isinstance(final_gate, dict) else {}
    resolution = final_target_resolution if isinstance(final_target_resolution, dict) else {}
    priority = resolution.get("capital_priority_decision") if isinstance(resolution.get("capital_priority_decision"), dict) else {}
    priority_value = clean_text(priority.get("capital_priority"))
    action = clean_text(
        gate.get("final_action")
        or priority.get("reason")
        or (position_decision or {}).get("final_action")
        or (position_decision or {}).get("sizing_reason")
    )
    if priority_value == "same_stock_t":
        if pct <= 0:
            action = "只观察，不新增参与"
        elif "B1" not in action:
            action = SAME_STOCK_T_CONFIRMATION_CLAUSE
    elif not action:
        action = "只观察，不新增参与" if pct <= 0 else PREMARKET_50_TRIGGER_TEXT
    return {
        "position_pct": pct,
        "action": action,
        "reason": clean_text(priority.get("reason") or (position_decision or {}).get("sizing_reason")),
    }


def _append_step(steps, *, step_id, label, source, candidate, role, decision, reason, source_rank=None):
    payload = stock_payload(candidate)
    if not payload:
        return
    steps.append(
        {
            "step_id": step_id,
            "label": label,
            "source": source,
            "candidate": payload,
            "role": role,
            "decision": decision,
            "reason": reason,
            "source_rank": source_rank,
        }
    )


def _selection_workflow_from_sources(*sources):
    for source in sources:
        workflow = source.get("selection_workflow") if isinstance(source, dict) else {}
        if isinstance(workflow, dict) and workflow.get("schema_version") == "selection_workflow.v1":
            return workflow
    return {}


def _workflow_final(workflow):
    workflow = workflow if isinstance(workflow, dict) else {}
    final = workflow.get("final")
    return final if isinstance(final, dict) else {}


def _workflow_position_pct(workflow):
    final = _workflow_final(workflow)
    try:
        return int(float(str(final.get("position_pct") or 0).replace("%", "").strip() or 0))
    except (TypeError, ValueError):
        return 0


def _workflow_final_target(workflow):
    final = _workflow_final(workflow)
    return stock_payload(final.get("execution_object"))


def _workflow_controls_derivation(workflow):
    workflow = workflow if isinstance(workflow, dict) else {}
    final = _workflow_final(workflow)
    return bool(final)


def _packet_from_selection_workflow(workflow, target_date="", bayesian_diagnosis=None):
    final = _workflow_final(workflow)
    position_pct = _workflow_position_pct(workflow)
    canonical = stock_payload(final.get("execution_object"))
    canonical_role = "执行对象" if canonical and position_pct > 0 else "无"
    if canonical:
        canonical["role"] = canonical_role
    canonical_key = stock_key(canonical)
    steps = []
    for index, item in enumerate(workflow.get("candidate_pool") or [], start=1):
        if not isinstance(item, dict):
            continue
        stock = stock_payload(item.get("stock"))
        if not stock:
            continue
        same = bool(canonical_key and stock_key(stock) == canonical_key)
        _append_step(
            steps,
            step_id="N5-N8",
            label="工作流候选生命周期",
            source="selection_workflow.candidate_pool",
            candidate=stock,
            role=clean_text(item.get("status"), "最终执行对象" if same else "过程候选"),
            decision="保留" if same else "被淘汰",
            reason=clean_text(item.get("entered_reason") or item.get("current_reason") or item.get("eliminated_reason"), "-"),
            source_rank=index,
        )
        if not same and clean_text(item.get("eliminated_reason")) and item.get("eliminated_reason") != steps[-1].get("reason"):
            steps[-1]["reason"] = f"{steps[-1]['reason']}；{clean_text(item.get('eliminated_reason'))}"
    packet = {
        "schema_version": SCHEMA_VERSION,
        "target_date": clean_text(target_date or workflow.get("target_date")),
        "canonical_target": canonical,
        "canonical_source": "selection_workflow.final.execution_object",
        "canonical_role": canonical_role,
        "final_action": {
            "position_pct": position_pct,
            "action": clean_text(final.get("action_text"), "0%不参与"),
            "reason": "来自 selection_workflow.v1 的 N8 仓位与执行条件",
        },
        "steps": steps,
        "warnings": [],
        "bayesian_diagnosis": dict(bayesian_diagnosis or {}) if isinstance(bayesian_diagnosis, dict) else {},
    }
    packet["compact_ascii"] = render_compact_ascii(packet)
    packet["full_ascii"] = render_full_ascii(packet)
    return packet


def _render_step_line(step, *, include_source_rank=False):
    parts = []
    if include_source_rank and step.get("source_rank") is not None:
        parts.append(f"来源序号={clean_text(step.get('source_rank'), '-')}")
    parts.extend(
        [
            f"来源={source_label(step.get('source'))}",
            f"候选={stock_label(step.get('candidate'))}",
            f"身份={clean_text(step.get('role'), '-')}",
            f"去向={clean_text(step.get('decision'), '-')}",
            f"原因={clean_text(step.get('reason'), '-')}",
        ]
    )
    return "|-- " + " ".join(parts)


def _render_bayesian_diagnosis_lines(packet):
    packet = packet if isinstance(packet, dict) else {}
    diagnosis = packet.get("bayesian_diagnosis") if isinstance(packet.get("bayesian_diagnosis"), dict) else {}
    if diagnosis.get("schema_version") != "bayesian_diagnosis.v1":
        return []
    conclusion = diagnosis.get("conclusion") if isinstance(diagnosis.get("conclusion"), dict) else {}
    path = diagnosis.get("path") if isinstance(diagnosis.get("path"), list) else []
    path_conclusion = clean_text(conclusion.get("path_conclusion"), "路径结论待确认")
    position_pct = clean_text(conclusion.get("position_pct"), "0")
    action_text = clean_text(conclusion.get("action_text"), "0%不参与")
    position_text = _position_display_text(position_pct, action_text)
    alignment = clean_text(conclusion.get("final_action_alignment"), "无法判断")
    lines = [
        "路径诊断复盘",
        f"|-- 路径结论={path_conclusion} 最终动作一致性={alignment} 仓位={position_text} 动作={action_text}",
    ]
    for step in path:
        if not isinstance(step, dict):
            continue
        layer = clean_text(step.get("layer"), "-")
        layer_label = DIAGNOSIS_LAYER_LABELS.get(layer, layer)
        source_date = clean_text(step.get("source_date"), DIAGNOSIS_SOURCE_DATE_MISSING)
        if source_date == "-":
            source_date = DIAGNOSIS_SOURCE_DATE_MISSING
        input_summary = clean_text(step.get("input_summary"), "-")
        judgement = clean_text(step.get("judgement"), "-")
        passes_forward = clean_text(step.get("passes_forward"), "-")
        cannot_conclude = [
            clean_text(item)
            for item in (step.get("cannot_conclude") if isinstance(step.get("cannot_conclude"), list) else [])
            if clean_text(item)
        ]
        lines.append(
            f"|-- 层级={layer_label} 日期={source_date} 输入={input_summary} 判断={judgement} 传递={passes_forward}"
        )
        if cannot_conclude:
            lines.append(f"|   不能推出={'；'.join(cannot_conclude)}")
    return lines


def _position_display_text(position_pct, action_text=""):
    action = clean_text(action_text, "")
    if "满仓" in action:
        return "满仓"
    pct = clean_text(position_pct, "0").replace("％", "%")
    if pct.endswith("%"):
        return pct
    return f"{pct}%"


def build_sniper_target_derivation_packet(
    *,
    data=None,
    execution_stage_context=None,
    market_research_snapshot=None,
    final_target_resolution=None,
    selected_position_candidate=None,
    position_decision=None,
    final_gate=None,
    two_layer_decision_payload=None,
    bayesian_diagnosis=None,
    target_date="",
):
    data = data if isinstance(data, dict) else {}
    execution_stage_context = execution_stage_context if isinstance(execution_stage_context, dict) else {}
    market_research_snapshot = market_research_snapshot if isinstance(market_research_snapshot, dict) else {}
    workflow = _selection_workflow_from_sources(data, execution_stage_context, market_research_snapshot)
    if _workflow_controls_derivation(workflow):
        return _packet_from_selection_workflow(
            workflow,
            target_date=target_date or data.get("target_date") or market_research_snapshot.get("target_date"),
            bayesian_diagnosis=bayesian_diagnosis,
        )
    selected = _selected_candidate(
        data=data,
        execution_stage_context=execution_stage_context,
        market_research_snapshot=market_research_snapshot,
        selected_position_candidate=selected_position_candidate,
    )
    canonical, canonical_source, canonical_role = _canonical_for_packet(
        final_target_resolution=final_target_resolution,
        selected_candidate=selected,
        position_decision=position_decision,
        two_layer_decision_payload=two_layer_decision_payload,
    )
    if canonical:
        canonical.setdefault("role", canonical_role or "观察对象")
    canonical_key = stock_key(canonical)
    loss_reasons = _candidate_loss_reason_map(two_layer_decision_payload)
    steps = []
    seen_raw = set()
    warnings = []
    for source_rank, (source, candidate) in enumerate(_raw_source_candidates(data, execution_stage_context, market_research_snapshot), start=1):
        key = (source, stock_key(candidate))
        if key in seen_raw:
            continue
        seen_raw.add(key)
        same = bool(canonical_key and stock_key(candidate) == canonical_key)
        _append_step(
            steps,
            step_id="T0",
            label="原始候选",
            source=source,
            candidate=candidate,
            source_rank=source_rank,
            role="过程候选" if not same else "过程候选",
            decision="保留" if same else "被替换",
            reason=_step_reason_for_candidate(candidate, canonical_role, kept=same, loss_reasons=loss_reasons),
        )
        if not same:
            warnings.append(f"{source}={stock_label(candidate)} 已作为过程候选处理")
    if selected:
        same = bool(canonical_key and stock_key(selected) == canonical_key)
        _append_step(
            steps,
            step_id="T1",
            label="当前核心解析",
            source="runtime.selected_position_candidate",
            candidate=selected,
            role="当前核心",
            decision="保留" if same else "被替换",
            reason=_step_reason_for_candidate(selected, canonical_role, kept=same, loss_reasons=loss_reasons),
        )
    final_action = _final_action(
        position_decision=position_decision,
        final_gate=final_gate,
        final_target_resolution=final_target_resolution,
        two_layer_decision_payload=two_layer_decision_payload,
    )
    _append_step(
        steps,
        step_id="T3",
        label="最终对象解析",
        source=canonical_source,
        candidate=canonical,
        role=canonical.get("role") or "观察对象",
        decision="最终",
        reason=final_action.get("reason") or final_action.get("action") or f"统一作为{_final_label(canonical_role)}",
    )
    packet = {
        "schema_version": SCHEMA_VERSION,
        "target_date": clean_text(target_date or data.get("target_date") or market_research_snapshot.get("target_date")),
        "canonical_target": canonical,
        "canonical_source": canonical_source,
        "canonical_role": canonical_role,
        "final_action": final_action,
        "steps": steps,
        "warnings": warnings,
        "bayesian_diagnosis": dict(bayesian_diagnosis or {}) if isinstance(bayesian_diagnosis, dict) else {},
    }
    packet["compact_ascii"] = render_compact_ascii(packet)
    packet["full_ascii"] = render_full_ascii(packet)
    return packet


def render_compact_ascii(packet):
    packet = packet if isinstance(packet, dict) else {}
    if not stock_key(packet.get("canonical_target")):
        return []
    final_action = packet.get("final_action") if isinstance(packet.get("final_action"), dict) else {}
    position_pct = final_action.get("position_pct", 0)
    action_label = "只观察" if int(position_pct or 0) <= 0 else "按条件参与"
    canonical = packet.get("canonical_target") if isinstance(packet.get("canonical_target"), dict) else {}
    role_label = _canonical_role_label(packet)
    lines = ["原始候选", "|"]
    seen = set()
    for step in packet.get("steps") or []:
        if not isinstance(step, dict) or step.get("step_id") == "T3":
            continue
        label = stock_label(step.get("candidate"))
        key = (label, step.get("role"), step.get("decision"))
        if key in seen:
            continue
        seen.add(key)
        lines.append(f"+-- {label}: {clean_text(step.get('role'), '过程候选')} / {clean_text(step.get('decision'), '过程证据')}")
        lines.append("|")
    lines.append(f"`-- {role_label}: {stock_label(canonical)}, {position_pct}%{action_label}")
    return lines


def render_full_ascii(packet):
    packet = packet if isinstance(packet, dict) else {}
    lines = _render_bayesian_diagnosis_lines(packet)
    if not stock_key(packet.get("canonical_target")):
        return lines
    current_step_id = ""
    final_target_steps = []
    for step in packet.get("steps") or []:
        if not isinstance(step, dict):
            continue
        step_id = clean_text(step.get("step_id"))
        label = clean_text(step.get("label"))
        if step_id == "T3":
            final_target_steps.append(step)
            continue
        if step_id != current_step_id:
            if lines:
                lines.append("|")
            lines.append(full_step_heading(step_id, label))
            current_step_id = step_id
        lines.append(_render_step_line(step, include_source_rank=True))
    final_action = packet.get("final_action") if isinstance(packet.get("final_action"), dict) else {}
    lines.append("|")
    lines.append(full_step_heading("T2"))
    lines.append(
        "|-- 仓位={position_text} 动作={action} 原因={reason}".format(
            position_text=_position_display_text(
                final_action.get("position_pct", 0),
                final_action.get("action"),
            ),
            action=clean_text(final_action.get("action"), "只观察，不新增参与"),
            reason=clean_text(final_action.get("reason"), "-"),
        )
    )
    lines.append("|")
    lines.append(full_step_heading("T3"))
    for step in final_target_steps:
        lines.append(_render_step_line(step))
    lines.append(f"`-- 最终对象={stock_label(packet.get('canonical_target'))} 身份={_canonical_role_text(packet)}")
    return lines


def compact_ascii_from_packet(packet):
    packet = packet if isinstance(packet, dict) else {}
    lines = packet.get("compact_ascii")
    if isinstance(lines, list) and lines:
        return [str(line) for line in lines]
    return render_compact_ascii(packet)


def full_ascii_from_packet(packet):
    packet = packet if isinstance(packet, dict) else {}
    lines = packet.get("full_ascii")
    if isinstance(lines, list) and lines:
        return _normalize_cached_full_ascii_lines(lines)
    return render_full_ascii(packet)


def _normalize_cached_full_ascii_lines(lines):
    normalized = []
    for line in lines or []:
        text = str(line)
        if "动作=满仓条件执行" in text:
            text = text.replace("仓位=50% 动作=满仓条件执行", "仓位=满仓 动作=满仓条件执行")
            text = text.replace("仓位=50 动作=满仓条件执行", "仓位=满仓 动作=满仓条件执行")
        normalized.append(text)
    return normalized


def compact_section(packet, *, heading="### 最终标的传导链"):
    lines = compact_ascii_from_packet(packet)
    if not lines:
        return []
    section = []
    if heading:
        section.extend([heading, ""])
    section.extend(["```text", *lines, "```"])
    return section


def full_section(packet, *, heading="## 狙击手最终标的完整路径图（过程证据）"):
    packet = packet if isinstance(packet, dict) else {}
    lines = full_ascii_from_packet(packet)
    if not lines:
        return []
    section = []
    if heading and not stock_key(packet.get("canonical_target")):
        heading = "## 路径诊断复盘（过程证据）"
    if heading:
        section.extend([heading, ""])
    section.extend(["```text", *lines, "```"])
    return section
