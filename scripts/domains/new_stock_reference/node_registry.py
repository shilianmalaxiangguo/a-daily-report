from domains.new_stock_reference.nodes import (
    build_new_stock_audit_node,
    build_new_stock_candidate_merge_node,
    build_new_stock_report_node,
    build_new_stock_request_node,
    build_new_stock_score_node,
)


NEW_STOCK_REFERENCE_NODE_BUILDERS = {
    "request": build_new_stock_request_node,
    "score": build_new_stock_score_node,
    "merge": build_new_stock_candidate_merge_node,
    "render": build_new_stock_report_node,
    "audit": build_new_stock_audit_node,
}


def build_new_stock_reference_node_specs(builder_map=None, enabled_node_keys=None):
    if builder_map is None:
        builder_map = NEW_STOCK_REFERENCE_NODE_BUILDERS
    if enabled_node_keys is None:
        enabled_node_keys = builder_map.keys()
    enabled = set(enabled_node_keys)
    specs = []
    for node_key in builder_map:
        if node_key not in enabled:
            continue
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
