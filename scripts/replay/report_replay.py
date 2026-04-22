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
