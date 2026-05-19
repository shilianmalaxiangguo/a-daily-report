from __future__ import annotations

import json
import time
from legacy_runtime_shim import export_or_default
from pathlib import Path


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


get_cache = export_or_default("history_cache", "get_cache", lambda *args, **kwargs: _HistoryCacheFallback(*args, **kwargs))
HistoryCache = export_or_default("history_cache", "HistoryCache", _HistoryCacheFallback)

__all__ = ["get_cache", "HistoryCache"]
