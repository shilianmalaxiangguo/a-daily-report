from __future__ import annotations

from legacy_runtime_shim import export_or_default

fetch_hot_plate = export_or_default("ths_hot_list", "fetch_hot_plate", lambda *args, **kwargs: [])

__all__ = ["fetch_hot_plate"]
