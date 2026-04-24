from __future__ import annotations

import importlib.util
from pathlib import Path

__all__ = ["XuangubaoIntradayAnalyzer"]

_LEGACY_ANALYZER_PATH = Path("/Users/chaixixi/.workbuddy/skills/a-daily-report/scripts/xuangubao_intraday.py")
_LEGACY_ANALYZER_CLASS = None
_LEGACY_ANALYZER_LOAD_ATTEMPTED = False


def _load_legacy_analyzer_class():
    global _LEGACY_ANALYZER_CLASS, _LEGACY_ANALYZER_LOAD_ATTEMPTED
    if _LEGACY_ANALYZER_LOAD_ATTEMPTED:
        return _LEGACY_ANALYZER_CLASS

    _LEGACY_ANALYZER_LOAD_ATTEMPTED = True
    if not _LEGACY_ANALYZER_PATH.exists():
        _LEGACY_ANALYZER_CLASS = None
        return None

    try:
        spec = importlib.util.spec_from_file_location("_legacy_workbuddy_xuangubao_intraday", _LEGACY_ANALYZER_PATH)
        if spec is None or spec.loader is None:
            _LEGACY_ANALYZER_CLASS = None
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _LEGACY_ANALYZER_CLASS = getattr(module, "XuangubaoIntradayAnalyzer", None)
    except Exception:
        _LEGACY_ANALYZER_CLASS = None
    return _LEGACY_ANALYZER_CLASS


class XuangubaoIntradayAnalyzer:
    """本地兼容层：优先复用旧 skill 的选股通分析器，缺失时回退为空结果。"""

    def __init__(self):
        legacy_cls = _load_legacy_analyzer_class()
        self._legacy = None
        if legacy_cls is not None:
            try:
                self._legacy = legacy_cls()
            except Exception:
                self._legacy = None

    def fetch_xuangubao_data(self):
        if self._legacy is not None and hasattr(self._legacy, "fetch_xuangubao_data"):
            try:
                return dict(self._legacy.fetch_xuangubao_data() or {})
            except Exception:
                return {"xuangubao_news": [], "xuangubao_plates": []}
        return {"xuangubao_news": [], "xuangubao_plates": []}

    def __getattr__(self, name):
        if self._legacy is not None:
            return getattr(self._legacy, name)
        raise AttributeError(f"XuangubaoIntradayAnalyzer has no attribute {name!r}")
