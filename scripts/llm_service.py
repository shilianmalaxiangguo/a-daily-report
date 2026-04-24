from __future__ import annotations

from legacy_runtime_shim import export_or_default

get_llm_service = export_or_default("llm_service", "get_llm_service", lambda *args, **kwargs: None)

__all__ = ["get_llm_service"]
