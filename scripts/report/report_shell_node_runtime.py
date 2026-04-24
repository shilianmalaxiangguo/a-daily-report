def _append_log(logs, step, status, message, **details):
    logs.append(
        {
            "module": "report.report_shell_node_runtime",
            "step": step,
            "status": status,
            "message": message,
            "details": details,
        }
    )


def build_report_shell_node_lookup(node_specs):
    lookup = {}
    for index, spec in enumerate(node_specs or []):
        node_key = str(spec.get("node_key", "") or "").strip()
        if not node_key:
            continue
        title = str(spec.get("title", "") or node_key).strip() or node_key
        lookup[node_key] = {
            "node_key": node_key,
            "title": title,
            "node_no": index,
        }
    return lookup


def run_report_shell_nodes(node_specs, node_context=None, node_lookup=None):
    node_specs = list(node_specs or [])
    node_lookup = node_lookup or build_report_shell_node_lookup(node_specs)
    current_context = dict(node_context or {})
    aggregated_lines = []
    aggregated_logs = []
    node_outputs = {}
    executed_nodes = []

    for spec in node_specs:
        node_key = str(spec.get("node_key", "") or "").strip()
        builder = spec.get("builder")
        if not node_key or builder is None:
            continue

        node_meta = dict(node_lookup.get(node_key) or {})
        if not node_meta:
            node_meta = {
                "node_key": node_key,
                "title": str(spec.get("title", "") or node_key).strip() or node_key,
                "node_no": len(executed_nodes),
            }

        try:
            result = builder(current_context, node_meta, node_lookup) or {}
        except Exception as error:
            _append_log(
                aggregated_logs,
                f"run.{node_key}",
                "error",
                "执行 report shell node 失败",
                node_key=node_key,
                error=str(error),
            )
            raise

        lines = list(result.get("lines") or [])
        exports = dict(result.get("exports") or {})
        module_logs = list(result.get("module_logs") or [])

        aggregated_lines.extend(lines)
        aggregated_logs.extend(module_logs)
        node_outputs[node_key] = exports
        current_context.update(exports)
        executed_nodes.append(node_meta)
        _append_log(
            aggregated_logs,
            f"run.{node_key}",
            "success",
            "已执行 report shell node",
            node_key=node_key,
            line_count=len(lines),
            export_keys=sorted(exports.keys()),
        )

    return {
        "lines": aggregated_lines,
        "context": current_context,
        "module_logs": aggregated_logs,
        "node_outputs": node_outputs,
        "node_lookup": node_lookup,
        "nodes": executed_nodes,
    }
