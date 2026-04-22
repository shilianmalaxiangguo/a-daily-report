def resolve_workflow_node(registry, node_key):
    if node_key not in (registry or {}):
        raise KeyError(f"workflow node not registered: {node_key}")
    return registry[node_key]
