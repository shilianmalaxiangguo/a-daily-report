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
