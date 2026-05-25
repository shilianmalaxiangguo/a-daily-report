# Understand Anything Dev Flow

Date: 2026-05-25
Scope: local developer navigation for `a-daily-report`

## Purpose

`Understand-Anything` is a local helper for navigating this project and reviewing the effect of code changes. It is not part of daily report generation and is not a source for trading conclusions.

## Use Modes

### Project Navigation

Use the project graph when you need to understand where a report concept, renderer, data source, selection step, or audit check lives.

Recommended flow:

1. Refresh the project graph after meaningful source changes.
2. Open the dashboard when a visual overview helps.
3. Use graph context to find relevant files, then verify behavior with the repo's normal tests and replay artifacts.

### Change-Impact Review

Use change-impact review after a non-trivial diff, especially when edits touch report rendering, selection, market-state, data-source, decision-ledger, or snap-ui export code.

Recommended flow:

1. Review the Git diff.
2. Run the graph-based diff review.
3. Inspect affected components before final verification.
4. Run the relevant Python 3.14 tests or replay checks required by the changed modules.

### Local-Only Exploration

The graph, dashboard data, intermediate files, and diff overlay are local helper artifacts. Do not treat them as report source data, and do not publish them unless a later reviewed design explicitly changes that.

## Boundaries

- Do not put graph summaries into the report body.
- Do not use the graph to decide participation, position, cancellation, or final report conclusions.
- Do not let graph output override deterministic facts, bounded reasoning payloads, tests, replay output, or human review.
- Do not use this workflow as a substitute for the report contract or data-source contract.

## Local Artifacts

- `.understand-anything/knowledge-graph.json`: local project graph if generated.
- `.understand-anything/domain-graph.json`: local domain graph if generated later.
- `.understand-anything/diff-overlay.json`: local dashboard overlay for changed and affected files.
- `.understand-anything/intermediate/`: temporary working files.
- `.understand-anything/tmp/`: temporary validation scripts.

By default, generated graph artifacts stay local.
