# Judgment Ledger Full Fieldization

## Goal

Convert daily-report judgments into structured records that can be reviewed and settled: mainline evidence, sample tier, trend-chain position, position plan, participation window, cancellation conditions, missed-entry plan, and source dates.

## In Scope

- Fieldize all major judgment types used by the daily report.
- Preserve the existing decision-ledger contracts.
- Make missing fields explicit instead of turning language-only judgment into performance credit.
- Add tests for records with complete, partial, and missing facts.

## Out of Scope

- Historical 60/120-day expansion; that belongs to the coverage child task.
- Front-page redesign; that belongs to the cockpit child task.
- Probability scoring; that belongs to the probability support child task.
- Fully automated trading or broker execution.

## Non-goals

- Do not collapse all judgment quality into one success label.
- Do not invent review facts from strong wording.
- Do not add a new storage layer unless current repeated complexity requires it.

## Requirements

- Every high-conviction item has a `decision_ledger_record.v1`-compatible shape.
- Records preserve:
  - report date,
  - source report path,
  - market participation qualification,
  - 0/50/100 position plan,
  - mainline and evidence labels,
  - sample tier,
  - trend-chain position,
  - planned participation,
  - cancellation conditions,
  - source dates,
  - missing fields.
- Records with incomplete facts remain auditable and render as incomplete or waiting for facts.

## Acceptance Criteria

- [ ] Tests cover full, partial, and language-only records.
- [ ] Missing fields remain visible in rendered rows or artifacts.
- [ ] Fieldized records do not create tomorrow action unless planned participation exists.
- [ ] Existing decision-ledger tests still pass.

## Definition of Done

- Python 3.14 unit tests pass for decision-ledger behavior.
- Relevant replay sample completes if report rendering changes.
- Spec remains aligned with `.trellis/spec/backend/daily-report-decision-loop.md`.

## Technical Approach

- Extend the existing decision-ledger path first.
- Prefer existing markdown/candidate extraction functions over new parsers.
- Keep source-date and missing-field behavior consistent with the coverage child task.
