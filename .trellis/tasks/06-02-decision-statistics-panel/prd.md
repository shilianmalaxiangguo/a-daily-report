# Decision Statistics Panel

## Goal

Build the instrument-panel layer that summarizes decision quality after ledger coverage is trustworthy: position-plan results, sample-tier rotation, mainline evidence quality, participation-window quality, and missed-entry behavior.

## In Scope

- Statistics derived from auditable decision-ledger rows.
- Coverage metadata for every statistic.
- Separate summaries for:
  - position plan 0/50/100,
  - sample tier high/middle/low,
  - mainline evidence score,
  - participation window,
  - missed-entry plan.
- Tests for missing facts and short sample handling.

## Out of Scope

- Building the historical coverage expansion itself.
- Front-page cockpit redesign.
- Probability recommendation.
- Broad backtesting framework or factor mining.

## Non-goals

- Do not present low-sample statistics as stable truth.
- Do not combine selection quality and execution quality into one number.
- Do not create next-day action from statistics alone.

## Requirements

- Every statistic includes:
  - sample count,
  - first date,
  - last date,
  - missing-fact count or missing fields,
  - metric definition.
- Statistics must distinguish selection quality, observation-window quality, risk-reward, and execution review.
- Current covered sample may be used first; 60/120-day views require coverage from the history expansion child task.

## Acceptance Criteria

- [ ] Statistics renderer/helper includes coverage metadata.
- [ ] Tests cover short sample, missing facts, and segmented statistics.
- [ ] Report output frames the panel as past evidence, not tomorrow action.

## Definition of Done

- Unit tests pass with Python 3.14.
- Report replay sample passes if rendering changes.
- User-visible text follows terminology rules.

## Technical Approach

- Depend on fieldized ledger rows and coverage metadata.
- Keep the first version file-local or helper-local unless repeated complexity requires extraction.
- Add probability support only after this panel is stable.
