# Context Model

## Purpose

Define the shared context slices used by the pipeline.

## Context Slices

- `request`: run parameters such as date, mode, and output variants
- `raw`: unnormalized source payloads from input hooks
- `normalized`: cleaned factual inputs ready for inference
- `derived`: intermediate judgments produced by inference hooks
- `decision`: final run-level choices before report generation
- `sections`: structured report sections assembled from derived context
- `rendered`: formatted report artifacts such as markdown text
- `diagnostics`: run-level warnings, confidence, missing fields, fallback usage
- `runtime`: timers, mode flags, cache hits, execution metadata

## Rules

- Each hook reads only the slices it declares.
- Inference hooks must not read rendered output.
- Report hooks must not recompute domain judgments.
- Persist hooks must only write output artifacts outside the shared context.
