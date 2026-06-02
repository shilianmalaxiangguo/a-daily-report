# Five Judgment Review Statistics

## Goal

Build a small, auditable statistics module for exactly five daily-report judgment types, then render a review table that shows accuracy, sample coverage, and what went wrong.

## In Scope

- Statistics derived from auditable decision-ledger rows.
- Coverage metadata for every statistic.
- Separate accuracy rows for exactly these five judgments:
  - market state judgment: whether the market state was correctly classified as attack, retreat, repair, chaotic, or ice point.
  - mainline judgment: whether capital continued to select the same mainline on the next day.
  - core candidate judgment: whether selected stocks entered capital attention.
  - participation rehearsal judgment: whether auction, open, reseal, or divergence paths matched the rehearsal.
  - cancellation condition judgment: whether not buying, staying empty, or giving up a chase avoided loss or invalid action.
- Tests for missing facts and short sample handling.
- Report review output as a table with accuracy and mistake explanation for each judgment type.

## Out of Scope

- Building the historical coverage expansion itself.
- Front-page cockpit redesign.
- Probability recommendation.
- Broad backtesting framework or factor mining.
- More than the five judgment types listed above.
- Detailed factor, drawdown, or risk-reward statistics.

## Non-goals

- Do not present low-sample statistics as stable truth.
- Do not combine the five judgments into one score.
- Do not create next-day action from statistics alone.

## Requirements

- Every statistic includes:
  - sample count,
  - first date,
  - last date,
  - missing-fact count or missing fields,
  - metric definition.
- Statistics must distinguish the five judgment types and keep their accuracy separate.
- Missing facts must not count as correct or wrong.
- Each row must explain the most recent or most representative mistake in a short text field.
- Current covered sample may be used first; 60/120-day views require coverage from the history expansion child task.

## Acceptance Criteria

- [ ] Statistics renderer/helper includes coverage metadata.
- [ ] Tests cover the five judgment types, short sample, missing facts, and mistake text.
- [ ] Report output renders a table with the five judgment rows and each row's accuracy.
- [ ] Report output frames the panel as past evidence, not tomorrow action.

## Definition of Done

- Unit tests pass with Python 3.14.
- Report replay sample passes if rendering changes.
- User-visible text follows terminology rules.

## Technical Approach

- Add a standalone report statistics helper module for the five judgment rows.
- Read explicit `judgment_reviews` rows first when present.
- Fall back only to existing auditable ledger fields:
  - `validation` for mainline continuation,
  - `selection_result` for core candidate visibility,
  - `participation_review` for participation rehearsal and cancellation condition.
- Leave market-state, mainline, or candidate rows as missing facts when the ledger has no settlement evidence for that judgment.
- Keep the first version helper-local and renderer-local unless repeated complexity requires extraction.
- Add probability support only after this panel is stable.
