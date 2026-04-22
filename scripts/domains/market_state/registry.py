from importlib import import_module

from domains.market_state.contracts import build_market_state_node_module_map


def build_market_state_registry():
    """Map semantic node keys to run callables from infer_/assemble_ node modules."""
    registry = {}
    for node_key, module_name in build_market_state_node_module_map().items():
        module = import_module(f"domains.market_state.nodes.{module_name}")
        registry[node_key] = module.run
    return registry
