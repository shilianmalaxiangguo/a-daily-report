# Daily Report Decision Loop Full Attack

## Goal

Turn the daily report into a full decision system: judgment fieldization, tomorrow rehearsal, participation review, historical settlement, and decision statistics. The first implementation slice has already started this loop, but the full attack must now become a parent campaign with child tasks instead of one unbounded code change.

## Current Coverage Facts

- Official full reports currently cover 42 trading days: `2026-03-31` through `2026-06-01`.
- Official snapshots currently cover 41 trading days: `2026-04-01` through `2026-06-01`.
- Replay full reports currently cover 36 trading days: `2026-04-03` through `2026-06-01`.
- Current decision-ledger code still uses 25 trading days as the default recent cycle in several report surfaces.
- Therefore 60-day and 120-day review windows are target states, not current facts. Report output must show the real covered sample count and date range before any 60/120-day wording is allowed.

## In Scope

- Treat this task as the parent campaign for all Daily Report Decision Loop work.
- Preserve the first closed-loop slice already implemented in `scripts/report/decision_ledger.py` and `tests/test_decision_ledger.py`.
- Split the full attack into child Trellis tasks that can be implemented, checked, and replayed independently.
- Capture the current historical coverage limit and the expansion path to 60/120 trading days.
- Keep the relationship clear: the daily report remains the decision surface; quantification supports it.

## Out of Scope

- One giant implementation PR that changes ledger, front page, historical expansion, statistics, and probability support at once.
- Fully automated trading, broker execution, cost/slippage modeling, or broad factor mining.
- Claiming 60/120-day evidence before the repository has source facts and settlement coverage for those windows.
- Rewriting unrelated report sections or cleaning unrelated dirty worktree changes.

## Non-goals

- Do not let statistics create tomorrow's action without an explicit report action.
- Do not treat missing historical facts as failed or successful decisions.
- Do not hide a short sample behind long-window labels.
- Do not collapse stock selection quality, observation-window quality, missed-entry behavior, and risk-reward into one score.

## Child Tasks

1. `06-02-decision-history-coverage-expansion`
   - First priority.
   - Audits available reports, snapshots, replay snapshots, and decision-ledger rows.
   - Makes report/statistic wording use true sample count and date range.
   - Defines the path from current coverage to 60 and 120 trading days.

2. `06-02-judgment-ledger-full-fieldization`
   - Converts all major daily-report judgments into structured settlement fields.
   - Covers mainline evidence, sample tier, trend-chain position, position plan, participation window, cancellation conditions, missed-entry plan, and source dates.

3. `06-02-decision-cockpit-front-page`
   - Rebuilds the front page around five answers: participation qualification, mainline, tomorrow action, cancellation condition, and prior rehearsal result.
   - Keeps analysis sections subordinate to the final decision surface.

4. `06-02-decision-statistics-panel`
   - Produces the instrument-panel summaries after ledger coverage is trustworthy.
   - Tracks win rate, drawdown, sample tier rotation, window quality, and missed-entry quality using only auditable rows.

5. `06-02-semi-automatic-probability-support`
   - Adds probability and base-rate support after historical statistics are available.
   - Supports report judgment but does not replace the report action contract.

## Acceptance Criteria

- [ ] Parent PRD documents current historical coverage truth and no longer implies current 60/120-day coverage.
- [ ] Child Trellis tasks exist for history coverage, ledger fieldization, front-page cockpit, statistics panel, and probability support.
- [ ] Each child task has its own PRD, implementation context, and check context.
- [ ] The daily-report decision-loop spec records the current coverage rule and expansion target.
- [ ] Future implementation must start with the history coverage child task unless the user explicitly changes priority.

## Definition of Done

- Trellis task tree is updated.
- Parent and child PRDs are written.
- Relevant `.trellis/spec/backend/daily-report-decision-loop.md` guidance is updated.
- Trellis validation runs for the parent and child tasks.
- No business code is changed by this planning update.

## Technical Approach

- Keep parent task as the campaign index.
- Use child tasks for implementation boundaries.
- Put factual coverage research in `research/history-coverage-current-state.md`.
- Require every future statistics surface to expose `sample_count`, `start_date`, `end_date`, and missing-fact handling.

## Decision (ADR-lite)

**Context**: The user rejected a narrow MVP-only route and correctly pointed out that current review coverage does not satisfy 60/120-day claims.

**Decision**: Expand from a single implementation slice into a full campaign, but split the work into Trellis child tasks. Treat current 25/42-day coverage as the honest starting point and 60/120 days as expansion targets.

**Consequences**: The project can advance aggressively without losing auditability. Historical coverage becomes the first attack point because every later statistic and probability view depends on truthful sample boundaries.

## Technical Notes

- Use Python 3.14 only: `.generated/venv-py314/bin/python3.14`.
- Primary spec: `.trellis/spec/backend/daily-report-decision-loop.md`.
- Current implementation slice: `scripts/report/decision_ledger.py`, `tests/test_decision_ledger.py`.
- Required historical truth file: `.trellis/tasks/06-02-daily-report-decision-loop/research/history-coverage-current-state.md`.
