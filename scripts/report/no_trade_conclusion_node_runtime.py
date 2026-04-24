def run_no_trade_conclusion_nodes(node_specs, node_context=None):
    context = dict(node_context or {})
    lines = []
    module_logs = []
    for index, spec in enumerate(node_specs or []):
        node_key = spec.get("node_key", "")
        builder = spec.get("builder")
        if not node_key or builder is None:
            continue
        result = builder(context, {"node_key": node_key, "node_no": index}, {}) or {}
        node_lines = list(result.get("lines") or [])
        lines.extend(node_lines)
        module_logs.append(
            {
                "module": "report.no_trade_conclusion_node_runtime",
                "step": f"run.{node_key}",
                "status": "success",
                "message": "已执行 no trade conclusion node",
                "details": {"node_key": node_key, "line_count": len(node_lines)},
            }
        )
    return {"lines": lines, "module_logs": module_logs, "context": context}
