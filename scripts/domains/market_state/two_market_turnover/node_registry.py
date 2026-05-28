from domains.market_state.two_market_turnover.nodes import build_two_market_turnover_compare_node


TWO_MARKET_TURNOVER_NODE_BUILDERS = {
    "compare": build_two_market_turnover_compare_node,
}


def build_two_market_turnover_node_specs(builder_map=None, enabled_node_keys=None):
    builder_map = builder_map or TWO_MARKET_TURNOVER_NODE_BUILDERS
    enabled = list(enabled_node_keys or builder_map.keys())
    specs = []
    for node_key in enabled:
        builder = builder_map.get(node_key)
        if builder is None:
            continue
        specs.append(
            {
                "node_key": node_key,
                "title": node_key,
                "builder": builder,
            }
        )
    return specs
