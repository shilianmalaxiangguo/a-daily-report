from __future__ import annotations

from legacy_runtime_shim import export_or_default

get_limit_up_pool = export_or_default("limit_up_down_pool", "get_limit_up_pool", lambda *args, **kwargs: ([], set()))
get_limit_down_pool = export_or_default("limit_up_down_pool", "get_limit_down_pool", lambda *args, **kwargs: ([], set()))
mark_limit_status = export_or_default("limit_up_down_pool", "mark_limit_status", lambda *args, **kwargs: {})

__all__ = ["get_limit_up_pool", "get_limit_down_pool", "mark_limit_status"]
