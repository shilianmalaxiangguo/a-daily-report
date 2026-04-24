from __future__ import annotations

from legacy_runtime_shim import export_or_default

get_integrated_hot_list = export_or_default("hot_list_integrated", "get_integrated_hot_list", lambda *args, **kwargs: {})
analyze_sector_distribution = export_or_default("hot_list_integrated", "analyze_sector_distribution", lambda *args, **kwargs: {})

__all__ = ["get_integrated_hot_list", "analyze_sector_distribution"]
