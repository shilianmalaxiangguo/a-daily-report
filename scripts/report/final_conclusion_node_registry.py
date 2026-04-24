DEFAULT_FINAL_CONCLUSION_NODE_SPECS = [
    {"node_key": "header", "title": "标题"},
    {"node_key": "table_header", "title": "表头"},
    {"node_key": "market_outlook", "title": "明日大盘预期"},
    {"node_key": "mvp_market", "title": "MVP市场环境"},
    {"node_key": "focus_recap", "title": "今日关注标的"},
    {"node_key": "mvp_mainline", "title": "MVP主看方向"},
    {"node_key": "mvp_focus", "title": "MVP观察池焦点"},
    {"node_key": "mvp_gate", "title": "MVP开仓裁决"},
    {"node_key": "mvp_probe", "title": "MVP异常探针"},
    {"node_key": "mvp_target", "title": "MVP目标"},
    {"node_key": "mvp_action", "title": "MVP唯一动作"},
    {"node_key": "style_summary", "title": "操作风格"},
    {"node_key": "risk_guard", "title": "盈亏比约束"},
    {"node_key": "mvp_discipline", "title": "MVP执行纪律"},
    {"node_key": "full_stage_rows", "title": "完整阶段行"},
    {"node_key": "full_strategy", "title": "完整策略行"},
    {"node_key": "full_discipline", "title": "完整执行纪律"},
    {"node_key": "footer", "title": "结尾空行"},
]


def build_final_conclusion_node_specs(builder_map, enabled_node_keys=None):
    builder_map = builder_map or {}
    enabled_node_keys = list(enabled_node_keys or [])
    enabled_key_set = set(enabled_node_keys) if enabled_node_keys else None

    specs = []
    for spec in DEFAULT_FINAL_CONCLUSION_NODE_SPECS:
        node_key = spec["node_key"]
        if enabled_key_set is not None and node_key not in enabled_key_set:
            continue
        builder = builder_map.get(node_key)
        if builder is None:
            continue
        specs.append({**spec, "builder": builder})
    return specs
