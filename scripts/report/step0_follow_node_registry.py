DEFAULT_STEP0_FOLLOW_NODE_SPECS = [
    {"node_key": "verdict", "title": "明日裁决"},
    {"node_key": "table_header", "title": "证据表头"},
    {"node_key": "risk_preference", "title": "盘面风险偏好"},
    {"node_key": "style_background", "title": "风格背景"},
    {"node_key": "mainline_focus", "title": "主线焦点"},
    {"node_key": "abnormal_projection", "title": "异常承接证据"},
    {"node_key": "state_summary", "title": "最终状态判断"},
    {"node_key": "conclusion", "title": "Step 0 结论"},
    {"node_key": "reminder", "title": "重要提醒"},
    {"node_key": "footer", "title": "章节收尾"},
]

FULL_MODE_EVIDENCE_NODE_KEYS = {
    "risk_preference",
    "style_background",
    "mainline_focus",
    "abnormal_projection",
    "state_summary",
}


def build_step0_follow_node_specs(builder_map, enabled_node_keys=None, compact=False):
    builder_map = builder_map or {}
    enabled_node_keys = list(enabled_node_keys or [])
    enabled_key_set = set(enabled_node_keys) if enabled_node_keys else None

    if not compact and enabled_key_set is not None and enabled_key_set & FULL_MODE_EVIDENCE_NODE_KEYS:
        enabled_key_set.add("table_header")

    specs = []
    for spec in DEFAULT_STEP0_FOLLOW_NODE_SPECS:
        node_key = spec["node_key"]
        if enabled_key_set is not None and node_key not in enabled_key_set:
            continue
        builder = builder_map.get(node_key)
        if builder is None:
            continue
        specs.append({**spec, "builder": builder})
    return specs
