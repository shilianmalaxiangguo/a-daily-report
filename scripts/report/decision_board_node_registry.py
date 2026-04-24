DEFAULT_DECISION_BOARD_NODE_SPECS = [
    {"node_key": "header", "title": "章节标题"},
    {"node_key": "market_snapshot_placeholder", "title": "市场快照占位"},
    {"node_key": "mvp_digest_placeholder", "title": "MVP摘要占位"},
    {"node_key": "mainline_section", "title": "主线方向"},
    {"node_key": "positioning_section", "title": "仓位决策"},
    {"node_key": "risk_section", "title": "风险提示"},
    {"node_key": "footer", "title": "章节收尾"},
]


def build_decision_board_node_specs(builder_map, enabled_node_keys=None):
    builder_map = builder_map or {}
    enabled_node_keys = list(enabled_node_keys or [])
    enabled_key_set = set(enabled_node_keys) if enabled_node_keys else None

    specs = []
    for spec in DEFAULT_DECISION_BOARD_NODE_SPECS:
        node_key = spec["node_key"]
        if enabled_key_set is not None and node_key not in enabled_key_set:
            continue
        builder = builder_map.get(node_key)
        if builder is None:
            continue
        specs.append({**spec, "builder": builder})
    return specs
