def run(ctx):
    _ = ctx
    return {
        "value": {"continuity_snapshot": {}},
        "exports": {"continuity_snapshot": {}},
        "state_patch": {},
        "module_logs": [],
        "errors": [],
        "control": {"status": "success"},
    }
