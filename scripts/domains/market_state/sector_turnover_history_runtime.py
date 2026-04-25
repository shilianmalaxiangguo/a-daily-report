from __future__ import annotations

import datetime

import daily_report_analysis_utils as analysis_utils
from daily_report_snapshot_io import load_data_snapshot
from market_data.kline_dates import normalize_kline_date_str as _default_normalize_kline_date_str

__all__ = [
    "extract_sector_turnover_snapshot",
    "load_recent_sector_turnover_history",
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


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def sector_name_matches(sector_a, sector_b):
    return analysis_utils.sector_name_matches(sector_a, sector_b)


def get_previous_date_str(target_date):
    try:
        dt = datetime.datetime.strptime(str(target_date), "%Y-%m-%d").date()
    except Exception:
        return None
    return (dt - datetime.timedelta(days=1)).strftime("%Y-%m-%d")


def _normalize_kline_date_str(value):
    return _default_normalize_kline_date_str(value)


def _iter_sector_turnover_snapshots(payload, depth=0, max_depth=6):
    if payload is None or depth > max_depth:
        return []

    snapshots = []
    if isinstance(payload, dict):
        direct_snapshot = payload.get("sector_turnover_snapshot")
        if isinstance(direct_snapshot, dict):
            snapshots.append(direct_snapshot)

        direct_snapshots = payload.get("sector_turnover_snapshots")
        if isinstance(direct_snapshots, list):
            snapshots.extend(item for item in direct_snapshots if isinstance(item, dict))

        for key, value in payload.items():
            if key in {"sector_turnover_snapshot", "sector_turnover_snapshots"}:
                continue
            if isinstance(value, (dict, list)):
                snapshots.extend(_iter_sector_turnover_snapshots(value, depth=depth + 1, max_depth=max_depth))
        return snapshots

    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, (dict, list)):
                snapshots.extend(_iter_sector_turnover_snapshots(item, depth=depth + 1, max_depth=max_depth))
    return snapshots


def _score_sector_turnover_snapshot(snapshot, sector_name):
    sector_name = str(sector_name or "").strip()
    if not sector_name or not isinstance(snapshot, dict):
        return 0

    score = 0
    snapshot_name = str(snapshot.get("sector_name", "") or "").strip()
    if snapshot_name == sector_name:
        score = max(score, 4)
    elif sector_name_matches(snapshot_name, sector_name):
        score = max(score, 3)

    for alias in snapshot.get("matched_sector_names", []) or []:
        alias = str(alias or "").strip()
        if not alias:
            continue
        if alias == sector_name:
            score = max(score, 2)
        elif sector_name_matches(alias, sector_name):
            score = max(score, 1)

    return score


def extract_sector_turnover_snapshot(snapshot_data, sector_name):
    best_snapshot = None
    best_score = 0

    for candidate in _iter_sector_turnover_snapshots(snapshot_data):
        score = _score_sector_turnover_snapshot(candidate, sector_name)
        if score > best_score:
            best_score = score
            best_snapshot = candidate

    if not best_snapshot:
        return None

    sector_turnover = round(_safe_float(best_snapshot.get("sector_turnover")), 2)
    total_turnover = round(_safe_float(best_snapshot.get("total_turnover")), 2)
    turnover_share_pct = best_snapshot.get("turnover_share_pct")
    if turnover_share_pct in (None, "") and sector_turnover > 0 and total_turnover > 0:
        turnover_share_pct = sector_turnover / total_turnover * 100
    turnover_share_pct = round(_safe_float(turnover_share_pct), 2)

    if sector_turnover <= 0 and turnover_share_pct <= 0:
        return None

    return {
        "date": str(best_snapshot.get("date", "") or "").strip(),
        "sector_name": str(best_snapshot.get("sector_name", "") or "").strip(),
        "sector_turnover": sector_turnover,
        "total_turnover": total_turnover,
        "turnover_share_pct": turnover_share_pct,
        "matched_sector_names": [str(item or "").strip() for item in (best_snapshot.get("matched_sector_names") or []) if str(item or "").strip()],
        "matched_sector_codes": [str(item or "").strip() for item in (best_snapshot.get("matched_sector_codes") or []) if str(item or "").strip()],
        "source": str(best_snapshot.get("source", "") or "").strip(),
    }


def load_recent_sector_turnover_history(target_date, sector_name, lookback_days=5, max_scan_days=20, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        history = []
        cursor = _normalize_kline_date_str(target_date)
        scanned_days = 0

        while cursor and len(history) < lookback_days and scanned_days < max_scan_days:
            cursor = get_previous_date_str(cursor)
            if not cursor:
                break
            scanned_days += 1

            snapshot_data, _ = load_data_snapshot(cursor)
            if not snapshot_data:
                continue

            snapshot = extract_sector_turnover_snapshot(snapshot_data, sector_name)
            if not snapshot:
                continue

            history.append(
                {
                    "date": snapshot.get("date") or cursor,
                    "sector_name": snapshot.get("sector_name", ""),
                    "sector_turnover": round(_safe_float(snapshot.get("sector_turnover")), 2),
                    "total_turnover": round(_safe_float(snapshot.get("total_turnover")), 2),
                    "turnover_share_pct": round(_safe_float(snapshot.get("turnover_share_pct")), 2),
                    "matched_sector_names": list(snapshot.get("matched_sector_names", []) or []),
                    "matched_sector_codes": list(snapshot.get("matched_sector_codes", []) or []),
                    "source": snapshot.get("source", ""),
                }
            )

        history.reverse()
        return history
    finally:
        _restore_runtime_bindings(previous)
