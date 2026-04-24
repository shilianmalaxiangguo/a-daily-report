from __future__ import annotations

from legacy_runtime_shim import export_or_default

get_strong_stock_pool = export_or_default("strong_stock_pool", "get_strong_stock_pool", lambda *args, **kwargs: [])
analyze_strong_stocks_by_sector = export_or_default("strong_stock_pool", "analyze_strong_stocks_by_sector", lambda *args, **kwargs: {})

__all__ = ["get_strong_stock_pool", "analyze_strong_stocks_by_sector"]
