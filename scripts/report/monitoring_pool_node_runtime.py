def run_monitoring_pool_nodes(node_specs, context):
    lines = []
    exports = {}
    module_logs = []
    node_lookup = {spec['key']: spec for spec in (node_specs or [])}
    for spec in node_specs or []:
        result = spec['builder'](context, {'key': spec['key']}, node_lookup) or {}
        lines.extend(result.get('lines', []) or [])
        exports.update(result.get('exports', {}) or {})
        module_logs.extend(result.get('module_logs', []) or [])
    return {'lines': lines, 'exports': exports, 'module_logs': module_logs}
