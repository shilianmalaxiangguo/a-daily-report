from __future__ import annotations

import daily_report_analysis_utils as analysis_utils

__all__ = [
    "resolve_primary_mainline_name",
    "split_candidates_by_mainline",
]

_MISSING = object()


def _install_runtime_bindings(bindings):
    previous = {}
    module_globals = globals()
    for key, value in (bindings or {}).items():
        if key.startswith("__") and key.endswith("__"):
            continue
        previous[key] = module_globals.get(key, _MISSING)
        module_globals[key] = value
    return previous


def _restore_runtime_bindings(previous):
    module_globals = globals()
    for key, value in (previous or {}).items():
        if value is _MISSING:
            module_globals.pop(key, None)
        else:
            module_globals[key] = value


def resolve_primary_mainline_name(market_research_snapshot=None, fallback_mainline="", *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _resolve_primary_mainline_name_legacy_body(
            market_research_snapshot=market_research_snapshot,
            fallback_mainline=fallback_mainline,
        )
    finally:
        _restore_runtime_bindings(previous)


def split_candidates_by_mainline(candidates, mainline_name="", *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _split_candidates_by_mainline_legacy_body(candidates, mainline_name=mainline_name)
    finally:
        _restore_runtime_bindings(previous)


def _candidate_matches_mainline(candidate, mainline_name=""):
    return analysis_utils._candidate_matches_mainline(candidate, mainline_name)


def _resolve_primary_mainline_name_legacy_body(market_research_snapshot=None, fallback_mainline=""):
    market_research_snapshot = market_research_snapshot or {}
    observation = market_research_snapshot.get("observation", {}) or {}
    mainline_candidates = observation.get("mainline_candidates", []) or []
    for name in mainline_candidates:
        name = str(name or "").strip()
        if name and "暂无明确主线" not in name:
            return name
    fallback_mainline = str(fallback_mainline or "").strip()
    return "" if "暂无明确主线" in fallback_mainline else fallback_mainline


def _split_candidates_by_mainline_legacy_body(candidates, mainline_name=""):
    mainline_items = []
    crossline_items = []
    for item in candidates or []:
        if _candidate_matches_mainline(item, mainline_name):
            mainline_items.append(item)
        else:
            crossline_items.append(item)
    return mainline_items, crossline_items
