def _append_log(logs, step, status, message, **details):
    logs.append(
        {
            "module": "report.strategy_performance_node_runtime",
            "step": step,
            "status": status,
            "message": message,
            "details": details,
        }
    )


def run_strategy_performance_nodes(node_specs, node_context=None):
    current_context = dict(node_context or {})
    aggregated_lines = []
    aggregated_logs = []
    node_outputs = {}

    for index, spec in enumerate(node_specs or []):
        node_key = str(spec.get("node_key", "") or "").strip()
        builder = spec.get("builder")
        if not node_key or builder is None:
            continue
        node_meta = {
            "node_key": node_key,
            "title": str(spec.get("title", "") or node_key).strip() or node_key,
            "node_no": index,
        }
        result = builder(current_context, node_meta, {}) or {}
        lines = list(result.get("lines") or [])
        exports = dict(result.get("exports") or {})
        aggregated_lines.extend(lines)
        aggregated_logs.extend(result.get("module_logs") or [])
        node_outputs[node_key] = exports
        current_context.update(exports)
        _append_log(
            aggregated_logs,
            f"run.{node_key}",
            "success",
            "已执行 strategy performance node",
            node_key=node_key,
            line_count=len(lines),
        )

    return {
        "lines": aggregated_lines,
        "context": current_context,
        "module_logs": aggregated_logs,
        "node_outputs": node_outputs,
    }
