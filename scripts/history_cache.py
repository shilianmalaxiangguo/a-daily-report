from __future__ import annotations

from legacy_runtime_shim import export_or_default


class _HistoryCacheFallback:
    pass


get_cache = export_or_default("history_cache", "get_cache", lambda *args, **kwargs: {})
HistoryCache = export_or_default("history_cache", "HistoryCache", _HistoryCacheFallback)

__all__ = ["get_cache", "HistoryCache"]
