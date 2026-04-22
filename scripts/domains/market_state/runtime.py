from domains.market_state.graph import build_market_state_graph
from domains.market_state.registry import build_market_state_registry
from workflow_graph.executor import execute_workflow_graph


def run_market_state_analysis(ctx):
    workflow = build_market_state_graph()
    registry = build_market_state_registry()
    return execute_workflow_graph(workflow, registry, ctx)
