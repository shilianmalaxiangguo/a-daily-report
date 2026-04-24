def run_appendix_nodes(node_specs, node_context=None):
    current_context = dict(node_context or {})
    aggregated_lines = []
    for spec in node_specs or []:
        builder = spec.get("builder")
        if builder is None:
            continue
        result = builder(current_context, spec, {}) or {}
        aggregated_lines.extend(result.get("lines") or [])
        current_context.update(result.get("exports") or {})
    return {"lines": aggregated_lines, "context": current_context}
