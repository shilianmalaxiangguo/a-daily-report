"""Run-store helpers for upstream exports and shared state merges."""


def collect_upstream_exports(node_key, edges, node_results):
    """Collect exports from direct upstream nodes for the current node."""
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
    """Return a new state dict with the node patch merged in."""
    state = dict(state or {})
    state.update(dict(state_patch or {}))
    return state
