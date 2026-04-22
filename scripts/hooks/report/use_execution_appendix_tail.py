import datetime as _dt
import time


HOOK_NAME = "report.execution_appendix_tail"


def _append_log(logs, step, status, message, **details):
    logs.append(
        {
            "module": "hooks.report.use_execution_appendix_tail",
            "step": step,
            "status": status,
            "message": message,
            "details": details,
        }
    )


def run(ctx):
    started_at = time.perf_counter()
    ctx = ctx or {}
    inputs = ctx.get("inputs") or {}
    helpers = ctx.get("helpers") or {}
    logs = []

    timer_summary = inputs.get("timer_summary", {}) or {}
    step_status = inputs.get("step_status", {}) or {}
    normalize_report_timer_steps = helpers.get("normalize_report_timer_steps")
    render_execution_appendix = helpers.get("render_execution_appendix")

    if callable(normalize_report_timer_steps) and timer_summary:
        normalized_timer_steps = normalize_report_timer_steps(timer_summary, step_status)
    else:
        normalized_timer_steps = []
    total_time = timer_summary.get("total_time", 0) if timer_summary else 0

    _append_log(
        logs,
        "derive.normalized_timer_steps",
        "success",
        "已归一化执行计时步骤",
        step_count=len(normalized_timer_steps),
        total_time=total_time,
    )

    render_context = {
        "data_status": inputs.get("data_status", {}) or {},
        "step_status": step_status,
        "normalized_timer_steps": normalized_timer_steps,
        "total_time": total_time,
        "target_date": inputs.get("target_date", ""),
        "generated_at": inputs.get("generated_at") or _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "report_version": inputs.get("report_version", "v2.5.0"),
    }
    lines = render_execution_appendix(render_context) if callable(render_execution_appendix) else []
    _append_log(
        logs,
        "render.execution_appendix_tail",
        "success",
        "已渲染执行附录尾部",
        line_count=len(lines),
        data_status_count=len(render_context["data_status"]),
        step_status_count=len(step_status),
    )

    exports = {
        "normalized_timer_steps": normalized_timer_steps,
        "total_time": total_time,
    }
    return {
        "value": {
            "lines": list(lines or []),
            "exports": exports,
            "module_logs": logs,
        },
        "patches": {
            "derived": {
                "execution_appendix": exports,
            }
        },
        "diagnostics": {
            "hook_name": HOOK_NAME,
            "status": "success",
            "warnings": [],
            "duration_ms": int((time.perf_counter() - started_at) * 1000),
        },
        "artifacts": {},
    }
