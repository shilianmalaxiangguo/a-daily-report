from hooks.trace.trace_events import make_trace_event


class TraceRuntime:
    def __init__(self, run_id):
        self.run_id = run_id
        self.events = [make_trace_event(run_id, status="started")]

    def before_hook(self, hook, inputs):
        self.events.append(
            make_trace_event(
                self.run_id,
                hook=hook,
                status="before",
                inputs=list(inputs or []),
            )
        )

    def after_hook(self, hook, outputs, warnings=None, fallback_used=False, duration_ms=0):
        self.events.append(
            make_trace_event(
                self.run_id,
                hook=hook,
                status="success",
                outputs=list(outputs or []),
                warnings=list(warnings or []),
                fallback_used=bool(fallback_used),
                duration_ms=duration_ms,
            )
        )

    def on_error(self, hook, inputs, error):
        self.events.append(
            make_trace_event(
                self.run_id,
                hook=hook,
                status="error",
                inputs=list(inputs or []),
                error=str(error),
            )
        )
