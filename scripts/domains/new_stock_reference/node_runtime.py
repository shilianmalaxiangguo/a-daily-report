def _append_log(logs, step, status, message, **details):
    logs.append(
        {
            "module": "domains.new_stock_reference.node_runtime",
            "step": step,
            "status": status,
            "message": message,
            "details": details,
        }
    )


def build_new_stock_reference_node_lookup(node_specs):
    lookup = {}
    for index, spec in enumerate(node_specs or []):
        node_key = str(spec.get("node_key", "") or "").strip()
        if not node_key:
            continue
        lookup[node_key] = {
            "node_key": node_key,
            "title": str(spec.get("title", "") or node_key).strip() or node_key,
            "node_no": index,
        }
    return lookup


def run_new_stock_reference_nodes(node_specs, node_context=None, node_lookup=None):
    node_specs = list(node_specs or [])
    node_lookup = node_lookup or build_new_stock_reference_node_lookup(node_specs)
    current_context = dict(node_context or {})
    aggregated_logs = []
    node_outputs = {}
    diagnostics = {}
    report_sections = {}
    artifacts = {}
    executed_nodes = []
    errors = []

    for spec in node_specs:
        node_key = str(spec.get("node_key", "") or "").strip()
        builder = spec.get("builder")
        if not node_key or builder is None:
            continue
        node_meta = dict(node_lookup.get(node_key) or {"node_key": node_key, "title": node_key})
        result = builder(current_context, node_meta, node_lookup) or {}
        exports = dict(result.get("exports") or {})
        context_patch = dict(result.get("context_patch") or {})
        current_context.update(exports)
        current_context.update(context_patch)
        node_outputs[node_key] = exports
        diagnostics[node_key] = dict(result.get("diagnostics") or {})
        report_sections.update(result.get("report_sections") or {})
        artifacts.update(result.get("artifacts") or {})
        aggregated_logs.extend(result.get("module_logs") or [])
        errors.extend(result.get("errors") or [])
        executed_nodes.append(node_meta)
        _append_log(
            aggregated_logs,
            f"run.{node_key}",
            "success",
            "已执行新股研究步骤",
            node_key=node_key,
            export_keys=sorted(exports.keys()),
            context_patch_keys=sorted(context_patch.keys()),
        )

    return {
        "context": current_context,
        "node_outputs": node_outputs,
        "diagnostics": diagnostics,
        "report_sections": report_sections,
        "artifacts": artifacts,
        "module_logs": aggregated_logs,
        "node_lookup": node_lookup,
        "nodes": executed_nodes,
        "errors": errors,
    }
