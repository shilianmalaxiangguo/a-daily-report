from domains.market_state.mainline_capacity.nodes import build_mainline_capacity_summary_node


MAINLINE_CAPACITY_NODE_BUILDERS = {
    "summary": build_mainline_capacity_summary_node,
}


def build_mainline_capacity_node_specs(builder_map=None, enabled_node_keys=None):
    builder_map = builder_map or MAINLINE_CAPACITY_NODE_BUILDERS
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

