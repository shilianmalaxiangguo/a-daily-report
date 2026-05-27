from __future__ import annotations

import json
from pathlib import Path

from selection.candidate_trace_contracts import build_candidate_trace_artifact_payload


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_candidate_trace_artifact(
    *,
    trade_date,
    traces,
    eliminated_summary=None,
    root_dir=".",
    generated_at=None,
    source_report=None,
):
    root = Path(root_dir)
    payload = build_candidate_trace_artifact_payload(
        trade_date=trade_date,
        traces=traces,
        eliminated_summary=eliminated_summary or [],
        generated_at=generated_at,
        source_report=source_report or {},
    )
    artifact_path = root / "data" / "candidate-traces" / f"{trade_date}.json"
    _write_json(artifact_path, payload)
    return {
        "artifact_path": str(artifact_path),
        "trace_count": len(payload.get("traces") or []),
        "eliminated_group_count": len(payload.get("eliminated_summary") or []),
        "payload": payload,
    }


__all__ = ["write_candidate_trace_artifact"]
