DEFAULT_CALENDAR_SECTION_NODE_SPECS = [
    {"node_key": "header", "title": "章节标题"},
    {"node_key": "top_directions", "title": "热点分布"},
    {"node_key": "event_table", "title": "重点事件明细"},
    {"node_key": "insight_summary", "title": "AI板块关联分析"},
    {"node_key": "empty_state", "title": "空态"},
    {"node_key": "footer", "title": "章节收尾"},
]


def build_calendar_section_node_specs(builder_map, enabled_node_keys=None):
    builder_map = builder_map or {}
    enabled_node_keys = list(enabled_node_keys or [])
    enabled_key_set = set(enabled_node_keys) if enabled_node_keys else None

    specs = []
    for spec in DEFAULT_CALENDAR_SECTION_NODE_SPECS:
        node_key = spec["node_key"]
        if enabled_key_set is not None and node_key not in enabled_key_set:
            continue
        builder = builder_map.get(node_key)
        if builder is None:
            continue
        specs.append({**spec, "builder": builder})
    return specs
