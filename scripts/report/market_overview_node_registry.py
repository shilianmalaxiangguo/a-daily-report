DEFAULT_MARKET_OVERVIEW_NODE_SPECS = [
    {"node_key": "header", "title": "章节标题"},
    {"node_key": "indices", "title": "指数表现"},
    {"node_key": "volume", "title": "量能分析"},
    {"node_key": "price_band_style", "title": "价格带风格"},
    {"node_key": "new_high", "title": "创新高趋势反馈"},
    {"node_key": "margin_pressure", "title": "融资承接压力"},
    {"node_key": "sentiment", "title": "市场情绪"},
]


def build_market_overview_node_specs(builder_map, enabled_node_keys=None):
    builder_map = builder_map or {}
    enabled_node_keys = list(enabled_node_keys or [])
    enabled_key_set = set(enabled_node_keys) if enabled_node_keys else None

    specs = []
    for spec in DEFAULT_MARKET_OVERVIEW_NODE_SPECS:
        node_key = spec["node_key"]
        if enabled_key_set is not None and node_key not in enabled_key_set:
            continue
        builder = builder_map.get(node_key)
        if builder is None:
            continue
        specs.append({**spec, "builder": builder})
    return specs
