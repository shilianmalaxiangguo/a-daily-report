"""Deterministic manifest compilation for the local LLM Wiki."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence


MANIFEST_SCHEMA_VERSION = "knowledge_manifest.v1"
DEFAULT_DECISION_SCOPE = "explanation_only"
VALID_DECISION_SCOPES = {DEFAULT_DECISION_SCOPE}
VALID_KINDS = {"knowledge_rule", "policy", "process"}
VALID_LIFECYCLES = {"draft", "reviewed", "verified", "disputed", "archived"}
VALID_MANIFEST_AVAILABILITIES = {"ready", "partial", "missing_sources", "invalid"}
VALID_SOURCE_AVAILABILITIES = {"available", "missing", "invalid"}
VALID_SOURCE_METADATA_STATUSES = {"complete", "partial"}
SOURCE_METADATA_FIELDS = ("source_date", "capture_date", "anchor")
SOURCE_REF_INDEX_FIELDS = (
    "path",
    "local_path",
    "content_hash",
    "availability",
    "source_date",
    "capture_date",
    "anchor",
    "url",
    "author_or_publisher",
    "metadata_status",
    "missing_metadata",
)
REQUIRED_ENTRY_FIELDS = (
    "knowledge_id",
    "title",
    "prior",
    "applies_to",
    "confidence",
    "lifecycle",
    "report_slots",
    "decision_effect",
    "decision_scope",
)
EXPLICIT_FACT_PATHS = frozenset(
    {
        "market.index_trend",
        "market.breadth",
        "market.turnover_distribution",
        "market.market_form",
        "market.sector_grid",
        "market.selection_order",
        "market.corner_sample",
        "market.rebound_roles",
        "market.rebound_state",
        "market.rebound_action",
        "account.cash_available",
        "account.status",
        "candidate.one_lot_amount",
        "candidate.identity",
        "candidate.quality",
        "candidate.rebound_roles",
        "candidate.rebound_state",
        "candidate.rebound_action",
        "position.state",
        "position.action",
        "position.capital_priority_reason",
        "position.capital_priority",
        "position.rebound_roles",
        "position.rebound_state",
        "position.rebound_action",
        "decision.position_plan",
        "decision.execution_object_state",
        "decision.action_layer",
        "decision.participation_rhythm",
        "decision.b1_role",
        "decision.b2_role",
        "decision.qualification",
        "decision.response_mode",
        "decision.behavior_traps",
        "decision.response_script",
        "capital_priority",
    }
)


def _json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, set):
        return sorted(
            (_json_ready(item) for item in value),
            key=lambda item: json.dumps(
                item,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ),
        )
    if isinstance(value, Path):
        return value.as_posix()
    return value


def stable_json(value: Any) -> str:
    return json.dumps(
        _json_ready(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def stable_json_hash(value: Mapping[str, Any], *, excluded_keys: Iterable[str] = ()) -> str:
    excluded = {str(key) for key in excluded_keys}
    payload = {key: item for key, item in value.items() if key not in excluded}
    return hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()


def is_sha256(value: Any) -> bool:
    text = str(value or "").strip().lower()
    return len(text) == 64 and all(character in "0123456789abcdef" for character in text)


def _is_iso_calendar_date(value: str) -> bool:
    if not value:
        return False
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def _as_string_list(value: Any) -> list[str]:
    if isinstance(value, set):
        return sorted({str(item).strip() for item in value if str(item).strip()})
    if isinstance(value, (list, tuple)):
        items = value
    elif value in (None, ""):
        items = []
    else:
        items = [value]
    return list(dict.fromkeys(str(item).strip() for item in items if str(item).strip()))


def _source_path_error(source_path: str) -> str:
    if not source_path:
        return "source_path_missing"
    candidate = PurePosixPath(source_path)
    if candidate.is_absolute() or ".." in candidate.parts or not candidate.parts or candidate.parts[0] != "wiki":
        return "source_path_invalid"
    return ""


def _source_ref(root: Path, source_path: str) -> tuple[dict[str, Any], str]:
    path_error = _source_path_error(source_path)
    base = {
        "path": source_path,
        "local_path": source_path,
        "content_hash": "",
        "availability": "invalid" if path_error else "missing",
        "metadata_status": "partial",
        "missing_metadata": list(SOURCE_METADATA_FIELDS),
    }
    if path_error:
        return base, path_error

    wiki_root = (root / "wiki").resolve()
    absolute_path = (root / source_path).resolve()
    try:
        absolute_path.relative_to(wiki_root)
    except ValueError:
        base["availability"] = "invalid"
        return base, "source_path_invalid"

    if not absolute_path.is_file():
        return base, "source_missing"

    base["content_hash"] = hashlib.sha256(absolute_path.read_bytes()).hexdigest()
    base["availability"] = "available"
    return base, ""


def _metadata_value(entry: Mapping[str, Any], source_data: Mapping[str, Any], key: str) -> str:
    return str(source_data.get(key) or entry.get(key) or "").strip()


def _has_structured_confirmation(entry: Mapping[str, Any]) -> bool:
    conditions = entry.get("fact_conditions")
    if not isinstance(conditions, Mapping):
        return False
    required = conditions.get("must_any")
    return bool(
        isinstance(required, list)
        and required
        and all(isinstance(condition, Mapping) for condition in required)
    )


def _fact_condition_path_errors(
    entry: Mapping[str, Any],
    *,
    knowledge_id: str,
) -> list[str]:
    conditions = entry.get("fact_conditions")
    if not isinstance(conditions, Mapping):
        return []
    errors: list[str] = []
    for group in ("must_any", "prefer_any"):
        grouped_conditions = conditions.get(group)
        if not isinstance(grouped_conditions, list):
            continue
        for condition in grouped_conditions:
            if not isinstance(condition, Mapping):
                continue
            path = str(condition.get("path") or "").strip()
            if path not in EXPLICIT_FACT_PATHS:
                errors.append(
                    f"fact_condition_path_invalid:{knowledge_id or '<missing>'}:{path or '<missing>'}"
                )
    return errors


def _normalize_entry(
    raw_entry: Mapping[str, Any],
    *,
    root: Path,
    duplicate_ids: set[str],
) -> tuple[dict[str, Any], list[str], list[str]]:
    knowledge_id = str(raw_entry.get("knowledge_id") or raw_entry.get("id") or "").strip()
    source_data = raw_entry.get("source_ref") if isinstance(raw_entry.get("source_ref"), Mapping) else {}
    source_path = str(source_data.get("path") or raw_entry.get("source_path") or "").strip()
    source_ref, source_error = _source_ref(root, source_path)

    for key in ("source_date", "capture_date", "anchor", "url", "author_or_publisher"):
        value = _metadata_value(raw_entry, source_data, key)
        if value:
            source_ref[key] = value
    missing_metadata = [key for key in SOURCE_METADATA_FIELDS if not source_ref.get(key)]
    source_ref["metadata_status"] = "complete" if not missing_metadata else "partial"
    source_ref["missing_metadata"] = missing_metadata

    confidence = str(raw_entry.get("confidence") or "").strip()
    lifecycle = str(raw_entry.get("lifecycle") or confidence or "draft").strip()
    decision_scope = (
        str(raw_entry.get("decision_scope") or "").strip()
        if "decision_scope" in raw_entry
        else DEFAULT_DECISION_SCOPE
    )
    report_slots = _as_string_list(raw_entry.get("report_slots") or raw_entry.get("report_slot"))
    decision_effect = str(raw_entry.get("decision_effect") or raw_entry.get("impact") or "").strip()
    normalized = {
        "knowledge_id": knowledge_id,
        "kind": str(raw_entry.get("kind") or "knowledge_rule").strip(),
        "title": str(raw_entry.get("title") or "").strip(),
        "prior": str(raw_entry.get("prior") or "").strip(),
        "topics": _as_string_list(raw_entry.get("topics")),
        "applies_to": _as_string_list(raw_entry.get("applies_to") or raw_entry.get("scenarios")),
        "trigger_terms": _as_string_list(raw_entry.get("trigger_terms")),
        "weak_trigger_terms": _as_string_list(raw_entry.get("weak_trigger_terms")),
        "fact_conditions": _json_ready(raw_entry.get("fact_conditions") or {}),
        "confidence": confidence,
        "lifecycle": lifecycle,
        "relationships": _json_ready(raw_entry.get("relationships") or []),
        "report_slots": report_slots,
        "decision_effect": decision_effect,
        "decision_scope": decision_scope,
        "available_from": str(raw_entry.get("available_from") or "").strip(),
        "source_ref": source_ref,
    }

    errors: list[str] = []
    warnings: list[str] = []
    if not knowledge_id:
        errors.append("knowledge_id_missing")
    elif knowledge_id in duplicate_ids:
        errors.append(f"knowledge_id_duplicate:{knowledge_id}")
    if normalized["kind"] not in VALID_KINDS:
        errors.append(f"kind_invalid:{knowledge_id or '<missing>'}:{normalized['kind']}")
    if lifecycle not in VALID_LIFECYCLES:
        errors.append(f"lifecycle_invalid:{knowledge_id or '<missing>'}:{lifecycle}")
    if not decision_scope:
        errors.append(f"decision_scope_missing:{knowledge_id or '<missing>'}")
    elif decision_scope not in VALID_DECISION_SCOPES:
        errors.append(f"decision_scope_invalid:{knowledge_id or '<missing>'}:{decision_scope}")
    if normalized["available_from"] and not _is_iso_calendar_date(
        normalized["available_from"]
    ):
        errors.append(
            "available_from_invalid:"
            f"{knowledge_id or '<missing>'}:{normalized['available_from']}"
        )
    if normalized["kind"] == "knowledge_rule" and not _has_structured_confirmation(normalized):
        errors.append(f"fact_conditions_missing:{knowledge_id or '<missing>'}")
    elif normalized["kind"] == "knowledge_rule":
        errors.extend(
            _fact_condition_path_errors(
                normalized,
                knowledge_id=knowledge_id,
            )
        )
    for field in REQUIRED_ENTRY_FIELDS:
        if normalized.get(field) in (None, "", []):
            errors.append(f"entry_field_missing:{knowledge_id or '<missing>'}:{field}")
    if source_error == "source_missing":
        warnings.append(f"source_missing:{source_path}")
    elif source_error:
        errors.append(f"{source_error}:{knowledge_id or '<missing>'}:{source_path}")
    if missing_metadata:
        warnings.append(
            f"source_metadata_incomplete:{knowledge_id or '<missing>'}:{','.join(missing_metadata)}"
        )

    normalized["available"] = not errors and source_ref["availability"] == "available" and lifecycle not in {
        "disputed",
        "archived",
    }
    return normalized, errors, warnings


def build_knowledge_manifest(
    entries: Sequence[Mapping[str, Any]],
    *,
    root: Path,
    wiki_version: str,
    language: str = "zh-CN",
    expected_source_paths: Sequence[str] | None = None,
) -> dict[str, Any]:
    root = Path(root)
    raw_entries = [dict(entry) for entry in entries]
    ids = [str(entry.get("knowledge_id") or entry.get("id") or "").strip() for entry in raw_entries]
    duplicate_ids = {knowledge_id for knowledge_id, count in Counter(ids).items() if knowledge_id and count > 1}

    normalized_entries: list[dict[str, Any]] = []
    errors: list[str] = []
    warnings: list[str] = []
    for entry in raw_entries:
        normalized, entry_errors, entry_warnings = _normalize_entry(
            entry,
            root=root,
            duplicate_ids=duplicate_ids,
        )
        normalized_entries.append(normalized)
        errors.extend(entry_errors)
        warnings.extend(entry_warnings)

    entry_source_paths = [entry["source_ref"]["path"] for entry in normalized_entries if entry["source_ref"]["path"]]
    expected_paths = list(dict.fromkeys([*(expected_source_paths or []), *entry_source_paths]))
    source_index: list[dict[str, Any]] = []
    available_paths: list[str] = []
    missing_paths: list[str] = []
    invalid_paths: list[str] = []
    entry_refs = {entry["source_ref"]["path"]: entry["source_ref"] for entry in normalized_entries}
    for source_path in expected_paths:
        source_ref = dict(entry_refs.get(source_path) or _source_ref(root, source_path)[0])
        source_index.append(source_ref)
        if source_path not in entry_refs and source_ref.get("missing_metadata"):
            warnings.append(
                "source_metadata_incomplete:"
                f"{source_path}:{','.join(source_ref['missing_metadata'])}"
            )
        if source_ref["availability"] == "available":
            available_paths.append(source_path)
        elif source_ref["availability"] == "missing":
            missing_paths.append(source_path)
            warning = f"source_missing:{source_path}"
            if warning not in warnings:
                warnings.append(warning)
        else:
            invalid_paths.append(source_path)

    errors = list(dict.fromkeys(errors))
    warnings = list(dict.fromkeys(warnings))
    if errors or invalid_paths:
        availability = "invalid"
    elif missing_paths:
        availability = "missing_sources"
    elif warnings:
        availability = "partial"
    else:
        availability = "ready"

    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "wiki_version": str(wiki_version or "").strip(),
        "language": str(language or "zh-CN").strip(),
        "entries": normalized_entries,
        "sources": source_index,
        "expected_source_paths": expected_paths,
        "available_source_paths": available_paths,
        "missing_source_paths": missing_paths,
        "invalid_source_paths": invalid_paths,
        "availability": availability,
        "warnings": warnings,
        "errors": errors,
    }
    manifest["manifest_hash"] = stable_json_hash(manifest)
    return manifest


def validate_knowledge_manifest(manifest: Any) -> list[str]:
    if not isinstance(manifest, Mapping):
        return ["manifest_type_invalid"]

    list_fields = (
        "entries",
        "sources",
        "expected_source_paths",
        "available_source_paths",
        "missing_source_paths",
        "invalid_source_paths",
        "warnings",
        "errors",
    )
    list_values: dict[str, list[Any]] = {}
    for field in list_fields:
        value = manifest.get(field)
        list_values[field] = value if isinstance(value, list) else []
    declared_errors = [str(error) for error in list_values["errors"]]
    errors = list(declared_errors)
    required_fields = (
        "schema_version",
        "wiki_version",
        "language",
        "entries",
        "sources",
        "expected_source_paths",
        "available_source_paths",
        "missing_source_paths",
        "invalid_source_paths",
        "availability",
        "warnings",
        "errors",
        "manifest_hash",
    )
    for field in required_fields:
        if field not in manifest:
            errors.append(f"manifest_field_missing:{field}")
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        errors.append("manifest_schema_invalid")
    for field in list_fields:
        if field in manifest and not isinstance(manifest.get(field), list):
            errors.append(f"manifest_field_type_invalid:{field}")

    availability = str(manifest.get("availability") or "").strip()
    if availability not in VALID_MANIFEST_AVAILABILITIES:
        errors.append(f"manifest_availability_invalid:{availability or '<missing>'}")
    if manifest.get("warnings") and availability == "ready":
        errors.append("manifest_availability_inconsistent")
    if manifest.get("missing_source_paths") and availability not in {"missing_sources", "invalid"}:
        errors.append("manifest_availability_inconsistent")
    if manifest.get("invalid_source_paths") and availability != "invalid":
        errors.append("manifest_availability_inconsistent")
    if declared_errors and availability != "invalid":
        errors.append("manifest_availability_inconsistent")

    sources = list_values["sources"]
    source_by_path: dict[str, Mapping[str, Any]] = {}
    source_paths: list[str] = []
    if isinstance(manifest.get("sources"), list):
        for index, source_ref in enumerate(sources):
            if not isinstance(source_ref, Mapping):
                errors.append(f"manifest_source_type_invalid:{index}")
                continue
            source_path = str(source_ref.get("path") or "").strip()
            if _source_path_error(source_path):
                errors.append(f"source_path_invalid:manifest_source:{source_path or index}")
            if source_path in source_by_path:
                errors.append(f"manifest_source_duplicate:{source_path}")
            elif source_path:
                source_by_path[source_path] = source_ref
            source_paths.append(source_path)
            source_availability = str(source_ref.get("availability") or "").strip()
            if source_availability not in VALID_SOURCE_AVAILABILITIES:
                errors.append(
                    f"source_availability_invalid:manifest_source:{source_path or index}:{source_availability or '<missing>'}"
                )
            if source_availability == "available" and not is_sha256(source_ref.get("content_hash")):
                errors.append(f"source_hash_invalid:manifest_source:{source_path or index}")
            metadata_status = str(source_ref.get("metadata_status") or "").strip()
            if metadata_status not in VALID_SOURCE_METADATA_STATUSES:
                errors.append(
                    "source_metadata_status_invalid:manifest_source:"
                    f"{source_path or index}:{metadata_status or '<missing>'}"
                )
            missing_metadata = source_ref.get("missing_metadata")
            expected_missing_metadata = [
                field for field in SOURCE_METADATA_FIELDS if not source_ref.get(field)
            ]
            if not isinstance(missing_metadata, list) or missing_metadata != expected_missing_metadata:
                errors.append(
                    f"source_missing_metadata_invalid:manifest_source:{source_path or index}"
                )
            expected_metadata_status = "partial" if expected_missing_metadata else "complete"
            if metadata_status in VALID_SOURCE_METADATA_STATUSES and metadata_status != expected_metadata_status:
                errors.append(
                    f"source_metadata_status_mismatch:manifest_source:{source_path or index}"
                )

        expected_paths = [
            str(item or "").strip()
            for item in list_values["expected_source_paths"]
        ]
        if source_paths != expected_paths:
            errors.append("manifest_source_index_paths_mismatch")
        classified_paths = {
            "available_source_paths": [
                path
                for path, source_ref in zip(source_paths, sources)
                if isinstance(source_ref, Mapping) and source_ref.get("availability") == "available"
            ],
            "missing_source_paths": [
                path
                for path, source_ref in zip(source_paths, sources)
                if isinstance(source_ref, Mapping) and source_ref.get("availability") == "missing"
            ],
            "invalid_source_paths": [
                path
                for path, source_ref in zip(source_paths, sources)
                if isinstance(source_ref, Mapping) and source_ref.get("availability") == "invalid"
            ],
        }
        for field, expected in classified_paths.items():
            actual = [str(item or "").strip() for item in list_values[field]]
            if actual != expected:
                errors.append(f"manifest_source_index_mismatch:{field}")

    entries = list_values["entries"]
    if isinstance(manifest.get("entries"), list):
        seen_ids: set[str] = set()
        for index, entry in enumerate(entries):
            if not isinstance(entry, Mapping):
                errors.append(f"manifest_entry_type_invalid:{index}")
                continue
            knowledge_id = str(entry.get("knowledge_id") or "").strip()
            if not knowledge_id:
                errors.append(f"knowledge_id_missing:{index}")
            elif knowledge_id in seen_ids:
                errors.append(f"knowledge_id_duplicate:{knowledge_id}")
            else:
                seen_ids.add(knowledge_id)
            for field in REQUIRED_ENTRY_FIELDS:
                if entry.get(field) in (None, "", []):
                    errors.append(f"entry_field_missing:{knowledge_id or index}:{field}")
            for field in (
                "topics",
                "applies_to",
                "trigger_terms",
                "weak_trigger_terms",
                "relationships",
                "report_slots",
            ):
                if field in entry and not isinstance(entry.get(field), list):
                    errors.append(
                        f"entry_field_type_invalid:{knowledge_id or index}:{field}"
                    )
            kind = entry.get("kind")
            if not isinstance(kind, str):
                errors.append(f"entry_field_type_invalid:{knowledge_id or index}:kind")
            elif kind not in VALID_KINDS:
                errors.append(f"kind_invalid:{knowledge_id or index}:{kind}")
            lifecycle = entry.get("lifecycle")
            if not isinstance(lifecycle, str):
                errors.append(f"entry_field_type_invalid:{knowledge_id or index}:lifecycle")
            elif lifecycle not in VALID_LIFECYCLES:
                errors.append(f"lifecycle_invalid:{knowledge_id or index}:{lifecycle}")
            if entry.get("kind") == "knowledge_rule" and not _has_structured_confirmation(entry):
                errors.append(f"fact_conditions_missing:{knowledge_id or index}")
            elif entry.get("kind") == "knowledge_rule":
                errors.extend(
                    _fact_condition_path_errors(
                        entry,
                        knowledge_id=knowledge_id or str(index),
                    )
                )
            decision_scope = str(entry.get("decision_scope") or "").strip()
            if decision_scope and decision_scope not in VALID_DECISION_SCOPES:
                errors.append(f"decision_scope_invalid:{knowledge_id or index}:{decision_scope}")
            available_from = entry.get("available_from")
            if available_from not in (None, "") and (
                not isinstance(available_from, str)
                or not _is_iso_calendar_date(available_from)
            ):
                errors.append(
                    "available_from_invalid:"
                    f"{knowledge_id or index}:{available_from}"
                )
            source_ref = entry.get("source_ref")
            if not isinstance(source_ref, Mapping):
                errors.append(f"source_ref_missing:{knowledge_id or index}")
                continue
            source_path = str(source_ref.get("path") or "").strip()
            source_availability = str(source_ref.get("availability") or "").strip()
            if _source_path_error(source_path):
                errors.append(f"source_path_invalid:{knowledge_id or index}:{source_path}")
            if source_availability not in VALID_SOURCE_AVAILABILITIES:
                errors.append(
                    f"source_availability_invalid:{knowledge_id or index}:{source_availability or '<missing>'}"
                )
            if source_availability == "available" and not is_sha256(source_ref.get("content_hash")):
                errors.append(f"source_hash_invalid:{knowledge_id or index}")
            indexed_source = source_by_path.get(source_path)
            if not isinstance(indexed_source, Mapping):
                errors.append(f"source_index_missing:{knowledge_id or index}:{source_path}")
            elif any(
                source_ref.get(field) != indexed_source.get(field)
                for field in SOURCE_REF_INDEX_FIELDS
            ):
                errors.append(f"source_index_mismatch:{knowledge_id or index}:{source_path}")

    expected_hash = stable_json_hash(manifest, excluded_keys={"manifest_hash"})
    if manifest.get("manifest_hash") != expected_hash:
        errors.append("manifest_hash_mismatch")
    return list(dict.fromkeys(errors))


def validate_knowledge_manifest_sources(
    manifest: Any,
    *,
    root: Path,
) -> list[str]:
    """Verify declared source availability and hashes against repository bytes."""
    if not isinstance(manifest, Mapping):
        return ["manifest_type_invalid"]

    sources = manifest.get("sources")
    if not isinstance(sources, list):
        return ["manifest_field_type_invalid:sources"]

    errors: list[str] = []
    for index, source_ref in enumerate(sources):
        if not isinstance(source_ref, Mapping):
            errors.append(f"manifest_source_type_invalid:{index}")
            continue
        source_path = str(source_ref.get("path") or "").strip()
        if _source_path_error(source_path):
            errors.append(f"source_path_invalid:manifest_source:{source_path or index}")
            continue
        actual_ref, _ = _source_ref(Path(root), source_path)
        declared_availability = str(source_ref.get("availability") or "").strip()
        actual_availability = str(actual_ref.get("availability") or "").strip()
        if declared_availability != actual_availability:
            errors.append(
                "source_availability_mismatch:"
                f"{source_path}:{declared_availability or '<missing>'}:{actual_availability or '<missing>'}"
            )
            continue
        if (
            declared_availability == "available"
            and str(source_ref.get("content_hash") or "").strip()
            != str(actual_ref.get("content_hash") or "").strip()
        ):
            errors.append(f"source_content_hash_mismatch:{source_path}")
    return list(dict.fromkeys(errors))


__all__ = [
    "DEFAULT_DECISION_SCOPE",
    "EXPLICIT_FACT_PATHS",
    "MANIFEST_SCHEMA_VERSION",
    "VALID_DECISION_SCOPES",
    "VALID_KINDS",
    "VALID_LIFECYCLES",
    "VALID_MANIFEST_AVAILABILITIES",
    "VALID_SOURCE_METADATA_STATUSES",
    "build_knowledge_manifest",
    "is_sha256",
    "stable_json",
    "stable_json_hash",
    "validate_knowledge_manifest",
    "validate_knowledge_manifest_sources",
]
