from report.board_tag_analysis_nodes import build_board_tag_analysis_section_result


def _append_log(logs, step, status, message, **details):
    logs.append(
        {
            "module": "report.board_tag_analysis_builder",
            "step": step,
            "status": status,
            "message": message,
            "details": details,
        }
    )


def build_board_tag_analysis_sections_contract(data, *, analyze_sector_distribution, enabled_node_keys=None):
    data = data or {}
    node_result = build_board_tag_analysis_section_result(
        {
            "data": data,
            "analyze_sector_distribution": analyze_sector_distribution,
            "enabled_node_keys": enabled_node_keys,
        }
    )
    lines = list(node_result.get("lines") or [])
    logs = list(node_result.get("module_logs") or [])
    tag_distribution = data.get("tag_distribution", {})

    _append_log(
        logs,
        "render.board_tag_analysis",
        "success",
        "已生成板块标签分析章节",
        tag_count=len(tag_distribution),
    )
    return {
        "lines": lines,
        "module_logs": logs,
    }
