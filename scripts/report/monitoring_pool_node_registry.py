def build_monitoring_pool_node_specs(builder_map, enabled_node_keys=None):
    enabled_node_keys = list(enabled_node_keys or [])
    ordered_keys = enabled_node_keys if enabled_node_keys else list(builder_map.keys())
    node_specs = []
    for key in ordered_keys:
        builder = builder_map.get(key)
        if callable(builder):
            node_specs.append({'key': key, 'builder': builder})
    return node_specs
