DEFAULT_CANDIDATE_SELECTION_NODE_SPECS = [
    {"node_key": "overview", "title": "阶段概览"},
    {"node_key": "trend_density_review", "title": "主线趋势密度复核"},
    {"node_key": "core_candidates", "title": "明日核心预判"},
    {"node_key": "secondary_candidates", "title": "明日次核心预判"},
    {"node_key": "crossline_watch", "title": "跨线观察候选"},
    {"node_key": "ignored_candidates", "title": "暂不关注"},
    {"node_key": "mainline_summary", "title": "明日核心方向预判"},
    {"node_key": "conviction_list", "title": "极度看好名单"},
    {"node_key": "quadrant_analysis", "title": "击球区判断"},
    {"node_key": "conclusion", "title": "结论"},
]


def build_candidate_selection_node_specs(builder_map, enabled_node_keys=None):
    builder_map = builder_map or {}
    enabled_node_keys = list(enabled_node_keys or [])
    enabled_key_set = set(enabled_node_keys) if enabled_node_keys else None

    specs = []
    for spec in DEFAULT_CANDIDATE_SELECTION_NODE_SPECS:
        node_key = spec["node_key"]
        if enabled_key_set is not None and node_key not in enabled_key_set:
            continue
        builder = builder_map.get(node_key)
        if builder is None:
            continue
        specs.append({**spec, "builder": builder})
    return specs
