def _append_log(logs, step, status, message, **details):
    logs.append(
        {
            "module": "domains.calendar_events.request",
            "step": step,
            "status": status,
            "message": message,
            "details": details,
        }
    )


def _calendar_event_source_date(event):
    if not isinstance(event, dict):
        return ""
    return str(
        event.get("source_date")
        or event.get("trade_date")
        or event.get("date")
        or event.get("calendar_day")
        or ""
    ).strip()


def _annotate_calendar_events(events, *, query_date, calendar_scope):
    annotated = []
    for event in events or []:
        if not isinstance(event, dict):
            annotated.append(event)
            continue
        item = dict(event)
        item.setdefault("query_date", query_date)
        item.setdefault("calendar_scope", calendar_scope)
        source_date = _calendar_event_source_date(item)
        if source_date:
            item.setdefault("source_date", source_date)
        annotated.append(item)
    return annotated


def _fetch_calendar_events_compat(
    fetch_calendar_events,
    target_date,
    *,
    target_date_only=False,
):
    if target_date_only:
        events = fetch_calendar_events(target_date=target_date)
        return (
            _annotate_calendar_events(
                events or [],
                query_date=target_date,
                calendar_scope="target_date",
            ),
            "target_date",
        )

    try:
        window_events = fetch_calendar_events()
        if window_events:
            return (
                _annotate_calendar_events(
                    window_events,
                    query_date=target_date,
                    calendar_scope="upcoming_window",
                ),
                "upcoming_window",
            )
    except TypeError as error:
        error_text = str(error)
        if (
            "target_date" not in error_text
            or "required" not in error_text
            or "argument" not in error_text
        ):
            raise

    try:
        events = fetch_calendar_events(target_date=target_date)
        if events:
            return _annotate_calendar_events(events, query_date=target_date, calendar_scope="target_date"), "target_date"
        return [], "target_date"
    except TypeError as error:
        error_text = str(error)
        if "target_date" not in error_text or "unexpected keyword argument" not in error_text:
            raise
        return (
            _annotate_calendar_events(
                fetch_calendar_events(),
                query_date=target_date,
                calendar_scope="legacy_unfiltered",
            ),
            "legacy_unfiltered",
        )


def collect_calendar_events_request_bundle(
    target_date,
    *,
    fetch_calendar_events,
    target_date_only=False,
    timer,
    emit,
):
    results = {}
    data_status = {}
    step_status = {"预期日历获取": False}
    module_logs = []

    emit("  🔟 获取预期日历（财联社CLS）...")
    try:
        calendar, calendar_scope = _fetch_calendar_events_compat(
            fetch_calendar_events,
            target_date,
            target_date_only=target_date_only,
        )
        if calendar:
            results["calendar_events"] = calendar
            data_status["预期日历"] = True
            step_status["预期日历获取"] = True
            elapsed, _ = timer.record("预期日历获取", 10)
            scope_note = {
                "upcoming_window": "后续窗口",
                "legacy_unfiltered": "兼容窗口",
            }.get(calendar_scope, "目标日期")
            emit(f"   ✅ 预期日历成功({scope_note}): {len(calendar)} 条 [⏱ {elapsed:.2f}s]")
        else:
            results["calendar_events"] = []
            data_status["预期日历"] = False
            elapsed, _ = timer.record("预期日历获取(失败)", 10)
            emit(f"   ❌ 预期日历返回空 [⏱ {elapsed:.2f}s]")
        _append_log(
            module_logs,
            "request.calendar_events",
            "success" if data_status.get("预期日历") else "degraded",
            "已处理预期日历请求",
            provider="tencent.get_calendar_events",
            target_keys=["calendar_events"],
            calendar_count=len(results.get("calendar_events", [])),
            calendar_scope=calendar_scope,
            query_date=target_date,
            source_dates=[
                _calendar_event_source_date(event)
                for event in results.get("calendar_events", [])
                if _calendar_event_source_date(event)
            ],
        )
    except Exception as error:
        results["calendar_events"] = []
        data_status["预期日历"] = False
        emit(f"   ❌ 预期日历失败: {error}")
        _append_log(
            module_logs,
            "request.calendar_events",
            "error",
            "预期日历请求失败",
            provider="tencent.get_calendar_events",
            target_keys=["calendar_events"],
            error=str(error),
        )

    return {
        "results": results,
        "data_status": data_status,
        "step_status": step_status,
        "module_logs": module_logs,
    }
