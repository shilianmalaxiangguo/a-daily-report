def run(ctx):
    _ = ctx
    return {
        "value": {"environment_signal": {}},
        "exports": {"environment_signal": {}},
        "state_patch": {},
        "module_logs": [],
        "errors": [],
        "control": {"status": "success"},
    }
