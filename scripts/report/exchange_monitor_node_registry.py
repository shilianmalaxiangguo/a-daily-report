DEFAULT_EXCHANGE_MONITOR_NODE_SPECS = [
    {"node_key": "header", "title": "章节标题"},
    {"node_key": "source_note", "title": "数据提示"},
    {"node_key": "today_alerts", "title": "当日异动预警"},
    {"node_key": "nextday_alerts", "title": "次日异动预警"},
    {"node_key": "footer", "title": "章节收尾"},
]


def build_exchange_monitor_node_specs(builder_map, enabled_node_keys=None):
    builder_map = builder_map or {}
    enabled_node_keys = list(enabled_node_keys or [])
    enabled_key_set = set(enabled_node_keys) if enabled_node_keys else None

    specs = []
    for spec in DEFAULT_EXCHANGE_MONITOR_NODE_SPECS:
        node_key = spec["node_key"]
        if enabled_key_set is not None and node_key not in enabled_key_set:
            continue
        builder = builder_map.get(node_key)
        if builder is None:
            continue
        specs.append({**spec, "builder": builder})
    return specs
