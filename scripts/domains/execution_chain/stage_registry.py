DEFAULT_EXECUTION_STAGE_SPECS = [
    {"stage_key": "environment_follow", "title": "明日环境与跟随裁决"},
    {"stage_key": "watch_pool", "title": "明天观察池"},
    {"stage_key": "candidate_selection", "title": "明日核心标的"},
    {"stage_key": "risk_review", "title": "明日风险预判"},
    {"stage_key": "entry_plan", "title": "明日买点预计算"},
    {"stage_key": "pk_decision", "title": "PK决胜局（期望值模型）"},
]


def build_execution_stage_specs(builder_map, enabled_stage_keys=None):
    builder_map = builder_map or {}
    enabled_stage_keys = list(enabled_stage_keys or [])
    enabled_key_set = set(enabled_stage_keys) if enabled_stage_keys else None

    specs = []
    for spec in DEFAULT_EXECUTION_STAGE_SPECS:
        stage_key = spec["stage_key"]
        if enabled_key_set is not None and stage_key not in enabled_key_set:
            continue
        builder = builder_map.get(stage_key)
        if builder is None:
            continue
        specs.append({**spec, "builder": builder})
    return specs
