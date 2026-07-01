from hooks.trace.trace_runtime import TraceRuntime
from observability.opik_runtime import build_report_run_observer
from observability.report_quality import build_report_quality_score

from orchestrator.context_store import build_empty_context, merge_hook_patches
from orchestrator.module_log_runtime import make_module_log


def run_pipeline(request, hooks):
    ctx = build_empty_context(request)
    trace = TraceRuntime(run_id=f"report:{request['target_date']}")
    observer = build_report_run_observer(
        run_name=f"daily-report.pipeline.{request['target_date']}",
        trace_input={
            "target_date": request.get("target_date"),
            "hook_count": len(hooks or []),
            "postgres_only": bool(request.get("postgres_only")),
        },
        metadata={"runner": "orchestrator.pipeline_runner"},
    )
    run_status = "success"

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
                run_status = "error"
                observer.record_step(
                    hook_name,
                    status="error",
                    input_payload={"target_date": request.get("target_date")},
                    output_payload={},
                    metadata={"runner": "orchestrator.pipeline_runner"},
                    error=error,
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
            observer.record_step(
                hook_name,
                status=diagnostics.get("status") or "success",
                input_payload={"target_date": request.get("target_date")},
                output_payload={
                    "patch_keys": list((result.get("patches") or {}).keys()),
                    "artifact_keys": list((result.get("artifacts") or {}).keys()),
                    "warning_count": len(diagnostics.get("warnings", []) or []),
                    "fallback_used": bool(diagnostics.get("fallback_used", False)),
                },
                metadata={
                    "runner": "orchestrator.pipeline_runner",
                    "duration_ms": diagnostics.get("duration_ms", 0),
                },
            )
        return ctx
    except Exception:
        run_status = "error"
        raise
    finally:
        trace.finish()
        ctx["runtime"]["trace_events"] = trace.events
        report_quality_score = build_report_quality_score(
            target_date=str(request.get("target_date") or ""),
            run_status=run_status,
            mode="pipeline",
            output_paths=ctx.get("rendered") or {},
            report_expected=False,
            decision_ledger_expected=False,
        )
        observer.finish(
            status=run_status,
            output_payload={
                "target_date": request.get("target_date"),
                "trace_event_count": len(trace.events),
                "module_log_count": len(ctx["runtime"].get("module_logs") or []),
                "report_quality_score": report_quality_score,
            },
        )
