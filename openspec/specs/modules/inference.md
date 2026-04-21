# Inference Module

## Purpose

Convert normalized facts into structured judgments.

## Responsibilities

- Derive market phase, mainline, and execution permission.
- Write decisions into `derived` and `decision`.
- Keep the reasoning explainable from upstream facts.

## Boundaries

- May read `raw` and `normalized`.
- Must not read `sections` or `rendered`.

