# Context Model

## Purpose

Define the shared context slices used by the pipeline.

## Context Slices

- `raw`: unnormalized source payloads from input hooks
- `normalized`: cleaned factual inputs ready for inference
- `derived`: intermediate judgments produced by inference hooks
- `decision`: final run-level choices before report generation
- `sections`: structured report sections assembled from derived context
- `rendered`: formatted report artifacts such as markdown text
- `artifacts`: saved outputs and traceable side products

## Rules

- Each hook reads only the slices it declares.
- Inference hooks must not read rendered output.
- Report hooks must not recompute domain judgments.
- Persist hooks must only write artifacts.

