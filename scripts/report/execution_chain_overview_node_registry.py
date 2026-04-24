DEFAULT_EXECUTION_CHAIN_OVERVIEW_NODE_SPECS = [
    {"node_key": "header", "title": "执行链标题"},
    {"node_key": "market_summary", "title": "市场整体判断"},
    {"node_key": "path_header", "title": "六步路径标题"},
]


def build_execution_chain_overview_node_specs(builder_map, enabled_node_keys=None):
    builder_map = builder_map or {}
    enabled_node_keys = list(enabled_node_keys or [])
    enabled_key_set = set(enabled_node_keys) if enabled_node_keys else None

    specs = []
    for spec in DEFAULT_EXECUTION_CHAIN_OVERVIEW_NODE_SPECS:
        node_key = spec["node_key"]
        if enabled_key_set is not None and node_key not in enabled_key_set:
            continue
        builder = builder_map.get(node_key)
        if builder is None:
            continue
        specs.append({**spec, "builder": builder})
    return specs
