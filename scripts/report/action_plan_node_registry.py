DEFAULT_ACTION_PLAN_NODE_SPECS = [
    {"node_key": "overview", "title": "阶段概览"},
    {"node_key": "action_table", "title": "最终动作表"},
    {"node_key": "candidate_quality", "title": "候选证据附录"},
    {"node_key": "observation_blocks", "title": "观察补充"},
    {"node_key": "positioning", "title": "明天仓位怎么放"},
    {"node_key": "schedule", "title": "明日执行时间表"},
    {"node_key": "alerts", "title": "异动预警"},
]


def build_action_plan_node_specs(builder_map, enabled_node_keys=None):
    builder_map = builder_map or {}
    enabled_node_keys = list(enabled_node_keys or [])
    enabled_key_set = set(enabled_node_keys) if enabled_node_keys else None

    specs = []
    for spec in DEFAULT_ACTION_PLAN_NODE_SPECS:
        node_key = spec["node_key"]
        if enabled_key_set is not None and node_key not in enabled_key_set:
            continue
        builder = builder_map.get(node_key)
        if builder is None:
            continue
        specs.append({**spec, "builder": builder})
    return specs
