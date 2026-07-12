DEFAULT_POSITIONING_NODE_SPECS = [
    {"node_key": "header", "title": "章节标题"},
    {"node_key": "execution_framework", "title": "执行框架"},
    {"node_key": "structure_note", "title": "结构说明"},
    {"node_key": "intraday_note", "title": "盘中说明"},
    {"node_key": "environment_status", "title": "明日市场环境"},
    {"node_key": "structure_range", "title": "结构区间"},
    {"node_key": "ascii_diagram", "title": "大盘结构图"},
    {"node_key": "state_basis", "title": "状态依据"},
    {"node_key": "structure_overview", "title": "结构识别概览"},
    {"node_key": "zhongshu_table", "title": "结构中枢表"},
    {"node_key": "connector_segments", "title": "过渡结构"},
    {"node_key": "error_state", "title": "异常状态"},
    {"node_key": "footer", "title": "章节收尾"},
]


def build_positioning_node_specs(builder_map, enabled_node_keys=None):
    builder_map = builder_map or {}
    enabled_node_keys = list(enabled_node_keys or [])
    enabled_key_set = set(enabled_node_keys) if enabled_node_keys else None

    specs = []
    for spec in DEFAULT_POSITIONING_NODE_SPECS:
        node_key = spec["node_key"]
        if enabled_key_set is not None and node_key not in enabled_key_set:
            continue
        builder = builder_map.get(node_key)
        if builder is None:
            continue
        specs.append({**spec, "builder": builder})
    return specs
