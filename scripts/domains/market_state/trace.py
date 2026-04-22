from workflow_graph.trace import make_workflow_node_log


def make_market_state_log(node_key, step, status, message, **details):
    return make_workflow_node_log(
        f"domains.market_state.nodes.{node_key}",
        node_key,
        step,
        status,
        message,
        **details,
    )
