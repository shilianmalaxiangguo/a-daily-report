DEFAULT_BOARD_TAG_ANALYSIS_NODE_SPECS = [
    {"node_key": "header", "title": "章节标题"},
    {"node_key": "source_note", "title": "数据提示"},
    {"node_key": "tag_rank_chart", "title": "标签热度排行榜"},
    {"node_key": "analysis", "title": "板块分布AI分析"},
    {"node_key": "footer", "title": "章节收尾"},
]


def build_board_tag_analysis_node_specs(builder_map, enabled_node_keys=None):
    builder_map = builder_map or {}
    enabled_node_keys = list(enabled_node_keys or [])
    enabled_key_set = set(enabled_node_keys) if enabled_node_keys else None

    specs = []
    for spec in DEFAULT_BOARD_TAG_ANALYSIS_NODE_SPECS:
        node_key = spec["node_key"]
        if enabled_key_set is not None and node_key not in enabled_key_set:
            continue
        builder = builder_map.get(node_key)
        if builder is None:
            continue
        specs.append({**spec, "builder": builder})
    return specs
