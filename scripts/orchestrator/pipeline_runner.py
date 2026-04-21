from hooks.trace.trace_runtime import TraceRuntime

from orchestrator.context_store import build_empty_context, merge_hook_patches


def run_pipeline(request, hooks):
    ctx = build_empty_context(request)
    trace = TraceRuntime(run_id=f"report:{request['target_date']}")

    for hook_name, hook_fn in hooks:
        trace.before_hook(hook_name, [])
        result = hook_fn(ctx)
        ctx = merge_hook_patches(ctx, result.get("patches") or {})
        diagnostics = result.get("diagnostics") or {}
        trace.after_hook(
            hook_name,
            list((result.get("patches") or {}).keys()),
            warnings=diagnostics.get("warnings", []),
            fallback_used=diagnostics.get("fallback_used", False),
            duration_ms=diagnostics.get("duration_ms", 0),
        )

    trace.finish()
    ctx["runtime"]["trace_events"] = trace.events
    return ctx
