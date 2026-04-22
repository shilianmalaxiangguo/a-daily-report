"""Workflow graph executor for workflow-graph orchestration.

Node implementations are expected to return a dict that may include:
- exports: values exposed for downstream nodes and workflow exports
- state_patch: partial state updates merged into shared workflow state
- module_logs: list of module log entries produced by the node
- errors: list of error entries produced by the node
- control.status (optional): explicit node status for executor trace logs
"""

from workflow_graph.node_contract import build_node_context
from workflow_graph.registry import resolve_workflow_node
from workflow_graph.run_store import collect_upstream_exports, merge_state_patch
from workflow_graph.trace import make_workflow_node_log
from workflow_graph.workflow_contract import build_execution_order


def _normalize_result_collection(value):
    """Normalize node result collections to a list.

    - list/tuple values are copied to a list
    - None becomes an empty list
    - any other value becomes a single-item list containing that value
    """
    if isinstance(value, (list, tuple)):
        return list(value)
    if value is None:
        return []
    return [value]


def execute_workflow_graph(workflow, registry, ctx=None):
    workflow = {} if workflow is None else workflow
    ctx = ctx or {}
    inputs = dict(ctx.get("inputs") or {})
    state = dict(ctx.get("state") or {})
    helpers = dict(ctx.get("helpers") or {})
    config = dict(ctx.get("config") or {})
    run_id = str(ctx.get("run_id", "") or "")
    node_results = {}
    module_logs = []
    errors = []
    execution_order = build_execution_order(workflow)
    edges = workflow.get("edges") or []
    node_meta_map = {item["key"]: item for item in (workflow.get("nodes") or [])}

    for node_key in execution_order:
        node_meta = node_meta_map[node_key]
        if node_meta.get("enabled", True) is False:
            module_logs.append(
                make_workflow_node_log(
                    "workflow_graph.executor",
                    node_key,
                    f"run.{node_key}",
                    "skipped",
                    "workflow node disabled",
                    workflow_key=workflow.get("workflow_key", ""),
                )
            )
            continue

        node_impl = resolve_workflow_node(registry, node_key)
        upstream = collect_upstream_exports(node_key, edges, node_results)
        node_ctx = build_node_context(
            node_key,
            workflow.get("workflow_key", ""),
            run_id,
            inputs,
            state,
            upstream,
            helpers,
            config,
        )
        result = node_impl(node_ctx) or {}
        node_module_logs = _normalize_result_collection(result.get("module_logs"))
        node_errors = _normalize_result_collection(result.get("errors"))
        control = result.get("control") or {}
        log_status = control.get("status")
        if node_errors:
            log_status = "error"
        elif not log_status:
            log_status = "success"
        log_message = (
            "workflow node completed with errors"
            if node_errors
            else "workflow node executed"
        )
        state = merge_state_patch(state, result.get("state_patch") or {})
        node_results[node_key] = result
        module_logs.extend(node_module_logs)
        errors.extend(node_errors)
        module_logs.append(
            make_workflow_node_log(
                "workflow_graph.executor",
                node_key,
                f"run.{node_key}",
                log_status,
                log_message,
                workflow_key=workflow.get("workflow_key", ""),
                export_keys=sorted((result.get("exports") or {}).keys()),
            )
        )

    exports = {}
    for export_key in (workflow.get("exports") or []):
        for node_key in reversed(execution_order):
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
