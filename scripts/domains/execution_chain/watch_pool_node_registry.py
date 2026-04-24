DEFAULT_WATCH_POOL_NODE_SPECS = [
    {"node_key": "overview", "title": "阶段概览"},
    {"node_key": "trend_density", "title": "主线趋势密度扫描"},
    {"node_key": "mainline_competition", "title": "主线竞争格局"},
    {"node_key": "leader_memory", "title": "龙头记忆库"},
    {"node_key": "memory_validation", "title": "跟踪记忆校验"},
    {"node_key": "watch_ranking", "title": "明日预期强度排序"},
    {"node_key": "abnormal_watch", "title": "异动后观察池"},
    {"node_key": "abnormal_projection", "title": "异常投影总结"},
    {"node_key": "a_kill_filter", "title": "A杀过滤"},
    {"node_key": "conclusion", "title": "结论"},
]


def build_watch_pool_node_specs(builder_map, enabled_node_keys=None):
    builder_map = builder_map or {}
    enabled_node_keys = list(enabled_node_keys or [])
    enabled_key_set = set(enabled_node_keys) if enabled_node_keys else None

    specs = []
    for spec in DEFAULT_WATCH_POOL_NODE_SPECS:
        node_key = spec["node_key"]
        if enabled_key_set is not None and node_key not in enabled_key_set:
            continue
        builder = builder_map.get(node_key)
        if builder is None:
            continue
        specs.append({**spec, "builder": builder})
    return specs
