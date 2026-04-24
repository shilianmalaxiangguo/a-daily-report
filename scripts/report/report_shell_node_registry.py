DEFAULT_REPORT_SHELL_NODE_SPECS = [
    {"node_key": "preamble", "title": "报告前言"},
    {"node_key": "discipline_header", "title": "纪律标题"},
    {"node_key": "blank_after_header", "title": "标题后空行"},
    {"node_key": "discipline_intro", "title": "纪律引导"},
    {"node_key": "blank_after_intro", "title": "引导后空行"},
    {"node_key": "discipline_placeholder", "title": "纪律占位符"},
    {"node_key": "footer", "title": "章节收尾"},
]

DEFAULT_PROHIBITION_SECTION_NODE_SPECS = [
    {"node_key": "environment", "title": "次日市场环境"},
    {"node_key": "blank_after_environment", "title": "环境后空行"},
    {"node_key": "prohibition_header", "title": "禁止事项标题"},
    {"node_key": "prohibition_items", "title": "禁止事项列表"},
    {"node_key": "blank_before_allowed", "title": "允许事项前空行"},
    {"node_key": "allowed_header", "title": "允许事项标题"},
    {"node_key": "allowed_items", "title": "允许事项列表"},
    {"node_key": "blank_before_risk", "title": "风险板块前空行"},
    {"node_key": "risk_section", "title": "风险板块"},
]


def _build_node_specs(default_specs, builder_map, enabled_node_keys=None):
    builder_map = builder_map or {}
    enabled_node_keys = list(enabled_node_keys or [])
    enabled_key_set = set(enabled_node_keys) if enabled_node_keys else None

    specs = []
    for spec in default_specs:
        node_key = spec["node_key"]
        if enabled_key_set is not None and node_key not in enabled_key_set:
            continue
        builder = builder_map.get(node_key)
        if builder is None:
            continue
        specs.append({**spec, "builder": builder})
    return specs


def build_report_shell_node_specs(builder_map, enabled_node_keys=None):
    return _build_node_specs(DEFAULT_REPORT_SHELL_NODE_SPECS, builder_map, enabled_node_keys=enabled_node_keys)


def build_prohibition_section_node_specs(builder_map, enabled_node_keys=None):
    return _build_node_specs(DEFAULT_PROHIBITION_SECTION_NODE_SPECS, builder_map, enabled_node_keys=enabled_node_keys)
