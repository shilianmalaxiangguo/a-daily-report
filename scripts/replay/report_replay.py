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
    from input.ths_sector_runtime import get_sector_turnover_snapshot_from_ths

    return {
        "build_mainline_history_record": build_mainline_history_record,
        "load_recent_mainline_history": load_recent_mainline_history,
        "get_sector_turnover_snapshot_from_ths": get_sector_turnover_snapshot_from_ths,
        "load_recent_sector_turnover_history": load_recent_sector_turnover_history,
        "build_mainline_turnover_summary": build_mainline_turnover_summary,
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
        snapshot_data["recent_mainline_history"] = helpers["load_recent_mainline_history"](
            target_date,
            lookback_days=5,
        )

    total_turnover = snapshot_data.get("total_turnover")
    if total_turnover in (None, ""):
        observation = market_research_snapshot.get("observation", {}) if isinstance(market_research_snapshot, dict) else {}
        total_turnover = observation.get("turnover", 0.0) if isinstance(observation, dict) else 0.0

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

    if not snapshot_data.get("mainline_turnover_summary") and callable(helpers.get("build_mainline_turnover_summary")):
        snapshot_data["mainline_turnover_summary"] = helpers["build_mainline_turnover_summary"](
            target_date=target_date,
            current_mainline_history_record=snapshot_data.get("current_mainline_history_record") or {},
            recent_mainline_history=snapshot_data.get("recent_mainline_history") or [],
            current_sector_turnover_snapshot=snapshot_data.get("current_sector_turnover_snapshot") or {},
            recent_sector_turnover_history=snapshot_data.get("recent_sector_turnover_history") or [],
        )

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
        base_name = name.replace("(失败)", "").replace("(回补)", "").strip()
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
    snapshot_data = _ensure_report_mainline_atoms(snapshot_data, target_date, helpers=helpers)

    if "calendar_events" in refresh_sources:
        print_fn("   🔄 重新拉取财联社预期日历...")
        try:
            tencent = tencent_factory()
            calendar = tencent.get_calendar_events(target_date=target_date)
            if calendar:
                snapshot_data["calendar_events"] = calendar
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
