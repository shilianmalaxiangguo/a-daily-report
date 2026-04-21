# Report Module

## Purpose

Assemble report sections and rendered output from decided context.

## Responsibilities

- Turn derived conclusions into report sections.
- Render markdown without re-running inference.
- Populate `sections` and `rendered`.

## Boundaries

- May read `derived` and `decision`.
- Must not change business decisions.

