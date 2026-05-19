DEFAULT_MARKET_RESEARCH_SNAPSHOT_NODE_SPECS = [
    {"node_key": "header", "title": "章节标题"},
    {"node_key": "cycle_calendar", "title": "周期日历主视图"},
    {"node_key": "cycle_interpretation", "title": "周期解读"},
    {"node_key": "pivot_mainline_interpretation", "title": "中枢与主线解读"},
    {"node_key": "mainline_capacity_regime", "title": "主线容量与格局判断"},
    {"node_key": "table_header", "title": "证据表头"},
    {"node_key": "risk_preference", "title": "盘面风险偏好"},
    {"node_key": "mainline_focus", "title": "主线焦点"},
    {"node_key": "mainline_turnover", "title": "主线更替与成交额占比"},
    {"node_key": "rotation", "title": "主线内部轮动"},
    {"node_key": "narrative", "title": "叙事节点"},
    {"node_key": "style_background", "title": "风格背景"},
    {"node_key": "abnormal_projection", "title": "异常承接证据"},
    {"node_key": "follow_verdict", "title": "明天能不能开仓"},
    {"node_key": "state_summary", "title": "统一状态判断"},
    {"node_key": "leader_memory", "title": "龙头记忆"},
    {"node_key": "trend_density", "title": "最强趋势密度"},
    {"node_key": "style_note", "title": "风格说明"},
    {"node_key": "dialectical_decision", "title": "辩证决策补充"},
    {"node_key": "footer", "title": "章节收尾"},
]

FULL_MODE_EVIDENCE_NODE_KEYS = {
    "risk_preference",
    "mainline_focus",
    "mainline_turnover",
    "rotation",
    "narrative",
    "style_background",
    "abnormal_projection",
    "follow_verdict",
}


def build_market_research_snapshot_node_specs(builder_map, enabled_node_keys=None, compact=False):
    builder_map = builder_map or {}
    enabled_node_keys = list(enabled_node_keys or [])
    enabled_key_set = set(enabled_node_keys) if enabled_node_keys else None

    if not compact and enabled_key_set is not None and enabled_key_set & FULL_MODE_EVIDENCE_NODE_KEYS:
        enabled_key_set.add("table_header")

    specs = []
    for spec in DEFAULT_MARKET_RESEARCH_SNAPSHOT_NODE_SPECS:
        node_key = spec["node_key"]
        if enabled_key_set is not None and node_key not in enabled_key_set:
            continue
        builder = builder_map.get(node_key)
        if builder is None:
            continue
        specs.append({**spec, "builder": builder})
    return specs
