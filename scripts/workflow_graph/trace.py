def make_workflow_node_log(module, node_key, step, status, message, **details):
    return {
        "module": module,
        "node_key": node_key,
        "step": step,
        "status": status,
        "message": message,
        "details": details,
    }
