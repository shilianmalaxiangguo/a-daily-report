from daily_report_snapshot_io import _save_data_snapshot

HOOK_NAME = "persist.snapshot"


def run(ctx):
    request = ctx.get("request") or {}
    target_date = request.get("target_date")
    payload = {
        "rendered": ctx.get("rendered") or {},
        "decision": ctx.get("decision") or {},
        "diagnostics": ctx.get("diagnostics") or {},
    }
    path = _save_data_snapshot(payload, target_date)
    return {
        "value": {"snapshot_path": path},
        "patches": {"runtime": {"snapshot_path": path}},
        "diagnostics": {"hook_name": HOOK_NAME, "status": "success", "warnings": []},
        "artifacts": {},
    }
