from __future__ import annotations

import datetime as _dt
import hashlib
import json
import re
from pathlib import Path

ARTIFACT_VERSION = 1

_TOPIC_ID_REPAIRS = {
    "AI算力基础设施": "ai-compute-infrastructure",
    "PCB电子材料": "pcb-electronic-materials",
    "算力基础设施": "compute-infrastructure",
    "电子材料": "electronic-materials",
}

_PHASE_TO_QUALIFICATION = {
    "观察期": "只作观察证据",
    "启动期": "进入淘汰赛复核",
    "主攻期": "进入淘汰赛复核",
    "分歧承接期": "只让核心进入复核",
    "高一致风险期": "只保留核心复核",
    "退潮期": "不进入明日复核",
    "过期回看期": "只作历史回看",
}

_PHASE_PRIORITY = {
    "主攻期": 0,
    "分歧承接期": 1,
    "高一致风险期": 2,
    "启动期": 3,
    "观察期": 4,
    "退潮期": 5,
    "过期回看期": 6,
}

_PHASE_SUMMARIES = {
    "观察期": "先观察，不进明日计划。",
    "启动期": "只提示板块进入淘汰赛复核，个股仍要走完整条件链。",
    "主攻期": "只说明板块可进入淘汰赛复核，不直接生成个股资格。",
    "分歧承接期": "明日只看核心承接，不从后排补涨里找机会。",
    "高一致风险期": "只保留核心复核，不追后排扩散。",
    "退潮期": "资金退或反证命中，不参与。",
    "过期回看期": "仅作历史回看，不影响明日动作。",
}

_TOPIC_LIFECYCLE_BOUNDARY = "题材阶段只作板块证据，不直接生成明日标的或个股资格。"

_PHASE_VALIDATION = {
    "观察期": {
        "watch_points": ["核心标的是否表态", "资金是否继续集中"],
        "upgrade_condition": "核心标的和资金证据同时补齐",
        "downgrade_condition": "只有热度，没有资金和核心承接",
        "invalidation": "关键证据仍然不足",
    },
    "启动期": {
        "watch_points": ["核心标的是否继续承接", "板块是否继续扩散"],
        "upgrade_condition": "核心承接继续，板块扩散不掉队",
        "downgrade_condition": "只有启动痕迹，没有后续承接",
        "invalidation": "核心失去承接或扩散转弱",
    },
    "主攻期": {
        "watch_points": ["核心承接是否强于后排", "分支成交额是否维持"],
        "upgrade_condition": "核心继续领跑，后排不扩大亏钱效应",
        "downgrade_condition": "核心承接弱于后排，扩散质量下降",
        "invalidation": "核心失去承接或资金撤出",
    },
    "分歧承接期": {
        "watch_points": ["核心是否继续承接", "后排亏钱效应是否扩大"],
        "upgrade_condition": "核心承接仍在，分歧没有扩大",
        "downgrade_condition": "核心承接转弱，后排开始失控",
        "invalidation": "核心破位且板块资金退潮",
    },
    "高一致风险期": {
        "watch_points": ["核心是否仍有承接", "后排是否继续掉队"],
        "upgrade_condition": "核心承接稳定，风险缓和",
        "downgrade_condition": "热度继续高于承接，后排继续失真",
        "invalidation": "一致风险扩大且核心承接失守",
    },
    "退潮期": {
        "watch_points": ["核心是否重新站回承接线", "资金是否重新回流"],
        "upgrade_condition": "核心重新站回承接线，资金回流",
        "downgrade_condition": "退潮延续，承接继续变弱",
        "invalidation": "核心破位且资金持续撤出",
    },
    "过期回看期": {
        "watch_points": ["只保留历史对照", "不把旧样本当今天动作"],
        "upgrade_condition": "有新的当日证据再重新评估",
        "downgrade_condition": "仅作历史对照，不进入动作",
        "invalidation": "没有新的当日证据",
    },
}


def _clean_text(value, default=""):
    text = str(value or "").strip()
    return text or default


def _dedupe(values):
    result = []
    for value in values or []:
        text = _clean_text(value)
        if text and text not in result:
            result.append(text)
    return result


def _split_terms(value):
    if value is None:
        return []
    if isinstance(value, dict):
        terms = []
        for key, item in value.items():
            terms.append(key)
            terms.extend(_split_terms(item))
        return [term for term in terms if term]
    if isinstance(value, (list, tuple, set)):
        terms = []
        for item in value:
            terms.extend(_split_terms(item))
        return [term for term in terms if term]
    text = _clean_text(value)
    if not text:
        return []
    for marker in (";", "；", "、", "|", "/", "，", ","):
        text = text.replace(marker, ",")
    return [_clean_text(part) for part in text.split(",") if _clean_text(part)]


def _join_lines(values, limit=3):
    return " / ".join(_dedupe(values)[:limit])


def _pick_first_dict(source, *paths):
    for path in paths:
        current = source
        for key in path:
            if not isinstance(current, dict):
                break
            current = current.get(key)
        if isinstance(current, dict) and current:
            return current
    return {}


def _pick_first_value(source, *paths):
    for path in paths:
        current = source
        for key in path:
            if not isinstance(current, dict):
                break
            current = current.get(key)
        else:
            if current not in (None, ""):
                return current
    return ""


def _slugify_topic_id(value):
    text = _clean_text(value)
    repairs = sorted(_TOPIC_ID_REPAIRS.items(), key=lambda item: len(item[0]), reverse=True)
    for source, target in repairs:
        text = text.replace(source, target)
    ascii_text = re.sub(r"[^0-9A-Za-z]+", "-", text).strip("-").lower()
    if ascii_text:
        return f"topic-{ascii_text}"
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]
    return f"topic-{digest}"


def _current_iso_timestamp():
    return _dt.datetime.now().astimezone().isoformat(timespec="seconds")


def _extract_trade_date(data):
    trade_date = _clean_text(
        _pick_first_value(
            data,
            ("trade_date",),
            ("date",),
            ("request", "target_date"),
            ("request", "trade_date"),
            ("normalized", "trade_date"),
            ("derived", "trade_date"),
            ("market_research_snapshot", "trade_date"),
            ("execution_stage_context", "trade_date"),
        )
    )
    if not trade_date:
        raise ValueError("missing trade_date")
    return trade_date


def _extract_source_report(data, trade_date):
    report_path = _clean_text(
        _pick_first_value(
            data,
            ("source_report", "path"),
            ("request", "source_report_path"),
            ("request", "report_path"),
            ("report_path",),
            ("markdown_report_path",),
            ("rendered", "report_path"),
        )
    )
    variant = _clean_text(_pick_first_value(data, ("source_report", "variant"), ("request", "report_variant")), "full")
    if not report_path and trade_date:
        report_path = f"reports/{trade_date}_A股日报_完整版.md"
    return {"path": report_path, "variant": variant or "full"}


def _extract_previous_topic_index(data, previous_index):
    if isinstance(previous_index, dict) and previous_index:
        return previous_index
    return (
        _pick_first_dict(
            data,
            ("topic_lifecycle_index",),
            ("knowledge", "topic_lifecycle_index"),
            ("derived", "topic_lifecycle_index"),
            ("request", "topic_lifecycle_index"),
        )
        or {}
    )


def _extract_tag_snapshot(data):
    return (
        _pick_first_dict(
            data,
            ("realtime_tag_evidence_snapshot",),
            ("market_research_snapshot", "realtime_tag_evidence_snapshot"),
            ("execution_stage_context", "realtime_tag_evidence_snapshot"),
            ("derived", "market_research_snapshot", "realtime_tag_evidence_snapshot"),
            ("data", "realtime_tag_evidence_snapshot"),
        )
        or {}
    )


def _extract_mainline_summary(data):
    return (
        _pick_first_dict(
            data,
            ("mainline_turnover_summary",),
            ("market_research_snapshot", "mainline_turnover_summary"),
            ("derived", "mainline_turnover_summary"),
            ("data", "mainline_turnover_summary"),
        )
        or {}
    )


def _extract_decision_ledger_index(data):
    return (
        _pick_first_dict(
            data,
            ("decision_ledger_artifacts", "index"),
            ("decision_ledger_index",),
            ("derived", "decision_ledger_index"),
            ("data", "decision_ledger_index"),
        )
        or {}
    )


def _candidate_texts(candidate):
    candidate = candidate or {}
    anchor_reversal = candidate.get("anchor_reversal") if isinstance(candidate.get("anchor_reversal"), dict) else {}
    texts = [
        candidate.get("topic_name"),
        candidate.get("adopted_label"),
        candidate.get("adopted_name"),
        candidate.get("sector"),
        candidate.get("mainline"),
        candidate.get("trade_narrative_sector"),
        candidate.get("raw_sector"),
        candidate.get("stock_name"),
        candidate.get("name"),
        candidate.get("topic_hint"),
        candidate.get("parent_theme"),
        anchor_reversal.get("sector_anchor"),
        anchor_reversal.get("candidate_role"),
        anchor_reversal.get("relationship_to_anchor"),
        anchor_reversal.get("anchor_reversal_reason"),
        anchor_reversal.get("why_not_anchor"),
        anchor_reversal.get("anchor_reversal_decision"),
        anchor_reversal.get("limit_up_evidence_role"),
    ]
    texts.extend(_split_terms(candidate.get("aliases")))
    return _dedupe(texts)


def _group_labels(group):
    group = group or {}
    labels = [
        group.get("采用名称"),
        group.get("当日主攻分支"),
        group.get("大方向"),
    ]
    labels.extend(_split_terms(group.get("表层行业名")))
    labels.extend(_split_terms(group.get("辅助名称")))
    labels.extend(_split_terms(group.get("标签")))
    labels.extend(_split_terms(group.get("label")))
    return _dedupe(labels)


def _topic_match_score(candidate_texts, labels):
    score = 0
    for label in labels or []:
        for text in candidate_texts or []:
            if not label or not text:
                continue
            if label == text or label in text or text in label:
                score += 1
                break
    return score


def _empty_card(topic_name, *, parent_theme="", aliases=None):
    topic_name = _clean_text(topic_name)
    parent_theme = _clean_text(parent_theme)
    aliases = _dedupe(aliases or [])
    return {
        "topic_id": _slugify_topic_id(topic_name),
        "topic_name": topic_name,
        "adopted_label": topic_name,
        "parent_theme": parent_theme,
        "aliases": aliases,
        "lifecycle_phase": "观察期",
        "participation_qualification": _PHASE_TO_QUALIFICATION["观察期"],
        "phase_age_trade_days": 1,
        "first_seen_trade_date": "",
        "latest_seen_trade_date": "",
        "evidence_level": "C",
        "evidence": {
            "launch_catalyst": [],
            "fund_attack": [],
            "core_stocks": [],
            "spread_evidence": [],
            "divergence_evidence": [],
            "acceptance_evidence": [],
            "counter_evidence": [],
        },
        "tomorrow_validation": {
            "watch_points": [],
            "upgrade_condition": "",
            "downgrade_condition": "",
            "invalidation": "",
        },
        "report_effect": {
            "candidate_policy": _PHASE_TO_QUALIFICATION["观察期"],
            "summary": "",
            "report_slots": [],
        },
        "source_refs": [],
    }


def _seed_from_tag_group(group, trade_date, mainline_summary):
    group = group or {}
    topic_name = _clean_text(group.get("采用名称"))
    if not topic_name:
        return None
    parent_theme = _clean_text(group.get("大方向"))
    aliases = _dedupe(
        _split_terms(group.get("表层行业名"))
        + _split_terms(group.get("辅助名称"))
        + [group.get("当日主攻分支"), parent_theme]
    )
    card = _empty_card(topic_name, parent_theme=parent_theme, aliases=aliases)
    card["relationship_judgment"] = _clean_text(group.get("关系判断"))
    launch_catalyst = []
    if _clean_text(group.get("当日主攻分支")):
        launch_catalyst.append(_clean_text(group.get("当日主攻分支")))
    if _clean_text((mainline_summary or {}).get("confirmation_evidence")):
        launch_catalyst.append(_clean_text((mainline_summary or {}).get("confirmation_evidence")))
    if _clean_text((mainline_summary or {}).get("data_text")):
        launch_catalyst.append(_clean_text((mainline_summary or {}).get("data_text")))
    card["evidence"]["launch_catalyst"] = _dedupe(launch_catalyst)
    card["evidence"]["fund_attack"] = _dedupe([
        group.get("资金证据"),
        (mainline_summary or {}).get("action_text"),
    ])
    card["evidence"]["spread_evidence"] = _dedupe([
        group.get("扩散证据"),
        group.get("注意力证据"),
    ])
    if _clean_text(group.get("反证信息")):
        card["evidence"]["counter_evidence"].append(_clean_text(group.get("反证信息")))
    card["source_refs"].append({"type": "tag_snapshot", "path": "data.realtime_tag_evidence_snapshot"})
    return card


def _candidate_names(candidate):
    candidate = candidate or {}
    names = [
        candidate.get("stock_name"),
        candidate.get("name"),
        candidate.get("topic_name"),
        candidate.get("adopted_label"),
        candidate.get("sector"),
        candidate.get("mainline"),
        candidate.get("trade_narrative_sector"),
        candidate.get("raw_sector"),
    ]
    return [item for item in _dedupe(names) if item]


def _card_match_labels(card):
    card = card or {}
    labels = [
        card.get("topic_name"),
        card.get("adopted_label"),
        card.get("parent_theme"),
    ]
    labels.extend(_split_terms(card.get("aliases")))
    labels.extend(_split_terms(card.get("topic_id")))
    return _dedupe(labels)


def _match_card(candidates_texts, cards):
    best_index = None
    best_score = 0
    for index, card in enumerate(cards):
        labels = _card_match_labels(card)
        score = _topic_match_score(candidates_texts, labels)
        if score > best_score:
            best_index = index
            best_score = score
    return best_index if best_score > 0 else None


def _normalize_trace_candidate(trace):
    trace = trace if isinstance(trace, dict) else {}
    anchor_reversal = trace.get("anchor_reversal") if isinstance(trace.get("anchor_reversal"), dict) else {}
    return {
        "source_type": "candidate_trace",
        "name": trace.get("stock_name") or trace.get("name") or "",
        "code": trace.get("stock_code") or trace.get("code") or "",
        "sector": trace.get("sector") or "",
        "mainline": trace.get("mainline") or "",
        "trade_narrative_sector": trace.get("sector") or trace.get("trade_narrative_sector") or "",
        "final_action": trace.get("final_action") or "",
        "branch_path": trace.get("branch_path") or [],
        "anchor_reversal_decision": anchor_reversal.get("anchor_reversal_decision") or "",
        "anchor_reversal_reason": anchor_reversal.get("anchor_reversal_reason") or "",
        "why_not_anchor": anchor_reversal.get("why_not_anchor") or "",
        "candidate_role": anchor_reversal.get("candidate_role") or "",
        "relationship_to_anchor": anchor_reversal.get("relationship_to_anchor") or "",
        "limit_up_evidence_role": anchor_reversal.get("limit_up_evidence_role") or "",
        "position_plan_pct": trace.get("position_plan_pct"),
        "market_participation_qualification": trace.get("market_participation_qualification") or "",
        "participation_review_status": trace.get("participation_review_status") or "",
        "selection_result_status": trace.get("selection_result", {}).get("status") if isinstance(trace.get("selection_result"), dict) else "",
        "missing_data": trace.get("missing_data") or [],
        "trigger_condition": trace.get("trigger_condition") or "",
        "failure_condition": trace.get("failure_condition") or "",
    }


def _normalize_decision_ledger_case(case):
    case = case if isinstance(case, dict) else {}
    hypothesis = case.get("hypothesis") if isinstance(case.get("hypothesis"), dict) else {}
    selection_result = case.get("selection_result") if isinstance(case.get("selection_result"), dict) else {}
    participation_review = case.get("participation_review") if isinstance(case.get("participation_review"), dict) else {}
    planned = case.get("planned_participation") if isinstance(case.get("planned_participation"), dict) else {}
    return {
        "source_type": "decision_ledger_case",
        "name": case.get("stock_name") or "",
        "code": case.get("stock_code") or "",
        "sector": case.get("mainline") or hypothesis.get("sector_candidate") or case.get("sector") or "",
        "mainline": case.get("mainline") or hypothesis.get("market_branch") or "",
        "trade_narrative_sector": case.get("mainline") or hypothesis.get("sector_candidate") or "",
        "final_action": planned.get("action") or "",
        "position_plan_pct": case.get("position_plan_pct"),
        "market_participation_qualification": case.get("market_participation_qualification") or "",
        "participation_review_status": case.get("participation_review_status") or participation_review.get("status") or "",
        "selection_result_status": selection_result.get("status") or "",
        "selection_result_reason": selection_result.get("reason") or "",
        "missing_data": case.get("missing_fields") or [],
        "cancellation_conditions": case.get("cancellation_conditions") or [],
        "planned_participation": planned,
    }


def _normalize_direct_candidate(candidate):
    candidate = candidate if isinstance(candidate, dict) else {}
    source_type = candidate.get("source_type") or "direct_candidate"
    return {
        "source_type": source_type,
        "name": candidate.get("stock_name") or candidate.get("name") or "",
        "code": candidate.get("stock_code") or candidate.get("code") or "",
        "sector": candidate.get("sector") or candidate.get("topic_name") or candidate.get("mainline") or "",
        "mainline": candidate.get("mainline") or "",
        "trade_narrative_sector": candidate.get("trade_narrative_sector") or candidate.get("sector") or "",
        "final_action": candidate.get("final_action") or "",
        "anchor_reversal_decision": candidate.get("anchor_reversal_decision") or "",
        "anchor_reversal_reason": candidate.get("anchor_reversal_reason") or "",
        "why_not_anchor": candidate.get("why_not_anchor") or "",
        "candidate_role": candidate.get("candidate_role") or "",
        "relationship_to_anchor": candidate.get("relationship_to_anchor") or "",
        "position_plan_pct": candidate.get("position_plan_pct"),
        "market_participation_qualification": candidate.get("market_participation_qualification") or "",
        "participation_review_status": candidate.get("participation_review_status") or "",
        "selection_result_status": candidate.get("selection_result_status") or "",
        "selection_result_reason": candidate.get("selection_result_reason") or "",
        "missing_data": candidate.get("missing_data") or [],
    }


def _extract_candidate_rows(data):
    rows = []
    selected = _pick_first_dict(
        data,
        ("selected_position_candidate",),
        ("current_core_candidate",),
        ("front_page_selected_position_candidate",),
    )
    if selected:
        rows.append(_normalize_direct_candidate(selected))

    for candidate in _pick_first_value(data, ("extreme_conviction_list",), ("execution_stage_context", "extreme_conviction_list")) or []:
        if isinstance(candidate, dict):
            rows.append(_normalize_direct_candidate(candidate))

    for trace in _pick_first_value(data, ("candidate_traces",), ("execution_stage_context", "candidate_traces")) or []:
        if isinstance(trace, dict):
            rows.append(_normalize_trace_candidate(trace))

    candidate_artifact = _pick_first_dict(data, ("candidate_trace_artifact", "payload"))
    for trace in candidate_artifact.get("traces") or []:
        if isinstance(trace, dict):
            rows.append(_normalize_trace_candidate(trace))

    ledger_index = _extract_decision_ledger_index(data)
    for records in (ledger_index.get("by_stock_code") or {}).values():
        for case in records or []:
            if isinstance(case, dict):
                rows.append(_normalize_decision_ledger_case(case))

    return rows


def _collect_card_evidence_from_candidate(card, candidate):
    evidence = card["evidence"]
    name = _clean_text(candidate.get("name") or candidate.get("stock_name"))
    code = _clean_text(candidate.get("code") or candidate.get("stock_code"))
    sector = _clean_text(candidate.get("trade_narrative_sector") or candidate.get("sector"))
    mainline = _clean_text(candidate.get("mainline"))
    candidate_text = " ".join(_candidate_names(candidate))
    topic_name = _clean_text(card.get("topic_name"))
    labels = _card_match_labels(card)
    if not _topic_match_score([candidate_text, sector, mainline], labels):
        return

    if name or code:
        role = _clean_text(candidate.get("candidate_role") or candidate.get("selection_result_status") or candidate.get("market_participation_qualification") or "核心")
        if _clean_text(candidate.get("final_action")) and any(marker in _clean_text(candidate.get("final_action")) for marker in ("不参与", "只观察", "关键数据不完整")):
            role = _clean_text(candidate.get("candidate_role") or "观察")
        stock_entry = {"name": name or topic_name, "code": code, "role": role or "核心"}
        if stock_entry not in evidence["core_stocks"]:
            evidence["core_stocks"].append(stock_entry)

    if candidate.get("final_action"):
        action_text = _clean_text(candidate.get("final_action"))
        if any(marker in action_text for marker in ("只观察", "不参与", "降级", "退潮", "关键数据不完整")):
            evidence["counter_evidence"].append(action_text)
        elif any(marker in action_text for marker in ("参与", "执行", "确认", "主买", "补位")):
            evidence["acceptance_evidence"].append(action_text)

    if candidate.get("anchor_reversal_decision") in {"降级观察", "不参与"}:
        evidence["divergence_evidence"].append(
            _clean_text(candidate.get("anchor_reversal_reason") or candidate.get("why_not_anchor") or candidate.get("final_action"))
        )
        if candidate.get("anchor_reversal_reason"):
            evidence["counter_evidence"].append(_clean_text(candidate.get("anchor_reversal_reason")))

    if _clean_text(candidate.get("selection_result_status")) in {"预演命中", "错过后方案命中"}:
        evidence["acceptance_evidence"].append(_clean_text(candidate.get("selection_result_reason") or candidate.get("selection_result_status")))

    if _clean_text(candidate.get("participation_review_status")) in {"预演命中", "错过后方案命中"}:
        evidence["acceptance_evidence"].append(_clean_text(candidate.get("participation_review_status")))

    if _clean_text(candidate.get("participation_review_status")) in {"预演作废", "预演过早", "待补事实"}:
        evidence["counter_evidence"].append(_clean_text(candidate.get("participation_review_status")))


def _topic_has_history(previous_index, topic_id):
    history = (previous_index or {}).get("by_topic_id") or {}
    return bool(history.get(topic_id))


def _topic_history_dates(previous_index, topic_id):
    records = list(((previous_index or {}).get("by_topic_id") or {}).get(topic_id) or [])
    dates = []
    for record in records:
        if not isinstance(record, dict):
            continue
        trade_date = _clean_text(record.get("trade_date"))
        if trade_date and trade_date not in dates:
            dates.append(trade_date)
    return dates


def _topic_history_dates_by_labels(previous_index, labels):
    records_by_topic = ((previous_index or {}).get("by_topic_id") or {}).values()
    dates = []
    for records in records_by_topic:
        for record in list(records or []):
            if not isinstance(record, dict):
                continue
            recorded_name = _clean_text(record.get("topic_name") or record.get("adopted_label") or record.get("name"))
            if not recorded_name:
                continue
            if not any(
                label and (recorded_name == label or recorded_name in label or label in recorded_name)
                for label in labels
            ):
                continue
            trade_date = _clean_text(record.get("trade_date"))
            if trade_date and trade_date not in dates:
                dates.append(trade_date)
    return dates


def _phase_has_strong_counter_evidence(card):
    counter_text = " ".join(card["evidence"]["counter_evidence"] + card["evidence"]["divergence_evidence"])
    if not counter_text:
        return False
    return any(marker in counter_text for marker in ("退潮", "不参与", "失效", "作废", "破位", "撤出", "降级观察", "关键数据不完整", "反证", "亏钱效应"))


def _phase_has_risk_evidence(card):
    counter_text = " ".join(card["evidence"]["counter_evidence"] + card["evidence"]["divergence_evidence"])
    if not counter_text:
        return False
    return any(marker in counter_text for marker in ("高位一致", "后排补涨质量下降", "追高风险"))


def _infer_phase(card, *, previous_index=None):
    evidence = card["evidence"]
    launch = bool(evidence["launch_catalyst"])
    funds = bool(evidence["fund_attack"])
    core = bool(evidence["core_stocks"])
    spread = bool(evidence["spread_evidence"])
    acceptance = bool(evidence["acceptance_evidence"])
    divergence = bool(evidence["divergence_evidence"])
    counter = _phase_has_strong_counter_evidence(card)
    risk = _phase_has_risk_evidence(card)
    relation_judgment = _clean_text(card.get("relationship_judgment"))

    if counter:
        return "退潮期"
    if relation_judgment == "证据不足" and not (funds and core):
        return "观察期"
    if divergence and (core or acceptance):
        return "分歧承接期"
    if risk and (core or funds or spread or acceptance):
        return "高一致风险期"
    if launch and funds and core and spread:
        return "主攻期"
    if launch and (funds or core or spread or acceptance):
        return "启动期"
    if launch or funds or core or spread or acceptance:
        return "观察期"
    return "过期回看期" if _topic_has_history(previous_index, card["topic_id"]) else "观察期"


def _evidence_score(card):
    evidence = card["evidence"]
    return sum(
        len(evidence[key])
        for key in ("launch_catalyst", "fund_attack", "spread_evidence", "divergence_evidence", "acceptance_evidence", "counter_evidence")
    ) + len(evidence["core_stocks"]) * 2


def _evidence_level(score):
    if score >= 8:
        return "A"
    if score >= 4:
        return "B"
    return "C"


def _phase_qualification(phase):
    return _PHASE_TO_QUALIFICATION.get(phase, "只作观察证据")


def _report_effect(card):
    phase = card["lifecycle_phase"]
    qualification = card["participation_qualification"]
    topic_name = card["topic_name"]
    summary_tail = _PHASE_SUMMARIES.get(phase, "先观察，不急着下结论。")
    return {
        "candidate_policy": qualification,
        "summary": f"{topic_name}处于{phase}，{summary_tail}",
        "boundary": _TOPIC_LIFECYCLE_BOUNDARY,
        "report_slots": ["板块资金扩散", "淘汰赛复核", "知识复利提示"] if phase != "过期回看期" else ["知识复利提示"],
    }


def build_topic_lifecycle_knowledge_update(snapshot):
    cards = [card for card in (snapshot or {}).get("cards") or [] if isinstance(card, dict)]
    if not cards:
        return {}
    card = cards[0]
    evidence = card.get("evidence") if isinstance(card.get("evidence"), dict) else {}
    basis = []
    basis.extend(evidence.get("launch_catalyst") or [])
    basis.extend(evidence.get("fund_attack") or [])
    basis.extend(
        f"{item.get('name', '')}({item.get('code', '')})核心承接"
        for item in evidence.get("core_stocks") or []
        if isinstance(item, dict) and (_clean_text(item.get("name")) or _clean_text(item.get("code")))
    )
    basis.extend(evidence.get("spread_evidence") or [])
    basis.extend(evidence.get("counter_evidence") or [])
    basis = _dedupe([item for item in basis if _clean_text(item)])
    summary = _clean_text(card.get("report_effect", {}).get("summary"))
    if not summary:
        summary = f"{_clean_text(card.get('topic_name'), '题材')}处于{_clean_text(card.get('lifecycle_phase'), '观察期')}"
    next_effect = _clean_text(card.get("tomorrow_validation", {}).get("invalidation"))
    if not next_effect:
        next_effect = _clean_text(card.get("report_effect", {}).get("candidate_policy"))
    trade_date = _clean_text(snapshot.get("trade_date"))
    suggested_nodes = []
    if trade_date:
        suggested_nodes.append(f"data/topic-lifecycle/{trade_date}.json")
    suggested_nodes.extend(["data/topic-lifecycle/index.json", "wiki/交易思想/AI摩擦与知识复利.md"])
    return {
        "topic": "题材生命周期证据层",
        "source_path": "docs/trellis/specs/2026-06-14-topic-lifecycle-evidence-layer-design.md",
        "new_insight": summary,
        "fact_basis": "；".join(basis[:4]),
        "suggested_nodes": _dedupe(suggested_nodes),
        "next_effect": next_effect,
    }


def _validation_for_phase(card):
    phase = card["lifecycle_phase"]
    validation = dict(_PHASE_VALIDATION.get(phase, _PHASE_VALIDATION["观察期"]))
    validation["watch_points"] = _dedupe(validation.get("watch_points"))
    return validation


def _merge_card(card, candidate):
    card = card or {}
    evidence = card["evidence"]
    candidate = candidate or {}
    topic_texts = _candidate_texts(candidate)
    candidate_topic_name = _clean_text(candidate.get("topic_name") or candidate.get("sector") or candidate.get("mainline") or candidate.get("trade_narrative_sector"))
    if candidate_topic_name and candidate_topic_name != card.get("topic_name") and not _topic_match_score(topic_texts, _card_match_labels(card)):
        return card

    aliases = []
    for value in (
        candidate.get("aliases"),
        candidate.get("trade_narrative_sector"),
        candidate.get("raw_sector"),
        candidate.get("sector"),
        candidate.get("mainline"),
    ):
        aliases.extend(_split_terms(value))
    if candidate.get("name"):
        aliases.append(candidate.get("name"))
    if candidate.get("stock_name"):
        aliases.append(candidate.get("stock_name"))
    card["aliases"] = _dedupe((card.get("aliases") or []) + aliases)

    if candidate.get("sector") and candidate.get("sector") not in evidence["launch_catalyst"]:
        if candidate.get("source_type") == "decision_ledger_case":
            evidence["launch_catalyst"].append(_clean_text(candidate.get("sector")))

    if _clean_text(candidate.get("mainline")) and _clean_text(candidate.get("mainline")) not in evidence["launch_catalyst"]:
        evidence["launch_catalyst"].append(_clean_text(candidate.get("mainline")))

    if _clean_text(candidate.get("selection_result_reason")):
        evidence["acceptance_evidence"].append(_clean_text(candidate.get("selection_result_reason")))

    _collect_card_evidence_from_candidate(card, candidate)
    return card


def _finalize_card(card, previous_index, trade_date):
    card = card or {}
    topic_id = card["topic_id"]
    history_dates = _topic_history_dates(previous_index, topic_id)
    if not history_dates:
        history_dates = _topic_history_dates_by_labels(previous_index, [card.get("topic_name")] + list(card.get("aliases") or []))
    if trade_date not in history_dates:
        history_dates.append(trade_date)
    history_dates = sorted(_dedupe(history_dates))
    card["phase_age_trade_days"] = len(history_dates) or 1
    card["first_seen_trade_date"] = history_dates[0] if history_dates else trade_date
    card["latest_seen_trade_date"] = trade_date
    card["lifecycle_phase"] = _infer_phase(card, previous_index=previous_index)
    card["participation_qualification"] = _phase_qualification(card["lifecycle_phase"])
    score = _evidence_score(card)
    card["evidence_level"] = _evidence_level(score)
    card["tomorrow_validation"] = _validation_for_phase(card)
    card["report_effect"] = _report_effect(card)
    card["source_refs"] = _dedupe_source_refs(card["source_refs"], trade_date)
    if card["lifecycle_phase"] == "过期回看期" and not card["evidence"]["counter_evidence"]:
        card["participation_qualification"] = _PHASE_TO_QUALIFICATION["过期回看期"]
    return card


def _dedupe_source_refs(source_refs, trade_date):
    refs = []
    for ref in source_refs or []:
        if not isinstance(ref, dict):
            continue
        item = {"type": _clean_text(ref.get("type")), "path": _clean_text(ref.get("path"))}
        if item not in refs:
            refs.append(item)
    if trade_date and not any(ref.get("type") == "candidate_trace" for ref in refs):
        refs.append({"type": "candidate_trace", "path": f"data/candidate-traces/{trade_date}.json"})
    if trade_date and not any(ref.get("type") == "decision_ledger" for ref in refs):
        refs.append({"type": "decision_ledger", "path": "data/decision-ledger/index.json"})
    return refs


def _seed_from_candidate(candidate):
    candidate = candidate or {}
    topic_name = _clean_text(
        candidate.get("topic_name")
        or candidate.get("trade_narrative_sector")
        or candidate.get("mainline")
        or candidate.get("sector")
    )
    if not topic_name:
        return None
    aliases = _dedupe(_split_terms(candidate.get("sector")) + _split_terms(candidate.get("mainline")) + _split_terms(candidate.get("trade_narrative_sector")))
    card = _empty_card(topic_name, parent_theme=_clean_text(candidate.get("parent_theme") or candidate.get("mainline")), aliases=aliases)
    card["source_refs"].append({"type": candidate.get("source_type") or "candidate_trace", "path": ""})
    _collect_card_evidence_from_candidate(card, candidate)
    return card


def _choose_cards(data, previous_index):
    tag_snapshot = _extract_tag_snapshot(data)
    mainline_summary = _extract_mainline_summary(data)
    candidates = _extract_candidate_rows(data)
    cards = []

    for group in tag_snapshot.get("groups") or []:
        if not isinstance(group, dict):
            continue
        seed = _seed_from_tag_group(group, _extract_trade_date(data), mainline_summary)
        if seed:
            cards.append(seed)

    if not cards:
        for candidate in candidates:
            seed = _seed_from_candidate(candidate)
            if seed:
                cards.append(seed)

    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        candidate_texts = _candidate_names(candidate)
        matched_index = _match_card(candidate_texts, cards)
        if matched_index is None:
            seed = _seed_from_candidate(candidate)
            if seed:
                cards.append(seed)
                matched_index = len(cards) - 1
        if matched_index is not None:
            cards[matched_index] = _merge_card(cards[matched_index], candidate)

    current_trade_date = _extract_trade_date(data)
    finalized = []
    for card in cards:
        finalized.append(_finalize_card(card, previous_index, current_trade_date))

    finalized.sort(
        key=lambda card: (
            _PHASE_PRIORITY.get(card.get("lifecycle_phase"), 99),
            -_evidence_score(card),
            card.get("topic_name") or "",
        )
    )
    return finalized


def build_topic_lifecycle_snapshot(data, *, previous_index=None):
    data = data or {}
    trade_date = _extract_trade_date(data)
    previous_index = _extract_previous_topic_index(data, previous_index)
    cards = _choose_cards(data, previous_index)
    source_report = _extract_source_report(data, trade_date)
    return {
        "artifact_version": ARTIFACT_VERSION,
        "trade_date": trade_date,
        "generated_at": _current_iso_timestamp(),
        "source_report": source_report,
        "cards": cards,
    }


def _topic_history_from_previous_index(previous_index):
    history = {}
    for topic_id, records in ((previous_index or {}).get("by_topic_id") or {}).items():
        normalized = []
        for record in list(records or []):
            if not isinstance(record, dict):
                continue
            normalized.append(
                {
                    "trade_date": _clean_text(record.get("trade_date")),
                    "phase": _clean_text(record.get("phase")),
                    "participation_qualification": _clean_text(record.get("participation_qualification")),
                    "snapshot_path": _clean_text(record.get("snapshot_path")),
                }
            )
        normalized = [item for item in normalized if item["trade_date"]]
        normalized.sort(key=lambda item: item["trade_date"])
        if normalized:
            history[topic_id] = normalized
    return history


def _build_index(snapshot, previous_index=None):
    previous_index = previous_index or {}
    history = _topic_history_from_previous_index(previous_index)
    available_trade_dates = _dedupe(list(previous_index.get("available_trade_dates") or []))
    trade_date = _clean_text(snapshot.get("trade_date"))
    if trade_date:
        available_trade_dates.append(trade_date)
    available_trade_dates = sorted(_dedupe(available_trade_dates))

    snapshot_path = f"data/topic-lifecycle/{trade_date}.json" if trade_date else ""
    current_entries = []
    for card in snapshot.get("cards") or []:
        if not isinstance(card, dict):
            continue
        topic_id = _clean_text(card.get("topic_id"))
        if not topic_id:
            continue
        record = {
            "trade_date": trade_date,
            "topic_id": topic_id,
            "topic_name": _clean_text(card.get("topic_name")),
            "adopted_label": _clean_text(card.get("adopted_label")),
            "phase": _clean_text(card.get("lifecycle_phase")),
            "participation_qualification": _clean_text(card.get("participation_qualification")),
            "snapshot_path": snapshot_path,
        }
        history.setdefault(topic_id, [])
        history[topic_id] = [item for item in history[topic_id] if item.get("trade_date") != trade_date]
        history[topic_id].append(record)
        history[topic_id].sort(key=lambda item: item.get("trade_date") or "")
        current_entries.append(
            {
                "topic_id": topic_id,
                "topic_name": _clean_text(card.get("topic_name")),
                "latest_phase": _clean_text(card.get("lifecycle_phase")),
                "participation_qualification": _clean_text(card.get("participation_qualification")),
                "latest_trade_date": trade_date,
                "snapshot_path": snapshot_path,
            }
        )

    current_entries.sort(key=lambda item: (item.get("latest_trade_date") or "", item.get("topic_name") or ""), reverse=True)
    latest_trade_date = max(available_trade_dates) if available_trade_dates else trade_date
    by_topic_id = {topic_id: records for topic_id, records in history.items() if records}
    return {
        "artifact_version": ARTIFACT_VERSION,
        "latest_trade_date": latest_trade_date,
        "available_trade_dates": available_trade_dates,
        "active_topics": current_entries,
        "by_topic_id": by_topic_id,
    }


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_topic_lifecycle_artifact(snapshot, *, root_dir="."):
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    trade_date = _clean_text(snapshot.get("trade_date"))
    if not trade_date:
        raise ValueError("missing trade_date")
    root = Path(root_dir)
    lifecycle_dir = root / "data" / "topic-lifecycle"
    snapshot_path = lifecycle_dir / f"{trade_date}.json"
    index_path = lifecycle_dir / "index.json"
    previous_index = {}
    if index_path.exists():
        try:
            previous_index = json.loads(index_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            previous_index = {}
    index = _build_index(snapshot, previous_index=previous_index)
    _write_json(snapshot_path, snapshot)
    _write_json(index_path, index)
    return {
        "snapshot_path": str(snapshot_path),
        "index_path": str(index_path),
        "index": index,
        "card_count": len(snapshot.get("cards") or []),
    }


def _format_card_line(card):
    topic_name = _clean_text(card.get("topic_name"), "题材")
    phase = _clean_text(card.get("lifecycle_phase"), "观察期")
    summary = _clean_text(card.get("report_effect", {}).get("summary"))
    qualification = _clean_text(card.get("participation_qualification"), "只作观察证据")
    if summary:
        return f"- {topic_name}：{phase}；{summary}；证据用途：{qualification}。"
    return f"- {topic_name}：{phase}；证据用途：{qualification}。"


def format_topic_lifecycle_for_report(snapshot):
    cards = [card for card in (snapshot or {}).get("cards") or [] if isinstance(card, dict)]
    if not cards:
        return []
    ordered = sorted(
        cards,
        key=lambda card: (
            _PHASE_PRIORITY.get(_clean_text(card.get("lifecycle_phase")), 99),
            -_evidence_score(card),
            _clean_text(card.get("topic_name")),
        ),
    )
    lines = []
    for card in ordered[:3]:
        line = _format_card_line(card)
        if line:
            lines.append(line)
    if any(_clean_text(card.get("participation_qualification")) in {"不进入明日复核", "只作历史回看"} for card in ordered[:3]):
        lines.append("- 退潮或过期样本只作复盘对照，不进入明日计划。")
    if lines and not any(_TOPIC_LIFECYCLE_BOUNDARY in line for line in lines):
        lines.append(f"- {_TOPIC_LIFECYCLE_BOUNDARY}")
    return lines[:5]


__all__ = [
    "ARTIFACT_VERSION",
    "build_topic_lifecycle_snapshot",
    "build_topic_lifecycle_knowledge_update",
    "format_topic_lifecycle_for_report",
    "write_topic_lifecycle_artifact",
]
