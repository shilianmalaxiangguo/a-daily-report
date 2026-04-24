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


def collect_calendar_events_request_bundle(
    target_date,
    *,
    fetch_calendar_events,
    timer,
    emit,
):
    results = {}
    data_status = {}
    step_status = {"预期日历获取": False}
    module_logs = []

    emit("  🔟 获取预期日历（财联社CLS）...")
    try:
        calendar = fetch_calendar_events(target_date=target_date)
        if calendar:
            results["calendar_events"] = calendar
            data_status["预期日历"] = True
            step_status["预期日历获取"] = True
            elapsed, _ = timer.record("预期日历获取", 10)
            emit(f"   ✅ 预期日历成功: {len(calendar)} 条 [⏱ {elapsed:.2f}s]")
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
