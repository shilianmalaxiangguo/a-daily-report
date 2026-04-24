DEFAULT_STRATEGY_PERFORMANCE_NODE_SPECS = [
    {"node_key": "header", "title": "策略计划账本标题"},
    {"node_key": "body", "title": "策略计划账本正文"},
]


def build_strategy_performance_node_specs(builder_map, enabled_node_keys=None):
    builder_map = builder_map or {}
    enabled_node_keys = list(enabled_node_keys or [])
    enabled_key_set = set(enabled_node_keys) if enabled_node_keys else None

    specs = []
    for spec in DEFAULT_STRATEGY_PERFORMANCE_NODE_SPECS:
        node_key = spec["node_key"]
        if enabled_key_set is not None and node_key not in enabled_key_set:
            continue
        builder = builder_map.get(node_key)
        if builder is None:
            continue
        specs.append({**spec, "builder": builder})
    return specs
