DEFAULT_LEGACY_STAGE_SUMMARY_NODE_SPECS = [
    {"node_key": "market_environment", "title": "环境与跟随裁决"},
    {"node_key": "selection_focus", "title": "明天观察池"},
    {"node_key": "anomaly_probe", "title": "异常探针"},
    {"node_key": "candidate_selection", "title": "主线核心与跨线观察"},
    {"node_key": "risk_review", "title": "明日风险预判"},
    {"node_key": "execution_plan", "title": "明日买点预计算"},
    {"node_key": "decisive_choice", "title": "唯一动作"},
]


def build_legacy_stage_summary_node_specs(builder_map, enabled_node_keys=None):
    builder_map = builder_map or {}
    enabled_node_keys = list(enabled_node_keys or [])
    default_meta = {spec["node_key"]: spec for spec in DEFAULT_LEGACY_STAGE_SUMMARY_NODE_SPECS}
    ordered_keys = enabled_node_keys if enabled_node_keys else list(builder_map.keys())

    specs = []
    for node_key in ordered_keys:
        builder = builder_map.get(node_key)
        if builder is None:
            continue
        spec_meta = default_meta.get(node_key, {"node_key": node_key, "title": node_key})
        specs.append({**spec_meta, "builder": builder})
    return specs
