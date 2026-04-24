from __future__ import annotations

from legacy_runtime_shim import export_or_default

fetch_ths_hot_stock = export_or_default("ths_hot_stock", "fetch_ths_hot_stock", lambda *args, **kwargs: [])
fetch_hot_stock_with_fallback = export_or_default("ths_hot_stock", "fetch_hot_stock_with_fallback", lambda *args, **kwargs: [])

__all__ = ["fetch_ths_hot_stock", "fetch_hot_stock_with_fallback"]
