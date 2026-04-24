from __future__ import annotations


def run_monitoring_pool_rule_nodes(node_specs, context=None):
    context = context or {}
    exports = {'main_pool': [], 'secondary_pool': []}
    logs = []
    for spec in node_specs or []:
        result = (spec.get('builder') or (lambda *_args, **_kwargs: {}))(context, node_meta=spec, exports=exports) or {}
        for key in ('main_pool', 'secondary_pool'):
            exports[key].extend(result.get(key, []) or [])
        logs.append({'node': spec.get('key'), 'status': 'success'})
    deduped = {'main_pool': [], 'secondary_pool': []}
    seen = set()
    for item in exports['main_pool']:
        code = item.get('stock_code') or item.get('code')
        if code and code not in seen:
            deduped['main_pool'].append(item)
            seen.add(code)
    for item in exports['secondary_pool']:
        code = item.get('stock_code') or item.get('code')
        if code and code not in seen:
            deduped['secondary_pool'].append(item)
            seen.add(code)
    return {'exports': deduped, 'module_logs': logs}
