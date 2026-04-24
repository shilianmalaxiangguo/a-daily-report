DEFAULT_RISK_REVIEW_NODE_SPECS = [
    {"node_key": "overview", "title": "阶段概览"},
    {"node_key": "stock_risk", "title": "逐只预判明日风险"},
    {"node_key": "sector_a_kill", "title": "板块级A杀预判"},
    {"node_key": "risk_groups", "title": "明日风险分组"},
    {"node_key": "sector_outlook", "title": "板块级明日风险预判"},
    {"node_key": "conclusion", "title": "结论"},
    {"node_key": "gem_pool", "title": "创业板20cm观察池"},
]


def build_risk_review_node_specs(builder_map, enabled_node_keys=None):
    builder_map = builder_map or {}
    enabled_node_keys = list(enabled_node_keys or [])
    enabled_key_set = set(enabled_node_keys) if enabled_node_keys else None

    specs = []
    for spec in DEFAULT_RISK_REVIEW_NODE_SPECS:
        node_key = spec["node_key"]
        if enabled_key_set is not None and node_key not in enabled_key_set:
            continue
        builder = builder_map.get(node_key)
        if builder is None:
            continue
        specs.append({**spec, "builder": builder})
    return specs
