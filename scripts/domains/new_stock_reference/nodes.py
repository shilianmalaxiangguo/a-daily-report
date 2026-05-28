from selection.new_stock_narrative_runtime import build_new_stock_research_pool


def _append_log(logs, step, status, message, **details):
    logs.append(
        {
            "module": "domains.new_stock_reference.nodes",
            "step": step,
            "status": status,
            "message": message,
            "details": details,
        }
    )


def build_new_stock_request_node(context, node_meta=None, node_lookup=None):
    calendar = list((context or {}).get("new_stock_calendar") or [])
    logs = []
    _append_log(
        logs,
        "request.new_stock_calendar",
        "success",
        "已复用新股上市日历",
        calendar_count=len(calendar),
    )
    return {
        "exports": {"new_stock_calendar": calendar},
        "diagnostics": {"calendar_count": len(calendar)},
        "module_logs": logs,
    }


def build_new_stock_score_node(context, node_meta=None, node_lookup=None):
    result = build_new_stock_research_pool(
        (context or {}).get("new_stock_calendar", []),
        target_date=(context or {}).get("target_date", ""),
        context=(context or {}).get("new_stock_context", {}),
    )
    research_pool = list((result or {}).get("new_stock_research_pool") or [])
    upgrades = list((result or {}).get("new_stock_candidate_upgrades") or [])
    logs = []
    _append_log(
        logs,
        "score.new_stock_narrative",
        "success",
        "已完成新股研究池评分",
        research_count=len(research_pool),
        upgrade_count=len(upgrades),
    )
    return {
        "exports": {
            "new_stock_research_pool": research_pool,
            "new_stock_candidate_upgrades": upgrades,
        },
        "diagnostics": {
            "research_count": len(research_pool),
            "upgrade_count": len(upgrades),
        },
        "module_logs": logs,
    }


def build_new_stock_candidate_merge_node(context, node_meta=None, node_lookup=None):
    upgrades = list((context or {}).get("new_stock_candidate_upgrades") or [])
    return {
        "exports": {"new_stock_candidate_upgrades": upgrades},
        "diagnostics": {"upgrade_count": len(upgrades)},
        "module_logs": [],
    }


def build_new_stock_report_node(context, node_meta=None, node_lookup=None):
    research_pool = list((context or {}).get("new_stock_research_pool") or [])
    upgrades = list((context or {}).get("new_stock_candidate_upgrades") or [])
    if upgrades:
        lines = ["有新股研究升级，进入观察。"]
    elif research_pool:
        lines = ["有新股研究池，但今日未形成买入资格。"]
    else:
        lines = ["新股研究池为空，今日不参与。"]
    return {
        "exports": {"new_stock_report_lines": lines},
        "report_sections": {"new_stock_research": lines},
        "diagnostics": {
            "research_count": len(research_pool),
            "upgrade_count": len(upgrades),
        },
        "module_logs": [],
    }


def build_new_stock_audit_node(context, node_meta=None, node_lookup=None):
    lines = list((context or {}).get("new_stock_report_lines") or [])
    passed = bool(lines)
    return {
        "exports": {"new_stock_audit_passed": passed},
        "diagnostics": {"passed": passed, "line_count": len(lines)},
        "module_logs": [],
    }
