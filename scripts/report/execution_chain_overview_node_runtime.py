def run_execution_chain_overview_nodes(node_specs, node_context=None):
    current_context = dict(node_context or {})
    lines = []
    module_logs = []
    for index, spec in enumerate(node_specs or []):
        node_key = spec.get("node_key", "")
        builder = spec.get("builder")
        if not node_key or builder is None:
            continue
        result = builder(current_context, {"node_key": node_key, "node_no": index}, {}) or {}
        node_lines = list(result.get("lines") or [])
        lines.extend(node_lines)
        module_logs.append(
            {
                "module": "report.execution_chain_overview_node_runtime",
                "step": f"run.{node_key}",
                "status": "success",
                "message": "已执行 execution chain overview node",
                "details": {"node_key": node_key, "line_count": len(node_lines)},
            }
        )
    return {"lines": lines, "module_logs": module_logs, "context": current_context}
