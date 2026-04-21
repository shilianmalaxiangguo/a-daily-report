# Trace Module

## Purpose

Record pipeline execution in a consistent machine-readable form.

## Responsibilities

- Emit run-level and hook-level trace events.
- Capture warnings, failures, and timing data.
- Support debugging without coupling to business logic.

## Boundaries

- May observe all stages.
- Must not influence decisions.

