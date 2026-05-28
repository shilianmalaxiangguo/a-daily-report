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

NEW_STOCK_REFERENCE_NODE_FULL_KEYS = {
    "request": "input.new_stock_calendar.request",
    "score": "selection.new_stock_narrative.score",
    "merge": "watch_candidates.new_stock_upgrade.merge",
    "render": "report.new_stock_research.render",
    "audit": "audit.new_stock_replay.check",
}

def _canonical_node_key(node_key):
    normalized = str(node_key or "").strip()
    return NEW_STOCK_REFERENCE_NODE_FULL_KEYS.get(normalized, normalized)


def build_new_stock_reference_node_specs(builder_map=None, enabled_node_keys=None):
    if builder_map is None:
        builder_map = NEW_STOCK_REFERENCE_NODE_BUILDERS
    if enabled_node_keys is None:
        enabled_node_keys = builder_map.keys()
    enabled = {_canonical_node_key(node_key) for node_key in enabled_node_keys}
    specs = []
    for alias, full_key in NEW_STOCK_REFERENCE_NODE_FULL_KEYS.items():
        if full_key not in enabled:
            continue
        builder = builder_map.get(full_key) or builder_map.get(alias)
        if builder is None:
            continue
        specs.append(
            {
                "node_key": full_key,
                "title": alias,
                "builder": builder,
            }
        )
    return specs
