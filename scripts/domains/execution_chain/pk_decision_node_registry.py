DEFAULT_PK_DECISION_NODE_SPECS = [
    {"node_key": "score_candidates", "title": "候选决策栈"},
    {"node_key": "observation_pool", "title": "观察池"},
    {"node_key": "watch_anchor", "title": "观察锚点"},
    {"node_key": "probe_position", "title": "探针与仓位"},
    {"node_key": "front_texts", "title": "前摘要文本"},
    {"node_key": "pk_context", "title": "PK渲染上下文"},
    {"node_key": "action_plan_context", "title": "操作计划上下文"},
    {"node_key": "render_sections", "title": "渲染"},
    {"node_key": "export_stage_state", "title": "阶段导出"},
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
