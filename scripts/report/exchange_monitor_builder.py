from report.exchange_monitor_nodes import build_exchange_monitor_section_result


def _append_log(logs, step, status, message, **details):
    logs.append(
        {
            "module": "report.exchange_monitor_builder",
            "step": step,
            "status": status,
            "message": message,
            "details": details,
        }
    )


def build_exchange_monitor_sections_contract(data, *, enabled_node_keys=None):
    data = data or {}
    node_result = build_exchange_monitor_section_result(
        {
            "data": data,
            "enabled_node_keys": enabled_node_keys,
        }
    )
    lines = list(node_result.get("lines") or [])
    logs = list(node_result.get("module_logs") or [])
    today_predictions = data.get("exchange_monitor_today", [])
    nextday_predictions = data.get("exchange_monitor_nextday", [])
    _append_log(
        logs,
        "render.exchange_monitor_sections",
        "success",
        "已生成异动监控章节",
        today_count=len(today_predictions),
        nextday_count=len(nextday_predictions),
    )
    return {
        "lines": lines,
        "module_logs": logs,
    }
