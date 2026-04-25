from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping


def _safe(value: str) -> str:
    return "".join(char if char.isalnum() or char in ("-", "_", ".") else "-" for char in str(value or ""))


def reasoning_cache_key(*, target_date: str, input_hash: str, schema_version: str, prompt_version: str, model_source: str) -> str:
    return "_".join(
        [
            _safe(target_date),
            _safe(str(input_hash)[:12]),
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


def save_reasoning_decision_cache(cache_dir: Path | str, decision: Mapping[str, Any]) -> Path:
    cache_path = Path(cache_dir)
    cache_path.mkdir(parents=True, exist_ok=True)
    record = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "target_date": decision.get("target_date"),
        "input_hash": decision.get("input_hash"),
        "schema_version": decision.get("schema_version"),
        "prompt_version": decision.get("prompt_version"),
        "model_source": decision.get("model_source"),
        "decision": dict(decision),
    }
    path = cache_path / f"{_key_from_decision(decision)}.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return path


def load_reasoning_decision_cache(cache_dir: Path | str, decision_or_key: Mapping[str, Any] | str) -> Dict[str, Any]:
    cache_path = Path(cache_dir)
    key = _key_from_decision(decision_or_key) if isinstance(decision_or_key, Mapping) else str(decision_or_key)
    path = cache_path / f"{key}.json"
    return json.loads(path.read_text(encoding="utf-8"))
