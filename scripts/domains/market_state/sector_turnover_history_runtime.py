from __future__ import annotations

import datetime

import daily_report_analysis_utils as analysis_utils
from daily_report_snapshot_io import load_data_snapshot
from market_data.kline_dates import normalize_kline_date_str as _default_normalize_kline_date_str

try:
    from market_data.tushare_market_activity_service import fetch_tushare_sector_flow as _default_fetch_tushare_sector_flow
except Exception:  # pragma: no cover - optional runtime dependency
    _default_fetch_tushare_sector_flow = None

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


def fetch_tushare_sector_flow(trade_date):
    if not callable(_default_fetch_tushare_sector_flow):
        return []
    return _default_fetch_tushare_sector_flow(trade_date)


def get_market_total_turnover_from_fact_db(target_date, *, market_scope="all_a", db_path=None):
    if DatabaseService is None:
        return 0.0
    try:
        if hasattr(DatabaseService, "fact_store_from_environment"):
            service = DatabaseService.fact_store_from_environment(db_path)
        elif hasattr(DatabaseService, "from_environment"):
            service = DatabaseService.from_environment(db_path)
        else:
            return 0.0
        row = service.query_market_daily_total(target_date, market_scope=market_scope)
    except Exception:
        return 0.0
    return _safe_float((row or {}).get("total_amount_yi"))


def get_previous_date_str(target_date):
    try:
        dt = datetime.datetime.strptime(str(target_date), "%Y-%m-%d").date()
    except Exception:
        return None
    return (dt - datetime.timedelta(days=1)).strftime("%Y-%m-%d")


def _normalize_kline_date_str(value):
    return _default_normalize_kline_date_str(value)


def ensure_daily_metric_history_index(**kwargs):
    if callable(_default_ensure_daily_metric_history_index):
        return _default_ensure_daily_metric_history_index(**kwargs)
    return {"indexed_count": 0, "dates": []}


def _postgres_only_runtime():
    return bool(globals().get("postgres_only_runtime"))


def _payload_total_turnover(payload, inherited_total_turnover=0.0):
    if not isinstance(payload, dict):
        return _safe_float(inherited_total_turnover)
    for key in ("total_turnover", "market_amount_yi", "total_amount_yi"):
        value = _safe_float(payload.get(key))
        if value > 0:
            return value
    turnover_data = payload.get("turnover_data")
    if isinstance(turnover_data, dict):
        for key in ("total_turnover_yi", "total_turnover", "total_amount_yi"):
            value = _safe_float(turnover_data.get(key))
            if value > 0:
                return value
    return _safe_float(inherited_total_turnover)


def _extract_total_turnover(payload, depth=0, max_depth=6):
    if payload is None or depth > max_depth:
        return 0.0
    if isinstance(payload, dict):
        direct = _payload_total_turnover(payload)
        if direct > 0:
            return direct
        for value in payload.values():
            if isinstance(value, (dict, list)):
                nested = _extract_total_turnover(value, depth=depth + 1, max_depth=max_depth)
                if nested > 0:
                    return nested
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, (dict, list)):
                nested = _extract_total_turnover(item, depth=depth + 1, max_depth=max_depth)
                if nested > 0:
                    return nested
    return 0.0


def _sector_fund_flow_row_to_turnover_snapshot(row, total_turnover=0.0):
    row = row or {}
    sector_name = str(row.get("name") or row.get("industry") or row.get("sector_name") or "").strip()
    if not sector_name:
        return None
    sector_turnover = _safe_float(row.get("turnover_yi"))
    if sector_turnover <= 0:
        sector_turnover = _safe_float(row.get("sector_turnover_yi") or row.get("sector_turnover"))
    if sector_turnover <= 0:
        sector_turnover = _safe_float(row.get("net_buy_amount")) + _safe_float(row.get("net_sell_amount"))
    if sector_turnover <= 0:
        return None
    total_turnover = _safe_float(total_turnover)
    return {
        "date": _normalize_kline_date_str(row.get("trade_date") or row.get("date") or ""),
        "sector_name": sector_name,
        "sector_turnover": round(sector_turnover, 2),
        "total_turnover": round(total_turnover, 2),
        "turnover_share_pct": round(sector_turnover / total_turnover * 100, 2) if total_turnover > 0 else 0.0,
        "matched_sector_names": [sector_name],
        "matched_sector_codes": [str(row.get("code") or row.get("ts_code") or "").strip()],
        "source": str(row.get("data_source") or row.get("source") or "tushare.moneyflow_ind_ths").strip(),
    }


def _iter_sector_fund_flow_turnover_snapshots(sector_fund_flow, total_turnover=0.0):
    snapshots = []
    if isinstance(sector_fund_flow, dict):
        buckets = [sector_fund_flow.get("inflow"), sector_fund_flow.get("outflow")]
    elif isinstance(sector_fund_flow, list):
        buckets = [sector_fund_flow]
    else:
        buckets = []
    for bucket in buckets:
        for row in bucket or []:
            snapshot = _sector_fund_flow_row_to_turnover_snapshot(row, total_turnover=total_turnover)
            if snapshot:
                snapshots.append(snapshot)
    return snapshots


def _iter_sector_turnover_snapshots(payload, depth=0, max_depth=6, inherited_total_turnover=0.0):
    if payload is None or depth > max_depth:
        return []

    snapshots = []
    if isinstance(payload, dict):
        total_turnover = _payload_total_turnover(payload, inherited_total_turnover)
        direct_snapshot = payload.get("sector_turnover_snapshot")
        if isinstance(direct_snapshot, dict):
            snapshots.append(direct_snapshot)

        current_snapshot = payload.get("current_sector_turnover_snapshot")
        if isinstance(current_snapshot, dict):
            snapshots.append(current_snapshot)

        direct_snapshots = payload.get("sector_turnover_snapshots")
        if isinstance(direct_snapshots, list):
            snapshots.extend(item for item in direct_snapshots if isinstance(item, dict))

        snapshots.extend(_iter_sector_fund_flow_turnover_snapshots(payload.get("sector_fund_flow"), total_turnover))

        for key, value in payload.items():
            if key in {
                "sector_turnover_snapshot",
                "current_sector_turnover_snapshot",
                "sector_turnover_snapshots",
                "sector_fund_flow",
            }:
                continue
            if isinstance(value, (dict, list)):
                snapshots.extend(
                    _iter_sector_turnover_snapshots(
                        value,
                        depth=depth + 1,
                        max_depth=max_depth,
                        inherited_total_turnover=total_turnover,
                    )
                )
        return snapshots

    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, (dict, list)):
                snapshots.extend(
                    _iter_sector_turnover_snapshots(
                        item,
                        depth=depth + 1,
                        max_depth=max_depth,
                        inherited_total_turnover=inherited_total_turnover,
                    )
                )
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


def _fetch_tushare_sector_turnover_snapshot(trade_date, sector_name, total_turnover=0.0):
    if not callable(fetch_tushare_sector_flow):
        return None
    candidates = []
    try:
        rows = fetch_tushare_sector_flow(trade_date) or []
    except Exception:
        rows = []
    for row in rows:
        snapshot = _sector_fund_flow_row_to_turnover_snapshot(row, total_turnover=total_turnover)
        if snapshot:
            candidates.append(snapshot)
    best_snapshot = None
    best_score = 0
    for candidate in candidates:
        score = _score_sector_turnover_snapshot(candidate, sector_name)
        if score > best_score:
            best_score = score
            best_snapshot = candidate
    if not best_snapshot:
        return None
    best_snapshot = dict(best_snapshot)
    if not best_snapshot.get("date"):
        best_snapshot["date"] = _normalize_kline_date_str(trade_date)
    return best_snapshot


def _total_turnover_from_payload_or_fact_db(snapshot_data, trade_date):
    total_turnover = _extract_total_turnover(snapshot_data)
    if total_turnover <= 0 and callable(globals().get("get_market_total_turnover_from_fact_db")):
        total_turnover = _safe_float(globals()["get_market_total_turnover_from_fact_db"](trade_date))
    return total_turnover


def _fill_missing_total_turnover(snapshot, snapshot_data, trade_date):
    if not snapshot:
        return snapshot
    total_turnover = _safe_float(snapshot.get("total_turnover"))
    sector_turnover = _safe_float(snapshot.get("sector_turnover"))
    share = _safe_float(snapshot.get("turnover_share_pct"))
    if total_turnover > 0 or sector_turnover <= 0:
        return snapshot
    total_turnover = _total_turnover_from_payload_or_fact_db(snapshot_data, trade_date)
    if total_turnover <= 0:
        return snapshot
    updated = dict(snapshot)
    updated["total_turnover"] = round(total_turnover, 2)
    if share <= 0:
        updated["turnover_share_pct"] = round(sector_turnover / total_turnover * 100, 2)
    return updated


def _load_recent_sector_turnover_history_from_fact_db(target_date, sector_name, lookback_days=25, *, db_path=None):
    service_cls = globals().get("DatabaseService")
    if service_cls is None:
        return []
    try:
        if _postgres_only_runtime() and hasattr(service_cls, "fact_store_from_environment"):
            service = service_cls.fact_store_from_environment(db_path)
            checker = getattr(service, "is_postgres_backed", None)
            if not callable(checker) or not checker():
                return []
        elif _postgres_only_runtime() and hasattr(service_cls, "from_environment"):
            service = service_cls.from_environment(db_path)
            checker = getattr(service, "is_postgres_backed", None)
            if not callable(checker) or not checker():
                return []
        elif hasattr(service_cls, "fact_store_from_environment"):
            service = service_cls.fact_store_from_environment(db_path)
        elif hasattr(service_cls, "from_environment"):
            service = service_cls.from_environment(db_path)
        else:
            return []
        rows = service.query_mainline_turnover_series(
            _normalize_kline_date_str(target_date) or target_date,
            sector_name,
            window_days=lookback_days,
        )
    except Exception:
        return []
    normalized = []
    for row in rows or []:
        snapshot = extract_sector_turnover_snapshot({"sector_turnover_snapshot": row}, sector_name)
        if snapshot and str(snapshot.get("date") or "") < str(target_date):
            normalized.append(snapshot)
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


def load_recent_sector_turnover_history(target_date, sector_name, lookback_days=25, max_scan_days=60, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        if globals().get("DatabaseService") is None:
            if _postgres_only_runtime():
                return []
        else:
            db_history = _load_recent_sector_turnover_history_from_fact_db(
                target_date,
                sector_name,
                lookback_days=lookback_days,
            )
            if db_history and _postgres_only_runtime():
                return db_history
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
                db_history = _load_recent_sector_turnover_history_from_fact_db(
                    target_date,
                    sector_name,
                    lookback_days=lookback_days,
            )
            if db_history:
                return db_history
            if _postgres_only_runtime():
                return []

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
            snapshot = _fill_missing_total_turnover(snapshot, snapshot_data, cursor)
            if not snapshot:
                snapshot = _fetch_tushare_sector_turnover_snapshot(
                    cursor,
                    sector_name,
                    total_turnover=_total_turnover_from_payload_or_fact_db(snapshot_data, cursor),
                )
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
