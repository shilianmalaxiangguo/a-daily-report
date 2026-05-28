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
    builder_map = builder_map or NEW_STOCK_REFERENCE_NODE_BUILDERS
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
