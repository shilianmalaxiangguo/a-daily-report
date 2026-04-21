from datetime import datetime, timezone


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def make_trace_event(run_id, hook=None, status="info", **extra):
    return {
        "run_id": run_id,
        "hook": hook,
        "status": status,
        "at": utc_now_iso(),
        **extra,
    }
