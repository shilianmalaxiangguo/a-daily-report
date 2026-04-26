from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Mapping


INPUT_SCHEMA_VERSION = "reasoning_input.v1"
DECISION_SCHEMA_VERSION = "reasoning_decision.v1"


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def compute_input_hash(packet: Mapping[str, Any]) -> str:
    hash_input = {key: value for key, value in packet.items() if key != "input_hash"}
    return hashlib.sha256(_stable_json(hash_input).encode("utf-8")).hexdigest()


def _as_dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _as_list(value: Any) -> List[Any]:
    return list(value) if isinstance(value, list) else []


def _normalize_candidate(candidate: Mapping[str, Any]) -> Dict[str, Any]:
    code = str(candidate.get("code") or candidate.get("id") or "").strip()
    name = str(candidate.get("name") or "").strip()
    return {
        "id": code or name,
        "code": code,
        "name": name,
        "sector": candidate.get("sector") or candidate.get("sector_name") or "",
        "qualification": candidate.get("qualification")
        or candidate.get("tomorrow_qualification")
        or candidate.get("action_rule")
        or "",
        "evidence": _as_dict(candidate.get("evidence")),
    }


def _candidate_pool(snapshot: Mapping[str, Any]) -> List[Dict[str, Any]]:
    raw_candidates = _as_list(snapshot.get("candidate_pool"))
    if not raw_candidates:
        raw_candidates = _as_list(snapshot.get("core_candidates"))
    return [_normalize_candidate(item) for item in raw_candidates if isinstance(item, Mapping)]


def build_reasoning_input_packet(
    target_date: str,
    market_research_snapshot: Mapping[str, Any] | None,
    final_gate: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    snapshot = _as_dict(market_research_snapshot)
    mainline_summary = _as_dict(snapshot.get("mainline_turnover_summary"))
    packet = {
        "schema_version": INPUT_SCHEMA_VERSION,
        "target_date": str(target_date or ""),
        "market_base": {
            "market_fit_calibration": _as_dict(snapshot.get("market_fit_calibration")),
            "state_machine": _as_dict(snapshot.get("state_machine")),
        },
        "mainline_snapshot": {
            "current_mainline": mainline_summary.get("current_mainline") or "",
            "double_mainline_summary": _as_dict(mainline_summary.get("double_mainline_summary")),
            "current_sector_turnover_snapshot": _as_dict(
                snapshot.get("current_sector_turnover_snapshot")
            ),
        },
        "turnover_share_history": _as_list(snapshot.get("recent_sector_turnover_history")),
        "candidate_pool": _candidate_pool(snapshot),
        "execution_contract": _as_dict(final_gate),
        "risk_context": _as_dict(snapshot.get("risk_context")),
        "source_status": _as_dict(snapshot.get("source_status")),
    }
    packet["input_hash"] = compute_input_hash(packet)
    return packet


ALLOWED_ACTIONS = {"do_nothing", "observe", "conditional_entry"}
ALLOWED_MAINLINE_STATES = {"strengthening", "diverging", "fading", "unclear"}
ALLOWED_CONFIDENCE = {"high", "medium", "low"}
ALLOWED_REASONING_EFFORT = {"xhigh"}
ALLOWED_MODEL_SOURCES = {"manual", "deterministic_fallback", "api"}
REQUIRED_DECISION_FIELDS = (
    "schema_version",
    "target_date",
    "input_hash",
    "prompt_version",
    "reasoning_effort",
    "model_source",
    "action",
    "mainline_state",
    "unique_target",
    "conclusion",
    "evidence",
    "trigger_conditions",
    "failure_conditions",
    "excluded_candidates",
    "confidence",
)


def _finding(code: str, message: str) -> Dict[str, str]:
    return {"code": code, "message": message}


def _flatten_paths(value: Any, prefix: str = "") -> set[str]:
    paths: set[str] = set()
    if isinstance(value, Mapping):
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            paths.add(path)
            paths.update(_flatten_paths(item, path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            path = f"{prefix}.{index}" if prefix else str(index)
            paths.add(path)
            paths.update(_flatten_paths(item, path))
    return paths


def _candidate_ids(packet: Mapping[str, Any]) -> set[str]:
    ids = set()
    for item in _as_list(packet.get("candidate_pool")):
        if not isinstance(item, Mapping):
            continue
        for key in ("id", "code"):
            value = str(item.get(key) or "").strip()
            if value:
                ids.add(value)
    return ids


def validate_reasoning_decision(packet: Mapping[str, Any], decision: Mapping[str, Any]) -> Dict[str, Any]:
    packet = _as_dict(packet)
    decision = _as_dict(decision)
    findings: List[Dict[str, str]] = []

    for field in REQUIRED_DECISION_FIELDS:
        if field not in decision:
            findings.append(_finding("required_field_missing", f"reasoning decision is missing required field: {field}"))

    if decision.get("schema_version") != DECISION_SCHEMA_VERSION:
        findings.append(_finding("unsupported_schema_version", "reasoning decision schema_version must be reasoning_decision.v1"))
    if decision.get("target_date") != packet.get("target_date"):
        findings.append(_finding("target_date_mismatch", "reasoning decision target_date must match input packet"))
    if decision.get("input_hash") != packet.get("input_hash"):
        findings.append(_finding("input_hash_mismatch", "reasoning decision input_hash must match input packet"))
    if decision.get("action") not in ALLOWED_ACTIONS:
        findings.append(_finding("invalid_action", "reasoning decision action is not supported"))
    if decision.get("mainline_state") not in ALLOWED_MAINLINE_STATES:
        findings.append(_finding("invalid_mainline_state", "reasoning decision mainline_state is not supported"))
    if decision.get("confidence") not in ALLOWED_CONFIDENCE:
        findings.append(_finding("invalid_confidence", "reasoning decision confidence is not supported"))
    if decision.get("reasoning_effort") not in ALLOWED_REASONING_EFFORT:
        findings.append(_finding("invalid_reasoning_effort", "reasoning decision effort must be xhigh"))
    if decision.get("model_source") not in ALLOWED_MODEL_SOURCES:
        findings.append(_finding("invalid_model_source", "reasoning decision model_source is not supported"))

    candidate_ids = _candidate_ids(packet)
    unique_target = decision.get("unique_target")
    unique_target_id = str(unique_target).strip() if unique_target is not None else ""
    if decision.get("action") == "do_nothing" and unique_target_id:
        findings.append(_finding("do_nothing_has_unique_target", "do_nothing decisions must not name a unique target"))
    if unique_target_id and unique_target_id not in candidate_ids:
        findings.append(_finding("unique_target_not_in_candidate_pool", "unique target must come from the candidate pool"))

    if decision.get("action") == "conditional_entry" and (not decision.get("trigger_conditions") or not decision.get("failure_conditions")):
        findings.append(_finding("conditional_entry_missing_conditions", "conditional entry must include trigger and failure conditions"))
    if decision.get("confidence") == "low" and decision.get("action") == "conditional_entry":
        findings.append(_finding("low_confidence_aggressive_action", "low confidence cannot create conditional entry"))

    known_paths = _flatten_paths(packet)
    for item in _as_list(decision.get("evidence")):
        if not isinstance(item, Mapping):
            findings.append(_finding("evidence_item_invalid", "evidence items must be objects"))
            continue
        field = str(item.get("field") or "").strip()
        if field not in known_paths:
            findings.append(_finding("evidence_field_unknown", f"evidence field is not present in input packet: {field}"))

    for item in _as_list(decision.get("excluded_candidates")):
        if not isinstance(item, Mapping):
            findings.append(_finding("excluded_candidate_invalid", "excluded candidates must be objects"))
            continue
        candidate_id = str(item.get("id") or item.get("code") or "").strip()
        if candidate_id and candidate_id not in candidate_ids:
            findings.append(_finding("excluded_candidate_unknown", f"excluded candidate is not present in input packet: {candidate_id}"))

    return {"passed": not findings, "findings": findings}


def derive_unique_action_target_from_reasoning_decision(snapshot: Mapping[str, Any]) -> Dict[str, str]:
    snapshot = _as_dict(snapshot)
    decision = _as_dict(snapshot.get("reasoning_decision"))
    if decision.get("action") != "conditional_entry" or decision.get("confidence") not in {"high", "medium"}:
        return {}
    target_id = str(decision.get("unique_target") or "").strip()
    if not target_id:
        return {}
    for candidate in _candidate_pool(snapshot):
        if target_id in {str(candidate.get("id") or ""), str(candidate.get("code") or "")}:
            return {
                "name": str(candidate.get("name") or "唯一对象"),
                "code": str(candidate.get("code") or candidate.get("id") or target_id),
                "condition": "主线确认 + 承接 + 60分钟确认",
            }
    return {}
