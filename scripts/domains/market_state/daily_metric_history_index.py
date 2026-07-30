from __future__ import annotations

import datetime
import json
import os
import re
import traceback
from pathlib import Path

from daily_report_snapshot_io import LEDGER_MODE_FROZEN, _get_snapshot_path, load_data_snapshot

try:
    from storage.database_service import DatabaseService
except Exception:  # pragma: no cover - optional runtime dependency
    DatabaseService = None


def _parse_date(value):
    try:
        return datetime.datetime.strptime(str(value or ""), "%Y-%m-%d").date()
    except Exception:
        return None


def _previous_date(value):
    date_value = _parse_date(value)
    if not date_value:
        return ""
    return (date_value - datetime.timedelta(days=1)).strftime("%Y-%m-%d")


def _repo_root():
    return Path(__file__).resolve().parents[3]


def _extract_nested(payload, key, depth=0, max_depth=6):
    if payload is None or depth > max_depth:
        return None
    if isinstance(payload, dict):
        value = payload.get(key)
        if isinstance(value, dict):
            return value
        for nested in payload.values():
            if isinstance(nested, (dict, list)):
                found = _extract_nested(nested, key, depth + 1, max_depth)
                if found is not None:
                    return found
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, (dict, list)):
                found = _extract_nested(item, key, depth + 1, max_depth)
                if found is not None:
                    return found
    return None


def _extract_nested_list(payload, key, depth=0, max_depth=6):
    if payload is None or depth > max_depth:
        return []
    if isinstance(payload, dict):
        value = payload.get(key)
        if isinstance(value, list):
            return value
        for nested in payload.values():
            if isinstance(nested, (dict, list)):
                found = _extract_nested_list(nested, key, depth + 1, max_depth)
                if found:
                    return found
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, (dict, list)):
                found = _extract_nested_list(item, key, depth + 1, max_depth)
                if found:
                    return found
    return []


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return float(default)
        text = str(value).strip().replace("%", "").replace("亿", "").replace("pct", "")
        return float(text)
    except (TypeError, ValueError):
        return float(default)


def _text(value):
    return str(value or "").strip()


def _safe_int(value, default=0):
    try:
        if value in (None, ""):
            return int(default)
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return int(default)


def _leading_sectors_from_distribution(rows, limit=3):
    names = []
    for row in rows or []:
        name = str((row or {}).get("sector") or "").strip()
        if name and name not in names:
            names.append(name)
        if len(names) >= limit:
            break
    return "、".join(names)


def _leading_sectors_from_summary(summary):
    text = str(summary or "")
    match = re.search(r"主要集中在\s*([^。\n]+)", text)
    return match.group(1).strip(" ，,。") if match else ""


def _load_replay_snapshot_data(target_date):
    if os.environ.get("A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME") == "1":
        stack = "".join(traceback.format_stack(limit=12))
        raise RuntimeError(
            "PostgreSQL-only runtime attempted to read replay JSON snapshot "
            f"for {target_date}.\n{stack}"
        )
    path = _repo_root() / "snapshots" / "replay" / f"{target_date}_replay.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if isinstance(payload, dict) and "data" in payload:
        return payload.get("data")
    return payload if isinstance(payload, dict) else None


def _load_compact_replay_metric_snapshot(target_date):
    if os.environ.get("A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME") == "1":
        stack = "".join(traceback.format_stack(limit=12))
        raise RuntimeError(
            "PostgreSQL-only runtime attempted to read replay JSON snapshot "
            f"for {target_date}.\n{stack}"
        )
    path = _repo_root() / "snapshots" / "replay" / f"{target_date}_replay.json"
    snapshot_data, _ = _load_compact_snapshot_file(path)
    return snapshot_data


def _load_report_markdown(target_date):
    candidates = [
        _repo_root() / "reports" / "replay" / f"{target_date}_A股日报_完整版_replay.md",
        _repo_root() / "reports" / f"{target_date}_A股日报_完整版.md",
        _repo_root() / "reports" / "replay" / f"{target_date}_A股日报_执行摘要_replay.md",
        _repo_root() / "reports" / f"{target_date}_A股日报_执行摘要.md",
    ]
    for path in candidates:
        if not path.exists():
            continue
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            continue
    return ""


def _load_mainline_series_replay_data(target_date):
    if os.environ.get("A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME") == "1":
        stack = "".join(traceback.format_stack(limit=12))
        raise RuntimeError(
            "PostgreSQL-only runtime attempted to read replay mainline series JSON "
            f"for {target_date}.\n{stack}"
        )
    path = _repo_root() / "snap-ui" / "dist" / "data" / "snap-ui" / "mainline-series" / f"{target_date}-replay.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


_COMPACT_METRIC_HISTORY_KEYS = (
    "total_turnover",
    "market_overview",
    "market_stats",
    "sector_fund_flow",
    "current_mainline_history_record",
    "current_mainline_history_records",
    "mainline_history_record",
    "mainline_history_records",
    "recent_mainline_history",
    "current_sector_turnover_snapshot",
    "sector_turnover_snapshot",
    "sector_turnover_snapshots",
    "market_amount_yi",
    "total_amount_yi",
    "turnover_data",
    "mainline_turnover_summary",
    "new_high_feedback",
)
_DEFAULT_REBUILD_WINDOW_CACHE = {}


def _decode_json_value(value_text):
    return json.JSONDecoder().raw_decode(str(value_text or "").lstrip())[0]


def _decode_top_level_data_field_from_text(text, field_name):
    marker = f'\n    "{field_name}":'
    index = str(text or "").find(marker)
    if index < 0 and str(text or "").startswith(marker.lstrip("\n")):
        index = 0
    if index < 0:
        return None, False
    colon_index = str(text).find(":", index + len(marker))
    if colon_index < 0:
        return None, False
    try:
        return _decode_json_value(str(text)[colon_index + 1 :]), True
    except (json.JSONDecodeError, ValueError):
        return None, False


def _extract_top_level_data_fields_from_file(snapshot_path, field_names):
    wanted = {str(field_name or "").strip() for field_name in field_names or [] if str(field_name or "").strip()}
    found = {}
    if not wanted:
        return found

    collecting_key = ""
    value_lines = []
    try:
        with Path(snapshot_path).open("r", encoding="utf-8") as file_obj:
            for line in file_obj:
                if not collecting_key:
                    matched_key = ""
                    for field_name in wanted - set(found):
                        marker = f'"{field_name}":'
                        if line.startswith(f"    {marker}"):
                            matched_key = field_name
                            break
                    if not matched_key:
                        continue
                    collecting_key = matched_key
                    value_lines = [line.split(":", 1)[1]]
                else:
                    value_lines.append(line)
                try:
                    found[collecting_key] = _decode_json_value("".join(value_lines))
                except (json.JSONDecodeError, ValueError):
                    continue
                collecting_key = ""
                value_lines = []
                if wanted <= set(found):
                    break
    except OSError:
        return found
    return found


def _load_compact_snapshot_file(snapshot_path):
    if os.environ.get("A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME") == "1":
        stack = "".join(traceback.format_stack(limit=12))
        raise RuntimeError(
            "PostgreSQL-only runtime attempted to read JSON snapshot "
            f"for {snapshot_path}.\n{stack}"
        )

    snapshot_path = Path(snapshot_path)
    if not snapshot_path.exists():
        return None, None

    try:
        file_size = snapshot_path.stat().st_size
    except OSError:
        return None, None

    if file_size <= 32 * 1024 * 1024:
        with snapshot_path.open("r", encoding="utf-8") as f:
            snapshot = json.load(f)
        if isinstance(snapshot, dict) and "data" in snapshot:
            return snapshot.get("data"), snapshot.get("supplementary_perspective", "") or ""
        if isinstance(snapshot, dict):
            perspective = snapshot.get("supplementary_perspective", "") or ""
            ignored = {"supplementary_perspective", "perspective_updated_at", "saved_at", "mode", "date"}
            return {k: v for k, v in snapshot.items() if k not in ignored}, perspective
        return snapshot, ""

    head_size = min(file_size, 32 * 1024 * 1024)
    tail_size = min(file_size, 16 * 1024 * 1024)
    try:
        with snapshot_path.open("rb") as file_obj:
            head_text = file_obj.read(head_size).decode("utf-8", errors="replace")
            file_obj.seek(max(file_size - tail_size, 0))
            tail_text = file_obj.read(tail_size).decode("utf-8", errors="replace")
    except OSError:
        return None, None

    compact = {}
    missing_keys = []
    for key in _COMPACT_METRIC_HISTORY_KEYS:
        value, found = _decode_top_level_data_field_from_text(head_text, key)
        if not found:
            value, found = _decode_top_level_data_field_from_text(tail_text, key)
        if not found:
            missing_keys.append(key)
        else:
            compact[key] = value
    for key, value in _extract_top_level_data_fields_from_file(snapshot_path, missing_keys).items():
        compact[key] = value
    return compact if compact else None, ""


def _load_compact_metric_history_snapshot(target_date):
    snapshot_path = Path(_get_snapshot_path(target_date, mode=LEDGER_MODE_FROZEN))
    return _load_compact_snapshot_file(snapshot_path)


def load_compact_metric_history_snapshot(target_date):
    return _load_compact_metric_history_snapshot(target_date)


def _new_high_record_from_report_markdown(markdown, fallback_date):
    text = str(markdown or "")
    if not text:
        return {}
    date_pattern = re.escape(str(fallback_date or "").strip())
    table_match = re.search(
        rf"\|\s*{date_pattern}\s*\|\s*([0-9]+)\s*\|\s*([0-9.]+)%?\s*\|\s*[^|]*\|\s*([^|\n]+)\|",
        text,
    )
    if table_match:
        return {
            "trade_date": str(fallback_date or "").strip(),
            "new_high_count": _safe_int(table_match.group(1)),
            "all_a_share_pct": _safe_float(table_match.group(2)),
            "leading_sectors": table_match.group(3).strip(),
            "source_policy": "report_markdown.new_high_feedback",
        }
    summary_match = re.search(
        r"阶段新高\s*([0-9]+)\s*只，?占全A约\s*([0-9.]+)%[，,]\s*主要集中在\s*([^。\n]+)",
        text,
    )
    if summary_match:
        return {
            "trade_date": str(fallback_date or "").strip(),
            "new_high_count": _safe_int(summary_match.group(1)),
            "all_a_share_pct": _safe_float(summary_match.group(2)),
            "leading_sectors": summary_match.group(3).strip(),
            "source_policy": "report_markdown.new_high_feedback",
        }
    return {}


def _mainline_record_from_snapshot(snapshot_data, fallback_date):
    record = _extract_nested(snapshot_data, "current_mainline_history_record")
    if not record:
        record = _extract_nested(snapshot_data, "mainline_history_record")
    if not isinstance(record, dict):
        return {}
    primary = str(record.get("primary_mainline") or record.get("leading_line") or "").strip()
    if not primary:
        return {}
    row = dict(record)
    row["trade_date"] = str(row.get("date") or fallback_date or "").strip()
    row.setdefault("source_policy", row.get("source") or "snapshot_index")
    return row


def _recent_mainline_records_from_snapshot(snapshot_data):
    rows = []
    records = _extract_nested_list(snapshot_data, "recent_mainline_history")
    for record in records:
        if not isinstance(record, dict):
            continue
        primary = str(record.get("primary_mainline") or record.get("leading_line") or "").strip()
        trade_date = str(record.get("date") or record.get("trade_date") or "").strip()
        if not primary or not trade_date:
            continue
        row = dict(record)
        row["trade_date"] = trade_date
        row.setdefault("source_policy", row.get("source") or "snapshot_index.recent_mainline_history")
        rows.append(row)
    return rows


def _recent_mainline_records_from_series_snapshot(snapshot_data, fallback_date):
    if not isinstance(snapshot_data, dict):
        return []
    rows = []
    trade_date = str(fallback_date or "").strip()
    for row in snapshot_data.get("rows") or []:
        if not isinstance(row, dict):
            continue
        record_date = _text(row.get("date") or row.get("trade_date"))
        primary = _text(row.get("currentMainline") or row.get("sectorName"))
        if not record_date or not primary or record_date > trade_date:
            continue
        rows.append(
            {
                "trade_date": record_date,
                "primary_mainline": primary,
                "daily_attack_line": primary,
                "secondary_mainline": _text(row.get("secondaryMainline")),
                "competition_mainline": _text(row.get("competitionMainline")),
                "rotation_label": _text(row.get("stateCode")),
                "leading_line": primary,
                "state_code": _text(row.get("stateCode")),
                "market_state": _text(row.get("stateCode")),
                "confidence": 0.0,
                "rotation_summary": _text(row.get("sourceMessage")),
                "source_policy": "snap_ui.mainline_series_replay",
            }
        )
    return rows


def _turnover_record_from_trend_row(row):
    row = row or {}
    sector_name = str(row.get("cycle_mainline") or row.get("daily_attack_line") or row.get("sector_name") or "").strip()
    trade_date = str(row.get("date") or row.get("trade_date") or "").strip()
    if not trade_date or not sector_name:
        return {}
    return {
        "trade_date": trade_date,
        "primary_mainline": sector_name,
        "sector_turnover_yi": _safe_float(row.get("mainline_turnover") or row.get("sector_turnover")),
        "total_turnover_yi": _safe_float(row.get("market_turnover") or row.get("total_turnover")),
        "turnover_share_pct": _safe_float(row.get("share") or row.get("turnover_share_pct")),
        "matched_sector_names": [sector_name],
        "source_policy": "mainline_turnover_summary",
    }


def _turnover_records_from_snapshot(snapshot_data):
    records = []
    summary = _extract_nested(snapshot_data, "mainline_turnover_summary")
    if isinstance(summary, dict):
        for row in summary.get("turnover_share_trend_rows") or []:
            record = _turnover_record_from_trend_row(row)
            if record:
                records.append(record)
    return records


def _sector_turnover_record_from_snapshot(snapshot_data, fallback_date):
    snapshot = _extract_nested(snapshot_data, "current_sector_turnover_snapshot")
    if not snapshot:
        snapshot = _extract_nested(snapshot_data, "sector_turnover_snapshot")
    if not isinstance(snapshot, dict):
        return {}
    sector_name = str(snapshot.get("sector_name") or snapshot.get("primary_mainline") or "").strip()
    if not sector_name:
        return {}
    row = dict(snapshot)
    row["trade_date"] = str(row.get("date") or fallback_date or "").strip()
    row["primary_mainline"] = sector_name
    row.setdefault("sector_turnover_yi", row.get("sector_turnover"))
    row.setdefault("total_turnover_yi", row.get("total_turnover"))
    row.setdefault("source_policy", row.get("source") or "snapshot_index")
    return row


def _new_high_record_from_snapshot(snapshot_data, fallback_date):
    snapshot = _extract_nested(snapshot_data, "new_high_feedback")
    if not isinstance(snapshot, dict) or not snapshot.get("available"):
        return {}
    row = dict(snapshot)
    row["trade_date"] = str(row.get("trade_date") or row.get("date") or fallback_date or "").strip()
    if not str(row.get("leading_sectors") or "").strip():
        row["leading_sectors"] = (
            _leading_sectors_from_distribution(row.get("sector_distribution") or [])
            or _leading_sectors_from_summary(row.get("summary"))
        )
    row.setdefault("source_policy", row.get("source") or "snapshot_index")
    return row


def _market_total_record_from_snapshot(snapshot_data, fallback_date):
    if not isinstance(snapshot_data, dict):
        return {}
    total_turnover = snapshot_data.get("total_turnover")
    if total_turnover in (None, ""):
        market_overview = _extract_nested(snapshot_data, "market_overview")
        if isinstance(market_overview, dict):
            total_turnover = market_overview.get("total_turnover")
    if total_turnover in (None, ""):
        market_stats = _extract_nested(snapshot_data, "market_stats")
        if isinstance(market_stats, dict):
            total_turnover = (
                market_stats.get("total_turnover")
                or market_stats.get("total_amount_yi")
                or market_stats.get("amount_yi")
            )
    total_amount_yi = _safe_float(total_turnover)
    if total_amount_yi <= 0:
        return {}
    market_stats = _extract_nested(snapshot_data, "market_stats")
    stock_count = 0
    if isinstance(market_stats, dict):
        stock_count = _safe_int(market_stats.get("stock_count"))
        if not stock_count:
            stock_count = _safe_int(market_stats.get("up_count")) + _safe_int(market_stats.get("down_count"))
    return {
        "trade_date": str(fallback_date or "").strip(),
        "market_scope": "all_a",
        "total_amount_yi": total_amount_yi,
        "stock_count": stock_count,
        "source_policy": "snapshot.total_turnover",
    }


def _sector_fund_flow_records_from_snapshot(snapshot_data, fallback_date):
    sector_fund_flow = _extract_nested(snapshot_data, "sector_fund_flow")
    if not isinstance(sector_fund_flow, dict):
        return []
    records = []
    trade_date = str(fallback_date or "").strip()
    for direction, sign in (("inflow", 1), ("outflow", -1)):
        for row in sector_fund_flow.get(direction) or []:
            if not isinstance(row, dict):
                continue
            sector_name = str(row.get("name") or row.get("sector_name") or row.get("板块") or "").strip()
            if not sector_name:
                continue
            raw_value = row.get("zljlr")
            if raw_value in (None, ""):
                raw_value = row.get("net_inflow_yi", row.get("inflow"))
            value = _safe_float(raw_value)
            if direction == "outflow" and value > 0:
                value = -abs(value)
            elif direction == "inflow" and value < 0:
                value = abs(value) * sign
            records.append(
                {
                    "trade_date": trade_date,
                    "sector_name": sector_name,
                    "net_inflow_yi": value,
                    "source_policy": "snapshot.sector_fund_flow",
                }
            )
    return records


def _new_high_record_from_builder(build_new_high_feedback_fn, fallback_date):
    if not callable(build_new_high_feedback_fn):
        return {}
    try:
        snapshot = build_new_high_feedback_fn(fallback_date)
    except Exception:
        return {}
    return _new_high_record_from_snapshot({"new_high_feedback": snapshot}, fallback_date)


def _existing_new_high_record(service, trade_date):
    if service is None or not str(trade_date or "").strip():
        return {}
    try:
        rows = service.query_new_high_feedback_series(trade_date, window_days=1)
    except Exception:
        return {}
    for row in rows or []:
        if str((row or {}).get("trade_date") or (row or {}).get("date") or "").strip() == str(trade_date or "").strip():
            return dict(row or {})
    return {}


def _fallback_new_high_record(
    cursor,
    *,
    load_replay_snapshot_fn=None,
    load_report_markdown_fn=None,
    build_new_high_feedback_fn=None,
):
    replay_snapshot_data = load_replay_snapshot_fn(cursor) if callable(load_replay_snapshot_fn) else None
    new_high_row = _new_high_record_from_snapshot(replay_snapshot_data, cursor)
    if not new_high_row:
        new_high_row = _new_high_record_from_report_markdown(
            load_report_markdown_fn(cursor) if callable(load_report_markdown_fn) else "",
            cursor,
        )
    if not new_high_row:
        new_high_row = _new_high_record_from_builder(build_new_high_feedback_fn, cursor)
    return new_high_row


def _iter_scan_dates(end_date, *, candidate_dates=None, max_scan_days=60):
    end_text = str(end_date or "").strip()
    if candidate_dates:
        dates = sorted(
            {
                str(date or "").strip()
                for date in candidate_dates
                if str(date or "").strip() and str(date or "").strip() <= end_text
            },
            reverse=True,
        )
        for date in dates[: int(max_scan_days or 60)]:
            yield date
        return

    cursor = end_text
    scanned_days = 0
    while cursor and scanned_days < int(max_scan_days or 60):
        yield cursor
        scanned_days += 1
        cursor = _previous_date(cursor)


def ensure_daily_metric_history_index(
    *,
    end_date,
    window_days=25,
    max_scan_days=60,
    db_path=None,
    database_service_cls=None,
    load_snapshot_fn=None,
    load_replay_snapshot_fn=None,
    load_report_markdown_fn=None,
    build_new_high_feedback_fn=None,
    candidate_dates=None,
):
    using_default_snapshot_loader = load_snapshot_fn is None
    using_default_replay_loader = load_replay_snapshot_fn is None
    cache_key = None
    if using_default_snapshot_loader and using_default_replay_loader and not candidate_dates:
        cache_key = (
            db_path,
            str(end_date or "").strip(),
            int(window_days or 25),
            int(max_scan_days or 60),
        )
        cached = _DEFAULT_REBUILD_WINDOW_CACHE.get(cache_key)
        if cached is not None:
            return dict(cached)

    database_service_cls = database_service_cls or DatabaseService
    if database_service_cls is None:
        return {"indexed_count": 0, "dates": []}
    if hasattr(database_service_cls, "fact_store_from_environment"):
        service = database_service_cls.fact_store_from_environment(db_path)
    elif hasattr(database_service_cls, "from_environment"):
        service = database_service_cls.from_environment(db_path)
    else:
        return {"indexed_count": 0, "dates": []}
    load_snapshot_fn = load_snapshot_fn or _load_compact_metric_history_snapshot
    load_replay_snapshot_fn = load_replay_snapshot_fn or _load_compact_replay_metric_snapshot
    load_report_markdown_fn = load_report_markdown_fn or _load_report_markdown
    indexed_dates = []
    new_high_dates = []
    for cursor in _iter_scan_dates(end_date, candidate_dates=candidate_dates, max_scan_days=max_scan_days):
        if len(new_high_dates) >= int(window_days or 25):
            break
        snapshot_data, _ = load_snapshot_fn(cursor)
        indexed_any = False
        new_high_row = _existing_new_high_record(service, cursor)
        if new_high_row:
            new_high_dates.append(cursor)
        series_snapshot_data = _load_mainline_series_replay_data(cursor)
        if series_snapshot_data:
            for mainline_row in _recent_mainline_records_from_series_snapshot(series_snapshot_data, cursor):
                service.upsert_mainline_daily(mainline_row)
                indexed_any = True
        if snapshot_data:
            market_total_row = _market_total_record_from_snapshot(snapshot_data, cursor)
            if market_total_row:
                service.upsert_market_daily_total(market_total_row)
                indexed_any = True
            for sector_flow_row in _sector_fund_flow_records_from_snapshot(snapshot_data, cursor):
                service.upsert_sector_fund_flow_daily(sector_flow_row)
                indexed_any = True
            for mainline_row in _recent_mainline_records_from_snapshot(snapshot_data):
                service.upsert_mainline_daily(mainline_row)
                indexed_any = True
            mainline_row = _mainline_record_from_snapshot(snapshot_data, cursor)
            if mainline_row:
                service.upsert_mainline_daily(mainline_row)
                indexed_any = True
            turnover_rows = _turnover_records_from_snapshot(snapshot_data)
            turnover_row = _sector_turnover_record_from_snapshot(snapshot_data, cursor)
            if turnover_row:
                turnover_rows.append(turnover_row)
            for row in turnover_rows:
                service.upsert_mainline_turnover_daily(row)
                indexed_any = True
            if not new_high_row:
                new_high_row = _new_high_record_from_snapshot(snapshot_data, cursor)
            if new_high_row:
                service.upsert_new_high_feedback_daily(new_high_row)
                indexed_any = True

        if not new_high_row:
            new_high_row = _fallback_new_high_record(
                cursor,
                load_replay_snapshot_fn=load_replay_snapshot_fn,
                load_report_markdown_fn=load_report_markdown_fn,
                build_new_high_feedback_fn=build_new_high_feedback_fn,
            )
        if new_high_row:
            service.upsert_new_high_feedback_daily(new_high_row)
            indexed_any = True
            new_high_dates.append(cursor)
        if indexed_any:
            indexed_dates.append(cursor)
    result = {"indexed_count": len(indexed_dates), "dates": sorted(indexed_dates)}
    if cache_key is not None:
        _DEFAULT_REBUILD_WINDOW_CACHE[cache_key] = dict(result)
    return result


__all__ = ["ensure_daily_metric_history_index", "load_compact_metric_history_snapshot"]
