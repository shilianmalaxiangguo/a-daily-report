DEFAULT_CONTEXT_TAIL_NODE_SPECS = [
    {"node_key": "mainline_discipline", "title": "主线执行纪律"},
    {"node_key": "supplementary_perspective", "title": "补充观察"},
    {"node_key": "market_insight", "title": "市场快照"},
]


def build_context_tail_node_specs(builder_map, enabled_node_keys=None):
    builder_map = builder_map or {}
    enabled_node_keys = list(enabled_node_keys or [])
    enabled_key_set = set(enabled_node_keys) if enabled_node_keys else None

    specs = []
    for spec in DEFAULT_CONTEXT_TAIL_NODE_SPECS:
        node_key = spec["node_key"]
        if enabled_key_set is not None and node_key not in enabled_key_set:
            continue
        builder = builder_map.get(node_key)
        if builder is None:
            continue
        specs.append({**spec, "builder": builder})
    return specs
