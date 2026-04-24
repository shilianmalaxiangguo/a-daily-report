DEFAULT_PK_DECISION_NODE_SPECS = [
    {"node_key": "overview", "title": "阶段概览"},
    {"node_key": "decision_stack", "title": "决策栈排序"},
    {"node_key": "single_candidate", "title": "单一候选"},
    {"node_key": "multi_candidate", "title": "多候选对比"},
    {"node_key": "pending_candidates", "title": "待触发候选"},
    {"node_key": "observation_candidates", "title": "观察分支"},
    {"node_key": "conclusion", "title": "结论"},
]


def build_pk_decision_node_specs(builder_map, enabled_node_keys=None):
    builder_map = builder_map or {}
    enabled_node_keys = list(enabled_node_keys or [])
    enabled_key_set = set(enabled_node_keys) if enabled_node_keys else None

    specs = []
    for spec in DEFAULT_PK_DECISION_NODE_SPECS:
        node_key = spec["node_key"]
        if enabled_key_set is not None and node_key not in enabled_key_set:
            continue
        builder = builder_map.get(node_key)
        if builder is None:
            continue
        specs.append({**spec, "builder": builder})
    return specs
