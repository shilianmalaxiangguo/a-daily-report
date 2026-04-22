from workflow_graph.registry import resolve_workflow_node
from workflow_graph.trace import make_workflow_node_log


def _build_execution_order(workflow):
    nodes = [item["key"] for item in workflow.get("nodes", [])]
    edges = workflow.get("edges", [])
    indegree = {key: 0 for key in nodes}
    children = {key: [] for key in nodes}
    for edge in edges:
        source = edge["from"]
        target = edge["to"]
        children[source].append(target)
        indegree[target] += 1
    queue = [key for key in nodes if indegree[key] == 0]
    ordered = []
    while queue:
        node_key = queue.pop(0)
        ordered.append(node_key)
        for child in children[node_key]:
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    return ordered


def execute_workflow_graph(workflow, registry, ctx=None):
    ctx = ctx or {}
    inputs = dict(ctx.get("inputs") or {})
    state = dict(ctx.get("state") or {})
    helpers = dict(ctx.get("helpers") or {})
    config = dict(ctx.get("config") or {})
    node_results = {}
    module_logs = []
    errors = []
    edges = workflow.get("edges", [])

    for node_key in _build_execution_order(workflow):
        node_impl = resolve_workflow_node(registry, node_key)
        upstream = {}
        for edge in edges:
            if edge["to"] == node_key:
                upstream_key = edge["from"]
                upstream[upstream_key] = dict(
                    (node_results.get(upstream_key) or {}).get("exports") or {}
                )
        node_ctx = {
            "node": {
                "key": node_key,
                "workflow_key": workflow.get("workflow_key", ""),
                "run_id": ctx.get("run_id", ""),
            },
            "inputs": inputs,
            "state": state,
            "upstream": upstream,
            "helpers": helpers,
            "config": config,
        }
        result = node_impl(node_ctx) or {}
        state.update(result.get("state_patch") or {})
        node_results[node_key] = result
        module_logs.extend(result.get("module_logs") or [])
        errors.extend(result.get("errors") or [])
        module_logs.append(
            make_workflow_node_log(
                "workflow_graph.executor",
                node_key,
                f"run.{node_key}",
                "success",
                "workflow node executed",
                export_keys=sorted((result.get("exports") or {}).keys()),
            )
        )

    exports = {}
    for export_key in workflow.get("exports", []):
        for node_key in reversed(_build_execution_order(workflow)):
            node_exports = (node_results.get(node_key) or {}).get("exports") or {}
            if export_key in node_exports:
                exports[export_key] = node_exports[export_key]
                break

    return {
        "workflow_key": workflow.get("workflow_key", ""),
        "state": state,
        "node_results": node_results,
        "exports": exports,
        "module_logs": module_logs,
        "errors": errors,
    }
