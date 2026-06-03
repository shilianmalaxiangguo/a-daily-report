# Daily Report Agent Runner Design

Date: 2026-05-24
Status: Approved design direction
Scope: first project-level runner for `a-daily-report`

## Background

The daily-report repo is no longer only a skill prompt. It already contains a report engine, pipeline runtime, run logs, replay artifacts, report acceptance checks, wiki knowledge, a decision ledger, and snap-ui review surfaces. The next useful move is to make these pieces behave like one daily work agent.

The article on Harness Engineering is useful here because the bottleneck is not "can the model write more text". The bottleneck is whether every run has enough context, writes auditable artifacts, exposes degraded data, and reviews yesterday's designed participation against real facts.

The first project-level slice should therefore be a Daily Report Agent Runner: a thin but explicit workflow owner around the existing generation engine.

## In Scope

1. Add a project-level runner concept named `DailyReportAgentRunner`.
2. Preserve the existing report-generation core instead of rewriting it.
3. Give one daily run a stable lifecycle:
   - load request
   - load required context
   - run report generation
   - write run ledger
   - audit report output
   - update decision ledger
   - produce review queue
   - review prior participation plans when next-day facts exist
4. Standardize first-version artifacts:
   - rendered daily report markdown
   - `reports/runs/<trade-date>/overview.md`
   - `reports/runs/<trade-date>/run.json`
   - `reports/runs/<trade-date>/review_queue.md`
   - report audit result
   - decision-ledger update under `data/decision-ledger/`
5. Keep `SKILL.md` as a compact natural-language router, not the main system.
6. Keep snap-ui as a consumer of published artifacts, not a second trading-logic engine.

## Out of Scope

1. No automatic trading.
2. No always-on backend service.
3. No scheduler in the first slice.
4. No snap-ui rewrite.
5. No replacement of existing report renderers.
6. No broad knowledge-platform rebuild.
7. No new command taxonomy beyond the minimum runner entry needed for the first slice.

## Non-goals

1. Do not increase report quality by making the prompt longer.
2. Do not let free-form model text override deterministic facts, replay output, or tests.
3. Do not add new subjective report-state labels unless they reduce ambiguity now.
4. Do not turn workflow memory into stock-tracking memory.
5. Do not hide missing or degraded data behind polished wording.

## Design Principle

Daily report quality is treated as:

```text
report quality = model judgment x context quality x replay quality
```

The runner improves the second and third factors. It makes context loading explicit, run evidence durable, and next-day review unavoidable.

## Architecture

```text
SKILL.md
  -> intent routing only

DailyReportAgentRunner
  -> request loading
  -> required context loading
  -> existing report generation
  -> run ledger writing
  -> report acceptance audit
  -> decision-ledger writing
  -> review queue writing
  -> prior-plan replay review

Existing runtime
  -> daily_report_entry_demo.py
  -> pipeline_runner / report_orchestrator
  -> report renderers
  -> report_acceptance_audit
  -> decision_ledger

Inspection surfaces
  -> reports/runs/<trade-date>/
  -> data/decision-ledger/
  -> reports/replay/
  -> snap-ui public data export
```

`DailyReportAgentRunner` owns orchestration, not domain judgment. Domain judgment stays in the existing report, inference, selection, and decision-ledger modules.

## Runner Lifecycle

### 1. Load Request

Inputs:

- target trade date
- report mode: fresh or replay
- output variant
- whether to update decision ledger
- whether to review previous unreviewed participation plans

The first implementation can use a Python entrypoint before adding a polished CLI alias.

### 2. Load Context

Required context sources:

- `SKILL.md`
- `references/report-contract.md`
- `references/reasoning-mode-contract.md`
- `references/verification.md` when verification is requested
- `wiki/README.md` and specific wiki pages only when the run touches that domain
- prior decision-ledger snapshots needed for replay review

This is progressive disclosure. The runner should not load the whole wiki by default.

### 3. Generate Report

The runner calls the existing report-generation path. It must preserve current behavior and artifacts unless a later implementation plan scopes a narrow change.

The runner records:

- start time
- end time
- target date
- mode
- output paths
- provider warnings
- missing critical data
- degraded data sources
- raised exceptions

### 4. Write Run Ledger

`reports/runs/<trade-date>/overview.md` should answer:

- Did the run finish?
- Is the report usable?
- Which key data is missing or degraded?
- Which provider paths were degraded?
- Which output artifacts were produced?
- What needs manual review?

`run.json` should carry the machine-readable equivalent.

### 5. Audit Report Output

The first runner-level audit should check:

- critical market data exists
- report has a clear conclusion
- next-day action is explicit
- no duplicate no-participation conclusion
- no fake precision for missing values
- no visible wording that violates `wiki/交易思想/日报术语契约.md`
- each high-conviction sample has a participation rehearsal or explicit no-participation reason

The audit result should be written into the run folder and summarized in `overview.md`.

### 6. Update Decision Ledger

The runner ensures high-conviction samples are persisted as structured facts rather than only report prose.

Required first-version fields:

- report date
- stock code and name
- source tier
- entry timing
- buy window
- position state: `0%`, `50%`, or `100%`
- planned participation
- cancellation conditions
- invalidation price when available
- tracking window

The runner should call existing `decision_ledger` code where possible rather than writing another ledger implementation.

### 7. Produce Review Queue

`review_queue.md` is the human-facing calibration queue.

Examples:

```md
- [ ] Critical data incomplete: 中证全指 missing.
  - Effect: report action should not be trusted until fixed.
  - Human judgment:
  - Follow-up:

- [ ] Participation rehearsal needs review: 300000 sample.
  - Reason: next-day facts are now available.
  - Human judgment:
  - Follow-up:
```

The queue is not a task manager. It is the daily review surface for uncertain or degraded outputs.

### 8. Review Prior Participation Plans

When next-day facts exist, the runner should inspect prior unreviewed `planned_participation` records and write `participation_review`.

Allowed labels:

- `预演命中`
- `预演作废`
- `错过后方案命中`
- `预演过早`
- waiting for more facts

The review must be derived from explicit facts already defined by the decision-ledger contract. It must not become free-form hindsight.

## Error Handling

- If critical market-state data is incomplete, the runner marks the report as not usable and records the reason.
- If a provider path is degraded, the runner records the provider, operation, fallback, and impact.
- If report generation fails, the runner still writes a partial run folder when possible.
- If decision-ledger update fails, the run can still preserve the report but must mark ledger persistence as failed.
- If next-day facts are missing, prior participation review remains pending instead of being fabricated.

## Testing Strategy

The implementation plan should start with focused tests:

1. Runner writes a run folder for a fake successful report.
2. Runner marks critical data as incomplete when required fields are missing.
3. Runner writes a review queue item for degraded provider output.
4. Runner calls the report audit and surfaces audit failures in `overview.md`.
5. Runner persists a high-conviction participation plan through existing decision-ledger code.
6. Runner leaves prior participation review pending when next-day facts are absent.
7. Runner writes `participation_review` only when explicit facts exist.

All Python verification must use:

```bash
.generated/venv-py314/bin/python3.14 -m unittest ...
```

## Done Definition

The first slice is complete when a single runner entry can produce, for one target date:

1. the daily report artifact,
2. `reports/runs/<trade-date>/overview.md`,
3. `reports/runs/<trade-date>/run.json`,
4. `reports/runs/<trade-date>/review_queue.md`,
5. a report audit summary,
6. a decision-ledger update for high-conviction samples,
7. pending or completed prior participation review based on available facts.

The user should be able to inspect the run folder and answer:

- Can I use today's report?
- Which data was missing or degraded?
- What action does the report recommend?
- Which judgment samples entered the ledger?
- What needs manual review?
- Which prior participation plans were reviewed or left pending?

## Follow-up Proposals

These are valuable but should stay out of the first slice:

1. A polished `daily-report agent run <date>` CLI wrapper.
2. snap-ui run folder browser.
3. scheduled local heartbeat for daily generation.
4. provider-level quality dashboard.
5. D1 synchronization of runner audit status.
6. richer wiki-based context selection.
7. multi-agent review after the single-runner contract is stable.
