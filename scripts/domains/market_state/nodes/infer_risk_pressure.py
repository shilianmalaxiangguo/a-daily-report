def run(ctx):
    _ = ctx
    return {
        "value": {"risk_snapshot": {}},
        "exports": {"risk_snapshot": {}},
        "state_patch": {},
        "module_logs": [],
        "errors": [],
        "control": {"status": "success"},
    }
