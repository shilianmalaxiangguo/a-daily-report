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
    from input.tushare_runtime import get_wind_a_from_tushare_first
    from input.ths_sector_runtime import get_sector_turnover_snapshot_from_ths
    from research.market_research_runtime import (
        _fill_sector_snapshot_total_turnover,
        _has_resolved_mainline_turnover_summary,
        _resolve_effective_total_turnover,
    )
    from research.market_research_support import (
        get_market_daily_total_from_fact_db_runtime,
        get_market_total_turnover_from_fact_db_runtime,
        get_turnover_rank_from_fact_db_runtime,
    )

    return {
        "build_mainline_history_record": build_mainline_history_record,
        "load_recent_mainline_history": load_recent_mainline_history,
        "get_sector_turnover_snapshot_from_ths": get_sector_turnover_snapshot_from_ths,
        "load_recent_sector_turnover_history": load_recent_sector_turnover_history,
        "build_mainline_turnover_summary": build_mainline_turnover_summary,
        "fill_sector_snapshot_total_turnover": _fill_sector_snapshot_total_turnover,
        "has_resolved_mainline_turnover_summary": _has_resolved_mainline_turnover_summary,
        "resolve_effective_total_turnover": _resolve_effective_total_turnover,
        "get_market_daily_total_from_fact_db": get_market_daily_total_from_fact_db_runtime,
        "get_market_total_turnover_from_fact_db": get_market_total_turnover_from_fact_db_runtime,
        "get_turnover_rank_from_fact_db": get_turnover_rank_from_fact_db_runtime,
        "get_wind_a_from_tushare": get_wind_a_from_tushare_first,
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


def _load_recent_mainline_history_for_cycle_calendar(loader, target_date):
    try:
        return loader(target_date, lookback_days=25, max_scan_days=60)
    except TypeError as exc:
        if "max_scan_days" not in str(exc):
            raise
        return loader(target_date, lookback_days=25)


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

    if not snapshot_data.get("recent_mainline_history") and callable(helpers.get("load_recent_mainline_history")):
        snapshot_data["recent_mainline_history"] = _load_recent_mainline_history_for_cycle_calendar(
            helpers["load_recent_mainline_history"],
            target_date,
        )

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

    if (
        not snapshot_data.get("recent_sector_turnover_history")
        and current_mainline_name
        and callable(helpers.get("load_recent_sector_turnover_history"))
    ):
        snapshot_data["recent_sector_turnover_history"] = helpers["load_recent_sector_turnover_history"](
            target_date,
            current_mainline_name,
            lookback_days=5,
        )

    summary_resolved = True
    if callable(helpers.get("has_resolved_mainline_turnover_summary")):
        summary_resolved = helpers["has_resolved_mainline_turnover_summary"](
            snapshot_data.get("mainline_turnover_summary")
        )

    sector_attack_evidence_rows = _build_replay_sector_attack_evidence_rows(snapshot_data, market_research_snapshot)
    should_rebuild_for_attack_evidence = bool(
        sector_attack_evidence_rows
        and not _summary_has_attack_evidence(snapshot_data.get("mainline_turnover_summary"))
    )

    if (not summary_resolved or should_rebuild_for_attack_evidence) and callable(helpers.get("build_mainline_turnover_summary")):
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
                message="已从热度前三十回补整合热榜",
                provider="primary_hot_rank.fallback",
                target_keys=["integrated_hot_list", "tag_distribution", "status_distribution", "high_lianban_stocks"],
                integrated_count=len(integrated),
                fallback_used=True,
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
            xgb_data = _fetch_replay_xuangubao_data(target_date, helpers)
        except Exception:
            xgb_data = {}
        news_count = len((xgb_data or {}).get("xuangubao_news", []) or [])
        plate_count = len((xgb_data or {}).get("xuangubao_plates", []) or [])
        limit_up_reason_count = len((xgb_data or {}).get("xuangubao_limit_up_reasons", []) or [])
        if news_count or plate_count or limit_up_reason_count:
            snapshot_data["xuangubao_data"] = xgb_data
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
                    for key, value in ((xgb_data or {}).get("diagnostics", {}) or {}).items()
                    if value not in (None, "", {})
                ),
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
        or snapshot_data.get("lianban_data") is None
    ):
        snapshot_data["lianban_data"] = list(snapshot_data.get("lianban_data") or [])
        snapshot_data.setdefault("step_status", {})["连板梯队提取"] = True
        _mark_replayed_step_success(snapshot_data, "连板梯队提取", safe_float)
        _replace_request_module_log(
            snapshot_data,
            module="domains.market_activity.request",
            step="request.lianban_snapshot",
            status="success",
            message="已确认连板梯队为空但请求成功",
            provider="tushare.limit_list_ths",
            target_keys=["lianban_data"],
            lianban_count=len(snapshot_data.get("lianban_data") or []),
        )
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
    runtime_helpers = {**_load_default_mainline_helpers(), **(helpers or {})}
    snapshot_data = _ensure_replay_critical_tushare_facts(
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
