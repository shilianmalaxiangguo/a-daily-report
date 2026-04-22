from collections import deque


def validate_workflow_graph(workflow):
    workflow = workflow or {}
    node_keys = [item.get("key", "") for item in workflow.get("nodes", [])]
    if len(node_keys) != len(set(node_keys)):
        raise ValueError("workflow graph contains duplicate node keys")
    for edge in workflow.get("edges", []):
        if edge.get("from") not in node_keys or edge.get("to") not in node_keys:
            raise ValueError("workflow graph edge points to unknown node")


def build_execution_order(workflow):
    validate_workflow_graph(workflow)
    nodes = [item["key"] for item in workflow.get("nodes", [])]
    edges = workflow.get("edges", [])
    indegree = {key: 0 for key in nodes}
    children = {key: [] for key in nodes}
    for edge in edges:
        source = edge["from"]
        target = edge["to"]
        children[source].append(target)
        indegree[target] += 1
    queue = deque([key for key in nodes if indegree[key] == 0])
    ordered = []
    while queue:
        node_key = queue.popleft()
        ordered.append(node_key)
        for child in children[node_key]:
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    if len(ordered) != len(nodes):
        raise ValueError("workflow graph contains a cycle")
    return ordered
