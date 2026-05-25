from report.market_overview_nodes import build_market_overview_section_result


def _append_log(logs, step, status, message, **details):
    logs.append(
        {
            "module": "report.market_overview_builder",
            "step": step,
            "status": status,
            "message": message,
            "details": details,
        }
    )


def build_market_trend_sections_contract(data, target_date, *, enabled_node_keys=None, daily_fact_db_path=None):
    data = data or {}
    node_result = build_market_overview_section_result(
        {
            "data": data,
            "target_date": target_date,
            "enabled_node_keys": enabled_node_keys,
            "daily_fact_db_path": daily_fact_db_path,
        }
    )
    lines = list(node_result.get("lines") or [])
    logs = list(node_result.get("module_logs") or [])
    turnover = data.get("total_turnover", 0)
    zt_count = len(data.get("zt_pool", []))
    dt_count = len(data.get("dt_pool", []))

    _append_log(
        logs,
        "render.market_trend_sections",
        "success",
        "已生成大盘趋势判断章节",
        index_count=len(data.get("indices", {}) or {}),
        turnover=turnover,
        zt_count=zt_count,
        dt_count=dt_count,
    )
    return {
        "lines": lines,
        "module_logs": logs,
    }
