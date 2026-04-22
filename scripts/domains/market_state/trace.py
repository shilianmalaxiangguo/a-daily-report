from domains.market_state.contracts import build_market_state_node_module_map
from workflow_graph.trace import make_workflow_node_log

_NODE_MODULE_BY_KEY = build_market_state_node_module_map()


def make_market_state_log(node_key, step, status, message, **details):
    module_name = _NODE_MODULE_BY_KEY.get(node_key, node_key)
    return make_workflow_node_log(
        f"domains.market_state.nodes.{module_name}",
        node_key,
        step,
        status,
        message,
        **details,
    )
