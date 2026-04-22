from hooks.trace.trace_runtime import TraceRuntime

from orchestrator.context_store import build_empty_context, merge_hook_patches
from orchestrator.module_log_runtime import make_module_log


def run_pipeline(request, hooks):
    ctx = build_empty_context(request)
    trace = TraceRuntime(run_id=f"report:{request['target_date']}")

    try:
        for hook_name, hook_fn in hooks:
            trace.before_hook(hook_name, [])
            try:
                result = hook_fn(ctx)
            except Exception as error:
                trace.on_error(hook_name, [], error)
                ctx["runtime"].setdefault("module_logs", []).append(
                    make_module_log(hook_name, status="error", error=error)
                )
                raise
            ctx = merge_hook_patches(ctx, result.get("patches") or {})
            diagnostics = result.get("diagnostics") or {}
            ctx["runtime"].setdefault("module_logs", []).append(
                make_module_log(
                    hook_name,
                    diagnostics=diagnostics,
                    patches=result.get("patches") or {},
                    artifacts=result.get("artifacts") or {},
                )
            )
            trace.after_hook(
                hook_name,
                list((result.get("patches") or {}).keys()),
                warnings=diagnostics.get("warnings", []),
                fallback_used=diagnostics.get("fallback_used", False),
                duration_ms=diagnostics.get("duration_ms", 0),
            )
        return ctx
    finally:
        trace.finish()
        ctx["runtime"]["trace_events"] = trace.events
