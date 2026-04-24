DEFAULT_APPENDIX_NODE_SPECS = [
    {"node_key": "header", "title": "附录标题"},
    {"node_key": "data_status", "title": "数据获取清单"},
    {"node_key": "step_status", "title": "执行步骤清单"},
    {"node_key": "summary_stats", "title": "统计信息"},
    {"node_key": "metadata", "title": "报告元信息"},
    {"node_key": "timer_stats", "title": "执行时间统计"},
]


def build_appendix_node_specs(builder_map, enabled_node_keys=None):
    builder_map = builder_map or {}
    enabled_node_keys = list(enabled_node_keys or [])
    enabled_key_set = set(enabled_node_keys) if enabled_node_keys else None

    specs = []
    for spec in DEFAULT_APPENDIX_NODE_SPECS:
        node_key = spec["node_key"]
        if enabled_key_set is not None and node_key not in enabled_key_set:
            continue
        builder = builder_map.get(node_key)
        if builder is None:
            continue
        specs.append({**spec, "builder": builder})
    return specs
