from __future__ import annotations

import os
import json
import time
from pathlib import Path

from storage.database_service import DatabaseService


def _postgres_database_url():
    return (
        os.environ.get("A_DAILY_REPORT_DATABASE_URL")
        or os.environ.get("DATABASE_URL")
        or ""
    ).strip()


def _postgres_only_runtime():
    return os.environ.get("A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME", "").strip() == "1"


def _runtime_cache_service():
    database_url = _postgres_database_url()
    postgres_required = _postgres_only_runtime() or database_url.startswith(("postgres://", "postgresql://"))
    if not postgres_required:
        return None
    service = DatabaseService.from_environment()
    if not service.is_postgres_backed():
        if _postgres_only_runtime():
            raise RuntimeError("PostgreSQL-only history cache requires PostgreSQL storage")
        return None
    return service


class _PostgresHistoryCache:
    def __init__(self, service, cache_dir: str | Path | None = None):
        self.service = service
        self.cache_dir = Path(cache_dir) if cache_dir is not None else Path(__file__).resolve().parent / "cache" / "history_cache"

    def _cache_key(self, code):
        return str(code or "")

    def _target_date(self, target_date):
        return str(target_date or "").strip()

    def _load(self, target_date):
        entry = self.service.get_runtime_cache_entry("history_cache", self._cache_key(None), self._target_date(target_date))
        return entry.get("payload", {}) if isinstance(entry, dict) else {}

    def _entry(self, code, target_date):
        entry = self.service.get_runtime_cache_entry("history_cache", self._cache_key(code), self._target_date(target_date))
        if isinstance(entry, dict):
            payload = entry.get("payload")
            if not isinstance(payload, dict):
                payload = {}
            return {**payload, "source": entry.get("source", "")}
        return {}

    def clean_old_cache(self, keep_days=7):
        try:
            keep_seconds = max(0, int(keep_days or 0)) * 86400
        except (TypeError, ValueError):
            keep_seconds = 7 * 86400
        if keep_seconds <= 0:
            return
        self.service.delete_expired_runtime_cache_entries()

    def get_cache_stats(self, target_date):
        return self.service.get_runtime_cache_stats("history_cache", self._target_date(target_date))

    def get(self, code, target_date):
        entry = self.service.get_runtime_cache_entry("history_cache", self._cache_key(code), self._target_date(target_date))
        if not isinstance(entry, dict):
            return []
        payload = entry.get("payload")
        if isinstance(payload, dict):
            data = payload.get("data")
        else:
            data = payload
        return list(data) if isinstance(data, list) else []

    def get_entry(self, code, target_date):
        entry = self.service.get_runtime_cache_entry("history_cache", self._cache_key(code), self._target_date(target_date))
        if not isinstance(entry, dict):
            return {}
        payload = entry.get("payload")
        if not isinstance(payload, dict):
            payload = {}
        result = dict(payload)
        if "data" not in result and isinstance(payload, list):
            result["data"] = list(payload)
        result["source"] = entry.get("source", "")
        return result

    def set(self, code, target_date, data, source="mixed_partial", max_length=120):
        values = list(data or [])
        if max_length:
            try:
                values = values[-int(max_length) :]
            except (TypeError, ValueError):
                pass
        payload = {
            "data": values,
            "source": source,
            "updated_at": int(time.time()),
        }
        return self.service.set_runtime_cache_entry(
            "history_cache",
            self._cache_key(code),
            self._target_date(target_date),
            payload,
            source=source,
            ttl_seconds=7 * 86400,
        )


class _HistoryCacheFallback:
    def __init__(self, cache_dir: str | Path | None = None):
        self.cache_dir = Path(cache_dir) if cache_dir is not None else Path(__file__).resolve().parent / "cache" / "history_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, target_date):
        safe_date = str(target_date or "").strip() or "unknown"
        safe_date = safe_date.replace("/", "-").replace(":", "-")
        return self.cache_dir / f"{safe_date}.json"

    def _load(self, target_date):
        path = self._path(target_date)
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def _save(self, target_date, payload):
        path = self._path(target_date)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    def clean_old_cache(self, keep_days=7):
        try:
            keep_seconds = max(0, int(keep_days or 0)) * 86400
        except (TypeError, ValueError):
            keep_seconds = 7 * 86400
        if keep_seconds <= 0:
            return
        cutoff = time.time() - keep_seconds
        for path in self.cache_dir.glob("*.json"):
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink()
            except OSError:
                continue

    def get_cache_stats(self, target_date):
        path = self._path(target_date)
        payload = self._load(target_date)
        size_mb = 0.0
        try:
            size_mb = round(path.stat().st_size / 1024 / 1024, 4) if path.exists() else 0.0
        except OSError:
            size_mb = 0.0
        return {"count": len(payload), "size_mb": size_mb}

    def get(self, code, target_date):
        entry = self._load(target_date).get(str(code or ""))
        if isinstance(entry, dict):
            data = entry.get("data")
        else:
            data = entry
        return list(data) if isinstance(data, list) else []

    def get_entry(self, code, target_date):
        entry = self._load(target_date).get(str(code or ""))
        if isinstance(entry, dict):
            return dict(entry)
        if isinstance(entry, list):
            return {"data": list(entry), "source": ""}
        return {}

    def set(self, code, target_date, data, source="mixed_partial", max_length=120):
        values = list(data or [])
        if max_length:
            try:
                values = values[-int(max_length) :]
            except (TypeError, ValueError):
                pass
        payload = self._load(target_date)
        payload[str(code or "")] = {
            "data": values,
            "source": source,
            "updated_at": int(time.time()),
        }
        self._save(target_date, payload)


class HistoryCache:
    def __new__(cls, cache_dir: str | Path | None = None):
        service = _runtime_cache_service()
        if service is not None:
            return _PostgresHistoryCache(service, cache_dir=cache_dir)
        return _HistoryCacheFallback(cache_dir=cache_dir)


def get_cache(*args, **kwargs):
    return HistoryCache(*args, **kwargs)

__all__ = ["get_cache", "HistoryCache"]
