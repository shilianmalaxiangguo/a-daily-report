def collect_upstream_exports(node_key, edges, node_results):
    upstream = {}
    for edge in edges or []:
        if edge.get("to") != node_key:
            continue
        upstream_key = edge.get("from")
        upstream[upstream_key] = dict(
            (node_results.get(upstream_key) or {}).get("exports") or {}
        )
    return upstream


def merge_state_patch(state, state_patch):
    state = dict(state or {})
    state.update(dict(state_patch or {}))
    return state
