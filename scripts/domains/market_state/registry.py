from importlib import import_module

from domains.market_state.contracts import build_market_state_node_module_map


class MarketStateRegistryBuildError(RuntimeError):
    """Raised when a market_state node cannot be loaded as a runnable registry entry."""


def build_market_state_registry():
    """Map semantic node keys to run callables from infer_/assemble_ node modules."""
    registry = {}
    for node_key, module_name in build_market_state_node_module_map().items():
        module_path = f"domains.market_state.nodes.{module_name}"
        try:
            module = import_module(module_path)
        except ImportError as exc:
            raise MarketStateRegistryBuildError(
                f"Unable to load market_state node '{node_key}' from '{module_path}'."
            ) from exc

        run_fn = getattr(module, "run", None)
        if not callable(run_fn):
            raise MarketStateRegistryBuildError(
                f"market_state node '{node_key}' in '{module_path}' must expose callable run(ctx)."
            )

        registry[node_key] = run_fn
    return registry
