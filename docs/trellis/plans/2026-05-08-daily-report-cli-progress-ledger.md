# Daily Report CLI Progress Ledger Implementation Plan

> **For agentic workers:** REQUIRED WORKFLOW: Use Trellis task execution to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a realtime CLI progress bar, line-by-line provider events, and a post-run ledger for daily report runs.

**Architecture:** Build a small observability layer around the existing Python runtime instead of adding a service. `RunProgressReporter` owns terminal rendering, `provider_event_runtime` owns structured provider events, `run_ledger_runtime` writes reviewable files, and existing entry points call these units at stable boundaries.

**Tech Stack:** Python stdlib, existing `unittest` suite, existing `orchestrator.pipeline_runner`, existing `daily_report_entry_demo.py`, existing report/replay file layout.

---

## File Structure

- Create `scripts/orchestrator/run_progress_runtime.py`
  - Formats elapsed time and progress bars.
  - Renders dynamic TTY progress or `[progress]` fallback lines.
  - Logs provider event lines without corrupting progress display.

- Create `scripts/orchestrator/provider_event_runtime.py`
  - Normalizes provider events.
  - Stores the current event sink in a `contextvars.ContextVar`.
  - Emits `provider_call_start`, `provider_call_success`, `provider_call_timeout`, `provider_call_retry`, `provider_call_fallback`, and `provider_call_error`.
  - Provides `observed_provider_call()` for start/success/error timing.

- Create `scripts/orchestrator/run_ledger_runtime.py`
  - Builds `reports/runs/YYYY-MM-DD/`.
  - Writes `run.json`, `module_logs.json`, `provider_events.json`, `artifacts.json`, `overview.md`, and `review_queue.md`.
  - Converts fallback/error events into human review items.

- Modify `scripts/orchestrator/pipeline_runner.py`
  - Accept optional `progress_reporter` and `provider_events`.
  - Emit hook progress around each hook.
  - Attach provider events to `ctx["runtime"]["provider_events"]`.

- Modify `scripts/daily_report_entry_demo.py`
  - Create a `RunProgressReporter` for the current legacy CLI flow.
  - Wrap major legacy stages: data/replay, run-mode resolution, report rendering, stock diagnostic, snapshot persistence, snap-ui export.
  - Install provider event sink around the run.
  - Write the run ledger before returning.

- Modify `scripts/input/iwencai_runtime.py`
  - Instrument AkShare fallback calls through `observed_provider_call()`.
  - First pass covers `_latest_index_row`, `_get_sector_change_akshare_fallback`, `_get_turnover_rank_akshare_fallback`.

- Modify `scripts/llm_service.py`
  - Instrument DeepSeek/LLM proxy calls through `observed_provider_call()`.
  - First pass covers `analyze_events_batch()` and `analyze_event_sectors()` when the legacy service exposes them.

- Add tests:
  - `tests/test_run_progress_runtime.py`
  - `tests/test_provider_event_runtime.py`
  - `tests/test_run_ledger_runtime.py`
  - Extend `tests/test_pipeline_runner.py`
  - Extend `tests/test_iwencai_runtime.py`
  - Extend `tests/test_llm_service.py`

## Task 1: Run Progress Reporter

**Files:**
- Create: `scripts/orchestrator/run_progress_runtime.py`
- Test: `tests/test_run_progress_runtime.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_run_progress_runtime.py`:

```python
import io
import re
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from orchestrator.run_progress_runtime import (
    RunProgressReporter,
    format_elapsed,
    format_progress_bar,
)


class RunProgressRuntimeTest(unittest.TestCase):
    def test_format_elapsed_uses_mm_ss(self):
        self.assertEqual(format_elapsed(0), "00:00")
        self.assertEqual(format_elapsed(74.2), "01:14")
        self.assertEqual(format_elapsed(3723), "62:03")

    def test_format_progress_bar_matches_requested_shape(self):
        self.assertEqual(format_progress_bar(6, 10, width=20), "████████████░░░░░░░░")
        self.assertEqual(format_progress_bar(0, 10, width=10), "░░░░░░░░░░")
        self.assertEqual(format_progress_bar(10, 10, width=10), "██████████")

    def test_non_tty_progress_writes_readable_progress_lines(self):
        stream = io.StringIO()
        reporter = RunProgressReporter(
            total_steps=10,
            stream=stream,
            is_tty=False,
            now_fn=lambda: datetime(2026, 5, 8, 9, 30, 0),
        )

        reporter.start_step("knowledge.llm_wiki", completed_steps=6)

        output = stream.getvalue()
        self.assertIn("[progress]", output)
        self.assertIn("6/10 hooks", output)
        self.assertIn("current=knowledge.llm_wiki", output)
        self.assertIn("elapsed=00:00", output)

    def test_tty_progress_renders_single_carriage_return_line(self):
        stream = io.StringIO()
        base = datetime(2026, 5, 8, 9, 30, 0)
        calls = [base, base + timedelta(seconds=134)]

        reporter = RunProgressReporter(
            total_steps=10,
            stream=stream,
            is_tty=True,
            now_fn=lambda: calls.pop(0) if calls else base + timedelta(seconds=134),
        )
        reporter.start_step("knowledge.llm_wiki", completed_steps=6)

        output = stream.getvalue()
        self.assertTrue(output.startswith("\r["))
        self.assertIn("6/10 hooks", output)
        self.assertIn("current=knowledge.llm_wiki", output)
        self.assertIn("elapsed=02:14", output)

    def test_event_line_preserves_log_and_restores_progress(self):
        stream = io.StringIO()
        reporter = RunProgressReporter(total_steps=10, stream=stream, is_tty=True)
        reporter.start_step("input.hot_rank", completed_steps=1)
        reporter.log_provider_event(
            {
                "hook_name": "input.hot_rank",
                "provider": "akshare",
                "operation": "stock_zh_a_hist",
                "event_type": "provider_call_timeout",
                "timeout_sec": 15,
                "attempt": 1,
                "max_attempts": 2,
                "duration_ms": 15001,
            }
        )

        output = stream.getvalue()
        self.assertRegex(output, re.compile(r"\[\d{2}:\d{2}:\d{2}\] input\.hot_rank\s+WARN akshare stock_zh_a_hist timeout after 15s"))
        self.assertIn("retry=2/2", output)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
venv/bin/python3 -m unittest tests.test_run_progress_runtime
```

Expected: FAIL with `ModuleNotFoundError: No module named 'orchestrator.run_progress_runtime'`.

- [ ] **Step 3: Implement `run_progress_runtime.py`**

Create `scripts/orchestrator/run_progress_runtime.py`:

```python
from __future__ import annotations

import sys
from datetime import datetime

FILLED = "█"
EMPTY = "░"


def format_elapsed(seconds):
    total = max(0, int(seconds or 0))
    minutes, secs = divmod(total, 60)
    return f"{minutes:02d}:{secs:02d}"


def format_progress_bar(completed, total, width=20):
    total = max(1, int(total or 1))
    completed = max(0, min(int(completed or 0), total))
    filled = int(round(width * completed / total))
    filled = max(0, min(width, filled))
    return f"{FILLED * filled}{EMPTY * (width - filled)}"


def _short_time(now):
    return now.strftime("%H:%M:%S")


def _provider_level(event):
    event_type = str((event or {}).get("event_type") or "")
    if event_type.endswith("_success"):
        return "OK"
    if event_type.endswith("_start"):
        return "INFO"
    if event_type.endswith("_timeout") or event_type.endswith("_fallback") or event_type.endswith("_retry"):
        return "WARN"
    if event_type.endswith("_error"):
        return "ERROR"
    return "INFO"


def _format_provider_message(event):
    event = event or {}
    provider = str(event.get("provider") or "provider")
    operation = str(event.get("operation") or "call")
    event_type = str(event.get("event_type") or "provider_event")
    timeout_sec = event.get("timeout_sec")
    duration_ms = event.get("duration_ms")
    attempt = int(event.get("attempt") or 0)
    max_attempts = int(event.get("max_attempts") or 0)
    fallback_provider = str(event.get("fallback_provider") or "")
    rows = event.get("rows")
    error_message = str(event.get("error_message") or "").strip()

    if event_type.endswith("_start"):
        bits = [provider, operation, "started"]
        if attempt:
            bits.append(f"attempt={attempt}")
        if timeout_sec:
            bits.append(f"timeout={timeout_sec}s")
        return " ".join(bits)

    if event_type.endswith("_timeout"):
        bits = [provider, operation, f"timeout after {timeout_sec}s" if timeout_sec else "timeout"]
        if max_attempts and attempt < max_attempts:
            bits.append(f"retry={attempt + 1}/{max_attempts}")
        return " ".join(bits)

    if event_type.endswith("_fallback"):
        bits = [provider, operation, "fallback"]
        if fallback_provider:
            bits.append(f"to={fallback_provider}")
        return " ".join(bits)

    if event_type.endswith("_success"):
        bits = [provider, operation, "done"]
        if rows is not None:
            bits.append(f"rows={rows}")
        if duration_ms is not None:
            bits.append(f"duration={float(duration_ms) / 1000:.1f}s")
        return " ".join(bits)

    if event_type.endswith("_error"):
        bits = [provider, operation, "error"]
        if error_message:
            bits.append(error_message)
        return " ".join(bits)

    return f"{provider} {operation} {event_type}"


class RunProgressReporter:
    def __init__(self, total_steps, stream=None, is_tty=None, now_fn=None, width=20):
        self.total_steps = max(1, int(total_steps or 1))
        self.stream = stream or sys.stdout
        self.is_tty = bool(self.stream.isatty()) if is_tty is None else bool(is_tty)
        self.now_fn = now_fn or datetime.now
        self.width = int(width or 20)
        self.started_at = self.now_fn()
        self.current_step = ""
        self.completed_steps = 0
        self._last_progress_line = ""

    def _elapsed_seconds(self):
        return (self.now_fn() - self.started_at).total_seconds()

    def _progress_line(self):
        bar = format_progress_bar(self.completed_steps, self.total_steps, width=self.width)
        return (
            f"[{bar}] {self.completed_steps}/{self.total_steps} hooks  "
            f"current={self.current_step or '-'}  elapsed={format_elapsed(self._elapsed_seconds())}"
        )

    def render_progress(self):
        line = self._progress_line()
        self._last_progress_line = line
        if self.is_tty:
            self.stream.write("\r" + line)
        else:
            self.stream.write(f"[progress] {self.completed_steps}/{self.total_steps} hooks current={self.current_step or '-'} elapsed={format_elapsed(self._elapsed_seconds())}\n")
        self.stream.flush()

    def start_step(self, step_name, completed_steps=None):
        self.current_step = str(step_name or "-")
        if completed_steps is not None:
            self.completed_steps = max(0, min(int(completed_steps), self.total_steps))
        self.render_progress()

    def finish_step(self, step_name=None, status="success"):
        if step_name:
            self.current_step = str(step_name)
        self.completed_steps = max(0, min(self.completed_steps + 1, self.total_steps))
        self.render_progress()

    def fail_step(self, step_name, error):
        self.current_step = str(step_name or self.current_step or "-")
        self.log_line(f"ERROR {self.current_step} {error}")
        self.render_progress()

    def log_line(self, message):
        if self.is_tty:
            self.stream.write("\n")
        self.stream.write(str(message).rstrip() + "\n")
        self.stream.flush()

    def log_provider_event(self, event):
        now = self.now_fn()
        hook = str((event or {}).get("hook_name") or self.current_step or "-")
        level = _provider_level(event)
        message = _format_provider_message(event)
        self.log_line(f"[{_short_time(now)}] {hook:<20} {level} {message}")
        if self.is_tty and self._last_progress_line:
            self.render_progress()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
venv/bin/python3 -m unittest tests.test_run_progress_runtime
```

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

Run:

```bash
git add scripts/orchestrator/run_progress_runtime.py tests/test_run_progress_runtime.py
git commit -m "feat: add daily report cli progress reporter" -- scripts/orchestrator/run_progress_runtime.py tests/test_run_progress_runtime.py
```

## Task 2: Provider Event Runtime

**Files:**
- Create: `scripts/orchestrator/provider_event_runtime.py`
- Test: `tests/test_provider_event_runtime.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_provider_event_runtime.py`:

```python
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from orchestrator.provider_event_runtime import (
    emit_provider_event,
    install_provider_event_handler,
    observed_provider_call,
)


class ProviderEventRuntimeTest(unittest.TestCase):
    def test_emit_provider_event_normalizes_and_sends_to_handler(self):
        events = []
        token = install_provider_event_handler(events.append)
        try:
            emitted = emit_provider_event(
                event_type="provider_call_start",
                hook_name="input.hot_rank",
                provider="akshare",
                operation="stock_zh_a_hist",
                attempt=1,
                max_attempts=2,
                timeout_sec=15,
            )
        finally:
            token.reset()

        self.assertEqual(events, [emitted])
        self.assertEqual(emitted["provider"], "akshare")
        self.assertEqual(emitted["event_type"], "provider_call_start")
        self.assertIn("at", emitted)

    def test_emit_provider_event_without_handler_returns_event(self):
        emitted = emit_provider_event(
            event_type="provider_call_start",
            hook_name="input.hot_rank",
            provider="akshare",
            operation="stock_zh_a_hist",
        )

        self.assertEqual(emitted["hook_name"], "input.hot_rank")
        self.assertEqual(emitted["provider"], "akshare")

    def test_observed_provider_call_records_start_and_success(self):
        events = []
        token = install_provider_event_handler(events.append)
        try:
            result = observed_provider_call(
                provider="akshare",
                operation="stock_board_industry_name_em",
                hook_name="input.sector_change",
                timeout_sec=15,
                rows_fn=lambda rows: len(rows),
                call_fn=lambda: [1, 2, 3],
            )
        finally:
            token.reset()

        self.assertEqual(result, [1, 2, 3])
        self.assertEqual(events[0]["event_type"], "provider_call_start")
        self.assertEqual(events[1]["event_type"], "provider_call_success")
        self.assertEqual(events[1]["rows"], 3)
        self.assertGreaterEqual(events[1]["duration_ms"], 0)

    def test_observed_provider_call_classifies_timeout_text(self):
        events = []

        def boom():
            raise RuntimeError("request timed out")

        token = install_provider_event_handler(events.append)
        try:
            with self.assertRaises(RuntimeError):
                observed_provider_call(
                    provider="deepseek",
                    operation="analyze_events_batch",
                    hook_name="calendar_events.llm",
                    timeout_sec=30,
                    call_fn=boom,
                )
        finally:
            token.reset()

        self.assertEqual(events[0]["event_type"], "provider_call_start")
        self.assertEqual(events[1]["event_type"], "provider_call_timeout")
        self.assertEqual(events[1]["error_type"], "RuntimeError")
        self.assertIn("timed out", events[1]["error_message"])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
venv/bin/python3 -m unittest tests.test_provider_event_runtime
```

Expected: FAIL with `ModuleNotFoundError: No module named 'orchestrator.provider_event_runtime'`.

- [ ] **Step 3: Implement `provider_event_runtime.py`**

Create `scripts/orchestrator/provider_event_runtime.py`:

```python
from __future__ import annotations

import contextvars
import time
from datetime import datetime, timezone

_current_provider_event_handler = contextvars.ContextVar("provider_event_handler", default=None)


class ProviderEventToken:
    def __init__(self, token):
        self._token = token

    def reset(self):
        _current_provider_event_handler.reset(self._token)


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _is_timeout_error(error):
    text = f"{error.__class__.__name__}: {error}".lower()
    return "timeout" in text or "timed out" in text or "read timed out" in text


def install_provider_event_handler(handler):
    token = _current_provider_event_handler.set(handler)
    return ProviderEventToken(token)


def normalize_provider_event(**event):
    normalized = {
        "event_type": str(event.get("event_type") or "provider_event"),
        "hook_name": str(event.get("hook_name") or ""),
        "provider": str(event.get("provider") or ""),
        "operation": str(event.get("operation") or ""),
        "at": event.get("at") or _now_iso(),
    }
    for key, value in event.items():
        if key not in normalized and value is not None:
            normalized[key] = value
    return normalized


def emit_provider_event(**event):
    normalized = normalize_provider_event(**event)
    handler = _current_provider_event_handler.get()
    if handler is not None:
        handler(normalized)
    return normalized


def observed_provider_call(
    *,
    provider,
    operation,
    hook_name="",
    timeout_sec=None,
    attempt=1,
    max_attempts=1,
    fallback_provider="",
    rows_fn=None,
    call_fn,
):
    emit_provider_event(
        event_type="provider_call_start",
        hook_name=hook_name,
        provider=provider,
        operation=operation,
        timeout_sec=timeout_sec,
        attempt=attempt,
        max_attempts=max_attempts,
    )
    started = time.monotonic()
    try:
        result = call_fn()
    except Exception as error:
        duration_ms = int((time.monotonic() - started) * 1000)
        event_type = "provider_call_timeout" if _is_timeout_error(error) else "provider_call_error"
        emit_provider_event(
            event_type=event_type,
            hook_name=hook_name,
            provider=provider,
            operation=operation,
            timeout_sec=timeout_sec,
            attempt=attempt,
            max_attempts=max_attempts,
            fallback_provider=fallback_provider,
            duration_ms=duration_ms,
            error_type=error.__class__.__name__,
            error_message=str(error),
        )
        raise

    duration_ms = int((time.monotonic() - started) * 1000)
    rows = None
    if rows_fn is not None:
        try:
            rows = rows_fn(result)
        except Exception:
            rows = None
    emit_provider_event(
        event_type="provider_call_success",
        hook_name=hook_name,
        provider=provider,
        operation=operation,
        timeout_sec=timeout_sec,
        attempt=attempt,
        max_attempts=max_attempts,
        fallback_provider=fallback_provider,
        duration_ms=duration_ms,
        rows=rows,
    )
    return result
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
venv/bin/python3 -m unittest tests.test_provider_event_runtime
```

Expected: PASS.

- [ ] **Step 5: Commit Task 2**

Run:

```bash
git add scripts/orchestrator/provider_event_runtime.py tests/test_provider_event_runtime.py
git commit -m "feat: add provider event runtime" -- scripts/orchestrator/provider_event_runtime.py tests/test_provider_event_runtime.py
```

## Task 3: Pipeline Progress Integration

**Files:**
- Modify: `scripts/orchestrator/pipeline_runner.py`
- Test: `tests/test_pipeline_runner.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_pipeline_runner.py`:

```python
    def test_run_pipeline_reports_hook_progress(self):
        calls = []

        class StubReporter:
            def start_step(self, step_name, completed_steps=None):
                calls.append(("start", step_name, completed_steps))

            def finish_step(self, step_name=None, status="success"):
                calls.append(("finish", step_name, status))

            def fail_step(self, step_name, error):
                calls.append(("fail", step_name, str(error)))

            def log_provider_event(self, event):
                calls.append(("provider", event.get("provider"), event.get("event_type")))

        ctx = run_pipeline(
            request={"target_date": "2026-04-21"},
            hooks=[("input.hot_rank", stub_input), ("report.markdown_document", stub_report)],
            progress_reporter=StubReporter(),
        )

        self.assertEqual(calls[0], ("start", "input.hot_rank", 0))
        self.assertEqual(calls[1], ("finish", "input.hot_rank", "success"))
        self.assertEqual(calls[2], ("start", "report.markdown_document", 1))
        self.assertEqual(calls[3], ("finish", "report.markdown_document", "success"))
        self.assertEqual(ctx["runtime"]["module_logs"][0]["hook_name"], "input.hot_rank")

    def test_run_pipeline_collects_provider_events_from_context_handler(self):
        from orchestrator.provider_event_runtime import emit_provider_event

        def provider_hook(ctx):
            emit_provider_event(
                event_type="provider_call_start",
                hook_name="input.hot_rank",
                provider="akshare",
                operation="stock_zh_a_hist",
            )
            return {
                "value": {},
                "patches": {"normalized": {"provider_seen": True}},
                "diagnostics": {"hook_name": "input.hot_rank", "status": "success"},
                "artifacts": {},
            }

        ctx = run_pipeline(
            request={"target_date": "2026-04-21"},
            hooks=[("input.hot_rank", provider_hook)],
        )

        events = ctx["runtime"]["provider_events"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["provider"], "akshare")
        self.assertEqual(events[0]["operation"], "stock_zh_a_hist")
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run:

```bash
venv/bin/python3 -m unittest tests.test_pipeline_runner.PipelineRunnerTest.test_run_pipeline_reports_hook_progress tests.test_pipeline_runner.PipelineRunnerTest.test_run_pipeline_collects_provider_events_from_context_handler
```

Expected: FAIL with `TypeError: run_pipeline() got an unexpected keyword argument 'progress_reporter'` or missing `provider_events`.

- [ ] **Step 3: Modify `pipeline_runner.py`**

Change `run_pipeline` to this shape:

```python
from hooks.trace.trace_runtime import TraceRuntime

from orchestrator.context_store import build_empty_context, merge_hook_patches
from orchestrator.module_log_runtime import make_module_log
from orchestrator.provider_event_runtime import install_provider_event_handler


def run_pipeline(request, hooks, progress_reporter=None, provider_events=None):
    ctx = build_empty_context(request)
    trace = TraceRuntime(run_id=f"report:{request['target_date']}")
    provider_events = provider_events if provider_events is not None else []
    ctx["runtime"].setdefault("provider_events", provider_events)

    def handle_provider_event(event):
        provider_events.append(event)
        if progress_reporter is not None and hasattr(progress_reporter, "log_provider_event"):
            progress_reporter.log_provider_event(event)

    token = install_provider_event_handler(handle_provider_event)
    try:
        for index, (hook_name, hook_fn) in enumerate(hooks):
            if progress_reporter is not None:
                progress_reporter.start_step(hook_name, completed_steps=index)
            trace.before_hook(hook_name, [])
            try:
                result = hook_fn(ctx)
            except Exception as error:
                trace.on_error(hook_name, [], error)
                ctx["runtime"].setdefault("module_logs", []).append(
                    make_module_log(hook_name, status="error", error=error)
                )
                if progress_reporter is not None:
                    progress_reporter.fail_step(hook_name, error)
                raise
            ctx = merge_hook_patches(ctx, result.get("patches") or {})
            ctx["runtime"].setdefault("provider_events", provider_events)
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
            if progress_reporter is not None:
                progress_reporter.finish_step(hook_name, status="success")
        return ctx
    finally:
        token.reset()
        trace.finish()
        ctx["runtime"]["trace_events"] = trace.events
        ctx["runtime"]["provider_events"] = provider_events
```

- [ ] **Step 4: Run the pipeline tests**

Run:

```bash
venv/bin/python3 -m unittest tests.test_pipeline_runner
```

Expected: PASS.

- [ ] **Step 5: Commit Task 3**

Run:

```bash
git add scripts/orchestrator/pipeline_runner.py tests/test_pipeline_runner.py
git commit -m "feat: report hook progress from pipeline runner" -- scripts/orchestrator/pipeline_runner.py tests/test_pipeline_runner.py
```

## Task 4: Run Ledger Writer

**Files:**
- Create: `scripts/orchestrator/run_ledger_runtime.py`
- Test: `tests/test_run_ledger_runtime.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_run_ledger_runtime.py`:

```python
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from orchestrator.run_ledger_runtime import build_run_status, write_run_ledger


class RunLedgerRuntimeTest(unittest.TestCase):
    def test_build_run_status_marks_fallback_as_success_with_warnings(self):
        status = build_run_status(
            module_logs=[{"hook_name": "input.hot_rank", "status": "success"}],
            provider_events=[
                {
                    "event_type": "provider_call_fallback",
                    "hook_name": "input.hot_rank",
                    "provider": "akshare",
                    "fallback_provider": "tencent",
                }
            ],
        )

        self.assertEqual(status, "success_with_warnings")

    def test_write_run_ledger_creates_json_and_review_markdown(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = write_run_ledger(
                target_date="2026-05-08",
                reports_root=tmpdir,
                run_meta={"target_date": "2026-05-08", "elapsed_sec": 134},
                module_logs=[{"hook_name": "input.hot_rank", "status": "success"}],
                provider_events=[
                    {
                        "event_type": "provider_call_fallback",
                        "hook_name": "input.hot_rank",
                        "provider": "akshare",
                        "operation": "stock_zh_a_hist",
                        "fallback_provider": "tencent",
                        "error_message": "request timed out",
                    }
                ],
                artifacts={"full_report": "reports/2026-05-08_A股日报_完整版.md"},
            )

            overview = Path(paths["overview_md"]).read_text(encoding="utf-8")
            review = Path(paths["review_queue_md"]).read_text(encoding="utf-8")
            provider_events = json.loads(Path(paths["provider_events_json"]).read_text(encoding="utf-8"))

        self.assertIn("success_with_warnings", overview)
        self.assertIn("Fallback：1", overview)
        self.assertIn("input.hot_rank", review)
        self.assertIn("akshare", review)
        self.assertEqual(provider_events[0]["provider"], "akshare")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
venv/bin/python3 -m unittest tests.test_run_ledger_runtime
```

Expected: FAIL with `ModuleNotFoundError: No module named 'orchestrator.run_ledger_runtime'`.

- [ ] **Step 3: Implement `run_ledger_runtime.py`**

Create `scripts/orchestrator/run_ledger_runtime.py`:

```python
from __future__ import annotations

import json
from pathlib import Path


def _repo_root():
    return Path(__file__).resolve().parents[2]


def _runs_root(reports_root=None):
    base = Path(reports_root) if reports_root else _repo_root() / "reports"
    return base / "runs"


def build_run_status(module_logs=None, provider_events=None, interrupted=False):
    module_logs = list(module_logs or [])
    provider_events = list(provider_events or [])
    if interrupted:
        return "interrupted"
    if any(item.get("status") == "error" for item in module_logs):
        return "error"
    if any(str(item.get("event_type") or "").endswith(("_fallback", "_timeout", "_error")) for item in provider_events):
        return "success_with_warnings"
    return "success"


def _fallback_or_error_events(provider_events):
    result = []
    for event in provider_events or []:
        event_type = str(event.get("event_type") or "")
        if event_type.endswith(("_fallback", "_timeout", "_error")):
            result.append(event)
    return result


def _write_json(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _render_overview(target_date, status, run_meta, module_logs, provider_events, artifacts):
    fallback_count = sum(1 for item in provider_events if str(item.get("event_type") or "").endswith("_fallback"))
    error_count = sum(1 for item in module_logs if item.get("status") == "error")
    completed = sum(1 for item in module_logs if item.get("status") != "error")
    total = len(module_logs)
    elapsed = run_meta.get("elapsed_sec", 0)
    lines = [
        f"# {target_date} 日报运行总览",
        "",
        "## 运行结果",
        f"- 状态：{status}",
        f"- 总耗时：{elapsed:.0f}s",
        f"- Hook：{completed}/{total} completed",
        f"- Fallback：{fallback_count}",
        f"- Errors：{error_count}",
        "",
        "## 今日需要人工确认",
    ]
    review_events = _fallback_or_error_events(provider_events)
    if not review_events:
        lines.append("- 暂无 provider fallback、timeout 或 error。")
    for index, event in enumerate(review_events, start=1):
        hook = event.get("hook_name") or "-"
        provider = event.get("provider") or "-"
        operation = event.get("operation") or "-"
        reason = event.get("error_message") or event.get("event_type") or "-"
        fallback = event.get("fallback_provider") or "无"
        lines.extend(
            [
                f"{index}. {hook}",
                f"   - 原因：{provider} {operation} {reason}",
                f"   - 降级：{fallback}",
                "   - 建议动作：人工确认该模块输出是否可接受",
            ]
        )
    if artifacts:
        lines.extend(["", "## 产物"])
        for key, value in artifacts.items():
            lines.append(f"- {key}: `{value}`")
    return "\n".join(lines).rstrip() + "\n"


def _render_review_queue(provider_events):
    review_events = _fallback_or_error_events(provider_events)
    if not review_events:
        return "# 人工复盘清单\n\n- [ ] 今日无 provider fallback、timeout 或 error；抽查最终日报即可。\n"
    lines = ["# 人工复盘清单", ""]
    for event in review_events:
        hook = event.get("hook_name") or "-"
        provider = event.get("provider") or "-"
        operation = event.get("operation") or "-"
        fallback = event.get("fallback_provider") or "无"
        reason = event.get("error_message") or event.get("event_type") or "-"
        lines.extend(
            [
                f"- [ ] {hook} 的 {provider} {operation} 结果是否可接受？",
                f"  - 原因：{reason}",
                f"  - 降级：{fallback}",
                "  - 人工判断：",
                "  - 后续优化：",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def write_run_ledger(
    *,
    target_date,
    reports_root=None,
    run_meta=None,
    module_logs=None,
    provider_events=None,
    artifacts=None,
    interrupted=False,
):
    run_meta = dict(run_meta or {})
    module_logs = list(module_logs or [])
    provider_events = list(provider_events or [])
    artifacts = dict(artifacts or {})
    status = build_run_status(module_logs, provider_events, interrupted=interrupted)
    run_root = _runs_root(reports_root) / str(target_date)
    run_root.mkdir(parents=True, exist_ok=True)

    run_payload = dict(run_meta)
    run_payload.update(
        {
            "target_date": str(target_date),
            "status": status,
            "interrupted": bool(interrupted),
            "module_log_count": len(module_logs),
            "provider_event_count": len(provider_events),
        }
    )

    paths = {
        "run_json": str(run_root / "run.json"),
        "module_logs_json": str(run_root / "module_logs.json"),
        "provider_events_json": str(run_root / "provider_events.json"),
        "artifacts_json": str(run_root / "artifacts.json"),
        "overview_md": str(run_root / "overview.md"),
        "review_queue_md": str(run_root / "review_queue.md"),
    }

    _write_json(Path(paths["run_json"]), run_payload)
    _write_json(Path(paths["module_logs_json"]), module_logs)
    _write_json(Path(paths["provider_events_json"]), provider_events)
    _write_json(Path(paths["artifacts_json"]), artifacts)
    Path(paths["overview_md"]).write_text(
        _render_overview(target_date, status, run_payload, module_logs, provider_events, artifacts),
        encoding="utf-8",
    )
    Path(paths["review_queue_md"]).write_text(_render_review_queue(provider_events), encoding="utf-8")
    return paths
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
venv/bin/python3 -m unittest tests.test_run_ledger_runtime
```

Expected: PASS.

- [ ] **Step 5: Commit Task 4**

Run:

```bash
git add scripts/orchestrator/run_ledger_runtime.py tests/test_run_ledger_runtime.py
git commit -m "feat: write daily report run ledger" -- scripts/orchestrator/run_ledger_runtime.py tests/test_run_ledger_runtime.py
```

## Task 5: Legacy CLI Entry Progress and Ledger

**Files:**
- Modify: `scripts/daily_report_entry_demo.py`
- Test: `tests/test_daily_report_cli_progress.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_daily_report_cli_progress.py`:

```python
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class DailyReportCliProgressTest(unittest.TestCase):
    def test_main_prints_progress_and_writes_ledger_for_no_report_run(self):
        import daily_report_entry_demo as demo

        with tempfile.TemporaryDirectory() as tmpdir:
            output = []
            reporter_calls = []

            class StubReporter:
                def __init__(self, total_steps, stream=None, is_tty=None):
                    self.total_steps = total_steps

                def start_step(self, step_name, completed_steps=None):
                    reporter_calls.append(("start", step_name, completed_steps))

                def finish_step(self, step_name=None, status="success"):
                    reporter_calls.append(("finish", step_name, status))

                def fail_step(self, step_name, error):
                    reporter_calls.append(("fail", step_name, str(error)))

                def log_provider_event(self, event):
                    reporter_calls.append(("provider", event.get("provider"), event.get("event_type")))

            def fake_write_run_ledger(**kwargs):
                output.append(kwargs)
                return {"overview_md": str(Path(tmpdir) / "overview.md")}

            argv = ["daily_report_entry_demo.py", "2026-05-08", "--no-report"]
            with patch.object(sys, "argv", argv), \
                patch.object(demo, "RunProgressReporter", StubReporter), \
                patch.object(demo, "write_run_ledger", side_effect=fake_write_run_ledger), \
                patch.object(demo, "get_daily_data", return_value={"ok": True}), \
                patch.object(demo, "_save_data_snapshot", return_value=None), \
                patch.object(demo, "sync_snap_ui_static_data", return_value=None), \
                patch.object(demo, "print", side_effect=lambda *args, **kwargs: None):
                exit_code = demo.main()

        self.assertEqual(exit_code, 0)
        self.assertIn(("start", "input.daily_data", 0), reporter_calls)
        self.assertTrue(any(call[0] == "finish" and call[1] == "persist.snapshot" for call in reporter_calls))
        self.assertEqual(output[0]["target_date"], "2026-05-08")
        self.assertIn("module_logs", output[0])
        self.assertIn("provider_events", output[0])
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
venv/bin/python3 -m unittest tests.test_daily_report_cli_progress
```

Expected: FAIL because `daily_report_entry_demo` does not import `RunProgressReporter` or `write_run_ledger`.

- [ ] **Step 3: Modify imports in `daily_report_entry_demo.py`**

Add near other orchestrator imports:

```python
from orchestrator.provider_event_runtime import install_provider_event_handler
from orchestrator.run_ledger_runtime import write_run_ledger
from orchestrator.run_progress_runtime import RunProgressReporter
```

- [ ] **Step 4: Add helper functions in `daily_report_entry_demo.py` above `main()`**

Add:

```python
def _build_cli_steps(args):
    steps = []
    steps.append("input.replay_snapshot" if getattr(args, "replay", False) else "input.daily_data")
    steps.append("decision.run_mode")
    if not getattr(args, "no_report", False):
        steps.append("report.outputs")
    if getattr(args, "stock", None):
        steps.append("diagnostics.single_stock")
    steps.append("persist.snapshot")
    steps.append("export.snap_ui")
    return steps


def _finish_cli_step(reporter, step_name):
    if reporter is not None:
        reporter.finish_step(step_name, status="success")


def _start_cli_step(reporter, step_name, completed):
    if reporter is not None:
        reporter.start_step(step_name, completed_steps=completed)
```

- [ ] **Step 5: Wrap `main()` with reporter and provider sink**

Inside `main()`, after `args = parser.parse_args()`, create:

```python
    cli_steps = _build_cli_steps(args)
    reporter = RunProgressReporter(total_steps=len(cli_steps))
    provider_events = []
    module_logs = []
    artifacts = {}
    started_at = time.time()

    def _record_provider_event(event):
        provider_events.append(event)
        reporter.log_provider_event(event)

    provider_token = install_provider_event_handler(_record_provider_event)
```

Then wrap the existing body in:

```python
    try:
        completed = 0
        step_name = cli_steps[completed]
        _start_cli_step(reporter, step_name, completed)
        if args.replay:
            data, target_date = replay_from_snapshot(target_date)
        else:
            print(f"📅 获取数据: {target_date}")
            data = get_daily_data(target_date)
        module_logs.append({"hook_name": step_name, "status": "success"})
        _finish_cli_step(reporter, step_name)
        completed += 1

        step_name = cli_steps[completed]
        _start_cli_step(reporter, step_name, completed)
        run_mode = LEDGER_MODE_REPLAY if args.replay else LEDGER_MODE_FROZEN
        if run_mode == LEDGER_MODE_FROZEN:
            official_ledger = load_strategy_performance_ledger(mode=LEDGER_MODE_FROZEN)
            official_record = _find_strategy_record(official_ledger.get('records', []), target_date)
            official_report_path = _get_report_output_path(target_date, mode=LEDGER_MODE_FROZEN)
            if official_record or os.path.exists(official_report_path):
                run_mode = LEDGER_MODE_REPLAY
                print("🧊 检测到该日期已有官方历史，本次自动切换为实验模式，不改写历史。")
        module_logs.append({"hook_name": step_name, "status": "success"})
        _finish_cli_step(reporter, step_name)
        completed += 1

        # Keep the existing report/stock/snapshot logic in the same order, but
        # surround each block with _start_cli_step/_finish_cli_step and append
        # module_logs. Store returned report paths in artifacts.
    except Exception as error:
        active_step = cli_steps[min(completed, len(cli_steps) - 1)] if cli_steps else "main"
        module_logs.append({"hook_name": active_step, "status": "error", "error": str(error)})
        reporter.fail_step(active_step, error)
        raise
    finally:
        provider_token.reset()
        write_run_ledger(
            target_date=target_date,
            run_meta={"elapsed_sec": time.time() - started_at, "argv": list(sys.argv)},
            module_logs=module_logs,
            provider_events=provider_events,
            artifacts=artifacts,
        )
```

When moving the existing blocks into this structure:

- For report saving, capture `saved_paths = save_report_outputs(...)` and merge into `artifacts`.
- For stock diagnostic saving, capture the returned path in `artifacts["stock_diagnostic"]`.
- For snapshot, use `artifacts["snapshot"] = str(run_get_snapshot_path(target_date, mode=run_mode))` after `_save_data_snapshot(...)`.
- Keep `return 0` after the `finally` block path completes normally.

- [ ] **Step 6: Run the new CLI progress test**

Run:

```bash
venv/bin/python3 -m unittest tests.test_daily_report_cli_progress
```

Expected: PASS.

- [ ] **Step 7: Run existing entry help test**

Run:

```bash
venv/bin/python3 -m unittest tests.test_run_log_runtime.RunLogRuntimeTest.test_entry_help_command_stays_usable_with_log_capture
```

Expected: PASS.

- [ ] **Step 8: Commit Task 5**

Run:

```bash
git add scripts/daily_report_entry_demo.py tests/test_daily_report_cli_progress.py
git commit -m "feat: add progress ledger to daily report cli" -- scripts/daily_report_entry_demo.py tests/test_daily_report_cli_progress.py
```

## Task 6: AkShare Provider Event Instrumentation

**Files:**
- Modify: `scripts/input/iwencai_runtime.py`
- Test: `tests/test_iwencai_runtime.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_iwencai_runtime.py`:

```python
    def test_akshare_index_fallback_emits_provider_events(self):
        import pandas as pd
        from orchestrator.provider_event_runtime import install_provider_event_handler

        events = []

        def fake_index_daily_em(symbol):
            return pd.DataFrame([{"date": "2026-04-27", "close": 4086, "amount": 1.13e12}])

        fake_akshare = SimpleNamespace(stock_zh_index_daily_em=fake_index_daily_em)
        token = install_provider_event_handler(events.append)
        try:
            with patch.dict(sys.modules, {"akshare": fake_akshare}):
                result = get_wind_a_from_iwencai(
                    target_date="2026-04-27",
                    api_key="ok",
                    urlopen_fn=_raise_network_blocked,
                    print_fn=lambda *args, **kwargs: None,
                )
        finally:
            token.reset()

        self.assertEqual(result["data_source"], "akshare.stock_zh_index_daily_em")
        self.assertTrue(any(event["event_type"] == "provider_call_start" for event in events))
        self.assertTrue(any(event["event_type"] == "provider_call_success" for event in events))
        self.assertTrue(any(event["provider"] == "akshare" for event in events))
        self.assertTrue(any(event["operation"] == "stock_zh_index_daily_em" for event in events))
```

- [ ] **Step 2: Run the targeted test to verify it fails**

Run:

```bash
venv/bin/python3 -m unittest tests.test_iwencai_runtime.IwencaiRuntimeTest.test_akshare_index_fallback_emits_provider_events
```

Expected: FAIL because no provider events are emitted.

- [ ] **Step 3: Import provider observation helper**

At the top of `scripts/input/iwencai_runtime.py`, add:

```python
from orchestrator.provider_event_runtime import observed_provider_call
```

- [ ] **Step 4: Wrap `_latest_index_row()` AkShare call**

Replace:

```python
    df = stock_zh_index_daily_em_fn(symbol=symbol)
```

with:

```python
    df = observed_provider_call(
        provider="akshare",
        operation="stock_zh_index_daily_em",
        hook_name="input.iwencai",
        timeout_sec=15,
        rows_fn=lambda frame: 0 if frame is None else len(frame),
        call_fn=lambda: stock_zh_index_daily_em_fn(symbol=symbol),
    )
```

- [ ] **Step 5: Wrap sector and turnover AkShare calls**

In `_get_sector_change_akshare_fallback()`, replace:

```python
        df = ak.stock_board_industry_name_em()
```

with:

```python
        df = observed_provider_call(
            provider="akshare",
            operation="stock_board_industry_name_em",
            hook_name="input.sector_change",
            timeout_sec=15,
            rows_fn=lambda frame: 0 if frame is None else len(frame),
            call_fn=ak.stock_board_industry_name_em,
        )
```

In `_get_turnover_rank_akshare_fallback()`, replace:

```python
        df = ak.stock_zh_a_spot_em()
```

with:

```python
        df = observed_provider_call(
            provider="akshare",
            operation="stock_zh_a_spot_em",
            hook_name="input.turnover_rank",
            timeout_sec=15,
            rows_fn=lambda frame: 0 if frame is None else len(frame),
            call_fn=ak.stock_zh_a_spot_em,
        )
```

- [ ] **Step 6: Run the targeted test**

Run:

```bash
venv/bin/python3 -m unittest tests.test_iwencai_runtime.IwencaiRuntimeTest.test_akshare_index_fallback_emits_provider_events
```

Expected: PASS.

- [ ] **Step 7: Run the full iwencai runtime tests**

Run:

```bash
venv/bin/python3 -m unittest tests.test_iwencai_runtime
```

Expected: PASS.

- [ ] **Step 8: Commit Task 6**

Run:

```bash
git add scripts/input/iwencai_runtime.py tests/test_iwencai_runtime.py
git commit -m "feat: emit akshare provider events" -- scripts/input/iwencai_runtime.py tests/test_iwencai_runtime.py
```

## Task 7: DeepSeek Provider Event Instrumentation

**Files:**
- Modify: `scripts/llm_service.py`
- Test: `tests/test_llm_service.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_llm_service.py`:

```python
    def test_llm_proxy_emits_provider_events_for_batch_analysis(self):
        from orchestrator.provider_event_runtime import install_provider_event_handler

        captured = {}
        events = []

        class LegacyService:
            def analyze_events_batch(self, events_for_analysis, batch_size=4, progress_callback=None, use_cache=True):
                captured["events"] = events_for_analysis
                return [{"main_direction": "AI算力"}]

        def export_impl(module_name, attr_name, default):
            return lambda: LegacyService()

        module = self._load_module_with_export(export_impl)
        service = module.get_llm_service()
        token = install_provider_event_handler(events.append)
        try:
            result = service.analyze_events_batch([{"title": "AI大会"}], batch_size=8)
        finally:
            token.reset()

        self.assertEqual(result[0]["main_direction"], "AI算力")
        self.assertEqual(events[0]["event_type"], "provider_call_start")
        self.assertEqual(events[0]["provider"], "deepseek")
        self.assertEqual(events[0]["operation"], "analyze_events_batch")
        self.assertEqual(events[1]["event_type"], "provider_call_success")

    def test_llm_proxy_classifies_timeout_event(self):
        from orchestrator.provider_event_runtime import install_provider_event_handler

        events = []

        class LegacyService:
            def analyze_events_batch(self, events_for_analysis, batch_size=4, progress_callback=None, use_cache=True):
                raise TimeoutError("deepseek timed out")

        def export_impl(module_name, attr_name, default):
            return lambda: LegacyService()

        module = self._load_module_with_export(export_impl)
        service = module.get_llm_service()
        token = install_provider_event_handler(events.append)
        try:
            with self.assertRaises(TimeoutError):
                service.analyze_events_batch([{"title": "AI大会"}], batch_size=8)
        finally:
            token.reset()

        self.assertEqual(events[1]["event_type"], "provider_call_timeout")
        self.assertEqual(events[1]["provider"], "deepseek")
        self.assertIn("deepseek timed out", events[1]["error_message"])
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run:

```bash
venv/bin/python3 -m unittest tests.test_llm_service.LlmServiceEnvTest.test_llm_proxy_emits_provider_events_for_batch_analysis tests.test_llm_service.LlmServiceEnvTest.test_llm_proxy_classifies_timeout_event
```

Expected: FAIL because the proxy does not emit provider events.

- [ ] **Step 3: Import provider helper**

In `scripts/llm_service.py`, add:

```python
from orchestrator.provider_event_runtime import observed_provider_call
```

- [ ] **Step 4: Instrument proxy methods**

Modify `_CalendarContractLLMServiceProxy`:

```python
class _CalendarContractLLMServiceProxy:
    def __init__(self, service):
        self._service = service

    def __getattr__(self, name):
        return getattr(self._service, name)

    def analyze_events_batch(self, events, *args, **kwargs):
        prepared_events = [_event_with_calendar_contract(event) for event in (events or [])]
        timeout_sec = int(os.environ.get("DEEPSEEK_TIMEOUT_SEC", "30") or 30)
        return observed_provider_call(
            provider="deepseek",
            operation="analyze_events_batch",
            hook_name="calendar_events.llm",
            timeout_sec=timeout_sec,
            rows_fn=lambda result: len(result or []),
            call_fn=lambda: self._service.analyze_events_batch(prepared_events, *args, **kwargs),
        )

    def analyze_event_sectors(self, event_title, event_summary="", *args, **kwargs):
        timeout_sec = int(os.environ.get("DEEPSEEK_TIMEOUT_SEC", "30") or 30)
        return observed_provider_call(
            provider="deepseek",
            operation="analyze_event_sectors",
            hook_name="calendar_events.llm",
            timeout_sec=timeout_sec,
            rows_fn=lambda result: 1 if result else 0,
            call_fn=lambda: self._service.analyze_event_sectors(event_title, event_summary, *args, **kwargs),
        )
```

Modify `_wrap_calendar_contract_service()` so it wraps services with either method:

```python
def _wrap_calendar_contract_service(service):
    if service is None:
        return service
    if hasattr(service, "analyze_events_batch") or hasattr(service, "analyze_event_sectors"):
        return _CalendarContractLLMServiceProxy(service)
    return service
```

- [ ] **Step 5: Run llm service tests**

Run:

```bash
venv/bin/python3 -m unittest tests.test_llm_service
```

Expected: PASS.

- [ ] **Step 6: Commit Task 7**

Run:

```bash
git add scripts/llm_service.py tests/test_llm_service.py
git commit -m "feat: emit deepseek provider events" -- scripts/llm_service.py tests/test_llm_service.py
```

## Task 8: End-to-End Verification

**Files:**
- No new files unless a prior test exposes a root-cause defect.

- [ ] **Step 1: Run focused observability suite**

Run:

```bash
venv/bin/python3 -m unittest \
  tests.test_run_progress_runtime \
  tests.test_provider_event_runtime \
  tests.test_run_ledger_runtime \
  tests.test_pipeline_runner \
  tests.test_daily_report_cli_progress \
  tests.test_iwencai_runtime \
  tests.test_llm_service
```

Expected: PASS.

- [ ] **Step 2: Run CLI help smoke test**

Run:

```bash
venv/bin/python3 scripts/daily_report_entry_demo.py --help
```

Expected: exit code 0 and output includes `A股日报数据获取入口` and `--replay`.

- [ ] **Step 3: Run a no-report smoke test with a mocked date only if market APIs are not needed**

Use this only after unit tests pass and before a real daily run:

```bash
venv/bin/python3 scripts/daily_report_entry_demo.py 2026-05-08 --no-report
```

Expected:

- CLI prints progress lines with `current=`.
- `reports/runs/2026-05-08/overview.md` exists.
- `reports/runs/2026-05-08/provider_events.json` exists.

If this command calls live market APIs and stalls, stop it with Ctrl-C and inspect the partial `logs/runs/*.log` plus `reports/runs/2026-05-08/`.

- [ ] **Step 4: Inspect generated ledger files**

Run:

```bash
ls -la reports/runs/2026-05-08
sed -n '1,160p' reports/runs/2026-05-08/overview.md
sed -n '1,160p' reports/runs/2026-05-08/review_queue.md
```

Expected:

- `overview.md` shows status, elapsed seconds, hook completion, fallback count, error count.
- `review_queue.md` has either a no-issue checklist item or concrete fallback/timeout review items.

- [ ] **Step 5: Commit verification-only doc or fixture updates if created**

If no files changed during verification, do not commit. If a test fixture changed because the ledger output is intentionally snapshot-tested, run:

```bash
git add tests/fixtures/path-that-changed
git commit -m "test: update run ledger fixture" -- tests/fixtures/path-that-changed
```

## Self-Review Result

- Spec coverage: CLI progress bar is covered by Task 1 and Task 5; provider events are covered by Task 2, Task 6, and Task 7; pipeline hook progress is covered by Task 3; run ledger and review queue are covered by Task 4; end-to-end verification is covered by Task 8.
- Placeholder scan: no unresolved placeholder markers or unspecified "add validation" steps remain. Each code-changing task names files, test commands, expected failures, and implementation snippets.
- Type consistency: `RunProgressReporter`, `observed_provider_call`, `install_provider_event_handler`, `write_run_ledger`, and `provider_events` names are consistent across tests and implementation steps.
