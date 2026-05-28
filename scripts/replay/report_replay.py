from pathlib import Path

__all__ = [
    "build_replay_snapshot_contract",
    "build_replay_report_outputs_contract",
    "replay_from_snapshot",
]

_MISSING = object()


def _load_default_mainline_helpers():
    from domains.market_state.mainline_history_runtime import (
        build_mainline_history_record,
        load_recent_mainline_history,
    )
    from domains.market_state.mainline_turnover_summary_runtime import build_mainline_turnover_summary
    from domains.market_state.sector_turnover_history_runtime import load_recent_sector_turnover_history
    from input.tushare_runtime import (
        get_new_high_feedback_from_tushare_first,
        get_price_band_style_series_from_tushare_first,
        get_wind_a_from_tushare_first,
    )
    from market_data.tushare_market_activity_service import fetch_tushare_open_trade_dates
    from input.ths_sector_runtime import get_sector_turnover_snapshot_from_ths
    from research.market_research_runtime import (
        _fill_sector_snapshot_total_turnover,
        _has_resolved_mainline_turnover_summary,
        _mainline_turnover_summary_conflicts_with_current_record,
        _resolve_effective_total_turnover,
    )
    from research.market_research_support import (
        get_market_daily_total_from_fact_db_runtime,
        get_market_total_turnover_from_fact_db_runtime,
        get_turnover_rank_from_fact_db_runtime,
    )
    from storage.database_service import DatabaseService

    fact_db_path = Path(__file__).resolve().parents[2] / "data" / "cloudflare_free_daily.db"

    def _query_new_high_feedback_series(end_date, window_days=25):
        service = DatabaseService.sqlite_d1_compatible(fact_db_path)
        return service.query_new_high_feedback_series(end_date, window_days=window_days)

    return {
        "_use_default_query_new_high_feedback_series": True,
        "build_mainline_history_record": build_mainline_history_record,
        "load_recent_mainline_history": load_recent_mainline_history,
        "get_sector_turnover_snapshot_from_ths": get_sector_turnover_snapshot_from_ths,
        "load_recent_sector_turnover_history": load_recent_sector_turnover_history,
        "build_mainline_turnover_summary": build_mainline_turnover_summary,
        "fill_sector_snapshot_total_turnover": _fill_sector_snapshot_total_turnover,
        "has_resolved_mainline_turnover_summary": _has_resolved_mainline_turnover_summary,
        "mainline_turnover_summary_conflicts_with_current_record": _mainline_turnover_summary_conflicts_with_current_record,
        "resolve_effective_total_turnover": _resolve_effective_total_turnover,
        "get_market_daily_total_from_fact_db": get_market_daily_total_from_fact_db_runtime,
        "get_market_total_turnover_from_fact_db": get_market_total_turnover_from_fact_db_runtime,
        "get_turnover_rank_from_fact_db": get_turnover_rank_from_fact_db_runtime,
        "get_wind_a_from_tushare": get_wind_a_from_tushare_first,
        "get_new_high_feedback_from_tushare": lambda target_date=None, **kwargs: get_new_high_feedback_from_tushare_first(
            target_date=target_date,
            db_path=fact_db_path,
            fetch_tushare_open_trade_dates_fn=fetch_tushare_open_trade_dates,
            **kwargs,
        ),
        "query_new_high_feedback_series": _query_new_high_feedback_series,
        "get_price_band_style_series_from_tushare": get_price_band_style_series_from_tushare_first,
    }


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


def replay_from_snapshot(target_date, refresh_sources=None, *, helpers=None):
    previous = _install_runtime_bindings(helpers or {})
    try:
        return _replay_from_snapshot_legacy_body(target_date, refresh_sources=refresh_sources)
    finally:
        _restore_runtime_bindings(previous)


def _append_log(logs, step, status, message, **details):
    logs.append(
        {
            "module": "replay.report_replay",
            "step": step,
            "status": status,
            "message": message,
            "details": details,
        }
    )


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _hoist_report_analysis_atoms(snapshot_data):
    if not isinstance(snapshot_data, dict):
        return snapshot_data

    analysis = snapshot_data.get("analysis", {}) or {}
    if not isinstance(analysis, dict):
        analysis = {}

    if not snapshot_data.get("current_mainline_history_record") and snapshot_data.get("mainline_history_record"):
        snapshot_data["current_mainline_history_record"] = snapshot_data.get("mainline_history_record")
    if not snapshot_data.get("current_mainline_history_record") and analysis.get("mainline_history_record"):
        snapshot_data["current_mainline_history_record"] = analysis.get("mainline_history_record")

    if not snapshot_data.get("current_sector_turnover_snapshot") and snapshot_data.get("sector_turnover_snapshot"):
        snapshot_data["current_sector_turnover_snapshot"] = snapshot_data.get("sector_turnover_snapshot")
    if not snapshot_data.get("current_sector_turnover_snapshot") and analysis.get("sector_turnover_snapshot"):
        snapshot_data["current_sector_turnover_snapshot"] = analysis.get("sector_turnover_snapshot")

    if not snapshot_data.get("mainline_turnover_summary") and analysis.get("mainline_turnover_summary"):
        snapshot_data["mainline_turnover_summary"] = analysis.get("mainline_turnover_summary")

    return snapshot_data


def _record_has_mainline(record):
    if not isinstance(record, dict):
        return False
    return bool(str(record.get("primary_mainline") or record.get("leading_line") or "").strip())


def _date_text(record):
    return str((record or {}).get("date") or (record or {}).get("trade_date") or "").strip()


def _mainline_text(record):
    return str((record or {}).get("primary_mainline") or (record or {}).get("leading_line") or "").strip()


def _history_is_short(history, expected_count=25):
    try:
        count = max(int(expected_count or 0), 1)
    except (TypeError, ValueError):
        count = 25
    return len([item for item in history or [] if isinstance(item, dict)]) < count


def _daily_attack_text(record, fallback=""):
    return str((record or {}).get("daily_attack_line") or (record or {}).get("attack_line") or fallback or "").strip()


def _load_recent_mainline_history_for_cycle_calendar(loader, target_date):
    try:
        return loader(target_date, lookback_days=25, max_scan_days=60)
    except TypeError as exc:
        if "max_scan_days" not in str(exc):
            raise
        return loader(target_date, lookback_days=25)


def _load_recent_turnover_by_daily_mainline(loader, recent_mainline_history, target_date):
    records_by_sector = {}
    record_by_date = {}
    for record in recent_mainline_history or []:
        record_date = _date_text(record)
        mainline = _mainline_text(record)
        if not record_date or not mainline:
            continue
        records_by_sector.setdefault(mainline, set()).add(record_date)
        record_by_date[record_date] = record

    rows_by_date = {}
    for mainline, expected_dates in records_by_sector.items():
        try:
            rows = loader(target_date, mainline, lookback_days=25) or []
        except TypeError:
            rows = loader(target_date, mainline) or []
        except Exception:
            rows = []
        for row in rows or []:
            item = dict(row or {})
            row_date = _date_text(item)
            if row_date not in expected_dates:
                continue
            record = record_by_date.get(row_date) or {}
            item["date"] = row_date
            item["cycle_mainline"] = mainline
            item["daily_attack_line"] = _daily_attack_text(record, mainline) or mainline
            rows_by_date[row_date] = item
    return [rows_by_date[date] for date in sorted(rows_by_date)]


def _fill_turnover_placeholders_for_mainline_history(recent_sector_turnover_history, recent_mainline_history):
    rows_by_date = {
        _date_text(row): dict(row or {})
        for row in recent_sector_turnover_history or []
        if _date_text(row)
    }
    completed = []
    for record in recent_mainline_history or []:
        record_date = _date_text(record)
        mainline = _mainline_text(record)
        if not record_date or not mainline:
            continue
        row = rows_by_date.get(record_date)
        if row:
            row["date"] = record_date
            row["cycle_mainline"] = mainline
            row["daily_attack_line"] = _daily_attack_text(record, mainline) or mainline
            completed.append(row)
            continue
        completed.append(
            {
                "date": record_date,
                "sector_name": mainline,
                "cycle_mainline": mainline,
                "daily_attack_line": _daily_attack_text(record, mainline) or mainline,
                "sector_turnover": 0.0,
                "total_turnover": 0.0,
                "turnover_share_pct": 0.0,
                "source_status": "history_missing",
            }
        )
    return completed[-25:]


def _trend_row_date(row):
    return str((row or {}).get("date") or (row or {}).get("trade_date") or "").strip()


def _new_high_feedback_needs_refresh(feedback, target_date):
    if not isinstance(feedback, dict):
        return True
    rows = [row for row in feedback.get("trend_rows") or [] if isinstance(row, dict)]
    if len(rows) < 25:
        return True
    target = str(target_date or "").strip()
    if target and not any(_trend_row_date(row) == target for row in rows):
        return True
    return False


def _same_day_new_high_fact_differs(feedback, target_date, helpers=None):
    helpers = helpers or {}
    if helpers.get("_use_default_query_new_high_feedback_series") and not helpers.get("_allow_default_new_high_fact_diff_check"):
        return False
    query = helpers.get("query_new_high_feedback_series")
    if not callable(query):
        return False
    try:
        rows = query(target_date, window_days=1) or []
    except Exception:
        return False
    target = str(target_date or "").strip()
    for row in rows:
        row_date = str((row or {}).get("trade_date") or (row or {}).get("date") or "").strip()
        if row_date != target:
            continue
        fact_count = row.get("new_high_count")
        fact_pct = row.get("all_a_share_pct")
        return (
            int(_safe_float(fact_count, -1)) != int(_safe_float(feedback.get("new_high_count"), -1))
            or round(_safe_float(fact_pct, -1), 2) != round(_safe_float(feedback.get("all_a_share_pct"), -1), 2)
        )
    return False


def _replay_new_high_feedback_candidate(target_date, helpers=None):
    helpers = helpers or {}
    loader = helpers.get("load_replay_snapshot_data")
    if not callable(loader):
        try:
            from domains.market_state.daily_metric_history_index import _load_replay_snapshot_data as loader
        except Exception:  # pragma: no cover - optional local replay snapshot
            loader = None
    if not callable(loader):
        return {}
    try:
        replay_data = loader(target_date)
    except Exception:
        return {}
    if not isinstance(replay_data, dict):
        return {}
    feedback = replay_data.get("new_high_feedback")
    if isinstance(feedback, dict):
        return feedback
    nested = replay_data.get("data")
    if isinstance(nested, dict) and isinstance(nested.get("new_high_feedback"), dict):
        return nested.get("new_high_feedback")
    return {}


def _load_replay_snapshot_candidate(target_date, helpers=None):
    helpers = helpers or {}
    loader = helpers.get("load_replay_snapshot_data")
    if not callable(loader):
        try:
            from domains.market_state.daily_metric_history_index import _load_replay_snapshot_data as loader
        except Exception:  # pragma: no cover - optional local replay snapshot
            loader = None
    if not callable(loader):
        return {}
    try:
        replay_data = loader(target_date)
    except Exception:
        return {}
    return replay_data if isinstance(replay_data, dict) else {}


def _use_replay_new_high_feedback_if_complete(snapshot_data, target_date, safe_float, helpers=None):
    feedback = _replay_new_high_feedback_candidate(target_date, helpers=helpers)
    if not isinstance(feedback, dict) or _new_high_feedback_needs_refresh(feedback, target_date):
        return False
    if _same_day_new_high_fact_differs(feedback, target_date, helpers=helpers):
        return False
    snapshot_data["new_high_feedback"] = feedback
    data_status = snapshot_data.setdefault("data_status", {})
    step_status = snapshot_data.setdefault("step_status", {})
    data_status["创新高趋势反馈"] = bool(feedback.get("available", True))
    step_status["创新高趋势反馈获取"] = bool(feedback.get("available", True))
    _mark_replayed_step_success(snapshot_data, "创新高趋势反馈获取", safe_float)
    _replace_request_module_log(
        snapshot_data,
        module="domains.market_activity.request",
        step="request.new_high_feedback",
        status="success",
        message="已复用本地 replay 阶段新高趋势反馈",
        provider=feedback.get("source") or "replay.new_high_feedback",
        target_keys=["new_high_feedback"],
        new_high_count=feedback.get("new_high_count", 0),
        trend_row_count=len(feedback.get("trend_rows") or []),
    )
    _refresh_request_diagnostics(snapshot_data)
    return True


def _ensure_replay_new_high_feedback(snapshot_data, target_date, safe_float, helpers=None):
    if not isinstance(snapshot_data, dict):
        return snapshot_data
    if "new_high_feedback" not in snapshot_data:
        return snapshot_data
    helpers = helpers or {}
    if (
        not _new_high_feedback_needs_refresh(snapshot_data.get("new_high_feedback"), target_date)
        and not _same_day_new_high_fact_differs(snapshot_data.get("new_high_feedback"), target_date, helpers=helpers)
    ):
        return snapshot_data
    if _use_replay_new_high_feedback_if_complete(snapshot_data, target_date, safe_float, helpers=helpers):
        return snapshot_data
    fetcher = helpers.get("get_new_high_feedback_from_tushare")
    if not callable(fetcher):
        return snapshot_data
    try:
        feedback = fetcher(target_date=target_date) or {}
    except TypeError as error:
        if "target_date" not in str(error):
            raise
        feedback = fetcher(target_date) or {}
    except Exception as error:
        data_status = snapshot_data.setdefault("data_status", {})
        step_status = snapshot_data.setdefault("step_status", {})
        data_status["创新高趋势反馈"] = False
        step_status["创新高趋势反馈获取"] = False
        _replace_request_module_log(
            snapshot_data,
            module="domains.market_activity.request",
            step="request.new_high_feedback",
            status="degraded",
            message="阶段新高趋势反馈刷新失败，保留快照内已有数据",
            provider="tushare.stk_factor_pro.topdays",
            target_keys=["new_high_feedback"],
            error=str(error),
        )
        _refresh_request_diagnostics(snapshot_data)
        return snapshot_data
    if not isinstance(feedback, dict) or not feedback.get("trend_rows"):
        return snapshot_data
    if _new_high_feedback_needs_refresh(feedback, target_date):
        return snapshot_data

    snapshot_data["new_high_feedback"] = feedback
    data_status = snapshot_data.setdefault("data_status", {})
    step_status = snapshot_data.setdefault("step_status", {})
    data_status["创新高趋势反馈"] = bool(feedback.get("available", True))
    step_status["创新高趋势反馈获取"] = bool(feedback.get("available", True))
    _mark_replayed_step_success(snapshot_data, "创新高趋势反馈获取", safe_float)
    _replace_request_module_log(
        snapshot_data,
        module="domains.market_activity.request",
        step="request.new_high_feedback",
        status="success",
        message="已刷新阶段新高趋势反馈",
        provider=feedback.get("source") or "tushare.stk_factor_pro.topdays",
        target_keys=["new_high_feedback"],
        new_high_count=feedback.get("new_high_count", 0),
        trend_row_count=len(feedback.get("trend_rows") or []),
    )
    _refresh_request_diagnostics(snapshot_data)
    return snapshot_data


def _price_band_style_series_needs_refresh(series, target_date):
    if not isinstance(series, dict):
        return True
    rows = [row for row in series.get("rows") or [] if isinstance(row, dict)]
    if len(rows) < 25:
        return True
    target = str(target_date or "").strip()
    if target and not any(_trend_row_date(row) == target for row in rows):
        return True
    return False


def _ensure_replay_price_band_style_series(snapshot_data, target_date, safe_float, helpers=None):
    if not isinstance(snapshot_data, dict):
        return snapshot_data
    if not _price_band_style_series_needs_refresh(snapshot_data.get("price_band_style_series"), target_date):
        return snapshot_data
    helpers = helpers or {}
    fetcher = helpers.get("get_price_band_style_series_from_tushare")
    if not callable(fetcher):
        return snapshot_data
    try:
        series = fetcher(target_date=target_date) or {}
    except TypeError as error:
        if "target_date" not in str(error):
            raise
        series = fetcher(target_date) or {}
    if not isinstance(series, dict) or not series.get("rows"):
        return snapshot_data

    snapshot_data["price_band_style_series"] = series
    data_status = snapshot_data.setdefault("data_status", {})
    step_status = snapshot_data.setdefault("step_status", {})
    data_status["价格带风格趋势"] = bool(series.get("available", True))
    step_status["价格带风格趋势获取"] = bool(series.get("available", True))
    _mark_replayed_step_success(snapshot_data, "价格带风格趋势获取", safe_float)
    _replace_request_module_log(
        snapshot_data,
        module="input.runtime",
        step="request.price_band_style_series",
        status="success",
        message="已刷新价格带风格趋势",
        provider=series.get("source") or "storage.price_band_style_daily",
        target_keys=["price_band_style_series"],
        row_count=len(series.get("rows") or []),
    )
    _refresh_request_diagnostics(snapshot_data)
    return snapshot_data


def _build_replay_sector_attack_evidence_rows(snapshot_data, market_research_snapshot=None):
    try:
        from research.market_research_runtime import _build_sector_attack_evidence_rows
    except Exception:
        return None
    market_research_snapshot = market_research_snapshot or {}
    return _build_sector_attack_evidence_rows(
        snapshot_data,
        snapshot_data.get("current_sector_turnover_snapshot")
        or market_research_snapshot.get("current_sector_turnover_snapshot")
        or {},
        snapshot_data.get("recent_sector_turnover_history")
        or market_research_snapshot.get("recent_sector_turnover_history")
        or [],
        snapshot_data.get("total_turnover") or (market_research_snapshot.get("observation") or {}).get("turnover", 0),
    )


def _summary_has_attack_evidence(summary):
    if not isinstance(summary, dict):
        return False
    attack_summary = summary.get("mainline_attack_evidence_summary")
    return isinstance(attack_summary, dict) and bool(str(attack_summary.get("attack_state") or "").strip())


def _expected_mainline_by_date(recent_mainline_history, current_record, target_date):
    expected = {}
    for record in recent_mainline_history or []:
        record_date = _date_text(record)
        mainline = _mainline_text(record)
        if record_date and mainline:
            expected[record_date] = mainline
    current_mainline = _mainline_text(current_record)
    if target_date and current_mainline:
        expected[str(target_date)] = current_mainline
    return expected


def _summary_trend_rows_misaligned(summary, expected_by_date):
    if not isinstance(summary, dict):
        return True
    rows = [row for row in summary.get("turnover_share_trend_rows") or [] if isinstance(row, dict)]
    if not rows:
        return True
    rows_by_date = {_date_text(row): row for row in rows if _date_text(row)}
    for row_date, expected_mainline in (expected_by_date or {}).items():
        if row_date not in rows_by_date:
            return True
        row = rows_by_date[row_date]
        cycle_mainline = str(row.get("cycle_mainline") or row.get("primary_mainline") or row.get("sector_name") or "").strip()
        daily_attack_line = str(row.get("daily_attack_line") or row.get("attack_line") or cycle_mainline or "").strip()
        if cycle_mainline and cycle_mainline != expected_mainline:
            return True
        if daily_attack_line and daily_attack_line != expected_mainline:
            return True
    return False


def _sector_history_misaligned(recent_sector_turnover_history, expected_by_date):
    rows_by_date = {_date_text(row): row for row in recent_sector_turnover_history or [] if _date_text(row)}
    if not expected_by_date:
        return False
    for row_date, expected_mainline in expected_by_date.items():
        row = rows_by_date.get(row_date)
        if not row:
            return True
        row_mainline = str(
            row.get("cycle_mainline")
            or row.get("primary_mainline")
            or row.get("sector_name")
            or row.get("turnover_scope_label")
            or ""
        ).strip()
        if row_mainline and row_mainline != expected_mainline:
            return True
    return False


def _ensure_report_mainline_atoms(snapshot_data, target_date, helpers=None):
    if not isinstance(snapshot_data, dict):
        return snapshot_data
    helpers = {**_load_default_mainline_helpers(), **(helpers or {})}
    market_research_snapshot = snapshot_data.get("market_research_snapshot") or snapshot_data.get("analysis") or {}

    if not _record_has_mainline(snapshot_data.get("current_mainline_history_record")) and callable(helpers.get("build_mainline_history_record")):
        built_record = helpers["build_mainline_history_record"](
            target_date,
            market_research_snapshot,
        )
        if _record_has_mainline(built_record):
            snapshot_data["current_mainline_history_record"] = built_record
        else:
            snapshot_data.pop("current_mainline_history_record", None)

    current_record = snapshot_data.get("current_mainline_history_record") or {}
    current_mainline_name = str(
        current_record.get("primary_mainline")
        or current_record.get("leading_line")
        or ""
    ).strip()

    if (
        (
            not snapshot_data.get("recent_mainline_history")
            or _history_is_short(snapshot_data.get("recent_mainline_history"), 24)
        )
        and callable(helpers.get("load_recent_mainline_history"))
    ):
        loaded_history = _load_recent_mainline_history_for_cycle_calendar(
            helpers["load_recent_mainline_history"],
            target_date,
        )
        if loaded_history:
            snapshot_data["recent_mainline_history"] = loaded_history

    observation = market_research_snapshot.get("observation", {}) if isinstance(market_research_snapshot, dict) else {}
    if callable(helpers.get("resolve_effective_total_turnover")):
        total_turnover = helpers["resolve_effective_total_turnover"](
            snapshot_data,
            observation,
            target_date,
            get_market_total_turnover_from_fact_db=helpers.get("get_market_total_turnover_from_fact_db"),
        )
    else:
        total_turnover = snapshot_data.get("total_turnover")
        if total_turnover in (None, ""):
            total_turnover = observation.get("turnover", 0.0) if isinstance(observation, dict) else 0.0
    if _safe_float(total_turnover) > 0:
        snapshot_data["total_turnover"] = round(_safe_float(total_turnover), 2)

    if callable(helpers.get("fill_sector_snapshot_total_turnover")):
        snapshot_data["current_sector_turnover_snapshot"] = helpers["fill_sector_snapshot_total_turnover"](
            snapshot_data.get("current_sector_turnover_snapshot") or {},
            total_turnover,
        )

    if (
        not snapshot_data.get("current_sector_turnover_snapshot")
        and current_mainline_name
        and callable(helpers.get("get_sector_turnover_snapshot_from_ths"))
    ):
        snapshot_data["current_sector_turnover_snapshot"] = helpers["get_sector_turnover_snapshot_from_ths"](
            current_mainline_name,
            target_date=target_date,
            total_turnover=total_turnover,
        )

    recent_mainline_history = snapshot_data.get("recent_mainline_history") or []
    expected_by_date = _expected_mainline_by_date(
        recent_mainline_history,
        current_record,
        target_date,
    )
    expected_history_by_date = {
        date: mainline
        for date, mainline in expected_by_date.items()
        if str(date) < str(target_date)
    }
    recent_sector_turnover_history = snapshot_data.get("recent_sector_turnover_history") or []
    if current_mainline_name and callable(helpers.get("load_recent_sector_turnover_history")):
        should_reload_sector_history = (
            not recent_sector_turnover_history
            or _sector_history_misaligned(recent_sector_turnover_history, expected_history_by_date)
        )
        if should_reload_sector_history:
            daily_history = _load_recent_turnover_by_daily_mainline(
                helpers["load_recent_sector_turnover_history"],
                recent_mainline_history,
                target_date,
            )
            if daily_history:
                snapshot_data["recent_sector_turnover_history"] = daily_history
                recent_sector_turnover_history = daily_history
            elif not recent_sector_turnover_history:
                snapshot_data["recent_sector_turnover_history"] = helpers["load_recent_sector_turnover_history"](
                    target_date,
                    current_mainline_name,
                    lookback_days=25,
                )
                recent_sector_turnover_history = snapshot_data.get("recent_sector_turnover_history") or []
    if recent_mainline_history:
        snapshot_data["recent_sector_turnover_history"] = _fill_turnover_placeholders_for_mainline_history(
            recent_sector_turnover_history,
            recent_mainline_history,
        )

    summary_resolved = True
    if callable(helpers.get("has_resolved_mainline_turnover_summary")):
        summary_resolved = helpers["has_resolved_mainline_turnover_summary"](
            snapshot_data.get("mainline_turnover_summary")
        )
    should_rebuild_for_history_alignment = _summary_trend_rows_misaligned(
        snapshot_data.get("mainline_turnover_summary"),
        expected_by_date,
    )

    sector_attack_evidence_rows = _build_replay_sector_attack_evidence_rows(snapshot_data, market_research_snapshot)
    should_rebuild_for_attack_evidence = bool(
        sector_attack_evidence_rows
        and not _summary_has_attack_evidence(snapshot_data.get("mainline_turnover_summary"))
    )
    should_rebuild_for_current_record_conflict = False
    if callable(helpers.get("mainline_turnover_summary_conflicts_with_current_record")):
        should_rebuild_for_current_record_conflict = helpers["mainline_turnover_summary_conflicts_with_current_record"](
            snapshot_data.get("mainline_turnover_summary"),
            snapshot_data.get("current_mainline_history_record") or {},
        )

    if (
        not summary_resolved
        or should_rebuild_for_attack_evidence
        or should_rebuild_for_history_alignment
        or should_rebuild_for_current_record_conflict
    ) and callable(helpers.get("build_mainline_turnover_summary")):
        build_kwargs = {
            "target_date": target_date,
            "current_mainline_history_record": snapshot_data.get("current_mainline_history_record") or {},
            "recent_mainline_history": snapshot_data.get("recent_mainline_history") or [],
            "current_sector_turnover_snapshot": snapshot_data.get("current_sector_turnover_snapshot") or {},
            "recent_sector_turnover_history": snapshot_data.get("recent_sector_turnover_history") or [],
        }
        if sector_attack_evidence_rows:
            build_kwargs["sector_attack_evidence_rows"] = sector_attack_evidence_rows
        snapshot_data["mainline_turnover_summary"] = helpers["build_mainline_turnover_summary"](
            **build_kwargs
        )
        if isinstance(market_research_snapshot, dict):
            market_research_snapshot["mainline_turnover_summary"] = snapshot_data["mainline_turnover_summary"]
            snapshot_data["market_research_snapshot"] = market_research_snapshot

    return snapshot_data


def _ensure_replay_capital_intent_atoms(snapshot_data):
    if not isinstance(snapshot_data, dict):
        return snapshot_data

    market_research_snapshot = snapshot_data.get("market_research_snapshot")
    if not isinstance(market_research_snapshot, dict):
        return snapshot_data

    try:
        from research.market_research_runtime import (
            _derive_capital_intent_breakdown,
            _derive_lhb_capital_intent,
        )
    except Exception:
        return snapshot_data

    mainline_turnover_summary = (
        snapshot_data.get("mainline_turnover_summary")
        or market_research_snapshot.get("mainline_turnover_summary")
        or {}
    )
    current_record = snapshot_data.get("current_mainline_history_record") or market_research_snapshot.get("current_mainline_history_record") or {}
    current_mainline_name = str(
        current_record.get("primary_mainline")
        or current_record.get("leading_line")
        or mainline_turnover_summary.get("current_mainline")
        or ""
    ).strip()

    sector_attack_evidence_rows = _build_replay_sector_attack_evidence_rows(snapshot_data, market_research_snapshot)
    lhb_capital_status, capital_conclusion = _derive_lhb_capital_intent(snapshot_data, current_mainline_name)
    capital_intent_breakdown, capital_conclusion = _derive_capital_intent_breakdown(
        mainline_turnover_summary,
        sector_attack_evidence_rows,
        lhb_capital_status,
        capital_conclusion,
    )

    if capital_intent_breakdown:
        market_research_snapshot["capital_intent_breakdown"] = capital_intent_breakdown
        market_research_snapshot["lhb_capital_status"] = lhb_capital_status
        market_research_snapshot["capital_conclusion"] = capital_conclusion
    elif lhb_capital_status or capital_conclusion:
        market_research_snapshot["lhb_capital_status"] = lhb_capital_status or market_research_snapshot.get("lhb_capital_status") or {}
        market_research_snapshot["capital_conclusion"] = capital_conclusion or market_research_snapshot.get("capital_conclusion") or {}

    snapshot_data["market_research_snapshot"] = market_research_snapshot
    return snapshot_data


def _mark_replayed_step_success(snapshot_data, step_name, safe_float):
    timer_summary = snapshot_data.setdefault("timer_summary", {}) or {}
    raw_steps = timer_summary.get("steps", []) or []
    normalized_steps = []
    matched = False

    for item in raw_steps:
        if not isinstance(item, (list, tuple)) or len(item) < 3:
            continue
        name = str(item[0] or "").strip()
        elapsed = safe_float(item[1])
        cumulative = safe_float(item[2])
        base_name = name.replace("(失败)", "").replace("(回补)", "").replace("(空)", "").strip()
        if ":" in base_name and base_name.startswith("步骤"):
            base_name = base_name.split(":", 1)[1].strip()
        if base_name == step_name:
            name = step_name
            matched = True
        normalized_steps.append([name, elapsed, cumulative])

    if not matched:
        prev_cumulative = normalized_steps[-1][2] if normalized_steps else 0.0
        normalized_steps.append([step_name, 0.0, prev_cumulative])

    timer_summary["steps"] = normalized_steps
    if "total_time" not in timer_summary:
        timer_summary["total_time"] = normalized_steps[-1][2] if normalized_steps else 0.0
    snapshot_data["timer_summary"] = timer_summary


def _replace_request_module_log(snapshot_data, *, module, step, status, message, **details):
    logs = snapshot_data.setdefault("module_logs", [])
    replacement = {
        "module": module,
        "step": step,
        "status": status,
        "message": message,
        "details": details,
    }
    replaced = False
    normalized_logs = []
    for item in logs or []:
        if isinstance(item, dict) and item.get("step") == step:
            if not replaced:
                normalized_logs.append(replacement)
                replaced = True
            continue
        normalized_logs.append(item)
    if not replaced:
        normalized_logs.append(replacement)
    snapshot_data["module_logs"] = normalized_logs
    return replacement


def _normalize_replay_quote_code(raw_code):
    code = str(raw_code or "").strip()
    for suffix in (".SZ", ".SS", ".SH", ".BJ"):
        if code.upper().endswith(suffix):
            code = code[: -len(suffix)]
            break
    lower_code = code.lower()
    for prefix in ("sz", "sh", "bj"):
        if lower_code.startswith(prefix):
            code = code[len(prefix):]
            break
    digits = "".join(ch for ch in code if ch.isdigit())
    return digits.zfill(6) if digits else ""


def _normalize_replay_stock_info_map(stock_full_info):
    normalized = {}
    for raw_code, info in (stock_full_info or {}).items():
        code = _normalize_replay_quote_code(raw_code)
        if code and isinstance(info, dict):
            normalized[code] = dict(info)
    return normalized


def _patch_replay_quote_fields(row, info):
    patched = dict(row or {})
    info = info or {}
    if not patched.get("name"):
        name_from_info = info.get("name") or info.get("名称", "")
        if name_from_info:
            patched["name"] = name_from_info
    for target_key, source_key in (
        ("change_pct", "change_pct"),
        ("high", "high"),
        ("low", "low"),
        ("open", "open"),
        ("close", "close"),
        ("zt_status", "zt_status"),
    ):
        value = info.get(source_key)
        if value not in (None, ""):
            patched[target_key] = value
    return patched


def _collect_replay_quote_codes(snapshot_data):
    codes = set()
    for key in ("hot_rank_top30", "turnover_rank", "turnover_over_100b", "lhb_net_buy_top10", "lhb_net_sell_top10", "lianban_data"):
        for item in snapshot_data.get(key) or []:
            if not isinstance(item, dict):
                continue
            code = _normalize_replay_quote_code(
                item.get("code")
                or item.get("代码")
                or item.get("stock_code")
                or item.get("symbol")
                or item.get("prod_code")
            )
            if code:
                codes.add(code)
    return codes


def _ensure_replay_stock_quotes(snapshot_data, target_date, helpers=None):
    if not isinstance(snapshot_data, dict):
        return snapshot_data
    helpers = helpers or {}
    stock_full_info = _normalize_replay_stock_info_map(snapshot_data.get("stock_full_info") or {})
    wanted_codes = _collect_replay_quote_codes(snapshot_data)
    missing_codes = sorted(wanted_codes - set(stock_full_info.keys()))
    if not missing_codes:
        snapshot_data["stock_full_info"] = stock_full_info
        return snapshot_data

    fetcher = helpers.get("fetch_stock_batch_quote_info")
    if not callable(fetcher):
        try:
            from market_data.tushare_turnover_service import fetch_stock_batch_quote_info as fetcher
        except Exception:
            fetcher = None
    if not callable(fetcher):
        return snapshot_data

    try:
        fetched = fetcher(missing_codes, target_date)
    except TypeError as error:
        if "target_date" not in str(error):
            raise
        fetched = fetcher(missing_codes)
    fetched_info = _normalize_replay_stock_info_map(fetched)
    patched_codes = []
    for code in missing_codes:
        info = fetched_info.get(code)
        if info:
            stock_full_info[code] = info
            patched_codes.append(code)
    if not patched_codes:
        snapshot_data["stock_full_info"] = stock_full_info
        return snapshot_data

    snapshot_data["stock_full_info"] = stock_full_info
    for key in ("lhb_net_buy_top10", "lhb_net_sell_top10"):
        patched_rows = []
        for item in snapshot_data.get(key) or []:
            code = _normalize_replay_quote_code((item or {}).get("code"))
            patched_rows.append(_patch_replay_quote_fields(item, stock_full_info.get(code, {})))
        snapshot_data[key] = patched_rows

    _replace_request_module_log(
        snapshot_data,
        module="domains.market_activity.request",
        step="request.stock_quotes",
        status="success",
        message="已回补 replay 快照股票行情缺口",
        provider="tushare.daily",
        target_keys=["stock_full_info", "lhb_net_buy_top10", "lhb_net_sell_top10"],
        stock_count=len(stock_full_info),
        patched_count=len(patched_codes),
    )
    _refresh_request_diagnostics(snapshot_data)
    return snapshot_data


def _refresh_request_diagnostics(snapshot_data):
    try:
        from input.request_diagnostics_runtime import build_request_diagnostics
    except Exception:
        return
    snapshot_data["request_diagnostics"] = build_request_diagnostics(
        snapshot_data.get("module_logs") or [],
        data_status=snapshot_data.get("data_status") or {},
        step_status=snapshot_data.get("step_status") or {},
    )


def _ensure_replay_critical_tushare_facts(snapshot_data, target_date, safe_float, helpers=None):
    if not isinstance(snapshot_data, dict):
        return snapshot_data
    helpers = helpers or {}
    data_status = snapshot_data.setdefault("data_status", {})
    step_status = snapshot_data.setdefault("step_status", {})
    changed = False

    total_row = {}
    get_total_row = helpers.get("get_market_daily_total_from_fact_db")
    if callable(get_total_row):
        total_row = get_total_row(target_date) or {}

    total_turnover = safe_float((total_row or {}).get("total_amount_yi"))
    if total_turnover <= 0 and callable(helpers.get("get_market_total_turnover_from_fact_db")):
        total_turnover = safe_float(helpers["get_market_total_turnover_from_fact_db"](target_date))

    if total_turnover > 0 and (
        data_status.get("两市成交额") is False
        or safe_float(snapshot_data.get("total_turnover")) <= 0
        or str(_provider_from_snapshot_log(snapshot_data, "request.total_turnover")).startswith(("akshare.", "eastmoney."))
    ):
        total_turnover = round(total_turnover, 2)
        snapshot_data["total_turnover"] = total_turnover
        turnover_data = dict(snapshot_data.get("turnover_data") or {})
        turnover_data["total_turnover_yi"] = total_turnover
        turnover_data["date"] = target_date
        snapshot_data["turnover_data"] = turnover_data
        data_status["两市成交额"] = True
        step_status["两市成交额获取"] = True
        _mark_replayed_step_success(snapshot_data, "两市成交额获取", safe_float)
        _replace_request_module_log(
            snapshot_data,
            module="domains.market_state.request",
            step="request.total_turnover",
            status="success",
            message="已从事实库回补两市成交额",
            provider="tushare.daily",
            target_keys=["total_turnover", "turnover_data"],
            total_turnover=total_turnover,
            row_count=(total_row or {}).get("stock_count"),
            source_run_id=(total_row or {}).get("source_run_id"),
        )
        changed = True

    get_rank_rows = helpers.get("get_turnover_rank_from_fact_db")
    rank_rows = get_rank_rows(target_date, limit=50) if callable(get_rank_rows) else []
    if rank_rows and (
        data_status.get("成交额排名") is False
        or not snapshot_data.get("turnover_rank")
        or not str(((snapshot_data.get("turnover_rank") or [{}])[0] or {}).get("data_source") or "").startswith("tushare.")
    ):
        snapshot_data["turnover_rank"] = list(rank_rows)
        snapshot_data["turnover_over_100b"] = [
            item for item in rank_rows if safe_float((item or {}).get("turnover")) > 100
        ]
        data_status["成交额排名"] = True
        step_status["成交额排名获取"] = True
        _mark_replayed_step_success(snapshot_data, "成交额排名获取", safe_float)
        _replace_request_module_log(
            snapshot_data,
            module="domains.market_activity.request",
            step="request.turnover_rank",
            status="success",
            message="已从事实库回补成交额排行",
            provider="tushare.daily",
            target_keys=["turnover_rank", "turnover_over_100b"],
            row_count=len(rank_rows),
            turnover_count=len(rank_rows),
            over_100b_count=len(snapshot_data.get("turnover_over_100b") or []),
        )
        changed = True

    get_wind_a = helpers.get("get_wind_a_from_tushare")
    wind_a = get_wind_a(target_date) if callable(get_wind_a) else {}
    wind_a_provider = str((wind_a or {}).get("data_source") or "").strip()
    wind_a_price = safe_float((wind_a or {}).get("price", (wind_a or {}).get("点位", 0)))
    if wind_a_price > 0 and wind_a_provider.startswith("tushare.") and (
        data_status.get("中证全指") is False
        or safe_float((snapshot_data.get("wind_a_alternative") or {}).get("price", (snapshot_data.get("wind_a_alternative") or {}).get("点位", 0))) <= 0
        or not str(_provider_from_snapshot_log(snapshot_data, "request.wind_a")).startswith("tushare.")
    ):
        snapshot_data["wind_a_alternative"] = dict(wind_a or {})
        data_status["中证全指"] = True
        step_status["中证全指获取"] = True
        _mark_replayed_step_success(snapshot_data, "中证全指获取", safe_float)
        _replace_request_module_log(
            snapshot_data,
            module="domains.market_state.request",
            step="request.wind_a",
            status="success",
            message="已从Tushare回补中证全指",
            provider=wind_a_provider,
            target_keys=["wind_a_alternative"],
            price=wind_a_price,
            change_pct=(wind_a or {}).get("change_pct", (wind_a or {}).get("涨跌幅", 0)),
        )
        changed = True

    if changed:
        _refresh_request_diagnostics(snapshot_data)
    return snapshot_data


def _has_rows(value):
    if isinstance(value, (list, tuple)):
        return len(value) > 0
    if isinstance(value, dict):
        return bool(value)
    return value not in (None, "", 0, 0.0)


def _sync_replay_source_status(snapshot_data, *, data_label, step_label, timer_label, safe_float):
    data_status = snapshot_data.setdefault("data_status", {})
    step_status = snapshot_data.setdefault("step_status", {})
    data_status[data_label] = True
    step_status[step_label] = True
    _mark_replayed_step_success(snapshot_data, timer_label, safe_float)


def _fallback_integrated_hot_list_from_primary(snapshot_data):
    hot_rank = snapshot_data.get("hot_rank_top30") or []
    if not isinstance(hot_rank, list):
        return []
    integrated = []
    for index, item in enumerate(hot_rank, 1):
        if not isinstance(item, dict):
            continue
        row = dict(item)
        row.setdefault("rank", index)
        integrated.append(row)
    return integrated


def _fetch_replay_xuangubao_data(target_date, helpers):
    fetcher = (helpers or {}).get("fetch_xuangubao_data")
    if callable(fetcher):
        try:
            return fetcher(target_date=target_date) or {}
        except TypeError as error:
            if "target_date" not in str(error):
                raise
            return fetcher() or {}
    from xuangubao_intraday import XuangubaoIntradayAnalyzer

    return XuangubaoIntradayAnalyzer().fetch_xuangubao_data(target_date=target_date) or {}


def _fetch_replay_wanzhu_top10(target_date, helpers):
    fetcher = (helpers or {}).get("fetch_wanzhu_top10")
    if callable(fetcher):
        return list(fetcher(target_date) or [])
    from data_collector import AShareDataCollector

    return list(AShareDataCollector().get_wanzhu_top10(target_date) or [])


def _fetch_replay_lhb_snapshot(target_date, helpers):
    fetcher = (helpers or {}).get("get_lhb_snapshot_from_tushare")
    if callable(fetcher):
        try:
            return fetcher(target_date=target_date) or {}
        except TypeError as error:
            if "target_date" not in str(error):
                raise
            return fetcher(target_date) or {}
    from input.tushare_runtime import get_lhb_snapshot_from_tushare_first

    return get_lhb_snapshot_from_tushare_first(target_date) or {}


def _fetch_replay_concept_fund_flow(target_date, snapshot_data, helpers):
    fetcher = (helpers or {}).get("get_hot_concept_fund_flow_from_tushare")
    if not callable(fetcher):
        from input.tushare_runtime import get_hot_concept_fund_flow_from_tushare_first as fetcher

    hot_plates = list((snapshot_data or {}).get("hot_plates") or [])
    try:
        return fetcher(target_date=target_date, hot_plates=hot_plates, limit=20) or {}
    except TypeError as error:
        if "target_date" not in str(error):
            raise
        return fetcher(target_date, hot_plates=hot_plates, limit=20) or {}


def _is_replay_concept_hot_plate(row):
    if not isinstance(row, dict):
        return False
    code = str(row.get("code") or row.get("ts_code") or row.get("指数代码") or "").strip()
    code_digits = "".join(ch for ch in code if ch.isdigit())
    if len(code_digits) >= 6 and code_digits[:3] in {"884", "885", "886"}:
        return True
    if code.endswith(".TI") and len(code_digits) >= 6 and code_digits[:3] in {"884", "885", "886"}:
        return True
    marker_text = " ".join(
        str(row.get(key) or "")
        for key in ("type", "market", "tag", "category", "板块类型")
    )
    return "概念" in marker_text


def _replay_concept_fund_flow_tracked(snapshot_data):
    if not isinstance(snapshot_data, dict):
        return False
    if "concept_fund_flow" in snapshot_data:
        return True
    if "概念资金流向" in (snapshot_data.get("data_status") or {}):
        return True
    if "概念资金流向获取" in (snapshot_data.get("step_status") or {}):
        return True
    if any(
        isinstance(item, dict) and item.get("step") == "request.concept_fund_flow"
        for item in snapshot_data.get("module_logs") or []
    ):
        return True
    return any(_is_replay_concept_hot_plate(row) for row in snapshot_data.get("hot_plates") or [])


def _replay_concept_fund_flow_candidate(target_date, helpers=None):
    replay_data = _load_replay_snapshot_candidate(target_date, helpers=helpers)
    if not isinstance(replay_data, dict):
        return {}
    concept_flow = replay_data.get("concept_fund_flow")
    if isinstance(concept_flow, dict) and _has_rows(concept_flow.get("rows") or []):
        return concept_flow
    nested = replay_data.get("data")
    if isinstance(nested, dict):
        concept_flow = nested.get("concept_fund_flow")
        if isinstance(concept_flow, dict) and _has_rows(concept_flow.get("rows") or []):
            return concept_flow
    return {}


def _use_replay_concept_fund_flow_if_complete(snapshot_data, target_date, safe_float, helpers=None):
    concept_flow = _replay_concept_fund_flow_candidate(target_date, helpers=helpers)
    rows = list((concept_flow or {}).get("rows") or [])
    if not rows:
        return False
    snapshot_data["concept_fund_flow"] = {
        "rows": rows,
        "inflow": list((concept_flow or {}).get("inflow") or rows),
        "outflow": list((concept_flow or {}).get("outflow") or []),
        "provider": (concept_flow or {}).get("provider", "replay.concept_fund_flow"),
    }
    _sync_replay_source_status(
        snapshot_data,
        data_label="概念资金流向",
        step_label="概念资金流向获取",
        timer_label="概念资金流向获取",
        safe_float=safe_float,
    )
    _replace_request_module_log(
        snapshot_data,
        module="domains.market_activity.request",
        step="request.concept_fund_flow",
        status="success",
        message="已复用本地 replay 阶段概念资金流",
        provider="replay.concept_fund_flow",
        target_keys=["concept_fund_flow"],
        row_count=len(rows),
        fallback_used=True,
    )
    return True


def _build_sector_bucket(records, *, include_zt_type=False):
    buckets = {}
    for item in records or []:
        if not isinstance(item, dict):
            continue
        sector = item.get("所属行业") or item.get("sector") or "未知"
        row = {
            "code": item.get("代码") or item.get("code") or "",
            "name": item.get("名称") or item.get("name") or "",
        }
        if include_zt_type:
            row["zt_type"] = item.get("涨停统计") or item.get("zt_type") or ""
        buckets.setdefault(sector, []).append(row)
    return buckets


def _fetch_replay_limit_pool_snapshot(target_date, helpers):
    fetcher = (helpers or {}).get("get_limit_pool_snapshot")
    if callable(fetcher):
        return fetcher(target_date) or {}
    try:
        from input.tushare_runtime import get_limit_pool_snapshot_from_tushare_first

        return get_limit_pool_snapshot_from_tushare_first(target_date=target_date) or {}
    except Exception:
        return {}


_NON_SECTOR_LABELS = {
    "HS",
    "GEM",
    "STAR",
    "BJ",
    "SH",
    "SZ",
    "沪深",
    "创业板",
    "科创板",
    "北交所",
    "未知",
    "未归类",
    "待补充板块",
    "待补充",
    "其他",
    "其它",
    "-",
}


def _is_valid_replay_sector(value):
    label = str(value or "").strip()
    return bool(label and label not in _NON_SECTOR_LABELS)


def _infer_replay_sector_from_reason(text):
    text = str(text or "")
    if "长鑫" in text or "国产芯片" in text:
        return "国产芯片"
    keyword_groups = [
        ("算力", ("Token工厂", "昇腾", "算力", "服务器", "数据中心", "液冷", "东数西算")),
        ("机器人", ("机器人", "减速器", "智能体", "机器视觉", "智能制造", "智能物流")),
        ("商业航天", ("商业航天", "卫星", "航天", "火箭")),
        ("低空经济", ("低空", "无人机", "eVTOL")),
        ("家用电器", ("小家电", "家用电器", "空调")),
        ("消费电子", ("MiniLED", "车载背光", "VR背光", "背光显示", "消费电子", "无线耳机", "苹果产业链")),
        ("食品饮料", ("葡萄酒", "白兰地", "保健酒", "食品", "饮料")),
        ("天然气", ("天然气", "页岩气", "燃气")),
        ("资产重组", ("股权转让", "资产重组", "并购重组", "控制权", "重整", "实控人变更", "国资入主", "资产置换")),
        ("环保", ("环保", "水务")),
        ("汽车产业链", ("汽车拆解", "汽车", "新能源汽车")),
    ]
    for sector, markers in keyword_groups:
        if any(marker in text for marker in markers):
            return sector
    return ""


def _normalize_replay_stock_code(value):
    text = str(value or "").strip()
    for suffix in (".SZ", ".SS", ".SH", ".BJ"):
        if text.endswith(suffix):
            text = text[: -len(suffix)]
            break
    lower_text = text.lower()
    for prefix in ("sz", "sh", "bj"):
        if lower_text.startswith(prefix):
            text = text[len(prefix):]
            break
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits.zfill(6) if digits else text


def _replay_stock_matches(item, code):
    if not isinstance(item, dict):
        return False
    expected = _normalize_replay_stock_code(code)
    for key in ("code", "代码", "stock_code", "symbol", "prod_code"):
        if expected and _normalize_replay_stock_code(item.get(key)) == expected:
            return True
    return False


def _first_valid_replay_plate_name(plates):
    for plate in plates or []:
        if isinstance(plate, dict):
            candidates = (
                plate.get("plate_name"),
                plate.get("name"),
                plate.get("concept_name"),
                plate.get("sector"),
            )
        else:
            candidates = (plate,)
        for candidate in candidates:
            if _is_valid_replay_sector(candidate):
                return str(candidate).strip()
    return ""


def _resolve_replay_xuangubao_reason(snapshot_data, code):
    xgb_data = (snapshot_data or {}).get("xuangubao_data") or {}
    for item in xgb_data.get("xuangubao_limit_up_reasons", []) or []:
        if _replay_stock_matches(item, code):
            return item
    return {}


def _normalize_replay_limit_time(value):
    text = str(value or "").strip()
    if not text:
        return "15:00:00"
    if " " in text:
        text = text.split()[-1]
    if ":" in text:
        parts = text.split(":")
        if len(parts) == 2:
            return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}:00"
        if len(parts) >= 3:
            return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}:{parts[2].zfill(2)}"
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) > 6:
        digits = digits[-6:]
    if len(digits) == 6:
        return f"{digits[:2]}:{digits[2:4]}:{digits[4:6]}"
    if len(digits) == 4:
        return f"{digits[:2]}:{digits[2:4]}:00"
    return text


def _derive_lianban_data_from_zt_pool(snapshot_data):
    rows = []
    for item in snapshot_data.get("zt_pool") or []:
        if not isinstance(item, dict):
            continue
        code = _normalize_replay_stock_code(item.get("代码") or item.get("code"))
        if not code:
            continue
        xgb_reason = _resolve_replay_xuangubao_reason(snapshot_data, code)
        stock_reason = str((xgb_reason or {}).get("stock_reason") or "").strip()
        sector = item.get("所属行业") or item.get("sector") or ""
        related_plates = (xgb_reason or {}).get("related_plates", []) or []
        plate_name = _first_valid_replay_plate_name(related_plates)
        reason_text = stock_reason or item.get("涨停统计") or item.get("reason") or ""
        if not _is_valid_replay_sector(sector):
            sector = plate_name or _infer_replay_sector_from_reason(reason_text) or ""
        row = {
            "code": code,
            "name": item.get("名称") or item.get("name") or "",
            "lianban_days": int(_safe_float(item.get("连板数", item.get("lianban_days", 1)), 1)),
            "change_pct": _safe_float(item.get("涨跌幅", item.get("change_pct", 0))),
            "turnover": _safe_float(item.get("成交额", item.get("turnover", 0))),
            "sector": sector,
            "plates": [sector] if _is_valid_replay_sector(sector) else [],
            "reason": reason_text,
            "open_price": _safe_float(item.get("开盘价", item.get("open_price", 0))),
            "close_price": _safe_float(item.get("最新价", item.get("close_price", item.get("price", 0)))),
            "high_price": _safe_float(item.get("最高价", item.get("high_price", 0))),
            "low_price": _safe_float(item.get("最低价", item.get("low_price", 0))),
            "first_limit_time": _normalize_replay_limit_time(item.get("首次封板时间", item.get("first_limit_time", ""))),
        }
        if xgb_reason:
            row.update(
                {
                    "xuangubao_stock_reason": stock_reason,
                    "xuangubao_related_plates": related_plates,
                    "xuangubao_related_plate_names": [
                        str(plate.get("plate_name") or plate.get("name") or "").strip()
                        for plate in related_plates
                        if isinstance(plate, dict) and str(plate.get("plate_name") or plate.get("name") or "").strip()
                    ],
                    "xuangubao_limit_up_days": (xgb_reason or {}).get("limit_up_days", 0),
                }
            )
        rows.append(row)
    rows.sort(key=lambda item: (-item.get("lianban_days", 0), item.get("first_limit_time", "99:99:99")))
    return rows


def _previous_turnover_window(stock, current_turnover):
    history = list((stock or {}).get("hist_turnover") or [])
    if len(history) >= 6 and abs(_safe_float(history[-1]) - current_turnover) < 0.0001:
        return history[-6:-1]
    return history[-5:]


def _derive_volume_anomalies_from_history(snapshot_data):
    rows = []
    for stock in snapshot_data.get("stocks_with_history") or []:
        if not isinstance(stock, dict):
            continue
        current_turnover = _safe_float(stock.get("turnover"))
        window = [_safe_float(value) for value in _previous_turnover_window(stock, current_turnover) if _safe_float(value) > 0]
        if current_turnover <= 0 or not window:
            continue
        avg_turnover = sum(window) / len(window)
        if avg_turnover <= 0:
            continue
        ratio = current_turnover / avg_turnover
        if ratio < 1.5:
            continue
        if ratio >= 2.0:
            anomaly_type = "放量突破"
            strength = "高"
            percentile = 98
        else:
            anomaly_type = "温和放量"
            strength = "中"
            percentile = 95
        rows.append(
            {
                "stock_code": _normalize_replay_stock_code(stock.get("code")),
                "stock_name": stock.get("name", ""),
                "anomaly_type": anomaly_type,
                "strength": strength,
                "volume_percentile": percentile,
                "price_change": _safe_float(stock.get("change_pct")),
                "reason": f"当日成交额{current_turnover:.1f}亿，约为近5日均值{ratio:.2f}倍",
                "turnover": current_turnover,
                "avg_turnover_5d": round(avg_turnover, 4),
                "volume_ratio": round(ratio, 4),
                "sector": stock.get("sector", ""),
            }
        )
    rows.sort(key=lambda item: (item.get("volume_ratio", 0), abs(item.get("price_change", 0))), reverse=True)
    return rows[:10]


def _is_renderable_lhb_analysis(rows):
    for item in rows or []:
        if isinstance(item, dict) and item.get("stock_name") not in (None, "") and item.get("net_buy") not in (None, ""):
            return True
        if hasattr(item, "stock_name") and hasattr(item, "net_buy"):
            return True
    return False


def _derive_lhb_analysis_for_render(snapshot_data):
    rows = []
    seen = set()
    for item in (snapshot_data.get("lhb_net_buy_top10") or []) + (snapshot_data.get("lhb_net_sell_top10") or []):
        if not isinstance(item, dict):
            continue
        code = _normalize_replay_stock_code(item.get("code") or item.get("stock_code"))
        amount = _safe_float(
            item.get(
                "net_buy_amount_yi",
                item.get("net_buy", item.get("net_amount_yi", item.get("net_sell_amount_yi", 0))),
            )
        )
        if item.get("net_sell_amount_yi") not in (None, "") and amount > 0:
            amount = -amount
        dedupe_key = code or item.get("name") or item.get("stock_name")
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        abs_amount = abs(amount)
        if amount >= 0:
            money_type = "龙虎榜净买入"
            pattern = "强净买" if abs_amount >= 3 else "净买跟踪"
        else:
            money_type = "龙虎榜净卖出"
            pattern = "强净卖" if abs_amount >= 3 else "净卖分歧"
        if abs_amount >= 5:
            signal_strength = "强"
        elif abs_amount >= 1:
            signal_strength = "中"
        else:
            signal_strength = "弱"
        rows.append(
            {
                "stock_code": code,
                "stock_name": item.get("name") or item.get("stock_name") or code,
                "net_buy": amount,
                "money_type": money_type,
                "pattern": pattern,
                "recent_appearances": 1,
                "signal_strength": signal_strength,
                "sector": item.get("sector", ""),
            }
        )
    rows.sort(key=lambda item: abs(item.get("net_buy", 0)), reverse=True)
    return rows[:10]


def _ensure_replay_advanced_activity(snapshot_data):
    changed = False
    if not _has_rows(snapshot_data.get("volume_anomalies")):
        volume_anomalies = _derive_volume_anomalies_from_history(snapshot_data)
        if volume_anomalies:
            snapshot_data["volume_anomalies"] = volume_anomalies
            _replace_request_module_log(
                snapshot_data,
                module="domains.market_activity.infer",
                step="infer.volume_anomalies",
                status="success",
                message="已从历史成交额派生放量异常",
                provider="replay.stocks_with_history.derived",
                target_keys=["volume_anomalies"],
                volume_anomaly_count=len(volume_anomalies),
            )
            changed = True

    lhb_analysis = snapshot_data.get("lhb_analysis")
    if not isinstance(lhb_analysis, list) or not _is_renderable_lhb_analysis(lhb_analysis):
        derived_lhb = _derive_lhb_analysis_for_render(snapshot_data)
        if derived_lhb:
            snapshot_data["lhb_analysis"] = derived_lhb
            _replace_request_module_log(
                snapshot_data,
                module="domains.market_activity.infer",
                step="infer.lhb_analysis",
                status="success",
                message="已从龙虎榜净买净卖派生多维龙虎榜结果",
                provider="replay.lhb_top10.derived",
                target_keys=["lhb_analysis"],
                lhb_count=len(derived_lhb),
            )
            changed = True
    return changed


def _apply_replay_limit_pool_snapshot(snapshot_data, pool_snapshot, safe_float):
    zt_pool = list((pool_snapshot or {}).get("zt_pool") or [])
    dt_pool = list((pool_snapshot or {}).get("dt_pool") or [])
    market_stats = dict((pool_snapshot or {}).get("market_stats") or {})
    if not (zt_pool or dt_pool or market_stats):
        return False

    snapshot_data["zt_pool"] = zt_pool
    snapshot_data["dt_pool"] = dt_pool
    snapshot_data["limit_up_codes"] = list((pool_snapshot or {}).get("limit_up_codes") or [row.get("代码") for row in zt_pool if isinstance(row, dict) and row.get("代码")])
    snapshot_data["limit_down_codes"] = list((pool_snapshot or {}).get("limit_down_codes") or [row.get("代码") for row in dt_pool if isinstance(row, dict) and row.get("代码")])
    snapshot_data["zt_pool_by_sector"] = (pool_snapshot or {}).get("zt_pool_by_sector") or _build_sector_bucket(zt_pool, include_zt_type=True)
    snapshot_data["dt_pool_by_sector"] = (pool_snapshot or {}).get("dt_pool_by_sector") or _build_sector_bucket(dt_pool)
    snapshot_data["market_stats"] = market_stats

    data_status = snapshot_data.setdefault("data_status", {})
    step_status = snapshot_data.setdefault("step_status", {})
    data_status["涨停池"] = bool(zt_pool)
    data_status["跌停池"] = bool(dt_pool)
    data_status["大盘涨跌统计"] = bool(market_stats)
    if zt_pool:
        data_status["涨停股板块分布"] = True
    if dt_pool:
        data_status["跌停股板块分布"] = True
    step_status["涨停跌停数据获取"] = True
    _mark_replayed_step_success(snapshot_data, "涨停跌停数据获取", safe_float)
    _replace_request_module_log(
        snapshot_data,
        module="domains.market_activity.request",
        step="request.pool_snapshot",
        status="success",
        message="已回补涨停跌停池与市场活跃度快照",
        provider=(pool_snapshot or {}).get("provider", "tushare.limit_list_ths"),
        target_keys=["zt_pool", "dt_pool", "zt_pool_by_sector", "dt_pool_by_sector", "market_stats"],
        zt_count=len(zt_pool),
        dt_count=len(dt_pool),
        fallback_used=bool((pool_snapshot or {}).get("fallback_used")),
    )
    return True


def _ensure_replay_decision_sources(snapshot_data, target_date, safe_float, helpers=None):
    if not isinstance(snapshot_data, dict):
        return snapshot_data
    helpers = helpers or {}
    changed = False

    if (
        snapshot_data.get("step_status", {}).get("涨停跌停数据获取") is False
        or snapshot_data.get("data_status", {}).get("涨停池") is False
        or snapshot_data.get("data_status", {}).get("跌停池") is False
        or snapshot_data.get("data_status", {}).get("大盘涨跌统计") is False
    ):
        if _apply_replay_limit_pool_snapshot(
            snapshot_data,
            _fetch_replay_limit_pool_snapshot(target_date, helpers),
            safe_float,
        ):
            changed = True

    if (
        snapshot_data.get("data_status", {}).get("整合热榜") is False
        or snapshot_data.get("step_status", {}).get("整合热榜获取") is False
        or not _has_rows(snapshot_data.get("integrated_hot_list"))
    ):
        integrated = _fallback_integrated_hot_list_from_primary(snapshot_data)
        if integrated:
            snapshot_data["integrated_hot_list"] = integrated
            snapshot_data.setdefault("tag_distribution", snapshot_data.get("tag_distribution") or {})
            snapshot_data.setdefault("status_distribution", snapshot_data.get("status_distribution") or {})
            _sync_replay_source_status(
                snapshot_data,
                data_label="整合热榜",
                step_label="整合热榜获取",
                timer_label="整合热榜获取",
                safe_float=safe_float,
            )
            _replace_request_module_log(
                snapshot_data,
                module="domains.market_activity.request",
                step="request.integrated_hot_rank",
                status="success",
                message="已从热度前三十派生整合热榜",
                provider="primary_hot_rank.derived",
                target_keys=["integrated_hot_list", "tag_distribution", "status_distribution", "high_lianban_stocks"],
                integrated_count=len(integrated),
                fallback_used=False,
            )
            changed = True

    xgb_data = snapshot_data.get("xuangubao_data") or {}
    xgb_count = (
        len((xgb_data or {}).get("xuangubao_news", []) or [])
        + len((xgb_data or {}).get("xuangubao_plates", []) or [])
        + len((xgb_data or {}).get("xuangubao_limit_up_reasons", []) or [])
    )
    xgb_news_count = len((xgb_data or {}).get("xuangubao_news", []) or [])
    if (
        snapshot_data.get("data_status", {}).get("选股通盘中异动") is False
        or snapshot_data.get("step_status", {}).get("选股通盘中异动获取") is False
        or xgb_count <= 0
        or xgb_news_count <= 0
    ):
        try:
            refreshed_xgb_data = _fetch_replay_xuangubao_data(target_date, helpers)
        except Exception:
            refreshed_xgb_data = {}
        news_count = len((refreshed_xgb_data or {}).get("xuangubao_news", []) or [])
        plate_count = len((refreshed_xgb_data or {}).get("xuangubao_plates", []) or [])
        limit_up_reason_count = len((refreshed_xgb_data or {}).get("xuangubao_limit_up_reasons", []) or [])
        refreshed_count = news_count + plate_count + limit_up_reason_count
        if refreshed_count:
            if news_count:
                next_xgb_data = refreshed_xgb_data
            elif xgb_news_count > 0:
                next_xgb_data = {
                    **(refreshed_xgb_data or {}),
                    "xuangubao_news": (xgb_data or {}).get("xuangubao_news", []) or [],
                }
                news_count = xgb_news_count
            else:
                next_xgb_data = refreshed_xgb_data
            snapshot_data["xuangubao_data"] = next_xgb_data
            _sync_replay_source_status(
                snapshot_data,
                data_label="选股通盘中异动",
                step_label="选股通盘中异动获取",
                timer_label="选股通盘中异动获取",
                safe_float=safe_float,
            )
            _replace_request_module_log(
                snapshot_data,
                module="domains.monitoring.request",
                step="request.xuangubao",
                status="success",
                message="已回补选股通盘中异动",
                provider="xuangubao.fetch_xuangubao_data",
                target_keys=["xuangubao_data"],
                optional=True,
                news_count=news_count,
                plate_count=plate_count,
                limit_up_reason_count=limit_up_reason_count,
                diagnostic_note="; ".join(
                    f"{key}={value}"
                    for key, value in ((refreshed_xgb_data or {}).get("diagnostics", {}) or {}).items()
                    if value not in (None, "", {})
                ),
                diagnostics=(refreshed_xgb_data or {}).get("diagnostics", {}),
            )
            changed = True
        elif xgb_news_count > 0:
            _sync_replay_source_status(
                snapshot_data,
                data_label="选股通盘中异动",
                step_label="选股通盘中异动获取",
                timer_label="选股通盘中异动获取",
                safe_float=safe_float,
            )
            _replace_request_module_log(
                snapshot_data,
                module="domains.monitoring.request",
                step="request.xuangubao",
                status="success",
                message="选股通刷新未返回新闻，保留旧快照新闻",
                provider="snapshot.xuangubao_data",
                target_keys=["xuangubao_data"],
                optional=True,
                news_count=xgb_news_count,
                plate_count=len((xgb_data or {}).get("xuangubao_plates", []) or []),
                limit_up_reason_count=len((xgb_data or {}).get("xuangubao_limit_up_reasons", []) or []),
                diagnostic_note="refresh_missing_news",
                diagnostics=(xgb_data or {}).get("diagnostics", {}),
            )
            changed = True

    if (
        snapshot_data.get("data_status", {}).get("顽主杯热门前十") is False
        or snapshot_data.get("step_status", {}).get("顽主杯热门前十获取") is False
        or not _has_rows(snapshot_data.get("wanzhu_top10"))
    ):
        try:
            wanzhu_top10 = _fetch_replay_wanzhu_top10(target_date, helpers)
        except Exception:
            wanzhu_top10 = []
        if wanzhu_top10:
            snapshot_data["wanzhu_top10"] = wanzhu_top10
            _sync_replay_source_status(
                snapshot_data,
                data_label="顽主杯热门前十",
                step_label="顽主杯热门前十获取",
                timer_label="顽主杯热门前十获取",
                safe_float=safe_float,
            )
            _replace_request_module_log(
                snapshot_data,
                module="domains.monitoring.request",
                step="request.wanzhu_top10",
                status="success",
                message="已回补顽主杯热门前十",
                provider="AShareDataCollector.get_wanzhu_top10",
                target_keys=["wanzhu_top10"],
                stock_count=len(wanzhu_top10),
            )
            changed = True

    if (
        snapshot_data.get("step_status", {}).get("连板梯队提取") is False
        or not _has_rows(snapshot_data.get("lianban_data"))
    ):
        derived_lianban = _derive_lianban_data_from_zt_pool(snapshot_data)
        snapshot_data["lianban_data"] = derived_lianban if derived_lianban else list(snapshot_data.get("lianban_data") or [])
        snapshot_data.setdefault("step_status", {})["连板梯队提取"] = True
        _mark_replayed_step_success(snapshot_data, "连板梯队提取", safe_float)
        _replace_request_module_log(
            snapshot_data,
            module="domains.market_activity.request",
            step="request.lianban_snapshot",
            status="success",
            message="已从涨停池派生连板与首板梯队" if derived_lianban else "已确认连板梯队为空但请求成功",
            provider="replay.zt_pool.derived" if derived_lianban else "tushare.limit_list_ths",
            target_keys=["lianban_data"],
            lianban_count=len(snapshot_data.get("lianban_data") or []),
        )
        changed = True

    lhb_buy = snapshot_data.get("lhb_net_buy_top10") or []
    lhb_sell = snapshot_data.get("lhb_net_sell_top10") or []
    lhb_analysis = snapshot_data.get("lhb_analysis") or []
    lhb_provider = str(_provider_from_snapshot_log(snapshot_data, "request.lhb_snapshot") or "")
    if (
        snapshot_data.get("step_status", {}).get("龙虎榜数据获取") is False
        or not (lhb_buy or lhb_sell or lhb_analysis)
        or (lhb_provider.startswith("legacy.") and not (lhb_buy or lhb_sell))
    ):
        try:
            lhb_snapshot = _fetch_replay_lhb_snapshot(target_date, helpers)
        except Exception:
            lhb_snapshot = {}
        refreshed_buy = list((lhb_snapshot or {}).get("lhb_net_buy_top10") or [])
        refreshed_sell = list((lhb_snapshot or {}).get("lhb_net_sell_top10") or [])
        refreshed_analysis = list((lhb_snapshot or {}).get("lhb_analysis") or [])
        if refreshed_buy or refreshed_sell or refreshed_analysis:
            snapshot_data["lhb_net_buy_top10"] = refreshed_buy
            snapshot_data["lhb_net_sell_top10"] = refreshed_sell
            snapshot_data["lhb_analysis"] = refreshed_analysis
            snapshot_data.setdefault("step_status", {})["龙虎榜数据获取"] = True
            _mark_replayed_step_success(snapshot_data, "龙虎榜数据获取", safe_float)
            _replace_request_module_log(
                snapshot_data,
                module="domains.market_activity.request",
                step="request.lhb_snapshot",
                status="success",
                message="已从Tushare回补龙虎榜数据",
                provider=(lhb_snapshot or {}).get("provider", "tushare.top_list"),
                target_keys=["lhb_net_buy_top10", "lhb_net_sell_top10", "lhb_analysis"],
                lhb_count=len(refreshed_analysis),
                buy_count=len(refreshed_buy),
                sell_count=len(refreshed_sell),
                fallback_used=bool((lhb_snapshot or {}).get("fallback_used")),
            )
            changed = True
        else:
            snapshot_data.setdefault("step_status", {})["龙虎榜数据获取"] = False
            _replace_request_module_log(
                snapshot_data,
                module="domains.market_activity.request",
                step="request.lhb_snapshot",
                status="degraded",
                message="龙虎榜回补仍为空",
                provider=(lhb_snapshot or {}).get("provider", "tushare.top_list"),
                target_keys=["lhb_net_buy_top10", "lhb_net_sell_top10", "lhb_analysis"],
                lhb_count=0,
                buy_count=0,
                sell_count=0,
                fallback_used=bool((lhb_snapshot or {}).get("fallback_used")),
            )
            changed = True

    concept_flow = snapshot_data.get("concept_fund_flow") or {}
    if _replay_concept_fund_flow_tracked(snapshot_data) and (
        snapshot_data.get("data_status", {}).get("概念资金流向") is False
        or snapshot_data.get("step_status", {}).get("概念资金流向获取") is False
        or not (isinstance(concept_flow, dict) and _has_rows(concept_flow.get("rows") or []))
    ):
        try:
            refreshed_concept_flow = _fetch_replay_concept_fund_flow(target_date, snapshot_data, helpers)
        except Exception:
            refreshed_concept_flow = {}
        rows = list((refreshed_concept_flow or {}).get("rows") or [])
        if rows:
            snapshot_data["concept_fund_flow"] = {
                "rows": rows,
                "inflow": list((refreshed_concept_flow or {}).get("inflow") or rows),
                "outflow": list((refreshed_concept_flow or {}).get("outflow") or []),
                "provider": (refreshed_concept_flow or {}).get("provider", "tushare.ths_member+tushare.moneyflow"),
            }
            _sync_replay_source_status(
                snapshot_data,
                data_label="概念资金流向",
                step_label="概念资金流向获取",
                timer_label="概念资金流向获取",
                safe_float=safe_float,
            )
            _replace_request_module_log(
                snapshot_data,
                module="domains.market_activity.request",
                step="request.concept_fund_flow",
                status="success",
                message="已回补概念板块资金流",
                provider=(refreshed_concept_flow or {}).get("provider", "tushare.ths_member+tushare.moneyflow"),
                target_keys=["concept_fund_flow"],
                row_count=len(rows),
                fallback_used=bool((refreshed_concept_flow or {}).get("fallback_used")),
            )
            changed = True
        elif _use_replay_concept_fund_flow_if_complete(snapshot_data, target_date, safe_float, helpers=helpers):
            changed = True
        else:
            snapshot_data.setdefault("data_status", {})["概念资金流向"] = False
            snapshot_data.setdefault("step_status", {})["概念资金流向获取"] = False
            _replace_request_module_log(
                snapshot_data,
                module="domains.market_activity.request",
                step="request.concept_fund_flow",
                status="degraded",
                message="概念板块资金流回补仍为空",
                provider=(refreshed_concept_flow or {}).get("provider", "tushare.ths_member+tushare.moneyflow"),
                target_keys=["concept_fund_flow"],
                row_count=0,
                fallback_used=bool((refreshed_concept_flow or {}).get("fallback_used")),
            )
            changed = True

    if _ensure_replay_advanced_activity(snapshot_data):
        changed = True

    if changed:
        _refresh_request_diagnostics(snapshot_data)
    return snapshot_data


def _provider_from_snapshot_log(snapshot_data, step):
    for item in snapshot_data.get("module_logs") or []:
        if not isinstance(item, dict) or item.get("step") != step:
            continue
        return (item.get("details") or {}).get("provider") or ""
    return ""


def _fetch_calendar_events_compat(tencent, target_date):
    try:
        return tencent.get_calendar_events(target_date=target_date)
    except TypeError as error:
        if "target_date" not in str(error):
            raise
        return tencent.get_calendar_events()


def build_replay_snapshot_contract(
    target_date,
    refresh_sources=None,
    *,
    load_data_snapshot,
    tencent_factory,
    get_major_indices_from_iwencai,
    safe_float,
    print_fn=print,
    helpers=None,
):
    refresh_sources = list(refresh_sources or ["calendar_events"])
    logs = []

    print_fn(f"\n{'=' * 60}")
    print_fn(f"🔄 复盘模式：从快照读取 {target_date} 数据")
    print_fn(f"   刷新数据源: {', '.join(refresh_sources)}")
    print_fn(f"{'=' * 60}")

    snapshot_data, supplementary = load_data_snapshot(target_date)
    if not snapshot_data:
        print_fn(f"❌ 快照不存在: {target_date}，无法复盘")
        _append_log(logs, "load.snapshot", "error", "快照不存在，无法进入复盘流程", target_date=target_date)
        return {
            "found": False,
            "data": None,
            "target_date": target_date,
            "supplementary_perspective": supplementary or "",
            "module_logs": logs,
        }

    _append_log(logs, "load.snapshot", "success", "已加载官方快照", refresh_sources=refresh_sources)
    snapshot_data = _hoist_report_analysis_atoms(snapshot_data)
    explicit_helpers = helpers or {}
    runtime_helpers = {**_load_default_mainline_helpers(), **explicit_helpers}
    if "query_new_high_feedback_series" in explicit_helpers:
        runtime_helpers["_use_default_query_new_high_feedback_series"] = False
    snapshot_data = _ensure_replay_critical_tushare_facts(
        snapshot_data,
        target_date,
        safe_float,
        helpers=runtime_helpers,
    )
    snapshot_data = _ensure_replay_new_high_feedback(
        snapshot_data,
        target_date,
        safe_float,
        helpers=runtime_helpers,
    )
    snapshot_data = _ensure_replay_price_band_style_series(
        snapshot_data,
        target_date,
        safe_float,
        helpers=runtime_helpers,
    )
    snapshot_data = _ensure_replay_decision_sources(
        snapshot_data,
        target_date,
        safe_float,
        helpers=runtime_helpers,
    )
    snapshot_data = _ensure_replay_stock_quotes(snapshot_data, target_date, helpers=runtime_helpers)
    snapshot_data = _ensure_report_mainline_atoms(snapshot_data, target_date, helpers=runtime_helpers)
    snapshot_data = _ensure_replay_capital_intent_atoms(snapshot_data)

    if "calendar_events" in refresh_sources:
        print_fn("   🔄 重新拉取财联社预期日历...")
        try:
            tencent = tencent_factory()
            calendar = _fetch_calendar_events_compat(tencent, target_date)
            if calendar:
                snapshot_data["calendar_events"] = calendar
                data_status = snapshot_data.setdefault("data_status", {})
                step_status = snapshot_data.setdefault("step_status", {})
                data_status["预期日历"] = True
                step_status["预期日历获取"] = True
                _mark_replayed_step_success(snapshot_data, "预期日历获取", safe_float)
                _replace_request_module_log(
                    snapshot_data,
                    module="domains.calendar_events.request",
                    step="request.calendar_events",
                    status="success",
                    message="已刷新财联社预期日历",
                    provider="tencent.get_calendar_events",
                    target_keys=["calendar_events"],
                    calendar_count=len(calendar),
                )
                _refresh_request_diagnostics(snapshot_data)
                print_fn(f"   ✅ 预期日历刷新成功: {len(calendar)} 条")
                _append_log(logs, "refresh.calendar_events", "success", "已刷新财联社预期日历", count=len(calendar))
            else:
                print_fn("   ⚠️ 预期日历返回空，保留快照中的旧数据")
                _append_log(logs, "refresh.calendar_events", "warning", "预期日历返回空，保留旧快照")
        except Exception as exc:
            print_fn(f"   ⚠️ 预期日历拉取失败: {exc}，保留快照中的旧数据")
            _append_log(logs, "refresh.calendar_events", "warning", "预期日历拉取失败，保留旧快照", error=str(exc))

    data_status = snapshot_data.setdefault("data_status", {})
    step_status = snapshot_data.setdefault("step_status", {})
    major_indices_missing = (
        "major_indices" in refresh_sources
        or not data_status.get("主要指数")
        or not snapshot_data.get("indices")
    )
    if major_indices_missing:
        print_fn("   🔄 回补主要指数...")
        try:
            indices = get_major_indices_from_iwencai(target_date=target_date)
            if indices:
                snapshot_data["indices"] = indices
                data_status["主要指数"] = True
                step_status["主要指数获取"] = True
                _mark_replayed_step_success(snapshot_data, "主要指数获取", safe_float)
                print_fn(f"   ✅ 主要指数回补成功: {len(indices)} 个")
                _append_log(logs, "refresh.major_indices", "success", "已回补主要指数", count=len(indices))
            else:
                print_fn("   ⚠️ 主要指数回补失败，保留快照中的旧数据")
                _append_log(logs, "refresh.major_indices", "warning", "主要指数返回空，保留旧快照")
        except Exception as exc:
            print_fn(f"   ⚠️ 主要指数回补失败: {exc}，保留快照中的旧数据")
            _append_log(logs, "refresh.major_indices", "warning", "主要指数回补失败，保留旧快照", error=str(exc))
    else:
        _append_log(logs, "refresh.major_indices", "success", "主要指数快照仍有效，无需回补")

    print_fn("   ✅ 快照数据加载完成，开始用最新skill生成报告")
    return {
        "found": True,
        "data": snapshot_data,
        "target_date": target_date,
        "supplementary_perspective": supplementary or "",
        "module_logs": logs,
    }


def build_replay_report_outputs_contract(
    target_date,
    refresh_sources=None,
    *,
    load_data_snapshot,
    tencent_factory,
    get_major_indices_from_iwencai,
    safe_float,
    build_report_outputs,
    save_report_outputs,
    output_dir=None,
    has_personal_positions=False,
    position_report_text="",
    print_fn=print,
    helpers=None,
):
    replay_contract = build_replay_snapshot_contract(
        target_date,
        refresh_sources=refresh_sources,
        load_data_snapshot=load_data_snapshot,
        tencent_factory=tencent_factory,
        get_major_indices_from_iwencai=get_major_indices_from_iwencai,
        safe_float=safe_float,
        print_fn=print_fn,
        helpers=helpers,
    )
    replay_contract.setdefault("report_outputs", {})
    replay_contract.setdefault("saved_paths", {})
    if not replay_contract.get("found"):
        return replay_contract

    logs = replay_contract.setdefault("module_logs", [])
    replay_data = replay_contract.get("data") or {}
    resolved_target_date = replay_contract.get("target_date") or target_date
    supplementary = replay_contract.get("supplementary_perspective") or ""

    try:
        report_outputs = build_report_outputs(
            replay_data,
            resolved_target_date,
            supplementary_perspective=supplementary,
            has_personal_positions=has_personal_positions,
            run_mode="replay",
            position_report_text=position_report_text,
        )
    except Exception as exc:
        _append_log(logs, "render.report_outputs", "error", "生成 replay 报告产物失败", error=str(exc))
        raise

    replay_contract["report_outputs"] = report_outputs
    _append_log(
        logs,
        "render.report_outputs",
        "success",
        "已生成 replay 报告产物",
        variants=sorted((report_outputs or {}).keys()),
    )

    try:
        saved_paths = save_report_outputs(
            report_outputs,
            resolved_target_date,
            mode="replay",
            output_dir=output_dir,
        )
    except Exception as exc:
        _append_log(logs, "save.report_outputs", "error", "落盘 replay 报告产物失败", error=str(exc))
        raise

    replay_contract["saved_paths"] = saved_paths
    _append_log(
        logs,
        "save.report_outputs",
        "success",
        "已落盘 replay 报告产物",
        variants=sorted((saved_paths or {}).keys()),
        output_dir=output_dir,
    )
    return replay_contract


def _replay_from_snapshot_legacy_body(target_date, refresh_sources=None):
    return build_replay_snapshot_contract(
        target_date,
        refresh_sources=refresh_sources,
        load_data_snapshot=load_data_snapshot,
        tencent_factory=TencentFinanceData,
        get_major_indices_from_iwencai=get_major_indices_from_iwencai,
        safe_float=safe_float,
    )
