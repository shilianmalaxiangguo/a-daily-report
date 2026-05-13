from __future__ import annotations

from pathlib import Path

from publish.snap_ui_public_data import publish_snap_ui_public_data

__all__ = [
    "run",
]


def run(ctx):
    request = ctx.get("request") or {}
    target_date = request.get("target_date")
    if not target_date:
        raise ValueError("target_date is required for snap-ui public data publishing")

    root = request.get("root")
    result = publish_snap_ui_public_data(
        target_date,
        root=Path(root) if root else None,
    )
    manifest_path = result.get("manifest_path", "")
    tasks_path = result.get("tasks_path", "")
    return {
        "value": result,
        "patches": {
            "runtime": {
                "snap_ui_public_data": {
                    "status": result.get("status", ""),
                    "manifest_path": manifest_path,
                    "tasks_path": tasks_path,
                }
            }
        },
        "diagnostics": {
            "hook_name": "publish.snap_ui_public_data",
            "status": result.get("status", "success"),
            "warnings": [],
        },
        "artifacts": {
            "manifest_path": manifest_path,
            "tasks_path": tasks_path,
        },
    }
