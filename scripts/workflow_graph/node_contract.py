"""Node context contract helpers for workflow execution."""


def build_node_context(node_key, workflow_key, run_id, inputs, state, upstream, helpers, config):
    """Build the normalized node context passed to node implementations."""
    return {
        "node": {
            "key": node_key,
            "workflow_key": workflow_key,
            "run_id": run_id,
        },
        "inputs": dict(inputs or {}),
        "state": dict(state or {}),
        "upstream": dict(upstream or {}),
        "helpers": dict(helpers or {}),
        "config": dict(config or {}),
    }
