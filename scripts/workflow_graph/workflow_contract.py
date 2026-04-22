from collections import deque


def _normalize_workflow_lists(workflow):
    if not isinstance(workflow, dict):
        raise ValueError("workflow graph must be a dict")

    if "nodes" in workflow and workflow.get("nodes") is None:
        raise ValueError("workflow graph nodes must not be null")
    if "edges" in workflow and workflow.get("edges") is None:
        raise ValueError("workflow graph edges must not be null")

    nodes = workflow.get("nodes", [])
    edges = workflow.get("edges", [])

    if not isinstance(nodes, list):
        raise ValueError("workflow graph nodes must be a list")
    if not isinstance(edges, list):
        raise ValueError("workflow graph edges must be a list")

    return nodes, edges


def validate_workflow_graph(workflow):
    workflow = workflow or {}
    nodes, edges = _normalize_workflow_lists(workflow)

    node_keys = []
    for node in nodes:
        if not isinstance(node, dict):
            raise ValueError("workflow graph node entry must be a dict")
        node_key = node.get("key")
        if not node_key:
            raise ValueError("workflow graph node is missing key")
        node_keys.append(node_key)

    if len(node_keys) != len(set(node_keys)):
        raise ValueError("workflow graph contains duplicate node keys")

    for edge in edges:
        if not isinstance(edge, dict):
            raise ValueError("workflow graph edge entry must be a dict")
        source = edge.get("from")
        target = edge.get("to")
        if source not in node_keys or target not in node_keys:
            raise ValueError("workflow graph edge points to unknown node")

    return nodes, edges, node_keys


def build_execution_order(workflow):
    _, edges, node_keys = validate_workflow_graph(workflow)
    indegree = {key: 0 for key in node_keys}
    children = {key: [] for key in node_keys}
    for edge in edges:
        source = edge["from"]
        target = edge["to"]
        children[source].append(target)
        indegree[target] += 1
    queue = deque([key for key in node_keys if indegree[key] == 0])
    ordered = []
    while queue:
        node_key = queue.popleft()
        ordered.append(node_key)
        for child in children[node_key]:
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    if len(ordered) != len(node_keys):
        raise ValueError("workflow graph contains a cycle")
    return ordered
