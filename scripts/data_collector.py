from __future__ import annotations

import importlib.util
from pathlib import Path

__all__ = ["AShareDataCollector"]

_LEGACY_COLLECTOR_PATH = Path("/Users/chaixixi/.workbuddy/skills/a-daily-report/scripts/data_collector.py")
_LEGACY_COLLECTOR_CLASS = None
_LEGACY_COLLECTOR_LOAD_ATTEMPTED = False


def _load_legacy_collector_class():
    global _LEGACY_COLLECTOR_CLASS, _LEGACY_COLLECTOR_LOAD_ATTEMPTED
    if _LEGACY_COLLECTOR_LOAD_ATTEMPTED:
        return _LEGACY_COLLECTOR_CLASS

    _LEGACY_COLLECTOR_LOAD_ATTEMPTED = True
    if not _LEGACY_COLLECTOR_PATH.exists():
        _LEGACY_COLLECTOR_CLASS = None
        return None

    try:
        spec = importlib.util.spec_from_file_location("_legacy_workbuddy_data_collector", _LEGACY_COLLECTOR_PATH)
        if spec is None or spec.loader is None:
            _LEGACY_COLLECTOR_CLASS = None
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _LEGACY_COLLECTOR_CLASS = getattr(module, "AShareDataCollector", None)
    except Exception:
        _LEGACY_COLLECTOR_CLASS = None
    return _LEGACY_COLLECTOR_CLASS


class AShareDataCollector:
    """本地兼容层：优先复用旧 skill 的 collector，缺失时只保留入口直跑所需最小接口。"""

    def __init__(self):
        legacy_cls = _load_legacy_collector_class()
        self._legacy = None
        if legacy_cls is not None:
            try:
                self._legacy = legacy_cls()
            except Exception:
                self._legacy = None

    def get_wanzhu_top10(self, query_date: str) -> list:
        if self._legacy is not None and hasattr(self._legacy, "get_wanzhu_top10"):
            try:
                result = self._legacy.get_wanzhu_top10(query_date)
                return list(result or [])
            except Exception:
                return []
        return []

    def __getattr__(self, name):
        if self._legacy is not None:
            return getattr(self._legacy, name)
        raise AttributeError(f"AShareDataCollector has no attribute {name!r}")
