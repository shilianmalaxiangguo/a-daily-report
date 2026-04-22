from domains.market_state.contracts import (
    NODE_ASSEMBLE_EXIT_ANALYSIS,
    NODE_ENVIRONMENT_SIGNAL,
    NODE_MAINLINE_CANDIDATES,
    NODE_MAINLINE_CONTINUITY,
    NODE_RISK_PRESSURE,
    NODE_SECTOR_COMPETITION,
)
from workflow_graph.trace import make_workflow_node_log

_NODE_MODULE_BY_KEY = {
    NODE_MAINLINE_CANDIDATES: "infer_mainline_candidates",
    NODE_ENVIRONMENT_SIGNAL: "infer_environment_signal",
    NODE_MAINLINE_CONTINUITY: "infer_mainline_continuity",
    NODE_RISK_PRESSURE: "infer_risk_pressure",
    NODE_SECTOR_COMPETITION: "infer_sector_competition",
    NODE_ASSEMBLE_EXIT_ANALYSIS: "assemble_exit_analysis",
}


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
