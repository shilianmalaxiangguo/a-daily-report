from __future__ import annotations

import json
import os
from pathlib import Path

from selection.candidate_trace_contracts import build_candidate_trace_artifact_payload

try:
    from storage.database_service import DatabaseService
except Exception:  # pragma: no cover - optional runtime path
    DatabaseService = None


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _postgres_database_configured():
    database_url = (
        os.environ.get("A_DAILY_REPORT_DATABASE_URL")
        or os.environ.get("DATABASE_URL")
        or ""
    ).strip()
    return database_url.startswith(("postgres://", "postgresql://"))


def _configured_postgres_service():
    service_cls = globals().get("DatabaseService")
    if not _postgres_database_configured():
        return None
    if service_cls is None:
        raise RuntimeError("PostgreSQL candidate trace storage is configured but DatabaseService is unavailable")
    service = service_cls.from_environment()
    checker = getattr(service, "is_postgres_backed", None)
    if not callable(checker) or not checker():
        raise RuntimeError("PostgreSQL candidate trace storage is configured but DatabaseService did not select PostgreSQL")
    return service


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
    service = _configured_postgres_service()
    if service is not None:
        writer = getattr(service, "replace_candidate_trace_artifact", None)
        if callable(writer):
            result = writer(payload)
            if isinstance(result, dict):
                return {
                    **result,
                    "payload": payload,
                }
        raise RuntimeError("PostgreSQL candidate trace writer is unavailable")
    artifact_path = root / "data" / "candidate-traces" / f"{trade_date}.json"
    _write_json(artifact_path, payload)
    return {
        "artifact_path": str(artifact_path),
        "trace_count": len(payload.get("traces") or []),
        "eliminated_group_count": len(payload.get("eliminated_summary") or []),
        "payload": payload,
    }


__all__ = ["write_candidate_trace_artifact"]
