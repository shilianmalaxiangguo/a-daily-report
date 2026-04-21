# Error Handling

## Purpose

Define failure behavior for the hook pipeline.

## Policy

- Prefer degradable failures for non-critical derivations.
- Stop the pipeline for unrecoverable input or persistence failures.
- Surface hook-local diagnostics before raising a run-level error.
- Preserve upstream facts when a downstream stage fails.

## Rules

- Input errors should identify the failing source and payload shape.
- Inference errors should identify the failing hook and missing context.
- Report errors should identify the missing section or render artifact.
- Persist errors should never mutate decision context.

