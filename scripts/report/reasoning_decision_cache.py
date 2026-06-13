from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping

from storage.database_service import DatabaseService


def _safe(value: str) -> str:
    return "".join(char if char.isalnum() or char in ("-", "_", ".") else "-" for char in str(value or ""))


def reasoning_cache_key(*, target_date: str, input_hash: str, schema_version: str, prompt_version: str, model_source: str) -> str:
    return "_".join(
        [
            _safe(target_date),
            _safe(input_hash),
            _safe(schema_version),
            _safe(prompt_version),
            _safe(model_source),
        ]
    )


def _key_from_decision(decision: Mapping[str, Any]) -> str:
    return reasoning_cache_key(
        target_date=str(decision.get("target_date") or ""),
        input_hash=str(decision.get("input_hash") or ""),
        schema_version=str(decision.get("schema_version") or ""),
        prompt_version=str(decision.get("prompt_version") or ""),
        model_source=str(decision.get("model_source") or ""),
    )


def _postgres_database_url() -> str:
    return (
        os.environ.get("A_DAILY_REPORT_DATABASE_URL")
        or os.environ.get("DATABASE_URL")
        or ""
    ).strip()


def _postgres_only_runtime() -> bool:
    return os.environ.get("A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME", "").strip() == "1"


def _runtime_cache_service():
    database_url = _postgres_database_url()
    postgres_required = _postgres_only_runtime() or database_url.startswith(("postgres://", "postgresql://"))
    if not postgres_required:
        return None
    service = DatabaseService.from_environment()
    if not service.is_postgres_backed():
        if _postgres_only_runtime():
            raise RuntimeError("PostgreSQL-only reasoning cache requires PostgreSQL storage")
        return None
    return service


def _target_date_from_key(key: str) -> str:
    return str(key or "").split("_", 1)[0]


def save_reasoning_decision_cache(cache_dir: Path | str, decision: Mapping[str, Any]) -> Path:
    service = _runtime_cache_service()
    record = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "target_date": decision.get("target_date"),
        "input_hash": decision.get("input_hash"),
        "schema_version": decision.get("schema_version"),
        "prompt_version": decision.get("prompt_version"),
        "model_source": decision.get("model_source"),
        "decision": dict(decision),
    }
    cache_path = Path(cache_dir)
    key = _key_from_decision(decision)
    path = cache_path / f"{key}.json"
    if service is not None:
        service.set_runtime_cache_entry(
            "reasoning_decision",
            key,
            str(decision.get("target_date") or ""),
            record,
            source=str(decision.get("model_source") or ""),
            ttl_seconds=30 * 86400,
        )
        return path
    cache_path.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _validate_raw_cache_key(key: str) -> str:
    if not key:
        raise ValueError("cache key must not be empty")
    if key.endswith(".json"):
        raise ValueError("cache key must not include the .json suffix")
    if key != _safe(key):
        raise ValueError("cache key contains unsafe characters")
    if key in (".", ".."):
        raise ValueError("cache key must not contain path traversal")
    return key


def load_reasoning_decision_cache(cache_dir: Path | str, decision_or_key: Mapping[str, Any] | str) -> Dict[str, Any]:
    service = _runtime_cache_service()
    key = _key_from_decision(decision_or_key) if isinstance(decision_or_key, Mapping) else _validate_raw_cache_key(str(decision_or_key))
    if service is not None:
        target_date = str(decision_or_key.get("target_date") or "") if isinstance(decision_or_key, Mapping) else _target_date_from_key(key)
        entry = service.get_runtime_cache_entry("reasoning_decision", key, target_date)
        if not isinstance(entry, dict):
            raise FileNotFoundError(f"PostgreSQL runtime cache entry not found: {key}")
        payload = entry.get("payload")
        return dict(payload) if isinstance(payload, dict) else {}
    cache_path = Path(cache_dir)
    path = cache_path / f"{key}.json"
    return json.loads(path.read_text(encoding="utf-8"))
