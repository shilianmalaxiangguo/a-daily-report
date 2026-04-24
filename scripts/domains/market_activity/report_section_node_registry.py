DEFAULT_MARKET_ACTIVITY_BASIC_NODE_SPECS = [
    {"node_key": "hot_rank_header", "title": "热度核心结果标题"},
    {"node_key": "hot_rank_table", "title": "热度核心结果表"},
    {"node_key": "turnover_header", "title": "成交核心结果标题"},
    {"node_key": "turnover_table", "title": "成交核心结果表"},
    {"node_key": "sector_fund_header", "title": "行业资金结果标题"},
    {"node_key": "sector_fund_inflow", "title": "行业资金流入结果"},
    {"node_key": "sector_fund_outflow", "title": "行业资金流出结果"},
    {"node_key": "lhb_header", "title": "龙虎榜结果标题"},
    {"node_key": "lhb_buy", "title": "龙虎榜净买入结果"},
    {"node_key": "lhb_sell", "title": "龙虎榜净流出结果"},
]

MARKET_ACTIVITY_BASIC_NODE_ALIASES = {
    "hot_rank": ["hot_rank_header", "hot_rank_table"],
    "turnover": ["turnover_header", "turnover_table"],
    "sector_fund_flow": ["sector_fund_header", "sector_fund_inflow", "sector_fund_outflow"],
    "lhb": ["lhb_header", "lhb_buy", "lhb_sell"],
}

DEFAULT_MARKET_ACTIVITY_ADVANCED_NODE_SPECS = [
    {"node_key": "lianban", "title": "连板结果"},
    {"node_key": "advanced_header", "title": "多维交易结果标题"},
    {"node_key": "volume_anomalies", "title": "放量结果"},
    {"node_key": "lhb_analysis", "title": "龙虎榜结果"},
    {"node_key": "resonance_scores", "title": "板块共振结果"},
    {"node_key": "trade_signals", "title": "交易信号结果"},
]


def build_market_activity_basic_node_specs(builder_map, enabled_node_keys=None):
    builder_map = builder_map or {}
    requested_node_keys = list(enabled_node_keys or [])
    enabled_node_keys = []
    for node_key in requested_node_keys:
        enabled_node_keys.extend(MARKET_ACTIVITY_BASIC_NODE_ALIASES.get(node_key, [node_key]))
    enabled_key_set = set(enabled_node_keys) if enabled_node_keys else None

    specs = []
    for spec in DEFAULT_MARKET_ACTIVITY_BASIC_NODE_SPECS:
        node_key = spec["node_key"]
        if enabled_key_set is not None and node_key not in enabled_key_set:
            continue
        builder = builder_map.get(node_key)
        if builder is None:
            continue
        specs.append({**spec, "builder": builder})
    return specs


def build_market_activity_advanced_node_specs(builder_map, enabled_node_keys=None):
    builder_map = builder_map or {}
    enabled_node_keys = list(enabled_node_keys or [])
    enabled_key_set = set(enabled_node_keys) if enabled_node_keys else None

    specs = []
    for spec in DEFAULT_MARKET_ACTIVITY_ADVANCED_NODE_SPECS:
        node_key = spec["node_key"]
        if enabled_key_set is not None and node_key not in enabled_key_set:
            continue
        builder = builder_map.get(node_key)
        if builder is None:
            continue
        specs.append({**spec, "builder": builder})
    return specs
