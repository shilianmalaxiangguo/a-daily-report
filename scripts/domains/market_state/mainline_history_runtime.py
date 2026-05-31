from __future__ import annotations

import datetime

from daily_report_snapshot_io import load_data_snapshot
from market_data.kline_dates import normalize_kline_date_str as _default_normalize_kline_date_str

try:
    from storage.database_service import DatabaseService
except Exception:  # pragma: no cover - optional runtime dependency
    DatabaseService = None

try:
    from domains.market_state.daily_metric_history_index import (
        ensure_daily_metric_history_index as _default_ensure_daily_metric_history_index,
    )
except Exception:  # pragma: no cover - optional runtime dependency
    _default_ensure_daily_metric_history_index = None

__all__ = [
    "build_mainline_history_record",
    "extract_mainline_history_record",
    "load_recent_mainline_history",
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


def _first_non_empty(*values):
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _pick_role_sector(competition_rows, role_name):
    for item in competition_rows or []:
        role = str((item or {}).get("role", "") or "").strip()
        if role != role_name:
            continue
        sector = str((item or {}).get("sector", "") or "").strip()
        if sector:
            return sector
    return ""


def _normalize_date(value):
    return str(value or "").strip()


def _normalize_kline_date_str(value):
    return _default_normalize_kline_date_str(value)


def ensure_daily_metric_history_index(**kwargs):
    if callable(_default_ensure_daily_metric_history_index):
        return _default_ensure_daily_metric_history_index(**kwargs)
    return {"indexed_count": 0, "dates": []}


def get_previous_date_str(target_date):
    try:
        dt = datetime.datetime.strptime(str(target_date), "%Y-%m-%d").date()
    except Exception:
        return None
    return (dt - datetime.timedelta(days=1)).strftime("%Y-%m-%d")


def build_mainline_history_record(target_date, market_research_snapshot=None):
    market_research_snapshot = market_research_snapshot or {}
    state_machine = market_research_snapshot.get("state_machine", {}) or {}
    observation = market_research_snapshot.get("observation", {}) or {}
    rotation_snapshot = market_research_snapshot.get("mainline_rotation_snapshot", {}) or {}
    competition_rows = observation.get("mainline_competition_snapshot", []) or []

    primary_mainline = _first_non_empty(
        state_machine.get("leading_line"),
        _pick_role_sector(competition_rows, "主攻线"),
        (observation.get("mainline_candidates", []) or [""])[0],
    )
    secondary_mainline = _first_non_empty(
        _pick_role_sector(competition_rows, "次强线"),
        (observation.get("secondary_candidates", []) or [""])[0],
    )
    competition_mainline = _first_non_empty(
        _pick_role_sector(competition_rows, "竞争线"),
    )

    return {
        "date": _normalize_date(target_date),
        "primary_mainline": primary_mainline,
        "secondary_mainline": secondary_mainline,
        "competition_mainline": competition_mainline,
        "rotation_label": str(rotation_snapshot.get("rotation_label", "") or "").strip(),
        "leading_line": str(state_machine.get("leading_line", "") or "").strip(),
        "state_code": str(state_machine.get("state_code", "") or "").strip(),
        "rotation_summary": str(rotation_snapshot.get("summary_text", "") or "").strip(),
        "source": "market_research_snapshot",
    }


def _iter_mainline_history_records(payload, depth=0, max_depth=6):
    if payload is None or depth > max_depth:
        return []

    records = []
    if isinstance(payload, dict):
        current_record = payload.get("current_mainline_history_record")
        if isinstance(current_record, dict):
            records.append(current_record)

        current_records = payload.get("current_mainline_history_records")
        if isinstance(current_records, list):
            records.extend(item for item in current_records if isinstance(item, dict))

        direct_record = payload.get("mainline_history_record")
        if isinstance(direct_record, dict):
            records.append(direct_record)

        direct_records = payload.get("mainline_history_records")
        if isinstance(direct_records, list):
            records.extend(item for item in direct_records if isinstance(item, dict))

        for key, value in payload.items():
            if key in {
                "current_mainline_history_record",
                "current_mainline_history_records",
                "mainline_history_record",
                "mainline_history_records",
                "recent_mainline_history",
            }:
                continue
            if isinstance(value, (dict, list)):
                records.extend(_iter_mainline_history_records(value, depth=depth + 1, max_depth=max_depth))
        return records

    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, (dict, list)):
                records.extend(_iter_mainline_history_records(item, depth=depth + 1, max_depth=max_depth))
    return records


def _score_mainline_history_record(record):
    if not isinstance(record, dict):
        return 0
    primary_mainline = str(record.get("primary_mainline", "") or "").strip()
    leading_line = str(record.get("leading_line", "") or "").strip()
    if primary_mainline:
        return 2
    if leading_line:
        return 1
    return 0


def extract_mainline_history_record(snapshot_data):
    best_record = None
    best_score = 0

    for candidate in _iter_mainline_history_records(snapshot_data):
        score = _score_mainline_history_record(candidate)
        if score > best_score:
            best_score = score
            best_record = candidate

    if not best_record:
        return None

    primary_mainline = _first_non_empty(best_record.get("primary_mainline"), best_record.get("leading_line"))
    if not primary_mainline:
        return None

    return {
        "date": _normalize_date(best_record.get("date")),
        "primary_mainline": primary_mainline,
        "secondary_mainline": _normalize_date(best_record.get("secondary_mainline")),
        "competition_mainline": _normalize_date(best_record.get("competition_mainline")),
        "rotation_label": _normalize_date(best_record.get("rotation_label")),
        "leading_line": _normalize_date(best_record.get("leading_line") or primary_mainline),
        "state_code": _normalize_date(best_record.get("state_code")),
        "rotation_summary": _normalize_date(best_record.get("rotation_summary")),
        "source": _normalize_date(best_record.get("source")),
    }


def _normalize_history_record(record, fallback_date=""):
    if not isinstance(record, dict):
        return None
    primary_mainline = _first_non_empty(record.get("primary_mainline"), record.get("leading_line"))
    if not primary_mainline:
        return None
    return {
        "date": _normalize_date(record.get("date") or fallback_date),
        "primary_mainline": primary_mainline,
        "secondary_mainline": _normalize_date(record.get("secondary_mainline")),
        "competition_mainline": _normalize_date(record.get("competition_mainline")),
        "rotation_label": _normalize_date(record.get("rotation_label")),
        "leading_line": _normalize_date(record.get("leading_line") or primary_mainline),
        "state_code": _normalize_date(record.get("state_code")),
        "rotation_summary": _normalize_date(record.get("rotation_summary")),
        "source": _normalize_date(record.get("source")),
    }


def _iter_recent_mainline_history(payload, depth=0, max_depth=4):
    if payload is None or depth > max_depth:
        return []
    records = []
    if isinstance(payload, dict):
        direct_records = payload.get("recent_mainline_history")
        if isinstance(direct_records, list):
            records.extend(item for item in direct_records if isinstance(item, dict))
        for key, value in payload.items():
            if key == "recent_mainline_history":
                continue
            if isinstance(value, (dict, list)):
                records.extend(_iter_recent_mainline_history(value, depth=depth + 1, max_depth=max_depth))
        return records
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, (dict, list)):
                records.extend(_iter_recent_mainline_history(item, depth=depth + 1, max_depth=max_depth))
    return records


def _load_recent_mainline_history_from_fact_db(target_date, lookback_days=25, *, db_path=None):
    service_cls = globals().get("DatabaseService")
    if service_cls is None:
        return []
    try:
        if hasattr(service_cls, "from_environment"):
            service = service_cls.from_environment(db_path)
        else:
            service = service_cls.sqlite_d1_compatible(db_path)
        rows = service.query_mainline_daily_series(
            _normalize_kline_date_str(target_date) or target_date,
            window_days=lookback_days,
        )
    except Exception:
        return []
    normalized = []
    for row in rows or []:
        record = _normalize_history_record(row, fallback_date=row.get("trade_date") if isinstance(row, dict) else "")
        if record and str(record.get("date") or "") < str(target_date):
            normalized.append(record)
    return normalized[-lookback_days:]


def _history_latest_date(history):
    dates = [str((item or {}).get("date") or "").strip() for item in history or []]
    dates = [date for date in dates if date]
    return max(dates) if dates else ""


def _history_is_stale(history, target_date):
    latest = _history_latest_date(history)
    previous_target = get_previous_date_str(_normalize_kline_date_str(target_date) or target_date)
    return bool(previous_target and latest and latest < previous_target)


def _history_is_short(history, lookback_days):
    try:
        target_count = max(int(lookback_days or 0), 1)
    except (TypeError, ValueError):
        target_count = 1
    return len(list(history or [])) < target_count


def load_recent_mainline_history(target_date, lookback_days=5, max_scan_days=20, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        if globals().get("DatabaseService") is not None:
            db_history = _load_recent_mainline_history_from_fact_db(
                target_date,
                lookback_days=lookback_days,
            )
            if (
                db_history
                and (
                    _history_is_stale(db_history, target_date)
                    or _history_is_short(db_history, lookback_days)
                )
                and callable(globals().get("ensure_daily_metric_history_index"))
            ):
                globals()["ensure_daily_metric_history_index"](
                    end_date=_normalize_kline_date_str(target_date) or target_date,
                    window_days=lookback_days,
                    max_scan_days=max_scan_days,
                )
                db_history = _load_recent_mainline_history_from_fact_db(
                    target_date,
                    lookback_days=lookback_days,
                )
            if db_history:
                return db_history

        history_by_date = {}
        cursor = _normalize_kline_date_str(target_date)
        scanned_days = 0

        while cursor and len(history_by_date) < lookback_days and scanned_days < max_scan_days:
            cursor = get_previous_date_str(cursor)
            if not cursor:
                break
            scanned_days += 1

            snapshot_data, _ = load_data_snapshot(cursor)
            if not snapshot_data:
                continue

            for recent_record in _iter_recent_mainline_history(snapshot_data):
                normalized_recent = _normalize_history_record(recent_record)
                record_date = normalized_recent.get("date") if normalized_recent else ""
                if not record_date or record_date >= str(target_date):
                    continue
                history_by_date.setdefault(record_date, normalized_recent)

            record = extract_mainline_history_record(snapshot_data)
            if not record:
                continue

            normalized_record = _normalize_history_record(record, fallback_date=cursor)
            record_date = normalized_record.get("date") if normalized_record else ""
            if record_date and record_date < str(target_date):
                history_by_date[record_date] = normalized_record

        return [history_by_date[key] for key in sorted(history_by_date)][-lookback_days:]
    finally:
        _restore_runtime_bindings(previous)
