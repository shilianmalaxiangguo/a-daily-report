from report.market_analysis_nodes import build_market_analysis_section_result


def _append_log(logs, step, status, message, **details):
    logs.append(
        {
            "module": "report.market_analysis_builder",
            "step": step,
            "status": status,
            "message": message,
            "details": details,
        }
    )


def build_market_and_sector_analysis_contract(
    data,
    market_analysis,
    sh_change,
    indices,
    exit_analysis,
    main_sectors_info,
    secondary_sectors_info,
    *,
    ai_group_concepts_into_chains,
    enabled_node_keys=None,
    target_date="",
):
    data = data or {}
    market_analysis = market_analysis or {}
    indices = indices or {}
    exit_analysis = exit_analysis or {}
    main_sectors_info = main_sectors_info or []
    secondary_sectors_info = secondary_sectors_info or []
    target_date = target_date or data.get("target_date", "")
    node_result = build_market_analysis_section_result(
        {
            "data": data,
            "market_analysis": market_analysis,
            "sh_change": sh_change,
            "indices": indices,
            "exit_analysis": exit_analysis,
            "main_sectors_info": main_sectors_info,
            "secondary_sectors_info": secondary_sectors_info,
            "ai_group_concepts_into_chains": ai_group_concepts_into_chains,
            "enabled_node_keys": enabled_node_keys,
            "target_date": target_date,
        }
    )
    lines = list(node_result.get("lines") or [])
    logs = list(node_result.get("module_logs") or [])
    hot_sectors = market_analysis.get("hot_sectors", [])
    risk_sectors = market_analysis.get("risk_sectors", [])
    mainline_name = exit_analysis.get("sector_name", "") if exit_analysis else ""

    _append_log(
        logs,
        "render.market_and_sector_analysis",
        "success",
        "已生成市场与板块分析章节",
        hot_sector_count=len(hot_sectors),
        risk_sector_count=len(risk_sectors),
        mainline_name=mainline_name,
    )
    return {
        "lines": lines,
        "module_logs": logs,
    }
