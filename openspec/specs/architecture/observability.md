# Observability

## Purpose

Define the trace and diagnostics surface for the pipeline.

## Requirements

- Emit trace events for hook start, hook finish, warnings, and errors.
- Attach per-hook diagnostics with timing, confidence, and status.
- Keep diagnostics machine-readable and stable across runs.
- Preserve enough context to explain a decision after execution.

## Cross-Cutting Fields

- `status`
- `duration_ms`
- `confidence`
- `warnings`

