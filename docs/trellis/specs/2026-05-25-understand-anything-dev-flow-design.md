# Understand Anything Dev Flow Design

Date: 2026-05-25
Status: Proposed design
Scope: developer-navigation support for `a-daily-report`

## Background

`Understand-Anything` can analyze a codebase, build a local knowledge graph, open a browser dashboard, and describe the effect of code changes against that graph. The daily-report project already has a large Python report engine, wiki knowledge, replay artifacts, snap-ui exports, and many local generated files.

The useful first slice is not to make the report depend on this tool. The useful first slice is to add a local development aid for project navigation and change-impact review.

## In Scope

1. Install or update `Understand-Anything` for the local Codex/Hermes environment.
2. Add a project-level `.understand-anything/.understandignore` focused on excluding generated artifacts, local UI copies, caches, environments, and large runtime data.
3. Add a short project workflow note that explains:
   - when to generate or refresh the project graph;
   - when to run change-impact review;
   - what local artifacts are produced;
   - what must not be treated as report input.
4. Verify that the local plugin links and project ignore rules are present.
5. Keep all generated graph artifacts local by default.

## Out of Scope

1. Do not change daily report generation.
2. Do not change report wording, report data contracts, decision-ledger behavior, or snap-ui export behavior.
3. Do not generate or commit `.understand-anything/knowledge-graph.json` in this first slice.
4. Do not analyze the `wiki/` knowledge graph in this first slice.
5. Do not add automatic post-commit refresh behavior yet.
6. Do not add CI, PR checks, schedulers, or a new project service.

## Non-goals

1. Do not use `Understand-Anything` as a trading judgment source.
2. Do not let graph summaries enter the report body.
3. Do not replace the existing report contracts, tests, replay checks, or audit scripts.
4. Do not create a broad knowledge platform around this tool.
5. Do not add abstractions for future automation before this local workflow proves useful.

## Design

The tool is treated as a local developer companion.

```text
Local developer request
  -> Understand-Anything skills
      -> project graph
      -> dashboard
      -> change-impact review

Daily report runtime
  -> unchanged

Report artifacts
  -> unchanged
```

The graph may help a developer ask questions such as:

- which files participate in the report front page;
- which modules are near a changed renderer;
- which report layers are affected by a current diff;
- where an unfamiliar selection or market-state concept lives.

The graph must not answer trading participation, position, cancellation, or report conclusion questions. Those remain owned by the deterministic report inputs, bounded reasoning payloads, report renderer, tests, replay output, and human review.

## Project Ignore Rules

Create `.understand-anything/.understandignore` with a conservative starter set. It should exclude:

- `.git/`
- `.generated/`
- `.worktrees/`
- `reports/`
- `replay/`
- `data/`
- `snapshots/`
- `logs/`
- `venv/`
- `.hermes/`
- Python caches
- local tool caches under `scripts/`
- `snap-ui/`
- `snap-ui-remote-*`
- image, archive, and minified build artifacts

The rule should follow the repo's existing ignore preference: recursive generated folders stay out of local analysis inputs unless a later task explicitly includes one.

## Workflow Note

Add a short document under `docs/ops/` named `understand-anything-dev-flow.md`.

The note should define three usage modes:

1. Project navigation: refresh the graph after meaningful source changes, then use the dashboard or chat-style graph context to find modules.
2. Change-impact review: after a non-trivial diff, run the diff review against the graph and inspect affected components before final verification.
3. Local-only exploration: generated graph and dashboard files are local helper artifacts unless a later reviewed design chooses to publish them.

The note should explicitly state that this tool is not part of daily report generation and not a source for trading conclusions.

## Verification

The first slice is considered verified when:

1. Plugin install or update succeeds for Codex/Hermes.
2. Local skill links resolve to the installed plugin checkout.
3. `.understand-anything/.understandignore` exists and includes the generated folders named above.
4. `git check-ignore` confirms representative local generated paths are excluded from normal Git tracking where applicable.
5. The new workflow note exists and keeps the boundary clear.

Generating the full project graph may be run after these checks, but it is not required for this first slice because the repo currently has a large, dirty worktree and a full graph run may take meaningful time.

## Done Definition

1. `Understand-Anything` is installed or updated locally.
2. The daily-report repo has a minimal `.understandignore` for local project analysis.
3. The repo has a short developer-flow note for project navigation and change-impact review.
4. No report-generation code or report output behavior changes.
5. Generated graph artifacts remain local by default.
