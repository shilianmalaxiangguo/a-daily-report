DEFAULT_ENTRY_PLAN_NODE_SPECS = [
    {"node_key": "overview", "title": "阶段概览"},
    {"node_key": "priority_discipline", "title": "交易优先级纪律"},
    {"node_key": "entry_judgement", "title": "买点判断"},
    {"node_key": "trigger_summary", "title": "明日触发条件汇总"},
    {"node_key": "stop_anchor", "title": "明日止损锚定"},
    {"node_key": "conclusion", "title": "结论"},
]


def build_entry_plan_node_specs(builder_map, enabled_node_keys=None):
    builder_map = builder_map or {}
    enabled_node_keys = list(enabled_node_keys or [])
    enabled_key_set = set(enabled_node_keys) if enabled_node_keys else None

    specs = []
    for spec in DEFAULT_ENTRY_PLAN_NODE_SPECS:
        node_key = spec["node_key"]
        if enabled_key_set is not None and node_key not in enabled_key_set:
            continue
        builder = builder_map.get(node_key)
        if builder is None:
            continue
        specs.append({**spec, "builder": builder})
    return specs
