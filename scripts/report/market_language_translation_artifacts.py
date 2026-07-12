from __future__ import annotations

import copy
import json
import os
import tempfile
from pathlib import Path

from domains.market_state.market_language_translation import (
    MARKET_LANGUAGE_SCHEMA_VERSION,
    attach_market_language_posthoc_validation,
    build_market_language_source_projection,
    build_market_language_translation,
    canonical_market_language_hash,
    normalize_market_language_translation,
)

try:
    from storage.database_service import DatabaseService
except Exception:  # pragma: no cover - optional runtime dependency
    DatabaseService = None


def fresh_market_language_path(root_dir, target_date):
    return Path(root_dir) / "data" / "market-language" / "fresh" / f"{target_date}.json"


def replay_market_language_path(root_dir, target_date):
    return (
        Path(root_dir)
        / "snapshots"
        / "replay"
        / "market-language"
        / f"{target_date}.json"
    )


def _atomic_write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_path = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    except Exception:
        try:
            os.unlink(temporary_path)
        except OSError:
            pass
        raise


def _configured_service(service):
    if service is False:
        return None
    if service is not None:
        return service
    service_cls = globals().get("DatabaseService")
    if service_cls is None:
        return None
    resolved = service_cls.from_environment()
    checker = getattr(resolved, "is_postgres_backed", None)
    return resolved if callable(checker) and checker() else None


def _loaded_artifact(payload):
    if not isinstance(payload, dict):
        return None
    if payload.get("schema_version") == MARKET_LANGUAGE_SCHEMA_VERSION:
        return payload
    for key in ("artifact", "market_language_translation", "data"):
        value = payload.get(key)
        if isinstance(value, dict) and value.get("schema_version") == MARKET_LANGUAGE_SCHEMA_VERSION:
            return value
    return None


def load_fresh_market_language_translation(
    target_date,
    *,
    root_dir=".",
    service=None,
):
    resolved_service = _configured_service(service)
    if resolved_service is not None:
        reader = getattr(resolved_service, "load_market_language_translation_artifact", None)
        if callable(reader):
            loaded = _loaded_artifact(reader(target_date))
            if loaded is not None:
                normalized = normalize_market_language_translation(loaded)
                return normalized if normalized.get("target_date") == target_date else None
    if os.environ.get("A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME", "").strip() == "1":
        return None
    path = fresh_market_language_path(root_dir, target_date)
    if not path.is_file():
        return None
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    loaded = _loaded_artifact(loaded)
    if loaded is None:
        return None
    normalized = normalize_market_language_translation(loaded)
    return normalized if normalized.get("target_date") == target_date else None


def write_fresh_market_language_translation(
    artifact,
    *,
    root_dir=".",
    service=None,
):
    normalized = normalize_market_language_translation(artifact)
    if normalized.get("analysis_mode") != "fresh":
        raise ValueError("fresh storage accepts only fresh market language artifacts")
    resolved_service = _configured_service(service)
    if resolved_service is not None:
        writer = getattr(resolved_service, "replace_market_language_translation_artifact", None)
        if not callable(writer):
            raise RuntimeError("PostgreSQL market language artifact writer is unavailable")
        result = writer(copy.deepcopy(normalized))
        result = dict(result or {})
        result.update(
            {
                "storage": "postgresql",
                "canonical_hash": canonical_market_language_hash(normalized),
                "payload": normalized,
            }
        )
        return result
    path = fresh_market_language_path(root_dir, normalized["target_date"])
    _atomic_write_json(path, normalized)
    return {
        "storage": "local_json",
        "artifact_path": str(path),
        "canonical_hash": canonical_market_language_hash(normalized),
        "payload": normalized,
    }


def write_replay_market_language_translation(artifact, *, root_dir="."):
    normalized = normalize_market_language_translation(artifact)
    if normalized.get("analysis_mode") != "replay":
        raise ValueError("replay storage accepts only replay market language artifacts")
    path = replay_market_language_path(root_dir, normalized["target_date"])
    _atomic_write_json(path, normalized)
    return {
        "storage": "replay_json",
        "artifact_path": str(path),
        "canonical_hash": canonical_market_language_hash(normalized),
        "payload": normalized,
    }


def _extract_embedded_artifact(data):
    if not isinstance(data, dict):
        return None
    loaded = None
    for key in ("market_language_translation", "market_language_translation_artifact"):
        value = data.pop(key, None)
        candidate = _loaded_artifact(value)
        if loaded is None and candidate is not None:
            loaded = candidate
    return loaded


def prepare_market_language_translation(
    data,
    *,
    target_date,
    analysis_mode="fresh",
    root_dir=".",
    service=None,
):
    analysis_mode = "replay" if analysis_mode == "replay" else "fresh"
    projection = build_market_language_source_projection(
        data,
        target_date=target_date,
        analysis_mode=analysis_mode,
    )
    if analysis_mode == "fresh":
        return build_market_language_translation(
            projection,
            target_date=target_date,
            analysis_mode="fresh",
            artifact_origin="computed",
        )

    loaded = _extract_embedded_artifact(data)
    if loaded is None:
        loaded = load_fresh_market_language_translation(
            target_date,
            root_dir=root_dir,
            service=service,
        )
    if loaded is not None and loaded.get("target_date") == target_date:
        replay_artifact = copy.deepcopy(loaded)
        replay_artifact["analysis_mode"] = "replay"
        replay_artifact["artifact_origin"] = "loaded"
        replay_artifact["posthoc_validation"] = None
        replay_artifact = normalize_market_language_translation(replay_artifact)
        return attach_market_language_posthoc_validation(replay_artifact, projection)
    return build_market_language_translation(
        projection,
        target_date=target_date,
        analysis_mode="replay",
        artifact_origin="reconstructed",
        include_posthoc=True,
    )


__all__ = [
    "fresh_market_language_path",
    "load_fresh_market_language_translation",
    "prepare_market_language_translation",
    "replay_market_language_path",
    "write_fresh_market_language_translation",
    "write_replay_market_language_translation",
]
